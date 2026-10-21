"""Tests for plan_tool.backend_config — per-project backend tuning file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from plan_tool.backend import structural_codex_backend
from plan_tool.backend_config import (
    BackendConfigError,
    BackendOverride,
    backend_override_for,
    default_backends_config_path,
    load_backend_overrides,
)


def _write(tmp_path: Path, payload) -> None:
    """Write ``payload`` (object or raw string) to the conventional path."""
    mf = default_backends_config_path(tmp_path)
    mf.parent.mkdir(parents=True, exist_ok=True)
    body = payload if isinstance(payload, str) else json.dumps(payload)
    mf.write_text(body, encoding="utf-8")


class TestLoadBackendOverrides:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_backend_overrides(tmp_path) == {}

    def test_absent_backends_key_returns_empty(self, tmp_path: Path) -> None:
        _write(tmp_path, {"default": "claude", "aspects": {}})
        assert load_backend_overrides(tmp_path) == {}

    def test_round_trip_model_and_argv(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {
                "backends": {
                    "codex": {
                        "model": "gpt-5",
                        "extra_batch_argv": ["--foo", "bar"],
                        "extra_streaming_argv": ["--baz"],
                    }
                }
            },
        )
        overrides = load_backend_overrides(tmp_path)
        assert overrides["codex"] == BackendOverride(
            model="gpt-5",
            extra_batch_argv=["--foo", "bar"],
            extra_streaming_argv=["--baz"],
        )

    def test_model_null_is_none(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {"backends": {"a": {"model": None}, "b": {"extra_batch_argv": []}}},
        )
        overrides = load_backend_overrides(tmp_path)
        assert overrides["a"].model is None
        assert overrides["b"].model is None

    def test_extra_argv_default_empty(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": {"codex": {"model": "gpt-5"}}})
        override = load_backend_overrides(tmp_path)["codex"]
        assert override.extra_batch_argv == []
        assert override.extra_streaming_argv == []

    def test_structural_evaluator_never_splices_project_extra_argv(
        self, tmp_path: Path
    ) -> None:
        _write(
            tmp_path,
            {
                "backends": {
                    "codex": {
                        "extra_batch_argv": ["--unsafe-batch"],
                        "extra_streaming_argv": ["--unsafe-stream"],
                    }
                }
            },
        )

        argv = structural_codex_backend(tmp_path / "empty").batch_argv("P")

        assert "--unsafe-batch" not in argv
        assert "--unsafe-stream" not in argv

    def test_tolerates_sibling_keys(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {
                "default": "claude",
                "aspects": {"review": "codex"},
                "failover": ["claude", "codex"],
                "backends": {"codex": {"model": "gpt-5"}},
            },
        )
        overrides = load_backend_overrides(tmp_path)
        assert list(overrides) == ["codex"]
        assert overrides["codex"].model == "gpt-5"

    def test_binary_and_parser_keys_ignored(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {
                "backends": {
                    "codex": {
                        "binary": "evil",
                        "parser": "evil",
                        "classification": {"x": "y"},
                        "model": "gpt-5",
                    }
                }
            },
        )
        override = load_backend_overrides(tmp_path)["codex"]
        assert override.model == "gpt-5"
        assert not hasattr(override, "binary")
        assert not hasattr(override, "parser")
        assert not hasattr(override, "classification")

    def test_backend_override_for_hit_and_miss(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": {"codex": {"model": "gpt-5"}}})
        assert backend_override_for("codex", tmp_path).model == "gpt-5"
        assert backend_override_for("nope", tmp_path) is None
        # Absent file → None.
        assert backend_override_for("codex", tmp_path / "elsewhere") is None


class TestBackendConfigErrors:
    def test_malformed_json_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, "{not json}")
        mf = default_backends_config_path(tmp_path)
        with pytest.raises(BackendConfigError, match=str(mf)):
            load_backend_overrides(tmp_path)

    def test_top_level_not_object_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, "[]")
        with pytest.raises(BackendConfigError, match="top-level"):
            load_backend_overrides(tmp_path)

    def test_backends_not_object_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": []})
        with pytest.raises(BackendConfigError, match="backends"):
            load_backend_overrides(tmp_path)

    def test_block_not_object_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": {"codex": "gpt-5"}})
        with pytest.raises(BackendConfigError, match="codex"):
            load_backend_overrides(tmp_path)

    def test_model_wrong_type_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": {"codex": {"model": 7}}})
        with pytest.raises(BackendConfigError, match="model"):
            load_backend_overrides(tmp_path)

    def test_model_empty_string_raises(self, tmp_path: Path) -> None:
        _write(tmp_path, {"backends": {"codex": {"model": "   "}}})
        with pytest.raises(BackendConfigError, match="model"):
            load_backend_overrides(tmp_path)

    def test_extra_argv_not_list_raises(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {"backends": {"codex": {"extra_streaming_argv": "--foo"}}},
        )
        with pytest.raises(BackendConfigError, match="extra_streaming_argv"):
            load_backend_overrides(tmp_path)

    def test_extra_argv_non_string_element_raises(self, tmp_path: Path) -> None:
        _write(
            tmp_path,
            {"backends": {"codex": {"extra_batch_argv": ["--ok", 3]}}},
        )
        with pytest.raises(BackendConfigError, match="extra_batch_argv"):
            load_backend_overrides(tmp_path)
