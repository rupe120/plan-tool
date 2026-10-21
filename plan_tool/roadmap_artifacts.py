"""Roadmap artifact contract: paths, closed vocabularies, rows, parse/render.

One module answers three questions about a roadmap's staged artifacts — where
``01-domain.md``, ``02-constraints.md``, ``03-components.md``, and
``04-roadmap.md`` live, what their frontmatter rows hold, and which words those
rows may use. Every consumer (the roadmap gates, the orchestrator above them,
the stage prompts' pinning tests) reads its artifact tokens from here rather
than re-declaring them, so the copies cannot drift. The three hard
stage-feedback ceilings are mirrored in the stdlib-only project-config leaf;
a regression test keeps its enforced values aligned with the reviewer-facing
comment here without adding a first-party import to either leaf.

Deliberately a **stdlib-plus-YAML leaf**: it imports no first-party module, not
even ``parser._split_frontmatter``, so the gate module directly above it can
stay a leaf too. The plan-side fence rules are therefore mirrored here rather
than shared, and the resolved plans directory arrives as an argument instead of
being re-derived — ``--plans-dir`` and skill-scoped repos both move it.

**Shape is checked here; relations are not.** Parsing raises on a malformed
artifact (missing fence, bad YAML, a missing row key, a wrong-typed value, an
unknown vocabulary member) and deliberately accepts a workflow naming an
undefined entity, two rows sharing an id, an absent quality attribute, and an
unanchored constraint. Those are relation checks: the gates own them, and they
return violations rather than raising.

All four artifacts may also carry the two **review** collections — ``feedback``
(a reviewer's redirect, its target, its lifecycle state, the model's optional
proposed response) and ``removals`` (a dropped design row, why, and which
feedback asked for it). They are omitted from the rendered frontmatter when
empty, so an artifact nobody has reviewed renders exactly the design keys, and
they follow the same shape/relation split: a feedback target naming an
undefined row, a removal citing no feedback, and a removal naming a row the
artifact still declares all parse.

The frontmatter schema is **open**: a key the contract does not name is ignored
rather than rejected, and the renderer emits only the contract's keys. The
optional ``feedback_reopen`` mapping is the narrow exception: its nested shape
is closed so it cannot retain response or evidence metadata. A closed schema
would otherwise turn a harmless extra field into a spent stage retry, and the
artifact a stage writes is rendered fresh rather than round-tripped out of a
directly edited file.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, fields, replace
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Final, Iterator, Mapping, Optional, TypeVar

import yaml

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------

# A roadmap's artifacts sit in their own subdirectory of the plans directory.
# Nesting keeps them outside ``locator.list_plans``' top-level ``*.md`` glob,
# so plan discovery cannot resolve one.
ROADMAP_DIRNAME = "roadmaps"

DOMAIN_FILENAME = "01-domain.md"
CONSTRAINTS_FILENAME = "02-constraints.md"
COMPONENTS_FILENAME = "03-components.md"
PLANS_FILENAME = "04-roadmap.md"
DRAFT_SEEDS_DIRNAME = "plan-seed-drafts"
LEGACY_DRAFT_SEEDS_DIRNAME = "seeds"

# Mirrors ``create.SLUG_RE``; this leaf does not import ``create.py``.
PLAN_ID_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")

HARD_MAX_ACTIVE_FEEDBACK_ITEMS = 32
HARD_MAX_RESPONSE_BYTES = 32 * 1024
HARD_MAX_PROSE_AMENDMENT_BYTES = 4 * 1024

# Shared persisted identifier grammar for feedback records and receipt selection.
RECEIPT_SAFE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", re.ASCII)
_FEEDBACK_REOPEN_NONCE_RE = re.compile(r"[A-Za-z0-9_-]{43}", re.ASCII)
_FEEDBACK_REOPEN_RECORDED_AT_RE = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", re.ASCII
)
_FEEDBACK_REOPEN_REASON = "operator-confirmed-evidence-unavailable"


def _validate_slug(slug: str) -> None:
    """Reject a slug that could escape the roadmap directory as a path segment.

    Mirrors ``worktree._validate_slug``; this is the only place a
    caller-supplied slug becomes a path component.
    """
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError(f"roadmap slug must be a non-empty string, got {slug!r}")
    if "/" in slug or "\\" in slug:
        raise ValueError(f"roadmap slug must not contain a path separator: {slug!r}")
    if ".." in Path(slug).parts:
        raise ValueError(f"roadmap slug must not contain a '..' component: {slug!r}")
    if Path(slug).parts != (slug,):
        raise ValueError(f"roadmap slug must be a single path component: {slug!r}")


def roadmap_dir(plans_dir: Path, slug: str) -> Path:
    """Return ``<plans_dir>/roadmaps/<slug>``.

    Pure: the plans directory is whatever the caller resolved, and nothing
    here touches the filesystem.
    """
    _validate_slug(slug)
    return Path(plans_dir) / ROADMAP_DIRNAME / slug


def roadmap_relative_stage_path(plans_dir: Path, slug: str, stage_path: Path) -> str:
    """Return one configured stage path relative to its resolved roadmap root."""
    root = roadmap_dir(Path(plans_dir), slug).resolve()
    candidate = Path(stage_path).resolve()
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise RoadmapArtifactError(
            f"configured stage path must sit under roadmap root: {stage_path}"
        ) from exc

    relative_path = relative.as_posix()
    if relative_path in {"", "."}:
        raise RoadmapArtifactError(
            f"configured stage path must name a file below roadmap root: {stage_path}"
        )
    return relative_path


def domain_path(plans_dir: Path, slug: str) -> Path:
    """Return the roadmap's ``01-domain.md`` path."""
    return roadmap_dir(plans_dir, slug) / DOMAIN_FILENAME


def constraints_path(plans_dir: Path, slug: str) -> Path:
    """Return the roadmap's ``02-constraints.md`` path."""
    return roadmap_dir(plans_dir, slug) / CONSTRAINTS_FILENAME


def components_path(plans_dir: Path, slug: str) -> Path:
    """Return the roadmap's ``03-components.md`` path."""
    return roadmap_dir(plans_dir, slug) / COMPONENTS_FILENAME


def plans_path(plans_dir: Path, slug: str) -> Path:
    """Return the roadmap's ``04-roadmap.md`` path."""
    return roadmap_dir(plans_dir, slug) / PLANS_FILENAME


def draft_seeds_dir(plans_dir: Path, slug: str) -> Path:
    """Return the default draft-seed directory under a roadmap slug."""
    return roadmap_dir(plans_dir, slug) / DRAFT_SEEDS_DIRNAME


def _validate_draft_seed_path(relative_path: str) -> None:
    """Reject a path outside the current or legacy draft-seed directory."""
    if not isinstance(relative_path, str) or not relative_path.strip():
        raise RoadmapArtifactError(
            f"draft_seed_path must be a non-empty relative path, got {relative_path!r}"
        )
    if relative_path.startswith(("/", "\\")):
        raise RoadmapArtifactError(
            f"draft_seed_path must be relative, not absolute: {relative_path!r}"
        )
    parts = Path(relative_path).parts
    if ".." in parts:
        raise RoadmapArtifactError(
            f"draft_seed_path must not contain a '..' component: {relative_path!r}"
        )
    accepted_dirnames = (DRAFT_SEEDS_DIRNAME, LEGACY_DRAFT_SEEDS_DIRNAME)
    if not parts or parts[0] not in accepted_dirnames:
        raise RoadmapArtifactError(
            "draft_seed_path must begin with "
            f"'{DRAFT_SEEDS_DIRNAME}/' or '{LEGACY_DRAFT_SEEDS_DIRNAME}/', "
            f"got {relative_path!r}"
        )


def resolve_draft_seed_path(plans_dir: Path, slug: str, draft_seed_path: str) -> Path:
    """Join ``roadmap_dir`` with a validated relative draft-seed path.

    Lexical validation alone cannot see a symlink: a component-safe relative
    path can still resolve, on disk, to a file outside the roadmap directory
    if any path segment is a symlink pointing elsewhere. Resolve both the
    candidate and the root through the real filesystem and require the
    candidate to stay contained, so a planted symlink is rejected the same
    way a literal ``..`` component already is — the unresolved candidate is
    still what's returned, so callers see the path they asked for.
    """
    _validate_draft_seed_path(draft_seed_path)
    root = roadmap_dir(plans_dir, slug)
    candidate = root / draft_seed_path
    resolved_candidate = candidate.resolve()
    resolved_root = root.resolve()
    if not resolved_candidate.is_relative_to(resolved_root):
        raise RoadmapArtifactError(
            "draft_seed_path resolves outside the roadmap directory "
            f"(possibly via a symlink): {draft_seed_path!r}"
        )
    return candidate


def resolve_plan_seed_dest(plan_seeds_dir: Path, plan_id: str) -> Path:
    """Join ``plan-seeds/`` with a promotion destination for a validated id.

    The write-side mirror of :func:`resolve_draft_seed_path`: parsing stays
    permissive so a bad id reaches ``check_plan_ordering_totality`` as a gate
    violation the operator can correct, but ``roadmap --apply``
    runs no gates, so the path sink validates before it builds a destination.
    """
    if not PLAN_ID_SLUG_RE.fullmatch(plan_id):
        raise RoadmapArtifactError(
            f"plan id {plan_id!r} is not a create-compatible slug, so it has "
            f"no promotion destination — use lowercase letters, digits, and "
            f"hyphens only, starting and ending with a letter or digit"
        )
    return plan_seeds_dir / f"{plan_id}.md"


# --------------------------------------------------------------------------
# Closed vocabularies
# --------------------------------------------------------------------------


class DecisionStatus(str, enum.Enum):
    """Where a decision record stands. Two members, deliberately.

    ``SETTLED`` reads as *this is the decision of record*, which is what makes
    the reported pending count a queue that can be worked to zero rather than
    a tally that only rises. :func:`settle_pending_decision` moves one
    Roadmap-derived row from ``PENDING`` to ``SETTLED`` and changes nothing
    else; a published version is never hand-edited.
    """

    SETTLED = "settled"
    PENDING = "pending"


class FeedbackState(str, enum.Enum):
    """Where one piece of reviewer feedback stands.

    The reviewer ordinarily moves a row out of ``AWAITING_REVIEW``; the
    ``--reopen-ledger-feedback`` action is the sole tool exception. The state
    says a response is on offer, not that anyone accepted it. ``DEFERRED`` is
    how a reviewer parks a request without deleting source text.
    """

    OPEN = "open"
    AWAITING_REVIEW = "awaiting-review"
    DEFERRED = "deferred"


class FeedbackTargetKind(str, enum.Enum):
    """What one piece of feedback bears on: the whole artifact, or one row.

    The tag travels with its payload (``ROW`` carries the ``row_id``, ``ARTIFACT``
    carries none) so neither reading depends on a sibling key's absence.
    """

    ARTIFACT = "artifact"
    ROW = "row"


class FieldType(str, enum.Enum):
    """The logical shape of one entity field.

    **Logical, never physical.** A roadmap is written before a technology is
    chosen, so a field says what kind of thing it holds — `varchar(255)`,
    `NUMERIC(10,2)` and their siblings are a plan's decision, not a roadmap's.
    Six members. There is deliberately no ``collection``: a to-many needs an
    element type to mean anything, which would make ``entity_id`` optional on
    two members instead of implied by exactly one — and cardinality is a plan's
    decision, expressible here as a reference from the other side or as a
    business rule.
    """

    TEXT = "text"
    NUMBER = "number"
    BOOLEAN = "boolean"
    TIMESTAMP = "timestamp"
    ENUM = "enum"
    REFERENCE = "reference"


class PlanDisposition(str, enum.Enum):
    """How one derived plan maps to components.

    ``CROSS_CUTTING`` names work not owned by a single component slice.
    """

    KEEP = "keep"
    MERGE = "merge"
    SPLIT = "split"
    CROSS_CUTTING = "cross-cutting"


class ConstraintDisposition(str, enum.Enum):
    """How a roadmap treats one quality attribute.

    ``NOT_LOAD_BEARING`` is the honest answer for an attribute a project does
    not trade on, and it is what keeps a total disposition gate satisfiable
    without filler.
    """

    PRIORITIZED = "prioritized"
    TRADED_AWAY = "traded-away"
    NOT_LOAD_BEARING = "not-load-bearing"


class ResearchDisclosure(str, enum.Enum):
    """Whether one product literal may leave the repository for research."""

    EXTERNAL = "external"
    LOCAL = "local"


# The quality attributes a roadmap disposes, in display order. A flat
# *operational* list, not a conformance taxonomy: each name is a concern an
# operator ranks on its own, so ``reliability: not-load-bearing`` beside
# ``availability: prioritized`` is coherent under this reading. ISO/IEC 25010
# is at most a spelling reference — its hierarchy nests availability and fault
# tolerance under reliability, which would stop a roadmap disposing all three
# independently.
#
# The parser coerces nothing against this tuple: membership belongs to the
# totality gate, which reports an unknown attribute as a violation naming the
# offending row instead of dying at parse time.
QUALITY_ATTRIBUTES: tuple[str, ...] = (
    "performance",
    "scalability",
    "security",
    "availability",
    "maintainability",
    "fault-tolerance",
    "reliability",
)

HOSTING_FACETS: tuple[str, ...] = ("compute", "model", "topology")

# The concerns a roadmap's stack must cover: deployment platform, store engine,
# language/runtime. The parser does not enforce membership; the gates do.
STACK_CONCERNS: tuple[str, ...] = ("platform", "store-engine", "language-runtime")

# The frontmatter keys each artifact's collections are written under, in
# render order. These are wire names and need not match the artifact
# dataclasses' field names; exposed so the stage prompts can be pinned against
# one source rather than a hand-copied list.
DOMAIN_ROW_KEYS = ("entities", "business_rules", "workflows", "decisions")
CONSTRAINTS_ROW_KEYS = ("hosting", "dispositions", "constraints", "decisions")
# ``stack`` is written only when recorded, so stack-less artifacts keep
# rendering exactly CONSTRAINTS_ROW_KEYS.
COMPONENTS_ROW_KEYS = (
    "system_patterns",
    "component_patterns",
    "stores",
    "components",
    "decisions",
)
PLANS_ROW_KEYS = ("plans", "ordering", "assumptions", "decisions")

# Draft-seed provenance frontmatter keys gates scan before ``--apply``.
DRAFT_SEED_ROADMAP_COMPONENTS_KEY = "roadmap_components"
DRAFT_SEED_CROSS_CUTTING_KEY = "cross_cutting"

# The review collections all four artifacts may carry, in render order —
# deliberately *not* folded into the four design-key tuples above. Those name
# the rows a stage prompt asks the model to author and are pinned against the
# prompts; feedback and removals arrive from a reviewer's edit, and are rendered
# only when present.
REVIEW_ROW_KEYS = ("feedback", "removals")


class RoadmapArtifactError(Exception):
    """A roadmap artifact is unreadable or off its shape contract.

    Carries the ``path`` it came from when one is known, so a caller reports
    the file without re-deriving it. Relation failures are a separate channel:
    the gates return violations, they never raise this.
    """

    def __init__(self, message: str, *, path: Optional[Path] = None) -> None:
        super().__init__(message)
        self.path = path


# --------------------------------------------------------------------------
# Row types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class FieldRow:
    """One thing an entity holds.

    ``entity_id`` is set exactly when ``type`` is ``REFERENCE`` — it names the
    entity pointed at, which is what puts entity→entity edges on the same
    traceability chain workflows and business rules already ride.
    """

    name: str
    type: FieldType
    entity_id: Optional[str] = None


@dataclass(frozen=True)
class EntityRow:
    """A thing the domain is about, and what it holds.

    ``fields`` is what stops every derived plan re-inventing the entity's
    shape. It stays coarse on purpose: a field's *logical* type and, for a
    reference, its target — no optionality, no cardinality, no physical type.
    """

    id: str
    name: str
    fields: tuple[FieldRow, ...]


@dataclass(frozen=True)
class BusinessRuleRow:
    """A rule the domain enforces, and the entity ids it governs.

    Rules carry entity ids for the same reason workflows do: a constraint may
    anchor to a rule id, so a rule connected to no entity would be a valid
    anchor target that breaks the entity→constraint traceability chain.
    """

    id: str
    statement: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class WorkflowRow:
    """A path through the domain, and the entity ids it touches."""

    id: str
    name: str
    entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class RejectedAlternative:
    """An option a decision considered and turned down, with its reason."""

    option: str
    reason: str


@dataclass(frozen=True)
class DecisionRow:
    """One decision of record, on either artifact.

    ``anchor`` names the row the decision bears on, always by *id* — an
    operator confirming a ``PENDING`` decision, and any later stage inheriting
    it as a fence, both need to see what it constrains.
    A non-None ``source`` marks an inherited row with optional deliberation.
    """

    id: str
    chosen_option: str
    rejected_alternatives: tuple[RejectedAlternative, ...]
    rationale: Optional[str]
    anchor: str
    status: DecisionStatus
    source: Optional[str] = None


@dataclass(frozen=True)
class AttributeDispositionRow:
    """How the roadmap disposes one quality attribute.

    Its ``id`` is the only way a quality attribute reaches the anchor space —
    attribute names are a constant, not rows, so a bare name resolves nowhere.
    """

    id: str
    attribute: str
    disposition: ConstraintDisposition


@dataclass(frozen=True)
class ConstraintRow:
    """A constraint, the attribute it serves, and the upstream ids it anchors to."""

    id: str
    statement: str
    attribute: str
    anchor_ids: tuple[str, ...]


@dataclass(frozen=True)
class HostingRow:
    """One coarse hosting choice for the application."""

    id: str
    facet: str
    value: str
    product: Optional[str] = None
    description: Optional[str] = None
    research_disclosure: Optional[ResearchDisclosure] = None


@dataclass(frozen=True)
class StackRow:
    """One stack concern, either chosen (``choice``) or explicitly ``open``."""

    id: str
    concern: str
    choice: Optional[str] = None
    open: bool = False


@dataclass(frozen=True)
class FeedbackTarget:
    """What one feedback row bears on. ``row_id`` is set exactly when ``kind``
    is ``ROW``."""

    kind: FeedbackTargetKind
    row_id: Optional[str] = None


@dataclass(frozen=True)
class FeedbackReopenRecord:
    """One redacted fact about an explicitly confirmed feedback reopen."""

    selector: Mapping[str, str]
    reason: str
    nonce: str
    recorded_at: str

    def __post_init__(self) -> None:
        """Copy the selector so the frozen record retains immutable value semantics."""
        object.__setattr__(self, "selector", MappingProxyType(dict(self.selector)))

    def __hash__(self) -> int:
        return hash(
            (tuple(sorted(self.selector.items())), self.reason, self.nonce, self.recorded_at)
        )


@dataclass(frozen=True)
class FeedbackRow:
    """One reviewer redirect, kept verbatim until the reviewer closes it.

    ``request`` is the reviewer's own words and is never rewritten;
    ``proposed_response`` is what the model offered back, stored as text and
    compared to nothing. ``feedback_reopen`` is the redacted fact a dedicated,
    explicitly confirmed operator action writes; a fresh stage response clears it.
    """

    id: str
    target: FeedbackTarget
    request: str
    state: FeedbackState
    proposed_response: Optional[str] = None
    feedback_reopen: Optional[FeedbackReopenRecord] = None


@dataclass(frozen=True)
class RemovalRecord:
    """A design row that was dropped, why, and the feedback that asked for it.

    Mints no ``id`` of its own — nothing references a removal, and ``removed_id``
    is the anchor every violation message names.
    """

    removed_id: str
    rationale: str
    feedback_ids: tuple[str, ...]


@dataclass(frozen=True)
class DomainArtifact:
    """A parsed ``01-domain.md``: its rows in source order, plus the prose body.

    Rows stay an ordered tuple rather than a dict keyed by id so a duplicate id
    survives parsing and the duplicate-id gate has something to report — which
    is why ``feedback`` is a tuple too rather than keyed by feedback id.
    """

    entities: tuple[EntityRow, ...]
    business_rules: tuple[BusinessRuleRow, ...]
    workflows: tuple[WorkflowRow, ...]
    decisions: tuple[DecisionRow, ...]
    body: str
    feedback: tuple[FeedbackRow, ...] = ()
    removals: tuple[RemovalRecord, ...] = ()


@dataclass(frozen=True)
class ConstraintsArtifact:
    """A parsed ``02-constraints.md``: its rows in source order, plus the body."""

    dispositions: tuple[AttributeDispositionRow, ...]
    constraints: tuple[ConstraintRow, ...]
    decisions: tuple[DecisionRow, ...]
    body: str
    hosting: tuple[HostingRow, ...] = ()
    # None = stack not recorded (every version predating the collection);
    # () = recorded and empty. Never default to ().
    stack: Optional[tuple[StackRow, ...]] = None
    feedback: tuple[FeedbackRow, ...] = ()
    removals: tuple[RemovalRecord, ...] = ()


@dataclass(frozen=True)
class PatternRow:
    """One named pattern — free text, with no closed catalog.

    Used for both system-level and component-level patterns; the collection
    key distinguishes scope.
    """

    id: str
    name: str
    statement: str


@dataclass(frozen=True)
class StoreRow:
    """One store definition a component may reference."""

    id: str
    category: str
    sharing: str
    product: Optional[str] = None
    description: Optional[str] = None
    research_disclosure: Optional[ResearchDisclosure] = None


@dataclass(frozen=True)
class ComponentRow:
    """One logical unit of the domain, owning the entity ids it names.

    Ownership is **coverage, not exclusivity**: nothing forbids two components
    from naming one entity id, and no gate checks that they don't. See
    :func:`~plan_tool.roadmap_gates.check_entity_component_coverage`.
    """

    id: str
    name: str
    entity_ids: tuple[str, ...]
    pattern_ids: tuple[str, ...]
    constraint_ids: tuple[str, ...] = ()
    store_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComponentsArtifact:
    """A parsed ``03-components.md``: its rows in source order, plus the body."""

    system_patterns: tuple[PatternRow, ...]
    component_patterns: tuple[PatternRow, ...]
    components: tuple[ComponentRow, ...]
    decisions: tuple[DecisionRow, ...]
    body: str
    stores: tuple[StoreRow, ...] = ()
    feedback: tuple[FeedbackRow, ...] = ()
    removals: tuple[RemovalRecord, ...] = ()


@dataclass(frozen=True)
class PlanRow:
    """One derived plan, including its review contract and draft seed.

    ``intent`` and ``non_goals`` default empty only so roadmaps authored before
    the review contract remain readable. New stage-4 output is required to
    populate both by ``check_plan_review_context``.
    """

    id: str
    title: str
    disposition: PlanDisposition
    component_ids: tuple[str, ...]
    draft_seed_path: str
    sizing_rationale: str
    intent: str = ""
    non_goals: tuple[str, ...] = ()


@dataclass(frozen=True)
class OrderingEntry:
    """One slot in the execution sequence — references plan ids, mints no row id."""

    plan_id: str
    depends_on: tuple[str, ...] = ()
    assumption_targets: tuple[str, ...] = ()


@dataclass(frozen=True)
class AssumptionRow:
    """An inter-plan assumption and the plan ids that consume it."""

    id: str
    statement: str
    consuming_plan_ids: tuple[str, ...]


@dataclass(frozen=True)
class PlansArtifact:
    """A parsed ``04-roadmap.md``: its rows in source order, plus the body."""

    plans: tuple[PlanRow, ...]
    ordering: tuple[OrderingEntry, ...]
    assumptions: tuple[AssumptionRow, ...]
    decisions: tuple[DecisionRow, ...]
    body: str
    feedback: tuple[FeedbackRow, ...] = ()
    removals: tuple[RemovalRecord, ...] = ()


RoadmapArtifact = (
    DomainArtifact | ConstraintsArtifact | ComponentsArtifact | PlansArtifact
)
DesignRow = (
    EntityRow
    | BusinessRuleRow
    | WorkflowRow
    | DecisionRow
    | AttributeDispositionRow
    | ConstraintRow
    | PatternRow
    | ComponentRow
    | PlanRow
    | AssumptionRow
)
StageRow = DesignRow | HostingRow | StoreRow | StackRow


@dataclass(frozen=True)
class StageRowOperationPolicy:
    """The shared mutation boundary for one stage row collection."""

    allow_add: bool = True
    allow_remove: bool = True
    allow_prose: bool = True
    requires_ordering_companion: bool = False
    immutable_fields: tuple[str, ...] = ()


_DEFAULT_STAGE_ROW_OPERATION_POLICY = StageRowOperationPolicy()
_STAGE_ROW_OPERATION_POLICIES: Final[Mapping[str, StageRowOperationPolicy]] = MappingProxyType(
    {
        "hosting": StageRowOperationPolicy(
            allow_add=False,
            allow_remove=False,
            allow_prose=False,
            immutable_fields=("facet",),
        ),
        "stores": StageRowOperationPolicy(allow_prose=False),
        # Addable so a candidate can introduce the stack on a roadmap that has
        # none (unlike hosting); never removable, so a recorded stack cannot
        # read as "not recorded" afterwards. No row-owned prose span.
        "stack": StageRowOperationPolicy(
            allow_remove=False,
            allow_prose=False,
            immutable_fields=("concern",),
        ),
        "plans": StageRowOperationPolicy(requires_ordering_companion=True),
    }
)


def stage_row_operation_policy(row_type: str) -> StageRowOperationPolicy:
    """Return the fixed operation boundary for one stage row collection."""
    return _STAGE_ROW_OPERATION_POLICIES.get(row_type, _DEFAULT_STAGE_ROW_OPERATION_POLICY)


def stage_collection_participates_in_impact(collection: str) -> bool:
    """Whether one stage collection is eligible for the impact graph."""
    policy = stage_row_operation_policy(collection)
    return policy.allow_add or policy.allow_remove


def stage_row_edit_preserves_fixed_fields(
    before: StageRow, after: StageRow, *, row_type: str
) -> bool:
    """Whether an edit preserves every field the row policy fixes."""
    return all(
        getattr(before, field) == getattr(after, field)
        for field in stage_row_operation_policy(row_type).immutable_fields
    )


_STAGE_ROW_TYPE_BY_COLLECTION: dict[str, type[StageRow]] = {
    "entities": EntityRow,
    "business_rules": BusinessRuleRow,
    "workflows": WorkflowRow,
    "decisions": DecisionRow,
    "dispositions": AttributeDispositionRow,
    "constraints": ConstraintRow,
    "hosting": HostingRow,
    "system_patterns": PatternRow,
    "component_patterns": PatternRow,
    "stores": StoreRow,
    "stack": StackRow,
    "components": ComponentRow,
    "plans": PlanRow,
    "assumptions": AssumptionRow,
}


def replace_design_row(
    artifact: RoadmapArtifact,
    *,
    collection: str,
    row_id: str,
    field: str,
    value: str,
) -> RoadmapArtifact:
    """Return ``artifact`` with one existing design row's text field replaced."""
    try:
        rows = design_row_collections(artifact)[collection]
    except KeyError as exc:
        raise ValueError(
            f"artifact has no design-row collection {collection!r}"
        ) from exc
    description = f"design row {row_id!r} in collection {collection!r}"
    index = _exactly_one_index(rows, lambda row: row.id == row_id, description)
    row = rows[index]
    row_fields = {item.name for item in fields(row)}
    current_value = getattr(row, field, None) if field in row_fields else None
    if (
        field == "id"
        or field not in row_fields
        or not isinstance(current_value, str)
        or isinstance(current_value, enum.Enum)
    ):
        # ``DecisionStatus``/``PlanDisposition``/``ConstraintDisposition`` are
        # ``str, enum.Enum`` subclasses, so ``isinstance(..., str)`` alone
        # would accept them — the closed-vocabulary check the enum exists to
        # enforce belongs to the type, not to this function's caller.
        raise ValueError(
            f"design row {row_id!r} has no replaceable text field {field!r}"
        )

    replacement = replace(row, **{field: value})
    return replace(artifact, **{collection: _replace_tuple_item(rows, index, replacement)})


def settle_pending_decision(
    artifact: RoadmapArtifact, *, decision_id: str
) -> RoadmapArtifact:
    """Return ``artifact`` with one Roadmap-derived ``PENDING`` decision moved
    to ``SETTLED``. Every other field of that row, every other row, the
    review collections, and the body stay the same objects.

    Refuses, in this order, an id that does not occur exactly once, an
    inherited row (``source is not None``) regardless of its status, and a
    row that is already ``SETTLED``. Inheritance is checked before status so
    an inherited row's refusal always names inheritance, never "already
    settled" — most inherited rows arrive settled, and checking status first
    would misreport the real reason.
    """
    description = f"decision {decision_id!r}"
    index = _exactly_one_index(
        artifact.decisions, lambda row: row.id == decision_id, description
    )
    row = artifact.decisions[index]
    if row.source is not None:
        raise ValueError(f"{description} is inherited and cannot be settled here")
    if row.status is not DecisionStatus.PENDING:
        raise ValueError(f"{description} is not pending")
    settled = replace(row, status=DecisionStatus.SETTLED)
    return replace(
        artifact, decisions=_replace_tuple_item(artifact.decisions, index, settled)
    )


def stage_row_collections(artifact: RoadmapArtifact) -> dict[str, tuple[StageRow, ...]]:
    """Return every collection the typed stage route may address.

    This is intentionally separate from :func:`design_row_collections`: hosting
    and stores are stage identities, not local presentation targets.
    """
    collections: dict[str, tuple[StageRow, ...]] = {
        name: rows
        for name, rows in design_row_collections(artifact).items()
    }
    if isinstance(artifact, ConstraintsArtifact):
        collections["hosting"] = artifact.hosting
        # Absent (None) stays absent; an empty tuple is a recorded, empty stack.
        if artifact.stack is not None:
            collections["stack"] = artifact.stack
    if isinstance(artifact, ComponentsArtifact):
        collections["stores"] = artifact.stores
    return collections


def stage_collection_accepts_add(artifact: RoadmapArtifact, collection: str) -> bool:
    """Whether ``collection`` exists on ``artifact`` for an add, counting an
    unrecorded ``stack`` (which an add may introduce) as present."""
    return collection in stage_row_collections(artifact) or (
        collection == "stack" and isinstance(artifact, ConstraintsArtifact)
    )


def append_stage_row(
    artifact: RoadmapArtifact, *, collection: str, row: StageRow
) -> RoadmapArtifact:
    """Return ``artifact`` with one typed stage row appended to ``collection``."""
    if not stage_row_operation_policy(collection).allow_add:
        raise ValueError(f"{collection} rows are never added by the stage route")
    if (
        collection == "stack"
        and isinstance(artifact, ConstraintsArtifact)
        and artifact.stack is None
    ):
        # The one collection an add may create: introducing the stack on a
        # roadmap that never recorded one.
        if type(row) is not StackRow:
            raise ValueError(
                f"stage collection 'stack' requires StackRow, not {type(row).__name__}"
            )
        rows: tuple[StageRow, ...] = ()
    else:
        rows = _stage_collection(artifact, collection, row)
    if any(existing.id == row.id for existing in rows):
        raise ValueError(
            f"stage row {row.id!r} in collection {collection!r} already exists"
        )
    return replace(artifact, **{collection: (*rows, row)})


def replace_stage_row(
    artifact: RoadmapArtifact, *, collection: str, row_id: str, row: StageRow
) -> RoadmapArtifact:
    """Return ``artifact`` with only its named typed stage row replaced."""
    rows = _stage_collection(artifact, collection, row)
    if row.id != row_id:
        raise ValueError(
            f"stage replacement row id {row.id!r} does not match {row_id!r}"
        )
    description = f"stage row {row_id!r} in collection {collection!r}"
    index = _exactly_one_index(rows, lambda existing: existing.id == row_id, description)
    return replace(artifact, **{collection: _replace_tuple_item(rows, index, row)})


def remove_stage_row(
    artifact: RoadmapArtifact, *, collection: str, row_id: str
) -> RoadmapArtifact:
    """Return ``artifact`` with only its named typed stage row removed."""
    if not stage_row_operation_policy(collection).allow_remove:
        raise ValueError(f"{collection} rows are never removed by the stage route")
    rows = _stage_collection(artifact, collection)
    description = f"stage row {row_id!r} in collection {collection!r}"
    index = _exactly_one_index(rows, lambda existing: existing.id == row_id, description)
    return replace(artifact, **{collection: _remove_tuple_item(rows, index)})


def append_removal_record(
    artifact: RoadmapArtifact, record: RemovalRecord
) -> RoadmapArtifact:
    """Return ``artifact`` with one new continuity record appended."""
    if any(existing.removed_id == record.removed_id for existing in artifact.removals):
        raise ValueError(f"removal record for {record.removed_id!r} already exists")
    return replace(artifact, removals=(*artifact.removals, record))


def append_plan_ordering_entry(
    artifact: PlansArtifact, entry: OrderingEntry
) -> PlansArtifact:
    """Return a plans artifact with one matching ordering entry appended."""
    if any(existing.plan_id == entry.plan_id for existing in artifact.ordering):
        raise ValueError(f"ordering entry for plan {entry.plan_id!r} already exists")
    return replace(artifact, ordering=(*artifact.ordering, entry))


def remove_plan_ordering_entry(
    artifact: PlansArtifact, *, plan_id: str
) -> PlansArtifact:
    """Return a plans artifact with only one matching ordering entry removed."""
    description = f"ordering entry for plan {plan_id!r}"
    index = _exactly_one_index(
        artifact.ordering, lambda entry: entry.plan_id == plan_id, description
    )
    return replace(artifact, ordering=_remove_tuple_item(artifact.ordering, index))


_TupleItem = TypeVar("_TupleItem")


def _exactly_one_index(
    items: tuple[_TupleItem, ...], matches: Callable[[_TupleItem], bool], description: str
) -> int:
    """Find one intended member while retaining its caller-specific label."""
    indexes = [index for index, item in enumerate(items) if matches(item)]
    if len(indexes) != 1:
        raise ValueError(f"{description} must occur exactly once, found {len(indexes)}")
    return indexes[0]


def _replace_tuple_item(
    items: tuple[_TupleItem, ...], index: int, replacement: _TupleItem
) -> tuple[_TupleItem, ...]:
    """Replace exactly the selected immutable tuple member."""
    return (*items[:index], replacement, *items[index + 1 :])


def _remove_tuple_item(items: tuple[_TupleItem, ...], index: int) -> tuple[_TupleItem, ...]:
    """Remove exactly the selected immutable tuple member."""
    return (*items[:index], *items[index + 1 :])


def _stage_collection(
    artifact: RoadmapArtifact, collection: str, row: StageRow | None = None
) -> tuple[StageRow, ...]:
    """Resolve one stage collection and, when supplied, its closed row type."""
    try:
        rows = stage_row_collections(artifact)[collection]
        expected_type = _STAGE_ROW_TYPE_BY_COLLECTION[collection]
    except KeyError as exc:
        raise ValueError(f"artifact has no stage-row collection {collection!r}") from exc
    if row is not None and type(row) is not expected_type:
        raise ValueError(
            f"stage collection {collection!r} requires {expected_type.__name__}, "
            f"not {type(row).__name__}"
        )
    return rows


def design_row_collections(artifact: RoadmapArtifact) -> dict[str, tuple[DesignRow, ...]]:
    """Return every design-row collection on ``artifact``, keyed by its plural name.

    Public and shared with :mod:`plan_tool.roadmap_revision`: that module's
    local-revision preflight needs the same collection-name-to-row-tuple
    dispatch, in the same render order, to resolve a feedback target's live
    row. Two hand-maintained copies of this ``isinstance`` table would drift
    the first time an artifact gains a collection — the same hazard
    :func:`roadmap_gates.design_row_ids` documents for its own, differently
    shaped (id-only, singular-label) sibling table.
    """
    if isinstance(artifact, DomainArtifact):
        return {
            "entities": artifact.entities,
            "business_rules": artifact.business_rules,
            "workflows": artifact.workflows,
            "decisions": artifact.decisions,
        }
    if isinstance(artifact, ConstraintsArtifact):
        return {
            "dispositions": artifact.dispositions,
            "constraints": artifact.constraints,
            "decisions": artifact.decisions,
        }
    if isinstance(artifact, ComponentsArtifact):
        return {
            "system_patterns": artifact.system_patterns,
            "component_patterns": artifact.component_patterns,
            "components": artifact.components,
            "decisions": artifact.decisions,
        }
    return {
        "plans": artifact.plans,
        "assumptions": artifact.assumptions,
        "decisions": artifact.decisions,
    }


def impact_node_collections(artifact: RoadmapArtifact) -> dict[str, tuple[StageRow, ...]]:
    """Return every row collection that can participate in impact relations."""
    return {
        name: rows
        for name, rows in stage_row_collections(artifact).items()
        if stage_collection_participates_in_impact(name)
    }


@dataclass(frozen=True)
class DraftSeedProvenance:
    """Provenance frontmatter on a stage-4 draft seed."""

    roadmap_components: tuple[str, ...]
    cross_cutting: bool = False


def plans_design_rows(artifact: PlansArtifact) -> tuple[tuple[str, str], ...]:
    """Return ``(kind label, id)`` for every design row on a plans artifact.

    Ordering entries are excluded — they reference plan ids but mint no ids.
    """
    rows: list[tuple[str, str]] = []
    for row in artifact.plans:
        rows.append(("plan", row.id))
    for row in artifact.assumptions:
        rows.append(("assumption", row.id))
    for row in artifact.decisions:
        rows.append(("decision", row.id))
    return tuple(rows)


def components_design_rows(
    artifact: ComponentsArtifact,
) -> tuple[tuple[str, str], ...]:
    """Return ``(kind label, id)`` for every design row on a components artifact.

    Kind labels are message-facing strings; they need not match wire keys.
    Order matches render order: system patterns, component patterns, components,
    then decisions.
    """
    rows: list[tuple[str, str]] = []
    for row in artifact.system_patterns:
        rows.append(("system pattern", row.id))
    for row in artifact.component_patterns:
        rows.append(("component pattern", row.id))
    for row in artifact.components:
        rows.append(("component", row.id))
    for row in artifact.decisions:
        rows.append(("decision", row.id))
    return tuple(rows)


# --------------------------------------------------------------------------
# Frontmatter splitting and shape coercion
# --------------------------------------------------------------------------

_FENCE = "---"

# Exact-source structural rewrites require canonical scalar sources never to wrap.
_CANONICAL_YAML_WIDTH = float("inf")


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split ``text`` into its frontmatter YAML and its prose body.

    Mirrors the plan-side rule: line 1 must be exactly ``---``, the next bare
    ``---`` closes the block, and everything after it is the body, byte for
    byte.
    """
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != _FENCE:
        raise RoadmapArtifactError(
            "roadmap artifact must begin with a '---' frontmatter fence on line 1"
        )
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == _FENCE:
            return "".join(lines[1:index]), "".join(lines[index + 1 :])
    raise RoadmapArtifactError(
        "roadmap artifact opens with '---' but has no closing fence"
    )


def _parse_frontmatter(text: str, *, artifact: str) -> tuple[dict[str, Any], str]:
    """Return ``(frontmatter mapping, body)`` for one artifact's text."""
    frontmatter_yaml, body = _split_frontmatter(text)
    try:
        raw = yaml.safe_load(frontmatter_yaml)
    except yaml.YAMLError as exc:
        feedback_hint = ""
        if re.search(r"(?m)^feedback:[ \t]*$", frontmatter_yaml):
            feedback_hint = (
                "\nTo repair a feedback `request`, use a YAML block scalar:\n"
                "  request: >-\n"
                "    <your request>"
            )
        raise RoadmapArtifactError(
            f"invalid YAML in {artifact} frontmatter: {exc}{feedback_hint}"
        ) from exc
    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise RoadmapArtifactError(
            f"{artifact} frontmatter must be a YAML mapping, "
            f"got {type(raw).__name__}"
        )
    return raw, body


def _iter_rows(frontmatter: dict[str, Any], key: str) -> Iterator[tuple[int, dict]]:
    """Yield ``(index, row mapping)`` for the rows under ``key``.

    An absent or null collection yields nothing — an artifact with no rows is
    the non-empty gate's to reject, not a parse failure. A present non-list, or
    a row that is not a mapping, is a shape error.
    """
    value = frontmatter.get(key)
    if value is None:
        return
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"'{key}' must be a list of rows, got {type(value).__name__}"
        )
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise RoadmapArtifactError(
                f"'{key}' row {index} must be a mapping, got {type(item).__name__}"
            )
        yield index, item


def _text_at(raw: dict, field: str, *, where: str) -> str:
    """A required string field. Present and typed, but free to be blank —
    emptiness of prose fields is a gate's judgment, not a shape rule."""
    if field not in raw:
        raise RoadmapArtifactError(f"{where} is missing required key '{field}'")
    value = raw[field]
    if not isinstance(value, str):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a string, "
            f"got {type(value).__name__}"
        )
    return value


def _row_id(raw: dict, *, key: str, index: int, field: str = "id") -> str:
    """The row's identifier, which every violation message anchors on and so may
    not be blank. ``field`` names it — a removal record anchors on ``removed_id``
    and mints no id of its own."""
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RoadmapArtifactError(
            f"'{key}' row {index} must carry a non-empty string '{field}', "
            f"got {value!r}"
        )
    return value


def _row_text(raw: dict, field: str, *, key: str, row_id: str) -> str:
    return _text_at(raw, field, where=f"'{key}' row '{row_id}'")


def _id_list(raw: dict, field: str, *, key: str, row_id: str) -> tuple[str, ...]:
    """A required list-of-ids field. Present-and-empty parses; the gates decide
    whether a row is allowed to reference nothing."""
    where = f"'{key}' row '{row_id}'"
    if field not in raw:
        raise RoadmapArtifactError(f"{where} is missing required key '{field}'")
    value = raw[field]
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a list of ids, "
            f"got {type(value).__name__}"
        )
    ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RoadmapArtifactError(
                f"{where} field '{field}' must hold non-empty id strings, "
                f"got {item!r}"
            )
        ids.append(item)
    return tuple(ids)


def _optional_id_list(
    raw: dict, field: str, *, key: str, row_id: str
) -> tuple[str, ...]:
    """An optional list-of-ids field. Absent or null yields an empty tuple."""
    if field not in raw:
        return ()
    where = f"'{key}' row '{row_id}'"
    value = raw[field]
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a list of ids, "
            f"got {type(value).__name__}"
        )
    ids: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RoadmapArtifactError(
                f"{where} field '{field}' must hold non-empty id strings, "
                f"got {item!r}"
            )
        ids.append(item)
    return tuple(ids)


def _optional_row_text(raw: dict, field: str, *, key: str, row_id: str) -> str:
    """An optional prose field. Absent or null preserves a legacy row."""
    if field not in raw or raw[field] is None:
        return ""
    return _text_at(raw, field, where=f"'{key}' row '{row_id}'")


def _optional_text_list(
    raw: dict, field: str, *, key: str, row_id: str
) -> tuple[str, ...]:
    """An optional list of non-empty prose strings.

    Unlike :func:`_optional_id_list`, these values are reviewer-facing text,
    not references. Absence remains accepted for pre-review-contract
    roadmaps; a plans gate asks a newly authored artifact to supply them.
    """
    if field not in raw or raw[field] is None:
        return ()
    where = f"'{key}' row '{row_id}'"
    value = raw[field]
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a list of strings, "
            f"got {type(value).__name__}"
        )
    values: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise RoadmapArtifactError(
                f"{where} field '{field}' must hold non-empty strings, "
                f"got {item!r}"
            )
        values.append(item)
    return tuple(values)


def _coerce_status(value: Any, *, row_id: str) -> DecisionStatus:
    try:
        return DecisionStatus(value)
    except ValueError:
        known = ", ".join(member.value for member in DecisionStatus)
        raise RoadmapArtifactError(
            f"'decisions' row '{row_id}' has unknown status {value!r} "
            f"(expected one of {known})"
        ) from None


def _coerce_plan_disposition(value: Any, *, row_id: str) -> PlanDisposition:
    try:
        return PlanDisposition(value)
    except ValueError:
        known = ", ".join(member.value for member in PlanDisposition)
        raise RoadmapArtifactError(
            f"'plans' row '{row_id}' has unknown disposition {value!r} "
            f"(expected one of {known})"
        ) from None


def _coerce_disposition(value: Any, *, row_id: str) -> ConstraintDisposition:
    try:
        return ConstraintDisposition(value)
    except ValueError:
        known = ", ".join(member.value for member in ConstraintDisposition)
        raise RoadmapArtifactError(
            f"'dispositions' row '{row_id}' has unknown disposition {value!r} "
            f"(expected one of {known})"
        ) from None


def _coerce_feedback_state(value: Any, *, row_id: str) -> FeedbackState:
    try:
        return FeedbackState(value)
    except ValueError:
        known = ", ".join(member.value for member in FeedbackState)
        raise RoadmapArtifactError(
            f"'feedback' row '{row_id}' has unknown state {value!r} "
            f"(expected one of {known})"
        ) from None


def _coerce_target_kind(value: Any, *, row_id: str) -> FeedbackTargetKind:
    try:
        return FeedbackTargetKind(value)
    except ValueError:
        known = ", ".join(member.value for member in FeedbackTargetKind)
        raise RoadmapArtifactError(
            f"'feedback' row '{row_id}' has unknown target kind {value!r} "
            f"(expected one of {known})"
        ) from None


def _coerce_field_type(value: Any, *, row_id: str, name: str) -> FieldType:
    try:
        return FieldType(value)
    except ValueError:
        known = ", ".join(member.value for member in FieldType)
        raise RoadmapArtifactError(
            f"'entities' row '{row_id}' field '{name}' has unknown type "
            f"{value!r} (expected one of {known})"
        ) from None


def _parse_field_rows(raw: dict, *, row_id: str) -> tuple[FieldRow, ...]:
    """Parse one entity's ``fields`` collection.

    Required key, present-and-empty parses — the same split the rules' and
    workflows' ``entity_ids`` use, so an empty list is a *relation* failure the
    gate reports against the row rather than a parse error with no row context.
    """
    field_key = "fields"
    where = f"'entities' row '{row_id}'"
    value = _require_key(raw, field_key, key="entities", row_id=row_id)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"{where} field '{field_key}' must be a list of rows, "
            f"got {type(value).__name__}"
        )
    rows: list[FieldRow] = []
    for index, item in enumerate(value):
        item_where = f"{where} field {index}"
        if not isinstance(item, dict):
            raise RoadmapArtifactError(
                f"{item_where} must be a mapping, got {type(item).__name__}"
            )
        # Identifier-like, not prose: the duplicate-name gate and every field
        # message anchor on it, so blank is rejected here as it is for an id.
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RoadmapArtifactError(
                f"{item_where} must carry a non-empty string 'name', "
                f"got {name!r}"
            )
        if "type" not in item:
            raise RoadmapArtifactError(
                f"{where} field '{name}' is missing required key 'type'"
            )
        entity_id = item.get("entity_id")
        if entity_id is not None and (
            not isinstance(entity_id, str) or not entity_id.strip()
        ):
            raise RoadmapArtifactError(
                f"{where} field '{name}' has an 'entity_id' that is not a "
                f"non-empty string, got {entity_id!r}"
            )
        rows.append(
            FieldRow(
                name=name,
                type=_coerce_field_type(item["type"], row_id=row_id, name=name),
                entity_id=entity_id,
            )
        )
    return tuple(rows)


def _parse_decision_rows(frontmatter: dict[str, Any]) -> tuple[DecisionRow, ...]:
    key = "decisions"
    rows: list[DecisionRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        source = _optional_decision_text(raw, "source", row_id=row_id)
        inherited = source is not None
        rows.append(
            DecisionRow(
                id=row_id,
                chosen_option=_row_text(raw, "chosen_option", key=key, row_id=row_id),
                rejected_alternatives=_parse_alternatives(
                    raw, row_id=row_id, required=not inherited
                ),
                rationale=_optional_decision_text(raw, "rationale", row_id=row_id)
                if inherited
                else _row_text(raw, "rationale", key=key, row_id=row_id),
                anchor=_row_text(raw, "anchor", key=key, row_id=row_id),
                status=_coerce_status(
                    _require_key(raw, "status", key=key, row_id=row_id),
                    row_id=row_id,
                ),
                source=source,
            )
        )
    return tuple(rows)


def _optional_product(raw: dict, *, key: str, row_id: str) -> Optional[str]:
    """The optional 'product' field shared by hosting and store rows."""
    product = raw.get("product")
    if product is not None and not isinstance(product, str):
        raise RoadmapArtifactError(
            f"'{key}' row '{row_id}' field 'product' must be a string, "
            f"got {type(product).__name__}"
        )
    return product


def _optional_description(raw: dict, *, key: str, row_id: str) -> Optional[str]:
    """The optional operator description shared by hosting and store rows."""
    description = raw.get("description")
    if description is not None and not isinstance(description, str):
        raise RoadmapArtifactError(
            f"'{key}' row '{row_id}' field 'description' must be a string, "
            f"got {type(description).__name__}"
        )
    return description


def _optional_research_disclosure(
    raw: dict, *, key: str, row_id: str
) -> Optional[ResearchDisclosure]:
    """The optional outbound-research consent shared by product rows."""
    disclosure = raw.get("research_disclosure")
    if disclosure is None:
        return None
    if not isinstance(disclosure, str):
        raise RoadmapArtifactError(
            f"'{key}' row '{row_id}' field 'research_disclosure' must be a string, "
            f"got {type(disclosure).__name__}"
        )
    try:
        return ResearchDisclosure(disclosure)
    except ValueError as exc:
        known = ", ".join(member.value for member in ResearchDisclosure)
        raise RoadmapArtifactError(
            f"'{key}' row '{row_id}' field 'research_disclosure' must be one of "
            f"{known}, got {disclosure!r}"
        ) from exc


def _parse_hosting_rows(frontmatter: dict[str, Any]) -> tuple[HostingRow, ...]:
    key = "hosting"
    rows: list[HostingRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        facet = _row_text(raw, "facet", key=key, row_id=row_id)
        value = _row_text(raw, "value", key=key, row_id=row_id)
        product = _optional_product(raw, key=key, row_id=row_id)
        description = _optional_description(raw, key=key, row_id=row_id)
        research_disclosure = _optional_research_disclosure(
            raw, key=key, row_id=row_id
        )
        if product is not None and facet in {"model", "topology"}:
            raise RoadmapArtifactError(
                f"'{key}' row '{row_id}' with facet '{facet}' must not carry "
                "a 'product'"
            )
        rows.append(
            HostingRow(
                id=row_id,
                facet=facet,
                value=value,
                product=product,
                description=description,
                research_disclosure=research_disclosure,
            )
        )
    return tuple(rows)


def _parse_stack_rows(
    frontmatter: dict[str, Any],
) -> Optional[tuple[StackRow, ...]]:
    """``None`` when the key is absent or null (not recorded); a tuple, possibly
    empty, when it is a list. Duplicate ids, unknown concerns and a choice/open
    combination other than exactly one parse; ``check_stack_totality`` owns them."""
    key = "stack"
    if frontmatter.get(key) is None:
        return None
    rows: list[StackRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        concern = _row_text(raw, "concern", key=key, row_id=row_id)
        choice = raw.get("choice")
        if choice is not None and not isinstance(choice, str):
            raise RoadmapArtifactError(
                f"'{key}' row '{row_id}' field 'choice' must be a string, "
                f"got {type(choice).__name__}"
            )
        is_open = raw.get("open", False)
        if not isinstance(is_open, bool):
            raise RoadmapArtifactError(
                f"'{key}' row '{row_id}' field 'open' must be a boolean, "
                f"got {type(is_open).__name__}"
            )
        rows.append(
            StackRow(id=row_id, concern=concern, choice=choice, open=is_open)
        )
    return tuple(rows)


def _parse_store_rows(frontmatter: dict[str, Any]) -> tuple[StoreRow, ...]:
    key = "stores"
    rows: list[StoreRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        product = _optional_product(raw, key=key, row_id=row_id)
        description = _optional_description(raw, key=key, row_id=row_id)
        research_disclosure = _optional_research_disclosure(
            raw, key=key, row_id=row_id
        )
        rows.append(
            StoreRow(
                id=row_id,
                category=_row_text(raw, "category", key=key, row_id=row_id),
                sharing=_row_text(raw, "sharing", key=key, row_id=row_id),
                product=product,
                description=description,
                research_disclosure=research_disclosure,
            )
        )
    return tuple(rows)


def _require_key(raw: dict, field: str, *, key: str, row_id: str) -> Any:
    if field not in raw:
        raise RoadmapArtifactError(
            f"'{key}' row '{row_id}' is missing required key '{field}'"
        )
    return raw[field]


def _optional_decision_text(raw: dict, field: str, *, row_id: str) -> Optional[str]:
    """Return an inherited decision's optional text field when it is present."""
    if field not in raw:
        return None
    return _row_text(raw, field, key="decisions", row_id=row_id)


def _parse_alternatives(
    raw: dict, *, row_id: str, required: bool = True
) -> tuple[RejectedAlternative, ...]:
    field = "rejected_alternatives"
    where = f"'decisions' row '{row_id}'"
    if not required and field not in raw:
        return ()
    value = _require_key(raw, field, key="decisions", row_id=row_id)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a list of rows, "
            f"got {type(value).__name__}"
        )
    alternatives: list[RejectedAlternative] = []
    for index, item in enumerate(value):
        item_where = f"{where} rejected alternative {index}"
        if not isinstance(item, dict):
            raise RoadmapArtifactError(
                f"{item_where} must be a mapping, got {type(item).__name__}"
            )
        alternatives.append(
            RejectedAlternative(
                option=_text_at(item, "option", where=item_where),
                reason=_text_at(item, "reason", where=item_where),
            )
        )
    return tuple(alternatives)


def _parse_feedback_target(raw: dict, *, row_id: str) -> FeedbackTarget:
    """Parse one feedback row's nested ``target`` mapping.

    A tag disagreeing with its payload — ``kind: row`` without a ``row_id``, or
    ``kind: artifact`` with one — is a shape error rather than a gate's finding:
    it has no defensible reading for a gate to report against. Whether the id
    resolves to a declared row is the gate's question.
    """
    field = "target"
    where = f"'feedback' row '{row_id}'"
    value = _require_key(raw, field, key="feedback", row_id=row_id)
    if not isinstance(value, dict):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a mapping, "
            f"got {type(value).__name__}"
        )
    if "kind" not in value:
        raise RoadmapArtifactError(f"{where} target is missing required key 'kind'")
    kind = _coerce_target_kind(value["kind"], row_id=row_id)
    target_row_id = value.get("row_id")
    if kind is FeedbackTargetKind.ROW:
        if not isinstance(target_row_id, str) or not target_row_id.strip():
            raise RoadmapArtifactError(
                f"{where} target 'kind: row' must carry a non-empty string "
                f"'row_id', got {target_row_id!r}"
            )
    elif target_row_id is not None:
        raise RoadmapArtifactError(
            f"{where} target 'kind: artifact' must not carry a 'row_id', "
            f"got {target_row_id!r}"
        )
    return FeedbackTarget(kind=kind, row_id=target_row_id)


def _parse_proposed_response(
    raw: dict, *, row_id: str, state: FeedbackState
) -> Optional[str]:
    """The model's optional proposed response.

    ``awaiting-review`` is *defined* by carrying one, so a blank or absent
    response in that state is a shape error — a deliberate exception to
    ``_text_at``'s rule that prose emptiness is a gate's judgment, because the
    state itself would otherwise claim a review that does not exist. The other
    two states may carry one: a reviewer reopening a row keeps the prior
    response readable beside their request while they decide.
    """
    field = "proposed_response"
    where = f"'feedback' row '{row_id}'"
    value = raw.get(field)
    if value is not None and not isinstance(value, str):
        raise RoadmapArtifactError(
            f"{where} field '{field}' must be a string, "
            f"got {type(value).__name__}"
        )
    if state is FeedbackState.AWAITING_REVIEW and not (value or "").strip():
        raise RoadmapArtifactError(
            f"{where} is '{FeedbackState.AWAITING_REVIEW.value}' and must carry "
            f"a non-blank '{field}', got {value!r}"
        )
    return value


def _parse_feedback_reopen_record(
    raw: dict, *, row_id: str
) -> Optional[FeedbackReopenRecord]:
    """Parse the one closed, redacted record an explicitly confirmed reopen keeps."""
    field = "feedback_reopen"
    if field not in raw:
        return None

    where = f"'feedback' row '{row_id}' field '{field}'"
    value = raw[field]
    if not isinstance(value, dict):
        raise RoadmapArtifactError(
            f"{where} must be a mapping, got {type(value).__name__}"
        )

    required_keys = {"selector", "reason", "nonce", "recorded_at"}
    missing_keys = sorted(required_keys - value.keys())
    if missing_keys:
        raise RoadmapArtifactError(f"{where} is missing required key {missing_keys[0]!r}")
    extra_keys = sorted(value.keys() - required_keys, key=repr)
    if extra_keys:
        raise RoadmapArtifactError(f"{where} has unsupported key {extra_keys[0]!r}")

    selector = value["selector"]
    if not isinstance(selector, dict):
        raise RoadmapArtifactError(
            f"{where} field 'selector' must be a mapping, "
            f"got {type(selector).__name__}"
        )
    selector_keys = {"artifact_key", "feedback_id"}
    missing_selector_keys = sorted(selector_keys - selector.keys())
    if missing_selector_keys:
        raise RoadmapArtifactError(
            f"{where} field 'selector' is missing required key "
            f"{missing_selector_keys[0]!r}"
        )
    extra_selector_keys = sorted(selector.keys() - selector_keys, key=repr)
    if extra_selector_keys:
        raise RoadmapArtifactError(
            f"{where} field 'selector' has unsupported key "
            f"{extra_selector_keys[0]!r}"
        )
    parsed_selector: dict[str, str] = {}
    for selector_key in ("artifact_key", "feedback_id"):
        selector_value = selector[selector_key]
        if not isinstance(selector_value, str) or not RECEIPT_SAFE_ID_RE.fullmatch(
            selector_value
        ):
            raise RoadmapArtifactError(
                f"{where} field 'selector.{selector_key}' must be a "
                f"receipt-safe non-empty string, got {selector_value!r}"
            )
        parsed_selector[selector_key] = selector_value

    reason = value["reason"]
    if reason != _FEEDBACK_REOPEN_REASON:
        raise RoadmapArtifactError(
            f"{where} field 'reason' must be "
            f"{_FEEDBACK_REOPEN_REASON!r}, got {reason!r}"
        )

    nonce = value["nonce"]
    if not isinstance(nonce, str) or _FEEDBACK_REOPEN_NONCE_RE.fullmatch(nonce) is None:
        raise RoadmapArtifactError(
            f"{where} field 'nonce' must be a 43-character URL-safe token, "
            f"got {nonce!r}"
        )

    recorded_at = value["recorded_at"]
    if (
        not isinstance(recorded_at, str)
        or _FEEDBACK_REOPEN_RECORDED_AT_RE.fullmatch(recorded_at) is None
    ):
        raise RoadmapArtifactError(
            f"{where} field 'recorded_at' must be a UTC RFC 3339 timestamp "
            f"with six fractional-second digits, got {recorded_at!r}"
        )
    try:
        datetime.strptime(recorded_at, "%Y-%m-%dT%H:%M:%S.%fZ")
    except ValueError as exc:
        raise RoadmapArtifactError(
            f"{where} field 'recorded_at' must be a UTC RFC 3339 timestamp "
            f"with six fractional-second digits, got {recorded_at!r}"
        ) from exc

    return FeedbackReopenRecord(
        selector=MappingProxyType(parsed_selector),
        reason=reason,
        nonce=nonce,
        recorded_at=recorded_at,
    )


def _parse_feedback_rows(frontmatter: dict[str, Any]) -> tuple[FeedbackRow, ...]:
    key = "feedback"
    rows: list[FeedbackRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        # ``state`` first: it decides whether a response is required.
        state = _coerce_feedback_state(
            _require_key(raw, "state", key=key, row_id=row_id), row_id=row_id
        )
        rows.append(
            FeedbackRow(
                id=row_id,
                target=_parse_feedback_target(raw, row_id=row_id),
                request=_row_text(raw, "request", key=key, row_id=row_id),
                state=state,
                proposed_response=_parse_proposed_response(
                    raw, row_id=row_id, state=state
                ),
                feedback_reopen=_parse_feedback_reopen_record(raw, row_id=row_id),
            )
        )
    return tuple(rows)


def _parse_removal_records(frontmatter: dict[str, Any]) -> tuple[RemovalRecord, ...]:
    key = "removals"
    records: list[RemovalRecord] = []
    for index, raw in _iter_rows(frontmatter, key):
        # Present-and-empty ``feedback_ids`` parses: "a removal cites at least
        # one feedback row" is the continuity gate's finding, reported against
        # the removal rather than raised with no row context.
        removed_id = _row_id(raw, key=key, index=index, field="removed_id")
        records.append(
            RemovalRecord(
                removed_id=removed_id,
                rationale=_row_text(raw, "rationale", key=key, row_id=removed_id),
                feedback_ids=_id_list(
                    raw, "feedback_ids", key=key, row_id=removed_id
                ),
            )
        )
    return tuple(records)


# --------------------------------------------------------------------------
# Parsing
# --------------------------------------------------------------------------


def parse_domain_artifact(text: str) -> DomainArtifact:
    """Parse ``01-domain.md`` text into typed rows plus its prose body."""
    frontmatter, body = _parse_frontmatter(text, artifact=DOMAIN_FILENAME)

    entities: list[EntityRow] = []
    for index, raw in _iter_rows(frontmatter, "entities"):
        row_id = _row_id(raw, key="entities", index=index)
        entities.append(
            EntityRow(
                id=row_id,
                name=_row_text(raw, "name", key="entities", row_id=row_id),
                fields=_parse_field_rows(raw, row_id=row_id),
            )
        )

    business_rules: list[BusinessRuleRow] = []
    for index, raw in _iter_rows(frontmatter, "business_rules"):
        row_id = _row_id(raw, key="business_rules", index=index)
        business_rules.append(
            BusinessRuleRow(
                id=row_id,
                statement=_row_text(
                    raw, "statement", key="business_rules", row_id=row_id
                ),
                entity_ids=_id_list(
                    raw, "entity_ids", key="business_rules", row_id=row_id
                ),
            )
        )

    workflows: list[WorkflowRow] = []
    for index, raw in _iter_rows(frontmatter, "workflows"):
        row_id = _row_id(raw, key="workflows", index=index)
        workflows.append(
            WorkflowRow(
                id=row_id,
                name=_row_text(raw, "name", key="workflows", row_id=row_id),
                entity_ids=_id_list(raw, "entity_ids", key="workflows", row_id=row_id),
            )
        )

    return DomainArtifact(
        entities=tuple(entities),
        business_rules=tuple(business_rules),
        workflows=tuple(workflows),
        decisions=_parse_decision_rows(frontmatter),
        body=body,
        feedback=_parse_feedback_rows(frontmatter),
        removals=_parse_removal_records(frontmatter),
    )


def parse_constraints_artifact(text: str) -> ConstraintsArtifact:
    """Parse ``02-constraints.md`` text into typed rows plus its prose body."""
    frontmatter, body = _parse_frontmatter(text, artifact=CONSTRAINTS_FILENAME)

    dispositions: list[AttributeDispositionRow] = []
    for index, raw in _iter_rows(frontmatter, "dispositions"):
        row_id = _row_id(raw, key="dispositions", index=index)
        dispositions.append(
            AttributeDispositionRow(
                id=row_id,
                attribute=_row_text(
                    raw, "attribute", key="dispositions", row_id=row_id
                ),
                disposition=_coerce_disposition(
                    _require_key(raw, "disposition", key="dispositions", row_id=row_id),
                    row_id=row_id,
                ),
            )
        )

    constraints: list[ConstraintRow] = []
    for index, raw in _iter_rows(frontmatter, "constraints"):
        row_id = _row_id(raw, key="constraints", index=index)
        constraints.append(
            ConstraintRow(
                id=row_id,
                statement=_row_text(raw, "statement", key="constraints", row_id=row_id),
                attribute=_row_text(raw, "attribute", key="constraints", row_id=row_id),
                anchor_ids=_id_list(
                    raw, "anchor_ids", key="constraints", row_id=row_id
                ),
            )
        )

    return ConstraintsArtifact(
        dispositions=tuple(dispositions),
        constraints=tuple(constraints),
        decisions=_parse_decision_rows(frontmatter),
        body=body,
        hosting=_parse_hosting_rows(frontmatter),
        stack=_parse_stack_rows(frontmatter),
        feedback=_parse_feedback_rows(frontmatter),
        removals=_parse_removal_records(frontmatter),
    )


def _parse_pattern_rows(
    frontmatter: dict[str, Any], key: str
) -> tuple[PatternRow, ...]:
    rows: list[PatternRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        rows.append(
            PatternRow(
                id=row_id,
                name=_row_text(raw, "name", key=key, row_id=row_id),
                statement=_row_text(raw, "statement", key=key, row_id=row_id),
            )
        )
    return tuple(rows)


def _parse_plan_rows(frontmatter: dict[str, Any]) -> tuple[PlanRow, ...]:
    key = "plans"
    rows: list[PlanRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        draft_seed_path = _row_text(
            raw, "draft_seed_path", key=key, row_id=row_id
        )
        _validate_draft_seed_path(draft_seed_path)
        rows.append(
            PlanRow(
                id=row_id,
                title=_row_text(raw, "title", key=key, row_id=row_id),
                disposition=_coerce_plan_disposition(
                    _require_key(raw, "disposition", key=key, row_id=row_id),
                    row_id=row_id,
                ),
                component_ids=_optional_id_list(
                    raw, "component_ids", key=key, row_id=row_id
                ),
                draft_seed_path=draft_seed_path,
                sizing_rationale=_row_text(
                    raw, "sizing_rationale", key=key, row_id=row_id
                ),
                intent=_optional_row_text(raw, "intent", key=key, row_id=row_id),
                non_goals=_optional_text_list(
                    raw, "non_goals", key=key, row_id=row_id
                ),
            )
        )
    return tuple(rows)


def _parse_ordering_entries(
    frontmatter: dict[str, Any],
) -> tuple[OrderingEntry, ...]:
    key = "ordering"
    entries: list[OrderingEntry] = []
    for index, raw in _iter_rows(frontmatter, key):
        plan_id = raw.get("plan_id")
        if not isinstance(plan_id, str) or not plan_id.strip():
            raise RoadmapArtifactError(
                f"'{key}' row {index} must carry a non-empty string 'plan_id', "
                f"got {plan_id!r}"
            )
        entries.append(
            OrderingEntry(
                plan_id=plan_id,
                depends_on=_optional_id_list(
                    raw, "depends_on", key=key, row_id=plan_id
                ),
                assumption_targets=_optional_id_list(
                    raw, "assumption_targets", key=key, row_id=plan_id
                ),
            )
        )
    return tuple(entries)


def _parse_assumption_rows(
    frontmatter: dict[str, Any],
) -> tuple[AssumptionRow, ...]:
    key = "assumptions"
    rows: list[AssumptionRow] = []
    for index, raw in _iter_rows(frontmatter, key):
        row_id = _row_id(raw, key=key, index=index)
        rows.append(
            AssumptionRow(
                id=row_id,
                statement=_row_text(raw, "statement", key=key, row_id=row_id),
                consuming_plan_ids=_id_list(
                    raw, "consuming_plan_ids", key=key, row_id=row_id
                ),
            )
        )
    return tuple(rows)


def parse_plans_artifact(text: str) -> PlansArtifact:
    """Parse ``04-roadmap.md`` text into typed rows plus its prose body."""
    frontmatter, body = _parse_frontmatter(text, artifact=PLANS_FILENAME)

    return PlansArtifact(
        plans=_parse_plan_rows(frontmatter),
        ordering=_parse_ordering_entries(frontmatter),
        assumptions=_parse_assumption_rows(frontmatter),
        decisions=_parse_decision_rows(frontmatter),
        body=body,
        feedback=_parse_feedback_rows(frontmatter),
        removals=_parse_removal_records(frontmatter),
    )


def parse_draft_seed_provenance(text: str) -> DraftSeedProvenance:
    """Parse draft-seed provenance frontmatter — shape only, no relation checks."""
    frontmatter, _body = _parse_frontmatter(text, artifact="draft seed")
    key = DRAFT_SEED_ROADMAP_COMPONENTS_KEY
    if key not in frontmatter:
        raise RoadmapArtifactError(
            f"draft seed frontmatter is missing required key '{key}'"
        )
    value = frontmatter[key]
    if not isinstance(value, list):
        raise RoadmapArtifactError(
            f"'{key}' must be a list of component ids, got {type(value).__name__}"
        )
    component_ids: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise RoadmapArtifactError(
                f"'{key}' entry {index} must be a non-empty string, got {item!r}"
            )
        component_ids.append(item)
    cross_cutting = frontmatter.get(DRAFT_SEED_CROSS_CUTTING_KEY, False)
    if not isinstance(cross_cutting, bool):
        raise RoadmapArtifactError(
            f"'{DRAFT_SEED_CROSS_CUTTING_KEY}' must be a boolean, "
            f"got {type(cross_cutting).__name__}"
        )
    return DraftSeedProvenance(
        roadmap_components=tuple(component_ids),
        cross_cutting=cross_cutting,
    )


def parse_components_artifact(text: str) -> ComponentsArtifact:
    """Parse ``03-components.md`` text into typed rows plus its prose body."""
    frontmatter, body = _parse_frontmatter(text, artifact=COMPONENTS_FILENAME)

    components: list[ComponentRow] = []
    for index, raw in _iter_rows(frontmatter, "components"):
        row_id = _row_id(raw, key="components", index=index)
        components.append(
            ComponentRow(
                id=row_id,
                name=_row_text(raw, "name", key="components", row_id=row_id),
                entity_ids=_id_list(
                    raw, "entity_ids", key="components", row_id=row_id
                ),
                pattern_ids=_id_list(
                    raw, "pattern_ids", key="components", row_id=row_id
                ),
                constraint_ids=_optional_id_list(
                    raw, "constraint_ids", key="components", row_id=row_id
                ),
                store_ids=_optional_id_list(
                    raw, "store_ids", key="components", row_id=row_id
                ),
            )
        )

    return ComponentsArtifact(
        system_patterns=_parse_pattern_rows(frontmatter, "system_patterns"),
        component_patterns=_parse_pattern_rows(frontmatter, "component_patterns"),
        components=tuple(components),
        decisions=_parse_decision_rows(frontmatter),
        body=body,
        stores=_parse_store_rows(frontmatter),
        feedback=_parse_feedback_rows(frontmatter),
        removals=_parse_removal_records(frontmatter),
    )


def load_domain_artifact(path: Path) -> DomainArtifact:
    """Read and parse ``01-domain.md``, naming ``path`` on any failure."""
    return _load(path, parse_domain_artifact)


def load_constraints_artifact(path: Path) -> ConstraintsArtifact:
    """Read and parse ``02-constraints.md``, naming ``path`` on any failure."""
    return _load(path, parse_constraints_artifact)


def load_components_artifact(path: Path) -> ComponentsArtifact:
    """Read and parse ``03-components.md``, naming ``path`` on any failure."""
    return _load(path, parse_components_artifact)


def load_plans_artifact(path: Path) -> PlansArtifact:
    """Read and parse ``04-roadmap.md``, naming ``path`` on any failure."""
    return _load(path, parse_plans_artifact)


_Artifact = TypeVar("_Artifact")


def _load(path: Path, parse: Callable[[str], _Artifact]) -> _Artifact:
    """Read ``path`` and parse it, binding the file to every failure — both a
    read error and a shape error carry the path a caller has to report."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise RoadmapArtifactError(
            f"roadmap artifact could not be read: {path} ({exc})", path=path
        ) from exc
    try:
        return parse(text)
    except RoadmapArtifactError as exc:
        raise RoadmapArtifactError(f"{path}: {exc}", path=path) from exc


# --------------------------------------------------------------------------
# Rendering
# --------------------------------------------------------------------------


# The reviewer's key, rendered above ``feedback:`` whenever the collection is
# present. It sits in the artifact rather than the docs because the artifact is
# the review surface: the reviewer is already looking at ``state:`` when they
# need to know what they may set it to, and a comment is the only annotation a
# YAML frontmatter carries. Comments are not parsed, so a revision re-renders
# this from scratch every time and it can neither accumulate nor drift.
_FEEDBACK_KEY_COMMENT_PREFIX = """\
# Your review. Set `state` on a row to one of:
#   open             send this request back to the model on the next run
#   awaiting-review  the model has answered — read its `proposed_response`
#   deferred         park it: kept in this file, no longer sent
# Close a row by deleting it; git keeps the record. If a response asks you a
# question, edit that row's `request` to answer it, then set `state: open`.
"""

_FEEDBACK_RESPONSE_LIMITS_COMMENT = f"""\
# A stage reply handles at most {HARD_MAX_ACTIVE_FEEDBACK_ITEMS} open items, {HARD_MAX_RESPONSE_BYTES // 1024} KiB total, and {HARD_MAX_PROSE_AMENDMENT_BYTES // 1024} KiB per
# row-prose amendment, with one material change per item. Split larger feedback;
# this project may set stricter numeric caps.
"""

_FEEDBACK_KEY_COMMENT = (
    _FEEDBACK_KEY_COMMENT_PREFIX
    + """\
# Only you move a row out of `awaiting-review`.
"""
    + _FEEDBACK_RESPONSE_LIMITS_COMMENT
)

_FEEDBACK_REOPEN_KEY_COMMENT = (
    _FEEDBACK_KEY_COMMENT_PREFIX
    + """\
# Ordinary close, defer, and reopen actions are yours in your editor. The sole
# tool exception is the explicitly confirmed operator `--reopen-feedback` action;
# a stage reply never reopens a row.
"""
    + _FEEDBACK_RESPONSE_LIMITS_COMMENT
)

# Byte-stable on purpose: these key texts are stored in published versions and
# decision settlement refuses an artifact that does not re-render to its stored
# bytes, so rewording them (including their retired-flag mentions) needs a
# render-version decision, not a text edit.
#
# The other half of the key, for an artifact carrying no feedback at all. The
# reviewer who wants to *start* the conversation needs the shape, and
# ``_FEEDBACK_KEY_COMMENT`` cannot give it to them: it is anchored to a
# ``feedback:`` line that does not exist yet, so before this block the channel
# was invisible until you had already used it. Rendered at the end of the
# frontmatter because that is where ``feedback:`` itself would go —
# ``REVIEW_ROW_KEYS`` sort after the design collections.
#
# It says the model never writes these rows for a second reason beyond being
# true: a revision is handed the predecessor's raw file text, comments
# included, so this block is in the model's context on every re-entry over an
# unreviewed artifact. ``_authored_review_rows`` refuses an invented row, but
# that refusal costs an attempt on a stage whose budget is tight, so the
# cheaper guard is to not tempt it.
_NO_FEEDBACK_KEY_COMMENT = f"""\
# No review on this artifact yet. To ask for a change, say it here rather than
# making a direct edit to the rows: uncomment the lines from `feedback:` down, fill
# them in, and re-run this artifact's own stage with --from-stage. The model
# answers in `proposed_response`, leaves your `request` untouched, and never
# writes one of these rows itself.
# A stage reply handles at most {HARD_MAX_ACTIVE_FEEDBACK_ITEMS} open items, {HARD_MAX_RESPONSE_BYTES // 1024} KiB total, and {HARD_MAX_PROSE_AMENDMENT_BYTES // 1024} KiB per
# row-prose amendment, with one material change per item. Split larger feedback;
# this project may set stricter numeric caps.
# feedback:
# - id: fb-1
#   target:
#     kind: row              # or `artifact` for the whole file, and no row_id
#     row_id: <the id this request is about>
#   request: >-
#     <what you want changed, in your own words>
#   state: open              # the only state that is sent to the model
"""


def _render(frontmatter: dict[str, Any], body: str) -> str:
    dumped = yaml.safe_dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=_CANONICAL_YAML_WIDTH,
    )
    if "feedback" in frontmatter:
        feedback = frontmatter["feedback"]
        comment = (
            _FEEDBACK_REOPEN_KEY_COMMENT
            if any("feedback_reopen" in row for row in feedback)
            else _FEEDBACK_KEY_COMMENT
        )
        dumped = dumped.replace("\nfeedback:", f"\n{comment}feedback:", 1)
    else:
        dumped = f"{dumped}{_NO_FEEDBACK_KEY_COMMENT}"
    return f"{_FENCE}\n{dumped}{_FENCE}\n{body}"


def _field_mapping(row: FieldRow) -> dict[str, Any]:
    # ``entity_id`` is omitted rather than rendered null when absent, so a
    # non-reference field round-trips to frontmatter that carries no key the
    # shape contract says it must not have.
    mapping: dict[str, Any] = {"name": row.name, "type": row.type.value}
    if row.entity_id is not None:
        mapping["entity_id"] = row.entity_id
    return mapping


def _decision_mapping(row: DecisionRow) -> dict[str, Any]:
    # ``.value`` rather than the member: PyYAML's SafeDumper has no
    # representer for an Enum subclass and raises even when it inherits str.
    mapping: dict[str, Any] = {"id": row.id, "chosen_option": row.chosen_option}
    if row.source is None:
        mapping["rejected_alternatives"] = [
            {"option": alternative.option, "reason": alternative.reason}
            for alternative in row.rejected_alternatives
        ]
        mapping["rationale"] = row.rationale
    else:
        mapping["source"] = row.source
        if row.rejected_alternatives:
            mapping["rejected_alternatives"] = [
                {"option": alternative.option, "reason": alternative.reason}
                for alternative in row.rejected_alternatives
            ]
        if row.rationale is not None:
            mapping["rationale"] = row.rationale
    mapping["anchor"] = row.anchor
    mapping["status"] = row.status.value
    return mapping


def _feedback_mapping(row: FeedbackRow) -> dict[str, Any]:
    # ``.value`` rather than the member, for the reason ``_decision_mapping``
    # gives; the two optional keys are omitted rather than rendered null, so a
    # rendered row carries no key the shape contract forbids it.
    target: dict[str, Any] = {"kind": row.target.kind.value}
    if row.target.row_id is not None:
        target["row_id"] = row.target.row_id
    mapping: dict[str, Any] = {
        "id": row.id,
        "target": target,
        "request": row.request,
        "state": row.state.value,
    }
    if row.proposed_response is not None:
        mapping["proposed_response"] = row.proposed_response
    if row.feedback_reopen is not None:
        mapping["feedback_reopen"] = {
            "selector": dict(row.feedback_reopen.selector),
            "reason": row.feedback_reopen.reason,
            "nonce": row.feedback_reopen.nonce,
            "recorded_at": row.feedback_reopen.recorded_at,
        }
    return mapping


def _removal_mapping(record: RemovalRecord) -> dict[str, Any]:
    return {
        "removed_id": record.removed_id,
        "rationale": record.rationale,
        "feedback_ids": list(record.feedback_ids),
    }


def _pattern_mapping(row: PatternRow) -> dict[str, Any]:
    return {"id": row.id, "name": row.name, "statement": row.statement}


def _plan_mapping(row: PlanRow) -> dict[str, Any]:
    mapping: dict[str, Any] = {
        "id": row.id,
        "title": row.title,
        "disposition": row.disposition.value,
        "draft_seed_path": row.draft_seed_path,
        "sizing_rationale": row.sizing_rationale,
    }
    if row.component_ids:
        mapping["component_ids"] = list(row.component_ids)
    if row.intent:
        mapping["intent"] = row.intent
    if row.non_goals:
        mapping["non_goals"] = list(row.non_goals)
    return mapping


def _ordering_mapping(entry: OrderingEntry) -> dict[str, Any]:
    mapping: dict[str, Any] = {"plan_id": entry.plan_id}
    if entry.depends_on:
        mapping["depends_on"] = list(entry.depends_on)
    if entry.assumption_targets:
        mapping["assumption_targets"] = list(entry.assumption_targets)
    return mapping


def _assumption_mapping(row: AssumptionRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "statement": row.statement,
        "consuming_plan_ids": list(row.consuming_plan_ids),
    }


def _component_mapping(row: ComponentRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "name": row.name,
        "entity_ids": list(row.entity_ids),
        "pattern_ids": list(row.pattern_ids),
        "constraint_ids": list(row.constraint_ids),
        "store_ids": list(row.store_ids),
    }


def _store_mapping(row: StoreRow) -> dict[str, Any]:
    mapping = {
        "id": row.id,
        "category": row.category,
        "sharing": row.sharing,
    }
    if row.product is not None:
        mapping["product"] = row.product
    if row.description is not None:
        mapping["description"] = row.description
    if row.research_disclosure is not None:
        mapping["research_disclosure"] = row.research_disclosure.value
    return mapping


_REVIEW_ROW_MAPPINGS = (_feedback_mapping, _removal_mapping)


def _review_mappings(artifact: Any) -> dict[str, Any]:
    """The review collections' frontmatter, in ``REVIEW_ROW_KEYS`` order and
    **omitted entirely when empty**.

    An always-emitted ``feedback: []`` would put a new key in every first-run
    artifact; omitting it is what keeps an unreviewed artifact rendering exactly
    its design keys. The wire names double as the dataclass field names, so the
    constant drives the render rather than being a hand-copy of it.
    """
    rendered: dict[str, Any] = {}
    for key, to_mapping in zip(REVIEW_ROW_KEYS, _REVIEW_ROW_MAPPINGS):
        rows = getattr(artifact, key)
        if rows:
            rendered[key] = [to_mapping(row) for row in rows]
    return rendered


def render_domain_artifact(artifact: DomainArtifact) -> str:
    """Render ``01-domain.md`` text that :func:`parse_domain_artifact` reads
    back as an equal artifact."""
    return _render(
        {
            "entities": [
                {
                    "id": row.id,
                    "name": row.name,
                    "fields": [_field_mapping(field) for field in row.fields],
                }
                for row in artifact.entities
            ],
            "business_rules": [
                {
                    "id": row.id,
                    "statement": row.statement,
                    "entity_ids": list(row.entity_ids),
                }
                for row in artifact.business_rules
            ],
            "workflows": [
                {
                    "id": row.id,
                    "name": row.name,
                    "entity_ids": list(row.entity_ids),
                }
                for row in artifact.workflows
            ],
            "decisions": [_decision_mapping(row) for row in artifact.decisions],
            **_review_mappings(artifact),
        },
        artifact.body,
    )


def render_constraints_artifact(artifact: ConstraintsArtifact) -> str:
    """Render ``02-constraints.md`` text that
    :func:`parse_constraints_artifact` reads back as an equal artifact."""
    return _render(
        {
            "hosting": [
                {
                    "id": row.id,
                    "facet": row.facet,
                    "value": row.value,
                    **({"product": row.product} if row.product is not None else {}),
                    **({"description": row.description} if row.description is not None else {}),
                    **(
                        {"research_disclosure": row.research_disclosure.value}
                        if row.research_disclosure is not None
                        else {}
                    ),
                }
                for row in artifact.hosting
            ],
            # `is not None`, never truthiness: `stack: []` is recorded-and-empty.
            **(
                {
                    "stack": [
                        {
                            "id": row.id,
                            "concern": row.concern,
                            **({"choice": row.choice} if row.choice is not None else {}),
                            **({"open": True} if row.open else {}),
                        }
                        for row in artifact.stack
                    ]
                }
                if artifact.stack is not None
                else {}
            ),
            "dispositions": [
                {
                    "id": row.id,
                    "attribute": row.attribute,
                    "disposition": row.disposition.value,
                }
                for row in artifact.dispositions
            ],
            "constraints": [
                {
                    "id": row.id,
                    "statement": row.statement,
                    "attribute": row.attribute,
                    "anchor_ids": list(row.anchor_ids),
                }
                for row in artifact.constraints
            ],
            "decisions": [_decision_mapping(row) for row in artifact.decisions],
            **_review_mappings(artifact),
        },
        artifact.body,
    )


def render_draft_seed_provenance(provenance: DraftSeedProvenance) -> str:
    """Render draft-seed provenance as a frontmatter block plus empty body."""
    frontmatter: dict[str, Any] = {
        DRAFT_SEED_ROADMAP_COMPONENTS_KEY: list(provenance.roadmap_components),
    }
    if provenance.cross_cutting:
        frontmatter[DRAFT_SEED_CROSS_CUTTING_KEY] = True
    dumped = yaml.safe_dump(
        frontmatter, default_flow_style=False, sort_keys=False, allow_unicode=True
    )
    return f"{_FENCE}\n{dumped}{_FENCE}\n"


def render_plans_artifact(artifact: PlansArtifact) -> str:
    """Render ``04-roadmap.md`` text that :func:`parse_plans_artifact` reads back."""
    return _render(
        {
            "plans": [_plan_mapping(row) for row in artifact.plans],
            "ordering": [_ordering_mapping(entry) for entry in artifact.ordering],
            "assumptions": [_assumption_mapping(row) for row in artifact.assumptions],
            "decisions": [_decision_mapping(row) for row in artifact.decisions],
            **_review_mappings(artifact),
        },
        artifact.body,
    )


def render_components_artifact(artifact: ComponentsArtifact) -> str:
    """Render ``03-components.md`` text that
    :func:`parse_components_artifact` reads back as an equal artifact."""
    return _render(
        {
            "system_patterns": [
                _pattern_mapping(row) for row in artifact.system_patterns
            ],
            "component_patterns": [
                _pattern_mapping(row) for row in artifact.component_patterns
            ],
            "stores": [_store_mapping(row) for row in artifact.stores],
            "components": [_component_mapping(row) for row in artifact.components],
            "decisions": [_decision_mapping(row) for row in artifact.decisions],
            **_review_mappings(artifact),
        },
        artifact.body,
    )
