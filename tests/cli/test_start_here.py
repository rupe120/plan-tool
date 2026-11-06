"""Bare ``plan-tool`` prints a short core path as its usage error."""

from __future__ import annotations

import shlex

import pytest

from plan_tool import cli
from plan_tool.cli.app import COMMAND_MODULES, START_HERE, main
from plan_tool.cli.parser import assemble

_PLACEHOLDERS = {"<slug>": "demo", "<name>": "demo", "<seed.md>": "seed.md"}


def _command_lines() -> list[str]:
    return [
        line.strip().split("  ")[0]
        for line in START_HERE.splitlines()
        if line.startswith("  plan-tool ")
    ]


def test_bare_invocation_prints_the_core_path_as_a_usage_error(capsys) -> None:
    """A missing subcommand stays exit 2, so a script with an empty one fails."""
    assert main([]) == 2

    captured = capsys.readouterr()
    assert captured.err == START_HERE
    assert captured.out == ""


def test_every_start_here_command_parses_against_the_real_parser() -> None:
    parser, dispatch = assemble(cli.__doc__, COMMAND_MODULES)

    for line in _command_lines():
        tokens = shlex.split(line)[1:]
        tokens = [_PLACEHOLDERS.get(token, token) for token in tokens]
        args = parser.parse_args(tokens)
        assert args.command in dispatch


def test_start_here_lines_fit_an_80_column_terminal() -> None:
    assert max(len(line) for line in START_HERE.splitlines()) <= 80


def test_core_path_follows_the_pipeline_order() -> None:
    commands = [line.split()[1] for line in _command_lines()]

    assert commands == [
        "install-skill",
        "create",
        "completeness-audit",
        "detail",
        "completeness-audit",
        "run",
        "reconcile-code",
    ]


def test_core_path_runs_every_step_and_ends_with_the_reconcile_tail() -> None:
    lines = _command_lines()

    assert "plan-tool run <name> --all --commit" in lines
    assert lines[-1] == "plan-tool reconcile-code <name> --all"


def test_init_is_left_to_the_skill_rather_than_shown_as_a_command() -> None:
    """A copied placeholder intent would be written as the real profile."""
    assert not any(line.startswith("plan-tool init") for line in _command_lines())
    assert "runs plan-tool init" in START_HERE


@pytest.mark.parametrize("integration", ("codex", "cursor"))
def test_skill_install_advice_for_other_integrations_parses(integration: str) -> None:
    parser, _ = assemble(cli.__doc__, COMMAND_MODULES)

    assert f"--integration {integration}" in START_HERE
    args = parser.parse_args(["install-skill", "--integration", integration, "--user"])
    assert args.integration == integration


def test_global_flags_without_a_subcommand_still_report_the_usage_error() -> None:
    """Only a fully bare invocation is the start screen; a flag means intent."""
    with pytest.raises(SystemExit) as raised:
        main(["--debug"])

    assert raised.value.code == 2


def test_full_help_points_newcomers_at_the_start_screen(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "Run plan-tool with no arguments for the core path." in capsys.readouterr().out
