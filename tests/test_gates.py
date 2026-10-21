"""Tests for post-build gate suggestion.

Covers the pure engine (:mod:`plan_tool.gates`) and the ``suggest-gates``
command handler (:mod:`plan_tool.cli.gates_cmd`). Never spawns a real backend
or blocks on stdin — the ``invoker`` and ``input_fn`` seams are injected fakes.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Callable

import pytest

from plan_tool.cli.gates_cmd import cmd_suggest_gates
from plan_tool.gates import (
    GateSuggestion,
    apply_gate_suggestions,
    built_steps,
    default_target_step,
    load_done_details,
    load_step_details,
    parse_gate_suggestions,
    remaining_steps,
    render_pre_build_gates_prompt,
    render_suggest_gates_prompt,
    suggest_gates,
)
from plan_tool.parser import parse_plan
from plan_tool.run_log import run_dir
from plan_tool.schema import ChangeType, Plan, PlanStatus, Priority, Step, StepStatus


def _read_run_log(repo_root: Path, slug: str) -> list[dict]:
    rd = run_dir(repo_root, slug)
    files = sorted(rd.glob("*.jsonl"))
    assert len(files) == 1, f"expected one run log under {rd}, found {files}"
    return [
        json.loads(line)
        for line in files[0].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _queue_input(answers: list[str]) -> Callable[[str], str]:
    it = iter(answers)

    def fake(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration as exc:  # pragma: no cover - guards a test bug
            raise AssertionError(f"input ran out at: {prompt!r}") from exc

    return fake


def _raises_if_called(prompt: str) -> str:  # invoker that must not run
    raise AssertionError("invoker should not be called")


def _plan(*steps: Step) -> Plan:
    return Plan(
        title="Demo",
        status=PlanStatus.IN_PROGRESS,
        priority=Priority.LOW,
        steps=list(steps),
    )


def _built_then_remaining() -> Plan:
    return _plan(
        Step(id=1, title="build", change_type=ChangeType.REFACTOR, status=StepStatus.DONE),
        Step(id=2, title="extend", status=StepStatus.CURRENT, depends_on=[1]),
        Step(id=3, title="docs", status=StepStatus.PENDING, depends_on=[2]),
    )


def _all_pending() -> Plan:
    """A freshly-created plan: no built (done) steps yet."""
    return _plan(
        Step(id=1, title="build", change_type=ChangeType.FEATURE, status=StepStatus.CURRENT),
        Step(id=2, title="extend", status=StepStatus.PENDING, depends_on=[1]),
        Step(id=3, title="docs", status=StepStatus.PENDING, depends_on=[2]),
    )


# --- engine: step partitions + default target -----------------------------


class TestStepPartitions:
    def test_built_and_remaining(self) -> None:
        plan = _built_then_remaining()
        assert [s.id for s in built_steps(plan)] == [1]
        assert [s.id for s in remaining_steps(plan)] == [2, 3]

    def test_default_target_prefers_current(self) -> None:
        assert default_target_step(_built_then_remaining()).id == 2

    def test_default_target_falls_back_to_next_runnable(self) -> None:
        plan = _plan(
            Step(id=1, title="done", status=StepStatus.DONE),
            Step(id=2, title="pending", status=StepStatus.PENDING, depends_on=[1]),
        )
        assert default_target_step(plan).id == 2

    def test_default_target_none_when_all_done(self) -> None:
        plan = _plan(Step(id=1, title="done", status=StepStatus.DONE))
        assert default_target_step(plan) is None


# --- engine: parsing ------------------------------------------------------


class TestParseGateSuggestions:
    def test_valid_entries(self) -> None:
        raw = json.dumps(
            [
                {"command": "pytest tests/x.py -q", "target": 2, "protects": 1, "rationale": "guard"},
                {"command": "grep -q foo .", "target": 3, "protects": 1, "rationale": ""},
            ]
        )
        out = parse_gate_suggestions(raw, valid_targets={2, 3}, default_target_id=2)
        assert out is not None
        assert [(s.command, s.target_id, s.protects_id) for s in out] == [
            ("pytest tests/x.py -q", 2, 1),
            ("grep -q foo .", 3, 1),
        ]

    def test_invalid_target_retargeted_to_default(self) -> None:
        raw = json.dumps([{"command": "pytest x", "target": 99}])
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert out[0].target_id == 2  # 99 isn't remaining → default

    def test_missing_target_retargeted_to_default(self) -> None:
        raw = json.dumps([{"command": "pytest x"}])
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert out[0].target_id == 2

    def test_quoted_numeral_resolves_to_the_same_id_as_its_bare_int_form(self) -> None:
        raw = json.dumps([{"command": "pytest x", "target": "2", "protects": "1"}])
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert (out[0].target_id, out[0].protects_id) == (2, 1)

    @pytest.mark.parametrize(
        "raw_id",
        [
            "--5",
            "²",
            "5.0",
            "2_0",
            "٢",
            "02",
            "0",
            pytest.param("1" + "0" * 4999, id="oversized"),
        ],
    )
    def test_malformed_numeral_ids_fall_back_without_raising(
        self, raw_id: str
    ) -> None:
        raw = json.dumps(
            [{"command": "pytest x", "target": raw_id, "protects": raw_id}]
        )
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert (out[0].target_id, out[0].protects_id) == (2, None)

    def test_malformed_entries_dropped(self) -> None:
        raw = json.dumps(
            [
                {"command": "", "target": 2},  # empty command
                {"command": "   ", "target": 2},  # whitespace-only
                {"command": 3, "target": 2},  # non-string
                "not a dict",
                {"command": "keep me", "target": 2},
            ]
        )
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert [s.command for s in out] == ["keep me"]

    def test_command_whitespace_preserved(self) -> None:
        raw = json.dumps([{"command": "grep -q 'a  b' .", "target": 2}])
        out = parse_gate_suggestions(raw, valid_targets={2}, default_target_id=2)
        assert out is not None
        assert out[0].command == "grep -q 'a  b' ."

    def test_empty_array_is_empty_list_not_none(self) -> None:
        out = parse_gate_suggestions("[]", valid_targets={2}, default_target_id=2)
        assert out == []

    def test_unparseable_is_none(self) -> None:
        assert parse_gate_suggestions("not json", valid_targets={2}, default_target_id=2) is None
        assert parse_gate_suggestions("{}", valid_targets={2}, default_target_id=2) is None


# --- engine: prompt + suggest_gates + apply -------------------------------


class TestRenderPrompt:
    def test_prompt_carries_built_and_remaining(self) -> None:
        plan = _built_then_remaining()
        prompt = render_suggest_gates_prompt(
            plan,
            done=built_steps(plan),
            remaining=remaining_steps(plan),
            done_details={1: "detail head text"},
            default_target_id=2,
        )
        assert "step 1 [refactor]: build" in prompt
        assert "detail head text" in prompt
        assert "step 2: extend" in prompt and "step 3: docs" in prompt
        assert "Ground every command in what exists now" in prompt
        assert "test_command" in prompt  # the don't-use-a-gate-for-this boundary

    def test_prompt_shows_existing_gates_on_remaining_steps(self) -> None:
        plan = _plan(
            Step(id=1, title="build", status=StepStatus.DONE),
            Step(id=2, title="extend", status=StepStatus.CURRENT, gate=["pytest a"]),
            Step(id=3, title="docs", status=StepStatus.PENDING, depends_on=[2]),
        )
        prompt = render_suggest_gates_prompt(
            plan,
            done=built_steps(plan),
            remaining=remaining_steps(plan),
            done_details={},
            default_target_id=2,
        )
        # The existing gate is surfaced so the model won't re-propose it.
        assert "already gated: `pytest a`" in prompt
        assert "Do NOT re-propose" in prompt


class TestRenderPreBuildPrompt:
    def test_prompt_carries_all_steps_and_details(self) -> None:
        plan = _all_pending()
        prompt = render_pre_build_gates_prompt(
            plan,
            steps=remaining_steps(plan),
            step_details={1: "intended test head"},
            default_target_id=1,
        )
        assert "step 1 [feature]: build" in prompt
        assert "intended test head" in prompt
        assert "step 2 [unclassified]: extend" in prompt
        assert "step 3 [unclassified]: docs" in prompt
        # Pre-build framing: speculative, no diff to inspect.
        assert "NOT built yet" in prompt
        assert "test_command" in prompt  # don't-use-a-gate-for-this boundary

    def test_prompt_shows_existing_gates_on_steps(self) -> None:
        plan = _plan(
            Step(id=1, title="build", status=StepStatus.CURRENT, gate=["pytest a"]),
            Step(id=2, title="docs", status=StepStatus.PENDING, depends_on=[1]),
        )
        prompt = render_pre_build_gates_prompt(
            plan,
            steps=remaining_steps(plan),
            step_details={},
            default_target_id=1,
        )
        assert "already gated: `pytest a`" in prompt
        assert "Do NOT re-propose" in prompt


class TestSuggestGates:
    def test_returns_parsed(self) -> None:
        plan = _built_then_remaining()
        raw = json.dumps([{"command": "pytest x", "target": 2, "protects": 1}])
        out = suggest_gates(plan, repo_root=Path("."), invoker=lambda p: raw)
        assert out is not None
        assert out[0].command == "pytest x"

    def test_no_built_steps_returns_empty_without_invoking(self) -> None:
        plan = _plan(Step(id=1, title="pending", status=StepStatus.CURRENT))
        assert suggest_gates(plan, repo_root=Path("."), invoker=_raises_if_called) == []

    def test_no_remaining_steps_returns_empty_without_invoking(self) -> None:
        plan = _plan(Step(id=1, title="done", status=StepStatus.DONE))
        assert suggest_gates(plan, repo_root=Path("."), invoker=_raises_if_called) == []

    def test_unparseable_response_returns_none(self) -> None:
        plan = _built_then_remaining()
        assert suggest_gates(plan, repo_root=Path("."), invoker=lambda p: "junk") is None

    # --- all_steps (pre-build) mode ---

    def test_all_steps_suggests_without_built_steps(self) -> None:
        plan = _all_pending()
        raw = json.dumps([{"command": "pytest x", "target": 1, "protects": None}])
        out = suggest_gates(
            plan, repo_root=Path("."), invoker=lambda p: raw, all_steps=True
        )
        assert out is not None
        assert out[0].command == "pytest x"

    def test_all_steps_targets_every_not_done_step(self) -> None:
        plan = _all_pending()
        # target 3 is valid in all_steps mode (no done precondition).
        raw = json.dumps([{"command": "pytest x", "target": 3}])
        out = suggest_gates(
            plan, repo_root=Path("."), invoker=lambda p: raw, all_steps=True
        )
        assert out is not None
        assert out[0].target_id == 3

    def test_all_steps_uses_pre_build_prompt(self) -> None:
        plan = _all_pending()
        captured: dict[str, str] = {}

        def spy(prompt: str) -> str:
            captured["prompt"] = prompt
            return "[]"

        suggest_gates(plan, repo_root=Path("."), invoker=spy, all_steps=True)
        assert "NOT built yet" in captured["prompt"]

    def test_all_steps_no_remaining_returns_empty_without_invoking(self) -> None:
        plan = _plan(Step(id=1, title="done", status=StepStatus.DONE))
        assert (
            suggest_gates(
                plan, repo_root=Path("."), invoker=_raises_if_called, all_steps=True
            )
            == []
        )


class TestApplyGateSuggestions:
    def test_appends_to_target_step(self) -> None:
        plan = _built_then_remaining()
        out = apply_gate_suggestions(
            plan, [GateSuggestion(command="pytest x", target_id=2)]
        )
        assert out.step_by_id(2).gate == ["pytest x"]
        assert out.step_by_id(3).gate == []  # untouched

    def test_dedups_existing_command(self) -> None:
        plan = _plan(
            Step(id=1, title="done", status=StepStatus.DONE),
            Step(id=2, title="cur", status=StepStatus.CURRENT, gate=["pytest x"]),
        )
        out = apply_gate_suggestions(
            plan,
            [
                GateSuggestion(command="pytest x", target_id=2),  # dup
                GateSuggestion(command="grep y", target_id=2),
            ],
        )
        assert out.step_by_id(2).gate == ["pytest x", "grep y"]


class TestLoadDoneDetails:
    def test_reads_head_skips_missing(self, tmp_path: Path) -> None:
        detail = tmp_path / "plan-details" / "p" / "01.md"
        detail.parent.mkdir(parents=True)
        detail.write_text("X" * 9000, encoding="utf-8")
        plan = _plan(
            Step(id=1, title="a", status=StepStatus.DONE, detail="plan-details/p/01.md"),
            Step(id=2, title="b", status=StepStatus.DONE, detail="plan-details/p/missing.md"),
            Step(id=3, title="c", status=StepStatus.DONE),  # no detail
        )
        out = load_done_details(plan, tmp_path, head_chars=100)
        assert set(out) == {1}
        assert len(out[1]) == 100

    def test_load_step_details_reads_arbitrary_steps(self, tmp_path: Path) -> None:
        detail = tmp_path / "plan-details" / "p" / "02.md"
        detail.parent.mkdir(parents=True)
        detail.write_text("Y" * 9000, encoding="utf-8")
        plan = _plan(
            # a not-done step with detail — load_done_details would skip it
            Step(id=2, title="b", status=StepStatus.PENDING, detail="plan-details/p/02.md"),
        )
        out = load_step_details(plan, plan.steps, tmp_path, head_chars=50)
        assert set(out) == {2}
        assert len(out[2]) == 50

    def test_gate_suggestion_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        """Unlike a missing/unreadable detail file (silently omitted above),
        a present, readable, unsupported-version body must refuse rather
        than silently omitting the step's detail from the prompt."""
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        detail = tmp_path / "plan-details" / "p" / "01.md"
        detail.parent.mkdir(parents=True)
        detail.write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )
        plan = _plan(
            Step(id=1, title="a", status=StepStatus.DONE, detail="plan-details/p/01.md"),
        )
        with pytest.raises(DetailFormatError):
            load_done_details(plan, tmp_path)


# --- command handler ------------------------------------------------------


_CANNED = json.dumps(
    [{"command": "pytest tests/x.py -q", "target": 2, "protects": 1, "rationale": "guard the rename"}]
)


def _seed_plan(repo: Path, *, name: str = "myplan") -> Path:
    (repo / ".git").mkdir(exist_ok=True)
    path = repo / f"{name}.md"
    path.write_text(
        "---\n"
        "title: Demo\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: build the thing\n"
        "    change_type: refactor\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: extend the thing\n"
        "    status: current\n"
        "    depends_on: [1]\n"
        "  - id: 3\n"
        "    title: write docs\n"
        "    status: pending\n"
        "    depends_on: [2]\n"
        "---\n",
        encoding="utf-8",
    )
    return path


def _args(
    repo: Path, *, slug: str = "myplan", yes: bool = False, all_steps: bool = False
) -> SimpleNamespace:
    return SimpleNamespace(
        slug=slug,
        plans_dir=repo,
        manifest=None,
        repo_root=repo,
        yes=yes,
        all_steps=all_steps,
    )


def _seed_fresh_plan(repo: Path, *, name: str = "fresh") -> Path:
    """A plan with no built (done) steps — the --all-steps use case."""
    (repo / ".git").mkdir(exist_ok=True)
    path = repo / f"{name}.md"
    path.write_text(
        "---\n"
        "title: Fresh\n"
        "status: in-progress\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: build the thing\n"
        "    change_type: feature\n"
        "    status: current\n"
        "  - id: 2\n"
        "    title: write docs\n"
        "    status: pending\n"
        "    depends_on: [1]\n"
        "---\n",
        encoding="utf-8",
    )
    return path


class TestCmdSuggestGates:
    def test_interactive_keep_writes_gate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["k"]),
        )
        assert rc == 0
        plan = parse_plan(path)
        assert plan.step_by_id(2).gate == ["pytest tests/x.py -q"]

    def test_interactive_drop_leaves_plan_unchanged(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["d"]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(2).gate == []

    def test_interactive_edit_writes_replacement(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["e", "pytest tests/edited.py -q"]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(2).gate == ["pytest tests/edited.py -q"]

    def test_move_writes_to_new_target(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        # _CANNED targets step 2; move it to step 3, then keep.
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["m", "3", "k"]),
        )
        assert rc == 0
        plan = parse_plan(path)
        assert plan.step_by_id(2).gate == []  # moved off
        assert plan.step_by_id(3).gate == ["pytest tests/x.py -q"]  # moved onto

    def test_move_rejects_invalid_target_then_accepts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        # 99 isn't a remaining step (reprompt), "x" isn't a number (reprompt),
        # then 3 is accepted; keep.
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["m", "99", "m", "x", "m", "3", "k"]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(3).gate == ["pytest tests/x.py -q"]

    def test_move_to_done_step_is_rejected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_plan(tmp_path)
        # Step 1 is done — not a valid target; reprompt, then 3, keep.
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["m", "1", "m", "3", "k"]),
        )
        assert rc == 0
        plan = parse_plan(path)
        assert plan.step_by_id(1).gate == []  # done step never gated
        assert plan.step_by_id(3).gate == ["pytest tests/x.py -q"]

    def test_run_log_records_the_call_and_outcome(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input(["k"]),
        )
        assert rc == 0
        log = _read_run_log(tmp_path, "myplan")
        events = [e["event"] for e in log]
        assert "run_start" in events
        run_ends = [e for e in log if e["event"] == "run_end"]
        assert run_ends and run_ends[-1]["outcome"] == "ok"

    def test_yes_reports_without_writing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path, yes=True),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input([]),  # must not be consulted
        )
        assert rc == 0
        out = capsys.readouterr()
        assert "pytest tests/x.py -q" in out.out
        assert "not written" in out.err
        assert parse_plan(path).step_by_id(2).gate == []  # nothing written

    def test_non_tty_reports_without_writing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: False)
        path = _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input([]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(2).gate == []

    def test_no_done_steps_is_noop(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir(exist_ok=True)
        path = tmp_path / "fresh.md"
        path.write_text(
            "---\ntitle: Fresh\nstatus: in-progress\npriority: low\nsteps:\n"
            "  - id: 1\n    title: first\n    status: current\n---\n",
            encoding="utf-8",
        )
        rc = cmd_suggest_gates(
            _args(tmp_path, slug="fresh"),
            invoker=_raises_if_called,
            input_fn=_queue_input([]),
        )
        assert rc == 0

    def test_all_done_is_noop(self, tmp_path: Path) -> None:
        (tmp_path / ".git").mkdir(exist_ok=True)
        path = tmp_path / "complete.md"
        path.write_text(
            "---\ntitle: Done\nstatus: in-progress\npriority: low\nsteps:\n"
            "  - id: 1\n    title: first\n    status: done\n---\n",
            encoding="utf-8",
        )
        rc = cmd_suggest_gates(
            _args(tmp_path, slug="complete"),
            invoker=_raises_if_called,
            input_fn=_queue_input([]),
        )
        assert rc == 0

    def test_unparseable_response_returns_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        _seed_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path),
            invoker=lambda p: "garbage",
            input_fn=_queue_input([]),
        )
        assert rc == 1

    # --- --all-steps (pre-build) ---

    def test_all_steps_writes_gate_on_fresh_plan(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        path = _seed_fresh_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path, slug="fresh", all_steps=True),
            invoker=lambda p: _CANNED,  # targets step 2
            input_fn=_queue_input(["k"]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(2).gate == ["pytest tests/x.py -q"]

    def test_fresh_plan_without_all_steps_is_noop(self, tmp_path: Path) -> None:
        # Default (no --all-steps) on a plan with no done steps: short-circuit
        # before any backend call and write nothing.
        path = _seed_fresh_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path, slug="fresh"),
            invoker=_raises_if_called,
            input_fn=_queue_input([]),
        )
        assert rc == 0
        assert parse_plan(path).step_by_id(2).gate == []

    def test_all_steps_yes_reports_without_writing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        path = _seed_fresh_plan(tmp_path)
        rc = cmd_suggest_gates(
            _args(tmp_path, slug="fresh", yes=True, all_steps=True),
            invoker=lambda p: _CANNED,
            input_fn=_queue_input([]),  # must not be consulted
        )
        assert rc == 0
        out = capsys.readouterr()
        assert "pytest tests/x.py -q" in out.out
        assert "not written" in out.err
        assert parse_plan(path).step_by_id(2).gate == []  # nothing written

    def test_cmd_suggest_gates_refuses_an_unsupported_detail_marker(
        self, tmp_path: Path
    ) -> None:
        from plan_tool.detail_artifacts import (
            DetailFormatError,
            render_detail_format_version_marker,
        )

        path = _seed_plan(tmp_path)
        plan_text = path.read_text(encoding="utf-8").replace(
            "    change_type: refactor\n",
            "    change_type: refactor\n    detail: 01.md\n",
        )
        path.write_text(plan_text, encoding="utf-8")
        (tmp_path / "01.md").write_text(
            f"# Step 1\n{render_detail_format_version_marker(999)}\n\nfine.\n",
            encoding="utf-8",
        )

        with pytest.raises(DetailFormatError):
            cmd_suggest_gates(
                _args(tmp_path),
                invoker=_raises_if_called,
                input_fn=_queue_input([]),
            )
