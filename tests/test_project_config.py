"""Unit coverage for the branch-awareness config leaf.

Every level resolves against a ``tmp_path`` repo root and the
conftest-pinned temp ``$HOME`` (``_isolate_known_roots_cache``) — no real
git, no ``claude``. The bad-prefix warning is asserted via ``capsys``.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

from plan_tool import project_config as pc
from plan_tool.roadmap_artifacts import (
    HARD_MAX_ACTIVE_FEEDBACK_ITEMS,
    HARD_MAX_PROSE_AMENDMENT_BYTES,
    HARD_MAX_RESPONSE_BYTES,
)


def test_config_leaf_has_no_plan_tool_imports() -> None:
    assert "from plan_tool" not in inspect.getsource(pc)
    assert "import plan_tool" not in inspect.getsource(pc)


def test_config_hard_limits_match_the_artifact_feedback_comment_limits() -> None:
    assert (
        pc.HARD_MAX_ACTIVE_FEEDBACK_ITEMS,
        pc.HARD_MAX_RESPONSE_BYTES,
        pc.HARD_MAX_PROSE_AMENDMENT_BYTES,
    ) == (
        HARD_MAX_ACTIVE_FEEDBACK_ITEMS,
        HARD_MAX_RESPONSE_BYTES,
        HARD_MAX_PROSE_AMENDMENT_BYTES,
    )


def _write_project(repo_root: Path, payload: dict) -> None:
    path = pc.project_config_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_user(payload: dict) -> None:
    path = pc.user_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


# --- branch_awareness_enabled -------------------------------------------


def test_disabled_by_default(tmp_path: Path) -> None:
    assert pc.branch_awareness_enabled(tmp_path) is False


@pytest.mark.parametrize("token", ["1", "true", "yes", "on", " TRUE ", "On"])
def test_env_truthy_enables(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    monkeypatch.setenv(pc.BRANCH_AWARENESS_ENV, token)
    assert pc.branch_awareness_enabled(tmp_path) is True


@pytest.mark.parametrize("token", ["0", "false", "no", "off", " Off "])
def test_env_falsy_overrides_project_true(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    _write_project(tmp_path, {"branch_awareness": {"enabled": True}})
    monkeypatch.setenv(pc.BRANCH_AWARENESS_ENV, token)
    assert pc.branch_awareness_enabled(tmp_path) is False


def test_env_unrecognized_falls_through(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_project(tmp_path, {"branch_awareness": {"enabled": True}})
    monkeypatch.setenv(pc.BRANCH_AWARENESS_ENV, "maybe")
    assert pc.branch_awareness_enabled(tmp_path) is True


def test_project_enabled_true(tmp_path: Path) -> None:
    _write_project(tmp_path, {"branch_awareness": {"enabled": True}})
    assert pc.branch_awareness_enabled(tmp_path) is True


def test_project_false_overrides_user_true(tmp_path: Path) -> None:
    _write_project(tmp_path, {"branch_awareness": {"enabled": False}})
    _write_user({"branch_awareness": {"enabled": True}})
    assert pc.branch_awareness_enabled(tmp_path) is False


def test_user_default_when_no_project(tmp_path: Path) -> None:
    _write_user({"branch_awareness": {"enabled": True}})
    assert pc.branch_awareness_enabled(tmp_path) is True


def test_malformed_project_json_swallowed(tmp_path: Path) -> None:
    path = pc.project_config_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ this is not json", encoding="utf-8")
    _write_user({"branch_awareness": {"enabled": True}})
    assert pc.branch_awareness_enabled(tmp_path) is True


def test_non_object_top_level_swallowed(tmp_path: Path) -> None:
    path = pc.project_config_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert pc.branch_awareness_enabled(tmp_path) is False


def test_missing_branch_awareness_block(tmp_path: Path) -> None:
    _write_project(tmp_path, {"something_else": {}})
    assert pc.branch_awareness_enabled(tmp_path) is False


def test_non_bool_enabled_treated_unset(tmp_path: Path) -> None:
    _write_project(tmp_path, {"branch_awareness": {"enabled": "true"}})
    assert pc.branch_awareness_enabled(tmp_path) is False


# --- branch_prefixes ----------------------------------------------------


def test_prefixes_default(tmp_path: Path) -> None:
    assert pc.branch_prefixes(tmp_path) == ["plan/"]


def test_prefixes_project_over_user(tmp_path: Path) -> None:
    _write_project(tmp_path, {"branch_awareness": {"branch_prefixes": ["feature/"]}})
    _write_user({"branch_awareness": {"branch_prefixes": ["bugfix/"]}})
    assert pc.branch_prefixes(tmp_path) == ["feature/"]


def test_prefixes_bad_list_warns_and_defaults(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(tmp_path, {"branch_awareness": {"branch_prefixes": []}})
    assert pc.branch_prefixes(tmp_path) == ["plan/"]
    err = capsys.readouterr().err
    assert err.count("invalid") == 1
    assert str(pc.project_config_path(tmp_path)) in err


def test_prefixes_invalid_element_falls_back(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(
        tmp_path, {"branch_awareness": {"branch_prefixes": ["pl an/"]}}
    )
    assert pc.branch_prefixes(tmp_path) == ["plan/"]
    assert "invalid" in capsys.readouterr().err


def test_enabled_independent_of_bad_prefixes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _write_project(
        tmp_path,
        {"branch_awareness": {"enabled": True, "branch_prefixes": "nope"}},
    )
    assert pc.branch_awareness_enabled(tmp_path) is True
    assert pc.branch_prefixes(tmp_path) == ["plan/"]
    assert "invalid" in capsys.readouterr().err


# --- derive_branch / convention_names -----------------------------------


def test_derive_branch_uses_primary_prefix() -> None:
    assert pc.derive_branch("my-slug", ["plan/", "bugfix/"]) == "plan/my-slug"


def test_convention_names_all_prefixes() -> None:
    assert pc.convention_names("my-slug", ["plan/", "feature/"]) == [
        "plan/my-slug",
        "feature/my-slug",
    ]


# --- path helpers and error type ----------------------------------------


def test_user_config_path_lazy_home(tmp_path: Path) -> None:
    # The conftest fixture pins Path.home() to a temp dir per test.
    assert pc.user_config_path() == Path.home() / ".plan-tool" / "config.json"
    assert str(Path.home()) in str(pc.user_config_path())


def test_project_config_path(tmp_path: Path) -> None:
    path = pc.project_config_path(tmp_path)
    assert path == (tmp_path / ".plan-tool" / "config.json").resolve()


def test_project_config_error_is_exception() -> None:
    assert issubclass(pc.ProjectConfigError, Exception)


# --- stage_feedback_limits ----------------------------------------------


def test_stage_feedback_limits_default_to_hard_ceilings_and_accept_stricter_project_values(
    tmp_path: Path,
) -> None:
    assert pc.stage_feedback_limits(tmp_path) == pc.StageFeedbackLimits()

    _write_project(
        tmp_path,
        {
            "roadmap_feedback": {
                "stage_limits": {
                    "max_active_feedback_items": 3,
                    "max_response_bytes": 300,
                    "max_prose_amendment_bytes": 200,
                }
            }
        },
    )

    assert pc.stage_feedback_limits(tmp_path) == pc.StageFeedbackLimits(3, 300, 200)


@pytest.mark.parametrize(
    "payload",
    (
        {"roadmap_feedback": {}},
        {"roadmap_feedback": {"stage_limits": []}},
        {"roadmap_feedback": {"unknown": {}}},
        {"roadmap_feedback": {"stage_limits": {"unknown": 1}}},
        {
            "roadmap_feedback": {
                "stage_limits": {"max_response_bytes": True}
            }
        },
        {
            "roadmap_feedback": {
                "stage_limits": {"max_response_bytes": "32"}
            }
        },
        {
            "roadmap_feedback": {
                "stage_limits": {"max_response_bytes": pc.HARD_MAX_RESPONSE_BYTES + 1}
            }
        },
        {
            "roadmap_feedback": {
                "stage_limits": {
                    "max_response_bytes": 20,
                    "max_prose_amendment_bytes": 21,
                }
            }
        },
    ),
)
def test_stage_feedback_limit_config_fails_closed_on_malformed_project_blocks(
    tmp_path: Path, payload: dict
) -> None:
    _write_project(tmp_path, payload)

    with pytest.raises(pc.ProjectConfigError):
        pc.stage_feedback_limits(tmp_path)


def test_stage_feedback_limits_never_read_user_configuration(tmp_path: Path) -> None:
    _write_user(
        {
            "roadmap_feedback": {
                "stage_limits": {
                    "max_active_feedback_items": 1,
                    "max_response_bytes": 2,
                    "max_prose_amendment_bytes": 1,
                }
            }
        }
    )

    assert pc.stage_feedback_limits(tmp_path) == pc.StageFeedbackLimits()


def test_is_valid_branch_prefix() -> None:
    for good in ("plan/", "feature/", "team/plan/"):
        assert pc._is_valid_branch_prefix(good) is True
    for bad in ("", "plan", "pl an/", "plan~/", "plan/../", "/plan/", 1, None):
        assert pc._is_valid_branch_prefix(bad) is False


# --- validation_machinery_paths -----------------------------------------


class TestValidationMachineryPaths:
    """Resolve project → user, no env axis, fail-soft on a bad list."""

    _BLOCK = pc.SMELL_CONFIG_BLOCK
    _KEY = pc.VALIDATION_MACHINERY_PATHS_KEY

    def test_unconfigured_returns_empty(self, tmp_path: Path) -> None:
        assert pc.validation_machinery_paths(tmp_path) == []

    def test_project_over_user(self, tmp_path: Path) -> None:
        _write_project(
            tmp_path, {self._BLOCK: {self._KEY: ["plan_tool/review.py"]}}
        )
        _write_user({self._BLOCK: {self._KEY: ["plan_tool/gates.py"]}})
        assert pc.validation_machinery_paths(tmp_path) == [
            "plan_tool/review.py"
        ]

    def test_user_when_no_project(self, tmp_path: Path) -> None:
        _write_user({self._BLOCK: {self._KEY: ["plan_tool/gates.py"]}})
        assert pc.validation_machinery_paths(tmp_path) == [
            "plan_tool/gates.py"
        ]

    def test_no_env_axis(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The set is repo-structural — no PLAN_TOOL_* override. A plausibly
        # named env var must not change the unconfigured-empty result.
        monkeypatch.setenv(
            "PLAN_TOOL_VALIDATION_MACHINERY_PATHS", "plan_tool/review.py"
        )
        assert pc.validation_machinery_paths(tmp_path) == []
        _write_project(
            tmp_path, {self._BLOCK: {self._KEY: ["plan_tool/gates.py"]}}
        )
        assert pc.validation_machinery_paths(tmp_path) == [
            "plan_tool/gates.py"
        ]

    @pytest.mark.parametrize(
        "bad",
        ["not-a-list", [], ["", "ok"], [1, "ok"]],
    )
    def test_bad_list_warns_and_returns_empty(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        bad: object,
    ) -> None:
        _write_project(tmp_path, {self._BLOCK: {self._KEY: bad}})
        assert pc.validation_machinery_paths(tmp_path) == []
        err = capsys.readouterr().err
        assert err.count("invalid") == 1
        assert str(pc.project_config_path(tmp_path)) in err

    def test_malformed_json_swallowed(self, tmp_path: Path) -> None:
        path = pc.project_config_path(tmp_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{ not json", encoding="utf-8")
        _write_user({self._BLOCK: {self._KEY: ["plan_tool/gates.py"]}})
        # Broken project falls through to user, never raises.
        assert pc.validation_machinery_paths(tmp_path) == [
            "plan_tool/gates.py"
        ]

    def test_is_valid_path_list(self) -> None:
        assert pc._is_valid_path_list(["a", "b/c.py"]) is True
        for bad in ("nope", [], ["", "x"], [1], [None], {}):
            assert pc._is_valid_path_list(bad) is False


# --- require_merged_plan ------------------------------------------------


def test_merged_plan_check_is_on_by_default(tmp_path: Path) -> None:
    assert pc.require_merged_plan(tmp_path) is True


@pytest.mark.parametrize("token,expected", [("0", False), ("off", False), ("1", True), ("TRUE", True)])
def test_merged_plan_env_token_sets_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, token: str, expected: bool
) -> None:
    monkeypatch.setenv(pc.REQUIRE_MERGED_PLAN_ENV, token)
    assert pc.require_merged_plan(tmp_path) is expected


def test_merged_plan_env_beats_the_project_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_project(tmp_path, {"run": {"require_merged_plan": False}})
    monkeypatch.setenv(pc.REQUIRE_MERGED_PLAN_ENV, "1")
    assert pc.require_merged_plan(tmp_path) is True


def test_merged_plan_project_false_turns_the_check_off_and_beats_the_user_file(tmp_path: Path) -> None:
    _write_user({"run": {"require_merged_plan": True}})
    _write_project(tmp_path, {"run": {"require_merged_plan": False}})
    assert pc.require_merged_plan(tmp_path) is False


def test_merged_plan_user_file_applies_when_the_project_is_silent(tmp_path: Path) -> None:
    _write_user({"run": {"require_merged_plan": False}})
    assert pc.require_merged_plan(tmp_path) is False


@pytest.mark.parametrize("value", ["false", 0, None, "no"])
def test_merged_plan_non_bool_values_fall_through_to_the_default(tmp_path: Path, value: object) -> None:
    # A quoted "false" must not silently switch a safety check off.
    _write_project(tmp_path, {"run": {"require_merged_plan": value}})
    assert pc.require_merged_plan(tmp_path) is True


def test_merged_plan_unrecognized_env_falls_through(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(pc.REQUIRE_MERGED_PLAN_ENV, "maybe")
    assert pc.require_merged_plan(tmp_path) is True
