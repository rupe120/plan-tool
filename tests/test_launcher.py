"""Tests for plan_tool.launcher. No real claude subprocess is ever spawned."""

from __future__ import annotations

import threading
from dataclasses import replace
from pathlib import Path
from typing import Optional

import pytest

from datetime import datetime, timezone

from plan_tool import claude_errors, parse_plan
from plan_tool.parser import parse_plan_text
from plan_tool import launcher as _launcher
from plan_tool.launcher import (
    EscalateResult,
    LauncherError,
    _streaming_prompt_bytes,
    _test_directive,
    append_lesson,
    escalate_to_split,
    extract_summary,
    mark_done_and_advance,
    preflight_step_paths,
    resolve_step,
    run_all_done_steps,
    run_step,
)
from plan_tool.prompt_budget import PromptBudget
from plan_tool.progress import ProgressReporter, StepHandle
from plan_tool.schema import ChangeType, PlanStatus, StepScope, StepStatus
from subprocess_doubles import _FakeProc, _make_popen_factory
from test_backend_runner import _StreamRecordingLogger


_PLAN = """---
title: Launcher Test
status: in-progress
priority: medium
steps:
  - id: 1
    title: First
    status: done
  - id: 2
    title: Second
    depends_on: [1]
    status: current
  - id: 3
    title: Third
    depends_on: [2]
---

# Launcher Test
"""

_CURSOR_MONTHLY_PLAN_QUOTA = (
    "ActionRequiredError: You've hit your usage limit for Opus. "
    "Switch to a different model or set a Spend Limit. "
    "Your usage limits will reset when your monthly cycle ends on 8/24/2026."
)


@pytest.fixture()
def plan_path(tmp_path: Path) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(_PLAN, encoding="utf-8")
    return p


class TestResolveStep:
    def test_explicit_id_returns_step(self, plan_path: Path) -> None:
        plan = parse_plan(plan_path)
        step = resolve_step(plan, step_id=3)
        assert step.id == 3

    def test_unknown_id_raises(self, plan_path: Path) -> None:
        plan = parse_plan(plan_path)
        with pytest.raises(LauncherError):
            resolve_step(plan, step_id=99)

    def test_current_returned_when_no_id(self, plan_path: Path) -> None:
        plan = parse_plan(plan_path)
        step = resolve_step(plan, step_id=None)
        assert step.id == 2  # current

    def test_falls_back_to_next_runnable(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: No Current\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    depends_on: [1]\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(p)
        step = resolve_step(plan, step_id=None)
        assert step.id == 1

    def test_raises_when_nothing_runnable(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: All Done\n"
            "status: completed\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(p)
        with pytest.raises(LauncherError):
            resolve_step(plan, step_id=None)


class TestMarkDoneAndAdvance:
    def test_marks_done_and_promotes_next(self, plan_path: Path) -> None:
        plan = parse_plan(plan_path)
        step2 = plan.step_by_id(2)
        advanced = mark_done_and_advance(plan, step2)
        assert advanced == 3
        assert plan.step_by_id(2).status == StepStatus.DONE
        assert plan.step_by_id(3).status == StepStatus.CURRENT

    def test_returns_none_when_nothing_follows(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: One Step\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(p)
        advanced = mark_done_and_advance(plan, plan.step_by_id(1))
        assert advanced is None
        assert plan.step_by_id(1).status == StepStatus.DONE

    def test_flips_status_to_completed_on_last_step(self, plan_path: Path) -> None:
        plan = parse_plan(plan_path)
        # Walk the plan to M/M: 2 done (→3 current), then 3 done (last step).
        mark_done_and_advance(plan, plan.step_by_id(2))
        advanced = mark_done_and_advance(plan, plan.step_by_id(3))
        assert advanced is None
        assert plan.all_steps_done
        assert plan.status == PlanStatus.COMPLETED

    def test_no_flip_when_another_step_left_current(self, plan_path: Path) -> None:
        # Out-of-order: run step 3 while step 2 is still current. Not all done,
        # so the plan must stay un-completed even though nothing was promoted.
        plan = parse_plan(plan_path)
        advanced = mark_done_and_advance(plan, plan.step_by_id(3))
        assert advanced is None
        assert plan.step_by_id(2).status == StepStatus.CURRENT
        assert plan.status != PlanStatus.COMPLETED

    def test_completes_with_deferred_tail(self, tmp_path: Path) -> None:
        # Last current step done and the only remaining step is parked
        # (scope: deferred): next_runnable_step() is None and all_steps_done
        # ignores parked steps, so the plan flips to COMPLETED with the
        # deferred work left parked.
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: Deferred Tail\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    scope: deferred\n"
            "---\n",
            encoding="utf-8",
        )
        plan = parse_plan(p)
        advanced = mark_done_and_advance(plan, plan.step_by_id(1))
        assert advanced is None
        assert plan.step_by_id(2).status == StepStatus.PENDING
        assert plan.step_by_id(2).scope == StepScope.DEFERRED
        assert plan.status == PlanStatus.COMPLETED


class TestExtractSummary:
    def test_happy_path(self) -> None:
        stdout = "some output\n## Summary\nSwitched to ruamel.yaml to preserve comments.\n"
        assert extract_summary(stdout) == "Switched to ruamel.yaml to preserve comments."

    def test_truncates_at_500(self) -> None:
        # The cap is generous so a non-APPLIED verdict's full status note
        # (e.g. a BLOCKED finding's "why / what next") survives into the
        # completeness report; it only bounds a pathological blob.
        long_line = "x" * 600
        stdout = f"## Summary\n{long_line}\n"
        result = extract_summary(stdout)
        assert result == "x" * 500

    def test_missing_returns_none(self) -> None:
        assert extract_summary("no summary section here") is None

    def test_multiline_body_takes_first_line(self) -> None:
        stdout = "## Summary\nfirst line\nsecond line\n"
        assert extract_summary(stdout) == "first line"

    def test_strips_ansi_before_matching(self) -> None:
        # ANSI reset code around the header shouldn't break extraction.
        stdout = "\x1b[0m## Summary\x1b[0m\nclean takeaway\n"
        assert extract_summary(stdout) == "clean takeaway"

    def test_whitespace_only_body_returns_none(self) -> None:
        stdout = "## Summary\n   \n"
        assert extract_summary(stdout) is None

    def test_final_text_kwarg_used_when_supplied(self) -> None:
        # When ``final_text`` carries the post-tool ``result`` envelope,
        # extract_summary should look there and not at the raw stdout.
        stdout = (
            "tool noise that happens to mention ## Summary\nbogus\n"
        )
        final_text = "## Summary\nreal takeaway\n"
        assert extract_summary(stdout, final_text=final_text) == (
            "real takeaway"
        )

    def test_final_text_preferred_over_stdout(self) -> None:
        # If both stdout and final_text contain a Summary block, the
        # final_text one wins — the envelope is the canonical source.
        stdout = "## Summary\nstdout summary\n"
        final_text = "## Summary\nenvelope summary\n"
        assert extract_summary(stdout, final_text=final_text) == (
            "envelope summary"
        )

    def test_final_text_none_falls_back_to_stdout(self) -> None:
        # Existing call sites pass nothing → behavior unchanged.
        stdout = "## Summary\nfallback takeaway\n"
        assert extract_summary(stdout, final_text=None) == (
            "fallback takeaway"
        )

    def test_empty_final_text_falls_back_to_stdout(self) -> None:
        # ``ClaudeRunStats.final_text`` defaults to ``""`` when no
        # ``result`` envelope was parsed (test fakes, pre-stream-json
        # invocations). Passing the empty default must not break
        # extraction — fall back to stdout instead of searching an
        # empty haystack.
        stdout = "## Summary\nfrom stdout\n"
        assert extract_summary(stdout, final_text="") == "from stdout"

    def test_final_text_without_summary_returns_none(self) -> None:
        # When final_text is supplied but lacks a Summary block, the
        # function does not silently consult stdout — the envelope is
        # canonical, and a missing block there means claude didn't
        # produce one.
        stdout = "## Summary\nignored stdout block\n"
        final_text = "no summary in envelope"
        assert extract_summary(stdout, final_text=final_text) is None

    def test_summary_past_4kb_tail_missed_without_full_scan(self) -> None:
        # The default fallback only scans the last 4 KB of stdout. A
        # Summary block buried under a long trailing wall of tool-use
        # chatter (the acceptEdits failure mode) is therefore missed —
        # this is the bug that blanked apply-finding disposition notes.
        chatter = "x" * 5000
        stdout = f"## Summary\nburied takeaway\n{chatter}"
        assert extract_summary(stdout) is None

    def test_full_stdout_scan_recovers_summary_past_tail(self) -> None:
        # full_stdout_scan=True searches the whole buffer (symmetric with
        # parse_apply_verdict), recovering the Summary even when edit-tool
        # output pushed it past the 4 KB tail window.
        chatter = "x" * 5000
        stdout = f"## Summary\nburied takeaway\n{chatter}"
        assert extract_summary(stdout, full_stdout_scan=True) == (
            "buried takeaway"
        )

    def test_final_text_still_preferred_over_full_scan(self) -> None:
        # When both are set, the clean envelope still wins over a
        # full-stdout scan.
        chatter = "x" * 5000
        stdout = f"## Summary\nstdout takeaway\n{chatter}"
        final_text = "## Summary\nenvelope takeaway\n"
        assert extract_summary(
            stdout, final_text=final_text, full_stdout_scan=True
        ) == "envelope takeaway"


class TestRunStep:
    def test_dry_run_does_not_invoke(self, plan_path: Path, tmp_path: Path, capsys) -> None:
        calls = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, "")

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            dry_run=True,
        )
        assert result.exit_code == 0
        assert result.done is False
        assert calls == []  # invoker not called in dry run

        # Plan file unchanged.
        plan = parse_plan(plan_path)
        assert plan.step_by_id(2).status == StepStatus.CURRENT

        # Prompt was printed to stdout.
        captured = capsys.readouterr()
        assert "Launcher Test" in captured.out

    def test_successful_run_advances_plan(self, plan_path: Path, tmp_path: Path) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        result = run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)
        assert result.exit_code == 0
        assert result.done is True
        assert result.advanced_to == 3

        reloaded = parse_plan(plan_path)
        assert reloaded.step_by_id(2).status == StepStatus.DONE
        assert reloaded.step_by_id(3).status == StepStatus.CURRENT

    def test_nonzero_exit_does_not_mutate(self, plan_path: Path, tmp_path: Path) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (1, "backend failure detail")

        result = run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)
        assert result.exit_code == 1
        assert result.done is False
        assert result.advanced_to is None
        assert result.stdout == "backend failure detail"

        reloaded = parse_plan(plan_path)
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT  # unchanged

    def test_explicit_step_id(self, plan_path: Path, tmp_path: Path) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            step_id=3,
            invoker=fake_invoker,
        )
        assert result.step_id == 3
        assert result.done is True
        # Out-of-order run: step 3 is done, but step 2 (which was current) must
        # remain current. Otherwise mark_done_and_advance would produce a
        # two-current state that write_plan's revalidation would reject.
        assert result.advanced_to is None

        reloaded = parse_plan(plan_path)
        assert reloaded.step_by_id(3).status == StepStatus.DONE
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT

    def test_out_of_order_with_pending_successor(self, tmp_path: Path) -> None:
        """Regression: 4-step plan where running step 3 could promote step 4 to
        current while step 2 is still current, producing an invalid state."""
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: Four Step\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    depends_on: [1]\n"
            "    status: current\n"
            "  - id: 3\n"
            "    title: Three\n"
            "    depends_on: [1]\n"
            "  - id: 4\n"
            "    title: Four\n"
            "    depends_on: [3]\n"
            "---\n",
            encoding="utf-8",
        )

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        result = run_step(p, repo_root=tmp_path, step_id=3, invoker=fake_invoker)
        assert result.done is True
        assert result.advanced_to is None  # no promotion while step 2 is current

        reloaded = parse_plan(p)
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT
        assert reloaded.step_by_id(3).status == StepStatus.DONE
        assert reloaded.step_by_id(4).status == StepStatus.PENDING  # NOT promoted


# A plan carrying both fence halves: two intents plus the guardrail sections.
_FENCED_PLAN = """---
title: Fenced Launcher Test
intent: PLAN_INTENT_MARKER — ship the fence to the run lane
status: in-progress
priority: medium
steps:
  - id: 1
    title: Second
    intent: STEP_ONE_INTENT_MARKER — wire the run prompt
    status: current
  - id: 2
    title: Third
    intent: STEP_TWO_INTENT_MARKER — wire the run prompt
    depends_on: [1]
---

# Fenced Launcher Test

## Scope guardrails

GUARDRAIL_MARKER — no gate flips.

## Out of scope

OUT_OF_SCOPE_MARKER — the review and reconcile prompts.
"""


def _write_fenced_plan(tmp_path: Path, yaml: str = _FENCED_PLAN) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(yaml, encoding="utf-8")
    return p


class TestRunStepPromptBudget:
    """Step 6: the pre-send prompt-budget advisory on the run path."""

    def _plan_with_detail(self, tmp_path: Path, *, body: str = "x" * 4000) -> Path:
        (tmp_path / "details").mkdir(exist_ok=True)
        (tmp_path / "details" / "01-only.md").write_text(
            "# Only\n\n" + body + "\n", encoding="utf-8"
        )
        p = tmp_path / "plan.md"
        p.write_text(
            "---\n"
            "title: Budget Test\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only\n"
            "    status: current\n"
            "    detail: details/01-only.md\n"
            "---\n\n# Budget Test\n",
            encoding="utf-8",
        )
        return p

    @staticmethod
    def _spy_warn(monkeypatch, calls: list) -> None:
        real = _launcher.maybe_warn_prompt_budget

        def spy(total_bytes, **kwargs):
            budget = real(total_bytes, **kwargs)
            calls.append({"total_bytes": total_bytes, "kwargs": kwargs, "budget": budget})
            return budget

        monkeypatch.setattr(_launcher, "maybe_warn_prompt_budget", spy)

    def test_run_step_default_prompt_budget_measures_embedded_run_grade_detail(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        body = "Declared execution detail: café"
        path = self._plan_with_detail(tmp_path, body=body)
        warns = []
        self._spy_warn(monkeypatch, warns)
        prompts = []
        run_step(path, repo_root=tmp_path, invoker=lambda p: prompts.append(p) or (0, ""))
        embedded_detail = (tmp_path / "details/01-only.md").read_text()
        assert embedded_detail in prompts[0]
        assert dict(warns[0]["kwargs"]["blocks"])["step detail"] == len(embedded_detail.encode("utf-8"))
        assert warns[0]["total_bytes"] == _streaming_prompt_bytes(prompts[0])

    def test_run_step_warns_before_invoke(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        warns: list = []
        self._spy_warn(monkeypatch, warns)
        invoked: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            invoked.append(prompt)
            return (0, "")

        result = run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)

        assert len(warns) == 1
        assert warns[0]["total_bytes"] == _streaming_prompt_bytes(invoked[0])
        assert warns[0]["kwargs"]["blocks"]  # non-empty breakdown
        assert result.done is True and result.advanced_to == 3

    def test_total_reuses_streaming_prompt_bytes(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        warns: list = []
        self._spy_warn(monkeypatch, warns)
        received: list[str] = []
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: received.append(p) or (0, ""),
        )
        # The total handed to the advisory is the streaming-transport byte
        # count of the exact prompt the invoker received — not a fresh encode.
        assert warns[0]["total_bytes"] == _streaming_prompt_bytes(received[0])

    def test_run_step_records_prompt_budget(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        warns: list = []
        self._spy_warn(monkeypatch, warns)
        records: list[dict] = []
        monkeypatch.setattr(
            _launcher,
            "record_prompt_budget",
            lambda repo_root, **kw: records.append(kw),
        )

        run_step(plan_path, repo_root=tmp_path, invoker=lambda _: (0, ""))

        assert len(records) == 1
        rec = records[0]
        assert rec["phase"] == "run-step"
        assert rec["plan_slug"] == "plan"
        assert rec["total_bytes"] == warns[0]["total_bytes"]
        assert rec["advisory"] == warns[0]["budget"].level

    def test_advisory_does_not_change_result(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        def fake_high(total_bytes, **kwargs):
            return PromptBudget(
                total_bytes=total_bytes,
                estimated_tokens=999_999,
                context_window=200_000,
                headroom_ratio=-0.5,
                level="high",
                window_defaulted=True,
                blocks=(),
            )

        monkeypatch.setattr(_launcher, "maybe_warn_prompt_budget", fake_high)
        invoked: list[str] = []

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: invoked.append(p) or (0, ""),
        )

        assert invoked  # advisory never blocks the invoke
        assert result.exit_code == 0
        assert result.done is True and result.advanced_to == 3

    def test_review_mode_also_warns(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        warns: list = []
        self._spy_warn(monkeypatch, warns)

        run_step(
            plan_path,
            repo_root=tmp_path,
            mode="security",
            invoker=lambda _: (0, ""),
        )
        assert len(warns) == 1  # mode-agnostic: a review mode warns too

    def test_dry_run_prints_breakdown_to_stderr_and_does_not_record(
        self, plan_path: Path, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        warns: list = []
        records: list = []
        monkeypatch.setattr(
            _launcher,
            "maybe_warn_prompt_budget",
            lambda *a, **k: warns.append((a, k)),
        )
        monkeypatch.setattr(
            _launcher,
            "record_prompt_budget",
            lambda *a, **k: records.append((a, k)),
        )

        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _: (0, ""),
            dry_run=True,
        )

        captured = capsys.readouterr()
        assert "Launcher Test" in captured.out  # prompt on stdout
        assert "prompt budget" in captured.err  # breakdown on stderr
        assert "run step" in captured.err
        assert warns == []  # silent-at-ok warn path not taken on dry-run
        assert records == []  # nothing sent → nothing recorded

    def test_blocks_include_step_detail(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        p = self._plan_with_detail(tmp_path)
        warns: list = []
        self._spy_warn(monkeypatch, warns)

        run_step(p, repo_root=tmp_path, invoker=lambda _: (0, ""))

        blocks = dict(warns[0]["kwargs"]["blocks"])
        assert "step detail" in blocks
        assert blocks["step detail"] > 0

    def test_no_run_logger_still_warns(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        warns: list = []
        self._spy_warn(monkeypatch, warns)

        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda _: (0, ""),
            run_logger=None,
        )
        assert len(warns) == 1  # not gated on the run logger

    def test_advisory_failure_does_not_break_run(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        def boom(*a, **k):
            raise RuntimeError("advisory slip")

        # Block sizes now ride the render itself, so there's no separate
        # measurement to fail; the surviving guarantee is that the advisory
        # is best-effort — a failure in it must never sink the run.
        monkeypatch.setattr(_launcher, "maybe_warn_prompt_budget", boom)
        invoked: list[str] = []

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: invoked.append(p) or (0, ""),
        )
        assert invoked
        assert result.done is True and result.advanced_to == 3


class TestRunReconcileCompletedSiblingContext:
    """The launcher only renders and measures selected-step context on opt-in."""

    def test_context_reaches_run_reconcile_prompt_and_budget(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        context = (
            "## Completed sibling ownership context\n\n"
            "### Completed step 3 — Later work\n"
            "- `later.py`\n"
        )
        warns: list = []
        TestRunStepPromptBudget._spy_warn(monkeypatch, warns)
        prompts: list[str] = []

        run_step(
            plan_path,
            repo_root=tmp_path,
            mode="run-reconcile",
            completed_sibling_context=context,
            invoker=lambda prompt: prompts.append(prompt) or (0, ""),
        )

        assert context in prompts[0]
        blocks = dict(warns[0]["kwargs"]["blocks"])
        assert blocks["completed sibling context"] == len(context.encode("utf-8"))

    def test_empty_context_does_not_change_other_mode_prompts(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        prompts: list[str] = []

        run_step(
            plan_path,
            repo_root=tmp_path,
            mode="check",
            invoker=lambda prompt: prompts.append(prompt) or (0, ""),
        )

        assert "Completed sibling ownership context" not in prompts[0]

    def test_context_is_rendered_during_dry_run(
        self, plan_path: Path, tmp_path: Path, capsys
    ) -> None:
        context = "## Completed sibling ownership context\n\n- `later.py`\n"

        run_step(
            plan_path,
            repo_root=tmp_path,
            mode="run-reconcile",
            completed_sibling_context=context,
            dry_run=True,
            invoker=lambda _: (_ for _ in ()).throw(
                AssertionError("dry run must not invoke the backend")
            ),
        )

        assert context in capsys.readouterr().out

    def test_selected_reconcile_high_budget_refuses_before_backend(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """A selected reconciliation must not send a high-budget prompt."""
        snapshot = parse_plan(plan_path)
        monkeypatch.setattr(
            _launcher,
            "estimate_prompt_budget",
            lambda *_args, **_kwargs: PromptBudget(
                total_bytes=1,
                estimated_tokens=1,
                context_window=1,
                headroom_ratio=0.0,
                level="high",
                window_defaulted=False,
            ),
        )

        with pytest.raises(LauncherError, match="prompt budget is high"):
            run_step(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                mode="run-reconcile",
                invoker=lambda _prompt: pytest.fail("backend must not run"),
                selected_reconcile_plan_snapshot=snapshot,
                selected_reconcile_plan_fingerprint=_launcher.compute_plan_fingerprint(
                    plan_path
                ),
                reject_high_selected_reconcile_budget=True,
            )

    @pytest.mark.parametrize("lane", ["claude-with-an-observed-window", "codex-with-a-catalog-window"])
    def test_selected_reconcile_refusal_gate_uses_only_deterministic_window_sources(
        self, plan_path: Path, tmp_path: Path, monkeypatch, lane: str
    ) -> None:
        """The one budget check that can refuse a send must not depend on which calls ran first:
        a window the Claude CLI reported earlier in the process is ignored, while the Codex
        catalog (a file) is used."""
        import dataclasses

        from plan_tool.backend import CLAUDE_BACKEND, CODEX_BACKEND, observe_context_window, scoped_active_backend

        seen: list[object] = []

        def spy(total_bytes, *, context_window=None, blocks=None):
            seen.append(context_window)
            return PromptBudget(
                total_bytes=total_bytes, estimated_tokens=1, context_window=context_window or 200_000,
                headroom_ratio=0.0, level="high", window_defaulted=context_window is None,
            )

        monkeypatch.setattr(_launcher, "estimate_prompt_budget", spy)
        if lane.startswith("claude"):
            observe_context_window("claude", None, 1_000_000)
            selected = CLAUDE_BACKEND
        else:
            home = tmp_path / "codex-home"
            home.mkdir()
            (home / "models_cache.json").write_text(
                '{"models": [{"slug": "gpt-6.1-sol", "context_window": 272000,'
                ' "effective_context_window_percent": 95}]}',
                encoding="utf-8",
            )
            monkeypatch.setenv("CODEX_HOME", str(home))
            selected = dataclasses.replace(CODEX_BACKEND, resolved_model="gpt-6.1-sol")

        with scoped_active_backend(selected), pytest.raises(
            LauncherError, match="prompt budget is high"
        ) as refusal:
            run_step(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                mode="run-reconcile",
                invoker=lambda _prompt: pytest.fail("backend must not run"),
                selected_reconcile_plan_snapshot=parse_plan(plan_path),
                selected_reconcile_plan_fingerprint=_launcher.compute_plan_fingerprint(plan_path),
                reject_high_selected_reconcile_budget=True,
            )

        assert seen == [None if lane.startswith("claude") else 258_400]
        # The refusal names the window it was judged against, and says when that was the default.
        assert "window" in str(refusal.value)
        assert ("(default)" in str(refusal.value)) == lane.startswith("claude")

    def test_selected_reconcile_snapshot_change_refuses_before_backend(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """Use the verified snapshot instead of silently rereading changed input."""
        snapshot = parse_plan(plan_path)
        expected_fingerprint = _launcher.compute_plan_fingerprint(plan_path)
        monkeypatch.setattr(
            _launcher, "compute_plan_fingerprint", lambda _path: "changed"
        )

        with pytest.raises(LauncherError, match="snapshot changed"):
            run_step(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                mode="run-reconcile",
                invoker=lambda _prompt: pytest.fail("backend must not run"),
                selected_reconcile_plan_snapshot=snapshot,
                selected_reconcile_plan_fingerprint=expected_fingerprint,
            )

    def test_selected_reconcile_fingerprint_recompute_failure_fails_closed(
        self, plan_path: Path, tmp_path: Path, monkeypatch
    ) -> None:
        """An unreadable-now plan must refuse like a changed one, not crash.

        Matches review_persistence.audit_input_fingerprint_matches_disk's
        posture: a bad current input is simply treated as stale.
        """
        snapshot = parse_plan(plan_path)
        expected_fingerprint = _launcher.compute_plan_fingerprint(plan_path)

        def boom(_path):
            raise OSError("permission denied")

        monkeypatch.setattr(_launcher, "compute_plan_fingerprint", boom)

        with pytest.raises(LauncherError, match="snapshot changed"):
            run_step(
                plan_path,
                repo_root=tmp_path,
                step_id=1,
                mode="run-reconcile",
                invoker=lambda _prompt: pytest.fail("backend must not run"),
                selected_reconcile_plan_snapshot=snapshot,
                selected_reconcile_plan_fingerprint=expected_fingerprint,
            )


class TestRunStepScopeFence:
    """The run lane delivers both fence halves to the executing agent."""

    @pytest.mark.parametrize("dry_run", (False, True))
    def test_run_step_rejects_unmatched_fence_before_backend_or_status_write(
        self, tmp_path: Path, dry_run: bool
    ) -> None:
        plan_path = _write_fenced_plan(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8") + "\n```\n",
            encoding="utf-8",
        )
        before = plan_path.read_text(encoding="utf-8")

        with pytest.raises(LauncherError, match="unmatched opening code fence"):
            run_step(
                plan_path,
                repo_root=tmp_path,
                dry_run=dry_run,
                invoker=lambda _prompt: pytest.fail("backend must not run"),
            )

        assert plan_path.read_text(encoding="utf-8") == before

    def test_run_step_prompt_carries_the_fence(self, tmp_path: Path) -> None:
        p = _write_fenced_plan(tmp_path)
        seen: list[str] = []

        run_step(
            p,
            repo_root=tmp_path,
            invoker=lambda prompt: seen.append(prompt) or (0, ""),
        )
        assert "PLAN_INTENT_MARKER" in seen[0]
        assert "STEP_ONE_INTENT_MARKER" in seen[0]
        assert "GUARDRAIL_MARKER" in seen[0]
        assert "OUT_OF_SCOPE_MARKER" in seen[0]
        assert "**Scope fence (authoritative, from the plan).**" in seen[0]

    def test_each_run_steps_prompt_carries_its_own_intent(
        self, tmp_path: Path
    ) -> None:
        p = _write_fenced_plan(tmp_path)
        seen: list[str] = []
        invoker = lambda prompt: seen.append(prompt) or (0, "")  # noqa: E731

        run_step(p, repo_root=tmp_path, invoker=invoker)
        run_step(p, repo_root=tmp_path, invoker=invoker)

        assert "STEP_ONE_INTENT_MARKER" in seen[0]
        assert "STEP_TWO_INTENT_MARKER" not in seen[0]
        assert "STEP_TWO_INTENT_MARKER" in seen[1]
        assert "STEP_ONE_INTENT_MARKER" not in seen[1]

    def test_test_directive_stays_last_after_the_fence(
        self, tmp_path: Path, capsys
    ) -> None:
        """The fence sits mid-prompt, so the appended directive keeps the
        tail — where the harness-parsed closing contract also lives."""
        yaml = _FENCED_PLAN.replace(
            "priority: medium\n",
            "priority: medium\nenforce_step_tests: true\n",
        ).replace(
            "    intent: STEP_ONE_INTENT_MARKER — wire the run prompt\n",
            "    intent: STEP_ONE_INTENT_MARKER — wire the run prompt\n"
            "    change_type: feature\n",
        )
        p = _write_fenced_plan(tmp_path, yaml)

        run_step(p, repo_root=tmp_path, invoker=lambda _: (0, ""), dry_run=True)

        out = capsys.readouterr().out
        directive = _test_directive(ChangeType.FEATURE).strip()
        assert out.rstrip().endswith(directive)
        assert out.index("**Scope fence") < out.index(directive)

    def test_prompt_budget_breakdown_includes_the_scope_fence(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        p = _write_fenced_plan(tmp_path)
        warns: list = []
        TestRunStepPromptBudget._spy_warn(monkeypatch, warns)

        run_step(p, repo_root=tmp_path, invoker=lambda _: (0, ""))

        blocks = dict(warns[0]["kwargs"]["blocks"])
        assert blocks["scope fence"] > 0

    def test_fenceless_plan_run_prompt_has_no_fence(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        # ``_PLAN`` carries no intent and no fence sections.
        seen: list[str] = []
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda prompt: seen.append(prompt) or (0, ""),
        )
        assert "**Scope fence" not in seen[0]

    def test_dry_run_preview_shows_the_fence(
        self, tmp_path: Path, capsys
    ) -> None:
        p = _write_fenced_plan(tmp_path)
        run_step(p, repo_root=tmp_path, invoker=lambda _: (0, ""), dry_run=True)
        out = capsys.readouterr().out
        assert "PLAN_INTENT_MARKER" in out
        assert "OUT_OF_SCOPE_MARKER" in out


class TestAppendLesson:
    def test_noop_when_lessons_unconfigured(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: No Lessons\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: x\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        plan = parse_plan(p)
        result = append_lesson(plan, plan.step_by_id(1), repo_root=tmp_path)
        assert result is None

    def test_appends_line_when_configured(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: With Lessons\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/with-lessons/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: First thing\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        plan = parse_plan(p)
        fixed = datetime(2026, 4, 22, 15, 30, 45, tzinfo=timezone.utc)
        lessons_path = append_lesson(
            plan, plan.step_by_id(1), repo_root=tmp_path, now=fixed
        )
        assert lessons_path is not None
        content = lessons_path.read_text(encoding="utf-8")
        assert content == "- 2026-04-22T15:30:45Z step 1: First thing\n"

    def test_appends_line_with_summary(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: With Summary\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/with-summary/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the parser\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        plan = parse_plan(p)
        fixed = datetime(2026, 4, 22, 15, 30, 45, tzinfo=timezone.utc)
        lessons_path = append_lesson(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            now=fixed,
            summary="Switched to ruamel.yaml to preserve comments through round-trip.",
        )
        assert lessons_path is not None
        content = lessons_path.read_text(encoding="utf-8")
        assert content == (
            "- 2026-04-22T15:30:45Z step 1: Build the parser"
            " — Switched to ruamel.yaml to preserve comments through round-trip.\n"
        )

    def test_append_only(self, tmp_path: Path) -> None:
        """Two calls produce two lines; existing content preserved."""
        text = (
            "---\n"
            "title: Append Only\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/append-only/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: First\n"
            "    status: done\n"
            "  - id: 2\n"
            "    title: Second\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        plan = parse_plan(p)
        t1 = datetime(2026, 4, 22, 10, 0, 0, tzinfo=timezone.utc)
        t2 = datetime(2026, 4, 22, 11, 0, 0, tzinfo=timezone.utc)
        append_lesson(plan, plan.step_by_id(1), repo_root=tmp_path, now=t1)
        append_lesson(plan, plan.step_by_id(2), repo_root=tmp_path, now=t2)

        lessons_path = tmp_path / "plan-details/append-only/lessons.md"
        content = lessons_path.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        assert len(lines) == 2
        assert "step 1:" in lines[0]
        assert "step 2:" in lines[1]


def _plan_with_change_type(
    change_type: Optional[str], *, enforce: bool = True
) -> str:
    """A 3-step plan whose current step (id 2) carries ``change_type``.

    ``change_type=None`` elides the line so the step parses unclassified —
    matching a legacy plan authored before the field existed. ``enforce``
    sets the plan-level ``enforce_step_tests`` switch (default ``True`` so
    the test-creation directive fires); pass ``enforce=False`` to model a
    legacy plan with the switch absent.
    """
    ct_line = f"    change_type: {change_type}\n" if change_type else ""
    enforce_line = "enforce_step_tests: true\n" if enforce else ""
    return (
        "---\n"
        "title: Change Type Test\n"
        "status: in-progress\n"
        "priority: medium\n"
        f"{enforce_line}"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: Second\n"
        "    depends_on: [1]\n"
        "    status: current\n"
        f"{ct_line}"
        "  - id: 3\n"
        "    title: Third\n"
        "    depends_on: [2]\n"
        "---\n\n"
        "# Change Type Test\n"
    )


def _classified_plan_path(
    tmp_path: Path, change_type: Optional[str], *, enforce: bool = True
) -> Path:
    p = tmp_path / "plan.md"
    p.write_text(
        _plan_with_change_type(change_type, enforce=enforce), encoding="utf-8"
    )
    return p


class TestRunPromptTestOrderDirective:
    """Step 6: the run prompt carries a change_type-derived test-order directive."""

    def test_run_prompt_carries_refactor_directive(self, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        path = _classified_plan_path(tmp_path, "refactor")
        run_step(path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "## Tests for this step" in received[0]
        assert "green before finishing" in received[0]
        # Withdrawn ordering contract must not reappear (BACKLOG #204).
        assert "BEFORE touching the code" not in received[0]

    def test_run_prompt_carries_feature_directive(self, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        path = _classified_plan_path(tmp_path, "feature")
        run_step(path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "## Tests for this step" in received[0]
        assert "green before finishing" in received[0]

    def test_run_prompt_no_directive_for_non_code(self, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        path = _classified_plan_path(tmp_path, "non-code")
        run_step(path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "Tests for this step" not in received[0]
        assert "Test-creation order" not in received[0]
        assert "BEFORE touching the code" not in received[0]

    def test_run_prompt_unchanged_for_unclassified(self, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        path = _classified_plan_path(tmp_path, None)
        run_step(path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "Tests for this step" not in received[0]
        assert "Test-creation order" not in received[0]
        assert "BEFORE touching the code" not in received[0]

    def test_no_directive_when_enforcement_off(self, tmp_path: Path) -> None:
        """A legacy plan without ``enforce_step_tests`` carries no directive
        even for a feature step — the switch gates the append."""
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        path = _classified_plan_path(tmp_path, "feature", enforce=False)
        run_step(path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "Tests for this step" not in received[0]

    def test_review_mode_omits_directive(self, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        # A refactor-classified step audited (not implemented) — the
        # MUTATING_MODES gate suppresses the directive.
        path = _classified_plan_path(tmp_path, "refactor")
        run_step(path, repo_root=tmp_path, mode="security", invoker=fake_invoker)
        assert len(received) == 1
        assert "Tests for this step" not in received[0]

    def test_dry_run_previews_directive(self, tmp_path: Path, capsys) -> None:
        path = _classified_plan_path(tmp_path, "refactor")
        run_step(
            path,
            repo_root=tmp_path,
            mode="run",
            dry_run=True,
            invoker=lambda _: (0, ""),
        )
        captured = capsys.readouterr()
        assert "## Tests for this step" in captured.out

    def test_directive_helper_code_types_share_one_block(self) -> None:
        """Both code types render the same directive. The per-type ordering
        contract was withdrawn (BACKLOG #204) — reinstating a refactor-only
        block fails here."""
        refactor = _test_directive(ChangeType.REFACTOR)
        feature = _test_directive(ChangeType.FEATURE)
        assert refactor and refactor == feature
        assert "green before finishing" in refactor

    def test_directive_helper_carries_no_ordering_contract(self) -> None:
        for ct in (ChangeType.REFACTOR, ChangeType.FEATURE):
            lowered = _test_directive(ct).lower()
            for banned in (
                "characterization",
                "before touching",
                "pass unchanged",
                "test-creation order",
            ):
                assert banned not in lowered, (
                    f"{ct} run directive reintroduced withdrawn ordering term "
                    f"{banned!r} — see BACKLOG #204"
                )

    def test_directive_helper_non_code_empty(self) -> None:
        assert _test_directive(ChangeType.NON_CODE) == ""

    def test_directive_helper_none_empty(self) -> None:
        assert _test_directive(None) == ""


class TestRunStepLessonsIntegration:
    def test_run_appends_lesson_when_lessons_configured(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: Run With Lessons\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/run-with-lessons/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        run_step(p, repo_root=tmp_path, invoker=lambda _: (0, ""))

        lessons_path = tmp_path / "plan-details/run-with-lessons/lessons.md"
        assert lessons_path.is_file()
        content = lessons_path.read_text(encoding="utf-8")
        assert "step 1: Only" in content

    def test_review_mode_does_not_append_lesson(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: No Lesson On Review\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/no-lesson-on-review/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        run_step(p, repo_root=tmp_path, mode="check", invoker=lambda _: (0, ""))

        lessons_path = tmp_path / "plan-details/no-lesson-on-review/lessons.md"
        assert not lessons_path.exists()

    def test_review_mode_does_not_mutate_plan(self, plan_path: Path, tmp_path: Path) -> None:
        """mode != 'run' should leave the plan file untouched even on success."""

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        original = plan_path.read_text(encoding="utf-8")
        result = run_step(
            plan_path,
            repo_root=tmp_path,
            mode="check",
            invoker=fake_invoker,
        )
        assert result.exit_code == 0
        assert result.done is False  # review modes never set done
        assert result.advanced_to is None
        assert plan_path.read_text(encoding="utf-8") == original  # byte-for-byte

    def test_review_mode_renders_mode_specific_template(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, mode="security", invoker=fake_invoker)
        assert len(received) == 1
        # Distinct content from run.md — at least one phrase unique to security.md.
        assert "Security audit" in received[0]
        assert "severity" in received[0].lower()

    def test_invoker_receives_rendered_prompt(self, plan_path: Path, tmp_path: Path) -> None:
        received: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            received.append(prompt)
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)
        assert len(received) == 1
        assert "Second" in received[0]  # step 2 title
        assert "Launcher Test" in received[0]  # plan title

    def test_run_step_appends_summary_when_present(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: Summary Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/summary-test/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build the parser\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "some output\n## Summary\nfake takeaway\n")

        run_step(p, repo_root=tmp_path, invoker=fake_invoker)

        lessons_path = tmp_path / "plan-details/summary-test/lessons.md"
        content = lessons_path.read_text(encoding="utf-8")
        assert "— fake takeaway" in content
        assert "step 1: Build the parser" in content

    def test_run_step_falls_back_when_no_summary(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: No Summary Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/no-summary-test/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Only\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "output without a summary section")

        run_step(p, repo_root=tmp_path, invoker=fake_invoker)

        lessons_path = tmp_path / "plan-details/no-summary-test/lessons.md"
        content = lessons_path.read_text(encoding="utf-8")
        assert "step 1: Only" in content
        assert "—" not in content  # no takeaway appended

    def test_run_step_prefers_stats_final_text_for_summary(
        self, tmp_path: Path
    ) -> None:
        # When the invoker exposes ``_last_stats.final_text`` (the
        # post-tool ``result`` envelope from stream-json), run_step
        # threads it through to ``extract_summary`` — even if the raw
        # stdout carries a different / no Summary block.
        from plan_tool.launcher import ClaudeRunStats

        text = (
            "---\n"
            "title: Threaded Summary Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "lessons: plan-details/threaded-summary-test/lessons.md\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Wire stats\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        class _Inv:
            def __init__(self) -> None:
                self._last_stats = ClaudeRunStats(
                    final_text=(
                        "## Summary\nenvelope takeaway from stats\n"
                    ),
                )

            def __call__(self, prompt: str) -> tuple[int, str]:
                # stdout lacks a Summary; the envelope provides it.
                return (0, "noise without a summary heading")

        run_step(p, repo_root=tmp_path, invoker=_Inv())

        lessons_path = (
            tmp_path / "plan-details/threaded-summary-test/lessons.md"
        )
        content = lessons_path.read_text(encoding="utf-8")
        assert "— envelope takeaway from stats" in content
        assert "step 1: Wire stats" in content


class TestWritePlanAppendLessonOrdering:
    """Step 8: write_plan / append_lesson must be transactional-ish.

    Lesson-first ordering closes the gap where a write_plan that
    succeeded followed by an append_lesson that raised used to leave
    the plan marked done with no matching lesson entry. The new order
    plus the ``append_lesson`` idempotency guard plus a partial-state
    stderr diagnostic constitute the fix.
    """

    _PLAN_TEXT = (
        "---\n"
        "title: Ordering Test\n"
        "status: in-progress\n"
        "priority: low\n"
        "lessons: plan-details/ordering-test/lessons.md\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: Second\n"
        "    depends_on: [1]\n"
        "    status: current\n"
        "  - id: 3\n"
        "    title: Third\n"
        "    depends_on: [2]\n"
        "---\n"
        "\n"
        "# Ordering Test\n"
    )

    @staticmethod
    def _fake_invoker(prompt: str) -> tuple[int, str]:
        return (0, "## Validation\n- ok\n## Summary\nok\n")

    def _setup(self, tmp_path: Path) -> Path:
        p = tmp_path / "plan.md"
        p.write_text(self._PLAN_TEXT, encoding="utf-8")
        return p

    def test_lesson_writes_before_plan_in_happy_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import launcher as launcher_module

        p = self._setup(tmp_path)

        order: list[str] = []
        real_append = launcher_module.append_lesson
        real_write = launcher_module.write_plan

        def recorded_append(*args, **kwargs):
            order.append("append_lesson")
            return real_append(*args, **kwargs)

        def recorded_write(*args, **kwargs):
            order.append("write_plan")
            return real_write(*args, **kwargs)

        monkeypatch.setattr(
            launcher_module, "append_lesson", recorded_append
        )
        monkeypatch.setattr(
            launcher_module, "write_plan", recorded_write
        )

        result = run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)
        assert result.done is True
        assert order == ["append_lesson", "write_plan"]

        reloaded = parse_plan(p)
        assert reloaded.step_by_id(2).status == StepStatus.DONE
        lessons_path = tmp_path / "plan-details/ordering-test/lessons.md"
        assert lessons_path.is_file()
        assert "step 2: Second" in lessons_path.read_text(encoding="utf-8")

    def test_append_lesson_failure_leaves_plan_unchanged(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import launcher as launcher_module

        p = self._setup(tmp_path)
        original_bytes = p.read_bytes()

        def boom(*args, **kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(launcher_module, "append_lesson", boom)

        with pytest.raises(OSError, match="disk full"):
            run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)

        # Plan file on disk byte-for-byte unchanged — write_plan was
        # never reached because append_lesson is first now.
        assert p.read_bytes() == original_bytes
        reloaded = parse_plan(p)
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT

        lessons_path = tmp_path / "plan-details/ordering-test/lessons.md"
        # Lessons file may not exist, or if it does, must not contain a
        # step 2 entry (the patched append_lesson never wrote one).
        if lessons_path.exists():
            assert "step 2:" not in lessons_path.read_text(encoding="utf-8")

        err = capsys.readouterr().err
        assert "step 2 persistence partial-state" in err
        assert "OSError" in err

    def test_write_plan_failure_keeps_lesson_with_current_plan(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool import launcher as launcher_module

        p = self._setup(tmp_path)

        def boom(*args, **kwargs):
            raise OSError("plan write failed")

        monkeypatch.setattr(launcher_module, "write_plan", boom)

        with pytest.raises(OSError, match="plan write failed"):
            run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)

        # Lesson has landed (append_lesson ran first).
        lessons_path = tmp_path / "plan-details/ordering-test/lessons.md"
        assert lessons_path.is_file()
        content = lessons_path.read_text(encoding="utf-8")
        assert "step 2: Second" in content
        assert content.count("step 2:") == 1

        # Plan write was patched to raise, so the on-disk plan still
        # records step 2 as current.
        reloaded = parse_plan(p)
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT

        err = capsys.readouterr().err
        assert "step 2 persistence partial-state" in err
        # The diagnostic must name the committed/failed sides so the
        # operator can tell which write needs retry.
        assert "committed=lessons" in err
        assert "plan write raised" in err

    def test_retry_after_partial_failure_does_not_duplicate_lesson(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool import launcher as launcher_module

        p = self._setup(tmp_path)

        def boom(*args, **kwargs):
            raise OSError("plan write failed")

        monkeypatch.setattr(launcher_module, "write_plan", boom)

        with pytest.raises(OSError):
            run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)

        lessons_path = tmp_path / "plan-details/ordering-test/lessons.md"
        assert lessons_path.is_file()
        assert (
            lessons_path.read_text(encoding="utf-8").count("step 2:") == 1
        )

        # Undo the write_plan patch and re-run — the in-memory plan
        # parsed on disk is still "step 2 current", so the success
        # path is re-entered. The idempotency guard inside
        # ``append_lesson`` must skip rather than append a duplicate.
        monkeypatch.undo()

        result = run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)
        assert result.done is True

        # Exactly one step 2 entry survives across both runs.
        content = lessons_path.read_text(encoding="utf-8")
        assert content.count("step 2:") == 1

        # Plan flipped to done on the retry.
        reloaded = parse_plan(p)
        assert reloaded.step_by_id(2).status == StepStatus.DONE

    @pytest.mark.parametrize("failing_side", ["lessons", "plan"])
    def test_partial_state_log_names_step_and_recovery(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
        failing_side: str,
    ) -> None:
        from plan_tool import launcher as launcher_module

        p = self._setup(tmp_path)

        def boom(*args, **kwargs):
            raise OSError(f"{failing_side} write failed")

        if failing_side == "lessons":
            monkeypatch.setattr(launcher_module, "append_lesson", boom)
        else:
            monkeypatch.setattr(launcher_module, "write_plan", boom)

        with pytest.raises(OSError):
            run_step(p, repo_root=tmp_path, invoker=self._fake_invoker)

        err = capsys.readouterr().err
        assert "step 2 persistence partial-state" in err
        assert "OSError" in err
        assert "plan-tool run --step 2" in err


_ALL_DONE_PLAN = """---
title: All Done Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: First Done
    status: done
  - id: 2
    title: Second Done
    depends_on: [1]
    status: done
  - id: 3
    title: Third Done
    depends_on: [2]
    status: done
  - id: 4
    title: Pending
    depends_on: [3]
---

# All Done Plan
"""


class TestRunAllDoneSteps:
    @pytest.fixture()
    def all_done_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "all_done.md"
        p.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        return p

    def test_invokes_once_per_done_step(self, all_done_path: Path, tmp_path: Path) -> None:
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, f"output #{len(calls)}")

        results = run_all_done_steps(
            all_done_path, repo_root=tmp_path, mode="check", invoker=fake_invoker
        )
        assert len(results) == 3
        assert len(calls) == 3

    def test_step_output_included_in_results(self, all_done_path: Path, tmp_path: Path) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            for title in ("First Done", "Second Done", "Third Done"):
                if title in prompt:
                    return (0, f"review of: {title}")
            return (0, "unknown")

        results = run_all_done_steps(
            all_done_path, repo_root=tmp_path, mode="check", invoker=fake_invoker
        )
        assert "First Done" in results[0].stdout
        assert "Second Done" in results[1].stdout
        assert "Third Done" in results[2].stdout

    def test_step_titles_in_results(self, all_done_path: Path, tmp_path: Path) -> None:
        results = run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=lambda _: (0, ""),
        )
        assert results[0].step_title == "First Done"
        assert results[1].step_title == "Second Done"
        assert results[2].step_title == "Third Done"

    def test_max_steps_takes_last_n(self, all_done_path: Path, tmp_path: Path) -> None:
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, "")

        results = run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=fake_invoker,
            max_steps=2,
        )
        assert len(results) == 2
        assert len(calls) == 2
        assert results[0].step_id == 2
        assert results[1].step_id == 3

    def test_mutating_mode_raises_before_invocation(
        self, all_done_path: Path, tmp_path: Path
    ) -> None:
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, "")

        with pytest.raises(LauncherError):
            run_all_done_steps(
                all_done_path, repo_root=tmp_path, mode="run", invoker=fake_invoker
            )
        assert calls == []

    def test_detail_render_refusal_is_a_launcher_error(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import render_detail_format_version_marker

        detail = tmp_path / "detail.md"
        detail.write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Summary\n\nUnsupported.\n",
            encoding="utf-8",
        )
        plan = tmp_path / "all_done.md"
        plan.write_text(
            "---\n"
            "title: Done\n"
            "status: completed\n"
            "priority: low\n"
            "steps:\n"
            "- id: 1\n"
            "  title: Done\n"
            "  detail: detail.md\n"
            "  status: done\n"
            "---\n"
            "# Done\n",
            encoding="utf-8",
        )
        calls = 0

        def fake_invoker(_prompt: str) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            return 0, ""

        with pytest.raises(LauncherError, match="999"):
            run_all_done_steps(
                plan, repo_root=tmp_path, mode="check", invoker=fake_invoker
            )
        assert calls == 0

    def test_plan_file_unchanged(self, all_done_path: Path, tmp_path: Path) -> None:
        original = all_done_path.read_text(encoding="utf-8")
        run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=lambda _: (0, ""),
        )
        assert all_done_path.read_text(encoding="utf-8") == original

    def test_dry_run_does_not_invoke(self, all_done_path: Path, tmp_path: Path) -> None:
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return (0, "")

        results = run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=fake_invoker,
            dry_run=True,
        )
        assert calls == []
        assert len(results) == 3
        assert "First Done" in results[0].stdout  # prompt, not claude output


# --- progress reporting ----------------------------------------------------


class _RecordingHandle(StepHandle):
    def __init__(self) -> None:
        self.completed: tuple[float, int] | None = None
        self.failed: tuple[float, str] | None = None

    def complete(self, elapsed_s: float, response_bytes: int) -> None:
        self.completed = (elapsed_s, response_bytes)

    def fail(self, elapsed_s: float, reason: str) -> None:
        self.failed = (elapsed_s, reason)


class _RecordingReporter(ProgressReporter):
    def __init__(self) -> None:
        self.starts: list[tuple[int, int, str]] = []
        self.handles: list[_RecordingHandle] = []

    def start_step(self, idx: int, total: int, label: str) -> StepHandle:
        self.starts.append((idx, total, label))
        h = _RecordingHandle()
        self.handles.append(h)
        return h


class TestRunStepProgress:
    def test_complete_on_zero_exit(self, plan_path: Path, tmp_path: Path) -> None:
        reporter = _RecordingReporter()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "claude output here"),
            reporter=reporter,
        )
        assert reporter.starts == [(1, 1, "step 2: Second (mode=run)")]
        h = reporter.handles[0]
        assert h.completed is not None
        assert h.failed is None
        _, nbytes = h.completed
        assert nbytes == len("claude output here".encode("utf-8"))

    def test_label_includes_change_type_tag(self, tmp_path: Path) -> None:
        """Step 8: a classified step's label carries the inline tag."""
        reporter = _RecordingReporter()
        run_step(
            _classified_plan_path(tmp_path, "refactor"),
            repo_root=tmp_path,
            invoker=lambda p: (0, "claude output here"),
            reporter=reporter,
        )
        assert reporter.starts == [(1, 1, "step 2: Second [refactor] (mode=run)")]

    def test_label_unclassified_unchanged(self, tmp_path: Path) -> None:
        """Step 8: an unclassified step's label has no tag (byte-identical)."""
        reporter = _RecordingReporter()
        run_step(
            _classified_plan_path(tmp_path, None),
            repo_root=tmp_path,
            invoker=lambda p: (0, "claude output here"),
            reporter=reporter,
        )
        assert reporter.starts == [(1, 1, "step 2: Second (mode=run)")]

    def test_label_includes_explicit_mode(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """Reconcile mode (or any review mode) — the label tells the user
        which prompt template was used."""
        reporter = _RecordingReporter()
        run_step(
            plan_path,
            repo_root=tmp_path,
            mode="detail-reconcile",
            invoker=lambda p: (0, "review body"),
            reporter=reporter,
        )
        assert reporter.starts == [
            (1, 1, "step 2: Second (mode=detail-reconcile)")
        ]

    def test_fail_on_nonzero_exit(self, plan_path: Path, tmp_path: Path) -> None:
        reporter = _RecordingReporter()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: (3, "partial output"),
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "code 3" in reason

    def test_dry_run_emits_no_progress(
        self, plan_path: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        reporter = _RecordingReporter()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "should not be called"),
            dry_run=True,
            reporter=reporter,
        )
        assert reporter.starts == []


class TestRunAllDoneStepsProgress:
    @pytest.fixture()
    def all_done_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "all_done.md"
        p.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        return p

    def test_per_step_idx_and_label(
        self, all_done_path: Path, tmp_path: Path
    ) -> None:
        reporter = _RecordingReporter()
        run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="detail-reconcile",
            invoker=lambda p: (0, "ok"),
            reporter=reporter,
        )
        assert reporter.starts == [
            (1, 3, "step 1: First Done (mode=detail-reconcile)"),
            (2, 3, "step 2: Second Done (mode=detail-reconcile)"),
            (3, 3, "step 3: Third Done (mode=detail-reconcile)"),
        ]
        for h in reporter.handles:
            assert h.completed is not None
            assert h.failed is None

    def test_fail_per_step_on_nonzero_exit(
        self, all_done_path: Path, tmp_path: Path
    ) -> None:
        reporter = _RecordingReporter()
        # First two succeed, third fails — verify the third gets fail() not complete().
        codes = iter([(0, "ok"), (0, "ok"), (2, "broken")])

        def fake(prompt: str) -> tuple[int, str]:
            return next(codes)

        run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=fake,
            reporter=reporter,
        )
        assert reporter.handles[0].completed is not None
        assert reporter.handles[1].completed is not None
        assert reporter.handles[2].completed is None
        assert reporter.handles[2].failed is not None

    def test_max_steps_narrows_total(
        self, all_done_path: Path, tmp_path: Path
    ) -> None:
        reporter = _RecordingReporter()
        run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=lambda p: (0, "ok"),
            max_steps=2,
            reporter=reporter,
        )
        # Only the last two done steps; idx counts from 1, total reflects
        # the limited range.
        assert [t for _, t, _ in reporter.starts] == [2, 2]
        assert [i for i, _, _ in reporter.starts] == [1, 2]

    def test_dry_run_emits_no_progress(
        self, all_done_path: Path, tmp_path: Path
    ) -> None:
        reporter = _RecordingReporter()
        run_all_done_steps(
            all_done_path,
            repo_root=tmp_path,
            mode="check",
            invoker=lambda p: (0, "should not be called"),
            dry_run=True,
            reporter=reporter,
        )
        assert reporter.starts == []


class TestCmdReviewAllEndToEndStderr:
    def test_emits_progress_on_stderr(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text(
            '{"plans": ["all_done.md"]}\n', encoding="utf-8"
        )
        (tmp_path / ".git").mkdir()

        original = cli_module.run_all_done_steps

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "ok")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.run_all_done_steps", patched)
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            [
                "--manifest",
                str(manifest),
                "reconcile-all",
                "all_done",
                "--mode",
                "check",
            ]
        )
        assert rc == 0
        err = capsys.readouterr().err
        # The per-step progress label reflects the mode that ran.
        assert "[1/3] step 1: First Done (mode=check)" in err
        assert "[3/3] step 3: Third Done (mode=check)" in err
        assert err.count("done in") == 3


# --- pre-flight path validation -------------------------------------------


_PREFLIGHT_PLAN = """---
title: Preflight Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: First
    files:
      - nonexistent/src/foo.py
    status: current
  - id: 2
    title: Second
    files:
      - nonexistent/src/bar.py
    depends_on: [1]
---

# Preflight Plan
"""


class TestPreflightStepPaths:
    """Refuse to invoke claude when declared files don't resolve.

    The plan paths intentionally live two missing levels deep
    (``nonexistent/src/``) so the auto-promotion for one-level
    new-subdir creation (:func:`_promote_new_subdir_paths`) does
    *not* apply — the gate fires as written.
    """

    def _setup_with_existing_files(self, tmp_path: Path) -> Path:
        (tmp_path / "nonexistent" / "src").mkdir(parents=True)
        (tmp_path / "nonexistent" / "src" / "foo.py").write_text(
            "x", encoding="utf-8"
        )
        (tmp_path / "nonexistent" / "src" / "bar.py").write_text(
            "y", encoding="utf-8"
        )
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        return p

    def test_passes_when_all_paths_resolve(self, tmp_path: Path) -> None:
        plan_path = self._setup_with_existing_files(tmp_path)
        plan = parse_plan(plan_path)
        # Should not raise.
        preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_passes_when_files_unset(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: No Files\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        plan = parse_plan(p)
        preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_passes_when_parent_exists_file_missing(self, tmp_path: Path) -> None:
        """NEW status (parent exists, file doesn't) is fine — the step may create it."""
        (tmp_path / "nonexistent" / "src").mkdir(parents=True)
        # Only foo.py exists; bar.py doesn't, but parent does → NEW.
        (tmp_path / "nonexistent" / "src" / "foo.py").write_text(
            "x", encoding="utf-8"
        )
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        plan = parse_plan(p)
        preflight_step_paths(plan, plan.step_by_id(2), repo_root=tmp_path)

    def test_refuses_when_step_has_missing_parent(self, tmp_path: Path) -> None:
        # Step 1's path is two missing levels deep → no auto-promotion;
        # gate fires. Step 2's path resolves so the systemic ratio stays
        # under threshold (we want the per-step branch, not plan-wide).
        (tmp_path / "src2").mkdir()
        plan_text = (
            "---\n"
            "title: Mixed\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: First\n"
            "    files:\n"
            "      - nonexistent/src/foo.py\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: Second\n"
            "    files:\n"
            "      - src2/a.py\n"
            "      - src2/b.py\n"
            "      - src2/c.py\n"
            "      - src2/d.py\n"
            "    depends_on: [1]\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(plan_text, encoding="utf-8")
        plan = parse_plan(p)
        with pytest.raises(LauncherError, match="don't resolve"):
            preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_promotes_one_level_new_subdir_path(self, tmp_path: Path) -> None:
        """Step that creates one new subdir under an existing dir is allowed.

        ``tests/fixtures/`` exists; ``tests/fixtures/reformat/`` is the
        new directory the step would create. Should NOT raise (auto-
        promotion) and should announce the new dir on stderr.
        """
        (tmp_path / "tests" / "fixtures").mkdir(parents=True)
        plan_text = (
            "---\n"
            "title: New subdir\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Create fixtures\n"
            "    files:\n"
            "      - tests/fixtures/reformat/a.md\n"
            "      - tests/fixtures/reformat/b.md\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(plan_text, encoding="utf-8")
        plan = parse_plan(p)
        # Should not raise.
        preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_promotes_emits_stderr_announcement(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Auto-promoted new subdirs are announced on stderr."""
        (tmp_path / "tests" / "fixtures").mkdir(parents=True)
        plan_text = (
            "---\n"
            "title: New subdir\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Create fixtures\n"
            "    files:\n"
            "      - tests/fixtures/reformat/a.md\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(plan_text, encoding="utf-8")
        plan = parse_plan(p)
        preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)
        captured = capsys.readouterr()
        assert "step 1 will create new directory" in captured.err
        assert "tests/fixtures/reformat/" in captured.err

    def test_new_directory_announcement_uses_posix_outside_repo_fallback(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The outside-repo fallback keeps the literal slash POSIX-compatible."""
        outside = tmp_path.parent / f"{tmp_path.name}-outside-announcement"
        outside.mkdir(exist_ok=True)
        plan_text = (
            "---\n"
            "title: Outside new subdir\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Create fixtures\n"
            "    files:\n"
            f"      - {outside}/reformat/a.md\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(plan_text, encoding="utf-8")

        plan = parse_plan(p)
        monkeypatch.setattr(
            _launcher.Path,
            "as_posix",
            lambda path: f"POSIX:{path}",
        )
        preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

        assert f"POSIX:{outside}/reformat/" in capsys.readouterr().err

    def test_does_not_promote_two_levels_missing(self, tmp_path: Path) -> None:
        """Auto-promotion is conservative: grandparent must exist.

        ``deep/nested/missing/foo.py`` has ``missing/`` missing AND
        ``nested/`` missing — promotion does not apply, gate fires.
        """
        (tmp_path / "src2").mkdir()  # keeps plan-wide ratio under threshold
        plan_text = (
            "---\n"
            "title: Deep missing\n"
            "status: in-progress\n"
            "priority: medium\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Deep\n"
            "    files:\n"
            "      - deep/nested/missing/foo.py\n"
            "    status: current\n"
            "  - id: 2\n"
            "    title: OK\n"
            "    files:\n"
            "      - src2/a.py\n"
            "      - src2/b.py\n"
            "      - src2/c.py\n"
            "      - src2/d.py\n"
            "    depends_on: [1]\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(plan_text, encoding="utf-8")
        plan = parse_plan(p)
        with pytest.raises(LauncherError, match="don't resolve"):
            preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_refuses_with_plan_wide_mismatch_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """≥80% MISSING_PARENT plan-wide → systemic diagnostic, not per-step."""
        # No `src/` directory → all paths in _PREFLIGHT_PLAN miss parents.
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        plan = parse_plan(p)
        with pytest.raises(LauncherError, match="plan-wide path issue"):
            preflight_step_paths(plan, plan.step_by_id(1), repo_root=tmp_path)

    def test_allow_missing_parent_overrides(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        plan = parse_plan(p)
        # Should not raise.
        preflight_step_paths(
            plan,
            plan.step_by_id(1),
            repo_root=tmp_path,
            allow_missing_parent=True,
        )

    def test_run_step_refuses_on_missing_parent(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        called: list[str] = []

        def fake(prompt: str) -> tuple[int, str]:
            called.append(prompt)
            return (0, "")

        with pytest.raises(LauncherError):
            run_step(p, repo_root=tmp_path, invoker=fake)
        # Pre-flight refused; claude never called.
        assert called == []

    def test_run_step_with_allow_flag_succeeds(self, tmp_path: Path) -> None:
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        called: list[str] = []

        def fake(prompt: str) -> tuple[int, str]:
            called.append(prompt)
            # Create the declared file: an unchanged step is blocked (no edits applied).
            target = tmp_path / "nonexistent" / "src" / "foo.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
            return (0, "")

        result = run_step(
            p,
            repo_root=tmp_path,
            invoker=fake,
            allow_missing_parent=True,
        )
        assert result.exit_code == 0
        assert called  # claude was invoked

    def test_run_step_check_mode_also_refuses(self, tmp_path: Path) -> None:
        """Pre-flight fires for review modes too — bad path is bad regardless of mode."""
        p = tmp_path / "plan.md"
        p.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        called: list[str] = []

        def fake(prompt: str) -> tuple[int, str]:
            called.append(prompt)
            return (0, "")

        with pytest.raises(LauncherError):
            run_step(p, repo_root=tmp_path, mode="check", invoker=fake)
        assert called == []

    def test_cli_run_returns_2_on_preflight_failure(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "plan.md"
        plan.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "run", "plan"]
        )
        assert rc == 2
        err = capsys.readouterr().err
        assert "error:" in err

    def test_cli_run_with_allow_flag_proceeds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "plan.md"
        plan.write_text(_PREFLIGHT_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        original = cli_module.run_step

        def edits_declared_file(prompt: str) -> tuple[int, str]:
            # Create the declared file: an unchanged step is blocked (no edits applied).
            target = tmp_path / "nonexistent" / "src" / "foo.py"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("x\n", encoding="utf-8")
            return (0, "")

        def patched(path, **kwargs):
            kwargs["invoker"] = edits_declared_file
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "run", "plan",
                "--allow-missing-parent",
            ]
        )
        assert rc == 0


# --- post-flight verification ---------------------------------------------


_POSTFLIGHT_PLAN = """---
title: Postflight Plan
status: in-progress
priority: medium
lessons: lessons.md
steps:
  - id: 1
    title: First
    files:
      - foo.py
      - bar.py
    status: current
---

# Postflight Plan
"""


class TestRunStepPostFlight:
    def _setup(self, tmp_path: Path) -> Path:
        (tmp_path / "foo.py").write_text("foo\n", encoding="utf-8")
        (tmp_path / "bar.py").write_text("bar\n", encoding="utf-8")
        p = tmp_path / "plan.md"
        p.write_text(_POSTFLIGHT_PLAN, encoding="utf-8")
        return p

    def test_blocks_and_names_no_edits_applied_when_no_files_modified(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """An exit-0 step that changed no declared file is not advanced,
        and the failure is named for what happened, not as a missing test."""
        p = self._setup(tmp_path)

        # Invoker that doesn't touch any files.
        def fake(prompt: str) -> tuple[int, str]:
            return (0, "## Summary\nDid nothing.\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.exit_code == 1
        assert result.done is False
        assert result.advanced_to is None
        err = capsys.readouterr().err
        assert "[no edits applied] FAILED" in err
        assert "foo.py" in err
        assert "bar.py" in err
        assert "--accept" in err
        assert "test-authoring gate" not in err
        note = parse_plan(p).steps[0].status_note
        assert note.startswith("no edits applied:")

    def test_names_no_edits_applied_not_test_authoring_when_enforcement_on(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """With test enforcement on, an unchanged step is still named for
        what happened; the test-authoring text would point the next attempt
        at tests instead."""
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=True)

        result = run_step(p, repo_root=tmp_path, invoker=lambda _p: (0, "ok"))
        assert result.exit_code == 1
        assert result.done is False
        err = capsys.readouterr().err
        assert "[no edits applied] FAILED" in err
        assert "test-authoring gate" not in err
        assert parse_plan(p).steps[0].status_note.startswith("no edits applied:")

    def test_failed_step_receipt_carries_reason_and_sidecar_not_reply_text(
        self, tmp_path: Path
    ) -> None:
        """The reply lives in a sidecar; the run log gets a receipt with its
        digest and the producer-owned reason, never the reply text."""
        import hashlib

        from plan_tool.run_log import RunLogWriter, read_run_events

        p = self._setup(tmp_path)
        reply = "## Summary\nstopped: upstream contract missing SECRET-MARKER\n"
        writer = RunLogWriter.start(
            repo_root=tmp_path, slug="plan", command="run", argv=["run", "plan"]
        )

        result = run_step(
            p, repo_root=tmp_path, invoker=lambda _p: (0, reply), run_logger=writer
        )
        assert result.exit_code == 1

        events = read_run_events(writer.log_path)
        receipts = [e for e in events if e["event"] == "model_failure_receipt"]
        assert len(receipts) == 1
        receipt = receipts[0]
        assert receipt["reason"] == "no-edits-applied"
        assert receipt["response_sha256"] == hashlib.sha256(
            reply.encode("utf-8")
        ).hexdigest()
        assert receipt["sidecar_disposition"] == "written"
        assert (tmp_path / receipt["sidecar_path"]).read_text(
            encoding="utf-8"
        ) == reply
        assert "SECRET-MARKER" not in writer.log_path.read_text(encoding="utf-8")

    def test_accept_hint_only_when_a_gate_can_certify(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """`--accept` refuses with no test_command and no gate, so the
        failure must not advertise it as the way forward there."""
        p = self._setup(tmp_path)  # no test_command, no gate
        run_step(p, repo_root=tmp_path, invoker=lambda _p: (0, "ok"))
        err = capsys.readouterr().err
        assert "[no edits applied] FAILED" in err
        assert "--accept` (nothing certifies" in err
        assert "add a `test_command:`" in err

        gated = tmp_path / "gated"
        gated.mkdir()
        (gated / "foo.py").write_text("foo\n", encoding="utf-8")
        gp = gated / "plan.md"
        gp.write_text(_gate_plan_body(["true"]), encoding="utf-8")
        run_step(gp, repo_root=gated, invoker=lambda _p: (0, "ok"))
        err = capsys.readouterr().err
        assert "[no edits applied] FAILED" in err
        assert "certifies the step with the plan's gates" in err
        assert "nothing certifies" not in err

    def test_identical_rewrite_is_no_edits_applied(self, tmp_path: Path) -> None:
        """Content decides, not mtime: rewriting the same bytes applied no
        edit, so the step must not advance on a bumped mtime alone."""
        import time as time_module

        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            time_module.sleep(0.02)
            for name, body in (("foo.py", "foo\n"), ("bar.py", "bar\n")):
                (tmp_path / name).write_text(body, encoding="utf-8")
            return (0, "## Summary\nrewrote\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.exit_code == 1
        assert result.done is False

    def test_declared_creates_entry_never_written_is_no_edits_applied(
        self, tmp_path: Path
    ) -> None:
        """Deliberate carve-out: a path missing before and after counts as
        unchanged, so a step whose only deliverable was never created is
        blocked (the case a step advancing with none of its files created)."""
        text = (
            "---\ntitle: Creates Plan\nstatus: in-progress\npriority: low\n"
            "steps:\n  - id: 1\n    title: One\n    creates:\n"
            "      - new_module.py\n    status: current\n---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        result = run_step(p, repo_root=tmp_path, invoker=lambda _p: (0, "ok"))
        assert result.exit_code == 1
        assert result.done is False

    def test_sidecar_holds_final_text_not_the_verbose_stream(
        self, tmp_path: Path
    ) -> None:
        """The reply kept for a failed step is the result envelope's
        `final_text`, not the raw stream with its tool-use chatter."""
        import hashlib

        from plan_tool.run_log import RunLogWriter, read_run_events
        from plan_tool.backend import ClaudeRunStats

        p = self._setup(tmp_path)

        def invoker(prompt: str) -> tuple[int, str]:
            return (0, "verbose stream\ntool chatter\n")

        invoker._last_stats = ClaudeRunStats(final_text="the final reply\n")  # type: ignore[attr-defined]
        writer = RunLogWriter.start(
            repo_root=tmp_path, slug="plan", command="run", argv=["run", "plan"]
        )
        run_step(p, repo_root=tmp_path, invoker=invoker, run_logger=writer)

        receipt = next(
            e
            for e in read_run_events(writer.log_path)
            if e["event"] == "model_failure_receipt"
        )
        assert receipt["response_sha256"] == hashlib.sha256(
            b"the final reply\n"
        ).hexdigest()
        assert (tmp_path / receipt["sidecar_path"]).read_text(
            encoding="utf-8"
        ) == "the final reply\n"

    def test_directory_entry_in_files_is_not_reported_as_no_edits(
        self, tmp_path: Path
    ) -> None:
        """A directory has no content digest, so unchanged cannot be proven:
        the check must fail open, not block work that landed inside it."""
        (tmp_path / "pkg").mkdir()
        text = (
            "---\ntitle: Dir Plan\nstatus: in-progress\npriority: low\n"
            "steps:\n  - id: 1\n    title: One\n    files:\n      - pkg\n"
            "    status: current\n---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        result = run_step(p, repo_root=tmp_path, invoker=lambda _p: (0, "ok"))
        assert result.done is True

    @pytest.mark.parametrize(
        "reason", ["invoke", "test-authoring-gate", "test-gate", "gate"]
    )
    def test_each_failure_kind_emits_one_receipt_with_its_reason(
        self, tmp_path: Path, reason: str
    ) -> None:
        """DATA_CONTRACT.md lists these `reason` values; dropping a receipt
        call at any emit site must turn this red."""
        from plan_tool.run_log import RunLogWriter, read_run_events

        invoker = lambda _p: (0, "## Summary\nedited\n")  # noqa: E731

        def edit_foo(_p: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Summary\nedited\n")

        if reason == "test-authoring-gate":
            _git_init(tmp_path)
            plan_path = _gate_plan_path(tmp_path, "feature", enforce=True)
            invoker = lambda _p: (  # noqa: E731
                (tmp_path / "src.py").write_text("edited\n", encoding="utf-8"),
                (0, "ok"),
            )[1]
        else:
            (tmp_path / "foo.py").write_text("foo\n", encoding="utf-8")
            plan_path = tmp_path / "plan.md"
            invoker = edit_foo
            if reason == "invoke":
                plan_path.write_text(_gate_plan_body([]), encoding="utf-8")
                invoker = lambda _p: (3, "boom")  # noqa: E731
            elif reason == "test-gate":
                plan_path.write_text(
                    _gate_plan_body([], test_command="exit 1"), encoding="utf-8"
                )
            else:
                plan_path.write_text(_gate_plan_body(["false"]), encoding="utf-8")

        writer = RunLogWriter.start(
            repo_root=tmp_path, slug="plan", command="run", argv=["run", "plan"]
        )
        result = run_step(
            plan_path, repo_root=tmp_path, invoker=invoker, run_logger=writer
        )
        assert result.exit_code != 0

        receipts = [
            e
            for e in read_run_events(writer.log_path)
            if e["event"] == "model_failure_receipt"
        ]
        assert [r["reason"] for r in receipts] == [reason]

    def test_two_failures_of_one_step_keep_separate_sidecars(
        self, tmp_path: Path
    ) -> None:
        """A second failed call under one logger must not overwrite the first
        reply, or the first receipt's digest stops matching its sidecar."""
        from plan_tool.run_log import RunLogWriter, read_run_events

        p = self._setup(tmp_path)
        writer = RunLogWriter.start(
            repo_root=tmp_path, slug="plan", command="run", argv=["run", "plan"]
        )
        for reply in ("first reply\n", "second reply\n"):
            run_step(
                p, repo_root=tmp_path, invoker=lambda _p, r=reply: (0, r),
                run_logger=writer,
            )

        receipts = [
            e
            for e in read_run_events(writer.log_path)
            if e["event"] == "model_failure_receipt"
        ]
        assert len(receipts) == 2
        assert receipts[0]["sidecar_path"] != receipts[1]["sidecar_path"]
        assert (tmp_path / receipts[0]["sidecar_path"]).read_text(
            encoding="utf-8"
        ) == "first reply\n"

    def test_same_size_edit_within_same_second_is_not_no_edits(
        self, tmp_path: Path
    ) -> None:
        """The check compares content, so a same-size, same-mtime edit still
        counts as applied (the unchanged check blocks now, so a false
        positive would reject real work)."""
        import os

        p = self._setup(tmp_path)
        foo = tmp_path / "foo.py"
        before = foo.stat()

        def fake(prompt: str) -> tuple[int, str]:
            foo.write_text("FOO\n", encoding="utf-8")  # same size as "foo\n"
            os.utime(foo, ns=(before.st_atime_ns, before.st_mtime_ns))
            return (0, "## Summary\nedited\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.exit_code == 0
        assert result.done is True

    def test_no_warning_when_a_file_modified(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._setup(tmp_path)
        # Force a positive mtime delta and size change.
        import time as time_module

        def fake(prompt: str) -> tuple[int, str]:
            time_module.sleep(0.01)
            (tmp_path / "foo.py").write_text("modified content\n", encoding="utf-8")
            return (0, "## Summary\nModified foo.\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        err = capsys.readouterr().err
        assert result.exit_code == 0
        assert result.done is True
        assert "[no edits applied]" not in err

    def test_warns_when_summary_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            # Touch a file so the file-modification warning doesn't fire.
            (tmp_path / "foo.py").write_text("changed\nbody\n", encoding="utf-8")
            return (0, "no summary section here\n")

        run_step(p, repo_root=tmp_path, invoker=fake)
        err = capsys.readouterr().err
        assert "no `## Summary` line" in err

    def test_no_warnings_in_review_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Review modes don't warn — they don't claim to modify files."""
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "no summary needed\n")

        result = run_step(p, repo_root=tmp_path, mode="check", invoker=fake)
        err = capsys.readouterr().err
        assert result.exit_code == 0
        assert "[no edits applied]" not in err
        assert "no `## Summary` line" not in err
        assert parse_plan(p).steps[0].status_note in (None, "")

    def test_no_modification_warning_when_step_has_no_files(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Steps without `files:` skip the modification check."""
        text = (
            "---\n"
            "title: No Files\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "    status: current\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "## Summary\nok\n")

        # Deliberately exempt from the no-edits block: with no declared set
        # there is nothing to compare, so the step advances.
        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True
        err = capsys.readouterr().err
        assert "[no edits applied]" not in err


_CREATES_PLAN = """---
title: Creates Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: Produce the fixtures
    files:
      - foo.py
    creates:
      - fixtures/sample-a.json
      - fixtures/sample-b.json
    status: current
---

# Creates Plan
"""


class TestRunStepCreatesPostFlight:
    """Post-flight `creates:` check — the hollow-completion warning.

    Refs the BUG_BACKLOG entry "`run` advances a step whose `creates:`
    files are missing" (origin: codex-cli-backend step 1, where an
    executor permission refusal read as a completion and the step
    advanced with zero of its fixtures on disk). Advisory like the
    other post-flight warnings: the step still advances either way.
    """

    def _setup(self, tmp_path: Path) -> Path:
        (tmp_path / "foo.py").write_text("foo\n", encoding="utf-8")
        p = tmp_path / "plan.md"
        p.write_text(_CREATES_PLAN, encoding="utf-8")
        return p

    def test_warns_and_names_missing_creates(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            # Touches the declared file but creates nothing.
            (tmp_path / "foo.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Summary\nDone (hollow).\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True  # advisory: still advances
        err = capsys.readouterr().err
        assert "2 of its `creates:` entries are missing" in err
        assert "fixtures/sample-a.json" in err
        assert "fixtures/sample-b.json" in err
        assert "--mode check" in err  # remediation hint

    def test_partial_creates_names_only_the_missing_one(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            target = tmp_path / "fixtures" / "sample-a.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("{}\n", encoding="utf-8")
            return (0, "## Summary\nMade one of two.\n")

        run_step(p, repo_root=tmp_path, invoker=fake)
        err = capsys.readouterr().err
        assert "1 of its `creates:` entries are missing" in err
        assert "fixtures/sample-b.json" in err
        assert "fixtures/sample-a.json" not in err.split("missing on disk")[1]

    def test_no_warning_when_all_creates_exist(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            for name in ("sample-a.json", "sample-b.json"):
                target = tmp_path / "fixtures" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("{}\n", encoding="utf-8")
            return (0, "## Summary\nMade both.\n")

        run_step(p, repo_root=tmp_path, invoker=fake)
        err = capsys.readouterr().err
        assert "`creates:` entries are missing" not in err

    def test_no_warning_in_review_mode(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Check mode never advances, so the post-flight check is moot."""
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "review prose\n")

        run_step(p, repo_root=tmp_path, mode="check", invoker=fake)
        err = capsys.readouterr().err
        assert "`creates:` entries are missing" not in err

    def test_not_advanced_step_does_not_warn(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A failed claude call never reaches the post-flight check."""
        p = self._setup(tmp_path)

        def fake(prompt: str) -> tuple[int, str]:
            return (1, "boom")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is False
        err = capsys.readouterr().err
        assert "`creates:` entries are missing" not in err


# --- post-flight mitigations: test gate, atomic-refactor, validation block --


_TEST_GATE_PLAN = """---
title: Test Gate Plan
status: in-progress
priority: medium
test_command: __TEST_COMMAND__
steps:
  - id: 1
    title: First
    files:
      - foo.py
    status: current
---

# Test Gate Plan
"""


def _gate_plan_body(
    gate_cmds: list[str], *, test_command: str | None = None
) -> str:
    """Build a single-step plan body carrying a per-step ``gate`` list.

    Mirrors ``_TEST_GATE_PLAN`` (step 1 ``current`` declaring ``foo.py``)
    but adds a ``gate:`` block, and optionally a plan-level
    ``test_command``, so the per-step gate loop can be exercised in
    isolation from (or downstream of) the ``test_command`` gate.
    """
    lines = [
        "---",
        "title: Gate Plan",
        "status: in-progress",
        "priority: medium",
    ]
    if test_command is not None:
        lines.append(f"test_command: {test_command}")
    lines += [
        "steps:",
        "  - id: 1",
        "    title: First",
        "    files:",
        "      - foo.py",
    ]
    if gate_cmds:
        lines.append("    gate:")
        lines += [f'      - "{c}"' for c in gate_cmds]
    lines += ["    status: current", "---", "", "# Gate Plan", ""]
    return "\n".join(lines)


class TestHelpers:
    def test_run_test_gate_pass(self, tmp_path: Path) -> None:
        from plan_tool.launcher import _run_test_gate

        rc, tail = _run_test_gate("echo hello", tmp_path)
        assert rc == 0
        assert "hello" in tail

    def test_run_test_gate_fail_captures_tail(self, tmp_path: Path) -> None:
        from plan_tool.launcher import _run_test_gate

        rc, tail = _run_test_gate("echo boom 1>&2; exit 3", tmp_path)
        assert rc == 3
        assert "boom" in tail

    def test_run_test_gate_strips_ansi(self, tmp_path: Path) -> None:
        from plan_tool.launcher import _run_test_gate

        rc, tail = _run_test_gate(
            r"printf '\033[31mred\033[0m\n'; exit 1", tmp_path
        )
        assert rc == 1
        assert "\x1b[" not in tail
        assert "red" in tail

    def test_has_validation_block_present(self) -> None:
        from plan_tool.launcher import _has_validation_block

        assert _has_validation_block("foo\n## Validation\n- ran X\n## Summary\nok")

    def test_has_validation_block_absent(self) -> None:
        from plan_tool.launcher import _has_validation_block

        assert not _has_validation_block("## Summary\nno validation here\n")

class TestRunStepMitigations:
    def _write_plan(self, tmp_path: Path, body: str) -> Path:
        (tmp_path / "foo.py").write_text("foo\n", encoding="utf-8")
        p = tmp_path / "plan.md"
        p.write_text(body, encoding="utf-8")
        return p

    def test_test_gate_failure_blocks_advance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        body = _TEST_GATE_PLAN.replace("__TEST_COMMAND__", "exit 5")
        p = self._write_plan(tmp_path, body)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("touched\n", encoding="utf-8")
            return (0, "## Validation\n- ran nothing (Bash denied)\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is False
        assert result.exit_code == 5
        assert result.advanced_to is None

        reloaded = parse_plan(p)
        step1 = reloaded.step_by_id(1)
        assert step1.status == StepStatus.CURRENT  # not advanced
        assert step1.status_note and "test gate failed" in step1.status_note

        err = capsys.readouterr().err
        assert "[test gate] FAILED" in err
        assert "ERROR: step 1 not advanced" in err
        # The failure names the route after a hand fix: a re-run cannot
        # advance a hand-fixed step, `--accept` can.
        assert "plan-tool run plan --step 1 --accept" in err

    def test_test_gate_pass_advances_normally(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        body = _TEST_GATE_PLAN.replace(
            "test_command: __TEST_COMMAND__", "test_command: 'true'"
        )
        p = self._write_plan(tmp_path, body)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("touched\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True
        err = capsys.readouterr().err
        assert "[test gate] passed" in err

    def test_no_test_command_skips_gate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        body = _TEST_GATE_PLAN.replace(
            "test_command: __TEST_COMMAND__\n", ""
        )
        p = self._write_plan(tmp_path, body)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("touched\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True
        err = capsys.readouterr().err
        assert "[test gate]" not in err

    def test_stale_failure_note_cleared_when_advance_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Full cycle on a single unchanged ``test_command``: the gate
        # fails the first run (writes a "test gate failed" status_note,
        # blocks advancement), then the regression is fixed and the
        # re-run passes the gate and advances the step to done. The
        # stale note must be gone — status_note is ephemeral and scoped
        # to the current status (PLAN_FORMAT).
        #
        # The gate is ``test -f pass.flag`` so the same command flips
        # outcome based on a sentinel the (simulated) fix lands, rather
        # than rewriting the plan between runs.
        body = _TEST_GATE_PLAN.replace("__TEST_COMMAND__", "test -f pass.flag")
        p = self._write_plan(tmp_path, body)

        def fake_failing(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("attempt 1\n", encoding="utf-8")
            return (0, "## Validation\n- ran nothing\n## Summary\nwip\n")

        first = run_step(p, repo_root=tmp_path, invoker=fake_failing)
        assert first.done is False
        assert first.advanced_to is None

        stuck = parse_plan(p).step_by_id(1)
        assert stuck.status == StepStatus.CURRENT
        assert stuck.status_note and "test gate failed" in stuck.status_note

        def fake_fixed(prompt: str) -> tuple[int, str]:
            # The fix that makes the gate pass on the re-run.
            (tmp_path / "foo.py").write_text("attempt 2\n", encoding="utf-8")
            (tmp_path / "pass.flag").write_text("ok\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nfixed\n")

        second = run_step(p, repo_root=tmp_path, invoker=fake_fixed)
        assert second.done is True

        advanced = parse_plan(p).step_by_id(1)
        assert advanced.status == StepStatus.DONE
        assert advanced.status_note is None

    def test_validation_block_missing_warns(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        body = _TEST_GATE_PLAN.replace(
            "test_command: __TEST_COMMAND__\n", ""
        )
        p = self._write_plan(tmp_path, body)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("touched\n", encoding="utf-8")
            return (0, "## Summary\nno validation section\n")

        run_step(p, repo_root=tmp_path, invoker=fake)
        err = capsys.readouterr().err
        assert "no `## Validation` section" in err

    # --- per-step `gate` runner ------------------------------------------

    def _ok_fake(self, tmp_path: Path):
        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("touched\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        return fake

    def test_gate_pass_advances_normally(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._write_plan(tmp_path, _gate_plan_body(["true"]))

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.done is True
        assert parse_plan(p).step_by_id(1).status == StepStatus.DONE
        assert "[gate] passed" in capsys.readouterr().err

    def test_no_gate_field_skips_gate_runner(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._write_plan(tmp_path, _gate_plan_body([]))

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.done is True
        assert "[gate]" not in capsys.readouterr().err

    def test_gate_failure_blocks_advance(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        p = self._write_plan(tmp_path, _gate_plan_body(["exit 5"]))

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.done is False
        assert result.exit_code == 5
        assert result.advanced_to is None

        step1 = parse_plan(p).step_by_id(1)
        assert step1.status == StepStatus.CURRENT  # not advanced
        assert step1.status_note and "gate failed" in step1.status_note
        assert "exit 5" in step1.status_note  # names the failing command

        err = capsys.readouterr().err
        assert "[gate] FAILED" in err
        assert "--step 1 --accept" in err
        assert "ERROR: step 1 not advanced" in err

    def test_gate_first_failure_short_circuits(
        self, tmp_path: Path
    ) -> None:
        # The second command fails; the third must never run.
        p = self._write_plan(
            tmp_path, _gate_plan_body(["true", "exit 7", "touch ran3"])
        )

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.exit_code == 7
        step1 = parse_plan(p).step_by_id(1)
        assert step1.status_note and "exit 7" in step1.status_note
        assert not (tmp_path / "ran3").exists()  # third command skipped

    def test_gate_runs_only_after_test_command_passes(
        self, tmp_path: Path
    ) -> None:
        # A failing test_command must short-circuit before the gate loop,
        # so the gate's side-effecting command never runs.
        p = self._write_plan(
            tmp_path,
            _gate_plan_body(["touch sentinel"], test_command="'false'"),
        )

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.done is False
        assert not (tmp_path / "sentinel").exists()

    def test_gate_runs_in_repo_root(
        self, tmp_path: Path
    ) -> None:
        # The marker lives in repo_root; the gate passing proves cwd.
        (tmp_path / "marker").write_text("x\n", encoding="utf-8")
        p = self._write_plan(tmp_path, _gate_plan_body(["test -f marker"]))

        result = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert result.done is True

    def test_stale_gate_note_cleared_when_advance_succeeds(
        self, tmp_path: Path
    ) -> None:
        # Same unchanged gate command flips outcome on a sentinel the
        # (simulated) fix lands; the stale gate-fail note must clear.
        p = self._write_plan(
            tmp_path, _gate_plan_body(["test -f pass.flag"])
        )

        first = run_step(p, repo_root=tmp_path, invoker=self._ok_fake(tmp_path))
        assert first.done is False
        stuck = parse_plan(p).step_by_id(1)
        assert stuck.status == StepStatus.CURRENT
        assert stuck.status_note and "gate failed" in stuck.status_note

        def fake_fixed(prompt: str) -> tuple[int, str]:
            (tmp_path / "foo.py").write_text("attempt 2\n", encoding="utf-8")
            (tmp_path / "pass.flag").write_text("ok\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nfixed\n")

        second = run_step(p, repo_root=tmp_path, invoker=fake_fixed)
        assert second.done is True
        advanced = parse_plan(p).step_by_id(1)
        assert advanced.status == StepStatus.DONE
        assert advanced.status_note is None


# --- test-authoring gate (enforce_step_tests) ------------------------------


def _git_init(repo: Path) -> None:
    import subprocess

    for args in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(args, cwd=repo, check=True, capture_output=True)


_GATE_PLAN = """---
title: Test Authoring Gate Plan
status: in-progress
__ENFORCE__priority: medium
steps:
  - id: 1
    title: First
    files:
      - src.py
    change_type: __CHANGE_TYPE__
__OVERRIDE__    status: current
---

# Test Authoring Gate Plan
"""


def _gate_plan_path(
    tmp_path: Path,
    change_type: str,
    *,
    enforce: bool,
    step_override: Optional[bool] = None,
) -> Path:
    enforce_line = "enforce_step_tests: true\n" if enforce else ""
    override_line = (
        f"    enforce_test_authoring: {str(step_override).lower()}\n"
        if step_override is not None
        else ""
    )
    body = (
        _GATE_PLAN.replace("__ENFORCE__", enforce_line)
        .replace("__CHANGE_TYPE__", change_type)
        .replace("__OVERRIDE__", override_line)
    )
    (tmp_path / "src.py").write_text("src\n", encoding="utf-8")
    p = tmp_path / "plan.md"
    p.write_text(body, encoding="utf-8")
    return p


class TestTestAuthoringGate:
    def test_git_changed_paths_lists_untracked_and_modified(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import _git_changed_paths

        _git_init(tmp_path)
        (tmp_path / "a.py").write_text("a\n", encoding="utf-8")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("t\n", encoding="utf-8")
        assert _git_changed_paths(tmp_path) == {"a.py", "tests/test_a.py"}

    def test_git_changed_paths_empty_outside_git(self, tmp_path: Path) -> None:
        from plan_tool.launcher import _git_changed_paths

        # No git metadata means no authorship evidence, not an exemption.
        assert _git_changed_paths(tmp_path) == set()

    def test_non_git_tree_cannot_certify_authorship_even_with_new_test_file(self, tmp_path):
        p = _gate_plan_path(tmp_path, "feature", enforce=True)

        def fake(prompt):
            (tmp_path / "src.py").write_text("changed\n")
            (tmp_path / "test_src.py").write_text("def test_ok(): assert True\n")
            return 0, "## Validation\n- ok\n## Summary\nok\n"

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert not result.done
        assert result.exit_code == 1
        assert "test-authoring gate failed" in parse_plan(p).step_by_id(1).status_note

    def test_git_changed_paths_handles_spaces(self, tmp_path: Path) -> None:
        """A path with a space comes through verbatim under ``-z`` (no quoting),
        so the test-path matcher sees the real name."""
        from plan_tool.launcher import _git_changed_paths

        _git_init(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test a b.py").write_text("t\n", encoding="utf-8")
        assert _git_changed_paths(tmp_path) == {"tests/test a b.py"}

    def test_git_changed_paths_rename_credits_destination(
        self, tmp_path: Path
    ) -> None:
        """A staged rename credits the destination and never leaks the origin
        path as its own entry (the extra ``-z`` field is consumed)."""
        import subprocess

        from plan_tool.launcher import _git_changed_paths

        _git_init(tmp_path)
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_a.py").write_text("t\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", "-A"], cwd=tmp_path, check=True, capture_output=True
        )
        subprocess.run(
            ["git", "commit", "-qm", "seed"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "mv", "tests/test_a.py", "tests/test_b.py"],
            cwd=tmp_path,
            check=True,
            capture_output=True,
        )
        changed = _git_changed_paths(tmp_path)
        assert "tests/test_b.py" in changed
        assert "tests/test_a.py" not in changed

    def test_requires_authoring_only_for_feature_refactor_when_on(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import _step_requires_test_authoring

        for ct in ("feature", "refactor"):
            plan = parse_plan_text(
                _GATE_PLAN.replace("__ENFORCE__", "enforce_step_tests: true\n")
                .replace("__CHANGE_TYPE__", ct)
                .replace("__OVERRIDE__", "")
            )
            assert _step_requires_test_authoring(plan, plan.step_by_id(1))
        # non-code never gated, even with the switch on
        plan = parse_plan_text(
            _GATE_PLAN.replace("__ENFORCE__", "enforce_step_tests: true\n")
            .replace("__CHANGE_TYPE__", "non-code")
            .replace("__OVERRIDE__", "")
        )
        assert not _step_requires_test_authoring(plan, plan.step_by_id(1))

    def test_requires_authoring_off_without_switch(self, tmp_path: Path) -> None:
        from plan_tool.launcher import _step_requires_test_authoring

        plan = parse_plan_text(
            _GATE_PLAN.replace("__ENFORCE__", "")
            .replace("__CHANGE_TYPE__", "feature")
            .replace("__OVERRIDE__", "")
        )
        assert not _step_requires_test_authoring(plan, plan.step_by_id(1))

    @pytest.mark.parametrize("change_type", ["feature", "refactor"])
    def test_blocks_advance_when_no_test_authored(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], change_type: str
    ) -> None:
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, change_type, enforce=True)

        def fake(prompt: str) -> tuple[int, str]:
            # Touches only production code — no test file.
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is False
        assert result.exit_code == 1
        assert result.advanced_to is None

        stuck = parse_plan(p).step_by_id(1)
        assert stuck.status == StepStatus.CURRENT
        assert stuck.status_note and "test-authoring gate failed" in stuck.status_note

        err = capsys.readouterr().err
        assert "[test-authoring gate] FAILED" in err
        assert "--accept" in err

    @pytest.mark.parametrize("change_type", ["feature", "refactor"])
    def test_advances_when_test_authored(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], change_type: str
    ) -> None:
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, change_type, enforce=True)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            (tmp_path / "tests").mkdir(exist_ok=True)
            (tmp_path / "tests" / "test_src.py").write_text(
                "def test_x():\n    assert True\n", encoding="utf-8"
            )
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True
        err = capsys.readouterr().err
        assert "[test-authoring gate] passed" in err
        assert "tests/test_src.py" in err

    @pytest.mark.parametrize("dirty", ["clean", "unstaged", "staged", "untracked"])
    @pytest.mark.parametrize("action", ["commit-test", "commit-production", "commit-delete", "uncommitted-test"])
    def test_committed_test_evidence_keeps_pre_call_dirty_paths_excluded(
        self, tmp_path, dirty, action
    ):
        import subprocess

        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=True)
        test = tmp_path / "tests" / "test_src.py"
        test.parent.mkdir()
        if dirty != "untracked":
            test.write_text("original\n")
        _git_commit_all(tmp_path, "baseline")
        if dirty != "clean":
            test.write_text("pre-call edit\n")
        if dirty == "staged":
            subprocess.run(["git", "add", "tests/test_src.py"], cwd=tmp_path, check=True)

        def fake(prompt):
            (tmp_path / "src.py").write_text("changed\n")
            if action in {"commit-test", "uncommitted-test"}:
                test.write_text("new test content\n")
            elif action == "commit-delete" and test.exists():
                test.unlink()
            if action != "uncommitted-test":
                _git_commit_all(tmp_path, "backend changes")
            return 0, "## Validation\n- ok\n## Summary\nok\n"

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        expected = dirty == "clean" and action in {"commit-test", "uncommitted-test"}
        assert result.done is expected
        assert result.exit_code == (0 if expected else 1)

    @pytest.mark.parametrize("change_type", ["feature", "refactor"])
    def test_new_test_committed_before_a_later_commit_still_satisfies_gate(
        self, tmp_path, change_type
    ):
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, change_type, enforce=True)
        _git_commit_all(tmp_path, "baseline")

        def fake(prompt):
            test = tmp_path / "tests" / "test spaced name.py"
            test.parent.mkdir()
            test.write_text("def test_ok(): assert True\n")
            _git_commit_all(tmp_path, "backend authors test")
            (tmp_path / "src.py").write_text("changed\n")
            _git_commit_all(tmp_path, "backend changes source")
            return 0, "## Validation\n- ok\n## Summary\nok\n"

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done
        assert result.exit_code == 0

    def test_checkout_of_existing_test_history_does_not_certify_new_authorship(self, tmp_path):
        import subprocess

        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=True)
        _git_commit_all(tmp_path, "baseline")
        before = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
        (tmp_path / "src.py").write_text("unrelated source\n")
        (tmp_path / "test_old.py").write_text("def test_old(): assert True\n")
        _git_commit_all(tmp_path, "existing unrelated work")
        old_work = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True).strip()
        subprocess.run(["git", "checkout", "--detach", before], cwd=tmp_path, check=True, capture_output=True)
        # Make the pre-call commit diverge from the already-authored test history.
        (tmp_path / "README.md").write_text("current branch\n")
        _git_commit_all(tmp_path, "current branch")

        def fake(prompt):
            subprocess.run(["git", "checkout", "--detach", old_work], cwd=tmp_path, check=True, capture_output=True)
            return 0, "## Validation\n- ok\n## Summary\nok\n"

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert not result.done
        assert result.exit_code == 1
        assert "test-authoring gate failed" in parse_plan(p).step_by_id(1).status_note

    def test_advances_with_root_conftest(self, tmp_path: Path) -> None:
        """A `conftest.py` at the repo root satisfies the gate (the matcher
        recognizes it, not just `tests/` paths)."""
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=True)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            (tmp_path / "conftest.py").write_text(
                "import pytest\n", encoding="utf-8"
            )
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True

    def test_advances_with_colocated_ts_test(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A colocated Vitest/Jest test beside its source satisfies the gate.

        TS/JS projects put no `tests/` tree above the file and use no
        `test_*.py` basename, so a Python-only matcher blocks a step that
        did author a test.
        """
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=True)
        svc = tmp_path / "apps" / "mobile" / "services"
        svc.mkdir(parents=True)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("edited\n", encoding="utf-8")
            (svc / "app-restart.ts").write_text("export {}\n", encoding="utf-8")
            (svc / "app-restart.test.ts").write_text(
                "it('works', () => {})\n", encoding="utf-8"
            )
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True
        err = capsys.readouterr().err
        assert "[test-authoring gate] passed" in err
        # The production sibling must not be counted as the test file.
        assert "apps/mobile/services/app-restart.test.ts" in err

    def test_skipped_when_switch_off(self, tmp_path: Path) -> None:
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "feature", enforce=False)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        # Legacy plan (switch absent): feature step with no test still advances.
        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True

    def test_skipped_for_non_code_step(self, tmp_path: Path) -> None:
        _git_init(tmp_path)
        p = _gate_plan_path(tmp_path, "non-code", enforce=True)

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True

    def test_step_override_false_exempts(self, tmp_path: Path) -> None:
        """A per-step `enforce_test_authoring: false` exempts that step even in
        an opted-in plan — a feature step with no test still advances."""
        _git_init(tmp_path)
        p = _gate_plan_path(
            tmp_path, "feature", enforce=True, step_override=False
        )

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True

    def test_step_override_true_forces_gate_in_off_plan(
        self, tmp_path: Path
    ) -> None:
        """A per-step `enforce_test_authoring: true` gates the step even when
        the plan default is off (legacy plan)."""
        _git_init(tmp_path)
        p = _gate_plan_path(
            tmp_path, "feature", enforce=False, step_override=True
        )

        def fake(prompt: str) -> tuple[int, str]:
            (tmp_path / "src.py").write_text("changed\n", encoding="utf-8")
            return (0, "## Validation\n- ok\n## Summary\nok\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is False
        assert result.exit_code == 1


# --- review-mode findings summarization ------------------------------------


from plan_tool.launcher import (
    FindingsSummary,
    format_findings_verdict,
    summarize_findings,
)


class TestSummarizeFindings:
    def test_no_block_marks_unparsed(self) -> None:
        s = summarize_findings("just a regular review with no findings block")
        assert s.parsed is False
        assert s.critical == 0
        assert s.total == 0

    def test_empty_block_with_none_marker(self) -> None:
        out = "## Findings\n\n_(none)_\n"
        s = summarize_findings(out)
        assert s.parsed is True
        assert s.critical == 0
        assert s.counts == {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "NIT": 0}

    def test_counts_each_severity(self) -> None:
        out = (
            "review prose…\n\n"
            "## Findings\n\n"
            "- CRITICAL: bug at foo.py:10\n"
            "- HIGH: missing validation\n"
            "- MEDIUM: dead code\n"
            "- NIT: trailing whitespace\n"
        )
        s = summarize_findings(out)
        assert s.parsed is True
        assert s.counts["CRITICAL"] == 1
        assert s.counts["HIGH"] == 1
        assert s.counts["MEDIUM"] == 1
        assert s.counts["NIT"] == 1

    def test_low_folds_into_medium(self) -> None:
        out = "## Findings\n\n- LOW: cosmetic issue\n"
        s = summarize_findings(out)
        assert s.parsed is True
        assert s.counts["MEDIUM"] == 1

    def test_anchors_to_last_findings_heading(self) -> None:
        """Prompt echoes earlier in verbose output shouldn't confuse the parser."""
        out = (
            "Earlier prompt echo:\n\n"
            "## Findings\n\n"
            "- CRITICAL: bogus example from prompt\n\n"
            "Now the real review:\n\n"
            "## Findings\n\n"
            "- NIT: tiny issue\n"
        )
        s = summarize_findings(out)
        assert s.critical == 0
        assert s.counts["NIT"] == 1

    def test_unspecified_bullets_bucketed(self) -> None:
        # Unspecified bullets appearing *before* the first severity
        # bullet bucket into ``unspecified``. Bullets that fall after a
        # severity bullet are absorbed into that finding's body (so
        # ``parse_finding_bullets`` returns multi-line bodies) and do
        # not inflate the unspecified count.
        out = (
            "## Findings\n\n"
            "- not-a-token: weird formatting\n"
            "- another oddly-formatted bullet\n"
            "- CRITICAL: real one\n"
        )
        s = summarize_findings(out)
        assert s.critical == 1
        assert s.unspecified == 2

    def test_strips_ansi(self) -> None:
        out = "\x1b[0m## Findings\x1b[0m\n\n- CRITICAL: real\n"
        s = summarize_findings(out)
        assert s.critical == 1

    def test_bold_severity_token(self) -> None:
        """Markdown bolding around the severity should still parse."""
        out = "## Findings\n\n- **CRITICAL**: an issue\n"
        s = summarize_findings(out)
        assert s.critical == 1

    def test_summarize_does_not_count_decision_block_rows_as_unspecified(
        self,
    ) -> None:
        """A Decision sub-block under a severity bullet must not inflate
        the unspecified bucket: each ``- **Intent**: ...`` row lives in
        the parent finding's body, not the head-of-block freestanding
        area."""
        out = (
            "## Findings\n\n"
            "- CRITICAL: missing acceptance criterion\n\n"
            "## Decision\n\n"
            "- **Intent**: step claims X is implemented\n"
            "- **Code state**: X is not implemented\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: status-flip\n"
        )
        s = summarize_findings(out)
        assert s.parsed is True
        assert s.critical == 1
        assert s.unspecified == 0

    def test_summarize_counts_three_severity_bullets_with_decision_blocks(
        self,
    ) -> None:
        out = (
            "## Findings\n\n"
            "- CRITICAL: first\n\n"
            "## Decision\n\n"
            "- **Intent**: i1\n"
            "- **Code state**: c1\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: path-rename\n\n"
            "- HIGH: second\n\n"
            "## Decision\n\n"
            "- **Intent**: i2\n"
            "- **Code state**: c2\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-code\n"
            "- **Justification**: missing-impl\n\n"
            "- MEDIUM: third\n\n"
            "## Decision\n\n"
            "- **Intent**: i3\n"
            "- **Code state**: c3\n"
            "- **Fulfills intent?**: partial\n"
            "- **Direction**: no-op\n"
            "- **Justification**: cosmetic\n"
        )
        s = summarize_findings(out)
        total_severity = (
            s.counts.get("CRITICAL", 0)
            + s.counts.get("HIGH", 0)
            + s.counts.get("MEDIUM", 0)
        )
        assert total_severity == 3
        assert s.unspecified == 0


from plan_tool.launcher import parse_finding_bullets, FindingBullet, findings_output_is_valid


class TestFindingsOutputIsValid:
    def test_accepts_explicit_clean_sentinel(self) -> None:
        assert findings_output_is_valid("## Findings\n\n_(none)_\n")

    def test_accepts_severity_labelled_findings(self) -> None:
        assert findings_output_is_valid("## Findings\n\n- HIGH: missing guard\n")

    def test_rejects_missing_empty_or_unspecified_findings(self) -> None:
        assert not findings_output_is_valid("no findings section")
        assert not findings_output_is_valid("## Findings\n")
        assert not findings_output_is_valid("## Findings\n\n- missing severity\n")


class TestParseFindingBullets:
    def test_bullet_body_includes_trailing_decision_block(self) -> None:
        out = (
            "## Findings\n\n"
            "- CRITICAL: missing acceptance criterion\n\n"
            "## Decision\n\n"
            "- **Intent**: step claims X\n"
            "- **Code state**: X missing\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: status-flip\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 1
        assert bullets[0].severity == "CRITICAL"
        assert "## Decision" in bullets[0].body
        assert "Justification" in bullets[0].body

    def test_three_bullets_with_decision_blocks_yield_three_findingbullets(
        self,
    ) -> None:
        out = (
            "## Findings\n\n"
            "- CRITICAL: first\n\n"
            "## Decision\n\n"
            "- **Intent**: i1\n"
            "- **Code state**: c1\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: path-rename\n\n"
            "- HIGH: second\n\n"
            "## Decision\n\n"
            "- **Intent**: i2\n"
            "- **Code state**: c2\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-code\n"
            "- **Justification**: missing-impl\n\n"
            "- MEDIUM: third\n\n"
            "## Decision\n\n"
            "- **Intent**: i3\n"
            "- **Code state**: c3\n"
            "- **Fulfills intent?**: partial\n"
            "- **Direction**: no-op\n"
            "- **Justification**: cosmetic\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 3
        assert [b.severity for b in bullets] == ["CRITICAL", "HIGH", "MEDIUM"]
        # Each bullet's body retains its own Decision block.
        for bullet in bullets:
            assert "## Decision" in bullet.body

    def test_freestanding_bullet_before_severity_still_counts_as_unspecified(
        self,
    ) -> None:
        out = (
            "## Findings\n\n"
            "- some prose note\n"
            "- CRITICAL: real one\n"
        )
        bullets = parse_finding_bullets(out)
        # CRITICAL plus one unspecified head bullet.
        assert len(bullets) == 2
        sevs = {b.severity for b in bullets}
        assert "CRITICAL" in sevs
        assert "UNSPECIFIED" in sevs

    def test_misshape_after_well_formed_is_minted_not_absorbed(self) -> None:
        """``- HIGH `[b]`: …`` after a good bullet must be its own finding."""
        out = (
            "## Findings\n\n"
            "- HIGH: real finding one "
            "(impact: high, complexity: low)\n"
            "- HIGH `[b]`: misshaped second "
            "(impact: high, complexity: low)\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 2
        assert [b.severity for b in bullets] == ["HIGH", "HIGH"]
        assert bullets[0].body.startswith("real finding one")
        assert "misshaped second" not in bullets[0].body
        assert "[b]" in bullets[1].body
        assert "misshaped second" in bullets[1].body

    def test_misshape_without_space_before_bracket_is_minted(self) -> None:
        """``- HIGH`[b]`:`` (no space) is still a misshape boundary."""
        out = (
            "## Findings\n\n"
            "- HIGH: first "
            "(impact: high, complexity: low)\n"
            "- HIGH`[b]`: no-space misshape "
            "(impact: high, complexity: low)\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 2
        assert bullets[1].severity == "HIGH"
        assert "no-space misshape" in bullets[1].body
        assert "no-space misshape" not in bullets[0].body

    def test_decision_block_rows_are_not_finding_shaped_misshapes(self) -> None:
        """``- **Intent**:`` under Decision stays inside the parent body."""
        out = (
            "## Findings\n\n"
            "- CRITICAL: missing acceptance criterion\n\n"
            "## Decision\n\n"
            "- **Intent**: step claims X\n"
            "- **Code state**: X missing\n"
            "- **Fulfills intent?**: no\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: status-flip\n"
        )
        bullets = parse_finding_bullets(out)
        assert len(bullets) == 1
        assert "## Decision" in bullets[0].body
        assert "**Intent**" in bullets[0].body


class TestFormatFindingsVerdict:
    def test_includes_all_buckets(self) -> None:
        s = FindingsSummary(
            parsed=True,
            counts={"CRITICAL": 1, "HIGH": 0, "MEDIUM": 2, "NIT": 0},
            unspecified=0,
        )
        v = format_findings_verdict(3, s)
        assert "Step 3" in v
        assert "1 critical" in v
        assert "2 medium" in v

    def test_unparsed_marks_could_not_summarize(self) -> None:
        s = FindingsSummary(parsed=False, counts={}, unspecified=0)
        v = format_findings_verdict(1, s)
        assert "could not summarize" in v

    def test_unspecified_appended_when_present(self) -> None:
        s = FindingsSummary(
            parsed=True,
            counts={"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "NIT": 0},
            unspecified=2,
        )
        v = format_findings_verdict(1, s)
        assert "2 unspecified" in v


class TestCmdRunReviewModeExitCode:
    def _setup(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        plan = tmp_path / "plan.md"
        plan.write_text(_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["plan.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)
        return manifest

    def test_critical_finding_still_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        original = cli_module.run_step

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (
                0,
                "review prose\n\n## Findings\n\n- CRITICAL: bad\n",
            )
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "run", "plan",
                "--mode", "check",
            ]
        )
        # The audit completed -- exit 0; the critical finding is in the
        # report, not the exit code.
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 critical" in out

    def test_no_findings_block_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        original = cli_module.run_step

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "review without a findings block")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "run", "plan",
                "--mode", "check",
            ]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "could not summarize" in out

    def test_only_nits_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path, monkeypatch)
        original = cli_module.run_step

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (
                0, "## Findings\n\n- NIT: small thing\n"
            )
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.run_cmd.run_step", patched)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "run", "plan",
                "--mode", "check",
            ]
        )
        assert rc == 0


class TestCmdReviewAllExitCode:
    def test_failed_step_output_is_bounded(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["all_done.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        failure_output = "omitted failure prefix\n" + ("x" * 2_100) + "\nvisible tail"
        original = cli_module.run_all_done_steps
        responses = iter([
            (1, failure_output),
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n_(none)_\n"),
        ])

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda _prompt: next(responses)
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.run_all_done_steps", patched)
        monkeypatch.chdir(tmp_path)

        assert cli_module.main(
            [
                "--manifest", str(manifest), "reconcile-all", "all_done",
                "--mode", "check",
            ]
        ) == 0

        out = capsys.readouterr().out
        assert "failure output truncated to last 2000 characters" in out
        assert "omitted failure prefix" not in out
        assert "visible tail" in out

    def test_critical_in_any_step_still_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["all_done.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        original = cli_module.run_all_done_steps
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n- CRITICAL: bad\n"),
            (0, "## Findings\n\n- NIT: tiny\n"),
        ])

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: next(responses)
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.run_all_done_steps", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "reconcile-all", "all_done",
                "--mode", "check",
            ]
        )
        # Completed review exits 0; the critical finding shows up in the
        # per-step verdicts, not the exit code.
        assert rc == 0
        out = capsys.readouterr().out
        assert "findings verdicts" in out
        assert "1 critical" in out

    def test_fail_on_findings_gates_on_critical(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fail-on-findings makes a critical finding in any step exit
        non-zero for CI."""
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["all_done.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        original = cli_module.run_all_done_steps
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n- CRITICAL: bad\n"),
            (0, "## Findings\n\n- NIT: tiny\n"),
        ])

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: next(responses)
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.run_all_done_steps", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "reconcile-all", "all_done",
                "--mode", "check", "--fail-on-findings",
            ]
        )
        assert rc == 1
        out = capsys.readouterr().out
        assert "1 critical" in out

    def test_all_clean_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from plan_tool.cli import app as cli_module

        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["all_done.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()

        original = cli_module.run_all_done_steps

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "## Findings\n\n_(none)_\n")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.run_all_done_steps", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            [
                "--manifest", str(manifest), "reconcile-all", "all_done",
                "--mode", "check",
            ]
        )
        assert rc == 0


# --- verify subcommand (Step 7) -------------------------------------------


from plan_tool.launcher import verify_plan, VerifyVerdict


class TestVerifyPlan:
    @pytest.fixture()
    def all_done_path(self, tmp_path: Path) -> Path:
        p = tmp_path / "all_done.md"
        p.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        return p

    def test_all_pass_when_no_critical(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "## Findings\n\n_(none)_\n"),
        )
        assert len(verdicts) == 3
        assert all(v.passed for v in verdicts)
        assert all(v.status == "pass" for v in verdicts)

    def test_critical_marks_fail(self, all_done_path: Path, tmp_path: Path) -> None:
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n- CRITICAL: bug\n"),
            (0, "## Findings\n\n- NIT: tiny\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            all_done_path, repo_root=tmp_path, invoker=fake
        )
        assert verdicts[0].status == "pass"
        assert verdicts[1].status == "fail"
        # NIT-only doesn't warn — only HIGH/MEDIUM/unspecified do.
        assert verdicts[2].status == "pass"

    def test_nit_only_passes(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "## Findings\n\n- NIT: tiny\n"),
        )
        # NIT-only counts as warn (since it's a non-zero finding even if minor).
        # Actually, looking at the implementation: NIT bullets aren't HIGH or
        # MEDIUM, so the elif branch catches HIGH/MEDIUM/unspecified — NIT
        # falls through to else (pass). Verify behavior:
        assert all(v.status == "pass" for v in verdicts)

    def test_high_marks_warn(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "## Findings\n\n- HIGH: gap\n"),
        )
        assert all(v.status == "warn" for v in verdicts)
        assert all(v.passed for v in verdicts)  # warn doesn't fail

    def test_unparsed_block_marks_warn(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "no findings block at all"),
        )
        assert all(v.status == "warn" for v in verdicts)
        assert all(v.passed for v in verdicts)

    def test_nonzero_exit_marks_fail(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (3, ""),
        )
        assert all(v.status == "fail" for v in verdicts)
        assert all(not v.passed for v in verdicts)

    def test_max_steps_limits(self, all_done_path: Path, tmp_path: Path) -> None:
        verdicts = verify_plan(
            all_done_path,
            repo_root=tmp_path,
            invoker=lambda p: (0, "## Findings\n\n_(none)_\n"),
            max_steps=2,
        )
        assert len(verdicts) == 2

    def test_no_done_steps_returns_empty(self, tmp_path: Path) -> None:
        text = (
            "---\n"
            "title: All Pending\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "  - id: 2\n"
            "    title: Two\n"
            "    depends_on: [1]\n"
            "---\n"
        )
        p = tmp_path / "plan.md"
        p.write_text(text, encoding="utf-8")
        verdicts = verify_plan(
            p, repo_root=tmp_path, invoker=lambda x: (0, "")
        )
        assert verdicts == []


class TestCmdVerify:
    def _setup(self, tmp_path: Path) -> Path:
        plan = tmp_path / "all_done.md"
        plan.write_text(_ALL_DONE_PLAN, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["all_done.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        return manifest

    def test_cli_all_pass_exit_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path)
        original = cli_module.verify_plan

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "## Findings\n\n_(none)_\n")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.verify_plan", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "verify", "all_done"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "3 pass" in out
        assert "0 fail" in out

    def test_cli_critical_still_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path)
        original = cli_module.verify_plan

        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n- CRITICAL: bug\n"),
            (0, "## Findings\n\n_(none)_\n"),
        ])

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: next(responses)
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.verify_plan", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "verify", "all_done"]
        )
        # The rollup completed -- exit 0; the [FAIL] verdict is the signal,
        # carried in the report rather than the exit code.
        assert rc == 0
        out = capsys.readouterr().out
        assert "[FAIL]" in out
        assert "1 fail" in out

    def test_cli_fail_on_findings_gates_on_fail(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """--fail-on-findings makes a [FAIL] step exit non-zero for CI."""
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path)
        original = cli_module.verify_plan

        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Findings\n\n- CRITICAL: bug\n"),
            (0, "## Findings\n\n_(none)_\n"),
        ])

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: next(responses)
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.verify_plan", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "verify", "all_done",
             "--fail-on-findings"]
        )
        assert rc == 1
        out = capsys.readouterr().out
        assert "[FAIL]" in out

    def test_cli_fail_on_findings_all_pass_exits_zero(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """--fail-on-findings only flips the rc on a [FAIL]; an all-pass
        rollup still exits 0."""
        from plan_tool.cli import app as cli_module

        manifest = self._setup(tmp_path)
        original = cli_module.verify_plan

        def patched(path, **kwargs):
            kwargs["invoker"] = lambda p: (0, "## Findings\n\n_(none)_\n")
            return original(path, **kwargs)

        monkeypatch.setattr("plan_tool.cli.review_cmd.verify_plan", patched)
        monkeypatch.chdir(tmp_path)
        rc = cli_module.main(
            ["--manifest", str(manifest), "verify", "all_done",
             "--fail-on-findings"]
        )
        assert rc == 0

    def test_cli_no_done_steps_prints_nothing_to_verify(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from plan_tool.cli import app as cli_module

        text = (
            "---\n"
            "title: Fresh\n"
            "status: planning\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: One\n"
            "---\n"
        )
        plan = tmp_path / "fresh.md"
        plan.write_text(text, encoding="utf-8")
        manifest = tmp_path / "m.json"
        manifest.write_text('{"plans": ["fresh.md"]}\n', encoding="utf-8")
        (tmp_path / ".git").mkdir()
        monkeypatch.chdir(tmp_path)

        rc = cli_module.main(
            ["--manifest", str(manifest), "verify", "fresh"]
        )
        assert rc == 0
        out = capsys.readouterr().out
        assert "nothing to verify" in out


# --- verify --deep (Step 6) ------------------------------------------------


from plan_tool.launcher import (  # noqa: E402
    BulletResult,
    parse_deep_verdict,
    read_lessons_step_ids,
)


class TestParseDeepVerdict:
    def test_extracts_pass(self) -> None:
        assert parse_deep_verdict("## Verdict\n\nPASS\n") == "PASS"

    def test_extracts_fail(self) -> None:
        assert parse_deep_verdict("prose\n\n## Verdict\n\nFAIL\n") == "FAIL"

    def test_extracts_unknown(self) -> None:
        assert parse_deep_verdict("## Verdict\n\nUNKNOWN\n") == "UNKNOWN"

    def test_anchors_on_last_heading(self) -> None:
        text = "## Verdict\n\nPASS\n\n## Verdict\n\nFAIL\n"
        assert parse_deep_verdict(text) == "FAIL"

    def test_no_heading_returns_none(self) -> None:
        assert parse_deep_verdict("just prose, no verdict") is None

    def test_unrecognized_token_returns_none(self) -> None:
        assert parse_deep_verdict("## Verdict\n\nMAYBE\n") is None


_DEEP_PLAN = """---
title: Deep Verify Plan
status: in-progress
priority: medium
steps:
  - id: 1
    title: First step
    files:
      - foo.py
    detail: details/01.md
    status: done
---

# Deep Verify Plan
"""

_DEEP_DETAIL_BODY = """# Step 1

## Why

reason

## Files

- `foo.py`

## Implementation

do thing

## Tests

test thing

## Acceptance criteria

- bullet one delivered
- bullet two delivered
- bullet three delivered
"""


def _setup_deep_plan(tmp_path: Path) -> Path:
    plan_path = tmp_path / "deep.md"
    plan_path.write_text(_DEEP_PLAN, encoding="utf-8")
    (tmp_path / "foo.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "details").mkdir()
    (tmp_path / "details" / "01.md").write_text(
        _DEEP_DETAIL_BODY, encoding="utf-8"
    )
    return plan_path


class TestVerifyDeep:
    def test_all_pass_promotes_to_pass(self, tmp_path: Path) -> None:
        plan_path = _setup_deep_plan(tmp_path)
        # First call: standard reconcile (none findings). Then 3 bullet
        # calls all return PASS. Total: 4 invocations.
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Verdict\n\nPASS\n"),
            (0, "## Verdict\n\nPASS\n"),
            (0, "## Verdict\n\nPASS\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        assert len(verdicts) == 1
        v = verdicts[0]
        assert v.status == "pass"
        assert v.passed is True
        assert len(v.bullet_results) == 3
        assert all(br.verdict == "PASS" for br in v.bullet_results)

    def test_any_fail_promotes_to_fail(self, tmp_path: Path) -> None:
        plan_path = _setup_deep_plan(tmp_path)
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),  # reconcile
            (0, "## Verdict\n\nPASS\n"),
            (0, "## Verdict\n\nFAIL\n"),
            (0, "## Verdict\n\nPASS\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        v = verdicts[0]
        assert v.status == "fail"
        assert v.passed is False
        verdict_tokens = [br.verdict for br in v.bullet_results]
        assert verdict_tokens == ["PASS", "FAIL", "PASS"]

    def test_mixed_pass_unknown_promotes_to_warn(self, tmp_path: Path) -> None:
        plan_path = _setup_deep_plan(tmp_path)
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Verdict\n\nPASS\n"),
            (0, "## Verdict\n\nUNKNOWN\n"),
            (0, "## Verdict\n\nPASS\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        v = verdicts[0]
        assert v.status == "warn"
        assert v.passed is True

    def test_no_acceptance_section_falls_back_to_reconcile(
        self, tmp_path: Path
    ) -> None:
        plan_path = tmp_path / "deep.md"
        plan_path.write_text(_DEEP_PLAN, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "details").mkdir()
        # Detail file with no Acceptance section.
        (tmp_path / "details" / "01.md").write_text(
            "# Step 1\n\n## Why\n\nx\n\n## Files\n\nfoo.py\n",
            encoding="utf-8",
        )
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        v = verdicts[0]
        # Reconcile said no critical → pass; deep skipped → no override.
        assert v.status == "pass"
        assert v.bullet_results == ()

    def test_deep_reconcile_still_falls_back_on_a_missing_detail_file(
        self, tmp_path: Path
    ) -> None:
        """A done step whose detail pointer is set but the file is gone on
        disk still falls back to the reconcile-derived verdict — the
        existing soft-fallback behavior, distinct from the hard refusal a
        present-but-unsupported body now gets below."""
        plan_path = tmp_path / "deep.md"
        plan_path.write_text(_DEEP_PLAN, encoding="utf-8")
        (tmp_path / "foo.py").write_text("x = 1\n", encoding="utf-8")
        # No `details/01.md` written at all.
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        v = verdicts[0]
        assert v.status == "pass"
        assert v.bullet_results == ()

    def test_deep_reconcile_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        """Exercised directly against ``_run_deep_for_step`` (not through
        ``verify_plan``): the earlier ``detail-reconcile`` prompt render
        reads the same on-disk body and would refuse first via
        ``renderer.py``'s own gate, so driving this end to end could never
        isolate this function's own refusal from that upstream one."""
        from plan_tool.detail_artifacts import render_detail_format_version_marker
        from plan_tool.launcher import _run_deep_for_step

        plan_path = _setup_deep_plan(tmp_path)
        (tmp_path / "details" / "01.md").write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\n"
            "## Acceptance criteria\n\n- bullet one delivered\n",
            encoding="utf-8",
        )

        with pytest.raises(LauncherError):
            _run_deep_for_step(
                plan_path,
                step_id=1,
                repo_root=tmp_path,
                invoker=lambda _prompt: (0, "## Verdict\nPASS\n"),
                reporter=None,
            )

    def test_contract_miss_treated_as_unknown(self, tmp_path: Path) -> None:
        plan_path = _setup_deep_plan(tmp_path)
        responses = iter([
            (0, "## Findings\n\n_(none)_\n"),
            (0, "## Verdict\n\nPASS\n"),
            (0, "no verdict heading at all"),  # contract miss → UNKNOWN
            (0, "## Verdict\n\nPASS\n"),
        ])

        def fake(prompt: str) -> tuple[int, str]:
            return next(responses)

        verdicts = verify_plan(
            plan_path, repo_root=tmp_path, invoker=fake, deep=True
        )
        v = verdicts[0]
        assert v.status == "warn"
        verdict_tokens = [br.verdict for br in v.bullet_results]
        assert verdict_tokens == ["PASS", "UNKNOWN", "PASS"]


# --- read_lessons_step_ids (Step 5 helper) ---------------------------------


class TestReadLessonsStepIds:
    def test_picks_up_canonical_format(self, tmp_path: Path) -> None:
        f = tmp_path / "log.md"
        f.write_text(
            "- 2026-05-05T00:00:00Z step 1: thing\n"
            "- 2026-05-06T00:00:00Z step 3: another\n",
            encoding="utf-8",
        )
        assert read_lessons_step_ids(f) == {1, 3}

    def test_loose_match_on_hand_edits(self, tmp_path: Path) -> None:
        f = tmp_path / "log.md"
        f.write_text(
            "Notes from yesterday: step 5: fixed thing\n",
            encoding="utf-8",
        )
        assert read_lessons_step_ids(f) == {5}

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert read_lessons_step_ids(tmp_path / "nope.md") == set()


# --- apply_finding ---------------------------------------------------------


_APPLY_PLAN = """---
title: Apply Test
status: in-progress
priority: low
steps:
  - id: 1
    title: Build the thing
    files: [foo.py]
    status: done
---
"""


def _write_plan_for_apply(tmp_path: Path) -> Path:
    plan_path = tmp_path / "plan.md"
    plan_path.write_text(_APPLY_PLAN, encoding="utf-8")
    (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
    return plan_path


def _write_phrase_guardrail_plan_for_apply(tmp_path: Path) -> Path:
    detail_rel = "details/01-audit-sample-reuse.md"
    detail_path = tmp_path / detail_rel
    detail_path.parent.mkdir(parents=True)
    detail_path.write_text(
        "# Audit sample reuse guard\n\n"
        "Keep the audit sample reuse guard phrase stable. Mechanical "
        "specifics stay illustrative, e.g. callers may branch on explicit "
        "flags, but the invariant is preserving default suppression.\n",
        encoding="utf-8",
    )
    plan_path = tmp_path / "phrase-guardrail-plan.md"
    plan_path.write_text(
        "---\n"
        "title: Phrase Guardrail Apply Test\n"
        "status: in-progress\n"
        "priority: low\n"
        "features:\n"
        "  - id: audit-sample-reuse\n"
        "    title: Audit sample reuse guard\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Preserve audit sample reuse guard\n"
        "    files: [foo.py]\n"
        "    features:\n"
        "      - audit-sample-reuse\n"
        f"    detail: {detail_rel}\n"
        "---\n\n"
        "## Overview\n\n"
        "The audit sample reuse guard is the recurring concept phrase.\n",
        encoding="utf-8",
    )
    (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
    return plan_path


class TestParseApplyVerdict:
    def test_extracts_applied(self) -> None:
        from plan_tool.launcher import parse_apply_verdict

        stdout = (
            "## Summary\n- did the thing\n\n"
            "## Verdict\nAPPLIED\n"
        )
        assert parse_apply_verdict(stdout) == "APPLIED"

    def test_extracts_blocked(self) -> None:
        from plan_tool.launcher import parse_apply_verdict

        stdout = "blah blah\n## Verdict\nBLOCKED — would create file\n"
        assert parse_apply_verdict(stdout) == "BLOCKED"

    def test_extracts_not_applicable(self) -> None:
        from plan_tool.launcher import parse_apply_verdict

        stdout = "## Verdict\nNOT-APPLICABLE\n"
        assert parse_apply_verdict(stdout) == "NOT-APPLICABLE"

    def test_returns_none_when_missing(self) -> None:
        from plan_tool.launcher import parse_apply_verdict

        assert parse_apply_verdict("just prose with no verdict") is None

    def test_anchors_on_last_verdict_block(self) -> None:
        """When the prompt is echoed in --verbose, the prompt's example
        ``## Verdict APPLIED`` must NOT win over the real one."""
        from plan_tool.launcher import parse_apply_verdict

        stdout = (
            "[verbose echo of prompt]\n"
            "Example output:\n## Verdict\nAPPLIED\n"
            "[end echo]\n\n"
            "[real response]\n## Verdict\nBLOCKED\n"
        )
        assert parse_apply_verdict(stdout) == "BLOCKED"

    def test_extracts_blocked_structural(self) -> None:
        from plan_tool.launcher import parse_apply_verdict

        stdout = "## Verdict\nBLOCKED-STRUCTURAL\n"
        assert parse_apply_verdict(stdout) == "BLOCKED-STRUCTURAL"

    def test_blocked_structural_not_misparsed_as_blocked(self) -> None:
        """Ordering guard: ``BLOCKED-STRUCTURAL`` must win over the
        ``BLOCKED`` alternative, which ``\\bBLOCKED\\b`` would otherwise
        match inside it (leftmost-match collapse)."""
        from plan_tool.launcher import parse_apply_verdict

        stdout = (
            "the only fix is a split\n"
            "## Verdict\nBLOCKED-STRUCTURAL\n"
        )
        assert parse_apply_verdict(stdout) == "BLOCKED-STRUCTURAL"


class TestApplyFindingDryRun:
    def test_dry_run_returns_prompt_without_changes(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        original = plan_path.read_text(encoding="utf-8")

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="flip step 1 status to current",
            step_id=1,
            dry_run=True,
        )
        assert result.exit_code == 0
        assert result.prompt is not None
        assert "flip step 1 status to current" in result.prompt
        # No targeted fix supplied → no Targeted fix section rendered.
        assert "## Targeted fix (realize exactly this intent)" not in result.prompt
        # Plan untouched.
        assert plan_path.read_text(encoding="utf-8") == original

    def test_targeted_fix_injected_into_prompt(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            targeted_fix="flip step 1 status from done to current",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        assert "## Targeted fix (realize exactly this intent)" in result.prompt
        assert "flip step 1 status from done to current" in result.prompt

    def test_apply_prompt_includes_plan_authoring_guardrails(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body=(
                "audit sample reuse guard is renamed as saved audit policy"
            ),
            targeted_fix=(
                "reuse audit sample reuse guard or bridge saved audit policy"
            ),
            step_id=1,
            dry_run=True,
        )

        assert result.prompt is not None
        assert "## Authoring guardrails" in result.prompt
        assert "Preserve conceptual altitude" in result.prompt
        assert "durable decisions, constraints" in result.prompt
        assert "contracts, correctness rationale" in result.prompt
        assert "Demote mechanical specifics" in result.prompt
        assert "Reuse the canonical concept phrase" in result.prompt
        assert "feature IDs and `step.features` authoritative" in result.prompt
        assert "authoritative ownership thread" in result.prompt
        assert "Do not infer" in result.prompt
        assert "feature ownership from prose alone" in result.prompt
        # Shared regression fixture: the same concept phrase and demoted
        # mechanical example reach the shared finding-application prompt.
        assert "audit-sample-reuse" in result.prompt
        assert "audit sample reuse guard" in result.prompt
        assert "e.g. callers may branch on explicit flags" in result.prompt

    def test_apply_finding_prompt_marks_a_declared_detail_path_with_no_file(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        detail_rel = "details/01-step.md"
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Bare Apply Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            f"    detail: {detail_rel}\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix the design",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        assert detail_rel in result.prompt
        assert "not authored yet" in result.prompt

    def test_apply_finding_prompt_keeps_the_undeclared_literal(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix something",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        assert "(no detail file declared for this step)" in result.prompt

    def test_apply_finding_prompt_names_the_file_when_it_exists(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix something",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        assert "details/01-audit-sample-reuse.md" in result.prompt
        assert "not authored yet" not in result.prompt


class TestApplyFindingCreatedDetailFileCleanup:
    def _bare_declared_detail_plan(self, tmp_path: Path) -> tuple[Path, Path]:
        detail_rel = "details/01-step.md"
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Bare Apply Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            f"    detail: {detail_rel}\n"
            "    status: done\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        return plan_path, tmp_path / detail_rel

    def test_apply_finding_removes_a_detail_file_the_apply_created(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path, detail_path = self._bare_declared_detail_plan(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\nedit\n",
                encoding="utf-8",
            )
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail_path.write_text("# created\n", encoding="utf-8")
            return 0, "## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix design",
            step_id=1,
            invoker=fake_invoker,
            auto_fix_introduced=False,
        )
        assert result.verdict == "APPLIED"
        assert not detail_path.exists()
        assert result.removed_created_detail_files

    def test_apply_finding_removes_a_detail_file_the_autofix_followup_created(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path, detail_path = self._bare_declared_detail_plan(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8")
            + "\n## Overview\nReal description.\n",
            encoding="utf-8",
        )
        calls = 0

        def fake_invoker(prompt: str) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            current = plan_path.read_text(encoding="utf-8")
            if calls == 1:
                plan_path.write_text(
                    current.replace(
                        "## Overview\nReal description.\n",
                        "## Overview\n_(TODO)_\n",
                    ),
                    encoding="utf-8",
                )
                return 0, "## Verdict\nAPPLIED\n"
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail_path.write_text("# follow-up created\n", encoding="utf-8")
            return 0, "## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix design",
            step_id=1,
            invoker=fake_invoker,
        )
        assert calls == 2
        assert not detail_path.exists()
        assert result.removed_created_detail_files

    def test_apply_finding_created_detail_does_not_trigger_autofix(
        self, tmp_path: Path
    ) -> None:
        """Cleanup runs before the findings delta, so a created detail file
        cannot seed regressions that burn an auto-fix follow-up."""
        from plan_tool.launcher import apply_finding

        plan_path, detail_path = self._bare_declared_detail_plan(tmp_path)
        calls = 0

        def fake_invoker(prompt: str) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            plan_path.write_text(
                plan_path.read_text(encoding="utf-8") + "\nedit\n",
                encoding="utf-8",
            )
            detail_path.parent.mkdir(parents=True, exist_ok=True)
            detail_path.write_text("# created\n", encoding="utf-8")
            return 0, "## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix design",
            step_id=1,
            invoker=fake_invoker,
        )
        assert calls == 1
        assert not detail_path.exists()
        assert result.removed_created_detail_files
        assert result.introduced_findings == ()

    def test_apply_finding_keeps_edits_to_an_existing_detail_file(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        detail_path = tmp_path / "details/01-audit-sample-reuse.md"

        def fake_invoker(prompt: str) -> tuple[int, str]:
            detail_path.write_text(
                detail_path.read_text(encoding="utf-8") + "\nMore detail.\n",
                encoding="utf-8",
            )
            return 0, "## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="extend detail",
            step_id=1,
            invoker=fake_invoker,
            auto_fix_introduced=False,
        )
        assert result.verdict == "APPLIED"
        assert "More detail." in detail_path.read_text(encoding="utf-8")
        assert result.removed_created_detail_files == ()


class TestApplyFindingDryRunStructuralOption:
    def test_structural_verdict_option_gated(self, tmp_path: Path) -> None:
        """Guard (a): the ``BLOCKED-STRUCTURAL`` option appears in the
        rendered prompt only when ``allow_structural_verdict=True``. The
        default keeps it absent, so create's unedited callers never offer
        the verdict."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        off = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1, dry_run=True,
        )
        assert off.prompt is not None
        assert "BLOCKED-STRUCTURAL" not in off.prompt

        on = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1, dry_run=True,
            allow_structural_verdict=True,
        )
        assert on.prompt is not None
        assert "BLOCKED-STRUCTURAL" in on.prompt

    def test_no_operator_feedback_no_section(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="flip step 1 status to current",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        # The static "What to do" prose mentions the section name, so assert
        # on the rendered block's full heading, which only appears when
        # feedback was supplied.
        assert "## Operator feedback (authoritative" not in result.prompt

    def test_operator_feedback_injected_into_prompt(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            targeted_fix="flip step 1 status from done to current",
            operator_feedback="only edit the YAML; leave the prose note alone",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        # Feedback renders as an authoritative section, after the targeted fix.
        assert "## Operator feedback (authoritative" in result.prompt
        assert "only edit the YAML; leave the prose note alone" in result.prompt
        assert result.prompt.index("## Targeted fix") < result.prompt.index(
            "## Operator feedback"
        )

    _CARRIED_HEADING = "## Already surfaced this run"

    def test_carried_findings_default_empty_renders_no_block(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="flip step 1 status to current",
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        assert self._CARRIED_HEADING not in result.prompt
        # No unexpanded template token leaks for an empty block.
        assert "${carried_findings_block}" not in result.prompt
        assert "carried_findings_block" not in result.prompt

    def test_carried_findings_rendered_when_supplied(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)
        carried = [
            CarriedFinding(
                anchor="step-3-missing-bullet",
                title="step 3 detail missing acceptance bullet",
                severity="high",
                body_excerpt="the acceptance section omits the criterion",
            )
        ]
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=carried,
            dry_run=True,
        )
        assert result.prompt is not None
        assert self._CARRIED_HEADING in result.prompt
        assert "(HIGH) step 3 detail missing acceptance bullet" in result.prompt

    def test_carried_block_advisory_framing(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)
        carried = [
            CarriedFinding(
                anchor="a",
                title="some finding",
                severity="medium",
                body_excerpt="",
            )
        ]
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=carried,
            dry_run=True,
        )
        assert result.prompt is not None
        # Framed as context-only, not new permission.
        assert "context only" in result.prompt
        assert "does NOT widen what you may edit" in result.prompt
        # The existing scope rule is still present verbatim.
        assert "Stay inside the plan/detail surface" in result.prompt

    def test_carried_findings_resolution_token(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)

        def render(resolution: str, reason: str = "") -> str:
            carried = [
                CarriedFinding(
                    anchor="a",
                    title="t",
                    severity="high",
                    body_excerpt="",
                    resolution=resolution,
                    resolution_reason=reason,
                )
            ]
            res = apply_finding(
                plan_path,
                repo_root=tmp_path,
                finding_body="anything",
                step_id=1,
                carried_findings=carried,
                dry_run=True,
            )
            assert res.prompt is not None
            return res.prompt

        # open → bare severity, no resolution token.
        assert "- (HIGH) t" in render("open")
        # applied → severity + resolution.
        assert "- (HIGH, applied) t" in render("applied")
        # blocked with a reason → severity, resolution, reason.
        assert "- (HIGH, blocked: needs a new file) t" in render(
            "blocked", "needs a new file"
        )
        # skipped likewise.
        assert "- (HIGH, skipped) t" in render("skipped")

    def test_carried_findings_excerpt_line(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)

        with_excerpt = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=[
                CarriedFinding(
                    anchor="a",
                    title="t",
                    severity="high",
                    body_excerpt="the excerpt text",
                    confidence=None,
                )
            ],
            dry_run=True,
        )
        assert with_excerpt.prompt is not None
        assert "confidence: unknown" in with_excerpt.prompt
        assert "  the excerpt text" in with_excerpt.prompt

        without = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=[
                CarriedFinding(
                    anchor="a", title="t", severity="high", body_excerpt=""
                )
            ],
            dry_run=True,
        )
        assert without.prompt is not None
        # No indented continuation line follows the bullet when the
        # excerpt is empty.
        assert "- (HIGH) t [confidence: unknown]\n  " not in without.prompt

    def test_carried_apply_block_caps_findings(self, tmp_path: Path) -> None:
        from plan_tool.launcher import (
            _CARRIED_APPLY_MAX_FINDINGS,
            apply_finding,
        )
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)
        # More than the cap, all same severity so order is by (anchor, title).
        n = _CARRIED_APPLY_MAX_FINDINGS + 5
        carried = [
            CarriedFinding(
                anchor=f"anchor-{i:03d}",
                title=f"finding {i:03d}",
                severity="high",
                body_excerpt="",
            )
            for i in range(n)
        ]
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=carried,
            dry_run=True,
        )
        assert result.prompt is not None
        rendered_count = result.prompt.count("- (HIGH) finding ")
        assert rendered_count == _CARRIED_APPLY_MAX_FINDINGS
        # Non-silent truncation note.
        assert (
            f"… {n - _CARRIED_APPLY_MAX_FINDINGS} more lower-priority "
            f"finding(s) not shown (cap {_CARRIED_APPLY_MAX_FINDINGS})."
            in result.prompt
        )

    def test_carried_apply_block_deterministic(self, tmp_path: Path) -> None:
        from plan_tool.launcher import (
            _CARRIED_APPLY_MAX_FINDINGS,
            _format_carried_context_block,
        )
        from plan_tool.review import CarriedFinding

        carried = [
            CarriedFinding(
                anchor=f"anchor-{i:03d}",
                title=f"finding {i:03d}",
                severity="high" if i % 2 else "critical",
                body_excerpt="x",
            )
            for i in range(_CARRIED_APPLY_MAX_FINDINGS + 5)
        ]
        first = _format_carried_context_block(carried)
        second = _format_carried_context_block(list(reversed(carried)))
        assert first == second

    def test_carried_findings_scope_set_unchanged(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)
        without = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            dry_run=True,
        )
        with_carried = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            carried_findings=[
                CarriedFinding(
                    anchor="a",
                    title="t",
                    severity="high",
                    body_excerpt="x",
                )
            ],
            dry_run=True,
        )
        assert set(without.pre_snapshot.keys()) == set(
            with_carried.pre_snapshot.keys()
        )

    def test_carried_findings_coexist_with_targeted_fix(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.review import CarriedFinding

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            targeted_fix="flip step 1 status from done to current",
            operator_feedback="only edit the YAML",
            carried_findings=[
                CarriedFinding(
                    anchor="a",
                    title="prior finding",
                    severity="high",
                    body_excerpt="x",
                )
            ],
            step_id=1,
            dry_run=True,
        )
        assert result.prompt is not None
        # Both the targeted-fix and the advisory block render.
        assert "## Targeted fix (realize exactly this intent)" in result.prompt
        assert self._CARRIED_HEADING in result.prompt
        # The carried block sits after the fix/feedback blocks, and the
        # whole volatile finding section trails the stable "## What to do"
        # instructions so the static prefix stays cache-reusable (#74 A1).
        assert result.prompt.index("## Targeted fix") < result.prompt.index(
            self._CARRIED_HEADING
        )
        assert result.prompt.index("## Operator feedback") < result.prompt.index(
            self._CARRIED_HEADING
        )
        assert result.prompt.index("## What to do") < result.prompt.index(
            self._CARRIED_HEADING
        )


class TestApplyFindingHappyPath:
    def test_successful_apply_returns_diff_and_applied_verdict(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        # Fake invoker: simulate Claude editing the plan in-place
        # (status: done → status: current) and emitting the contract.
        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            return 0, (
                "Edited the YAML frontmatter.\n\n"
                "## Summary\n"
                "- `plan.md`: flipped step 1 status from `done` to `current`\n\n"
                "## Verdict\nAPPLIED\n"
            )

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            step_id=1,
            dry_run=False,
            invoker=fake_invoker,
        )
        assert result.exit_code == 0
        assert result.verdict == "APPLIED"
        # Diff captures the YAML mutation.
        assert "status: done" in result.diff_text
        assert "status: current" in result.diff_text
        assert "plan.md" in result.diff_text
        # Pre-snapshot retained the original content for revert.
        assert "status: done" in (result.pre_snapshot[plan_path] or "")
        # Plan on disk reflects the edit.
        post = plan_path.read_text(encoding="utf-8")
        assert "status: current" in post

    def test_revert_restores_pre_snapshot(self, tmp_path: Path) -> None:
        from plan_tool.launcher import (
            apply_finding,
            _restore_text_files,
        )

        plan_path = _write_plan_for_apply(tmp_path)
        original = plan_path.read_text(encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            plan_path.write_text(
                "completely rewritten\n", encoding="utf-8"
            )
            return 0, "## Summary\n- nuked it\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="rewrite",
            step_id=1,
            invoker=fake_invoker,
        )
        # Verify the change landed
        assert plan_path.read_text(encoding="utf-8") == "completely rewritten\n"
        # Revert
        _restore_text_files(result.pre_snapshot)
        assert plan_path.read_text(encoding="utf-8") == original

    def test_diff_covers_a_non_resolved_steps_detail_file(
        self, tmp_path: Path
    ) -> None:
        """A finding with no ``step_id`` resolves to the current step,
        but Claude edits a *different* step's detail file. The diff and
        snapshot must cover every step's detail — not just the resolved
        step's — or the edit reports a false "nothing changed" and never
        gets reverted. (Observed on plan-wide review/completeness recs.)"""
        from plan_tool.launcher import apply_finding

        details_dir = tmp_path / "details"
        details_dir.mkdir()
        step1_detail = details_dir / "01-step.md"
        step2_detail = details_dir / "02-step.md"
        step1_detail.write_text("# step 1 detail\nuntouched\n", encoding="utf-8")
        step2_detail.write_text("# step 2 detail\nORIGINAL\n", encoding="utf-8")

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Cross-Step Apply\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: First\n"
            "    files: [a.py]\n"
            "    status: current\n"
            "    detail: details/01-step.md\n"
            "  - id: 2\n"
            "    title: Second\n"
            "    files: [b.py]\n"
            "    status: pending\n"
            "    detail: details/02-step.md\n"
            "---\n",
            encoding="utf-8",
        )

        # No step_id → resolves to step 1 (current). Claude edits step 2's
        # detail file (the finding's real target).
        def fake_invoker(prompt: str) -> tuple[int, str]:
            step2_detail.write_text(
                "# step 2 detail\nEDITED\n", encoding="utf-8"
            )
            return 0, "## Summary\n- edited step 2 detail\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="Step 2: fix the detail body",
            step_id=None,
            dry_run=False,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        # The edit to the non-resolved step's detail is captured, not a
        # false empty diff.
        assert result.diff_text != ""
        assert "02-step.md" in result.diff_text
        assert "EDITED" in result.diff_text
        # Snapshot retained step 2's pre-edit content so a revert works.
        assert result.pre_snapshot[step2_detail.resolve()] == (
            "# step 2 detail\nORIGINAL\n"
        )


    def test_diff_covers_a_canonical_only_detail_file(
        self, tmp_path: Path
    ) -> None:
        """Same as the sibling above, but the edited step's ``detail:``
        pointer was never persisted and only its canonical file is on disk.
        The reviewer is shown that body, so an edit to it must be diffed and
        revertible — otherwise a declined edit stays on disk."""
        from plan_tool.launcher import apply_finding

        plan_path = tmp_path / "2-canon.md"
        plan_path.write_text(
            "---\n"
            "title: Canon\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: build it\n"
            "    files: [a.py]\n"
            "    status: current\n"
            "---\n",
            encoding="utf-8",
        )
        (tmp_path / "a.py").write_text("x\n", encoding="utf-8")
        bundle = tmp_path / "plan-details" / "canon"
        bundle.mkdir(parents=True)
        canonical = bundle / "01-build.md"
        canonical.write_text("# step 1 detail\nORIGINAL\n", encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            canonical.write_text("# step 1 detail\nEDITED\n", encoding="utf-8")
            return 0, "## Summary\n- edited canonical detail\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix the canonical-only detail body",
            step_id=None,
            dry_run=False,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        assert "01-build.md" in result.diff_text
        assert "EDITED" in result.diff_text
        # Snapshot holds the pre-edit body, so a decline can revert it.
        assert result.pre_snapshot[canonical.resolve()] == (
            "# step 1 detail\nORIGINAL\n"
        )


class TestApplyFindingTelemetry:
    """``apply_finding`` emits joinable parsed and invocation-failure events."""

    @staticmethod
    def _verdict_invoker(verdict_block: str):
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, f"## Summary\n- did it\n\n{verdict_block}"
        return fake_invoker

    def test_apply_finding_records_applied_verdict(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nAPPLIED\n"),
        )
        events = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"]
        assert len(events) == 1
        assert events[0].context["verdict"] == "APPLIED"
        assert events[0].context["step_id"] == "1"

    def test_apply_finding_threads_anchor_and_plan_fingerprint(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nAPPLIED\n"),
            anchor="some-slug",
            plan_fingerprint="pf123",
        )
        event = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"][0]
        assert event.anchor == "some-slug"
        assert event.plan_fingerprint == "pf123"

    def test_apply_finding_defaults_anchor_and_fingerprint_empty(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nAPPLIED\n"),
        )
        event = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"][0]
        assert event.anchor == ""
        assert event.plan_fingerprint == ""

    def test_apply_finding_records_blocked_verdict(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nBLOCKED\n"),
        )
        event = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"][0]
        assert event.context["verdict"] == "BLOCKED"

    def test_apply_finding_records_unknown_when_no_verdict(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Summary\n- did it, no verdict block\n"

        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=fake_invoker,
        )
        event = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"][0]
        assert event.context["verdict"] == "UNKNOWN"

    def test_apply_finding_dry_run_records_nothing(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            dry_run=True,
        )
        assert [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"] == []

    def test_apply_finding_can_defer_apply_verdict_recording(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        observed = []
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nBLOCKED\n"),
            record_verdict=False,
            verdict_observer=observed.append,
        )
        assert result.verdict == "BLOCKED"
        assert [(item.verdict, item.step_id) for item in observed] == [
            ("BLOCKED", 1)
        ]
        assert [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"] == []

    def test_apply_finding_deferred_failure_keeps_classification(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)
        observed = []
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=lambda prompt: (7, "unusable"),
            record_verdict=False,
            verdict_observer=observed.append,
        )
        assert result.exit_code == 7
        assert observed[0].verdict == "INVOCATION-FAILED"
        assert observed[0].restoration_succeeded is True
        assert [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"] == []

    def test_apply_finding_nonzero_exit_records_invocation_failed_once(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 1, "backend blew up"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=fake_invoker,
            anchor="finding-anchor",
            plan_fingerprint="plan-fingerprint",
        )
        events = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"]
        assert len(events) == 1
        assert events[0].context == {
            "verdict": "INVOCATION-FAILED",
            "step_id": "1",
        }
        assert events[0].anchor == "finding-anchor"
        assert events[0].plan_fingerprint == "plan-fingerprint"
        assert result.exit_code == 1
        assert result.verdict == "UNKNOWN"

    def test_apply_finding_invoker_exception_records_once_then_reraises(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions, scoped_run_id

        plan_path = _write_plan_for_apply(tmp_path)
        original = plan_path.read_text(encoding="utf-8")
        backend_error = RuntimeError("backend unavailable")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            plan_path.write_text("partial edit\n", encoding="utf-8")
            raise backend_error

        with scoped_run_id("run-42"):
            with pytest.raises(RuntimeError) as caught:
                apply_finding(
                    plan_path,
                    repo_root=tmp_path,
                    finding_body="fix it",
                    step_id=1,
                    invoker=fake_invoker,
                    anchor="finding-anchor",
                    plan_fingerprint="plan-fingerprint",
                )
        assert caught.value is backend_error
        assert backend_error.apply_finding_restore_succeeded is True
        assert plan_path.read_text(encoding="utf-8") == original
        events = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"]
        assert len(events) == 1
        assert events[0].context["verdict"] == "INVOCATION-FAILED"
        assert events[0].run_id == "run-42"

    def test_apply_finding_failure_recorder_error_preserves_host_failure(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import plan_tool.launcher as launcher_mod
        from plan_tool.launcher import apply_finding

        monkeypatch.setattr(
            launcher_mod,
            "record_apply_verdict",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
        )
        plan_path = _write_plan_for_apply(tmp_path)
        returned = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=lambda prompt: (9, "failed"),
        )
        assert returned.exit_code == 9

        backend_error = RuntimeError("backend failed")

        def raising_invoker(prompt: str) -> tuple[int, str]:
            raise backend_error

        with pytest.raises(RuntimeError) as caught:
            apply_finding(
                plan_path,
                repo_root=tmp_path,
                finding_body="fix it",
                step_id=1,
                invoker=raising_invoker,
            )
        assert caught.value is backend_error

    def test_apply_finding_zero_exit_is_error_uses_accepted_verdict(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.backend import ClaudeRunStats
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Verdict\nBLOCKED\n"

        fake_invoker._last_stats = ClaudeRunStats(is_error=True)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=fake_invoker,
        )
        events = [e for e in read_decisions(tmp_path) if e.kind == "apply-verdict"]
        assert result.verdict == "BLOCKED"
        assert [event.context["verdict"] for event in events] == ["BLOCKED"]

    def test_apply_finding_telemetry_is_best_effort(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        import plan_tool.launcher as launcher_mod
        from plan_tool.launcher import apply_finding

        def boom(*a, **k):
            raise RuntimeError("telemetry down")

        monkeypatch.setattr(launcher_mod, "record_apply_verdict", boom)

        plan_path = _write_plan_for_apply(tmp_path)
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="fix it",
            step_id=1,
            invoker=self._verdict_invoker("## Verdict\nAPPLIED\n"),
        )
        assert result.verdict == "APPLIED"
        assert result.exit_code == 0


class TestApplyFindingSummaryRecovery:
    """An APPLIED edit whose ``## Summary`` is buried past the 4 KB tail
    by acceptEdits tool-use chatter must still be captured — otherwise the
    disposition note records a bare ``applied finding:`` with no
    description of the change (the observed report bug)."""

    def test_summary_buried_under_chatter_is_recovered(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            # Summary up top, then a long wall of edit-tool chatter that
            # pushes it well past the last 4 KB of stdout.
            chatter = "tool-use line\n" * 600
            return 0, (
                "## Summary\n"
                "- `plan.md`: flipped step 1 status to `current`\n\n"
                "## Verdict\nAPPLIED\n\n" + chatter
            )

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            step_id=1,
            dry_run=False,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        # The fix: full-stdout scan recovers the buried summary.
        assert "flipped step 1 status" in result.summary

    def test_applied_without_summary_warns(
        self, tmp_path: Path, capsys
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            # APPLIED but no ``## Summary`` block at all.
            return 0, "Edited the frontmatter.\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="step 1 status should be current not done",
            step_id=1,
            dry_run=False,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        assert result.summary == ""
        # The empty summary is surfaced loudly, not swallowed.
        err = capsys.readouterr().err
        assert "no `## Summary`" in err
        assert "APPLIED" in err


class TestApplyFindingProgressLabel:
    """The apply-finding progress line must describe the finding being
    applied, not repeat the step title on every call (the title is
    identical across every finding for a given step and tells the
    operator nothing about which finding is in flight)."""

    def test_label_names_the_finding_not_the_step_title(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)  # step 1 title: "Build the thing"

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Summary\n- noop\n\n## Verdict\nNOT-APPLICABLE\n"

        reporter = _RecordingReporter()
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body=(
                "[HIGH] Downgrade MISSING_PARENT for covered dirs\n\nbody"
            ),
            step_id=1,
            invoker=fake_invoker,
            reporter=reporter,
        )
        label = reporter.starts[0][2]
        assert "[HIGH] Downgrade MISSING_PARENT for covered dirs" in label
        assert "Build the thing" not in label

    def test_label_falls_back_when_finding_body_blank(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Verdict\nNOT-APPLICABLE\n"

        reporter = _RecordingReporter()
        apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="   \n  ",
            step_id=1,
            invoker=fake_invoker,
            reporter=reporter,
        )
        assert reporter.starts[0][2] == "apply-finding step 1: finding"


class TestApplyFindingNoGate:
    """Step 6 of Reconcile Subcommand Split deleted the
    ``_ALLOWED_PLAN_UPDATE_JUSTIFICATIONS`` gate and the ``REFUSED``
    branch from ``apply_finding``. These tests pin the post-deletion
    shape: the kwarg is gone from the signature, and a finding body
    that the old gate would have refused now reaches the invoker and
    returns ``APPLIED``."""

    def test_apply_finding_signature_no_longer_carries_allowed_justifications(
        self,
    ) -> None:
        import inspect

        from plan_tool.launcher import apply_finding

        params = inspect.signature(apply_finding).parameters
        assert "allowed_justifications" not in params

    def test_apply_finding_admits_previously_refused_justification(
        self, tmp_path: Path
    ) -> None:
        """A finding body declaring ``Direction: update-plan`` paired
        with ``Justification: scope-narrowing`` (formerly REFUSED) now
        reaches the invoker and returns ``APPLIED`` — the gate is
        gone."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            return 0, "## Summary\n- did it\n\n## Verdict\nAPPLIED\n"

        finding_body = (
            "narrow scope\n\n"
            "## Decision\n\n"
            "- **Intent**: step claims foo\n"
            "- **Code state**: foo exists\n"
            "- **Fulfills intent?**: yes\n"
            "- **Direction**: update-plan\n"
            "- **Justification**: scope-narrowing\n"
        )
        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body=finding_body,
            step_id=1,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        assert len(calls) == 1


class TestApplyFindingFailureHandling:
    def test_non_zero_exit_reverts_and_returns_unknown(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        original = plan_path.read_text(encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            # Simulate Claude making a partial edit then failing.
            plan_path.write_text("partial garbage\n", encoding="utf-8")
            return 1, "boom"

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            invoker=fake_invoker,
        )
        assert result.exit_code == 1
        assert result.verdict == "UNKNOWN"
        # Snapshot was auto-restored so the partial edit is gone.
        assert plan_path.read_text(encoding="utf-8") == original

    def test_invoker_exception_attempts_every_restore_and_preserves_error(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        detail_path = tmp_path / "details/01-audit-sample-reuse.md"
        original_plan = plan_path.read_text(encoding="utf-8")
        original_detail = detail_path.read_text(encoding="utf-8")
        original_write_text = Path.write_text
        restore_attempts: list[Path] = []
        backend_error = RuntimeError("backend failed after editing")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            original_write_text(plan_path, "partial plan\n", encoding="utf-8")
            original_write_text(detail_path, "partial detail\n", encoding="utf-8")
            raise backend_error

        def fail_one_restore(
            path: Path, content: str, *args, **kwargs
        ) -> int:
            if path == plan_path and content == original_plan:
                restore_attempts.append(path)
                raise OSError("plan restore failed")
            if path == detail_path.resolve() and content == original_detail:
                restore_attempts.append(path)
            return original_write_text(path, content, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", fail_one_restore)
        with pytest.raises(RuntimeError) as caught:
            apply_finding(
                plan_path,
                repo_root=tmp_path,
                finding_body="fix it",
                step_id=1,
                invoker=fake_invoker,
            )

        assert caught.value is backend_error
        assert backend_error.apply_finding_restore_succeeded is False
        assert restore_attempts == [plan_path, detail_path.resolve()]
        assert plan_path.read_text(encoding="utf-8") == "partial plan\n"
        assert detail_path.read_text(encoding="utf-8") == original_detail

    def test_apply_refuses_unsupported_detail_before_snapshot_or_mutation(
        self, tmp_path: Path
    ) -> None:
        """A step's detail already declaring an unsupported version at call
        time must stop the whole apply before the pre-edit snapshot, the
        model call, or any mutation — not merely before the post-edit
        delta (see ``test_post_edit_delta_reraises_detail_format_error``)."""
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        detail_path = tmp_path / "details/01-audit-sample-reuse.md"
        detail_path.write_text(
            f"# Audit sample reuse guard\n{render_detail_format_version_marker(999)}"
            "\n\nKeep the audit sample reuse guard phrase stable.\n",
            encoding="utf-8",
        )
        original_detail_bytes = detail_path.read_bytes()
        calls = {"n": 0}

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls["n"] += 1
            return 0, "## Summary\n- edited it\n\n## Verdict\nAPPLIED\n"

        with pytest.raises(DetailFormatError):
            apply_finding(
                plan_path,
                repo_root=tmp_path,
                finding_body="anything",
                step_id=1,
                invoker=fake_invoker,
            )
        assert calls["n"] == 0
        assert detail_path.read_bytes() == original_detail_bytes

    def test_no_verdict_in_response_marks_unknown(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "I made some edits but forgot the verdict block."

        result = apply_finding(
            plan_path,
            repo_root=tmp_path,
            finding_body="anything",
            step_id=1,
            invoker=fake_invoker,
        )
        # Exit was 0, but no verdict → caller should treat as unknown.
        assert result.exit_code == 0
        assert result.verdict == "UNKNOWN"


class TestApplyFindingValidationDelta:
    """``apply_finding`` runs the deterministic correctness +
    completeness primitives against pre and post plan state and
    surfaces the delta on the result. Regressions land in
    ``introduced_findings``; resolved issues land in
    ``resolved_findings``."""

    def _plan_with_placeholder_section(self, tmp_path: Path) -> Path:
        """Plan whose ``## Overview`` body is a TODO placeholder — a
        body-completeness gap the apply-finding edit might either
        resolve (fill in real content) or preserve. Parser doesn't
        validate body content, so we can construct it freely."""
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Delta Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n"
            "_(TODO)_\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        return plan_path

    def test_clean_apply_has_empty_delta(self, tmp_path: Path) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            # Delta-neutral edit: bump priority but leave step 1 `done`.
            # (Flipping a done step back to `current` would re-surface its
            # pre-execution authoring findings — a real delta — since the
            # completeness checks skip done steps.)
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("priority: low", "priority: medium"),
                encoding="utf-8",
            )
            return 0, "## Summary\n- bumped priority\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="bump priority", step_id=1,
            invoker=fake_invoker,
        )
        # No new findings, no resolved findings.
        assert result.introduced_findings == ()
        assert result.resolved_findings == ()

    def test_resolved_finding_surfaces(self, tmp_path: Path) -> None:
        """Plan starts with a placeholder ## Overview body. Apply
        replaces it with real content — body-completeness finding
        should appear in resolved."""
        from plan_tool.launcher import apply_finding

        plan_path = self._plan_with_placeholder_section(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace(
                    "## Overview\n_(TODO)_\n",
                    "## Overview\nReal description of what this plan delivers.\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- filled overview\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="fill in ## Overview", step_id=1,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        # Resolved should contain the body-completeness finding for
        # ``## Overview``. Other body sections are also missing
        # (TODO sweep) — they persist in both pre and post and don't
        # show up here.
        assert any(
            r.source == "body-completeness"
            and "Overview" in r.title
            for r in result.resolved_findings
        ), (
            "expected body-completeness Overview finding in resolved: "
            f"{result.resolved_findings}"
        )

    def test_introduced_finding_surfaces(self, tmp_path: Path) -> None:
        """Plan starts with a populated ## Overview. Apply replaces
        it with a placeholder — body-completeness finding should
        appear in introduced."""
        from plan_tool.launcher import apply_finding

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Intro Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n"
            "Real description.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace(
                    "## Overview\nReal description.\n",
                    "## Overview\n_(TODO)_\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- replaced with todo\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder the overview", step_id=1,
            invoker=fake_invoker,
        )
        assert result.verdict == "APPLIED"
        assert any(
            r.source == "body-completeness"
            and "Overview" in r.title
            for r in result.introduced_findings
        ), (
            "expected body-completeness Overview finding in "
            f"introduced: {result.introduced_findings}"
        )

    def test_unparseable_post_edit_surfaces_critical(
        self, tmp_path: Path
    ) -> None:
        """If Claude breaks the YAML, surface a synthetic
        post-edit-parse-failure as an introduced finding so the user
        knows to revert."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            plan_path.write_text(
                "this is not valid YAML frontmatter\n", encoding="utf-8"
            )
            return 0, "## Summary\n- broke it\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1,
            invoker=fake_invoker,
        )
        assert any(
            r.id == "post-edit-parse-failure"
            for r in result.introduced_findings
        )

    def test_post_edit_delta_reraises_detail_format_error(
        self, tmp_path: Path
    ) -> None:
        """A detail body corrupted with a malformed marker *by the model's
        own edit* must surface as its own named refusal, not get
        misdiagnosed as ``post-edit-parse-failure`` — that synthetic
        finding is reserved for an actual broken plan-frontmatter parse."""
        from plan_tool.detail_artifacts import DetailFormatError
        from plan_tool.launcher import apply_finding

        plan_path = _write_phrase_guardrail_plan_for_apply(tmp_path)
        detail_path = tmp_path / "details" / "01-audit-sample-reuse.md"

        def fake_invoker(prompt: str) -> tuple[int, str]:
            detail_path.write_text(
                "# Audit sample reuse guard\n"
                "<!-- plan-tool:detail-format-version: not-a-number -->\n\n"
                "Keep the audit sample reuse guard phrase stable.\n",
                encoding="utf-8",
            )
            return 0, "## Summary\n- edited it\n\n## Verdict\nAPPLIED\n"

        with pytest.raises(DetailFormatError):
            apply_finding(
                plan_path, repo_root=tmp_path,
                finding_body="anything", step_id=1,
                invoker=fake_invoker,
            )

    def test_post_edit_delta_reraises_unsupported_plan_format_version(
        self, tmp_path: Path
    ) -> None:
        """A model-authored unsupported plan version remains a named refusal."""
        from plan_tool.launcher import apply_finding
        from plan_tool.parser import UnsupportedPlanFormatVersionError

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                text.replace("title: Apply Test", "format_version: 999\ntitle: Apply Test"),
                encoding="utf-8",
            )
            return 0, "## Summary\n- set a version\n\n## Verdict\nAPPLIED\n"

        with pytest.raises(UnsupportedPlanFormatVersionError):
            apply_finding(
                plan_path, repo_root=tmp_path,
                finding_body="anything", step_id=1,
                invoker=fake_invoker,
            )

    def test_blocked_verdict_skips_delta(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Summary\n- nothing\n\n## Verdict\nBLOCKED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1,
            invoker=fake_invoker,
        )
        assert result.verdict == "BLOCKED"
        # Delta is intentionally empty for non-APPLIED verdicts.
        assert result.introduced_findings == ()
        assert result.resolved_findings == ()

    def test_blocked_structural_verdict_skips_delta(
        self, tmp_path: Path
    ) -> None:
        """``BLOCKED-STRUCTURAL`` flows through the same non-APPLIED
        path as ``BLOCKED``: it carries verbatim and yields an empty
        delta with no new ``apply_finding`` branch."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return 0, "## Summary\n- nothing\n\n## Verdict\nBLOCKED-STRUCTURAL\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1,
            invoker=fake_invoker,
        )
        assert result.verdict == "BLOCKED-STRUCTURAL"
        assert result.introduced_findings == ()
        assert result.resolved_findings == ()


class TestApplyFindingAutoFixIntroduced:
    """When the initial apply lands but introduces new deterministic
    findings, ``apply_finding`` makes ONE follow-up Claude call that
    bundles every regression into a single finding body and asks
    Claude to fix them all together. The final ``introduced`` /
    ``resolved`` lists are recomputed against the original pre-edit
    baseline."""

    def _plan_with_overview(self, tmp_path: Path) -> Path:
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Auto-Fix Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n"
            "Real description.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        return plan_path

    def test_followup_resolves_regression(self, tmp_path: Path) -> None:
        """Initial apply replaces a populated ## Overview with a
        placeholder (introducing a body-completeness regression). The
        follow-up call restores real content. Final result has no
        introduced findings — the regression was auto-fixed."""
        from plan_tool.launcher import apply_finding

        plan_path = self._plan_with_overview(tmp_path)
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            current = plan_path.read_text(encoding="utf-8")
            if len(calls) == 1:
                # Initial: stomp the overview with a placeholder.
                plan_path.write_text(
                    current.replace(
                        "## Overview\nReal description.\n",
                        "## Overview\n_(TODO)_\n",
                    ),
                    encoding="utf-8",
                )
                return 0, (
                    "## Summary\n- placeholdered overview\n\n"
                    "## Verdict\nAPPLIED\n"
                )
            # Follow-up: fix the body-completeness regression by
            # restoring real content (different prose so the diff
            # doesn't roundtrip to zero).
            plan_path.write_text(
                current.replace(
                    "## Overview\n_(TODO)_\n",
                    "## Overview\nFollow-up restored body.\n",
                ),
                encoding="utf-8",
            )
            return 0, (
                "## Summary\n- restored overview body\n\n"
                "## Verdict\nAPPLIED\n"
            )

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder the overview", step_id=1,
            operator_feedback="retain the existing API contract",
            invoker=fake_invoker,
        )
        # Two calls: the initial apply and one bundled follow-up.
        assert len(calls) == 2
        # Follow-up prompt carried the regression's body.
        assert "body-completeness" in calls[1] or "Overview" in calls[1]
        assert "## Operator feedback (authoritative" in calls[1]
        assert "retain the existing API contract" in calls[1]
        assert "${operator_feedback_block}" not in calls[1]
        assert result.verdict == "APPLIED"
        # Regression auto-fixed → introduced is empty.
        assert result.introduced_findings == ()
        # Summary mentions the follow-up.
        assert "follow-up" in result.summary
        # Plan reflects the final follow-up content.
        assert (
            "Follow-up restored body."
            in plan_path.read_text(encoding="utf-8")
        )

    def test_followup_bundles_multiple_regressions(
        self, tmp_path: Path
    ) -> None:
        """Initial apply introduces multiple body-completeness
        regressions. The follow-up call is invoked exactly once with
        all regressions bundled into the finding body."""
        from plan_tool.launcher import apply_finding

        # Plan starts with two populated body sections — Overview and
        # Risks. The initial apply will placeholder both.
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Bundle Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\nReal overview.\n\n"
            "## Risks\nReal risks.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            current = plan_path.read_text(encoding="utf-8")
            if len(calls) == 1:
                # Stomp both sections with placeholders.
                new = current.replace(
                    "## Overview\nReal overview.\n",
                    "## Overview\n_(TODO)_\n",
                ).replace(
                    "## Risks\nReal risks.\n",
                    "## Risks\n_(TODO)_\n",
                )
                plan_path.write_text(new, encoding="utf-8")
                return 0, "## Summary\n- placeholdered\n\n## Verdict\nAPPLIED\n"
            # Follow-up: restore both.
            new = current.replace(
                "## Overview\n_(TODO)_\n",
                "## Overview\nFixed overview.\n",
            ).replace(
                "## Risks\n_(TODO)_\n",
                "## Risks\nFixed risks.\n",
            )
            plan_path.write_text(new, encoding="utf-8")
            return 0, "## Summary\n- restored both\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder bodies", step_id=1,
            invoker=fake_invoker,
        )
        # Exactly one follow-up call (not one per regression).
        assert len(calls) == 2
        followup_prompt = calls[1]
        # The bundled body lists both regressions and the directive
        # tells Claude to address them in a single edit.
        assert "Overview" in followup_prompt
        assert "Risks" in followup_prompt
        assert "Address all of them" in followup_prompt
        assert "Finding 1" in followup_prompt
        assert "Finding 2" in followup_prompt
        # Both regressions resolved.
        assert result.introduced_findings == ()
        # Plan has both fixes applied.
        post = plan_path.read_text(encoding="utf-8")
        assert "Fixed overview." in post
        assert "Fixed risks." in post

    def test_followup_failure_preserves_regressions(
        self, tmp_path: Path
    ) -> None:
        """If the follow-up call exits non-zero, the initial apply
        stays — but the introduced findings are surfaced unchanged so
        the caller's confirmation prompt warns the user."""
        from plan_tool.launcher import apply_finding

        plan_path = self._plan_with_overview(tmp_path)
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            if len(calls) == 1:
                current = plan_path.read_text(encoding="utf-8")
                plan_path.write_text(
                    current.replace(
                        "## Overview\nReal description.\n",
                        "## Overview\n_(TODO)_\n",
                    ),
                    encoding="utf-8",
                )
                return 0, "## Summary\n- placeholdered\n\n## Verdict\nAPPLIED\n"
            # Follow-up explodes.
            return 1, "boom"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder the overview", step_id=1,
            invoker=fake_invoker,
        )
        assert len(calls) == 2
        # Initial apply's verdict survives; regression is surfaced.
        assert result.verdict == "APPLIED"
        assert any(
            r.source == "body-completeness"
            and "Overview" in r.title
            for r in result.introduced_findings
        )
        # Plan still in placeholder state (we don't revert on
        # follow-up failure — the user gets to decide via the caller's
        # confirmation prompt).
        assert "_(TODO)_" in plan_path.read_text(encoding="utf-8")
        from plan_tool.telemetry import read_decisions
        assert [
            event.context["verdict"]
            for event in read_decisions(tmp_path)
            if event.kind == "apply-verdict"
        ] == ["APPLIED", "INVOCATION-FAILED"]

    def test_followup_exception_preserves_primary_edit_and_reraises(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding
        from plan_tool.telemetry import read_decisions

        plan_path = self._plan_with_overview(tmp_path)
        calls = 0
        backend_error = RuntimeError("follow-up failed")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            nonlocal calls
            calls += 1
            current = plan_path.read_text(encoding="utf-8")
            if calls == 1:
                plan_path.write_text(
                    current.replace("Real description.", "_(TODO)_"),
                    encoding="utf-8",
                )
                return 0, "## Summary\n- changed body\n\n## Verdict\nAPPLIED\n"
            plan_path.write_text("follow-up partial garbage\n", encoding="utf-8")
            raise backend_error

        with pytest.raises(RuntimeError) as caught:
            apply_finding(
                plan_path,
                repo_root=tmp_path,
                finding_body="replace overview",
                step_id=1,
                invoker=fake_invoker,
            )
        assert caught.value is backend_error
        assert backend_error.apply_finding_restore_succeeded is True
        restored = plan_path.read_text(encoding="utf-8")
        assert "Real description." not in restored
        assert "_(TODO)_" in restored
        assert "follow-up partial garbage" not in restored
        assert [
            event.context["verdict"]
            for event in read_decisions(tmp_path)
            if event.kind == "apply-verdict"
        ] == ["APPLIED", "INVOCATION-FAILED"]

    def test_followup_partial_resolution_surfaces_remainder(
        self, tmp_path: Path
    ) -> None:
        """When the follow-up resolves some regressions but not all,
        the remaining ones surface in the final result."""
        from plan_tool.launcher import apply_finding

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Partial Fix Test\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\nReal overview.\n\n"
            "## Risks\nReal risks.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            current = plan_path.read_text(encoding="utf-8")
            if len(calls) == 1:
                new = current.replace(
                    "## Overview\nReal overview.\n",
                    "## Overview\n_(TODO)_\n",
                ).replace(
                    "## Risks\nReal risks.\n",
                    "## Risks\n_(TODO)_\n",
                )
                plan_path.write_text(new, encoding="utf-8")
                return 0, "## Summary\n- placeholdered\n\n## Verdict\nAPPLIED\n"
            # Only fix Overview; leave Risks placeholder.
            new = current.replace(
                "## Overview\n_(TODO)_\n",
                "## Overview\nFixed overview.\n",
            )
            plan_path.write_text(new, encoding="utf-8")
            return 0, "## Summary\n- partial fix\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder bodies", step_id=1,
            invoker=fake_invoker,
        )
        assert len(calls) == 2
        intro_titles = {r.title for r in result.introduced_findings}
        # Risks regression survives.
        assert any("Risks" in t for t in intro_titles)
        # Overview regression cleaned up.
        assert not any("Overview" in t for t in intro_titles)

    def test_auto_fix_disabled_skips_followup(
        self, tmp_path: Path
    ) -> None:
        """``auto_fix_introduced=False`` preserves legacy single-call
        behavior — regressions surface unchanged with no second
        Claude invocation."""
        from plan_tool.launcher import apply_finding

        plan_path = self._plan_with_overview(tmp_path)
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace(
                    "## Overview\nReal description.\n",
                    "## Overview\n_(TODO)_\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- placeholdered\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder the overview", step_id=1,
            invoker=fake_invoker,
            auto_fix_introduced=False,
        )
        assert len(calls) == 1
        assert any(
            r.source == "body-completeness"
            and "Overview" in r.title
            for r in result.introduced_findings
        )

    def test_parse_failure_skips_followup(self, tmp_path: Path) -> None:
        """A post-edit-parse-failure regression must NOT trigger a
        follow-up — the plan is already broken and piling more edits
        on top would muddy the eventual revert."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            plan_path.write_text(
                "totally broken yaml\n", encoding="utf-8"
            )
            return 0, "## Summary\n- broke it\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="anything", step_id=1,
            invoker=fake_invoker,
        )
        # Only the initial call — parse failure short-circuits the
        # auto-fix.
        assert len(calls) == 1
        assert any(
            r.id == "post-edit-parse-failure"
            for r in result.introduced_findings
        )

    def test_followup_revert_back_to_pre_edit_yields_empty_delta(
        self, tmp_path: Path
    ) -> None:
        """Edge case: follow-up rewrites the plan back to its
        original state. Diff collapses to empty; the result reports
        no introduced and no resolved (the apply effectively no-ops)."""
        from plan_tool.launcher import apply_finding

        plan_path = self._plan_with_overview(tmp_path)
        original = plan_path.read_text(encoding="utf-8")
        calls: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            calls.append(prompt)
            if len(calls) == 1:
                current = plan_path.read_text(encoding="utf-8")
                plan_path.write_text(
                    current.replace(
                        "## Overview\nReal description.\n",
                        "## Overview\n_(TODO)_\n",
                    ),
                    encoding="utf-8",
                )
                return 0, "## Summary\n- placeholdered\n\n## Verdict\nAPPLIED\n"
            # Follow-up writes the original back verbatim.
            plan_path.write_text(original, encoding="utf-8")
            return 0, "## Summary\n- reverted\n\n## Verdict\nAPPLIED\n"

        result = apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder the overview", step_id=1,
            invoker=fake_invoker,
        )
        assert result.introduced_findings == ()
        assert result.resolved_findings == ()
        assert result.diff_text == ""
        assert plan_path.read_text(encoding="utf-8") == original


def _write_declared_risk_apply_plan(tmp_path: Path) -> Path:
    plan_path = _write_plan_for_apply(tmp_path)
    plan_path.write_text(
        plan_path.read_text(encoding="utf-8").replace(
            "priority: low\n",
            "priority: low\n"
            "risk_profile: high\n"
            "risk_profile_rationale: The edit crosses an external boundary.\n",
        )
        + "\n## Overview\nReal description.\n",
        encoding="utf-8",
    )
    return plan_path


def test_apply_finding_context_reaches_primary_and_followup_prompts(
    tmp_path: Path,
) -> None:
    """Keep an opted-in context stable across one automatic follow-up."""
    from plan_tool.launcher import apply_finding

    plan_path = _write_declared_risk_apply_plan(tmp_path)
    risk_context_block = "## Captured risk context\n\nRISK-CONTEXT\n\n"
    prompts: list[str] = []

    def fake_invoker(prompt: str) -> tuple[int, str]:
        prompts.append(prompt)
        current = plan_path.read_text(encoding="utf-8")
        if len(prompts) == 1:
            plan_path.write_text(
                current.replace(
                    "## Overview\nReal description.\n",
                    "## Overview\n_(TODO)_\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- placeholder overview\n\n## Verdict\nAPPLIED\n"
        plan_path.write_text(
            current.replace(
                "## Overview\n_(TODO)_\n",
                "## Overview\nFollow-up description.\n",
            ),
            encoding="utf-8",
        )
        return 0, "## Summary\n- restore overview\n\n## Verdict\nAPPLIED\n"

    apply_finding(
        plan_path,
        repo_root=tmp_path,
        finding_body="Replace the overview with a placeholder.",
        step_id=1,
        invoker=fake_invoker,
        risk_context_block=risk_context_block,
    )

    assert len(prompts) == 2
    assert all(
        risk_context_block in prompt.split("## What to do", 1)[0]
        for prompt in prompts
    )


def test_apply_finding_empty_context_preserves_shared_caller_prompt(
    tmp_path: Path,
) -> None:
    """Keep omitted and explicit-empty contexts byte-identical for callers."""
    from plan_tool.launcher import apply_finding

    plan_path = _write_declared_risk_apply_plan(tmp_path)
    omitted = apply_finding(
        plan_path,
        repo_root=tmp_path,
        finding_body="Keep the declared risk profile advisory.",
        step_id=1,
        dry_run=True,
    )
    explicit_empty = apply_finding(
        plan_path,
        repo_root=tmp_path,
        finding_body="Keep the declared risk profile advisory.",
        step_id=1,
        dry_run=True,
        risk_context_block="",
    )

    assert omitted.prompt == explicit_empty.prompt


def test_apply_finding_prompt_renders_single_what_to_do_heading(
    tmp_path: Path,
) -> None:
    """Regression: the advisory insertion point must not duplicate the
    template's real ``## What to do`` heading, whether or not risk context
    is supplied. A prior template edit merged a literal ``## What to do``
    onto the insertion point's own line instead of placing it inertly
    before the existing paragraph, corrupting every apply-finding prompt."""
    from plan_tool.launcher import apply_finding

    plan_path = _write_declared_risk_apply_plan(tmp_path)
    kwargs = dict(
        repo_root=tmp_path,
        finding_body="Keep the declared risk profile advisory.",
        step_id=1,
        dry_run=True,
    )

    empty = apply_finding(plan_path, **kwargs, risk_context_block="")
    declared = apply_finding(
        plan_path,
        **kwargs,
        risk_context_block="## Declared risk profile (advisory)\n\nRISK\n\n",
    )

    assert empty.prompt.count("## What to do") == 1
    assert declared.prompt.count("## What to do") == 1
    assert (
        "The plan file, the step's detail, and the finding(s)" in empty.prompt
    )


class TestFormatFindingsAsBody:
    """Unit tests for the bundled-finding body formatter — covers the
    single-finding shape and the multi-finding directive shape."""

    def test_empty_returns_empty_string(self) -> None:
        from plan_tool.launcher import _format_findings_as_body

        assert _format_findings_as_body(()) == ""

    def test_single_finding_uses_bracketed_severity_header(self) -> None:
        from plan_tool.launcher import _format_findings_as_body
        from plan_tool.review import Recommendation

        rec = Recommendation(
            id="x", source="body-completeness", severity="medium",
            step_id=None, title="Overview is a placeholder",
            body="Replace `_(TODO)_` with real prose.",
            suggested_action=None,
        )
        body = _format_findings_as_body((rec,))
        assert body.startswith("[MEDIUM] Overview is a placeholder")
        assert "Replace `_(TODO)_` with real prose." in body
        # No multi-finding directive on a single-item bundle.
        assert "Address all of them" not in body
        assert "Finding 1:" not in body

    def test_apply_body_renders_confidence_as_display_only_context(self) -> None:
        from plan_tool.launcher import _format_findings_as_body
        from plan_tool.review import Recommendation

        rec = Recommendation(
            id="legacy", source="body-completeness", severity="medium",
            step_id=None, title="Legacy support", body="Keep the remedy.",
            confidence=None,
        )
        assert "confidence: unknown" in _format_findings_as_body((rec,))

    def test_multi_finding_includes_directive_and_numbering(self) -> None:
        from plan_tool.launcher import _format_findings_as_body
        from plan_tool.review import Recommendation

        recs = (
            Recommendation(
                id="a", source="body-completeness", severity="medium",
                step_id=None, title="Overview is a placeholder",
                body="Fill in the overview.",
                suggested_action=None,
                confidence="supported",
            ),
            Recommendation(
                id="b", source="body-completeness", severity="medium",
                step_id=None, title="Risks is a placeholder",
                body="Fill in the risks.",
                suggested_action=None,
                confidence=None,
            ),
        )
        body = _format_findings_as_body(recs)
        assert "introduced 2 new findings" in body
        assert "Address all of them in this single edit" in body
        assert "### Finding 1: [MEDIUM] Overview is a placeholder" in body
        assert "### Finding 2: [MEDIUM] Risks is a placeholder" in body
        assert "confidence: supported" in body
        assert "confidence: unknown" in body
        assert "Fill in the overview." in body
        assert "Fill in the risks." in body

    def test_multi_finding_uses_info_for_an_unset_severity(self) -> None:
        from plan_tool.launcher import _format_findings_as_body
        from plan_tool.review import Recommendation

        recs = (
            Recommendation(
                id="unset", source="body-completeness", severity=None,
                step_id=None, title="Unset severity", body="Fix it.",
            ),
            Recommendation(
                id="normal", source="body-completeness", severity="medium",
                step_id=None, title="Normal severity", body="Fix it too.",
            ),
        )

        assert "### Finding 1: [INFO] Unset severity" in _format_findings_as_body(recs)

    def test_multi_finding_includes_restated_property(self) -> None:
        """A 6th independent render site: the multi-finding bundler must not
        silently drop restated_property the way the single-finding path
        (format_recommendation_for_apply) already does not."""
        from plan_tool.launcher import _format_findings_as_body
        from plan_tool.review import Recommendation

        recs = (
            Recommendation(
                id="a", source="plan-correctness", severity="high",
                step_id=None, title="Bare step has no route",
                body="Step 4 names a property but nothing delivers it.",
                restated_property="the plan has no route for this property",
            ),
            Recommendation(
                id="b", source="body-completeness", severity="medium",
                step_id=None, title="Risks is a placeholder",
                body="Fill in the risks.",
            ),
        )
        body = _format_findings_as_body(recs)
        assert "the plan has no route for this property" in body
        # The second finding carries no restated_property; no stray label.
        assert body.count("Plan-altitude restatement") == 1


class TestApplyFindingDispatchSourceSet:
    """Regression: source-based dispatch contract — detail-reconcile and
    claude recs are dispatchable via apply_finding even when their
    suggested_action is None."""

    def test_detail_reconcile_source_is_dispatchable(self) -> None:
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import (
            is_dispatchable,
            should_apply_as_finding,
        )

        rec = Recommendation(
            id="x", source="detail-reconcile", severity="critical",
            step_id=3, title="t", body="status should flip to current",
            suggested_action=None,
        )
        assert should_apply_as_finding(rec) is True
        assert is_dispatchable(rec) is True

    def test_claude_source_is_dispatchable(self) -> None:
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import (
            is_dispatchable,
            should_apply_as_finding,
        )

        rec = Recommendation(
            id="x", source="claude", severity="medium",
            step_id=None, title="t", body="add note about constraint",
            suggested_action=None,
        )
        assert should_apply_as_finding(rec) is True
        assert is_dispatchable(rec) is True

    def test_deps_source_not_dispatchable(self) -> None:
        from plan_tool.review import Recommendation
        from plan_tool.review_walk import (
            is_dispatchable,
            should_apply_as_finding,
        )

        rec = Recommendation(
            id="x", source="deps", severity="high",
            step_id=2, title="t", body="b",
            suggested_action="unblock dep on step 1",
        )
        assert should_apply_as_finding(rec) is False
        assert is_dispatchable(rec) is False


# ---------------------------------------------------------------------------
# Step 5: run_log wiring for run_step / apply_finding.
#
# These exercise the per-method emit contract via a recording fake; the
# integration tests in tests/test_cli.py cover the full JSONL pipeline.
# ---------------------------------------------------------------------------


class _RecordingLogger:
    """Drop-in fake matching the subset of ``RunLogWriter`` that
    ``run_step`` / ``apply_finding`` call. Records every emit so tests
    can assert on the event sequence without touching disk.

    ``bind_shell_sink`` installs a real sink via
    ``shell.set_active_sink`` for the duration of the ``with`` block —
    the same shape as the production
    :meth:`RunLogWriter.bind_shell_sink` — so any ``ClaudeCallEnd``
    pushed inside the block (e.g. from step 3's direct emit in
    :func:`run_step`) lands on ``self.events`` as a
    ``("claude_call_end", payload)`` tuple instead of being dropped.
    """

    def __init__(self) -> None:
        self.events: list[tuple] = []
        self.run_id = "fake-run-id"

    def phase_start(self, phase, **extra):
        self.events.append(("phase_start", phase, extra))

    def phase_end(self, phase, *, duration_ms, outcome, **extra):
        self.events.append(("phase_end", phase, outcome, extra))

    def claude_call_start(self, *, phase, attempt, prompt_bytes, **extra):
        self.events.append(
            ("claude_call_start", phase, attempt, prompt_bytes, extra)
        )

    def backend_recovery_wait(self, *, phase, attempt, reason, delay_ms,
                              next_attempt, backend, **extra):
        self.events.append((
            "backend_recovery_wait", phase, attempt, reason, delay_ms,
            next_attempt, backend, extra,
        ))

    def run_interrupted(self, *, phase, attempt, source, signal="SIGINT",
                        **extra):
        self.events.append(
            ("run_interrupted", phase, attempt, source, signal, extra)
        )

    def backend_spawn(self, *, phase, attempt, backend, **extra):
        self.events.append(("backend_spawn", phase, attempt, backend, extra))

    def backend_termination(self, *, phase, attempt, backend, reason,
                            duration_ms, **extra):
        self.events.append((
            "backend_termination", phase, attempt, backend, reason,
            duration_ms, extra,
        ))

    def bind_shell_sink(self, *, phase, attempt):
        from contextlib import contextmanager
        from dataclasses import asdict
        from plan_tool import shell as shell_module

        self.events.append(("bind_shell_sink", phase, attempt))
        events = self.events
        run_id = self.run_id

        @contextmanager
        def _bound():
            prev = shell_module.get_active_sink()

            def _sink(event):
                payload = asdict(event)
                payload["run_id"] = run_id
                payload["phase"] = phase
                payload["attempt"] = attempt
                events.append(("claude_call_end", payload))

            shell_module.set_active_sink(_sink)
            try:
                yield
            finally:
                shell_module.set_active_sink(prev)

        return _bound()


class TestRunStepRunLog:
    """``run_step`` emits ``prompt_build`` and ``claude_call`` phase
    pairs around the renderer and the invoker when a ``run_logger`` is
    supplied. With ``run_logger=None`` it emits nothing — the
    back-compat contract that protects every existing test in
    ``TestRunStep``."""

    def test_run_step_no_logger_writes_nothing_under_runs(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)
        runs_dir = tmp_path / ".plan-tool" / "runs"
        # Either absent or empty — but never carrying files we didn't write.
        if runs_dir.exists():
            files = [p for p in runs_dir.rglob("*") if p.is_file()]
            assert files == []

    def test_run_step_emits_prompt_build_phase_pair(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            run_logger=logger,
        )
        kinds = [(e[0], e[1]) for e in logger.events]
        assert ("phase_start", "prompt_build") in kinds
        # phase_end for prompt_build with outcome success.
        end_events = [
            e for e in logger.events
            if e[0] == "phase_end" and e[1] == "prompt_build"
        ]
        assert len(end_events) == 1
        assert end_events[0][2] == "success"

    def test_run_step_emits_claude_call_phase_pair_with_start_event(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        captured_prompt: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            captured_prompt.append(prompt)
            return (0, "")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            run_logger=logger,
        )
        kinds = [(e[0], e[1]) for e in logger.events]
        assert ("phase_start", "claude_call") in kinds

        ccs = [e for e in logger.events if e[0] == "claude_call_start"]
        assert len(ccs) == 1
        # ccs[0] = ("claude_call_start", phase, attempt, prompt_bytes, extra)
        assert ccs[0][1] == "claude_call"
        assert ccs[0][2] == 1
        assert ccs[0][3] == len(captured_prompt[0].encode("utf-8"))

        cc_ends = [
            e for e in logger.events
            if e[0] == "phase_end" and e[1] == "claude_call"
        ]
        assert len(cc_ends) == 1
        assert cc_ends[0][2] == "success"

    def test_run_step_logs_streaming_transport_prompt_bytes(
        self, plan_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from types import SimpleNamespace

        from plan_tool import launcher
        from plan_tool.backend import PromptTransport

        captured_prompt: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            captured_prompt.append(prompt)
            return (0, "")

        logger = _RecordingLogger()
        monkeypatch.setattr(
            launcher,
            "get_active_backend",
            lambda: SimpleNamespace(
                streaming_transport=lambda prompt: PromptTransport(
                    ["backend", "--stdin"], stdin_text=f"wire:{prompt}"
                )
            ),
        )

        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            run_logger=logger,
        )

        ccs = [e for e in logger.events if e[0] == "claude_call_start"]
        assert len(ccs) == 1
        assert ccs[0][3] == len(f"wire:{captured_prompt[0]}".encode("utf-8"))

    def test_recording_logger_accepts_backend_spawn_and_termination_calls(
        self, plan_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Batch-authoring-observability step 7's runner-native
        ``backend_spawn``/``backend_termination`` bracket fires for *any*
        non-``None`` writer passed to ``backend_runner.run_streaming_once``
        — including the bare ones ``run``'s real streaming path passes.
        Step 5 deliberately left these two methods off ``_RecordingLogger``,
        noting ``shell_invoker`` didn't call them yet; without them here,
        the calls would raise (caught by the runner's own exception
        wrapping) and never actually be exercised."""
        from plan_tool import launcher

        monkeypatch.setattr(
            launcher.subprocess, "Popen",
            _make_popen_factory([(["ok\n"], [], 0)]),
        )

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=launcher.shell_invoker,
            run_logger=logger,
        )

        assert any(e[0] == "backend_spawn" for e in logger.events)
        assert any(e[0] == "backend_termination" for e in logger.events)

    def test_run_step_dry_run_emits_only_prompt_build_phase_pair(
        self, plan_path: Path, tmp_path: Path, capsys
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            dry_run=True,
            run_logger=logger,
        )
        phases_started = [
            e[1] for e in logger.events if e[0] == "phase_start"
        ]
        assert phases_started == ["prompt_build"]
        # No claude_call_start either — no subprocess ran.
        assert not any(e[0] == "claude_call_start" for e in logger.events)

    def test_run_step_nonzero_exit_marks_claude_call_phase_error(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (2, "")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=fake_invoker,
            run_logger=logger,
        )
        cc_ends = [
            e for e in logger.events
            if e[0] == "phase_end" and e[1] == "claude_call"
        ]
        assert len(cc_ends) == 1
        assert cc_ends[0][2] == "error"
        # rc was stamped onto the extras dict.
        assert cc_ends[0][3].get("rc") == 2

    def test_run_step_invoker_raises_still_emits_claude_call_phase_end(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        def fake_invoker(prompt: str) -> tuple[int, str]:
            raise RuntimeError("boom")

        logger = _RecordingLogger()
        with pytest.raises(RuntimeError):
            run_step(
                plan_path,
                repo_root=tmp_path,
                invoker=fake_invoker,
                run_logger=logger,
            )
        # Both phase_start("claude_call") and a matching phase_end with
        # outcome=error must have been recorded before the raise
        # propagated.
        cc_starts = [
            e for e in logger.events
            if e[0] == "phase_start" and e[1] == "claude_call"
        ]
        cc_ends = [
            e for e in logger.events
            if e[0] == "phase_end" and e[1] == "claude_call"
        ]
        assert len(cc_starts) == 1
        assert len(cc_ends) == 1
        assert cc_ends[0][2] == "error"


class TestApplyFindingRunLog:
    """``apply_finding`` emits ``claude_call_start`` events around its
    one (or two) invoker calls but never emits a wrapping
    ``apply_finding_dispatch`` phase pair — that frame belongs to the
    caller in ``cli._dispatch_apply_finding``."""

    def test_apply_finding_no_logger_writes_nothing(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            return 0, "## Summary\n- flipped\n\n## Verdict\nAPPLIED\n"

        apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="flip step 1", step_id=1,
            invoker=fake_invoker,
        )
        runs_dir = tmp_path / ".plan-tool" / "runs"
        if runs_dir.exists():
            assert not any(p.is_file() for p in runs_dir.rglob("*"))

    def test_apply_finding_emits_one_claude_call_start_on_happy_path(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            # Delta-neutral edit (see TestApplyFindingValidationDelta):
            # bump priority, leave step 1 `done`, so no introduced finding
            # triggers an auto-fix follow-up call.
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("priority: low", "priority: medium"),
                encoding="utf-8",
            )
            return 0, "## Summary\n- bumped priority\n\n## Verdict\nAPPLIED\n"

        logger = _RecordingLogger()
        apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="bump priority", step_id=1,
            invoker=fake_invoker, run_logger=logger,
        )
        ccs = [e for e in logger.events if e[0] == "claude_call_start"]
        assert len(ccs) == 1
        # Phase is apply_finding_dispatch on attempt=1.
        assert ccs[0][1] == "apply_finding_dispatch"
        assert ccs[0][2] == 1

    def test_apply_finding_writes_an_end_for_each_start_even_when_invoker_raises(
        self, tmp_path: Path
    ) -> None:
        """The streaming invoker emits no end itself (0 ends for 26 starts in
        the token ledger), so apply_finding writes it; a raise must not orphan
        the start."""
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def ok(prompt: str) -> tuple[int, str]:
            return 0, "## Summary\n- none\n\n## Verdict\nAPPLIED\n"

        logger = _RecordingLogger()
        apply_finding(
            plan_path, repo_root=tmp_path, finding_body="x", step_id=1,
            invoker=ok, run_logger=logger,
        )
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(ends) == 1 and ends[0][1]["rc"] == 0

        def boom(prompt: str) -> tuple[int, str]:
            raise RuntimeError("spawn failed")

        logger = _RecordingLogger()
        with pytest.raises(RuntimeError):
            apply_finding(
                plan_path, repo_root=tmp_path, finding_body="x", step_id=1,
                invoker=boom, run_logger=logger,
            )
        starts = [e for e in logger.events if e[0] == "claude_call_start"]
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(starts) == 1 and len(ends) == 1 and ends[0][1]["rc"] == 1

    def test_apply_finding_emits_two_claude_call_starts_on_followup(
        self, tmp_path: Path
    ) -> None:
        """Sequence the fake invoker to introduce a new finding on the
        first call and clean it up on the second, exercising the
        auto-fix follow-up path."""
        from plan_tool.launcher import apply_finding

        # Plan with a populated ## Overview that the first apply will
        # replace with a placeholder (introducing a body-completeness
        # finding); the follow-up restores it.
        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Auto-Fix\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n"
            "Real description.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")

        call_count = {"n": 0}

        def fake_invoker(prompt: str) -> tuple[int, str]:
            call_count["n"] += 1
            current = plan_path.read_text(encoding="utf-8")
            if call_count["n"] == 1:
                # First call: regress the overview.
                plan_path.write_text(
                    current.replace(
                        "## Overview\nReal description.\n",
                        "## Overview\n_(TODO)_\n",
                    ),
                    encoding="utf-8",
                )
                return 0, "## Summary\n- placeholder\n\n## Verdict\nAPPLIED\n"
            # Second call: restore.
            plan_path.write_text(
                current.replace(
                    "## Overview\n_(TODO)_\n",
                    "## Overview\nRestored description.\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- restored\n\n## Verdict\nAPPLIED\n"

        logger = _RecordingLogger()
        apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder", step_id=1,
            invoker=fake_invoker, run_logger=logger,
        )
        ccs = [e for e in logger.events if e[0] == "claude_call_start"]
        assert len(ccs) == 2
        assert ccs[0][2] == 1
        assert ccs[1][2] == 2
        # Both are under apply_finding_dispatch phase.
        assert ccs[0][1] == "apply_finding_dispatch"
        assert ccs[1][1] == "apply_finding_dispatch"
        # The follow-up's prompt is strictly larger than the original
        # (it embeds the formatted-findings body).
        assert ccs[1][3] > ccs[0][3]

    def test_apply_finding_no_followup_call_when_auto_fix_disabled(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = tmp_path / "plan.md"
        plan_path.write_text(
            "---\n"
            "title: Auto-Fix-Off\n"
            "status: in-progress\n"
            "priority: low\n"
            "steps:\n"
            "  - id: 1\n"
            "    title: Build\n"
            "    files: [foo.py]\n"
            "    status: done\n"
            "---\n"
            "\n"
            "## Overview\n"
            "Real description.\n",
            encoding="utf-8",
        )
        (tmp_path / "foo.py").write_text("x\n", encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace(
                    "## Overview\nReal description.\n",
                    "## Overview\n_(TODO)_\n",
                ),
                encoding="utf-8",
            )
            return 0, "## Summary\n- placeholder\n\n## Verdict\nAPPLIED\n"

        logger = _RecordingLogger()
        apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="placeholder", step_id=1,
            invoker=fake_invoker, run_logger=logger,
            auto_fix_introduced=False,
        )
        ccs = [e for e in logger.events if e[0] == "claude_call_start"]
        assert len(ccs) == 1
        assert ccs[0][2] == 1

    def test_apply_finding_emits_no_extra_phase_starts(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import apply_finding

        plan_path = _write_plan_for_apply(tmp_path)

        def fake_invoker(prompt: str) -> tuple[int, str]:
            current = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                current.replace("status: done", "status: current"),
                encoding="utf-8",
            )
            return 0, "## Summary\n- flipped\n\n## Verdict\nAPPLIED\n"

        logger = _RecordingLogger()
        apply_finding(
            plan_path, repo_root=tmp_path,
            finding_body="flip step 1", step_id=1,
            invoker=fake_invoker, run_logger=logger,
        )
        # apply_finding never emits its own phase_start / phase_end
        # — the caller (_dispatch_apply_finding in cli.py) owns the
        # ``apply_finding_dispatch`` phase pair.
        assert not any(e[0] == "phase_start" for e in logger.events)
        assert not any(e[0] == "phase_end" for e in logger.events)


# ──────────────────────────────────────────────────────────────────────────
# shell_invoker retry behavior
# ──────────────────────────────────────────────────────────────────────────
#
# shell_invoker is the production claude invoker for `plan-tool run`.
# Unlike claude_invoke (shell.py), it streams stdout/stderr via Popen
# threads while also accumulating both buffers for failure classification.
# Tests below mock subprocess.Popen and validate that the same retry
# protocol from shell.claude_invoke applies here too.


def _recording_stream_backend(base, seen_parse: list[str]):
    """Return ``base`` with a parser that records backend selection."""

    def parse_stream_line(_line: str, *, bytes_in: int):
        seen_parse.append(base.name)
        return None

    return replace(base, parse_stream_line=parse_stream_line)


def test_shell_invoker_returns_success_first_try(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Happy path: rc=0, no retry, stdout buffer returned."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["hello\n", "world\n"], [], 0),
        ]),
    )
    rc, out = launcher.shell_invoker("p")
    assert (rc, out) == (0, "hello\nworld\n")


def test_shell_invoker_accepts_empty_success_after_workspace_edits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The streaming runner has no response-body contract on success."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            ([], [], 0),
        ]),
    )

    assert launcher.shell_invoker("p") == (0, "")


def test_shell_invoker_retries_transient_runner_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A retryable runner exception reaches the shared recovery loop."""
    from plan_tool import launcher
    from plan_tool.launcher import ClaudeRunStats

    attempts: list[int] = []

    def fake_streaming_once(
        _prompt, *, run_logger=None, phase="claude_call", attempt=1,
        sibling_log_dir=None,
    ):
        attempts.append(attempt)
        if attempt == 1:
            raise OSError("temporarily unavailable while spawning backend")
        return 0, "recovered\n", "", ClaudeRunStats()

    monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming_once)

    assert launcher.shell_invoker(
        "p", _sleep=lambda _seconds: None, max_transient_retries=2,
        transient_base_delay=0.0,
    ) == (0, "recovered\n")
    assert attempts == [1, 2]


def test_shell_invoker_returns_spawn_exception_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing backend executable becomes a classified failure outcome."""
    from plan_tool import launcher

    calls: list[int] = []

    def fake_streaming_once(
        _prompt, *, run_logger=None, phase="claude_call", attempt=1,
        sibling_log_dir=None,
    ):
        calls.append(attempt)
        raise FileNotFoundError("backend executable is missing")

    monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming_once)

    assert launcher.shell_invoker("p") == (
        1,
        "FileNotFoundError: backend executable is missing",
    )
    assert calls == [1]


def test_shell_invoker_returns_defensive_runner_exception_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-retryable runner exception no longer crashes the run command."""
    from plan_tool import launcher

    calls: list[int] = []

    def fake_streaming_once(
        _prompt, *, run_logger=None, phase="claude_call", attempt=1,
        sibling_log_dir=None,
    ):
        calls.append(attempt)
        raise RuntimeError("streaming process stdout/stderr pipes are missing")

    monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming_once)

    assert launcher.shell_invoker(
        "p", _sleep=lambda _seconds: None, transient_base_delay=0.0,
    ) == (1, "RuntimeError: streaming process stdout/stderr pipes are missing")
    assert calls == [1]


@pytest.mark.parametrize("failure", (KeyboardInterrupt, SystemExit))
def test_shell_invoker_reraises_runner_interrupts(
    monkeypatch: pytest.MonkeyPatch, failure: type[BaseException]
) -> None:
    """The runner adapter must not turn operator/process exits into retries."""
    from plan_tool import launcher

    def fake_streaming_once(*_args, **_kwargs):
        raise failure()

    monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming_once)

    with pytest.raises(failure):
        launcher.shell_invoker("p")


def test_shell_invoker_waits_then_retries_on_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate-limit then success: one wait, two Popen calls."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit. resets 3am\n"], [], 1),
            (["recovered\n"], [], 0),
        ]),
    )

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    rc, out = launcher.shell_invoker(
        "p",
        _sleep=fake_sleep,
        _clock=fake_clock,
        wait_on_rate_limit=True,
    )
    assert (rc, out) == (0, "recovered\n")
    assert sleeps  # countdown ran at least once


@pytest.mark.parametrize(
    "policy",
    [
        claude_errors.OnRateLimitPolicy(claude_errors.OnRateLimitAction.WAIT),
        claude_errors.OnRateLimitPolicy(claude_errors.OnRateLimitAction.ASK),
        claude_errors.OnRateLimitPolicy(
            claude_errors.OnRateLimitAction.SWITCH, fallback_backend="codex"
        ),
    ],
)
def test_shell_invoker_plan_quota_bypasses_every_rate_limit_policy_action(
    monkeypatch: pytest.MonkeyPatch,
    policy: claude_errors.OnRateLimitPolicy,
) -> None:
    """A confirmed quota returns after one streaming attempt under every policy."""
    from plan_tool import launcher
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend

    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy", policy)
    attempts: list[int] = []

    def fake_streaming_once(_prompt, *, attempt=1, **_kwargs):
        attempts.append(attempt)
        return 1, _CURSOR_MONTHLY_PLAN_QUOTA, "", launcher.ClaudeRunStats()

    def unexpected_recovery_action(*_args, **_kwargs):
        raise AssertionError("plan quota must not start rate-limit recovery")

    class Guard:
        def __call__(self, _outcome):
            raise AssertionError("plan quota must not consult the retry guard")

    monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming_once)
    monkeypatch.setattr(launcher, "_select_rate_limit_backend", unexpected_recovery_action)
    monkeypatch.setattr(launcher, "_can_prompt_on_rate_limit", unexpected_recovery_action)
    monkeypatch.setattr(launcher, "_ask_rate_limit_action", unexpected_recovery_action)
    monkeypatch.setattr(
        launcher,
        "make_partial_mutation_retry_guard",
        lambda *_args, **_kwargs: Guard(),
    )

    rc, stdout = launcher.shell_invoker(
        "prompt",
        _sleep=unexpected_recovery_action,
    )

    assert (rc, stdout) == (1, _CURSOR_MONTHLY_PLAN_QUOTA)
    assert attempts == [1]


def test_shell_invoker_records_cursor_plan_quota_pattern_near_miss(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool import launcher
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend, spawn_cwd
    from plan_tool.telemetry import read_decisions

    near_miss = (
        "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit. The monthly cycle ends on 8/24/2026."
    )
    set_active_backend(CURSOR_BACKEND)
    monkeypatch.setattr(
        launcher,
        "_run_streaming_once",
        lambda *_args, **_kwargs: (1, near_miss, "", launcher.ClaudeRunStats()),
    )
    with spawn_cwd(tmp_path):
        assert launcher.shell_invoker("prompt", wait_on_rate_limit=False) == (1, near_miss)

    (event,) = read_decisions(tmp_path)
    assert event.kind == "backend-pattern-miss"
    assert event.plan_slug == ""
    assert event.context == {
        "backend": "cursor",
        "classified_as": "rate_limit",
        "markers": [
            "action-required-error",
            "usage-limit",
            "switch-model",
            "spend-limit",
            "monthly-cycle",
        ],
        "excerpt": near_miss,
        "phase": "claude_call",
    }


def test_shell_invoker_skips_quota_near_miss_observer_before_retry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from plan_tool import launcher
    from plan_tool.backend import CURSOR_BACKEND, set_active_backend, spawn_cwd
    from plan_tool.telemetry import read_decisions

    near_miss = (
        "ActionRequiredError — usage limit reached. Switch models or set a "
        "Spend Limit before the monthly cycle ends."
    )
    set_active_backend(CURSOR_BACKEND)

    def fake_leaf(**kwargs):
        classification = kwargs["classify"]((1, near_miss, ""))
        kwargs["on_nonsuccess"](
            (1, near_miss, ""), classification.failure, True, True
        )
        return 1, near_miss

    monkeypatch.setattr(launcher, "run_with_rate_limit_recovery", fake_leaf)

    with spawn_cwd(tmp_path):
        assert launcher.shell_invoker("prompt") == (1, near_miss)

    assert read_decisions(tmp_path) == []


def test_shell_invoker_rate_limit_wait_emits_no_progress_or_stall_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The retry-loop wait between a rate-limited attempt and its retry emits
    only ``backend_recovery_wait`` — none of ``_run_streaming_once``'s own
    per-attempt stream/progress/stall events, since no child process is alive
    during the wait itself. Binds a run-log recorder through
    ``launcher._run_logger_var`` (the seam ``run_step`` sets around its own
    ``invoker(prompt)`` call) rather than passing ``run_logger`` directly,
    since that ContextVar is the only path by which the real wait window
    could reach a logger at all.

    ``_StreamRecordingLogger`` comes from tests/test_backend_runner.py and
    ``_make_popen_factory`` from tests/subprocess_doubles.py, both imported
    at the top of this module.
    """
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit. resets 3am\n"], [], 1),
            (["recovered\n"], [], 0),
        ]),
    )

    logger = _StreamRecordingLogger()
    seen_run_loggers: list[object] = []
    real_streaming_once = launcher._run_streaming_once

    def spy_streaming_once(prompt, *, run_logger=None, phase="claude_call",
                            attempt=1, sibling_log_dir=None):
        # Proves the run logger really is reachable at each attempt (not
        # merely absent from this call path) — the pairing the plan step
        # asks for, so the assertion below reads as "unused", not
        # "out of scope". See ``TestShellInvokerContextVarPlumbing`` for
        # the same technique used against a sentinel instead of a real call.
        seen_run_loggers.append(run_logger)
        return real_streaming_once(
            prompt, run_logger=run_logger, phase=phase, attempt=attempt,
            sibling_log_dir=sibling_log_dir,
        )

    monkeypatch.setattr(launcher, "_run_streaming_once", spy_streaming_once)

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    token = launcher._run_logger_var.set(logger)
    try:
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=fake_sleep,
            _clock=fake_clock,
            wait_on_rate_limit=True,
        )
    finally:
        launcher._run_logger_var.reset(token)

    assert (rc, out) == (0, "recovered\n")
    assert sleeps  # the wait actually ran
    assert seen_run_loggers == [logger, logger]
    assert logger.progress_events == []
    assert logger.stall_events == []
    assert len(logger.recovery_wait_events) == 1
    assert logger.recovery_wait_events[0]["reason"] == "rate_limit"
    assert logger.recovery_wait_events[0]["phase"] == "claude_call"


def test_shell_invoker_skips_wait_when_flag_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit\n"], [], 1),
        ]),
    )
    sleeps: list[float] = []
    rc, out = launcher.shell_invoker(
        "p",
        _sleep=lambda s: sleeps.append(s),
        wait_on_rate_limit=False,
    )
    assert rc == 1
    assert "hit your limit" in out
    assert sleeps == []


def test_shell_invoker_retries_transient_with_exponential_backoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["request timed out\n"], [], 1),
            (["ECONNRESET\n"], [], 1),
            (["finally ok\n"], [], 0),
        ]),
    )
    sleeps: list[float] = []
    rc, out = launcher.shell_invoker(
        "p",
        _sleep=lambda s: sleeps.append(s),
        max_transient_retries=3,
        transient_base_delay=2.0,
    )
    assert (rc, out) == (0, "finally ok\n")
    assert sleeps == [2.0, 4.0]


def test_shell_invoker_emits_backend_recovery_wait_on_rate_limit_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extends ``test_shell_invoker_waits_then_retries_on_rate_limit``: a
    writer bound through ``launcher._run_logger_var`` sees one
    ``backend_recovery_wait`` row before the retried Popen call, tagged
    ``phase="claude_call"``."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit. resets 3am\n"], [], 1),
            (["recovered\n"], [], 0),
        ]),
    )

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    logger = _RecordingLogger()
    token = launcher._run_logger_var.set(logger)
    try:
        rc, out = launcher.shell_invoker(
            "p", _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
        )
    finally:
        launcher._run_logger_var.reset(token)

    assert (rc, out) == (0, "recovered\n")
    waits = [e for e in logger.events if e[0] == "backend_recovery_wait"]
    assert len(waits) == 1
    # ("backend_recovery_wait", phase, attempt, reason, delay_ms, next_attempt, backend, extra)
    assert waits[0][1] == "claude_call"
    assert waits[0][3] == "rate_limit"
    assert waits[0][5] == 2  # next_attempt


def test_shell_invoker_emits_backend_recovery_wait_on_transient_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Extends ``test_shell_invoker_retries_transient_with_exponential_backoff``:
    a bound writer sees one ``backend_recovery_wait`` row per transient
    retry."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["request timed out\n"], [], 1),
            (["ECONNRESET\n"], [], 1),
            (["finally ok\n"], [], 0),
        ]),
    )

    logger = _RecordingLogger()
    token = launcher._run_logger_var.set(logger)
    try:
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=lambda s: None,
            max_transient_retries=3,
            transient_base_delay=2.0,
        )
    finally:
        launcher._run_logger_var.reset(token)

    assert (rc, out) == (0, "finally ok\n")
    waits = [e for e in logger.events if e[0] == "backend_recovery_wait"]
    assert [w[3] for w in waits] == ["transient", "transient"]
    assert [w[4] for w in waits] == [2000, 4000]
    assert [w[5] for w in waits] == [2, 3]


def test_shell_invoker_keyboard_interrupt_during_recovery_wait_propagates_after_run_interrupted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A ``KeyboardInterrupt`` raised out of the rate-limit wait's countdown
    tick emits one ``run_interrupted`` row (when a writer is bound) and
    still propagates out of ``shell_invoker`` unchanged."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit. resets 3am\n"], [], 1),
            (["should not run\n"], [], 0),
        ]),
    )

    def fake_clock() -> float:
        return 1000.0

    def interrupt_sleep(secs: float) -> None:
        raise KeyboardInterrupt

    logger = _RecordingLogger()
    token = launcher._run_logger_var.set(logger)
    try:
        with pytest.raises(KeyboardInterrupt):
            launcher.shell_invoker(
                "p",
                _sleep=interrupt_sleep,
                _clock=fake_clock,
                wait_on_rate_limit=True,
            )
    finally:
        launcher._run_logger_var.reset(token)

    interrupts = [e for e in logger.events if e[0] == "run_interrupted"]
    assert len(interrupts) == 1
    # ("run_interrupted", phase, attempt, source, signal, extra)
    assert interrupts[0][1] == "claude_call"
    assert interrupts[0][3] == "recovery_wait"


def test_run_step_with_run_logger_gets_backend_recovery_wait_via_shell_invoker(
    plan_path: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An end-to-end case through ``run_step(..., run_logger=...)``, with a
    fake invoker wrapping the real ``shell_invoker`` (Popen mocked to
    rate-limit once), proves the ``_run_logger_var`` plumbing ``run_step``
    already sets around ``invoker(prompt)`` reaches the new wrapper with no
    new per-call-site wiring in ``run_step`` itself."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit. resets 3am\n"], [], 1),
            (["recovered\n"], [], 0),
        ]),
    )

    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    def fake_invoker(prompt: str) -> tuple[int, str]:
        return launcher.shell_invoker(
            prompt, _sleep=fake_sleep, _clock=fake_clock, wait_on_rate_limit=True,
        )

    logger = _RecordingLogger()
    run_step(
        plan_path,
        repo_root=tmp_path,
        invoker=fake_invoker,
        run_logger=logger,
    )

    waits = [e for e in logger.events if e[0] == "backend_recovery_wait"]
    assert len(waits) == 1
    assert waits[0][3] == "rate_limit"


def test_shell_invoker_context_overflow_does_not_retry(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["prompt is too long\n"], [], 1),
        ]),
    )
    rc, _ = launcher.shell_invoker("p", _sleep=lambda s: None)
    assert rc == 1
    err = capsys.readouterr().err
    assert "split a large seed" in err


def test_shell_invoker_detects_rate_limit_on_stderr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rate-limit copy on stderr-only must still trigger the wait path.

    Streaming claude can put transport-layer errors on stderr while
    stdout stays clean — without stderr capture, we'd miss this.
    """
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            ([], ["You've hit your limit\n"], 1),
            (["ok\n"], [], 0),
        ]),
    )
    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    rc, out = launcher.shell_invoker(
        "p",
        _sleep=fake_sleep,
        _clock=fake_clock,
        wait_on_rate_limit=True,
    )
    assert (rc, out) == (0, "ok\n")
    assert sleeps  # waited despite empty stdout


def test_shell_invoker_rate_limit_non_tty_does_not_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import launcher

    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr(
        launcher,
        "ask_on_rate_limit_action",
        lambda *, current_backend_name: pytest.fail("must not prompt"),
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit\n"], [], 1),
            (["ok\n"], [], 0),
        ]),
    )
    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    rc, out = launcher.shell_invoker(
        "p",
        _sleep=fake_sleep,
        _clock=fake_clock,
        wait_on_rate_limit=True,
    )

    assert (rc, out) == (0, "ok\n")
    assert sleeps


def test_shell_invoker_rate_limit_menu_stop_returns_failed_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import launcher
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr(
        launcher,
        "ask_on_rate_limit_action",
        lambda *, current_backend_name: OnRateLimitAskResult(
            action=OnRateLimitAction.STOP
        ),
    )
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit\n"], [], 1),
        ]),
    )

    sleeps: list[float] = []
    rc, out = launcher.shell_invoker(
        "p",
        _sleep=lambda s: sleeps.append(s),
    )

    assert rc == 1
    assert "hit your limit" in out
    assert sleeps == []


def test_shell_invoker_rate_limit_menu_switch_reselects_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from contextlib import contextmanager

    from plan_tool import launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        CODEX_BACKEND,
        get_active_backend,
        scoped_active_backend,
        spawn_cwd,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    codex_backend = _recording_stream_backend(CODEX_BACKEND, seen_parse)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    monkeypatch.setattr(
        launcher,
        "ask_on_rate_limit_action",
        lambda *, current_backend_name: OnRateLimitAskResult(
            action=OnRateLimitAction.SWITCH,
            switch_backend_name="codex",
        ),
    )
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )
    selections: list[tuple[str, Path]] = []

    @contextmanager
    def fake_scoped_select_active_backend(
        name: str, *, repo_root: Path, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        selections.append((name, repo_root))
        assert name == "codex"
        with scoped_active_backend(codex_backend):
            yield object()

    monkeypatch.setattr(
        launcher, "scoped_select_active_backend", fake_scoped_select_active_backend
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["recovered on codex\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )

    set_active_backend(claude_backend)
    try:
        with spawn_cwd(tmp_path):
            rc, out = launcher.shell_invoker("p")

        assert (rc, out) == (0, "recovered on codex\n")
        assert selections == [("codex", tmp_path)]
        assert [argv[0] for argv in seen_argv] == ["claude", "codex"]
        assert seen_parse == ["claude", "codex"]
        assert get_active_backend() is claude_backend
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_policy_switches_without_prompt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A process-wide SWITCH policy consumes ``fallback_backend`` and retries
    on it without opening the interactive menu, even on a TTY."""
    from contextlib import contextmanager

    from plan_tool import claude_errors, launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        CODEX_BACKEND,
        get_active_backend,
        scoped_active_backend,
        spawn_cwd,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    codex_backend = _recording_stream_backend(CODEX_BACKEND, seen_parse)
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)

    def _fail_if_prompted(**_kwargs):  # pragma: no cover - must not run
        raise AssertionError("SWITCH policy must not open the interactive menu")

    monkeypatch.setattr(launcher, "ask_on_rate_limit_action", _fail_if_prompted)
    selections: list[tuple[str, Path]] = []

    @contextmanager
    def fake_scoped_select_active_backend(
        name: str, *, repo_root: Path, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        selections.append((name, repo_root))
        assert name == "codex"
        with scoped_active_backend(codex_backend):
            yield object()

    monkeypatch.setattr(
        launcher, "scoped_select_active_backend", fake_scoped_select_active_backend
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["recovered on codex\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )

    set_active_backend(claude_backend)
    try:
        with spawn_cwd(tmp_path):
            rc, out = launcher.shell_invoker("p")

        assert (rc, out) == (0, "recovered on codex\n")
        assert selections == [("codex", tmp_path)]
        assert [argv[0] for argv in seen_argv] == ["claude", "codex"]
        assert seen_parse == ["claude", "codex"]
        assert get_active_backend() is claude_backend
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_policy_synthesizes_model_family_backend(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A documented inferred backend remains a valid switch target."""
    from plan_tool import claude_errors, launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        get_active_backend,
        spawn_cwd,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    config_dir = tmp_path / ".plan-tool"
    config_dir.mkdir()
    (config_dir / "backends.json").write_text(
        '{"backends": {"gemini": {"extra_streaming_argv": ["--project"]}, '
        '"typo": {"model": "ignored"}}}',
        encoding="utf-8",
    )
    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH, fallback_backend="gemini"),
    )
    monkeypatch.setattr(launcher.shutil, "which", lambda _binary: "/usr/bin/tool")
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["recovered on gemini\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )

    set_active_backend(CLAUDE_BACKEND)
    try:
        with spawn_cwd(tmp_path):
            assert launcher.shell_invoker("p") == (0, "recovered on gemini\n")
        assert [argv[0] for argv in seen_argv] == ["claude", "gemini"]
        assert seen_argv[1] == ["gemini", "--project", "p"]
        err = capsys.readouterr().err
        assert "unknown backend 'typo'" in err
        assert "provisional descriptor" in err
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_policy_degrades_to_wait_when_fallback_bad(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SWITCH whose fallback backend can't be selected degrades to waiting
    and retrying rather than aborting the run (launcher parity with shell)."""
    from plan_tool import claude_errors, launcher
    from plan_tool.backend import CLAUDE_BACKEND, get_active_backend, set_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="bogus"))
    selected: list[str] = []

    def bad_select(
        name: str, *, repo_root, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        selected.append(name)
        raise ValueError(f"unknown backend {name!r}")

    monkeypatch.setattr(launcher, "scoped_select_active_backend", bad_select)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["recovered\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 1_000_000

    set_active_backend(claude_backend)
    try:
        rc, out = launcher.shell_invoker(
            "p", _sleep=fake_sleep, _clock=lambda: clock_state["t"]
        )

        assert (rc, out) == (0, "recovered\n")
        assert selected == ["bogus"]
        assert [argv[0] for argv in seen_argv] == ["claude", "claude"]
        assert seen_parse == ["claude", "claude"]
        assert get_active_backend() is claude_backend
        assert sleeps, "expected a fallback wait after the failed switch"
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_policy_degrades_when_fallback_binary_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A registered fallback with a missing executable waits on original backend."""
    from plan_tool import claude_errors, launcher
    from plan_tool.backend import CLAUDE_BACKEND, get_active_backend, set_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        OnRateLimitPolicy(
            action=OnRateLimitAction.SWITCH,
            fallback_backend="codex",
        ),
    )
    monkeypatch.setattr(
        launcher.shutil,
        "which",
        lambda name: "/usr/bin/claude" if name == "claude" else None,
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["recovered\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 1_000_000

    set_active_backend(claude_backend)
    try:
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=fake_sleep,
            _clock=lambda: clock_state["t"],
        )

        assert (rc, out) == (0, "recovered\n")
        assert [argv[0] for argv in seen_argv] == ["claude", "claude"]
        assert seen_parse == ["claude", "claude"]
        assert get_active_backend() is claude_backend
        assert sleeps, "expected a fallback wait after the missing fallback binary"
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_to_active_backend_does_not_hot_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A SWITCH whose fallback names the already-active backend must not
    self-switch or hot-loop (launcher parity). Exactly two rate-limits are
    provided: the bounded code makes two Popen calls, then gives up; a
    hot-loop would call Popen a third time and trip the factory's assertion."""
    from plan_tool import claude_errors, launcher
    from plan_tool.backend import get_active_backend
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="claude"))
    selected: list[str] = []

    def spy_select(
        name: str, *, repo_root, model=None, fallback_factory=None,
        known_override_names=(),
    ):  # pragma: no cover
        selected.append(name)

    monkeypatch.setattr(launcher, "scoped_select_active_backend", spy_select)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit\n"], [], 1),
            (["You've hit your limit\n"], [], 1),
        ]),
    )

    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 1_000_000

    rc, _out = launcher.shell_invoker(
        "p", _sleep=fake_sleep, _clock=lambda: clock_state["t"]
    )

    assert rc == 1  # bounded — returns rather than hanging / over-calling Popen
    assert selected == []  # never self-switched to the already-active backend
    assert get_active_backend() is original_backend
    assert sleeps, "expected one fallback wait before giving up"


def test_shell_invoker_rate_limit_switch_resets_wait_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from plan_tool import launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        CODEX_BACKEND,
        get_active_backend,
        scoped_active_backend,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    codex_backend = _recording_stream_backend(CODEX_BACKEND, seen_parse)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)
    choices = iter([
        OnRateLimitAskResult(
            action=OnRateLimitAction.SWITCH,
            switch_backend_name="codex",
        ),
        OnRateLimitAskResult(action=OnRateLimitAction.WAIT),
    ])
    monkeypatch.setattr(
        launcher,
        "ask_on_rate_limit_action",
        lambda *, current_backend_name: next(choices),
    )
    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )

    @contextmanager
    def fake_scoped_select_active_backend(
        name: str, *, repo_root: Path, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        assert name == "codex"
        with scoped_active_backend(codex_backend):
            yield object()

    monkeypatch.setattr(
        launcher, "scoped_select_active_backend", fake_scoped_select_active_backend
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["You've hit your limit\n"], [], 1),
                (["ok after wait\n"], [], 0),
            ],
            seen_argv=seen_argv,
        ),
    )
    sleeps: list[float] = []
    clock_state = {"t": 1000.0}

    def fake_sleep(secs: float) -> None:
        sleeps.append(secs)
        clock_state["t"] += 10_000

    def fake_clock() -> float:
        return clock_state["t"]

    set_active_backend(claude_backend)
    try:
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=fake_sleep,
            _clock=fake_clock,
        )

        assert (rc, out) == (0, "ok after wait\n")
        assert [argv[0] for argv in seen_argv] == ["claude", "codex", "codex"]
        assert seen_parse == ["claude", "codex", "codex"]
        assert get_active_backend() is claude_backend
        assert sleeps
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_switch_policy_restores_after_fallback_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager
    from types import SimpleNamespace

    from plan_tool import claude_errors, launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        CODEX_BACKEND,
        get_active_backend,
        scoped_active_backend,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitPolicy

    original_backend = get_active_backend()
    seen_argv: list[list[str]] = []
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    codex_backend = _recording_stream_backend(CODEX_BACKEND, seen_parse)
    monkeypatch.setattr(claude_errors, "_default_on_rate_limit_policy",
                        OnRateLimitPolicy(action=OnRateLimitAction.SWITCH,
                                          fallback_backend="codex"))
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("sys.stderr.isatty", lambda: False)

    @contextmanager
    def fake_scoped_select_active_backend(
        name: str, *, repo_root: Path, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        assert name == "codex"
        with scoped_active_backend(codex_backend):
            yield object()

    monkeypatch.setattr(
        launcher, "scoped_select_active_backend", fake_scoped_select_active_backend
    )
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory(
            [
                (["You've hit your limit\n"], [], 1),
                (["You've hit your limit\n"], [], 1),
            ],
            seen_argv=seen_argv,
        ),
    )
    # The wait now happens in the claude_errors seam, so patch it there.
    monkeypatch.setattr(
        claude_errors,
        "wait_until_epoch",
        lambda *a, **k: SimpleNamespace(action=claude_errors.WaitUntilAction.STOP),
    )

    set_active_backend(claude_backend)
    try:
        rc, out = launcher.shell_invoker("p")

        assert rc == 1
        assert "hit your limit" in out
        assert [argv[0] for argv in seen_argv] == ["claude", "codex"]
        assert seen_parse == ["claude", "codex"]
        assert get_active_backend() is claude_backend
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_parallel_switches_are_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import contextmanager

    from plan_tool import launcher
    from plan_tool.backend import (
        CLAUDE_BACKEND,
        CODEX_BACKEND,
        get_active_backend,
        scoped_active_backend,
        set_active_backend,
    )
    from plan_tool.claude_errors import OnRateLimitAction, OnRateLimitAskResult

    original_backend = get_active_backend()
    seen_parse: list[str] = []
    claude_backend = _recording_stream_backend(CLAUDE_BACKEND, seen_parse)
    codex_backend = _recording_stream_backend(CODEX_BACKEND, seen_parse)
    cursor_backend = _recording_stream_backend(
        replace(
            CODEX_BACKEND,
            name="cursor",
            binary="cursor",
            streaming_argv=lambda prompt: ["cursor", prompt],
        ),
        seen_parse,
    )
    switched = {"a": "codex", "b": "cursor"}
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("sys.stderr.isatty", lambda: True)

    monkeypatch.setattr(
        claude_errors,
        "_default_on_rate_limit_policy",
        claude_errors.OnRateLimitPolicy(
            action=claude_errors.OnRateLimitAction.ASK
        ),
    )

    def fake_ask(**_kwargs):
        name = threading.current_thread().name
        return OnRateLimitAskResult(
            action=OnRateLimitAction.SWITCH,
            switch_backend_name=switched[name],
        )

    @contextmanager
    def fake_scoped_select_active_backend(
        name: str, *, repo_root: Path, model=None, fallback_factory=None,
        known_override_names=(),
    ):
        selected_backend = {
            "codex": codex_backend,
            "cursor": cursor_backend,
        }[name]
        with scoped_active_backend(selected_backend):
            yield object()

    monkeypatch.setattr(launcher, "ask_on_rate_limit_action", fake_ask)
    monkeypatch.setattr(
        launcher, "scoped_select_active_backend", fake_scoped_select_active_backend
    )

    a_on_fallback = threading.Event()
    b_done = threading.Event()
    seen: list[tuple[str, str]] = []
    seen_lock = threading.Lock()

    def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
        prompt = argv[-1]
        backend_name = argv[0]
        with seen_lock:
            seen.append((prompt, backend_name))
        if prompt == "a" and backend_name == "claude":
            return _FakeProc(["You've hit your limit\n"], [], 1)
        if prompt == "a" and backend_name == "codex":
            a_on_fallback.set()
            assert b_done.wait(2), "b did not run during a fallback scope"
            return _FakeProc(["a ok\n"], [], 0)
        if prompt == "b" and backend_name == "claude":
            assert a_on_fallback.is_set(), "b ran before a fallback scope"
            return _FakeProc(["You've hit your limit\n"], [], 1)
        if prompt == "b" and backend_name == "cursor":
            return _FakeProc(["b ok\n"], [], 0)
        raise AssertionError(f"unexpected Popen call: {argv!r}")

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    results: dict[str, tuple[int, str]] = {}
    post_backend: dict[str, str] = {}
    errors: list[BaseException] = []

    def run_a() -> None:
        try:
            results["a"] = launcher.shell_invoker("a")
            post_backend["a"] = get_active_backend().name
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)

    def run_b() -> None:
        try:
            assert a_on_fallback.wait(2), "a did not switch"
            results["b"] = launcher.shell_invoker("b")
            post_backend["b"] = get_active_backend().name
        except BaseException as exc:  # pragma: no cover - failure path
            errors.append(exc)
        finally:
            b_done.set()

    set_active_backend(claude_backend)
    try:
        threads = [
            threading.Thread(target=run_a, name="a"),
            threading.Thread(target=run_b, name="b"),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=3)

        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        assert results == {"b": (0, "b ok\n"), "a": (0, "a ok\n")}
        assert post_backend == {"b": "claude", "a": "claude"}
        assert seen == [
            ("a", "claude"),
            ("a", "codex"),
            ("b", "claude"),
            ("b", "cursor"),
        ]
        assert "codex" in seen_parse
        assert "cursor" in seen_parse
        assert get_active_backend() is claude_backend
    finally:
        set_active_backend(original_backend)


def test_shell_invoker_honors_module_default_when_kwarg_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``wait_on_rate_limit=None`` (the default) reads the module flag."""
    from plan_tool import claude_errors, launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["You've hit your limit\n"], [], 1),
        ]),
    )
    original = claude_errors.get_default_wait_on_rate_limit()
    try:
        claude_errors.set_default_wait_on_rate_limit(False)
        sleeps: list[float] = []
        rc, _ = launcher.shell_invoker(
            "p", _sleep=lambda s: sleeps.append(s)
        )
        assert rc == 1
        assert sleeps == []
    finally:
        claude_errors.set_default_wait_on_rate_limit(original)


def test_shell_invoker_routes_through_shared_leaf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``shell_invoker`` delegates its recovery cascade to the shared
    ``rate_limit_loop`` leaf. Guards the structural claim that the reroute
    happened — a red here is a wiring regression, not an expected adaptation."""
    from plan_tool import launcher

    calls: list[dict] = []

    def fake_leaf(**kwargs) -> tuple[int, str]:
        calls.append(kwargs)
        return 0, "ok\n"

    monkeypatch.setattr(launcher, "run_with_rate_limit_recovery", fake_leaf)
    rc, stdout = launcher.shell_invoker("p")
    assert (rc, stdout) == (0, "ok\n")
    assert len(calls) == 1


# ──────────────────────────────────────────────────────────────────────────
# Partial-mutation retry guard: ``shell_invoker`` refuses a transient/rate-limit
# re-invoke when the aborted turn already left uncommitted edits in the spawn
# cwd (BUG_BACKLOG RISK — the streaming double-apply).
# ──────────────────────────────────────────────────────────────────────────


def _popen_factory_with_edits(
    responses: list[tuple[list[str], list[str], int, Optional[str]]],
    *,
    repo: Path,
):
    """Popen replacement whose responses can each write a file into the spawn
    cwd before "returning" — simulating a turn that partially edits the tree
    then aborts. Each response is
    ``(stdout_lines, stderr_lines, returncode, write_path_or_None)``.

    The retry-guard consults ``_git_changed_paths`` (a real ``git status`` via
    ``subprocess.run``) on the real tmp repo, so ``git`` argv is delegated to
    the real ``Popen`` (captured before the monkeypatch); only the backend
    invocation is faked. Faking git too would both starve the response iterator
    and break ``subprocess.run``'s ``with Popen(...)`` (``_FakeProc`` is not a
    context manager).
    """
    import subprocess as _subprocess

    real_popen = _subprocess.Popen
    it = iter(responses)

    def fake_popen(_argv, **kwargs):
        if _argv and _argv[0] == "git":
            return real_popen(_argv, **kwargs)
        try:
            stdout_lines, stderr_lines, rc, write_path = next(it)
        except StopIteration:
            raise AssertionError("Popen called more times than expected")
        if write_path is not None:
            (repo / write_path).write_text("edited\n", encoding="utf-8")
        return _FakeProc(stdout_lines, stderr_lines, rc)

    return fake_popen


def _git_commit_all(repo: Path, message: str) -> None:
    import subprocess

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", message], cwd=repo, check=True, capture_output=True
    )


def test_shell_invoker_stops_transient_retry_on_partial_edit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A transient whose aborted turn edited the tree STOPs the retry: no
    re-invoke (Popen once), the transient's non-zero rc is returned, and the
    partial-mutation hint is surfaced."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [(["request timed out\n"], [], 1, "edited.py")],
            repo=tmp_path,
        ),
    )
    sleeps: list[float] = []
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=lambda s: sleeps.append(s),
            max_transient_retries=3,
        )
    assert rc == 1
    assert sleeps == []  # no backoff paid — STOP fires before the sleep
    err = capsys.readouterr().err
    assert "uncommitted edits" in err
    assert "edited.py" in err


def test_shell_invoker_git_read_failure_stops_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A git-read failure at guard-check time fails CLOSED: the transient is
    not re-driven (the tree can't be verified), so it surfaces terminally with
    a git-state hint rather than risking a double-apply. Reading the empty set
    on error (the old behavior) would have collapsed the delta and retried."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    # Repo readable at baseline (guard active), then `git status` fails at the
    # guard check (e.g. an index.lock). A non-git tree would instead read None
    # at baseline and stay inert — distinct from this genuine mid-run error.
    reads: list[int] = []

    def _flaky_git(_p):
        reads.append(1)
        return set() if len(reads) == 1 else None

    monkeypatch.setattr(launcher, "_git_changed_paths_or_none", _flaky_git)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([(["request timed out\n"], [], 1)]),
    )
    sleeps: list[float] = []
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=lambda s: sleeps.append(s),
            max_transient_retries=3,
        )
    assert rc == 1
    assert sleeps == []  # STOP before any backoff
    assert "could not read git state" in capsys.readouterr().err


def test_shell_invoker_stops_rate_limit_retry_on_partial_edit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same closure covers the rate-limit arm: a partial edit STOPs before
    the wait is paid (Popen once, no sleep), returning the rate-limit rc."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [(["You've hit your limit. resets 3am\n"], [], 1, "edited.py")],
            repo=tmp_path,
        ),
    )
    sleeps: list[float] = []
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p",
            _sleep=lambda s: sleeps.append(s),
            wait_on_rate_limit=True,
        )
    assert rc == 1
    assert sleeps == []  # STOP pre-empts the wait
    err = capsys.readouterr().err
    assert "uncommitted edits" in err


def test_shell_invoker_partial_edit_is_caught_on_first_attempt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Baseline is captured before attempt 1: the very first attempt's edit
    trips the guard (proving the snapshot isn't folded into attempt 1)."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [(["ECONNRESET\n"], [], 1, "first_attempt.py")],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert rc == 1  # Popen called exactly once (factory raises on a 2nd call)


def test_shell_invoker_gitignored_write_does_not_stop_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A gitignored write during the aborted turn leaves the delta empty
    (porcelain omits ignored paths), so the transient retries and succeeds."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    _git_commit_all(tmp_path, "add gitignore")  # clean baseline
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [
                (["request timed out\n"], [], 1, "ignored.txt"),
                (["recovered\n"], [], 0, None),
            ],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert (rc, out) == (0, "recovered\n")


def test_shell_invoker_preexisting_dirty_does_not_stop_retry(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A path already dirty before the call sits in the baseline; a transient
    whose aborted turn adds no new path retries as before."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    (tmp_path / "already_dirty.py").write_text("pre\n", encoding="utf-8")
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [
                (["request timed out\n"], [], 1, None),  # no new path
                (["recovered\n"], [], 0, None),
            ],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert (rc, out) == (0, "recovered\n")


def test_shell_invoker_bare_rerun_after_stop_rebaselines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Known limit: a *second* ``shell_invoker`` over a tree that still carries
    the leftover partial edits snapshots them into its baseline, so the delta is
    empty and the guard no longer fires — recovery is revert-first, not a bare
    re-run."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    # First invocation: partial edit → STOP (Popen once), edits left in tree.
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [(["request timed out\n"], [], 1, "leftover.py")],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc1, _ = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert rc1 == 1
    assert (tmp_path / "leftover.py").exists()  # partial work not reverted

    # Second invocation over the unreverted tree: leftover.py is now in the
    # baseline, so a transient adds no new path → delta empty → retries.
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [
                (["request timed out\n"], [], 1, None),
                (["recovered\n"], [], 0, None),
            ],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc2, out2 = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert (rc2, out2) == (0, "recovered\n")


def test_shell_invoker_retry_guard_inert_without_spawn_cwd(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No active spawn cwd → the guard is inert (retry_guard is None); a
    transient followed by success retries exactly as before."""
    from plan_tool import launcher

    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _make_popen_factory([
            (["request timed out\n"], [], 1),
            (["finally ok\n"], [], 0),
        ]),
    )
    rc, out = launcher.shell_invoker(
        "p", _sleep=lambda s: None, max_transient_retries=3
    )
    assert (rc, out) == (0, "finally ok\n")


def test_shell_invoker_stop_preserves_rc_contract(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The STOP path returns the just-failed attempt's non-zero rc (completion,
    not a findings code)."""
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    _git_init(tmp_path)
    monkeypatch.setattr(
        launcher.subprocess,
        "Popen",
        _popen_factory_with_edits(
            [(["request timed out\n"], [], 1, "edited.py")],
            repo=tmp_path,
        ),
    )
    with spawn_cwd(tmp_path):
        rc, out = launcher.shell_invoker(
            "p", _sleep=lambda s: None, max_transient_retries=3
        )
    assert rc == 1


class TestMutatingModes:
    """``MUTATING_MODES`` membership controls whether ``run_step``
    advances step state. The detail-side reconcile mode is read-only,
    so it must stay OUT of the set even though its name doesn't match
    one of the existing review-class tokens."""

    def test_detail_reconcile_is_not_in_mutating_modes(self) -> None:
        from plan_tool.launcher import MUTATING_MODES

        assert "detail-reconcile" not in MUTATING_MODES

    def test_reconcile_is_not_in_mutating_modes(self) -> None:
        from plan_tool.launcher import MUTATING_MODES

        assert "reconcile" not in MUTATING_MODES

    def test_run_reconcile_is_not_in_mutating_modes(self) -> None:
        """``run-reconcile`` is the code-side audit. Code edits land
        inline via ``acceptEdits`` in the launcher's
        ``shell_invoker``, but plan state — step.status / current
        promotion / lessons append — must NOT advance: the audit may
        well leave critical findings open, and advancing under that
        condition would silently mark the step done."""
        from plan_tool.launcher import MUTATING_MODES

        assert "run-reconcile" not in MUTATING_MODES

    def test_run_is_the_only_mutating_mode(self) -> None:
        from plan_tool.launcher import MUTATING_MODES

        assert MUTATING_MODES == frozenset({"run"})

    def test_run_step_with_mode_run_reconcile_is_read_only_at_plan_state_level(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """End-to-end through ``run_step``: a successful run-reconcile
        call (fake invoker, exit 0) leaves the plan's step status
        unchanged and writes no lessons entry — confirming the
        read-only contract holds at the full ``run_step`` boundary,
        not just at the constant declaration."""
        from plan_tool.launcher import run_step as _run_step

        original = plan_path.read_text(encoding="utf-8")

        def fake_invoker(prompt: str) -> tuple[int, str]:
            return (0, "")

        result = _run_step(
            plan_path,
            repo_root=tmp_path,
            mode="run-reconcile",
            invoker=fake_invoker,
        )
        assert result.exit_code == 0
        assert result.done is False
        assert result.advanced_to is None
        # Plan file unchanged byte-for-byte: no status flip, no
        # frontmatter rewrite.
        assert plan_path.read_text(encoding="utf-8") == original
        # No lessons file written either (the plan fixture has no
        # ``lessons:`` configured; this also serves as a contract
        # check that ``append_lesson`` wasn't reached).
        lessons_files = list(tmp_path.rglob("lessons.md"))
        assert lessons_files == []


# ──────────────────────────────────────────────────────────────────────────
# Stream-json stats hand-off via the ``shell_invoker._last_stats`` sentinel.
# The streaming runner itself (``backend_runner.run_streaming_once``) is
# covered in tests/test_backend_runner.py; here we test the launcher-side
# wrapper and hand-off. ``_StreamRecordingLogger`` lives there too and is
# imported at the top of this file.
# ──────────────────────────────────────────────────────────────────────────


import json as _json_for_streaming_tests  # noqa: E402


class TestRunStreamingOnceWrapper:
    """``launcher._run_streaming_once`` is a thin wrapper over
    ``backend_runner.run_streaming_once`` that supplies the active
    backend's ``streaming_transport``. The runner's own behavior is
    covered in tests/test_backend_runner.py."""

    def test_run_streaming_once_wrapper_resolves_transport_from_active_backend(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The run lane's call site passes ``streaming_transport``: a
        patched active backend's streaming argv is what reaches Popen
        when the wrapper is called with no transport of its own."""
        from types import SimpleNamespace

        from plan_tool.backend import PromptTransport
        from plan_tool import launcher

        captured_argv: list[list[str]] = []

        def fake_popen(argv, *, stdout, stderr, text, stdin=None, cwd=None):
            captured_argv.append(list(argv))
            return _FakeProc([], [], 0)

        monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
        fake_backend = SimpleNamespace(
            binary="claude",
            streaming_transport=lambda prompt: PromptTransport(
                ["SENTINEL", prompt]
            ),
            parse_stream_line=lambda line, *, bytes_in: None,
        )
        monkeypatch.setattr(
            launcher, "get_active_backend", lambda: fake_backend
        )
        launcher._run_streaming_once("the prompt")
        assert captured_argv == [["SENTINEL", "the prompt"]]


class TestShellInvokerStatsHandoff:
    """``shell_invoker`` exposes the last call's ``ClaudeRunStats`` via
    a sentinel attribute on the function object so callers in step 3
    (``run_step`` populating ``ClaudeCallEnd`` usage fields) can read
    it without widening the ``Invoker`` Protocol."""

    def test_last_stats_attribute_exists_with_default(self) -> None:
        from plan_tool.launcher import ClaudeRunStats, shell_invoker

        # The attribute is initialized at module load to a default
        # ``ClaudeRunStats()`` — never AttributeError on first read.
        assert isinstance(shell_invoker._last_stats, ClaudeRunStats)

    def test_last_stats_populated_from_result_envelope(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import launcher

        assistant_line = _json_for_streaming_tests.dumps({
            "type": "assistant", "request_id": "req_77",
            "message": {"content": [{"type": "text", "text": "ok"}]},
        }) + "\n"
        result_line = _json_for_streaming_tests.dumps({
            "type": "result", "is_error": False, "result": "ok",
            "usage": {"input_tokens": 7, "output_tokens": 11},
            "total_cost_usd": 0.05, "session_id": "sess-xyz",
        }) + "\n"
        monkeypatch.setattr(
            launcher.subprocess, "Popen",
            _make_popen_factory([([assistant_line, result_line], [], 0)]),
        )
        launcher.shell_invoker("p")
        stats = launcher.shell_invoker._last_stats
        assert stats.tokens_input == 7
        assert stats.tokens_output == 11
        assert stats.cost_usd == pytest.approx(0.05)
        # request_id comes from the assistant event (per-API-request),
        # not the result envelope's session_id (shared across turns).
        assert stats.request_id == "req_77"
        assert stats.final_text == "ok"

    def test_last_stats_reflects_most_recent_call_on_retry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A rate-limit retry runs ``_run_streaming_once`` twice. The
        sentinel records the *most recent* call's stats so the caller
        observes the successful run, not the failed one."""
        from plan_tool import launcher

        # First call: rate-limit. Second call: result with usage.
        result_line = _json_for_streaming_tests.dumps({
            "type": "result", "is_error": False, "result": "ok",
            "usage": {"input_tokens": 99},
        }) + "\n"
        monkeypatch.setattr(
            launcher.subprocess, "Popen",
            _make_popen_factory([
                (["You've hit your limit. resets 3am\n"], [], 1),
                ([result_line], [], 0),
            ]),
        )
        clock_state = {"t": 1000.0}

        def fake_sleep(secs: float) -> None:
            clock_state["t"] += 10_000

        def fake_clock() -> float:
            return clock_state["t"]

        launcher.shell_invoker(
            "p", _sleep=fake_sleep, _clock=fake_clock,
            wait_on_rate_limit=True,
        )
        assert launcher.shell_invoker._last_stats.tokens_input == 99


# ──────────────────────────────────────────────────────────────────────────
# Step 3 of Claude Call Observability: ContextVar plumbing + direct
# ClaudeCallEnd emission from run_step.
# ──────────────────────────────────────────────────────────────────────────


class TestShellInvokerContextVarPlumbing:
    """``shell_invoker`` reads ``_run_logger_var`` and
    ``_sibling_log_dir_var`` from the calling context and forwards both
    to ``_run_streaming_once`` (which already accepts them as kwargs).
    The plumbing lets ``run_step`` thread observability state through
    the bare ``Invoker = Callable[[str], tuple[int, str]]`` interface
    without widening the Protocol that 20+ test fakes are written
    against.
    """

    def test_run_logger_var_forwarded_to_streaming_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        captured: dict = {}

        def fake_streaming(prompt, *, run_logger=None, phase="claude_call",
                           attempt=1, sibling_log_dir=None):
            captured["run_logger"] = run_logger
            captured["attempt"] = attempt
            captured["sibling_log_dir"] = sibling_log_dir
            return 0, "ok\n", "", ClaudeRunStats()

        monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming)

        sentinel_logger = object()
        token = launcher._run_logger_var.set(sentinel_logger)  # type: ignore[arg-type]
        try:
            launcher.shell_invoker("p")
        finally:
            launcher._run_logger_var.reset(token)
        assert captured["run_logger"] is sentinel_logger
        assert captured["attempt"] == 1
        assert captured["sibling_log_dir"] is None

    def test_sibling_log_dir_var_forwarded_to_streaming_once(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        captured: dict = {}

        def fake_streaming(prompt, *, run_logger=None, phase="claude_call",
                           attempt=1, sibling_log_dir=None):
            captured["sibling_log_dir"] = sibling_log_dir
            return 0, "", "", ClaudeRunStats()

        monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming)

        sibling = tmp_path / "sibling-dir"
        token = launcher._sibling_log_dir_var.set(sibling)
        try:
            launcher.shell_invoker("p")
        finally:
            launcher._sibling_log_dir_var.reset(token)
        assert captured["sibling_log_dir"] == sibling

    def test_attempt_increments_across_transient_retries(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Each rerun of ``_run_streaming_once`` gets a fresh
        ``attempt`` so the streaming events for the second try aren't
        misfiled under the first attempt's stream transcript."""
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        attempts: list[int] = []
        responses = iter([
            (1, "request timed out\n", "", ClaudeRunStats()),
            (0, "ok\n", "", ClaudeRunStats()),
        ])

        def fake_streaming(prompt, *, run_logger=None, phase="claude_call",
                           attempt=1, sibling_log_dir=None):
            attempts.append(attempt)
            return next(responses)

        monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming)
        rc, _ = launcher.shell_invoker(
            "p", _sleep=lambda _s: None,
            max_transient_retries=3, transient_base_delay=0.0,
        )
        assert rc == 0
        assert attempts == [1, 2]

    def test_default_is_none_when_no_context_set(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A bare ``shell_invoker(prompt)`` call with no surrounding
        ``run_step`` frame must still produce ``run_logger=None`` /
        ``sibling_log_dir=None`` — the contextvar default."""
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        captured: dict = {}

        def fake_streaming(prompt, *, run_logger=None, phase="claude_call",
                           attempt=1, sibling_log_dir=None):
            captured["run_logger"] = run_logger
            captured["sibling_log_dir"] = sibling_log_dir
            return 0, "", "", ClaudeRunStats()

        monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming)
        launcher.shell_invoker("p")
        assert captured["run_logger"] is None
        assert captured["sibling_log_dir"] is None


class TestRunStepEmitsClaudeCallEnd:
    """``run_step`` constructs a ``ClaudeCallEnd`` directly from the
    invoker's ``_last_stats`` sentinel and pushes it to the active
    shell sink installed by ``bind_shell_sink``. Step 3's load-bearing
    test: the run log now carries token / cache / cost / request_id
    for ``plan-tool run``, where ``shell_invoker`` (not
    ``shell.claude_invoke``) does the subprocess work and so the
    historical shell-side emit path never fires.
    """

    def test_claude_call_end_emitted_with_usage_fields(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import ClaudeRunStats

        class _Inv:
            def __init__(self) -> None:
                self._last_stats = ClaudeRunStats(
                    final_text="ok",
                    tokens_input=42, tokens_output=10,
                    cache_creation_tokens=5, cache_read_tokens=3,
                    cost_usd=0.0123, request_id="sess-abc",
                )

            def __call__(self, prompt: str) -> tuple[int, str]:
                return (0, "claude output bytes")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=_Inv(),
            run_logger=logger,
        )
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(ends) == 1
        payload = ends[0][1]
        assert payload["phase"] == "claude_call"
        assert payload["attempt"] == 1
        assert payload["rc"] == 0
        assert payload["tokens_input"] == 42
        assert payload["tokens_output"] == 10
        assert payload["cache_creation_tokens"] == 5
        assert payload["cache_read_tokens"] == 3
        assert payload["cost_usd"] == pytest.approx(0.0123)
        assert payload["request_id"] == "sess-abc"
        assert payload["stdout_bytes"] == len(
            "claude output bytes".encode("utf-8")
        )
        # The bind_shell_sink closure stamps the writer's run_id over
        # the event's empty placeholder.
        assert payload["run_id"] == logger.run_id

    def test_claude_call_end_falls_back_to_defaults_without_stats(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """A fake invoker without a ``_last_stats`` attribute (the
        majority of test fakes) must not raise — the helper falls back
        to a default :class:`ClaudeRunStats`, leaving usage fields as
        ``None``."""
        logger = _RecordingLogger()

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, invoker=fake,
                 run_logger=logger)
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(ends) == 1
        payload = ends[0][1]
        assert payload["tokens_input"] is None
        assert payload["tokens_output"] is None
        assert payload["cost_usd"] is None
        assert payload["request_id"] is None

    def test_claude_call_end_carries_nonzero_rc(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        logger = _RecordingLogger()

        def fake(prompt: str) -> tuple[int, str]:
            return (3, "partial")

        run_step(plan_path, repo_root=tmp_path, invoker=fake,
                 run_logger=logger)
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(ends) == 1
        assert ends[0][1]["rc"] == 3

    def test_claude_call_end_not_emitted_when_no_logger(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """Without a ``run_logger`` the bind_shell_sink ctx is
        ``nullcontext`` and no sink is installed — so the helper finds
        no sink and skips. The default test harness has no active sink
        either, so this is also a guard against leaking events into the
        next test."""
        from plan_tool import shell as shell_module

        # Confirm no sink is installed at the start; bail with a
        # clearer message if a prior test left one.
        assert shell_module.get_active_sink() is None

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, invoker=fake)
        # No assertion on logger here — without a logger, nothing was
        # recorded. The real check is that the call didn't raise and
        # didn't leave a sink installed.
        assert shell_module.get_active_sink() is None

    def test_claude_call_end_not_emitted_when_invoker_raises(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """If the invoker raises, the call never produced an ``rc`` or
        stdout to record — only the surrounding ``phase_end`` with
        outcome=error fires."""
        logger = _RecordingLogger()

        def fake(prompt: str) -> tuple[int, str]:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            run_step(plan_path, repo_root=tmp_path, invoker=fake,
                     run_logger=logger)
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert ends == []

    def test_run_step_resets_contextvars_after_invoker_returns(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        """The ContextVars are reset back to their pre-call value on
        every exit path (success, exception). A leaked logger reference
        would tie the next ``plan-tool`` command's claude call to the
        previous run's JSONL."""
        from plan_tool import launcher

        assert launcher._run_logger_var.get() is None
        assert launcher._sibling_log_dir_var.get() is None
        logger = _RecordingLogger()

        def fake(prompt: str) -> tuple[int, str]:
            # Inside the call, the contextvars are set so shell_invoker
            # can read them.
            assert launcher._run_logger_var.get() is logger
            return (0, "")

        run_step(plan_path, repo_root=tmp_path, invoker=fake,
                 run_logger=logger)
        assert launcher._run_logger_var.get() is None
        assert launcher._sibling_log_dir_var.get() is None

    def test_run_step_resets_contextvars_when_invoker_raises(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        from plan_tool import launcher

        def fake(prompt: str) -> tuple[int, str]:
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            run_step(plan_path, repo_root=tmp_path, invoker=fake,
                     run_logger=_RecordingLogger())
        assert launcher._run_logger_var.get() is None
        assert launcher._sibling_log_dir_var.get() is None

    def test_sink_exception_does_not_break_run_step(
        self, plan_path: Path, tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A sink that raises is best-effort — the claude call result
        must survive. Mirrors the convention in ``shell._emit_call_end``.
        """
        from plan_tool import shell as shell_module

        class _BadLogger(_RecordingLogger):
            def bind_shell_sink(self, *, phase, attempt):
                from contextlib import contextmanager

                @contextmanager
                def _bound():
                    prev = shell_module.get_active_sink()

                    def _sink(_event):
                        raise RuntimeError("sink boom")

                    shell_module.set_active_sink(_sink)
                    try:
                        yield
                    finally:
                        shell_module.set_active_sink(prev)

                return _bound()

        def fake(prompt: str) -> tuple[int, str]:
            return (0, "")

        # No exception — the helper swallows sink errors and logs to
        # stderr, just like shell.py's _emit_call_end.
        result = run_step(plan_path, repo_root=tmp_path, invoker=fake,
                          run_logger=_BadLogger())
        assert result.exit_code == 0
        err = capsys.readouterr().err
        assert "run-log sink raised" in err


class TestEmitClaudeCallEndIsErrorSignal:
    """Pins the four-corner truth table for the effective-rc derivation
    in ``_emit_claude_call_end`` and the ``run_step`` coercion site.

    When the subprocess exits 0 but the terminal ``result`` envelope
    reports ``is_error: true``, ``run_step`` coerces ``exit_code`` to a
    synthesized non-zero rc so the emitted ``ClaudeCallEnd`` (and every
    downstream rc-bucketed consumer) sees the model-reported failure.
    A genuine non-zero subprocess rc wins — preserving it keeps the
    bucket honest.
    """

    @pytest.mark.parametrize(
        "rc_in,is_error,expected_rc",
        [
            (0, False, 0),
            (0, True, 1),  # synthesized from is_error
            (3, False, 3),
            (2, True, 2),  # raw rc wins over the sentinel
        ],
        ids=[
            "rc0_clean",
            "rc0_is_error_true_synthesizes_nonzero",
            "rc3_is_error_false_preserves_raw",
            "rc2_is_error_true_preserves_raw",
        ],
    )
    def test_effective_rc_truth_table(
        self,
        plan_path: Path,
        tmp_path: Path,
        rc_in: int,
        is_error: bool,
        expected_rc: int,
    ) -> None:
        from plan_tool.launcher import ClaudeRunStats

        class _Inv:
            def __init__(self) -> None:
                self._last_stats = ClaudeRunStats(is_error=is_error)

            def __call__(self, prompt: str) -> tuple[int, str]:
                return (rc_in, "")

        logger = _RecordingLogger()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=_Inv(),
            run_logger=logger,
        )
        ends = [e for e in logger.events if e[0] == "claude_call_end"]
        assert len(ends) == 1
        assert ends[0][1]["rc"] == expected_rc


class TestRunStepIsErrorSignal:
    """``run_step`` consults ``invoker._last_stats.is_error`` and coerces
    its local ``exit_code`` so a ``rc=0 + is_error=true`` call does not
    silently advance the plan. The fix closes the BUG_BACKLOG entry
    ``stats.is_error from result envelope is captured but never used``.
    """

    def test_is_error_true_with_rc_zero_does_not_advance_plan(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import ClaudeRunStats

        class _Inv:
            def __init__(self) -> None:
                self._last_stats = ClaudeRunStats(is_error=True)

            def __call__(self, prompt: str) -> tuple[int, str]:
                return (0, "")

        result = run_step(plan_path, repo_root=tmp_path, invoker=_Inv())
        assert result.exit_code != 0
        assert result.done is False
        assert result.advanced_to is None

        reloaded = parse_plan(plan_path)
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT
        assert reloaded.step_by_id(3).status == StepStatus.PENDING

    def test_is_error_true_failure_message_mentions_envelope(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        from plan_tool.launcher import ClaudeRunStats

        class _Inv:
            def __init__(self) -> None:
                self._last_stats = ClaudeRunStats(is_error=True)

            def __call__(self, prompt: str) -> tuple[int, str]:
                return (0, "")

        reporter = _RecordingReporter()
        run_step(
            plan_path,
            repo_root=tmp_path,
            invoker=_Inv(),
            reporter=reporter,
        )
        h = reporter.handles[0]
        assert h.completed is None
        assert h.failed is not None
        _, reason = h.failed
        assert "is_error" in reason
        # The synthesized-failure message must not pretend the
        # subprocess exited non-zero — that string is reserved for the
        # genuine-non-zero-rc path.
        assert "code 1" not in reason


# ──────────────────────────────────────────────────────────────────────────
# Reconcile Subcommand Split — per-mode dispatch + apply-path selection.
# ──────────────────────────────────────────────────────────────────────────


class TestRunStepModeDispatch:
    """``run_step`` resolves the per-mode prompt template by name —
    ``mode="detail-reconcile"`` renders ``prompts/detail-reconcile.md``
    and ``mode="run-reconcile"`` renders ``prompts/run-reconcile.md``.
    The test drives the dry-run path so the prompt body is captured
    via ``capsys`` rather than handed to a real claude subprocess.
    """

    @pytest.mark.parametrize(
        "mode,prompt_marker",
        [
            ("detail-reconcile", "Reconcile plan/detail vs code"),
            ("run-reconcile", "Reconcile code vs plan/detail"),
        ],
    )
    def test_run_step_renders_per_mode_prompt(
        self,
        plan_path: Path,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        mode: str,
        prompt_marker: str,
    ) -> None:
        run_step(
            plan_path,
            repo_root=tmp_path,
            mode=mode,
            invoker=lambda _: (0, ""),
            dry_run=True,
        )
        captured = capsys.readouterr().out
        assert prompt_marker in captured


class TestRunReconcileInlineApply:
    """``mode="run-reconcile"`` routes through the launcher's
    ``shell_invoker`` (claude under ``acceptEdits``) and never reaches
    per-finding ``apply_finding``. The mirror — ``mode="detail-reconcile"``
    — is read-only at the ``run_step`` boundary: it drives one
    ``shell_invoker`` call to render the audit prompt and never lands
    code edits inline."""

    def test_run_reconcile_invokes_through_shell_invoker(
        self, plan_path: Path, tmp_path: Path
    ) -> None:
        captured: list[str] = []

        def fake_invoker(prompt: str) -> tuple[int, str]:
            captured.append(prompt)
            return (0, "## Findings\n\n- HIGH: x\n")

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            mode="run-reconcile",
            invoker=fake_invoker,
        )
        assert result.exit_code == 0
        assert len(captured) == 1
        assert "Reconcile code vs plan/detail" in captured[0]

    def test_run_reconcile_does_not_reach_apply_finding(
        self,
        plan_path: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Run-reconcile's apply path is claude-under-acceptEdits in
        the same call that renders the audit prompt — there's nothing
        for per-finding ``apply_finding`` to do. Patch it with a
        raiser to surface any accidental routing back through the
        plan-edit apply path."""
        from plan_tool import launcher as launcher_module

        def fail_apply(*args, **kwargs):  # pragma: no cover - asserts no call
            raise AssertionError(
                "apply_finding must not run during mode=run-reconcile"
            )

        monkeypatch.setattr(launcher_module, "apply_finding", fail_apply)

        result = run_step(
            plan_path,
            repo_root=tmp_path,
            mode="run-reconcile",
            invoker=lambda _: (0, "## Findings\n\n_(none)_\n"),
        )
        assert result.exit_code == 0


def test_streaming_spawn_uses_active_spawn_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The streaming Popen passes ``backend.get_active_spawn_cwd()`` as cwd.

    Mirror of the batch-side pin in test_shell.py — both spawn sites
    must consume the context or a caller whose ``repo_root`` differs
    from the process cwd (the bench; a CLI invocation from a repo
    subdirectory) spawns backends against the wrong tree.
    """
    from plan_tool import launcher
    from plan_tool.backend import spawn_cwd

    seen: list[object] = []
    real_factory = _make_popen_factory(
        [(["x\n"], [], 0), (["x\n"], [], 0), (["x\n"], [], 0)]
    )

    def capturing_popen(argv, **kwargs):
        # The retry-guard's baseline snapshot runs a real ``git status`` under
        # the spawn cwd; that's not the backend spawn this test pins, so record
        # only the (non-git) backend invocations and delegate git through.
        if not (argv and argv[0] == "git"):
            seen.append(kwargs.get("cwd"))
        return real_factory(argv, **kwargs)

    monkeypatch.setattr(launcher.subprocess, "Popen", capturing_popen)

    launcher.shell_invoker("p")
    with spawn_cwd(tmp_path):
        launcher.shell_invoker("p")
    launcher.shell_invoker("p")

    assert seen == [None, tmp_path, None]


class TestRunStepConcurrentEditWriteBack:
    """run_step must not clobber a concurrent plan-file edit on write-back.

    run_step parses the plan at entry and holds it across the claude
    call; writing that stale snapshot back silently reverted any edit
    made to the plan file during the call (BUG_BACKLOG: "run clobbers
    concurrent plan-file edits with stale in-memory state on write-back"
    — observed when a later step's run reverted a files: rename). The
    fix re-reads the plan immediately before write-back and re-applies
    only the run step's status transition to the fresh copy.
    """

    _PLAN = (
        "---\n"
        "title: Concurrent Edit\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    status: current\n"
        "  - id: 2\n"
        "    title: Second\n"
        "    depends_on: [1]\n"
        "---\n\n# Concurrent Edit\n"
    )

    _PLAN_GATE = (
        "---\n"
        "title: Concurrent Edit Gate\n"
        "status: in-progress\n"
        "priority: medium\n"
        "test_command: 'false'\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    status: current\n"
        "  - id: 2\n"
        "    title: Second\n"
        "    depends_on: [1]\n"
        "---\n\n# Concurrent Edit Gate\n"
    )

    _PLAN_STEP_GATE = (
        "---\n"
        "title: Concurrent Edit Step Gate\n"
        "status: in-progress\n"
        "priority: medium\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: First\n"
        "    gate:\n"
        '      - "false"\n'
        "    status: current\n"
        "  - id: 2\n"
        "    title: Second\n"
        "    depends_on: [1]\n"
        "---\n\n# Concurrent Edit Step Gate\n"
    )

    def test_success_path_preserves_concurrent_edit(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._PLAN, encoding="utf-8")

        def fake(prompt: str) -> tuple[int, str]:
            # Simulate the operator editing step 2's title mid-run.
            p.write_text(
                p.read_text(encoding="utf-8").replace(
                    "title: Second", "title: Second EDITED"
                ),
                encoding="utf-8",
            )
            return (0, "## Summary\nran step 1\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is True

        reloaded = parse_plan(p)
        # The status transition landed…
        assert reloaded.step_by_id(1).status == StepStatus.DONE
        assert reloaded.step_by_id(2).status == StepStatus.CURRENT
        # …AND the concurrent edit survived (was clobbered before the fix).
        assert reloaded.step_by_id(2).title == "Second EDITED"

    def test_test_gate_fail_path_preserves_concurrent_edit(
        self, tmp_path: Path
    ) -> None:
        p = tmp_path / "plan.md"
        p.write_text(self._PLAN_GATE, encoding="utf-8")

        def fake(prompt: str) -> tuple[int, str]:
            p.write_text(
                p.read_text(encoding="utf-8").replace(
                    "title: Second", "title: Second EDITED"
                ),
                encoding="utf-8",
            )
            return (0, "## Summary\nran step 1\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        # test_command 'false' fails the gate → step not advanced.
        assert result.done is False
        assert result.exit_code != 0

        reloaded = parse_plan(p)
        assert reloaded.step_by_id(1).status == StepStatus.CURRENT  # not advanced
        assert reloaded.step_by_id(1).status_note  # gate-fail note written
        # The concurrent edit survived the status_note write-back.
        assert reloaded.step_by_id(2).title == "Second EDITED"

    def test_gate_fail_path_preserves_concurrent_edit(
        self, tmp_path: Path
    ) -> None:
        # The per-step `gate` (not the test_command gate) drives the
        # write-back here: no failing test_command, step 1 carries
        # gate: ['false'] so the gate loop is what blocks advancement.
        p = tmp_path / "plan.md"
        p.write_text(self._PLAN_STEP_GATE, encoding="utf-8")

        def fake(prompt: str) -> tuple[int, str]:
            p.write_text(
                p.read_text(encoding="utf-8").replace(
                    "title: Second", "title: Second EDITED"
                ),
                encoding="utf-8",
            )
            return (0, "## Summary\nran step 1\n")

        result = run_step(p, repo_root=tmp_path, invoker=fake)
        assert result.done is False
        assert result.exit_code != 0

        reloaded = parse_plan(p)
        assert reloaded.step_by_id(1).status == StepStatus.CURRENT  # not advanced
        assert reloaded.step_by_id(1).status_note  # gate-fail note written
        # The concurrent edit survived the status_note write-back.
        assert reloaded.step_by_id(2).title == "Second EDITED"


# --- escalate_to_split bridge --------------------------------------------

import json as _json_for_escalate  # noqa: E402

from plan_tool import review as _review  # noqa: E402


_ESC_PLAN_HEAD = """---
title: Escalate Test
status: in-progress
priority: medium
steps:
  - id: 1
    title: Mixed step
    files:
      - renderer.py
    complexity: low
  - id: 2
    title: Downstream
    files:
      - foo.py
    depends_on: [1]
"""

_ESC_PLAN_TAIL = """---

# Escalate Test
"""

# Two-step refactor->feature decomposition _propose_step_split parses.
_ESC_SPLIT_JSON = _json_for_escalate.dumps(
    [
        {
            "title": "Refactor extract",
            "change_type": "refactor",
            "files": ["renderer.py"],
            "creates": [],
            "rationale": "behavior-preserving extract",
        },
        {
            "title": "Add caching",
            "change_type": "feature",
            "files": ["renderer.py"],
            "creates": [],
            "rationale": "new caching behavior",
        },
    ]
)


def _raise_invoker(_prompt: str) -> str:
    # Rigged onto every no-Claude path: a regression that leaks a proposal
    # call where the safe-gate / recommend-only short-circuit should have
    # fired surfaces as this loud failure rather than a silent token spend.
    raise AssertionError("invoker must not be called on this path")


def _split_invoker(_prompt: str) -> str:
    return _ESC_SPLIT_JSON


class TestEscalateToSplit:
    """The apply-or-recommend bridge: one mixed step, never half-split."""

    def _write_plan(self, tmp_path: Path, *, downstream_done: bool = False) -> Path:
        status = "    status: done\n" if downstream_done else ""
        plan_path = tmp_path / "3-escalate.md"
        plan_path.write_text(
            _ESC_PLAN_HEAD + status + _ESC_PLAN_TAIL, encoding="utf-8"
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        return plan_path

    def test_step_missing_returns_noop(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=99,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=True,
        )
        assert result.outcome == "step-missing"
        assert result.target_id == 99
        assert result.recommendation is None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_unsafe_skips_proposal(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path, downstream_done=True)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=True,
        )
        assert result.outcome == "unsafe"
        assert result.blocking == [2]
        assert result.recommendation is None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_recommend_only_no_claude(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=False,
        )
        assert result.outcome == "recommended"
        assert result.recommendation is not None
        assert result.recommendation.source == "structural-split"

    def test_proposal_unusable(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=lambda _p: "not json at all",
            allow_split=True,
        )
        assert result.outcome == "proposal-unusable"
        assert result.recommendation is None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_raising_recorder_does_not_perturb_bridge(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A raising ``record_escalate_split`` must not abort the bridge —
        telemetry never changes control flow (ground rule 2). Guards the
        best-effort try/except around the recorder call in ``_record_and_return``.
        """
        plan_path = self._write_plan(tmp_path)

        def _boom(*_a, **_k):
            raise RuntimeError("recorder blew up before the sink")

        monkeypatch.setattr("plan_tool.launcher.record_escalate_split", _boom)
        # Recommend-only path (no Claude): the recorder still fires on return.
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=False,
        )
        assert result.outcome == "recommended"
        assert result.recommendation is not None

    def test_declined_confirm_recommends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "n",
        )
        assert result.outcome == "recommended"
        assert result.recommendation is not None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_applied_writes_split(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "applied"
        assert result.recommendation is None
        plan = parse_plan(plan_path)
        assert [s.title for s in plan.steps] == [
            "Refactor extract",
            "Add caching",
            "Downstream",
        ]
        assert plan.step_by_id(1).change_type == ChangeType.REFACTOR
        assert plan.step_by_id(2).change_type == ChangeType.FEATURE
        assert plan.step_by_id(3).depends_on == [2]
        # The bridge writes the structural edit only — halves stay unauthored.
        assert plan.step_by_id(1).detail is None
        assert plan.step_by_id(2).detail is None

    def test_applied_records_step_provenance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """#238: the bridge's ``applied`` outcome records the new halves'
        titles as step-provenance telemetry, same signal ``split_step``
        records, tagged with ``mechanism="escalate-split"``."""
        from plan_tool.telemetry import read_step_provenance_titles

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "applied"
        titles = read_step_provenance_titles(tmp_path, "escalate")
        assert titles == {"Refactor extract", "Add caching"}

    def test_recommended_records_no_step_provenance(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.telemetry import read_step_provenance_titles

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "n",
        )
        assert result.outcome == "recommended"
        assert read_step_provenance_titles(tmp_path, "escalate") == set()

    def test_applied_split_preserves_concept_ids(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        concept_a, concept_b = "a" * 64, "b" * 64
        plan_path = self._write_plan(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "    title: Mixed step\n",
                "    title: Mixed step\n"
                f"    concept_ids: [{concept_a}, {concept_b}]\n",
            ),
            encoding="utf-8",
        )
        proposal = _json_for_escalate.loads(_ESC_SPLIT_JSON)
        proposal[0]["concept_ids"] = [concept_a]
        proposal[1]["concept_ids"] = [concept_b]
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=lambda _prompt: _json_for_escalate.dumps(proposal),
            allow_split=True,
            prompt_fn=lambda _message: "y",
        )
        assert result.outcome == "applied"
        plan = parse_plan(plan_path)
        assert plan.step_by_id(1).concept_ids == [concept_a]
        assert plan.step_by_id(2).concept_ids == [concept_b]

    @pytest.mark.parametrize("invent", [False, True])
    def test_rejects_nonconserving_concept_proposal_before_confirmation(
        self,
        tmp_path: Path,
        invent: bool,
    ) -> None:
        concept_a, concept_b = "a" * 64, "b" * 64
        plan_path = self._write_plan(tmp_path)
        plan_path.write_text(
            plan_path.read_text(encoding="utf-8").replace(
                "    title: Mixed step\n",
                f"    title: Mixed step\n    concept_ids: [{concept_a}]\n",
            ),
            encoding="utf-8",
        )
        before = plan_path.read_bytes()
        proposal = _json_for_escalate.loads(_ESC_SPLIT_JSON)
        proposal[0]["concept_ids"] = [concept_a, concept_b] if invent else []
        proposal[1]["concept_ids"] = []

        def fail_confirmation(_message: str) -> str:
            raise AssertionError("invalid proposals must not reach confirmation")

        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=lambda _prompt: _json_for_escalate.dumps(proposal),
            allow_split=True,
            prompt_fn=fail_confirmation,
        )
        assert result.outcome == "proposal-unusable"
        assert plan_path.read_bytes() == before

    def test_apply_error_degrades_to_recommend(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        from plan_tool import create as _create

        def _boom(*_a, **_k):
            raise _create.CreateError("graph rejected")

        monkeypatch.setattr(_create, "_apply_step_split", _boom)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "recommended"
        assert result.recommendation is not None
        assert plan_path.read_text(encoding="utf-8") == before

    def test_reparses_plan_from_disk(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        # The on-disk step 1 is the only thing the bridge can act on — it
        # takes no in-memory Plan. Splitting it proves the re-parse.
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "applied"
        assert parse_plan(plan_path).step_by_id(1).title == "Refactor extract"

    def test_non_tty_recommends(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=None,
        )
        assert result.outcome == "recommended"
        assert plan_path.read_text(encoding="utf-8") == before

    def test_structural_rec_is_advisory(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=False,
        )
        rec = result.recommendation
        assert rec is not None
        assert rec.source == "structural-split"
        assert rec.step_id == 1
        assert "plan-tool split" in (rec.suggested_action or "")
        assert _review.is_apply_eligible(rec) is False
        assert _review.is_structural(rec) is True

    # --- decision telemetry (one escalate-split event per completed call) ---

    @staticmethod
    def _escalate_events(tmp_path: Path) -> list:
        from plan_tool.telemetry import read_decisions

        return [
            e for e in read_decisions(tmp_path) if e.kind == "escalate-split"
        ]

    def test_step_missing_records_one_event(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        escalate_to_split(
            plan_path,
            step_id=99,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=True,
        )
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "step-missing"
        assert event.context["step_id"] == "99"

    def test_unsafe_records_blocking(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path, downstream_done=True)
        escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=True,
        )
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "unsafe"
        assert event.context["blocking"] == ["2"]

    def test_recommend_only_records_event(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=False,
        )
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "recommended"
        assert event.context["allow_split"] is False
        assert "blocking" not in event.context

    def test_proposal_unusable_records_event(self, tmp_path: Path) -> None:
        plan_path = self._write_plan(tmp_path)
        escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=lambda _p: "not json at all",
            allow_split=True,
        )
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "proposal-unusable"

    def test_applied_records_event(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from plan_tool.review_persistence import compute_plan_fingerprint

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        pre_split_fp = compute_plan_fingerprint(plan_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "applied"
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "applied"
        # Fingerprint reflects the pre-split plan, computed before write_plan.
        assert event.plan_fingerprint
        assert event.plan_fingerprint == pre_split_fp

    def test_escalate_records_exactly_one_event_per_call(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert len(self._escalate_events(tmp_path)) == 1

    def test_failed_plan_write_rolls_back_the_detail_migration(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Never half-split: downstream details are renamed before the plan
        write, so a refused write must put them back."""
        from plan_tool.parser import ConcurrentModificationError

        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = tmp_path / "3-escalate.md"
        plan_path.write_text(
            _ESC_PLAN_HEAD
            + "    detail: plan-details/escalate/02-downstream.md\n"
            + _ESC_PLAN_TAIL,
            encoding="utf-8",
        )
        (tmp_path / "renderer.py").write_text("X = 1\n", encoding="utf-8")
        (tmp_path / "foo.py").write_text("Y = 1\n", encoding="utf-8")
        detail = tmp_path / "plan-details/escalate/02-downstream.md"
        detail.parent.mkdir(parents=True, exist_ok=True)
        detail.write_text("# downstream detail\n", encoding="utf-8")

        def _edit_plan_at_the_confirm(_prompt: str) -> str:
            # A concurrent writer touches the frontmatter while the operator is
            # at the prompt — what write_plan's compare-and-swap exists to catch.
            text = plan_path.read_text(encoding="utf-8")
            plan_path.write_text(
                text.replace("priority: medium", "priority: high"),
                encoding="utf-8",
            )
            return "y"

        with pytest.raises(ConcurrentModificationError):
            escalate_to_split(
                plan_path,
                step_id=1,
                repo_root=tmp_path,
                invoker=_split_invoker,
                allow_split=True,
                prompt_fn=_edit_plan_at_the_confirm,
            )

        assert detail.is_file(), "detail was not restored to its pre-split path"
        assert not (tmp_path / "plan-details/escalate/03-downstream.md").exists()
        # The plan still points at the file that is actually there.
        assert "02-downstream.md" in plan_path.read_text(encoding="utf-8")

    def test_escalate_fingerprint_failure_does_not_break_bridge(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import plan_tool.review_persistence as _rp

        def _boom(_p):
            raise RuntimeError("fingerprint exploded")

        monkeypatch.setattr(_rp, "compute_plan_fingerprint", _boom)
        plan_path = self._write_plan(tmp_path)
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_raise_invoker,
            allow_split=False,
        )
        assert result.outcome == "recommended"
        (event,) = self._escalate_events(tmp_path)
        assert event.context["outcome"] == "recommended"
        assert event.plan_fingerprint == ""

    def test_escalate_to_split_threads_depends_on_notes(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        plan_path = self._write_plan(tmp_path)
        from plan_tool.parser import parse_plan, write_plan

        plan = parse_plan(plan_path)
        plan.steps[1] = plan.steps[1].model_copy(
            update={"depends_on_notes": {1: "consumes mixed step"}}
        )
        write_plan(plan_path, plan)

        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert result.outcome == "applied"
        plan = parse_plan(plan_path)
        downstream = plan.step_by_id(3)
        assert downstream.depends_on == [2]
        assert downstream.depends_on_notes == {}

    def test_escalate_to_split_stale_note_raises_create_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        from plan_tool import create as create_mod
        from plan_tool.create import CreateError

        real_remap = create_mod._remap_depends_on_notes

        def _inject_stale(notes, depends_on, **kwargs):
            result = real_remap(notes, depends_on, **kwargs)
            result[99] = "stale"
            return result

        monkeypatch.setattr(create_mod, "_remap_depends_on_notes", _inject_stale)
        raised: list[CreateError] = []
        real_apply = create_mod._apply_step_split

        def _spy_apply(*args, **kwargs):
            try:
                return real_apply(*args, **kwargs)
            except CreateError as exc:
                raised.append(exc)
                raise

        monkeypatch.setattr(create_mod, "_apply_step_split", _spy_apply)
        plan_path = self._write_plan(tmp_path)
        before = plan_path.read_text(encoding="utf-8")
        result = escalate_to_split(
            plan_path,
            step_id=1,
            repo_root=tmp_path,
            invoker=_split_invoker,
            allow_split=True,
            prompt_fn=lambda _msg: "y",
        )
        assert raised
        assert "depends_on_notes" in str(raised[0])
        assert result.outcome == "recommended"
        assert plan_path.read_text(encoding="utf-8") == before


class TestInvokerStatsAreThreadLocal:
    def test_concurrent_shell_invoker_calls_each_read_their_own_stats(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--jobs N`` apply workers share ``shell_invoker``; each must read its own call's stats, not the last writer's."""
        import threading

        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        both_stored = threading.Barrier(2)

        def fake_streaming(prompt, *, run_logger=None, phase="claude_call",
                           attempt=1, sibling_log_dir=None):
            return 0, "ok\n", "", ClaudeRunStats(final_text=prompt)

        monkeypatch.setattr(launcher, "_run_streaming_once", fake_streaming)
        seen: dict[str, str] = {}

        def worker(name: str) -> None:
            launcher.shell_invoker(name)
            both_stored.wait(timeout=5)  # both calls finished before either reads
            seen[name] = launcher._invoker_stats(launcher.shell_invoker).final_text

        threads = [threading.Thread(target=worker, args=(n,)) for n in ("a", "b")]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert seen == {"a": "a", "b": "b"}

    def test_non_shell_invoker_keeps_attribute_read(self) -> None:
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        def fake(prompt):
            return 0, ""

        fake._last_stats = ClaudeRunStats(final_text="fake")  # type: ignore[attr-defined]
        assert launcher._invoker_stats(fake).final_text == "fake"


class TestInvokeAndLogEnd:
    def test_end_write_failure_does_not_mask_the_invokers_exception(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """apply_finding's restore path keys off the invoker's own exception, so a failing end write must not replace it."""
        from plan_tool import launcher

        class Boom(RuntimeError):
            pass

        def invoker(prompt):
            raise Boom("invoker")

        def bad_emit(**kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(launcher, "_emit_claude_call_end", bad_emit)
        with pytest.raises(Boom):
            launcher._invoke_and_log_end(
                invoker, "p", run_logger=object(), started_monotonic=0.0, attempt=1,
            )

    def test_end_write_failure_after_a_successful_call_keeps_the_result(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A completed apply must not be restored as a failure because its call end could not be logged."""
        from plan_tool import launcher

        def bad_emit(**kwargs):
            raise OSError("disk full")

        monkeypatch.setattr(launcher, "_emit_claude_call_end", bad_emit)
        assert launcher._invoke_and_log_end(
            lambda p: (0, "ok"), "p", run_logger=object(), started_monotonic=0.0, attempt=1,
        ) == (0, "ok")

    def test_raising_invoker_end_does_not_inherit_a_previous_calls_usage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raise carries no usage; the stale _last_stats of an earlier call must not be double-counted."""
        from plan_tool import launcher
        from plan_tool.launcher import ClaudeRunStats

        seen = {}

        def capture(*, stats=None, **kwargs):
            seen["stats"] = stats

        monkeypatch.setattr(launcher, "_emit_claude_call_end", capture)

        def invoker(prompt):
            raise RuntimeError("before reset")

        invoker._last_stats = ClaudeRunStats(final_text="previous call")  # type: ignore[attr-defined]
        with pytest.raises(RuntimeError):
            launcher._invoke_and_log_end(
                invoker, "p", run_logger=object(), started_monotonic=0.0, attempt=1,
            )
        assert seen["stats"] == ClaudeRunStats()


def test_run_writeback_keeps_description_and_step_text(plan_path, tmp_path):
    import yaml
    from plan_tool.parser import split_plan_document, write_plan

    plan = parse_plan(plan_path)
    text = plan.step_by_id(2).title
    write_plan(plan_path, plan)
    prompts = []
    def fake_invoker(prompt):
        prompts.append(prompt)
        return 0, ""

    result = run_step(plan_path, repo_root=tmp_path, invoker=fake_invoker)
    assert result.done
    assert text in prompts[0]
    assert parse_plan(plan_path).step_by_id(2).title == text
    assert parse_plan(plan_path).step_by_id(2).status == StepStatus.DONE
    steps = yaml.safe_load(split_plan_document(plan_path.read_text()).frontmatter_yaml)["steps"]
    assert all("description" in step and "title" not in step for step in steps)
