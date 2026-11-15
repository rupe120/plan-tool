"""Which paths a plan owns for ``--commit``.

One rule shared by ``detail``, ``completeness-audit`` and ``run``, so their
footprints cannot drift. Leaf helper: no business logic, no git calls.
"""

from __future__ import annotations

import sys
from pathlib import Path

from plan_tool.parser import parse_plan
from plan_tool.review_persistence import plan_reports_dir


def plan_tool_state_dir(repo_root: Path) -> Path:
    """``.plan-tool/``: everything plan-tool writes there (lessons, telemetry,
    run logs, run-prefs) is committed unless the repo's ignore rules exclude it."""
    return repo_root / ".plan-tool"


# Runtime state plan-tool writes under ``.plan-tool/``: transient, so ignored
# by default. A repo keeps one by tracking it (git add -f); tracked files stay
# tracked whatever the ignore rules say.
RUNTIME_STATE_PATTERNS = (
    "runs/",
    "checkpoints/",
    "reviews/",
    "parse-failures/",
    "crashes/",
    "scenarios/",
    "telemetry/",
    "purity-cache/",
    "mutation.lock",
    "run-prefs.json",
    "lessons-warnings.jsonl",
    "lessons-warnings.jsonl.*",
)

_STATE_IGNORE_HEADER = (
    "# Written by plan-tool: its runtime state under .plan-tool/ is ignored by\n"
    "# default, and this file ignores itself. Kept as-is once written; edit it\n"
    "# or force-track a file (git add -f) to keep that file in history.\n"
)


def ensure_state_ignore(repo_root: Path) -> None:
    """Write ``.plan-tool/.gitignore`` when it is missing; never overwrite it.

    Called before every ``--commit`` clean-tree gate, so runtime state never
    reads as dirt and nothing plan-tool writes after a verb's last commit (the
    run-log end record, the sweep's run-prefs) blocks the next ``--commit``.
    Best-effort: an unwritable directory leaves the repo's own rules in charge.
    """
    path = plan_tool_state_dir(repo_root) / ".gitignore"
    if path.exists():
        return
    lines = ["/.gitignore", *(f"/{p}" for p in RUNTIME_STATE_PATTERNS)]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_STATE_IGNORE_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


def plan_commit_footprint(repo_root: Path, plan_path: Path) -> list[Path]:
    """The plan file, its ``plan-details/<slug>/`` directory (detail files,
    ``archive/`` moves, saved reports), every ``steps[].detail`` pointer the
    plan declares and its ``lessons:`` log (either can sit outside that
    directory), and :func:`plan_tool_state_dir`. Rebuild it at each commit so a pointer set
    mid-run is included; an unreadable plan contributes no pointers rather
    than raising.
    """
    footprint = [
        plan_path,
        plan_reports_dir(plan_path).parent,
        plan_tool_state_dir(repo_root),
    ]
    try:
        plan = parse_plan(plan_path)
    except Exception as exc:  # noqa: BLE001 — the footprint must never abort a commit
        if plan_path.exists():
            print(
                f"warning: could not read {plan_path.name} ({exc.__class__.__name__}); "
                "committing without its declared detail files and lessons log",
                file=sys.stderr,
            )
        return footprint
    footprint.extend(repo_root / step.detail for step in plan.steps if step.detail)
    if plan.lessons:
        footprint.append(repo_root / plan.lessons)
    return footprint
