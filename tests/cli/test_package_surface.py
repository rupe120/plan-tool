"""Package-surface contract tests for ``plan_tool.cli``.

This is the guard rail for the upcoming refactor that splits the
~11k-line ``cli.py`` into an intent-grouped ``plan_tool.cli`` *package*.
The tests here lock the parts of the CLI that callers (and the rest of
the test suite) depend on, so the split can move functions between
modules freely as long as it preserves these contracts:

* the **import surface** — symbols other modules / tests import from
  ``plan_tool.cli`` keep resolving through the package's ``__init__``;
* the **CLI surface** — ``plan-tool --help`` output (a golden snapshot)
  and the parser↔dispatcher correspondence (every registered subcommand
  has a handler and vice versa).

Split-proof test conventions (followed by every test in ``tests/cli/``)
-----------------------------------------------------------------------
1. Import the things under test **only** from ``plan_tool.cli`` (the
   package entry point), never from a would-be submodule. After the
   split the package ``__init__`` re-exports the surface, so these
   imports stay stable.
2. Never ``monkeypatch.setattr`` a ``plan_tool.cli`` module global. A
   global that moves to a submodule during the split would make the
   patch silently target the wrong object. Instead, either drive
   behavior through ``main(argv)`` against a temp repo (see
   ``conftest.CliRepo``), or patch the *domain* module that owns the
   dependency (``plan_tool.launcher``, ``plan_tool.shell``,
   ``plan_tool.review``, …).
3. Treat ``build_parser()`` and ``main()`` as the stable entry points;
   reach private helpers through them rather than calling helpers that
   may be relocated.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import shutil
from pathlib import Path

import pytest

import plan_tool.cli as cli
from plan_tool import model_specs
from plan_tool.backend import CLAUDE_BACKEND, get_active_backend, set_active_backend
from plan_tool.shell import EXEC_NOT_FOUND_EXIT


@pytest.fixture(autouse=True)
def _restore_active_backend():
    """Reset the process-global active backend after each test.

    ``main()`` mutates the module-global active backend via
    ``set_active_backend``; without this the selection from one test
    would leak into the next.
    """
    yield
    set_active_backend(CLAUDE_BACKEND)


# The symbols guaranteed to resolve via ``from plan_tool.cli import X``.
# ``walk_recommendations`` is re-exported from ``plan_tool.review_walk``;
# the rest are defined in the cli module today. The package split must
# keep all of them importable from ``plan_tool.cli``.
MODULE_LEVEL_SURFACE = (
    "main",
    "build_parser",
    "AVAILABLE_MODES",
    "_iter_events",
    "_print_attributed_files",
    "_review_walk_environment_allows",
    "walk_recommendations",
)

# Golden snapshot of ``plan-tool --help``. Self-seeding: the first run
# writes it, later runs compare against it. Set ``UPDATE_CLI_GOLDEN=1``
# to re-baseline after an intentional help change.
GOLDEN_HELP_PATH = Path(__file__).parent / "package_surface_help.golden.txt"


def _subparser_command_names(parser: argparse.ArgumentParser) -> set[str]:
    """Return every subcommand name (including aliases) the parser registers."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return set(action.choices)
    raise AssertionError("build_parser() registered no subparsers action")


# Commands whose dispatch handler does not follow the mechanical
# ``cmd_<name-with-underscores>`` rule. ``completeness-audit`` is the
# primary command name; its handler keeps the shorter historical name
# (shared with the hidden ``completeness`` alias). The ``reconcile*``
# commands keep their historical ``cmd_review*`` handler names (the
# ``review*`` aliases still resolve mechanically, so only the canonical
# names need an entry here).
_HANDLER_NAME_EXCEPTIONS = {
    "completeness-audit": "cmd_completeness",
    # ``reconcile-plan`` (+ aliases reconcile/review) keep the ``cmd_review``
    # handler; ``reconcile-plan-walk`` (+ aliases reconcile-walk/review-walk)
    # keep ``cmd_review_walk`` (``review-walk`` resolves mechanically).
    "reconcile-plan": "cmd_review",
    "reconcile": "cmd_review",
    "reconcile-plan-walk": "cmd_review_walk",
    "reconcile-walk": "cmd_review_walk",
    # ``verify-all`` resolves mechanically to ``cmd_verify_all``; its aliases
    # (reconcile-all / verify) route to the same dispatcher.
    "reconcile-all": "cmd_verify_all",
    "verify": "cmd_verify_all",
}


def _handler_name_for(command: str) -> str:
    """Map a subcommand name to its module-level handler attribute.

    Every dispatch handler is a module-level ``cmd_*`` callable exported
    from ``plan_tool.cli`` (the split's ``__init__`` re-export list
    guarantees this stays true after the package conversion), so the
    parser↔dispatch correspondence is checkable through the public
    surface — no bytecode or source introspection, which would couple
    this test to the monolith's internal dict literal.
    """
    return _HANDLER_NAME_EXCEPTIONS.get(
        command, "cmd_" + command.replace("-", "_")
    )


def _render_help(monkeypatch: pytest.MonkeyPatch) -> str:
    """Render ``plan-tool --help`` deterministically (fixed terminal width)."""
    monkeypatch.setenv("COLUMNS", "80")
    return cli.build_parser().format_help()


class TestImportSurface:
    def test_module_level_symbols_importable(self) -> None:
        """Each guaranteed symbol resolves as an attribute of the package."""
        module = importlib.import_module("plan_tool.cli")
        missing = [
            name for name in MODULE_LEVEL_SURFACE if not hasattr(module, name)
        ]
        assert missing == [], f"missing from plan_tool.cli surface: {missing}"

    def test_from_import_statement_resolves(self) -> None:
        """The literal ``from plan_tool.cli import ...`` line succeeds."""
        from plan_tool.cli import (  # noqa: F401
            AVAILABLE_MODES,
            _iter_events,
            _print_attributed_files,
            _review_walk_environment_allows,
            build_parser,
            main,
            walk_recommendations,
        )

    def test_apply_finding_dispatch_reachable(self) -> None:
        """``_dispatch_apply_finding`` is a nested helper of ``_build_review_action_fn``.

        The apply-finding dispatch is part of the surface later steps
        lean on, but it is *not* a module-level symbol today — it is
        defined inside ``_build_review_action_fn``'s closure. The split
        must keep it reachable through that builder (or promote it to a
        module global and update this test). We assert the nested code
        object exists so the contract is recorded either way.
        """
        nested_names = {
            getattr(const, "co_name", None)
            for const in cli._build_review_action_fn.__code__.co_consts
        }
        assert "_dispatch_apply_finding" in nested_names
        # It is genuinely not a module global yet — document that fact so
        # a future promotion is a deliberate, test-visible change.
        assert not hasattr(cli, "_dispatch_apply_finding")


class TestHelpGoldenSnapshot:
    @staticmethod
    def _normalize_help_snapshot(text: str) -> str:
        """Ignore argparse patch-version wrapping of the subcommand metavar."""
        return re.sub(r"(\{[^}\n]+\})\s*\n\s+(\.\.\.)", r"\1 \2", text)

    def test_help_matches_golden(self, monkeypatch: pytest.MonkeyPatch) -> None:
        help_text = _render_help(monkeypatch)
        if not GOLDEN_HELP_PATH.exists() or os.environ.get("UPDATE_CLI_GOLDEN"):
            GOLDEN_HELP_PATH.write_text(help_text, encoding="utf-8")
            pytest.skip(f"seeded golden help snapshot at {GOLDEN_HELP_PATH.name}")
        assert self._normalize_help_snapshot(
            help_text
        ) == self._normalize_help_snapshot(
            GOLDEN_HELP_PATH.read_text(encoding="utf-8")
        )

    def test_normalize_collapses_metavar_dots_wrap(self) -> None:
        """The two argparse wrap forms of the subcommand ``{...} ...`` metavar
        (one-line vs the trailing ``...`` broken to its own line, which varies
        across CPython patch releases) must normalize to the *same* text — the
        cross-version guarantee ``test_help_matches_golden`` relies on. Pinned
        directly so a broken normalizer fails on any interpreter, not only the
        one whose argparse happens to render the other form."""
        one_line = (
            "                 {list,status,install-skill} ...\n\n"
            "plan-tool command-line entry point.\n"
        )
        two_line = (
            "                 {list,status,install-skill}\n"
            "                 ...\n\n"
            "plan-tool command-line entry point.\n"
        )
        norm = self._normalize_help_snapshot
        assert norm(one_line) == norm(two_line)
        # The collapsed form is the single-line shape (idempotent on it).
        assert norm(one_line) == one_line

    def test_help_lists_every_subcommand(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Structural invariant that holds even before the golden is seeded."""
        help_text = _render_help(monkeypatch)
        assert "plan-tool" in help_text
        for command in _subparser_command_names(cli.build_parser()):
            assert command in help_text, f"{command!r} absent from --help"


class TestRegistrationSeam:
    """Pin the ``COMMAND_MODULES`` + ``register``/``assemble`` seam.

    These tests reach into ``plan_tool.cli.app`` and ``plan_tool.cli.parser``
    deliberately: the registry is an internal contract that later steps
    (11–16) plug into, not part of the public package surface. They prove
    the registry-built subparsers and the registry-built dispatch map
    cannot drift apart.
    """

    def test_command_modules_registry_excludes_app(self) -> None:
        """``app`` is absent from the registry once the split completes.

        Steps 11-18 carved every verb into a per-intent command module;
        step 19 finalized ``app`` as the thin entry, so it registers no
        subparsers and is no longer a ``COMMAND_MODULES`` member. The
        base-parser description is threaded from the package docstring
        independently of the registry (see ``build_parser`` / ``main``).
        """
        import plan_tool.cli.app as app

        assert app not in app.COMMAND_MODULES
        assert not hasattr(app, "register")

    def test_register_returns_dispatch_for_every_subcommand(self) -> None:
        import plan_tool.cli.app as app
        from plan_tool.cli.parser import assemble

        parser, dispatch = assemble(app.__doc__, app.COMMAND_MODULES)
        assert set(dispatch) == _subparser_command_names(parser)

    def test_deprecated_review_aliases_route_to_reconcile_handlers(self) -> None:
        """``review*`` are hidden aliases of the canonical ``reconcile*``.

        argparse routes an alias to the same subparser but sets
        ``args.command`` to the name as typed, so the dispatch map must
        resolve both the canonical name and its alias to the same handler.
        """
        import plan_tool.cli.app as app
        from plan_tool.cli.parser import assemble

        parser, dispatch = assemble(app.__doc__, app.COMMAND_MODULES)
        for canonical, aliases in (
            ("reconcile-plan", ("reconcile", "review")),
            ("reconcile-plan-walk", ("reconcile-walk", "review-walk")),
            ("verify-all", ("reconcile-all", "review-all", "verify")),
        ):
            for alias in aliases:
                assert dispatch[canonical] is dispatch[alias], (
                    f"{alias!r} must dispatch to the same handler as {canonical!r}"
                )

    def test_assemble_dispatch_values_are_callable(self) -> None:
        import plan_tool.cli.app as app
        from plan_tool.cli.parser import assemble

        _, dispatch = assemble(app.__doc__, app.COMMAND_MODULES)
        non_callable = sorted(c for c, h in dispatch.items() if not callable(h))
        assert non_callable == [], (
            f"dispatch entries with non-callable handlers: {non_callable}"
        )


class TestParserDispatcherCorrespondence:
    def test_scope_review_is_registered(self) -> None:
        parser = cli.build_parser()
        assert "scope-review" in _subparser_command_names(parser)
        assert callable(cli.cmd_scope_review)

    def test_every_subcommand_has_a_dispatch_handler(self) -> None:
        """Each registered subcommand resolves to a callable cmd_* handler."""
        unhandled = [
            command
            for command in _subparser_command_names(cli.build_parser())
            if not callable(getattr(cli, _handler_name_for(command), None))
        ]
        assert unhandled == [], (
            f"subcommands with no callable handler on plan_tool.cli: "
            f"{sorted(unhandled)}"
        )

    def test_every_dispatch_handler_has_a_subcommand(self) -> None:
        """Each public cmd_* handler is reachable from a registered command.

        Sub-dispatchers (``cmd_jira_config``, ``cmd_lessons_consolidate``)
        are reachable through their parent command's namespace, so a
        handler counts as covered when its stem extends a registered
        command's stem (``jira_config`` extends ``jira``). The reverse also
        counts: a handler whose stem a command extends (``cmd_completeness``
        reached via the ``completeness-audit`` subcommand).
        """
        command_stems = {
            c.replace("-", "_")
            for c in _subparser_command_names(cli.build_parser())
        }
        orphan = []
        for name in dir(cli):
            if not name.startswith("cmd_"):
                continue
            stem = name[len("cmd_"):]
            covered = stem in command_stems or any(
                stem.startswith(parent + "_") or parent.startswith(stem + "_")
                for parent in command_stems
            )
            if not covered:
                orphan.append(name)
        assert orphan == [], (
            f"cmd_* handlers with no registered subparser route: {orphan}"
        )


def _backend_action(parser: argparse.ArgumentParser) -> argparse.Action:
    """Return the ``--backend`` option action from ``parser``."""
    for action in parser._actions:
        if action.dest == "backend":
            return action
    raise AssertionError("build_parser() registered no --backend option")


class TestBackendSelection:
    """The global ``--backend`` flag, precedence, and missing-binary preflight.

    Drives selection through ``main(argv)`` (never patching a cli module
    global) and asserts the process-global active backend, per the
    split-proof conventions. ``PLAN_TOOL_BACKEND`` is cleared per test so
    the ambient environment can't perturb the precedence assertions.
    """

    def test_backend_flag_is_free_form(self) -> None:
        # An unregistered name is synthesized at selection (see
        # test_unregistered_backend_is_synthesized), so the flag carries no
        # ``choices`` constraint — argparse must accept e.g. --backend gemini.
        action = _backend_action(cli.build_parser())
        assert action.choices is None
        assert action.default is None

    def test_backend_default_is_claude(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        assert cli.main(tmp_repo.argv("list")) == 0
        assert get_active_backend().name == "claude"

    def test_backend_flag_selects_codex(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/codex")
        assert cli.main(tmp_repo.argv("--backend", "codex", "list")) == 0
        assert get_active_backend().name == "codex"

    def test_backend_env_selects_codex(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "codex")
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/codex")
        assert cli.main(tmp_repo.argv("list")) == 0
        assert get_active_backend().name == "codex"

    def test_backend_flag_beats_env(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "codex")
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/claude")
        assert cli.main(tmp_repo.argv("--backend", "claude", "list")) == 0
        assert get_active_backend().name == "claude"

    @pytest.mark.parametrize("model", ("gpt-5.6-terra", "chatgpt-4o-latest"))
    def test_openai_model_family_selects_codex_without_backend_flag(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch, model: str
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/codex")
        assert cli.main(tmp_repo.argv("--model", model, "list")) == 0
        active = get_active_backend()
        assert active.name == "codex"
        assert active.streaming_argv("P")[-3:] == ["-m", model, "P"]

    def test_model_family_beats_backend_environment_default(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "claude")
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/codex")
        assert cli.main(tmp_repo.argv("--model", "gpt-5.6-sol", "list")) == 0
        assert get_active_backend().name == "codex"

    def test_backend_flag_beats_model_family(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/claude")
        assert (
            cli.main(
                tmp_repo.argv(
                    "--backend", "claude", "--model", "gpt-5.6-terra", "list"
                )
            )
            == 0
        )
        assert get_active_backend().name == "claude"

    def test_gemini_model_selects_provisional_gemini_without_catalog_fetch(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(
            model_specs,
            "fetch_catalog",
            lambda **_kw: pytest.fail("an explicit model needs no default lookup"),
        )
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/gemini")
        assert cli.main(tmp_repo.argv("--model", "gemini-3-pro", "list")) == 0
        active = get_active_backend()
        assert active.name == "gemini"
        assert active.streaming_argv("P")[-3:] == ["--model", "gemini-3-pro", "P"]

    def test_unregistered_backend_is_synthesized(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # An unregistered name no longer hard-fails: it's synthesized into a
        # provisional backend whose default model is sourced from models.dev.
        # Patch the *domain* module's fetch (convention #2) so no network.
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "gemini")
        catalog = model_specs.Catalog(
            specs=(
                model_specs.ModelSpec(
                    id="gemini-3-pro", provider="google",
                    context_window=2_000_000, output_cost=10.0,
                ),
            ),
        )
        monkeypatch.setattr(model_specs, "fetch_catalog", lambda **_kw: catalog)
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/gemini")

        assert cli.main(tmp_repo.argv("list")) == 0
        active = get_active_backend()
        assert active.name == "gemini"
        # The models.dev-sourced default is spliced in via the backend's
        # --model flag.
        assert "gemini-3-pro" in active.streaming_argv("P")
        err = capsys.readouterr().err
        assert "not a registered integration" in err
        assert "gemini-3-pro" in err

    def test_unregistered_backend_missing_binary_fails_fast(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # A genuine typo still fails fast — synthesized, but its binary isn't
        # on PATH, so the explicit-selection preflight catches it. An offline
        # catalog (no default sourced) must not change that.
        monkeypatch.setattr(
            model_specs, "fetch_catalog",
            lambda **_kw: model_specs.Catalog(error="offline"),
        )
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        assert (
            cli.main(tmp_repo.argv("--backend", "bogus", "list"))
            == EXEC_NOT_FOUND_EXIT
        )
        message = capsys.readouterr().err
        assert "bogus" in message

    def test_backend_preflight_missing_binary_fails_fast(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        # Explicit codex selection with no binary on PATH fails fast.
        assert (
            cli.main(tmp_repo.argv("--backend", "codex", "list"))
            == EXEC_NOT_FOUND_EXIT
        )
        message = capsys.readouterr().err
        assert "codex" in message
        # The default-claude path (no explicit selection) is not blocked by
        # the same missing-binary condition — read-only ``list`` never
        # shells out.
        assert cli.main(tmp_repo.argv("list")) == 0

    def test_default_claude_model_does_not_preflight_missing_binary(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        assert cli.main(tmp_repo.argv("--model", "claude-sonnet-4-5", "list")) == 0
        assert get_active_backend().name == "claude"

    def test_model_override_of_backend_env_does_not_preflight_default_claude(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "codex")
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        assert cli.main(tmp_repo.argv("--model", "claude-sonnet-4-5", "list")) == 0
        assert get_active_backend().name == "claude"

    def test_explicit_default_backend_preflights_missing_binary(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        assert (
            cli.main(tmp_repo.argv("--backend", "claude", "list"))
            == EXEC_NOT_FOUND_EXIT
        )

    @pytest.mark.parametrize(
        ("model", "backend"),
        (("gpt-5.6-terra", "codex"), ("gemini-3-pro", "gemini")),
    )
    def test_nondefault_model_family_preflights_missing_binary(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch, model: str, backend: str,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        monkeypatch.setattr(shutil, "which", lambda _binary: None)
        assert cli.main(tmp_repo.argv("--model", model, "list")) == EXEC_NOT_FOUND_EXIT
        message = capsys.readouterr().err
        assert backend in message
        assert "--model" in message

    @pytest.mark.parametrize(
        ("env_backend", "argv", "expected_backend", "expected_exit"),
        (
            (None, (), "claude", 0),
            ("", (), "claude", 0),
            (None, ("--model", "claude-sonnet-4-5"), "claude", 0),
            ("codex", ("--model", "claude-sonnet-4-5"), "claude", 0),
            ("claude", (), "claude", EXEC_NOT_FOUND_EXIT),
            (
                "claude",
                ("--model", "claude-sonnet-4-5"),
                "claude",
                EXEC_NOT_FOUND_EXIT,
            ),
            ("codex", (), "codex", EXEC_NOT_FOUND_EXIT),
            (None, ("--model", "gpt-5.6-terra"), "codex", EXEC_NOT_FOUND_EXIT),
            (
                "codex",
                ("--backend", "claude", "--model", "gpt-5.6-terra"),
                "claude",
                EXEC_NOT_FOUND_EXIT,
            ),
        ),
    )
    def test_preflight_tracks_selection_source(
        self,
        tmp_repo,
        monkeypatch: pytest.MonkeyPatch,
        env_backend: str | None,
        argv: tuple[str, ...],
        expected_backend: str,
        expected_exit: int,
    ) -> None:
        if env_backend is None:
            monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        else:
            monkeypatch.setenv("PLAN_TOOL_BACKEND", env_backend)
        monkeypatch.setattr(shutil, "which", lambda _binary: None)

        assert cli.main(tmp_repo.argv(*argv, "list")) == expected_exit
        assert get_active_backend().name == expected_backend


def _write_backends_json(repo, block: dict) -> Path:
    """Write ``.plan-tool/backends.json`` with a ``{"backends": {...}}`` block."""
    cfg_dir = repo.root / ".plan-tool"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    path = cfg_dir / "backends.json"
    path.write_text(json.dumps({"backends": block}), encoding="utf-8")
    return path


class TestModelSelection:
    """The global ``--model`` flag, the precedence chain, and the effective
    backend ``main`` activates at selection.

    Selection is driven through ``main(argv)`` against a temp repo whose
    ``.plan-tool/backends.json`` is written on disk (``--repo-root`` is
    pinned by ``tmp_repo.argv``), per the file's no-patch-cli-global
    convention. ``PLAN_TOOL_BACKEND`` is cleared so the precedence
    assertions read the claude default.
    """

    def test_model_flag_parses(self) -> None:
        ns = cli.build_parser().parse_args(["--model", "opus", "list"])
        assert ns.model == "opus"

    def test_model_flag_defaults_none(self) -> None:
        assert cli.build_parser().parse_args(["list"]).model is None

    def test_model_flag_applies_to_active_backend(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        assert cli.main(tmp_repo.argv("--model", "opus", "list")) == 0
        argv = get_active_backend().streaming_argv("P")
        assert "--model" in argv and "opus" in argv
        assert argv[-3:] == ["--model", "opus", "P"]

    def test_model_precedence_flag_beats_config(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _write_backends_json(tmp_repo, {"claude": {"model": "sonnet"}})
        assert cli.main(tmp_repo.argv("--model", "opus", "list")) == 0
        argv = get_active_backend().streaming_argv("P")
        assert "opus" in argv and "sonnet" not in argv

    def test_model_precedence_config_beats_default(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _write_backends_json(tmp_repo, {"claude": {"model": "sonnet"}})
        assert cli.main(tmp_repo.argv("list")) == 0
        argv = get_active_backend().streaming_argv("P")
        assert argv[-3:] == ["--model", "sonnet", "P"]

    def test_extra_streaming_argv_from_config_applied(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _write_backends_json(
            tmp_repo, {"claude": {"extra_streaming_argv": ["--foo"]}}
        )
        assert cli.main(tmp_repo.argv("list")) == 0
        argv = get_active_backend().streaming_argv("P")
        assert "--foo" in argv
        assert argv.index("--foo") < argv.index("P")

    def test_no_model_no_config_byte_identical(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        assert cli.main(tmp_repo.argv("list")) == 0
        # Value-equal (argv fields are ``compare=False``); argv byte-matches
        # the literal. Not ``is``: import-time discovery seeds a manifest-built
        # claude object, and the no-op short-circuit returns that unchanged.
        assert get_active_backend() == CLAUDE_BACKEND
        assert (
            get_active_backend().streaming_argv("P")
            == CLAUDE_BACKEND.streaming_argv("P")
        )

    def test_malformed_backends_json_returns_2(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        cfg_dir = tmp_repo.root / ".plan-tool"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        (cfg_dir / "backends.json").write_text("{not json", encoding="utf-8")
        assert cli.main(tmp_repo.argv("list")) == 2
        assert "backends.json" in capsys.readouterr().err

    def test_model_against_no_model_flag_returns_2(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Register a throwaway backend with no ``model_flag`` and select it
        # via the env (which bypasses ``--backend``'s ``choices`` gate), then
        # request a model: ``main`` must catch the ValueError and return 2.
        from plan_tool import backend as backend_mod

        dummy = importlib.import_module("re").compile(r"(?!x)x")
        nomodel = backend_mod.CliBackend(
            name="nomodel",
            binary="nomodelbin",
            batch_argv=lambda prompt: ["nomodelbin", prompt],
            streaming_argv=lambda prompt: ["nomodelbin", prompt],
            parse_stream_line=lambda line, *, bytes_in: None,
            rate_limit_pattern=dummy,
            provider_limit_pattern=dummy,
            context_overflow_pattern=dummy,
            transient_pattern=dummy,
            model_flag=None,
        )
        saved = dict(backend_mod._REGISTRY)
        backend_mod.register_backend(nomodel)
        monkeypatch.setenv("PLAN_TOOL_BACKEND", "nomodel")
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/nomodelbin")
        try:
            assert cli.main(tmp_repo.argv("--model", "x", "list")) == 2
        finally:
            backend_mod._REGISTRY.clear()
            backend_mod._REGISTRY.update(saved)
        assert "nomodel" in capsys.readouterr().err

    def test_model_family_override_is_applied_without_unknown_warning(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _write_backends_json(
            tmp_repo, {"gemini": {"extra_streaming_argv": ["--project-flag"]}}
        )
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/gemini")

        assert cli.main(tmp_repo.argv("--model", "gemini-3-pro", "list")) == 0
        assert "--project-flag" in get_active_backend().streaming_argv("P")
        err = capsys.readouterr().err
        assert "unknown backend 'gemini'" not in err

    def test_unknown_override_key_warns(
        self, tmp_repo, capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        _write_backends_json(tmp_repo, {"typo": {"model": "ignored"}})

        assert cli.main(tmp_repo.argv("list")) == 0
        err = capsys.readouterr().err
        assert "unknown backend 'typo'" in err
        assert "known:" in err

    @pytest.mark.parametrize("selector", ("flag", "environment"))
    def test_case_mismatched_registered_backend_uses_real_descriptor(
        self, tmp_repo, monkeypatch: pytest.MonkeyPatch, selector: str
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_BACKEND", raising=False)
        argv: tuple[str, ...] = ()
        if selector == "flag":
            argv = ("--backend", "Claude")
        else:
            monkeypatch.setenv("PLAN_TOOL_BACKEND", "Claude")
        monkeypatch.setattr(shutil, "which", lambda _binary: "/usr/bin/claude")

        assert cli.main(tmp_repo.argv(*argv, "list")) == 0
        assert get_active_backend().streaming_argv("P") == CLAUDE_BACKEND.streaming_argv(
            "P"
        )
