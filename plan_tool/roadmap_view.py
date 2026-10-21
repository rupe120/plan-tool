"""Turn a roadmap cross-reference id into the row it names.

Every cross-row reference in a roadmap — ``FieldRow.entity_id``,
``ConstraintRow.anchor_ids``, ``DecisionRow.anchor``,
``PlanRow.component_ids``, ``FeedbackTarget.row_id``, and every other
id-shaped field the four staged artifacts carry — is a bare string in YAML
today. Nothing in ``plan_tool.roadmap_artifacts`` or ``plan_tool.roadmap_gates``
turns one into the row it names: the gates return ``Violation`` records that
block a stage, not a label a renderer can print. This module is that missing
piece — the one place a later view turns an id into a human-readable label,
so no renderer invents its own rule for the same feedback-target row kinds.

Two indices, built once and handed to every resolve call: one roadmap-wide
index of design rows (:func:`build_design_row_index`), keyed by id and
carrying every match when an id is genuinely ambiguous, and a separate index
of ``RemovalRecord``\\ s (:func:`build_removal_index`). They stay separate
because ``current`` mode must resolve no removal at all — folding them
together would make an ordinary :func:`resolve_id` call quietly resolve
through a removal for every caller, not just the one (a feedback target) that
is allowed to.

A dangling id (matches nothing) and an ambiguous one (matches more than one
row) are **rendering annotations, not findings**: both come back as a
:class:`Resolution`, never an exception. This module is the first reader of
roadmap artifacts no gate has just blessed, so a directly edited roadmap
resolving oddly is the expected case, not a bug in this module to fix by
raising.

A stdlib-plus leaf, one level above ``plan_tool.roadmap_gates``: its only
first-party imports are artifact parsing and live loading, the authoritative
``plan_tool.roadmap_gates.feedback_target_ids`` membership call, relation and
seed-view leaves, and the accepted-version reader with its fixed inventory.
It never imports ``plan_tool.roadmap``, so the one-way chain (artifacts ->
gates -> orchestrator) stays intact.

:func:`load_roadmap` turns a ``plans_dir``/``slug`` pair into a
:class:`LoadedRoadmap`. It parses only the accepted stored bundle, naming any
member it could not parse; a folder with no accepted head is refused with
:class:`~plan_tool.roadmap_seed_manifest.NoPublishedRoadmapVersionError`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import indent
from typing import Callable, Mapping, Optional

from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    ComponentRow,
    ComponentsArtifact,
    ConstraintRow,
    ConstraintsArtifact,
    DOMAIN_FILENAME,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldType,
    HostingRow,
    OrderingEntry,
    PLANS_FILENAME,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RemovalRecord,
    RoadmapArtifact,
    RoadmapArtifactError,
    StackRow,
    StoreRow,
    WorkflowRow,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    parse_draft_seed_provenance,
    parse_plans_artifact,
    resolve_draft_seed_path,
    roadmap_dir,
)
from plan_tool.roadmap_gates import feedback_target_ids
from plan_tool.roadmap_relations import (
    RelationKind,
    RoadmapRelation,
    extract_declared_relations,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_STALE,
    DraftSeedClassification,
    ORPHAN_SEED_RECORD_FILE,
    ORPHAN_SEED_RECORD_SIDECAR_ENTRY,
    NoPublishedRoadmapVersionError,
    OrphanSeedRecord,
    no_published_version_message,
)
from plan_tool.roadmap_versions import VERSION_ARTIFACT_INVENTORY, load_accepted_version

# --------------------------------------------------------------------------
# The design-row index
# --------------------------------------------------------------------------


# The row-kind vocabulary ``roadmap_gates``'s own row enumeration uses, so a
# resolved label and a gate's violation message never disagree about what to
# call the same row, and every ``kind=``/``citer_kind=`` argument in this
# module draws from one place instead of a hand-typed literal per call site.
KIND_ENTITY = "entity"
KIND_BUSINESS_RULE = "business rule"
KIND_WORKFLOW = "workflow"
KIND_DECISION = "decision"
KIND_DISPOSITION = "disposition"
KIND_CONSTRAINT = "constraint"
KIND_HOSTING = "hosting"
KIND_STACK = "stack"
KIND_SYSTEM_PATTERN = "system pattern"
KIND_COMPONENT_PATTERN = "component pattern"
KIND_COMPONENT = "component"
KIND_STORE = "store"
KIND_PLAN = "plan"
KIND_ASSUMPTION = "assumption"
# The two review-mode-only citer kinds :class:`Citation` carries that are not
# themselves design rows.
KIND_FEEDBACK = "feedback"
KIND_REMOVAL = "removal"


@dataclass(frozen=True)
class DesignRowEntry:
    """One design row, tagged with the label its collection renders under.

    ``kind`` reuses this module's own row-kind vocabulary (``KIND_ENTITY``,
    ``KIND_BUSINESS_RULE``, ... ``KIND_ASSUMPTION``), so a resolved label and
    a gate's violation message never disagree about what to call the same
    row — and so ``kind`` can double as the scope tag :func:`display_label`
    needs to disambiguate a ``PatternRow``.
    """

    kind: str
    id: str
    row: object


def _entries_of(kind: str, rows: "tuple[object, ...]") -> tuple[DesignRowEntry, ...]:
    return tuple(DesignRowEntry(kind=kind, id=row.id, row=row) for row in rows)


def _domain_entries(artifact: DomainArtifact) -> tuple[DesignRowEntry, ...]:
    """Every domain design row, in render order."""
    return (
        *_entries_of(KIND_ENTITY, artifact.entities),
        *_entries_of(KIND_BUSINESS_RULE, artifact.business_rules),
        *_entries_of(KIND_WORKFLOW, artifact.workflows),
        *_entries_of(KIND_DECISION, artifact.decisions),
    )


def _constraints_entries(artifact: ConstraintsArtifact) -> tuple[DesignRowEntry, ...]:
    """Every constraints design row, in render order."""
    return (
        *_entries_of(KIND_HOSTING, artifact.hosting),
        *_entries_of(KIND_STACK, artifact.stack or ()),
        *_entries_of(KIND_DISPOSITION, artifact.dispositions),
        *_entries_of(KIND_CONSTRAINT, artifact.constraints),
        *_entries_of(KIND_DECISION, artifact.decisions),
    )


def _components_entries(artifact: ComponentsArtifact) -> tuple[DesignRowEntry, ...]:
    """Every components design row, in render order."""
    return (
        *_entries_of(KIND_SYSTEM_PATTERN, artifact.system_patterns),
        *_entries_of(KIND_COMPONENT_PATTERN, artifact.component_patterns),
        *_entries_of(KIND_STORE, artifact.stores),
        *_entries_of(KIND_COMPONENT, artifact.components),
        *_entries_of(KIND_DECISION, artifact.decisions),
    )


def _plans_entries(artifact: PlansArtifact) -> tuple[DesignRowEntry, ...]:
    """Every plans design row, in render order."""
    return (
        *_entries_of(KIND_PLAN, artifact.plans),
        *_entries_of(KIND_ASSUMPTION, artifact.assumptions),
        *_entries_of(KIND_DECISION, artifact.decisions),
    )


def build_design_row_index(
    *,
    domain: Optional[DomainArtifact] = None,
    constraints: Optional[ConstraintsArtifact] = None,
    components: Optional[ComponentsArtifact] = None,
    plans: Optional[PlansArtifact] = None,
) -> Mapping[str, tuple[DesignRowEntry, ...]]:
    """Every design row across whichever artifacts are supplied, keyed by id.

    Every parameter is optional — unlike ``ArtifactEnvelope.domain``, this
    builder is not the orchestrator's stage-gate envelope and has no
    mandatory artifact. Rows accumulate in stage order (domain, constraints,
    components, plans) and, within an artifact, in that artifact's own
    render-field order, so a duplicated id's matches come out in the plan's
    stated render order with no separate sort step. Membership is taken from
    :func:`plan_tool.roadmap_gates.feedback_target_ids` rather than
    re-derived: an entry is kept only when that call also names its id a valid
    feedback target for the artifact it came from.
    """
    index: "dict[str, list[DesignRowEntry]]" = defaultdict(list)
    for artifact, build_entries in (
        (domain, _domain_entries),
        (constraints, _constraints_entries),
        (components, _components_entries),
        (plans, _plans_entries),
    ):
        if artifact is None:
            continue
        ids = feedback_target_ids(artifact)
        for entry in build_entries(artifact):
            if entry.id in ids:
                index[entry.id].append(entry)
    return {row_id: tuple(entries) for row_id, entries in index.items()}


def _build_row_index(
    domain: Optional[DomainArtifact],
    constraints: Optional[ConstraintsArtifact],
    components: Optional[ComponentsArtifact],
    plans: Optional[PlansArtifact],
    *,
    rows_of: Callable[[object], "tuple[object, ...]"],
    key_of: Callable[[object], str],
) -> Mapping[str, tuple[object, ...]]:
    """The shared shape :func:`build_removal_index` and
    :func:`build_feedback_index` both build: every ``rows_of(artifact)``
    item across whichever of the four artifacts are supplied, keyed by
    ``key_of(item)``, with every colliding key kept rather than one
    silently overwriting another."""
    index: "dict[str, list[object]]" = defaultdict(list)
    for artifact in (domain, constraints, components, plans):
        if artifact is None:
            continue
        for item in rows_of(artifact):
            index[key_of(item)].append(item)
    return {key: tuple(items) for key, items in index.items()}


def build_removal_index(
    *,
    domain: Optional[DomainArtifact] = None,
    constraints: Optional[ConstraintsArtifact] = None,
    components: Optional[ComponentsArtifact] = None,
    plans: Optional[PlansArtifact] = None,
) -> Mapping[str, tuple[RemovalRecord, ...]]:
    """Every ``RemovalRecord`` across whichever artifacts are supplied, keyed
    by ``removed_id`` — kept separate from :func:`build_design_row_index` so
    an ordinary :func:`resolve_id` call never resolves through a removal.

    A colliding ``removed_id`` is exactly as reachable as a colliding
    design-row id and gets the same treatment: nothing in ``roadmap_gates``
    enforces its uniqueness, so every record lands under its key rather than
    one silently overwriting another.
    """
    return _build_row_index(
        domain,
        constraints,
        components,
        plans,
        rows_of=lambda artifact: artifact.removals,
        key_of=lambda record: record.removed_id,
    )


def build_feedback_index(
    *,
    domain: Optional[DomainArtifact] = None,
    constraints: Optional[ConstraintsArtifact] = None,
    components: Optional[ComponentsArtifact] = None,
    plans: Optional[PlansArtifact] = None,
) -> Mapping[str, tuple[FeedbackRow, ...]]:
    """Every ``FeedbackRow`` across whichever artifacts are supplied, keyed by
    id — mirrors :func:`build_removal_index`'s shape.

    A feedback id declared by two different artifacts is exactly as
    reachable as a colliding ``removed_id``: ``roadmap_gates`` enforces
    feedback-id uniqueness only within one artifact, never across all four,
    so every row lands under its key rather than one silently overwriting
    another.
    """
    return _build_row_index(
        domain,
        constraints,
        components,
        plans,
        rows_of=lambda artifact: artifact.feedback,
        key_of=lambda row: row.id,
    )


# --------------------------------------------------------------------------
# Display labels
# --------------------------------------------------------------------------


def display_label(row: object, *, kind: Optional[str] = None) -> str:
    """The one label this codebase uses for ``row``.

    Every later view interpolates this rather than reading a row's fields
    directly, so the display rule set here never gets a second, drifting
    copy. ``kind`` is required only for a bare ``PatternRow`` — the row
    itself does not carry which of the two pattern collections it came from,
    and guessing one would reproduce the exact ambiguity this module exists
    to remove, so that case raises instead. This is the only raise in this
    module apart from an unrecognized row type; every id-resolution outcome
    below is a rendering annotation, never an exception.
    """
    if isinstance(row, (EntityRow, WorkflowRow, ComponentRow)):
        return row.name
    if isinstance(row, (BusinessRuleRow, ConstraintRow, AssumptionRow)):
        return row.statement
    if isinstance(row, PlanRow):
        return row.title
    if isinstance(row, DecisionRow):
        return row.chosen_option
    if isinstance(row, FeedbackRow):
        return row.request
    if isinstance(row, AttributeDispositionRow):
        return f"{row.attribute}: {row.disposition.value}"
    if isinstance(row, HostingRow):
        product = f" ({row.product})" if row.product is not None else ""
        return f"hosting {row.facet}: {row.value}{product}"
    if isinstance(row, StoreRow):
        product = f" ({row.product})" if row.product is not None else ""
        return f"store: {row.category}, {row.sharing}{product}"
    if isinstance(row, StackRow):
        return f"stack {row.concern}: {'open' if row.open else row.choice or 'no choice'}"
    if isinstance(row, PatternRow):
        if kind is None:
            raise ValueError(
                "display_label requires 'kind' to label a PatternRow — it "
                "does not carry its own scope ('system pattern' vs. "
                "'component pattern')"
            )
        return f"{kind}: {row.name}"
    if isinstance(row, RemovalRecord):
        # Worded as a tombstone, never as a resolved row's label: nothing
        # recovers what the removed row said.
        return f"removed: {row.removed_id} — {row.rationale}"
    raise TypeError(f"display_label does not know how to label {type(row).__name__}")


# --------------------------------------------------------------------------
# Resolution
# --------------------------------------------------------------------------

RESOLUTION_RESOLVED = "resolved"
RESOLUTION_DANGLING = "dangling"
RESOLUTION_AMBIGUOUS = "ambiguous"
RESOLUTION_ARTIFACT_SCOPE = "artifact-scope"


@dataclass(frozen=True)
class Resolution:
    """The outcome of turning one id or feedback target into a row.

    ``text`` is already the ready-to-print string for every status — the
    resolved label, or the literal marker text (``"⚠ undefined: ..."`` /
    ``"⚠ ambiguous: ..."``) — so a caller interpolates ``text`` uniformly and
    never invents its own wording for a dangling or ambiguous id.
    ``matches`` is populated only for ``RESOLUTION_AMBIGUOUS``, one label per
    row (or removal) the id matched, in the index's stage-then-source order.
    """

    status: str
    text: str
    matches: tuple[str, ...] = ()


def _ambiguous(row_id: str, labels: "tuple[str, ...]") -> Resolution:
    """The one shape every ambiguous-id outcome in this module shares, so
    the marker text can't drift between call sites for the same status."""
    return Resolution(
        status=RESOLUTION_AMBIGUOUS, text=f"⚠ ambiguous: {row_id}", matches=labels
    )


def resolve_id(id: str, index: Mapping[str, tuple[DesignRowEntry, ...]]) -> Resolution:
    """Resolve a bare cross-reference id against the design-row index alone.

    Never raises: a dangling or ambiguous id is a rendering annotation, not a
    finding a later view enforces.
    """
    entries = index.get(id, ())
    if not entries:
        return Resolution(status=RESOLUTION_DANGLING, text=f"⚠ undefined: {id}")
    if len(entries) > 1:
        return _ambiguous(
            id,
            tuple(display_label(entry.row, kind=entry.kind) for entry in entries),
        )
    entry = entries[0]
    return Resolution(
        status=RESOLUTION_RESOLVED, text=display_label(entry.row, kind=entry.kind)
    )


def resolve_id_of_kind(ref_id: str, loaded: LoadedRoadmap, *, kind: str) -> Resolution:
    """Resolve an id only when its unique row has the expected ``kind``."""
    entries = loaded.design_row_index.get(ref_id, ())
    if len(entries) == 1 and entries[0].kind != kind:
        return Resolution(
            status=RESOLUTION_DANGLING,
            text=f"⚠ wrong kind: {ref_id} is a {entries[0].kind}, not {kind}",
        )
    return resolve_id(ref_id, loaded.design_row_index)


def resolve_feedback_target(
    target: FeedbackTarget,
    index: Mapping[str, tuple[DesignRowEntry, ...]],
    removals: Mapping[str, tuple[RemovalRecord, ...]],
) -> Resolution:
    """Resolve a feedback row's target — the one caller allowed to fall
    through to a removal.

    Branches on ``target.kind`` before any lookup: an ``ARTIFACT``-kind
    target has no ``row_id`` to resolve, by parse-time construction. A
    ``ROW``-kind target tries the design-row index first and only falls back
    to ``removals`` on a dangling result, so a feedback row may keep naming
    an id a prior revision removed without ever reading as undefined. A
    ``removed_id`` more than one removal record declares resolves
    ``ambiguous`` the same way a colliding design-row id does.
    """
    if target.kind is FeedbackTargetKind.ARTIFACT:
        return Resolution(status=RESOLUTION_ARTIFACT_SCOPE, text="the whole artifact")

    resolution = resolve_id(target.row_id, index)
    if resolution.status != RESOLUTION_DANGLING:
        return resolution

    records = removals.get(target.row_id, ())
    if not records:
        return resolution
    if len(records) > 1:
        return _ambiguous(
            target.row_id, tuple(display_label(record) for record in records)
        )
    return Resolution(status=RESOLUTION_RESOLVED, text=display_label(records[0]))


# --------------------------------------------------------------------------
# Loading a roadmap off disk
# --------------------------------------------------------------------------

MODE_CURRENT = "current"
MODE_REVIEW = "review"


@dataclass(frozen=True)
class UnparseableArtifact:
    """One artifact that exists on disk but failed to parse.

    Kept as its own record, distinct from an absent artifact's bare filename
    in :attr:`LoadedRoadmap.absent`: "not found" and "found but broken" call
    for different operator fixes, and a single list could not tell them
    apart.
    """

    filename: str
    reason: str


@dataclass(frozen=True)
class LoadedRoadmap:
    """One snapshot of a roadmap directory: whatever parsed, what didn't, and
    the roadmap-wide indices built from what did.

    Deliberately not called an envelope: every one of the four artifact
    fields is ``Optional``, unlike ``ArtifactEnvelope.domain``'s mandatory
    field, because the normal case this type exists to serve is a partly
    authored roadmap. ``mode`` is carried as data rather than decided by a
    renderer: under :data:`MODE_CURRENT`, ``removal_index`` and
    ``feedback_index`` are empty by construction; under :data:`MODE_REVIEW`
    they carry every removal record and feedback row the parsed artifacts
    declare. ``design_row_index`` is mode-independent, and so are
    ``all_removal_index`` / ``all_feedback_index`` — the same two indices
    built unconditionally, so a caller that must distinguish "genuinely
    undeclared" from "declared but hidden by the current mode" (see
    :func:`resolve_citation_subject`) has a real index to consult instead of
    a raw scan over the parsed artifacts.
    """

    slug: str
    mode: str
    directory_exists: bool
    domain: Optional[DomainArtifact]
    constraints: Optional[ConstraintsArtifact]
    components: Optional[ComponentsArtifact]
    plans: Optional[PlansArtifact]
    absent: tuple[str, ...]
    unparseable: tuple[UnparseableArtifact, ...]
    design_row_index: Mapping[str, tuple[DesignRowEntry, ...]]
    removal_index: Mapping[str, tuple[RemovalRecord, ...]]
    feedback_index: Mapping[str, tuple[FeedbackRow, ...]]
    all_removal_index: Mapping[str, tuple[RemovalRecord, ...]]
    all_feedback_index: Mapping[str, tuple[FeedbackRow, ...]]


SEED_TRACKING_TRACKED = "tracked"
SEED_TRACKING_UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SeedLifecycleSummary:
    """The active plans' classified draft-seed state, supplied by the CLI.

    ``roadmap_view`` accepts this small projection instead of opening draft
    files or lifecycle state itself.  The classifier covers only active plan
    rows, so a retired sidecar entry cannot appear in this summary.
    """

    tracking: str
    current_plan_ids: tuple[str, ...] = ()
    invalidated_plan_ids: tuple[str, ...] = ()
    classifications: Mapping[str, DraftSeedClassification] = field(
        default_factory=dict
    )
    reason: Optional[str] = None


def summarize_seed_lifecycle(
    loaded: LoadedRoadmap,
    classifications: Optional[Mapping[str, DraftSeedClassification]] = None,
    *,
    unavailable_reason: Optional[str] = None,
) -> SeedLifecycleSummary:
    """Fold supplied draft-seed classifications into summary lifecycle counts.

    The CLI owns classification and folds a sidecar-level classifier failure
    into ``unavailable_reason``.  An unreadable stage 4 takes precedence,
    because seed readiness needs its active plan rows.
    """
    if loaded.plans is None:
        return SeedLifecycleSummary(
            tracking=SEED_TRACKING_UNAVAILABLE,
            reason="04-roadmap.md is not readable",
        )
    if unavailable_reason is not None:
        return SeedLifecycleSummary(
            tracking=SEED_TRACKING_UNAVAILABLE,
            reason=unavailable_reason,
        )
    if classifications is None:
        return SeedLifecycleSummary(
            tracking=SEED_TRACKING_UNAVAILABLE,
            reason="draft seed classifications are unavailable",
        )

    current: list[str] = []
    invalidated: list[str] = []
    for plan in loaded.plans.plans:
        classification = classifications.get(plan.id)
        if classification is not None and classification.state == DRAFT_SEED_STATE_CURRENT:
            current.append(plan.id)
        else:
            invalidated.append(plan.id)
    return SeedLifecycleSummary(
        tracking=SEED_TRACKING_TRACKED,
        current_plan_ids=tuple(current),
        invalidated_plan_ids=tuple(invalidated),
        classifications=classifications,
    )


def _draft_seed_remedy(
    loaded: LoadedRoadmap, classification: DraftSeedClassification
) -> str:
    """Return the shared operator remedy for one non-current seed state."""
    if classification.state in {
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_PATH_ESCAPING,
    }:
        return (
            "materialize with "
            f"{_summary_command(loaded, f'--materialize {classification.plan_id}')}"
        )
    if classification.state == DRAFT_SEED_STATE_DIGEST_MISMATCHED:
        return (
            "review the draft diff, then accept with "
            f"{_summary_command(loaded, f'--accept-seed {classification.plan_id}')} "
            "or discard with "
            f"{_summary_command(loaded, f'--materialize {classification.plan_id}')}"
        )
    if classification.state == DRAFT_SEED_STATE_DUPLICATE:
        return "draft_seed_path basenames collide; resolve them in a roadmap revision"
    return ""


def _seed_state_unavailable_reason(loaded: LoadedRoadmap) -> str:
    """Name why a per-plan seed projection cannot be rendered."""
    if PLANS_FILENAME in loaded.absent:
        return "04-roadmap.md is absent"
    if any(item.filename == PLANS_FILENAME for item in loaded.unparseable):
        return "04-roadmap.md is unparseable"
    return "04-roadmap.md is not readable"


def render_seed_state_view(
    loaded: LoadedRoadmap,
    classifications: Mapping[str, DraftSeedClassification],
    orphans: "tuple[OrphanSeedRecord, ...]",
    *,
    unavailable_reason: Optional[str] = None,
) -> str:
    """Render ``--view seeds`` from the CLI-supplied seed projections.

    This renderer never opens the sidecar or draft directories itself.  An
    unavailable projection and unusual supplied records remain annotations,
    so this read-only view always produces text rather than raising.
    """
    lines = [_mode_header(loaded)]
    notice = _artifact_notice(loaded)
    if notice is not None:
        lines.append(notice)

    if loaded.plans is None:
        lines.append(
            "seed states unavailable: "
            f"{_seed_state_unavailable_reason(loaded)}; per-plan seed states "
            "and orphans cannot be reported"
        )
        return "\n".join(lines)
    if unavailable_reason is not None:
        lines.append(f"seed states unavailable: {unavailable_reason}")
        return "\n".join(lines)

    lines.append("seeds:")
    for plan in loaded.plans.plans:
        classification = classifications.get(plan.id)
        if classification is None:
            lines.append(
                indent(
                    f"- {plan.id}: classification unavailable for this plan row", "  "
                )
            )
            continue
        line = f"- {plan.id}: {classification.state}"
        if classification.detail:
            line += f" — {classification.detail}"
        remedy = _draft_seed_remedy(loaded, classification)
        if remedy:
            line += f" — {remedy}"
        lines.append(indent(line, "  "))

    sidecar_orphans = tuple(
        record
        for record in orphans
        if record.kind == ORPHAN_SEED_RECORD_SIDECAR_ENTRY
    )
    file_orphans = tuple(
        record for record in orphans if record.kind == ORPHAN_SEED_RECORD_FILE
    )
    lines.extend(
        [
            "orphans:",
            "  sidecar entries naming no plan row:",
            indent(
                "\n".join(
                    f"- {record.plan_id}" for record in sidecar_orphans
                )
                or "(none)",
                "    ",
            ),
            "  files naming no plan row:",
            indent(
                "\n".join(f"- {record.path}" for record in file_orphans)
                or "(none)",
                "    ",
            ),
        ]
    )
    return "\n".join(lines)


def _parse_accepted_artifact_bundle(
    artifact_bytes: tuple[bytes, ...],
) -> tuple[
    DomainArtifact | None,
    ConstraintsArtifact | None,
    ComponentsArtifact | None,
    PlansArtifact | None,
    tuple[UnparseableArtifact, ...],
]:
    """Parse stored members independently while retaining accepted-head authority."""
    parsers = (
        parse_domain_artifact,
        parse_constraints_artifact,
        parse_components_artifact,
        parse_plans_artifact,
    )
    parsed: list[RoadmapArtifact | None] = []
    unparseable: list[UnparseableArtifact] = []
    for entry, data, parser in zip(
        VERSION_ARTIFACT_INVENTORY, artifact_bytes, parsers, strict=True
    ):
        try:
            parsed.append(parser(data.decode("utf-8")))
        except (RoadmapArtifactError, UnicodeDecodeError) as exc:
            unparseable.append(UnparseableArtifact(filename=entry.member_name, reason=str(exc)))
            parsed.append(None)
    domain, constraints, components, plans = parsed
    return domain, constraints, components, plans, tuple(unparseable)


def load_roadmap(plans_dir: Path, slug: str, *, mode: str = MODE_CURRENT) -> LoadedRoadmap:
    """Read the four staged artifacts from the accepted version's stored bytes.

    The version store is the only source; top-level artifact files are never
    read. A folder with no accepted head raises
    :class:`NoPublishedRoadmapVersionError`, and an invalid accepted-head
    authority record raises ``RoadmapVersionError`` — a corrupt head is not
    "no head". An invalid ``slug`` raises ``ValueError``. Members parse
    independently, so one unparseable stored member does not hide the others.
    """
    directory_exists = roadmap_dir(plans_dir, slug).exists()
    accepted_version = load_accepted_version(plans_dir=plans_dir, slug=slug)

    if accepted_version is None:
        raise NoPublishedRoadmapVersionError(no_published_version_message(plans_dir, slug))
    domain, constraints, components, plans, unparseable = _parse_accepted_artifact_bundle(
        accepted_version.artifact_bytes
    )
    # A stored version always carries all four members, so none is ever absent.
    absent: list[str] = []

    design_row_index = build_design_row_index(
        domain=domain, constraints=constraints, components=components, plans=plans
    )
    all_removal_index = build_removal_index(
        domain=domain, constraints=constraints, components=components, plans=plans
    )
    all_feedback_index = build_feedback_index(
        domain=domain, constraints=constraints, components=components, plans=plans
    )

    if mode == MODE_REVIEW:
        removal_index = all_removal_index
        feedback_index = all_feedback_index
    else:
        removal_index = {}
        feedback_index = {}

    return LoadedRoadmap(
        slug=slug,
        mode=mode,
        directory_exists=directory_exists,
        domain=domain,
        constraints=constraints,
        components=components,
        plans=plans,
        absent=tuple(absent),
        unparseable=tuple(unparseable),
        design_row_index=design_row_index,
        removal_index=removal_index,
        feedback_index=feedback_index,
        all_removal_index=all_removal_index,
        all_feedback_index=all_feedback_index,
    )


# --------------------------------------------------------------------------
# The citation map — the reverse index from an id to the rows that name it
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Citation:
    """One row that names some other row's id, and the field it named it in.

    ``field`` is carried alongside ``label`` so two citers of the same id
    arriving through different fields (e.g. a component's ``entity_ids`` and
    a business rule's ``entity_ids``) stay distinguishable in the rendered
    list, rather than reading as duplicates. ``kind`` carries the citer's own
    row kind — the same ``KIND_*`` vocabulary :class:`DesignRowEntry.kind`
    uses for a citer that is itself a design row, plus ``KIND_FEEDBACK`` and
    ``KIND_REMOVAL`` for the two review-mode-only citer kinds that are not
    design rows at all. The traceability walk (step 4) filters on
    ``kind`` to pick out exactly the citers it wants at a reverse hop the
    format has no forward field for — an entity's governing business rules
    and workflows, and a plan's consuming assumptions — without a second
    traversal.
    """

    label: str
    field: str
    kind: str


def _cite(
    citations: "dict[str, list[Citation]]",
    citer_label: str,
    citer_kind: str,
    field: str,
    target_ids: "tuple[str, ...]",
) -> None:
    for target_id in target_ids:
        citations[target_id].append(
            Citation(label=citer_label, field=field, kind=citer_kind)
        )


_CITATION_FIELDS_BY_RELATION_KIND: Mapping[RelationKind, tuple[str, str]] = {
    RelationKind.BUSINESS_RULE_ENTITY: (KIND_BUSINESS_RULE, "entity_ids"),
    RelationKind.WORKFLOW_ENTITY: (KIND_WORKFLOW, "entity_ids"),
    RelationKind.DECISION_ANCHOR: (KIND_DECISION, "anchor"),
    RelationKind.CONSTRAINT_ANCHOR: (KIND_CONSTRAINT, "anchor_ids"),
    RelationKind.COMPONENT_ENTITY: (KIND_COMPONENT, "entity_ids"),
    RelationKind.COMPONENT_PATTERN: (KIND_COMPONENT, "pattern_ids"),
    RelationKind.COMPONENT_CONSTRAINT: (KIND_COMPONENT, "constraint_ids"),
    RelationKind.COMPONENT_STORE: (KIND_COMPONENT, "store_ids"),
    RelationKind.PLAN_COMPONENT: (KIND_PLAN, "component_ids"),
    RelationKind.ASSUMPTION_CONSUMING_PLAN: (
        KIND_ASSUMPTION,
        "consuming_plan_ids",
    ),
}

_CITATION_OWNER_COLLECTION_BY_RELATION_KIND: Mapping[RelationKind, str] = {
    RelationKind.BUSINESS_RULE_ENTITY: "business_rules",
    RelationKind.WORKFLOW_ENTITY: "workflows",
    RelationKind.DECISION_ANCHOR: "decisions",
    RelationKind.CONSTRAINT_ANCHOR: "constraints",
    RelationKind.COMPONENT_ENTITY: "components",
    RelationKind.COMPONENT_PATTERN: "components",
    RelationKind.COMPONENT_CONSTRAINT: "components",
    RelationKind.COMPONENT_STORE: "components",
    RelationKind.PLAN_COMPONENT: "plans",
    RelationKind.ASSUMPTION_CONSUMING_PLAN: "assumptions",
}


def _citation_owner_label(loaded: LoadedRoadmap, relation: RoadmapRelation) -> str:
    """Return one cited relation owner's label without collapsing duplicate ids."""
    artifact = getattr(loaded, relation.owner_artifact_key)
    collection = _CITATION_OWNER_COLLECTION_BY_RELATION_KIND[relation.kind]
    return display_label(getattr(artifact, collection)[relation.owner_row_index])


def build_citation_map(loaded: LoadedRoadmap) -> Mapping[str, tuple[Citation, ...]]:
    """The reverse index from any id to the rows that name it.

    Covers exactly eleven reference fields — the ones neither the
    traceability walk nor a removal's own tombstone label already claims:
    ``BusinessRuleRow.entity_ids``, ``WorkflowRow.entity_ids``,
    ``ConstraintRow.anchor_ids``, ``ComponentRow.entity_ids``,
    ``ComponentRow.pattern_ids``, ``ComponentRow.constraint_ids``,
    ``PlanRow.component_ids``, ``DecisionRow.anchor`` (walked on all four
    artifacts), ``AssumptionRow.consuming_plan_ids``, and — under
    :data:`MODE_REVIEW` only — ``FeedbackTarget.row_id`` and
    ``RemovalRecord.feedback_ids``. ``FieldRow.entity_id``,
    ``OrderingEntry.depends_on``, and ``OrderingEntry.assumption_targets``
    are deliberately excluded: the walk prints those directly. No ``mode``
    branch guards the review-only pair below because ``feedback_index`` and
    ``removal_index`` are already empty under :data:`MODE_CURRENT`.

    Citers accumulate in the same stage-then-source, then within-artifact
    row order :func:`build_design_row_index` uses, so a repeat query returns
    citers in the same order every time.
    """
    citations: "dict[str, list[Citation]]" = defaultdict(list)
    for relation in extract_declared_relations(
        domain=loaded.domain,
        constraints=loaded.constraints,
        components=loaded.components,
        plans=loaded.plans,
    ):
        citation_data = _CITATION_FIELDS_BY_RELATION_KIND.get(relation.kind)
        if citation_data is None:
            continue
        citer_kind, field = citation_data
        citations[relation.endpoint_id].append(
            Citation(
                label=_citation_owner_label(loaded, relation),
                field=field,
                kind=citer_kind,
            )
        )

    for rows in loaded.feedback_index.values():
        for row in rows:
            if row.target.kind is FeedbackTargetKind.ROW:
                _cite(
                    citations,
                    display_label(row),
                    KIND_FEEDBACK,
                    "row_id",
                    (row.target.row_id,),
                )
    for records in loaded.removal_index.values():
        for record in records:
            _cite(
                citations,
                display_label(record),
                KIND_REMOVAL,
                "feedback_ids",
                record.feedback_ids,
            )

    return {row_id: tuple(entries) for row_id, entries in citations.items()}


# --------------------------------------------------------------------------
# Resolving a citation-map query subject
# --------------------------------------------------------------------------

RESOLUTION_OUT_OF_SCOPE_FOR_MODE = "out-of-scope-for-mode"


def resolve_citation_subject(row_id: str, loaded: LoadedRoadmap) -> Resolution:
    """Resolve what ``row_id`` names, for the reverse-index view's own query.

    Tries, in order, the design-row index (:func:`resolve_id`), then —
    on a dangling result — the removal index, then the feedback index, then
    (only if none of those match) ``loaded.all_removal_index`` and
    ``loaded.all_feedback_index`` — the same two mode-invariant indices
    :func:`load_roadmap` always builds — to distinguish a genuinely
    undeclared id from a removal or feedback id the current ``loaded.mode``
    is hiding. A design row wins over a same-string feedback or removal id
    by construction: the design-row check runs first and returns
    immediately on anything but ``dangling``. Never raises: every outcome,
    including the two-way and three-way collisions at each stage, comes
    back as a :class:`Resolution`.
    """
    resolution = resolve_id(row_id, loaded.design_row_index)
    if resolution.status != RESOLUTION_DANGLING:
        return resolution

    removals = loaded.removal_index.get(row_id, ())
    if removals:
        if len(removals) > 1:
            return _ambiguous(
                row_id, tuple(display_label(record) for record in removals)
            )
        return Resolution(status=RESOLUTION_RESOLVED, text=display_label(removals[0]))

    feedback_rows = loaded.feedback_index.get(row_id, ())
    if feedback_rows:
        if len(feedback_rows) > 1:
            return _ambiguous(
                row_id, tuple(display_label(row) for row in feedback_rows)
            )
        return Resolution(
            status=RESOLUTION_RESOLVED, text=display_label(feedback_rows[0])
        )

    if row_id in loaded.all_removal_index or row_id in loaded.all_feedback_index:
        return Resolution(
            status=RESOLUTION_OUT_OF_SCOPE_FOR_MODE,
            text=f"⚠ out of scope for mode {loaded.mode!r}: {row_id}",
        )

    return resolution


# --------------------------------------------------------------------------
# The reverse-index render (``--view index``)
# --------------------------------------------------------------------------


def _mode_header(loaded: LoadedRoadmap) -> str:
    return f"roadmap: {loaded.slug} (mode: {loaded.mode})"


def _artifact_notice(loaded: LoadedRoadmap) -> Optional[str]:
    parts: "list[str]" = []
    if loaded.absent:
        parts.append(f"absent: {', '.join(loaded.absent)}")
    if loaded.unparseable:
        parts.append(
            "unparseable: " + ", ".join(item.filename for item in loaded.unparseable)
        )
    if not parts:
        return None
    return "artifact status: " + "; ".join(parts)


def _render_citers(citations: "tuple[Citation, ...]") -> str:
    if not citations:
        return indent("(nothing cites this)", "  ")
    return indent(
        "\n".join(f"- {citation.label} ({citation.field})" for citation in citations),
        "  ",
    )


def _render_subject_entry(
    row_id: str, loaded: LoadedRoadmap, citation_map: Mapping[str, tuple[Citation, ...]]
) -> str:
    resolution = resolve_citation_subject(row_id, loaded)
    lines = [f"{row_id}: {resolution.text}"]
    if resolution.matches:
        lines.append(indent("\n".join(resolution.matches), "  "))
    lines.append(_render_citers(citation_map.get(row_id, ())))
    return "\n".join(lines)


def render_reverse_index(loaded: LoadedRoadmap, row_id: Optional[str] = None) -> str:
    """Render ``--view index``: one queried id's citers, or the full map.

    With ``row_id`` given, renders that one subject's resolution and citer
    list. With ``row_id`` omitted, renders every declared id — every
    ``loaded.design_row_index`` key always, plus every
    ``loaded.feedback_index`` key not already covered by the first loop —
    each with its citer list, including a stated empty result for an id
    nothing cites. A feedback id that collides with a design row id (legal,
    per ``ROADMAP_FORMAT.md``'s separate-namespaces rule) renders once, from
    the design-row loop, matching :func:`resolve_citation_subject`'s
    documented design-row-wins precedence, rather than the same resolved
    text appearing twice. No ``mode`` branch guards the feedback-key loop:
    ``feedback_index`` is already empty under :data:`MODE_CURRENT`, so it
    only ever contributes keys under :data:`MODE_REVIEW`. Every render
    states the mode it ran under and, once, the artifacts ``loaded.absent``
    / ``loaded.unparseable`` name. Never raises, touches no disk, and gives
    a removal no heading or list of its own: a removal surfaces only as a
    citer entry under the feedback id its ``feedback_ids`` names.
    """
    citation_map = build_citation_map(loaded)
    lines = [_mode_header(loaded)]
    notice = _artifact_notice(loaded)
    if notice is not None:
        lines.append(notice)

    if row_id is not None:
        lines.append(_render_subject_entry(row_id, loaded, citation_map))
    else:
        for key in loaded.design_row_index.keys():
            lines.append(_render_subject_entry(key, loaded, citation_map))
        for key in loaded.feedback_index.keys():
            if key in loaded.design_row_index:
                continue
            lines.append(_render_subject_entry(key, loaded, citation_map))

    return "\n".join(lines)


# --------------------------------------------------------------------------
# The traceability walk (``--view walk``)
# --------------------------------------------------------------------------


def _resolve_unique(
    ref_id: str, loaded: LoadedRoadmap, *, kind: str
) -> Optional[DesignRowEntry]:
    """The walk's leaf/continue rule: ``ref_id`` continues the walk only when
    it names exactly one design row of the expected ``kind``: a dangling,
    ambiguous, or wrong-kind id (a ``component_ids``/entity-reference id that
    resolves uniquely to some other row kind — reachable on a directly edited,
    ungated roadmap) is always a leaf, resolved instead through
    :func:`_leaf_reference_text`'s marker text."""
    entries = loaded.design_row_index.get(ref_id, ())
    if len(entries) == 1 and entries[0].kind == kind:
        return entries[0]
    return None


def _leaf_reference_text(ref_id: str, loaded: LoadedRoadmap, *, kind: str) -> str:
    """The text for a reference expected to name a design row of ``kind``
    that :func:`_resolve_unique` declined to continue the walk through: the
    ordinary :func:`resolve_id` text for a dangling or ambiguous id, or a
    distinct wrong-kind marker when the id resolves uniquely to some other
    design-row kind — never silently presenting that other row's own label
    as if it were the expected kind."""
    return resolve_id_of_kind(ref_id, loaded, kind=kind).text


def _render_ref_id_list(
    title: str, ref_ids: "tuple[str, ...]", loaded: LoadedRoadmap
) -> str:
    """A list of leaf-resolved ids under ``title`` — every reference this
    step owns that never continues the walk (``depends_on``,
    ``assumption_targets``, a component's ``pattern_ids`` /
    ``constraint_ids``): each id is resolved once through :func:`resolve_id`
    and printed, dangling and ambiguous ids included, with no further
    traversal."""
    header = f"{title}:"
    if not ref_ids:
        return "\n".join([header, indent("(none)", "  ")])
    body = "\n".join(
        f"- {resolve_id(ref_id, loaded.design_row_index).text}" for ref_id in ref_ids
    )
    return "\n".join([header, indent(body, "  ")])


def _reference_field_text(field: object, loaded: LoadedRoadmap) -> str:
    """The resolved text for one ``REFERENCE``-typed field's target: a
    distinct missing-``entity_id`` marker when the field carries none — the
    ungated shape a gate normally rejects, reachable here since ``--view``
    runs no gates — rather than :func:`resolve_id`\\ (``None``, ...)'s
    ``⚠ undefined: None``, indistinguishable from a real dangling id.
    Otherwise resolved through :func:`resolve_id_of_kind`, which also
    supplies the distinct wrong-kind marker for an id that resolves
    uniquely to some other design-row kind."""
    if field.entity_id is None:
        return f"⚠ missing entity_id: {field.name}"
    return resolve_id_of_kind(field.entity_id, loaded, kind=KIND_ENTITY).text


def _render_entity(
    entity_id: str,
    loaded: LoadedRoadmap,
    citation_map: Mapping[str, tuple[Citation, ...]],
) -> str:
    """One entity reached through a component's ``entity_ids``: its label,
    the business rules and workflows that govern it (the one reverse hop
    this step reuses step 3's citation map for), and its own reference-typed
    fields — each field's target printed as a label only, never expanded, so
    an entity-to-entity reference cycle cannot turn the walk unbounded."""
    entry = _resolve_unique(entity_id, loaded, kind=KIND_ENTITY)
    if entry is None:
        return f"- {_leaf_reference_text(entity_id, loaded, kind=KIND_ENTITY)}"

    entity = entry.row
    label = display_label(entity, kind=entry.kind)

    governs = [
        citation.label
        for citation in citation_map.get(entity_id, ())
        if citation.kind in (KIND_BUSINESS_RULE, KIND_WORKFLOW)
    ]
    governs_body = (
        "\n".join(f"- {statement}" for statement in governs) if governs else "(none)"
    )

    reference_fields = [
        field for field in entity.fields if field.type is FieldType.REFERENCE
    ]
    fields_body = (
        "\n".join(
            f"- {field.name}: {_reference_field_text(field, loaded)}"
            for field in reference_fields
        )
        if reference_fields
        else "(none)"
    )

    body = "\n".join(
        [
            "governs:",
            indent(governs_body, "  "),
            "fields:",
            indent(fields_body, "  "),
        ]
    )
    return "\n".join([f"- {label}", indent(body, "  ")])


def _render_labeled_section(
    title: str,
    ids: "tuple[str, ...]",
    loaded: LoadedRoadmap,
    citation_map: Mapping[str, tuple[Citation, ...]],
    render_item,
) -> str:
    """``title:`` header over one rendered item per id, or an explicit
    ``(none)`` — the shape both the entities section (``render_item=``
    :func:`_render_entity`) and the components section
    (``render_item=`` :func:`_render_component`) share."""
    if not ids:
        return "\n".join([f"{title}:", indent("(none)", "  ")])
    body = "\n".join(render_item(item_id, loaded, citation_map) for item_id in ids)
    return "\n".join([f"{title}:", indent(body, "  ")])


def _render_component(
    component_id: str,
    loaded: LoadedRoadmap,
    citation_map: Mapping[str, tuple[Citation, ...]],
) -> str:
    """One component reached through a plan's ``component_ids``: its label
    and its three sub-lists, each in the row's own field order — entities
    (which keep descending), then patterns and constraints (both always
    leaves)."""
    entry = _resolve_unique(component_id, loaded, kind=KIND_COMPONENT)
    if entry is None:
        return f"- {_leaf_reference_text(component_id, loaded, kind=KIND_COMPONENT)}"

    component = entry.row
    label = display_label(component, kind=entry.kind)
    body = "\n".join(
        [
            _render_labeled_section(
                "entities", component.entity_ids, loaded, citation_map, _render_entity
            ),
            _render_ref_id_list("patterns", component.pattern_ids, loaded),
            _render_ref_id_list("constraints", component.constraint_ids, loaded),
        ]
    )
    return "\n".join([f"- {label}", indent(body, "  ")])


def _render_consuming_assumptions(
    plan_id: str, citation_map: Mapping[str, tuple[Citation, ...]]
) -> str:
    """The assumptions naming this plan in their own ``consuming_plan_ids`` —
    reached the same way :func:`_render_entity` reaches an entity's
    governing business rules and workflows: a reverse query into the
    citation map, filtered to its ``kind``, rather than a second reverse-
    lookup mechanism."""
    statements = [
        citation.label
        for citation in citation_map.get(plan_id, ())
        if citation.kind == KIND_ASSUMPTION
    ]
    header = "assumptions:"
    if not statements:
        return "\n".join([header, indent("(none)", "  ")])
    body = "\n".join(f"- {statement}" for statement in statements)
    return "\n".join([header, indent(body, "  ")])


def _render_draft_seed(
    plan: PlanRow,
    loaded: LoadedRoadmap,
    plans_dir: Path,
    classifications: Mapping[str, DraftSeedClassification],
) -> str:
    """Render a classified draft seed, reading current provenance once.

    ``roadmap_components`` prints literal ids, never through
    :func:`resolve_id`; :func:`validate_draft_seed_content` and
    :func:`classify_draft_seeds` own validation against the plan row.
    """
    classification = classifications.get(plan.id)
    if classification is None:
        return f"⚠ draft seed classification unavailable: {plan.draft_seed_path}"
    if classification.state != DRAFT_SEED_STATE_CURRENT:
        lines = [f"⚠ draft seed {classification.state}: {plan.draft_seed_path}"]
        if classification.detail:
            lines.append(indent(classification.detail, "  "))
        return "\n".join(lines)

    try:
        source = resolve_draft_seed_path(plans_dir, loaded.slug, plan.draft_seed_path)
    except RoadmapArtifactError as exc:
        return f"⚠ current draft seed path unavailable: {exc}"
    try:
        provenance = parse_draft_seed_provenance(source.read_text(encoding="utf-8"))
    except (RoadmapArtifactError, UnicodeDecodeError, OSError):
        return f"⚠ current draft seed unreadable: {plan.draft_seed_path}"

    if not provenance.roadmap_components:
        components_body = "(none)"
    else:
        components_body = "\n".join(f"- {cid}" for cid in provenance.roadmap_components)
    body = "\n".join(["roadmap_components:", indent(components_body, "  ")])
    return "\n".join([f"draft seed: {plan.draft_seed_path}", indent(body, "  ")])


def _render_plan_intent(plan: PlanRow) -> str:
    """Render a plan's authored outcome, annotating legacy rows clearly."""
    intent = plan.intent.strip()
    body = intent if intent else "⚠ intent not recorded"
    return "\n".join(["intent:", indent(body, "  ")])


def _render_delivery_shape(plan: PlanRow) -> str:
    """Expose the mapping disposition in review language without duplicating it.

    ``PlanDisposition.CROSS_CUTTING`` is already the schema's authoritative
    statement that the work need not be owned by a component slice. All other
    dispositions retain component-owned delivery, even when a merge or split
    spans more than one component.
    """
    if plan.disposition is PlanDisposition.CROSS_CUTTING:
        body = "cross-cutting (component ownership is not required)"
    else:
        body = "component-owned"
    return f"delivery shape: {body}"


def _render_plan_non_goals(plan: PlanRow) -> str:
    """Render authored boundaries, annotating legacy rows clearly."""
    if not plan.non_goals:
        body = "⚠ non-goals not recorded"
    else:
        body = "\n".join(f"- {non_goal}" for non_goal in plan.non_goals)
    return "\n".join(["non-goals:", indent(body, "  ")])


def _render_plan_body(
    plan: PlanRow,
    ordering_entry: Optional[OrderingEntry],
    loaded: LoadedRoadmap,
    citation_map: Mapping[str, tuple[Citation, ...]],
    plans_dir: Path,
    classifications: Mapping[str, DraftSeedClassification],
) -> str:
    """One plan's review contract, then its dependency and component chain.

    Intent, delivery shape, and non-goals lead so a reviewer can decide
    whether the row belongs before tracing the supporting relationships.
    """
    depends_on = ordering_entry.depends_on if ordering_entry is not None else ()
    assumption_targets = (
        ordering_entry.assumption_targets if ordering_entry is not None else ()
    )
    sections = [
        _render_plan_intent(plan),
        _render_delivery_shape(plan),
        _render_plan_non_goals(plan),
        _render_ref_id_list("depends_on", depends_on, loaded),
        _render_ref_id_list("assumption_targets", assumption_targets, loaded),
        _render_consuming_assumptions(plan.id, citation_map),
        _render_labeled_section(
            "components", plan.component_ids, loaded, citation_map, _render_component
        ),
        _render_draft_seed(plan, loaded, plans_dir, classifications),
    ]
    return indent("\n".join(sections), "  ")


def render_traceability_walk(
    loaded: LoadedRoadmap,
    plans_dir: Path,
    classifications: Mapping[str, DraftSeedClassification],
    *,
    unavailable_reason: Optional[str] = None,
) -> str:
    """Render ``--view walk``: every plan, in ``ordering`` sequence, out to
    its components, their entities/patterns/constraints, the business rules
    and workflows that govern each entity, and that plan's draft seed and
    ``roadmap_components`` provenance.

    Plans render in :attr:`PlansArtifact.ordering` order; a plan row absent
    from ``ordering`` renders after the sequence, marked distinctly; an
    ``ordering`` entry naming no plan row renders a diagnostic at its
    position — a dangling/ambiguous id renders its resolution marker, while
    an id that resolves to a non-plan design row renders an explicit "does
    not name a plan" message; an entry repeating a ``plan_id`` already
    rendered renders a duplicate marker in place, never a second full
    render — a repeat of a non-plan-resolved id gets its own "(repeated)"
    variant of that same explicit message rather than a bare id. Two
    ``PlanRow`` entries sharing the same ``id`` (nothing enforces
    plan-id uniqueness the way :func:`build_design_row_index`'s membership
    check does) render the same ambiguous marker a colliding design-row id
    gets, listing every match, rather than one silently replacing the other
    in ``ordering`` lookups — including when neither collides with an
    ``ordering`` entry at all, in which case the "not in ordering" tail
    renders that one ambiguous marker instead of one silent duplicate
    subtree per row. Deliberately mode-invariant: reads ``loaded.domain`` /
    ``constraints`` / ``components`` / ``plans`` and the citation map built
    from them, never ``loaded.feedback_index``, ``loaded.removal_index``, or
    ``loaded.mode`` beyond the shared header line, so the walk's body is
    identical under both modes for the same artifacts. Never raises: every
    dangling, ambiguous, and seed-classification marker is a rendering
    annotation. The caller supplies the classifier's complete map, while a
    hand-built map missing a plan id still renders a distinct marker.
    ``unavailable_reason``, when supplied, notes why ``classifications`` is
    empty (e.g. an unreadable sidecar) instead of leaving the reader to infer
    "every plan's seed state happens to be unclassifiable" from silence —
    mirroring ``render_seed_state_view``'s own advisory.
    """
    citation_map = build_citation_map(loaded)
    lines = [_mode_header(loaded)]
    notice = _artifact_notice(loaded)
    if notice is not None:
        lines.append(notice)
    if unavailable_reason is not None:
        lines.append(f"seed states unavailable: {unavailable_reason}")

    if loaded.plans is not None:
        plan_groups: "dict[str, list[PlanRow]]" = defaultdict(list)
        for plan in loaded.plans.plans:
            plan_groups[plan.id].append(plan)
        rendered: "set[str]" = set()
        for ordering_entry in loaded.plans.ordering:
            plan_id = ordering_entry.plan_id
            matches = plan_groups.get(plan_id, ())
            if plan_id in rendered:
                # A repeated malformed id still gets its own diagnostic
                # rather than falling through to the generic "repeated"
                # label with nothing said about what is wrong with it —
                # mirrors roadmap_html.py's ``_plans_block``.
                if not matches:
                    resolution = resolve_id(plan_id, loaded.design_row_index)
                    if resolution.status == RESOLUTION_RESOLVED:
                        lines.append(
                            "⚠ ordering entry does not name a plan "
                            f"(repeated): {resolution.text}"
                        )
                    else:
                        lines.append(f"repeated, {resolution.text}")
                    continue
                label = display_label(matches[0]) if len(matches) == 1 else plan_id
                lines.append(f"⚠ duplicate ordering entry: {label}")
                continue
            if not matches:
                resolution = resolve_id(plan_id, loaded.design_row_index)
                if resolution.status == RESOLUTION_RESOLVED:
                    lines.append(
                        f"⚠ ordering entry does not name a plan: {resolution.text}"
                    )
                else:
                    lines.append(resolution.text)
                rendered.add(plan_id)
                continue
            if len(matches) > 1:
                resolution = _ambiguous(
                    plan_id, tuple(display_label(plan) for plan in matches)
                )
                lines.append(resolution.text)
                lines.append(indent("\n".join(resolution.matches), "  "))
                rendered.add(plan_id)
                continue
            plan = matches[0]
            lines.append(display_label(plan))
            lines.append(
                _render_plan_body(
                    plan, ordering_entry, loaded, citation_map, plans_dir, classifications
                )
            )
            rendered.add(plan_id)

        for plan_id, matches in plan_groups.items():
            if plan_id in rendered:
                continue
            if len(matches) > 1:
                resolution = _ambiguous(
                    plan_id, tuple(display_label(plan) for plan in matches)
                )
                lines.append(f"⚠ not in ordering, ambiguous: {plan_id}")
                lines.append(indent("\n".join(resolution.matches), "  "))
                continue
            plan = matches[0]
            lines.append(f"⚠ not in ordering: {display_label(plan)}")
            lines.append(
                _render_plan_body(
                    plan, None, loaded, citation_map, plans_dir, classifications
                )
            )

    return "\n".join(lines)


# --------------------------------------------------------------------------
# The decision ledger (``--view ledger``)
# --------------------------------------------------------------------------


def _all_decisions(loaded: LoadedRoadmap) -> "tuple[DecisionRow, ...]":
    """Every ``DecisionRow`` across whichever artifacts are parsed, in stage
    order, each artifact's own decisions in source order."""
    decisions: "list[DecisionRow]" = []
    for artifact in (loaded.domain, loaded.constraints, loaded.components, loaded.plans):
        if artifact is not None:
            decisions.extend(artifact.decisions)
    return tuple(decisions)


def _render_resolution(label: str, resolution: Resolution) -> str:
    """``label: text``, plus every ambiguous match indented beneath it —
    the same shape :func:`_render_subject_entry` uses for a queried id."""
    lines = [f"{label}: {resolution.text}"]
    if resolution.matches:
        lines.append(indent("\n".join(resolution.matches), "  "))
    return "\n".join(lines)


def _render_decision(decision: DecisionRow, loaded: LoadedRoadmap) -> str:
    """One decision's own fields — never through :func:`display_label`, which
    would flatten it to ``chosen_option`` alone — plus its ``anchor`` resolved
    through :func:`resolve_id`, never :func:`resolve_feedback_target`: a
    decision anchor takes no removals fallback, regardless of ``status``."""
    anchor_resolution = resolve_id(decision.anchor, loaded.design_row_index)
    if decision.rejected_alternatives:
        rejected_body = "\n".join(
            f"- {alternative.option}: {alternative.reason}"
            for alternative in decision.rejected_alternatives
        )
    else:
        rejected_body = "(none)"
    body = "\n".join(
        [
            f"source: {decision.source if decision.source is not None else '(none)'}",
            _render_resolution("anchor", anchor_resolution),
            f"rationale: {decision.rationale if decision.rationale is not None else '(none)'}",
            "rejected_alternatives:",
            indent(rejected_body, "  "),
        ]
    )
    return "\n".join([f"- {decision.chosen_option}", indent(body, "  ")])


def _render_pending_feedback(row: FeedbackRow, loaded: LoadedRoadmap) -> str:
    """One unclosed feedback row's ``request`` and its ``target`` resolved
    through :func:`resolve_feedback_target` — the one caller in this module
    that renders a removal, exactly beside the live feedback row whose
    target resolved through it."""
    target_resolution = resolve_feedback_target(
        row.target, loaded.design_row_index, loaded.removal_index
    )
    body = _render_resolution("target", target_resolution)
    return "\n".join([f"- {row.request}", indent(body, "  ")])


def render_decision_ledger(loaded: LoadedRoadmap) -> str:
    """Render ``--view ledger``: every decision, grouped ``settled`` /
    ``pending``, each with its ``anchor`` resolved.

    Under :data:`MODE_REVIEW`, the pending group additionally carries every
    row ``loaded.feedback_index`` holds, each showing its ``request`` beside
    its ``target`` resolved through :func:`resolve_feedback_target`. No
    ``if loaded.mode == ...`` branch is needed for that inclusion:
    ``feedback_index`` is already empty under :data:`MODE_CURRENT`, per
    :class:`LoadedRoadmap`'s own contract, so reading it as-is is the mode
    filter. Pending decisions render before pending feedback rows; within
    each population, stage-then-source order is preserved. A removal renders
    nowhere in this view except inside the pending feedback entry whose
    target resolved through it.

    Every render states the mode it ran under and, once, before the ledger's
    own output, the artifacts ``loaded.absent`` / ``loaded.unparseable``
    name. Never raises, and reads nothing off disk beyond ``loaded`` itself.
    """
    lines = [_mode_header(loaded)]
    notice = _artifact_notice(loaded)
    if notice is not None:
        lines.append(notice)

    decisions = _all_decisions(loaded)
    settled = [d for d in decisions if d.status is DecisionStatus.SETTLED]
    pending = [d for d in decisions if d.status is DecisionStatus.PENDING]

    settled_body = (
        "\n".join(_render_decision(decision, loaded) for decision in settled)
        if settled
        else "(none)"
    )
    lines.append("settled:")
    lines.append(indent(settled_body, "  "))

    pending_entries = [_render_decision(decision, loaded) for decision in pending]
    for rows in loaded.feedback_index.values():
        for row in rows:
            pending_entries.append(_render_pending_feedback(row, loaded))
    pending_body = "\n".join(pending_entries) if pending_entries else "(none)"
    lines.append("pending:")
    lines.append(indent(pending_body, "  "))

    return "\n".join(lines)


# --------------------------------------------------------------------------
# The review summary (``--view summary``)
# --------------------------------------------------------------------------


_SUMMARY_ATTENTION_LIMIT = 5


def _summary_text(value: str, *, limit: int = 72) -> str:
    """One compact, single-line description for the bounded attention list."""
    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _summary_command(loaded: LoadedRoadmap, suffix: str) -> str:
    """The common, copy-pasteable start of every summary drill-down."""
    return f"plan-tool roadmap {loaded.slug} {suffix}"


def _summary_view_command(
    loaded: LoadedRoadmap, view: str, *, row_id: Optional[str] = None
) -> str:
    """A mode-preserving command for one of the detailed read-only views."""
    suffix = f"--view {view}"
    if row_id is not None:
        suffix += f" --id {row_id}"
    if loaded.mode == MODE_REVIEW:
        suffix += " --mode review"
    return _summary_command(loaded, suffix)


def _summary_seed_line(seed_lifecycle: SeedLifecycleSummary) -> str:
    if seed_lifecycle.tracking == SEED_TRACKING_UNAVAILABLE:
        return "unavailable: " + (seed_lifecycle.reason or "unknown reason")
    return (
        f"{len(seed_lifecycle.current_plan_ids)} current · "
        f"{len(seed_lifecycle.invalidated_plan_ids)} invalidated"
    )


def _summary_feedback_counts(loaded: LoadedRoadmap) -> dict[FeedbackState, int]:
    """All review-visible feedback rows by lifecycle state, zeros included."""
    counts = {state: 0 for state in FeedbackState}
    for rows in loaded.feedback_index.values():
        for row in rows:
            counts[row.state] += 1
    return counts


def _summary_attention(
    loaded: LoadedRoadmap, seed_lifecycle: SeedLifecycleSummary
) -> tuple[str, ...]:
    """The bounded, priority-ordered set of review actions for the summary.

    Artifact readability comes first because every other signal is derived
    from whatever did parse.  Indexed-reference problems come next, followed
    by seed lifecycle, decisions, and review-channel work.  The detailed
    views remain the source of complete context; this list is deliberately a
    small starting queue rather than another all-rows renderer.
    """
    items: list[str] = []
    for artifact in loaded.unparseable:
        items.append(
            f"⚠ artifact {artifact.filename} is unparseable in the accepted version — "
            f"change it only through {_summary_command(loaded, '--propose-candidate')}"
        )
    for filename in loaded.absent:
        items.append(
            f"⚠ artifact {filename} is absent from the accepted version — "
            f"restore it through {_summary_command(loaded, '--propose-candidate')}"
        )

    if loaded.plans is not None:
        for plan in loaded.plans.plans:
            missing: list[str] = []
            if not plan.intent.strip():
                missing.append("intent")
            if not plan.non_goals:
                missing.append("non-goals")
            if missing:
                items.append(
                    f"⚠ plan {plan.id} has no {', '.join(missing)} — submit "
                    f"{_summary_command(loaded, '--submit-feedback ITEM_ID --feedback-target plans:artifact --feedback-request TEXT')}"
                    f", then {_summary_command(loaded, '--propose-candidate')}"
                )

    for row_id in build_citation_map(loaded):
        resolution = resolve_citation_subject(row_id, loaded)
        if resolution.status == RESOLUTION_DANGLING:
            items.append(
                f"⚠ indexed reference {row_id} is undefined — inspect "
                f"{_summary_view_command(loaded, 'index', row_id=row_id)}"
            )
        elif resolution.status == RESOLUTION_AMBIGUOUS:
            items.append(
                f"⚠ indexed reference {row_id} is ambiguous — inspect "
                f"{_summary_view_command(loaded, 'index', row_id=row_id)}"
            )

    if (
        seed_lifecycle.tracking == SEED_TRACKING_UNAVAILABLE
        and seed_lifecycle.reason != "04-roadmap.md is not readable"
    ):
        items.append(
            "⚠ seed lifecycle state is unavailable — inspect seed-state.json beside "
            "04-roadmap.md"
        )
    if loaded.plans is not None:
        for plan in loaded.plans.plans:
            classification = seed_lifecycle.classifications.get(plan.id)
            if (
                classification is None
                or classification.state == DRAFT_SEED_STATE_CURRENT
            ):
                continue
            remedy = _draft_seed_remedy(loaded, classification)
            if classification.state in {
                DRAFT_SEED_STATE_MISSING,
                DRAFT_SEED_STATE_STALE,
                DRAFT_SEED_STATE_MALFORMED,
                DRAFT_SEED_STATE_PATH_ESCAPING,
            }:
                items.append(
                    f"⚠ seed {plan.id} is {classification.state} — {remedy}"
                )
            elif classification.state == DRAFT_SEED_STATE_DIGEST_MISMATCHED:
                items.append(
                    f"⚠ seed {plan.id} is digest-mismatched — {remedy}"
                )
            elif classification.state == DRAFT_SEED_STATE_DUPLICATE:
                detail = (
                    f": {_summary_text(classification.detail)}"
                    if classification.detail
                    else ""
                )
                items.append(
                    f"⚠ seed {plan.id} is duplicate{detail} — {remedy}"
                )

    for decision in _all_decisions(loaded):
        if decision.status is DecisionStatus.PENDING:
            items.append(
                f"⚠ pending decision {decision.id}: {_summary_text(decision.chosen_option)} "
                f"— review {_summary_view_command(loaded, 'ledger')}"
            )

    if loaded.mode == MODE_REVIEW:
        for rows in loaded.feedback_index.values():
            for row in rows:
                if row.state in (FeedbackState.OPEN, FeedbackState.AWAITING_REVIEW):
                    items.append(
                        f"⚠ {row.state.value} feedback {row.id}: "
                        f"{_summary_text(row.request)} — review "
                        f"{_summary_view_command(loaded, 'ledger')}"
                    )
    return tuple(items)


def render_roadmap_summary(
    loaded: LoadedRoadmap, seed_lifecycle: SeedLifecycleSummary
) -> str:
    """Render ``--view summary``: a compact, actionable roadmap review queue.

    Counts describe only parsed artifacts.  "Indexed references" is
    intentionally narrower than every relationship the walk can display: it
    reports the citation map used by ``--view index`` and names that scope in
    the heading rather than claiming universal validation.  Under current
    mode feedback remains hidden exactly as it is in the other views; review
    mode counts it and adds open / awaiting-review rows to the attention
    queue.  The raw output is deterministic and bounded: no more than five
    attention items render, with the full ledger, index, and walk offered as
    drill-downs below.
    """
    lines = [_mode_header(loaded)]
    notice = _artifact_notice(loaded)
    if notice is not None:
        lines.append(notice)

    readable = 4 - len(loaded.absent) - len(loaded.unparseable)
    lines.extend(["artifacts:", indent(f"{readable}/4 readable", "  ")])

    entity_count = len(loaded.domain.entities) if loaded.domain is not None else 0
    component_count = (
        len(loaded.components.components) if loaded.components is not None else 0
    )
    plan_count = len(loaded.plans.plans) if loaded.plans is not None else 0
    lines.extend(
        [
            "design:",
            indent(
                f"{entity_count} entities · {component_count} components · "
                f"{plan_count} plans",
                "  ",
            ),
        ]
    )

    if loaded.plans is not None:
        intent_count = sum(bool(plan.intent.strip()) for plan in loaded.plans.plans)
        non_goal_count = sum(bool(plan.non_goals) for plan in loaded.plans.plans)
        lines.extend(
            [
                "plan review context:",
                indent(
                    f"{intent_count}/{plan_count} intent recorded · "
                    f"{non_goal_count}/{plan_count} non-goal lists recorded",
                    "  ",
                ),
            ]
        )

    decisions = _all_decisions(loaded)
    settled_count = sum(
        decision.status is DecisionStatus.SETTLED for decision in decisions
    )
    pending_count = len(decisions) - settled_count
    lines.extend(
        [
            "decisions:",
            indent(f"{settled_count} settled · {pending_count} pending", "  "),
        ]
    )

    lines.append("feedback:")
    if loaded.mode == MODE_CURRENT:
        lines.append(indent("hidden in current mode; rerun with --mode review", "  "))
    else:
        feedback_counts = _summary_feedback_counts(loaded)
        lines.append(
            indent(
                f"{feedback_counts[FeedbackState.OPEN]} open · "
                f"{feedback_counts[FeedbackState.AWAITING_REVIEW]} awaiting review · "
                f"{feedback_counts[FeedbackState.DEFERRED]} deferred",
                "  ",
            )
        )

    lines.extend(["seeds:", indent(_summary_seed_line(seed_lifecycle), "  ")])

    citation_map = build_citation_map(loaded)
    dangling_count = 0
    ambiguous_count = 0
    other_unresolved_count = 0
    for row_id in citation_map:
        status = resolve_citation_subject(row_id, loaded).status
        if status == RESOLUTION_DANGLING:
            dangling_count += 1
        elif status == RESOLUTION_AMBIGUOUS:
            ambiguous_count += 1
        elif status != RESOLUTION_RESOLVED:
            other_unresolved_count += 1
    resolved_count = len(citation_map) - dangling_count - ambiguous_count - other_unresolved_count
    reference_bits = [
        f"{resolved_count} resolved",
        f"{dangling_count} dangling",
        f"{ambiguous_count} ambiguous",
    ]
    if other_unresolved_count:
        reference_bits.append(f"{other_unresolved_count} unavailable")
    lines.extend(["indexed references:", indent(" · ".join(reference_bits), "  ")])

    attention = _summary_attention(loaded, seed_lifecycle)
    lines.append("needs attention:")
    if not attention:
        lines.append(indent("(none)", "  "))
    else:
        for item in attention[:_SUMMARY_ATTENTION_LIMIT]:
            lines.append(indent(item, "  "))
        remaining = len(attention) - _SUMMARY_ATTENTION_LIMIT
        if remaining:
            lines.append(indent(f"… {remaining} additional item(s)", "  "))

    lines.extend(
        [
            "drill down:",
            indent(
                "\n".join(
                    [
                        f"- decisions: {_summary_view_command(loaded, 'ledger')}",
                        f"- references: {_summary_view_command(loaded, 'index', row_id='ROW_ID')}",
                        f"- full traceability: {_summary_view_command(loaded, 'walk')}",
                    ]
                ),
                "  ",
            ),
        ]
    )
    return "\n".join(lines)
