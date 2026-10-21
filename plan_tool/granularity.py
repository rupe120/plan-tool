"""plan-tool granularity advisor: deterministic split/merge smell detection.

A cycle-free leaf exposing the stateless ``assess_granularity`` contract, the
``GranularityEvidence`` per-stage envelope, and the no-Claude split/merge
detectors. It imports only ``plan_tool.schema`` (``Plan``/``Step``/
``ChangeType``) and ``plan_tool.review``'s finding primitives
(``Recommendation``/``_make_rec_id``/``Invoker``) — never CLI or orchestrator
modules — so it sits *below* ``create``/``detail``/``completeness``, which
import it in later steps.

The deterministic signals here read only the ``Plan`` and never shell out, and
neither does the prose MIXED-STEP kernel (:func:`parse_mixed_step_findings`),
which is a pure regex lift of the ``## Structural findings`` block the model
already authored. The ``invoker`` seam is therefore present but unused on every
path — it is reserved for a stage that needs a live Claude judgment. The
deterministic split/merge recs are advisory (``severity="info"``); the prose
kernel's recs are ``severity="medium"`` (higher-confidence). Neither family is
ever apply-eligible — ``granularity-split`` is excluded from
``review.APPLY_ELIGIBLE_SOURCES``.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Optional

from plan_tool.review import (
    MERGE_ACTION_MERGE,
    Invoker,
    Recommendation,
    _make_rec_id,
    render_merge_action,
)
from plan_tool.schema import ChangeType, Plan, Step

# Finding sources. ``_make_rec_id`` folds the source into the id, so detectors
# must pass these exact constants — never a stray literal.
GRANULARITY_SPLIT_SOURCE = "granularity-split"
GRANULARITY_MERGE_SOURCE = "granularity-merge"

SPLIT_PREDICATE_MIXED_VERBS = "mixed-verbs"
SPLIT_PREDICATE_CONJOINED_CLAUSES = "two-clauses"
SPLIT_PREDICATE_UNRELATED_AREAS = "multi-area"
SPLIT_PREDICATE_MIXED_STEP = "mixed-step"

DETERMINISTIC_SPLIT_PREDICATE_KEYS = frozenset(
    {
        SPLIT_PREDICATE_MIXED_VERBS,
        SPLIT_PREDICATE_CONJOINED_CLAUSES,
        SPLIT_PREDICATE_UNRELATED_AREAS,
    }
)
SPLIT_PREDICATE_KEYS = frozenset(
    {*DETERMINISTIC_SPLIT_PREDICATE_KEYS, SPLIT_PREDICATE_MIXED_STEP}
)

# Advisory severity, matching ``review._TEST_STRATEGY_INCONSISTENT_SEV``. The
# rc-0 guarantee is belt-and-suspenders here; the primary guarantee is
# structural — steps 2–4 never pass granularity-* recs into a blocking gate.
_GRANULARITY_SEV = "info"

# Stages allowed to ask for a granularity assessment. Validated now; reserved
# for semantic dispatch later (the deterministic battery is stage-independent).
_VALID_STAGES = frozenset({"create", "detail", "completeness"})

# Verb lexicons for the title smells. Deliberately small and precision-first:
# false positives nag the author, so each detector requires strong evidence.
_REFACTOR_VERBS = frozenset(
    {"refactor", "extract", "move", "rename", "consolidate", "inline", "relocate"}
)
_FEATURE_VERBS = frozenset(
    {"add", "implement", "introduce", "create", "build", "wire"}
)
_ACTION_VERBS = _REFACTOR_VERBS | _FEATURE_VERBS

# A "trivial" refactor footprint for the merge signal — one file or fewer.
_TRIVIAL_REFACTOR_MAX_FILES = 1

# Directories whose paths mirror a source area rather than forming one. Folded
# out of the area count so the ordinary impl+test pairing never false-positives.
_TEST_TOP_DIRS = frozenset({"tests", "test"})


@dataclass(frozen=True)
class GranularityEvidence:
    """Per-stage evidence handed to ``assess_granularity``.

    Mirrors ``review.Recommendation``'s frozen-dataclass style. ``detail_bodies``
    maps ``step_id`` → that step's authored implementation prose (the
    ``## Structural findings`` block detail emits).

    Step 1's deterministic path does **not** read ``detail_bodies`` — it is the
    forward contract surface the semantic fold (step 2) consumes. It is declared
    now so steps 2–4 need not change the public signature; the empty consumption
    is intentional, not a bug.
    """

    detail_bodies: Mapping[int, str] = field(default_factory=dict)


def assess_granularity(
    plan: Plan,
    *,
    stage: str,
    evidence: GranularityEvidence,
    invoker: Optional[Invoker] = None,
) -> list[Recommendation]:
    """Return advisory split/merge granularity recs for ``plan``.

    Stateless and no-Claude on the deterministic path: ``invoker`` defaults to
    ``None`` and is never called here (pinned by a negative test). It defaults
    to ``None`` rather than a real shell-out so this leaf imports only
    ``schema`` and ``review``; adapters inject a concrete invoker when a stage
    folds in prose judgment (step 2+).

    ``stage`` is validated against ``_VALID_STAGES``. The deterministic
    split+merge battery runs for every stage (both read only plan structure);
    the ``"detail"`` stage additionally lifts the prose MIXED-STEP findings
    from ``evidence.detail_bodies`` via :func:`parse_mixed_step_findings`, so
    that kernel has exactly one implementation reached both here and from
    detail's direct callers.
    """
    if stage not in _VALID_STAGES:
        raise ValueError(
            f"unknown granularity stage {stage!r}; "
            f"expected one of {sorted(_VALID_STAGES)}"
        )
    recs = _split_findings(plan) + _merge_findings(plan)
    if stage == "detail":
        for step_id, body in evidence.detail_bodies.items():
            recs += parse_mixed_step_findings(body, plan.step_by_id(step_id), plan.title)
    # De-duplicate by id (distinct predicates carry distinct fingerprints, so
    # this collapses only true repeats — one step tripping the same smell twice).
    seen: set[str] = set()
    out: list[Recommendation] = []
    for rec in recs:
        if rec.id in seen:
            continue
        seen.add(rec.id)
        out.append(rec)
    return out


# --- split detectors (per step → granularity-split) ------------------------


def _split_findings(plan: Plan) -> list[Recommendation]:
    recs: list[Recommendation] = []
    for step in plan.steps:
        for detector in (
            _title_mixes_refactor_and_feature,
            _title_conjoins_clauses,
            _step_spans_unrelated_areas,
        ):
            rec = detector(step)
            if rec is not None:
                recs.append(rec)
    return recs


def _title_words(title: str) -> list[str]:
    """Lowercased word tokens of ``title`` (alphanumeric runs only)."""
    return re.findall(r"[a-z0-9]+", title.lower())


def _title_mixes_refactor_and_feature(step: Step) -> Optional[Recommendation]:
    """Trip when the title carries both a refactor verb and a feature verb.

    Precision over recall — both must be present. This plan's own step-1 title
    ("Add … contract, GranularityEvidence, and deterministic split/merge
    signals") carries a feature verb ("Add") but no refactor verb, so it does
    not trip.
    """
    words = set(_title_words(step.title))
    refactor_hits = sorted(words & _REFACTOR_VERBS)
    feature_hits = sorted(words & _FEATURE_VERBS)
    if not (refactor_hits and feature_hits):
        return None
    return _split_rec(
        step,
        SPLIT_PREDICATE_MIXED_VERBS,
        title=f"Step {step.id} title mixes refactor and feature verbs",
        body=(
            f"Step {step.id} \"{step.title}\" carries refactor verb(s) "
            f"{refactor_hits} and feature verb(s) {feature_hits} — likely two "
            f"concerns in one step."
        ),
    )


def _title_conjoins_clauses(step: Step) -> Optional[Recommendation]:
    """Trip when the title joins ≥2 clauses that each begin with an action verb.

    Clause separators are ``" and "``, ``";"``, and ``","``. Precision over
    recall: *every* part must begin with an action verb, so a comma-led noun
    enumeration ("…, and deterministic split/merge signals"), a parenthetical
    flag list ("…, --reconcile, --step"), or a verb-list inside one clause
    ("…that flags, blocks, and reports") — whose fragments are not all verb-led
    — does not trip. Only genuinely conjoined action clauses do; the comma is as
    safe a separator as ``and``/``;`` precisely because of the verb-led guard.
    """
    parts = [p for p in re.split(r"\s+and\s+|[;,]\s+", step.title) if p.strip()]
    if len(parts) < 2:
        return None

    def _begins_with_verb(clause: str) -> bool:
        words = _title_words(clause)
        return bool(words) and words[0] in _ACTION_VERBS

    if not all(_begins_with_verb(p) for p in parts):
        return None
    return _split_rec(
        step,
        SPLIT_PREDICATE_CONJOINED_CLAUSES,
        title=f"Step {step.id} title conjoins multiple action clauses",
        body=(
            f"Step {step.id} \"{step.title}\" reads as {len(parts)} verb-led "
            f"clauses — likely {len(parts)} concerns in one step."
        ),
    )


def _step_spans_unrelated_areas(step: Step) -> Optional[Recommendation]:
    """Trip when a *code* step's files span ≥2 distinct top-level areas.

    Areas come from ``step.all_files`` (so ``creates`` counts) via the **top**
    path segment, so a package and its sub-packages collapse to one area
    (``plan_tool`` and ``plan_tool/cli`` are the same area — a normal
    logic+CLI vertical slice, not two unrelated concerns). A ``tests/`` mirror
    and documentation (``.md``) riders fold out of the count, so neither the
    ordinary impl+test pairing nor a code step that ships a companion doc
    false-positives. **Non-code (doc/config) steps are exempt entirely** — a
    step that documents across many surfaces is not over-packed (mirrors the
    Stage-2 "non-code riders don't count as mixing" rule).
    """
    if step.change_type == ChangeType.NON_CODE:
        return None
    areas: dict[str, str] = {}
    for path in step.all_files:
        area = _path_area(path)
        if area is not None:
            areas.setdefault(area, path)
    if len(areas) < 2:
        return None
    return _split_rec(
        step,
        SPLIT_PREDICATE_UNRELATED_AREAS,
        title=f"Step {step.id} spans unrelated areas",
        body=(
            f"Step {step.id} \"{step.title}\" touches {len(areas)} unrelated "
            f"areas: " + ", ".join(f"`{a}`" for a in sorted(areas)) + "."
        ),
    )


def _path_area(path: str) -> Optional[str]:
    """Coarse "area" of a repo-relative path: its **top** directory segment.

    Returns ``None`` for a test-mirror path (test files aren't a distinct
    area) and for a documentation (``.md``) rider (so a code step that ships a
    companion doc isn't flagged). A package and its sub-packages collapse to
    one area: ``plan_tool/x.py`` and ``plan_tool/cli/run_cmd.py`` both →
    ``plan_tool``; ``tests/test_x.py`` and ``docs/X.md`` → ``None``.
    """
    p = PurePosixPath(path.strip())
    parts = p.parts
    if not parts:
        return None
    if parts[0] in _TEST_TOP_DIRS:
        return None
    if p.suffix == ".md":
        return None
    return parts[0]


def _split_rec(
    step: Step, predicate_key: str, *, title: str, body: str
) -> Recommendation:
    return Recommendation(
        id=_make_rec_id(
            step.id, GRANULARITY_SPLIT_SOURCE, f"split:{predicate_key}:{step.id}"
        ),
        source=GRANULARITY_SPLIT_SOURCE,
        severity=_GRANULARITY_SEV,
        step_id=step.id,
        title=title,
        body=body,
        suggested_action=f"Consider splitting step {step.id} into type-pure steps",
    )


def split_predicate_key(rec: Recommendation) -> Optional[str]:
    """Recover the stable split-predicate key for a granularity split rec.

    Deterministic split rec ids are minted from ``split:{key}:{step_id}``, so
    this helper can recover those keys without parsing human prose. Prose
    MIXED-STEP recs share the same ``granularity-split`` source but not that
    fingerprint shape; they map to ``mixed-step``. Non-split recs return
    ``None``.
    """
    if rec.source != GRANULARITY_SPLIT_SOURCE or rec.step_id is None:
        return None
    for key in DETERMINISTIC_SPLIT_PREDICATE_KEYS:
        expected = _make_rec_id(rec.step_id, GRANULARITY_SPLIT_SOURCE,
                                f"split:{key}:{rec.step_id}")
        if rec.id == expected:
            return key
    return SPLIT_PREDICATE_MIXED_STEP


# --- merge detectors (pairwise / plan-level → granularity-merge) -----------


def _merge_findings(plan: Plan) -> list[Recommendation]:
    return _merge_signal_identical_file_sets(plan) + (
        _merge_signal_trivial_refactor_feeding_one_feature(plan)
    )


def _merge_signal_identical_file_sets(plan: Plan) -> list[Recommendation]:
    """Two ``depends_on``-adjacent steps with equal, non-empty file sets."""
    by_id = {s.id: s for s in plan.steps}
    recs: list[Recommendation] = []
    for dependent in plan.steps:
        for dep_id in dependent.depends_on:
            dependency = by_id.get(dep_id)
            if dependency is None:
                continue
            files = frozenset(dependency.all_files)
            if files and files == frozenset(dependent.all_files):
                recs.append(
                    _merge_rec(
                        dependency,
                        dependent,
                        "identical-files",
                        body=(
                            f"Steps {dependency.id} and {dependent.id} are "
                            f"dependency-adjacent and touch the identical file "
                            f"set ({sorted(files)})."
                        ),
                    )
                )
    return recs


def _merge_signal_trivial_refactor_feeding_one_feature(
    plan: Plan,
) -> list[Recommendation]:
    """A small refactor step whose only dependent is exactly one feature step."""
    recs: list[Recommendation] = []
    for step in plan.steps:
        if step.change_type is not ChangeType.REFACTOR:
            continue
        if len(step.all_files) > _TRIVIAL_REFACTOR_MAX_FILES:
            continue
        dependents = [s for s in plan.steps if step.id in s.depends_on]
        if len(dependents) != 1:
            continue
        dependent = dependents[0]
        if dependent.change_type is not ChangeType.FEATURE:
            continue
        recs.append(
            _merge_rec(
                step,
                dependent,
                "trivial-refactor",
                body=(
                    f"Step {step.id} is a trivial refactor "
                    f"({len(step.all_files)} file) whose only dependent is "
                    f"feature step {dependent.id} — likely setup for that step."
                ),
            )
        )
    return recs


def _merge_rec(
    a: Step, b: Step, key: str, *, body: str
) -> Recommendation:
    lo_id, hi_id = sorted((a.id, b.id))
    # Only a *contiguous* (adjacent-id) pair can be folded: ``merge_steps``
    # requires a contiguous run and rejects a gapped set. Attach the dispatchable
    # machine marker only then, so downstream routing recovers the merge target
    # via ``review.parse_merge_action`` (fingerprint stays keyed on
    # ``merge:{key}:{lo}+{hi}``; the directive rides ``suggested_action`` only).
    # A gapped pair (e.g. a ``depends_on`` edge between non-adjacent steps) stays
    # recommend-only prose with NO marker — it routes through neutral triage
    # instead of dispatching to ``merge_bridge`` and failing with a confusing
    # "invalid", because a gap needs manual operator judgment (reorder first).
    # See the plan's out-of-scope note on gapped merge pairs.
    if hi_id == lo_id + 1:
        suggested = (
            f"Consider merging steps {lo_id} and {hi_id}. "
            + render_merge_action(MERGE_ACTION_MERGE, (lo_id, hi_id))
        )
    else:
        suggested = (
            f"Consider merging steps {lo_id} and {hi_id}, but their ids are not "
            f"adjacent — reorder them to be contiguous first, then merge by "
            f"hand; the automated merge bridge only folds a contiguous run."
        )
    return Recommendation(
        id=_make_rec_id(lo_id, GRANULARITY_MERGE_SOURCE, f"merge:{key}:{lo_id}+{hi_id}"),
        source=GRANULARITY_MERGE_SOURCE,
        severity=_GRANULARITY_SEV,
        step_id=lo_id,
        title=f"Steps {lo_id} and {hi_id} may be a single step",
        body=body,
        suggested_action=suggested,
    )


# --- prose MIXED-STEP kernel (LLM-judged step purity → granularity-split) ---

# LLM-judged step-purity (refactor-vs-feature mixing). detail-quality.md
# emits a separate ``## Structural findings`` block carrying ``MIXED-STEP:``
# bullets when a code step mixes behavior-preserving restructuring with new
# behavior. The block is kept distinct from ``## Findings`` and stripped from
# the response before the ``## Findings`` parse (see detail's
# :func:`collect_detail_quality_findings`) so a purity bullet can never leak
# into an apply-eligible ``claude`` rec — ``_STRUCTURAL_BLOCK_RE`` is
# single-sourced here and imported back by ``detail.py`` for that strip so the
# strip consumer and this parse kernel cannot drift to two copies. Both
# patterns tolerate the bold / casing models routinely add around the heading
# and the token.
_STRUCTURAL_BLOCK_RE = re.compile(
    r"^#{1,6}\s*Structural findings\s*$\n?(.*?)(?=^#{1,6}\s|\Z)",
    re.MULTILINE | re.DOTALL | re.IGNORECASE,
)
_MIXED_STEP_BULLET_RE = re.compile(
    r"^\s*[-*]\s*(?:\*\*)?MIXED-STEP(?:\*\*)?\s*[:\-]\s*(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def parse_mixed_step_findings(
    raw: str, step: Step, plan_name: str
) -> list[Recommendation]:
    """Lift ``## Structural findings`` MIXED-STEP bullets into
    ``source="granularity-split"`` recs — the one kernel for detail's purity
    check, ``detail --split`` Phase B, and the ``"detail"`` advisor stage.

    LLM-judged companion to the deterministic split detectors: the model
    applies the ``plan-audit.md`` mixed-step rule to the authored detail body,
    flagging a code step that bundles behavior-preserving restructuring with
    new behavior. The result is a *structural* finding — surfaced every
    iteration but never dispatched to ``apply_finding`` (``granularity-split``
    is absent from ``APPLY_ELIGIBLE_SOURCES``), because the remedy is splitting
    the step into a refactor-then-feature pair, not editing prose.

    These recs carry ``severity="medium"`` — deliberately higher than the
    deterministic split detectors' ``info`` default, because the prose
    MIXED-STEP judgment is a higher-confidence signal than the title/area
    heuristics. Severity does not gate apply here: ``granularity-split`` is
    structurally excluded from apply-eligibility, so both ``info`` and
    ``medium`` granularity-split recs are non-apply-eligible.

    Defensive: a ``non-code`` step is never mixed, so a bullet emitted against
    one is dropped.
    """
    if step.change_type == ChangeType.NON_CODE:
        return []
    m = _STRUCTURAL_BLOCK_RE.search(raw)
    if not m:
        return []
    out: list[Recommendation] = []
    for bm in _MIXED_STEP_BULLET_RE.finditer(m.group(1)):
        desc = bm.group(1).strip()
        if not desc:
            continue
        body = (
            f"Step {step.id} mixes behavior-preserving refactoring with new "
            f"behavior in one step: {desc} Split into type-pure steps — the "
            "make-the-change-easy refactor first, then the make-the-easy-change "
            "feature (depends_on the refactor)."
        )
        out.append(
            Recommendation(
                id=_make_rec_id(step.id, GRANULARITY_SPLIT_SOURCE, desc),
                source=GRANULARITY_SPLIT_SOURCE,
                severity="medium",
                step_id=step.id,
                title=(
                    f"Step {step.id}: mixed refactor + feature "
                    "(split recommended)"
                ),
                body=body,
                suggested_action=(
                    f"Split step {step.id} into type-pure steps: a "
                    "behavior-preserving refactor first, then the feature "
                    f"(depends_on the refactor). [{plan_name}]"
                ),
            )
        )
    return out
