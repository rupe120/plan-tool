"""Read-only path predicates and display helpers shared by leaf modules.

A stdlib-only leaf: imports nothing first-party, so any module — including
the cycle-sensitive ones — can use it. Kept separate from
:mod:`plan_tool.fileio`, which owns *writing* files; every function here
only reads (``Path.resolve``, a directory listing, an mtime stat), never
writes.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


def normalize_declared_path(entry: str) -> str:
    """Return the comparison identity for one declared plan path.

    Scope declarations may carry a trailing creation annotation or a leading
    current-directory segment; neither changes the file they name. Strips
    both but leaves ``..`` segments untouched — collapsing them lexically
    here (rather than at :func:`is_within`'s resolve-first, symlink-aware
    point) would let a ``..`` through a symlinked directory land somewhere
    that later differs from what ``Path.resolve()`` would actually reach.
    """
    clean = entry.split("(", 1)[0].strip()
    return Path(clean).as_posix() if clean else ""


def is_within(path: Path, root: Path) -> bool:
    """True when ``path`` resolves to somewhere inside ``root``.

    Both sides are resolved first, so symlinks and ``..`` segments are
    judged by where they actually land rather than how they are spelled.
    """
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def latest_seed_archive(path: Path) -> Optional[Path]:
    """The most recent archived generation of ``path``, or ``None``.

    Looks for ``<dir>/archive/<stem>.replaced[.N]<suffix>`` — the naming
    ``create --from-existing`` uses when it moves a seed there right after
    publishing the new plan (see ``create.py``'s ``archive_existing_
    source``). A reader resolving a seed by its original path should check
    here before treating a missing file as "never had one."
    """
    archive_dir = path.parent / "archive"
    if not archive_dir.is_dir():
        return None
    prefix = f"{path.stem}.replaced"
    candidates = [
        candidate
        for candidate in archive_dir.iterdir()
        if candidate.is_file()
        and candidate.suffix == path.suffix
        and candidate.name.startswith(prefix)
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)


def display_path(path: Path, repo_root: Optional[Path]) -> str:
    """Render ``path`` repo-relative when possible, else as an absolute string.

    Keeps terminal output readable on a narrow terminal — long absolute
    paths in a nested monorepo otherwise wrap and obscure which artifacts
    moved. ``repo_root=None`` (no repo context) and a ``path`` outside the
    repo both fall back to the full string form.

    Returns the platform string form, not POSIX: contrast
    ``cli/console.py``'s ``_repo_rel``, which emits ``as_posix()`` for the
    machine-readable surfaces. For a warning that must name a dangling
    symlink's own link path rather than its (missing) resolved target, use
    :func:`literal_path` instead.
    """
    if repo_root is None:
        return str(path)
    try:
        return str(path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        return str(path)


def literal_path(path: Path, repo_root: Path) -> str:
    """Render ``path`` repo-relative without resolving it first.

    Unlike :func:`display_path`, preserves a dangling symlink's lexical link
    path for warnings that name the link rather than its target.
    """
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)
