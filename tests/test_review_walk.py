"""Tests for plan_tool.review_walk — the interactive walk-through loop."""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Callable, Optional

import pytest

import plan_tool.human_io as human_io
from plan_tool.fileio import durable_create_text
from plan_tool.human_io import HumanInputResolution
from plan_tool.review import Recommendation
from plan_tool.review_persistence import (
    Annotation,
    save_review,
    load_review,
    plan_reports_dir,
    update_annotation,
)
from plan_tool.review_walk import (
    StructuralOutcomeEffects,
    WalkResult,
    WalkResponsePolicy,
    WalkState,
    apply_structural_outcome,
    compute_target_signature,
    structural_apply_allowed,
    walk_recommendations,
)
from plan_tool.schema import (
    ChangeType,
    Plan,
    PlanStatus,
    Priority,
    Step,
)


def _queue_input(answers: list[str]) -> Callable[[str], str]:
    """Build a fake input() that pops answers in order. Extras raise."""
    it = iter(answers)

    def fake(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:
            raise AssertionError(
                f"input_fn ran out of answers at prompt: {prompt!r}"
            ) from exc

    return fake


def _capture_output() -> tuple[Callable[[str], None], list[str]]:
    captured: list[str] = []

    def out(line: str) -> None:
        captured.append(line)

    return out, captured


def _make_saved_review(tmp_path: Path, *recs: Recommendation):
    """Save a review with the given recs and return the loaded SavedReview."""
    path = save_review(
        plan_slug="x",
        plan_path="plans/x.md",
        repo_root=tmp_path,
        report_md="report",
        recommendations=list(recs),
    )
    return load_review(path)


def _rec(rec_id: str = "step1-deps-abc12345", **overrides) -> Recommendation:
    base = dict(
        id=rec_id,
        source="deps",
        severity="high",
        step_id=1,
        title="Step 1: depends on step 99 which is unknown",
        body="…",
        suggested_action="fix the dep",
    )
    base.update(overrides)
    return Recommendation(**base)


def _publish_remote_answers(
    directory: Path,
    answers: list[str],
    recorded_requests: Optional[list[dict[str, str]]] = None,
) -> Callable[[float], None]:
    """Return a poll hook that resolves each remote request in order."""
    answer_iter = iter(answers)

    def publish(_: float) -> None:
        for request_path in directory.glob("*.request.json"):
            record = json.loads(request_path.read_text(encoding="utf-8"))
            resolution_path = directory / f"{record['request_id']}.resolution.json"
            if resolution_path.exists():
                continue
            if recorded_requests is not None:
                recorded_requests.append(record)
            try:
                text = next(answer_iter)
            except StopIteration as exc:
                raise AssertionError("remote provider requested an unexpected answer") from exc
            durable_create_text(
                resolution_path,
                json.dumps({"request_id": record["request_id"], "text": text}) + "\n",
            )
            return
        raise AssertionError("remote provider polled without recording a request")

    return publish


class TestWalkRecommendationsHappyPath:
    def test_marks_done(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
        )
        assert result == WalkResult(answered=1, quit_early=False)
        # Persisted to disk.
        reloaded = load_review(saved.path)
        assert reloaded.annotations[
            "step1-deps-abc12345"
        ] == Annotation(status="applied", note="")

    def test_marks_skip(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["s"]),
            output_fn=out_fn,
        )
        assert result.answered == 1
        reloaded = load_review(saved.path)
        assert reloaded.annotations[
            "step1-deps-abc12345"
        ].status == "skip"

    def test_long_form_aliases(self, tmp_path: Path) -> None:
        """`apply` / `skip` / `quit` work alongside one-letter forms."""
        saved = _make_saved_review(
            tmp_path, _rec("a-1"), _rec("a-2", id="step2-deps-deadbeef")
        )
        out_fn, _ = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["apply", "skip"]),
            output_fn=out_fn,
        )
        reloaded = load_review(saved.path)
        assert reloaded.annotations["a-1"].status == "applied"
        assert reloaded.annotations["step2-deps-deadbeef"].status == "skip"


class TestWalkHumanInputProvider:
    def test_walk_without_pending_recommendations_skips_provider_configuration(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.delenv("PLAN_TOOL_HUMAN_IO_DIR", raising=False)
        saved = _make_saved_review(tmp_path, _rec())
        update_annotation(saved.path, _rec().id, Annotation(status="applied", note=""))
        saved = load_review(saved.path)
        out_fn, _ = _capture_output()

        result = walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("a completed walk must not read input"),
            output_fn=out_fn,
        )

        assert result == WalkResult(answered=0, quit_early=False)

    def test_terminal_annotation_command_preserves_prompt_and_annotation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        prompts: list[str] = []

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            return "a"

        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        walk_recommendations(saved, input_fn=input_fn, output_fn=out_fn)

        assert prompts == [
            "  (a)pply [default] / (s)kip / (f)eedback / (r)un / "
            "(aa) apply-all / (q)uit / (?) help > "
        ]
        assert load_review(saved.path).annotations[_rec().id] == Annotation(
            status="applied", note=""
        )

    def test_terminal_feedback_preserves_note_and_action_steering(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        saved = _make_saved_review(
            tmp_path,
            _rec(
                source="detail-coverage",
                suggested_action="plan-tool detail plan --step 1",
            ),
        )
        out_fn, _ = _capture_output()
        state = WalkState()
        prompts: list[str] = []
        answers = iter(["f", "  steer this apply  ", "a"])
        seen_feedback: list[str] = []

        def input_fn(prompt: str) -> str:
            prompts.append(prompt)
            return next(answers)

        def action_fn(_: Recommendation) -> str:
            seen_feedback.append(state.pending_feedback)
            return "applied the requested change"

        walk_recommendations(
            saved,
            input_fn=input_fn,
            output_fn=out_fn,
            action_fn=action_fn,
            state=state,
        )

        assert prompts == [
            "  (a)pply [default] / (s)kip / (f)eedback / (r)un / "
            "(aa) apply-all / (q)uit / (?) help > ",
            "  feedback: ",
            "  (a)pply [default] / (s)kip / (f)eedback / (r)un / "
            "(aa) apply-all / (q)uit / (?) help > ",
        ]
        assert seen_feedback == ["steer this apply"]
        assert load_review(saved.path).annotations[_rec().id] == Annotation(
            status="applied", note="steer this apply"
        )

    def test_provider_is_constructed_once_for_multi_read_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        constructed_with: list[Callable[[str], str]] = []
        requests = []
        answers = iter(["f", "guide the apply", "a"])

        def provider(request):
            requests.append(request)
            return HumanInputResolution(request.request_id, next(answers))

        def factory(input_fn):
            constructed_with.append(input_fn)
            return provider

        monkeypatch.setattr("plan_tool.review_walk.make_human_input_provider", factory)

        def unexpected_input(_: str) -> str:
            pytest.fail("the provider must own every interactive read")

        walk_recommendations(saved, input_fn=unexpected_input, output_fn=out_fn)

        assert constructed_with == [unexpected_input]
        assert [request.prompt_id for request in requests] == [
            "review-walk.annotation",
            "review-walk.feedback",
            "review-walk.annotation",
        ]

    def test_remote_annotation_command_request_uses_annotation_prompt_id(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(tmp_path, ["a"]),
        )
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()

        walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
        )

        request_records = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in tmp_path.glob("*.request.json")
        ]
        assert len(request_records) == 1
        assert request_records[0]["prompt_id"] == "review-walk.annotation"
        assert load_review(saved.path).annotations[_rec().id] == Annotation(
            status="applied", note=""
        )

    @pytest.mark.parametrize("response", ["s", "skip"])
    def test_restricted_remote_skip_spellings_persist_skip_without_dispatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        response: str,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(tmp_path, [response]),
        )
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()

        def unexpected_action(_: Recommendation) -> None:
            pytest.fail("restricted skip must not dispatch an action")

        result = walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
            action_fn=unexpected_action,
            response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
        )

        assert result == WalkResult(answered=1, quit_early=False)
        assert load_review(saved.path).annotations[_rec().id] == Annotation(status="skip", note="")

    @pytest.mark.parametrize("response", ["q", "quit"])
    def test_restricted_remote_quit_spellings_leave_no_annotation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        response: str,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(tmp_path, [response]),
        )
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()

        def unexpected_action(_: Recommendation) -> None:
            pytest.fail("restricted quit must not dispatch an action")

        result = walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
            action_fn=unexpected_action,
            response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
        )

        assert result == WalkResult(answered=0, quit_early=True)
        assert load_review(saved.path).annotations == {}

    @pytest.mark.parametrize(
        "response",
        [
            "",
            "a",
            "apply",
            "d",
            "done",
            "aa",
            "apply-all",
            "all",
            "f",
            "feedback",
            "n",
            "note",
            "r",
            "run",
            "?",
            "help",
            "unknown",
        ],
    )
    def test_restricted_remote_rejects_every_non_skip_quit_response_after_one_request(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        response: str,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        requests: list[dict[str, str]] = []
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(tmp_path, [response], requests),
        )
        saved = _make_saved_review(
            tmp_path,
            _rec(),
            _rec("second", id="step2-deps-deadbeef"),
        )
        out_fn, output = _capture_output()
        state = WalkState(yes_to_all=True)

        def unexpected_action(_: Recommendation) -> None:
            pytest.fail("restricted input must not dispatch an action")

        result = walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
            action_fn=unexpected_action,
            state=state,
            response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
        )

        assert result == WalkResult(answered=0, quit_early=True)
        assert load_review(saved.path).annotations == {}
        assert state == WalkState(yes_to_all=True)
        assert [request["prompt_id"] for request in requests] == ["review-walk.annotation"]
        assert "feedback" not in "\n".join(output).lower()

    def test_restricted_remote_annotation_prompt_advertises_only_skip_and_quit(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        requests: list[dict[str, str]] = []
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(tmp_path, ["q"], requests),
        )
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()

        walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
            response_policy=WalkResponsePolicy.SKIP_OR_QUIT,
        )

        assert requests[0]["prompt_id"] == "review-walk.annotation"
        assert requests[0]["prompt"] == "  (s)kip / (q)uit > "

    def test_unrestricted_walk_keeps_existing_remote_annotation_and_feedback_behavior(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(tmp_path))
        recorded_requests: list[dict[str, str]] = []
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(
                tmp_path,
                ["f", "  remote guidance  ", "a"],
                recorded_requests,
            ),
        )
        saved = _make_saved_review(
            tmp_path,
            _rec(
                source="detail-coverage",
                suggested_action="plan-tool detail plan --step 1",
            ),
        )
        out_fn, _ = _capture_output()
        state = WalkState()
        seen_feedback: list[str] = []

        def action_fn(_: Recommendation) -> str:
            seen_feedback.append(state.pending_feedback)
            return "applied the requested change"

        walk_recommendations(
            saved,
            input_fn=lambda _: pytest.fail("remote mode must not read the terminal"),
            output_fn=out_fn,
            action_fn=action_fn,
            state=state,
        )

        request_records = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in tmp_path.glob("*.request.json")
        ]
        assert [record["prompt_id"] for record in recorded_requests] == [
            "review-walk.annotation",
            "review-walk.feedback",
            "review-walk.annotation",
        ]
        assert len({record["request_id"] for record in request_records}) == 3
        assert seen_feedback == ["remote guidance"]
        assert load_review(saved.path).annotations[_rec().id] == Annotation(
            status="applied", note="remote guidance"
        )

    def test_apply_all_does_not_call_human_input_provider(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        requests = []

        def provider(request):
            requests.append(request)
            pytest.fail("apply-all must not request human input")

        result = walk_recommendations(
            saved,
            human_input_provider=provider,
            output_fn=out_fn,
            state=WalkState(yes_to_all=True),
        )

        assert result == WalkResult(answered=1, quit_early=False)
        assert requests == []


class TestWalkRecommendationsSkipInfo:
    def test_skips_info_findings_by_default_flag(self, tmp_path: Path) -> None:
        """skip_info hides info recs but walks the rest."""
        saved = _make_saved_review(
            tmp_path,
            _rec("a-1", severity="high"),
            _rec("a-2", id="step2-heuristic-deadbeef", severity="info"),
        )
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
            skip_info=True,
        )
        # Only the non-info rec was prompted.
        assert result.answered == 1
        reloaded = load_review(saved.path)
        assert reloaded.annotations["a-1"].status == "applied"
        # The info rec stays in the saved JSON, un-annotated.
        assert "step2-heuristic-deadbeef" not in reloaded.annotations
        assert any(
            r.id == "step2-heuristic-deadbeef" for r in reloaded.recommendations
        )
        # Total reflects the visible count, and a notice is shown.
        joined = "\n".join(output)
        assert "Walking 1 review recommendation(s)" in joined
        assert "skipping 1 info-level finding(s)" in joined

    def test_info_walked_when_skip_info_false(self, tmp_path: Path) -> None:
        """Default (skip_info=False) keeps the prior all-inclusive behavior."""
        saved = _make_saved_review(
            tmp_path,
            _rec("a-1", severity="high"),
            _rec("a-2", id="step2-heuristic-deadbeef", severity="info"),
        )
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["s", "s"]),
            output_fn=out_fn,
        )
        assert result.answered == 2
        assert "Walking 2 review recommendation(s)" in "\n".join(output)


class TestWalkRecommendationsNote:
    def test_note_then_done(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["n", "fix later", "d"]),
            output_fn=out_fn,
        )
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step1-deps-abc12345"]
        assert ann.status == "applied"
        assert ann.note == "fix later"


class TestWalkRecommendationsQuit:
    def test_quit_returns_early(self, tmp_path: Path) -> None:
        saved = _make_saved_review(
            tmp_path, _rec("a-1"), _rec("a-2", id="step2-deps-deadbeef")
        )
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["q"]),
            output_fn=out_fn,
        )
        assert result.quit_early is True
        assert result.answered == 0
        # No annotations persisted.
        reloaded = load_review(saved.path)
        assert reloaded.annotations == {}

    def test_quit_preserves_prior_marks(self, tmp_path: Path) -> None:
        """Items marked before the quit must persist."""
        saved = _make_saved_review(
            tmp_path,
            _rec("a-1"),
            _rec("a-2", id="step2-deps-deadbeef"),
            _rec("a-3", id="step3-deps-cafebabe"),
        )
        out_fn, _ = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["d", "q"]),
            output_fn=out_fn,
        )
        assert result.quit_early is True
        assert result.answered == 1
        reloaded = load_review(saved.path)
        assert reloaded.annotations["a-1"].status == "applied"
        assert "step2-deps-deadbeef" not in reloaded.annotations
        assert "step3-deps-cafebabe" not in reloaded.annotations


class TestWalkRecommendationsHelp:
    def test_help_then_done(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["?", "d"]),
            output_fn=out_fn,
        )
        # Help text was emitted.
        joined = "\n".join(output)
        assert "(a)pply" in joined or "apply" in joined
        # And the annotation persisted.
        reloaded = load_review(saved.path)
        assert reloaded.annotations[
            "step1-deps-abc12345"
        ].status == "applied"


class TestWalkBlankDefaultsToApply:
    def test_blank_input_marks_applied(self, tmp_path: Path) -> None:
        """Enter (blank input) treats the rec as applied — the walk
        assumes the user will act on each rec they're shown. Items
        already annotated applied/skipped don't reach this prompt at
        all."""
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input([""]),
            output_fn=out_fn,
        )
        assert result.answered == 1
        reloaded = load_review(saved.path)
        assert reloaded.annotations[
            "step1-deps-abc12345"
        ] == Annotation(status="applied", note="")

    def test_blank_default_advertised_in_prompt(self, tmp_path: Path) -> None:
        """Prompt copy advertises [default] so users know Enter applies."""
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, _ = _capture_output()
        captured_prompts: list[str] = []

        def recording_input(prompt: str) -> str:
            captured_prompts.append(prompt)
            return ""

        walk_recommendations(
            saved,
            input_fn=recording_input,
            output_fn=out_fn,
        )
        assert any("default" in p for p in captured_prompts)
        assert any("(a)pply" in p for p in captured_prompts)


class TestWalkRecommendationsInvalid:
    def test_invalid_then_done(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["x", "what", "d"]),
            output_fn=out_fn,
        )
        joined = "\n".join(output)
        assert "unrecognized" in joined.lower()
        reloaded = load_review(saved.path)
        assert reloaded.annotations[
            "step1-deps-abc12345"
        ].status == "applied"


class TestWalkRecommendationsSkipsAnnotated:
    def test_already_annotated_items_skipped_by_default(
        self, tmp_path: Path
    ) -> None:
        saved = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[
                _rec("a-1", confidence=None),
                _rec("a-2", id="step2-deps-deadbeef"),
            ],
            annotations={
                "a-1": Annotation(status="applied", note="already done"),
            },
        )
        from plan_tool.review_persistence import load_review

        loaded = load_review(saved)
        out_fn, output = _capture_output()
        result = walk_recommendations(
            loaded,
            input_fn=_queue_input(["d"]),  # only one prompt expected
            output_fn=out_fn,
        )
        # Only the unannotated item was prompted.
        assert result.answered == 1
        assert "confidence: unknown; already applied; skipping" in "\n".join(output)
        reloaded = load_review(saved)
        assert reloaded.annotations["a-1"].note == "already done"  # unchanged
        assert reloaded.annotations["step2-deps-deadbeef"].status == "applied"

    def test_rewalk_re_prompts_annotated(self, tmp_path: Path) -> None:
        saved = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[_rec("a-1")],
            annotations={
                "a-1": Annotation(status="skip", note="deferred"),
            },
        )
        from plan_tool.review_persistence import load_review

        loaded = load_review(saved)
        out_fn, _ = _capture_output()
        walk_recommendations(
            loaded,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
            rewalk=True,
        )
        reloaded = load_review(saved)
        # Status overwritten.
        assert reloaded.annotations["a-1"].status == "applied"

    def test_failed_annotation_re_prompted_without_rewalk(
        self, tmp_path: Path
    ) -> None:
        """A non-terminal ``failed`` apply is re-prompted on the next walk
        without ``--rewalk`` — unlike a terminal ``skip``/``applied`` — so a
        failed apply isn't silently treated as resolved (BUG_BACKLOG)."""
        saved = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="",
            recommendations=[_rec("a-1")],
            annotations={
                "a-1": Annotation(status="failed", note="apply errored"),
            },
        )
        from plan_tool.review_persistence import load_review

        loaded = load_review(saved)
        out_fn, output = _capture_output()
        # No --rewalk: the failed rec is still walked (and re-answered here).
        result = walk_recommendations(
            loaded,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
        )
        assert result.answered == 1
        assert "previously failed to apply; retrying" in "".join(output)
        reloaded = load_review(saved)
        # Re-answered → status overwritten (no longer the failed mark).
        assert reloaded.annotations["a-1"].status == "applied"


class TestWalkRequiresPath:
    def test_in_memory_saved_review_rejected(self, tmp_path: Path) -> None:
        from plan_tool.review_persistence import SavedReview

        # Fabricate a SavedReview with path=None (didn't come from disk).
        fake = SavedReview(
            plan_slug="x",
            plan_path="p",
            created_at="2026-01-01T00:00:00Z",
            report_md="",
            recommendations=[_rec()],
            annotations={},
            path=None,
        )
        out_fn, _ = _capture_output()
        with pytest.raises(ValueError, match="path"):
            walk_recommendations(
                fake,
                input_fn=_queue_input(["d"]),
                output_fn=out_fn,
            )


class TestWalkOutput:
    def test_renders_severity_and_title(self, tmp_path: Path) -> None:
        saved = _make_saved_review(
            tmp_path,
            _rec(severity="critical", title="Critical issue X"),
        )
        out_fn, output = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
        )
        joined = "\n".join(output)
        assert "[CRITICAL]" in joined
        assert "Critical issue X" in joined

    def test_renders_suggested_action(self, tmp_path: Path) -> None:
        saved = _make_saved_review(
            tmp_path,
            _rec(suggested_action="run plan-tool ..."),
        )
        out_fn, output = _capture_output()
        walk_recommendations(
            saved,
            input_fn=_queue_input(["d"]),
            output_fn=out_fn,
        )
        joined = "\n".join(output)
        assert "run plan-tool" in joined

    def test_audit_finding_labels_fix_as_will_apply(self) -> None:
        """plan-audit findings label the action block 'will apply' so the
        operator sees what (a)pply does; other sources stay 'suggested'."""
        from plan_tool.review_walk import _format_recommendation

        audit = _format_recommendation(
            1, 1,
            _rec(
                source="plan-completeness",
                suggested_action="add a mitigation criterion to step 3",
            ),
        )
        assert "will apply" in audit
        assert "add a mitigation criterion to step 3" in audit
        assert "suggested" not in audit

        other = _format_recommendation(
            1, 1, _rec(source="deps", suggested_action="run plan-tool ...")
        )
        assert "suggested" in other
        assert "will apply" not in other

    def test_restated_property_renders_as_evidence_not_an_action(self) -> None:
        """CLAUDE.md designates this walk as the intended review-and-apply
        path -- ``restated_property`` must reach it, distinctly labelled
        from the "will apply"/"suggested" action block so it doesn't read
        as an instruction."""
        from plan_tool.review_walk import _format_recommendation

        block = _format_recommendation(
            1, 1,
            _rec(
                source="plan-correctness",
                restated_property="the safety net has no route for this case",
            ),
        )
        assert "the safety net has no route for this case" in block
        assert "restatement" in block
        assert "evidence" in block

    def test_no_restatement_block_when_absent(self) -> None:
        from plan_tool.review_walk import _format_recommendation

        block = _format_recommendation(1, 1, _rec(restated_property=None))
        assert "restatement" not in block

    def test_no_restatement_block_when_whitespace_only(self) -> None:
        """A whitespace-only value must be treated the same as absent, not
        rendered as a dangling header with no content beneath it."""
        from plan_tool.review_walk import _format_recommendation

        block = _format_recommendation(1, 1, _rec(restated_property="   "))
        assert "restatement" not in block

    def test_triage_pair_shown_on_meta_line(self) -> None:
        """impact/complexity ride the meta line so a low/low wording fix
        isn't triaged with the same weight as its severity token."""
        from plan_tool.review_walk import _format_recommendation

        block = _format_recommendation(
            1, 1, _rec(source="plan-completeness", impact="low", complexity="low")
        )
        assert "impact low" in block
        assert "complexity low" in block

    def test_recommendation_shows_stored_confidence_without_changing_actions(self) -> None:
        """Display stored evidence support while keeping the walk decision data intact."""
        from plan_tool.review_walk import _format_recommendation

        for confidence, label in (
            ("supported", "confidence: supported"),
            ("limited", "confidence: limited"),
            (None, "confidence: unknown"),
        ):
            rec = _rec(confidence=confidence, suggested_action="apply this")
            block = _format_recommendation(1, 1, rec)
            assert label in block
            assert "apply this" in block

    def test_triage_pair_omitted_when_absent(self) -> None:
        """No impact/complexity → the meta line stays clean (no `· impact ?`)."""
        from plan_tool.review_walk import _format_recommendation

        block = _format_recommendation(
            1, 1, _rec(source="deps", impact=None, complexity=None)
        )
        assert "impact" not in block

    def test_long_lines_are_wrapped(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import review_walk

        monkeypatch.setattr(review_walk, "_term_width", lambda: 60)
        long_body = "word " * 60  # ~300 chars, must wrap at width 60
        saved = _make_saved_review(tmp_path, _rec(body=long_body.strip()))
        out_fn, output = _capture_output()
        walk_recommendations(
            saved, input_fn=_queue_input(["d"]), output_fn=out_fn
        )
        body_lines = [
            ln for chunk in output for ln in chunk.splitlines()
            if ln.strip().startswith("word")
        ]
        assert len(body_lines) > 1  # wrapped, not one run-on line
        assert all(len(ln) <= 60 for ln in body_lines)

    def test_color_applied_when_forced(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_FORCE_COLOR", "1")
        saved = _make_saved_review(tmp_path, _rec(severity="critical"))
        out_fn, output = _capture_output()
        walk_recommendations(
            saved, input_fn=_queue_input(["d"]), output_fn=out_fn
        )
        joined = "\n".join(output)
        assert "\033[" in joined  # ANSI codes present

    def test_no_color_when_disabled(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)
        monkeypatch.setenv("NO_COLOR", "1")
        saved = _make_saved_review(tmp_path, _rec(severity="critical"))
        out_fn, output = _capture_output()
        walk_recommendations(
            saved, input_fn=_queue_input(["d"]), output_fn=out_fn
        )
        joined = "\n".join(output)
        assert "\033[" not in joined


# --- CLI integration: reconcile --walk and reconcile-plan-walk subcommand ------------


_REVIEW_WALK_PLAN = """---
title: Walk Plan
status: in-progress
priority: low
steps:
  - id: 1
    title: t
    files:
      - some/missing/dir/x.py
    status: current
---

# Walk Plan
"""


def _setup_walk_repo(tmp_path: Path, *, with_detail: bool = False) -> Path:
    plan_path = tmp_path / "plan.md"
    text = _REVIEW_WALK_PLAN
    if with_detail:
        detail_path = tmp_path / "details" / "step-1.md"
        detail_path.parent.mkdir(parents=True, exist_ok=True)
        detail_path.write_text("# Step 1\n\n## Summary\n\nDetail.\n", encoding="utf-8")
        text = text.replace(
            "    status: current\n",
            "    status: current\n    detail: details/step-1.md\n",
        )
    plan_path.write_text(text, encoding="utf-8")
    manifest = tmp_path / "m.json"
    manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
    (tmp_path / ".git").mkdir()
    return manifest


def _force_tty(monkeypatch: pytest.MonkeyPatch, value: bool = True) -> None:
    """Make ``sys.stdin.isatty()`` return ``value`` for the test.

    Walk-by-default keys off TTY detection so non-interactive contexts
    (CI, pipes) don't hang on input. Tests must opt in to the
    interactive path explicitly.
    """
    import sys
    monkeypatch.setattr(sys.stdin, "isatty", lambda: value)


def _configure_remote_non_tty(
    monkeypatch: pytest.MonkeyPatch,
    directory: Path,
    answers: list[str] | None = None,
    recorded_requests: list[dict[str, str]] | None = None,
) -> None:
    """Select the file-backed remote provider for a headless command test."""
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
    monkeypatch.setenv("PLAN_TOOL_HUMAN_IO_DIR", str(directory))
    _force_tty(monkeypatch, False)
    if answers is not None:
        monkeypatch.setattr(
            human_io.time,
            "sleep",
            _publish_remote_answers(directory, answers, recorded_requests),
        )


class TestCliReviewWalkDefault:
    def test_walk_runs_by_default_when_tty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        captured = {}

        def fake_walk(saved, **kwargs):
            captured["saved"] = saved
            from plan_tool.review_walk import WalkResult
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        _force_tty(monkeypatch, True)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        # Walk fired without --walk flag.
        assert "saved" in captured

    def test_walk_skipped_when_not_tty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-TTY context (CI, pipes) skips walk silently — would hang otherwise."""
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        def fail_walk(*args, **kwargs):
            raise AssertionError("walk must not run when stdin isn't a TTY")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)
        _force_tty(monkeypatch, False)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0

    def test_no_walk_flag_opts_out_even_in_tty(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        def fail_walk(*args, **kwargs):
            raise AssertionError("walk must not run when --no-walk passed")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)
        _force_tty(monkeypatch, True)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan", "--no-walk"]
        )
        assert rc == 0

    def test_no_save_skips_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """No save target → no walk (annotations would have nowhere to land)."""
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        def fail_walk(*args, **kwargs):
            raise AssertionError("walk must not run with --no-save")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)
        _force_tty(monkeypatch, True)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan", "--no-save"]
        )
        assert rc == 0

    def test_dry_run_skips_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        def fail_walk(*args, **kwargs):
            raise AssertionError("walk must not run with --dry-run")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)
        _force_tty(monkeypatch, True)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan", "--dry-run"]
        )
        assert rc == 0

    def test_no_recommendations_skips_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A plan with zero recommendations skips walk silently — no preamble for nothing."""
        from plan_tool.cli import app as cli_module

        plan_path = tmp_path / "plan.md"
        # Body includes all required H2 sections so the body-completeness
        # check produces zero findings — this test asserts the walk is
        # skipped on truly empty recommendation lists.
        plan_path.write_text(
            "---\n"
            "title: Clean Plan\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: do nothing\n"
            "    status: current\n"
            "---\n"
            "\n"
            "## Overview\n\nN/A\n\n"
            "## Problem statement\n\nN/A\n\n"
            "## Architecture\n\nN/A\n\n"
            "## References\n\nN/A\n\n"
            "## Steps\n\nN/A\n\n"
            "## Out of scope\n\nN/A\n\n"
            "## Risks\n\nN/A\n\n"
            "## Testing\n\nN/A\n\n"
            "## Acceptance criteria\n\nN/A\n\n"
            "## Deferred\n\nN/A\n",
            encoding="utf-8",
        )
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)

        def fail_walk(*args, **kwargs):
            raise AssertionError("walk should not be called when no recs")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)
        _force_tty(monkeypatch, True)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0


class TestCliReviewRemoteNonTty:
    def _fresh_result(
        self, recommendations: list[Recommendation]
    ):
        from plan_tool.review import ReviewResult

        finding_text = "\n".join(
            "\n".join(
                part for part in (rec.title, rec.body, rec.suggested_action) if part
            )
            for rec in recommendations
        )
        return ReviewResult(
            report=f"## Plan Review\n\n{finding_text}\n",
            recommendations=recommendations,
            dry_run=False,
        )

    def _configure_fresh_review(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recommendations: list[Recommendation],
    ):
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        captured: dict[str, object] = {}

        def fake_full(path, **kwargs):
            captured["walk_will_run"] = kwargs["walk_will_run"]
            return self._fresh_result(recommendations)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)
        monkeypatch.chdir(tmp_path)
        return cli_module, manifest, captured

    def test_cmd_review_remote_non_tty_fresh_promptable_result_keeps_full_report_and_walks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        rec = _rec(
            title="Remote finding",
            body="keep this full finding body visible",
            suggested_action="take the explicit suggested action",
        )
        cli_module, manifest, captured = self._configure_fresh_review(
            tmp_path, monkeypatch, [rec]
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["skip"], requests)

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0

        out = capsys.readouterr().out
        assert captured["walk_will_run"] is False
        assert out.count("keep this full finding body visible") == 1
        assert out.count("take the explicit suggested action") == 1
        assert [request["prompt_id"] for request in requests] == [
            "review-walk.annotation"
        ]
        saved_path = next((tmp_path / "plan-details" / "plan" / "reports").glob("*.json"))
        assert load_review(saved_path).annotations[rec.id] == Annotation(status="skip", note="")

    def test_cmd_review_remote_non_tty_fresh_mixed_result_keeps_hidden_findings_visible(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        promptable = _rec("promptable", title="Promptable finding")
        hidden = _rec(
            "hidden-info",
            severity="info",
            title="Hidden info finding",
            body="hidden info body remains visible",
            suggested_action="hidden info action remains visible",
        )
        cli_module, manifest, _ = self._configure_fresh_review(
            tmp_path, monkeypatch, [promptable, hidden]
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"], requests)

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0

        out = capsys.readouterr().out
        assert "hidden info body remains visible" in out
        assert "hidden info action remains visible" in out
        assert len(requests) == 1

    def test_cmd_review_remote_non_tty_default_info_only_result_does_not_request_input(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        info_rec = _rec(
            severity="info",
            title="Info-only finding",
            body="info-only detail remains visible",
            suggested_action="info-only suggested action remains visible",
        )
        cli_module, manifest, _ = self._configure_fresh_review(
            tmp_path, monkeypatch, [info_rec]
        )
        _configure_remote_non_tty(monkeypatch, tmp_path)

        def fail_sleep(_: float) -> None:
            raise AssertionError("info-only result must not request remote input")

        monkeypatch.setattr(human_io.time, "sleep", fail_sleep)
        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0

        out = capsys.readouterr().out
        assert "info-only detail remains visible" in out
        assert "info-only suggested action remains visible" in out
        assert list(tmp_path.glob("*.request.json")) == []

    def test_cmd_review_remote_non_tty_empty_result_does_not_reload_save(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cli_module, manifest, captured = self._configure_fresh_review(
            tmp_path, monkeypatch, []
        )
        _configure_remote_non_tty(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.load_review",
            lambda _: pytest.fail("empty result must not reload its saved review"),
        )

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        assert captured["walk_will_run"] is False
        assert list(tmp_path.glob("*.request.json")) == []

    def test_cmd_review_remote_non_tty_default_pairwise_merge_info_remains_promptable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        pairwise_merge = _rec(
            "granularity-merge-1-2",
            source="granularity-merge",
            severity="info",
            step_id=1,
            title="Steps 1 and 2 may merge",
        )
        cli_module, manifest, _ = self._configure_fresh_review(
            tmp_path, monkeypatch, [pairwise_merge]
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"], requests)

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        assert len(requests) == 1

    def test_cmd_review_remote_non_tty_include_info_makes_info_finding_promptable(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        info_rec = _rec("info", severity="info", title="Info finding")
        cli_module, manifest, _ = self._configure_fresh_review(
            tmp_path, monkeypatch, [info_rec]
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"], requests)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "review", "plan", "--include-info"]
            )
            == 0
        )
        assert len(requests) == 1

    def test_cmd_review_remote_non_tty_does_not_build_or_dispatch_review_actions(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        cli_module, manifest, _ = self._configure_fresh_review(
            tmp_path, monkeypatch, [_rec()]
        )
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"])

        def fail_action_builder(**kwargs):
            raise AssertionError("restricted remote walk must not build review actions")

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", fail_action_builder
        )
        monkeypatch.setattr(
            "builtins.input",
            lambda _: pytest.fail("remote mode must not read terminal input"),
        )
        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0

    @pytest.mark.parametrize("remote", [False, True])
    def test_cmd_review_remote_tty_and_terminal_tty_keep_full_walk_contracts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        remote: bool,
    ) -> None:
        cli_module, manifest, captured = self._configure_fresh_review(
            tmp_path, monkeypatch, [_rec()]
        )
        _force_tty(monkeypatch, True)
        if remote:
            monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        else:
            monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        walk_calls: list[dict[str, object]] = []

        def fake_walk(saved, **kwargs):
            walk_calls.append(kwargs)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        assert captured["walk_will_run"] is True
        assert len(walk_calls) == 1
        assert walk_calls[0]["action_fn"] is not None
        assert walk_calls[0].get("response_policy", WalkResponsePolicy.FULL) is (
            WalkResponsePolicy.FULL
        )

    def test_cmd_review_refresh_bypasses_remote_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.refresh import RefreshOutcome

        manifest = _setup_walk_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        _configure_remote_non_tty(monkeypatch, tmp_path)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.refresh_plan",
            lambda *args: RefreshOutcome(plan_slug="plan"),
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.review_plan_full",
            lambda *args, **kwargs: pytest.fail("refresh must not start a review"),
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda *args, **kwargs: pytest.fail("refresh must not start a walk"),
        )

        assert (
            cli_module.main(["--manifest", str(manifest), "review", "plan", "--refresh"])
            == 0
        )
        assert "still grounded" in capsys.readouterr().out

    def test_walk_and_reuse_help_describe_remote_non_tty_restricted_walk(
        self,
    ) -> None:
        import argparse

        from plan_tool.cli import app as cli_module

        parser = cli_module.build_parser()
        subcommands = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        )
        review_parser = subcommands.choices["review"]
        helps = {action.dest: action.help for action in review_parser._actions}
        assert "Ordinary CI and non-TTY contexts skip the walk automatically" in helps["no_walk"]
        assert "PLAN_TOOL_HUMAN_IO=remote" in helps["no_walk"]
        assert "restricted (s)kip/(q)uit walk" in helps["reuse"]


@pytest.mark.integration
class TestCliReviewWalkSubcommand:
    @staticmethod
    def _forbid_remote_action_build(monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn",
            lambda **kwargs: pytest.fail("remote walks must not build actions"),
        )

    @pytest.mark.parametrize(
        "command",
        ("reconcile-plan-walk", "reconcile-walk", "review-walk"),
    )
    @pytest.mark.parametrize("response", ("s", "skip"))
    def test_cmd_review_walk_remote_non_tty_skip_persists_only_skip_annotation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
        response: str,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        rec = _rec("remote-skip")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[rec],
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, [response], requests)
        self._forbid_remote_action_build(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert cli_module.main(["--manifest", str(manifest), command, "plan"]) == 0
        assert load_review(saved_path).annotations == {
            rec.id: Annotation(status="skip", note="")
        }
        assert [request["prompt_id"] for request in requests] == [
            "review-walk.annotation"
        ]

    def test_cmd_review_walk_remote_non_tty_skip_continues_to_later_promptable_finding(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        first = _rec("first-remote-skip")
        second = _rec("second-remote-skip")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[first, second],
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s", "skip"], requests)
        self._forbid_remote_action_build(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        assert load_review(saved_path).annotations == {
            first.id: Annotation(status="skip", note=""),
            second.id: Annotation(status="skip", note=""),
        }
        assert [request["prompt_id"] for request in requests] == [
            "review-walk.annotation",
            "review-walk.annotation",
        ]

    @pytest.mark.parametrize("response", ("q", "quit"))
    def test_cmd_review_walk_remote_non_tty_quit_leaves_sidecar_unmodified(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        response: str,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        rec = _rec("remote-quit")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[rec],
        )
        _configure_remote_non_tty(monkeypatch, tmp_path, [response])
        self._forbid_remote_action_build(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        assert load_review(saved_path).annotations == {}

    @pytest.mark.parametrize("response", ("apply", "feedback", "run", "apply-all"))
    def test_cmd_review_walk_remote_non_tty_rejects_full_menu_response_without_dispatch(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        response: str,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        rec = _rec("remote-reject")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[rec],
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, [response], requests)
        self._forbid_remote_action_build(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        assert load_review(saved_path).annotations == {}
        assert [request["prompt_id"] for request in requests] == [
            "review-walk.annotation"
        ]

    @pytest.mark.parametrize("remote_mode", (None, "REMOTE"))
    def test_cmd_review_walk_non_tty_without_exact_remote_mode_remains_report_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        remote_mode: str | None,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        rec = _rec("ordinary-headless", title="Ordinary headless finding")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[rec],
        )
        _force_tty(monkeypatch, False)
        if remote_mode is None:
            monkeypatch.delenv("PLAN_TOOL_HUMAN_IO", raising=False)
        else:
            monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", remote_mode)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations",
            lambda *args, **kwargs: pytest.fail("ordinary headless walks must report only"),
        )
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        captured = capsys.readouterr()
        assert "non-interactive stdin" in captured.err
        assert "Ordinary headless finding" in captured.out
        assert load_review(saved_path).annotations == {}

    def test_cmd_review_walk_remote_non_tty_preserves_rewalk_and_info_selection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        annotated = _rec("rewalk-annotated")
        info_rec = _rec("include-info", severity="info")
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[annotated, info_rec],
            annotations={
                annotated.id: Annotation(status="skip", note="already reviewed")
            },
        )
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["skip", "s"], requests)
        self._forbid_remote_action_build(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                [
                    "--manifest",
                    str(manifest),
                    "reconcile-plan-walk",
                    "plan",
                    "--rewalk",
                    "--include-info",
                ]
            )
            == 0
        )
        assert load_review(saved_path).annotations == {
            annotated.id: Annotation(status="skip", note=""),
            info_rec.id: Annotation(status="skip", note=""),
        }
        assert [request["prompt_id"] for request in requests] == [
            "review-walk.annotation",
            "review-walk.annotation",
        ]

    def test_cmd_review_walk_tty_keeps_full_policy_and_action_setup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        saved_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[_rec("tty-full")],
        )
        action = object()
        captured: dict[str, object] = {}
        monkeypatch.setenv("PLAN_TOOL_HUMAN_IO", "remote")
        _force_tty(monkeypatch, True)
        action_builder_state: dict[str, WalkState] = {}

        def build_action(**kwargs):
            action_builder_state["state"] = kwargs["state"]
            return action

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", build_action
        )

        def fake_walk(saved, **kwargs):
            captured["saved_path"] = saved.path
            captured.update(kwargs)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        assert captured["saved_path"] == saved_path
        assert captured["action_fn"] is action
        assert isinstance(captured["state"], WalkState)
        assert captured["state"] is action_builder_state["state"]
        assert captured["rewalk"] is False
        assert captured["skip_info"] is True
        assert captured["response_policy"] is WalkResponsePolicy.FULL

    @pytest.mark.parametrize(
        "command",
        ("reconcile-plan-walk", "reconcile-walk", "review-walk"),
    )
    def test_cmd_review_walk_aliases_share_remote_restricted_route(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        command: str,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[_rec("shared-remote-route")],
        )
        captured: dict[str, object] = {}
        _configure_remote_non_tty(monkeypatch, tmp_path)
        self._forbid_remote_action_build(monkeypatch)

        def fake_walk(saved, **kwargs):
            captured["saved_path"] = saved.path
            captured.update(kwargs)
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        monkeypatch.chdir(tmp_path)

        assert cli_module.main(["--manifest", str(manifest), command, "plan"]) == 0
        assert captured["response_policy"] is WalkResponsePolicy.SKIP_OR_QUIT
        assert "action_fn" not in captured
        assert captured["rewalk"] is False
        assert captured["skip_info"] is True

    def test_loads_newest_eligible_final_saved_review(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        final_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# final",
            recommendations=[_rec("final")],
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# checkpoint",
            recommendations=[_rec("checkpoint")],
            now=datetime(2026, 2, 1, tzinfo=timezone.utc),
            kind="completeness",
            is_pre_apply_checkpoint=True,
        )
        unknown_path = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# unknown",
            recommendations=[_rec("unknown")],
            now=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        payload = json.loads(unknown_path.read_text(encoding="utf-8"))
        payload["version"] = 3
        unknown_path.write_text(json.dumps(payload), encoding="utf-8")
        (plan_reports_dir(tmp_path / "plan.md") / "20260401-000000.json").write_text(
            "not valid json", encoding="utf-8"
        )

        captured = {}

        def fake_walk(saved, **kwargs):
            captured["path"] = saved.path
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        _force_tty(monkeypatch)
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 0
        )
        assert captured["path"] == final_path

    def test_rejected_direct_selection_returns_2_without_starting_walk(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        checkpoint = save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="# checkpoint",
            recommendations=[_rec("checkpoint")],
            now=datetime(2026, 1, 1, tzinfo=timezone.utc),
            kind="completeness",
            is_pre_apply_checkpoint=True,
        )
        original_checkpoint = checkpoint.read_text(encoding="utf-8")

        def fail_before_walk(*args, **kwargs):
            raise AssertionError("rejected direct selection must not start a walk")

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd._build_review_action_fn", fail_before_walk
        )
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.walk_recommendations", fail_before_walk
        )
        monkeypatch.chdir(tmp_path)

        assert (
            cli_module.main(
                ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
            )
            == 2
        )
        assert (
            cli_module.main(
                [
                    "--manifest", str(manifest),
                    "reconcile-plan-walk", "plan", "--id", checkpoint.stem,
                ]
            )
            == 2
        )
        assert checkpoint.read_text(encoding="utf-8") == original_checkpoint

    def test_loads_most_recent_saved(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)
        monkeypatch.chdir(tmp_path)

        # Run review twice so two saved files exist.
        cli_module.main(["--manifest", str(manifest), "reconcile", "plan"])
        cli_module.main(["--manifest", str(manifest), "reconcile", "plan"])

        # Capture which path the walk loads.
        captured = {}

        def fake_walk(saved, **kwargs):
            captured["path"] = saved.path
            from plan_tool.review_walk import WalkResult
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        _force_tty(monkeypatch)  # walk is per-finding + TTY-gated

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
        )
        assert rc == 0
        # Most-recent-by-name (since timestamps may collide at second precision).
        assert captured["path"] is not None

    def test_no_saved_reviews_returns_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile-plan-walk", "plan"]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "no eligible saved review" in err.lower()

    def test_unknown_id_returns_2(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = _setup_walk_repo(tmp_path)
        original = cli_module.review_plan_full

        def patched(path, **kwargs):
            kwargs["invoker"] = None
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", patched)
        monkeypatch.chdir(tmp_path)

        cli_module.main(["--manifest", str(manifest), "reconcile", "plan"])
        rc = cli_module.main(
            [
                "--manifest", str(manifest),
                "reconcile-plan-walk", "plan", "--id", "nope",
            ]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "no saved review" in err.lower()


# --- 'r' (run) action key ----------------------------------------------------


class TestWalkRunAction:
    def test_run_invokes_action_fn_then_reprompts(
        self, tmp_path: Path
    ) -> None:
        """Pressing 'r' calls action_fn(rec); walk re-prompts for status."""
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()
        calls: list[Recommendation] = []

        def action_fn(rec: Recommendation):
            calls.append(rec)
            return "did the thing"

        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["r", "d"]),
            output_fn=out_fn,
            action_fn=action_fn,
        )
        assert result.answered == 1
        assert len(calls) == 1
        assert calls[0].id == "step1-deps-abc12345"
        # Action handler's return message rendered via output_fn.
        assert any("did the thing" in line for line in output)

    def test_run_without_handler_warns_and_reprompts(
        self, tmp_path: Path
    ) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["r", "d"]),
            output_fn=out_fn,
            # No action_fn
        )
        assert result.answered == 1
        assert any("no action handler" in line for line in output)

    def test_run_action_exception_caught(self, tmp_path: Path) -> None:
        saved = _make_saved_review(tmp_path, _rec())
        out_fn, output = _capture_output()

        def boom(rec: Recommendation):
            raise RuntimeError("kaboom")

        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["r", "s"]),
            output_fn=out_fn,
            action_fn=boom,
        )
        assert result.answered == 1
        assert any("kaboom" in line for line in output)


# --- apply auto-dispatch when suggested_action is recognized -----------------


class TestWalkApplyDispatchesAction:
    """Apply (Enter / 'a') runs action_fn for recs whose suggested_action
    matches a recognized pattern (reconcile / detail) and an action_fn
    is wired. For other recs, apply records the annotation only.
    """

    def _reconcile_rec(self, rec_id: str = "step3-heuristic-abc") -> Recommendation:
        return Recommendation(
            id=rec_id,
            source="heuristic",
            severity="info",
            step_id=3,
            title="Step 3 looks already done",
            body="symbol foo present in foo.py",
            suggested_action=(
                "run `plan-tool detail plan --reconcile --step 3` to confirm"
            ),
        )

    def _detail_rec(self, rec_id: str = "step4-detail-xyz") -> Recommendation:
        return Recommendation(
            id=rec_id,
            source="detail-coverage",
            severity="medium",
            step_id=4,
            title="Step 4: detail file missing on disk",
            body="declares detail: docs/.../step-4.md but it isn't on disk",
            suggested_action="plan-tool detail plan --step 4 --force",
        )

    def test_apply_runs_action_fn_for_recognized_reconcile(
        self, tmp_path: Path
    ) -> None:
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, output = _capture_output()
        calls: list[Recommendation] = []

        def action_fn(rec: Recommendation):
            calls.append(rec)
            return "ran reconcile on step 3; 0 findings"

        result = walk_recommendations(
            saved,
            input_fn=_queue_input([""]),  # bare Enter — apply default
            output_fn=out_fn,
            action_fn=action_fn,
        )
        assert result == WalkResult(answered=1, quit_early=False)
        assert len(calls) == 1
        assert calls[0].id == "step3-heuristic-abc"
        # Action's return message rendered.
        assert any("ran reconcile on step 3" in line for line in output)
        # Annotation marked applied with the action's message captured
        # as the note (so users see what happened later).
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step3-heuristic-abc"]
        assert ann.status == "applied"
        assert ann.note == "ran reconcile on step 3; 0 findings"

    def test_apply_runs_action_fn_for_recognized_detail(
        self, tmp_path: Path
    ) -> None:
        saved = _make_saved_review(tmp_path, self._detail_rec())
        out_fn, _ = _capture_output()
        calls: list[Recommendation] = []

        def action_fn(rec: Recommendation):
            calls.append(rec)
            return "wrote detail for step 4 to docs/.../step-4.md"

        walk_recommendations(
            saved,
            input_fn=_queue_input(["a"]),
            output_fn=out_fn,
            action_fn=action_fn,
        )
        assert len(calls) == 1
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step4-detail-xyz"]
        assert ann.status == "applied"
        assert "wrote detail for step 4" in ann.note

    def test_apply_falls_back_when_no_action_fn(
        self, tmp_path: Path
    ) -> None:
        """Without an action_fn, recognized recs still get the apply-only
        treatment — the walk has nothing to dispatch them with."""
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, _ = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input([""]),
            output_fn=out_fn,
            # No action_fn
        )
        assert result.answered == 1
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step3-heuristic-abc"]
        assert ann == Annotation(status="applied", note="")

    def test_apply_falls_back_for_unrecognized_suggestion(
        self, tmp_path: Path
    ) -> None:
        """Recs with a free-form suggested_action (deps, files-coherence,
        claude semantic findings) don't auto-dispatch — apply records
        acknowledgment-only just like before this change."""
        saved = _make_saved_review(tmp_path, _rec())  # source=deps, free-text
        out_fn, _ = _capture_output()
        calls: list[Recommendation] = []

        def action_fn(rec: Recommendation):
            calls.append(rec)
            return "should not be called"

        walk_recommendations(
            saved,
            input_fn=_queue_input([""]),
            output_fn=out_fn,
            action_fn=action_fn,
        )
        assert calls == []  # action_fn left untouched
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step1-deps-abc12345"]
        assert ann == Annotation(status="applied", note="")

    def test_apply_action_failure_reprompts(self, tmp_path: Path) -> None:
        """When the dispatched action raises, the walk surfaces the
        error and re-prompts — the rec is NOT marked applied behind a
        failed run."""
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, output = _capture_output()

        def boom(rec: Recommendation):
            raise RuntimeError("kaboom")

        result = walk_recommendations(
            saved,
            # Apply (boom), then skip to record a non-applied status.
            input_fn=_queue_input(["", "s"]),
            output_fn=out_fn,
            action_fn=boom,
        )
        assert result.answered == 1
        assert any("kaboom" in line for line in output)
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step3-heuristic-abc"]
        assert ann.status == "skip"  # not applied — the action failed

    def test_apply_preserves_user_note_over_action_message(
        self, tmp_path: Path
    ) -> None:
        """A note captured before applying wins over the action's return
        message — the user's intent dominates."""
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, _ = _capture_output()

        def action_fn(rec: Recommendation):
            return "ran reconcile; 0 findings"

        walk_recommendations(
            saved,
            input_fn=_queue_input(
                # Note first, then apply (Enter).
                ["n", "follow up after release", ""]
            ),
            output_fn=out_fn,
            action_fn=action_fn,
        )
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step3-heuristic-abc"]
        assert ann.status == "applied"
        assert ann.note == "follow up after release"

    def test_feedback_stashed_on_state_and_visible_to_action(
        self, tmp_path: Path
    ) -> None:
        """The ``(f)eedback`` choice records the text as the note AND puts
        it on the shared WalkState so the apply handler can steer the edit
        by it."""
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, _ = _capture_output()
        state = WalkState()
        seen: list[str] = []

        def action_fn(rec: Recommendation):
            # The handler reads steering off the shared state at apply time.
            seen.append(state.pending_feedback)
            return "ran reconcile; 0 findings"

        walk_recommendations(
            saved,
            # feedback first, then apply (Enter).
            input_fn=_queue_input(["f", "prefer approach X", ""]),
            output_fn=out_fn,
            action_fn=action_fn,
            state=state,
        )
        assert seen == ["prefer approach X"]
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step3-heuristic-abc"]
        assert ann.status == "applied"
        assert ann.note == "prefer approach X"

    def test_note_is_backcompat_alias_for_feedback(
        self, tmp_path: Path
    ) -> None:
        """``n``/``note`` still works and now also stashes steering."""
        saved = _make_saved_review(tmp_path, self._reconcile_rec())
        out_fn, _ = _capture_output()
        state = WalkState()
        seen: list[str] = []

        def action_fn(rec: Recommendation):
            seen.append(state.pending_feedback)
            return "ran reconcile; 0 findings"

        walk_recommendations(
            saved,
            input_fn=_queue_input(["n", "legacy note text", ""]),
            output_fn=out_fn,
            action_fn=action_fn,
            state=state,
        )
        assert seen == ["legacy note text"]


class TestReviewWalkActionsReraiseDetailFormatError:
    """``DetailFormatError`` must escape every action-dispatch surface in
    the walk — apply-all's auto-dispatch, interactive apply, and
    interactive run — instead of being caught by the generic
    action-failed display-and-continue branch each surface otherwise
    uses for an ordinary action exception."""

    def _dispatchable_rec(self) -> Recommendation:
        return Recommendation(
            id="step3-heuristic-format",
            source="heuristic",
            severity="info",
            step_id=3,
            title="Step 3 looks already done",
            body="symbol foo present in foo.py",
            suggested_action=(
                "run `plan-tool detail plan --reconcile --step 3` to confirm"
            ),
        )

    def _dispatch_kwargs(self, mode: str) -> dict:
        if mode == "apply-all":
            return {"state": WalkState(yes_to_all=True)}
        if mode == "apply":
            return {"input_fn": _queue_input([""])}
        assert mode == "run"
        return {"input_fn": _queue_input(["r"])}

    @pytest.mark.parametrize("mode", ["apply-all", "apply", "run"])
    def test_each_review_walk_action_reraises_detail_format_error(
        self, tmp_path: Path, mode: str
    ) -> None:
        from plan_tool.detail_artifacts import DetailFormatError

        saved = _make_saved_review(tmp_path, self._dispatchable_rec())
        out_fn, _ = _capture_output()

        def boom(_rec: Recommendation) -> str:
            raise DetailFormatError("detail declares an unsupported version")

        with pytest.raises(DetailFormatError):
            walk_recommendations(
                saved, output_fn=out_fn, action_fn=boom,
                **self._dispatch_kwargs(mode),
            )

    @pytest.mark.parametrize("mode", ["apply-all", "apply", "run"])
    def test_each_review_walk_action_reraises_unsupported_plan_format(
        self, tmp_path: Path, mode: str
    ) -> None:
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        saved = _make_saved_review(tmp_path, self._dispatchable_rec())
        out_fn, _ = _capture_output()

        def boom(_rec: Recommendation) -> str:
            raise UnsupportedPlanFormatVersionError("unsupported format_version")

        with pytest.raises(UnsupportedPlanFormatVersionError):
            walk_recommendations(
                saved, output_fn=out_fn, action_fn=boom,
                **self._dispatch_kwargs(mode),
            )

    @pytest.mark.parametrize("mode", ["apply-all", "apply", "run"])
    def test_review_walk_keeps_generic_action_failure_continuation(
        self, tmp_path: Path, mode: str
    ) -> None:
        saved = _make_saved_review(tmp_path, self._dispatchable_rec())
        out_fn, output = _capture_output()

        def boom(_rec: Recommendation) -> str:
            raise RuntimeError("kaboom")

        kwargs = self._dispatch_kwargs(mode)
        if mode == "apply":
            kwargs["input_fn"] = _queue_input(["", "s"])
        elif mode == "run":
            kwargs["input_fn"] = _queue_input(["r", "s"])
        else:  # "apply-all" falls back to an interactive re-prompt on
            # failure (clearing state.yes_to_all) — feed it a skip.
            kwargs["input_fn"] = _queue_input(["s"])

        result = walk_recommendations(
            saved, output_fn=out_fn, action_fn=boom, **kwargs
        )
        assert result.answered == 1
        assert any("kaboom" in line for line in output)


class TestRecognizedActionParser:
    """``recognized_action`` is the single source of truth for the apply
    auto-dispatch contract — both the predicate and the CLI dispatcher
    consume it. Cover the parsed-parameters shape directly so a regex
    edit can't silently reshape the dispatcher input."""

    def test_detail_no_force_returns_descriptor(self) -> None:
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="detail-coverage", severity="info",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 7",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail"
        assert descriptor.step_id == 7
        assert descriptor.force is False

    def test_detail_with_force_returns_descriptor(self) -> None:
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="detail-body", severity="medium",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 7 --force",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail"
        assert descriptor.step_id == 7
        assert descriptor.force is True

    def test_detail_reconcile_reconcile_first_returns_descriptor(self) -> None:
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="detail-coverage", severity="info",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --reconcile --step 7",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail-reconcile"
        assert descriptor.step_id == 7

    def test_detail_reconcile_step_first_returns_descriptor(self) -> None:
        """Reverse flag order must still route to the audit handler, not
        the authoring handler (BUG_BACKLOG: _DETAIL_RECONCILE_PAT matched
        only one argument order)."""
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="detail-coverage", severity="info",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 7 --reconcile",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail-reconcile"
        assert descriptor.step_id == 7

    def test_unrecognized_returns_none(self) -> None:
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="deps", severity="high",
            step_id=2, title="t", body="b",
            suggested_action="unblock dependency on step 1",
        )
        assert recognized_action(rec) is None

    def test_no_suggested_action_returns_none(self) -> None:
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="claude", severity="info",
            step_id=None, title="t", body="b",
            suggested_action=None,
        )
        assert recognized_action(rec) is None

    def test_lessons_coverage_excluded_even_when_pattern_matches(
        self,
    ) -> None:
        """``lessons-coverage`` missing_entry recs phrase reconcile as a
        SECONDARY option (after "or"). Auto-dispatching reconcile would
        mark the rec applied without fixing the lessons gap (reconcile
        is read-only); the user must add the entry manually."""
        from plan_tool.review import (
            LessonsCoverageIssue,
            _lessons_recommendation,
        )
        from plan_tool.review_walk import recognized_action

        # Build the real shape so the test breaks if the source
        # text or source label is renamed.
        issue = LessonsCoverageIssue(
            step_id=5, kind="missing_entry", lessons_path="LESSONS.md"
        )
        rec = _lessons_recommendation(issue, plan_name="my-plan")
        assert rec.source == "lessons-coverage"
        # Sanity: the suggested_action does mention reconcile.
        assert "--reconcile" in (rec.suggested_action or "")
        # Source filter wins over pattern match.
        assert recognized_action(rec) is None

    def test_recognized_action_matches_detail_reconcile_command_shape(
        self,
    ) -> None:
        """``plan-tool detail <name> --reconcile --step N`` resolves to
        ``RecognizedAction(kind="detail-reconcile", step_id=N,
        force=False)``."""
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="claude", severity="medium",
            step_id=3, title="t", body="b",
            suggested_action="plan-tool detail my-plan --reconcile --step 3",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail-reconcile"
        assert descriptor.step_id == 3
        assert descriptor.force is False

    def test_recognized_action_detail_reconcile_takes_precedence_over_detail(
        self,
    ) -> None:
        """A ``detail --reconcile --step N`` suggestion must route to the
        new dispatcher kind, not silently regress into the authoring
        ``detail`` dispatcher."""
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="claude", severity="medium",
            step_id=3, title="t", body="b",
            suggested_action="plan-tool detail my-plan --reconcile --step 3",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail-reconcile"

    def test_recognized_action_plain_detail_still_returns_detail_kind(
        self,
    ) -> None:
        """Regression: the addition of ``_DETAIL_RECONCILE_PAT`` must not
        change the existing ``--step``-only parse."""
        from plan_tool.review_walk import recognized_action

        rec = Recommendation(
            id="x", source="detail-coverage", severity="info",
            step_id=3, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 3",
        )
        descriptor = recognized_action(rec)
        assert descriptor is not None
        assert descriptor.kind == "detail"
        assert descriptor.step_id == 3
        assert descriptor.force is False


class TestShouldApplyAsFinding:
    """``_APPLY_AS_FINDING_SOURCES`` membership — recs whose ``source``
    indicates they should route through ``apply_finding`` rather than
    a deterministic command dispatcher."""

    def test_returns_true_for_detail_reconcile_source(self) -> None:
        """``plan-tool detail --reconcile`` produces findings whose body
        describes a plan/detail edit; the walk must route them through
        ``apply_finding`` exactly like a run-side reconcile finding."""
        from plan_tool.review_walk import should_apply_as_finding

        rec = Recommendation(
            id="x", source="detail-reconcile", severity="medium",
            step_id=3, title="t", body="b", suggested_action=None,
        )
        assert should_apply_as_finding(rec) is True

    def test_returns_true_for_claude_source(self) -> None:
        from plan_tool.review_walk import should_apply_as_finding

        rec = Recommendation(
            id="x", source="claude", severity="medium",
            step_id=3, title="t", body="b", suggested_action=None,
        )
        assert should_apply_as_finding(rec) is True

    def test_returns_false_for_unrelated_source(self) -> None:
        from plan_tool.review_walk import should_apply_as_finding

        rec = Recommendation(
            id="x", source="deps", severity="high",
            step_id=3, title="t", body="b", suggested_action=None,
        )
        assert should_apply_as_finding(rec) is False

    def test_returns_true_for_plan_completeness_source(self) -> None:
        """Generic walks retain explicit plan-completeness dispatch support."""
        from plan_tool.review_walk import should_apply_as_finding

        rec = Recommendation(
            id="cache-invalidation", source="plan-completeness",
            severity="medium", step_id=None,
            title="t", body="b", suggested_action=None,
        )
        assert should_apply_as_finding(rec) is True

    def test_plan_correctness_dispatch_requires_explicit_caller_opt_in(
        self,
    ) -> None:
        """Design findings require explicit opt-in even in a generic saved walk."""
        from plan_tool.review_walk import (
            is_dispatchable,
            should_apply_as_finding,
        )

        rec = Recommendation(
            id="pc", source="plan-correctness", severity="high",
            step_id=None, title="t", body="b", suggested_action=None,
        )
        # Base (generic walk): NOT dispatchable.
        assert should_apply_as_finding(rec) is False
        assert is_dispatchable(rec) is False
        # Explicit caller opt-in widens the dispatchable set.
        extra = frozenset({"plan-correctness"})
        assert should_apply_as_finding(rec, extra_sources=extra) is True
        assert is_dispatchable(rec, extra_apply_sources=extra) is True


class TestHasRecognizedAction:
    """Shape predicate the walk uses to decide whether apply auto-dispatches."""

    def test_reconcile_pattern_recognized(self) -> None:
        from plan_tool.review_walk import has_recognized_action

        rec = Recommendation(
            id="x", source="heuristic", severity="info",
            step_id=2, title="t", body="b",
            suggested_action=(
                "run `plan-tool detail plan --reconcile --step 2` to confirm"
            ),
        )
        assert has_recognized_action(rec) is True

    def test_detail_pattern_recognized(self) -> None:
        from plan_tool.review_walk import has_recognized_action

        rec = Recommendation(
            id="x", source="detail-coverage", severity="info",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 2",
        )
        assert has_recognized_action(rec) is True

    def test_detail_force_pattern_recognized(self) -> None:
        from plan_tool.review_walk import has_recognized_action

        rec = Recommendation(
            id="x", source="detail-body", severity="medium",
            step_id=2, title="t", body="b",
            suggested_action="plan-tool detail my-plan --step 2 --force",
        )
        assert has_recognized_action(rec) is True

    def test_no_suggested_action_not_recognized(self) -> None:
        from plan_tool.review_walk import has_recognized_action

        rec = Recommendation(
            id="x", source="claude", severity="info",
            step_id=None, title="t", body="b",
            suggested_action=None,
        )
        assert has_recognized_action(rec) is False

    def test_free_form_not_recognized(self) -> None:
        from plan_tool.review_walk import has_recognized_action

        rec = Recommendation(
            id="x", source="deps", severity="high",
            step_id=2, title="t", body="b",
            suggested_action=(
                "unblock or fix dependency on step 1 before running step 2"
            ),
        )
        assert has_recognized_action(rec) is False


# --- nested reconcile walk from review walk -----------------------------------


def _basic_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(
        "---\n"
        "title: P\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: t\n"
        "    files: [foo.py]\n"
        "    status: done\n"
        "---\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    return plan_path


def _setup_manifest(tmp_path: Path) -> Path:
    manifest = tmp_path / "m.json"
    manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
    return manifest


@pytest.mark.integration
class TestNestedReconcileWalk:
    """The review-walk action_fn triggers run_step against reconcile.

    We exercise the action_fn directly (not through the walk loop) so
    the test doesn't need to drive interactive input through pytest's
    captured stdin. The walk integration is exercised by the unit
    tests above (TestWalkRunAction).
    """

    def test_action_fn_with_unrecognized_suggestion(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )
        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )
        # ``deps`` source: not a recognized command shape AND not in
        # the apply-as-finding set, so the handler returns the
        # unrecognized-suggestion message rather than auto-dispatching.
        rec = Recommendation(
            id="x",
            source="deps",
            severity="high",
            step_id=2,
            title="t",
            body="b",
            suggested_action="unblock dependency on step 1",
        )
        msg = action(rec)
        assert msg is not None
        assert "isn't a recognized reconcile" in msg

    def test_action_fn_dispatches_detail(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """suggested_action of ``plan-tool detail … --step N`` invokes
        generate_detail rather than reconcile."""
        from plan_tool.cli import app as cli_module
        from plan_tool.detail import DetailResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        captured: dict = {}

        def fake_generate_detail(plan_path_arg, **kwargs):
            captured["kwargs"] = kwargs
            return [
                DetailResult(
                    step_id=kwargs["step_id"],
                    output_path=tmp_path / "docs" / "step.md",
                    written=True,
                )
            ]

        # action_fn imports generate_detail lazily; patch the source
        # module so the closure picks up the fake.
        from plan_tool import detail as detail_module
        monkeypatch.setattr(
            detail_module, "generate_detail", fake_generate_detail
        )

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )

        # A bare `plan-tool detail ... --step N` (no --force) must parse to
        # force=False — the dispatcher's suggested-action parsing is generic.
        rec = Recommendation(
            id="step1-detail-abc",
            source="detail-coverage",
            severity="medium",
            step_id=1,
            title="Step 1: author detail file",
            body="detail authoring suggested",
            suggested_action="plan-tool detail plan --step 1",
        )
        msg = action(rec)
        assert msg is not None
        assert "wrote detail for step 1" in msg
        assert captured["kwargs"]["step_id"] == 1
        assert captured["kwargs"]["force"] is False

    def test_dispatch_reconcile_runs_fresh_when_user_declines_reuse(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the user declines the reuse prompt, _dispatch_detail_reconcile
        falls through to run_step as before."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import RunResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        # Seed a saved detail-reconcile so the prompt fires.
        saved_rec = Recommendation(
            id="step1-detail-reconcile-prior",
            source="detail-reconcile", severity="high",
            step_id=1, title="prior",
            body="b", suggested_action=None,
        )
        save_review(
            plan_slug="plan", plan_path="plan.md",
            repo_root=tmp_path, report_md="prior",
            recommendations=[saved_rec],
            kind="detail-reconcile", step_id=1,
        )

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        called = {"run_step": False}

        def fake_run_step(plan_path_arg, **kwargs):
            called["run_step"] = True
            return RunResult(
                step_id=1, exit_code=0, advanced_to=None, done=False,
                stdout="## Findings\n\n- NIT: x\n", step_title="t",
            )

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(launcher_module, "run_step", fake_run_step)
        monkeypatch.setattr("builtins.input", lambda prompt: "n")
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)
        # Mock the nested walk so it doesn't try to read real stdin
        # for the post-run findings — we only care that run_step was
        # called (the decline path).
        from plan_tool.review_walk import WalkResult

        def fake_walk(saved, **kwargs):
            return WalkResult(answered=0, quit_early=False)

        # ``_dispatch_reconcile`` drives the walk through
        # ``reconcile._walk_with_reconcile_phase``, which reads
        # ``walk_recommendations`` from the reconcile leaf's namespace.
        monkeypatch.setattr(
            "plan_tool.cli.reconcile.walk_recommendations", fake_walk
        )

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )

        rec = Recommendation(
            id="step1-heuristic-xyz",
            source="heuristic", severity="info",
            step_id=1, title="t", body="b",
            suggested_action=(
                "run `plan-tool detail plan --reconcile --step 1` to confirm"
            ),
        )
        action(rec)
        assert called["run_step"] is True

    def test_action_fn_dispatches_apply_finding_for_detail_reconcile_source(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """detail-reconcile recs (source=detail-reconcile,
        suggested_action=None) dispatch to apply_finding. The handler
        returns the action's outcome — we check the message shape and the
        path through ``_dispatch_apply_finding``."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        captured: dict = {}

        def fake_apply_finding(plan_path_arg, **kwargs):
            captured["kwargs"] = kwargs
            return ApplyFindingResult(
                step_id=kwargs.get("step_id"),
                exit_code=0,
                verdict="APPLIED",
                summary="flipped status to current",
                diff_text=(
                    "--- a/plan.md\n+++ b/plan.md\n"
                    "@@ -8 +8 @@\n-    status: done\n+    status: current\n"
                ),
                pre_snapshot={plan_path: "before"},
                stdout="",
            )

        # action_fn imports apply_finding lazily from plan_tool.launcher;
        # patch the source module so the closure picks up the fake.
        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )
        # User accepts the diff.
        monkeypatch.setattr("builtins.input", lambda prompt: "y")
        # Ensure the prompt path runs (TTY check).
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )
        rec = Recommendation(
            id="step1-detail-reconcile-aaa",
            source="detail-reconcile",
            severity="critical",
            step_id=1,
            title="step status should flip",
            body="acceptance criteria not met; flip to current",
            suggested_action=None,
        )
        msg = action(rec)
        assert msg is not None
        assert "applied finding" in msg
        assert captured["kwargs"]["step_id"] == 1
        assert "flip to current" in captured["kwargs"]["finding_body"]

    def test_action_fn_revert_path_when_user_rejects_diff(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the user types 'n' at the keep-changes prompt, the
        snapshot is restored and the rec is NOT marked applied with
        'applied finding'."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        # Track whether revert was called.
        revert_called: dict = {"v": False}

        def fake_apply_finding(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1, exit_code=0, verdict="APPLIED",
                summary="some edit",
                diff_text="--- a/plan.md\n+++ b/plan.md\n@@ -1 +1 @@\n-x\n+y\n",
                pre_snapshot={plan_path: "x\n"},
                stdout="",
            )

        def fake_revert(snapshot):
            revert_called["v"] = True

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )
        monkeypatch.setattr(
            launcher_module, "_restore_text_files", fake_revert
        )
        monkeypatch.setattr("builtins.input", lambda prompt: "n")
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )
        rec = Recommendation(
            id="step1-detail-reconcile-bbb",
            source="detail-reconcile",
            severity="high",
            step_id=1,
            title="t",
            body="b",
            suggested_action=None,
        )
        msg = action(rec)
        assert revert_called["v"] is True
        assert "reverted" in msg.lower()

    def test_apply_finding_failure_records_failed_not_applied(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A non-zero apply-finding exit rolls back the snapshot and is
        recorded as the non-terminal ``failed`` — never ``applied``, and
        never the terminal ``skip``.

        Regression (BUG_BACKLOG): the failure branch first returned a bare
        message that read as ``applied``; it was then fixed to set
        ``apply_skip``, but a terminal ``skip`` is the same annotation a
        deliberate decline gets, so the re-walk pre-skipped the gap as
        ``(already skip)`` and a *failed* apply was silently treated as
        resolved. The dispatcher must set ``apply_failed`` so the walk
        records the non-terminal ``failed`` (re-prompted next walk without
        ``--rewalk``)."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.locator import build_plan_tool_context
        from plan_tool.review_walk import WalkState, _prompt_for_annotation

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        def fake_apply_finding(plan_path_arg, **kwargs):
            # Apply ran, failed (rc=1), and rolled back to the snapshot.
            return ApplyFindingResult(
                step_id=1, exit_code=1, verdict="UNKNOWN",
                summary="", diff_text="",
                pre_snapshot={plan_path: "x\n"},
                stdout="",
            )

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)

        state = WalkState()
        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan", state=state
        )
        rec = Recommendation(
            id="step1-detail-reconcile-ccc",
            source="detail-reconcile",
            severity="high",
            step_id=1,
            title="t",
            body="b",
            suggested_action=None,
        )

        # Drive the real prompt path: the user presses Enter to apply.
        annotation = _prompt_for_annotation(
            human_input_provider=lambda request: HumanInputResolution(
                request.request_id, ""
            ),
            output_fn=lambda *_a, **_k: None,
            rec=rec,
            action_fn=action,
            state=state,
        )
        assert state.apply_failed is True
        assert state.apply_skip is False
        assert annotation is not None
        assert annotation.status == "failed"

    def test_action_fn_hard_reverts_on_post_edit_parse_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When the apply introduces a ``post-edit-parse-failure``
        finding, the keep/revert prompt is bypassed and the snapshot
        is restored unconditionally. Keeping the change would leave
        the plan unparseable, wedging every subsequent apply in the
        walk at ``parse_plan``."""
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.locator import build_plan_tool_context
        from plan_tool.review import Recommendation as _Rec

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        revert_called: dict = {"v": False}
        prompt_called: dict = {"v": False}

        def fake_apply_finding(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1, exit_code=0, verdict="APPLIED",
                summary="status flip",
                diff_text=(
                    "--- a/plan.md\n+++ b/plan.md\n"
                    "@@ -8 +8 @@\n-    status: done\n"
                    "+    status: current\n"
                ),
                pre_snapshot={plan_path: "before"},
                stdout="",
                introduced_findings=(
                    _Rec(
                        id="post-edit-parse-failure",
                        source="apply-validation",
                        severity="critical",
                        step_id=1,
                        title="post-edit plan failed to parse",
                        body="more than one step has status=current",
                        suggested_action=None,
                    ),
                ),
            )

        def fake_revert(snapshot):
            revert_called["v"] = True

        def fake_input(prompt):
            prompt_called["v"] = True
            return "y"

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )
        monkeypatch.setattr(
            launcher_module, "_restore_text_files", fake_revert
        )
        monkeypatch.setattr("builtins.input", fake_input)
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )
        rec = Recommendation(
            id="step1-detail-reconcile-parsebreak",
            source="detail-reconcile",
            severity="critical",
            step_id=1,
            title="status should flip",
            body="acceptance criteria not met",
            suggested_action=None,
        )
        msg = action(rec)
        assert revert_called["v"] is True
        assert prompt_called["v"] is False, (
            "user prompt must not run when parse failure introduced"
        )
        assert "post-edit plan failed to parse" in msg.lower()
        assert "reverted" in msg.lower()

    def test_action_fn_blocked_verdict_reverts_and_reports(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.launcher import ApplyFindingResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        revert_called: dict = {"v": False}

        def fake_apply_finding(plan_path_arg, **kwargs):
            return ApplyFindingResult(
                step_id=1, exit_code=0, verdict="BLOCKED",
                summary="would create new file; not allowed",
                diff_text="", pre_snapshot={plan_path: "x"},
                stdout="",
            )

        def fake_revert(snapshot):
            revert_called["v"] = True

        from plan_tool import launcher as launcher_module
        monkeypatch.setattr(
            launcher_module, "apply_finding", fake_apply_finding
        )
        monkeypatch.setattr(
            launcher_module, "_restore_text_files", fake_revert
        )

        # Input must NOT be called — BLOCKED short-circuits before the
        # keep-changes prompt.
        def fail_input(prompt: str) -> str:
            raise AssertionError("must not prompt on BLOCKED verdict")

        monkeypatch.setattr("builtins.input", fail_input)
        monkeypatch.setattr(cli_module.sys.stdin, "isatty", lambda: True)

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )
        rec = Recommendation(
            id="step1-detail-reconcile-ccc",
            source="detail-reconcile",
            severity="medium",
            step_id=1, title="t",
            body="add new file",
            suggested_action=None,
        )
        msg = action(rec)
        assert revert_called["v"] is True
        assert "BLOCKED" in msg

    def test_action_fn_dispatches_detail_force(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The --force suffix is honored without entering recovery mode."""
        from plan_tool.cli import app as cli_module
        from plan_tool.detail import DetailResult
        from plan_tool.locator import build_plan_tool_context

        plan_path = _basic_plan(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)

        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        captured: dict = {}

        def fake_generate_detail(plan_path_arg, **kwargs):
            captured["kwargs"] = kwargs
            return [
                DetailResult(
                    step_id=kwargs["step_id"],
                    output_path=tmp_path / "docs" / "step.md",
                    written=True,
                )
            ]

        from plan_tool import detail as detail_module
        monkeypatch.setattr(
            detail_module, "generate_detail", fake_generate_detail
        )

        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan"
        )

        rec = Recommendation(
            id="step1-detail-abc",
            source="detail-body",
            severity="medium",
            step_id=1,
            title="Step 1: detail body missing section",
            body="missing impl",
            suggested_action="plan-tool detail plan --step 1 --force",
        )
        msg = action(rec)
        assert msg is not None
        assert captured["kwargs"]["force"] is True
        assert "recovery_only" not in captured["kwargs"]


class TestReuseSavedReviewPrompt:
    """When a saved review exists, cmd_review offers to walk it instead
    of running a fresh claude review."""

    def _make_repo_with_plan(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: t\n"
            "    files: [foo.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        return manifest

    def _seed_saved_review(
        self,
        tmp_path: Path,
        *,
        recommendations: list[Recommendation] | None = None,
        annotations: dict[str, Annotation] | None = None,
    ) -> Path:
        from plan_tool.fingerprint import compute_code_fingerprint
        from plan_tool.parser import parse_plan
        from plan_tool.review_persistence import compute_plan_fingerprint

        if recommendations is None:
            recommendations = [
                Recommendation(
                    id="step1-deps-old",
                    source="deps",
                    severity="high",
                    step_id=1,
                    title="some prior finding",
                    body="…",
                    suggested_action=None,
                )
            ]
        # Fingerprint the save against current disk so the freshness gate
        # reads it as fresh (and reuse is actually offered).
        plan_path = tmp_path / "plan.md"
        plan = parse_plan(plan_path)
        return save_review(
            plan_slug="plan",
            plan_path="plan.md",
            repo_root=tmp_path,
            report_md="prior report",
            recommendations=recommendations,
            annotations=annotations,
            plan_fingerprint=compute_plan_fingerprint(plan_path),
            code_fingerprint=compute_code_fingerprint(plan, plan_path, tmp_path),
        )

    def test_yes_walks_saved_skips_claude(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._make_repo_with_plan(tmp_path)
        saved_path = self._seed_saved_review(tmp_path)
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        # Sentinel: review_plan_full must NOT be called when reuse=yes.
        def fail_full(*args, **kwargs):
            raise AssertionError(
                "review_plan_full must not run when user reuses saved review"
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fail_full)

        # Walk fake records the saved review handed to it.
        captured: dict = {}

        def fake_walk(saved, **kwargs):
            captured["saved"] = saved
            from plan_tool.review_walk import WalkResult
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        monkeypatch.setattr("builtins.input", lambda prompt: "y")

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        assert captured.get("saved") is not None
        assert captured["saved"].path == saved_path
        out = capsys.readouterr().out
        assert "Walking saved review" in out

    def test_no_runs_fresh_review(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        called = {"full": False, "walk": False}

        def fake_full(plan_path, **kwargs):
            called["full"] = True
            return ReviewResult(
                report="fresh report",
                recommendations=[],
                dry_run=False,
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)

        def fake_walk(saved, **kwargs):
            called["walk"] = True
            from plan_tool.review_walk import WalkResult
            return WalkResult(answered=0, quit_early=False)

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fake_walk)
        # Default-no behavior: any non-y input runs fresh.
        monkeypatch.setattr("builtins.input", lambda prompt: "n")

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        assert called["full"] is True

    def test_blank_answer_runs_fresh(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Blank input on the reuse prompt = default (no), runs fresh."""
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        called_full = {"v": False}

        def fake_full(plan_path, **kwargs):
            called_full["v"] = True
            return ReviewResult(
                report="fresh", recommendations=[], dry_run=False
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)
        monkeypatch.setattr("builtins.input", lambda prompt: "")

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        assert called_full["v"] is True

    def test_no_prompt_when_no_saved_review(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        # Intentionally NO saved review.
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        called_full = {"v": False}

        def fake_full(plan_path, **kwargs):
            called_full["v"] = True
            return ReviewResult(
                report="fresh", recommendations=[], dry_run=False
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)

        # Input shouldn't be called at all — assert via fail-on-call.
        def fail_input(prompt: str) -> str:
            raise AssertionError(
                "must not prompt to reuse when no saved review exists"
            )

        monkeypatch.setattr("builtins.input", fail_input)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        assert called_full["v"] is True

    def test_non_tty_auto_accepts_fresh_save_without_walking(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Non-TTY context (CI) with a FRESH save auto-accepts reuse —
        no prompt, no fresh claude review (parity with the reconcile core
        and completeness-audit's --reuse-audit unset default). The walk is
        per-finding, so it reports the findings and returns instead, exactly
        as a fresh non-TTY review does."""
        from plan_tool.cli import app as cli_module

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, False)

        # review_plan_full must NOT run — the fresh save is auto-accepted.
        def fail_full(*args, **kwargs):
            raise AssertionError(
                "review_plan_full must not run when a fresh save auto-accepts"
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fail_full)

        def fail_walk(saved, **kwargs):
            raise AssertionError("the walk must not run on non-interactive stdin")

        monkeypatch.setattr("plan_tool.cli.review_cmd.walk_recommendations", fail_walk)

        def fail_input(prompt: str) -> str:
            raise AssertionError("must not prompt in non-TTY context")

        monkeypatch.setattr("builtins.input", fail_input)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "non-interactive stdin" in captured.err
        # The saved findings are still reported, so the operator sees them.
        assert "some prior finding" in captured.out

    def test_cmd_review_remote_non_tty_reused_failed_finding_reprompts(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._make_repo_with_plan(tmp_path)
        rec = _rec(
            "failed-finding",
            title="Failed finding",
            body="failed finding detail",
            suggested_action="failed finding action",
        )
        saved_path = self._seed_saved_review(
            tmp_path,
            recommendations=[rec],
            annotations={rec.id: Annotation(status="failed", note="timed out")},
        )
        monkeypatch.chdir(tmp_path)
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"], requests)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.review_plan_full",
            lambda *args, **kwargs: pytest.fail("fresh review must not run"),
        )

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        assert len(requests) == 1
        assert load_review(saved_path).annotations[rec.id] == Annotation(status="skip", note="")
        out = capsys.readouterr().out
        assert "(reuse) walking saved review" in out
        assert "Walking saved review" in out
        assert out.count("failed finding detail") == 1
        assert out.count("failed finding action") == 1

    @pytest.mark.parametrize("status", ["applied", "skip", "open"])
    def test_cmd_review_remote_non_tty_reused_terminal_annotations_remain_report_only(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        status: str,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._make_repo_with_plan(tmp_path)
        rec = _rec(
            f"{status}-finding",
            title=f"{status} finding",
            body=f"{status} detail remains visible",
            suggested_action=f"{status} action remains visible",
        )
        self._seed_saved_review(
            tmp_path,
            recommendations=[rec],
            annotations={rec.id: Annotation(status=status, note="already handled")},
        )
        monkeypatch.chdir(tmp_path)
        _configure_remote_non_tty(monkeypatch, tmp_path)

        def fail_sleep(_: float) -> None:
            raise AssertionError("terminal annotation must not request remote input")

        monkeypatch.setattr(human_io.time, "sleep", fail_sleep)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.review_plan_full",
            lambda *args, **kwargs: pytest.fail("fresh review must not run"),
        )

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        out = capsys.readouterr().out
        assert f"{status} detail remains visible" in out
        assert f"{status} action remains visible" in out
        assert list(tmp_path.glob("*.request.json")) == []

    def test_cmd_review_remote_non_tty_reused_mixed_findings_keeps_excluded_findings_visible(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._make_repo_with_plan(tmp_path)
        promptable = _rec("promptable", title="Promptable saved finding")
        hidden_info = _rec(
            "hidden-info",
            severity="info",
            title="Hidden saved info",
            body="hidden saved info detail",
            suggested_action="hidden saved info action",
        )
        terminal = _rec(
            "terminal",
            title="Terminal saved finding",
            body="terminal saved detail",
            suggested_action="terminal saved action",
        )
        self._seed_saved_review(
            tmp_path,
            recommendations=[promptable, hidden_info, terminal],
            annotations={terminal.id: Annotation(status="open", note="reviewed")},
        )
        monkeypatch.chdir(tmp_path)
        requests: list[dict[str, str]] = []
        _configure_remote_non_tty(monkeypatch, tmp_path, ["s"], requests)
        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.review_plan_full",
            lambda *args, **kwargs: pytest.fail("fresh review must not run"),
        )

        assert cli_module.main(["--manifest", str(manifest), "review", "plan"]) == 0
        out = capsys.readouterr().out
        assert "hidden saved info detail" in out
        assert "hidden saved info action" in out
        assert "terminal saved detail" in out
        assert "terminal saved action" in out
        assert len(requests) == 1

    def test_non_tty_stale_save_runs_fresh(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Non-TTY context with a STALE save declines reuse and runs a
        fresh review — the freshness gate precedes the auto-accept."""
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        # Drift the watched code file → the located save goes stale.
        (tmp_path / "foo.py").write_text("y\ny\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, False)

        called_full = {"v": False}

        def fake_full(plan_path, **kwargs):
            called_full["v"] = True
            return ReviewResult(
                report="fresh", recommendations=[], dry_run=False
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)

        def fail_input(prompt: str) -> str:
            raise AssertionError("must not prompt in non-TTY context")

        monkeypatch.setattr("builtins.input", fail_input)

        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan"]
        )
        assert rc == 0
        assert called_full["v"] is True

    def test_step_filter_skips_reuse_prompt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--step N skips the reuse prompt — saved plan-wide review may
        not align with a step-specific request."""
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        def fake_full(plan_path, **kwargs):
            return ReviewResult(
                report="fresh", recommendations=[], dry_run=False
            )

        monkeypatch.setattr("plan_tool.cli.review_cmd.review_plan_full", fake_full)

        def fail_input(prompt: str) -> str:
            raise AssertionError(
                "must not prompt when --step is set"
            )

        monkeypatch.setattr("builtins.input", fail_input)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "reconcile",
                "plan",
                "--step",
                "1",
            ]
        )
        assert rc == 0

    def test_stale_review_runs_fresh(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A code-drifted saved review declines reuse: the gate runs a
        fresh review and prints the attributed drift warning to stderr."""
        from plan_tool.cli import app as cli_module
        from plan_tool.review import ReviewResult

        manifest = self._make_repo_with_plan(tmp_path)
        self._seed_saved_review(tmp_path)
        # Edit the watched (step.files) code file after the save → code drift.
        (tmp_path / "foo.py").write_text("y\nz\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        _force_tty(monkeypatch, True)

        called_full = {"v": False}

        def fake_full(plan_path, **kwargs):
            called_full["v"] = True
            return ReviewResult(
                report="fresh", recommendations=[], dry_run=False
            )

        monkeypatch.setattr(
            "plan_tool.cli.review_cmd.review_plan_full", fake_full
        )
        # --yes would accept a fresh save; the gate must decline before it.
        rc = cli_module.main(
            ["--manifest", str(manifest), "reconcile", "plan", "--yes"]
        )
        assert rc == 0
        assert called_full["v"] is True
        err = capsys.readouterr().err
        # Grouped under the owning step, at info level (normal operation).
        assert "step 1: t" in err
        assert "foo.py" in err
        assert "foo.py (step 1:" not in err  # not the inline form
        assert "--reconcile" in err


class TestFileCheckCreateTarget:
    """MISSING_PARENT file-check recs are dispatchable on apply: their
    declared path can be moved files: -> creates: on the step."""

    def test_missing_parent_is_dispatchable(self) -> None:
        from plan_tool.review_walk import (
            file_check_create_target,
            is_dispatchable,
        )

        rec = Recommendation(
            id="step8-file-check-abc", source="file-check", severity="medium",
            step_id=8, title="Step 8: declared file path doesn't resolve",
            body="`a/b.ts` — parent dir `a/` doesn't exist",
            suggested_action="verify the path or pass `--allow-missing-parent`",
            file_path="a/b.ts",
        )
        assert file_check_create_target(rec) == "a/b.ts"
        assert is_dispatchable(rec) is True

    def test_file_check_without_path_not_dispatchable(self) -> None:
        """NEW-on-DONE file-check shapes leave file_path unset — their
        resolution is reconcile, not a path move — so apply falls back to
        acknowledgment-only."""
        from plan_tool.review_walk import (
            file_check_create_target,
            is_dispatchable,
        )

        rec = Recommendation(
            id="step3-file-check-xyz", source="file-check", severity="medium",
            step_id=3, title="Step 3: declared file missing despite step done",
            body="`a/b.ts` missing on disk although step 3 is marked done",
            suggested_action="run reconcile to confirm whether the work landed",
        )
        assert file_check_create_target(rec) is None
        assert is_dispatchable(rec) is False


def _merge_directive_rec(
    *, step_ids=(3, 4), severity="info", rec_id="granularity-merge-3-4"
) -> Recommendation:
    """A ``granularity-merge`` pairwise finding carrying a ``merge`` directive
    marker — the shape ``granularity._merge_rec`` emits (``step_id`` = low
    member id, ``info`` severity by default)."""
    from plan_tool.review import MERGE_ACTION_MERGE, render_merge_action

    lo, hi = step_ids[0], step_ids[-1]
    suggested = (
        f"Consider merging steps {lo} and {hi}. "
        + render_merge_action(MERGE_ACTION_MERGE, step_ids)
    )
    return Recommendation(
        id=rec_id,
        source="granularity-merge",
        severity=severity,
        step_id=step_ids[0],
        title=f"Steps {lo}–{hi} may be over-fragmented",
        body="adjacent dependent steps",
        suggested_action=suggested,
    )


class TestMergeDirectiveDispatch:
    """A ``granularity-merge`` finding carrying a ``merge`` directive is a
    dispatchable structural remedy — even at ``info`` severity — while a
    directive-less same-source finding is not."""

    def test_merge_directive_is_dispatchable(self) -> None:
        from plan_tool.review_walk import is_dispatchable, merge_remedy_target

        rec = _merge_directive_rec(step_ids=(3, 4))
        action = merge_remedy_target(rec)
        assert action is not None
        assert action.kind == "merge"
        assert action.step_ids == (3, 4)
        assert is_dispatchable(rec) is True

    def test_info_level_merge_directive_visible_without_include_info(
        self, tmp_path: Path
    ) -> None:
        # An info-level merge directive is part of the targeted structural walk
        # surface, so skip_info (the default hide) must still present it.
        saved = _make_saved_review(
            tmp_path,
            _rec("a-1", severity="high"),
            _merge_directive_rec(step_ids=(3, 4), rec_id="granularity-merge-3-4"),
        )
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["s", "s"]),
            output_fn=out_fn,
            skip_info=True,
        )
        # Both recs presented: the high one and the info merge directive.
        assert result.answered == 2
        reloaded = load_review(saved.path)
        assert "granularity-merge-3-4" in reloaded.annotations
        assert "skipping" not in "\n".join(output)

    def test_gapped_merge_finding_visible_without_include_info(
        self, tmp_path: Path
    ) -> None:
        # A gapped pairwise granularity-merge finding carries NO machine marker
        # (non-dispatchable, recommend-only) but is still merge advice, so
        # skip_info must keep it visible — otherwise the "reorder then merge"
        # guidance is invisible unless the operator passes --include-info.
        gapped = _rec(
            "granularity-merge-2-5",
            source="granularity-merge",
            severity="info",
            step_id=2,
            title="Steps 2 and 5 may be a single step",
            suggested_action="Consider merging steps 2 and 5, but their ids "
            "are not adjacent — reorder first.",  # no marker
        )
        saved = _make_saved_review(tmp_path, _rec("a-1", severity="high"), gapped)
        out_fn, output = _capture_output()
        result = walk_recommendations(
            saved,
            input_fn=_queue_input(["s", "s"]),
            output_fn=out_fn,
            skip_info=True,
        )
        assert result.answered == 2  # both the high rec AND the gapped merge
        assert "granularity-merge-2-5" in load_review(saved.path).annotations
        assert "skipping" not in "\n".join(output)

    def test_granularity_merge_without_directive_not_dispatchable(self) -> None:
        from plan_tool.review_walk import is_dispatchable, merge_remedy_target

        rec = Recommendation(
            id="granularity-merge-legacy",
            source="granularity-merge",
            severity="info",
            step_id=3,
            title="Steps 3–4 may be over-fragmented",
            body="adjacent dependent steps",
            suggested_action="Consider merging steps 3 and 4.",  # no marker
        )
        assert merge_remedy_target(rec) is None
        assert is_dispatchable(rec) is False


def _split_escalation_rec(
    *, severity="medium", step_id=4, rec_id="step4-split-abc"
) -> Recommendation:
    """A ``granularity-split`` MIXED-STEP finding — a step fusing a refactor
    with new behavior — the shape ``granularity.parse_mixed_step_findings``
    persists at ``medium`` severity."""
    from plan_tool.granularity import GRANULARITY_SPLIT_SOURCE

    return Recommendation(
        id=rec_id,
        source=GRANULARITY_SPLIT_SOURCE,
        severity=severity,
        step_id=step_id,
        title=f"Step {step_id} mixes a refactor with new behavior",
        body="split the refactor half from the feature half",
        suggested_action="plan-tool split demo --step 4",
    )


class TestSplitEscalationTarget:
    """The ``medium`` ``granularity-split`` MIXED-STEP finding is dispatchable
    to the escalate-to-split bridge, but ONLY when the caller opts the source
    into ``extra_apply_sources`` (the completeness-apply lane) — and never at
    ``info`` severity."""

    def test_medium_granularity_split_dispatchable_only_with_opt_in(
        self,
    ) -> None:
        from plan_tool.review_walk import (
            is_dispatchable,
            split_escalation_target,
        )

        rec = _split_escalation_rec(severity="medium")
        # No opt-in: not dispatchable (a generic reconcile/review walk that
        # loads a completeness sidecar must not auto-dispatch it).
        assert split_escalation_target(rec) is False
        assert is_dispatchable(rec) is False
        # completeness-apply opts the source in: dispatchable.
        extra = frozenset({"granularity-split"})
        assert (
            split_escalation_target(rec, extra_apply_sources=extra) is True
        )
        assert is_dispatchable(rec, extra_apply_sources=extra) is True

    def test_info_granularity_split_not_dispatchable(self) -> None:
        from plan_tool.review_walk import (
            is_dispatchable,
            split_escalation_target,
        )

        rec = _split_escalation_rec(severity="info")
        extra = frozenset({"granularity-split"})
        # Only the medium mixed-step signal dispatches; a low-confidence info
        # split hint never reaches the bridge, even opted in.
        assert (
            split_escalation_target(rec, extra_apply_sources=extra) is False
        )
        assert is_dispatchable(rec, extra_apply_sources=extra) is False

    def test_info_code_split_not_auto_dispatched(self) -> None:
        # The reconcile-lane code-grounded split producer emits an ``info``
        # ``granularity-split`` finding; like the deterministic info split
        # hints, it must never auto-dispatch to the escalate-to-split bridge.
        from plan_tool.review import (
            HeuristicHit,
            _code_reveals_split_recommendations,
        )
        from plan_tool.review_walk import (
            is_dispatchable,
            split_escalation_target,
        )

        plan = Plan(
            title="t",
            status=PlanStatus.IN_PROGRESS,
            priority=Priority.MEDIUM,
            steps=[
                Step(id=1, title="Add alpha and beta handlers",
                     files=["alpha.py", "beta.py", "gamma.py"]),
            ],
        )
        hits = [
            HeuristicHit(step_id=1, file="alpha.py", symbol="alpha", pattern="def alpha"),
            HeuristicHit(step_id=1, file="beta.py", symbol="beta", pattern="def beta"),
        ]
        # Producer takes the prebuilt hits-by-step map (all hits here are step 1).
        recs = _code_reveals_split_recommendations({1: hits}, plan, plan_name="demo")
        assert len(recs) == 1
        rec = recs[0]
        assert rec.source == "granularity-split" and rec.severity == "info"
        extra = frozenset({"granularity-split"})
        assert split_escalation_target(rec, extra_apply_sources=extra) is False
        assert is_dispatchable(rec, extra_apply_sources=extra) is False

    def test_granularity_split_not_routed_as_apply_finding(self) -> None:
        from plan_tool.review_walk import should_apply_as_finding

        rec = _split_escalation_rec(severity="medium")
        # Even opted into the apply-finding source set, a structural source is
        # excluded from the apply_finding route (it routes to the split bridge).
        extra = frozenset({"granularity-split"})
        assert should_apply_as_finding(rec) is False
        assert should_apply_as_finding(rec, extra_sources=extra) is False


class TestApplySkipDowngradesAnnotation:
    """An action handler can flip ``state.apply_skip`` to record a skip
    instead of applied — the file-check 'path is wrong' branch uses this."""

    def _fc_rec(self) -> Recommendation:
        return Recommendation(
            id="step8-file-check-abc", source="file-check", severity="medium",
            step_id=8, title="Step 8: declared file path doesn't resolve",
            body="`a/b.ts` — parent dir `a/` doesn't exist",
            suggested_action="verify the path",
            file_path="a/b.ts",
        )

    def test_apply_records_skip_when_handler_sets_apply_skip(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review_walk import WalkState

        saved = _make_saved_review(tmp_path, self._fc_rec())
        out_fn, _ = _capture_output()
        state = WalkState()

        def handler(rec):
            state.apply_skip = True
            return "path is wrong; nothing moved"

        walk_recommendations(
            saved,
            input_fn=_queue_input(["a"]),
            output_fn=out_fn,
            action_fn=handler,
            state=state,
        )
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step8-file-check-abc"]
        assert ann.status == "skip"
        assert ann.note == "path is wrong; nothing moved"
        # A user/handler decline is not a drift halt.
        assert ann.halt_reason == ""

    def test_pre_apply_drift_halt_records_drift_halt_reason(
        self, tmp_path: Path
    ) -> None:
        """A pre-apply drift halt records status=skip with
        halt_reason='drift', so downstream tooling can tell a safety
        skip from a user decline (both were plain 'skip' before)."""
        from plan_tool.review_walk import WalkState

        saved = _make_saved_review(tmp_path, self._fc_rec())
        out_fn, _ = _capture_output()
        state = WalkState()

        def handler(rec):
            # Pre-apply drift halt: nothing landed.
            state.halt_requested = True
            state.halt_apply_landed = False
            return "pre-apply drift detected; skipping for safety"

        walk_recommendations(
            saved,
            input_fn=_queue_input(["a"]),
            output_fn=out_fn,
            action_fn=handler,
            state=state,
        )
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step8-file-check-abc"]
        assert ann.status == "skip"
        assert ann.halt_reason == "drift"

    def test_apply_records_applied_when_handler_leaves_flag(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.review_walk import WalkState

        saved = _make_saved_review(tmp_path, self._fc_rec())
        out_fn, _ = _capture_output()
        state = WalkState()

        def handler(rec):
            return "moved a/b.ts to creates: on step 8; plan written"

        walk_recommendations(
            saved,
            input_fn=_queue_input(["a"]),
            output_fn=out_fn,
            action_fn=handler,
            state=state,
        )
        reloaded = load_review(saved.path)
        ann = reloaded.annotations["step8-file-check-abc"]
        assert ann.status == "applied"


@pytest.mark.integration
class TestFileCheckCreateDispatch:
    """``_build_review_action_fn`` resolves a MISSING_PARENT file-check
    finding by moving its path files: -> creates: ((c)reate) or leaving
    it for the user to fix ((f)ix → skip)."""

    def _plan_with_missing_parent(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: P\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 2\n"
            "    title: build dashboard\n"
            "    files: [newdir/new.py, existing.py]\n"
            "    status: pending\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "existing.py").write_text("x\n", encoding="utf-8")
        (tmp_path / ".git").mkdir()
        return plan_path

    def _fc_rec(self) -> Recommendation:
        return Recommendation(
            id="step2-file-check-abc", source="file-check", severity="medium",
            step_id=2, title="Step 2: declared file path doesn't resolve",
            body="`newdir/new.py` — parent dir `newdir/` doesn't exist",
            suggested_action="verify the path or pass `--allow-missing-parent`",
            file_path="newdir/new.py",
        )

    def test_create_moves_path_files_to_creates(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.locator import build_plan_tool_context
        from plan_tool.parser import parse_plan
        from plan_tool.review_walk import WalkState

        plan_path = self._plan_with_missing_parent(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )
        monkeypatch.setattr("builtins.input", lambda _prompt: "c")

        state = WalkState()
        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan", state=state
        )
        msg = action(self._fc_rec())

        assert "moved" in msg and "creates:" in msg
        assert state.apply_skip is False
        step = next(s for s in parse_plan(plan_path).steps if s.id == 2)
        assert "newdir/new.py" not in step.files
        assert "existing.py" in step.files
        assert "newdir/new.py" in step.creates

    def test_fix_leaves_plan_unchanged_and_sets_skip(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.locator import build_plan_tool_context
        from plan_tool.parser import parse_plan
        from plan_tool.review_walk import WalkState

        plan_path = self._plan_with_missing_parent(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )
        monkeypatch.setattr("builtins.input", lambda _prompt: "f")

        state = WalkState()
        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan", state=state
        )
        msg = action(self._fc_rec())

        assert state.apply_skip is True
        assert "fix or remove" in msg
        step = next(s for s in parse_plan(plan_path).steps if s.id == 2)
        assert "newdir/new.py" in step.files
        assert "newdir/new.py" not in step.creates

    def test_apply_all_auto_creates_without_prompt(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.cli import app as cli_module
        from plan_tool.locator import build_plan_tool_context
        from plan_tool.parser import parse_plan
        from plan_tool.review_walk import WalkState

        plan_path = self._plan_with_missing_parent(tmp_path)
        manifest = _setup_manifest(tmp_path)
        monkeypatch.chdir(tmp_path)
        ctx = build_plan_tool_context(
            None, manifest_path=manifest, repo_root_override=None
        )

        def fail_input(_prompt: str) -> str:
            raise AssertionError("apply-all must not prompt")

        monkeypatch.setattr("builtins.input", fail_input)

        state = WalkState(yes_to_all=True)
        action = cli_module._build_review_action_fn(
            ctx=ctx, plan_path=plan_path, plan_name="plan", state=state
        )
        msg = action(self._fc_rec())
        assert "moved" in msg
        step = next(s for s in parse_plan(plan_path).steps if s.id == 2)
        assert "newdir/new.py" in step.creates


class TestStructuralOutcomeKernel:
    """Direct unit tests for ``apply_structural_outcome`` — the shared
    WalkState tail the four structural dispatchers route through. Pins the
    boundaries the dispatcher-level tests exercise only indirectly.
    """

    def test_kernel_skip_sets_apply_skip(self):
        state = WalkState()
        rec = _rec()
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=False)
        )
        assert state.apply_skip is True
        assert state.halt_requested is False
        assert state.halt_apply_landed is False
        assert state.applied_structural_finding_ids == set()

    def test_kernel_resolved_sets_nothing(self):
        state = WalkState()
        rec = _rec()
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=True)
        )
        assert state.apply_skip is False
        assert state.halt_requested is False
        assert state.halt_apply_landed is False
        assert state.applied_structural_finding_ids == set()

    def test_kernel_record_finding_id_adds_rec_id(self):
        state = WalkState()
        rec = _rec()
        effects = StructuralOutcomeEffects(resolved=True, record_finding_id=True)
        apply_structural_outcome(state, rec, effects)
        assert state.applied_structural_finding_ids == {rec.id}
        # A second call with the same rec is idempotent (set semantics).
        apply_structural_outcome(state, rec, effects)
        assert state.applied_structural_finding_ids == {rec.id}

    def test_kernel_halt_sets_both_halt_fields(self):
        state = WalkState()
        rec = _rec()
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=True, halt=True)
        )
        assert state.halt_requested is True
        assert state.halt_apply_landed is True

    def test_kernel_never_touches_apply_failed(self):
        rec = _rec()
        for effects in (
            StructuralOutcomeEffects(resolved=False),
            StructuralOutcomeEffects(resolved=True),
            StructuralOutcomeEffects(resolved=True, record_finding_id=True),
            StructuralOutcomeEffects(resolved=True, halt=True),
            StructuralOutcomeEffects(
                resolved=False, record_finding_id=True, halt=True
            ),
        ):
            state = WalkState()
            apply_structural_outcome(state, rec, effects)
            assert state.apply_failed is False

    def test_kernel_does_not_reset_apply_skip_to_false(self):
        state = WalkState()
        state.apply_skip = True  # pre-set, as an earlier arm might leave it
        rec = _rec()
        apply_structural_outcome(
            state, rec, StructuralOutcomeEffects(resolved=True)
        )
        # The kernel only ever SETS True; the walk owns the reset.
        assert state.apply_skip is True


class TestStructuralApplyAllowedGate:
    """Direct unit tests for ``structural_apply_allowed`` — the shared
    ``opt_in and not state.yes_to_all`` gate the three bridge dispatchers
    (escalate/reground/merge) route through. File-check's inverted rule is
    pinned separately by ``TestFileCheckCreateDispatch`` (its ``yes_to_all``
    path still auto-creates, proving it is NOT routed through this helper).
    """

    def test_structural_apply_allowed_true_when_opted_in_and_no_fast_forward(self):
        assert structural_apply_allowed(True, WalkState(yes_to_all=False)) is True

    def test_structural_apply_allowed_false_under_yes_to_all(self):
        assert structural_apply_allowed(True, WalkState(yes_to_all=True)) is False

    def test_structural_apply_allowed_false_when_not_opted_in(self):
        # Not opted in → False regardless of the fast-forward flag.
        assert structural_apply_allowed(False, WalkState(yes_to_all=False)) is False
        assert structural_apply_allowed(False, WalkState(yes_to_all=True)) is False

    def test_structural_apply_allowed_returns_plain_bool(self):
        # Bool operands → a real bool, not the truthy operand.
        result = structural_apply_allowed(True, WalkState(yes_to_all=False))
        assert result is True
        assert isinstance(result, bool)


def _plan_with_steps(*specs) -> Plan:
    """Build a minimal Plan from ``(id, title[, change_type])`` specs."""
    steps = []
    for spec in specs:
        step_id, title = spec[0], spec[1]
        change_type = spec[2] if len(spec) > 2 else ChangeType.FEATURE
        steps.append(Step(id=step_id, title=title, change_type=change_type))
    return Plan(
        title="P",
        status=PlanStatus.PLANNING,
        priority=Priority.MEDIUM,
        steps=steps,
    )


class TestComputeTargetSignature:
    def test_compute_target_signature_stable_for_same_plan_and_ids(self):
        plan = _plan_with_steps((1, "Alpha"), (2, "Beta"), (3, "Gamma"))
        first = compute_target_signature(plan, [1, 3])
        second = compute_target_signature(plan, [1, 3])
        assert first == second

    def test_compute_target_signature_changes_when_target_title_changes(self):
        before = _plan_with_steps((1, "Alpha"), (2, "Beta"))
        after = _plan_with_steps((1, "Renamed"), (2, "Beta"))
        assert compute_target_signature(before, [1]) != compute_target_signature(
            after, [1]
        )

    def test_compute_target_signature_ignores_non_target_edits(self):
        before = _plan_with_steps((1, "Alpha"), (2, "Beta"))
        after = _plan_with_steps((1, "Alpha"), (2, "Beta renamed"))
        # Step 2 is not a target, so editing it leaves the digest unchanged.
        assert compute_target_signature(before, [1]) == compute_target_signature(
            after, [1]
        )

    def test_compute_target_signature_order_independent(self):
        plan = _plan_with_steps((1, "Alpha"), (2, "Beta"), (3, "Gamma"))
        assert compute_target_signature(plan, [3, 1]) == compute_target_signature(
            plan, [1, 3]
        )

    def test_compute_target_signature_changes_when_change_type_changes(self):
        before = _plan_with_steps((1, "Alpha", ChangeType.FEATURE))
        after = _plan_with_steps((1, "Alpha", ChangeType.REFACTOR))
        assert compute_target_signature(before, [1]) != compute_target_signature(
            after, [1]
        )

    def test_compute_target_signature_missing_id_does_not_raise(self):
        plan = _plan_with_steps((1, "Alpha"))
        # id 99 names no step; the helper returns a digest rather than raising.
        assert isinstance(compute_target_signature(plan, [99]), str)

    def test_compute_target_signature_missing_id_distinct_from_present(self):
        plan = _plan_with_steps((1, "Alpha"))
        present = compute_target_signature(plan, [1])
        missing = compute_target_signature(plan, [99])
        assert present != missing


class TestRecommendationTargetSignature:
    def test_recommendation_target_signature_round_trips(self, tmp_path):
        rec = _rec(rec_id="r-sig", target_signature="deadbeef")
        saved = _make_saved_review(tmp_path, rec)
        loaded = saved.recommendations[0]
        assert loaded.target_signature == "deadbeef"

        # Survives an annotation write (asdict → Recommendation(**r) round-trip).
        path = save_review(
            plan_slug="x",
            plan_path="plans/x.md",
            repo_root=tmp_path,
            report_md="report",
            recommendations=[rec],
        )
        update_annotation(path, "r-sig", Annotation(status="skip", note=""))
        reloaded = load_review(path)
        assert reloaded.recommendations[0].target_signature == "deadbeef"

    def test_recommendation_target_signature_defaults_none(self, tmp_path):
        rec = _rec(rec_id="r-none")
        assert rec.target_signature is None
        saved = _make_saved_review(tmp_path, rec)
        assert saved.recommendations[0].target_signature is None


def _reground_rec(step_ids, rec_id="rg-1") -> Recommendation:
    """A re-ground finding: ``granularity-merge`` source, no ``step_id``,
    target ids inside a ``→ reground steps: …`` marker."""
    from plan_tool.review import MERGE_ACTION_REGROUND, render_merge_action

    return Recommendation(
        id=rec_id,
        source="granularity-merge",
        severity="info",
        step_id=None,
        title="Re-ground already-built steps",
        body="…",
        suggested_action="mark them done — "
        + render_merge_action(MERGE_ACTION_REGROUND, step_ids),
    )


def _pairwise_merge_rec(step_ids, rec_id="mg-1") -> Recommendation:
    """A contiguous pairwise merge finding: ``granularity-merge`` source,
    ``step_id`` set, target ids inside a ``→ merge steps: …`` marker."""
    from plan_tool.review import MERGE_ACTION_MERGE, render_merge_action

    return Recommendation(
        id=rec_id,
        source="granularity-merge",
        severity="info",
        step_id=step_ids[0],
        title="Merge adjacent fragmented steps",
        body="…",
        suggested_action="plan-tool merge — "
        + render_merge_action(MERGE_ACTION_MERGE, step_ids),
    )


def _split_rec(step_id, severity="medium", rec_id="sp-1") -> Recommendation:
    """A ``granularity-split`` MIXED-STEP finding targeting one ``step_id``."""
    return Recommendation(
        id=rec_id,
        source="granularity-split",
        severity=severity,
        step_id=step_id,
        title="Step mixes concerns",
        body="…",
        suggested_action="plan-tool split",
    )


class TestDirectiveTargetIds:
    def test_directive_target_ids_reground(self):
        from plan_tool.review_walk import directive_target_ids

        assert directive_target_ids(_reground_rec((3, 4))) == (3, 4)

    def test_directive_target_ids_pairwise_merge(self):
        from plan_tool.review_walk import directive_target_ids

        assert directive_target_ids(_pairwise_merge_rec((2, 3))) == (2, 3)

    def test_directive_target_ids_medium_split(self):
        from plan_tool.review_walk import directive_target_ids

        assert directive_target_ids(_split_rec(5)) == (5,)

    def test_directive_target_ids_none_for_non_directive(self):
        from plan_tool.review_walk import directive_target_ids

        for src in ("deps", "file-check", "claude"):
            assert directive_target_ids(_rec(source=src)) is None

    def test_directive_target_ids_none_for_info_split(self):
        from plan_tool.review_walk import directive_target_ids

        assert directive_target_ids(_split_rec(5, severity="info")) is None

    def test_directive_target_ids_none_for_gapped_merge_advisory(self):
        from plan_tool.review_walk import directive_target_ids

        gapped = Recommendation(
            id="mg-gap",
            source="granularity-merge",
            severity="info",
            step_id=1,
            title="Gapped pair — recommend only",
            body="…",
            suggested_action="review these steps",  # no marker
        )
        assert directive_target_ids(gapped) is None


class TestStampTargetSignatures:
    def test_stamp_sets_signature_on_each_directive_shape(self):
        from plan_tool.review_walk import (
            directive_target_ids,
            stamp_target_signatures,
        )

        plan = _plan_with_steps(
            (2, "Beta"), (3, "Gamma"), (4, "Delta"), (5, "Epsilon")
        )
        recs = [
            _reground_rec((3, 4)),
            _pairwise_merge_rec((2, 3)),
            _split_rec(5),
        ]
        stamped = stamp_target_signatures(plan, recs)
        for original, out in zip(recs, stamped):
            ids = directive_target_ids(original)
            assert out.target_signature == compute_target_signature(plan, ids)

    def test_stamp_leaves_non_directive_recs_unchanged(self):
        from plan_tool.review_walk import stamp_target_signatures

        plan = _plan_with_steps((1, "Alpha"))
        rec = _rec(source="deps")
        stamped = stamp_target_signatures(plan, [rec])
        assert stamped[0].target_signature is None
        assert stamped[0] is rec  # same object, untouched

    def test_stamp_returns_new_recs_and_does_not_mutate_input(self):
        from plan_tool.review_walk import stamp_target_signatures

        plan = _plan_with_steps((3, "Gamma"), (4, "Delta"))
        rec = _reground_rec((3, 4))
        stamped = stamp_target_signatures(plan, [rec])
        assert stamped[0] is not rec
        assert stamped[0].target_signature is not None
        assert rec.target_signature is None  # frozen input untouched

    def test_stamped_signature_recomputes_equal_when_titles_unchanged(self):
        from plan_tool.review_walk import (
            directive_target_ids,
            stamp_target_signatures,
        )

        plan = _plan_with_steps((3, "Gamma"), (4, "Delta"))
        rec = _reground_rec((3, 4))
        stamped = stamp_target_signatures(plan, [rec])[0]
        recomputed = compute_target_signature(plan, directive_target_ids(rec))
        assert stamped.target_signature == recomputed

    def test_stamped_signature_recomputes_unequal_after_target_title_change(
        self,
    ):
        from plan_tool.review_walk import (
            directive_target_ids,
            stamp_target_signatures,
        )

        before = _plan_with_steps((3, "Gamma"), (4, "Delta"))
        rec = _reground_rec((3, 4))
        stamped = stamp_target_signatures(before, [rec])[0]
        after = _plan_with_steps((3, "Gamma renamed"), (4, "Delta"))
        recomputed = compute_target_signature(after, directive_target_ids(rec))
        assert stamped.target_signature != recomputed

    def test_stamp_survives_save_and_load(self, tmp_path):
        from plan_tool.review_walk import stamp_target_signatures

        plan = _plan_with_steps((3, "Gamma"), (4, "Delta"))
        stamped = stamp_target_signatures(plan, [_reground_rec((3, 4))])
        saved = _make_saved_review(tmp_path, *stamped)
        assert saved.recommendations[0].target_signature == (
            stamped[0].target_signature
        )
