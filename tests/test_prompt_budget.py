"""Unit tests for the ``prompt_budget`` leaf: the byte→token estimate, the
headroom classifier, the emit gate, and color/leaf discipline."""

from __future__ import annotations

import ast
import io
import math
from pathlib import Path

import pytest

from plan_tool import prompt_budget as pb
from plan_tool.prompt_budget import (
    BYTES_PER_TOKEN,
    DEFAULT_CONTEXT_WINDOW,
    HIGH_HEADROOM_RATIO,
    LEVEL_HIGH,
    LEVEL_OK,
    LEVEL_WARN,
    WARN_HEADROOM_RATIO,
    PromptBudget,
    estimate_prompt_budget,
    maybe_warn_prompt_budget,
)


def _window_for_headroom(ratio: float, tokens: int) -> int:
    """Window sized so ``tokens`` leaves exactly ``ratio`` headroom."""
    return math.ceil(tokens / (1 - ratio))


# --- estimate_prompt_budget ------------------------------------------------


def test_estimate_rounds_tokens_up():
    # 100 / 3.5 = 28.57… → ceil 29
    budget = estimate_prompt_budget(100)
    assert budget.estimated_tokens == math.ceil(100 / BYTES_PER_TOKEN) == 29


def test_estimate_uses_default_window_when_none():
    assert estimate_prompt_budget(100).context_window == DEFAULT_CONTEXT_WINDOW


def test_estimate_guards_nonpositive_window():
    budget = estimate_prompt_budget(100, context_window=0)
    assert budget.context_window == DEFAULT_CONTEXT_WINDOW


def test_level_ok_above_warn_threshold():
    # Tiny prompt against a big window → almost all headroom.
    assert estimate_prompt_budget(100, context_window=200_000).level == LEVEL_OK


def test_level_warn_between_thresholds():
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    # Headroom 0.30 sits in [0.15, 0.40).
    window = _window_for_headroom(0.30, tokens)
    budget = estimate_prompt_budget(1000, context_window=window)
    assert budget.level == LEVEL_WARN
    assert HIGH_HEADROOM_RATIO <= budget.headroom_ratio < WARN_HEADROOM_RATIO


def test_level_high_below_high_threshold():
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    window = _window_for_headroom(0.05, tokens)
    budget = estimate_prompt_budget(1000, context_window=window)
    assert budget.level == LEVEL_HIGH
    assert budget.headroom_ratio < HIGH_HEADROOM_RATIO


def test_level_high_when_estimate_exceeds_window():
    # 1M bytes ≈ 286K tokens against a 200K window → negative headroom.
    budget = estimate_prompt_budget(1_000_000, context_window=200_000)
    assert budget.level == LEVEL_HIGH
    assert budget.headroom_ratio < 0


def test_boundary_at_warn_ratio():
    # 2100 bytes → exactly 600 tokens; a 1000 window leaves exactly 0.40
    # headroom, which must stay ok (the ``<`` boundary excludes equality).
    assert math.ceil(2100 / BYTES_PER_TOKEN) == 600
    budget = estimate_prompt_budget(2100, context_window=1000)
    assert budget.headroom_ratio == WARN_HEADROOM_RATIO
    assert budget.level == LEVEL_OK


def test_blocks_sorted_by_bytes_descending():
    budget = estimate_prompt_budget(
        600, blocks={"small": 100, "big": 300, "mid": 200}
    )
    assert budget.blocks == (("big", 300), ("mid", 200), ("small", 100))


def test_blocks_accepts_pair_sequence():
    budget = estimate_prompt_budget(300, blocks=[("a", 100), ("b", 200)])
    assert budget.blocks == (("b", 200), ("a", 100))


# --- maybe_warn_prompt_budget ----------------------------------------------


def test_maybe_warn_silent_at_ok():
    stream = io.StringIO()
    budget = maybe_warn_prompt_budget(100, context_window=200_000, stream=stream)
    assert budget.level == LEVEL_OK
    assert stream.getvalue() == ""


def test_maybe_warn_emits_at_warn_and_high():
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    window = _window_for_headroom(0.30, tokens)
    stream = io.StringIO()
    maybe_warn_prompt_budget(
        1000,
        context_window=window,
        blocks={"seed": 800, "context": 200},
        remedies=["--step N", "scope-out"],
        stream=stream,
    )
    out = stream.getvalue()
    assert out != ""
    assert "seed" in out          # top block name
    assert "--step N" in out      # passed remedy
    assert "scope-out" in out


def test_maybe_warn_caps_block_list():
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    window = _window_for_headroom(0.05, tokens)
    blocks = {f"b{i}": (10 - i) for i in range(10)}
    stream = io.StringIO()
    maybe_warn_prompt_budget(1000, context_window=window, blocks=blocks, stream=stream)
    # Ellipsis marks the truncated tail beyond the top handful.
    assert "…" in stream.getvalue()


def test_maybe_warn_includes_surface_label():
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    window = _window_for_headroom(0.30, tokens)
    stream = io.StringIO()
    maybe_warn_prompt_budget(
        1000, context_window=window, surface="detail:step-3", stream=stream
    )
    assert "detail:step-3" in stream.getvalue()


def test_maybe_warn_returns_budget():
    stream = io.StringIO()
    result = maybe_warn_prompt_budget(100, context_window=200_000, stream=stream)
    assert isinstance(result, PromptBudget)
    # Same verdict the pure estimate would give.
    assert result == estimate_prompt_budget(100, context_window=200_000)


def test_maybe_warn_plain_on_non_tty(monkeypatch):
    monkeypatch.delenv("PLAN_TOOL_FORCE_COLOR", raising=False)
    tokens = math.ceil(1000 / BYTES_PER_TOKEN)
    window = _window_for_headroom(0.05, tokens)
    stream = io.StringIO()  # not a TTY
    maybe_warn_prompt_budget(1000, context_window=window, stream=stream)
    assert "\033[" not in stream.getvalue()


def test_maybe_warn_never_raises():
    for total in (0, 100, 10_000_000):
        for window in (None, 0, 200_000):
            stream = io.StringIO()
            budget = maybe_warn_prompt_budget(
                total, context_window=window, stream=stream
            )
            assert isinstance(budget, PromptBudget)


# --- shared summary formatter ----------------------------------------------


def test_render_budget_summary_caps_with_ellipsis():
    budget = pb.estimate_prompt_budget(
        700_000, blocks=[("a", 300), ("b", 200), ("c", 100)]
    )
    line = pb.render_budget_summary(budget, blocks_label="top blocks", max_blocks=2)
    assert "top blocks: a 300B, b 200B, …" in line
    assert "c 100B" not in line


def test_render_budget_summary_uncapped_shows_all():
    budget = pb.estimate_prompt_budget(
        700_000, blocks=[("a", 300), ("b", 200), ("c", 100)]
    )
    line = pb.render_budget_summary(budget, blocks_label="blocks", max_blocks=None)
    assert "blocks: a 300B, b 200B, c 100B" in line
    assert "…" not in line


def test_advisory_emits_the_shared_summary():
    """maybe_warn routes through render_budget_summary — single-source guard."""
    stream = io.StringIO()
    budget = pb.maybe_warn_prompt_budget(
        700_000, blocks=[("a", 300)], surface="x", remedies=("do y",), stream=stream
    )
    expected = pb.render_budget_summary(budget, surface="x", remedies=("do y",))
    assert expected in stream.getvalue()


# --- leaf discipline -------------------------------------------------------


def test_leaf_imports_are_cycle_free():
    src = Path(pb.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    first_party: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("plan_tool"):
            first_party.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("plan_tool"):
                    first_party.add(alias.name)
    assert first_party == {"plan_tool.style"}


# --- window_defaulted ------------------------------------------------------


@pytest.mark.parametrize("window", [None, 0, -5])
def test_a_missing_or_unusable_window_is_marked_defaulted_and_says_so(window):
    budget = estimate_prompt_budget(500_000, context_window=window)

    assert budget.window_defaulted is True
    assert budget.context_window == DEFAULT_CONTEXT_WINDOW
    assert "200,000 window (default)" in pb.render_budget_summary(budget)


def test_a_passed_window_is_not_marked_defaulted():
    budget = estimate_prompt_budget(500_000, context_window=200_000)

    assert budget.window_defaulted is False
    assert "(default)" not in pb.render_budget_summary(budget)
