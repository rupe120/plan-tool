"""Deterministic initialization of tracked project-level intent metadata."""

from __future__ import annotations

import argparse

from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.gitcommit import path_is_gitignored
from plan_tool.cli.parser import Handler
from plan_tool.pathutil import display_path
from plan_tool.project_profile import (
    PROJECT_PROFILE_SUBPATH,
    ProjectProfileError,
    initialize_project_profile,
    normalize_project_profile_text,
    project_profile_path,
)
from plan_tool.style import error, success


def _nonblank(value: str) -> str:
    """Normalize a CLI text value while rejecting blank input at the boundary."""
    cleaned = normalize_project_profile_text(value)
    if cleaned is None:
        raise argparse.ArgumentTypeError("must not be blank")
    return cleaned


def cmd_init(args: argparse.Namespace) -> int:
    """Create the one project-owned profile this V1 command needs."""
    repo_root = _resolve_cmd_repo_root(args)
    profile_path = project_profile_path(repo_root)
    if profile_path.exists():
        error(
            f"project profile already exists at {profile_path}; edit it and commit "
            "the revision"
        )
        return 2
    if path_is_gitignored(repo_root, profile_path):
        error(
            f"{PROJECT_PROFILE_SUBPATH.as_posix()} is gitignored; allow it before "
            "initializing because the project profile must be committed."
        )
        return 2
    try:
        path = initialize_project_profile(
            repo_root,
            intent=args.intent,
            non_goals=args.non_goal,
            decisions=args.decision,
        )
    except ProjectProfileError as exc:
        error(str(exc))
        return 2
    success(f"Initialized {display_path(path, repo_root)}.")
    print("Commit it with the confirmed project decision.")
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the deterministic, no-inference ``init`` command."""
    parser = subparsers.add_parser(
        "init",
        help="capture one confirmed project intent in a tracked profile",
    )
    parser.add_argument(
        "--intent",
        required=True,
        type=_nonblank,
        help="confirmed project-level intent; supplied by the operator, never inferred",
    )
    parser.add_argument(
        "--non-goal",
        action="append",
        default=[],
        type=_nonblank,
        help="confirmed project-level non-goal; may be repeated",
    )
    parser.add_argument(
        "--decision",
        action="append",
        default=[],
        type=_nonblank,
        help="confirmed project-level decision; may be repeated and is not categorized",
    )
    return {"init": cmd_init}
