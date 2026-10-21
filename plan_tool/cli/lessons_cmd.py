"""Lessons command module — the ``lessons`` maintenance verb.

Holds the ``lessons`` action dispatcher (``cmd_lessons``), its
``consolidate`` body (``cmd_lessons_consolidate``), and the three
rendering helpers (``_print_consolidate_summary`` /
``_recurrence_annotation`` / ``_render_lessons_unified_diff``), plus a
:func:`register` that contributes the ``lessons`` subparser to the
shared ``add_subparsers`` action (see :mod:`plan_tool.cli.parser`).

Named ``lessons_cmd`` (not ``lessons``) so ``from plan_tool.cli import
lessons`` can never shadow the domain module :mod:`plan_tool.lessons`.

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`) and
the domain packages — never :mod:`plan_tool.cli.app`. ``app`` re-imports
these names back into its own namespace so the package surface stays
intact.

``cmd_lessons_consolidate`` reads ``shell_equivalence_invoker`` as a
bare-name **module global**, so tests that stub the invoker must
``setattr`` it on *this* module (``plan_tool.cli.lessons_cmd``), not on
``app``'s re-imported alias — dispatch routes the handler from here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from plan_tool.cli.console import _atomic_write, _repo_rel
from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.lessons import (
    DEFAULT_EQUIVALENCE_CONFIDENCE,
    EquivalenceInvoker,
    discover_lessons_files,
    find_lesson_equivalences,
    load_warnings,
    parse_existing_entries,
    recurrence_counts,
    recurrence_weight_from_counts,
    render_consolidated_file,
    shell_equivalence_invoker,
)
from plan_tool.run_log import RunLogWriter
from plan_tool.style import colorize_diff


def cmd_lessons(args: argparse.Namespace) -> int:
    """Maintenance verbs over plan-tool's lessons files (state management).

    Intent: reconcile near-duplicate / contradictory bullets that pile
    up in ``general.md`` / ``project.md`` / per-plan ``lessons.md``
    across many ``plan-tool detail`` and ``plan-tool reconcile-plan``
    iterations. The dedup heuristic in ``_append_to_file``
    (case-insensitive substring match on ``rule`` text) silently lets
    semantic near-duplicates and contradictions through; this verb runs
    the lessons-equivalence primitive against every discovered file and
    surfaces what the write path missed.

    Sub-actions:
      - ``consolidate``: scan, judge, and either diff or rewrite.

    Future sub-actions (``lessons clear`` to drop the warning log,
    ``lessons grep`` to search machine entries by rule text) slot in
    here.
    """
    if args.action == "consolidate":
        return cmd_lessons_consolidate(args)
    print(f"error: unknown lessons action: {args.action}", file=sys.stderr)
    return 2


def _print_consolidate_summary(
    per_file: list,  # list[tuple[LessonsFile, list[LessonEntry], EquivalenceFindings]]
    *,
    repo_root: Path,
    recurrence: Optional[dict] = None,  # {(candidate_lower, matched_lower): count}
) -> None:
    """Print a per-file structured summary of duplicate/conflict findings.

    Each file renders a header line followed by one bullet per finding.
    Files with zero findings render only the header. Output is a normal
    product (stdout), not a diagnostic.

    When ``recurrence`` (the ``{(candidate_lower, matched_lower): count}``
    map read from ``.plan-tool/lessons-warnings.jsonl``) holds counts,
    each file's findings are ordered by ``(-weight, left_index)`` —
    findings re-flagged across many prior detail/review iterations sort
    first — and a ``recurrence=N`` annotation is appended to every bullet
    whose weight exceeds the ``1.0`` floor. When ``recurrence`` is ``None``
    (``--ignore-recurrence``) or empty (no warning log), findings render in
    the primitive's returned order with no annotation. The weight function
    is rebuilt per file so the 1-based finding indices key against that
    file's own entries.
    """
    for f, entries, findings in per_file:
        rel = _repo_rel(f.path, repo_root)
        print(
            f"### {rel} · kind={f.kind} · {len(entries)} entries · "
            f"{len(findings.duplicates)} duplicates · "
            f"{len(findings.conflicts)} conflicts"
        )
        if not recurrence:
            weight_fn = lambda _finding: 1.0  # noqa: E731 — local no-op weight
            dups = list(findings.duplicates)
            cons = list(findings.conflicts)
        else:
            entries_by_index = {i: e for i, e in enumerate(entries, start=1)}
            weight_fn = recurrence_weight_from_counts(
                recurrence, entries_by_index=entries_by_index
            )
            dups = sorted(
                findings.duplicates, key=lambda d: (-weight_fn(d), d.left_index)
            )
            cons = sorted(
                findings.conflicts, key=lambda c: (-weight_fn(c), c.left_index)
            )
        for d in dups:
            ann = _recurrence_annotation(weight_fn(d))
            print(
                f"- DUP[{d.confidence:.2f}] #{d.left_index} ↔ #{d.right_index}"
                f"{ann}  {d.rationale}  (will drop #{d.right_index})"
            )
        for c in cons:
            ann = _recurrence_annotation(weight_fn(c))
            print(
                f"- CONFLICT[{c.confidence:.2f}] #{c.left_index} ↔ "
                f"#{c.right_index}{ann}  {c.rationale}  (manual review required)"
            )


def _recurrence_annotation(weight: float) -> str:
    """Render the ``recurrence=N`` suffix for a finding's weight.

    ``N`` is the recurrence count (``weight - 1.0`` floor); returns the
    empty string when ``N == 0`` so first-time findings don't get noisy
    ``recurrence=0`` clutter."""
    n = int(weight - 1.0)
    return f" recurrence={n}" if n > 0 else ""


def _render_lessons_unified_diff(
    path: Path,
    original: str,
    new_body: str,
    *,
    repo_root: Path,
) -> str:
    """Render a unified diff for one rewritten lessons file.

    Mirrors the per-file shape ``launcher._render_diff`` established:
    ``fromfile=a/<rel>``, ``tofile=b/<rel>``, ``n=3``.
    """
    import difflib as _difflib

    rel = _repo_rel(path, repo_root)
    diff_lines = _difflib.unified_diff(
        original.splitlines(keepends=True),
        new_body.splitlines(keepends=True),
        fromfile=f"a/{rel}",
        tofile=f"b/{rel}",
        n=3,
    )
    return "".join(diff_lines)


def cmd_lessons_consolidate(args: argparse.Namespace) -> int:
    """Scan known lessons files for duplicates/conflicts; diff or rewrite.

    Diff by default (never touches disk); ``--apply`` rewrites the
    affected files behind a confirmation gate. Headless callers never
    silently rewrite — ``--apply`` against a non-TTY requires ``-y``.
    Only duplicates drive a drop; conflicts are surfaced for manual
    edit and never auto-removed.

    Findings are ordered by recurrence: the warning log
    (``.plan-tool/lessons-warnings.jsonl``) is read to count how often
    each candidate↔prior pair has been re-flagged, and the summary sorts
    repeat findings ahead of first-time ones. ``--ignore-recurrence``
    skips the log read and renders the raw primitive order.
    """
    ctx = _load_context(args)

    # 1. Discover. Order is deterministic (general, project, per-plan in
    #    entries order) so summary/diff output is reproducible.
    discovered = discover_lessons_files(ctx.repo_root, ctx.entries)
    if args.plan is not None:
        discovered = [
            f for f in discovered
            if f.kind == "per-plan" and f.plan_slug == args.plan
        ]
        if not discovered:
            print(
                f"error: no per-plan lessons file found for plan "
                f"{args.plan!r}",
                file=sys.stderr,
            )
            return 2

    if not discovered:
        print(
            "no lessons files discovered "
            "(general.md / project.md / per-plan lessons.md all absent)."
        )
        return 0

    # 2. Headless-no-TTY contract. --apply against a non-TTY without -y
    #    refuses to rewrite. Diff-only (default) is always safe headless.
    if (
        args.apply
        and not args.dry_run
        and not args.yes
        and not sys.stdin.isatty()
    ):
        print(
            "error: --apply needs -y or a TTY (refusing to rewrite "
            f"{len(discovered)} file(s) unattended).",
            file=sys.stderr,
        )
        return 2

    # 3. Run-log open so `runs list/show` can attribute the claude spend.
    run_logger = RunLogWriter.start(
        repo_root=ctx.repo_root,
        slug="lessons-consolidate",
        command="lessons-consolidate",
        argv=list(sys.argv[1:]),
        plan_path=None,
        step_filter=None,
        flags={
            "apply": args.apply,
            "dry_run": args.dry_run,
            "yes": args.yes,
            "plan": args.plan,
            "min_confidence": args.min_confidence,
        },
    )
    rc = 0
    err_msg: Optional[str] = None
    try:
        # 4. Per file: parse entries, call the primitive (intra-set:
        #    candidates=()), record findings. Empty files are skipped.
        per_file: list = []
        invoker: EquivalenceInvoker = shell_equivalence_invoker
        for f in discovered:
            body = f.path.read_text(encoding="utf-8") if f.path.is_file() else ""
            entries = parse_existing_entries(body)
            if not entries:
                continue
            findings = find_lesson_equivalences(
                entries,
                (),
                invoker=invoker,
                repo_root=ctx.repo_root,
                resume=not args.no_resume,
                min_confidence=args.min_confidence,
            )
            per_file.append((f, entries, findings))

        # 5a. Recurrence weighting: read the warning log and count repeat
        #     candidate↔matched-prior pairs so the summary can sort
        #     re-flagged findings first. --ignore-recurrence skips the
        #     read entirely (raw primitive order, no annotation).
        recurrence = (
            None
            if args.ignore_recurrence
            else recurrence_counts(load_warnings(ctx.repo_root))
        )

        # 5b. Structured summary (always — diff and apply both lead with it).
        _print_consolidate_summary(
            per_file, repo_root=ctx.repo_root, recurrence=recurrence
        )

        if all(findings.is_empty for _f, _e, findings in per_file):
            print(
                "no duplicate or conflict findings above threshold "
                f"({args.min_confidence}). nothing to consolidate."
            )
            return rc

        # 6. Compute per-file proposed rewrites. ONLY duplicates drive a
        #    drop — conflicts are never auto-removed (silent nuance loss).
        rewrites: list = []  # (LessonsFile, original, new_body)
        for f, _entries, findings in per_file:
            if not findings.duplicates:
                continue
            # Drop the right_index entry of each duplicate (1-based →
            # 0-based); dedupe when the same right_index recurs.
            drops = frozenset(d.right_index - 1 for d in findings.duplicates)
            original = f.path.read_text(encoding="utf-8")
            new_body = render_consolidated_file(original, drops)
            if new_body != original:
                rewrites.append((f, original, new_body))

        # 7. Diff mode (default). Emit unified diffs per file; never write.
        if not args.apply:
            if not rewrites:
                print(
                    "(conflicts present but no auto-removable duplicates; "
                    "manual edit required.)"
                )
                return rc
            for f, original, new_body in rewrites:
                print(
                    colorize_diff(
                        _render_lessons_unified_diff(
                            f.path, original, new_body, repo_root=ctx.repo_root
                        )
                    ),
                    end="",
                )
            return rc

        # 8. Apply --dry-run: print the rewrite product (NOT the diff).
        if args.dry_run:
            for f, _original, new_body in rewrites:
                rel = _repo_rel(f.path, ctx.repo_root)
                print(f"# === {rel} (rewrite preview) ===")
                print(new_body, end="")
            return rc

        # 9. TTY confirmation gate (skipped by -y; non-TTY already gated).
        if not args.yes and sys.stdin.isatty():
            import builtins

            n = len(rewrites)
            answer = (
                builtins.input(f"\nRewrite {n} lessons file(s)? [y/N] ")
                .strip()
                .lower()
            )
            if answer not in ("y", "yes"):
                print("aborted")
                return rc

        # 10. Write each affected file atomically.
        for f, _original, new_body in rewrites:
            _atomic_write(f.path, new_body)
            print(f"rewrote {_repo_rel(f.path, ctx.repo_root)}")
        return rc
    except Exception as exc:  # noqa: BLE001 — record then re-raise to main.
        rc = 1
        err_msg = str(exc)
        raise
    finally:
        run_logger.run_end(
            outcome=("success" if rc == 0 else "error"),
            rc=rc,
            error=err_msg,
        )


def register(subparsers) -> dict[str, Handler]:
    """Add the ``lessons`` subparser (and its sub-action) and return its map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    p_lessons = sub.add_parser(
        "lessons",
        help=(
            "maintenance verbs over plan-tool's lessons files "
            "(general.md / project.md / per-plan lessons.md). "
            "Subactions: consolidate."
        ),
        parents=[yes_parent],
    )
    p_lessons_sub = p_lessons.add_subparsers(dest="action", required=True)

    p_lessons_consolidate = p_lessons_sub.add_parser(
        "consolidate",
        help=(
            "scan lessons files for duplicate/conflict findings using the "
            "lessons-equivalence primitive. Default: emit a unified diff "
            "for review. --apply rewrites with confirmation; --apply "
            "--dry-run prints the rewrite to stdout."
        ),
        parents=[yes_parent],
    )
    p_lessons_consolidate.add_argument(
        "--apply",
        action="store_true",
        help=(
            "rewrite the affected files in place (after a Y/N confirmation "
            "on a TTY; silent with -y). Default: emit a unified diff to "
            "stdout and exit without touching disk."
        ),
    )
    p_lessons_consolidate.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help=(
            "with --apply: print the rewritten file body(ies) to stdout "
            "without touching disk (useful for piping into diff tools). "
            "Without --apply: no-op (the default mode already does not "
            "write)."
        ),
    )
    p_lessons_consolidate.add_argument(
        "--plan",
        default=None,
        metavar="SLUG",
        help=(
            "scope the run to one plan's per-plan lessons.md (file at the "
            "path declared by that plan's `lessons:` frontmatter). "
            "Default: every discovered lessons file."
        ),
    )
    p_lessons_consolidate.add_argument(
        "--min-confidence",
        type=float,
        default=DEFAULT_EQUIVALENCE_CONFIDENCE,
        dest="min_confidence",
        metavar="FLOAT",
        help=(
            f"primitive threshold below which findings are dropped "
            f"(default: {DEFAULT_EQUIVALENCE_CONFIDENCE}). Lower to see "
            f"borderline cases; raise to require higher claude confidence "
            f"before a duplicate drives a drop."
        ),
    )
    p_lessons_consolidate.add_argument(
        "--no-resume",
        action="store_true",
        dest="no_resume",
        help=(
            "force a fresh equivalence-primitive call per file, ignoring "
            "any cached payload under "
            ".plan-tool/checkpoints/lessons-equivalence/. The input hash "
            "already invalidates the cache when the lessons body changes; "
            "pass this when re-spending tokens is the explicit goal."
        ),
    )
    p_lessons_consolidate.add_argument(
        "--ignore-recurrence",
        action="store_true",
        dest="ignore_recurrence",
        help=(
            "skip the recurrence weighting (don't read "
            ".plan-tool/lessons-warnings.jsonl). Default: findings flagged "
            "across many prior detail/review iterations sort ahead of "
            "first-time findings, annotated with recurrence=N. Pass this "
            "to see the raw primitive ordering when investigating noise "
            "patterns."
        ),
    )

    return {
        "lessons": cmd_lessons,
    }
