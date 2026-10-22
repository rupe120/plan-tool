"""Working-tree reads and the partial-mutation retry guard built on them.

A stdlib-only leaf below ``shell``/``launcher`` whose one first-party import is
``rate_limit_loop`` (itself a stdlib-only leaf), so it forms no cycle. It exists
because **both** backend callers need the same guard: the shared recovery loop
re-invokes ``run_once`` on a transient or rate-limit outcome, and re-driving a
turn that already edited the tree double-applies those edits.

``launcher.shell_invoker`` (streaming) has always guarded that. ``shell``'s
batch path did not — it passed an unconditional always-retry on the premise
that "batch proposal turns never edit the working tree", which was never true:
the batch argv carries ``--permission-mode acceptEdits`` and ``detail``'s
subprocess demonstrably authors files (see ``detail._archive_orphan_details``,
which exists to sweep them). One guard, both callers.

See docs/how-to/pipeline/run.md for the seam-by-seam recovery contract.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

from plan_tool.rate_limit_loop import ALWAYS_RETRY, RetryDecision, RetryPolicy

ChangedPathsReader = Callable[[Path], Optional[set[str]]]


def changed_paths_or_none(repo_root: Path) -> Optional[set[str]]:
    """Repo-relative paths ``git status`` reports as changed, or ``None`` when
    git can't be read (spawn failure / non-zero rc).

    The ``None`` return lets a caller distinguish "the tree is clean" (empty
    set) from "we couldn't tell" (git errored). The retry-guard needs that
    distinction to fail *closed* on an unreadable tree; the test-authoring gate
    does not, and uses :func:`changed_paths`, which collapses ``None`` to an
    empty set.

    ``--untracked-files=all`` lists files individually instead of collapsing a
    wholly-untracked dir to its name, so a test in a brand-new ``tests/`` is
    seen as ``tests/test_x.py``. ``-z`` disables git's path quoting/escaping,
    so spaces/tabs/non-ASCII come through verbatim; each NUL record is
    ``XY <path>`` and a rename/copy (``X`` in ``R``/``C``) is followed by an
    extra NUL field (the origin) we skip.
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
            cwd=str(repo_root),
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, PermissionError, OSError):
        return None
    if proc.returncode != 0:
        return None
    # ``-z`` output is a flat NUL-separated stream (no per-line framing); a
    # trailing NUL yields a final empty token we skip. Walk it as a cursor so
    # a rename/copy can consume its extra origin-path field.
    fields = proc.stdout.split("\0")
    paths: set[str] = set()
    i = 0
    while i < len(fields):
        entry = fields[i]
        if len(entry) < 4:  # need at least "XY <1-char path>"
            i += 1
            continue
        status, path = entry[:2], entry[3:]
        paths.add(path)
        # Rename/copy records are followed by their origin path in the next
        # NUL field; skip it so it isn't parsed as a separate status entry.
        i += 2 if status[0] in ("R", "C") else 1
    return paths


def changed_paths(repo_root: Path) -> set[str]:
    """Repo-relative changed paths, or an empty set on any git error.

    Thin wrapper over :func:`changed_paths_or_none` for callers (the
    test-authoring gate) that treat "can't tell" as "nothing changed" and so
    never block on a non-git tree. The retry-guard uses the ``_or_none`` form
    directly so it can fail closed instead.
    """
    changed = changed_paths_or_none(repo_root)
    return changed if changed is not None else set()


def head_revision(repo_root: Path) -> Optional[str]:
    """Return the pre-call commit, or None for unreadable/unborn repositories."""
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=str(repo_root), stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
    except OSError:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def committed_changed_paths(repo_root: Path, baseline: Optional[str]) -> set[str]:
    """Added/modified destination paths between a known pre-call commit and HEAD."""
    if baseline is None:
        return set()
    try:
        proc = subprocess.run(
            ["git", "diff", "--name-only", "-z", "--no-renames",
             "--diff-filter=ACMRT", baseline, "HEAD", "--"],
            cwd=str(repo_root), stdin=subprocess.DEVNULL,
            capture_output=True, text=True,
        )
    except OSError:
        return set()
    return set(filter(None, proc.stdout.split("\0"))) if proc.returncode == 0 else set()


def make_partial_mutation_retry_guard(
    spawn_cwd: Optional[Path],
    *,
    read_changed: ChangedPathsReader = changed_paths_or_none,
) -> Optional[Callable[[object], RetryDecision]]:
    """Build the loop's ``retry_guard`` for a backend call, or ``None``.

    Snapshots the spawn-cwd changed-paths set once, *before* attempt 1, so
    attempt 1's own edits aren't folded into the baseline (capturing later would
    hide the first attempt's partial edits — the "baseline captured too late"
    trap). When an aborted turn leaves a newly-changed path, re-driving would
    double-apply it, so the guard STOPs the retry instead.

    The baseline read also classifies the tree: ``None`` (no spawn cwd, a
    non-git tree, or a repo unreadable at entry) returns ``None`` here, leaving
    the caller's retry behavior exactly as it was without a guard.

    ``read_changed`` is a seam so a caller can route the read through its own
    module-level name (keeping existing monkeypatch points live).
    """
    if spawn_cwd is None:
        return None
    baseline = read_changed(spawn_cwd)
    if baseline is None:
        return None

    def _guard(_outcome: object) -> RetryDecision:
        # Consulted by the loop before any predicted re-invoke (transient
        # backoff *or* rate-limit wait/switch). ``current - baseline`` isolates
        # paths that became changed after the snapshot: a pre-existing dirty
        # tree stays in the baseline and never trips the guard; only new
        # mutations do. Ignored paths are excluded (porcelain omits them).
        current = read_changed(spawn_cwd)
        if current is None:
            # The repo was readable at baseline but not now (e.g. an index.lock
            # during a --commit run) — we can't verify the tree, so fail
            # CLOSED: refuse the retry rather than risk re-driving over an
            # unseen partial mutation. (Reading the empty set here would let
            # the delta collapse to empty and retry, defeating the guard.) A
            # surfaced failure is the safe direction.
            return RetryDecision(
                RetryPolicy.STOP,
                "could not read git state to verify the working tree; refusing "
                "retry to avoid double-applying a possible partial mutation. "
                "Resolve any git lock, inspect with git status, then re-run "
                "the step.",
            )
        delta = current - baseline
        if not delta:
            return ALWAYS_RETRY
        listed = ", ".join(sorted(delta))
        hint = (
            "aborted turn left uncommitted edits "
            f"({listed}); refusing retry to avoid double-applying them. "
            "Discard them (git restore / git checkout for modified files; "
            "git clean -f / rm for newly-created ones — restore/checkout do "
            "not remove untracked files) and re-run the step, or accept the "
            "partial work as complete and do not re-run. Do not "
            "commit-then-re-run — that re-drives over the partial edits."
        )
        return RetryDecision(RetryPolicy.STOP, hint)

    return _guard
