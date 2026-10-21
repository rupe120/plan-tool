"""Discovery & inspection command module — the read-only plan verbs.

Holds the "never call claude" inspection handlers (``cmd_list`` /
``cmd_root`` / ``cmd_status`` / ``cmd_validate``) plus the ``_print_status``
renderer they share, and a :func:`register` that contributes their
subparsers to the shared ``add_subparsers`` action (see
:mod:`plan_tool.cli.parser`).

Like every per-intent command module, this imports only the cycle-free
leaves (:mod:`plan_tool.cli.console`, :mod:`plan_tool.cli.context`) and the
domain packages — never :mod:`plan_tool.cli.app`. ``app`` re-imports these
names back into its own namespace so the package surface stays intact.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from plan_tool.annotate_render import (
    CachedAnnotatedReport,
    parse_cached_annotated_report,
)
from plan_tool.audit_shapes import AUDIT_SHAPES
from plan_tool.cli.console import _common_dir_prefix, _repo_rel
from plan_tool.cli.context import _load_context, _resolve_cmd_repo_root
from plan_tool.cli.parser import Handler, make_yes_parent
from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.locator import (
    default_manifest_path,
    is_project_root,
    resolve_plan_for_context,
    resolve_repo_root,
    slug_from_filename,
)
from plan_tool.parser import (
    ParseError,
    UnsupportedPlanFormatVersionError,
    ValidationError,
    format_validation_errors,
    parse_plan,
)
from plan_tool.schema import Plan, StepScope, StepStatus
from plan_tool.style import change_type_tag, warn


@dataclass(frozen=True)
class _PlanAnnotationStatus:
    """One ``list --status`` rollup row."""

    slug: str
    path: Path
    report: CachedAnnotatedReport | None
    error: str | None = None


_AUDIT_SHAPE_DOCUMENT_MARKER = "<!-- plan-tool:audit-shapes -->"
_AUDIT_SHAPE_TABLE_HEADER = "| id | tell | classification |"
_AUDIT_SHAPE_TABLE_DIVIDER = "| --- | --- | --- |"
_AUDIT_SHAPE_TABLE_ROW = re.compile(
    r"^\|\s*`(?P<id>[a-z0-9][a-z0-9-]*)`\s*\|\s*"
    r"(?P<tell>[^|]+?)\s*\|\s*`(?P<classification>[^`|]+)`\s*\|\s*$"
)


@dataclass(frozen=True)
class _DocumentedAuditShape:
    """One strictly formatted record from the owned CLAUDE.md table."""

    id: str
    tell: str
    classification: str
    line_number: int


def _audit_shape_documentation_findings(repo_root: Path) -> list[str]:
    """Return advisory-only drift findings for an owned CLAUDE.md shape table.

    An unrelated CLAUDE.md is not a plan-tool contract, so this check stays
    inert until the document opts in with ``_AUDIT_SHAPE_DOCUMENT_MARKER``.
    The registry remains the source of truth for both the expected values and
    their order.
    """
    try:
        document_lines = (repo_root / "CLAUDE.md").read_text(
            encoding="utf-8"
        ).splitlines()
    except OSError:
        return []

    marker_lines = [
        index for index, line in enumerate(document_lines)
        if line.strip() == _AUDIT_SHAPE_DOCUMENT_MARKER
    ]
    if not marker_lines:
        return []
    if len(marker_lines) != 1:
        return [
            "the ownership marker must appear exactly once "
            f"(found {len(marker_lines)})"
        ]

    records, findings = _extract_documented_audit_shapes(
        document_lines, marker_lines[0]
    )
    if records is None:
        return findings

    expected_by_id = {shape.id: shape for shape in AUDIT_SHAPES}
    documented_ids = [record.id for record in records]
    duplicate_ids = sorted(
        shape_id for shape_id in set(documented_ids)
        if documented_ids.count(shape_id) > 1
    )
    for shape_id in duplicate_ids:
        findings.append(f"duplicate documented record '{shape_id}'")

    known_records: dict[str, _DocumentedAuditShape] = {}
    for record in records:
        expected = expected_by_id.get(record.id)
        if expected is None:
            findings.append(
                f"unknown documented record '{record.id}' on line {record.line_number}"
            )
            continue
        if record.id in known_records:
            continue
        known_records[record.id] = record
        if record.tell != expected.tell:
            findings.append(
                f"tell drift for '{record.id}' on line {record.line_number}: "
                f"expected '{expected.tell}'"
            )
        if record.classification != expected.classification:
            findings.append(
                f"classification drift for '{record.id}' on line "
                f"{record.line_number}: expected '{expected.classification}'"
            )

    for shape in AUDIT_SHAPES:
        if shape.id not in known_records:
            findings.append(f"missing registered record '{shape.id}'")

    expected_ids = tuple(shape.id for shape in AUDIT_SHAPES)
    if tuple(documented_ids) != expected_ids:
        findings.append(
            "record order differs from the registry: expected "
            + ", ".join(expected_ids)
        )
    return findings


def _extract_documented_audit_shapes(
    document_lines: list[str], marker_line: int
) -> tuple[list[_DocumentedAuditShape] | None, list[str]]:
    """Extract the single table immediately owned by the audit-shape marker."""
    human_marker_line = marker_line + 1
    header_line = marker_line + 1
    divider_line = marker_line + 2
    if (
        header_line >= len(document_lines)
        or document_lines[header_line].strip() != _AUDIT_SHAPE_TABLE_HEADER
    ):
        return None, [
            f"owned list after marker on line {human_marker_line} has a malformed header"
        ]
    if (
        divider_line >= len(document_lines)
        or document_lines[divider_line].strip() != _AUDIT_SHAPE_TABLE_DIVIDER
    ):
        return None, [
            f"owned list after marker on line {human_marker_line} has a malformed divider"
        ]

    records: list[_DocumentedAuditShape] = []
    findings: list[str] = []
    line_index = marker_line + 3
    while line_index < len(document_lines):
        line = document_lines[line_index]
        if not line.startswith("|"):
            break
        match = _AUDIT_SHAPE_TABLE_ROW.fullmatch(line)
        if match is None:
            findings.append(
                f"malformed documented record on line {line_index + 1}; expected "
                "| `id` | tell | `classification` |"
            )
        else:
            records.append(
                _DocumentedAuditShape(
                    id=match.group("id"),
                    tell=match.group("tell"),
                    classification=match.group("classification"),
                    line_number=line_index + 1,
                )
            )
        line_index += 1
    if line_index < len(document_lines) and document_lines[line_index].strip():
        findings.append(
            f"malformed documented record on line {line_index + 1}; table rows "
            "must remain contiguous"
        )
    if not records and not findings:
        findings.append("owned audit-shape list contains no documented records")
    return records, findings


def cmd_list(args: argparse.Namespace) -> int:
    """Enumerate plan-tool-compatible plans (discovery & inspection).

    Intent: answer "what plans does plan-tool know about, and what's
    their headline state?" without touching the filesystem beyond the
    plan files themselves. Pairs with :func:`cmd_status` (single-plan
    detail) and :func:`cmd_validate` (schema-only health check).

    No claude call; never mutates anything. Warns on stderr about
    manifest entries that don't resolve on disk so the operator can
    prune dead entries.
    """
    ctx = _load_context(args)

    if ctx.missing_paths:
        manifest = args.manifest or default_manifest_path(ctx.repo_root)
        warn(
            f"{len(ctx.missing_paths)} manifest entry/entries not "
            f"found on disk (check your repo root or manifest paths):"
        )
        for p in ctx.missing_paths:
            print(f"  {p}", file=sys.stderr)
            # Best-effort repo-relative form for the manifest entry — matches
            # what's actually stored in `structured_plans.json`. Falls back
            # to the absolute path when the missing file lives outside the
            # repo root (rare; usually means --repo-root is wrong).
            try:
                rel = p.resolve().relative_to(ctx.repo_root.resolve())
                manifest_entry = rel.as_posix()
            except ValueError:
                manifest_entry = str(p)
            print(
                f'    if no longer needed, remove "{manifest_entry}" '
                f"from {manifest}",
                file=sys.stderr,
            )

    if not ctx.entries:
        print("no plan-tool plans registered")
        if ctx.plans_dir is None:
            mf = args.manifest or default_manifest_path(ctx.repo_root)
            print(f'  add repo-relative paths to the "plans" array in {mf}')
        else:
            print(f"  (no YAML frontmatter plans found under {ctx.plans_dir})")
        return 0

    if getattr(args, "status", False):
        _print_annotation_status_rollup(ctx, args)
        return 0

    if ctx.plans_dir is not None:
        print(f"discovered in directory: {ctx.plans_dir}")
    else:
        mf = args.manifest or default_manifest_path(ctx.repo_root)
        print(f"registered in manifest: {mf}")

    # Factor a shared parent directory out of the plan paths so each row can
    # show a short basename instead of a long, near-identical absolute path
    # (the part operators found unreadable). Only kicks in when every plan
    # lives in the same directory; otherwise rows fall back to repo-relative
    # paths, which are still far shorter than absolute ones.
    repo_root = ctx.repo_root.resolve()
    common = _common_dir_prefix([e.path for e in ctx.entries])
    show_basenames = common is not None

    def _rel_to_repo(path: Path) -> str:
        try:
            return path.resolve().relative_to(repo_root).as_posix()
        except ValueError:
            return str(path)

    if show_basenames:
        common_disp = _rel_to_repo(common)
        # In directory mode the header already named this directory; only
        # echo it when it adds information (manifest mode, or a deeper subdir).
        if ctx.plans_dir is None or common.resolve() != ctx.plans_dir.resolve():
            print(f"  in {common_disp}/")

    def _file_cell(path: Path) -> str:
        return path.name if show_basenames else _rel_to_repo(path)

    # Pre-compute rows so column widths fit the actual content rather than
    # padding every slug out to a fixed 45 columns.
    rows: list[tuple[str, str, str, str, str, Optional[str]]] = []
    for e in ctx.entries:
        if e.plan is None:
            rows.append((e.slug, "MALFORMED", "-", "-", _file_cell(e.path), e.error))
            continue
        p = e.plan
        rows.append(
            (
                e.slug,
                p.status.value,
                p.priority.value,
                f"{p.done_count}/{len(p.steps)}",
                _file_cell(e.path),
                None,
            )
        )

    headers = ("SLUG", "STATUS", "PRIORITY", "STEPS", "FILE")
    widths = [max(len(headers[i]), *(len(r[i]) for r in rows)) for i in range(4)]
    # Keep one unusually long slug from widening every row's later columns;
    # such a slug just overflows its cell ragged-right instead.
    widths[0] = min(widths[0], 45)

    def _format(cells: tuple[str, str, str, str, str]) -> str:
        return (
            "  "
            + cells[0].ljust(widths[0])
            + "  "
            + cells[1].ljust(widths[1])
            + "  "
            + cells[2].ljust(widths[2])
            + "  "
            + cells[3].ljust(widths[3])
            + "  "
            + cells[4]
        )

    print(_format(headers))
    for slug, status, prio, steps, fcell, error in rows:
        print(_format((slug, status, prio, steps, fcell)))
        if error is not None:
            # Indent every line of a (often multi-line) parse error so it
            # reads as subordinate to its row rather than blending in.
            for i, eline in enumerate(error.splitlines() or [""]):
                print(("      error: " if i == 0 else "             ") + eline)

    # Point the operator at the per-plan deep-dive: `list` shows the headline
    # error inline, but `validate` adds the full file path and field-level
    # detail needed to actually fix it.
    malformed = [e for e in ctx.entries if e.plan is None]
    if malformed:
        noun = "plan" if len(malformed) == 1 else "plans"
        print(
            f"\n  {len(malformed)} {noun} failed to validate; run "
            f"'plan-tool validate <slug>' for the full path and field-level "
            f"detail (e.g. {malformed[0].slug})."
        )
    return 0


def _print_annotation_status_rollup(ctx, args: argparse.Namespace) -> None:
    """Print the cached annotate status rollup for every discovered plan."""
    repo_root = ctx.repo_root.resolve()
    reports_by_source = _collect_cached_annotation_reports(ctx, args)
    rows: list[_PlanAnnotationStatus] = []
    for entry in ctx.entries:
        report = reports_by_source.get(entry.path.resolve())
        rows.append(
            _PlanAnnotationStatus(
                slug=entry.slug,
                path=entry.path,
                report=report,
                error=entry.error if entry.plan is None else None,
            )
        )

    if getattr(args, "format", "text") == "md":
        _print_annotation_status_markdown(rows, repo_root=repo_root)
    else:
        _print_annotation_status_text(rows, repo_root=repo_root)


def _collect_cached_annotation_reports(
    ctx, args: argparse.Namespace
) -> dict[Path, CachedAnnotatedReport]:
    """Map active plan paths to their newest cached annotate report."""
    active_paths = {entry.path.resolve() for entry in ctx.entries}
    active_by_name = {entry.path.name: entry.path.resolve() for entry in ctx.entries}
    reports: dict[Path, CachedAnnotatedReport] = {}
    for report_path in _iter_annotation_report_paths(ctx, args):
        report = parse_cached_annotated_report(report_path)
        if report is None:
            continue
        source_path = _resolve_report_source(
            report, repo_root=ctx.repo_root, active_by_name=active_by_name
        )
        if source_path not in active_paths:
            continue
        previous = reports.get(source_path)
        if previous is not None and _duplicate_report_tie_disagrees(report, previous):
            warn(
                "duplicate annotated reports for "
                f"{_repo_rel(source_path, ctx.repo_root)} share "
                f"annotated_at={report.annotated_at or '-'} but disagree on "
                "counts; using lexicographically last path"
            )
        if previous is None or _report_is_newer(report, previous):
            reports[source_path] = report
    return reports


def _iter_annotation_report_paths(ctx, args: argparse.Namespace) -> list[Path]:
    """Return unique cached report candidates from sibling and report dirs."""
    candidates: dict[Path, Path] = {}
    report_dirs = list(getattr(args, "report_dir", None) or [])
    for entry in ctx.entries:
        sibling_report = entry.path.with_name(f"{entry.path.stem}.annotated.md")
        candidates[sibling_report.resolve()] = sibling_report
        conventional_reports_dir = (
            entry.path.parent
            / "plan-details"
            / (slug_from_filename(entry.path) or entry.slug)
            / "reports"
        )
        for path in conventional_reports_dir.glob("*.annotated.md"):
            candidates[path.resolve()] = path
        for report_dir in report_dirs:
            for path in report_dir.glob("*.annotated.md"):
                candidates[path.resolve()] = path
    return [candidates[key] for key in sorted(candidates)]


def _resolve_report_source(
    report: CachedAnnotatedReport, *, repo_root: Path, active_by_name: dict[str, Path]
) -> Path:
    """Resolve report source metadata to an active plan path candidate."""
    source = report.source_path
    if source is None:
        return active_by_name.get(
            report.path.name.replace(".annotated.md", ".md"), report.path
        )
    if source.is_absolute():
        return source.resolve()
    repo_relative = (repo_root / source).resolve()
    if repo_relative.exists():
        return repo_relative
    if source.name in active_by_name:
        return active_by_name[source.name]
    return active_by_name.get(source.name, (report.path.parent / source).resolve())


def _report_is_newer(
    candidate: CachedAnnotatedReport, existing: CachedAnnotatedReport
) -> bool:
    """Choose newest annotated_at; tie-break by lexicographically last path."""
    candidate_key = (candidate.annotated_at, str(candidate.path))
    existing_key = (existing.annotated_at, str(existing.path))
    return candidate_key > existing_key


def _duplicate_report_tie_disagrees(
    candidate: CachedAnnotatedReport, existing: CachedAnnotatedReport
) -> bool:
    return (
        candidate.annotated_at == existing.annotated_at
        and candidate.counts_key != existing.counts_key
    )


def _print_annotation_status_text(
    rows: list[_PlanAnnotationStatus], *, repo_root: Path
) -> None:
    headers = (
        "SLUG",
        "ANN",
        "IMPL",
        "PART",
        "NOT",
        "REVIEW",
        "GROUNDED",
        "ANNOTATED_AT",
        "FILE",
    )
    rendered = [_annotation_status_cells(row, repo_root=repo_root) for row in rows]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in rendered))
        for i in range(len(headers) - 1)
    ]
    widths[0] = min(widths[0], 45)

    def _format(cells: tuple[str, ...]) -> str:
        return (
            "  "
            + "  ".join(cells[i].ljust(widths[i]) for i in range(len(widths)))
            + "  "
            + cells[-1]
        )

    print(_format(headers))
    for row, cells in zip(rows, rendered):
        print(_format(cells))
        if row.error is not None:
            for i, eline in enumerate(row.error.splitlines() or [""]):
                print(("      error: " if i == 0 else "             ") + eline)


def _print_annotation_status_markdown(
    rows: list[_PlanAnnotationStatus], *, repo_root: Path
) -> None:
    headers = (
        "Plan",
        "Annotated",
        "IMPLEMENTED",
        "PARTIAL",
        "NOT-IMPLEMENTED",
        "NEEDS-REVIEW",
        "grounded_files",
        "last_annotated",
        "File",
    )
    print("| " + " | ".join(headers) + " |")
    print("| " + " | ".join("---" for _ in headers) + " |")
    for row in rows:
        cells = _annotation_status_cells(row, repo_root=repo_root)
        print("| " + " | ".join(_escape_md_cell(cell) for cell in cells) + " |")


def _annotation_status_cells(
    row: _PlanAnnotationStatus, *, repo_root: Path
) -> tuple[str, str, str, str, str, str, str, str, str]:
    report = row.report
    if report is None:
        return (
            row.slug,
            "no",
            "-",
            "-",
            "-",
            "-",
            "-",
            "-",
            _repo_rel(row.path, repo_root),
        )
    return (
        row.slug,
        "yes",
        str(report.implemented),
        str(report.partial),
        str(report.not_implemented),
        str(report.needs_review),
        str(report.grounded_files),
        report.annotated_at or "-",
        _repo_rel(row.path, repo_root),
    )


def _escape_md_cell(value: str) -> str:
    return value.replace("|", "\\|")


def cmd_status(args: argparse.Namespace) -> int:
    """Show step-by-step status for one plan (discovery & inspection).

    Intent: answer "where am I in this plan?" with marker, id, title,
    complexity, and deps for every step. Read-only; no claude call.
    Pairs with :func:`cmd_list` (the all-plans summary view).
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    plan = parse_plan(path)
    _print_status(plan, path)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Schema-check a plan's YAML frontmatter (discovery & inspection).

    Intent: confirm the plan loads cleanly under the Pydantic schema
    (required fields, valid enums, unique step ids, deps resolve,
    no two `current` steps). Deliberately narrower than
    :func:`cmd_review` and :func:`cmd_completeness` — `validate`
    catches *structural* errors that would otherwise crash other
    subcommands; it does NOT flag authoring gaps (empty sections,
    missing detail files), broken paths, or stale steps. See the
    "three audit verbs" framing in SKILL.md.

    Exits 0 once the check runs — the ``OK:`` / ``INVALID:`` line is
    the verdict a caller reads, not the exit code. Pass
    ``--fail-on-findings`` to make an ``INVALID`` verdict exit non-zero
    for CI gating. (A plan that can't be located still surfaces a
    non-zero error from name resolution upstream.) No claude call.

    Two named exceptions to that flag-controlled exit code, both because
    this build cannot safely interpret the declared artifact at all. A plan
    declaring an unsupported ``format_version``
    (:class:`plan_tool.parser.UnsupportedPlanFormatVersionError`) always
    exits 1, independently of ``--fail-on-findings``. So does a detailed
    step whose run-grade body declares an unsupported or malformed format
    version (:class:`plan_tool.detail_artifacts.DetailFormatError`),
    surfaced by the pointer-backed suppression scan that now runs before
    ``OK:`` is printed.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    try:
        plan = parse_plan(path)
    except (ParseError, ValidationError) as exc:
        # Lead with the full path so the verdict doubles as "open this file";
        # render schema failures as concise `field: message` lines (the same
        # form `list` uses) rather than the verbose pydantic dump. ParseError
        # (malformed/absent frontmatter) has no structured errors — its own
        # message is already human-readable, so print it as-is.
        print(f"INVALID: {path}")
        if isinstance(exc, ValidationError) and exc.errors:
            for line in format_validation_errors(exc.errors):
                print(f"  {line}")
        else:
            print(f"  {exc}")
        if isinstance(exc, UnsupportedPlanFormatVersionError):
            return 1
        return 1 if getattr(args, "fail_on_findings", False) else 0
    # Advisory, no-Claude smell pass on the valid path only — surfaces the
    # feature-ref / suppression-shape / self-referential heuristics so an
    # operator sees them before paying for a completeness-audit Claude run.
    # Imported in-body so the lookup stays `plan_tool.review.collect_smell_findings`
    # (the attribute the split-proof cli tests patch) and `validate`'s
    # no-Claude import graph stays light. `validate` has no gate, so these
    # findings never touch the exit code (even the `medium` suppression-shape
    # one) — the only rc flip lives in the `INVALID:` / `DetailFormatError`
    # arms, so a smell can never gate CI here.
    #
    # Run before ``OK:`` is printed: the suppression-shape detector reads a
    # detailed step's pointer-backed body, so an unsupported or malformed
    # declared format version there is the same class of "this build cannot
    # safely interpret the artifact" refusal as the plan-format check above,
    # and must not print a misleading ``OK:`` first.
    from plan_tool.review import collect_smell_findings, confidence_label

    try:
        smells = collect_smell_findings(plan, ctx.repo_root, plan_name=args.name)
    except DetailFormatError as exc:
        print(f"INVALID: {path}")
        print(f"  {exc}")
        return 1
    print(f"OK: {path}")
    if smells:
        # Split by routing, not by severity: members of
        # ``SELF_CONSISTENCY_SOURCES`` block ``completeness-audit`` convergence,
        # so printing them under "advisory" tells an operator the opposite of
        # what the next command will do. ``validate`` still gates on nothing —
        # only the ``INVALID:`` arm above flips the rc.
        from plan_tool.review import SELF_CONSISTENCY_SOURCES

        blocking = [r for r in smells if r.source in SELF_CONSISTENCY_SOURCES]
        advisory = [r for r in smells if r.source not in SELF_CONSISTENCY_SOURCES]

        def _emit(header: str, recs: list) -> None:
            if not recs:
                return
            print(header)
            for rec in recs:
                body = (rec.body or rec.title).strip()
                print(
                    f"    - {rec.title} [{rec.source}] "
                    f"[{confidence_label(rec.confidence)}]: {body}"
                )

        _emit(
            "  blocks completeness convergence (validate does not gate):",
            blocking,
        )
        _emit("  smells (advisory):", advisory)

    documentation_findings = _audit_shape_documentation_findings(ctx.repo_root)
    if documentation_findings:
        print("  audit-shape documentation (advisory, repo-wide):")
        for finding in documentation_findings:
            print(f"    - {finding}")

    # Repo-wide capability-catalog honesty check (no Claude, advisory). Surfaced
    # once here rather than in the plan-scoped smell layer: it reads no `plan`,
    # needs the CLI parser surface, and is labeled repo-wide so it isn't read as
    # a property of this plan. Inert when CAPABILITIES.md is absent; never flips
    # the exit code. Deferred import keeps validate's no-Claude graph light.
    from plan_tool.capability_catalog import check_capabilities

    cap_findings = check_capabilities(ctx.repo_root)
    if cap_findings:
        print("  capability catalog (advisory, repo-wide):")
        for f in cap_findings:
            print(f"    - [{f.code}] {f.message}")
    return 0


def cmd_root(args: argparse.Namespace) -> int:
    """Report the repo root plan-tool would discover here (discovery & inspection).

    Intent: answer "where would `create` (and every no-name subcommand)
    put / look for plans from this directory?" before running anything
    that writes. Resolves the root with the same precedence as those
    commands — ``--repo-root`` flag → ``PLAN_TOOL_REPO_ROOT`` env → walk up
    from cwd to the nearest ``.git`` / ``.plan-tool`` ancestor, falling back
    to the cwd when neither marker is found — and names which source won, the
    manifest path under that root, and whether it differs from the cwd.

    Read-only; no claude call. Always exits 0 — there is no failure mode now
    that an unmarked tree resolves to the current directory.
    """
    repo_root = _resolve_cmd_repo_root(args)
    root = repo_root.resolve()
    cwd = Path.cwd().resolve()

    if getattr(args, "repo_root", None) is not None:
        source = "--repo-root flag"
    elif resolve_repo_root(None) is not None:
        source = "PLAN_TOOL_REPO_ROOT env"
    elif is_project_root(root):
        source = "walked up from cwd to .git or .plan-tool/plans.json"
    else:
        source = "current directory (no .git or .plan-tool/plans.json found)"

    print(f"root:     {root}")
    print(f"  source:   {source}")
    print(f"  manifest: {default_manifest_path(root)}")
    if root != cwd:
        print(f"  cwd:      {cwd}  (differs — plans resolve under root)")
    return 0


def _print_status(plan: Plan, path: Path) -> None:
    print(f"{plan.title}  ({path.name})")
    print(
        f"  status={plan.status.value}  priority={plan.priority.value}  "
        f"progress={plan.done_count}/{len(plan.steps)}"
    )
    print()
    for s in plan.steps:
        if s.scope is StepScope.DEFERRED:
            marker = "[~]"
        elif s.scope is StepScope.WONT_DO:
            marker = "[/]"
        else:
            marker = {
                StepStatus.DONE: "[x]",
                StepStatus.CURRENT: "[>]",
                StepStatus.PENDING: "[ ]",
            }[s.status]
        deps = f"  deps={s.depends_on}" if s.depends_on else ""
        complexity = f"  ({s.complexity.value})" if s.complexity else ""
        print(
            f"  {marker} {s.id}. {s.title}"
            f"{change_type_tag(s.change_type)}{complexity}{deps}"
        )

    from plan_tool.grounding import stale_detail_warning

    warning = stale_detail_warning(plan, path)
    if warning:
        print(f"  {warning}")
    _print_pending_decisions(plan, path)


def _pending_section_excerpt(body: str, *, max_lines: int = 3, max_chars: int = 240) -> str:
    """A short, truncated excerpt of a plan body-section — the lazy context
    that tells the operator what a parked deferral relates to. Collapses blank
    lines, keeps the first few, and clips overall length."""
    kept: list[str] = []
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        kept.append(stripped)
        if len(kept) >= max_lines:
            break
    excerpt = " ".join(kept)
    if len(excerpt) > max_chars:
        excerpt = excerpt[: max_chars - 1].rstrip() + "…"
    return excerpt


def _print_pending_decisions(plan: Plan, path: Path) -> None:
    """Render the non-blocking pending concept-decision block on ``status``.

    Reuses the one detector (``check_concept_coverage``) and the shared
    ``PENDING_DECISION_SOURCES`` filter, then groups flat still-resolving
    decisions by their section ``bucket`` (with an on-demand excerpt of that
    section's body text), while missing-bucket and legacy nodes fall into
    their own note-only groups. Display only — spends no Claude, never raises
    on a stale record, and never changes the exit code. Prints nothing when
    there are no pending decisions (the common case).
    """
    from plan_tool.completeness_report import (
        PENDING_DECISION_SOURCES,
        pending_concept_id,
    )
    from plan_tool.review import (
        CONCEPT_BUCKET_MISSING_SOURCE,
        CONCEPT_LEGACY_STALE_SOURCE,
        check_concept_coverage,
    )

    slug = slug_from_filename(path.name) or path.stem
    findings = [
        rec
        for rec in check_concept_coverage(plan, path, plan_name=slug)
        if rec.source in PENDING_DECISION_SOURCES
    ]
    if not findings:
        return

    # Second, per-node load to read each pending node's coarse ``bucket`` for
    # section grouping. Unlike the finding call (stale-tolerant per step 3),
    # this raw load still raises on a stale *legacy* record — guard it and fall
    # back to id-only rendering so ``status`` never crashes on drift.
    nodes_by_id: dict[str, object] = {}
    try:
        from plan_tool.concept_tree import (
            InvalidConceptTreeError,
            StaleConceptTreeError,
            load_concepts,
        )
        from plan_tool.review_persistence import compute_plan_fingerprint

        tree = load_concepts(path, compute_plan_fingerprint(path))
        if tree is not None:
            nodes_by_id = {node.id: node for node in tree.concepts}
    except (StaleConceptTreeError, InvalidConceptTreeError, OSError):
        nodes_by_id = {}

    # Section bodies for the lazy-context excerpts, read on demand from the
    # current plan body (keyed on the same normalized name the bucket uses).
    section_bodies: dict[str, str] = {}
    try:
        from plan_tool.parser import parse_body_sections, split_plan_document

        section_bodies = {
            section.name: section.body
            for section in parse_body_sections(
                split_plan_document(path.read_text(encoding="utf-8")).body,
                ignore_fenced_code=True,
            )
        }
    except (OSError, ParseError):
        section_bodies = {}

    # Partition: flat still-resolving buckets (by section name), missing-bucket
    # re-reviews, legacy-pending (empty-bucket full-tree nodes), and the
    # whole-record legacy-stale re-sync advisory.
    flat_by_bucket: dict[str, list] = {}
    missing: list = []
    legacy_pending: list = []
    legacy_stale: list = []
    for rec in findings:
        if rec.source == CONCEPT_BUCKET_MISSING_SOURCE:
            missing.append(rec)
        elif rec.source == CONCEPT_LEGACY_STALE_SOURCE:
            legacy_stale.append(rec)
        else:  # concept-unsigned-deferral
            node = nodes_by_id.get(pending_concept_id(rec))
            bucket = getattr(node, "bucket", "") if node is not None else ""
            if bucket:
                flat_by_bucket.setdefault(bucket, []).append(rec)
            else:
                # No resolvable bucket → a legacy full-tree deferral (never a
                # missing-section: that fires ``concept-bucket-missing`` above).
                legacy_pending.append(rec)

    def _decision_line(rec) -> str:
        node = nodes_by_id.get(pending_concept_id(rec))
        title = getattr(node, "title", "") if node is not None else ""
        cid = pending_concept_id(rec)
        label = f"{cid} — {title}" if title else cid
        return (
            f"    - {label}\n"
            f"      → plan-tool scope-review {slug} --concept {cid} defer|wont_do"
        )

    print()
    print(
        f"Pending concept decisions ({len(findings)}) — "
        f"resolve with `plan-tool scope-review {slug}`:"
    )
    for bucket in sorted(flat_by_bucket):
        print(f"  {bucket}:")
        excerpt = _pending_section_excerpt(section_bodies.get(bucket, ""))
        if excerpt:
            print(f"      {excerpt}")
        for rec in flat_by_bucket[bucket]:
            print(_decision_line(rec))
    if missing:
        print("  section no longer exists — re-review:")
        for rec in missing:
            cid = pending_concept_id(rec)
            print(
                f"    - {cid}\n"
                f"      → plan-tool scope-review {slug} --concept {cid} "
                f"wont_do (or defer)"
            )
    if legacy_pending:
        print("  legacy record — confirm via scope-review:")
        for rec in legacy_pending:
            print(_decision_line(rec))
    if legacy_stale:
        print("  legacy record — needs re-sync via scope-review:")
        for rec in legacy_stale:
            print(f"      {(rec.body or rec.title).strip()}")


def register(subparsers) -> dict[str, Handler]:
    """Add the discovery & inspection subparsers and return their dispatch map.

    Takes ``-y/--yes`` from :func:`plan_tool.cli.parser.make_yes_parent`
    and builds the ``--fail-on-findings`` parent locally.
    """
    sub = subparsers

    yes_parent = make_yes_parent()

    # Opt-in CI gate inherited by the audit subcommands. By default the
    # audit verbs exit 0 once they complete; passing this flag restores
    # each command's own blocking threshold as a non-zero exit.
    fail_on_findings_parent = argparse.ArgumentParser(add_help=False)
    fail_on_findings_parent.add_argument(
        "--fail-on-findings",
        action="store_true",
        dest="fail_on_findings",
        help=(
            "exit non-zero when the audit's blocking findings are present "
            "(completeness: medium+; verify-all: a [FAIL] / critical "
            "finding; validate: INVALID — except an unsupported declared "
            "format_version, for which validate always exits 1 regardless "
            "of this flag). Off by default; intended for CI gates that "
            "stop the pipeline on findings."
        ),
    )

    p_list = sub.add_parser(
        "list", help="list plan-tool-compatible plans", parents=[yes_parent]
    )
    p_list.add_argument(
        "--status",
        action="store_true",
        help=(
            "roll up cached annotate reports for active plans, including "
            "per-status counts and grounding metadata"
        ),
    )
    p_list.add_argument(
        "--report-dir",
        type=Path,
        action="append",
        default=None,
        dest="report_dir",
        help=(
            "additional directory of cached *.annotated.md reports to include "
            "with list --status; may be repeated"
        ),
    )
    p_list.add_argument(
        "--format",
        choices=("text", "md"),
        default="text",
        help="output format for list --status (default: text)",
    )

    sub.add_parser(
        "root",
        help="report the repo root plan-tool discovers from here",
        parents=[yes_parent],
    )

    p_status = sub.add_parser(
        "status",
        help="show step-by-step status for a plan",
        parents=[yes_parent],
    )
    p_status.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )

    p_validate = sub.add_parser(
        "validate",
        help="validate a plan's frontmatter",
        parents=[yes_parent, fail_on_findings_parent],
    )
    p_validate.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )

    return {
        "list": cmd_list,
        "root": cmd_root,
        "status": cmd_status,
        "validate": cmd_validate,
    }
