"""``plan_commit_footprint`` — the one rule for which paths a plan owns."""

from __future__ import annotations

from pathlib import Path

from plan_tool.cli.commit_footprint import plan_commit_footprint


def test_unreadable_plan_still_yields_plan_details_and_lessons(
    tmp_path: Path, capsys
) -> None:
    plan = tmp_path / "plans" / "1-demo.md"
    plan.parent.mkdir()
    plan.write_bytes(b"\xff not a plan")
    footprint = plan_commit_footprint(tmp_path, plan)
    # Says what it dropped, so a dirty tree afterwards has an explanation.
    assert "could not read 1-demo.md" in capsys.readouterr().err
    assert footprint == [
        plan,
        plan.parent / "plan-details" / "demo",
        tmp_path / ".plan-tool" / "lessons",
    ]


def test_missing_plan_does_not_raise(tmp_path: Path) -> None:
    plan = tmp_path / "plans" / "1-gone.md"
    assert plan in plan_commit_footprint(tmp_path, plan)


def test_plan_level_lessons_log_is_in_the_footprint(tmp_path: Path) -> None:
    plan = tmp_path / "plans" / "1-demo.md"
    plan.parent.mkdir()
    plan.write_text(
        "---\ntitle: Demo\nstatus: planning\npriority: low\n"
        "lessons: notes/demo-lessons.md\nsteps:\n"
        "  - id: 1\n    title: Only\n    status: pending\n---\n# Body\n",
        encoding="utf-8",
    )
    assert tmp_path / "notes" / "demo-lessons.md" in plan_commit_footprint(
        tmp_path, plan
    )
