"""Tests for the INDEX.md renderer over the roadmap version store."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from plan_tool import roadmap_candidate_run, roadmap_index
from plan_tool.roadmap_index import (
    IndexVersionRow,
    RoadmapIndexNoHeadError,
    classify_version_status,
    collect_index_rows,
    collect_index_stack_lines,
    render_roadmap_index,
    write_roadmap_index,
)
from plan_tool.roadmap_versions import (
    VERSION_ARTIFACT_KEYS,
    AcceptedRoadmapHead,
    RoadmapVersionError,
    artifact_member_name,
    create_candidate_version,
    create_root_version,
    render_accepted_head,
    render_stored_version,
    stored_artifact_path,
    stored_brief_path,
    stored_version_record_path,
    version_namespace_path,
)

SLUG = "storefront"
LINEAGE = hashlib.sha256(b"lineage").hexdigest()


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


STACKLESS_CONSTRAINTS = "---\ndispositions: []\nconstraints: []\ndecisions: []\n---\nbody\n"
EMPTY_COMPONENTS = "---\ncomponents: []\ndecisions: []\n---\nbody\n"


EMPTY_PLANS = "---\nplans: []\nordering: []\nassumptions: []\ndecisions: []\n---\nbody\n"


def _member_texts(
    tag: str, constraints_text: str, components_text: str, plans_text: str = EMPTY_PLANS
) -> dict[str, str]:
    texts = {key: f"{tag}-{key}" for key in VERSION_ARTIFACT_KEYS}
    texts["constraints"] = constraints_text
    texts["components"] = components_text
    texts["plans"] = plans_text
    return texts


def _store(plans_dir: Path, record, texts: dict[str, str], brief_text: str) -> str:
    path = stored_version_record_path(plans_dir, SLUG, record.version_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_stored_version(record))
    for key, text in texts.items():
        stored_artifact_path(plans_dir, SLUG, record.version_id, key).write_text(text)
    stored_brief_path(plans_dir, SLUG, record.version_id).write_text(brief_text)
    return record.version_id


def _root(
    plans_dir: Path,
    tag: str = "root",
    constraints_text: str = STACKLESS_CONSTRAINTS,
    components_text: str = EMPTY_COMPONENTS,
    plans_text: str = EMPTY_PLANS,
) -> str:
    texts = _member_texts(tag, constraints_text, components_text, plans_text)
    record = create_root_version(
        roadmap_slug=SLUG,
        brief_digest=_digest(tag),
        artifact_digests=[_digest(texts[key]) for key in VERSION_ARTIFACT_KEYS],
    )
    return _store(plans_dir, record, texts, tag)


def _candidate(
    plans_dir: Path,
    predecessor: str,
    tag: str,
    constraints_text: str = STACKLESS_CONSTRAINTS,
    components_text: str = EMPTY_COMPONENTS,
) -> str:
    texts = _member_texts(tag, constraints_text, components_text)
    record = create_candidate_version(
        roadmap_slug=SLUG,
        predecessor_version_id=predecessor,
        content_identity=_digest(f"content-{tag}"),
        review_lineage_identity=LINEAGE,
        brief_digest=_digest(tag),
        artifact_digests=[_digest(texts[key]) for key in VERSION_ARTIFACT_KEYS],
    )
    return _store(plans_dir, record, texts, tag)


def _set_head(plans_dir: Path, version_id: str) -> None:
    head = AcceptedRoadmapHead(schema_version=1, roadmap_slug=SLUG, version_id=version_id)
    (version_namespace_path(plans_dir, SLUG) / "accepted-head.json").write_bytes(
        render_accepted_head(head)
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def _namespace(plans_dir: Path) -> Path:
    return version_namespace_path(plans_dir, SLUG)


def _status_by_id(plans_dir: Path) -> dict[str, str]:
    _, rows = collect_index_rows(plans_dir, SLUG)
    return {row.version_id: row.status for row in rows}


def _row(version_id: str, **overrides) -> IndexVersionRow:
    fields = dict(
        version_id=version_id,
        kind="root",
        status="promoted",
        predecessor_version_id=None,
        answered_feedback_ids=(),
    )
    fields.update(overrides)
    return IndexVersionRow(**fields)


def test_render_links_the_four_artifacts_of_the_accepted_head():
    head = "a" * 64
    text = render_roadmap_index(SLUG, head, [_row(head, status="accepted head")], [])
    assert len(VERSION_ARTIFACT_KEYS) == 4
    for key in VERSION_ARTIFACT_KEYS:
        assert f"[{key}](.roadmap-versions/{head}/{artifact_member_name(key)})" in text


def test_every_version_gets_exactly_one_status(tmp_path):
    root = _root(tmp_path)
    mid = _candidate(tmp_path, root, "mid")
    head = _candidate(tmp_path, mid, "head")
    stray = _candidate(tmp_path, root, "stray")
    _set_head(tmp_path, head)
    _, rows = collect_index_rows(tmp_path, SLUG)
    assert sorted(row.version_id for row in rows) == sorted([root, mid, head, stray])
    assert all(isinstance(row.status, str) and row.status for row in rows)


def test_head_is_listed_as_accepted_head_and_ancestors_as_promoted(tmp_path):
    root = _root(tmp_path)
    mid = _candidate(tmp_path, root, "mid")
    head = _candidate(tmp_path, mid, "head")
    _set_head(tmp_path, head)
    assert _status_by_id(tmp_path) == {
        root: "promoted",
        mid: "promoted",
        head: "accepted head",
    }


def test_superseded_stack_hop_that_was_promoted_reads_promoted(tmp_path):
    # Promoted outranks superseded: a hop superseded when the stack grew is promoted with it.
    root = _root(tmp_path)
    hop = _candidate(tmp_path, root, "hop")
    head = _candidate(tmp_path, hop, "head")
    _set_head(tmp_path, head)
    _write_json(_namespace(tmp_path) / "candidate-supersessions" / f"{hop}.json", {})
    assert _status_by_id(tmp_path)[hop] == "promoted"


def test_active_candidate_reads_active(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, root)
    _write_json(
        _namespace(tmp_path) / "candidate-admission.json",
        {"active_candidate_version_id": cand},
    )
    assert _status_by_id(tmp_path)[cand] == "active"


@pytest.mark.parametrize("reason", ["rejected", "discarded", "settled"])
def test_terminal_reasons_render_as_rejected_discarded_settled(tmp_path, reason):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, root)
    _write_json(
        _namespace(tmp_path) / "candidate-terminal-resolutions" / f"{cand}.json",
        {"reason": reason},
    )
    assert _status_by_id(tmp_path)[cand] == reason


def test_superseded_candidate_that_is_not_promoted_reads_superseded(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, root)
    _write_json(_namespace(tmp_path) / "candidate-supersessions" / f"{cand}.json", {})
    assert _status_by_id(tmp_path)[cand] == "superseded"


def test_version_with_no_status_record_is_listed_unrecorded(tmp_path):
    root = _root(tmp_path)
    orphan = _candidate(tmp_path, root, "orphan")
    _set_head(tmp_path, root)
    assert _status_by_id(tmp_path)[orphan] == "unrecorded"


def test_unrecorded_version_does_not_stop_the_rest_of_the_index(tmp_path):
    root = _root(tmp_path)
    orphan = _candidate(tmp_path, root, "orphan")
    _set_head(tmp_path, root)
    path = write_roadmap_index(tmp_path, SLUG)
    text = path.read_text()
    assert f"`{orphan[:8]}` | candidate | unrecorded" in text
    assert f"`{root[:8]}` | root | accepted head" in text
    for key in VERSION_ARTIFACT_KEYS:
        assert f"[{key}](" in text


def test_selector_era_admission_without_pointer_keys_is_readable(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, root)
    _write_json(
        _namespace(tmp_path) / "candidate-admission.json",
        {"schema_version": 1, "roadmap_slug": SLUG, "predecessor_version_id": root},
    )
    assert _status_by_id(tmp_path)[cand] == "unrecorded"


def test_answered_feedback_ids_come_from_batch_and_selector_evidence(tmp_path):
    root = _root(tmp_path)
    batch = _candidate(tmp_path, root, "batch")
    selector = _candidate(tmp_path, root, "selector")
    _set_head(tmp_path, root)
    ns = _namespace(tmp_path)
    _write_json(
        ns / batch / "candidate-evidence.json",
        {"batch_receipt": {"reviewer_items": [{"item_id": "r1"}, {"item_id": "r2"}]}},
    )
    _write_json(ns / selector / "candidate-evidence.json", {"feedback": {"feedback_id": "f9"}})
    _, rows = collect_index_rows(tmp_path, SLUG)
    answered = {row.version_id: row.answered_feedback_ids for row in rows}
    assert answered[batch] == ("r1", "r2")
    assert answered[selector] == ("f9",)
    assert answered[root] == ()
    text = render_roadmap_index(SLUG, root, rows, [])
    assert f"`{root[:8]}` | root | accepted head | — | none |" in text


def test_lineage_order_is_root_first_then_depth_then_id(tmp_path):
    root = _root(tmp_path)
    child_a = _candidate(tmp_path, root, "a")
    child_b = _candidate(tmp_path, root, "b")
    grandchild = _candidate(tmp_path, child_a, "grand")
    _set_head(tmp_path, grandchild)
    _, rows = collect_index_rows(tmp_path, SLUG)
    ids = [row.version_id for row in rows]
    assert ids == [root, *sorted([child_a, child_b]), grandchild]


def test_render_contains_no_date_or_timestamp(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, cand)
    text = write_roadmap_index(tmp_path, SLUG).read_text()
    assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}", text)


def test_render_is_deterministic_for_the_same_store(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, cand)
    first = write_roadmap_index(tmp_path, SLUG).read_bytes()
    second = write_roadmap_index(tmp_path, SLUG).read_bytes()
    assert first == second


def test_no_head_is_a_named_refusal_not_an_empty_index(tmp_path):
    _root(tmp_path)
    with pytest.raises(RoadmapIndexNoHeadError):
        write_roadmap_index(tmp_path, SLUG)
    assert not (tmp_path / "roadmaps" / SLUG / "INDEX.md").exists()


def test_malformed_terminal_record_raises_instead_of_being_swallowed(tmp_path):
    root = _root(tmp_path)
    cand = _candidate(tmp_path, root, "cand")
    _set_head(tmp_path, root)
    _write_json(
        _namespace(tmp_path) / "candidate-terminal-resolutions" / f"{cand}.json",
        {"reason": "bogus"},
    )
    with pytest.raises(RoadmapVersionError):
        collect_index_rows(tmp_path, SLUG)


def test_write_replaces_the_whole_file(tmp_path):
    root = _root(tmp_path)
    _set_head(tmp_path, root)
    index = tmp_path / "roadmaps" / SLUG / "INDEX.md"
    index.write_text("stale line\n" * 500)
    write_roadmap_index(tmp_path, SLUG)
    assert "stale line" not in index.read_text()


def test_classify_precedence_orders_head_promoted_active_terminal_superseded_unrecorded():
    base = dict(
        head_version_id="h",
        promoted_ancestor_ids=frozenset({"p"}),
        active_candidate_version_id="a",
        terminal_reason="rejected",
        is_superseded=True,
    )
    assert classify_version_status("h", **base) == "accepted head"
    assert classify_version_status("p", **base) == "promoted"
    assert classify_version_status("a", **base) == "active"
    assert classify_version_status("t", **base) == "rejected"
    assert classify_version_status("s", **{**base, "terminal_reason": None}) == "superseded"
    assert (
        classify_version_status("u", **{**base, "terminal_reason": None, "is_superseded": False})
        == "unrecorded"
    )


def test_mirrored_record_names_match_candidate_run_path_helpers(tmp_path):
    version_id = "b" * 64
    ns = version_namespace_path(tmp_path, SLUG)
    assert roadmap_candidate_run.candidate_admission_path(tmp_path, SLUG) == ns / roadmap_index.ADMISSION_FILENAME
    assert (
        roadmap_candidate_run.candidate_evidence_path(tmp_path, SLUG, version_id).name
        == roadmap_index.EVIDENCE_FILENAME
    )
    assert (
        roadmap_candidate_run.supersession_path(tmp_path, SLUG, version_id)
        == ns / roadmap_index.SUPERSESSIONS_DIRECTORY / f"{version_id}.json"
    )
    assert (
        roadmap_candidate_run.terminal_resolution_path(tmp_path, SLUG, version_id)
        == ns / roadmap_index.TERMINAL_RESOLUTIONS_DIRECTORY / f"{version_id}.json"
    )


def test_module_imports_no_roadmap_orchestrator():
    # The subprocess check sees runtime imports; the source scan also sees a lazy in-function one.
    probe = (
        "import sys, plan_tool.roadmap_index; "
        "bad = [m for m in ('plan_tool.roadmap', 'plan_tool.roadmap_candidate_run') if m in sys.modules]; "
        "print(','.join(bad))"
    )
    result = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, check=True)
    assert result.stdout.strip() == ""
    source = Path(roadmap_index.__file__).read_text()
    assert not re.search(r"roadmap_candidate_run|plan_tool\.roadmap import|from plan_tool import roadmap\b", source)


# --------------------------------------------------------------------------
# Stack section
# --------------------------------------------------------------------------

STACK_CONSTRAINTS = (
    "---\ndispositions: []\nconstraints: []\ndecisions: []\n"
    "stack:\n"
    "- id: stack-1\n  concern: platform\n  choice: AWS Lambda\n"
    "- id: stack-2\n  concern: store-engine\n  open: true\n"
    "---\nbody\n"
)
PENDING_STACK_COMPONENTS = (
    "---\ncomponents: []\ndecisions:\n"
    "- id: decision-1\n  chosen_option: Lambda\n  rejected_alternatives: []\n"
    "  rationale: fits\n  anchor: stack-1\n  status: pending\n"
    "---\nbody\n"
)


def _stack_section(text: str) -> str:
    return text.split("## Stack\n\n", 1)[1].split("\n\n## Versions", 1)[0]


def test_index_stack_section_lists_every_row_with_groups(tmp_path):
    root = _root(
        tmp_path, constraints_text=STACK_CONSTRAINTS, components_text=PENDING_STACK_COMPONENTS
    )
    _set_head(tmp_path, root)
    section = _stack_section(write_roadmap_index(tmp_path, SLUG).read_text())
    assert "- `stack-1` platform: AWS Lambda" in section
    assert "- `stack-2` store-engine: open" in section
    open_group = section.split("Open concerns:\n")[1].split("Pending concerns:")[0]
    pending_group = section.split("Pending concerns:\n")[1]
    assert "stack-2" in open_group and "stack-1" not in open_group
    assert "stack-1" in pending_group and "stack-2" not in pending_group


def test_index_pending_concerns_include_a_pending_decision_authored_in_the_plans_artifact(tmp_path):
    """A stage-4 decision can anchor to a stack row, so the pending group reads all three
    decision-bearing artifacts the stack can be anchored from, not constraints and components alone."""
    plans_text = (
        "---\nplans: []\nordering: []\nassumptions: []\ndecisions:\n"
        "- id: decision-9\n  chosen_option: Lambda\n  rejected_alternatives: []\n"
        "  rationale: fits\n  anchor: stack-1\n  status: pending\n---\nbody\n"
    )
    root = _root(tmp_path, constraints_text=STACK_CONSTRAINTS, plans_text=plans_text)
    _set_head(tmp_path, root)
    section = _stack_section(write_roadmap_index(tmp_path, SLUG).read_text())
    assert "stack-1" in section.split("Pending concerns:\n")[1]


def test_index_for_stackless_head_says_not_recorded(tmp_path):
    root = _root(tmp_path)
    _set_head(tmp_path, root)
    section = _stack_section(write_roadmap_index(tmp_path, SLUG).read_text())
    assert section == "Stack: not recorded for this version."


def test_index_stack_text_equals_producer_output(tmp_path):
    root = _root(
        tmp_path, constraints_text=STACK_CONSTRAINTS, components_text=PENDING_STACK_COMPONENTS
    )
    _set_head(tmp_path, root)
    expected = "\n".join(collect_index_stack_lines(tmp_path, SLUG, root))
    assert _stack_section(write_roadmap_index(tmp_path, SLUG).read_text()) == expected


def test_index_rewrite_is_whole_file_and_replaces_prior_stack_section(tmp_path):
    first = _root(tmp_path, constraints_text=STACK_CONSTRAINTS)
    _set_head(tmp_path, first)
    assert "stack-2" in write_roadmap_index(tmp_path, SLUG).read_text()
    second = _candidate(tmp_path, first, "next")
    _set_head(tmp_path, second)
    text = write_roadmap_index(tmp_path, SLUG).read_text()
    assert "stack-1" not in text and "stack-2" not in text
    assert text.count("## Stack") == 1


def test_index_with_unparseable_head_constraints_raises_version_error(tmp_path):
    root = _root(tmp_path, constraints_text="not a roadmap artifact\n")
    _set_head(tmp_path, root)
    with pytest.raises(RoadmapVersionError):
        write_roadmap_index(tmp_path, SLUG)
