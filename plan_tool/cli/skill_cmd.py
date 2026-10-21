"""Setup command module — the ``install-skill`` verb.

Wires the bundled ``integrations/<backend>/SKILL.md`` router and the
single shared ``integrations/shared/DIRECTIVES.md`` reference (the agent
instruction sheet plus the rules it cites) into a project — or the
user's home — so **Claude Code** / Codex / Cursor can orchestrate
plan-tool. The CLI itself is standalone; this is purely an opt-in
convenience, never part of project bootstrap.

A leaf command module: imports only the cycle-free helpers
(:mod:`plan_tool.cli.context` for repo-root resolution,
:func:`plan_tool.backend._packaged_integrations_dir` for the bundled
sources, :mod:`plan_tool.fileio` for the atomic ``--copy`` write) and the
parser ``Handler`` type — never :mod:`plan_tool.cli.app`.
No claude call; the only side effect is creating the two skill files
(symlink or copy) under the chosen root.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Literal, NamedTuple

from plan_tool.backend import _packaged_integrations_dir
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler
from plan_tool.fileio import atomic_write_bytes
from plan_tool.style import error, info, success, warn

# Both are valid Claude-Code skill roots (see scope_guard.SKILL_AGENT_ROOTS);
# ``.claude`` is the current convention, so it's the default.
_VALID_ROOTS = (".claude", ".agents")

# Codex scans ``.agents/skills`` (not ``.claude``) and skips a symlinked
# SKILL.md without logging, so its integration defaults to ``.agents`` and
# always copies. Measured 2026-10-06 on codex-cli 0.160.1.
_CODEX_ROOT = ".agents"


def _bundled_source(subdir: str, filename: str) -> Path | None:
    """Locate a bundled ``integrations/<subdir>/<filename>`` file.

    Returns ``None`` when the integrations tree or the file itself is
    absent (a broken install / unknown integration); the caller turns
    that into a user-facing error.
    """
    root = _packaged_integrations_dir()
    if root is None:
        return None
    candidate = root / subdir / filename
    return candidate if candidate.is_file() else None


def _bundled_skill_source(integration: str) -> Path | None:
    """Locate the bundled ``integrations/<integration>/SKILL.md``."""
    return _bundled_source(integration, "SKILL.md")


def _bundled_shared_directives_source() -> Path | None:
    """Locate the single bundled ``integrations/shared/DIRECTIVES.md``.

    Unlike :func:`_bundled_skill_source`, this is not per-integration —
    every backend's router cites the same shared reference.
    """
    return _bundled_source("shared", "DIRECTIVES.md")


class _SkillFile(NamedTuple):
    """One (source, dest, label) triple in the set ``install-skill`` installs."""

    source: Path
    dest: Path
    label: str


_DestStatus = Literal["missing", "already", "mode-switch", "collision"]


def _classify_dest(dest: Path, source: Path, *, copy: bool) -> _DestStatus:
    """Classify ``dest`` against ``source`` and the requested mode.

    See docs/ARCHITECTURE.md's "Installed skill" section for what each
    status means and why ``mode-switch`` still requires ``--force``.
    """
    if not (dest.exists() or dest.is_symlink()):
        return "missing"
    is_our_symlink = dest.is_symlink() and _resolve_or_none(dest) == source.resolve()
    is_our_copy = not dest.is_symlink() and dest.is_file() and _same_bytes(dest, source)
    matches_requested = is_our_copy if copy else is_our_symlink
    matches_other_mode = is_our_symlink if copy else is_our_copy
    if matches_requested:
        return "already"
    if matches_other_mode:
        return "mode-switch"
    return "collision"


def cmd_install_skill(args: argparse.Namespace) -> int:
    """Install the bundled agent skill and its shared ``DIRECTIVES.md`` as one set.

    Every destination is classified before any of them is written, so a
    foreign collision on one path refuses the whole set rather than
    leaving it half-installed — that guarantee covers pre-existing
    collisions, not a write failing partway through (disk full,
    permission revoked). See ``README.md``'s install section for the
    symlink/``--copy``/``--user`` tradeoffs. No claude call.
    """
    skill_source = _bundled_skill_source(args.integration)
    if skill_source is None:
        error(
            f"no bundled SKILL.md for integration {args.integration!r} "
            "(expected integrations/"
            f"{args.integration}/SKILL.md in the plan-tool install)."
        )
        return 1

    directives_source = _bundled_shared_directives_source()
    if directives_source is None:
        error(
            "no bundled shared DIRECTIVES.md (expected "
            "integrations/shared/DIRECTIVES.md in the plan-tool install)."
        )
        return 1

    codex = args.integration == "codex"
    root_name = args.root or (_CODEX_ROOT if codex else ".claude")
    copy = args.copy or codex
    if args.user:
        base = Path.home() / root_name
        location = f"~/{root_name}"
    else:
        repo_root = _resolve_cmd_repo_root(args)
        base = repo_root / root_name
        location = f"{root_name} (under {repo_root})"

    dest_dir = base / "skills" / "plan-tool"
    items = [
        _SkillFile(skill_source, dest_dir / "SKILL.md", "skill"),
        _SkillFile(directives_source, dest_dir / "DIRECTIVES.md", "shared reference"),
    ]

    # Classify every destination before writing any of them (see
    # _classify_dest for what each status means and why mode-switch still
    # needs --force).
    classified = [
        (item, _classify_dest(item.dest, item.source, copy=copy))
        for item in items
    ]
    collisions = [item.dest for item, status in classified if status == "collision"]
    mode_switches = [item.dest for item, status in classified if status == "mode-switch"]
    # Only "collision" can be a directory -- unlink() can't clear one.
    unremovable = [dest for dest in collisions if dest.is_dir() and not dest.is_symlink()]
    if unremovable:
        paths = ", ".join(str(dest) for dest in unremovable)
        error(f"a directory occupies the destination, remove it by hand first: {paths}")
        return 2
    if not args.force and (collisions or mode_switches):
        if collisions:
            paths = ", ".join(str(dest) for dest in collisions)
            error(f"a foreign file exists, refusing without --force: {paths}")
        if mode_switches:
            paths = ", ".join(str(dest) for dest in mode_switches)
            error(
                "already installed in the other mode (symlink vs --copy), "
                f"refusing to switch without --force: {paths}"
            )
        return 2

    # Write only what needs writing; "already" items are skipped below.
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        error(f"cannot create {dest_dir}: {exc}")
        return 2
    installed_any = False
    for item, status in classified:
        if status == "already":
            info(f"already installed: {item.dest}")
            continue
        try:
            if status in ("collision", "mode-switch"):
                item.dest.unlink()
            if copy:
                atomic_write_bytes(item.dest, item.source.read_bytes())
                success(f"copied {item.label} → {item.dest}")
            else:
                resolved_source = item.source.resolve()
                os.symlink(resolved_source, item.dest)
                success(f"linked {item.label} → {item.dest}")
                info(f"  → {resolved_source}")
        except OSError as exc:
            error(f"cannot install {item.dest}: {exc}")
            return 2
        installed_any = True

    if installed_any:
        info(f"  location: {location}")
        if copy:
            info(
                "  (committed copies travel with the repo but go stale on a "
                "plan-tool upgrade — re-run install-skill --copy --force to "
                "refresh: a changed source no longer byte-matches the "
                "committed copy, so it classifies as a collision)"
            )
        elif not args.user:
            warn(
                "these symlinks point outside the repo (into the plan-tool "
                "clone), so they're machine-local — they won't survive a "
                "fresh clone or run in CI. Use --copy to commit the skill, "
                "or --user to install it once for every project."
            )

    return 0


def _resolve_or_none(link: Path) -> Path | None:
    """Resolve a symlink's target, or ``None`` if it dangles."""
    try:
        return link.resolve(strict=True)
    except OSError:
        return None


def _same_bytes(a: Path, b: Path) -> bool:
    """True when two files have byte-identical content."""
    try:
        return a.read_bytes() == b.read_bytes()
    except OSError:
        return False


def register(subparsers) -> dict[str, Handler]:
    """Add the ``install-skill`` subparser and return its dispatch map."""
    p = subparsers.add_parser(
        "install-skill",
        help=(
            "install the bundled Claude Code / Codex / Cursor skill into a "
            "project (opt-in; the CLI is standalone and needs no skill)"
        ),
    )
    p.add_argument(
        "--root",
        choices=_VALID_ROOTS,
        default=None,
        help=(
            "skill root to install under (default: .claude; .agents for "
            "--integration codex, which does not read .claude)"
        ),
    )
    p.add_argument(
        "--integration",
        choices=("claude", "codex", "cursor"),
        default="claude",
        help="which bundled SKILL.md to install (default: claude)",
    )
    p.add_argument(
        "--user",
        action="store_true",
        help=(
            "install under ~/<root> (e.g. ~/.claude) so every project "
            "the operator drives discovers it — no per-project step"
        ),
    )
    p.add_argument(
        "--copy",
        action="store_true",
        help=(
            "copy the file instead of symlinking — the skill travels with "
            "the repo (committable), but goes stale on a plan-tool upgrade; "
            "always on for --integration codex, which ignores a symlinked "
            "SKILL.md"
        ),
    )
    p.add_argument(
        "--force",
        action="store_true",
        help=(
            "overwrite destination files that point elsewhere — only the "
            "colliding paths are unlinked; an already-correct sibling is "
            "left untouched"
        ),
    )

    return {"install-skill": cmd_install_skill}
