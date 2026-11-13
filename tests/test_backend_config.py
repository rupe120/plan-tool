"""Tests for plan_tool.backend_config — per-project backend tuning file."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.mark.parametrize("reader", ["legacy", "lookup", "project"])
def test_explicit_config_path_wins_over_project_convention(tmp_path, reader):
    from plan_tool.backend_config import load_project_backend_config

    _write(tmp_path, {"backends": {"codex": {"model": "conventional"}}})
    explicit = tmp_path / "selected.json"
    explicit.write_text(json.dumps({"default_backend": "codex", "backends": {
        "codex": {"model": "selected", "commands": {"run": {"model": "command"}}}
    }}))
    if reader == "legacy":
        assert load_backend_overrides(tmp_path, path=explicit)["codex"].model == "selected"
    elif reader == "lookup":
        assert backend_override_for("codex", tmp_path, path=explicit).model == "selected"
    else:
        config = load_project_backend_config(tmp_path, path=explicit, command_names={"run": "run"})
        assert config.default_backend == "codex"
        assert config.overrides["codex"].model == "selected"
        assert config.command_models == {"codex": {"run": "command"}}

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


class TestProjectBackendConfig:
    @pytest.mark.parametrize('value', [None, '', '  ', 3, [], {}])
    def test_explicit_default_requires_nonempty_string(self, tmp_path, value):
        from plan_tool.backend_config import load_project_backend_config
        _write(tmp_path, {'default_backend': value})
        with pytest.raises(BackendConfigError, match='default_backend') as error:
            load_project_backend_config(tmp_path, command_names={})
        assert str(default_backends_config_path(tmp_path)) in str(error.value)

    @pytest.mark.parametrize('entry', [{}, {'model': None}, {'model': ' model-x '}])
    def test_alias_models_normalize_and_null_inherits(self, tmp_path, entry):
        from plan_tool.backend_config import load_project_backend_config
        _write(tmp_path, {'default_backend': ' custom ', 'backends': {'custom': {
            'model': 'base', 'commands': {'alias': entry}}}})
        config = load_project_backend_config(tmp_path, command_names={'run': 'run', 'alias': 'run'})
        assert config.default_backend == 'custom'
        assert config.command_models == {'custom': {'run': 'model-x' if entry.get('model') else None}}
        assert config.overrides == load_backend_overrides(tmp_path)

    @pytest.mark.parametrize('commands', [None, [], {'run': None}, {'run': []},
        {'run': {'model': ''}}, {'run': {'model': 1}}, {'unknown': {}},
        {'run': {}, 'alias': {}}])
    def test_invalid_commands_fail_without_changing_file(self, tmp_path, commands):
        from plan_tool.backend_config import load_project_backend_config
        _write(tmp_path, {'backends': {'custom': {'commands': commands}}})
        path = default_backends_config_path(tmp_path)
        before = path.read_bytes()
        with pytest.raises(BackendConfigError) as error:
            load_project_backend_config(tmp_path, command_names={'run': 'run', 'alias': 'run'})
        assert str(path) in str(error.value)
        assert 'commands' in str(error.value)
        if isinstance(commands, dict) and 'unknown' in commands:
            assert 'supported choices: alias, run' in str(error.value)
        assert path.read_bytes() == before
        assert load_backend_overrides(tmp_path)['custom'].model is None

    def test_missing_config_does_not_create_files(self, tmp_path):
        from plan_tool.backend_config import load_project_backend_config, ProjectBackendConfig
        assert load_project_backend_config(tmp_path, command_names={}) == ProjectBackendConfig()
        assert list(tmp_path.iterdir()) == []

    def test_command_identity_comes_from_parsers_not_shared_handlers(self):
        from types import SimpleNamespace
        from plan_tool.cli.parser import assemble, command_name_map
        def handler():
            pass
        def register(subparsers):
            subparsers.add_parser('run', aliases=['r'])
            subparsers.add_parser('review')
            return {'run': handler, 'r': handler, 'review': handler}
        parser, _ = assemble('test', [SimpleNamespace(register=register)])
        assert command_name_map(parser) == {'run': 'run', 'r': 'run', 'review': 'review'}
