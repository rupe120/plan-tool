"""Tests for plan_tool.plan_merge_guard: the plan and its detail bundle are on origin's default branch."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from plan_tool.detail_artifacts import derive_jira_detail_path
from plan_tool.parser import parse_plan
from plan_tool.plan_merge_guard import NO_REMOTE, check_plan_merged, default_branch_name

PLAN = "docs/implementation-plans/demo.md"
_REPO_TEMPLATE: Path | None = None


def _plan_text(*, title: str = "Demo", step_status: str = "pending", plan_status: str = "planning", second: str = "detail") -> str:
    step2 = {
        "detail": "- id: 2\n  title: Two\n  files:\n  - b.py\n  detail: docs/d/02.md\n  status: pending\n",
        "none": "- id: 2\n  title: Two\n  files:\n  - b.py\n  status: pending\n",
        "deferred": "- id: 2\n  title: Two\n  files:\n  - b.py\n  status: pending\n  scope: deferred\n",
    }[second]
    return (
        f"---\nformat_version: 1\ntitle: {title}\nstatus: {plan_status}\npriority: medium\nsteps:\n"
        f"- id: 1\n  title: One\n  files:\n  - a.py\n  detail: docs/d/01.md\n  status: {step_status}\n{step2}---\n\n# Demo\n"
    )


class Repo:
    def __init__(self, root: Path, env: dict[str, str]) -> None:
        self.root, self.env = root, env

    def git(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["git", *args], cwd=self.root, env=self.env, capture_output=True, text=True, check=check)

    def write(self, rel: str, text: str) -> None:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, message: str) -> None:
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)

    def merge_to_origin(self, message: str = "merge") -> None:
        self.commit(message)
        self.git("push", "-q", "origin", "HEAD:main")
        self.git("fetch", "-q", "origin")

    def check(self, detail_grade: str = "run"):
        result = check_plan_merged(self.root, self.root / PLAN, detail_grade)
        # An unparseable plan or missing ref returns empty results; never let that read as a pass.
        assert result.unverifiable is None, result.unverifiable
        return result


def _git_env(home: Path) -> dict[str, str]:
    return {
        **os.environ, "HOME": str(home), "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    }


@pytest.fixture(scope="session", autouse=True)
def _repo_template(tmp_path_factory: pytest.TempPathFactory):
    """Create the immutable remote and checkout baseline once per worker."""
    global _REPO_TEMPLATE
    base = tmp_path_factory.mktemp("plan-merge-template")
    env = _git_env(base)
    bare = base / "origin.git"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], env=env, check=True)
    root = base / "work"
    root.mkdir()
    r = Repo(root, env)
    r.git("init", "-q", "-b", "main")
    r.git("remote", "add", "origin", str(bare))
    r.write("README.md", "seed\n")
    r.merge_to_origin("seed")
    r.git("checkout", "-q", "-b", "feature")
    _REPO_TEMPLATE = base
    yield
    _REPO_TEMPLATE = None


@pytest.fixture
def repo(tmp_path: Path) -> Repo:
    assert _REPO_TEMPLATE is not None
    shutil.copytree(_REPO_TEMPLATE / "origin.git", tmp_path / "origin.git")
    root = tmp_path / "work"
    shutil.copytree(_REPO_TEMPLATE / "work", root)
    r = Repo(root, _git_env(tmp_path))
    r.git("remote", "set-url", "origin", str(tmp_path / "origin.git"))
    return r


def _merge_full_plan(r: Repo, **plan_kwargs) -> None:
    r.write(PLAN, _plan_text(**plan_kwargs))
    r.write("docs/d/01.md", "detail one\n")
    r.write("docs/d/02.md", "detail two\n")
    r.merge_to_origin("plan")


def test_a_repo_without_an_origin_remote_cannot_be_checked(tmp_path: Path) -> None:
    root = tmp_path / "solo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    (root / "plan.md").write_text(_plan_text())
    assert check_plan_merged(root, root / "plan.md").unverifiable == NO_REMOTE


def test_an_origin_with_no_default_branch_asks_for_a_fetch(tmp_path: Path) -> None:
    root, bare = tmp_path / "w", tmp_path / "o.git"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(root)], check=True)
    subprocess.run(["git", "remote", "add", "origin", str(bare)], cwd=root, check=True)
    (root / "plan.md").write_text(_plan_text())
    assert "git fetch" in (check_plan_merged(root, root / "plan.md").unverifiable or "")


def test_a_plan_and_every_detail_file_on_origin_main_passes(repo: Repo) -> None:
    _merge_full_plan(repo)
    result = repo.check()
    assert (result.default_ref, result.unverifiable, result.missing, result.drifted) == ("origin/main", None, (), ())


def test_a_plan_that_exists_only_on_the_branch_is_missing_with_all_its_details(repo: Repo) -> None:
    repo.write(PLAN, _plan_text())
    repo.write("docs/d/01.md", "one\n")
    repo.write("docs/d/02.md", "two\n")
    repo.commit("branch only")
    assert repo.check().missing == (PLAN, "docs/d/01.md", "docs/d/02.md")


def test_one_detail_file_missing_on_main_is_reported_alone(repo: Repo) -> None:
    repo.write(PLAN, _plan_text())
    repo.write("docs/d/01.md", "one\n")
    repo.merge_to_origin("plan and first detail")
    repo.write("docs/d/02.md", "two\n")
    repo.commit("second detail on the branch only")
    assert repo.check().missing == ("docs/d/02.md",)


def test_a_committed_step_with_no_declared_detail_is_missing(repo: Repo) -> None:
    repo.write(PLAN, _plan_text(second="none"))
    repo.write("docs/d/01.md", "one\n")
    repo.merge_to_origin("plan")
    assert repo.check().missing == ("step 2: no detail file declared",)


def test_a_deferred_step_needs_no_detail_file(repo: Repo) -> None:
    # Carve-out: parked (non-committed) steps are outside the full-bundle rule.
    repo.write(PLAN, _plan_text(second="deferred"))
    repo.write("docs/d/01.md", "one\n")
    repo.merge_to_origin("plan")
    assert repo.check().missing == ()


def test_status_changes_that_run_writes_are_not_drift(repo: Repo) -> None:
    _merge_full_plan(repo)
    repo.write(PLAN, _plan_text(step_status="done", plan_status="in-progress"))
    assert repo.check().drifted == ()


def test_editing_the_plan_or_a_detail_after_the_merge_is_drift(repo: Repo) -> None:
    _merge_full_plan(repo)
    repo.write(PLAN, _plan_text(title="Renamed"))
    repo.write("docs/d/02.md", "edited\n")
    assert repo.check().drifted == (PLAN, "docs/d/02.md")


def test_the_default_branch_comes_from_origin_head_else_falls_back_to_master(repo: Repo, tmp_path: Path) -> None:
    _merge_full_plan(repo)
    repo.git("remote", "set-head", "origin", "main")
    assert repo.check().default_ref == "origin/main"
    repo.git("symbolic-ref", "--delete", "refs/remotes/origin/HEAD")
    repo.git("update-ref", "refs/remotes/origin/master", "refs/remotes/origin/main")
    repo.git("update-ref", "-d", "refs/remotes/origin/main")
    assert repo.check().default_ref == "origin/master"
    assert default_branch_name("origin/master") == "master"


def test_a_plan_outside_the_repository_cannot_be_checked(repo: Repo, tmp_path: Path) -> None:
    outside = tmp_path / "elsewhere.md"
    outside.write_text(_plan_text())
    assert "outside" in (check_plan_merged(repo.root, outside).unverifiable or "")


def _jira_detail_paths(r: Repo) -> list[str]:
    plan = parse_plan(r.root / PLAN)
    return [derive_jira_detail_path(r.root / PLAN, plan, step).relative_to(r.root).as_posix() for step in plan.steps]


def test_a_jira_grade_run_needs_the_jira_artifacts_and_not_the_run_grade_details(repo: Repo) -> None:
    # Carve-out: at jira grade the run never reads Step.detail, so absent run-grade files are fine.
    repo.write(PLAN, _plan_text())
    repo.commit("plan only")
    for rel in _jira_detail_paths(repo):
        repo.write(rel, "jira detail\n")
    repo.merge_to_origin("plan and jira artifacts")
    assert repo.check("jira").missing == ()
    assert repo.check("run").missing == ("docs/d/01.md", "docs/d/02.md")


def test_a_missing_jira_artifact_is_reported_by_its_derived_path(repo: Repo) -> None:
    repo.write(PLAN, _plan_text())
    first, second = _jira_detail_paths(repo)
    repo.write(first, "jira detail\n")
    repo.merge_to_origin("plan and first jira artifact")
    assert repo.check("jira").missing == (second,)
