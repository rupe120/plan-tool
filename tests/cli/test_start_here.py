"""Bare ``plan-tool`` prints a short core path instead of a usage error."""

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


def test_bare_invocation_prints_the_core_path_and_exits_zero(capsys) -> None:
    assert main([]) == 0

    out = capsys.readouterr().out
    assert out == START_HERE
    assert "plan-tool --help" in out
    # The skill is installed machine-wide first, because the skill is what
    # collects and confirms the intent before running `init`.
    assert "plan-tool install-skill --user" in out


def test_every_start_here_command_parses_against_the_real_parser() -> None:
    parser, dispatch = assemble(cli.__doc__, COMMAND_MODULES)
    lines = _command_lines()
    assert len(lines) == 7

    for line in lines:
        tokens = shlex.split(line)[1:]
        tokens = [_PLACEHOLDERS.get(token, token) for token in tokens]
        args = parser.parse_args(tokens)
        assert args.command in dispatch


def test_global_flags_without_a_subcommand_still_report_the_usage_error() -> None:
    """Only a fully bare invocation is the start screen; a flag means intent."""
    with pytest.raises(SystemExit) as raised:
        main(["--debug"])

    assert raised.value.code == 2


def test_full_help_points_newcomers_at_the_start_screen(capsys) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])

    assert "Run plan-tool with no arguments for the core path." in capsys.readouterr().out
