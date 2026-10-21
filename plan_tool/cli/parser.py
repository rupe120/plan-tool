"""ArgumentParser construction + the per-module subparser registration seam.

This is a **leaf** module: it imports only stdlib and is imported *by*
``plan_tool.cli.app`` (and, in later steps, by every per-intent command
module). It never imports a ``plan_tool.cli`` submodule itself — the
command modules are handed to :func:`assemble` as data via the caller's
``COMMAND_MODULES`` registry, so the dependency edge stays one-directional
(``app -> parser``) and cycle-free.

``make_base_parser`` owns the parser wiring shared by every invocation
(prog, the intent-grouped description, the global flags, the
verbosity group). ``assemble`` adds the single ``add_subparsers`` action
and drives the registry: each command module exposes
``register(subparsers) -> dict[str, Handler]`` adding its own subparsers
and returning the command→handler map, which ``assemble`` merges into one
dispatch dict.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import tomllib
from pathlib import Path
from typing import Callable

# The shape every ``cmd_*`` dispatch handler satisfies: it takes the
# parsed ``argparse.Namespace`` and returns a process exit code.
Handler = Callable[[argparse.Namespace], int]

# The monolith's historical subcommand registration order. ``plan-tool
# --help`` renders subcommands in registration order, and the package
# split's contract is byte-identical help at every intermediate carve —
# but extraction groups commands by *intent module* (e.g. ``authoring``
# owns create + detail) while the historical order interleaves intents
# (``detail`` sits between ``jira`` and ``run``). ``assemble`` therefore
# reorders the registered subcommands to this canonical sequence after
# the registry pass, making help order independent of module grouping.
# A command absent from this tuple sorts after all canonical ones (new
# commands appended post-split extend the tuple instead).
CANONICAL_COMMAND_ORDER = (
    "list",
    "status",
    "init",
    "validate",
    "register",
    "deregister",
    "sweep",
    "withdraw",
    "checkpoint",
    "runs",
    "lessons",
    # ``roadmap`` sits one rung above ``create`` in the workflow, so it leads
    # the authoring group rather than being appended at the tuple's end.
    "roadmap",
    "create",
    "reconcile-plan",
    "reconcile-code",
    "reconcile-plan-walk",
    "verify-all",
    "completeness-audit",
    "completeness-apply",
    "data-contract-apply",
    "gate-status",
    "convergence",
    "telemetry",
    "decide",
    "jira",
    "detail",
    "run",
    "direct-jira",
    "direct-run",
    "suggest-gates",
    "bench",
    "annotate",
    "attach-branch",
    "detach-branch",
    "scope-out",
    "scope-review",
    "split-criteria",
    "worktree",
)


def _canonical_index(command: str) -> int:
    try:
        return CANONICAL_COMMAND_ORDER.index(command)
    except ValueError:
        return len(CANONICAL_COMMAND_ORDER)


def _reorder_subcommands(subparsers: argparse._SubParsersAction) -> None:
    """Reorder registered subcommands to :data:`CANONICAL_COMMAND_ORDER`.

    Two argparse-internal structures drive help rendering order: the
    ``choices`` dict (insertion order feeds the ``{a,b,...}`` metavar
    brace list, aliases included) and ``_choices_actions`` (one
    pseudo-action per primary command name, feeding the per-command help
    lines). Both are rebuilt in canonical order so the rendered help is
    byte-identical to the monolith's regardless of which module
    registered which command.
    """
    ordered = sorted(
        subparsers.choices.items(), key=lambda kv: _canonical_index(kv[0])
    )
    subparsers.choices.clear()
    subparsers.choices.update(ordered)
    subparsers._choices_actions.sort(
        key=lambda action: _canonical_index(action.dest)
    )


def package_version(source_root: Path | None = None) -> str:
    """This plan-tool's version, or ``"unknown"`` when it cannot be read.

    An editable install freezes its metadata at install time, so a source
    checkout reads its own ``pyproject.toml`` (only when that file declares
    this package) and an installed wheel reads its metadata. See
    ``docs/RELEASING.md``.
    """
    root = source_root if source_root is not None else Path(__file__).resolve().parents[2]
    try:
        project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project["name"] == "plan-tool":
            return project["version"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        return importlib.metadata.version("plan-tool")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


class _VersionAction(argparse.Action):
    """Print ``plan-tool <version>`` and exit; read the version only when asked."""

    def __init__(self, option_strings, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)

    def __call__(self, parser, namespace, values, option_string=None):
        print(f"plan-tool {package_version()}")
        parser.exit()


def make_base_parser(description: str) -> argparse.ArgumentParser:
    """Build the base parser (global flags + verbosity), no subparsers yet."""
    # RawDescriptionHelpFormatter preserves the intent-grouped category
    # headings in the module docstring so `plan-tool --help` matches the
    # structure documented in SKILL.md's "Subcommands at a glance".
    parser = argparse.ArgumentParser(
        prog="plan-tool",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action=_VersionAction,
        help="print the plan-tool version and exit.",
    )
    parser.add_argument(
        "--plans-dir",
        type=Path,
        default=None,
        help=(
            "scan this directory for *.md plans (overrides PLAN_TOOL_PLANS_DIR). "
            "If omitted and PLAN_TOOL_PLANS_DIR is unset, use structured_plans.json "
            "in the plan_tool package plus repo root from .git."
        ),
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help=(
            "override path to structured_plans.json (default: beside plan_tool "
            "locator). Only used when neither --plans-dir nor PLAN_TOOL_PLANS_DIR is set."
        ),
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        dest="repo_root",
        help=(
            "pin the repo root explicitly (overrides PLAN_TOOL_REPO_ROOT and "
            "the walk-up `.git` heuristic). Use this when plan-tool's own "
            "folder is a nested git repo, when the skill is installed "
            "somewhere other than `.agents/`, or when the checkout has no "
            "`.git` (CI sparse checkouts)."
        ),
    )
    parser.add_argument(
        "--no-wait-on-rate-limit",
        action="store_true",
        dest="no_wait_on_rate_limit",
        help=(
            "legacy alias for --on-rate-limit stop. Cannot be combined with "
            "--on-rate-limit."
        ),
    )
    parser.add_argument(
        "--on-rate-limit",
        choices=("wait", "switch", "stop", "ask"),
        default=None,
        dest="on_rate_limit",
        help=(
            "choose the default response for an ordinary recoverable rate "
            "limit. 'wait' sleeps until reset and retries; 'switch' retries "
            "the current call with --fallback-backend; 'stop' returns "
            "immediately; 'ask' prompts when interactive. A confirmed "
            "terminal plan quota bypasses these actions. Overrides "
            "PLAN_TOOL_ON_RATE_LIMIT. "
            "Precedence: this flag > --no-wait-on-rate-limit > "
            "PLAN_TOOL_ON_RATE_LIMIT > wait."
        ),
    )
    parser.add_argument(
        "--fallback-backend",
        default=None,
        dest="fallback_backend",
        metavar="BACKEND",
        help=(
            "backend to retry the current ordinary rate-limited call with "
            "when --on-rate-limit switch is active. A terminal plan quota "
            "does not use a fallback backend. Overrides "
            "PLAN_TOOL_FALLBACK_BACKEND."
        ),
    )
    parser.add_argument(
        "--backend",
        default=None,
        dest="backend",
        metavar="BACKEND",
        help=(
            "select the CLI backend that runs steps. Registered backends "
            "(claude, codex, cursor) run with their shipped integration; an "
            "unregistered name is synthesized into a provisional backend "
            "(generic argv, models.dev-sourced default model) so a new CLI "
            "is batch-invocable before an integration manifest exists. "
            "Overrides model-family inference and the PLAN_TOOL_BACKEND env "
            "var; default claude. Precedence: this flag > inferred --model "
            "family > PLAN_TOOL_BACKEND > claude."
        ),
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        dest="model",
        help=(
            "model the selected backend runs steps with, passed via its "
            "model_flag (--model for claude and cursor, -m for codex). When "
            "--backend is absent, gpt-* / chatgpt-* / o1 / o3 / o4 / codex-* "
            "select codex, "
            "claude-* selects claude, and gemini-* selects gemini. Other "
            "names stay on the configured backend. Free-form model names "
            "remain backend-specific and open-ended, so this takes no "
            "choices. Precedence: this flag > .plan-tool/backends.json "
            "backends.<name>.model > the backend's default_model > omit."
        ),
    )
    parser.add_argument(
        "--prompt-mode",
        choices=("combined", "split"),
        default=None,
        dest="prompt_mode",
        help=(
            "A/B prompt mode for create/detail authoring. 'combined' (default) "
            "is the legacy single-call prompt; 'split' runs the lifted-out "
            "foundational-logic call. Overrides PLAN_TOOL_PROMPT_MODE. "
            "Precedence: this flag > --experiment-arm prompt-mode=… > "
            "PLAN_TOOL_PROMPT_MODE > combined."
        ),
    )
    parser.add_argument(
        "--experiment-arm",
        action="append",
        default=None,
        metavar="NAME=ARM",
        dest="experiment_arm",
        help=(
            "Select an A/B experiment's arm generically, e.g. "
            "--experiment-arm prompt-mode=split. Repeatable for multiple "
            "experiments. A dedicated flag (--prompt-mode) takes precedence."
        ),
    )
    # Console verbosity. Default is quiet: only the structured progress
    # reporter (step header, in-place heartbeat, done line) is shown.
    # ``-v`` adds per-tool-use one-liners so the operator can see what
    # claude is touching. ``--debug`` prints the path of the live raw
    # backend stream log (always written beside the run log). The flags are
    # mutually exclusive — picking both is a usage error.
    verbosity = parser.add_mutually_exclusive_group()
    verbosity.add_argument(
        "-v", "--verbose",
        action="store_true",
        dest="verbose",
        help=(
            "show one indented line per claude tool_use event (Edit "
            "path, Bash command, etc.) in addition to the default "
            "step-level progress."
        ),
    )
    verbosity.add_argument(
        "--debug",
        action="store_true",
        dest="debug",
        help=(
            "print the path of the raw backend stream log, which is "
            "written live to <run_id>.streams/ beside the run log "
            "(tail -f it). Falls back to stdout only when no log can "
            "be opened."
        ),
    )
    return parser


def make_yes_parent() -> argparse.ArgumentParser:
    """A fresh parent parser carrying the shared ``-y/--yes`` flag.

    A factory, not a shared instance: ``parents=`` copies actions by
    reference, so one instance handed to every module would let a later
    ``set_defaults`` on one subparser mutate the flag for all of them.

    Three command modules deliberately keep their own variant and must not
    call this — ``gates`` (where ``-y`` means "print a report instead of
    prompting", not auto-accept), ``scope-out`` (whose help documents the
    ``--apply`` mutation gate), and ``worktree`` (explicit ``dest``/
    ``default``). See BACKLOG #80.
    """
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        help=(
            "auto-accept Y/N confirmation prompts (proceed with the "
            "offered action without asking). Useful for scripted/"
            "unattended runs."
        ),
    )
    return parent


def assemble(
    description: str, command_modules
) -> tuple[argparse.ArgumentParser, dict[str, Handler]]:
    """Build the full parser and dispatch map from a command-module registry.

    Each module in ``command_modules`` must expose
    ``register(subparsers) -> dict[str, Handler]``: it adds its own
    subparsers to the shared ``add_subparsers`` action and returns the
    command→handler map for the commands it registered. The returned maps
    are merged into one dispatch dict; a command key registered by two
    modules is a registry collision and fails loud rather than silently
    shadowing (there is only ``app`` today, but the contract is what
    steps 11–16 plug into).
    """
    parser = make_base_parser(description)
    subparsers = parser.add_subparsers(dest="command", required=True)
    dispatch: dict[str, Handler] = {}
    for module in command_modules:
        handlers = module.register(subparsers)
        for command, handler in handlers.items():
            assert command not in dispatch, (
                f"command {command!r} registered by more than one command "
                f"module"
            )
            dispatch[command] = handler
    _reorder_subcommands(subparsers)
    return parser, dispatch
