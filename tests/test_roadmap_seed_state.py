"""Lifecycle state discovery for direct, promoted, and archived roadmap seeds."""

from __future__ import annotations

import os
import json
from pathlib import Path

import pytest

from plan_tool.cli.authoring import _confirm_invalidated_roadmap_seed
from plan_tool.roadmap_artifacts import (
    PlanDisposition,
    PlanRow,
    PlansArtifact,
    render_plans_artifact,
)
from plan_tool.roadmap_versions import accepted_head_path
from tests.roadmap_accepted_fixtures import publish_accepted_root, with_minimal_upstream
from plan_tool.roadmap_seed_state import (
    digest_text,
    empty_seed_state,
    invalidated_seed_state,
    invalidated_seed_continuation,
    locate_tracked_seed,
    render_seed_state_marker,
    snapshot_seed_state,
    seed_state_path,
    write_seed_state,
)


def _write_invalidated_state(
    root: Path, *, draft_seed_dirname: str = "seeds", status: str = "invalidated"
) -> Path:
    path = seed_state_path(root)
    state = empty_seed_state()
    state["seeds"]["slice"] = {
        "draft_seed_path": f"{draft_seed_dirname}/slice.md",
        "status": status,
        "digest": digest_text("# seed\n"),
        "published": False,
    }
    write_seed_state(path, state)
    artifact = PlansArtifact(
        plans=(
            PlanRow(
                id="slice",
                title="Slice",
                disposition=PlanDisposition.KEEP,
                component_ids=(),
                draft_seed_path=f"{draft_seed_dirname}/slice.md",
                sizing_rationale="Keeps one bounded concern together.",
            ),
        ),
        ordering=(),
        assumptions=(),
        decisions=(),
        body="# Roadmap\n",
    )
    publish_accepted_root(
        root.parent.parent,
        root.name,
        with_minimal_upstream(render_plans_artifact(artifact)),
    )
    return path


def test_write_seed_state_fsyncs_before_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_path = tmp_path / "seed-state.json"
    events: list[str] = []
    real_replace = os.replace

    def fsync(_descriptor: int) -> None:
        events.append("fsync")

    def replace(source, destination) -> None:
        assert events == ["fsync"]
        events.append("replace")
        real_replace(source, destination)

    monkeypatch.setattr("plan_tool.roadmap_seed_state.os.fsync", fsync)
    monkeypatch.setattr("plan_tool.roadmap_seed_state.os.replace", replace)

    write_seed_state(state_path, empty_seed_state())

    assert events == ["fsync", "replace"]


def test_direct_draft_and_its_archive_require_stale_seed_confirmation(
    tmp_path: Path,
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root)
    direct = roadmap_root / "seeds" / "slice.md"
    direct.parent.mkdir()
    direct.write_text("# seed\n", encoding="utf-8")

    current = invalidated_seed_continuation(direct, repo_root=tmp_path)
    assert current is not None
    assert current.plan_id == "slice"
    assert current.state_path == state_path

    archived = direct.parent / "archive" / "slice.replaced.md"
    archived.parent.mkdir()
    archived.write_text("# prior seed\n", encoding="utf-8")
    direct.unlink()
    assert invalidated_seed_continuation(archived, repo_root=tmp_path) == current


def test_renamed_direct_draft_and_archive_require_stale_seed_confirmation(
    tmp_path: Path,
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(
        roadmap_root, draft_seed_dirname="plan-seed-drafts"
    )
    direct = roadmap_root / "plan-seed-drafts" / "slice.md"
    direct.parent.mkdir()
    direct.write_text("# seed\n", encoding="utf-8")

    current = invalidated_seed_continuation(direct, repo_root=tmp_path)
    assert current is not None
    assert current.plan_id == "slice"
    assert current.state_path == state_path

    archived = direct.parent / "archive" / "slice.replaced.md"
    archived.parent.mkdir()
    archived.write_text("# prior seed\n", encoding="utf-8")
    direct.unlink()
    assert invalidated_seed_continuation(archived, repo_root=tmp_path) == current


def test_promoted_seed_marker_survives_its_archive_move(tmp_path: Path) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root)
    promoted = tmp_path / "plan-seeds" / "slice.md"
    promoted.parent.mkdir()
    promoted.write_text(
        "# seed\n\n"
        + render_seed_state_marker(
            state_path=state_path,
            repo_root=tmp_path,
            roadmap_slug="demo",
            plan_id="slice",
        )
        + "\n",
        encoding="utf-8",
    )

    current = invalidated_seed_continuation(promoted, repo_root=tmp_path)
    assert current is not None
    archived = promoted.parent / "archive" / "slice.replaced.md"
    archived.parent.mkdir()
    promoted.replace(archived)
    assert invalidated_seed_continuation(archived, repo_root=tmp_path) == current


def test_promoted_seed_needs_no_confirmation_once_its_draft_is_archived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root, status="current")
    promoted = tmp_path / "plan-seeds" / "slice.md"
    promoted.parent.mkdir()
    promoted.write_text(
        "# seed\n\n"
        + render_seed_state_marker(
            state_path=state_path,
            repo_root=tmp_path,
            roadmap_slug="demo",
            plan_id="slice",
        )
        + "\n",
        encoding="utf-8",
    )
    # The originating draft never existed on disk here — simulating
    # ``create --archive`` having moved or removed it after promotion.
    monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)

    assert _confirm_invalidated_roadmap_seed(
        locate_tracked_seed(promoted, repo_root=tmp_path),
        yes=False,
        input_fn=lambda _prompt: "n",
    )


def test_promoted_seed_still_requires_assent_when_invalidated_after_draft_archived(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root, status="invalidated")
    promoted = tmp_path / "plan-seeds" / "slice.md"
    promoted.parent.mkdir()
    promoted.write_text(
        "# seed\n\n"
        + render_seed_state_marker(
            state_path=state_path,
            repo_root=tmp_path,
            roadmap_slug="demo",
            plan_id="slice",
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)

    location = locate_tracked_seed(promoted, repo_root=tmp_path)
    assert not _confirm_invalidated_roadmap_seed(
        location, yes=False, input_fn=lambda _prompt: "n"
    )
    assert _confirm_invalidated_roadmap_seed(
        location, yes=True, input_fn=lambda _prompt: "n"
    )


def test_corrupt_accepted_head_is_an_error_message_not_a_traceback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    _write_invalidated_state(roadmap_root)
    source = roadmap_root / "seeds" / "slice.md"
    source.parent.mkdir()
    source.write_text("# seed\n", encoding="utf-8")
    accepted_head_path(roadmap_root.parent.parent, "demo").write_text("{not json", encoding="utf-8")
    monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)

    assert not _confirm_invalidated_roadmap_seed(
        locate_tracked_seed(source, repo_root=tmp_path), yes=True, input_fn=lambda _prompt: "yes"
    )
    assert capsys.readouterr().err.strip()


def test_create_requires_an_explicit_assent_for_an_invalidated_seed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    _write_invalidated_state(roadmap_root)
    source = roadmap_root / "seeds" / "slice.md"
    source.parent.mkdir()
    source.write_text("# seed\n", encoding="utf-8")
    monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)

    location = locate_tracked_seed(source, repo_root=tmp_path)
    assert not _confirm_invalidated_roadmap_seed(
        location, yes=False, input_fn=lambda _prompt: "n"
    )
    assert _confirm_invalidated_roadmap_seed(
        location, yes=False, input_fn=lambda _prompt: "yes"
    )
    assert _confirm_invalidated_roadmap_seed(
        location, yes=True, input_fn=lambda _prompt: "n"
    )


def test_create_requires_assent_for_an_invalidated_seed_in_renamed_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    _write_invalidated_state(roadmap_root, draft_seed_dirname="plan-seed-drafts")
    source = roadmap_root / "plan-seed-drafts" / "slice.md"
    source.parent.mkdir()
    source.write_text("# seed\n", encoding="utf-8")
    monkeypatch.setattr("plan_tool.cli.authoring.sys.stdin.isatty", lambda: True)

    location = locate_tracked_seed(source, repo_root=tmp_path)
    assert not _confirm_invalidated_roadmap_seed(
        location, yes=False, input_fn=lambda _prompt: "n"
    )
    assert _confirm_invalidated_roadmap_seed(
        location, yes=False, input_fn=lambda _prompt: "yes"
    )


def test_locate_tracked_seed_finds_a_direct_draft_regardless_of_status(
    tmp_path: Path,
) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root, status="current")
    source = roadmap_root / "seeds" / "slice.md"
    source.parent.mkdir()
    source.write_text("# seed\n", encoding="utf-8")

    location = locate_tracked_seed(source, repo_root=tmp_path)

    assert location is not None
    assert location.plan_id == "slice"
    assert location.roadmap_slug == "demo"
    assert location.state_path == state_path
    assert invalidated_seed_continuation(source, repo_root=tmp_path) is None


def test_locate_tracked_seed_finds_an_archived_current_draft(tmp_path: Path) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root, status="current")
    source = roadmap_root / "seeds" / "archive" / "slice.replaced.md"
    source.parent.mkdir(parents=True)
    source.write_text("# seed\n", encoding="utf-8")

    location = locate_tracked_seed(source, repo_root=tmp_path)

    assert location is not None
    assert location.state_path == state_path


def test_locate_tracked_seed_finds_a_promoted_current_copy(tmp_path: Path) -> None:
    roadmap_root = tmp_path / "docs" / "implementation-plans" / "roadmaps" / "demo"
    state_path = _write_invalidated_state(roadmap_root, status="current")
    source = tmp_path / "plan-seeds" / "slice.md"
    source.parent.mkdir()
    source.write_text(
        "# seed\n\n"
        + render_seed_state_marker(
            state_path=state_path,
            repo_root=tmp_path,
            roadmap_slug="demo",
            plan_id="slice",
        )
        + "\n",
        encoding="utf-8",
    )

    location = locate_tracked_seed(source, repo_root=tmp_path)

    assert location is not None
    assert location.plan_id == "slice"
    assert location.roadmap_slug == "demo"


def test_locate_tracked_seed_returns_none_for_an_untracked_file(tmp_path: Path) -> None:
    source = tmp_path / "seed.md"
    source.write_text("# seed\n", encoding="utf-8")

    assert locate_tracked_seed(source, repo_root=tmp_path) is None


def test_seed_state_generation_snapshot_is_validated_and_independent() -> None:
    state = empty_seed_state()
    state["seeds"]["slice"] = {
        "draft_seed_path": "seeds/slice.md",
        "status": "current",
        "digest": None,
        "published": False,
    }

    snapshot = snapshot_seed_state(state)
    invalidated = invalidated_seed_state(snapshot)
    invalidated["seeds"]["slice"]["published"] = True

    assert state["seeds"]["slice"] == {
        "draft_seed_path": "seeds/slice.md",
        "status": "current",
        "digest": None,
        "published": False,
    }
    assert snapshot["seeds"]["slice"]["status"] == "current"


def test_invalidation_refreshes_a_renamed_draft_seed_path() -> None:
    state = empty_seed_state()
    state["seeds"]["slice"] = {
        "draft_seed_path": "seeds/old-name.md",
        "status": "current",
        "digest": None,
        "published": False,
    }

    invalidated = invalidated_seed_state(
        state,
        draft_seed_paths={"slice": "seeds/current-name.md"},
    )

    assert invalidated["seeds"]["slice"]["draft_seed_path"] == "seeds/current-name.md"
    assert invalidated["seeds"]["slice"]["status"] == "invalidated"


@pytest.mark.parametrize("layout", ["root", "nested"])
def test_publication_layout_survives_state_roundtrip_and_invalidation(tmp_path, layout):
    path = _write_invalidated_state(tmp_path / "roadmap")
    state = snapshot_seed_state(json.loads(path.read_text()))
    state["seeds"]["slice"]["publication_layout"] = layout
    write_seed_state(path, state)
    reread = snapshot_seed_state(json.loads(path.read_text()))
    assert reread["seeds"]["slice"]["publication_layout"] == layout
    assert invalidated_seed_state(reread)["seeds"]["slice"]["publication_layout"] == layout


@pytest.mark.parametrize("layout", ["elsewhere", [], {}, 1, None])
def test_invalid_publication_layout_fails_closed(tmp_path, layout):
    from plan_tool.roadmap_seed_state import RoadmapSeedStateError
    path = _write_invalidated_state(tmp_path / "roadmap")
    state = json.loads(path.read_text())
    state["seeds"]["slice"]["publication_layout"] = layout
    with pytest.raises(RoadmapSeedStateError, match="publication layout"):
        snapshot_seed_state(state)
