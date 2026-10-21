"""Resolve recorded telemetry decisions into outcome verdicts.

This leaf resolves both self-recorded results and later effects joined from
run logs and saved report history.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from plan_tool.review import Recommendation

from plan_tool import convergence_diagnosis, locator, review_persistence, run_log
from plan_tool.telemetry import (
    APPLY_VERDICT_INVOCATION_FAILED,
    APPLY_VERDICT_KIND,
    CREATE_ACTION_ACCEPT,
    CREATE_ACTION_OVERRIDE,
    CREATE_ACTION_SPLIT_APPLIED,
    CREATE_ACTION_SPLIT_ERROR,
    CREATE_ACTION_SPLIT_INVALID,
    CREATE_ACTION_SPLIT_REQUESTED,
    CREATE_ACTION_SPLIT_UNUSABLE,
    CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
    CREATE_ACTION_UNCLASSIFIED_CLASSIFIED,
    CREATE_DECISION_STEP_OUTCOME,
    ESCALATE_SPLIT_KIND,
    DecisionEvent,
    read_decisions,
)


OUTCOME_ACTED_ON = "acted-on"
OUTCOME_NO_OP = "no-op"
OUTCOME_REVERTED = "reverted"
OUTCOME_STILL_OPEN = "still-open"

RESOLUTION_INLINE = "inline"
RESOLUTION_ASYNC = "async"
RESOLUTION_UNRESOLVED = "unresolved"

MIN_SAMPLE_FOR_RECOMMENDATION = 10
HIGH_NO_OP_RATE = 0.6
REVERTED_RATE_FLAG = 0.2
LOW_COVERAGE_RATE = 0.7

FINDING_DRIFT_INSUFFICIENT_EVIDENCE = "insufficient-evidence"
FINDING_DRIFT_EVIDENCE_SUFFICIENT = "evidence-sufficient"
LOW_IMPACT_DEMOTION_MIN_RESOLVED = 10
LOW_IMPACT_DEMOTION_MAX_CONFIRMED_RATE = 0.10
_CALIBRATION_ORIGIN_KINDS = frozenset({"completeness", "detail-reconcile"})
_CALIBRATION_SCOPE_TOKENS = ("seam", "boundary", "cross-step", "contract")
_PURITY_FINDING_SOURCE = "granularity-split"
_INELIGIBLE_PURITY_PROVENANCE = frozenset({"unknown", "legacy"})


@dataclass(frozen=True)
class ResolvedDecision:
    """One decision paired with its current outcome verdict and evidence."""

    decision_id: str
    kind: str
    decision: str
    plan_slug: str
    outcome: str
    resolution: str
    evidence: str


@dataclass(frozen=True)
class DecisionAggregate:
    """Outcome and resolution totals for one telemetry signal."""

    kind: str
    decision: str
    total: int
    plan_count: int
    acted_on: int
    no_op: int
    reverted: int
    still_open: int
    resolved: int
    unresolved: int


@dataclass(frozen=True)
class TuningRecommendation:
    """An advisory note about one telemetry signal's calibration."""

    kind: str
    decision: str
    category: str
    message: str


@dataclass(frozen=True)
class TelemetryAnalysis:
    """A deterministic summary of all recorded telemetry decisions."""

    total_events: int
    aggregates: tuple[DecisionAggregate, ...]
    recommendations: tuple[TuningRecommendation, ...]
    calibration: Optional["FindingDriftAnalysis"] = None


@dataclass(frozen=True, order=True)
class FindingClass:
    """Stable persisted-field identity for one audit-finding cohort.

    ``purity_verdict_provenance`` is populated only for purity verdicts, so
    ordinary audit findings are never accidentally assigned a purity cohort.
    """

    source: str
    anchor_category: str
    scope_shape: str
    purity_verdict_provenance: Optional[str] = None


@dataclass(frozen=True)
class FindingClassDriftSignal:
    """Read-only observed outcomes for one :class:`FindingClass`."""

    finding_class: FindingClass
    total: int
    confirmed: int
    cleared: int
    unresolved: int
    confirmed_rate: Optional[float]
    evidence_state: str


@dataclass(frozen=True)
class FindingDriftAnalysis:
    """Deterministic calibration evidence derived from saved audit reports."""

    total_findings: int
    signals: tuple[FindingClassDriftSignal, ...]


@dataclass(frozen=True)
class LowImpactDemotionLookup:
    """Immutable, operation-scoped calibration rule for live recommendations."""

    qualifying_finding_classes: frozenset[FindingClass]

    def __call__(self, recommendation: "Recommendation") -> bool:
        """Return whether this low-impact medium recommendation is demotable."""
        if recommendation.impact != "low" or recommendation.severity != "medium":
            return False
        return (
            classify_calibration_recommendation(recommendation)
            in self.qualifying_finding_classes
        )


def _anchor_category(anchor: Optional[str]) -> str:
    if convergence_diagnosis._step_token(anchor) is not None:
        return "step"
    if anchor and anchor.strip():
        return "anchored"
    return "unanchored"


def _scope_shape(anchor: Optional[str], title: str) -> str:
    persisted_text = f"{anchor or ''} {title or ''}".lower()
    if any(token in persisted_text for token in _CALIBRATION_SCOPE_TOKENS):
        return "cross-boundary"
    if convergence_diagnosis._step_token(anchor) is not None:
        return "step-detail"
    if anchor and anchor.strip():
        return "anchored-detail"
    return "unclassified"


def classify_calibration_recommendation(rec: "Recommendation") -> FindingClass:
    """Return a live recommendation's persisted-field calibration class key.

    This deliberately inspects only fields which survive saved-report
    normalization. It is a class-key helper, not a live audit or gate.
    """
    provenance = (
        rec.purity_verdict_provenance or "unknown"
        if rec.source == _PURITY_FINDING_SOURCE
        else None
    )
    return FindingClass(
        source=rec.source,
        anchor_category=_anchor_category(rec.anchor),
        scope_shape=_scope_shape(rec.anchor, rec.title),
        purity_verdict_provenance=provenance,
    )


def _classify_history_finding(finding: convergence_diagnosis.RunFinding) -> FindingClass:
    """Apply the public class vocabulary to the normalized history subset."""
    provenance = (
        finding.purity_verdict_provenance or "unknown"
        if finding.source == _PURITY_FINDING_SOURCE
        else None
    )
    return FindingClass(
        source=finding.source,
        anchor_category=_anchor_category(finding.anchor),
        scope_shape=_scope_shape(finding.anchor, finding.title),
        purity_verdict_provenance=provenance,
    )


def build_low_impact_demotion_lookup(repo_root: Path) -> LowImpactDemotionLookup:
    """Build one immutable, read-only demotion rule for an operation.

    Calibration history is read exactly once here. Evaluating the returned
    lookup uses only its frozen class set and the live recommendation.
    """
    analysis = analyze_finding_drift(repo_root)
    qualifying_finding_classes = frozenset(
        signal.finding_class
        for signal in analysis.signals
        if (
            signal.finding_class.purity_verdict_provenance
            not in _INELIGIBLE_PURITY_PROVENANCE
            and signal.confirmed + signal.cleared >= LOW_IMPACT_DEMOTION_MIN_RESOLVED
            and signal.confirmed_rate is not None
            and signal.confirmed_rate <= LOW_IMPACT_DEMOTION_MAX_CONFIRMED_RATE
        )
    )
    return LowImpactDemotionLookup(qualifying_finding_classes)


def build_low_impact_demotion_rule(repo_root: Path) -> Callable[["Recommendation"], bool]:
    """Build the callable form of :func:`build_low_impact_demotion_lookup`."""
    return build_low_impact_demotion_lookup(repo_root)


def _parse_created_at(value: str) -> Optional[datetime]:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (AttributeError, TypeError, ValueError):
        return None


def _normalized_anchor(anchor: Optional[str]) -> str:
    return " ".join((anchor or "").lower().split())


def _is_bare_step_anchor(anchor: Optional[str]) -> bool:
    normalized = _normalized_anchor(anchor)
    step = convergence_diagnosis._step_token(normalized)
    return step is not None and normalized == f"step{step}"


def _has_identity_title(title: str) -> bool:
    return bool(title and title.strip() and title.strip().lower() != "(unspecified)")


def _strict_finding_match(
    origin: convergence_diagnosis.RunFinding,
    outcome: convergence_diagnosis.RunFinding,
) -> bool:
    """Match calibration regions without the intentionally broad focus matcher."""
    if not _has_identity_title(origin.title) or not _has_identity_title(outcome.title):
        return False
    origin_anchor = _normalized_anchor(origin.anchor)
    outcome_anchor = _normalized_anchor(outcome.anchor)
    if (
        origin_anchor
        and outcome_anchor
        and not _is_bare_step_anchor(origin.anchor)
        and not _is_bare_step_anchor(outcome.anchor)
    ):
        return origin_anchor == outcome_anchor
    return convergence_diagnosis._title_ratio(
        convergence_diagnosis._title_slug(origin.title),
        convergence_diagnosis._title_slug(outcome.title),
    ) >= convergence_diagnosis.TITLE_SIMILARITY_CUTOFF


def _origin_identity(finding: convergence_diagnosis.RunFinding) -> Optional[tuple[str, str]]:
    """Return a strict grouping identity, or None when evidence cannot join."""
    if not _has_identity_title(finding.title):
        return None
    anchor = _normalized_anchor(finding.anchor)
    if anchor and not _is_bare_step_anchor(finding.anchor):
        return "anchor", anchor
    title = convergence_diagnosis._title_slug(finding.title)
    return ("title", title) if title else None


def _resolved_step(finding: convergence_diagnosis.RunFinding) -> Optional[int]:
    if finding.step_id is not None:
        return finding.step_id
    return convergence_diagnosis._step_token(finding.anchor)


def _selected_outcome(
    history: convergence_diagnosis.ReportHistory,
    origin_index: int,
    origin: convergence_diagnosis.RunFinding,
) -> Optional[tuple[int, convergence_diagnosis.RunSnapshot]]:
    """Find the first chronologically usable same-step code-side audit."""
    step = _resolved_step(origin)
    origin_time = _parse_created_at(history.runs[origin_index].created_at)
    if step is None or origin_time is None:
        return None
    for index in range(origin_index + 1, len(history.runs)):
        snapshot = history.runs[index]
        if snapshot.kind != "run-reconcile" or snapshot.step_id != step:
            continue
        outcome_time = _parse_created_at(snapshot.created_at)
        # The first same-step outcome boundary is authoritative. A tied or
        # malformed timestamp cannot be rescued by a later report.
        if outcome_time is None or outcome_time <= origin_time:
            return None
        return index, snapshot
    return None


def _outcome_valid(snapshot: convergence_diagnosis.RunSnapshot) -> bool:
    """Only an explicitly valid parser marker can turn absence into clearance."""
    return getattr(snapshot, "outcome_evidence_valid", None) is True


def analyze_finding_drift(repo_root: Path) -> FindingDriftAnalysis:
    """Measure later code-side drift for saved audit-finding classes.

    The analysis is intentionally independent of decision telemetry and never
    writes evidence. Origins without a joinable outcome remain visible as
    unresolved observations.
    """
    try:
        plan_paths = [entry.path for entry in locator.list_plans_from_manifest(repo_root)]
    except Exception:
        plan_paths = []

    observations: list[tuple[FindingClass, str]] = []
    for plan_path in plan_paths:
        try:
            history = convergence_diagnosis.load_report_history(plan_path)
        except Exception:
            continue
        candidates: dict[tuple[FindingClass, int, tuple[str, str], int], list[tuple[int, convergence_diagnosis.RunFinding]]] = {}
        for origin_index, snapshot in enumerate(history.runs):
            if snapshot.kind not in _CALIBRATION_ORIGIN_KINDS:
                continue
            for origin in snapshot.findings:
                finding_class = _classify_history_finding(origin)
                step = _resolved_step(origin)
                identity = _origin_identity(origin)
                selected = _selected_outcome(history, origin_index, origin)
                if step is None or identity is None or selected is None:
                    observations.append((finding_class, "unresolved"))
                    continue
                outcome_index, _ = selected
                candidates.setdefault((finding_class, step, identity, outcome_index), []).append((origin_index, origin))

        for (_, _, _, outcome_index), origins in candidates.items():
            # One later audit observes one semantic region once. The latest
            # pre-outcome origin is the state that observation actually saw.
            origin_index, origin = max(origins, key=lambda item: item[0])
            finding_class = _classify_history_finding(origin)
            outcome = history.runs[outcome_index]
            drift_confirmed = any(
                not finding.redirect_present and _strict_finding_match(origin, finding)
                for finding in outcome.findings
            )
            if drift_confirmed:
                observations.append((finding_class, "confirmed"))
            elif _outcome_valid(outcome):
                observations.append((finding_class, "cleared"))
            else:
                observations.append((finding_class, "unresolved"))

    grouped: dict[FindingClass, dict[str, int]] = {}
    for finding_class, outcome in observations:
        grouped.setdefault(finding_class, {"confirmed": 0, "cleared": 0, "unresolved": 0})[outcome] += 1
    signals = []
    for finding_class in sorted(grouped):
        counts = grouped[finding_class]
        resolved = counts["confirmed"] + counts["cleared"]
        signals.append(FindingClassDriftSignal(
            finding_class=finding_class,
            total=resolved + counts["unresolved"],
            confirmed=counts["confirmed"],
            cleared=counts["cleared"],
            unresolved=counts["unresolved"],
            confirmed_rate=counts["confirmed"] / resolved if resolved else None,
            evidence_state=(FINDING_DRIFT_EVIDENCE_SUFFICIENT if resolved >= 3 else FINDING_DRIFT_INSUFFICIENT_EVIDENCE),
        ))
    return FindingDriftAnalysis(total_findings=len(observations), signals=tuple(signals))


# The longer spelling reads naturally at call sites while retaining the concise
# public analysis name above.
analyze_finding_class_drift = analyze_finding_drift


def _inline_evidence(event: DecisionEvent) -> Optional[str]:
    if event.kind == APPLY_VERDICT_KIND:
        return str(event.context.get("verdict", ""))
    if event.kind == ESCALATE_SPLIT_KIND:
        return str(event.context.get("outcome", ""))
    if event.kind == "granularity" and event.decision == CREATE_DECISION_STEP_OUTCOME:
        return str(event.context.get("action", ""))
    return None


def resolve_decision_inline(event: DecisionEvent) -> Optional[str]:
    """Map an event's self-recorded result, or return ``None`` for async work."""
    evidence = _inline_evidence(event)
    if evidence is None:
        return None

    # Unknown and missing values stay visible as open instead of being dropped.
    if event.kind == APPLY_VERDICT_KIND:
        if evidence == "APPLIED":
            return OUTCOME_ACTED_ON
        if evidence == "NOT-APPLICABLE":
            return OUTCOME_NO_OP
        if evidence == APPLY_VERDICT_INVOCATION_FAILED:
            return OUTCOME_STILL_OPEN
        return OUTCOME_STILL_OPEN

    if event.kind == ESCALATE_SPLIT_KIND:
        if evidence == "applied":
            return OUTCOME_ACTED_ON
        if evidence in {"unsafe", "proposal-unusable", "step-missing"}:
            return OUTCOME_NO_OP
        return OUTCOME_STILL_OPEN

    if evidence == CREATE_ACTION_SPLIT_APPLIED:
        return OUTCOME_ACTED_ON
    if evidence in {
        CREATE_ACTION_ACCEPT,
        CREATE_ACTION_OVERRIDE,
        CREATE_ACTION_UNCLASSIFIED_ACCEPTED,
        CREATE_ACTION_UNCLASSIFIED_CLASSIFIED,
    }:
        return OUTCOME_NO_OP
    if evidence in {
        CREATE_ACTION_SPLIT_REQUESTED,
        CREATE_ACTION_SPLIT_ERROR,
        CREATE_ACTION_SPLIT_UNUSABLE,
        CREATE_ACTION_SPLIT_INVALID,
    }:
        return OUTCOME_STILL_OPEN
    return OUTCOME_STILL_OPEN


def _decision_focuses(event: DecisionEvent) -> list[convergence_diagnosis.RunFinding]:
    """Synthesize matcher inputs from the join keys actually stored on an event."""
    raw_step_ids = event.context.get("step_ids", [])
    if not isinstance(raw_step_ids, (list, tuple)):
        raw_step_ids = []

    focuses: list[convergence_diagnosis.RunFinding] = []
    for raw_step_id in raw_step_ids:
        value = str(raw_step_id)
        step_id = convergence_diagnosis._step_token(value)
        if step_id is None:
            try:
                step_id = int(value)
            except ValueError:
                continue
        focuses.append(
            convergence_diagnosis.RunFinding(
                id="decision-focus",
                source="plan-correctness",
                severity="medium",
                step_id=step_id,
                anchor=value,
                title=value,
            )
        )

    if not focuses and event.anchor:
        step_id = convergence_diagnosis._step_token(str(event.anchor))
        focuses.append(
            convergence_diagnosis.RunFinding(
                id="decision-focus",
                source="plan-correctness",
                severity="medium",
                step_id=step_id,
                anchor=str(event.anchor) if step_id is not None else None,
                title=str(event.anchor),
            )
        )

    # Exercise the convergence module's canonical focus normalization here;
    # matching below remains wholly delegated to its tested matcher.
    for focus in focuses:
        convergence_diagnosis._normalized_focus(focus)
    return focuses


def _sidecar_outcome(
    event: DecisionEvent,
    history: convergence_diagnosis.ReportHistory,
) -> Optional[tuple[str, str]]:
    """Resolve a fingerprint-anchored structural decision from later reports."""
    if not event.plan_fingerprint or not history.runs:
        return None
    decision_run_indices = [
        index
        for index, snapshot in enumerate(history.runs)
        if snapshot.plan_fingerprint == event.plan_fingerprint
    ]
    if not decision_run_indices:
        return None

    # Anchor the decision at the matching snapshot current when it fired. Using
    # the last matching fingerprint is wrong when a later revert restores the
    # original plan bytes: it skips the intervening transition entirely.
    decision_index = decision_run_indices[0]
    try:
        event_time = datetime.fromisoformat(event.ts.replace("Z", "+00:00"))
        matching_before_event = [
            index
            for index in decision_run_indices
            if datetime.fromisoformat(
                history.runs[index].created_at.replace("Z", "+00:00")
            )
            <= event_time
        ]
        if matching_before_event:
            decision_index = matching_before_event[-1]
    except (TypeError, ValueError):
        # Legacy/test events can lack a parseable timestamp. The first matching
        # snapshot preserves every subsequent transition, including a revert.
        pass

    focuses = _decision_focuses(event)
    if not focuses:
        return None

    # Reuse convergence's source and matcher contracts without its medium+
    # recurrence threshold: this low-confidence structural signal is ``info``.
    def matches_structural(finding: convergence_diagnosis.RunFinding) -> bool:
        return convergence_diagnosis.is_structural_source(finding.source) and any(
            convergence_diagnosis._matches(finding, focus) for focus in focuses
        )

    if not any(
        matches_structural(finding)
        for snapshot in history.runs
        for finding in snapshot.findings
    ):
        return OUTCOME_NO_OP, "sidecar: no matching region"

    later_runs = history.runs[decision_index + 1 :]
    first_transition = next(
        (
            index
            for index, snapshot in enumerate(later_runs)
            if snapshot.plan_fingerprint != event.plan_fingerprint
        ),
        None,
    )
    if first_transition is None:
        return OUTCOME_STILL_OPEN, "sidecar: no plan fingerprint transition"

    # Once a transition occurs, retain every later snapshot. A revert can
    # restore the original fingerprint, and filtering those snapshots out
    # would hide the recurrence that distinguishes ``reverted`` from
    # ``acted-on``.
    transitioned_runs = later_runs[first_transition:]

    present_after_transition = [
        any(matches_structural(finding) for finding in snapshot.findings)
        for snapshot in transitioned_runs
    ]
    if False in present_after_transition and any(
        present_after_transition[present_after_transition.index(False) + 1 :]
    ):
        return OUTCOME_REVERTED, "sidecar: region resolved then recurred"
    if not present_after_transition[-1]:
        return OUTCOME_ACTED_ON, "sidecar: fingerprint changed and region resolved"
    return OUTCOME_STILL_OPEN, "sidecar: region remains after fingerprint transition"


def resolve_decision_async(
    event: DecisionEvent,
    *,
    run_outcome: Optional[run_log.RunOutcome],
    history: Optional[convergence_diagnosis.ReportHistory],
) -> Optional[tuple[str, str]]:
    """Derive a later outcome from injected run-log and sidecar evidence."""
    # Structural sidecar evidence is more specific than a whole-run result.
    if history is not None:
        sidecar_result = _sidecar_outcome(event, history)
        if sidecar_result is not None:
            return sidecar_result
    if run_outcome is None:
        return None
    if not run_outcome.completed:
        return OUTCOME_STILL_OPEN, "run-log: incomplete"
    details = f"run-log: outcome={run_outcome.outcome} rc={run_outcome.rc}"
    return OUTCOME_STILL_OPEN, details


def resolve_decisions(repo_root: Path) -> list[ResolvedDecision]:
    """Read every decision and return one stable resolution record per event."""
    try:
        plans_by_slug = {
            entry.slug: entry.path for entry in locator.list_plans_from_manifest(repo_root)
        }
    except Exception:
        plans_by_slug = {}
    histories: dict[str, Optional[convergence_diagnosis.ReportHistory]] = {}
    resolved: list[ResolvedDecision] = []
    for event in read_decisions(repo_root):
        outcome = resolve_decision_inline(event)
        is_inline = outcome is not None
        async_result: Optional[tuple[str, str]] = None
        if not is_inline:
            try:
                run_outcome = (
                    run_log.read_run_outcome(
                        run_log.run_log_path(repo_root, event.plan_slug, event.run_id)
                    )
                    if event.run_id
                    else None
                )
                if event.plan_slug not in histories:
                    plan_path = plans_by_slug.get(event.plan_slug)
                    histories[event.plan_slug] = (
                        convergence_diagnosis.load_report_history(plan_path)
                        if plan_path is not None
                        else None
                    )
                async_result = resolve_decision_async(
                    event,
                    run_outcome=run_outcome,
                    history=histories[event.plan_slug],
                )
            except Exception:
                async_result = None
        final_outcome = outcome if is_inline else (
            async_result[0] if async_result is not None else OUTCOME_STILL_OPEN
        )
        resolution = (
            RESOLUTION_INLINE
            if is_inline
            else RESOLUTION_ASYNC if async_result is not None else RESOLUTION_UNRESOLVED
        )
        evidence = (
            (_inline_evidence(event) or "")
            if is_inline
            else async_result[1] if async_result is not None else ""
        )
        resolved.append(
            ResolvedDecision(
                decision_id=event.decision_id,
                kind=event.kind,
                decision=event.decision,
                plan_slug=event.plan_slug,
                outcome=final_outcome,
                resolution=resolution,
                evidence=evidence,
            )
        )
    return resolved


def aggregate_decisions(resolved: list[ResolvedDecision]) -> list[DecisionAggregate]:
    """Group resolved decisions by signal and tally known verdicts."""
    groups: dict[tuple[str, str], list[ResolvedDecision]] = {}
    for item in resolved:
        groups.setdefault((item.kind, item.decision), []).append(item)

    aggregates: list[DecisionAggregate] = []
    for (kind, decision), items in sorted(groups.items()):
        outcomes = {
            OUTCOME_ACTED_ON: 0,
            OUTCOME_NO_OP: 0,
            OUTCOME_REVERTED: 0,
            OUTCOME_STILL_OPEN: 0,
        }
        resolved_count = 0
        unresolved_count = 0
        for item in items:
            if item.outcome in outcomes:
                outcomes[item.outcome] += 1
            if item.resolution in {RESOLUTION_INLINE, RESOLUTION_ASYNC}:
                resolved_count += 1
            elif item.resolution == RESOLUTION_UNRESOLVED:
                unresolved_count += 1

        aggregates.append(
            DecisionAggregate(
                kind=kind,
                decision=decision,
                total=len(items),
                plan_count=len({item.plan_slug for item in items if item.plan_slug}),
                acted_on=outcomes[OUTCOME_ACTED_ON],
                no_op=outcomes[OUTCOME_NO_OP],
                reverted=outcomes[OUTCOME_REVERTED],
                still_open=outcomes[OUTCOME_STILL_OPEN],
                resolved=resolved_count,
                unresolved=unresolved_count,
            )
        )
    return aggregates


def recommend_tuning(
    aggregates: list[DecisionAggregate],
) -> list[TuningRecommendation]:
    """Derive deterministic, advisory-only calibration notes."""
    recommendations: list[TuningRecommendation] = []
    for aggregate in sorted(aggregates, key=lambda item: (item.kind, item.decision)):
        signal = f"{aggregate.kind}/{aggregate.decision}"
        if (
            aggregate.total >= MIN_SAMPLE_FOR_RECOMMENDATION
            and aggregate.total > 0
            and aggregate.unresolved / aggregate.total >= LOW_COVERAGE_RATE
        ):
            recommendations.append(
                TuningRecommendation(
                    aggregate.kind,
                    aggregate.decision,
                    "low-coverage",
                    f"{signal}: {aggregate.unresolved}/{aggregate.total} outcomes "
                    "are uncorrelated; review join coverage before tuning.",
                )
            )

        if aggregate.resolved < MIN_SAMPLE_FOR_RECOMMENDATION:
            continue
        if aggregate.no_op / aggregate.resolved >= HIGH_NO_OP_RATE:
            recommendations.append(
                TuningRecommendation(
                    aggregate.kind,
                    aggregate.decision,
                    "over-sensitive",
                    f"{signal}: {aggregate.no_op}/{aggregate.resolved} resolved "
                    "outcomes were no-op; review its firing threshold.",
                )
            )
        if aggregate.reverted / aggregate.resolved >= REVERTED_RATE_FLAG:
            recommendations.append(
                TuningRecommendation(
                    aggregate.kind,
                    aggregate.decision,
                    "reverting",
                    f"{signal}: {aggregate.reverted}/{aggregate.resolved} resolved "
                    "outcomes reverted; review its threshold.",
                )
            )
    return recommendations


def analyze_decisions(repo_root: Path) -> TelemetryAnalysis:
    """Read repository decisions and assemble their aggregate analysis."""
    resolved = resolve_decisions(repo_root)
    aggregates = aggregate_decisions(resolved)
    recommendations = recommend_tuning(aggregates)
    return TelemetryAnalysis(
        total_events=len(resolved),
        aggregates=tuple(aggregates),
        recommendations=tuple(recommendations),
    )


def analyze_telemetry(repo_root: Path) -> TelemetryAnalysis:
    """Read decision telemetry and independent saved-finding calibration."""
    decisions = analyze_decisions(repo_root)
    return TelemetryAnalysis(
        total_events=decisions.total_events,
        aggregates=decisions.aggregates,
        recommendations=decisions.recommendations,
        calibration=analyze_finding_drift(repo_root),
    )


def analysis_to_dict(analysis: TelemetryAnalysis) -> dict[str, object]:
    """Project an analysis into its stable, machine-readable CLI shape."""
    return {
        "total_events": analysis.total_events,
        "aggregates": [
            {
                "kind": aggregate.kind,
                "decision": aggregate.decision,
                "total": aggregate.total,
                "plan_count": aggregate.plan_count,
                "acted_on": aggregate.acted_on,
                "no_op": aggregate.no_op,
                "reverted": aggregate.reverted,
                "still_open": aggregate.still_open,
                "resolved": aggregate.resolved,
                "unresolved": aggregate.unresolved,
            }
            for aggregate in analysis.aggregates
        ],
        "recommendations": [
            {
                "kind": recommendation.kind,
                "decision": recommendation.decision,
                "category": recommendation.category,
                "message": recommendation.message,
            }
            for recommendation in analysis.recommendations
        ],
        "calibration": {
            "total_findings": analysis.calibration.total_findings if analysis.calibration else 0,
            "signals": [
                {
                    "source": signal.finding_class.source,
                    "anchor_category": signal.finding_class.anchor_category,
                    "scope_shape": signal.finding_class.scope_shape,
                    "purity_verdict_provenance": signal.finding_class.purity_verdict_provenance,
                    "total": signal.total,
                    "confirmed": signal.confirmed,
                    "cleared": signal.cleared,
                    "unresolved": signal.unresolved,
                    "confirmed_rate": signal.confirmed_rate,
                    "evidence_state": signal.evidence_state,
                }
                for signal in (analysis.calibration.signals if analysis.calibration else ())
            ],
        },
    }


def render_analysis(analysis: TelemetryAnalysis) -> str:
    """Render an analysis as a compact human-readable text block."""
    calibration = analysis.calibration
    if analysis.total_events == 0 and (calibration is None or not calibration.signals):
        return "No telemetry recorded yet."

    lines = [f"Telemetry analysis: {analysis.total_events} events"]
    for aggregate in analysis.aggregates:
        lines.append(
            f"- {aggregate.kind}/{aggregate.decision}: total={aggregate.total}, "
            f"plans={aggregate.plan_count}, acted-on={aggregate.acted_on}, "
            f"no-op={aggregate.no_op}, reverted={aggregate.reverted}, "
            f"still-open={aggregate.still_open}, resolved={aggregate.resolved}, "
            f"unresolved={aggregate.unresolved}"
        )
    if analysis.recommendations:
        lines.append("Recommendations:")
        lines.extend(f"- {item.message}" for item in analysis.recommendations)
    if calibration is not None and calibration.signals:
        lines.append("Calibration:")
        for signal in calibration.signals:
            finding_class = signal.finding_class
            provenance = (
                f", provenance={finding_class.purity_verdict_provenance}"
                if finding_class.purity_verdict_provenance is not None else ""
            )
            rate = (
                f"{signal.confirmed_rate:.2f}"
                if signal.confirmed_rate is not None else "n/a"
            )
            lines.append(
                f"- source={finding_class.source}, anchor={finding_class.anchor_category}, "
                f"scope={finding_class.scope_shape}{provenance}: "
                f"confirmed={signal.confirmed}, cleared={signal.cleared}, "
                f"unresolved={signal.unresolved}, rate={rate}, "
                f"evidence={signal.evidence_state}"
            )
    return "\n".join(lines)
