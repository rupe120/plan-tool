"""Command-contract tests for the read-only ``plan-tool telemetry`` surface."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from plan_tool.capability_catalog import check_capabilities
from plan_tool.cli.app import COMMAND_MODULES, main
from plan_tool.cli.parser import CANONICAL_COMMAND_ORDER, assemble
from plan_tool.telemetry import record_decision
from plan_tool.telemetry_analysis import analyze_telemetry, render_analysis


def _argv(repo_root: Path, *command_args: str) -> list[str]:
    return ["--repo-root", str(repo_root), *command_args]


def _seed(repo_root: Path) -> None:
    record_decision(
        repo_root,
        kind="apply-verdict",
        decision="recorded",
        plan_slug="first",
        context={"verdict": "APPLIED"},
    )
    record_decision(
        repo_root,
        kind="apply-verdict",
        decision="recorded",
        plan_slug="second",
        context={"verdict": "NOT-APPLICABLE"},
    )


def test_telemetry_default_prints_report(tmp_path, capsys) -> None:
    _seed(tmp_path)
    expected = render_analysis(analyze_telemetry(tmp_path))

    assert main(_argv(tmp_path, "telemetry")) == 0
    assert capsys.readouterr().out == expected + "\n"


def test_telemetry_empty_log_exits_zero(tmp_path, capsys) -> None:
    assert main(_argv(tmp_path, "telemetry")) == 0
    assert capsys.readouterr().out == "No telemetry recorded yet.\n"


def test_telemetry_json_emits_parseable_payload(tmp_path, capsys) -> None:
    _seed(tmp_path)

    assert main(_argv(tmp_path, "telemetry", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_events"] == 2
    assert isinstance(payload["aggregates"], list)
    assert isinstance(payload["recommendations"], list)
    assert payload["calibration"] == {"total_findings": 0, "signals": []}


def test_telemetry_json_matches_analysis(tmp_path, capsys) -> None:
    _seed(tmp_path)
    analysis = analyze_telemetry(tmp_path)

    assert main(_argv(tmp_path, "telemetry", "--json")) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["total_events"] == analysis.total_events
    assert [item["total"] for item in payload["aggregates"]] == [
        aggregate.total for aggregate in analysis.aggregates
    ]


def test_telemetry_spends_no_claude_and_writes_no_run_log(tmp_path) -> None:
    _seed(tmp_path)

    assert main(_argv(tmp_path, "telemetry")) == 0
    assert not (tmp_path / ".plan-tool" / "runs").exists()


def test_telemetry_registered_and_ordered() -> None:
    parser, dispatch = assemble("test", COMMAND_MODULES)
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )

    assert dispatch["telemetry"].__name__ == "cmd_telemetry"
    names = [action.dest for action in subparsers._choices_actions]
    telemetry_index = names.index("telemetry")
    assert names[telemetry_index - 1] == "convergence"
    assert CANONICAL_COMMAND_ORDER[CANONICAL_COMMAND_ORDER.index("telemetry") - 1] == "convergence"


def test_telemetry_has_owning_capability() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    findings = check_capabilities(repo_root)
    assert not any(
        finding.kind == "orphan-subcommand" and "telemetry" in finding.message
        for finding in findings
    )
