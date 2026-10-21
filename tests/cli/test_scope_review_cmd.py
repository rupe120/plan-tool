from __future__ import annotations

import argparse
import json
from pathlib import Path

from plan_tool.cli import scope_review_cmd
from plan_tool.concept_bootstrap import ConceptConflict, bootstrap_concepts
from plan_tool.concept_sync import ConceptSyncResult, SyncStatus
from plan_tool.concept_tree import (
    RECORD_KIND_DECISION,
    ConceptNode,
    ConceptTree,
    concept_id,
    concepts_path,
    save_concepts,
)
from plan_tool.locator import slug_from_filename
from plan_tool.parser import parse_body_sections, parse_plan, split_plan_document
from plan_tool.review_persistence import compute_plan_fingerprint


def _write_plan(path: Path) -> str:
    text = (
        "---\ntitle: Review concepts\nstatus: planning\npriority: medium\nsteps:\n"
        "- id: 1\n  title: Ship\n---\n"
        "# Review concepts\n\n## Candidate\n\nCandidate source.\n\n"
        "## Tail\n\nUnrelated prose.\n"
    )
    path.write_text(text, encoding="utf-8")
    return text


def _args(concept: str, decision: str) -> argparse.Namespace:
    return argparse.Namespace(
        name="review-concepts",
        concept=[concept],
        decision=[(concept, decision)],
    )


def _multi_args(pairs: list[tuple[str, str]]) -> argparse.Namespace:
    return argparse.Namespace(
        name="review-concepts",
        concept=[concept for concept, _ in pairs],
        decision=list(pairs),
    )


def _resolve_to(monkeypatch, plan_path: Path) -> None:
    monkeypatch.setattr(scope_review_cmd, "_load_context", lambda args: object())
    monkeypatch.setattr(
        scope_review_cmd,
        "resolve_plan_for_context",
        lambda context, name: plan_path,
    )


def _seed_full_tree_record(plan_path: Path) -> ConceptTree:
    """Persist a valid legacy full-tree record matching the current plan."""
    text = plan_path.read_text(encoding="utf-8")
    tree = bootstrap_concepts(
        parse_plan(plan_path),
        parse_body_sections(split_plan_document(text).body),
        plan_slug=slug_from_filename(plan_path),
        plan_fingerprint=compute_plan_fingerprint(plan_path),
    )
    save_concepts(plan_path, tree)
    return tree


def _seed_flat_record(
    plan_path: Path, nodes: list[tuple[str, str, str]]
) -> ConceptTree:
    """Persist a flat decision record of ``(title, bucket, decision)`` nodes."""
    concepts = [
        ConceptNode(
            id=concept_id(title, []),
            title=title,
            order=index,
            decision=decision,
            bucket=bucket,
        )
        for index, (title, bucket, decision) in enumerate(nodes)
    ]
    tree = ConceptTree(
        plan_slug=slug_from_filename(plan_path),
        plan_fingerprint=compute_plan_fingerprint(plan_path),
        concepts=concepts,
        record_kind=RECORD_KIND_DECISION,
    )
    save_concepts(plan_path, tree)
    return tree


def _stored_nodes(plan_path: Path) -> dict[str, dict]:
    stored = json.loads(concepts_path(plan_path).read_text(encoding="utf-8"))
    return {node["title"]: node for node in stored["concepts"]}


def test_scope_review_confirms_flat_decision_after_unrelated_edit(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("parked idea", "tail", "defer")])
    # Edit an unrelated section so the plan fingerprint drifts from the record.
    edited = plan_path.read_text(encoding="utf-8").replace(
        "Candidate source.", "Candidate source, revised."
    )
    plan_path.write_text(edited, encoding="utf-8")
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(_args(concept_id("parked idea", []), "defer"))

    assert result == 0
    assert _stored_nodes(plan_path)["parked idea"]["review_state"] == "approved"
    updated = plan_path.read_text(encoding="utf-8")
    assert "## Deferred" in updated and "- parked idea" in updated
    assert "Candidate source, revised." in updated


def test_scope_review_confirms_after_edit_to_own_bucket_body(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("parked idea", "candidate", "defer")])
    # Rewrite the deferral's own bucket body but keep its H2 name.
    edited = plan_path.read_text(encoding="utf-8").replace(
        "Candidate source.", "Candidate source, entirely rewritten body."
    )
    plan_path.write_text(edited, encoding="utf-8")
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(_args(concept_id("parked idea", []), "defer"))

    assert result == 0
    output = capsys.readouterr()
    assert "no longer names a plan body section" not in output.out + output.err
    assert _stored_nodes(plan_path)["parked idea"]["review_state"] == "approved"


def test_scope_review_flat_missing_bucket_resolves_with_warn(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("orphaned idea", "deleted section", "wont_do")])
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("orphaned idea", []), "wont_do")
    )

    assert result == 0
    assert result != scope_review_cmd.SCOPE_REVIEW_INVALID_STATE_EXIT
    output = capsys.readouterr()
    assert "deleted section" in output.out + output.err
    assert "no longer names a plan body section" in output.out + output.err
    updated = plan_path.read_text(encoding="utf-8")
    assert "## Out of scope" in updated and "- orphaned idea" in updated


def test_scope_review_flat_preserves_unscoped_pending_nodes(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(
        plan_path,
        [("confirmed idea", "candidate", "defer"), ("pending idea", "tail", "defer")],
    )
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("confirmed idea", []), "defer")
    )

    assert result == 0
    stored = _stored_nodes(plan_path)
    assert stored["confirmed idea"]["review_state"] == "approved"
    assert stored["pending idea"]["review_state"] == "unreviewed"
    updated = plan_path.read_text(encoding="utf-8")
    assert "- confirmed idea" in updated
    assert "- pending idea" not in updated


def test_scope_review_flat_include_rejected(tmp_path: Path, monkeypatch) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("parked idea", "candidate", "defer")])
    before_plan = plan_path.read_bytes()
    before_sidecar = concepts_path(plan_path).read_bytes()
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("parked idea", []), "include")
    )

    assert result == scope_review_cmd.SCOPE_REVIEW_INVALID_STATE_EXIT == 4
    assert plan_path.read_bytes() == before_plan
    assert concepts_path(plan_path).read_bytes() == before_sidecar


def test_scope_review_flat_unknown_concept_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("parked idea", "candidate", "defer")])
    before_plan = plan_path.read_bytes()
    before_sidecar = concepts_path(plan_path).read_bytes()
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("no such concept", []), "defer")
    )

    assert result == scope_review_cmd.SCOPE_REVIEW_INVALID_STATE_EXIT
    assert plan_path.read_bytes() == before_plan
    assert concepts_path(plan_path).read_bytes() == before_sidecar


def test_scope_review_no_record_refused(tmp_path: Path, monkeypatch) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    before_plan = plan_path.read_bytes()
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(_args(concept_id("candidate", []), "defer"))

    assert result == scope_review_cmd.SCOPE_REVIEW_INVALID_STATE_EXIT == 4
    assert plan_path.read_bytes() == before_plan
    assert not concepts_path(plan_path).exists()


def test_scope_review_legacy_full_tree_still_confirms(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_full_tree_record(plan_path)
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(_args(concept_id("candidate", []), "defer"))

    assert result == 0
    stored = _stored_nodes(plan_path)
    assert stored["candidate"]["decision"] == "defer"
    assert stored["candidate"]["review_state"] == "approved"
    assert "- candidate" in plan_path.read_text(encoding="utf-8")


def test_scope_review_flat_sync_conflict_maps_to_conflict_exit(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_flat_record(plan_path, [("parked idea", "candidate", "defer")])
    before_plan = plan_path.read_bytes()
    before_sidecar = concepts_path(plan_path).read_bytes()
    _resolve_to(monkeypatch, plan_path)
    monkeypatch.setattr(
        scope_review_cmd,
        "synchronize_concepts",
        lambda *a, **k: ConceptSyncResult(
            SyncStatus.SOURCE_DIVERGENCE, "diverged"
        ),
    )

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("parked idea", []), "defer")
    )

    assert result == scope_review_cmd.SCOPE_REVIEW_CONFLICT_EXIT == 3
    assert plan_path.read_bytes() == before_plan
    assert concepts_path(plan_path).read_bytes() == before_sidecar


def test_scope_review_invalid_record_has_distinct_exit_and_writes_nothing(
    tmp_path: Path, monkeypatch
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    sidecar = concepts_path(plan_path)
    sidecar.parent.mkdir(parents=True)
    sidecar.write_text("{broken", encoding="utf-8")
    before_plan = plan_path.read_bytes()
    before_sidecar = sidecar.read_bytes()
    _resolve_to(monkeypatch, plan_path)

    result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("candidate", []), "include")
    )

    assert result == scope_review_cmd.SCOPE_REVIEW_INVALID_STATE_EXIT == 4
    assert plan_path.read_bytes() == before_plan
    assert sidecar.read_bytes() == before_sidecar


def test_scope_review_reports_all_derivation_conflicts_without_writes(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    plan_path = tmp_path / "review-concepts.md"
    _write_plan(plan_path)
    _seed_full_tree_record(plan_path)
    _resolve_to(monkeypatch, plan_path)
    concept = concept_id("candidate", [])
    before_plan = plan_path.read_bytes()
    before_sidecar = concepts_path(plan_path).read_bytes()
    original_rederive = scope_review_cmd.rederive_concepts

    def conflicting(current, fresh):
        result = original_rederive(current, fresh)
        result.conflicts = [
            ConceptConflict(concept, "candidate", "title", "A", "B", "C"),
            ConceptConflict(concept, "candidate", "source", "A", "B", "C"),
        ]
        return result

    monkeypatch.setattr(scope_review_cmd, "rederive_concepts", conflicting)
    result = scope_review_cmd.cmd_scope_review(_args(concept, "defer"))

    assert result == scope_review_cmd.SCOPE_REVIEW_CONFLICT_EXIT == 3
    output = capsys.readouterr()
    assert "title" in output.out + output.err
    assert "source" in output.out + output.err
    assert plan_path.read_bytes() == before_plan
    assert concepts_path(plan_path).read_bytes() == before_sidecar


def test_scope_review_parser_rejects_malformed_decision() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    scope_review_cmd.register(subparsers)
    try:
        parser.parse_args(
            ["scope-review", "plan", "--concept", "id", "--decision", "id=maybe"]
        )
    except SystemExit as exc:
        assert exc.code == 2
    else:
        raise AssertionError("argparse accepted an unknown concept decision")


def test_scope_review_uses_real_sections_for_flat_and_legacy_concepts(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    flat_path = tmp_path / "flat-review-concepts.md"
    flat_source = _write_plan(flat_path).replace(
        "## Candidate\n\nCandidate source.\n",
        "```markdown\n## Candidate\nExample-only bucket.\n```\n",
    )
    flat_path.write_text(flat_source, encoding="utf-8")
    _seed_flat_record(flat_path, [("parked idea", "candidate", "defer")])
    _resolve_to(monkeypatch, flat_path)

    flat_result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("parked idea", []), "defer")
    )
    flat_capture = capsys.readouterr()
    flat_output = flat_capture.out + flat_capture.err

    assert flat_result == 0
    assert "no longer names a plan body section" in flat_output

    legacy_path = tmp_path / "legacy-review-concepts.md"
    legacy_source = _write_plan(legacy_path).replace(
        "## Candidate\n\nCandidate source.\n",
        "```markdown\n## Example bucket\nExample-only bucket.\n```\n\n"
        "## Candidate\n\nCandidate source.\n",
    )
    legacy_path.write_text(legacy_source, encoding="utf-8")
    legacy_plan = parse_plan(legacy_path)
    safe_tree = bootstrap_concepts(
        legacy_plan,
        parse_body_sections(
            split_plan_document(legacy_source).body, ignore_fenced_code=True
        ),
        plan_slug=slug_from_filename(legacy_path),
        plan_fingerprint=compute_plan_fingerprint(legacy_path),
    )
    save_concepts(legacy_path, safe_tree)
    _resolve_to(monkeypatch, legacy_path)

    legacy_result = scope_review_cmd.cmd_scope_review(
        _args(concept_id("candidate", []), "defer")
    )

    assert legacy_result == 0
    assert "example bucket" not in _stored_nodes(legacy_path)
