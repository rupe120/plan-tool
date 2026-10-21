"""Tracked project-level intent profile for a plan-tool consumer repository."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from plan_tool.fileio import durable_create_text


PROJECT_PROFILE_SCHEMA_VERSION = 1
PROJECT_PROFILE_SUBPATH = Path(".plan-tool") / "project.json"


class ProjectProfileError(ValueError):
    """Raised when a project profile cannot be initialized."""


@dataclass(frozen=True)
class ProjectProfile:
    """The confirmed, project-owned intent available to future commands."""

    schema_version: int
    intent: str
    non_goals: tuple[str, ...]
    decisions: tuple[str, ...]


def project_profile_path(repo_root: Path) -> Path:
    """Return the tracked project-profile path under ``repo_root``."""
    return (repo_root / PROJECT_PROFILE_SUBPATH).resolve()


def initialize_project_profile(
    repo_root: Path,
    *,
    intent: str,
    non_goals: Sequence[str] = (),
    decisions: Sequence[str] = (),
) -> Path:
    """Write the first confirmed profile and refuse to replace an existing one."""
    profile = _profile_from_values(intent, non_goals, decisions)
    path = project_profile_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": profile.schema_version,
        "intent": profile.intent,
        "non_goals": list(profile.non_goals),
        "decisions": list(profile.decisions),
    }
    try:
        durable_create_text(path, json.dumps(payload, indent=2) + "\n")
    except FileExistsError as exc:
        raise ProjectProfileError(
            f"project profile already exists at {path}; edit it and commit the revision"
        ) from exc
    return path


def read_project_profile(repo_root: Path) -> ProjectProfile | None:
    """Load one valid V1 profile, treating absent or malformed files as unset."""
    path = project_profile_path(repo_root)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    if set(raw) != {"schema_version", "intent", "non_goals", "decisions"}:
        return None
    schema_version = raw.get("schema_version")
    if (
        type(schema_version) is not int
        or schema_version != PROJECT_PROFILE_SCHEMA_VERSION
    ):
        return None
    intent = raw.get("intent")
    non_goals = raw.get("non_goals")
    decisions = raw.get("decisions")
    if (
        not isinstance(intent, str)
        or not isinstance(non_goals, list)
        or not isinstance(decisions, list)
    ):
        return None
    if any(not isinstance(value, str) for value in non_goals + decisions):
        return None
    try:
        return _profile_from_values(intent, non_goals, decisions)
    except ProjectProfileError:
        return None


def render_project_profile_context(profile: ProjectProfile | None) -> str:
    """Render confirmed project context for scope-bearing model prompts."""
    if profile is None:
        return ""

    def render_items(items: tuple[str, ...]) -> str:
        return "\n".join(
            f"- {_escape_prompt_markdown(item)}" for item in items
        ) or "- _(none confirmed)_"

    return (
        "## Confirmed project context\n\n"
        "This context guides scope and trade-offs. It is not repository evidence; "
        "verify repository claims against the code.\n\n"
        "### Project intent\n\n"
        f"{_escape_prompt_markdown(profile.intent)}\n\n"
        "### Non-goals\n\n"
        f"{render_items(profile.non_goals)}\n\n"
        "### Settled decisions\n\n"
        f"{render_items(profile.decisions)}"
    )


def project_profile_context(repo_root: Path) -> str:
    """Load and render the optional project profile for a model prompt."""
    return render_project_profile_context(read_project_profile(repo_root))


def render_project_context_block(context: str) -> str:
    """Return a rendered context block with its separator, when present."""
    cleaned = context.strip()
    return f"{cleaned}\n\n" if cleaned else ""


def _profile_from_values(
    intent: object,
    non_goals: Sequence[str],
    decisions: Sequence[str],
) -> ProjectProfile:
    cleaned_intent = _clean_text(intent, "--intent")
    cleaned_non_goals = _clean_list(non_goals, "--non-goal")
    cleaned_decisions = _clean_list(decisions, "--decision")
    return ProjectProfile(
        schema_version=PROJECT_PROFILE_SCHEMA_VERSION,
        intent=cleaned_intent,
        non_goals=tuple(cleaned_non_goals),
        decisions=tuple(cleaned_decisions),
    )


def _clean_list(values: Sequence[str], option: str) -> list[str]:
    if not isinstance(values, Sequence) or isinstance(values, (str, bytes)):
        raise ProjectProfileError(
            f"{option} values must be supplied as a sequence"
        )
    cleaned: list[str] = []
    for value in values:
        cleaned.append(_clean_text(value, option))
    return cleaned


def normalize_project_profile_text(value: object) -> str | None:
    """Collapse one logical profile value, or return ``None`` when blank."""
    if not isinstance(value, str):
        return None
    return " ".join(value.split()) or None


def _clean_text(value: object, option: str) -> str:
    cleaned = normalize_project_profile_text(value)
    if cleaned is None:
        raise ProjectProfileError(f"{option} must not be blank")
    return cleaned


def _escape_prompt_markdown(value: str) -> str:
    """Keep confirmed text from introducing headings into a prompt block."""
    return value.replace("\\", "\\\\").replace("#", "\\#")
