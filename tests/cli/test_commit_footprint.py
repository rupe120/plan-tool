"""``plan_commit_footprint`` — the one rule for which paths a plan owns."""

from __future__ import annotations

from pathlib import Path

from plan_tool.cli.commit_footprint import plan_commit_footprint


def test_unreadable_plan_still_yields_plan_details_and_lessons(tmp_path: Path) -> None:
    plan = tmp_path / "plans" / "1-demo.md"
    plan.parent.mkdir()
    plan.write_bytes(b"\xff not a plan")
    footprint = plan_commit_footprint(tmp_path, plan)
    assert footprint == [
        plan,
        plan.parent / "plan-details" / "demo",
        tmp_path / ".plan-tool" / "lessons",
    ]


def test_missing_plan_does_not_raise(tmp_path: Path) -> None:
    plan = tmp_path / "plans" / "1-gone.md"
    assert plan in plan_commit_footprint(tmp_path, plan)
