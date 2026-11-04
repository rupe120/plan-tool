"""plan-tool CLI entry point: main(), COMMAND_MODULES dispatch assembly, and top-level error UX.

The intent-grouped subcommand catalog that feeds ``--help`` lives on the
package itself (:mod:`plan_tool.cli`'s module docstring); ``build_parser``
and ``main`` thread it into the base parser's ``description`` at call time.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Optional

from plan_tool import model_specs
from plan_tool.backend import (
    provisional_backend_warning,
    registered_names,
    resolve_backend,
    select_active_backend,
    synthesize_backend,
    unknown_backend_override_warning,
)
from plan_tool.backend_config import (
    BackendConfigError,
)
from plan_tool.claude_errors import (
    OnRateLimitAction,
    OnRateLimitPolicy,
    set_default_on_rate_limit_policy,
)
from plan_tool.crash import save_crash_traceback
from plan_tool.convergence import (
    ConvergenceState,
    DEFAULT_ITERATION_BUDGET_SECONDS,
    DEFAULT_MAX_ITERATIONS,
    DEFAULT_MAX_STALL_ROUNDS,
    IterativeBudget,
    finding_set_delta,
    is_blocking,
    record_iteration,
    should_continue,
    touch,
)
from plan_tool.create import (
    DEFAULT_OUTPUT_DIR,
    CreateError,
    SplitProposal,
    SplitProposalEntry,
    archive_existing_source,
    create_plan,
    extract_file_path_candidates,
    read_existing_description,
    resolve_create_slug,
    resolve_output_dir,
    shell_claude_invoker,
)
from plan_tool.detail import DetailError, generate_detail
from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.human_io import HumanInputError
from plan_tool.launcher import (
    LauncherError,
    MUTATING_MODES,
    format_findings_verdict,
    resolve_step,
    run_all_done_steps,
    run_step,
    summarize_findings,
    verify_plan,
)
from plan_tool.locator import (
    ManifestError,
    PlanToolContext,
    build_plan_tool_context,
    find_repo_root_from_cwd,
    find_umbrella_root,
    record_known_root,
    resolve_plan_for_context,
    resolve_repo_root,
)
from plan_tool.parser import (
    ParseError,
    UnsupportedPlanFormatVersionError,
    ValidationError,
    parse_plan,
    write_plan,
)
from plan_tool.canonical import read_canonical_provenance
from plan_tool.reprocess import (
    ReprocessError,
    find_archive_for_slug,
    reprocess_plan,
)
from plan_tool.scope_out import NarrowError
from plan_tool.review import (
    AUDIT_DEFAULT_DRY_ROUNDS,
    AUDIT_DEFAULT_MAX_PASSES,
    ReviewError,
    review_plan_full,
)
from plan_tool.review_persistence import (
    ReviewLoadError,
    load_review,
    resolve_saved_review,
    save_review,
)
from plan_tool.review_walk import WalkState, walk_recommendations
from plan_tool.run_log import (
    RunLogWriter,
    in_flight_path,
)
from plan_tool.repo_lock import RepoMutationLockError, repo_mutation_lock
from plan_tool.schema import Plan, StepStatus
from plan_tool.shell import EXEC_NOT_FOUND_EXIT
from plan_tool.style import (
    BOLD,
    BOLD_GREEN,
    BOLD_RED,
    CYAN,
    DIM,
    color_enabled,
    colorize_diff,
    detail,
    error,
    info,
    note,
    paint,
    render_markdown_for_console,
    success,
    warn,
)
# Keep helper re-exports stable for package consumers and monkeypatch seams.
from plan_tool.cli.console import (
    _atomic_write,
    _common_dir_prefix,
    _fmt_ms,
    _fmt_ms_or_n,
    _format_relative_age,
    _is_within,
    _print_detail_summary,
    _print_next_steps,
    _repo_rel,
    _short_path,
)
from plan_tool.cli.context import (
    _build_run_budget,
    _load_context,
    _resolve_cmd_repo_root,
    _resolve_iterative_budget,
)
from plan_tool.cli.parser import Handler, assemble

# Per-intent command modules carved out of this one. They own their
# handlers + ``register(subparsers)`` and contribute to ``COMMAND_MODULES``
# below. Imported as modules (for the registry) and their moved names are
# re-imported back into this namespace so the bare-name call sites here, the
# ``plan_tool.cli`` package re-export, and the legacy patch sites that
# ``setattr`` an ``app`` global all keep resolving. These modules import only
# the cycle-free leaves (console / context / parser) and domain packages —
# never ``app`` — so the edge stays one-directional and cycle-free.
# NOTE: the ``from plan_tool.cli import X`` form (not ``import
# plan_tool.cli.X`` + dotted attribute access) is load-bearing: this
# module executes while ``plan_tool.cli``'s __init__ is still
# initializing, and only the from-import falls back to sys.modules for
# a partially-initialized package — a dotted ``plan_tool.cli.inspect``
# reference at module-eval time raises AttributeError.
from plan_tool.cli import inspect as _inspect_commands
from plan_tool.cli import manifest as _manifest_commands
from plan_tool.cli.inspect import (
    _print_status,
    cmd_list,
    cmd_root,
    cmd_status,
    cmd_validate,
)
from plan_tool.cli.manifest import (
    _archive_duplicate_plans,
    _print_partial_classification,
    _print_sweep_report,
    _prompt_remove_missing,
    _resolve_deregister_target,
    _resolve_register_target,
    cmd_attach_branch,
    cmd_deregister,
    cmd_detach_branch,
    cmd_register,
    cmd_sweep,
    cmd_withdraw,
)
from plan_tool.cli import checkpoints as _checkpoint_commands
from plan_tool.cli import runs as _runs_commands
from plan_tool.cli import lessons_cmd as _lessons_commands
from plan_tool.cli.checkpoints import (
    _safe_under_root,
    _validate_checkpoint_arg,
    cmd_checkpoint,
)
from plan_tool.cli.runs import (
    _CallSample,
    _aggregate_run_for_diff,
    _cmd_runs_profile,
    _group_samples,
    _is_run_evictable,
    _iter_call_samples,
    _iter_events,
    _load_events_with_skips,
    _parse_duration_arg,
    _parse_runs_target,
    _summarize_group,
    _summarize_run_log,
    cmd_runs,
)
from plan_tool.cli.lessons_cmd import (
    _print_consolidate_summary,
    _recurrence_annotation,
    _render_lessons_unified_diff,
    cmd_lessons,
    cmd_lessons_consolidate,
)
from plan_tool.cli import roadmap_cmd as _roadmap_commands
from plan_tool.cli.roadmap_cmd import cmd_roadmap
from plan_tool.cli import authoring as _authoring_commands
from plan_tool.cli.authoring import (
    _cmd_create_reprocess,
    _confirm_repo_root,
    _emit_split_proposal,
    _read_seed_body,
    _render_split_proposal_markdown,
    _stamp_grounding,
    cmd_create,
    cmd_detail,
    cmd_merge,
    cmd_split,
)
from plan_tool.cli import jira_cmd as _jira_commands
from plan_tool.cli.jira_cmd import (
    _assign_epic_for_plan,
    _assign_plan_tag_for_plan,
    _dedupe_plan_tag,
    _print_jira_config,
    _prompt_new_epic_inline,
    _resolve_epic_for_plan,
    _resolve_plan_tag_for_plan,
    _run_jira_config_wizard,
    _wizard_add_epic,
    _wizard_assign_plan,
    _wizard_edit_epic,
    _wizard_remove_epic,
    _wizard_resolve_plan_rel,
    _wizard_unassign_plan,
    cmd_jira,
    cmd_jira_config,
)
from plan_tool.cli import run_cmd as _run_commands
from plan_tool.cli.run_cmd import _cmd_run_sweep, cmd_reconcile_code, cmd_run
from plan_tool.cli import review_cmd as _review_commands
from plan_tool.cli.review_cmd import (
    _prompt_reuse_saved_review,
    _review_walk_environment_allows,
    cmd_review,
    cmd_review_all,
    cmd_review_walk,
    cmd_verify,
    cmd_verify_all,
)
from plan_tool.cli import completeness_cmd as _completeness_commands
from plan_tool.cli.completeness_cmd import (
    _completeness_has_blocking_findings,
    _finding_progress_label,
    _fmt_finding_counts,
    cmd_completeness,
)
from plan_tool.cli import data_contract_cmd as _data_contract_commands
from plan_tool.cli.data_contract_cmd import cmd_data_contract_apply
from plan_tool.cli import bench_cmd as _bench_commands
from plan_tool.cli.bench_cmd import cmd_bench
from plan_tool.cli import gates_cmd as _gates_commands
from plan_tool.cli.gates_cmd import cmd_suggest_gates
from plan_tool.cli import convergence_cmd as _convergence_commands
from plan_tool.cli.convergence_cmd import cmd_convergence
from plan_tool.cli import gate_status_cmd as _gate_status_commands
from plan_tool.cli.gate_status_cmd import cmd_gate_status
from plan_tool.cli import telemetry_cmd as _telemetry_commands
from plan_tool.cli.telemetry_cmd import cmd_telemetry
from plan_tool.cli import init_cmd as _init_commands
from plan_tool.cli.init_cmd import cmd_init
from plan_tool.cli import decision_cmd as _decision_commands
from plan_tool.cli.decision_cmd import cmd_decide
from plan_tool.cli import scope_out_cmd as _scope_out_commands
from plan_tool.cli.scope_out_cmd import cmd_scope_out
from plan_tool.cli import scope_review_cmd as _scope_review_commands
from plan_tool.cli.scope_review_cmd import cmd_scope_review
from plan_tool.cli import split_criteria_cmd as _split_criteria_commands
from plan_tool.cli.split_criteria_cmd import cmd_split_criteria
from plan_tool.cli import annotate_cmd as _annotate_commands
from plan_tool.cli.annotate_cmd import cmd_annotate
from plan_tool.cli import skill_cmd as _skill_commands
from plan_tool.cli.skill_cmd import cmd_install_skill
from plan_tool.cli import worktree_cmd as _worktree_commands
from plan_tool.cli.worktree_cmd import cmd_worktree


# The reconcile engine and the shared review-action builder live in two
# non-command leaf submodules (no ``register`` / ``COMMAND_MODULES`` entry).
# Re-import every moved name back into this namespace so the
# ``plan_tool.cli`` package re-export and ``authoring.cmd_detail``'s
# ``app._cmd_detail_reconcile`` / ``app._cmd_detail_reconcile_all`` reaches
# keep resolving zero-edit. The edge is one-directional -- ``app`` ->
# {``reconcile``, ``review_actions``}; neither leaf imports ``app``.
from plan_tool.cli.review_actions import _build_review_action_fn
from plan_tool.cli.reconcile import (
    ReusableReconcile,
    _ask_reuse_saved_detail_reconcile,
    _ask_reuse_saved_run_reconcile,
    _cmd_detail_reconcile,
    _cmd_detail_reconcile_all,
    _cmd_run_reconcile,
    _emit_drift_halt_warning,
    _emit_scope_guard_plan,
    _find_saved_detail_reconcile_for_step,
    _find_saved_run_reconcile_for_step,
    _iterate_reconcile_loop,
    _print_attributed_files,
    _prompt_reuse_saved_detail_reconcile,
    _prompt_reuse_saved_run_reconcile,
    _run_auto_reconcile_on_drift,
    _run_detail_reconcile_path,
    resolve_reusable_reconcile,
    _save_and_walk_reconcile,
    _save_and_walk_run_reconcile,
    _walk_saved_detail_reconcile,
    _walk_saved_run_reconcile,
    _walk_with_reconcile_phase,
    _note_reuse_code_drift,
)


_REVIEW_SEP = "=" * 62

AVAILABLE_MODES = (
    "run",
    "check",
    "optimize",
    "document",
    "test",
    "security",
    "lint",
)


# NOTE: a ``_RunLogger`` class formerly lived here as a private
# precursor to ``RunLogWriter``. Step 5 promoted the canonical class
# to ``plan_tool.run_log.RunLogWriter`` and step-3's review (the
# parallel-runs correctness pass) found the two coexisting with
# subtly different signatures (keyword-only vs positional
# ``claude_call_start``, plus install/uninstall vs context-manager
# sink shapes). The promotion was finished here: ``RunLogWriter``
# now exposes the same ``install_call_end_sink`` / ``uninstall_call_end_sink``
# / ``parse_failure`` shims ``_RunLogger`` had, so every caller in
# the tree (``cmd_create``, ``cmd_detail``, ``cmd_run``) uses one
# class. Tests that previously imported ``_RunLogger`` from this
# module should import ``RunLogWriter`` instead.


def build_parser() -> argparse.ArgumentParser:
    """Build the full ``plan-tool`` parser from the command-module registry.

    Construction lives in :mod:`plan_tool.cli.parser`; this stays a
    module global so ``from plan_tool.cli import build_parser`` keeps
    resolving for callers and tests. The base-parser ``description`` is
    the package docstring (the intent-grouped subcommand catalog), read
    here at call time — a function-body access, never a module-top
    import, so the ``__init__ → app`` re-export edge stays cycle-free.
    """
    from plan_tool import cli

    return assemble(cli.__doc__, COMMAND_MODULES)[0]


# The command-module registry. ``assemble`` iterates this in order,
# calling each module's ``register(subparsers)`` and merging the returned
# dispatch maps. The displayed ``plan-tool --help`` order is fixed by
# ``CANONICAL_COMMAND_ORDER`` in ``parser.py`` (applied after registration),
# so this tuple's order is no longer help-order-bearing. ``inspect`` (list /
# status / validate) and ``manifest`` (register / deregister / sweep) come
# first, then the state-management verbs (checkpoint / runs / lessons), the
# authoring verbs (create / detail), the ``jira`` integration verb, the
# ``run`` execution verb, the ``review_cmd`` audit verbs (reconcile-plan /
# reconcile-plan-walk / verify-all), and the ``completeness_cmd`` audit verbs
# (completeness-audit). ``app`` itself is absent: it
# registers no subparsers, and the base-parser description is threaded
# independently from the package docstring (see ``build_parser`` / ``main``).
COMMAND_MODULES = (
    _inspect_commands,
    _manifest_commands,
    _checkpoint_commands,
    _runs_commands,
    _lessons_commands,
    _roadmap_commands,
    _authoring_commands,
    _jira_commands,
    _run_commands,
    _review_commands,
    _completeness_commands,
    _data_contract_commands,
    _gate_status_commands,
    _convergence_commands,
    _telemetry_commands,
    _init_commands,
    _decision_commands,
    _gates_commands,
    _bench_commands,
    _annotate_commands,
    _scope_out_commands,
    _scope_review_commands,
    _split_criteria_commands,
    _worktree_commands,
    _skill_commands,
)


_LOCKED_MUTATING_COMMANDS = frozenset(
    {
        "register",
        "deregister",
        "sweep",
        "withdraw",
        "init",
        "attach-branch",
        "detach-branch",
        "roadmap",
        "create",
        "detail",
        "reconcile-plan",
        "reconcile",
        "review",
        "reconcile-plan-walk",
        "reconcile-walk",
        "review-walk",
        "run",
        "reconcile-code",
        "completeness-audit",
        "data-contract-apply",
        "jira",
        "scope-out",
        "scope-review",
        "lessons",
        "annotate",
    }
)


def _requires_repo_mutation_lock(args: argparse.Namespace) -> bool:
    command = getattr(args, "command", None)
    if command not in _LOCKED_MUTATING_COMMANDS:
        return False
    if command == "sweep" and (
        getattr(args, "dry_run", False) or getattr(args, "report_only", False)
    ):
        return False
    if command == "jira" and getattr(args, "name", None) == "config" and getattr(
        args, "show", False
    ):
        return False
    return True


def _synthesize_unregistered_backend(name: str, *, model_supplied: bool = False):
    """Build a provisional descriptor from a model or catalog fallback."""
    try:
        return resolve_backend(name.strip().lower())
    except ValueError:
        pass

    if model_supplied:
        warn(provisional_backend_warning(
            name,
            "The supplied --model will be passed through.",
        ))
        return synthesize_backend(name)

    provider = model_specs.provider_for_backend(name)
    catalog = model_specs.fetch_catalog(
        cache_path=Path.home() / ".cache" / "plan-tool" / "models.dev.json"
    )
    spec = model_specs.pick_default_model(catalog, provider)
    default_model = spec.id if spec else None

    if default_model:
        detail = (
            f"Default model sourced from models.dev: {default_model} "
            f"(provider {provider!r}); override with --model."
        )
    elif catalog.error:
        detail = (
            f"No default model sourced (models.dev unavailable: "
            f"{catalog.error}); pass --model explicitly."
        )
    else:
        detail = (
            f"No default model sourced (models.dev knows no provider "
            f"{provider!r}); pass --model explicitly."
        )
    warn(provisional_backend_warning(name, detail))
    return synthesize_backend(name, default_model=default_model)


_ON_RATE_LIMIT_ENV = "PLAN_TOOL_ON_RATE_LIMIT"
_FALLBACK_BACKEND_ENV = "PLAN_TOOL_FALLBACK_BACKEND"


def _resolve_on_rate_limit_policy(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> OnRateLimitPolicy:
    """Resolve CLI/env rate-limit policy and report usage errors via parser."""
    if args.no_wait_on_rate_limit and args.on_rate_limit is not None:
        parser.error("--no-wait-on-rate-limit cannot be combined with --on-rate-limit")

    if args.on_rate_limit is not None:
        action_value = args.on_rate_limit
    elif args.no_wait_on_rate_limit:
        action_value = OnRateLimitAction.STOP.value
    else:
        env_value = os.environ.get(_ON_RATE_LIMIT_ENV)
        action_value = env_value.strip().lower() if env_value else None

    if action_value is None:
        action = OnRateLimitAction.WAIT
    else:
        try:
            action = OnRateLimitAction(action_value)
        except ValueError:
            choices = ", ".join(action.value for action in OnRateLimitAction)
            parser.error(
                f"{_ON_RATE_LIMIT_ENV} must be one of: {choices}; "
                f"got {action_value!r}"
            )

    fallback_backend = args.fallback_backend
    if fallback_backend is None:
        fallback_backend = os.environ.get(_FALLBACK_BACKEND_ENV)
    if fallback_backend is not None:
        fallback_backend = fallback_backend.strip()
        if not fallback_backend:
            fallback_backend = None

    if action is OnRateLimitAction.SWITCH and fallback_backend is None:
        parser.error(
            "--on-rate-limit switch requires --fallback-backend or "
            f"{_FALLBACK_BACKEND_ENV}"
        )

    return OnRateLimitPolicy(action=action, fallback_backend=fallback_backend)


def main(argv: Optional[list[str]] = None) -> int:
    from plan_tool import cli

    parser, dispatch = assemble(cli.__doc__, COMMAND_MODULES)
    args = parser.parse_args(argv)
    rate_limit_policy = _resolve_on_rate_limit_policy(args, parser)

    # A flag wins; a recognized model family otherwise precedes env/default.
    env_backend = os.environ.get("PLAN_TOOL_BACKEND")
    inferred_backend = model_specs.backend_for_model(args.model or "")
    if args.backend is not None:
        name, selection_source = args.backend, "flag"
    elif inferred_backend is not None:
        name, selection_source = inferred_backend, "model"
    elif env_backend:
        name, selection_source = env_backend, "environment"
    else:
        name, selection_source = "claude", "default"
    preflight_required = (
        args.backend is not None or name != "claude" or env_backend == "claude"
    )
    model_inference_changed_selection = (
        selection_source == "model" and name != (env_backend or "claude")
    )
    repo_root = _resolve_cmd_repo_root(args)
    try:
        selection = select_active_backend(
            name,
            repo_root=repo_root,
            model=args.model,
            fallback_factory=lambda backend_name: _synthesize_unregistered_backend(
                backend_name,
                model_supplied=bool(args.model),
            ),
            known_override_names=model_specs.model_family_backend_names(),
        )
    except BackendConfigError as exc:
        error(str(exc))
        return 2
    except ValueError as exc:
        error(str(exc))
        return 2
    selected = selection.selected

    # Warn (non-fatally) on a config key outside registered and inferred names.
    names = set(registered_names()) | model_specs.model_family_backend_names()
    for key in selection.unknown_override_names:
        warn(unknown_backend_override_warning(key, names))

    # Only the silent default and a model-only Claude selection stay lazy.
    if preflight_required and shutil.which(selected.binary) is None:
        error(
            f"{selected.name} backend selected but its '{selected.binary}' "
            "executable was not found on PATH"
        )
        next_steps = [
            (
                f"install {selected.name}",
                f"make the '{selected.binary}' command available",
            ),
            (
                f"add {selected.binary} to PATH",
                "if it is installed in a non-standard location",
            ),
            (
                "plan-tool --backend claude …",
                "or unset PLAN_TOOL_BACKEND to use the default backend",
            ),
        ]
        if model_inference_changed_selection:
            next_steps.append(
                (
                    "remove or change --model",
                    "to select a backend whose executable is available",
                )
            )
        _print_next_steps("Fix one of:", next_steps)
        return EXEC_NOT_FOUND_EXIT

    # Top-level rate-limit recovery policy. Apply once before any
    # subcommand dispatch so every downstream backend call sees the same
    # invocation-level default.
    set_default_on_rate_limit_policy(rate_limit_policy)

    # Console verbosity: propagated to the launcher's stream-json pump
    # so the raw NDJSON stays off the terminal (it goes to the stream log).
    # See ``launcher.set_console_verbosity`` for the level semantics.
    from plan_tool.launcher import (
        _CONSOLE_VERBOSITY_DEBUG,
        _CONSOLE_VERBOSITY_QUIET,
        _CONSOLE_VERBOSITY_VERBOSE,
        set_console_verbosity,
    )
    if getattr(args, "debug", False):
        set_console_verbosity(_CONSOLE_VERBOSITY_DEBUG)
    elif getattr(args, "verbose", False):
        set_console_verbosity(_CONSOLE_VERBOSITY_VERBOSE)
    else:
        set_console_verbosity(_CONSOLE_VERBOSITY_QUIET)

    try:
        with repo_mutation_lock(
            repo_root,
            command=args.command,
            enabled=_requires_repo_mutation_lock(args),
        ):
            return dispatch[args.command](args)
    except RepoMutationLockError as exc:
        error(str(exc))
        return 2
    except FileNotFoundError as exc:
        error(str(exc))
        # Most FileNotFoundError surfaces from plan-name resolution (the
        # slug doesn't match any manifest entry / on-disk plan). Point
        # the operator at ``list`` so they can see what *is* registered.
        _print_next_steps(
            "Try:",
            [
                ("plan-tool list", "show all registered plans"),
                (
                    "plan-tool register <path>",
                    "register an existing plan file",
                ),
            ],
        )
        return 2
    except ManifestError as exc:
        error(str(exc))
        _print_next_steps(
            "Try:",
            [
                (
                    "plan-tool list",
                    "list registered plans (validates the manifest)",
                ),
                (
                    "plan-tool sweep --dry-run",
                    "preview manifest cleanup of done / missing plans",
                ),
            ],
        )
        return 1
    except UnsupportedPlanFormatVersionError as exc:
        error(str(exc))
        # An unknown format has no safe in-build upgrade path.
        _print_next_steps(
            "Try:",
            [
                (
                    "use a plan-tool build that supports this format_version",
                    "this build cannot safely read or upgrade the declared version",
                ),
            ],
        )
        return 1
    except (ParseError, ValidationError) as exc:
        error(str(exc))
        # Parse / schema failures point at the plan frontmatter or body
        # shape. ``validate`` is the deterministic diagnostic; the user
        # may also need to fix the offending file through a direct edit.
        plan_arg = getattr(args, "name", None) or getattr(args, "slug", None)
        suggestions: list[tuple[str, str]] = []
        if plan_arg:
            suggestions.append((
                f"plan-tool validate {plan_arg}",
                "show the exact schema error and offending line",
            ))
        suggestions.append((
            "plan-tool list",
            "confirm the plan name is registered",
        ))
        _print_next_steps("Try:", suggestions)
        return 1
    except NarrowError as exc:
        error(str(exc))
        return 2
    except HumanInputError as exc:
        error(str(exc))
        _print_next_steps(
            "Try:",
            [
                (
                    "unset PLAN_TOOL_HUMAN_IO",
                    "use the existing terminal-input path",
                ),
                (
                    "set PLAN_TOOL_HUMAN_IO_DIR to an existing readable, writable directory",
                    "configure the filesystem human-input path",
                ),
                (
                    "resolve the existing request or resolution record",
                    "preserve no-clobber publication before retrying",
                ),
            ],
        )
        return 2
    except DetailFormatError as exc:
        error(str(exc))
        # An unsupported or malformed declared version has no safe
        # read-time repair; the plan's stated recovery is forced
        # regeneration of the refused detail, never a partial read.
        plan_arg = getattr(args, "name", None) or getattr(args, "slug", None)
        _print_next_steps(
            "Try:",
            [
                (
                    f"plan-tool detail {plan_arg or '<plan>'} --step N --force "
                    "--recover-refused --commit --no-completeness",
                    "replace the refused detail without the automatic "
                    "completeness re-audit reading a still-refused sibling",
                ),
            ],
        )
        return 1
    except Exception as exc:
        # Catch-all for UNEXPECTED exceptions (the specific handlers above
        # own the known-error UX). ``KeyboardInterrupt`` / ``SystemExit``
        # are ``BaseException`` and intentionally pass straight through.
        #
        # Show a clean one-liner instead of a raw stack trace, but persist
        # the full traceback to a file so it survives for debugging. The
        # convergence loops release their iteration lock on the way out
        # (context-manager cleanup), so a re-run is never blocked by a
        # stale lock.
        #
        # Land the crash file in the repo the command actually targeted:
        # honor an explicit ``--repo-root`` first (the crash belongs with
        # that repo's ``.plan-tool/``, not cwd's), then fall back to
        # cwd-based discovery, then cwd itself.
        repo_root: Path
        repo_root_arg = getattr(args, "repo_root", None)
        if repo_root_arg is not None:
            repo_root = Path(repo_root_arg).resolve()
        else:
            try:
                repo_root = find_repo_root_from_cwd()
            except Exception:
                repo_root = Path.cwd()
        label = (
            getattr(args, "slug", None)
            or getattr(args, "name", None)
            or getattr(args, "command", None)
            or "plan-tool"
        )
        crash_path = save_crash_traceback(
            repo_root, str(label), tb_text=traceback.format_exc()
        )
        print(
            f"plan-tool: unexpected error: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        if crash_path is not None:
            print(
                f"  full traceback saved to {_short_path(crash_path, repo_root)}",
                file=sys.stderr,
            )
        else:
            # Couldn't persist the traceback (unwritable .plan-tool/); fall
            # back to the raw trace on stderr so it isn't lost entirely.
            print(
                "  (could not write a crash file; raw traceback follows)",
                file=sys.stderr,
            )
            traceback.print_exc()
        print(
            "  re-run the command to retry (create/detail resume from "
            "cached checkpoints). To continue a partially-iterated plan "
            "without rebuilding it, run `plan-tool completeness-audit <slug>`. "
            "Please report this with the saved traceback.",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
