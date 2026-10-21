"""Tests for the leaf audit-shape registry."""

from __future__ import annotations

import ast
import importlib.util
import sys
import types
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from plan_tool.audit_shapes import (
    AUDIT_SHAPES,
    AuditShapeAdvisory,
    AuditShapeFindingEvidence,
    AuditShape,
    audit_shape_by_id,
    evaluate_arm_clustering,
    is_advisory_emitter_eligible,
)


_ROOT = Path(__file__).resolve().parents[1]
_MODULE_PATH = _ROOT / "plan_tool" / "audit_shapes.py"


def test_audit_shapes_are_the_canonical_ordered_records() -> None:
    assert AUDIT_SHAPES == (
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


def test_audit_shape_records_and_registry_are_immutable() -> None:
    with pytest.raises(FrozenInstanceError):
        AUDIT_SHAPES[0].classification = "judgment_only"  # type: ignore[misc]
    with pytest.raises(TypeError):
        AUDIT_SHAPES[0] = AUDIT_SHAPES[1]  # type: ignore[index]


def test_audit_shape_by_id_returns_the_registered_record() -> None:
    assert audit_shape_by_id("arm-clustering") is AUDIT_SHAPES[0]


@pytest.mark.parametrize("shape_id", ["unknown", "", None, 7, object()])
def test_audit_shape_by_id_returns_no_match_for_unknown_or_missing_id(
    shape_id: object,
) -> None:
    assert audit_shape_by_id(shape_id) is None


def test_only_arm_clustering_is_advisory_emitter_eligible() -> None:
    assert is_advisory_emitter_eligible("arm-clustering")


@pytest.mark.parametrize(
    "shape_id",
    [
        "check-saturation",
        "measurement-instrument-adequacy",
        "self-seeded-finding",
        "remedy-proportionality",
        "premise-conditioned-design",
        "unknown",
        "",
        None,
        7,
    ],
)
def test_judgment_only_and_unknown_shapes_are_not_eligible(shape_id: object) -> None:
    assert not is_advisory_emitter_eligible(shape_id)


def test_leaf_has_no_first_party_runtime_import() -> None:
    tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
    first_party_imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            first_party_imports.extend(
                alias.name
                for alias in node.names
                if alias.name == "plan_tool" or alias.name.startswith("plan_tool.")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                first_party_imports.append(
                    f"{'.' * node.level}{node.module or ''}"
                )
            elif node.module == "plan_tool" or (
                node.module is not None and node.module.startswith("plan_tool.")
            ):
                first_party_imports.append(node.module)
    assert first_party_imports == []


def test_leaf_imports_without_other_plan_tool_modules(monkeypatch) -> None:
    package = types.ModuleType("plan_tool")
    package.__path__ = [str(_MODULE_PATH.parent)]
    module_name = "plan_tool._audit_shapes_leaf_test"
    existing_first_party_modules = {
        name for name in sys.modules if name == "plan_tool" or name.startswith("plan_tool.")
    }
    monkeypatch.setitem(sys.modules, "plan_tool", package)
    spec = importlib.util.spec_from_file_location(module_name, _MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    added_first_party_modules = {
        name
        for name in sys.modules
        if name == "plan_tool" or name.startswith("plan_tool.")
    } - existing_first_party_modules
    assert added_first_party_modules <= {module_name}


def test_arm_clustering_evaluates_a_single_contiguous_majority_arm() -> None:
    advisory = evaluate_arm_clustering(
        declared_step_ids=(1, 2, 3, 4, 5),
        material_finding_ids=("f-1", "f-2", "f-3", "f-4"),
        consensus_targets={"f-1": 1, "f-2": 2, "f-3": 3, "f-4": 3},
        source_plan_fingerprint="snapshot-sha",
        material_finding_evidence=(
            AuditShapeFindingEvidence("f-1", "one", "plan-correctness"),
            AuditShapeFindingEvidence("f-2", "two", "plan-completeness"),
            AuditShapeFindingEvidence("f-3", "three", "plan-completeness"),
            AuditShapeFindingEvidence("f-4", "four", "plan-correctness"),
        ),
    )

    assert advisory == AuditShapeAdvisory(
        shape_id="arm-clustering",
        source_plan_fingerprint="snapshot-sha",
        arm_step_ids=(1, 2, 3),
        material_finding_ids=("f-1", "f-2", "f-3", "f-4"),
        arm_finding_ids=("f-1", "f-2", "f-3", "f-4"),
        material_finding_evidence=(
            AuditShapeFindingEvidence("f-1", "one", "plan-correctness"),
            AuditShapeFindingEvidence("f-2", "two", "plan-completeness"),
            AuditShapeFindingEvidence("f-3", "three", "plan-completeness"),
            AuditShapeFindingEvidence("f-4", "four", "plan-correctness"),
        ),
        material_finding_count=4,
        arm_finding_count=4,
        committed_step_count=5,
    )


@pytest.mark.parametrize(
    ("shape_id", "step_ids", "finding_ids", "targets"),
    [
        ("check-saturation", (1, 2, 3, 4, 5), ("a", "b", "c"), {"a": 1, "b": 2, "c": 3}),
        ("arm-clustering", (1, 2, 3, 4, 5), ("a", "b"), {"a": 1, "b": 2}),
        ("arm-clustering", (1, 2, 3, 4, 5), ("a", "b", "c", "d"), {"a": 1, "b": 2, "c": 4, "d": 5}),
        ("arm-clustering", (1, 2, 3), ("a", "b", "c"), {"a": 1, "b": 2, "c": 3}),
    ],
)
def test_arm_clustering_fails_closed_for_ineligible_or_ambiguous_evidence(
    shape_id, step_ids, finding_ids, targets,
) -> None:
    assert evaluate_arm_clustering(
        shape_id=shape_id,
        declared_step_ids=step_ids,
        material_finding_ids=finding_ids,
        consensus_targets=targets,
    ) is None
