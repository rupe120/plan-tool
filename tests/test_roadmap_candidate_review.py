"""Tests for the immutable one-question candidate review boundary."""

from __future__ import annotations

import ast
import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool import (
    roadmap_candidate,
    roadmap_candidate_context,
    roadmap_candidate_narrative,
    roadmap_candidate_review,
    roadmap_candidate_run,
)
from plan_tool.roadmap import STAGES
from plan_tool.roadmap_artifacts import (
    RoadmapArtifactError,
    AttributeDispositionRow,
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
    RemovalRecord,
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
)
from plan_tool.roadmap_candidate_context import (
    CANDIDATE_CONTEXT_MAX_BYTES,
    CandidateContextBatchReceipt,
    CandidateContextPredecessor,
    build_candidate_context,
)
from plan_tool.roadmap_diff import build_roadmap_diff
from plan_tool.roadmap_impact_snapshot import RoadmapGateOutcome
from plan_tool.roadmap_revision_publish import (
    RoadmapWriterGuardError,
    publish_roadmap_generation,
    roadmap_writer_guard,
)
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    build_root_enrollment_generation,
    create_root_version,
    render_accepted_head,
    stored_artifact_path,
    version_directory_path,
)
from plan_tool import run_log as run_log_module
from plan_tool.run_log import read_run_events
from plan_tool import roadmap_feedback_ledger_run
from plan_tool.roadmap_feedback_ledger import (
    LedgerState,
    LedgerTarget,
    ProposalFields,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    item_snapshot,
    load_ledger,
    render_ledger,
    roadmap_feedback_ledger_path,
)
from tests.test_roadmap_candidate_run import (
    _FIRST_BATCH_DELTA,
    _SECOND_BATCH_DELTA,
    _approve_structural_candidate,
    _batch_item,
    _interrupting_invoker,
    _prompt_following_invoker,
    _edit_stored_evidence,
    _raise_interrupt_for_run_log_events,
    _run_batch,
    _seed_batch_ledger,
    _store_first_batch_candidate,
    _store_stack,
)


_SLUG = "storefront"
_SELECTOR = "domain:feedback-order"


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@pytest.mark.parametrize(
    ("outcome", "expected"),
    (
        ("stored", 0),
        ("response-rejected", 1),
        ("failed", 1),
        ("refused", 2),
        ("interrupted", 130),
    ),
)
def test_candidate_review_outcome_return_codes_are_closed(outcome: str, expected: int) -> None:
    assert roadmap_candidate_review._result_return_code(outcome) == expected  # type: ignore[arg-type]


def test_refused_candidate_question_records_its_usage_exit(tmp_path) -> None:
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        "a" * 64,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
    )

    events = read_run_events(next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl")))

    assert result.outcome == "refused"
    assert next(event for event in events if event["event"] == "run_end")["rc"] == 2


def test_candidate_review_reports_writer_guard_failures_as_failed(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    @contextmanager
    def blocked_writer(*_args: object, **_kwargs: object):
        raise RoadmapWriterGuardError("roadmap writer is already active")
        yield

    monkeypatch.setattr(roadmap_candidate_review, "roadmap_writer_guard", blocked_writer)

    question = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        "a" * 64,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
    )
    replacement = roadmap_candidate_review.request_replacement(
        _SLUG,
        "question-id",
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
    )

    assert question.outcome == "failed"
    assert replacement.outcome == "failed"


def _structural_batch_delta() -> dict:
    return {
        "operations": [{
            "op": "replace-row", "feedback_id": "batch-one", "artifact_key": "domain",
            "row_type": "entities", "row_id": "entity-order",
            "row": {"id": "entity-order", "name": "Order", "fields": [{
                "name": "buyer", "type": "reference", "entity_id": "entity-customer",
            }]},
        }],
        "responses": [{"item_id": "batch-one", "response": "Use buyer."}],
        "derived_feedback": [],
    }


def _confirming_digest(plans_dir, candidate) -> str:
    """The digest the stack view yields for a stored candidate: the value an operator confirms with."""
    return roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=candidate
    ).digest


_DIGEST_REFUSALS = (
    roadmap_candidate_review._APPROVAL_DIGEST_REQUIRED,
    roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH,
)
_WELL_FORMED_DIGEST_OF_NO_STACK = "0" * 64


def test_structural_approve_with_the_matching_digest_seals_the_top_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seals the displayed initial candidate, with no question asked, when the digest matches."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None

    approved = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert approved.outcome == "stored"
    assert approved.seal is not None
    assert approved.seal.decision == "structural-approval"
    assert approved.seal.approved_candidate_version_id == proposed.candidate.version_id
    assert not roadmap_candidate_review.question_inventory_path(
        tmp_path / "plans", _SLUG, proposed.candidate.version_id
    ).exists()


def _store_structural_stack_tip(tmp_path, monkeypatch: pytest.MonkeyPatch, shape: str):
    """The active tip of a stack that carries a structural change: the tip itself, or the hop below it."""
    if shape == "own-structural-top":
        _seed_batch_ledger(tmp_path, monkeypatch)
        proposed = _run_batch(tmp_path, _structural_batch_delta())
        assert proposed.candidate is not None
        return proposed.candidate
    assert shape == "presentation-only-top-over-structural-hop"
    _root, (_structural, tip) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    assert tip.evidence.operation_classification is (
        roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
    )
    return tip


def _run_answered_route(route: str, *, tmp_path, tip_version_id: str, backend):
    """One call into each entry of the answered review route, none of which may reach a backend."""
    plans_dir = tmp_path / "plans"
    if route == "question":
        return roadmap_candidate_review.generate_candidate_question(
            _SLUG, tip_version_id, repo_root=tmp_path, plans_dir=plans_dir, invoker=backend
        )
    if route == "answer":
        return roadmap_candidate_review.record_reviewer_answer(
            _SLUG, "question-id", "answer", plans_dir=plans_dir
        )
    if route == "replacement":
        return roadmap_candidate_review.request_replacement(
            _SLUG, "question-id", "answer", repo_root=tmp_path, plans_dir=plans_dir, invoker=backend
        )
    if route == "seal":
        return roadmap_candidate_review.seal_review(_SLUG, tip_version_id, plans_dir=plans_dir)
    return roadmap_candidate_review.answer_candidate_question(
        _SLUG, "question-id", "answer", repo_root=tmp_path, plans_dir=plans_dir, invoker=backend
    )


_ANSWERED_ROUTES = ("question", "answer", "replacement", "seal", "combined")


@pytest.mark.parametrize("shape", ("own-structural-top", "presentation-only-top-over-structural-hop"))
@pytest.mark.parametrize("route", _ANSWERED_ROUTES)
def test_answered_review_route_refuses_a_structural_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch, route: str, shape: str
) -> None:
    """A structural change reaches the head through the top candidate of the stack that carries it, so
    the answered route refuses that stack whether the change is the tip's own or an ancestor's."""
    tip = _store_structural_stack_tip(tmp_path, monkeypatch, shape)
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    result = _run_answered_route(
        route, tmp_path=tmp_path, tip_version_id=tip.version_id,
        backend=lambda _prompt: pytest.fail("a structural stack invoked the answered-route backend"),
    )

    assert result.outcome == "refused"
    assert "--decide-candidate" in result.detail
    assert _tree(plans_dir) == before


@pytest.mark.parametrize("route", _ANSWERED_ROUTES)
def test_answered_review_route_refuses_an_underivable_stack_instead_of_admitting_it(
    tmp_path, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """Reading "cannot tell" as "not structural" would admit a structural ancestor to the answered
    route. The forged lower hop leaves the tip loading cleanly, so only the stack derivation refuses;
    the refusal does not name --decide-candidate because a decision cannot succeed on this stack either."""
    _root, (lower, tip) = _store_stack(
        tmp_path, monkeypatch, ("presentation-only", "presentation-only")
    )
    _edit_stored_evidence(tmp_path, lower, lambda data: data.update(operation_classification="structural"))
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    result = _run_answered_route(
        route, tmp_path=tmp_path, tip_version_id=tip.version_id,
        backend=lambda _prompt: pytest.fail("an underivable stack invoked the answered-route backend"),
    )

    assert result.outcome == "refused"
    assert "underivable" in result.detail
    assert "--decide-candidate" not in result.detail
    assert _tree(plans_dir) == before


def test_answered_review_route_still_admits_a_stack_with_no_structural_hop(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: only a structural hop closes the answered route. A multi-hop stack of
    presentation-only candidates is still answerable, so a guard that refused every stack fails here."""
    _root, (_lower, tip) = _store_stack(
        tmp_path, monkeypatch, ("presentation-only", "presentation-only")
    )
    receipt = tip.evidence.batch_receipt
    kind, anchored = (
        ("inventory", receipt.inventory[0]) if receipt.inventory
        else ("full-member", receipt.full_members[0].identity)
    )
    question = json.dumps({
        "anchor": {
            "kind": kind, "artifact_key": anchored.artifact_key,
            "row_type": anchored.row_type, "row_id": anchored.row_id,
        },
        "question": "Should the customer-facing name use this exact spelling?",
    })

    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG, tip.version_id, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, question),
    )

    assert asked.outcome == "stored", asked.detail
    assert asked.question_inventory is not None
    assert roadmap_candidate_review.question_inventory_path(
        tmp_path / "plans", _SLUG, tip.version_id
    ).exists()


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
def test_batch_evidence_without_route_remains_readable_but_cannot_enter_any_structural_decision(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        plans_dir, _SLUG, proposed.candidate.version_id
    )
    old_shape = proposed.candidate.evidence.model_copy(
        update={"normalized_operations": None, "operation_classification": None}
    )
    evidence_path.write_bytes(roadmap_candidate_run.render_candidate_evidence(old_shape))
    stored = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=proposed.candidate.version_id
    )
    assert stored.evidence.normalized_operations is None
    before = _tree(plans_dir)

    refused = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, decision, plans_dir=plans_dir,
        repo_root=tmp_path, correction="Use owner.",
        invoker=lambda _prompt: pytest.fail("route-less evidence reached the backend"),
        confirm_digest=_confirming_digest(plans_dir, stored) if decision == "approve" else None,
    )

    assert refused.outcome == "refused"
    assert refused.detail not in _DIGEST_REFUSALS, "refused for the eligibility guard, not for the digest"
    assert refused.seal is None
    assert _tree(plans_dir) == before


def test_structural_rejection_releases_only_the_active_pointer(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None

    rejected = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, "reject", plans_dir=tmp_path / "plans"
    )

    assert rejected.outcome == "stored"
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id is None
    assert roadmap_candidate_run.terminal_resolution_path(
        tmp_path / "plans", _SLUG, proposed.candidate.version_id
    ).exists()


def test_structural_edit_activates_an_unsealed_replacement_with_its_own_route(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    replacement_delta = _structural_batch_delta()
    replacement_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]
    prompts: list[str] = []

    edited = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, "edit", correction="Call the field owner.",
        repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (prompts.append(prompt) or (0, json.dumps(replacement_delta))),
    )

    assert edited.outcome == "stored", edited.detail
    assert len(prompts) == 1
    assert '"EntityRow":["entities"]' in prompts[0]
    assert "Every eligible `add-row` must include its required `prose_amendment` object" in prompts[0]
    assert "Call the field owner." in prompts[0]
    assert "grants no question or answer authority, reviewer items, operations" in prompts[0]
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=tmp_path / "plans", slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id != proposed.candidate.version_id
    active = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate_version_id=admission.active_candidate_version_id
    )
    assert edited.active_candidate is not None
    assert edited.active_candidate.version_id == active.version_id
    assert edited.active_candidate.content == active.content
    assert edited.replacement is None
    assert active.evidence.operation_classification is roadmap_candidate.CandidateOperationClassification.STRUCTURAL
    assert active.evidence.normalized_operations is not None
    assert not (version_directory_path(tmp_path / "plans", _SLUG, active.version_id).parent.parent / "review-seals").exists()
    approved = _approve_structural_candidate(tmp_path / "plans", active)
    assert approved.outcome == "stored"
    assert approved.seal is not None
    assert approved.seal.approved_candidate_version_id == active.version_id


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
def test_structural_decision_refuses_candidate_evidence_changed_before_publication(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    selector = accepted_head_path(plans_dir, _SLUG)
    selector_before = selector.read_bytes()
    evidence_path = roadmap_candidate_run.candidate_evidence_path(
        plans_dir, _SLUG, proposed.candidate.version_id
    )
    real_publish = roadmap_candidate_review.publish_roadmap_generation

    def change_evidence_before_replace(generation, **kwargs):
        recheck = kwargs.pop("before_replace")

        def changed_then_recheck() -> None:
            evidence_path.write_bytes(b"invalid candidate evidence")
            recheck()

        return real_publish(generation, before_replace=changed_then_recheck, **kwargs)

    monkeypatch.setattr(
        roadmap_candidate_review, "publish_roadmap_generation", change_evidence_before_replace
    )
    replacement_delta = _structural_batch_delta()
    replacement_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]
    # Taken before the evidence changes: approve must match the digest and then reach the publication recheck.
    confirming_digest = _confirming_digest(plans_dir, proposed.candidate)
    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, decision,
        plans_dir=plans_dir, repo_root=tmp_path if decision == "edit" else None,
        correction="Use owner." if decision == "edit" else None,
        invoker=lambda _prompt: (0, json.dumps(replacement_delta)) if decision == "edit" else None,
        confirm_digest=confirming_digest if decision == "approve" else None,
    )

    assert result.outcome == "refused"
    assert result.detail not in _DIGEST_REFUSALS, "refused at the publication recheck, not for the digest"
    assert selector.read_bytes() == selector_before
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id == proposed.candidate.version_id


@pytest.mark.parametrize(
    ("case", "outcome"),
    (
        ("backend-failure", "failed"),
        ("unparsable-response", "response-rejected"),
        ("presentation-only-replacement", "response-rejected"),
    ),
)
def test_structural_edit_that_cannot_yield_a_structural_replacement_stores_nothing_and_stays_approvable(
    tmp_path, monkeypatch: pytest.MonkeyPatch, case: str, outcome: str
) -> None:
    """A stored presentation-only replacement would be activated and then refused by approve,
    leaving the operator without an approvable candidate; every failed edit keeps the original."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)
    reply = {
        "backend-failure": (1, ""),
        "unparsable-response": (0, "not a candidate delta"),
        "presentation-only-replacement": (0, _batch_replacement_response()),
    }[case]

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, "edit", correction="Use owner.",
        repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: reply,
    )

    assert result.outcome == outcome
    assert result.active_candidate is None
    assert _tree(plans_dir) == before
    approved = _approve_structural_candidate(plans_dir, proposed.candidate)
    assert approved.outcome == "stored"


def _interrupt_backend(_prompt: str) -> tuple[int, str]:
    raise KeyboardInterrupt


@pytest.mark.parametrize(
    ("case", "outcome", "return_code", "model_calls", "kept_reply"),
    (
        ("stored", "stored", 0, 1, None),
        ("backend-failure", "failed", 1, 1, "backend failure secret"),
        ("unparsable-response", "response-rejected", 1, 1, "not a candidate delta secret"),
        ("presentation-only-replacement", "response-rejected", 1, 1, "PRESENTATION-ONLY"),
        ("refused-before-any-model-call", "refused", 2, 0, None),
        ("interrupted", "interrupted", 130, 1, None),
    ),
)
def test_structural_edit_records_the_same_run_log_lifecycle_as_the_other_model_routes(
    tmp_path, monkeypatch: pytest.MonkeyPatch,
    case: str, outcome: str, return_code: int, model_calls: int, kept_reply: str | None,
) -> None:
    """Every outcome of the one model-calling structural decision leaves a run-log trail with its own
    phase, so behavior and debugging analysis can see it: the phase, the model call, the failure and
    the exact rejected reply, the interruption, and the exit code. Reviewer prose stays out of the log."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    stored_delta = _structural_batch_delta()
    stored_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]
    replies = {
        "stored": (0, json.dumps(stored_delta)),
        "backend-failure": (17, "backend failure secret"),
        "unparsable-response": (0, "not a candidate delta secret"),
        "presentation-only-replacement": (0, _batch_replacement_response()),
    }
    invoker = _interrupt_backend if case == "interrupted" else (lambda _prompt: replies[case])
    target = "9" * 64 if case == "refused-before-any-model-call" else proposed.candidate.version_id
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, target, "edit", correction="REVIEWER-CORRECTION-PROSE",
        repo_root=tmp_path, plans_dir=tmp_path / "plans", invoker=invoker,
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)
    phase = "roadmap-candidate-structural-edit"
    by_event = lambda name: [event for event in events if event["event"] == name]  # noqa: E731
    assert result.outcome == outcome
    assert result.call_count == model_calls
    assert [event["phase"] for event in by_event("phase_start")] == [phase]
    assert [event["outcome"] for event in by_event("phase_end")] == [outcome]
    assert by_event("run_end")[0]["rc"] == return_code
    assert [event["phase"] for event in by_event("claude_call_start")] == [phase] * model_calls
    assert bool(by_event("run_interrupted")) is (case == "interrupted")
    failures = by_event("parse_failure")
    if kept_reply is None:
        assert not failures
    else:
        (failure,) = failures
        expected = _batch_replacement_response() if kept_reply == "PRESENTATION-ONLY" else kept_reply
        assert failure["phase"] == phase
        assert failure["outcome"] == outcome
        assert (tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == expected
    assert "REVIEWER-CORRECTION-PROSE" not in log_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
@pytest.mark.parametrize(
    "situation",
    (
        "unknown-candidate",
        "rejected",
        "superseded-by-edit",
        "approved-then-superseded-by-edit",
        "superseded-by-later-batch",
    ),
)
def test_structural_decision_refuses_a_candidate_that_is_no_longer_the_admitted_one_without_writes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str, situation: str
) -> None:
    """Edit, reject, and a later batch stacked above it each end the prior candidate's eligibility for
    structural approval: only the top of a stack takes a decision. The admitted loader is the sole guard
    where a seal already exists: re-approval returns the stored seal before any publication recheck runs.
    The later-batch cell needs a first hop with derived context, or the second batch ends as
    `no eligible work` and supersedes nothing."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    first_delta = _structural_batch_delta()
    if situation == "superseded-by-later-batch":
        first_delta["derived_feedback"] = [{"context_id": "derived-one", "content": "Check naming."}]
    proposed = _run_batch(tmp_path, first_delta)
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    target = proposed.candidate.version_id
    # The digest of the stored stack, so that approve is refused for its named guard and not for the digest.
    confirming_digest = _confirming_digest(plans_dir, proposed.candidate)
    if situation == "unknown-candidate":
        target = "9" * 64
        confirming_digest = _WELL_FORMED_DIGEST_OF_NO_STACK
    elif situation == "rejected":
        rejected = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, target, "reject", plans_dir=plans_dir
        )
        assert rejected.outcome == "stored"
    elif situation == "superseded-by-later-batch":
        later = _run_batch(tmp_path, _SECOND_BATCH_DELTA)
        assert later.outcome == "stored", later.detail
        assert later.candidate is not None and later.candidate.evidence.source_version_id == target
    elif situation in {"superseded-by-edit", "approved-then-superseded-by-edit"}:
        if situation == "approved-then-superseded-by-edit":
            approved = _approve_structural_candidate(plans_dir, proposed.candidate)
            assert approved.outcome == "stored"
        replacement_delta = _structural_batch_delta()
        replacement_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]
        edited = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, target, "edit", correction="Call the field owner.", repo_root=tmp_path,
            plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(replacement_delta)),
        )
        assert edited.outcome == "stored", edited.detail
    before = _tree(plans_dir)

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, target, decision, plans_dir=plans_dir, repo_root=tmp_path, correction="Use owner.",
        invoker=lambda _prompt: pytest.fail("an ineligible candidate reached the backend"),
        confirm_digest=confirming_digest if decision == "approve" else None,
    )

    assert result.outcome == "refused"
    assert result.detail not in _DIGEST_REFUSALS, "refused as ineligible, not for the digest"
    assert result.seal is None
    assert _tree(plans_dir) == before


# --------------------------------------------------------------------------
# Structural decisions over a stack of unpromoted candidates
# --------------------------------------------------------------------------

_PRESENTATION_ONLY = roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY


def test_structural_approval_of_a_presentation_only_top_seals_that_top_and_promotes_nothing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The one approval binds the top candidate, the one the head would receive, so a structural
    change lower in its stack is approved through it. Approving only seals: the head does not move."""
    _root_version, (_structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    assert top.evidence.operation_classification is _PRESENTATION_ONLY
    plans_dir = tmp_path / "plans"
    head_before = accepted_head_path(plans_dir, _SLUG).read_bytes()

    approved = _approve_structural_candidate(plans_dir, top)

    assert approved.outcome == "stored", approved.detail
    assert approved.seal is not None
    assert approved.seal.decision == "structural-approval"
    assert approved.seal.approved_candidate_version_id == top.version_id
    assert accepted_head_path(plans_dir, _SLUG).read_bytes() == head_before


def test_structural_rejection_of_a_presentation_only_top_releases_the_pointer_and_keeps_every_hop_stored(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Reject keeps its contract for a stack: only the active pointer is released, and no hop's stored
    version or evidence is deleted, so the lower hop stays readable as history."""
    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"

    rejected = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, "reject", plans_dir=plans_dir
    )

    assert rejected.outcome == "stored", rejected.detail
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id is None
    assert roadmap_candidate_run.terminal_resolution_path(plans_dir, _SLUG, top.version_id).exists()
    for hop in (structural, top):
        reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug=_SLUG, candidate_version_id=hop.version_id
        )
        assert reloaded.version_id == hop.version_id


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
@pytest.mark.parametrize(
    "routes",
    (("presentation-only",), ("presentation-only", "presentation-only")),
    ids=("one-hop", "two-hop-all-presentation"),
)
def test_structural_decision_refuses_a_stack_with_no_structural_hop_for_every_decision(
    tmp_path, monkeypatch: pytest.MonkeyPatch, routes: tuple[str, ...], decision: str
) -> None:
    """Carve-out: eligibility needs a structural hop somewhere in the stack, not merely a stack. A
    presentation-only candidate has nothing to approve structurally however many hops sit below it."""
    _root_version, hops = _store_stack(tmp_path, monkeypatch, routes)
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, hops[-1].version_id, decision, plans_dir=plans_dir, repo_root=tmp_path,
        correction="Use owner.",
        invoker=lambda _prompt: pytest.fail("a stack with no structural hop reached the backend"),
        confirm_digest=_confirming_digest(plans_dir, hops[-1]) if decision == "approve" else None,
    )

    assert result.outcome == "refused"
    assert result.seal is None
    assert "candidate is not a stored structural proposal" in result.detail
    assert _tree(plans_dir) == before


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
def test_structural_decision_refuses_an_underivable_stack_with_no_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    """The stack derivation raises CandidateProposalError, which these entries do not catch, so the
    guard must translate it: an underivable stack is a refused result, never an escaped exception and
    never "not structural". The forged lower hop leaves the tip loading cleanly."""
    _root_version, (lower, tip) = _store_stack(
        tmp_path, monkeypatch, ("presentation-only", "presentation-only")
    )
    _edit_stored_evidence(tmp_path, lower, lambda data: data.update(operation_classification="structural"))
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, tip.version_id, decision, plans_dir=plans_dir, repo_root=tmp_path,
        correction="Use owner.",
        invoker=lambda _prompt: pytest.fail("an underivable stack reached the backend"),
        # An underivable stack has no digest to take, so approve carries a well-formed stand-in.
        confirm_digest=_WELL_FORMED_DIGEST_OF_NO_STACK if decision == "approve" else None,
    )

    assert result.outcome == "refused"
    assert result.seal is None
    assert "underivable" in result.detail
    assert _tree(plans_dir) == before


def test_structural_edit_over_a_structural_lower_hop_accepts_a_presentation_only_replacement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replacement is sourced from the top candidate's own source (edit sourcing is unchanged), so a
    presentation-only replacement over a structural hop still carries that hop's change into the head.
    The edit check therefore tests the replacement's stack, not its own route alone."""
    root, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    reply = {
        "operations": [], "responses": [],
        "derived_feedback": [{"context_id": "derived-edit", "content": "Edited."}],
    }

    edited = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, "edit", correction="Tighten the wording.",
        repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(reply)),
    )

    assert edited.outcome == "stored", edited.detail
    replacement = edited.active_candidate
    assert replacement is not None
    assert replacement.record.predecessor_version_id == structural.version_id
    assert replacement.evidence.operation_classification is _PRESENTATION_ONLY
    assert roadmap_candidate_run.candidate_stack_route(
        plans_dir=plans_dir, slug=_SLUG,
        tip_version_id=replacement.version_id, root_version_id=root.record.version_id,
    ).is_structural is True
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id == replacement.version_id


def test_structural_edit_over_a_presentation_only_lower_hop_still_refuses_a_replacement_with_no_structural_route(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Carve-out: a lower hop that is not structural exempts nothing. The replacement is its own route
    over that hop, so a presentation-only one leaves no structural change to approve, and storing it
    would leave the operator without an approvable candidate. The original stays approvable."""
    _root_version, (_lower, top) = _store_stack(
        tmp_path, monkeypatch, ("presentation-only", "structural")
    )
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)
    reply = {
        "operations": [],
        "responses": [{"item_id": "filed-against-hop-1", "response": "Noted."}],
        "derived_feedback": [],
    }

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, "edit", correction="Drop the change.",
        repo_root=tmp_path, plans_dir=plans_dir, invoker=lambda _prompt: (0, json.dumps(reply)),
    )

    assert result.outcome == "response-rejected"
    assert "structural edit replacement is not structural" in result.detail
    assert result.active_candidate is None
    assert _tree(plans_dir) == before
    approved = _approve_structural_candidate(plans_dir, top)
    assert approved.outcome == "stored"


# --------------------------------------------------------------------------
# Structural approval confirmed by the stack digest
# --------------------------------------------------------------------------


def _store_confirmable_stack(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """C1 (structural) -> C2 (presentation-only, the active tip): two stacks with different digests."""
    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    own, other = _confirming_digest(plans_dir, top), _confirming_digest(plans_dir, structural)
    assert own != other, "the two stacks must differ, or a wrong-stack digest would confirm"
    return plans_dir, top, own, other


def _approve_with(plans_dir, candidate, confirm_digest: str | None):
    return roadmap_candidate_review.decide_structural_candidate(
        _SLUG, candidate.version_id, "approve", plans_dir=plans_dir, confirm_digest=confirm_digest
    )


def test_structural_approve_without_a_digest_refuses_and_writes_nothing(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The library has no unconfirmed approve: the seal has one construction site, and it needs a digest.
    Refusing before the writer guard means even the guard's lock file is not touched."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)
    monkeypatch.setattr(
        roadmap_candidate_review, "roadmap_writer_guard",
        lambda *_args, **_kwargs: pytest.fail("an approve with no digest entered the writer guard"),
    )

    result = _approve_with(plans_dir, proposed.candidate, None)

    assert result.outcome == "refused"
    assert result.detail == roadmap_candidate_review._APPROVAL_DIGEST_REQUIRED
    assert result.seal is None
    assert _tree(plans_dir) == before


def test_structural_approve_of_a_presentation_only_top_confirms_against_the_whole_stack_digest(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest covers the stack the operator saw, not the top candidate alone: the tip's own stack
    digest seals it, and the digest of the structural hop beneath it (a different stack) refuses."""
    plans_dir, top, own, other = _store_confirmable_stack(tmp_path, monkeypatch)
    before = _tree(plans_dir)

    refused = _approve_with(plans_dir, top, other)

    assert refused.outcome == "refused"
    assert refused.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    assert _tree(plans_dir) == before
    approved = _approve_with(plans_dir, top, own)
    assert approved.outcome == "stored", approved.detail
    assert approved.seal is not None
    assert approved.seal.decision == "structural-approval"
    assert approved.seal.approved_candidate_version_id == top.version_id


_DIFFERING_DIGESTS = {
    "one-flipped-character": lambda own, other: ("0" if own[0] != "0" else "1") + own[1:],
    "another-stacks-digest": lambda own, other: other,
    "empty-string": lambda own, other: "",
    "correct-digest-uppercased": lambda own, other: own.upper(),
    "correct-digest-padded": lambda own, other: f" {own}\n",
}


@pytest.mark.parametrize("case", tuple(_DIFFERING_DIGESTS))
def test_structural_approve_with_a_differing_digest_refuses_with_no_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Exact string equality is the whole contract: the digest is deliberately not trimmed, case-folded, or
    prefix-matched, and an empty string is a present (wrong) digest, not an absent one."""
    plans_dir, top, own, other = _store_confirmable_stack(tmp_path, monkeypatch)
    before = _tree(plans_dir)

    result = _approve_with(plans_dir, top, _DIFFERING_DIGESTS[case](own, other))

    assert result.outcome == "refused"
    assert result.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    assert result.seal is None
    assert _tree(plans_dir) == before


def test_digest_is_recomputed_from_stored_records_under_the_writer_guard_not_taken_from_the_caller(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The caller supplies only a string; the value it is compared with is rebuilt from stored records
    while the writer guard that publishes the seal is held, so it cannot go stale between compare and seal."""
    plans_dir, top, own, _other = _store_confirmable_stack(tmp_path, monkeypatch)
    real_guard = roadmap_candidate_review.roadmap_writer_guard
    real_builder = roadmap_candidate_review.build_candidate_stack_view
    guard_held: list[bool] = []
    builder_ran_under_guard: list[bool] = []

    @contextmanager
    def tracking_guard(*args, **kwargs):
        with real_guard(*args, **kwargs) as token:
            guard_held.append(True)
            try:
                yield token
            finally:
                guard_held.pop()

    def tracking_builder(**kwargs):
        builder_ran_under_guard.append(bool(guard_held))
        return real_builder(**kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "roadmap_writer_guard", tracking_guard)
    monkeypatch.setattr(roadmap_candidate_review, "build_candidate_stack_view", tracking_builder)

    approved = _approve_with(plans_dir, top, own)

    assert approved.outcome == "stored", approved.detail
    assert builder_ran_under_guard == [True]

    # A stack that has moved since the digest was printed is a different stack: the old digest refuses.
    monkeypatch.setattr(
        roadmap_candidate_review, "build_candidate_stack_view",
        lambda **kwargs: replace(real_builder(**kwargs), root_version_id="f" * 64),
    )
    stale = _approve_with(plans_dir, top, own)
    assert stale.outcome == "refused"
    assert stale.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH


@pytest.mark.parametrize("situation", ("rejected", "superseded-by-edit"))
def test_ineligible_candidate_is_refused_for_its_own_reason_before_the_digest_is_compared(
    tmp_path, monkeypatch: pytest.MonkeyPatch, situation: str
) -> None:
    """An operator holding a stale digest for a candidate that can no longer be approved learns that, not
    "digest differs": eligibility is judged before the compare, so a wrong digest never masks it."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    if situation == "rejected":
        released = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, proposed.candidate.version_id, "reject", plans_dir=plans_dir
        )
        assert released.outcome == "stored"
    else:
        replacement_delta = _structural_batch_delta()
        replacement_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]
        edited = roadmap_candidate_review.decide_structural_candidate(
            _SLUG, proposed.candidate.version_id, "edit", correction="Call the field owner.",
            repo_root=tmp_path, plans_dir=plans_dir,
            invoker=lambda _prompt: (0, json.dumps(replacement_delta)),
        )
        assert edited.outcome == "stored", edited.detail
    before = _tree(plans_dir)

    result = _approve_with(plans_dir, proposed.candidate, _WELL_FORMED_DIGEST_OF_NO_STACK)

    assert result.outcome == "refused"
    assert result.detail not in _DIGEST_REFUSALS
    assert _tree(plans_dir) == before


def test_reapproving_an_already_sealed_candidate_still_requires_the_matching_digest(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A confirmed approve that was not promoted is retried with the same digest and returns its stored
    seal. The stored-seal return sits behind the compare, so a wrong digest cannot read the seal back."""
    plans_dir, top, own, other = _store_confirmable_stack(tmp_path, monkeypatch)
    first = _approve_with(plans_dir, top, own)
    assert first.outcome == "stored" and first.seal is not None

    retried = _approve_with(plans_dir, top, own)
    wrong = _approve_with(plans_dir, top, other)

    assert retried.outcome == "stored"
    assert retried.seal == first.seal
    assert wrong.outcome == "refused"
    assert wrong.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    assert wrong.seal is None


@pytest.mark.parametrize("decision", ("edit", "reject"))
def test_structural_edit_and_reject_refuse_a_digest_with_no_write(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    """A stack digest confirms an approval and nothing else: edit and reject have no confirm step, so a
    digest handed to either is refused before it can be mistaken for one."""
    plans_dir, top, own, _other = _store_confirmable_stack(tmp_path, monkeypatch)
    before = _tree(plans_dir)

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, top.version_id, decision, plans_dir=plans_dir, repo_root=tmp_path,
        correction="Use owner.", confirm_digest=own,
        invoker=lambda _prompt: pytest.fail("a refused digest reached the backend"),
    )

    assert result.outcome == "refused"
    assert result.detail not in _DIGEST_REFUSALS
    assert "digest" in result.detail
    assert _tree(plans_dir) == before


def test_structural_approval_seal_has_one_construction_site() -> None:
    """The binary observable: a `structural-approval` seal is built only by `decide_structural_candidate`,
    which has just required the confirming digest. A second caller would be a way around the confirm step."""
    package = Path(roadmap_candidate_review.__file__).parent
    name = "_new_structural_approval_seal"
    mentions = sum(path.read_text(encoding="utf-8").count(f"{name}(") for path in package.rglob("*.py"))
    tree = ast.parse(Path(roadmap_candidate_review.__file__).read_text(encoding="utf-8"))
    callers = [
        function.name
        for function in ast.walk(tree)
        if isinstance(function, ast.FunctionDef)
        for node in ast.walk(function)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name
    ]

    assert mentions == 2, "one definition and one call"
    assert callers == ["decide_structural_candidate"]


def _root() -> PreparedRoadmapVersion:
    domain = DomainArtifact(
        entities=(
            EntityRow(
                "entity-order",
                "Order",
                (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),),
            ),
            EntityRow("entity-customer", "Customer", ()),
            EntityRow("entity-compact", "Compact", ()),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="domain\n",
        feedback=(
            FeedbackRow(
                "feedback-order",
                FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                "Use the customer-facing order name.",
                FeedbackState.OPEN,
            ),
        ),
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
        body="constraints\n",
    )
    components = ComponentsArtifact(
        system_patterns=(PatternRow("pattern-order", "Order", "Keep orders coherent."),),
        component_patterns=(),
        components=(
            ComponentRow(
                "component-order",
                "Order service",
                ("entity-order",),
                ("pattern-order",),
                ("constraint-order",),
            ),
        ),
        decisions=(),
        body="components\n",
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
        ),
        ordering=(OrderingEntry("plan-order"),),
        assumptions=(),
        decisions=(),
        body="plans\n",
    )
    artifact_bytes = tuple(
        stage.render(artifact).encode("utf-8")
        for stage, artifact in zip(STAGES, (domain, constraints, components, plans), strict=True)
    )
    brief_bytes = b"Recorded brief\n"
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=_SLUG,
            brief_digest=_digest(brief_bytes),
            artifact_digests=tuple(_digest(value) for value in artifact_bytes),
        ),
        content=RoadmapVersionContent(brief_bytes=brief_bytes, artifact_bytes=artifact_bytes),
    )


def _enroll(tmp_path) -> PreparedRoadmapVersion:
    root = _root()
    with roadmap_writer_guard(tmp_path / "plans", _SLUG) as token:
        publish_roadmap_generation(
            build_root_enrollment_generation(root, plans_dir=tmp_path / "plans", slug=_SLUG),
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            writer_token=token,
        )
    return root


def _green_gates(_evidence, *, stages=STAGES):
    return tuple(RoadmapGateOutcome(stage, ()) for stage in stages)


def _delta_response() -> str:
    return json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-order",
                        "row": {
                            "id": "entity-order",
                            "name": "Customer order",
                            "fields": [
                                {
                                    "name": "customer",
                                    "type": "reference",
                                    "entity_id": "entity-customer",
                                }
                            ],
                        },
                    }
                ]
            }
        }
    )


def _initial_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch):
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert result.candidate is not None
    return result.candidate


def _review_required_delta_response() -> str:
    return json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-order",
                        "row": {
                            "id": "entity-order",
                            "name": "Customer order",
                            "fields": [],
                        },
                    }
                ]
            }
        }
    )


def _review_required_initial_candidate(tmp_path, monkeypatch: pytest.MonkeyPatch):
    _enroll(tmp_path)
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", _green_gates)
    result = roadmap_candidate_run.run_initial_candidate_proposal(
        _SLUG,
        _SELECTOR,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )
    assert result.candidate is not None
    assert result.candidate.evidence.review_requirement is not None
    return result.candidate


def _question_response() -> str:
    return json.dumps(
        {
            "anchor": {
                "kind": "diff-row",
                "artifact_key": "domain",
                "row_type": "entities",
                "row_id": "entity-order",
            },
            "question": "Should the customer-facing name use this exact spelling?",
        }
    )


def _question(tmp_path, monkeypatch: pytest.MonkeyPatch):
    initial = _initial_candidate(tmp_path, monkeypatch)
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert result.question_inventory is not None
    return initial, result.question_inventory


def _review_required_question(tmp_path, monkeypatch: pytest.MonkeyPatch):
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert result.question_inventory is not None
    return initial, result.question_inventory


def _move_review_required_head_at_generation_boundary(
    monkeypatch: pytest.MonkeyPatch,
    *,
    plans_dir,
    initial,
) -> None:
    """Make the final publisher recheck observe a head changed after validation."""
    original_publish = roadmap_candidate_review.publish_roadmap_generation
    selector = accepted_head_path(plans_dir, _SLUG)

    def move_head_before_replace(generation, **kwargs):
        recheck = kwargs.pop("before_replace")
        assert recheck is not None

        def stale_then_recheck() -> None:
            selector.write_bytes(
                render_accepted_head(
                    AcceptedRoadmapHead(
                        schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                        roadmap_slug=_SLUG,
                        version_id=initial.version_id,
                    )
                )
            )
            recheck()

        return original_publish(generation, before_replace=stale_then_recheck, **kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "publish_roadmap_generation", move_head_before_replace)


def _eliminated_review_requirement_delta_response() -> str:
    return json.dumps(
        {
            "delta": {
                "operations": [
                    {
                        "op": "replace-row",
                        "feedback_id": "feedback-order",
                        "artifact_key": "domain",
                        "row_type": "entities",
                        "row_id": "entity-order",
                        "row": {
                            "id": "entity-order",
                            "name": "Order",
                            "fields": [
                                {
                                    "name": "customer",
                                    "type": "reference",
                                    "entity_id": "entity-customer",
                                }
                            ],
                        },
                    }
                ]
            }
        }
    )


def _requirement_with_changed_predecessor(
    requirement: roadmap_candidate.CandidateReviewRequirement,
) -> roadmap_candidate.CandidateReviewRequirement:
    predecessor_version_id = "0" * 64
    return roadmap_candidate.CandidateReviewRequirement(
        reason=requirement.reason,
        predecessor_version_id=predecessor_version_id,
        selected_feedback=requirement.selected_feedback,
        capsule_receipt=requirement.capsule_receipt,
        normalized_operations=requirement.normalized_operations,
        predecessor_diff=requirement.predecessor_diff,
        affected_predecessor_members=requirement.affected_predecessor_members,
        impact_atoms=requirement.impact_atoms,
        initial_disclosed_impact_identity=roadmap_candidate._review_impact_identity(
            reason=requirement.reason,
            predecessor_version_id=predecessor_version_id,
            selected_feedback=requirement.selected_feedback,
            receipt=requirement.capsule_receipt,
            normalized_operations=requirement.normalized_operations,
            predecessor_diff=requirement.predecessor_diff,
            affected_predecessor_members=requirement.affected_predecessor_members,
            impact_atoms=requirement.impact_atoms,
        ),
    )


def _inventory_with_requirement(
    inventory: roadmap_candidate_review.CandidateQuestionInventory,
    requirement: roadmap_candidate.CandidateReviewRequirement | None,
) -> roadmap_candidate_review.CandidateQuestionInventory:
    changed = inventory.model_copy(update={"review_requirement": requirement})
    return roadmap_candidate_review.CandidateQuestionInventory(
        schema_version=changed.schema_version,
        inventory_id=roadmap_candidate_review._identity(
            roadmap_candidate_review._inventory_preimage(changed)
        ),
        initial_candidate_version_id=changed.initial_candidate_version_id,
        initial_content_identity=changed.initial_content_identity,
        predecessor_version_id=changed.predecessor_version_id,
        feedback=changed.feedback,
        predecessor_diff=changed.predecessor_diff,
        capsule_identity=changed.capsule_identity,
        question=changed.question,
        review_requirement=requirement,
    )


def test_review_required_question_inventory_binds_exact_stored_requirement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )

    assert result.question_inventory is not None
    assert result.question_inventory.review_requirement == initial.evidence.review_requirement
    assert initial.evidence.review_requirement.initial_disclosed_impact_identity in (
        roadmap_candidate_review.render_question_inventory(result.question_inventory).decode("utf-8")
    )


def test_review_required_requirement_changes_inventory_identity_and_refuses_substitution(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert result.question_inventory is not None
    requirement = initial.evidence.review_requirement
    assert requirement is not None
    substituted = _inventory_with_requirement(
        result.question_inventory, _requirement_with_changed_predecessor(requirement)
    )

    assert substituted.inventory_id != result.question_inventory.inventory_id
    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match="stored initial facts"):
        roadmap_candidate_review._validate_inventory(substituted, initial=initial)


def test_gate_clean_question_inventory_omits_requirement_and_replays_legacy_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _initial, inventory = _question(tmp_path, monkeypatch)
    legacy_bytes = roadmap_candidate_review.render_question_inventory(inventory)

    assert inventory.review_requirement is None
    assert b'"review_requirement"' not in legacy_bytes
    assert roadmap_candidate_review.parse_question_inventory(legacy_bytes) == inventory


def test_review_required_question_prompt_contains_complete_stored_requirement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    requirement = initial.evidence.review_requirement
    assert requirement is not None

    prompt = roadmap_candidate_review.render_candidate_question_prompt(candidate=initial)

    assert roadmap_candidate_review._canonical_json_text(requirement) in prompt
    assert requirement.initial_disclosed_impact_identity in prompt
    assert "It grants no edit, replacement, promotion, or approval" in prompt
    assert "authority." in prompt
    assert "Recorded brief" not in prompt


def test_review_required_inventory_replay_does_not_invoke_or_rewrite(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    first = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert first.question_inventory is not None
    path = roadmap_candidate_review.question_inventory_path(
        tmp_path / "plans", _SLUG, initial.version_id
    )
    stored_bytes = path.read_bytes()

    replay = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored requirement-bearing inventory must not invoke"),
    )

    assert replay.question_inventory == first.question_inventory
    assert replay.call_count == 0
    assert path.read_bytes() == stored_bytes


def test_requirement_removal_refuses_before_question_invocation_or_rewrite(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    first = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert first.question_inventory is not None
    path = roadmap_candidate_review.question_inventory_path(
        tmp_path / "plans", _SLUG, initial.version_id
    )
    tampered_bytes = roadmap_candidate_review.render_question_inventory(
        _inventory_with_requirement(first.question_inventory, None)
    )
    path.write_bytes(tampered_bytes)
    calls: list[str] = []

    rejected = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (calls.append(prompt) or (0, _question_response())),
    )

    assert rejected.outcome == "refused"
    assert rejected.call_count == 0
    assert calls == []
    assert path.read_bytes() == tampered_bytes


def test_reviewer_answer_remains_opaque_through_a_requirement_bearing_inventory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _review_required_initial_candidate(tmp_path, monkeypatch)
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )
    assert result.question_inventory is not None

    blank = roadmap_candidate_review._new_answer(
        inventory=result.question_inventory, answer_text=""
    )
    arbitrary = roadmap_candidate_review._new_answer(
        inventory=result.question_inventory, answer_text="Use a name that feels right."
    )
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        result.question_inventory.question.question_id,
        arbitrary.answer_text,
        plans_dir=tmp_path / "plans",
    )

    assert blank.inventory_id == arbitrary.inventory_id == result.question_inventory.inventory_id
    assert blank.question_id == arbitrary.question_id == result.question_inventory.question.question_id
    assert blank.answer_text == ""
    assert arbitrary.answer_text == "Use a name that feels right."
    assert recorded.answer == arbitrary


def test_review_required_replacement_accepts_eliminated_impact_with_initial_capsule(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Restore the declared relation.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )

    assert result.outcome == "stored"
    assert result.replacement is not None
    assert result.seal is not None
    assert result.replacement.evidence.replacement_review_requirement is None
    assert result.replacement.evidence.replacement_impact_atoms == ()
    assert result.replacement.evidence.capsule == initial.evidence.capsule
    assert result.replacement.evidence.receipt == initial.evidence.receipt
    assert not roadmap_candidate_review.replacement_state_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_review_required_replacement_retains_its_recomputed_requirement_and_identity(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    initial_requirement = initial.evidence.review_requirement
    assert initial_requirement is not None

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Keep the exact declared relation change.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _review_required_delta_response()),
    )

    assert result.outcome == "stored"
    assert result.replacement is not None
    replacement = result.replacement.evidence
    assert replacement.replacement_review_requirement is not None
    assert replacement.replacement_review_requirement.impact_atoms == replacement.replacement_impact_atoms
    assert replacement.replacement_impact_identity != initial_requirement.initial_disclosed_impact_identity
    assert result.seal is not None


def test_review_required_replacement_refuses_uncontained_gate_clean_impact_without_storage(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    calls: list[str] = []

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Make a different authorized change.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (calls.append(prompt) or (0, _delta_response())),
    )

    assert result.outcome == "response-rejected"
    assert result.replacement is None
    assert result.seal is None
    assert len(calls) == 1
    assert not roadmap_candidate_review.replacement_binding_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_review_required_replacement_rejects_expansion_without_writing_state(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    compact = initial.evidence.capsule.inventory[0]
    calls: list[str] = []

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Need more context.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (
            calls.append(prompt) or (0, json.dumps({"expand": compact.model_dump(mode="json")}))
        ),
    )

    assert result.outcome == "response-rejected"
    assert len(calls) == 1
    assert not roadmap_candidate_review.replacement_state_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_request_replacement_surfaces_a_missing_prompt_template_as_failed_not_uncaught(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # A missing template raises CandidateProposalError (a ValueError, not an
    # OSError); request_replacement's except clauses must catch it too.
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None

    monkeypatch.setattr(roadmap_candidate_run, "prompts_dir", lambda: tmp_path / "no-such-prompts-dir")

    result = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("must fail before invocation on a missing template"),
    )

    assert result.outcome == "failed"
    assert "no candidate prompt template" in result.detail


@pytest.mark.parametrize("symlink", (False, True))
def test_review_required_replacement_refuses_preexisting_expansion_state_before_invocation(
    tmp_path, monkeypatch: pytest.MonkeyPatch, symlink: bool
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Do not invoke the model.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    path = roadmap_candidate_review.replacement_state_path(
        tmp_path / "plans", _SLUG, initial.version_id
    )
    if symlink:
        path.symlink_to(tmp_path / "unreadable-state")
    else:
        path.write_bytes(b"unreadable-state")

    result = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("review-required state must refuse before invocation"),
    )

    assert result.outcome == "refused"
    assert result.call_count == 0
    assert path.is_symlink() if symlink else path.read_bytes() == b"unreadable-state"


def test_review_required_answer_flow_refuses_expansion_state_before_writing_an_answer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    roadmap_candidate_review.replacement_state_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).write_bytes(b"unreadable-state")

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Do not write an answer.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("review-required state must refuse before invocation"),
    )

    assert result.outcome == "refused"
    assert not roadmap_candidate_review.reviewer_answer_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_review_required_replacement_revalidates_the_persisted_atom_stream_before_seal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    requested = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )
    assert requested.replacement is not None
    initial_requirement = initial.evidence.review_requirement
    assert initial_requirement is not None
    substituted = replace(
        requested.replacement,
        evidence=requested.replacement.evidence.model_copy(
            update={
                "replacement_impact_atoms": initial_requirement.impact_atoms,
                "replacement_impact_identity": roadmap_candidate.candidate_impact_identity(
                    initial_requirement.impact_atoms
                ),
            }
        ),
    )

    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match="impact atoms"):
        roadmap_candidate_review._validate_replacement(
            substituted,
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            initial=initial,
            inventory=inventory,
            answer=recorded.answer,
        )


def test_stale_review_required_lineage_refuses_replacement_write_before_invocation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    selector = accepted_head_path(tmp_path / "plans", _SLUG)
    selector.write_bytes(
        render_accepted_head(
            AcceptedRoadmapHead(
                schema_version=ROADMAP_VERSION_SCHEMA_VERSION,
                roadmap_slug=_SLUG,
                version_id=initial.version_id,
            )
        )
    )

    refused = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stale review-required lineage must not invoke"),
    )

    assert refused.outcome == "refused"
    assert refused.call_count == 0
    assert not roadmap_candidate_review.replacement_binding_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_prechange_gate_clean_replacement_evidence_replays_and_seals(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    requested = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert requested.replacement is not None
    evidence_path = roadmap_candidate_review.replacement_evidence_path(
        tmp_path / "plans", _SLUG, requested.replacement.version_id
    )
    legacy_payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    for field in (
        "replacement_impact_atoms",
        "replacement_impact_identity",
        "replacement_review_requirement",
    ):
        legacy_payload.pop(field)
    legacy_bytes = roadmap_candidate_review._canonical_json_bytes(legacy_payload)
    evidence_path.write_bytes(legacy_bytes)

    replay = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("legacy replacement must replay without a model call"),
    )
    sealed = roadmap_candidate_review.seal_review(
        _SLUG, requested.replacement.version_id, plans_dir=tmp_path / "plans"
    )

    assert replay.replacement is not None
    assert replay.replacement.version_id == requested.replacement.version_id
    assert replay.replacement.evidence.replacement_impact_atoms is None
    assert sealed.outcome == "stored"
    assert roadmap_candidate_review.render_replacement_evidence(replay.replacement.evidence) == legacy_bytes


def test_review_required_answer_refuses_when_head_changes_at_publish_boundary(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    _move_review_required_head_at_generation_boundary(
        monkeypatch, plans_dir=tmp_path / "plans", initial=initial
    )

    refused = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )

    assert refused.outcome == "refused"
    assert not roadmap_candidate_review.reviewer_answer_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_review_required_replacement_refuses_when_head_changes_at_publish_boundary(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    _move_review_required_head_at_generation_boundary(
        monkeypatch, plans_dir=tmp_path / "plans", initial=initial
    )

    refused = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )

    assert refused.outcome == "refused"
    assert not roadmap_candidate_review.replacement_binding_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_review_required_seal_refuses_when_head_changes_at_publish_boundary(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Restore the relation.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    requested = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )
    assert requested.replacement is not None
    _move_review_required_head_at_generation_boundary(
        monkeypatch, plans_dir=tmp_path / "plans", initial=initial
    )

    refused = roadmap_candidate_review.seal_review(
        _SLUG, requested.replacement.version_id, plans_dir=tmp_path / "plans"
    )

    assert refused.outcome == "refused"
    assert not roadmap_candidate_review.review_seal_path(
        tmp_path / "plans", _SLUG, roadmap_candidate_review._new_seal(
            initial=initial,
            inventory=inventory,
            answer=recorded.answer,
            replacement=requested.replacement,
        ).seal_id
    ).exists()


def test_question_request_uses_only_stored_candidate_diff_feedback_closure_and_identity_inventory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)
    captured: list[str] = []

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda prompt: (captured.append(prompt) or (0, _question_response())),
    )

    assert result.outcome == "stored"
    assert len(captured) == 1
    prompt = captured[0]
    assert "Customer order" in prompt
    assert "feedback-order" in prompt
    assert '"inclusion_reasons"' in prompt
    assert '"relation_evidence"' in prompt
    assert '"source_index"' in prompt
    assert "Recorded brief" not in prompt
    assert "Do not inspect repository files" in prompt


@pytest.mark.parametrize(
    "response",
    (
        '{"anchor":{"kind":"feedback","artifact_key":"domain","feedback_id":"feedback-order"},"question":""}',
        '{"anchor":{"kind":"inventory","artifact_key":"domain","row_type":"EntityRow","row_id":"entity-compact"},"question":"opaque"}',
        '{"anchor":{"kind":"feedback","artifact_key":"domain","feedback_id":"feedback-order","row_id":"entity-order"},"question":"bad"}',
        '{"anchor":{"kind":"unknown"},"question":"bad"}',
        '{"anchor":{"kind":"feedback","artifact_key":"domain","feedback_id":"feedback-order"},"question":"a","extra":1}',
        '{"anchor":{"kind":"feedback","artifact_key":"domain","feedback_id":"feedback-order"},"question":"a","question":"b"}',
    ),
)
def test_question_response_requires_one_closed_resolvable_anchor(
    tmp_path, monkeypatch: pytest.MonkeyPatch, response: str
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    expected = "stored" if "entity-compact" in response or '"question":""' in response else "response-rejected"
    assert result.outcome == expected


def test_candidate_question_rejection_records_its_reason_and_exact_response_receipt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))
    response = (
        '{"anchor":{"kind":"feedback","artifact_key":"domain",'
        '"feedback_id":"feedback-order"},"question":"review response secret","extra":1}'
    )

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "response-rejected"
    assert result.detail == "candidate question response has unknown or missing fields"
    assert failure["phase"] == "roadmap-candidate-question"
    assert failure["reason"] == result.detail
    assert failure["raw_bytes"] == len(response.encode("utf-8"))
    assert failure["response_digest"] == _digest(response.encode("utf-8"))
    assert failure["response_capture"] == "stored"
    assert (tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == response
    assert terminal["failure_detail"] == result.detail
    assert "review response secret" not in log_path.read_text(encoding="utf-8")


def test_question_second_interrupt_during_run_interrupted_still_records_the_interrupted_outcome(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))

    monkeypatch.setattr(
        run_log_module, "_append_jsonl_line", _raise_interrupt_for_run_log_events("run_interrupted")
    )

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=_interrupting_invoker,
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)

    assert result.outcome == "interrupted"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["interrupted"]


def test_question_second_interrupt_during_failure_diagnostics_setup_still_reaches_phase_end_and_run_end(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_finish_log's call to record_candidate_failure_diagnostics was
    unguarded even after its *internal* calls were guarded — a second
    KeyboardInterrupt landing in its setup (encode/digest/path-building,
    before either of its own guarded calls) must not stop phase_end/run_end
    from still being attempted."""
    initial = _initial_candidate(tmp_path, monkeypatch)
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))
    response = (
        '{"anchor":{"kind":"feedback","artifact_key":"domain",'
        '"feedback_id":"feedback-order"},"question":"review response secret","extra":1}'
    )
    original_digest = roadmap_candidate_run._digest

    def interrupt_digest(value: bytes) -> str:
        if value == response.encode("utf-8"):
            raise KeyboardInterrupt
        return original_digest(value)

    monkeypatch.setattr(roadmap_candidate_run, "_digest", interrupt_digest)

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)

    assert result.outcome == "response-rejected"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["response-rejected"]
    assert not any(event["event"] == "parse_failure" for event in events)
    terminal = next(event for event in events if event["event"] == "phase_end")
    assert terminal["failure_detail"] == result.detail
    assert terminal["failure_attempt"] == 1
    assert terminal["failure_call_count"] == result.call_count
    assert terminal["response_capture"] == "unavailable"


def test_question_storage_failure_after_a_valid_response_is_not_recorded_as_a_parse_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))

    def fail_publish(**_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(roadmap_candidate_review, "_publish_new_record", fail_publish)

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _question_response()),
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "failed"
    assert not any(event["event"] == "parse_failure" for event in events)
    assert terminal["response_capture"] == "not-applicable"


def test_question_inventory_is_candidate_bound_reusable_and_replacement_is_refused_before_invocation(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    repeated = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored inventory must not invoke"),
    )
    rejected = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        "0" * 64,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("replacement identity must not invoke"),
    )

    assert repeated.question_inventory == inventory
    assert repeated.call_count == 0
    assert rejected.outcome == "refused"
    assert rejected.call_count == 0


def test_candidate_replacement_transport_failure_records_its_response_receipt(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))
    response = "replacement backend failure secret"

    result = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (17, response),
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)
    failure = next(event for event in events if event["event"] == "parse_failure")
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "failed"
    assert result.detail == "candidate replacement backend request failed"
    assert failure["phase"] == "roadmap-candidate-replacement"
    assert failure["attempt"] == 1
    assert failure["outcome"] == "failed"
    assert failure["reason"] == result.detail
    assert failure["response_digest"] == _digest(response.encode("utf-8"))
    assert (tmp_path / failure["failure_path"]).read_text(encoding="utf-8") == response
    assert terminal["failure_response_bytes"] == len(response.encode("utf-8"))
    assert "replacement backend failure secret" not in log_path.read_text(encoding="utf-8")


def test_reviewer_answer_is_immutable_and_bound_to_the_question_inventory(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    first = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "",
        plans_dir=tmp_path / "plans",
        question_inventory_id=inventory.inventory_id,
    )
    replay = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "",
        plans_dir=tmp_path / "plans",
    )
    changed = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "different",
        plans_dir=tmp_path / "plans",
    )
    wrong_inventory = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "",
        plans_dir=tmp_path / "plans",
        question_inventory_id="1" * 64,
    )

    assert first.answer is not None
    assert replay.answer == first.answer
    assert first.answer.answer_text == ""
    assert changed.outcome == "refused"
    assert wrong_inventory.outcome == "refused"
    assert initial.content.brief_bytes == b"Recorded brief\n"


def test_review_pair_permits_opaque_blank_text() -> None:
    pair = roadmap_candidate_run.CandidateReviewPair(
        question_id="question-1",
        anchor="{\"row_id\":\"entity-order\"}",
        question_text="",
        answer_id="answer-1",
        answer_text="",
    )

    assert pair.question_text == ""
    assert pair.answer_text == ""


def test_shell_candidate_review_invoker_accepts_the_replacement_phase(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def invoke(_prompt: str, **kwargs: object) -> tuple[int, str]:
        seen.update(kwargs)
        return 0, "{}"

    monkeypatch.setattr(roadmap_candidate_review.shell, "claude_invoke", invoke)

    assert roadmap_candidate_review.shell_candidate_review_invoker(
        "prompt", phase="roadmap-candidate-replacement"
    ) == (0, "{}")
    assert seen["phase"] == "roadmap-candidate-replacement"


def test_answer_replacement_creates_distinct_candidate_and_exact_review_seal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    initial_artifacts = initial.content.artifact_bytes

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    replay = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("stored replacement must not invoke"),
    )

    assert result.outcome == "stored"
    assert result.replacement is not None
    assert result.seal is not None
    assert result.replacement.version_id != initial.version_id
    assert result.replacement.record.content_identity == initial.record.content_identity
    assert initial.content.artifact_bytes == initial_artifacts
    assert replay.replacement == result.replacement
    assert replay.seal == result.seal


def test_replacement_second_interrupt_during_run_interrupted_still_records_the_interrupted_outcome(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))

    monkeypatch.setattr(
        run_log_module, "_append_jsonl_line", _raise_interrupt_for_run_log_events("run_interrupted")
    )

    result = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=_interrupting_invoker,
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)

    assert result.outcome == "interrupted"
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["interrupted"]


def test_replacement_storage_failure_after_a_valid_response_is_not_recorded_as_a_parse_failure(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    runs_dir = tmp_path / ".plan-tool" / "runs" / _SLUG
    prior_logs = set(runs_dir.glob("*.jsonl"))

    def fail_store(**_kwargs):
        raise roadmap_candidate_review.CandidateReviewError("replacement storage unavailable")

    monkeypatch.setattr(roadmap_candidate_review, "_store_replacement", fail_store)

    result = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )

    log_path = next(iter(set(runs_dir.glob("*.jsonl")) - prior_logs))
    events = read_run_events(log_path)
    terminal = next(event for event in events if event["event"] == "phase_end")

    assert result.outcome == "refused"
    assert not any(event["event"] == "parse_failure" for event in events)
    assert terminal["response_capture"] == "not-applicable"


def test_review_seal_refuses_a_replacement_not_bound_to_the_initial_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        plans_dir=tmp_path / "plans",
    )
    assert recorded.answer is not None
    requested = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        recorded.answer.answer_text,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )
    assert requested.replacement is not None
    monkeypatch.setattr(
        roadmap_candidate_review,
        "load_stored_candidate_review_replacement",
        lambda **_kwargs: requested.replacement,
    )

    sealed = roadmap_candidate_review.seal_review(
        _SLUG,
        "0" * 64,
        plans_dir=tmp_path / "plans",
    )

    assert sealed.outcome == "refused"
    assert sealed.seal is None


def test_answer_driven_replacement_spends_the_recorded_expansion_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _question(tmp_path, monkeypatch)
    compact = initial.evidence.capsule.inventory[0]
    calls: list[str] = []

    def invoke(prompt: str) -> tuple[int, str]:
        calls.append(prompt)
        if len(calls) == 1:
            return 0, json.dumps({"expand": compact.model_dump(mode="json")})
        return 0, _delta_response()

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Need compact context.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=invoke,
    )
    state = roadmap_candidate_review.parse_replacement_state(
        roadmap_candidate_review.replacement_state_path(
            tmp_path / "plans", _SLUG, initial.version_id
        ).read_bytes()
    )

    assert result.outcome == "stored"
    assert result.replacement is not None
    assert result.call_count == 2
    assert state.capsule.expansion is not None
    assert state.capsule.ceiling_bytes == CANDIDATE_CONTEXT_MAX_BYTES
    assert len(calls) == 2

    assert result.answer is not None
    substituted = replace(
        result.replacement,
        evidence=result.replacement.evidence.model_copy(
            update={
                "capsule": initial.evidence.capsule,
                "receipt": initial.evidence.receipt,
            }
        ),
    )
    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match="exact stored review pair"):
        roadmap_candidate_review._validate_replacement(
            substituted,
            plans_dir=tmp_path / "plans",
            slug=_SLUG,
            initial=initial,
            inventory=inventory,
            answer=result.answer,
        )

    invalid_expansion = state.capsule.expansion.model_copy(
        update={"parent_capsule_identity": "0" * 64}
    )
    payload = json.loads(state.capsule.payload)
    payload["expansion"]["parent_capsule_identity"] = "0" * 64
    invalid_payload = roadmap_candidate_run._canonical_json_bytes(payload)
    invalid_identity = roadmap_candidate_run._digest(invalid_payload)
    invalid_receipt = state.receipt.model_copy(
        update={
            "payload_bytes": len(invalid_payload),
            "payload_digest": invalid_identity,
            "capsule_identity": invalid_identity,
            "expansion": invalid_expansion,
        }
    )
    invalid_capsule = state.capsule.model_copy(
        update={
            "payload": invalid_payload,
            "capsule_identity": invalid_identity,
            "receipt": invalid_receipt,
            "expansion": invalid_expansion,
        }
    )
    invalid_state = state.model_copy(
        update={"capsule": invalid_capsule, "receipt": invalid_receipt}
    )
    roadmap_candidate_review.replacement_state_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).write_bytes(roadmap_candidate_review.render_replacement_state(invalid_state))

    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match="initial candidate"):
        roadmap_candidate_review._replacement_capsule(
            plans_dir=tmp_path / "plans", slug=_SLUG, initial=initial
        )


def test_candidate_review_invoker_and_run_log_are_bounded_and_redacted(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = _initial_candidate(tmp_path, monkeypatch)
    response = _question_response().replace("exact spelling", "reviewer secret")
    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        initial.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, response),
    )
    log_path = next((tmp_path / ".plan-tool" / "runs" / _SLUG).glob("*.jsonl"))
    events = read_run_events(log_path)
    raw = log_path.read_text(encoding="utf-8")

    assert result.outcome == "stored"
    assert len([event for event in events if event["event"] == "claude_call_start"]) == 1
    assert [event["outcome"] for event in events if event["event"] == "run_end"] == ["stored"]
    assert "reviewer secret" not in raw
    assert "Use the customer-facing order name." not in raw


def test_question_inventory_binds_the_exact_active_candidate_batch() -> None:
    """Keep batch review facts separate from the candidate's direct source."""
    root = "a" * 64
    source = "b" * 64
    candidate_id = "c" * 64
    receipt = CandidateContextBatchReceipt.model_construct(
        root=CandidateContextPredecessor.model_construct(version_id=root),
        source=CandidateContextPredecessor.model_construct(version_id=source),
        capsule_identity="d" * 64,
        reviewer_items=(), derived_context=(), full_members=(), relation_evidence=(), inventory=(),
    )
    evidence = roadmap_candidate_run.CandidateProposalEvidence.model_construct(
        roadmap_slug=_SLUG, candidate_version_id=candidate_id, predecessor_version_id=source,
        content_identity="e" * 64,
        predecessor_diff=roadmap_candidate.CandidatePredecessorDiff(
            changed_artifacts=(), changed_rows=(), added_relations=(), removed_relations=()
        ),
        capsule=receipt, receipt=receipt, batch_receipt=receipt, root_version_id=root,
        source_version_id=source,
    )
    candidate = roadmap_candidate_run.StoredCandidateProposal(
        record=roadmap_candidate_run.StoredRoadmapVersion.model_construct(
            version_id=candidate_id, content_identity="e" * 64
        ),
        content=roadmap_candidate_run.RoadmapVersionContent(b"", tuple(b"" for _ in STAGES)), evidence=evidence,
    )
    anchor = roadmap_candidate_review.CandidateQuestionAnchor(
        kind="inventory", artifact_key="domain", row_type="entity", row_id="order"
    )
    question = roadmap_candidate_review.CandidateQuestion(
        question_id=roadmap_candidate_review._identity({
            "schema_version": 1,
            "anchor": anchor,
            "question_text": "What needs confirmation?",
        }),
        anchor=anchor, question_text="What needs confirmation?",
    )

    inventory = roadmap_candidate_review._new_question_inventory(initial=candidate, question=question)

    assert (inventory.initial_candidate_version_id, inventory.root_version_id, inventory.source_version_id) == (
        candidate_id, root, source
    )
    assert inventory.batch_receipt_identity == receipt.capsule_identity
    assert inventory.feedback is None


# --------------------------------------------------------------------------
# Batch bindings on replacement evidence and seals
# --------------------------------------------------------------------------

# Captured from the selector-era flow at e9a3e30b, before the batch route existed. It is the
# pre-batch value on purpose: every id in it (candidate, inventory, answer, seal) must keep
# recomputing to what an already-stored selector-era lifecycle holds.
_LEGACY_SEAL_BYTES = (
    b'{"answer_ids":["3c3e5b019c135747ad842ad1d93272255b91989c14fe699d0a25a8cf2732a6f7"],'
    b'"answer_incorporation_id":"8e77839498f79d07dc01d1bfe68911c3e83dea20ecaa18af49dbd93e63083b1f",'
    b'"final_capsule_identity":"71de80b8789ea0d9cdfbfdd53ec25940d839c2696e7d90bba7a34bcf4ae37bbf",'
    b'"initial_candidate_version_id":"ad11afeba4192ceab3872deb3f5fe39387b310d35516d3e17c96330390683904",'
    b'"question_inventory_id":"cc6449d8d0a84a109c4bb95ba68415b7ff59367f0be5d60a96beda9e545f981e",'
    b'"replacement_candidate_version_id":"22968f256f390183fff58e65ed0465081c94e4908a1182da7d4c2c2c3446bb22",'
    b'"replacement_content_identity":"223e5bed16c7ff14bfb348c4c09eeae354f8ccf6bc33a3f7763b5932388ace8f",'
    b'"roadmap_slug":"storefront","schema_version":1,'
    b'"seal_id":"a81b1f480a80fac85ce15ea51de91c83e922f446ca8905ef0df842fe2861a297"}'
)
_BATCH_FIELDS = (
    "root_version_id", "source_version_id", "batch_receipt_identity", "response_patch",
    "derived_feedback",
)


@pytest.mark.parametrize("kind", ("reviewer-item", "response", "derived-context"))
def test_batch_only_anchor_kinds_never_resolve_for_a_selector_era_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch, kind: str
) -> None:
    """These kinds are defined only for a batch receipt. On a selector-era candidate they
    must not fall through to the inventory lookup and resolve by sharing a row identity."""
    initial, _inventory = _question(tmp_path, monkeypatch)
    entry = initial.evidence.receipt.inventory[0]
    identity = {"artifact_key": entry.artifact_key, "row_type": entry.row_type, "row_id": entry.row_id}

    batch_only = roadmap_candidate_review.CandidateQuestionAnchor(kind=kind, **identity)
    control = roadmap_candidate_review.CandidateQuestionAnchor(kind="inventory", **identity)

    assert not roadmap_candidate_review._anchor_resolves(batch_only, candidate=initial)
    assert roadmap_candidate_review._anchor_resolves(control, candidate=initial)


def test_selector_era_replacement_stores_when_the_model_answers_the_shape_its_prompt_asks_for(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replacement request renders the same delta prompt as the initial proposal, so a
    selector-era replacement must be prompted for the shape the selector parser accepts."""
    _initial, inventory = _question(tmp_path, monkeypatch)

    result = roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=_prompt_following_invoker(
            selector_reply=_delta_response(), batch_reply=json.loads(_batch_replacement_response())
        ),
    )

    assert result.replacement is not None and result.seal is not None


# The ceiling the pinned stored-era values were issued under; a literal fact, not the current constant.
PRIOR_CEILING_BYTES = 192 * 1024


def _selector_era_review(tmp_path, monkeypatch: pytest.MonkeyPatch):
    # Issued under the 192 KiB ceiling, then continued under the current one: a stored lineage
    # reproduces at its recorded ceiling, so these pinned stored-era bytes cannot move.
    with monkeypatch.context() as issued_under_prior_ceiling:
        issued_under_prior_ceiling.setattr(
            roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", PRIOR_CEILING_BYTES
        )
        _initial, inventory = _question(tmp_path, monkeypatch)
    return roadmap_candidate_review.answer_candidate_question(
        _SLUG,
        inventory.question.question_id,
        "Use the conventional spelling.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _delta_response()),
    )


def test_selector_era_seal_and_replacement_bytes_are_unchanged_by_the_batch_fields(
    tmp_path, monkeypatch
) -> None:
    """Existing on-disk seals and replacement evidence must keep their exact bytes
    and identity: the optional batch fields are absent from them, not null."""
    result = _selector_era_review(tmp_path, monkeypatch)

    assert result.seal is not None and result.replacement is not None
    assert roadmap_candidate_review.render_review_seal(result.seal) == _LEGACY_SEAL_BYTES
    assert roadmap_candidate_review.parse_review_seal(_LEGACY_SEAL_BYTES) == result.seal
    assert result.seal.root_version_id is None
    evidence_bytes = roadmap_candidate_review.render_replacement_evidence(result.replacement.evidence)
    assert set(json.loads(evidence_bytes)).isdisjoint(_BATCH_FIELDS)
    assert (
        roadmap_candidate_review.render_replacement_evidence(
            roadmap_candidate_review.parse_replacement_evidence(evidence_bytes)
        )
        == evidence_bytes
    )


def _batch_replacement_payload(tmp_path, monkeypatch) -> tuple[dict, dict]:
    """A batch-shaped replacement payload derived from a real selector-era one, plus that original."""
    result = _selector_era_review(tmp_path, monkeypatch)
    assert result.replacement is not None
    original = json.loads(
        roadmap_candidate_review.replacement_evidence_path(
            tmp_path / "plans", _SLUG, result.replacement.version_id
        ).read_text(encoding="utf-8")
    )
    payload = dict(original)
    for field in (
        "feedback", "capsule", "receipt", "replacement_impact_atoms",
        "replacement_impact_identity", "replacement_review_requirement",
    ):
        payload.pop(field)
    payload.update(
        root_version_id="1" * 64,
        source_version_id=payload["predecessor_version_id"],
        batch_receipt_identity="3" * 64,
        response_patch={"entries": []},
        derived_feedback=[],
    )
    return payload, original


def _validate_replacement_payload(payload: dict):
    return roadmap_candidate_review.CandidateReviewReplacement.model_validate_json(json.dumps(payload))


def test_batch_replacement_evidence_requires_its_complete_batch_binding_and_no_selector_evidence(
    tmp_path, monkeypatch
) -> None:
    payload, original = _batch_replacement_payload(tmp_path, monkeypatch)

    accepted = _validate_replacement_payload(payload)
    rendered = roadmap_candidate_review.render_replacement_evidence(accepted)
    assert roadmap_candidate_review.parse_replacement_evidence(rendered) == accepted
    assert set(_BATCH_FIELDS) <= set(json.loads(rendered))

    for field in _BATCH_FIELDS:
        incomplete = {key: value for key, value in payload.items() if key != field}
        with pytest.raises(ValueError, match="batch binding is incomplete"):
            _validate_replacement_payload(incomplete)
    with pytest.raises(ValueError, match="cannot substitute selector evidence"):
        _validate_replacement_payload({**payload, "feedback": original["feedback"]})
    with pytest.raises(ValueError, match="cannot substitute selector evidence"):
        _validate_replacement_payload({**payload, "capsule": original["capsule"]})
    with pytest.raises(ValueError, match="predecessor must be its reviewed source"):
        _validate_replacement_payload({**payload, "predecessor_version_id": "4" * 64})
    with pytest.raises(ValueError):
        _validate_replacement_payload({**payload, "batch_receipt_identity": "not-a-digest"})


def test_selector_replacement_evidence_still_requires_feedback_capsule_and_receipt(
    tmp_path, monkeypatch
) -> None:
    result = _selector_era_review(tmp_path, monkeypatch)
    assert result.replacement is not None
    legacy = json.loads(
        roadmap_candidate_review.replacement_evidence_path(
            tmp_path / "plans", _SLUG, result.replacement.version_id
        ).read_text(encoding="utf-8")
    )

    _validate_replacement_payload(legacy)
    for field in ("feedback", "capsule", "receipt"):
        with pytest.raises(ValueError, match="inconsistent immutable bindings"):
            _validate_replacement_payload({key: value for key, value in legacy.items() if key != field})
    with pytest.raises(ValueError, match="batch binding is incomplete"):
        _validate_replacement_payload({**legacy, "root_version_id": "1" * 64})


def _seal_values(**extra) -> dict:
    return {
        "schema_version": 1,
        "roadmap_slug": "storefront",
        "initial_candidate_version_id": "1" * 64,
        "question_inventory_id": "2" * 64,
        "answer_ids": ("3" * 64,),
        "replacement_candidate_version_id": "4" * 64,
        "replacement_content_identity": "5" * 64,
        "answer_incorporation_id": "6" * 64,
        "final_capsule_identity": "7" * 64,
        **extra,
    }


def test_batch_seal_identity_binds_root_source_and_batch_but_a_selector_seal_does_not() -> None:
    batch_fields = {"root_version_id": "a" * 64, "source_version_id": "b" * 64, "batch_receipt_identity": "c" * 64}
    plain = roadmap_candidate_review.CandidateReviewSeal(
        seal_id=roadmap_candidate_review._identity(_seal_values()), **_seal_values()
    )
    batch = roadmap_candidate_review.CandidateReviewSeal(
        seal_id=roadmap_candidate_review._identity(
            {**_seal_values(), **batch_fields}
        ),
        **_seal_values(**batch_fields),
    )

    assert batch.seal_id != plain.seal_id
    rendered = roadmap_candidate_review.render_review_seal(batch)
    assert set(json.loads(rendered)) >= set(batch_fields)
    assert roadmap_candidate_review.parse_review_seal(rendered) == batch
    assert set(json.loads(roadmap_candidate_review.render_review_seal(plain))).isdisjoint(batch_fields)
    with pytest.raises(ValueError, match="does not bind its complete review"):
        roadmap_candidate_review.CandidateReviewSeal(
            seal_id=batch.seal_id, **_seal_values(**{**batch_fields, "source_version_id": "d" * 64})
        )
    with pytest.raises(ValueError, match="batch binding is incomplete"):
        roadmap_candidate_review.CandidateReviewSeal(
            seal_id=batch.seal_id, **_seal_values(root_version_id="a" * 64)
        )


# --------------------------------------------------------------------------
# Ledger-batch replacement
# --------------------------------------------------------------------------

_BATCH_ANSWER = "Use the conventional spelling."


def _batch_question_response() -> str:
    return json.dumps(
        {
            "anchor": {
                "kind": "reviewer-item",
                "artifact_key": "ledger",
                "row_type": "reviewer-item",
                "row_id": "batch-one",
            },
            "question": "Should the customer-facing name use this exact spelling?",
        }
    )


def _batch_replacement_response() -> str:
    return json.dumps(
        {
            "operations": [
                {
                    "op": "replace-row",
                    "feedback_id": "batch-one",
                    "artifact_key": "domain",
                    "row_type": "entities",
                    "row_id": "entity-order",
                    "row": {
                        "id": "entity-order",
                        "name": "Customer order",
                        "fields": [
                            {"name": "customer", "type": "reference", "entity_id": "entity-customer"}
                        ],
                    },
                }
            ],
            "responses": [{"item_id": "batch-one", "response": "Use the conventional spelling."}],
            "derived_feedback": [{"context_id": "derived-replacement", "content": "Spelling settled."}],
        }
    )


def _batch_review(tmp_path, monkeypatch):
    """A real ledger-batch candidate with a stored question and recorded answer."""
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    first = _run_batch(tmp_path, _FIRST_BATCH_DELTA)
    assert first.candidate is not None
    asked = roadmap_candidate_review.generate_candidate_question(
        _SLUG,
        first.candidate.version_id,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _batch_question_response()),
    )
    assert asked.question_inventory is not None
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG, asked.question_inventory.question.question_id, _BATCH_ANSWER, plans_dir=tmp_path / "plans"
    )
    assert recorded.answer is not None
    return root, first.candidate, asked.question_inventory


def _request_batch_replacement(tmp_path, inventory, *, invoker=None):
    return roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        _BATCH_ANSWER,
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=invoker or (lambda _prompt: (0, _batch_replacement_response())),
    )


def test_batch_replacement_prompt_uses_immutable_source_collection_hints(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    prompts: list[str] = []
    result = _request_batch_replacement(
        tmp_path, inventory,
        invoker=lambda prompt: (prompts.append(prompt) or (0, _batch_replacement_response())),
    )

    assert result.outcome == "stored", result.detail
    assert len(prompts) == 1
    assert '"EntityRow":["entities"]' in prompts[0]
    assert '"PatternRow":["system_patterns","component_patterns"]' in prompts[0]
    assert "Every eligible `add-row` must include its required `prose_amendment` object" in prompts[0]
    assert _BATCH_ANSWER in prompts[0]


def test_batch_question_prompt_offers_no_response_anchor_and_keeps_the_others(tmp_path, monkeypatch) -> None:
    """Batch evidence retains no response text, so the prompt must not offer an anchor on one."""
    _root, initial, _inventory = _batch_review(tmp_path, monkeypatch)

    prompt = roadmap_candidate_review.render_candidate_question_prompt(candidate=initial)

    assert '"kind":"response"' not in prompt
    assert "persisted proposed response" not in prompt
    for kind in ("reviewer-item", "derived-context", "diff-row", "full-member", "inventory"):
        assert f'"kind":"{kind}"' in prompt


def test_batch_question_anchored_on_a_response_is_refused_with_the_explicit_reason(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, initial = _store_first_batch_candidate(tmp_path, monkeypatch)
    reply = json.dumps(
        {
            "anchor": {"kind": "response", "artifact_key": "ledger", "row_type": "response", "row_id": "batch-one"},
            "question": "Why this response?",
        }
    )

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG, initial.version_id, repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, reply),
    )

    assert result.outcome == "response-rejected"
    assert "cannot anchor on a response" in result.detail
    assert "does not resolve" not in result.detail


def test_batch_response_anchor_never_resolves_even_when_a_receipt_snapshot_carries_a_proposal(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The receipt snapshots the question prompt shows come from admission, where an item
    is still open and has no proposal; a snapshot that did carry one still may not make a
    response anchor resolve, because the evidence keeps no response text to ground it."""
    _root, initial = _store_first_batch_candidate(tmp_path, monkeypatch)
    receipt = initial.evidence.batch_receipt
    item = receipt.reviewer_items[0]
    proposed = item.model_copy(update={"proposal": ProposalFields(response="Rename it.")})
    candidate = replace(
        initial,
        evidence=initial.evidence.model_copy(
            update={"batch_receipt": receipt.model_copy(update={"reviewer_items": (proposed, *receipt.reviewer_items[1:])})}
        ),
    )
    identity = {"artifact_key": "ledger", "row_id": item.item_id}

    response = roadmap_candidate_review.CandidateQuestionAnchor(kind="response", row_type="response", **identity)
    control = roadmap_candidate_review.CandidateQuestionAnchor(kind="reviewer-item", row_type="reviewer-item", **identity)

    assert not roadmap_candidate_review._anchor_resolves(response, candidate=candidate)
    assert roadmap_candidate_review._anchor_resolves(control, candidate=candidate)


def test_batch_replacement_stores_when_the_model_answers_the_shape_its_prompt_asks_for(
    tmp_path, monkeypatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)

    result = _request_batch_replacement(
        tmp_path,
        inventory,
        invoker=_prompt_following_invoker(
            selector_reply=_delta_response(), batch_reply=json.loads(_batch_replacement_response())
        ),
    )

    assert result.outcome == "stored", result.detail


def test_answered_replacement_that_is_structural_is_refused_even_for_a_presentation_only_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replacement's own classification gates storage, not only the initial candidate's:
    a presentation-only candidate must not reach a structural head through the answered route."""
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    assert initial.evidence.operation_classification is (
        roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
    )
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    result = _request_batch_replacement(
        tmp_path, inventory, invoker=lambda _prompt: (0, json.dumps(_structural_batch_delta()))
    )

    assert result.outcome == "response-rejected"
    assert "--decide-candidate" in result.detail
    assert _tree(plans_dir) == before


def test_batch_replacement_materializes_from_the_reviewed_source_and_binds_root_source_and_batch(
    tmp_path, monkeypatch
) -> None:
    root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger_before = ledger_path.read_bytes()
    admission_before = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes()

    result = _request_batch_replacement(tmp_path, inventory)

    assert result.outcome == "stored", result.detail
    replacement = result.replacement
    assert replacement is not None
    assert replacement.version_id != initial.version_id
    assert replacement.record.predecessor_version_id == initial.evidence.source_version_id
    assert replacement.content.artifact_bytes != initial.content.artifact_bytes
    evidence = replacement.evidence
    assert (evidence.root_version_id, evidence.source_version_id) == (
        initial.evidence.root_version_id, initial.evidence.source_version_id,
    )
    assert evidence.batch_receipt_identity == initial.evidence.batch_receipt.capsule_identity
    assert evidence.initial_candidate_version_id == initial.version_id
    assert evidence.response_patch is not None and evidence.derived_feedback is not None
    assert [entry.response for entry in evidence.response_patch.entries] == [
        "Use the conventional spelling."
    ]
    # The reviewed candidate stays active and the ledger is untouched until the seal.
    assert roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes() == admission_before
    assert ledger_path.read_bytes() == ledger_before
    own = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=replacement.version_id
    )
    reloaded = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=initial.version_id
    )
    assert own.evidence.capsule == reloaded.evidence.capsule
    assert own.evidence.batch_receipt == reloaded.evidence.batch_receipt
    assert own.evidence.root_version_id == root.record.version_id


def test_batch_replacement_replays_without_a_model_call_and_refuses_a_different_answer(
    tmp_path, monkeypatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    first = _request_batch_replacement(tmp_path, inventory)
    assert first.replacement is not None

    replay = _request_batch_replacement(
        tmp_path, inventory, invoker=lambda _prompt: pytest.fail("a stored replacement must not invoke")
    )
    different = roadmap_candidate_review.request_replacement(
        _SLUG,
        inventory.question.question_id,
        "A different answer.",
        repo_root=tmp_path,
        plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: pytest.fail("a mismatched answer must refuse before invoking"),
    )

    assert replay.outcome == "stored"
    assert replay.replacement == first.replacement
    assert replay.call_count == 0
    assert different.outcome == "refused"


def test_replacement_refuses_when_the_active_pointer_changes_before_storage(
    tmp_path, monkeypatch
) -> None:
    root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    released = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG).model_copy(
        update={"candidate_version_id": None, "active_candidate_version_id": None}
    )

    def release_pointer(_prompt: str) -> tuple[int, str]:
        admission_path.write_bytes(roadmap_candidate_run.render_candidate_admission(released))
        return 0, _batch_replacement_response()

    result = _request_batch_replacement(tmp_path, inventory, invoker=release_pointer)

    assert result.outcome == "refused"
    assert result.replacement is None
    assert admission_path.read_bytes() == roadmap_candidate_run.render_candidate_admission(released)
    assert not roadmap_candidate_review.replacement_binding_path(plans_dir, _SLUG, initial.version_id).exists()
    assert root.record.version_id == initial.evidence.root_version_id


def test_batch_replacement_rejects_a_response_that_names_no_admitted_item(tmp_path, monkeypatch) -> None:
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    payload = json.loads(_batch_replacement_response())
    payload["responses"] = [{"item_id": "not-admitted", "response": "x"}]

    result = _request_batch_replacement(
        tmp_path, inventory, invoker=lambda _prompt: (0, json.dumps(payload))
    )

    assert result.outcome == "response-rejected"
    assert not roadmap_candidate_review.replacement_binding_path(
        tmp_path / "plans", _SLUG, initial.version_id
    ).exists()


def test_replacement_publish_rechecks_the_pointer_after_the_pre_storage_check(
    tmp_path, monkeypatch
) -> None:
    """The pointer can move between the storage-time check and the journaled
    publish; the publish's own recheck must still refuse without writing."""
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    released = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG).model_copy(
        update={"candidate_version_id": None, "active_candidate_version_id": None}
    )
    real_publish = roadmap_candidate_review.publish_roadmap_generation

    def publish_after_the_pointer_moves(generation, **kwargs):
        admission_path.write_bytes(roadmap_candidate_run.render_candidate_admission(released))
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "publish_roadmap_generation", publish_after_the_pointer_moves)

    result = _request_batch_replacement(tmp_path, inventory)

    assert result.outcome == "refused"
    assert "pointer changed" in (result.detail or "")
    assert not roadmap_candidate_review.replacement_binding_path(plans_dir, _SLUG, initial.version_id).exists()


def _tamper(field: str, value):
    def change(payload: dict) -> None:
        payload[field] = value
    return change


def _drop_changed_rows(payload: dict) -> None:
    payload["predecessor_diff"]["changed_rows"] = []


@pytest.mark.parametrize(
    "mutate",
    (
        _tamper("root_version_id", "9" * 64),
        _tamper("batch_receipt_identity", "9" * 64),
        _tamper("initial_candidate_version_id", "9" * 64),
        _tamper("response_patch", {"entries": []}),
        _drop_changed_rows,
    ),
    ids=("root", "batch-receipt", "initial-candidate", "response-patch", "diff-disagrees-with-own-evidence"),
)
def test_a_stored_batch_replacement_that_disagrees_with_its_reviewed_candidate_is_refused_on_replay(
    tmp_path, monkeypatch, mutate
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    stored = _request_batch_replacement(tmp_path, inventory)
    assert stored.replacement is not None
    path = roadmap_candidate_review.replacement_evidence_path(
        tmp_path / "plans", _SLUG, stored.replacement.version_id
    )
    payload = json.loads(path.read_text(encoding="utf-8"))
    mutate(payload)
    path.write_bytes(roadmap_candidate_review._canonical_json_bytes(payload))

    replay = _request_batch_replacement(
        tmp_path, inventory, invoker=lambda _prompt: pytest.fail("a stored replacement must not invoke")
    )

    assert replay.outcome == "refused"
    assert replay.replacement is None


def test_a_replacement_whose_own_candidate_evidence_carries_a_different_capsule_is_refused_on_replay(
    tmp_path, monkeypatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    stored = _request_batch_replacement(tmp_path, inventory)
    assert stored.replacement is not None
    path = roadmap_candidate_run.candidate_evidence_path(
        tmp_path / "plans", _SLUG, stored.replacement.version_id
    )
    own = roadmap_candidate_run.parse_candidate_evidence(path.read_bytes())
    edited = own.model_copy(
        update={"capsule": own.capsule.model_copy(update={"brief": own.capsule.brief + " (edited)"})}
    )
    path.write_bytes(roadmap_candidate_run.render_candidate_evidence(edited))

    replay = _request_batch_replacement(
        tmp_path, inventory, invoker=lambda _prompt: pytest.fail("a stored replacement must not invoke")
    )

    assert replay.outcome == "refused"
    assert "candidate evidence does not bind its review evidence" in (replay.detail or "")


def _stored_replacement_id(tmp_path, inventory) -> str:
    stored = _request_batch_replacement(tmp_path, inventory)
    assert stored.replacement is not None, stored.detail
    return stored.replacement.version_id


def test_sealed_batch_replacement_atomically_swaps_the_pointer_and_records_supersession(
    tmp_path, monkeypatch
) -> None:
    root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    initial_bytes = {
        path.name: path.read_bytes()
        for path in version_directory_path(plans_dir, _SLUG, initial.version_id).iterdir()
    }
    captured = []
    real_publish = roadmap_candidate_review.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "publish_roadmap_generation", spy)

    sealed = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)

    assert sealed.outcome == "stored", sealed.detail
    assert sealed.seal is not None
    seal = sealed.seal
    assert (seal.root_version_id, seal.source_version_id) == (
        root.record.version_id, initial.evidence.source_version_id,
    )
    assert seal.batch_receipt_identity == initial.evidence.batch_receipt.capsule_identity
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None
    assert (admission.active_candidate_version_id, admission.candidate_version_id) == (
        replacement_id, replacement_id,
    )
    assert admission.root_version_id == root.record.version_id
    supersession = json.loads(
        roadmap_candidate_run.supersession_path(plans_dir, _SLUG, initial.version_id).read_text()
    )
    assert supersession["superseded_candidate_version_id"] == initial.version_id
    assert supersession["successor_candidate_version_id"] == replacement_id
    assert {
        path.name: path.read_bytes()
        for path in version_directory_path(plans_dir, _SLUG, initial.version_id).iterdir()
    } == initial_bytes

    (generation,) = captured
    namespace = roadmap_candidate_run.version_namespace_path(plans_dir, _SLUG).parent
    assert generation.kind == "candidate-review-seal"
    assert {member.relative_path for member in generation.members} == {
        roadmap_candidate_review.review_seal_path(plans_dir, _SLUG, seal.seal_id).relative_to(namespace).as_posix(),
        roadmap_candidate_run.supersession_path(plans_dir, _SLUG, initial.version_id).relative_to(namespace).as_posix(),
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(namespace).as_posix(),
        roadmap_feedback_ledger_path(plans_dir, _SLUG).relative_to(namespace).as_posix(),
    }


def test_sealing_rebinds_awaiting_review_proposals_to_the_replacement_and_publishes_its_derived_set(
    tmp_path, monkeypatch
) -> None:
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)

    sealed = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)

    assert sealed.outcome == "stored"
    ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG))
    (item,) = ledger.reviewer_feedback_groups[0].items
    assert item.state is ReviewerItemState.AWAITING_REVIEW
    assert item.proposal == ProposalFields(
        response="Use the conventional spelling.", candidate_version_id=replacement_id
    )
    assert item.request == "Use the customer-facing order name."
    sets = {(entry.source_version_id, entry.context_id) for entry in ledger.derived_context}
    assert sets == {(initial.version_id, "derived-one"), (replacement_id, "derived-replacement")}


def test_sealing_leaves_an_item_the_reviewer_reopened_between_replacement_and_seal_untouched(
    tmp_path, monkeypatch
) -> None:
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    roadmap_feedback_ledger_run.edit_reviewer_feedback(
        plans_dir=plans_dir, slug=_SLUG, item_id="batch-one", request="The reviewer changed their mind."
    )

    sealed = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)

    assert sealed.outcome == "stored"
    ledger = load_ledger(roadmap_feedback_ledger_path(plans_dir, _SLUG))
    (item,) = ledger.reviewer_feedback_groups[0].items
    assert item.state is ReviewerItemState.OPEN
    assert item.proposal is None
    assert item.request == "The reviewer changed their mind."
    assert {entry.source_version_id for entry in ledger.derived_context} == {
        initial.version_id, replacement_id,
    }


def _patch_item(item_id: str, *, state: ReviewerItemState, bound_to: str | None, request: str = "Ask.",
                fingerprint: str = "f" * 64) -> ReviewerFeedbackItem:
    return ReviewerFeedbackItem(
        item_id=item_id,
        target=LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ARTIFACT),
        request=request,
        state=state,
        submitted_against_version_id="a" * 64,
        target_fingerprint=fingerprint,
        proposal=None if bound_to is None else ProposalFields(response="Old.", candidate_version_id=bound_to),
    )


@pytest.mark.parametrize(
    ("item", "rebound"),
    (
        (_patch_item("i", state=ReviewerItemState.AWAITING_REVIEW, bound_to="1" * 64), True),
        (_patch_item("i", state=ReviewerItemState.AWAITING_REVIEW, bound_to="2" * 64), False),
        (_patch_item("i", state=ReviewerItemState.AWAITING_REVIEW, bound_to=None), False),
        (_patch_item("i", state=ReviewerItemState.AWAITING_REVIEW, bound_to="1" * 64, request="Edited."), False),
        (_patch_item("i", state=ReviewerItemState.AWAITING_REVIEW, bound_to="1" * 64, fingerprint="e" * 64), False),
        (_patch_item("i", state=ReviewerItemState.OPEN, bound_to=None), False),
        (_patch_item("i", state=ReviewerItemState.DEFERRED, bound_to="1" * 64), False),
        (_patch_item("i", state=ReviewerItemState.CLOSED, bound_to=None), False),
    ),
    ids=("awaiting-on-reviewed", "bound-elsewhere", "unbound", "request-edited", "target-changed",
         "open", "deferred", "closed"),
)
def test_replacement_ledger_patch_rebinds_only_an_item_still_awaiting_review_on_the_reviewed_candidate(
    item: ReviewerFeedbackItem, rebound: bool
) -> None:
    admitted = _patch_item("i", state=ReviewerItemState.OPEN, bound_to=None)
    other = _patch_item("other", state=ReviewerItemState.AWAITING_REVIEW, bound_to="1" * 64)
    ledger = RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug=_SLUG,
        ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(predecessor_version_id="a" * 64, items=(item, other)),),
        derived_context=(),
    )
    patch = roadmap_candidate.CandidateResponsePatch(
        entries=(roadmap_candidate.CandidateResponsePatchEntry(item=item_snapshot(admitted), response="New."),)
    )

    updated = roadmap_candidate_run.apply_replacement_ledger_patch(
        ledger, reviewed_candidate_version_id="1" * 64, replacement_version_id="9" * 64,
        response_patch=patch,
        derived_feedback=(roadmap_candidate.CandidateDerivedFeedback(context_id="d", content="C."),),
    )

    result = {entry.item_id: entry for entry in updated.reviewer_feedback_groups[0].items}
    assert result["i"] == (
        item.model_copy(update={"proposal": ProposalFields(response="New.", candidate_version_id="9" * 64)})
        if rebound
        else item
    )
    assert result["other"] == other
    assert [(entry.source_version_id, entry.context_id) for entry in updated.derived_context] == [("9" * 64, "d")]


def test_seal_refuses_when_the_ledger_changes_inside_the_publication_window(
    tmp_path, monkeypatch
) -> None:
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    admission_before = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes()
    real_publish = roadmap_candidate_review.publish_roadmap_generation

    def publish_after_a_hand_edit(generation, **kwargs):
        ledger_path.write_bytes(ledger_path.read_bytes() + b"# edited by hand\n")
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "publish_roadmap_generation", publish_after_a_hand_edit)

    sealed = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)

    assert sealed.outcome == "refused"
    assert "ledger changed" in (sealed.detail or "")
    assert ledger_path.read_bytes().endswith(b"# edited by hand\n")
    assert roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).read_bytes() == admission_before
    assert not roadmap_candidate_run.supersession_path(plans_dir, _SLUG, initial.version_id).exists()


def test_a_sealed_active_replacement_is_loadable_by_the_next_batch_and_by_rejection(
    tmp_path, monkeypatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    assert roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir).outcome == "stored"

    next_batch = _run_batch(
        tmp_path,
        {"operations": [], "responses": [],
         "derived_feedback": [{"context_id": "derived-next", "content": "Next pass."}]},
    )
    assert next_batch.outcome == "stored", next_batch.detail
    assert next_batch.candidate is not None
    assert next_batch.candidate.record.predecessor_version_id == replacement_id
    assert roadmap_candidate_run.supersession_path(plans_dir, _SLUG, replacement_id).is_file()

    released = roadmap_candidate_review.reject_candidate_review(
        _SLUG, next_batch.candidate.version_id, plans_dir=plans_dir
    )
    assert released.outcome == "stored", released.detail


def test_a_release_the_lifecycle_builder_refuses_is_reported_as_refused_and_writes_nothing(
    tmp_path, monkeypatch
) -> None:
    _root, initial, _inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    pointer = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    before = pointer.read_bytes()

    def refuse(**_kwargs):
        raise roadmap_candidate_run.CandidateProposalError(
            "terminal resolution does not name the candidate being released"
        )

    monkeypatch.setattr(roadmap_candidate_run, "build_terminal_resolution_generation", refuse)

    result = roadmap_candidate_review.reject_candidate_review(_SLUG, initial.version_id, plans_dir=plans_dir)

    assert result.outcome == "refused"
    assert "does not name the candidate being released" in (result.detail or "")
    assert pointer.read_bytes() == before


def test_review_commands_for_a_sealed_candidate_refuse_once_the_replacement_is_active(
    tmp_path, monkeypatch
) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    assert roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir).outcome == "stored"

    resealed = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)
    replayed = roadmap_candidate_review.answer_candidate_question(
        _SLUG, inventory.question.question_id, _BATCH_ANSWER, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: pytest.fail("a review of an inactive candidate must refuse before invoking"),
    )

    assert resealed.outcome == "refused"
    assert replayed.outcome == "refused"



# --------------------------------------------------------------------------
# Rejection and discard, and review once the pointer has moved
# --------------------------------------------------------------------------


# INDEX.md is a derived human aid rewritten by every committing command; these
# snapshots compare version-store state, not that file (covered in its own tests).
_INDEX_NAME = "INDEX.md"


def _tree(directory) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and path.name != _INDEX_NAME
    }


_RELEASES = (
    ("reject_candidate_review", "rejected"),
    ("discard_candidate_review", "discarded"),
)


@pytest.mark.parametrize(("release", "reason"), _RELEASES, ids=("rejected", "discarded"))
def test_review_rejection_and_discard_record_the_exact_resolution_and_release_only_the_matching_pointer(
    tmp_path, monkeypatch, release: str, reason: str
) -> None:
    root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    roadmap_root = version_directory_path(plans_dir, _SLUG, first.version_id).parent.parent
    before = _tree(roadmap_root)
    captured = []
    real_publish = roadmap_candidate_review.publish_roadmap_generation

    def spy(generation, **kwargs):
        captured.append(generation)
        return real_publish(generation, **kwargs)

    monkeypatch.setattr(roadmap_candidate_review, "publish_roadmap_generation", spy)

    result = getattr(roadmap_candidate_review, release)(_SLUG, first.version_id, plans_dir=plans_dir)

    assert result.outcome == "stored", result.detail
    record = json.loads(
        roadmap_candidate_run.terminal_resolution_path(plans_dir, _SLUG, first.version_id).read_text(
            encoding="utf-8"
        )
    )
    assert record["reason"] == reason
    assert (record["root_version_id"], record["source_version_id"], record["candidate_version_id"]) == (
        root.record.version_id, first.evidence.source_version_id, first.version_id,
    )
    assert record["batch_receipt"]["capsule_identity"] == first.evidence.batch_receipt.capsule_identity
    released = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert released is not None
    assert released.root_version_id == root.record.version_id
    assert (released.active_candidate_version_id, released.candidate_version_id) == (None, None)

    # One generation carries the pointer release and its history record; nothing else moves,
    # so the ledger, the accepted head and every stored candidate byte are unchanged.
    (generation,) = captured
    namespace = version_directory_path(plans_dir, _SLUG, first.version_id).parent.parent
    assert generation.kind == "candidate-terminal-resolution"
    assert {member.relative_path for member in generation.members} == {
        roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG).relative_to(namespace).as_posix(),
        roadmap_candidate_run.terminal_resolution_path(plans_dir, _SLUG, first.version_id).relative_to(
            namespace
        ).as_posix(),
    }
    after = _tree(roadmap_root)
    changed = {name for name in before.keys() | after.keys() if before.get(name) != after.get(name)}
    assert changed == {member.relative_path for member in generation.members}


@pytest.mark.parametrize(("release", "reason"), _RELEASES, ids=("rejected", "discarded"))
@pytest.mark.parametrize("situation", ("unknown-candidate", "already-released", "superseded"))
def test_rejection_and_discard_refuse_a_candidate_that_is_not_the_active_one_without_writes(
    tmp_path, monkeypatch, release: str, reason: str, situation: str
) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    target = first.version_id
    if situation == "unknown-candidate":
        target = "9" * 64
    elif situation == "already-released":
        assert getattr(roadmap_candidate_review, release)(_SLUG, first.version_id, plans_dir=plans_dir).outcome == "stored"
    else:
        assert _run_batch(tmp_path, _SECOND_BATCH_DELTA).outcome == "stored"
    roadmap_root = version_directory_path(plans_dir, _SLUG, first.version_id).parent.parent
    before = _tree(roadmap_root)

    result = getattr(roadmap_candidate_review, release)(_SLUG, target, plans_dir=plans_dir)

    assert result.outcome == "refused"
    assert _tree(roadmap_root) == before


def test_release_refuses_when_a_terminal_record_already_exists_for_the_active_candidate(
    tmp_path, monkeypatch
) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    record = roadmap_candidate_run.terminal_resolution_path(plans_dir, _SLUG, first.version_id)
    record.parent.mkdir(parents=True, exist_ok=True)
    record.write_bytes(b"{}")
    pointer = roadmap_candidate_run.candidate_admission_path(plans_dir, _SLUG)
    pointer_before = pointer.read_bytes()

    result = roadmap_candidate_review.reject_candidate_review(_SLUG, first.version_id, plans_dir=plans_dir)

    assert result.outcome == "refused"
    assert "already exists" in (result.detail or "")
    assert pointer.read_bytes() == pointer_before
    assert record.read_bytes() == b"{}"


def test_question_generation_refuses_a_candidate_the_pointer_has_left_without_invoking(
    tmp_path, monkeypatch
) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    assert _run_batch(tmp_path, _SECOND_BATCH_DELTA).outcome == "stored"
    plans_dir = tmp_path / "plans"

    result = roadmap_candidate_review.generate_candidate_question(
        _SLUG, first.version_id, repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: pytest.fail("a candidate the pointer has left must refuse before invoking"),
    )

    assert result.outcome == "refused"
    assert not roadmap_candidate_review.question_inventory_path(plans_dir, _SLUG, first.version_id).exists()


@pytest.mark.parametrize("kind", ("full-member", "inventory"))
def test_a_batch_question_anchor_of_a_stored_receipt_kind_resolves_and_an_unknown_row_does_not(
    tmp_path, monkeypatch, kind: str
) -> None:
    _root, first = _store_first_batch_candidate(tmp_path, monkeypatch)
    receipt = first.evidence.batch_receipt
    if kind == "full-member":
        identity = receipt.full_members[0].identity
        triple = (identity.artifact_key, identity.row_type, identity.row_id)
    else:
        entry = receipt.inventory[0]
        triple = (entry.artifact_key, entry.row_type, entry.row_id)
    anchor = roadmap_candidate_review.CandidateQuestionAnchor(
        kind=kind, artifact_key=triple[0], row_type=triple[1], row_id=triple[2]
    )

    assert roadmap_candidate_review._anchor_resolves(anchor, candidate=first)
    assert not roadmap_candidate_review._anchor_resolves(
        anchor.model_copy(update={"row_id": "no-such-row"}), candidate=first
    )


def test_a_batch_diff_row_anchor_resolves_only_for_a_row_the_candidate_changed(tmp_path, monkeypatch) -> None:
    _root, _initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement = _request_batch_replacement(tmp_path, inventory).replacement
    assert replacement is not None
    stored = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug=_SLUG, candidate_version_id=replacement.version_id
    )
    changed = roadmap_candidate_review.CandidateQuestionAnchor(
        kind="diff-row", artifact_key="domain", row_type="entities", row_id="entity-order"
    )

    assert roadmap_candidate_review._anchor_resolves(changed, candidate=stored)
    assert not roadmap_candidate_review._anchor_resolves(
        changed.model_copy(update={"row_id": "entity-customer"}), candidate=stored
    )


# --------------------------------------------------------------------------
# Whole-stack view: hops, cumulative diff, and the digest a confirm can bind to
# --------------------------------------------------------------------------

_STRUCTURAL = roadmap_candidate.CandidateOperationClassification.STRUCTURAL


def _order_row(*, name: str = "Order", field_name: str = "customer") -> dict:
    """A replacement for the root's `entity-order`: a new field name is structural, a new name is not."""
    return {
        "id": "entity-order", "name": name,
        "fields": [{"name": field_name, "type": "reference", "entity_id": "entity-customer"}],
    }


def _customer_row(name: str) -> dict:
    return {"id": "entity-customer", "name": name, "fields": []}


def _file_feedback_on_row(tmp_path, source, item_id: str, row_id: str) -> None:
    """Add an open reviewer item on `row_id`, submitted against a stored candidate."""
    plans_dir = tmp_path / "plans"
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger = load_ledger(ledger_path)
    resolved = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir, slug=_SLUG, version_id=source.version_id
    )
    filed = ReviewerFeedbackGroup(
        predecessor_version_id=source.version_id, items=(_batch_item(resolved, item_id, row_id),)
    )
    ledger_path.write_bytes(
        render_ledger(
            ledger.model_copy(update={"reviewer_feedback_groups": (*ledger.reviewer_feedback_groups, filed)})
        )
    )


def _store_stack_hop(tmp_path, *, source, row: dict):
    """Store one batch candidate replacing `row`, over `source` (None: over the enrolled root), by the runner alone."""
    if source is None:
        assert row["id"] == "entity-order", "the seeded reviewer item targets entity-order"
        item_id = "batch-one"
    else:
        item_id = f"filed-against-{source.version_id[:8]}"
        _file_feedback_on_row(tmp_path, source, item_id, row["id"])
    delta = {
        "operations": [{
            "op": "replace-row", "feedback_id": item_id, "artifact_key": "domain",
            "row_type": "entities", "row_id": row["id"], "row": row,
        }],
        "responses": [{"item_id": item_id, "response": "Changed."}],
        "derived_feedback": [],
    }
    stored = _run_batch(tmp_path, delta)
    assert stored.outcome == "stored", stored.detail
    assert stored.candidate is not None
    return stored.candidate


def _store_row_changing_stack(tmp_path, monkeypatch: pytest.MonkeyPatch, rows):
    """root -> one batch candidate per entry of `rows`, oldest first, each replacing its row.

    `_store_stack`'s hops change no rows, so its diffs are empty; here
    every hop has its own diff, which is what lets a cumulative diff differ from the top hop's.
    """
    root, _resolved = _seed_batch_ledger(tmp_path, monkeypatch)
    hops: list = []
    for row in rows:
        hops.append(
            _store_stack_hop(tmp_path, source=hops[-1] if hops else None, row=row)
        )
    return root, tuple(hops)


def _structural_then_presentation_stack(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """C1 renames a field (structural); C2, the top, renames another entity (presentation-only)."""
    root, (structural, top) = _store_row_changing_stack(
        tmp_path, monkeypatch, (_order_row(field_name="buyer"), _customer_row("Shopper"))
    )
    assert structural.evidence.operation_classification is _STRUCTURAL
    assert top.evidence.operation_classification is _PRESENTATION_ONLY
    return root, structural, top


def _stack_view(tmp_path, tip):
    return roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=tmp_path / "plans", slug=_SLUG, candidate=tip
    )


def _stored_artifacts(plans_dir, version_id: str):
    resolved = roadmap_candidate_run._load_resolved_version(
        plans_dir=plans_dir, slug=_SLUG, version_id=version_id
    )
    artifacts = {
        stage.artifact_key: stage.parse(data.decode("utf-8"))
        for stage, data in zip(STAGES, resolved.artifact_bytes, strict=True)
    }
    return artifacts, resolved.artifact_bytes


def test_stack_view_lists_hops_oldest_first_above_the_recorded_root_and_ends_at_the_tip(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)

    view = _stack_view(tmp_path, top)

    assert tuple(hop.version_id for hop in view.hops) == (structural.version_id, top.version_id)
    assert root.record.version_id not in {hop.version_id for hop in view.hops}
    assert view.root_version_id == root.record.version_id == top.evidence.root_version_id


def test_stack_view_promotion_effects_name_every_hop_and_only_the_structural_ones(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The top's own route is presentation-only, yet the structural hop below it is promoted with it
    and is what invalidates seed state. Both effects are derived from `hops`, never stored beside it."""
    _root, structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)

    view = _stack_view(tmp_path, top)

    assert view.promoted_version_ids == (structural.version_id, top.version_id)
    assert view.structural_version_ids == (structural.version_id,)
    without_the_lower_hop = replace(view, hops=view.hops[1:])
    assert without_the_lower_hop.promoted_version_ids == (top.version_id,)
    assert without_the_lower_hop.structural_version_ids == ()


def test_cumulative_diff_is_the_root_to_tip_diff_recomputed_from_stored_bytes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    root_artifacts, root_bytes = _stored_artifacts(plans_dir, root.record.version_id)
    tip_artifacts, tip_bytes = _stored_artifacts(plans_dir, top.version_id)

    view = _stack_view(tmp_path, top)

    assert view.cumulative_diff == build_roadmap_diff(
        predecessor_artifacts=root_artifacts, candidate_artifacts=tip_artifacts,
        predecessor_bytes=root_bytes, candidate_artifacts_bytes=tip_bytes, stages=STAGES,
    )
    assert view.cumulative_diff != top.evidence.predecessor_diff
    assert {row.row_id for row in view.cumulative_diff.changed_rows} == {"entity-order", "entity-customer"}
    assert {row.row_id for row in top.evidence.predecessor_diff.changed_rows} == {"entity-customer"}


def test_cumulative_diff_collapses_two_hops_editing_the_same_row_into_one_change(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Root-to-tip, not the hops' own diffs concatenated: the row shows the root's value before and
    the tip's value after, with the intermediate value in neither."""
    _root, (first, second) = _store_row_changing_stack(
        tmp_path, monkeypatch, (_order_row(name="Order A"), _order_row(name="Order B"))
    )

    view = _stack_view(tmp_path, second)

    (row,) = view.cumulative_diff.changed_rows
    assert (row.row_id, row.before.name, row.after.name) == ("entity-order", "Order", "Order B")
    assert first.evidence.predecessor_diff.changed_rows[0].after.name == "Order A"
    assert second.evidence.predecessor_diff.changed_rows[0].before.name == "Order A"


def test_single_hop_cumulative_diff_equals_the_hops_own_diff(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, (only,) = _store_row_changing_stack(
        tmp_path, monkeypatch, (_order_row(field_name="buyer"),)
    )

    view = _stack_view(tmp_path, only)

    assert len(view.hops) == 1
    assert view.cumulative_diff == only.evidence.predecessor_diff


def test_stack_view_carves_out_route_less_hops_and_never_judges_eligibility(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberate carve-out: the builder describes a stack and does not decide whether it may be
    approved. An all-presentation stack and a stack with a route-less legacy hop both yield a view;
    the guards, not the builder, own eligibility."""
    _root, (lower, top) = _store_row_changing_stack(
        tmp_path, monkeypatch, (_order_row(name="Order A"), _customer_row("Shopper"))
    )

    all_presentation = _stack_view(tmp_path, top)
    assert all_presentation.structural_version_ids == ()

    _edit_stored_evidence(
        tmp_path, lower,
        lambda data: data.update(operation_classification=None, normalized_operations=None),
    )
    route_less = _stack_view(tmp_path, top)

    assert route_less.hops[0].evidence.operation_classification is None
    assert route_less.hops[1].evidence.operation_classification is _PRESENTATION_ONLY
    assert route_less.promoted_version_ids == (lower.version_id, top.version_id)
    assert route_less.structural_version_ids == ()


def test_stack_view_is_rebuilt_from_stored_records_not_from_the_callers_candidate(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A stale or edited in-memory candidate must not change what a confirm's recompute binds to: only
    its id and recorded root are read."""
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    altered = replace(
        top,
        evidence=top.evidence.model_copy(update={
            "operation_classification": _STRUCTURAL,
            "normalized_operations": (),
            "predecessor_diff": top.evidence.predecessor_diff.model_copy(update={"changed_rows": ()}),
        }),
    )
    assert altered.evidence != top.evidence

    from_stored = _stack_view(tmp_path, top)
    from_altered = _stack_view(tmp_path, altered)

    assert from_altered == from_stored
    assert from_altered.digest == from_stored.digest
    assert from_altered.hops[-1].evidence.operation_classification is _PRESENTATION_ONLY


@pytest.mark.parametrize(
    ("variant", "reason"),
    (
        pytest.param("no-recorded-root", "no accepted root", id="no-recorded-root"),
        pytest.param("candidate-is-its-own-root", "underivable", id="candidate-is-its-own-root"),
        pytest.param("forged-lower-hop", "underivable", id="forged-lower-hop"),
        pytest.param("unreadable-root", "underivable", id="unreadable-root"),
        pytest.param("deleted-lower-hop", "underivable", id="deleted-lower-hop"),
    ),
)
def test_stack_view_refuses_an_underivable_stack_with_a_review_error_and_no_partial_view(
    tmp_path, monkeypatch: pytest.MonkeyPatch, variant: str, reason: str
) -> None:
    """A digest over a view missing a hop could confirm a stack the operator never saw, so every gap
    refuses, and as the review module's own error: `CandidateProposalError` must not escape."""
    root, (lower, top) = _store_row_changing_stack(
        tmp_path, monkeypatch, (_order_row(name="Order A"), _customer_row("Shopper"))
    )
    plans_dir = tmp_path / "plans"
    candidate = top
    if variant == "no-recorded-root":
        candidate = replace(top, evidence=top.evidence.model_copy(update={"root_version_id": None}))
    elif variant == "candidate-is-its-own-root":
        candidate = replace(top, evidence=top.evidence.model_copy(update={"root_version_id": top.version_id}))
    elif variant == "forged-lower-hop":
        _edit_stored_evidence(tmp_path, lower, lambda data: data.update(operation_classification="structural"))
    elif variant == "unreadable-root":
        stored_artifact_path(plans_dir, _SLUG, root.record.version_id, "domain").unlink()
    else:
        roadmap_candidate_run.candidate_evidence_path(plans_dir, _SLUG, lower.version_id).unlink()

    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match=reason):
        _stack_view(tmp_path, candidate)


@pytest.mark.parametrize("refused_endpoint", ("root", "tip"))
def test_stack_view_refuses_when_the_cumulative_diff_cannot_be_derived(
    tmp_path, monkeypatch: pytest.MonkeyPatch, refused_endpoint: str
) -> None:
    """Either endpoint of the cumulative diff failing to parse refuses the whole view. The hop
    derivation is answered from a precomputed stack so only the diff endpoints reach the patched parser."""
    root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    real_stack = roadmap_candidate_run.candidate_stack_route(
        plans_dir=tmp_path / "plans", slug=_SLUG,
        tip_version_id=top.version_id, root_version_id=root.record.version_id,
    )
    refused_id = root.record.version_id if refused_endpoint == "root" else top.version_id
    real_parse = roadmap_candidate._parse_predecessor_artifacts

    def parse(version, stages):
        if version.record.version_id == refused_id:
            return roadmap_candidate._refusal("invalid-predecessor", "predecessor stored artifacts cannot be parsed")
        return real_parse(version, stages)

    monkeypatch.setattr(roadmap_candidate_run, "candidate_stack_route", lambda **_kwargs: real_stack)
    monkeypatch.setattr(roadmap_candidate, "_parse_predecessor_artifacts", parse)

    with pytest.raises(roadmap_candidate_review.CandidateReviewError, match="cumulative diff is underivable"):
        _stack_view(tmp_path, top)


def test_stack_view_is_read_only_and_never_reads_the_head_or_the_admission_pointer(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """It must give the same answer inside or outside a writer guard, before or after promotion."""
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    def refuse(*_args, **_kwargs):
        pytest.fail("building the stack view read the head or the admission pointer, or took a writer guard")

    monkeypatch.setattr(roadmap_candidate_run, "load_accepted_version", refuse)
    monkeypatch.setattr(roadmap_candidate_run, "load_candidate_admission", refuse)
    monkeypatch.setattr(roadmap_candidate_review, "load_accepted_version", refuse)
    monkeypatch.setattr(roadmap_candidate_review, "roadmap_writer_guard", refuse)

    _stack_view(tmp_path, top)

    assert _tree(plans_dir) == before


def test_stack_view_digest_is_stable_across_rebuilds(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)

    first = _stack_view(tmp_path, top).digest
    second = _stack_view(tmp_path, top).digest

    assert first == second
    assert len(first) == 64 and int(first, 16) >= 0


def _prose_amended_add_row(fragment: str) -> roadmap_candidate.CandidateAddRow:
    return roadmap_candidate.CandidateAddRow(
        feedback_id="feedback-amended",
        artifact_key="domain",
        row_type="entities",
        row=EntityRow(id="entity-amended", name="Amended", fields=()),
        prose_amendment=roadmap_candidate.CandidateAddRowProseAmendment(
            row_id="entity-amended", fragment=fragment
        ),
    )


def test_candidate_prose_amendment_diff_lists_artifact_row_and_exact_fragment_in_normalized_order() -> None:
    first = _prose_amended_add_row("### entity-amended\nFirst fragment.")
    second = roadmap_candidate.CandidateAddRow(
        feedback_id="feedback-second",
        artifact_key="components",
        row_type="components",
        row=ComponentRow(
            id="component-second", name="Second", entity_ids=(), pattern_ids=()
        ),
        prose_amendment=roadmap_candidate.CandidateAddRowProseAmendment(
            row_id="component-second", fragment="### component-second\nSecond fragment."
        ),
    )

    records = roadmap_candidate.candidate_prose_amendment_diffs((first, second))

    assert [(record.artifact_key, record.row_id, record.fragment) for record in records] == [
        ("domain", "entity-amended", "### entity-amended\nFirst fragment."),
        ("components", "component-second", "### component-second\nSecond fragment."),
    ]


def test_candidate_prose_amendment_diff_ignores_operations_without_an_admitted_add_row_amendment() -> None:
    replace_row = roadmap_candidate.CandidateReplaceRow(
        feedback_id="feedback-replace",
        artifact_key="domain",
        row_type="entities",
        row_id="entity-existing",
        row=EntityRow(id="entity-existing", name="Existing", fields=()),
    )
    remove_row = roadmap_candidate.CandidateRemoveRow(
        feedback_id="feedback-remove",
        artifact_key="domain",
        row_type="entities",
        row_id="entity-removed",
    )

    assert roadmap_candidate.candidate_prose_amendment_diffs((replace_row, remove_row, "legacy-operation")) == ()


def _with_hop_evidence(view, index: int, **update):
    hop = view.hops[index]
    changed = replace(hop, evidence=hop.evidence.model_copy(update=update))
    return replace(view, hops=(*view.hops[:index], changed, *view.hops[index + 1:]))


def _with_hop_receipt(view, index: int, **update):
    receipt = view.hops[index].evidence.batch_receipt
    return _with_hop_evidence(view, index, batch_receipt=receipt.model_copy(update=update))


def _with_hop_version_id(view, index: int):
    hop = view.hops[index]
    changed = replace(hop, record=hop.record.model_copy(update={"version_id": "e" * 64}))
    return replace(view, hops=(*view.hops[:index], changed, *view.hops[index + 1:]))


def _without_rows(diff):
    return diff.model_copy(update={"changed_rows": ()})


_DIGEST_VARIANTS = {
    "root-id": lambda view: replace(view, root_version_id="f" * 64),
    "cumulative-diff": lambda view: replace(view, cumulative_diff=_without_rows(view.cumulative_diff)),
    "hop-order": lambda view: replace(view, hops=tuple(reversed(view.hops))),
    "dropped-lower-hop": lambda view: replace(view, hops=view.hops[1:]),
    **{
        f"hop-{index}-{fact}": (lambda view, index=index, make=make: make(view, index))
        for index in (0, 1)
        for fact, make in {
            "version-id": _with_hop_version_id,
            "route": lambda view, index: _with_hop_evidence(view, index, operation_classification=None),
            "receipt-identity": lambda view, index: _with_hop_receipt(view, index, capsule_identity="d" * 64),
            "selected-feedback": lambda view, index: _with_hop_receipt(view, index, reviewer_items=()),
            "typed-operations": lambda view, index: _with_hop_evidence(view, index, normalized_operations=()),
            "own-diff": lambda view, index: _with_hop_evidence(
                view, index, predecessor_diff=_without_rows(view.hops[index].evidence.predecessor_diff)
            ),
        }.items()
    },
}


def test_stack_view_digest_changes_when_an_amended_operations_fragment_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    view = _stack_view(tmp_path, top)
    initial = _prose_amended_add_row("### entity-amended\nFirst fragment.")
    changed = _prose_amended_add_row("### entity-amended\nChanged fragment.")
    amended_view = _with_hop_evidence(view, 0, normalized_operations=(initial,))
    changed_view = _with_hop_evidence(view, 0, normalized_operations=(changed,))

    assert amended_view.digest != changed_view.digest


def test_stack_view_rebuilds_amendment_disclosure_from_stored_operations(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    altered = replace(
        top,
        evidence=top.evidence.model_copy(update={
            "normalized_operations": (_prose_amended_add_row("### entity-amended\nAltered."),),
        }),
    )

    stored_view = _stack_view(tmp_path, top)
    rebuilt_view = _stack_view(tmp_path, altered)

    assert rebuilt_view == stored_view
    assert roadmap_candidate.candidate_prose_amendment_diffs(
        rebuilt_view.hops[-1].evidence.normalized_operations
    ) == ()


@pytest.mark.parametrize("variant", tuple(_DIGEST_VARIANTS))
def test_stack_view_digest_changes_when_any_covered_fact_changes(
    tmp_path, monkeypatch: pytest.MonkeyPatch, variant: str
) -> None:
    """Each covered fact is checked on the lower hop as well as the top: a digest of the top hop alone
    would confirm a stack whose lower hop changed after the operator read it."""
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    view = _stack_view(tmp_path, top)
    changed = _DIGEST_VARIANTS[variant](view)
    assert changed != view, "the variant must actually change the view"

    assert changed.digest != view.digest


def test_stack_view_digest_distinguishes_a_route_less_hop_from_a_presentation_only_one(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the route differs between the two views: no stored route is a different fact from a
    stored presentation-only route, and the digest must not fold one into the other."""
    _root, _structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    presentation_only = _stack_view(tmp_path, top)
    assert presentation_only.hops[-1].evidence.operation_classification is _PRESENTATION_ONLY

    route_less = _with_hop_evidence(presentation_only, 1, operation_classification=None)

    assert route_less.digest != presentation_only.digest


def test_storing_a_descendant_changes_the_new_tops_digest_and_leaves_an_ancestors_digest_alone(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The digest is stateless: a candidate's view depends on its own stack only, so an ancestor's
    digest survives a descendant being stored while the descendant's covers one more hop."""
    _root, structural, top = _structural_then_presentation_stack(tmp_path, monkeypatch)
    ancestor_digest = _stack_view(tmp_path, top).digest

    descendant = _store_stack_hop(
        tmp_path, source=top, row={"id": "entity-compact", "name": "Tiny", "fields": []},
    )
    descendant_view = _stack_view(tmp_path, descendant)

    assert tuple(hop.version_id for hop in descendant_view.hops) == (
        structural.version_id, top.version_id, descendant.version_id
    )
    assert descendant_view.digest != ancestor_digest
    assert _stack_view(tmp_path, top).digest == ancestor_digest


def test_stack_view_module_does_not_import_the_cli_layer() -> None:
    """The digest must never depend on the printout, and a library module that could import the CLI's
    rendering helpers could hash printed text. The boundary is checked on the import statements."""
    tree = ast.parse(Path(roadmap_candidate_review.__file__).read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            imported.append(module)
            imported.extend(f"{module}.{alias.name}" for alias in node.names)

    assert not [name for name in imported if name == "plan_tool.cli" or name.startswith("plan_tool.cli.")]


# --------------------------------------------------------------------------
# correct-prose: stack digest coverage and the edit route
# --------------------------------------------------------------------------

from types import SimpleNamespace  # noqa: E402

from plan_tool.roadmap_candidate_context import CandidateContextSourceSpan  # noqa: E402
from plan_tool.roadmap_diff import RoadmapDiff  # noqa: E402
from tests.test_roadmap_candidate_run import (  # noqa: E402
    _correction_delta,
    _store_correction_candidate,
)


def _correction_stack_view(*, before: str, after: str, with_correction: bool = True):
    span = CandidateContextSourceSpan(
        row_id="entity-order", span_id="span-order", text=before,
        digest=hashlib.sha256(before.encode()).hexdigest(),
    )
    capsule = SimpleNamespace(
        full_members=(SimpleNamespace(
            identity=SimpleNamespace(artifact_key="domain", row_id="entity-order"), source_spans=(span,)
        ),)
    )
    operations = (
        (roadmap_candidate.CandidateCorrectProse(
            feedback_id="batch-one", artifact_key="domain", span_id="span-order", replacement=after
        ),)
        if with_correction else ()
    )
    diff = RoadmapDiff(changed_artifacts=(), changed_rows=(), added_relations=(), removed_relations=())
    hop = SimpleNamespace(
        version_id="hop-1",
        evidence=SimpleNamespace(
            operation_classification=roadmap_candidate.CandidateOperationClassification.STRUCTURAL,
            batch_receipt=None, normalized_operations=operations, predecessor_diff=diff, capsule=capsule,
        ),
    )
    return roadmap_candidate_review.CandidateStackView(
        root_version_id="root-id", hops=(hop,), cumulative_diff=diff
    )


def test_stack_digest_moves_when_only_a_correction_after_text_moves() -> None:
    """A correction changes no typed row, so only its own text can move the digest."""
    one = _correction_stack_view(before="old\n", after="new one\n")
    two = _correction_stack_view(before="old\n", after="new two\n")

    assert one.digest != two.digest


def test_stack_digest_moves_when_only_a_correction_before_text_moves() -> None:
    """The stored before text is covered, so approval of one paragraph cannot confirm another."""
    one = _correction_stack_view(before="old one\n", after="new\n")
    two = _correction_stack_view(before="old two\n", after="new\n")

    assert one.digest != two.digest


def test_digest_is_unchanged_for_a_stack_with_no_corrections() -> None:
    """The ``corrections`` key is omitted, not emptied, so stored approvals of older stacks stay valid."""
    view = _correction_stack_view(before="old\n", after="new\n", with_correction=False)

    identity_input = roadmap_candidate_review._stack_view_identity_input(view)

    assert all("corrections" not in hop for hop in identity_input["hops"])  # type: ignore[union-attr]


def _edit_with_correction_delta(tmp_path, candidate, delta: dict):
    return roadmap_candidate_review.decide_structural_candidate(
        _SLUG, candidate.version_id, "edit", correction="Reword the order paragraph.",
        repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, json.dumps(delta)),
    )


def _replacement_correction_delta(candidate) -> dict:
    # Reuse the stored operation's span id: once a candidate exists, a fresh context build offers no capsule.
    stored = candidate.evidence.normalized_operations[0]
    delta = _correction_delta_for_span(stored.span_id)
    delta["operations"][0]["replacement"] = "entity-order is the reworded order.\n"
    return delta


def _correction_delta_for_span(span_id: str) -> dict:
    return {
        "operations": [
            {
                "op": "correct-prose", "feedback_id": "batch-one", "artifact_key": "domain",
                "span_id": span_id, "replacement": "",
            }
        ],
        "responses": [{"item_id": "batch-one", "response": "Done."}],
        "derived_feedback": [],
    }


def test_structural_edit_keeps_the_correction_operation_in_the_replacement(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    candidate = _store_correction_candidate(tmp_path, monkeypatch)

    edited = _edit_with_correction_delta(tmp_path, candidate, _replacement_correction_delta(candidate))

    assert edited.outcome == "stored", edited.detail
    assert edited.active_candidate is not None
    assert [type(op) for op in edited.active_candidate.evidence.normalized_operations] == [
        roadmap_candidate.CandidateCorrectProse
    ]
    assert edited.active_candidate.evidence.normalized_operations[0].replacement == (
        "entity-order is the reworded order.\n"
    )


def test_edit_replacement_requires_a_fresh_approval_and_refuses_the_prior_digest(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Approval of the original text never confirms the edited text: the replacement has its own digest."""
    candidate = _store_correction_candidate(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    original_digest = _confirming_digest(plans_dir, candidate)
    edited = _edit_with_correction_delta(tmp_path, candidate, _replacement_correction_delta(candidate))
    assert edited.active_candidate is not None
    replacement = edited.active_candidate
    replacement_digest = _confirming_digest(plans_dir, replacement)
    assert replacement_digest != original_digest

    refused = _approve_with(plans_dir, replacement, original_digest)

    assert refused.outcome == "refused"
    assert refused.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    approved = _approve_with(plans_dir, replacement, replacement_digest)
    assert approved.outcome == "stored", approved.detail
    assert approved.seal is not None


# --------------------------------------------------------------------------
# The Integration Decisions paragraph, end to end
# --------------------------------------------------------------------------

import tests.test_roadmap_candidate_run as candidate_run_tests  # noqa: E402
from plan_tool.cli import roadmap_cmd  # noqa: E402
from plan_tool import roadmap_version_promotion  # noqa: E402
from plan_tool.roadmap_version_promotion import promote_review_seal  # noqa: E402
from plan_tool.roadmap_versions import load_accepted_version  # noqa: E402

_INTEGRATION_DECISIONS_FIXTURE = Path(__file__).parent / "fixtures" / "roadmap" / "integration-decisions-paragraph.md"
_INTEGRATION_DECISIONS_FIXTURE_BYTES = 1288
_INTEGRATION_DECISION_IDS = (
    "decision-config-vs-run-split",
    "decision-engine-session-scope",
    "decision-gate-representation",
    "decision-runtime-granularity",
    "decision-isolation-boundary",
)
_GROUP_FOUR_PREDECESSOR = "4" * 64
# Held before the test patches the module attribute, so the Integration root can borrow the other three artifacts.
_STOREFRONT_ROOT = candidate_run_tests._resolved_root


def _integration_decisions_paragraph() -> str:
    return _INTEGRATION_DECISIONS_FIXTURE.read_bytes().decode("utf-8")


def _integration_corrected_paragraph(paragraph: str) -> str:
    """Drop the removed row's sentence and settle the pending one, leaving every other sentence as is."""
    removed = paragraph.index("`decision-exclude-repo-browsing`")
    pending = paragraph.index("`decision-runtime-granularity`")
    isolation = paragraph.index("`decision-isolation-boundary`")
    assert removed < pending < isolation
    settled = (
        "`decision-runtime-granularity` is settled: plan-tool roadmap and plan-tool are separate "
        "runtimes for handoff-checking purposes. "
    )
    return paragraph[:removed] + settled + paragraph[isolation:]


def _integration_decisions_root(paragraph: str):
    """A root whose Domain body is the Integration paragraph: five live decisions, and one id that is no row at all.

    The root carries no removal record because a candidate is assembled feedback-free, which strips
    review rows from its frontmatter; the byte comparison below is about the paragraph alone."""
    base = _STOREFRONT_ROOT()
    domain = DomainArtifact(
        entities=(EntityRow("entity-order", "Order", ()),),
        business_rules=(),
        workflows=(),
        decisions=tuple(
            DecisionRow(row_id, "chosen", (), "Recorded.", "entity-order", DecisionStatus.SETTLED)
            for row_id in _INTEGRATION_DECISION_IDS
        ),
        body=paragraph,
        feedback=(),
    )
    artifact_bytes = (STAGES[0].render(domain).encode("utf-8"), *base.content.artifact_bytes[1:])
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=_SLUG,
            brief_digest=base.record.brief_digest,
            artifact_digests=tuple(hashlib.sha256(value).hexdigest() for value in artifact_bytes),
        ),
        content=RoadmapVersionContent(
            brief_bytes=base.content.brief_bytes, artifact_bytes=artifact_bytes
        ),
    )


def test_integration_decisions_fixture_is_the_recorded_size() -> None:
    """A silent edit to the checked-in paragraph fails here instead of changing what the proof proves."""
    assert len(_INTEGRATION_DECISIONS_FIXTURE.read_bytes()) == _INTEGRATION_DECISIONS_FIXTURE_BYTES


def test_integration_decisions_paragraph_correction_end_to_end_leaves_group_four_untouched(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paragraph = _integration_decisions_paragraph()
    corrected = _integration_corrected_paragraph(paragraph)
    monkeypatch.setattr(
        candidate_run_tests, "_resolved_root", lambda _body="": _integration_decisions_root(paragraph)
    )
    candidate_run_tests._enroll(tmp_path)
    plans_dir = tmp_path / "plans"
    root = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert root is not None
    # Group 4's accepted feedback: a closed item bound to an earlier version, which must not move.
    group_four_item = _batch_item(root, "group-four-one", "decision-config-vs-run-split").model_copy(
        update={
            "state": ReviewerItemState.CLOSED,
            "submitted_against_version_id": _GROUP_FOUR_PREDECESSOR,
        }
    )
    group_four = ReviewerFeedbackGroup(
        predecessor_version_id=_GROUP_FOUR_PREDECESSOR, items=(group_four_item,)
    )
    open_item = _batch_item(root, "batch-one", "decision-runtime-granularity")
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger_path.write_bytes(
        render_ledger(
            RoadmapFeedbackLedger(
                schema_version=1,
                roadmap_slug=_SLUG,
                ledger_state=LedgerState.LEDGER_NATIVE,
                reviewer_feedback_groups=(
                    group_four,
                    ReviewerFeedbackGroup(
                        predecessor_version_id=root.record.version_id, items=(open_item,)
                    ),
                ),
                derived_context=(),
            )
        )
    )
    monkeypatch.setattr(
        roadmap_candidate, "check_complete_roadmap_gates", candidate_run_tests._green_gates
    )

    # The shared span is issued only because every live row the paragraph names is in the context.
    capsule = build_candidate_context(root, None, load_ledger(ledger_path)).capsule
    assert capsule is not None
    (span,) = {
        span.span_id: span
        for member in capsule.full_members
        for span in member.source_spans
        if paragraph in span.text
    }.values()
    assert span.owning_row_ids == tuple(sorted(_INTEGRATION_DECISION_IDS))

    stored = _run_batch(
        tmp_path,
        {
            "operations": [
                {
                    "op": "correct-prose", "feedback_id": "batch-one", "artifact_key": "domain",
                    "span_id": span.span_id, "replacement": corrected,
                }
            ],
            "responses": [{"item_id": "batch-one", "response": "Done."}],
            "derived_feedback": [],
        },
    )
    assert stored.outcome == "stored", stored.detail
    candidate = stored.candidate
    assert candidate is not None

    # The candidate differs from the root only inside the issued span: frontmatter, every typed row, and
    # every other artifact are the root's own bytes.
    root_domain = root.artifact_bytes[0]
    assert root_domain.count(paragraph.encode("utf-8")) == 1
    assert candidate.content.artifact_bytes[0] == root_domain.replace(
        paragraph.encode("utf-8"), corrected.encode("utf-8")
    )
    assert candidate.content.artifact_bytes[1:] == root.artifact_bytes[1:]

    # The reviewer sees the exact stored before and after text of the one correction.
    view = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug=_SLUG, candidate=candidate
    )
    (diff,) = roadmap_candidate.candidate_prose_correction_diffs(
        candidate.evidence.normalized_operations, candidate.evidence.capsule
    )
    assert (diff.before, diff.after) == (paragraph, corrected)
    roadmap_cmd._render_structural_candidate_stack(view)
    printed = capsys.readouterr().out.splitlines()
    assert "  correction before text: " + roadmap_cmd._render_stored_value(paragraph) in printed
    assert "  correction after text: " + roadmap_cmd._render_stored_value(corrected) in printed

    # Approval without the confirming digest seals nothing; with it, the seal promotes the candidate.
    tree_before = _tree(plans_dir)
    refused = _approve_with(plans_dir, candidate, None)
    assert refused.outcome == "refused"
    assert refused.seal is None
    assert _tree(plans_dir) == tree_before
    approved = _approve_with(plans_dir, candidate, view.digest)
    assert approved.outcome == "stored", approved.detail
    assert approved.seal is not None
    # The toy decision rows are not gate-clean; the promotion-time gate walk has its own tests.
    monkeypatch.setattr(
        roadmap_version_promotion, "check_complete_roadmap_gates", candidate_run_tests._green_gates
    )
    with roadmap_writer_guard(plans_dir, _SLUG) as writer_token:
        promoted = promote_review_seal(
            plans_dir=plans_dir, slug=_SLUG, seal_id=approved.seal.seal_id, writer_token=writer_token
        )
    assert promoted.version_id == candidate.version_id
    head = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    assert head is not None and head.record.version_id == candidate.version_id
    assert head.artifact_bytes[0].replace(
        corrected.encode("utf-8"), paragraph.encode("utf-8")
    ) == root_domain
    assert head.artifact_bytes[1:] == root.artifact_bytes[1:]

    # Group 4 is exactly as it was: same group, same item, same snapshot.
    group_four_after = next(
        group
        for group in load_ledger(ledger_path).reviewer_feedback_groups
        if group.predecessor_version_id == _GROUP_FOUR_PREDECESSOR
    )
    assert group_four_after == group_four
    assert [item_snapshot(item) for item in group_four_after.items] == [
        item_snapshot(group_four_item)
    ]


# --- narrative review evidence at approval -----------------------------------------------------

_BLOCKING_KIND = "removed-id-in-live-prose"
_AMBIGUOUS_KIND = "removed-id-ambiguous-reference"


def _narrative_finding(kind: str, artifact: str, row_id: str):
    return roadmap_candidate_narrative.NarrativeFinding(
        kind=kind, artifact=artifact, row_id=row_id, start=0, end=1, line=1, excerpt=row_id,
        correction_path=(
            ("use the correction exit", "use the historical marker")
            if kind == _BLOCKING_KIND
            else ("none",)
        ),
        message=f"{artifact} {row_id}",
    )


def _stub_narrative_evidence(monkeypatch: pytest.MonkeyPatch, *, blocking=(), items=()) -> list:
    """Replace the adapter with fixed evidence; returns the calls it received."""
    seen: list = []

    def fake(members, predecessor, *, feedback_free=False):
        seen.append(feedback_free)
        return roadmap_candidate_narrative.CandidateNarrativeEvidence(tuple(blocking), tuple(items))

    monkeypatch.setattr(roadmap_candidate_narrative, "candidate_narrative_evidence_from_bytes", fake)
    return seen


def test_structural_approve_refuses_a_candidate_whose_live_prose_names_a_removed_row(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    seen = _stub_narrative_evidence(
        monkeypatch,
        blocking=[
            _narrative_finding(_BLOCKING_KIND, "domain", "entity-gone"),
            _narrative_finding(_BLOCKING_KIND, "plans", "step-gone"),
        ],
    )

    refused = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert refused.outcome == "refused"
    assert refused.seal is None
    assert "entity-gone" in refused.detail and "step-gone" in refused.detail
    # Each operator exit appears once even with two defects of the same class.
    assert refused.detail.count("use the correction exit") == 1
    assert refused.detail.count("use the historical marker") == 1
    assert seen == [True]  # a batch candidate is checked as feedback-free


@pytest.mark.parametrize(
    "error",
    [
        RoadmapArtifactError("domain frontmatter is malformed"),
        roadmap_candidate_run.CandidateProposalError("predecessor is gone"),
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte"),
        ValueError("zip() argument 2 is shorter than argument 1"),
    ],
    ids=["unparseable-artifact", "unloadable-predecessor", "non-utf8-member", "wrong-member-count"],
)
def test_approval_reports_a_failed_result_when_narrative_evidence_cannot_be_computed(
    tmp_path, monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    """An evidence computation error is a failed result with nothing written, never a traceback."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None

    def broken(*_args, **_kwargs):
        raise error

    monkeypatch.setattr(roadmap_candidate_narrative, "candidate_narrative_evidence_from_bytes", broken)

    failed = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert failed.outcome == "failed"
    assert failed.seal is None
    assert "narrative evidence could not be computed" in failed.detail


def test_ambiguous_reference_is_never_a_refusal(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-blocking evidence is display-only; approval still seals."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    _stub_narrative_evidence(
        monkeypatch, items=[_narrative_finding(_AMBIGUOUS_KIND, "domain", "entity-order")]
    )

    approved = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert approved.outcome == "stored"


def test_wrong_digest_still_reports_the_digest_mismatch_before_narrative_evidence(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    seen = _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )

    refused = _approve_with(tmp_path / "plans", proposed.candidate, _WELL_FORMED_DIGEST_OF_NO_STACK)

    assert refused.outcome == "refused"
    assert refused.detail == roadmap_candidate_review._APPROVAL_DIGEST_MISMATCH
    assert seen == []


def test_already_sealed_lineage_still_returns_the_stored_seal_without_a_narrative_recheck(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Deliberate: create-only seal replay is unchanged, so a stored seal is not re-checked."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    first = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)
    assert first.outcome == "stored"
    seen = _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )

    replay = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert replay.outcome == "stored"
    assert replay.seal == first.seal
    assert seen == []


def test_seal_review_refuses_a_replacement_whose_live_prose_names_a_removed_row(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    recorded = roadmap_candidate_review.record_reviewer_answer(
        _SLUG, inventory.question.question_id, "Restore the relation.", plans_dir=tmp_path / "plans"
    )
    assert recorded.answer is not None
    requested = roadmap_candidate_review.request_replacement(
        _SLUG, inventory.question.question_id, recorded.answer.answer_text,
        repo_root=tmp_path, plans_dir=tmp_path / "plans",
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )
    assert requested.replacement is not None
    _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )

    refused = roadmap_candidate_review.seal_review(
        _SLUG, requested.replacement.version_id, plans_dir=tmp_path / "plans"
    )

    assert refused.outcome == "refused"
    assert "entity-gone" in refused.detail
    seal = roadmap_candidate_review._new_seal(
        initial=initial, inventory=inventory, answer=recorded.answer, replacement=requested.replacement
    )
    assert not roadmap_candidate_review.review_seal_path(tmp_path / "plans", _SLUG, seal.seal_id).exists()


def test_refusal_names_each_blocking_defect_and_its_operator_exit(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One refusal reports every defect with its artifact and row, and states each exit once."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    _stub_narrative_evidence(
        monkeypatch,
        blocking=[
            _narrative_finding(_BLOCKING_KIND, "domain", "entity-gone"),
            _narrative_finding(_BLOCKING_KIND, "plans", "step-gone"),
        ],
    )

    refused = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)

    assert refused.outcome == "refused"
    assert "domain names removed id 'entity-gone'" in refused.detail
    assert "plans names removed id 'step-gone'" in refused.detail
    assert refused.detail.count("use the correction exit") == 1
    assert refused.detail.count("use the historical marker") == 1
    assert "line" not in refused.detail  # reads on its own: no position or line number


# Seal identity of the clean storefront candidate, recorded with the narrative check disabled, so the
# test pins "approval without removed ids is unchanged" to pre-check behavior and not to itself.
# Re-recorded the same way when batch payloads moved to schema 2 (shared-span table, 2026-10-05).
_CLEAN_STRUCTURAL_SEAL_ID = "7e9c2b7fdcd66d15536ba0cd4d84a45335337e7c68257a8f9703b4046e1d1e36"


def test_approval_without_removed_ids_is_unchanged(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The seal id was recorded when batch payloads carried the 192 KiB ceiling; the id covers the payload.
    _seed_batch_ledger(tmp_path, monkeypatch)
    # Only issuance is patched, for symmetry: a stored batch capsule is never re-rendered, so approval
    # cannot read the current ceiling. `_selector_era_review` is the guard for the recorded-ceiling rule.
    with monkeypatch.context() as issued_then:
        issued_then.setattr(roadmap_candidate_context, "CANDIDATE_CONTEXT_MAX_BYTES", PRIOR_CEILING_BYTES)
        proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None

    approved = _approve_structural_candidate(tmp_path / "plans", proposed.candidate)  # real evidence

    assert approved.outcome == "stored", approved.detail
    assert approved.seal is not None
    assert approved.seal.seal_id == _CLEAN_STRUCTURAL_SEAL_ID


def _removed_id_root(body: str):
    """The storefront root, carrying a removal record for `entity-gone` and a Domain body of `body`."""
    base = _STOREFRONT_ROOT()
    domain = DomainArtifact(
        entities=(
            EntityRow(
                "entity-order", "Order", (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),)
            ),
            EntityRow("entity-customer", "Customer", ()),
            EntityRow("entity-compact", "Compact", ()),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body=body,
        feedback=(
            FeedbackRow(
                "feedback-order",
                FeedbackTarget(FeedbackTargetKind.ROW, "entity-order"),
                "Use the customer-facing order name.",
                FeedbackState.OPEN,
            ),
        ),
        removals=(RemovalRecord("entity-gone", "Removed by an earlier review.", ("old-feedback",)),),
    )
    artifact_bytes = (STAGES[0].render(domain).encode("utf-8"), *base.content.artifact_bytes[1:])
    return PreparedRoadmapVersion(
        record=create_root_version(
            roadmap_slug=_SLUG,
            brief_digest=base.record.brief_digest,
            artifact_digests=tuple(hashlib.sha256(value).hexdigest() for value in artifact_bytes),
        ),
        content=RoadmapVersionContent(
            brief_bytes=base.content.brief_bytes, artifact_bytes=artifact_bytes
        ),
    )


@pytest.mark.parametrize(
    ("body", "defective"),
    [
        ("entity-order and entity-gone share this paragraph.\n", True),
        ("entity-order alone is described here.\n", False),
    ],
    ids=["defective", "clean"],
)
def test_a_candidate_stored_before_the_check_shipped_is_checked_the_same_way(
    tmp_path, monkeypatch: pytest.MonkeyPatch, body: str, defective: bool
) -> None:
    """No narrative record exists on disk for any candidate, so every stored one is checked from its bytes
    with no stub, version, or creation-time test: defective is refused, clean is sealed."""
    monkeypatch.setattr(candidate_run_tests, "_resolved_root", lambda _body="": _removed_id_root(body))
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None, proposed.detail
    plans_dir = tmp_path / "plans"
    assert not [path for path in plans_dir.rglob("*") if "narrative" in path.name]

    result = _approve_structural_candidate(plans_dir, proposed.candidate)

    if defective:
        assert result.outcome == "refused"
        assert result.seal is None
        assert "entity-gone" in result.detail
    else:
        assert result.outcome == "stored", result.detail
        assert result.seal is not None
    assert not [path for path in plans_dir.rglob("*") if "narrative" in path.name]


def test_batch_seal_is_refused_through_the_same_check(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The batch-receipt seal publishes through `_publish_batch_seal`; the check must precede it."""
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    replacement_id = _stored_replacement_id(tmp_path, inventory)
    assert initial.evidence.batch_receipt is not None
    seen = _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )
    before = _tree(plans_dir)

    refused = roadmap_candidate_review.seal_review(_SLUG, replacement_id, plans_dir=plans_dir)

    assert refused.outcome == "refused"
    assert "entity-gone" in refused.detail
    assert seen == [True]  # checked as a feedback-free batch candidate
    assert _tree(plans_dir) == before  # no seal and no pointer swap
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug=_SLUG)
    assert admission is not None and admission.active_candidate_version_id == initial.version_id


def test_answer_path_returns_the_seal_refusal_and_leaves_replacement_stored(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial, inventory = _review_required_question(tmp_path, monkeypatch)
    plans_dir = tmp_path / "plans"
    _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )

    refused = roadmap_candidate_review.answer_candidate_question(
        _SLUG, inventory.question.question_id, "Restore the relation.",
        repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda _prompt: (0, _eliminated_review_requirement_delta_response()),
    )

    assert refused.outcome == "refused"
    assert "entity-gone" in refused.detail
    assert refused.seal is None
    # The answer and its replacement stay stored; only the seal is missing.
    answer = roadmap_candidate_review._require_stored_answer(
        plans_dir=plans_dir, slug=_SLUG, initial=initial, inventory=inventory, answer_text=None
    )
    replacement = roadmap_candidate_review._load_replacement_if_present(
        plans_dir=plans_dir, slug=_SLUG, initial=initial, inventory=inventory, answer=answer
    )
    assert replacement is not None
    seal = roadmap_candidate_review._new_seal(
        initial=initial, inventory=inventory, answer=answer, replacement=replacement
    )
    assert not roadmap_candidate_review.review_seal_path(plans_dir, _SLUG, seal.seal_id).exists()


def test_narrative_evidence_is_not_stored_and_seal_bytes_gain_no_field(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    plans_dir = tmp_path / "plans"
    before = _tree(plans_dir)

    approved = _approve_structural_candidate(plans_dir, proposed.candidate)

    assert approved.outcome == "stored" and approved.seal is not None
    assert not [name for name in roadmap_candidate_review.CandidateReviewSeal.model_fields if "narrative" in name]
    added = {name: data for name, data in _tree(plans_dir).items() if name not in before}
    assert added, "approval wrote nothing"
    assert not [name for name in added if "narrative" in name]
    assert all(b"narrative" not in data for data in added.values())


@pytest.mark.parametrize("decision", ("reject", "edit"))
def test_reject_and_edit_routes_do_not_run_the_narrative_check(
    tmp_path, monkeypatch: pytest.MonkeyPatch, decision: str
) -> None:
    """A defective candidate can still be rejected or edited: only approval is gated."""
    _seed_batch_ledger(tmp_path, monkeypatch)
    proposed = _run_batch(tmp_path, _structural_batch_delta())
    assert proposed.candidate is not None
    seen = _stub_narrative_evidence(
        monkeypatch, blocking=[_narrative_finding(_BLOCKING_KIND, "domain", "entity-gone")]
    )
    replacement_delta = _structural_batch_delta()
    replacement_delta["operations"][0]["row"]["fields"][0]["name"] = "owner"  # type: ignore[index]

    result = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, proposed.candidate.version_id, decision, plans_dir=tmp_path / "plans",
        repo_root=tmp_path if decision == "edit" else None,
        correction="Call the field owner." if decision == "edit" else None,
        invoker=(lambda _prompt: (0, json.dumps(replacement_delta))) if decision == "edit" else None,
    )

    assert result.outcome == "stored", result.detail
    assert seen == []


def test_a_stored_candidate_whose_closure_has_decision_rows_can_be_edited_after_reload_from_disk(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The edit route rehydrates the stored capsule's rows from disk, as a later session does; every
    stored Decision row carries `source`, which the model-delta parser rejects. Approval never
    rehydrates rows, so the end-to-end test above stays green without the restore fix."""
    paragraph = _integration_decisions_paragraph()
    corrected = _integration_corrected_paragraph(paragraph)
    monkeypatch.setattr(candidate_run_tests, "_resolved_root", lambda _body="": _integration_decisions_root(paragraph))
    candidate_run_tests._enroll(tmp_path)
    plans_dir = tmp_path / "plans"
    root = load_accepted_version(plans_dir=plans_dir, slug=_SLUG)
    item = _batch_item(root, "batch-one", "decision-runtime-granularity")
    ledger_path = roadmap_feedback_ledger_path(plans_dir, _SLUG)
    ledger_path.write_bytes(render_ledger(RoadmapFeedbackLedger(
        schema_version=1, roadmap_slug=_SLUG, ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(ReviewerFeedbackGroup(predecessor_version_id=root.record.version_id, items=(item,)),),
        derived_context=())))
    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", candidate_run_tests._green_gates)
    capsule = build_candidate_context(root, None, load_ledger(ledger_path)).capsule
    (span,) = {s.span_id: s for m in capsule.full_members for s in m.source_spans if paragraph in s.text}.values()

    def delta(text):
        return {"operations": [{"op": "correct-prose", "feedback_id": "batch-one", "artifact_key": "domain",
                                "span_id": span.span_id, "replacement": text}],
                "responses": [{"item_id": "batch-one", "response": "Done."}], "derived_feedback": []}

    stored = _run_batch(tmp_path, delta(corrected))
    assert stored.outcome == "stored", stored.detail
    decisions = [m for m in capsule.full_members if m.identity.row_type == "DecisionRow"]
    assert len(decisions) == len(_INTEGRATION_DECISION_IDS)
    edited = roadmap_candidate_review.decide_structural_candidate(
        _SLUG, stored.candidate.version_id, "edit", correction="Reword the correction.",
        repo_root=tmp_path, plans_dir=plans_dir,
        invoker=lambda prompt: (0, json.dumps(delta(corrected + "\nExtra.\n"))))
    assert edited.outcome == "stored", edited.detail


def test_a_stored_candidate_whose_closure_has_decision_rows_can_request_a_replacement_after_reload(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The replacement route rehydrates the stored capsule's rows from disk, like the edit route above;
    the closure carries every settled decision, each stored with a `source` key."""
    paragraph = _integration_decisions_paragraph()
    monkeypatch.setattr(
        candidate_run_tests, "_resolved_root", lambda _body="": _integration_decisions_root(paragraph)
    )
    _root, initial, inventory = _batch_review(tmp_path, monkeypatch)
    assert {
        member.identity.row_type for member in initial.evidence.capsule.full_members
    } >= {"DecisionRow"}

    result = _request_batch_replacement(tmp_path, inventory)

    assert result.outcome != "refused", result.detail
    assert "cannot be restored" not in (result.detail or "")


def test_stack_callout_is_not_wired_into_approval_or_narrative_evidence() -> None:
    """Stack content adds no approval refusal or narrative finding: neither module knows the callout."""
    import plan_tool.roadmap_candidate_narrative as narrative
    import plan_tool.roadmap_candidate_review as review

    for module in (narrative, review):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "roadmap_stack_summary" not in source
        assert "stack_callout" not in source
