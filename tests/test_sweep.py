"""Tests for plan_tool.sweep + plan-tool sweep CLI."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from plan_tool.cli import main
from plan_tool.locator import collect_plan_entries
from plan_tool.parser import parse_plan
from plan_tool.detail_artifacts import locate_detail_format_carrier
from plan_tool.sweep import (
    archive_completed_plan,
    classify_plan,
    compute_step_counts,
    discover_orphan_plans,
    sweep_plans,
    withdraw_plan,
)


def _plan_text(
    *,
    status: str = "planning",
    step_statuses: list[str] | None = None,
    title: str = "Test Plan",
) -> str:
    """Build a YAML-frontmatter plan with parameterized status fields.

    Each entry in ``step_statuses`` becomes one step. Defaults to a
    single pending step so the common ``status: planning, 0/1`` case
    is one line at the call site. An entry of ``"deferred"`` or
    ``"wont_do"`` is emitted as a parked step (``scope:`` line, status
    left at the default ``pending``) rather than a lifecycle status.
    """
    statuses = step_statuses if step_statuses is not None else ["pending"]
    _scopes = {"deferred", "wont_do"}
    step_lines = []
    for i, s in enumerate(statuses, start=1):
        step_lines.append(f"  - id: {i}")
        step_lines.append(f"    title: Step {i}")
        if s in _scopes:
            step_lines.append(f"    scope: {s}")
        else:
            step_lines.append(f"    status: {s}")
    return (
        "---\n"
        f"title: {title}\n"
        f"status: {status}\n"
        "priority: low\n"
        "steps:\n"
        + "\n".join(step_lines) + "\n"
        "---\n"
        "# Body\n"
    )


def _seed_repo(
    tmp_path: Path,
    *,
    plans: dict[str, str] | None = None,
) -> tuple[Path, Path, Path]:
    """Build a hermetic repo with a ``.git`` marker, plans dir, manifest.

    ``plans`` maps relative filename → file body. Every key is added
    to the manifest as ``plans/<name>``. Returns
    ``(repo_root, plans_dir, manifest_path)``.
    """
    (tmp_path / ".git").mkdir()
    plans_dir = tmp_path / "plans"
    plans_dir.mkdir()
    manifest = tmp_path / "m.json"
    rel_entries: list[str] = []
    for name, body in (plans or {}).items():
        (plans_dir / name).write_text(body, encoding="utf-8")
        rel_entries.append(f"plans/{name}")
    manifest.write_text(json.dumps({"plans": rel_entries}), encoding="utf-8")
    return tmp_path, plans_dir, manifest


# ---------- compute_step_counts ----------


def test_compute_step_counts_tallies_each_status(tmp_path: Path) -> None:
    """Each bucket is counted independently; total = sum. Parked steps land
    in ``deferred`` and are excluded from the committed ``pending`` tally."""
    body = _plan_text(
        step_statuses=["done", "done", "current", "pending", "deferred"]
    )
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    plan = parse_plan(path)
    counts = compute_step_counts(plan)
    assert counts.total == 5
    assert counts.done == 2
    assert counts.current == 1
    assert counts.pending == 1
    assert counts.deferred == 1


def test_compute_step_counts_percent_done_rounds(tmp_path: Path) -> None:
    """percent_done uses round-half-to-even (Python default)."""
    body = _plan_text(step_statuses=["done"] * 2 + ["pending"])  # 2/3
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    plan = parse_plan(path)
    counts = compute_step_counts(plan)
    assert counts.percent_done == 67  # round(66.666...) = 67


# ---------- classify_plan ----------


def test_classify_completed_requires_both_status_and_all_steps(
    tmp_path: Path,
) -> None:
    """Strict AND rule: status=completed AND every step done → completed."""
    body = _plan_text(status="completed", step_statuses=["done", "done"])
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    [entry] = collect_plan_entries([path])
    c = classify_plan(entry)
    assert c.completed is True
    assert c.counts is not None
    assert c.counts.done == 2 == c.counts.total


def test_classify_status_completed_but_step_pending_not_completed(
    tmp_path: Path,
) -> None:
    """Top-level status: completed alone doesn't qualify when a step is pending."""
    body = _plan_text(
        status="completed", step_statuses=["done", "pending"]
    )
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    [entry] = collect_plan_entries([path])
    c = classify_plan(entry)
    assert c.completed is False


def test_classify_all_steps_done_but_status_planning_not_completed(
    tmp_path: Path,
) -> None:
    """All steps done with top-level status: planning stays in partial.

    This is the common case where the author finished the work but
    hasn't promoted the top-level status yet — sweep should surface
    it as 100% partial, not silently archive.
    """
    body = _plan_text(status="planning", step_statuses=["done", "done"])
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    [entry] = collect_plan_entries([path])
    c = classify_plan(entry)
    assert c.completed is False
    assert c.counts is not None
    assert c.counts.percent_done == 100


def test_classify_malformed_plan_returns_none_counts(tmp_path: Path) -> None:
    """Plans that fail validation appear as malformed (counts=None)."""
    # Frontmatter missing required fields → ValidationError surfaces in
    # PlanEntry.error and plan=None.
    path = tmp_path / "bad.md"
    path.write_text(
        "---\npriority: low\n---\n", encoding="utf-8"
    )
    entries = collect_plan_entries([path])
    # Could be 0 entries (ParseError) or 1 entry with plan=None
    # (ValidationError). Either way we don't archive it; the report
    # surfaces malformed ones.
    if not entries:
        pytest.skip("ParseError fixture variant; covered elsewhere")
    c = classify_plan(entries[0])
    assert c.completed is False
    assert c.counts is None
    assert c.parse_error is not None


def test_classify_records_in_progress_step_titles(tmp_path: Path) -> None:
    """Steps with status: current bubble their titles into the report."""
    body = (
        "---\n"
        "title: Test\n"
        "status: planning\n"
        "priority: low\n"
        "steps:\n"
        "  - id: 1\n"
        "    title: Done step\n"
        "    status: done\n"
        "  - id: 2\n"
        "    title: Active step\n"
        "    status: current\n"
        "---\n"
        "# Body\n"
    )
    path = tmp_path / "p.md"
    path.write_text(body, encoding="utf-8")
    [entry] = collect_plan_entries([path])
    c = classify_plan(entry)
    assert c.in_progress_titles == ["Active step"]


# ---------- archive_completed_plan ----------


def test_archive_moves_file_and_deregisters(tmp_path: Path) -> None:
    """Happy path: file moves to archive/, manifest entry removed."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    [entry] = collect_plan_entries([plans_dir / "1-done.md"])
    c = classify_plan(entry)
    outcome = archive_completed_plan(
        c,
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 5, 20),
    )
    archived_path = plans_dir / "archive" / "1-done.md"
    assert outcome.archived_to == archived_path
    assert archived_path.is_file()
    assert not (plans_dir / "1-done.md").exists()
    assert outcome.deregistered is True
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "plans/1-done.md" not in data["plans"]
    # Archive notice was prepended.
    body = archived_path.read_text(encoding="utf-8")
    assert "Auto-archived" in body
    assert "2026-05-20" in body


def test_archive_collision_dedupes_target_and_deregisters(tmp_path: Path) -> None:
    """An existing archive target no longer halts the move: the plan is
    archived to a deduplicated name and the manifest entry is removed, so
    no entry is left dangling (BUG_BACKLOG: collision skipped deregister).
    """
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    archive_dir = plans_dir / "archive"
    archive_dir.mkdir()
    (archive_dir / "1-done.md").write_text("pre-existing\n", encoding="utf-8")

    [entry] = collect_plan_entries([plans_dir / "1-done.md"])
    c = classify_plan(entry)
    outcome = archive_completed_plan(
        c, manifest_path=manifest, repo_root=repo
    )

    # Archived to a deduplicated path; the prior archive is untouched.
    assert outcome.archived_to == archive_dir / "1-done.2.md"
    assert (archive_dir / "1-done.2.md").is_file()
    assert (
        archive_dir / "1-done.md"
    ).read_text(encoding="utf-8") == "pre-existing\n"
    assert any("already exists" in s for s in outcome.skipped)
    # Source moved out of plans/ and the manifest entry deregistered.
    assert not (plans_dir / "1-done.md").exists()
    assert outcome.deregistered is True
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "plans/1-done.md" not in data["plans"]


def test_archive_moves_plan_details(tmp_path: Path) -> None:
    """plan-details/<slug>/ moves alongside the plan into archive/plan-details/<slug>/."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    details_dir = plans_dir / "plan-details" / "done"
    details_dir.mkdir(parents=True)
    (details_dir / "01-step.md").write_text(
        "# step detail\n", encoding="utf-8"
    )

    [entry] = collect_plan_entries([plans_dir / "1-done.md"])
    c = classify_plan(entry)
    outcome = archive_completed_plan(
        c,
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 5, 20),
    )
    moved = plans_dir / "archive" / "plan-details" / "done" / "01-step.md"
    assert moved.is_file()
    assert "Auto-archived" in moved.read_text(encoding="utf-8")
    assert not details_dir.exists()  # source removed after move
    assert any(
        dst.name == "01-step.md" for _src, dst in outcome.plan_details_moved
    )


def test_archived_detail_snapshot_has_no_run_grade_carrier(
    tmp_path: Path,
) -> None:
    """The archive breadcrumb prepended ahead of the H1 puts the archived
    snapshot outside the live run-grade format-version carrier — this is a
    deliberate exemption (the writer never re-touches an archived file), not
    a change to ``_archive_plan_details`` itself."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    details_dir = plans_dir / "plan-details" / "done"
    details_dir.mkdir(parents=True)
    run_grade_body = (
        "# Step 1 — Wire up the renderer\n\n"
        "<!-- plan-tool:detail-format-version: 1 -->\n\n"
        "## Summary\n\nDone.\n"
    )
    (details_dir / "01-step.md").write_text(run_grade_body, encoding="utf-8")
    assert locate_detail_format_carrier(run_grade_body) is not None

    [entry] = collect_plan_entries([plans_dir / "1-done.md"])
    c = classify_plan(entry)
    archive_completed_plan(
        c, manifest_path=manifest, repo_root=repo, today=date(2026, 5, 20),
    )

    archived_text = (
        plans_dir / "archive" / "plan-details" / "done" / "01-step.md"
    ).read_text(encoding="utf-8")
    assert locate_detail_format_carrier(archived_text) is None


def test_archive_plan_details_decollides_to_paired_suffix(
    tmp_path: Path,
) -> None:
    """A same-slug re-creation ("take 2") archives its details to the
    suffixed ``<slug>.N/`` paired with the plan file, never stranding
    the live directory.

    Regression: ``_archive_plan_details`` used to *skip* on a collision
    while the plan-file path de-collided with a numeric suffix, leaving
    the live ``plan-details/<slug>/`` orphaned in the working tree.
    """
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"2-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    # A prior same-name plan + its details already sit in the archive
    # (the "take 1" that this plan supersedes).
    archive = plans_dir / "archive"
    (archive).mkdir()
    (archive / "2-done.md").write_text("# take 1\n", encoding="utf-8")
    prior_details = archive / "plan-details" / "done"
    prior_details.mkdir(parents=True)
    (prior_details / "01-step.md").write_text(
        "# take 1 detail\n", encoding="utf-8"
    )

    details_dir = plans_dir / "plan-details" / "done"
    details_dir.mkdir(parents=True)
    (details_dir / "01-step.md").write_text(
        "# take 2 detail\n", encoding="utf-8"
    )

    [entry] = collect_plan_entries([plans_dir / "2-done.md"])
    c = classify_plan(entry)
    outcome = archive_completed_plan(
        c,
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 5, 20),
    )

    # Plan file de-collided to .2; details paired at done.2/.
    assert outcome.archived_to == archive / "2-done.2.md"
    paired = archive / "plan-details" / "done.2" / "01-step.md"
    assert paired.is_file()
    assert "take 2 detail" in paired.read_text(encoding="utf-8")
    assert "Auto-archived" in paired.read_text(encoding="utf-8")
    # Live directory is gone — not stranded.
    assert not details_dir.exists()
    # Take 1's details are untouched.
    assert (prior_details / "01-step.md").read_text(
        encoding="utf-8"
    ) == "# take 1 detail\n"
    assert outcome.plan_details_moved


def test_archive_plan_details_decollides_when_only_details_collide(
    tmp_path: Path,
) -> None:
    """Details de-collide independently when the plan *file* name does
    not collide (no paired suffix to inherit) — next-free ``<slug>.2/``.
    """
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"2-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    archive = plans_dir / "archive"
    prior_details = archive / "plan-details" / "done"
    prior_details.mkdir(parents=True)
    (prior_details / "01-step.md").write_text("# prior\n", encoding="utf-8")

    details_dir = plans_dir / "plan-details" / "done"
    details_dir.mkdir(parents=True)
    (details_dir / "01-step.md").write_text("# fresh\n", encoding="utf-8")

    [entry] = collect_plan_entries([plans_dir / "2-done.md"])
    c = classify_plan(entry)
    outcome = archive_completed_plan(
        c,
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 5, 20),
    )

    # Plan file did not collide — keeps its bare name.
    assert outcome.archived_to == archive / "2-done.md"
    moved = archive / "plan-details" / "done.2" / "01-step.md"
    assert moved.is_file()
    assert "fresh" in moved.read_text(encoding="utf-8")
    assert not details_dir.exists()


class TestArchivePlanDetailsAtomicity:
    """``_archive_plan_details`` is all-or-nothing under mid-loop failure.

    Pins the stage-then-rename contract: per-file writes happen under
    a sibling ``<details_dst.name>.tmp`` directory and the visible
    archive only appears after a single ``os.replace``. A mid-loop
    ``OSError`` removes the staging directory, leaves the source
    intact, and records the failure on ``outcome.skipped`` — never a
    half-archived mix.
    """

    @staticmethod
    def _seed(tmp_path: Path) -> tuple[Path, Path, Path, Path]:
        """Build a completed plan with three plan-details files."""
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-done.md": _plan_text(
                status="completed", step_statuses=["done"]
            )},
        )
        details_src = plans_dir / "plan-details" / "done"
        details_src.mkdir(parents=True)
        (details_src / "01-step.md").write_text(
            "# step 1\n", encoding="utf-8"
        )
        (details_src / "02-step.md").write_text(
            "# step 2\n", encoding="utf-8"
        )
        (details_src / "03-step.md").write_text(
            "# step 3\n", encoding="utf-8"
        )
        return repo, plans_dir, manifest, details_src

    def test_mid_loop_oserror_leaves_no_half_archived_state(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo, plans_dir, manifest, details_src = self._seed(tmp_path)
        staging_dir = plans_dir / "archive" / "plan-details" / "done.tmp"
        final_dir = plans_dir / "archive" / "plan-details" / "done"

        original_write_text = Path.write_text
        call_count = {"n": 0}

        def flaky_write_text(
            self: Path, data: str, *args: object, **kwargs: object
        ) -> int:
            # Only count writes that target the staging dir — the plan
            # file itself (archived just before _archive_plan_details
            # runs) is also a write_text call, and we don't want to
            # raise on it.
            try:
                self.relative_to(staging_dir)
            except ValueError:
                return original_write_text(self, data, *args, **kwargs)
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise OSError("disk full")
            return original_write_text(self, data, *args, **kwargs)

        monkeypatch.setattr(Path, "write_text", flaky_write_text)

        [entry] = collect_plan_entries([plans_dir / "1-done.md"])
        c = classify_plan(entry)
        outcome = archive_completed_plan(
            c,
            manifest_path=manifest,
            repo_root=repo,
            today=date(2026, 5, 20),
        )

        assert outcome.plan_details_moved == []
        assert any(
            "could not archive plan-details" in s for s in outcome.skipped
        )
        # Staging dir cleaned up; final destination never published.
        assert not staging_dir.exists()
        assert not final_dir.exists()
        # Source intact, byte-for-byte.
        assert (details_src / "01-step.md").read_text(
            encoding="utf-8"
        ) == "# step 1\n"
        assert (details_src / "02-step.md").read_text(
            encoding="utf-8"
        ) == "# step 2\n"
        assert (details_src / "03-step.md").read_text(
            encoding="utf-8"
        ) == "# step 3\n"

    def test_successful_archive_publishes_via_staging_dir(
        self, tmp_path: Path
    ) -> None:
        repo, plans_dir, manifest, details_src = self._seed(tmp_path)
        staging_dir = plans_dir / "archive" / "plan-details" / "done.tmp"
        final_dir = plans_dir / "archive" / "plan-details" / "done"

        [entry] = collect_plan_entries([plans_dir / "1-done.md"])
        c = classify_plan(entry)
        outcome = archive_completed_plan(
            c,
            manifest_path=manifest,
            repo_root=repo,
            today=date(2026, 5, 20),
        )

        # Staging dir cleaned up after os.replace; final dir holds all files.
        assert not staging_dir.exists()
        assert (final_dir / "01-step.md").is_file()
        assert (final_dir / "02-step.md").is_file()
        assert (final_dir / "03-step.md").is_file()
        # Source removed.
        assert not details_src.exists()
        # plan_details_moved reports post-rename destinations, not staging.
        assert len(outcome.plan_details_moved) == 3
        for _src, dst in outcome.plan_details_moved:
            assert dst.parent == final_dir
            # Sanity: the staging path is NOT what got recorded.
            assert ".tmp" not in str(dst)

    def test_pre_existing_staging_dir_is_cleared_before_use(
        self, tmp_path: Path
    ) -> None:
        repo, plans_dir, manifest, details_src = self._seed(tmp_path)
        staging_dir = plans_dir / "archive" / "plan-details" / "done.tmp"
        final_dir = plans_dir / "archive" / "plan-details" / "done"

        # Simulate a SIGKILL'd prior run leaving a stray file behind.
        staging_dir.mkdir(parents=True)
        stray = staging_dir / "leftover.md"
        stray.write_text("stale\n", encoding="utf-8")

        [entry] = collect_plan_entries([plans_dir / "1-done.md"])
        c = classify_plan(entry)
        archive_completed_plan(
            c,
            manifest_path=manifest,
            repo_root=repo,
            today=date(2026, 5, 20),
        )

        # Stray file gone; only the three real files at the destination.
        assert not staging_dir.exists()
        assert not stray.exists()
        assert (final_dir / "01-step.md").is_file()
        assert (final_dir / "02-step.md").is_file()
        assert (final_dir / "03-step.md").is_file()
        assert not (final_dir / "leftover.md").exists()


# ---------- withdraw_plan ----------


def test_withdraw_moves_file_with_withdrawn_marker_and_deregisters(
    tmp_path: Path,
) -> None:
    """Happy path: file moves to archive/<stem>.withdrawn.md with the reason
    and date in its header, and the manifest entry is removed."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path, plans={"1-foo.md": _plan_text()}
    )
    outcome = withdraw_plan(
        plans_dir / "1-foo.md",
        slug="foo",
        reason="premise disproved by replay",
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 8, 8),
    )
    archived_path = plans_dir / "archive" / "1-foo.withdrawn.md"
    assert outcome.archived_to == archived_path
    assert archived_path.is_file()
    assert not (plans_dir / "1-foo.md").exists()
    assert outcome.deregistered is True
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert "plans/1-foo.md" not in data["plans"]

    body = archived_path.read_text(encoding="utf-8")
    assert "Withdrawn 2026-08-08" in body
    assert "premise disproved by replay" in body
    # Distinct wording from the completed-sweep notice — a reader must be
    # able to tell abandonment from completion at a glance.
    assert "Auto-archived" not in body


def test_withdraw_moves_plan_details_with_reason_notice(
    tmp_path: Path,
) -> None:
    """plan-details/<slug>/ moves alongside the plan, bare (no .withdrawn
    marker on the directory — only the plan file carries it), and each
    markdown file gets the same withdrawal notice as the plan."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path, plans={"1-foo.md": _plan_text()}
    )
    details_dir = plans_dir / "plan-details" / "foo"
    details_dir.mkdir(parents=True)
    (details_dir / "01-step.md").write_text(
        "# step detail\n", encoding="utf-8"
    )

    outcome = withdraw_plan(
        plans_dir / "1-foo.md",
        slug="foo",
        reason="carved wrong",
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 8, 8),
    )
    moved = plans_dir / "archive" / "plan-details" / "foo" / "01-step.md"
    assert moved.is_file()
    body = moved.read_text(encoding="utf-8")
    assert "Withdrawn 2026-08-08" in body
    assert "carved wrong" in body
    assert not details_dir.exists()
    assert any(
        dst.name == "01-step.md" for _src, dst in outcome.plan_details_moved
    )


def test_withdraw_collision_dedupes_target_and_deregisters(
    tmp_path: Path,
) -> None:
    """An existing <stem>.withdrawn.md target doesn't block the move — the
    plan archives to a deduplicated name and still deregisters, mirroring
    archive_completed_plan's own collision handling."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path, plans={"1-foo.md": _plan_text()}
    )
    archive_dir = plans_dir / "archive"
    archive_dir.mkdir()
    (archive_dir / "1-foo.withdrawn.md").write_text(
        "pre-existing\n", encoding="utf-8"
    )

    outcome = withdraw_plan(
        plans_dir / "1-foo.md",
        slug="foo",
        reason="second withdrawal of a same-named plan",
        manifest_path=manifest,
        repo_root=repo,
    )
    assert outcome.archived_to == archive_dir / "1-foo.withdrawn.2.md"
    assert (archive_dir / "1-foo.withdrawn.2.md").is_file()
    assert (
        archive_dir / "1-foo.withdrawn.md"
    ).read_text(encoding="utf-8") == "pre-existing\n"
    assert any("already exists" in s for s in outcome.skipped)
    assert not (plans_dir / "1-foo.md").exists()
    assert outcome.deregistered is True


def test_withdraw_nonexistent_plan_file_is_skipped(tmp_path: Path) -> None:
    """A plan file that's already gone is reported, not raised — mirrors
    archive_completed_plan's own missing-file handling."""
    repo, plans_dir, manifest = _seed_repo(tmp_path, plans={})
    outcome = withdraw_plan(
        plans_dir / "1-ghost.md",
        slug="ghost",
        reason="already deleted",
        manifest_path=manifest,
        repo_root=repo,
    )
    assert outcome.archived_to is None
    assert any("no longer exists" in s for s in outcome.skipped)


def test_withdraw_unregistered_plan_still_archives(tmp_path: Path) -> None:
    """A plan never registered (or already deregistered by hand) is still
    withdrawable — deregistered=False, not an error, matching deregister's
    own not-registered shape."""
    repo, plans_dir, manifest = _seed_repo(tmp_path, plans={})
    (plans_dir / "1-solo.md").write_text(_plan_text(), encoding="utf-8")
    outcome = withdraw_plan(
        plans_dir / "1-solo.md",
        slug="solo",
        reason="never registered",
        manifest_path=manifest,
        repo_root=repo,
    )
    assert outcome.archived_to is not None
    assert outcome.deregistered is False


# ---------- sweep_plans + cmd_sweep ----------


def test_sweep_plans_classifies_and_archives(tmp_path: Path) -> None:
    """End-to-end on the core: completed plans archived, partials reported."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={
            "1-done.md": _plan_text(
                status="completed", step_statuses=["done"]
            ),
            "2-active.md": _plan_text(
                status="planning",
                step_statuses=["done", "current", "pending"],
            ),
        },
    )
    entries = collect_plan_entries(
        [plans_dir / "1-done.md", plans_dir / "2-active.md"]
    )
    report = sweep_plans(
        entries,
        manifest_path=manifest,
        repo_root=repo,
        today=date(2026, 5, 20),
    )
    assert len(report.completed) == 1
    assert len(report.partial) == 1
    assert report.partial[0].entry.path.name == "2-active.md"
    assert report.archived[0].archived_to is not None
    # Manifest reflects the deregister.
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["plans"] == ["plans/2-active.md"]


def test_sweep_plans_dry_run_touches_nothing(tmp_path: Path) -> None:
    """Dry-run reports the would-be archive without moving disk state."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    entries = collect_plan_entries([plans_dir / "1-done.md"])
    report = sweep_plans(
        entries,
        manifest_path=manifest,
        repo_root=repo,
        dry_run=True,
    )
    assert report.dry_run is True
    assert len(report.archived) == 1
    assert report.archived[0].archived_to is not None  # planned target
    # Source still in place; manifest untouched.
    assert (plans_dir / "1-done.md").is_file()
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["plans"] == ["plans/1-done.md"]


def test_sweep_plans_report_only_skips_archive_pass(tmp_path: Path) -> None:
    """``archive=False`` reports without populating ``archived``."""
    repo, plans_dir, manifest = _seed_repo(
        tmp_path,
        plans={"1-done.md": _plan_text(
            status="completed", step_statuses=["done"]
        )},
    )
    entries = collect_plan_entries([plans_dir / "1-done.md"])
    report = sweep_plans(
        entries,
        manifest_path=manifest,
        repo_root=repo,
        archive=False,
    )
    assert report.archived == []
    assert len(report.completed) == 1
    # Disk state untouched.
    assert (plans_dir / "1-done.md").is_file()


@pytest.mark.integration
class TestCmdSweep:
    """End-to-end coverage for ``plan-tool sweep``."""

    def test_archives_completed_and_reports_partial(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={
                "1-done.md": _plan_text(
                    status="completed", step_statuses=["done"]
                ),
                "2-active.md": _plan_text(
                    status="planning", step_statuses=["pending"]
                ),
            },
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 archived" in out
        assert "1 partial" in out
        # Slug form (priority prefix stripped) appears in both sections.
        assert "done" in out
        assert "active" in out
        # Manifest reflects the deregister.
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-active.md"]
        # File moved to archive.
        assert (plans_dir / "archive" / "1-done.md").is_file()
        assert not (plans_dir / "1-done.md").exists()

    def test_dry_run_does_not_mutate(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-done.md": _plan_text(
                status="completed", step_statuses=["done"]
            )},
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--dry-run",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "would archive" in out
        # Filesystem and manifest unchanged.
        assert (plans_dir / "1-done.md").is_file()
        assert not (plans_dir / "archive").exists()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/1-done.md"]

    def test_report_only_skips_archive(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-done.md": _plan_text(
                status="completed", step_statuses=["done"]
            )},
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--report-only",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "report-only" in out
        # Archive pass skipped entirely.
        assert (plans_dir / "1-done.md").is_file()
        assert not (plans_dir / "archive").exists()

    def test_directory_mode_refused(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """sweep is manifest-mode only; --plans-dir should be rejected."""
        (tmp_path / ".git").mkdir()
        plans_dir = tmp_path / "plans"
        plans_dir.mkdir()
        rc = main([
            "--repo-root", str(tmp_path),
            "--plans-dir", str(plans_dir),
            "sweep",
        ])
        assert rc == 2
        err = capsys.readouterr().err
        assert "manifest-mode command" in err


def _add_missing_entry(manifest: Path, rel: str) -> None:
    """Append a manifest entry whose file was never created on disk."""
    data = json.loads(manifest.read_text(encoding="utf-8"))
    data["plans"].append(rel)
    manifest.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.integration
class TestCmdSweepMissing:
    """Coverage for the missing-entry prune offered by ``plan-tool sweep``."""

    def test_prunes_missing_with_yes(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-active.md": _plan_text(
                status="planning", step_statuses=["pending"]
            )},
        )
        _add_missing_entry(manifest, "plans/2-gone.md")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 missing" in out
        assert "removed 1 missing entry" in out
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/1-active.md"]

    def test_dry_run_previews_prune_but_keeps(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = _seed_repo(tmp_path, plans={})
        _add_missing_entry(manifest, "plans/2-gone.md")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--dry-run", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "would remove 1 missing entry" in out
        # Manifest untouched in dry-run.
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-gone.md"]

    def test_report_only_skips_prune(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest = _seed_repo(tmp_path, plans={})
        _add_missing_entry(manifest, "plans/2-gone.md")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--report-only", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "remove" not in out.lower()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-gone.md"]

    def test_non_interactive_without_yes_keeps_missing(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # pytest's captured stdin is not a TTY, so without -y the prune is
        # declined and a hint is printed — the manifest is left intact.
        repo, _plans_dir, manifest = _seed_repo(tmp_path, plans={})
        _add_missing_entry(manifest, "plans/2-gone.md")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "re-run with -y" in captured.err
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-gone.md"]

    def test_interactive_yes_prunes(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo, _plans_dir, manifest = _seed_repo(tmp_path, plans={})
        _add_missing_entry(manifest, "plans/2-gone.md")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "y")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "removed 1 missing entry" in out
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == []

    def test_interactive_no_keeps(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo, _plans_dir, manifest = _seed_repo(tmp_path, plans={})
        _add_missing_entry(manifest, "plans/2-gone.md")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        err = capsys.readouterr().err
        assert "kept" in err
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert data["plans"] == ["plans/2-gone.md"]


def _seed_nested_git_repo(
    tmp_path: Path,
    *,
    plans: dict[str, str] | None = None,
) -> tuple[Path, Path, Path, Path]:
    """Seed an outer repo with a nested ``.git`` checkout inside it.

    Mirrors the 2026-05-21 "skill bundle shipped as an independent
    git repo" layout: the outer repo has its own ``.git``, and a
    nested ``.git`` lives at ``<outer>/.agents/.git`` (mimicking the
    way ``.agents/`` is distributed as a standalone git checkout).
    The manifest is placed INSIDE the nested checkout at
    ``<outer>/.agents/skills/plan-tool/m.json`` — same location as
    the packaged default ``plan_tool/structured_plans.json`` — with
    entries repo-relative to the OUTER root. That's the shape that
    triggers the bug: walk-up from the manifest's parent halts at
    ``.agents/.git`` (not the outer ``.git``) and joins entries
    against the wrong root.

    Returns ``(outer, plans_dir, manifest, nested_cwd)`` where
    ``nested_cwd`` is the manifest's parent directory — the CWD
    that reproduces the original ``cd .agents/skills/plan-tool``
    invocation.
    """
    outer = tmp_path / "outer"
    outer.mkdir()
    (outer / ".git").mkdir()
    plans_dir = outer / "plans"
    plans_dir.mkdir()
    nested = outer / ".agents" / "skills" / "plan-tool"
    nested.mkdir(parents=True)
    (outer / ".agents" / ".git").mkdir()
    manifest = nested / "m.json"
    rel_entries: list[str] = []
    for name, body in (plans or {}).items():
        (plans_dir / name).write_text(body, encoding="utf-8")
        rel_entries.append(f"plans/{name}")
    manifest.write_text(json.dumps({"plans": rel_entries}), encoding="utf-8")
    return outer, plans_dir, manifest, nested


@pytest.mark.integration
class TestSweepUsesLocatorResolution:
    """The 2026-05-21 nested-``.git`` divergence — pinned.

    Before step 4, ``plan-tool sweep --dry-run`` produced
    ``0 would archive, 0 partial, 28 missing`` from inside
    ``.agents/skills/plan-tool/`` (CWD walk-up halted at
    ``.agents/.git``) but the accurate ``6 would archive, 20 partial,
    2 missing`` from the outer repo root. These cases pin both halves
    of the fix:

    1. With ``--repo-root <outer>`` the output is byte-identical from
       either CWD — the override threads through ``build_plan_tool_context``
       into ``cmd_sweep`` → ``sweep_plans``.
    2. Without ``--repo-root`` (and with ``PLAN_TOOL_REPO_ROOT``
       cleared) a sweep run from inside the nested checkout exits
       non-zero with a diagnostic naming the override knobs — the
       silent ``0 archive, 0 partial, N missing`` result is impossible.
    """

    def test_repo_root_override_produces_identical_output_from_both_cwds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        outer, plans_dir, manifest, nested = _seed_nested_git_repo(
            tmp_path,
            plans={
                "1-done.md": _plan_text(
                    status="completed", step_statuses=["done"]
                ),
                "2-active.md": _plan_text(
                    status="planning",
                    step_statuses=["done", "current", "pending"],
                ),
            },
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)

        monkeypatch.chdir(outer)
        rc_outer = main([
            "--repo-root", str(outer),
            "--manifest", str(manifest),
            "sweep", "--dry-run",
        ])
        captured_outer = capsys.readouterr()

        monkeypatch.chdir(nested)
        rc_nested = main([
            "--repo-root", str(outer),
            "--manifest", str(manifest),
            "sweep", "--dry-run",
        ])
        captured_nested = capsys.readouterr()

        assert rc_outer == 0
        assert rc_nested == 0
        assert captured_outer.out == captured_nested.out
        assert captured_outer.err == captured_nested.err
        # And the output matches the "true" sweep — non-empty completed
        # + non-empty partial — not the broken "all missing" shape.
        assert "1 would archive" in captured_outer.out
        assert "1 partial" in captured_outer.out

    def test_no_override_from_nested_checkout_auto_recovers(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Walk-up enumerates *every* ``.git`` ancestor — the outer root
        scores 1 entry resolved and the nested root scores 0, so the
        outer wins and sweep produces the correct output without any
        ``--repo-root`` override."""
        outer, plans_dir, manifest, nested = _seed_nested_git_repo(
            tmp_path,
            plans={
                "1-done.md": _plan_text(
                    status="completed", step_statuses=["done"]
                ),
            },
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(nested)

        rc = main(["--manifest", str(manifest), "sweep", "--dry-run"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 would archive" in out

    def test_hard_errors_when_no_candidate_resolves(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """If the manifest references files that don't exist under *any*
        reachable ``.git`` ancestor, the diagnostic lists every candidate
        tried so the operator can see which roots were considered."""
        outer = tmp_path / "outer"
        outer.mkdir()
        (outer / ".git").mkdir()
        nested = outer / ".agents" / "skills" / "plan-tool"
        nested.mkdir(parents=True)
        (outer / ".agents" / ".git").mkdir()
        manifest = nested / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/ghost.md"]}), encoding="utf-8"
        )
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.chdir(nested)

        rc = main(["--manifest", str(manifest), "sweep", "--dry-run"])
        assert rc != 0
        err = capsys.readouterr().err
        assert "--repo-root" in err
        assert "PLAN_TOOL_REPO_ROOT" in err
        # The diagnostic must enumerate the candidates tried so the
        # operator can see which roots were considered.
        assert str(outer.resolve()) in err
        assert str((outer / ".agents").resolve()) in err


# ---------- discover_orphan_plans ----------


def test_discover_finds_unregistered_plan_beside_registered(
    tmp_path: Path,
) -> None:
    """A valid plan file in a registered-plan dir but not in the manifest
    surfaces as an orphan; registered files don't."""
    _repo, plans_dir, _manifest = _seed_repo(
        tmp_path,
        plans={"1-active.md": _plan_text(
            status="planning", step_statuses=["pending"]
        )},
    )
    orphan_path = plans_dir / "2-stray.md"
    orphan_path.write_text(
        _plan_text(status="planning", step_statuses=["pending"]),
        encoding="utf-8",
    )
    entries = collect_plan_entries([plans_dir / "1-active.md"])
    orphans = discover_orphan_plans(entries)
    assert [o.path for o in orphans] == [orphan_path.resolve()]
    assert orphans[0].plan is not None
    assert orphans[0].error is None


def test_discover_skips_fenceless_md_and_subdirectories(
    tmp_path: Path,
) -> None:
    """Notes without a frontmatter fence are not orphans, and files in
    archive/ or plan-details/ subdirectories are never scanned."""
    _repo, plans_dir, _manifest = _seed_repo(
        tmp_path,
        plans={"1-active.md": _plan_text(
            status="planning", step_statuses=["pending"]
        )},
    )
    (plans_dir / "notes.md").write_text("# just notes\n", encoding="utf-8")
    archive_dir = plans_dir / "archive"
    archive_dir.mkdir()
    (archive_dir / "2-old.md").write_text(
        _plan_text(status="completed", step_statuses=["done"]),
        encoding="utf-8",
    )
    details_dir = plans_dir / "plan-details" / "active"
    details_dir.mkdir(parents=True)
    (details_dir / "01-step.md").write_text("# detail\n", encoding="utf-8")

    entries = collect_plan_entries([plans_dir / "1-active.md"])
    assert discover_orphan_plans(entries) == []


def test_discover_surfaces_invalid_plan_with_error(tmp_path: Path) -> None:
    """A file WITH a frontmatter fence that fails schema validation is
    reported as an invalid orphan (it looks like a plan, so hiding it
    would mask a malformed plan that should be registered)."""
    _repo, plans_dir, _manifest = _seed_repo(
        tmp_path,
        plans={"1-active.md": _plan_text(
            status="planning", step_statuses=["pending"]
        )},
    )
    (plans_dir / "2-broken.md").write_text(
        "---\npriority: low\n---\n# Body\n", encoding="utf-8"
    )
    entries = collect_plan_entries([plans_dir / "1-active.md"])
    orphans = discover_orphan_plans(entries)
    assert len(orphans) == 1
    assert orphans[0].plan is None
    assert orphans[0].error


def test_discover_scans_parents_of_missing_entries(tmp_path: Path) -> None:
    """A directory whose registered plans were all deleted (manifest
    entries now missing) is still scanned for newcomers."""
    _repo, plans_dir, _manifest = _seed_repo(tmp_path, plans={})
    stray = plans_dir / "1-stray.md"
    stray.write_text(
        _plan_text(status="planning", step_statuses=["pending"]),
        encoding="utf-8",
    )
    orphans = discover_orphan_plans(
        [], missing_paths=[plans_dir / "1-gone.md"]
    )
    assert [o.path for o in orphans] == [stray.resolve()]


@pytest.mark.integration
class TestCmdSweepOrphans:
    """Sweep reports orphans, while ``register`` remains the only adopter."""

    def _seed_with_orphan(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path, Path]:
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-active.md": _plan_text(
                status="planning", step_statuses=["pending"]
            )},
        )
        orphan = plans_dir / "2-stray.md"
        orphan.write_text(
            _plan_text(status="planning", step_statuses=["pending"]),
            encoding="utf-8",
        )
        return repo, plans_dir, manifest, orphan

    def test_yes_never_registers_orphans(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 unregistered" in out
        assert "plan-tool register <path>" in out
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]
        assert parse_plan(orphan).registered_by is None

    def test_dry_run_previews_without_mutating(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        before = orphan.read_text(encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--dry-run", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "plan-tool register <path>" in out
        assert orphan.read_text(encoding="utf-8") == before
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]

    def test_report_only_lists_with_hint_but_never_mutates(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        before = orphan.read_text(encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "--report-only", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "1 unregistered" in out
        assert "plans/2-stray.md" in out
        assert "hint" in out
        assert orphan.read_text(encoding="utf-8") == before
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]

    def test_non_interactive_without_yes_leaves_orphans(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        before = orphan.read_text(encoding="utf-8")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        captured = capsys.readouterr()
        assert "1 unregistered" in captured.out
        assert captured.err == ""
        assert orphan.read_text(encoding="utf-8") == before
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]

    def test_interactive_yes_never_registers(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "y")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "plan-tool register <path>" in out
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]

    def test_interactive_no_keeps(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        repo, _plans_dir, manifest, orphan = self._seed_with_orphan(tmp_path)
        before = orphan.read_text(encoding="utf-8")
        monkeypatch.setattr("sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda *a, **k: "n")
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "plan-tool register <path>" in out
        assert orphan.read_text(encoding="utf-8") == before
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-stray.md" not in data["plans"]

    def test_completed_orphan_is_reported_not_archived(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A completed orphan remains untouched until explicitly registered."""
        repo, plans_dir, manifest = _seed_repo(
            tmp_path,
            plans={"1-active.md": _plan_text(
                status="planning", step_statuses=["pending"]
            )},
        )
        orphan = plans_dir / "2-finished.md"
        orphan.write_text(
            _plan_text(status="completed", step_statuses=["done"]),
            encoding="utf-8",
        )
        rc = main([
            "--repo-root", str(repo),
            "--manifest", str(manifest),
            "sweep", "-y",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "0 archived" in out
        assert "plan-tool register <path>" in out
        assert orphan.is_file()
        data = json.loads(manifest.read_text(encoding="utf-8"))
        assert "plans/2-finished.md" not in data["plans"]


@pytest.mark.integration
class TestSweepDuplicatePlans:
    """When the same plan file exists under multiple candidate roots
    *within the current tree* (e.g. an outer repo plus a nested inner
    repo such as a skill bundle), sweep surfaces the duplicates in its
    report and the ``--archive-duplicates`` flag moves them to
    ``archive/`` beside each duplicate. Duplicates in unrelated sibling
    repos are intentionally not detected — candidate enumeration is
    scoped to roots that contain cwd so one project never reaches into
    another's plans."""

    def _seed_duplicate_layout(
        self, tmp_path: Path
    ) -> tuple[Path, Path, Path, Path]:
        """Build nested repos (outer + inner), both hosting the same plan.

        ``inner`` wins the candidate tie (innermost), so ``outer``'s copy
        is the one reported as a duplicate.
        """
        outer = tmp_path / "outer"
        inner = outer / "inner"
        (outer / "plans").mkdir(parents=True)
        (inner / "plans").mkdir(parents=True)
        (outer / ".git").mkdir()
        (inner / ".git").mkdir()
        plan_body = _plan_text(status="planning", step_statuses=["pending"])
        (outer / "plans" / "1-alpha.md").write_text(plan_body, encoding="utf-8")
        (inner / "plans" / "1-alpha.md").write_text(plan_body, encoding="utf-8")
        manifest = inner / "m.json"
        manifest.write_text(
            json.dumps({"plans": ["plans/1-alpha.md"]}), encoding="utf-8"
        )
        return outer, inner, manifest, outer / "plans" / "1-alpha.md"

    def test_report_surfaces_duplicates_hint(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        outer, inner, manifest, dup_plan = self._seed_duplicate_layout(
            tmp_path
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(inner)

        rc = main([
            "--manifest", str(manifest),
            "sweep", "--dry-run",
        ])
        assert rc == 0
        out = capsys.readouterr().out
        assert "duplicates" in out
        assert str(dup_plan.resolve()) in out
        assert "--archive-duplicates" in out

    def test_archive_duplicates_moves_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        outer, inner, manifest, dup_plan = self._seed_duplicate_layout(
            tmp_path
        )
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        monkeypatch.delenv("PLAN_TOOL_REPO_ROOT", raising=False)
        monkeypatch.chdir(inner)

        rc = main([
            "--manifest", str(manifest),
            "sweep", "--archive-duplicates", "-y",
        ])
        assert rc == 0
        # Source moved.
        assert not dup_plan.is_file()
        # Destination exists.
        archived = dup_plan.parent / "archive" / dup_plan.name
        assert archived.is_file()
