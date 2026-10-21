"""Tests for the roadmap publication journal and the ephemeral feedback snapshot."""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool import roadmap_source_identity
from plan_tool.roadmap_artifacts import (
    DomainArtifact,
    EntityRow,
    FeedbackRow,
    FeedbackState,
    FeedbackTarget,
    FeedbackTargetKind,
    RemovalRecord,
)
from plan_tool.roadmap_source_identity import (
    GenerationMember,
    PendingGeneration,
    RoadmapSourceIdentityError,
    feedback_snapshot,
    load_pending_generation,
    render_pending_generation,
)


def _artifact() -> DomainArtifact:
    return DomainArtifact(
        entities=(EntityRow("order", "Order", ()),),
        business_rules=(),
        workflows=(),
        decisions=(),
        body="Canonical domain prose.",
        feedback=(
            FeedbackRow(
                "feedback-order",
                FeedbackTarget(FeedbackTargetKind.ROW, "order"),
                "Clarify naming.",
                FeedbackState.OPEN,
            ),
        ),
        removals=(RemovalRecord("legacy-order", "Replaced by order.", ("feedback-order",)),),
    )


def test_source_identity_module_does_not_import_orchestrators() -> None:
    module = ast.parse((Path(__file__).resolve().parents[1] / "plan_tool" / "roadmap_source_identity.py").read_text())
    imports = {
        alias.name
        for node in ast.walk(module)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(module)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {
        "plan_tool.roadmap",
        "plan_tool.roadmap_escalation_run",
        "plan_tool.cli.roadmap_cmd",
    } & imports


def test_stage_baseline_api_is_gone() -> None:
    """The stage-baseline sidecar and its identity record no longer exist."""
    for name in (
        "BaselineRecord",
        "CanonicalSourceIdentity",
        "baseline_path",
        "baseline_record",
        "load_baseline_record",
        "render_baseline_record",
        "compare_baseline",
        "admit_baseline_backed_source",
    ):
        assert not hasattr(roadmap_source_identity, name)


def test_feedback_snapshot_is_ordered_ephemeral_input() -> None:
    artifact = _artifact()
    original = feedback_snapshot(artifact)
    reordered = replace(
        artifact,
        feedback=(
            FeedbackRow(
                "feedback-second",
                FeedbackTarget(FeedbackTargetKind.ARTIFACT),
                "Second feedback.",
                FeedbackState.OPEN,
            ),
            artifact.feedback[0],
        ),
    )

    assert feedback_snapshot(reordered) != original


def test_pending_generation_version_remains_a_journal_protocol(tmp_path: Path) -> None:
    journal = tmp_path / "pending.json"
    generation = PendingGeneration(
        "test",
        (
            GenerationMember("artifact.md", None, b"new"),
            GenerationMember("other/domain.json", b"old", None),
        ),
    )
    journal.write_bytes(render_pending_generation(generation))

    assert load_pending_generation(journal) == generation


def test_journal_refuses_duplicate_json_keys(tmp_path: Path) -> None:
    journal = tmp_path / "pending.json"
    journal.write_text(
        '{"version":1,"kind":"test","kind":"other","members":[]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RoadmapSourceIdentityError, match="duplicate JSON object key"):
        load_pending_generation(journal)


def test_journal_refuses_a_boolean_version_value(tmp_path: Path) -> None:
    journal = tmp_path / "pending.json"
    journal.write_text('{"version":true}\n', encoding="utf-8")

    with pytest.raises(RoadmapSourceIdentityError, match="unsupported format"):
        load_pending_generation(journal)


@pytest.mark.parametrize("constant", ("NaN", "Infinity", "-Infinity"))
def test_journal_refuses_nonfinite_json_constants(tmp_path: Path, constant: str) -> None:
    journal = tmp_path / "pending.json"
    journal.write_text(
        '{"version":1,"kind":"test","members":[{"path":"artifact.md",'
        '"old":{"present":true,"data":' + constant + '},"new":{"present":false}}]}\n',
        encoding="utf-8",
    )

    with pytest.raises(RoadmapSourceIdentityError, match="non-finite JSON constant"):
        load_pending_generation(journal)
