"""Benchmark command module — the ``bench`` verb (run / report).

``bench run`` executes the task-family × backend × trial matrix over the
step-1 corpus (``benchmarks/corpus/``), writing one JSONL record per cell trial
under ``<repo>/.plan-tool/bench/runs/<stamp>/``. ``bench report`` renders a
run's records into a scored per-(family, backend) comparison (quality median +
spread, wall-clock, token/cost totals, failure/retry rates) as markdown or JSON,
and ``--write-recommendations`` regenerates ``docs/evidence/backend-recommendations.md``.

Clean leaf-importing command module (per the ``run_cmd`` precedent): imports
the engine (:mod:`plan_tool.bench`), the cycle-free CLI leaves
(``context`` / ``parser``) and ``style`` — never the app module and never the
shared apply-action builder leaf. ``app`` re-imports ``cmd_bench`` back so the
package surface and the parser↔dispatch correspondence keep resolving.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Optional

from plan_tool.bench import (
    RECORDS_FILENAME,
    bench_run_dir,
    bench_runs_root,
    build_quality_report,
    recommend_per_family,
    render_recommendations_doc,
    render_report_markdown,
    report_to_dict,
    run_bench_matrix,
    write_recommendations_doc,
)
from plan_tool.cli.context import _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.run_log import new_run_id
from plan_tool.style import error, note


def _split_csv(value: Optional[str]) -> Optional[list[str]]:
    """Parse a ``--backends`` / ``--families`` CSV into a list (or None)."""
    if not value:
        return None
    items = [part.strip() for part in value.split(",") if part.strip()]
    return items or None


def _cmd_bench_run(args: argparse.Namespace, *, repo_root: Path) -> int:
    """Run the matrix and print where the records landed."""
    stamp = args.stamp or new_run_id()
    corpus_root = (
        Path(args.corpus_root)
        if args.corpus_root
        else repo_root / "benchmarks" / "corpus"
    )
    if not corpus_root.is_dir():
        error(f"corpus root not found: {corpus_root}")
        return 1
    try:
        summary = run_bench_matrix(
            repo_root,
            corpus_root=corpus_root,
            stamp=stamp,
            backends=_split_csv(args.backends),
            families=_split_csv(args.families),
            trials=args.trials,
            timeout_s=args.timeout,
            resume=args.resume,
        )
    except KeyError as exc:
        # Unknown family name passed to --families.
        error(f"unknown family: {exc}")
        return 2
    except ValueError as exc:
        # Unknown backend name passed to --backends.
        error(str(exc))
        return 2
    note(
        f"bench run {stamp}: {summary.records_written} record(s) written, "
        f"{summary.skipped} skipped ({summary.cells} cell(s))"
    )
    print(bench_run_dir(repo_root, stamp) / RECORDS_FILENAME)
    return 0


def _cmd_bench_report(args: argparse.Namespace, *, repo_root: Path) -> int:
    """Render one bench run's scored per-(family, backend) report.

    Builds the quality report (scoring records on the fly if needed), then emits
    the markdown table, the JSON twin, or — with ``--write-recommendations`` —
    the regenerated ``docs/evidence/backend-recommendations.md``.
    """
    run_dir = bench_run_dir(repo_root, args.stamp)
    if not run_dir.is_dir() or not (run_dir / RECORDS_FILENAME).is_file():
        error(
            f"no bench run found for stamp {args.stamp!r} under "
            f"{bench_runs_root(repo_root)}"
        )
        return 1
    corpus_root = (
        Path(args.corpus_root)
        if args.corpus_root
        else repo_root / "benchmarks" / "corpus"
    )
    report = build_quality_report(run_dir, corpus_root=corpus_root)

    if args.write_recommendations:
        recommendations = recommend_per_family(report)
        text = render_recommendations_doc(report, recommendations)
        path = write_recommendations_doc(repo_root, text)
        note(
            f"wrote recommendations for {len(recommendations)} family(ies) "
            f"({'STALE corpus' if report.is_stale else 'corpus current'})"
        )
        print(path)
        return 0

    if args.format == "json":
        print(json.dumps(report_to_dict(report), indent=2))
        return 0

    print(render_report_markdown(report))
    return 0


def cmd_bench(args: argparse.Namespace) -> int:
    """Dispatch ``bench run`` / ``bench report`` after resolving the repo root."""
    try:
        repo_root = _resolve_cmd_repo_root(args)
    except FileNotFoundError as exc:
        error(str(exc))
        return 2

    if args.action == "run":
        return _cmd_bench_run(args, repo_root=repo_root)
    if args.action == "report":
        return _cmd_bench_report(args, repo_root=repo_root)
    error(f"unknown bench action {args.action!r}")
    return 2


def register(subparsers) -> dict[str, Handler]:
    """Add the ``bench`` subparser (run / report) and return its dispatch map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`.
    """
    yes_parent = make_yes_parent()

    p_bench = subparsers.add_parser(
        "bench",
        help=(
            "run the backend-quality benchmark matrix and report raw results. "
            "Subactions: run / report."
        ),
        parents=[yes_parent],
    )
    p_bench_sub = p_bench.add_subparsers(dest="action", required=True)

    p_run = p_bench_sub.add_parser(
        "run",
        help="run the task-family × backend × trial matrix over the corpus",
        parents=[yes_parent],
    )
    p_run.add_argument(
        "--backends",
        default=None,
        help="comma-separated backend names to iterate (default: all registered)",
    )
    p_run.add_argument(
        "--families",
        default=None,
        help=(
            "comma-separated family names to iterate (default: all — proposal, "
            "detail, reconcile, implementation, apply)"
        ),
    )
    p_run.add_argument(
        "--trials",
        type=int,
        default=3,
        metavar="N",
        help="trials per cell (default: 3)",
    )
    p_run.add_argument(
        "--timeout",
        type=int,
        default=600,
        dest="timeout",
        metavar="SECONDS",
        help=(
            "per-cell wall-clock cap; a slow cell records failure_kind=timeout "
            "and the matrix continues (default: 600)"
        ),
    )
    p_run.add_argument(
        "--no-resume",
        action="store_false",
        dest="resume",
        help=(
            "re-run completed cells instead of skipping them (default: resume, "
            "skipping cells already present for the stamp)"
        ),
    )
    p_run.add_argument(
        "--stamp",
        default=None,
        help="run stamp / directory name (default: a fresh timestamp). Reuse to resume.",
    )
    p_run.add_argument(
        "--corpus-root",
        default=None,
        dest="corpus_root",
        help="override the corpus root (default: <repo>/benchmarks/corpus)",
    )

    p_report = p_bench_sub.add_parser(
        "report",
        help="render one bench run's scored per-(family, backend) report",
        parents=[yes_parent],
    )
    p_report.add_argument(
        "--stamp",
        required=True,
        help="which run stamp (directory under .plan-tool/bench/runs/) to report",
    )
    p_report.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="output format for the report (default: markdown)",
    )
    p_report.add_argument(
        "--write-recommendations",
        action="store_true",
        dest="write_recommendations",
        help=(
            "render docs/evidence/backend-recommendations.md from this run and print its "
            "path (a regenerable artifact, never directly edited)"
        ),
    )
    p_report.add_argument(
        "--corpus-root",
        default=None,
        dest="corpus_root",
        help=(
            "override the corpus root used for on-the-fly scoring + the "
            "staleness drift recompute (default: <repo>/benchmarks/corpus)"
        ),
    )

    return {"bench": cmd_bench}
