"""Live-edit drift detection for iteration loops.

Wraps an iteration loop's lifetime (``cmd_create`` / ``cmd_detail`` /
``cmd_completeness --iterate``)
with one guarantee:

**Live-edit drift detection.** On acquire we snapshot the SHA-256
content hash of each file in the watched-files set (the iteration's
in-scope paths). On exit we re-hash; any file whose content changed
during the hold is flagged. The iteration loop's findings against
those files may reflect the user's concurrent edits, not pre-existing
drift -- a class of confusion observed during the
``iterative-correctness-completeness-passes`` self-test where live
edits to ``cli.py`` / ``convergence.py`` / ``scope_guard.py`` produced
reconcile findings about the edits-in-flight. Hashing replaced the
legacy mtime check so harmless mtime touches (IDE re-saves, ``git
checkout`` of unchanged content, ``touch`` for build invalidation) no
longer trip the check.

Pure file I/O. No claude shell-out; ``pathutil`` supplies lexical displays
and ``style`` supplies diagnostic styling.
"""

from __future__ import annotations

import hashlib
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from plan_tool.pathutil import literal_path
from plan_tool.style import tool


@dataclass
class IterationLock:
    """Active iteration lock for one plan slug.

    Construction is via :func:`acquire_lock`; drift at the end of the
    hold is measured via :func:`check_drift` / :func:`release_lock`.
    """

    repo_root: Path
    slug: str
    command: str
    started_at: float
    pid: int
    # path string → content hash (sha256 hex digest). Replaces the
    # legacy mtime check: mtime advances on harmless touches
    # (IDE re-saves with no change, ``git checkout`` of unchanged
    # content, ``touch`` for build-system invalidation), producing
    # false-positive drift halts. Content hash only changes when
    # bytes actually change. The hex digest is small and round-trips
    # through json cleanly.
    content_hash_snapshot: dict[str, str] = field(default_factory=dict)
    # Idempotency sentinel: ``release_lock`` flips this to True on
    # first call. Subsequent calls return ``[]`` without re-hashing
    # files, so callers that release in more than one place don't
    # double-emit the live-edit drift warning.
    released: bool = False


def compute_content_hash(p: Path) -> Optional[str]:
    """Return the SHA-256 hex digest of ``p``'s content, or ``None``
    when the file doesn't exist / is unreadable.

    Used by acquire/release drift detection to replace the
    legacy mtime check. Streamed read in 64 KB chunks so the
    function handles arbitrarily large files without spiking
    memory. SHA-256 is stdlib; the speed (~500 MB/s on modern
    hardware) is plenty for the per-iteration / per-watch-call cost.

    Returns ``None`` rather than raising for missing/unreadable
    files so callers can treat that the same way the legacy mtime
    code did: skip silently.
    """
    try:
        h = hashlib.sha256()
        with p.open("rb") as fh:
            while True:
                chunk = fh.read(65_536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def acquire_lock(
    repo_root: Path,
    *,
    slug: str,
    command: str,
    watched_paths: Iterable[Path],
    force: bool = False,
) -> IterationLock:
    """Snapshot the watched files' content hashes and return an
    :class:`IterationLock`.

    Writes no lockfile: the returned lock carries the slug, command,
    pid, started_at, and the per-file SHA-256 snapshot in memory, and
    nothing under ``<repo_root>/.plan-tool/`` is created. The ``slug``
    argument is recorded on the lock for debug visibility. ``force`` is
    accepted for signature compatibility and has no effect.

    ``watched_paths`` is the set of files whose SHA-256 content
    hashes are snapshotted at acquire time (#31; replaces the legacy
    mtime snapshot). Files that don't exist are skipped silently
    (e.g. step.files entries for not-yet-written files).
    """
    content_hash_snapshot: dict[str, str] = {}
    for p in watched_paths:
        # Files that don't exist yet (e.g. a step declares a new
        # file) or are transiently unreadable get skipped silently
        # -- same shape the legacy mtime check used.
        digest = compute_content_hash(p)
        if digest is None:
            continue
        content_hash_snapshot[str(p)] = digest

    return IterationLock(
        repo_root=repo_root,
        slug=slug,
        command=command,
        started_at=time.time(),
        pid=os.getpid(),
        content_hash_snapshot=content_hash_snapshot,
    )


def refresh_snapshot(lock: IterationLock) -> None:
    """Replace ``lock.content_hash_snapshot`` with hashes of the
    watched files' CURRENT on-disk content.

    Used by the change-collision merge-continue path: when the user
    has merged their drift into the plan/detail (via the
    ``change_collision`` sidecar flow) and chosen to continue
    iteration, the post-merge state of the watched files becomes
    the new baseline. Subsequent ``check_drift`` calls then compare
    against the merged state rather than the pre-merge snapshot,
    which is the only thing that keeps the merge-continue path from
    immediately halting again on the same drift on the next
    iteration's pre-apply check.

    Tracked paths stay the same -- this only refreshes hashes. A
    file that was tracked at acquire time but is now missing /
    unreadable is dropped from the snapshot (mirrors acquire-time
    "skip None" semantics; future drift checks won't flag a
    deleted file as drifted).

    Mutates ``lock`` in place. No effect on lock ownership /
    lockfile state.
    """
    new_snapshot: dict[str, str] = {}
    for p_str in list(lock.content_hash_snapshot.keys()):
        digest = compute_content_hash(Path(p_str))
        if digest is None:
            continue
        new_snapshot[p_str] = digest
    lock.content_hash_snapshot = new_snapshot


def check_drift(lock: IterationLock) -> list[Path]:
    """Return paths whose CONTENT changed since ``lock`` was acquired,
    WITHOUT releasing the lock.

    Used by the mid-iteration drift check (task #30): callers poll
    ``check_drift`` after each ``apply_finding`` so they can halt the
    loop the moment a watched file changes, rather than waiting until
    the end-of-loop release to discover it. The iteration loop's apply
    step may have already mutated the spec based on the user's
    in-flight code edits; the caller is responsible for reverting the
    apply (via ``apply_finding``'s ``pre_snapshot``) before halting.

    #31 replaced the legacy mtime check with content hashing: a
    re-saved file with unchanged bytes (some IDEs do this on every
    save, ``git checkout`` of unchanged content does this) no
    longer trips drift. False-positive elimination at the cost of a
    sha256 per watched file per check call — cheap (the watched set
    is step.files, typically a handful of small source files).

    Returns the same sorted list shape as :func:`release_lock`'s
    return value, so callers can pass it directly to
    :func:`emit_drift_warning`.
    """
    drifted: list[Path] = []
    for p_str, snap_hash in lock.content_hash_snapshot.items():
        p = Path(p_str)
        current_hash = compute_content_hash(p)
        if current_hash is None:
            # File deleted or unreadable since acquire. Match legacy
            # behavior: ignore (deleted file can't be "drifted").
            continue
        if current_hash != snap_hash:
            drifted.append(p)
    return sorted(drifted)


def release_lock(lock: IterationLock) -> list[Path]:
    """Measure end-of-hold drift and return paths whose CONTENT changed
    during the hold.

    Empty list = no drift detected. Non-empty = user (or a concurrent
    process) edited the named files while the iteration was running.
    Callers should surface this to the user -- iteration findings
    against those files may reflect the in-flight edits, not the
    pre-existing state the audit was meant to detect.

    Idempotent: a second call after the lock was already released
    returns ``[]`` without re-hashing files. This lets callers that
    release in more than one place clean up without double-emitting the
    live-edit drift warning when end-of-loop cleanup already ran.

    Touches no filesystem path -- it is a thin idempotency wrapper
    around :func:`check_drift`.
    """
    if lock.released:
        return []
    drifted = check_drift(lock)
    lock.released = True
    return drifted


def render_attributed_path_line(
    p: Path,
    repo_root: Path,
    file_to_step: "dict[Path, tuple[int, str]] | None",
) -> str:
    """Render one bullet line for a path, optionally annotated with
    the owning step.

    With ``file_to_step`` non-None, suffix the line with
    ``(step N: title)`` when the path is in the map -- gives
    operators step context without forcing them to consult the plan.
    Without the map, falls back to the bare repo-relative path.

    Used by drift warnings AND scope-guard out-of-scope warnings, so
    the function name is generic ("attributed-path-line") rather than
    drift-specific (sibling).
    """
    rel = literal_path(p, repo_root)
    if file_to_step is None:
        return rel
    step_info = file_to_step.get(p.resolve()) if p.is_absolute() else None
    if step_info is None:
        # Try the un-resolved path too -- callers don't always pass
        # resolved Path objects.
        step_info = file_to_step.get((repo_root / rel).resolve())
    if step_info is None:
        return rel
    step_id, step_title = step_info
    return f"{rel} (step {step_id}: {step_title})"


def reconcile_drift_hint(loop_name: str | None) -> str:
    """Return the re-reconcile recovery sentence for a drift warning.

    The shipped recovery for drift is to re-reconcile the affected
    surface against current code, so every drift/halt warning ends
    with the exact ``--reconcile`` command for the kind of drift seen.
    Returns a plain string with no ``plan-tool:`` prefix -- the caller
    wraps it in :func:`tool` so it routes through the styled sink.

    With a named ``loop_name`` the hint names ``detail --reconcile``
    only: every iteration loop that can emit drift is plan-side.
    Plan-authoring loops (``create`` / ``detail (step N)`` /
    ``completeness``) drift on plan/detail text, recovered by
    re-reconciling the plan. The lone ``loop_name="reconcile"`` loop is
    the ``detail --reconcile`` audit *itself* (``_save_and_walk_reconcile``
    → ``_iterate_reconcile_loop``, ``loop_name="reconcile"`` at
    ``plan_tool/cli/reconcile.py:1258``; reached from
    ``_run_detail_reconcile_path`` and the deprecated ``run --mode
    reconcile``) -- a code-is-truth plan audit recovered by re-running
    ``detail --reconcile``, not ``run --reconcile``. There is no
    code-side loop to route to ``run --reconcile``: the new
    ``run --reconcile`` (``_cmd_run_reconcile`` →
    ``_save_and_walk_run_reconcile``) lands edits inline with no
    ``iteration_session``, so it never emits drift.

    ``loop_name is None`` is the neutral halt-path default (no loop
    threaded through): it names both commands as an operator menu --
    ``detail --reconcile`` for plan-side drift, ``run --reconcile`` for
    code-side drift.
    """
    if loop_name is None:
        return (
            "Re-reconcile against current code before relying on the "
            "output: `plan-tool detail <name> --reconcile` for plan-side "
            "drift, `plan-tool run <name> --reconcile` for code-side "
            "drift."
        )
    return (
        "Re-reconcile against current code before relying on the "
        "output: `plan-tool detail <name> --reconcile`."
    )


def emit_drift_warning(
    drifted: Iterable[Path],
    *,
    repo_root: Path,
    loop_name: str,
    file=None,
    max_listed: int = 10,
    file_to_step: "dict[Path, tuple[int, str]] | None" = None,
) -> None:
    """Print a structured warning to ``file`` (default ``sys.stderr``)
    when ``drifted`` is non-empty.

    Used by every caller that wraps an iteration loop with
    :func:`acquire_lock` + :func:`release_lock` so the warning text
    stays consistent: "WARNING: N watched file(s) changed during the
    <loop_name> iteration loop. ...". Paths are rendered relative to
    ``repo_root`` when possible; the first ``max_listed`` are shown
    inline, the rest summarized as "... and N more". The warning ends
    with the :func:`reconcile_drift_hint` recovery line for
    ``loop_name`` -- a ``detail --reconcile`` pointer (every iteration
    loop is plan-side).

    When ``file_to_step`` is provided (from
    :func:`scope_guard.build_file_to_step_map`), each path line is
    suffixed with ``(step N: title)`` so operators know which step
    each drifted file belongs to without consulting the plan
   .

    No-op when ``drifted`` is empty -- callers can pass the
    release_lock return value unconditionally without a length check.
    """
    drifted_list = list(drifted)
    if not drifted_list:
        return
    out = file if file is not None else sys.stderr
    lines = [
        render_attributed_path_line(p, repo_root, file_to_step)
        for p in drifted_list
    ]
    tool(
        f"WARNING: {len(drifted_list)} watched file(s) "
        f"changed during the {loop_name} iteration loop. Findings "
        f"against these files may reflect in-flight edits rather "
        f"than pre-existing drift -- review the loop's output "
        f"skeptically before treating it as canonical:",
        stream=out,
    )
    for line in lines[:max_listed]:
        print(f"  - {line}", file=out)
    if len(lines) > max_listed:
        print(
            f"  - ... and {len(lines) - max_listed} more", file=out
        )
    tool(reconcile_drift_hint(loop_name), stream=out)


def emit_drift_halt_warning(
    drifted: Iterable[Path],
    *,
    phase: str,
    finding_id: str,
    repo_root: Path,
    file=None,
    max_listed: int = 10,
    file_to_step: "dict[Path, tuple[int, str]] | None" = None,
    loop_name: str | None = None,
) -> None:
    """Print the mid-iteration drift-halt warning to ``file`` (default
    ``sys.stderr``).

    Distinct from :func:`emit_drift_warning` (which fires at lock
    release as an informational live-edit notice): this one fires when
    the loop is HALTING mid-iteration because drift was detected
    between or during applies. The phase wording makes the consequence
    explicit so the user knows whether the apply's edits were kept.

    ``phase`` is ``"before"`` when drift was detected before
    ``apply_finding`` ran (no claude tokens spent -- the halt is
    purely preventative) or ``"during"`` when drift was detected after
    the apply (tokens spent; the just-completed apply's edits are
    KEPT, subsequent applies halted). Token preservation over strict
    spec integrity in the during-apply-drift case.

    When ``file_to_step`` is provided (from
    :func:`scope_guard.build_file_to_step_map`), each path line is
    suffixed with ``(step N: title)`` so operators know which step
    each drifted file belongs to without consulting the plan
   .

    The warning ends with the :func:`reconcile_drift_hint` recovery
    line for ``loop_name``. ``loop_name`` defaults to ``None``, which
    keeps direct callers byte-unchanged and emits the neutral
    both-commands hint (``detail --reconcile`` / ``run --reconcile``)
    as an operator menu; a named loop yields the ``detail --reconcile``
    pointer.
    """
    drifted_list = list(drifted)
    if not drifted_list:
        return
    out = file if file is not None else sys.stderr
    lines = [
        render_attributed_path_line(p, repo_root, file_to_step)
        for p in drifted_list
    ]
    if phase == "before":
        opener = (
            f"WARNING: drift detected on {len(drifted_list)} "
            f"watched file(s) BEFORE applying finding {finding_id}. "
            f"Halting iteration loop without spending claude tokens "
            f"on a likely-spurious apply. No edits made this round."
        )
    else:  # "during"
        opener = (
            f"WARNING: drift detected on {len(drifted_list)} "
            f"watched file(s) DURING apply of finding {finding_id}. "
            f"That apply's edits to plan/detail were KEPT (claude "
            f"tokens already spent; the edits may still be useful) "
            f"-- review them via `git diff` before relying on the "
            f"output. Halting subsequent applies to prevent "
            f"compounding the issue."
        )
    tool(opener, stream=out)
    print("Drifted files:", file=out)
    for line in lines[:max_listed]:
        print(f"  - {line}", file=out)
    if len(lines) > max_listed:
        print(f"  - ... and {len(lines) - max_listed} more", file=out)
    tool(reconcile_drift_hint(loop_name), stream=out)


@contextmanager
def iteration_session(
    repo_root: Path,
    *,
    enabled: bool,
    slug: str,
    command: str,
    loop_name: str,
    watched_paths: Iterable[Path],
    file_to_step: "dict[Path, tuple[int, str]] | None" = None,
    force: bool = False,
) -> Iterator[Optional[IterationLock]]:
    """Full lifecycle for one convergence-loop's iteration drift check.

    Acquires the content-hash snapshot, yields the lock, and on every
    exit path (including exceptions) checks drift via :func:`check_drift`
    and emits the live-edit warning. The four convergence loops
    (``create_plan``, ``generate_detail``, ``cmd_completeness``,
    ``_iterate_reconcile_loop``) wrap their loop body in
    ``with iteration_session(...) as lock:`` so the drift warning fires
    on every exit -- including an *unexpected* exception escaping the
    body.

    ``enabled=False`` (the lock-free production paths: create / detail
    without ``--iterate``) yields ``None``, so the caller's drift checks
    -- already guarded on ``lock is not None`` -- stay no-ops.

    The snapshot writes no lockfile and installs no signal handler;
    ``emit_drift_warning`` no-ops on an empty drift set, so it's called
    unconditionally.
    """
    if not enabled:
        yield None
        return

    lock = acquire_lock(
        repo_root,
        slug=slug,
        command=command,
        watched_paths=watched_paths,
        force=force,
    )
    try:
        yield lock
    finally:
        emit_drift_warning(
            check_drift(lock),
            repo_root=repo_root,
            loop_name=loop_name,
            file_to_step=file_to_step,
        )
