from __future__ import annotations

import copy
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from plan_tool.concept_sync import SyncStatus, _fingerprint, synchronize_concepts
from plan_tool.concept_tree import ConceptNode, ConceptTree, concept_id, concepts_path
from plan_tool.parser import parse_plan, split_body_sections
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.schema import PLAN_FORMAT_VERSION, StepScope


def _write_plan(path: Path) -> str:
    text = (
        "---\ntitle: Sync\nstatus: planning\npriority: medium\nsteps:\n"
        "- id: 1\n  title: Ship\n- id: 2\n  title: Later\n---\n"
        "# Sync\n\n## Custom\n\nKeep  two spaces.\n\n"
        "## Deferred\n\nOld\n\n## Tail\n\nKeep tail.\n"
    )
    path.write_text(text, encoding="utf-8")
    return text


def _write_plan_with_fenced_owned_heading(path: Path) -> str:
    text = (
        "---\ntitle: Sync\nstatus: planning\npriority: medium\nsteps:\n"
        "- id: 1\n  title: Ship\n- id: 2\n  title: Later\n---\n"
        "# Sync\n\n## Custom\n\nKeep custom content.\n\n"
        "```markdown\n## Deferred\n\nExample decision\n```\n\n"
        "## Deferred\n\nOld\n\n## Tail\n\nKeep tail.\n"
    )
    path.write_text(text, encoding="utf-8")
    return text


def _node(title: str, decision: str, *, order: int, step_id: str | None = None) -> ConceptNode:
    metadata = {} if step_id is None else {"step_id": step_id}
    return ConceptNode(
        id=concept_id(title, []), title=title, order=order,
        decision=decision, rationale=f"Why {title}", review_state="approved",
        source_metadata=metadata,
    )


def _tree(*nodes: ConceptNode) -> ConceptTree:
    return ConceptTree(plan_slug="sync", plan_fingerprint="old", concepts=list(nodes))


def _persist_tree(plan_path: Path, tree: ConceptTree) -> None:
    target = concepts_path(plan_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(tree), indent=2) + "\n", encoding="utf-8")


def test_generated_handoff_does_not_change_concept_sync_fingerprint(
    tmp_path: Path,
) -> None:
    """``_fingerprint`` walks the plan plus its ``plan-details/<slug>/*.md``
    bundle only — a companion developer-handoff under
    ``jira-handoffs/<slug>/`` sits outside that bundle, so concept
    synchronization stays grounded on the plan and its detail bundle, not
    the terminal handoff.
    """
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    bundle = tmp_path / "plan-details" / "sync"
    bundle.mkdir(parents=True)
    (bundle / "01-a.md").write_text("alpha", encoding="utf-8")
    baseline = _fingerprint(path, source.encode("utf-8"))

    handoff_dir = tmp_path / "jira-handoffs" / "sync"
    handoff_dir.mkdir(parents=True)
    handoff = handoff_dir / "jira-stories.developer-handoff.md"
    handoff.write_text("# Developer handoff\n", encoding="utf-8")
    assert _fingerprint(path, source.encode("utf-8")) == baseline

    handoff.write_text("# Developer handoff, edited\n", encoding="utf-8")
    assert _fingerprint(path, source.encode("utf-8")) == baseline


def test_sync_renders_decisions_preserves_markdown_and_maps_steps(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(
        _node("Included", "include", order=0, step_id="1"),
        _node("Delayed", "defer", order=1, step_id="2"),
        _node("Rejected", "wont_do", order=2),
    )
    _persist_tree(path, tree)

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SUCCESS
    updated = path.read_text(encoding="utf-8")
    sections = split_body_sections(updated.split("---\n", 2)[2])
    assert "Delayed" in sections["deferred"]
    assert "Rejected" in sections["out of scope"]
    assert "Included" not in sections["deferred"] + sections["out of scope"]
    assert "## Custom\n\nKeep  two spaces." in updated
    assert "## Tail\n\nKeep tail." in updated
    parsed = parse_plan(path)
    assert parsed.step_by_id(1).scope is StepScope.COMMITTED
    assert parsed.step_by_id(2).scope is StepScope.DEFERRED
    assert parsed.risk_profile is None
    assert parsed.risk_profile_rationale is None
    stored = json.loads(concepts_path(path).read_text(encoding="utf-8"))
    assert stored["plan_fingerprint"] == compute_plan_fingerprint(path)


def test_synchronized_plan_carries_the_current_format_version_declaration(
    tmp_path: Path,
) -> None:
    """``synchronize_concepts`` publishes through ``render_plan_text`` — the
    one other in-repo caller besides ``write_plan`` — so its output must
    also carry the current format declaration, not just parse-time reads."""
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0, step_id="2"))
    _persist_tree(path, tree)

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SUCCESS
    reloaded = parse_plan(path)
    assert reloaded.format_version == PLAN_FORMAT_VERSION


def test_sync_strips_whitespace_from_step_id_mapping(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0, step_id=" 2 "))
    _persist_tree(path, tree)

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SUCCESS
    assert parse_plan(path).step_by_id(2).scope is StepScope.DEFERRED


def test_sync_detects_changed_owned_section_without_writes(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)
    changed = path.read_text().replace("Old", "Concurrent")
    path.write_text(changed)

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)
    assert result.status is SyncStatus.SOURCE_DIVERGENCE
    assert path.read_text() == changed


def test_sync_ignores_changed_fenced_pseudo_owned_heading_in_compare(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan_with_fenced_owned_heading(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)
    changed = path.read_text(encoding="utf-8").replace(
        "```markdown\n## Deferred\n\nExample decision\n```",
        "```markdown\n## Out of scope\n\nEdited example decision\n```",
    )
    path.write_text(changed, encoding="utf-8")

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SUCCESS
    updated = path.read_text(encoding="utf-8")
    assert "```markdown\n## Out of scope\n\nEdited example decision\n```" in updated


def test_sync_replaces_only_real_owned_heading_and_preserves_fenced_example(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan_with_fenced_owned_heading(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SUCCESS
    updated = path.read_text(encoding="utf-8")
    assert "```markdown\n## Deferred\n\nExample decision\n```" in updated
    sections = split_body_sections(
        updated.split("---\n", 2)[2], ignore_fenced_code=True
    )
    assert sections["deferred"] == "- Delayed — Why Delayed"


@pytest.mark.parametrize("sidecar_exists", [False, True])
@pytest.mark.parametrize("unsafe_text", ["snapshot", "current"])
def test_sync_rejects_unmatched_opening_fence_without_changing_plan_or_sidecar(
    tmp_path: Path,
    sidecar_exists: bool,
    unsafe_text: str,
) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    original_tree = tree if sidecar_exists else None
    if sidecar_exists:
        _persist_tree(path, tree)
    unsafe_source = source + "\n```markdown\n## Deferred\nunsafe\n"
    if unsafe_text == "current":
        path.write_text(unsafe_source, encoding="utf-8")
    before_plan = path.read_bytes()
    sidecar = concepts_path(path)
    before_sidecar = sidecar.read_bytes() if sidecar_exists else None

    result = synchronize_concepts(
        path,
        plan,
        original_tree,
        tree,
        source_plan_text=unsafe_source if unsafe_text == "snapshot" else source,
    )

    assert result.status is SyncStatus.INVALID_STATE
    assert "unmatched opening code fence" in result.message
    assert path.read_bytes() == before_plan
    if before_sidecar is None:
        assert not sidecar.exists()
    else:
        assert sidecar.read_bytes() == before_sidecar


def test_sync_non_utf8_plan_returns_source_divergence(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0, step_id="2"))
    path.write_bytes(b"\xff")

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SOURCE_DIVERGENCE
    assert "utf-8" in result.message.lower()


def test_sync_rejects_conflicting_mappings_without_writes(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    tree = _tree(
        _node("A", "include", order=0, step_id="1"),
        _node("B", "defer", order=1, step_id="1"),
    )
    before = path.read_bytes()
    result = synchronize_concepts(path, parse_plan(path), None, tree, source_plan_text=source)
    assert result.status is SyncStatus.MAPPING_CONFLICT
    assert path.read_bytes() == before
    assert not concepts_path(path).exists()


def test_sync_rejects_oversized_step_id_mapping_without_writes(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    tree = _tree(_node("A", "include", order=0, step_id="1" + "0" * 4999))
    before = path.read_bytes()

    result = synchronize_concepts(
        path, parse_plan(path), None, tree, source_plan_text=source
    )

    assert result.status is SyncStatus.MAPPING_CONFLICT
    assert "invalid step_id mapping" in result.message
    assert path.read_bytes() == before
    assert not concepts_path(path).exists()


def test_second_publication_failure_rolls_back_new_sidecar(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    before = path.read_bytes()
    tree = _tree(_node("Delayed", "defer", order=0))
    calls = 0

    def publisher(target: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    result = synchronize_concepts(
        path, parse_plan(path), None, copy.deepcopy(tree),
        source_plan_text=source, publish=publisher,
    )
    assert result.status is SyncStatus.PUBLICATION_FAILURE
    assert path.read_bytes() == before
    assert not concepts_path(path).exists()


def test_second_publication_failure_restores_existing_plan_and_sidecar(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)
    before_plan = path.read_bytes()
    before_sidecar = concepts_path(path).read_bytes()
    calls = 0

    def publisher(target: Path, text: str) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("injected")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    result = synchronize_concepts(
        path,
        parse_plan(path),
        tree,
        copy.deepcopy(tree),
        source_plan_text=source,
        publish=publisher,
    )

    assert result.status is SyncStatus.PUBLICATION_FAILURE
    assert path.read_bytes() == before_plan
    assert concepts_path(path).read_bytes() == before_sidecar


def test_first_publication_failure_leaves_both_files(tmp_path: Path) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)
    old_plan = path.read_bytes()
    old_sidecar = concepts_path(path).read_bytes()

    def fail(_target: Path, _text: str) -> None:
        raise OSError("injected")

    result = synchronize_concepts(
        path, parse_plan(path), tree, tree, source_plan_text=source, publish=fail,
    )
    assert result.status is SyncStatus.PUBLICATION_FAILURE
    assert path.read_bytes() == old_plan
    assert concepts_path(path).read_bytes() == old_sidecar


@pytest.mark.parametrize("newline", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("with_snapshot", [False, True])
def test_sync_preserves_unowned_bytes_and_replaces_real_owned_section(
    tmp_path: Path, newline: str, with_snapshot: bool,
) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan_with_fenced_owned_heading(path).replace("\n", newline)
    path.write_bytes(source.encode())
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0, step_id="2"))
    _persist_tree(path, tree)
    changed = source.replace("Keep custom content.", "Concurrent custom content.")
    path.write_bytes(changed.encode())

    result = synchronize_concepts(
        path, plan, tree, tree,
        source_plan_text=source if with_snapshot else None,
    )

    assert result.status is SyncStatus.SUCCESS
    updated = path.read_bytes()
    custom = changed[changed.index("# Sync"):changed.rindex("## Deferred")]
    tail = changed[changed.index("## Tail"):]
    assert custom.encode() in updated
    assert tail.encode() in updated
    sections = split_body_sections(updated.decode().split("---\n", 2)[2], ignore_fenced_code=True)
    assert sections["deferred"] == "- Delayed — Why Delayed"
    assert json.loads(concepts_path(path).read_text())["plan_fingerprint"] == compute_plan_fingerprint(path)
    # Publication refreshes provenance for the original in-memory snapshot.
    from plan_tool.parser import write_plan
    write_plan(path, plan)
    assert tail.encode() in path.read_bytes()


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
def test_sync_rejects_concurrent_owned_edit_without_normalizing_bytes(
    tmp_path: Path, newline: str,
) -> None:
    path = tmp_path / "sync.md"
    source = _write_plan(path).replace("\n", newline)
    path.write_bytes(source.encode())
    plan = parse_plan(path)
    tree = _tree(_node("Delayed", "defer", order=0))
    _persist_tree(path, tree)
    changed = source.replace("Old", "Concurrent").encode()
    path.write_bytes(changed)
    sidecar = concepts_path(path).read_bytes()

    result = synchronize_concepts(path, plan, tree, tree, source_plan_text=source)

    assert result.status is SyncStatus.SOURCE_DIVERGENCE
    assert path.read_bytes() == changed
    assert concepts_path(path).read_bytes() == sidecar
