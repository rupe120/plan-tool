"""Tests for the pure decision-settlement preflight leaf."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    PlansArtifact,
    RejectedAlternative,
    components_path,
    constraints_path,
    domain_path,
    plans_path,
)
from plan_tool import roadmap_decision_settlement
from plan_tool.roadmap_decision_settlement import (
    DecisionSettlementCandidate,
    DecisionSettlementContentIntegrityError,
    DecisionSettlementRefusal,
    DecisionSettlementSelector,
    DecisionSettlementSourceCorruptError,
    build_decision_settlement_candidate,
    decision_settlement_candidate_is_current,
    resolve_decision_settlement_selector,
)
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    LedgerTarget,
    ProposalFields,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    render_ledger,
    roadmap_feedback_ledger_path,
    target_fingerprint,
)
from plan_tool.roadmap_versions import (
    INITIAL_EMPTY_REVIEW_LINEAGE_ID,
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    create_candidate_version,
    create_root_version,
    load_accepted_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
)

MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_decision_settlement.py"
)
SLUG = "demo"
_ARTIFACT_KEYS = tuple(stage.artifact_key for stage in STAGES)
_DOMAIN_STAGE = STAGES[0]
_CONSTRAINTS_STAGE = STAGES[1]


# --------------------------------------------------------------------------
# Fixture builders
# --------------------------------------------------------------------------


def _entity(id_: str = "entity-order", name: str = "Order") -> EntityRow:
    return EntityRow(id_, name, ())


def _decision(
    id_: str = "decision-1",
    *,
    anchor: str = "entity-order",
    status: DecisionStatus = DecisionStatus.PENDING,
    source: str | None = None,
) -> DecisionRow:
    return DecisionRow(
        id=id_,
        chosen_option="Use the order-centric model.",
        rejected_alternatives=(
            ()
            if source is not None
            else (RejectedAlternative("Use a cart-centric model.", "Rejected for clarity."),)
        ),
        rationale=None if source is not None else "Keeps the domain simple.",
        anchor=anchor,
        status=status,
        source=source,
    )


def _feedback(
    id_: str = "feedback-1",
    *,
    target: FeedbackTarget | None = None,
    request: str = "Confirm the order-centric model.",
    state: FeedbackState = FeedbackState.OPEN,
    proposed_response: str | None = None,
) -> FeedbackRow:
    return FeedbackRow(
        id=id_,
        target=target if target is not None else FeedbackTarget(FeedbackTargetKind.ROW, "decision-1"),
        request=request,
        state=state,
        proposed_response=proposed_response,
    )


def _domain(
    *,
    entities: tuple[EntityRow, ...] = (_entity(),),
    decisions: tuple[DecisionRow, ...] | None = None,
    feedback: tuple[FeedbackRow, ...] | None = None,
    body: str = "# Domain\n",
) -> DomainArtifact:
    return DomainArtifact(
        entities=entities,
        business_rules=(),
        workflows=(),
        decisions=(_decision(),) if decisions is None else decisions,
        body=body,
        feedback=(_feedback(),) if feedback is None else feedback,
    )


def _constraints(
    *,
    decisions: tuple[DecisionRow, ...] | None = None,
    feedback: tuple[FeedbackRow, ...] | None = None,
    body: str = "# Constraints\n",
) -> ConstraintsArtifact:
    return ConstraintsArtifact(
        dispositions=(),
        constraints=(),
        decisions=(_decision(),) if decisions is None else decisions,
        body=body,
        hosting=(),
        feedback=(_feedback(),) if feedback is None else feedback,
    )


def _empty_constraints() -> ConstraintsArtifact:
    return ConstraintsArtifact(
        dispositions=(), constraints=(), decisions=(), body="# Constraints\n", hosting=(), feedback=()
    )


def _empty_components() -> ComponentsArtifact:
    return ComponentsArtifact(
        system_patterns=(), component_patterns=(), components=(), decisions=(), body="# Components\n"
    )


def _empty_plans() -> PlansArtifact:
    return PlansArtifact(plans=(), ordering=(), assumptions=(), decisions=(), body="# Plans\n")


def _selector(
    *, artifact_key: str = "domain", decision_id: str = "decision-1", feedback_id: str = "feedback-1"
) -> DecisionSettlementSelector:
    return DecisionSettlementSelector(artifact_key, decision_id, feedback_id)


# --------------------------------------------------------------------------
# Top-level stage-file fixtures (inert leftovers the leaf must never read)
# --------------------------------------------------------------------------


_STAGE_PATHS = {
    "domain": domain_path,
    "constraints": constraints_path,
    "components": components_path,
    "plans": plans_path,
}


def _write_stage_source(plans_dir: Path, stage, artifact) -> Path:
    path = _STAGE_PATHS[stage.artifact_key](plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(stage.render(artifact), encoding="utf-8")
    return path


# --------------------------------------------------------------------------
# Enrolled immutable-version fixtures
# --------------------------------------------------------------------------


def _enroll(
    plans_dir: Path,
    *,
    domain: DomainArtifact | None = None,
    domain_bytes: bytes | None = None,
    constraints: ConstraintsArtifact | None = None,
    components: ComponentsArtifact | None = None,
    plans: PlansArtifact | None = None,
    predecessor_version_id: str | None = None,
) -> str:
    """Store one immutable version (root, or a candidate atop
    ``predecessor_version_id``) and point the accepted head at it."""
    domain_data = (
        domain_bytes
        if domain_bytes is not None
        else _DOMAIN_STAGE.render(domain if domain is not None else _domain()).encode("utf-8")
    )
    constraints_data = STAGES[1].render(
        constraints if constraints is not None else _empty_constraints()
    ).encode("utf-8")
    components_data = STAGES[2].render(
        components if components is not None else _empty_components()
    ).encode("utf-8")
    plans_data = STAGES[3].render(plans if plans is not None else _empty_plans()).encode("utf-8")

    content = RoadmapVersionContent(
        brief_bytes=b"recorded brief\n",
        artifact_bytes=(domain_data, constraints_data, components_data, plans_data),
    )
    digests = tuple(hashlib.sha256(data).hexdigest() for data in content.artifact_bytes)
    if predecessor_version_id is None:
        record = create_root_version(
            roadmap_slug=SLUG,
            brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
            artifact_digests=digests,
        )
    else:
        record = create_candidate_version(
            roadmap_slug=SLUG,
            predecessor_version_id=predecessor_version_id,
            content_identity=hashlib.sha256(b"candidate content").hexdigest(),
            review_lineage_identity=INITIAL_EMPTY_REVIEW_LINEAGE_ID,
            brief_digest=hashlib.sha256(content.brief_bytes).hexdigest(),
            artifact_digests=digests,
        )
    prepared = PreparedRoadmapVersion(record=record, content=content)
    version_dir = version_directory_path(plans_dir, SLUG, record.version_id)
    for member in stored_version_members(prepared):
        path = version_dir / member.member_name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(member.data)

    head_path = accepted_head_path(plans_dir, SLUG)
    head_path.parent.mkdir(parents=True, exist_ok=True)
    head_path.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=SLUG,
                version_id=record.version_id,
            )
        )
    )
    return record.version_id


# --------------------------------------------------------------------------
# Selector (pure)
# --------------------------------------------------------------------------


def test_resolver_returns_one_selector_for_two_well_formed_same_artifact_values() -> None:
    result = resolve_decision_settlement_selector(
        "domain:decision-1", "domain:feedback-1", artifact_keys=_ARTIFACT_KEYS
    )

    assert result == DecisionSettlementSelector("domain", "decision-1", "feedback-1")


@pytest.mark.parametrize(
    "value", (123, "domain-decision-1", "domain:"), ids=("non-string", "no-colon", "blank-id")
)
def test_malformed_decision_selector_is_refused(value: object) -> None:
    result = resolve_decision_settlement_selector(
        value, "domain:feedback-1", artifact_keys=_ARTIFACT_KEYS
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "malformed-decision-selector"


def test_malformed_evidence_selector_is_refused() -> None:
    result = resolve_decision_settlement_selector(
        "domain:decision-1", "domain-feedback-1", artifact_keys=_ARTIFACT_KEYS
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "malformed-evidence-selector"


def test_decision_selector_naming_an_unconfigured_artifact_is_unknown_artifact() -> None:
    result = resolve_decision_settlement_selector(
        "unknown:decision-1", "unknown:feedback-1", artifact_keys=_ARTIFACT_KEYS
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "unknown-artifact"


@pytest.mark.parametrize(
    "evidence_value",
    ("constraints:feedback-1", "unknown:feedback-1"),
    ids=("another-configured-key", "unconfigured-key"),
)
def test_evidence_in_another_or_unknown_artifact_is_an_artifact_mismatch(
    evidence_value: str,
) -> None:
    result = resolve_decision_settlement_selector(
        "domain:decision-1", evidence_value, artifact_keys=_ARTIFACT_KEYS
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "evidence-artifact-mismatch"


@pytest.mark.parametrize(
    "decision_value, evidence_value",
    (
        ("domain:decision 1", "domain:feedback-1"),
        ("domain:decision-1", "domain:feedback 1"),
    ),
    ids=("decision-id", "feedback-id"),
)
def test_unsafe_decision_or_feedback_id_is_refused(
    decision_value: str, evidence_value: str
) -> None:
    result = resolve_decision_settlement_selector(
        decision_value, evidence_value, artifact_keys=_ARTIFACT_KEYS
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "unsafe-selector"


def test_build_refuses_a_hand_built_unsafe_selector_before_any_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    selector = DecisionSettlementSelector("domain", "decision 1", "feedback-1")

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("an unsafe selector must not read its source")

    monkeypatch.setattr(roadmap_decision_settlement, "load_accepted_version", unexpected)

    result = build_decision_settlement_candidate(
        selector, plans_dir=tmp_path, slug=SLUG, stages=(_DOMAIN_STAGE,)
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "unsafe-selector"


# --------------------------------------------------------------------------
# Source and lineage
# --------------------------------------------------------------------------


def test_no_accepted_head_is_refused_before_any_stage_file_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberate: a top-level stage file never stands in for a missing accepted head."""
    for stage, artifact in zip(
        STAGES, (_domain(), _empty_constraints(), _empty_components(), _empty_plans())
    ):
        _write_stage_source(tmp_path, stage, artifact)
    ledger_path = roadmap_feedback_ledger_path(tmp_path, SLUG)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_bytes(b"not a ledger")

    def unexpected(*args: object, **kwargs: object) -> None:
        raise AssertionError("a roadmap with no accepted head must not read anything else")

    monkeypatch.setattr(roadmap_decision_settlement, "load_ledger", unexpected)
    monkeypatch.setattr(roadmap_decision_settlement, "canonical_artifact_snapshot", unexpected)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "no-published-version"


def test_retired_unenrolled_admission_verdict_and_baseline_reader_are_gone() -> None:
    """Deliberate carve-out: the recorded-baseline admission arm is removed, not dormant."""
    source = MODULE_PATH.read_text()
    assert "source-not-admitted" not in source
    assert "admit_versioned_artifact_source" not in source
    assert "artifact_path" not in source


def test_enrolled_preflight_reads_the_accepted_version_and_never_the_stage_file(
    tmp_path: Path,
) -> None:
    artifact = _domain()
    _enroll(tmp_path, domain=artifact)

    _write_stage_source(tmp_path, _DOMAIN_STAGE, _domain(decisions=()))

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementCandidate)
    assert result.accepted_version_id is not None


def test_enrolled_feedback_present_only_on_disk_is_missing_feedback(tmp_path: Path) -> None:
    _enroll(tmp_path, domain=_domain(feedback=()))
    _write_stage_source(tmp_path, _DOMAIN_STAGE, _domain())

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "missing-feedback"


def test_enrolled_noncanonical_accepted_bytes_are_refused(tmp_path: Path) -> None:
    artifact = _domain()
    canonical_bytes = _DOMAIN_STAGE.render(artifact).encode("utf-8")
    noncanonical_bytes = canonical_bytes.replace(b"feedback:\n", b"feedback: # hand-edited\n", 1)
    _enroll(tmp_path, domain_bytes=noncanonical_bytes)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "source-not-canonical"


def test_unparsable_accepted_member_raises_a_distinct_corrupt_source_error_rather_than_refusing(
    tmp_path: Path,
) -> None:
    """Not a plain ``RoadmapVersionError``: both runners' catch-all treats a
    ``ValueError`` subclass as an ordinary refusal and folds it into a
    generic ``write-failed`` outcome, which would hide a broken store."""
    _enroll(tmp_path, domain_bytes=b"not a roadmap artifact at all")

    with pytest.raises(DecisionSettlementSourceCorruptError):
        build_decision_settlement_candidate(
            _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
        )


# --------------------------------------------------------------------------
# Enrolled ledger evidence
# --------------------------------------------------------------------------


def _ledger_item(
    resolved,
    *,
    item_id: str = "feedback-1",
    target: LedgerTarget | None = None,
    request: str = "Confirm the order-centric model.",
    state: ReviewerItemState = ReviewerItemState.OPEN,
    fingerprint: str | None = None,
    submitted_against: str | None = None,
    proposal: ProposalFields | None = None,
) -> ReviewerFeedbackItem:
    target = target or LedgerTarget(
        artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="decision-1"
    )
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=target,
        request=request,
        state=state,
        submitted_against_version_id=submitted_against or resolved.record.version_id,
        target_fingerprint=fingerprint or target_fingerprint(resolved, target),
        proposal=proposal,
    )


def _write_ledger(
    plans_dir: Path,
    items: tuple[ReviewerFeedbackItem, ...],
    *,
    state: LedgerState = LedgerState.LEDGER_NATIVE,
) -> None:
    groups: dict[str, list[ReviewerFeedbackItem]] = {}
    for item in items:
        groups.setdefault(item.submitted_against_version_id, []).append(item)
    ledger = RoadmapFeedbackLedger(
        schema_version=1,
        roadmap_slug=SLUG,
        ledger_state=state,
        reviewer_feedback_groups=tuple(
            ReviewerFeedbackGroup(predecessor_version_id=key, items=tuple(value))
            for key, value in groups.items()
        ),
        derived_context=(),
    )
    path = roadmap_feedback_ledger_path(plans_dir, SLUG)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_ledger(ledger))


def _enroll_without_embedded_feedback(plans_dir: Path):
    """An enrolled roadmap whose accepted artifacts carry no feedback rows."""
    _enroll(plans_dir, domain=_domain(feedback=()))
    return load_accepted_version(plans_dir=plans_dir, slug=SLUG)


def _build(plans_dir: Path):
    return build_decision_settlement_candidate(
        _selector(), plans_dir=plans_dir, slug=SLUG, stages=STAGES
    )


def test_enrolled_settlement_evidence_resolves_from_a_ledger_item_not_embedded_feedback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved),))

    def unexpected(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ledger-backed evidence must not read embedded feedback rows")

    monkeypatch.setattr(roadmap_decision_settlement, "matching_feedback_rows", unexpected)

    result = _build(tmp_path)

    assert isinstance(result, DecisionSettlementCandidate)
    assert result.accepted_version_id == resolved.record.version_id


def test_ledger_evidence_digest_binds_the_reviewer_request_and_ignores_a_model_proposal(
    tmp_path: Path,
) -> None:
    """A live proposal is model output, never settlement evidence: it must not
    move the digest, while the reviewer's own request must."""
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved),))
    baseline = _build(tmp_path)
    _write_ledger(
        tmp_path,
        (_ledger_item(resolved, proposal=ProposalFields(response="A model-written answer.")),),
    )
    with_proposal = _build(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved, request="A different reviewer request."),))
    other_request = _build(tmp_path)

    assert isinstance(baseline, DecisionSettlementCandidate)
    assert isinstance(with_proposal, DecisionSettlementCandidate)
    assert isinstance(other_request, DecisionSettlementCandidate)
    assert with_proposal.evidence_digest == baseline.evidence_digest
    assert other_request.evidence_digest != baseline.evidence_digest


def test_enrolled_roadmap_with_a_ledger_ignores_embedded_feedback_rows(tmp_path: Path) -> None:
    """The ledger's existence, not the embedded rows, selects the evidence route."""
    _enroll(tmp_path, domain=_domain())
    _write_ledger(tmp_path, ())

    result = _build(tmp_path)

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "missing-feedback"


def test_enrolled_roadmap_without_a_ledger_keeps_embedded_feedback_evidence(
    tmp_path: Path,
) -> None:
    _enroll(tmp_path, domain=_domain())

    assert not roadmap_feedback_ledger_path(tmp_path, SLUG).exists()
    assert isinstance(_build(tmp_path), DecisionSettlementCandidate)


@pytest.mark.parametrize(
    ("verdict", "make_item"),
    (
        pytest.param(
            "feedback-not-targeting-decision",
            lambda resolved: _ledger_item(
                resolved,
                target=LedgerTarget(
                    artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="entity-order"
                ),
            ),
            id="targets-another-row",
        ),
        pytest.param(
            "feedback-not-targeting-decision",
            lambda resolved: _ledger_item(
                resolved,
                target=LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT),
            ),
            id="targets-the-whole-artifact",
        ),
        pytest.param(
            "feedback-not-targeting-decision",
            lambda resolved: _ledger_item(
                resolved,
                target=LedgerTarget(
                    artifact_key="constraints", kind=FeedbackTargetKind.ROW, row_id="decision-1"
                ),
                fingerprint="a" * 64,
            ),
            id="targets-the-same-row-id-in-another-artifact",
        ),
        pytest.param(
            "empty-request",
            lambda resolved: _ledger_item(resolved, request="   "),
            id="blank-request",
        ),
        pytest.param(
            "feedback-not-eligible",
            lambda resolved: _ledger_item(resolved, fingerprint="f" * 64),
            id="stale-target-fingerprint",
        ),
        pytest.param(
            "feedback-not-eligible",
            lambda resolved: _ledger_item(resolved, submitted_against="e" * 64),
            id="submitted-against-another-source",
        ),
        pytest.param(
            "feedback-not-eligible",
            lambda resolved: _ledger_item(resolved, state=ReviewerItemState.DEFERRED),
            id="deferred",
        ),
        pytest.param(
            "feedback-not-eligible",
            lambda resolved: _ledger_item(resolved, state=ReviewerItemState.CLOSED),
            id="closed",
        ),
        pytest.param(
            "feedback-not-eligible",
            lambda resolved: _ledger_item(resolved, state=ReviewerItemState.AWAITING_REVIEW),
            id="awaiting-review",
        ),
        pytest.param(
            "missing-feedback",
            lambda resolved: _ledger_item(resolved, item_id="some-other-item"),
            id="no-item-with-the-cited-id",
        ),
    ),
)
def test_enrolled_settlement_refuses_ledger_evidence_that_is_not_an_eligible_item_citing_the_decision(
    tmp_path: Path, verdict: str, make_item
) -> None:
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (make_item(resolved),))

    result = _build(tmp_path)

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == verdict


def test_corrupt_ledger_raises_the_corrupt_source_error_rather_than_refusing(
    tmp_path: Path,
) -> None:
    """A broken store, like a corrupt version member: it must not fold into the
    runners' generic ``write-failed`` (a ``ValueError`` would)."""
    _enroll_without_embedded_feedback(tmp_path)
    roadmap_feedback_ledger_path(tmp_path, SLUG).write_bytes(b"not a ledger")

    with pytest.raises(DecisionSettlementSourceCorruptError):
        _build(tmp_path)


def test_currency_refuses_once_the_cited_ledger_item_leaves_eligibility(tmp_path: Path) -> None:
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved),))
    candidate = _build(tmp_path)
    assert isinstance(candidate, DecisionSettlementCandidate)
    assert decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    _write_ledger(tmp_path, (_ledger_item(resolved, state=ReviewerItemState.CLOSED),))

    assert not decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )


@pytest.mark.parametrize("artifact_key", ("domain", "constraints"))
def test_selector_reads_the_artifact_its_key_names(tmp_path: Path, artifact_key: str) -> None:
    stage = next(item for item in STAGES if item.artifact_key == artifact_key)
    artifact = _domain() if artifact_key == "domain" else _constraints()
    _enroll(tmp_path, **{artifact_key: artifact})
    selector = DecisionSettlementSelector(artifact_key, "decision-1", "feedback-1")

    result = build_decision_settlement_candidate(
        selector, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementCandidate)
    assert result.source_digest == hashlib.sha256(
        stage.render(artifact).encode("utf-8")
    ).hexdigest()


# --------------------------------------------------------------------------
# Decision
# --------------------------------------------------------------------------


def test_missing_decision_is_refused(tmp_path: Path) -> None:
    _enroll(tmp_path, domain=_domain(decisions=()))

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "missing-decision"


def test_an_id_carried_only_by_a_non_decision_row_is_a_missing_decision(tmp_path: Path) -> None:
    artifact = _domain(
        decisions=(), entities=(EntityRow("decision-1", "Not a decision", ()),)
    )
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "missing-decision"


@pytest.mark.parametrize(
    "artifact",
    (
        _domain(decisions=(_decision(), _decision())),
        _domain(entities=(_entity(), EntityRow("decision-1", "Duplicate", ()))),
    ),
    ids=("two-decisions", "decision-and-entity"),
)
def test_duplicate_decision_id_is_refused_rather_than_settling_the_first(
    tmp_path: Path, artifact: DomainArtifact
) -> None:
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "duplicate-decision"


@pytest.mark.parametrize("status", (DecisionStatus.SETTLED, DecisionStatus.PENDING))
def test_inherited_decision_is_refused_before_its_status_is_checked(
    tmp_path: Path, status: DecisionStatus
) -> None:
    artifact = _domain(decisions=(_decision(status=status, source="prior stage"),))
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "inherited-decision"


def test_already_settled_decision_is_refused(tmp_path: Path) -> None:
    artifact = _domain(decisions=(_decision(status=DecisionStatus.SETTLED),))
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "decision-not-pending"


def test_decision_refusals_come_before_evidence_refusals(tmp_path: Path) -> None:
    artifact = _domain(
        decisions=(_decision(status=DecisionStatus.SETTLED, source="prior stage"),),
        feedback=(),
    )
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "inherited-decision"


# --------------------------------------------------------------------------
# Evidence
# --------------------------------------------------------------------------


def test_missing_feedback_is_refused(tmp_path: Path) -> None:
    _enroll(tmp_path, domain=_domain(feedback=()))

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "missing-feedback"


def test_duplicate_feedback_id_is_refused(tmp_path: Path) -> None:
    artifact = _domain(feedback=(_feedback(), _feedback()))
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "duplicate-feedback"


@pytest.mark.parametrize(
    "target",
    (
        FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
        FeedbackTarget(FeedbackTargetKind.ARTIFACT),
    ),
    ids=("row-anchor-entity", "artifact"),
)
def test_feedback_targeting_another_row_or_the_whole_artifact_does_not_target_the_decision(
    tmp_path: Path, target: FeedbackTarget
) -> None:
    artifact = _domain(feedback=(_feedback(target=target),))
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "feedback-not-targeting-decision"


@pytest.mark.parametrize("request_text", ("", "   "))
def test_blank_request_is_refused_even_when_a_proposed_response_is_set(
    tmp_path: Path, request_text: str
) -> None:
    artifact = _domain(
        feedback=(
            _feedback(
                request=request_text,
                state=FeedbackState.AWAITING_REVIEW,
                proposed_response="A model-authored reply.",
            ),
        )
    )
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementRefusal)
    assert result.verdict == "empty-request"


@pytest.mark.parametrize(
    "feedback_row",
    (
        _feedback(state=FeedbackState.OPEN),
        _feedback(state=FeedbackState.AWAITING_REVIEW, proposed_response="A model-authored reply."),
        _feedback(state=FeedbackState.DEFERRED),
    ),
    ids=("open", "awaiting-review", "deferred"),
)
def test_every_feedback_state_is_eligible_evidence(
    tmp_path: Path, feedback_row: FeedbackRow
) -> None:
    artifact = _domain(feedback=(feedback_row,))
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementCandidate)


# --------------------------------------------------------------------------
# Candidate and currency
# --------------------------------------------------------------------------


def test_candidate_settles_only_the_selected_rows_status_line(tmp_path: Path) -> None:
    artifact = _domain()
    source_bytes = _DOMAIN_STAGE.render(artifact).encode("utf-8")
    _enroll(tmp_path, domain=artifact)

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementCandidate)
    source_lines = source_bytes.decode("utf-8").splitlines(keepends=True)
    settled_lines = result.settled_bytes.decode("utf-8").splitlines(keepends=True)
    diffs = [(before, after) for before, after in zip(source_lines, settled_lines) if before != after]
    assert len(diffs) == 1
    before, after = diffs[0]
    assert before.strip() == "status: pending"
    assert after.strip() == "status: settled"
    assert result.source_digest == hashlib.sha256(source_bytes).hexdigest()
    assert result.settled_digest == hashlib.sha256(result.settled_bytes).hexdigest()
    assert result.settled_artifact.feedback == artifact.feedback


def test_evidence_digest_depends_on_the_cited_row_alone(tmp_path: Path) -> None:
    sibling = _feedback(
        id_="feedback-sibling",
        target=FeedbackTarget(FeedbackTargetKind.ARTIFACT),
        request="Sibling request.",
    )
    cited = _feedback()
    _enroll(tmp_path, domain=_domain(feedback=(cited, sibling)))
    baseline_result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(baseline_result, DecisionSettlementCandidate)

    edited_sibling = replace(sibling, request="Changed sibling request.")
    _enroll(tmp_path, domain=_domain(feedback=(cited, edited_sibling)))
    sibling_edit_result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(sibling_edit_result, DecisionSettlementCandidate)
    assert sibling_edit_result.evidence_digest == baseline_result.evidence_digest

    edited_cited = replace(cited, request="Changed cited request.")
    _enroll(tmp_path, domain=_domain(feedback=(edited_cited, sibling)))
    cited_edit_result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(cited_edit_result, DecisionSettlementCandidate)
    assert cited_edit_result.evidence_digest != baseline_result.evidence_digest


def test_candidate_binds_the_accepted_version_it_was_built_from(tmp_path: Path) -> None:
    root_version_id = _enroll(tmp_path, domain=_domain())

    result = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )

    assert isinstance(result, DecisionSettlementCandidate)
    assert result.accepted_version_id == root_version_id


def test_a_renderer_that_changes_more_than_the_status_line_raises_a_distinct_integrity_error(
    tmp_path: Path,
) -> None:
    """Not a plain ``ValueError``: both runners' catch-all folds a
    ``ValueError`` into a generic, message-discarding ``write-failed``
    outcome, and this integrity violation must stay diagnosable instead."""
    artifact = _domain()
    _enroll(tmp_path, domain=artifact)
    real_render = _DOMAIN_STAGE.render

    def render_with_extra_line_once_settled(value: DomainArtifact) -> str:
        rendered = real_render(value)
        if any(row.status is DecisionStatus.SETTLED for row in value.decisions):
            rendered += "# unexpected extra line\n"
        return rendered

    stage = replace(_DOMAIN_STAGE, render=render_with_extra_line_once_settled)

    with pytest.raises(DecisionSettlementContentIntegrityError):
        build_decision_settlement_candidate(
            _selector(), plans_dir=tmp_path, slug=SLUG, stages=(stage,)
        )


def test_currency_accepts_an_unchanged_source(tmp_path: Path) -> None:
    _enroll(tmp_path, domain=_domain())

    candidate = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(candidate, DecisionSettlementCandidate)

    assert decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )


def test_currency_refuses_a_feedback_only_edit_in_a_new_accepted_version(
    tmp_path: Path,
) -> None:
    root_version_id = _enroll(tmp_path, domain=_domain())
    candidate = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(candidate, DecisionSettlementCandidate)

    edited = _domain(feedback=(replace(_feedback(), request="Edited after capture."),))
    _enroll(tmp_path, domain=edited, predecessor_version_id=root_version_id)

    assert not decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )


def test_currency_refuses_a_ledger_evidence_edit_that_the_source_bytes_cannot_see(tmp_path: Path) -> None:
    """Ledger evidence lives outside the accepted source bytes, so lineage and ``source_digest``
    cannot see a reviewer's edit to the cited item; the evidence digest must."""
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved),))
    candidate = _build(tmp_path)
    assert isinstance(candidate, DecisionSettlementCandidate)
    assert decision_settlement_candidate_is_current(candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES)

    _write_ledger(tmp_path, (_ledger_item(resolved, request="A different reviewer request."),))

    assert not decision_settlement_candidate_is_current(candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES)


def test_currency_accepts_a_ledger_edit_that_changes_only_a_model_proposal(tmp_path: Path) -> None:
    """Carve-out: a live proposal is model output, never settlement evidence, so it cannot stale a candidate."""
    resolved = _enroll_without_embedded_feedback(tmp_path)
    _write_ledger(tmp_path, (_ledger_item(resolved),))
    candidate = _build(tmp_path)
    assert isinstance(candidate, DecisionSettlementCandidate)

    _write_ledger(tmp_path, (_ledger_item(resolved, proposal=ProposalFields(response="A model-written answer.")),))

    assert decision_settlement_candidate_is_current(candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES)


def test_enrolled_currency_refuses_a_new_head_that_leaves_the_selected_artifact_unchanged(
    tmp_path: Path,
) -> None:
    domain_artifact = _domain()
    root_version_id = _enroll(tmp_path, domain=domain_artifact, constraints=_empty_constraints())
    candidate = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(candidate, DecisionSettlementCandidate)

    changed_constraints = replace(_empty_constraints(), body="# Constraints\n\nChanged.\n")
    _enroll(
        tmp_path,
        domain=domain_artifact,
        constraints=changed_constraints,
        predecessor_version_id=root_version_id,
    )

    assert not decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )


def test_currency_refuses_once_the_accepted_head_is_gone(tmp_path: Path) -> None:
    """A rebuild with no accepted head is a refusal, never a read of a stage file."""
    _enroll(tmp_path, domain=_domain())
    candidate = build_decision_settlement_candidate(
        _selector(), plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )
    assert isinstance(candidate, DecisionSettlementCandidate)
    _write_stage_source(tmp_path, _DOMAIN_STAGE, _domain())
    accepted_head_path(tmp_path, SLUG).unlink()

    assert not decision_settlement_candidate_is_current(
        candidate, plans_dir=tmp_path, slug=SLUG, stages=STAGES
    )


# --------------------------------------------------------------------------
# Leaf discipline
# --------------------------------------------------------------------------


def test_module_imports_only_the_artifact_selection_feedback_ledger_identity_and_version_leaves() -> None:
    """Mirrors ``tests/test_roadmap_view.py``'s equivalent leaf-discipline test:
    the source grep catches a lazy import, the subprocess catches a transitive one.
    ``checkpoint`` (stdlib-only canonical hash) and the feedback ledger (a leaf
    over artifacts and versions) are the two additions ledger evidence needs."""
    source = MODULE_PATH.read_text()
    assert re.findall(r"(?m)^\s*(?:from|import) (plan_tool\S*)", source) == [
        "plan_tool.checkpoint",
        "plan_tool.roadmap_artifacts",
        "plan_tool.roadmap_escalation_selection",
        "plan_tool.roadmap_feedback",
        "plan_tool.roadmap_feedback_ledger",
        "plan_tool.roadmap_source_identity",
        "plan_tool.roadmap_versions",
    ]

    code = (
        "import sys, types\n"
        "pkg = types.ModuleType('plan_tool')\n"
        f"pkg.__path__ = [{str(MODULE_PATH.parent)!r}]\n"
        "sys.modules['plan_tool'] = pkg\n"
        "import plan_tool.roadmap_decision_settlement\n"
        "leaked = sorted(m for m in sys.modules if m.startswith('plan_tool.')"
        " and m not in ('plan_tool.roadmap_decision_settlement', 'plan_tool.roadmap_artifacts',"
        " 'plan_tool.checkpoint', 'plan_tool.roadmap_feedback_ledger',"
        " 'plan_tool.roadmap_escalation_selection', 'plan_tool.roadmap_feedback',"
        " 'plan_tool.roadmap_source_identity', 'plan_tool.roadmap_versions',"
        " 'plan_tool.roadmap_json'))\n"
        "assert not leaked, leaked\n"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_module_never_writes_and_never_reads_feedback_state_or_proposed_response() -> None:
    source = MODULE_PATH.read_text()
    for token in (
        "write_bytes",
        "write_text",
        "atomic_write",
        "roadmap_writer_guard",
        "recover_roadmap_publication",
        "proposed_response",
        "FeedbackState",
    ):
        assert token not in source
