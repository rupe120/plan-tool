"""Engine unit tests for ``plan_tool.bench`` — fixture-driven, no real binary.

Every test injects fake invokers (via :class:`plan_tool.bench.BenchInvokers`)
so the matrix drives the real production entrypoints without ever spawning a
backend; the repo-root subprocess guard (``tests/conftest.py``) blocks one if a
seam is missed. The matrix engine always records a trial — even when a family's
entrypoint fails internally — so the count/resume/selection invariants hold
regardless of any one family's internals.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

from plan_tool.backend import CLAUDE_BACKEND, get_active_backend, set_active_backend
from plan_tool.create import CreateError
from plan_tool import bench
from plan_tool.bench import (
    ApplyArtifact,
    BackendVersion,
    BenchInvokers,
    BenchTrialRecord,
    DetailArtifact,
    ImplementationArtifact,
    ProposalArtifact,
    ReconcileAnswerKey,
    ReconcileArtifact,
    RunMeta,
    aggregate_run,
    bench_run_dir,
    build_quality_report,
    corpus_hash,
    load_apply_answer,
    load_detail_answer,
    load_proposal_answer,
    load_reconcile_answer,
    load_run_meta,
    recommend_per_family,
    records_path,
    render_recommendations_doc,
    render_report_markdown,
    report_to_dict,
    run_bench_matrix,
    score_apply,
    score_detail,
    score_implementation,
    score_proposal,
    score_reconcile,
    score_records,
    score_trial,
    write_run_meta,
)
from plan_tool.bench import ImplementationAnswerKey

REPO_ROOT = Path(__file__).resolve().parents[1]
REAL_CORPUS = REPO_ROOT / "benchmarks" / "corpus"


@pytest.fixture(autouse=True)
def _restore_active_backend():
    """Reset the process-global active backend after each test.

    The engine mutates the active backend per trial; without this the
    selection from one test would leak into the next.
    """
    yield
    set_active_backend(CLAUDE_BACKEND)


class RecordingStrInvoker:
    """A ``ClaudeInvoker`` / ``DetailInvoker`` (str -> str) that records calls."""

    def __init__(self, ret: str = "") -> None:
        self.ret = ret
        self.calls: list[str] = []
        self.backends: list[str] = []

    def __call__(self, prompt: str) -> str:
        self.calls.append(prompt)
        self.backends.append(get_active_backend().name)
        return self.ret


class RecordingTupleInvoker:
    """An ``Invoker`` (str -> (rc, stdout)) that records calls + active backend."""

    def __init__(self, rc: int = 0, out: str = "") -> None:
        self.rc = rc
        self.out = out
        self.calls: list[str] = []
        self.backends: list[str] = []

    def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
        self.calls.append(prompt)
        self.backends.append(get_active_backend().name)
        return self.rc, self.out


class SleepingTupleInvoker:
    """An ``Invoker`` that sleeps past the per-cell timeout."""

    def __init__(self, seconds: float = 1.0) -> None:
        self.seconds = seconds

    def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
        time.sleep(self.seconds)
        return 0, ""


def _write_stub_proposal_corpus(corpus_root: Path, seeds: int) -> Path:
    """Write ``seeds`` minimal proposal seeds and return the corpus root."""
    proposal_dir = corpus_root / "proposal"
    proposal_dir.mkdir(parents=True, exist_ok=True)
    for i in range(seeds):
        (proposal_dir / f"seed-stub{i}.md").write_text(
            f"# Stub seed {i}\n\n## Request\nAdd a small feature number {i}.\n",
            encoding="utf-8",
        )
    return corpus_root


def _read_records(repo_root: Path, stamp: str) -> list[dict]:
    path = records_path(repo_root, stamp)
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _stub_cell_trials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep matrix bookkeeping tests independent of production trial work."""

    def fake_trial(family, cell, backend_name, trial, *, stamp, **_kwargs):
        return BenchTrialRecord(
            family=family.name,
            cell_id=cell.cell_id,
            backend=backend_name,
            trial=trial,
            stamp=stamp,
            wall_clock_ms=0,
            tokens_input=None,
            tokens_output=None,
            cache_creation_tokens=None,
            cache_read_tokens=None,
            cost_usd=None,
            failure_kind=None,
            retries=0,
            exit_or_verdict=0,
            raw_output="",
        )

    monkeypatch.setattr(bench, "_run_cell_trial", fake_trial)


def test_matrix_enumerates_cells_x_backends_x_trials(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=3)
    repo_root = tmp_path / "repo"
    _stub_cell_trials(monkeypatch)
    summary = run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude", "codex"],
        families=["proposal"],
        trials=2,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    # 3 cells × 2 backends × 2 trials = 12.
    assert summary.records_written == 12
    assert len(_read_records(repo_root, "s1")) == 12


def test_resume_skips_completed_cells(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=2)
    repo_root = tmp_path / "repo"
    common = dict(
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    first = run_bench_matrix(repo_root, **common)
    assert first.records_written == 2
    second = run_bench_matrix(repo_root, **common)
    assert second.records_written == 0
    assert second.skipped == 2
    assert len(_read_records(repo_root, "s1")) == 2


def test_per_cell_timeout_records_failure_and_continues(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    summary = run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["apply"],
        trials=1,
        timeout_s=0.2,
        invokers=BenchInvokers(apply_invoker=SleepingTupleInvoker(seconds=1.0)),
    )
    records = _read_records(repo_root, "s1")
    # Both apply cells still produced a record (the matrix did not abort).
    assert summary.records_written == len(records) == 2
    assert any(r["failure_kind"] == "timeout" for r in records)


def test_records_none_safe_for_missing_stats(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    (record,) = _read_records(repo_root, "s1")
    # A batch family produces no per-call token stats — every field is null.
    assert record["cost_usd"] is None
    assert record["cache_creation_tokens"] is None
    assert record["cache_read_tokens"] is None
    assert record["tokens_input"] is None
    assert record["tokens_output"] is None


def test_failure_classification_uses_active_backend(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    # apply_finding preserves the invoker's stdout on a non-zero exit, so the
    # rate-limit copy reaches classify() against the active backend.
    rate_limited = RecordingTupleInvoker(rc=1, out="Error: rate limit exceeded; try again")
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["apply"],
        trials=1,
        invokers=BenchInvokers(apply_invoker=rate_limited),
    )
    records = _read_records(repo_root, "s1")
    assert records
    assert all(r["failure_kind"] == "rate_limit" for r in records)


def test_scratch_is_isolated_and_git_initialized(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=2)
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
        retain_scratch=True,
    )
    scratch_root = bench_run_dir(repo_root, "s1") / "scratch"
    cell_dirs = sorted(p for p in scratch_root.iterdir() if p.is_dir())
    assert len(cell_dirs) == 2
    for d in cell_dirs:
        assert (d / ".git").is_dir()


def test_proposal_family_routes_through_create_proposal_path(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    repo_root = tmp_path / "repo"
    fake = RecordingStrInvoker()
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=fake),
    )
    # The injected ClaudeInvoker was observed — the trial drove create_plan's
    # proposal stage, not a bespoke prompt.
    assert fake.calls, "create_plan never called the injected proposal invoker"


def test_proposal_trial_allows_placeholder_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_run_proposal`` passes ``allow_placeholder_body=True`` to create_plan.

    Without the bypass, ``synthesize_body=False`` + no iteration means
    Risks/Deferred always render as ``_(TODO)_`` and create_plan's
    fail-loud gate kills every single-plan trial with ``CreateError``
    regardless of backend quality — found live on the first real
    ``bench run`` (all claude proposal/seed-feature trials recorded
    ``unknown_nonzero`` with the gate's message as raw_output).
    """
    captured_kwargs: list[dict] = []

    def fake_create_plan(slug, **kwargs):
        captured_kwargs.append(kwargs)
        raise CreateError("stop after capture")

    monkeypatch.setattr(bench, "create_plan", fake_create_plan)
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    run_bench_matrix(
        tmp_path / "repo",
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    assert captured_kwargs, "trial never reached create_plan"
    assert captured_kwargs[0].get("allow_placeholder_body") is True


def test_proposal_trial_answers_risk_classification_without_a_second_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The proposal trial isolates token/latency to one prompt round-trip.

    ``create_plan`` always classifies a non-empty seed's risk profile before
    publication and its public signature is frozen, so the proposal trial
    cannot ask it to skip that call. The wrapped ``claude_invoker`` must
    answer a risk-classification prompt locally instead of forwarding it to
    the injected invoker — forwarding it would spend a second real backend
    call inside a trial whose whole point is measuring exactly one.
    """
    from plan_tool.create import _render_risk_profile_prompt

    captured_kwargs: list[dict] = []

    def fake_create_plan(slug, **kwargs):
        captured_kwargs.append(kwargs)
        raise CreateError("stop after capture")

    monkeypatch.setattr(bench, "create_plan", fake_create_plan)
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    recorder = RecordingStrInvoker(ret="proposal answer")
    run_bench_matrix(
        tmp_path / "repo",
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=recorder),
    )
    assert captured_kwargs, "trial never reached create_plan"
    wrapped_invoker = captured_kwargs[0]["claude_invoker"]

    risk_prompt = _render_risk_profile_prompt("Remove the unused component.")
    assert wrapped_invoker(risk_prompt) == ""
    assert not recorder.calls, "risk-classification prompt reached the injected invoker"

    assert wrapped_invoker("Propose an initial plan step-list.") == "proposal answer"
    assert recorder.calls == ["Propose an initial plan step-list."]


def test_codex_trial_activates_codex_backend(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    fake = RecordingTupleInvoker(rc=0, out="")
    set_active_backend(CLAUDE_BACKEND)
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["codex"],
        families=["apply"],
        trials=1,
        invokers=BenchInvokers(apply_invoker=fake),
    )
    # The entrypoint ran while codex was the active backend...
    assert "codex" in fake.backends
    # ...and the prior backend was restored after the trial.
    assert get_active_backend() is CLAUDE_BACKEND


def test_selection_flags_narrow_matrix(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=2)
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    records = _read_records(repo_root, "s1")
    assert {r["backend"] for r in records} == {"claude"}
    assert {r["family"] for r in records} == {"proposal"}
    assert len(records) == 2


def test_records_written_under_bench_runs_dir(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="2026-05-14T12-34-56-9f3a1c",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    expected = (
        repo_root
        / ".plan-tool"
        / "bench"
        / "runs"
        / "2026-05-14T12-34-56-9f3a1c"
        / "records.jsonl"
    )
    assert expected.is_file()


def test_full_corpus_enumerates_eleven_cells(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The step-1 corpus yields 11 cells = 11 records at 1 backend × 1 trial."""
    repo_root = tmp_path / "repo"
    _stub_cell_trials(monkeypatch)
    invokers = BenchInvokers(
        proposal_invoker=RecordingStrInvoker(),
        detail_invoker=RecordingStrInvoker(),
        reconcile_invoker=RecordingTupleInvoker(),
        implementation_invoker=RecordingTupleInvoker(),
        apply_invoker=RecordingTupleInvoker(),
    )
    summary = run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        trials=1,
        invokers=invokers,
    )
    records = _read_records(repo_root, "s1")
    assert summary.cells == 11
    assert len(records) == 11
    assert {r["family"] for r in records} == {
        "proposal",
        "detail",
        "reconcile",
        "implementation",
        "apply",
    }


def test_implementation_seed_materializes_parseable_solution(
    tmp_path: Path,
) -> None:
    """The materialized seed ``solution.py`` compiles for every cell.

    Found live: the corpus embeds the seed inside the fixture module's
    own docstring, so its docstring quotes were written escaped
    (``\\\"\\\"\\\"``) and materialized verbatim — a syntax error from
    birth. Trials then measured "did the backend notice and fix a
    pre-broken file" instead of the step spec, and the import gate
    failed any trial that edited around it.
    """
    from plan_tool.bench import BENCH_FAMILIES

    fam = BENCH_FAMILIES["implementation"]
    cells = fam.enumerate_cells(REAL_CORPUS / fam.corpus_subdir)
    assert cells, "no implementation cells enumerated"
    for cell in cells:
        scratch = tmp_path / cell.cell_id.replace("/", "__")
        scratch.mkdir(parents=True)
        fam.materialize(cell, scratch)
        source = (scratch / "solution.py").read_text(encoding="utf-8")
        compile(source, "solution.py", "exec")  # raises on a broken seed


def test_implementation_trial_runs_in_scratch_without_answer_key(
    tmp_path: Path,
) -> None:
    """Backend spawns are scoped to the scratch dir and cannot see
    ``hidden_tests.py``; the answer key lands only for the capture-time run.

    Pins two live-found defects from the first real ``bench run``:
    (a) spawned backends inherited the process cwd (no ``cwd=`` at the
    Popen sites), so trials ran inside the repo that invoked ``bench
    run`` — implementation trials wrote solution.py into the plan-tool
    repo root while the scratch stayed untouched. Now the decorated
    entrypoints scope ``backend.spawn_cwd`` to their ``repo_root``, so
    the active spawn cwd during the invoker call must be this trial's
    scratch. (b) ``_materialize_implementation`` wrote the answer key
    into the scratch BEFORE the backend ran, violating the corpus
    contract ("the backend never sees the ``test_*`` functions").
    """
    from plan_tool.backend import get_active_spawn_cwd

    seen: dict[str, object] = {}

    class SpyInvoker:
        def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
            cwd = get_active_spawn_cwd()
            seen["spawn_cwd"] = cwd
            seen["hidden_visible"] = (
                (cwd / "hidden_tests.py").exists() if cwd else None
            )
            return 0, ""

    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["implementation"],
        trials=1,
        invokers=BenchInvokers(implementation_invoker=SpyInvoker()),
    )

    assert "spawn_cwd" in seen, "trial never reached the backend invoker"
    # (a) spawns are scoped to the per-trial scratch, not the process cwd.
    assert seen["spawn_cwd"] is not None
    assert Path(str(seen["spawn_cwd"])).name.startswith("benchcell-")
    # (b) the answer key is invisible at backend time…
    assert seen["hidden_visible"] is False
    # …but lands for the capture-time pytest run (4 hidden tests collect).
    records = _read_records(repo_root, "s1")
    assert records, "no records written"
    for r in records:
        assert (r["artifact"] or {}).get("hidden_tests_total") == 4
    # The scope is restored once the trial returns.
    assert get_active_spawn_cwd() is None


def test_aggregate_run_rolls_up_per_family_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=2)
    repo_root = tmp_path / "repo"
    _stub_cell_trials(monkeypatch)
    run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=2,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
    )
    report = aggregate_run(bench_run_dir(repo_root, "s1"))
    assert report.total_records == 4
    assert len(report.groups) == 1
    group = report.groups[0]
    assert group["family"] == "proposal"
    assert group["backend"] == "claude"
    assert group["trials"] == 4


# ---------------------------------------------------------------------------
# Step 3 — per-family scorers (hand-written good/bad/partial artifacts so a
# scoring disagreement is debuggable without re-running a backend).
# ---------------------------------------------------------------------------


def _valid_plan_text(steps_block: str, *, test_command: bool = False) -> str:
    """Wrap a steps YAML block in a parseable plan file."""
    tc = "test_command: uv run pytest -q\n" if test_command else ""
    return (
        "---\n"
        "title: Bench scorer fixture\n"
        "status: planning\n"
        "priority: low\n"
        f"{tc}"
        "steps:\n"
        f"{steps_block}"
        "---\n"
        "# Bench scorer fixture\n"
    )


_ONE_FEATURE_STEP = (
    "- id: 1\n"
    "  title: Add discounted_total to the cart\n"
    "  files:\n"
    "  - src/cart.py\n"
    "  change_type: feature\n"
)


# --- proposal ---------------------------------------------------------------


def test_proposal_score_good_artifact_high() -> None:
    answer = load_proposal_answer(REAL_CORPUS, "proposal/seed-feature")
    assert answer is not None
    artifact = ProposalArtifact(plan_text=_valid_plan_text(_ONE_FEATURE_STEP))
    score = score_proposal(artifact, answer)
    assert score.validity == 1.0
    assert score.change_type_agreement == 1.0
    assert score.value == 1.0


def test_proposal_score_unparseable_plan_zero() -> None:
    answer = load_proposal_answer(REAL_CORPUS, "proposal/seed-feature")
    assert answer is not None
    score = score_proposal(ProposalArtifact(plan_text="not a plan at all"), answer)
    assert score.validity == 0.0
    assert score.value == 0.0


def test_proposal_score_mixed_seed_requires_split() -> None:
    answer = load_proposal_answer(REAL_CORPUS, "proposal/seed-mixed-must-split")
    assert answer is not None and answer.must_split
    # Multi-plan split short-circuit (>= 2 entries) scores the split component.
    split_artifact = ProposalArtifact(plan_text=None, split_proposal_entry_count=2)
    split_score = score_proposal(split_artifact, answer)
    assert split_score.split_ok == 1.0
    # A single non-split step does not satisfy the must-split signal.
    single_artifact = ProposalArtifact(
        plan_text=_valid_plan_text(_ONE_FEATURE_STEP), split_proposal_entry_count=0
    )
    single_score = score_proposal(single_artifact, answer)
    assert single_score.split_ok == 0.0
    assert split_score.value > single_score.value


def test_proposal_score_two_pure_steps_satisfy_split() -> None:
    """A refactor→feature two-step plan is the in-plan must-split shape."""
    answer = load_proposal_answer(REAL_CORPUS, "proposal/seed-mixed-must-split")
    assert answer is not None
    steps = (
        "- id: 1\n"
        "  title: Extract rounding + tax helpers\n"
        "  files:\n"
        "  - src/pricing.py\n"
        "  change_type: refactor\n"
        "- id: 2\n"
        "  title: Add per-currency rounding on the extracted helpers\n"
        "  files:\n"
        "  - src/pricing.py\n"
        "  change_type: feature\n"
        "  depends_on:\n"
        "  - 1\n"
    )
    score = score_proposal(ProposalArtifact(plan_text=_valid_plan_text(steps)), answer)
    assert score.split_ok == 1.0
    assert score.value == 1.0


def test_proposal_score_partial_wrong_change_type() -> None:
    answer = load_proposal_answer(REAL_CORPUS, "proposal/seed-feature")
    assert answer is not None
    steps = (
        "- id: 1\n"
        "  title: Add discounted_total\n"
        "  files:\n"
        "  - src/cart.py\n"
        "  change_type: feature\n"
        "- id: 2\n"
        "  title: Wire the coupon table\n"
        "  files:\n"
        "  - src/coupons.py\n"
        "  change_type: refactor\n"
    )
    score = score_proposal(ProposalArtifact(plan_text=_valid_plan_text(steps)), answer)
    assert score.change_type_agreement == 0.5
    assert 0.0 < score.value < 1.0


# --- detail -----------------------------------------------------------------


_DETAIL_GOOD_BODY = (
    "# Add discounted_total\n\n"
    "## Summary\nApply a coupon to the subtotal.\n\n"
    "## Table of Contents\n- Summary\n- Why\n\n"
    "## Why\nCustomers expect coupons.\n\n"
    "## Files\n- `src/cart.py`\n- `src/discounts.py`\n- `tests/test_discounts.py`\n\n"
    "## Implementation\nLook up coupon, clamp, subtract.\n\n"
    "## Tests\n- discounted_total applies a valid coupon\n\n"
    "## Acceptance criteria\n- A valid coupon reduces the total\n"
)


def test_detail_score_all_h2_present_high() -> None:
    answer = load_detail_answer(REAL_CORPUS, "detail/step-1")
    assert answer is not None
    score = score_detail(DetailArtifact(detail_body=_DETAIL_GOOD_BODY), answer)
    assert score.required_h2 == 1.0
    assert score.files_coherence == 1.0
    assert score.acceptance_ok == 1.0
    assert score.value == 1.0


def test_detail_files_coherence_tolerates_depends_on_notes() -> None:
    """Isolating a step for coherence must clear notes with depends_on."""
    from plan_tool.bench import _detail_files_coherence_issue_count
    from plan_tool.schema import Step

    step = Step(
        id=2,
        title="downstream",
        files=["src/cart.py"],
        depends_on=[1],
        depends_on_notes={1: "consumes schema types"},
    )
    # Must not raise Plan validation on orphan note keys.
    assert (
        _detail_files_coherence_issue_count(_DETAIL_GOOD_BODY, step) >= 0
    )


def test_detail_score_missing_h2_penalized() -> None:
    answer = load_detail_answer(REAL_CORPUS, "detail/step-1")
    assert answer is not None
    body = _DETAIL_GOOD_BODY.replace(
        "## Tests\n- discounted_total applies a valid coupon\n\n", ""
    ).replace("## Acceptance criteria\n- A valid coupon reduces the total\n", "")
    score = score_detail(DetailArtifact(detail_body=body), answer)
    assert score.required_h2 < 1.0


def test_detail_score_files_coherence_issue_counts() -> None:
    answer = load_detail_answer(REAL_CORPUS, "detail/step-1")
    assert answer is not None
    # Cites a near-miss of the declared src/discounts.py alongside the real ones.
    body = _DETAIL_GOOD_BODY.replace(
        "- `tests/test_discounts.py`\n",
        "- `tests/test_discounts.py`\n- `src/discount.py`\n",
    )
    score = score_detail(DetailArtifact(detail_body=body), answer)
    assert score.files_coherence < 1.0


def test_detail_score_empty_acceptance_bullets_fail() -> None:
    answer = load_detail_answer(REAL_CORPUS, "detail/step-1")
    assert answer is not None
    body = _DETAIL_GOOD_BODY.replace(
        "## Acceptance criteria\n- A valid coupon reduces the total\n",
        "## Acceptance criteria\n_TODO: fill in_\n",
    )
    score = score_detail(DetailArtifact(detail_body=body), answer)
    assert score.acceptance_ok == 0.0


# --- reconcile --------------------------------------------------------------


def test_reconcile_score_full_recall_precision() -> None:
    answer = load_reconcile_answer(REAL_CORPUS, "reconcile/auth-service")
    assert answer is not None and len(answer.defects) == 2
    findings = [
        "auth.py declares validate_token but the code defines verify_token",
        "cli.py build_parser never registers the promised --strict flag",
    ]
    score = score_reconcile(ReconcileArtifact(findings=findings), answer)
    assert score.recall == 1.0
    assert score.precision == 1.0
    assert score.value == 1.0


def test_reconcile_score_fuzzy_symbol_match() -> None:
    answer = ReconcileAnswerKey(
        defects=[{"file": "auth.py", "symbol": "validate_token"}]
    )
    findings = ["The auth.py validateToken helper is missing from the module"]
    score = score_reconcile(ReconcileArtifact(findings=findings), answer)
    assert score.recall == 1.0
    assert score.recalled_defects == 1


def test_reconcile_score_false_positive_lowers_precision() -> None:
    answer = load_reconcile_answer(REAL_CORPUS, "reconcile/auth-service")
    assert answer is not None
    findings = [
        "auth.py declares validate_token but the code defines verify_token",
        "cli.py build_parser never registers the promised --strict flag",
        "unrelated nit about formatting in widgets.py render()",
    ]
    score = score_reconcile(ReconcileArtifact(findings=findings), answer)
    assert score.recall == 1.0
    assert score.precision < 1.0


def test_reconcile_score_missed_defect_lowers_recall() -> None:
    answer = load_reconcile_answer(REAL_CORPUS, "reconcile/auth-service")
    assert answer is not None
    findings = ["auth.py declares validate_token but the code defines verify_token"]
    score = score_reconcile(ReconcileArtifact(findings=findings), answer)
    assert score.recall < 1.0
    assert score.precision == 1.0


# --- implementation ---------------------------------------------------------


def test_implementation_score_hidden_test_pass_rate() -> None:
    partial = score_implementation(
        ImplementationArtifact(
            hidden_tests_passed=2,
            hidden_tests_total=4,
            test_command_exit=1,
            out_of_scope_file_count=0,
        ),
        ImplementationAnswerKey(),
    )
    full = score_implementation(
        ImplementationArtifact(
            hidden_tests_passed=4,
            hidden_tests_total=4,
            test_command_exit=0,
            out_of_scope_file_count=0,
        ),
        ImplementationAnswerKey(),
    )
    assert partial.hidden_test_rate == 0.5
    assert full.value == 1.0
    assert partial.value < full.value


def test_implementation_score_out_of_scope_penalized() -> None:
    clean = score_implementation(
        ImplementationArtifact(
            hidden_tests_passed=4,
            hidden_tests_total=4,
            test_command_exit=0,
            out_of_scope_file_count=0,
        ),
        ImplementationAnswerKey(),
    )
    dirty = score_implementation(
        ImplementationArtifact(
            hidden_tests_passed=4,
            hidden_tests_total=4,
            test_command_exit=0,
            out_of_scope_file_count=2,
        ),
        ImplementationAnswerKey(),
    )
    assert dirty.scope_clean < 1.0
    assert dirty.value < clean.value


# --- apply ------------------------------------------------------------------


def test_apply_score_target_edit_landed() -> None:
    answer = load_apply_answer(REAL_CORPUS, "apply/add-empty-cart-acceptance-bullet")
    assert answer is not None
    diff = "--- a/detail/01-discounts.md\n+++ b/detail/01-discounts.md\n+- Empty cart returns a total of 0\n"
    score = score_apply(
        ApplyArtifact(verdict="APPLIED", diff_text=diff, out_of_scope_file_count=0),
        answer,
    )
    assert score.target_landed == 1.0
    assert score.value == 1.0


def test_apply_score_unrelated_hunk_penalized() -> None:
    answer = load_apply_answer(REAL_CORPUS, "apply/add-empty-cart-acceptance-bullet")
    assert answer is not None
    diff = "+- Empty cart returns a total of 0\n"
    score = score_apply(
        ApplyArtifact(verdict="APPLIED", diff_text=diff, out_of_scope_file_count=1),
        answer,
    )
    assert score.scope_clean == 0.0


# --- dispatcher + records pass ----------------------------------------------


def _scored_records_fixture() -> list[dict]:
    return [
        {
            "family": "proposal",
            "cell_id": "proposal/seed-feature",
            "backend": "claude",
            "trial": 1,
            "failure_kind": None,
            "artifact": {
                "plan_text": _valid_plan_text(_ONE_FEATURE_STEP),
                "split_proposal_entry_count": 0,
            },
        },
        {
            "family": "implementation",
            "cell_id": "implementation/slugify",
            "backend": "claude",
            "trial": 1,
            "failure_kind": None,
            "artifact": {
                "hidden_tests_passed": 4,
                "hidden_tests_total": 4,
                "test_command_exit": 0,
                "out_of_scope_file_count": 0,
            },
        },
        {
            "family": "apply",
            "cell_id": "apply/add-empty-cart-acceptance-bullet",
            "backend": "claude",
            "trial": 1,
            "failure_kind": None,
            "artifact": {
                "verdict": "APPLIED",
                "diff_text": "+- Empty cart returns a total of 0\n",
                "out_of_scope_file_count": 0,
            },
        },
    ]


def test_score_records_round_trip(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    rec_path = run_dir / "records.jsonl"
    with rec_path.open("w", encoding="utf-8") as handle:
        for record in _scored_records_fixture():
            handle.write(json.dumps(record) + "\n")

    score_records(run_dir, corpus_root=REAL_CORPUS)
    first = [json.loads(line) for line in rec_path.read_text().splitlines()]
    assert len(first) == 3
    for record in first:
        assert record["score"] is not None
        assert 0.0 <= record["score"]["value"] <= 1.0

    # Idempotent: re-running re-derives the same score from the same artifact.
    score_records(run_dir, corpus_root=REAL_CORPUS)
    second = [json.loads(line) for line in rec_path.read_text().splitlines()]
    assert [r["score"] for r in second] == [r["score"] for r in first]


def test_score_trial_skips_timeout_record() -> None:
    record = {
        "family": "implementation",
        "cell_id": "implementation/slugify",
        "failure_kind": "timeout",
        "artifact": None,
    }
    assert score_trial(record, corpus_root=REAL_CORPUS) is None


# ---------------------------------------------------------------------------
# Step 4 — scored aggregation, recommendation, render, and run-meta capture.
# Records are hand-authored with a ``score`` key already attached so the
# aggregation is exercised without re-scoring (and without a real run).
# ---------------------------------------------------------------------------


def _scored_record(
    family: str,
    backend: str,
    trial: int,
    *,
    value: float | None,
    cell_id: str | None = None,
    failure_kind: str | None = None,
    wall_clock_ms: int = 100,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    cost_usd: float | None = None,
    retries: int = 0,
) -> dict:
    """Build one scored ``records.jsonl`` line; ``value=None`` ⇒ no score."""
    return {
        "family": family,
        "cell_id": cell_id or f"{family}/cell",
        "backend": backend,
        "trial": trial,
        "wall_clock_ms": wall_clock_ms,
        "tokens_input": tokens_input,
        "tokens_output": tokens_output,
        "cost_usd": cost_usd,
        "failure_kind": failure_kind,
        "retries": retries,
        "exit_or_verdict": 0,
        "raw_output": "",
        "artifact": {},
        "score": {"value": value} if value is not None else None,
    }


def _write_run(tmp_path: Path, records: list[dict], meta: RunMeta | None = None) -> Path:
    """Write a run dir with the given records (+ optional run-meta)."""
    run_dir = tmp_path / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    with (run_dir / "records.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    if meta is not None:
        write_run_meta(run_dir, meta)
    return run_dir


def test_build_quality_report_groups_by_family_backend(tmp_path: Path) -> None:
    import statistics

    records = (
        [_scored_record("proposal", "claude", t, value=v) for t, v in ((1, 0.8), (2, 0.9), (3, 0.85))]
        + [_scored_record("proposal", "codex", t, value=v) for t, v in ((1, 0.6), (2, 0.5), (3, 0.55))]
        + [_scored_record("implementation", "claude", t, value=0.7) for t in (1, 2, 3)]
        + [_scored_record("implementation", "codex", t, value=v) for t, v in ((1, 0.72), (2, 0.71), (3, 0.73))]
    )
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    assert len(report.cells) == 4
    cell = next(c for c in report.cells if c.family == "proposal" and c.backend == "claude")
    assert cell.quality_median == statistics.median([0.8, 0.9, 0.85])
    assert cell.trial_count == 3
    assert cell.scored_count == 3


def test_quality_spread_is_min_max_not_percentile(tmp_path: Path) -> None:
    records = [
        _scored_record("proposal", "claude", t, value=v)
        for t, v in ((1, 0.2), (2, 0.9), (3, 0.5))
    ]
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (cell,) = report.cells
    # Spread is the pooled extremes — a quantile would interpolate something else.
    assert cell.quality_min == 0.2
    assert cell.quality_max == 0.9


def test_quality_excludes_timeout_records(tmp_path: Path) -> None:
    records = [
        _scored_record("proposal", "claude", 1, value=0.8),
        _scored_record("proposal", "claude", 2, value=0.6),
        _scored_record("proposal", "claude", 3, value=None, failure_kind="timeout"),
    ]
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (cell,) = report.cells
    assert cell.quality_median == 0.7  # median of [0.8, 0.6], timeout excluded
    assert cell.scored_count == 2
    assert cell.trial_count == 3
    assert cell.failure_count == 1
    assert cell.failure_rate == pytest.approx(1 / 3)


def test_tokens_none_safe_for_batch_family(tmp_path: Path) -> None:
    records = [_scored_record("proposal", "claude", t, value=0.5) for t in (1, 2, 3)]
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (cell,) = report.cells
    assert cell.tokens_input_total is None
    assert cell.tokens_output_total is None
    assert cell.cost_usd_total is None


def test_build_quality_report_runs_score_records_when_unscored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A record with no ``score`` key but a real artifact is scored on the fly.
    record = {
        "family": "proposal",
        "cell_id": "proposal/seed-feature",
        "backend": "claude",
        "trial": 1,
        "wall_clock_ms": 100,
        "tokens_input": None,
        "tokens_output": None,
        "cost_usd": None,
        "failure_kind": None,
        "retries": 0,
        "exit_or_verdict": 0,
        "raw_output": "",
        "artifact": {
            "plan_text": _valid_plan_text(_ONE_FEATURE_STEP),
            "split_proposal_entry_count": 0,
        },
    }
    run_dir = _write_run(tmp_path, [record])

    calls: list[Path] = []
    real = bench.score_records

    def _spy(rd: Path, *, corpus_root: Path) -> None:
        calls.append(rd)
        return real(rd, corpus_root=corpus_root)

    monkeypatch.setattr(bench, "score_records", _spy)
    report = build_quality_report(run_dir, corpus_root=REAL_CORPUS)
    assert calls, "score_records was not called for an unscored run dir"
    (cell,) = report.cells
    assert cell.quality_median is not None


def test_recommend_per_family_picks_highest_median(tmp_path: Path) -> None:
    records = (
        [_scored_record("proposal", "claude", t, value=0.9) for t in (1, 2, 3)]
        + [_scored_record("proposal", "codex", t, value=0.5) for t in (1, 2, 3)]
    )
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (rec,) = recommend_per_family(report)
    assert rec.recommended_backend == "claude"
    assert rec.evidence is not None and rec.evidence.backend == "claude"


def test_recommend_tie_break_prefers_lower_wall_clock(tmp_path: Path) -> None:
    # claude has the marginally higher median but is slower; within the tie
    # delta the lower-wall-clock backend wins and the caveat flags no winner.
    records = (
        [_scored_record("proposal", "claude", t, value=0.82, wall_clock_ms=200) for t in (1, 2, 3)]
        + [_scored_record("proposal", "codex", t, value=0.80, wall_clock_ms=100) for t in (1, 2, 3)]
    )
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (rec,) = recommend_per_family(report)
    assert rec.recommended_backend == "codex"
    assert "No clear winner" in rec.confidence_caveat


def test_recommend_no_scorable_trials_is_none(tmp_path: Path) -> None:
    records = [
        _scored_record("proposal", "claude", t, value=None, failure_kind="timeout")
        for t in (1, 2, 3)
    ]
    report = build_quality_report(_write_run(tmp_path, records), corpus_root=REAL_CORPUS)
    (rec,) = recommend_per_family(report)
    assert rec.recommended_backend is None
    assert "no scorable" in rec.confidence_caveat.lower()


def test_confidence_caveat_names_trial_and_cell_counts(tmp_path: Path) -> None:
    meta = RunMeta(
        stamp="s1",
        backends=(BackendVersion("claude", "1.2.3"),),
        corpus_hash=corpus_hash(REAL_CORPUS),
        corpus_cell_count=2,
        trials=3,
        families=("proposal",),
    )
    records = [
        _scored_record("proposal", "claude", t, value=0.7, cell_id=f"proposal/cell-{c}")
        for c in ("a", "b")
        for t in (1, 2, 3)
    ]
    report = build_quality_report(_write_run(tmp_path, records, meta), corpus_root=REAL_CORPUS)
    (rec,) = recommend_per_family(report)
    assert "3 trials/backend" in rec.confidence_caveat
    assert "2 proposal corpus cell" in rec.confidence_caveat


def test_corpus_hash_stable_and_order_independent(tmp_path: Path) -> None:
    corpus_a = tmp_path / "a"
    (corpus_a / "proposal").mkdir(parents=True)
    (corpus_a / "proposal" / "x.md").write_text("alpha", encoding="utf-8")
    (corpus_a / "proposal" / "y.md").write_text("beta", encoding="utf-8")
    first = corpus_hash(corpus_a)
    second = corpus_hash(corpus_a)
    assert first == second  # deterministic

    # Same files written in the opposite order hash identically (sorted paths).
    corpus_b = tmp_path / "b"
    (corpus_b / "proposal").mkdir(parents=True)
    (corpus_b / "proposal" / "y.md").write_text("beta", encoding="utf-8")
    (corpus_b / "proposal" / "x.md").write_text("alpha", encoding="utf-8")
    assert corpus_hash(corpus_b) == first


def test_report_marks_stale_when_corpus_hash_differs(tmp_path: Path) -> None:
    meta = RunMeta(
        stamp="s1",
        backends=(BackendVersion("claude", "1.0"),),
        corpus_hash="deadbeef",  # differs from the recomputed REAL_CORPUS hash
        corpus_cell_count=1,
        trials=3,
        families=("proposal",),
    )
    records = [_scored_record("proposal", "claude", t, value=0.7) for t in (1, 2, 3)]
    report = build_quality_report(_write_run(tmp_path, records, meta), corpus_root=REAL_CORPUS)
    assert report.is_stale is True
    assert "STALE" in render_report_markdown(report)


def test_render_recommendations_doc_has_staleness_header(tmp_path: Path) -> None:
    meta = RunMeta(
        stamp="2026-05-14T00-00-00-abc123",
        backends=(BackendVersion("claude", "1.2.3"), BackendVersion("codex", "0.9")),
        corpus_hash=corpus_hash(REAL_CORPUS),
        corpus_cell_count=1,
        trials=3,
        families=("proposal",),
    )
    records = [_scored_record("proposal", "claude", t, value=0.7) for t in (1, 2, 3)]
    report = build_quality_report(_write_run(tmp_path, records, meta), corpus_root=REAL_CORPUS)
    doc = render_recommendations_doc(report, recommend_per_family(report))
    assert "do not edit directly" in doc
    assert "2026-05-14T00-00-00-abc123" in doc
    assert "1.2.3" in doc and "0.9" in doc
    assert meta.corpus_hash in doc
    # The JSON twin carries the same comparison data.
    payload = report_to_dict(report)
    assert payload["run_meta"]["stamp"] == meta.stamp
    assert payload["cells"]


def test_load_run_meta_missing_returns_none(tmp_path: Path) -> None:
    records = [_scored_record("proposal", "claude", t, value=0.7) for t in (1, 2, 3)]
    run_dir = _write_run(tmp_path, records)  # no run_meta.json
    assert load_run_meta(run_dir) is None
    report = build_quality_report(run_dir, corpus_root=REAL_CORPUS)
    assert report.run_meta is None
    assert report.is_stale is False  # staleness unknown without recorded meta
    assert "not recorded" in render_report_markdown(report)


def test_run_bench_matrix_writes_run_meta(tmp_path: Path) -> None:
    corpus = _write_stub_proposal_corpus(tmp_path / "corpus", seeds=1)
    repo_root = tmp_path / "repo"
    summary = run_bench_matrix(
        repo_root,
        corpus_root=corpus,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RecordingStrInvoker()),
        version_probe=lambda backend: f"v-{backend.name}",
    )
    # Record output is unchanged by the additive run-meta write.
    assert summary.records_written == 1
    assert len(_read_records(repo_root, "s1")) == 1
    meta = load_run_meta(bench_run_dir(repo_root, "s1"))
    assert meta is not None
    assert meta.backends == (BackendVersion("claude", "v-claude"),)
    assert meta.corpus_hash == corpus_hash(corpus)
    assert meta.trials == 1
    assert meta.families == ("proposal",)


# ---------------------------------------------------------------------------
# Realistic stub invokers — one fully-successful trial per family.
#
# The matrix-mechanics tests above use empty stubs whose trials FAIL inside
# the production flow (unparseable steps -> CreateError), which is fine for
# pinning enumeration/resume/record shape but masked a deterministic
# wrapper-level defect: the TODO-body gate killed every real proposal trial
# and the suite stayed green because no test ever asserted a successful
# trial's ``failure_kind``. These invokers answer each production phase with
# a minimal-but-parseable response so one trial per family completes
# end-to-end, and each test pins ``failure_kind is None`` + a scorable
# artifact. A future flag collision in any family's production flow now
# fails its test instead of hiding behind always-failing stubs.
# ---------------------------------------------------------------------------


_DISTILL_SECTIONS = {
    key: f"{key} prose for the realistic stub."
    for key in (
        "Overview",
        "Problem statement",
        "Architecture",
        "Out of scope",
        "Risks",
        "Testing",
        "Acceptance criteria",
        "Deferred",
    )
}

_REALISTIC_STEPS_JSON = json.dumps(
    [
        {
            "title": "Implement the described feature",
            "complexity": "low",
            "change_type": "feature",
            "files": [],
            "creates": [],
            "depends_on": [],
        }
    ]
)


class RealisticProposalInvoker:
    """Answers create_plan's phases with parseable payloads.

    Routes by prompt: the distill pass gets a single-outcome sections
    JSON, the steps pass gets a one-step array, and references research gets
    ``[]`` — the explicit valid-empty result tolerated by production.
    """

    def __call__(self, prompt: str, **_kwargs) -> str:
        if "Distill a free-form seed" in prompt:
            return json.dumps({"outcome": "single", "sections": _DISTILL_SECTIONS})
        if "Propose an initial plan step-list" in prompt:
            return _REALISTIC_STEPS_JSON
        return "[]"


_REALISTIC_DETAIL_BODY = """# Step detail (realistic stub)

## Summary

One-paragraph summary of the step.

## Table of Contents

- Summary
- Why
- Files
- Implementation
- Tests
- Acceptance criteria

## Why

The step is needed for the fixture plan to do its job.

## Files

- src/widget.py

## Implementation

Describe the change in prose.

## Tests

- a unit test bullet

## Acceptance criteria

- a parseable acceptance bullet

<!-- plan-tool-detail-deferrals
{"deferrals": []}
-->
"""


class RealisticDetailInvoker:
    """Returns a draft carrying every required H2 so generate_detail writes it."""

    def __call__(self, prompt: str, **_kwargs) -> str:
        return _REALISTIC_DETAIL_BODY


class RealisticReconcileInvoker:
    """Names each repo's seeded defects in a machine-parsed Findings block."""

    def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
        if "auth.py" in prompt:
            return 0, (
                "Prose review.\n\n## Findings\n\n"
                "- HIGH: `auth.py:validate_token` is missing — the code "
                "defines `verify_token` instead (rename drift).\n"
                "- HIGH: `cli.py` `--strict` flag is never registered by "
                "`build_parser`; the audience-claim rejection is absent.\n"
            )
        return 0, (
            "Prose review.\n\n## Findings\n\n"
            "- HIGH: `exporter.py:export` has no retry loop — the "
            "acceptance criteria promise 3 retries on transient IO "
            "errors.\n"
        )


_REALISTIC_SOLUTION = '''import re


def slugify(text):
    text = text.lower()
    text = re.sub(r"\\s+", "-", text)
    text = re.sub(r"[^a-z0-9-]", "", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def truncate_words(text, max_words):
    words = text.split()
    if len(words) <= max_words:
        return " ".join(words)
    return " ".join(words[:max_words]) + "..."
'''


class RealisticImplementationInvoker:
    """Performs the backend's edit: writes a correct solution.py.

    Uses ``backend.get_active_spawn_cwd()`` — the same scope a real
    spawned backend runs in — so this also exercises the cwd-threading
    seam from the consumer side.
    """

    def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
        from plan_tool.backend import get_active_spawn_cwd

        cwd = get_active_spawn_cwd()
        assert cwd is not None, "implementation trial ran without a spawn scope"
        (cwd / "solution.py").write_text(_REALISTIC_SOLUTION, encoding="utf-8")
        return 0, "Implemented the step in solution.py."


class RealisticApplyInvoker:
    """Performs the finding's stated edit and reports an APPLIED verdict."""

    def __call__(self, prompt: str, **_kwargs) -> tuple[int, str]:
        from plan_tool.backend import get_active_spawn_cwd

        cwd = get_active_spawn_cwd()
        assert cwd is not None, "apply trial ran without a spawn scope"
        if "Empty cart returns a total of 0" in prompt:
            target = cwd / "detail" / "01-discounts.md"
            target.write_text(
                target.read_text(encoding="utf-8")
                + "- Empty cart returns a total of 0\n",
                encoding="utf-8",
            )
        elif "tests/test_exporter.py" in prompt:
            target = cwd / "detail" / "01-exporter.md"
            target.write_text(
                target.read_text(encoding="utf-8")
                + "- tests/test_exporter.py\n",
                encoding="utf-8",
            )
        return 0, "Edited the detail file.\n\n## Verdict\nAPPLIED\n"


def _scored_records(repo_root: Path, stamp: str) -> list[dict]:
    from plan_tool.bench import score_records, records_path

    score_records(records_path(repo_root, stamp).parent, corpus_root=REAL_CORPUS)
    return _read_records(repo_root, stamp)


def test_proposal_realistic_trial_succeeds(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["proposal"],
        trials=1,
        invokers=BenchInvokers(proposal_invoker=RealisticProposalInvoker()),
    )
    records = _scored_records(repo_root, "s1")
    assert len(records) == 3
    for r in records:
        assert r["failure_kind"] is None, (r["cell_id"], r["raw_output"])
        assert r["artifact"] is not None
        assert r["score"] is not None
        # A written plan parses; the split short-circuit doesn't fire for a
        # single-outcome distill, so validity comes from the plan text.
        assert r["score"]["validity"] == 1.0


def test_detail_realistic_trial_succeeds(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["detail"],
        trials=1,
        invokers=BenchInvokers(detail_invoker=RealisticDetailInvoker()),
    )
    records = _scored_records(repo_root, "s1")
    assert len(records) == 2
    for r in records:
        assert r["failure_kind"] is None, (r["cell_id"], r["raw_output"])
        assert r["exit_or_verdict"] == "written"
        assert r["score"] is not None
        assert r["score"]["required_h2"] == 1.0


def test_reconcile_realistic_trial_succeeds(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["reconcile"],
        trials=1,
        invokers=BenchInvokers(reconcile_invoker=RealisticReconcileInvoker()),
    )
    records = _scored_records(repo_root, "s1")
    assert len(records) == 2
    for r in records:
        assert r["failure_kind"] is None, (r["cell_id"], r["raw_output"])
        assert r["score"] is not None
        # Every seeded defect is named with its file+symbol — full recall.
        assert r["score"]["recall"] == 1.0


def test_implementation_realistic_trial_succeeds(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["implementation"],
        trials=1,
        invokers=BenchInvokers(
            implementation_invoker=RealisticImplementationInvoker()
        ),
    )
    records = _scored_records(repo_root, "s1")
    assert len(records) == 2
    for r in records:
        assert r["failure_kind"] is None, (r["cell_id"], r["raw_output"])
        art = r["artifact"]
        assert art["hidden_tests_passed"] == art["hidden_tests_total"] == 4
        assert art["test_command_exit"] == 0
        assert art["out_of_scope_file_count"] == 0
        assert r["score"] is not None


def test_apply_realistic_trial_succeeds(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    run_bench_matrix(
        repo_root,
        corpus_root=REAL_CORPUS,
        stamp="s1",
        backends=["claude"],
        families=["apply"],
        trials=1,
        invokers=BenchInvokers(apply_invoker=RealisticApplyInvoker()),
    )
    records = _scored_records(repo_root, "s1")
    assert len(records) == 2
    for r in records:
        assert r["failure_kind"] is None, (r["cell_id"], r["raw_output"])
        assert r["score"] is not None
        assert r["score"]["target_landed"] == 1.0, (
            r["cell_id"],
            r["raw_output"],
        )
