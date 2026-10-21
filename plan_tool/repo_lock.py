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
    """Raised when another plan-tool mutation appears to be active."""


@dataclass(frozen=True)
class RepoMutationLock:
    repo_root: Path
    path: Path
    command: str
    pid: int


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


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
    payload = {
        "pid": os.getpid(),
        "command": command,
        "started_at": time.time(),
    }

    for attempt in range(2):
        try:
            fd = os.open(
                lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o644,
            )
        except FileExistsError:
            current = _read_lock(lock_path)
            pid = current.get("pid")
            if isinstance(pid, int) and not _pid_is_running(pid):
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                if attempt == 0:
                    continue
            owner = f"pid {pid}" if isinstance(pid, int) else "unknown pid"
            owner_cmd = current.get("command")
            if isinstance(owner_cmd, str) and owner_cmd:
                owner += f" running {owner_cmd!r}"
            raise RepoMutationLockError(
                f"another mutating plan-tool command is active ({owner}); "
                f"refusing to run {command!r}. Retry after it exits, or "
                f"remove {lock_path} if that process is gone."
            )
        else:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh)
                fh.write("\n")
            return RepoMutationLock(
                repo_root=repo_root,
                path=lock_path,
                command=command,
                pid=os.getpid(),
            )

    raise RepoMutationLockError(f"could not acquire mutation lock at {lock_path}")


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
