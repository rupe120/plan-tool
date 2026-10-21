"""Tests for computed draft-seed lifecycle classifications."""

from __future__ import annotations

from pathlib import Path

import pytest

from plan_tool.roadmap_artifacts import (
    COMPONENTS_FILENAME,
    CONSTRAINTS_FILENAME,
    DOMAIN_FILENAME,
    PLANS_FILENAME,
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    parse_plans_artifact,
    render_plans_artifact,
    roadmap_dir,
)
from plan_tool.roadmap_seed_manifest import (
    DRAFT_SEED_STATE_CURRENT,
    DRAFT_SEED_STATE_DIGEST_MISMATCHED,
    DRAFT_SEED_STATE_DUPLICATE,
    DRAFT_SEED_STATE_MALFORMED,
    DRAFT_SEED_STATE_MISSING,
    DRAFT_SEED_STATE_PATH_ESCAPING,
    DRAFT_SEED_STATE_PRECEDENCE,
    DRAFT_SEED_STATE_STALE,
    ORPHAN_SEED_RECORD_FILE,
    ORPHAN_SEED_RECORD_SIDECAR_ENTRY,
    classify_draft_seeds,
    find_orphan_seed_records,
)
from plan_tool.roadmap_seed_state import (
    RoadmapSeedStateError,
    digest_text,
    empty_seed_state,
    seed_state_path,
    write_seed_state,
)


SLUG = "demo"


def _plan(
    plan_id: str = "slice",
    *,
    draft_seed_path: str = "plan-seed-drafts/slice.md",
    component_ids: tuple[str, ...] = ("component-a",),
) -> PlanRow:
    return PlanRow(
        id=plan_id,
        title=plan_id.title(),
        disposition=PlanDisposition.KEEP,
        component_ids=component_ids,
        draft_seed_path=draft_seed_path,
        sizing_rationale="Keeps one bounded concern together.",
    )


def _artifact(*plans: PlanRow) -> PlansArtifact:
    return PlansArtifact(
        plans=plans,
        ordering=(),
        assumptions=(),
        decisions=(),
        body="# Roadmap\n",
    )


def _seed_text(*component_ids: str) -> str:
    components = "\n".join(f"  - {component_id}" for component_id in component_ids)
    return (
        f"---\nroadmap_components:\n{components}\n---\n# Seed\n\n"
        "## Risks\n\n- A risk the accepted roadmap already states.\n\n"
        "## References\n\n"
        f"- `{DOMAIN_FILENAME}`\n"
        f"- `{CONSTRAINTS_FILENAME}`\n"
        f"- `{COMPONENTS_FILENAME}`\n"
        f"- `{PLANS_FILENAME}`\n"
    )


def _root(plans_dir: Path) -> Path:
    return roadmap_dir(plans_dir, SLUG)


def _write_seed(plans_dir: Path, plan: PlanRow, text: str) -> Path:
    source = _root(plans_dir) / plan.draft_seed_path
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text(text, encoding="utf-8")
    return source


def _write_state(plans_dir: Path, entries: dict[str, dict[str, object]]) -> Path:
    state = empty_seed_state()
    state["seeds"].update(entries)
    path = seed_state_path(_root(plans_dir))
    write_seed_state(path, state)
    return path


def _entry(plan: PlanRow, text: str, *, status: str = "current") -> dict[str, object]:
    return {
        "draft_seed_path": plan.draft_seed_path,
        "status": status,
        "digest": digest_text(text),
        "published": False,
    }


def test_classify_current_when_digest_matches_and_content_validates(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids)
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_CURRENT
    assert classification[plan.id].detail == ""


def test_classify_current_for_a_draft_that_carries_a_stack_section(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids).replace(
        "## References",
        "## Stack\n\nSettled by the accepted roadmap (version `v1`).\n\n"
        "### Hosting\n\n- `hosting-compute` — facet: compute; value: per-request; product: x\n\n"
        "## References",
    )
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_CURRENT
    assert classification[plan.id].detail == ""


def test_classify_current_for_seed_text_carrying_the_stack_section(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids).replace(
        "## References",
        "## Stack\n\nSettled by the accepted roadmap (version `v1`).\n\n"
        "### Hosting\n\n- (none) The accepted roadmap lists no hosting rows.\n\n"
        "### Technology stack\n\n"
        "- `stack-platform` — concern: platform; open — not decided by the accepted roadmap\n\n"
        "## References",
    )
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_CURRENT


@pytest.mark.parametrize("with_entry", [False, True])
def test_classify_missing_when_no_file_exists(tmp_path: Path, with_entry: bool) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    if with_entry:
        _write_state(plans_dir, {plan.id: _entry(plan, _seed_text(*plan.component_ids))})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_MISSING


@pytest.mark.parametrize("with_entry", [False, True])
def test_classify_digest_mismatched_without_a_known_good_digest(
    tmp_path: Path, with_entry: bool
) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids)
    source = _write_seed(plans_dir, plan, text)
    if with_entry:
        entry = _entry(plan, text)
        entry["digest"] = None
        _write_state(plans_dir, {plan.id: entry})

    original_read_text = Path.read_text

    def unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == source:
            raise OSError("unreadable draft")
        return original_read_text(path, *args, **kwargs)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(Path, "read_text", unreadable)
    try:
        classification = classify_draft_seeds(
            _artifact(plan), plans_dir=plans_dir, slug=SLUG
        )
    finally:
        monkeypatch.undo()

    assert classification[plan.id].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED


def test_classify_digest_mismatched_when_file_changes(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids)
    source = _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})
    source.write_text(text + "hand edit\n", encoding="utf-8")

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_DIGEST_MISMATCHED


def test_stale_takes_precedence_over_malformed(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    invalid_text = _seed_text("component-other")
    _write_seed(plans_dir, plan, invalid_text)
    _write_state(
        plans_dir, {plan.id: _entry(plan, invalid_text, status="invalidated")}
    )

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_STALE


def test_classify_malformed_includes_validation_detail(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    invalid_text = _seed_text("component-other")
    _write_seed(plans_dir, plan, invalid_text)
    _write_state(plans_dir, {plan.id: _entry(plan, invalid_text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    result = classification[plan.id]
    assert result.state == DRAFT_SEED_STATE_MALFORMED
    assert "component-other" in result.detail


def test_classify_malformed_when_digest_matching_seed_omits_accepted_artifact_reference(
    tmp_path: Path,
) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids).replace(f"- `{DOMAIN_FILENAME}`\n", "")
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_MALFORMED
    assert DOMAIN_FILENAME in classification[plan.id].detail


def test_classify_malformed_when_digest_matching_seed_has_no_risks(tmp_path: Path) -> None:
    # The consumer of `validate_draft_seed_content` that `--apply` and
    # `--accept-seed` both trust: a Risks-less draft is `malformed`, not `current`.
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids).replace(
        "## Risks\n\n- A risk the accepted roadmap already states.\n\n", ""
    )
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_MALFORMED
    assert "## Risks" in classification[plan.id].detail


@pytest.mark.parametrize(
    ("status", "expected_state"),
    [("current", DRAFT_SEED_STATE_MALFORMED), ("invalidated", DRAFT_SEED_STATE_STALE)],
)
def test_classify_unreadable_file_uses_sidecar_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    expected_state: str,
) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids)
    source = _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text, status=status)})
    original_read_text = Path.read_text

    def unreadable(path: Path, *args: object, **kwargs: object) -> str:
        if path == source:
            raise UnicodeDecodeError("utf-8", b"x", 0, 1, "invalid byte")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", unreadable)

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == expected_state


def test_path_escaping_takes_precedence_over_missing(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan()
    entry = _entry(plan, _seed_text(*plan.component_ids))
    entry["draft_seed_path"] = "../outside.md"
    _write_state(plans_dir, {plan.id: entry})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_PATH_ESCAPING
    assert "must not contain" in classification[plan.id].detail


def test_duplicate_takes_precedence_over_every_other_state(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    first = _plan("first")
    second = _plan("second")

    classification = classify_draft_seeds(
        _artifact(first, second), plans_dir=plans_dir, slug=SLUG
    )

    assert {item.state for item in classification.values()} == {DRAFT_SEED_STATE_DUPLICATE}
    assert "second" in classification["first"].detail
    assert "first" in classification["second"].detail


def test_classify_accepts_legacy_seed_paths(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan(draft_seed_path="seeds/slice.md")
    text = _seed_text(*plan.component_ids)
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})

    classification = classify_draft_seeds(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert classification[plan.id].state == DRAFT_SEED_STATE_CURRENT


def test_classification_returns_every_plan_and_never_writes(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    first = _plan("first", draft_seed_path="plan-seed-drafts/first.md")
    second = _plan("second", draft_seed_path="plan-seed-drafts/second.md")
    first_text = _seed_text(*first.component_ids)
    second_text = _seed_text(*second.component_ids)
    first_source = _write_seed(plans_dir, first, first_text)
    second_source = _write_seed(plans_dir, second, second_text)
    state_path = _write_state(
        plans_dir,
        {first.id: _entry(first, first_text), second.id: _entry(second, second_text)},
    )
    before_bytes = {
        path: path.read_bytes() for path in (state_path, first_source, second_source)
    }
    before_mtimes = {path: path.stat().st_mtime_ns for path in before_bytes}

    classification = classify_draft_seeds(
        _artifact(first, second), plans_dir=plans_dir, slug=SLUG
    )

    assert set(classification) == {"first", "second"}
    assert {path: path.read_bytes() for path in before_bytes} == before_bytes
    assert {path: path.stat().st_mtime_ns for path in before_mtimes} == before_mtimes


def test_precedence_constant_matches_the_documented_order() -> None:
    assert DRAFT_SEED_STATE_PRECEDENCE == (
        DRAFT_SEED_STATE_DUPLICATE,
        DRAFT_SEED_STATE_PATH_ESCAPING,
        DRAFT_SEED_STATE_MISSING,
        DRAFT_SEED_STATE_DIGEST_MISMATCHED,
        DRAFT_SEED_STATE_STALE,
        DRAFT_SEED_STATE_MALFORMED,
        DRAFT_SEED_STATE_CURRENT,
    )


def test_sidecar_entry_naming_no_plan_row_is_an_orphan(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan("current")
    retired = _plan("retired")
    _write_state(plans_dir, {retired.id: _entry(retired, _seed_text("component-a"))})

    records = find_orphan_seed_records(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert len(records) == 1
    assert records[0].kind == ORPHAN_SEED_RECORD_SIDECAR_ENTRY
    assert records[0].plan_id == retired.id
    assert records[0].path is None


def test_file_in_the_draft_dir_no_plan_row_names_is_an_orphan(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan("current")
    source = _root(plans_dir) / "plan-seed-drafts" / "orphan.md"
    source.parent.mkdir(parents=True)
    source.write_text("orphan\n", encoding="utf-8")

    records = find_orphan_seed_records(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert len(records) == 1
    assert records[0].kind == ORPHAN_SEED_RECORD_FILE
    assert records[0].path == source


def test_file_in_the_legacy_seeds_dir_is_scanned_too(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    source = _root(plans_dir) / "seeds" / "orphan.md"
    source.parent.mkdir(parents=True)
    source.write_text("orphan\n", encoding="utf-8")

    records = find_orphan_seed_records(_artifact(), plans_dir=plans_dir, slug=SLUG)

    assert [(record.kind, record.path) for record in records] == [
        (ORPHAN_SEED_RECORD_FILE, source)
    ]


def test_legacy_prefix_plan_row_owns_its_legacy_file(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    plan = _plan(draft_seed_path="seeds/slice.md")
    _write_seed(plans_dir, plan, _seed_text(*plan.component_ids))

    records = find_orphan_seed_records(_artifact(plan), plans_dir=plans_dir, slug=SLUG)

    assert records == ()


def test_archive_subdirectory_is_skipped(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    archive = _root(plans_dir) / "plan-seed-drafts" / "archive"
    archive.mkdir(parents=True)
    (archive / "orphan.replaced.1.md").write_text("history\n", encoding="utf-8")

    records = find_orphan_seed_records(_artifact(), plans_dir=plans_dir, slug=SLUG)

    assert records == ()


def test_no_sidecar_and_missing_or_empty_draft_dirs_produce_no_orphans(
    tmp_path: Path,
) -> None:
    plans_dir = tmp_path / "plans"
    _root(plans_dir).mkdir(parents=True)

    records = find_orphan_seed_records(_artifact(), plans_dir=plans_dir, slug=SLUG)

    assert records == ()


def test_orphan_records_come_back_in_deterministic_order(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    retired_z = _plan("retired-z")
    retired_a = _plan("retired-a")
    _write_state(
        plans_dir,
        {
            retired_z.id: _entry(retired_z, _seed_text("component-a")),
            retired_a.id: _entry(retired_a, _seed_text("component-a")),
        },
    )
    for dirname, names in (("plan-seed-drafts", ("z.md", "a.md")), ("seeds", ("b.md",))):
        directory = _root(plans_dir) / dirname
        directory.mkdir(parents=True, exist_ok=True)
        for name in names:
            (directory / name).write_text("orphan\n", encoding="utf-8")

    records = find_orphan_seed_records(_artifact(), plans_dir=plans_dir, slug=SLUG)

    assert [(record.plan_id, record.path) for record in records] == [
        ("retired-a", None),
        ("retired-z", None),
        (None, _root(plans_dir) / "plan-seed-drafts" / "a.md"),
        (None, _root(plans_dir) / "plan-seed-drafts" / "z.md"),
        (None, _root(plans_dir) / "seeds" / "b.md"),
    ]


def test_unusable_sidecar_propagates_matching_the_classifier_stance(
    tmp_path: Path,
) -> None:
    plans_dir = tmp_path / "plans"
    path = seed_state_path(_root(plans_dir))
    path.parent.mkdir(parents=True)
    path.write_text("not json", encoding="utf-8")

    with pytest.raises(RoadmapSeedStateError):
        find_orphan_seed_records(_artifact(), plans_dir=plans_dir, slug=SLUG)


def test_classify_draft_seeds_accepts_a_version_parsed_plans_artifact(tmp_path: Path) -> None:
    """Classification needs only the parsed artifact, never a stage file on disk."""
    plans_dir = tmp_path / "plans"
    plan = _plan()
    text = _seed_text(*plan.component_ids)
    _write_seed(plans_dir, plan, text)
    _write_state(plans_dir, {plan.id: _entry(plan, text)})
    parsed = parse_plans_artifact(render_plans_artifact(_artifact(plan)))

    classification = classify_draft_seeds(parsed, plans_dir=plans_dir, slug=SLUG)

    assert not (_root(plans_dir) / PLANS_FILENAME).exists()
    assert classification[plan.id].state == DRAFT_SEED_STATE_CURRENT
