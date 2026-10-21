"""``worktree`` command group — provision, inspect, and tear down per-plan workspaces.

Four verbs: ``worktree add <plan>`` provisions (or reuses) an isolated
workspace at the plan's deterministic per-slug path on the plan's branch,
``worktree list`` reports every registered plan's workspace (kind / branch /
path / dirty state), ``worktree remove <plan>`` deletes one plan's *worktree*
(a *clone* is never deleted — plan-tool surfaces a manual-cleanup message),
and ``worktree prune`` sweeps dead (deregistered / path-gone) plan-tool
worktrees. The module composes the step-1 git primitives
(``worktree_add`` / ``worktree_list`` / ``worktree_remove`` /
``worktree_prune`` / ``clone_repo``) with the step-2 pure path/target leaf
(``derive_worktree_path`` / ``classify_target`` / ``worktree_base``) and the
branch-awareness name helpers, adding the impure glue those leaves left out:
branch resolution, start-point resolution, the reuse-vs-fail tiebreak at the
derived path, kind dispatch in ``list``, and the clean-tree pre-gate +
confirmation policy the policy-free destructive primitives leave to the caller.

The destructive-verb safety rules: ``remove`` refuses a dirty worktree unless
``--force`` and refuses the workspace you are standing in with a clean message
(never git's raw ``fatal:``); ``prune`` never deletes a dirty workspace *even
under* ``-y`` — it surfaces it for an explicit ``remove --force`` instead, so
prune can't become a data-loss backdoor around the dirty gate. Neither verb
deletes the branch born inside the workspace (out of scope by plan decision).

The load-bearing rule: the branch is *born inside* the provisioning call
(``worktree add -b`` / an in-clone ``switch -c``), never a main-tree
``switch -c`` first — git refuses to check the same branch out in two trees.
Branch and start-point are always defined, so a bare ``worktree add <plan>``
works on a local-only repo with no remote (``default_branch`` → ``None`` →
``"HEAD"``).

Cycle-free per-intent command module: imports only leaves
(``context`` / ``parser`` / ``locator`` / ``worktree`` / ``gitcommit`` /
``project_config`` / ``style``) and never ``plan_tool.cli.app``.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional

from plan_tool.cli.context import _load_context
from plan_tool.cli.gitcommit import (
    WorktreeEntry,
    branch_exists,
    clone_repo,
    current_branch,
    default_branch,
    working_tree_dirty,
    worktree_add,
    worktree_list,
    worktree_prune,
    worktree_remove,
)
from plan_tool.cli.parser import Handler
from plan_tool.locator import resolve_plan_for_context, slug_from_filename
from plan_tool.project_config import (
    branch_awareness_enabled,
    branch_prefixes,
    derive_branch,
)
from plan_tool.style import error, info, success, warn
from plan_tool.worktree import (
    TargetState,
    classify_target,
    derive_worktree_path,
    worktree_base,
)


def _resolve_branch(repo_root: Path, slug: str, explicit: Optional[str]) -> str:
    """Return an always-defined branch name for this plan's workspace.

    Precedence: an explicit ``--branch`` wins; else, when branch-awareness is
    ON, the canonical ``derive_branch`` name (``prefixes[0] + slug``); else the
    slug-derived fallback (the project default, branch-awareness OFF). Never
    returns empty — ``branch_prefixes`` defaults to a non-empty list, so
    ``derive_branch`` never indexes an empty sequence.
    """
    if explicit:
        return explicit
    if branch_awareness_enabled(repo_root):
        return derive_branch(slug, branch_prefixes(repo_root))
    return slug


def _resolve_start_point(repo_root: Path) -> str:
    """Return an always-defined start point for a newly-born branch.

    ``default_branch`` returns ``None`` on a local-only repo with no
    ``origin/HEAD`` and no ``PLAN_TOOL_DEFAULT_BRANCH`` (every ``tmp_path`` test
    repo, and the common local case), so the ``"HEAD"`` fallback is what makes a
    bare ``worktree add`` succeed there. Never ``None``/empty — the primitives
    fail cryptically on an empty start point.
    """
    return default_branch(repo_root) or "HEAD"


def _reuse_or_fail(
    repo_root: Path, target: Path, branch: str, *, clone: bool
) -> str:
    """The impure half of step 2's reuse-vs-fail tiebreak.

    Returns ``"provision"`` (safe to create here), ``"reuse"`` (a healthy
    workspace of the expected kind on the expected branch already sits at
    ``target``), or ``"fail"`` (something else occupies the path — a file, a
    foreign dir, a stale/wrong-branch/wrong-kind workspace). ``classify_target``
    supplies the filesystem state; the git-aware health probe decides the
    non-empty case.
    """
    state = classify_target(target)
    if state in (TargetState.ABSENT, TargetState.EMPTY):
        return "provision"
    if state == TargetState.NOT_A_DIR:
        return "fail"
    # NON_EMPTY: probe for a healthy workspace of the expected kind + branch.
    if clone:
        if (
            (target / ".git").is_dir()
            and current_branch(target) == branch
            and _clone_origin_matches(target, repo_root)
        ):
            return "reuse"
        return "fail"
    resolved = target.resolve()
    for entry in worktree_list(repo_root):
        if Path(entry.path).resolve() == resolved and entry.branch == branch:
            return "reuse"
    return "fail"


def _clone_origin_matches(target: Path, repo_root: Path) -> bool:
    """True when the clone at ``target`` was actually cloned from ``repo_root``.

    Clone-reuse must not silently adopt an *unrelated* repo that merely sits at
    the derived path on a same-named branch. A local clone records its source as
    ``origin``'s URL, so a path-normalized match to ``repo_root`` is the identity
    check the non-clone path gets for free via the worktree registry. A missing
    ``origin`` / non-path URL / unresolvable path all read as "not ours".
    """
    proc = subprocess.run(
        ["git", "-C", str(target), "remote", "get-url", "origin"],
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        return False
    try:
        return Path(proc.stdout.strip()).resolve() == repo_root.resolve()
    except (OSError, ValueError):
        return False


def _classify_workspace_kind(
    target: Path, wt_by_path: dict[Path, WorktreeEntry]
) -> tuple[Optional[str], Optional[str]]:
    """Classify what kind of workspace sits at ``target`` and its branch.

    Returns ``(kind, branch)`` — ``kind`` is ``"worktree"`` (in the git worktree
    registry) or ``"clone"`` (a standalone repo whose ``.git`` is a directory),
    or ``(None, None)`` when ``target`` is not a recognized workspace. The
    worktree branch comes from the ``WorktreeEntry`` (``refs/heads/``-stripped,
    ``None`` when detached); the clone branch from ``current_branch``.
    """
    resolved = target.resolve()
    entry = wt_by_path.get(resolved)
    if entry is not None:
        return "worktree", entry.branch
    if target.exists() and (target / ".git").is_dir():
        return "clone", current_branch(target)
    return None, None


def _cmd_worktree_add(args: argparse.Namespace) -> int:
    """Provision (or reuse) the plan's workspace on its branch."""
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    slug = slug_from_filename(path)
    assert slug is not None  # default_to_stem=True guarantees non-None
    branch = _resolve_branch(ctx.repo_root, slug, args.branch)
    start_point = _resolve_start_point(ctx.repo_root)
    target = derive_worktree_path(ctx.repo_root, slug)

    decision = _reuse_or_fail(ctx.repo_root, target, branch, clone=args.clone)
    if decision == "reuse":
        success(f"reusing existing workspace at {target}")
        print(f"  cd {target}")
        return 0
    if decision == "fail":
        error(
            f"a non-empty directory that is not a matching workspace already "
            f"exists at {target}; refusing to overwrite it"
        )
        return 1

    # A new branch is born off the start point (-b); an existing branch is
    # checked out as-is (git refuses -b on an existing name).
    create = not branch_exists(ctx.repo_root, branch)
    if args.clone:
        rc, tail = clone_repo(
            ctx.repo_root, target, branch=branch, create=create,
            start_point=start_point,
        )
        kind = "clone"
    else:
        rc, tail = worktree_add(
            ctx.repo_root, target, branch, create=create,
            start_point=start_point,
        )
        kind = "worktree"
    if rc != 0:
        detail = f": {tail}" if tail else ""
        error(f"failed to provision {kind} at {target}{detail}")
        return rc
    success(f"provisioned {kind} at {target} on branch {branch}")
    print(f"  cd {target}")
    return 0


def _cmd_worktree_list(args: argparse.Namespace) -> int:
    """Report every registered plan's provisioned workspace."""
    ctx = _load_context(args)
    wt_by_path = {
        Path(e.path).resolve(): e for e in worktree_list(ctx.repo_root)
    }
    rows: list[tuple[str, str, str, str, str]] = []
    # Resolve the worktree base once — worktree_base re-reads two config files,
    # so calling derive_worktree_path per plan without base= scales that I/O
    # linearly with the plan count.
    base = worktree_base(ctx.repo_root)
    for entry in ctx.entries:
        slug = entry.slug
        target = derive_worktree_path(ctx.repo_root, slug, base=base)
        if classify_target(target) == TargetState.ABSENT:
            continue
        kind, branch = _classify_workspace_kind(target, wt_by_path)
        if kind is None:
            continue
        state = "dirty" if working_tree_dirty(target) else "clean"
        rows.append((slug, kind, branch or "(detached)", str(target), state))

    if not rows:
        print("no workspaces provisioned")
        return 0
    header = f"{'plan':<24}  {'kind':<8}  {'branch':<24}  {'state':<6}  path"
    print(header)
    for slug, kind, branch, target, state in rows:
        print(f"{slug:<24}  {kind:<8}  {branch:<24}  {state:<6}  {target}")
    return 0


def _dirty_gate(target: Path, *, force: bool) -> Optional[str]:
    """The shared clean-tree pre-gate for worktree deletion.

    Returns ``None`` when it is safe to delete (``force``, or the working tree
    is clean), else a one-line refusal message. The caller decides whether a
    non-``None`` result is a hard error (``remove``) or a skip-and-surface
    (``prune``); this is the single source so the dirty policy can't drift
    between the two verbs.
    """
    if force or not working_tree_dirty(target):
        return None
    return f"{target} has uncommitted changes; re-run with --force to delete it."


def _inside_target(target: Path, repo_root: Path) -> bool:
    """True when the cwd sits in ``target`` (or ``target`` is the main tree).

    git refuses to remove a worktree you are inside or the main working tree;
    detecting it up front lets the handler print a clean message instead of
    git's raw ``fatal:``. ``repo_root`` is threaded in by the caller because a
    misconfigured base could resolve onto the main tree.
    """
    cwd = Path.cwd().resolve()
    resolved = target.resolve()
    if cwd.is_relative_to(resolved):
        return True
    return resolved == repo_root.resolve()


def _confirm(prompt: str, *, yes: bool) -> bool:
    """Destructive-action confirmation (mirrors ``manifest._prompt_remove_missing``).

    ``yes`` short-circuits to ``True``. A non-interactive run without ``yes``
    prints a hint and returns ``False`` (an unattended run never silently
    deletes). An interactive TTY prompts ``[y/N]``, returning ``True`` only on
    ``y``/``yes``; ``EOFError``/``KeyboardInterrupt`` cancels.
    """
    if yes:
        return True
    if not sys.stdin.isatty():
        print(f"  {prompt} — re-run with -y to proceed.", file=sys.stderr)
        return False
    import builtins

    try:
        answer = builtins.input(f"{prompt} [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  cancelled.", file=sys.stderr)
        return False
    return answer in ("y", "yes")


def _cmd_worktree_remove(args: argparse.Namespace) -> int:
    """Delete one named plan's worktree (clean-tree gated; clones surfaced only)."""
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    slug = slug_from_filename(path)
    assert slug is not None  # default_to_stem=True guarantees non-None
    target = derive_worktree_path(ctx.repo_root, slug)

    # No workspace at the derived path is a successful, idempotent no-op.
    if classify_target(target) == TargetState.ABSENT:
        info(f"no workspace for {slug} at {target}")
        return 0

    wt_by_path = {
        Path(e.path).resolve(): e for e in worktree_list(ctx.repo_root)
    }
    kind, branch = _classify_workspace_kind(target, wt_by_path)
    if kind is None:
        error(
            f"the path at {target} is not a plan-tool workspace; "
            f"refusing to remove it"
        )
        return 1
    if kind == "clone":
        # A clone is an independent repo (objects not shared); the uncommitted-
        # only dirty gate can't see committed-but-unmerged work, so plan-tool
        # never deletes it — surface a manual-cleanup message and stop *before*
        # the gate/confirm (those exist only for the worktree delete path).
        warn(
            f"{target} is a --clone workspace (an independent repo); "
            f"plan-tool won't delete it. After confirming no unmerged commits, "
            f"remove it manually from a terminal: rm -rf {target}"
        )
        return 0

    if _inside_target(target, ctx.repo_root):
        error("cannot remove the workspace you are inside; cd elsewhere first")
        return 1

    msg = _dirty_gate(target, force=args.force)
    if msg is not None:
        error(msg)
        return 1

    if not _confirm(
        f"Remove {kind} workspace for {slug} at {target}?", yes=args.yes
    ):
        print("  kept — nothing removed.")
        return 0

    rc, tail = worktree_remove(ctx.repo_root, target, force=args.force)
    if rc != 0:
        error(tail or f"failed to remove worktree at {target}")
        return rc
    left = f" (branch {branch} left in place)" if branch else ""
    success(f"removed {kind} workspace for {slug}{left}")
    return 0


def _cmd_worktree_prune(args: argparse.Namespace) -> int:
    """Sweep dead (deregistered / path-gone) plan-tool worktrees.

    Discovery is git's worktree registry scoped to ``worktree_base`` — never a
    path-scan — so an operator's unrelated worktree is never a candidate, and
    clones (not in the registry) are ignored entirely. A dead-but-dirty
    worktree is surfaced (not deleted) even under ``-y``.
    """
    ctx = _load_context(args)
    base = worktree_base(ctx.repo_root).resolve()
    registered = {
        derive_worktree_path(ctx.repo_root, e.slug, base=base).resolve(): e
        for e in ctx.entries
    }
    # Candidates: git-registered worktrees under the base whose dir name
    # round-trips through the deterministic derived-path scheme.
    candidates: list[Path] = []
    for entry in worktree_list(ctx.repo_root):
        p = Path(entry.path).resolve()
        if base not in p.parents:
            continue
        # A dir name that can't be a plan slug (e.g. contains a backslash, which
        # ``_validate_slug`` rejects) can't be a plan-tool worktree — skip it
        # rather than crash on the ValueError.
        try:
            derived = derive_worktree_path(ctx.repo_root, p.name, base=base).resolve()
        except ValueError:
            continue
        if derived != p:
            continue
        candidates.append(p)
    dead = [p for p in candidates if p not in registered]

    # git admin GC for worktrees whose directory was deleted outside the tool — deletes
    # nothing on disk (the dir is already gone), so no dirty gate applies.
    worktree_prune(ctx.repo_root)

    if not dead:
        print("no dead workspaces to prune")
        return 0

    to_delete: list[Path] = []
    for target in dead:
        if not target.exists():
            continue  # path-gone; the admin prune above cleared its registry entry
        # Never delete the workspace the operator is standing in (git would
        # succeed and pull the cwd out from under them) — surface, don't sweep.
        if _inside_target(target, ctx.repo_root):
            warn(
                f"skipping {target}: it is the workspace you are standing in; "
                f"cd elsewhere and re-run to prune it"
            )
            continue
        if working_tree_dirty(target):
            warn(
                f"dead-but-dirty workspace at {target}; use "
                f"`plan-tool worktree remove <plan> --force` to delete it"
            )
            continue
        to_delete.append(target)

    if not to_delete:
        return 0

    if not _confirm(
        f"Prune {len(to_delete)} dead workspace(s)?", yes=args.yes
    ):
        print("  kept — nothing pruned.")
        return 0

    # Track partial failure: a git ``worktree remove`` that fails (locked,
    # submodule, broken admin link) must make the whole sweep exit non-zero so
    # automation doesn't read a false success (exit-code convention).
    failures = 0
    for target in to_delete:
        rc, tail = worktree_remove(ctx.repo_root, target, force=False)
        if rc != 0:
            error(tail or f"failed to remove worktree at {target}")
            failures += 1
            continue
        success(f"pruned {target}")
    return 1 if failures else 0


def cmd_worktree(args: argparse.Namespace) -> int:
    """Dispatch the ``worktree`` group on ``args.action`` (add / list / remove / prune)."""
    if args.action == "add":
        return _cmd_worktree_add(args)
    if args.action == "list":
        return _cmd_worktree_list(args)
    if args.action == "remove":
        return _cmd_worktree_remove(args)
    if args.action == "prune":
        return _cmd_worktree_prune(args)
    error(f"unknown worktree action {args.action!r}")
    return 2


def register(subparsers) -> dict[str, Handler]:
    """Add the ``worktree`` subparser (with its add / list sub-actions)."""
    p = subparsers.add_parser(
        "worktree",
        help=(
            "provision and inspect isolated per-plan workspaces "
            "(worktrees / clones)"
        ),
    )
    sub = p.add_subparsers(dest="action", required=True)

    p_add = sub.add_parser(
        "add",
        help="provision (or reuse) the plan's workspace on its branch",
    )
    p_add.add_argument("name", help="path or slug of a registered plan")
    p_add.add_argument(
        "--branch",
        dest="branch",
        default=None,
        help=(
            "branch to provision the workspace on (overrides the derived "
            "name: derive_branch when branch-awareness is on, else the slug)"
        ),
    )
    p_add.add_argument(
        "--clone",
        action="store_true",
        default=False,
        help=(
            "provision a standalone clone instead of a git worktree "
            "(an independent repo dir whose .git is a directory)"
        ),
    )

    sub.add_parser(
        "list",
        help="report every plan's workspace: kind, branch, path, dirty state",
    )

    # Deliberately NOT parser.make_yes_parent(): this one carries an
    # explicit dest/default and its own shorter help. ``add``/``list`` stay
    # non-destructive and unparented.
    yes_parent = argparse.ArgumentParser(add_help=False)
    yes_parent.add_argument(
        "-y",
        "--yes",
        action="store_true",
        dest="yes",
        default=False,
        help="auto-accept the confirmation prompt (for scripted/unattended runs)",
    )

    p_remove = sub.add_parser(
        "remove",
        parents=[yes_parent],
        help="delete a plan's workspace (clean-tree gated; --force to override)",
    )
    p_remove.add_argument("name", help="path or slug of a registered plan")
    p_remove.add_argument(
        "--force",
        action="store_true",
        dest="force",
        default=False,
        help="delete even a dirty worktree (bypasses the clean-tree gate)",
    )

    sub.add_parser(
        "prune",
        parents=[yes_parent],
        help=(
            "sweep dead (deregistered/path-gone) worktrees; "
            "dirty ones are surfaced, not deleted"
        ),
    )

    return {"worktree": cmd_worktree}
