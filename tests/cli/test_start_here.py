"""Bare ``plan-tool`` prints a short core path instead of a usage error."""

from __future__ import annotations

import shlex
import sys

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


def test_bare_invocation_at_a_terminal_prints_the_core_path_and_exits_zero(
    capsys, monkeypatch
) -> None:
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    assert main([]) == 0

    assert capsys.readouterr().out == START_HERE


def test_bare_invocation_from_a_script_still_exits_nonzero(capsys) -> None:
    """A wrapper whose subcommand variable expanded to nothing must still fail."""
    assert main([]) == 2

    assert capsys.readouterr().out == START_HERE


def test_every_start_here_command_parses_against_the_real_parser() -> None:
    parser, dispatch = assemble(cli.__doc__, COMMAND_MODULES)
    lines = _command_lines()
    assert len(lines) == 7

    for line in lines:
        tokens = shlex.split(line)[1:]
        tokens = [_PLACEHOLDERS.get(token, token) for token in tokens]
        args = parser.parse_args(tokens)
        assert args.command in dispatch


def test_core_path_runs_every_step_and_ends_with_the_reconcile_tail() -> None:
    lines = _command_lines()

    assert "plan-tool run <name> --all --commit" in lines
    assert lines[-1] == "plan-tool reconcile-code <name> --all"


def test_init_is_left_to_the_skill_rather_than_shown_as_a_command() -> None:
    """A copied placeholder intent would be written as the real profile."""
    assert not any(line.startswith("plan-tool init") for line in _command_lines())
    assert "runs plan-tool init" in START_HERE


def test_skill_install_names_the_other_integrations() -> None:
    assert "plan-tool install-skill --integration claude --user" in _command_lines()
    assert "--integration codex" in START_HERE
    assert "--integration cursor" in START_HERE


def test_global_flags_without_a_subcommand_still_report_the_usage_error() -> None:
    """Only a fully bare invocation is the start screen; a flag means intent."""
    with pytest.raises(SystemExit) as raised:
        main(["--debug"])

    assert raised.value.code == 2


def test_full_help_points_newcomers_at_the_start_screen(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "Run plan-tool with no arguments for the core path." in capsys.readouterr().out
