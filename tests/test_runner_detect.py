"""Tests for the fixed UV/pytest command qualifier."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from plan_tool import runner_detect


def _write_fixed_markers(
    repo_root: Path,
    *,
    dev_dependencies: list[str] | None = None,
    testpaths: str = 'testpaths = ["tests"]',
    include_lock: bool = True,
    include_tests: bool = True,
) -> None:
    dependencies = (
        dev_dependencies
        if dev_dependencies is not None
        else ["pytest>=9", "pytest-xdist>=3"]
    )
    dependency_lines = "\n".join(f'    "{dependency}",' for dependency in dependencies)
    (repo_root / "pyproject.toml").write_text(
        "[dependency-groups]\n"
        "dev = [\n"
        f"{dependency_lines}\n"
        "]\n\n"
        "[tool.pytest.ini_options]\n"
        f"{testpaths}\n",
        encoding="utf-8",
    )
    if include_lock:
        (repo_root / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    if include_tests:
        (repo_root / "tests").mkdir(exist_ok=True)


def _successful_preflight(*args: object, **kwargs: object) -> SimpleNamespace:
    return SimpleNamespace(returncode=0)


def test_uv_pytest_candidate_requires_every_fixed_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Each fixed marker is necessary before the command can be preflighted."""
    monkeypatch.setattr(runner_detect.subprocess, "run", _successful_preflight)

    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None

    _write_fixed_markers(tmp_path, dev_dependencies=["pytest>=9"])
    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None

    _write_fixed_markers(
        tmp_path,
        dev_dependencies=["pytest>=9", "pytest-xdist>=3"],
        testpaths='testpaths = ["unit"]',
    )
    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None

    _write_fixed_markers(tmp_path)
    (tmp_path / "uv.lock").unlink()
    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None

    (tmp_path / "uv.lock").write_text("version = 1\n", encoding="utf-8")
    (tmp_path / "tests").rmdir()
    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None


def test_pytest_dependency_marker_requires_exact_package_names(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`pytest-cov` never substitutes for the required `pytest` package."""
    _write_fixed_markers(
        tmp_path,
        dev_dependencies=["pytest-cov>=7", "pytest-xdist>=3"],
    )

    def fail_if_preflight_runs(*args: object, **kwargs: object) -> SimpleNamespace:
        raise AssertionError("unqualified markers must not run a preflight")

    monkeypatch.setattr(runner_detect.subprocess, "run", fail_if_preflight_runs)

    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None


def test_unreadable_or_malformed_pyproject_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unreadable and invalid project configuration returns unknown without raising."""
    _write_fixed_markers(tmp_path)
    (tmp_path / "pyproject.toml").write_text("[dependency-groups", encoding="utf-8")
    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None

    _write_fixed_markers(tmp_path)

    def raise_permission_error(self: Path, *args: object, **kwargs: object) -> None:
        raise PermissionError("pyproject.toml is unreadable")

    monkeypatch.setattr(runner_detect.Path, "open", raise_permission_error)

    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None


def test_qualified_uv_pytest_candidate_is_the_exact_command(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Successful evidence and preflight return only the fixed command."""
    _write_fixed_markers(tmp_path)
    monkeypatch.setattr(runner_detect.subprocess, "run", _successful_preflight)

    assert runner_detect.qualify_uv_pytest_command(tmp_path) == (
        "uv run pytest tests/ -q -n auto"
    )


def test_preflight_runs_the_exact_command_from_repo_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Preflight mirrors the runtime gate's command, shell, root, and deadline."""
    _write_fixed_markers(tmp_path)
    seen: dict[str, object] = {}

    def record_preflight(command: str, **kwargs: object) -> SimpleNamespace:
        seen["command"] = command
        seen.update(kwargs)
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(runner_detect.subprocess, "run", record_preflight)

    assert (
        runner_detect.qualify_uv_pytest_command(tmp_path)
        == runner_detect.UV_PYTEST_COMMAND
    )
    assert seen == {
        "command": "uv run pytest tests/ -q -n auto",
        "shell": True,
        "cwd": str(tmp_path),
        "capture_output": True,
        "text": True,
        "timeout": 600,
    }


@pytest.mark.parametrize(
    "preflight",
    [
        lambda *args, **kwargs: SimpleNamespace(returncode=1),
        lambda *args, **kwargs: (_ for _ in ()).throw(
            subprocess.TimeoutExpired(runner_detect.UV_PYTEST_COMMAND, 600)
        ),
        lambda *args, **kwargs: (_ for _ in ()).throw(FileNotFoundError()),
    ],
    ids=["failed", "timeout", "spawn-error"],
)
def test_failed_timeout_or_spawn_error_preflight_is_unknown(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    preflight: object,
) -> None:
    """Every failed preflight outcome remains unknown instead of raising."""
    _write_fixed_markers(tmp_path)
    monkeypatch.setattr(runner_detect.subprocess, "run", preflight)

    assert runner_detect.qualify_uv_pytest_command(tmp_path) is None


def test_runner_detect_is_stdlib_only_leaf() -> None:
    """Loading the detector alone imports no first-party module."""
    source = Path(__file__).resolve().parents[1] / "plan_tool" / "runner_detect.py"
    code = (
        "import importlib.util, sys\n"
        "spec = importlib.util.spec_from_file_location(\n"
        f"    'runner_detect_isolated', {str(source)!r}\n"
        ")\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "sys.modules['runner_detect_isolated'] = module\n"
        "spec.loader.exec_module(module)\n"
        "leaked = [name for name in sys.modules "
        "if name == 'plan_tool' or name.startswith('plan_tool.')]\n"
        "assert not leaked, leaked\n"
    )

    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
