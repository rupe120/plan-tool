"""``plan_commit_footprint`` — the one rule for which paths a plan owns."""

from __future__ import annotations

from pathlib import Path

import pytest

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


def test_state_ignore_hides_runtime_state_and_is_itself_tracked(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import ensure_state_ignore

    _repo(tmp_path)
    state = tmp_path / ".plan-tool"
    (state / "runs" / "demo").mkdir(parents=True)
    (state / "runs" / "demo" / "r.jsonl").write_text("{}\n", encoding="utf-8")
    (state / "run-prefs.json").write_text("{}\n", encoding="utf-8")
    (state / "plans.json").write_text("{}\n", encoding="utf-8")

    ensure_state_ignore(tmp_path)

    # Runtime state is hidden; the manifest and the ignore file itself, both
    # meant to be committed, still show up.
    assert _git(tmp_path, "status", "--porcelain", "-uall") == (
        "?? .plan-tool/.gitignore\n?? .plan-tool/plans.json\n"
    )


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
        ".plan-tool/.gitignore", ".plan-tool/run-prefs.json"
    ]


def _log(root: Path) -> list[str]:
    return _git(root, "log", "--format=%s").splitlines()


def test_default_ignore_is_committed_on_its_own_on_a_clean_tree(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import (
        STATE_IGNORE_COMMIT_SUBJECT,
        commit_state_ignore,
    )

    _repo(tmp_path)
    commit_state_ignore(tmp_path)
    assert _log(tmp_path) == [STATE_IGNORE_COMMIT_SUBJECT, "init"]
    assert _git(tmp_path, "show", "--name-only", "--format=", "HEAD").split() == [
        ".plan-tool/.gitignore"
    ]
    assert _git(tmp_path, "status", "--porcelain") == ""
    commit_state_ignore(tmp_path)  # already there: no second commit
    assert len(_log(tmp_path)) == 2


def test_default_ignore_is_not_written_on_a_dirty_tree(tmp_path: Path) -> None:
    """The gate refuses a dirty tree; plan-tool adds nothing to it first."""
    from plan_tool.cli.commit_footprint import commit_state_ignore

    _repo(tmp_path)
    (tmp_path / "wip.txt").write_text("x\n", encoding="utf-8")
    commit_state_ignore(tmp_path)
    assert not (tmp_path / ".plan-tool" / ".gitignore").exists()
    assert _log(tmp_path) == ["init"]


def test_existing_rules_are_not_overridden_only_gaps_are_written(tmp_path: Path) -> None:
    """A nested .gitignore outranks the root one, so the default writes only
    patterns no rule decides: a root negation that keeps a review stays."""
    from plan_tool.cli.commit_footprint import commit_state_ignore

    _repo(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".plan-tool/reviews/*\n!.plan-tool/reviews/keep.json\n.plan-tool/runs\n",
        encoding="utf-8",
    )
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-q", "-m", "rules")
    commit_state_ignore(tmp_path)

    written = (tmp_path / ".plan-tool" / ".gitignore").read_text(encoding="utf-8")
    assert "/reviews/" not in written and "/runs/" not in written
    assert "/telemetry/" in written and "/run-prefs.json" in written
    keep = tmp_path / ".plan-tool" / "reviews" / "keep.json"
    keep.parent.mkdir(parents=True)
    keep.write_text("{}\n", encoding="utf-8")
    assert "?? .plan-tool/reviews/keep.json" in _git(tmp_path, "status", "--porcelain", "-uall")


def test_no_file_when_the_repo_already_decides_everything(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import commit_state_ignore

    _repo(tmp_path)
    (tmp_path / ".gitignore").write_text(".plan-tool/\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore")
    _git(tmp_path, "commit", "-q", "-m", "ignore all")
    commit_state_ignore(tmp_path)
    assert not (tmp_path / ".plan-tool" / ".gitignore").exists()
    assert len(_log(tmp_path)) == 2


def test_committed_deletion_is_an_opt_out(tmp_path: Path) -> None:
    from plan_tool.cli.commit_footprint import commit_state_ignore

    _repo(tmp_path)
    commit_state_ignore(tmp_path)
    _git(tmp_path, "rm", "-q", ".plan-tool/.gitignore")
    _git(tmp_path, "commit", "-q", "-m", "we manage our own rules")
    commit_state_ignore(tmp_path)
    assert not (tmp_path / ".plan-tool" / ".gitignore").exists()
    assert _log(tmp_path)[0] == "we manage our own rules"


@pytest.mark.parametrize("hook", ["reject", "rewrite"])
def test_a_failed_default_commit_is_reported(
    tmp_path: Path, capsys, hook: str
) -> None:
    """A hook that rejects the commit (file removed) or rewrites the file after
    it lands (file kept) both say what happened and what to do instead."""
    from plan_tool.cli.commit_footprint import commit_state_ignore

    _repo(tmp_path)
    script = (
        "#!/bin/sh\nexit 1\n" if hook == "reject"
        else "#!/bin/sh\necho '# touched' >> .plan-tool/.gitignore\n"
    )
    hook_path = tmp_path / ".git" / "hooks" / "pre-commit"
    hook_path.write_text(script, encoding="utf-8")
    hook_path.chmod(0o755)

    commit_state_ignore(tmp_path)

    err = capsys.readouterr().err
    assert ".plan-tool/.gitignore" in err and "your .gitignore" in err
    assert (tmp_path / ".plan-tool" / ".gitignore").exists() == (hook == "rewrite")
