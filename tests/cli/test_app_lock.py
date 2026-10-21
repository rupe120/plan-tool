from __future__ import annotations

from argparse import Namespace

from plan_tool.cli.app import _requires_repo_mutation_lock


def test_reconcile_mutating_aliases_require_repo_lock() -> None:
    for command in (
        "reconcile-plan",
        "reconcile",
        "review",
        "reconcile-plan-walk",
        "reconcile-walk",
        "review-walk",
    ):
        assert _requires_repo_mutation_lock(Namespace(command=command))


def test_read_only_aliases_do_not_require_repo_lock() -> None:
    for command in ("verify-all", "reconcile-all", "review-all", "verify"):
        assert not _requires_repo_mutation_lock(Namespace(command=command))


def test_scope_review_requires_repo_lock() -> None:
    assert _requires_repo_mutation_lock(Namespace(command="scope-review"))
