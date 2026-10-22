#!/usr/bin/env python3
"""Cut a release commit: derive the next version from the pending changelog fragments.

    uv run scripts/release.py [--minor] [--dry-run]

Runs the release-commit step of docs/RELEASING.md, which owns the bump rule,
the refusals, and what the script deliberately leaves out (tagging and pushing). It never tags or pushes, and restores the four release paths
to HEAD on any failure before the commit.

The fragment parse mirrors scriv's markdown parser because scriv consumes the
fragments; after `scriv collect`, its output categories are compared with the
derived ones, so a parser drift fails the release instead of mis-numbering it.
Not mirrored: scriv's `scriv-insert-here` start marker, which fragments do not
carry; a fragment that does is caught by that same comparison.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Sequence
from pathlib import Path

MAJOR_CATEGORIES = ("Breaking",)
MINOR_CATEGORIES = ("Added", "Changed", "Deprecated", "Removed")
PATCH_CATEGORIES = ("Fixed", "Security")
FRAGMENT_DIR = "changelog.d"
RELEASE_PATHS = ("pyproject.toml", "uv.lock", "CHANGELOG.md", FRAGMENT_DIR)
VERSION_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
VERSION_LINE_RE = re.compile(r'^version\s*=\s*"[^"]*"\s*(?:#.*)?$')
TABLE_RE = re.compile(r"^\[\[?[A-Za-z0-9_.-]+\]\]?\s*(?:#.*)?$")
ANCHOR_RE = re.compile(r"^<a id='changelog-[^']*'></a>$")

ToolRunner = Callable[[Sequence[str], Path], None]


class ReleaseError(Exception):
    pass


def _git(root: Path, *args: str) -> str:
    try:
        proc = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    except FileNotFoundError:
        raise ReleaseError("'git' is not on PATH") from None
    if proc.returncode != 0:
        raise ReleaseError(f"git {args[0]} failed: {proc.stderr.strip()}")
    return proc.stdout


def _git_ok(root: Path, *args: str) -> bool:
    return subprocess.run(["git", *args], cwd=root, capture_output=True).returncode == 0


def run_tool(argv: Sequence[str], cwd: Path) -> None:
    try:
        proc = subprocess.run(list(argv), cwd=cwd)
    except FileNotFoundError:
        raise ReleaseError(f"{argv[0]!r} is not on PATH") from None
    if proc.returncode != 0:
        raise ReleaseError(f"`{' '.join(argv)}` exited {proc.returncode}")


def fragment_sections(text: str) -> list[str | None]:
    """Section titles scriv sees in one fragment; None marks text before any heading."""
    titles: list[str | None] = []
    in_comment = False
    section_mark: str | None = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if in_comment:
            in_comment = not re.search(r"-->$", line)
            continue
        if re.search(r"^\s*<!--.*-->$", line) or re.search(r"""^<a id=(['"])[-.\w]+\1></a>$""", line):
            continue
        if re.search(r"^\s*<!--", line):
            in_comment = True
            continue
        if re.search(r"^#+ ", line) and (section_mark is None or line.startswith(section_mark)):
            titles.append(line.split(maxsplit=1)[1])
            section_mark = line.partition(" ")[0] + " "
        elif line and section_mark is None and None not in titles:
            titles.append(None)
    return titles


def fragment_paths(root: Path) -> list[Path]:
    """The files scriv collects: `*.rst` and `*.md` in the fragment directory, minus `README.*`."""
    directory = root / FRAGMENT_DIR
    found = [p for pattern in ("*.rst", "*.md") for p in directory.glob(pattern)]
    return sorted(p for p in found if not p.match("README.*"))


def derive(fragments: dict[str, list[str | None]]) -> tuple[str, dict[str, list[str]]]:
    """The bump ("major", "minor" or "patch") and which fragments carry each category."""
    known = MAJOR_CATEGORIES + MINOR_CATEGORIES + PATCH_CATEGORIES
    by_category: dict[str, list[str]] = {}
    for name, titles in fragments.items():
        if not titles:
            raise ReleaseError(f"{name} has no category heading; use one of {', '.join(known)}")
        for title in titles:
            if title is None:
                raise ReleaseError(f"{name} has text before its first category heading")
            if title not in known:
                raise ReleaseError(f"{name} has unknown category {title!r}; use one of {', '.join(known)}")
            if name not in by_category.setdefault(title, []):
                by_category[title].append(name)
    if any(c in by_category for c in MAJOR_CATEGORIES):
        bump = "major"
    else:
        bump = "minor" if any(c in by_category for c in MINOR_CATEGORIES) else "patch"
    return bump, by_category


def next_version(current: tuple[int, int, int], bump: str) -> str:
    major, minor, patch = current
    if bump == "major":
        return f"{major + 1}.0.0"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "patch":
        return f"{major}.{minor}.{patch + 1}"
    raise ReleaseError(f"unknown release bump {bump!r}")


def set_project_version(text: str, new: str) -> str:
    """Replace the `version` line under `[project]`; the caller re-reads the result."""
    lines = text.splitlines(keepends=True)
    in_project = False
    for i, line in enumerate(lines):
        stripped = line.strip()
        if TABLE_RE.match(stripped):
            in_project = stripped.split("#")[0].strip() == "[project]"
        elif in_project and VERSION_LINE_RE.match(line.rstrip("\r\n")):
            lines[i] = re.sub(r'"[^"]*"', f'"{new}"', line, count=1)
            return "".join(lines)
    raise ReleaseError('no `version = "..."` line under [project] in pyproject.toml')


def collected_titles(changelog: str, version: str) -> list[str]:
    """Category headings in the section scriv wrote for `version`, bounded by scriv's anchors."""
    lines = changelog.splitlines()
    try:
        start = lines.index(f"<a id='changelog-{version}'></a>")
    except ValueError:
        raise ReleaseError(f"scriv wrote no `changelog-{version}` section into CHANGELOG.md") from None
    titles: list[str] = []
    for line in lines[start + 1 :]:
        if ANCHOR_RE.match(line):
            break
        if line.startswith("### "):
            titles.append(line[4:].strip())
    return titles


def check_collected(root: Path, version: str, by_category: dict[str, list[str]]) -> None:
    left = fragment_paths(root)
    if left:
        raise ReleaseError(f"scriv left fragments behind: {', '.join(p.name for p in left)}")
    got = set(collected_titles((root / "CHANGELOG.md").read_text(encoding="utf-8"), version))
    if got != set(by_category):
        raise ReleaseError(
            f"scriv collected categories {sorted(got)} but the fragments parse as "
            f"{sorted(by_category)}; the bump may be wrong"
        )


def _read_version(root: Path) -> tuple[str, tuple[int, int, int], tuple[str, ...]]:
    try:
        data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ReleaseError(f"cannot read pyproject.toml: {exc}") from None
    current = data.get("project", {}).get("version", "")
    match = VERSION_RE.match(current)
    if not match:
        raise ReleaseError(f"[project].version {current!r} is not X.Y.Z; cut this release by hand")
    return current, tuple(int(g) for g in match.groups()), tuple(
        data.get("tool", {}).get("scriv", {}).get("categories", ())
    )


def cut(root: Path, *, force_minor: bool, dry_run: bool, tool: ToolRunner = run_tool) -> int:
    current, parts, configured = _read_version(root)
    if set(configured) != set(MAJOR_CATEGORIES + MINOR_CATEGORIES + PATCH_CATEGORIES):
        raise ReleaseError(
            f"[tool.scriv].categories {list(configured)} differ from the categories this script maps to a bump"
        )
    if _git(root, "status", "--porcelain").strip():
        raise ReleaseError("uncommitted changes (untracked files count); commit or stash them first")
    if not _git_ok(root, "symbolic-ref", "--quiet", "HEAD"):
        raise ReleaseError("HEAD is detached; check out a release branch first")
    if _git(root, "symbolic-ref", "--short", "HEAD").strip() == "main":
        raise ReleaseError("on main; cut the release on a branch off main and open a pull request")
    if not _git_ok(root, "rev-parse", "--verify", "--quiet", f"refs/tags/v{current}"):
        raise ReleaseError(f"no tag v{current}: the current version is unreleased; cut it by hand")
    if not _git_ok(root, "merge-base", "--is-ancestor", f"refs/tags/v{current}", "HEAD"):
        raise ReleaseError(f"tag v{current} is not an ancestor of HEAD; branch from a commit that contains it")
    paths = fragment_paths(root)
    if not paths:
        raise ReleaseError(f"no fragments in {FRAGMENT_DIR}/: nothing to release")

    for path in paths:
        if path.suffix != ".md":
            raise ReleaseError(f"{path.name} is not a Markdown fragment; the script reads .md fragments only")
    bump, by_category = derive({p.name: fragment_sections(p.read_text(encoding="utf-8")) for p in paths})
    pre_one_breaking = parts[0] == 0 and bump == "major"
    if pre_one_breaking:
        bump = "minor"
    raised = force_minor and bump == "patch"
    if raised:
        bump = "minor"
    new = next_version(parts, bump)
    if _git_ok(root, "rev-parse", "--verify", "--quiet", f"refs/tags/v{new}"):
        raise ReleaseError(f"tag v{new} already exists, so v{current} is not the latest release; check the tags")

    print(f"{current} (tag v{current}) -> {new}: {bump}{' (raised by --minor)' if raised else ''}")
    if pre_one_breaking:
        print("  Breaking changes before 1.0 use a minor bump.")
    for category in MAJOR_CATEGORIES + MINOR_CATEGORIES + PATCH_CATEGORIES:
        if category in by_category:
            print(f"  {category:<10} {', '.join(by_category[category])}")
    if dry_run:
        return 0

    pyproject = root / "pyproject.toml"
    try:
        pyproject.write_text(set_project_version(pyproject.read_text(encoding="utf-8"), new), encoding="utf-8")
        if _read_version(root)[0] != new:
            raise ReleaseError(f"pyproject.toml does not read back as version {new}")
        tool(["uv", "lock"], root)
        if _git(root, "diff", "--numstat", "--", "uv.lock").split()[:2] != ["1", "1"]:
            raise ReleaseError("`uv lock` did not change exactly plan-tool's own version line in uv.lock; commit that lock update first")
        tool(["uvx", "scriv", "collect", "--no-edit", "--no-add"], root)
        check_collected(root, new, by_category)
        _git(root, "add", "--", *RELEASE_PATHS)
        _git(root, "commit", "-q", "-m", f"Release {new}")
    except BaseException:
        if _git_ok(root, "restore", "--source=HEAD", "--staged", "--worktree", "--", *RELEASE_PATHS):
            print(f"release: restored {', '.join(RELEASE_PATHS)} to HEAD", file=sys.stderr)
        else:
            print(
                f"release: could NOT restore {', '.join(RELEASE_PATHS)}; run "
                f"`git restore --source=HEAD --staged --worktree -- {' '.join(RELEASE_PATHS)}` before retrying",
                file=sys.stderr,
            )
        raise
    print(
        f"\nCommitted Release {new}. Push this branch and open a pull request; after it merges,\n"
        f"tag the merge commit `v{new}`; pushing the tag needs the maintainer's go-ahead (docs/RELEASING.md)."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Derive the next version and commit the release.")
    parser.add_argument("--minor", action="store_true", help="raise a patch bump to a minor bump")
    parser.add_argument("--dry-run", action="store_true", help="print the derived version and change nothing")
    args = parser.parse_args(argv)
    try:
        root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip())
        return cut(root, force_minor=args.minor, dry_run=args.dry_run)
    except ReleaseError as exc:
        print(f"release: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
