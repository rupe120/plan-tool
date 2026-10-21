"""Tests for presentation-only bound roadmap comparison rendering."""

from __future__ import annotations

import hashlib
from types import MappingProxyType

from plan_tool.roadmap_artifacts import (
    ComponentsArtifact,
    ConstraintsArtifact,
    DomainArtifact,
    EntityRow,
    FieldRow,
    FieldType,
    PatternRow,
    PlansArtifact,
)
from plan_tool.roadmap_compare import (
    ComparisonProseAmendment,
    ComparisonProseAmendmentEvidence,
    build_roadmap_comparison,
)
from plan_tool.roadmap_compare_render import (
    comparison_json_payload,
    render_comparison_json,
    render_patch_comparison,
    render_terminal_comparison,
)
from plan_tool.roadmap_compare_run import (
    RoadmapComparisonRun,
    RoadmapComparisonSnapshot,
    RoadmapGitPatch,
)
from plan_tool.roadmap_diff import build_roadmap_diff
from plan_tool.roadmap_versions import VERSION_ARTIFACT_INVENTORY


def _artifacts(*, entities: tuple[EntityRow, ...] = (), patterns: tuple[PatternRow, ...] = ()):
    return {
        "domain": DomainArtifact(entities, (), (), (), "# Domain\n"),
        "constraints": ConstraintsArtifact((), (), (), "# Constraints\n"),
        "components": ComponentsArtifact(patterns, (), (), (), "# Components\n"),
        "plans": PlansArtifact((), (), (), (), "# Plans\n"),
    }


def _snapshot(kind: str, artifacts: dict[str, object], marker: str) -> RoadmapComparisonSnapshot:
    keys = tuple(item.artifact_key for item in VERSION_ARTIFACT_INVENTORY)
    content = tuple(f"{marker}-{key}".encode() for key in keys)
    return RoadmapComparisonSnapshot(
        kind=kind, version_id=None if kind == "working" else f"{marker}-version",
        brief_digest=None if kind == "working" else f"{marker}-brief", record=None,
        brief_bytes=None, artifact_keys=keys, artifact_bytes=content,
        artifact_digests=tuple(hashlib.sha256(value).hexdigest() for value in content),
        parsed_artifacts=MappingProxyType(artifacts),
    )


def _run(
    before: dict[str, object], after: dict[str, object], *, patches: dict[str, str] | None = None
) -> RoadmapComparisonRun:
    base = _snapshot("root", before, "base")
    target = _snapshot("working", after, "target")
    from plan_tool.roadmap import STAGES

    diff = build_roadmap_diff(
        predecessor_artifacts=before, candidate_artifacts=after,
        predecessor_bytes=base.artifact_bytes, candidate_artifacts_bytes=target.artifact_bytes,
        stages=STAGES,
    )
    patches = patches or {key: "" for key in before}
    comparison = build_roadmap_comparison(typed_diff=diff, raw_patches=patches)
    patch_records = tuple(
        RoadmapGitPatch(key, 1 if patches[key] else 0, patches[key])
        for key in (item.artifact_key for item in VERSION_ARTIFACT_INVENTORY)
    )
    return RoadmapComparisonRun(base, target, patch_records, comparison)


def test_terminal_cards_preserve_base_then_target_comparison_order() -> None:
    run = _run(
        _artifacts(entities=(EntityRow("removed", "Zed", ()), EntityRow("changed", "Old", ()))),
        _artifacts(entities=(EntityRow("changed", "New", ()), EntityRow("added", "Able", ()))),
    )

    text = render_terminal_comparison(run)

    assert text.index("removed") < text.index("changed") < text.index("added")


def test_terminal_card_uses_display_label_and_complete_endpoints() -> None:
    run = _run(_artifacts(entities=(EntityRow("order", "Order", ()),)),
               _artifacts(entities=(EntityRow("order", "Purchase", ()),)))

    card = comparison_json_payload(run)["cards"][0]
    terminal = render_terminal_comparison(run)

    assert card["label"] == "Purchase"
    assert card["before"]["name"] == "Order"
    assert card["after"]["name"] == "Purchase"
    assert "Purchase before=" in terminal
    assert '"name": "Order"' in terminal
    assert "after=" in terminal
    assert '"name": "Purchase"' in terminal


def test_changed_card_renders_only_non_relation_field_differences() -> None:
    run = _run(
        _artifacts(entities=(EntityRow("order", "Order", (FieldRow("customer", FieldType.REFERENCE, "a"),)),)),
        _artifacts(entities=(EntityRow("order", "Purchase", (FieldRow("customer", FieldType.REFERENCE, "b"),)),)),
    )

    card = comparison_json_payload(run)["cards"][0]

    assert [field["name"] for field in card["changed_fields"]] == ["name"]
    assert 'fields=[{"name":"name"' in render_terminal_comparison(run)


def test_relation_occurrences_render_separately_without_deduplication() -> None:
    before = _artifacts(entities=(EntityRow(
        "order", "Order", (
            FieldRow("customer", FieldType.REFERENCE, "customer"),
            FieldRow("billing", FieldType.REFERENCE, "customer"),
        ),
    ),))
    after = _artifacts(entities=(EntityRow(
        "order", "Order", (
            FieldRow("customer", FieldType.REFERENCE, "account"),
            FieldRow("billing", FieldType.REFERENCE, "account"),
        ),
    ),))

    relations = comparison_json_payload(_run(before, after))["relations"]

    assert [(item["change_kind"], item["endpoint_id"]) for item in relations] == [
        ("added", "account"), ("added", "account"),
        ("removed", "customer"), ("removed", "customer"),
    ]


def test_unmapped_raw_text_renders_without_an_invented_card() -> None:
    payload = comparison_json_payload(_run(_artifacts(), _artifacts()))

    assert payload["cards"] == []
    assert [item["artifact_key"] for item in payload["unmapped_raw_evidence"]] == [
        "domain", "constraints", "components", "plans"
    ]


def test_mixed_typed_and_raw_text_preserves_the_complete_patch() -> None:
    patches = {"domain": "- Order\n+ Purchase\n+ comment\n", "constraints": "", "components": "", "plans": ""}
    run = _run(
        _artifacts(entities=(EntityRow("order", "Order", ()),)),
        _artifacts(entities=(EntityRow("order", "Purchase", ()),)),
        patches=patches,
    )

    assert comparison_json_payload(run)["cards"][0]["stable_id"] == "order"
    assert render_patch_comparison(run) == patches["domain"]


def test_json_and_cards_render_bound_row_linked_prose_without_changing_patch() -> None:
    run = _run(_artifacts(), _artifacts())
    comparison = run.comparison.model_copy(update={
        "prose_amendment_evidence": ComparisonProseAmendmentEvidence(
            outcome="bound",
            amendments=(ComparisonProseAmendment(
                artifact_key="constraints", row_id="boundary", fragment="Keep it private."
            ),),
        ),
    })
    run = RoadmapComparisonRun(run.base, run.target, run.patches, comparison)

    payload = comparison_json_payload(run)

    assert payload["row_linked_prose_amendments"] == {
        "outcome": "bound",
        "items": [{
            "artifact_key": "constraints", "row_id": "boundary", "fragment": "Keep it private."
        }],
    }
    assert "Row-linked prose amendments: bound" in render_terminal_comparison(run)
    assert render_patch_comparison(run) == ""


def test_patch_render_preserves_complete_git_output_in_inventory_order() -> None:
    patches = {"domain": "domain\n", "constraints": "constraints\n", "components": "components\n", "plans": "plans\n"}
    run = _run(_artifacts(), _artifacts(), patches=patches)

    assert render_patch_comparison(run) == "domain\nconstraints\ncomponents\nplans\n"


def test_terminal_and_json_identify_each_artifact_and_keep_working_identity_absent() -> None:
    run = _run(_artifacts(), _artifacts(), patches={"domain": "diff\n", "constraints": "", "components": "", "plans": ""})

    terminal = render_terminal_comparison(run)
    payload = comparison_json_payload(run)

    assert "domain: differing" in terminal
    assert "constraints: identical" in terminal
    assert "Base: kind=root version_id=base-version brief_digest=base-brief" in terminal
    assert "Target: kind=working version_id=None brief_digest=None" in terminal
    assert "Base counts: artifacts=4 concepts=0" in terminal
    assert "base " + run.base.artifact_digests[0] in terminal
    assert payload["target"]["version_id"] is None
    assert [item["evidence_outcome"] for item in payload["artifacts"]] == ["differing", "identical", "identical", "identical"]


def test_json_is_deterministic_and_supplies_pattern_row_kind_context() -> None:
    pattern = PatternRow("pattern", "Use ports and adapters", ())
    first = _run(_artifacts(), _artifacts(patterns=(pattern,)))
    second = _run(_artifacts(), _artifacts(patterns=(pattern,)))

    assert render_comparison_json(first) == render_comparison_json(second)
    assert comparison_json_payload(first)["cards"][0]["label"] == (
        "system pattern: Use ports and adapters"
    )
    assert "system pattern: Use ports and adapters" in render_terminal_comparison(first)


def test_comparing_a_stack_less_version_with_one_that_records_a_stack_renders_a_labeled_card() -> None:
    """The row diff for an introduced stack must also render: a card needs a
    display label for every row type the diff can emit."""
    from dataclasses import replace

    from plan_tool.roadmap_artifacts import StackRow

    before = _artifacts()
    after = _artifacts()
    after["constraints"] = replace(
        after["constraints"], stack=(StackRow("stack-platform", "platform", choice="managed"),)
    )

    run = _run(before, after)

    card = comparison_json_payload(run)["cards"][0]
    assert card["label"] == "stack platform: managed"
    assert "stack platform: managed" in render_terminal_comparison(run)
