"""Read project backend defaults and tuning without importing CLI registrations.

``BackendOverride`` has no ``binary``/``parser``/``classification`` fields, so a
project file cannot swap the binary, stream parser or failure regexes: tuning
only. Stdlib-only leaf; ``repo_root`` is a parameter so it stays hermetic.
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


def _read_backend_config(
    repo_root: Path, *, path: Optional[Path] = None
) -> tuple[dict, dict[str, BackendOverride], Path]:
    """Read ``.plan-tool/backends.json``: raw data, parsed overrides, file path.

    Returns empty data and overrides when the file is absent (the unconfigured
    project). ``default_backend`` and ``commands`` are validated by
    :func:`load_project_backend_config`; other sibling keys are never
    inspected or rejected. Raises
    :class:`BackendConfigError` when the file exists but is malformed.

    Other keys inside a per-backend block (``binary``, ``parser``,
    ``classification``, anything else) are inert: :class:`BackendOverride`
    has nowhere to put them, which is the scoping guarantee.
    """
    mf = path or default_backends_config_path(repo_root)
    if not mf.is_file():
        return {}, {}, mf

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
        model = _model_field(block, f"backends[{name!r}].model", mf)
        overrides[name] = BackendOverride(
            model=model,
            extra_batch_argv=_argv_field(block, "extra_batch_argv", name, mf),
            extra_streaming_argv=_argv_field(
                block, "extra_streaming_argv", name, mf
            ),
        )
    return data, overrides, mf


def backend_override_for(
    name: str, repo_root: Path, *, path: Optional[Path] = None
) -> Optional[BackendOverride]:
    """Return the override for backend ``name``, or ``None`` if none applies.

    ``None`` when the file is absent or has no ``backends.<name>`` block —
    the "use manifest defaults" signal for step 6's selection-time lookup.
    """
    return load_backend_overrides(repo_root, path=path).get(name)


@dataclass(frozen=True)
class ProjectBackendConfig:
    """Project selection defaults and the compatible base-tuning projection."""

    default_backend: str | None = None
    overrides: dict[str, BackendOverride] = field(default_factory=dict)
    command_models: dict[str, dict[str, str | None]] = field(default_factory=dict)


def load_backend_overrides(
    repo_root: Path, *, path: Optional[Path] = None
) -> dict[str, BackendOverride]:
    """Read base tuning only; selection settings remain inert for legacy callers."""
    return _read_backend_config(repo_root, path=path)[1]


def load_project_backend_config(
    repo_root: Path, *, command_names: dict[str, str], path: Optional[Path] = None
) -> ProjectBackendConfig:
    """Read selection settings using canonical command identities supplied by CLI."""
    data, overrides, mf = _read_backend_config(repo_root, path=path)
    default = data.get("default_backend")
    if "default_backend" in data:
        if not isinstance(default, str) or not default.strip():
            raise BackendConfigError(f"default_backend in {mf} must be a non-empty string")
        default = default.strip()
    command_models: dict[str, dict[str, str | None]] = {}
    for name, block in data.get("backends", {}).items():
        commands = block.get("commands", {})
        prefix = f"backends[{name!r}].commands"
        if not isinstance(commands, dict):
            raise BackendConfigError(f"{prefix} in {mf} must be a JSON object")
        models: dict[str, str | None] = {}
        for command, entry in commands.items():
            location = f"{prefix}[{command!r}] in {mf}"
            if command not in command_names:
                choices = ", ".join(sorted(command_names))
                raise BackendConfigError(f"{location}: unknown command; supported choices: {choices}")
            canonical = command_names[command]
            if canonical in models:
                raise BackendConfigError(f"{location}: duplicate command after normalization to {canonical!r}")
            if not isinstance(entry, dict):
                raise BackendConfigError(f"{location} must be a JSON object")
            models[canonical] = _model_field(entry, f"{prefix}[{command!r}].model", mf)
        command_models[name] = models
    return ProjectBackendConfig(default, overrides, command_models)


def _model_field(block: dict, location: str, mf: Path) -> str | None:
    """Null and absent models inherit; explicit models must be non-empty strings."""
    model = block.get("model")
    if model is not None and (not isinstance(model, str) or not model.strip()):
        raise BackendConfigError(f"{location} in {mf} must be a non-empty string when set")
    return model.strip() if isinstance(model, str) else None
