"""Evidence-receipt Git helpers shared by roadmap receipt publishers.

Only the decision-settlement receipt publisher consumes these; the escalation
receipt runner is gone. Each helper takes the evidence namespace explicitly.
"""

from __future__ import annotations

from pathlib import Path
import subprocess
from typing import Callable, Literal, TypeAlias

from plan_tool.roadmap_evidence_store import EvidenceNamespace, namespace_relative_components


ReceiptCommitter: TypeAlias = Callable[[Path, Path, str], tuple[int, str]]
ReceiptHeadState: TypeAlias = Literal["matching", "missing", "different", "unreadable"]


def receipt_worktree_for_plans_dir(plans_dir: Path) -> Path | None:
    """Resolve the Git worktree that contains the configured plans directory."""
    configured_plans_dir = Path(plans_dir)
    for directory in (configured_plans_dir, configured_plans_dir.parent):
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=directory,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
            )
        except OSError:
            continue
        if result.returncode != 0:
            continue
        output = result.stdout.strip()
        if not output:
            continue
        try:
            return Path(output).resolve()
        except OSError:
            continue
    return None


def _receipt_final_path(
    roadmap_root: Path, receipt_final_name: str, *, namespace: EvidenceNamespace
) -> Path:
    """Return one namespace's exact final path without scanning its directory."""
    return roadmap_root.joinpath(
        *namespace_relative_components(namespace), receipt_final_name
    )


def receipt_path_is_within_worktree(
    roadmap_root: Path,
    receipt_worktree: Path,
    *,
    namespace: EvidenceNamespace,
) -> bool:
    """Ensure an eventual receipt final has a Git-relative exact path."""
    try:
        _receipt_final_path(roadmap_root, "0" * 64, namespace=namespace).resolve().relative_to(
            receipt_worktree.resolve()
        )
    except (OSError, ValueError):
        return False
    return True


def receipt_head_state(
    receipt_data: bytes,
    *,
    receipt_final_name: str,
    roadmap_root: Path,
    receipt_worktree: Path | None,
    namespace: EvidenceNamespace,
) -> ReceiptHeadState:
    """Compare stored receipt bytes with their exact path in the controlling HEAD."""
    if receipt_worktree is None or not receipt_path_is_within_worktree(
        roadmap_root, receipt_worktree, namespace=namespace
    ):
        return "unreadable"
    try:
        relative_path = _receipt_final_path(
            roadmap_root, receipt_final_name, namespace=namespace
        ).resolve().relative_to(receipt_worktree.resolve()).as_posix()
    except (OSError, ValueError):
        return "unreadable"
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", "HEAD"],
            cwd=receipt_worktree,
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    except OSError:
        return "unreadable"
    if head.returncode == 1:
        return "missing"
    if head.returncode != 0:
        return "unreadable"
    head_revision = head.stdout.decode(errors="replace").strip()
    if not head_revision:
        return "unreadable"
    try:
        listed = subprocess.run(
            ["git", "ls-tree", "-z", head_revision, "--", relative_path],
            cwd=receipt_worktree,
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    except OSError:
        return "unreadable"
    if listed.returncode != 0:
        return "unreadable"
    if not listed.stdout:
        return "missing"
    try:
        stored = subprocess.run(
            ["git", "show", f"{head_revision}:{relative_path}"],
            cwd=receipt_worktree,
            stdin=subprocess.DEVNULL,
            capture_output=True,
        )
    except OSError:
        return "unreadable"
    if stored.returncode != 0:
        return "unreadable"
    return "matching" if stored.stdout == receipt_data else "different"
