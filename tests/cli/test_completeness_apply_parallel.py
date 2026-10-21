"""Unit tests for the parallel completeness-apply worker (#74/B2, Step 2.1)."""

from __future__ import annotations

import contextlib
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from plan_tool.cli.completeness_apply_parallel import (
    FileChange,
    FindingApplyResult,
    ReplayOutcome,
    _capture_changes,
    apply_finding_in_tree,
    replay_results,
    replay_sort_key,
)
from plan_tool.review import Recommendation


def _rec(rid="pc", source="plan-correctness", body="b", step_id=1,
         severity="high", anchor=None):
    return Recommendation(
        id=rid, source=source, severity=severity, step_id=step_id,
        title="t", body=body, anchor=anchor,
    )


def _plan_text(title: str) -> str:
    return (
        "---\n"
        f"title: {title}\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Only step\n"
        "---\n"
        "# Body\n"
    )


def _named_backend(name: str):
    from dataclasses import replace

    from plan_tool.backend import CLAUDE_BACKEND

    return replace(CLAUDE_BACKEND, name=name)


@contextlib.contextmanager
def _active_backend(name: str):
    from plan_tool.backend import get_active_backend, set_active_backend

    prior = get_active_backend()
    set_active_backend(_named_backend(name))
    try:
        yield
    finally:
        set_active_backend(prior)


class TestCaptureChanges:
    def test_modified_file_is_captured_repo_relative(self, tmp_path: Path):
        f = tmp_path / "plans" / "1-demo.md"
        f.parent.mkdir(parents=True)
        f.write_text("after", encoding="utf-8")
        changes = _capture_changes({f: "before"}, tmp_path)
        assert changes == (
            FileChange(path="plans/1-demo.md", pre="before", post="after"),
        )

    def test_untouched_file_is_dropped(self, tmp_path: Path):
        f = tmp_path / "a.md"
        f.write_text("same", encoding="utf-8")
        assert _capture_changes({f: "same"}, tmp_path) == ()

    def test_created_file_has_none_pre(self, tmp_path: Path):
        f = tmp_path / "new.md"
        f.write_text("fresh", encoding="utf-8")
        changes = _capture_changes({f: None}, tmp_path)
        assert changes == (FileChange(path="new.md", pre=None, post="fresh"),)

    def test_deleted_file_has_none_post(self, tmp_path: Path):
        f = tmp_path / "gone.md"  # never written
        changes = _capture_changes({f: "had content"}, tmp_path)
        assert changes == (
            FileChange(path="gone.md", pre="had content", post=None),
        )


class TestApplyFindingInTree:
    def test_captures_changes_from_apply(self, tmp_path: Path, monkeypatch):
        import plan_tool.launcher as launcher_mod

        plan = tmp_path / "plans" / "1-demo.md"
        plan.parent.mkdir(parents=True)
        plan.write_text("edited body", encoding="utf-8")

        def fake_apply(plan_path, **kwargs):
            # Simulate Claude having edited the plan in place already.
            return SimpleNamespace(
                verdict="APPLIED", summary="did it", exit_code=0,
                pre_snapshot={plan: "original body"},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)
        res = apply_finding_in_tree(
            _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert res.ok
        assert res.verdict == "APPLIED"
        assert res.summary == "did it"
        assert res.changes == (
            FileChange(path="plans/1-demo.md", pre="original body",
                       post="edited body"),
        )

    def test_untouched_apply_yields_no_changes(self, tmp_path: Path, monkeypatch):
        import plan_tool.launcher as launcher_mod

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")

        def fake_apply(plan_path, **kwargs):
            return SimpleNamespace(
                verdict="NOT-APPLICABLE", summary="", exit_code=0,
                pre_snapshot={plan: "body"},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)
        res = apply_finding_in_tree(
            _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert res.ok
        assert res.changes == ()

    def test_parse_error_is_handled_not_raised(self, tmp_path: Path, monkeypatch):
        import plan_tool.launcher as launcher_mod
        from plan_tool.parser import ParseError

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")

        def boom(plan_path, **kwargs):
            raise ParseError("bad yaml")

        monkeypatch.setattr(launcher_mod, "apply_finding", boom)
        res = apply_finding_in_tree(
            _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert not res.ok
        assert res.exit_code == 1
        assert "bad yaml" in res.error
        assert res.changes == ()

    def test_detail_format_error_is_reraised_not_handled(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Unlike ``ParseError``/``ValidationError`` above (folded into a
        handled ``FindingApplyResult``), a ``DetailFormatError`` carries no
        ``apply_finding_restore_succeeded`` attribute and must escape this
        worker uncaught."""
        import plan_tool.launcher as launcher_mod
        from plan_tool.detail_artifacts import DetailFormatError

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")

        def boom(plan_path, **kwargs):
            raise DetailFormatError("detail declares an unsupported version")

        monkeypatch.setattr(launcher_mod, "apply_finding", boom)
        with pytest.raises(DetailFormatError):
            apply_finding_in_tree(
                _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
            )

    def test_unsupported_plan_format_is_reraised_not_handled(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import plan_tool.launcher as launcher_mod
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")
        monkeypatch.setattr(
            launcher_mod,
            "apply_finding",
            lambda *_args, **_kwargs: (_ for _ in ()).throw(
                UnsupportedPlanFormatVersionError("unsupported format_version")
            ),
        )

        with pytest.raises(UnsupportedPlanFormatVersionError):
            apply_finding_in_tree(
                _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
            )

    def test_raised_invocation_transports_failure_metadata_to_replay(
        self, tmp_path: Path
    ):
        plan = tmp_path / "1-demo.md"
        original = _plan_text("Orig")
        plan.write_text(original, encoding="utf-8")

        def raising_invoker(prompt):
            plan.write_text("partial edit", encoding="utf-8")
            raise RuntimeError("backend raised")

        res = apply_finding_in_tree(
            _rec(step_id=1), repo_root=tmp_path, plan_path=plan,
            plan_name="demo", invoker=raising_invoker,
            plan_fingerprint="evaluated",
        )
        assert not res.ok
        assert res.recordable_verdict == "INVOCATION-FAILED"
        assert res.resolved_step_id == 1
        assert res.restoration_succeeded is True
        assert res.changes == ()
        assert plan.read_text(encoding="utf-8") == original

    def test_deferred_followup_exception_restores_pre_primary_snapshot(
        self, tmp_path: Path
    ):
        plan = tmp_path / "1-demo.md"
        original = (
            "---\n"
            "title: Auto-Fix Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n\n"
            "## Overview\n"
            "Real description.\n"
        )
        plan.write_text(original, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        calls = 0

        def raising_followup(prompt):
            nonlocal calls
            calls += 1
            if calls == 1:
                plan.write_text(
                    original.replace("Real description.", "_(TODO)_"),
                    encoding="utf-8",
                )
                return 0, "## Summary\n- changed body\n\n## Verdict\nAPPLIED\n"
            plan.write_text("follow-up partial garbage\n", encoding="utf-8")
            raise RuntimeError("follow-up failed")

        res = apply_finding_in_tree(
            _rec(step_id=1), repo_root=tmp_path, plan_path=plan,
            plan_name="demo", invoker=raising_followup,
            plan_fingerprint="canonical-rerun-state",
        )

        assert not res.ok
        assert res.recordable_verdict == "INVOCATION-FAILED"
        assert res.restoration_succeeded is True
        assert res.changes == ()
        assert plan.read_text(encoding="utf-8") == original

    def test_worker_passes_finding_body_and_step_id(self, tmp_path: Path, monkeypatch):
        import plan_tool.launcher as launcher_mod

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")
        captured: dict = {}

        def fake_apply(plan_path, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                verdict="APPLIED", summary="", exit_code=0,
                pre_snapshot={plan: "body"},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)
        apply_finding_in_tree(
            _rec(body="fix this", step_id=3),
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert captured["finding_body"].endswith("fix this")
        assert "confidence: limited" in captured["finding_body"]
        assert captured["step_id"] == 3
        assert captured["plan_name"] == "demo"
        assert captured["record_verdict"] is False
        assert callable(captured["verdict_observer"])

    def test_default_shell_invoker_rate_limit_switch_restores_backend(
        self, tmp_path: Path, monkeypatch,
    ):
        import plan_tool.launcher as launcher_mod
        from plan_tool.backend import get_active_backend, scoped_active_backend

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")
        seen = []

        def fake_shell_invoker(prompt):
            assert prompt == "prompt"
            with scoped_active_backend(_named_backend("fallback")):
                seen.append(("during", get_active_backend().name))
            seen.append(("after_invoker", get_active_backend().name))
            return 0, "ok"

        def fake_apply(plan_path, **kwargs):
            assert kwargs["invoker"] is fake_shell_invoker
            kwargs["invoker"]("prompt")
            seen.append(("after_apply", get_active_backend().name))
            return SimpleNamespace(
                verdict="APPLIED", summary="", exit_code=0,
                pre_snapshot={plan: "body"},
            )

        monkeypatch.setattr(launcher_mod, "shell_invoker", fake_shell_invoker)
        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)

        with _active_backend("primary"):
            res = apply_finding_in_tree(
                _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
            )
            seen.append(("after_worker", get_active_backend().name))

        assert res.ok
        assert seen == [
            ("during", "fallback"),
            ("after_invoker", "primary"),
            ("after_apply", "primary"),
            ("after_worker", "primary"),
        ]

    def test_injected_batch_invoker_rate_limit_switch_restores_backend(
        self, tmp_path: Path, monkeypatch,
    ):
        import plan_tool.launcher as launcher_mod
        from plan_tool.backend import get_active_backend, scoped_active_backend

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")
        seen = []

        def batch_invoker(prompt):
            assert prompt == "prompt"
            with scoped_active_backend(_named_backend("fallback")):
                seen.append(("during", get_active_backend().name))
            seen.append(("after_invoker", get_active_backend().name))
            return 0, "ok"

        def fake_apply(plan_path, **kwargs):
            assert kwargs["invoker"] is batch_invoker
            kwargs["invoker"]("prompt")
            seen.append(("after_apply", get_active_backend().name))
            return SimpleNamespace(
                verdict="APPLIED", summary="", exit_code=0,
                pre_snapshot={plan: "body"},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)

        with _active_backend("primary"):
            res = apply_finding_in_tree(
                _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
                invoker=batch_invoker,
            )
            seen.append(("after_worker", get_active_backend().name))

        assert res.ok
        assert seen == [
            ("during", "fallback"),
            ("after_invoker", "primary"),
            ("after_apply", "primary"),
            ("after_worker", "primary"),
        ]


class TestReplaySortKey:
    def test_correctness_before_completeness(self):
        c = _rec("a", source="plan-correctness", severity="info")
        p = _rec("b", source="plan-completeness", severity="critical")
        assert replay_sort_key(c) < replay_sort_key(p)

    def test_most_severe_first_within_source(self):
        hi = _rec("a", source="plan-correctness", severity="critical")
        lo = _rec("b", source="plan-correctness", severity="medium")
        assert replay_sort_key(hi) < replay_sort_key(lo)

    def test_id_is_final_tiebreak(self):
        x = _rec("aaa", source="plan-correctness", severity="high")
        y = _rec("bbb", source="plan-correctness", severity="high")
        assert replay_sort_key(x) < replay_sort_key(y)


def _result(
    rec, *, changes=(), verdict="APPLIED", error=None,
    recordable_verdict=None, resolved_step_id=None, plan_fingerprint="",
    elapsed=0.0,
):
    return FindingApplyResult(
        rec=rec, verdict=verdict, summary="", exit_code=0,
        changes=tuple(changes), error=error,
        recordable_verdict=recordable_verdict,
        resolved_step_id=resolved_step_id,
        plan_fingerprint=plan_fingerprint,
        elapsed=elapsed,
    )


class _FakeRunLogger:
    """Records ``phase_start``/``phase_end`` calls; ``phase_end`` takes
    ``duration_ms``/``outcome`` positionally, matching the real signature."""

    def __init__(self) -> None:
        self.events: list[tuple] = []

    def phase_start(self, phase, **extra):
        self.events.append(("phase_start", phase, extra))

    def phase_end(self, phase, duration_ms, outcome, **extra):
        self.events.append(("phase_end", phase, duration_ms, outcome, extra))


class TestReplayResults:
    def test_replay_records_clean_result_once_in_canonical_repo(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        change = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("New")
        )
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append((a, k))
        )
        rec = _rec("a")
        replay_results(
            [_result(
                rec, changes=[change], recordable_verdict="APPLIED",
                resolved_step_id=9, plan_fingerprint="evaluated-plan",
            )],
            repo_root=tmp_path, plan_path=plan, plan_name="canonical-plan",
        )
        assert len(calls) == 1
        assert calls[0][0][0] == tmp_path
        assert calls[0][1] == {
            "plan_slug": "canonical-plan", "verdict": "APPLIED",
            "step_id": "9", "anchor": "",
            "plan_fingerprint": "evaluated-plan",
        }

    @pytest.mark.parametrize(
        ("verdict", "error"),
        [
            ("NOT-APPLICABLE", None),
            ("INVOCATION-FAILED", "apply exited 1"),
            ("INVOCATION-FAILED", "worker crashed: backend raised"),
        ],
    )
    def test_replay_records_selected_non_applied_outcomes_with_anchor(
        self, tmp_path, monkeypatch, verdict, error
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        replay_results(
            [_result(
                _rec("a", anchor="step:1:gap"), verdict=verdict,
                error=error, recordable_verdict=verdict,
                resolved_step_id=4, plan_fingerprint="evaluated-state",
            )],
            repo_root=tmp_path, plan_path=plan, plan_name="canonical-plan",
        )

        assert calls == [{
            "plan_slug": "canonical-plan", "verdict": verdict,
            "step_id": "4", "anchor": "step:1:gap",
            "plan_fingerprint": "evaluated-state",
        }]

    def test_replay_does_not_record_pre_invocation_worker_failure(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        replay_results(
            [_result(_rec("a"), error="setup failed")],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert calls == []

    def test_applied_empty_diff_records_no_acted_on_verdict(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        replay_results(
            [_result(_rec("a"), recordable_verdict="APPLIED", resolved_step_id=1)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert calls == []

    def test_parse_gate_restore_records_no_acted_on_verdict(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        bad = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post="broken"
        )
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        replay_results(
            [_result(
                _rec("a"), changes=[bad], recordable_verdict="APPLIED",
                resolved_step_id=1,
            )],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert calls == []

    def test_unsupported_plan_format_reverts_then_aborts_the_replay(
        self, tmp_path
    ) -> None:
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        plan = tmp_path / "1-demo.md"
        original = _plan_text("Orig")
        plan.write_text(original, encoding="utf-8")
        unsupported = original.replace(
            "status: planning\n", "format_version: 999\nstatus: planning\n"
        )
        change = FileChange(path="1-demo.md", pre=original, post=unsupported)

        with pytest.raises(UnsupportedPlanFormatVersionError):
            replay_results(
                [_result(_rec("a"), changes=[change])],
                repo_root=tmp_path,
                plan_path=plan,
                plan_name="demo",
            )

        assert plan.read_text(encoding="utf-8") == original

    def test_clean_results_write_posts_to_canonical(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        change = FileChange(path="1-demo.md", pre=_plan_text("Orig"),
                            post=_plan_text("New"))
        out = replay_results(
            [_result(_rec("a"), changes=[change])],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda rec: pytest.fail("should not re-run"),
        )
        assert plan.read_text(encoding="utf-8") == _plan_text("New")
        assert [r.id for r, _ in out.applied] == ["a"]
        assert out.conflicts == 0

    def test_ordering_is_deterministic_regardless_of_completion(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        # Two findings that touch no files (empty changes) so both just record.
        comp = _result(_rec("z", source="plan-completeness", severity="medium"))
        corr = _result(_rec("a", source="plan-correctness", severity="high"))
        # Feed in completion order [completeness, correctness]; expect
        # correctness-first in the outcome.
        out = replay_results(
            [comp, corr], repo_root=tmp_path, plan_path=plan,
            plan_name="demo",
        )
        assert [r.id for r, _ in out.applied] == ["a", "z"]

    def test_conflict_triggers_serial_rerun(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        # Canonical already differs from the worker's captured pre.
        plan.write_text(_plan_text("AlreadyChanged"), encoding="utf-8")
        stale = FileChange(path="1-demo.md", pre=_plan_text("Orig"),
                           post=_plan_text("StaleWorkerPost"))
        rerun_calls = []

        def fake_rerun(rec):
            rerun_calls.append(rec.id)
            # The serial re-run mutates canonical directly (like apply_finding).
            plan.write_text(_plan_text("FreshFromRerun"), encoding="utf-8")
            fresh_change = FileChange(
                path="1-demo.md", pre=_plan_text("AlreadyChanged"),
                post=_plan_text("FreshFromRerun"),
            )
            return _result(rec, changes=[fresh_change])

        out = replay_results(
            [_result(_rec("a"), changes=[stale])],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=fake_rerun,
        )
        assert rerun_calls == ["a"]
        assert out.conflicts == 1
        assert plan.read_text(encoding="utf-8") == _plan_text("FreshFromRerun")
        assert [r.id for r, _ in out.applied] == ["a"]

    def test_conflict_records_only_fresh_serial_rerun(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Changed"), encoding="utf-8")
        stale = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("Stale")
        )
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        rec = _rec("a")
        replay_results(
            [_result(
                rec, changes=[stale], recordable_verdict="APPLIED",
                resolved_step_id=1, plan_fingerprint="stale-fp",
            )],
            repo_root=tmp_path,
            plan_path=plan,
            plan_name="demo",
            rerun_fn=lambda selected: _result(
                selected, verdict="NOT-APPLICABLE",
                recordable_verdict="NOT-APPLICABLE", resolved_step_id=7,
                plan_fingerprint="fresh-fp",
            ),
        )
        assert [(call["verdict"], call["step_id"], call["plan_fingerprint"])
                for call in calls] == [("NOT-APPLICABLE", "7", "fresh-fp")]

    def test_conflict_rerun_failure_records_only_fresh_failure(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Changed"), encoding="utf-8")
        stale = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("Stale")
        )
        calls = []
        monkeypatch.setattr(
            mod, "record_apply_verdict", lambda *a, **k: calls.append(k)
        )
        rec = _rec("a", anchor="finding-anchor")
        out = replay_results(
            [_result(
                rec, changes=[stale], recordable_verdict="APPLIED",
                resolved_step_id=1, plan_fingerprint="stale-fp",
            )],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda selected: _result(
                selected, verdict="INVOCATION-FAILED",
                error="worker crashed: backend raised",
                recordable_verdict="INVOCATION-FAILED", resolved_step_id=7,
                plan_fingerprint="fresh-fp",
            ),
        )

        assert out.conflicts == 1
        assert [rec.id for rec, _ in out.failed] == ["a"]
        assert calls == [{
            "plan_slug": "demo", "verdict": "INVOCATION-FAILED",
            "step_id": "7", "anchor": "finding-anchor",
            "plan_fingerprint": "fresh-fp",
        }]

    def test_replay_telemetry_failure_is_best_effort(
        self, tmp_path, monkeypatch
    ):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        change = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("New")
        )
        monkeypatch.setattr(
            mod, "record_apply_verdict",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
        )
        out = replay_results(
            [_result(
                _rec("a"), changes=[change], recordable_verdict="APPLIED",
                resolved_step_id=1,
            )],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert plan.read_text(encoding="utf-8") == _plan_text("New")
        assert [rec.id for rec, _ in out.applied] == ["a"]

    def test_parse_failure_reverts_and_records_failed(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        bad = FileChange(path="1-demo.md", pre=_plan_text("Orig"),
                         post="not valid frontmatter at all")
        out = replay_results(
            [_result(_rec("a"), changes=[bad])],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda rec: pytest.fail("no re-run"),
        )
        # Reverted to the pre content — no broken plan left behind.
        assert plan.read_text(encoding="utf-8") == _plan_text("Orig")
        assert out.applied == []
        assert len(out.failed) == 1
        assert out.failed[0][0].id == "a"
        assert "failed to parse" in out.failed[0][1]

    def test_failed_worker_result_is_recorded_not_applied(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        out = replay_results(
            [_result(_rec("a"), error="boom")],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert out.applied == []
        assert out.failed[0][0].id == "a"
        assert "boom" in out.failed[0][1]

    def test_empty_changes_records_verdict_without_writing(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        out = replay_results(
            [_result(_rec("a"), verdict="NOT-APPLICABLE")],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert plan.read_text(encoding="utf-8") == _plan_text("Orig")
        assert out.applied == [(out.applied[0][0], "NOT-APPLICABLE")]


class TestReplayResultsRunLog:
    """#74/B2 follow-up: the parallel apply path's per-finding run-log
    entries must land in ``replay_sort_key`` order — not thread-completion
    order — so the log reads the same regardless of ``--jobs``."""

    def test_phases_emitted_in_sort_order_not_input_order(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        # Input order is the reverse of replay_sort_key order (id is the
        # tiebreak within one source/severity) — a real concurrent run would
        # hand these to replay_results in whatever order threads finished.
        results = [
            _result(_rec("c", source="plan-correctness", severity="high", body="c")),
            _result(_rec("a", source="plan-correctness", severity="high", body="a")),
            _result(_rec("b", source="plan-correctness", severity="high", body="b")),
        ]
        logger = _FakeRunLogger()
        replay_results(
            results, repo_root=tmp_path, plan_path=plan, plan_name="demo",
            run_logger=logger,
        )
        starts = [e for e in logger.events if e[0] == "phase_start"]
        ends = [e for e in logger.events if e[0] == "phase_end"]
        assert [e[2]["finding_label"] for e in starts] == ["a", "b", "c"]
        assert [e[4]["verdict"] for e in ends] == ["APPLIED"] * 3
        # Each finding's start/end pair is adjacent (try/finally per finding).
        assert [e[0] for e in logger.events] == [
            "phase_start", "phase_end",
            "phase_start", "phase_end",
            "phase_start", "phase_end",
        ]

    def test_phase_events_carry_step_id_source_and_duration(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        rec = _rec("a", source="plan-completeness", step_id=7, body="finding body")
        logger = _FakeRunLogger()
        replay_results(
            [_result(rec, elapsed=1.5)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            run_logger=logger,
        )
        start = next(e for e in logger.events if e[0] == "phase_start")
        end = next(e for e in logger.events if e[0] == "phase_end")
        assert start[1] == "apply_finding_dispatch"
        assert start[2] == {
            "step_id": 7, "source": "plan-completeness",
            "finding_label": "finding body",
        }
        assert end[1] == "apply_finding_dispatch"
        assert end[2] == 1500  # duration_ms from FindingApplyResult.elapsed
        assert end[3] == "applied"
        assert end[4] == {
            "step_id": 7, "source": "plan-completeness", "verdict": "APPLIED",
        }

    def test_no_run_logger_is_a_no_op(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        # Default (no run_logger) — must not raise, matching every other
        # TestReplayResults case that omits the kwarg.
        out = replay_results(
            [_result(_rec("a"))],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert out.applied[0][0].id == "a"

    def test_conflict_rerun_logs_the_rerun_outcome(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        stale = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("Stale")
        )
        rec = _rec("a")
        # Canonical tree has already moved past the worker's captured "pre" —
        # forces the conflict/rerun branch.
        plan.write_text(_plan_text("AlreadyChanged"), encoding="utf-8")
        rerun_result = _result(
            rec, changes=[FileChange(
                path="1-demo.md", pre=_plan_text("AlreadyChanged"),
                post=_plan_text("Rerun"),
            )],
            verdict="APPLIED", elapsed=2.0,
        )
        logger = _FakeRunLogger()
        replay_results(
            [_result(rec, changes=[stale], elapsed=0.1)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda r: rerun_result,
            run_logger=logger,
        )
        end = next(e for e in logger.events if e[0] == "phase_end")
        # Duration/verdict reflect the rerun (the finding's real final
        # state), not the stale worker result that triggered the rerun.
        assert end[2] == 2000
        assert end[4]["verdict"] == "APPLIED"

    def test_worker_failure_still_logs_a_phase_pair(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        logger = _FakeRunLogger()
        replay_results(
            [_result(_rec("a"), error="worker crashed: boom", elapsed=3.0)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            run_logger=logger,
        )
        end = next(e for e in logger.events if e[0] == "phase_end")
        assert [e[0] for e in logger.events] == ["phase_start", "phase_end"]
        assert end[2] == 3000
        assert end[3] == "error"
        assert end[4]["verdict"] == "APPLIED"  # _result()'s default verdict

    def test_not_applicable_still_logs_a_phase_pair(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        logger = _FakeRunLogger()
        replay_results(
            [_result(_rec("a"), verdict="NOT-APPLICABLE", elapsed=0.5)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            run_logger=logger,
        )
        end = next(e for e in logger.events if e[0] == "phase_end")
        assert [e[0] for e in logger.events] == ["phase_start", "phase_end"]
        assert end[2] == 500
        assert end[3] == "not-applicable"
        assert end[4]["verdict"] == "NOT-APPLICABLE"

    def test_conflict_rerun_failure_logs_the_rerun_not_the_stale_result(
        self, tmp_path
    ):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("AlreadyChanged"), encoding="utf-8")
        stale = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"), post=_plan_text("Stale")
        )
        rec = _rec("a")
        rerun_failure = _result(
            rec, verdict="UNKNOWN", error="re-run failed: boom", elapsed=4.0,
        )
        logger = _FakeRunLogger()
        replay_results(
            [_result(rec, changes=[stale], elapsed=0.1)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda r: rerun_failure,
            run_logger=logger,
        )
        end = next(e for e in logger.events if e[0] == "phase_end")
        # Duration/verdict reflect the failed rerun (the finding's real
        # final state) — not the stale worker result whose conflict
        # triggered the rerun in the first place.
        assert [e[0] for e in logger.events] == ["phase_start", "phase_end"]
        assert end[2] == 4000
        assert end[3] == "error"
        assert end[4]["verdict"] == "UNKNOWN"  # _result()'s failure default

    def test_parse_gate_failure_still_logs_a_phase_pair(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        bad = FileChange(
            path="1-demo.md", pre=_plan_text("Orig"),
            post="not valid frontmatter at all",
        )
        logger = _FakeRunLogger()
        replay_results(
            [_result(_rec("a"), changes=[bad], elapsed=0.7)],
            repo_root=tmp_path, plan_path=plan, plan_name="demo",
            rerun_fn=lambda rec: pytest.fail("no re-run"),
            run_logger=logger,
        )
        # Reverted to the pre content — no broken plan left behind.
        assert plan.read_text(encoding="utf-8") == _plan_text("Orig")
        end = next(e for e in logger.events if e[0] == "phase_end")
        assert [e[0] for e in logger.events] == ["phase_start", "phase_end"]
        assert end[2] == 700
        assert end[3] == "reverted"
        assert end[4]["verdict"] == "REVERTED"


class TestDispatchParallel:
    def test_returns_one_result_per_rec(self):
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel

        recs = [_rec(f"r{i}") for i in range(5)]
        out = dispatch_parallel(
            recs, lambda rec: _result(rec, verdict="APPLIED"), jobs=3,
        )
        assert {r.rec.id for r in out} == {f"r{i}" for i in range(5)}
        assert all(r.verdict == "APPLIED" for r in out)

    def test_failure_isolation_one_crash_does_not_abort_siblings(self):
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel

        recs = [_rec("ok1"), _rec("boom"), _rec("ok2")]

        def apply_one(rec):
            if rec.id == "boom":
                raise RuntimeError("kaboom")
            return _result(rec, verdict="APPLIED")

        out = dispatch_parallel(recs, apply_one, jobs=3)
        by_id = {r.rec.id: r for r in out}
        assert by_id["ok1"].ok and by_id["ok2"].ok
        assert not by_id["boom"].ok
        assert "kaboom" in by_id["boom"].error

    def test_parallel_apply_reraises_detail_format_error_without_recording_a_worker_result(
        self,
    ):
        """Unlike the ordinary crash above (isolated into a failed
        per-finding result), a ``DetailFormatError`` is a hard, named
        refusal and must abort the whole batch — never recorded as a
        failed :class:`FindingApplyResult` and never replaying a sibling
        candidate into the canonical tree."""
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel
        from plan_tool.detail_artifacts import DetailFormatError

        recs = [_rec("ok1"), _rec("boom"), _rec("ok2")]

        def apply_one(rec):
            if rec.id == "boom":
                raise DetailFormatError("detail declares an unsupported version")
            return _result(rec, verdict="APPLIED")

        with pytest.raises(DetailFormatError):
            dispatch_parallel(recs, apply_one, jobs=3)

    def test_parallel_apply_reraises_unsupported_plan_format(self):
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        recs = [_rec("ok"), _rec("boom")]

        def apply_one(rec):
            if rec.id == "boom":
                raise UnsupportedPlanFormatVersionError("unsupported format_version")
            return _result(rec, verdict="APPLIED")

        with pytest.raises(UnsupportedPlanFormatVersionError):
            dispatch_parallel(recs, apply_one, jobs=2)


    def test_parallel_apply_logs_a_hard_refusal(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import plan_tool.cli.completeness_apply_parallel as parallel
        import plan_tool.cli.completeness_phases as phases
        import plan_tool.run_log as run_log
        from plan_tool.detail_artifacts import DetailFormatError

        events: list[dict] = []

        class Logger:
            def telemetry_run_id_scope(self):
                return contextlib.nullcontext()

            def run_end(self, **kwargs) -> None:
                events.append(kwargs)

        monkeypatch.setattr(
            run_log.RunLogWriter, "start", lambda **_kwargs: Logger()
        )
        monkeypatch.setattr(
            parallel,
            "run_parallel_apply",
            lambda _recs, **_kwargs: (_ for _ in ()).throw(
                DetailFormatError("detail declares an unsupported version")
            ),
        )
        saved = SimpleNamespace(recommendations=[_rec()], annotations={})
        args = SimpleNamespace(rewalk=False, include_info=False, name="demo")
        ctx = SimpleNamespace(repo_root=tmp_path)
        plan_path = tmp_path / "1-demo.md"
        plan_path.write_text(_plan_text("Demo"), encoding="utf-8")

        with pytest.raises(DetailFormatError):
            phases._apply_walk_recs_parallel(
                saved.recommendations,
                saved=saved,
                saved_path=tmp_path / "saved.json",
                plan_path=plan_path,
                ctx=ctx,
                args=args,
                jobs=2,
            )

        assert events == [{
            "outcome": "error",
            "rc": 1,
            "error": "detail declares an unsupported version",
        }]

    def test_empty_recs_returns_empty(self):
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel

        assert dispatch_parallel([], lambda rec: _result(rec), jobs=4) == []

    def test_jobs_capped_at_rec_count(self, monkeypatch):
        # Confirm we never request more workers than there are recs.
        import plan_tool.cli.completeness_apply_parallel as mod

        seen = {}
        real = mod.ThreadPoolExecutor

        class SpyPool(real):
            def __init__(self, *a, **kw):
                seen["max_workers"] = kw.get("max_workers", a[0] if a else None)
                super().__init__(*a, **kw)

        monkeypatch.setattr(mod, "ThreadPoolExecutor", SpyPool)
        mod.dispatch_parallel(
            [_rec("a"), _rec("b")], lambda rec: _result(rec), jobs=10,
        )
        assert seen["max_workers"] == 2

    def test_switches_do_not_leak_between_overlapping_workers(self):
        from plan_tool.backend import get_active_backend, scoped_active_backend
        from plan_tool.cli.completeness_apply_parallel import dispatch_parallel

        switch_entered = threading.Event()
        sibling_seen = threading.Event()
        captures = []
        lock = threading.Lock()

        def capture(label):
            with lock:
                captures.append((label, get_active_backend().name))

        def apply_one(rec):
            if rec.id == "switch":
                with scoped_active_backend(_named_backend("fallback")):
                    capture("switch-during")
                    switch_entered.set()
                    assert sibling_seen.wait(5)
                capture("switch-after")
                return _result(rec, verdict="APPLIED")

            assert switch_entered.wait(5)
            capture("sibling-during-switch")
            sibling_seen.set()
            capture("sibling-after")
            return _result(rec, verdict="APPLIED")

        with _active_backend("primary"):
            out = dispatch_parallel(
                [_rec("switch"), _rec("sibling")], apply_one, jobs=2,
            )
            final_backend = get_active_backend().name

        assert {r.rec.id for r in out} == {"switch", "sibling"}
        assert dict(captures) == {
            "switch-during": "fallback",
            "sibling-during-switch": "primary",
            "sibling-after": "primary",
            "switch-after": "primary",
        }
        assert final_backend == "primary"


class TestRunParallelApply:
    def test_parallel_apply_presents_fresh_arm_advice_once_before_dispatch(
        self, tmp_path, monkeypatch
    ):
        import contextlib as _cl

        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        events: list[str] = []

        class FakePool:
            def __init__(self, count):
                self.count = count

            def __enter__(self):
                events.append("provision")
                assert events == ["advice", "provision"]
                return self

            def __exit__(self, *args):
                return False

            @_cl.contextmanager
            def acquire(self):
                yield mod.IsolatedTree(repo_root=tmp_path, plan_path=plan)

        def fake_worker(*args, **kwargs):
            events.append("worker")
            return _result(args[0], verdict="NOT-APPLICABLE")

        monkeypatch.setattr(mod, "apply_finding_in_tree", fake_worker)
        mod.run_parallel_apply(
            [_rec("a")],
            repo_root=tmp_path,
            plan_path=plan,
            plan_name="demo",
            jobs=2,
            pool_factory=lambda count: FakePool(count),
            pre_apply_presentation=lambda: events.append("advice"),
        )
        assert events == ["advice", "provision", "worker"]

    def test_merges_worker_changes_onto_canonical(self, tmp_path, monkeypatch):
        import contextlib as _cl

        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")

        class FakePool:
            def __init__(self, count):
                self.count = count

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            @_cl.contextmanager
            def acquire(self):
                yield mod.IsolatedTree(repo_root=tmp_path, plan_path=plan)

        def fake_worker(
            rec, *, repo_root, plan_path, plan_name, invoker=None,
            run_logger=None, plan_fingerprint="",
        ):
            return mod.FindingApplyResult(
                rec=rec, verdict="APPLIED", summary="", exit_code=0,
                changes=(mod.FileChange(
                    path="1-demo.md", pre=_plan_text("Orig"),
                    post=_plan_text("New"),
                ),),
            )

        monkeypatch.setattr(mod, "apply_finding_in_tree", fake_worker)
        out = mod.run_parallel_apply(
            [_rec("a")], repo_root=tmp_path, plan_path=plan,
            plan_name="demo", jobs=2, pool_factory=lambda c: FakePool(c),
        )
        assert [r.id for r, _ in out.applied] == ["a"]
        assert plan.read_text(encoding="utf-8") == _plan_text("New")

    def test_empty_recs_short_circuits(self, tmp_path):
        import plan_tool.cli.completeness_apply_parallel as mod

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")

        def boom(count):
            raise AssertionError("pool should not be provisioned")

        out = mod.run_parallel_apply(
            [], repo_root=tmp_path, plan_path=plan, plan_name="demo",
            jobs=4, pool_factory=boom,
        )
        assert out.applied == [] and out.failed == []

    def test_restores_backend_after_worker_switches(self, tmp_path, monkeypatch):
        import contextlib as _cl

        import plan_tool.cli.completeness_apply_parallel as mod
        from plan_tool.backend import get_active_backend, scoped_active_backend

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        captures = []

        class FakePool:
            def __init__(self, count):
                self.count = count

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            @_cl.contextmanager
            def acquire(self):
                yield mod.IsolatedTree(repo_root=tmp_path, plan_path=plan)

        def fake_worker(
            rec, *, repo_root, plan_path, plan_name, invoker=None,
            run_logger=None, plan_fingerprint="",
        ):
            with scoped_active_backend(_named_backend(f"fallback-{rec.id}")):
                captures.append((f"{rec.id}-during", get_active_backend().name))
            captures.append((f"{rec.id}-after", get_active_backend().name))
            return _result(rec, verdict="APPLIED")

        def persist(rec, status, note):
            captures.append((f"{rec.id}-persist", get_active_backend().name))

        monkeypatch.setattr(mod, "apply_finding_in_tree", fake_worker)
        with _active_backend("primary"):
            out = mod.run_parallel_apply(
                [_rec("a"), _rec("b")], repo_root=tmp_path, plan_path=plan,
                plan_name="demo", jobs=2, pool_factory=lambda c: FakePool(c),
                persist=persist,
            )
            final_backend = get_active_backend().name

        assert {r.id for r, _ in out.applied} == {"a", "b"}
        assert dict(captures) == {
            "a-during": "fallback-a",
            "a-after": "primary",
            "b-during": "fallback-b",
            "b-after": "primary",
            "a-persist": "primary",
            "b-persist": "primary",
        }
        assert final_backend == "primary"

    def test_conflict_rerun_restores_backend_after_serial_tail(
        self, tmp_path, monkeypatch,
    ):
        import contextlib as _cl

        import plan_tool.cli.completeness_apply_parallel as mod
        from plan_tool.backend import get_active_backend, scoped_active_backend

        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        isolated_root = tmp_path / "isolated"
        isolated_plan = isolated_root / "1-demo.md"
        isolated_plan.parent.mkdir()
        isolated_plan.write_text(_plan_text("Orig"), encoding="utf-8")
        captures = []

        class FakePool:
            def __init__(self, count):
                self.count = count

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            @_cl.contextmanager
            def acquire(self):
                yield mod.IsolatedTree(
                    repo_root=isolated_root, plan_path=isolated_plan,
                )

        def fake_apply_finding_in_tree(
            rec, *, repo_root, plan_path, plan_name, invoker=None,
            run_logger=None, plan_fingerprint="",
        ):
            if repo_root == tmp_path:
                with scoped_active_backend(_named_backend("fallback-rerun")):
                    captures.append(("rerun-during", get_active_backend().name))
                    plan.write_text(_plan_text("Fresh"), encoding="utf-8")
                captures.append(("rerun-after", get_active_backend().name))
                return _result(
                    rec,
                    changes=[mod.FileChange(
                        path="1-demo.md",
                        pre=_plan_text("First"),
                        post=_plan_text("Fresh"),
                    )],
                )

            captures.append((f"{rec.id}-worker", get_active_backend().name))
            post = "First" if rec.id == "a" else "StaleSecond"
            return _result(
                rec,
                changes=[mod.FileChange(
                    path="1-demo.md",
                    pre=_plan_text("Orig"),
                    post=_plan_text(post),
                )],
            )

        def persist(rec, status, note):
            captures.append((f"{rec.id}-persist", get_active_backend().name))

        monkeypatch.setattr(
            mod, "apply_finding_in_tree", fake_apply_finding_in_tree,
        )
        with _active_backend("primary"):
            out = mod.run_parallel_apply(
                [
                    _rec("a", source="plan-correctness"),
                    _rec("b", source="plan-completeness"),
                ],
                repo_root=tmp_path, plan_path=plan, plan_name="demo", jobs=2,
                pool_factory=lambda c: FakePool(c), persist=persist,
            )
            final_backend = get_active_backend().name

        assert out.conflicts == 1
        assert {r.id for r, _ in out.applied} == {"a", "b"}
        assert captures == [
            ("a-worker", "primary"),
            ("b-worker", "primary"),
            ("a-persist", "primary"),
            ("rerun-during", "fallback-rerun"),
            ("rerun-after", "primary"),
            ("b-persist", "primary"),
        ]
        assert final_backend == "primary"
        assert plan.read_text(encoding="utf-8") == _plan_text("Fresh")


@pytest.mark.integration
class TestWorktreePoolRealGit:
    def _init_repo(self, tmp_path):
        import subprocess

        def git(*a):
            subprocess.run(["git", *a], cwd=tmp_path, check=True,
                           capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@t.t")
        git("config", "user.name", "t")
        (tmp_path / "plans").mkdir()
        plan = tmp_path / "plans" / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "init")
        return plan

    def test_pool_yields_pristine_isolated_trees(self, tmp_path):
        from plan_tool.cli.completeness_apply_parallel import WorktreePool

        plan = self._init_repo(tmp_path)
        with WorktreePool(tmp_path, 2, "plans/1-demo.md", "demo") as pool:
            with pool.acquire() as tree:
                assert tree.repo_root != tmp_path  # a separate worktree
                assert tree.plan_path.read_text(encoding="utf-8") == \
                    _plan_text("Orig")
                # A worker edits its isolated copy...
                tree.plan_path.write_text(_plan_text("Edited"),
                                          encoding="utf-8")
            # ...and the next acquire of that slot is reset to pristine HEAD.
            with pool.acquire() as tree2:
                assert tree2.plan_path.read_text(encoding="utf-8") == \
                    _plan_text("Orig")
        # Canonical tree untouched by any worker edit.
        assert plan.read_text(encoding="utf-8") == _plan_text("Orig")

    def test_pool_cleans_up_worktrees_and_branches(self, tmp_path):
        import subprocess

        from plan_tool.cli.completeness_apply_parallel import WorktreePool

        self._init_repo(tmp_path)
        with WorktreePool(tmp_path, 2, "plans/1-demo.md", "demo"):
            pass
        wt = subprocess.run(["git", "worktree", "list"], cwd=tmp_path,
                            capture_output=True, text=True).stdout
        assert "parallel-apply" not in wt
        br = subprocess.run(["git", "branch"], cwd=tmp_path,
                            capture_output=True, text=True).stdout
        assert "parallel-apply" not in br


class TestAnnotationStatus:
    def test_applied_maps_to_applied(self):
        from plan_tool.cli.completeness_apply_parallel import annotation_status
        assert annotation_status(_result(_rec("a"), verdict="APPLIED")) == \
            ("applied", "APPLIED")

    def test_not_applicable_maps_to_skip(self):
        from plan_tool.cli.completeness_apply_parallel import annotation_status
        assert annotation_status(
            _result(_rec("a"), verdict="NOT-APPLICABLE")
        ) == ("skip", "NOT-APPLICABLE")

    def test_blocked_maps_to_failed_nonterminal(self):
        from plan_tool.cli.completeness_apply_parallel import annotation_status
        for v in ("BLOCKED", "BLOCKED-STRUCTURAL", "UNKNOWN"):
            assert annotation_status(_result(_rec("a"), verdict=v))[0] == \
                "failed", v


class TestWorkerExitCode:
    def test_nonzero_exit_becomes_failed(self, tmp_path, monkeypatch):
        import plan_tool.launcher as launcher_mod

        plan = tmp_path / "1-demo.md"
        plan.write_text("body", encoding="utf-8")

        def fake_apply(plan_path, **kwargs):
            # Backend failed; apply_finding restored the snapshot, exit != 0.
            return SimpleNamespace(
                verdict="UNKNOWN", summary="", exit_code=1,
                pre_snapshot={plan: "body"},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)
        res = apply_finding_in_tree(
            _rec(), repo_root=tmp_path, plan_path=plan, plan_name="demo",
        )
        assert not res.ok
        assert res.exit_code == 1
        assert "exited 1" in res.error


class TestReplayPersistCallback:
    def test_persist_fires_per_finding_incrementally(self, tmp_path):
        plan = tmp_path / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        persisted = []

        results = [
            _result(_rec("a", source="plan-correctness"),
                    verdict="NOT-APPLICABLE"),
            _result(_rec("b"), error="boom"),
        ]
        replay_results(
            results, repo_root=tmp_path, plan_path=plan, plan_name="demo",
            persist=lambda rec, status, note: persisted.append(
                (rec.id, status)
            ),
        )
        assert ("a", "skip") in persisted
        assert ("b", "failed") in persisted


@pytest.mark.integration
class TestWorktreePoolUniqueness:
    def _init_repo(self, tmp_path):
        import subprocess

        def git(*a):
            subprocess.run(["git", *a], cwd=tmp_path, check=True,
                           capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@t.t")
        git("config", "user.name", "t")
        (tmp_path / "plans").mkdir()
        (tmp_path / "plans" / "1-demo.md").write_text(
            _plan_text("Orig"), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "init")

    def test_stale_branch_does_not_block_provisioning(self, tmp_path):
        import subprocess

        from plan_tool.cli.completeness_apply_parallel import WorktreePool

        self._init_repo(tmp_path)
        # Simulate a crashed prior run leaving a legacy fixed-name branch.
        subprocess.run(
            ["git", "branch", "plan-tool/parallel-apply/demo-0"],
            cwd=tmp_path, check=True, capture_output=True, text=True,
        )
        # A fresh pool uses a unique token, so it provisions cleanly anyway.
        with WorktreePool(tmp_path, 2, "plans/1-demo.md", "demo") as pool:
            with pool.acquire() as tree:
                assert tree.plan_path.exists()


@pytest.mark.integration
class TestRunParallelApplyRealWorktrees:
    def _init_repo(self, tmp_path):
        import subprocess

        def git(*a):
            subprocess.run(["git", *a], cwd=tmp_path, check=True,
                           capture_output=True, text=True)

        git("init", "-q")
        git("config", "user.email", "t@t.t")
        git("config", "user.name", "t")
        (tmp_path / "plans").mkdir()
        plan = tmp_path / "plans" / "1-demo.md"
        plan.write_text(_plan_text("Orig"), encoding="utf-8")
        git("add", "-A")
        git("commit", "-q", "-m", "init")
        return plan

    def test_end_to_end_isolated_apply_and_replay(self, tmp_path, monkeypatch):
        """Full machinery: real worktrees → concurrent workers → serial replay
        onto the canonical tree, with apply_finding stubbed to edit whatever
        tree it's handed. Two findings both edit the plan, so the second
        conflicts and re-runs serially — the canonical tree ends coherent."""
        import plan_tool.launcher as launcher_mod
        from plan_tool.cli.completeness_apply_parallel import run_parallel_apply

        plan = self._init_repo(tmp_path)

        def fake_apply(plan_path, **kwargs):
            pre = plan_path.read_text(encoding="utf-8")
            body = kwargs["finding_body"].splitlines()[-1]
            plan_path.write_text(_plan_text(f"Edited-{body}"), encoding="utf-8")
            return SimpleNamespace(
                verdict="APPLIED", summary="", exit_code=0,
                pre_snapshot={plan_path: pre},
            )

        monkeypatch.setattr(launcher_mod, "apply_finding", fake_apply)

        recs = [
            _rec("a", source="plan-correctness", body="A"),
            _rec("b", source="plan-completeness", body="B"),
        ]
        persisted = []
        out = run_parallel_apply(
            recs, repo_root=tmp_path, plan_path=plan, plan_name="demo",
            jobs=2, persist=lambda r, s, n: persisted.append((r.id, s)),
        )
        # Both findings landed; the completeness one conflicted (correctness
        # replayed first, dirtying the plan) and re-ran serially.
        assert {r.id for r, _ in out.applied} == {"a", "b"}
        assert out.conflicts == 1
        # Canonical plan is coherent (parseable) and reflects the last apply.
        from plan_tool.parser import parse_plan
        parsed = parse_plan(plan)
        assert parsed.title == "Edited-B"
        assert ("a", "applied") in persisted and ("b", "applied") in persisted
        # No worktrees/branches leaked.
        import subprocess
        wt = subprocess.run(["git", "worktree", "list"], cwd=tmp_path,
                            capture_output=True, text=True).stdout
        assert "parallel-apply" not in wt
