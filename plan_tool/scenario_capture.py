"""Scenario capture for prompt A/B experiments.

Records the *re-runnable inputs* of real ``create`` / ``detail`` invocations so
they can later be replayed through an experiment's arms and scored. The corpus
is **multi-experiment**: every record carries the ``experiment`` it belongs to
(today only ``prompt-mode`` — combined vs split) and the ``arm`` that ran, so
one corpus holds many A/Bs (see ``Experiment`` / ``EXPERIMENTS`` below, and
``docs/explanations/prompt-ab-testing.md`` for the "defining a new experiment" guide). Off by
default: writes only when ``PLAN_TOOL_CAPTURE_SCENARIOS`` is truthy, so normal
runs pay nothing and nothing lands on disk unexpectedly.

Each record is one JSON line under
``<repo_root>/.plan-tool/scenarios/<kind>.jsonl`` (schema v2, canonical
sorted-key serialization — only ``captured_at`` is not a function of the run):

    {"v": 2, "kind": "propose_steps", "experiment": "prompt-mode",
     "arm": "combined", "categories": ["foundational-logic"], "repo_sha": "<git HEAD>",
     "dirty": false, "run_id": "<run>", "captured_at": "<iso>",
     "inputs": {"description": "..."}, "outcome": {"n_steps": 4}}

``inputs`` is everything needed to *re-run* the scenario (a create description, a
detail plan-path + step id + plan content hash); ``repo_sha`` + ``dirty`` pin the
tree the run audited so a replay can reproduce it (the arms are functions of repo
state, not just ``inputs``); ``run_id`` links to the run-log telemetry under
``.plan-tool/runs/``. The capture is best-effort — a disk / permission error is
swallowed so it can never break the run it is observing.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

# Record schema version — bump when the record shape changes so a consumer can
# tell old corpora from new as the mechanism grows.
# v2: ``mode`` (combined/split) generalized to ``experiment`` + ``arm`` so one
# corpus can hold many A/B experiments, not just prompt-mode.
SCHEMA_VERSION = 2

_ENABLE_ENV = "PLAN_TOOL_CAPTURE_SCENARIOS"
_TRUTHY = frozenset({"1", "true", "yes", "on"})

# Category vocabulary. This is an OPEN set: ``categorize_scenario`` records
# whatever truthy signals a caller hands it, so a future A/B axis can introduce
# a new category by computing a new signal at its orchestrator — no change here.
# The constants below are the *currently known* labels, centralised so call
# sites share spelling and a future replay/report tool can enumerate them.
#
# A scenario is "relevant" — and therefore saved — only when at least one
# category applies (the run exercised a behavior the experiment changes). A
# trivial run matches nothing and is dropped, keeping the corpus signal-dense.
CATEGORY_FOUNDATIONAL = "foundational-logic"  # shared/duplicated logic in play
CATEGORY_MIXED_STEP = "mixed-step"  # a refactor+feature split / purity finding
CATEGORY_FAILURE = "failure"  # the run failed (parse/graph/write) — kept as the
# most discriminating A/B case: the inputs that broke one arm are re-runnable.
# ``KNOWN_CATEGORIES`` is derived from the experiment registry below (so a new
# experiment's categories extend it with no second edit) — see after EXPERIMENTS.


@dataclass(frozen=True)
class Experiment:
    """A registered A/B experiment — its arms and how to select one.

    Adding a future prompt A/B is a *registration*, not a re-implementation:
    define an ``Experiment``, add ``capture_scenario(experiment=<name>, arm=…)``
    calls at its orchestrator, and wire its arm to whatever prompt knobs it
    flips. The capture corpus, dedup, provenance, and replay tooling are all
    generic over ``experiment`` + ``arm``.
    """

    name: str  # stable id stored in every record's ``experiment`` field
    arms: tuple[str, ...]  # the variants compared (e.g. ("combined","split"))
    default_arm: str  # the arm when nothing is selected (the safe/legacy one)
    categories: frozenset[str] = field(default_factory=frozenset)  # this
    # experiment's behavior categories (``failure`` is universal, not listed)
    env_var: Optional[str] = None  # optional env selector for this experiment

    def resolve_arm(self, flag: Optional[str] = None) -> str:
        """Resolve the active arm: ``flag`` > ``env_var`` env > ``default_arm``.

        An unrecognized value (typo, removed arm) falls back to ``default_arm``
        so a mistake never silently changes behavior.
        """
        env_val = os.environ.get(self.env_var) if self.env_var else None
        for cand in (flag, env_val):
            norm = (cand or "").strip().lower()
            if norm in self.arms:
                return norm
        return self.default_arm


# The combined-vs-split prompt A/B (the first registered experiment).
PROMPT_MODE_EXPERIMENT = Experiment(
    name="prompt-mode",
    arms=("combined", "split"),
    default_arm="combined",
    categories=frozenset({CATEGORY_FOUNDATIONAL, CATEGORY_MIXED_STEP}),
    env_var="PLAN_TOOL_PROMPT_MODE",
)

# Registry of all experiments — a generic selector / replay tool enumerates this
# rather than hard-coding prompt-mode. Register new experiments here.
EXPERIMENTS: dict[str, Experiment] = {
    PROMPT_MODE_EXPERIMENT.name: PROMPT_MODE_EXPERIMENT,
}


# Known category labels — for documentation / tooling (e.g. validating a
# ``--category`` filter on a future replay command). DERIVED from the registry —
# the union of every registered experiment's declared ``categories`` plus the
# universal ``failure`` — so registering an experiment with a new category
# extends this automatically, with no hand-maintained parallel list to drift.
# ``CATEGORY_FAILURE`` is universal (every experiment can fail) and is therefore
# not listed on any ``Experiment``.
KNOWN_CATEGORIES: frozenset[str] = frozenset({CATEGORY_FAILURE}).union(
    *(exp.categories for exp in EXPERIMENTS.values())
)


def resolve_arm(experiment: str, *, flag: Optional[str] = None) -> str:
    """Resolve the active arm for a registered ``experiment`` (flag > env >
    default). Unknown experiment name → empty string (caller decides)."""
    exp = EXPERIMENTS.get(experiment)
    return exp.resolve_arm(flag) if exp is not None else ""


def valid_categories_for(experiment: str) -> Optional[frozenset[str]]:
    """The category vocabulary a registered ``experiment`` may emit — its
    declared ``categories`` plus the universal ``failure``.

    ``None`` for an unregistered experiment: its owner defines the vocabulary,
    so :func:`capture_scenario` won't filter it. This is what makes the
    ``Experiment.categories`` field load-bearing — capture drops any category a
    call site emits that the experiment didn't declare, so a typo can't land
    junk in the corpus and a genuinely new category must be registered to be
    captured.
    """
    exp = EXPERIMENTS.get(experiment)
    if exp is None:
        return None
    return exp.categories | {CATEGORY_FAILURE}


def arm_from_split(arm: Optional[str], *, split: bool) -> str:
    """Resolve the arm label to record. A caller-resolved ``arm`` wins; when it
    is ``None`` (the caller didn't thread it) fall back to invoker-presence —
    the split arm wires the lifted-out invokers, so ``split=True`` ⇒ ``"split"``.

    Threading the resolved ``arm`` from the CLI removes the two-sources-of-truth
    between arm *selection* (resolved via the experiment) and arm *recording*
    (historically re-derived from invoker presence at the capture site).
    """
    if arm is not None:
        return arm
    return "split" if split else "combined"


def repo_sha(repo_root: Path) -> Optional[str]:
    """Best-effort git HEAD of ``repo_root`` — the provenance a faithful replay
    needs (the proposal/detail are functions of the tree, not just ``inputs``).

    Returns ``None`` when the dir is not a git work tree or git is unavailable;
    capture proceeds without provenance rather than failing.
    """
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    sha = out.stdout.strip()
    return sha if out.returncode == 0 and sha else None


def content_sha(path: Path) -> Optional[str]:
    """Short content hash of a file (for detail's plan snapshot) — distinguishes
    an uncommitted plan edit at the same ``repo_sha``. ``None`` if unreadable."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()[:12]
    except OSError:
        return None


# The capture's OWN output dir, excluded from the dirty check below: a corpus
# file the prior run wrote is not a change to the source tree the *next* run
# depends on, so it must not falsely flip ``dirty`` (which would make a consumer
# skip reproducible scenarios). Matters in target repos that don't gitignore it.
_CORPUS_REL = ".plan-tool/scenarios"


def working_tree_dirty(repo_root: Path) -> Optional[bool]:
    """Whether ``repo_root`` has uncommitted changes to the SOURCE tree
    (``git status --porcelain``, ignoring the scenario corpus itself).

    ``repo_sha`` pins HEAD, but the run used the *working tree*; a dirty tree is
    not faithfully reproducible from the commit alone. Returns ``True``/``False``
    so a consumer can skip/flag dirty captures, or ``None`` when the dir is not a
    git work tree or git is unavailable.
    """
    try:
        out = subprocess.run(
            # ``-uall`` lists untracked files individually (git otherwise
            # collapses an untracked dir to ``?? .plan-tool/``), so the
            # corpus-exclusion filter below sees the real paths.
            ["git", "-C", str(repo_root), "status", "--porcelain",
             "--untracked-files=all"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    for line in out.stdout.splitlines():
        if not line.strip():
            continue
        # Porcelain v1: two status chars + space + path.
        path = line[3:].strip()
        if path.startswith(_CORPUS_REL):
            continue  # the capture's own corpus — not a source change
        return True
    return False


def _utcnow() -> datetime:
    """UTC now at seconds precision — a seam so capture timestamps are
    controllable in tests (``captured_at`` is the only field that is not a pure
    function of the run's inputs)."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def categorize_scenario(signals: Mapping[str, bool]) -> list[str]:
    """Return the labels of every truthy signal, in the caller's order.

    Open-vocabulary by design: the caller owns the category names (typically the
    ``CATEGORY_*`` constants, but any string works), so adding a detector later
    is a call-site change, not a change here. Returns ``[]`` when no signal is
    set — the caller treats that as "not a relevant scenario" and skips capture.
    """
    return [name for name, present in signals.items() if present]


def capture_enabled() -> bool:
    """True when ``PLAN_TOOL_CAPTURE_SCENARIOS`` is set to a truthy value."""
    return os.environ.get(_ENABLE_ENV, "").strip().lower() in _TRUTHY


def scenarios_dir(repo_root: Path) -> Path:
    """The per-repo scenario corpus directory (not created until a write)."""
    return repo_root / ".plan-tool" / "scenarios"


def _dedup_key(
    kind: str,
    experiment: str,
    arm: str,
    sha: Optional[str],
    inputs: dict,
    failed: bool,
) -> str:
    """Identity of a scenario for de-duplication: same kind + experiment + arm +
    tree + inputs + outcome-class is the same replayable scenario (regardless of
    LLM-varying categories/outcome detail). ``failed`` keeps a later *success*
    of a previously-*failed* input distinct, preserving the flaky-input signal.
    """
    payload = json.dumps(
        [kind, experiment, arm, sha, inputs, failed],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _existing_keys(target: Path) -> set[str]:
    """Dedup keys already in the corpus file (best-effort; empty on any error)."""
    keys: set[str] = set()
    try:
        text = target.read_text(encoding="utf-8")
    except OSError:
        return keys
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        keys.add(
            _dedup_key(
                rec.get("kind", ""),
                rec.get("experiment", ""),
                # tolerate a v1 record (``mode``) when reading an older corpus
                rec.get("arm", rec.get("mode", "")),
                rec.get("repo_sha"),
                rec.get("inputs", {}),
                CATEGORY_FAILURE in rec.get("categories", []),
            )
        )
    return keys


def capture_scenario(
    kind: str,
    *,
    experiment: str,
    arm: str,
    categories: Sequence[str],
    inputs: dict[str, Any],
    outcome: Optional[dict[str, Any]] = None,
    repo_root: Optional[Path],
    run_id: Optional[str] = None,
) -> Optional[Path]:
    """Append one scenario record to ``<repo_root>/.plan-tool/scenarios/<kind>.jsonl``.

    ``experiment`` is the A/B this record belongs to (e.g. ``"prompt-mode"``) and
    ``arm`` the variant that ran (e.g. ``"combined"``/``"split"``) — one corpus
    holds many experiments, filterable by ``experiment``.

    No-op (returns ``None``) when:
    - capture is disabled (``PLAN_TOOL_CAPTURE_SCENARIOS`` unset/falsy),
    - ``repo_root`` is ``None``,
    - ``categories`` is empty — the **relevance gate**: a run that exercised no
      experiment-relevant behavior is not worth saving, or
    - an identical scenario (same kind + experiment + arm + ``repo_sha`` +
      ``inputs`` + failure-class) is already in the corpus — **dedup**, so
      re-running the same input doesn't bloat the replay set (a later success of
      a previously *failed* input is kept distinct).

    The record pins provenance (``repo_sha`` + ``dirty``) and telemetry
    (``run_id``) so a consumer can faithfully reproduce the run and correlate
    its run-log, and is serialized canonically (sorted keys) so it is a
    deterministic function of its inputs. Best-effort on write: an ``OSError``
    is swallowed and ``None`` returned, never raised into the orchestrator.
    """
    if repo_root is None or not categories or not capture_enabled():
        return None
    # Constrain to the experiment's declared vocabulary so a typo'd category at
    # a call site can't silently land junk in the corpus (and a genuinely new
    # category must be registered on the ``Experiment`` to be captured). An
    # unregistered experiment is not filtered — its owner defines the vocabulary.
    valid = valid_categories_for(experiment)
    if valid is not None:
        categories = [c for c in categories if c in valid]
        if not categories:
            return None  # nothing survived the vocabulary gate → not relevant
    sha = repo_sha(repo_root)
    failed = CATEGORY_FAILURE in categories
    target = scenarios_dir(repo_root) / f"{kind}.jsonl"
    if _dedup_key(kind, experiment, arm, sha, inputs, failed) in _existing_keys(
        target
    ):
        return None
    record = {
        "v": SCHEMA_VERSION,
        "kind": kind,
        "experiment": experiment,
        "arm": arm,
        "categories": list(categories),
        "repo_sha": sha,
        # ``repo_sha`` pins HEAD; ``dirty`` flags an uncommitted tree the commit
        # alone can't reproduce, so a consumer can skip non-reproducible runs.
        "dirty": working_tree_dirty(repo_root),
        "run_id": run_id,
        "captured_at": _utcnow().isoformat(),
        "inputs": inputs,
        "outcome": outcome or {},
    }
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as fh:
            # Canonical serialization (sorted keys) so a record is a
            # deterministic function of its inputs — only ``captured_at`` varies.
            fh.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return None
    return target
