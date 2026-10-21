"""Tests for the in-memory complete-bundle roadmap gate checker."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from plan_tool import roadmap_impact_snapshot
from plan_tool.roadmap import RoadmapStage
from plan_tool.roadmap_artifacts import RoadmapArtifactError
from plan_tool.roadmap_gates import ArtifactEnvelope, Violation
from plan_tool.roadmap_impact_snapshot import (
    CompleteRoadmapGateEvidence,
    RoadmapImpactSnapshotError,
    check_complete_roadmap_gates,
)


_ARTIFACT_KEYS = ("domain", "constraints", "components", "plans")


@dataclass(frozen=True)
class _Artifact:
    value: str


def _parse_artifact(text: str) -> _Artifact:
    if text == "malformed\n":
        raise RoadmapArtifactError("malformed test artifact")
    return _Artifact(text.removeprefix("canonical:"))


def _render_artifact(artifact: _Artifact) -> str:
    return f"canonical:{artifact.value}"


def _stage(key: str, number: int, *, gates=None) -> RoadmapStage:
    return RoadmapStage(
        number=number,
        name=key,
        prompt_filename="unused",
        artifact_key=key,
        parse=_parse_artifact,
        render=_render_artifact,
        gates=(lambda _envelope: []) if gates is None else gates,
    )


def _stages(*, gates_by_key: dict[str, Any] | None = None) -> tuple[RoadmapStage, ...]:
    return tuple(
        _stage(
            key,
            number,
            gates=None if gates_by_key is None else gates_by_key.get(key),
        )
        for number, key in enumerate(_ARTIFACT_KEYS, start=1)
    )


def _evidence(**updates: object) -> CompleteRoadmapGateEvidence:
    texts = tuple(f"canonical:{key}\n" for key in _ARTIFACT_KEYS)
    evidence = CompleteRoadmapGateEvidence(
        artifact_keys=_ARTIFACT_KEYS,
        artifact_texts=texts,
        artifacts=tuple(_Artifact(f"{key}\n") for key in _ARTIFACT_KEYS),
        artifact_digests=tuple(hashlib.sha256(text.encode()).hexdigest() for text in texts),
    )
    return evidence.model_copy(update=updates) if updates else evidence


_CARRIED_BRIEF = (
    "## Carried decisions\n\n```json\n"
    '{"confirmed_answers":[{"id":"answer-1","answer":"Use queues","status":"confirmed"}],'
    '"decisions":[{"id":"decision-1","owner":"domain","anchor":"entity-1",'
    '"chosen_option":"Use queues","source":"answer-1"}]}\n```\n'
)


def test_direct_complete_bundle_checker_reuses_the_shared_ordered_gate_walk() -> None:
    envelopes: list[ArtifactEnvelope] = []

    def gate(envelope: ArtifactEnvelope) -> list[Violation]:
        envelopes.append(envelope)
        return []

    stages = _stages(gates_by_key={key: gate for key in _ARTIFACT_KEYS})
    evidence = _evidence()

    outcomes = check_complete_roadmap_gates(evidence, stages=stages)

    assert [outcome.stage for outcome in outcomes] == list(stages)
    assert [envelope.predecessor for envelope in envelopes] == [None] * len(stages)
    assert [envelope.artifact_under_check for envelope in envelopes] == list(evidence.artifacts)


def test_complete_bundle_reports_a_stage_violation_as_an_outcome_without_raising() -> None:
    def reject(envelope: ArtifactEnvelope) -> list[Violation]:
        if envelope.artifact_under_check == _Artifact("components\n"):
            return [
                Violation(
                    kind="test-gate-violation",
                    artifact="components.md",
                    row_id=None,
                    message="the shared gate rejected this artifact",
                )
            ]
        return []

    stages = _stages(gates_by_key={key: reject for key in _ARTIFACT_KEYS})

    outcomes = check_complete_roadmap_gates(_evidence(), stages=stages)

    assert [bool(outcome.violations) for outcome in outcomes] == [False, False, True, False]
    assert outcomes[2].stage is stages[2]


def test_complete_bundle_gates_receive_carried_decisions_from_stored_brief() -> None:
    envelopes: list[ArtifactEnvelope] = []

    def gate(envelope: ArtifactEnvelope) -> list[Violation]:
        envelopes.append(envelope)
        return []

    stages = _stages(gates_by_key={key: gate for key in _ARTIFACT_KEYS})

    check_complete_roadmap_gates(_evidence(brief_bytes=_CARRIED_BRIEF.encode()), stages=stages)

    assert len(envelopes) == len(stages)
    assert all(envelope.carried_decisions.decisions[0].source == "answer-1" for envelope in envelopes)


def test_complete_bundle_gates_parse_crlf_carried_brief() -> None:
    envelopes: list[ArtifactEnvelope] = []

    def gate(envelope: ArtifactEnvelope) -> list[Violation]:
        envelopes.append(envelope)
        return []

    stages = _stages(gates_by_key={key: gate for key in _ARTIFACT_KEYS})
    brief = _CARRIED_BRIEF.replace("\n", "\r\n").encode()

    check_complete_roadmap_gates(_evidence(brief_bytes=brief), stages=stages)

    assert len(envelopes) == len(stages)
    assert all(envelope.carried_decisions.decisions[0].source == "answer-1" for envelope in envelopes)


@pytest.mark.parametrize(
    "evidence_update",
    (
        {"artifact_keys": _ARTIFACT_KEYS[:-1]},
        {"artifact_keys": tuple(reversed(_ARTIFACT_KEYS))},
        {"artifact_digests": ("0" * 64, "1" * 64, "2" * 64, "3" * 64)},
        {"artifacts": (_Artifact("wrong\n"), *(_Artifact(f"{key}\n") for key in _ARTIFACT_KEYS[1:]))},
    ),
)
def test_direct_complete_bundle_checker_rejects_invalid_evidence_before_gates(
    evidence_update: dict[str, object],
) -> None:
    calls: list[ArtifactEnvelope] = []
    stages = _stages(gates_by_key={key: lambda envelope: calls.append(envelope) for key in _ARTIFACT_KEYS})

    with pytest.raises(RoadmapImpactSnapshotError):
        check_complete_roadmap_gates(_evidence(**evidence_update), stages=stages)

    assert calls == []


def test_the_recorded_source_capture_path_is_deleted() -> None:
    """Deliberate: nothing captures a snapshot from ``source.json`` or top-level stage files any
    more, so the capture/recheck functions and their brief-baseline errors no longer exist."""
    for removed in (
        "capture_roadmap_impact_snapshot",
        "recheck_roadmap_impact_snapshot",
        "check_full_roadmap_gates",
        "RoadmapImpactSnapshot",
        "CandidateSubstitution",
        "ChangedRoadmapBriefBaselineError",
        "LegacyRoadmapBriefBaselineError",
        "StaleRoadmapImpactSnapshotError",
    ):
        assert not hasattr(roadmap_impact_snapshot, removed), removed
