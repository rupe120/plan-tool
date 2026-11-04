"""Pre-run check: the plan and its whole detail bundle are on the default branch's remote ref.

Read-only and git-only. A merged plan pull request is the review that must
precede ``run``, so this reads that fact instead of judging the plan. See
docs/how-to/pipeline/run.md.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from plan_tool.parser import ParseError, ValidationError, parse_plan, parse_plan_text
from plan_tool.schema import Plan, StepScope

NO_REMOTE = "no origin remote"
_FALLBACK_REFS = ("origin/main", "origin/master")
_RUN_MANAGED_FIELDS = ("status", "status_note")


@dataclass(frozen=True)
class MergeCheck:
    default_ref: Optional[str] = None
    unverifiable: Optional[str] = None
    missing: tuple[str, ...] = ()
    drifted: tuple[str, ...] = ()


def default_branch_name(ref: str) -> str:
    return ref.split("/", 1)[1]


def _git(root: Path, *args: str, stdin: Optional[bytes] = None) -> Optional[bytes]:
    try:
        proc = subprocess.run(["git", *args], cwd=root, input=stdin, capture_output=True)
    except OSError:
        return None
    return proc.stdout if proc.returncode == 0 else None


def _default_ref(root: Path) -> Optional[str]:
    head = _git(root, "symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD")
    candidates = ([head.decode().strip()] if head and head.strip() else []) + list(_FALLBACK_REFS)
    for ref in candidates:
        if _git(root, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") is not None:
            return ref
    return None


def _files_on_ref(root: Path, ref: str, paths: list[str]) -> set[str]:
    query = "".join(f"{ref}:{p}\n" for p in paths).encode()
    out = _git(root, "cat-file", "--batch-check", stdin=query) or b""
    lines = out.decode(errors="replace").splitlines()
    return {p for p, line in zip(paths, lines) if line.split()[1:2] == ["blob"]}


def _without_run_managed(plan: Plan) -> dict:
    data = plan.model_dump(mode="json")
    for holder in (data, *data["steps"]):
        for key in _RUN_MANAGED_FIELDS:
            holder.pop(key, None)
    return data


def _plan_drifted(root: Path, ref: str, rel: str, current: Plan) -> bool:
    merged = _git(root, "show", f"{ref}:{rel}")
    try:
        return merged is None or _without_run_managed(parse_plan_text(merged.decode())) != _without_run_managed(current)
    except (ParseError, ValidationError):
        return True


def _detail_drifted(root: Path, ref: str, rel: str) -> bool:
    merged = _git(root, "show", f"{ref}:{rel}")
    try:
        return merged != (root / rel).read_bytes()
    except OSError:
        return True


def check_plan_merged(repo_root: Path, plan_path: Path) -> MergeCheck:
    if _git(repo_root, "remote", "get-url", "origin") is None:
        return MergeCheck(unverifiable=NO_REMOTE)
    ref = _default_ref(repo_root)
    if ref is None:
        return MergeCheck(unverifiable="origin has no resolvable default branch (run `git fetch`)")
    try:
        rel = plan_path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return MergeCheck(default_ref=ref, unverifiable="the plan is outside the repository")
    try:
        plan = parse_plan(plan_path)
    except (OSError, ParseError, ValidationError):
        return MergeCheck(default_ref=ref, unverifiable="the plan does not parse")

    committed = [s for s in plan.steps if s.scope == StepScope.COMMITTED]
    undeclared = tuple(f"step {s.id}: no detail file declared" for s in committed if not s.detail)
    details = [s.detail for s in committed if s.detail]
    wanted = list(dict.fromkeys([rel, *details]))
    present = _files_on_ref(repo_root, ref, wanted)
    missing = tuple(p for p in wanted if p not in present) + undeclared
    drifted = tuple(
        p for p in wanted
        if p in present and (_plan_drifted(repo_root, ref, p, plan) if p == rel else _detail_drifted(repo_root, ref, p))
    )
    return MergeCheck(default_ref=ref, missing=missing, drifted=drifted)
