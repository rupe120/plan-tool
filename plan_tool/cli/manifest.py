"""Manifest-mutation command module — the register / deregister / sweep verbs.

Holds the three manifest-mutating handlers (``cmd_register`` /
``cmd_deregister`` / ``cmd_sweep``) plus their target-resolution and
reporting helpers, and a :func:`register` that contributes their
subparsers to the shared ``add_subparsers`` action (see
:mod:`plan_tool.cli.parser`).

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`) and the
domain packages — never :mod:`plan_tool.cli.app`. ``app`` re-imports these
names back into its own namespace so the package surface stays intact. The
interactive-prompt helpers keep their ``import builtins`` body-local so the
characterization tests can drive them by patching ``builtins.input``.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from plan_tool.branch_binding import BranchBindingError, clear_binding, set_binding
from plan_tool.branch_ownership import OWNER_AD_HOC, OWNER_CONVENTION, branch_owner
from plan_tool.cli.console import _is_within
from plan_tool.cli.context import _load_context
from plan_tool.cli.gitcommit import (
    branch_exists,
    checkout_existing_branch,
    commit_all,
    create_and_checkout_branch,
    current_branch,
    list_branches,
    remote_collisions,
    warn_recommended_paths_ignored,
    working_tree_dirty,
)
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.create import CreateError, append_to_manifest, remove_from_manifest
from plan_tool.locator import (
    PlanToolContext,
    default_manifest_path,
    slug_from_filename,
)
from plan_tool.project_config import (
    branch_awareness_enabled,
    branch_prefixes,
    derive_branch,
)
from plan_tool.parser import ParseError, ValidationError, parse_plan
from plan_tool.style import error, info, success, warn
from plan_tool.sweep import (
    OrphanPlan,
    SweepClassification,
    SweepReport,
    discover_orphan_plans,
    sweep_plans,
    withdraw_plan,
)


def cmd_register(args: argparse.Namespace) -> int:
    """Adopt an on-disk plan file into the structured-plans manifest.

    Closes the asymmetry between ``create`` (which scans the filesystem
    for collisions) and the rest of the tool (which only sees manifest-
    registered plans): if you have a plan file on disk that isn't
    listed in ``structured_plans.json``, every other subcommand fails
    with "no plan matching … among registered plan entries". ``register``
    is the one verb that brings it in.

    Accepts a path (absolute or repo-relative) or a bare slug. Slug
    resolution scans the directories that already host registered
    plans, matching the same prefix-aware lookup ``create`` uses (the
    unprefixed form plus ``1-``/``2-``/``3-`` priority variants).

    Idempotent: re-registering a path that's already in the manifest
    prints ``already registered`` and exits 0. Rejects a path that
    doesn't parse as a structured plan — the manifest is supposed to
    list only valid plans.

    Read-only besides the manifest write; no claude call.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "register is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    target = _resolve_register_target(ctx, args.target)
    if target is None:
        error(
            f"no plan file matching {args.target!r}. "
            "Pass a path to the .md file or a slug that exists under one "
            "of the registered plan directories."
        )
        return 2

    try:
        parse_plan(target)
    except (ParseError, ValidationError) as exc:
        error(f"{target} is not a valid structured plan: {exc}")
        return 1

    mf = args.manifest or default_manifest_path(ctx.repo_root)
    try:
        rel = target.resolve().relative_to(ctx.repo_root.resolve())
    except ValueError:
        error(
            f"{target} is not inside repo root {ctx.repo_root}; "
            "manifest entries must be repo-relative."
        )
        return 2

    updated = append_to_manifest(mf, ctx.repo_root, target)
    if updated:
        print(f"registered {rel.as_posix()}")
    else:
        print(f"already registered {rel.as_posix()}")
    warn_recommended_paths_ignored(ctx.repo_root, warn)
    return 0


def _resolve_register_target(
    ctx: PlanToolContext, raw: str
) -> Optional[Path]:
    """Resolve the ``register`` argument to a concrete .md path.

    Tries, in order: literal path (absolute or repo-relative), then
    slug-based lookup in the parent directories of every already-
    registered entry. Returns ``None`` when nothing matches — the
    caller emits the user-facing error so the message can reference
    the original input.
    """
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = (ctx.repo_root / candidate)
    if candidate.is_file():
        return candidate.resolve()

    cleaned = raw.removesuffix(".md")
    if "/" in cleaned or "\\" in cleaned:
        # Looked like a path but didn't resolve — don't fall through to
        # slug mode and silently pick a same-named file elsewhere.
        return None

    filenames = [
        f"{cleaned}.md",
        f"1-{cleaned}.md",
        f"2-{cleaned}.md",
        f"3-{cleaned}.md",
    ]
    seen: set[Path] = set()
    for e in ctx.entries:
        parent = e.path.parent.resolve()
        if parent in seen:
            continue
        seen.add(parent)
        for fn in filenames:
            candidate = parent / fn
            if candidate.is_file():
                return candidate.resolve()
    return None


def cmd_deregister(args: argparse.Namespace) -> int:
    """Drop a plan from the structured-plans manifest (the inverse of
    :func:`cmd_register`).

    Removes the plan's repo-relative entry from ``structured_plans.json``
    so the rest of the tool stops seeing it. The plan file on disk is left
    untouched — this only edits the manifest. (To archive a *completed*
    plan and move its file, use :func:`cmd_sweep`.)

    Accepts a path (absolute or repo-relative) or a bare slug. Unlike
    ``register``, the target file need not exist or parse: pruning a stale
    entry whose file was deleted or a malformed plan you no longer want
    listed is a primary use case, so slug resolution also matches the
    known-missing entries ``list`` warns about.

    Deregistering a *path* that isn't in the manifest is a no-op: prints
    ``not registered`` and exits 0. A bare *slug* only resolves while the
    plan is still registered, so re-running the slug form after removal
    exits 2 (unresolvable target) — same shape ``register`` uses. No
    claude call.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "deregister is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    target = _resolve_deregister_target(ctx, args.target)
    if target is None:
        error(
            f"no registered plan matching {args.target!r}. "
            "Pass a path (absolute or repo-relative) or the slug of a "
            "registered plan — see 'plan-tool list'."
        )
        return 2

    mf = args.manifest or default_manifest_path(ctx.repo_root)
    try:
        rel = target.resolve().relative_to(ctx.repo_root.resolve())
    except ValueError:
        error(
            f"{target} is not inside repo root {ctx.repo_root}; "
            "manifest entries are repo-relative, so it can't be registered."
        )
        return 2

    if remove_from_manifest(mf, ctx.repo_root, target):
        print(f"deregistered {rel.as_posix()}")
        print("  (the plan file on disk was left in place)")
    else:
        print(f"not registered {rel.as_posix()}")
    return 0


def cmd_withdraw(args: argparse.Namespace) -> int:
    """Archive a plan that is being *abandoned* — as distinct from one that
    *completed* (:func:`cmd_sweep`) or that ``create`` superseded with a
    replacement.

    A withdrawal takes a plan through all four steps that used to be done by
    hand: move the plan file to ``<plan-dir>/archive/<stem>.withdrawn.md``,
    move its ``plan-details/<slug>/`` alongside it, prepend a dated
    ``> **Withdrawn ...** — <reason>`` header above the frontmatter, and
    deregister it from the manifest. ``--reason`` is required: an archived
    plan with no stated reason reads as completed to the next reader, which
    is the present-tense-history failure CLAUDE.md's "Documentation is
    forward-looking" section describes.

    Target resolution mirrors :func:`_resolve_deregister_target` exactly
    (path or slug; the file need not currently be registered — a plan
    abandoned before it was ever registered, or already deregistered by
    hand, is still withdrawable). Deregistering an unregistered target is
    reported, not treated as an error, matching ``deregister``'s own
    not-registered shape.

    Manifest-mode only — directory-mode (``--plans-dir`` /
    ``PLAN_TOOL_PLANS_DIR``) has no manifest to deregister from, the same
    refusal ``register``/``deregister``/``sweep`` already use.

    No claude call; never mutates outside the plan file / its plan-details /
    the manifest.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "withdraw is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    reason = (args.reason or "").strip()
    if not reason:
        error("withdraw requires --reason \"...\" — a withdrawal with no "
              "stated reason reads as completed to the next reader.")
        return 2

    target = _resolve_deregister_target(ctx, args.target)
    if target is None:
        error(
            f"no plan matching {args.target!r}. Pass a path (absolute or "
            "repo-relative) or the slug of a registered plan — see "
            "'plan-tool list'."
        )
        return 2

    if not target.is_file():
        error(f"{target} does not exist — nothing to withdraw.")
        return 2

    try:
        rel = target.resolve().relative_to(ctx.repo_root.resolve())
    except ValueError:
        error(
            f"{target} is not inside repo root {ctx.repo_root}; "
            "manifest entries are repo-relative, so it can't be withdrawn."
        )
        return 2

    slug = slug_from_filename(target)
    assert slug is not None  # default_to_stem=True guarantees non-None
    manifest_path = args.manifest or default_manifest_path(ctx.repo_root)
    outcome = withdraw_plan(
        target,
        slug=slug,
        reason=reason,
        manifest_path=manifest_path,
        repo_root=ctx.repo_root,
    )

    if outcome.archived_to is None:
        for msg in outcome.skipped:
            error(msg)
        return 2

    archived_rel = outcome.archived_to.resolve().relative_to(
        ctx.repo_root.resolve()
    )
    success(f"withdrawn {rel.as_posix()} -> {archived_rel.as_posix()}")
    for src, dst in outcome.plan_details_moved[:1]:
        details_rel = dst.parent.resolve().relative_to(ctx.repo_root.resolve())
        print(f"  plan-details moved to {details_rel.as_posix()}/")
    if outcome.deregistered:
        print("  deregistered from the manifest")
    else:
        print("  (was not registered; nothing to remove from the manifest)")
    for msg in outcome.skipped:
        warn(msg)
    return 0


def _resolve_deregister_target(
    ctx: PlanToolContext, raw: str
) -> Optional[Path]:
    """Resolve the ``deregister`` argument to a manifest entry's abs path.

    Unlike :func:`_resolve_register_target`, the file need not exist on
    disk — pruning a stale entry whose file was deleted is a core use
    case. Tries a literal path first (absolute or repo-relative, returned
    without an existence check), then a slug match against the registered
    entries *and* the known-missing manifest entries. Returns ``None``
    when nothing matches; the caller emits the user-facing error.
    """
    raw = raw.strip()
    if not raw:
        return None
    candidate = Path(raw)
    looks_like_path = (
        candidate.is_absolute()
        or "/" in raw
        or "\\" in raw
        or raw.endswith(".md")
    )
    if looks_like_path:
        if not candidate.is_absolute():
            candidate = ctx.repo_root / candidate
        return candidate.resolve()

    cleaned = raw.removesuffix(".md")
    for path in [e.path for e in ctx.entries] + list(ctx.missing_paths):
        if slug_from_filename(path) == cleaned:
            return path.resolve()
    return None


def cmd_attach_branch(args: argparse.Namespace) -> int:
    """Attach a registered plan to an ad-hoc branch override (set the binding).

    Records the optional plan→branch override that overrides the slug-
    derived ``expected_branch`` (see :mod:`plan_tool.branch_binding`). The
    override lives in untracked local git config, never in the manifest, so
    this verb reads :class:`PlanToolContext` only to resolve the plan and the
    already-registered slug set — it writes no manifest entry.

    Refuses non-zero (rc 2) before any branch read when branch awareness is
    off (every repo by default), the same flag-check-first rule the run guard
    and the create gate apply.

    The protected behavior is the convention-namespace collision: binding
    plan P to a branch that is registered plan R's reserved
    ``<prefix><slug>`` name would let two plans claim one branch. Rather than
    do that, ``attach-branch`` strong-warns and — on consent (``-y`` or an
    interactive yes) and a clean tree — re-homes: it branches P's own
    ``derive_branch`` name *from the colliding branch* (carrying the work)
    and binds P to that instead. An *explicit* ad-hoc binding held by another
    plan is a hard refuse (no re-home) — the operator resolves that.

    No claude call; every refusal-capable check runs before any git mutation,
    so a rejected request leaves no orphan branch or binding.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "attach-branch is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    if not branch_awareness_enabled(ctx.repo_root):
        error(
            "branch awareness is disabled; enable it in .plan-tool/config.json "
            "(or set PLAN_TOOL_BRANCH_AWARENESS=1)."
        )
        return 2

    target = _resolve_register_target(ctx, args.plan)
    if target is None:
        error(
            f"no plan file matching {args.plan!r}. "
            "Pass a path to the .md file or a slug that exists under one "
            "of the registered plan directories."
        )
        return 2
    slug = slug_from_filename(target)

    branch = args.branch.strip()
    if not branch:
        error("branch name is required.")
        return 2

    # The override is stored verbatim — git enforces ref validity at checkout
    # time, so an arbitrary override like ``JIRA-1`` (no ``/``) is legal and
    # must not be rejected by the derived-name ``_is_valid_ref`` rule.
    prefixes = branch_prefixes(ctx.repo_root)
    registered = {e.slug for e in ctx.entries}
    owner = branch_owner(ctx.repo_root, branch, registered, prefixes)

    if owner is None or owner.slug == slug:
        # No collision (or the branch is already this plan's): bind directly.
        # ``set_binding`` writes git config, not the working tree, so the
        # plain bind needs no clean-tree gate.
        if owner is None:
            # No local owner — but the override name may already be claimed
            # only as a pushed remote-tracking ref. Read the offline ref list
            # once (no network) and warn-and-proceed if so; a pure advisory
            # tier, no block and no re-home (contrast the convention re-home
            # path below). Self-owned re-attach (owner.slug == slug) skips
            # this: a remote collision on a name you already own is noise.
            collisions = remote_collisions(
                list_branches(ctx.repo_root), branch, prefixes
            )
            if collisions:
                warn(
                    f"{branch} already exists on the remote as "
                    f"{', '.join(collisions)} (as of your last fetch — no "
                    f"network performed); run 'git fetch' to refresh. "
                    f"Binding anyway."
                )
        try:
            set_binding(ctx.repo_root, slug, branch)
        except BranchBindingError as exc:
            error(str(exc))
            return 1
        success(f"bound {slug} → {branch}")
        return 0

    if owner.kind == OWNER_AD_HOC:
        # Another plan holds an explicit binding to this branch — a one-branch-
        # per-plan desync the user must resolve, not auto-rewrite. No re-home.
        error(
            f"{branch} is already attached to plan {owner.slug!r}; run "
            f"'detach-branch {owner.slug}' first or choose another branch."
        )
        return 2

    # owner.kind == OWNER_CONVENTION and owner.slug != slug → re-home path.
    warn(
        f"{branch} is the convention branch of registered plan "
        f"{owner.slug!r}; attaching {slug} there would let two plans claim it."
    )

    if not args.yes:
        if not sys.stdin.isatty():
            print(
                f"re-run with -y to re-home {slug} onto its own branch "
                f"from {branch}",
                file=sys.stderr,
            )
            return 2
        import builtins

        try:
            answer = (
                builtins.input(
                    f"Re-home {slug} onto its own branch from {branch}? [y/N]: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n  left unchanged.", file=sys.stderr)
            return 2
        if answer not in ("y", "yes"):
            print("  left unchanged.", file=sys.stderr)
            return 2

    if working_tree_dirty(ctx.repo_root):
        error("re-home needs a clean working tree (commit or stash first).")
        return 2

    rehome = derive_branch(slug, prefixes)
    # Capture the branch attach-branch was run on first, so a mid-composition
    # failure can restore the developer rather than strand them.
    invocation = current_branch(ctx.repo_root)

    if branch_exists(ctx.repo_root, rehome):
        # The plan's own branch already exists — switch to it; nothing to carry.
        rc, tail = checkout_existing_branch(ctx.repo_root, rehome)
    elif branch_exists(ctx.repo_root, branch):
        # Switch to the colliding branch first, then branch the re-home name
        # from its HEAD so the work carries over.
        rc, tail = checkout_existing_branch(ctx.repo_root, branch)
        if rc == 0:
            rc, tail = create_and_checkout_branch(ctx.repo_root, rehome)
    else:
        # The colliding name is a registered plan's convention name but not a
        # local branch — nothing to carry; create rehome from current HEAD.
        rc, tail = create_and_checkout_branch(ctx.repo_root, rehome)
        tail = tail or f"no local {branch} to carry from"

    if rc != 0:
        # The ``elif`` create can fail after its switch already moved off
        # ``invocation``; best-effort-restore so the developer is never
        # stranded on the colliding branch. No binding persisted.
        if invocation and invocation != current_branch(ctx.repo_root):
            checkout_existing_branch(ctx.repo_root, invocation)
        error(f"{tail}; restored branch {invocation}")
        return 2

    try:
        set_binding(ctx.repo_root, slug, rehome)
    except BranchBindingError as exc:
        error(str(exc))
        return 1
    success(f"re-homed {slug} → {rehome} (from {branch})")
    return 0


def cmd_detach_branch(args: argparse.Namespace) -> int:
    """Detach a registered plan from its ad-hoc branch override (clear it).

    Clears the plan→branch override (see :mod:`plan_tool.branch_binding`) so
    the plan falls back to its slug-derived branch name. Refuses non-zero (rc
    2) before any branch read when branch awareness is off, the same flag-
    check-first rule :func:`cmd_attach_branch` applies.

    Quiet and idempotent: clearing a plan that has no override is a satisfied
    no-op (still rc 0). **Never deletes the branch** — the branch on disk is
    left in place; only the override is removed. No claude call.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "detach-branch is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    if not branch_awareness_enabled(ctx.repo_root):
        error(
            "branch awareness is disabled; enable it in .plan-tool/config.json "
            "(or set PLAN_TOOL_BRANCH_AWARENESS=1)."
        )
        return 2

    target = _resolve_deregister_target(ctx, args.plan)
    if target is None:
        error(
            f"no registered plan matching {args.plan!r}. "
            "Pass a path (absolute or repo-relative) or the slug of a "
            "registered plan — see 'plan-tool list'."
        )
        return 2
    slug = slug_from_filename(target)

    if clear_binding(ctx.repo_root, slug):
        success(
            f"cleared branch override for {slug} "
            "(the branch on disk was left in place)"
        )
    else:
        info(f"no branch override to clear for {slug}")
    return 0


def cmd_sweep(args: argparse.Namespace) -> int:
    """Sweep registered plans: archive completed ones, report on the rest.

    Intent: collapse the steady-state housekeeping a long-lived plan
    list accumulates. A plan whose top-level ``status: completed``
    AND every step ``status: done`` is moved to ``<plan-dir>/archive/``
    and removed from ``structured_plans.json``. Everything else
    (planning / in-progress / blocked / malformed) lands in a static
    summary so the operator can see what's outstanding without
    opening each file individually.

    Registered plans whose files no longer exist on disk are reported
    as ``missing`` and the operator is offered the chance to prune those
    stale manifest entries (see :func:`_prompt_remove_missing` for the
    -y / TTY / dry-run contract).

    The inverse blind spot is covered too: valid plan files sitting in
    registered-plan directories that the manifest doesn't list are reported as
    ``unregistered``. Sweep only reports them; ``plan-tool register <path>``
    remains the explicit adoption operation.

    Flags:

    - ``--dry-run`` reports what WOULD be archived (and which missing
      entries WOULD be pruned) without touching disk or the manifest.
      Pairs with the report so a user can preview the destructive half
      of the command before running for real.
    - ``--report-only`` skips the archive pass AND the missing-entry
      prune entirely; only the partial-status report is printed. Useful
      as a quick "where am I across all plans" check during planning.

    Manifest-mode only — directory-mode (``--plans-dir`` /
    ``PLAN_TOOL_PLANS_DIR``) has no manifest to deregister from, so
    the command refuses early with the same shape ``register`` uses.

    No claude call; never mutates outside the plan files / their
    plan-details / the manifest.
    """
    ctx = _load_context(args)
    if ctx.plans_dir is not None:
        error(
            "sweep is a manifest-mode command; "
            "drop --plans-dir / PLAN_TOOL_PLANS_DIR to use it."
        )
        return 2

    # ``--commit`` gates up front: it commits the archival/manifest edits
    # the sweep itself produces, so a mode that writes nothing (--dry-run,
    # --report-only) has nothing to commit, and a dirty tree would fold
    # unrelated work into the sweep commit. Refuse both before mutating.
    if getattr(args, "commit", False):
        if args.dry_run or args.report_only:
            error(
                "--commit has nothing to commit with --dry-run / "
                "--report-only (those modes write nothing)."
            )
            return 2
        if working_tree_dirty(ctx.repo_root):
            error(
                "--commit requires a clean working tree (commit or stash "
                "your changes first) so the sweep commit captures only the "
                "archived plans and manifest edits."
            )
            return 2

    manifest_path = args.manifest or default_manifest_path(ctx.repo_root)
    report = sweep_plans(
        ctx.entries,
        manifest_path=manifest_path,
        repo_root=ctx.repo_root,
        dry_run=args.dry_run,
        archive=not args.report_only,
    )

    # Read-only discovery. Reporting an unregistered file must not turn a
    # sweep into an implicit registration operation, including under ``-y``.
    orphans = discover_orphan_plans(ctx.entries, ctx.missing_paths)

    duplicate_archive_results: list[tuple[Path, Path]] = []
    if ctx.duplicate_paths and getattr(args, "archive_duplicates", False):
        duplicate_archive_results = _archive_duplicate_plans(
            ctx.duplicate_paths, dry_run=args.dry_run
        )

    _print_sweep_report(
        report,
        ctx=ctx,
        manifest_path=manifest_path,
        report_only=args.report_only,
        duplicate_archive_results=duplicate_archive_results,
        duplicates_archived=getattr(args, "archive_duplicates", False),
        orphans=orphans,
    )

    # Missing entries remain sweep-owned housekeeping. Unregistered plans
    # above are report-only and must go through the explicit ``register`` verb.
    if not args.report_only:
        _prompt_remove_missing(
            ctx.missing_paths,
            manifest_path=manifest_path,
            repo_root=ctx.repo_root,
            dry_run=args.dry_run,
            yes=args.yes,
        )

    # ``--commit``: stage and commit exactly the sweep's own mutations —
    # the archived plan files, their moved plan-details, and the manifest
    # edits (archives + missing-entry deregistrations). The clean-tree gate ran up
    # front, so a dirty tree here is the sweep's doing; a clean tree means
    # the sweep moved nothing (no completed plans, no orphans/missing),
    # leaving nothing to commit.
    if getattr(args, "commit", False):
        if working_tree_dirty(ctx.repo_root):
            n_archived = sum(
                1 for o in report.archived if o.archived_to is not None
            )
            commit_rc, tail = commit_all(
                ctx.repo_root, _sweep_commit_subject(n_archived)
            )
            if commit_rc == 0:
                success("committed sweep changes")
            else:
                error(f"git commit failed (rc={commit_rc})")
                if tail:
                    error(tail)
                return 1
        else:
            info("--commit: nothing to commit (sweep moved nothing)")

    # The sweep completed -- exit 0 even when some plans were skipped or
    # malformed. Those are findings the printed report surfaces (skipped
    # archives, malformed plans) for the operator to act on, not a
    # failure of the sweep itself. Non-zero is reserved for a run that
    # couldn't proceed (e.g. directory-mode refusal above, rc 2).
    return 0


def _sweep_commit_subject(n_archived: int) -> str:
    """Commit subject for a ``sweep --commit`` run.

    Leads with the archived-plan count (sweep's primary action); a run
    that archived nothing but still mutated — a missing-entry prune — gets the
    generic manifest-hygiene subject.
    """
    if n_archived > 0:
        plural = "plan" if n_archived == 1 else "plans"
        return f"sweep: archive {n_archived} completed {plural}"
    return "sweep: manifest hygiene"


def _archive_duplicate_plans(
    duplicates: list[Path], *, dry_run: bool
) -> list[tuple[Path, Path]]:
    """Move each duplicate to ``archive/`` beside its parent directory.

    Returns ``(source, destination)`` pairs. Best-effort: a duplicate
    that fails to move (e.g. permission denied) is silently skipped so
    one bad path doesn't abort the rest. When ``dry_run`` is True, no
    filesystem changes happen but the planned destinations are still
    returned for reporting.
    """
    results: list[tuple[Path, Path]] = []
    for src in duplicates:
        dest_dir = src.parent / "archive"
        dest = dest_dir / src.name
        if not dry_run:
            try:
                dest_dir.mkdir(parents=True, exist_ok=True)
                src.rename(dest)
            except OSError:
                continue
        results.append((src, dest))
    return results


def _prompt_remove_missing(
    missing: list[Path],
    *,
    manifest_path: Path,
    repo_root: Path,
    dry_run: bool,
    yes: bool,
) -> None:
    """Offer to deregister manifest entries whose files no longer exist.

    Called after the sweep report has already listed the missing paths,
    so this only handles the decision + the manifest write. Contract
    mirrors the rest of sweep:

    - ``--dry-run`` reports what WOULD be removed and writes nothing.
    - ``-y`` removes without prompting; a non-interactive run *without*
      ``-y`` leaves the entries in place and prints a hint, so an
      unattended sweep never silently rewrites the manifest.
    - an interactive TTY without ``-y`` prompts ``[y/N]`` defaulting to
      keep — deregistration is one-way (re-adding needs ``register``).

    Best-effort per entry: a manifest-write failure on one path is
    reported and the rest still proceed.
    """
    if not missing:
        return
    n = len(missing)
    noun = "entry" if n == 1 else "entries"

    if dry_run:
        print()
        print(f"would remove {n} missing {noun} from the manifest (--dry-run)")
        return

    if not yes:
        if not sys.stdin.isatty():
            print()
            print(
                f"{n} missing {noun} left in the manifest; re-run with -y "
                "(or `plan-tool deregister <slug>`) to prune.",
                file=sys.stderr,
            )
            return
        import builtins

        print()
        try:
            answer = (
                builtins.input(
                    f"Remove {n} missing {noun} from the manifest? [y/N]: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print("\n  cancelled — manifest left unchanged.", file=sys.stderr)
            return
        if answer not in ("y", "yes"):
            print("  kept — manifest left unchanged.", file=sys.stderr)
            return

    removed: list[Path] = []
    for p in missing:
        try:
            if remove_from_manifest(manifest_path, repo_root, p):
                removed.append(p)
        except CreateError as exc:
            print(f"  ! could not deregister {p}: {exc}", file=sys.stderr)

    print()
    print(
        f"removed {len(removed)} missing "
        f"{'entry' if len(removed) == 1 else 'entries'} from the manifest:"
    )
    for p in removed:
        try:
            display = p.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            display = str(p)
        print(f"  - {display}")


def _print_sweep_report(
    report: SweepReport,
    *,
    ctx: PlanToolContext,
    manifest_path: Path,
    report_only: bool,
    duplicate_archive_results: Optional[list[tuple[Path, Path]]] = None,
    duplicates_archived: bool = False,
    orphans: Optional[list[OrphanPlan]] = None,
) -> None:
    """Render :func:`cmd_sweep`'s output to stdout.

    Sections are each printed only when non-empty so a clean sweep
    of a tidy manifest stays terse. The headline counts come first so
    the operator can tell at a glance whether anything moved.
    """
    orphans = orphans or []
    completed_n = len(report.completed)
    partial_n = len(report.partial)
    malformed_n = len(report.malformed)
    missing_n = len(ctx.missing_paths)
    unregistered_n = len(orphans)

    if report.dry_run:
        prefix = "sweep (dry-run): "
        archive_verb = "would archive"
    elif report_only:
        prefix = "sweep (report-only): "
        archive_verb = "completed (not archived)"
    else:
        prefix = "sweep: "
        archive_verb = "archived"

    parts = [f"{completed_n} {archive_verb}"]
    parts.append(f"{partial_n} partial")
    if malformed_n:
        parts.append(f"{malformed_n} malformed")
    if missing_n:
        parts.append(f"{missing_n} missing")
    if unregistered_n:
        parts.append(f"{unregistered_n} unregistered")
    print(prefix + ", ".join(parts))
    print(f"  manifest: {manifest_path}")

    if report.archived:
        print()
        print(
            "archived:" if not report.dry_run else "would archive:"
        )
        for outcome in report.archived:
            target = (
                outcome.archived_to.relative_to(ctx.repo_root)
                if outcome.archived_to
                and _is_within(outcome.archived_to, ctx.repo_root)
                else outcome.archived_to
            )
            print(f"  - {outcome.slug} → {target}")
            for skipped in outcome.skipped:
                print(f"      ! {skipped}", file=sys.stderr)

    if report.partial:
        print()
        print(f"partial ({partial_n}):")
        for c in report.partial:
            _print_partial_classification(c)

    if report.malformed:
        print()
        print(f"malformed ({malformed_n}):")
        for c in report.malformed:
            print(f"  - {c.entry.path.name}: {c.parse_error}")

    if ctx.missing_paths:
        print()
        print(f"missing ({missing_n}):")
        for p in ctx.missing_paths:
            try:
                rel = p.resolve().relative_to(ctx.repo_root.resolve())
                display = rel.as_posix()
            except ValueError:
                display = str(p)
            print(f"  - {display}")

    if orphans:
        print()
        print(
            f"unregistered ({unregistered_n}) — plan files on disk "
            "the manifest doesn't list:"
        )
        for o in orphans:
            try:
                rel = o.path.resolve().relative_to(ctx.repo_root.resolve())
                display = rel.as_posix()
            except ValueError:
                display = str(o.path)
            if o.error:
                print(f"  - {display}: invalid, will not be registered — {o.error}")
            else:
                print(f"  - {display}")
        if any(o.plan is not None for o in orphans):
            print(
                "  hint: register an intended plan explicitly with "
                "`plan-tool register <path>`"
            )

    if ctx.duplicate_paths:
        print()
        dup_n = len(ctx.duplicate_paths)
        print(f"duplicates ({dup_n}) — same plan file exists under other candidate repo roots:")
        for p in ctx.duplicate_paths:
            print(f"  - {p}")
        if duplicates_archived and duplicate_archive_results:
            print()
            verb = "would archive" if report.dry_run else "archived duplicates"
            print(f"{verb}:")
            for src, dest in duplicate_archive_results:
                print(f"  - {src} → {dest}")
        elif not duplicates_archived:
            print(
                "  hint: pass --archive-duplicates to move these into "
                "an `archive/` subdirectory beside each duplicate"
            )


def _print_partial_classification(c: SweepClassification) -> None:
    """Render one partial-plan block for the sweep report."""
    assert c.counts is not None  # report.partial filters out malformed
    plan = c.entry.plan
    assert plan is not None  # ditto
    last_mod = datetime.fromtimestamp(c.last_modified).strftime("%Y-%m-%d")
    print(
        f"  - {c.entry.slug:<45} "
        f"({plan.status.value}, {c.counts.done}/{c.counts.total} done, "
        f"{c.counts.percent_done}%)"
    )
    print(f"      last edited {last_mod}")
    if c.in_progress_titles:
        for title in c.in_progress_titles:
            print(f"      in progress: {title}")
    if c.counts.deferred:
        print(f"      deferred steps: {c.counts.deferred}")


def register(subparsers) -> dict[str, Handler]:
    """Add the manifest-mutation subparsers and return their dispatch map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    p_register = sub.add_parser(
        "register",
        help=(
            "adopt an on-disk plan file into the structured-plans "
            "manifest (path or slug accepted)"
        ),
        parents=[yes_parent],
    )
    p_register.add_argument(
        "target",
        help=(
            "path to the plan file (absolute or repo-relative), or a "
            "bare slug to look up under directories that already host "
            "registered plans"
        ),
    )

    p_deregister = sub.add_parser(
        "deregister",
        help=(
            "remove a plan from the structured-plans manifest "
            "(path or slug accepted; leaves the file on disk)"
        ),
        parents=[yes_parent],
    )
    p_deregister.add_argument(
        "target",
        help=(
            "path to the plan file (absolute or repo-relative), or the "
            "slug of a registered plan. The file need not exist — stale "
            "entries pointing at deleted files can be pruned this way."
        ),
    )

    p_sweep = sub.add_parser(
        "sweep",
        help=(
            "archive completed plans (top-level status: completed AND "
            "all steps done), report on partially implemented plans, "
            "offer to prune manifest entries whose files no longer "
            "exist, and report unregistered plan files found beside "
            "registered plans"
        ),
        parents=[yes_parent],
    )
    p_sweep.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "report what WOULD be archived without touching disk or "
            "the manifest"
        ),
    )
    p_sweep.add_argument(
        "--report-only",
        action="store_true",
        help=(
            "skip the archive pass entirely; print only the partial-"
            "status report"
        ),
    )
    p_sweep.add_argument(
        "--archive-duplicates",
        action="store_true",
        help=(
            "move duplicate plan files discovered under non-selected "
            "candidate repo roots to an `archive/` subdirectory beside "
            "each duplicate. Use this after auto-discovery surfaces "
            "stale copies from a forgotten checkout or pre-move "
            "location. Requires -y for non-interactive runs."
        ),
    )
    p_sweep.add_argument(
        "--commit",
        action="store_true",
        dest="commit",
        help=(
            "after sweeping, stage all changes (git add -A) and create one "
            "commit for the archived plans + manifest edits (subject "
            "'sweep: archive N completed plans'). Requires a clean working "
            "tree up front; incompatible with --dry-run / --report-only; "
            "off by default; only commits when the sweep moved something."
        ),
    )

    p_withdraw = sub.add_parser(
        "withdraw",
        help=(
            "archive a plan being abandoned, as distinct from one that "
            "completed (sweep) or was superseded (create): moves the file "
            "to archive/<stem>.withdrawn.md, moves its plan-details "
            "alongside it, prepends a dated reason header, and "
            "deregisters it"
        ),
        parents=[yes_parent],
    )
    p_withdraw.add_argument(
        "target",
        help=(
            "path to the plan file (absolute or repo-relative), or a "
            "bare slug. Need not currently be registered."
        ),
    )
    p_withdraw.add_argument(
        "--reason",
        required=True,
        help=(
            "why this plan is being withdrawn — required. An archived "
            "plan with no stated reason reads as completed to the next "
            "reader."
        ),
    )

    p_attach = sub.add_parser(
        "attach-branch",
        help=(
            "attach a registered plan to an ad-hoc branch (untracked local "
            "git-config override; refuses unless branch awareness is enabled; "
            "re-homes the plan onto its own branch on a convention-name "
            "collision)"
        ),
        parents=[yes_parent],
    )
    p_attach.add_argument(
        "plan",
        help="path or slug of a registered plan",
    )
    p_attach.add_argument(
        "branch",
        help=(
            "branch to attach (arbitrary; stored as an untracked "
            "local-git-config override)"
        ),
    )

    p_detach = sub.add_parser(
        "detach-branch",
        help=(
            "clear a registered plan's ad-hoc branch override (refuses unless "
            "branch awareness is enabled; leaves the branch on disk in place)"
        ),
    )
    p_detach.add_argument(
        "plan",
        help="path or slug of a registered plan",
    )

    return {
        "register": cmd_register,
        "deregister": cmd_deregister,
        "sweep": cmd_sweep,
        "withdraw": cmd_withdraw,
        "attach-branch": cmd_attach_branch,
        "detach-branch": cmd_detach_branch,
    }
