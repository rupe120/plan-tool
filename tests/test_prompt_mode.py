"""Tests for the A/B prompt-mode selector (--prompt-mode / PLAN_TOOL_PROMPT_MODE)."""

from __future__ import annotations

import argparse

import pytest

from plan_tool.cli.authoring import _resolve_prompt_mode


def _args(prompt_mode=None, experiment_arm=None):
    return argparse.Namespace(
        prompt_mode=prompt_mode, experiment_arm=experiment_arm
    )


class TestResolvePromptMode:
    def test_combined_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert _resolve_prompt_mode() == "combined"
        assert _resolve_prompt_mode(_args()) == "combined"

    def test_env_split(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", "split")
        assert _resolve_prompt_mode() == "split"

    def test_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", "  SPLIT ")
        assert _resolve_prompt_mode() == "split"

    @pytest.mark.parametrize("val", ["combined", "", "bogus", "COMBINED"])
    def test_anything_else_falls_back_to_combined(
        self, monkeypatch: pytest.MonkeyPatch, val: str
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", val)
        assert _resolve_prompt_mode() == "combined"

    def test_flag_selects_split(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert _resolve_prompt_mode(_args("split")) == "split"

    def test_flag_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Precedence: flag > env. Flag=combined beats env=split.
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", "split")
        assert _resolve_prompt_mode(_args("combined")) == "combined"

    def test_flag_unset_falls_back_to_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", "split")
        assert _resolve_prompt_mode(_args(None)) == "split"

    def test_generic_experiment_arm_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # The generic --experiment-arm path selects the prompt-mode arm.
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert (
            _resolve_prompt_mode(_args(experiment_arm=["prompt-mode=split"]))
            == "split"
        )

    def test_dedicated_flag_beats_generic(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # --prompt-mode > --experiment-arm prompt-mode=…
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert (
            _resolve_prompt_mode(
                _args("combined", experiment_arm=["prompt-mode=split"])
            )
            == "combined"
        )

    def test_generic_arm_beats_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("PLAN_TOOL_PROMPT_MODE", "combined")
        assert (
            _resolve_prompt_mode(_args(experiment_arm=["prompt-mode=split"]))
            == "split"
        )

    def test_malformed_experiment_arm_ignored(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("PLAN_TOOL_PROMPT_MODE", raising=False)
        assert (
            _resolve_prompt_mode(_args(experiment_arm=["no-equals-sign"]))
            == "combined"
        )
