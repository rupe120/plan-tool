"""Tests for the decision-settlement run result types shared with the enrolled runner."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import get_args

import pytest

from plan_tool import roadmap_decision_settlement_run as run_module
from plan_tool.roadmap_decision_settlement_run import (
    DecisionSettlementRunRefusal,
    DecisionSettlementRunResult,
)


MODULE_PATH = (
    Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_decision_settlement_run.py"
)


def test_result_carries_only_outcome_status_refusal_and_receipt_id() -> None:
    result = run_module._result("settled", receipt_id="receipt-1")

    assert result.outcome == "settled"
    assert result.receipt_id == "receipt-1"
    fields = {field.name for field in dataclasses.fields(DecisionSettlementRunResult)}
    assert fields == {"outcome", "status", "refusal", "receipt_id"}


@pytest.mark.parametrize(
    "outcome, expected_status",
    (
        ("settled", 0),
        ("preflight-rejected", 2),
        ("receipt-rejected", 1),
        ("write-failed", 1),
        ("interrupted", 130),
    ),
)
def test_every_outcome_maps_to_its_status(outcome: str, expected_status: int) -> None:
    assert run_module._result(outcome).status == expected_status


def test_the_removed_unenrolled_runner_and_its_fallback_refusal_are_gone() -> None:
    """Deliberate: ``--settle-decision`` dispatches straight to the enrolled runner, so the
    un-enrolled runner and the ``enrolled-roadmap-rejected`` fallback signal no longer exist."""
    assert not hasattr(run_module, "run_unenrolled_decision_settlement")
    assert not hasattr(run_module, "ENROLLED_ROADMAP_FALLBACK_REFUSAL")
    refusals = {
        value
        for member in get_args(DecisionSettlementRunRefusal)
        for value in (get_args(member) or (member,))
    }
    assert "enrolled-roadmap-rejected" not in refusals
    assert "unenrolled-roadmap-rejected" not in refusals


def test_module_is_types_only_and_writes_nothing() -> None:
    source = MODULE_PATH.read_text(encoding="utf-8")
    banned = (
        "write_bytes",
        "write_text",
        "durable_write",
        "publish_roadmap_generation",
        "publish_stage_artifact",
        "accepted_head",
        "unlink",
        "invoker",
        "RunLogWriter",
    )
    for token in banned:
        assert token not in source, token
    assert re.search(r"^from plan_tool\.cli|^import plan_tool\.cli", source, re.MULTILINE) is None
