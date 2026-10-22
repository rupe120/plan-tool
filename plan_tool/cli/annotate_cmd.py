"""Plan-annotation command module — the ``annotate`` verb.

``plan-tool annotate <path-or-glob>...`` judges existing plan / notes files
against the current code and emits two artifacts per source: an additive
``<name>.annotated.md`` (the original verbatim plus per-section
IMPLEMENTED / PARTIAL / NOT-IMPLEMENTED status blocks) and a compact
``<name>.seed.md`` carryover brief in the default seed directory for
``create --from-existing``. It
continues past per-file failures in batch mode and is read-only over each
source except the opt-in ``--archive``, which moves the original (and, for an
``N-slug.md`` plan, its sibling ``plan-details/<slug>/`` bundle) into
``archive/`` with a notice pointing at the report.

The classification engine lives in :mod:`plan_tool.annotate`; the two pure
renderers in :mod:`plan_tool.annotate_render`. This module owns only the CLI
glue: path derivation, disk writes, and the archive mutation.

Like every per-intent command module this imports only the cycle-free leaves
(:mod:`plan_tool.cli.context` / :mod:`plan_tool.cli.parser` /
:mod:`plan_tool.cli.console`) and domain packages — never
:mod:`plan_tool.cli.app`. ``cmd_annotate`` exposes an ``invoker`` keyword seam
(defaulted to :func:`plan_tool.annotate.shell_annotate_invoker`) so tests pass
a stub and never shell out; dispatch calls it with the ``Namespace`` alone.
"""

from __future__ import annotations

import argparse
import glob
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from plan_tool.seed_paths import default_seeds_dir
from plan_tool.annotate import (
    AnnotateError,
    AnnotateInvoker,
    AnnotationStatus,
    PlanAnnotation,
    classify_plan_implementation,
    shell_annotate_invoker,
)
from plan_tool.annotate_render import (
    reject_unmatched_annotation_fence,
    render_annotated_report,
    render_create_seed,
)
from plan_tool.create import CreateError, archive_existing_source
from plan_tool.locator import load_manifest_plan_paths
from plan_tool.cli.console import _report_archive_result, _short_path
from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.style import detail, error, success, warn


@dataclass(frozen=True)
class AnnotatePaths:
    """Output destinations for one source file."""

    report: Path
    seed: Path


@dataclass(frozen=True)
class AnnotateBatchResult:
    """One row in the batch summary."""

    source_path: Path
    report_path: Optional[Path]
    seed_path: Optional[Path]
    annotation: Optional[PlanAnnotation]
    error_message: str = ""

    @property
    def ok(self) -> bool:
        return self.annotation is not None and not self.error_message


@dataclass(frozen=True)
class _ExpandedAnnotateSources:
    """Resolved batch inputs plus expansion-time usage errors."""

    sources: list[Path]
    errors: list[str]


def cmd_annotate(
    args: argparse.Namespace, *, invoker: Optional[AnnotateInvoker] = None
) -> int:
    """Classify ``args.plan_file`` against the code and write the two artifacts.

    Resolves the Claude seam first (``invoker`` override → the real
    ``shell_annotate_invoker``), runs one classification pass, renders the
    additive report beside the source and the carryover seed in the default
    seed directory, preserving explicit output destinations.
    ``--archive`` moves the original with a report-pointing notice.

    Returns 2 (no artifact written) when ``--iterate`` is requested, 1 on a
    non-file source (``CreateError``) or an unparseable Claude response
    (``AnnotateError``), and 0 on success.

    See ``docs/reference/contracts/process.md`` for annotate's forward-only handoff.
    """
    if getattr(args, "iterate", False):
        error(
            "--iterate is not supported for annotate; annotate is single-pass "
            "(one classification plus deterministic report/seed rendering)."
        )
        return 2

    ctx = _load_context(args)
    expanded = _expand_annotate_sources(_raw_plan_file_args(args))
    if expanded.errors:
        for message in expanded.errors:
            error(message)
        return 2
    sources = expanded.sources
    if not sources:
        error("no plans matched")
        return 2
    if len(sources) > 1 and (args.report is not None or args.seed is not None):
        error("--report/--seed can only be used with a single annotate source")
        return 2
    output_errors = _find_duplicate_annotate_outputs(args, sources, repo_root=ctx.repo_root)
    if output_errors:
        for message in output_errors:
            error(message)
        return 2

    inv = invoker if invoker is not None else shell_annotate_invoker
    results: list[AnnotateBatchResult] = []
    for source_path in sources:
        results.append(
            _annotate_one(
                args,
                source_path=source_path,
                repo_root=ctx.repo_root,
                invoker=inv,
            )
        )

    if len(results) > 1:
        _print_batch_summary(results, repo_root=ctx.repo_root)

    return 0 if all(r.ok for r in results) else 1


def _raw_plan_file_args(args: argparse.Namespace) -> list[Path]:
    """Return parsed source path/glob arguments, preserving direct-test fallback."""
    plan_files = getattr(args, "plan_files", None)
    if plan_files is not None:
        return list(plan_files)
    return [args.plan_file]


def _expand_annotate_sources(
    path_or_globs: list[Path],
) -> _ExpandedAnnotateSources:
    """Expand path/glob arguments in CLI order, sorting each expansion."""
    out: list[Path] = []
    errors: list[str] = []
    for path_or_glob in path_or_globs:
        raw = str(path_or_glob)
        if glob.has_magic(raw):
            matches = sorted(
                p
                for p in (Path(p) for p in glob.glob(raw))
                if _is_active_plan_markdown(p)
            )
            if not matches:
                errors.append(f"no plans matched {raw}")
            out.extend(matches)
        elif path_or_glob.is_dir():
            matches = sorted(
                p
                for p in path_or_glob.rglob("*.md")
                if _is_active_plan_markdown(p)
            )
            if not matches:
                errors.append(f"no plans matched {path_or_glob}")
            out.extend(matches)
        else:
            out.append(path_or_glob)
    return _ExpandedAnnotateSources(sources=out, errors=errors)


def _is_active_plan_markdown(path: Path) -> bool:
    """True when expansion should treat ``path`` as a live annotate input."""
    if path.suffix.lower() != ".md":
        return False
    if path.name.endswith(".annotated.md") or path.name.endswith(".seed.md"):
        return False
    return not any(part in {"archive", "plan-details"} for part in path.parts)


def _annotate_one(
    args: argparse.Namespace,
    *,
    source_path: Path,
    repo_root: Path,
    invoker: AnnotateInvoker,
) -> AnnotateBatchResult:
    """Classify one source and write its report/seed artifacts."""
    resolved_source = source_path.resolve()
    paths = _derive_annotate_paths(args, source_path=resolved_source, repo_root=repo_root)

    default_seed = (
        args.seed is None and args.output_dir is None
        and getattr(args, "seed_dir", None) is None
    )
    if default_seed and (paths.seed.exists() or paths.seed.is_symlink()):
        message = (
            f"default seed already exists: {_short_path(paths.seed, repo_root)}; "
            "choose a different --seed path; explicitly passing the existing path permits replacement"
        )
        error(message)
        return AnnotateBatchResult(
            source_path=resolved_source, report_path=paths.report,
            seed_path=paths.seed, annotation=None, error_message=message,
        )

    try:
        reject_unmatched_annotation_fence(
            resolved_source.read_text(encoding="utf-8"), resolved_source
        )
    except (OSError, UnicodeDecodeError, AnnotateError) as exc:
        error(str(exc))
        return AnnotateBatchResult(
            source_path=resolved_source,
            report_path=paths.report,
            seed_path=paths.seed,
            annotation=None,
            error_message=str(exc),
        )

    try:
        annotation = classify_plan_implementation(
            resolved_source, repo_root=repo_root, invoker=invoker
        )
    except (CreateError, AnnotateError) as exc:
        error(str(exc))
        return AnnotateBatchResult(
            source_path=resolved_source,
            report_path=paths.report,
            seed_path=paths.seed,
            annotation=None,
            error_message=str(exc),
        )

    try:
        report_md = render_annotated_report(annotation)
        seed_md = render_create_seed(annotation, report_path=paths.report)
    except AnnotateError as exc:
        error(str(exc))
        return AnnotateBatchResult(
            source_path=resolved_source,
            report_path=paths.report,
            seed_path=paths.seed,
            annotation=None,
            error_message=str(exc),
        )
    for path, text in ((paths.report, report_md), (paths.seed, seed_md)):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path == paths.seed and default_seed:
                with path.open("x", encoding="utf-8") as stream:
                    stream.write(text)
            else:
                path.write_text(text, encoding="utf-8")
        except OSError as exc:
            message = f"could not write {_short_path(path, repo_root)}: {exc}"
            error(message)
            return AnnotateBatchResult(
                source_path=resolved_source,
                report_path=paths.report,
                seed_path=paths.seed,
                annotation=None,
                error_message=message,
            )

    success(f"annotated {_short_path(paths.report, repo_root)}")
    detail(f"seed {_short_path(paths.seed, repo_root)}")
    detail(
        "grounding "
        f"grounded_files={len(annotation.grounded_files)} "
        f"candidate_text_files={annotation.grounding_candidate_count} "
        f"skipped_or_unreadable={annotation.grounding_skipped_count}"
    )

    # Terminal case: every section IMPLEMENTED → empty carryover. Say so
    # explicitly so the operator isn't left to infer the no-op from an empty
    # seed. Both artifacts are still written; only this line is conditional.
    if _all_implemented(annotation):
        success(
            f"no remaining work — every section is implemented; see "
            f"{_short_path(paths.report, repo_root)}, no next plan needed"
        )

    if args.archive:
        archive_errors = _archive_source(resolved_source, paths.report, repo_root)
        if archive_errors:
            return AnnotateBatchResult(
                source_path=resolved_source,
                report_path=paths.report,
                seed_path=paths.seed,
                annotation=annotation,
                error_message="archive failed/partial move requires manual recovery",
            )

    return AnnotateBatchResult(
        source_path=resolved_source,
        report_path=paths.report,
        seed_path=paths.seed,
        annotation=annotation,
    )


def _derive_annotate_paths(
    args: argparse.Namespace, *, source_path: Path, repo_root: Path
) -> AnnotatePaths:
    """Derive report/seed paths for one source file."""
    output_dir = args.output_dir if args.output_dir is not None else source_path.parent
    report_dir = getattr(args, "report_dir", None) or output_dir
    seed_dir = (getattr(args, "seed_dir", None) or args.output_dir
                or default_seeds_dir(repo_root))
    report_path = (
        args.report.resolve()
        if args.report is not None
        else (report_dir / f"{source_path.stem}.annotated.md")
    )
    seed_path = (
        args.seed.resolve()
        if args.seed is not None
        else (seed_dir / f"{source_path.stem}.seed.md")
    )
    return AnnotatePaths(report=report_path, seed=seed_path)


def _find_duplicate_annotate_outputs(
    args: argparse.Namespace, sources: list[Path], *, repo_root: Path
) -> list[str]:
    """Return duplicate derived report/seed paths that would overwrite output."""
    seen: dict[Path, Path] = {}
    errors: list[str] = []
    for source in sources:
        paths = _derive_annotate_paths(args, source_path=source.resolve(), repo_root=repo_root)
        for path in (paths.report, paths.seed):
            resolved = path.resolve()
            if resolved in seen:
                errors.append(
                    "annotate output collision: "
                    f"{source} and {seen[resolved]} both write {path}"
                )
            else:
                seen[resolved] = source
    return errors


def _print_batch_summary(
    results: list[AnnotateBatchResult], *, repo_root: Path, stream=None
) -> None:
    """Print a compact coverage + grounding table for a batch annotate run."""
    out = stream if stream is not None else sys.stdout
    rows: list[tuple[str, str, str, str, str]] = []
    for result in results:
        source = _short_path(result.source_path, repo_root)
        if result.annotation is None:
            rows.append(
                (source, "FAIL", "-", "-", _summarize_error(result.error_message))
            )
            continue
        annotation = result.annotation
        total = len(annotation.sections)
        implemented = sum(
            1
            for section in annotation.sections
            if section.status is AnnotationStatus.IMPLEMENTED
        )
        coverage = f"{implemented}/{total}" if total else "0/0"
        grounding = (
            f"{len(annotation.grounded_files)}/"
            f"{annotation.grounding_candidate_count}"
            f" ({annotation.grounding_skipped_count} skipped)"
        )
        counts = _status_counts(annotation)
        status = "OK" if result.ok else "FAIL"
        rows.append((source, status, coverage, grounding, counts))

    headers = ("source", "result", "coverage", "grounding", "sections")
    widths = [
        max(len(row[i]) for row in [headers, *rows])
        for i in range(len(headers))
    ]
    out.write("\nannotate batch summary\n")
    out.write(_format_summary_row(headers, widths) + "\n")
    out.write(_format_summary_row(tuple("-" * w for w in widths), widths) + "\n")
    for row in rows:
        out.write(_format_summary_row(row, widths) + "\n")
    out.flush()


def _format_summary_row(row: tuple[str, str, str, str, str], widths: list[int]) -> str:
    return "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))


def _status_counts(annotation: PlanAnnotation) -> str:
    counts = {
        AnnotationStatus.IMPLEMENTED: 0,
        AnnotationStatus.PARTIAL: 0,
        AnnotationStatus.NOT_IMPLEMENTED: 0,
        AnnotationStatus.NEEDS_REVIEW: 0,
    }
    for section in annotation.sections:
        counts[section.status] += 1
    return (
        f"I={counts[AnnotationStatus.IMPLEMENTED]} "
        f"P={counts[AnnotationStatus.PARTIAL]} "
        f"N={counts[AnnotationStatus.NOT_IMPLEMENTED]} "
        f"R={counts[AnnotationStatus.NEEDS_REVIEW]}"
    )


def _summarize_error(message: str) -> str:
    return message.splitlines()[0] if message else "failed"


def _all_implemented(annotation: PlanAnnotation) -> bool:
    """True when every section classifies IMPLEMENTED (nothing carries forward)."""
    return bool(annotation.sections) and all(
        s.status is AnnotationStatus.IMPLEMENTED for s in annotation.sections
    )


def _archive_source(
    source_path: Path, report_path: Path, repo_root: Path
) -> list[str]:
    """Move the original into ``archive/`` with a report-pointing notice.

    Warns (but does not deregister) when the source is registered in the
    repo's ``.plan-tool/plans.json``: archiving moves the file but leaves the
    manifest entry pointing at the old location, so ``locator`` resolution of
    that plan fails until the operator fixes the entry through a direct edit.
    Manifest
    mutation is out of scope, so this is document-and-warn only.
    """
    if source_path in load_manifest_plan_paths(repo_root):
        warn(
            f"{_short_path(source_path, repo_root)} is registered in "
            f"{repo_root / '.plan-tool' / 'plans.json'}; archiving moves the "
            "plan but leaves its plans.json entry pointing at the old location, "
            "so resolving that plan will fail until you update or remove the "
            "entry directly (annotate does not deregister)."
        )

    result = archive_existing_source(source_path, report_path, repo_root=repo_root)
    _report_archive_result(result, repo_root=repo_root)
    return result.skipped


def register(subparsers) -> dict[str, Handler]:
    """Add the ``annotate`` subparser and return its handler map."""
    p = subparsers.add_parser(
        "annotate",
        help=(
            "judge an existing plan/notes file against the current code and "
            "emit two artifacts — an additive `<name>.annotated.md` (verbatim "
            "original + per-section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED status) "
            "and a carryover seed in docs/implementation-plans/plan-seeds/ "
            "for `create --from-existing`; "
            "read-only except the opt-in `--archive`."
        ),
    )
    p.add_argument(
        "plan_files",
        type=Path,
        nargs="+",
        metavar="path-or-glob",
        help=(
            "existing plan/notes path or glob to annotate against the current "
            "code; accepts multiple values"
        ),
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        dest="output_dir",
        help=(
            "directory for the derived <name>.annotated.md / <name>.seed.md "
            "(default: report beside source; seed in docs/implementation-plans/plan-seeds)"
        ),
    )
    p.add_argument(
        "--report",
        type=Path,
        default=None,
        help="explicit path for the annotated report (overrides the derived name + --output-dir)",
    )
    p.add_argument(
        "--seed",
        type=Path,
        default=None,
        help="explicit path for the create-seed (overrides the derived name + --output-dir)",
    )
    p.add_argument(
        "--report-dir",
        type=Path,
        default=None,
        dest="report_dir",
        help=(
            "directory for derived <name>.annotated.md reports "
            "(default: --output-dir or beside each source file)"
        ),
    )
    p.add_argument(
        "--seed-dir",
        type=Path,
        default=None,
        dest="seed_dir",
        help=(
            "directory for derived <name>.seed.md carryover files "
            "(default: --output-dir or docs/implementation-plans/plan-seeds)"
        ),
    )
    p.add_argument(
        "--archive",
        action="store_true",
        help=(
            "move the original (and, for an N-slug.md plan file, its sibling "
            "plan-details/<slug>/ bundle) into archive/ with a notice pointing "
            "at the report (the only mutation of the source; default: leave it "
            "in place)"
        ),
    )
    p.add_argument(
        "--iterate",
        action=argparse.BooleanOptionalAction,
        default=False,
        help=(
            "unsupported for annotate: annotation is currently single-pass "
            "(one classification + two renderers). Deliberately defaults OFF "
            "— diverging from the authoring family's opt-out default=True "
            "(create/detail) — because there is no convergence loop to drive."
        ),
    )
    return {"annotate": cmd_annotate}
