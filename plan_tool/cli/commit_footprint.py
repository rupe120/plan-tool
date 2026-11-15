"""Which paths a plan owns for ``--commit``, and plan-tool's default ignore
file for its runtime state.

One footprint rule shared by ``detail``, ``completeness-audit`` and ``run``,
so their footprints cannot drift. Imports only the ``gitcommit`` leaf for git.
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
    "bench/runs/",
    "evidence/impact-analyses/",
    "lessons-warnings.jsonl",
    "lessons-warnings.jsonl.*",
)

_STATE_IGNORE_HEADER = (
    "# Written by plan-tool: its runtime state under .plan-tool/ is ignored by\n"
    "# default. Tracked and never overwritten, so the team can edit it: delete a\n"
    "# line to commit that state. A file already tracked stays tracked.\n"
)


def state_ignore_path(repo_root: Path) -> Path:
    return plan_tool_state_dir(repo_root) / ".gitignore"


def ensure_state_ignore(repo_root: Path) -> None:
    """Write ``.plan-tool/.gitignore`` when it is missing; never overwrite it.

    Best-effort: an unwritable directory leaves the repo's own rules in charge.
    """
    path = state_ignore_path(repo_root)
    if path.exists():
        return
    lines = [f"/{p}" for p in RUNTIME_STATE_PATTERNS]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_STATE_IGNORE_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


STATE_IGNORE_COMMIT_SUBJECT = "plan-tool: ignore runtime state by default"


def commit_state_ignore(repo_root: Path) -> None:
    """Before a ``--commit`` clean-tree gate: on an otherwise clean tree with no
    ``.plan-tool/.gitignore``, write the default and commit it on its own.

    Runtime state then never reads as dirt, and nothing plan-tool writes after
    a verb's last commit (the run-log end record, the sweep's run-prefs)
    blocks the next ``--commit``. A dirty tree is left alone for the gate to
    refuse; a failed commit removes the file and warns.
    """
    from plan_tool.cli.gitcommit import commit_all, working_tree_dirty

    path = state_ignore_path(repo_root)
    if path.exists() or working_tree_dirty(repo_root):
        return
    ensure_state_ignore(repo_root)
    if not path.exists():
        return
    outcome = commit_all(repo_root, STATE_IGNORE_COMMIT_SUBJECT, [path])
    if outcome.rc != 0 and not outcome.committed:
        path.unlink(missing_ok=True)
        print(
            "warning: " + outcome.describe("the default .plan-tool/.gitignore"),
            file=sys.stderr,
        )


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
