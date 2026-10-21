from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from plan_tool import concept_tree as ct


def _node(title: str, parents: list[str] | None = None, **values: object) -> ct.ConceptNode:
    parent_path = parents or []
    defaults: dict[str, object] = {
        "id": ct.concept_id(title, parent_path),
        "title": title,
        "parent_path": parent_path,
    }
    defaults.update(values)
    return ct.ConceptNode(**defaults)  # type: ignore[arg-type]


def _tree(slug: str = "sample", fingerprint: str = "fingerprint") -> ct.ConceptTree:
    return ct.ConceptTree(
        plan_slug=slug,
        plan_fingerprint=fingerprint,
        concepts=[
            _node("Root", order=1, source="overview", source_metadata={"line": "4"}),
            _node(
                "Child", ["Root"], order=2, decision="Keep it",
                rationale="Required", review_state="approved",
            ),
        ],
    )


def _flat_node(title: str, **values: object) -> ct.ConceptNode:
    defaults: dict[str, object] = {
        "id": ct.concept_id(title, []),
        "title": title,
        "bucket": "Section",
        "decision": "defer",
    }
    defaults.update(values)
    return ct.ConceptNode(**defaults)  # type: ignore[arg-type]


def _flat_tree(slug: str = "sample", fingerprint: str = "fingerprint") -> ct.ConceptTree:
    return ct.ConceptTree(
        plan_slug=slug,
        plan_fingerprint=fingerprint,
        concepts=[_flat_node("Deferred concept", rationale="later")],
        record_kind=ct.RECORD_KIND_DECISION,
    )


def test_concepts_path_is_inside_plan_detail_bundle(tmp_path: Path) -> None:
    assert ct.concepts_path(tmp_path / "12-sample.md") == (
        tmp_path / "plan-details" / "sample" / "concepts.json"
    )


def test_concept_id_is_stable_and_changes_only_with_position() -> None:
    identifier = ct.concept_id("Child", ["Root"])
    assert identifier == ct.concept_id("Child", ["Root"])
    assert len(identifier) == 64
    assert identifier != ct.concept_id("Other", ["Root"])
    assert identifier != ct.concept_id("Child", ["Other"])
    mutable = _node("Child", ["Root"], order=99, review_state="rejected")
    assert mutable.id == identifier
    assert ct.concept_id(" Child ", ["Root"]) == identifier


def test_save_and_load_round_trip_exact_record(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    tree = _tree()
    path = ct.save_concepts(plan, tree)
    assert path.is_file()
    assert ct.load_concepts(plan, "fingerprint") == tree


def test_second_save_replaces_single_sidecar(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    ct.save_concepts(plan, _tree())
    changed = replace(_tree(), concepts=[_node("Replacement")])
    ct.save_concepts(plan, changed)
    assert ct.load_concepts(plan, "fingerprint") == changed
    assert [path.name for path in ct.concepts_path(plan).parent.iterdir()] == ["concepts.json"]


def test_missing_sidecar_returns_absent(tmp_path: Path) -> None:
    assert ct.load_concepts(tmp_path / "1-sample.md", "fingerprint") is None


def test_non_utf8_sidecar_is_invalid(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    path = ct.concepts_path(plan)
    path.parent.mkdir(parents=True)
    path.write_bytes(b"\xff")

    with pytest.raises(ct.InvalidConceptTreeError, match="cannot read"):
        ct.load_concepts(plan, "fingerprint")


@pytest.mark.parametrize("content", ["{", "[]", "true"])
def test_malformed_or_non_object_json_is_invalid(tmp_path: Path, content: str) -> None:
    plan = tmp_path / "1-sample.md"
    path = ct.concepts_path(plan)
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.load_concepts(plan, "fingerprint")


def test_plan_fingerprint_mismatch_is_stale(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    ct.save_concepts(plan, _tree())
    with pytest.raises(ct.StaleConceptTreeError):
        ct.load_concepts(plan, "different")


def test_tampering_duplicates_and_invalid_parent_are_rejected(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    path = ct.save_concepts(plan, _tree())
    data = json.loads(path.read_text())
    data["concepts"][0]["id"] = "0" * 64
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.load_concepts(plan, "fingerprint")
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, replace(_tree(), concepts=[_node("Root"), _node("Root")]))
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, replace(_tree(), concepts=[_node("Child", ["Missing"])]))


class TestParseEmittedConcepts:
    """The model-response parse path (``emit_concept_tree``'s Claude reply)
    shares its JSON-envelope handling with the on-disk ``load_concepts``
    path and must reject a duplicate key the same way, not just decode
    against the last-seen value."""

    _EVIDENCE = "The system caches results in memory for fast lookup."

    def test_valid_reply_parses(self) -> None:
        reply = (
            '{"concepts": [{"title": "Caching", "suggested_state": '
            '"candidate", "evidence_rationale": "caches results in memory", '
            '"children": []}]}'
        )
        assert ct._parse_emitted_concepts(reply, self._EVIDENCE) == [
            ("Caching", [], "caches results in memory")
        ]

    def test_duplicate_top_level_key_is_rejected(self) -> None:
        reply = '{"concepts": [], "concepts": []}'
        assert ct._parse_emitted_concepts(reply, self._EVIDENCE) == []

    def test_duplicate_key_in_a_nested_concept_is_rejected(self) -> None:
        reply = (
            '{"concepts": [{"title": "Caching", "suggested_state": '
            '"candidate", "evidence_rationale": "caches results in memory", '
            '"children": [], "title": "Retitled"}]}'
        )
        assert ct._parse_emitted_concepts(reply, self._EVIDENCE) == []


def test_slug_schema_types_and_review_state_are_strict(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, replace(_tree(), plan_slug="other"))
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, replace(_tree(), schema_version=True))
    bad = replace(_tree(), concepts=[_node("Root", review_state="maybe")])
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, bad)


def test_flat_decision_record_round_trips(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    tree = _flat_tree()
    ct.save_concepts(plan, tree)
    assert ct.load_concepts(plan, "fingerprint") == tree


def test_flat_record_loads_after_unrelated_edit(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    tree = _flat_tree()
    ct.save_concepts(plan, tree)
    # A decision is confirmed after further plan edits, so a changed fingerprint
    # must not make the flat record stale.
    assert ct.load_concepts(plan, "different-fingerprint") == tree


def test_legacy_full_tree_still_stale_on_fingerprint_mismatch(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    ct.save_concepts(plan, _tree())
    assert _tree().record_kind == ct.RECORD_KIND_FULL_TREE
    with pytest.raises(ct.StaleConceptTreeError):
        ct.load_concepts(plan, "different")


def test_legacy_record_without_new_keys_still_loads(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    path = ct.save_concepts(plan, _tree())
    data = json.loads(path.read_text())
    del data["record_kind"]
    for node in data["concepts"]:
        del node["bucket"]
    path.write_text(json.dumps(data), encoding="utf-8")
    loaded = ct.load_concepts(plan, "fingerprint")
    assert loaded == _tree()
    assert loaded.record_kind == ct.RECORD_KIND_FULL_TREE


def test_flat_record_requires_non_empty_bucket(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    bad = replace(_flat_tree(), concepts=[_flat_node("Deferred", bucket="")])
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, bad)


def test_flat_record_rejects_hierarchy_and_bad_decision(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(
            plan,
            replace(
                _flat_tree(),
                concepts=[_flat_node("Root"), _flat_node("Child", parent_path=["Root"])],
            ),
        )
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(
            plan, replace(_flat_tree(), concepts=[_flat_node("Deferred", decision="keep")])
        )


def test_unknown_record_kind_is_invalid(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.save_concepts(plan, replace(_tree(), record_kind="mystery"))


def test_unknown_extra_key_still_rejected(tmp_path: Path) -> None:
    plan = tmp_path / "1-sample.md"
    path = ct.save_concepts(plan, _tree())
    data = json.loads(path.read_text())
    data["surprise"] = True
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ct.InvalidConceptTreeError):
        ct.load_concepts(plan, "fingerprint")


def test_failed_atomic_publish_preserves_previous_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan = tmp_path / "1-sample.md"
    original = _tree()
    ct.save_concepts(plan, original)
    monkeypatch.setattr(ct.os, "replace", lambda *_: (_ for _ in ()).throw(OSError("fail")))
    with pytest.raises(OSError):
        ct.save_concepts(plan, replace(original, concepts=[_node("New")]))
    assert ct.load_concepts(plan, "fingerprint") == original
    assert [path.name for path in ct.concepts_path(plan).parent.iterdir()] == ["concepts.json"]
