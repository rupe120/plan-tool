"""Tests for the leaf concept-brief reading contract."""

from __future__ import annotations

import ast
import hashlib
import importlib
import json
import sys
from pathlib import Path

import pytest

from plan_tool.roadmap_source import (
    CarriedDecision,
    ConfirmedAnswer,
    RejectedAlternative,
    RoadmapSourceError,
    digest_decoded_text,
    parse_carried_decisions,
    read_brief_text,
)


SLUG = "storefront"


def _carried_decision_block(payload: dict[str, object]) -> str:
    return "# Concept\n\n## Carried decisions\n\n```json\n" + json.dumps(payload) + "\n```\n"


def test_brief_without_carried_decisions_is_compatible(tmp_path: Path) -> None:
    assert (
        parse_carried_decisions("# Concept\n", brief_path=tmp_path / "concept.md").decisions == ()
    )


@pytest.mark.parametrize(
    "brief",
    (
        "## Carried decisions extra\n",
        "## Carried decisions\n\n```json\n{}\n```\n\n## Carried decisions\n",
        "## Carried decisions\n\n{\"confirmed_answers\": [], \"decisions\": []}\n",
        "## Carried decisions\n\n```yaml\n{}\n```\n",
        "## Carried decisions\n\n~~~~json\n{}\n~~~~\n",
        "## Carried decisions\n\n````json\n{}\n````\n",
        "## Carried decisions\n\n  ```json\n{}\n  ```\n",
        "## Carried decisions\n\n```json\n{}\n",
    ),
)
def test_malformed_carried_heading_or_fence_refuses(tmp_path: Path, brief: str) -> None:
    with pytest.raises(RoadmapSourceError, match="concept\\.md"):
        parse_carried_decisions(brief, brief_path=tmp_path / "concept.md")


def test_carried_block_changes_the_recorded_brief_digest(tmp_path: Path) -> None:
    first = _carried_decision_block({"confirmed_answers": [], "decisions": []})
    second = _carried_decision_block(
        {"confirmed_answers": [{"id": "a", "answer": "Use queues", "status": "confirmed"}], "decisions": []}
    )

    assert digest_decoded_text(first) != digest_decoded_text(second)
    assert parse_carried_decisions(first, brief_path=tmp_path / "concept.md").decisions == ()
    assert len(parse_carried_decisions(second, brief_path=tmp_path / "concept.md").confirmed_answers) == 1


def test_brief_exposes_closed_carried_decisions(tmp_path: Path) -> None:
    parsed = parse_carried_decisions(
        _carried_decision_block(
            {
                "confirmed_answers": [
                    {"id": "answer-1", "answer": "Use queues", "status": "confirmed"}
                ],
                "decisions": [
                    {
                        "id": "decision-1",
                        "owner": "components",
                        "anchor": "queue",
                        "chosen_option": "Use queues",
                        "source": "answer-1",
                        "rationale": "The approved route.",
                        "rejected_alternatives": [
                            {"option": "Poll", "reason": "It lost upstream."}
                        ],
                    }
                ],
            }
        ),
        brief_path=tmp_path / "concept.md",
    )

    assert parsed.confirmed_answers == (ConfirmedAnswer(id="answer-1", answer="Use queues"),)
    assert parsed.decisions == (
        CarriedDecision(
            id="decision-1",
            owner="components",
            anchor="queue",
            chosen_option="Use queues",
            source="answer-1",
            rationale="The approved route.",
            rejected_alternatives=(RejectedAlternative(option="Poll", reason="It lost upstream."),),
        ),
    )


@pytest.mark.parametrize(
    "payload",
    (
        {"confirmed_answers": {}, "decisions": []},
        {"confirmed_answers": [], "decisions": {}},
        {"confirmed_answers": [], "decisions": [], "metadata": {}},
        {
            "confirmed_answers": [],
            "decisions": [
                {
                    "id": "d",
                    "owner": "domain",
                    "anchor": "a",
                    "chosen_option": "x",
                    "source": "missing",
                }
            ],
        },
        {"confirmed_answers": [{"id": "a", "answer": "x", "status": "pending"}], "decisions": []},
        {
            "confirmed_answers": [{"id": "a", "answer": "x", "status": "confirmed"}],
            "decisions": [
                {"id": "d", "owner": "other", "anchor": "a", "chosen_option": "x", "source": "a"}
            ],
        },
        {
            "confirmed_answers": [{"id": "a", "answer": "x", "status": "confirmed"}],
            "decisions": [
                {"id": "d", "owner": "domain", "anchor": "a", "chosen_option": "y", "source": "a"}
            ],
        },
        {
            "confirmed_answers": [{"id": "a", "answer": "x", "status": "confirmed"}],
            "decisions": [
                {"id": "d", "owner": "domain", "anchor": "a", "chosen_option": "x", "source": "a"},
                {"id": "d", "owner": "domain", "anchor": "a", "chosen_option": "x", "source": "a"},
            ],
        },
    ),
)
def test_invalid_carried_decision_block_raises_naming_brief(
    tmp_path: Path, payload: dict[str, object]
) -> None:
    with pytest.raises(RoadmapSourceError, match="concept\\.md"):
        parse_carried_decisions(
            _carried_decision_block(payload), brief_path=tmp_path / "concept.md"
        )


def test_invalid_carried_decision_json_raises_naming_brief(tmp_path: Path) -> None:
    brief = "# Concept\n\n## Carried decisions\n\n```json\n{invalid}\n```\n"
    with pytest.raises(RoadmapSourceError, match="concept\\.md"):
        parse_carried_decisions(brief, brief_path=tmp_path / "concept.md")


def test_carried_decision_rejects_duplicate_or_free_form_fields(tmp_path: Path) -> None:
    brief = _carried_decision_block(
        {
            "confirmed_answers": [
                {"id": "answer", "answer": "x", "status": "confirmed"},
                {"id": "answer", "answer": "y", "status": "confirmed"},
            ],
            "decisions": [],
        }
    )

    with pytest.raises(RoadmapSourceError, match="duplicate"):
        parse_carried_decisions(brief, brief_path=tmp_path / "concept.md")


def test_brief_text_and_digest_match_broad_decoded_text_contract(tmp_path: Path) -> None:
    brief_path = tmp_path / "concept.md"
    source_bytes = b"first line\r\nsecond line\r\n"
    brief_path.write_bytes(source_bytes)

    text = read_brief_text(brief_path)

    assert text == "first line\nsecond line\n"
    assert digest_decoded_text(text) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert digest_decoded_text(text) != hashlib.sha256(source_bytes).hexdigest()


def test_non_utf8_recorded_brief_preserves_broad_read_failure(tmp_path: Path) -> None:
    brief_path = tmp_path / "concept.md"
    brief_path.write_bytes(b"\xff")

    with pytest.raises(UnicodeDecodeError):
        read_brief_text(brief_path)


def test_source_module_does_not_import_roadmap_or_orchestrator_modules(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module_path = Path(importlib.import_module("plan_tool.roadmap_source").__file__)
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert {module for module in imported_modules if module.startswith("plan_tool")} == set()
    monkeypatch.delitem(sys.modules, "plan_tool.roadmap_source", raising=False)
    monkeypatch.delitem(sys.modules, "plan_tool.roadmap", raising=False)
    importlib.import_module("plan_tool.roadmap_source")
    assert "plan_tool.roadmap" not in sys.modules
