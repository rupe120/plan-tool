"""Command contract for deterministic project-profile initialization."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from plan_tool.capability_catalog import check_capabilities
from plan_tool.cli.app import COMMAND_MODULES, main
from plan_tool.cli.parser import CANONICAL_COMMAND_ORDER, assemble
from plan_tool.project_profile import PROJECT_PROFILE_SUBPATH


def _argv(repo_root: Path, *command_args: str) -> list[str]:
    return ["--repo-root", str(repo_root), *command_args]


def test_init_writes_one_operator_supplied_profile(tmp_path: Path, capsys) -> None:
    assert main(
        _argv(
            tmp_path,
            "init",
            "--intent",
            "Keep plan work aligned to the product.",
            "--non-goal",
            "Do not infer priorities.",
            "--decision",
            "Do not execute a plan without a demonstrated problem.",
        )
    ) == 0

    assert json.loads((tmp_path / PROJECT_PROFILE_SUBPATH).read_text(encoding="utf-8")) == {
        "schema_version": 1,
        "intent": "Keep plan work aligned to the product.",
        "non_goals": ["Do not infer priorities."],
        "decisions": ["Do not execute a plan without a demonstrated problem."],
    }
    output = capsys.readouterr().out
    assert "Initialized .plan-tool/project.json." in output
    assert "Commit it with the confirmed project decision." in output
    assert not (tmp_path / ".plan-tool" / "runs").exists()


def test_init_refuses_to_replace_an_existing_profile(tmp_path: Path, capsys) -> None:
    profile = tmp_path / PROJECT_PROFILE_SUBPATH
    profile.parent.mkdir()
    profile.write_text('{"schema_version": 1}\n', encoding="utf-8")
    original = profile.read_bytes()

    assert main(_argv(tmp_path, "init", "--intent", "A replacement.")) == 2

    assert profile.read_bytes() == original
    assert "already exists" in capsys.readouterr().err


@pytest.mark.parametrize(
    "flag",
    ("--intent", "--non-goal", "--decision"),
)
def test_init_rejects_blank_text_at_the_cli_boundary(
    tmp_path: Path, flag: str
) -> None:
    argv = _argv(tmp_path, "init", "--intent", "A real intent.")
    if flag == "--intent":
        argv[-1] = "   "
    else:
        argv.extend((flag, "   "))

    with pytest.raises(SystemExit) as raised:
        main(argv)

    assert raised.value.code == 2
    assert not (tmp_path / PROJECT_PROFILE_SUBPATH).exists()


def test_init_normalizes_each_logical_profile_value(tmp_path: Path) -> None:
    assert main(
        _argv(
            tmp_path,
            "init",
            "--intent",
            "Keep scope narrow.\n## Plan body",
            "--non-goal",
            "Do not add a service.\n### New scope",
            "--decision",
            "Prefer reversible changes.\n## Step",
        )
    ) == 0

    assert json.loads(
        (tmp_path / PROJECT_PROFILE_SUBPATH).read_text(encoding="utf-8")
    ) == {
        "schema_version": 1,
        "intent": "Keep scope narrow. ## Plan body",
        "non_goals": ["Do not add a service. ### New scope"],
        "decisions": ["Prefer reversible changes. ## Step"],
    }


def test_init_refuses_a_gitignored_profile(tmp_path: Path, capsys) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")

    assert main(_argv(tmp_path, "init", "--intent", "A real intent.")) == 2

    assert not (tmp_path / PROJECT_PROFILE_SUBPATH).exists()
    assert "is gitignored" in capsys.readouterr().err


def test_init_prefers_an_existing_profile_error_to_gitignore(
    tmp_path: Path, capsys
) -> None:
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
    profile = tmp_path / PROJECT_PROFILE_SUBPATH
    profile.parent.mkdir()
    profile.write_text('{"schema_version": 1}\n', encoding="utf-8")

    assert main(_argv(tmp_path, "init", "--intent", "A replacement.")) == 2

    error_output = capsys.readouterr().err
    assert "already exists" in error_output
    assert "is gitignored" not in error_output


def test_init_is_registered_between_status_and_validate() -> None:
    parser, dispatch = assemble("test", COMMAND_MODULES)
    subparsers = next(
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    )
    names = [action.dest for action in subparsers._choices_actions]
    index = names.index("init")

    assert dispatch["init"].__name__ == "cmd_init"
    assert names[index - 1 : index + 2] == ["status", "init", "validate"]
    canonical_index = CANONICAL_COMMAND_ORDER.index("init")
    assert CANONICAL_COMMAND_ORDER[canonical_index - 1 : canonical_index + 2] == (
        "status",
        "init",
        "validate",
    )


def test_init_has_an_owning_capability() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    findings = check_capabilities(repo_root)
    assert not any(
        finding.kind == "orphan-subcommand" and "init" in finding.message
        for finding in findings
    )
