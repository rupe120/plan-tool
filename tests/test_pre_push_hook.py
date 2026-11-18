"""The pre-push hook runs the suite only for pushes no pull-request pipeline gates."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[1] / "scripts" / "hooks" / "pre-push"
BITBUCKET = "git@ssh.bitbucket.org:protagona/plan-tool.git"
GITHUB = "git@github.com:rupe120/plan-tool.git"


@pytest.fixture
def sandbox(tmp_path: Path) -> dict:
    """A repo whose `uv` is a stub that records that the suite was started."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {**os.environ, "HOME": str(tmp_path), "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    for key in [k for k in env if k.startswith("GIT_") and k not in ("GIT_CONFIG_GLOBAL", "GIT_CONFIG_SYSTEM")]:
        del env[key]
    subprocess.run(["git", "init", "-q"], cwd=repo, env=env, check=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    ran = tmp_path / "suite-ran"
    stub = bin_dir / "uv"
    stub.write_text(f"#!/bin/sh\ntouch {ran}\nexit 0\n")
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)
    env["PATH"] = f"{bin_dir}{os.pathsep}{env['PATH']}"
    return {"repo": repo, "env": env, "ran": ran}


def _push(sandbox: dict, *, remote_urls: list[str], remote_ref: str) -> subprocess.CompletedProcess:
    repo, env = sandbox["repo"], sandbox["env"]
    subprocess.run(["git", "remote", "add", "origin", remote_urls[0]], cwd=repo, env=env, check=True)
    for url in remote_urls[1:]:
        subprocess.run(["git", "remote", "set-url", "--add", "--push", "origin", url], cwd=repo, env=env, check=True)
    stdin = f"refs/heads/topic {'a' * 40} {remote_ref} {'0' * 40}\n"
    return subprocess.run([str(HOOK), "origin", remote_urls[0]], cwd=repo, env=env, input=stdin, capture_output=True, text=True)


def test_a_feature_branch_push_to_bitbucket_skips_the_suite_because_its_pull_request_pipeline_runs_it(sandbox) -> None:
    result = _push(sandbox, remote_urls=[BITBUCKET], remote_ref="refs/heads/feature")

    assert result.returncode == 0 and "skipped" in result.stderr
    assert not sandbox["ran"].exists()


def test_a_push_that_updates_main_runs_the_suite_even_to_bitbucket(sandbox) -> None:
    result = _push(sandbox, remote_urls=[BITBUCKET], remote_ref="refs/heads/main")

    assert result.returncode == 0
    assert sandbox["ran"].exists()


def test_a_push_to_a_github_remote_runs_the_suite_whatever_the_ref(sandbox) -> None:
    result = _push(sandbox, remote_urls=[GITHUB], remote_ref="refs/tags/v1.0.0")

    assert result.returncode == 0
    assert sandbox["ran"].exists()


def test_a_remote_with_a_second_github_push_url_counts_as_github(sandbox) -> None:
    """`origin` here has two push URLs, as this repo's does; the first being Bitbucket must not hide the GitHub one."""
    result = _push(sandbox, remote_urls=[BITBUCKET, GITHUB], remote_ref="refs/heads/feature")

    assert result.returncode == 0
    assert sandbox["ran"].exists()


def test_a_red_suite_still_blocks_a_gated_push(sandbox) -> None:
    stub = Path(sandbox["env"]["PATH"].split(os.pathsep)[0]) / "uv"
    stub.write_text("#!/bin/sh\necho 'FAILED tests/test_x.py'\nexit 1\n")

    result = _push(sandbox, remote_urls=[BITBUCKET], remote_ref="refs/heads/main")

    assert result.returncode == 1 and "push blocked" in result.stderr
