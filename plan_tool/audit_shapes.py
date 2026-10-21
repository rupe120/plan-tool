"""Canonical audit-shape classifications and advisory eligibility.

This module is deliberately a leaf: audit flow and persistence consumers use
these immutable records, but the registry does not depend on them.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


@dataclass(frozen=True)
class AuditShape:
    """A stable audit shape and its advisory-emitter classification."""

    id: str
    tell: str
    classification: str


AUDIT_SHAPES: tuple[AuditShape, ...] = (
    AuditShape(
        id="arm-clustering",
        tell=(
            "Material conceptual findings form a strict-majority, contiguous "
            "proper arm of committed plan steps"
        ),
        classification="checked",
    ),
    AuditShape(
        id="check-saturation",
        tell="Every part is correct but no producer delivers the intended value",
        classification="judgment_only",
    ),
    AuditShape(
        id="measurement-instrument-adequacy",
        tell="A measurement instrument cannot see the data on which a decision relies",
        classification="judgment_only",
    ),
    AuditShape(
        id="self-seeded-finding",
        tell="Findings describe the prior audit edit rather than the artifact",
        classification="judgment_only",
    ),
    AuditShape(
        id="remedy-proportionality",
        tell="The proposed remedy outgrows the defect",
        classification="judgment_only",
    ),
    AuditShape(
        id="premise-conditioned-design",
        tell=(
            "A step's design differs by the outcome of an investigation the "
            "same plan contains"
        ),
        classification="judgment_only",
    ),
)


def audit_shape_by_id(shape_id: object) -> AuditShape | None:
    """Return the registered shape for a valid ID, or ``None`` when absent."""
    if not isinstance(shape_id, str):
        return None
    return next((shape for shape in AUDIT_SHAPES if shape.id == shape_id), None)


def is_advisory_emitter_eligible(shape_id: object) -> bool:
    """Whether a registered shape may produce an advisory emitter."""
    shape = audit_shape_by_id(shape_id)
    return shape is not None and shape.classification == "checked"


@dataclass(frozen=True)
class AuditShapeFindingEvidence:
    """Minimal non-routing evidence retained for one material finding."""

    finding_id: str
    anchor: str | None
    source: str


@dataclass(frozen=True)
class AuditShapeAdvisory:
    """An immutable, non-executable audit-shape result.

    The payload intentionally contains identifiers and structured audit axes
    only. It carries neither recommendation prose nor a finding-to-step target,
    so loading it can never change normal review routing.
    """

    shape_id: str
    source_plan_fingerprint: str
    arm_step_ids: tuple[int, ...]
    material_finding_ids: tuple[str, ...]
    arm_finding_ids: tuple[str, ...]
    material_finding_evidence: tuple[AuditShapeFindingEvidence, ...]
    material_finding_count: int
    arm_finding_count: int
    committed_step_count: int


def is_well_formed_audit_shape_advisory(
    advisory: object,
    *,
    declared_step_ids: Sequence[int] | None = None,
) -> bool:
    """Validate the non-routing invariants of a stored arm advisory.

    Saved sidecars are user-editable input, so their optional advisory must
    fail closed when its own evidence is contradictory.  When a caller has
    the current committed-step sequence, validate the claimed proper,
    contiguous arm against it too.  This remains a leaf: it deliberately
    knows nothing about persistence or recommendation routing.
    """
    if (
        not isinstance(advisory, AuditShapeAdvisory)
        or not is_advisory_emitter_eligible(advisory.shape_id)
        or not isinstance(advisory.source_plan_fingerprint, str)
        or not advisory.source_plan_fingerprint
        or not isinstance(advisory.arm_step_ids, tuple)
        or not isinstance(advisory.material_finding_ids, tuple)
        or not isinstance(advisory.arm_finding_ids, tuple)
        or not isinstance(advisory.material_finding_evidence, tuple)
    ):
        return False

    arm_steps = advisory.arm_step_ids
    material_ids = advisory.material_finding_ids
    arm_ids = advisory.arm_finding_ids
    if (
        not arm_steps
        or len(set(arm_steps)) != len(arm_steps)
        or any(
            isinstance(step_id, bool) or not isinstance(step_id, int)
            for step_id in arm_steps
        )
        or len(material_ids) < 3
        or len(set(material_ids)) != len(material_ids)
        or any(not isinstance(finding_id, str) or not finding_id for finding_id in material_ids)
        or len(set(arm_ids)) != len(arm_ids)
        or any(not isinstance(finding_id, str) or not finding_id for finding_id in arm_ids)
        or not set(arm_ids).issubset(material_ids)
        or len(arm_ids) * 2 <= len(material_ids)
        or any(
            isinstance(count, bool) or not isinstance(count, int) or count < 0
            for count in (
                advisory.material_finding_count,
                advisory.arm_finding_count,
                advisory.committed_step_count,
            )
        )
        or advisory.material_finding_count != len(material_ids)
        or advisory.arm_finding_count != len(arm_ids)
        or len(arm_steps) >= advisory.committed_step_count
        or len(arm_steps) * 2 <= advisory.committed_step_count
        or len(advisory.material_finding_evidence) != len(material_ids)
        or any(
            not isinstance(item, AuditShapeFindingEvidence)
            or not isinstance(item.finding_id, str)
            or not item.finding_id
            or not isinstance(item.anchor, (str, type(None)))
            or not isinstance(item.source, str)
            for item in advisory.material_finding_evidence
        )
        or tuple(item.finding_id for item in advisory.material_finding_evidence)
        != material_ids
    ):
        return False

    if declared_step_ids is None:
        return True
    declared = tuple(declared_step_ids)
    if (
        len(declared) != advisory.committed_step_count
        or len(set(declared)) != len(declared)
        or any(
            isinstance(step_id, bool) or not isinstance(step_id, int)
            for step_id in declared
        )
    ):
        return False
    positions = {step_id: index for index, step_id in enumerate(declared)}
    try:
        arm_positions = tuple(positions[step_id] for step_id in arm_steps)
    except KeyError:
        return False
    return arm_positions == tuple(
        range(arm_positions[0], arm_positions[0] + len(arm_positions))
    )


def evaluate_arm_clustering(
    *,
    declared_step_ids: Sequence[int],
    material_finding_ids: Sequence[str],
    consensus_targets: Mapping[str, int],
    source_plan_fingerprint: str = "",
    material_finding_evidence: Sequence[AuditShapeFindingEvidence] = (),
    shape_id: str = "arm-clustering",
) -> AuditShapeAdvisory | None:
    """Return one fail-closed contiguous-majority arm advisory, if warranted.

    Inputs are already-validated primitive audit evidence. ``declared_step_ids``
    is the declared ordered set of committed steps; every material finding
    needs exactly one already-validated consensus target in that order. A
    candidate arm must be a gap-free proper run that covers strict majorities
    of both committed steps
    and material findings. This deliberately keeps all plan/model validation
    and all persistence concerns out of the registry leaf.
    """
    if not is_advisory_emitter_eligible(shape_id):
        return None
    if (
        not isinstance(source_plan_fingerprint, str)
        or not isinstance(shape_id, str)
        or len(material_finding_ids) < 3
    ):
        return None

    ordered_steps = tuple(declared_step_ids)
    material_ids = tuple(material_finding_ids)
    if (
        not ordered_steps
        or len(set(ordered_steps)) != len(ordered_steps)
        or any(isinstance(step_id, bool) or not isinstance(step_id, int)
               for step_id in ordered_steps)
        or len(set(material_ids)) != len(material_ids)
        or any(not isinstance(finding_id, str) or not finding_id
               for finding_id in material_ids)
    ):
        return None

    step_positions = {step_id: position for position, step_id in enumerate(ordered_steps)}
    targets: dict[str, int] = {}
    for finding_id in material_ids:
        target = consensus_targets.get(finding_id)
        if isinstance(target, bool) or not isinstance(target, int):
            return None
        if target not in step_positions:
            return None
        targets[finding_id] = target

    evidence_by_id = {item.finding_id: item for item in material_finding_evidence}
    if material_finding_evidence and (
        len(evidence_by_id) != len(material_finding_evidence)
        or set(evidence_by_id) != set(material_ids)
        or any(
            not isinstance(item.finding_id, str)
            or not isinstance(item.anchor, (str, type(None)))
            or not isinstance(item.source, str)
            for item in material_finding_evidence
        )
    ):
        return None
    evidence = tuple(
        evidence_by_id.get(
            finding_id,
            AuditShapeFindingEvidence(finding_id, None, ""),
        )
        for finding_id in material_ids
    )

    target_positions = sorted({step_positions[target] for target in targets.values()})
    runs: list[tuple[int, ...]] = []
    current: list[int] = []
    for position in target_positions:
        if current and position != current[-1] + 1:
            runs.append(tuple(current))
            current = []
        current.append(position)
    if current:
        runs.append(tuple(current))
    if not runs:
        return None

    run_evidence: list[tuple[tuple[int, ...], tuple[str, ...]]] = []
    for positions in runs:
        arm_steps = tuple(ordered_steps[position] for position in positions)
        arm_step_set = set(arm_steps)
        arm_findings = tuple(
            finding_id for finding_id in material_ids
            if targets[finding_id] in arm_step_set
        )
        run_evidence.append((arm_steps, arm_findings))

    largest_support = max(len(findings) for _, findings in run_evidence)
    if sum(len(findings) == largest_support for _, findings in run_evidence) != 1:
        return None
    arm_steps, arm_findings = next(
        pair for pair in run_evidence if len(pair[1]) == largest_support
    )
    if (
        len(arm_steps) == len(ordered_steps)
        or len(arm_steps) * 2 <= len(ordered_steps)
        or len(arm_findings) * 2 <= len(material_ids)
    ):
        return None

    return AuditShapeAdvisory(
        shape_id=shape_id,
        source_plan_fingerprint=source_plan_fingerprint,
        arm_step_ids=arm_steps,
        material_finding_ids=material_ids,
        arm_finding_ids=arm_findings,
        material_finding_evidence=evidence,
        material_finding_count=len(material_ids),
        arm_finding_count=len(arm_findings),
        committed_step_count=len(ordered_steps),
    )
