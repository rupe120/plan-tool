"""Read per-project backend tuning from ``.plan-tool/backends.json``.

The file is co-owned with the backend *selection* design
(``docs/design-plans/BACKEND_SELECTION.md``), which reads its
``default`` / ``aspects`` / ``failover`` keys. This module reads **only**
the ``backends.<name>`` block and parses each entry into a typed
:class:`BackendOverride`.

The load-bearing scoping decision: :class:`BackendOverride` carries
**no** ``binary`` / ``parser`` / ``classification`` fields, so a project
file structurally cannot swap the binary, the stream parser, or the
failure-classification regexes — the per-project surface is deliberately
tuning-only (``model`` + extra argv). A missing file returns an empty
map, the legitimate "no per-project tuning" state.

Stdlib-only leaf: imports nothing from :mod:`plan_tool.backend`,
``locator``, or any orchestrator, so it sits below the backend seam in
the import graph. ``repo_root`` is a parameter (the loader never calls
``locator``) so it stays hermetic and testable.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


BACKENDS_CONFIG_SUBPATH = Path(".plan-tool") / "backends.json"


class BackendConfigError(Exception):
    """Raised when ``.plan-tool/backends.json`` is malformed.

    Mirrors :class:`plan_tool.jira_config.JiraConfigError`: surfaced
    verbatim to the user, message names the offending file (and backend /
    field where applicable). Raised for malformed JSON, a non-object top
    level, a non-object ``backends`` block, a non-object per-backend
    entry, or a wrong-typed ``model`` / ``extra_*_argv`` field.
    """


@dataclass(frozen=True)
class BackendOverride:
    """Per-backend project tuning parsed from ``backends.<name>``.

    ``model`` is the project-file model tier (step 6 slots it into the
    ``--model`` > project > manifest-default precedence chain). The two
    ``extra_*_argv`` lists are appended after the manifest flags and
    before the prompt. There are deliberately **no** ``binary`` /
    ``parser`` / ``classification`` fields — their absence is what
    guarantees a project file cannot change the backend's binary or
    parser.
    """

    model: Optional[str] = None
    extra_batch_argv: list[str] = field(default_factory=list)
    extra_streaming_argv: list[str] = field(default_factory=list)


def default_backends_config_path(repo_root: Path) -> Path:
    """Path to ``.plan-tool/backends.json`` under ``repo_root``."""
    return (repo_root / BACKENDS_CONFIG_SUBPATH).resolve()


def _argv_field(block: dict, key: str, name: str, mf: Path) -> list[str]:
    """Parse one ``extra_*_argv`` field, raising on a non-string-list."""
    raw = block.get(key, [])
    if not isinstance(raw, list):
        raise BackendConfigError(
            f'backends[{name!r}].{key} in {mf} must be a list of strings, '
            f"got {type(raw).__name__}"
        )
    for i, element in enumerate(raw):
        if not isinstance(element, str):
            raise BackendConfigError(
                f"backends[{name!r}].{key}[{i}] in {mf} must be a string, "
                f"got {type(element).__name__}"
            )
    return list(raw)


def load_backend_overrides(
    repo_root: Path, *, path: Optional[Path] = None
) -> dict[str, BackendOverride]:
    """Read ``.plan-tool/backends.json`` and parse its ``backends`` block.

    Returns an empty map when the file is absent (the unconfigured
    project) or carries no ``backends`` key. Tolerates the sibling
    ``default`` / ``aspects`` / ``failover`` keys — they belong to
    ``BACKEND_SELECTION.md`` and are never inspected or rejected. Raises
    :class:`BackendConfigError` when the file exists but is malformed.

    Other keys inside a per-backend block (``binary``, ``parser``,
    ``classification``, anything else) are inert: :class:`BackendOverride`
    has nowhere to put them, which is the scoping guarantee.
    """
    mf = path or default_backends_config_path(repo_root)
    if not mf.is_file():
        return {}

    try:
        data = json.loads(mf.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackendConfigError(f"invalid JSON in {mf}: {exc}") from exc
    if not isinstance(data, dict):
        raise BackendConfigError(
            f"{mf} top-level must be a JSON object, got {type(data).__name__}"
        )

    raw_backends = data.get("backends", {})
    if not isinstance(raw_backends, dict):
        raise BackendConfigError(
            f'"backends" in {mf} must be a JSON object, '
            f"got {type(raw_backends).__name__}"
        )

    overrides: dict[str, BackendOverride] = {}
    for name, block in raw_backends.items():
        if not isinstance(name, str) or not name.strip():
            raise BackendConfigError(
                f"backends key {name!r} in {mf}: must be a non-empty string"
            )
        if not isinstance(block, dict):
            raise BackendConfigError(
                f"backends[{name!r}] in {mf} must be a JSON object, "
                f"got {type(block).__name__}"
            )
        model = block.get("model")
        if model is not None and (not isinstance(model, str) or not model.strip()):
            raise BackendConfigError(
                f"backends[{name!r}].model in {mf} must be a non-empty string "
                "when set"
            )
        overrides[name] = BackendOverride(
            model=model.strip() if isinstance(model, str) else None,
            extra_batch_argv=_argv_field(block, "extra_batch_argv", name, mf),
            extra_streaming_argv=_argv_field(
                block, "extra_streaming_argv", name, mf
            ),
        )
    return overrides


def backend_override_for(
    name: str, repo_root: Path, *, path: Optional[Path] = None
) -> Optional[BackendOverride]:
    """Return the override for backend ``name``, or ``None`` if none applies.

    ``None`` when the file is absent or has no ``backends.<name>`` block —
    the "use manifest defaults" signal for step 6's selection-time lookup.
    """
    return load_backend_overrides(repo_root, path=path).get(name)
