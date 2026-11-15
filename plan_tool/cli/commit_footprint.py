"""Which paths a plan owns for ``--commit``, and plan-tool's default ignore
file for its runtime state.

One footprint rule shared by ``detail``, ``completeness-audit`` and ``run``,
so their footprints cannot drift. First-party imports: ``parser``,
``review_persistence``, and ``cli.gitcommit`` (lazily, for the commit).
"""

from __future__ import annotations

import sys
from collections.abc import Sequence
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


def _probe_path(pattern: str) -> str:
    """A path under ``.plan-tool/`` that ``pattern`` would match."""
    if pattern.endswith("/"):
        return f".plan-tool/{pattern}x"
    return f".plan-tool/{pattern.replace('*', '1')}"


def undecided_patterns(repo_root: Path) -> "list[str] | None":
    """The default patterns no existing ignore rule decides either way, or
    ``None`` when git cannot say. A rule that ignores a path, or a negation
    that keeps it, is the repo's decision; a nested default would override it."""
    import subprocess

    probes = [_probe_path(p) for p in RUNTIME_STATE_PATTERNS]
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-v", "-n", "-z", "--no-index", "--stdin"],
            cwd=repo_root,
            input="\0".join(probes) + "\0",
            capture_output=True,
            text=True,
            errors="surrogateescape",
        )
    except OSError:
        return None
    if proc.returncode not in (0, 1):
        return None
    fields = proc.stdout.split("\0")
    # Four fields per path (source, line, pattern, path); no source = no rule.
    decided = {
        fields[k + 3] for k in range(0, len(fields) - 3, 4) if fields[k]
    }
    return [p for p, probe in zip(RUNTIME_STATE_PATTERNS, probes) if probe not in decided]


def ensure_state_ignore(repo_root: Path, patterns: "Sequence[str] | None" = None) -> None:
    """Write ``.plan-tool/.gitignore`` with ``patterns`` (default: all) when it
    is missing; never overwrite it. Best-effort: an unwritable directory leaves
    the repo's own rules in charge."""
    path = state_ignore_path(repo_root)
    if path.exists():
        return
    chosen = RUNTIME_STATE_PATTERNS if patterns is None else patterns
    lines = [f"/{p}" for p in chosen]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_STATE_IGNORE_HEADER + "\n".join(lines) + "\n", encoding="utf-8")
    except OSError:
        pass


STATE_IGNORE_COMMIT_SUBJECT = "plan-tool: ignore runtime state by default"


def _ever_committed(repo_root: Path, path: Path) -> bool:
    """True when ``path`` is in any commit's history (its deletion is an opt-out)."""
    import subprocess

    try:
        proc = subprocess.run(
            ["git", "log", "-1", "--format=%H", "--", str(path)],
            cwd=repo_root, capture_output=True, text=True, errors="surrogateescape",
        )
    except OSError:
        return True  # can't tell: never re-create over a possible opt-out
    return proc.returncode != 0 or bool(proc.stdout.strip())


def commit_state_ignore(repo_root: Path) -> None:
    """Before a ``--commit`` clean-tree gate: fill the gaps in the repo's ignore
    rules for plan-tool's runtime state, in ``.plan-tool/.gitignore``, committed
    on its own.

    Only patterns no existing rule decides are written, so the file never
    overrides a repo's own choice, and none is written when nothing is left.
    Skipped on a dirty tree (the gate refuses it), when the file exists, and
    when it was ever committed (a committed deletion is the opt-out). Writes
    made after a verb's last commit then never block the next ``--commit``.
    """
    from plan_tool.cli.gitcommit import commit_all, working_tree_dirty

    path = state_ignore_path(repo_root)
    if path.exists() or working_tree_dirty(repo_root):
        return
    if _ever_committed(repo_root, path):
        return
    gaps = undecided_patterns(repo_root)
    if not gaps:
        return
    ensure_state_ignore(repo_root, gaps)
    if not path.exists():
        return
    outcome = commit_all(repo_root, STATE_IGNORE_COMMIT_SUBJECT, [path])
    if outcome.rc == 0 and outcome.committed:
        return
    if not outcome.committed:
        path.unlink(missing_ok=True)
    print(
        "warning: " + outcome.describe("the default .plan-tool/.gitignore")
        + ". Add plan-tool's runtime paths (docs/how-to/pipeline/run.md"
        " § Commit footprint) to your .gitignore so --commit runs stay clean.",
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
