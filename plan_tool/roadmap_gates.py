"""Roadmap response gates: the relation checks a staged artifact must pass.

``plan_tool.roadmap_artifacts`` decides whether a roadmap artifact has the
right *shape*, and deliberately accepts nonsense relations — a workflow naming
an entity nothing defines, two rows sharing an id, a constraints artifact
missing half the quality attributes, a components artifact citing undefined
pattern ids. The shared gates plus eight components traceability gates, the
plans review-context gate, and five plans relation gates decide
whether those relations hold, so deterministic code rather than the model says
whether a stage's output is good enough to hand to the next stage. Each stage
runs its own gate set — :func:`run_domain_gates`, :func:`run_constraints_gates`,
:func:`run_components_gates`, :func:`run_plans_gates` — over the same
:class:`ArtifactEnvelope` type.

**Violations are retry text, not a report.** Each message is written to be
quoted straight into the retried stage prompt, so it names the offending row's
id, the artifact that row lives in, and the correction to make. Ids are the
only anchor: the artifact is rewritten on every retry, so a line number is
stale before it is read. Nothing carries a severity — every violation blocks
its stage.

**Each gate judges the artifact under check.** Upstream artifacts in the
envelope are read to *resolve* ids, never to widen what is judged, because a
violation the retried stage cannot rewrite would spin the retry loop.
:func:`check_duplicate_row_ids` is the one exception, and only because its rule
is inherently cross-artifact: an id colliding across two files is invisible
from either file alone, and the retried stage can still rename its own side.
The three **revision** gates read ``ArtifactEnvelope.predecessor`` the same
way — to resolve what a re-run replaces, never to judge it — and every rule
derived from it is inert when the envelope carries none, so a first run and a
below-stage re-gating pass behave as they do without one.

A **stdlib-plus-leaves leaf**: the only first-party imports are
``plan_tool.roadmap_artifacts`` and ``plan_tool.scope_fence`` (itself
stdlib-only, so this adds no cycle risk). Nothing here reads a file, asks
Claude anything, or decides what a violation costs — the orchestrator above
owns reading, retrying, and halting.

Not to be confused with ``plan_tool.gates``, which proposes ``gate:`` shell
commands for a plan's steps. Neither module imports the other.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence, Union

from plan_tool.scope_fence import (
    _fenced_code_spans,
    _is_placeholder_section,
    _strip_frontmatter,
    extract_h2_sections,
)

from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DRAFT_SEED_CROSS_CUTTING_KEY,
    DRAFT_SEED_ROADMAP_COMPONENTS_KEY,
    DOMAIN_FILENAME,
    PLAN_ID_SLUG_RE,
    PLANS_FILENAME,
    QUALITY_ATTRIBUTES,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
    ConstraintsArtifact,
    DecisionStatus,
    DomainArtifact,
    FeedbackState,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HOSTING_FACETS,
    STACK_CONCERNS,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    RoadmapArtifactError,
    components_design_rows,
    parse_draft_seed_provenance,
    plans_design_rows,
)

# --------------------------------------------------------------------------
# The violation type
# --------------------------------------------------------------------------

# One token per defect, so a consumer can group violations without matching on
# prose. ``ROADMAP_FORMAT.md`` documents each beside the rule it enforces.
VIOLATION_UNDEFINED_ENTITY_REFERENCE = "undefined-entity-reference"
VIOLATION_NO_ENTITY_REFERENCE = "no-entity-reference"
VIOLATION_ENTITY_WITHOUT_FIELDS = "entity-without-fields"
VIOLATION_DUPLICATE_FIELD_NAME = "duplicate-field-name"
VIOLATION_FIELD_REFERENCE_TARGET = "field-reference-target"
VIOLATION_DUPLICATE_ROW_ID = "duplicate-row-id"
VIOLATION_UNDISPOSED_ATTRIBUTE = "undisposed-attribute"
VIOLATION_REDUNDANT_DISPOSITION = "redundant-disposition"
VIOLATION_UNKNOWN_DISPOSED_ATTRIBUTE = "unknown-disposed-attribute"
VIOLATION_UNKNOWN_CONSTRAINT_ATTRIBUTE = "unknown-constraint-attribute"
VIOLATION_CONSTRAINT_ON_NOT_LOAD_BEARING = "constraint-on-not-load-bearing-attribute"
VIOLATION_MISSING_HOSTING_FACET = "missing-hosting-facet"
VIOLATION_REDUNDANT_HOSTING_FACET = "redundant-hosting-facet"
VIOLATION_UNKNOWN_HOSTING_FACET = "unknown-hosting-facet"
VIOLATION_UNKNOWN_HOSTING_VALUE = "unknown-hosting-value"
VIOLATION_HOSTING_TOPOLOGY_COHERENCE = "hosting-topology-coherence"
VIOLATION_MISSING_STACK_CONCERN = "missing-stack-concern"
VIOLATION_UNKNOWN_STACK_CONCERN = "unknown-stack-concern"
VIOLATION_DUPLICATE_STACK_ID = "duplicate-stack-id"
VIOLATION_DUPLICATE_STACK_CONCERN = "duplicate-stack-concern"
VIOLATION_STACK_ROW_STATE = "stack-row-state"
VIOLATION_UNANCHORED_CONSTRAINT = "unanchored-constraint"
VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR = "unresolved-constraint-anchor"
VIOLATION_NO_REJECTED_ALTERNATIVE = "no-rejected-alternative"
VIOLATION_UNREASONED_ALTERNATIVE = "unreasoned-alternative"
VIOLATION_BLANK_RATIONALE = "blank-rationale"
VIOLATION_UNRESOLVED_DECISION_ANCHOR = "unresolved-decision-anchor"
VIOLATION_INHERITED_DECISION_UNCONFIRMED = "inherited-decision-unconfirmed"
VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE = "inherited-decision-unknown-source"
VIOLATION_INHERITED_DECISION_AMBIGUOUS_SOURCE = "inherited-decision-ambiguous-source"
VIOLATION_INHERITED_DECISION_WRONG_ARTIFACT = "inherited-decision-wrong-artifact"
VIOLATION_INHERITED_DECISION_NONLOCAL_ANCHOR = "inherited-decision-nonlocal-anchor"
VIOLATION_MISSING_INHERITED_DECISION = "missing-inherited-decision"
VIOLATION_DUPLICATE_INHERITED_DECISION = "duplicate-inherited-decision"
VIOLATION_ALTERED_INHERITED_DECISION = "altered-inherited-decision"
VIOLATION_EMPTY_ARTIFACT = "empty-artifact"
VIOLATION_UNDESCRIBED_ROW = "undescribed-row"
# The revision gates' defects: what a re-run may not do to the version it
# replaces.
VIOLATION_DROPPED_DESIGN_ROW = "dropped-design-row"
VIOLATION_BLANK_REMOVAL_RATIONALE = "blank-removal-rationale"
VIOLATION_UNCITED_REMOVAL = "uncited-removal"
VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW = "removal-names-a-present-row"
VIOLATION_UNRESOLVED_REMOVAL_CITATION = "unresolved-removal-citation"
VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW = "removal-without-a-predecessor-row"
VIOLATION_DUPLICATE_FEEDBACK_ID = "duplicate-feedback-id"
VIOLATION_DROPPED_FEEDBACK = "dropped-feedback"
VIOLATION_ALTERED_FEEDBACK_SOURCE = "altered-feedback-source"
VIOLATION_DISALLOWED_FEEDBACK_STATE = "disallowed-feedback-state"
VIOLATION_ALTERED_CARRIED_RESPONSE = "altered-carried-response"
VIOLATION_UNRESOLVED_FEEDBACK_TARGET = "unresolved-feedback-target"
VIOLATION_DROPPED_SETTLED_DECISION = "dropped-settled-decision"
VIOLATION_ALTERED_SETTLED_DECISION = "altered-settled-decision"
# Components traceability: entity coverage, pattern presence, constraint resolution,
# prioritized-constraint discharge, and concrete store references.
VIOLATION_UNCOVERED_ENTITY = "uncovered-entity"
VIOLATION_NO_PATTERN_REFERENCE = "no-pattern-reference"
VIOLATION_UNDEFINED_PATTERN_REFERENCE = "undefined-pattern-reference"
VIOLATION_EMPTY_PATTERN_COLLECTION = "empty-pattern-collection"
VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE = "undefined-constraint-reference"
VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT = "undischarged-prioritized-constraint"
VIOLATION_NO_STORE_REFERENCE = "no-store-reference"
VIOLATION_DUPLICATE_STORE_REFERENCE = "duplicate-store-reference"
VIOLATION_UNDEFINED_STORE_REFERENCE = "undefined-store-reference"
VIOLATION_SHARED_IN_PROCESS_STORE = "shared-in-process-store"
VIOLATION_UNCOVERED_STORE = "uncovered-store"
VIOLATION_UNKNOWN_STORE_CATEGORY = "unknown-store-category"
VIOLATION_UNKNOWN_STORE_SHARING = "unknown-store-sharing"
# Plans traceability: review context, component coverage, draft-path collision,
# ordering, slug shape, and assumption consumers (step 3).
VIOLATION_BLANK_PLAN_INTENT = "blank-plan-intent"
VIOLATION_NO_PLAN_NON_GOALS = "no-plan-non-goals"
VIOLATION_NO_COMPONENT_REFERENCE = "no-component-reference"
VIOLATION_UNDEFINED_COMPONENT_REFERENCE = "undefined-component-reference"
VIOLATION_UNCOVERED_COMPONENT = "uncovered-component"
VIOLATION_DRAFT_SEED_PROVENANCE = "draft-seed-provenance"
VIOLATION_DRAFT_SEED_UNMATCHED_FENCE = "draft-seed-unmatched-fence"
VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE = "undefined-seed-component-reference"
VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE = "missing-draft-seed-artifact-reference"
VIOLATION_MISSING_DRAFT_SEED_RISKS = "missing-draft-seed-risks"
VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME = "duplicate-draft-seed-basename"
VIOLATION_INVALID_PLAN_ID_SLUG = "invalid-plan-id-slug"
VIOLATION_ORDERING_PLAN_ID_DUPLICATE = "ordering-plan-id-duplicate"
VIOLATION_MISSING_ORDERING_PLAN_ID = "missing-ordering-plan-id"
VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE = "undefined-ordering-plan-reference"
# Closed ``Violation.reference_defect`` values for that kind: the referenced
# plan id has no plan row; it is defined but not earlier in ``ordering``; or it
# is not earlier because it already reaches this plan through ordering references.
ORDERING_REFERENCE_ABSENT = "absent"
ORDERING_REFERENCE_NOT_EARLIER = "not-earlier"
ORDERING_REFERENCE_CYCLE = "cycle"
VIOLATION_NO_ASSUMPTION_CONSUMER = "no-assumption-consumer"
VIOLATION_UNDEFINED_ASSUMPTION_PLAN_REFERENCE = "undefined-assumption-plan-reference"

# Narrative-review defect classes. See ROADMAP_FORMAT.md § "Narrative review evidence".
NARRATIVE_REMOVED_ID_IN_LIVE_PROSE = "removed-id-in-live-prose"
NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE = "removed-id-ambiguous-reference"
NARRATIVE_UNCLOSED_FENCE_UNREAD = "unclosed-fence-unread"
# Each marker stands alone on its own line; the spelling is the contract.
HISTORY_MARKER_START = "<!-- roadmap:history:start -->"
HISTORY_MARKER_END = "<!-- roadmap:history:end -->"
_NARRATIVE_EXCERPT_LIMIT = 160


@dataclass(frozen=True)
class Violation:
    """One relation a roadmap artifact breaks.

    Modeled on ``jira_grade.JiraGradeFinding`` minus its ``blocking`` flag:
    every violation here blocks a stage and feeds its retry, so a severity
    axis would be a field nobody reads and an invitation to invent an
    advisory tier. ``artifact`` is a filename constant, never a path —
    enough for a message to say which file to fix. ``row_id`` is ``None``
    only when the defect is an *absent* row, and the message then names the
    identifier that should have been there instead — an undisposed quality
    attribute has no row id at all. A row a revision *dropped* and a removal
    record's ``removed_id`` are real ids, so both populate it.
    ``referenced_id`` / ``reference_defect`` carry an ordering reference's
    target and closed defect, so a consumer that may not echo ``message`` can
    still tell the cases apart.
    """

    kind: str
    artifact: str
    row_id: Optional[str]
    message: str
    referenced_id: Optional[str] = None
    reference_defect: Optional[str] = None


StageArtifact = Union[DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact]


# Coarse persistence vocabulary. Products remain free text so these terms stay
# portable across vendors and deployment choices.
STORE_CATEGORIES: tuple[str, ...] = (
    "in-process",
    "relational",
    "document",
    "key-value",
    "object",
)
STORE_SHARING_MODELS: tuple[str, ...] = ("silo", "pool", "bridge")


@dataclass(frozen=True)
class ArtifactEnvelope:
    """The roadmap artifacts parsed so far — the one under check comes last.

    Every stage gate set takes this one type, so ``roadmap.py``'s stage table can
    hold a gate set as a value instead of branching on which artifact a stage
    judges. ``domain`` is always present: the domain stage judges it, and later
    stages resolve anchors against it. ``constraints``, ``components``, and
    ``plans`` fill in as upstream artifacts when those stages run.

    ``predecessor`` is the prior version of :attr:`artifact_under_check` — a
    ``DomainArtifact``, ``ConstraintsArtifact``, ``ComponentsArtifact``, or
    ``PlansArtifact`` depending on which stage is running. It defaults to
    ``None``, which is what lets ``roadmap.py`` fill only the ``artifact_key``-
    named slots and what makes a first run inert to every revision rule. That
    the two types agree is the caller's to arrange, not this module's to enforce:
    the pair is built from one stage row, and a ``__post_init__`` raise would be
    the first exception this violations-only layer ever threw.
    """

    domain: DomainArtifact
    constraints: Optional[ConstraintsArtifact] = None
    components: Optional[ComponentsArtifact] = None
    plans: Optional[PlansArtifact] = None
    predecessor: Optional[StageArtifact] = None
    # The source reader's ``CarriedDecisions`` is deliberately duck-typed here:
    # gates remain directly above the artifact leaf and receive its parsed facts.
    carried_decisions: Optional[object] = None

    @property
    def artifact_under_check(self) -> StageArtifact:
        """The artifact the stage just wrote — the envelope's last filled slot."""
        if self.plans is not None:
            return self.plans
        if self.components is not None:
            return self.components
        if self.constraints is not None:
            return self.constraints
        return self.domain

    @property
    def filename_under_check(self) -> str:
        """The filename of :attr:`artifact_under_check`."""
        if self.plans is not None:
            return PLANS_FILENAME
        if self.components is not None:
            return COMPONENTS_FILENAME
        if self.constraints is not None:
            return CONSTRAINTS_FILENAME
        return DOMAIN_FILENAME


Gate = Callable[[ArtifactEnvelope], "list[Violation]"]


# Hosting values are gate-owned rather than parser-owned: malformed row shapes
# fail parsing, while a concrete but unrecognized value receives retry text.
HOSTING_FACET_VALUES: dict[str, tuple[str, ...]] = {
    "compute": ("per-request", "managed-containers", "long-lived", "mixed"),
    "model": ("self-hosted", "silo", "pool", "bridge"),
    "topology": ("single-unit", "multi-unit"),
}


# --------------------------------------------------------------------------
# Row enumeration
# --------------------------------------------------------------------------
#
# Row kinds in render order, each paired with the label its messages use.
# Spelled out rather than derived from ``DOMAIN_ROW_KEYS`` /
# ``CONSTRAINTS_ROW_KEYS``: those are wire names, free to diverge from the
# dataclass fields.


def _domain_rows(artifact: DomainArtifact) -> tuple[tuple[str, str], ...]:
    """Every domain row as ``(kind label, id)``."""
    return (
        *(("entity", row.id) for row in artifact.entities),
        *(("business rule", row.id) for row in artifact.business_rules),
        *(("workflow", row.id) for row in artifact.workflows),
        *(("decision", row.id) for row in artifact.decisions),
    )


def _constraints_rows(artifact: ConstraintsArtifact) -> tuple[tuple[str, str], ...]:
    """Every constraints row as ``(kind label, id)``."""
    return (
        *(("disposition", row.id) for row in artifact.dispositions),
        *(("constraint", row.id) for row in artifact.constraints),
        *(("decision", row.id) for row in artifact.decisions),
    )


def _stack_identity_rows(
    artifact: ConstraintsArtifact,
) -> tuple[tuple[str, str], ...]:
    """Stack ids; ``stack is None`` (not recorded) carries none. Deliberately
    not in ``_constraints_rows``, which feeds ``design_row_ids`` and the
    prose-inventory gate."""
    return tuple(("stack", row.id) for row in artifact.stack or ())


def _constraints_identity_rows(
    artifact: ConstraintsArtifact,
) -> tuple[tuple[str, str], ...]:
    """Constraint rows plus hosting and stack ids for identity-sensitive gates."""
    return (
        *_constraints_rows(artifact),
        *(("hosting", row.id) for row in artifact.hosting),
        *_stack_identity_rows(artifact),
    )


def _components_identity_rows(
    artifact: ComponentsArtifact,
) -> tuple[tuple[str, str], ...]:
    """Component rows plus store ids for identity-sensitive gates."""
    return (
        *components_design_rows(artifact),
        *(("store", row.id) for row in artifact.stores),
    )


def _rows_of(artifact: StageArtifact) -> tuple[tuple[str, str], ...]:
    if isinstance(artifact, DomainArtifact):
        return _domain_rows(artifact)
    if isinstance(artifact, ConstraintsArtifact):
        return _constraints_rows(artifact)
    if isinstance(artifact, ComponentsArtifact):
        return components_design_rows(artifact)
    return plans_design_rows(artifact)


def _feedback_target_rows(artifact: StageArtifact) -> tuple[tuple[str, str], ...]:
    """Return every predecessor row a stage feedback request may name."""
    if isinstance(artifact, ConstraintsArtifact):
        return _constraints_identity_rows(artifact)
    if isinstance(artifact, ComponentsArtifact):
        return _components_identity_rows(artifact)
    return _rows_of(artifact)


def feedback_target_ids(artifact: StageArtifact) -> set[str]:
    """Return ids valid for stage feedback, not local selection."""
    return {row_id for _label, row_id in _feedback_target_rows(artifact)}


def _continuity_rows(artifact: StageArtifact) -> tuple[tuple[str, str], ...]:
    """Return the removal identities that continuity preserves across runs."""
    return _feedback_target_rows(artifact)


def design_row_ids(artifact: StageArtifact) -> set[str]:
    """Return the narrower local presentation-selector row ids."""
    return {row_id for _label, row_id in _rows_of(artifact)}


def _envelope_rows(
    envelope: ArtifactEnvelope,
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """``(filename, rows)`` for every artifact the envelope carries, upstream
    first."""
    carried: list[tuple[str, tuple[tuple[str, str], ...]]] = [
        (DOMAIN_FILENAME, _domain_rows(envelope.domain))
    ]
    if envelope.constraints is not None:
        carried.append(
            (
                CONSTRAINTS_FILENAME,
                (
                    *_constraints_rows(envelope.constraints),
                    *_stack_identity_rows(envelope.constraints),
                ),
            )
        )
    if envelope.components is not None:
        carried.append((COMPONENTS_FILENAME, _rows_of(envelope.components)))
    if envelope.plans is not None:
        carried.append((PLANS_FILENAME, _rows_of(envelope.plans)))
    return tuple(carried)


def _envelope_identity_rows(
    envelope: ArtifactEnvelope,
) -> tuple[tuple[str, tuple[tuple[str, str], ...]], ...]:
    """Rows participating in global id uniqueness, upstream first."""
    carried: list[tuple[str, tuple[tuple[str, str], ...]]] = [
        (DOMAIN_FILENAME, _domain_rows(envelope.domain))
    ]
    if envelope.constraints is not None:
        carried.append(
            (
                CONSTRAINTS_FILENAME,
                _constraints_identity_rows(envelope.constraints),
            )
        )
    if envelope.components is not None:
        carried.append(
            (
                COMPONENTS_FILENAME,
                _components_identity_rows(envelope.components),
            )
        )
    if envelope.plans is not None:
        carried.append((PLANS_FILENAME, _rows_of(envelope.plans)))
    return tuple(carried)


def _entity_referencing_rows(
    artifact: DomainArtifact,
) -> tuple[tuple[str, str, tuple[str, ...]], ...]:
    """Every row obliged to name an entity, as ``(kind label, id, entity
    ids)``."""
    return (
        *(("business rule", row.id, row.entity_ids) for row in artifact.business_rules),
        *(("workflow", row.id, row.entity_ids) for row in artifact.workflows),
    )


def _attribute_names() -> str:
    return ", ".join(QUALITY_ATTRIBUTES)


def _field_type_names() -> str:
    return ", ".join(member.value for member in FieldType)


def _or_list(items: Sequence[str]) -> str:
    """``a`` / ``a or b`` / ``a, b, or c``.

    A message that builds its noun phrase from whatever rows an envelope holds
    still has to read as a sentence — it is quoted into a retried prompt, not
    into a report.
    """
    if len(items) < 3:
        return " or ".join(items)
    return f"{', '.join(items[:-1])}, or {items[-1]}"


def _article(noun: str) -> str:
    """``a``/``an`` for a noun phrase assembled at runtime."""
    return "an" if noun[:1].lower() in "aeiou" else "a"


def _kind_labels(rows: Sequence[tuple[str, str]]) -> tuple[str, ...]:
    """The row kinds ``rows`` holds, deduplicated in first-seen order.

    First-seen, never sorted: the row enumerators emit render order, and a
    message listing an artifact's kinds reads best in the order the artifact
    declares them.
    """
    seen: list[str] = []
    for label, _row_id in rows:
        if label not in seen:
            seen.append(label)
    return tuple(seen)


# --------------------------------------------------------------------------
# The gates
# --------------------------------------------------------------------------
#
# Domain and constraints stages share entity-field, reference, totality, and
# anchor checks; components adds eight traceability gates: entity, pattern,
# constraint, and store reference/coverage/value checks.


def check_entity_fields(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every entity holds at least one field, field names are unique within an
    entity, and ``entity_id`` is present exactly on ``reference`` fields.

    The presence half is the whole point of the field list: an entity with no
    fields is an anchor with no shape, which leaves every plan derived from it
    re-inventing what the thing holds. The gate judges *presence and shape*
    only — whether the fields are the right ones is not observable here, and
    deliberately unchecked.
    """
    violations: list[Violation] = []
    for entity in envelope.domain.entities:
        if not entity.fields:
            violations.append(
                Violation(
                    kind=VIOLATION_ENTITY_WITHOUT_FIELDS,
                    artifact=DOMAIN_FILENAME,
                    row_id=entity.id,
                    message=(
                        f"entity '{entity.id}' in {DOMAIN_FILENAME} holds no "
                        f"fields — every entity lists at least one field with a "
                        f"name and a type from {_field_type_names()}, so a plan "
                        f"derived from it does not have to invent the shape; add "
                        f"the fields the entity is defined by"
                    ),
                )
            )
            continue
        # One violation per duplicated *name*, not per extra occurrence —
        # matching check_duplicate_row_ids, and keeping a thrice-declared field
        # from spending three corrections on one defect.
        counts: dict[str, int] = {}
        for field in entity.fields:
            counts[field.name] = counts.get(field.name, 0) + 1
        reported: set[str] = set()
        for field in entity.fields:
            if counts[field.name] > 1 and field.name not in reported:
                reported.add(field.name)
                violations.append(
                    Violation(
                        kind=VIOLATION_DUPLICATE_FIELD_NAME,
                        artifact=DOMAIN_FILENAME,
                        row_id=entity.id,
                        message=(
                            f"entity '{entity.id}' in {DOMAIN_FILENAME} declares "
                            f"field '{field.name}' {counts[field.name]} times — "
                            f"field names are unique within an entity; rename all "
                            f"but one, or drop the extras"
                        ),
                    )
                )
            violations.extend(_field_target_violations(entity.id, field))
    return violations


def _field_target_violations(entity_id: str, field: FieldRow) -> list[Violation]:
    """``entity_id`` is set exactly when the field's type is ``reference``."""
    is_reference = field.type is FieldType.REFERENCE
    if is_reference and field.entity_id is None:
        return [
            Violation(
                kind=VIOLATION_FIELD_REFERENCE_TARGET,
                artifact=DOMAIN_FILENAME,
                row_id=entity_id,
                message=(
                    f"entity '{entity_id}' in {DOMAIN_FILENAME} has field "
                    f"'{field.name}' of type '{FieldType.REFERENCE.value}' with "
                    f"no 'entity_id' — a reference names the entity it points "
                    f"at; add 'entity_id', or give the field a different type"
                ),
            )
        ]
    if not is_reference and field.entity_id is not None:
        return [
            Violation(
                kind=VIOLATION_FIELD_REFERENCE_TARGET,
                artifact=DOMAIN_FILENAME,
                row_id=entity_id,
                message=(
                    f"entity '{entity_id}' in {DOMAIN_FILENAME} has field "
                    f"'{field.name}' of type '{field.type.value}' carrying an "
                    f"'entity_id' — only a '{FieldType.REFERENCE.value}' field "
                    f"points at an entity; drop 'entity_id', or change the type "
                    f"to '{FieldType.REFERENCE.value}'"
                ),
            )
        ]
    return []


def check_entity_references(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every workflow and business rule names entity ids the same artifact
    defines, and names at least one; every ``reference`` field resolves too.

    Business rules are in scope alongside workflows because a constraint may
    anchor to a rule id: a rule connected to no entity is a legal anchor
    target that silently breaks the entity→constraint chain. Every bad
    reference is reported, not just a row's first.

    Reference *fields* resolve here rather than in
    :func:`check_entity_fields` so that "does this entity id resolve" has one
    home, whatever row kind asked.
    """
    defined = {row.id for row in envelope.domain.entities}
    violations: list[Violation] = []
    for label, row_id, entity_ids in _entity_referencing_rows(envelope.domain):
        if not entity_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_ENTITY_REFERENCE,
                    artifact=DOMAIN_FILENAME,
                    row_id=row_id,
                    message=(
                        f"{label} '{row_id}' in {DOMAIN_FILENAME} references no "
                        f"entity — every {label} names at least one entity id it "
                        f"acts on, so a constraint anchored to it traces back to "
                        f"the domain; list the entity ids it touches"
                    ),
                )
            )
            continue
        for entity_id in entity_ids:
            if entity_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_ENTITY_REFERENCE,
                    artifact=DOMAIN_FILENAME,
                    row_id=row_id,
                    message=(
                        f"{label} '{row_id}' in {DOMAIN_FILENAME} references "
                        f"entity id '{entity_id}', which no entity row in "
                        f"{DOMAIN_FILENAME} defines — add an entity row with id "
                        f"'{entity_id}', or point the {label} at an entity id "
                        f"that is already defined"
                    ),
                )
            )
    for entity in envelope.domain.entities:
        for field in entity.fields:
            # A reference with no target at all is check_entity_fields' finding;
            # reporting it twice would spend two corrections on one defect.
            if field.entity_id is None or field.entity_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_ENTITY_REFERENCE,
                    artifact=DOMAIN_FILENAME,
                    row_id=entity.id,
                    message=(
                        f"entity '{entity.id}' in {DOMAIN_FILENAME} has field "
                        f"'{field.name}' referencing entity id "
                        f"'{field.entity_id}', which no entity row in "
                        f"{DOMAIN_FILENAME} defines — add an entity row with id "
                        f"'{field.entity_id}', or point the field at an entity "
                        f"id that is already defined"
                    ),
                )
            )
    return violations


def check_duplicate_row_ids(envelope: ArtifactEnvelope) -> list[Violation]:
    """Row ids are unique across every row kind in every artifact the envelope
    carries.

    Anchorable ids share this scope so an anchor cannot resolve two ways: a
    ``checkout`` workflow in the domain beside a ``checkout`` constraint would
    otherwise be ambiguous. Hosting and store ids are the deliberate
    identity-only additions: they reserve global ids without becoming anchor
    targets. One violation per duplicated id, not per occurrence.
    """
    counts: dict[str, int] = {}
    artifacts_by_id: dict[str, list[str]] = {}
    first_seen: list[str] = []
    for filename, rows in _envelope_identity_rows(envelope):
        for _label, row_id in rows:
            if row_id not in counts:
                counts[row_id] = 0
                artifacts_by_id[row_id] = []
                first_seen.append(row_id)
            counts[row_id] += 1
            if filename not in artifacts_by_id[row_id]:
                artifacts_by_id[row_id].append(filename)

    violations: list[Violation] = []
    for row_id in first_seen:
        count = counts[row_id]
        if count < 2:
            continue
        filenames = artifacts_by_id[row_id]
        if len(filenames) == 1:
            violations.append(
                Violation(
                    kind=VIOLATION_DUPLICATE_ROW_ID,
                    artifact=filenames[0],
                    row_id=row_id,
                    message=(
                        f"row id '{row_id}' is declared by {count} rows in "
                        f"{filenames[0]} — ids must be unique across every row "
                        "kind, so row ids resolve unambiguously; "
                        "rename all but one"
                    ),
                )
            )
            continue
        # Reported against the artifact under check: it is the one the retried
        # stage rewrites, so it is the side that can be renamed.
        violations.append(
            Violation(
                kind=VIOLATION_DUPLICATE_ROW_ID,
                artifact=envelope.filename_under_check,
                row_id=row_id,
                message=(
                    f"row id '{row_id}' is declared in both "
                    f"{' and '.join(filenames)} ({count} rows in total) — ids "
                    f"must be unique across the roadmap's artifacts, not only "
                    "within one file, so row ids resolve unambiguously; "
                    f"rename the row in "
                    f"{envelope.filename_under_check}"
                ),
            )
        )
    return violations


def check_attribute_totality(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every quality attribute carries exactly one disposition, and every
    ``attribute`` value names one of them coherently.

    This gate owns attribute membership everywhere the word appears — the
    parser carries the list as a plain constant and coerces nothing against
    it, so nothing else validates a *constraint* row's ``attribute``. Five
    defects: an undisposed attribute, one disposed twice, an unknown attribute
    on a disposition row, an unknown attribute on a constraint row, and a
    constraint serving an attribute this same artifact disposed
    ``not-load-bearing`` — a concern deliberately declared unranked cannot
    also be constrained for, and that is the shape a model produces when it
    pads to satisfy totality. ``traded-away`` is deliberately *not* in that
    last arm: spending an attribute knowingly and bounding how much you spend
    are coherent together.
    """
    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    known = set(QUALITY_ATTRIBUTES)
    rows_by_attribute: dict[str, list[str]] = {}
    for row in constraints_artifact.dispositions:
        rows_by_attribute.setdefault(row.attribute, []).append(row.id)

    violations: list[Violation] = []
    for attribute in QUALITY_ATTRIBUTES:
        if attribute in rows_by_attribute:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNDISPOSED_ATTRIBUTE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=None,
                message=(
                    f"quality attribute '{attribute}' has no disposition row in "
                    f"{CONSTRAINTS_FILENAME} — every attribute carries exactly "
                    f"one disposition; add a row disposing '{attribute}' as "
                    f"prioritized, traded-away, or not-load-bearing, the last "
                    f"being the honest answer when the project does not rank on "
                    f"it"
                ),
            )
        )

    for attribute, row_ids in rows_by_attribute.items():
        if len(row_ids) < 2:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_REDUNDANT_DISPOSITION,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row_ids[0],
                message=(
                    f"quality attribute '{attribute}' is disposed by "
                    f"{len(row_ids)} rows in {CONSTRAINTS_FILENAME} "
                    f"({', '.join(row_ids)}) — each attribute carries exactly "
                    f"one disposition; keep the row that states the real "
                    f"decision and drop the rest"
                ),
            )
        )

    for row in constraints_artifact.dispositions:
        if row.attribute in known:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNKNOWN_DISPOSED_ATTRIBUTE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"disposition row '{row.id}' in {CONSTRAINTS_FILENAME} "
                    f"disposes '{row.attribute}', which is not one of the "
                    f"roadmap's quality attributes ({_attribute_names()}) — "
                    f"rename it to one of those, or drop the row"
                ),
            )
        )

    for row in constraints_artifact.constraints:
        if row.attribute in known:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNKNOWN_CONSTRAINT_ATTRIBUTE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"constraint '{row.id}' in {CONSTRAINTS_FILENAME} serves "
                    f"attribute '{row.attribute}', which is not one of the "
                    f"roadmap's quality attributes ({_attribute_names()}) — "
                    f"point it at the attribute it actually discharges"
                ),
            )
        )

    not_load_bearing = {
        row.attribute
        for row in constraints_artifact.dispositions
        if row.disposition == ConstraintDisposition.NOT_LOAD_BEARING
    }
    for row in constraints_artifact.constraints:
        if row.attribute not in not_load_bearing:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_CONSTRAINT_ON_NOT_LOAD_BEARING,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"constraint '{row.id}' in {CONSTRAINTS_FILENAME} serves "
                    f"'{row.attribute}', which the same artifact disposes "
                    f"not-load-bearing — a concern declared unranked cannot also "
                    f"be constrained for; either drop the constraint or dispose "
                    f"'{row.attribute}' as prioritized or traded-away"
                ),
            )
        )
    return violations


def check_hosting_totality(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every fixed hosting facet has exactly one recognized row."""
    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    rows_by_facet: dict[str, list[str]] = {}
    for row in constraints_artifact.hosting:
        rows_by_facet.setdefault(row.facet, []).append(row.id)

    violations: list[Violation] = []
    for facet in HOSTING_FACETS:
        if facet in rows_by_facet:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_MISSING_HOSTING_FACET,
                artifact=CONSTRAINTS_FILENAME,
                row_id=None,
                message=(
                    f"hosting facet '{facet}' has no row in {CONSTRAINTS_FILENAME} "
                    "— add exactly one hosting row for every fixed facet: "
                    f"{', '.join(HOSTING_FACETS)}"
                ),
            )
        )

    for facet, row_ids in rows_by_facet.items():
        if len(row_ids) < 2:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_REDUNDANT_HOSTING_FACET,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row_ids[0],
                message=(
                    f"hosting facet '{facet}' is declared by {len(row_ids)} rows "
                    f"in {CONSTRAINTS_FILENAME} ({', '.join(row_ids)}) — keep "
                    "the one concrete answer for that facet and remove the rest"
                ),
            )
        )

    known_facets = set(HOSTING_FACETS)
    for row in constraints_artifact.hosting:
        if row.facet in known_facets:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNKNOWN_HOSTING_FACET,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"hosting row '{row.id}' in {CONSTRAINTS_FILENAME} names "
                    f"facet '{row.facet}', which is not one of the fixed hosting "
                    f"facets ({', '.join(HOSTING_FACETS)}) — rename it to one "
                    "of those, or remove the row"
                ),
            )
        )
    return violations


def check_stack_totality(envelope: ArtifactEnvelope) -> list[Violation]:
    """An artifact that carries the stack collection covers every concern.

    Binds on presence, never absence: ``stack is None`` (not recorded) is inert
    on every envelope path, so accepted stack-less versions stay valid. Reads
    shape only, never ``choice`` text; ``open`` is a legal answer.
    """
    constraints_artifact = envelope.constraints
    if constraints_artifact is None or constraints_artifact.stack is None:
        return []
    rows = constraints_artifact.stack

    ids_by_concern: dict[str, list[str]] = {}
    concerns_by_id: dict[str, list[str]] = {}
    for row in rows:
        ids_by_concern.setdefault(row.concern, []).append(row.id)
        concerns_by_id.setdefault(row.id, []).append(row.concern)

    concerns = ", ".join(STACK_CONCERNS)
    violations: list[Violation] = []
    for concern in STACK_CONCERNS:
        if concern in ids_by_concern:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_MISSING_STACK_CONCERN,
                artifact=CONSTRAINTS_FILENAME,
                row_id=None,
                message=(
                    f"stack concern '{concern}' has no row in {CONSTRAINTS_FILENAME} "
                    f"— record every stack concern ({concerns}); a concern with "
                    "no decision yet is recorded as `open`, never as an invented choice"
                ),
            )
        )

    known = set(STACK_CONCERNS)
    for row in rows:
        if row.concern in known:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNKNOWN_STACK_CONCERN,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"stack row '{row.id}' in {CONSTRAINTS_FILENAME} names concern "
                    f"'{row.concern}', which is not one of the stack concerns "
                    f"({concerns}) — rename it to one of those, or remove the row"
                ),
            )
        )

    for row_id, row_concerns in concerns_by_id.items():
        if len(row_concerns) < 2:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_DUPLICATE_STACK_ID,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row_id,
                message=(
                    f"stack id '{row_id}' is declared by {len(row_concerns)} rows "
                    f"in {CONSTRAINTS_FILENAME} (concerns: "
                    f"{', '.join(row_concerns)}) — give each stack row its own id"
                ),
            )
        )

    for concern, row_ids in ids_by_concern.items():
        distinct_ids = list(dict.fromkeys(row_ids))
        if concern not in known or len(distinct_ids) < 2:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_DUPLICATE_STACK_CONCERN,
                artifact=CONSTRAINTS_FILENAME,
                row_id=distinct_ids[0],
                message=(
                    f"stack concern '{concern}' is carried by {len(distinct_ids)} "
                    f"rows in {CONSTRAINTS_FILENAME} ({', '.join(distinct_ids)}) "
                    "— keep one row for that concern and remove the rest"
                ),
            )
        )

    for row in rows:
        # A blank choice is no choice.
        has_choice = row.choice is not None and bool(row.choice.strip())
        if has_choice != row.open:
            continue
        remedy = (
            "it carries both; keep one"
            if row.open
            else "it carries neither; record a choice or mark it `open: true`"
        )
        violations.append(
            Violation(
                kind=VIOLATION_STACK_ROW_STATE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"stack row '{row.id}' in {CONSTRAINTS_FILENAME} must be "
                    f"exactly one of a `choice` or `open: true` — {remedy}"
                ),
            )
        )
    return violations


def check_hosting_value_membership(envelope: ArtifactEnvelope) -> list[Violation]:
    """Each recognized hosting facet uses one of its concrete values."""
    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    violations: list[Violation] = []
    for row in constraints_artifact.hosting:
        allowed_values = HOSTING_FACET_VALUES.get(row.facet)
        if allowed_values is None or row.value in allowed_values:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNKNOWN_HOSTING_VALUE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"hosting row '{row.id}' in {CONSTRAINTS_FILENAME} gives "
                    f"facet '{row.facet}' value '{row.value}', which is not one "
                    f"of its concrete values ({', '.join(allowed_values)}) "
                    "— choose one of those values"
                ),
            )
        )
    return violations


def check_hosting_topology_coherence(envelope: ArtifactEnvelope) -> list[Violation]:
    """Mixed compute and bridge models describe a multi-unit application."""
    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    topology_rows = [row for row in constraints_artifact.hosting if row.facet == "topology"]
    if len(topology_rows) != 1 or topology_rows[0].value not in HOSTING_FACET_VALUES["topology"]:
        return []
    if topology_rows[0].value == "multi-unit":
        return []

    violations: list[Violation] = []
    for row in constraints_artifact.hosting:
        if (row.facet, row.value) not in {
            ("compute", "mixed"),
            ("model", "bridge"),
        }:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_HOSTING_TOPOLOGY_COHERENCE,
                artifact=CONSTRAINTS_FILENAME,
                row_id=row.id,
                message=(
                    f"hosting row '{row.id}' in {CONSTRAINTS_FILENAME} uses "
                    f"{row.facet}: {row.value}, which requires topology: "
                    "multi-unit — change the topology row or choose a value "
                    "that describes a single-unit application"
                ),
            )
        )
    return violations


def check_constraint_anchors(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every constraint anchors to at least one entity, business rule, or
    workflow id the domain artifact defines.

    It judges whatever domain artifact it is handed rather than reading one,
    which is what lets a resumed stage run re-decide it against a freshly
    loaded domain.
    """
    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    domain = envelope.domain
    anchorable = (
        {row.id for row in domain.entities}
        | {row.id for row in domain.business_rules}
        | {row.id for row in domain.workflows}
    )

    violations: list[Violation] = []
    for row in constraints_artifact.constraints:
        if not row.anchor_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_UNANCHORED_CONSTRAINT,
                    artifact=CONSTRAINTS_FILENAME,
                    row_id=row.id,
                    message=(
                        f"constraint '{row.id}' in {CONSTRAINTS_FILENAME} anchors "
                        f"to nothing — name at least one entity, business rule, "
                        f"or workflow id from {DOMAIN_FILENAME} that it "
                        f"constrains"
                    ),
                )
            )
            continue
        for anchor_id in row.anchor_ids:
            if anchor_id in anchorable:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNRESOLVED_CONSTRAINT_ANCHOR,
                    artifact=CONSTRAINTS_FILENAME,
                    row_id=row.id,
                    message=(
                        f"constraint '{row.id}' in {CONSTRAINTS_FILENAME} anchors "
                        f"to id '{anchor_id}', which {DOMAIN_FILENAME} does not "
                        f"define — anchor it to an entity, business rule, or "
                        f"workflow id that {DOMAIN_FILENAME} declares"
                    ),
                )
            )
    return violations


def check_decision_records(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every decision on the artifact under check names a rejected alternative
    with its reason, carries a rationale, and anchors to a resolvable row id.

    The anchor is what makes a ``pending`` decision actionable: an unanchored
    one names a tradeoff but not the thing it binds, leaving the operator who
    confirms it with nothing to attach it to. A quality attribute is reachable
    only through its disposition row's id — attribute names are a constant,
    not rows, so a bare name resolves nowhere.

    ``status`` is read nowhere in this module, which is how *``pending`` is
    never a violation* is enforced rather than merely intended: pending is the
    plan's review channel, and gating on it would fail the verb on exactly the
    artifacts it exists to produce.
    """
    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    carried = _envelope_rows(envelope)
    resolvable = {row_id for _filename, rows in carried for _label, row_id in rows}
    undefined_by = _or_list([artifact_filename for artifact_filename, _rows in carried])
    hint_parts: list[str] = []
    for artifact_filename, rows in carried:
        kinds = _kind_labels(rows)
        if not kinds:
            continue
        hint_parts.append(f"{_article(kinds[0])} {_or_list(kinds)} id in {artifact_filename}")
    anchor_hint = f"anchor it to {'; or to '.join(hint_parts)}"
    # Keyed on the constraints artifact being *reachable*, not on which stage is
    # running: the components stage resolves anchors against it too, so the
    # bare-attribute-name trap is live there and the guidance has to survive.
    if envelope.constraints is not None:
        anchor_hint += (
            " — a quality attribute is reachable only through its disposition "
            "row's id, never by its bare name"
        )

    violations: list[Violation] = []
    for row in artifact.decisions:
        if row.source is not None:
            continue
        if not row.rejected_alternatives:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_REJECTED_ALTERNATIVE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"decision '{row.id}' in {filename} rejects no "
                        f"alternative — record at least one option that was "
                        f"considered and turned down, with the reason it lost"
                    ),
                )
            )
        for alternative in row.rejected_alternatives:
            if alternative.reason.strip():
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNREASONED_ALTERNATIVE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"rejected alternative '{alternative.option}' on decision "
                        f"'{row.id}' in {filename} carries no reason — say why "
                        f"that option lost, not only that it did"
                    ),
                )
            )
        if not row.rationale.strip():
            violations.append(
                Violation(
                    kind=VIOLATION_BLANK_RATIONALE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"decision '{row.id}' in {filename} has a blank rationale "
                        f"— say why the chosen option won, so a later stage "
                        f"inheriting this decision as a fence knows what it is "
                        f"protecting"
                    ),
                )
            )
        anchor = row.anchor.strip()
        if not anchor:
            violations.append(
                Violation(
                    kind=VIOLATION_UNRESOLVED_DECISION_ANCHOR,
                    artifact=filename,
                    row_id=row.id,
                    message=(f"decision '{row.id}' in {filename} names no anchor — {anchor_hint}"),
                )
            )
        elif anchor not in resolvable:
            violations.append(
                Violation(
                    kind=VIOLATION_UNRESOLVED_DECISION_ANCHOR,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"decision '{row.id}' in {filename} anchors to id "
                        f"'{anchor}', which no row in {undefined_by} defines — "
                        f"{anchor_hint}"
                    ),
                )
            )
    return violations


def _owner_filename(owner: str) -> str:
    """Return the one artifact filename a carried-decision owner may write."""
    return {
        "domain": DOMAIN_FILENAME,
        "constraints": CONSTRAINTS_FILENAME,
        "components": COMPONENTS_FILENAME,
        "plans": PLANS_FILENAME,
    }[owner]


def check_inherited_decisions(envelope: ArtifactEnvelope) -> list[Violation]:
    """Require inherited rows to be exact, settled records from the current source.

    No carried input means this is a legacy run, so existing decision behavior
    remains unchanged.  The source parser normally prevents malformed source
    records; retaining the checks here makes a supplied current record the
    gate's complete authority rather than trusting an earlier parse forever.
    """
    source = envelope.carried_decisions
    if source is None:
        return []

    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    local_ids = design_row_ids(artifact)
    confirmed_sources = {answer.id for answer in source.confirmed_answers}
    records_by_id: dict[str, list[object]] = {}
    for record in source.decisions:
        records_by_id.setdefault(record.id, []).append(record)

    inherited_rows = [row for row in artifact.decisions if row.source is not None]
    rows_by_id: dict[str, list[object]] = {}
    for row in inherited_rows:
        rows_by_id.setdefault(row.id, []).append(row)

    violations: list[Violation] = []
    for record in source.decisions:
        if _owner_filename(record.owner) != filename:
            continue
        rows = rows_by_id.get(record.id, [])
        if not rows:
            violations.append(
                Violation(
                    kind=VIOLATION_MISSING_INHERITED_DECISION,
                    artifact=filename,
                    row_id=record.id,
                    message=(
                        f"inherited decision '{record.id}' owned by {filename} is missing "
                        f"— emit it once with confirmed citation '{record.source}'"
                    ),
                )
            )
        elif len(rows) > 1:
            violations.append(
                Violation(
                    kind=VIOLATION_DUPLICATE_INHERITED_DECISION,
                    artifact=filename,
                    row_id=record.id,
                    message=(
                        f"inherited decision '{record.id}' appears {len(rows)} times in {filename} "
                        f"for citation '{record.source}' — emit its owning-source record once"
                    ),
                )
            )

    for row in inherited_rows:
        records = records_by_id.get(row.id, [])
        if not records:
            violations.append(
                Violation(
                    kind=VIOLATION_ALTERED_INHERITED_DECISION,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} has no current source record "
                        f"for citation '{row.source}' — restore its approved identity"
                    ),
                )
            )
            continue
        if len(records) > 1:
            violations.append(
                Violation(
                    kind=VIOLATION_INHERITED_DECISION_AMBIGUOUS_SOURCE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} matches {len(records)} current "
                        f"source records for citation '{row.source}' — resolve the source ambiguity"
                    ),
                )
            )
            continue
        record = records[0]
        owner_filename = _owner_filename(record.owner)
        if owner_filename != filename:
            violations.append(
                Violation(
                    kind=VIOLATION_INHERITED_DECISION_WRONG_ARTIFACT,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} is owned by {owner_filename} "
                        f"under citation '{record.source}' — publish it only in its owning artifact"
                    ),
                )
            )
        if row.status is not DecisionStatus.SETTLED:
            violations.append(
                Violation(
                    kind=VIOLATION_INHERITED_DECISION_UNCONFIRMED,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} has status '{row.status.value}' "
                        f"for citation '{record.source}' — inherited decisions must remain settled"
                    ),
                )
            )
        if not row.source or row.source not in confirmed_sources:
            violations.append(
                Violation(
                    kind=VIOLATION_INHERITED_DECISION_UNKNOWN_SOURCE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} cites unconfirmed source "
                        f"'{row.source}' — cite confirmed answer '{record.source}'"
                    ),
                )
            )
        if record.anchor not in local_ids or row.anchor not in local_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_INHERITED_DECISION_NONLOCAL_ANCHOR,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} anchors to '{row.anchor}' "
                        f"under citation '{record.source}' — its approved anchor must name a live row in {filename}"
                    ),
                )
            )
        if (
            row.chosen_option != record.chosen_option
            or row.source != record.source
            or row.anchor != record.anchor
            or row.rationale != record.rationale
            or tuple((item.option, item.reason) for item in row.rejected_alternatives)
            != tuple((item.option, item.reason) for item in record.rejected_alternatives)
        ):
            violations.append(
                Violation(
                    kind=VIOLATION_ALTERED_INHERITED_DECISION,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"inherited decision '{row.id}' in {filename} differs from current source "
                        f"citation '{record.source}' — restore its approved option, anchor, citation, and supplied deliberation"
                    ),
                )
            )
    return violations


def check_artifact_non_empty(envelope: ArtifactEnvelope) -> list[Violation]:
    """The artifact under check declares the rows the rest of the gates judge.

    This is what stops the rest from passing vacuously. Every one of them
    is a check *over rows*, so an artifact with none clears them all — and
    because violations come back as corrections, deleting the offending rows
    is always the cheapest way to clear them, so a model under retry pressure
    converges on the emptiest passing artifact.
    """
    # Each entry is ``(collection, rows, the correction to make)``.
    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    if isinstance(artifact, DomainArtifact):
        required: tuple[tuple[str, tuple, str], ...] = (
            (
                "entities",
                artifact.entities,
                "name at least one entity the domain is about",
            ),
            (
                "workflows",
                artifact.workflows,
                "name at least one workflow, listing the entity ids it touches",
            ),
        )
    elif isinstance(artifact, ConstraintsArtifact):
        required = (
            (
                "constraints",
                artifact.constraints,
                "name at least one constraint, with the attribute it serves "
                f"and the {DOMAIN_FILENAME} ids it anchors to — dispositions "
                "alone are not a constraints artifact",
            ),
        )
    elif isinstance(artifact, ComponentsArtifact):
        required = (
            (
                "components",
                artifact.components,
                "name at least one component, listing the entity ids it owns "
                "and the pattern ids it applies",
            ),
        )
    else:
        required = (
            (
                "plans",
                artifact.plans,
                "name at least one plan, listing the component ids it covers "
                "and the draft seed path it will emit",
            ),
        )

    return [
        Violation(
            kind=VIOLATION_EMPTY_ARTIFACT,
            artifact=filename,
            row_id=None,
            message=(
                f"{filename} declares no {collection} — every other check is a "
                f"check over rows, so an artifact with none passes them all "
                f"vacuously; {correction}"
            ),
        )
        for collection, rows, correction in required
        if not rows
    ]


# An id's alphabet. ``\b`` will not do for the prose match: ``-`` is a
# non-word character, so ``\bentity-1\b`` is satisfied by a body that only
# mentions ``entity-1-extra``.
_ID_CHARACTER = r"[0-9A-Za-z_-]"


def _id_token_pattern(row_id: str) -> str:
    """Regex matching ``row_id`` as a whole token, bounded both sides."""
    return rf"(?<!{_ID_CHARACTER}){re.escape(row_id)}(?!{_ID_CHARACTER})"


def _prose_names_id(body: str, row_id: str) -> bool:
    """Whether ``body`` names ``row_id`` as a whole token, bounded both sides."""
    return re.search(_id_token_pattern(row_id), body) is not None


def check_inventory_has_prose(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every row the frontmatter inventories is named in the prose below it.

    Decidable on ids, which is what keeps it inside the plan's ban on prose
    gates: it never judges whether the prose is *good*, only whether the row
    was described at all. An inventoried row with no prose reads as covered
    and is not.
    """
    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    return [
        Violation(
            kind=VIOLATION_UNDESCRIBED_ROW,
            artifact=filename,
            row_id=row_id,
            message=(
                f"{label} '{row_id}' in {filename} is inventoried in the "
                f"frontmatter but never named in the prose below it — describe "
                f"it in the body, referring to it by its id so the description "
                f"is traceable"
            ),
        )
        for label, row_id in _rows_of(artifact)
        if not _prose_names_id(artifact.body, row_id)
    ]


@dataclass(frozen=True)
class NarrativeReference:
    """One occurrence of a removed row id in an artifact's live prose.

    Not a ``Violation``: it carries a body span, and it has no ``blocking``
    field because what blocks is policy owned above this module. ``start`` and
    ``end`` are body character offsets; ``line`` is 1-based within the body.
    """

    kind: str
    artifact: str
    row_id: str
    start: int
    end: int
    line: int
    excerpt: str


def _history_marked_spans(
    body: str, fenced: tuple[tuple[int, int], ...]
) -> list[tuple[int, int]]:
    """Spans from a start-marker line through the next end-marker line.

    A marker inside a fenced span is quoted text; an unclosed start yields no
    span, so the check fails safe toward reporting.
    """
    spans: list[tuple[int, int]] = []
    open_at: Optional[int] = None
    offset = 0
    for line in body.splitlines(keepends=True):
        in_fence = any(start <= offset < end for start, end in fenced)
        text = line.strip()
        if not in_fence:
            if text == HISTORY_MARKER_START and open_at is None:
                open_at = offset
            elif text == HISTORY_MARKER_END and open_at is not None:
                spans.append((open_at, offset + len(line)))
                open_at = None
        offset += len(line)
    return spans


def check_removed_ids_in_live_prose(
    envelope: ArtifactEnvelope, *, feedback_free: bool = False
) -> list[NarrativeReference]:
    """Removed design-row ids still named in the artifact under check's live prose.

    Not a stage gate: absent from every ``*_GATES`` tuple, so no stage run
    evaluates it. Matches whole-token ids from removal records only, outside
    fenced spans and history-marked spans, and reads no meaning. A removed id
    that is also a present row is the non-blocking ambiguous kind.

    ``feedback_free`` adds the predecessor's removals, because a feedback-free
    candidate is rendered with its own ``removals`` cleared.
    """
    artifact = envelope.artifact_under_check
    removals = list(artifact.removals)
    if feedback_free and envelope.predecessor is not None:
        removals.extend(envelope.predecessor.removals)
    removed_ids = tuple(dict.fromkeys(record.removed_id for record in removals))
    if not removed_ids:
        return []
    body = artifact.body
    scan = _fenced_code_spans(body)
    fenced = scan.spans
    excluded = [*fenced, *_history_marked_spans(body, fenced)]
    present_ids = {row_id for _label, row_id in _continuity_rows(artifact)}
    filename = envelope.filename_under_check
    found: list[NarrativeReference] = []
    unread: Optional[tuple[str, int]] = None  # first removed id hidden by an unclosed fence
    for row_id in removed_ids:
        pattern = _id_token_pattern(row_id)
        kind = (
            NARRATIVE_REMOVED_ID_AMBIGUOUS_REFERENCE
            if row_id in present_ids
            else NARRATIVE_REMOVED_ID_IN_LIVE_PROSE
        )
        for match in re.finditer(pattern, body):
            if any(start <= match.start() < end for start, end in excluded):
                if (
                    scan.unmatched_opening is not None
                    and match.start() >= scan.unmatched_opening
                    and unread is None
                ):
                    unread = (row_id, match.start())
                continue
            line_start = body.rfind("\n", 0, match.start()) + 1
            line_end = body.find("\n", match.end())
            line_text = body[line_start : len(body) if line_end == -1 else line_end]
            # Window the excerpt around the match so a long line still shows the defect.
            window_start = max(0, match.start() - line_start - _NARRATIVE_EXCERPT_LIMIT // 2)
            excerpt = line_text[window_start : window_start + _NARRATIVE_EXCERPT_LIMIT].strip()
            found.append(
                NarrativeReference(
                    kind=kind,
                    artifact=filename,
                    row_id=row_id,
                    start=match.start(),
                    end=match.end(),
                    line=body.count("\n", 0, match.start()) + 1,
                    excerpt=excerpt,
                )
            )
    if unread is not None and scan.unmatched_opening is not None:
        # The scanner runs an unclosed fence to end of text, so the check never read this tail.
        opener_line_end = body.find("\n", scan.unmatched_opening)
        found.append(
            NarrativeReference(
                kind=NARRATIVE_UNCLOSED_FENCE_UNREAD,
                artifact=filename,
                row_id=unread[0],
                start=scan.unmatched_opening,
                end=len(body),
                line=body.count("\n", 0, scan.unmatched_opening) + 1,
                excerpt=body[
                    scan.unmatched_opening : len(body) if opener_line_end == -1 else opener_line_end
                ].strip()[:_NARRATIVE_EXCERPT_LIMIT],
            )
        )
    return sorted(found, key=lambda ref: (ref.start, ref.row_id))


# --- The revision gates: what a re-run owes the version it replaces --------
#
# Each reaches ``artifact.feedback`` / ``artifact.removals`` directly rather
# than through ``_rows_of``: those stay the *design*-row inventory, so a
# reviewer's feedback is never asked for prose and feedback ids never fold into
# the design-row namespace.


def _prior_version(filename: str) -> str:
    """How a message names the predecessor. Ids are the only other anchor, and
    the file is rewritten whole on every attempt."""
    return f"the version of {filename} this run revises"


def _normalized_prose(value: Optional[str]) -> Optional[str]:
    """Stored prose with trailing whitespace off the value and every line.

    A ``request: |`` block a reviewer wrote round-trips through the renderer as
    a scalar carrying a trailing newline, so a model re-emitting the same
    visible words would otherwise trip an alteration on text nobody changed.
    The normalization lives in the comparison rather than in the renderer.
    """
    if value is None:
        return None
    return "\n".join(line.rstrip() for line in value.rstrip().splitlines())


def check_design_row_continuity(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every predecessor design row survives, or a removal record declares its
    drop and cites the reviewer feedback that asked for it.

    Three rules judge the artifact alone — a removal's rationale is non-blank,
    it cites at least one feedback row, and it does not name a row the same
    artifact still declares — so they hold on a first run and on a re-gated
    below-stage artifact, which already satisfy them.

    A removal record **carried from the predecessor is never re-judged** against
    it. Feedback is transient (the reviewer closes a row by deleting it), so a
    citation that resolved last run may name a row nobody can restore, and
    re-reporting it would turn an ordinary human close into a violation the
    model cannot fix. Identity is the whole record, so a directly edited one is
    judged afresh. The model may never drop a carried removal; pruning one is
    the reviewer's move, and it is how a removed row is later restored.

    A row a **settled** decision anchors to may not go at all — not even with a
    cited removal — because :func:`check_settled_decisions` pins that decision's
    anchor while :func:`check_decision_records` would then ask for the re-anchor
    gate 3 forbids, and the stage would oscillate between the two until its
    budget is gone. That arm is reported whether or not a removal record covers
    the drop, so an uncovered one is never told to add the record the block
    refuses, and its message names the un-settle the reviewer has to perform.
    A dropped *settled decision* is reported by :func:`check_settled_decisions`
    alone: saying here that a cited removal declares it, beside a message
    saying a removal is not enough, would spend two contradictory corrections
    on one defect.
    """
    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    declared = {row_id for _label, row_id in _continuity_rows(artifact)}

    violations: list[Violation] = []
    for record in artifact.removals:
        if not record.rationale.strip():
            violations.append(
                Violation(
                    kind=VIOLATION_BLANK_REMOVAL_RATIONALE,
                    artifact=filename,
                    row_id=record.removed_id,
                    message=(
                        f"the removal of '{record.removed_id}' in {filename} has "
                        f"a blank rationale — say why the row went, so a reader "
                        f"of the next revision knows the drop was considered "
                        f"rather than accidental"
                    ),
                )
            )
        if not record.feedback_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_UNCITED_REMOVAL,
                    artifact=filename,
                    row_id=record.removed_id,
                    message=(
                        f"the removal of '{record.removed_id}' in {filename} "
                        f"cites no feedback — a design row is dropped only "
                        f"because a reviewer asked for it; list the feedback "
                        f"ids in 'feedback_ids', or keep the row"
                    ),
                )
            )
        if record.removed_id in declared:
            violations.append(
                Violation(
                    kind=VIOLATION_REMOVAL_NAMES_A_PRESENT_ROW,
                    artifact=filename,
                    row_id=record.removed_id,
                    message=(
                        f"{filename} records the removal of '{record.removed_id}' "
                        f"and still declares a row with that id — a removal "
                        f"record says the row is gone; drop the row, or drop the "
                        f"removal record"
                    ),
                )
            )

    predecessor = envelope.predecessor
    if predecessor is None:
        return violations

    prior_version = _prior_version(filename)
    removed_ids = {record.removed_id for record in artifact.removals}
    settled = tuple(row for row in predecessor.decisions if row.status is DecisionStatus.SETTLED)
    pinned_by_anchor = {row.anchor.strip(): row.id for row in settled}
    settled_ids = {row.id for row in settled}

    reported: set[str] = set()
    for label, row_id in _continuity_rows(predecessor):
        if row_id in declared or row_id in reported or row_id in settled_ids:
            continue
        reported.add(row_id)
        # The pinned arm comes first whether or not a removal covers the drop:
        # offering the removal path to a row that may not take it would cost an
        # attempt to discover the block the other arm then reports.
        if row_id in pinned_by_anchor:
            violations.append(
                Violation(
                    kind=VIOLATION_DROPPED_DESIGN_ROW,
                    artifact=filename,
                    row_id=row_id,
                    message=(
                        f"{label} '{row_id}' is declared in {prior_version} and "
                        f"is absent from this revision, but decision "
                        f"'{pinned_by_anchor[row_id]}' is settled and anchors to "
                        f"it — a settled decision pins its anchor, so this row "
                        f"may not go, with or without a removal record; restore "
                        f"'{row_id}', drop any removal record naming it, and say "
                        f"in the feedback row's 'proposed_response' that the "
                        f"reviewer has to set decision "
                        f"'{pinned_by_anchor[row_id]}' to status "
                        f"'{DecisionStatus.PENDING.value}' in {filename} first"
                    ),
                )
            )
        elif row_id not in removed_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_DROPPED_DESIGN_ROW,
                    artifact=filename,
                    row_id=row_id,
                    message=(
                        f"{label} '{row_id}' is declared in {prior_version} and "
                        f"is absent from this revision, with no removal record "
                        f"— a revision revises the reviewer's artifact rather "
                        f"than regenerating over it; restore '{row_id}', or "
                        f"record its removal with a rationale and the id of the "
                        f"open feedback that asked for it"
                    ),
                )
            )

    carried = set(predecessor.removals)
    predecessor_rows = {row_id for _label, row_id in _continuity_rows(predecessor)}
    prior_feedback_ids = {row.id for row in predecessor.feedback}
    open_feedback_ids = {row.id for row in predecessor.feedback if row.state is FeedbackState.OPEN}
    for record in artifact.removals:
        if record in carried:
            continue
        if record.removed_id not in predecessor_rows:
            violations.append(
                Violation(
                    kind=VIOLATION_REMOVAL_WITHOUT_A_PREDECESSOR_ROW,
                    artifact=filename,
                    row_id=record.removed_id,
                    message=(
                        f"{filename} records the removal of '{record.removed_id}', "
                        f"which {prior_version} never declared — a removal "
                        f"record accounts for a row that existed; drop the "
                        f"record"
                    ),
                )
            )
        for feedback_id in record.feedback_ids:
            if feedback_id in open_feedback_ids:
                continue
            if feedback_id in prior_feedback_ids:
                detail = (
                    f"which is not '{FeedbackState.OPEN.value}' in "
                    f"{prior_version} — a "
                    f"'{FeedbackState.DEFERRED.value}' row was parked by the "
                    f"reviewer and an '{FeedbackState.AWAITING_REVIEW.value}' "
                    f"row was already answered, so neither authorizes dropping "
                    f"a design row"
                )
            else:
                detail = (
                    f"which no feedback row in {prior_version} carries — a "
                    f"removal is authorized only by feedback the reviewer wrote"
                )
            violations.append(
                Violation(
                    kind=VIOLATION_UNRESOLVED_REMOVAL_CITATION,
                    artifact=filename,
                    row_id=record.removed_id,
                    message=(
                        f"the removal of '{record.removed_id}' in {filename} "
                        f"cites feedback id '{feedback_id}', {detail}; keep "
                        f"'{record.removed_id}', or cite the "
                        f"'{FeedbackState.OPEN.value}' feedback that asked for "
                        f"its removal"
                    ),
                )
            )
    return violations


# The one state move a revision may make. Every other transition is the
# reviewer's, made in the editor before the run — and an ``open`` row left
# ``open`` is a request the revision owes an answer to.
_ANSWERED_FEEDBACK_STATE = {
    FeedbackState.OPEN: FeedbackState.AWAITING_REVIEW,
    FeedbackState.AWAITING_REVIEW: FeedbackState.AWAITING_REVIEW,
    FeedbackState.DEFERRED: FeedbackState.DEFERRED,
}


def check_feedback_integrity(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every predecessor feedback row survives with the reviewer's own text
    untouched, and moves only ``open`` → ``awaiting-review``.

    **No message here quotes a ``request`` or a ``proposed_response``.** The
    orchestrator writes these messages into the run log, and the plan's own
    criterion is that the log carries no feedback text — so an alteration names
    the row's id and the field that changed, never the words expected back.

    Feedback ids are their own namespace and deliberately stay out of
    :func:`check_duplicate_row_ids`: a removal's ``feedback_ids`` resolve
    against feedback rows only, while anchors and feedback targets each use
    their own explicit artifact identity set, so nothing resolves against the
    union.

    **The response text is never judged** — whether it answers the request, how
    long it is, whether it repeats a prior one. Only the carried rows that must
    not change at all have their response compared, and then only for equality.

    There is deliberately **no invented-feedback rule**. A fabricated row that
    manufactures a removal's reviewer-originated reason is the reply-rejection
    pass's to refuse, ahead of every gate, because that is the only place the
    predecessor-free case is visible at all. A rule here would sit unreachable
    behind it, and ordering it first would draw two corrections for one defect.
    Do not restore it.

    A predecessor carrying duplicate feedback ids has no defined join — "the
    predecessor's row for this id" is ambiguous — so the reviewer's own
    duplicate is the pre-flight check's to raise beside the predecessor load,
    never a violation the retry loop could act on.
    """
    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check

    violations: list[Violation] = []
    counts: dict[str, int] = {}
    for row in artifact.feedback:
        counts[row.id] = counts.get(row.id, 0) + 1
    reported: set[str] = set()
    for row in artifact.feedback:
        if counts[row.id] < 2 or row.id in reported:
            continue
        reported.add(row.id)
        violations.append(
            Violation(
                kind=VIOLATION_DUPLICATE_FEEDBACK_ID,
                artifact=filename,
                row_id=row.id,
                message=(
                    f"feedback id '{row.id}' is carried by {counts[row.id]} rows "
                    f"in {filename} — a feedback id names one request, and a "
                    f"removal citing it would otherwise resolve two ways; keep "
                    f"one row per id"
                ),
            )
        )

    predecessor = envelope.predecessor
    if predecessor is None:
        return violations

    prior_version = _prior_version(filename)
    prior_by_id = {row.id: row for row in predecessor.feedback}
    present = {row.id for row in artifact.feedback}
    for prior in predecessor.feedback:
        if prior.id in present:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_DROPPED_FEEDBACK,
                artifact=filename,
                row_id=prior.id,
                message=(
                    f"feedback row '{prior.id}' is carried by {prior_version} "
                    f"and is absent from this revision — only the reviewer "
                    f"closes feedback, by deleting the row before a run; carry "
                    f"'{prior.id}' forward"
                ),
            )
        )

    # Resolved against the predecessor, never the revision: that is what lets
    # feedback ask for the removal of the row it names, and the predecessor's
    # ``removed_id``s are in the set so the sanctioned drop does not deadlock a
    # row still open when the next run starts. A candidate-only target cannot
    # make a newly introduced feedback row reviewer-authored after the fact.
    resolvable = feedback_target_ids(predecessor) | {
        record.removed_id for record in predecessor.removals
    }
    for row in artifact.feedback:
        prior = prior_by_id.get(row.id)
        if row.target.kind is FeedbackTargetKind.ROW and row.target.row_id not in resolvable:
            violations.append(
                Violation(
                    kind=VIOLATION_UNRESOLVED_FEEDBACK_TARGET,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"feedback row '{row.id}' in {filename} targets row "
                        f"id '{row.target.row_id}', which {prior_version} "
                        f"neither declares nor records the removal of — a "
                        f"feedback row bears on a row that existed when the "
                        f"reviewer wrote it"
                    ),
                )
            )
        if prior is None:
            continue
        if row.target != prior.target:
            violations.append(
                Violation(
                    kind=VIOLATION_ALTERED_FEEDBACK_SOURCE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"feedback row '{row.id}' in {filename} changes the "
                        f"'target' it carries in {prior_version} — the reviewer "
                        f"chose what their request bears on; restore the target "
                        f"and answer the request as written"
                    ),
                )
            )
        if _normalized_prose(row.request) != _normalized_prose(prior.request):
            violations.append(
                Violation(
                    kind=VIOLATION_ALTERED_FEEDBACK_SOURCE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"feedback row '{row.id}' in {filename} changes the "
                        f"'request' it carries in {prior_version} — the "
                        f"reviewer's words are source input, never model-authored "
                        f"prose; restore the request verbatim and put your answer "
                        f"in 'proposed_response'"
                    ),
                )
            )
        if row.state is not _ANSWERED_FEEDBACK_STATE[prior.state]:
            if prior.state is FeedbackState.OPEN:
                correction = (
                    f"an '{FeedbackState.OPEN.value}' row is active guidance and "
                    f"owes an answer: set its state to "
                    f"'{FeedbackState.AWAITING_REVIEW.value}' and put the answer "
                    f"in 'proposed_response'. Deferring and reopening are the "
                    f"reviewer's moves, made in the editor before a run"
                )
            else:
                correction = (
                    f"only the reviewer moves a row out of "
                    f"'{prior.state.value}'; restore that state"
                )
            violations.append(
                Violation(
                    kind=VIOLATION_DISALLOWED_FEEDBACK_STATE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"feedback row '{row.id}' in {filename} is "
                        f"'{prior.state.value}' in {prior_version} and "
                        f"'{row.state.value}' here — {correction}"
                    ),
                )
            )
        if prior.state is FeedbackState.OPEN:
            continue
        if _normalized_prose(row.proposed_response) != _normalized_prose(prior.proposed_response):
            violations.append(
                Violation(
                    kind=VIOLATION_ALTERED_CARRIED_RESPONSE,
                    artifact=filename,
                    row_id=row.id,
                    message=(
                        f"feedback row '{row.id}' in {filename} is "
                        f"'{prior.state.value}' in {prior_version} and changes "
                        f"its 'proposed_response' — a row in that state is not "
                        f"active guidance, so rewriting its response is an "
                        f"unrequested edit; restore the response this row "
                        f"already carries"
                    ),
                )
            )
    return violations


def check_settled_decisions(envelope: ArtifactEnvelope) -> list[Violation]:
    """A predecessor decision marked ``settled`` keeps its id, status, chosen
    option, and anchor.

    Predecessor-only: without one there is no settled commitment to break.
    A cited removal does not excuse dropping a settled decision — it is pinned
    until an operator un-settles it, which is the one move the messages name, so
    the revision has something it can actually do instead of spending its
    budget restating the rule.

    ``rationale`` and ``rejected_alternatives`` are deliberately **not**
    compared. The revision prompt asks that they be kept; whether a reworded
    rationale means the same thing is not decidable here, and an equality check
    on prose would fail on formatting alone. Do not "complete" this comparison.
    """
    predecessor = envelope.predecessor
    if predecessor is None:
        return []

    artifact = envelope.artifact_under_check
    filename = envelope.filename_under_check
    prior_version = _prior_version(filename)
    current = {row.id: row for row in artifact.decisions}

    violations: list[Violation] = []
    for prior in predecessor.decisions:
        if prior.status is not DecisionStatus.SETTLED:
            continue
        unsettle = (
            f"an operator must reopen a settled decision: keep it as it "
            f"stands, and say in the feedback row's 'proposed_response' that "
            f"they have to set decision '{prior.id}' to status "
            f"'{DecisionStatus.PENDING.value}' in {filename} first"
        )
        row = current.get(prior.id)
        if row is None:
            violations.append(
                Violation(
                    kind=VIOLATION_DROPPED_SETTLED_DECISION,
                    artifact=filename,
                    row_id=prior.id,
                    message=(
                        f"decision '{prior.id}' is settled in {prior_version} "
                        f"and is absent from this revision — a cited removal "
                        f"does not excuse dropping it; restore '{prior.id}'. "
                        f"{unsettle}"
                    ),
                )
            )
            continue
        changed = [
            field
            for field, differs in (
                ("status", row.status is not prior.status),
                ("chosen_option", row.chosen_option != prior.chosen_option),
                ("anchor", row.anchor != prior.anchor),
            )
            if differs
        ]
        if not changed:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_ALTERED_SETTLED_DECISION,
                artifact=filename,
                row_id=prior.id,
                message=(
                    f"decision '{prior.id}' is settled in {prior_version} and "
                    f"this revision changes its {', '.join(changed)} — "
                    f"{unsettle}"
                ),
            )
        )
    return violations


def check_component_entity_references(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every component names at least one entity id ``01-domain.md`` defines.

    Components-stage only: upstream domain rows are read to resolve ids, not
    re-judged here.
    """
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    defined = {row.id for row in envelope.domain.entities}
    violations: list[Violation] = []
    for component in artifact.components:
        if not component.entity_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_ENTITY_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references no entity — every component names at least "
                        f"one entity id it owns from {DOMAIN_FILENAME}; list the "
                        f"entity ids it owns"
                    ),
                )
            )
            continue
        for entity_id in component.entity_ids:
            if entity_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_ENTITY_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references entity id '{entity_id}', which no entity "
                        f"row in {DOMAIN_FILENAME} defines — add an entity row "
                        f"with id '{entity_id}', or point the component at an "
                        f"entity id that is already defined"
                    ),
                )
            )
    return violations


def check_entity_component_coverage(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every domain entity id appears on at least one component's ``entity_ids``."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    claimed = {entity_id for component in artifact.components for entity_id in component.entity_ids}
    violations: list[Violation] = []
    for entity in envelope.domain.entities:
        if entity.id in claimed:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNCOVERED_ENTITY,
                artifact=COMPONENTS_FILENAME,
                row_id=None,
                message=(
                    f"entity id '{entity.id}' is defined in {DOMAIN_FILENAME} "
                    f"but appears on no component in {COMPONENTS_FILENAME} — "
                    f"every domain entity is owned by at least one component; "
                    f"list '{entity.id}' on a component's 'entity_ids'"
                ),
            )
        )
    return violations


def check_component_pattern_references(envelope: ArtifactEnvelope) -> list[Violation]:
    """Both pattern collections are non-empty and every component cites defined
    pattern ids from their union."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    violations: list[Violation] = []
    if not artifact.system_patterns:
        violations.append(
            Violation(
                kind=VIOLATION_EMPTY_PATTERN_COLLECTION,
                artifact=COMPONENTS_FILENAME,
                row_id=None,
                message=(
                    f"{COMPONENTS_FILENAME} declares no system_patterns — "
                    f"the artifact carries at least one system pattern row "
                    f"defining cross-cutting patterns the components share"
                ),
            )
        )
    if not artifact.component_patterns:
        violations.append(
            Violation(
                kind=VIOLATION_EMPTY_PATTERN_COLLECTION,
                artifact=COMPONENTS_FILENAME,
                row_id=None,
                message=(
                    f"{COMPONENTS_FILENAME} declares no component_patterns — "
                    f"the artifact carries at least one component pattern row "
                    f"defining reusable decomposition shapes"
                ),
            )
        )

    defined = {row.id for row in artifact.system_patterns} | {
        row.id for row in artifact.component_patterns
    }
    for component in artifact.components:
        if not component.pattern_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_PATTERN_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references no pattern — every component names at least "
                        f"one pattern id from {COMPONENTS_FILENAME}'s "
                        f"system_patterns or component_patterns; list the "
                        f"patterns it applies"
                    ),
                )
            )
            continue
        for pattern_id in component.pattern_ids:
            if pattern_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_PATTERN_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references pattern id '{pattern_id}', which no pattern "
                        f"row in {COMPONENTS_FILENAME} defines — add a pattern "
                        f"row with id '{pattern_id}', or point the component at "
                        f"a pattern id that is already defined"
                    ),
                )
            )
    return violations


def check_component_constraint_references(
    envelope: ArtifactEnvelope,
) -> list[Violation]:
    """Every non-empty ``constraint_ids`` entry names a constraint row
    ``02-constraints.md`` defines. An absent or empty list is not a discharge
    claim."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    defined = {row.id for row in constraints_artifact.constraints}
    violations: list[Violation] = []
    for component in artifact.components:
        for constraint_id in component.constraint_ids:
            if constraint_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references constraint id '{constraint_id}', which no "
                        f"constraint row in {CONSTRAINTS_FILENAME} defines — add "
                        f"a constraint row with id '{constraint_id}', or point "
                        f"the component at a constraint id that is already "
                        f"defined"
                    ),
                )
            )
    return violations


def check_prioritized_constraint_discharge(
    envelope: ArtifactEnvelope,
) -> list[Violation]:
    """Every constraint on a ``prioritized`` attribute is cited by at least one
    component's ``constraint_ids``.

    Constraints on ``traded-away`` or ``not-load-bearing`` attributes need no
    discharger — only ``prioritized`` rows are in scope.
    """
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    constraints_artifact = envelope.constraints
    if constraints_artifact is None:
        return []

    disposition_by_attribute = {
        row.attribute: row.disposition for row in constraints_artifact.dispositions
    }
    discharged = {
        constraint_id
        for component in artifact.components
        for constraint_id in component.constraint_ids
    }
    violations: list[Violation] = []
    for row in constraints_artifact.constraints:
        if disposition_by_attribute.get(row.attribute) is not ConstraintDisposition.PRIORITIZED:
            continue
        if row.id in discharged:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT,
                artifact=COMPONENTS_FILENAME,
                row_id=row.id,
                message=(
                    f"constraint '{row.id}' in {CONSTRAINTS_FILENAME} serves "
                    f"'{row.attribute}', which is prioritized, but no component "
                    f"in {COMPONENTS_FILENAME} cites it in 'constraint_ids' — "
                    f"list '{row.id}' on a component that discharges it"
                ),
            )
        )
    return violations


def check_store_definitions(envelope: ArtifactEnvelope) -> list[Violation]:
    """Components name defined stores, while in-process stores stay local."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    stores_by_id = {store.id: store for store in artifact.stores}
    in_process_owner_by_id: dict[str, str] = {}
    violations: list[Violation] = []
    for component in artifact.components:
        if not component.store_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_STORE_REFERENCE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        "references no store — every component names at least "
                        "one defined store; use a distinct 'in-process' store "
                        "when it has no durable store"
                    ),
                )
            )
            continue

        referenced_here: set[str] = set()
        reported_duplicates: set[str] = set()
        for store_id in component.store_ids:
            if store_id in referenced_here:
                if store_id not in reported_duplicates:
                    violations.append(
                        Violation(
                            kind=VIOLATION_DUPLICATE_STORE_REFERENCE,
                            artifact=COMPONENTS_FILENAME,
                            row_id=component.id,
                            message=(
                                f"component '{component.id}' in {COMPONENTS_FILENAME} "
                                f"lists store id '{store_id}' more than once in "
                                "'store_ids' — name each store once"
                            ),
                        )
                    )
                    reported_duplicates.add(store_id)
                continue
            referenced_here.add(store_id)

            store = stores_by_id.get(store_id)
            if store is None:
                violations.append(
                    Violation(
                        kind=VIOLATION_UNDEFINED_STORE_REFERENCE,
                        artifact=COMPONENTS_FILENAME,
                        row_id=component.id,
                        message=(
                            f"component '{component.id}' in {COMPONENTS_FILENAME} "
                            f"references store id '{store_id}', which no store row "
                            f"in {COMPONENTS_FILENAME} defines — add a store row "
                            f"with id '{store_id}', or point the component at a "
                            "defined store"
                        ),
                    )
                )
                continue
            if store.category != "in-process":
                continue

            owner = in_process_owner_by_id.setdefault(store_id, component.id)
            if owner == component.id:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_SHARED_IN_PROCESS_STORE,
                    artifact=COMPONENTS_FILENAME,
                    row_id=component.id,
                    message=(
                        f"component '{component.id}' in {COMPONENTS_FILENAME} "
                        f"references in-process store '{store_id}', already used "
                        f"by component '{owner}' — in-process storage is volatile "
                        "and component-local; define a separate in-process store "
                        "for this component"
                    ),
                )
            )
    return violations


def check_store_coverage(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every defined store serves at least one component."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    referenced_store_ids = {
        store_id for component in artifact.components for store_id in component.store_ids
    }
    return [
        Violation(
            kind=VIOLATION_UNCOVERED_STORE,
            artifact=COMPONENTS_FILENAME,
            row_id=store.id,
            message=(
                f"store '{store.id}' in {COMPONENTS_FILENAME} is defined but "
                "no component names it in 'store_ids' — point a component at "
                "the store, or remove the unused definition"
            ),
        )
        for store in artifact.stores
        if store.id not in referenced_store_ids
    ]


def check_store_value_membership(envelope: ArtifactEnvelope) -> list[Violation]:
    """Store categories and sharing models use the closed coarse vocabulary."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, ComponentsArtifact):
        return []

    violations: list[Violation] = []
    for store in artifact.stores:
        if store.category not in STORE_CATEGORIES:
            violations.append(
                Violation(
                    kind=VIOLATION_UNKNOWN_STORE_CATEGORY,
                    artifact=COMPONENTS_FILENAME,
                    row_id=store.id,
                    message=(
                        f"store '{store.id}' in {COMPONENTS_FILENAME} uses "
                        f"category '{store.category}', which is not one of the "
                        f"store categories ({', '.join(STORE_CATEGORIES)}) — "
                        "choose one of those values"
                    ),
                )
            )
        if store.sharing not in STORE_SHARING_MODELS:
            violations.append(
                Violation(
                    kind=VIOLATION_UNKNOWN_STORE_SHARING,
                    artifact=COMPONENTS_FILENAME,
                    row_id=store.id,
                    message=(
                        f"store '{store.id}' in {COMPONENTS_FILENAME} uses "
                        f"sharing '{store.sharing}', which is not one of the "
                        f"store sharing models ({', '.join(STORE_SHARING_MODELS)}) "
                        "— choose one of those values"
                    ),
                )
            )
    return violations


def check_plan_component_references(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every non-cross-cutting plan names at least one component id from
    ``03-components.md``; every listed id resolves there.

    Plans-stage only: upstream component rows are read to resolve ids, not
    re-judged here.
    """
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []

    components = envelope.components
    if components is None:
        return []

    defined = {row.id for row in components.components}
    violations: list[Violation] = []
    for plan in artifact.plans:
        if plan.disposition is PlanDisposition.CROSS_CUTTING:
            if not plan.component_ids:
                continue
        elif not plan.component_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_COMPONENT_REFERENCE,
                    artifact=PLANS_FILENAME,
                    row_id=plan.id,
                    message=(
                        f"plan '{plan.id}' in {PLANS_FILENAME} references no "
                        f"component — every plan whose disposition is not "
                        f"'{PlanDisposition.CROSS_CUTTING.value}' names at "
                        f"least one component id from {COMPONENTS_FILENAME}; "
                        f"list the component ids it covers"
                    ),
                )
            )
            continue
        for component_id in plan.component_ids:
            if component_id in defined:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_COMPONENT_REFERENCE,
                    artifact=PLANS_FILENAME,
                    row_id=plan.id,
                    message=(
                        f"plan '{plan.id}' in {PLANS_FILENAME} references "
                        f"component id '{component_id}', which no component row "
                        f"in {COMPONENTS_FILENAME} defines — add a component row "
                        f"with id '{component_id}', or point the plan at a "
                        f"component id that is already defined"
                    ),
                )
            )
    return violations


def check_plan_review_context(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every plan states its intended outcome and its explicit boundaries.

    ``intent`` gives a reviewer the reason the plan exists. ``non_goals``
    keeps predecessor-owned or deliberately deferred work from being inferred
    from the implementation shape, sizing rationale, or generated seed.
    """
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []

    violations: list[Violation] = []
    for plan in artifact.plans:
        if not plan.intent.strip():
            violations.append(
                Violation(
                    kind=VIOLATION_BLANK_PLAN_INTENT,
                    artifact=PLANS_FILENAME,
                    row_id=plan.id,
                    message=(
                        f"plan '{plan.id}' in {PLANS_FILENAME} has no intent — "
                        "state the operational outcome this plan is meant to "
                        "achieve, not just its implementation shape or size"
                    ),
                )
            )
        if not plan.non_goals:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_PLAN_NON_GOALS,
                    artifact=PLANS_FILENAME,
                    row_id=plan.id,
                    message=(
                        f"plan '{plan.id}' in {PLANS_FILENAME} has no non-goals "
                        "— list the adjacent or prerequisite work this plan "
                        "intentionally does not deliver"
                    ),
                )
            )
    return violations


def check_component_plan_coverage(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every component id in ``03-components.md`` appears on at least one
    plan row's ``component_ids``."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []

    components = envelope.components
    if components is None:
        return []

    claimed = {component_id for plan in artifact.plans for component_id in plan.component_ids}
    violations: list[Violation] = []
    for component in components.components:
        if component.id in claimed:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNCOVERED_COMPONENT,
                artifact=COMPONENTS_FILENAME,
                row_id=None,
                message=(
                    f"component id '{component.id}' is defined in "
                    f"{COMPONENTS_FILENAME} but appears on no plan in "
                    f"{PLANS_FILENAME} — every component is covered by at "
                    f"least one plan; list '{component.id}' on a plan row's "
                    f"'component_ids'"
                ),
            )
        )
    return violations


def validate_draft_seed_content(text: str, *, plan: PlanRow) -> list[Violation]:
    """Validate one draft seed's provenance and body references for its plan row."""
    basename = Path(plan.draft_seed_path).name
    if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
        return [
            Violation(
                kind=VIOLATION_DRAFT_SEED_UNMATCHED_FENCE,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan '{plan.id}' in {PLANS_FILENAME} draft seed "
                    f"'{basename}' has an unmatched opening code fence — add a "
                    "matching closing fence before materializing the draft seed"
                ),
            )
        ]
    try:
        provenance = parse_draft_seed_provenance(text)
    except RoadmapArtifactError as exc:
        return [
            Violation(
                kind=VIOLATION_DRAFT_SEED_PROVENANCE,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan '{plan.id}' in {PLANS_FILENAME} draft seed "
                    f"'{basename}' has invalid provenance frontmatter — "
                    f"{exc}; fix the '{DRAFT_SEED_ROADMAP_COMPONENTS_KEY}' "
                    f"block so it lists the component ids this plan owns"
                ),
            )
        ]

    plan_components = set(plan.component_ids)
    cross_cutting_plan = plan.disposition is PlanDisposition.CROSS_CUTTING
    violations: list[Violation] = []
    for component_id in provenance.roadmap_components:
        if component_id in plan_components:
            continue
        if cross_cutting_plan and provenance.cross_cutting:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_UNDEFINED_SEED_COMPONENT_REFERENCE,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan '{plan.id}' in {PLANS_FILENAME} draft seed "
                    f"'{basename}' lists component id '{component_id}' in "
                    f"'{DRAFT_SEED_ROADMAP_COMPONENTS_KEY}', which the plan "
                    f"row does not carry in 'component_ids' — list "
                    f"'{component_id}' on the plan row, or remove it from "
                    f"the seed provenance"
                ),
            )
        )

    sections = _draft_seed_sections(text)
    references = sections.get("references", "")

    for filename in (
        DOMAIN_FILENAME,
        CONSTRAINTS_FILENAME,
        COMPONENTS_FILENAME,
        PLANS_FILENAME,
    ):
        if re.search(
            rf"(?<![A-Za-z0-9_.-]){re.escape(filename)}(?![A-Za-z0-9_.-])",
            references,
        ):
            continue
        violations.append(
            Violation(
                kind=VIOLATION_MISSING_DRAFT_SEED_ARTIFACT_REFERENCE,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan '{plan.id}' in {PLANS_FILENAME} draft seed "
                    f"'{basename}' is missing accepted artifact reference "
                    f"'{filename}' in its body 'References' section — add "
                    f"the literal filename to a '## References' entry"
                ),
            )
        )
    risks = sections.get("risks", "").strip()
    if not risks or _is_placeholder_section(risks):
        violations.append(
            Violation(
                kind=VIOLATION_MISSING_DRAFT_SEED_RISKS,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan '{plan.id}' in {PLANS_FILENAME} draft seed "
                    f"'{basename}' has no '## Risks' section or it is empty — "
                    "restate each risk its accepted artifacts already state "
                    "(its 'Stop / defer' conditions, provisional decisions, open "
                    "stack concerns, inter-plan assumptions); when it states "
                    "none, write one line saying so rather than inventing one"
                ),
            )
        )
    return violations


def _draft_seed_sections(text: str) -> dict[str, str]:
    """The draft seed's H2 section bodies (lowercased keys), fences excised.

    Reuses ``scope_fence``'s canonical frontmatter-stripping and fence-aware
    H2 extraction rather than a second hand-rolled scanner, so a heading this
    gate recognizes is recognized the same way by every other consumer of a
    seed's References section (``create --from-existing``, ``scope_out``) —
    a divergent scanner here previously let a roadmap-apply accept a draft
    that ``create --from-existing`` then rejected on the identical file.

    ``strip_fenced_code=True``, not just ``ignore_fenced_code``: the caller
    pattern-matches the References body against known artifact filenames, so
    a fenced example that merely *mentions* a filename must not satisfy the
    gate the same as a real reference, and a fenced example is not a Risks
    section's content either.
    """
    return extract_h2_sections(_strip_frontmatter(text), strip_fenced_code=True)


def find_duplicate_draft_seed_basenames(plans: Sequence[PlanRow]) -> list[Violation]:
    """Report plan rows that resolve to the same draft-seed path."""
    path_to_plan_ids: dict[str, list[str]] = {}
    for plan in plans:
        path_to_plan_ids.setdefault(plan.draft_seed_path, []).append(plan.id)

    violations: list[Violation] = []
    for draft_seed_path, plan_ids in path_to_plan_ids.items():
        if len(plan_ids) < 2:
            continue
        basename = Path(draft_seed_path).name
        for index, plan_id in enumerate(plan_ids):
            others = [pid for i, pid in enumerate(plan_ids) if i != index]
            violations.append(
                Violation(
                    kind=VIOLATION_DUPLICATE_DRAFT_SEED_BASENAME,
                    artifact=PLANS_FILENAME,
                    row_id=plan_id,
                    message=(
                        f"plan '{plan_id}' in {PLANS_FILENAME} shares draft "
                        f"seed basename '{basename}' with "
                        f"{len(others)} other plan row(s) "
                        f"({', '.join(others)}) "
                        f"— each plan row's 'draft_seed_path' must resolve to "
                        f"a unique basename; give every plan its own seed file"
                    ),
                )
            )
    return violations


def check_draft_seed_bundle_alignment(envelope: ArtifactEnvelope) -> list[Violation]:
    """Plan rows must resolve to distinct draft-seed basenames."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []
    return find_duplicate_draft_seed_basenames(artifact.plans)


def _later_ordering_reference_message(
    plan_id: str, field: str, referenced_id: str, noun: str, defect: str
) -> str:
    """A cycle has no placement that satisfies it, so it is told to drop a reference, not to move one."""
    head = (
        f"ordering entry '{plan_id}' in {PLANS_FILENAME} lists '{field}' id "
        f"'{referenced_id}', which must appear earlier in 'ordering' than '{plan_id}'"
    )
    if defect == ORDERING_REFERENCE_CYCLE:
        return (
            f"{head}, but it already reaches '{plan_id}' through ordering "
            f"references, so no order satisfies both — drop this {noun}, or "
            f"another reference on the same cycle"
        )
    return f"{head} — move '{referenced_id}' above '{plan_id}', or drop the {noun}"


def check_plan_ordering_totality(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every plan id appears exactly once in ``ordering``, dependency fields
    reference earlier plan ids, and every plan id matches the create slug rule."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []

    plan_ids = {plan.id for plan in artifact.plans}
    violations: list[Violation] = []

    for plan in artifact.plans:
        if PLAN_ID_SLUG_RE.fullmatch(plan.id):
            continue
        violations.append(
            Violation(
                kind=VIOLATION_INVALID_PLAN_ID_SLUG,
                artifact=PLANS_FILENAME,
                row_id=plan.id,
                message=(
                    f"plan id '{plan.id}' in {PLANS_FILENAME} is not a valid "
                    f"create-compatible slug — use lowercase letters, digits, "
                    f"and hyphens only, starting and ending with a letter or "
                    f"digit"
                ),
            )
        )

    ordering_plan_ids = [entry.plan_id for entry in artifact.ordering]
    ordering_counts: dict[str, int] = {}
    for plan_id in ordering_plan_ids:
        ordering_counts[plan_id] = ordering_counts.get(plan_id, 0) + 1

    reported_duplicates: set[str] = set()
    for plan_id, count in ordering_counts.items():
        if count < 2 or plan_id in reported_duplicates:
            continue
        reported_duplicates.add(plan_id)
        violations.append(
            Violation(
                kind=VIOLATION_ORDERING_PLAN_ID_DUPLICATE,
                artifact=PLANS_FILENAME,
                row_id=plan_id,
                message=(
                    f"plan id '{plan_id}' appears {count} times in "
                    f"{PLANS_FILENAME} 'ordering' — each plan id must appear "
                    f"exactly once; keep one ordering entry and drop the rest"
                ),
            )
        )

    for plan_id in sorted(plan_ids):
        if plan_id in ordering_counts:
            continue
        violations.append(
            Violation(
                kind=VIOLATION_MISSING_ORDERING_PLAN_ID,
                artifact=PLANS_FILENAME,
                row_id=plan_id,
                message=(
                    f"plan id '{plan_id}' is declared in {PLANS_FILENAME} "
                    f"'plans' but absent from 'ordering' — list every plan id "
                    f"exactly once in the execution sequence"
                ),
            )
        )

    position_by_plan_id = {entry.plan_id: index for index, entry in enumerate(artifact.ordering)}
    references_by_plan_id: dict[str, set[str]] = {}
    for entry in artifact.ordering:
        references_by_plan_id.setdefault(entry.plan_id, set()).update(
            referenced_id
            for referenced_id in (*entry.depends_on, *entry.assumption_targets)
            if referenced_id in plan_ids
        )

    def later_reference_defect(referenced_id: str, plan_id: str) -> str:
        seen: set[str] = set()
        frontier = [referenced_id]
        while frontier:
            current = frontier.pop()
            if current == plan_id:
                return ORDERING_REFERENCE_CYCLE
            if current not in seen:
                seen.add(current)
                frontier.extend(references_by_plan_id.get(current, ()))
        return ORDERING_REFERENCE_NOT_EARLIER

    for entry in artifact.ordering:
        if entry.plan_id not in plan_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
                    artifact=PLANS_FILENAME,
                    row_id=entry.plan_id,
                    message=(
                        f"ordering entry '{entry.plan_id}' in {PLANS_FILENAME} "
                        f"names no plan row in 'plans' — drop the entry, or "
                        f"add a plan row with id '{entry.plan_id}'"
                    ),
                    referenced_id=entry.plan_id,
                    reference_defect=ORDERING_REFERENCE_ABSENT,
                )
            )
        entry_index = position_by_plan_id.get(entry.plan_id)
        if entry_index is None:
            continue
        for dependency_id in entry.depends_on:
            if dependency_id not in plan_ids:
                violations.append(
                    Violation(
                        kind=VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
                        artifact=PLANS_FILENAME,
                        row_id=entry.plan_id,
                        message=(
                            f"ordering entry '{entry.plan_id}' in "
                            f"{PLANS_FILENAME} lists 'depends_on' id "
                            f"'{dependency_id}', which no plan row in 'plans' "
                            f"defines — point the dependency at a plan id that "
                            f"is already declared, or drop it"
                        ),
                        referenced_id=dependency_id,
                        reference_defect=ORDERING_REFERENCE_ABSENT,
                    )
                )
                continue
            referenced_position = position_by_plan_id.get(dependency_id)
            if referenced_position is None:
                continue  # no ordering slot: reported as missing-ordering-plan-id
            if referenced_position >= entry_index:
                defect = later_reference_defect(dependency_id, entry.plan_id)
                violations.append(
                    Violation(
                        kind=VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
                        artifact=PLANS_FILENAME,
                        row_id=entry.plan_id,
                        message=_later_ordering_reference_message(
                            entry.plan_id, "depends_on", dependency_id, "dependency", defect
                        ),
                        referenced_id=dependency_id,
                        reference_defect=defect,
                    )
                )
        for target_id in entry.assumption_targets:
            if target_id not in plan_ids:
                violations.append(
                    Violation(
                        kind=VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
                        artifact=PLANS_FILENAME,
                        row_id=entry.plan_id,
                        message=(
                            f"ordering entry '{entry.plan_id}' in "
                            f"{PLANS_FILENAME} lists 'assumption_targets' id "
                            f"'{target_id}', which no plan row in 'plans' "
                            f"defines — point the target at a plan id that is "
                            f"already declared, or drop it"
                        ),
                        referenced_id=target_id,
                        reference_defect=ORDERING_REFERENCE_ABSENT,
                    )
                )
                continue
            referenced_position = position_by_plan_id.get(target_id)
            if referenced_position is None:
                continue  # no ordering slot: reported as missing-ordering-plan-id
            if referenced_position >= entry_index:
                defect = later_reference_defect(target_id, entry.plan_id)
                violations.append(
                    Violation(
                        kind=VIOLATION_UNDEFINED_ORDERING_PLAN_REFERENCE,
                        artifact=PLANS_FILENAME,
                        row_id=entry.plan_id,
                        message=_later_ordering_reference_message(
                            entry.plan_id, "assumption_targets", target_id, "target", defect
                        ),
                        referenced_id=target_id,
                        reference_defect=defect,
                    )
                )
    return violations


def check_assumption_plan_references(envelope: ArtifactEnvelope) -> list[Violation]:
    """Every assumption cites at least one consumer, and each id resolves in
    ``plans``."""
    artifact = envelope.artifact_under_check
    if not isinstance(artifact, PlansArtifact):
        return []

    plan_ids = {plan.id for plan in artifact.plans}
    violations: list[Violation] = []
    for assumption in artifact.assumptions:
        if not assumption.consuming_plan_ids:
            violations.append(
                Violation(
                    kind=VIOLATION_NO_ASSUMPTION_CONSUMER,
                    artifact=PLANS_FILENAME,
                    row_id=assumption.id,
                    message=(
                        f"assumption '{assumption.id}' in {PLANS_FILENAME} cites "
                        f"no consuming plan — list at least one plan id from "
                        f"'plans' in 'consuming_plan_ids', or drop the "
                        f"assumption"
                    ),
                )
            )
            continue
        for plan_id in assumption.consuming_plan_ids:
            if plan_id in plan_ids:
                continue
            violations.append(
                Violation(
                    kind=VIOLATION_UNDEFINED_ASSUMPTION_PLAN_REFERENCE,
                    artifact=PLANS_FILENAME,
                    row_id=assumption.id,
                    message=(
                        f"assumption '{assumption.id}' in {PLANS_FILENAME} lists "
                        f"consuming plan id '{plan_id}', which no plan row in "
                        f"'plans' defines — point the consumer at a plan id that "
                        f"is already declared, or drop it"
                    ),
                )
            )
    return violations


# --------------------------------------------------------------------------
# The stage gate sets
# --------------------------------------------------------------------------
#
# Declared order is the violation order: gate by gate, then row order as
# parsed, so two runs over one input produce the same list and a retried
# prompt is reproducible.

DOMAIN_GATES: tuple[Gate, ...] = (
    check_artifact_non_empty,
    check_duplicate_row_ids,
    check_entity_fields,
    check_entity_references,
    check_decision_records,
    check_inherited_decisions,
    check_inventory_has_prose,
    check_design_row_continuity,
    check_feedback_integrity,
    check_settled_decisions,
)

CONSTRAINTS_GATES: tuple[Gate, ...] = (
    check_artifact_non_empty,
    check_duplicate_row_ids,
    check_hosting_totality,
    check_hosting_value_membership,
    check_hosting_topology_coherence,
    check_stack_totality,
    check_attribute_totality,
    check_constraint_anchors,
    check_decision_records,
    check_inherited_decisions,
    check_inventory_has_prose,
    check_design_row_continuity,
    check_feedback_integrity,
    check_settled_decisions,
)

COMPONENTS_GATES: tuple[Gate, ...] = (
    check_artifact_non_empty,
    check_duplicate_row_ids,
    check_component_entity_references,
    check_entity_component_coverage,
    check_component_pattern_references,
    check_component_constraint_references,
    check_prioritized_constraint_discharge,
    check_store_definitions,
    check_store_coverage,
    check_store_value_membership,
    check_decision_records,
    check_inherited_decisions,
    check_inventory_has_prose,
    check_design_row_continuity,
    check_feedback_integrity,
    check_settled_decisions,
)

PLANS_GATES: tuple[Gate, ...] = (
    check_artifact_non_empty,
    check_duplicate_row_ids,
    check_plan_review_context,
    check_plan_component_references,
    check_component_plan_coverage,
    check_draft_seed_bundle_alignment,
    check_plan_ordering_totality,
    check_assumption_plan_references,
    check_decision_records,
    check_inherited_decisions,
    check_inventory_has_prose,
    check_design_row_continuity,
    check_feedback_integrity,
    check_settled_decisions,
)


def _run_gates(gates: tuple[Gate, ...], envelope: ArtifactEnvelope) -> list[Violation]:
    violations: list[Violation] = []
    for gate in gates:
        violations.extend(gate(envelope))
    return violations


def run_domain_gates(envelope: ArtifactEnvelope) -> list[Violation]:
    """Judge ``01-domain.md``. The gate-set third of a stage table entry."""
    return _run_gates(DOMAIN_GATES, envelope)


def run_constraints_gates(envelope: ArtifactEnvelope) -> list[Violation]:
    """Judge ``02-constraints.md`` against the domain in the envelope.

    Same call shape as :func:`run_domain_gates` on purpose: the stage table
    holds one of these as a value, and a differing signature would put
    knowledge of which gate needs what back into the orchestrator.
    """
    return _run_gates(CONSTRAINTS_GATES, envelope)


def run_components_gates(envelope: ArtifactEnvelope) -> list[Violation]:
    """Judge ``03-components.md`` against the domain and constraints in the
    envelope.

    Same call shape as :func:`run_domain_gates` and
    :func:`run_constraints_gates` on purpose: step 5's stage table holds this
    by identity with no wrapper.
    """
    return _run_gates(COMPONENTS_GATES, envelope)


def run_plans_gates(envelope: ArtifactEnvelope) -> list[Violation]:
    """Judge ``04-roadmap.md`` against its upstream artifacts.

    Same call shape as :func:`run_domain_gates`,
    :func:`run_constraints_gates`, and :func:`run_components_gates` on purpose:
    step 6's stage table holds this by identity with no wrapper.
    """
    return _run_gates(PLANS_GATES, envelope)
