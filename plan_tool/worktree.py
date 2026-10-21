"""Pure worktree path/base resolution leaf — no git shell-out.

Answers the three pure questions the worktree command group needs before
touching git:

- *where is the worktree base?* — :func:`worktree_base` (project config →
  user config → a default **sibling** of the repo, never inside it)
- *what path does a plan's slug map to?* — :func:`derive_worktree_path`
  (deterministic ``base / slug``, so ``list`` / ``remove`` / ``prune``
  recompute it with no stored state)
- *what is sitting at that path right now?* — :func:`classify_target`
  (a pure filesystem classifier: absent / empty / non-empty / not-a-dir)

The git-aware "is this a *healthy reusable* worktree of the expected
kind/branch" decision needs ``worktree_list`` / a ``.git`` probe and stays
in the worktree command module — this leaf ships only the filesystem half.

Config-path reuse: the ``.plan-tool/config.json`` (project) and
``~/.plan-tool/config.json`` (user) locations come from
:func:`plan_tool.project_config.project_config_path` /
:func:`~plan_tool.project_config.user_config_path` — one source for the
config-file layout.

Per-level tolerance mirrors :func:`plan_tool.project_config._read_level`:
a malformed level is treated as "unset" and falls through silently — a
broken user file never crashes an otherwise-fine project. The one place
this leaf warns is the inside-repo guard, which fires on a *valid* string
that resolves to a forbidden location.

Cycle-free leaf: imports only stdlib plus the two public config-path
helpers from :mod:`plan_tool.project_config`. It calls no git, reads no
plan files, and takes ``repo_root`` / ``slug`` as parameters (never
resolves them itself) so it stays hermetic against a ``tmp_path``.
"""

from __future__ import annotations

import enum
import json
import sys
from pathlib import Path
from typing import Optional

from plan_tool.project_config import project_config_path, user_config_path

# The JSON key holding the worktree base, at the config file's top level
# (not nested under a block like ``branch_awareness``). Exported so step 3,
# docs, and tests reference one name.
WORKTREE_BASE_KEY = "worktree_base"


def default_worktree_base(repo_root: Path) -> Path:
    """Return ``<repo-parent>/<repo-name>.worktrees`` — a repo sibling.

    For a repo at ``/home/u/plan-tool`` this is
    ``/home/u/plan-tool.worktrees``. ``repo_root`` is resolved first so
    ``.name`` / ``.parent`` are stable regardless of how the caller passed
    it. Structurally never inside the repo, so it always passes the
    inside-repo guard.
    """
    root = repo_root.resolve()
    return root.parent / f"{root.name}.worktrees"


def _read_worktree_base(path: Path) -> Optional[str]:
    """Return the raw ``worktree_base`` string for one config file, or ``None``.

    ``None`` ("level unset") on any malformed shape: file absent,
    ``OSError``, ``json.JSONDecodeError``, top-level value not a ``dict``,
    key missing, or value not a non-empty ``str``. **Never raises.**

    The worktree analog of :func:`plan_tool.project_config._read_level`,
    keyed on the top-level :data:`WORKTREE_BASE_KEY` scalar rather than a
    nested block. A present-but-invalid value collapses to ``None`` here
    (indistinguishable from key-absent), so :func:`worktree_base` has no
    warn-once branch — it simply falls through to the next level.
    """
    try:
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data.get(WORKTREE_BASE_KEY)
    if not isinstance(raw, str) or not raw:
        return None
    return raw


def _base_inside_repo(base: Path, repo_root: Path) -> bool:
    """True when ``base`` resolves to ``repo_root`` itself or under it.

    A worktree under the main working tree corrupts git; the guard rejects
    such a configured base. Both paths are already resolved by the caller.
    """
    return base == repo_root or repo_root in base.parents


def worktree_base(repo_root: Path) -> Path:
    """Resolve the worktree base: project config → user config → default.

    Per-level tolerance, never raises. A malformed level (see
    :func:`_read_worktree_base`) is treated as unset and falls through to
    the next; an all-levels-unset state yields
    :func:`default_worktree_base`.

    A configured value is ``Path(raw).expanduser()``, resolved against
    ``repo_root.parent`` if relative, then ``.resolve()``. If it lands on
    ``repo_root`` or under it, the inside-repo guard warns to stderr and
    returns the default — an inside-repo base goes **straight to the
    default**, it does not fall through to the next level (the guard fires
    on the resolved location of the level that supplied the value, not on
    validity).
    """
    root = repo_root.resolve()
    for path in (project_config_path(root), user_config_path()):
        raw = _read_worktree_base(path)
        if raw is None:
            continue
        base = Path(raw).expanduser()
        if not base.is_absolute():
            base = root.parent / base
        base = base.resolve()
        if _base_inside_repo(base, root):
            print(
                f"{WORKTREE_BASE_KEY} in {path} resolves inside the repo "
                f"({base}); using {default_worktree_base(root)}",
                file=sys.stderr,
            )
            return default_worktree_base(root)
        return base

    return default_worktree_base(root)


def _validate_slug(slug: str) -> None:
    """Reject a slug that could escape the base directory as a path segment.

    Raises ``ValueError`` on: a non-``str``, empty / whitespace-only, a
    value containing a path separator (``/`` or the OS separator), or a
    ``..`` traversal component. Callers derive the slug from
    :func:`plan_tool.locator.slug_from_filename` (a file stem that normally
    can't contain ``/``), but this is the path-safety boundary and is cheap.
    """
    if not isinstance(slug, str) or not slug.strip():
        raise ValueError(f"worktree slug must be a non-empty string, got {slug!r}")
    if "/" in slug or "\\" in slug:
        raise ValueError(f"worktree slug must not contain a path separator: {slug!r}")
    if ".." in Path(slug).parts:
        raise ValueError(f"worktree slug must not contain a '..' component: {slug!r}")


def derive_worktree_path(
    repo_root: Path, slug: str, *, base: Optional[Path] = None
) -> Path:
    """Return ``base / slug``, deterministic for the same inputs.

    ``base`` defaults to :func:`worktree_base` when not supplied; passing
    it (e.g. an already-resolved ``--base``) skips config re-reads and
    keeps the function pure over its inputs. The slug is validated via
    :func:`_validate_slug` before joining, so a traversal-bearing slug
    raises rather than escaping the base.
    """
    _validate_slug(slug)
    if base is None:
        base = worktree_base(repo_root)
    return base / slug


class TargetState(str, enum.Enum):
    """What is on disk at a candidate worktree path (filesystem-only)."""

    ABSENT = "absent"  # nothing exists at the path
    EMPTY = "empty"  # a directory exists with no entries
    NON_EMPTY = "non-empty"  # a directory exists with at least one entry
    NOT_A_DIR = "not-a-dir"  # something exists but is not a directory


def classify_target(path: Path) -> TargetState:
    """Report *what is on disk* at ``path`` — not whether it's a healthy worktree.

    The pure half of step 3's reuse-vs-fail tiebreak; the git-aware
    kind/branch check lives with the worktree command. An unreadable
    directory (``iterdir`` raises ``OSError``) is treated as
    :attr:`TargetState.NON_EMPTY` — fail safe, so a caller never overwrites
    a dir it can't inspect.
    """
    if not path.exists():
        return TargetState.ABSENT
    if not path.is_dir():
        return TargetState.NOT_A_DIR
    try:
        has_entry = any(path.iterdir())
    except OSError:
        return TargetState.NON_EMPTY
    return TargetState.NON_EMPTY if has_entry else TargetState.EMPTY
