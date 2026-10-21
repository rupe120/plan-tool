#!/usr/bin/env python3
"""Split the current branch into a plan-artifact branch and a code branch.

    scripts/split_pr.py IPPT-123 [--base origin/main] [--dry-run]

Builds `<KEY>-plan` (docs/implementation-plans, plan-seeds) and `<KEY>-code`
(everything else) from the branch's total change since its merge-base with
`--base`, one snapshot commit each. A squash merge discards in-branch history,
so the snapshot loses nothing a reviewer sees.

Never touches the working tree or the current branch and never pushes. It
creates every branch it reports or none, and refuses a dirty tree or an
existing target branch. Commit hooks still run on the snapshot commits.
"""
from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

PLAN_PATHS = ("docs/implementation-plans", "plan-seeds")
KEY_RE = re.compile(r"^[A-Z][A-Z0-9]*-[0-9]+$")


class SplitError(Exception):
    pass


@dataclass(frozen=True)
class PathSet:
    name: str
    spec: tuple[str, ...]
    label: str


SETS = (
    PathSet("plan", PLAN_PATHS, "plan artifacts"),
    PathSet("code", (".", *(f":(exclude){p}" for p in PLAN_PATHS)), "code, tests, and all other files"),
)


def _run(args: list[str], cwd: Path | None = None, stdin: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=cwd, input=stdin, capture_output=True)


def git(*args: str, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    proc = _run(list(args), cwd, stdin)
    if proc.returncode != 0:
        raise SplitError(f"git {args[0]} failed: {proc.stderr.decode(errors='replace').strip()}")
    return proc.stdout


def git_ok(*args: str, cwd: Path | None = None) -> bool:
    return _run(list(args), cwd).returncode == 0


def changed_paths(cwd: Path, merge_base: str, tip: str, spec: tuple[str, ...]) -> list[str]:
    out = git("diff", "--name-only", "-z", merge_base, tip, "--", *spec, cwd=cwd)
    return [p for p in out.decode(errors="replace").split("\0") if p]


def build_branch(root: Path, merge_base: str, tip: str, branch: str, pset: PathSet, message: tuple[str, str]) -> None:
    patch = git("diff", "--binary", "--full-index", merge_base, tip, "--", *pset.spec, cwd=root)
    tmp = tempfile.mkdtemp(prefix="split-pr-")
    ok = False
    try:
        git("worktree", "add", "-q", "-b", branch, tmp, merge_base, cwd=root)
        git("apply", "--index", "--whitespace=nowarn", "-", cwd=Path(tmp), stdin=patch)
        git("commit", "-q", "-m", message[0], "-m", message[1], cwd=Path(tmp))
        if not git_ok("diff", "--quiet", branch, tip, "--", *pset.spec, cwd=root):
            raise SplitError(f"{branch} does not reproduce the work branch for its paths")
        ok = True
    finally:
        git_ok("worktree", "remove", "--force", tmp, cwd=root)
        shutil.rmtree(tmp, ignore_errors=True)
        if not ok:
            git_ok("branch", "-D", branch, cwd=root)


def split(key: str, base: str, dry_run: bool) -> int:
    if not KEY_RE.match(key):
        raise SplitError(f"{key!r} is not a ticket key such as IPPT-123")
    root = Path(git("rev-parse", "--show-toplevel").decode().strip())
    if git("status", "--porcelain", cwd=root).strip():
        raise SplitError("uncommitted changes (untracked files count); commit or stash them first")
    if not git_ok("symbolic-ref", "--quiet", "HEAD", cwd=root):
        raise SplitError("HEAD is detached; check out the work branch first")
    work = git("symbolic-ref", "--short", "HEAD", cwd=root).decode().strip()
    if not git_ok("rev-parse", "--verify", "--quiet", f"{base}^{{commit}}", cwd=root):
        raise SplitError(f"base {base!r} not found; fetch it or pass --base")
    tip = git("rev-parse", "HEAD", cwd=root).decode().strip()
    merge_base = git("merge-base", base, "HEAD", cwd=root).decode().strip()

    found = [(s, f"{key}-{s.name}", changed_paths(root, merge_base, tip, s.spec)) for s in SETS]
    for pset, branch, files in found:
        if not files:
            print(f"no {pset.label} changed since {base}: {branch} not created")
    todo = [(s, b, f) for s, b, f in found if f]
    if not todo:
        print(f"no changes since {base}: nothing to split")
        return 0
    taken = [b for _, b, _ in todo if git_ok("show-ref", "--verify", "--quiet", f"refs/heads/{b}", cwd=root)]
    if taken:
        raise SplitError(f"branch already exists: {', '.join(taken)}; delete it or use another key")

    for pset, branch, files in todo:
        print(f"{'would create' if dry_run else 'creating':>12} {branch}: {len(files)} files ({pset.label})")
    if dry_run:
        return 0

    created: list[str] = []
    try:
        for pset, branch, files in todo:
            subject = f"{key}: {pset.label}"
            body = f"Snapshot of {work} at {tip[:12]}, limited to {len(files)} {pset.name} paths."
            build_branch(root, merge_base, tip, branch, pset, (subject, body))
            created.append(branch)
    except BaseException:
        for branch in created:
            git_ok("branch", "-D", branch, cwd=root)
        raise

    print(f"\nWork branch {work} is unchanged. Push each branch and open its pull request:")
    for branch in created:
        print(f"  git push -u origin {branch}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Split the current branch into plan and code branches.")
    parser.add_argument("key", help="ticket key, such as IPPT-123")
    parser.add_argument("--base", default="origin/main", help="ref to split against (default: origin/main)")
    parser.add_argument("--dry-run", action="store_true", help="list the branches and file counts, create nothing")
    args = parser.parse_args(argv)
    try:
        return split(args.key, args.base, args.dry_run)
    except SplitError as exc:
        print(f"split-pr: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
