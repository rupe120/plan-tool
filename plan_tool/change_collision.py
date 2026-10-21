"""Change-collision sidecar + pause-for-merge for drift-during-apply.

When mid-iteration drift fires AFTER ``apply_finding`` has already
written its edits to plan/detail (the "during apply" case in prior session work), the legacy behavior was to KEEP claude's edits on disk and
point the user at ``git diff``. That preserves the tokens already
spent (Lesson 2) but forces a manual merge in whatever editor the
user has open, with no 3-way framing and no protection of the user's
concurrent edits to the same files.

This module replaces "keep + git diff" with "save sidecar + restore
original + pause for merge":

1. ``save_collision_sidecars`` writes the post-apply content of each
   changed file to ``<stem>-change-collision<ext>`` next to the
   original, then restores the original to its pre-apply state.
   Token preservation (Lesson 2) is satisfied -- claude's work lands
   in the sidecar; the original goes back to a clean state.
2. ``emit_collision_summary`` prints a structured stderr summary
   listing each (original, sidecar) pair plus example merge-tool
   invocations (vimdiff, ``code --diff``, meld) so the user can
   pick whatever tool they prefer.
3. ``prompt_user_to_merge`` blocks the iteration loop with an
   interactive prompt. On Enter the caller breaks out of the
   per-finding loop and the OUTER while-loop's next iteration
   recollects findings against the merged state, continuing the
   iteration cleanly. On Ctrl-C / EOF / headless mode the caller
   falls through to the legacy halt-with-rc=2 behavior.

The whole module is on by default; the CLI flag
``--no-collision-sidecar`` opts back into the legacy "keep claude's
edits on disk + ``git diff``" behavior. Headless runs (`-y` or
non-TTY) skip the interactive pause and fall through to legacy
halt automatically -- there's no human to merge in CI.

Module dependencies: stdlib plus ``plan_tool.pathutil`` for lexical displays
and ``plan_tool.style`` for diagnostics. The caller passes
``apply_result.pre_snapshot`` directly so this module doesn't import
``plan_tool.launcher``.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from plan_tool.pathutil import literal_path
from plan_tool.style import tool


@dataclass(frozen=True)
class CollisionSidecar:
    """One (original, sidecar) pair produced by
    :func:`save_collision_sidecars`.

    ``pre_content`` is the original's pre-apply content (None when
    the file didn't exist before apply_finding -- in that case the
    "restore" deletes the file). Carried so callers / tests can
    verify the restore worked without re-reading from disk.
    """

    original: Path
    sidecar: Path
    pre_content: Optional[str]


def collision_sidecar_path(
    original: Path, *, n: int = 1,
) -> Path:
    """Compute the sidecar path: ``<stem>-change-collision<suffix>``
    next to ``original``.

    ``original.suffix`` includes the leading dot (e.g. ``.py``); if
    the file has no extension, the sidecar has none either
    (``Makefile`` → ``Makefile-change-collision``).

    Pass ``n > 1`` to get a numbered variant
    (``<stem>-change-collision-2<suffix>``) so consecutive drift
    halts on the same file don't silently overwrite a prior
    unmerged sidecar (Bug 2 from session-4 review).
    ``allocate_sidecar_path`` is the higher-level helper that picks
    the smallest available ``n``; callers should prefer that.

    Examples:

    - ``plans/2-foo-bar.md`` → ``plans/2-foo-bar-change-collision.md``
    - ``src/cli.py`` → ``src/cli-change-collision.py``
    - ``Makefile`` → ``Makefile-change-collision``
    - with ``n=2``: ``src/cli.py`` → ``src/cli-change-collision-2.py``
    """
    if n <= 1:
        marker = "-change-collision"
    else:
        marker = f"-change-collision-{n}"
    return original.with_name(f"{original.stem}{marker}{original.suffix}")


def allocate_sidecar_path(original: Path, *, max_n: int = 99) -> Path:
    """Return the smallest-``n`` sidecar path that doesn't already
    exist on disk.

    On first drift collision, ``n=1`` → ``<stem>-change-collision<ext>``.
    On second (if the prior sidecar is still on disk because the user
    hasn't merged it yet), ``n=2`` → ``<stem>-change-collision-2<ext>``.
    And so on up to ``max_n`` (a safety cap; the unlikely failure mode
    where every numbered slot is full surfaces as an exception so the
    caller can decide whether to overwrite or abort).

    Avoids the prior overwrite-silently behavior (Bug 2) so an
    operator who runs a noisy iteration and accumulates several
    unmerged sidecars can still review them later by name.
    """
    for n in range(1, max_n + 1):
        candidate = collision_sidecar_path(original, n=n)
        if not candidate.exists():
            return candidate
    raise RuntimeError(
        f"collision-sidecar allocation exhausted at n={max_n} for "
        f"{original}; all numbered slots are occupied. Clean up "
        f"existing `*-change-collision*` files in {original.parent} "
        f"before re-running."
    )


def save_collision_sidecars(
    pre_snapshot: "dict[Path, Optional[str]]",
    *,
    file=None,
) -> list[CollisionSidecar]:
    """For each file in ``pre_snapshot`` whose current content
    differs from the pre-apply state, write the current content to
    a numbered sidecar and restore the original. Returns the list
    of sidecars written.

    Files whose current content matches the pre-apply state are
    skipped (no edit landed; nothing to save).

    Files that didn't exist pre-apply but exist now are saved to a
    sidecar; the new file is removed (matches the snapshot's
    ``None → delete-on-restore`` semantics).

    Files that EXISTED pre-apply but were DELETED by apply_finding
    are restored (no sidecar; there's no post-apply content to
    save) and NOT included in the returned list (Bug 5 from session
    -4 review: the prior render of ``<orig> ⇄ <orig>`` was
    confusing; better to silently restore unusual deletions).

    Sidecar paths are allocated via
    :func:`allocate_sidecar_path` so consecutive drifts on the same
    original file get numbered slots
    (``<stem>-change-collision-2<ext>``,
    ``<stem>-change-collision-3<ext>``, …) rather than silently
    overwriting a prior unmerged sidecar (Bug 2).

    Best-effort:

    - Sidecar write failure (full disk, permissions, RuntimeError
      from allocator exhaustion): log to stderr and skip that file.
      The original is NOT restored in that case -- better to keep
      claude's edits than to lose both the proposal AND the work,
      because token preservation (Lesson 2) outranks tree
      cleanliness on the failure path.
    - Restore failure after a successful sidecar write: log to
      stderr; both files may then carry claude's edits. The
      caller's stderr summary makes the gap visible.
    - ``KeyboardInterrupt`` between sidecar write and restore (Bug
      7): log the partially-written state to stderr before
      re-raising so the operator knows where to look for the
      orphan sidecar.
    """
    out = file if file is not None else sys.stderr
    sidecars: list[CollisionSidecar] = []

    for original, pre_content in pre_snapshot.items():
        try:
            current: Optional[str] = original.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        except OSError as exc:
            tool(
                f"collision-sidecar read failed for "
                f"{original}: {exc}; leaving in place",
                stream=out,
            )
            continue

        if current == pre_content:
            # No change landed for this path; nothing to save.
            continue

        if current is None:
            # apply_finding DELETED the file (unusual). Restore the
            # original; no sidecar to write because there's no
            # post-apply content. Don't record in sidecars -- the
            # caller's summary would otherwise render a useless
            # ``<orig> ⇄ <orig>`` row (Bug 5).
            try:
                if pre_content is not None:
                    original.write_text(pre_content, encoding="utf-8")
            except OSError as exc:
                tool(
                    f"failed to restore {original} after "
                    f"apply_finding deleted it ({exc}); the file is "
                    f"still missing -- recover from git",
                    stream=out,
                )
            continue

        try:
            sidecar = allocate_sidecar_path(original)
        except RuntimeError as exc:
            tool(
                f"collision-sidecar allocation failed for "
                f"{original}: {exc}; keeping claude's edits in place "
                f"on {original.name} (legacy keep-on-drift behavior)",
                stream=out,
            )
            continue

        try:
            sidecar.write_text(current, encoding="utf-8")
        except OSError as exc:
            tool(
                f"collision-sidecar write failed for "
                f"{sidecar}: {exc}; keeping claude's edits in "
                f"place on {original.name} (legacy keep-on-drift "
                f"behavior)",
                stream=out,
            )
            # Don't restore -- leave claude's edits on disk so the
            # user can recover via git diff (Lesson 2: token
            # preservation > tree cleanliness).
            continue

        # Sidecar written. Restore original. If KeyboardInterrupt
        # fires here, log the orphan-sidecar state before re-
        # raising so the operator can find it (Bug 7).
        try:
            try:
                if pre_content is None:
                    if original.exists():
                        original.unlink()
                else:
                    original.write_text(pre_content, encoding="utf-8")
            except OSError as exc:
                tool(
                    f"failed to restore {original} after "
                    f"writing sidecar ({exc}); BOTH the original and "
                    f"the sidecar may carry claude's edits -- "
                    f"inspect carefully",
                    stream=out,
                )
        except KeyboardInterrupt:
            tool(
                f"caught SIGINT mid-collision-save; "
                f"sidecar {sidecar} was written but the original "
                f"{original} may not have been restored. Inspect "
                f"both files before re-running.",
                stream=out,
            )
            raise

        sidecars.append(
            CollisionSidecar(
                original=original,
                sidecar=sidecar,
                pre_content=pre_content,
            )
        )

    return sidecars


def emit_collision_summary(
    sidecars: list[CollisionSidecar],
    *,
    repo_root: Path,
    file=None,
) -> None:
    """Print the structured stderr summary listing each
    ``(original, sidecar)`` pair plus example merge-tool invocations.

    No-op when ``sidecars`` is empty.
    """
    if not sidecars:
        return
    out = file if file is not None else sys.stderr

    tool(
        f"drift collision -- saved claude's plan/detail "
        f"edits to {len(sidecars)} sidecar file(s). Originals "
        f"restored to pre-apply state. NOTE: your source-file edits "
        f"(the changes on watched ``step.files`` that triggered "
        f"this drift) are untouched on disk -- the sidecar(s) below "
        f"only carry claude's plan/detail proposals. Merge the "
        f"sidecars manually:",
        stream=out,
    )
    for s in sidecars:
        print(
            f"  - {literal_path(s.original, repo_root)}  ⇄  "
            f"{literal_path(s.sidecar, repo_root)}",
            file=out,
        )
    print("", file=out)
    first = sidecars[0]
    orig = literal_path(first.original, repo_root)
    side = literal_path(first.sidecar, repo_root)
    print("Example merge commands (pick any tool):", file=out)
    print(f"  code --diff {orig} {side}", file=out)
    print(f"  vimdiff {orig} {side}", file=out)
    print(f"  meld {orig} {side}", file=out)


def prompt_user_to_merge(
    sidecars: list[CollisionSidecar],
    *,
    yes: bool = False,
    input_fn: Callable[[str], str] = input,
    isatty_fn: Callable[[], bool] = lambda: sys.stdin.isatty(),
    file=None,
) -> bool:
    """Block the caller until the user merges (returns True) or
    aborts (returns False).

    Returns:
    - ``True`` when the user pressed Enter after merging. The caller
      should break out of the per-finding loop; the outer iteration
      while-loop re-collects findings against the merged state and
      proceeds.
    - ``False`` when the prompt is skipped (``yes=True`` or non-TTY)
      OR when the user aborted (EOF / Ctrl-D). The caller falls
      through to the legacy halt-with-rc=2 behavior.

    Ctrl-C during the prompt re-raises ``KeyboardInterrupt`` --
    handled by the iteration entry point's SIGINT handler,
    which releases the lock cleanly and exits. The user's
    intent there is "abort everything", which is the same outcome
    as ``False`` from this function but via a different code path.

    ``input_fn`` and ``isatty_fn`` are injectable so tests can drive
    the prompt without a TTY.
    """
    if not sidecars:
        return False
    out = file if file is not None else sys.stderr

    if yes or not isatty_fn():
        # Headless: skip the pause and signal "no merge".
        tool(
            "skipping merge pause (non-interactive); "
            "halting iteration. Re-run after merging the sidecar "
            "file(s) above.",
            stream=out,
        )
        return False

    try:
        response = input_fn(
            "\nplan-tool: merge the sidecar file(s) above, then "
            "press Enter to continue iteration (or Ctrl-D to abort)> "
        )
    except EOFError:
        tool(
            "merge prompt aborted via EOF; halting "
            "iteration. Re-run after merging.",
            stream=out,
        )
        return False

    # Any non-empty answer that starts with 'n' or 'a' (abort) opts
    # out; empty / Enter / anything else = continue. Generous on the
    # affirmative side so the user doesn't get tripped up by extra
    # whitespace.
    stripped = response.strip().lower()
    if stripped in ("n", "no", "a", "abort", "q", "quit"):
        tool(
            "merge prompt declined; halting iteration. "
            "Re-run after merging.",
            stream=out,
        )
        return False

    tool(
        "merge acknowledged; continuing iteration with "
        "the merged state.",
        stream=out,
    )
    return True


def handle_drift_collision(
    pre_snapshot: "dict[Path, Optional[str]]",
    *,
    repo_root: Path,
    yes: bool = False,
    input_fn: Callable[[str], str] = input,
    isatty_fn: Callable[[], bool] = lambda: sys.stdin.isatty(),
    file=None,
) -> bool:
    """One-shot helper: save sidecars + emit summary + prompt.

    Returns ``True`` when the user merged and wants to continue
    iteration. Returns ``False`` when the iteration should halt
    (no collisions, headless, user declined, or EOF). Each iteration
    entry point's post-apply drift halt branch invokes this helper
    and branches on the return value.

    The four steps (save / summary / prompt / signal) are also
    exposed individually for tests that need finer control over
    the side effects.
    """
    sidecars = save_collision_sidecars(pre_snapshot, file=file)
    if not sidecars:
        # No file changed (apply_finding wrote nothing, or every
        # change had already been undone). Treat as "no collision";
        # caller proceeds with legacy halt.
        return False
    emit_collision_summary(sidecars, repo_root=repo_root, file=file)
    return prompt_user_to_merge(
        sidecars,
        yes=yes,
        input_fn=input_fn,
        isatty_fn=isatty_fn,
        file=file,
    )
