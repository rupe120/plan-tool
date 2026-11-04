"""Tests for ``plan_tool.cli.parser``'s shared parent-parser factories."""

from __future__ import annotations

import argparse
import importlib.metadata
import tomllib
from pathlib import Path

import pytest

from plan_tool.cli import build_parser, main
from plan_tool.cli import parser as parser_module
from plan_tool.cli.parser import make_yes_parent, package_version

SHARED_YES_HELP = (
    "auto-accept Y/N confirmation prompts (proceed with the offered "
    "action without asking). Useful for scripted/unattended runs."
)

# Commands whose ``-y`` deliberately differs from the shared flag. See
# BACKLOG #80 and ``make_yes_parent``'s docstring.
VARIANT_YES_COMMANDS = ("suggest-gates", "scope-out", "worktree")


def _yes_action(parser: argparse.ArgumentParser):
    for action in parser._actions:
        if "--yes" in action.option_strings:
            return action
    return None


def _subparsers_by_name(parser: argparse.ArgumentParser) -> dict:
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return dict(action.choices)
    return {}


class TestMakeYesParent:
    def test_returns_a_fresh_parser_each_call(self) -> None:
        """A factory, not a shared instance.

        ``parents=`` copies actions by reference, so handing one instance
        to every command module would let a later ``set_defaults`` on one
        subparser mutate the flag for all of them.
        """
        first, second = make_yes_parent(), make_yes_parent()
        assert first is not second
        assert _yes_action(first) is not _yes_action(second)

    def test_default_mutation_does_not_leak_between_callers(self) -> None:
        first, second = make_yes_parent(), make_yes_parent()
        _yes_action(first).default = True
        assert _yes_action(second).default is False

    def test_carries_the_shared_flag_contract(self) -> None:
        action = _yes_action(make_yes_parent())
        assert action is not None
        assert action.option_strings == ["-y", "--yes"]
        assert action.default is False
        assert action.help == SHARED_YES_HELP


class TestVariantYesFlagsStaySeparate:
    """The three commands whose ``-y`` means something else keep their own.

    Pinned as a test because the distinction is invisible to a reader
    scanning for duplication: the declarations look near-identical, and
    ``suggest-gates -y`` in particular does not mean auto-accept at all —
    it selects report-instead-of-prompt, so the shared help text would be
    an actively false claim about the flag.
    """

    def test_variant_commands_do_not_use_the_shared_help(self) -> None:
        import plan_tool.cli.app as app
        from plan_tool.cli.parser import assemble

        parser, _ = assemble(app.__doc__, app.COMMAND_MODULES)
        subs = _subparsers_by_name(parser)
        for name in VARIANT_YES_COMMANDS:
            sub = subs.get(name)
            assert sub is not None, f"{name} is no longer a registered command"
            actions = [sub] + list(_subparsers_by_name(sub).values())
            helps = {
                a.help for a in (_yes_action(p) for p in actions) if a is not None
            }
            assert helps, f"{name} no longer declares -y/--yes"
            assert SHARED_YES_HELP not in helps, (
                f"{name}'s -y was folded onto the shared parent; its flag means "
                "something different there — see BACKLOG #80"
            )


def _write_pyproject(root: Path, body: str) -> None:
    (root / "pyproject.toml").write_text(body, encoding="utf-8")


def _stale_install_metadata(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    monkeypatch.setattr(importlib.metadata, "version", lambda name: version)


def _no_install_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(importlib.metadata, "version", missing)


class TestPackageVersion:
    """``plan-tool --version`` reports the released version, not a stale install's."""

    def test_source_checkout_version_wins_over_stale_install_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An editable install freezes its metadata, so a bump would not show."""
        _write_pyproject(tmp_path, '[project]\nname = "plan-tool"\nversion = "9.9.9"\n')
        _stale_install_metadata(monkeypatch, "0.0.1")
        assert package_version(tmp_path) == "9.9.9"

    def test_a_pyproject_for_another_package_beside_the_source_is_ignored(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_pyproject(tmp_path, '[project]\nname = "something-else"\nversion = "5.5.5"\n')
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_installed_package_without_a_pyproject_reads_its_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_a_pyproject_with_a_dynamic_version_falls_back_to_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_pyproject(tmp_path, '[project]\nname = "plan-tool"\ndynamic = ["version"]\n')
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_an_unreadable_pyproject_falls_back_to_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_pyproject(tmp_path, "this is [not valid toml")
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_a_pyproject_that_is_not_valid_utf8_falls_back_to_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        (tmp_path / "pyproject.toml").write_bytes(b'[project]\nname = "plan-tool"\n\xff\xfe')
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_a_pyproject_whose_project_entry_is_not_a_table_falls_back_to_metadata(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _write_pyproject(tmp_path, 'project = "not a table"\n')
        _stale_install_metadata(monkeypatch, "1.2.3")
        assert package_version(tmp_path) == "1.2.3"

    def test_a_version_that_cannot_be_read_is_reported_as_unknown_not_guessed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _no_install_metadata(monkeypatch)
        assert package_version(tmp_path) == "unknown"

    def test_this_checkouts_version_matches_its_pyproject(self) -> None:
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]
        assert package_version() == declared


class TestVersionFlag:
    def test_flag_prints_the_version_and_exits_zero_without_a_subcommand(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr(parser_module, "package_version", lambda: "1.2.3")
        with pytest.raises(SystemExit) as exit_info:
            build_parser().parse_args(["--version"])
        assert exit_info.value.code == 0
        assert capsys.readouterr().out == "plan-tool 1.2.3\n"

    def test_main_serves_the_flag_before_any_command_setup(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The real entry point exits 0 on the flag, ahead of backend selection."""
        with pytest.raises(SystemExit) as exit_info:
            main(["--version"])
        assert exit_info.value.code == 0
        assert capsys.readouterr().out.startswith("plan-tool ")

    def test_verbose_stays_usable_by_its_full_and_short_names(self) -> None:
        for spelling in ("-v", "--verbose"):
            assert build_parser().parse_args([spelling, "list"]).verbose is True

    def test_an_abbreviation_matching_both_flags_is_rejected_not_guessed(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """``--ver`` once meant ``--verbose``; with ``--version`` it is ambiguous.

        Deliberately accepted (see the changelog): argparse must refuse it,
        never silently pick one of the two flags.
        """
        with pytest.raises(SystemExit) as exit_info:
            build_parser().parse_args(["--ver", "list"])
        assert exit_info.value.code == 2
        assert "ambiguous option" in capsys.readouterr().err

    def test_building_the_parser_does_not_read_the_version(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Only ``--version`` pays for the lookup, not every command."""

        def must_not_run() -> str:
            raise AssertionError("the version was read while building the parser")

        monkeypatch.setattr(parser_module, "package_version", must_not_run)
        help_text = build_parser().format_help()
        assert "--version" in help_text


@pytest.mark.parametrize("command", ("direct-run", "direct-jira"))
def test_retired_direct_commands_are_rejected(command: str) -> None:
    with pytest.raises(SystemExit) as exit_info:
        build_parser().parse_args([command])
    assert exit_info.value.code == 2


def test_standalone_pipeline_commands_remain_registered() -> None:
    import plan_tool.cli.app as app
    from plan_tool.cli.parser import assemble

    parser, dispatch = assemble(app.__doc__, app.COMMAND_MODULES)
    commands = {"create", "detail", "jira", "run", "reconcile-code"}
    assert commands <= _subparsers_by_name(parser).keys()
    assert commands <= dispatch.keys()


def test_completeness_apply_is_rejected_before_dispatch(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        build_parser().parse_args(["completeness-apply", "demo"])
    assert exc.value.code == 2
    assert "invalid choice: 'completeness-apply'" in capsys.readouterr().err


def test_completeness_retirement_preserves_surviving_commands() -> None:
    commands = _subparsers_by_name(build_parser())
    assert {"completeness-audit", "data-contract-apply",
            "review", "reconcile-plan", "reconcile-code", "reconcile-plan-walk"} <= commands.keys()
