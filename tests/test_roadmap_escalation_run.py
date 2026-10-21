"""Tests for the evidence-receipt Git helpers kept in ``roadmap_escalation_run``."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from plan_tool import roadmap_escalation_run as escalation_run
from plan_tool.roadmap_evidence_store import EvidenceNamespace


_SLUG = "receipt-run"


def test_receipt_head_state_pins_one_head_for_tree_and_blob(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    roadmap_root = tmp_path / "plans" / "roadmaps" / _SLUG
    roadmap_root.mkdir(parents=True)
    receipt_name = "a" * 64
    relative_path = escalation_run._receipt_final_path(
        roadmap_root, receipt_name, namespace=EvidenceNamespace.DECISION_SETTLEMENTS
    ).relative_to(tmp_path).as_posix()
    revision = "b" * 40
    calls: list[list[str]] = []

    def run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess[bytes]:
        calls.append(args)
        if args[1] == "rev-parse":
            return subprocess.CompletedProcess(args, 0, f"{revision}\n".encode(), b"")
        if args[1] == "ls-tree":
            assert args == ["git", "ls-tree", "-z", revision, "--", relative_path]
            return subprocess.CompletedProcess(args, 0, b"entry\0", b"")
        assert args == ["git", "show", f"{revision}:{relative_path}"]
        return subprocess.CompletedProcess(args, 0, b"receipt", b"")

    monkeypatch.setattr(escalation_run.subprocess, "run", run)

    assert (
        escalation_run.receipt_head_state(
            b"receipt",
            receipt_final_name=receipt_name,
            roadmap_root=roadmap_root,
            receipt_worktree=tmp_path,
            namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
        )
        == "matching"
    )
    assert [call[1] for call in calls] == ["rev-parse", "ls-tree", "show"]


def test_receipt_helpers_require_an_explicit_namespace_and_never_default_to_escalations(
    tmp_path: Path,
) -> None:
    """The escalation namespace is retired, so no helper may silently fall back to it."""
    with pytest.raises(TypeError):
        escalation_run.receipt_head_state(  # type: ignore[call-arg]
            b"receipt",
            receipt_final_name="a" * 64,
            roadmap_root=tmp_path,
            receipt_worktree=tmp_path,
        )
    with pytest.raises(TypeError):
        escalation_run.receipt_path_is_within_worktree(  # type: ignore[call-arg]
            tmp_path, tmp_path
        )


def test_receipt_path_outside_the_worktree_is_not_within_it(tmp_path: Path) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    outside_root = tmp_path / "elsewhere" / "roadmaps" / _SLUG

    assert not escalation_run.receipt_path_is_within_worktree(
        outside_root, worktree, namespace=EvidenceNamespace.DECISION_SETTLEMENTS
    )
    assert escalation_run.receipt_path_is_within_worktree(
        worktree / "roadmaps" / _SLUG,
        worktree,
        namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
    )


def test_receipt_head_state_is_unreadable_without_a_worktree(tmp_path: Path) -> None:
    assert (
        escalation_run.receipt_head_state(
            b"receipt",
            receipt_final_name="a" * 64,
            roadmap_root=tmp_path,
            receipt_worktree=None,
            namespace=EvidenceNamespace.DECISION_SETTLEMENTS,
        )
        == "unreadable"
    )
