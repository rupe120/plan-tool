"""The selected model's context window for the prompt-budget advisory, from local sources only.

Never raises and returns ``None`` when nothing is known. See docs/ARCHITECTURE.md § "Prompt-budget
window" for the sources, the refusal-gate exclusion (``observed=False``) and the limits, and
docs/reference/contracts/model-window-sources.md for the external shapes it reads.
"""

from __future__ import annotations

import json
import os
import threading
import tomllib
from pathlib import Path
from typing import Optional

from plan_tool.backend import get_active_backend, observed_context_window

# path -> ((mtime_ns, size, inode, device), parsed value or _UNREADABLE). Lock-guarded because
# ``detail --jobs N`` resolves windows from worker threads.
_UNREADABLE = object()
_FILE_MEMO: dict[str, tuple[tuple[int, int, int, int], object]] = {}
_FILE_MEMO_LOCK = threading.Lock()


def _file_version(path: Path) -> tuple[int, int, int, int]:
    stat = path.stat()
    return (stat.st_mtime_ns, stat.st_size, stat.st_ino, stat.st_dev)


def _memoized_file(path: Path, parse):
    """``parse(path)`` once per version of the file; ``None`` when it cannot be parsed."""
    cached = _FILE_MEMO.get(str(path))
    if cached is not None and cached[0] == _file_version(path):
        return None if cached[1] is _UNREADABLE else cached[1]
    with _FILE_MEMO_LOCK:
        version = _file_version(path)  # inside the lock: the stored tag is never older than the entry
        cached = _FILE_MEMO.get(str(path))
        if cached is not None and cached[0] == version:
            return None if cached[1] is _UNREADABLE else cached[1]
        try:
            value = parse(path)
        except (ValueError, TypeError, AttributeError, RecursionError):
            value = _UNREADABLE  # a content failure: stays true until the file changes
        except Exception:  # noqa: BLE001 — a read error may be transient, so it is not cached
            return None
        _FILE_MEMO[str(path)] = (version, value)
        return None if value is _UNREADABLE else value


def active_context_window(*, observed: bool = True) -> Optional[int]:
    """The active backend's model window, or ``None``; a refusal gate passes ``observed=False``."""
    try:
        backend = get_active_backend()
        return context_window_for(backend.name, backend.resolved_model, observed=observed)
    except Exception:  # noqa: BLE001 — an advisory lookup never fails the caller
        return None


def context_window_for(
    backend_name: str, model: Optional[str], *, observed: bool = True
) -> Optional[int]:
    """An observed window (unless excluded), else Codex's catalog window."""
    if observed:
        reported = observed_context_window(backend_name, model)
        if reported is not None:
            return reported
    if backend_name == "codex":
        return _codex_window(model)
    return None


def _codex_home() -> Path:
    configured = os.environ.get("CODEX_HOME")
    return Path(configured) if configured else Path.home() / ".codex"


def _parse_codex_catalog(path: Path) -> dict[str, int]:
    """Usable window per model slug in a Codex ``models_cache.json``.

    Usable means ``context_window`` scaled by ``effective_context_window_percent``, because
    Codex compacts at that fraction. An entry with no usable window is left out.
    """
    catalog = json.loads(path.read_text(encoding="utf-8"))
    windows: dict[str, int] = {}
    for entry in catalog.get("models", []):
        if not isinstance(entry, dict) or not isinstance(entry.get("slug"), str):
            continue
        window = entry.get("context_window")
        percent = entry.get("effective_context_window_percent", 100)
        if type(window) is not int or window <= 0:
            continue
        if type(percent) is not int or not 0 < percent <= 100:
            percent = 100
        windows[entry["slug"]] = window * percent // 100
    return windows


def _parse_codex_model(path: Path) -> Optional[str]:
    model = tomllib.loads(path.read_text(encoding="utf-8")).get("model")
    return model if isinstance(model, str) and model else None


def _codex_window(model: Optional[str]) -> Optional[int]:
    """The usable window Codex's catalog lists for ``model`` (default: its configured model).

    Any unreadable or malformed input is "not known", never an error.
    """
    try:
        home = _codex_home()
        slug = model or _memoized_file(home / "config.toml", _parse_codex_model)
        if not slug:
            return None
        catalog = _memoized_file(home / "models_cache.json", _parse_codex_catalog)
        return catalog.get(slug) if catalog is not None else None
    except Exception:  # noqa: BLE001 — see module docstring
        return None
