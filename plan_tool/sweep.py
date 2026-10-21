"""Sweep registered plans: archive completed ones, report on the rest.

Backs ``plan-tool sweep`` (see :func:`plan_tool.cli.cmd_sweep`). Pure
deterministic logic — no claude call, no network.

The completion rule is intentionally strict: a plan is auto-archived
only when BOTH the top-level frontmatter ``status`` is ``completed``
AND every committed step's ``status`` is ``done`` (parked deferred /
wont_do steps are ignored — a plan can complete with gated work
parked). The "either-or" loosening was
considered and rejected — strict-AND minimizes false-positive archival
(an author who set top-level ``status: completed`` prematurely won't
have a plan disappear out from under them; conversely, a plan whose
steps are all done but whose author forgot to update the top-level
status stays visible until that's reconciled).

Plans that don't meet the rule are surfaced in a partial-status
report so the operator can see what's outstanding without opening
each file.

Sweep also closes the manifest's blind spot in the other direction:
:func:`discover_orphan_plans` scans the directories that host
registered plans for valid plan files the manifest doesn't list. It
**reports** those paths and nothing more — adoption is the explicit
``plan-tool register <path>`` operation, so no sweep (not even under
``-y``) can turn a report into a registration side effect.

:func:`withdraw_plan` backs ``plan-tool withdraw`` — the abandon-path
counterpart to this module's completion path. It shares the archive-move /
plan-details-move / deregister machinery with :func:`archive_completed_plan`
(via :func:`_dedupe_archive_path` and :func:`_archive_plan_details`) but
requires an operator-supplied reason and marks the archived file
``.withdrawn`` rather than claiming completion.

This module owns no path resolution: ``repo_root`` is supplied by the
caller and the single owner of the CWD-vs-repo-root contract is
:func:`plan_tool.locator.build_plan_tool_context`. Subcommand handlers
forward ``ctx.repo_root`` into :func:`sweep_plans` and
:func:`archive_completed_plan` rather than re-deriving the root here —
that keeps the precedence chain (``--repo-root`` flag →
``PLAN_TOOL_REPO_ROOT`` env → manifest-anchored walk-up → CWD walk-up)
in exactly one place.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional, Sequence

from plan_tool.create import ARCHIVE_DIRNAME, CreateError
from plan_tool.locator import PlanEntry
from plan_tool.parser import (
    ParseError,
    ValidationError,
    format_validation_errors,
    parse_plan,
)
from plan_tool.schema import Plan, PlanStatus, StepScope, StepStatus


@dataclass(frozen=True)
class StepCounts:
    """Per-status step counts for one plan."""

    total: int
    done: int
    current: int
    pending: int
    deferred: int

    @property
    def percent_done(self) -> int:
        """Integer percentage of done steps (0 when the plan has no steps)."""
        if self.total == 0:
            return 0
        return round(100 * self.done / self.total)


@dataclass(frozen=True)
class SweepClassification:
    """Result of classifying one registered plan for sweep purposes.

    ``completed`` is the auto-archive trigger: both top-level
    ``PlanStatus.COMPLETED`` and every committed step at
    ``StepStatus.DONE`` (parked steps ignored).

    ``counts`` is ``None`` only when the underlying ``PlanEntry`` failed
    to parse — those plans surface as malformed in the sweep report
    and are never archived.

    ``in_progress_titles`` lists the titles of steps currently marked
    ``status: current`` (typically 0 or 1; the schema validator caps it
    at most one in well-formed plans but the sweep classifier
    doesn't assume that).
    """

    entry: PlanEntry
    completed: bool
    counts: Optional[StepCounts]
    in_progress_titles: list[str]
    last_modified: float
    parse_error: Optional[str] = None


@dataclass
class ArchiveOutcome:
    """Result of attempting to archive one completed plan.

    Best-effort by design: ``skipped`` captures human-readable reasons
    for partial successes (e.g. archive target already exists). The
    caller surfaces these as warnings rather than aborting because the
    sweep typically runs across many plans and one collision shouldn't
    block the rest.
    """

    plan_path: Path
    # Defaulted so external/keyword construction (ArchiveOutcome(plan_path=…))
    # stays valid; every in-repo caller passes it explicitly.
    slug: str = ""
    archived_to: Optional[Path] = None
    deregistered: bool = False
    plan_details_moved: list[tuple[Path, Path]] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)


@dataclass
class SweepReport:
    """Aggregate result of one sweep run."""

    classifications: list[SweepClassification]
    archived: list[ArchiveOutcome] = field(default_factory=list)
    dry_run: bool = False

    @property
    def completed(self) -> list[SweepClassification]:
        return [c for c in self.classifications if c.completed]

    @property
    def partial(self) -> list[SweepClassification]:
        return [
            c
            for c in self.classifications
            if not c.completed and c.counts is not None
        ]

    @property
    def malformed(self) -> list[SweepClassification]:
        return [c for c in self.classifications if c.counts is None]


def compute_step_counts(plan: Plan) -> StepCounts:
    """Tally per-status step counts for ``plan``."""
    current = sum(1 for s in plan.steps if s.status == StepStatus.CURRENT)
    pending = sum(
        1
        for s in plan.steps
        if s.status == StepStatus.PENDING and s.scope is StepScope.COMMITTED
    )
    deferred = sum(1 for s in plan.steps if s.scope is not StepScope.COMMITTED)
    return StepCounts(
        total=len(plan.steps),
        done=plan.done_count,
        current=current,
        pending=pending,
        deferred=deferred,
    )


def classify_plan(entry: PlanEntry) -> SweepClassification:
    """Classify ``entry`` for sweep — completion rule + supporting data.

    A plan is ``completed`` only when BOTH the top-level
    ``PlanStatus.COMPLETED`` and every committed step ``StepStatus.DONE``
    (parked deferred / wont_do steps ignored, via ``Plan.all_steps_done``).
    The AND-rule is documented at the module level; it minimizes
    false-positive archival.

    The plan file's mtime is captured for the partial-status report;
    falls back to ``0.0`` if the file is missing (shouldn't happen for
    a registered entry, but the classifier is conservative).
    """
    try:
        mtime = entry.path.stat().st_mtime
    except OSError:
        mtime = 0.0

    if entry.plan is None:
        return SweepClassification(
            entry=entry,
            completed=False,
            counts=None,
            in_progress_titles=[],
            last_modified=mtime,
            parse_error=entry.error,
        )

    counts = compute_step_counts(entry.plan)
    in_progress = [
        s.title for s in entry.plan.steps if s.status == StepStatus.CURRENT
    ]
    completed = (
        entry.plan.status == PlanStatus.COMPLETED
        and entry.plan.all_steps_done
    )
    return SweepClassification(
        entry=entry,
        completed=completed,
        counts=counts,
        in_progress_titles=in_progress,
        last_modified=mtime,
    )


def _archive_notice(archived_on: date) -> str:
    """One-line breadcrumb prepended to the archived plan file.

    Distinct wording from the create-time replacement notice
    (:func:`plan_tool.create._replacement_notice`) and from
    :func:`_withdrawal_notice` so a reader of the archive can tell whether a
    file landed there because it was superseded by a different plan, because
    it completed and was swept, or because it was abandoned mid-flight.
    """
    return (
        f"> **Auto-archived**: this plan was swept on "
        f"{archived_on.isoformat()} after reaching `status: completed` "
        f"with all steps marked `done`.\n"
        "> Preserved here for history; do not edit.\n\n"
    )


def _withdrawal_notice(reason: str, withdrawn_on: date) -> str:
    """One-line-plus-reason breadcrumb prepended to a withdrawn plan file.

    A withdrawn plan is neither completed (see :func:`_archive_notice`) nor
    superseded by a replacement — it is abandoned, and the reason is the part
    a later reader actually needs: an archived plan carrying no stated reason
    reads as completed, which is the present-tense-history failure
    CLAUDE.md's "Documentation is forward-looking" section describes.
    """
    return (
        f"> **Withdrawn {withdrawn_on.isoformat()}** — {reason}\n"
        "> Preserved here for history; do not edit.\n\n"
    )


def _dedupe_archive_path(
    archive_dir: Path, stem: str, suffix: str
) -> tuple[Path, Optional[int]]:
    """Return a collision-free path for ``<stem><suffix>`` under
    ``archive_dir``, and the numeric suffix used (``None`` if ``stem`` was
    free).

    Shared de-collision rule for every archive mover in this module: on a
    collision, insert ``.N`` before ``suffix`` and keep incrementing rather
    than skipping — skipping would leave a manifest entry or a plan-details
    directory stranded once the source above it is removed.
    """
    candidate = archive_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate, None
    n = 2
    while True:
        candidate = archive_dir / f"{stem}.{n}{suffix}"
        if not candidate.exists():
            return candidate, n
        n += 1


def archive_completed_plan(
    classification: SweepClassification,
    *,
    manifest_path: Path,
    repo_root: Path,
    archive_dirname: str = ARCHIVE_DIRNAME,
    today: Optional[date] = None,
) -> ArchiveOutcome:
    """Move a completed plan (and its plan-details) to the archive dir
    and remove it from the manifest.

    Mirrors :func:`plan_tool.create.archive_existing_source` in
    structure but with two differences: the archived file keeps its
    original stem (no ``.replaced`` suffix — a completed plan is the
    final document, not a stand-in for one) and the manifest entry is
    removed (the file is no longer a candidate for ``list`` / ``run`` /
    ``review``).

    ``today`` is parameterizable for deterministic tests; defaults to
    today's local date for production callers.
    """
    plan_path = classification.entry.path
    outcome = ArchiveOutcome(
        plan_path=plan_path, slug=classification.entry.slug
    )
    today = today or date.today()

    if not plan_path.is_file():
        outcome.skipped.append(f"plan file no longer exists: {plan_path}")
        return outcome

    archive_dir = plan_path.parent / archive_dirname
    archive_dir.mkdir(exist_ok=True)

    archived_path, collision_suffix = _dedupe_archive_path(
        archive_dir, plan_path.stem, plan_path.suffix
    )
    if collision_suffix is not None:
        # A prior archive of a same-named plan already sits there. Don't
        # skip — skipping would leave the manifest entry behind and turn
        # dangling the moment the source is later removed. The de-duped
        # target preserves the older archive as history; forward the
        # suffix so the plan-details land at the paired ``<slug>.N``.
        outcome.skipped.append(
            f"archive target {archive_dir / plan_path.name} already exists; "
            f"archived to {archived_path.name} instead"
        )

    try:
        body = plan_path.read_text(encoding="utf-8")
        archived_path.write_text(
            _archive_notice(today) + body, encoding="utf-8"
        )
        plan_path.unlink()
        outcome.archived_to = archived_path
    except OSError as exc:
        outcome.skipped.append(f"could not archive {plan_path}: {exc}")
        return outcome

    _archive_plan_details(
        plan_path,
        archive_dir,
        classification.entry.slug,
        _archive_notice(today),
        outcome,
        preferred_suffix=collision_suffix,
    )

    try:
        from plan_tool.create import remove_from_manifest

        outcome.deregistered = remove_from_manifest(
            manifest_path, repo_root, plan_path
        )
    except CreateError as exc:
        outcome.skipped.append(f"could not deregister {plan_path}: {exc}")

    return outcome


def withdraw_plan(
    plan_path: Path,
    *,
    slug: str,
    reason: str,
    manifest_path: Path,
    repo_root: Path,
    archive_dirname: str = ARCHIVE_DIRNAME,
    today: Optional[date] = None,
) -> ArchiveOutcome:
    """Archive a plan that is being *abandoned*, as distinct from one that
    *completed* (:func:`archive_completed_plan`) or was *superseded* by a
    replacement (:func:`plan_tool.create.archive_existing_source`).

    Shares this module's archive-move / plan-details-move / deregister
    machinery, differing in exactly two places: the archived filename gets a
    ``.withdrawn`` marker before its suffix (``<stem>.withdrawn.md``, so it
    reads as abandoned rather than finished at a glance — mirroring the
    ``.withdrawn.md`` convention already used under ``plan-seeds/archive/``),
    and the prepended breadcrumb carries the caller-supplied ``reason`` and
    today's date rather than a fixed "reached status: completed" claim. A
    reasonless withdrawal reads as completed to the next reader — the
    present-tense-history failure CLAUDE.md's "Documentation is
    forward-looking" section describes — so ``reason`` is required by the CLI
    layer, not optional here.

    The plan-details directory keeps its bare ``<slug>`` name on a
    collision-free move (matching :func:`archive_completed_plan`'s own
    convention) — the ``.withdrawn`` marker lives on the plan file a reader
    actually opens, not on its supporting detail files.

    ``slug`` is caller-supplied rather than read from a parsed ``Plan``,
    because a plan whose premise has been disproved may not be worth
    re-parsing to withdraw it, and because a malformed plan must still be
    withdrawable — mirroring :func:`plan_tool.locator.slug_from_filename`'s
    filename-only derivation, which the CLI layer already uses for this
    reason on ``deregister``.

    ``today`` is parameterizable for deterministic tests; defaults to
    today's local date for production callers.
    """
    outcome = ArchiveOutcome(plan_path=plan_path, slug=slug)
    today = today or date.today()

    if not plan_path.is_file():
        outcome.skipped.append(f"plan file no longer exists: {plan_path}")
        return outcome

    archive_dir = plan_path.parent / archive_dirname
    archive_dir.mkdir(exist_ok=True)

    withdrawn_stem = f"{plan_path.stem}.withdrawn"
    archived_path, collision_suffix = _dedupe_archive_path(
        archive_dir, withdrawn_stem, plan_path.suffix
    )
    if collision_suffix is not None:
        outcome.skipped.append(
            f"archive target "
            f"{archive_dir / f'{withdrawn_stem}{plan_path.suffix}'} already "
            f"exists; archived to {archived_path.name} instead"
        )

    notice = _withdrawal_notice(reason, today)
    try:
        body = plan_path.read_text(encoding="utf-8")
        archived_path.write_text(notice + body, encoding="utf-8")
        plan_path.unlink()
        outcome.archived_to = archived_path
    except OSError as exc:
        outcome.skipped.append(f"could not archive {plan_path}: {exc}")
        return outcome

    _archive_plan_details(
        plan_path,
        archive_dir,
        slug,
        notice,
        outcome,
        preferred_suffix=collision_suffix,
    )

    try:
        from plan_tool.create import remove_from_manifest

        outcome.deregistered = remove_from_manifest(
            manifest_path, repo_root, plan_path
        )
    except CreateError as exc:
        outcome.skipped.append(f"could not deregister {plan_path}: {exc}")

    return outcome


def _archive_plan_details(
    plan_path: Path,
    archive_dir: Path,
    slug: str,
    notice: str,
    outcome: ArchiveOutcome,
    *,
    preferred_suffix: Optional[int] = None,
) -> None:
    """Move ``plan-details/<slug>/`` alongside the archived plan.

    Mirrors the plan-details archival in
    :func:`plan_tool.create.archive_existing_source`. Markdown files get
    ``notice`` prepended so a reader of the per-step detail also sees the
    same breadcrumb the plan file carries — the caller picks which one
    (:func:`_archive_notice` for a completed sweep, :func:`_withdrawal_notice`
    for a withdrawal) so this function stays agnostic to why the plan is
    being archived. Non-markdown files are copied bytes-for-bytes (rare but
    possible — illustrations, screenshots).

    De-collision mirrors the plan-file path in
    :func:`archive_completed_plan`: when the bare ``<slug>/`` target is
    already taken (a same-slug plan was archived before — e.g. a
    ``create --from-existing`` "take 2"), the details move to a
    numerically-suffixed ``<slug>.N/`` instead of being skipped.
    Skipping stranded the live details in the working tree with no plan
    referencing them. ``preferred_suffix`` is the suffix the plan *file*
    de-collided to (``None`` when it didn't collide); trying it first
    keeps the archived plan and its details paired by name.

    Atomicity: per-file copies are staged into a sibling
    ``<details_dst.name>.tmp`` directory and published with a single
    ``os.replace``. A mid-loop ``OSError`` removes the staging
    directory, leaves ``details_src`` intact, and records the failure
    on ``outcome.skipped``; the archive directory contains either the
    complete pre-state or the complete post-state, never a
    half-archived mix.
    """
    details_src = plan_path.parent / "plan-details" / slug
    if not details_src.is_dir():
        return

    details_base = archive_dir / "plan-details"
    bare_dst = details_base / slug
    # Prefer pairing with the plan file's suffix; fall back to the bare
    # name when the plan file didn't collide.
    if preferred_suffix is not None:
        details_dst = details_base / f"{slug}.{preferred_suffix}"
    else:
        details_dst = bare_dst
    if details_dst.exists():
        # Even the preferred/bare target is taken — pick the next free
        # numeric suffix so the details always land somewhere rather
        # than being stranded live.
        n = 2 if preferred_suffix is None else preferred_suffix + 1
        while details_dst.exists():
            details_dst = details_base / f"{slug}.{n}"
            n += 1
        outcome.skipped.append(
            f"plan-details archive target {details_base / slug} already "
            f"exists; archived to {details_dst.name} instead"
        )

    details_dst.parent.mkdir(parents=True, exist_ok=True)
    staging = details_dst.parent / f"{details_dst.name}.tmp"
    if staging.exists():
        shutil.rmtree(staging)

    moves: list[tuple[Path, Path]] = []
    try:
        for child in sorted(details_src.rglob("*")):
            rel = child.relative_to(details_src)
            staged_target = staging / rel
            final_target = details_dst / rel
            if child.is_dir():
                staged_target.mkdir(parents=True, exist_ok=True)
                continue
            staged_target.parent.mkdir(parents=True, exist_ok=True)
            if child.suffix.lower() == ".md":
                body = child.read_text(encoding="utf-8")
                staged_target.write_text(
                    notice + body, encoding="utf-8"
                )
            else:
                staged_target.write_bytes(child.read_bytes())
            moves.append((child, final_target))
        os.replace(staging, details_dst)
    except OSError as exc:
        shutil.rmtree(staging, ignore_errors=True)
        outcome.skipped.append(
            f"could not archive plan-details for slug {slug!r}: {exc}"
        )
        return

    outcome.plan_details_moved.extend(moves)
    shutil.rmtree(details_src)


def sweep_plans(
    entries: list[PlanEntry],
    *,
    manifest_path: Path,
    repo_root: Path,
    dry_run: bool = False,
    archive: bool = True,
    today: Optional[date] = None,
) -> SweepReport:
    """Classify every entry, then archive the completed ones.

    Pass ``dry_run=True`` to get the classifications + a populated
    ``archived`` list reporting what WOULD have moved without touching
    disk. Pass ``archive=False`` for the report-only mode (skip the
    archive list entirely).

    The classification pass is the same in every mode — sweep always
    surfaces the partial-status report.
    """
    classifications = [classify_plan(e) for e in entries]
    report = SweepReport(
        classifications=classifications, dry_run=dry_run
    )

    if not archive:
        return report

    for c in classifications:
        if not c.completed:
            continue
        if dry_run:
            report.archived.append(
                ArchiveOutcome(
                    plan_path=c.entry.path,
                    slug=c.entry.slug,
                    archived_to=c.entry.path.parent
                    / ARCHIVE_DIRNAME
                    / c.entry.path.name,
                    deregistered=False,
                )
            )
        else:
            outcome = archive_completed_plan(
                c,
                manifest_path=manifest_path,
                repo_root=repo_root,
                today=today,
            )
            report.archived.append(outcome)

    return report


@dataclass(frozen=True)
class OrphanPlan:
    """One unregistered plan file discovered beside registered plans.

    ``plan`` is the parsed model when the file validates; ``None`` with
    ``error`` populated when the frontmatter parses as YAML but fails
    schema validation. Files with no frontmatter fence at all never
    reach this type — :func:`discover_orphan_plans` skips them the same
    way :func:`plan_tool.locator.collect_plan_entries` does (a fence-
    less ``.md`` beside the plans is notes, not a malformed plan).
    """

    path: Path
    plan: Optional[Plan]
    error: Optional[str] = None


def discover_orphan_plans(
    entries: Sequence[PlanEntry],
    missing_paths: Sequence[Path] = (),
) -> list[OrphanPlan]:
    """Find top-level ``*.md`` files beside registered plans that the
    manifest doesn't list.

    Scans the parent directory of every registered entry (and of every
    known-missing manifest path, so a directory whose plans were all
    deleted is still swept for newcomers). Only each directory's own
    top-level ``*.md`` files are considered — ``archive/`` and
    ``plan-details/`` live in subdirectories and are excluded by
    construction. An empty manifest anchors no directories, so
    discovery is a no-op there by design (same reasoning as the rest
    of sweep: the manifest is the root of trust for where plans live).

    Read-only. The CLI reports the result and directs the operator to
    ``plan-tool register <path>``; it never adopts an orphan as a sweep
    side effect.
    """
    known: set[Path] = {e.path.resolve() for e in entries}
    known.update(p.resolve() for p in missing_paths)

    dirs: list[Path] = []
    seen: set[Path] = set()
    for p in [e.path for e in entries] + list(missing_paths):
        parent = p.parent.resolve()
        if parent not in seen:
            seen.add(parent)
            dirs.append(parent)

    out: list[OrphanPlan] = []
    for d in dirs:
        for f in sorted(d.glob("*.md")):
            resolved = f.resolve()
            if resolved in known:
                continue
            try:
                plan = parse_plan(resolved)
            except ParseError:
                # No frontmatter fence — notes/readme, not a plan.
                continue
            except ValidationError as exc:
                summary = (
                    "\n".join(format_validation_errors(exc.errors))
                    or str(exc)
                )
                out.append(OrphanPlan(path=resolved, plan=None, error=summary))
                continue
            out.append(OrphanPlan(path=resolved, plan=plan))
    return out
