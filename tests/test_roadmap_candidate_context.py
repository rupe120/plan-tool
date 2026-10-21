"""Tests for immutable, bounded candidate proposal context."""

from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect
import json

import pytest

from plan_tool import (
    roadmap_candidate,
    roadmap_candidate_context,
    roadmap_candidate_review,
    roadmap_candidate_run,
)
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    AssumptionRow,
    AttributeDispositionRow,
    BusinessRuleRow,
    ComponentRow,
    ComponentsArtifact,
    ConstraintDisposition,
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
    OrderingEntry,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    StoreRow,
    WorkflowRow,
    stage_row_collections,
)
from plan_tool.roadmap_candidate_context import (
    CANDIDATE_CONTEXT_MAX_BYTES,
    CandidateContextCapsule,
    CandidateContextInventoryEntry,
    CandidateContextSourceSpan,
    CandidateContextSourceSpanReceipt,
    build_candidate_context,
    candidate_collection_hints,
    expand_candidate_context,
    is_supported_candidate_context_ceiling,
    rebuild_candidate_context_at_recorded_ceiling,
)
from plan_tool.roadmap_feedback_ledger import (
    DerivedFeedbackContext,
    LedgerState,
    LedgerTarget,
    ProposalFields,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    render_ledger,
    target_fingerprint,
)
from plan_tool.roadmap_impact_relations import ImpactClosure
from plan_tool.roadmap_versions import (
    ResolvedRoadmapVersion,
    create_candidate_version,
    create_root_version,
)


_SELECTOR = "domain:feedback-order"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _artifacts(
    *,
    feedback: FeedbackRow | tuple[FeedbackRow, ...] | None = None,
    domain_body: str | None = None,
) -> tuple[DomainArtifact, ConstraintsArtifact, ComponentsArtifact, PlansArtifact]:
    if feedback is None:
        feedback_rows = (
            FeedbackRow(
                id="feedback-order",
                target=FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                request="Show the order name customers recognize.",
                state=FeedbackState.OPEN,
            ),
        )
    elif isinstance(feedback, tuple):
        feedback_rows = feedback
    else:
        feedback_rows = (feedback,)
    domain = DomainArtifact(
        entities=(
            EntityRow(
                "entity-order",
                "Order",
                (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),),
            ),
            EntityRow("entity-customer", "Customer", ()),
            EntityRow("entity-invoice", "Invoice", ()),
            EntityRow("entity-unrelated", "Unrelated", ()),
        ),
        business_rules=(BusinessRuleRow("rule-order", "Orders require customers.", ("entity-order",)),),
        workflows=(
            WorkflowRow("workflow-order", "Place order", ("entity-order",)),
            WorkflowRow("workflow-invoice", "Issue invoice", ("entity-invoice",)),
        ),
        decisions=(
            DecisionRow(
                "decision-outside",
                "Keep invoice numbering local.",
                (),
                "The order feedback does not change invoice numbering.",
                "entity-invoice",
                DecisionStatus.SETTLED,
            ),
        ),
        body=domain_body
        if domain_body is not None
        else (
            "entity-order owns this first source block.\n\n"
            "entity-order owns this second source block.\n\n"
            "entity-customer owns this source block.\n\n"
            "entity-invoice owns this source block.\n\n"
            "entity-order and entity-unrelated share no ownership.\n"
        ),
        feedback=feedback_rows,
    )
    constraints = ConstraintsArtifact(
        dispositions=(
            AttributeDispositionRow(
                "disposition-security", "security", ConstraintDisposition.PRIORITIZED
            ),
        ),
        constraints=(
            ConstraintRow("constraint-order", "Protect orders.", "security", ("entity-order",)),
        ),
        decisions=(),
        body="constraint-order owns this source block.\n",
    )
    components = ComponentsArtifact(
        system_patterns=(PatternRow("pattern-order", "Order pattern", "Keep orders coherent."),),
        component_patterns=(),
        components=(
            ComponentRow(
                "component-order",
                "Order service",
                ("entity-order",),
                ("pattern-order",),
                ("constraint-order",),
                ("store-order",),
            ),
            ComponentRow(
                "component-invoice",
                "Invoice service",
                ("entity-invoice",),
                (),
                (),
                ("store-invoice",),
            ),
        ),
        decisions=(),
        stores=(
            StoreRow("store-order", "relational", "component-owned", "PostgreSQL"),
            StoreRow("store-invoice", "document", "component-owned", "MongoDB"),
        ),
        body=(
            "component-order owns this source block.\n\n"
            "component-invoice owns this source block.\n"
        ),
    )
    plans = PlansArtifact(
        plans=(
            PlanRow(
                "plan-order",
                "Deliver orders",
                PlanDisposition.KEEP,
                ("component-order",),
                "plan-seed-drafts/plan-order.md",
                "Keep the slice small.",
            ),
            PlanRow(
                "plan-invoice",
                "Deliver invoices",
                PlanDisposition.KEEP,
                ("component-invoice",),
                "plan-seed-drafts/plan-invoice.md",
                "Keep the slice small.",
            ),
        ),
        ordering=(OrderingEntry("plan-order"), OrderingEntry("plan-invoice")),
        assumptions=(
            AssumptionRow("assumption-order", "Orders deploy first.", ("plan-order",)),
        ),
        decisions=(),
        body=(
            "plan-order owns this source block.\n\n"
            "plan-invoice owns this source block.\n"
        ),
    )
    return domain, constraints, components, plans


def _resolved(
    *,
    brief: bytes = b"Recorded brief\n",
    feedback: FeedbackRow | tuple[FeedbackRow, ...] | None = None,
    domain_body: str | None = None,
) -> ResolvedRoadmapVersion:
    artifacts = _artifacts(feedback=feedback, domain_body=domain_body)
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES, artifacts, strict=True)
    )
    record = create_root_version(
        roadmap_slug="storefront",
        brief_digest=_digest(brief),
        artifact_digests=tuple(_digest(data) for data in artifact_bytes),
    )
    return ResolvedRoadmapVersion(record, brief, artifact_bytes)


def _capsule(predecessor: ResolvedRoadmapVersion) -> CandidateContextCapsule:
    outcome = build_candidate_context(predecessor, _SELECTOR)
    assert outcome.refusal is None
    assert outcome.capsule is not None
    return outcome.capsule


def _ledger(
    source: ResolvedRoadmapVersion,
    *,
    state: LedgerState = LedgerState.LEDGER_NATIVE,
    item_ids: tuple[str, ...] = (),
    derived: tuple[DerivedFeedbackContext, ...] = (),
) -> RoadmapFeedbackLedger:
    items = tuple(
        ReviewerFeedbackItem(
            item_id=item_id,
            target=LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="entity-order"),
            request=f"Request {item_id}",
            state=ReviewerItemState.OPEN,
            submitted_against_version_id=source.record.version_id,
            target_fingerprint=target_fingerprint(
                source, LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="entity-order")
            ),
        )
        for item_id in item_ids
    )
    return RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="storefront", ledger_state=state,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(
            predecessor_version_id=source.record.version_id, items=items
        ),) if items else (),
        derived_context=derived,
    )


def test_context_uses_only_the_selected_accepted_predecessor() -> None:
    predecessor = _resolved()
    capsule = _capsule(predecessor)
    unrelated_version = _resolved(brief=b"A different stored brief\n")

    assert capsule.brief == "Recorded brief\n"
    assert unrelated_version.brief_bytes not in capsule.payload
    assert capsule.predecessor.version_id == predecessor.record.version_id


@pytest.mark.parametrize(
    "brief",
    (b"\xff", b"Recorded brief\n"),
)
def test_context_uses_verified_raw_brief_bytes_without_live_fallback(brief: bytes) -> None:
    predecessor = _resolved(brief=brief)
    if brief == b"Recorded brief\n":
        predecessor = replace(
            predecessor,
            record=predecessor.record.model_copy(
                update={"brief_digest": _digest(b"different")}
            ),
        )

    outcome = build_candidate_context(predecessor, _SELECTOR)

    assert outcome.capsule is None
    assert outcome.refusal is not None
    assert outcome.refusal.reason == "invalid-predecessor"


@pytest.mark.parametrize(
    ("selector", "feedback", "reason"),
    (
        ("bad-selector", None, "malformed-feedback-selector"),
        ("unknown:feedback-order", None, "unknown-feedback-artifact"),
        ("domain:missing", None, "feedback-not-found"),
        (
            _SELECTOR,
            (
                FeedbackRow(
                    "feedback-order",
                    FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                    "first",
                    FeedbackState.OPEN,
                ),
                FeedbackRow(
                    "feedback-order",
                    FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                    "second",
                    FeedbackState.OPEN,
                ),
            ),
            "duplicate-feedback",
        ),
        (
            _SELECTOR,
            FeedbackRow(
                "feedback-order",
                FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                "closed",
                FeedbackState.DEFERRED,
            ),
            "feedback-not-open",
        ),
    ),
)
def test_context_requires_exactly_one_open_selected_feedback_row(
    selector: object, feedback: FeedbackRow | tuple[FeedbackRow, ...] | None, reason: str
) -> None:
    outcome = build_candidate_context(_resolved(feedback=feedback), selector)

    assert outcome.capsule is None
    assert outcome.refusal is not None
    assert outcome.refusal.reason == reason


def test_row_and_artifact_targets_build_declared_closure() -> None:
    row_capsule = _capsule(_resolved())
    artifact_feedback = FeedbackRow(
        "feedback-order",
        FeedbackTarget(FeedbackTargetKind.ARTIFACT),
        "Review the domain.",
        FeedbackState.OPEN,
    )
    artifact_capsule = _capsule(_resolved(feedback=artifact_feedback))

    row_ids = {member.identity.row_id for member in row_capsule.full_members}
    artifact_ids = {member.identity.row_id for member in artifact_capsule.full_members}
    assert "entity-unrelated" not in row_ids
    assert {"entity-order", "component-order", "plan-order"} <= row_ids
    assert {"entity-unrelated", "entity-invoice"} <= artifact_ids
    assert [evidence.source_index for evidence in row_capsule.relation_evidence] == sorted(
        evidence.source_index for evidence in row_capsule.relation_evidence
    )


def test_context_includes_settled_decisions_and_exact_row_owned_source_blocks() -> None:
    capsule = _capsule(_resolved())
    members = {member.identity.row_id: member for member in capsule.full_members}

    assert members["decision-outside"].inclusion_reasons == ("settled-decision",)
    assert [span.text for span in members["entity-order"].source_spans] == [
        "entity-order owns this first source block.\n",
        "entity-order owns this second source block.\n",
    ]
    assert not members["entity-order"].source_spans[-1].text.endswith("shared no ownership.\n")


_SHARED_BODY = (
    "entity-order owns this first source block.\n\n"
    "entity-order and entity-customer share this decisions paragraph.\n"
)
_SHARED_OWNERS = ("entity-customer", "entity-order")


def test_shared_span_is_carried_with_its_owning_set_through_the_capsule() -> None:
    capsule = _capsule(_resolved(domain_body=_SHARED_BODY))
    members = {member.identity.row_id: member for member in capsule.full_members}
    receipts = {member.identity.row_id: member for member in capsule.receipt.full_members}
    wire = {
        member["identity"]["row_id"]: member
        for member in json.loads(capsule.payload)["full_members"]
    }

    for row_id in _SHARED_OWNERS:
        shared = [span for span in members[row_id].source_spans if span.owning_row_ids]
        assert [span.owning_row_ids for span in shared] == [_SHARED_OWNERS]
        assert [span.owning_row_ids for span in receipts[row_id].source_spans if span.owning_row_ids] == [
            _SHARED_OWNERS
        ]
        assert [span["owning_row_ids"] for span in wire[row_id]["source_spans"] if "owning_row_ids" in span] == [
            list(_SHARED_OWNERS)
        ]
    assert members["entity-order"].source_spans[-1].span_id == members["entity-customer"].source_spans[-1].span_id


def test_single_owner_span_wire_form_omits_the_owning_set_field() -> None:
    capsule = _capsule(_resolved())
    spans = [
        span
        for member in json.loads(capsule.payload)["full_members"]
        for span in member["source_spans"]
    ]

    assert spans
    assert all("owning_row_ids" not in span for span in spans)


def test_legacy_capsule_without_owning_set_still_loads() -> None:
    span = CandidateContextSourceSpan.model_validate(
        {"row_id": "entity-order", "span_id": "row-prose-x", "text": "t\n", "digest": "d"}
    )
    receipt = CandidateContextSourceSpanReceipt.model_validate(
        {"row_id": "entity-order", "span_id": "row-prose-x", "digest": "d"}
    )

    assert span.owning_row_ids is None
    assert receipt.owning_row_ids is None


def test_oversized_shared_block_is_withheld_instead_of_multiplying_into_the_capsule_ceiling() -> None:
    """A selector capsule repeats a shared span per owner, so a block over the cap is not issued; context building still succeeds."""
    body = f"entity-order and entity-customer share {'x' * (CANDIDATE_CONTEXT_MAX_BYTES // 2 + 1)}\n"
    outcome = build_candidate_context(_resolved(domain_body=body), _SELECTOR)

    assert outcome.refusal is None
    assert outcome.capsule is not None
    assert [
        span.row_id
        for member in outcome.capsule.full_members
        for span in member.source_spans
        if span.owning_row_ids is not None
    ] == []


def test_context_projects_store_nodes_without_offering_unrootable_store_expansion() -> None:
    capsule = _capsule(_resolved())
    members = {member.identity.row_id: member for member in capsule.full_members}
    inventory = {entry.row_id: entry for entry in capsule.inventory}

    assert isinstance(members["store-order"].row, StoreRow)
    assert members["store-order"].source_spans == ()
    assert "store-invoice" not in inventory
    assert all(entry.row_type != "StoreRow" for entry in inventory.values())
    assert any(
        evidence.endpoint.row_id == "store-order" for evidence in capsule.relation_evidence
    )


def test_compact_inventory_has_no_content_or_edit_authority() -> None:
    capsule = _capsule(_resolved())
    inventory = next(entry for entry in capsule.inventory if entry.row_id == "entity-unrelated")

    assert inventory.label == "Unrelated"
    assert set(inventory.model_dump()) == {"artifact_key", "row_type", "row_id", "label", "digest"}
    assert not hasattr(inventory, "row")
    assert not hasattr(inventory, "source_spans")


def test_context_receipt_payload_and_identity_are_repeatable() -> None:
    first = _capsule(_resolved())
    second = _capsule(_resolved())

    assert first.payload == second.payload
    assert first.capsule_identity == second.capsule_identity
    assert first.receipt == second.receipt
    assert first.receipt.payload_bytes == len(first.payload)


def test_context_uses_one_module_owned_ceiling_without_caller_override() -> None:
    capsule = _capsule(_resolved())
    entry = next(entry for entry in capsule.inventory if entry.row_id == "entity-invoice")
    expanded = expand_candidate_context(_resolved(), capsule, entry)

    assert CANDIDATE_CONTEXT_MAX_BYTES == 384 * 1024
    assert capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert expanded.capsule is not None
    assert expanded.capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert "ceiling" not in inspect.signature(build_candidate_context).parameters
    assert "ceiling" not in inspect.signature(expand_candidate_context).parameters


def test_legacy_context_ceiling_remains_exact_for_stored_candidate_lineage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_ceiling = 64 * 1024
    with monkeypatch.context() as scoped:
        scoped.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", legacy_ceiling)
        legacy = _capsule(_resolved())

    entry = next(item for item in legacy.inventory if item.row_id == "entity-invoice")
    expanded = expand_candidate_context(_resolved(), legacy, entry)

    assert legacy.ceiling_bytes == legacy_ceiling
    assert roadmap_candidate_context._capsule_is_intact(legacy)
    assert roadmap_candidate_run._capsule_and_receipt_are_exact(legacy, legacy.receipt)
    assert expanded.capsule is not None
    assert expanded.capsule.ceiling_bytes == legacy_ceiling
    assert json.loads(expanded.capsule.payload)["ceiling_bytes"] == legacy_ceiling


def test_payload_uses_enum_wire_values() -> None:
    payload = json.loads(_capsule(_resolved()).payload)
    serialized = json.dumps(payload, sort_keys=True)

    assert "FieldType.REFERENCE" not in serialized
    assert "PlanDisposition.KEEP" not in serialized
    assert '"reference"' in serialized
    assert '"keep"' in serialized


def test_over_budget_context_reports_complete_membership_without_partial_content() -> None:
    outcome = build_candidate_context(_resolved(brief=b"x" * CANDIDATE_CONTEXT_MAX_BYTES), _SELECTOR)

    assert outcome.capsule is None
    assert outcome.refusal is not None
    assert outcome.refusal.reason == "payload-over-budget"
    assert outcome.refusal.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert outcome.refusal.measured_payload_bytes is not None
    assert outcome.refusal.measured_payload_bytes > CANDIDATE_CONTEXT_MAX_BYTES
    assert outcome.refusal.full_members
    refusal_data = outcome.refusal.model_dump()
    rendered_refusal = json.dumps(refusal_data)
    assert '"row": {' not in rendered_refusal
    assert "owns this source block" not in rendered_refusal


def test_expansion_requires_an_exact_initial_inventory_item_and_rebuilds_closure() -> None:
    predecessor = _resolved()
    capsule = _capsule(predecessor)
    entry = next(item for item in capsule.inventory if item.row_id == "entity-invoice")
    invalid = entry.model_copy(update={"label": "Substituted"})
    forged_inventory = tuple(
        invalid if item == entry else item for item in capsule.inventory
    )
    forged_capsule = capsule.model_copy(
        update={
            "inventory": forged_inventory,
            "receipt": capsule.receipt.model_copy(update={"inventory": forged_inventory}),
        }
    )

    rejected = expand_candidate_context(predecessor, capsule, invalid)
    forged = expand_candidate_context(predecessor, forged_capsule, invalid)
    expanded = expand_candidate_context(predecessor, capsule, entry)

    assert rejected.refusal is not None
    assert rejected.refusal.reason == "invalid-expansion-entry"
    assert forged.refusal is not None
    assert forged.refusal.reason == "invalid-capsule"
    assert expanded.capsule is not None
    expanded_ids = {member.identity.row_id for member in expanded.capsule.full_members}
    assert {"entity-order", "entity-invoice", "component-invoice", "plan-invoice"} <= expanded_ids
    assert "entity-invoice" not in {member.identity.row_id for member in capsule.full_members}


def test_expansion_records_parent_and_refuses_a_second_expansion() -> None:
    predecessor = _resolved()
    capsule = _capsule(predecessor)
    entry = next(item for item in capsule.inventory if item.row_id == "entity-invoice")
    expanded = expand_candidate_context(predecessor, capsule, entry)
    assert expanded.capsule is not None

    second = expand_candidate_context(predecessor, expanded.capsule, entry)

    assert expanded.capsule.expansion is not None
    assert expanded.capsule.expansion.parent_capsule_identity == capsule.capsule_identity
    assert expanded.capsule.expansion.inventory_entry == entry
    assert second.capsule is None
    assert second.refusal is not None
    assert second.refusal.reason == "already-expanded"


def test_invalid_predecessor_or_closure_returns_no_partial_capsule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    malformed = replace(_resolved(), artifact_bytes=(b"not an artifact",) * len(STAGES))
    malformed_result = build_candidate_context(malformed, _SELECTOR)
    monkeypatch.setattr(
        roadmap_candidate_context,
        "resolve_impact_closure",
        lambda *args, **kwargs: ImpactClosure(verdict="unmappable-relation"),
    )
    closure_result = build_candidate_context(_resolved(), _SELECTOR)

    assert malformed_result.capsule is None
    assert malformed_result.refusal is not None
    assert malformed_result.refusal.reason == "invalid-predecessor"
    assert closure_result.capsule is None
    assert closure_result.refusal is not None
    assert closure_result.refusal.reason == "incomplete-closure"


def test_batch_snapshots_all_eligible_items_and_source_local_derived_context() -> None:
    root = _resolved()
    current = DerivedFeedbackContext(
        source_version_id=root.record.version_id, context_id="current", content="Current derived context"
    )
    other = DerivedFeedbackContext(
        source_version_id="a" * 64, context_id="other", content="Old derived context"
    )

    outcome = build_candidate_context(root, None, _ledger(
        root, item_ids=("review-b", "review-a"), derived=(current, other)
    ))

    assert outcome.refusal is None
    assert outcome.capsule is not None
    assert outcome.capsule.root == outcome.capsule.source == outcome.capsule.predecessor
    assert tuple(item.item_id for item in outcome.capsule.reviewer_items) == ("review-b", "review-a")
    assert outcome.capsule.derived_context == (current,)
    assert outcome.capsule.receipt.reviewer_items == outcome.capsule.reviewer_items


def test_batch_admits_only_eligible_items_and_leaves_every_ineligible_item_in_the_ledger_untouched() -> None:
    root = _resolved()
    eligible = _ledger(root, item_ids=("eligible",)).reviewer_feedback_groups[0].items[0]
    variants = (
        eligible.model_copy(update={"item_id": "deferred", "state": ReviewerItemState.DEFERRED}),
        eligible.model_copy(update={"item_id": "closed", "state": ReviewerItemState.CLOSED}),
        eligible.model_copy(update={
            "item_id": "awaiting", "state": ReviewerItemState.AWAITING_REVIEW,
            "proposal": ProposalFields(response="Proposed.", candidate_version_id=None),
        }),
        eligible.model_copy(update={"item_id": "stale-target", "target_fingerprint": "0" * 64}),
    )
    elsewhere = eligible.model_copy(
        update={"item_id": "other-predecessor", "submitted_against_version_id": "a" * 64}
    )
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug="storefront", ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(
                predecessor_version_id=root.record.version_id, items=(eligible, *variants)
            ),
            ReviewerFeedbackGroup(predecessor_version_id="a" * 64, items=(elsewhere,)),
        ),
        derived_context=(),
    )
    before = render_ledger(ledger)

    outcome = build_candidate_context(root, None, ledger)

    assert outcome.capsule is not None
    assert [item.item_id for item in outcome.capsule.reviewer_items] == ["eligible"]
    assert render_ledger(ledger) == before


def _identity_of(root: ResolvedRoadmapVersion, ledger: RoadmapFeedbackLedger) -> str:
    outcome = build_candidate_context(root, None, ledger)
    assert outcome.capsule is not None, outcome.refusal
    return outcome.capsule.capsule_identity


def _edited_request(ledger: RoadmapFeedbackLedger) -> RoadmapFeedbackLedger:
    group = ledger.reviewer_feedback_groups[0]
    item = group.items[0].model_copy(update={"request": "A different request."})
    return ledger.model_copy(update={"reviewer_feedback_groups": (
        group.model_copy(update={"items": (item,)}),
    )})


@pytest.mark.parametrize(
    "vary",
    (
        lambda root, ledger: (root, _edited_request(ledger)),
        lambda root, ledger: (root, _ledger(root, item_ids=("review-a", "review-b"))),
        lambda root, ledger: (root, ledger.model_copy(update={"derived_context": (
            DerivedFeedbackContext(
                source_version_id=root.record.version_id, context_id="new", content="Added context."
            ),
        )})),
        lambda root, ledger: (lambda other: (other, _ledger(other, item_ids=("review-a",))))(
            _resolved(brief=b"A different stored brief\n")
        ),
    ),
    ids=("request-edited", "item-added", "derived-context-added", "different-root"),
)
def test_batch_capsule_identity_changes_with_each_bound_input(vary) -> None:
    root = _resolved()
    ledger = _ledger(root, item_ids=("review-a",))
    changed_root, changed_ledger = vary(root, ledger)

    assert _identity_of(changed_root, changed_ledger) != _identity_of(root, ledger)


def test_batch_context_is_repeatable_for_equivalent_inputs() -> None:
    first_root, second_root = _resolved(), _resolved()
    derived = lambda root: (DerivedFeedbackContext(  # noqa: E731
        source_version_id=root.record.version_id, context_id="ctx", content="Context."),)
    first = build_candidate_context(first_root, None, _ledger(first_root, item_ids=("a", "b"), derived=derived(first_root)))
    second = build_candidate_context(second_root, None, _ledger(second_root, item_ids=("a", "b"), derived=derived(second_root)))

    assert first.capsule is not None and second.capsule is not None
    assert first.capsule.payload == second.capsule.payload
    assert first.capsule.receipt == second.capsule.receipt
    assert first.capsule.capsule_identity == second.capsule.capsule_identity


def test_batch_over_budget_reports_safe_membership_and_the_admitted_inputs_without_a_capsule() -> None:
    root = _resolved()
    huge = DerivedFeedbackContext(
        source_version_id=root.record.version_id, context_id="huge", content="x" * CANDIDATE_CONTEXT_MAX_BYTES
    )

    outcome = build_candidate_context(root, None, _ledger(root, item_ids=("review-a",), derived=(huge,)))

    assert outcome.capsule is None
    assert outcome.refusal is not None
    assert outcome.refusal.reason == "payload-over-budget"
    assert outcome.refusal.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert outcome.refusal.measured_payload_bytes is not None
    assert outcome.refusal.measured_payload_bytes > CANDIDATE_CONTEXT_MAX_BYTES
    assert [item.item_id for item in outcome.refusal.reviewer_items] == ["review-a"]
    assert outcome.refusal.derived_context == (huge,)
    assert outcome.refusal.full_members
    rendered = json.dumps(outcome.refusal.model_dump())
    assert '"row": {' not in rendered
    assert "owns this source block" not in rendered


def test_batch_no_work_requires_both_input_families_to_be_empty() -> None:
    root = _resolved()
    empty = build_candidate_context(root, None, _ledger(root))
    reviewer_work = build_candidate_context(root, None, _ledger(root, item_ids=("review",)))
    derived_work = build_candidate_context(root, None, _ledger(root, derived=(
        DerivedFeedbackContext(
            source_version_id=root.record.version_id, context_id="derived", content="Derived context"
        ),
    )))

    assert empty.no_work is not None
    assert reviewer_work.no_work is None and reviewer_work.capsule is not None
    assert derived_work.no_work is None and derived_work.capsule is not None


def test_batch_active_candidate_preserves_root_and_changes_direct_source() -> None:
    root = _resolved()
    candidate_record = create_candidate_version(
        roadmap_slug="storefront", predecessor_version_id=root.record.version_id,
        content_identity="b" * 64, review_lineage_identity="c" * 64,
        brief_digest=root.record.brief_digest,
        artifact_digests=tuple(_digest(data) for data in root.artifact_bytes),
    )
    active = ResolvedRoadmapVersion(candidate_record, root.brief_bytes, root.artifact_bytes)
    outcome = build_candidate_context(active, root, _ledger(root, item_ids=("review",)))
    valid_pair = build_candidate_context(root, active, _ledger(active, derived=(
        DerivedFeedbackContext(
            source_version_id=active.record.version_id, context_id="active", content="Active context"
        ),
    )))

    assert outcome.refusal is not None
    assert outcome.refusal.reason == "invalid-processing-pair"
    assert valid_pair.capsule is not None
    assert valid_pair.capsule.root.version_id == root.record.version_id
    assert valid_pair.capsule.source.version_id == active.record.version_id


def _chain_of_candidates(root: ResolvedRoadmapVersion, length: int) -> list[ResolvedRoadmapVersion]:
    versions: list[ResolvedRoadmapVersion] = []
    predecessor = root
    for index in range(length):
        record = create_candidate_version(
            roadmap_slug="storefront", predecessor_version_id=predecessor.record.version_id,
            content_identity=f"{index + 1:x}" * 64, review_lineage_identity="c" * 64,
            brief_digest=root.record.brief_digest,
            artifact_digests=tuple(_digest(data) for data in root.artifact_bytes),
        )
        predecessor = ResolvedRoadmapVersion(record, root.brief_bytes, root.artifact_bytes)
        versions.append(predecessor)
    return versions


def _derived_for(source: ResolvedRoadmapVersion) -> tuple[DerivedFeedbackContext, ...]:
    return (DerivedFeedbackContext(
        source_version_id=source.record.version_id, context_id="derived", content="Derived context"
    ),)


def test_batch_source_two_hops_from_the_root_needs_its_walked_ancestry_and_verifies_it() -> None:
    """The builder reads no store. A source beyond the root's direct candidate is
    accepted only with a chain that starts at the source's own predecessor and
    ends at the root; without one it stays fail-closed."""
    root = _resolved()
    first, second = _chain_of_candidates(root, 2)
    ledger = _ledger(second, derived=_derived_for(second))
    good = (first.record.version_id, root.record.version_id)

    accepted = build_candidate_context(root, second, ledger, source_ancestry=good)
    assert accepted.capsule is not None
    assert accepted.capsule.source.version_id == second.record.version_id
    assert accepted.capsule.root.version_id == root.record.version_id

    bad_chains = {
        "no chain supplied": None,
        "wrong head": (root.record.version_id,),
        "wrong tail": (first.record.version_id,),
        "empty chain": (),
        "repeats a version": (first.record.version_id, first.record.version_id, root.record.version_id),
        "contains the source": (first.record.version_id, second.record.version_id, root.record.version_id),
    }
    for label, chain in bad_chains.items():
        outcome = build_candidate_context(root, second, ledger, source_ancestry=chain)
        assert outcome.capsule is None, label
        assert outcome.refusal is not None and outcome.refusal.reason == "invalid-processing-pair", label


def test_batch_source_one_hop_from_the_root_needs_no_supplied_ancestry() -> None:
    root = _resolved()
    (only,) = _chain_of_candidates(root, 1)
    ledger = _ledger(only, derived=_derived_for(only))

    default = build_candidate_context(root, only, ledger)
    explicit = build_candidate_context(root, only, ledger, source_ancestry=(root.record.version_id,))

    assert default.capsule is not None and explicit.capsule is not None
    assert default.capsule.receipt == explicit.capsule.receipt


def test_batch_source_equal_to_the_root_refuses_a_supplied_ancestry() -> None:
    root = _resolved()
    (only,) = _chain_of_candidates(root, 1)

    outcome = build_candidate_context(
        root, None, _ledger(root, item_ids=("review",)), source_ancestry=(only.record.version_id,)
    )

    assert outcome.refusal is not None and outcome.refusal.reason == "invalid-processing-pair"


def test_candidate_collection_hints_preserve_each_issued_row_collection() -> None:
    source = _resolved()
    outcome = build_candidate_context(source, None, _ledger(source, item_ids=("review",)))
    assert outcome.capsule is not None

    hints = candidate_collection_hints(outcome.capsule, source)
    records = hints["existing_rows"]
    assert isinstance(records, list)
    expected_collections = {
        (stage.artifact_key, type(row).__name__, row.id): collection
        for stage, data in zip(STAGES, source.artifact_bytes, strict=True)
        for artifact in (stage.parse(data.decode("utf-8")),)
        for collection, rows in stage_row_collections(artifact).items()
        for row in rows
    }
    issued_rows = [
        (member.identity.artifact_key, member.identity.row_type, member.identity.row_id)
        for member in outcome.capsule.full_members
    ] + [
        (item.artifact_key, item.row_type, item.row_id)
        for item in outcome.capsule.inventory
    ]

    assert [
        (
            record["issued_row"]["artifact"],
            record["issued_row"]["class"],
            record["issued_row"]["id"],
            record["source_collection"],
        )
        for record in records
    ] == [(*identity, expected_collections[identity]) for identity in issued_rows]


def test_candidate_collection_hints_disambiguate_pattern_collections() -> None:
    base = _resolved()
    artifacts = list(_artifacts())
    components = artifacts[2]
    assert isinstance(components, ComponentsArtifact)
    artifacts[2] = replace(
        components,
        component_patterns=(PatternRow("pattern-component", "Component pattern", "Keep local state."),),
    )
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES, artifacts, strict=True)
    )
    record = create_root_version(
        roadmap_slug="storefront",
        brief_digest=_digest(base.brief_bytes),
        artifact_digests=tuple(_digest(data) for data in artifact_bytes),
    )
    source = ResolvedRoadmapVersion(record, base.brief_bytes, artifact_bytes)
    outcome = build_candidate_context(source, None, _ledger(source, item_ids=("review",)))
    assert outcome.capsule is not None

    hints = candidate_collection_hints(outcome.capsule, source)
    records = hints["existing_rows"]
    assert isinstance(records, list)
    pattern_collections = {
        record["issued_row"]["id"]: record["source_collection"]
        for record in records
        if record["issued_row"]["class"] == "PatternRow"
    }

    assert pattern_collections["pattern-order"] == "system_patterns"
    assert pattern_collections["pattern-component"] == "component_patterns"


def test_candidate_collection_hint_records_do_not_match_operation_envelopes() -> None:
    source = _resolved()
    outcome = build_candidate_context(source, None, _ledger(source, item_ids=("review",)))
    assert outcome.capsule is not None

    records = candidate_collection_hints(outcome.capsule, source)["existing_rows"]
    assert isinstance(records, list)
    operation_keys = set().union(
        roadmap_candidate.ADD_ROW_REQUIRED_KEYS,
        roadmap_candidate.ADD_ROW_OPTIONAL_KEYS,
        roadmap_candidate.REPLACE_ROW_REQUIRED_KEYS,
        roadmap_candidate.REPLACE_ROW_OPTIONAL_KEYS,
        roadmap_candidate.REMOVE_ROW_REQUIRED_KEYS,
        roadmap_candidate.REMOVE_ROW_OPTIONAL_KEYS,
        {"collection"},
    )

    assert all(set(record).isdisjoint(operation_keys) for record in records)
    assert not set({"artifact_key", "row_type", "row_id", "collection"}).isdisjoint(operation_keys)


@pytest.mark.parametrize(
    "module",
    [
        roadmap_candidate,
        roadmap_candidate_context,
        roadmap_candidate_review,
        roadmap_candidate_run,
    ],
)
def test_every_wire_helper_omits_an_absent_owning_set_so_legacy_identities_recompute(module) -> None:
    """Four `_wire_value` copies feed identity and receipt preimages; all must keep a legacy span's bytes."""
    legacy = roadmap_candidate_context.CandidateContextSourceSpanReceipt(
        row_id="a", span_id="s", digest="d"
    )
    shared = roadmap_candidate_context.CandidateContextSourceSpanReceipt(
        row_id="a", span_id="s", digest="d", owning_row_ids=("a", "b")
    )

    assert module._wire_value(legacy) == {"row_id": "a", "span_id": "s", "digest": "d"}
    assert module._wire_value(shared)["owning_row_ids"] == ["a", "b"]


def _batch_capsule(domain_body: str):
    root = _resolved(domain_body=domain_body)
    outcome = build_candidate_context(root, None, _ledger(root, item_ids=("review-a",)))
    assert outcome.refusal is None, outcome.refusal
    assert outcome.capsule is not None
    return outcome.capsule


def test_batch_payload_issues_a_shared_span_once_and_names_it_from_every_owner() -> None:
    """A shared span used to repeat per owning member; the batch payload carries it once in a table."""
    capsule = _batch_capsule(_SHARED_BODY)
    payload = json.loads(capsule.payload)
    members = {member["identity"]["row_id"]: member for member in payload["full_members"]}
    shared = payload["shared_source_spans"]

    assert payload["schema_version"] == capsule.receipt.schema_version == 2
    assert len(shared) == 1
    assert shared[0]["artifact_key"] == "domain"
    assert shared[0]["owning_row_ids"] == list(_SHARED_OWNERS)
    assert capsule.payload.count(b"entity-order and entity-customer share this decisions paragraph.") == 1
    for row_id in _SHARED_OWNERS:
        assert members[row_id]["shared_source_span_ids"] == [shared[0]["span_id"]]
        assert all("owning_row_ids" not in span for span in members[row_id]["source_spans"])


def test_batch_payload_keeps_single_owner_spans_inline_and_omits_the_empty_shared_id_list() -> None:
    """Single-owner spans were never repeated, so moving them to a table only adds bytes: they stay
    inline in the schema-1 form, and a member with no shared span carries no extra key."""
    capsule = _batch_capsule(_SHARED_BODY)
    payload = json.loads(capsule.payload)
    members = {member["identity"]["row_id"]: member for member in payload["full_members"]}
    typed = {member.identity.row_id: member for member in capsule.full_members}

    assert members["entity-order"]["source_spans"] == json.loads(json.dumps([
        roadmap_candidate_context._wire_value(span)
        for span in typed["entity-order"].source_spans
        if span.owning_row_ids is None
    ]))
    unshared = [member for member in payload["full_members"] if member["identity"]["row_id"] not in _SHARED_OWNERS]
    assert unshared
    assert all("shared_source_span_ids" not in member for member in unshared)


def test_batch_payload_without_a_shared_span_is_no_larger_than_the_schema_one_layout() -> None:
    """The span table must not regress a batch the old layout fitted: with no shared span the payload
    differs from schema 1 only by the table key and the version digit."""
    capsule = _batch_capsule("entity-order owns this first source block.\n")
    payload = json.loads(capsule.payload)

    assert payload["shared_source_spans"] == []
    legacy = {key: value for key, value in payload.items() if key != "shared_source_spans"}
    legacy["schema_version"] = 1
    assert len(capsule.payload) - len(roadmap_candidate_context._canonical_json_bytes(legacy)) == len(
        b',"shared_source_spans":[]'
    )


def test_batch_shared_span_table_matches_the_issued_member_spans_exactly() -> None:
    """Edit authority and receipts still read each member's typed spans; the payload must issue exactly those."""
    capsule = _batch_capsule(_SHARED_BODY)
    payload = json.loads(capsule.payload)
    shared = {
        (member.identity.artifact_key, span.span_id): {
            "artifact_key": member.identity.artifact_key, **roadmap_candidate_context._wire_value(span)
        }
        for member in capsule.full_members
        for span in member.source_spans
        if span.owning_row_ids is not None
    }

    assert {(span["artifact_key"], span["span_id"]): span for span in payload["shared_source_spans"]} == shared
    for wire, member in zip(payload["full_members"], capsule.full_members, strict=True):
        issued = {span.span_id for span in member.source_spans}
        assert {span["span_id"] for span in wire["source_spans"]} | set(
            wire.get("shared_source_span_ids", ())
        ) == issued


def test_batch_with_many_shared_spans_fits_only_because_each_is_issued_once() -> None:
    """Each block is under the shared cap; repeated per owner they would exceed the ceiling."""
    block = "x" * 2048
    count = (CANDIDATE_CONTEXT_MAX_BYTES * 2 // 3) // len(block)
    body = "".join(f"entity-order and entity-customer share block {index} {block}\n\n" for index in range(count))

    capsule = _batch_capsule(body)
    owners = [member for member in capsule.full_members if member.identity.row_id in _SHARED_OWNERS]
    repeated = sum(len(span.text) for member in owners for span in member.source_spans)

    assert repeated > CANDIDATE_CONTEXT_MAX_BYTES
    assert len(capsule.payload) <= CANDIDATE_CONTEXT_MAX_BYTES


def test_selector_payload_keeps_schema_one_per_member_spans() -> None:
    """Stored selector capsules are verified by exact recompilation, so their bytes must not change."""
    capsule = _capsule(_resolved(domain_body=_SHARED_BODY))
    payload = json.loads(capsule.payload)

    assert payload["schema_version"] == capsule.receipt.schema_version == 1
    assert "source_spans" not in payload
    assert all("source_spans" in member for member in payload["full_members"])


def test_stored_schema_one_batch_capsule_with_per_member_spans_still_verifies() -> None:
    """Batch capsules are bound by digest and member receipts, never re-rendered, so a capsule stored
    before the span table keeps verifying after it."""
    capsule = _batch_capsule(_SHARED_BODY)
    payload = json.loads(capsule.payload)
    spans = {(span["artifact_key"], span["span_id"]): span for span in payload.pop("shared_source_spans")}
    for member in payload["full_members"]:
        artifact_key = member["identity"]["artifact_key"]
        member["source_spans"] += [
            {key: value for key, value in spans[(artifact_key, span_id)].items() if key != "artifact_key"}
            for span_id in member.pop("shared_source_span_ids", ())
        ]
    payload["schema_version"] = 1
    legacy_bytes = roadmap_candidate_context._canonical_json_bytes(payload)
    identity = roadmap_candidate_context._digest_bytes(legacy_bytes)
    legacy = capsule.model_copy(update={
        "payload": legacy_bytes,
        "capsule_identity": identity,
        "receipt": capsule.receipt.model_copy(update={
            "schema_version": 1,
            "payload_bytes": len(legacy_bytes),
            "payload_digest": identity,
            "capsule_identity": identity,
        }),
    })

    assert legacy_bytes != capsule.payload
    assert roadmap_candidate_context._capsule_is_intact(legacy)


def _resolved_with_stack() -> ResolvedRoadmapVersion:
    from plan_tool.roadmap_artifacts import StackRow

    domain, constraints, components, plans = _artifacts()
    constraints = replace(
        constraints,
        stack=(
            StackRow("stack-platform", "platform", choice="managed"),
            StackRow("stack-store-engine", "store-engine", open=True),
        ),
    )
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES, (domain, constraints, components, plans), strict=True)
    )
    record = create_root_version(
        roadmap_slug="storefront",
        brief_digest=_digest(b"Recorded brief\n"),
        artifact_digests=tuple(_digest(data) for data in artifact_bytes),
    )
    return ResolvedRoadmapVersion(record, b"Recorded brief\n", artifact_bytes)


def test_context_builds_over_a_predecessor_that_records_a_stack() -> None:
    """Stack rows are impact nodes (addable), but they carry no label and no
    design relation; building the capsule must not raise on them."""
    root = _resolved_with_stack()

    capsule = build_candidate_context(root, None, _ledger(root, item_ids=("review",))).capsule

    assert capsule is not None


_PRIOR_CEILINGS = (64 * 1024, 192 * 1024)  # issued values, as literals: they must not follow the constant


@pytest.mark.parametrize("ceiling", [*_PRIOR_CEILINGS, 384 * 1024])
def test_every_issued_ceiling_is_supported(ceiling: int) -> None:
    assert is_supported_candidate_context_ceiling(ceiling)


@pytest.mark.parametrize(
    "value", [256 * 1024, 512 * 1024, 0, 196_609, 1024 * 1024, True, "196608", None],
    ids=lambda value: repr(value),
)
def test_only_issued_ceilings_are_supported_so_an_unissued_value_is_refused(value: object) -> None:
    """The allowlist is the carve-out that keeps a forged `ceiling_bytes` from validating a capsule."""
    assert not is_supported_candidate_context_ceiling(value)


def test_context_between_the_prior_and_current_ceiling_is_admitted_under_the_current_one() -> None:
    """The Integration follow-up measured 211,712 bytes: over 192 KiB, well under the current ceiling."""
    brief = b"x" * (200 * 1024)

    capsule = _capsule(_resolved(brief=brief))

    assert 192 * 1024 < len(capsule.payload) <= CANDIDATE_CONTEXT_MAX_BYTES
    assert capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert capsule.receipt.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert roadmap_candidate_context._capsule_is_intact(capsule)


def test_batch_context_between_the_prior_and_current_ceiling_is_admitted_with_every_member() -> None:
    block = "y" * 2048
    count = (200 * 1024) // len(block)
    body = "".join(f"entity-order and entity-customer share block {index} {block}\n\n" for index in range(count))

    capsule = _batch_capsule(body)

    assert 192 * 1024 < len(capsule.payload) <= CANDIDATE_CONTEXT_MAX_BYTES
    assert capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert {member.identity.row_id for member in capsule.full_members} >= set(_SHARED_OWNERS)


@pytest.mark.parametrize("prior", _PRIOR_CEILINGS)
def test_a_stored_capsule_reproduces_only_at_its_recorded_ceiling(
    prior: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ceiling is part of the payload and its digest, so a lineage issued under an earlier ceiling
    must be rebuilt at that value; rebuilding at the current one would read as a different capsule."""
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", prior)
        stored = _capsule(_resolved())

    rebuilt = rebuild_candidate_context_at_recorded_ceiling(
        _resolved(), _SELECTOR, recorded_ceiling_bytes=stored.ceiling_bytes
    )
    at_current = _capsule(_resolved())

    assert stored.ceiling_bytes == prior
    assert rebuilt.capsule == stored
    assert at_current != stored
    assert at_current.capsule_identity != stored.capsule_identity
    assert json.loads(stored.payload)["ceiling_bytes"] == prior


@pytest.mark.parametrize("recorded", [256 * 1024, 0, True, None, "196608"], ids=lambda value: repr(value))
def test_rebuild_at_an_unissued_recorded_ceiling_is_refused_without_a_capsule(recorded: object) -> None:
    outcome = rebuild_candidate_context_at_recorded_ceiling(
        _resolved(), _SELECTOR, recorded_ceiling_bytes=recorded
    )

    assert outcome.capsule is None
    assert outcome.refusal is not None
    assert outcome.refusal.reason == "invalid-capsule"


@pytest.mark.parametrize("prior", _PRIOR_CEILINGS)
def test_an_expanded_capsule_stored_under_an_earlier_ceiling_still_verifies_after_a_raise(
    prior: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The expansion branch of `_verify_bindings` must rebuild the initial capsule at the recorded
    ceiling before expanding it; rebuilding at the current one would read as an unrelated capsule."""
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", prior)
        initial = _capsule(_resolved())
        entry = next(item for item in initial.inventory if item.row_id == "entity-invoice")
        expanded = expand_candidate_context(_resolved(), initial, entry).capsule
    assert expanded is not None
    assert expanded.expansion is not None
    assert expanded.ceiling_bytes == prior

    verified = roadmap_candidate._verify_bindings(
        predecessor=_resolved(), capsule=expanded, receipt=expanded.receipt, stages=STAGES
    )

    assert not isinstance(verified, roadmap_candidate.CandidateRefusal), verified


def test_a_stored_capsule_with_an_unissued_ceiling_is_refused_as_an_invalid_capsule_not_a_predecessor_fault() -> None:
    """The operator must be pointed at the capsule, not at the predecessor that reproduced it fine."""
    stored = _capsule(_resolved())
    forged = stored.model_copy(update={"ceiling_bytes": 256 * 1024})

    refusal = roadmap_candidate._verify_bindings(
        predecessor=_resolved(), capsule=forged, receipt=forged.receipt, stages=STAGES
    )

    assert isinstance(refusal, roadmap_candidate.CandidateRefusal)
    assert refusal.reason == "invalid-capsule"
    assert "ceiling" in refusal.detail
