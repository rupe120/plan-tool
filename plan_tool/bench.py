"""Backend-quality benchmark engine — the task-family × backend × trial matrix.

This module runs the synthetic backend-quality benchmark designed in step 1
(``docs/evidence/benchmark-design.md``). For every ``(family, cell, backend, trial)``
it materializes an isolated scratch workspace (a fresh tempdir + ``git init`` +
a baseline commit, with the step-1 corpus fixtures laid down inside) and drives
the **production entrypoint operators actually call** — never a bespoke
harness prompt:

============== =====================================================
Family         Production entrypoint driven
============== =====================================================
``proposal``   :func:`plan_tool.create.create_plan` (proposal stage)
``detail``     :func:`plan_tool.detail.generate_detail`
``reconcile``  :func:`plan_tool.review.review_plan_full`
``implementation`` :func:`plan_tool.launcher.run_step`
``apply``      :func:`plan_tool.launcher.apply_finding`
============== =====================================================

The matrix axis that makes "claude vs codex" mean anything is
:func:`plan_tool.backend.set_active_backend`: the engine flips the active
backend per trial and lets each entrypoint's *existing default invoker* route
through :func:`plan_tool.backend.get_active_backend`. Codex session hygiene is
automatic — ``CODEX_BACKEND``'s argv builders already carry
``-s workspace-write --skip-git-repo-check --ephemeral`` + ``stdin=DEVNULL``,
so the engine passes **no** codex flags itself.

The per-family ``invoker`` injection parameters every entrypoint already
exposes are reused only as the **test seam** (:class:`BenchInvokers` carries
fixture-replay fakes); a real ``bench run`` passes an empty
:class:`BenchInvokers` so the production default invoker spawns the real
backend.

Scope: step 2 *captures* raw output + wall-clock + None-safe token/stats +
failure classification per trial as JSONL under
``<repo>/.plan-tool/bench/runs/<stamp>/records.jsonl``. It does **not** score
against the step-1 ground truth (step 3's scorers) — :func:`aggregate_run`
here is a deterministic *raw* rollup.

Path conventions mirror :mod:`plan_tool.run_log`: :data:`BENCH_RUNS_REL` is the
sibling of ``run_log.RUNS_REL``, and the run stamp reuses ``run_log``'s run-id
shape (computed by the CLI and passed in, so the engine stays deterministic
given a stamp).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from plan_tool.backend import (
    ClaudeRunStats,
    CliBackend,
    get_active_backend,
    registered_binaries,
    resolve_backend,
    set_active_backend,
)
from plan_tool.claude_errors import ClaudeFailureKind, classify
from plan_tool.run_log import RunLogWriter

# Production entrypoints — driven unchanged so results measure what operators
# get. Imported at module top (no cycle: ``bench`` is a leaf consumed only by
# ``cli.bench_cmd``).
from plan_tool.create import CreateError, create_plan, shell_claude_invoker
from plan_tool.detail import (
    generate_detail,
    parse_acceptance_bullets,
    parse_detail_file_sections,
    shell_detail_invoker,
)
from plan_tool.launcher import apply_finding, run_step, shell_invoker
from plan_tool.parser import ParseError, ValidationError, parse_plan, parse_plan_text
from plan_tool.renderer import prompts_dir
from plan_tool.review import (
    _REQUIRED_DETAIL_SECTION_NAMES,
    check_files_coherence,
    review_plan_full,
    shell_review_invoker,
)
from plan_tool.schema import Plan, PlanStatus, Priority, Step
from plan_tool.scope_guard import (
    compute_in_scope_paths,
    evaluate_apply_scope,
    snapshot_subtrees,
)

# Records sibling to ``run_log.RUNS_REL = (".plan-tool", "runs")``.
BENCH_RUNS_REL = (".plan-tool", "bench", "runs")
RECORDS_FILENAME = "records.jsonl"

# Captured stdout / final text is for triage, not scoring (step 3 reads the
# scratch via its own fixtures); cap it so one JSONL line stays bounded.
_RAW_OUTPUT_CAP = 2000
# Apply diffs are scoped to the plan + one detail file, so this is generous;
# capping keeps the artifact bounded without truncating the landed-edit marker.
_DIFF_TEXT_CAP = 8000

# Design-doc trial count (median over three runs absorbs single-run variance).
DEFAULT_TRIALS = 3
# Per-cell wall-clock cap, seconds. One slow cell never aborts the matrix.
DEFAULT_TIMEOUT_S = 600


# ---------------------------------------------------------------------------
# Path helpers (mirror run_log.py).
# ---------------------------------------------------------------------------


def bench_runs_root(repo_root: Path) -> Path:
    """Return ``<repo_root>/.plan-tool/bench/runs/``."""
    return repo_root.joinpath(*BENCH_RUNS_REL)


def bench_run_dir(repo_root: Path, stamp: str) -> Path:
    """Return the per-stamp run directory under the bench runs root."""
    return bench_runs_root(repo_root) / stamp


def records_path(repo_root: Path, stamp: str) -> Path:
    """Return the append-only ``records.jsonl`` for one bench run."""
    return bench_run_dir(repo_root, stamp) / RECORDS_FILENAME


# ---------------------------------------------------------------------------
# Data shapes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class BenchCell:
    """One unit of work in the matrix: a single corpus fixture under a family.

    ``cell_id`` is a stable slug (e.g. ``proposal/seed-feature``).
    ``fixture_path`` points at the on-disk corpus file the cell loads;
    ``selector`` disambiguates a fixture that holds several cells (a step id
    for ``detail`` / ``implementation``, a repo / finding id for
    ``reconcile`` / ``apply``).
    """

    family: str
    cell_id: str
    fixture_path: Path
    selector: Optional[str] = None


@dataclass(frozen=True)
class BenchInvokers:
    """Per-family invoker overrides — the engine's only test seam.

    Each field defaults to ``None`` → the family's production default invoker
    (which routes through the active backend). Tests pass fakes that replay
    step-1 / codex fixtures; a real ``bench run`` passes the empty
    ``BenchInvokers()`` so every trial spawns the real backend.
    """

    proposal_invoker: Optional[Callable[..., Any]] = None
    detail_invoker: Optional[Callable[..., Any]] = None
    reconcile_invoker: Optional[Callable[..., Any]] = None
    implementation_invoker: Optional[Callable[..., Any]] = None
    apply_invoker: Optional[Callable[..., Any]] = None


@dataclass
class BenchTrialContext:
    """Everything a family's ``run`` callable needs for one trial."""

    cell: BenchCell
    scratch_dir: Path
    invoker: Callable[..., Any]
    run_logger: Optional[RunLogWriter]
    backend: CliBackend


@dataclass(frozen=True)
class BenchTrialResult:
    """What a family ``run`` callable returns for one production-entrypoint call.

    ``exit_code`` feeds :func:`plan_tool.claude_errors.classify` (0 = success).
    ``empty_response_is_failure`` is false for streaming implementation work,
    whose successful result can be exclusively workspace edits. ``verdict`` is
    the entrypoint's semantic outcome (split shape, apply
    verdict, recommendation count, …) recorded as ``exit_or_verdict``.
    ``stats`` is ``None`` for paths that emit no per-call token stats.
    """

    raw_output: str
    exit_code: int
    verdict: Optional[Any] = None
    stderr: str = ""
    stats: Optional[ClaudeRunStats] = None
    retries: int = 0
    empty_response_is_failure: bool = True
    # Per-family captured artifact the step-3 scorers read offline (the
    # produced plan text, the drafted detail body, the reconcile findings,
    # the implementation hidden-test/scope counts, the apply verdict/diff).
    # ``None`` for a failed/timed-out trial that produced nothing to score.
    artifact: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class BenchTrialRecord:
    """One JSONL line: the captured outcome of a single matrix cell trial."""

    family: str
    cell_id: str
    backend: str
    trial: int
    stamp: str
    wall_clock_ms: int
    tokens_input: Optional[int]
    tokens_output: Optional[int]
    cache_creation_tokens: Optional[int]
    cache_read_tokens: Optional[int]
    cost_usd: Optional[float]
    failure_kind: Optional[str]
    retries: int
    exit_or_verdict: Any
    raw_output: str
    # Per-family captured artifact the step-3 scorers read; ``None`` for a
    # trial that produced nothing scorable (timeout, materialize/run crash).
    artifact: Optional[dict[str, Any]] = None


@dataclass(frozen=True)
class BenchFamily:
    """A task family: data pointing at the relocated production call.

    A frozen dataclass-of-callables (not an ABC) so a future sixth family is
    one more literal in :data:`BENCH_FAMILIES`.
    """

    name: str
    corpus_subdir: str
    enumerate_cells: Callable[[Path], list[BenchCell]]
    materialize: Callable[[BenchCell, Path], None]
    run: Callable[[BenchTrialContext], BenchTrialResult]
    default_invoker: Callable[..., Any]


@dataclass
class BenchRunSummary:
    """Outcome of a whole ``run_bench_matrix`` invocation."""

    stamp: str
    run_dir: Path
    cells: int
    records_written: int
    skipped: int


@dataclass
class BenchReport:
    """Raw per-``(family, backend)`` rollup produced by :func:`aggregate_run`."""

    stamp: str
    groups: list[dict[str, Any]]
    total_records: int


# ---------------------------------------------------------------------------
# Corpus loading helpers.
# ---------------------------------------------------------------------------


def _write_repo_map(scratch: Path, repo: dict[str, str]) -> None:
    """Materialize a ``path -> contents`` map into the scratch workspace."""
    for rel, content in repo.items():
        dest = scratch / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")


def _extract_embedded_repo(text: str) -> dict[str, str]:
    """Pull the ``{"repo": {...}}`` map out of a fenced ```json block.

    Used by the ``detail`` fixture whose plan markdown embeds the scratch repo
    as a documented JSON block. Returns ``{}`` when no such block parses.
    """
    for match in re.finditer(r"```json\s*\n(.*?)\n```", text, re.DOTALL):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("repo"), dict):
            return obj["repo"]
    return {}


def _parse_impl_step_names(text: str) -> list[str]:
    """Extract the ``STEP SPEC N — <name>`` identifiers from the impl corpus."""
    return re.findall(r"STEP SPEC\s+\d+\s*[—-]\s*(\S+)", text)


def _parse_impl_seed(text: str) -> dict[str, str]:
    """Extract the embedded ``path -> contents`` seed from the impl docstring.

    The implementation corpus carries its scratch seed as an indented text
    block under an ``EMBEDDED SCRATCH-REPO SEED`` marker. Returns ``{}`` when
    the marker isn't found so the caller can fall back to a stub.
    """
    idx = text.find("EMBEDDED SCRATCH-REPO SEED")
    if idx < 0:
        return {}
    region = text[idx:]
    seed: dict[str, str] = {}
    for match in re.finditer(
        r"^(\S+\.\w+):\s*\n(.*?)(?=^={3,}|\Z)", region, re.DOTALL | re.MULTILINE
    ):
        path = match.group(1)
        body = textwrap.dedent(match.group(2)).strip("\n")
        if body:
            seed[path] = body + "\n"
    return seed


def _synth_impl_plan(names: list[str]) -> str:
    """Synthesize a minimal plan whose steps map to the impl step specs.

    Steps are independent (no ``depends_on``) so each cell's ``run_step`` is
    runnable on its own.
    """
    steps = "\n".join(
        f"- id: {i}\n"
        f"  title: Implement {name} in solution.py\n"
        f"  files:\n"
        f"  - solution.py\n"
        f"  change_type: feature"
        for i, name in enumerate(names, start=1)
    )
    return (
        "---\n"
        "title: Implementation bench fixture\n"
        "status: planning\n"
        "priority: low\n"
        # The gate must not reference hidden_tests.py — the answer key
        # lands only AFTER run_step (corpus contract), so a pytest gate
        # on it exits 4 (nothing to collect) and poisons every trial's
        # failure_kind. An import check still catches syntax/parse
        # errors in the backend's edit; the hidden-test pass signal is
        # captured separately at artifact time.
        "test_command: python -c 'import solution'\n"
        "steps:\n"
        f"{steps}\n"
        "---\n"
        "# Implementation bench fixture\n"
    )


# ---------------------------------------------------------------------------
# Per-family cell enumeration.
# ---------------------------------------------------------------------------


def _proposal_cells(corpus_dir: Path) -> list[BenchCell]:
    return [
        BenchCell("proposal", f"proposal/{p.stem}", p)
        for p in sorted(corpus_dir.glob("seed-*.md"))
    ]


def _detail_cells(corpus_dir: Path) -> list[BenchCell]:
    fixture = corpus_dir / "fixture-plan.md"
    if not fixture.is_file():
        return []
    plan = parse_plan(fixture)
    return [
        BenchCell("detail", f"detail/step-{step.id}", fixture, selector=str(step.id))
        for step in plan.steps
    ]


def _reconcile_cells(corpus_dir: Path) -> list[BenchCell]:
    fixture = corpus_dir / "seeded-defects.json"
    if not fixture.is_file():
        return []
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return [
        BenchCell("reconcile", f"reconcile/{r['id']}", fixture, selector=r["id"])
        for r in data.get("repos", [])
    ]


def _implementation_cells(corpus_dir: Path) -> list[BenchCell]:
    fixture = corpus_dir / "hidden-tests.py"
    if not fixture.is_file():
        return []
    names = _parse_impl_step_names(fixture.read_text(encoding="utf-8"))
    return [
        BenchCell("implementation", f"implementation/{name}", fixture, selector=str(i))
        for i, name in enumerate(names, start=1)
    ]


def _apply_cells(corpus_dir: Path) -> list[BenchCell]:
    fixture = corpus_dir / "findings.json"
    if not fixture.is_file():
        return []
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return [
        BenchCell("apply", f"apply/{f['id']}", fixture, selector=f["id"])
        for f in data.get("findings", [])
    ]


# ---------------------------------------------------------------------------
# Per-family materialization (lay the corpus into the scratch workspace).
# ---------------------------------------------------------------------------


def _materialize_proposal(cell: BenchCell, scratch: Path) -> None:
    # The seed is prose handed to ``create_plan`` at run time; nothing to lay
    # down beyond the git-initialized scratch root the runner already builds.
    return None


def _materialize_detail(cell: BenchCell, scratch: Path) -> None:
    text = cell.fixture_path.read_text(encoding="utf-8")
    (scratch / "plan.md").write_text(text, encoding="utf-8")
    _write_repo_map(scratch, _extract_embedded_repo(text))


def _materialize_reconcile(cell: BenchCell, scratch: Path) -> None:
    data = json.loads(cell.fixture_path.read_text(encoding="utf-8"))
    entry = next(r for r in data["repos"] if r["id"] == cell.selector)
    _write_repo_map(scratch, entry.get("repo", {}))


def _materialize_implementation(cell: BenchCell, scratch: Path) -> None:
    text = cell.fixture_path.read_text(encoding="utf-8")
    seed = _parse_impl_seed(text) or {
        "solution.py": (
            "def slugify(text):\n    raise NotImplementedError\n\n\n"
            "def truncate_words(text, max_words):\n    raise NotImplementedError\n"
        )
    }
    _write_repo_map(scratch, seed)
    # hidden_tests.py is deliberately NOT materialized here — it is the
    # answer key, and the corpus contract says the backend never sees it.
    # ``_run_implementation`` drops it into the scratch AFTER run_step
    # returns, just before the capture-time pytest run.
    names = _parse_impl_step_names(text) or ["slugify", "truncate_words"]
    (scratch / "plan.md").write_text(_synth_impl_plan(names), encoding="utf-8")


def _materialize_apply(cell: BenchCell, scratch: Path) -> None:
    data = json.loads(cell.fixture_path.read_text(encoding="utf-8"))
    entry = next(f for f in data["findings"] if f["id"] == cell.selector)
    _write_repo_map(scratch, entry.get("repo", {}))


# ---------------------------------------------------------------------------
# Capture-time helpers (the one live-workspace execution: hidden tests + scope).
# ---------------------------------------------------------------------------


# The scope snapshot must ignore the run-log the trial itself writes under
# ``.plan-tool/`` — that churn is the bench's own bookkeeping, not a backend
# edit, and counting it would inflate every out-of-scope number. Extends
# ``snapshot_subtrees``'s vendored/cache excludes with the run-log root.
_SCOPE_SNAPSHOT_EXCLUDES = frozenset(
    {
        ".venv",
        ".pytest_cache",
        "dist",
        "__pycache__",
        ".git",
        "node_modules",
        ".plan-tool",
    }
)


def _scope_snapshot(scratch: Path) -> dict[Path, Optional[str]]:
    """Snapshot the scratch tree for scope evaluation, ignoring run-log churn."""
    return snapshot_subtrees([scratch], exclude_parts=_SCOPE_SNAPSHOT_EXCLUDES)


_PYTEST_COUNT_RE = re.compile(r"(\d+)\s+(passed|failed|error|errors)\b")


def _count_pytest_results(output: str) -> tuple[int, int]:
    """Parse ``N passed`` / ``N failed`` / ``N error(s)`` from pytest output.

    Returns ``(passed, total)`` where ``total = passed + failed + errors``.
    Tolerant of any summary-line variant; ``(0, 0)`` when nothing parsed.
    """
    passed = failed = errors = 0
    for match in _PYTEST_COUNT_RE.finditer(output):
        n = int(match.group(1))
        kind = match.group(2)
        if kind == "passed":
            passed = n
        elif kind == "failed":
            failed = n
        else:  # "error" / "errors"
            errors = n
    return passed, passed + failed + errors


def _run_hidden_tests(scratch: Path) -> tuple[int, int]:
    """Run the materialized ``hidden_tests.py`` against the scratch tree.

    The hidden-test file is the implementation family's answer key — it was
    never shown to the backend. Runs it as a fresh pytest subprocess (cwd =
    scratch so ``from solution import ...`` resolves) and returns
    ``(passed, total)``. ``(0, 0)`` when the file is missing or pytest can't
    be spawned.
    """
    test_file = scratch / "hidden_tests.py"
    if not test_file.is_file():
        return 0, 0
    try:
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "pytest",
                "hidden_tests.py",
                "-q",
                "--tb=no",
                "-p",
                "no:cacheprovider",
            ],
            cwd=str(scratch),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError):
        return 0, 0
    return _count_pytest_results(proc.stdout + proc.stderr)


def _count_out_of_scope(
    plan_path: Path,
    repo_root: Path,
    *,
    pre_snapshot: dict[Path, Optional[str]],
    post_snapshot: dict[Path, Optional[str]],
    finding_id: str,
    step_id: Optional[int],
) -> int:
    """Count edited files outside the plan's in-scope set (docs excluded).

    Reuses the production :func:`plan_tool.scope_guard.evaluate_apply_scope`
    over a pre/post snapshot pair so the bench's scope-cleanliness number
    matches what the real scope guard would flag. ``kept-documentation``
    records are excluded (the step-1 rubric scores only code drift). Returns
    ``0`` on any parse/evaluate failure so a capture hiccup never aborts the
    trial.
    """
    try:
        plan = parse_plan(plan_path)
        in_scope = compute_in_scope_paths(plan, plan_path, repo_root)
        records = evaluate_apply_scope(
            finding_id=finding_id,
            finding_body="",
            step_id=step_id,
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            in_scope_paths=in_scope,
            repo_root=repo_root,
        )
    except Exception:
        return 0
    return sum(
        len(rec.out_of_scope_files)
        for rec in records
        if rec.impact_status != "kept-documentation"
    )


def _capture_implementation_artifact(
    plan_path: Path,
    repo_root: Path,
    *,
    pre_snapshot: dict[Path, Optional[str]],
    post_snapshot: dict[Path, Optional[str]],
    test_command_exit: int,
) -> dict[str, Any]:
    """Build the implementation family's numeric artifact at trial time.

    Records the hidden-test pass count, the ``test_command`` exit, and the
    out-of-scope file count — all numbers, so the scorer stays a pure
    function over data and the trial need not be re-run to re-score.
    """
    passed, total = _run_hidden_tests(repo_root)
    out_of_scope = _count_out_of_scope(
        plan_path,
        repo_root,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        finding_id="implementation",
        step_id=None,
    )
    return {
        "hidden_tests_passed": passed,
        "hidden_tests_total": total,
        "test_command_exit": test_command_exit,
        "out_of_scope_file_count": out_of_scope,
    }


# ---------------------------------------------------------------------------
# Per-family run (drive the production entrypoint — no bespoke prompt).
# ---------------------------------------------------------------------------


def _skip_risk_classification_prompt(
    invoker: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap ``invoker`` so a risk-classification prompt never reaches it.

    ``create_plan`` always classifies a non-empty seed's risk profile before
    publication, and its public signature is frozen
    (``test_create_plan_signature_is_exact``) so the proposal trial cannot
    ask it to skip that call. Answering the classifier prompt locally keeps
    the trial's measured token/latency signal isolated to the one proposal
    round-trip, matching every other optional phase this trial disables
    below. The marker is read from the live prompt template rather than
    duplicated here, so a reworded template can't silently stop matching.
    """
    marker = (
        (prompts_dir() / "classify-risk-profile.md")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )

    def _shim(prompt: str, *args: Any, **kwargs: Any) -> Any:
        if prompt.startswith(marker):
            return ""
        return invoker(prompt, *args, **kwargs)

    return _shim


def _run_proposal(ctx: BenchTrialContext) -> BenchTrialResult:
    seed_body = ctx.cell.fixture_path.read_text(encoding="utf-8")
    slug = ctx.cell.cell_id.split("/")[-1]
    # Drive create_plan's proposal/split path; iteration, body synthesis and
    # doc fetch disabled to isolate the proposal signal. distill=True so the
    # must-split seed exercises real split detection surfaced on
    # CreateResult.split_proposal.
    try:
        result = create_plan(
            slug,
            repo_root=ctx.scratch_dir,
            # Contain the manifest inside the scratch repo — the default is the
            # installed package's structured_plans.json, which a benchmark run
            # must never touch.
            manifest_path=ctx.scratch_dir / "structured_plans.json",
            from_description=seed_body,
            input_fn=lambda _prompt: "",
            claude_invoker=_skip_risk_classification_prompt(ctx.invoker),
            yes=True,
            resume=False,
            synthesize_body=False,
            # Unscored, like body synthesis above: the proposal rubric reads
            # steps, change_types, and dependency shape. Leaving the intent
            # offer on would put a second, unrelated backend call inside a
            # trial whose whole purpose is to isolate the proposal signal, so
            # every token and latency number would measure two prompts.
            offer_intents=False,
            # Body sections are unscored — the proposal rubric reads steps,
            # change_types, and dependency shape. Without this bypass the
            # fail-loud ``_(TODO)_`` gate kills every single-plan trial
            # (synthesize_body=False + no iteration leaves Risks/Deferred
            # as placeholders), measuring the wrapper instead of the
            # backend.
            allow_placeholder_body=True,
            fetch_docs=False,
            distill=True,
            run_logger=ctx.run_logger,
        )
    except CreateError as exc:
        return BenchTrialResult(raw_output=str(exc), exit_code=1, verdict=None)
    split = result.split_proposal is not None
    # The produced plan text (single-plan path) drives proposal validity +
    # change_type scoring; the multi-plan split short-circuit writes no plan
    # but carries >= 2 proposal entries, the must-split signal.
    plan_text: Optional[str] = None
    if result.plan_path is not None and Path(result.plan_path).is_file():
        plan_text = Path(result.plan_path).read_text(encoding="utf-8")
    entry_count = len(result.split_proposal.entries) if result.split_proposal else 0
    return BenchTrialResult(
        raw_output=f"split_proposal={split}",
        exit_code=0,
        verdict="must-split" if split else "single-plan",
        artifact={
            "plan_text": plan_text,
            "split_proposal_entry_count": entry_count,
        },
    )


def _run_detail(ctx: BenchTrialContext) -> BenchTrialResult:
    plan_path = ctx.scratch_dir / "plan.md"
    results = generate_detail(
        plan_path,
        repo_root=ctx.scratch_dir,
        step_id=int(ctx.cell.selector) if ctx.cell.selector else None,
        invoker=ctx.invoker,
        extract_lessons=False,
        resume=False,
        run_logger=ctx.run_logger,
    )
    written = any(r.written for r in results)
    reason = next((r.skipped_reason for r in results if r.skipped_reason), None)
    # Capture the drafted detail body off disk so the scorer can re-parse its
    # H2s / acceptance bullets and re-run check_files_coherence offline.
    step_id = int(ctx.cell.selector) if ctx.cell.selector else None
    detail_body: Optional[str] = None
    for r in results:
        if r.output_path.is_file():
            detail_body = r.output_path.read_text(encoding="utf-8")
            break
    return BenchTrialResult(
        raw_output=str(reason or "written"),
        exit_code=0 if written else 1,
        verdict="written" if written else (reason or "skipped"),
        artifact={"detail_body": detail_body, "step_id": step_id},
    )


def _run_reconcile(ctx: BenchTrialContext) -> BenchTrialResult:
    data = json.loads(ctx.cell.fixture_path.read_text(encoding="utf-8"))
    entry = next(r for r in data["repos"] if r["id"] == ctx.cell.selector)
    plan_path = ctx.scratch_dir / entry.get("plan_path", "plan.md")
    result = review_plan_full(
        plan_path,
        repo_root=ctx.scratch_dir,
        plan_name=str(ctx.cell.selector),
        invoker=ctx.invoker,
        extract_lessons=False,
    )
    count = len(result.recommendations)
    # Normalize each reported finding to its searchable text (title + body);
    # the scorer fuzzy-matches file+symbol mentions in this text against the
    # seeded-defect manifest, agnostic to which check surfaced the finding.
    findings = [
        f"{rec.title}\n{rec.body}" for rec in result.recommendations
    ]
    return BenchTrialResult(
        raw_output=f"recommendations={count}",
        exit_code=0,
        verdict=f"recommendations={count}",
        artifact={"findings": findings},
    )


def _run_implementation(ctx: BenchTrialContext) -> BenchTrialResult:
    plan_path = ctx.scratch_dir / "plan.md"
    # Snapshot the scratch tree around run_step so the scope-guard sees the
    # backend's edits; the hidden-test run + scope evaluation are the one
    # capture-time execution that needs the live workspace (step 3 keeps the
    # scorer itself pure by recording only their numeric results).
    pre_snapshot = _scope_snapshot(ctx.scratch_dir)
    result = run_step(
        plan_path,
        repo_root=ctx.scratch_dir,
        step_id=int(ctx.cell.selector) if ctx.cell.selector else None,
        mode="run",
        invoker=ctx.invoker,
        run_logger=ctx.run_logger,
    )
    post_snapshot = _scope_snapshot(ctx.scratch_dir)
    # The answer key lands only now — after the backend has run and after
    # the post-snapshot, so it is neither readable by the backend (found
    # live: a trial transcript quoted the step specs from the materialized
    # copy) nor counted as a backend edit by the scope guard.
    (ctx.scratch_dir / "hidden_tests.py").write_text(
        ctx.cell.fixture_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    artifact = _capture_implementation_artifact(
        plan_path,
        ctx.scratch_dir,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        test_command_exit=result.exit_code,
    )
    return BenchTrialResult(
        raw_output=result.stdout,
        exit_code=result.exit_code,
        verdict=f"exit={result.exit_code}",
        stats=getattr(ctx.invoker, "_last_stats", None),
        empty_response_is_failure=False,
        artifact=artifact,
    )


def _run_apply(ctx: BenchTrialContext) -> BenchTrialResult:
    data = json.loads(ctx.cell.fixture_path.read_text(encoding="utf-8"))
    entry = next(f for f in data["findings"] if f["id"] == ctx.cell.selector)
    plan_path = ctx.scratch_dir / entry.get("plan_path", "plan.md")
    pre_snapshot = _scope_snapshot(ctx.scratch_dir)
    result = apply_finding(
        plan_path,
        repo_root=ctx.scratch_dir,
        finding_body=entry["finding_body"],
        step_id=entry.get("target_step_id"),
        plan_name=str(ctx.cell.selector),
        invoker=ctx.invoker,
        run_logger=ctx.run_logger,
    )
    post_snapshot = _scope_snapshot(ctx.scratch_dir)
    out_of_scope = _count_out_of_scope(
        plan_path,
        ctx.scratch_dir,
        pre_snapshot=pre_snapshot,
        post_snapshot=post_snapshot,
        finding_id=str(ctx.cell.selector),
        step_id=entry.get("target_step_id"),
    )
    return BenchTrialResult(
        raw_output=result.stdout,
        exit_code=result.exit_code,
        verdict=result.verdict,
        stats=getattr(ctx.invoker, "_last_stats", None),
        artifact={
            "verdict": result.verdict,
            "diff_text": result.diff_text[:_DIFF_TEXT_CAP],
            "out_of_scope_file_count": out_of_scope,
        },
    )


BENCH_FAMILIES: dict[str, BenchFamily] = {
    "proposal": BenchFamily(
        name="proposal",
        corpus_subdir="proposal",
        enumerate_cells=_proposal_cells,
        materialize=_materialize_proposal,
        run=_run_proposal,
        default_invoker=shell_claude_invoker,
    ),
    "detail": BenchFamily(
        name="detail",
        corpus_subdir="detail",
        enumerate_cells=_detail_cells,
        materialize=_materialize_detail,
        run=_run_detail,
        default_invoker=shell_detail_invoker,
    ),
    "reconcile": BenchFamily(
        name="reconcile",
        corpus_subdir="reconcile",
        enumerate_cells=_reconcile_cells,
        materialize=_materialize_reconcile,
        run=_run_reconcile,
        default_invoker=shell_review_invoker,
    ),
    "implementation": BenchFamily(
        name="implementation",
        corpus_subdir="implementation",
        enumerate_cells=_implementation_cells,
        materialize=_materialize_implementation,
        run=_run_implementation,
        default_invoker=shell_invoker,
    ),
    "apply": BenchFamily(
        name="apply",
        corpus_subdir="apply",
        enumerate_cells=_apply_cells,
        materialize=_materialize_apply,
        run=_run_apply,
        default_invoker=shell_invoker,
    ),
}


# ---------------------------------------------------------------------------
# Scratch isolation + stats capture.
# ---------------------------------------------------------------------------


def _git_init_scratch(scratch: Path) -> None:
    """``git init`` + throwaway identity so a baseline commit can succeed."""
    subprocess.run(
        ["git", "init", "-q"],
        cwd=scratch,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        check=True,
    )
    for key, value in (
        ("user.email", "bench@plan-tool.local"),
        ("user.name", "plan-tool bench"),
    ):
        subprocess.run(
            ["git", "config", key, value],
            cwd=scratch,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            check=True,
        )


def _git_commit_baseline(scratch: Path) -> None:
    """Commit the materialized fixtures so apply/scope-guard see a clean tree."""
    subprocess.run(
        ["git", "add", "-A"],
        cwd=scratch,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-q", "-m", "bench baseline", "--no-verify"],
        cwd=scratch,
        stdin=subprocess.DEVNULL,
        capture_output=True,
    )


_EMPTY_STATS_FIELDS = {
    "tokens_input": None,
    "tokens_output": None,
    "cache_creation_tokens": None,
    "cache_read_tokens": None,
    "cost_usd": None,
}


def _stats_to_fields(stats: ClaudeRunStats) -> dict[str, Any]:
    return {
        "tokens_input": stats.tokens_input,
        "tokens_output": stats.tokens_output,
        "cache_creation_tokens": stats.cache_creation_tokens,
        "cache_read_tokens": stats.cache_read_tokens,
        "cost_usd": stats.cost_usd,
    }


def _read_log_stats(log_path: Optional[Path]) -> dict[str, Any]:
    """Aggregate token/cost fields from a trial's run-log, None-safe.

    Batch families (proposal / detail / reconcile) emit no per-call token
    stats, and fake invokers never spawn the streaming path — both leave every
    field ``None`` here, the same Optional contract ``run_log.ClaudeCallEnd``
    and ``cli/runs.py`` already tolerate.
    """
    fields: dict[str, Any] = dict(_EMPTY_STATS_FIELDS)
    if log_path is None or not log_path.is_file():
        return fields
    try:
        for raw in log_path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("event") != "claude_call_end":
                continue
            for key in fields:
                value = event.get(key)
                if isinstance(value, (int, float)):
                    fields[key] = (fields[key] or 0) + value
    except OSError:
        pass
    return fields


def _select_invoker(family: BenchFamily, invokers: BenchInvokers) -> Callable[..., Any]:
    override = getattr(invokers, f"{family.name}_invoker", None)
    return override if override is not None else family.default_invoker


def _run_with_timeout(
    fn: Callable[[], Any], timeout_s: Optional[float]
) -> tuple[str, Any]:
    """Run ``fn`` with a wall-clock cap, returning ``("ok", value)`` or
    ``("timeout", None)``.

    Python can't kill the worker thread, so a timed-out trial's thread runs to
    completion in the background (harmless — it writes only into a scratch dir
    that is discarded). Re-raises any exception ``fn`` raised so the caller can
    classify it.
    """
    box: dict[str, Any] = {}

    def _worker() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 - surfaced to caller
            box["error"] = exc

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    thread.join(timeout_s)
    if thread.is_alive():
        return "timeout", None
    if "error" in box:
        raise box["error"]
    return "ok", box["value"]


def _run_cell_trial(
    family: BenchFamily,
    cell: BenchCell,
    backend_name: str,
    trial: int,
    *,
    stamp: str,
    scratch_parent: Path,
    invokers: BenchInvokers,
    timeout_s: Optional[float],
    retain_scratch: bool,
) -> BenchTrialRecord:
    """Run one ``(family, cell, backend, trial)`` and return its record.

    Always returns a record: a materialize/run failure is classified (via the
    *active* backend) and recorded so the matrix count holds regardless of any
    one family's internals. Swaps the active backend before the entrypoint call
    and restores the prior backend in ``finally``.
    """
    backend = resolve_backend(backend_name)
    prior_backend = get_active_backend()
    scratch = Path(tempfile.mkdtemp(prefix="benchcell-", dir=str(scratch_parent)))
    started = time.monotonic()
    failure_kind: Optional[str] = None
    verdict: Any = None
    raw_output = ""
    exit_code = 0
    retries = 0
    artifact: Optional[dict[str, Any]] = None
    stats_fields = dict(_EMPTY_STATS_FIELDS)

    try:
        invoker = _select_invoker(family, invokers)
        writer: Optional[RunLogWriter] = None
        try:
            writer = RunLogWriter.start(
                repo_root=scratch,
                slug=cell.cell_id.replace("/", "__"),
                command="bench",
                argv=[],
            )
        except Exception:
            writer = None
        ctx = BenchTrialContext(
            cell=cell,
            scratch_dir=scratch,
            invoker=invoker,
            run_logger=writer,
            backend=backend,
        )

        def _do() -> BenchTrialResult:
            _git_init_scratch(scratch)
            family.materialize(cell, scratch)
            _git_commit_baseline(scratch)
            # Backend-subprocess cwd is owned by the production
            # entrypoints now: each one is decorated with
            # ``backend.spawn_cwd_from_repo_root``, so the
            # ``repo_root=scratch`` this trial passes scopes every spawn
            # to the scratch tree (the per-trial ``os.chdir`` this
            # replaced is in the lessons log — found live when
            # implementation trials edited the invoking repo).
            return family.run(ctx)

        set_active_backend(backend)
        status, value = _run_with_timeout(_do, timeout_s)
        if status == "timeout":
            failure_kind = "timeout"
            raw_output = "trial exceeded per-cell timeout"
            exit_code = 124
        else:
            result: BenchTrialResult = value
            raw_output = result.raw_output
            exit_code = result.exit_code
            verdict = result.verdict
            retries = result.retries
            artifact = result.artifact
            kind = classify(
                exit_code,
                raw_output,
                result.stderr,
                empty_response_is_failure=result.empty_response_is_failure,
            ).kind
            failure_kind = None if kind == ClaudeFailureKind.SUCCESS else kind.value
            if result.stats is not None:
                stats_fields = _stats_to_fields(result.stats)
            elif writer is not None:
                stats_fields = _read_log_stats(writer.log_path)
    except Exception as exc:  # materialize / run raised — record, don't abort
        raw_output = f"{type(exc).__name__}: {exc}"
        exit_code = 1
        kind = classify(exit_code, raw_output, "").kind
        failure_kind = None if kind == ClaudeFailureKind.SUCCESS else kind.value
    finally:
        set_active_backend(prior_backend)
        wall_clock_ms = int((time.monotonic() - started) * 1000)
        if not retain_scratch:
            shutil.rmtree(scratch, ignore_errors=True)

    return BenchTrialRecord(
        family=family.name,
        cell_id=cell.cell_id,
        backend=backend_name,
        trial=trial,
        stamp=stamp,
        wall_clock_ms=wall_clock_ms,
        failure_kind=failure_kind,
        retries=retries,
        exit_or_verdict=verdict if verdict is not None else exit_code,
        raw_output=raw_output[:_RAW_OUTPUT_CAP],
        artifact=artifact,
        **stats_fields,
    )


# ---------------------------------------------------------------------------
# Records I/O + resume.
# ---------------------------------------------------------------------------


def _append_record(rec_path: Path, record: BenchTrialRecord) -> None:
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    with rec_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")


def _read_records(rec_path: Path) -> list[dict[str, Any]]:
    if not rec_path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for raw in rec_path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            records.append(obj)
    return records


def _completed_keys(rec_path: Path) -> set[tuple[str, str, str, int]]:
    keys: set[tuple[str, str, str, int]] = set()
    for r in _read_records(rec_path):
        try:
            keys.add((r["family"], r["cell_id"], r["backend"], int(r["trial"])))
        except (KeyError, TypeError, ValueError):
            continue
    return keys


def _default_backend_names() -> list[str]:
    """All registered backends (binary == registry name for claude / codex)."""
    return sorted(registered_binaries())


# ---------------------------------------------------------------------------
# Capture-time run metadata — the staleness facts the recommendations doc dates
# itself by. Backend versions and corpus hash are recorded *as measured* at
# ``bench run`` time (a ``CliBackend`` carries no version field, so the version
# is probed live), never recomputed at report time. The report later recomputes
# the current corpus hash and flags drift against the recorded one.
# ---------------------------------------------------------------------------

RUN_META_FILENAME = "run_meta.json"


@dataclass(frozen=True)
class BackendVersion:
    """One backend's name and the version string probed at run time."""

    name: str
    version: Optional[str]

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackendVersion":
        return cls(name=data.get("name", ""), version=data.get("version"))


@dataclass(frozen=True)
class RunMeta:
    """The staleness facts a run dir records about what produced its numbers."""

    stamp: str
    backends: tuple[BackendVersion, ...]
    corpus_hash: str
    corpus_cell_count: int
    trials: int
    families: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "stamp": self.stamp,
            "backends": [b.to_dict() for b in self.backends],
            "corpus_hash": self.corpus_hash,
            "corpus_cell_count": self.corpus_cell_count,
            "trials": self.trials,
            "families": list(self.families),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RunMeta":
        return cls(
            stamp=data.get("stamp", ""),
            backends=tuple(
                BackendVersion.from_dict(b) for b in data.get("backends", [])
            ),
            corpus_hash=data.get("corpus_hash", ""),
            corpus_cell_count=int(data.get("corpus_cell_count", 0)),
            trials=int(data.get("trials", 0)),
            families=tuple(data.get("families", [])),
        )


def corpus_hash(corpus_root: Path) -> str:
    """Order-stable 8-hex digest over every corpus file's path + bytes.

    ``hashlib.sha256`` (the algorithm of :data:`plan_tool.checkpoint._HASH_ALGO`)
    over the sorted relative-path + content of each file under ``corpus_root``,
    truncated to 8 hex chars (the ``[:8]`` convention of
    :func:`plan_tool.review._make_rec_id`). Sorting makes the digest independent
    of filesystem iteration order; a missing root hashes to the empty digest so
    a report over a stub corpus never crashes.
    """
    digest = hashlib.sha256()
    if corpus_root.is_dir():
        for path in sorted(p for p in corpus_root.rglob("*") if p.is_file()):
            rel = path.relative_to(corpus_root).as_posix()
            digest.update(rel.encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")
    return digest.hexdigest()[:8]


def _default_version_probe(backend: CliBackend) -> Optional[str]:
    """Probe ``<binary> --version`` for a backend's version string, or ``None``.

    ``shutil.which`` first so an absent binary returns ``None`` without a spawn;
    then a short ``--version`` subprocess. Any failure (binary missing, probe
    error, or the test suite's real-subprocess guard) returns ``None`` so the
    capture is best-effort and never aborts a run.
    """
    try:
        if shutil.which(backend.binary) is None:
            return None
        proc = subprocess.run(
            [backend.binary, "--version"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except Exception:  # noqa: BLE001 - best-effort; never aborts a run
        return None
    return (proc.stdout or "").strip() or (proc.stderr or "").strip() or None


def write_run_meta(run_dir: Path, meta: RunMeta) -> Path:
    """Write ``run_meta.json`` into the run dir and return its path."""
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / RUN_META_FILENAME
    path.write_text(json.dumps(meta.to_dict(), indent=2), encoding="utf-8")
    return path


def load_run_meta(run_dir: Path) -> Optional[RunMeta]:
    """Load a run dir's ``run_meta.json``, or ``None`` for a legacy run dir.

    A run dir captured before run-meta was recorded simply has no
    ``run_meta.json``; the report renders the staleness header with versions
    marked unrecorded rather than raising.
    """
    path = run_dir / RUN_META_FILENAME
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return RunMeta.from_dict(data)


# ---------------------------------------------------------------------------
# Matrix driver + raw aggregation.
# ---------------------------------------------------------------------------


def run_bench_matrix(
    repo_root: Path,
    *,
    corpus_root: Path,
    stamp: str,
    backends: Optional[list[str]] = None,
    families: Optional[list[str]] = None,
    trials: int = DEFAULT_TRIALS,
    timeout_s: Optional[float] = DEFAULT_TIMEOUT_S,
    resume: bool = True,
    invokers: Optional[BenchInvokers] = None,
    retain_scratch: bool = False,
    version_probe: Callable[[CliBackend], Optional[str]] = _default_version_probe,
) -> BenchRunSummary:
    """Run the task-family × backend × trial matrix, appending one JSONL record
    per cell trial under ``<repo>/.plan-tool/bench/runs/<stamp>/``.

    ``--backends`` / ``--families`` / ``--trials`` narrow the iterated axes
    (defaults: all registered backends, all families, :data:`DEFAULT_TRIALS`).
    With ``resume=True`` (default) completed ``(family, cell, backend, trial)``
    cells are skipped, so re-invocation with the same stamp runs zero new
    trials once complete. A trial exceeding ``timeout_s`` records
    ``failure_kind="timeout"`` and the matrix continues.
    """
    invokers = invokers or BenchInvokers()
    backend_names = backends if backends else _default_backend_names()
    family_names = families if families else list(BENCH_FAMILIES)

    run_dir = bench_run_dir(repo_root, stamp)
    run_dir.mkdir(parents=True, exist_ok=True)
    rec_path = run_dir / RECORDS_FILENAME
    completed = _completed_keys(rec_path) if resume else set()

    if retain_scratch:
        scratch_parent = run_dir / "scratch"
        scratch_parent.mkdir(parents=True, exist_ok=True)
    else:
        scratch_parent = Path(tempfile.gettempdir())

    cells: list[tuple[BenchFamily, BenchCell]] = []
    for fam_name in family_names:
        family = BENCH_FAMILIES[fam_name]
        for cell in family.enumerate_cells(corpus_root / family.corpus_subdir):
            cells.append((family, cell))

    # Record the staleness facts *as measured* now (additive — no effect on the
    # matrix/resume/record-writing below). Each selected backend's version is
    # probed once; the corpus hash dates the numbers to this corpus state.
    write_run_meta(
        run_dir,
        RunMeta(
            stamp=stamp,
            backends=tuple(
                BackendVersion(
                    name=name, version=version_probe(resolve_backend(name))
                )
                for name in backend_names
            ),
            corpus_hash=corpus_hash(corpus_root),
            corpus_cell_count=len(cells),
            trials=trials,
            families=tuple(family_names),
        ),
    )

    written = 0
    skipped = 0
    for family, cell in cells:
        for backend_name in backend_names:
            for trial in range(1, trials + 1):
                key = (family.name, cell.cell_id, backend_name, trial)
                if key in completed:
                    skipped += 1
                    continue
                record = _run_cell_trial(
                    family,
                    cell,
                    backend_name,
                    trial,
                    stamp=stamp,
                    scratch_parent=scratch_parent,
                    invokers=invokers,
                    timeout_s=timeout_s,
                    retain_scratch=retain_scratch,
                )
                _append_record(rec_path, record)
                completed.add(key)
                written += 1

    return BenchRunSummary(
        stamp=stamp,
        run_dir=run_dir,
        cells=len(cells),
        records_written=written,
        skipped=skipped,
    )


def aggregate_run(run_dir: Path) -> BenchReport:
    """Read ``records.jsonl`` and roll up per ``(family, backend)``.

    Raw only: completed-trial counts, wall-clock totals/means, None-skipping
    token totals, and failure-kind counts. No rubric scoring (step 4).
    """
    rec_path = run_dir / RECORDS_FILENAME
    records = _read_records(rec_path)
    groups: dict[tuple[str, str], dict[str, Any]] = {}
    for r in records:
        key = (r.get("family", "?"), r.get("backend", "?"))
        group = groups.setdefault(
            key,
            {
                "family": key[0],
                "backend": key[1],
                "trials": 0,
                "wall_ms_total": 0,
                "wall_ms_mean": None,
                "tokens_input": None,
                "tokens_output": None,
                "cost_usd": None,
                "failures": {},
                "_walls": [],
            },
        )
        group["trials"] += 1
        fk = r.get("failure_kind")
        if fk:
            group["failures"][fk] = group["failures"].get(fk, 0) + 1
        wall = r.get("wall_clock_ms")
        if isinstance(wall, (int, float)):
            group["_walls"].append(int(wall))
        for token_key in ("tokens_input", "tokens_output", "cost_usd"):
            value = r.get(token_key)
            if isinstance(value, (int, float)):
                group[token_key] = (group[token_key] or 0) + value

    out: list[dict[str, Any]] = []
    for _key, group in sorted(groups.items()):
        walls = group.pop("_walls")
        group["wall_ms_total"] = sum(walls) if walls else 0
        group["wall_ms_mean"] = int(sum(walls) / len(walls)) if walls else None
        out.append(group)

    return BenchReport(stamp=run_dir.name, groups=out, total_records=len(records))


# ---------------------------------------------------------------------------
# Step 3 — per-family scorers: pure functions over captured trial artifacts.
#
# Each scorer is ``(<family>Artifact, <family>AnswerKey) -> <family>Score``,
# reads only the persisted artifact plus the step-1 corpus answer key, spawns
# no backend, and reuses the production deterministic primitive the rubric
# names. Every ``<family>Score`` exposes its raw metric components alongside a
# single normalized ``value`` in ``[0.0, 1.0]`` so a low score is
# self-explaining without re-running a backend. Cross-metric weighting and the
# comparative table are step 4 — ``value`` is the family's headline number only.
# ---------------------------------------------------------------------------


def _mean(values: list[float]) -> float:
    """Arithmetic mean, ``0.0`` for an empty list."""
    return sum(values) / len(values) if values else 0.0


def _f1(recall: float, precision: float) -> float:
    """Harmonic mean of recall and precision; ``0.0`` when both are ``0``."""
    if recall + precision == 0:
        return 0.0
    return 2 * recall * precision / (recall + precision)


# --- proposal ---------------------------------------------------------------


@dataclass(frozen=True)
class ProposalArtifact:
    """What a proposal trial produced: the written plan text (``None`` on the
    multi-plan split short-circuit) and the split-proposal entry count."""

    plan_text: Optional[str]
    split_proposal_entry_count: int = 0


@dataclass(frozen=True)
class ProposalAnswerKey:
    """The seed's fenced expected-label block."""

    expected_step_count_range: tuple[int, int]
    expected_change_types: list[str]
    must_split: bool
    split_first_change_type: str = "refactor"
    split_second_change_type: str = "feature"
    split_second_depends_on_first: bool = True


@dataclass(frozen=True)
class ProposalScore:
    validity: float
    change_type_agreement: float
    step_count_ok: float
    split_ok: float
    purity: float
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _proposal_split_satisfied(
    plan: Optional[Plan], artifact: ProposalArtifact, answer: ProposalAnswerKey
) -> bool:
    """True when a must-split seed was answered with the production split shape.

    Either the multi-plan split short-circuit fired (>= 2 proposal entries) or
    the produced plan is exactly two type-pure steps wired
    ``first_change_type`` → ``second_change_type`` with the second depending on
    the first — the deterministic shape ``create._apply_step_split`` enforces.
    """
    if artifact.split_proposal_entry_count >= 2:
        return True
    if plan is None or len(plan.steps) != 2:
        return False
    first, second = plan.steps
    if first.change_type is None or second.change_type is None:
        return False
    if first.change_type.value != answer.split_first_change_type:
        return False
    if second.change_type.value != answer.split_second_change_type:
        return False
    if answer.split_second_depends_on_first and first.id not in second.depends_on:
        return False
    return True


def score_proposal(
    artifact: ProposalArtifact, answer: ProposalAnswerKey
) -> ProposalScore:
    """Score a proposal trial against its seed's expected-label block.

    Validity is a precondition: an unparseable produced plan zeroes every
    component (and ``value``). The exception is the multi-plan split
    short-circuit — it writes no plan but is itself the correct answer for a
    must-split seed, so it scores validity ``1.0`` and the split component.
    """
    # Multi-plan split short-circuit: no plan written, but the >= 2-entry split
    # is the correct must-split answer — score it as valid and pure.
    if artifact.plan_text is None and artifact.split_proposal_entry_count >= 2:
        split_ok = 1.0 if answer.must_split else 0.0
        value = _mean([1.0, 1.0, split_ok, 1.0])
        return ProposalScore(
            validity=1.0,
            change_type_agreement=1.0,
            step_count_ok=1.0,
            split_ok=split_ok,
            purity=1.0,
            value=value,
        )

    plan: Optional[Plan] = None
    if artifact.plan_text is not None:
        try:
            plan = parse_plan_text(artifact.plan_text)
        except (ParseError, ValidationError):
            plan = None

    if plan is None:
        return ProposalScore(
            validity=0.0,
            change_type_agreement=0.0,
            step_count_ok=0.0,
            split_ok=0.0,
            purity=0.0,
            value=0.0,
        )

    expected_types = set(answer.expected_change_types)
    classified = [s for s in plan.steps if s.change_type is not None]
    agreement = _mean(
        [
            1.0
            if s.change_type is not None and s.change_type.value in expected_types
            else 0.0
            for s in plan.steps
        ]
    )
    # Purity: every step is classified (carries exactly one change_type). The
    # schema permits only one type per step, so an unclassified step is the
    # only way a proposal leaves a step's purity in question.
    purity = len(classified) / len(plan.steps) if plan.steps else 0.0

    low, high = answer.expected_step_count_range
    step_count_ok = 1.0 if low <= len(plan.steps) <= high else 0.0

    if answer.must_split:
        split_ok = 1.0 if _proposal_split_satisfied(plan, artifact, answer) else 0.0
    else:
        split_ok = 1.0

    value = _mean([agreement, step_count_ok, split_ok, purity])
    return ProposalScore(
        validity=1.0,
        change_type_agreement=agreement,
        step_count_ok=step_count_ok,
        split_ok=split_ok,
        purity=purity,
        value=value,
    )


# --- detail -----------------------------------------------------------------


@dataclass(frozen=True)
class DetailArtifact:
    """The drafted detail body for one fixture-plan step."""

    detail_body: Optional[str]
    step_id: Optional[int] = None


@dataclass(frozen=True)
class DetailAnswerKey:
    """The fixture step the draft targets (footprint drives coherence)."""

    step: Step


@dataclass(frozen=True)
class DetailScore:
    required_h2: float
    files_coherence: float
    acceptance_ok: float
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detail_files_coherence_issue_count(
    body: str, step: Step
) -> int:
    """Run the production ``check_files_coherence`` against the drafted body.

    ``check_files_coherence`` reads detail bodies from disk off a ``Plan``, so
    we materialize a one-step plan (the target step with ``detail`` set) plus
    the body into a tempdir and invoke the real checker — reusing the
    production near-miss logic rather than forking it. Returns the
    ``FilesCoherenceIssue`` count.
    """
    detail_rel = "detail/step.md"
    one_step = step.model_copy(
        update={
            "detail": detail_rel,
            "depends_on": [],
            "depends_on_notes": {},
        }
    )
    plan = Plan(
        title="detail bench fixture",
        status=PlanStatus.PLANNING,
        priority=Priority.LOW,
        steps=[one_step],
    )
    with tempfile.TemporaryDirectory(prefix="benchdetail-") as tmp:
        root = Path(tmp)
        detail_path = root / detail_rel
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text(body, encoding="utf-8")
        return len(check_files_coherence(plan, root))


def score_detail(artifact: DetailArtifact, answer: DetailAnswerKey) -> DetailScore:
    """Score a drafted detail body: required H2s, files-coherence, acceptance.

    A missing body zeroes every component. The required-H2 token set is
    imported from ``review._REQUIRED_DETAIL_SECTION_NAMES`` so it tracks the
    production check rather than hardcoding the list.
    """
    body = artifact.detail_body
    if not body:
        return DetailScore(0.0, 0.0, 0.0, 0.0)

    sections = parse_detail_file_sections(body)
    present = sum(
        1 for token, _name in _REQUIRED_DETAIL_SECTION_NAMES if token in sections
    )
    required_h2 = present / len(_REQUIRED_DETAIL_SECTION_NAMES)

    issue_count = _detail_files_coherence_issue_count(body, answer.step)
    files_coherence = 1.0 / (1.0 + issue_count)

    acceptance_ok = 1.0 if parse_acceptance_bullets(body) else 0.0

    value = _mean([required_h2, files_coherence, acceptance_ok])
    return DetailScore(
        required_h2=required_h2,
        files_coherence=files_coherence,
        acceptance_ok=acceptance_ok,
        value=value,
    )


# --- reconcile --------------------------------------------------------------


@dataclass(frozen=True)
class ReconcileArtifact:
    """The findings a reconcile run reported, each as searchable text."""

    findings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReconcileAnswerKey:
    """The seeded-defect manifest for one scratch repo."""

    defects: list[dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class ReconcileScore:
    recall: float
    precision: float
    recalled_defects: int
    total_defects: int
    true_positive_findings: int
    total_findings: int
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_ident(text: str) -> str:
    """Lowercase and strip every non-alphanumeric char (fuzzy identifier key).

    Collapses casing and separators so ``validate_token`` / ``validateToken``
    / ``--validate-token`` all normalize to the same searchable run, letting a
    finding's wording differ from the manifest without zeroing the match.
    """
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _finding_matches_defect(finding_text: str, defect: dict[str, str]) -> bool:
    """Fuzzy file+symbol match between a finding and a seeded defect.

    The defect's file (by basename stem) and symbol must both appear in the
    finding's normalized text — basename so a different directory still
    matches, normalized identifier so casing/spelling differences don't zero
    the score.
    """
    text_norm = _normalize_ident(finding_text)
    file_base = defect.get("file", "").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    file_norm = _normalize_ident(file_base)
    symbol_norm = _normalize_ident(defect.get("symbol", ""))
    if not file_norm or not symbol_norm:
        return False
    return file_norm in text_norm and symbol_norm in text_norm


def score_reconcile(
    artifact: ReconcileArtifact, answer: ReconcileAnswerKey
) -> ReconcileScore:
    """Score reconcile findings as set-overlap against the seeded manifest.

    A defect is *recalled* when >= 1 finding matches it; a finding is a *true
    positive* when it matches >= 1 defect. ``value`` is the F1 of recall and
    precision. Matching is agnostic to which review check surfaced the finding
    (deterministic drift or LLM-backed criteria-fulfillment).
    """
    defects = answer.defects
    findings = artifact.findings
    total_defects = len(defects)
    total_findings = len(findings)

    recalled = sum(
        1
        for d in defects
        if any(_finding_matches_defect(f, d) for f in findings)
    )
    true_positive = sum(
        1
        for f in findings
        if any(_finding_matches_defect(f, d) for d in defects)
    )

    recall = recalled / total_defects if total_defects else 1.0
    # No findings ⇒ no false positives (vacuously precise); the missed defects
    # are penalized by recall instead.
    precision = true_positive / total_findings if total_findings else 1.0
    value = _f1(recall, precision)
    return ReconcileScore(
        recall=recall,
        precision=precision,
        recalled_defects=recalled,
        total_defects=total_defects,
        true_positive_findings=true_positive,
        total_findings=total_findings,
        value=value,
    )


# --- implementation ---------------------------------------------------------


@dataclass(frozen=True)
class ImplementationArtifact:
    """Numbers captured while the scratch workspace was live (step 2 runner)."""

    hidden_tests_passed: int = 0
    hidden_tests_total: int = 0
    test_command_exit: int = 1
    out_of_scope_file_count: int = 0


@dataclass(frozen=True)
class ImplementationAnswerKey:
    """No corpus side-data: scoring is over the captured numbers alone."""


@dataclass(frozen=True)
class ImplementationScore:
    hidden_test_rate: float
    scope_clean: float
    test_command_ok: float
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_implementation(
    artifact: ImplementationArtifact, answer: ImplementationAnswerKey
) -> ImplementationScore:
    """Score from the captured hidden-test, scope, and exit numbers.

    Pure over the artifact: no backend, no re-run. Hidden-test pass rate +
    out-of-scope cleanliness (inverse of the count) + ``test_command`` exit.
    """
    if artifact.hidden_tests_total > 0:
        hidden_test_rate = artifact.hidden_tests_passed / artifact.hidden_tests_total
    else:
        hidden_test_rate = 0.0
    scope_clean = 1.0 / (1.0 + artifact.out_of_scope_file_count)
    test_command_ok = 1.0 if artifact.test_command_exit == 0 else 0.0
    value = _mean([hidden_test_rate, scope_clean, test_command_ok])
    return ImplementationScore(
        hidden_test_rate=hidden_test_rate,
        scope_clean=scope_clean,
        test_command_ok=test_command_ok,
        value=value,
    )


# --- apply ------------------------------------------------------------------


@dataclass(frozen=True)
class ApplyArtifact:
    """The apply-finding outcome: verdict, scoped diff, out-of-scope count."""

    verdict: str
    diff_text: str
    out_of_scope_file_count: int = 0


@dataclass(frozen=True)
class ApplyAnswerKey:
    """The saved finding's known target edit."""

    expected_edit: str
    target_step_id: Optional[int] = None
    target_file: Optional[str] = None


@dataclass(frozen=True)
class ApplyScore:
    target_landed: float
    scope_clean: float
    value: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def score_apply(artifact: ApplyArtifact, answer: ApplyAnswerKey) -> ApplyScore:
    """Score an apply-finding trial: target edit landed + no unrelated hunks.

    Target landed requires ``verdict == "APPLIED"`` AND the ``expected_edit``
    marker present in the scoped diff. ``scope_clean`` requires a zero
    out-of-scope file count.
    """
    landed = (
        artifact.verdict == "APPLIED"
        and answer.expected_edit in artifact.diff_text
    )
    target_landed = 1.0 if landed else 0.0
    scope_clean = 1.0 if artifact.out_of_scope_file_count == 0 else 0.0
    value = _mean([target_landed, scope_clean])
    return ApplyScore(
        target_landed=target_landed,
        scope_clean=scope_clean,
        value=value,
    )


# ---------------------------------------------------------------------------
# Answer-key loaders (read the step-1 corpus from ``corpus_root``).
# ---------------------------------------------------------------------------


_EXPECTED_LABEL_RE = re.compile(r"```json\s*\n(.*?)\n```", re.DOTALL)


def _cell_slug(cell_id: str) -> str:
    """Last path component of a ``family/slug`` cell id."""
    return cell_id.split("/", 1)[-1]


def load_proposal_answer(
    corpus_root: Path, cell_id: str
) -> Optional[ProposalAnswerKey]:
    """Parse a proposal seed's fenced expected-label block."""
    seed_path = corpus_root / "proposal" / f"{_cell_slug(cell_id)}.md"
    if not seed_path.is_file():
        return None
    text = seed_path.read_text(encoding="utf-8")
    for match in _EXPECTED_LABEL_RE.finditer(text):
        try:
            obj = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or "expected_change_types" not in obj:
            continue
        rng = obj.get("expected_step_count_range", [1, 1])
        contract = obj.get("split_contract") or {}
        return ProposalAnswerKey(
            expected_step_count_range=(int(rng[0]), int(rng[1])),
            expected_change_types=list(obj.get("expected_change_types", [])),
            must_split=bool(obj.get("must_split", False)),
            split_first_change_type=contract.get(
                "first_step_change_type", "refactor"
            ),
            split_second_change_type=contract.get(
                "second_step_change_type", "feature"
            ),
            split_second_depends_on_first=bool(
                contract.get("second_depends_on_first", True)
            ),
        )
    return None


def load_detail_answer(
    corpus_root: Path, cell_id: str
) -> Optional[DetailAnswerKey]:
    """Find the fixture-plan step the ``detail/step-N`` cell targets."""
    fixture = corpus_root / "detail" / "fixture-plan.md"
    if not fixture.is_file():
        return None
    try:
        step_id = int(_cell_slug(cell_id).rsplit("-", 1)[-1])
    except ValueError:
        return None
    plan = parse_plan(fixture)
    step = next((s for s in plan.steps if s.id == step_id), None)
    return DetailAnswerKey(step=step) if step is not None else None


def load_reconcile_answer(
    corpus_root: Path, cell_id: str
) -> Optional[ReconcileAnswerKey]:
    """Pull the seeded-defect manifest for the ``reconcile/<id>`` scratch repo."""
    fixture = corpus_root / "reconcile" / "seeded-defects.json"
    if not fixture.is_file():
        return None
    data = json.loads(fixture.read_text(encoding="utf-8"))
    repo_id = _cell_slug(cell_id)
    entry = next((r for r in data.get("repos", []) if r.get("id") == repo_id), None)
    if entry is None:
        return None
    return ReconcileAnswerKey(defects=list(entry.get("defects", [])))


def load_implementation_answer(
    corpus_root: Path, cell_id: str
) -> ImplementationAnswerKey:
    """The implementation family scores over captured numbers — no side-data."""
    return ImplementationAnswerKey()


def load_apply_answer(
    corpus_root: Path, cell_id: str
) -> Optional[ApplyAnswerKey]:
    """Read the saved finding's known target edit from ``findings.json``."""
    fixture = corpus_root / "apply" / "findings.json"
    if not fixture.is_file():
        return None
    data = json.loads(fixture.read_text(encoding="utf-8"))
    finding_id = _cell_slug(cell_id)
    entry = next(
        (f for f in data.get("findings", []) if f.get("id") == finding_id), None
    )
    if entry is None:
        return None
    return ApplyAnswerKey(
        expected_edit=entry.get("expected_edit", ""),
        target_step_id=entry.get("target_step_id"),
        target_file=entry.get("target_file"),
    )


# ---------------------------------------------------------------------------
# Dispatcher + records-scoring pass (the seam step 4's report aggregation reads).
# ---------------------------------------------------------------------------


def score_trial(
    record: dict[str, Any], *, corpus_root: Path
) -> Optional[Any]:
    """Build the family artifact from a record and score it, or ``None``.

    Returns ``None`` for an unscorable record — a timed-out / crashed trial
    that captured no artifact, or a cell whose answer key is missing from the
    corpus.
    """
    if record.get("failure_kind") == "timeout":
        return None
    family = record.get("family")
    cell_id = record.get("cell_id", "")
    data = record.get("artifact")
    if data is None:
        return None

    if family == "proposal":
        answer = load_proposal_answer(corpus_root, cell_id)
        if answer is None:
            return None
        return score_proposal(
            ProposalArtifact(
                plan_text=data.get("plan_text"),
                split_proposal_entry_count=data.get(
                    "split_proposal_entry_count", 0
                ),
            ),
            answer,
        )

    if family == "detail":
        answer = load_detail_answer(corpus_root, cell_id)
        if answer is None:
            return None
        return score_detail(
            DetailArtifact(
                detail_body=data.get("detail_body"),
                step_id=data.get("step_id"),
            ),
            answer,
        )

    if family == "reconcile":
        answer = load_reconcile_answer(corpus_root, cell_id)
        if answer is None:
            return None
        return score_reconcile(
            ReconcileArtifact(findings=list(data.get("findings", []))),
            answer,
        )

    if family == "implementation":
        return score_implementation(
            ImplementationArtifact(
                hidden_tests_passed=data.get("hidden_tests_passed", 0),
                hidden_tests_total=data.get("hidden_tests_total", 0),
                test_command_exit=data.get("test_command_exit", 1),
                out_of_scope_file_count=data.get("out_of_scope_file_count", 0),
            ),
            load_implementation_answer(corpus_root, cell_id),
        )

    if family == "apply":
        answer = load_apply_answer(corpus_root, cell_id)
        if answer is None:
            return None
        return score_apply(
            ApplyArtifact(
                verdict=data.get("verdict", "UNKNOWN"),
                diff_text=data.get("diff_text", ""),
                out_of_scope_file_count=data.get("out_of_scope_file_count", 0),
            ),
            answer,
        )

    return None


def score_records(run_dir: Path, *, corpus_root: Path) -> None:
    """Attach a ``score`` object to every scorable record in ``records.jsonl``.

    Reads the run's records, scores each via :func:`score_trial`, writes the
    per-family ``score`` dict (or ``None`` for an unscorable record) back into
    the line, and rewrites the file. Idempotent: re-running re-derives the same
    score from the same captured artifact, so a scoring disagreement is
    debuggable offline without re-spawning a backend.
    """
    rec_path = run_dir / RECORDS_FILENAME
    records = _read_records(rec_path)
    for record in records:
        score = score_trial(record, corpus_root=corpus_root)
        record["score"] = score.to_dict() if score is not None else None
    rec_path.parent.mkdir(parents=True, exist_ok=True)
    with rec_path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Step 4 — scored aggregation, per-family recommendation, and the regenerable
# ``docs/evidence/backend-recommendations.md`` artifact.
#
# ``build_quality_report`` rolls the step-3-scored records up into a
# per-(family, backend) table; ``recommend_per_family`` picks a backend per
# family with a sample-count caveat; the renderers emit the comparison table
# (markdown / JSON) and the self-dating recommendations doc. Spread is reported
# as median + (min, max), never ``statistics.quantiles`` percentiles — at three
# trials a p95 reads as authoritative but means nothing (the
# ``runs.py:_SMALL_BUCKET_THRESHOLD`` lesson), so confidence is bound to trial
# and corpus-cell counts instead.
# ---------------------------------------------------------------------------

RECOMMENDATIONS_REL = ("docs", "BACKEND_RECOMMENDATIONS.md")

# Two backends whose median quality differs by less than this read as a tie:
# the comparison resolves on wall-clock then cost, and the caveat says so. Small
# enough that a real quality gap still picks a winner.
_QUALITY_TIE_DELTA = 0.05

_DO_NOT_EDIT_MARKER = (
    "<!-- generated by `plan-tool bench report --write-recommendations`; "
    "do not edit directly -->"
)


@dataclass(frozen=True)
class QualityCell:
    """Scored rollup for one ``(family, backend)`` — pooled across that family's
    corpus cells and trials.

    ``quality_*`` are over the step-3 ``score.value`` of every *scorable* trial
    (a timed-out / unscorable trial carries ``score=None`` and is excluded from
    the median but still counted in ``trial_count`` / ``failure_count``). Token
    and cost totals are None-skipping sums — a batch family that reports no
    tokens yields ``None`` (rendered ``n/a``), never ``0``.
    """

    family: str
    backend: str
    trial_count: int
    scored_count: int
    quality_median: Optional[float]
    quality_min: Optional[float]
    quality_max: Optional[float]
    wall_clock_median_ms: Optional[float]
    tokens_input_total: Optional[int]
    tokens_output_total: Optional[int]
    cost_usd_total: Optional[float]
    failure_count: int
    failure_rate: float
    retry_total: int
    retry_rate: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QualityReport:
    """The whole scored comparison for one run dir."""

    stamp: str
    run_meta: Optional[RunMeta]
    cells: tuple[QualityCell, ...]
    current_corpus_hash: str
    is_stale: bool
    families: tuple[str, ...]
    backends: tuple[str, ...]
    # Distinct corpus-cell count per family (the M the confidence caveat names).
    family_cell_counts: dict[str, int]
    # Trials per cell per backend (the N the caveat names) — from ``RunMeta``
    # when recorded, else inferred from the highest trial index seen.
    trials_per_cell: Optional[int]


def _none_skip_sum(records: list[dict[str, Any]], key: str) -> Optional[float]:
    """Sum a numeric field across records, ``None`` when no record carried one.

    Mirrors ``runs.py:_summarize_group``'s token/cost policy: a family that
    never reports a value stays ``None`` (rendered ``n/a``), distinct from a
    real ``0``.
    """
    values = [r[key] for r in records if isinstance(r.get(key), (int, float))]
    if not values:
        return None
    total = sum(values)
    return int(total) if all(isinstance(v, int) for v in values) else total


def _scorable_values(records: list[dict[str, Any]]) -> list[float]:
    """The ``score.value`` of every scorable trial in a group."""
    values: list[float] = []
    for r in records:
        score = r.get("score")
        if isinstance(score, dict) and isinstance(score.get("value"), (int, float)):
            values.append(float(score["value"]))
    return values


def _build_quality_cell(
    family: str, backend: str, records: list[dict[str, Any]]
) -> QualityCell:
    attempts = len(records)
    failure_count = sum(1 for r in records if r.get("failure_kind"))
    retry_total = sum(int(r.get("retries") or 0) for r in records)
    values = _scorable_values(records)
    completed_walls = [
        float(r["wall_clock_ms"])
        for r in records
        if not r.get("failure_kind") and isinstance(r.get("wall_clock_ms"), (int, float))
    ]
    return QualityCell(
        family=family,
        backend=backend,
        trial_count=attempts,
        scored_count=len(values),
        quality_median=statistics.median(values) if values else None,
        quality_min=min(values) if values else None,
        quality_max=max(values) if values else None,
        wall_clock_median_ms=(
            statistics.median(completed_walls) if completed_walls else None
        ),
        tokens_input_total=_none_skip_sum(records, "tokens_input"),
        tokens_output_total=_none_skip_sum(records, "tokens_output"),
        cost_usd_total=_none_skip_sum(records, "cost_usd"),
        failure_count=failure_count,
        failure_rate=failure_count / attempts if attempts else 0.0,
        retry_total=retry_total,
        retry_rate=retry_total / attempts if attempts else 0.0,
    )


def _infer_trials_per_cell(records: list[dict[str, Any]]) -> Optional[int]:
    """Highest trial index seen across records (legacy run with no run-meta)."""
    trials = [int(r["trial"]) for r in records if isinstance(r.get("trial"), int)]
    return max(trials) if trials else None


def build_quality_report(
    run_dir: Path, *, corpus_root: Path, ensure_scored: bool = True
) -> QualityReport:
    """Aggregate a run dir's scored records into a per-(family, backend) report.

    With ``ensure_scored`` (default), any record lacking a ``score`` key is
    scored on the fly via :func:`score_records` first, so ``bench report`` works
    on a freshly-captured (step-2-only) run dir without a manual scoring pass.
    Records are grouped by ``(family, backend)`` (pooling a family's corpus
    cells), each rolled into a :class:`QualityCell`. The current corpus hash is
    recomputed from ``corpus_root`` and compared against the run's recorded hash
    to flag staleness (unknown — never stale — for a legacy run dir).
    """
    rec_path = run_dir / RECORDS_FILENAME
    records = _read_records(rec_path)
    if ensure_scored and any("score" not in r for r in records):
        score_records(run_dir, corpus_root=corpus_root)
        records = _read_records(rec_path)

    run_meta = load_run_meta(run_dir)
    families = tuple(sorted({r.get("family", "?") for r in records}))
    backends = tuple(sorted({r.get("backend", "?") for r in records}))

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in records:
        groups.setdefault((r.get("family", "?"), r.get("backend", "?")), []).append(r)
    cells = tuple(
        _build_quality_cell(family, backend, group)
        for (family, backend), group in sorted(groups.items())
    )

    family_cell_counts = {
        family: len(
            {r.get("cell_id") for r in records if r.get("family") == family}
        )
        for family in families
    }
    current = corpus_hash(corpus_root)
    is_stale = run_meta is not None and run_meta.corpus_hash != current
    trials_per_cell = (
        run_meta.trials if run_meta is not None else _infer_trials_per_cell(records)
    )
    return QualityReport(
        stamp=run_meta.stamp if run_meta is not None else run_dir.name,
        run_meta=run_meta,
        cells=cells,
        current_corpus_hash=current,
        is_stale=is_stale,
        families=families,
        backends=backends,
        family_cell_counts=family_cell_counts,
        trials_per_cell=trials_per_cell,
    )


# ---------------------------------------------------------------------------
# Recommendation selection.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FamilyRecommendation:
    """The recommended backend for one family, with evidence and a caveat."""

    family: str
    recommended_backend: Optional[str]
    evidence: Optional[QualityCell]
    runner_up: Optional[QualityCell]
    confidence_caveat: str


def _confidence_caveat(
    report: QualityReport, family: str, *, no_clear_winner: bool, scorable: bool
) -> str:
    """Sample-count prose, never a fabricated p-value (the small-N honesty rule).

    Names the per-family trial count and corpus-cell count the report actually
    has; prepends a no-clear-winner note when the top two medians tie.
    """
    if not scorable:
        return (
            f"No scorable trials for {family}; no backend can be recommended "
            "from this run."
        )
    trials = report.trials_per_cell
    trials_text = "unknown" if trials is None else str(trials)
    cells = report.family_cell_counts.get(family, 0)
    base = (
        f"Directional only: {trials_text} trials/backend across {cells} "
        f"{family} corpus cell(s); not statistically significant."
    )
    return f"No clear winner — {base}" if no_clear_winner else base


def _cell_sort_key(cell: QualityCell) -> tuple[float, float]:
    """Tie-break key: lower wall-clock then lower cost (``None`` sorts last)."""
    wall = cell.wall_clock_median_ms
    cost = cell.cost_usd_total
    return (
        wall if wall is not None else float("inf"),
        cost if cost is not None else float("inf"),
    )


def recommend_per_family(report: QualityReport) -> tuple[FamilyRecommendation, ...]:
    """Pick one backend per family: highest median, tie-break wall-clock then cost.

    Backends whose median is within :data:`_QUALITY_TIE_DELTA` of the best read
    as tied — the winner among them is the one with the lower wall-clock median
    (then lower cost), and the caveat says "No clear winner". A family with no
    scorable trial recommends ``None`` with an explanatory caveat.
    """
    recommendations: list[FamilyRecommendation] = []
    for family in report.families:
        scorable = [
            c
            for c in report.cells
            if c.family == family and c.quality_median is not None
        ]
        if not scorable:
            recommendations.append(
                FamilyRecommendation(
                    family=family,
                    recommended_backend=None,
                    evidence=None,
                    runner_up=None,
                    confidence_caveat=_confidence_caveat(
                        report, family, no_clear_winner=False, scorable=False
                    ),
                )
            )
            continue

        ranked = sorted(scorable, key=lambda c: c.quality_median, reverse=True)
        best_median = ranked[0].quality_median
        contenders = [
            c for c in ranked if best_median - c.quality_median <= _QUALITY_TIE_DELTA
        ]
        winner = sorted(contenders, key=_cell_sort_key)[0]
        runner_up = next((c for c in ranked if c is not winner), None)
        no_clear_winner = (
            runner_up is not None
            and abs(winner.quality_median - runner_up.quality_median)
            <= _QUALITY_TIE_DELTA
        )
        recommendations.append(
            FamilyRecommendation(
                family=family,
                recommended_backend=winner.backend,
                evidence=winner,
                runner_up=runner_up,
                confidence_caveat=_confidence_caveat(
                    report, family, no_clear_winner=no_clear_winner, scorable=True
                ),
            )
        )
    return tuple(recommendations)


# ---------------------------------------------------------------------------
# Renderers — pure ``str`` builders, split from any disk write (the
# ``completeness_report.build_report_md`` vs ``write_completeness_report`` shape).
# ---------------------------------------------------------------------------


def _fmt_num(value: Optional[float], *, decimals: int = 3) -> str:
    """Round a float for display; ``-`` for ``None``."""
    return "-" if value is None else f"{value:.{decimals}f}"


def _fmt_int(value: Optional[float]) -> str:
    """Integer display; ``n/a`` for ``None`` (never ``0``)."""
    return "n/a" if value is None else str(int(value))


def _fmt_tokens(cell: QualityCell) -> str:
    """``in/out`` token totals, ``n/a`` when neither was reported."""
    if cell.tokens_input_total is None and cell.tokens_output_total is None:
        return "n/a"
    return f"{_fmt_int(cell.tokens_input_total)}/{_fmt_int(cell.tokens_output_total)}"


def _fmt_cost(value: Optional[float]) -> str:
    return "n/a" if value is None else f"${value:.4f}"


def _fmt_spread(cell: QualityCell) -> str:
    """``min–max`` (an en dash), ``-`` when no scorable trial exists."""
    if cell.quality_min is None or cell.quality_max is None:
        return "-"
    return f"{cell.quality_min:.3f}–{cell.quality_max:.3f}"


def _fmt_pct(rate: float) -> str:
    return f"{rate * 100:.0f}%"


def _staleness_header_lines(report: QualityReport) -> list[str]:
    """The shared dating block: stamp, backend versions, measured + current hash.

    Both the comparison table and the recommendations doc lead with this so a
    reader can tell at a glance whether the numbers are current.
    """
    meta = report.run_meta
    lines = [f"- Run stamp: `{report.stamp}`"]
    if meta is None:
        lines.append("- Backend versions: not recorded for this run.")
    else:
        lines.append("- Backends measured:")
        for backend in meta.backends:
            lines.append(f"  - `{backend.name}` version `{backend.version or 'unknown'}`")
    measured = meta.corpus_hash if meta is not None else "unknown"
    lines.append(f"- Corpus hash measured: `{measured}`")
    lines.append(f"- Corpus hash current: `{report.current_corpus_hash}`")
    if report.is_stale:
        lines.append(
            f"- ⚠️ STALE: the corpus changed since these numbers were measured "
            f"(measured `{measured}`, current `{report.current_corpus_hash}`); "
            f"re-run `bench run` before trusting them."
        )
    return lines


def render_report_markdown(report: QualityReport) -> str:
    """Per-family scored comparison table as markdown, led by the staleness header."""
    lines = [f"# Backend quality bench report — `{report.stamp}`", ""]
    lines.extend(_staleness_header_lines(report))
    lines.append("")
    if not report.cells:
        lines.append("_No records to report._")
        return "\n".join(lines) + "\n"
    for family in report.families:
        lines.append(f"## {family}")
        lines.append("")
        lines.append(
            "| backend | quality (median) | spread (min–max) | wall-clock med (ms) "
            "| tokens in/out | cost | fail% | retry% |"
        )
        lines.append(
            "| --- | --- | --- | --- | --- | --- | --- | --- |"
        )
        for cell in report.cells:
            if cell.family != family:
                continue
            lines.append(
                f"| {cell.backend} | {_fmt_num(cell.quality_median)} | "
                f"{_fmt_spread(cell)} | {_fmt_num(cell.wall_clock_median_ms, decimals=0)} | "
                f"{_fmt_tokens(cell)} | {_fmt_cost(cell.cost_usd_total)} | "
                f"{_fmt_pct(cell.failure_rate)} | {_fmt_pct(cell.retry_rate)} |"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def report_to_dict(report: QualityReport) -> dict[str, Any]:
    """JSON twin of :func:`render_report_markdown` — the ``--format json`` payload."""
    return {
        "stamp": report.stamp,
        "run_meta": report.run_meta.to_dict() if report.run_meta is not None else None,
        "current_corpus_hash": report.current_corpus_hash,
        "is_stale": report.is_stale,
        "families": list(report.families),
        "backends": list(report.backends),
        "family_cell_counts": dict(report.family_cell_counts),
        "trials_per_cell": report.trials_per_cell,
        "cells": [c.to_dict() for c in report.cells],
    }


def _evidence_row(cell: QualityCell) -> list[str]:
    """A one-row markdown evidence table for a recommended/runner-up cell."""
    return [
        "| backend | quality (median) | spread (min–max) | wall-clock med (ms) "
        "| tokens in/out | cost | fail% |",
        "| --- | --- | --- | --- | --- | --- | --- |",
        f"| {cell.backend} | {_fmt_num(cell.quality_median)} | {_fmt_spread(cell)} | "
        f"{_fmt_num(cell.wall_clock_median_ms, decimals=0)} | {_fmt_tokens(cell)} | "
        f"{_fmt_cost(cell.cost_usd_total)} | {_fmt_pct(cell.failure_rate)} |",
    ]


def render_recommendations_doc(
    report: QualityReport, recommendations: tuple[FamilyRecommendation, ...]
) -> str:
    """Render ``docs/evidence/backend-recommendations.md`` — a fully regenerable artifact.

    Leads with the do-not-edit marker and the staleness header (stamp, backend
    versions, measured + current corpus hash, stale marker), then one section
    per family: the recommended backend, its evidence row, the runner-up for
    contrast, and the sample-count confidence caveat.
    """
    lines = [
        _DO_NOT_EDIT_MARKER,
        "",
        "# Backend recommendations",
        "",
        "Per task family, the backend this benchmark run recommends. Regenerate "
        "with `plan-tool bench report --stamp <s> --write-recommendations`; never "
        "edit directly.",
        "",
        "## Provenance",
        "",
    ]
    lines.extend(_staleness_header_lines(report))
    lines.append("")
    for rec in recommendations:
        lines.append(f"## {rec.family}")
        lines.append("")
        if rec.recommended_backend is None:
            lines.append("**Recommended backend:** none")
        else:
            lines.append(f"**Recommended backend:** `{rec.recommended_backend}`")
        lines.append("")
        if rec.evidence is not None:
            lines.append("Evidence:")
            lines.append("")
            lines.extend(_evidence_row(rec.evidence))
            lines.append("")
        if rec.runner_up is not None:
            lines.append(f"Runner-up for contrast: `{rec.runner_up.backend}`")
            lines.append("")
            lines.extend(_evidence_row(rec.runner_up))
            lines.append("")
        lines.append(f"_{rec.confidence_caveat}_")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_recommendations_doc(repo_root: Path, text: str) -> Path:
    """Write the rendered doc to ``<repo>/docs/evidence/backend-recommendations.md``.

    Overwrites in full — the doc is a regenerated artifact, not hand-maintained.
    """
    path = repo_root.joinpath(*RECOMMENDATIONS_REL)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
