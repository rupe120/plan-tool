"""Gate one complete in-memory roadmap bundle for candidates, promotion, and settlement."""

from __future__ import annotations

import hashlib
import io
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from plan_tool.roadmap import STAGES, RoadmapStage
from plan_tool.roadmap_artifacts import RoadmapArtifactError
from plan_tool.roadmap_gates import ArtifactEnvelope, Violation
from plan_tool.roadmap_source import (
    CarriedDecisions,
    RoadmapSourceError,
    parse_carried_decisions,
)


class RoadmapImpactSnapshotError(ValueError):
    """The supplied roadmap evidence cannot be gated."""


@dataclass(frozen=True)
class RoadmapGateOutcome:
    """The violations one stage reports during a full-roadmap gate check."""

    stage: RoadmapStage
    violations: tuple[Violation, ...]


class _FrozenGateEvidence(BaseModel):
    """Closed value records used by the in-memory complete-bundle route."""

    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, arbitrary_types_allowed=True
    )


class CompleteRoadmapGateEvidence(_FrozenGateEvidence):
    """Every raw and parsed member needed to gate one immutable candidate."""

    artifact_keys: tuple[str, ...]
    artifact_texts: tuple[str, ...]
    artifacts: tuple[Any, ...]
    artifact_digests: tuple[str, ...]
    brief_bytes: bytes | None = None


def _decode_brief_bytes(brief_bytes: bytes) -> str:
    """Apply the roadmap text reader's UTF-8 universal-newline semantics in memory."""
    return io.TextIOWrapper(io.BytesIO(brief_bytes), encoding="utf-8", newline=None).read()


def _parse_carried_brief_bytes(brief_bytes: bytes | None) -> CarriedDecisions | None:
    if brief_bytes is None:
        return None
    try:
        return parse_carried_decisions(
            _decode_brief_bytes(brief_bytes), brief_path=Path("stored roadmap brief")
        )
    except (RoadmapSourceError, UnicodeDecodeError) as exc:
        raise RoadmapImpactSnapshotError("complete roadmap brief is malformed") from exc


def check_complete_roadmap_gates(
    evidence: CompleteRoadmapGateEvidence,
    *,
    stages: Sequence[RoadmapStage] = STAGES,
) -> tuple[RoadmapGateOutcome, ...]:
    """Gate one complete in-memory bundle after every member binds exactly.

    This boundary has no live-path fallback and no substitution slot. The raw
    bytes, parsed values, and stage table must all agree before the shared
    ordered evaluator is allowed to run.
    """
    if not isinstance(evidence, CompleteRoadmapGateEvidence):
        raise RoadmapImpactSnapshotError("complete roadmap gate evidence has the wrong type")
    expected_keys = tuple(stage.artifact_key for stage in stages)
    values = (
        evidence.artifact_keys,
        evidence.artifact_texts,
        evidence.artifacts,
        evidence.artifact_digests,
    )
    if (
        not all(isinstance(value, tuple) for value in values)
        or not expected_keys
        or len(set(expected_keys)) != len(expected_keys)
        or any(len(value) != len(stages) for value in values)
        or evidence.artifact_keys != expected_keys
    ):
        raise RoadmapImpactSnapshotError(
            "complete roadmap gate evidence does not match the supplied stage table"
        )

    try:
        for stage, text, artifact, digest in zip(
            stages,
            evidence.artifact_texts,
            evidence.artifacts,
            evidence.artifact_digests,
            strict=True,
        ):
            if not isinstance(text, str) or not isinstance(digest, str):
                raise RoadmapImpactSnapshotError(
                    "complete roadmap gate evidence must retain text and raw digests"
                )
            raw_bytes = text.encode("utf-8")
            if raw_bytes.decode("utf-8") != text:
                raise RoadmapImpactSnapshotError(
                    "complete roadmap gate evidence text is not strict UTF-8"
                )
            if hashlib.sha256(raw_bytes).hexdigest() != digest:
                raise RoadmapImpactSnapshotError(
                    "complete roadmap gate evidence digest does not match its text"
                )
            if stage.parse(text) != artifact:
                raise RoadmapImpactSnapshotError(
                    "complete roadmap gate evidence parsed artifact does not match its text"
                )
    except RoadmapImpactSnapshotError:
        raise
    except (AttributeError, RoadmapArtifactError, TypeError, UnicodeError, ValueError) as exc:
        raise RoadmapImpactSnapshotError(
            "complete roadmap gate evidence cannot be parsed by the supplied stage table"
        ) from exc

    return _evaluate_full_roadmap_gates(
        stages=stages,
        artifacts=evidence.artifacts,
        carried_decisions=_parse_carried_brief_bytes(evidence.brief_bytes),
    )


def _evaluate_full_roadmap_gates(
    *,
    stages: Sequence[RoadmapStage],
    artifacts: Sequence[Any],
    carried_decisions: CarriedDecisions | None = None,
) -> tuple[RoadmapGateOutcome, ...]:
    """Run every supplied stage gate over its accumulated artifact context."""
    envelope_artifacts: dict[str, Any] = {}
    outcomes: list[RoadmapGateOutcome] = []
    for stage, artifact in zip(stages, artifacts, strict=True):
        envelope_artifacts[stage.artifact_key] = artifact
        outcomes.append(
            RoadmapGateOutcome(
                stage=stage,
                violations=tuple(
                    stage.gates(
                        ArtifactEnvelope(
                            predecessor=None,
                            carried_decisions=carried_decisions,
                            **envelope_artifacts,
                        )
                    )
                ),
            )
        )
    return tuple(outcomes)
