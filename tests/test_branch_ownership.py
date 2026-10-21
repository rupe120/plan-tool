"""Tests for plan_tool.branch_ownership — the two lookups + the pure classifier."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from plan_tool.branch_binding import set_binding
from plan_tool.branch_ownership import (
    OWNER_AD_HOC,
    OWNER_CONVENTION,
    BranchOwner,
    Tier,
    branch_owner,
    classify_branch,
    convention_owner,
    expected_branch,
    matches_convention_pattern,
)

# Fixed multi-prefix list exercising secondary-prefix recognition.
PREFIXES = ["plan/", "bugfix/"]
_GIT_TEMPLATE: Path | None = None


@pytest.fixture(scope="session", autouse=True)
def _empty_git_template(tmp_path_factory: pytest.TempPathFactory):
    """Provide isolated ownership stores with local Git identity."""
    global _GIT_TEMPLATE
    root = tmp_path_factory.mktemp("branch-ownership-git-template")
    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@example.com"],
        ["git", "config", "user.name", "Test"],
    ):
        subprocess.run(cmd, cwd=root, check=True, capture_output=True)
    _GIT_TEMPLATE = root / ".git"
    yield
    _GIT_TEMPLATE = None


def _init_git_repo(root: Path) -> None:
    assert _GIT_TEMPLATE is not None
    shutil.copytree(_GIT_TEMPLATE, root / ".git")


# --- expected_branch -------------------------------------------------------


def test_expected_branch_derives_when_no_override(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    assert expected_branch(tmp_path, "my-plan", PREFIXES) == "plan/my-plan"


def test_expected_branch_returns_override(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "JIRA-1")
    assert expected_branch(tmp_path, "my-plan", PREFIXES) == "JIRA-1"


# --- branch_owner (ad-hoc-beats-convention + registered-locally) -----------


def test_branch_owner_ad_hoc(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    set_binding(tmp_path, "my-plan", "JIRA-1")
    # Not in registered_slugs — the binding alone is the ownership signal.
    owner = branch_owner(tmp_path, "JIRA-1", registered_slugs=set(), prefixes=PREFIXES)
    assert owner == BranchOwner(slug="my-plan", kind=OWNER_AD_HOC)


def test_branch_owner_convention_registered(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    owner = branch_owner(
        tmp_path, "plan/my-plan", registered_slugs={"my-plan"}, prefixes=PREFIXES
    )
    assert owner == BranchOwner(slug="my-plan", kind=OWNER_CONVENTION)


def test_branch_owner_convention_secondary_prefix(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    owner = branch_owner(
        tmp_path, "bugfix/my-plan", registered_slugs={"my-plan"}, prefixes=PREFIXES
    )
    assert owner == BranchOwner(slug="my-plan", kind=OWNER_CONVENTION)


def test_branch_owner_unregistered_convention_is_none(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    owner = branch_owner(
        tmp_path, "plan/my-plan", registered_slugs=set(), prefixes=PREFIXES
    )
    assert owner is None


def test_branch_owner_ad_hoc_beats_convention(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    # Branch is both ad-hoc-bound to Q and the convention name of registered R.
    set_binding(tmp_path, "q-plan", "plan/r-plan")
    owner = branch_owner(
        tmp_path, "plan/r-plan", registered_slugs={"r-plan"}, prefixes=PREFIXES
    )
    assert owner == BranchOwner(slug="q-plan", kind=OWNER_AD_HOC)


def test_branch_owner_convention_forfeited_when_bound_elsewhere(
    tmp_path: Path,
) -> None:
    _init_git_repo(tmp_path)
    # P's plan/<slug> matches by convention but P is ad-hoc-bound elsewhere.
    set_binding(tmp_path, "my-plan", "plan/my-plan-2")
    owner = branch_owner(
        tmp_path, "plan/my-plan", registered_slugs={"my-plan"}, prefixes=PREFIXES
    )
    assert owner is None


def test_branch_owner_no_owner(tmp_path: Path) -> None:
    _init_git_repo(tmp_path)
    owner = branch_owner(
        tmp_path, "main", registered_slugs={"my-plan"}, prefixes=PREFIXES
    )
    assert owner is None


# --- convention_owner (pure) -----------------------------------------------


def test_convention_owner_matches_registered() -> None:
    assert convention_owner("plan/my-plan", {"my-plan"}, PREFIXES) == "my-plan"
    assert convention_owner("bugfix/my-plan", {"my-plan"}, PREFIXES) == "my-plan"


def test_convention_owner_skips_unregistered() -> None:
    assert convention_owner("plan/my-plan", {"other"}, PREFIXES) is None


# --- classify_branch (pure, all four tiers + ownership) --------------------


def test_classify_tier1_ad_hoc_other_plan() -> None:
    owner = BranchOwner(slug="q-plan", kind=OWNER_AD_HOC)
    result = classify_branch("JIRA-1", "p-plan", owner, PREFIXES)
    assert result.tier == Tier.AD_HOC_OWNED
    assert result.owner == "q-plan"
    assert result.is_owned_by_plan is False


def test_classify_tier1_ad_hoc_same_plan() -> None:
    owner = BranchOwner(slug="p-plan", kind=OWNER_AD_HOC)
    result = classify_branch("JIRA-1", "p-plan", owner, PREFIXES)
    assert result.tier == Tier.AD_HOC_OWNED
    assert result.is_owned_by_plan is True


def test_classify_tier2_convention() -> None:
    owner = BranchOwner(slug="p-plan", kind=OWNER_CONVENTION)
    result = classify_branch("plan/p-plan", "p-plan", owner, PREFIXES)
    assert result.tier == Tier.CONVENTION_OWNED
    assert result.is_owned_by_plan is True


def test_classify_tier3_orphan_pattern() -> None:
    result = classify_branch("plan/nobody", "p-plan", None, PREFIXES)
    assert result.tier == Tier.ORPHAN_PATTERN
    assert result.owner is None
    assert result.is_owned_by_plan is False


def test_classify_tier4_unowned() -> None:
    result = classify_branch("main", "p-plan", None, PREFIXES)
    assert result.tier == Tier.UNOWNED
    assert result.owner is None
    assert result.is_owned_by_plan is False


# --- matches_convention_pattern (pure) -------------------------------------


def test_matches_pattern_true_with_tail() -> None:
    assert matches_convention_pattern("plan/foo", ["plan/"]) is True


def test_matches_pattern_false_bare_prefix() -> None:
    assert matches_convention_pattern("plan/", ["plan/"]) is False
    assert matches_convention_pattern("main", ["plan/"]) is False
