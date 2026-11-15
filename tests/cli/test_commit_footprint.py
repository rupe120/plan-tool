"""``plan_commit_footprint`` — the one rule for which paths a plan owns."""

from __future__ import annotations

from pathlib import Path

from plan_tool.cli.commit_footprint import plan_commit_footprint


def test_unreadable_plan_still_yields_plan_details_and_state_dir(
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
        tmp_path / ".plan-tool",
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


def _git(root: Path, *args: str) -> str:
    import subprocess

    return subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    ).stdout


def _repo(root: Path) -> None:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t@example.com")
    _git(root, "config", "user.name", "t")
    (root / "seed.txt").write_text("s\n", encoding="utf-8")
    _git(root, "add", "seed.txt")
    _git(root, "commit", "-q", "-m", "init")


def test_state_ignore_hides_runtime_state_and_itself(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import ensure_state_ignore

    _repo(tmp_path)
    state = tmp_path / ".plan-tool"
    (state / "runs" / "demo").mkdir(parents=True)
    (state / "runs" / "demo" / "r.jsonl").write_text("{}\n", encoding="utf-8")
    (state / "run-prefs.json").write_text("{}\n", encoding="utf-8")
    (state / "plans.json").write_text("{}\n", encoding="utf-8")

    ensure_state_ignore(tmp_path)

    # Only the manifest, which is not runtime state, still shows up.
    assert _git(tmp_path, "status", "--porcelain", "-uall") == "?? .plan-tool/plans.json\n"


def test_state_ignore_is_never_overwritten(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import ensure_state_ignore

    ignore = tmp_path / ".plan-tool" / ".gitignore"
    ignore.parent.mkdir()
    ignore.write_text("/runs/\n", encoding="utf-8")
    ensure_state_ignore(tmp_path)
    assert ignore.read_text(encoding="utf-8") == "/runs/\n"


def test_tracked_runtime_file_stays_committed(tmp_path: Path) -> None:
    """A repo that force-tracks run-prefs.json keeps committing it: ignore
    rules never untrack a file."""
    from plan_tool.cli.commit_footprint import ensure_state_ignore, plan_tool_state_dir
    from plan_tool.cli.gitcommit import commit_all

    _repo(tmp_path)
    prefs = tmp_path / ".plan-tool" / "run-prefs.json"
    prefs.parent.mkdir()
    prefs.write_text("{}\n", encoding="utf-8")
    _git(tmp_path, "add", ".plan-tool/run-prefs.json")
    _git(tmp_path, "commit", "-q", "-m", "track prefs")
    ensure_state_ignore(tmp_path)
    prefs.write_text('{"last_plan": "x"}\n', encoding="utf-8")

    rc, tail, committed = commit_all(tmp_path, "s", [plan_tool_state_dir(tmp_path)])

    assert rc == 0 and committed, tail
    assert _git(tmp_path, "show", "--name-only", "--format=", "HEAD").split() == [
        ".plan-tool/run-prefs.json"
    ]
