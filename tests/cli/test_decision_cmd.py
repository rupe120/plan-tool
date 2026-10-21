"""Command-contract tests for explicit decomposition-decision recording."""

from __future__ import annotations

import argparse
from pathlib import Path

import pytest

from plan_tool.capability_catalog import check_capabilities
from plan_tool.cli.app import COMMAND_MODULES, main
from plan_tool.cli.parser import CANONICAL_COMMAND_ORDER, assemble
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.telemetry import read_decisions


def test_decide_records_plan_anchor(registered_plan, capsys) -> None:
    plan_path = registered_plan.plans_dir / "1-demo.md"
    before = plan_path.read_bytes()
    rc = main(
        registered_plan.argv(
            "decide",
            "1-demo",
            "--outcome",
            "withdraw",
            "--anchor",
            "plan",
            "--rationale",
            "The premise is disproved.",
        )
    )

    assert rc == 0
    assert capsys.readouterr().out == "Recorded withdraw decision for demo at plan.\n"
    (event,) = read_decisions(registered_plan.root)
    assert event.kind == "decomposition-decision"
    assert event.decision == "recorded"
    assert event.plan_slug == "demo"
    assert event.anchor == "plan"
    assert event.context == {
        "outcome": "withdraw",
        "rationale": "The premise is disproved.",
    }
    assert event.plan_fingerprint == compute_plan_fingerprint(plan_path)
    assert plan_path.read_bytes() == before
    assert not (registered_plan.root / ".plan-tool" / "runs").exists()


def test_decide_records_existing_step_anchor(registered_plan, capsys) -> None:
    rc = main(
        registered_plan.argv(
            "decide",
            "demo",
            "--outcome",
            "split",
            "--anchor",
            "step:1",
            "--rationale",
            "The step owns two independently releasable outcomes.",
        )
    )

    assert rc == 0
    event = read_decisions(registered_plan.root)[0]
    assert event.anchor == "step:1"
    assert event.context["outcome"] == "split"


@pytest.mark.parametrize("anchor", ("step:2", "step:01", "step:one", "other"))
def test_decide_rejects_invalid_or_missing_anchor(registered_plan, capsys, anchor) -> None:
    rc = main(
        registered_plan.argv(
            "decide",
            "demo",
            "--outcome",
            "single",
            "--anchor",
            anchor,
            "--rationale",
            "One coherent outcome remains.",
        )
    )

    assert rc == 2
    assert "--anchor" in capsys.readouterr().err
    assert read_decisions(registered_plan.root) == []


def test_decide_rejects_blank_rationale_before_write(registered_plan, capsys) -> None:
    rc = main(
        registered_plan.argv(
            "decide",
            "demo",
            "--outcome",
            "single",
            "--anchor",
            "plan",
            "--rationale",
            "   ",
        )
    )

    assert rc == 2
    assert "--rationale must be non-empty" in capsys.readouterr().err
    assert read_decisions(registered_plan.root) == []


def test_decide_rejects_unknown_outcome_before_write(registered_plan) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(
            registered_plan.argv(
                "decide",
                "demo",
                "--outcome",
                "unknown",
                "--anchor",
                "plan",
                "--rationale",
                "reason",
            )
        )

    assert excinfo.value.code == 2
    assert read_decisions(registered_plan.root) == []


def test_decide_reports_unacknowledged_persistence(registered_plan, monkeypatch, capsys) -> None:
    import plan_tool.cli.decision_cmd as decision_cmd

    monkeypatch.setattr(
        decision_cmd, "record_decomposition_decision", lambda *args, **kwargs: False
    )

    rc = main(
        registered_plan.argv(
            "decide",
            "demo",
            "--outcome",
            "defer",
            "--anchor",
            "plan",
            "--rationale",
            "Waiting on labelled evidence.",
        )
    )

    assert rc == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "could not persist decomposition decision" in captured.err
    assert read_decisions(registered_plan.root) == []


def test_decide_registered_and_ordered() -> None:
    parser, dispatch = assemble("test", COMMAND_MODULES)
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert dispatch["decide"].__name__ == "cmd_decide"
    names = [action.dest for action in subparsers._choices_actions]
    decide_index = names.index("decide")
    assert names[decide_index - 1] == "telemetry"
    assert CANONICAL_COMMAND_ORDER[CANONICAL_COMMAND_ORDER.index("decide") - 1] == "telemetry"


def test_decide_has_owning_capability() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    findings = check_capabilities(repo_root)
    assert not any(
        finding.kind == "orphan-subcommand" and "decide" in finding.message
        for finding in findings
    )
