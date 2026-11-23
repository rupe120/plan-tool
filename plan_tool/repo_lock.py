"""Repo-level mutation lock for commands that rewrite shared plan-tool files."""

from __future__ import annotations

import json
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional


class RepoMutationLockError(Exception):
    """Raised when an existing marker blocks repository mutation."""


@dataclass(frozen=True)
class RepoMutationLock:
    repo_root: Path
    path: Path
    command: str
    pid: int


def _read_lock(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def mutation_lock_path(repo_root: Path) -> Path:
    """Return a per-repo lock path that does not dirty real git worktrees."""
    git_dir = repo_root / ".git"
    if git_dir.is_dir():
        return git_dir / "plan-tool-mutation.lock"
    if git_dir.is_file():
        try:
            first_line = git_dir.read_text(encoding="utf-8").splitlines()[0]
        except (IndexError, OSError, UnicodeDecodeError):
            first_line = ""
        prefix = "gitdir:"
        if first_line.startswith(prefix):
            target = first_line[len(prefix):].strip()
            resolved = Path(target)
            if not resolved.is_absolute():
                resolved = (repo_root / resolved).resolve()
            return resolved / "plan-tool-mutation.lock"
    return repo_root / ".plan-tool" / "mutation.lock"


def acquire_repo_mutation_lock(
    repo_root: Path,
    *,
    command: str,
) -> RepoMutationLock:
    """Acquire the repo mutation lock or raise clearly."""
    lock_path = mutation_lock_path(repo_root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    payload = {
        "pid": pid,
        "command": command,
        "started_at": time.time(),
    }

    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        raise RepoMutationLockError(
            f"repository mutation lock already exists at {lock_path}; "
            f"refusing to run {command!r}. Retry after the holder exits. "
            "If the marker remains, confirm all writers have stopped before "
            "inspecting or removing it."
        ) from None

    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)
        fh.write("\n")
    return RepoMutationLock(
        repo_root=repo_root,
        path=lock_path,
        command=command,
        pid=pid,
    )


def release_repo_mutation_lock(lock: RepoMutationLock) -> None:
    current = _read_lock(lock.path)
    if current.get("pid") != lock.pid:
        return
    try:
        lock.path.unlink()
    except FileNotFoundError:
        pass


@contextmanager
def repo_mutation_lock(
    repo_root: Path,
    *,
    command: str,
    enabled: bool = True,
) -> Iterator[Optional[RepoMutationLock]]:
    if not enabled:
        yield None
        return
    lock = acquire_repo_mutation_lock(repo_root, command=command)
    try:
        yield lock
    finally:
        release_repo_mutation_lock(lock)
