"""Completeness report assembly + persistence.

``cmd_completeness --iterate`` produces a lot of findings across several
dispositions — the deterministic well-formedness findings get *applied*,
others are *deferred* (structural diagnostics that an apply pass can't
fix, info-severity advisories, triage-deferred low-payoff edits) and both
conceptual sources (*correctness* and *completeness*) are *reported but
never auto-applied by design* (read-only-audit split, #85 — they are
walked by ``completeness-apply``). Dumping all of that to the terminal
buries the signal and can't be reused later.

So the full detail is written to a reusable markdown artifact under
``<plan-dir>/plan-details/<slug>/reports/<ts>-completeness.md`` (same tree as
saved reviews), and the terminal gets a concise summary plus the report
path. Crucially, the report states *why* each non-applied finding was
not addressed — especially the conceptual-completeness gaps, which are
the ones a reader is most likely to wonder about.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from plan_tool.audit_shapes import (
    AuditShapeAdvisory,
    is_advisory_emitter_eligible,
    is_well_formed_audit_shape_advisory,
)
from plan_tool.detail_artifacts import (
    DetailFormatError,
    derive_detail_path,
    require_supported_detail_format_version,
)
from plan_tool.locator import slug_from_filename
from plan_tool.fileio import durable_write_text
from plan_tool.fingerprint import compute_code_fingerprint, diff_code_fingerprint
from plan_tool.jira_grade import GRADE_JIRA, GRADE_RUN
from plan_tool.parser import ParseError, ValidationError, parse_plan
from plan_tool.schema import ChangeType, StepScope
from plan_tool.telemetry import read_step_provenance_titles
from plan_tool.review import (
    indent_bullet_body,
    CONCEPT_BUCKET_MISSING_SOURCE,
    CONCEPT_LEGACY_STALE_SOURCE,
    CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
    RESTATED_PROPERTY_LABEL,
    Recommendation,
    confidence_label,
    is_apply_eligible,
    restated_property_or_none,
    should_apply_by_triage,
)
from plan_tool.review_persistence import (
    COMPLETENESS_ARTIFACT_STEM_SUFFIX,
    COMPLETENESS_REPORT_SUFFIX,
    COMPLETENESS_SIDECAR_SUFFIX,
    ReviewLoadError,
    SavedReview,
    compute_plan_fingerprint,
    list_saved_reviews,
    load_review,
    normalize_audit_coverage,
    plan_reports_dir,
    project_audit_coverage,
    save_review,
)
from plan_tool.review_walk import stamp_target_signatures
# ``compute_code_fingerprint`` now lives in the shared
# ``plan_tool.fingerprint`` leaf so the reconcile family can reach it
# without importing this module; it is re-exported here (imported above)
# so ``resolve_reusable_audit`` and existing callers keep working.


DETAIL_LEVEL_DIAGNOSTIC_SOURCES = {"detail-coverage", "files-coherence"}
DETAIL_LEVEL_FINDING_SOURCES = DETAIL_LEVEL_DIAGNOSTIC_SOURCES | {"detail-body"}
_QUALIFIED_RESULT_UNSET = object()
BLOCKING_STATE_SET = "set"
BLOCKING_STATE_INCOMPLETE = "incomplete"
BLOCKING_STATE_ABSENT = "absent"
# Why an ``incomplete`` verdict is untrusted. ``transient``: the run was cut
# short, so re-auditing continues it. ``persistent``: re-auditing unchanged
# text reproduces the same result, so the reader prescribes hand triage first.
UNTRUSTED_TRANSIENT = "transient"
UNTRUSTED_PERSISTENT = "persistent"
# ``stale-revision``: no current audit evidence for this text (changed, legacy,
# or never sampled), so the reader prescribes a fresh audit, not triage.
UNTRUSTED_STALE_REVISION = "stale-revision"
# What an operator reads for each cause (the enum names are internal).
_CAUSE_PHRASES = {
    UNTRUSTED_TRANSIENT: "the audit stopped early",
    UNTRUSTED_PERSISTENT: "re-auditing unchanged text reproduces this",
    UNTRUSTED_STALE_REVISION: "no current audit evidence for this text",
}


@dataclass(frozen=True)
class DeterministicArmFinding(Recommendation):
    """The one synthetic finding an issue-object deterministic arm contributes:
    it names a failing check, not a counted gap (marked by type, not by id)."""


@dataclass(frozen=True)
class BlockingVerdict:
    """The gate's own blocking answer, carried as plain data.

    ``set``: the gate established its result; ``blocking_ids`` (conceptual-bar
    ids) plus ``blocking_deterministic`` (blocking deterministic findings with
    no conceptual id) are the set, possibly empty. ``incomplete``: the gate
    could not certify its result but keeps every id and deterministic finding
    it computed (they name gaps to close); ``untrusted_cause`` says why
    (``transient``, ``persistent``, or ``stale-revision``), and an
    ``incomplete`` verdict never offers a stage. ``absent``: no verdict was
    supplied and no ids exist. Only a ``set`` with both collections empty means
    nothing blocks.
    """

    state: str
    blocking_ids: tuple[str, ...] = ()
    blocking_deterministic: tuple[Recommendation, ...] = ()
    untrusted_cause: str = ""

    @property
    def is_completed_empty_set(self) -> bool:
        return (
            self.state == BLOCKING_STATE_SET
            and not self.blocking_ids
            and not self.blocking_deterministic
        )

    @property
    def blocking_count(self) -> int:
        """Gaps a reader names to close: a ``stale-revision`` verdict's ids
        describe changed text and are advisory, so only deterministic blockers
        count (matching :func:`next_step_gaps`)."""
        ids = (
            0 if self.untrusted_cause == UNTRUSTED_STALE_REVISION
            else len(self.blocking_ids)
        )
        return ids + len(self.blocking_deterministic) - self.blocking_arm_count

    @property
    def blocking_arm_count(self) -> int:
        """Synthetic deterministic-arm findings: failing checks, not gaps."""
        return sum(
            1 for rec in self.blocking_deterministic
            if isinstance(rec, DeterministicArmFinding)
        )


# An omitted verdict reads as ``absent``: no stage transition is offered.
ABSENT_BLOCKING_VERDICT = BlockingVerdict(state=BLOCKING_STATE_ABSENT)


def blocking_verdict_from_gate(
    blocking_ids,
    blocking_deterministic=(),
    *,
    untrusted_cause: str = "",
) -> BlockingVerdict:
    """Wrap the gate's own ids and deterministic findings, unfiltered.

    A non-empty ``untrusted_cause`` makes the verdict ``incomplete``."""
    return BlockingVerdict(
        state=BLOCKING_STATE_INCOMPLETE if untrusted_cause else BLOCKING_STATE_SET,
        blocking_ids=tuple(blocking_ids),
        blocking_deterministic=tuple(blocking_deterministic),
        untrusted_cause=untrusted_cause,
    )


def _verdict_offers_stage(verdict) -> bool:
    """Whether a stage transition may be offered: only a completed empty set
    offers one; ``absent``, ``incomplete``, and ``None`` hold it."""
    return isinstance(verdict, BlockingVerdict) and verdict.is_completed_empty_set


def _reaudit_command(
    plan_name: str, verdict, *, detail_grade: str = GRADE_RUN, also=()
) -> tuple[str, str]:
    """The one re-audit a reader names; it carries the audit's grade.

    Run grade always passes ``--iterate`` (repo mandate); jira grade never does.
    The description states why the verdict is open, merged with any ``also``
    reasons a reader adds. A persistent untrusted cause (re-auditing unchanged
    text reproduces it) prescribes hand triage before the re-audit."""
    reasons: list[str] = []
    if not _verdict_offers_stage(verdict):
        count = verdict.blocking_count if isinstance(verdict, BlockingVerdict) else 0
        arms = verdict.blocking_arm_count if isinstance(verdict, BlockingVerdict) else 0
        lead = f"{count} blocking gap(s) open — " if count else ""
        if arms:
            lead += f"{arms} deterministic check(s) failing — "
        if not isinstance(verdict, BlockingVerdict) or verdict.state == BLOCKING_STATE_ABSENT:
            reasons.append("blocking verdict unavailable — re-audit to establish it")
        elif verdict.state == BLOCKING_STATE_SET:
            reasons.append(f"{lead}re-audit after the session-directed edit")
        elif verdict.untrusted_cause == UNTRUSTED_STALE_REVISION:
            reasons.append(
                f"{lead}no current audit evidence for this text — run a fresh audit"
            )
        elif verdict.untrusted_cause == UNTRUSTED_PERSISTENT:
            reasons.append(
                f"{lead}re-auditing unchanged text reproduces this result — "
                "triage the saved report's findings, correct them in a "
                "session-directed edit, commit, then re-audit the changed snapshot"
            )
        else:
            reasons.append(f"{lead}the audit stopped early — re-audit to continue")
    reasons.extend(also)
    command = f"plan-tool completeness-audit {plan_name}"
    command += f" --grade {GRADE_JIRA}" if detail_grade == GRADE_JIRA else " --iterate"
    return command, "; ".join(reasons)


@dataclass(frozen=True)
class NextStepGaps:
    """Gaps a reader must close versus list as advisory, by the verdict alone."""

    close_correctness: tuple[Recommendation, ...] = ()
    close_completeness: tuple[Recommendation, ...] = ()
    close_deterministic: tuple[Recommendation, ...] = ()
    advisory_correctness: tuple[Recommendation, ...] = ()
    advisory_completeness: tuple[Recommendation, ...] = ()
    unlisted_blocking: int = 0  # blocking ids with no listed finding
    # The verdict's ids were demoted to advisory because the text they judged
    # has no current evidence: they were blocking, and are unverified now.
    demoted_stale: bool = False

    @property
    def close_conceptual_count(self) -> int:
        return len(self.close_correctness) + len(self.close_completeness)

    @property
    def advisory_count(self) -> int:
        return len(self.advisory_correctness) + len(self.advisory_completeness)

    @property
    def close_count(self) -> int:
        return (
            self.close_conceptual_count
            + self.unlisted_blocking
            + len(self.close_deterministic)
        )


def next_step_gaps(verdict, *, correctness=(), advisory_conceptual=()) -> NextStepGaps:
    """Split listed conceptual findings into close / advisory by ``verdict``.

    A ``set`` or ``incomplete`` verdict puts its ids to close (``incomplete``
    keeps what the audit established); ``absent`` has no ids. Deterministic
    blockers always close. A ``stale-revision`` verdict describes changed
    text, so its conceptual ids are advisory, not text to close."""
    deterministic = (
        tuple(verdict.blocking_deterministic)
        if isinstance(verdict, BlockingVerdict)
        else ()
    )
    ids = (
        set(verdict.blocking_ids)
        if isinstance(verdict, BlockingVerdict)
        and verdict.state != BLOCKING_STATE_ABSENT
        and verdict.untrusted_cause != UNTRUSTED_STALE_REVISION
        else set()
    )
    close_c = tuple(r for r in correctness if r.id in ids)
    close_x = tuple(r for r in advisory_conceptual if r.id in ids)
    return NextStepGaps(
        close_correctness=close_c,
        close_completeness=close_x,
        close_deterministic=deterministic,
        advisory_correctness=tuple(r for r in correctness if r.id not in ids),
        advisory_completeness=tuple(r for r in advisory_conceptual if r.id not in ids),
        unlisted_blocking=max(0, len(ids) - len(close_c) - len(close_x)),
        demoted_stale=(
            isinstance(verdict, BlockingVerdict)
            and verdict.untrusted_cause == UNTRUSTED_STALE_REVISION
        ),
    )


def _blocking_deterministic_steps(verdict, *, covered_sources=()) -> list[str]:
    """One prose step per blocking deterministic finding the verdict carries,
    except those whose ``source`` a reader's own remedy bullet already covers."""
    if not isinstance(verdict, BlockingVerdict):
        return []
    covered = set(covered_sources)
    return [
        f"Close the blocking `{rec.source}` finding ({rec.severity}) directly — "
        f"{(rec.title or rec.body or '').strip()}"
        for rec in verdict.blocking_deterministic
        if rec.source not in covered
    ]


def _detail_authoring_command(plan_name: str, *, detail_grade: str) -> str:
    """Return the detail writer command for the selected artifact grade."""
    if detail_grade == GRADE_JIRA:
        return f"plan-tool detail {plan_name} --grade {GRADE_JIRA}"
    return f"plan-tool detail {plan_name}"


def _qualified_result_payload(qualified_result) -> Optional[dict[str, object]]:
    """Return a JSON-shaped result without reclassifying its decision."""
    if hasattr(qualified_result, "as_dict"):
        qualified_result = qualified_result.as_dict()
    return qualified_result if isinstance(qualified_result, dict) else None


def render_qualified_result_markdown(
    qualified_result,
    *,
    is_pre_apply_checkpoint: bool = False,
    view_revision_status: Optional[str] = None,
    heading: str = "##",
) -> str:
    """Render the shared audit decision and its immutable provenance."""
    if is_pre_apply_checkpoint:
        return (
            f"{heading} Recovery evidence\n\n"
            "This pre-apply checkpoint preserves findings for recovery; it is "
            "not a final qualified audit result."
        )
    result = _qualified_result_payload(qualified_result)
    if result is None:
        return (
            f"{heading} Audit result\n\n"
            "- **Result:** `no-qualified-current-evidence`\n"
            "- **Qualification:** unavailable"
        )
    lines = [
        f"{heading} Audit result",
        "",
        f"- **Result:** `{result['headline']}`",
        f"- **Coverage:** `{result['coverage']}`",
        f"- **Audit revision:** `{result['revision_status']}`",
        f"- **Audit stage:** `{result['stage']}`",
    ]
    if view_revision_status is not None:
        lines.append(f"- **Current artifact view:** `{view_revision_status}`")
    revision = result["audit_revision"]
    if revision is None:
        lines.append("- **Audited plan/detail revision:** not captured")
    else:
        lines.extend(
            [
                f"- **Plan digest:** `{revision['plan_digest']}`",
                f"- **Detail bundle digest:** `{revision['detail_bundle_digest']}`",
                f"- **Detail grade:** `{revision['detail_grade']}`",
            ]
        )
    return "\n".join(lines)


@dataclass(frozen=True)
class AuditShapeAdvisoryDisplay:
    """Fresh, presentation-only view of a stored audit-shape advisory.

    The saved payload remains the source of truth. This record adds only step
    titles from the plan whose exact audit-input fingerprint matched it, plus
    anchor slugs grouped by the audit axis. It intentionally excludes finding
    bodies and opaque finding IDs so rendering cannot create a second finding
    transport or influence the saved-finding walk.
    """

    shape_id: str
    source_plan_fingerprint: str
    arm_steps: tuple[tuple[int, str], ...]
    material_finding_count: int
    arm_finding_count: int
    committed_step_count: int
    anchor_groups: tuple[tuple[str, tuple[str, ...]], ...]


_ADVISORY_AXIS_LABELS = {
    "plan-correctness": "Correctness",
    "plan-completeness": "Completeness",
}
_MAX_ADVISORY_ANCHORS_PER_AXIS = 8


def prepare_audit_shape_advisory_display(
    advisory: Optional[AuditShapeAdvisory],
    *,
    plan,
    plan_path: Path,
    repo_root: Path,
    detail_grade: str = GRADE_RUN,
) -> Optional[AuditShapeAdvisoryDisplay]:
    """Return a renderable advisory only when its captured inputs are current.

    Freshness intentionally uses the dedicated audit-input snapshot rather
    than the broader saved-review fingerprint. A malformed optional advisory
    is already loaded as ``None``; any missing plan step or unrecognised audit
    axis also fails closed so ordinary findings stay usable without displaying
    ungrounded shape advice.
    """
    if (
        detail_grade != GRADE_RUN
        or advisory is None
        or not is_advisory_emitter_eligible(advisory.shape_id)
    ):
        return None

    committed_step_ids = tuple(
        step.id for step in plan.steps if step.scope is StepScope.COMMITTED
    )
    if not is_well_formed_audit_shape_advisory(
        advisory, declared_step_ids=committed_step_ids
    ):
        return None

    from plan_tool.review_persistence import audit_input_fingerprint_matches_disk

    if not audit_input_fingerprint_matches_disk(
        plan_path, repo_root, advisory.source_plan_fingerprint
    ):
        return None

    steps_by_id = {step.id: step for step in plan.steps}
    try:
        arm_steps = tuple(
            (step_id, steps_by_id[step_id].title)
            for step_id in advisory.arm_step_ids
        )
    except KeyError:
        return None
    if not arm_steps:
        return None

    anchors_by_axis: dict[str, list[str]] = {}
    for evidence in advisory.material_finding_evidence:
        label = _ADVISORY_AXIS_LABELS.get(evidence.source)
        if label is None:
            return None
        if not evidence.anchor:
            continue
        anchors = anchors_by_axis.setdefault(label, [])
        if evidence.anchor not in anchors:
            anchors.append(evidence.anchor)

    anchor_groups = tuple(
        (label, tuple(anchors[:_MAX_ADVISORY_ANCHORS_PER_AXIS]))
        for label, anchors in anchors_by_axis.items()
    )
    return AuditShapeAdvisoryDisplay(
        shape_id=advisory.shape_id,
        source_plan_fingerprint=advisory.source_plan_fingerprint,
        arm_steps=arm_steps,
        material_finding_count=advisory.material_finding_count,
        arm_finding_count=advisory.arm_finding_count,
        committed_step_count=advisory.committed_step_count,
        anchor_groups=anchor_groups,
    )


def _advisory_arm_steps(display: AuditShapeAdvisoryDisplay) -> str:
    return "; ".join(
        f"{step_id} — {title}" for step_id, title in display.arm_steps
    )


def render_audit_shape_advisory_markdown(
    display: AuditShapeAdvisoryDisplay, *, heading: str = "##"
) -> str:
    """Render the evidence-bearing, non-blocking keep-or-carve prompt."""
    lines = [f"{heading} Audit shape advisory — `{display.shape_id}`", ""]
    lines.extend(
        [
            "Material conceptual findings concentrate in one contiguous plan "
            "arm. Decide whether that arm belongs in this plan or should be "
            "carved into a separate plan.",
            "",
            f"- **Arm steps:** {_advisory_arm_steps(display)}",
            (
                f"- **Stored evidence:** {display.arm_finding_count} of "
                f"{display.material_finding_count} material finding(s) map to "
                f"this arm across {display.committed_step_count} committed "
                "step(s)."
            ),
        ]
    )
    for axis, anchors in display.anchor_groups:
        lines.append(
            f"- **{axis} anchors:** "
            + ", ".join(f"`[{anchor}]`" for anchor in anchors)
        )
    lines.extend(
        [
            "",
            "**Keep or carve?** Continuing with the current arm overrides "
            "this signal. It is non-blocking and does not change the apply "
            "queue.",
        ]
    )
    return "\n".join(lines)


def render_audit_shape_advisory_console(
    display: AuditShapeAdvisoryDisplay,
) -> str:
    """Compact parent-process presentation for apply and iterate output."""
    lines = [
        f"plan-tool: audit shape `{display.shape_id}` — keep or carve?",
        f"  arm       {_advisory_arm_steps(display)}",
        (
            f"  evidence  {display.arm_finding_count}/"
            f"{display.material_finding_count} material finding(s) across "
            f"{display.committed_step_count} committed step(s)"
        ),
    ]
    for axis, anchors in display.anchor_groups:
        lines.append(
            f"  {axis.lower()}  "
            + ", ".join(f"[{anchor}]" for anchor in anchors)
        )
    lines.append(
        "  continuing with the current arm overrides this non-blocking signal"
    )
    return "\n".join(lines)


def audit_shape_advisory_json(display: AuditShapeAdvisoryDisplay) -> dict:
    """Public JSON form of the same display data, without finding prose/IDs."""
    return {
        "shape_id": display.shape_id,
        "source_plan_fingerprint": display.source_plan_fingerprint,
        "arm_steps": [
            {"id": step_id, "title": title}
            for step_id, title in display.arm_steps
        ],
        "material_finding_count": display.material_finding_count,
        "arm_finding_count": display.arm_finding_count,
        "committed_step_count": display.committed_step_count,
        "evidence": [
            {"axis": axis.lower(), "anchors": list(anchors)}
            for axis, anchors in display.anchor_groups
        ],
    }


# --- Pending concept decisions (the one shared filter) -------------------
# A concept deferral is recorded now and confirmed later; between record and
# confirm the operator needs a standing reminder of what is waiting. These are
# the ``check_concept_coverage`` finding sources that carry such a pending,
# still-needs-a-human decision. Single-sourced here so status, the completeness
# report, and the create run-summary line all key on one predicate — no surface
# re-derives it. Render order is fixed: unsigned deferrals first (the common
# parked decision), then missing-bucket re-reviews, then the legacy re-sync
# advisory. All three are non-blocking.
_PENDING_DECISION_ORDER: tuple[str, ...] = (
    CONCEPT_UNSIGNED_DEFERRAL_SOURCE,
    CONCEPT_BUCKET_MISSING_SOURCE,
    CONCEPT_LEGACY_STALE_SOURCE,
)

PENDING_DECISION_SOURCES: "frozenset[str]" = frozenset(_PENDING_DECISION_ORDER)

# Human label per pending source (the report groups by these; status groups
# flat nodes by their section bucket instead — see ``_print_status``).
_PENDING_DECISION_LABELS: dict[str, str] = {
    CONCEPT_UNSIGNED_DEFERRAL_SOURCE: (
        "Unsigned deferrals — a proposed defer/wont_do not yet reviewed"
    ),
    CONCEPT_BUCKET_MISSING_SOURCE: (
        "Missing-bucket re-reviews — the decision's section was renamed/deleted"
    ),
    CONCEPT_LEGACY_STALE_SOURCE: (
        "Legacy record — needs re-sync before coverage can be re-checked"
    ),
}


@dataclass(frozen=True)
class PendingDecisionGroup:
    """One labeled bucket of pending concept-decision findings, in the fixed
    render order. ``recs`` is always non-empty (empty buckets are dropped).
    Every group resolves with ``plan-tool scope-review``."""

    source: str
    label: str
    recs: list[Recommendation]


def group_pending_decisions(
    recs: list[Recommendation],
) -> list[PendingDecisionGroup]:
    """Keep only the pending-decision sources and split them into ordered,
    labeled buckets. Pure — takes a rec list and returns groups, no disk
    access — so status, the report, and create all group the same way."""
    groups: list[PendingDecisionGroup] = []
    for source in _PENDING_DECISION_ORDER:
        bucket = [r for r in recs if r.source == source]
        if bucket:
            groups.append(
                PendingDecisionGroup(
                    source=source,
                    label=_PENDING_DECISION_LABELS[source],
                    recs=bucket,
                )
            )
    return groups


def pending_concept_id(rec: Recommendation) -> str:
    """The bare concept id — the token ``scope-review --concept`` consumes —
    for a pending finding: its ``anchor`` (``concept-{id}``) with the
    ``concept-`` prefix stripped, else the raw id.

    Returns ``""`` for the record-wide ``concept-legacy-stale`` advisory: it
    describes the whole drifted record, not one node, so it carries no
    ``--concept`` token (its anchor is the literal ``concept-legacy-stale``,
    which would otherwise strip to a bogus ``legacy-stale`` id)."""
    if rec.source == CONCEPT_LEGACY_STALE_SOURCE:
        return ""
    anchor = rec.anchor or ""
    prefix = "concept-"
    if anchor.startswith(prefix):
        return anchor[len(prefix):]
    return anchor or rec.id


@dataclass
class ReusableAudit:
    """A located saved completeness sidecar plus its freshness verdict.

    Produced by :func:`resolve_reusable_audit` — the read/verdict seam
    that step 6's CLI reuse decision consumes. ``fresh`` is the sampled
    plan/detail revision verdict; code stays live audit context. ``plan_match``
    / ``code_match`` remain exposed so callers can present their distinct
    metadata without treating a code-fingerprint change as plan-result drift.
    ``drifted_code`` is absolute, resolved, sorted content-digest changes
    only (intersection of saved and current fingerprints).
    """

    saved: SavedReview  # the loaded sidecar (carries both fingerprints)
    correctness_recs: list[Recommendation]  # source == "plan-correctness"
    conceptual_recs: list[Recommendation]  # source == "plan-completeness"
    fresh: bool  # audit_revision_match; code remains live explanation context
    plan_match: bool  # captured plan + selected detail revision matches current
    code_match: bool  # code fingerprint computed and saved→current maps identical
    drifted_code: list[Path]  # abs resolved sorted paths with content digest changes
    audit_coverage: dict[str, object] = field(
        default_factory=lambda: project_audit_coverage(None)
    )  # observed coverage or unknown-legacy
    footprint_added: list[Path] = field(default_factory=list)
    footprint_removed: list[Path] = field(default_factory=list)
    audit_revision_match: bool = False


def is_reusable_audit_sidecar(saved: SavedReview) -> bool:
    """Whether a loaded sidecar may supply a reused completeness audit.

    Only the loaded payload decides: a ``kind="completeness"`` sidecar whose
    persisted role is the ordinary final one (``False`` — an unmarked legacy
    save or a raw version-3 ``false``). A confirmed pre-apply checkpoint
    captures findings before the apply work finishes, and an unknown role is
    metadata no reader may trust as final, so both fail closed. See
    DATA_CONTRACT.md § ``SavedReview`` for the role states.
    """
    return saved.kind == "completeness" and saved.is_pre_apply_checkpoint is False


def resolve_reusable_audit(
    plan_slug: str,
    repo_root: Path,
    *,
    plan_path: Path,
    review_id: Optional[str] = None,
    audit_input_snapshot=None,
) -> Optional[ReusableAudit]:
    """Locate the newest completeness sidecar (or the one pinned by
    ``review_id``), recompute both fingerprints against current disk, and
    return a :class:`ReusableAudit` freshness verdict — or ``None`` when no
    sidecar resolves.

    This is the pure read/verdict half of reuse. It compares the saved
    grade-aware audit revision with one current capture, then exposes the
    legacy code fingerprint separately for report metadata. It issues zero
    Claude calls and does not prompt, warn, or touch the CLI.

    Eligibility is decided by the loaded payload, never the filename: only a
    ``kind="completeness"`` ordinary-final sidecar
    (:func:`is_reusable_audit_sidecar`) can be reused. A pre-apply checkpoint
    or an unknown role is skipped outright rather than returned as a stale
    verdict, so partial checkpoint findings never supply the next audit.

    ``review_id`` pins a specific sidecar by stem — the bare ``<ts>`` or the
    full ``<ts>-completeness`` form. An unresolvable id returns ``None``
    (same as no sidecar); step 6 owns the "id given but unresolved" user
    error. A pinned id that resolves to an ineligible sidecar also returns
    ``None`` — it never falls back to an older report. Without an id, the
    newest eligible ``-completeness.json`` sidecar wins.

    A missing or malformed audit revision is unknown legacy evidence and
    therefore never reusable. The code fingerprint remains deletion-aware for
    callers that display its metadata; it does not decide audit freshness.
    """
    candidates = [
        p
        for p in list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)
        if p.name.endswith(COMPLETENESS_SIDECAR_SUFFIX)
    ]
    if review_id is not None:
        wanted = {review_id, f"{review_id}{COMPLETENESS_ARTIFACT_STEM_SUFFIX}"}
        # A pinned id names one sidecar: if that one is ineligible the lookup
        # declines rather than silently reusing a different report.
        candidates = [p for p in candidates if p.stem in wanted][:1]
    saved = None
    for candidate in candidates:
        try:
            loaded = load_review(candidate)
        except ReviewLoadError:
            # A candidate found by filename is not automatically trustworthy.
            # Treat unreadable sidecars like unsafe roles so a bad newer file
            # cannot block reuse of an older final report.
            continue
        if is_reusable_audit_sidecar(loaded):
            saved = loaded
            break
    if saved is None:
        return None

    # --- Audited plan/detail verdict -----------------------------------
    # A saved audit is current only when the exact selected-grade plan/detail
    # capture still matches. Generic plan/code fingerprints remain available
    # as legacy report metadata; they do not claim to freeze live context.
    audit_revision_match = False
    if saved.audit_revision is not None:
        try:
            from plan_tool.review_persistence import AuditInputSnapshot

            current_snapshot = audit_input_snapshot
            if current_snapshot is None:
                current_snapshot = AuditInputSnapshot.capture(
                    plan_path,
                    repo_root,
                    detail_grade=saved.audit_revision["detail_grade"],
                )
            if current_snapshot.detail_grade != saved.audit_revision["detail_grade"]:
                current_snapshot = None
            audit_revision_match = (
                current_snapshot is not None
                and current_snapshot.revision == saved.audit_revision
            )
        except Exception:  # noqa: BLE001 — revision freshness fails closed
            audit_revision_match = False
    plan_match = audit_revision_match

    # --- Code verdict (content vs footprint membership) ----------------
    if not saved.code_fingerprint_present:
        # Legacy/never-computed capture: no baseline to diff against, so
        # every current file would be a spurious `new` key. Stale, no drift.
        code_match = False
        drifted_code: list[Path] = []
        footprint_added: list[Path] = []
        footprint_removed: list[Path] = []
    else:
        plan = parse_plan(plan_path)
        current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)
        code_diff = diff_code_fingerprint(
            saved.code_fingerprint, current_code_fp, repo_root
        )
        code_match = code_diff.match
        drifted_code = list(code_diff.content_drifted)
        footprint_added = list(code_diff.footprint_added)
        footprint_removed = list(code_diff.footprint_removed)

    # --- Axis split ----------------------------------------------------
    correctness_recs = [
        r for r in saved.recommendations if r.source == "plan-correctness"
    ]
    conceptual_recs = [
        r for r in saved.recommendations if r.source == "plan-completeness"
    ]

    return ReusableAudit(
        saved=saved,
        correctness_recs=correctness_recs,
        conceptual_recs=conceptual_recs,
        audit_coverage=project_audit_coverage(saved.audit_coverage),
        fresh=audit_revision_match,
        plan_match=plan_match,
        code_match=code_match,
        drifted_code=drifted_code,
        footprint_added=footprint_added,
        footprint_removed=footprint_removed,
        audit_revision_match=audit_revision_match,
    )


# One-paragraph rationale per non-applied disposition. Surfaced verbatim
# in the report so a reader understands why a finding wasn't auto-fixed
# — the "sufficient logging to understand why" requirement. Keyed by the
# disposition codes produced below.
WHY: dict[str, str] = {
    "concept-link": (
        "Signed-off concepts need durable, explicit accounting. Assign each "
        "listed concept ID to a committed step or record a reviewed structured "
        "deferral; the prose apply loop cannot choose an owner or approve a "
        "deferral."
    ),
    "advisory-conceptual": (
        "Coverage gaps in the plan's own ideas (orphaned concepts, "
        "uncovered risks, dangling criteria, missing edge cases). Each is a "
        "scoping judgment call, so the audit's iterate loop does **not** "
        "touch them — chasing every newly-surfaced gap would never converge. "
        "Read each finding below and close it through a session-directed "
        "edit, then commit and re-audit the changed snapshot. Each finding "
        "carries its `[anchor-slug]` so you can refer to one precisely."
    ),
    "diagnostic": (
        "Structural diagnostics. `apply_finding` edits plan/detail prose; it "
        "cannot create a file, rewrite `step.files`, author a missing detail "
        "file, or write lessons — so dispatching these only returns "
        "NOT-APPLICABLE. Resolve them directly (fix the declared path, run "
        "`plan-tool detail`, author the lessons file)."
    ),
    "info": (
        "Info-severity advisories, excluded from the apply loop by default. "
        "Re-run with `--include-info` to apply them."
    ),
    "triage": (
        "Deferred by impact-weighted triage: the finding's estimated "
        "complexity exceeds its impact, so an automated apply isn't worth "
        "the cost. Make a session-directed edit if warranted, or re-run with "
        "`--no-triage`."
    ),
    "open": (
        "Eligible to apply, but the loop stopped (iteration cap, wall-clock "
        "budget, or no-progress) before reaching them. Re-run to continue, "
        "optionally with a larger `--max-iterations` / `--iteration-budget`."
    ),
}

# Human-facing heading per disposition code.
_HEADINGS: dict[str, str] = {
    "concept-link": "Missing explicit concept links — assign or defer",
    "advisory-conceptual": "Conceptual completeness — reported, not auto-applied",
    "diagnostic": "Deferred — structural diagnostics (resolve directly)",
    "info": "Deferred — info-severity advisories",
    "triage": "Deferred — low payoff (complexity > impact)",
    "open": "Open — eligible but not reached",
}

# Intro for the dedicated ``## Conceptual correctness`` section. Correctness
# gaps are unsound/contradictory concepts — the highest-priority findings,
# which the ``--iterate`` loop auto-applies. They surface here, as a first-
# class topic ahead of the completeness gaps, when the loop did not apply
# them this run (it halted, was budget-limited, or the audit ran read-only).
CORRECTNESS_INTRO = (
    "Unsound or contradictory concepts in the plan's design — the "
    "highest-priority gaps, addressed before the completeness gaps below. "
    "The audit reports these but does not apply them (read-only-audit "
    "split, #85): close each one through a session-directed edit to the "
    "plan body, then commit and re-audit the changed snapshot."
)

# Bare-plan variant: correctness gaps are actionable without a detail bundle;
# completeness gaps stay withheld until one exists.
CORRECTNESS_INTRO_BARE = (
    "Unsound or contradictory concepts in the plan's design — the "
    "highest-priority gaps. The audit reports these but does not apply them "
    "(read-only-audit split, #85): close each one through a session-directed "
    "edit to the plan body. Completeness gaps below stay informational until "
    "a detail bundle exists.\n\n"
    "    plan-tool reconcile-plan-walk {plan_name}  "
    "# optional interactive review of the saved findings"
)

# The jira-grade intro for both conceptual header blocks
# (:data:`CORRECTNESS_INTRO` and ``WHY['advisory-conceptual']``). Since #367
# none of the three names an apply verb — conceptual gaps are closed by
# whoever drives plan-tool — so this no longer exists to avoid a wrong-grade
# sidecar; it is simply the jira-grade wording of the same instruction.
# Deliberately no ``--anchor``-shaped substitute: there is nothing for an
# anchor to address.
_HAND_FIX_INTRO = (
    "Close these through a session-directed edit: read the findings below and "
    "edit the plan or detail prose yourself, then commit and re-audit the "
    "changed snapshot. Conceptual gaps are closed by whoever is driving "
    "plan-tool — a human at a TTY, or an orchestrating session — not by a "
    "tool command."
)


@dataclass
class AppliedOutcome:
    """One dispatched finding and the verdict ``apply_finding`` returned."""

    rec: Recommendation
    verdict: str  # APPLIED | NOT-APPLICABLE | BLOCKED | UNKNOWN
    summary: str = ""


def deferred_kind(rec: Recommendation) -> str:
    """Classify why a *deferred* finding wasn't applied, mirroring the
    gate order in :func:`partition_findings_for_triage`.

    ``plan-completeness`` findings are special-cased to
    ``"advisory-conceptual"`` — they're report-only by design rather
    than merely deferred by a gate.
    """
    if rec.source == "plan-completeness":
        return "advisory-conceptual"
    if rec.source == "concept-coverage":
        return "concept-link"
    if not is_apply_eligible(rec):
        return "diagnostic"
    if rec.severity.lower() == "info":
        return "info"
    if not should_apply_by_triage(rec):
        return "triage"
    return "open"


def _blocked_split_targets(
    blocked: list["AppliedOutcome"], plan
) -> list[tuple[int, Optional[str]]]:
    """The distinct ``(step_id, step_title)`` pairs a set of BLOCKED
    findings point at — the steps a reader could split. ``step_title`` is
    looked up from ``plan`` when available (``None`` if the plan wasn't
    passed or the id is stale). Findings with no ``step_id`` (plan-level)
    contribute nothing and fall through to the generic suggestion."""
    targets: list[tuple[int, Optional[str]]] = []
    seen: set[int] = set()
    for a in blocked:
        sid = a.rec.step_id
        if sid is None or sid in seen:
            continue
        seen.add(sid)
        title: Optional[str] = None
        if plan is not None:
            try:
                title = plan.step_by_id(sid).title
            except KeyError:
                title = None
        targets.append((sid, title))
    return targets


def _blocked_next_step(
    blocked: list["AppliedOutcome"],
    plan_name: str,
    plan,
    *,
    bare_plan: bool = False,
    detail_grade: str = GRADE_RUN,
) -> str:
    """The headline BLOCKED bullet, rendered as a multi-line block: a
    one-line headline, then one concrete ``split`` command per flagged
    step (numbered + titled when the plan is in hand), then the
    new-step fallback. Naming the specific step the finding sits on is
    what makes the suggestion prescriptive — the reader only has to fill
    in the two sub-step titles, not hunt for which ``--step N`` to pass.

    On a bare plan the headline routes to ``plan-tool detail`` first;
    ``split`` stays as the secondary over-packed-step option."""
    n = len(blocked)
    targets = _blocked_split_targets(blocked, plan)
    detail_command = _detail_authoring_command(plan_name, detail_grade=detail_grade)
    if bare_plan:
        lines = [
            f"{n} finding(s) came back **BLOCKED** — `apply` can't create "
            f"files, and the step's detail file doesn't exist yet. Author "
            f"the missing detail file(s) first:",
            f"  • `{detail_command}`",
        ]
        if targets:
            for sid, title in targets:
                label = (
                    f' (step {sid}: "{title}")' if title else f" (step {sid})"
                )
                lines.append(
                    f"  • if the step is over-packed, split{label}: "
                    f"`plan-tool split {plan_name} --step {sid} "
                    f'--into "<first sub-step>" --into "<second sub-step>"`'
                )
        else:
            lines.append(
                f"  • if a step is over-packed, split it: "
                f"`plan-tool split {plan_name} --step N "
                f'--into "<first sub-step>" --into "<second sub-step>"`'
            )
    else:
        lines = [
            f"{n} finding(s) came back **BLOCKED** — `apply` can't add or "
            f"restructure steps, so each needs a manual plan edit. "
            f"`split` authors both halves' detail files and re-runs the audit:",
        ]
        if targets:
            for sid, title in targets:
                label = (
                    f' (step {sid}: "{title}")' if title else f" (step {sid})"
                )
                lines.append(
                    f"  • split{label}: `plan-tool split {plan_name} --step {sid} "
                    f'--into "<first sub-step>" --into "<second sub-step>"`'
                )
        else:
            lines.append(
                f"  • split a step: `plan-tool split {plan_name} --step N "
                f'--into "<first sub-step>" --into "<second sub-step>"`'
            )
    lines.append(
        f"  • new step: add it to the plan, then `{detail_command}`"
    )
    return "\n".join(lines)


def diagnostic_remedies(
    diagnostics: list[Recommendation],
    plan_name: str,
    *,
    detail_grade: str = GRADE_RUN,
) -> list[str]:
    """One tailored remedy line per *source* present in ``diagnostics``.

    Structural diagnostics aren't fungible: a files-coherence drift wants
    a ``files:``/``allowed_mentions:`` edit, a detail-coverage gap wants
    ``plan-tool detail``, a lessons gap wants the lessons file. The old
    summary collapsed all three into one generic line that always named
    ``plan-tool detail`` — so when the only open diagnostics were
    files-coherence drift (every step's detail file already on disk),
    the reader ran ``detail`` and it no-op'd. This names **only** the
    fixes that actually apply, so ``plan-tool detail`` appears solely when
    a detail file is genuinely missing or unreferenced.

    At jira grade the ``completeness-apply`` files-coherence remedy is
    withheld: that verb resolves its target through the newest saved sidecar,
    which this grade does not write.
    """
    by_source: dict[str, int] = {}
    for r in diagnostics:
        by_source[r.source] = by_source.get(r.source, 0) + 1
    jira_grade = detail_grade == GRADE_JIRA
    lines: list[str] = []
    if by_source.get("detail-coverage"):
        n = by_source["detail-coverage"]
        lines.append(
            f"`{_detail_authoring_command(plan_name, detail_grade=detail_grade)}` "
            f"— reattach/author "
            f"{n} missing or unreferenced detail file(s). The default run "
            f"skips steps whose detail file already exists, so it reattaches "
            f"unreferenced files and authors genuinely-missing ones without "
            f"touching your other steps; pass `--force` only to deliberately "
            f"overwrite an existing detail file."
        )
    if by_source.get("files-coherence") and not jira_grade:
        n = by_source["files-coherence"]
        lines.append(
            f"`plan-tool completeness-apply {plan_name}` also clears "
            f"these deterministically (no claude): it adds the cited path(s) "
            f"that resolve to real files to the step's `allowed_mentions:`. "
            f"Citations that don't resolve to a file are likely typos — fix "
            f"those in the detail prose. ({n} files-coherence drift(s))."
        )
    if by_source.get("lessons-coverage"):
        n = by_source["lessons-coverage"]
        lines.append(
            f"Author or backfill the lessons file "
            f"({n} lessons-coverage finding(s))."
        )
    handled = {"detail-coverage", "files-coherence", "lessons-coverage"}
    for r in diagnostics:
        if r.source in handled:
            continue
        act = (r.suggested_action or "").strip()
        if act:
            lines.append(act)
    return lines


def _has_critical_or_high(*finding_groups) -> bool:
    """True when any finding across the given groups is critical/high severity.

    Matches the convergence diagnostic's run-readiness threshold
    (``convergence_diagnosis._ADVISORY_SEVERITIES`` is the same critical/high
    set) — deliberately *not* :func:`convergence.is_blocking`, which is
    medium+ and would flag the advisory gaps most plans carry. The literals
    are inlined rather than importing that leaf's private constant, to avoid a
    cross-leaf coupling for two severity strings. ``AppliedOutcome`` groups
    are unwrapped to their ``.rec``; ``Recommendation`` groups read directly.
    The case-insensitive compare matches how every severity gate in the
    codebase keys (``severity.lower()``)."""
    for group in finding_groups:
        for item in group:
            rec = item.rec if isinstance(item, AppliedOutcome) else item
            if rec.severity.lower() in ("critical", "high"):
                return True
    return False


# The reconcile-plan staleness recommendation, shared by both renderers so
# the prose bullet and the console command stay one definition. Emitted only
# when code drifted under the plan AND a critical/high finding is present
# (per BACKLOG #65 — avoid noise on docs-only staleness or a clean re-audit).
def _reconcile_drift_prose(plan_name: str) -> str:
    return (
        f"`plan-tool reconcile-plan {plan_name}` — code changed under the "
        f"plan since its last audit; it may be stale against current code. "
        f"Rebase, then re-audit, before running."
    )


def _reconcile_drift_command(plan_name: str) -> tuple[str, str]:
    return (
        f"plan-tool reconcile-plan {plan_name}",
        "# code drifted under the plan — rebase before running",
    )


def next_stage_command(
    plan_name: str,
    bundle_status,
    *,
    detail_grade: str = GRADE_RUN,
    verdict=ABSENT_BLOCKING_VERDICT,
) -> tuple[str, str]:
    """Return the only valid post-audit stage transition.

    Anything but a completed empty-set ``verdict`` returns the re-audit."""
    if not _verdict_offers_stage(verdict):
        return _reaudit_command(plan_name, verdict, detail_grade=detail_grade)
    jira_grade = detail_grade == GRADE_JIRA
    if bool(getattr(bundle_status, "is_bare", False)):
        return (
            _detail_authoring_command(plan_name, detail_grade=detail_grade),
            (
                "no plan-level gaps remain — author the jira-grade detail "
                "bundle before export"
                if jira_grade
                else "no plan-level gaps remain — author the detail bundle "
                "before execution"
            ),
        )
    if jira_grade:
        return (
            f"plan-tool jira {plan_name} --grade {GRADE_JIRA}",
            "no gaps left — export the jira-grade bundle as stories",
        )
    return (
        f"plan-tool run {plan_name}",
        "no gaps left — execute the next runnable step",
    )


def _close_conceptual_steps(
    gaps: NextStepGaps, *, jira_grade: bool, bare_plan: bool = False
) -> list[str]:
    """Prose bullets for the conceptual gaps the verdict says to close."""
    if jira_grade:
        n = gaps.close_conceptual_count + gaps.unlisted_blocking
        return [
            f"Close {n} conceptual gap(s) through a session-directed edit — a "
            "jira-grade audit writes no findings sidecar, so no apply verb "
            "can replay them."
        ] if n else []
    steps = []
    corr, comp = len(gaps.close_correctness), len(gaps.close_completeness)
    if corr and comp:
        steps.append(
            f"Close {corr} conceptual-correctness gap(s) through a "
            "session-directed edit first (design gaps; not auto-applied under "
            f"#85), then {comp} conceptual-completeness gap(s)."
        )
    elif corr:
        tail = (
            "; the non-blocking completeness gaps stay informational until a "
            "complete detail bundle exists"
            if bare_plan and gaps.advisory_completeness
            else ""
        )
        steps.append(
            f"Close {corr} conceptual-correctness gap(s) through a "
            f"session-directed edit (design gaps; not auto-applied under #85){tail}."
        )
    elif comp:
        steps.append(
            f"Close {comp} conceptual-completeness gap(s) through a "
            "session-directed edit (not auto-applied; each needs your judgment)."
        )
    if gaps.unlisted_blocking:
        steps.append(
            f"Close {gaps.unlisted_blocking} blocking conceptual gap(s) "
            "through a session-directed edit."
        )
    return steps


def _advisory_conceptual_step(gaps: NextStepGaps, *, bare_plan: bool) -> str:
    """The one advisory line: listed gaps outside the blocking set, no close wording."""
    scope = (
        "not verified against the current text"
        if gaps.demoted_stale
        else "outside the blocking set"
    )
    line = (
        f"{gaps.advisory_count} conceptual gap(s) are listed in the report as "
        f"advisory ({scope})"
    )
    if bare_plan and gaps.advisory_completeness:
        line += "; completeness gaps stay informational until a complete detail bundle exists"
    return line + "."


def _fresh_audit_required(result, verdict, is_pre_apply_checkpoint: bool) -> bool:
    """A checkpoint, or an unqualified result with no gate verdict to read,
    leaves nothing to triage: only a fresh audit helps. A gate verdict (set or
    incomplete) keeps its ids, so the ordinary flow names the gaps instead."""
    if is_pre_apply_checkpoint:
        return True
    unqualified = (
        result is not None and result["headline"] == "no-qualified-current-evidence"
    )
    return unqualified and not (
        isinstance(verdict, BlockingVerdict)
        and verdict.state != BLOCKING_STATE_ABSENT
    )


def reaudit_step(
    plan_name: str, verdict, *, detail_grade: str, also=()
) -> str:
    """The one closing prose step for a verdict that offers no stage: the
    command plus its description from :func:`_reaudit_command`."""
    command, why = _reaudit_command(
        plan_name, verdict, detail_grade=detail_grade, also=also
    )
    return f"`{command}` — {why}; no stage transition is offered while the blocking verdict is open or unavailable."


def suggested_next_steps(
    *,
    plan_name: str,
    iterate_enabled: bool,
    applied: list["AppliedOutcome"],
    deferred: list[Recommendation],
    advisory_conceptual: list[Recommendation],
    open_findings: list[Recommendation],
    plan=None,
    code_drifted: bool = False,
    bundle_status=None,
    correctness: list[Recommendation] = (),
    detail_grade: str = GRADE_RUN,
    qualified_result=_QUALIFIED_RESULT_UNSET,
    is_pre_apply_checkpoint: bool = False,
    verdict=ABSENT_BLOCKING_VERDICT,
) -> list[str]:
    """The disposition-level "what do I do now" bullets, ordered by what
    most needs a human.

    This is the *summary* next-step list — the grouped report carries its
    own deterministic/structural one, but that lives at the bottom of the
    embedded dump where it's easy to miss. Both the console summary and
    the curated report render this list last so the reader leaves with an
    action instead of re-deriving the workflow.

    Each bullet is conditional on the disposition it addresses; the
    BLOCKED bullet is the headline case — an apply verdict of BLOCKED
    means the finding calls for a *new file or a restructured step*, which
    ``apply_finding`` does neither, so it's the one most likely to be a
    "this needs a new step" finding. Pass ``plan`` to make its ``split``
    suggestion prescriptive — naming the exact step (number + title) each
    blocked finding sits on instead of a placeholder ``--step N``. When
    nothing is outstanding, the list falls back to the single common
    pointer at ``run``.

    Bullets may be multi-line; callers render the first line on the bullet
    and indent the continuation under it.

    ``code_drifted`` (the audit detected code changed under the plan since
    its last save) prepends a ``reconcile-plan`` rebase bullet as the most
    urgent step — but only when a critical/high finding is also present, so a
    docs-only staleness or a clean re-audit stays quiet (BACKLOG #65).

    At jira grade the ``--iterate --max-iterations N`` open-findings bullet is
    withheld (``--iterate`` is rejected at that grade). Conceptual gaps are
    always closed by a session-directed edit (#367);
    :func:`next_step_gaps` splits close from advisory by the verdict alone, so
    every reader agrees on which gaps to close.
    """
    result = _qualified_result_payload(qualified_result)
    if _fresh_audit_required(result, verdict, is_pre_apply_checkpoint):
        command, _note = _reaudit_command(plan_name, verdict, detail_grade=detail_grade)
        return [
            *_blocking_deterministic_steps(verdict),
            f"`{command}` — run a fresh audit before reusing or applying saved "
            "findings.",
        ]
    blocked = [a for a in applied if a.verdict == "BLOCKED"]
    bare_plan = bool(getattr(bundle_status, "is_bare", False))
    jira_grade = detail_grade == GRADE_JIRA
    gaps = next_step_gaps(
        verdict, correctness=correctness, advisory_conceptual=advisory_conceptual
    )
    concept_links = [
        r for r in deferred if deferred_kind(r) == "concept-link"
    ]
    diagnostic = [r for r in deferred if deferred_kind(r) == "diagnostic"]
    bare_detail_diagnostic_count = 0
    if bare_plan:
        bare_detail_diagnostic_count = sum(
            1 for r in diagnostic if r.source in DETAIL_LEVEL_DIAGNOSTIC_SOURCES
        )
        diagnostic = [
            r for r in diagnostic
            if r.source not in DETAIL_LEVEL_DIAGNOSTIC_SOURCES
        ]
    steps: list[str] = []

    if code_drifted and _has_critical_or_high(
        applied, deferred, advisory_conceptual, open_findings
    ):
        steps.append(_reconcile_drift_prose(plan_name))
    if blocked:
        steps.append(
            _blocked_next_step(
                blocked,
                plan_name,
                plan,
                bare_plan=bare_plan,
                detail_grade=detail_grade,
            )
        )
    steps.extend(
        _close_conceptual_steps(gaps, jira_grade=jira_grade, bare_plan=bare_plan)
    )
    if gaps.advisory_count:
        steps.append(_advisory_conceptual_step(gaps, bare_plan=bare_plan))
    if concept_links:
        steps.append(
            f"Assign or defer {len(concept_links)} signed-off concept(s) "
            "using explicit concept IDs — see the missing-link findings above."
        )
    if diagnostic:
        remedies = diagnostic_remedies(
            diagnostic, plan_name, detail_grade=detail_grade
        )
        if not remedies:
            steps.append(
                f"Resolve {len(diagnostic)} structural diagnostic(s) "
                f"directly — see each finding's suggested fix above."
            )
        elif len(remedies) == 1:
            # The lone remedy already states its own count + action, so
            # the generic "Resolve N structural diagnostic(s)" wrapper would
            # just double the count — emit the remedy directly.
            steps.append(remedies[0])
        else:
            # Multiple distinct remedies — headline + indented sub-bullets
            # (callers render the first line on the bullet, continuation
            # lines indented under it).
            body = "\n".join(f"  • {r}" for r in remedies)
            steps.append(
                f"Resolve {len(diagnostic)} structural diagnostic(s) "
                f"directly:\n{body}"
            )
    if open_findings and not jira_grade:
        steps.append(
            f"`plan-tool completeness-audit {plan_name} --iterate "
            f"--max-iterations N` — {len(open_findings)} eligible finding(s) "
            f"weren't reached before the loop stopped."
        )
    next_command, next_description = next_stage_command(
        plan_name, bundle_status, detail_grade=detail_grade, verdict=verdict
    )
    if not _verdict_offers_stage(verdict):
        steps.extend(
            _blocking_deterministic_steps(
                verdict,
                covered_sources={r.source for r in (*diagnostic, *concept_links)},
            )
        )
        steps.append(reaudit_step(plan_name, verdict, detail_grade=detail_grade))
        return steps
    if not steps and bare_detail_diagnostic_count:
        steps.append(
            f"No structural gaps left to close in this bare-plan audit — "
            f"`{next_command}` — {next_description}. "
            "Detail-level/conceptual findings above are informational until "
            "a detail bundle exists."
        )
    elif steps and len(steps) == (1 if gaps.advisory_count else 0):
        steps.append(
            "The gaps above are advisory and hold back no stage — "
            f"`{next_command}` — {next_description}."
        )
    elif steps:
        steps.append(f"`{next_command}` — {next_description}.")
    else:
        steps.append(
            f"No gaps left to close — `{next_command}` — {next_description}."
        )
    return steps


def suggested_next_step_commands(
    *,
    plan_name: str,
    applied: list["AppliedOutcome"],
    deferred: list[Recommendation],
    advisory_conceptual: list[Recommendation],
    open_findings: list[Recommendation],
    plan=None,
    code_drifted: bool = False,
    bundle_status=None,
    correctness: list[Recommendation] = (),
    detail_grade: str = GRADE_RUN,
    qualified_result=_QUALIFIED_RESULT_UNSET,
    is_pre_apply_checkpoint: bool = False,
    verdict=ABSENT_BLOCKING_VERDICT,
    include_stage: bool = True,
) -> list[tuple[str, str]]:
    """Disposition next-steps as ``(command, description)`` tuples for the
    clean aligned console block (``_print_next_steps``).

    The console companion to :func:`suggested_next_steps`: that one stays
    prose for the markdown report; this one compresses each disposition to
    a scannable command + short ``#`` note, most-urgent first, so the
    on-screen block aligns into columns and merges with the pipeline
    suggestions into a single list. The full rationale lives in the saved
    report (the console summary links it), so the compression drops no
    actionable detail. Remedies with no single command (e.g. a
    lessons-coverage backfill) are intentionally omitted here — they stay
    in the report's prose list. A completed empty ``verdict`` ends with the
    shared stage (omitted when ``include_stage`` is false, for a parent that
    appends its own); any other verdict ends with the one re-audit row.

    ``code_drifted`` (code changed under the plan since its last audit)
    prepends a ``reconcile-plan`` command first — but only when a
    critical/high finding is present, so docs-only staleness or a clean
    re-audit emits nothing (BACKLOG #65). Mirrors
    :func:`suggested_next_steps`' prose bullet.

    Conceptual gaps never appear here: they are closed by a session-directed
    edit (#367), so only :func:`suggested_next_steps`' prose carries them.
    This block names a command only where one exists — including the
    deterministic files-coherence clear.
    """
    result = _qualified_result_payload(qualified_result)
    if _fresh_audit_required(result, verdict, is_pre_apply_checkpoint):
        command, _note = _reaudit_command(plan_name, verdict, detail_grade=detail_grade)
        return [(command, "fresh audit required before reuse or apply")]
    blocked = [a for a in applied if a.verdict == "BLOCKED"]
    bare_plan = bool(getattr(bundle_status, "is_bare", False))
    jira_grade = detail_grade == GRADE_JIRA
    concept_links = [
        r for r in deferred if deferred_kind(r) == "concept-link"
    ]
    diagnostic = [r for r in deferred if deferred_kind(r) == "diagnostic"]
    if bare_plan:
        diagnostic = [
            r for r in diagnostic
            if r.source not in DETAIL_LEVEL_DIAGNOSTIC_SOURCES
        ]
    cmds: list[tuple[str, str]] = []

    if code_drifted and _has_critical_or_high(
        applied, deferred, advisory_conceptual, open_findings
    ):
        cmds.append(_reconcile_drift_command(plan_name))
    if blocked:
        # `apply` can't add or restructure steps (or create files on a bare
        # plan), so each BLOCKED finding needs a manual edit — the headline
        # case. Name the specific step when the plan is in hand; the full
        # `--into` syntax lives in the report so the command column stays narrow.
        if bare_plan:
            cmds.append((
                _detail_authoring_command(plan_name, detail_grade=detail_grade),
                "BLOCKED — author missing detail file(s) (apply can't create files)",
            ))
        targets = _blocked_split_targets(blocked, plan)
        steps_to_split = [sid for sid, _title in targets] or [None]
        split_desc = (
            "if over-packed — split into sub-steps (see report)"
            if bare_plan
            else "BLOCKED — split into sub-steps (apply can't; see report)"
        )
        for sid in steps_to_split:
            arg = sid if sid is not None else "N"
            cmds.append((
                f"plan-tool split {plan_name} --step {arg}",
                split_desc,
            ))
    by_source: dict[str, int] = {}
    for r in diagnostic:
        by_source[r.source] = by_source.get(r.source, 0) + 1
    # Conceptual gaps are closed by a session-directed edit (#367), so this
    # command block names no conceptual walk — only the deterministic,
    # no-claude files-coherence clear, and never the nonexistent ``--apply``
    # flag. The prose renderer carries the hand-edit instruction instead.
    apply_effects: list[str] = []
    if by_source.get("files-coherence") and not jira_grade:
        apply_effects.append(
            f"clear {by_source['files-coherence']} files-coherence "
            f"drift(s) (no claude)"
        )
    if apply_effects:
        cmds.append((
            f"plan-tool completeness-apply {plan_name}",
            "; ".join(apply_effects),
        ))
    # Every reason to re-audit merges into one canonical row, placed where the
    # first reason arose; ``_reaudit_command`` is its only source.
    reaudit_at: int | None = None
    reaudit_also: list[str] = []
    if concept_links:
        reaudit_at = len(cmds)
        reaudit_also.append(
            f"assign or structurally defer {len(concept_links)} concept(s)"
        )
    if by_source.get("detail-coverage") and not jira_grade:
        cmds.append((
            f"plan-tool detail {plan_name}",
            f"reattach/author {by_source['detail-coverage']} missing "
            f"detail file(s)",
        ))
    if open_findings and not jira_grade:
        if reaudit_at is None:
            reaudit_at = len(cmds)
        reaudit_also.append(
            f"{len(open_findings)} finding(s) not reached by the loop"
        )
    if not _verdict_offers_stage(verdict) and reaudit_at is None:
        reaudit_at = len(cmds)
    if reaudit_at is not None:
        cmds.insert(
            reaudit_at,
            _reaudit_command(
                plan_name, verdict, detail_grade=detail_grade, also=reaudit_also
            ),
        )
    if _verdict_offers_stage(verdict) and include_stage:
        stage = next_stage_command(
            plan_name, bundle_status, detail_grade=detail_grade, verdict=verdict
        )
        # A bare plan's BLOCKED row may already name this same command.
        if stage[0] not in {c for c, _ in cmds}:
            cmds.append(stage)
    return cmds


def _anchor_value(rec: Recommendation) -> str:
    """The ``--anchor`` value for a finding: the human-readable
    ``[anchor-slug]`` when the audit captured one, else the hashed id.
    ``completeness-apply --anchor`` accepts both."""
    return rec.anchor or rec.id


def format_finding_bullet(rec: Recommendation, key: str) -> str:
    """The one report bullet for a finding: severity, ``[key]`` tag,
    confidence, then the *full* ``rec.body`` (not ``rec.title``, which is the
    body's first line clipped to 120 chars and reads truncated mid-thought).
    Continuation lines of a multi-line body sit indented under the bullet
    (:func:`indent_bullet_body`). Every finding bullet in a report goes
    through here, so the bullet shape changes in one place."""
    tag = f" `[{key}]`" if key else ""
    body = indent_bullet_body((rec.body or rec.title).strip())
    return (
        f"- {rec.severity.upper()}{tag} "
        f"[{confidence_label(rec.confidence)}]: {body}"
    )


def _fmt_finding_line(rec: Recommendation) -> str:
    """One report bullet for a finding, tagged with its anchor or id."""
    return format_finding_bullet(rec, _anchor_value(rec))


def _fmt_fix_line(rec: Recommendation) -> Optional[str]:
    """The remediation-scope sub-bullet for a conceptual finding.

    ``review_walk`` shows ``suggested_action`` in the interactive walk (labelled
    "will apply"); the persisted report used to drop it, so the
    session-directed
    path the #85 split mandates for a session never saw the scope the auditor
    had already computed — and fixes landed on the cited spot only. See
    BUG_BACKLOG "The persisted report withholds ``suggested_action``".
    """
    act = (rec.suggested_action or "").strip()
    return f"  - Fix: {act}" if act else None


def _fmt_restated_line(rec: Recommendation) -> Optional[str]:
    """The plan-altitude restatement sub-bullet. Contract: DATA_CONTRACT.md
    and plan-audit.md's "Property coverage versus delivery mechanisms"."""
    restated = restated_property_or_none(rec)
    return f"  - {RESTATED_PROPERTY_LABEL}: {restated}" if restated else None


def _fmt_pending_line(rec: Recommendation) -> str:
    """One report bullet for a pending concept decision. Same shape as
    :func:`_fmt_finding_line`, but tagged with the bare concept id (the
    ``scope-review --concept`` token) rather than the ``concept-`` anchor."""
    return format_finding_bullet(rec, pending_concept_id(rec) or "")


# --- Plan mass (#238) -----------------------------------------------------
# The convergence loop measures *findings*; it does not measure the
# *artifact*. Findings can fall while the plan grows, because the fix for a
# finding is almost always more plan — a state the finding-count stopping
# rule reads as healthy convergence. This block reports the artifact's own
# growth alongside the finding curve so a reader can see both at once.
#
# Reporting only, by deliberate scope fence (BACKLOG #238): no threshold,
# warning, gate, or exit-code change is derived from any number here. The
# ratios are heuristics over a single session's evidence and are expected to
# need tuning against a real corpus before anything gates on them.

# Sentence-level markers a detail body uses to annotate a declared
# ``depends_on`` edge as ordering-only or test-only rather than a real
# content dependency. Free-prose heuristic, not a schema field — will
# mis-fire until tuned against real bundles (see BACKLOG #238 risks).
_SOFT_EDGE_MARKERS: tuple[str, ...] = (
    "ordering-only",
    "ordering only",
    "test-only",
    "test only",
    "no file collision",
    "no shared file",
    "not a content dependency",
    "edit different",
    # The full qualifier matters: "...for the behavior" alone (without "the
    # suite observes") also substring-matches a genuine hard/content
    # dependency ("depends on it for the behavior of the retry loop"),
    # inverting the marker's meaning. Matches BACKLOG #238's own example
    # sentence verbatim.
    "depends on it for the behavior the suite observes",
)

# Free-prose phrases a detail body volunteers when the step changes nothing
# user-visible. Same heuristic caveat as the soft-edge markers above.
# Deliberately excludes "changes no production code": that is the literal
# boilerplate ``detail.py:_format_tests_directive`` inserts into every
# non-code step's Verification section ("This is a **non-code** step - it
# changes no production code."), so it would flag every non-code step as
# "inert" - a category error, not a padding signal. Scoped to code steps
# only (see ``_is_code_step``) for the same reason: a non-code step
# legitimately renders/behaves like nothing, by definition, which is not
# what this ratio means to measure.
_INERT_STEP_PHRASES: tuple[str, ...] = (
    "nothing renders differently",
    "nothing user-visible changes",
    "no user-visible change",
    "is not edited",
    "no behavior change",
    "no behavior changes",
)

# Deliberately a local declaration, not imported from ``jira_grade``'s
# identical-pattern private ``_SENTENCE_SPLIT_RE`` — a leading-underscore
# name is an internal contract of its own module, and reaching across a
# module boundary for it couples this file to jira_grade's private
# internals for one two-line regex. Not caught by tests/test_duplication.py
# either (its detector matches ≥4-line function bodies, not a single
# constant assignment).
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class SoftEdge:
    """One declared ``depends_on`` edge whose detail prose marks it as
    ordering-only or test-only rather than a content dependency — a seam
    where the step graph would separate if the edge were cut."""

    step_id: int
    depends_on_id: int
    note: str


@dataclass(frozen=True)
class PlanMass:
    """One plan's structural-mass snapshot (#238).

    ``step_count`` / ``detail_bundle_bytes`` cover **committed** steps only
    (a parked step is excluded from the runnable graph and the completion
    tally elsewhere in the tool; this block matches that convention).
    ``keystone_fan_out`` / ``satellite_ratio`` / ``inert_step_ratio`` /
    ``audit_induced_growth`` are ``None`` when fewer than two committed
    steps exist (no ratio is meaningful on a single-step plan) — never
    coerced to ``0.0``, which would misreport "measured, found none" for
    "not measurable here". ``keystone_fan_out`` / ``satellite_ratio`` /
    ``inert_step_ratio`` are additionally scoped to **code** steps
    (``change_type`` anything but ``non-code``, see ``_is_code_step`` for the
    explicit unclassified-defaults-to-code rule) and are ``None`` when the
    plan has zero code steps too.
    """

    step_count: int
    detail_bundle_bytes: int
    keystone_fan_out: Optional[float]
    satellite_ratio: Optional[float]
    inert_step_ratio: Optional[float]
    audit_induced_growth: Optional[float]
    soft_edges: tuple[SoftEdge, ...] = ()


def _read_detail_bodies_for_mass(
    plan, plan_path: Path, committed
) -> dict[int, str]:
    bodies: dict[int, str] = {}
    for step in committed:
        detail_path = derive_detail_path(plan_path, plan, step)
        try:
            # ``errors="replace"`` — matches ``review.py``'s own detail-body
            # reads: a non-UTF-8 detail file degrades that one step's body
            # rather than raising and losing the whole snapshot.
            body = detail_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        require_supported_detail_format_version(body, path=detail_path)
        bodies[step.id] = body
    return bodies


def _find_soft_edges(step, dependency_titles: dict[int, str], body: str) -> list[SoftEdge]:
    if not body:
        return []
    sentences = _SENTENCE_SPLIT_RE.split(body)
    edges: list[SoftEdge] = []
    for dep_id in step.depends_on:
        dep_title = dependency_titles.get(dep_id, "")
        # ``\b`` word-boundary, not a bare substring test: "step 1" must not
        # match inside "step 12"/"step 10"/"step 100" on a plan with 10+
        # steps, which a plain ``in`` check would (a digit boundary is not a
        # regex word boundary).
        step_ref_re = re.compile(rf"\bstep\s+{dep_id}\b")
        for sentence in sentences:
            lowered = sentence.lower()
            if not any(marker in lowered for marker in _SOFT_EDGE_MARKERS):
                continue
            mentions_dep = (
                step_ref_re.search(lowered) is not None
                or (dep_title and dep_title.lower() in lowered)
            )
            if mentions_dep:
                edges.append(
                    SoftEdge(
                        step_id=step.id,
                        depends_on_id=dep_id,
                        note=sentence.strip(),
                    )
                )
                break
    return edges


def _is_code_step(step) -> bool:
    """Whether ``step`` is a keystone/inert-ratio candidate — every
    ``change_type`` except the explicit ``NON_CODE`` marker, **including**
    ``None`` (unclassified/unset).

    Explicit default, not an oversight: ``change_type`` is optional and
    frequently unset on older or hand-authored plans (``schema.py``'s
    ``Step.change_type: Optional[ChangeType] = None``), and the overwhelming
    majority of unclassified steps are ordinary code steps that were never
    run through classification — treating them as non-code by default would
    make both ratios ``None``/skewed on exactly the plans least likely to
    have been audited for this already. Only a step explicitly marked
    ``non-code`` is excluded.
    """
    return step.change_type is not ChangeType.NON_CODE


def compute_plan_mass(plan, plan_path: Path, repo_root: Path) -> PlanMass:
    """Compute the current plan's structural-mass snapshot.

    Pure read over already-parsed plan data plus on-disk detail bodies and
    the best-effort step-provenance telemetry
    (:func:`plan_tool.telemetry.read_step_provenance_titles`) — no Claude,
    no mutation. Deltas against a plan's first audit are computed by the
    caller (the report needs the *first saved* snapshot, which this function
    has no reason to know about).
    """
    # ``plan.steps`` + a manual scope filter, not ``plan.committed_steps`` —
    # the completeness CLI's own test doubles pass a lightweight plan
    # stand-in (real ``title``/``steps`` for the fields under test, nothing
    # else) into the code path this is called from, and requiring the full
    # ``Plan`` interface here would break them for no benefit this function
    # needs.
    committed = [s for s in plan.steps if s.scope is StepScope.COMMITTED]
    step_count = len(committed)
    bodies = _read_detail_bodies_for_mass(plan, plan_path, committed)
    detail_bundle_bytes = sum(len(body.encode("utf-8")) for body in bodies.values())

    if step_count < 2:
        return PlanMass(
            step_count=step_count,
            detail_bundle_bytes=detail_bundle_bytes,
            keystone_fan_out=None,
            satellite_ratio=None,
            inert_step_ratio=None,
            audit_induced_growth=None,
            soft_edges=(),
        )

    committed_ids = {s.id for s in committed}
    code_steps = [s for s in committed if _is_code_step(s)]
    keystone_fan_out: Optional[float] = None
    keystone_id: Optional[int] = None
    if code_steps:
        # ``set(...)`` — count distinct dependencies, not raw list length.
        # ``Plan._validate_graph`` already rejects an unknown or parked
        # dependency id, so every entry here names a real committed step;
        # the schema places no uniqueness constraint on the list itself, so
        # a directly edited duplicate entry would otherwise inflate the count.
        keystone = max(code_steps, key=lambda s: len(set(s.depends_on)))
        keystone_id = keystone.id
        keystone_fan_out = len(set(keystone.depends_on)) / (step_count - 1)

    satellite_ratio: Optional[float] = None
    if keystone_id is not None:
        # Reverse edges: for each step, which (non-``non-code``) committed
        # steps declare a dependency on it.
        dependents: dict[int, set[int]] = {sid: set() for sid in committed_ids}
        for s in committed:
            if not _is_code_step(s):
                continue
            for dep_id in s.depends_on:
                if dep_id in dependents:
                    dependents[dep_id].add(s.id)
        satellite_count = sum(
            1
            for s in committed
            if s.id != keystone_id and dependents.get(s.id) == {keystone_id}
        )
        satellite_ratio = satellite_count / step_count

    # Scoped to code steps: a non-code step legitimately touches nothing
    # user-visible by definition (see the phrase-list comment above), so
    # counting it here would measure "how many non-code steps exist," not
    # padding. Denominator matches — diluting by the non-code population
    # would understate real padding on a docs-heavy plan.
    #
    # Whole-body substring match, not sentence-scoped: a marker phrase's
    # words practically never straddle a sentence boundary, so splitting
    # first would not change which bodies match — it would only add code.
    # The real residual imprecision is subject-attribution, not sentence
    # boundaries: "this step updates the schema; the seed script is not
    # edited" contains a genuine, self-contained "is not edited" claim
    # about one file, and no phrase-level heuristic (sentence-scoped or
    # not) can tell that apart from a claim about the whole step without
    # judging content — which BACKLOG #238 explicitly keeps out of scope.
    # Expected false-positive rate, not a bug to chase further here.
    code_step_ids = {s.id for s in code_steps}
    inert_count = sum(
        1
        for step_id, body in bodies.items()
        if step_id in code_step_ids
        and any(phrase in body.lower() for phrase in _INERT_STEP_PHRASES)
    )
    inert_step_ratio = inert_count / len(code_steps) if code_steps else None

    # Plan-wide title union, not scoped to one split: two structural splits
    # at different points in this plan's history that happen to reuse the
    # same generic title (e.g. two different "Add tests" halves) are
    # indistinguishable here, and a later hand-authored step that happens
    # to reuse an old split-created title would misread as audit-induced.
    # ``split_step`` only guarantees title uniqueness *within* one split
    # call, never plan-wide or across time — a known, accepted heuristic
    # limit (see :data:`STEP_PROVENANCE_KIND`), not tightened further here:
    # #238 ships the measurement, and title-collision avoidance is
    # calibration work for once a real corpus exists.
    # Public ``locator.slug_from_filename`` — matches the sibling call site
    # in ``cli/completeness_phases.py:first_saved_plan_mass`` (same slug
    # derivation, same purpose), rather than reaching for the private
    # ``detail_artifacts._plan_slug`` wrapper.
    provenance_titles = read_step_provenance_titles(
        repo_root, slug_from_filename(plan_path)
    )
    induced_count = sum(1 for s in committed if s.title in provenance_titles)
    audit_induced_growth = induced_count / step_count

    titles_by_id = {s.id: s.title for s in committed}
    soft_edges: list[SoftEdge] = []
    for step in committed:
        soft_edges.extend(
            _find_soft_edges(step, titles_by_id, bodies.get(step.id, ""))
        )

    return PlanMass(
        step_count=step_count,
        detail_bundle_bytes=detail_bundle_bytes,
        keystone_fan_out=keystone_fan_out,
        satellite_ratio=satellite_ratio,
        inert_step_ratio=inert_step_ratio,
        audit_induced_growth=audit_induced_growth,
        soft_edges=tuple(soft_edges),
    )


def compute_plan_mass_best_effort(
    plan, plan_path: Path, repo_root: Path
) -> Optional[PlanMass]:
    """:func:`compute_plan_mass`, swallowing ordinary failures to ``None``.

    The one shared failure policy for every CLI call site (the markdown
    report path in ``cli/completeness_phases.py`` and the ``--json`` path in
    ``cli/completeness_cmd.py``) — reporting-only per BACKLOG #238's scope
    fence, so an ordinary plan-mass failure never turns an otherwise-successful
    completeness audit into a crash. ``DetailFormatError`` is the deliberate
    exception: a present unsupported detail refuses the whole semantic read
    instead of allowing a partial report. Previously duplicated as an identical
    try/except at both call sites; this is the single place that failure policy
    now lives.
    """
    try:
        return compute_plan_mass(plan, plan_path, repo_root)
    except DetailFormatError:
        raise
    except Exception:
        return None


def first_saved_plan_mass(
    plan_slug: str, repo_root: Path, plan_path: Path
) -> Optional[dict]:
    """The earliest saved completeness sidecar's ``plan_mass`` snapshot for
    this plan, or ``None`` when none exists yet (this run *is* the first
    audit with mass tracking).

    Walks :func:`list_saved_reviews` (newest-first) in reverse, skipping
    unreadable/ineligible sidecars (:func:`is_reusable_audit_sidecar` — a
    pre-apply checkpoint is crash-recovery evidence, not a real snapshot) and
    legacy sidecars saved before this field existed (``plan_mass is None``).
    Read-only; issues no Claude call."""
    candidates = [
        p
        for p in list_saved_reviews(plan_slug, repo_root, plan_path=plan_path)
        if p.name.endswith(COMPLETENESS_SIDECAR_SUFFIX)
    ]
    for candidate in reversed(candidates):  # oldest first
        try:
            saved = load_review(candidate)
        except ReviewLoadError:
            continue
        if is_reusable_audit_sidecar(saved) and saved.plan_mass is not None:
            return saved.plan_mass
    return None


def plan_mass_to_json(mass: PlanMass) -> dict:
    """JSON-serializable projection of :class:`PlanMass`.

    ``dataclasses.asdict`` recurses through the ``soft_edges`` tuple's
    nested :class:`SoftEdge` instances on its own, matching how
    ``Recommendation`` and ``AuditShapeAdvisory`` are already serialized
    elsewhere in this module — no hand-rolled projection needed. ``None``
    ratios (fewer than two committed steps) are emitted as ``null``, never
    ``0``, since ``asdict`` passes ``None`` through unchanged."""
    return asdict(mass)


def _fmt_ratio(value: Optional[float]) -> str:
    # ``None`` covers two distinct causes (fewer than 2 committed steps, or
    # zero code steps for the two code-scoped ratios) — kept generic rather
    # than naming one and misdescribing the other.
    return "n/a (not computable for this plan)" if value is None else f"{value:.2f}"


def _fmt_delta(current: int, first: Optional[int]) -> str:
    if first is None:
        return "(first audit)"
    delta = current - first
    sign = "+" if delta >= 0 else ""
    return f"({sign}{delta} vs. first audit)"


def render_plan_mass_section(
    mass: PlanMass, *, first_step_count: Optional[int], first_detail_bytes: Optional[int]
) -> str:
    """Render the ``## Plan mass`` report section.

    ``first_step_count`` / ``first_detail_bytes`` are the earliest saved
    completeness sidecar's counts for this plan, or ``None`` when this run
    *is* the first audit — the caller resolves that lookup (this function
    does no disk I/O).
    """
    lines = [
        "## Plan mass",
        "",
        (
            "Findings falling while the plan grows reads as healthy "
            "convergence to the finding-count stopping rule; this block "
            "reports the artifact's own growth so both curves are visible "
            "together. Reporting only — nothing here gates or warns "
            "(BACKLOG #238)."
        ),
        "",
        f"- **Committed step count:** {mass.step_count} "
        f"{_fmt_delta(mass.step_count, first_step_count)}",
        f"- **Detail-bundle size:** {mass.detail_bundle_bytes} bytes "
        f"{_fmt_delta(mass.detail_bundle_bytes, first_detail_bytes)}",
        f"- **Keystone fan-out:** {_fmt_ratio(mass.keystone_fan_out)}",
        f"- **Satellite ratio:** {_fmt_ratio(mass.satellite_ratio)}",
        f"- **Inert-step ratio:** {_fmt_ratio(mass.inert_step_ratio)}",
        f"- **Audit-induced growth:** {_fmt_ratio(mass.audit_induced_growth)}",
    ]
    if mass.soft_edges:
        lines.append("")
        lines.append(
            "**Prose-declared soft edges** — `depends_on` edges the detail "
            "prose marks as ordering-only or test-only:"
        )
        for edge in mass.soft_edges:
            lines.append(
                f"  - step {edge.step_id} → step {edge.depends_on_id}: "
                f"\"{edge.note}\""
            )
    return "\n".join(lines)


def build_report_md(
    *,
    plan_title: str,
    plan_name: str,
    iterate_enabled: bool,
    stop_reason: Optional[str],
    iterations: int,
    applied: list[AppliedOutcome],
    deferred: list[Recommendation],
    advisory_conceptual: list[Recommendation],
    open_findings: list[Recommendation],
    grouped_report_md: str,
    now: Optional[datetime] = None,
    correctness: Optional[list[Recommendation]] = None,
    smells: Optional[list[Recommendation]] = None,
    plan=None,
    code_drifted: bool = False,
    halt_reason: Optional[str] = None,
    bundle_status=None,
    detail_grade: str = GRADE_RUN,
    audit_shape_advisory_display: Optional[AuditShapeAdvisoryDisplay] = None,
    plan_mass: Optional[PlanMass] = None,
    plan_mass_first_step_count: Optional[int] = None,
    plan_mass_first_detail_bytes: Optional[int] = None,
    qualified_result=_QUALIFIED_RESULT_UNSET,
    is_pre_apply_checkpoint: bool = False,
    verdict=ABSENT_BLOCKING_VERDICT,
) -> str:
    """Assemble the full markdown completeness report.

    Leads with a disposition summary + per-category "why it wasn't
    addressed" rationale, then embeds the existing grouped report so the
    artifact is self-contained.

    ``correctness`` is the conceptual-*correctness* finding set (source
    ``plan-correctness``); when provided, the disposition summary always
    reports its count — including ``0`` — so a reader can't mistake "the
    correctness layer wasn't sampled" for "no correctness issues" (report
    defect #3). ``None`` omits the line for callers that don't track it.

    ``smells`` is the advisory plan-structure heuristic set (smell
    detectors plus cross-step granularity split/merge advice). When
    non-empty it renders a dedicated ``## Smells
    (advisory)`` section — reported but never auto-applied. ``None`` (the
    default) omits the section entirely, so callers that don't track smells
    render byte-identically to before.

    ``code_drifted`` is threaded straight to :func:`suggested_next_steps`:
    when True *and* a critical/high finding is present, the suggested-steps
    list leads with a ``reconcile-plan`` rebase bullet (BACKLOG #65). False
    (the default) renders byte-identically to before.

    ``detail_grade`` replaces the two apply-verb header blocks and the
    per-finding ``Address:`` lines with a session-directed-edit instruction at
    jira grade, where
    no findings sidecar exists for an apply verb to read. The default renders
    byte-identically to before.

    ``plan_mass`` (when passed) inserts a ``## Plan mass`` section (#238) —
    via :func:`render_plan_mass_section` — after ``## Halt`` / the audit
    shape advisory and before ``## Applied this run``.
    ``plan_mass_first_step_count`` / ``plan_mass_first_detail_bytes`` are the
    earliest saved sidecar's counts for this plan (``None`` on the first
    audit or when the caller doesn't track deltas). ``None`` (the default)
    for ``plan_mass`` omits the section entirely, rendering byte-identically
    to before.
    """
    jira_grade = detail_grade == GRADE_JIRA
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines: list[str] = []
    lines.append(f"# Completeness report: {plan_title}")
    lines.append("")
    mode = "iterate" if iterate_enabled else "audit-only"
    meta = f"`{plan_name}` · generated {ts} · mode: {mode}"
    if iterate_enabled:
        meta += f" · loop stopped: {stop_reason} after {iterations} iteration(s)"
    lines.append(meta)
    lines.append("")

    if qualified_result is not _QUALIFIED_RESULT_UNSET:
        lines.append(
            render_qualified_result_markdown(
                qualified_result,
                is_pre_apply_checkpoint=is_pre_apply_checkpoint,
            )
        )
        lines.append("")

    # --- Disposition summary -------------------------------------------
    applied_ct = len(applied)
    applied_ok = sum(1 for a in applied if a.verdict == "APPLIED")
    lines.append("## Disposition summary")
    lines.append("")
    if iterate_enabled:
        lines.append(
            f"- **Applied:** {applied_ct} dispatched "
            f"({applied_ok} APPLIED, {applied_ct - applied_ok} other verdict)"
        )
    if correctness is not None:
        lines.append(
            f"- **Conceptual correctness:** {len(correctness)}"
        )
    lines.append(
        f"- **Conceptual completeness (advisory, not auto-applied):** "
        f"{len(advisory_conceptual)}"
    )
    by_kind = {"concept-link": 0, "diagnostic": 0, "info": 0, "triage": 0}
    for rec in deferred:
        k = deferred_kind(rec)
        if k in by_kind:
            by_kind[k] += 1
    lines.append(
        f"- **Deferred:** {len(deferred)} "
        f"({by_kind['concept-link']} missing-concept-link, "
        f"{by_kind['diagnostic']} structural-diagnostic, "
        f"{by_kind['info']} info, {by_kind['triage']} low-payoff)"
    )
    pending_groups = group_pending_decisions(smells or [])
    if smells is not None:
        pending_count = sum(len(g.recs) for g in pending_groups)
        lines.append(
            f"- **Pending concept decisions (advisory, not blocking):** "
            f"{pending_count}"
        )
    if open_findings:
        lines.append(f"- **Open (not reached):** {len(open_findings)}")
    lines.append("")

    if halt_reason:
        lines.append("## Halt")
        lines.append("")
        lines.append(halt_reason)
        lines.append("")

    if audit_shape_advisory_display is not None:
        lines.append(
            render_audit_shape_advisory_markdown(audit_shape_advisory_display)
        )
        lines.append("")

    # --- Plan mass (#238; artifact-growth signal beside the finding curve) -
    if plan_mass is not None:
        lines.append(
            render_plan_mass_section(
                plan_mass,
                first_step_count=plan_mass_first_step_count,
                first_detail_bytes=plan_mass_first_detail_bytes,
            )
        )
        lines.append("")

    # --- Applied -------------------------------------------------------
    if applied:
        lines.append("## Applied this run")
        lines.append("")
        for a in applied:
            # Full finding body (not the clipped title); the apply verdict's
            # own summary is kept verbatim — for non-APPLIED verdicts
            # (BLOCKED especially) it carries the actionable "why / what
            # next", so it must not be clipped. Collapse any internal
            # whitespace/newlines to keep it on a single markdown bullet.
            note = (
                f" — {' '.join(a.summary.split())}"
                if a.summary.strip() else ""
            )
            body = indent_bullet_body((a.rec.body or a.rec.title).strip())
            confidence = f"[{confidence_label(a.rec.confidence)}]"
            if "\n" in body:
                # Text after a closing fence un-closes the block, so a
                # multi-line body keeps its note and confidence on a line of
                # their own.
                note_line = f"{note.lstrip()} {confidence}".strip()
                lines.append(f"- [{a.verdict}] {body}\n  {note_line}")
            else:
                lines.append(f"- [{a.verdict}] {body}{note} {confidence}")
        lines.append("")

    # --- Conceptual correctness (highest priority; run first) ---------
    # A dedicated, first-class topic section for the conceptual-correctness
    # gaps, parallel to the completeness section below. Without it these
    # findings only surfaced as a count plus the by-disposition "open" /
    # deferred buckets, where their nature as correctness gaps was easy to
    # miss. Under #85 the audit never applies correctness, so ``correctness``
    # lists the full conceptual-correctness set; the ``## Applied this run``
    # section only ever holds deterministic applies, so there is nothing to
    # double-list (the dedup filter below is a defensive no-op).
    if correctness:
        bare_plan = bool(getattr(bundle_status, "is_bare", False))
        lines.append("## Conceptual correctness — fix these first")
        lines.append("")
        if jira_grade:
            intro = _HAND_FIX_INTRO
        elif bare_plan:
            intro = CORRECTNESS_INTRO_BARE.format(plan_name=plan_name)
        else:
            intro = CORRECTNESS_INTRO.format(plan_name=plan_name)
        lines.append(intro)
        lines.append("")
        for rec in correctness:
            lines.append(_fmt_finding_line(rec))
            restated = _fmt_restated_line(rec)
            if restated:
                lines.append(restated)
            fix = _fmt_fix_line(rec)
            if fix:
                lines.append(fix)
        lines.append("")

    # --- Conceptual completeness (the headline "why not addressed") ----
    if advisory_conceptual:
        bare_plan = bool(getattr(bundle_status, "is_bare", False))
        lines.append(f"## {_HEADINGS['advisory-conceptual']}")
        lines.append("")
        # No italic wrapping here: the bare-plan rationale still embeds a
        # code block and newlines for the reconcile-plan-walk pointer, which
        # underscores would break.
        if bare_plan:
            lines.append(
                "Coverage gaps in the plan's own ideas are reported for "
                "visibility in this bare-plan audit. Apply actions for this "
                "axis are withheld until a complete detail bundle exists, so "
                "these findings are informational for now."
            )
        elif jira_grade:
            lines.append(_HAND_FIX_INTRO)
        else:
            lines.append(WHY['advisory-conceptual'])
        lines.append("")
        for rec in advisory_conceptual:
            # The bullet carries the full body, so no separate body
            # sub-bullet is needed — just the fix line.
            lines.append(_fmt_finding_line(rec))
            fix = _fmt_fix_line(rec)
            if fix:
                lines.append(fix)
        lines.append("")

    # --- Pending concept decisions (advisory, non-blocking) -----------
    # Parked concept deferrals still awaiting a human decision. Pulled OUT of
    # the ``smells`` list below so they render once here, in their own section,
    # grouped by pending kind — not buried among the generic structural smells.
    # ``build_report_md`` has only the recs (no disk access), so grouping keys
    # on ``rec.source``, not each node's section bucket (that's the status
    # surface's job).
    if pending_groups:
        lines.append("## Pending concept decisions")
        lines.append("")
        lines.append(
            "Concept deferrals still awaiting a human decision — advisory, "
            "never blocking. Resolve each with "
            f"`plan-tool scope-review {plan_name}`."
        )
        lines.append("")
        for group in pending_groups:
            lines.append(f"### {group.label}")
            lines.append("")
            for rec in group.recs:
                lines.append(_fmt_pending_line(rec))
            lines.append("")

    # --- Smells (advisory) --------------------------------------------
    # Rendered inline (like ``## Applied this run``), not routed through the
    # ``deferred_kind`` ladder / ``_HEADINGS`` — smells are a separate
    # advisory class, reported but never auto-applied or blocking. Pending
    # concept decisions are excluded (rendered in their own section above), so
    # they never double-list.
    remaining_smells = [
        r for r in (smells or []) if r.source not in PENDING_DECISION_SOURCES
    ]
    if remaining_smells:
        lines.append("## Smells (advisory)")
        lines.append("")
        lines.append(
            "Advisory plan-structure heuristics (brittle feature refs, "
            "self-referential steps, and cross-step granularity split/merge "
            "advice). Reported for a human to act on; never auto-applied and "
            "never block the run."
        )
        lines.append("")
        for rec in remaining_smells:
            lines.append(_fmt_finding_line(rec))
        lines.append("")

    # --- Other deferred buckets ---------------------------------------
    # ``open`` (eligible-but-not-reached) is no longer a section of its own —
    # it was always plan-correctness-only, now owned by the dedicated
    # ``## Conceptual correctness`` section above. Any deferred (info/triage)
    # correctness is likewise rendered there, so filter it out here to avoid
    # double-listing; non-correctness deferrals (the common case) render
    # unchanged.
    for kind in ("concept-link", "diagnostic", "triage", "info"):
        bucket = [
            r for r in deferred
            if deferred_kind(r) == kind and r.source != "plan-correctness"
        ]
        if not bucket:
            continue
        lines.append(f"## {_HEADINGS[kind]}")
        lines.append("")
        lines.append(f"_{WHY[kind]}_")
        lines.append("")
        for rec in bucket:
            lines.append(_fmt_finding_line(rec))
        lines.append("")

    # --- Suggested next steps -----------------------------------------
    # Kept as the last part of the curated summary, above the embedded
    # grouped report: the grouped report has its own next-steps list, but
    # it sits at the bottom of the full dump where it's lost in the
    # detail. This disposition-level list is what the reader should act on.
    next_steps = suggested_next_steps(
        plan_name=plan_name,
        iterate_enabled=iterate_enabled,
        applied=applied,
        deferred=deferred,
        advisory_conceptual=advisory_conceptual,
        open_findings=open_findings,
        plan=plan,
        code_drifted=code_drifted,
        bundle_status=bundle_status,
        correctness=correctness or (),
        detail_grade=detail_grade,
        qualified_result=qualified_result,
        is_pre_apply_checkpoint=is_pre_apply_checkpoint,
        verdict=verdict,
    )
    lines.append("## Suggested next steps")
    lines.append("")
    for step in next_steps:
        # A step may be a multi-line block; the first line carries the
        # bullet marker, continuation lines indent two spaces to stay
        # inside the list item.
        block = step.split("\n")
        lines.append(f"- {block[0]}")
        lines.extend(f"  {cont}" for cont in block[1:])
    lines.append("")

    # --- Embedded grouped report --------------------------------------
    lines.append("---")
    lines.append("")
    lines.append("## Full grouped report")
    lines.append("")
    lines.append(grouped_report_md.rstrip())
    lines.append("")
    return "\n".join(lines)


def console_summary(
    *,
    plan_name: str,
    iterate_enabled: bool,
    stop_reason: Optional[str],
    iterations: int,
    applied: list[AppliedOutcome],
    deferred: list[Recommendation],
    advisory_conceptual: list[Recommendation],
    open_findings: list[Recommendation],
    report_path: Path,
    plan=None,
    correctness: list[Recommendation] = (),
    bundle_status=None,
    audit_shape_advisory_display: Optional[AuditShapeAdvisoryDisplay] = None,
    resumed_from_sampler_checkpoint: bool = False,
    qualified_result=_QUALIFIED_RESULT_UNSET,
    verdict=ABSENT_BLOCKING_VERDICT,
) -> str:
    """Concise multi-line terminal summary — counts + the headline
    'why' for conceptual gaps + the report path. The full detail lives
    in the report file, not on screen.

    ``correctness`` (the conceptual-*correctness* gaps, never applied by
    the audit under #85) surfaces a 'fix these first' count line so the
    terminal names the highest-priority findings, not just the completeness
    gaps. Empty (the default) keeps the legacy line set — callers that don't
    track it are unchanged.

    ``bundle_status`` (when provided) axis-scopes the conceptual-completeness
    line: on a bare plan those gaps stay informational and the apply verb is
    not named. ``None`` keeps today's output for callers not yet wired.

    ``audit_shape_advisory_display`` (when provided) appends the same current
    keep-or-carve advisory line the report/JSON surfaces; ``None`` omits it.
    ``resumed_from_sampler_checkpoint`` adds presentation-only provenance and
    never changes the final audit decision."""
    by_kind = {"diagnostic": 0, "info": 0, "triage": 0}
    for rec in deferred:
        k = deferred_kind(rec)
        if k in by_kind:
            by_kind[k] += 1

    blocked_ct = sum(1 for a in applied if a.verdict == "BLOCKED")

    lines: list[str] = []
    if iterate_enabled:
        applied_ok = sum(1 for a in applied if a.verdict == "APPLIED")
        lines.append(
            f"plan-tool: completeness done — loop stopped: {stop_reason} "
            f"({iterations} iteration(s))"
        )
        lines.append(
            f"  applied   {len(applied)} "
            f"({applied_ok} APPLIED, "
            f"{len(applied) - applied_ok} other)"
        )
        if blocked_ct:
            lines.append(
                f"  blocked   {blocked_ct} (needs a new step/detail file "
                f"apply can't create — see next steps)"
            )
    else:
        lines.append("plan-tool: completeness audit done")
    if qualified_result is not _QUALIFIED_RESULT_UNSET:
        result = _qualified_result_payload(qualified_result)
        if result is None:
            lines.append("  result    recovery evidence — not a final audit result")
        else:
            lines.append(
                f"  result    {result['headline']} "
                f"(coverage: {result['coverage']}; revision: "
                f"{result['revision_status']})"
            )
    if isinstance(verdict, BlockingVerdict) and (
        verdict.state != BLOCKING_STATE_ABSENT
    ):
        phrase = _CAUSE_PHRASES.get(verdict.untrusted_cause)
        incomplete = f"verdict incomplete: {phrase}" if phrase else "verdict incomplete"
        arms = verdict.blocking_arm_count
        parts = []
        if verdict.blocking_count or not arms:
            parts.append(f"{verdict.blocking_count} gap(s)")
        if arms:
            parts.append(f"{arms} deterministic check(s) failing")
        counted = " + ".join(parts)
        if verdict.state == BLOCKING_STATE_SET:
            lines.append(f"  blocking  {counted}")
        elif verdict.blocking_count or arms:
            lines.append(f"  blocking  {counted} ({incomplete})")
        else:
            # A bare "0 gap(s)" would read as a cleared set.
            lines.append(f"  blocking  {incomplete}")
    else:
        lines.append("  blocking  verdict unavailable")
    if resumed_from_sampler_checkpoint:
        lines.append("  provenance resumed from a durable sampler pass boundary")
    gaps = next_step_gaps(
        verdict, correctness=correctness, advisory_conceptual=advisory_conceptual
    )
    blocking_correctness = list(gaps.close_correctness)
    if blocking_correctness:
        lines.append(
            f"  correctness {len(blocking_correctness)} conceptual gap(s) — fix these "
            f"first through a session-directed edit (NOT auto-applied; "
            f"see report)"
        )
    if gaps.close_completeness:
        lines.append(
            f"  completeness {len(gaps.close_completeness)} conceptual gap(s) — "
            "close through a session-directed edit (need human judgment; see report)"
        )
    if gaps.advisory_count:
        bare_plan = bool(getattr(bundle_status, "is_bare", False))
        note = (
            "; completeness gaps are informational until a complete detail "
            "bundle exists"
            if bare_plan and gaps.advisory_completeness
            else ""
        )
        lines.append(
            f"  advisory  {gaps.advisory_count} conceptual gap(s) — listed in "
            f"the report; "
            f"{'not verified against the current text' if gaps.demoted_stale else 'outside the blocking set'}"
            f"{note}"
        )
    if audit_shape_advisory_display is not None:
        lines.append(render_audit_shape_advisory_console(audit_shape_advisory_display))
    lines.append(
        f"  deferred  {len(deferred)} "
        f"({by_kind['diagnostic']} structural-diagnostic, "
        f"{by_kind['info']} info, {by_kind['triage']} low-payoff)"
    )
    if open_findings and not blocking_correctness:
        # ``open`` is the correctness-only "eligible but not reached" subset;
        # when the correctness line is shown it already covers them, so only
        # emit the standalone open line for legacy callers that don't pass
        # the correctness set.
        lines.append(f"  open      {len(open_findings)} (not reached)")
    lines.append(f"  report  → {report_path}")
    # Next steps are rendered separately (see ``suggested_next_step_commands``
    # → ``_print_next_steps``) so the disposition actions and the pipeline
    # suggestions land in a single clean aligned block instead of two
    # competing ones. This summary is just the counts + report pointer.
    return "\n".join(lines)


def _report_artifact_paths(target_dir: Path, ts_dt: datetime) -> tuple[Path, ...]:
    """Every artifact one completeness report can occupy at one timestamp:
    the markdown report, its findings sidecar, and the data-contract payload."""
    stem = f"{ts_dt.strftime('%Y%m%d-%H%M%S')}{COMPLETENESS_ARTIFACT_STEM_SUFFIX}"
    return (
        target_dir / f"{stem}.md",
        target_dir / f"{stem}.json",
        target_dir / f"{stem}-data-contract.json",
    )


def _reserve_report_timestamp(target_dir: Path, start: datetime) -> datetime:
    """The first whole-second timestamp whose complete artifact set is free.

    A pre-apply checkpoint and the final report it precedes can land in the
    same wall-clock second, and the timestamp stem is the only thing keeping
    them apart — so reserve all three artifacts together before any is
    written, advancing whole seconds until none of them is taken.
    """
    ts_dt = start.replace(microsecond=0)
    while any(p.exists() for p in _report_artifact_paths(target_dir, ts_dt)):
        ts_dt += timedelta(seconds=1)
    return ts_dt


def write_completeness_report(
    plan_path: Path,
    report_md: str,
    *,
    repo_root: Path,
    now: Optional[datetime] = None,
    recommendations: Optional[list[Recommendation]] = None,
    plan_fingerprint: str = "",
    code_fingerprint: Optional[dict[str, str]] = None,
    detail_bundle_fingerprint: Optional[dict[str, str]] = None,
    plan_rel_path: Optional[str] = None,
    data_contract_payloads: Optional[dict[str, dict]] = None,
    audit_shape_advisory: Optional[AuditShapeAdvisory] = None,
    audit_coverage: Optional[dict[str, object]] = None,
    is_pre_apply_checkpoint: bool = False,
    plan_mass: Optional[dict] = None,
    audit_stage: Optional[str] = None,
    audit_revision: Optional[dict[str, object]] = None,
    checkpoint_audit_revision: Optional[dict[str, object]] = None,
    qualified_result: object = _QUALIFIED_RESULT_UNSET,
    audit_stage_is_sampled: bool = False,
    plan=None,
) -> Path:
    """Persist ``report_md`` under the plan's reports directory —
    ``<plan-dir>/plan-details/<slug>/reports/`` (:func:`plan_reports_dir`) —
    and return the markdown path. Filename is a sortable UTC timestamp so
    successive runs accumulate rather than clobber; two reports written in
    one wall-clock second get distinct whole-second stems (see
    :func:`_reserve_report_timestamp`), and the reserved timestamp is what
    :func:`save_review` records as ``created_at``.

    When ``recommendations`` is provided, also writes a sibling JSON
    sidecar via :func:`save_review` (``kind="completeness"``) so
    ``completeness-apply`` can walk and address the structured findings
    without re-running the audit. ``plan_rel_path`` is the plan's repo-
    relative posix path stored inside the sidecar; required when a
    sidecar is being written.

    When a sidecar is written, ``plan_fingerprint`` (the
    :func:`compute_plan_fingerprint` digest) and ``code_fingerprint`` (the
    :func:`compute_code_fingerprint` path→hash map) captured at save time
    are persisted alongside the findings so a later reuse check can compare
    them against current plan/code state. Both default to the unset
    sentinels (``""`` / ``{}``), so omitting them writes a legacy-shaped
    sidecar. The fingerprints are axis-agnostic: the writer stores the
    ``recommendations`` list flat, and a reuse consumer splits it back on
    each ``Recommendation.source`` (``plan-correctness`` vs
    ``plan-completeness``).

    ``data_contract_payloads`` writes a sibling payload artifact keyed by
    recommendation id for ``source="data-contract"`` findings. It deliberately
    does not change the saved-review schema.

    ``audit_coverage`` is the completed conceptual audit's coverage result.
    When a completeness sidecar is written, it is normalized and persisted as
    optional provenance; omission remains legacy-unknown rather than a clean
    coverage verdict.

    ``is_pre_apply_checkpoint`` marks the sidecar as pre-apply crash-recovery
    evidence rather than a converged final report, moving it to the role-aware
    schema version. It only reaches disk through the sidecar, so a caller that
    omits ``recommendations`` writes no role either; the default is the
    ordinary final save, which leaves the key absent and the version alone.
    A checkpoint may carry ``checkpoint_audit_revision`` as its immutable
    plan/detail provenance. It remains distinct from ``audit_revision``,
    which belongs inside a qualified final result.

    ``plan_mass`` is #238's optional structural-mass snapshot
    (:func:`plan_mass_to_json`), threaded straight to :func:`save_review` so
    a later :func:`first_saved_plan_mass` lookup can use this run as a
    baseline. Like the other optional sidecar fields, it only reaches disk
    when a sidecar is written at all (``recommendations is not None``).

    ``audit_stage`` is the bare/detail bar stamped on the completeness
    sidecar. When omitted and a sidecar is written, it is derived from the
    plan's current detail-bundle status at save time. Derive is best-effort
    (same soft-fail set as stamp): an absent/unparseable plan omits the
    field rather than crashing after the ``.md`` is already on disk.

    ``plan`` is the caller's already-parsed :class:`~plan_tool.schema.Plan`
    (BACKLOG #166) — when supplied, it is reused for signature stamping, the
    audit-stage derivation, and :func:`save_review`'s ``step_ids`` capture
    instead of each re-parsing ``plan_path`` independently, and it keeps
    ``step_ids`` describing the same read as the caller's ``plan_fingerprint``
    rather than a separate, later one. Omit it to preserve the prior
    self-parsing behavior (e.g. a caller with no plan already in hand).
    """
    if (
        qualified_result is not _QUALIFIED_RESULT_UNSET
        and audit_revision is not None
    ):
        raise ValueError(
            "audit_revision must be nested in qualified_result for new "
            "completeness sidecars"
        )
    target_dir = plan_reports_dir(plan_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    ts_dt = _reserve_report_timestamp(
        target_dir, now or datetime.now(timezone.utc)
    )
    ts = ts_dt.strftime("%Y%m%d-%H%M%S")
    path = target_dir / f"{ts}{COMPLETENESS_REPORT_SUFFIX}"
    durable_write_text(path, report_md)
    if recommendations is not None:
        if plan_rel_path is None:
            raise ValueError(
                "write_completeness_report requires plan_rel_path when "
                "recommendations is provided"
            )
        from plan_tool.locator import slug_from_filename

        normalized_audit_coverage = None
        if audit_coverage is not None:
            normalized_audit_coverage = normalize_audit_coverage(audit_coverage)
            if normalized_audit_coverage is None:
                raise ValueError("audit_coverage is not a valid audit producer state")

        plan_slug = slug_from_filename(plan_path)
        assert plan_slug is not None
        # One parse serves signature stamping, audit-stage derivation, and
        # (below) save_review's step_ids capture — reuse the caller's
        # already-parsed ``plan`` when supplied, else parse once here rather
        # than the three independent re-parses this used to be (BACKLOG #166).
        parsed_plan = plan
        if parsed_plan is None:
            try:
                parsed_plan = parse_plan(plan_path)
            except (
                FileNotFoundError,
                OSError,
                UnicodeDecodeError,
                ParseError,
                ValidationError,
            ):
                parsed_plan = None
        resolved_audit_stage = audit_stage
        if (
            resolved_audit_stage is None
            and not audit_stage_is_sampled
        ):
            # Preserve the audit-stage read's independent retry after a
            # transient failure of the shared parse.
            if parsed_plan is None:
                try:
                    parsed_plan = parse_plan(plan_path)
                except (
                    FileNotFoundError,
                    OSError,
                    UnicodeDecodeError,
                    ParseError,
                    ValidationError,
                ):
                    parsed_plan = None
            # Soft-fail like stamp above: ``.md`` already landed; do not orphan
            # it without a sidecar when the bundle status can't be derived.
            if parsed_plan is not None:
                try:
                    from plan_tool.cli.completeness_phases import derive_audit_stage
                    from plan_tool.review import audit_detail_bundle_status

                    bundle_status = audit_detail_bundle_status(
                        parsed_plan, plan_path, repo_root, detail_grade=GRADE_RUN
                    )
                    resolved_audit_stage = derive_audit_stage(bundle_status)
                except (
                    FileNotFoundError,
                    OSError,
                    UnicodeDecodeError,
                    ParseError,
                    ValidationError,
                ):
                    resolved_audit_stage = None
        # Stamp the medium ``granularity-split`` MIXED-STEP finding riding in
        # ``smell_recs`` with its target step's signature so a later split guard
        # can gate precisely; non-directive completeness recs pass through.
        # Best-effort: if the plan file is absent/unparseable we can't compute
        # signatures, so leave the recs unstamped (target_signature=None → the
        # guard's coarse fallback) rather than crash the report write.
        if parsed_plan is not None:
            stamped_recommendations = stamp_target_signatures(
                parsed_plan, recommendations
            )
        else:
            stamped_recommendations = recommendations
        save_kwargs = dict(
            plan_slug=plan_slug,
            plan_path=plan_rel_path,
            repo_root=repo_root,
            report_md=report_md,
            recommendations=stamped_recommendations,
            plan_fingerprint=plan_fingerprint,
            code_fingerprint=code_fingerprint or {},
            detail_bundle_fingerprint=detail_bundle_fingerprint,
            kind="completeness",
            now=ts_dt,
            plan=parsed_plan,
            audit_shape_advisory=audit_shape_advisory,
            audit_coverage=normalized_audit_coverage,
            is_pre_apply_checkpoint=is_pre_apply_checkpoint,
            plan_mass=plan_mass,
            audit_stage=resolved_audit_stage,
            audit_revision=audit_revision,
            checkpoint_audit_revision=checkpoint_audit_revision,
        )
        if (
            qualified_result is not _QUALIFIED_RESULT_UNSET
            and (qualified_result is not None or is_pre_apply_checkpoint)
        ):
            save_kwargs["qualified_result"] = qualified_result
        sidecar_path = save_review(**save_kwargs)
        if data_contract_payloads:
            payload_path = sidecar_path.with_name(
                f"{sidecar_path.stem}-data-contract.json"
            )
            durable_write_text(
                payload_path,
                json.dumps(
                    {
                        "kind": "data-contract",
                        "review_id": sidecar_path.stem,
                        "payloads": data_contract_payloads,
                    },
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
            )
    return path
