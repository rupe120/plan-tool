from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from plan_tool import concept_tree as ct
from plan_tool import shell


def _node(title: str, parents: list[str] | None = None, **values: object) -> ct.ConceptNode:
    parent_path = parents or []
    defaults: dict[str, object] = {
        "id": ct.concept_id(title, parent_path),
        "title": title,
        "parent_path": parent_path,
    }
    defaults.update(values)
    return ct.ConceptNode(**defaults)  # type: ignore[arg-type]


def _tree() -> ct.ConceptTree:
    return ct.ConceptTree(
        plan_slug="sample",
        plan_fingerprint="fingerprint",
        concepts=[_node("Seed", source="deterministic evidence")],
    )


def _decision_tree() -> ct.ConceptTree:
    return ct.ConceptTree(
        plan_slug="sample",
        plan_fingerprint="fingerprint",
        concepts=[
            _node(
                "Seed",
                source="deterministic evidence",
                decision="defer",
                review_state="approved",
                bucket="Seed",
            )
        ],
        record_kind=ct.RECORD_KIND_DECISION,
    )


def _response(*concepts: dict[str, object]) -> str:
    return json.dumps({"concepts": list(concepts)})


def _candidate(title: str, excerpt: str, **values: object) -> dict[str, object]:
    result: dict[str, object] = {
        "title": title,
        "suggested_state": "include",
        "evidence_rationale": excerpt,
    }
    result.update(values)
    return result


def test_render_concept_emit_prompt_includes_supplied_evidence() -> None:
    prompt = ct.render_concept_emit_prompt("Exact evidence", plan_context="A plan")
    assert "Exact evidence" in prompt
    assert '"concepts"' in prompt and '"evidence_rationale"' in prompt
    assert str(ct.CONCEPT_EMIT_MAX_DEPTH) in prompt
    assert str(ct.CONCEPT_EMIT_MAX_BREADTH) in prompt


def test_emit_enriches_deterministic_tree() -> None:
    evidence = "Parent support. Child support."
    stdout = _response(
        _candidate(
            "Parent", "Parent support",
            children=[_candidate("Child", "Child support")],
        )
    )
    result = ct.emit_concept_tree(_tree(), evidence, invoker=lambda _: stdout)
    assert result is not None
    assert [node.title for node in result.concepts] == ["Seed", "Parent", "Child"]
    assert result.concepts[2].parent_path == ["Parent"]


def test_emit_preserves_existing_reviewed_decisions() -> None:
    tree = _tree()
    tree.concepts[0].review_state = "approved"
    tree.concepts[0].decision = "include"
    tree.concepts[0].rationale = "reviewed"
    tree.concepts[0].source_metadata = {"owner": "operator"}
    original = copy.deepcopy(tree.concepts[0])
    stdout = _response(
        _candidate("Seed", "different source"),
        _candidate("Added", "new support"),
    )
    result = ct.emit_concept_tree(
        tree, "different source and new support", invoker=lambda _: stdout
    )
    assert result is not None
    assert result.concepts[0] == original


def test_emit_rejects_flat_decision_record_without_calling_model() -> None:
    tree = _decision_tree()
    before = copy.deepcopy(tree)
    calls: list[str] = []

    result = ct.emit_concept_tree(
        tree,
        "new support",
        invoker=lambda prompt: calls.append(prompt) or _response(_candidate("Added", "new support")),
    )

    assert result is None
    assert calls == []
    assert tree == before


def test_emit_fails_closed_on_full_tree_rederivation_conflict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from plan_tool import concept_bootstrap

    tree = _tree()
    before = copy.deepcopy(tree)
    conflict = concept_bootstrap.ConceptConflict(
        concept_id=tree.concepts[0].id,
        source_key="seed",
        field="source",
        baseline="baseline",
        current="current",
        derived="derived",
    )
    monkeypatch.setattr(
        concept_bootstrap,
        "rederive_concepts",
        lambda _current, _fresh: concept_bootstrap.RederivationResult(
            candidate=_tree(), conflicts=[conflict]
        ),
    )

    result = ct.emit_concept_tree(
        tree,
        "new support",
        invoker=lambda _: _response(_candidate("Added", "new support")),
    )

    assert result is None
    assert tree == before


def test_emit_does_not_trust_model_ids() -> None:
    raw = _candidate("Added", "supported", id="model-chosen")
    result = ct.emit_concept_tree(_tree(), "supported", invoker=lambda _: _response(raw))
    assert result is not None
    assert result.concepts[-1].id == ct.concept_id("Added", [])


def test_emit_additions_are_unsigned() -> None:
    result = ct.emit_concept_tree(
        _tree(), "supported",
        invoker=lambda _: _response(_candidate("Added", "supported")),
    )
    assert result is not None
    added = result.concepts[-1]
    assert added.review_state == "unreviewed"
    assert added.decision == added.rationale == ""


def test_emit_maps_unknown_state_to_safe_visible_default() -> None:
    raw = _candidate("Added", "supported", suggested_state="surprise")
    result = ct.emit_concept_tree(_tree(), "supported", invoker=lambda _: _response(raw))
    assert result is not None
    assert result.concepts[-1].review_state == "unreviewed"


@pytest.mark.parametrize(
    "raw,evidence",
    [
        ({"title": "Unsupported", "suggested_state": "include"}, "evidence"),
        (_candidate("Unsupported", "invented claim"), "different evidence"),
    ],
)
def test_emit_rejects_unsupported_claim_without_evidence(
    raw: dict[str, object], evidence: str
) -> None:
    assert ct.emit_concept_tree(_tree(), evidence, invoker=lambda _: _response(raw)) is None


def test_emit_enforces_depth_and_breadth_limits() -> None:
    breadth = [
        _candidate(f"Concept {index}", f"support {index}")
        for index in range(ct.CONCEPT_EMIT_MAX_BREADTH + 1)
    ]
    evidence = " ".join(f"support {index}" for index in range(len(breadth)))
    assert ct.emit_concept_tree(_tree(), evidence, invoker=lambda _: _response(*breadth)) is None

    nested = _candidate("Level 1", "one")
    cursor = nested
    for depth in range(2, ct.CONCEPT_EMIT_MAX_DEPTH + 2):
        child = _candidate(f"Level {depth}", str(depth))
        cursor["children"] = [child]
        cursor = child
    assert ct.emit_concept_tree(
        _tree(), "one 2 3 4 5", invoker=lambda _: _response(nested)
    ) is None


@pytest.mark.parametrize(
    "stdout",
    ["", "not json", "{", "[]", '{"concepts":"wrong"}', '{"concepts":[{"title":1}]}'],
)
def test_emit_returns_none_on_empty_or_invalid_output(stdout: str) -> None:
    assert ct.emit_concept_tree(_tree(), "evidence", invoker=lambda _: stdout) is None


def test_emit_failure_leaves_input_unchanged() -> None:
    tree = _tree()
    before = copy.deepcopy(tree)
    assert ct.emit_concept_tree(tree, "evidence", invoker=lambda _: "bad") is None
    assert tree == before


def test_emit_does_not_persist(tmp_path: Path) -> None:
    plan_path = tmp_path / "1-sample.md"
    result = ct.emit_concept_tree(
        _tree(), "supported",
        invoker=lambda _: _response(_candidate("Added", "supported")),
    )
    assert result is not None
    assert not ct.concepts_path(plan_path).exists()


def test_emit_uses_injected_invoker_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(shell, "claude_invoke", lambda *_a, **_k: pytest.fail("shell call"))
    result = ct.emit_concept_tree(
        _tree(), "supported",
        invoker=lambda prompt: calls.append(prompt) or _response(_candidate("Added", "supported")),
    )
    assert result is not None
    assert len(calls) == 1 and "supported" in calls[0]


def test_default_invoker_uses_real_backend_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell.shutil, "which", lambda _binary: "/usr/bin/backend")
    assert ct.emit_concept_tree(_tree(), "evidence") is None


def test_shell_concept_invoker_returns_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shell, "claude_invoke", lambda *_a, **_k: (9, "stdout"))
    assert shell.shell_concept_invoker("prompt") == "stdout"


def test_same_seed_and_response_are_deterministic() -> None:
    stdout = _response(_candidate("Added", "supported"))
    first = ct.emit_concept_tree(_tree(), "supported", invoker=lambda _: stdout)
    second = ct.emit_concept_tree(_tree(), "supported", invoker=lambda _: stdout)
    assert first == second
