"""Load saved report history and render its convergence diagnosis.

See docs/ARCHITECTURE.md and docs/how-to/pipeline/audit.md for the saved-audit evidence
ledger and convergence contracts.
"""

from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Optional

from plan_tool.convergence import (
    CONCEPTUAL_SOURCES,
    STAGE_BARE,
    STAGE_DETAIL,
    is_blocking,
    is_blocking_finding,
)
from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE
from plan_tool.jira_grade import GRADE_RUN
from plan_tool.locator import slug_from_filename
from plan_tool.review import (
    Recommendation,
    STRUCTURAL_SOURCES,
    classify_finding_domain,
    classify_likely_bare_mechanism,
    confidence_label,
)
from plan_tool.review_persistence import (
    Annotation,
    COMPLETENESS_ARTIFACT_STEM_SUFFIX,
    COMPLETENESS_REPORT_SUFFIX,
    COMPLETENESS_SIDECAR_SUFFIX,
    ReviewLoadError,
    SavedReview,
    list_report_artifacts,
    list_saved_reviews,
    load_review,
    plan_reports_dir,
    project_audit_coverage,
    sampler_checkpoint_path,
)


# Which ``SavedReview.kind`` values count as convergence history. Excludes the
# bare ``kind="review"`` reconcile-plan report (the suffixless
# ``<timestamp>.json``). Filtering on the parsed ``kind`` field — not the
# filename suffix — keeps this robust to any future rename of the file-naming
# scheme and keeps one source for the directory layout.
HISTORY_KINDS: frozenset[str] = frozenset(
    {"completeness", "detail-reconcile", "run-reconcile"}
)


AUDIT_EVIDENCE_REPORT_ONLY = "report-only"
AUDIT_EVIDENCE_ORPHAN_SIDECAR = "orphan-sidecar"
AUDIT_EVIDENCE_MALFORMED_SIDECAR = "malformed-sidecar"
AUDIT_EVIDENCE_CHECKPOINT = "checkpoint"
AUDIT_EVIDENCE_IN_PROGRESS_SAMPLER_CHECKPOINT = "in-progress-checkpoint"
AUDIT_EVIDENCE_TERMINAL_SAMPLER_RESIDUE = "terminal-sampler-residue"
AUDIT_EVIDENCE_UNKNOWN_ROLE = "unknown-role"
AUDIT_EVIDENCE_SAVED_FINAL = "saved-final"

_AUDIT_EVIDENCE_STATES = frozenset(
    {
        AUDIT_EVIDENCE_REPORT_ONLY,
        AUDIT_EVIDENCE_ORPHAN_SIDECAR,
        AUDIT_EVIDENCE_MALFORMED_SIDECAR,
        AUDIT_EVIDENCE_CHECKPOINT,
        AUDIT_EVIDENCE_IN_PROGRESS_SAMPLER_CHECKPOINT,
        AUDIT_EVIDENCE_TERMINAL_SAMPLER_RESIDUE,
        AUDIT_EVIDENCE_UNKNOWN_ROLE,
        AUDIT_EVIDENCE_SAVED_FINAL,
    }
)
_COMPLETENESS_ARTIFACT_RE = re.compile(
    rf"(?P<timestamp>\d{{8}}-\d{{6}}){re.escape(COMPLETENESS_ARTIFACT_STEM_SUFFIX)}$"
)
_QUALIFIED_RESULT_DISPLAY_FIELDS = (
    "headline",
    "stage",
    "coverage",
    "revision_status",
)


@dataclass(frozen=True)
class AuditEvidenceMetadata:
    """Saved completeness metadata presented without current-state checks."""

    is_pre_apply_checkpoint: Optional[bool]
    created_at: str
    audit_stage: str
    audit_revision_grade: str
    audit_coverage: Mapping[str, object]
    qualified_result: Mapping[str, str]


@dataclass(frozen=True)
class AuditEvidenceRow:
    """One saved completeness Markdown/JSON pair or orphan."""

    report_path: Optional[Path]
    sidecar_path: Optional[Path]
    filename_time: str
    state: str
    saved_metadata: AuditEvidenceMetadata
    next_action: str


@dataclass(frozen=True)
class AuditEvidenceLedger:
    """The ordered, read-only saved-artifact inventory for one plan."""

    plan_slug: str
    plan_path: str
    rows: tuple[AuditEvidenceRow, ...]


def _immutable_mapping(values: Mapping[str, object]) -> Mapping[str, object]:
    """Copy a display projection behind a read-only mapping boundary."""
    return MappingProxyType(dict(values))


def _qualified_result_display(values: Mapping[str, object]) -> Mapping[str, str]:
    """Project a saved qualified result without trusting malformed fields."""
    return MappingProxyType(
        {
            field: value if isinstance(value := values.get(field), str) else "unknown"
            for field in _QUALIFIED_RESULT_DISPLAY_FIELDS
        }
    )


def _unknown_qualified_result() -> Mapping[str, str]:
    return _qualified_result_display({})


def _parse_saved_created_at(value: object) -> Optional[datetime]:
    """Parse a timezone-aware saved timestamp, or return ``None``."""
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None and parsed.utcoffset() is not None else None


def _saved_created_at(value: str) -> str:
    """Keep only timezone-aware ISO saved timestamps as displayable facts."""
    return value if _parse_saved_created_at(value) is not None else "invalid"


def _audit_evidence_metadata(review: Optional[SavedReview]) -> AuditEvidenceMetadata:
    """Project saved fields without reading the live plan, code, or reports."""
    if review is None:
        return AuditEvidenceMetadata(
            is_pre_apply_checkpoint=None,
            created_at="unknown",
            audit_stage="unknown",
            audit_revision_grade="unknown",
            audit_coverage=_immutable_mapping(project_audit_coverage(None)),
            qualified_result=_unknown_qualified_result(),
        )
    audit_revision = review.audit_revision
    grade = (
        audit_revision.get("detail_grade")
        if isinstance(audit_revision, dict)
        and isinstance(audit_revision.get("detail_grade"), str)
        else "unknown"
    )
    result = review.qualified_result
    qualified_result = (
        _qualified_result_display(result)
        if isinstance(result, dict)
        else _unknown_qualified_result()
    )
    return AuditEvidenceMetadata(
        is_pre_apply_checkpoint=review.is_pre_apply_checkpoint,
        created_at=_saved_created_at(review.created_at),
        audit_stage=review.audit_stage or "unknown",
        audit_revision_grade=grade,
        audit_coverage=_immutable_mapping(project_audit_coverage(review.audit_coverage)),
        qualified_result=qualified_result,
    )


def _filename_time(path: Path) -> tuple[Optional[datetime], str]:
    """Parse the generated completeness timestamp without consulting payloads."""
    match = _COMPLETENESS_ARTIFACT_RE.search(path.stem)
    if match is None:
        return None, "unknown"
    try:
        parsed = datetime.strptime(match.group("timestamp"), "%Y%m%d-%H%M%S")
    except ValueError:
        return None, "unknown"
    parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed, parsed.strftime("%Y-%m-%dT%H:%M:%SZ")


def _evidence_next_action(state: str, metadata: AuditEvidenceMetadata) -> str:
    """Select a row-local operator action without comparing saved entries."""
    if state not in _AUDIT_EVIDENCE_STATES:
        raise ValueError(f"unknown audit evidence state {state!r}")
    if state != AUDIT_EVIDENCE_SAVED_FINAL:
        return "Inspect the saved artifact or run a fresh completeness audit."
    headline = metadata.qualified_result["headline"]
    if headline == "no-qualified-current-evidence":
        return "Run a fresh completeness audit."
    if headline != "unknown":
        return "Inspect the saved report and its saved result."
    return "Inspect the saved artifact; run a fresh audit when a qualified result is needed."


def _ledger_relative_path(path: Path, reports_dir: Path) -> str:
    """Return the deterministic reports-directory-relative artifact path."""
    return path.relative_to(reports_dir).as_posix()


def _load_saved_review_paths(
    paths: Iterable[Path],
) -> dict[Path, Optional[SavedReview]]:
    """Load saved sidecars once, retaining unreadable entries."""
    loaded: dict[Path, Optional[SavedReview]] = {}
    for path in paths:
        try:
            loaded[path] = load_review(path)
        except ReviewLoadError:
            loaded[path] = None
    return loaded


def _sampler_checkpoint_evidence_state(review: Optional[SavedReview]) -> str:
    """Classify a stable sampler artifact without treating its name as proof.

    Delegates the in-progress determination to
    :attr:`SavedReview.is_in_progress_sampler_checkpoint` rather than
    re-deriving it, so the two can't drift independently.
    """
    if review is None or review.kind != "completeness":
        return AUDIT_EVIDENCE_MALFORMED_SIDECAR
    if review.is_pre_apply_checkpoint is None:
        return AUDIT_EVIDENCE_UNKNOWN_ROLE
    if review.is_in_progress_sampler_checkpoint:
        return AUDIT_EVIDENCE_IN_PROGRESS_SAMPLER_CHECKPOINT
    if review.is_pre_apply_checkpoint is not True or review.sampler_state is None:
        return AUDIT_EVIDENCE_MALFORMED_SIDECAR
    lifecycle = review.sampler_state.get("lifecycle")
    if lifecycle == "terminal-residue":
        return AUDIT_EVIDENCE_TERMINAL_SAMPLER_RESIDUE
    return AUDIT_EVIDENCE_MALFORMED_SIDECAR


def _artifact_snapshot_for_plan(
    plan_path: Path, artifact_paths: Optional[Iterable[Path]]
) -> tuple[Path, tuple[Path, ...]]:
    """Return one reports snapshot after checking it belongs to ``plan_path``."""
    reports_dir = plan_reports_dir(plan_path)
    paths = (
        list_report_artifacts(plan_path)
        if artifact_paths is None
        else tuple(artifact_paths)
    )
    for path in paths:
        try:
            path.relative_to(reports_dir)
        except ValueError as exc:
            raise ValueError(
                f"{path}: saved-artifact snapshot is not under {reports_dir}"
            ) from exc
    return reports_dir, paths


def _validate_saved_review_cache(
    saved_reviews: Mapping[Path, Optional[SavedReview]], reports_dir: Path
) -> None:
    """Reject a saved-review cache captured for another plan's reports tree."""
    for path in saved_reviews:
        try:
            path.relative_to(reports_dir)
        except ValueError as exc:
            raise ValueError(
                f"{path}: saved-review cache is not under {reports_dir}"
            ) from exc


def load_saved_reviews(
    plan_path: Path,
    *,
    artifact_paths: Optional[Iterable[Path]] = None,
    completeness_only: bool = False,
) -> dict[Path, Optional[SavedReview]]:
    """Load this plan's artifact snapshot's sidecars, retaining unreadable entries."""
    slug = slug_from_filename(plan_path)
    assert slug is not None
    _, artifact_paths = _artifact_snapshot_for_plan(plan_path, artifact_paths)
    paths = list_saved_reviews(
        slug,
        plan_path,
        plan_path=plan_path,
        artifact_paths=artifact_paths,
    )
    if completeness_only:
        checkpoint_path = sampler_checkpoint_path(plan_path)
        paths = [
            path
            for path in paths
            if path.name.endswith(COMPLETENESS_SIDECAR_SUFFIX)
            or path == checkpoint_path
        ]
    return _load_saved_review_paths(paths)


def load_audit_evidence_ledger(
    plan_path: Path,
    *,
    saved_reviews: Optional[Mapping[Path, Optional[SavedReview]]] = None,
    artifact_paths: Optional[Iterable[Path]] = None,
) -> AuditEvidenceLedger:
    """Inventory this plan's completeness snapshot without affecting history."""
    slug = slug_from_filename(plan_path)
    assert slug is not None
    reports_dir, artifact_paths = _artifact_snapshot_for_plan(
        plan_path, artifact_paths
    )
    if not artifact_paths:
        if saved_reviews is not None:
            _validate_saved_review_cache(saved_reviews, reports_dir)
        return AuditEvidenceLedger(slug, str(plan_path), ())
    if saved_reviews is None:
        saved_reviews = load_saved_reviews(
            plan_path,
            artifact_paths=artifact_paths,
            completeness_only=True,
        )
    else:
        _validate_saved_review_cache(saved_reviews, reports_dir)

    sampler_path = sampler_checkpoint_path(plan_path)
    artifacts: dict[str, dict[str, Path]] = {}
    sampler_sidecar: Optional[Path] = None
    for path in artifact_paths:
        if path.name.endswith(COMPLETENESS_SIDECAR_SUFFIX):
            artifacts.setdefault(path.stem, {})["sidecar"] = path
        if path.name.endswith(COMPLETENESS_REPORT_SUFFIX):
            artifacts.setdefault(path.stem, {})["report"] = path
        if path == sampler_path:
            sampler_sidecar = path

    missing_sidecars = [
        pair["sidecar"]
        for pair in artifacts.values()
        if "sidecar" in pair and pair["sidecar"] not in saved_reviews
    ]
    if missing_sidecars:
        raise ValueError(
            "saved-review cache does not cover supplied completeness sidecar "
            f"{missing_sidecars[0]}"
        )
    if sampler_sidecar is not None and sampler_sidecar not in saved_reviews:
        raise ValueError(
            "saved-review cache does not cover supplied sampler checkpoint "
            f"{sampler_sidecar}"
        )

    ordered_rows: list[tuple[Optional[datetime], str, AuditEvidenceRow]] = []
    for stem, pair in artifacts.items():
        report_path = pair.get("report")
        sidecar_path = pair.get("sidecar")
        review: Optional[SavedReview] = None
        if sidecar_path is None:
            state = AUDIT_EVIDENCE_REPORT_ONLY
        else:
            review = saved_reviews.get(sidecar_path)
            if review is None:
                state = AUDIT_EVIDENCE_MALFORMED_SIDECAR
            elif review.kind != "completeness":
                state = AUDIT_EVIDENCE_MALFORMED_SIDECAR
            elif report_path is None:
                state = AUDIT_EVIDENCE_ORPHAN_SIDECAR
            elif review.is_pre_apply_checkpoint is True:
                state = AUDIT_EVIDENCE_CHECKPOINT
            elif review.is_pre_apply_checkpoint is None:
                state = AUDIT_EVIDENCE_UNKNOWN_ROLE
            else:
                state = AUDIT_EVIDENCE_SAVED_FINAL
        artifact_path = report_path or sidecar_path
        if artifact_path is None:
            raise ValueError("audit evidence row must have an artifact path")
        timestamp, filename_time = _filename_time(artifact_path)
        metadata = _audit_evidence_metadata(review)
        row = AuditEvidenceRow(
            report_path=report_path,
            sidecar_path=sidecar_path,
            filename_time=filename_time,
            state=state,
            saved_metadata=metadata,
            next_action=_evidence_next_action(state, metadata),
        )
        ordered_rows.append(
            (timestamp, _ledger_relative_path(artifact_path, reports_dir), row)
        )

    if sampler_sidecar is not None:
        review = saved_reviews[sampler_sidecar]
        state = _sampler_checkpoint_evidence_state(review)
        timestamp, filename_time = _filename_time(sampler_sidecar)
        metadata = _audit_evidence_metadata(review)
        row = AuditEvidenceRow(
            report_path=None,
            sidecar_path=sampler_sidecar,
            filename_time=filename_time,
            state=state,
            saved_metadata=metadata,
            next_action=_evidence_next_action(state, metadata),
        )
        # The checkpoint's fixed filename carries no timestamp
        # (_filename_time always misses it), so sort by its real saved time
        # instead of always ranking it behind every dated report.
        sort_timestamp = timestamp or _parse_saved_created_at(metadata.created_at)
        ordered_rows.append(
            (sort_timestamp, _ledger_relative_path(sampler_sidecar, reports_dir), row)
        )

    ordered_rows.sort(
        key=lambda item: (
            item[0] is None,
            item[0] or datetime.max.replace(tzinfo=timezone.utc),
            item[1],
        )
    )
    return AuditEvidenceLedger(
        plan_slug=slug,
        plan_path=str(plan_path),
        rows=tuple(item[2] for item in ordered_rows),
    )


@dataclass(frozen=True)
class RunFinding:
    """One finding flattened from a saved report's recommendation list.

    Carries only fields the saved JSON actually persists. Deliberately
    omits both a per-finding apply verdict (``BLOCKED`` / ``BLOCKED-
    STRUCTURAL`` never reaches the report JSON) and a ``resolved`` flag —
    closed-state is derived per run from the raw ``Annotation`` on
    :attr:`RunSnapshot.annotations`, never carried on the finding itself.

    ``step_id`` is None for completeness findings (``plan-completeness`` /
    ``plan-correctness`` carry ``step_id=None``); the step a completeness
    finding is *about* is resolved by parsing :attr:`anchor`, not this field.
    ``severity`` / ``source`` are kept raw. ``impact`` is the persisted
    triage tag (``"low"`` / ``"medium"`` / ``"high"``), copied verbatim;
    ``None`` when the saved recommendation had no tag.
    """

    id: str
    source: str
    severity: str  # "critical" | "high" | "medium" | "nit" | "info"
    step_id: Optional[int]
    anchor: Optional[str]
    title: str
    impact: Optional[str] = None  # "low" | "medium" | "high" when populated
    purity_verdict_provenance: Optional[str] = None
    redirect_present: bool = False
    # Derived at flatten time via ``classify_finding_domain`` on the full
    # ``Recommendation`` (title + body + suggested_action + file_path) --
    # this dataclass keeps only the label, not the prose it came from. Lets
    # ``_open_medium_plus`` apply the same stage-differentiated blocking bar
    # ``completeness-audit`` uses instead of a blanket severity floor.
    domain: Optional[str] = None
    # Derived from persisted recommendation text for a later advisory. It is
    # deliberately absent from Recommendation and every enforcement path.
    likely_bare_mechanism: bool = False
    confidence: str | None = None


@dataclass(frozen=True)
class RunSnapshot:
    """One saved report, flattened from a :class:`SavedReview`.

    ``annotations`` is carried through verbatim, keyed by finding id — the
    sole carrier of closed-state inputs the advisory helpers read (both
    ``status == "skip"`` and ``halt_reason == ""``). Flattening to a
    per-finding bool would discard ``halt_reason`` and silently disable
    skip-suppression, so the raw map is retained.

    ``plan_fingerprint`` is ``""`` when unset (the persistence sentinel);
    ``code_fingerprint_present`` (not dict truthiness) is the
    never-computed-vs-computed sentinel. ``report_bytes`` is the only on-disk
    growth proxy.
    """

    kind: str
    step_id: Optional[int]
    created_at: str  # ISO-8601 UTC, e.g. "2026-05-05T12:34:56Z"
    plan_fingerprint: str
    code_fingerprint: dict[str, str]
    code_fingerprint_present: bool
    report_bytes: int
    findings: list[RunFinding]
    annotations: dict[str, Annotation]
    # ``None`` is the deliberate legacy/unknown state. Calibration may use a
    # no-match as clearance only when this is explicitly ``True``.
    outcome_evidence_valid: Optional[bool] = None
    # Persisted bare/detail bar for completeness sidecars; ``None`` for legacy
    # or non-completeness runs.
    audit_stage: Optional[str] = None
    # The captured detail grade from immutable audit provenance. ``None`` is
    # legacy or ungraded history, which cannot support bare-mechanism advice.
    audit_revision_grade: Optional[str] = None
    # Sorted step ids parsed from the plan at save time
    # (``SavedReview.step_ids``, BACKLOG #166). ``()`` is the unset sentinel
    # (a save-time parse failure, or history saved before this field
    # existed) — matching ``plan_fingerprint``'s empty-string convention,
    # since a real plan is never zero steps.
    step_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class CompatiblePass:
    """One logical completeness pass after reuse-collapse merging."""

    audit_stage: str
    created_at: str
    findings: tuple[RunFinding, ...]
    annotations: dict[str, Annotation]
    collapsed_count: int = 1
    audit_revision_grade: Optional[str] = None


@dataclass(frozen=True)
class ImpactRecurrenceAdvisory:
    """Recommend-only signal when a high-impact seam recurs without shrinkage."""

    window_audit_stage: str
    seam_source: str
    seam_anchor: Optional[str]
    seam_step_id: Optional[int]
    seam_title_slug: str
    passes_present: int
    newest_matched_count: int


@dataclass(frozen=True)
class EditDriftAdvisory:
    """Recommend-only signal when edit-drift-eligible findings self-seed."""

    window_audit_stage: str
    matched_findings: tuple[RunFinding, ...]
    new_eligible_count: int
    matched_count: int


@dataclass(frozen=True)
class ReportHistory:
    """The whole saved-report series for one plan, oldest→newest.

    ``runs`` is sorted ascending by ``created_at`` (``list_saved_reviews``
    returns newest-first; the trailing-window verdict wants chronological
    order, so the sort happens once, here). ``plan_slug`` is resolved via
    :func:`slug_from_filename` (``default_to_stem=True`` → never None), so
    the renderer can read it straight off the diagnosis.
    """

    plan_slug: str
    plan_path: str  # the plan path the history was loaded for
    runs: list[RunSnapshot]


def _finding_from_recommendation(
    rec: Recommendation,
    *,
    classify_bare_mechanism: bool = True,
) -> RunFinding:
    """Flatten one :class:`Recommendation` to the persisted-field subset."""
    purity_verdict_provenance = None
    if rec.source == GRANULARITY_SPLIT_SOURCE:
        purity_verdict_provenance = rec.purity_verdict_provenance or "unknown"
    # classify_finding_domain is only ever consulted for conceptual-source
    # findings (is_blocking_finding falls back to is_blocking(severity) for
    # every other source) -- skip it for the rest rather than classifying a
    # domain no caller reads.
    domain = classify_finding_domain(rec) if rec.source in CONCEPTUAL_SOURCES else None
    return RunFinding(
        id=rec.id,
        source=rec.source,
        severity=rec.severity,
        impact=rec.impact,
        step_id=rec.step_id,
        anchor=rec.anchor,
        title=rec.title,
        purity_verdict_provenance=purity_verdict_provenance,
        redirect_present=rec.redirect is not None,
        domain=domain,
        likely_bare_mechanism=(
            classify_likely_bare_mechanism(rec) if classify_bare_mechanism else False
        ),
        confidence=rec.confidence,
    )


def _snapshot_from_saved_review(
    review: SavedReview,
    *,
    classify_bare_mechanism: bool = True,
) -> RunSnapshot:
    """Flatten one :class:`SavedReview` into a :class:`RunSnapshot`."""
    audit_revision = review.audit_revision
    audit_revision_grade = (
        audit_revision["detail_grade"]
        if isinstance(audit_revision, dict)
        and isinstance(audit_revision.get("detail_grade"), str)
        else None
    )
    return RunSnapshot(
        kind=review.kind,
        step_id=review.step_id,
        created_at=review.created_at,
        plan_fingerprint=review.plan_fingerprint,
        code_fingerprint=review.code_fingerprint,
        code_fingerprint_present=review.code_fingerprint_present,
        report_bytes=len(review.report_md),
        findings=[
            _finding_from_recommendation(
                recommendation,
                classify_bare_mechanism=classify_bare_mechanism,
            )
            for recommendation in review.recommendations
        ],
        annotations=review.annotations,
        outcome_evidence_valid=review.outcome_evidence_valid,
        audit_stage=review.audit_stage,
        audit_revision_grade=audit_revision_grade,
        step_ids=review.step_ids if review.step_ids_present else (),
    )


def _is_final_report_role(review: SavedReview) -> bool:
    """Whether a loaded sidecar counts as a completed run.

    Only the persisted role decides: ``False`` — an unmarked legacy save or a
    raw version-3 ``false`` — is the ordinary final artifact. A confirmed
    pre-apply checkpoint holds findings from before the apply work finished,
    and an unknown role is metadata no reader may trust as final, so both fail
    closed for every history kind. See DATA_CONTRACT.md § ``SavedReview``.
    """
    return review.is_pre_apply_checkpoint is False


def _created_at_sort_key(snapshot: RunSnapshot) -> datetime:
    """Sort key ordering runs ascending by ``created_at``.

    A malformed ``created_at`` sorts last (``datetime.max``) rather than
    raising, keeping the reader total — a single bad timestamp never sinks
    the whole read.
    """
    return _parse_saved_created_at(snapshot.created_at) or datetime.max.replace(
        tzinfo=timezone.utc
    )


def load_report_history(
    plan_path: Path,
    *,
    saved_reviews: Optional[Mapping[Path, Optional[SavedReview]]] = None,
) -> ReportHistory:
    """Load ``plan_path``'s saved reports into a normalized history model.

    Reuses :func:`list_saved_reviews` / :func:`load_review` (the single
    on-disk parser) rather than re-globbing. Keeps only reviews whose
    ``kind`` is in :data:`HISTORY_KINDS` *and* whose persisted role is the
    ordinary final one (:func:`_is_final_report_role`), flattens each into a
    :class:`RunSnapshot`, and returns them sorted oldest→newest by
    ``created_at``. Excluded sidecars stay on disk and readable through
    :func:`load_review`; they simply never reach a convergence verdict.

    Total by design: an absent reports dir yields an empty history (no
    error), an unparseable sidecar is skipped (``ReviewLoadError``
    swallowed), and a malformed ``created_at`` sorts last instead of
    raising.
    """
    slug = slug_from_filename(plan_path)  # default_to_stem=True → never None
    assert slug is not None
    reports_dir = plan_reports_dir(plan_path)
    if saved_reviews is None:
        saved_reviews = load_saved_reviews(plan_path)
    else:
        _validate_saved_review_cache(saved_reviews, reports_dir)
    reviews: list[SavedReview] = []
    for review in saved_reviews.values():
        if review is None:
            continue
        if review.kind not in HISTORY_KINDS:
            continue
        if not _is_final_report_role(review):
            continue
        reviews.append(review)
    reviews.sort(key=_created_at_sort_key)
    newest_completeness = next(
        (
            review
            for review in reversed(reviews)
            if review.kind == "completeness" and review.audit_stage is not None
        ),
        None,
    )
    snapshots = [
        _snapshot_from_saved_review(
            review,
            classify_bare_mechanism=review is newest_completeness,
        )
        for review in reviews
    ]
    return ReportHistory(
        plan_slug=slug,
        plan_path=str(plan_path),
        runs=snapshots,
    )


def _merge_collapse_annotations(
    older: dict[str, Annotation],
    newer: dict[str, Annotation],
) -> dict[str, Annotation]:
    """Merge annotations when collapsing adjacent identical-id reuse replays."""
    merged: dict[str, Annotation] = {}
    for finding_id in set(older) | set(newer):
        old_ann = older.get(finding_id)
        new_ann = newer.get(finding_id)
        old_terminal = _is_resolved_in_run(old_ann)
        new_terminal = _is_resolved_in_run(new_ann)
        if old_terminal and not new_terminal:
            merged[finding_id] = old_ann  # type: ignore[assignment]
        elif new_terminal and not old_terminal:
            merged[finding_id] = new_ann  # type: ignore[assignment]
        elif new_ann is not None:
            merged[finding_id] = new_ann
        elif old_ann is not None:
            merged[finding_id] = old_ann
    return merged


def _compatible_pass_from_snapshot(
    snapshot: RunSnapshot, *, collapsed_count: int = 1
) -> CompatiblePass:
    assert snapshot.audit_stage is not None
    return CompatiblePass(
        audit_stage=snapshot.audit_stage,
        created_at=snapshot.created_at,
        findings=tuple(snapshot.findings),
        annotations=dict(snapshot.annotations),
        collapsed_count=collapsed_count,
        audit_revision_grade=snapshot.audit_revision_grade,
    )


def build_collapsed_completeness_passes(
    history: ReportHistory,
) -> tuple[CompatiblePass, ...]:
    """Return completeness finals with stage gates and reuse-collapse applied.

    Consumes :func:`load_report_history` output as-is — checkpoint pairing
    stays upstream. Drops completeness runs with missing ``audit_stage``,
    never collapses across a stage boundary, and merges adjacent finals
    whose finding-id sets are identical within the same stage.
    """
    passes: list[CompatiblePass] = []
    for snapshot in history.runs:
        if snapshot.kind != "completeness" or snapshot.audit_stage is None:
            continue
        current_ids = frozenset(finding.id for finding in snapshot.findings)
        if (
            passes
            and passes[-1].audit_stage == snapshot.audit_stage
            and current_ids == frozenset(f.id for f in passes[-1].findings)
        ):
            prev = passes[-1]
            passes[-1] = CompatiblePass(
                audit_stage=snapshot.audit_stage,
                created_at=snapshot.created_at,
                findings=tuple(snapshot.findings),
                annotations=_merge_collapse_annotations(
                    prev.annotations, snapshot.annotations
                ),
                collapsed_count=prev.collapsed_count + 1,
                audit_revision_grade=snapshot.audit_revision_grade,
            )
        else:
            passes.append(_compatible_pass_from_snapshot(snapshot))
    return tuple(passes)


# --------------------------------------------------------------------------- #
# Finding-matching helpers
#
# Identify when two findings across runs are "the same" recurring finding,
# using a tiered match (step focus -> concept-slug anchor -> fuzzy title).
# Consumed both by the verdict/advisory logic below and by
# ``telemetry_analysis`` for its own cross-run finding-outcome matching.
# --------------------------------------------------------------------------- #

# Read old persisted purity findings as their folded structural successor.
_LEGACY_STRUCTURAL_SOURCES = frozenset({"detail-purity"})


def is_structural_source(source: str) -> bool:
    """True when ``source`` supports a current or legacy structural decision."""
    return source in STRUCTURAL_SOURCES | _LEGACY_STRUCTURAL_SOURCES


# The ``difflib.SequenceMatcher.ratio()`` floor for the title-similarity tier.
# Named so downstream readers reuse it rather than re-hardcoding ``0.85``.
TITLE_SIMILARITY_CUTOFF: float = 0.85

# The only severity ordering this module needs (sub-``medium`` is filtered out
# before ranking). No shared severity-order constant exists in ``review.py`` or
# ``convergence.py`` to reuse, so this is the single source for
# ``_max_severity_str``. Keyed on ``severity.lower()`` everywhere — an
# uppercase ``"MEDIUM"`` clears the ``is_blocking`` floor, so a raw lookup would
# ``KeyError`` without the lowercase guard.
_SEVERITY_RANK: dict[str, int] = {"medium": 1, "high": 2, "critical": 3}

# Severities worth a run-readiness advisory on an otherwise converging verdict:
# ``critical`` / ``high`` only. ``medium`` is an advisory gap most converging
# plans carry, too noisy to flag here. Keyed lowercase, like every severity
# compare in this module.
_ADVISORY_SEVERITIES: frozenset[str] = frozenset({"critical", "high"})

# Cap for the title-slug fallback focus, so a non-anchored finding's focus key
# stays a bounded slug rather than a full title.
_TITLE_SLUG_FOCUS_MAXLEN: int = 60

# Parse a leading ``step<N>`` / ``step-<N>`` token: matches ``step5-over-pack``
# and ``step-5-…``.
_STEP_TOKEN_RE = re.compile(r"^step-?(\d+)")


def _step_token(anchor: Optional[str]) -> Optional[int]:
    """Parse a leading ``step<N>`` number from ``anchor``, else None."""
    if not anchor:
        return None
    match = _STEP_TOKEN_RE.match(anchor)
    return int(match.group(1)) if match else None


def _title_slug(title: str) -> str:
    """Normalize a title to a lowercase hyphen slug."""
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def _title_ratio(a: str, b: str) -> float:
    """Similarity of two title slugs, in ``[0.0, 1.0]``."""
    return difflib.SequenceMatcher(None, a, b).ratio()


def _finding_step_focus(finding: RunFinding) -> Optional[int]:
    """The finding's step focus int: ``step_id`` if set, else the anchor token."""
    if finding.step_id is not None:
        return finding.step_id
    return _step_token(finding.anchor)


def _normalized_focus(finding: RunFinding) -> str:
    """The keying string, in priority order: step focus -> anchor -> title slug."""
    if finding.step_id is not None:
        return f"step{finding.step_id}"
    token = _step_token(finding.anchor)
    if token is not None:
        return f"step{token}"
    if finding.anchor:
        return finding.anchor
    return _title_slug(finding.title)[:_TITLE_SLUG_FOCUS_MAXLEN]


def _matches(candidate: RunFinding, representative: RunFinding) -> bool:
    """True when ``candidate`` matches ``representative`` (highest tier).

    Tier 1 (step focus) and tier 2 (concept-slug anchor) are authoritative and
    take precedence over tier 3 (fuzzy title), so a step-focused finding prefers
    a step-focused match and a stable anchor does not break the match just
    because no ``step<N>`` token is present.
    """
    c_focus = _finding_step_focus(candidate)
    r_focus = _finding_step_focus(representative)
    # Tier 1 — step focus (authoritative): both resolve a focus and they match.
    if c_focus is not None and r_focus is not None:
        return c_focus == r_focus
    # Tier 2 — concept-slug anchor (authoritative): neither resolves a focus,
    # both anchors non-empty and equal.
    if c_focus is None and r_focus is None and candidate.anchor and representative.anchor:
        if candidate.anchor == representative.anchor:
            return True
    # Tier 3 — title similarity (last resort).
    return (
        _title_ratio(_title_slug(candidate.title), _title_slug(representative.title))
        >= TITLE_SIMILARITY_CUTOFF
    )


def series_key(snapshot: RunSnapshot) -> tuple:
    """The series partition key.

    ``(kind,)`` for completeness; ``(kind, step_id)`` for the two reconcile
    kinds — each reconcile sidecar audits a single step, so partitioning on
    ``kind`` alone would compare audits of different steps.
    """
    if snapshot.kind == "completeness":
        return (snapshot.kind,)
    return (snapshot.kind, snapshot.step_id)


def series_label(snapshot: RunSnapshot) -> str:
    """The ``":"``-joined string form of :func:`series_key`.

    e.g. ``"completeness"``, ``"detail-reconcile:5"``. Derived from
    ``series_key`` only, so a series and its label never disagree.
    """
    return ":".join(str(part) for part in series_key(snapshot))


def partition_series(history: ReportHistory) -> dict[tuple, list[RunSnapshot]]:
    """Group the ordered runs by :func:`series_key`, preserving chronology.

    The insertion-ordered dict keeps output series order deterministic.
    """
    series: dict[tuple, list[RunSnapshot]] = {}
    for run in history.runs:
        series.setdefault(series_key(run), []).append(run)
    return series


def _max_severity_str(severities: list[str]) -> str:
    """The severity string with the highest ``_SEVERITY_RANK`` (lower-keyed)."""
    return max(severities, key=lambda s: _SEVERITY_RANK[s.lower()])


def _is_decline_close(annotation: Optional[Annotation]) -> bool:
    """True when ``annotation`` is a deliberate WONTFIX decline.

    Only ``status == "skip"`` with ``halt_reason == ""`` closes persistently.
    Applied state is current-run-only: it closes a presently applied finding,
    but a later fresh finding may recur.
    """
    if annotation is None:
        return False
    return annotation.status == "skip" and annotation.halt_reason == ""


# --------------------------------------------------------------------------- #
# Verdict + newest-run advisories
#
# Reads each series' snapshots (via ``partition_series``) and decides per
# series a three-state verdict — ``no-history`` / ``insufficient-history`` /
# ``converging`` — from run count and fingerprint stability alone, then rolls
# the per-series calls into one plan-level worst-of headline. Also computes
# three newest-run advisories (unresolved blocking findings, code drift, and a
# same-kind open-finding trajectory) that ride along without altering the
# verdict, and renders the whole diagnosis as the printable block the CLI
# emits.
# --------------------------------------------------------------------------- #

# The trailing window N: a series with at least this many runs (or a stable
# fingerprint streak, see below) reads ``converging``. Plumbed as a keyword on
# ``diagnose_convergence`` so tests can shrink it without 3+ runs.
WINDOW_SIZE: int = 3

# The three verdict states, as constants the render and CLI key on — do not
# inline the literals downstream.
VERDICT_NO_HISTORY = "no-history"
VERDICT_INSUFFICIENT_HISTORY = "insufficient-history"
VERDICT_CONVERGING = "converging"

# The worst-of ordering ``converging > insufficient-history > no-history``. The
# plan-level headline is the max-rank verdict across the per-series verdicts.
_VERDICT_RANK: dict[str, int] = {
    VERDICT_NO_HISTORY: 0,
    VERDICT_INSUFFICIENT_HISTORY: 1,
    VERDICT_CONVERGING: 2,
}


@dataclass(frozen=True)
class SeriesDiagnosis:
    """One verdict record per series (one ``kind``, or ``(kind, step_id)``).

    ``structural_recurrence`` is ``True`` when this series certified
    ``converging`` via the full-window path (``run_count >= window``) *and* a
    structural finding recurred across the trailing window
    (:func:`_structural_recurs_in_streak`) — the sub-threshold path
    (:func:`_fingerprint_stable_streak`) already denies certification in that
    case, so this only ever fires for a full-window series. Never alters
    ``verdict``: the retired ``spinning`` fourth state (BACKLOG #251) is not
    coming back, this only feeds the :class:`ConvergenceDiagnosis`-level
    advisory.

    ``redecomposition_step_counts`` (BACKLOG #166): the trailing window's
    step counts when its known step-id sets differ, with the same full-window
    scoping as ``structural_recurrence`` — see
    :func:`_redecomposition_step_counts`. Labels only; never excludes a run or
    alters ``verdict``/``run_count``.
    """

    key: tuple
    kind: str
    step_id: Optional[int]
    verdict: str
    run_count: int
    structural_recurrence: bool = False
    redecomposition_step_counts: tuple[int, ...] = ()


@dataclass(frozen=True)
class ConvergenceDiagnosis:
    """The full diagnosis the render and the CLI consume.

    ``verdict`` is the worst-of headline; ``window`` is the N actually used (for
    the render's "… of the last N audits"); ``series`` lists every series'
    verdict in ``partition_series`` order.

    ``latest_blocking`` / ``code_drift`` / ``finding_churn`` /
    ``structural_recurrence`` / ``redecomposition_span`` /
    ``impact_recurrence`` / ``edit_drift`` / ``bare_mechanism_findings`` are
    newest-run signals the verdict cannot carry: unresolved critical/high
    findings, code movement since the prior same-kind run, an increasing
    open-medium+ trajectory whose severity ceiling also rose, a full-window
    series whose same structural finding is still open unchanged
    (:attr:`SeriesDiagnosis.structural_recurrence`), a full-window series
    whose runs span more than one known step-id set
    (:attr:`SeriesDiagnosis.redecomposition_step_counts`, BACKLOG #166), a
    recurring high-impact seam across compatible completeness passes, and a
    strict majority of new edit-drift-eligible findings matching the
    window-local prior-apply set. The render shows them as recommend-only
    advisories without altering the verdict or acting as run-readiness
    gates. Defaults preserve existing constructions and the no-history path.
    """

    plan_slug: str
    verdict: str
    window: int
    series: tuple[SeriesDiagnosis, ...]
    latest_blocking: tuple[RunFinding, ...] = ()
    code_drift: bool = False
    finding_churn: "FindingChurn | None" = None
    structural_recurrence: tuple[SeriesDiagnosis, ...] = ()
    redecomposition_span: tuple[SeriesDiagnosis, ...] = ()
    impact_recurrence: ImpactRecurrenceAdvisory | None = None
    edit_drift: EditDriftAdvisory | None = None
    bare_mechanism_findings: tuple[RunFinding, ...] = ()


@dataclass(frozen=True)
class FindingChurn:
    """A same-kind two-run rise that merits measurement, not re-decomposition."""

    kind: str
    prior_open_count: int
    latest_open_count: int
    prior_ceiling: str
    latest_ceiling: str


def _structural_recurs_in_streak(
    snapshots: list[RunSnapshot], streak_indices: list[int]
) -> bool:
    """True when a structural, medium+ finding recurs across ≥2 of the streak's runs.

    The narrow slice of the retired region-trending layer (BACKLOG #251)
    that :func:`_fingerprint_stable_streak` still needs: a fingerprint-stable
    streak is not "converging" evidence when the same structural finding is
    still open across it. Scoped exactly like the old ``recurring_regions``
    (``is_structural_source`` + ``is_blocking``, matched via :func:`_matches`)
    — not the whole spinning verdict, which #251 retired for being starved
    (0.13% of findings) and its one lifetime firing a false alarm. Does not
    special-case a declined (WONTFIX) finding, matching the pre-#251 check it
    restores.
    """
    representatives: list[RunFinding] = []
    seen_in: list[set[int]] = []
    for index in streak_indices:
        scoped = [
            f
            for f in snapshots[index].findings
            if is_structural_source(f.source) and is_blocking(f.severity)
        ]
        for finding in scoped:
            joined = next(
                (i for i, rep in enumerate(representatives) if _matches(finding, rep)),
                None,
            )
            if joined is None:
                representatives.append(finding)
                seen_in.append({index})
            else:
                seen_in[joined].add(index)
    return any(len(indices) >= 2 for indices in seen_in)


def _redecomposition_step_counts(
    snapshots: list[RunSnapshot], trailing: list[int]
) -> tuple[int, ...]:
    """The trailing window's known step counts when its step-id sets differ.

    ``()`` when fewer than two of the trailing runs carry a known
    :attr:`RunSnapshot.step_ids` (``()`` is the unset sentinel and is
    skipped, not treated as a mismatch — legacy history predating BACKLOG
    #166 must not falsely flag every full-window series) or when every known
    step-id set agrees. Counts remain the compact render payload, but only
    identities decide whether the advisory fires. A fact for the render to
    surface, not a judgment: this never excludes a run from ``run_count`` or
    denies certification, unlike :func:`_structural_recurs_in_streak`.
    """
    known_step_ids = [
        snapshots[i].step_ids for i in trailing if snapshots[i].step_ids
    ]
    if len(known_step_ids) < 2 or len(set(known_step_ids)) <= 1:
        return ()
    return tuple(len(step_ids) for step_ids in known_step_ids)


def _fingerprint_stable_streak(snapshots: list[RunSnapshot]) -> bool:
    """The converging certificate for a sub-threshold series.

    Needs ≥2 trailing snapshots sharing an identical *non-empty*
    ``plan_fingerprint`` (an all-``""`` streak is not stable evidence), an
    identical ``code_fingerprint`` among the streak's runs whose
    ``code_fingerprint`` is non-empty (an all-empty one does not block — plan
    fingerprint alone certifies), and no structural finding recurring across
    ≥2 of the streak's runs (:func:`_structural_recurs_in_streak`).
    """
    if len(snapshots) < 2:
        return False
    last_fingerprint = snapshots[-1].plan_fingerprint
    if not last_fingerprint:  # unset sentinel -> not stable evidence
        return False
    # The maximal trailing run of snapshots sharing the same plan fingerprint.
    streak_indices: list[int] = []
    for index in range(len(snapshots) - 1, -1, -1):
        if snapshots[index].plan_fingerprint != last_fingerprint:
            break
        streak_indices.append(index)
    streak_indices.reverse()
    if len(streak_indices) < 2:
        return False
    # Non-empty code fingerprints across the streak must agree.
    code_fingerprints = [
        snapshots[i].code_fingerprint for i in streak_indices if snapshots[i].code_fingerprint
    ]
    if code_fingerprints and any(cf != code_fingerprints[0] for cf in code_fingerprints):
        return False
    if _structural_recurs_in_streak(snapshots, streak_indices):
        return False
    return True


def _series_verdict(snapshots: list[RunSnapshot], window: int) -> SeriesDiagnosis:
    """The per-series three-state call over one series' snapshots.

    ``run_count >= window`` or a stable fingerprint streak reads
    ``converging``; any run at all short of that reads ``insufficient-
    history``; no runs (never reached via ``partition_series``, which always
    yields ≥1 run per series) reads ``no-history``.

    A full-window ``converging`` series (``run_count >= window``) additionally
    checks whether a structural finding recurred across the trailing window —
    unlike the sub-threshold path, ``run_count >= window`` certifies
    unconditionally, so this can't deny the verdict; it only sets
    :attr:`SeriesDiagnosis.structural_recurrence` for the plan-level advisory.
    Skipped when certification came via the sub-threshold path instead
    (``_fingerprint_stable_streak`` already denies certification on the same
    recurrence, so it is always ``False`` there by construction).
    """
    run_count = len(snapshots)
    if run_count >= window or _fingerprint_stable_streak(snapshots):
        verdict = VERDICT_CONVERGING
    elif run_count >= 1:
        verdict = VERDICT_INSUFFICIENT_HISTORY
    else:  # run_count == 0 — never reached via partition_series (always ≥1 run)
        verdict = VERDICT_NO_HISTORY

    structural_recurrence = False
    redecomposition_step_counts: tuple[int, ...] = ()
    if verdict == VERDICT_CONVERGING and run_count >= window:
        trailing = list(range(max(0, run_count - window), run_count))
        structural_recurrence = _structural_recurs_in_streak(snapshots, trailing)
        redecomposition_step_counts = _redecomposition_step_counts(snapshots, trailing)

    head = snapshots[0]
    return SeriesDiagnosis(
        key=series_key(head),
        kind=head.kind,
        step_id=head.step_id,
        verdict=verdict,
        run_count=run_count,
        structural_recurrence=structural_recurrence,
        redecomposition_step_counts=redecomposition_step_counts,
    )


def _is_resolved_in_run(annotation: Optional[Annotation]) -> bool:
    """Terminal, no-longer-open state for a finding in *its own run*.

    ``applied`` (resolved) or a deliberate decline-close
    (:func:`_is_decline_close`) both count; a ``halt_reason="drift"`` safety
    skip and ``open``/unreached do not.
    """
    if annotation is None:
        return False
    return annotation.status == "applied" or _is_decline_close(annotation)


def _seam_sort_key(representative: RunFinding) -> tuple[str, str | int, str]:
    """Stable tie-break key for impact-recurrence seam selection."""
    if representative.step_id is not None:
        anchor_or_step: str | int = representative.step_id
    elif representative.anchor:
        anchor_or_step = representative.anchor
    else:
        anchor_or_step = ""
    return (
        representative.source,
        anchor_or_step,
        _title_slug(representative.title),
    )


def _impact_recurrence_trailing_window(
    passes: tuple[CompatiblePass, ...],
    *,
    window: int,
) -> tuple[CompatiblePass, ...] | None:
    if not passes:
        return None
    window_audit_stage = passes[-1].audit_stage
    compatible: list[CompatiblePass] = []
    for pass_ in reversed(passes):
        if pass_.audit_stage != window_audit_stage:
            break
        compatible.append(pass_)
    compatible.reverse()
    if len(compatible) < window:
        return None
    return tuple(compatible[-window:])


def _matched_high_impact_count(
    pass_: CompatiblePass,
    representative: RunFinding,
) -> int:
    return sum(
        1
        for finding in pass_.findings
        if finding.impact == "high" and _matches(finding, representative)
    )


def _has_open_high_impact_match(
    pass_: CompatiblePass,
    representative: RunFinding,
) -> bool:
    for finding in pass_.findings:
        if finding.impact != "high" or not _matches(finding, representative):
            continue
        if not _is_resolved_in_run(pass_.annotations.get(finding.id)):
            return True
    return False


def _build_impact_seam_representatives(
    window: tuple[CompatiblePass, ...],
) -> list[RunFinding]:
    representatives: list[RunFinding] = []
    for pass_ in window:
        for finding in pass_.findings:
            if finding.impact != "high":
                continue
            if any(_matches(finding, rep) for rep in representatives):
                continue
            representatives.append(finding)
    return representatives


def _impact_recurrence_shrinkage_ok(
    window: tuple[CompatiblePass, ...],
    representative: RunFinding,
) -> bool:
    counts = [_matched_high_impact_count(pass_, representative) for pass_ in window]
    return all(counts[i + 1] >= counts[i] for i in range(len(counts) - 1))


@dataclass(frozen=True)
class _ImpactSeamCandidate:
    representative: RunFinding
    passes_present: int
    newest_matched_count: int


def _build_prior_apply_set(window: tuple[CompatiblePass, ...]) -> list[RunFinding]:
    """Window-local prior-apply representatives from dispositions and disappearances."""
    representatives: list[RunFinding] = []
    for pass_ in window:
        for finding in pass_.findings:
            if _is_resolved_in_run(pass_.annotations.get(finding.id)):
                representatives.append(finding)
    for index in range(len(window) - 1):
        older = window[index]
        newer = window[index + 1]
        for finding in older.findings:
            if not any(_matches(finding, newer_f) for newer_f in newer.findings):
                representatives.append(finding)
    return representatives


def _new_findings_vs_prior(
    pass_: CompatiblePass,
    prior_pass: CompatiblePass,
) -> list[RunFinding]:
    """Findings in ``pass_`` with no ``_matches`` counterpart in ``prior_pass``."""
    return [
        finding
        for finding in pass_.findings
        if not any(_matches(finding, prior_f) for prior_f in prior_pass.findings)
    ]


def _edit_drift_eligible(
    findings: list[RunFinding],
    *,
    window_audit_stage: str,
    annotations: dict[str, Annotation],
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
) -> list[RunFinding]:
    """New findings that pass the stage bar and remain open in the newest pass."""
    eligible: list[RunFinding] = []
    for finding in findings:
        if not is_blocking_finding(
            finding, stage=window_audit_stage, classify_domain=classify_domain
        ):
            continue
        if _is_resolved_in_run(annotations.get(finding.id)):
            continue
        eligible.append(finding)
    return eligible


def classify_edit_drift(
    history: ReportHistory,
    *,
    window: int = WINDOW_SIZE,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
    passes: tuple[CompatiblePass, ...] | None = None,
) -> EditDriftAdvisory | None:
    """Return a recommend-only advisory when edit-drift-eligible findings self-seed.

    Evaluates the newest ``window`` same-``audit_stage`` collapsed completeness
    passes. Fires when a strict majority of new edit-drift-eligible findings in
    the newest pass match the window-local prior-apply set built from resolved
    dispositions and disappearances between adjacent window passes.
    """
    # Edit drift must compare the newest pass with its immediate predecessor.
    # ``diagnose_convergence`` intentionally lets callers shrink ``window``
    # for focused checks, so a sub-two-pass window is valid input but cannot
    # provide edit-drift evidence.
    if window < 2:
        return None
    collapsed_passes = (
        build_collapsed_completeness_passes(history) if passes is None else passes
    )
    evaluation_window = _impact_recurrence_trailing_window(
        collapsed_passes, window=window
    )
    if evaluation_window is None:
        return None

    window_audit_stage = evaluation_window[-1].audit_stage
    prior_apply_set = _build_prior_apply_set(evaluation_window)
    prior_pass, newest_pass = evaluation_window[-2], evaluation_window[-1]

    new_eligible = _edit_drift_eligible(
        _new_findings_vs_prior(newest_pass, prior_pass),
        window_audit_stage=window_audit_stage,
        annotations=newest_pass.annotations,
        classify_domain=classify_domain,
    )
    if not new_eligible:
        return None

    matched_findings = tuple(
        finding
        for finding in new_eligible
        if any(_matches(finding, representative) for representative in prior_apply_set)
    )
    matched_count = len(matched_findings)
    new_eligible_count = len(new_eligible)
    if matched_count * 2 <= new_eligible_count:
        return None

    return EditDriftAdvisory(
        window_audit_stage=window_audit_stage,
        matched_findings=matched_findings,
        new_eligible_count=new_eligible_count,
        matched_count=matched_count,
    )


def classify_bare_mechanism_advisory(
    history: ReportHistory,
    *,
    grade: str = GRADE_RUN,
    passes: tuple[CompatiblePass, ...] | None = None,
) -> tuple[RunFinding, ...]:
    """Return current, open bare correctness findings likely owned by detail.

    The newest collapsed logical pass is the only advisory source. Its
    immutable captured grade must be run grade; legacy, Jira-grade, and an
    operator-selected Jira convergence view remain silent.
    """
    if grade != GRADE_RUN:
        return ()
    collapsed_passes = (
        build_collapsed_completeness_passes(history) if passes is None else passes
    )
    if not collapsed_passes:
        return ()
    newest = collapsed_passes[-1]
    if newest.audit_stage != STAGE_BARE or newest.audit_revision_grade != GRADE_RUN:
        return ()
    return tuple(
        finding
        for finding in newest.findings
        if (
            finding.source == "plan-correctness"
            and finding.likely_bare_mechanism
            and not _is_resolved_in_run(newest.annotations.get(finding.id))
        )
    )


def classify_impact_recurrence(
    history: ReportHistory,
    *,
    window: int = WINDOW_SIZE,
    passes: tuple[CompatiblePass, ...] | None = None,
) -> ImpactRecurrenceAdvisory | None:
    """Return a recommend-only advisory when a high-impact seam recurs without shrinkage.

    Reads collapsed completeness passes from ``history``, evaluates the newest
    ``window`` same-``audit_stage`` passes, and fires when one seam has explicit
    ``impact == "high"`` findings in every window pass with non-decreasing
    matched counts and at least one still-open match in the newest pass.
    """
    # A recurrence needs an earlier observation to recur from. Keep the
    # ``window`` test seam valid at one pass, but withhold this cross-pass
    # advisory until at least two passes are available.
    if window < 2:
        return None
    collapsed_passes = (
        build_collapsed_completeness_passes(history) if passes is None else passes
    )
    evaluation_window = _impact_recurrence_trailing_window(
        collapsed_passes, window=window
    )
    if evaluation_window is None:
        return None

    window_audit_stage = evaluation_window[-1].audit_stage
    representatives = _build_impact_seam_representatives(evaluation_window)
    newest = evaluation_window[-1]

    candidates: list[_ImpactSeamCandidate] = []
    for representative in representatives:
        newest_count = _matched_high_impact_count(newest, representative)
        if newest_count == 0 or not _has_open_high_impact_match(newest, representative):
            continue
        passes_present = sum(
            1
            for pass_ in evaluation_window
            if _matched_high_impact_count(pass_, representative) > 0
        )
        if passes_present < window:
            continue
        if not _impact_recurrence_shrinkage_ok(evaluation_window, representative):
            continue
        candidates.append(
            _ImpactSeamCandidate(
                representative=representative,
                passes_present=passes_present,
                newest_matched_count=newest_count,
            )
        )

    if not candidates:
        return None

    best = min(
        candidates,
        key=lambda candidate: (
            -candidate.passes_present,
            -candidate.newest_matched_count,
            _seam_sort_key(candidate.representative),
        ),
    )
    representative = best.representative
    return ImpactRecurrenceAdvisory(
        window_audit_stage=window_audit_stage,
        seam_source=representative.source,
        seam_anchor=representative.anchor,
        seam_step_id=representative.step_id,
        seam_title_slug=_title_slug(representative.title),
        passes_present=best.passes_present,
        newest_matched_count=best.newest_matched_count,
    )


def _latest_blocking_findings(history: ReportHistory) -> tuple[RunFinding, ...]:
    """The newest saved run's *open* critical/high findings, newest-run-only.

    Lets the render flag run-readiness the verdict can't: the loop signal reads
    ``converging`` even when the newest audit just surfaced a fresh critical.
    Excludes findings the newest run's annotations mark resolved
    (:func:`_is_resolved_in_run`) — ``completeness-apply`` rewrites the same
    report in place, keeping ``recommendations`` verbatim and only adding
    annotations, so presence alone overstates what is open. Filtered on
    severity only (not :data:`STRUCTURAL_SOURCES`): ``plan-completeness`` is
    nonstructural yet is the source ``completeness-apply``'s gap walk resolves,
    so a structural source gate would drop the very findings this flags.
    """
    if not history.runs:
        return ()
    newest = history.runs[-1]
    return tuple(
        f
        for f in newest.findings
        if f.severity.lower() in _ADVISORY_SEVERITIES
        and not _is_resolved_in_run(newest.annotations.get(f.id))
    )


def _open_medium_plus(
    snapshot: RunSnapshot,
    *,
    audit_stage: str,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
) -> tuple[RunFinding, ...]:
    """Return the snapshot's unresolved medium-or-higher findings.

    Uses the same stage-differentiated blocking bar ``completeness-audit``
    does (``classify_domain`` defaults to the old blanket-block behavior);
    reads each report's saved annotation rather than raw recommendation
    presence, since an apply walk's applied/declined findings are no longer
    open evidence. See docs/how-to/pipeline/audit.md § "Stage bar and mid-run steering".
    """
    return tuple(
        finding
        for finding in snapshot.findings
        if is_blocking_finding(finding, stage=audit_stage, classify_domain=classify_domain)
        and not _is_resolved_in_run(snapshot.annotations.get(finding.id))
    )


def _finding_churn(
    history: ReportHistory,
    *,
    audit_stage: str,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
) -> FindingChurn | None:
    """Return a rising same-kind trajectory, if the newest run has one.

    Finding-identity matching (tiered by step focus/anchor/title) deliberately
    cannot see findings that relocate every audit — this signal covers that
    blind spot without becoming a verdict: it compares only the newest report
    with its immediate prior report of the same kind, and requires both the
    unresolved medium+ total *and* its severity ceiling to rise.
    """
    if not history.runs:
        return None
    latest = history.runs[-1]
    prior = next(
        (run for run in reversed(history.runs[:-1]) if run.kind == latest.kind),
        None,
    )
    if prior is None:
        return None
    prior_open = _open_medium_plus(
        prior, audit_stage=audit_stage, classify_domain=classify_domain
    )
    latest_open = _open_medium_plus(
        latest, audit_stage=audit_stage, classify_domain=classify_domain
    )
    if not prior_open or not latest_open or len(latest_open) <= len(prior_open):
        return None
    prior_ceiling = _max_severity_str([f.severity for f in prior_open]).lower()
    latest_ceiling = _max_severity_str([f.severity for f in latest_open]).lower()
    if _SEVERITY_RANK[latest_ceiling] <= _SEVERITY_RANK[prior_ceiling]:
        return None
    return FindingChurn(
        kind=latest.kind,
        prior_open_count=len(prior_open),
        latest_open_count=len(latest_open),
        prior_ceiling=prior_ceiling,
        latest_ceiling=latest_ceiling,
    )


def _code_drifted_since_prior(history: ReportHistory) -> bool:
    """True when code moved under the plan between the newest run and the prior
    run *of the same kind*.

    Same-kind so a completeness fingerprint is never diffed against a reconcile
    one (different watched-file sets → spurious drift). Gates on
    ``code_fingerprint_present`` (never dict truthiness, per DATA_CONTRACT): a
    computed-but-empty map is real evidence (docs-only plan), an uncomputed one
    is not. No same-kind prior → no baseline → ``False``.
    """
    if not history.runs:
        return False
    newest = history.runs[-1]
    prior = next(
        (r for r in reversed(history.runs[:-1]) if r.kind == newest.kind), None
    )
    if prior is None:
        return False
    if not (newest.code_fingerprint_present and prior.code_fingerprint_present):
        return False
    return newest.code_fingerprint != prior.code_fingerprint


def diagnose_convergence(
    history: ReportHistory,
    *,
    window: int = WINDOW_SIZE,
    audit_stage: str = STAGE_DETAIL,
    classify_domain: Optional[Callable[[RunFinding], str]] = None,
    mechanism_advisory_grade: str = GRADE_RUN,
) -> ConvergenceDiagnosis:
    """The entry point: a three-state verdict over a plan's report history.

    Builds a per-series :class:`SeriesDiagnosis` (in ``partition_series`` order)
    and rolls them into a worst-of headline. An empty history (no saved runs)
    reads whole-plan ``no-history``.

    Also records seven newest-run signals the verdict alone cannot carry —
    ``latest_blocking`` (the newest audit's critical/high findings),
    ``code_drift`` (code moved under the plan since the prior run),
    ``finding_churn`` (a same-kind rising open-finding trajectory),
    ``structural_recurrence`` (a full-window series whose same structural
    finding is still open unchanged), ``redecomposition_span`` (a
    full-window series whose runs span more than one known step-id set, BACKLOG
    #166), ``impact_recurrence`` (a high-impact
    seam recurring without shrinkage across compatible completeness passes),
    and ``edit_drift`` (a strict majority of new edit-drift-eligible findings
    matching the window-local prior-apply set) — so the render can surface
    loop-pattern advisories and run-readiness recommendations on an otherwise
    ``converging`` plan without changing the verdict.

    ``audit_stage`` / ``classify_domain`` feed :func:`_open_medium_plus` (via
    ``finding_churn``) and :func:`classify_edit_drift`; the impact-recurrence
    classifier reads persisted stage from collapsed passes only. When
    ``classify_domain`` is omitted, a shared default reads persisted
    ``RunFinding.domain`` (else ``"unknown"``) for *both* consumers so they
    cannot disagree on the same history. Pass an explicit callback (e.g.
    keyed off :attr:`RunFinding.domain`) to agree with what
    ``completeness-audit`` currently reports as blocking for the same plan.
    ``mechanism_advisory_grade`` gates only bare-mechanism presentation.
    """
    domain_fn = classify_domain or (lambda f: getattr(f, "domain", None) or "unknown")
    collapsed_passes = build_collapsed_completeness_passes(history)
    impact_recurrence = classify_impact_recurrence(
        history, window=window, passes=collapsed_passes
    )
    edit_drift = classify_edit_drift(
        history,
        window=window,
        classify_domain=domain_fn,
        passes=collapsed_passes,
    )
    bare_mechanism_findings = classify_bare_mechanism_advisory(
        history, grade=mechanism_advisory_grade, passes=collapsed_passes
    )
    series_runs = partition_series(history)
    if not series_runs:
        return ConvergenceDiagnosis(
            plan_slug=history.plan_slug,
            verdict=VERDICT_NO_HISTORY,
            window=window,
            series=(),
            impact_recurrence=impact_recurrence,
            edit_drift=edit_drift,
            bare_mechanism_findings=bare_mechanism_findings,
        )
    series = [
        _series_verdict(snapshots, window) for snapshots in series_runs.values()
    ]
    headline = max(series, key=lambda s: _VERDICT_RANK[s.verdict]).verdict
    return ConvergenceDiagnosis(
        plan_slug=history.plan_slug,
        verdict=headline,
        window=window,
        series=tuple(series),
        latest_blocking=_latest_blocking_findings(history),
        code_drift=_code_drifted_since_prior(history),
        finding_churn=_finding_churn(
            history, audit_stage=audit_stage, classify_domain=domain_fn
        ),
        structural_recurrence=tuple(s for s in series if s.structural_recurrence),
        redecomposition_span=tuple(
            s for s in series if s.redecomposition_step_counts
        ),
        impact_recurrence=impact_recurrence,
        edit_drift=edit_drift,
        bare_mechanism_findings=bare_mechanism_findings,
    )


def _series_breakdown_line(series: SeriesDiagnosis) -> str:
    """One per-series breakdown line: ``kind`` (and step for reconcile), verdict,
    and the series' own run count."""
    label = series.kind if series.step_id is None else f"{series.kind}/step {series.step_id}"
    audits = "audit" if series.run_count == 1 else "audits"
    return f"  {label}: {series.verdict} ({series.run_count} {audits})"


def _advisory_lines(diagnosis: ConvergenceDiagnosis) -> list[str]:
    """The run-readiness advisory the verdict alone can't make — never alters it.

    When code drifted, head and body stay coherent: it ties any blocking
    findings to the drift (likely stale-baseline artifacts) and recommends
    rebase-then-re-audit (``reconcile-plan``). With no drift it points at the
    saved report (the resolving command is source-dependent; the audit
    surface names it). The ``(breakdown)`` is shown only when blocking
    findings exist.
    """
    crit = sum(1 for f in diagnosis.latest_blocking if f.severity.lower() == "critical")
    high = sum(1 for f in diagnosis.latest_blocking if f.severity.lower() == "high")
    bits = ", ".join(f"{n} {label}" for n, label in ((crit, "critical"), (high, "high")) if n)
    signal = "Convergence is a loop/structure signal, not a run-readiness gate."
    if diagnosis.code_drift:
        head = (
            f"⚠ The latest audit surfaced unresolved blocking finding(s) ({bits}), "
            "and code moved under the plan since then — they may be stale-baseline "
            "artifacts."
            if bits
            else "⚠ Code moved under the plan since its last audit — it may be stale."
        )
        return [
            f"{head} {signal}",
            "  Rebase against current code, then re-audit, before running:",
            f"  plan-tool reconcile-plan {diagnosis.plan_slug}",
        ]
    # No drift (the render gate guarantees a blocking finding here).
    return [
        f"⚠ The latest audit surfaced unresolved blocking finding(s) ({bits}). {signal}",
        "  Resolve them before running — see the saved report.",
    ]


def _finding_churn_lines(churn: FindingChurn) -> list[str]:
    """Render the non-actuating trajectory signal beside the verdict."""
    return [
        "⚠ Open medium+ findings rose "
        f"from {churn.prior_open_count} to {churn.latest_open_count} and "
        f"the severity ceiling rose from {churn.prior_ceiling} to "
        f"{churn.latest_ceiling} across the latest two {churn.kind} audits.",
        "  Findings are churning without recurring; measure the source before "
        "adding another iteration. This is not a re-decomposition signal.",
    ]


def _impact_recurrence_seam_label(advisory: ImpactRecurrenceAdvisory) -> str:
    """Operator-facing seam identity for impact-recurrence render."""
    if advisory.seam_step_id is not None:
        focus = f"step {advisory.seam_step_id}"
    elif advisory.seam_anchor:
        focus = advisory.seam_anchor
    else:
        focus = advisory.seam_title_slug
    return f"{advisory.seam_source} ({focus})"


def _impact_recurrence_lines(
    advisory: ImpactRecurrenceAdvisory, *, window: int
) -> list[str]:
    """Render the high-impact seam recurrence advisory."""
    seam = _impact_recurrence_seam_label(advisory)
    return [
        "⚠ High-impact seam recurrence: the same seam "
        f"({seam}) recurred across {advisory.passes_present} of the last "
        f"{window} compatible completeness passes without shrinkage.",
        "  Surface this seam to the operator before another session-directed "
        "edit.",
        "  This is recommend-only and does not alter the convergence verdict "
        "or act as a run-readiness gate.",
    ]


_ADVISORY_TITLE_CAP: int = 3


def _capped_join(items: tuple, formatter) -> str:
    """Join at most :data:`_ADVISORY_TITLE_CAP` formatted items, noting any
    omitted remainder."""
    shown = items[:_ADVISORY_TITLE_CAP]
    joined = "; ".join(formatter(item) for item in shown)
    remainder = len(items) - len(shown)
    return f"{joined}; and {remainder} more" if remainder else joined


def _capped_finding_titles(findings: tuple[RunFinding, ...]) -> str:
    """Render at most :data:`_ADVISORY_TITLE_CAP` finding titles."""
    return _capped_join(findings, lambda finding: f'"{finding.title}"')


def _capped_finding_confidence_labels(findings: tuple[RunFinding, ...]) -> str:
    """Render canonical confidence labels for finding titles in an advisory."""
    return _capped_join(
        findings,
        lambda finding: f"{finding.title}: {confidence_label(finding.confidence)}",
    )


def _edit_drift_lines(
    advisory: EditDriftAdvisory,
    *,
    named_findings: tuple[RunFinding, ...] | None = None,
) -> list[str]:
    """Render the edit-drift self-seeding advisory."""
    selected_findings = (
        advisory.matched_findings if named_findings is None else named_findings
    )
    names = _capped_finding_titles(selected_findings)
    confidence = _capped_finding_confidence_labels(selected_findings)
    return [
        "⚠ Edit drift: a strict majority of new edit-drift-eligible findings "
        f"in the newest pass matched the prior-apply set "
        f"({advisory.matched_count} of {advisory.new_eligible_count}).",
        f"  Matched findings: {names}.",
        f"  Evidence support: {confidence}.",
        "  Further session-directed edits may be auditing your edits rather "
        "than gaps in "
        "the original artifact.",
        "  This is recommend-only and does not alter the convergence verdict "
        "or act as a run-readiness gate.",
    ]


def compose_mechanism_edit_drift_advisory_lines(
    mechanism_findings: tuple[RunFinding, ...],
    edit_drift: EditDriftAdvisory | None,
) -> list[str]:
    """Compose bare-mechanism and edit-drift advice by exact current id."""
    drift_ids = (
        {finding.id for finding in edit_drift.matched_findings}
        if edit_drift is not None
        else set()
    )
    combined = tuple(
        finding for finding in mechanism_findings if finding.id in drift_ids
    )
    combined_ids = {finding.id for finding in combined}
    standalone = tuple(
        finding for finding in mechanism_findings if finding.id not in combined_ids
    )
    lines: list[str] = []
    if combined:
        names = _capped_finding_titles(combined)
        confidence = _capped_finding_confidence_labels(combined)
        assert edit_drift is not None
        lines.extend(
            [
                "⚠ Bare-plan mechanism and edit-drift advisory: current finding(s) "
                f"{names} look likely mechanism-only and matched the prior-apply "
                f"comparison ({edit_drift.matched_count} of "
                f"{edit_drift.new_eligible_count}).",
                f"  Evidence support: {confidence}.",
                "  The comparison is not causal proof; check whether the plan should "
                "state an observable property instead or leave the delivery choice to "
                "detail.",
                "  This is recommend-only and does not alter the convergence verdict "
                "or act as a run-readiness gate.",
            ]
        )
    if standalone:
        names = _capped_finding_titles(standalone)
        confidence = _capped_finding_confidence_labels(standalone)
        lines.extend(
            [
                "⚠ Bare-plan mechanism advisory: current finding(s) "
                f"{names} look likely mechanism-only.",
                f"  Evidence support: {confidence}.",
                "  Check whether the plan should state an observable property instead "
                "or leave the delivery choice to detail.",
                "  This is recommend-only and does not alter the convergence verdict "
                "or act as a run-readiness gate.",
            ]
        )
    if edit_drift is not None:
        remainder = tuple(
            finding
            for finding in edit_drift.matched_findings
            if finding.id not in combined_ids
        )
        if remainder:
            lines.extend(_edit_drift_lines(edit_drift, named_findings=remainder))
    return lines


def _structural_recurrence_lines(series: tuple[SeriesDiagnosis, ...]) -> list[str]:
    """Render the full-window structural-recurrence advisory.

    Unlike :func:`_finding_churn_lines`, this *is* a re-decomposition signal —
    it is the narrow, non-actuating remainder of the retired ``spinning``
    verdict (BACKLOG #251): the same structural finding held open, unchanged,
    across the whole trailing window the ``converging`` headline just
    certified.
    """
    labels = ", ".join(
        s.kind if s.step_id is None else f"{s.kind}/step {s.step_id}" for s in series
    )
    return [
        f"⚠ A structural finding recurred across the trailing window without "
        f"resolving, on: {labels}.",
        "  Certified converging on run count/fingerprint alone; consider "
        "re-splitting the step or `plan-tool scope-out` rather than patching "
        "again.",
    ]


def _redecomposition_span_lines(series: tuple[SeriesDiagnosis, ...]) -> list[str]:
    """Render the re-decomposition span advisory (BACKLOG #166).

    A fact for the operator to judge, not a verdict: the trailing window's
    runs carried different step-id sets, so this ``converging`` certification
    may span materially different plan versions — or may just be an ordinary
    one-step change. The compact counts give useful context. Never excludes a
    run or changes the headline.
    """
    lines: list[str] = []
    for s in series:
        label = s.kind if s.step_id is None else f"{s.kind}/step {s.step_id}"
        counts = " → ".join(str(c) for c in s.redecomposition_step_counts)
        lines.append(
            f"⚠ {label}: the trailing window's step IDs varied across runs "
            f"(step counts: {counts}) — this verdict may span a re-decomposition."
        )
    lines.append(
        "  Certified converging on run count/fingerprint alone; check "
        "whether these are the same plan before trusting the trend."
    )
    return lines


def render_diagnosis(diagnosis: ConvergenceDiagnosis) -> str:
    """The full printable block the CLI emits with one ``print(...)``.

    A three-state headline (read straight off the diagnosis — the slug is
    never recomputed) plus a per-series breakdown. On any verdict, a
    newest-run critical/high finding or code drift appends a run-readiness
    advisory (see :func:`_advisory_lines`), a rising open-medium+ trajectory
    appends a churn advisory (see :func:`_finding_churn_lines`), a
    full-window recurring structural finding appends a re-decomposition
    advisory (see :func:`_structural_recurrence_lines`), a full-window
    series whose runs span more than one known step-id set appends a
    re-decomposition span advisory (see :func:`_redecomposition_span_lines`,
    BACKLOG #166), a recurring high-impact seam appends an impact-recurrence
    advisory (see :func:`_impact_recurrence_lines`), and the shared
    bare-mechanism/edit-drift composer appends their recommend-only advice;
    none alters the headline.
    """
    lines: list[str] = [
        f"convergence: {diagnosis.verdict} — {diagnosis.plan_slug} "
        f"(window {diagnosis.window})"
    ]
    lines.extend(_series_breakdown_line(s) for s in diagnosis.series)

    if diagnosis.verdict == VERDICT_NO_HISTORY:
        lines.append(
            "No eligible ordinary-final completeness or reconcile history "
            "sidecars are saved yet; the diagnostic needs at least "
            f"{diagnosis.window} separate invocations before it has signal."
        )
    elif diagnosis.verdict == VERDICT_INSUFFICIENT_HISTORY:
        runs = max(
            (s.run_count for s in diagnosis.series if s.verdict == VERDICT_INSUFFICIENT_HISTORY),
            default=0,
        )
        lines.append(
            f"Not enough data yet — {runs} of {diagnosis.window} audits; "
            "re-run the audit/apply loop to build history."
        )
    elif diagnosis.verdict == VERDICT_CONVERGING:
        lines.append("The audit/apply loop is converging; no re-decomposition needed.")

    # Trajectory advisory: finding-identity matching cannot see a relocating
    # finding set. Deliberately never affects the verdict.
    if diagnosis.finding_churn is not None:
        lines.extend(_finding_churn_lines(diagnosis.finding_churn))

    # Re-decomposition advisory: a full-window series whose same structural
    # finding never resolved. Deliberately never affects the verdict.
    if diagnosis.structural_recurrence:
        lines.extend(_structural_recurrence_lines(diagnosis.structural_recurrence))

    # Re-decomposition span advisory (BACKLOG #166): a full-window series
    # whose runs carried different step-id sets. Deliberately never affects
    # the verdict or excludes a run — see _redecomposition_span_lines.
    if diagnosis.redecomposition_span:
        lines.extend(_redecomposition_span_lines(diagnosis.redecomposition_span))

    # Loop-pattern advisories: high-impact seam recurrence, then the shared
    # mechanism/edit-drift composition. Deliberately never affect the verdict.
    if diagnosis.impact_recurrence is not None:
        lines.extend(
            _impact_recurrence_lines(
                diagnosis.impact_recurrence, window=diagnosis.window
            )
        )
    lines.extend(
        compose_mechanism_edit_drift_advisory_lines(
            diagnosis.bare_mechanism_findings, diagnosis.edit_drift
        )
    )

    # Run-readiness advisory: a fresh blocking finding or code drift.
    if diagnosis.latest_blocking or diagnosis.code_drift:
        lines.extend(_advisory_lines(diagnosis))

    return "\n".join(lines)


def _render_saved_mapping(values: Mapping[str, object]) -> str:
    """Render a saved metadata projection without inspecting its source artifact."""
    return json.dumps(dict(values), sort_keys=True, default=str)


def _render_audit_evidence_row(row: AuditEvidenceRow) -> list[str]:
    """Render one already-classified ledger row without deriving new state."""
    metadata = row.saved_metadata
    paths: list[tuple[str, Path]] = []
    if row.report_path is not None:
        paths.append(("report path", row.report_path))
    if row.sidecar_path is not None:
        paths.append(("sidecar path", row.sidecar_path))
    if not paths:
        paths.append(("artifact path", Path("unknown")))

    lines = [f"  {row.state}: filename time {row.filename_time}"]
    lines.extend(f"    {label}: {path}" for label, path in paths)
    lines.extend(
        [
            "    saved metadata: "
            f"created at={metadata.created_at}; "
            f"pre-apply checkpoint={metadata.is_pre_apply_checkpoint}; "
            f"audit stage={metadata.audit_stage}; "
            f"audit revision grade={metadata.audit_revision_grade}",
            "    qualified result: "
            f"headline={metadata.qualified_result['headline']}; "
            f"stage={metadata.qualified_result['stage']}; "
            f"coverage={metadata.qualified_result['coverage']}; "
            f"revision status={metadata.qualified_result['revision_status']}",
            f"    audit coverage: {_render_saved_mapping(metadata.audit_coverage)}",
            f"    next action: {row.next_action}",
        ]
    )
    return lines


def render_audit_evidence_ledger(ledger: AuditEvidenceLedger) -> str:
    """Render saved audit evidence without changing convergence diagnosis input."""
    lines = [f"saved audit evidence ledger: {ledger.plan_slug}"]
    if not ledger.rows:
        lines.extend(
            [
                "  no-saved-audits: no saved completeness-audit artifacts.",
                "    next action: Run a completeness audit to save structured evidence.",
            ]
        )
        return "\n".join(lines)

    for row in ledger.rows:
        lines.extend(_render_audit_evidence_row(row))
    return "\n".join(lines)
