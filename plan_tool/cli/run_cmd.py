"""Execution command module — the ``run`` verb.

Owns the execution primitive (``cmd_run``) and its sweep controller
(``_cmd_run_sweep``). ``run`` is dual-identity by design: ``--mode run``
executes a step and advances plan state (the only path that writes code),
while ``--mode <review>`` runs a per-step read-only audit. The reconcile
plumbing (``--reconcile`` audit alias, saved-reconcile reuse) is delegated
to the reconcile engine, which this module imports as a library.

Import edge is one-directional: ``run_cmd`` imports the cycle-free leaves
(``console`` / ``context`` / ``parser``), the reconcile engine
(``reconcile``), and domain packages — never ``app``. ``app`` re-imports
``cmd_run`` / ``_cmd_run_sweep`` back so the package surface and the legacy
patch sites keep resolving.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from plan_tool.backend import get_active_backend
from plan_tool.branch_ownership import (
    Tier,
    branch_owner,
    classify_branch,
    convention_owner,
    expected_branch,
)
from plan_tool.create import CreateError
from plan_tool.launcher import (
    LauncherError,
    accept_step,
    format_findings_verdict,
    resolve_step,
    run_step,
    summarize_findings,
)
from plan_tool.claude_errors import (
    reset_rate_limit_resume_command_provider,
    set_rate_limit_resume_command_provider,
)
from plan_tool.jira_grade import GRADE_DEFAULT, GRADE_JIRA, JIRA_GRADE_VALUES
from plan_tool.renderer import DetailGradeError, load_jira_grade_step_detail
from plan_tool.scope_fence import _fenced_code_spans, _strip_frontmatter
from plan_tool.pathutil import literal_path
from plan_tool.locator import (
    PlanToolContext,
    collect_plan_entries,
    default_manifest_path,
    resolve_plan_for_context,
    slug_from_filename,
)
from plan_tool.parser import (
    ParseError,
    UnsupportedPlanFormatVersionError,
    ValidationError,
    parse_plan,
)
from plan_tool.plan_merge_guard import NO_REMOTE, check_plan_merged, default_branch_name
from plan_tool.project_config import branch_awareness_enabled, branch_prefixes, require_merged_plan
from plan_tool.run_log import RunLogWriter
from plan_tool.schema import StepStatus
from plan_tool.sweep import (
    ArchiveOutcome,
    archive_completed_plan,
    classify_plan,
)
from plan_tool.style import (
    BOLD_GREEN,
    BOLD_RED,
    DIM,
    color_enabled,
    error,
    paint,
    warn,
)

from plan_tool.cli.console import _print_next_steps
from plan_tool.cli.context import (
    _load_context,
    _resolve_iterative_budget,
)
from plan_tool.cli.gitcommit import (
    path_is_gitignored,
    unexpected_dirty_paths,
    branch_exists,
    checkout_existing_branch,
    create_and_checkout_branch,
    current_branch,
)
# Re-exported under its historical name so ``run_cmd._working_tree_dirty``
# stays the patch point the test suite monkeypatches (mirrors authoring.py).
from plan_tool.cli.gitcommit import working_tree_dirty as _working_tree_dirty
from plan_tool.cli.parser import Handler, make_yes_parent

# Reconcile engine (step-15 leaf). ``cmd_run`` forward-calls
# ``_cmd_run_reconcile`` for the ``--reconcile`` code-side audit (which owns
# its own reuse/save/walk plumbing). The edge is ``run_cmd`` -> ``reconcile``;
# ``reconcile`` imports neither ``run_cmd`` nor ``app``, so it stays
# cycle-free.
from plan_tool.cli.reconcile import _cmd_run_reconcile

# ``AVAILABLE_MODES`` is part of the ``plan_tool.cli`` package surface; the
# subparser below imports it lazily inside ``register`` from that surface
# (never from ``app`` directly) so this module carries no edge to ``app`` and
# stays cycle-free.


def _detail_grade(args: argparse.Namespace) -> str:
    """Which detail grade this invocation runs at.

    Read through ``getattr`` everywhere: hand-built namespaces are a
    repo-wide test idiom, and ``direct_cmd.cmd_direct_run`` reaches
    ``cmd_run`` with a copied namespace — the default keeps both on
    run grade.
    """
    return getattr(args, "detail_grade", GRADE_DEFAULT)


def _grade_flag_suffix(args: argparse.Namespace) -> str:
    """`` --detail-grade <g>`` when a non-default grade is active, else "".

    Every printed `plan-tool run` line carries it: a hint that drops the grade
    sends the operator to a run that renders from the other contract's body.
    """
    grade = _detail_grade(args)
    return f" --detail-grade {grade}" if grade != GRADE_DEFAULT else ""


def _reject_detail_grade_conflicts(args: argparse.Namespace) -> Optional[int]:
    """Reject a non-default grade combined with a non-execution path.

    Grade selects the *input* a step executes from, so it only means
    something on the execution path. Returns ``2`` (after printing the
    redirect) for a review ``--mode`` or the ``--reconcile`` audit alias,
    else ``None``. Called before any context or run-log work so a rejected
    invocation leaves no ghost run dir.
    """
    detail_grade = _detail_grade(args)
    if detail_grade == GRADE_DEFAULT:
        return None
    if getattr(args, "reconcile", False):
        error(
            f"--detail-grade {detail_grade} is mutually exclusive with "
            f"--reconcile (the code-side audit grounds on the plan contract, "
            f"not on a step's execution detail)."
        )
        return 2
    if getattr(args, "mode", "run") != "run":
        error(
            f"--detail-grade {detail_grade} applies to execution only (got "
            f"--mode {args.mode}); review modes carry their own grounding."
        )
        return 2
    return None


def _preflight_jira_grade_details(
    plan_path: Path,
    *,
    repo_root: Path,
    step_id: Optional[int],
    all_steps: bool,
) -> Optional[str]:
    """Aggregate every in-scope step that has no usable jira-grade artifact.

    Returns one error message naming *all* broken steps (an operator
    repairing a bundle wants the whole list) or ``None`` when every in-scope
    step can be executed at jira grade. Resolution and validation go through
    :func:`plan_tool.renderer.load_jira_grade_step_detail`, so this check and
    the render-time gate agree by construction.

    Scope is the steps this invocation would actually execute: the
    not-yet-done steps for a sweep, else the single step ``step_id``
    resolves to. That is at or inside the bundle-coverage rule's non-``done``
    set — a run may check fewer steps than the rule, never more, so ``run``
    can never reject a bundle the audit and the export accept.

    An explicitly requested ``done`` step is the one case where scope leaves
    that set: ``resolve_step`` honours ``--step N`` at any status. It is
    still checked (a step with no body cannot execute), but reported as an
    execution problem — bundle coverage exempts ``done`` steps, so the
    bundle is not at fault.

    A plan that fails to parse falls through (``None``); ``run_step``
    surfaces the same error with a better message.
    """
    try:
        plan = parse_plan(plan_path)
        if all_steps:
            steps = [s for s in plan.steps if s.status != StepStatus.DONE]
        else:
            steps = [resolve_step(plan, step_id)]
    except (OSError, ParseError, ValidationError, LauncherError):
        return None

    problems: list[str] = []
    for step in steps:
        try:
            load_jira_grade_step_detail(
                plan, step, plan_path=plan_path, repo_root=repo_root
            )
        except DetailGradeError as exc:
            note = (
                " (this step is done, which jira-grade bundle coverage "
                "exempts — the bundle is not at fault; this run simply has "
                "no body to execute from)"
                if step.status == StepStatus.DONE
                else ""
            )
            problems.append(f"{exc}{note}")
    if not problems:
        return None
    noun = "step" if len(problems) == 1 else "steps"
    bullets = "\n".join(f"- {body}" for body in problems)
    return (
        f"--detail-grade {GRADE_JIRA} cannot execute {len(problems)} "
        f"{noun}:\n{bullets}"
    )


def _build_run_resume_command(
    args: argparse.Namespace,
    plan_name: str,
    *,
    initial_backend_name: str | None = None,
) -> str:
    """Return the CLI command that resumes this ``run`` invocation.

    The command is intentionally narrow: it includes the plan and the flags
    that affect execution scope / durability, plus the currently active
    backend so stopping on a rate limit can be resumed without depending on
    ambient ``PLAN_TOOL_BACKEND`` state. A switched backend omits the original
    model rather than pairing it with a different CLI.
    """
    argv = [
        "plan-tool",
        "--backend",
        get_active_backend().name,
    ]
    if getattr(args, "model", None) and (
        initial_backend_name is None
        or get_active_backend().name == initial_backend_name
    ):
        argv.extend(["--model", args.model])
    argv.extend(["run", plan_name])
    if getattr(args, "commit", False):
        argv.append("--commit")
    if getattr(args, "all", False):
        argv.append("--all")
    if args.step is not None:
        argv.extend(["--step", str(args.step)])
    if getattr(args, "archive", False):
        argv.append("--archive")
    if getattr(args, "dry_run", False):
        argv.append("--dry-run")
    if getattr(args, "allow_missing_parent", False):
        argv.append("--allow-missing-parent")
    detail_grade = _detail_grade(args)
    if detail_grade != GRADE_DEFAULT:
        argv.extend(["--detail-grade", detail_grade])
    return shlex.join(argv)


def _warn_missing_step_detail(
    plan_path: Path,
    *,
    repo_root: Path,
    plan_name: str,
    step_id: Optional[int],
) -> bool:
    """Recommend authoring a detail file when the step about to run lacks one.

    A step's detail file grounds its prompt and carries the
    ``change_type`` Tests directive, so executing without one yields a
    thinner prompt. This is a recommendation, not a gate: the caller
    proceeds unchanged whether or not the warning fires. Emits at most
    one stderr line (``warning:`` prefix) naming the exact remediation
    command, and returns ``True`` when it did.

    The step is "detail-less" when its ``detail`` field is unset or
    points at a file that is missing on disk. Plan-resolution failures
    fall through silently (return ``False``) — ``run_step`` surfaces the
    same error with a better message right after.
    """
    try:
        plan = parse_plan(plan_path)
        step = resolve_step(plan, step_id)
    except (OSError, ParseError, ValidationError, LauncherError):
        # OSError covers a plan path that doesn't resolve on disk —
        # read_text raises before any parse begins.
        return False
    if step.detail is not None and (repo_root / step.detail).is_file():
        return False
    warn(
        f"step {step.id} has no detail file; details ground the step "
        f"prompt and carry the change_type Tests directive — recommended: "
        f"plan-tool detail {plan_name} --step {step.id}"
    )
    return True


def _confirm_missing_step_details(
    plan_path: Path,
    *,
    repo_root: Path,
    plan_name: str,
    step_id: Optional[int],
    all_steps: bool,
    yes: bool,
) -> bool:
    """Warn + confirm before running when in-scope step(s) lack a detail file.

    Unlike :func:`_warn_missing_step_detail` (a non-blocking per-step
    recommendation), this is a preflight *gate*. It collects every
    in-scope step whose ``detail`` is unset or points at a file missing on
    disk and, when any are missing, warns and asks whether to proceed.
    ``all_steps`` checks the whole plan (the ``--all`` sweep); otherwise
    only the single step ``step_id`` resolves to (``None`` = the next
    runnable step).

    Returns ``True`` to proceed, ``False`` to abort. ``yes`` proceeds
    without prompting. A non-interactive stdin can't answer, so it
    proceeds (the warning already fired) rather than hang or newly break
    unattended runs. A plan that fails to parse falls through (``True``):
    ``run_step`` surfaces the same error with a better message.
    """
    try:
        plan = parse_plan(plan_path)
        if all_steps:
            # A sweep only runs not-yet-done steps; a done step whose
            # detail was archived would be a false positive.
            steps = [s for s in plan.steps if s.status != StepStatus.DONE]
        else:
            steps = [resolve_step(plan, step_id)]
    except (OSError, ParseError, ValidationError, LauncherError):
        return True
    missing = [
        s for s in steps
        if s.detail is None or not (repo_root / s.detail).is_file()
    ]
    if not missing:
        return True
    ids = ", ".join(str(s.id) for s in missing)
    warn(
        f"detail file missing for step(s) {ids}; details ground the step "
        f"prompt and carry the change_type Tests directive, so running "
        f"without them yields a thinner prompt. Author them with "
        f"`plan-tool detail {plan_name} --step <id>`."
    )
    if yes:
        return True
    if not _stdin_is_tty():
        warn("stdin is not a TTY; proceeding without confirmation (pass -y to silence).")
        return True
    try:
        answer = input("Proceed without these detail file(s)? [y/N] ").strip().lower()
    except EOFError:
        answer = ""
    return answer in ("y", "yes")


_MERGE_LIST_CAP = 8


def _preflight_merged_plan_guard(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> Optional[int]:
    """Refuse ``run`` on the default branch or before the plan is fully on it.

    Return contract matches :func:`_preflight_branch_guard`: ``None``
    proceeds, ``2`` is the refusal rc. On by default; ``--skip-merge-check``
    or ``run.require_merged_plan: false`` turns it off. A repo with no
    ``origin`` proceeds silently: there is nothing to have merged into.
    """
    if getattr(args, "skip_merge_check", False):
        warn("merge check skipped (--skip-merge-check).")
        return None
    if not require_merged_plan(ctx.repo_root):
        return None
    check = check_plan_merged(ctx.repo_root, plan_path, _detail_grade(args))
    if check.unverifiable is not None:
        if check.unverifiable != NO_REMOTE:
            warn(f"cannot verify the plan is on the default branch: {check.unverifiable}; proceeding.")
        return None
    default = default_branch_name(check.default_ref)
    if current_branch(ctx.repo_root) == default:
        error(
            f"`run` must not run on the default branch '{default}'. Create a "
            "feature branch (for example `git switch -c <ticket-key>`) and run "
            "there. To skip this check once, pass --skip-merge-check."
        )
        return 2
    if check.missing:
        more = len(check.missing) - _MERGE_LIST_CAP
        shown = ", ".join(check.missing[:_MERGE_LIST_CAP]) + (f" (and {more} more)" if more > 0 else "")
        error(
            f"the plan is not fully on {check.default_ref}; missing there: {shown}. "
            f"Merge the plan's pull request first (author the plan and its detail "
            f"files on a plan branch, get it reviewed, merge), `git fetch`, then "
            f"branch from {default} and run. To skip this check once, pass "
            "--skip-merge-check."
        )
        return 2
    if check.drifted:
        warn(
            f"these differ from {check.default_ref} (edited after the plan "
            f"merged): {', '.join(check.drifted[:_MERGE_LIST_CAP])}. Merge the "
            "change first if it needs review."
        )
    return None


def _preflight_branch_guard(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_slug: str,
) -> Optional[int]:
    """Classify the current branch against the plan; block/warn/nudge/switch.

    Fires only on a mutating ``run`` (the call site gates on ``--mode run``
    and ``not --dry-run``). Return contract: ``None`` proceeds, an ``int``
    is the rc :func:`cmd_run` returns immediately (``2`` for a block /
    refusal, matching this file's other preflight rejections).

    Off by default: returns ``None`` *before reading any branch* when
    branch awareness is disabled, so an unconfigured repo is a no-op.
    Non-git / detached HEAD (``current_branch`` -> ``None``) prints a note
    and proceeds. Otherwise it does the one git read via
    :func:`branch_owner`, classifies with the pure
    :func:`classify_branch`, and maps the tier to UX:

    - **Tier 1-2** (a local signal makes ownership unambiguous): block
      unless the branch is this plan's. A Tier-1 ad-hoc binding that
      shadows a *different* plan's convention name also surfaces that
      conflict.
    - **Tier 3** (orphan pattern): warn and proceed.
    - **Tier 4** (unowned): nudge toward ``expected_branch``, or — with
      ``--switch-branch`` on a clean tree — create-if-missing and switch.
    """
    if not branch_awareness_enabled(ctx.repo_root):
        return None

    current = current_branch(ctx.repo_root)
    if current is None:
        warn(
            "branch awareness is on but the current branch is "
            "undeterminable (detached HEAD or non-git) — proceeding."
        )
        return None

    prefixes = branch_prefixes(ctx.repo_root)
    registered = {e.slug for e in ctx.entries}
    owner = branch_owner(ctx.repo_root, current, registered, prefixes)
    cls = classify_branch(current, plan_slug, owner, prefixes)

    if cls.tier <= Tier.CONVENTION_OWNED:
        if cls.is_owned_by_plan:
            return None
        kind = (
            "an ad-hoc branch binding"
            if cls.tier == Tier.AD_HOC_OWNED
            else "the branch-naming convention"
        )
        message = (
            f"branch '{current}' is owned by plan '{cls.owner}' via {kind}, "
            f"not '{plan_slug}'."
        )
        if cls.tier == Tier.AD_HOC_OWNED:
            shadowed = convention_owner(current, registered, prefixes)
            if shadowed is not None and shadowed != cls.owner:
                message += (
                    f" (the convention claim by '{shadowed}' is shadowed "
                    f"by the ad-hoc binding.)"
                )
        expected = expected_branch(ctx.repo_root, plan_slug, prefixes)
        message += (
            f" Switch to '{plan_slug}'s branch ('{expected}'), or use "
            f"`plan-tool attach-branch` / `detach-branch` to change "
            f"ownership."
        )
        error(message)
        return 2

    if cls.tier == Tier.ORPHAN_PATTERN:
        warn(
            f"branch '{current}' matches the naming convention but no "
            f"locally-registered plan owns it (likely another developer's "
            f"plan or one not yet pulled) — proceeding."
        )
        return None

    # Tier 4 (UNOWNED): no local signal ties this branch to any plan.
    expected = expected_branch(ctx.repo_root, plan_slug, prefixes)
    if current == expected:
        return None

    if getattr(args, "switch_branch", False):
        # The clean-tree precondition is checked ONLY on this switch path —
        # an unconditional check would be a false refusal on the no-op path.
        if _working_tree_dirty(ctx.repo_root):
            error(
                "--switch-branch needs a clean working tree (commit or "
                "stash your changes first)."
            )
            return 2
        if branch_exists(ctx.repo_root, expected):
            rc, tail = checkout_existing_branch(ctx.repo_root, expected)
            verb = "switched to"
        else:
            rc, tail = create_and_checkout_branch(ctx.repo_root, expected)
            verb = "created and switched to"
        if rc != 0:
            if "already checked out" in (tail or "").lower():
                # The branch lives in a worktree (e.g. `worktree add` provisioned
                # it); git refuses to check it out twice. Point the operator at
                # the worktree instead of surfacing git's raw fatal.
                error(
                    f"branch '{expected}' is already checked out in another "
                    f"worktree ({tail.strip()}). Run the plan from that "
                    f"worktree, or remove it with `plan-tool worktree remove "
                    f"{plan_slug}` first."
                )
            else:
                error(tail or f"failed to switch to branch '{expected}'.")
            return 2
        print(f"{verb} branch '{expected}' for plan '{plan_slug}'.")
        return None

    warn(
        f"branch '{current}' is unowned; plan '{plan_slug}' expects branch "
        f"'{expected}'. Pass --switch-branch to move there (on a clean "
        f"tree) before running — proceeding on the current branch."
    )
    return None


def _record_sweep_halt(
    plan,
    *,
    repo_root: Path,
    step_id,
    reason: str,
    now: Optional[datetime] = None,
) -> Optional[Path]:
    """Append a one-line halt entry to the plan's ``lessons:`` file.

    The native ``run --all`` sweep's halt self-recording: when the sweep
    halts — on a run failure or a per-step ``gate`` / ``test_command``
    refusing
    advancement (both surface as a non-zero step exit), or on a preflight
    ``LauncherError`` — a halt line self-records next to the plan it
    guards so an operator's post-mortem lesson can extend it after the
    fix.

    The line shape is ``- <ts> step N halt (sweep): <reason>``. The
    ``halt (sweep)`` segment between the step number and the colon means
    :data:`plan_tool.launcher._LESSONS_STEP_RE` (which matches only
    ``step\\s+\\d+\\s*:``) does **not** match, so halt lines never inflate
    :func:`plan_tool.launcher.read_lessons_step_ids` and never trip
    :func:`plan_tool.launcher.append_lesson`'s per-step idempotency guard.
    The ``(sweep)`` producer tag distinguishes app-written halts from any
    ``(harness)`` lines a transitional ``fail()`` still writes.

    Mirrors :func:`plan_tool.launcher.append_lesson`'s structure (no-op
    when ``plan.lessons`` is unset, ``mkdir(parents=True)``, injectable
    ``now``, returns the written :class:`~pathlib.Path` or ``None``) but
    is a separate helper: ``append_lesson``'s completion-line format and
    its idempotency short-circuit are both wrong for halts, which must
    always record. ``step_id`` is left untyped so a defensive non-int
    fallback string would still render; both call sites pass an ``int``.
    """
    if plan.lessons is None:
        return None
    lessons_path = repo_root / plan.lessons
    lessons_path.parent.mkdir(parents=True, exist_ok=True)
    ts = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    line = f"- {ts} step {step_id} halt (sweep): {reason}\n"
    with lessons_path.open("a", encoding="utf-8") as f:
        f.write(line)
    return lessons_path


_GREEN_COMMIT_TITLE_CAP = 60


def _green_commit_subject(slug: str, step_id: int, step_title: str) -> str:
    """The per-step commit subject mirroring the gated-run harness.

    Pure function so a test can assert the exact format without shelling
    out. Em dash (U+2014) separates the prefix from the title. The title
    is truncated (with an ellipsis) at ``_GREEN_COMMIT_TITLE_CAP`` so the
    subject stays a sane git-log width — step titles run long, and the
    harness it mirrors did the same via ``cut -c1-60``.
    """
    if len(step_title) > _GREEN_COMMIT_TITLE_CAP:
        step_title = step_title[: _GREEN_COMMIT_TITLE_CAP - 1].rstrip() + "…"
    return f"plan({slug}): step {step_id} green — {step_title}"


def _green_commit_failure_msg(
    rc: int, step_id: int, tail: str, *, swept: bool
) -> str:
    """Recovery message for a failed green-step ``--commit``, shared by the
    single-step and ``--all`` sweep call sites. ``swept`` adds the sweep-halt
    clause; ``tail`` (git stderr) is appended when present."""
    lead = (
        f"git commit failed (rc={rc}) for green step {step_id}; sweep halted. The"
        if swept
        else f"git commit failed (rc={rc}) for green step {step_id}; the"
    )
    msg = (
        f"{lead} step's work is staged/uncommitted in the working tree — "
        f"inspect with `git status` and `git diff` (recover with `git reset`)."
    )
    if tail:
        msg += f" git: {tail}"
    return msg


def _commit_green_step(
    repo_root: Path,
    *,
    slug: str,
    step_id: int,
    step_title: str,
    paths: Optional[list[Path]] = None,
) -> tuple[int, str]:
    """Stage all changes and commit the just-greened step. Returns ``(rc, tail)``.

    ``paths`` (``--accept``) scopes the commit to those files, so build output
    a certifying suite left behind is not swept in; a gitignored path is
    skipped rather than failing ``git add``.

    One ``git add -A`` + ``git commit`` per green step: ``git add -A``
    stages the step's code edits and
    the plan-file mark-done/advance write ``run_step`` already performed
    (and any ``.plan-tool/runs/`` run-log artifacts, unless gitignored —
    the harness has the same property). The commit carries the mirrored
    subject only — no AI-attribution trailer; the operator's own git
    identity is the sole author of record. No ``--no-verify`` — pre-commit
    hooks run, and a hook rejection surfaces as a non-zero rc that halts
    the sweep. ``tail`` is the commit's stderr so the caller can surface a
    reason on failure.
    """
    scoped = (
        None
        if paths is None
        else [
            str(p) for p in paths
            if p.exists() and not path_is_gitignored(repo_root, p)
        ]
    )
    add = subprocess.run(
        ["git", "add", "-A"] if scoped is None else ["git", "add", "--", *scoped],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        return add.returncode, add.stderr.strip()
    subject = _green_commit_subject(slug, step_id, step_title)
    commit = subprocess.run(
        ["git", "commit", "-m", subject]
        + ([] if scoped is None else ["--", *scoped]),
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return commit.returncode, commit.stderr.strip()


def _archive_on_completion(
    plan_path: Path,
    *,
    ctx: PlanToolContext,
    manifest_path: Path,
) -> Optional[ArchiveOutcome]:
    """Archive a plan the moment a run takes it to N/N done (opt-in ``--archive``).

    Re-derives completion from the freshly-written plan file rather than
    trusting the caller: parses ``plan_path`` into a one-element
    :class:`PlanEntry` list via :func:`collect_plan_entries`, then classifies
    it with :func:`classify_plan` — the strict ``status: completed`` ∧
    every-step-``done`` rule. Only a genuinely complete plan is archived.

    Returns the :class:`ArchiveOutcome` on a successful archive. Returns
    ``None`` (no-op) when the plan is not complete — printing a one-line
    ``not complete (<done>/<total> done)`` note — or when the file vanished
    or went unparseable between the mark-done write and this call.

    On success prints the archived path (relative to ``ctx.repo_root`` when
    it lives within the root) plus a ``plan-tool register <archived-path>``
    undo hint so the action and its reversal are both visible. Best-effort
    :attr:`ArchiveOutcome.skipped` reasons (e.g. an archive-target
    collision) are surfaced on stderr, mirroring ``_print_sweep_report``.
    """
    entries = collect_plan_entries([plan_path])
    if not entries or entries[0].plan is None:
        # File removed or corrupted between run_step's write and now —
        # nothing safe to archive; leave it in place silently.
        return None
    classification = classify_plan(entries[0])
    if not classification.completed:
        counts = classification.counts
        done = counts.done if counts is not None else 0
        total = counts.total if counts is not None else 0
        print(
            f"--archive: plan not complete ({done}/{total} done); "
            f"nothing archived."
        )
        return None

    outcome = archive_completed_plan(
        classification,
        manifest_path=manifest_path,
        repo_root=ctx.repo_root,
    )

    if outcome.archived_to is not None:
        target = literal_path(outcome.archived_to, ctx.repo_root)
        print(f"archived: {outcome.slug} → {target}")
        print(
            f"  undo: plan-tool register {target} "
            f"(re-register the archived plan in the manifest)"
        )
    for skipped in outcome.skipped:
        print(f"  ! {skipped}", file=sys.stderr)
    return outcome


# ---------------------------------------------------------------------------
# Interactive plan picker (no-name / unresolved-name fallback for `run`)
# ---------------------------------------------------------------------------
#
# When `plan-tool run` is invoked without a plan name (or with one that
# doesn't resolve) and stdin is a TTY, `cmd_run` offers a numbered list of
# the plans that still have open steps, asks whether to run all runnable
# steps or just the next one, and remembers both choices in a small
# per-repo prefs file so the next picker pre-selects them.

# Runtime state, sibling to .plan-tool/runs and .plan-tool/checkpoints.
RUN_PREFS_REL = (".plan-tool", "run-prefs.json")


def _stdin_is_tty() -> bool:
    """True when stdin is an interactive terminal we can prompt on.

    Pipes, redirected stdin, and CI keep the historical hard error /
    re-raise path instead of hanging on an unanswerable prompt.
    """
    try:
        return sys.stdin.isatty()
    except Exception:
        return False


def _run_prefs_path(repo_root: Path) -> Path:
    return repo_root.joinpath(*RUN_PREFS_REL)


def _load_run_prefs(repo_root: Path) -> dict:
    """Return the parsed run-prefs dict, or ``{}`` if absent/unreadable."""
    try:
        data = json.loads(_run_prefs_path(repo_root).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_run_prefs(
    repo_root: Path, *, last_plan: str, scope: Optional[str]
) -> None:
    """Record the last-run plan and (when known) its all/next scope.

    Best-effort: a write failure must never abort a run, so every error
    is swallowed. ``scope`` of ``None`` (e.g. an explicit ``--step N``)
    updates ``last_plan`` without touching the per-plan scope memory.
    """
    prefs = _load_run_prefs(repo_root)
    prefs["last_plan"] = last_plan
    if scope in ("all", "next"):
        by_plan = prefs.get("scope_by_plan")
        if not isinstance(by_plan, dict):
            by_plan = {}
        by_plan[last_plan] = scope
        prefs["scope_by_plan"] = by_plan
    path = _run_prefs_path(repo_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prefs, indent=2) + "\n", encoding="utf-8")
    except OSError:
        pass


def _open_plan_entries(ctx: PlanToolContext) -> list:
    """Parsed plan entries that still have at least one non-``done`` step."""
    return [
        e
        for e in ctx.entries
        if e.plan is not None and not e.plan.all_steps_done
    ]


def _open_step_hint(plan) -> str:
    """One-line description of what `run` would do next for an open plan."""
    nxt = plan.next_runnable_step()
    if nxt is not None:
        title = nxt.title.strip()
        if len(title) > 48:
            title = title[:47] + "…"
        return f"next: step {nxt.id} — {title}"
    cur = plan.current_step()
    if cur is not None:
        return f"current: step {cur.id} in progress"
    return "no runnable step (blocked / deps unmet)"


def _read_plan_choice(n: int, *, default: int) -> Optional[int]:
    """Read a 1..n menu selection. Enter picks ``default``; q/EOF returns None."""
    prompt = f"Select a plan [1-{n}] (Enter={default}, q to quit): "
    while True:
        try:
            raw = input(prompt).strip()
        except EOFError:
            print()
            return None
        if raw == "":
            return default
        if raw.lower() in ("q", "quit"):
            return None
        if raw.isdigit() and 1 <= int(raw) <= n:
            return int(raw)
        print(f"  enter a number 1-{n}, or q to quit.")


def _select_open_plan(
    ctx: PlanToolContext, *, last_plan: Optional[str]
) -> Optional[tuple[Path, str]]:
    """Prompt for one plan with open steps.

    Returns ``(plan_path, canonical_slug)`` for the chosen plan, or
    ``None`` when there is nothing to run or the user quits. The default
    selection is ``last_plan`` when it still has open steps, else the
    first row. Caller guarantees an interactive stdin.
    """
    candidates = _open_plan_entries(ctx)
    if not candidates:
        print("no plans with open steps.")
        _print_next_steps(
            "Try:",
            [
                ("plan-tool list", "show all registered plans"),
                ("plan-tool create <slug>", "author a new plan"),
            ],
        )
        return None

    default_idx = 1
    for i, e in enumerate(candidates, start=1):
        if last_plan is not None and e.slug == last_plan:
            default_idx = i
            break

    print("Plans with open steps:")
    num_w = len(str(len(candidates)))
    slug_w = min(max(len(e.slug) for e in candidates), 40)
    for i, e in enumerate(candidates, start=1):
        plan = e.plan
        marker = "*" if i == default_idx else " "
        steps = f"{plan.done_count}/{len(plan.steps)} done"
        prio = f"[{plan.priority.value}]"
        print(
            f"  {marker}{str(i).rjust(num_w)}. {e.slug.ljust(slug_w)}  "
            f"{steps:<9} {prio:<8} {_open_step_hint(plan)}"
        )
    print("  (* = last run; Enter selects it)")

    choice = _read_plan_choice(len(candidates), default=default_idx)
    if choice is None:
        return None
    chosen = candidates[choice - 1]
    return chosen.path, chosen.slug


def _prompt_run_scope(default: str) -> Optional[str]:
    """Ask whether to run ``all`` runnable steps or just the ``next`` one.

    ``default`` (``"all"`` / ``"next"``) is taken on a blank line; q/EOF
    returns None.
    """
    hint = "[n/A]" if default == "all" else "[N/a]"
    prompt = (
        f"Run [a]ll runnable steps or just the [n]ext step? {hint} "
        f"(q to quit): "
    )
    while True:
        try:
            raw = input(prompt).strip().lower()
        except EOFError:
            print()
            return None
        if raw == "":
            return default
        if raw in ("n", "next"):
            return "next"
        if raw in ("a", "all"):
            return "all"
        if raw in ("q", "quit"):
            return None
        print("  enter 'n' for next, 'a' for all, or q to quit.")


def _accept_flag_error(args: argparse.Namespace) -> Optional[int]:
    """Reject ``--accept`` combinations that imply a backend call, and a
    missing ``--step``. Run before the picker and any context work, so a
    rejected invocation never asks the all-or-next question or logs a run."""
    if not getattr(args, "accept", False):
        return None
    conflicts = [
        flag
        for flag, active in (
            ("--all", getattr(args, "all", False)),
            ("--reconcile", getattr(args, "reconcile", False)),
            ("--dry-run", args.dry_run),
            ("--archive", getattr(args, "archive", False)),
            (f"--detail-grade {_detail_grade(args)}",
             _detail_grade(args) != GRADE_DEFAULT),
            (f"--mode {args.mode}", args.mode != "run"),
        )
        if active
    ]
    if conflicts:
        error(
            f"--accept cannot be combined with {', '.join(conflicts)}: it "
            "certifies one hand-fixed step and makes no backend call."
        )
        return 2
    if args.step is None:
        error("--accept needs --step N: name the hand-fixed step to accept.")
        return 2
    if getattr(args, "iterate", False):
        # Tolerated as on every ``run`` (scripts pass it uniformly), but say so.
        warn("--iterate has no effect with --accept (no backend call).")
    return None


def _cmd_run_accept(
    args: argparse.Namespace, *, ctx: PlanToolContext, plan_path: Path
) -> int:
    """``run <slug> --step N --accept``: mark a hand-fixed step done.

    Certifies with the plan's ``test_command`` and the step's ``gate`` (the
    gates a backend run would have run), then applies the ordinary done-and-
    advance. Refuses, with the plan untouched, on a combination that implies
    a backend call, a dirty tree, or a step that cannot be certified. See
    docs/how-to/pipeline/run.md § "Accept a hand-fixed step".
    """
    try:
        plan = parse_plan(plan_path)
    except (ParseError, ValidationError) as exc:
        error(str(exc))
        return 2
    # The tool itself leaves the plan (a failed gate's ``status_note``) and a
    # sweep halt's lessons line dirty, so those two files are expected; any
    # other change means the certified tree is not the committed one.
    expected = [plan_path] + ([ctx.repo_root / plan.lessons] if plan.lessons else [])
    dirty = unexpected_dirty_paths(ctx.repo_root, expected)
    if dirty is None or dirty:
        error(
            "--accept requires a clean working tree apart from the plan "
            "file and its lessons log: commit the hand fix first"
            + (f" (uncommitted: {', '.join(dirty[:5])})" if dirty else "")
            + "."
        )
        return 2
    try:
        result = accept_step(plan_path, repo_root=ctx.repo_root, step_id=args.step)
    except (LauncherError, ParseError, ValidationError) as exc:
        error(str(exc))
        return 2
    except OSError as exc:
        error(f"could not persist the accepted step: {exc}")
        return 1
    if result.exit_code != 0:
        print(
            f"✗ step {result.step_id} not accepted; plan unchanged.",
            file=sys.stderr,
        )
        return result.exit_code
    if getattr(args, "commit", False):
        rc_commit, tail = _commit_green_step(
            ctx.repo_root,
            slug=args.name,
            step_id=result.step_id,
            step_title=result.step_title,
            paths=expected,
        )
        if rc_commit != 0:
            error(_green_commit_failure_msg(
                rc_commit, result.step_id, tail, swept=False
            ))
            return rc_commit
    if result.plan_completed:
        print(f"✓ step {result.step_id} accepted — plan completed")
    elif result.advanced_to is not None:
        print(
            f"✓ step {result.step_id} accepted — advanced to step "
            f"{result.advanced_to}"
        )
    else:
        print(f"✓ step {result.step_id} accepted")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    """Drive a step via a fresh claude subprocess (execution / audit).

    Intent: invoke claude with the rendered step prompt and either
    advance plan state (default ``--mode run``) or surface a
    read-only review verdict (``--mode check`` / ``optimize`` /
    ``document`` / ``test`` / ``security`` / ``lint``).

    Dual identity by design:

    - ``--mode run`` is the *execution* primitive — the only way
      code actually gets written and the only way step status
      advances. New code-mutating modes belong here.
    - ``--mode <review>`` is the per-step *audit* primitive —
      complements :func:`cmd_review` (plan-wide) and
      :func:`cmd_review_all` (all-done-steps). New per-step
      read-only inspections (e.g. ``--mode accessibility``) also
      belong here, hooked into ``MUTATING_MODES`` only when they
      legitimately mutate.

    The code-side reconcile audit is reached via the ``--reconcile``
    flag (:func:`_cmd_run_reconcile`), which saves findings as a
    walkable artifact and offers to replay a pre-existing save instead
    of spending a fresh claude call.

    See ``docs/reference/contracts/process.md`` for the execution and reconciliation
    authority boundaries.
    """
    # Grade/mode conflicts are pure argument validation — rejected before any
    # context or run-log work so a bad invocation leaves nothing behind.
    grade_conflict_rc = _reject_detail_grade_conflicts(args)
    if grade_conflict_rc is not None:
        return grade_conflict_rc
    accept_conflict_rc = _accept_flag_error(args)
    if accept_conflict_rc is not None:
        return accept_conflict_rc

    ctx = _load_context(args)

    # Resolve the plan, falling back to the interactive picker when no
    # name was given or the given one doesn't resolve. The picker is
    # TTY-only: pipes / -y keep the historical hard error (no name) or
    # re-raise (bad name) so scripts fail fast instead of blocking on a
    # prompt. ``picked`` records whether the picker ran, so the scope
    # question below only fires on the interactive path.
    prefs = _load_run_prefs(ctx.repo_root)
    picked = False
    if args.name is None:
        if not _stdin_is_tty():
            error(
                "a plan name is required when stdin is not a TTY. Pass a "
                "plan slug, or run `plan-tool list` to see what's registered."
            )
            return 2
        selection = _select_open_plan(ctx, last_plan=prefs.get("last_plan"))
        if selection is None:
            return 0  # nothing to run, or the user quit
        path, args.name = selection
        picked = True
    else:
        try:
            path = resolve_plan_for_context(ctx, args.name)
        except FileNotFoundError as exc:
            if not _stdin_is_tty():
                raise  # non-interactive: keep the rc=2 via the dispatcher
            warn(str(exc))
            selection = _select_open_plan(ctx, last_plan=prefs.get("last_plan"))
            if selection is None:
                return 0
            path, args.name = selection
            picked = True

    try:
        plan_text = path.read_text(encoding="utf-8")
    except OSError as exc:
        error(f"{path}: could not read plan file: {exc}")
        return 2
    if _fenced_code_spans(_strip_frontmatter(plan_text)).unmatched_opening is not None:
        error(
            f"{path}: unmatched opening code fence; add a matching closing fence "
            "before running this plan."
        )
        return 2

    # On the interactive path, ask all-vs-next unless the user already
    # pinned the scope with --all / --step. The default is the last
    # scope chosen for this plan (else "next").
    if picked and not getattr(args, "all", False) and args.step is None:
        slug = slug_from_filename(path)
        default_scope = (prefs.get("scope_by_plan") or {}).get(slug, "next")
        if default_scope not in ("all", "next"):
            default_scope = "next"
        scope = _prompt_run_scope(default_scope)
        if scope is None:
            return 0
        if scope == "all":
            args.all = True

    # Remember the plan + scope for the next picker run (best-effort).
    # Skipped for the ``--reconcile`` audit path (not an execution).
    # ``next`` for the default single-step run, ``all`` for a sweep, and
    # ``None`` (plan-only update) for an explicit ``--step N``.
    record_prefs = not getattr(args, "reconcile", False)
    run_scope = (
        "all"
        if getattr(args, "all", False)
        else ("next" if args.step is None else None)
    )
    run_slug = slug_from_filename(path)

    # Branch-awareness preflight (mutating run only): classify the current
    # branch against the plan and block / warn / nudge / switch. A
    # byte-for-byte no-op when branch awareness is off (every repo with no
    # config). Placed before both ``_save_run_prefs`` writes (which dirty
    # the tree and would trip ``--switch-branch``'s clean-tree gate) and
    # the run log, so the guard measures the user's tree — not the tool's —
    # and a block leaves no ghost run dir. ``cmd_run`` is the single funnel
    # all mutating ``run`` variants pass through (single-step, ``--all``
    # sweep, ``--reconcile``), so one predicate-gated call here guards them
    # all; review modes (``mode != "run"``) and ``--dry-run`` skip it.
    if args.mode == "run" and not args.dry_run:
        guard_rc = _preflight_branch_guard(args, ctx=ctx, plan_slug=run_slug)
        if guard_rc is not None:
            return guard_rc
        if not getattr(args, "reconcile", False):
            merge_rc = _preflight_merged_plan_guard(args, ctx=ctx, plan_path=path)
            if merge_rc is not None:
                return merge_rc

    # ``--accept`` certifies a hand-fixed step with no backend call: validated
    # and dispatched before the sweep / audit branches so a bad combination is
    # rejected cleanly. See ``_cmd_run_accept``.
    if getattr(args, "accept", False):
        return _cmd_run_accept(args, ctx=ctx, plan_path=path)

    # ``--all`` sweep dispatch lives BEFORE the ``--reconcile`` audit
    # branch so the sweep's flag validations (mode allowlist, mutex
    # with --step / --reconcile) reject bad combinations cleanly with
    # rc=2 instead of falling into that branch. See ``_cmd_run_sweep``
    # for the loop body and validation policy.
    if getattr(args, "all", False):
        # Defer the prefs write until AFTER the sweep: the prefs file is
        # runtime state (gitignored in a real repo), but writing it up
        # front would dirty the working tree and trip ``--commit``'s
        # clean-tree precheck.
        initial_backend_name = get_active_backend().name
        resume_token = set_rate_limit_resume_command_provider(
            lambda: _build_run_resume_command(
                args, run_slug, initial_backend_name=initial_backend_name
            )
        )
        try:
            rc = _cmd_run_sweep(args, ctx=ctx, plan_path=path)
        finally:
            reset_rate_limit_resume_command_provider(resume_token)
        if record_prefs:
            _save_run_prefs(ctx.repo_root, last_plan=run_slug, scope=run_scope)
        return rc

    # ``--commit`` only commits a green *execution* step. Warn (don't fail)
    # when it can't fire — a review mode or ``--reconcile`` — so it's never a
    # silent no-op (``--dry-run`` is documented as ignoring it, so stays quiet).
    commit_active = getattr(args, "commit", False) and not args.dry_run
    if commit_active and (args.mode != "run" or getattr(args, "reconcile", False)):
        ignored_by = (
            "--reconcile" if getattr(args, "reconcile", False)
            else f"--mode {args.mode}"
        )
        warn(f"--commit has no effect with {ignored_by} (no step is committed).")

    # ``--commit`` requires a clean tree at single-step scope too (parity with
    # the ``--all`` sweep). Checked before the prefs write — which can dirty
    # the tree in a repo that doesn't gitignore run-prefs.json — so it measures
    # the user's tree, and before the run log so a rejection leaves no ghost run
    # dir. Run-execution path only. See docs/how-to/pipeline/run.md.
    if commit_active and args.mode == "run" and not getattr(args, "reconcile", False):
        if _working_tree_dirty(ctx.repo_root):
            error(
                "--commit requires a clean working tree (commit or "
                "stash your changes first)."
            )
            return 2

    # Record prefs before the run log (keeps last_plan fresh even if the step
    # fails); run-prefs.json is gitignored, so it doesn't ride a --commit commit.
    if record_prefs:
        _save_run_prefs(ctx.repo_root, last_plan=run_slug, scope=run_scope)

    # ``--reconcile`` switches ``run`` into a code-side audit path
    # (renders prompts/run-reconcile.md, lands code edits inline via
    # acceptEdits, short-circuits plan-rooted findings with
    # ``[REDIRECT]``). It is mutually exclusive with ``--mode`` (the
    # audit always uses mode="run-reconcile") and ``--iterate`` (the
    # new audit path does not iterate).
    # Checked here rather than via add_mutually_exclusive_group
    # because ``--mode`` carries a default of ``"run"`` and argparse
    # can't tell "user passed --mode run" from "user didn't pass
    # --mode" without post-parse inspection. Rejection short-circuits
    # before any run log opens to keep the on-disk artifact for bad
    # invocations.
    if getattr(args, "reconcile", False):
        if args.mode != "run":
            error(
                f"--reconcile is mutually exclusive with --mode "
                f"(got --mode {args.mode}); use --reconcile alone."
            )
            return 2
        if getattr(args, "iterate", False):
            error(
                "--reconcile is mutually exclusive with --iterate "
                "(the new audit path does not iterate)."
            )
            return 2
        return _cmd_run_reconcile(args, ctx=ctx, plan_path=path)

    # Preflight gate: when the step about to execute has no detail file,
    # warn and (on an interactive TTY) confirm before opening a run log or
    # spending a claude call. Scoped to the execution mode and skipped in
    # --dry-run, superseding the older non-blocking recommendation. Placed
    # before the run log opens so a decline leaves no ghost run dir.
    #
    # Under a non-default grade the run-grade warn/confirm helpers are the
    # wrong check (they read ``Step.detail`` and recommend authoring it) and
    # the wrong shape (warn-and-proceed is the silent fallback the grade
    # forbids). The hard aggregated preflight below replaces them, and runs
    # under --dry-run too so a broken artifact never reaches a render.
    detail_grade = _detail_grade(args)
    if detail_grade == GRADE_JIRA:
        problem = _preflight_jira_grade_details(
            path,
            repo_root=ctx.repo_root,
            step_id=args.step,
            all_steps=False,
        )
        if problem is not None:
            error(problem)
            return 2
    elif args.mode == "run" and not args.dry_run:
        if not _confirm_missing_step_details(
            path,
            repo_root=ctx.repo_root,
            plan_name=args.name,
            step_id=args.step,
            all_steps=False,
            yes=args.yes,
        ):
            print("aborted: missing detail file(s).", file=sys.stderr)
            return 0

    # Open the run log AFTER resolve_plan_for_context succeeds. A bad
    # plan name bubbles a FileNotFoundError to the dispatcher (rc=2)
    # before any log is created; we don't want a ghost run dir for an
    # invocation that never started.
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug=args.name,
        command="run",
        argv=list(sys.argv[1:]),
        plan_path=path,
        step_filter=args.step,
        flags={
            "mode": args.mode,
            "detail_grade": detail_grade,
            "dry_run": args.dry_run,
            "no_save": args.no_save,
            "no_walk": args.no_walk,
            "yes": args.yes,
            "allow_missing_parent": args.allow_missing_parent,
        },
    )
    # Stamp any decision recorded during this run with the run-log run_id
    # (step-1 telemetry ContextVar). Entered manually rather than via a
    # ``with`` to avoid re-indenting the whole run body; the finally below
    # resets it on every exit path, next to run_end.
    telemetry_scope = run_logger.telemetry_run_id_scope()
    telemetry_scope.__enter__()
    # Default the rc/outcome defensively so an unexpected escape path
    # still records a sensible terminal event.
    rc = 1
    err_msg: Optional[str] = None
    try:
        try:
            _resolve_iterative_budget(args)
        except CreateError as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return rc
        # Keep shared script flags compatible without promising a run loop.
        if getattr(args, "iterate", False):
            warn(
                f"--iterate has no effect on `plan-tool run` (mode={args.mode}); "
                "remove it. Reconciliation does not support --iterate."
            )

        # Capture the step title for a ``--commit`` subject BEFORE run_step's
        # mark-done write — run_step returns an empty step_title on green, and
        # reading it back after the write risks a title-less subject if the
        # file is momentarily unparseable. Mirrors the sweep's pre_step.title.
        # Best-effort: a bad step id / unparseable plan surfaces as run_step's
        # own error just below, so we never reach the commit with a bad title.
        commit_step_title = ""
        if commit_active:
            try:
                commit_step_title = resolve_step(parse_plan(path), args.step).title
            except (ParseError, ValidationError, LauncherError):
                commit_step_title = ""

        try:
            initial_backend_name = get_active_backend().name
            resume_token = set_rate_limit_resume_command_provider(
                lambda: _build_run_resume_command(
                    args, run_slug, initial_backend_name=initial_backend_name
                )
            )
            result = run_step(
                path,
                repo_root=ctx.repo_root,
                step_id=args.step,
                mode=args.mode,
                dry_run=args.dry_run,
                allow_missing_parent=args.allow_missing_parent,
                run_logger=run_logger,
                detail_grade=detail_grade,
            )
        except LauncherError as exc:
            err_msg = str(exc)
            error(str(exc))
            rc = 2
            return rc
        finally:
            reset_rate_limit_resume_command_provider(resume_token)

        if args.dry_run:
            rc = 0
            return rc

        if result.exit_code != 0:
            err_color = color_enabled(sys.stderr)
            print(
                paint(
                    f"✗ step {result.step_id} exited with code "
                    f"{result.exit_code}; plan not advanced.",
                    BOLD_RED,
                    enabled=err_color,
                ),
                file=sys.stderr,
            )
            _print_next_steps(
                "Try:",
                [
                    (
                        f"plan-tool runs list --slug {args.name}",
                        "inspect the run log for the failed call",
                    ),
                    (
                        # Carry the grade: replaying without it re-renders the
                        # run-grade prompt, not the one that failed.
                        f"plan-tool run {args.name} --step {result.step_id}"
                        f"{_grade_flag_suffix(args)} --dry-run",
                        "re-render the prompt without invoking claude",
                    ),
                    (
                        "plan-tool --debug run …",
                        "re-run with raw claude stream output for diagnosis",
                    ),
                ],
            )
            rc = result.exit_code
            return rc

        if args.mode != "run":
            summary = summarize_findings(result.stdout)
            verdict = format_findings_verdict(result.step_id, summary)
            print(f"mode '{args.mode}' finished for step {result.step_id}. Plan unchanged.")
            print(verdict)

            # The audit completed -- exit 0 even with critical findings.
            # The verdict line above is what a caller acts on; a critical
            # finding is a result to address, not a failure of the run
            # itself. A genuine non-zero claude exit is handled on the
            # branch above.
            rc = 0
            return rc

        # ``--archive`` (completing step): move the plan + rewrite the manifest
        # BEFORE the commit so the green commit's ``git add -A`` captures the
        # move + manifest edit — otherwise ``--commit --archive`` exits with a
        # dirty tree that blocks the next ``--commit``. ``archived`` lets the
        # plan_completed branch below skip re-archiving. See docs/how-to/pipeline/run.md.
        archived = False
        if getattr(args, "archive", False) and result.plan_completed:
            manifest_path = getattr(args, "manifest", None) or (
                default_manifest_path(ctx.repo_root)
            )
            _archive_on_completion(path, ctx=ctx, manifest_path=manifest_path)
            archived = True

        # ``--commit``: one commit for the green step at single-step scope too
        # (mirrors the ``--all`` sweep; was inert without ``--all``). Uses the
        # pre-run title (see above) and captures the archive move above when the
        # completing step was archived. See docs/how-to/pipeline/run.md.
        if commit_active and result.done:
            rc_commit, tail = _commit_green_step(
                ctx.repo_root,
                slug=args.name,
                step_id=result.step_id,
                step_title=commit_step_title,
            )
            if rc_commit != 0:
                err_msg = _green_commit_failure_msg(
                    rc_commit, result.step_id, tail, swept=False
                )
                error(err_msg)
                rc = rc_commit
                return rc

        out_color = color_enabled(sys.stdout)
        if result.advanced_to is not None:
            print(
                paint(
                    f"✓ step {result.step_id} done", BOLD_GREEN, enabled=out_color
                )
                + paint(
                    f" — advanced to step {result.advanced_to}",
                    DIM,
                    enabled=out_color,
                )
            )
            if getattr(args, "archive", False):
                # ``run --step N --archive`` on a non-terminal step: the
                # plan didn't complete, so there is nothing to archive.
                # Say so rather than silently doing nothing.
                print(
                    "--archive: the run advanced the plan but did not "
                    "complete the plan; nothing archived."
                )
            _print_next_steps(
                "Next steps:",
                [
                    (
                        f"plan-tool run {args.name}{_grade_flag_suffix(args)}",
                        f"execute step {result.advanced_to}",
                    ),
                    (
                        f"plan-tool status {args.name}",
                        "inspect plan progress",
                    ),
                ],
            )
        elif result.plan_completed:
            print(
                paint(
                    f"✓ step {result.step_id} done", BOLD_GREEN, enabled=out_color
                )
                + paint(
                    " — plan complete, status flipped to `completed`",
                    DIM,
                    enabled=out_color,
                )
            )
            if archived:
                # Already archived above (before the commit, so the green
                # commit captured the move + manifest edit);
                # ``_archive_on_completion`` printed the archived path and the
                # ``plan-tool register`` undo hint. Auto-archive intentionally
                # replaces the verify-all/sweep next-step hints (the file no
                # longer lives at ``path``).
                pass
            else:
                _print_next_steps(
                    "Next steps:",
                    [
                        (
                            f"plan-tool verify-all --rollup {args.name}",
                            "reconcile the whole plan against the current code (rollup)",
                        ),
                        (
                            "plan-tool sweep",
                            "archive this completed plan",
                        ),
                    ],
                )
        else:
            print(
                paint(
                    f"✓ step {result.step_id} done", BOLD_GREEN, enabled=out_color
                )
                + paint(" — no next runnable step", DIM, enabled=out_color)
            )
            if getattr(args, "archive", False):
                # A green step that neither advanced nor completed the plan
                # (e.g. remaining steps are blocked) leaves nothing to
                # archive — note it so ``--archive`` isn't silently inert.
                print(
                    "--archive: the run did not complete the plan; "
                    "nothing archived."
                )
            _print_next_steps(
                "Next steps:",
                [
                    (
                        f"plan-tool status {args.name}",
                        "inspect blocked/pending steps",
                    ),
                ],
            )
        rc = 0
        return rc
    except KeyboardInterrupt:
        # Record SIGINT in the run log before exiting; 130 is the POSIX
        # convention. ``raise SystemExit(130)`` (not a bare re-raise) is
        # what reaches a real process exit here — ``app.py``'s dispatcher
        # catches only ``Exception``, so an unconverted ``KeyboardInterrupt``
        # would hit Python's default handler instead: a raw traceback and
        # exit 1. ``SystemExit`` still runs the ``finally:`` below on its
        # way out, so the run-log record is unaffected.
        rc = 130
        err_msg = "interrupted"
        raise SystemExit(130)
    finally:
        try:
            run_logger.run_end(
                outcome=("success" if rc == 0 else "error"),
                rc=rc,
                error=err_msg,
            )
        finally:
            # Clear the telemetry run_id (restores the prior value) so it can't
            # leak into a later run or a non-run command. Its own `finally` so a
            # run_end failure (OSError / over-cap line) can't skip the reset.
            telemetry_scope.__exit__(None, None, None)


def _cmd_run_sweep(
    args: argparse.Namespace,
    *,
    ctx: PlanToolContext,
    plan_path: Path,
) -> int:
    """Controlling loop for ``plan-tool run <name> --all``.

    Resolves the next-runnable step, runs it via :func:`run_step`,
    and repeats until the plan completes, a step exits non-zero, or
    ``--max-steps`` is hit. Each iteration opens its own
    :class:`RunLogWriter` (one log per step, matching the per-``run``
    shape); the sweep itself produces no aggregating log.

    Halt-on-failure: a non-zero step exit ends the sweep and the
    sweep returns that step's exit code unchanged (no aggregation,
    no remapping; matches the single-step ``cmd_run`` contract).

    ``--all`` implies ``-y`` (a sweep that stalls waiting for input
    defeats the purpose) -- the helper mutates ``args.yes`` to make
    the per-iteration code paths see the override.

    Only ``--mode run`` is accepted. Other (review) modes return rc=2
    with a redirect to ``verify-all``. This keeps the execution path
    (``run --all``) and the audit path (``verify-all``)
    cleanly separated.
    """
    # Validate flag combinations BEFORE opening any log -- a ghost
    # run dir for a rejected invocation is worse than no log at all.
    if args.step is not None:
        error(
            "--all and --step are mutually exclusive "
            "(--all sweeps every runnable step; --step picks one)."
        )
        return 2

    if args.mode != "run":
        error(
            f"--all does not accept --mode {args.mode}. "
            f"Use `plan-tool verify-all <name> --mode "
            f"{args.mode}` instead -- the review path is "
            f"separate from the execution sweep."
        )
        return 2

    if args.max_steps is not None and args.max_steps < 1:
        error(f"--max-steps must be >= 1 (got {args.max_steps}).")
        return 2

    if getattr(args, "reconcile", False):
        # Execution and reconcile sweeps use different step-selection policies.
        error(
            "--all is mutually exclusive with --reconcile on 'run' "
            "(this --all sweeps runnable execution steps, not audit "
            "steps). Use `plan-tool reconcile-code <name> --all` for a "
            "reconcile sweep."
        )
        return 2

    # ``--commit`` requires a clean tree before the sweep: the
    # "one commit per green step" guarantee breaks if pre-existing
    # edits fold into the first step's commit (mirrors the harness's
    # clean-tree fail gate). Checked before any RunLogWriter opens,
    # consistent with the other rc=2 gates above. Skipped under
    # ``--dry-run`` (no step advances, so no commit happens).
    if getattr(args, "commit", False) and not args.dry_run:
        if _working_tree_dirty(ctx.repo_root):
            error(
                "--commit requires a clean working tree (commit or "
                "stash your changes first)."
            )
            return 2

    # Validate iteration budget once up front -- a bad value here
    # would fail every per-iteration call identically, so surfacing
    # it before the loop avoids spurious half-swept plans.
    try:
        _resolve_iterative_budget(args)
    except CreateError as exc:
        error(str(exc))
        return 2

    # Preflight gate (whole-plan): if any step lacks a detail file, warn
    # and confirm before the sweep starts. ``--all`` implies ``-y`` (set
    # just below), so this — reading the operator's *original* ``--yes`` —
    # is the one chance to ask. A non-interactive stdin proceeds with the
    # warning. Skipped under --dry-run (no claude call to ground).
    #
    # A non-default grade swaps that soft gate for the hard aggregated
    # artifact check over every step the sweep would run (see
    # ``_preflight_jira_grade_details``): one rc=2 naming every broken step,
    # before the first run log opens and under --dry-run too.
    detail_grade = _detail_grade(args)
    if detail_grade == GRADE_JIRA:
        problem = _preflight_jira_grade_details(
            plan_path,
            repo_root=ctx.repo_root,
            step_id=None,
            all_steps=True,
        )
        if problem is not None:
            error(problem)
            return 2
    elif not args.dry_run:
        if not _confirm_missing_step_details(
            plan_path,
            repo_root=ctx.repo_root,
            plan_name=args.name,
            step_id=None,
            all_steps=True,
            yes=args.yes,
        ):
            print("aborted: missing detail file(s).", file=sys.stderr)
            return 0

    # ``-y`` semantics implied: the per-step code paths read
    # ``args.yes`` directly, so flipping the attribute is the cleanest
    # way to propagate the override without touching every call site.
    args.yes = True

    # Resolve the manifest path once, only when ``--archive`` is set, so
    # each completed-plan archive reuses it and a non-archive sweep never
    # reads ``args.manifest`` (the gate-test namespace carries no manifest
    # field). The same precedence as ``cmd_sweep``: ``--manifest`` wins,
    # else the repo-anchored default.
    archive_manifest_path: Optional[Path] = None
    if getattr(args, "archive", False):
        archive_manifest_path = getattr(args, "manifest", None) or (
            default_manifest_path(ctx.repo_root)
        )

    steps_run = 0
    while True:
        if args.max_steps is not None and steps_run >= args.max_steps:
            print(
                f"sweep capped at --max-steps {args.max_steps}; "
                f"stopping. Re-run `plan-tool run {args.name}"
                f"{_grade_flag_suffix(args)} --all` "
                f"to continue.",
                file=sys.stderr,
            )
            return 0

        # Re-parse the plan each iteration because the previous
        # ``run_step`` mutated it (mark-done + advance + write).
        # ``resolve_step`` raises ``LauncherError`` when nothing
        # runnable remains -- that's the natural completion signal
        # for the sweep.
        try:
            text = plan_path.read_text(encoding="utf-8")
            if _fenced_code_spans(_strip_frontmatter(text)).unmatched_opening is not None:
                error(
                    f"{plan_path}: unmatched opening code fence; add a matching "
                    "closing fence before running this plan."
                )
                return 2
            plan = parse_plan(plan_path)
            pre_step = resolve_step(plan, None)
        except LauncherError:
            if steps_run == 0:
                print(
                    f"no runnable step in '{args.name}'; nothing "
                    f"to sweep.",
                    file=sys.stderr,
                )
            else:
                print(
                    f"sweep complete: {steps_run} step(s) advanced. "
                    f"No further runnable steps."
                )
            return 0
        except UnsupportedPlanFormatVersionError:
            raise
        except (ParseError, ValidationError) as exc:
            # Plan went bad mid-sweep (or was malformed to begin
            # with). Surface it and stop -- continuing past a parse
            # failure would just retry the same error.
            error(str(exc))
            return 2

        run_logger = RunLogWriter.start(
            repo_root=ctx.repo_root,
            slug=args.name,
            command="run",
            argv=list(sys.argv[1:]),
            plan_path=plan_path,
            step_filter=None,
            flags={
                "mode": args.mode,
                "detail_grade": detail_grade,
                "dry_run": args.dry_run,
                "no_save": args.no_save,
                "no_walk": args.no_walk,
                "yes": args.yes,
                "allow_missing_parent": args.allow_missing_parent,
                "all": True,
                "max_steps": args.max_steps,
                "sweep_index": steps_run,
            },
        )
        # Bind the telemetry run_id to this iteration's writer; each swept
        # step opens its own writer and clears its own scope in the finally
        # below, so one step's run_id is cleared before the next binds — no
        # leak across the sweep. Manual enter/exit avoids re-indenting the
        # per-iteration body (see cmd_run for the same pattern).
        telemetry_scope = run_logger.telemetry_run_id_scope()
        telemetry_scope.__enter__()
        rc = 1
        err_msg: Optional[str] = None
        try:
            # Recommend a detail file once per swept step before its
            # claude call (suppressed in --dry-run); the sweep is always
            # the execution mode, so the directive applies every step.
            # Skipped at a non-default grade — it reads ``Step.detail``,
            # which that grade does not execute from.
            if not args.dry_run and detail_grade == GRADE_DEFAULT:
                _warn_missing_step_detail(
                    plan_path,
                    repo_root=ctx.repo_root,
                    plan_name=args.name,
                    step_id=None,
                )

            try:
                result = run_step(
                    plan_path,
                    repo_root=ctx.repo_root,
                    step_id=None,
                    mode=args.mode,
                    dry_run=args.dry_run,
                    allow_missing_parent=args.allow_missing_parent,
                    run_logger=run_logger,
                    detail_grade=detail_grade,
                )
            except LauncherError as exc:
                # A LauncherError from run_step itself (e.g. preflight
                # failure) is a real error, not a "no runnable" --
                # the earlier resolve_step succeeded for this slot.
                err_msg = str(exc)
                error(str(exc))
                # Self-record the preflight halt against the step the
                # sweep already resolved for this slot (the native analog
                # of ``fail "plan-tool run exited non-zero"`` for a run
                # that can't even start). No-op without a ``lessons:``.
                _record_sweep_halt(
                    plan,
                    repo_root=ctx.repo_root,
                    step_id=pre_step.id,
                    reason=str(exc),
                )
                rc = 2
                return rc

            if args.dry_run:
                # In dry-run, ``run_step`` printed the prompt and
                # returned without invoking claude or advancing the
                # plan. Continuing the loop would re-render the same
                # step forever (no advance), so exit after one
                # iteration -- mirrors how single-step dry-run only
                # ever produces one prompt.
                rc = 0
                return rc

            if result.exit_code != 0:
                print(
                    f"step {result.step_id} exited with code "
                    f"{result.exit_code}; sweep halted, plan not "
                    f"advanced. {steps_run} step(s) completed "
                    f"before the failure.",
                    file=sys.stderr,
                )
                # Self-record the halt in the plan's lessons log (no-op
                # when the plan declares no ``lessons:``). Covers both
                # halt classes the title names: a backend run failure and
                # a per-step gate/test_command refusing advancement both
                # arrive here as ``result.exit_code != 0``.
                _record_sweep_halt(
                    plan,
                    repo_root=ctx.repo_root,
                    step_id=result.step_id,
                    reason=f"run failed (exit code {result.exit_code})",
                )
                rc = result.exit_code
                return rc

            if result.advanced_to is not None:
                print(
                    f"step {result.step_id} done. Advanced to step "
                    f"{result.advanced_to}."
                )
            else:
                print(
                    f"step {result.step_id} done. No next runnable "
                    f"step."
                )

            # ``--archive`` (completing step): move the plan to ``archive/`` +
            # deregister BEFORE the commit so the green commit's ``git add -A``
            # captures the move + manifest edit — otherwise ``--commit
            # --archive`` leaves them uncommitted, dirtying the tree and
            # blocking the next ``--commit``. Gate on ``result.plan_completed``
            # (the M/M signal), NOT ``advanced_to`` (None on the terminal step).
            # See docs/how-to/pipeline/run.md.
            plan_archived = (
                getattr(args, "archive", False) and result.plan_completed
            )
            if plan_archived:
                assert archive_manifest_path is not None
                _archive_on_completion(
                    plan_path,
                    ctx=ctx,
                    manifest_path=archive_manifest_path,
                )

            # ``--commit``: one git commit for the step just taken green. Gate
            # on ``result.done`` (not ``advanced_to``) so the terminal step
            # commits too. The title comes from ``pre_step`` (``run_step``
            # leaves ``RunResult.step_title`` empty on green). When the step
            # completed + archived above, this same commit captures the archive
            # move. A failed commit halts the sweep with the commit's rc,
            # leaving that step's work dirty for ``git reset`` recovery.
            if args.commit and result.done:
                rc_commit, tail = _commit_green_step(
                    ctx.repo_root,
                    slug=args.name,
                    step_id=result.step_id,
                    step_title=pre_step.title,
                )
                if rc_commit != 0:
                    err_msg = _green_commit_failure_msg(
                        rc_commit, result.step_id, tail, swept=True
                    )
                    error(err_msg)
                    rc = rc_commit
                    return rc

            # After archiving the completed plan, end the sweep: the next loop
            # iteration would ``parse_plan`` the now-moved file and raise an
            # uncaught ``FileNotFoundError``, so short-circuit with the
            # sweep-complete summary.
            if plan_archived:
                steps_run += 1
                print(
                    f"sweep complete: {steps_run} step(s) advanced. "
                    f"Plan complete."
                )
                rc = 0
                return rc

            rc = 0
            steps_run += 1
        except KeyboardInterrupt:
            # SystemExit (not a bare re-raise) is what reaches a real
            # process exit 130 here rather than Python's default
            # KeyboardInterrupt handler — see cmd_run's matching site.
            rc = 130
            err_msg = "interrupted"
            raise SystemExit(130)
        finally:
            try:
                run_logger.run_end(
                    outcome=("success" if rc == 0 else "error"),
                    rc=rc,
                    error=err_msg,
                )
            finally:
                # Clear this iteration's telemetry run_id before the next writer
                # binds, so no run_id leaks across swept steps or past the sweep.
                # Its own `finally` so a run_end failure can't skip the reset.
                telemetry_scope.__exit__(None, None, None)


def cmd_reconcile_code(args: argparse.Namespace) -> int:
    """Audit code against the plan and land code edits inline — ``reconcile-code``.

    The code-side counterpart to ``reconcile-plan``: where ``reconcile-plan``
    edits the *plan* to match the code, ``reconcile-code`` edits the *code* to
    match the plan (the plan is canonical). Findings whose root cause is in the
    plan are short-circuited with ``[REDIRECT]`` pointing at
    ``detail --reconcile``. Shares its entire implementation with the legacy
    ``run --reconcile`` form via :func:`_cmd_run_reconcile`.

    See ``docs/reference/contracts/process.md`` for the post-execution direction.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    return _cmd_run_reconcile(args, ctx=ctx, plan_path=path)


def register(subparsers) -> dict[str, Handler]:
    """Add the ``run`` + ``reconcile-code`` subparsers and their dispatch map.

    ``run`` declares ``parents=[yes_parent, iterate_parent]``; those parents
    currently originate in ``app.register``. Per the duplicate-then-defer
    rule, this command module — carved out before ``parser.py`` owns the
    shared parents — rebuilds its own verbatim copies (argparse ``parents=``
    copies actions by reference, so identical parent objects yield
    byte-identical ``run --help``). Consolidation into ``parser.py`` is
    deferred. ``AVAILABLE_MODES`` is imported lazily from the
    ``plan_tool.cli`` package surface (not ``app``) so this module keeps no
    import edge to ``app``.
    """
    from plan_tool.cli import AVAILABLE_MODES
    from plan_tool.convergence import (
        DEFAULT_ITERATION_BUDGET_SECONDS,
        DEFAULT_MAX_ITERATIONS,
        DEFAULT_MAX_STALL_ROUNDS,
    )

    sub = subparsers

    yes_parent = make_yes_parent()

    # Retain loop options for shared scripts; run never consumes a loop budget.
    iterate_parent = argparse.ArgumentParser(add_help=False)
    iterate_parent.add_argument(
        "--max-iterations",
        type=int,
        default=DEFAULT_MAX_ITERATIONS,
        dest="max_iterations",
        metavar="N",
        help="compatibility iteration count; no run loop executes. Existing value validation still applies.",
    )
    iterate_parent.add_argument(
        "--iteration-budget",
        type=int,
        default=DEFAULT_ITERATION_BUDGET_SECONDS,
        dest="iteration_budget",
        metavar="SECONDS",
        help="compatibility progress budget; run has no iteration deadline. Existing value validation still applies.",
    )
    iterate_parent.add_argument(
        "--time-budget",
        type=int,
        default=None,
        dest="time_budget",
        metavar="SECONDS",
        help="compatibility loop time budget; this option does not limit run execution time.",
    )
    iterate_parent.add_argument(
        "--max-stall-rounds",
        type=int,
        default=DEFAULT_MAX_STALL_ROUNDS,
        dest="max_stall_rounds",
        metavar="N",
        help="compatibility stall count; run has no iteration stall detector. Existing value validation still applies.",
    )
    iterate_parent.add_argument(
        "--allow-drift",
        action="store_true",
        dest="allow_drift",
        help="compatibility flag; run does not use an iteration live-edit drift guard.",
    )
    iterate_parent.add_argument(
        "--no-auto-reconcile-on-drift",
        action="store_false",
        dest="auto_reconcile_on_drift",
        default=True,
        help="compatibility flag; run has no iteration-triggered auto-reconcile pass.",
    )
    iterate_parent.add_argument(
        "--no-triage",
        action="store_false",
        dest="triage",
        default=True,
        help="compatibility flag; run has no iterative finding-apply triage.",
    )
    iterate_parent.add_argument(
        "--include-info",
        action="store_true",
        dest="include_info",
        default=False,
        help="compatibility flag; run does not auto-apply review findings.",
    )
    iterate_parent.add_argument(
        "--no-collision-sidecar",
        action="store_false",
        dest="collision_sidecar",
        default=True,
        help="compatibility flag; run has no iteration collision-sidecar pause.",
    )

    p_run = sub.add_parser(
        "run",
        help="execute a step via claude subprocess",
        parents=[yes_parent, iterate_parent],
    )
    p_run.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "no effect on run; retained for script compatibility. "
            "--reconcile rejects --iterate. Use separate reconcile-code "
            "invocations after reviewing and committing corrections."
        ),
    )
    # ``--reconcile`` switches ``run`` into a code-audit path (renders
    # prompts/run-reconcile.md, lands code edits inline via
    # acceptEdits, and short-circuits plan-rooted findings with
    # ``[REDIRECT]`` stderr). It is mutually exclusive with --mode
    # (the audit path always uses mode="run-reconcile") and with
    # --iterate (the new audit path does not iterate). Both mutex
    # checks live in ``cmd_run`` rather than an argparse mutually-
    # exclusive group because ``--mode`` has a default of ``"run"``
    # and argparse can't distinguish "user passed --mode run" from
    # "user passed nothing and got the default" without post-parse
    # inspection.
    p_run.add_argument(
        "--reconcile",
        action="store_true",
        help=(
            "legacy form of 'plan-tool reconcile-code' (kept working). "
            "Audit code against the plan (plan is canonical) and land "
            "code edits inline; findings whose root cause is in the "
            "plan are short-circuited with [REDIRECT] pointing at "
            "'plan-tool detail --reconcile'. Mutually exclusive with "
            "--mode and --iterate."
        ),
    )
    p_run.add_argument(
        "name",
        nargs="?",
        default=None,
        help=(
            "plan name — slug, filename stem (e.g. 1-my-feature), or "
            "filename.md. Omit (or pass a name that doesn't resolve) to "
            "pick interactively from the plans that still have open steps."
        ),
    )
    p_run.add_argument(
        "--step",
        type=int,
        default=None,
        help="run a specific step by id (default: current or next runnable)",
    )
    # ``--all`` sweeps every runnable step in one invocation. Implies
    # ``-y`` (a sweep that stalls waiting for input defeats the
    # purpose) and is mutually exclusive with ``--step N`` and with
    # any non-``run`` mode -- those validations live in ``cmd_run``
    # since argparse mutex groups can't co-exist with defaults like
    # ``--mode run``. Halts on the first non-zero step exit and
    # propagates that step's exit code.
    p_run.add_argument(
        "--all",
        action="store_true",
        dest="all",
        help=(
            "sweep every runnable step in one invocation. Loops "
            "`next runnable -> run` until the plan completes, a step "
            "exits non-zero, or --max-steps N is hit. Implies -y. "
            "Mutually exclusive with --step and review-mode --mode "
            "values; only --mode run (default) is accepted."
        ),
    )
    p_run.add_argument(
        "--accept",
        action="store_true",
        dest="accept",
        help=(
            "with --step N: mark a hand-fixed step done with no backend call. "
            "Requires a clean working tree apart from the plan file and its "
            "lessons log, runs the plan's test_command and the step's gate, "
            "and writes nothing unless all pass; then applies the ordinary "
            "done-and-advance and the lessons entry. With --commit, commits "
            "only the plan and lessons files. Refused unless the step is "
            "current and committed, and when nothing certifies it. Not "
            "combinable with --all, --reconcile, --dry-run, --archive, "
            "--detail-grade, or a review --mode (--iterate warns)."
        ),
    )
    p_run.add_argument(
        "--max-steps",
        type=int,
        default=None,
        dest="max_steps",
        metavar="N",
        help=(
            "for --all: cap the sweep at N steps (default: unlimited, "
            "bounded by plan length). Ignored without --all."
        ),
    )
    p_run.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help=(
            "after each step goes green, stage all changes (git add -A) and "
            "create one commit with subject "
            "'plan(<slug>): step N green — <title>'. Applies to execution "
            "(--mode run) at either scope (single-step or --all); requires a "
            "clean working tree up front; off by default. No-ops (with a "
            "warning) under --dry-run or review/--reconcile modes — nothing "
            "to commit."
        ),
    )
    p_run.add_argument(
        "--archive",
        action="store_true",
        dest="archive",
        help=(
            "for --all or a completing --step run: when the step takes "
            "the plan to N/N done, move it to archive/ (file + "
            "plan-details/) and deregister from the manifest, then print "
            "a 'plan-tool register' undo hint. Off by default."
        ),
    )
    p_run.add_argument(
        "--skip-merge-check",
        action="store_true",
        dest="skip_merge_check",
        help=(
            "skip the pre-run check that you are off the default branch and "
            "that the plan and every committed step's detail file are on its "
            "remote ref (origin/main). The check is on by default; a repo can "
            "turn it off with run.require_merged_plan=false in "
            ".plan-tool/config.json or PLAN_TOOL_REQUIRE_MERGED_PLAN=0."
        ),
    )
    p_run.add_argument(
        "--switch-branch",
        action="store_true",
        dest="switch_branch",
        help=(
            "for branch-aware repos: on an unowned branch whose plan expects "
            "a different branch, switch to (creating if missing) the plan's "
            "expected branch on a clean tree before running; refuses on a "
            "dirty tree. No effect when branch awareness is off."
        ),
    )
    p_run.add_argument(
        "--mode",
        choices=AVAILABLE_MODES,
        default="run",
        help=(
            "prompt mode (default: run). 'run' executes the step and advances "
            "the plan; other modes are read-only inspections that leave the "
            "plan unchanged. Review modes parse claude's `## Findings` block "
            "and print a verdict; a completed audit exits 0 even with "
            "CRITICAL findings."
        ),
    )
    # Grade is an *input* axis, deliberately separate from ``--mode``: the
    # public mode stays ``run`` at every grade, so the lifecycle (mark-done,
    # advance, the test-authoring gate) and the ``--all`` sweep's mode
    # allowlist are untouched.
    p_run.add_argument(
        "--detail-grade",
        choices=JIRA_GRADE_VALUES,
        default=GRADE_DEFAULT,
        dest="detail_grade",
        help=(
            f"which detail artifact the step executes from (default: "
            f"{GRADE_DEFAULT}). `{GRADE_JIRA}` reads the compact jira-grade "
            "artifacts under plan-details/<plan_slug>/jira/ and fails before "
            "any backend call — including under --dry-run — when one is "
            "missing or off-contract; the run-grade detail file is never "
            "substituted. Execution only: rejected with a review --mode or "
            "with --reconcile."
        ),
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="render the prompt and print it; do not invoke claude",
    )
    p_run.add_argument(
        "--allow-missing-parent",
        action="store_true",
        dest="allow_missing_parent",
        help=(
            "skip the pre-flight check that refuses steps whose declared "
            "files have a missing parent directory under the repo root. "
            "Use when the step legitimately creates files under a path "
            "that doesn't exist yet (e.g. a new module directory)."
        ),
    )
    p_run.add_argument(
        "--no-save",
        action="store_true",
        dest="no_save",
        help=(
            "for --reconcile: skip persisting the audit findings to "
            "plan-details/<slug>/reports/. Implies --no-walk. Has no "
            "effect otherwise."
        ),
    )
    p_run.add_argument(
        "--no-walk",
        action="store_true",
        dest="no_walk",
        help=(
            "for --reconcile: skip the interactive walk over the "
            "audit findings. The findings are still saved unless "
            "--no-save is also set. Has no effect otherwise."
        ),
    )
    p_run.add_argument(
        "--reuse",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="reuse",
        help=(
            "for --reconcile: reuse a saved run-reconcile's findings "
            "instead of running a fresh claude audit, when the save is "
            "fresh (plan AND code fingerprints still match). Default "
            "(unset): prompt interactively, auto-accepting under --yes / "
            "non-TTY stdin. --reuse always reuses a fresh save; --no-reuse "
            "always re-audits. A stale save is never reused — it declines "
            "to a fresh audit with a staleness note."
        ),
    )
    p_run.add_argument(
        "--reuse-id",
        default=None,
        dest="reuse_id",
        metavar="STEM",
        help=(
            "pin reuse to a specific saved run-reconcile by filename stem "
            "(the bare `<ts>` or full `<ts>-run-reconcile` form); default: "
            "newest matching save for this step. An unresolved id prints a "
            "note and falls back to a fresh audit."
        ),
    )

    # ``reconcile-code`` is the promoted, canonical form of ``run
    # --reconcile`` — the code-side counterpart to ``reconcile-plan``
    # (``reconcile-plan`` edits the plan to match the code; this edits the
    # code to match the plan). It shares ``_cmd_run_reconcile`` with the
    # legacy flag, which keeps working. Same flag surface as the
    # ``--reconcile`` path, plus ``--all`` for a standalone code-reconcile
    # sweep.
    p_reconcile_code = sub.add_parser(
        "reconcile-code",
        help=(
            "audit the code against the plan (plan is canonical) and land "
            "code edits inline; plan-rooted findings redirect to "
            "'detail --reconcile' (legacy form: 'run --reconcile')"
        ),
        parents=[yes_parent],
    )
    p_reconcile_code.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    reconcile_code_scope = p_reconcile_code.add_mutually_exclusive_group()
    reconcile_code_scope.add_argument(
        "--step",
        type=int,
        default=None,
        help="reconcile a specific step by id (default: current or next runnable)",
    )
    reconcile_code_scope.add_argument(
        "--all",
        action="store_true",
        help="reconcile every step in plan order (mutually exclusive with --step)",
    )
    p_reconcile_code.add_argument(
        "--dry-run",
        action="store_true",
        help="render the prompt and print it; do not invoke claude",
    )
    p_reconcile_code.add_argument(
        "--allow-missing-parent",
        action="store_true",
        dest="allow_missing_parent",
        help=(
            "skip the pre-flight check that refuses steps whose declared "
            "files have a missing parent directory under the repo root."
        ),
    )
    p_reconcile_code.add_argument(
        "--no-save",
        action="store_true",
        dest="no_save",
        help=(
            "skip persisting the audit findings to "
            "plan-details/<slug>/reports/. Implies --no-walk."
        ),
    )
    p_reconcile_code.add_argument(
        "--no-walk",
        action="store_true",
        dest="no_walk",
        help=(
            "skip the interactive walk over the audit findings. The "
            "findings are still saved unless --no-save is also set."
        ),
    )
    p_reconcile_code.add_argument(
        "--reuse",
        action=argparse.BooleanOptionalAction,
        default=None,
        dest="reuse",
        help=(
            "reuse a saved run-reconcile's findings instead of running a "
            "fresh claude audit, when the save is fresh (plan AND code "
            "fingerprints still match). Default (unset): prompt "
            "interactively, auto-accepting under --yes / non-TTY stdin. "
            "--reuse always reuses a fresh save; --no-reuse always "
            "re-audits. A stale save is never reused — it declines to a "
            "fresh audit with a staleness note."
        ),
    )
    p_reconcile_code.add_argument(
        "--reuse-id",
        default=None,
        dest="reuse_id",
        metavar="STEM",
        help=(
            "pin reuse to a specific saved run-reconcile by filename stem "
            "(the bare `<ts>` or full `<ts>-run-reconcile` form); default: "
            "newest matching save for this step. An unresolved id prints a "
            "note and falls back to a fresh audit. Not compatible with "
            "--all (a pinned save can't mean anything sensible across "
            "every step)."
        ),
    )

    return {"run": cmd_run, "reconcile-code": cmd_reconcile_code}
