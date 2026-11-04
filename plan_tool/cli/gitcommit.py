"""Shared git-commit plumbing for the opt-in ``--commit`` flags.

Used by the authoring/audit verbs whose ``--commit`` stages and commits the
plan/detail edits they produce (``detail``, ``completeness-audit``). Stdlib-only leaf — imports nothing from the cli
package, so any command module can import it without a cycle. ``run``'s
``--commit`` keeps its own per-green-step helper (different subject/semantics).
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


def working_tree_dirty(repo_root: Path) -> bool:
    """True when ``git status --porcelain`` reports any change — or can't run.

    A non-zero git rc (e.g. ``repo_root`` isn't a git work tree) also counts
    as dirty so ``--commit`` refuses rather than risk folding unrelated work
    into the commit.
    """
    proc = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return True
    return bool(proc.stdout.strip())


def unexpected_dirty_paths(
    repo_root: Path, expected: Sequence[Path]
) -> "list[str] | None":
    """Repo-relative dirty paths in ``repo_root`` not covered by ``expected``.

    Runs ``git status --porcelain --untracked-files=all``. The ``-uall`` mode is
    load-bearing: git otherwise collapses a wholly-new untracked directory into
    one ``?? .plan-tool/`` line, which would both mask the expected file inside
    it and hide an unrelated file sitting next to it. Same gotcha
    ``scenario_capture.working_tree_dirty`` solves — generalized here from one
    hardcoded prefix to a caller-supplied set. A reported path counts as
    expected when it equals, or is nested under, any ``expected`` entry (so a
    directory in ``expected`` covers the files ``-uall`` lists beneath it).

    Each ``expected`` path is resolved and relativized against ``repo_root``; an
    entry that can't be under ``repo_root`` (an out-of-repo ``--manifest``
    override) is skipped, since it can't appear in this repo's status anyway.
    Returns the sorted reported paths not in the expected set (``[]`` when all
    dirt is accounted for), or ``None`` when ``git status`` can't be read (not a
    work tree, git unavailable) — a caller that must fail closed treats ``None``
    the same as a non-empty list, never as "clean" (mirrors
    ``launcher._git_changed_paths_or_none``'s None-means-"couldn't-tell").
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--untracked-files=all"],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except OSError:
        # git binary absent / repo_root unreadable → "couldn't tell", same as a
        # non-zero rc. Mirrors scenario_capture.working_tree_dirty's OSError
        # guard so a missing git crashes nothing (the caller fails closed).
        return None
    if proc.returncode != 0:
        return None
    root = repo_root.resolve()
    expected_rel: set[str] = set()
    for path in expected:
        try:
            expected_rel.add(path.resolve().relative_to(root).as_posix())
        except ValueError:
            continue  # not under repo_root — can't appear in its git status
    unexpected: list[str] = []
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        # Porcelain v1: two status chars + space + path.
        reported = line[3:].strip()
        if any(
            reported == exp or reported.startswith(exp + "/")
            for exp in expected_rel
        ):
            continue
        unexpected.append(reported)
    return sorted(unexpected)


def path_is_gitignored(repo_root: Path, path: Path) -> bool:
    """True when ``path`` is excluded by gitignore rules (``git check-ignore``).

    Lets a ``--commit`` verb warn when a file it means to commit — e.g. the
    saved-audit JSON the walker annotates in place — sits on an ignored path,
    so ``git add -A`` would silently skip it and the annotations would never
    land. ``check-ignore`` exits 0 when one or more paths match an ignore
    rule, 1 when none do, 128 on a fatal error (not a work tree, …); only an
    exit of 0 is a positive "ignored", so any other rc returns False rather
    than false-warning.
    """
    proc = subprocess.run(
        ["git", "check-ignore", "-q", "--", str(path)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


# Durable plan-tool state the project is meant to COMMIT (see the README's
# "The .plan-tool/ directory" split). When a repo gitignores these — e.g. by
# excluding ``.plan-tool/`` wholesale — they silently never reach version
# control and the team loses the shared manifest / lessons. ``bench/runs`` is
# intentionally omitted: it's deliberately mostly-ignored (only a pinned
# fixture is force-kept), so it would false-positive here.
RECOMMENDED_COMMITTED_SUBPATHS = (
    Path(".plan-tool") / "plans.json",
    Path(".plan-tool") / "lessons",
    Path(".plan-tool") / "project.json",
)


def ignored_recommended_paths(repo_root: Path) -> "list[Path]":
    """Return the recommended-to-commit plan-tool paths that gitignore excludes.

    Only paths that actually exist on disk are checked (an absent ``lessons/``
    isn't a problem). Returns repo-relative ``Path``s so the caller can name
    them. Empty when nothing is ignored or git can't answer (not a work tree,
    …) — ``check-ignore`` exits 0 with the ignored paths on stdout, 1 when none
    match, 128 on a fatal error, so only rc 0 is read.
    """
    existing = [
        sub for sub in RECOMMENDED_COMMITTED_SUBPATHS
        if (repo_root / sub).exists()
    ]
    if not existing:
        return []
    proc = subprocess.run(
        ["git", "check-ignore", "--", *(str(repo_root / s) for s in existing)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    ignored = {line.strip() for line in proc.stdout.splitlines() if line.strip()}
    return [s for s in existing if str(repo_root / s) in ignored]


def warn_recommended_paths_ignored(repo_root: Path, emit) -> None:
    """Warn (via ``emit``) when a recommended-to-commit path is gitignored.

    ``emit`` is a ``style.warn``-style callable taking one string. A no-op when
    nothing is ignored, so callers can fire it unconditionally after writing the
    manifest. Kept here (not in ``style``) so the detection and its message stay
    next to ``ignored_recommended_paths``.
    """
    ignored = ignored_recommended_paths(repo_root)
    if not ignored:
        return
    names = ", ".join(p.as_posix() for p in ignored)
    emit(
        f"gitignored but meant to be committed: {names} — these won't be "
        "shared with your team. Remove the matching .plan-tool/ rule from "
        ".gitignore."
    )


def commit_all(repo_root: Path, subject: str) -> "tuple[int, str]":
    """Stage all changes (``git add -A``) and commit with ``subject``.
    Returns ``(rc, stderr-tail)``.

    No AI-attribution trailer — the operator's own git identity is the sole
    author of record. No ``--no-verify`` — pre-commit hooks run and a
    rejection surfaces as a non-zero rc. ``tail`` is the failing command's
    stderr for the caller to show.
    """
    add = subprocess.run(
        ["git", "add", "-A"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if add.returncode != 0:
        return add.returncode, add.stderr.strip()
    commit = subprocess.run(
        ["git", "commit", "-m", subject],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return commit.returncode, commit.stderr.strip()


def commit_receipt(
    repo_root: Path, receipt_path: Path, subject: str
) -> "tuple[int, str]":
    """Force-stage and commit only ``receipt_path``. Returns ``(rc, tail)``.

    The path-limited commit leaves pre-existing index entries alone. If staging
    succeeds but committing cannot, unstage only the receipt while keeping its
    on-disk bytes for the caller's retry or recovery path.
    """
    try:
        relative_path = receipt_path.resolve().relative_to(repo_root.resolve()).as_posix()
        receipt_data = receipt_path.read_bytes()
    except (OSError, ValueError) as exc:
        return 1, f"receipt path is unavailable: {exc}"

    try:
        raw_hash = subprocess.run(
            ["git", "hash-object", "--stdin"],
            cwd=repo_root,
            input=receipt_data,
            capture_output=True,
        )
        filtered_hash = subprocess.run(
            ["git", "hash-object", f"--path={relative_path}", "--stdin"],
            cwd=repo_root,
            input=receipt_data,
            capture_output=True,
        )
    except OSError as exc:
        return 1, f"git subprocess error: {exc}"
    if raw_hash.returncode != 0:
        return raw_hash.returncode, raw_hash.stderr.decode(errors="replace").strip()
    if filtered_hash.returncode != 0:
        return filtered_hash.returncode, filtered_hash.stderr.decode(errors="replace").strip()
    if raw_hash.stdout != filtered_hash.stdout:
        return 1, "Git attributes would transform receipt bytes"

    pathspec = f":(literal){relative_path}"
    try:
        add = subprocess.run(
            ["git", "add", "--force", "--", pathspec],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return 1, f"git subprocess error: {exc}"
    if add.returncode != 0:
        return add.returncode, add.stderr.strip()

    try:
        commit = subprocess.run(
            ["git", "commit", "--only", "-m", subject, "--", pathspec],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        failure = 1, f"git subprocess error: {exc}"
    else:
        if commit.returncode == 0:
            return 0, commit.stderr.strip()
        failure = commit.returncode, commit.stderr.strip()

    try:
        unstage = subprocess.run(
            ["git", "reset", "--", pathspec],
            cwd=repo_root,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return failure[0], (
            f"{failure[1]}\nreceipt unstage failed: {exc}".strip()
        )
    if unstage.returncode != 0:
        return failure[0], (
            f"{failure[1]}\nreceipt unstage failed: {unstage.stderr.strip()}".strip()
        )
    return failure


# Environment override the branch-awareness feature reads when a local-only
# repo has no ``origin/HEAD`` to derive a default branch from. Matches the
# existing ``PLAN_TOOL_*`` env convention (``PLAN_TOOL_BACKEND``, …).
DEFAULT_BRANCH_ENV = "PLAN_TOOL_DEFAULT_BRANCH"


def current_branch(repo_root: Path) -> str | None:
    """The checked-out branch name, or ``None`` when undeterminable.

    Uses ``git symbolic-ref --short HEAD`` whose native non-zero exit folds
    detached HEAD *and* "not a work tree" into the same ``None`` answer — no
    magic-string check (``rev-parse --abbrev-ref`` would print ``"HEAD"`` on a
    detached head). The same reader is reused on producer and consumer sides
    so normalized comparisons can't diverge.
    """
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "HEAD"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def default_branch(repo_root: Path) -> str | None:
    """The repo's default branch name, or ``None`` when undeterminable.

    Precedence: a non-empty ``PLAN_TOOL_DEFAULT_BRANCH`` env override (the
    escape hatch for local-only repos with no ``origin/HEAD``), else the
    branch ``refs/remotes/origin/HEAD`` points at with its ``origin/`` prefix
    stripped, else ``None``.
    """
    override = os.environ.get(DEFAULT_BRANCH_ENV)
    if override is not None and override.strip():
        return override.strip()
    proc = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return None
    # Short form is ``origin/<branch>``; drop the leading ``origin/`` segment.
    short = proc.stdout.strip()
    _, _, branch = short.partition("/")
    return branch or None


def branch_exists(repo_root: Path, name: str) -> bool:
    """True only when a local ``refs/heads/<name>`` branch exists.

    Scoped to ``refs/heads/`` so existence means a local branch (what the run
    guard checks before switching), not a tag or remote-tracking ref. Mirrors
    ``path_is_gitignored``'s rc-0-is-the-only-positive posture: any non-zero
    rc (absent ref, non-repo) returns False.
    """
    proc = subprocess.run(
        ["git", "show-ref", "--verify", "--quiet", "--", f"refs/heads/{name}"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def list_branches(repo_root: Path) -> list[str]:
    """Short names of every local branch and remote-tracking ref.

    Uses ``git for-each-ref`` over ``refs/heads`` and ``refs/remotes`` — reads
    local ref storage only, issues no network call. Returns the non-empty
    stripped lines on rc 0, ``[]`` on any failure. Kept raw (no sort/filter)
    so the caller owns dedup/normalization for the collision scan.
    """
    proc = subprocess.run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname:short)",
            "refs/heads",
            "refs/remotes",
        ],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def remote_collisions(
    refs: Sequence[str], derived: str, prefixes: Sequence[str]
) -> list[str]:
    """Remote-tracking short refs whose branch name equals ``derived``.

    Pure (no git read): the caller does the single ``list_branches`` read and
    passes its raw output as ``refs``. ``derived`` is the canonical branch name
    to test against (e.g. ``plan/<slug>``); ``prefixes`` are the configured
    convention prefixes, used only to exclude local convention branches from the
    remote scan.

    Per ``refs`` entry: skip single-segment names (no ``/``, can't be
    ``<remote>/<branch>``); skip local convention branches (an entry whose own
    first segment is a configured prefix); split once on ``/`` to strip the
    ``<remote>/`` segment (``partition`` keeps slash-bearing branch names
    whole); filter the symbolic ``<remote>/HEAD`` and empty tails; and collect
    the full entry when the stripped tail equals ``derived``. Returns the
    sorted, de-duplicated full short refs (e.g. ``origin/plan/<slug>``) so the
    caller can name the offending remote; ``[]`` when nothing collides.
    """
    collected: list[str] = []
    for entry in refs:
        if "/" not in entry:
            continue
        if any(entry.startswith(p) and len(entry) > len(p) for p in prefixes):
            continue
        _, _, tail = entry.partition("/")
        if not tail or tail == "HEAD":
            continue
        if tail == derived:
            collected.append(entry)
    return sorted(set(collected))


def create_and_checkout_branch(repo_root: Path, name: str) -> "tuple[int, str]":
    """Create branch ``name`` and switch to it (``git switch -c``).

    Returns ``(rc, stderr-tail)`` and never raises. ``switch -c`` fails when
    the branch already exists (correct for the create-at-attach path) and
    refuses to clobber uncommitted work absent ``--discard-changes``/``--merge``
    (neither passed). ``--quiet`` drops the "Switched to" feedback so a clean
    success yields an empty tail; real errors still surface. Stays policy-free:
    the clean-tree precondition is the caller's, so both attach-branch and the
    create-gate reuse this primitive.
    """
    proc = subprocess.run(
        ["git", "switch", "--quiet", "-c", name],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr.strip()


def checkout_existing_branch(repo_root: Path, name: str) -> "tuple[int, str]":
    """Switch to the existing branch ``name`` (plain ``git switch``).

    Returns ``(rc, stderr-tail)`` and never raises. The switch verb, distinct
    from ``create_and_checkout_branch``'s create verb: the bound branch already
    exists when the run guard wants to switch to it, so ``switch -c`` would
    error "branch already exists".
    """
    proc = subprocess.run(
        ["git", "switch", "--quiet", name],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr.strip()


@dataclass(frozen=True)
class WorktreeEntry:
    """One record parsed from ``git worktree list --porcelain``.

    ``path`` is the raw porcelain string (callers ``resolve()`` for
    comparison); ``branch`` is the short name with ``refs/heads/`` stripped,
    ``None`` when detached or bare.
    """

    path: str
    branch: str | None
    head: str | None
    detached: bool
    bare: bool


def worktree_add(
    repo_root: Path,
    path: Path,
    branch: str,
    *,
    create: bool,
    start_point: str,
) -> "tuple[int, str]":
    """Add a worktree at ``path`` checked out on ``branch``. ``(rc, tail)``.

    ``create=True`` births the branch inside the add off ``start_point``
    (``git worktree add -b <branch> <path> <start_point>``); ``create=False``
    attaches the existing branch (``git worktree add <path> <branch>``, which
    ignores ``start_point``). The single most important rule: the branch is
    created/checked out *inside* the add, never via a main-tree ``switch -c``
    first — git refuses to add a worktree on a branch already checked out in
    another tree. On the ``create=True`` path ``start_point`` must be a
    non-empty, locally-resolvable commit-ish (the caller resolves it); this
    primitive neither defaults nor validates it. Returns ``(rc, stderr-tail)``
    and never raises — the same-branch-twice and non-empty-target cases surface
    as a non-zero rc + git's stderr tail for the caller to message.
    """
    if create:
        argv = [
            "git",
            "worktree",
            "add",
            "--quiet",
            "-b",
            branch,
            str(path),
            start_point,
        ]
    else:
        argv = ["git", "worktree", "add", "--quiet", str(path), branch]
    proc = subprocess.run(
        argv,
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr.strip()


def worktree_list(repo_root: Path) -> list[WorktreeEntry]:
    """Parse ``git worktree list --porcelain`` into ``WorktreeEntry`` records.

    Returns ``[]`` on any non-zero rc (non-repo, old git), matching
    ``list_branches``. Blocks are separated by blank lines; a block without a
    ``worktree <path>`` line is skipped. The main working tree is the first
    entry and is *not* filtered here — the caller decides (step 3). The parser
    ignores unknown lines (``locked``, ``prunable``, …) so a future git field
    doesn't break the read.
    """
    proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        return []
    entries: list[WorktreeEntry] = []
    path: str | None = None
    head: str | None = None
    branch: str | None = None
    detached = False
    bare = False

    def _flush() -> None:
        nonlocal path, head, branch, detached, bare
        if path is not None:
            entries.append(
                WorktreeEntry(
                    path=path,
                    branch=branch,
                    head=head,
                    detached=detached,
                    bare=bare,
                )
            )
        path, head, branch, detached, bare = None, None, None, False, False

    for line in proc.stdout.splitlines():
        if not line.strip():
            _flush()
            continue
        key, _, value = line.partition(" ")
        if key == "worktree":
            path = value
        elif key == "HEAD":
            head = value
        elif key == "branch":
            branch = value.removeprefix("refs/heads/")
        elif line == "detached":
            detached = True
        elif line == "bare":
            bare = True
    _flush()
    return entries


def worktree_remove(
    repo_root: Path, path: Path, *, force: bool
) -> "tuple[int, str]":
    """Remove the worktree at ``path`` (``git worktree remove``). ``(rc, tail)``.

    Appends ``--force`` when ``force`` is true. Policy-free: the clean-tree gate
    is the caller's (step 4) — git's own dirty-tree refusal surfaces as a
    non-zero rc, mirroring how ``create_and_checkout_branch`` leaves the
    clean-tree precondition to the caller. Never raises.
    """
    argv = ["git", "worktree", "remove"]
    if force:
        argv.append("--force")
    argv.append(str(path))
    proc = subprocess.run(
        argv,
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr.strip()


def worktree_prune(repo_root: Path) -> "tuple[int, str]":
    """Drop admin files for worktrees whose directory is gone. ``(rc, tail)``.

    Plain ``git worktree prune`` — no flags. Step 4's prune verb layers the
    discovery/confirmation/dirty-surfacing policy on top. Never raises.
    """
    proc = subprocess.run(
        ["git", "worktree", "prune"],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return proc.returncode, proc.stderr.strip()


def _resolve_start_in_clone(path: Path, start_point: str) -> str:
    """Resolve ``start_point`` against a fresh clone's refs.

    A local clone materializes only ONE local branch (the source's checked-out
    HEAD); every other branch exists only as ``origin/<name>``. So a bare
    ``start_point`` like ``main`` fails ``switch -c`` unless it happens to be the
    source's current branch. Prefer the literal name, then ``origin/<name>``,
    then the clone's ``HEAD`` — the first that resolves to a commit.
    """
    for candidate in (start_point, f"origin/{start_point}"):
        probe = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "--verify", "--quiet",
             f"{candidate}^{{commit}}"],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
        if probe.returncode == 0:
            return candidate
    return "HEAD"


def clone_repo(
    repo_root: Path,
    path: Path,
    *,
    branch: str,
    create: bool,
    start_point: str,
) -> "tuple[int, str]":
    """Clone ``repo_root`` to ``path`` and land ``branch`` inside the clone.

    Two-phase because a clone is an independent repo with no main-tree
    co-checkout conflict, so the worktree ``-b`` rationale does not apply:
    (1) ``git clone <repo_root> <path>`` — on non-zero rc return ``(rc, tail)``
    immediately, never attempting the switch; (2) inside the clone, either
    ``git -C <path> switch -c <branch> <start>`` (``create=True``, new branch
    off ``start`` — ``start_point`` resolved against the clone's refs by
    :func:`_resolve_start_in_clone`, since a fresh clone has only one local
    branch) or ``git -C <path> switch <branch>``
    (``create=False``, DWIM onto the cloned ``origin/<branch>``). Never uses
    ``git clone -b`` — it fails for a not-yet-existing branch. The ``create``
    keyword is the new-vs-existing discriminator, mirroring ``worktree_add``.
    Returns ``(rc, stderr-tail)`` from whichever phase ran last; never raises.
    """
    clone = subprocess.run(
        ["git", "clone", "--quiet", str(repo_root), str(path)],
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    if clone.returncode != 0:
        return clone.returncode, clone.stderr.strip()
    if create:
        switch_argv = [
            "git",
            "-C",
            str(path),
            "switch",
            "--quiet",
            "-c",
            branch,
            _resolve_start_in_clone(path, start_point),
        ]
    else:
        switch_argv = ["git", "-C", str(path), "switch", "--quiet", branch]
    switch = subprocess.run(
        switch_argv,
        cwd=repo_root,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
    )
    return switch.returncode, switch.stderr.strip()
