"""Split-criteria catalog + legend renderer (read-only leaf).

Declares, as one catalog of frozen descriptors, every structural-split
criterion the tool already applies across its three altitudes, and renders
the plan-independent **legend** from that catalog. Each criterion is described
once as data (:class:`SplitCriterion`) so the later per-plan mode (step 3)
renders from the same catalog and never re-describes a criterion.

The criteria themselves live in — and stay owned by — the deciders
(``plan_tool/granularity.py``, ``plan_tool/distill_thresholds.py``,
``plan_tool/review.py``, ``plan_tool/launcher.py``'s ``escalate_to_split``,
``plan_tool/split_safety.py``, ``plan_tool/scope_out.py``). This module never
copies or re-implements a predicate; it references each criterion's live
threshold/lexicon by **importing the owning module's constant and
interpolating it**, so a re-typed ``3``/``0.85``/``16384`` can never drift out
of sync (``tests/test_split_criteria.py`` drift-guards each rendered value
against its imported source).

Cycle-free: imports ``granularity``, ``convergence_diagnosis`` (for its saved
report history reader only — see the per-plan evaluator below),
``distill_thresholds``, ``review``, ``review_persistence``, ``telemetry``, and
``style`` — none import back, exactly as the CLI layer sits above them. No
orchestrator (``create.py``) is imported; the distill thresholds are read from
the light ``distill_thresholds`` leaf. The per-plan evaluator records one
best-effort ``plan-criteria-breakdown`` telemetry event (step 5), but spends no
Claude and mutates no plan/code.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from plan_tool import (
    convergence_diagnosis,
    distill_thresholds,
    granularity,
    locator,
    review,
    review_persistence,
    telemetry,
)
from plan_tool.detail_artifacts import require_supported_detail_format_version
from plan_tool.review import Recommendation
from plan_tool.schema import Plan
from plan_tool.split_safety import split_is_safe

if TYPE_CHECKING:
    # Type-only: ``evaluate_split_criteria`` imports ``compute_plan_mass``
    # lazily at call time (#238's plan-mass reporting is an optional,
    # best-effort addition, not a load-bearing dependency of this module).
    from plan_tool.completeness_report import PlanMass
from plan_tool.style import BOLD, BOLD_CYAN, paint


@dataclass(frozen=True)
class SplitCriterion:
    """One structural-split criterion, described once as data.

    ``id`` is the stable slug step 3's evaluator maps detector output back to;
    where a predicate slug already exists (``granularity.SPLIT_PREDICATE_*``)
    it is reused so the two line up.
    ``altitude`` is 1 (plan too big → many plans), 2 (decompose into steps), or
    3 (conditionally split one step). ``deterministic`` is whether step 3's
    per-plan mode can evaluate the criterion without Claude. ``remedy`` names
    which structural remedy applies (``re-split`` / ``scope-out`` / ``merge`` /
    ``re-seed``). ``source`` is the ``review``/``granularity`` finding source a
    detector stamps, when one exists, so step 3 can map findings back to the id.
    """

    id: str
    altitude: int
    description: str
    advisory: bool
    deterministic: bool
    detector: str
    remedy: str
    source: Optional[str] = None


# Whether a finding source only advises (vs. driving an ``apply_finding`` edit).
# Read straight off ``review.APPLY_ELIGIBLE_SOURCES`` rather than re-deciding it:
# every split/merge source here is deliberately kept out of that set, so this is
# ``True`` for them; a sourceless criterion (distill, the convergence forks,
# split-safety) is a read-only signal, also advisory.
def _advisory(source: Optional[str]) -> bool:
    return source not in review.APPLY_ELIGIBLE_SOURCES


# The full criteria set, in altitude order. The legend shows all of these; step
# 3's per-plan evaluator fires only the ``deterministic`` ones (the altitude-1
# distill split is Claude-judged, so per-plan mode marks it "not evaluated").
SPLIT_CRITERIA: tuple[SplitCriterion, ...] = (
    # --- Altitude 1 — plan too big → split into multiple plans --------------
    SplitCriterion(
        id="distill-oversize",
        altitude=1,
        description=(
            "Inline seed size gates conventional create-time distillation; "
            "large inline seeds often describe several plans. Direct-ready "
            "file-backed sources instead receive a raw Claude-judged split "
            "assessment at every size. Per-plan mode cannot fire either "
            "route from bytes."
        ),
        advisory=_advisory(None),
        deterministic=False,
        detector="create.propose_distilled_seed_from_claude",
        remedy="re-seed",
    ),
    # --- Altitude 2 — decompose into steps ---------------------------------
    SplitCriterion(
        id=granularity.SPLIT_PREDICATE_MIXED_VERBS,
        altitude=2,
        description=(
            "A step title carrying both a refactor verb and a feature verb — "
            "likely two concerns in one step."
        ),
        advisory=_advisory(granularity.GRANULARITY_SPLIT_SOURCE),
        deterministic=True,
        detector="granularity._title_mixes_refactor_and_feature",
        remedy="re-split",
        source=granularity.GRANULARITY_SPLIT_SOURCE,
    ),
    SplitCriterion(
        id=granularity.SPLIT_PREDICATE_CONJOINED_CLAUSES,
        altitude=2,
        description=(
            "A step title joining two or more action-verb-led clauses — likely "
            "one concern per clause."
        ),
        advisory=_advisory(granularity.GRANULARITY_SPLIT_SOURCE),
        deterministic=True,
        detector="granularity._title_conjoins_clauses",
        remedy="re-split",
        source=granularity.GRANULARITY_SPLIT_SOURCE,
    ),
    SplitCriterion(
        id=granularity.SPLIT_PREDICATE_UNRELATED_AREAS,
        altitude=2,
        description=(
            "A code step whose files span two or more unrelated top-level "
            "areas. Control-flow rule (test mirrors and doc riders fold out of "
            "the count) — unpinned; no single backing constant."
        ),
        advisory=_advisory(granularity.GRANULARITY_SPLIT_SOURCE),
        deterministic=True,
        detector="granularity._step_spans_unrelated_areas",
        remedy="re-split",
        source=granularity.GRANULARITY_SPLIT_SOURCE,
    ),
    SplitCriterion(
        id="merge",
        altitude=2,
        description=(
            "Two dependency-adjacent steps with identical file sets, or a "
            "trivial refactor feeding exactly one feature step — likely one "
            "step. The inverse signal: merge / re-ground rather than split."
        ),
        advisory=_advisory(granularity.GRANULARITY_MERGE_SOURCE),
        deterministic=True,
        detector="granularity._merge_findings",
        remedy="merge",
        source=granularity.GRANULARITY_MERGE_SOURCE,
    ),
    SplitCriterion(
        id=granularity.SPLIT_PREDICATE_MIXED_STEP,
        altitude=2,
        description=(
            "A code step whose authored detail mixes behavior-preserving "
            "refactoring with new behavior, lifted from the "
            "'## Structural findings' block. Regex-parsed from prose — "
            "unpinned; no backing constant."
        ),
        advisory=_advisory(granularity.GRANULARITY_SPLIT_SOURCE),
        deterministic=True,
        detector="granularity.parse_mixed_step_findings",
        remedy="re-split",
        source=granularity.GRANULARITY_SPLIT_SOURCE,
    ),
    # --- Altitude 3 — conditionally split one step -------------------------
    SplitCriterion(
        id="split-safe",
        altitude=3,
        description=(
            "Run-state gate: can this step be re-split in place right now? "
            "False when a DONE step at or after it carries id-keyed run state a "
            "renumber would orphan (a CURRENT step is 'next runnable', not run, "
            "so it splits cleanly). Not a shape defect — a partly-run plan can "
            "be un-splittable. Control-flow rule — unpinned; computable without "
            "Claude, no single constant."
        ),
        advisory=_advisory(None),
        deterministic=True,
        detector="split_safety.split_is_safe",
        remedy="re-split",
    ),
    SplitCriterion(
        id="scope-out-blocked",
        altitude=3,
        description=(
            "Run-state gate: would carving this step out at plan scope be "
            "refused right now? True when scope-out's graph blockers "
            "(inbound-dependent / downstream-orphan / non-canonical-numbering) "
            "fire — read from the same gate scope_out_step consults. Control-flow "
            "rule — unpinned; computable without Claude, no single constant."
        ),
        advisory=_advisory(None),
        deterministic=True,
        detector="scope_out.compute_narrow",
        remedy="scope-out",
    ),
)


# Altitude headers, matching the plan's three-altitude framing.
_ALTITUDE_HEADERS: dict[int, str] = {
    1: "plan too big → split into multiple plans",
    2: "decompose into steps",
    3: "conditionally split one step",
}

# The remedy vocabulary as one split/merge axis parameterized by altitude (a
# step vs the plan's scope) and disposition of the carved side (kept as a
# sibling step vs carved to a forward-seed) — CLAUDE-doc "Structural remedy
# vocabulary". Kept beside the ``remedy`` field so a remedy is described once.
_REMEDY_VOCABULARY: tuple[tuple[str, str], ...] = (
    ("re-split", "step-altitude split, both halves kept as sibling steps"),
    ("scope-out", "plan-scope split, carved side deferred to a forward-seed"),
    ("merge", "the inverse of split — merge / re-ground adjacent or already-built steps"),
    ("re-seed", "the limit — split everything and re-decompose from a fresh seed"),
)


def _reference_lines() -> dict[str, str]:
    """The drift-guarded reference suffix for each data-backed criterion.

    Every numeric/lexical value is read from its owning module's constant and
    interpolated — never re-typed here. Criteria whose rule is control-flow
    (multi-area, mixed-step, the split-safe / scope-out-blocked run-state
    gates) have no entry and render as prose only.
    """
    refactor_verbs = ", ".join(sorted(granularity._REFACTOR_VERBS))
    feature_verbs = ", ".join(sorted(granularity._FEATURE_VERBS))
    test_dirs = ", ".join(sorted(granularity._TEST_TOP_DIRS))
    return {
        "distill-oversize": (
            f"inline only: skip distillation below "
            f"{distill_thresholds.DISTILL_SKIP_BELOW_BYTES} bytes; advise "
            f"conventional preparation above "
            f"{distill_thresholds.DISTILL_ADVISE_ABOVE_BYTES} bytes; "
            "file-backed direct sources assess raw text at every size"
        ),
        granularity.SPLIT_PREDICATE_MIXED_VERBS: (
            f"refactor verbs: {refactor_verbs}; feature verbs: {feature_verbs}"
        ),
        granularity.SPLIT_PREDICATE_CONJOINED_CLAUSES: (
            "clauses split on ' and ' / ';' / ',', each led by an action verb "
            "(the refactor + feature verbs above)"
        ),
        granularity.SPLIT_PREDICATE_UNRELATED_AREAS: (
            f"top-level source areas; test dirs ({test_dirs}) and .md doc "
            "riders fold out of the count"
        ),
        "merge": (
            f"trivial refactor = {granularity._TRIVIAL_REFACTOR_MAX_FILES} "
            "file or fewer feeding one feature step"
        ),
    }


def render_split_criteria(*, color: bool = False) -> str:
    """Render the full, plan-independent split-criteria legend.

    Takes no plan and returns the legend as a string; the CLI handler (step 6)
    is the only caller that prints it, passing ``color=style.color_enabled(...)``
    so the legend is colored on a TTY and plain when piped. Pure — builds a
    ``list[str]`` and joins it, the same shape as
    ``convergence_diagnosis.render_diagnosis``. Spends no Claude, mutates
    nothing.
    """
    references = _reference_lines()
    lines: list[str] = [
        paint("Split-criteria legend", BOLD_CYAN, enabled=color),
        "The tool decides how to split work at three altitudes; each criterion",
        "below is one structural-split signal it already applies.",
        "",
    ]
    for altitude, header in _ALTITUDE_HEADERS.items():
        lines.append(paint(f"Altitude {altitude} — {header}", BOLD, enabled=color))
        for criterion in SPLIT_CRITERIA:
            if criterion.altitude != altitude:
                continue
            lines.append(f"  • {criterion.id} [{criterion.remedy}]: {criterion.description}")
            reference = references.get(criterion.id)
            if reference:
                lines.append(f"      {reference}")
        lines.append("")
    lines.append(paint("Structural remedies (altitude × disposition)", BOLD, enabled=color))
    for name, description in _REMEDY_VOCABULARY:
        lines.append(f"  • {name} — {description}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Per-plan evaluator (steps 3-4)
#
# Orchestrates the tool's *existing* deterministic split detectors against one
# plan and maps each result back to a catalog id — it writes no new detection
# logic. Every detector is called with ``invoker=None``: altitude 2 runs the
# ``granularity`` split/merge battery (including the regex-lifted prose
# MIXED-STEP findings), and altitude 1 surfaces the ``distill_thresholds``
# values as reference only (the distill split is Claude-judged on the seed).
# The two altitude-3 split-safety run-state gates reuse
# ``split_safety.split_is_safe`` and ``scope_out.compute_narrow`` (step 4).
# Step 5 wraps the body in a read-history → diff → record cycle: it reads
# prior telemetry *before* recording (so the drift diff never sees this run's
# own event), diffs the fires? results against the last recorded breakdown
# with a different plan fingerprint, and records this run's breakdown through
# step 1's recorder. No Claude, no plan/code mutation.
# --------------------------------------------------------------------------- #


# The two run-state split-safety criteria are surfaced as per-step gates (a
# separate ``SplitSafetyGate`` structure rendered "splittable now?"), not as
# ``CriterionResult`` fires? rows — so the fires? loop skips these ids.
_GATE_CRITERION_IDS: frozenset[str] = frozenset({"split-safe", "scope-out-blocked"})

# Severity ordering spanning the granularity ``info``/``medium``/``high``/
# ``critical`` bands, so a criterion's surfaced severity is the worst of its
# driving findings.
_SEVERITY_ORDER: dict[str, int] = {"info": 0, "medium": 1, "high": 2, "critical": 3}

_CATALOG_IDS: frozenset[str] = frozenset(c.id for c in SPLIT_CRITERIA)


@dataclass(frozen=True)
class CriterionResult:
    """One catalog criterion evaluated against a single plan.

    ``criterion_id`` / ``altitude`` echo the matching :class:`SplitCriterion`.
    ``fired`` is whether the criterion tripped; ``evaluated`` is ``False`` only
    for the Claude-judged altitude-1 distill row (it carries reference
    thresholds, not a live result). ``severity`` / ``step_ids`` come from the
    driving findings; ``reason`` is the one-line, plan-specific explanation.
    In-memory only — never serialized here.
    """

    criterion_id: str
    altitude: int
    fired: bool
    evaluated: bool
    severity: Optional[str]
    step_ids: tuple[int, ...]
    reason: str


@dataclass(frozen=True)
class SplitSafetyGate:
    """One step's run-state split-safety, as two independent signals.

    ``split_safe`` answers "can this step be re-split in place right now?"
    (``split_safety.split_is_safe``); ``scope_out_blocked`` answers "would
    carving it out at plan scope be refused right now?"
    (``scope_out.compute_narrow``'s blocker list). They read different graph
    conditions and can disagree — a step with an inbound dependent but no
    started downstream work is ``split_safe`` yet ``scope_out_blocked``. A
    run-state gate, not a fires?-style shape defect, so it is carried apart from
    the ``CriterionResult`` rows (step 5 excludes it from the drift diff — its
    input is run state, which the plan fingerprint does not hash). In-memory
    only — never serialized here.
    """

    step_id: int
    split_safe: bool
    split_blocking: tuple[int, ...]
    scope_out_blocked: bool
    scope_out_blocker_kinds: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class CriteriaDrift:
    """How this plan's fires? evaluation moved since it last looked structurally
    different.

    ``has_prior`` is whether a recorded breakdown with a *different*
    ``plan_fingerprint`` was found to diff against; ``prior_fingerprint`` /
    ``current_fingerprint`` are the two plan digests. ``newly_firing`` /
    ``stopped_firing`` / ``severity_changed`` are the criterion ids that started
    firing, stopped firing, or changed severity between the two evaluations;
    ``changed`` is their disjunction — the render gate (a reshaped plan whose
    criteria evaluate identically is not drift). The diff covers only the
    ``CriterionResult`` fires? rows, never the run-state split-safety gates
    (``compute_plan_fingerprint`` does not hash run state, so a fingerprint change
    can never reflect a gate change). In-memory only — never serialized."""

    has_prior: bool
    prior_fingerprint: Optional[str]
    current_fingerprint: str
    newly_firing: tuple[str, ...]
    stopped_firing: tuple[str, ...]
    severity_changed: tuple[str, ...]
    changed: bool


@dataclass(frozen=True)
class PlanCriteriaBreakdown:
    """A plan's evaluation: one :class:`CriterionResult` per fires?-style catalog
    criterion, plus one :class:`SplitSafetyGate` per step for the two run-state
    split-safety signals, plus the :class:`CriteriaDrift` diff against the plan's
    last structurally-different recorded evaluation. In-memory only — step 5
    serializes a *primitive* projection of ``results`` (not the gates, not the
    drift, not this dataclass) into telemetry, so the persisted-schema contract
    is untouched here."""

    plan_slug: str
    results: tuple[CriterionResult, ...]
    gates: tuple[SplitSafetyGate, ...]
    drift: Optional[CriteriaDrift] = None


def evaluate_split_criteria(
    plan: Plan, *, plan_path: Path, repo_root: Optional[Path] = None
) -> PlanCriteriaBreakdown:
    """Evaluate ``plan`` against every deterministically-evaluable split
    criterion and return the per-criterion breakdown plus the run-state gates.

    Pure orchestration + mapping over the existing detectors — no new detection,
    no Claude (``invoker=None`` everywhere), no mutation. Altitude 2 runs
    ``granularity.assess_granularity`` at ``stage="detail"`` (deterministic
    split/merge + regex-lifted prose MIXED-STEP findings); altitude 1 surfaces
    the distill thresholds as reference only. The two run-state split-safety
    signals (``split-safe`` / ``scope-out-blocked``) are computed per step into
    ``gates`` — reusing the actuators' own gates, never re-implementing them.
    ``repo_root`` is used to resolve the carve preview's detail files (never to
    decide blockers) and as the telemetry root; when omitted it is
    best-effort-resolved from ``plan_path``.

    Step 5 wraps this in a read → diff → record cycle: prior telemetry is read
    *before* recording so the drift diff can never see this run's own event, the
    fires? results are diffed against the last recorded breakdown with a
    different plan fingerprint, and this run's breakdown is recorded through the
    best-effort recorder (a telemetry failure never changes this return value).
    """
    resolved_repo_root = repo_root if repo_root is not None else _repo_root_for(plan_path)

    history = convergence_diagnosis.load_report_history(plan_path)
    slug = history.plan_slug

    bodies = _read_detail_bodies(plan, plan_path, slug)
    granularity_hits = _evaluate_granularity(plan, bodies)

    # #238: re-reads the detail bundle ``bodies`` already read a few lines
    # above (``compute_plan_mass`` has its own committed-steps-only read via
    # ``derive_detail_path``, not the glob-based ``_read_detail_bodies``
    # above) — a deliberate, deferred optimization, not an oversight: this
    # is a manual, non-hot-path inspection command (no Claude, no network),
    # and threading a pre-read bodies dict through ``compute_plan_mass``'s
    # public contract for every caller is not proportionate to the cost of
    # one extra local markdown read here. ``compute_plan_mass_best_effort``
    # is the shared failure policy — see its docstring — not a local
    # try/except, so this stays the one place that policy lives. Lazy
    # import — see the ``TYPE_CHECKING`` note above for why this stays
    # call-time rather than module-level.
    from plan_tool.completeness_report import compute_plan_mass_best_effort

    plan_mass = compute_plan_mass_best_effort(plan, plan_path, resolved_repo_root)

    results: list[CriterionResult] = []
    for criterion in SPLIT_CRITERIA:
        if criterion.id in _GATE_CRITERION_IDS:
            continue  # a run-state gate, carried in ``gates`` not ``results``
        if criterion.altitude == 1:
            results.append(_altitude1_result(criterion, plan_mass))
        else:  # altitude == 2 — every altitude-3 criterion is a gate, above
            results.append(_altitude2_result(criterion, granularity_hits))

    gates = _evaluate_split_safety_gates(plan, plan_path, resolved_repo_root)

    # Read history → diff → record, in that order (step 5). Reading prior
    # telemetry before the record keeps the diff independent of write timing.
    plan_fingerprint = review_persistence.compute_plan_fingerprint(plan_path)
    prior_events = telemetry.read_decisions(resolved_repo_root)
    drift = compute_criteria_drift(
        prior_events,
        current_results=results,
        current_fingerprint=plan_fingerprint,
        plan_slug=slug,
    )
    _record_breakdown(
        resolved_repo_root,
        plan_slug=slug,
        plan_fingerprint=plan_fingerprint,
        results=results,
        history=history,
    )
    return PlanCriteriaBreakdown(
        plan_slug=slug, results=tuple(results), gates=gates, drift=drift
    )


def _result_to_primitive(result: CriterionResult) -> dict:
    """Project one fires? :class:`CriterionResult` to JSON primitives for the
    recorder.

    ``telemetry`` is a stdlib-only leaf that stores only primitives, so the
    dataclass is flattened to ``id``/``fired``/``severity``/``step_ids`` here —
    never handed the ``CriterionResult`` object. ``step_ids`` are stringified per
    the DATA_CONTRACT ``plan-criteria-breakdown`` row shape (matching
    ``split_step_ids``). This is also the shape the drift diff reads back from a
    prior recorded event, so the two stay in lockstep.
    """
    return {
        "id": result.criterion_id,
        "fired": result.fired,
        "severity": result.severity,
        "step_ids": [str(s) for s in result.step_ids],
    }


def _record_breakdown(
    repo_root: Path,
    *,
    plan_slug: str,
    plan_fingerprint: str,
    results: list[CriterionResult],
    history: convergence_diagnosis.ReportHistory,
) -> None:
    """Record this run's breakdown through step 1's best-effort recorder.

    The evaluator is the recorder site (the CLI handler must not record, or it
    double-counts). Only the fires? ``results`` are recorded — never the
    run-state gates, which the plan fingerprint does not hash. The code
    fingerprint is *borrowed* from the newest saved run rather than computed
    (leaf posture): keyed on that run's ``code_fingerprint_present`` bool, it is
    passed when the run computed one and omitted otherwise (including an empty
    history). ``record_plan_criteria_breakdown`` swallows every error, so no
    try/except is needed here.
    """
    code_fingerprint: Optional[dict[str, str]] = None
    if history.runs:
        newest = history.runs[-1]
        if newest.code_fingerprint_present:
            code_fingerprint = newest.code_fingerprint
    telemetry.record_plan_criteria_breakdown(
        repo_root,
        plan_slug=plan_slug,
        plan_fingerprint=plan_fingerprint,
        criteria=[_result_to_primitive(r) for r in results],
        code_fingerprint=code_fingerprint,
    )


def compute_criteria_drift(
    prior_events: list[telemetry.DecisionEvent],
    *,
    current_results: list[CriterionResult],
    current_fingerprint: str,
    plan_slug: str,
) -> CriteriaDrift:
    """Diff the current fires? results against the last recorded breakdown with a
    *different* plan fingerprint.

    Keeps only ``plan-criteria-breakdown`` events for this ``plan_slug`` and walks
    them newest-to-oldest (``decisions.jsonl`` append order is chronological),
    picking the first whose recorded ``plan_fingerprint`` differs from
    ``current_fingerprint`` — the last time the plan looked structurally
    different. With no such event there is nothing to diff (``has_prior=False``).
    The diff keys on criterion ``id``: ids that fire now but didn't
    (``newly_firing``), ids that stopped (``stopped_firing``), and ids firing in
    both whose severity moved (``severity_changed``). It reads the prior event's
    primitive ``criteria`` rows — the same projection :func:`_result_to_primitive`
    records — and never touches run-state gates (they are not in ``results``).
    """
    prior = _last_different_fingerprint_event(
        prior_events, current_fingerprint=current_fingerprint, plan_slug=plan_slug
    )
    if prior is None:
        return CriteriaDrift(
            has_prior=False,
            prior_fingerprint=None,
            current_fingerprint=current_fingerprint,
            newly_firing=(),
            stopped_firing=(),
            severity_changed=(),
            changed=False,
        )

    prior_rows = prior.context.get("criteria", [])
    prior_fired = {
        str(row.get("id")): bool(row.get("fired")) for row in prior_rows
    }
    prior_severity = {
        str(row.get("id")): row.get("severity") for row in prior_rows
    }
    current_fired = {r.criterion_id: r.fired for r in current_results}
    current_severity = {r.criterion_id: r.severity for r in current_results}

    newly_firing = tuple(
        sorted(
            cid
            for cid, fired in current_fired.items()
            if fired and not prior_fired.get(cid, False)
        )
    )
    stopped_firing = tuple(
        sorted(
            cid
            for cid, fired in prior_fired.items()
            if fired and not current_fired.get(cid, False)
        )
    )
    severity_changed = tuple(
        sorted(
            cid
            for cid, fired in current_fired.items()
            if fired
            and prior_fired.get(cid, False)
            and current_severity.get(cid) != prior_severity.get(cid)
        )
    )
    changed = bool(newly_firing or stopped_firing or severity_changed)
    return CriteriaDrift(
        has_prior=True,
        prior_fingerprint=str(prior.context.get("plan_fingerprint", "")),
        current_fingerprint=current_fingerprint,
        newly_firing=newly_firing,
        stopped_firing=stopped_firing,
        severity_changed=severity_changed,
        changed=changed,
    )


def _last_different_fingerprint_event(
    events: list[telemetry.DecisionEvent],
    *,
    current_fingerprint: str,
    plan_slug: str,
) -> Optional[telemetry.DecisionEvent]:
    """The newest ``plan-criteria-breakdown`` event for ``plan_slug`` whose
    recorded ``plan_fingerprint`` differs from ``current_fingerprint``, or
    ``None``."""
    for event in reversed(events):
        if event.kind != telemetry.PLAN_CRITERIA_BREAKDOWN_KIND:
            continue
        if event.plan_slug != plan_slug:
            continue
        if str(event.context.get("plan_fingerprint", "")) != current_fingerprint:
            return event
    return None


def _repo_root_for(plan_path: Path) -> Path:
    """Best-effort repo root for the split-safety gate when the caller omits it.

    ``compute_narrow`` reads ``repo_root`` only to resolve detail files (never to
    decide blockers), so a best-effort value is safe for this read-only gate; the
    CLI handler (step 6) passes the resolved context repo root explicitly.
    """
    try:
        return locator.find_repo_root_from_cwd(plan_path.parent)
    except (FileNotFoundError, OSError):
        return plan_path.parent


def _evaluate_split_safety_gates(
    plan: Plan, plan_path: Path, repo_root: Path
) -> tuple[SplitSafetyGate, ...]:
    """Per-step run-state split-safety, reusing the actuators' own gates.

    ``split-safe`` reads ``split_safety.split_is_safe`` (a ``schema``-only leaf,
    imported at module top); ``scope-out-blocked`` reads
    ``scope_out.compute_narrow``'s blocker list — ``scope_out`` imports the
    ``detail`` orchestrator, so it is imported **inside** this body to keep the
    catalog/legend reachable without dragging the orchestrator layer in. Neither
    decider takes an invoker — no Claude — and ``compute_narrow`` mutates
    nothing. The frontmatter hash is provenance for the (never-called-here)
    apply, so a missing plan file falls back to an empty hash.
    """
    from plan_tool.parser import ParseError
    from plan_tool.scope_out import compute_frontmatter_hash, compute_narrow

    # Provenance for a never-called-here apply, so any unusable plan file — absent
    # (OSError) or lacking a frontmatter fence (ParseError) — falls back to "".
    try:
        source_frontmatter_hash = compute_frontmatter_hash(plan_path)
    except (OSError, ParseError):
        source_frontmatter_hash = ""

    gates: list[SplitSafetyGate] = []
    for step in plan.steps:
        split_safe, split_blocking = split_is_safe(plan, step.id)
        preview = compute_narrow(
            plan,
            carved_id=step.id,
            plan_path=plan_path,
            repo_root=repo_root,
            source_frontmatter_hash=source_frontmatter_hash,
        )
        blocker_kinds = tuple(b.kind for b in preview.blockers)
        scope_out_blocked = bool(preview.blockers)
        gates.append(
            SplitSafetyGate(
                step_id=step.id,
                split_safe=split_safe,
                split_blocking=tuple(split_blocking),
                scope_out_blocked=scope_out_blocked,
                scope_out_blocker_kinds=blocker_kinds,
                reason=_gate_reason(
                    split_safe, split_blocking, scope_out_blocked, blocker_kinds
                ),
            )
        )
    return tuple(gates)


def _gate_reason(
    split_safe: bool,
    split_blocking: list[int],
    scope_out_blocked: bool,
    blocker_kinds: tuple[str, ...],
) -> str:
    """The one-line, plan-specific reason for a step's two run-state signals.

    Uses run-state-gate wording ("splittable now?" / "can't split now" /
    "scope-out blocked") — never the fires? "a shape defect is present" phrasing.
    """
    if split_safe:
        split_part = "splittable now — no started or finished step at or after it"
    else:
        split_part = (
            "can't split now — started/finished downstream step(s) "
            f"{list(split_blocking)} block renumbering"
        )
    if not scope_out_blocked:
        scope_part = "scope-out clear — carve would renumber cleanly"
    else:
        scope_part = "scope-out blocked — " + ", ".join(blocker_kinds)
    return f"{split_part}; {scope_part}"


def _read_detail_bodies(plan: Plan, plan_path: Path, slug: str) -> dict[int, str]:
    """Read each step's canonical detail file, keyed by ``step.id``.

    Re-derives the bundle path locally
    (``<plan_path.parent>/plan-details/<slug>/<NN>-*.md``) rather than importing
    ``detail.py`` — mirroring how ``review_persistence.compute_plan_fingerprint``
    avoids pulling a heavy orchestrator into this leaf. A missing or unreadable
    detail file contributes nothing (no MIXED-STEP findings). A present,
    readable detail with an unsupported format version refuses the diagnostic
    rather than producing a partial criterion report.
    """
    bundle_dir = plan_path.parent / "plan-details" / slug
    bodies: dict[int, str] = {}
    for step in plan.steps:
        matches = sorted(bundle_dir.glob(f"{step.id:02d}-*.md"))
        if not matches:
            continue
        try:
            body = matches[0].read_text(encoding="utf-8")
        except OSError:
            continue
        require_supported_detail_format_version(body, path=matches[0])
        bodies[step.id] = body
    return bodies


def _evaluate_granularity(
    plan: Plan, bodies: dict[int, str]
) -> dict[str, list[Recommendation]]:
    """Run the altitude-2 granularity battery and group each rec under its
    catalog id.

    Every rec maps to a known catalog id (the split-predicate keys and the merge
    id are the catalog ids themselves); a rec landing on an unknown id is a
    mapping bug, so this asserts exhaustiveness rather than silently dropping it.
    """
    recs = granularity.assess_granularity(
        plan,
        stage="detail",
        evidence=granularity.GranularityEvidence(detail_bodies=bodies),
        invoker=None,
    )
    hits: dict[str, list[Recommendation]] = {}
    for rec in recs:
        criterion_id = _granularity_criterion_id(rec)
        assert criterion_id in _CATALOG_IDS, (
            f"granularity rec {rec.id!r} mapped to unknown criterion "
            f"{criterion_id!r}"
        )
        hits.setdefault(criterion_id, []).append(rec)
    return hits


def _granularity_criterion_id(rec: Recommendation) -> str:
    """Map one granularity rec to its catalog id by predicate key.

    A merge rec → the ``merge`` criterion. A split rec →
    ``granularity.split_predicate_key`` (one of ``mixed-verbs`` / ``two-clauses``
    / ``multi-area`` for the deterministic predicates, or ``mixed-step`` for a
    prose rec) — that key *is* the catalog id. The key is never re-derived off
    ``rec.id`` here; the helper re-hashes the candidate keys.
    """
    if rec.source == granularity.GRANULARITY_MERGE_SOURCE:
        return "merge"
    key = granularity.split_predicate_key(rec)
    # A split-source rec with a step id always resolves to a key; the outer
    # source guard in ``assess_granularity`` never emits a keyless split rec.
    assert key is not None, f"split rec {rec.id!r} has no predicate key"
    return key


def _altitude1_result(
    criterion: SplitCriterion, plan_mass: Optional["PlanMass"] = None
) -> CriterionResult:
    """The altitude-1 distill row: not evaluated (Claude-judged on the seed).

    Names the two inline-distill thresholds as reference values — direct-ready
    file-backed sources do not use them. It never compares the authored plan
    file's bytes against them (an authored plan's bytes are not the inline seed
    the threshold judges). ``plan_mass`` (#238),
    when supplied, appends the *current* plan's structural-mass numbers to the
    reason as informational context — everything a plan can grow into after
    create time that altitude 1 has otherwise had no way to see. Citing them
    does not evaluate the criterion (``evaluated`` stays ``False``: this is
    still not a live comparison against a threshold) and derives no
    threshold/gate/warning from them, per BACKLOG #238's scope fence.
    """
    reason = (
        "direct file-backed split is Claude-judged on raw source at every "
        "size; inline-distill reference thresholds: skip below "
        f"{distill_thresholds.DISTILL_SKIP_BELOW_BYTES} bytes, advise "
        f"conventional preparation above {distill_thresholds.DISTILL_ADVISE_ABOVE_BYTES} "
        "bytes"
    )
    if plan_mass is not None:
        reason += (
            f"; current plan: {plan_mass.step_count} committed step(s), "
            f"{plan_mass.detail_bundle_bytes} detail-bundle byte(s) "
            "(informational only — not compared against the seed "
            "thresholds above, which judge the seed, not the authored plan)"
        )
    return CriterionResult(
        criterion_id=criterion.id,
        altitude=1,
        fired=False,
        evaluated=False,
        severity=None,
        step_ids=(),
        reason=reason,
    )


def _altitude2_result(
    criterion: SplitCriterion, hits: dict[str, list[Recommendation]]
) -> CriterionResult:
    """An altitude-2 granularity criterion, fired iff a rec mapped to its id."""
    recs = hits.get(criterion.id, [])
    if not recs:
        return CriterionResult(
            criterion_id=criterion.id,
            altitude=2,
            fired=False,
            evaluated=True,
            severity=None,
            step_ids=(),
            reason="no step trips this predicate",
        )
    step_ids = tuple(sorted({r.step_id for r in recs if r.step_id is not None}))
    severity = max(
        (r.severity for r in recs),
        key=lambda s: _SEVERITY_ORDER.get(s.lower(), 0),
    )
    return CriterionResult(
        criterion_id=criterion.id,
        altitude=2,
        fired=True,
        evaluated=True,
        severity=severity,
        step_ids=step_ids,
        reason=recs[0].title,
    )


def render_plan_breakdown(breakdown: PlanCriteriaBreakdown, *, color: bool = False) -> str:
    """Render a per-plan breakdown: per criterion, fires?/steps/severity/reason.

    Pure — builds a ``list[str]`` and joins it, the same shape as
    ``render_split_criteria`` and ``convergence_diagnosis.render_diagnosis``.
    Colored via ``style`` when ``color=True``, plain (no ANSI) when ``False``.
    Spends no Claude, mutates nothing.
    """
    lines: list[str] = [
        paint(f"Split criteria — {breakdown.plan_slug}", BOLD_CYAN, enabled=color),
        "Per-criterion evaluation of why this plan is shaped the way it is.",
        "",
    ]
    for altitude, header in _ALTITUDE_HEADERS.items():
        lines.append(paint(f"Altitude {altitude} — {header}", BOLD, enabled=color))
        for result in breakdown.results:
            if result.altitude != altitude:
                continue
            lines.append(_render_result_line(result))
        lines.append("")
    lines.append(paint("Run-state gates (splittable now?)", BOLD, enabled=color))
    lines.append(
        "Whether each step's structural remedies are reachable right now given "
        "the plan's run state — not a shape defect."
    )
    for gate in breakdown.gates:
        lines.append(_render_gate_line(gate))
    lines.extend(_render_drift_lines(breakdown.drift, color=color))
    return "\n".join(lines).rstrip("\n")


def _render_drift_lines(drift: Optional[CriteriaDrift], *, color: bool) -> list[str]:
    """The drift note, shown only when the plan was reshaped *and* its fires?
    results changed.

    A reshaped plan whose criteria evaluate identically is not drift (``changed``
    is ``False``), so no note renders. Each non-empty id set gets its own line;
    the note reads off the same "why is this plan shaped this way?" surface as the
    breakdown above it. Plain (no ANSI) when ``color`` is off.
    """
    if drift is None or not drift.changed:
        return []
    lines = [
        "",
        paint("Decomposition drift (since last different plan shape)", BOLD, enabled=color),
        "The plan was re-decomposed and its split-criteria evaluation changed.",
    ]
    if drift.newly_firing:
        lines.append(f"  • newly firing: {', '.join(drift.newly_firing)}")
    if drift.stopped_firing:
        lines.append(f"  • stopped firing: {', '.join(drift.stopped_firing)}")
    if drift.severity_changed:
        lines.append(f"  • severity changed: {', '.join(drift.severity_changed)}")
    return lines


def _render_result_line(result: CriterionResult) -> str:
    """One breakdown line: ``• <id>: <status>; [steps …; severity …;] <reason>``."""
    if not result.evaluated:
        status = "not evaluated (Claude-judged)"
    elif result.fired:
        status = "fires"
    else:
        status = "does not fire"
    parts = [status]
    if result.fired and result.step_ids:
        parts.append(f"steps {list(result.step_ids)}")
    if result.severity:
        parts.append(f"severity {result.severity}")
    parts.append(result.reason)
    return f"  • {result.criterion_id}: " + "; ".join(parts)


def _render_gate_line(gate: SplitSafetyGate) -> str:
    """One run-state gate line: ``• step N: <split signal>; <scope-out signal>``."""
    return f"  • step {gate.step_id}: {gate.reason}"
