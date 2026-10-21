"""Pure-I/O memoization primitive for ``plan-tool create`` / ``plan-tool detail``.

Provides a ``Checkpoint`` dataclass plus atomic save / hash-gated load
helpers. Callers compute a content hash over their normalized inputs,
look up an on-disk checkpoint by that hash, and skip the expensive
``claude_invoke`` round-trip when the hash matches.

This module is intentionally narrow:

- no claude shell-out (the whole point is to avoid it),
- no CLI surface (resume / no-resume flags land in ``cli.py`` in step 4),
- no first-party ``plan_tool.*`` imports (keeps the dependency graph a
  tree and lets callers in steps 2/3 wire in parallel),
- no third-party dependencies — JSON on disk avoids pulling ``pydantic``
  / ``yaml`` into a contract that's read once and written once.

Checkpoints live under ``<repo_root>/.plan-tool/checkpoints/<slug>/``,
mirroring the ``PROJECT_LESSONS_REL`` convention in ``plan_tool.lessons``.

**Concurrency.** Two simultaneous ``plan-tool detail`` (or ``create``)
runs against the same plan are *undefined behaviour*. The atomic
``os.replace`` in ``save_checkpoint`` guarantees an individual file
is never half-written, but it does not serialize two writers — both
runs may invoke claude, both may write, and the last writer wins for
the checkpoint *and* for the durable detail file / plan frontmatter.
There is no lockfile. Don't run plan-tool concurrently against the
same plan; use ``--no-resume`` if you need to deliberately overlap.

**Staleness.** Checkpoints are only auto-discarded on success.
Abandoned runs leave files behind. Pass ``max_age_seconds`` to
``load_if_valid`` (or accept the default ``DEFAULT_MAX_AGE_SECONDS``)
to opt into expiration so an old checkpoint doesn't silently re-emit
content from weeks ago. Operators can also clear the directory
manually — it's gitignored.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


CHECKPOINT_SCHEMA_VERSION = 1

CHECKPOINTS_REL = (".plan-tool", "checkpoints")

_HASH_ALGO = "sha256"

# Default expiration for cached responses, in seconds. 30 days is the
# cliff after which an abandoned plan's checkpoints get treated as
# stale rather than silently re-emitted. Picked conservatively — a
# detail body that hasn't been re-hit in a month is overwhelmingly
# likely to no longer reflect the user's current intent. Callers can
# pass a different value (or ``None`` for no expiration) to
# ``load_if_valid`` per-call.
DEFAULT_MAX_AGE_SECONDS = 30 * 24 * 60 * 60


@dataclass(frozen=True)
class Checkpoint:
    """One memoized artifact from a previous create / detail run.

    ``payload`` is an opaque string — callers in steps 2/3 cache
    different shapes (parsed detail body vs. raw claude JSON for create)
    and parse on read. Forcing a structured field here would push the
    wrong abstraction into the storage layer.
    """

    input_hash: str
    payload: str
    created_at: str
    schema_version: int = CHECKPOINT_SCHEMA_VERSION


def checkpoints_root(repo_root: Path) -> Path:
    """Return ``<repo_root>/.plan-tool/checkpoints/``."""
    return repo_root.joinpath(*CHECKPOINTS_REL)


def checkpoint_dir(repo_root: Path, slug: str) -> Path:
    """Return the per-plan-slug directory under the checkpoints root."""
    return checkpoints_root(repo_root) / slug


def checkpoint_path(repo_root: Path, slug: str, name: str) -> Path:
    """Return the file path for a checkpoint with opaque ``name``.

    ``name`` is chosen by the caller (e.g. ``"detail-step-3"``,
    ``"create-initial-steps"``). This module deliberately does not
    enumerate kinds so it doesn't need to grow every time a new caller
    appears.
    """
    return checkpoint_dir(repo_root, slug) / f"{name}.json"


def compute_input_hash(payload: object) -> str:
    """SHA-256 hex of the canonical-JSON encoding of ``payload``.

    ``sort_keys=True`` makes dict-typed inputs order-independent;
    ``separators=(",", ":")`` strips insignificant whitespace so two
    semantically equal inputs hash identically. Non-JSON-serializable
    inputs raise ``TypeError`` — callers must pre-stringify (e.g. pass
    ``str(path)`` rather than a ``Path``) so hashing is never based on
    a hidden ``repr()``.
    """
    canonical = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def save_checkpoint(path: Path, checkpoint: Checkpoint) -> None:
    """Atomically write ``checkpoint`` to ``path``.

    Writes a sibling tempfile in the same directory and ``os.replace``s
    it into place so a crash mid-write cannot leave a half-written
    checkpoint. The temp file lives in ``path.parent`` (not ``/tmp``)
    so the rename stays a single-inode operation — cross-filesystem
    renames are not atomic.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(asdict(checkpoint), indent=2, sort_keys=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(body)
            f.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_if_valid(
    path: Path,
    *,
    expected_input_hash: str,
    max_age_seconds: Optional[int] = DEFAULT_MAX_AGE_SECONDS,
) -> Optional[Checkpoint]:
    """Return the checkpoint at ``path`` iff its ``input_hash`` matches
    AND it isn't older than ``max_age_seconds``.

    Returns ``None`` when the file is missing, can't be decoded, has the
    wrong ``schema_version``, is missing/wrong-typed fields, holds a
    different ``input_hash``, has an unparseable ``created_at``, or
    exceeds ``max_age_seconds``. Fail-safe by design: a missing
    checkpoint and a stale one are indistinguishable to the caller,
    which is the right contract for a memoization layer — both fall
    through to invoking claude.

    ``max_age_seconds=None`` disables the staleness check (legacy
    "honor any matching hash" behavior). The default
    (``DEFAULT_MAX_AGE_SECONDS`` = 30 days) protects against an
    abandoned plan's checkpoint being silently replayed long after the
    user has lost track of why they cached it.
    """
    try:
        raw = path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError):
        return None
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    schema_version = obj.get("schema_version")
    if schema_version != CHECKPOINT_SCHEMA_VERSION:
        return None
    input_hash = obj.get("input_hash")
    payload = obj.get("payload")
    created_at = obj.get("created_at")
    if not isinstance(input_hash, str):
        return None
    if not isinstance(payload, str):
        return None
    if not isinstance(created_at, str):
        return None
    if input_hash != expected_input_hash:
        return None
    if max_age_seconds is not None:
        try:
            ts = datetime.fromisoformat(created_at)
        except ValueError:
            return None
        # Naive timestamps are treated as UTC; the saver always writes
        # tz-aware UTC, so this only matters for directly edited files.
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        age = (datetime.now(timezone.utc) - ts).total_seconds()
        if age > max_age_seconds:
            return None
    return Checkpoint(
        input_hash=input_hash,
        payload=payload,
        created_at=created_at,
        schema_version=schema_version,
    )


def discard_checkpoint(path: Path) -> bool:
    """Remove a checkpoint file. Returns ``True`` iff a file was removed."""
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
