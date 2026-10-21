"""Checkpoint command module — the on-disk resume-cache verb.

Holds the ``checkpoint`` handler (``cmd_checkpoint``) plus its two
path-safety helpers (``_validate_checkpoint_arg`` / ``_safe_under_root``)
and a :func:`register` that contributes the ``checkpoint`` subparser to
the shared ``add_subparsers`` action (see :mod:`plan_tool.cli.parser`).

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`) and
the domain packages — never :mod:`plan_tool.cli.app`. ``app`` re-imports
these names back into its own namespace so the package surface stays
intact.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from plan_tool.checkpoint import checkpoint_dir, checkpoints_root
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.style import error, warn


def _validate_checkpoint_arg(value: str, *, kind: str) -> Optional[str]:
    """Reject slug/name arguments that could escape the checkpoints root.

    Returns ``None`` for valid inputs; an error message otherwise. Kept
    strict because the argument is joined into a filesystem path and
    used to read or delete files — anything that lets the joined path
    resolve outside ``<repo>/.plan-tool/checkpoints/`` is a path-
    traversal hole.

    Rejected shapes:

    - empty string (would collapse the join to the parent directory)
    - any occurrence of ``/`` or ``\\`` (multi-component injection)
    - any occurrence of ``..`` (parent-directory escape)
    - leading ``.`` (hidden file / current-dir markers; e.g. ``.``,
      ``.git``, ``..hidden``)
    """
    if not value:
        return f"{kind} cannot be empty"
    if "/" in value or "\\" in value:
        return f"{kind} cannot contain '/' or '\\' (got {value!r})"
    if ".." in value:
        return f"{kind} cannot contain '..' (got {value!r})"
    if value.startswith("."):
        return f"{kind} cannot start with '.' (got {value!r})"
    return None


def _safe_under_root(candidate: Path, root: Path) -> bool:
    """Defense-in-depth: ensure ``candidate`` resolves under ``root``.

    ``_validate_checkpoint_arg`` should catch every traversal attempt
    upstream, but the cost of a final resolve-and-compare is one
    syscall per call site and it covers exotic encodings (Unicode
    normalization, ``%2F``-escaped bytes from non-shell callers) we'd
    otherwise miss.
    """
    try:
        candidate.resolve().relative_to(root.resolve())
    except (ValueError, OSError):
        return False
    return True


def cmd_checkpoint(args: argparse.Namespace) -> int:
    """Inspect and manage on-disk resume checkpoints (state management).

    Intent: give the operator visibility into and control over
    plan-tool's own claude-response cache under
    ``<repo>/.plan-tool/checkpoints/``. The cache is what lets
    :func:`cmd_create` and :func:`cmd_detail` resume after a crash
    without re-spending a claude call. This subcommand never touches
    plan files or invokes claude — it only manipulates plan-tool's
    own state. New state-management actions (e.g. cleaning saved
    reviews under ``plan-details/<slug>/reports/``) belong here, not on
    a plan-data subcommand.

    Three actions, dispatched via ``args.action``:

    - ``list`` — show every cached checkpoint under
      ``<repo>/.plan-tool/checkpoints/`` with its slug, name, age, and
      payload size. No claude calls; no plan file required.
    - ``show <slug>/<checkpoint>`` — print one checkpoint's payload to stdout
      so a user can inspect what the cache will replay before
      re-running with resume. The ``.json`` extension is optional —
      ``show foo/bar`` and ``show foo/bar.json`` both work.
    - ``clear <slug>`` (or ``--all``) — delete cached checkpoints. Used
      after abandoning a plan or to force a fresh claude call without
      passing ``--no-resume`` on every invocation.

    Exit codes:

    - ``0`` — successful (including ``clear`` on a non-existent slug,
      since clear is idempotent — re-running it shouldn't surprise
      with a non-zero exit).
    - ``1`` — partial failure (``clear`` couldn't remove some files,
      ``show`` target missing or unreadable).
    - ``2`` — invalid arguments (traversal attempt, missing
      ``--all``/slug, missing slash in ``show`` target).
    """
    try:
        repo_root = _resolve_cmd_repo_root(args)
    except FileNotFoundError as exc:
        error(str(exc))
        return 2

    root = checkpoints_root(repo_root)

    if args.action == "list":
        if not root.is_dir():
            print(f"no checkpoints (root {root} does not exist)")
            return 0
        rows: list[tuple[str, str, str, int]] = []
        now = datetime.now(timezone.utc)
        # Filter symlinks at both levels so a malicious symlink under
        # ``checkpoints/`` (or a slug dir symlinked to ``/etc``) can't
        # cause the list walk to read files outside the root.
        for slug_dir in sorted(
            p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
        ):
            for ckpt_file in sorted(slug_dir.glob("*.json")):
                if ckpt_file.is_symlink() or not ckpt_file.is_file():
                    continue
                try:
                    obj = json.loads(ckpt_file.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError):
                    rows.append((slug_dir.name, ckpt_file.stem, "?", 0))
                    continue
                created_at = obj.get("created_at", "")
                try:
                    ts = datetime.fromisoformat(created_at)
                    if ts.tzinfo is None:
                        ts = ts.replace(tzinfo=timezone.utc)
                    age_min = int((now - ts).total_seconds() // 60)
                    age = f"{age_min}m" if age_min < 60 else f"{age_min // 60}h"
                except (ValueError, TypeError):
                    age = "?"
                payload = obj.get("payload", "") or ""
                rows.append((slug_dir.name, ckpt_file.stem, age, len(payload)))
        if not rows:
            print(f"no checkpoints under {root}")
            return 0
        print(f"{'slug':<40}  {'name':<30}  {'age':>6}  {'bytes':>8}")
        for slug, name, age, size in rows:
            print(f"{slug:<40}  {name:<30}  {age:>6}  {size:>8}")
        return 0

    if args.action == "show":
        if "/" not in args.target:
            error(
                "show requires <slug>/<checkpoint> (e.g. "
                "my-plan/detail-step-01)"
            )
            return 2
        slug, name = args.target.split("/", 1)
        # Optional ``.json`` suffix — strip so the user can paste a
        # filename from ``list`` output or a tab-completion guess
        # without a confusing "no such checkpoint" miss.
        if name.endswith(".json"):
            name = name[: -len(".json")]
        for value, kind in ((slug, "slug"), (name, "name")):
            err = _validate_checkpoint_arg(value, kind=kind)
            if err is not None:
                error(f"{err}")
                return 2
        ckpt_file = checkpoint_dir(repo_root, slug) / f"{name}.json"
        if not _safe_under_root(ckpt_file, root):
            error(
                f"refusing to read outside {root} (resolved: "
                f"{ckpt_file})"
            )
            return 2
        if not ckpt_file.is_file() or ckpt_file.is_symlink():
            print(f"no such checkpoint: {ckpt_file}", file=sys.stderr)
            return 1
        try:
            obj = json.loads(ckpt_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"error reading {ckpt_file}: {exc}", file=sys.stderr)
            return 1
        # Metadata to stderr, payload to stdout — pipeable.
        print(
            f"# checkpoint {slug}/{name}\n"
            f"# created_at: {obj.get('created_at', '?')}\n"
            f"# input_hash: {obj.get('input_hash', '?')}\n"
            f"# schema_version: {obj.get('schema_version', '?')}",
            file=sys.stderr,
        )
        sys.stdout.write(obj.get("payload", "") or "")
        return 0

    if args.action == "clear":
        # ``--all`` wipes everything under the root; otherwise a single
        # slug must be named. Refuse "no slug + no --all" so a missing
        # arg can't accidentally nuke the cache.
        if args.all_slugs:
            if not root.is_dir():
                print(f"no checkpoints to clear (root {root} does not exist)")
                return 0
            removed = 0
            failed = 0
            # Skip symlinked dirs to keep a malicious link from making
            # ``clear --all`` reach into the rest of the filesystem.
            for slug_dir in [
                p for p in root.iterdir() if p.is_dir() and not p.is_symlink()
            ]:
                for ckpt_file in slug_dir.glob("*.json"):
                    if ckpt_file.is_symlink():
                        continue
                    try:
                        ckpt_file.unlink()
                        removed += 1
                    except OSError as exc:
                        failed += 1
                        warn(
                            f"could not remove {ckpt_file}: {exc}"
                        )
                # Rmdir the slug dir if it's empty afterwards. Non-empty
                # dirs (stray non-json files) survive — that's fine.
                try:
                    slug_dir.rmdir()
                except OSError:
                    pass
            if failed:
                print(
                    f"removed {removed} checkpoint file(s); "
                    f"{failed} could not be removed (see warnings above)"
                )
                return 1
            print(f"removed {removed} checkpoint file(s)")
            return 0
        if args.slug is None:
            error(
                "clear requires either --all or a <slug> "
                "(e.g. plan-tool checkpoint clear my-plan)"
            )
            return 2
        err = _validate_checkpoint_arg(args.slug, kind="slug")
        if err is not None:
            error(f"{err}")
            return 2
        slug_dir = checkpoint_dir(repo_root, args.slug)
        if not _safe_under_root(slug_dir, root):
            error(
                f"refusing to operate outside {root} "
                f"(resolved: {slug_dir})"
            )
            return 2
        if slug_dir.is_symlink() or not slug_dir.is_dir():
            # Treat symlinks and missing dirs the same: nothing to
            # clear. Idempotent — same exit-0 contract.
            print(f"no checkpoints for slug {args.slug!r}")
            return 0
        removed = 0
        failed = 0
        for ckpt_file in slug_dir.glob("*.json"):
            if ckpt_file.is_symlink():
                continue
            try:
                ckpt_file.unlink()
                removed += 1
            except OSError as exc:
                failed += 1
                warn(
                    f"could not remove {ckpt_file}: {exc}"
                )
        try:
            slug_dir.rmdir()
        except OSError:
            pass
        if failed:
            print(
                f"removed {removed} checkpoint file(s) for {args.slug!r}; "
                f"{failed} could not be removed (see warnings above)"
            )
            return 1
        print(f"removed {removed} checkpoint file(s) for {args.slug!r}")
        return 0

    error(f"unknown checkpoint action {args.action!r}")
    return 2


def register(subparsers) -> dict[str, Handler]:
    """Add the ``checkpoint`` subparser and return its dispatch map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    p_checkpoint = sub.add_parser(
        "checkpoint",
        help=(
            "inspect / manage on-disk resume checkpoints under "
            "<repo>/.plan-tool/checkpoints/. Subactions: list / show / clear."
        ),
        parents=[yes_parent],
    )
    p_checkpoint_sub = p_checkpoint.add_subparsers(
        dest="action", required=True
    )
    p_checkpoint_sub.add_parser(
        "list",
        help="list every cached checkpoint with slug, name, age, and bytes",
        parents=[yes_parent],
    )
    p_checkpoint_show = p_checkpoint_sub.add_parser(
        "show",
        help=(
            "print one checkpoint's payload (metadata to stderr, "
            "payload to stdout)"
        ),
        parents=[yes_parent],
    )
    p_checkpoint_show.add_argument(
        "target",
        help=(
            "checkpoint identifier in the form <slug>/<checkpoint>, where "
            "<checkpoint> is the per-plan name shown in the 'name' column "
            "of `plan-tool checkpoint list` (e.g. my-plan/detail-step-01)"
        ),
    )
    p_checkpoint_clear = p_checkpoint_sub.add_parser(
        "clear",
        help=(
            "delete cached checkpoints. Pass a <slug> to clear one "
            "plan's cache, or --all to wipe everything."
        ),
        parents=[yes_parent],
    )
    p_checkpoint_clear.add_argument(
        "slug",
        nargs="?",
        default=None,
        help="plan slug whose checkpoints to clear (omit when using --all)",
    )
    p_checkpoint_clear.add_argument(
        "--all",
        dest="all_slugs",
        action="store_true",
        help="clear every checkpoint in the repo's checkpoints directory",
    )

    return {
        "checkpoint": cmd_checkpoint,
    }
