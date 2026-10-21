"""Tests for the bounded same-artifact roadmap feedback revision contract."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from plan_tool import roadmap_revision
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HostingRow,
    OrderingEntry,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    PatternRow,
    RemovalRecord,
    ResearchDisclosure,
    StoreRow,
    WorkflowRow,
    parse_components_artifact,
    parse_constraints_artifact,
    parse_domain_artifact,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
)
from plan_tool.project_config import StageFeedbackLimits
from plan_tool.roadmap_relations import RelationKind
from plan_tool.roadmap_revision import (
    STAGE_SPLIT_FEEDBACK_ACTION,
    TEXT_FIELDS_BY_ROW_TYPE,
    RevisionContractError,
    StageFeedbackAuthority,
    StageLiveRow,
    StageRevisionLimitError,
    StageRevisionContext,
    build_stage_revision_context,
    parse_feedback_selector,
    parse_revision_operations,
    parse_stage_revision_operations,
    preflight_feedback_revision,
    SHARED_SPAN_MAX_BYTES,
    project_row_owned_prose_spans,
    stage_prose_span_id,
    stage_row_operation_policy,
)
from plan_tool.roadmap_revision_patch import merge_stage_revision


_ARTIFACT_KEYS = tuple(stage.artifact_key for stage in STAGES)
_TARGET_ID = "entity-order"
_FEEDBACK_ID = "feedback-order-name"


def test_plan_row_operation_policy_owns_the_ordering_companion_rule() -> None:
    assert stage_row_operation_policy("plans").requires_ordering_companion is True
    assert stage_row_operation_policy("entities").requires_ordering_companion is False


def _feedback(
    *,
    feedback_id: str = _FEEDBACK_ID,
    target: FeedbackTarget | None = None,
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response: str | None = None,
) -> FeedbackRow:
    return FeedbackRow(
        id=feedback_id,
        target=target
        or FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id=_TARGET_ID),
        request="Use the customer-facing order name.",
        state=state,
        proposed_response=proposed_response,
    )


def _artifact(
    *,
    feedback: tuple[FeedbackRow, ...] = (_feedback(),),
    entities: tuple[EntityRow, ...] | None = None,
    removals: tuple[RemovalRecord, ...] = (),
) -> DomainArtifact:
    return DomainArtifact(
        entities=entities
        or (
            EntityRow(
                id=_TARGET_ID,
                name="Order",
                fields=(FieldRow(name="total", type=FieldType.NUMBER),),
            ),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="# Domain\n",
        feedback=feedback,
        removals=removals,
    )


def _canonical_text(**kwargs: object) -> str:
    return render_domain_artifact(_artifact(**kwargs))


def _preflight(**kwargs: object):
    return preflight_feedback_revision(
        parse_feedback_selector(f"domain:{_FEEDBACK_ID}", _ARTIFACT_KEYS),
        _canonical_text(**kwargs),
        parse_domain_artifact,
        render_domain_artifact,
    )


def _operations(*records: dict[str, object]) -> str:
    return json.dumps({"operations": list(records)})


def _response_record(**overrides: object) -> dict[str, object]:
    return {
        "op": "respond-feedback",
        "feedback_id": _FEEDBACK_ID,
        "proposed_response": "The row now uses the requested presentation.",
    } | overrides


def _replacement_record(**overrides: object) -> dict[str, object]:
    return {
        "op": "replace-row-presentation",
        "row_id": _TARGET_ID,
        "field": "name",
        "value": "Customer order",
    } | overrides


def _stage_context(
    *,
    artifact_key: str = "domain",
    active_feedback: tuple[StageFeedbackAuthority, ...] | None = None,
    live_rows: tuple[StageLiveRow, ...] | None = None,
    predecessor_relation_ids: frozenset[str] = frozenset({"entity-predecessor"}),
    predecessor_plan_ids: tuple[str, ...] = (),
    carried_removal_ids: frozenset[str] = frozenset(),
    inherited_decision_ids: frozenset[str] = frozenset(),
    limits: StageFeedbackLimits = StageFeedbackLimits(),
) -> StageRevisionContext:
    row = EntityRow(
        id=_TARGET_ID,
        name="Order",
        fields=(FieldRow(name="total", type=FieldType.NUMBER),),
    )
    return StageRevisionContext(
        artifact_key=artifact_key,  # type: ignore[arg-type]
        active_feedback=active_feedback
        or (
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=_TARGET_ID,
                target_row_type="entities",
                allow_edit=True,
                allow_remove=True,
            ),
        ),
        live_rows=live_rows or (StageLiveRow("entities", row, "span-order"),),
        predecessor_relation_ids=predecessor_relation_ids,
        predecessor_plan_ids=predecessor_plan_ids,
        carried_removal_ids=carried_removal_ids,
        inherited_decision_ids=inherited_decision_ids,
        limits=limits,
    )


def _stage_operations(*records: dict[str, object]) -> str:
    return json.dumps({"operations": list(records)})


def _stage_response(feedback_id: str = _FEEDBACK_ID, **overrides: object) -> dict[str, object]:
    return {
        "op": "respond-feedback",
        "feedback_id": feedback_id,
        "proposed_response": "The requested revision is ready for review.",
    } | overrides


def _entity_payload(row_id: str = "entity-new", **overrides: object) -> dict[str, object]:
    return {"id": row_id, "name": "New entity", "fields": []} | overrides


def _add_entity(
    feedback_id: str = _FEEDBACK_ID, **overrides: object
) -> dict[str, object]:
    row = _entity_payload()
    return {
        "op": "add-row",
        "feedback_id": feedback_id,
        "row_type": "entities",
        "row": row,
        "prose_amendment": {
            "action": "append",
            "row_id": row["id"],
            "fragment": f"{row['id']} is the new domain entity.",
        },
    } | overrides


def _edit_entity(
    feedback_id: str = _FEEDBACK_ID, **overrides: object
) -> dict[str, object]:
    return {
        "op": "edit-row",
        "feedback_id": feedback_id,
        "row_type": "entities",
        "row_id": _TARGET_ID,
        "row": _entity_payload(
            _TARGET_ID,
            name="Customer order",
            fields=[{"name": "total", "type": "number"}],
        ),
        "prose_amendment": {
            "action": "replace",
            "row_id": _TARGET_ID,
            "span_id": "span-order",
            "replacement": "entity-order now uses the customer-facing name.",
        },
    } | overrides


def _remove_entity(
    feedback_id: str = _FEEDBACK_ID, **overrides: object
) -> dict[str, object]:
    return {
        "op": "remove-row-with-record",
        "feedback_id": feedback_id,
        "row_type": "entities",
        "row_id": _TARGET_ID,
        "removal_record": {
            "removed_id": _TARGET_ID,
            "rationale": "This entity is no longer needed.",
            "feedback_ids": [feedback_id],
        },
        "prose_amendment": {
            "action": "delete",
            "row_id": _TARGET_ID,
            "span_id": "span-order",
        },
    } | overrides


@pytest.mark.parametrize(
    ("selector", "message"),
    (
        (None, "feedback selector must be a string"),
        ("domain", "feedback selector must use '<artifact-key>:<feedback-id>'"),
        (
            "domain:one:two",
            "feedback selector must contain one non-empty artifact key and one "
            "colon-free feedback id",
        ),
        ("unknown:feedback-1", "unknown roadmap artifact key: 'unknown'"),
    ),
)
def test_revision_selector_compatibility_preserves_revision_contract_errors_and_messages(
    selector: object, message: str
) -> None:
    with pytest.raises(RevisionContractError) as error:
        parse_feedback_selector(selector, _ARTIFACT_KEYS)

    assert str(error.value) == message


def test_preflight_selects_one_open_response_less_live_row() -> None:
    preflight = _preflight()

    assert preflight.artifact_key == "domain"
    assert preflight.feedback_id == _FEEDBACK_ID
    assert preflight.feedback_request == "Use the customer-facing order name."
    assert preflight.feedback_state is FeedbackState.OPEN
    assert preflight.target_row_id == _TARGET_ID
    assert preflight.target_collection == "entities"
    assert [
        (field.field, field.value) for field in preflight.allowed_text_fields
    ] == [("name", "Order")]
    assert [item.field for item in preflight.relation_data] == ["fields"]
    assert not hasattr(preflight, "artifact")


def test_preflight_rejects_a_collection_missing_from_the_text_field_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``TEXT_FIELDS_BY_ROW_TYPE`` is hand-maintained separately from
    ``design_row_collections`` and only happens to cover the same keys
    today; a collection the latter names but the former doesn't must raise
    a typed contract error, not an uncaught ``KeyError``."""
    real_design_row_collections = roadmap_revision.design_row_collections

    def with_unknown_collection(artifact):
        collections = dict(real_design_row_collections(artifact))
        collections["a-future-collection"] = collections.pop("entities")
        return collections

    monkeypatch.setattr(
        roadmap_revision, "design_row_collections", with_unknown_collection
    )

    with pytest.raises(RevisionContractError, match="a-future-collection"):
        _preflight()


def test_preflight_rejects_duplicate_feedback_and_duplicate_live_target_ids() -> None:
    duplicate_feedback = (_feedback(), _feedback())
    with pytest.raises(RevisionContractError, match="unique"):
        _preflight(feedback=duplicate_feedback)

    duplicate_entities = (
        EntityRow(_TARGET_ID, "Order", ()),
        EntityRow(_TARGET_ID, "Order copy", ()),
    )
    with pytest.raises(RevisionContractError, match="exactly one live"):
        _preflight(entities=duplicate_entities)


def test_preflight_accepts_feedback_targeting_a_candidate_only_live_row() -> None:
    candidate_id = "entity-candidate"
    candidate = EntityRow(
        id=candidate_id,
        name="Candidate",
        fields=(FieldRow(name="total", type=FieldType.NUMBER),),
    )
    feedback = _feedback(
        target=FeedbackTarget(FeedbackTargetKind.ROW, candidate_id)
    )

    assert _preflight(feedback=(feedback,), entities=(candidate,)).target_row_id == (
        candidate_id
    )


@pytest.mark.parametrize(
    "feedback,removals",
    (
        (_feedback(state=FeedbackState.DEFERRED), ()),
        (_feedback(state=FeedbackState.AWAITING_REVIEW, proposed_response="Already answered."), ()),
        (_feedback(target=FeedbackTarget(FeedbackTargetKind.ARTIFACT)), ()),
        (
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "removed-row")),
            (RemovalRecord("removed-row", "Removed by an earlier review.", ("old-feedback",)),),
        ),
        (_feedback(proposed_response="A reviewer reopened this request."), ()),
    ),
)
def test_preflight_rejects_non_open_artifact_removed_and_reopened_selected_feedback(
    feedback: FeedbackRow, removals: tuple[RemovalRecord, ...]
) -> None:
    with pytest.raises(RevisionContractError):
        _preflight(feedback=(feedback,), removals=removals)


def test_preflight_checks_retained_feedback_without_rejecting_an_unselected_reopened_row() -> None:
    dangling = _feedback(
        feedback_id="other-feedback",
        target=FeedbackTarget(FeedbackTargetKind.ROW, "missing-row"),
    )
    with pytest.raises(RevisionContractError, match="recorded removal"):
        _preflight(feedback=(_feedback(), dangling))

    reopened = _feedback(
        feedback_id="other-feedback",
        state=FeedbackState.OPEN,
        proposed_response="An earlier response remains visible.",
    )
    preflight = _preflight(feedback=(_feedback(), reopened))
    assert preflight.feedback_id == _FEEDBACK_ID

    removed_target = _feedback(
        feedback_id="other-feedback",
        target=FeedbackTarget(FeedbackTargetKind.ROW, "removed-row"),
    )
    preflight = _preflight(
        feedback=(_feedback(), removed_target),
        removals=(RemovalRecord("removed-row", "An earlier review removed it.", ()),),
    )
    assert preflight.feedback_id == _FEEDBACK_ID


def test_preflight_requires_exact_parser_renderer_round_trip() -> None:
    canonical = _canonical_text()
    selector = parse_feedback_selector(f"domain:{_FEEDBACK_ID}", _ARTIFACT_KEYS)
    assert "# Your review." in canonical
    assert preflight_feedback_revision(
        selector, canonical, parse_domain_artifact, render_domain_artifact
    ).target_row_id == _TARGET_ID

    for changed in (
        canonical.replace("feedback:\n", "unknown: value\nfeedback:\n", 1),
        canonical.replace("entities:\n", "entities: \n", 1),
        canonical.replace("# Your review.", "# Changed review.", 1),
    ):
        with pytest.raises(RevisionContractError, match="render-canonical"):
            preflight_feedback_revision(
                selector, changed, parse_domain_artifact, render_domain_artifact
            )


def test_local_revision_preflight_refuses_inherited_decision_target() -> None:
    decision = DecisionRow(
        "decision-approved", "Use queues", (), "Approved rationale", _TARGET_ID,
        DecisionStatus.SETTLED, source="answer-approved",
    )
    feedback = _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, decision.id))
    artifact = replace(_artifact(feedback=(feedback,)), decisions=(decision,))
    selector = parse_feedback_selector(f"domain:{_FEEDBACK_ID}", _ARTIFACT_KEYS)

    with pytest.raises(RevisionContractError, match="targets inherited decision"):
        preflight_feedback_revision(
            selector, render_domain_artifact(artifact), parse_domain_artifact,
            render_domain_artifact,
        )


def test_local_revision_preflight_keeps_local_decision_revisable() -> None:
    decision = DecisionRow(
        "decision-local", "Use queues", (), "Local rationale", _TARGET_ID,
        DecisionStatus.SETTLED,
    )
    feedback = _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, decision.id))
    artifact = replace(_artifact(feedback=(feedback,)), decisions=(decision,))
    selector = parse_feedback_selector(f"domain:{_FEEDBACK_ID}", _ARTIFACT_KEYS)

    preflight = preflight_feedback_revision(
        selector, render_domain_artifact(artifact), parse_domain_artifact,
        render_domain_artifact,
    )

    assert preflight.target_row_id == decision.id
    assert [(field.field, field.value) for field in preflight.allowed_text_fields] == [
        ("rationale", "Local rationale")
    ]


@pytest.mark.parametrize(
    ("selector_text", "artifact", "parser", "renderer", "target_row_id"),
    (
        (
            "constraints:constraint-primary",
            ConstraintsArtifact(
                dispositions=(),
                constraints=(
                    ConstraintRow(
                        "constraint-primary",
                        "Keep response latency bounded.",
                        "performance",
                        (),
                    ),
                ),
                decisions=(),
                hosting=(HostingRow("hosting-primary", "region", "us-east-1"),),
                body="# Constraints\n",
                feedback=(
                    _feedback(
                        feedback_id="hosting-feedback",
                        target=FeedbackTarget(FeedbackTargetKind.ROW, "hosting-primary"),
                    ),
                    _feedback(
                        feedback_id="constraint-primary",
                        target=FeedbackTarget(FeedbackTargetKind.ROW, "constraint-primary"),
                    ),
                ),
            ),
            parse_constraints_artifact,
            render_constraints_artifact,
            "constraint-primary",
        ),
        (
            "components:component-primary",
            ComponentsArtifact(
                system_patterns=(),
                component_patterns=(),
                components=(ComponentRow("component-primary", "Orders", (), (), (), ()),),
                decisions=(),
                stores=(StoreRow("store-primary", "relational", "shared"),),
                body="# Components\n",
                feedback=(
                    _feedback(
                        feedback_id="store-feedback",
                        target=FeedbackTarget(FeedbackTargetKind.ROW, "store-primary"),
                    ),
                    _feedback(
                        feedback_id="component-primary",
                        target=FeedbackTarget(FeedbackTargetKind.ROW, "component-primary"),
                    ),
                ),
            ),
            parse_components_artifact,
            render_components_artifact,
            "component-primary",
        ),
    ),
)
def test_local_preflight_accepts_unrelated_identity_only_feedback(
    selector_text: str,
    artifact: ConstraintsArtifact | ComponentsArtifact,
    parser: object,
    renderer: object,
    target_row_id: str,
) -> None:
    preflight = preflight_feedback_revision(
        parse_feedback_selector(selector_text, _ARTIFACT_KEYS),
        renderer(artifact),  # type: ignore[operator]
        parser,  # type: ignore[arg-type]
        renderer,  # type: ignore[arg-type]
    )

    assert preflight.target_row_id == target_row_id


def test_text_field_table_covers_every_targetable_row_type() -> None:
    assert dict(TEXT_FIELDS_BY_ROW_TYPE) == {
        "entities": ("name",),
        "business_rules": ("statement",),
        "workflows": ("name",),
        "decisions": ("rationale",),
        "dispositions": (),
        "constraints": ("statement",),
        "system_patterns": ("name", "statement"),
        "component_patterns": ("name", "statement"),
        "components": ("name",),
        "plans": ("title", "sizing_rationale"),
        "assumptions": ("statement",),
    }
    assert "fields" not in TEXT_FIELDS_BY_ROW_TYPE
    assert "ordering" not in TEXT_FIELDS_BY_ROW_TYPE
    assert TEXT_FIELDS_BY_ROW_TYPE["dispositions"] == ()


def test_operations_require_optional_replacement_then_one_final_response() -> None:
    preflight = _preflight()
    response_only = parse_revision_operations(_operations(_response_record()), preflight)
    assert response_only.replacement is None

    with_replacement = parse_revision_operations(
        _operations(_replacement_record(), _response_record()), preflight
    )
    assert with_replacement.replacement is not None
    assert [record.op for record in with_replacement.operations] == [
        "replace-row-presentation",
        "respond-feedback",
    ]

    for records in (
        (),
        (_replacement_record(),),
        (_response_record(), _replacement_record()),
    ):
        with pytest.raises(RevisionContractError, match="operations"):
            parse_revision_operations(_operations(*records), preflight)


def test_operations_reject_non_json_framing_duplicate_keys_and_unknown_fields() -> None:
    preflight = _preflight()
    valid = _operations(_response_record())
    invalid = (
        f"preamble {valid}",
        f"```json\n{valid}\n```",
        f"{valid}\n{valid}",
        f"\v{valid}",
        f"{valid}\v",
        f"\u00a0{valid}",
        f"{valid}\u00a0",
        '{"operations": [], "operations": []}',
        '{"operations": {}}',
        '{"operations": [], "unexpected": true}',
        '{"operations": [{"op": "respond-feedback", "op": "respond-feedback"}]}',
        '{"operations": [null]}',
        _operations(_response_record(unexpected="value")),
    )
    for response in invalid:
        with pytest.raises(RevisionContractError):
            parse_revision_operations(response, preflight)


def test_operations_bind_to_selected_ids_and_one_allowed_field() -> None:
    preflight = _preflight()
    invalid = (
        _operations(_replacement_record(row_id="other-row"), _response_record()),
        _operations(_replacement_record(field="fields"), _response_record()),
        _operations(_replacement_record(value=" "), _response_record()),
        _operations(_replacement_record(value=" Customer order"), _response_record()),
        _operations(_replacement_record(value=3), _response_record()),
        _operations(_response_record(feedback_id="other-feedback")),
        _operations(_response_record(proposed_response=" ")),
        _operations(_response_record(proposed_response=" Answer")),
        _operations(_response_record(proposed_response=3)),
        _operations(_replacement_record(), _replacement_record(), _response_record()),
        _operations(_response_record(), _response_record()),
    )
    for response in invalid:
        with pytest.raises(RevisionContractError):
            parse_revision_operations(response, preflight)


def test_stage_envelope_rejects_non_json_framing_duplicate_keys_and_unknown_members() -> None:
    context = _stage_context()
    valid = _stage_operations(_stage_response())
    invalid = (
        f"preamble {valid}",
        f"```json\n{valid}\n```",
        f"{valid}\n{valid}",
        '{"operations": [], "operations": []}',
        '{"operations": [], "unexpected": true}',
        '{"operations": [{"op": "respond-feedback", "op": "respond-feedback"}]}',
        '{"operations": [NaN]}',
        _stage_operations(_stage_response(unexpected=True)),
    )

    for response in invalid:
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(response, context)

    with pytest.raises(RevisionContractError, match="must be text"):
        parse_stage_revision_operations(123, context)  # type: ignore[arg-type]


def test_stage_envelope_accepts_only_closed_operation_vocabulary() -> None:
    context = _stage_context()
    for record in (
        {"op": "replace-body", "feedback_id": _FEEDBACK_ID},
        {"op": "edit-row", "feedback_id": _FEEDBACK_ID, "row_type": "entities"},
        _add_entity(row={"id": "entity-new", "statement": "not an entity"}),
    ):
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_stage_add_row_requires_explicit_supported_type_and_matching_payload() -> None:
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),)
    )
    parsed = parse_stage_revision_operations(
        _stage_operations(_add_entity(), _stage_response()), context
    )
    assert parsed.material_operations[0].row.id == "entity-new"

    invalid = (
        _add_entity(row_type="unknown"),
        _add_entity(row={"id": "entity-new", "statement": "wrong shape"}),
        _add_entity(row_type="stores"),
    )
    for record in invalid:
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


@pytest.mark.parametrize(
    ("artifact_key", "row_type", "row", "predecessor_ids", "predecessor_plans"),
    (
        ("domain", "entities", _entity_payload("entity-new"), frozenset(), ()),
        (
            "domain",
            "business_rules",
            {"id": "rule-new", "statement": "Orders are valid.", "entity_ids": ["entity-predecessor"]},
            frozenset({"entity-predecessor"}),
            (),
        ),
        (
            "domain",
            "workflows",
            {"id": "workflow-new", "name": "Order flow", "entity_ids": ["entity-predecessor"]},
            frozenset({"entity-predecessor"}),
            (),
        ),
        (
            "domain",
            "decisions",
            {
                "id": "decision-new",
                "chosen_option": "Keep it simple.",
                "rejected_alternatives": [],
                "rationale": "It fits the bounded stage.",
                "anchor": "entity-predecessor",
                "status": "pending",
            },
            frozenset({"entity-predecessor"}),
            (),
        ),
        (
            "constraints",
            "dispositions",
            {"id": "disposition-new", "attribute": "security", "disposition": "prioritized"},
            frozenset(),
            (),
        ),
        (
            "constraints",
            "constraints",
            {
                "id": "constraint-new",
                "statement": "Protect orders.",
                "attribute": "security",
                "anchor_ids": ["entity-predecessor"],
            },
            frozenset({"entity-predecessor"}),
            (),
        ),
        (
            "constraints",
            "decisions",
            {
                "id": "constraint-decision-new",
                "chosen_option": "Prioritize security.",
                "rejected_alternatives": [],
                "rationale": "The constraint requires it.",
                "anchor": "constraint-predecessor",
                "status": "settled",
            },
            frozenset({"constraint-predecessor"}),
            (),
        ),
        (
            "components",
            "system_patterns",
            {"id": "system-pattern-new", "name": "Events", "statement": "Use durable events."},
            frozenset(),
            (),
        ),
        (
            "components",
            "component_patterns",
            {"id": "component-pattern-new", "name": "Ports", "statement": "Keep adapters local."},
            frozenset(),
            (),
        ),
        (
            "components",
            "stores",
            {"id": "store-new", "category": "database", "sharing": "private"},
            frozenset(),
            (),
        ),
        (
            "components",
            "components",
            {
                "id": "component-new",
                "name": "Orders",
                "entity_ids": ["entity-predecessor"],
                "pattern_ids": ["pattern-predecessor"],
                "constraint_ids": ["constraint-predecessor"],
                "store_ids": ["store-predecessor"],
            },
            frozenset(
                {
                    "entity-predecessor",
                    "pattern-predecessor",
                    "constraint-predecessor",
                    "store-predecessor",
                }
            ),
            (),
        ),
        (
            "components",
            "decisions",
            {
                "id": "component-decision-new",
                "chosen_option": "Keep ownership local.",
                "rejected_alternatives": [],
                "rationale": "It keeps the component bounded.",
                "anchor": "component-predecessor",
                "status": "pending",
            },
            frozenset({"component-predecessor"}),
            (),
        ),
        (
            "plans",
            "plans",
            {
                "id": "plan-new",
                "title": "New plan",
                "disposition": "keep",
                "component_ids": ["component-predecessor"],
                "draft_seed_path": "plan-seed-drafts/plan-new.md",
                "sizing_rationale": "One bounded increment.",
            },
            frozenset({"component-predecessor"}),
            ("plan-predecessor",),
        ),
        (
            "plans",
            "assumptions",
            {
                "id": "assumption-new",
                "statement": "The predecessor stays available.",
                "consuming_plan_ids": ["plan-predecessor"],
            },
            frozenset({"plan-predecessor"}),
            ("plan-predecessor",),
        ),
        (
            "plans",
            "decisions",
            {
                "id": "plan-decision-new",
                "chosen_option": "Deliver in order.",
                "rejected_alternatives": [],
                "rationale": "The roadmap needs the dependency.",
                "anchor": "plan-predecessor",
                "status": "pending",
            },
            frozenset({"plan-predecessor"}),
            ("plan-predecessor",),
        ),
    ),
)
def test_stage_add_row_accepts_every_admitted_typed_collection(
    artifact_key: str,
    row_type: str,
    row: dict[str, object],
    predecessor_ids: frozenset[str],
    predecessor_plans: tuple[str, ...],
) -> None:
    context = _stage_context(
        artifact_key=artifact_key,
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        live_rows=(),
        predecessor_relation_ids=predecessor_ids,
        predecessor_plan_ids=predecessor_plans,
    )
    record: dict[str, object] = {
        "op": "add-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": row_type,
        "row": row,
    }
    if row_type == "stores":
        pass
    else:
        record["prose_amendment"] = {
            "action": "append",
            "row_id": row["id"],
            "fragment": f"{row['id']} is described by this row-owned fragment.",
        }
    if row_type == "plans":
        record["ordering"] = {
            "plan_id": row["id"],
            "depends_on": ["plan-predecessor"],
        }

    parsed = parse_stage_revision_operations(
        _stage_operations(record, _stage_response()), context
    )
    assert parsed.material_operations[0].row.id == row["id"]


def test_stage_feedback_cannot_add_an_inherited_decision_id() -> None:
    decision_id = "decision-inherited"
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        inherited_decision_ids=frozenset({decision_id}),
    )
    addition = {
        "op": "add-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "decisions",
        "row": {
            "id": decision_id,
            "chosen_option": "Approved",
            "rejected_alternatives": [],
            "rationale": "Invented by feedback",
            "anchor": _TARGET_ID,
            "status": "settled",
        },
    }

    with pytest.raises(RevisionContractError, match="inherited decision.*cannot be added"):
        parse_stage_revision_operations(
            _stage_operations(addition, _stage_response()), context
        )


@pytest.mark.parametrize("operation", ("edit-row", "remove-row-with-record"))
def test_stage_feedback_cannot_change_an_inherited_decision(operation: str) -> None:
    decision = DecisionRow(
        "decision-inherited", "Approved", (), None, _TARGET_ID,
        DecisionStatus.SETTLED, "answer-1",
    )
    context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=decision.id,
                target_row_type="decisions",
                allow_edit=True,
                allow_remove=True,
            ),
        ),
        live_rows=(StageLiveRow("decisions", decision, "span-decision"),),
        inherited_decision_ids=frozenset({decision.id}),
    )
    record: dict[str, object] = {
        "op": operation,
        "feedback_id": _FEEDBACK_ID,
        "row_type": "decisions",
        "row_id": decision.id,
    }
    if operation == "edit-row":
        record["row"] = {
            "id": decision.id,
            "chosen_option": "Changed",
            "rejected_alternatives": [],
            "rationale": "Changed by feedback",
            "anchor": _TARGET_ID,
            "status": "settled",
        }
    else:
        record["removal_record"] = {
            "removed_id": decision.id,
            "rationale": "Changed by feedback",
            "feedback_ids": [_FEEDBACK_ID],
        }

    with pytest.raises(RevisionContractError, match="inherited decision.*cannot be"):
        parse_stage_revision_operations(
            _stage_operations(record, _stage_response()), context
        )


def test_hosting_add_and_removal_are_rejected_but_edit_preserves_fixed_facet() -> None:
    hosting = HostingRow("hosting-app", "runtime", "managed", "example")
    context = _stage_context(
        artifact_key="constraints",
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=hosting.id,
                target_row_type="hosting",
                allow_edit=True,
                allow_remove=False,
                allow_add=True,
            ),
        ),
        live_rows=(StageLiveRow("hosting", hosting),),
    )
    edit = {
        "op": "edit-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "hosting",
        "row_id": hosting.id,
        "row": {"id": hosting.id, "facet": "runtime", "value": "serverless"},
    }
    parsed = parse_stage_revision_operations(
        _stage_operations(edit, _stage_response()), context
    )
    assert parsed.material_operations[0].row == HostingRow(
        "hosting-app", "runtime", "serverless", "example"
    )

    removal = _remove_entity(row_type="hosting", row_id=hosting.id)
    removal["removal_record"] = {
        "removed_id": hosting.id,
        "rationale": "no longer needed",
        "feedback_ids": [_FEEDBACK_ID],
    }
    removal["prose_amendment"] = None
    addition = _add_entity(row_type="hosting", row={"id": "h", "facet": "runtime", "value": "x"})
    for record in (removal, addition, edit | {"row": {"id": hosting.id, "facet": "other", "value": "x"}}):
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_hosting_and_store_stage_edits_preserve_omitted_descriptions() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        "Internal Runtime",
        "The platform team operates this internal runtime.",
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id),
            ),
        ),
    )
    hosting_operations = parse_stage_revision_operations(
        _stage_operations(
            {
                "op": "edit-row",
                "feedback_id": _FEEDBACK_ID,
                "row_type": "hosting",
                "row_id": hosting.id,
                "row": {
                    "id": hosting.id,
                    "facet": hosting.facet,
                    "value": "per-request",
                    "product": hosting.product,
                },
            },
            _stage_response(),
        ),
        build_stage_revision_context(constraints),
    )
    revised_constraints = merge_stage_revision(
        constraints, build_stage_revision_context(constraints), hosting_operations
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        "Internal Database",
        "The orders team operates this internal store.",
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, store.id),
            ),
        ),
    )
    store_operations = parse_stage_revision_operations(
        _stage_operations(
            {
                "op": "edit-row",
                "feedback_id": _FEEDBACK_ID,
                "row_type": "stores",
                "row_id": store.id,
                "row": {
                    "id": store.id,
                    "category": store.category,
                    "sharing": "silo",
                    "product": store.product,
                },
            },
            _stage_response(),
        ),
        build_stage_revision_context(components),
    )
    revised_components = merge_stage_revision(
        components, build_stage_revision_context(components), store_operations
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].description == hosting.description
    assert (
        parse_constraints_artifact(render_constraints_artifact(revised_constraints))
        == revised_constraints
    )
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].description == store.description
    assert (
        parse_components_artifact(render_components_artifact(revised_components))
        == revised_components
    )


def test_hosting_and_store_stage_edits_preserve_omitted_product() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        "Cloud Run",
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id),
            ),
        ),
    )
    revised_constraints = merge_stage_revision(
        constraints,
        build_stage_revision_context(constraints),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "hosting",
                    "row_id": hosting.id,
                    "row": {
                        "id": hosting.id,
                        "facet": hosting.facet,
                        "value": "per-request",
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(constraints),
        ),
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        "Managed Postgres",
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, store.id),
            ),
        ),
    )
    revised_components = merge_stage_revision(
        components,
        build_stage_revision_context(components),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "stores",
                    "row_id": store.id,
                    "row": {
                        "id": store.id,
                        "category": store.category,
                        "sharing": "silo",
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(components),
        ),
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].product == hosting.product
    assert (
        parse_constraints_artifact(render_constraints_artifact(revised_constraints))
        == revised_constraints
    )
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].product == store.product
    assert (
        parse_components_artifact(render_components_artifact(revised_components))
        == revised_components
    )


def test_hosting_and_store_stage_edits_clear_explicit_null_product() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        product="Cloud Run",
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id),
            ),
        ),
    )
    revised_constraints = merge_stage_revision(
        constraints,
        build_stage_revision_context(constraints),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "hosting",
                    "row_id": hosting.id,
                    "row": {
                        "id": hosting.id,
                        "facet": hosting.facet,
                        "value": "per-request",
                        "product": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(constraints),
        ),
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        product="Managed Postgres",
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, store.id),
            ),
        ),
    )
    revised_components = merge_stage_revision(
        components,
        build_stage_revision_context(components),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "stores",
                    "row_id": store.id,
                    "row": {
                        "id": store.id,
                        "category": store.category,
                        "sharing": "silo",
                        "product": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(components),
        ),
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].product is None
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].product is None


def test_hosting_and_store_stage_edits_clear_explicit_null_descriptions() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        description="The platform team operates this internal runtime.",
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id),
            ),
        ),
    )
    revised_constraints = merge_stage_revision(
        constraints,
        build_stage_revision_context(constraints),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "hosting",
                    "row_id": hosting.id,
                    "row": {
                        "id": hosting.id,
                        "facet": hosting.facet,
                        "value": "per-request",
                        "description": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(constraints),
        ),
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        description="The orders team operates this internal store.",
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, store.id),
            ),
        ),
    )
    revised_components = merge_stage_revision(
        components,
        build_stage_revision_context(components),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "stores",
                    "row_id": store.id,
                    "row": {
                        "id": store.id,
                        "category": store.category,
                        "sharing": "silo",
                        "description": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(components),
        ),
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].description is None
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].description is None


def test_hosting_and_store_stage_edits_preserve_omitted_research_disclosure() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        product="Cloud Run",
        research_disclosure=ResearchDisclosure.EXTERNAL,
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id)),),
    )
    revised_constraints = merge_stage_revision(
        constraints,
        build_stage_revision_context(constraints),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "hosting",
                    "row_id": hosting.id,
                    "row": {
                        "id": hosting.id,
                        "facet": hosting.facet,
                        "value": "per-request",
                        "product": hosting.product,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(constraints),
        ),
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        product="PostgreSQL",
        research_disclosure=ResearchDisclosure.LOCAL,
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, store.id)),),
    )
    revised_components = merge_stage_revision(
        components,
        build_stage_revision_context(components),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "stores",
                    "row_id": store.id,
                    "row": {
                        "id": store.id,
                        "category": store.category,
                        "sharing": "silo",
                        "product": store.product,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(components),
        ),
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].research_disclosure is ResearchDisclosure.EXTERNAL
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].research_disclosure is ResearchDisclosure.LOCAL


def test_hosting_and_store_stage_edits_clear_explicit_null_research_disclosure() -> None:
    hosting = HostingRow(
        "hosting-compute",
        "compute",
        "managed-cloud",
        product="Cloud Run",
        research_disclosure=ResearchDisclosure.EXTERNAL,
    )
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="# Constraints\n",
        hosting=(hosting,),
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id)),),
    )
    revised_constraints = merge_stage_revision(
        constraints,
        build_stage_revision_context(constraints),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "hosting",
                    "row_id": hosting.id,
                    "row": {
                        "id": hosting.id,
                        "facet": hosting.facet,
                        "value": "per-request",
                        "research_disclosure": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(constraints),
        ),
    )

    store = StoreRow(
        "store-orders",
        "relational",
        "shared",
        product="PostgreSQL",
        research_disclosure=ResearchDisclosure.EXTERNAL,
    )
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        stores=(store,),
        components=(),
        decisions=(),
        body="# Components\n",
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, store.id)),),
    )
    revised_components = merge_stage_revision(
        components,
        build_stage_revision_context(components),
        parse_stage_revision_operations(
            _stage_operations(
                {
                    "op": "edit-row",
                    "feedback_id": _FEEDBACK_ID,
                    "row_type": "stores",
                    "row_id": store.id,
                    "row": {
                        "id": store.id,
                        "category": store.category,
                        "sharing": "silo",
                        "research_disclosure": None,
                    },
                },
                _stage_response(),
            ),
            build_stage_revision_context(components),
        ),
    )

    assert isinstance(revised_constraints, ConstraintsArtifact)
    assert revised_constraints.hosting[0].research_disclosure is None
    assert isinstance(revised_components, ComponentsArtifact)
    assert revised_components.stores[0].research_disclosure is None


def test_store_operations_reject_row_prose_amendments() -> None:
    store = StoreRow("store-main", "database", "shared")
    context = _stage_context(
        artifact_key="components",
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=store.id,
                target_row_type="stores",
                allow_edit=True,
                allow_remove=True,
            ),
        ),
        live_rows=(StageLiveRow("stores", store),),
    )
    edit = {
        "op": "edit-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "stores",
        "row_id": store.id,
        "row": {"id": store.id, "category": "database", "sharing": "isolated"},
        "prose_amendment": {
            "action": "replace",
            "row_id": store.id,
            "span_id": "no-span",
            "replacement": "never accepted",
        },
    }

    with pytest.raises(RevisionContractError, match="cannot carry a prose"):
        parse_stage_revision_operations(_stage_operations(edit, _stage_response()), context)


def test_prose_inventory_operations_require_one_row_owned_amendment() -> None:
    add_context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),)
    )
    for record, context in (
        (_add_entity(prose_amendment=None), add_context),
        (_edit_entity(prose_amendment=None), _stage_context()),
        (_remove_entity(prose_amendment=None), _stage_context()),
        (_edit_entity(body="general body replacement"), _stage_context()),
    ):
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_stage_row_prose_replacement_keeps_its_edited_row_id() -> None:
    record = _edit_entity()
    assert record["prose_amendment"] is not None
    record["prose_amendment"]["replacement"] = "The revised row has no identifier."

    with pytest.raises(RevisionContractError, match="must name its edited row id"):
        parse_stage_revision_operations(_stage_operations(record, _stage_response()), _stage_context())


def test_stage_material_operations_precede_feedback_responses_and_preserve_order() -> None:
    feedback_two = "feedback-two"
    context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),
            StageFeedbackAuthority(feedback_two, allow_add=True),
        )
    )
    second = _add_entity(feedback_two, row=_entity_payload("entity-second"))
    second["prose_amendment"] = {
        "action": "append",
        "row_id": "entity-second",
        "fragment": "entity-second is another entity.",
    }
    parsed = parse_stage_revision_operations(
        _stage_operations(_add_entity(), second, _stage_response(), _stage_response(feedback_two)),
        context,
    )
    assert [item.row.id for item in parsed.material_operations] == [
        "entity-new",
        "entity-second",
    ]

    with pytest.raises(RevisionContractError, match="before feedback responses"):
        parse_stage_revision_operations(
            _stage_operations(_stage_response(), _add_entity(), _stage_response(feedback_two)),
            context,
        )


def test_stage_envelope_requires_one_ordered_response_for_each_active_feedback() -> None:
    feedback_two = "feedback-two"
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID), StageFeedbackAuthority(feedback_two))
    )
    for records in (
        (_stage_response(),),
        (_stage_response(feedback_two), _stage_response()),
        (_stage_response(), _stage_response()),
        (_stage_response(), _stage_response("unknown")),
    ):
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(*records), context)


def test_stage_envelope_rejects_duplicate_live_targets_and_added_row_follow_ups() -> None:
    feedback_two = "feedback-two"
    context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=_TARGET_ID,
                target_row_type="entities",
                allow_edit=True,
            ),
            StageFeedbackAuthority(
                feedback_two,
                target_row_id=_TARGET_ID,
                target_row_type="entities",
                allow_remove=True,
            ),
        )
    )
    with pytest.raises(RevisionContractError, match="already has a material"):
        parse_stage_revision_operations(
            _stage_operations(
                _edit_entity(),
                _remove_entity(feedback_two),
                _stage_response(),
                _stage_response(feedback_two),
            ),
            context,
        )

    add_context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),
            StageFeedbackAuthority(
                feedback_two,
                target_row_id="entity-new",
                target_row_type="entities",
                allow_edit=True,
            ),
        )
    )
    follow_up = _edit_entity(feedback_two, row_id="entity-new", row=_entity_payload("entity-new"))
    follow_up["prose_amendment"] = {
        "action": "replace",
        "row_id": "entity-new",
        "span_id": "none",
        "replacement": "not available",
    }
    with pytest.raises(RevisionContractError):
        parse_stage_revision_operations(
            _stage_operations(_add_entity(), follow_up, _stage_response(), _stage_response(feedback_two)),
            add_context,
        )


def test_stage_envelope_rejects_limits_and_second_material_operation_with_split_action() -> None:
    response_context = _stage_context(limits=StageFeedbackLimits(32, 80, 80))
    oversized = _stage_operations(_stage_response(proposed_response="x" * 100))
    with pytest.raises(StageRevisionLimitError, match=STAGE_SPLIT_FEEDBACK_ACTION) as error:
        parse_stage_revision_operations(oversized, response_context)
    assert error.value.invalid is True
    assert error.value.retryable is False
    assert error.value.measured > error.value.limit

    prose_context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        limits=StageFeedbackLimits(32, 10_000, 10),
    )
    record = _add_entity()
    record["prose_amendment"] = {
        "action": "append",
        "row_id": "entity-new",
        "fragment": "entity-new " + "x" * 20,
    }
    with pytest.raises(RevisionContractError, match=_FEEDBACK_ID):
        parse_stage_revision_operations(_stage_operations(record, _stage_response()), prose_context)

    duplicate_context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                allow_add=True,
                target_row_id=_TARGET_ID,
                target_row_type="entities",
                allow_edit=True,
            ),
        )
    )
    with pytest.raises(StageRevisionLimitError, match=STAGE_SPLIT_FEEDBACK_ACTION) as error:
        parse_stage_revision_operations(
            _stage_operations(_add_entity(), _edit_entity(), _stage_response()), duplicate_context
        )
    assert error.value.invalid is True
    assert error.value.retryable is False
    assert error.value.feedback_id == _FEEDBACK_ID
    assert error.value.measured == 2
    assert error.value.limit == 1


def test_stage_material_operation_limit_counts_the_actual_occurrence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(roadmap_revision, "STAGE_MAX_MATERIAL_OPERATIONS_PER_FEEDBACK", 2)
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
    )

    def addition(row_id: str) -> dict[str, object]:
        return _add_entity(
            row=_entity_payload(row_id),
            prose_amendment={
                "action": "append",
                "row_id": row_id,
                "fragment": f"{row_id} is the new domain entity.",
            },
        )

    with pytest.raises(StageRevisionLimitError) as error:
        parse_stage_revision_operations(
            _stage_operations(
                addition("entity-one"),
                addition("entity-two"),
                addition("entity-three"),
                _stage_response(),
            ),
            context,
        )

    assert error.value.measured == 3
    assert error.value.limit == 2


def test_stage_addition_checks_the_full_frozen_live_id_inventory() -> None:
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        live_rows=(),
        predecessor_relation_ids=frozenset({"entity-unselected"}),
    )
    record = _add_entity(row=_entity_payload("entity-unselected"))
    record["prose_amendment"] = {
        "action": "append",
        "row_id": "entity-unselected",
        "fragment": "entity-unselected stays frozen outside this feedback target.",
    }

    with pytest.raises(RevisionContractError, match="frozen live row"):
        parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_stage_addition_requires_a_whole_row_id_in_its_prose_fragment() -> None:
    context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
    )
    record = _add_entity()
    record["prose_amendment"] = {
        "action": "append",
        "row_id": "entity-new",
        "fragment": "entity-newer is a different identifier.",
    }

    with pytest.raises(RevisionContractError, match="must name its added row id"):
        parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_plan_addition_requires_one_predecessor_only_ordering_companion() -> None:
    plan = {
        "id": "new-plan",
        "title": "New plan",
        "disposition": "keep",
        "component_ids": ["component-predecessor"],
        "draft_seed_path": "plan-seed-drafts/new-plan.md",
        "sizing_rationale": "A small bounded slice.",
    }
    context = _stage_context(
        artifact_key="plans",
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        live_rows=(),
        predecessor_relation_ids=frozenset({"component-predecessor"}),
        predecessor_plan_ids=("earlier-plan",),
    )
    base = {
        "op": "add-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "plans",
        "row": plan,
        "prose_amendment": {
            "action": "append",
            "row_id": "new-plan",
            "fragment": "new-plan delivers the next bounded slice.",
        },
        "ordering": {"plan_id": "new-plan", "depends_on": ["earlier-plan"]},
    }
    parsed = parse_stage_revision_operations(
        _stage_operations(base, _stage_response()), context
    )
    assert parsed.material_operations[0].ordering == OrderingEntry(
        "new-plan", ("earlier-plan",), ()
    )

    for record in (
        base | {"ordering": None},
        base | {"ordering": {"plan_id": "other"}},
        base | {"ordering": {"plan_id": "new-plan", "depends_on": ["new-plan"]}},
    ):
        with pytest.raises(RevisionContractError):
            parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_new_row_relations_use_predecessor_ids_and_existing_relations_cannot_retarget() -> None:
    add_context = _stage_context(
        active_feedback=(StageFeedbackAuthority(_FEEDBACK_ID, allow_add=True),),
        predecessor_relation_ids=frozenset({"entity-predecessor"}),
    )
    related_add = _add_entity(
        row=_entity_payload(
            fields=[
                {"name": "parent", "type": "reference", "entity_id": "entity-new"}
            ]
        )
    )
    with pytest.raises(RevisionContractError, match="predecessor"):
        parse_stage_revision_operations(_stage_operations(related_add, _stage_response()), add_context)

    non_reference_metadata = _add_entity(
        row=_entity_payload(
            fields=[{"name": "rank", "type": "number", "entity_id": "entity-new"}]
        )
    )
    parsed = parse_stage_revision_operations(
        _stage_operations(non_reference_metadata, _stage_response()), add_context
    )
    added = parsed.material_operations[0]
    assert isinstance(added, roadmap_revision.AddRowOperation)
    assert added.row.fields[0].entity_id == "entity-new"
    assert added.row.fields[0].type is FieldType.NUMBER

    component = ComponentRow(
        "component-order",
        "Orders",
        ("entity-predecessor",),
        ("pattern-one",),
        ("constraint-one",),
        ("store-one",),
    )
    context = _stage_context(
        artifact_key="components",
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=component.id,
                target_row_type="components",
                allow_edit=True,
            ),
        ),
        live_rows=(StageLiveRow("components", component, "span-component"),),
    )
    retarget = {
        "op": "edit-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "components",
        "row_id": component.id,
        "row": {
            "id": component.id,
            "name": "Orders",
            "entity_ids": ["entity-predecessor"],
            "pattern_ids": ["pattern-one"],
            "constraint_ids": ["constraint-one"],
            "store_ids": ["store-two"],
        },
        "prose_amendment": {
            "action": "replace",
            "row_id": component.id,
            "span_id": "span-component",
            "replacement": "component-order uses its original store.",
        },
    }
    with pytest.raises(RevisionContractError, match="preserve every declared relation"):
        parse_stage_revision_operations(_stage_operations(retarget, _stage_response()), context)


@pytest.mark.parametrize(
    ("row_type", "current", "replacement"),
    (
        (
            "entities",
            EntityRow(
                "entity-order",
                "Order",
                (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),),
            ),
            {
                "id": "entity-order",
                "name": "Order",
                "fields": [
                    {"name": "customer", "type": "reference", "entity_id": "entity-account"}
                ],
            },
        ),
        (
            "entities",
            EntityRow("entity-order", "Order", (FieldRow("rank", FieldType.NUMBER),)),
            {
                "id": "entity-order",
                "name": "Order",
                "fields": [{"name": "rank", "type": "text"}],
            },
        ),
        (
            "business_rules",
            BusinessRuleRow("rule-order", "Order must validate.", ("entity-order",)),
            {"id": "rule-order", "statement": "Order must validate.", "entity_ids": ["entity-account"]},
        ),
        (
            "workflows",
            WorkflowRow("workflow-order", "Order flow", ("entity-order",)),
            {"id": "workflow-order", "name": "Order flow", "entity_ids": ["entity-account"]},
        ),
        (
            "decisions",
            DecisionRow("decision-order", "Keep", (), "Bounded.", "entity-order", DecisionStatus.PENDING),
            {
                "id": "decision-order",
                "chosen_option": "Keep",
                "rejected_alternatives": [],
                "rationale": "Bounded.",
                "anchor": "entity-account",
                "status": "pending",
            },
        ),
        (
            "constraints",
            ConstraintRow("constraint-order", "Protect orders.", "security", ("entity-order",)),
            {
                "id": "constraint-order",
                "statement": "Protect orders.",
                "attribute": "security",
                "anchor_ids": ["entity-account"],
            },
        ),
        (
            "components",
            ComponentRow("component-order", "Orders", ("entity-order",), ("pattern-order",), ("constraint-order",), ("store-order",)),
            {
                "id": "component-order",
                "name": "Orders",
                "entity_ids": ["entity-account"],
                "pattern_ids": ["pattern-order"],
                "constraint_ids": ["constraint-order"],
                "store_ids": ["store-order"],
            },
        ),
        (
            "components",
            ComponentRow("component-pattern", "Orders", ("entity-order",), ("pattern-order",), ("constraint-order",), ("store-order",)),
            {
                "id": "component-pattern",
                "name": "Orders",
                "entity_ids": ["entity-order"],
                "pattern_ids": ["pattern-account"],
                "constraint_ids": ["constraint-order"],
                "store_ids": ["store-order"],
            },
        ),
        (
            "components",
            ComponentRow("component-constraint", "Orders", ("entity-order",), ("pattern-order",), ("constraint-order",), ("store-order",)),
            {
                "id": "component-constraint",
                "name": "Orders",
                "entity_ids": ["entity-order"],
                "pattern_ids": ["pattern-order"],
                "constraint_ids": ["constraint-account"],
                "store_ids": ["store-order"],
            },
        ),
        (
            "components",
            ComponentRow("component-store", "Orders", ("entity-order",), ("pattern-order",), ("constraint-order",), ("store-order",)),
            {
                "id": "component-store",
                "name": "Orders",
                "entity_ids": ["entity-order"],
                "pattern_ids": ["pattern-order"],
                "constraint_ids": ["constraint-order"],
                "store_ids": ["store-account"],
            },
        ),
        (
            "plans",
            PlanRow("plan-order", "Orders", PlanDisposition.KEEP, ("component-order",), "plan-seed-drafts/plan-order.md", "Bounded."),
            {
                "id": "plan-order",
                "title": "Orders",
                "disposition": "keep",
                "component_ids": ["component-account"],
                "draft_seed_path": "plan-seed-drafts/plan-order.md",
                "sizing_rationale": "Bounded.",
            },
        ),
        (
            "assumptions",
            AssumptionRow("assumption-order", "The order plan lands first.", ("plan-order",)),
            {
                "id": "assumption-order",
                "statement": "The order plan lands first.",
                "consuming_plan_ids": ["plan-account"],
            },
        ),
    ),
)
def test_existing_relation_fields_cannot_be_retargeted(
    row_type: str, current: object, replacement: dict[str, object]
) -> None:
    row_id = current.id  # type: ignore[union-attr]
    context = _stage_context(
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=row_id,
                target_row_type=row_type,  # type: ignore[arg-type]
                allow_edit=True,
            ),
        ),
        live_rows=(StageLiveRow(row_type, current, "span-relation"),),  # type: ignore[arg-type]
    )
    record = {
        "op": "edit-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": row_type,
        "row_id": row_id,
        "row": replacement,
        "prose_amendment": {
            "action": "replace",
            "row_id": row_id,
            "span_id": "span-relation",
            "replacement": f"{row_id} keeps its declared relation.",
        },
    }

    with pytest.raises(RevisionContractError, match="preserve every declared relation"):
        parse_stage_revision_operations(_stage_operations(record, _stage_response()), context)


def test_stage_context_includes_only_open_feedback_in_predecessor_order() -> None:
    artifact = _artifact(
        feedback=(
            _feedback(feedback_id="feedback-first"),
            _feedback(feedback_id="feedback-deferred", state=FeedbackState.DEFERRED),
            _feedback(
                feedback_id="feedback-retained",
                state=FeedbackState.AWAITING_REVIEW,
                proposed_response="Keep the earlier answer for review.",
            ),
            _feedback(feedback_id="feedback-last"),
        )
    )

    context = build_stage_revision_context(artifact)

    assert [authority.feedback_id for authority in context.active_feedback] == [
        "feedback-first",
        "feedback-last",
    ]
    assert [authority.request for authority in context.active_feedback] == [
        "Use the customer-facing order name.",
        "Use the customer-facing order name.",
    ]


def test_stage_context_accepts_reopened_feedback_with_a_prior_response() -> None:
    context = build_stage_revision_context(
        _artifact(feedback=(_feedback(proposed_response="Reconsider this answer."),))
    )

    assert context.active_feedback[0].feedback_id == _FEEDBACK_ID
    assert context.active_feedback[0].request == "Use the customer-facing order name."


@pytest.mark.parametrize(
    "feedback",
    (
        (_feedback(), _feedback()),
        (
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, "missing-row")
            ),
        ),
    ),
)
def test_stage_context_rejects_duplicate_feedback_and_unresolvable_row_targets(
    feedback: tuple[FeedbackRow, ...],
) -> None:
    with pytest.raises(RevisionContractError, match="unique|exactly one"):
        build_stage_revision_context(_artifact(feedback=feedback))


def test_stage_context_binds_each_feedback_to_its_authority_matrix_operations() -> None:
    artifact = _artifact(
        feedback=(
            _feedback(
                feedback_id="feedback-artifact",
                target=FeedbackTarget(FeedbackTargetKind.ARTIFACT),
            ),
            _feedback(feedback_id="feedback-live"),
            _feedback(
                feedback_id="feedback-removal",
                target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-removed"),
            ),
        ),
        removals=(RemovalRecord("entity-removed", "Superseded.", ("old-feedback",)),),
    )

    context = build_stage_revision_context(artifact)
    authorities = {authority.feedback_id: authority for authority in context.active_feedback}

    assert authorities["feedback-artifact"].allowed_operation_kinds == (
        "add-row",
        "respond-feedback",
    )
    assert authorities["feedback-live"].allowed_operation_kinds == ("respond-feedback",)
    assert authorities["feedback-live"].target_row_type == "entities"
    assert authorities["feedback-removal"].allowed_operation_kinds == (
        "respond-feedback",
    )
    assert authorities["feedback-removal"].target is not None
    assert authorities["feedback-removal"].target.row_id == "entity-removed"


def test_stage_context_rejects_more_than_its_effective_active_feedback_limit_before_prompt_or_invocation() -> None:
    artifact = _artifact(
        feedback=(
            _feedback(feedback_id="feedback-one"),
            _feedback(feedback_id="feedback-two"),
        )
    )

    with pytest.raises(StageRevisionLimitError, match=STAGE_SPLIT_FEEDBACK_ACTION) as error:
        build_stage_revision_context(artifact, limits=StageFeedbackLimits(1, 100, 100))

    assert error.value.measured == 2
    assert error.value.limit == 1


def test_stage_context_exposes_selected_typed_rows_without_artifact_or_body() -> None:
    selected = EntityRow("entity-order", "Order", ())
    untouched = EntityRow("entity-customer", "Customer", ())
    artifact = _artifact(
        entities=(selected, untouched),
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, selected.id)),),
    )

    context = build_stage_revision_context(artifact)

    assert context.live_rows == (StageLiveRow("entities", selected, None),)
    assert not hasattr(context, "body")
    assert all(value is not artifact for value in vars(context).values())


def test_stage_context_preserves_hosting_and_store_identity_only_exceptions() -> None:
    hosting = HostingRow("hosting-primary", "region", "us-east-1")
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="hosting-primary appears only in prose.",
        hosting=(hosting,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, hosting.id),
            ),
        ),
    )
    store = StoreRow("store-primary", "relational", "shared")
    components = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        components=(),
        decisions=(),
        body="store-primary appears only in prose.",
        stores=(store,),
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, store.id),
            ),
        ),
    )

    hosting_context = build_stage_revision_context(constraints)
    store_context = build_stage_revision_context(components)

    assert hosting_context.live_rows == (StageLiveRow("hosting", hosting, None),)
    assert store_context.live_rows == (StageLiveRow("stores", store, None),)
    assert hosting_context.active_feedback[0].allowed_operation_kinds == (
        "edit-row",
        "respond-feedback",
    )
    assert store_context.active_feedback[0].allowed_operation_kinds == (
        "edit-row",
        "remove-row-with-record",
        "respond-feedback",
    )
    assert not hosting_context.prose_spans
    assert not store_context.prose_spans


def _context_components_artifact(
    *, feedback: tuple[FeedbackRow, ...], body: str = "component-orders owns order work.\n"
) -> ComponentsArtifact:
    return ComponentsArtifact(
        system_patterns=(PatternRow("pattern-system", "Layered", "Keep layers."),),
        component_patterns=(),
        components=(
            ComponentRow(
                "component-orders",
                "Orders",
                ("entity-order",),
                ("pattern-system",),
                (),
                ("store-orders",),
            ),
        ),
        decisions=(),
        body=body,
        stores=(StoreRow("store-orders", "relational", "shared"),),
        feedback=feedback,
    )


def test_stage_context_projects_incident_relations_and_predecessor_reference_ids() -> None:
    domain = _artifact(
        entities=(EntityRow("entity-order", "Order", ()),), feedback=()
    )
    components = _context_components_artifact(
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, "component-orders")
            ),
        )
    )

    context = build_stage_revision_context(components, (domain,))

    assert context.predecessor_reference_ids == frozenset(
        {"entity-order", "pattern-system", "component-orders", "store-orders"}
    )
    assert [
        (relation.kind, relation.owner_id, relation.endpoint_id)
        for relation in context.incident_relations
    ] == [
        (RelationKind.COMPONENT_ENTITY, "component-orders", "entity-order"),
        (RelationKind.COMPONENT_PATTERN, "component-orders", "pattern-system"),
        (RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
    ]


def test_store_removal_context_exposes_incoming_component_store_references() -> None:
    components = _context_components_artifact(
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ROW, "store-orders")
            ),
        )
    )

    context = build_stage_revision_context(components)

    assert [
        (relation.kind, relation.owner_id, relation.endpoint_id)
        for relation in context.relations
    ] == [
        (RelationKind.COMPONENT_STORE, "component-orders", "store-orders"),
    ]


def test_stage_context_admits_only_predecessor_relation_targets_for_every_added_row_type() -> None:
    artifact = _artifact(
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ARTIFACT)),
        )
    )
    context = build_stage_revision_context(artifact)
    same_envelope_target = _add_entity(
        row=_entity_payload(
            fields=[
                {"name": "parent", "type": "reference", "entity_id": "entity-new"}
            ]
        )
    )

    assert "entity-order" in context.predecessor_reference_ids
    assert "entity-new" not in context.predecessor_reference_ids
    with pytest.raises(RevisionContractError, match="frozen predecessor"):
        parse_stage_revision_operations(
            _stage_operations(same_envelope_target, _stage_response()), context
        )
    with pytest.raises(RevisionContractError, match="downstream"):
        build_stage_revision_context(artifact, (_context_components_artifact(feedback=()),))


def test_row_owned_span_projection_returns_all_unambiguous_selected_blocks() -> None:
    artifact = _artifact(
        entities=(
            EntityRow("entity-order", "Order", ()),
            EntityRow("entity-customer", "Customer", ()),
            EntityRow("entity-invoice", "Invoice", ()),
        ),
        feedback=(),
    )
    artifact = DomainArtifact(
        artifact.entities,
        artifact.business_rules,
        artifact.workflows,
        artifact.decisions,
        (
            "entity-order owns the first block.\n\n"
            "entity-customer owns this block.\n\n"
            "entity-order owns the second block.\n\n"
            "entity-order and entity-invoice share this block.\n"
        ),
        artifact.feedback,
        artifact.removals,
    )

    spans = project_row_owned_prose_spans(artifact, {"entity-order", "entity-customer"})

    assert [(span.row_id, span.text) for span in spans] == [
        ("entity-order", "entity-order owns the first block.\n"),
        ("entity-customer", "entity-customer owns this block.\n"),
        ("entity-order", "entity-order owns the second block.\n"),
    ]


def _domain_with_body(
    body: str,
    entities: tuple[EntityRow, ...],
    removals: tuple[RemovalRecord, ...] = (),
) -> DomainArtifact:
    base = _artifact(entities=entities, feedback=(), removals=removals)
    return DomainArtifact(
        base.entities,
        base.business_rules,
        base.workflows,
        base.decisions,
        body,
        base.feedback,
        base.removals,
    )


_THREE_ENTITIES = (
    EntityRow("entity-order", "Order", ()),
    EntityRow("entity-customer", "Customer", ()),
    EntityRow("entity-invoice", "Invoice", ()),
)


def test_shared_block_naming_two_visible_live_rows_is_issued_with_both_owners() -> None:
    artifact = _domain_with_body(
        "entity-order and entity-customer share this decisions paragraph.\n",
        _THREE_ENTITIES,
    )

    spans = project_row_owned_prose_spans(artifact, {"entity-order", "entity-customer"})

    assert len(spans) == 1
    assert spans[0].owning_row_ids == ("entity-customer", "entity-order")
    assert spans[0].is_shared


def test_shared_span_id_binds_the_whole_owning_set_and_text() -> None:
    text = "entity-order and entity-customer share this.\n"
    pair = stage_prose_span_id("entity-customer", text, owning_row_ids=("entity-customer", "entity-order"))
    triple = stage_prose_span_id(
        "entity-customer", text, owning_row_ids=("entity-customer", "entity-invoice", "entity-order")
    )
    edited = stage_prose_span_id("entity-customer", text + "x", owning_row_ids=("entity-customer", "entity-order"))

    assert len({pair, triple, edited}) == 3


def test_single_owner_span_id_is_unchanged_by_shared_issuance() -> None:
    text = "entity-order owns this block.\n"
    artifact = _domain_with_body(text, _THREE_ENTITIES)

    (span,) = project_row_owned_prose_spans(artifact, {"entity-order"})

    assert span.owning_row_ids == ("entity-order",)
    assert not span.is_shared
    assert span.span_id == stage_prose_span_id("entity-order", text)


def test_shared_block_over_the_byte_cap_is_not_issued_but_a_single_owner_block_still_is() -> None:
    """A shared block over the cap could never be replaced under the correction ceiling, so it is not issued; legacy single-owner issuance is unchanged."""
    filler = "x" * SHARED_SPAN_MAX_BYTES
    shared = _domain_with_body(f"entity-order and entity-customer {filler}\n", _THREE_ENTITIES)
    single = _domain_with_body(f"entity-order {filler}\n", _THREE_ENTITIES)

    assert project_row_owned_prose_spans(shared, {"entity-order", "entity-customer"}) == ()
    assert len(project_row_owned_prose_spans(single, {"entity-order"})) == 1


def test_shared_span_cap_equals_the_correction_replacement_ceiling() -> None:
    """The two limits are separate constants by design; a block larger than the ceiling is unreplaceable."""
    from plan_tool.roadmap_candidate import CORRECT_PROSE_MAX_REPLACEMENT_BYTES

    assert SHARED_SPAN_MAX_BYTES == CORRECT_PROSE_MAX_REPLACEMENT_BYTES


def test_shared_block_is_not_issued_when_an_owner_is_not_visible() -> None:
    artifact = _domain_with_body(
        "entity-order and entity-invoice share this block.\n", _THREE_ENTITIES
    )

    assert project_row_owned_prose_spans(artifact, {"entity-order"}) == ()


def test_removed_row_reference_neither_joins_nor_is_required_of_the_owning_set() -> None:
    removals = (RemovalRecord("entity-gone", "Removed by an earlier review.", ("old-feedback",)),)
    one_live = _domain_with_body(
        "entity-order replaced entity-gone in this paragraph.\n", _THREE_ENTITIES, removals
    )
    two_live = _domain_with_body(
        "entity-order and entity-customer replaced entity-gone.\n", _THREE_ENTITIES, removals
    )

    (single,) = project_row_owned_prose_spans(one_live, {"entity-order"})
    (shared,) = project_row_owned_prose_spans(two_live, {"entity-order", "entity-customer"})

    assert single.owning_row_ids == ("entity-order",)
    assert shared.owning_row_ids == ("entity-customer", "entity-order")


def test_block_naming_an_ambiguous_duplicate_live_id_is_not_issued() -> None:
    artifact = _domain_with_body(
        "entity-order and entity-customer share this block.\n",
        (*_THREE_ENTITIES, EntityRow("entity-customer", "Customer again", ())),
    )

    assert project_row_owned_prose_spans(artifact, {"entity-order", "entity-customer"}) == ()


def test_local_revision_selector_still_refuses_a_shared_block() -> None:
    artifact = _domain_with_body(
        "entity-order and entity-customer share this paragraph.\n\nentity-order owns this one.\n",
        _THREE_ENTITIES,
    )
    artifact = DomainArtifact(
        artifact.entities,
        artifact.business_rules,
        artifact.workflows,
        artifact.decisions,
        artifact.body,
        (_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-order")),),
        artifact.removals,
    )

    context = build_stage_revision_context(artifact)

    assert [span.text for span in context.prose_spans] == ["entity-order owns this one.\n"]


def test_row_owned_span_projection_does_not_treat_identity_only_store_as_competing_design_row() -> None:
    artifact = ComponentsArtifact(
        system_patterns=(),
        component_patterns=(),
        components=(ComponentRow("component-orders", "Orders", (), (), (), ()),),
        decisions=(),
        stores=(StoreRow("store-orders", "relational", "shared"),),
        body="component-orders uses store-orders.\n",
    )

    spans = project_row_owned_prose_spans(artifact, {"component-orders"})

    assert [(span.row_id, span.text) for span in spans] == [
        ("component-orders", "component-orders uses store-orders.\n")
    ]


def test_stage_context_keeps_its_existing_local_prose_selection() -> None:
    artifact = _artifact(
        entities=(
            EntityRow("entity-order", "Order", ()),
            EntityRow("entity-customer", "Customer", ()),
        ),
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-order")),
        ),
    )
    artifact = DomainArtifact(
        artifact.entities,
        artifact.business_rules,
        artifact.workflows,
        artifact.decisions,
        "entity-order has an isolated paragraph.\n\nentity-customer remains separate.\n",
        artifact.feedback,
        artifact.removals,
    )

    context = build_stage_revision_context(artifact)

    assert len(context.prose_spans) == 1
    span = context.prose_spans[0]
    assert span.row_id == "entity-order"
    assert span.text == "entity-order has an isolated paragraph.\n"
    assert context.live_rows[0].prose_span_id == span.span_id


@pytest.mark.parametrize(
    "body",
    (
        "entity-order and entity-customer share this paragraph.\n",
        "entity-customer owns the only paragraph.\n",
        "entity-order owns the complete body.\n",
    ),
)
def test_stage_context_omits_ambiguous_shared_overlapping_and_cross_target_prose_spans(
    body: str,
) -> None:
    artifact = _artifact(
        entities=(
            EntityRow("entity-order", "Order", ()),
            EntityRow("entity-customer", "Customer", ()),
        ),
        feedback=(
            _feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-order")),
        ),
    )
    artifact = DomainArtifact(
        artifact.entities,
        artifact.business_rules,
        artifact.workflows,
        artifact.decisions,
        body,
        artifact.feedback,
        artifact.removals,
    )

    context = build_stage_revision_context(artifact)

    assert context.live_rows[0].prose_span_id is None
    assert not context.prose_spans
    assert context.active_feedback[0].allowed_operation_kinds == ("respond-feedback",)


def test_plans_stage_context_preserves_ordering_and_blocks_nonpredecessor_companions() -> None:
    existing = PlanRow(
        "plan-existing",
        "Existing plan",
        PlanDisposition.KEEP,
        (),
        "plan-seed-drafts/existing.md",
        "Keep the first slice bounded.",
    )
    artifact = PlansArtifact(
        plans=(existing,),
        ordering=(OrderingEntry(existing.id),),
        assumptions=(),
        decisions=(),
        body="plan-existing is the initial delivery.\n",
        feedback=(
            _feedback(
                target=FeedbackTarget(FeedbackTargetKind.ARTIFACT),
            ),
        ),
    )

    context = build_stage_revision_context(artifact)

    assert context.ordering_entries == (OrderingEntry(existing.id),)
    assert context.predecessor_plan_ids == (existing.id,)
    assert "reorder" not in context.active_feedback[0].allowed_operation_kinds
    assert "retarget-relation" not in context.active_feedback[0].allowed_operation_kinds


def test_stack_policy_fixes_concern_and_allows_add_but_never_removal() -> None:
    """A candidate may introduce the stack (unlike hosting) but can never drop a
    row, so a recorded stack cannot silently read as 'stack not recorded'."""
    from plan_tool.roadmap_artifacts import stage_row_operation_policy

    stack = stage_row_operation_policy("stack")
    assert stack.allow_add is True
    assert stack.allow_remove is False
    assert stack.immutable_fields == ("concern",)
    assert stage_row_operation_policy("hosting").allow_add is False


def test_constraints_stage_allows_stack_additions_and_domain_does_not() -> None:
    assert "stack" in roadmap_revision._STAGE_ADD_ROW_TYPES["constraints"]
    assert "stack" not in roadmap_revision._STAGE_ADD_ROW_TYPES["domain"]


def test_stack_is_a_targetable_collection_that_can_be_edited_but_never_removed() -> None:
    """Feedback naming a stack row gets a ``stack`` live row with edit but no
    remove-with-record authority; a stack-less artifact exposes no stack rows."""
    from plan_tool.roadmap_artifacts import StackRow

    stack = StackRow("stack-platform", "platform", choice="managed")
    constraints = ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(),
        body="stack-platform appears only in prose.",
        stack=(stack,),
        feedback=(_feedback(target=FeedbackTarget(FeedbackTargetKind.ROW, stack.id)),),
    )

    context = build_stage_revision_context(constraints)

    assert context.live_rows == (StageLiveRow("stack", stack, None),)
    assert context.active_feedback[0].target_row_type == "stack"
    kinds = context.active_feedback[0].allowed_operation_kinds
    assert "edit-row" in kinds
    assert "remove-row-with-record" not in kinds


def test_stack_edit_may_swap_choice_for_open_but_not_change_its_concern() -> None:
    """The fixed-field error names the collection and field, not 'hosting'/'facet'."""
    from plan_tool.roadmap_artifacts import StackRow

    stack = StackRow("stack-platform", "platform", choice="managed")
    context = _stage_context(
        artifact_key="constraints",
        active_feedback=(
            StageFeedbackAuthority(
                _FEEDBACK_ID,
                target_row_id=stack.id,
                target_row_type="stack",
                allow_edit=True,
                allow_remove=False,
                allow_add=True,
            ),
        ),
        live_rows=(StageLiveRow("stack", stack),),
    )
    edit = {
        "op": "edit-row",
        "feedback_id": _FEEDBACK_ID,
        "row_type": "stack",
        "row_id": stack.id,
        "row": {"id": stack.id, "concern": "platform", "open": True},
    }
    parsed = parse_stage_revision_operations(
        _stage_operations(edit, _stage_response()), context
    )
    assert parsed.material_operations[0].row == StackRow(
        "stack-platform", "platform", choice=None, open=True
    )

    moved = edit | {"row": {"id": stack.id, "concern": "store-engine", "open": True}}
    with pytest.raises(RevisionContractError, match="a stack edit must preserve its fixed field 'concern'"):
        parse_stage_revision_operations(_stage_operations(moved, _stage_response()), context)
