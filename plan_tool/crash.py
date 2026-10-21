"""Persist unexpected-exception tracebacks to disk for later debugging.

When an *unhandled* exception escapes a ``plan-tool`` command, the CLI's
top-level handler (:func:`plan_tool.cli.main`) shows a clean one-line
message instead of a raw stack trace — but the full traceback would be
lost the moment the process exits. This module writes that traceback to
a file under ``<repo_root>/.plan-tool/crashes/<label>/`` so it survives
for a bug report or a debugging pass.

Mirrors the conventions of ``plan_tool.create._dump_failed_response``:

- best-effort — never raises; returns ``None`` on any I/O error so a
  failure to *log* a crash can't escalate into a second crash,
- no first-party ``plan_tool.*`` imports (keeps the dependency graph a
  tree, like :mod:`plan_tool.checkpoint`),
- gitignored location alongside ``checkpoints`` / ``runs`` /
  ``parse-failures``.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


CRASHES_REL = (".plan-tool", "crashes")

# Conservative slug for the per-label subdirectory: keep word chars,
# dot, dash, underscore; collapse everything else to a single dash so a
# plan name with slashes / spaces can't escape the crashes dir or create
# surprise nesting. Empty / all-stripped labels fall back to "unknown".
_LABEL_SANITIZE_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Labels that resolve to a path component which would escape or alias the
# crashes dir (``.`` -> the dir itself, ``..`` -> its parent). The
# character allowlist above keeps dots, so a dot-only label survives
# sanitization and must be rejected explicitly.
_RESERVED_LABELS = {"", ".", ".."}


def crashes_root(repo_root: Path) -> Path:
    """Return ``<repo_root>/.plan-tool/crashes/``."""
    return repo_root.joinpath(*CRASHES_REL)


def _sanitize_label(label: str) -> str:
    cleaned = _LABEL_SANITIZE_RE.sub("-", label).strip("-")
    if cleaned in _RESERVED_LABELS:
        return "unknown"
    return cleaned


def save_crash_traceback(
    repo_root: Path, label: str, *, tb_text: str
) -> Optional[Path]:
    """Write ``tb_text`` to a timestamped file and return its path.

    The file lands at
    ``<repo_root>/.plan-tool/crashes/<label>/<YYYYMMDDTHHMMSSZ>.txt``.
    ``label`` is sanitized (plan slug / name / command), defaulting to
    ``"unknown"`` when it sanitizes to empty.

    Best-effort: returns ``None`` (writing nothing) on any ``OSError`` —
    a logging failure must never derail the crash-reporting path it
    exists to support.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dest_dir = crashes_root(repo_root) / _sanitize_label(label)
    dest_path = dest_dir / f"{ts}.txt"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path.write_text(tb_text, encoding="utf-8")
    except OSError:
        return None
    return dest_path
