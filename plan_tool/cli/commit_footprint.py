"""Which paths a plan owns for ``--commit``.

One rule shared by ``detail``, ``completeness-audit`` and ``run``, so their
footprints cannot drift. Leaf helper: no business logic, no git calls.
"""

from __future__ import annotations

from pathlib import Path

from plan_tool.lessons import PROJECT_LESSONS_REL
from plan_tool.parser import parse_plan
from plan_tool.review_persistence import plan_reports_dir


def plan_commit_footprint(repo_root: Path, plan_path: Path) -> list[Path]:
    """The plan file, its ``plan-details/<slug>/`` directory (detail files,
    ``archive/`` moves, saved reports), every ``steps[].detail`` pointer the
    plan declares (a pointer can name a file outside that directory), and the
    project lessons directory. Rebuild it at each commit so a pointer set
    mid-run is included; an unreadable plan contributes no pointers rather
    than raising.
    """
    footprint = [
        plan_path,
        plan_reports_dir(plan_path).parent,
        repo_root.joinpath(*PROJECT_LESSONS_REL),
    ]
    try:
        plan = parse_plan(plan_path)
    except Exception:  # noqa: BLE001 — the footprint must never abort a commit
        return footprint
    footprint.extend(repo_root / step.detail for step in plan.steps if step.detail)
    return footprint
