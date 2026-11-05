"""CLI tests for ``plan-tool roadmap`` — the wiring, not the orchestrator.

Nearly every case here stubs :func:`plan_tool.roadmap.run_roadmap` (as imported
into ``plan_tool.cli.roadmap_cmd``'s namespace) and asserts only what the CLI
layer owns: the argparse surface, repo-root / plans-dir resolution, the
arguments that reach the orchestrator, and the mapping from a ``RoadmapResult``
onto an exit code and a printed summary. Whether the orchestrator itself is
correct is ``tests/test_roadmap.py``'s job.

**Ten deliberate exceptions**:
:class:`TestOverwriteAdviceIsPrintedExactlyOnce` and
:class:`TestFeedbackSummaryOverTheRealOrchestrator` run the CLI over the *real*
orchestrator with a stubbed invoker. Layer-isolated tests on both sides passed
while a real invocation printed the overwrite advice twice, once per layer, on
two streams — a defect neither layer can observe alone. The feedback block is
emitted from the same place, and its count additionally has to match the rows a
real run left on disk, which no stubbed result can show.
``test_decide_candidate_reaches_a_presentation_only_top_of_a_real_structural_stack``
runs ``--decide-candidate`` over a real stored candidate stack with neither the
stack derivation nor the decision library stubbed: the CLI precheck and the
library guard each decide eligibility, and only a real stack shows they agree.
``test_stack_printout_from_a_real_stack_prints_every_hop_and_never_prints_the_digest``
prints a stack view built from real stored records: the other printout cases hand-build
their hops, and only a real view shows the printout's fields exist on what the builder
returns.
``test_unconfirmed_approve_over_a_real_stack_writes_nothing_and_its_digest_confirms_the_second_invocation``
and ``test_confirmed_approve_with_a_differing_digest_over_a_real_stack_refuses_and_changes_nothing``
run structural approve over a real stack with neither the builder nor the decision stubbed: the digest one
invocation prints is the value the next must accept, a seam no stubbed layer shows.
``test_reject_over_a_real_stack_prints_every_hop_and_the_drop_note_before_releasing_the_pointer``,
``test_proposal_output_over_a_real_stack_with_a_structural_lower_hop_prints_the_whole_stack``, and
``test_edit_over_a_real_stack_prints_the_replacements_stack_built_from_the_stored_replacement``
run the non-approve surfaces over real stored stacks: a stubbed builder answers with whatever view the
test hands it, so only a real stack shows that the hops printed are the stored ones, that a
presentation-only top over a structural hop reaches the proposal printout, and that an edit's view is
built from the replacement the library stored rather than from the candidate that was edited.
``test_operator_walk_stacks_a_batch_under_a_structural_candidate_and_reaches_the_head_only_by_confirmed_approval``
runs the operator's whole sequence over the real orchestrator with only the model replies canned: the seam
between the proposal output, the answered-route refusal, and the two approve invocations is visible only
over the real orchestrator.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import inspect
import json
import re
import subprocess
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import pytest

from roadmap_accepted_fixtures import (
    advance_accepted_head,
    publish_accepted_root,
    with_minimal_upstream,
)
import plan_tool.cli as cli
import plan_tool.cli.app as cli_app
import plan_tool.cli.roadmap_cmd as roadmap_cmd
import plan_tool.roadmap as roadmap
import plan_tool.roadmap_candidate as roadmap_candidate
import plan_tool.roadmap_candidate_review as roadmap_candidate_review
import plan_tool.roadmap_candidate_run as roadmap_candidate_run
import plan_tool.roadmap_impact_snapshot as roadmap_impact_snapshot
import plan_tool.roadmap_version_promotion as roadmap_version_promotion
import plan_tool.roadmap_versions as roadmap_versions
from plan_tool.cli.roadmap_cmd import cmd_roadmap, register
from plan_tool.create import resolve_output_dir
from plan_tool.roadmap_view import MODE_CURRENT, MODE_REVIEW
from plan_tool.roadmap import stage_resume_directory
from plan_tool.roadmap import (
    ACCEPT_OUTCOME_ACCEPTED,
    ACCEPT_OUTCOME_REFUSED,
    APPLY_OUTCOME_APPLIED,
    APPLY_OUTCOME_RECOMMENDED,
    APPLY_OUTCOME_REFUSED,
    FAILURE_AUTHORED_REVIEW_ROWS,
    FAILURE_GATES,
    FAILURE_INVOKE,
    FAILURE_PARSE,
    OUTCOME_COMPLETED,
    OUTCOME_COMPLETED_NO_CHANGE,
    OUTCOME_STAGE_EXHAUSTED,
    OUTCOME_STAGE_INVALID,
    RoadmapApplyResult,
    RoadmapEnvironmentalError,
    RoadmapError,
    RoadmapHeadExistsError,
    RoadmapPreHeadStateError,
    RoadmapResult,
    RoadmapSeedAcceptResult,
    RoadmapSeedRefreshChange,
    RoadmapSeedRefreshFailure,
    RoadmapSeedRefreshResult,
    SEED_REFRESH_OUTCOME_APPLIED,
    SEED_REFRESH_OUTCOME_EXHAUSTED,
    SEED_REFRESH_OUTCOME_PARTIAL,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_MISSING,
    DraftSeedClassification,
    NoPublishedRoadmapVersionError,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    digest_text,
    load_seed_state,
    seed_state_path,
    write_seed_state,
)
from plan_tool.roadmap_artifacts import (
    AttributeDispositionRow,
    COMPONENTS_FILENAME,
    ComponentRow,
    ComponentsArtifact,
    CONSTRAINTS_FILENAME,
    ConstraintDisposition,
    ConstraintRow,
    ConstraintsArtifact,
    DecisionRow,
    DecisionStatus,
    DOMAIN_FILENAME,
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackReopenRecord,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    FieldRow,
    FieldType,
    HostingRow,
    PatternRow,
    PlanDisposition,
    PlanRow,
    PLANS_FILENAME,
    PlansArtifact,
    AssumptionRow,
    OrderingEntry,
    QUALITY_ATTRIBUTES,
    RejectedAlternative,
    RoadmapArtifactError,
    StoreRow,
    domain_path,
    WorkflowRow,
    load_constraints_artifact,
    load_domain_artifact,
    parse_domain_artifact,
    render_components_artifact,
    render_constraints_artifact,
    render_domain_artifact,
    render_plans_artifact,
)
from plan_tool.roadmap_impact_snapshot import RoadmapGateOutcome
from plan_tool.roadmap_diff import RoadmapArtifactDiff, RoadmapDiff, RoadmapRowDiff
from plan_tool.roadmap_decision_settlement_run import DecisionSettlementRunResult
from plan_tool.roadmap_versions import (
    ROADMAP_VERSION_SCHEMA_VERSION,
    AcceptedRoadmapHead,
    PreparedRoadmapVersion,
    RoadmapVersionContent,
    accepted_head_path,
    create_root_version,
    load_accepted_version,
    render_accepted_head,
    stored_version_members,
    version_directory_path,
    version_namespace_path,
)
from plan_tool.roadmap_gates import Violation
from plan_tool.roadmap_feedback_ledger import (
    LEDGER_SCHEMA_VERSION,
    LedgerState,
    LedgerTarget,
    ReviewerFeedbackGroup,
    ReviewerFeedbackItem,
    ReviewerItemState,
    RoadmapFeedbackLedger,
    render_ledger,
    roadmap_feedback_ledger_path,
    target_fingerprint,
)
from plan_tool.roadmap_revision_publish import (
    RoadmapPublicationRecoveryError,
)

MODULE = "plan_tool.cli.roadmap_cmd"
# ``_cmd_roadmap_materialize`` no longer calls ``materialize_and_diff_one_plan``
# or constructs ``_MaterializationObserver`` directly — both now live behind
# ``plan_tool.roadmap._materialize_seed_rows``, shared with ``refresh_roadmap_seeds``.
# Patch/reference them at their real home, not ``MODULE``.
ROADMAP_MODULE = "plan_tool.roadmap"


def _init_receipt_worktree(root: Path) -> None:
    """Initialize the Git boundary used by real receipt lifecycle helpers."""
    if (root / ".git").exists():
        return
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "test@example.com"],
        ["git", "config", "user.name", "Test User"],
    ):
        subprocess.run(command, cwd=root, check=True, capture_output=True)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _roadmap_parser() -> tuple[argparse.ArgumentParser, argparse._SubParsersAction]:
    parser = argparse.ArgumentParser(prog="plan-tool")
    subparsers = parser.add_subparsers(dest="command", required=True)
    return parser, subparsers


def _parse(*argv: str) -> argparse.Namespace:
    parser, subparsers = _roadmap_parser()
    register(subparsers)
    return parser.parse_args(list(argv))


def _roadmap_help() -> str:
    _, subparsers = _roadmap_parser()
    register(subparsers)
    return subparsers.choices["roadmap"].format_help()


_BROAD_MODE_ARGUMENTS = {
    "--apply": ("--apply",),
    "--refresh-seeds": ("--refresh-seeds",),
    "--accept-seed": ("--accept-seed", "plan-a"),
    "--materialize": ("--materialize", "plan-a"),
    "--view": ("--view", "summary"),
}


def _ns(tmp_path: Path, **overrides) -> argparse.Namespace:
    """The namespace ``cmd_roadmap`` reads, defaulted for a ``tmp_path`` repo."""
    ns = argparse.Namespace(
        command="roadmap",
        plans_dir=None,
        manifest=None,
        repo_root=tmp_path,
        slug="my-roadmap",
        from_existing=tmp_path / "concept.md",
        revise_feedback=None,
        propose_candidate=None,
        submit_feedback=None,
        retarget_feedback=None,
        edit_feedback=None,
        defer_feedback=None,
        close_feedback=None,
        reopen_ledger_feedback=None,
        feedback_target=None,
        feedback_request=None,
        review_candidate=None,
        answer_question=None,
        answer=None,
        reject_candidate=None,
        discard_candidate=None,
        decide_candidate=None,
        candidate_decision=None,
        candidate_correction=None,
        confirm_stack_digest=None,
        promote_review_seal=None,
        respond_decision_settlement=None,
        decision_settlement_yes=None,
        decision_settlement_no=None,
        settle_decision=None,
        settlement_evidence=None,
        confirm_decision_settlement=None,
        apply=False,
        refresh_seeds=False,
        accept_seed=None,
        materialize=None,
        compare=None,
        comparison_base=None,
        comparison_target=None,
        comparison_output="cards",
        yes=False,
        view=None,
        mode=None,
        id=None,
        output=None,
        _settle_decision_occurrences=(),
        _settlement_evidence_occurrences=(),
        _confirm_decision_settlement_occurrences=(),
        _revise_feedback_occurrences=(),
        _propose_candidate_occurrences=(),
        _submit_feedback_occurrences=(),
        _retarget_feedback_occurrences=(),
        _edit_feedback_occurrences=(),
        _defer_feedback_occurrences=(),
        _close_feedback_occurrences=(),
        _reopen_ledger_feedback_occurrences=(),
        _feedback_target_occurrences=(),
        _feedback_request_occurrences=(),
        _review_candidate_occurrences=(),
        _answer_question_occurrences=(),
        _answer_occurrences=(),
        _reject_candidate_occurrences=(),
        _discard_candidate_occurrences=(),
        _decide_candidate_occurrences=(),
        _candidate_decision_occurrences=(),
        _candidate_correction_occurrences=(),
        _confirm_stack_digest_occurrences=(),
        _promote_review_seal_occurrences=(),
        _respond_decision_settlement_occurrences=(),
        _decision_settlement_yes_occurrences=(),
        _decision_settlement_no_occurrences=(),
        _compare_occurrences=(),
        _comparison_base_occurrences=(),
        _comparison_target_occurrences=(),
        _comparison_output_occurrences=(),
        _roadmap_mode_occurrences=(),
    )
    for key, value in overrides.items():
        setattr(ns, key, value)
    return ns


def _completed(
    *,
    artifacts: tuple[Path, ...] = (),
    stages_run: tuple[int, ...] = (),
    pending: int = 0,
    awaiting: int = 0,
    newly_settled: tuple[str, ...] = (),
    written_stages: tuple[int, ...] = (),
) -> RoadmapResult:
    return RoadmapResult(
        outcome=OUTCOME_COMPLETED,
        artifacts=artifacts,
        stages_run=stages_run,
        pending_decisions=pending,
        feedback_awaiting_review=awaiting,
        newly_settled_decisions=newly_settled,
        written_stages=written_stages,
    )


def _four_stage_completed(tmp_path: Path, **kwargs) -> RoadmapResult:
    """A completed four-stage run whose artifacts sit under ``tmp_path``."""
    root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
    return _completed(
        artifacts=(
            root / "01-domain.md",
            root / "02-constraints.md",
            root / "03-components.md",
            root / "04-roadmap.md",
        ),
        stages_run=(1, 2, 3, 4),
        **kwargs,
    )


def _three_stage_completed(tmp_path: Path, **kwargs) -> RoadmapResult:
    """A completed three-stage run whose artifacts sit under ``tmp_path``."""
    root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
    return _completed(
        artifacts=(
            root / "01-domain.md",
            root / "02-constraints.md",
            root / "03-components.md",
        ),
        stages_run=(1, 2, 3),
        **kwargs,
    )


def _two_stage_completed(tmp_path: Path, **kwargs) -> RoadmapResult:
    """A completed two-stage run whose artifacts sit under ``tmp_path``."""
    root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
    return _completed(
        artifacts=(root / "01-domain.md", root / "02-constraints.md"),
        stages_run=(1, 2),
        **kwargs,
    )


def _exhausted(**kwargs) -> RoadmapResult:
    base = dict(
        outcome=OUTCOME_STAGE_EXHAUSTED,
        artifacts=(),
        stages_run=(1,),
        pending_decisions=0,
        failed_stage=1,
    )
    base.update(kwargs)
    return RoadmapResult(**base)


def _stub_run(monkeypatch: pytest.MonkeyPatch, result_or_exc) -> dict:
    """Replace ``run_roadmap`` with a recorder; return the captured call."""
    captured: dict = {}

    def fake(slug, **kwargs):
        captured["slug"] = slug
        captured.update(kwargs)
        if isinstance(result_or_exc, BaseException):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(f"{MODULE}.run_roadmap", fake)
    return captured


def test_selector_free_revise_feedback_dispatches_to_batch_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def proposal(slug: str, selector: object, **kwargs: object) -> SimpleNamespace:
        captured.update(slug=slug, selector=selector, **kwargs)
        return SimpleNamespace(outcome="stored", candidate=None, detail=None)

    invoker = lambda _: (0, "")
    monkeypatch.setattr(roadmap_cmd, "run_initial_candidate_proposal", proposal)
    assert cmd_roadmap(_ns(tmp_path, from_existing=None, revise_feedback=True), invoker=invoker) == 0
    assert captured == {
        "slug": "my-roadmap", "selector": None, "repo_root": tmp_path,
        "plans_dir": tmp_path / "docs" / "implementation-plans", "invoker": invoker,
    }


def test_ordinary_feedback_commands_reject_legacy_selector_values() -> None:
    with pytest.raises(SystemExit) as revise:
        _parse("roadmap", "my-roadmap", "--revise-feedback", "domain:feedback-1")
    with pytest.raises(SystemExit) as propose:
        _parse("roadmap", "my-roadmap", "--propose-candidate", "domain:feedback-1")
    assert revise.value.code == propose.value.code == 2


@pytest.mark.parametrize(
    ("option", "value", "owner"),
    (("defer_feedback", "feedback-1", "defer_reviewer_feedback"),),
)
def test_a_writer_guard_failure_on_a_ledger_command_is_a_clean_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, option: str, value: object, owner: str
) -> None:
    """The ledger owners acquire the writer guard themselves, so a contended or stale guard
    raises from their entry; it must reach the operator as the usage error every other
    lifecycle command gives, not as an unexpected-error traceback."""

    def contended(**_kwargs: object) -> None:
        raise roadmap.RoadmapWriterGuardError("roadmap writer guard is held")

    monkeypatch.setattr(roadmap_cmd, owner, contended)

    assert cmd_roadmap(_ns(tmp_path, from_existing=None, **{option: value})) == roadmap_cmd._RC_USAGE
    assert "roadmap writer guard is held" in capsys.readouterr().err


def test_ledger_mutation_forwards_runtime_owned_target_validation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def submit(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(result="updated")

    monkeypatch.setattr(roadmap_cmd, "submit_reviewer_feedback", submit)
    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, submit_feedback="feedback-1",
        feedback_target="domain:row:order-1", feedback_request="Clarify ordering.",
    )) == 0
    assert captured["item_id"] == "feedback-1"
    assert captured["target"].artifact_key == "domain"
    assert captured["target"].row_id == "order-1"


def test_settlement_response_forwards_exact_confirmation_evidence_name(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}
    final_name = "a" * 64

    def respond(*received: object, **kwargs: object) -> SimpleNamespace:
        captured.update(received=received, **kwargs)
        return SimpleNamespace(outcome="settled", refusal=None, receipt_id=None, status=0)

    monkeypatch.setattr(roadmap_cmd, "respond_enrolled_decision_settlement", respond)
    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, respond_decision_settlement=final_name,
        decision_settlement_yes=True,
    )) == 0
    assert captured["received"] == ("my-roadmap", final_name, True)
    assert captured["plans_dir"] == tmp_path / "docs" / "implementation-plans"


def test_candidate_lifecycle_flags_preserve_exact_occurrences_and_required_answer_pair() -> None:
    """Lifecycle inputs stay exclusive and answer recording names both stored fields."""
    repeated = _parse(
        "roadmap",
        "my-roadmap",
        "--propose-candidate",
        "--propose-candidate",
        "--answer-question",
        "question-a",
        "--answer",
        "first",
        "--answer",
        "second",
    )

    assert repeated.propose_candidate is True
    assert repeated._propose_candidate_occurrences == (True, True)
    assert repeated._answer_question_occurrences == ("question-a",)
    assert repeated._answer_occurrences == ("first", "second")
    assert cmd_roadmap(repeated) == 2

    missing_answer = _parse("roadmap", "my-roadmap", "--answer-question", "question-a")
    assert cmd_roadmap(missing_answer) == 2


def test_new_lifecycle_options_do_not_join_the_broad_mode_group() -> None:
    args = _parse(
        "roadmap",
        "my-roadmap",
        "--review-candidate",
        "a" * 64,
    )

    assert args._roadmap_mode_occurrences == ()
    assert args._review_candidate_occurrences == ("a" * 64,)


@pytest.mark.parametrize(
    "legacy_flag",
    (
        "--enroll-version",
        "--enroll-baselines",
        "--migrate-feedback-ledger",
        "--restore-revision",
        "--confirm-restore-revision",
        "--reopen-feedback",
        "--confirm-feedback-reopen",
    ),
)
def test_removed_legacy_flags_are_rejected_by_the_parser(
    legacy_flag: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """Deliberate: the legacy writer routes are gone with no deprecation stub and no replacement,
    so each flag is an unrecognized argument and cannot silently return."""
    args = ["roadmap", "my-roadmap", legacy_flag]
    if legacy_flag == "--reopen-feedback":
        args.append("domain:feedback-a")

    with pytest.raises(SystemExit) as exit_info:
        _parse(*args)

    assert exit_info.value.code == 2
    assert "unrecognized arguments" in capsys.readouterr().err


def test_propose_candidate_dispatches_to_selector_free_batch_runner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}
    fake_invoker = lambda _prompt: (0, "unused")

    def proposal(slug: str, selector: object, **kwargs: object) -> SimpleNamespace:
        captured.update(slug=slug, selector=selector, **kwargs)
        return SimpleNamespace(outcome="refused", candidate=None, detail="admission refused")

    monkeypatch.setattr(roadmap_cmd, "run_initial_candidate_proposal", proposal)

    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            propose_candidate=True,
        ),
        invoker=fake_invoker,
    ) == 2
    assert captured["slug"] == "my-roadmap"
    assert captured["selector"] is None
    assert captured["invoker"] is fake_invoker


@pytest.mark.parametrize(
    ("entrypoint", "arguments"),
    (
        ("run_initial_candidate_proposal", {"propose_candidate": "domain:feedback-order"}),
        ("generate_candidate_question", {"review_candidate": "a" * 64}),
        (
            "answer_candidate_question",
            {"answer_question": "a" * 64, "answer": "Use the conventional spelling."},
        ),
    ),
)
def test_candidate_lifecycle_value_errors_return_usage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    entrypoint: str,
    arguments: dict[str, str],
) -> None:
    def invalid_slug(*_args: object, **_kwargs: object) -> None:
        raise ValueError("roadmap slug is invalid")

    monkeypatch.setattr(roadmap_cmd, entrypoint, invalid_slug)

    assert cmd_roadmap(_ns(tmp_path, from_existing=None, **arguments)) == 2
    assert "roadmap slug is invalid" in capsys.readouterr().err


@pytest.mark.parametrize(
    "arguments",
    (
        {"propose_candidate": "domain:feedback-order"},
        {"review_candidate": "a" * 64},
        {"answer_question": "a" * 64, "answer": "Use the conventional spelling."},
    ),
)
def test_candidate_lifecycle_rejects_malformed_slug_before_opening_a_run_log(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    arguments: dict[str, str],
) -> None:
    assert cmd_roadmap(_ns(tmp_path, from_existing=None, slug="..", **arguments)) == 2
    assert "slug" in capsys.readouterr().err
    assert not (tmp_path / ".plan-tool" / "runs").exists()


def test_review_candidate_prints_stored_identity_diff_and_question(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    initial = SimpleNamespace(
        version_id="initial-candidate", content=SimpleNamespace(artifact_bytes=()),
        record=SimpleNamespace(predecessor_version_id="accepted-root"),
    )
    question = SimpleNamespace(
        question_id="question-id",
        anchor={"artifact_key": "domain", "kind": "feedback", "feedback_id": "feedback-order"},
        question_text="Use this exact name?",
    )
    result = SimpleNamespace(
        outcome="stored",
        initial_candidate=initial,
        question_inventory=SimpleNamespace(
            predecessor_diff={"changed_rows": ["entity-order"]}, question=question
        ),
        detail=None,
    )
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_args, **_kwargs: result)

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, review_candidate="initial-candidate")
    ) == 0
    assert capsys.readouterr().out == (
        "candidate review: stored\n"
        "candidate: initial-candidate\n"
        "predecessor: accepted-root\n"
        'predecessor diff: {"changed_rows":["entity-order"]}\n'
        "question: question-id\n"
        'anchor: {"artifact_key":"domain","feedback_id":"feedback-order","kind":"feedback"}\n'
        "text: Use this exact name?\n"
        "narrative evidence: none\n"
    )


def test_review_candidate_prints_complete_requirement_with_repeated_relation_occurrences(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    initial = SimpleNamespace(
        version_id="initial-candidate", content=SimpleNamespace(artifact_bytes=()),
        record=SimpleNamespace(predecessor_version_id="accepted-root"),
    )
    question = SimpleNamespace(
        question_id="question-id",
        anchor={"artifact_key": "domain", "kind": "feedback", "feedback_id": "feedback-order"},
        question_text="Use this exact name?",
    )
    requirement = {
        "schema_version": 1,
        "initial_disclosed_impact_identity": "impact-id",
        "reason": "declared-relation-impact",
        "predecessor_version_id": "accepted-root",
        "selected_feedback": {"artifact_key": "domain", "feedback_id": "feedback-order"},
        "capsule_receipt": {"capsule_identity": "capsule-id"},
        "normalized_operations": [{"op": "replace-row", "row_id": "entity-order"}],
        "predecessor_diff": {"changed_rows": ["entity-order"]},
        "affected_predecessor_members": [{"identity": "domain:entity-order"}],
        "impact_atoms": [
            {
                "kind": "relation",
                "direction": "removed",
                "source_index": 0,
                "relation": {"source": "entity-order", "target": "entity-customer"},
            },
            {
                "kind": "relation",
                "direction": "removed",
                "source_index": 1,
                "relation": {"source": "entity-order", "target": "entity-customer"},
            },
        ],
    }
    result = SimpleNamespace(
        outcome="stored",
        initial_candidate=initial,
        question_inventory=SimpleNamespace(
            predecessor_diff={"changed_rows": ["entity-order"]},
            review_requirement=requirement,
            question=question,
        ),
        detail=None,
    )
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_args, **_kwargs: result)

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, review_candidate="initial-candidate")
    ) == 0

    output = capsys.readouterr().out
    assert "review requirement: " + json.dumps(
        requirement, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ) in output
    assert output.index('"source_index":0') < output.index('"source_index":1')


def test_answer_question_forwards_exact_pair_and_prints_sealed_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    captured: dict[str, object] = {}
    result = SimpleNamespace(
        outcome="stored",
        initial_candidate=SimpleNamespace(version_id="initial-candidate"),
        replacement=SimpleNamespace(
            version_id="replacement-id", content=SimpleNamespace(artifact_bytes=()),
            evidence=SimpleNamespace(predecessor_diff={"changed_rows": ["entity-order"]}),
        ),
        seal=SimpleNamespace(seal_id="seal-id"),
        detail=None,
    )

    def answer(slug: str, question_id: str, answer_text: str, **kwargs: object) -> SimpleNamespace:
        captured.update(slug=slug, question_id=question_id, answer_text=answer_text, **kwargs)
        return result

    monkeypatch.setattr(roadmap_cmd, "answer_candidate_question", answer)
    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            answer_question="question-id",
            answer="Use the conventional spelling.",
        )
    ) == 0
    assert captured["question_id"] == "question-id"
    assert captured["answer_text"] == "Use the conventional spelling."
    assert capsys.readouterr().out == (
        "candidate answer: stored\n"
        "replacement: replacement-id\n"
        'predecessor diff: {"changed_rows":["entity-order"]}\n'
        "narrative evidence: none\n"
        "review seal: seal-id\n"
    )


def test_promote_review_seal_holds_matching_writer_guard_without_backend(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    events: list[str] = []
    token = object()

    @contextlib.contextmanager
    def guard(plans_dir: Path, slug: str):
        assert plans_dir == tmp_path / "docs" / "implementation-plans"
        assert slug == "my-roadmap"
        events.append("entered")
        yield token
        events.append("exited")

    def promote(**kwargs: object) -> SimpleNamespace:
        assert events == ["entered"]
        assert kwargs["writer_token"] is token
        assert kwargs["seal_id"] == "seal-id"
        events.append("promoted")
        return SimpleNamespace(version_id="replacement-id", outcome="promoted")

    monkeypatch.setattr(roadmap_cmd, "roadmap_writer_guard", guard)
    monkeypatch.setattr(roadmap_cmd, "promote_review_seal", promote)
    monkeypatch.setattr(
        roadmap_cmd,
        "run_roadmap",
        lambda *_args, **_kwargs: pytest.fail("promotion must not run a backend"),
    )

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, promote_review_seal="seal-id")
    ) == 0
    assert events == ["entered", "promoted", "exited"]
    assert capsys.readouterr().out == "promoted version: replacement-id\n"


def _stored_structural_cli_candidate() -> SimpleNamespace:
    return SimpleNamespace(
        version_id="candidate-id",
        content=SimpleNamespace(artifact_bytes=()),
        record=SimpleNamespace(predecessor_version_id="source-id"),
        evidence=SimpleNamespace(
            root_version_id="root-id",
            batch_receipt=SimpleNamespace(capsule_identity="receipt-id", reviewer_items=()),
            normalized_operations=("replace-row",),
            operation_classification=roadmap_candidate.CandidateOperationClassification.STRUCTURAL,
            predecessor_diff=RoadmapDiff(
                changed_artifacts=(RoadmapArtifactDiff(
                    artifact_key="domain", before_digest="a" * 64, after_digest="b" * 64
                ),),
                changed_rows=(
                    RoadmapRowDiff(
                        artifact_key="domain", row_type="entities", row_id="entity-order",
                        before={"name": "Old"}, after={"name": "New"},
                    ),
                    RoadmapRowDiff(
                        artifact_key="plans", row_type="ordering", row_id="plan-order",
                        before={"phase": 1}, after={"phase": 2},
                    ),
                ),
                added_relations=(), removed_relations=(),
            ),
        ),
    )


def _prose_amended_add_row(*, artifact_key: str, row_id: str, fragment: str):
    return roadmap_candidate.CandidateAddRow(
        feedback_id=f"feedback-{row_id}",
        artifact_key=artifact_key,
        row_type="entities",
        row=EntityRow(id=row_id, name=row_id, fields=()),
        prose_amendment=roadmap_candidate.CandidateAddRowProseAmendment(
            row_id=row_id, fragment=fragment
        ),
    )


def _admit_candidate(monkeypatch: pytest.MonkeyPatch, candidate_id: str = "candidate-id") -> None:
    """Point the active-candidate pointer at one candidate, as a stored proposal leaves it."""
    monkeypatch.setattr(
        roadmap_cmd, "load_candidate_admission",
        lambda **_kwargs: SimpleNamespace(candidate_version_id=candidate_id),
    )


def _stub_candidate_stack_route(
    monkeypatch: pytest.MonkeyPatch, *, is_structural: bool = True, error: Exception | None = None
) -> list[dict]:
    """Answer the precheck's stack derivation, recording the keywords it was asked with.

    The precheck asks about the whole unpromoted stack, not the candidate's own stored route, so a
    test that fakes the candidate must also fake the stack answer it is meant to reach.
    """
    asked: list[dict] = []

    def candidate_stack_route(**kwargs: object) -> SimpleNamespace:
        asked.append(kwargs)
        if error is not None:
            raise error
        return SimpleNamespace(is_structural=is_structural)

    monkeypatch.setattr(roadmap_cmd, "candidate_stack_route", candidate_stack_route)
    return asked


_STUB_DIGEST = "d" * 64


def _stack_view_with_digest(digest: str, *hops: SimpleNamespace):
    """A hand-built view whose digest is fixed, so a CLI case need not build digestible stored hops."""

    class FixedDigestView(roadmap_candidate_review.CandidateStackView):
        @property
        def digest(self) -> str:
            return digest

    return FixedDigestView(
        root_version_id="root-id", hops=hops, cumulative_diff=_stack_hop_diff("cumulative-row")
    )


def _stub_stack_view(
    monkeypatch: pytest.MonkeyPatch, candidate, *, digest: str = _STUB_DIGEST, error: Exception | None = None
) -> list[dict]:
    """Answer the approve path's stack-view build with a one-hop view of `candidate`, recording the
    keywords it was asked with. The stack view's own contents are step-4 territory; here only what the
    CLI does with the view and its digest is under test."""
    asked: list[dict] = []

    def build_candidate_stack_view(**kwargs: object):
        asked.append(kwargs)
        if error is not None:
            raise error
        return _stack_view_with_digest(digest, candidate)

    monkeypatch.setattr(roadmap_cmd, "build_candidate_stack_view", build_candidate_stack_view)
    return asked


def test_confirmed_structural_approve_prints_the_same_printout_then_seals_and_promotes_the_returned_seal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The confirmed invocation shows the stack and its digest before sealing, and promotes only the
    seal the library returned."""
    candidate = _stored_structural_cli_candidate()
    calls: list[str] = []
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    _stub_stack_view(monkeypatch, candidate)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)

    def decide(*args: object, **kwargs: object) -> SimpleNamespace:
        assert args == ("my-roadmap", "candidate-id", "approve")
        assert kwargs["correction"] is None
        assert kwargs["confirm_digest"] == _STUB_DIGEST
        calls.append("decide")
        return SimpleNamespace(
            outcome="stored", active_candidate=None,
            seal=SimpleNamespace(seal_id="seal-id"), detail=None,
        )

    def promote(*_args: object, **kwargs: object) -> int:
        assert calls == ["decide"]
        assert kwargs["seal_id"] == "seal-id"
        calls.append("promote")
        return 0

    monkeypatch.setattr(roadmap_cmd, "decide_structural_candidate", decide)
    monkeypatch.setattr(roadmap_cmd, "_cmd_roadmap_promote_review_seal_id", promote)

    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve",
        confirm_stack_digest=_STUB_DIGEST,
    )) == 0
    assert calls == ["decide", "promote"]
    output = capsys.readouterr().out
    assert output.index("candidate stack:") < output.index(f"stack digest: {_STUB_DIGEST}")
    assert output.index("structural proposal: stored") < output.index(f"stack digest: {_STUB_DIGEST}")
    assert output.index(f"stack digest: {_STUB_DIGEST}") < output.index("structural decision: approve stored")
    assert "selected feedback:" in output
    assert 'stored route: "structural"' in output
    assert "typed operations:" in output
    assert '"artifact_key":"domain"' in output
    assert '"row_id":"entity-order"' in output
    assert '"name":"Old"' in output and '"name":"New"' in output
    assert '"row_type":"ordering"' in output
    assert "added relations: []" in output and "removed relations: []" in output
    assert "non-goals:" in output


def test_presentation_candidate_keeps_the_existing_proposal_output(capsys) -> None:
    candidate = _stored_structural_cli_candidate()
    candidate.evidence.operation_classification = (
        roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
    )
    roadmap_cmd._render_candidate_proposal_result(
        SimpleNamespace(outcome="stored", candidate=candidate, detail=None), stack_view=None
    )
    output = capsys.readouterr().out
    assert "candidate proposal: stored" in output
    assert "structural proposal:" not in output
    assert "choices: approve, edit, reject" not in output


def test_structural_candidate_edit_requires_one_correction_and_never_promotes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """An edit creates an unapproved replacement and cannot reach the accepted-head writer."""
    candidate = _stored_structural_cli_candidate()
    edited_candidate = _stored_structural_cli_candidate()
    edited_candidate.version_id = "edited-id"
    edited_candidate.evidence.predecessor_diff = edited_candidate.evidence.predecessor_diff.model_copy(
        update={"changed_rows": (RoadmapRowDiff(
            artifact_key="domain", row_type="entities", row_id="entity-order",
            before={"name": "Old"}, after={"name": "Edited"},
        ),)}
    )
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    _stub_stack_views_by_candidate(monkeypatch, {
        "candidate-id": _stack_view(candidate), "edited-id": _stack_view(edited_candidate),
    })
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    monkeypatch.setattr(
        roadmap_cmd, "decide_structural_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            outcome="stored", active_candidate=edited_candidate, seal=None, detail=None
        ),
    )
    monkeypatch.setattr(
        roadmap_cmd, "_cmd_roadmap_promote_review_seal_id",
        lambda *_args, **_kwargs: pytest.fail("editing must not promote"),
    )

    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="edit",
        candidate_correction="Use an explicit ownership row.",
    )) == 0
    output = capsys.readouterr().out
    assert "replacement: edited-id" in output
    assert output.count('stored route: "structural"') == 2
    assert '"name":"Edited"' in output
    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="edit",
    )) == 2


@pytest.mark.parametrize(
    ("decision", "outcome", "detail", "expected_rc"),
    (
        ("reject", "stored", None, 0),
        ("approve", "refused", "stale active pointer", 2),
        ("approve", "response-rejected", "invalid candidate response", 1),
        ("edit", "failed", "backend failed", 1),
    ),
)
def test_structural_decision_results_remain_distinct_without_promotion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys,
    decision: str, outcome: str, detail: str | None, expected_rc: int,
) -> None:
    candidate = _stored_structural_cli_candidate()
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    _stub_stack_view(monkeypatch, candidate)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    monkeypatch.setattr(
        roadmap_cmd, "decide_structural_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(
            outcome=outcome, active_candidate=None, seal=None, detail=detail
        ),
    )
    monkeypatch.setattr(
        roadmap_cmd, "_cmd_roadmap_promote_review_seal_id",
        lambda *_args, **_kwargs: pytest.fail("non-approval result must not promote"),
    )
    args = _ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision=decision,
        candidate_correction="Change ownership." if decision == "edit" else None,
        confirm_stack_digest=_STUB_DIGEST if decision == "approve" else None,
    )
    assert cmd_roadmap(args) == expected_rc
    output = capsys.readouterr().out
    assert f"structural decision: {decision} {outcome}" in output
    if detail:
        assert f"reason: {detail}" in output


@pytest.mark.parametrize(
    ("decision", "confirmed"),
    (("approve", True), ("approve", False), ("edit", False), ("reject", False)),
    ids=("approve-confirmed", "approve-unconfirmed", "edit", "reject"),
)
@pytest.mark.parametrize(
    "case",
    (
        "presentation-only", "underivable-stack", "route-less", "superseded-candidate", "no-active-pointer",
    ),
)
def test_structural_precheck_refusal_precedes_the_stack_printout_for_both_invocations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, decision: str, confirmed: bool, case: str
) -> None:
    """An approval prompt is never shown for a candidate that cannot be decided: the disclosure,
    with its promotion effects and choices, and the stack and digest follow only the eligibility the
    library re-checks, so neither the unconfirmed nor the confirmed approve prints them for an
    ineligible candidate. `presentation-only` is a stack with no structural hop; `underivable-stack`
    is one whose route cannot be read, which refuses rather than reading as "not structural"."""
    candidate = _stored_structural_cli_candidate()
    if case == "presentation-only":
        candidate.evidence.operation_classification = (
            roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
        )
        asked = _stub_candidate_stack_route(monkeypatch, is_structural=False)
    elif case == "underivable-stack":
        asked = _stub_candidate_stack_route(
            monkeypatch, error=roadmap_candidate_run.CandidateProposalError("candidate source ancestry is unreadable")
        )
    else:
        asked = _stub_candidate_stack_route(monkeypatch)
        if case == "route-less":
            candidate.evidence.operation_classification = None
            candidate.evidence.normalized_operations = None
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    if case == "no-active-pointer":
        monkeypatch.setattr(roadmap_cmd, "load_candidate_admission", lambda **_kwargs: None)
    else:
        _admit_candidate(monkeypatch, "replacement-id" if case == "superseded-candidate" else "candidate-id")
    monkeypatch.setattr(
        roadmap_cmd, "decide_structural_candidate",
        lambda *_args, **_kwargs: pytest.fail("an ineligible candidate reached the decision"),
    )
    monkeypatch.setattr(
        roadmap_cmd, "build_candidate_stack_view",
        lambda **_kwargs: pytest.fail("the stack view was built for an ineligible candidate"),
    )

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision=decision,
        candidate_correction="Change ownership." if decision == "edit" else None,
        confirm_stack_digest=_STUB_DIGEST if confirmed else None,
    ))

    captured = capsys.readouterr()
    assert rc == 2
    assert "structural proposal:" not in captured.out + captured.err
    assert "choices: approve, edit, reject" not in captured.out + captured.err
    assert "candidate stack:" not in captured.out + captured.err
    assert "stack digest:" not in captured.out + captured.err
    if case == "underivable-stack":
        assert "underivable" in captured.err
    if case == "route-less":
        assert asked == [], "a candidate with no stored operations is refused before the stack is derived"


@pytest.mark.parametrize("decision", ("approve", "edit", "reject"))
def test_structural_decision_accepts_a_presentation_only_top_when_its_stack_is_structural(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, decision: str
) -> None:
    """The reported defect: a presentation-only top of a structural stack was refused before its
    disclosure, so the structural change beneath it could never be approved, edited, or rejected."""
    candidate = _stored_structural_cli_candidate()
    candidate.evidence.operation_classification = (
        roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY
    )
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch, is_structural=True)
    _stub_stack_view(monkeypatch, candidate)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    decided: list[str] = []
    stored = {
        "approve": SimpleNamespace(
            outcome="stored", active_candidate=None, seal=SimpleNamespace(seal_id="seal-id"), detail=None
        ),
        "edit": SimpleNamespace(
            outcome="stored", active_candidate=_stored_structural_cli_candidate(), seal=None, detail=None
        ),
        "reject": SimpleNamespace(outcome="stored", active_candidate=None, seal=None, detail=None),
    }

    def decide(_slug: str, candidate_id: str, chosen: str, **_kwargs: object) -> SimpleNamespace:
        decided.append(f"{candidate_id}:{chosen}")
        return stored[chosen]

    monkeypatch.setattr(roadmap_cmd, "decide_structural_candidate", decide)
    monkeypatch.setattr(roadmap_cmd, "_cmd_roadmap_promote_review_seal_id", lambda *_args, **_kwargs: 0)

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision=decision,
        candidate_correction="Change ownership." if decision == "edit" else None,
        confirm_stack_digest=_STUB_DIGEST if decision == "approve" else None,
    ))

    output = capsys.readouterr().out
    assert rc == 0
    assert decided == [f"candidate-id:{decision}"]
    assert "structural proposal: stored" in output


def test_structural_precheck_derives_the_stack_from_the_candidate_and_its_recorded_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stack is the candidate's own unpromoted ancestry down to the root its evidence records, so
    the precheck must not ask about the current head or the admission's root: both move on promotion,
    and a stack derived from either would answer differently after the promotion it gates."""
    candidate = _stored_structural_cli_candidate()
    _admit_candidate(monkeypatch)
    asked = _stub_candidate_stack_route(monkeypatch)
    _stub_stack_view(monkeypatch, candidate)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    monkeypatch.setattr(
        roadmap_cmd, "decide_structural_candidate",
        lambda *_args, **_kwargs: SimpleNamespace(outcome="stored", active_candidate=None, seal=None, detail=None),
    )

    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="reject",
    )) == 0

    assert asked == [{
        "plans_dir": tmp_path.resolve() / "docs" / "implementation-plans",
        "slug": "my-roadmap",
        "tip_version_id": "candidate-id",
        "root_version_id": candidate.evidence.root_version_id,
    }]


def test_decide_candidate_reaches_a_presentation_only_top_of_a_real_structural_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The precheck and the library guard each answer "does this stack carry a structural route?".
    The stubbed tests above hand the precheck its answer; only a real stack stored by the runner, with
    neither side stubbed, shows the two agree. A precheck that disagreed with the guard would refuse a
    stack the library accepts, or accept one it refuses."""
    from tests.test_roadmap_candidate_run import _store_stack

    _root_version, (_structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"

    rc = cmd_roadmap(_ns(
        tmp_path, slug="storefront", plans_dir=plans_dir, from_existing=None,
        decide_candidate=top.version_id, candidate_decision="reject",
    ))

    output = capsys.readouterr()
    assert rc == 0, output.out + output.err
    assert "structural decision: reject stored" in output.out
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug="storefront")
    assert admission is not None and admission.active_candidate_version_id is None


def _stack_hop_diff(row_id: str) -> RoadmapDiff:
    """One changed row named for its hop, so a test can tell which hop's diff a line came from."""
    return RoadmapDiff(
        changed_artifacts=(RoadmapArtifactDiff(
            artifact_key="domain", before_digest="a" * 64, after_digest="b" * 64
        ),),
        changed_rows=(RoadmapRowDiff(
            artifact_key="domain", row_type="entities", row_id=row_id,
            before={"name": "Old"}, after={"name": "New"},
        ),),
        added_relations=(), removed_relations=(),
    )


def _stack_hop(version_id: str, *, route) -> SimpleNamespace:
    """A hand-built stored hop. The printout reads only fields and never the digest, so no stored
    record is needed; each hop carries its own id, receipt, feedback, and diff row."""
    hop = _stored_structural_cli_candidate()
    hop.version_id = version_id
    hop.record.predecessor_version_id = f"source-of-{version_id}"
    hop.evidence.operation_classification = route
    hop.evidence.batch_receipt = SimpleNamespace(
        capsule_identity=f"receipt-of-{version_id}",
        reviewer_items=({"item_id": f"feedback-of-{version_id}"},),
    )
    hop.evidence.predecessor_diff = _stack_hop_diff(f"row-of-{version_id}")
    return hop


def _stack_view(*hops: SimpleNamespace):
    return roadmap_candidate_review.CandidateStackView(
        root_version_id="root-id", hops=hops, cumulative_diff=_stack_hop_diff("cumulative-row")
    )


_STRUCTURAL = roadmap_candidate.CandidateOperationClassification.STRUCTURAL
_PRESENTATION_ONLY = roadmap_candidate.CandidateOperationClassification.PRESENTATION_ONLY


def _printed_stack(view, capsys) -> list[str]:
    roadmap_cmd._render_structural_candidate_stack(view)
    return capsys.readouterr().out.splitlines()


def _printed_disclosure(candidate, capsys) -> list[str]:
    roadmap_cmd._render_structural_candidate_disclosure(candidate)
    return capsys.readouterr().out.splitlines()


def _hop_sections(lines: list[str]) -> dict[str, list[str]]:
    """The indented lines under each `stack hop N of M: <id>` header, keyed by hop id."""
    sections: dict[str, list[str]] = {}
    current: list[str] | None = None
    for line in lines:
        header = re.fullmatch(r"stack hop \d+ of \d+: (.+)", line)
        if header:
            current = sections.setdefault(header.group(1), [])
        elif current is not None and line.startswith("  "):
            current.append(line.strip())
        else:
            current = None
    return sections


def test_stack_printout_lists_every_hop_oldest_first_with_route_selected_feedback_and_own_diff(capsys) -> None:
    lower, middle, top = (
        _stack_hop("hop-a", route=_STRUCTURAL),
        _stack_hop("hop-b", route=_PRESENTATION_ONLY),
        _stack_hop("hop-c", route=_PRESENTATION_ONLY),
    )

    lines = _printed_stack(_stack_view(lower, middle, top), capsys)

    headers = [line for line in lines if line.startswith("stack hop ")]
    assert headers == ["stack hop 1 of 3: hop-a", "stack hop 2 of 3: hop-b"]
    assert lines.index("candidate: hop-c") > lines.index(headers[1]) > lines.index(headers[0])
    sections = _hop_sections(lines)
    assert set(sections) == {"hop-a", "hop-b"}
    assert 'stored route: "structural"' in sections["hop-a"]
    assert 'stored route: "presentation-only"' in sections["hop-b"]
    for hop_id, section in sections.items():
        assert 'selected feedback: [{"item_id":"feedback-of-%s"}]' % hop_id in section
        assert 'batch receipt: "receipt-of-%s"' % hop_id in section
        assert any(f'"row_id":"row-of-{hop_id}"' in line for line in section)
        assert not any("cumulative-row" in line for line in section)


def test_structural_disclosure_prints_row_linked_prose_amendment_records(capsys) -> None:
    candidate = _stored_structural_cli_candidate()
    candidate.evidence.normalized_operations = (
        _prose_amended_add_row(
            artifact_key="domain", row_id="entity-amended", fragment="### entity-amended\nExact fragment."
        ),
    )

    lines = _printed_disclosure(candidate, capsys)

    (record_line,) = [line for line in lines if line.startswith("row-linked prose amendments:")]
    assert '"artifact_key":"domain"' in record_line
    assert '"row_id":"entity-amended"' in record_line
    assert '"fragment":"### entity-amended\\nExact fragment."' in record_line
    assert lines.index(record_line) < lines.index("affected artifacts: " + roadmap_cmd._render_stored_value(
        candidate.evidence.predecessor_diff.changed_artifacts
    ))


def test_structural_disclosure_prints_row_linked_prose_amendments_line_when_none_present(capsys) -> None:
    """Every other disclosure field prints unconditionally with an explicit empty value;
    the amendment line must not vanish for a replace/remove-only candidate, which would
    make 'zero amendments' indistinguishable from 'this build doesn't report them'."""
    candidate = _stored_structural_cli_candidate()

    lines = _printed_disclosure(candidate, capsys)

    assert "row-linked prose amendments: []" in lines


def test_stack_printout_lists_amendment_records_for_each_hop(capsys) -> None:
    lower = _stack_hop("hop-a", route=_STRUCTURAL)
    top = _stack_hop("hop-b", route=_PRESENTATION_ONLY)
    lower.evidence.normalized_operations = (
        _prose_amended_add_row(artifact_key="domain", row_id="entity-lower", fragment="lower first"),
        _prose_amended_add_row(artifact_key="domain", row_id="entity-later", fragment="lower second"),
    )
    top.evidence.normalized_operations = (
        _prose_amended_add_row(artifact_key="domain", row_id="entity-top", fragment="top fragment"),
    )

    lines = _printed_stack(_stack_view(lower, top), capsys)
    lower_records = next(line for line in _hop_sections(lines)["hop-a"] if line.startswith("row-linked prose amendments:"))
    top_record = next(line for line in lines if line.startswith("row-linked prose amendments:"))

    assert lower_records.index('"row_id":"entity-lower"') < lower_records.index('"row_id":"entity-later"')
    assert '"fragment":"lower first"' in lower_records
    assert '"row_id":"entity-top"' in top_record
    assert '"fragment":"top fragment"' in top_record


def test_stack_printout_keeps_every_line_the_existing_disclosure_prints_for_the_top_candidate(capsys) -> None:
    """The stack view extends the disclosure and never replaces it, and the disclosure's closing
    `choices` line stays the last line."""
    lower, top = _stack_hop("hop-a", route=_STRUCTURAL), _stack_hop("hop-b", route=_PRESENTATION_ONLY)
    disclosure = _printed_disclosure(top, capsys)

    lines = _printed_stack(_stack_view(lower, top), capsys)

    assert lines[-len(disclosure):] == disclosure
    assert lines[-1] == "choices: approve, edit, reject"


def test_stack_printout_names_the_structural_hop_when_the_top_is_presentation_only(capsys) -> None:
    lines = _printed_stack(
        _stack_view(
            _stack_hop("hop-a", route=_STRUCTURAL),
            _stack_hop("hop-b", route=_PRESENTATION_ONLY),
            _stack_hop("hop-c", route=_PRESENTATION_ONLY),
        ),
        capsys,
    )

    (effects,) = [line for line in lines if line.startswith("stack promotion effects:")]
    assert effects == (
        'stack promotion effects: hops promoted together: ["hop-a","hop-b","hop-c"]; '
        'structural hops that invalidate enrolled seed state: ["hop-a"]'
    )


def test_stack_printout_states_that_a_route_less_hop_has_no_stored_route(capsys) -> None:
    """Deliberate: a hop with no stored route gets an explicit marker rather than a missing line, and
    the marker is not the presentation-only output."""
    lines = _printed_stack(
        _stack_view(
            _stack_hop("hop-a", route=None),
            _stack_hop("hop-b", route=_PRESENTATION_ONLY),
            _stack_hop("hop-c", route=_STRUCTURAL),
        ),
        capsys,
    )

    sections = _hop_sections(lines)
    assert "stored route: no stored route" in sections["hop-a"]
    assert 'stored route: "presentation-only"' in sections["hop-b"]
    assert not any("presentation-only" in line for line in sections["hop-a"])


def test_stack_printout_prints_the_cumulative_diff_for_a_multi_hop_stack_and_one_line_for_a_single_hop(
    capsys
) -> None:
    multi = _printed_stack(
        _stack_view(_stack_hop("hop-a", route=_STRUCTURAL), _stack_hop("hop-b", route=_PRESENTATION_ONLY)),
        capsys,
    )

    start = multi.index("cumulative diff, accepted root to top candidate:")
    block = multi[start + 1:start + 6]
    assert [line.split(":")[0].strip() for line in block] == [
        "affected artifacts", "affected rows and before/after values",
        "added relations", "removed relations", "ordering effects",
    ]
    assert '"row_id":"cumulative-row"' in block[1]

    single = _printed_stack(_stack_view(_stack_hop("hop-a", route=_STRUCTURAL)), capsys)

    assert (
        "cumulative diff, accepted root to top candidate: equals the top candidate's own diff (one hop)"
        in single
    )
    assert not any("cumulative-row" in line for line in single)
    assert not any(line.startswith("stack hop ") or line.startswith("  ") for line in single)


def test_stack_printout_is_a_pure_render_and_reads_no_stored_state(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The view is the only input: a printout that reloaded a candidate, the admission pointer, or the
    stack would let the text disagree with the digest the view carries."""
    def refuse(*_args: object, **_kwargs: object):
        pytest.fail("the stack printout read stored state")

    for name in ("load_stored_candidate_proposal", "load_candidate_admission", "candidate_stack_route"):
        monkeypatch.setattr(roadmap_cmd, name, refuse)

    lines = _printed_stack(
        _stack_view(_stack_hop("hop-a", route=_STRUCTURAL), _stack_hop("hop-b", route=_PRESENTATION_ONLY)),
        capsys,
    )

    assert "stack hop 1 of 2: hop-a" in lines


def test_stack_printout_from_a_real_stack_prints_every_hop_and_never_prints_the_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The hand-built hops above can carry any shape; only a view built from real stored records shows
    the printout's fields exist on what the builder returns. The digest is for the confirm step to
    print beside the printout, so the printout itself must not contain it."""
    from tests.test_roadmap_candidate_run import _store_stack

    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    view = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=tmp_path / "plans", slug="storefront", candidate=top
    )

    lines = _printed_stack(view, capsys)

    printed = "\n".join(lines)
    assert f"stack hop 1 of 2: {structural.version_id}" in lines
    assert f"candidate: {top.version_id}" in lines
    assert 'stored route: "structural"' in _hop_sections(lines)[structural.version_id]
    assert view.digest not in printed


@pytest.mark.parametrize(
    "argv",
    (
        ("--propose-candidate", "--apply"),
        ("--review-candidate", "initial", "--propose-candidate"),
        ("--answer-question", "question", "--answer", "text", "-y"),
        ("--decide-candidate", "candidate", "--candidate-decision", "approve", "--apply"),
        ("--promote-review-seal", "seal", "--output", "review.html"),
        ("--confirm-stack-digest", _STUB_DIGEST),
        (
            "--decide-candidate", "candidate", "--candidate-decision", "edit",
            "--candidate-correction", "Use owner.", "--confirm-stack-digest", _STUB_DIGEST,
        ),
        (
            "--decide-candidate", "candidate", "--candidate-decision", "reject",
            "--confirm-stack-digest", _STUB_DIGEST,
        ),
        ("--reject-candidate", "candidate", "--confirm-stack-digest", _STUB_DIGEST),
        (
            "--decide-candidate", "candidate", "--candidate-decision", "approve",
            "--confirm-stack-digest", _STUB_DIGEST, "--confirm-stack-digest", _STUB_DIGEST,
        ),
        ("--decide-candidate", "candidate", "--confirm-stack-digest", _STUB_DIGEST),
        ("--promote-review-seal", "seal", "--confirm-stack-digest", _STUB_DIGEST),
        (
            "--decide-candidate", "candidate", "--candidate-decision", "approve",
            "--confirm-stack-digest", _STUB_DIGEST, "-y",
        ),
        (
            "--decide-candidate", "candidate", "--candidate-decision", "approve",
            "--confirm-stack-digest", _STUB_DIGEST, "--apply",
        ),
    ),
    ids=(
        "propose-with-apply", "review-with-propose", "answer-with-yes",
        "approve-with-apply", "promote-with-output",
        "confirm-digest-alone", "confirm-digest-with-edit", "confirm-digest-with-reject",
        "confirm-digest-with-reject-candidate", "confirm-digest-twice",
        "confirm-digest-without-a-decision", "confirm-digest-with-promote-review-seal",
        "confirm-digest-with-yes", "confirm-digest-with-apply",
    ),
)
def test_candidate_lifecycle_actions_reject_companion_modes_before_side_effects(
    monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]
) -> None:
    args = _parse("roadmap", "my-roadmap", *argv)

    def unexpected(*_args, **_kwargs):
        pytest.fail("candidate lifecycle conflicts must stop before side effects")

    for name in (
        "_resolve_cmd_repo_root",
        "resolve_explicit_plans_dir",
        "resolve_output_dir",
        "render_roadmap_html",
        "review_path",
        "atomic_write_text",
        "run_initial_candidate_proposal",
        "generate_candidate_question",
        "answer_candidate_question",
        "promote_review_seal",
        "run_roadmap",
        "build_candidate_stack_view",
        "decide_structural_candidate",
    ):
        monkeypatch.setattr(roadmap_cmd, name, unexpected)

    assert cmd_roadmap(args) == 2


@pytest.mark.parametrize(
    "argv",
    (
        ("--compare",),
        ("--settle-decision", "decision-a", "--confirm-decision-settlement"),
    ),
    ids=("compare", "settlement"),
)
def test_confirm_flag_beside_a_sibling_exclusive_mode_is_rejected(
    monkeypatch: pytest.MonkeyPatch, argv: tuple[str, ...]
) -> None:
    """The flag joins `_has_candidate_lifecycle_action`, which every sibling exclusive-mode predicate
    reads. A sibling that did not see it would run its own action and silently ignore the digest."""
    args = _parse("roadmap", "my-roadmap", *argv, "--confirm-stack-digest", _STUB_DIGEST)

    def unexpected(*_args, **_kwargs):
        pytest.fail("a stray --confirm-stack-digest must stop before any mode dispatches")

    for name in (
        "_resolve_cmd_repo_root",
        "resolve_explicit_plans_dir",
        "resolve_output_dir",
        "_cmd_roadmap_comparison",
        "_cmd_roadmap_decision_settlement",
        "run_roadmap",
    ):
        monkeypatch.setattr(roadmap_cmd, name, unexpected)

    assert cmd_roadmap(args) == 2


def test_confirm_flag_parses_as_a_tracked_value_option() -> None:
    other = "e" * 64

    once = _parse(
        "roadmap", "my-roadmap", "--decide-candidate", "candidate", "--candidate-decision", "approve",
        "--confirm-stack-digest", _STUB_DIGEST,
    )
    twice = _parse(
        "roadmap", "my-roadmap", "--decide-candidate", "candidate", "--candidate-decision", "approve",
        "--confirm-stack-digest", _STUB_DIGEST, "--confirm-stack-digest", other,
    )
    empty = _parse("roadmap", "my-roadmap", "--confirm-stack-digest", "")
    absent = _parse("roadmap", "my-roadmap", "--decide-candidate", "candidate")

    assert (once.confirm_stack_digest, once._confirm_stack_digest_occurrences) == (
        _STUB_DIGEST, (_STUB_DIGEST,)
    )
    assert (twice.confirm_stack_digest, twice._confirm_stack_digest_occurrences) == (
        other, (_STUB_DIGEST, other)
    )
    assert (empty.confirm_stack_digest, empty._confirm_stack_digest_occurrences) == ("", ("",))
    assert (absent.confirm_stack_digest, absent._confirm_stack_digest_occurrences) == (None, ())


def test_roadmap_help_documents_the_confirm_flag_and_the_write_nothing_first_invocation() -> None:
    # argparse wraps help with textwrap, which may break a hyphenated flag across lines, so compare with
    # every space removed rather than joined.
    squashed = "".join(_roadmap_help().split())

    assert "--confirm-stack-digestDIGEST" in squashed
    assert "writesnothinguntil--confirm-stack-digestsuppliesthatdigest" in squashed
    assert "recomputedatconfirmtime.-yisnotconfirmation" in squashed


def _unconfirmed_approve_setup(monkeypatch: pytest.MonkeyPatch, candidate, *, is_structural: bool = True):
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch, is_structural=is_structural)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    monkeypatch.setattr(
        roadmap_cmd, "decide_structural_candidate",
        lambda *_args, **_kwargs: pytest.fail("an unconfirmed approve called the library decision"),
    )
    monkeypatch.setattr(
        roadmap_cmd, "roadmap_writer_guard",
        lambda *_args, **_kwargs: pytest.fail("an unconfirmed approve took the writer guard"),
    )
    monkeypatch.setattr(
        roadmap_cmd, "_cmd_roadmap_promote_review_seal_id",
        lambda *_args, **_kwargs: pytest.fail("an unconfirmed approve reached promotion"),
    )


def test_unconfirmed_structural_approve_prints_the_stack_and_digest_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    candidate = _stored_structural_cli_candidate()
    _unconfirmed_approve_setup(monkeypatch, candidate)
    asked = _stub_stack_view(monkeypatch, candidate)
    printed: list[object] = []
    monkeypatch.setattr(
        roadmap_cmd, "_render_structural_candidate_stack", lambda view: printed.append(view)
    )
    before = sorted(tmp_path.rglob("*"))

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve"
    ))

    output = capsys.readouterr().out
    assert rc == 2
    assert len(asked) == 1 and asked[0]["candidate"] is candidate and asked[0]["slug"] == "my-roadmap"
    assert len(printed) == 1 and printed[0].digest == _STUB_DIGEST
    assert f"stack digest: {_STUB_DIGEST}" in output
    assert "structural decision: approve confirmation-required" in output
    (reason,) = [line for line in output.splitlines() if line.startswith("reason:")]
    assert f"--confirm-stack-digest {_STUB_DIGEST}" in reason
    assert sorted(tmp_path.rglob("*")) == before


@pytest.mark.parametrize("top_route", ("structural", "presentation-only"))
def test_unconfirmed_structural_approve_never_exits_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, top_route: str
) -> None:
    """Automation reads exit 0 from this command as "approved", so the invocation that seals nothing
    cannot exit 0 for an own-structural candidate or for a presentation-only top of a structural stack."""
    candidate = _stored_structural_cli_candidate()
    if top_route == "presentation-only":
        candidate.evidence.operation_classification = _PRESENTATION_ONLY
    _unconfirmed_approve_setup(monkeypatch, candidate)
    _stub_stack_view(monkeypatch, candidate)

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve"
    ))

    assert rc == 2


def test_confirmed_approve_passes_the_operators_digest_not_the_one_the_cli_computed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The library is the only comparison. A CLI that handed it the digest it had just computed would
    confirm anything, so the operator's value must arrive unchanged."""
    candidate = _stored_structural_cli_candidate()
    computed, supplied = "a" * 64, "b" * 64
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    _stub_stack_view(monkeypatch, candidate, digest=computed)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    received: list[object] = []

    def decide(*_args: object, **kwargs: object) -> SimpleNamespace:
        received.append(kwargs["confirm_digest"])
        return SimpleNamespace(
            outcome="refused", active_candidate=None, seal=None, detail="digest differs"
        )

    monkeypatch.setattr(roadmap_cmd, "decide_structural_candidate", decide)
    monkeypatch.setattr(
        roadmap_cmd, "_cmd_roadmap_promote_review_seal_id",
        lambda *_args, **_kwargs: pytest.fail("a refused confirmation reached promotion"),
    )

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve",
        confirm_stack_digest=supplied,
    ))

    output = capsys.readouterr().out
    assert rc == 2
    assert received == [supplied]
    assert f"stack digest: {computed}" in output
    assert "structural decision: approve refused" in output
    assert "reason: digest differs" in output


def test_empty_digest_is_a_present_confirm_that_reaches_the_library_not_an_absent_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Presence is `is None`, never truthiness: `--confirm-stack-digest ""` is a wrong confirmation
    for the library to refuse, not the write-nothing first invocation."""
    candidate = _stored_structural_cli_candidate()
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    _stub_stack_view(monkeypatch, candidate)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)
    received: list[object] = []

    def decide(*_args: object, **kwargs: object) -> SimpleNamespace:
        received.append(kwargs["confirm_digest"])
        return SimpleNamespace(outcome="refused", active_candidate=None, seal=None, detail="digest differs")

    monkeypatch.setattr(roadmap_cmd, "decide_structural_candidate", decide)

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve",
        confirm_stack_digest="",
    ))

    assert rc == 2
    assert received == [""]
    assert "confirmation-required" not in capsys.readouterr().out


@pytest.mark.parametrize("confirmed", (False, True), ids=("unconfirmed", "confirmed"))
def test_stack_view_failure_refuses_before_any_output_and_any_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, confirmed: bool
) -> None:
    candidate = _stored_structural_cli_candidate()
    _unconfirmed_approve_setup(monkeypatch, candidate)
    _stub_stack_view(
        monkeypatch, candidate,
        error=roadmap_candidate_review.CandidateReviewError("candidate stack is underivable: source is gone"),
    )

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve",
        confirm_stack_digest=_STUB_DIGEST if confirmed else None,
    ))

    captured = capsys.readouterr()
    assert rc == 2
    assert "candidate stack is underivable" in captured.err
    assert captured.out == ""


def _approve_argv_namespace(tmp_path: Path, top, plans_dir: Path, *, digest: str | None):
    return _ns(
        tmp_path, slug="storefront", plans_dir=plans_dir, from_existing=None,
        decide_candidate=top.version_id, candidate_decision="approve", confirm_stack_digest=digest,
    )


def _file_contents(directory: Path) -> dict[str, bytes]:
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def test_unconfirmed_approve_over_a_real_stack_writes_nothing_and_its_digest_confirms_the_second_invocation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The digest one invocation prints is the value the next accepts: a seam neither stubbed layer shows.
    The first invocation over a real presentation-only top of a structural hop changes nothing on disk;
    the second, given the printed digest, seals and promotes the top."""
    from tests.test_roadmap_candidate_run import (
        _green_gates,
        _store_stack,
    )

    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    head_before = roadmap_versions.accepted_head_path(plans_dir, "storefront").read_bytes()
    before = _file_contents(tmp_path)

    first = cmd_roadmap(_approve_argv_namespace(tmp_path, top, plans_dir, digest=None))

    first_out = capsys.readouterr().out
    assert first == 2
    assert structural.version_id in first_out and top.version_id in first_out
    (digest,) = re.findall(r"^stack digest: ([0-9a-f]{64})$", first_out, flags=re.MULTILINE)
    assert _file_contents(tmp_path) == before
    assert roadmap_versions.accepted_head_path(plans_dir, "storefront").read_bytes() == head_before

    second = cmd_roadmap(_approve_argv_namespace(tmp_path, top, plans_dir, digest=digest))

    second_out = capsys.readouterr().out
    assert second == 0, second_out
    (seal_id,) = re.findall(r"^review seal: ([0-9a-f]{64})$", second_out, flags=re.MULTILINE)
    seal = roadmap_candidate_review.load_review_seal(plans_dir=plans_dir, slug="storefront", seal_id=seal_id)
    assert seal.decision == "structural-approval"
    assert seal.approved_candidate_version_id == top.version_id
    assert f"promoted version: {top.version_id}" in second_out
    head = roadmap_versions.load_accepted_version(plans_dir=plans_dir, slug="storefront")
    assert head.record.version_id == top.version_id
    before_head = roadmap_versions.accepted_head_path(plans_dir, "storefront").read_bytes()
    admission_path = roadmap_candidate_run.candidate_admission_path(plans_dir, "storefront")
    before_admission = admission_path.read_bytes() if admission_path.exists() else None

    repeated_rc = cmd_roadmap(
        _ns(
            tmp_path, slug="storefront", from_existing=None, plans_dir=plans_dir,
            promote_review_seal=seal_id,
        )
    )

    assert repeated_rc == 0
    assert capsys.readouterr().out == f"already promoted version: {top.version_id}\n"
    assert roadmap_versions.accepted_head_path(plans_dir, "storefront").read_bytes() == before_head
    assert (admission_path.read_bytes() if admission_path.exists() else None) == before_admission


def test_confirmed_approve_with_a_differing_digest_over_a_real_stack_refuses_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from tests.test_roadmap_candidate_run import (
        _green_gates,
        _store_stack,
    )

    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", _green_gates)
    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    before = _file_contents(tmp_path)
    another_stacks_digest = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug="storefront", candidate=structural
    ).digest

    rc = cmd_roadmap(_approve_argv_namespace(tmp_path, top, plans_dir, digest=another_stacks_digest))

    output = capsys.readouterr().out
    assert rc == 2
    assert "structural decision: approve refused" in output
    assert "review seal:" not in output and "promoted version:" not in output
    assert _file_contents(tmp_path) == before


# --------------------------------------------------------------------------
# The stack printout on edit, reject, and a structural-stack proposal
# --------------------------------------------------------------------------

_DECISION_CALLED = "<<library decision called>>"


def _stub_stack_views_by_candidate(
    monkeypatch: pytest.MonkeyPatch, views: dict[str, object]
) -> list[dict]:
    """Answer each stack-view build from `views`, keyed on the asked candidate's `version_id`.

    Records every call's keywords. A value that is an exception is raised instead of returned. An id
    with no entry fails the test, so a surface that builds a view for a candidate the test did not
    expect is caught rather than answered with somebody else's stack.
    """
    asked: list[dict] = []

    def build_candidate_stack_view(**kwargs: object):
        asked.append(kwargs)
        version_id = kwargs["candidate"].version_id
        if version_id not in views:
            pytest.fail(f"a stack view was built for the unexpected candidate {version_id}")
        answer = views[version_id]
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(roadmap_cmd, "build_candidate_stack_view", build_candidate_stack_view)
    return asked


def _decision_result(outcome: str, *, active_candidate=None, detail: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(outcome=outcome, active_candidate=active_candidate, seal=None, detail=detail)


def _two_hop_stack() -> tuple[SimpleNamespace, SimpleNamespace, roadmap_candidate_review.CandidateStackView]:
    """A structural `hop-a` under the presentation-only top `candidate-id`: the reported defect's shape."""
    lower = _stack_hop("hop-a", route=_STRUCTURAL)
    top = _stack_hop("candidate-id", route=_PRESENTATION_ONLY)
    return lower, top, _stack_view(lower, top)


def _run_edit_or_reject_over_stubbed_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, decision: str, candidate,
    views: dict[str, object], result: SimpleNamespace | None,
) -> tuple[int, list[dict]]:
    """Run `--decide-candidate` (edit or reject) for `candidate`, answering every stack-view build from `views`.

    `result` answers the library decision, which prints a marker so a test can order the printout
    against it; `None` means the decision must not be reached.
    """
    _admit_candidate(monkeypatch)
    _stub_candidate_stack_route(monkeypatch)
    asked = _stub_stack_views_by_candidate(monkeypatch, views)
    monkeypatch.setattr(roadmap_cmd, "load_stored_candidate_proposal", lambda **_kwargs: candidate)

    def decide(*_args: object, **_kwargs: object) -> SimpleNamespace:
        if result is None:
            pytest.fail("the library decision was reached")
        print(_DECISION_CALLED)
        return result

    monkeypatch.setattr(roadmap_cmd, "decide_structural_candidate", decide)
    monkeypatch.setattr(
        roadmap_cmd, "_cmd_roadmap_promote_review_seal_id",
        lambda *_args, **_kwargs: pytest.fail("edit and reject must not promote"),
    )
    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision=decision,
        candidate_correction="Change ownership." if decision == "edit" else None,
    ))
    return rc, asked


@pytest.mark.parametrize("decision", ("edit", "reject"))
def test_edit_and_reject_print_every_hop_of_the_stack_before_the_decision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, decision: str
) -> None:
    """The reported defect: the top-only disclosure hid the structural hop beneath a presentation-only
    top. The printout comes before the library call, so the operator sees what the decision covers
    before it is applied. The reject note is reject's alone: edit prints the stack without it."""
    _lower, top, view = _two_hop_stack()

    rc, asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision=decision, candidate=top, views={"candidate-id": view},
        result=_decision_result("failed", detail="backend failed"),
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 1
    assert (
        lines.index("stack hop 1 of 2: hop-a")
        < lines.index("candidate: candidate-id")
        < lines.index(_DECISION_CALLED)
        < lines.index(f"structural decision: {decision} failed")
    )
    assert len(asked) == 1 and asked[0]["candidate"] is top and asked[0]["slug"] == "my-roadmap"
    assert asked[0]["plans_dir"] == tmp_path.resolve() / "docs" / "implementation-plans"
    assert any(line.startswith("reject effect:") for line in lines) == (decision == "reject")


def test_reject_note_lists_every_dropped_hop_and_says_nothing_is_promoted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Reject releases the active candidate and drops the whole unpromoted stack, not only the top the
    operator named; the note says so in the terms the printout above it uses."""
    top = _stack_hop("candidate-id", route=_PRESENTATION_ONLY)
    view = _stack_view(
        _stack_hop("hop-a", route=_STRUCTURAL), _stack_hop("hop-b", route=_PRESENTATION_ONLY), top
    )

    rc, _asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="reject", candidate=top, views={"candidate-id": view},
        result=_decision_result("stored"),
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    (note,) = [line for line in lines if line.startswith("reject effect:")]
    assert '["hop-a","hop-b","candidate-id"]' in note
    assert "nothing is promoted" in note
    assert (
        lines.index("choices: approve, edit, reject")
        < lines.index(note)
        < lines.index(_DECISION_CALLED)
        < lines.index("structural decision: reject stored")
    )


@pytest.mark.parametrize("hop_count", (1, 3))
def test_reject_note_prints_for_a_single_hop_stack_too(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, hop_count: int
) -> None:
    """Deliberate: the note has no hop-count branch. Rejecting a one-hop stack drops its one hop, so
    the uniform note is true there as well, and a branch would be one more case to keep in step."""
    top = _stack_hop("candidate-id", route=_PRESENTATION_ONLY)
    lower = [_stack_hop(f"hop-{number}", route=_STRUCTURAL if number == 0 else _PRESENTATION_ONLY)
             for number in range(hop_count - 1)]
    hops = (*lower, top)

    rc, _asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="reject", candidate=top,
        views={"candidate-id": _stack_view(*hops)}, result=_decision_result("stored"),
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    (note,) = [line for line in lines if line.startswith("reject effect:")]
    assert json.dumps([hop.version_id for hop in hops], separators=(",", ":")) in note


@pytest.mark.parametrize(
    ("option", "resolver", "label"),
    (
        ("reject_candidate", "reject_candidate_review", "rejection"),
        ("discard_candidate", "discard_candidate_review", "discard"),
    ),
)
def test_standalone_reject_and_discard_candidate_print_neither_the_stack_printout_nor_the_reject_note(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, option: str, resolver: str, label: str
) -> None:
    """Carve-out from the plan's fence: neither flag asks for or confirms a structural approval, so
    each keeps its one-line result and reads no stack, even for a candidate that heads a structural one."""
    for name in ("build_candidate_stack_view", "candidate_stack_route"):
        monkeypatch.setattr(
            roadmap_cmd, name,
            lambda *_args, _name=name, **_kwargs: pytest.fail(f"{_name} ran for a standalone resolution"),
        )
    monkeypatch.setattr(
        roadmap_cmd, resolver, lambda *_args, **_kwargs: SimpleNamespace(outcome="stored", detail=None)
    )

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, **{option: "candidate-id"}))

    assert rc == 0
    assert capsys.readouterr().out == f"candidate {label}: stored\n"


def test_answered_route_output_carries_no_stack_printout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Owner decision 2: only the structural decision and a structural-stack proposal present a stack.
    The answered route's review, answer, and seal promotion refuse a stack that carries a structural
    hop, so their output keeps its own lines and none of them derives a stack or builds a view."""
    for name in ("build_candidate_stack_view", "candidate_stack_route"):
        monkeypatch.setattr(
            roadmap_cmd, name,
            lambda *_args, _name=name, **_kwargs: pytest.fail(f"{_name} ran on the answered route"),
        )
    reviewed = SimpleNamespace(
        outcome="stored",
        initial_candidate=SimpleNamespace(
            version_id="initial-candidate", content=SimpleNamespace(artifact_bytes=()),
            record=SimpleNamespace(predecessor_version_id="accepted-root"),
        ),
        question_inventory=SimpleNamespace(
            predecessor_diff={"changed_rows": ["entity-order"]},
            question=SimpleNamespace(
                question_id="question-id", anchor={"artifact_key": "domain"}, question_text="Use this name?"
            ),
        ),
        detail=None,
    )
    answered = SimpleNamespace(
        outcome="stored",
        initial_candidate=reviewed.initial_candidate,
        replacement=SimpleNamespace(
            version_id="replacement-id", content=SimpleNamespace(artifact_bytes=()),
            evidence=SimpleNamespace(predecessor_diff={"changed_rows": ["entity-order"]}),
        ),
        seal=SimpleNamespace(seal_id="seal-id"),
        detail=None,
    )
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_args, **_kwargs: reviewed)
    monkeypatch.setattr(roadmap_cmd, "answer_candidate_question", lambda *_args, **_kwargs: answered)

    @contextlib.contextmanager
    def guard(_plans_dir: Path, _slug: str):
        yield object()

    monkeypatch.setattr(roadmap_cmd, "roadmap_writer_guard", guard)
    monkeypatch.setattr(
        roadmap_cmd, "promote_review_seal",
        lambda **_kwargs: SimpleNamespace(version_id="promoted-id", outcome="promoted"),
    )

    assert cmd_roadmap(_ns(tmp_path, from_existing=None, review_candidate="initial-candidate")) == 0
    assert cmd_roadmap(_ns(
        tmp_path, from_existing=None, answer_question="question-id", answer="Use this name."
    )) == 0
    assert cmd_roadmap(_ns(tmp_path, from_existing=None, promote_review_seal="seal-id")) == 0

    output = capsys.readouterr().out
    assert "candidate review: stored" in output and "candidate answer: stored" in output
    assert "promoted version: promoted-id" in output
    for stack_only_text in (
        "candidate stack:", "stack hop ", "stack promotion effects:", "structural proposal:",
        "reject effect:", "stack digest:",
    ):
        assert stack_only_text not in output


def test_edit_result_prints_the_replacements_whole_stack_not_its_top_hop_alone(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The replacement the operator approves next keeps its lower structural hop, because an edit is
    sourced from the top's own source. Its view is built from the candidate the library returned, after
    the write; a view of the edited candidate would print a stack that no longer exists."""
    lower, top, view = _two_hop_stack()
    replacement = _stack_hop("replacement-id", route=_PRESENTATION_ONLY)

    rc, asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="edit", candidate=top,
        views={"candidate-id": view, "replacement-id": _stack_view(lower, replacement)},
        result=_decision_result("stored", active_candidate=replacement),
    )

    output = capsys.readouterr().out
    assert rc == 0
    assert len(asked) == 2 and asked[0]["candidate"] is top and asked[1]["candidate"] is replacement
    assert output.index(_DECISION_CALLED) < output.index("replacement: replacement-id\n")
    tail = output.split("replacement: replacement-id\n", 1)[1]
    assert "stack hop 1 of 2: hop-a" in tail
    assert "candidate: replacement-id" in tail
    assert "candidate-id" not in tail


@pytest.mark.parametrize("decision", ("edit", "reject"))
def test_edit_and_reject_refuse_before_any_output_and_any_decision_when_the_stack_view_cannot_be_built(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, decision: str
) -> None:
    """Nothing has been written yet, so this refuses like approve does: status 2 and no output. It
    never falls back to the top-only disclosure, which is the defect this printout ends, and an edit
    never spends its backend call."""
    top = _stack_hop("candidate-id", route=_STRUCTURAL)

    rc, asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision=decision, candidate=top,
        views={"candidate-id": roadmap_candidate_review.CandidateReviewError(
            "candidate stack is underivable: source is gone"
        )},
        result=None,
    )

    captured = capsys.readouterr()
    assert rc == 2
    assert captured.out == ""
    assert "candidate stack is underivable: source is gone" in captured.err
    assert len(asked) == 1


def test_stored_edit_with_an_unbuildable_replacement_view_reports_the_write_and_exits_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Pins the write-happened failure channel. The replacement is already published when its view
    fails, so the stored result stays visible; exit 0 would say the operator was shown what the write
    covers, and exit 2 would say nothing was written. The top-only disclosure is no substitute."""
    _lower, top, view = _two_hop_stack()
    replacement = _stack_hop("replacement-id", route=_STRUCTURAL)

    rc, _asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="edit", candidate=top,
        views={
            "candidate-id": view,
            "replacement-id": roadmap_candidate_review.CandidateReviewError(
                "candidate stack is underivable: replacement source is gone"
            ),
        },
        result=_decision_result("stored", active_candidate=replacement),
    )

    captured = capsys.readouterr()
    lines = captured.out.splitlines()
    assert rc == 1
    assert lines.index(_DECISION_CALLED) < lines.index("structural decision: edit stored")
    assert "replacement: replacement-id" in lines
    assert "candidate: replacement-id" not in lines
    assert captured.out.count("structural proposal: stored") == 1, "only the pre-decision printout"
    assert "candidate stack is underivable: replacement source is gone" in captured.err


def _run_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: SimpleNamespace, **arguments: object
) -> int:
    monkeypatch.setattr(roadmap_cmd, "run_initial_candidate_proposal", lambda *_args, **_kwargs: result)
    return cmd_roadmap(_ns(tmp_path, from_existing=None, **arguments))


@pytest.mark.parametrize(
    "arguments", ({"propose_candidate": True}, {"revise_feedback": True}),
    ids=("propose-candidate", "revise-feedback"),
)
def test_proposal_output_prints_the_stack_when_a_lower_hop_is_structural_though_the_candidates_own_route_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, arguments: dict[str, object]
) -> None:
    """The reported defect's shape on the proposal output: a presentation-only candidate over a
    structural hop printed no structural lines at all, because the check read its own route only."""
    _lower, top, view = _two_hop_stack()
    _stub_candidate_stack_route(monkeypatch, is_structural=True)
    _stub_stack_views_by_candidate(monkeypatch, {"candidate-id": view})

    rc = _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=top, detail=None), **arguments
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    diff_line = next(index for index, line in enumerate(lines) if line.startswith("predecessor diff:"))
    assert diff_line < lines.index("stack hop 1 of 2: hop-a")
    assert "structural proposal: stored" in lines
    (effects,) = [line for line in lines if line.startswith("stack promotion effects:")]
    assert effects.endswith('structural hops that invalidate enrolled seed state: ["hop-a"]')


def test_proposal_output_for_an_own_structural_candidate_keeps_the_disclosure_lines_through_the_printout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A structural candidate of its own still shows every disclosure line, now as the printout's last
    part rather than on its own, so `choices` stays the closing line."""
    top = _stack_hop("candidate-id", route=_STRUCTURAL)
    _stub_candidate_stack_route(monkeypatch, is_structural=True)
    _stub_stack_views_by_candidate(monkeypatch, {"candidate-id": _stack_view(top)})

    rc = _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=top, detail=None),
        propose_candidate=True,
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert lines.index("candidate stack: accepted root root-id; hops above it: 1") < lines.index(
        "structural proposal: stored"
    )
    assert lines[-1] == "choices: approve, edit, reject"


@pytest.mark.parametrize("case", ("all-presentation-stack", "route-less-candidate", "no-recorded-root"))
def test_proposal_output_keeps_todays_output_when_the_stack_has_no_structural_hop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, case: str
) -> None:
    """Deliberate carve-out: a stack with no structural hop prints the four proposal lines and nothing
    more, and never builds a view, so it gains neither output nor a new way to fail beyond an unreadable
    hop, which the derivation refuses (see the stored-proposal failure test). `no-recorded-root`
    is selector-era evidence, whose stack is empty by definition and is answered without a stub."""
    candidate = _stored_structural_cli_candidate()
    if case == "all-presentation-stack":
        candidate.evidence.operation_classification = _PRESENTATION_ONLY
        _stub_candidate_stack_route(monkeypatch, is_structural=False)
    elif case == "route-less-candidate":
        candidate.evidence.operation_classification = None
        _stub_candidate_stack_route(monkeypatch, is_structural=False)
    else:
        candidate.evidence.operation_classification = None
        candidate.evidence.root_version_id = None
    _stub_stack_views_by_candidate(monkeypatch, {})

    rc = _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=candidate, detail=None),
        propose_candidate=True,
    )

    lines = capsys.readouterr().out.splitlines()
    assert rc == 0
    assert lines[:3] == ["candidate proposal: stored", "candidate: candidate-id", "predecessor: source-id"]
    # The four proposal lines are unchanged; the narrative evidence block is the one addition.
    assert len(lines) == 5 and lines[3].startswith("predecessor diff: ")
    assert lines[4] == "narrative evidence: none"


def test_proposal_without_a_stored_candidate_never_derives_a_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    asked = _stub_candidate_stack_route(monkeypatch)
    _stub_stack_views_by_candidate(monkeypatch, {})

    rc = _run_proposal(
        tmp_path, monkeypatch,
        SimpleNamespace(outcome="refused", candidate=None, detail="admission refused"),
        propose_candidate=True,
    )

    assert rc == 2
    assert asked == []
    assert capsys.readouterr().out == "candidate proposal: refused\nreason: admission refused\n"


def test_proposal_stack_is_derived_from_the_candidates_own_id_and_recorded_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The stack is the candidate's own unpromoted ancestry down to the root its evidence records, so
    the proposal must not ask about the accepted head or the admission pointer: neither says what this
    candidate sits on once another candidate is admitted or promoted."""
    _lower, top, view = _two_hop_stack()
    asked = _stub_candidate_stack_route(monkeypatch, is_structural=True)
    _stub_stack_views_by_candidate(monkeypatch, {"candidate-id": view})

    _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=top, detail=None),
        propose_candidate=True,
    )

    assert asked == [{
        "plans_dir": tmp_path.resolve() / "docs" / "implementation-plans",
        "slug": "my-roadmap",
        "tip_version_id": "candidate-id",
        "root_version_id": top.evidence.root_version_id,
    }]


@pytest.mark.parametrize("failing_step", ("derivation", "view-build"))
def test_proposal_stack_failure_after_a_stored_proposal_prints_the_stored_lines_and_exits_incomplete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, failing_step: str
) -> None:
    """The proposal is stored before its stack is read, so a failure reads as incomplete (1), not as a
    refusal (2) and not as success. The candidate is structural of its own, so the top-only disclosure
    the old check would have printed is what must stay absent."""
    candidate = _stored_structural_cli_candidate()
    if failing_step == "derivation":
        message = "candidate source ancestry is unreadable"
        _stub_candidate_stack_route(
            monkeypatch, error=roadmap_candidate_run.CandidateProposalError(message)
        )
        _stub_stack_views_by_candidate(monkeypatch, {})
    else:
        message = "candidate stack is underivable: source is gone"
        _stub_candidate_stack_route(monkeypatch, is_structural=True)
        _stub_stack_views_by_candidate(
            monkeypatch, {"candidate-id": roadmap_candidate_review.CandidateReviewError(message)}
        )

    rc = _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=candidate, detail=None),
        propose_candidate=True,
    )

    captured = capsys.readouterr()
    assert rc == 1
    assert "candidate proposal: stored" in captured.out
    assert "predecessor diff:" in captured.out
    assert "structural proposal:" not in captured.out and "candidate stack:" not in captured.out
    assert message in captured.err


def test_reject_over_a_real_stack_prints_every_hop_and_the_drop_note_before_releasing_the_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Over a real presentation-only top of a structural hop: both hops print oldest first, the note
    names both, all of it before the decision result, and the digest stays out because a reject has
    no confirm. The pointer is released and both hops stay stored."""
    from tests.test_roadmap_candidate_run import _store_stack

    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    digest = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug="storefront", candidate=top
    ).digest

    rc = cmd_roadmap(_ns(
        tmp_path, slug="storefront", plans_dir=plans_dir, from_existing=None,
        decide_candidate=top.version_id, candidate_decision="reject",
    ))

    output = capsys.readouterr().out
    lines = output.splitlines()
    assert rc == 0, output
    (note,) = [line for line in lines if line.startswith("reject effect:")]
    assert structural.version_id in note and top.version_id in note
    assert (
        lines.index(f"stack hop 1 of 2: {structural.version_id}")
        < lines.index(f"candidate: {top.version_id}")
        < lines.index(note)
        < lines.index("structural decision: reject stored")
    )
    assert digest not in output
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug="storefront")
    assert admission is not None and admission.active_candidate_version_id is None
    for hop in (structural, top):
        stored = roadmap_candidate_run.load_stored_candidate_proposal(
            plans_dir=plans_dir, slug="storefront", candidate_version_id=hop.version_id
        )
        assert stored.version_id == hop.version_id


def test_proposal_output_over_a_real_stack_with_a_structural_lower_hop_prints_the_whole_stack(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Real stored records under a stubbed runner: the derivation, builder, and printout are all real.
    The top's own route is presentation-only, so the old own-route check would have printed nothing
    structural; the stack shows the structural hop beneath it and no digest."""
    from tests.test_roadmap_candidate_run import _store_stack

    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    plans_dir = tmp_path / "plans"
    assert top.evidence.operation_classification is _PRESENTATION_ONLY
    digest = roadmap_candidate_review.build_candidate_stack_view(
        plans_dir=plans_dir, slug="storefront", candidate=top
    ).digest

    rc = _run_proposal(
        tmp_path, monkeypatch, SimpleNamespace(outcome="stored", candidate=top, detail=None),
        slug="storefront", plans_dir=plans_dir, propose_candidate=True,
    )

    output = capsys.readouterr().out
    lines = output.splitlines()
    assert rc == 0, output
    assert f"stack hop 1 of 2: {structural.version_id}" in lines
    assert f"candidate: {top.version_id}" in lines
    assert 'stored route: "structural"' in _hop_sections(lines)[structural.version_id]
    (effects,) = [line for line in lines if line.startswith("stack promotion effects:")]
    assert effects.endswith(f'structural hops that invalidate enrolled seed state: ["{structural.version_id}"]')
    assert digest not in output


def test_edit_over_a_real_stack_prints_the_replacements_stack_built_from_the_stored_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The replacement is sourced from the structural hop, not from the top that was edited, so its
    stack is that hop plus itself. After `replacement:` the output holds the structural hop and the
    replacement but not the edited top: a view built from the candidate the operator named would still
    list it. Only the real library shows which candidate it stores."""
    from tests.test_roadmap_candidate_run import _store_stack

    _root_version, (structural, top) = _store_stack(
        tmp_path, monkeypatch, ("structural", "presentation-only")
    )
    reply = {
        "operations": [], "responses": [],
        "derived_feedback": [{"context_id": "derived-edit", "content": "Edited."}],
    }

    rc = cmd_roadmap(
        _ns(
            tmp_path, slug="storefront", plans_dir=tmp_path / "plans", from_existing=None,
            decide_candidate=top.version_id, candidate_decision="edit",
            candidate_correction="Tighten the wording.",
        ),
        invoker=lambda _prompt: (0, json.dumps(reply)),
    )

    output = capsys.readouterr().out
    assert rc == 0, output
    (replacement_id,) = re.findall(r"^replacement: ([0-9a-f]{64})$", output, flags=re.MULTILINE)
    assert replacement_id != top.version_id
    tail = output.split(f"replacement: {replacement_id}\n", 1)[1]
    assert f"stack hop 1 of 2: {structural.version_id}" in tail
    assert f"candidate: {replacement_id}" in tail
    assert top.version_id not in tail


@pytest.mark.parametrize(
    "outcome, expected_status",
    (("stored", 0), ("response-rejected", 1), ("failed", 1), ("refused", 2)),
)
def test_candidate_model_route_outcomes_map_to_existing_cli_exits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, outcome: str, expected_status: int
) -> None:
    monkeypatch.setattr(
        roadmap_cmd,
        "run_initial_candidate_proposal",
        lambda *_args, **_kwargs: SimpleNamespace(
            outcome=outcome, candidate=None, detail="closed outcome"
        ),
    )

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, propose_candidate=True)
    ) == expected_status


def _candidate_lifecycle_snapshot() -> SimpleNamespace:
    """Build the complete accepted-root input for the CLI lifecycle proof."""
    domain = DomainArtifact(
        entities=(
            EntityRow(
                "entity-order",
                "Order",
                (FieldRow("customer", FieldType.REFERENCE, "entity-customer"),),
            ),
            EntityRow("entity-customer", "Customer", ()),
        ),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="domain\n",
        feedback=(),
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
    artifact_texts = tuple(
        stage.render(artifact)
        for stage, artifact in zip(
            roadmap.STAGES, (domain, constraints, components, plans), strict=True
        )
    )
    brief_bytes = b"Recorded brief\n"
    return SimpleNamespace(
        brief_bytes=brief_bytes,
        brief_raw_digest=hashlib.sha256(brief_bytes).hexdigest(),
        artifact_keys=tuple(stage.artifact_key for stage in roadmap.STAGES),
        artifact_texts=artifact_texts,
        artifacts=(domain, constraints, components, plans),
        artifact_digests=tuple(
            hashlib.sha256(text.encode("utf-8")).hexdigest() for text in artifact_texts
        ),
    )


def _candidate_delta_response() -> str:
    return json.dumps(
        {
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
            ],
            "responses": [
                {
                    "item_id": "feedback-order",
                    "response": "Renamed the order entity to the customer-facing spelling.",
                }
            ],
            "derived_feedback": [],
        }
    )


def _candidate_question_response() -> str:
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


def _enrolled_roadmap_with_a_proposed_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, *, reply: str | None = None
) -> tuple[Path, str]:
    """Enroll a roadmap, seed one eligible reviewer item, and store a batch candidate through the CLI.

    ``reply`` is the first batch's canned model reply; the default is the presentation-only rename.
    """
    plans_dir = tmp_path / "docs" / "implementation-plans"
    plans_dir.mkdir(parents=True)
    snapshot = _candidate_lifecycle_snapshot()

    def green_gates(_evidence, *, stages=roadmap.STAGES):
        return tuple(RoadmapGateOutcome(stage, ()) for stage in stages)

    monkeypatch.setattr(roadmap_candidate, "check_complete_roadmap_gates", green_gates)
    monkeypatch.setattr(roadmap_version_promotion, "check_complete_roadmap_gates", green_gates)

    # Publish the root version the way the first stage run does (version, ledger, head last).
    with roadmap._roadmap_writer_owner(plans_dir, "my-roadmap") as writer_token:
        roadmap._publish_root_version(
            slug="my-roadmap",
            plans_dir=plans_dir,
            writer_token=writer_token,
            brief_bytes=snapshot.brief_bytes,
            stages=roadmap.STAGES,
            stage_texts={
                stage.number: text
                for stage, text in zip(roadmap.STAGES, snapshot.artifact_texts, strict=True)
            },
        )

    # A first-run root starts with an empty ledger; seed one eligible
    # reviewer-created item so the selector-free batch below has real eligible
    # work to find.
    accepted = load_accepted_version(plans_dir=plans_dir, slug="my-roadmap")
    assert accepted is not None
    target = LedgerTarget(artifact_key="domain", kind=FeedbackTargetKind.ROW, row_id="entity-order")
    item = ReviewerFeedbackItem(
        item_id="feedback-order",
        target=target,
        request="Use the customer-facing order name.",
        state=ReviewerItemState.OPEN,
        submitted_against_version_id=accepted.record.version_id,
        target_fingerprint=target_fingerprint(accepted, target),
    )
    ledger = RoadmapFeedbackLedger(
        schema_version=LEDGER_SCHEMA_VERSION,
        roadmap_slug="my-roadmap",
        ledger_state=LedgerState.LEDGER_NATIVE,
        reviewer_feedback_groups=(
            ReviewerFeedbackGroup(predecessor_version_id=accepted.record.version_id, items=(item,)),
        ),
        derived_context=(),
    )
    roadmap_feedback_ledger_path(plans_dir, "my-roadmap").write_bytes(render_ledger(ledger))

    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            plans_dir=plans_dir,
            propose_candidate=True,
        ),
        invoker=lambda _prompt: (0, _candidate_delta_response() if reply is None else reply),
    ) == 0
    proposal_output = capsys.readouterr().out
    initial_id = re.search(r"candidate: ([0-9a-f]{64})", proposal_output)
    assert initial_id is not None
    return plans_dir, initial_id.group(1)


def test_cli_candidate_lifecycle_promotes_only_the_reviewer_displayed_answer_incorporated_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Run the CLI lifecycle through its real accepted-head reader with canned replies."""
    plans_dir, initial_id = _enrolled_roadmap_with_a_proposed_candidate(tmp_path, monkeypatch, capsys)

    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            plans_dir=plans_dir,
            review_candidate=initial_id,
        ),
        invoker=lambda _prompt: (0, _candidate_question_response()),
    ) == 0
    review_output = capsys.readouterr().out
    question_id = re.search(r"question: ([0-9a-f]{64})", review_output)
    assert question_id is not None
    assert "Should the customer-facing name use this exact spelling?" in review_output

    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            plans_dir=plans_dir,
            answer_question=question_id.group(1),
            answer="Use the conventional spelling.",
        ),
        invoker=lambda _prompt: (0, _candidate_delta_response()),
    ) == 0
    answer_output = capsys.readouterr().out
    replacement_id = re.search(r"replacement: ([0-9a-f]{64})", answer_output)
    seal_id = re.search(r"review seal: ([0-9a-f]{64})", answer_output)
    assert replacement_id is not None
    assert seal_id is not None
    version_root = version_namespace_path(plans_dir, "my-roadmap")
    # Promotion rewrites exactly two files: the accepted-head selector and the
    # active-candidate pointer it releases. Every stored version and record stays.
    rewritten_by_promotion = {
        accepted_head_path(plans_dir, "my-roadmap"),
        roadmap_candidate_run.candidate_admission_path(plans_dir, "my-roadmap"),
    }

    def stored_bytes() -> dict[Path, bytes]:
        return {
            path.relative_to(version_root): path.read_bytes()
            for path in version_root.rglob("*")
            if path.is_file() and path not in rewritten_by_promotion
        }

    stored_before_promotion = stored_bytes()
    assert any(
        replacement_id.group(1) in path.parts for path in stored_before_promotion
    ), "the snapshot must hold the replacement's stored version, or it asserts nothing"

    assert cmd_roadmap(
        _ns(
            tmp_path,
            from_existing=None,
            plans_dir=plans_dir,
            promote_review_seal=seal_id.group(1),
        )
    ) == 0
    assert replacement_id.group(1) in capsys.readouterr().out
    assert stored_bytes() == stored_before_promotion
    accepted_after = load_accepted_version(plans_dir=plans_dir, slug="my-roadmap")
    assert accepted_after is not None
    assert accepted_after.record.version_id == replacement_id.group(1)

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, plans_dir=plans_dir, view="walk")
    ) == 0
    assert "Customer order" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("option", "label", "reason"),
    (
        ("reject_candidate", "rejection", "rejected"),
        ("discard_candidate", "discard", "discarded"),
    ),
)
def test_cli_rejection_and_discard_release_only_the_named_active_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, option: str, label: str, reason: str
) -> None:
    plans_dir, candidate_id = _enrolled_roadmap_with_a_proposed_candidate(tmp_path, monkeypatch, capsys)
    head_before = accepted_head_path(plans_dir, "my-roadmap").read_bytes()

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, plans_dir=plans_dir, **{option: candidate_id}))

    assert rc == 0
    assert f"candidate {label}: stored" in capsys.readouterr().out
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug="my-roadmap")
    assert admission is not None and admission.active_candidate_version_id is None
    record = json.loads(
        roadmap_candidate_run.terminal_resolution_path(plans_dir, "my-roadmap", candidate_id).read_text(
            encoding="utf-8"
        )
    )
    assert (record["reason"], record["candidate_version_id"]) == (reason, candidate_id)
    assert accepted_head_path(plans_dir, "my-roadmap").read_bytes() == head_before


@pytest.mark.parametrize("option", ("reject_candidate", "discard_candidate"))
def test_cli_release_of_a_candidate_that_is_not_active_refuses_and_changes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, option: str
) -> None:
    plans_dir, candidate_id = _enrolled_roadmap_with_a_proposed_candidate(tmp_path, monkeypatch, capsys)
    pointer = roadmap_candidate_run.candidate_admission_path(plans_dir, "my-roadmap")
    pointer_before = pointer.read_bytes()

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, plans_dir=plans_dir, **{option: "9" * 64}))

    out = capsys.readouterr().out
    assert rc == 2
    assert "refused" in out
    assert re.search(r"^reason: \S.*$", out, re.MULTILINE), "a refusal names why, as its sibling commands do"
    assert pointer.read_bytes() == pointer_before
    assert not roadmap_candidate_run.terminal_resolution_path(plans_dir, "my-roadmap", candidate_id).exists()


def _structural_candidate_delta_response() -> str:
    """A field rename (structural) that also files derived context, so a second batch has eligible work
    and reaches the runner instead of ending as `no eligible work`."""
    return json.dumps(
        {
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
                        "fields": [{"name": "buyer", "type": "reference", "entity_id": "entity-customer"}],
                    },
                }
            ],
            "responses": [{"item_id": "feedback-order", "response": "Use buyer."}],
            "derived_feedback": [{"context_id": "derived-one", "content": "Check naming."}],
        }
    )


def test_operator_walk_stacks_a_batch_under_a_structural_candidate_and_reaches_the_head_only_by_confirmed_approval(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """The operator's whole sequence over the real orchestrator, with only the model replies canned: a
    batch is proposed under a still-undecided structural candidate, its output presents both hops, the
    answered route refuses the stack, an unconfirmed approve prints the digest and writes nothing, and the
    approve that carries that digest promotes the top. Every seam here lies between two invocations, so
    no test that stubs a layer can show it."""
    plans_dir, structural_id = _enrolled_roadmap_with_a_proposed_candidate(
        tmp_path, monkeypatch, capsys, reply=_structural_candidate_delta_response()
    )
    structural = roadmap_candidate_run.load_stored_candidate_proposal(
        plans_dir=plans_dir, slug="my-roadmap", candidate_version_id=structural_id
    )
    # A fixture that stored a presentation-only first hop would leave the whole walk proving nothing.
    assert structural.evidence.operation_classification is _STRUCTURAL
    presentation_only_reply = json.dumps(
        {
            "operations": [],
            "responses": [],
            "derived_feedback": [{"context_id": "derived-two", "content": "Check naming again."}],
        }
    )

    rc = cmd_roadmap(
        _ns(tmp_path, from_existing=None, plans_dir=plans_dir, propose_candidate=True),
        invoker=lambda _prompt: (0, presentation_only_reply),
    )

    proposal_output = capsys.readouterr().out
    assert rc == 0, proposal_output
    top_match = re.search(r"^candidate: ([0-9a-f]{64})$", proposal_output, flags=re.MULTILINE)
    assert top_match is not None
    top_id = top_match.group(1)
    assert top_id != structural_id
    proposal_lines = proposal_output.splitlines()
    assert f"stack hop 1 of 2: {structural_id}" in proposal_lines
    assert f"candidate: {top_id}" in proposal_lines
    admission = roadmap_candidate_run.load_candidate_admission(plans_dir=plans_dir, slug="my-roadmap")
    assert admission is not None and admission.active_candidate_version_id == top_id
    head_before = accepted_head_path(plans_dir, "my-roadmap").read_bytes()

    review_rc = cmd_roadmap(
        _ns(tmp_path, from_existing=None, plans_dir=plans_dir, review_candidate=top_id),
        invoker=lambda _prompt: pytest.fail("the answered route reached a backend for a structural stack"),
    )

    review_output = capsys.readouterr().out
    assert review_rc == 2
    assert "--decide-candidate" in review_output
    before_unconfirmed = _file_contents(tmp_path)

    unconfirmed_rc = cmd_roadmap(
        _ns(
            tmp_path, from_existing=None, plans_dir=plans_dir,
            decide_candidate=top_id, candidate_decision="approve",
        )
    )

    unconfirmed_output = capsys.readouterr().out
    assert unconfirmed_rc == 2
    (digest,) = re.findall(r"^stack digest: ([0-9a-f]{64})$", unconfirmed_output, flags=re.MULTILINE)
    assert "promoted version:" not in unconfirmed_output
    assert _file_contents(tmp_path) == before_unconfirmed
    assert accepted_head_path(plans_dir, "my-roadmap").read_bytes() == head_before

    confirmed_rc = cmd_roadmap(
        _ns(
            tmp_path, from_existing=None, plans_dir=plans_dir,
            decide_candidate=top_id, candidate_decision="approve", confirm_stack_digest=digest,
        )
    )

    confirmed_output = capsys.readouterr().out
    assert confirmed_rc == 0, confirmed_output
    assert f"promoted version: {top_id}" in confirmed_output
    head = load_accepted_version(plans_dir=plans_dir, slug="my-roadmap")
    assert head is not None and head.record.version_id == top_id


# --------------------------------------------------------------------------
# Argparse wiring
# --------------------------------------------------------------------------


class TestArgparseWiring:
    def test_register_returns_the_roadmap_dispatch_entry(self) -> None:
        _, subparsers = _roadmap_parser()
        handlers = register(subparsers)
        assert handlers == {"roadmap": cmd_roadmap}
        assert list(subparsers.choices) == ["roadmap"]

    def test_slug_positional_is_required(self) -> None:
        with pytest.raises(SystemExit):
            _parse("roadmap", "--from-existing", "concept.md")

    def test_from_existing_not_required_with_apply(self) -> None:
        args = _parse("roadmap", "my-roadmap", "--apply")
        assert args.apply is True
        assert args.from_existing is None

    def test_from_stage_flag_is_rejected_as_unknown(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            _parse("roadmap", "my-roadmap", "--from-existing", "c.md", "--from-stage", "2")

        assert excinfo.value.code == 2
        assert "unrecognized arguments: --from-stage" in capsys.readouterr().err

    def test_confirm_brief_rebind_flag_is_rejected_as_unknown(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            _parse("roadmap", "my-roadmap", "--confirm-brief-rebind")

        assert excinfo.value.code == 2
        assert "unrecognized arguments: --confirm-brief-rebind" in capsys.readouterr().err

    def test_help_documents_from_existing_and_apply(self) -> None:
        help_text = _roadmap_help()
        assert "--from-existing" in help_text
        assert "--apply" in help_text

    def test_help_text_names_neither_removed_flag(self) -> None:
        help_text = _roadmap_help()

        assert "--from-stage" not in help_text
        assert "--confirm-brief-rebind" not in help_text

    def test_help_documents_apply_and_y(self) -> None:
        help_text = _roadmap_help()
        assert "--apply" in help_text
        assert "-y" in help_text or "--yes" in help_text
        assert "second opt-in" in help_text

    def test_broad_mode_options_reach_occurrence_preserving_namespace(self) -> None:
        args = _parse(
            "roadmap",
            "my-roadmap",
            "--apply",
            "--refresh-seeds",
            "--accept-seed",
            "plan-a",
            "--materialize",
            "plan-b",
            "--view",
            "summary",
        )
        assert args._roadmap_mode_occurrences == (
            ("--apply", True),
            ("--refresh-seeds", True),
            ("--accept-seed", "plan-a"),
            ("--materialize", "plan-b"),
            ("--view", "summary"),
        )
        assert args.apply is True
        assert args.refresh_seeds is True
        assert args.accept_seed == "plan-a"
        assert args.materialize == "plan-b"
        assert args.view == "summary"

    def test_repeated_current_broad_option_keeps_current_final_value(self) -> None:
        args = _parse(
            "roadmap",
            "my-roadmap",
            "--accept-seed",
            "plan-a",
            "--accept-seed",
            "plan-b",
        )
        assert args.accept_seed == "plan-b"
        assert args._roadmap_mode_occurrences == (
            ("--accept-seed", "plan-a"),
            ("--accept-seed", "plan-b"),
        )

    def test_repeated_ordinary_view_preserves_each_occurrence_and_current_final_value(
        self,
    ) -> None:
        args = _parse(
            "roadmap",
            "my-roadmap",
            "--view",
            "walk",
            "--view",
            "ledger",
        )
        assert args.view == "ledger"
        assert args._roadmap_mode_occurrences == (
            ("--view", "walk"),
            ("--view", "ledger"),
        )

    def test_accept_seed_parses_and_defaults_to_none(self) -> None:
        assert _parse("roadmap", "my-roadmap").accept_seed is None
        assert (
            _parse("roadmap", "my-roadmap", "--accept-seed", "plan-a").accept_seed
            == "plan-a"
        )

    def test_help_documents_accept_seed(self) -> None:
        assert "--accept-seed" in _roadmap_help()

    def test_materialize_distinguishes_an_absent_flag_from_all_and_one_plan(self) -> None:
        assert _parse("roadmap", "my-roadmap").materialize is None
        assert (
            _parse("roadmap", "my-roadmap", "--materialize").materialize
            is roadmap_cmd._MATERIALIZE_ALL
        )
        assert (
            _parse("roadmap", "my-roadmap", "--materialize", "plan-a").materialize
            == "plan-a"
        )

    def test_help_documents_materialize(self) -> None:
        assert "--materialize" in _roadmap_help()

    def test_stage_run_help_has_no_iterate_flag(self) -> None:
        help_text = _roadmap_help()
        assert "--iterate" not in help_text

    def test_view_choices_include_the_compact_summary_and_seed_states(self) -> None:
        for choice in ("summary", "walk", "ledger", "index", "seeds"):
            args = _parse("roadmap", "my-roadmap", "--view", choice)
            assert args.view == choice
        with pytest.raises(SystemExit):
            _parse("roadmap", "my-roadmap", "--view", "bogus")

    def test_view_does_not_require_from_existing(self) -> None:
        args = _parse("roadmap", "my-roadmap", "--view", "ledger")
        assert args.view == "ledger"
        assert args.from_existing is None

    def test_mode_choices_are_current_review(self) -> None:
        current = _parse(
            "roadmap", "my-roadmap", "--view", "walk", "--mode", "current"
        )
        assert current.mode == "current"
        review = _parse(
            "roadmap", "my-roadmap", "--view", "walk", "--mode", "review"
        )
        assert review.mode == "review"
        with pytest.raises(SystemExit):
            _parse("roadmap", "my-roadmap", "--view", "walk", "--mode", "bogus")

    def test_mode_argparse_default_is_none(self) -> None:
        args = _parse("roadmap", "my-roadmap", "--view", "walk")
        assert args.mode is None

    def test_id_argparse_default_is_none(self) -> None:
        args = _parse("roadmap", "my-roadmap", "--view", "index")
        assert args.id is None

    def test_help_documents_view_mode_and_id(self) -> None:
        help_text = _roadmap_help()
        assert "--view" in help_text
        assert "--mode" in help_text
        assert "--id" in help_text

    @pytest.mark.parametrize(
        "argv",
        (
            ("--escalate-feedback", "domain:feedback-a"),
            ("--escalation-reason", "prose"),
            ("--analyze-escalation", "f"),
            ("--rewrite-structural", "f"),
            ("--rewrite-analysis", "f"),
        ),
        ids=(
            "escalate-feedback",
            "escalation-reason",
            "analyze-escalation",
            "rewrite-structural",
            "rewrite-analysis",
        ),
    )
    def test_removed_roadmap_flags_are_rejected_by_the_parser(
        self, monkeypatch: pytest.MonkeyPatch, capsys, argv: tuple[str, ...]
    ) -> None:
        """The escalation, impact-analysis, and structural-rewrite flags no longer exist.

        argparse must stop at parse time (usage error, nonzero), so no
        orchestrator or handler is ever reached.
        """

        def unexpected(*_args, **_kwargs):
            pytest.fail("a removed flag must not reach any orchestrator")

        for name in ("run_roadmap", "_cmd_roadmap_view"):
            monkeypatch.setattr(roadmap_cmd, name, unexpected)

        with pytest.raises(SystemExit) as excinfo:
            _parse("roadmap", "my-roadmap", *argv)

        assert excinfo.value.code not in (0, None)
        assert "unrecognized arguments" in capsys.readouterr().err

    @pytest.mark.parametrize("view", ("escalations", "impact-analyses"))
    def test_removed_views_are_not_accepted_view_choices(
        self, capsys, view: str
    ) -> None:
        with pytest.raises(SystemExit) as excinfo:
            _parse("roadmap", "my-roadmap", "--view", view)

        assert excinfo.value.code == 2
        assert "invalid choice" in capsys.readouterr().err

    @pytest.mark.parametrize(
        "view", ("summary", "walk", "ledger", "index", "seeds", "html")
    )
    def test_remaining_views_still_parse(self, view: str) -> None:
        args = _parse("roadmap", "my-roadmap", "--view", view)

        assert args.view == view
        assert args._roadmap_mode_occurrences == (("--view", view),)

    def test_view_companion_option_rejection_is_unchanged_for_remaining_views(
        self, tmp_path: Path, capsys
    ) -> None:
        """Companion rejection keeps its usage code and wording after the view list shrank.

        ``--mode`` / ``--id`` without a view and ``--id`` beside a view other
        than ``index`` stay usage errors (status 2) naming the missing or
        mismatched flag.
        """
        assert cmd_roadmap(_ns(tmp_path, from_existing=None, mode="review")) == 2
        err = capsys.readouterr().err
        assert "--mode" in err
        assert "--view" in err

        assert cmd_roadmap(_ns(tmp_path, from_existing=None, id="entity-1")) == 2
        err = capsys.readouterr().err
        assert "--id" in err
        assert "--view" in err

        for view in ("summary", "walk", "ledger", "seeds"):
            assert (
                cmd_roadmap(_ns(tmp_path, from_existing=None, view=view, id="entity-1"))
                == 2
            )
            assert "--id is only valid with --view index" in capsys.readouterr().err

    def test_decision_settlement_options_preserve_absent_single_and_repeated_occurrences(
        self, tmp_path: Path
    ) -> None:
        absent = _parse("roadmap", "my-roadmap")
        single = _parse(
            "roadmap",
            "my-roadmap",
            "--settle-decision",
            "domain:decision-a",
            "--settlement-evidence",
            "domain:feedback-a",
            "--confirm-decision-settlement",
        )
        repeated = _parse(
            "roadmap",
            "my-roadmap",
            "--settle-decision",
            "domain:decision-a",
            "--settle-decision",
            "domain:decision-b",
            "--settlement-evidence",
            "domain:feedback-a",
            "--settlement-evidence",
            "domain:feedback-b",
            "--confirm-decision-settlement",
            "--confirm-decision-settlement",
        )

        assert absent._settle_decision_occurrences == ()
        assert absent._settlement_evidence_occurrences == ()
        assert absent._confirm_decision_settlement_occurrences == ()
        assert absent.confirm_decision_settlement is None
        assert single._settle_decision_occurrences == ("domain:decision-a",)
        assert single._settlement_evidence_occurrences == ("domain:feedback-a",)
        assert single._confirm_decision_settlement_occurrences == (True,)
        assert repeated.settle_decision == "domain:decision-b"
        assert repeated.settlement_evidence == "domain:feedback-b"
        assert repeated.confirm_decision_settlement is True
        assert repeated._settle_decision_occurrences == (
            "domain:decision-a",
            "domain:decision-b",
        )
        assert repeated._settlement_evidence_occurrences == (
            "domain:feedback-a",
            "domain:feedback-b",
        )
        assert repeated._confirm_decision_settlement_occurrences == (True, True)
        for name, value in (
            ("settle_decision", "domain:decision-a"),
            ("settlement_evidence", "domain:feedback-a"),
            ("confirm_decision_settlement", True),
        ):
            assert roadmap_cmd._option_occurrences(
                _ns(tmp_path, **{name: value}), name
            ) == (value,)

    def test_decision_settlement_triple_is_not_a_broad_mode(self) -> None:
        args = _parse(
            "roadmap",
            "my-roadmap",
            "--settle-decision",
            "domain:decision-a",
            "--settlement-evidence",
            "domain:feedback-a",
            "--confirm-decision-settlement",
        )

        assert args._roadmap_mode_occurrences == ()

    def test_decision_settlement_help_documents_the_exact_confirmed_triple(self) -> None:
        help_text = _roadmap_help()

        assert "--settle-decision" in help_text
        assert "--settlement-evidence" in help_text
        assert "--confirm-decision-settlement" in help_text
        assert "Required exactly once" in help_text
        # argparse wraps help text, so compare with whitespace collapsed.
        assert "-y is not confirmation" in " ".join(help_text.split())


@pytest.mark.parametrize("first, second", tuple(combinations(_BROAD_MODE_ARGUMENTS, 2)))
def test_nonreceipt_broad_mode_conflicts_keep_current_usage_output_and_status(
    first: str, second: str, capsys
) -> None:
    """Keep the pre-extraction grouped usage line and ordered conflict diagnostic.

    Pinned against a frozen literal, not the live parser's own
    ``format_usage()``: comparing against the same parser being tested would
    pass even if the extraction silently dropped the ``--apply | ...`` group.
    """
    args = _parse(
        "roadmap",
        "my-roadmap",
        *_BROAD_MODE_ARGUMENTS[first],
        *_BROAD_MODE_ARGUMENTS[second],
    )

    assert cmd_roadmap(args) == 2

    assert capsys.readouterr().err.endswith(
        f"plan-tool roadmap: error: argument {second}: not allowed with argument {first}\n"
    )


def test_nonreceipt_broad_mode_conflict_has_no_path_or_orchestrator_side_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reject incompatible broad modes before resolving paths or dispatching work."""
    args = _parse("roadmap", "my-roadmap", "--apply", "--view", "summary")

    def unexpected(*_args, **_kwargs):
        pytest.fail("broad-mode rejection must not resolve or dispatch work")

    for name in (
        "_resolve_cmd_repo_root",
        "resolve_explicit_plans_dir",
        "resolve_output_dir",
        "_cmd_roadmap_apply",
        "_cmd_roadmap_refresh_seeds",
        "_cmd_roadmap_accept_seed",
        "_cmd_roadmap_materialize",
        "_cmd_roadmap_view",
        "run_roadmap",
    ):
        monkeypatch.setattr(roadmap_cmd, name, unexpected)

    assert cmd_roadmap(args) == 2


def test_nonreceipt_broad_mode_conflict_falls_back_cleanly_without_argparse_hook(
    monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A future argparse layout change remains a usage error, never a crash."""
    args = _parse("roadmap", "my-roadmap", "--apply", "--view", "summary")
    parser = args._roadmap_mode_parser
    monkeypatch.setattr(parser, "add_mutually_exclusive_group", lambda: object())

    assert cmd_roadmap(args) == 2
    output = capsys.readouterr().err
    assert "usage: plan-tool roadmap" in output
    assert "argument --view: not allowed with argument --apply" in output


@pytest.mark.parametrize(
    "argv, handler_name",
    (
        (("--apply",), "_cmd_roadmap_apply"),
        (("--refresh-seeds",), "_cmd_roadmap_refresh_seeds"),
        (("--accept-seed", "plan-a"), "_cmd_roadmap_accept_seed"),
        (("--materialize", "plan-a"), "_cmd_roadmap_materialize"),
        (("--view", "summary"), "_cmd_roadmap_view"),
    ),
)
def test_single_broad_modes_keep_existing_dispatch_contracts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    argv: tuple[str, ...],
    handler_name: str,
) -> None:
    """Keep each single broad mode on its established handler and argument set."""
    args = _parse("roadmap", "my-roadmap", *argv)
    args.repo_root = tmp_path
    args.plans_dir = None
    args.manifest = None
    captured: dict = {}

    def handler(*received_args, **kwargs):
        captured.update(args=received_args, **kwargs)
        return 37

    monkeypatch.setattr(roadmap_cmd, handler_name, handler)

    assert cmd_roadmap(args) == 37
    assert captured["args"] == (args,)
    if handler_name == "_cmd_roadmap_view":
        assert captured["plans_dir"] == tmp_path / "docs" / "implementation-plans"
    else:
        assert captured["repo_root"] == tmp_path
        assert captured["plans_dir"] == tmp_path / "docs" / "implementation-plans"
    if handler_name in {
        "_cmd_roadmap_refresh_seeds",
        "_cmd_roadmap_materialize",
    }:
        assert captured["invoker"] is None


def test_selector_free_revise_feedback_rejects_broad_companions_before_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keep selector-free proposal conflicts ahead of path resolution and runners."""
    args = _parse(
        "roadmap",
        "my-roadmap",
        "--revise-feedback",
        "--apply",
    )
    args.repo_root = tmp_path
    args.plans_dir = None
    args.manifest = None
    monkeypatch.setattr(
        roadmap_cmd, "_resolve_cmd_repo_root",
        lambda _args: pytest.fail("conflicting lifecycle command resolved a path"),
    )

    assert cmd_roadmap(args) == 2


# --------------------------------------------------------------------------
# Repo-root / plans-dir resolution
# --------------------------------------------------------------------------


class TestPathResolution:
    def test_cmd_roadmap_resolves_repo_root_without_a_registered_manifest(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # No .plan-tool/plans.json at all — manifest-mode context building
        # would raise ManifestError here; _resolve_cmd_repo_root must not.
        assert not (tmp_path / ".plan-tool").exists()
        captured = _stub_run(monkeypatch, _completed())
        assert cmd_roadmap(_ns(tmp_path)) == 0
        assert captured["repo_root"] == tmp_path.resolve()

    def test_plans_dir_defaults_to_docs_implementation_plans(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path))
        assert (
            captured["plans_dir"]
            == tmp_path.resolve() / "docs" / "implementation-plans"
        )

    def test_plans_dir_override_reaches_run_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        other = tmp_path / "elsewhere"
        other.mkdir()
        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path, plans_dir=other))
        assert captured["plans_dir"] == other.resolve()


# --------------------------------------------------------------------------
# Dispatch → orchestrator wiring
# --------------------------------------------------------------------------


class TestOrchestratorWiring:
    def test_cmd_roadmap_calls_run_roadmap_with_the_parsed_slug_and_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        brief = tmp_path / "concept.md"
        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path, slug="payments", from_existing=brief))
        assert captured["slug"] == "payments"
        assert captured["brief_path"] == brief
        assert captured["repo_root"] == tmp_path.resolve()
        assert (
            captured["plans_dir"]
            == tmp_path.resolve() / "docs" / "implementation-plans"
        )
        assert captured["status_callback"] is roadmap_cmd.note

    def test_stage_run_forwards_only_the_slug_paths_and_status_callback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The removed ``--from-stage`` and ``--confirm-brief-rebind`` keywords
        never reach the orchestrator, which no longer accepts them."""
        captured = _stub_run(monkeypatch, _completed())

        assert cmd_roadmap(_ns(tmp_path)) == 0

        assert set(captured) == {
            "slug",
            "repo_root",
            "plans_dir",
            "brief_path",
            "status_callback",
        }

    def test_stage_run_leaves_the_brief_unread_to_run_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The CLI forwards the brief path without reading or classifying it."""
        missing_brief = tmp_path / "not-yet-readable.md"
        captured = _stub_run(monkeypatch, _completed())

        assert cmd_roadmap(_ns(tmp_path, from_existing=missing_brief)) == 0

        assert captured["brief_path"] == missing_brief

    def test_cmd_roadmap_forwards_a_supplied_invoker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, ""

        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path), invoker=fake_invoker)
        assert captured["invoker"] is fake_invoker

    def test_cmd_roadmap_omits_invoker_kwarg_when_none_supplied(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path))
        assert "invoker" not in captured


def test_non_stage_routes_keep_their_existing_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A non-stage route dispatches to its own handler, never the stage run."""
    captured: dict[str, object] = {}

    def apply(args: argparse.Namespace, **kwargs: object) -> int:
        captured["args"] = args
        captured.update(kwargs)
        return 37

    monkeypatch.setattr(roadmap_cmd, "_cmd_roadmap_apply", apply)

    assert cmd_roadmap(_ns(tmp_path, from_existing=None, apply=True)) == 37
    assert captured["args"].apply is True


class TestStageLifecycleStatus:
    def test_note_prefixes_an_already_bounded_status_line_without_further_truncation(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """``note()`` only adds its fixed prefix (the 250-char bound itself is
        covered elsewhere); scoped to non-colorized capture — a TTY's ANSI
        wrapping is pre-existing ``style.py`` behavior, not this feature's."""

        def runner(_slug: str, **kwargs) -> RoadmapResult:
            kwargs["status_callback"]("x" * 250)
            return _completed()

        monkeypatch.setattr(roadmap_cmd, "run_roadmap", runner)

        assert cmd_roadmap(_ns(tmp_path)) == 0

        first_line = capsys.readouterr().err.splitlines()[0]
        assert first_line.startswith("note: ")
        assert len(first_line) == 256

    @pytest.mark.parametrize(
        ("result", "renderer", "expected_rc"),
        (
            (_completed(), "completed", 0),
            (
                RoadmapResult(
                    outcome=OUTCOME_COMPLETED_NO_CHANGE,
                    artifacts=(),
                    stages_run=(),
                    pending_decisions=0,
                ),
                "no-change",
                0,
            ),
            (_exhausted(), "exhausted", 1),
            (
                RoadmapResult(
                    outcome=OUTCOME_STAGE_INVALID,
                    artifacts=(),
                    stages_run=(),
                    pending_decisions=0,
                    failed_stage=1,
                    failure_detail="invalid",
                ),
                "invalid",
                1,
            ),
        ),
        ids=("completed", "completed-no-change", "stage-exhausted", "stage-invalid"),
    )
    def test_returned_outcomes_emit_one_terminal_after_existing_summaries(
        self,
        result: RoadmapResult,
        renderer: str,
        expected_rc: int,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        calls: list[str] = []
        statuses: list[str] = []
        real_terminal_status = roadmap_cmd.emit_roadmap_terminal_status

        for name, label in (
            ("_print_completed", "completed"),
            ("_print_completed_no_change", "no-change"),
            ("_print_exhausted", "exhausted"),
            ("_print_invalid", "invalid"),
        ):
            monkeypatch.setattr(
                roadmap_cmd,
                name,
                lambda *_args, label=label, **_kwargs: calls.append(label),
            )
        for name, label in (
            ("_feedback_summary_lines", "feedback"),
            ("_newly_settled_summary_lines", "settled"),
            ("_seed_invalidation_summary_lines", "seeds"),
        ):
            monkeypatch.setattr(
                roadmap_cmd,
                name,
                lambda *_args, label=label, **_kwargs: calls.append(label) or [],
            )

        def terminal(status_callback, *, slug: str, result: RoadmapResult) -> None:
            calls.append("terminal")
            real_terminal_status(status_callback, slug=slug, result=result)

        monkeypatch.setattr(roadmap_cmd, "note", statuses.append)
        monkeypatch.setattr(roadmap_cmd, "emit_roadmap_terminal_status", terminal)
        _stub_run(monkeypatch, result)

        assert cmd_roadmap(_ns(tmp_path)) == expected_rc
        assert calls == [renderer, "feedback", "settled", "seeds", "terminal"]
        assert statuses == [f"roadmap my-roadmap: {result.outcome}"]

    def test_stage_status_does_not_change_existing_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _completed())

        assert cmd_roadmap(_ns(tmp_path)) == 0

        captured = capsys.readouterr()
        assert captured.out == "✓ roadmap my-roadmap: wrote 0 artifact(s)\n"
        assert captured.err == "note: roadmap my-roadmap: completed\n"

    def test_view_route_emits_no_stage_lifecycle_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def unexpected(*_args, **_kwargs):
            pytest.fail("view mode must not emit stage lifecycle status")

        monkeypatch.setattr(roadmap_cmd, "note", unexpected)
        monkeypatch.setattr(roadmap_cmd, "run_roadmap", unexpected)
        monkeypatch.setattr(roadmap_cmd, "_cmd_roadmap_view", lambda *_args, **_kwargs: 0)

        assert cmd_roadmap(_ns(tmp_path, view="summary", from_existing=None)) == 0

    def test_escaping_preflight_error_emits_refusal_terminal_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        emitted: list[dict[str, object]] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )
        _stub_run(monkeypatch, RoadmapError("bad stage source"))

        assert cmd_roadmap(_ns(tmp_path)) == 2
        assert emitted == [{"slug": "my-roadmap", "disposition": "preflight-refused"}]

    def test_escaping_disk_failure_returns_incomplete_not_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An ``OSError`` (disk full, permission denied) is an environmental
        failure-to-complete per this function's own docstring, not a bad
        argument — it must return 1, the same as every other write failure,
        not 2 alongside a pre-flight rejection."""
        _stub_run(monkeypatch, OSError("disk full"))

        assert cmd_roadmap(_ns(tmp_path)) == 1

    def test_escaping_environmental_prompt_read_failure_returns_incomplete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RoadmapEnvironmentalError`` (a prompt template that existed at
        the pre-flight check but failed to read, e.g. mid-run on a later
        stage) is the same environmental-failure shape as a raw
        ``OSError`` and must return 1, not the 2 a base ``RoadmapError``
        (a genuinely missing template) still returns."""
        _stub_run(monkeypatch, RoadmapEnvironmentalError("prompt input is not readable"))

        assert cmd_roadmap(_ns(tmp_path)) == 1

    def test_preflight_environmental_failure_returns_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        failure = RoadmapEnvironmentalError("prompt input is not readable")
        failure.roadmap_stage_started = False
        _stub_run(monkeypatch, failure)

        assert cmd_roadmap(_ns(tmp_path)) == 2

    def test_execution_path_resolution_emits_unexpected_terminal_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )
        monkeypatch.setattr(
            roadmap_cmd,
            "_resolve_cmd_repo_root",
            lambda _args: (_ for _ in ()).throw(RuntimeError("resolver defect")),
        )

        with pytest.raises(RuntimeError, match="resolver defect"):
            cmd_roadmap(_ns(tmp_path))

        assert emitted == [{"slug": "my-roadmap", "disposition": "unexpected-error"}]

    def test_escaping_stale_writer_token_returns_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_run(monkeypatch, roadmap_cmd.RoadmapWriterGuardError("stale writer token"))

        assert cmd_roadmap(_ns(tmp_path)) == 2

    def test_preflight_writer_guard_refusal_returns_matrix_usage_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_run(monkeypatch, RoadmapError("stale writer token"))

        assert cmd_roadmap(_ns(tmp_path)) == 2

    def test_mid_run_writer_guard_failure_returns_matrix_incomplete_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_run(
            monkeypatch,
            roadmap_cmd.RoadmapRunStartedWriterGuardError("stale writer token"),
        )

        assert cmd_roadmap(_ns(tmp_path)) == 1

    def test_keyboard_interrupt_keeps_rc_130_without_terminal_status(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **_kwargs: pytest.fail("interruption has no returned terminal"),
        )
        _stub_run(monkeypatch, KeyboardInterrupt())

        assert cmd_roadmap(_ns(tmp_path)) == 130


# --------------------------------------------------------------------------
# Outcome → exit code and summary
# --------------------------------------------------------------------------


class TestOutcomeMapping:
    def test_completed_outcome_returns_zero_and_prints_written_artifacts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _two_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "01-domain.md" in out
        assert "02-constraints.md" in out

    def test_completed_outcome_with_pending_decisions_still_returns_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _two_stage_completed(tmp_path, pending=3))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "3 pending decision(s)" in out
        assert "--settle-decision" in out and "--submit-feedback" in out
        assert "re-entering" not in out

    def test_completed_no_change_returns_zero_without_a_write_summary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            RoadmapResult(
                outcome=OUTCOME_COMPLETED_NO_CHANGE,
                artifacts=(),
                stages_run=(2,),
                pending_decisions=0,
            ),
        )

        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "re-gated without artifact changes" in out
        assert "wrote 0 artifact" not in out

    def test_stage_invalid_returns_nonzero_without_exhaustion_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            RoadmapResult(
                outcome=OUTCOME_STAGE_INVALID,
                artifacts=(),
                stages_run=(2,),
                pending_decisions=0,
                failed_stage=2,
                failure_detail="source changed outside reviewer feedback",
            ),
        )

        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert "stage 2 is invalid" in err
        assert "retry budget" not in err

    def test_pending_advice_never_sends_the_operator_back_to_the_edited_stage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Settling a `pending` row must not be advice that destroys the edit.

        A stage run never re-enters a published roadmap, so "edit the artifact
        and re-enter at that stage" would point at a route that does not exist.
        """
        _stub_run(monkeypatch, _two_stage_completed(tmp_path, pending=1))

        assert cmd_roadmap(_ns(tmp_path)) == 0

        out = capsys.readouterr().out
        assert "re-entering at that stage" not in out
        assert "in place" in out
        assert "above" in out

    def test_stage_exhausted_outcome_returns_nonzero_and_names_the_failed_stage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failed_stage=2,
                stages_run=(1, 2),
                failure_kind=FAILURE_GATES,
                violations=(
                    Violation(
                        kind="anchor",
                        artifact="02-constraints.md",
                        row_id="W",
                        message="workflow W names no entity",
                    ),
                ),
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert "stage 2" in err
        assert "workflow W names no entity" in err

    def test_gates_exhaustion_names_the_resume_directory_and_that_deleting_it_restarts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # The operator must be able to act on the text alone: the path, and the
        # cost of deleting it (every held, already paid stage).
        _stub_run(
            monkeypatch,
            _exhausted(failed_stage=2, stages_run=(1, 2), failure_kind=FAILURE_GATES),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert str(stage_resume_directory(tmp_path, "my-roadmap")) in err
        assert "restarts at stage 1" in err

    def test_roadmap_error_returns_a_usage_shaped_code_and_prints_the_message(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            RoadmapError("roadmap my-roadmap already has an accepted head"),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 2
        assert "already has an accepted head" in capsys.readouterr().err

    def test_malformed_upstream_artifact_error_is_caught_at_the_cli_layer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # run_roadmap lets a broken artifact surface as step 1's own parse
        # error rather than wrapping it, so the CLI catches both types.
        broken = tmp_path / "01-domain.md"
        _stub_run(
            monkeypatch,
            RoadmapArtifactError(f"{broken}: frontmatter is not a mapping", path=broken),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 2
        assert "frontmatter is not a mapping" in capsys.readouterr().err


class TestKeyboardInterruptExitCode:
    """batch-authoring-observability step 8: one ``except KeyboardInterrupt``
    wraps ``cmd_roadmap``'s whole dispatch, so an operator's Ctrl-C during
    any of the three backend-invoking branches (stage run, ``--refresh-seeds``,
    ``--apply``) maps to the same clean exit — rc 130, one stderr line, no
    traceback — rather than the raw ``KeyboardInterrupt`` a caller would see
    with no handler at all."""

    def test_stage_run_keyboard_interrupt_exits_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, KeyboardInterrupt())
        rc = cmd_roadmap(_ns(tmp_path))
        assert rc == 130
        assert "interrupted" in capsys.readouterr().err

    def test_refresh_seeds_keyboard_interrupt_exits_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        def boom(*_args, **_kwargs):
            raise KeyboardInterrupt()

        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", boom)
        rc = cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None))
        assert rc == 130
        assert "interrupted" in capsys.readouterr().err

    def test_apply_keyboard_interrupt_exits_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_apply(monkeypatch, KeyboardInterrupt())
        rc = cmd_roadmap(_ns(tmp_path, apply=True, yes=True, from_existing=None))
        assert rc == 130
        assert "interrupted" in capsys.readouterr().err


class TestFailureKindRendering:
    def test_gate_exhaustion_prints_the_violation_bullets(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failure_kind=FAILURE_GATES,
                violations=(
                    Violation(
                        kind="anchor",
                        artifact="01-domain.md",
                        row_id="E",
                        message="entity E is unreferenced",
                    ),
                    Violation(
                        kind="totality",
                        artifact="01-domain.md",
                        row_id="A",
                        message="attribute A has no owner",
                    ),
                ),
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert "- entity E is unreferenced" in err
        assert "- attribute A has no owner" in err
        assert "If the concept brief is the cause" in err
        assert "next plain run resumes at stage 1" in err
        assert "--from-stage" not in err

    def test_invoke_exhaustion_prints_the_diagnostic_not_an_empty_list(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failure_kind=FAILURE_INVOKE,
                failure_rc=127,
                failure_detail="claude: command not found",
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert "127" in err
        assert "claude: command not found" in err
        # No violation bullets, and no bare header implying an empty list.
        assert "\n- " not in err

    def test_invoke_exhaustion_omits_the_fix_the_brief_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failure_kind=FAILURE_INVOKE,
                failure_rc=1,
                failure_detail="rate limited",
            ),
        )
        cmd_roadmap(_ns(tmp_path))
        assert "brief" not in capsys.readouterr().err

    def test_parse_exhaustion_prints_the_reply_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failure_kind=FAILURE_PARSE,
                failure_detail="Sure! Here is the domain artifact you asked for:",
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        err = capsys.readouterr().err
        assert "Sure! Here is the domain artifact you asked for:" in err
        assert "brief" not in err

    def test_authored_review_rows_exhaustion_names_the_invented_collections(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """The fourth kind needs its own arm, or it prints nothing actionable.

        The generic tail quotes the reply head and stops, which reads as a
        malformed reply — the operator then goes looking in an artifact that
        is fine.
        """
        _stub_run(
            monkeypatch,
            _exhausted(
                failed_stage=1,
                failure_kind=FAILURE_AUTHORED_REVIEW_ROWS,
                failure_detail="---\nentities:\n- id: e-order\n",
            ),
        )

        assert cmd_roadmap(_ns(tmp_path)) == 1

        err = capsys.readouterr().err
        assert "feedback" in err
        assert "removals" in err
        assert "nothing you wrote caused this" in err
        assert "--from-stage" not in err

    def test_authored_review_rows_exhaustion_omits_the_fix_the_brief_advice(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failed_stage=1,
                failure_kind=FAILURE_AUTHORED_REVIEW_ROWS,
                failure_detail="---\nentities: []\n",
            ),
        )

        cmd_roadmap(_ns(tmp_path))

        err = capsys.readouterr().err
        assert "brief" not in err
        # No violation bullets: the gates never ran on this kind.
        assert "\n- " not in err


# --------------------------------------------------------------------------
# Feedback awaiting the reviewer
# --------------------------------------------------------------------------


class TestFeedbackAwaitingReview:
    """The advisory that points a reviewer at the responses waiting for them.

    Everything printed comes off ``RoadmapResult.feedback_awaiting_review``:
    this layer opens no artifact and counts nothing itself.
    """

    def _run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
        **kwargs,
    ) -> str:
        _stub_run(monkeypatch, _two_stage_completed(tmp_path, **kwargs))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        return capsys.readouterr().out

    def test_a_completed_run_with_awaiting_review_feedback_reports_the_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=3)
        assert "3 feedback row(s)" in out
        assert "await your review" in out

    def test_a_zero_count_prints_no_feedback_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=0)
        assert "feedback" not in out

    def test_a_zero_count_does_not_claim_feedback_awaits_review_when_a_stage_was_written(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=0, written_stages=(1,))
        assert "feedback row(s)" not in out
        assert "await your review" not in out

    def test_an_exhausted_run_that_wrote_a_revision_still_reports_the_count(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """A halted arc can still have answered a request before halting.

        Stage 1 can revise its artifact, answer the reviewer, and write it;
        stage 2 can then spend its budget. The response is on disk either way.
        """
        _stub_run(
            monkeypatch,
            _exhausted(
                stages_run=(1, 2), failed_stage=2, feedback_awaiting_review=2
            ),
        )

        assert cmd_roadmap(_ns(tmp_path)) == 1

        assert "2 feedback row(s)" in capsys.readouterr().out

    def test_an_exhausted_run_with_no_written_revision_reports_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _exhausted(stages_run=(1,), failed_stage=1))

        assert cmd_roadmap(_ns(tmp_path)) == 1

        assert "feedback" not in capsys.readouterr().out

    def test_the_block_names_deleting_the_row_as_the_close_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert "deleting the row" in out

    def test_the_block_names_reopening_by_setting_the_state_back_to_open(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert f"reopen it by setting 'state' back to '{FeedbackState.OPEN.value}'" in out

    def test_the_block_names_deferring_the_row(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert f"'{FeedbackState.DEFERRED.value}'" in out

    def test_the_printed_state_words_come_from_the_feedback_vocabulary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """The advice tells a reviewer what to type into YAML the parser reads.

        Hard-coding the spellings would let a rename in the artifact leaf make
        this module's advice wrong with nothing red firing, so the source must
        read them off the enum — not merely happen to agree with it today.
        """
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert FeedbackState.OPEN.value in out
        assert FeedbackState.DEFERRED.value in out

        source = inspect.getsource(roadmap_cmd._feedback_summary_lines)
        assert "FeedbackState.OPEN.value" in source
        assert "FeedbackState.DEFERRED.value" in source

    def test_the_block_points_at_the_proposed_response_field_by_name(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert "proposed_response" in out

    def test_the_block_never_claims_the_feedback_was_resolved(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Whether a response answered the request is the reviewer's call.

        "Awaiting your review" is the whole claim this tool is entitled to
        make about a row the model answered.
        """
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=2).lower()
        for claim in ("resolved", "addressed", "handled", "done"):
            assert claim not in out

    def test_feedback_summary_keeps_every_reopen_a_reviewer_edit_and_names_no_removed_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Deliberate: the confirmed ``--reopen-feedback`` exception is removed, so reopening is only a reviewer edit."""
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=2)
        assert "ordinary reopening remain reviewer edits" in out
        assert "--reopen-feedback" not in out
        assert "--confirm-feedback-reopen" not in out

    def test_the_block_names_no_removed_stage_reentry_flag(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=1)
        assert "--from-stage" not in out

    def test_awaiting_review_feedback_does_not_change_the_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _two_stage_completed(tmp_path, awaiting=20))
        assert cmd_roadmap(_ns(tmp_path)) == 0

        _stub_run(monkeypatch, _exhausted(failed_stage=1, feedback_awaiting_review=20))
        assert cmd_roadmap(_ns(tmp_path)) == 1

    def test_the_feedback_block_and_the_pending_decision_line_both_appear(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Two different things await a human, and neither swallows the other.

        A pending decision is the model's own unsettled guess; an
        awaiting-review row is its answer to something the reviewer wrote.
        """
        out = self._run(tmp_path, monkeypatch, capsys, awaiting=3, pending=2)
        assert "2 pending decision(s)" in out
        assert "3 feedback row(s)" in out

    def test_the_command_module_makes_no_interactive_call(self) -> None:
        """This block is where a TTY review walk is most tempting: the tool now
        knows a human is needed. It prints and returns."""
        source = inspect.getsource(roadmap_cmd)
        assert "input(" not in source
        assert "isatty" not in source


# --------------------------------------------------------------------------
# Decisions this revision newly settled
# --------------------------------------------------------------------------


class TestNewlySettledDecisions:
    """Advisory naming decision ids a revision settled and the prior version
    had not.

    Everything printed comes off ``RoadmapResult.newly_settled_decisions``:
    this layer opens no artifact and diffs nothing itself, so which of the two
    shapes produced an id — a row the predecessor never carried, or one it
    carried as ``pending`` — is settled in :mod:`plan_tool.roadmap` and never
    re-derived here.
    """

    def _run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
        **kwargs,
    ) -> str:
        _stub_run(monkeypatch, _two_stage_completed(tmp_path, **kwargs))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        return capsys.readouterr().out

    def test_a_completed_run_names_each_newly_settled_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(
            tmp_path,
            monkeypatch,
            capsys,
            newly_settled=("dec-two-patterns-not-one", "dec-extra"),
        )
        assert "2 decision(s) newly settled by this revision" in out
        assert "'dec-two-patterns-not-one'" in out
        assert "'dec-extra'" in out
        assert "confirm each in place" in out

    def test_the_block_names_both_shapes_that_reach_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """An id alone does not say which move produced it.

        A reviewer reading only "newly settled" would look for a row that is
        not there when the revision settled one they had left ``pending``.
        """
        out = self._run(tmp_path, monkeypatch, capsys, newly_settled=("dec-x",))
        assert "did not carry" in out
        assert f"carried as '{DecisionStatus.PENDING.value}'" in out

    def test_the_printed_status_word_comes_from_the_decision_vocabulary(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """The advice tells a reviewer what to type into YAML the parser reads.

        Same rule as the feedback block above: hard-coding the spelling would
        let a rename in the artifact leaf make this module's advice wrong with
        nothing red firing, so the source must read it off the enum rather than
        merely happen to agree with it today.
        """
        out = self._run(tmp_path, monkeypatch, capsys, newly_settled=("dec-x",))
        assert DecisionStatus.PENDING.value in out

        source = inspect.getsource(roadmap_cmd._newly_settled_summary_lines)
        assert "DecisionStatus.PENDING.value" in source

    def test_an_empty_tuple_prints_no_newly_settled_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(tmp_path, monkeypatch, capsys, newly_settled=())
        assert "newly settled" not in out

    def test_newly_settled_decisions_do_not_change_the_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _two_stage_completed(tmp_path, newly_settled=("dec-x",)),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 0

        _stub_run(
            monkeypatch,
            _exhausted(
                failed_stage=1, newly_settled_decisions=("dec-x",)
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1

    def test_an_exhausted_run_still_names_newly_settled_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(
            monkeypatch,
            _exhausted(
                failed_stage=2,
                stages_run=(1, 2),
                artifacts=(
                    tmp_path
                    / "docs"
                    / "implementation-plans"
                    / "roadmaps"
                    / "my-roadmap"
                    / "01-domain.md",
                ),
                newly_settled_decisions=("dec-minted",),
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 1
        out = capsys.readouterr().out
        assert "1 decision(s) newly settled by this revision" in out
        assert "'dec-minted'" in out

    def test_feedback_precedes_newly_settled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(
            tmp_path,
            monkeypatch,
            capsys,
            awaiting=1,
            newly_settled=("dec-x",),
        )
        assert out.index("await your review") < out.index("newly settled")

    def test_all_three_residue_lines_appear_together(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        out = self._run(
            tmp_path,
            monkeypatch,
            capsys,
            pending=1,
            awaiting=2,
            newly_settled=("dec-x",),
        )
        assert "1 pending decision(s)" in out
        assert "2 feedback row(s)" in out
        assert "1 decision(s) newly settled by this revision" in out


# --------------------------------------------------------------------------
# Repo-mutation lock and module registry
# --------------------------------------------------------------------------


class TestRegistryWiring:
    def test_roadmap_is_a_locked_mutating_command(self) -> None:
        assert cli_app._requires_repo_mutation_lock(
            argparse.Namespace(command="roadmap")
        )

    def test_build_parser_registers_roadmap_exactly_once(self) -> None:
        parser = cli.build_parser()
        action = next(
            a
            for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        )
        assert "roadmap" in action.choices
        assert [ca.dest for ca in action._choices_actions].count("roadmap") == 1


# --------------------------------------------------------------------------
# The one end-to-end case: the CLI over the real orchestrator
# --------------------------------------------------------------------------


def _e2e_domain_text(*, feedback: tuple[FeedbackRow, ...] = ()) -> str:
    """A minimal ``01-domain.md`` that passes every domain gate.

    ``feedback`` rides on the artifact so a caller can stage a predecessor
    carrying an open request and a reply carrying its answer. The design rows
    are identical either way, so the no-argument callers render exactly what
    they rendered before.
    """
    return render_domain_artifact(
        DomainArtifact(
            entities=(
                EntityRow(
                    id="e-order",
                    name="Order",
                    fields=(FieldRow(name="total", type=FieldType.NUMBER),),
                ),
            ),
            business_rules=(),
            workflows=(
                WorkflowRow(id="w-checkout", name="Check out", entity_ids=("e-order",)),
            ),
            decisions=(
                DecisionRow(
                    id="d-scope",
                    chosen_option="one order per checkout",
                    rejected_alternatives=(
                        RejectedAlternative(option="basket splitting", reason="no demand"),
                    ),
                    rationale="keeps the checkout path single-purpose",
                    anchor="w-checkout",
                    status=DecisionStatus.SETTLED,
                ),
            ),
            body="\n# Domain\n\n`e-order` moves through `w-checkout`; `d-scope` bounds it.\n",
            feedback=feedback,
        )
    )


# One reviewer request, in the two lifecycle states an answered revision moves
# it between. Same id, target, and request text on both — the gates reject a
# revision that alters any of them.
_E2E_FEEDBACK_ID = "fb-total-units"
_E2E_REQUEST = "Say what units the order total is counted in."


def _e2e_feedback(
    *, state: FeedbackState, response: str | None = None
) -> FeedbackRow:
    return FeedbackRow(
        id=_E2E_FEEDBACK_ID,
        target=FeedbackTarget(kind=FeedbackTargetKind.ROW, row_id="e-order"),
        request=_E2E_REQUEST,
        state=state,
        proposed_response=response,
    )


def _e2e_constraints_text() -> str:
    """A minimal ``02-constraints.md`` that passes every constraints gate."""
    dispositions = tuple(
        AttributeDispositionRow(
            id=f"qa-{attribute}",
            attribute=attribute,
            disposition=(
                ConstraintDisposition.PRIORITIZED
                if attribute == "performance"
                else ConstraintDisposition.NOT_LOAD_BEARING
            ),
        )
        for attribute in QUALITY_ATTRIBUTES
    )
    named = " ".join(f"`{row.id}`" for row in dispositions)
    return render_constraints_artifact(
        ConstraintsArtifact(
            dispositions=dispositions,
            constraints=(
                ConstraintRow(
                    id="c-latency",
                    statement="checkout answers under 200ms at p95",
                    attribute="performance",
                    anchor_ids=("e-order",),
                ),
            ),
            decisions=(
                DecisionRow(
                    id="d-budget",
                    chosen_option="200ms at p95",
                    rejected_alternatives=(
                        RejectedAlternative(option="100ms", reason="needs a cache tier"),
                    ),
                    rationale="the cheapest bound the checkout path can hold",
                    anchor="c-latency",
                    status=DecisionStatus.SETTLED,
                ),
            ),
            body=f"\n# Constraints\n\n{named} rank it; `c-latency` bounds it, per `d-budget`.\n",
            hosting=(
                HostingRow(
                    id="hosting-compute", facet="compute", value="per-request"
                ),
                HostingRow(id="hosting-model", facet="model", value="pool"),
                HostingRow(
                    id="hosting-topology", facet="topology", value="single-unit"
                ),
            ),
        )
    )


def _e2e_components_text() -> str:
    """A minimal ``03-components.md`` that passes every components gate."""
    return render_components_artifact(
        ComponentsArtifact(
            system_patterns=(
                PatternRow(
                    id="sp-boundary",
                    name="Service boundary",
                    statement="each component owns one write path",
                ),
            ),
            component_patterns=(
                PatternRow(
                    id="cp-aggregate",
                    name="Aggregate root",
                    statement="one consistency boundary per component",
                ),
            ),
            components=(
                ComponentRow(
                    id="comp-checkout",
                    name="Checkout",
                    entity_ids=("e-order",),
                    pattern_ids=("sp-boundary", "cp-aggregate"),
                    constraint_ids=("c-latency",),
                    store_ids=("store-checkout",),
                ),
            ),
            decisions=(
                DecisionRow(
                    id="d-split",
                    chosen_option="checkout stands alone",
                    rejected_alternatives=(
                        RejectedAlternative(
                            option="fold into catalog",
                            reason="different lifecycles",
                        ),
                    ),
                    rationale="checkout latency is its own concern",
                    anchor="c-latency",
                    status=DecisionStatus.SETTLED,
                ),
            ),
            body=(
                "\n# Components\n\n`sp-boundary` and `cp-aggregate` shape "
                "`comp-checkout`, which discharges `c-latency`, per `d-split`.\n"
            ),
            stores=(
                StoreRow(
                    id="store-checkout",
                    category="relational",
                    sharing="pool",
                ),
            ),
        )
    )


def _e2e_plans_text() -> str:
    """A minimal stage-4 reply that clears ``run_plans_gates`` for the e2e fixtures."""
    plans_text = """---
plans:
- id: checkout-core
  title: Checkout core
  intent: Let a shopper create a valid checkout order.
  non_goals:
  - Payment settlement.
  disposition: keep
  component_ids:
  - comp-checkout
  draft_seed_path: seeds/checkout-core.md
  sizing_rationale: One component, one plan.
ordering:
- plan_id: checkout-core
assumptions: []
decisions: []
---
# Plans

`checkout-core` covers `comp-checkout`.
"""
    return plans_text


@pytest.mark.integration
class TestFirstRunOverTheRealOrchestrator:
    """The CLI over the **real** orchestrator — the case that does not stub.

    Every other class here stubs ``run_roadmap`` and asserts what the CLI
    renders; ``tests/test_roadmap.py`` asserts the orchestrator prints nothing.
    Only a test that runs both layers can show that a real first run prints
    its summary once, lands the version store, and leaves no top-level files.
    """

    def _run(
        self, tmp_path: Path, capsys, *, replies: tuple[str, ...] | None = None
    ) -> tuple[int, str, str, Path]:
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir(exist_ok=True)
        brief = tmp_path / "concept.md"
        brief.write_text("A checkout system.\n", encoding="utf-8")
        queued = iter(
            replies
            if replies is not None
            else (
                _e2e_domain_text(),
                _e2e_constraints_text(),
                _e2e_components_text(),
                _e2e_plans_text(),
            )
        )

        def invoker(_prompt: str) -> tuple[int, str]:
            return 0, next(queued)

        args = _ns(tmp_path, plans_dir=plans_dir, from_existing=brief)
        rc = cmd_roadmap(args, invoker=invoker)
        captured = capsys.readouterr()
        return rc, captured.out, captured.err, plans_dir / "roadmaps" / "my-roadmap"

    def test_a_clean_first_run_prints_its_summary_once_and_leaves_only_the_version_store(
        self, tmp_path: Path, capsys
    ) -> None:
        rc, out, err, roadmap_folder = self._run(tmp_path, capsys)

        assert rc == 0, out + err
        assert (out + err).count("wrote 4 artifact(s)") == 1
        assert "--from-stage" not in out + err
        assert not list(roadmap_folder.glob("[0-9][0-9]-*.md"))
        assert (roadmap_folder / ".roadmap-versions" / "accepted-head.json").is_file()
        assert (roadmap_folder / "feedback-ledger.yaml").is_file()

    def test_a_second_run_is_refused_naming_the_head_and_writes_nothing(
        self, tmp_path: Path, capsys
    ) -> None:
        _rc, _out, _err, roadmap_folder = self._run(tmp_path, capsys)
        head_bytes = (roadmap_folder / ".roadmap-versions" / "accepted-head.json").read_bytes()

        rc, out, err, _folder = self._run(tmp_path, capsys)

        assert rc == 2
        assert "already has an accepted head" in err
        assert "wrote" not in out
        assert (
            roadmap_folder / ".roadmap-versions" / "accepted-head.json"
        ).read_bytes() == head_bytes

    def test_a_failed_stage_four_names_that_the_next_run_resumes_there(
        self, tmp_path: Path, capsys
    ) -> None:
        rc, _out, err, roadmap_folder = self._run(
            tmp_path,
            capsys,
            replies=(
                _e2e_domain_text(),
                _e2e_constraints_text(),
                _e2e_components_text(),
                # Stage 4 is retried up to its attempt limit; every attempt
                # gets the unparseable reply so the invoker never runs dry.
                "no artifact in this reply",
                "no artifact in this reply",
                "no artifact in this reply",
            ),
        )

        assert rc == 1
        assert "next plain run resumes at stage 4" in err
        assert "--from-stage" not in err
        assert not (roadmap_folder / ".roadmap-versions").exists()


def test_cli_refusal_for_accepted_head_exits_nonzero_with_the_named_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A pre-run refusal is a failure-to-complete: nonzero, message on stderr."""
    _stub_run(
        monkeypatch,
        RoadmapHeadExistsError(
            "roadmap my-roadmap already has an accepted head (version abc); "
            "a roadmap with a head is changed through feedback and review, "
            "not through a stage run"
        ),
    )

    assert cmd_roadmap(_ns(tmp_path)) == 2

    assert "already has an accepted head" in capsys.readouterr().err


def test_cli_refusal_for_pre_head_state_exits_nonzero_with_the_named_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _stub_run(
        monkeypatch,
        RoadmapPreHeadStateError(
            "roadmap my-roadmap has no accepted head but its folder already holds:\n"
            "- 01-domain.md\nconvert it by hand"
        ),
    )

    assert cmd_roadmap(_ns(tmp_path)) == 2

    err = capsys.readouterr().err
    assert "01-domain.md" in err
    assert "convert it by hand" in err


def test_failure_summary_does_not_mention_from_stage_and_says_the_next_run_resumes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    for result in (
        _exhausted(failed_stage=3, failure_kind=FAILURE_INVOKE, failure_rc=1),
        _exhausted(failed_stage=3, failure_kind=FAILURE_PARSE, failure_detail="x"),
        _exhausted(
            failed_stage=3,
            failure_kind=FAILURE_GATES,
            violations=(
                Violation(kind="k", artifact="03-components.md", row_id="r", message="m"),
            ),
        ),
        _exhausted(failed_stage=3, failure_kind=FAILURE_AUTHORED_REVIEW_ROWS),
    ):
        _stub_run(monkeypatch, result)

        assert cmd_roadmap(_ns(tmp_path)) == 1

        err = capsys.readouterr().err
        assert "--from-stage" not in err
        assert "next plain run resumes at stage 3" in err


@pytest.mark.integration
class TestKeyboardInterruptRunEndPairing:
    """The CLI's ``SystemExit``-free rc-130 mapping paired with the
    orchestrator's honest ``run_end`` bookkeeping (``plan_tool/roadmap.py``'s
    ``rc=130``/``error="interrupted"`` wrapper edit) — the same reason
    :class:`TestOverwriteAdviceIsPrintedExactlyOnce` runs the real
    orchestrator instead of a stub: only a test that drives both layers can
    see them land together on one run-log JSONL."""

    def _run_end_event(self, tmp_path: Path, slug: str) -> dict:
        logs = sorted((tmp_path / ".plan-tool" / "runs" / slug).glob("*.jsonl"))
        assert logs, "no run log was written"
        events = [
            json.loads(line)
            for line in logs[0].read_text(encoding="utf-8").splitlines()
        ]
        return next(e for e in events if e.get("event") == "run_end")

    def test_interrupted_stage_run_records_interrupt_run_end(
        self, tmp_path: Path
    ) -> None:
        brief = tmp_path / "concept.md"
        brief.write_text("A checkout system.\n", encoding="utf-8")

        def invoker(_prompt: str) -> tuple[int, str]:
            raise KeyboardInterrupt()

        rc = cmd_roadmap(_ns(tmp_path, from_existing=brief), invoker=invoker)
        assert rc == 130

        run_end = self._run_end_event(tmp_path, "my-roadmap")
        assert run_end["rc"] == 130
        assert run_end["error"] == "interrupted"

    def test_interrupted_apply_records_interrupt_run_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_apply_fixtures(tmp_path)
        import plan_tool.roadmap as roadmap_mod

        def boom(*_args, **_kwargs):
            raise KeyboardInterrupt()

        # ``_promoted_seed_body`` runs mid-apply, after the confirm (``yes=
        # True`` skips it) and before any file is committed — a realistic
        # "the operator hit Ctrl-C while this was writing" injection point.
        monkeypatch.setattr(roadmap_mod, "_promoted_seed_body", boom)
        monkeypatch.setattr(
            f"{MODULE}.run_roadmap",
            lambda *_a, **_k: (_ for _ in ()).throw(
                AssertionError("run_roadmap must not run in apply mode")
            ),
        )

        rc = cmd_roadmap(_ns(tmp_path, apply=True, yes=True, from_existing=None))
        assert rc == 130

        run_end = self._run_end_event(tmp_path, "my-roadmap")
        assert run_end["rc"] == 130
        assert run_end["error"] == "interrupted"

    def test_interrupted_before_the_feedback_proposal_run_logger_opens(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``run_initial_candidate_proposal`` opens its run log before its own try block —
        the one gap its own interrupt handling leaves — and it must still map to a clean
        130 like every other roadmap dispatch branch, not propagate."""
        import plan_tool.run_log as run_log_mod

        opened: list[str] = []

        def boom(*_args, **_kwargs):
            opened.append("run log")
            raise KeyboardInterrupt()

        monkeypatch.setattr(run_log_mod.RunLogWriter, "start", boom)

        rc = cmd_roadmap(_ns(tmp_path, revise_feedback=True, from_existing=None))
        assert opened == ["run log"]
        assert rc == 130

    def test_interrupted_refresh_records_interrupt_run_end(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_apply_fixtures(tmp_path)
        import plan_tool.roadmap as roadmap_mod

        monkeypatch.setattr(
            roadmap_mod,
            "materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        rc = cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None))
        assert rc == 130

        logs = sorted(
            (tmp_path / ".plan-tool" / "runs" / "my-roadmap").glob("*.jsonl")
        )
        events = [
            json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()
        ]
        phase_end = next(event for event in events if event["event"] == "phase_end")
        run_end = events[-1]
        assert phase_end["outcome"] == "interrupted"
        assert phase_end["active_plan_id"] == "plan-b"
        assert run_end["outcome"] == "interrupted"
        assert run_end["rc"] == 130
        assert run_end["active_plan_id"] is None
        assert not (
            tmp_path / ".plan-tool" / "runs" / "my-roadmap" / "in-flight.json"
        ).exists()


_STACK_CONSTRAINTS_TEXT = """---
dispositions: []
constraints: []
decisions:
- id: decision-1
  chosen_option: Lambda
  rejected_alternatives: []
  rationale: fits
  anchor: stack-1
  status: pending
stack:
- id: stack-1
  concern: platform
  choice: AWS Lambda
- id: stack-2
  concern: store-engine
  open: true
---
body
"""

_STACKLESS_CONSTRAINTS_TEXT = "---\ndispositions: []\nconstraints: []\ndecisions: []\n---\nbody\n"


def _write_constraints(tmp_path: Path, text: str) -> None:
    root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
    root.mkdir(parents=True)
    (root / "02-constraints.md").write_text(text, encoding="utf-8")


class TestStackSummaryOutput:
    def test_first_run_completion_prints_the_full_stack_with_open_and_pending_groups(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_constraints(tmp_path, _STACK_CONSTRAINTS_TEXT)
        _stub_run(monkeypatch, _two_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "`stack-1` platform: AWS Lambda" in out
        assert "`stack-2` store-engine: open" in out
        open_group = out.split("Open concerns:")[1].split("Pending concerns:")[0]
        pending_group = out.split("Pending concerns:")[1]
        assert "stack-2" in open_group and "stack-1" not in open_group
        assert "stack-1" in pending_group and "stack-2" not in pending_group

    def test_stack_lines_print_plain_with_no_bullet_inside_a_bullet_and_no_empty_bullet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """The producer's blank separators serve INDEX.md; the terminal must not
        turn them into bare ``·`` lines or nest the row bullets under ``·``."""
        _write_constraints(tmp_path, _STACK_CONSTRAINTS_TEXT)
        _stub_run(monkeypatch, _two_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        lines = capsys.readouterr().out.splitlines()
        assert not any(line.strip() == "·" for line in lines)
        assert not any("· - `stack-" in line for line in lines)
        assert "  - `stack-1` platform: AWS Lambda" in lines

    def test_first_run_without_a_stack_prints_not_recorded(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_constraints(tmp_path, _STACKLESS_CONSTRAINTS_TEXT)
        _stub_run(monkeypatch, _two_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        assert "Stack: not recorded for this version." in capsys.readouterr().out

    def test_no_change_regate_prints_no_stack_block(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_constraints(tmp_path, _STACK_CONSTRAINTS_TEXT)
        _stub_run(
            monkeypatch,
            RoadmapResult(
                outcome=OUTCOME_COMPLETED_NO_CHANGE,
                artifacts=(),
                stages_run=(2,),
                pending_decisions=0,
            ),
        )
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "Stack" not in out and "Open concerns" not in out

    def test_unloadable_constraints_artifact_reports_error_and_keeps_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_constraints(tmp_path, "not a roadmap artifact\n")
        _stub_run(monkeypatch, _two_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        captured = capsys.readouterr()
        assert "cannot print stack summary" in captured.out + captured.err
        assert "Open concerns" not in captured.out


class TestCreateHandoffLines:
    def test_completed_four_stage_run_prints_create_handoff_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
        root.mkdir(parents=True)
        plans_text = """---
plans:
- id: plan-b
  title: B
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-b.md
  sizing_rationale: one
- id: plan-a
  title: A
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-a.md
  sizing_rationale: one
ordering:
- plan_id: plan-b
- plan_id: plan-a
  depends_on:
  - plan-b
assumptions: []
decisions: []
---
# Plans

`plan-b` and `plan-a`.
"""
        (root / "04-roadmap.md").write_text(plans_text, encoding="utf-8")
        seeds = root / "seeds"
        seeds.mkdir()
        plan_a = _draft_seed_text(body="# Seed a\n")
        plan_b = _draft_seed_text(body="# Seed b\n")
        (seeds / "plan-a.md").write_text(plan_a, encoding="utf-8")
        (seeds / "plan-b.md").write_text(plan_b, encoding="utf-8")
        write_seed_state(
            seed_state_path(root),
            {
                "version": 1,
                "seeds": {
                    "plan-a": {
                        "draft_seed_path": "seeds/plan-a.md",
                        "status": "current",
                        "digest": digest_text(plan_a),
                        "published": False,
                    },
                    "plan-b": {
                        "draft_seed_path": "seeds/plan-b.md",
                        "status": "current",
                        "digest": digest_text(plan_b),
                        "published": False,
                    },
                },
            },
        )
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert out.index("plan-tool create plan-b") < out.index(
            "plan-tool create plan-a"
        )
        assert "--from-existing" in out

    def test_three_stage_completed_run_prints_no_create_handoff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _three_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert "plan-tool create" not in out

    def test_create_handoff_uses_ordering_sequence_not_plans_row_order(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
        root.mkdir(parents=True)
        plans_text = """---
plans:
- id: plan-z
  title: Z
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-z.md
  sizing_rationale: one
- id: plan-a
  title: A
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-a.md
  sizing_rationale: one
ordering:
- plan_id: plan-a
- plan_id: plan-z
assumptions: []
decisions: []
---
# Plans

`plan-z` and `plan-a`.
"""
        (root / "04-roadmap.md").write_text(plans_text, encoding="utf-8")
        seeds = root / "seeds"
        seeds.mkdir()
        plan_a = _draft_seed_text(body="# Seed a\n")
        plan_z = _draft_seed_text(body="# Seed z\n")
        (seeds / "plan-a.md").write_text(plan_a, encoding="utf-8")
        (seeds / "plan-z.md").write_text(plan_z, encoding="utf-8")
        write_seed_state(
            seed_state_path(root),
            {
                "version": 1,
                "seeds": {
                    "plan-a": {
                        "draft_seed_path": "seeds/plan-a.md",
                        "status": "current",
                        "digest": digest_text(plan_a),
                        "published": False,
                    },
                    "plan-z": {
                        "draft_seed_path": "seeds/plan-z.md",
                        "status": "current",
                        "digest": digest_text(plan_z),
                        "published": False,
                    },
                },
            },
        )
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path)) == 0
        out = capsys.readouterr().out
        assert out.index("plan-tool create plan-a") < out.index(
            "plan-tool create plan-z"
        )

    def test_create_handoff_reports_error_on_corrupt_seed_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        root = _write_apply_fixtures(tmp_path)
        seed_state_path(root).write_text("{", encoding="utf-8")
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))

        assert cmd_roadmap(_ns(tmp_path)) == 0

        captured = capsys.readouterr()
        assert "cannot print create handoff:" in captured.err
        assert "plan-tool create" not in captured.out

    def test_create_handoff_routes_noncurrent_drafts_to_materialization(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        root = _write_apply_fixtures(tmp_path)
        state = load_seed_state(seed_state_path(root))
        state["seeds"]["plan-a"]["status"] = "invalidated"
        write_seed_state(seed_state_path(root), state)
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))

        assert cmd_roadmap(_ns(tmp_path)) == 0

        out = capsys.readouterr().out
        assert "plan-tool create plan-b" in out
        assert "plan-tool create plan-a" not in out
        assert "plan-a' is not seed-ready (stale)" in out
        assert "--materialize plan-a" in out

    def test_create_handoff_labels_a_missing_classification_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_apply_fixtures(tmp_path)
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: {},
        )

        assert cmd_roadmap(_ns(tmp_path)) == 0

        out = capsys.readouterr().out
        assert "plan-a' is not seed-ready (unavailable)" in out
        assert "plan-b' is not seed-ready (unavailable)" in out


# --------------------------------------------------------------------------
# Apply-only mode
# --------------------------------------------------------------------------


def _stub_apply(monkeypatch: pytest.MonkeyPatch, result_or_exc) -> dict:
    captured: dict = {}

    def fake(slug, **kwargs):
        captured["slug"] = slug
        captured.update(kwargs)
        if isinstance(result_or_exc, BaseException):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", fake)
    return captured


def _stub_accept(monkeypatch: pytest.MonkeyPatch, result_or_exc) -> dict:
    captured: dict = {}

    def fake(slug, plan_id, **kwargs):
        captured["slug"] = slug
        captured["plan_id"] = plan_id
        captured.update(kwargs)
        if isinstance(result_or_exc, BaseException):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(f"{MODULE}.accept_roadmap_seed", fake)
    return captured


def _draft_seed_text(*, body: str = "# Seed body\n") -> str:
    return f"""---
roadmap_components:
  - component-checkout
---

{body.rstrip()}

## Risks

- A risk the accepted roadmap already states.

## References

- `{DOMAIN_FILENAME}`
- `{CONSTRAINTS_FILENAME}`
- `{COMPONENTS_FILENAME}`
- `{PLANS_FILENAME}`
"""


def _write_apply_fixtures(tmp_path: Path) -> Path:
    root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "my-roadmap"
    root.mkdir(parents=True)
    plans_text = """---
plans:
- id: plan-b
  title: B
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-b.md
  sizing_rationale: one
- id: plan-a
  title: A
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: seeds/plan-a.md
  sizing_rationale: one
ordering:
- plan_id: plan-b
- plan_id: plan-a
assumptions: []
decisions: []
---
# Plans
"""
    publish_accepted_root(
        tmp_path / "docs" / "implementation-plans",
        "my-roadmap",
        with_minimal_upstream(plans_text),
    )
    # Handoff tests name this copy in ``result.artifacts`` (any readable plans
    # file works); the seed routes read only the accepted version published above.
    (root / "04-roadmap.md").write_text(plans_text, encoding="utf-8")
    seeds = root / "seeds"
    seeds.mkdir()
    plan_a = _draft_seed_text(body="# Seed a\n")
    plan_b = _draft_seed_text(body="# Seed b\n")
    (seeds / "plan-a.md").write_text(plan_a, encoding="utf-8")
    (seeds / "plan-b.md").write_text(plan_b, encoding="utf-8")
    write_seed_state(
        seed_state_path(root),
        {
            "version": 1,
            "seeds": {
                "plan-a": {
                    "draft_seed_path": "seeds/plan-a.md",
                    "status": "current",
                    "digest": digest_text(plan_a),
                    "published": False,
                },
                "plan-b": {
                    "draft_seed_path": "seeds/plan-b.md",
                    "status": "current",
                    "digest": digest_text(plan_b),
                    "published": False,
                },
            },
        },
    )
    return root


def _materialize_artifact() -> PlansArtifact:
    rows = (
        PlanRow(
            id="plan-a",
            title="Plan A",
            disposition=PlanDisposition.KEEP,
            component_ids=("component-checkout",),
            draft_seed_path="seeds/plan-a.md",
            sizing_rationale="one",
        ),
        PlanRow(
            id="plan-b",
            title="Plan B",
            disposition=PlanDisposition.KEEP,
            component_ids=("component-checkout",),
            draft_seed_path="seeds/plan-b.md",
            sizing_rationale="one",
        ),
    )
    return PlansArtifact(
        plans=rows,
        ordering=tuple(OrderingEntry(plan_id=row.id) for row in rows),
        assumptions=(),
        decisions=(),
        body="# Plans\n",
    )


def _classifications(
    **states: str,
) -> dict[str, DraftSeedClassification]:
    return {
        plan_id: DraftSeedClassification(plan_id=plan_id, state=state)
        for plan_id, state in states.items()
    }


def _materialize_change(row: PlanRow, tmp_path: Path) -> RoadmapSeedRefreshChange:
    return RoadmapSeedRefreshChange(
        plan_id=row.id,
        target=tmp_path / f"{row.id}.md",
        previous=None,
        action="created",
        diff="",
    )


class TestMaterializeMode:
    def _lifecycle_events(self, tmp_path: Path) -> list[dict]:
        logs = list((tmp_path / ".plan-tool" / "runs" / "my-roadmap").glob("*.jsonl"))
        assert len(logs) == 1
        return [
            json.loads(line) for line in logs[0].read_text(encoding="utf-8").splitlines()
        ]

    def _assert_snapshot_removed(self, tmp_path: Path) -> None:
        assert not (
            tmp_path / ".plan-tool" / "runs" / "my-roadmap" / "in-flight.json"
        ).exists()

    def _stub_artifact_and_classifications(
        self,
        monkeypatch: pytest.MonkeyPatch,
        classifications: dict[str, DraftSeedClassification],
    ) -> PlansArtifact:
        artifact = _materialize_artifact()
        monkeypatch.setattr(f"{MODULE}.load_accepted_plans_artifact", lambda **_kwargs: artifact)
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda _artifact, **_kwargs: classifications,
        )
        return artifact

    def test_materialize_runs_no_stages_or_apply(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        called: list[tuple[str, dict, bool]] = []

        def boom(*_args, **_kwargs) -> None:
            raise AssertionError("materialize mode must not dispatch another mode")

        def materialize(_slug, row, **_kwargs):
            called.append((row.id, _kwargs, _kwargs["writer_token"]._active))
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom)
        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )
        assert [plan_id for plan_id, _kwargs, _active in called] == [artifact.plans[0].id]
        assert called[0][2]
        # Exact key set — not just presence checks — so a future stray kwarg
        # added at either call site is caught rather than silently passed
        # through unnoticed.
        assert set(called[0][1].keys()) == {
            "repo_root",
            "plans_dir",
            "max_attempts",
            "materialization_observer",
            "writer_token",
        }
        assert called[0][1]["repo_root"] == tmp_path
        assert (
            called[0][1]["plans_dir"] == tmp_path / "docs" / "implementation-plans"
        )
        assert called[0][1]["max_attempts"] == roadmap.MAX_STAGE_ATTEMPTS
        assert isinstance(
            called[0][1]["materialization_observer"],
            roadmap._MaterializationObserver,
        )

    def test_materialize_acquires_the_guard_before_loading_its_batch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = _materialize_artifact()
        entered = False
        token = object()

        @contextlib.contextmanager
        def guard(_plans_dir: Path, _slug: str):
            nonlocal entered
            entered = True
            yield token

        def load(**_kwargs: object) -> PlansArtifact:
            assert entered
            return artifact

        def classify(_artifact: PlansArtifact, **_kwargs):
            assert entered
            return _classifications(**{"plan-a": "missing", "plan-b": "current"})

        def materialize(_slug, _row, **kwargs):
            assert entered
            assert kwargs["writer_token"] is token
            return (), None

        monkeypatch.setattr(f"{MODULE}._roadmap_writer_owner", guard)
        monkeypatch.setattr(
            f"{MODULE}.require_roadmap_writer_token", lambda *_args, **_kwargs: None
        )
        monkeypatch.setattr(f"{MODULE}.load_accepted_plans_artifact", load)
        monkeypatch.setattr(f"{MODULE}.classify_draft_seeds", classify)
        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )

    def test_materialize_rejects_a_bad_slug_cleanly(
        self, tmp_path: Path, capsys
    ) -> None:
        """A bad slug must fail at guard acquisition with the same clean
        usage error every other roadmap dispatch branch gives it, not an
        uncaught ``ValueError``."""
        rc = cmd_roadmap(
            _ns(
                tmp_path,
                slug="bad/slug",
                materialize=roadmap_cmd._MATERIALIZE_ALL,
                from_existing=None,
            )
        )
        assert rc == 2
        assert "path separator" in capsys.readouterr().err

    def test_materialize_preflight_lifecycle_survives_a_broken_run_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """The best-effort preflight record this branch builds only ever
        swallowed ``RoadmapError`` -- a disk failure opening the run log
        (``RunLogWriter.start`` doing real file I/O) must not replace the
        original clean refusal with an uncaught ``OSError``."""

        @contextlib.contextmanager
        def broken_guard(_plans_dir: Path, _slug: str):
            raise roadmap_cmd.RoadmapError("writer acquisition refused")
            yield  # pragma: no cover

        monkeypatch.setattr(roadmap_cmd, "_roadmap_writer_owner", broken_guard)
        monkeypatch.setattr(
            roadmap.RunLogWriter,
            "start",
            classmethod(lambda *_a, **_kw: (_ for _ in ()).throw(OSError("disk full"))),
        )

        rc = cmd_roadmap(
            _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
        )

        assert rc == roadmap_cmd._RC_USAGE
        assert "writer acquisition refused" in capsys.readouterr().err

    def test_materialize_emits_unexpected_error_when_writer_teardown_fails_after_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A batch that materialized nothing (a clean no-op) already emitted
        its own accurate disposition before returning. If the writer guard's
        own teardown then fails (e.g. releasing its lock), that is a
        genuinely new, unhandled failure and must get its own
        "unexpected-error" disposition -- not be silently treated as already
        accounted for just because we were "inside" the owned lifecycle."""
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "current", "plan-b": "current"})
        )

        @contextlib.contextmanager
        def guard(_plans_dir: Path, _slug: str):
            yield object()
            raise OSError("lock release failed")

        monkeypatch.setattr(roadmap_cmd, "_roadmap_writer_owner", guard)
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )

        with pytest.raises(OSError, match="lock release failed"):
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )

        assert emitted[-1]["disposition"] == "unexpected-error"

    def test_materialize_does_not_double_report_an_already_dispositioned_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RoadmapError``/``RoadmapArtifactError`` that already carries
        ``materialize_disposition_emitted`` (set by
        ``_cmd_roadmap_materialize_owned``'s own merged exception handler
        before it re-raises) must not also get treated as an unattempted
        preflight refusal by the outer function -- the owned call already
        owns whatever disposition this failure gets."""

        @contextlib.contextmanager
        def guard(_plans_dir: Path, _slug: str):
            yield object()

        def already_dispositioned(*_a, **_kw):
            exc = roadmap_cmd.RoadmapError("owned lifecycle already reported this")
            exc.materialize_disposition_emitted = True
            raise exc

        monkeypatch.setattr(roadmap_cmd, "_roadmap_writer_owner", guard)
        monkeypatch.setattr(
            roadmap_cmd, "_cmd_roadmap_materialize_owned", already_dispositioned
        )
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )

        with pytest.raises(roadmap_cmd.RoadmapError, match="already reported"):
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )

        assert emitted == []

    def test_materialize_treats_a_fresh_roadmap_error_after_entry_as_unexpected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RoadmapError``/``RoadmapArtifactError`` that reaches the
        outer function *without* the disposition tag (e.g. raised by the
        writer guard's own teardown after ``_cmd_roadmap_materialize_owned``
        already returned) must not be misread as an unattempted preflight
        refusal -- real work was already underway or complete by then."""

        @contextlib.contextmanager
        def guard(_plans_dir: Path, _slug: str):
            yield object()
            raise roadmap_cmd.RoadmapError("teardown broke after materialize returned")

        monkeypatch.setattr(roadmap_cmd, "_roadmap_writer_owner", guard)
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "current", "plan-b": "current"})
        )
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )

        with pytest.raises(roadmap_cmd.RoadmapError, match="teardown broke"):
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )

        assert emitted[-1]["disposition"] == "unexpected-error"

    def test_materialize_owned_does_not_let_its_outer_net_swallow_a_dispositioned_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A ``RoadmapError`` reaching the merged inner ``except
        BaseException`` (an unclassified failure, not one of the six named
        preflight branches) already gets an "unexpected-error" disposition
        there. ``_cmd_roadmap_materialize_owned``'s own trailing
        ``except (RoadmapError, RoadmapArtifactError)`` outer net must not
        then re-catch that same re-raised exception and return a clean
        rc=2 usage error, contradicting the disposition already emitted."""
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda _slug, row, **_kw: ((_materialize_change(row, tmp_path),), None),
        )
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report",
            lambda *_a, **_kw: (_ for _ in ()).throw(
                roadmap_cmd.RoadmapError("report write hit an unclassified failure")
            ),
        )
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )

        with pytest.raises(roadmap_cmd.RoadmapError, match="unclassified failure"):
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )

        assert emitted[-1]["disposition"] == "unexpected-error"

    def test_materialize_owned_emits_disposition_for_a_baseexception_escape(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-``Exception`` escape (e.g. ``SystemExit``) from inside the
        owned lifecycle must get the same terminal-disposition emission as
        an ordinary exception -- not silently skip it because it isn't an
        ``Exception`` subclass."""
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_a, **_kw: (_ for _ in ()).throw(SystemExit(3)),
        )
        emitted: list[dict] = []
        monkeypatch.setattr(
            roadmap_cmd,
            "emit_roadmap_terminal_status",
            lambda *_args, **kwargs: emitted.append(kwargs),
        )

        with pytest.raises(SystemExit):
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )

        assert emitted[-1]["disposition"] == "unexpected-error"

    def test_selected_materialize_emits_one_attributed_lifecycle_and_cleans_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )

        def materialize(_slug, row, **kwargs):
            kwargs["materialization_observer"].begin_seed_attempt(
                seed_attempt=1, prompt_bytes=42, prompt_sha256="0" * 64
            )
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 0

        events = self._lifecycle_events(tmp_path)
        run_start = events[0]
        phase_start = next(event for event in events if event["event"] == "phase_start")
        call_start = next(event for event in events if event["event"] == "claude_call_start")
        phase_end = next(event for event in events if event["event"] == "phase_end")
        run_end = events[-1]
        assert run_start["roadmap_action"] == "materialize"
        assert run_start["roadmap_slug"] == "my-roadmap"
        assert run_start["requested_plan_id"] == "plan-a"
        assert run_start["active_plan_id"] is None
        assert phase_start["phase"] == "seed-materialize:plan-a"
        assert phase_start["active_plan_id"] == "plan-a"
        assert call_start["active_plan_id"] == "plan-a"
        assert call_start["seed_attempt"] == 1
        assert phase_end["outcome"] == "ok"
        assert phase_end["active_plan_id"] == "plan-a"
        assert phase_end["seed_attempt"] is None
        assert phase_end["backend_attempt"] is None
        assert run_end["outcome"] == "completed"
        assert run_end["rc"] == 0
        assert run_end["active_plan_id"] is None
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_one_targets_only_the_named_recoverable_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "stale", "plan-b": "missing"})
        )
        called: list[str] = []

        def materialize(_slug, row, **_kwargs):
            called.append(row.id)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 0
        assert called == [artifact.plans[0].id]

    def test_materialize_all_skips_a_plan_row_with_no_classification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "stale"})
        )
        called: list[str] = []

        def materialize(_slug, row, **_kwargs):
            called.append(row.id)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )
        assert called == [artifact.plans[0].id]

    def test_materialize_all_uses_the_real_classifier_to_skip_current_drafts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        root = _write_apply_fixtures(tmp_path)
        current = (root / "seeds" / "plan-a.md").read_text(encoding="utf-8")
        write_seed_state(
            seed_state_path(root),
            {
                "version": 1,
                "seeds": {
                    "plan-a": {
                        "draft_seed_path": "seeds/plan-a.md",
                        "status": "current",
                        "digest": digest_text(current),
                        "published": False,
                    }
                },
            },
        )
        called: list[str] = []

        def materialize(_slug, row, **_kwargs):
            called.append(row.id)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )
        assert called == ["plan-b"]

    @pytest.mark.parametrize("state", ("current", "duplicate"))
    def test_materialize_refuses_a_known_nonrecoverable_plan(
        self,
        state: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": state, "plan-b": "missing"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: pytest.fail("must not materialize"),
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 2
        assert state in capsys.readouterr().err

    def test_materialize_refuses_an_unknown_plan_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "missing"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: pytest.fail("must not materialize"),
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-absent", from_existing=None)) == 2
        assert "no such plan in this roadmap" in capsys.readouterr().err

    def test_materialize_cli_refuses_with_no_published_version_via_preflight_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: pytest.fail("must not materialize"),
        )

        rc = cmd_roadmap(_ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None))

        assert rc == roadmap_cmd._RC_USAGE
        assert "no published version" in capsys.readouterr().err
        events = self._lifecycle_events(tmp_path)
        assert events[-1]["outcome"] == "preflight-refused"
        assert events[-1]["rc"] == roadmap_cmd._RC_USAGE
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_cli_selects_rows_from_the_accepted_version(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        plans_dir = tmp_path / "docs" / "implementation-plans"
        root_artifact = _materialize_artifact()
        publish_accepted_root(
            plans_dir, "my-roadmap", with_minimal_upstream(render_plans_artifact(root_artifact))
        )
        head_row = PlanRow(
            id="plan-head",
            title="Plan Head",
            disposition=PlanDisposition.KEEP,
            component_ids=("component-checkout",),
            draft_seed_path="seeds/plan-head.md",
            sizing_rationale="one",
        )
        head_artifact = PlansArtifact(
            plans=(head_row,),
            ordering=(OrderingEntry(plan_id=head_row.id),),
            assumptions=(),
            decisions=(),
            body="# Plans\n\n`plan-head`\n",
        )
        advance_accepted_head(
            plans_dir, "my-roadmap", with_minimal_upstream(render_plans_artifact(head_artifact))
        )
        seen: list[str] = []

        def materialize(_slug, row, **_kwargs):
            seen.append(row.id)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )
            == 0
        )
        assert cmd_roadmap(_ns(tmp_path, materialize="plan-head", from_existing=None)) == 0
        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 2

        assert seen == ["plan-head", "plan-head"]

    def test_stale_writer_token_is_a_clean_usage_error_not_a_raw_exception(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """A stale/contended writer token is a clean rc=2 usage error, not a raw
        exception, like every other roadmap dispatch branch's guard failure."""

        def stale_writer_token(*_args: object, **_kwargs: object) -> None:
            raise roadmap.RoadmapWriterGuardError("stale writer token")

        monkeypatch.setattr(
            roadmap_cmd, "require_roadmap_writer_token", stale_writer_token
        )

        assert (
            cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None))
            == roadmap_cmd._RC_USAGE
        )
        assert "stale writer token" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("target", "classifications"),
        (
            (
                "plan-absent",
                _classifications(**{"plan-a": "missing", "plan-b": "missing"}),
            ),
            (
                "plan-a",
                _classifications(**{"plan-a": "current", "plan-b": "missing"}),
            ),
            (
                "plan-a",
                _classifications(**{"plan-a": "duplicate", "plan-b": "missing"}),
            ),
        ),
    )
    def test_selected_materialize_preflight_refusal_records_requested_id_without_phase(
        self,
        target: str,
        classifications: dict[str, DraftSeedClassification],
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, classifications
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: pytest.fail("must not materialize"),
        )

        assert cmd_roadmap(_ns(tmp_path, materialize=target, from_existing=None)) == 2

        events = self._lifecycle_events(tmp_path)
        assert [event["event"] for event in events] == ["run_start", "run_end"]
        assert events[0]["requested_plan_id"] == target
        assert events[-1]["outcome"] == "preflight-refused"
        assert events[-1]["rc"] == 2
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_all_current_returns_without_a_report(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "current", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: pytest.fail("must not materialize"),
        )
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report",
            lambda *_args, **_kwargs: pytest.fail("must not write a report"),
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )
        assert "nothing to materialize" in capsys.readouterr().err

        events = self._lifecycle_events(tmp_path)
        assert [event["event"] for event in events] == ["run_start", "run_end"]
        assert events[0]["requested_plan_id"] is None
        assert events[-1]["outcome"] == "no-op"
        assert events[-1]["rc"] == 0
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_maps_partial_and_exhausted_batches_to_refresh_exit_codes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "stale"})
        )

        def partial(_slug, row, **_kwargs):
            if row.id == "plan-a":
                return (_materialize_change(row, tmp_path),), None
            return (), RoadmapSeedRefreshFailure(plan_id=row.id, failure_kind=FAILURE_GATES)

        reports: list[tuple[tuple, tuple]] = []
        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", partial)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report",
            lambda _slug, changes, failures, **_kwargs: reports.append(
                (tuple(changes), tuple(failures))
            ) or tmp_path / "seed-refresh-report.md",
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 3
        )
        assert len(reports[0][0]) == 1
        assert len(reports[0][1]) == 1

        events = self._lifecycle_events(tmp_path)
        assert events[-1]["outcome"] == "partial"
        assert events[-1]["rc"] == 3
        self._assert_snapshot_removed(tmp_path)

        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda _slug, row, **_kwargs: (
                (),
                RoadmapSeedRefreshFailure(plan_id=row.id, failure_kind=FAILURE_GATES),
            ),
        )
        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 1
        )
        run_ends = []
        for log_path in (tmp_path / ".plan-tool" / "runs" / "my-roadmap").glob("*.jsonl"):
            events = [
                json.loads(line)
                for line in log_path.read_text(encoding="utf-8").splitlines()
            ]
            run_ends.append(events[-1])
        assert {(event["outcome"], event["rc"]) for event in run_ends} == {
            ("partial", 3),
            ("exhausted", 1),
        }
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_all_eligible_uses_plans_source_order_for_phases_and_calls(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        artifact = _materialize_artifact()
        reordered = PlansArtifact(
            plans=artifact.plans,
            ordering=(
                OrderingEntry(plan_id="plan-b"),
                OrderingEntry(plan_id="plan-a"),
            ),
            assumptions=artifact.assumptions,
            decisions=artifact.decisions,
            body=artifact.body,
        )
        monkeypatch.setattr(f"{MODULE}.load_accepted_plans_artifact", lambda **_kwargs: reordered)
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: _classifications(
                **{"plan-a": "missing", "plan-b": "stale"}
            ),
        )
        calls: list[str] = []

        def materialize(_slug, row, **_kwargs):
            calls.append(row.id)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                )
            )
            == 0
        )

        assert calls == ["plan-a", "plan-b"]
        events = self._lifecycle_events(tmp_path)
        assert [
            event["phase"] for event in events if event["event"] == "phase_start"
        ] == ["seed-materialize:plan-a", "seed-materialize:plan-b"]
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_passes_the_active_phase_observer_and_only_a_supplied_invoker(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        calls: list[dict] = []

        def materialize(_slug, row, **kwargs):
            calls.append(kwargs)
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report", lambda *_args, **_kwargs: None
        )
        supplied_invoker = lambda _prompt: (0, "")

        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    materialize=roadmap_cmd._MATERIALIZE_ALL,
                    from_existing=None,
                ),
                invoker=supplied_invoker,
            )
            == 0
        )
        assert calls[0]["invoker"] is supplied_invoker
        assert isinstance(
            calls[0]["materialization_observer"],
            roadmap._MaterializationObserver,
        )

    def test_materialize_row_preparation_refusal_closes_the_active_phase(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapError("row preparation refused")
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 2

        events = self._lifecycle_events(tmp_path)
        phase_end = next(event for event in events if event["event"] == "phase_end")
        assert phase_end["phase"] == "seed-materialize:plan-a"
        assert phase_end["outcome"] == "preflight-refused"
        assert phase_end["active_plan_id"] == "plan-a"
        assert phase_end["seed_attempt"] is None
        assert phase_end["backend_attempt"] is None
        assert events[-1]["outcome"] == "preflight-refused"
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_later_row_refusal_keeps_and_reports_earlier_successes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A row that raises after an earlier row already succeeded must not
        discard that row's already-written change, and must not be labeled
        "preflight-refused" — nothing about this run was refused before it
        started; it failed partway through."""
        artifact = self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "missing"})
        )

        def materialize(_slug, row, **_kwargs):
            if row.id == "plan-b":
                raise RoadmapError("row preparation refused")
            return (_materialize_change(row, tmp_path),), None

        monkeypatch.setattr(f"{ROADMAP_MODULE}.materialize_and_diff_one_plan", materialize)
        reports: list[tuple[tuple, tuple]] = []
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report",
            lambda _slug, changes, failures, **_kwargs: reports.append(
                (tuple(changes), tuple(failures))
            )
            or tmp_path / "seed-refresh-report.md",
        )

        assert (
            cmd_roadmap(
                _ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None)
            )
            == roadmap_cmd._RC_PARTIAL
        )

        assert len(reports) == 1
        changes, failures = reports[0]
        assert [change.plan_id for change in changes] == [artifact.plans[0].id]
        assert failures == ()

        events = self._lifecycle_events(tmp_path)
        phase_ends = [event for event in events if event["event"] == "phase_end"]
        assert [event["phase"] for event in phase_ends] == [
            "seed-materialize:plan-a",
            "seed-materialize:plan-b",
        ]
        assert phase_ends[0]["outcome"] == "ok"
        assert phase_ends[1]["outcome"] == "row-refused"
        assert events[-1]["outcome"] == "error"
        assert events[-1]["rc"] == 1
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_surfaces_artifact_and_seed_state_errors_as_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            f"{MODULE}.load_accepted_plans_artifact",
            lambda **_kwargs: (_ for _ in ()).throw(RoadmapArtifactError("broken")),
        )
        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 2

        artifact = _materialize_artifact()
        monkeypatch.setattr(f"{MODULE}.load_accepted_plans_artifact", lambda **_kwargs: artifact)
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapSeedStateError("bad sidecar")
            ),
        )
        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 2

    def test_materialize_surfaces_a_mid_loop_roadmap_error_as_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch,
            _classifications(
                **{"plan-a": DRAFT_SEED_STATE_MISSING, "plan-b": DRAFT_SEED_STATE_MISSING}
            ),
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapArtifactError("stage 2 artifact is malformed")
            ),
        )

        rc = cmd_roadmap(
            _ns(
                tmp_path,
                materialize=roadmap_cmd._MATERIALIZE_ALL,
                from_existing=None,
            )
        )

        assert rc == 2
        assert "stage 2 artifact is malformed" in capsys.readouterr().err

    def test_materialize_interrupt_ends_the_owned_lifecycle_before_exit_130(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(KeyboardInterrupt()),
        )

        assert cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None)) == 130

        events = self._lifecycle_events(tmp_path)
        phase_end = next(event for event in events if event["event"] == "phase_end")
        assert phase_end["outcome"] == "interrupted"
        assert phase_end["active_plan_id"] == "plan-a"
        assert events[-1]["outcome"] == "interrupted"
        assert events[-1]["rc"] == 130
        assert "error" not in events[-1]
        assert events[-1]["active_plan_id"] is None
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_escaping_row_error_records_only_a_safe_error_class(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("SEED-CONTENT-MUST-NOT-LOG")
            ),
        )

        with pytest.raises(RuntimeError, match="SEED-CONTENT-MUST-NOT-LOG"):
            cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None))

        events = self._lifecycle_events(tmp_path)
        failure = next(event for event in events if event["event"] == "attempt_failed")
        phase_end = next(event for event in events if event["event"] == "phase_end")
        assert failure["failure_kind"] == "materialize-error"
        assert failure["active_plan_id"] == "plan-a"
        assert failure["seed_attempt"] is None
        assert failure["backend_attempt"] is None
        assert phase_end["active_plan_id"] == "plan-a"
        assert phase_end["outcome"] == "error"
        assert events[-1]["outcome"] == "error"
        assert events[-1]["rc"] == 1
        assert events[-1]["active_plan_id"] is None
        assert "error" not in events[-1]
        assert "SEED-CONTENT-MUST-NOT-LOG" not in json.dumps(events)
        self._assert_snapshot_removed(tmp_path)

    def test_materialize_report_publication_error_is_command_scoped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._stub_artifact_and_classifications(
            monkeypatch, _classifications(**{"plan-a": "missing", "plan-b": "current"})
        )
        monkeypatch.setattr(
            f"{ROADMAP_MODULE}.materialize_and_diff_one_plan",
            lambda _slug, row, **_kwargs: (
                (_materialize_change(row, tmp_path),),
                None,
            ),
        )
        monkeypatch.setattr(
            f"{MODULE}.write_seed_refresh_report",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RuntimeError("REPORT-CONTENT-MUST-NOT-LOG")
            ),
        )

        with pytest.raises(RuntimeError, match="REPORT-CONTENT-MUST-NOT-LOG"):
            cmd_roadmap(_ns(tmp_path, materialize="plan-a", from_existing=None))

        events = self._lifecycle_events(tmp_path)
        assert [event["event"] for event in events].count("phase_start") == 1
        assert [event["event"] for event in events].count("phase_end") == 1
        assert not any(event["event"] == "attempt_failed" for event in events)
        assert events[-1]["outcome"] == "error"
        assert events[-1]["active_plan_id"] is None
        assert "REPORT-CONTENT-MUST-NOT-LOG" not in json.dumps(events)
        self._assert_snapshot_removed(tmp_path)


class TestAcceptSeedMode:
    def test_cmd_accept_seed_delegates_without_running_other_modes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_args, **_kwargs):
            raise AssertionError("accept-seed must not dispatch another mode")

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom)
        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", boom)
        captured = _stub_accept(
            monkeypatch,
            RoadmapSeedAcceptResult(
                outcome=ACCEPT_OUTCOME_ACCEPTED,
                plan_id="plan-a",
                target=tmp_path / "draft.md",
            ),
        )

        assert (
            cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None))
            == 0
        )
        assert captured == {
            "slug": "my-roadmap",
            "plan_id": "plan-a",
            "repo_root": tmp_path,
            "plans_dir": tmp_path / "docs" / "implementation-plans",
        }

    def test_accept_seed_prints_accepted_target_and_promoted_handoff(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        promoted = tmp_path / "docs" / "implementation-plans" / "plan-seeds" / "plan-a.md"
        _stub_accept(
            monkeypatch,
            RoadmapSeedAcceptResult(
                outcome=ACCEPT_OUTCOME_ACCEPTED,
                plan_id="plan-a",
                target=tmp_path / "drafts" / "plan-a.md",
                promoted_target=promoted,
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None)) == 0
        out = capsys.readouterr().out
        assert "plan-a" in out
        assert "drafts/plan-a.md" in out
        assert "plan-seeds/plan-a.md" in out
        assert "plan-tool create plan-a --from-existing docs/implementation-plans/plan-seeds/plan-a.md" in out

    def test_accept_seed_says_an_unpublished_seeds_existing_file_was_left_untouched(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # promoted_target=None alone reads as "no promoted copy exists"; the
        # existing file the tool deliberately skipped must be named.
        existing = tmp_path / "docs" / "implementation-plans" / "plan-seeds" / "plan-a.md"
        existing.parent.mkdir(parents=True)
        existing.write_text("hand-written\n", encoding="utf-8")
        _stub_accept(
            monkeypatch,
            RoadmapSeedAcceptResult(
                outcome=ACCEPT_OUTCOME_ACCEPTED,
                plan_id="plan-a",
                target=tmp_path / "drafts" / "plan-a.md",
                promoted_target=None,
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None)) == 0
        out = capsys.readouterr().out
        assert "left untouched: docs/implementation-plans/plan-seeds/plan-a.md" in out
        assert "re-synced promoted seed" not in out

    @pytest.mark.parametrize(
        "result, expected",
        (
            (
                RoadmapSeedAcceptResult(
                    outcome=ACCEPT_OUTCOME_REFUSED, plan_id="plan-absent"
                ),
                "no such plan",
            ),
            (
                RoadmapSeedAcceptResult(
                    outcome=ACCEPT_OUTCOME_REFUSED,
                    plan_id="plan-a",
                    state="duplicate",
                    detail="shares a draft basename with plan-b",
                ),
                "shares a draft basename",
            ),
            (
                RoadmapSeedAcceptResult(
                    outcome=ACCEPT_OUTCOME_REFUSED,
                    plan_id="plan-a",
                    violations=(
                        Violation(
                            kind="bad-draft",
                            artifact="draft seed",
                            row_id="plan-a",
                            message="draft references component-missing",
                        ),
                    ),
                ),
                "component-missing",
            ),
        ),
    )
    def test_accept_seed_refusals_render_their_matching_detail_and_return_usage(
        self,
        result: RoadmapSeedAcceptResult,
        expected: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        _stub_accept(monkeypatch, result)

        assert cmd_roadmap(_ns(tmp_path, accept_seed=result.plan_id, from_existing=None)) == 2
        captured = capsys.readouterr()
        assert expected in captured.out + captured.err

    @pytest.mark.parametrize(
        "state",
        ("missing", "stale", "malformed", "path-escaping"),
    )
    def test_accept_seed_refusals_name_materialize_for_regenerable_states(
        self,
        state: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        _stub_accept(
            monkeypatch,
            RoadmapSeedAcceptResult(
                outcome=ACCEPT_OUTCOME_REFUSED,
                plan_id="plan-a",
                state=state,
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None)) == 2
        captured = capsys.readouterr()
        assert "plan-tool roadmap my-roadmap --materialize plan-a" in (
            captured.out + captured.err
        )

    @pytest.mark.parametrize("state", ("duplicate", "current"))
    def test_accept_seed_refusals_skip_materialize_for_nonregenerable_states(
        self,
        state: str,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        _stub_accept(
            monkeypatch,
            RoadmapSeedAcceptResult(
                outcome=ACCEPT_OUTCOME_REFUSED,
                plan_id="plan-a",
                state=state,
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None)) == 2
        captured = capsys.readouterr()
        assert "--materialize" not in captured.out + captured.err

    def test_accept_seed_maps_roadmap_errors_to_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_accept(monkeypatch, RoadmapError("bad sidecar"))

        assert cmd_roadmap(_ns(tmp_path, accept_seed="plan-a", from_existing=None)) == 2
        assert "bad sidecar" in capsys.readouterr().err


class TestApplyMode:
    def test_cmd_stage_run_forwards_an_absent_brief_for_source_resolution(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _stub_run(monkeypatch, _completed())
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, apply=False))
        assert rc == 0
        assert captured["brief_path"] is None

    def test_cmd_apply_delegates_to_apply_roadmap_seeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        run_called: list[str] = []

        def boom(*_args, **_kwargs):
            run_called.append("run")
            raise AssertionError("run_roadmap must not run in apply mode")

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        captured = _stub_apply(
            monkeypatch,
            RoadmapApplyResult(outcome=APPLY_OUTCOME_RECOMMENDED, targets=()),
        )
        cmd_roadmap(_ns(tmp_path, apply=True, from_existing=None))
        assert run_called == []
        assert captured["slug"] == "my-roadmap"
        assert captured["allow_apply"] is True

    def test_cmd_refresh_seeds_delegates_without_running_stages(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, object] = {}

        def boom(*_args, **_kwargs):
            raise AssertionError("run_roadmap must not run in refresh mode")

        def refresh(slug, **kwargs):
            called["slug"] = slug
            called.update(kwargs)
            return RoadmapSeedRefreshResult(outcome=SEED_REFRESH_OUTCOME_APPLIED)

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", refresh)

        assert (
            cmd_roadmap(
                _ns(tmp_path, refresh_seeds=True, from_existing=None)
            )
            == 0
        )
        assert called["slug"] == "my-roadmap"

    def test_cmd_refresh_seeds_partial_outcome_returns_a_distinct_rc(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_refresh = lambda *_args, **_kwargs: RoadmapSeedRefreshResult(
            outcome=SEED_REFRESH_OUTCOME_PARTIAL
        )
        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", _stub_refresh)

        assert (
            cmd_roadmap(
                _ns(tmp_path, refresh_seeds=True, from_existing=None)
            )
            == 3
        )

    def test_cmd_refresh_seeds_exhausted_outcome_returns_rc_one(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_refresh = lambda *_args, **_kwargs: RoadmapSeedRefreshResult(
            outcome=SEED_REFRESH_OUTCOME_EXHAUSTED
        )
        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", _stub_refresh)

        assert (
            cmd_roadmap(
                _ns(tmp_path, refresh_seeds=True, from_existing=None)
            )
            == 1
        )

    def test_cmd_refresh_seeds_reports_each_failed_plans_kind(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        failure = RoadmapSeedRefreshFailure(
            plan_id="plan-auth", failure_kind=FAILURE_GATES
        )
        _stub_refresh = lambda *_args, **_kwargs: RoadmapSeedRefreshResult(
            outcome=SEED_REFRESH_OUTCOME_EXHAUSTED,
            failures=(failure,),
        )
        monkeypatch.setattr(f"{MODULE}.refresh_roadmap_seeds", _stub_refresh)

        cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None))

        err = capsys.readouterr().err
        assert failure.plan_id in err
        assert failure.failure_kind in err

    def test_cmd_stage_run_still_calls_run_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        apply_called: list[str] = []

        def boom(*_args, **_kwargs):
            apply_called.append("apply")
            raise AssertionError("apply_roadmap_seeds must not run in stage mode")

        monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom)
        captured = _stub_run(monkeypatch, _completed())
        cmd_roadmap(_ns(tmp_path, apply=False))
        assert apply_called == []
        assert captured["brief_path"] == tmp_path / "concept.md"

    def test_apply_yes_prints_create_handoff_with_promoted_paths(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_apply_fixtures(tmp_path)
        run_called: list[str] = []

        def boom(*_args, **_kwargs):
            run_called.append("run")
            raise AssertionError("run_roadmap must not run in apply mode")

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        rc = cmd_roadmap(
            _ns(tmp_path, apply=True, yes=True, from_existing=None)
        )
        out = capsys.readouterr().out
        assert rc == 0
        assert run_called == []
        assert "plan-tool create plan-b --from-existing docs/implementation-plans/plan-seeds/plan-b.md" in out
        assert "plan-tool create plan-a --from-existing docs/implementation-plans/plan-seeds/plan-a.md" in out
        assert out.index("plan-tool create plan-b") < out.index(
            "plan-tool create plan-a"
        )

    def test_apply_recommended_prints_preview_and_actuate_hint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        _write_apply_fixtures(tmp_path)
        import plan_tool.roadmap as roadmap_mod

        monkeypatch.setattr(
            f"{MODULE}.run_roadmap",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("stage run")),
        )
        monkeypatch.setattr(roadmap_mod.sys.stdin, "isatty", lambda: False)
        rc = cmd_roadmap(_ns(tmp_path, apply=True, from_existing=None))
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert rc == 0
        assert "seeds/plan-b.md" in combined
        assert "plan-seeds/plan-b.md" in combined
        assert "recommend-only" in combined
        assert "--apply" in combined
        assert "-y" in combined

    def test_apply_refused_prints_collision_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _write_apply_fixtures(tmp_path)
        plan_seeds = tmp_path / "docs" / "implementation-plans" / "plan-seeds"
        plan_seeds.mkdir(parents=True)
        (plan_seeds / "plan-b.md").write_text("existing\n", encoding="utf-8")
        monkeypatch.setattr(
            f"{MODULE}.run_roadmap",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
        )
        rc = cmd_roadmap(
            _ns(tmp_path, apply=True, yes=True, from_existing=None)
        )
        err = capsys.readouterr().err
        assert rc == 2
        assert "plan-seeds/plan-b.md" in err
        assert "nothing was copied" in err

    def test_apply_names_skipped_published_seeds_and_says_nothing_is_left(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        result = RoadmapApplyResult(
            outcome=APPLY_OUTCOME_RECOMMENDED,
            skipped=(("plan-a", tmp_path / "docs" / "implementation-plans" / "plan-seeds" / "plan-a.md"),),
        )
        _stub_apply(monkeypatch, result)

        rc = cmd_roadmap(_ns(tmp_path, apply=True, yes=True, from_existing=None))

        out = capsys.readouterr()
        combined = out.out + out.err
        assert rc == 0
        assert "plan-a: already published, skipped" in combined
        assert "no unpublished seed to promote" in combined
        assert "recommend-only" not in combined

    def test_apply_warns_about_a_stale_published_seed_without_listing_it_refused(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        result = RoadmapApplyResult(
            outcome=APPLY_OUTCOME_RECOMMENDED,
            skipped=(("plan-a", tmp_path / "docs" / "implementation-plans" / "plan-seeds" / "plan-a.md"),),
            stale_published=(DraftSeedClassification(plan_id="plan-a", state="stale"),),
        )
        _stub_apply(monkeypatch, result)

        rc = cmd_roadmap(_ns(tmp_path, apply=True, yes=True, from_existing=None))

        out = capsys.readouterr()
        combined = out.out + out.err
        assert rc == 0
        assert "plan-a: published seed's draft is stale" in combined
        assert "see --refresh-seeds" in combined
        assert "<unknown>" not in combined

    def test_apply_refused_rendering_names_each_classification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        result = RoadmapApplyResult(
            outcome=APPLY_OUTCOME_REFUSED,
            targets=(
                ("plan-a", tmp_path / "draft-a.md", tmp_path / "plan-a.md"),
                ("plan-b", tmp_path / "draft-b.md", tmp_path / "plan-b.md"),
            ),
            refused_drafts=(
                DraftSeedClassification(
                    plan_id="plan-a",
                    state="digest-mismatched",
                    detail="recorded digest differs",
                ),
                DraftSeedClassification(plan_id="plan-b", state="stale"),
            ),
        )
        _stub_apply(monkeypatch, result)

        rc = cmd_roadmap(_ns(tmp_path, apply=True, from_existing=None))

        err = capsys.readouterr().err
        assert rc == 2
        assert "plan-a" in err
        assert "draft-a.md" in err
        assert "digest-mismatched" in err
        assert "recorded digest differs" in err
        assert "plan-b" in err
        assert "stale" in err
        assert "unparseable" not in err

    def test_apply_refused_prints_bijection_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        root = _write_apply_fixtures(tmp_path)
        broken = (root / "04-roadmap.md").read_text(encoding="utf-8")
        # Drop plan-a from ordering while leaving it in plans.
        broken = broken.replace("- plan_id: plan-a\n", "")
        publish_accepted_root(
            tmp_path / "docs" / "implementation-plans",
            "my-roadmap",
            with_minimal_upstream(broken),
        )
        monkeypatch.setattr(
            f"{MODULE}.run_roadmap",
            lambda *_a, **_k: (_ for _ in ()).throw(AssertionError()),
        )
        rc = cmd_roadmap(
            _ns(tmp_path, apply=True, yes=True, from_existing=None)
        )
        err = capsys.readouterr().err
        assert rc == 2
        assert "nothing was copied" in err
        assert "plan-a" in err
        assert "ordering" in err

    def test_four_stage_run_still_does_not_touch_plan_seeds(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo_seeds = tmp_path / "docs" / "implementation-plans" / "plan-seeds"
        repo_seeds.mkdir(parents=True)
        marker = repo_seeds / "marker.md"
        marker.write_text("untouched\n", encoding="utf-8")
        _stub_run(monkeypatch, _four_stage_completed(tmp_path))
        assert cmd_roadmap(_ns(tmp_path, apply=False)) == 0
        assert marker.read_text(encoding="utf-8") == "untouched\n"


# --------------------------------------------------------------------------
# Read-only mode (--view)
# --------------------------------------------------------------------------


def _stub_load_roadmap(monkeypatch: pytest.MonkeyPatch, result_or_exc) -> dict:
    """Replace ``load_roadmap`` with a recorder; return the captured call."""
    captured: dict = {}

    def fake(plans_dir, slug, *, mode=MODE_CURRENT):
        captured["plans_dir"] = plans_dir
        captured["slug"] = slug
        captured["mode"] = mode
        if isinstance(result_or_exc, BaseException):
            raise result_or_exc
        return result_or_exc

    monkeypatch.setattr(f"{MODULE}.load_roadmap", fake)
    return captured


def _loaded(*, directory_exists: bool = True) -> SimpleNamespace:
    """A stand-in for ``LoadedRoadmap``: ``_cmd_roadmap_view`` reads only
    ``directory_exists`` off what ``load_roadmap`` returns before handing it,
    untouched, to a (stubbed) render function."""
    return SimpleNamespace(
        directory_exists=directory_exists, plans=None, slug="my-roadmap"
    )


def _stub_render(monkeypatch: pytest.MonkeyPatch, name: str, text: str = "rendered text") -> dict:
    """Replace one of the three render functions with a recorder."""
    captured: dict = {}

    def fake(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return text

    monkeypatch.setattr(f"{MODULE}.{name}", fake)
    return captured


class TestViewValidation:
    """``--mode``/``--id`` are meaningful only alongside ``--view``; argparse's
    mutually-exclusive-group machinery cannot express that, so ``cmd_roadmap``
    checks it by hand, ahead of every dispatch branch.
    """

    def test_mode_without_view_is_rejected(
        self, tmp_path: Path, capsys
    ) -> None:
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, mode="review"))
        assert rc == 2
        err = capsys.readouterr().err
        assert "--mode" in err
        assert "--view" in err

    def test_id_without_view_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, id="entity-1"))
        assert rc == 2
        err = capsys.readouterr().err
        assert "--id" in err
        assert "--view" in err

    def test_id_with_view_walk_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="walk", id="entity-1")
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--id is only valid with --view index" in err
        assert "requires --view" not in err

    def test_id_with_view_ledger_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="ledger", id="entity-1")
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "--id is only valid with --view index" in err
        assert "requires --view" not in err

    def test_id_with_view_summary_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(
            _ns(tmp_path, view="summary", id="entity-1", from_existing=None)
        )
        assert rc == 2
        assert "--id is only valid with --view index" in capsys.readouterr().err

    def test_id_with_view_seeds_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(
            _ns(tmp_path, view="seeds", id="plan-1", from_existing=None)
        )
        assert rc == 2
        assert "--id is only valid with --view index" in capsys.readouterr().err

    def test_mode_rejected_even_when_apply_is_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """Proves the validation runs ahead of the ``--apply`` branch, not
        only ahead of the stage-run branch — an ordinary CLI parse can never
        produce this combination (``--mode`` sits outside the mutually
        exclusive group), but a caller building the ``Namespace`` by hand can.
        """

        def boom(*_a, **_k):
            raise AssertionError("apply_roadmap_seeds must not run")

        monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom)
        rc = cmd_roadmap(
            _ns(tmp_path, apply=True, from_existing=None, mode="review")
        )
        assert rc == 2
        assert "--mode" in capsys.readouterr().err


class TestViewDispatch:
    def test_view_summary_calls_summary_renderer_with_lifecycle_snapshot(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = SimpleNamespace(
            plans=(SimpleNamespace(id="plan-summary"),)
        )
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_roadmap_summary")
        classifications = {
            "plan-summary": DraftSeedClassification(
                plan_id="plan-summary", state="current"
            )
        }
        classifier_calls: dict = {}

        def classify(artifact, **kwargs):
            classifier_calls["artifact"] = artifact
            classifier_calls.update(kwargs)
            return classifications

        monkeypatch.setattr(f"{MODULE}.classify_draft_seeds", classify)

        cmd_roadmap(_ns(tmp_path, view="summary", from_existing=None))

        assert captured["args"][0] is loaded
        assert len(captured["args"]) == 2
        assert classifier_calls == {
            "artifact": loaded.plans,
            "plans_dir": tmp_path.resolve() / "docs" / "implementation-plans",
            "slug": loaded.slug,
        }
        assert captured["args"][1].classifications is classifications

    def test_view_summary_renders_a_classifier_sidecar_error_as_unavailable(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = object()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_roadmap_summary")
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapSeedStateError("bad sidecar")
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, view="summary", from_existing=None)) == 0
        assert captured["args"][1].reason == "bad sidecar"

    def test_view_walk_passes_the_classification(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = SimpleNamespace(plans=(SimpleNamespace(id="plan-walk"),))
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_traceability_walk")
        classifications = {
            "plan-walk": DraftSeedClassification(plan_id="plan-walk", state="current")
        }
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds", lambda *_args, **_kwargs: classifications
        )
        cmd_roadmap(_ns(tmp_path, view="walk", from_existing=None))
        assert captured["args"] == (
            loaded,
            tmp_path.resolve() / "docs" / "implementation-plans",
            classifications,
        )

    def test_view_walk_folds_a_corrupt_sidecar_into_an_unavailable_reason(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = object()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_traceability_walk")
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapSeedStateError("bad sidecar")
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, view="walk", from_existing=None)) == 0
        assert captured["args"] == (
            loaded,
            tmp_path.resolve() / "docs" / "implementation-plans",
            {},
        )
        assert captured["kwargs"] == {"unavailable_reason": "bad sidecar"}

    def test_view_seeds_dispatches_to_the_seeds_renderer_and_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = SimpleNamespace(plans=(SimpleNamespace(id="plan-missing"),))
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_seed_state_view")
        classifications = {
            "plan-missing": DraftSeedClassification(
                plan_id="plan-missing", state="missing"
            )
        }
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds", lambda *_args, **_kwargs: classifications
        )
        orphan_records = (object(),)
        monkeypatch.setattr(
            f"{MODULE}.find_orphan_seed_records",
            lambda *_args, **_kwargs: orphan_records,
        )

        assert cmd_roadmap(_ns(tmp_path, view="seeds", from_existing=None)) == 0
        assert captured["args"] == (loaded, classifications, orphan_records)

    def test_view_seeds_folds_a_corrupt_sidecar_into_an_unavailable_line(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        loaded.plans = object()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_seed_state_view")
        monkeypatch.setattr(
            f"{MODULE}.classify_draft_seeds",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                RoadmapSeedStateError("bad sidecar")
            ),
        )

        assert cmd_roadmap(_ns(tmp_path, view="seeds", from_existing=None)) == 0
        assert captured["args"] == (loaded, {}, ())
        assert captured["kwargs"] == {"unavailable_reason": "bad sidecar"}

    def test_view_ledger_calls_render_decision_ledger_with_loaded_only(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_decision_ledger")
        cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None))
        assert captured["args"] == (loaded,)

    def test_view_index_calls_the_reverse_index_render_with_loaded_and_id(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_reverse_index")
        cmd_roadmap(
            _ns(tmp_path, view="index", id="entity-1", from_existing=None)
        )
        assert captured["args"] == (loaded, "entity-1")

    def test_view_index_without_id_passes_none_for_the_full_map(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_reverse_index")
        cmd_roadmap(_ns(tmp_path, view="index", from_existing=None))
        assert captured["args"] == (loaded, None)

    def test_view_mode_defaults_to_current_when_mode_flag_omitted(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_traceability_walk")
        cmd_roadmap(_ns(tmp_path, view="walk", from_existing=None))
        assert captured["mode"] == MODE_CURRENT

    def test_view_mode_review_reaches_load_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured = _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_traceability_walk")
        cmd_roadmap(
            _ns(tmp_path, view="walk", mode=MODE_REVIEW, from_existing=None)
        )
        assert captured["mode"] == MODE_REVIEW

    def test_view_prints_the_rendered_text_to_stdout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(
            monkeypatch, "render_decision_ledger", text="ledger body\nsecond line"
        )
        cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None))
        out = capsys.readouterr().out
        assert "Roadmap view · Decision ledger" in out
        assert "ledger body\nsecond line" in out

    def test_view_returns_zero_when_directory_exists(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded(directory_exists=True))
        _stub_render(monkeypatch, "render_decision_ledger")
        assert cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None)) == 0

    def test_view_without_a_published_version_returns_two_naming_the_roadmap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(
            monkeypatch,
            NoPublishedRoadmapVersionError(
                "roadmap 'my-roadmap' has no published version"
            ),
        )
        rc = cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None))
        assert rc == 2
        assert "my-roadmap" in capsys.readouterr().err


class TestLeftoverTopLevelArtifactsWarning:
    """Top-level 0N-*.md beside an accepted head are inert; name them (BUG_BACKLOG)."""

    _SLUG = "my-roadmap"

    def _folder(self, tmp_path: Path, *, head: bool, leftovers: tuple[str, ...]) -> Path:
        from plan_tool.roadmap_artifacts import roadmap_dir
        from plan_tool.roadmap_versions import accepted_head_path

        plans_dir = tmp_path / "docs" / "implementation-plans"
        folder = roadmap_dir(plans_dir, self._SLUG)
        folder.mkdir(parents=True)
        for name in leftovers:
            (folder / name).write_text("stale\n", encoding="utf-8")
        if head:
            marker = accepted_head_path(plans_dir, self._SLUG)
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("{}", encoding="utf-8")
        return plans_dir

    def _refresh_ok(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            f"{MODULE}.refresh_roadmap_seeds",
            lambda *_a, **_k: RoadmapSeedRefreshResult(outcome=SEED_REFRESH_OUTCOME_APPLIED),
        )

    def test_refresh_names_each_leftover_beside_an_accepted_head(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._folder(tmp_path, head=True, leftovers=("01-domain.md", "04-roadmap.md"))
        self._refresh_ok(monkeypatch)

        rc = cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None))

        err = capsys.readouterr().err
        assert rc == 0
        assert "01-domain.md, 04-roadmap.md" in err
        assert "02-constraints.md" not in err
        assert "files 01-domain.md, 04-roadmap.md are beside" in err

    def test_view_warns_on_stderr_and_leaves_the_rendered_view_alone(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._folder(tmp_path, head=True, leftovers=("04-roadmap.md",))
        _stub_load_roadmap(monkeypatch, _loaded())
        monkeypatch.setattr(f"{MODULE}.render_roadmap_summary", lambda *_a, **_k: "SUMMARY-BODY")

        rc = cmd_roadmap(_ns(tmp_path, view="summary", from_existing=None))

        out, err = capsys.readouterr()
        assert rc == 0
        assert "file 04-roadmap.md is beside" in err
        assert "04-roadmap.md" not in out

    def test_materialize_route_warns(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._folder(tmp_path, head=True, leftovers=("03-components.md",))
        monkeypatch.setattr(
            f"{MODULE}._cmd_roadmap_materialize_owned", lambda *_a, **_k: 0
        )
        monkeypatch.setattr(
            f"{MODULE}._roadmap_writer_owner", lambda *_a, **_k: contextlib.nullcontext(object())
        )

        rc = cmd_roadmap(_ns(tmp_path, materialize=roadmap_cmd._MATERIALIZE_ALL, from_existing=None))

        assert rc == 0
        assert "03-components.md" in capsys.readouterr().err

    @pytest.mark.parametrize(
        ("flags", "target"),
        (
            ({"accept_seed": "plan-a"}, "accept_roadmap_seed"),
            ({"apply": True, "yes": True}, "apply_roadmap_seeds"),
        ),
    )
    def test_accept_and_apply_routes_warn_even_when_the_operation_refuses(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, flags, target
    ) -> None:
        # These are the routes that hand a draft seed on to `create`; the
        # warning fires before the operation, so a refusal still names the files.
        self._folder(tmp_path, head=True, leftovers=("04-roadmap.md",))

        def refuse(*_a, **_k):
            raise RoadmapError("refused for the test")

        monkeypatch.setattr(f"{MODULE}.{target}", refuse)

        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, **flags))

        assert rc == 2
        assert "file 04-roadmap.md is beside" in capsys.readouterr().err

    def test_a_folder_without_leftovers_is_silent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        self._folder(tmp_path, head=True, leftovers=())
        self._refresh_ok(monkeypatch)

        assert cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None)) == 0

        assert "inert leftovers" not in capsys.readouterr().err

    def test_a_headless_folder_is_not_warned_about_the_refusal_already_names_them(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # Deliberately not warned: without an accepted head the files are not
        # "beside" one, and the no-published-version refusal already names them.
        self._folder(tmp_path, head=False, leftovers=("04-roadmap.md",))
        self._refresh_ok(monkeypatch)

        cmd_roadmap(_ns(tmp_path, refresh_seeds=True, from_existing=None))

        assert "inert leftovers" not in capsys.readouterr().err


@pytest.mark.parametrize("view", ("summary", "walk", "ledger", "index", "seeds", "html"))
def test_every_view_refuses_on_a_folder_with_no_accepted_head(
    tmp_path: Path, capsys, view: str
) -> None:
    """Deliberate: no view degrades to a partial read of top-level files; one refusal covers all six."""
    plans_dir = tmp_path / "docs" / "implementation-plans"
    leftover = domain_path(plans_dir, "my-roadmap")
    leftover.parent.mkdir(parents=True)
    leftover.write_text(
        render_domain_artifact(
            DomainArtifact(
                entities=(EntityRow("ent-order", "Order", ()),),
                business_rules=(),
                workflows=(),
                decisions=(),
                body="# Top-level leftover.\n",
            )
        ),
        encoding="utf-8",
    )

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view=view, plans_dir=plans_dir))

    assert rc == 2
    assert "no published version" in capsys.readouterr().err
    assert not roadmap_cmd.review_path(plans_dir, "my-roadmap").exists()


# --------------------------------------------------------------------------
#   Confirmed feedback reopen and decision settlement
# --------------------------------------------------------------------------


def _decision_settlement_args(tmp_path: Path, **overrides) -> argparse.Namespace:
    decision = "domain:decision-order"
    evidence = "domain:feedback-order"
    values = {
        "from_existing": None,
        "settle_decision": decision,
        "settlement_evidence": evidence,
        "confirm_decision_settlement": True,
        "_settle_decision_occurrences": (decision,),
        "_settlement_evidence_occurrences": (evidence,),
        "_confirm_decision_settlement_occurrences": (True,),
    }
    values.update(overrides)
    return _ns(tmp_path, **values)


def test_settle_decision_dispatches_to_the_enrolled_runner_directly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Deliberate: there is no un-enrolled runner and no fallback to attempt first, so the
    handler neither imports nor calls one and calls the enrolled runner exactly once."""
    captured: dict[str, object] = {}
    calls: list[str] = []
    decision = "UNSAFE DECISION SELECTOR MUST NOT ECHO"
    evidence = "UNSAFE EVIDENCE SELECTOR MUST NOT ECHO"

    def enrolled_runner(*received, **kwargs):
        calls.append("enrolled")
        captured["received"] = received
        captured.update(kwargs)
        return DecisionSettlementRunResult("settled", 0, None, "receipt-final-id")

    def unexpected(*_args, **_kwargs):
        pytest.fail("decision settlement must not enter another roadmap action")

    assert not hasattr(roadmap_cmd, "run_unenrolled_decision_settlement")
    monkeypatch.setattr(roadmap_cmd, "run_enrolled_decision_settlement", enrolled_runner)
    for name in (
        "run_roadmap",
        "_cmd_roadmap_view",
    ):
        monkeypatch.setattr(roadmap_cmd, name, unexpected)

    assert cmd_roadmap(
        _decision_settlement_args(
            tmp_path,
            settle_decision=decision,
            settlement_evidence=evidence,
            _settle_decision_occurrences=(decision,),
            _settlement_evidence_occurrences=(evidence,),
        )
    ) == 0
    assert calls == ["enrolled"]
    assert captured["received"] == ("my-roadmap", decision, evidence, True)
    assert "repo_root" not in captured
    assert captured["plans_dir"] == tmp_path / "docs" / "implementation-plans"
    assert captured["mode_rejected"] is False
    output = capsys.readouterr().out
    assert output.strip() == "decision settlement: settled\nreceipt: receipt-final-id"
    assert decision not in output
    assert evidence not in output


def test_settle_decision_without_accepted_head_exits_2(tmp_path: Path, capsys) -> None:
    """The real enrolled runner refuses a folder with no head; the handler names the missing version."""
    plans_dir = tmp_path / "docs" / "implementation-plans"
    leftover = domain_path(plans_dir, "my-roadmap")
    leftover.parent.mkdir(parents=True)
    leftover.write_text("top-level leftover\n", encoding="utf-8")

    assert cmd_roadmap(_decision_settlement_args(tmp_path)) == 2

    captured = capsys.readouterr()
    assert "no published version" in captured.err
    assert "unenrolled" not in captured.out + captured.err


@pytest.mark.parametrize(
    "result",
    (
        DecisionSettlementRunResult("preflight-rejected", 2, "missing-decision"),
        DecisionSettlementRunResult("preflight-rejected", 2, "decision-not-pending"),
        DecisionSettlementRunResult("preflight-rejected", 2, "source-changed", "receipt-id"),
        DecisionSettlementRunResult("write-failed", 1, None, "receipt-id"),
        DecisionSettlementRunResult("receipt-rejected", 1, "commit-failed"),
    ),
    ids=(
        "missing-decision",
        "decision-not-pending",
        "source-changed",
        "write-failed",
        "receipt-rejected",
    ),
)
def test_decision_settlement_returns_the_enrolled_runner_status_for_every_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, result: DecisionSettlementRunResult
) -> None:
    monkeypatch.setattr(
        roadmap_cmd, "run_enrolled_decision_settlement", lambda *_args, **_kwargs: result
    )

    assert cmd_roadmap(_decision_settlement_args(tmp_path)) == result.status


@pytest.mark.parametrize(
    "overrides",
    (
        {"settle_decision": None, "_settle_decision_occurrences": ()},
        {
            "settle_decision": "domain:decision-b",
            "_settle_decision_occurrences": ("domain:decision-a", "domain:decision-b"),
        },
        {"settlement_evidence": None, "_settlement_evidence_occurrences": ()},
        {
            "settlement_evidence": "domain:feedback-b",
            "_settlement_evidence_occurrences": ("domain:feedback-a", "domain:feedback-b"),
        },
        {"confirm_decision_settlement": None, "_confirm_decision_settlement_occurrences": ()},
        {"_confirm_decision_settlement_occurrences": (True, True)},
    ),
    ids=(
        "missing-decision",
        "repeated-decision",
        "missing-evidence",
        "repeated-evidence",
        "missing-confirmation",
        "repeated-confirmation",
    ),
)
def test_decision_settlement_incomplete_or_repeated_triple_reaches_only_settlement_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
) -> None:
    captured: dict[str, object] = {}

    def runner(*_args, **kwargs):
        captured.update(kwargs)
        return DecisionSettlementRunResult("preflight-rejected", 2, "mode-rejected")

    def unexpected(*_args, **_kwargs):
        pytest.fail("invalid decision settlement must not fall through to another action")

    monkeypatch.setattr(roadmap_cmd, "run_enrolled_decision_settlement", runner)
    monkeypatch.setattr(roadmap_cmd, "run_roadmap", unexpected)

    assert cmd_roadmap(_decision_settlement_args(tmp_path, **overrides)) == 2
    assert captured["mode_rejected"] is True


def test_decision_settlement_confirmation_required_takes_precedence_over_mode_rejected(
    tmp_path: Path, capsys
) -> None:
    """Confirmation absence must win over an incomplete/repeated triple: the
    runner checks confirmation before mode_rejected unconditionally, so this
    stays true even when a selector is also missing at the same time."""
    args = _decision_settlement_args(
        tmp_path,
        settle_decision=None,
        _settle_decision_occurrences=(),
        confirm_decision_settlement=None,
        _confirm_decision_settlement_occurrences=(),
    )

    assert cmd_roadmap(args) == 2

    output = capsys.readouterr().out
    assert output == "decision settlement: preflight-rejected\nreason: confirmation-required\n"


@pytest.mark.parametrize(
    "overrides",
    (
        {"revise_feedback": "domain:feedback-local"},
        {"view": "summary", "_roadmap_mode_occurrences": (("--view", "summary"),)},
        {"yes": True},
        {"from_existing": Path("brief.md")},
        {"apply": True, "_roadmap_mode_occurrences": (("--apply", True),)},
        {"mode": "review"},
        {"id": "row-a"},
    ),
    ids=(
        "local-revision",
        "view",
        "yes",
        "brief",
        "broad-mode",
        "view-mode",
        "view-id",
    ),
)
def test_decision_settlement_rejects_every_companion_mode_without_other_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    overrides: dict[str, object],
) -> None:
    captured: dict[str, object] = {}

    def runner(*_args, **kwargs):
        captured.update(kwargs)
        return DecisionSettlementRunResult("preflight-rejected", 2, "mode-rejected")

    def unexpected(*_args, **_kwargs):
        pytest.fail("decision settlement must own every parseable companion conflict")

    monkeypatch.setattr(roadmap_cmd, "run_enrolled_decision_settlement", runner)
    for name in (
        "run_roadmap",
        "_cmd_roadmap_view",
    ):
        monkeypatch.setattr(roadmap_cmd, name, unexpected)

    assert cmd_roadmap(_decision_settlement_args(tmp_path, **overrides)) == 2
    assert captured["mode_rejected"] is True


def test_existing_exclusive_mode_predicates_reject_the_decision_settlement_triple(
    tmp_path: Path,
) -> None:
    settlement = {
        "settle_decision": "domain:decision-order",
        "settlement_evidence": "domain:feedback-order",
        "confirm_decision_settlement": True,
        "_settle_decision_occurrences": ("domain:decision-order",),
        "_settlement_evidence_occurrences": ("domain:feedback-order",),
        "_confirm_decision_settlement_occurrences": (True,),
    }

    assert roadmap_cmd._revise_feedback_has_conflict(
        _ns(tmp_path, revise_feedback="domain:feedback-order", **settlement)
    )
    assert roadmap_cmd._candidate_lifecycle_has_conflict(
        _ns(
            tmp_path,
            propose_candidate=True,
            _propose_candidate_occurrences=(True,),
            **settlement,
        )
    )


def test_decision_settlement_does_not_treat_yes_as_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def runner(*_args, **kwargs):
        captured.update(kwargs)
        return DecisionSettlementRunResult("preflight-rejected", 2, "confirmation-required")

    monkeypatch.setattr(roadmap_cmd, "run_enrolled_decision_settlement", runner)
    assert cmd_roadmap(
        _decision_settlement_args(
            tmp_path,
            confirm_decision_settlement=None,
            _confirm_decision_settlement_occurrences=(),
            yes=True,
        )
    ) == 2
    assert captured["mode_rejected"] is True


def test_bad_slug_under_view_mode_returns_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    _stub_load_roadmap(
        monkeypatch, ValueError("'bad slug' is not a valid roadmap slug")
    )
    rc = cmd_roadmap(
        _ns(tmp_path, view="ledger", slug="bad slug", from_existing=None)
    )
    assert rc == 2
    assert "not a valid roadmap slug" in capsys.readouterr().err


def test_view_mode_never_calls_run_roadmap_or_apply_roadmap_seeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom_run(*_a, **_k):
        raise AssertionError("run_roadmap must not run in view mode")

    def boom_apply(*_a, **_k):
        raise AssertionError("apply_roadmap_seeds must not run in view mode")

    monkeypatch.setattr(f"{MODULE}.run_roadmap", boom_run)
    monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom_apply)
    _stub_load_roadmap(monkeypatch, _loaded())
    _stub_render(monkeypatch, "render_decision_ledger")
    assert cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None)) == 0


def test_apply_and_stage_run_paths_are_unaffected_by_the_new_flags(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = _stub_run(monkeypatch, _completed())
    assert cmd_roadmap(_ns(tmp_path)) == 0
    assert captured["slug"] == "my-roadmap"

    captured_apply = _stub_apply(
        monkeypatch,
        RoadmapApplyResult(outcome=APPLY_OUTCOME_RECOMMENDED, targets=()),
    )
    assert cmd_roadmap(_ns(tmp_path, apply=True, from_existing=None)) == 0
    assert captured_apply["slug"] == "my-roadmap"


def test_view_over_a_real_missing_roadmap_directory_returns_two_without_stubbing(
    tmp_path: Path, capsys
) -> None:
    """Run one real load to keep the directory-existence contract grounded."""
    rc = cmd_roadmap(_ns(tmp_path, view="ledger", from_existing=None))
    assert rc == 2
    assert "my-roadmap" in capsys.readouterr().err


# --------------------------------------------------------------------------
# ``--compare``
# --------------------------------------------------------------------------


def test_comparison_parser_preserves_closed_selectors() -> None:
    """Keep comparison selection separate from broad roadmap modes."""
    args = _parse(
        "roadmap",
        "my-roadmap",
        "--compare",
        "--comparison-base",
        "root-1",
        "--comparison-target",
        "candidate-2",
        "--comparison-output",
        "json",
    )

    assert args.compare is True
    assert args.comparison_base == "root-1"
    assert args.comparison_target == "candidate-2"
    assert args.comparison_output == "json"
    assert args._roadmap_mode_occurrences == ()


def test_comparison_default_target_uses_the_read_only_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Omitted selectors reach the library as None; it resolves head and active candidate."""
    received: dict[str, object] = {}
    comparison = object()

    def run_comparison(**kwargs):
        received.update(kwargs)
        return comparison

    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", run_comparison)
    monkeypatch.setattr(roadmap_cmd, "render_terminal_comparison", lambda run: "cards\n")

    assert cmd_roadmap(_ns(tmp_path, compare=True, from_existing=None)) == 0
    assert received == {
        "plans_dir": tmp_path / "docs" / "implementation-plans",
        "slug": "my-roadmap",
        "base_version_id": None,
        "target_version_id": None,
    }
    assert capsys.readouterr().out == "cards\n"


def test_comparison_no_active_candidate_refusal_exits_usage_with_message(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    def refuse(**_kwargs):
        raise roadmap_cmd.RoadmapComparisonRunError(
            "no candidate is active to compare against; pass --comparison-target VERSION_ID"
        )

    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", refuse)

    assert cmd_roadmap(_ns(tmp_path, compare=True, from_existing=None)) == 2
    assert "--comparison-target" in capsys.readouterr().err


def test_comparison_no_published_version_error_exits_usage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    from plan_tool.roadmap_seed_manifest import NoPublishedRoadmapVersionError

    def refuse(**_kwargs):
        raise NoPublishedRoadmapVersionError("roadmap 'my-roadmap' has no published version")

    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", refuse)

    assert cmd_roadmap(_ns(tmp_path, compare=True, from_existing=None)) == 2
    assert "no published version" in capsys.readouterr().err


def test_compare_help_describes_active_candidate_default() -> None:
    _, subparsers = _roadmap_parser()
    register(subparsers)
    helps = {
        option: " ".join(action.help.split())
        for action in subparsers.choices["roadmap"]._actions
        for option in action.option_strings
        if option in {"--compare", "--comparison-target"}
    }

    assert set(helps) == {"--compare", "--comparison-target"}
    for text in helps.values():
        assert "active candidate" in text
        assert "working roadmap" not in text


def test_comparison_explicit_stored_selectors_reach_the_operation_unchanged(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass stored version selectors straight through without CLI interpretation."""
    received: dict[str, object] = {}
    monkeypatch.setattr(
        roadmap_cmd,
        "run_roadmap_comparison",
        lambda **kwargs: received.update(kwargs) or object(),
    )
    monkeypatch.setattr(roadmap_cmd, "render_terminal_comparison", lambda run: "")

    assert cmd_roadmap(
        _ns(
            tmp_path,
            compare=True,
            comparison_base="root-1",
            comparison_target="candidate-2",
            from_existing=None,
        )
    ) == 0
    assert received["base_version_id"] == "root-1"
    assert received["target_version_id"] == "candidate-2"


@pytest.mark.parametrize(
    ("comparison_output", "renderer_name", "expected"),
    (
        ("cards", "render_terminal_comparison", "cards\n"),
        ("patch", "render_patch_comparison", "complete patch\n"),
        ("json", "render_comparison_json", '{"comparison":true}\n'),
    ),
)
def test_comparison_prints_the_selected_renderer_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys,
    comparison_output: str,
    renderer_name: str,
    expected: str,
) -> None:
    """Keep renderer output, including raw patch and JSON framing, intact."""
    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", lambda **_kwargs: object())
    for name in ("render_terminal_comparison", "render_patch_comparison", "render_comparison_json"):
        monkeypatch.setattr(roadmap_cmd, name, lambda _run, name=name: expected if name == renderer_name else (_ for _ in ()).throw(AssertionError(name)))

    assert cmd_roadmap(
        _ns(tmp_path, compare=True, comparison_output=comparison_output, from_existing=None)
    ) == 0
    assert capsys.readouterr().out == expected


def test_comparison_renderer_invariant_failure_is_a_clean_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A renderer's internal invariant check (bare ValueError/TypeError) must
    return the same clean usage error as a RoadmapComparisonRunError, not
    crash — the comparison feature narrows every error to one CLI contract."""
    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", lambda **_kwargs: object())
    monkeypatch.setattr(
        roadmap_cmd,
        "render_terminal_comparison",
        lambda _run: (_ for _ in ()).throw(ValueError("comparison value is not JSON-safe")),
    )

    assert cmd_roadmap(_ns(tmp_path, compare=True, from_existing=None)) == 2
    assert "not JSON-safe" in capsys.readouterr().err


def test_comparison_refusal_returns_usage_without_rendering(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Keep an absent accepted-head refusal visible without a CLI fallback."""
    def refuse(**_kwargs):
        raise roadmap_cmd.RoadmapComparisonRunError("comparison base requires an accepted roadmap version")

    monkeypatch.setattr(roadmap_cmd, "run_roadmap_comparison", refuse)
    monkeypatch.setattr(
        roadmap_cmd,
        "render_terminal_comparison",
        lambda _run: (_ for _ in ()).throw(AssertionError("refusals do not render")),
    )

    assert cmd_roadmap(_ns(tmp_path, compare=True, from_existing=None)) == 2
    assert "accepted roadmap version" in capsys.readouterr().err


def test_comparison_rejects_companion_modes_before_comparison_loading(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Reject lifecycle and broad-mode companions before any comparison work."""
    monkeypatch.setattr(
        roadmap_cmd,
        "run_roadmap_comparison",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("comparison must not load")),
    )

    assert cmd_roadmap(_ns(tmp_path, compare=True, apply=True, from_existing=None)) == 2
    assert "--compare accepts no companion roadmap options" in capsys.readouterr().err


def test_comparison_companion_option_without_compare_names_the_missing_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """A companion selector alone (no ``--compare``) gets its own clear refusal,
    not the "accepts no companion options" message meant for a real conflict."""
    monkeypatch.setattr(
        roadmap_cmd,
        "run_roadmap_comparison",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("comparison must not load")),
    )

    assert cmd_roadmap(
        _ns(tmp_path, compare=None, comparison_base="root-1", from_existing=None)
    ) == 2
    assert (
        "--comparison-base/--comparison-target/--comparison-output require --compare"
        in capsys.readouterr().err
    )


# --------------------------------------------------------------------------
# ``--view html`` and its ``--output`` companion
# --------------------------------------------------------------------------


def _publish_real_domain_root(plans_dir: Path) -> None:
    """Publish an accepted root whose domain artifact carries one real entity."""
    domain_text = render_domain_artifact(
        DomainArtifact(
            entities=(EntityRow("ent-order", "Order", ()),),
            business_rules=(),
            workflows=(),
            decisions=(),
            body="# Real pipeline check.\n",
        )
    )
    texts = with_minimal_upstream(render_plans_artifact(PlansArtifact(
        plans=(), ordering=(), assumptions=(), decisions=(), body="# Plans\n"
    )))
    publish_accepted_root(plans_dir, "my-roadmap", (domain_text, *texts[1:]))


class TestHtmlView:
    """The one view whose text is a document rather than a report: it must
    bypass the shared banner/ANSI framing, and it is the only view ``--output``
    is valid with."""

    def test_output_without_view_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, output=str(tmp_path / "p.html")))
        assert rc == 2
        err = capsys.readouterr().err
        assert "--output" in err
        assert "--view html" in err

    @pytest.mark.parametrize("view", ("summary", "walk", "ledger", "index", "seeds"))
    def test_output_with_any_other_ordinary_view_is_rejected(
        self, tmp_path: Path, capsys, view: str
    ) -> None:
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view=view, output=str(tmp_path / "p.html"))
        )
        assert rc == 2
        assert "--output is only valid with --view html" in capsys.readouterr().err

    def test_output_dash_prints_the_document_without_the_shared_banner(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # ``render_roadmap_view`` would prepend "Roadmap view · …" and a
        # divider; either would make the printed bytes invalid HTML.
        # ``--output -`` is the escape hatch back to stdout now that no
        # ``--output`` at all means "write the default file", not "print".
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n<html></html>\n")

        def unexpected(*_a, **_k):
            raise AssertionError("the html view must not be framed")

        monkeypatch.setattr(f"{MODULE}.render_roadmap_view", unexpected)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output="-"))
        assert rc == 0
        assert capsys.readouterr().out == "<!DOCTYPE html>\n<html></html>\n"

    def test_no_output_writes_the_default_review_file_in_the_roadmap_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # The premise of defaulting to a file: a roadmap review page is
        # meant to be opened (and printed), not piped, so omitting
        # ``--output`` now writes rather than prints.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html"))
        assert rc == 0
        expected = roadmap_cmd.review_path(resolve_output_dir(tmp_path), "my-roadmap")
        assert expected.read_text() == "<!DOCTYPE html>\n"
        out = capsys.readouterr().out
        assert "review.html" in out
        assert "<!DOCTYPE" not in out

    def test_output_writes_the_document_and_reports_the_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        destination = tmp_path / "nested" / "review.html"
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output=str(destination)))
        assert rc == 0
        assert destination.read_text() == "<!DOCTYPE html>\n"
        out = capsys.readouterr().out
        assert "review.html" in out
        assert "<!DOCTYPE" not in out

    def test_an_unwritable_destination_reports_incomplete_not_usage(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # The arguments were valid and the document rendered; only the disk
        # write failed. That is a failure-to-complete (1). Returning the
        # pre-flight code (2) would tell an operator — and CI — that they
        # passed something invalid, and retrying with corrected arguments
        # would hit the same failure.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        blocker = tmp_path / "blocker"
        blocker.write_text("not a directory")
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="html", output=str(blocker / "p.html"))
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "<!DOCTYPE" not in captured.out
        assert "could not write" in captured.err

    @pytest.mark.parametrize("bad", (".", "..", "/", "DIR", "TRAILING"))
    def test_every_directory_destination_is_one_usage_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, bad: str
    ) -> None:
        """One message and one exit code for every value that cannot name a
        file.

        Left to the write these diverge by accident of pathlib: ``.`` and
        ``/`` raise ValueError — which escapes to the global crash handler and
        tells the operator to report a traceback for their own typo — while
        ``..`` and an existing directory raise OSError, reporting the same
        mistake as a failure-to-complete. The parametrization is the point:
        fixing only the reported input leaves the siblings inconsistent.

        ``TRAILING`` is the fourth way to say "directory" and the one
        pathlib itself cannot see: a trailing separator on a path that does
        not exist yet (``newdir/``) survives every check on the normalized
        ``Path`` — ``.name`` and ``.is_dir()`` both see an ordinary,
        available filename — so it must be caught on the raw string before
        normalization drops the signal.
        """
        if bad == "DIR":
            target = str(tmp_path)
        elif bad == "TRAILING":
            target = str(tmp_path / "newdir") + "/"
        else:
            target = bad
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output=target))
        assert rc == 2
        captured = capsys.readouterr()
        assert "must name a file, not a directory" in captured.err
        assert "<!DOCTYPE" not in captured.out
        if bad == "TRAILING":
            assert not (tmp_path / "newdir").exists()

    def test_an_explicit_output_error_shows_what_the_operator_typed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # Regression: a message interpolating the expanded/normalized Path
        # instead of the raw string is technically still correct but far
        # less recognizable to the operator who typed ``~/notes/`` and reads
        # back ``/Users/alice/notes`` with no trailing slash and no ``~``.
        # A substring check ("must name a file" in err) cannot catch this —
        # only pinning the exact text can.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        raw = "./nested/../" + str(tmp_path) + "/"
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output=raw))
        assert rc == 2
        assert (
            f"error: --output must name a file, not a directory: {raw}\n"
            == capsys.readouterr().err
        )

    def test_an_unexpandable_output_path_is_a_usage_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded())

        def unexpected(*_args, **_kwargs):
            raise AssertionError("must not render before output expansion")

        _stub_render(monkeypatch, "render_roadmap_html", unexpected)
        raw = "~no-such-plan-tool-user/review.html"
        target = Path(raw)
        real_expanduser = Path.expanduser

        def boom(self):
            if self == target:
                raise RuntimeError("Could not determine home directory")
            return real_expanduser(self)

        monkeypatch.setattr(Path, "expanduser", boom)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output=raw))
        assert rc == 2
        assert (
            "error: --output is not a usable file path: "
            "~no-such-plan-tool-user/review.html: Could not determine home directory\n"
            == capsys.readouterr().err
        )

    def test_the_default_destination_error_shows_the_computed_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # No raw operator string exists for the default case — the computed
        # destination is the only thing that can be shown. A directory at
        # that computed path is environmental rather than malformed input.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        default_path = roadmap_cmd.review_path(resolve_output_dir(tmp_path), "my-roadmap")
        default_path.mkdir(parents=True)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html"))
        assert rc == 1
        assert (
            f"error: the default review page must name a file, not a directory: {default_path}\n"
            == capsys.readouterr().err
        )

    def test_a_permission_error_checking_the_default_destination_is_incomplete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        target = roadmap_cmd.review_path(resolve_output_dir(tmp_path), "my-roadmap")
        real_is_dir = Path.is_dir

        def boom(self):
            if self == target:
                raise PermissionError(13, "Permission denied")
            return real_is_dir(self)

        monkeypatch.setattr(Path, "is_dir", boom)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html"))
        assert rc == 1
        captured = capsys.readouterr()
        assert (
            f"error: could not check the default review page destination {target}: "
            in captured.err
        )
        assert "<!DOCTYPE" not in captured.out

    def test_a_default_destination_value_error_is_incomplete(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")

        def boom(*_args, **_kwargs):
            raise ValueError("simulated filesystem rejection")

        monkeypatch.setattr(f"{MODULE}.atomic_write_text", boom)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html"))
        assert rc == 1
        captured = capsys.readouterr()
        target = roadmap_cmd.review_path(resolve_output_dir(tmp_path), "my-roadmap")
        assert (
            "error: the default review page is not a usable file path: "
            f"{target}: simulated filesystem rejection\n" == captured.err
        )
        assert "<!DOCTYPE" not in captured.out

    def test_a_permission_error_checking_the_destination_is_a_usage_error_not_a_crash(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        """``Path.is_dir()`` stats the path and only swallows OSError for
        errnos meaning "doesn't exist" (ENOENT/ENOTDIR/EBADF/ELOOP) —
        EACCES is not among them, so a permission-denied intermediate
        directory makes ``is_dir()`` itself raise. Uncaught, that would
        reach the global crash handler instead of the same usage error
        every other unusable ``--output`` value gets.
        """
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        target = tmp_path / "p.html"
        # A raw string that parses to the same Path as `target` (pathlib
        # collapses the redundant "/./" during parsing) but is not the same
        # *string* as str(target) — the case that distinguishes "shows what
        # the operator typed" from "shows the expanded form", the same
        # display-fidelity property the sibling tests above pin.
        raw = f"{tmp_path}/./p.html"
        real_is_dir = Path.is_dir

        def boom(self):
            # Only the destination under test raises; every other `is_dir()`
            # call this dispatch makes along the way (repo-root resolution,
            # etc.) behaves normally.
            if self == target:
                raise PermissionError(13, "Permission denied")
            return real_is_dir(self)

        monkeypatch.setattr(Path, "is_dir", boom)
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="html", output=raw)
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert (
            f"error: could not check --output destination {raw}: "
            in captured.err
        )
        assert str(target) not in captured.err
        assert "<!DOCTYPE" not in captured.out

    def test_the_html_view_reaches_the_renderer_under_the_requested_mode(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        loaded = _loaded()
        captured_load = _stub_load_roadmap(monkeypatch, loaded)
        captured = _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        assert (
            cmd_roadmap(
                _ns(
                    tmp_path,
                    from_existing=None,
                    view="html",
                    mode=MODE_REVIEW,
                )
            )
            == 0
        )
        assert captured_load["mode"] == MODE_REVIEW
        assert captured["args"] == (loaded,)
        assert roadmap_cmd.review_path(
            resolve_output_dir(tmp_path), "my-roadmap"
        ).read_text() == "<!DOCTYPE html>\n"

    def test_the_html_view_runs_no_stage_and_invokes_no_backend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def boom(*_a, **_k):
            raise AssertionError("the html view must not run a stage")

        monkeypatch.setattr(f"{MODULE}.run_roadmap", boom)
        monkeypatch.setattr(f"{MODULE}.apply_roadmap_seeds", boom)
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        assert cmd_roadmap(_ns(tmp_path, from_existing=None, view="html")) == 0
        assert roadmap_cmd.review_path(
            resolve_output_dir(tmp_path), "my-roadmap"
        ).read_text() == "<!DOCTYPE html>\n"

    def test_an_invalid_output_never_reaches_the_renderer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bad ``--output`` fails before the whole-roadmap render runs, not
        after — walking every row of all four artifacts to render text that
        is immediately discarded is wasted work a usage error should never
        pay for."""
        _stub_load_roadmap(monkeypatch, _loaded())

        def unexpected(*_a, **_k):
            raise AssertionError("must not render before --output is validated")

        monkeypatch.setattr(f"{MODULE}.render_roadmap_html", unexpected)
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="html", output=str(tmp_path))
        )
        assert rc == 2

    def test_output_dash_never_computes_a_destination(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The stdout escape hatch skips destination computation entirely.
        # A call proves the default-path computation ran when it shouldn't.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")

        def boom(*_a, **_k):
            raise AssertionError("--output - must not compute a destination")

        monkeypatch.setattr(f"{MODULE}.review_path", boom)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", output="-"))
        assert rc == 0

    def test_the_default_destination_being_a_directory_names_it_as_the_default_not_output(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        # The rare case where the default review-page path collides with an
        # existing directory of that name must not blame "--output", which
        # was never supplied.
        _stub_load_roadmap(monkeypatch, _loaded())
        _stub_render(monkeypatch, "render_roadmap_html", "<!DOCTYPE html>\n")
        default_path = roadmap_cmd.review_path(resolve_output_dir(tmp_path), "my-roadmap")
        default_path.mkdir(parents=True)
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html"))
        assert rc == 1
        captured = capsys.readouterr()
        assert "the default review page must name a file, not a directory" in captured.err
        assert "--output" not in captured.err

    def test_id_with_view_html_is_rejected(self, tmp_path: Path, capsys) -> None:
        rc = cmd_roadmap(_ns(tmp_path, from_existing=None, view="html", id="ent-1"))
        assert rc == 2
        assert "--id is only valid with --view index" in capsys.readouterr().err

    def test_the_real_pipeline_writes_a_well_formed_page_from_a_real_artifact(
        self, tmp_path: Path
    ) -> None:
        """The one test in this class that stubs neither ``load_roadmap``
        nor ``render_roadmap_html``: a real accepted version, through the
        real dispatch, to a real file. Every other ``TestHtmlView`` case
        stubs both, so a rename or reshape of a ``LoadedRoadmap`` field the
        renderer consumes — or a change to ``load_roadmap``'s per-artifact
        None-vs-absent semantics — would pass every stubbed test here while
        breaking the actual wiring.
        """
        plans_dir = tmp_path / "docs" / "implementation-plans"
        _publish_real_domain_root(plans_dir)
        destination = tmp_path / "review.html"
        rc = cmd_roadmap(
            _ns(
                tmp_path,
                from_existing=None,
                view="html",
                output=str(destination),
                plans_dir=plans_dir,
            )
        )
        assert rc == 0
        html = destination.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>")
        assert "ent-order" in html
        assert "Order" in html
        assert "Real pipeline check." in html

    def test_the_real_pipeline_writes_the_default_file_with_no_output_flag(
        self, tmp_path: Path
    ) -> None:
        """Sibling of the explicit-``--output`` real-pipeline test above,
        for the new default: no ``--output`` at all, through the real
        dispatch and the real ``roadmap_dir``, landing at the actual
        computed path rather than one this test hands-assembles."""
        plans_dir = tmp_path / "docs" / "implementation-plans"
        _publish_real_domain_root(plans_dir)
        rc = cmd_roadmap(
            _ns(tmp_path, from_existing=None, view="html", plans_dir=plans_dir)
        )
        assert rc == 0
        destination = roadmap_cmd.review_path(plans_dir, "my-roadmap")
        html = destination.read_text(encoding="utf-8")
        assert html.startswith("<!DOCTYPE html>")
        assert "ent-order" in html


def test_every_exclusive_mode_predicate_rejects_the_output_companion(
    tmp_path: Path,
) -> None:
    """``--output`` joins the shared companion set, so each exclusive mode —
    which accepts no companion options — must refuse it. Sibling of the
    feedback-reopen predicate sweep above: the point is that the new
    companion reaches *every* predicate, not only the ordinary view path.

    Every caller of ``_broad_mode_companions_present`` that can be
    exercised with no action selected is asserted (``_candidate_lifecycle_has_conflict``
    already conflicts with no action selected, regardless of ``--output``,
    so it cannot isolate this companion).
    The set is the contract: refactor one predicate off the shared helper
    and its rejection silently disappears, which a subset would not catch.
    """
    out = {"output": str(tmp_path / "page.html")}
    settlement = {
        "settle_decision": "domain:decision-order",
        "settlement_evidence": "domain:feedback-order",
        "confirm_decision_settlement": True,
        "_settle_decision_occurrences": ("domain:decision-order",),
        "_settlement_evidence_occurrences": ("domain:feedback-order",),
        "_confirm_decision_settlement_occurrences": (True,),
    }

    assert roadmap_cmd._revise_feedback_has_conflict(
        _ns(tmp_path, revise_feedback="domain:feedback-order", **out)
    )
    assert roadmap_cmd._decision_settlement_has_conflict(_ns(tmp_path, **settlement, **out))


# --------------------------------------------------------------------------
# No restore hint at any non-completion path
# --------------------------------------------------------------------------


class TestNoRestoreHintAtAnyPath:
    """The revision checkpoint and its ``--restore-revision`` route are removed, so no
    non-completion exit of ``cmd_roadmap`` names a restore command."""

    @pytest.mark.parametrize(
        "result_or_exc, expected_rc",
        (
            (
                RoadmapResult(
                    outcome=OUTCOME_STAGE_INVALID,
                    artifacts=(),
                    stages_run=(1,),
                    pending_decisions=0,
                    failed_stage=1,
                ),
                1,
            ),
            (_exhausted(), 1),
            (OSError("disk full"), 1),
            (RoadmapError("missing template"), 2),
            (KeyboardInterrupt(), 130),
        ),
        ids=(
            "stage-invalid",
            "stage-exhausted",
            "environmental-failure",
            "roadmap-error",
            "keyboard-interrupt",
        ),
    )
    def test_no_restore_hint_at_any_non_completion_path(
        self,
        result_or_exc,
        expected_rc: int,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys,
    ) -> None:
        _stub_run(monkeypatch, result_or_exc)

        assert cmd_roadmap(_ns(tmp_path)) == expected_rc

        output = capsys.readouterr().out
        assert "--restore-revision" not in output
        assert "--confirm-restore-revision" not in output

    def test_completed_run_never_prints_a_restore_hint(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
    ) -> None:
        _stub_run(monkeypatch, _completed())

        assert cmd_roadmap(_ns(tmp_path)) == 0

        captured = capsys.readouterr()
        assert "--restore-revision" not in captured.out
        assert "--restore-revision" not in captured.err


_CORRECTION_BEFORE = "entity-order is the customer order.\nSecond line, kept verbatim.\n"
_CORRECTION_AFTER = "entity-order is the corrected order.\nSecond line, kept verbatim.\n"


def _correction_capsule(*, before: str = _CORRECTION_BEFORE) -> SimpleNamespace:
    from plan_tool.roadmap_candidate_context import CandidateContextSourceSpan

    span = CandidateContextSourceSpan(
        row_id="entity-order", span_id="span-order", text=before,
        digest=hashlib.sha256(before.encode()).hexdigest(),
        owning_row_ids=("entity-order", "entity-customer"),
    )
    member = SimpleNamespace(
        identity=SimpleNamespace(artifact_key="domain", row_id="entity-order"), source_spans=(span,)
    )
    return SimpleNamespace(full_members=(member,))


def _correction_operation(*, after: str = _CORRECTION_AFTER):
    return roadmap_candidate.CandidateCorrectProse(
        feedback_id="batch-one", artifact_key="domain", span_id="span-order", replacement=after
    )


def _corrected_candidate() -> SimpleNamespace:
    candidate = _stored_structural_cli_candidate()
    candidate.evidence.normalized_operations = (_correction_operation(),)
    candidate.evidence.capsule = _correction_capsule()
    return candidate


def test_structural_disclosure_prints_exact_before_and_after_for_a_correction(capsys) -> None:
    lines = _printed_disclosure(_corrected_candidate(), capsys)

    assert "prose corrections: 1" in lines
    assert "  correction artifact key: domain" in lines
    assert '  correction owning row ids: ["entity-order","entity-customer"]' in lines
    assert "  correction before text: " + roadmap_cmd._render_stored_value(_CORRECTION_BEFORE) in lines
    assert "  correction after text: " + roadmap_cmd._render_stored_value(_CORRECTION_AFTER) in lines


def test_structural_disclosure_prints_empty_corrections_line_when_none_present(capsys) -> None:
    """An explicit empty line keeps 'no corrections' distinguishable from 'not reported'."""
    lines = _printed_disclosure(_stored_structural_cli_candidate(), capsys)

    assert "prose corrections: []" in lines


def test_every_stack_hop_prints_its_own_corrections(capsys) -> None:
    lower = _stack_hop("hop-a", route=_STRUCTURAL)
    top = _stack_hop("hop-b", route=_PRESENTATION_ONLY)
    lower.evidence.normalized_operations = (_correction_operation(),)
    lower.evidence.capsule = _correction_capsule()

    lines = _printed_stack(_stack_view(lower, top), capsys)

    lower_section = _hop_sections(lines)["hop-a"]
    assert "prose corrections: 1" in lower_section
    assert "correction after text: " + roadmap_cmd._render_stored_value(_CORRECTION_AFTER) in lower_section
    assert "prose corrections: []" in lines  # the top candidate, which has none


def test_correction_display_reads_stored_evidence_not_the_live_artifact(capsys) -> None:
    """The before text is the capsule's stored span; nothing here can reach the live artifact."""
    candidate = _corrected_candidate()
    stored_before = candidate.evidence.capsule.full_members[0].source_spans[0].text

    lines = _printed_disclosure(candidate, capsys)

    assert "  correction before text: " + roadmap_cmd._render_stored_value(stored_before) in lines


# --- Narrative review evidence on the candidate surfaces (docs/implementation-plans/archive/2-candidate-narrative-review-evidence.md) ---

_NARRATIVE_FINDING = SimpleNamespace(
    kind="removed-id-in-live-prose", artifact="domain", row_id="entity-gone", start=10, end=21, line=3,
    excerpt="the entity-gone row is live", correction_path=("rewrite the span", "mark it historical"),
)
_NARRATIVE_AMBIGUOUS = SimpleNamespace(
    kind="ambiguous-reference", artifact="plans", row_id="entity-shared", start=1, end=5, line=1,
    excerpt="entity-shared", correction_path=("none required; the reviewer reads this evidence item",),
)


def _narrative_evidence(*, blocking=(), items=()):
    return roadmap_cmd.roadmap_candidate_narrative.CandidateNarrativeEvidence(tuple(blocking), tuple(items))


@pytest.fixture(autouse=True)
def _no_narrative_findings_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hand-built candidates here have no stored predecessor; cases that care stub their own evidence."""
    monkeypatch.setattr(roadmap_cmd, "_compute_narrative_evidence", lambda **_kwargs: _narrative_evidence())


def _stub_narrative_evidence(monkeypatch: pytest.MonkeyPatch, evidence=None, *, error: Exception | None = None):
    calls: list[dict] = []

    def compute(**kwargs: object):
        calls.append(kwargs)
        if error is not None:
            raise error
        return evidence if evidence is not None else _narrative_evidence()

    monkeypatch.setattr(roadmap_cmd, "_compute_narrative_evidence", compute)
    return calls


def _content() -> SimpleNamespace:
    return SimpleNamespace(artifact_bytes=())


def _review_result_with_initial() -> SimpleNamespace:
    initial = SimpleNamespace(
        version_id="initial-candidate", content=_content(),
        record=SimpleNamespace(predecessor_version_id="accepted-root"),
    )
    return SimpleNamespace(outcome="stored", initial_candidate=initial, question_inventory=None, detail=None)


def test_propose_candidate_output_prints_narrative_evidence_with_artifact_span_class_and_correction_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    candidate = _stored_structural_cli_candidate()
    candidate.content = _content()
    result = SimpleNamespace(outcome="stored", candidate=candidate, detail=None)
    monkeypatch.setattr(roadmap_cmd, "run_initial_candidate_proposal", lambda *_a, **_k: result)
    _stub_candidate_stack_route(monkeypatch, is_structural=False)
    _stub_narrative_evidence(monkeypatch, _narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, propose_candidate=True))

    out = capsys.readouterr().out
    assert rc == 0
    assert "narrative evidence: 1 blocking, 0 non-blocking" in out
    assert "[blocking] artifact: domain" in out
    assert "row 'entity-gone', body line 3, offsets 10-21" in out
    assert "defect class: removed-id-in-live-prose" in out
    assert "correction path: rewrite the span; or mark it historical" in out
    assert out.index("predecessor diff:") < out.index("narrative evidence:")


def test_review_candidate_output_prints_narrative_evidence_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    result = _review_result_with_initial()
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_a, **_k: result)
    calls = _stub_narrative_evidence(monkeypatch, _narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    assert cmd_roadmap(_ns(tmp_path, from_existing=None, review_candidate="initial-candidate")) == 0

    assert "narrative evidence: 1 blocking, 0 non-blocking" in capsys.readouterr().out
    initial = result.initial_candidate
    assert calls[0]["initial"] is initial and calls[0]["content"] is initial.content


def test_answer_output_prints_narrative_evidence_for_the_replacement_not_the_edited_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Approval judges the replacement's content against the initial candidate's predecessor; so does the display."""
    initial = _stored_structural_cli_candidate()
    initial.content = _content()
    replacement = SimpleNamespace(
        version_id="replacement-id", content=_content(),
        evidence=SimpleNamespace(predecessor_diff={"changed_rows": []}),
    )
    result = SimpleNamespace(
        outcome="stored", initial_candidate=initial, replacement=replacement,
        seal=SimpleNamespace(seal_id="seal-id"), detail=None,
    )
    monkeypatch.setattr(roadmap_cmd, "answer_candidate_question", lambda *_a, **_k: result)
    calls = _stub_narrative_evidence(monkeypatch, _narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    assert cmd_roadmap(
        _ns(tmp_path, from_existing=None, answer_question="question-id", answer="Use this.")
    ) == 0

    out = capsys.readouterr().out
    assert calls[0]["content"] is replacement.content and calls[0]["initial"] is initial
    assert out.index("replacement: replacement-id") < out.index("narrative evidence:") < out.index("review seal:")


def test_decide_candidate_approve_prints_evidence_before_the_stack_digest_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    candidate = _stored_structural_cli_candidate()
    candidate.content = _content()
    _unconfirmed_approve_setup(monkeypatch, candidate)
    _stub_stack_view(monkeypatch, candidate)
    _stub_narrative_evidence(monkeypatch, _narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve"
    ))

    out = capsys.readouterr().out
    assert rc == 2
    assert (
        out.index("structural proposal: stored")
        < out.index("narrative evidence: 1 blocking")
        < out.index(f"stack digest: {_STUB_DIGEST}")
        < out.index("structural decision: approve confirmation-required")
    )


@pytest.mark.parametrize("decision", ("edit", "reject"))
def test_decide_candidate_edit_and_reject_print_evidence_before_the_decision_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys, decision: str
) -> None:
    _lower, top, view = _two_hop_stack()
    top.content = _content()
    calls = _stub_narrative_evidence(monkeypatch, _narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision=decision, candidate=top, views={"candidate-id": view},
        result=_decision_result("failed", detail="backend failed"),
    )

    lines = capsys.readouterr().out.splitlines()
    evidence_line = next(i for i, line in enumerate(lines) if line.startswith("narrative evidence:"))
    assert evidence_line < lines.index(_DECISION_CALLED)
    # For a stack the top candidate holds the final text, so evidence is for it alone.
    assert len(calls) == 1 and calls[0]["initial"] is top


def test_no_findings_prints_the_block_header_with_none_and_not_silence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    result = _review_result_with_initial()
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_a, **_k: result)
    _stub_narrative_evidence(monkeypatch, _narrative_evidence())

    cmd_roadmap(_ns(tmp_path, from_existing=None, review_candidate="initial-candidate"))

    assert "narrative evidence: none\n" in capsys.readouterr().out


def test_ambiguous_reference_prints_as_non_blocking_evidence_and_does_not_change_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    result = _review_result_with_initial()
    monkeypatch.setattr(roadmap_cmd, "generate_candidate_question", lambda *_a, **_k: result)
    _stub_narrative_evidence(monkeypatch, _narrative_evidence())
    clean_rc = cmd_roadmap(_ns(tmp_path, from_existing=None, review_candidate="initial-candidate"))
    capsys.readouterr()
    _stub_narrative_evidence(monkeypatch, _narrative_evidence(items=(_NARRATIVE_AMBIGUOUS,)))

    rc = cmd_roadmap(_ns(tmp_path, from_existing=None, review_candidate="initial-candidate"))

    out = capsys.readouterr().out
    assert "narrative evidence: 0 blocking, 1 non-blocking" in out
    assert "[non-blocking] artifact: plans" in out
    assert rc == clean_rc == 0


def test_evidence_failure_on_approve_returns_usage_before_the_digest_line_and_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    candidate = _stored_structural_cli_candidate()
    candidate.content = _content()
    _unconfirmed_approve_setup(monkeypatch, candidate)
    _stub_stack_view(monkeypatch, candidate)
    _stub_narrative_evidence(monkeypatch, error=ValueError("predecessor version is unreadable"))
    before = sorted(tmp_path.rglob("*"))

    rc = cmd_roadmap(_ns(
        tmp_path, from_existing=None, decide_candidate="candidate-id", candidate_decision="approve",
        confirm_stack_digest=_STUB_DIGEST,
    ))

    captured = capsys.readouterr()
    assert rc == roadmap_cmd._RC_USAGE
    assert "predecessor version is unreadable" in captured.err
    assert "stack digest:" not in captured.out
    assert sorted(tmp_path.rglob("*")) == before


def test_evidence_failure_on_reject_prints_unavailable_and_still_releases_the_candidate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Deliberate: a display failure must not trap a reviewer who is dropping the candidate."""
    _lower, top, view = _two_hop_stack()
    top.content = _content()
    _stub_narrative_evidence(monkeypatch, error=ValueError("predecessor version is unreadable"))

    rc, _asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="reject", candidate=top, views={"candidate-id": view},
        result=_decision_result("stored", detail=None),
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "narrative evidence: unavailable" in out
    assert "reason: predecessor version is unreadable" in out
    assert out.index("narrative evidence: unavailable") < out.index(_DECISION_CALLED)


def test_evidence_failure_from_a_malformed_artifact_prints_unavailable_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """RoadmapArtifactError is not a ValueError, so the display helper must catch it by name."""
    _lower, top, view = _two_hop_stack()
    top.content = _content()
    _stub_narrative_evidence(monkeypatch, error=RoadmapArtifactError("domain frontmatter is malformed"))

    rc, _asked = _run_edit_or_reject_over_stubbed_stack(
        tmp_path, monkeypatch, decision="reject", candidate=top, views={"candidate-id": view},
        result=_decision_result("stored", detail=None),
    )

    out = capsys.readouterr().out
    assert rc == 0
    assert "narrative evidence: unavailable" in out
    assert "reason: domain frontmatter is malformed" in out


def test_evidence_excerpt_is_escaped_so_candidate_prose_cannot_drive_the_terminal(capsys) -> None:
    """Excerpts are model-authored; control bytes print as JSON escapes like every other disclosure value."""
    hostile = SimpleNamespace(
        kind="removed-id-in-live-prose", artifact="domain", row_id="entity-gone", start=1, end=5, line=1,
        excerpt="entity-gone \x1b[2J\x1b[Hnarrative evidence: none", correction_path=("rewrite the span",),
    )

    roadmap_cmd._render_narrative_evidence(_narrative_evidence(blocking=(hostile,)))

    out = capsys.readouterr().out
    assert "\x1b" not in out
    assert 'excerpt: "entity-gone \\u001b[2J' in out


def test_standalone_reject_discard_and_promote_print_no_narrative_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys
) -> None:
    """Carve-out: these surfaces show no candidate content, so they compute and print no evidence."""
    monkeypatch.setattr(
        roadmap_cmd, "_compute_narrative_evidence",
        lambda **_kwargs: pytest.fail("a surface that shows no candidate content computed evidence"),
    )
    for name in ("reject_candidate_review", "discard_candidate_review"):
        monkeypatch.setattr(
            roadmap_cmd, name, lambda *_a, **_k: SimpleNamespace(outcome="stored", detail=None)
        )
    monkeypatch.setattr(
        roadmap_cmd, "promote_review_seal",
        lambda **_k: SimpleNamespace(version_id="replacement-id", outcome="promoted"),
    )

    @contextlib.contextmanager
    def guard(_plans_dir: Path, _slug: str):
        yield object()

    monkeypatch.setattr(roadmap_cmd, "roadmap_writer_guard", guard)

    for option, value in (
        ("reject_candidate", "candidate-id"), ("discard_candidate", "candidate-id"),
        ("promote_review_seal", "seal-id"),
    ):
        cmd_roadmap(_ns(tmp_path, from_existing=None, **{option: value}))

    assert "narrative evidence" not in capsys.readouterr().out


def test_evidence_is_not_part_of_the_stack_digest() -> None:
    """The digest is the view's alone; rendering evidence never feeds it."""
    _lower, _top, view = _two_hop_stack()
    digest = view.digest

    roadmap_cmd._render_narrative_evidence(_narrative_evidence(blocking=(_NARRATIVE_FINDING,)))

    assert view.digest == digest


# --- stack callout beside the narrative evidence ------------------------------


@pytest.fixture(autouse=True)
def _silence_stack_callout_except_for_its_own_tests(request, monkeypatch: pytest.MonkeyPatch) -> None:
    """Other tests pin exact output built on stubbed content the callout cannot parse."""
    if "stack_callout" in request.node.name:
        return
    monkeypatch.setattr(roadmap_cmd, "_print_candidate_stack_callout", lambda **_kwargs: None)


def test_every_narrative_evidence_print_site_also_prints_the_stack_callout() -> None:
    """Each evidence print site has its own callout call; a new site must add one or state why not."""
    source = Path(roadmap_cmd.__file__).read_text(encoding="utf-8")
    sites = source.split("def _compute_narrative_evidence(")[0]
    evidence_sites = sites.count("_print_narrative_evidence_or_unavailable(") + sites.count(
        "_render_narrative_evidence(\n"
    )
    assert evidence_sites == 5  # proposal, review, answer, structural approve, structural edit/reject
    assert sites.count("_print_candidate_stack_callout(") == evidence_sites


def test_stack_callout_failure_prints_unavailable_and_does_not_raise(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
) -> None:
    """Display only: an unreadable predecessor prints 'stack: unavailable' and returns, never raises."""
    initial = SimpleNamespace(evidence=SimpleNamespace(predecessor_version_id="accepted-root"))

    def unreadable(**_kwargs: object):
        raise ValueError("predecessor version is unreadable")

    monkeypatch.setattr(roadmap_cmd, "load_resolved_stored_version", unreadable)

    roadmap_cmd._print_candidate_stack_callout(
        plans_dir=tmp_path, slug="s", initial=initial, content=_content()
    )

    out = capsys.readouterr().out
    assert out.startswith("stack: unavailable\n")
    assert "reason: predecessor version is unreadable" in out


def test_stack_callout_prints_its_own_block_and_adds_no_narrative_evidence_text(
    monkeypatch: pytest.MonkeyPatch, capsys, tmp_path: Path
) -> None:
    """The callout is separate from the evidence block: a stack change never reaches its counts."""
    from plan_tool.roadmap_artifacts import ConstraintsArtifact, StackRow

    def constraints(stack):
        return ConstraintsArtifact(
            dispositions=(), constraints=(), decisions=(), body="", stack=stack
        )

    parsed = {
        b"candidate": constraints((StackRow(id="stack-1", concern="platform", choice="ECS"),)),
        b"predecessor": constraints(()),
    }
    monkeypatch.setattr(
        roadmap_cmd, "parse_constraints_artifact", lambda text: parsed[text.encode()]
    )
    monkeypatch.setattr(
        roadmap_cmd, "parse_components_artifact", lambda _text: SimpleNamespace(stores=())
    )
    names = ("domain", "constraints", "components", "plans")
    monkeypatch.setattr(
        roadmap_cmd,
        "load_resolved_stored_version",
        lambda **_kwargs: SimpleNamespace(
            artifact_bytes=tuple(b"predecessor" if n != "domain" and n != "plans" else b"" for n in names)
        ),
    )
    content = SimpleNamespace(
        artifact_bytes=tuple(b"candidate" if n != "domain" and n != "plans" else b"" for n in names)
    )
    initial = SimpleNamespace(evidence=SimpleNamespace(predecessor_version_id="accepted-root"))

    roadmap_cmd._print_candidate_stack_callout(
        plans_dir=tmp_path, slug="s", initial=initial, content=content
    )

    out = capsys.readouterr().out
    assert out.startswith("stack:\n")
    assert "Stack rows added:" in out and "stack-1" in out
    assert "narrative evidence" not in out
