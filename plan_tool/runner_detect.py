"""Qualify the one supported repository test command."""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path


UV_PYTEST_COMMAND = "uv run pytest tests/ -q -n auto"
PREFLIGHT_TIMEOUT_S = 600

_REQUIRED_DEV_PACKAGES = frozenset({"pytest", "pytest-xdist"})
_REQUIREMENT_NAME_RE = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)")
_NORMALIZED_NAME_RE = re.compile(r"[-_.]+")


def qualify_uv_pytest_command(repo_root: Path) -> str | None:
    """Return the fixed command only when its markers and preflight succeed."""
    if not _has_uv_pytest_markers(repo_root):
        return None

    try:
        result = subprocess.run(
            UV_PYTEST_COMMAND,
            shell=True,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=PREFLIGHT_TIMEOUT_S,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return None

    return UV_PYTEST_COMMAND if result.returncode == 0 else None


def _has_uv_pytest_markers(repo_root: Path) -> bool:
    """Return whether the fixed repository markers nominate the candidate."""
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.is_file():
        return False
    if not (repo_root / "uv.lock").is_file() or not (repo_root / "tests").is_dir():
        return False

    try:
        with pyproject_path.open("rb") as pyproject_file:
            project_config = tomllib.load(pyproject_file)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError):
        return False

    return _has_required_dev_packages(project_config) and _has_exact_testpaths(
        project_config
    )


def _has_required_dev_packages(project_config: dict) -> bool:
    """Return whether the development group names both required packages."""
    dependency_groups = project_config.get("dependency-groups")
    if not isinstance(dependency_groups, dict):
        return False
    dev_dependencies = dependency_groups.get("dev")
    if not isinstance(dev_dependencies, list):
        return False

    package_names = {
        name
        for requirement in dev_dependencies
        if (name := _requirement_name(requirement)) is not None
    }
    return _REQUIRED_DEV_PACKAGES <= package_names


def _requirement_name(requirement: object) -> str | None:
    """Extract a normalized distribution name from one dependency string."""
    if not isinstance(requirement, str):
        return None
    match = _REQUIREMENT_NAME_RE.match(requirement)
    if match is None:
        return None
    return _NORMALIZED_NAME_RE.sub("-", match.group(1)).lower()


def _has_exact_testpaths(project_config: dict) -> bool:
    """Return whether pytest declares exactly the repository test directory."""
    tool_config = project_config.get("tool")
    if not isinstance(tool_config, dict):
        return False
    pytest_config = tool_config.get("pytest")
    if not isinstance(pytest_config, dict):
        return False
    ini_options = pytest_config.get("ini_options")
    return isinstance(ini_options, dict) and ini_options.get("testpaths") == ["tests"]
