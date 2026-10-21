"""Parallel apply for ``completeness-apply`` (#74/B2).

The interactive ``completeness-apply`` walk applies one finding at a time,
each a serial Claude round-trip. This module adds an opt-in ``--jobs N``
path that fans those applies out concurrently, mirroring the shipped
``parallel-detail-authoring`` (B1) pattern: a **plan-mutation-free worker**
runs ``apply_finding`` against its *own* isolated copy of the plan tree, and
a **serial, deterministic-order tail** replays each worker's captured content
onto the canonical tree with a parse gate — conflicting findings re-run
serially. See ``docs/how-to/pipeline/run.md``-adjacent notes and the Phase-2 section of
the read-only-audit-split plan.

Why isolation is mandatory: ``apply_finding`` snapshots the plan ``.md`` plus
*every* step's detail file and lets Claude edit any of them
(``launcher.py`` ``apply_finding``), so two concurrent applies against one
tree have fully-overlapping potential write-targets and cannot be made safe
by ``step_id`` partitioning. Each worker therefore edits a private tree; the
tail is the single writer to the canonical tree.

This module is import-light and holds no CLI parsing — ``completeness_cmd.py``
owns the ``--jobs`` flag; the clean-tree gate and the refusal/degrade rules
live in ``completeness_phases.py``'s ``_resolve_apply_walk_targets``.
"""

from __future__ import annotations

import contextlib
import queue
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

from plan_tool.detail_artifacts import DetailFormatError
from plan_tool.parser import UnsupportedPlanFormatVersionError
from plan_tool.review import Recommendation, format_recommendation_for_apply
from plan_tool.telemetry import record_apply_verdict


@dataclass(frozen=True)
class FileChange:
    """One tracked file's pre/post content around a single apply.

    ``path`` is repo-relative (POSIX) so it maps across the isolated worker
    tree and the canonical tree. ``pre`` / ``post`` are the full file
    contents; ``None`` means the file did not exist at that point (a create
    or delete). A change with ``pre == post`` is dropped by the worker (the
    apply left that file untouched)."""

    path: str
    pre: Optional[str]
    post: Optional[str]


@dataclass(frozen=True)
class FindingApplyResult:
    """Outcome of one worker applying one finding in an isolated tree.

    Deliberately decoupled from ``launcher.ApplyFindingResult``: it carries
    only what the serial replay tail needs — the finding, the verdict/summary
    to record, and the captured content changes to replay. ``error`` is set
    (and ``changes`` empty) when the worker raised a *handled* per-finding
    failure that must not abort its siblings; any other exception propagates
    out of the worker as a batch-level abort (mirrors B1's taxonomy).
    ``elapsed`` is the worker's measured wall time, used by the replay
    tail as the logged run-log duration."""

    rec: Recommendation
    verdict: str
    summary: str
    exit_code: int
    changes: tuple[FileChange, ...] = ()
    error: Optional[str] = None
    recordable_verdict: Optional[str] = None
    resolved_step_id: Optional[int] = None
    plan_fingerprint: str = ""
    restoration_succeeded: Optional[bool] = None
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.error is None


def _capture_changes(
    pre_snapshot: dict[Path, Optional[str]],
    repo_root: Path,
) -> tuple[FileChange, ...]:
    """Diff ``pre_snapshot`` (path → pre-content) against current on-disk
    content, returning one :class:`FileChange` per file the apply actually
    changed, keyed by repo-relative POSIX path.

    ``pre_snapshot`` keys are absolute paths inside the worker's tree; the
    returned paths are relative to that tree's ``repo_root`` so the tail can
    re-root them onto the canonical tree.
    """
    changes: list[FileChange] = []
    for abs_path, pre in pre_snapshot.items():
        try:
            post: Optional[str] = abs_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            post = None
        if post == pre:
            continue  # untouched by this apply
        try:
            rel = abs_path.resolve().relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            # Outside the tree (shouldn't happen for tracked plan/detail
            # files); skip rather than emit an unrelocatable change.
            continue
        changes.append(FileChange(path=rel, pre=pre, post=post))
    return tuple(changes)


def apply_finding_in_tree(
    rec: Recommendation,
    *,
    repo_root: Path,
    plan_path: Path,
    plan_name: str,
    carried_findings: Sequence = (),
    invoker=None,
    run_logger=None,
    plan_fingerprint: str = "",
) -> FindingApplyResult:
    """Apply one finding via ``launcher.apply_finding`` against the tree at
    ``repo_root`` and capture the resulting content changes.

    This is the concurrency-safe worker: it mutates only the tree it is
    handed (the canonical tree at ``jobs == 1``, a private isolated copy at
    ``jobs > 1``) and never touches any other tree. It returns the captured
    changes for the serial tail to replay; it does not decide whether to
    keep them.

    A handled per-finding failure (parse error, apply raising) is folded into
    a ``FindingApplyResult`` with ``error`` set and no changes, so a sibling
    worker is unaffected — matching B1's failure isolation.
    """
    from plan_tool.launcher import (
        DeferredApplyVerdict,
        apply_finding,
        shell_invoker,
    )
    from plan_tool.parser import ParseError, ValidationError
    from plan_tool.progress import NullReporter
    from plan_tool.review import audit_targeted_fix

    if invoker is None:
        invoker = shell_invoker

    deferred_outcome: Optional[DeferredApplyVerdict] = None

    def _observe(outcome: DeferredApplyVerdict) -> None:
        nonlocal deferred_outcome
        # A follow-up invocation failure supersedes the primary parsed token.
        deferred_outcome = outcome

    t0 = time.monotonic()
    try:
        result = apply_finding(
            plan_path,
            repo_root=repo_root,
            finding_body=format_recommendation_for_apply(rec),
            targeted_fix=audit_targeted_fix(rec),
            carried_findings=carried_findings,
            step_id=rec.step_id,
            plan_name=plan_name,
            auto_fix_introduced=True,
            invoker=invoker,
            reporter=NullReporter(),
            run_logger=run_logger,
            anchor=rec.anchor or "",
            plan_fingerprint=plan_fingerprint,
            record_verdict=False,
            verdict_observer=_observe,
        )
    except UnsupportedPlanFormatVersionError:
        raise
    except (ParseError, ValidationError) as exc:
        return FindingApplyResult(
            rec=rec, verdict="UNKNOWN", summary="",
            exit_code=1, error=f"plan failed to parse: {exc}",
            elapsed=time.monotonic() - t0,
        )
    except DetailFormatError:
        # A hard, named refusal — never the ordinary per-finding failure
        # this isolation exists for.
        raise
    except Exception as exc:
        if not getattr(exc, "apply_finding_restore_succeeded", False):
            raise
        return FindingApplyResult(
            rec=rec,
            verdict=(deferred_outcome.verdict if deferred_outcome else "UNKNOWN"),
            summary="",
            exit_code=1,
            error=f"worker crashed: {exc}",
            recordable_verdict=(
                deferred_outcome.verdict if deferred_outcome else None
            ),
            resolved_step_id=(
                deferred_outcome.step_id if deferred_outcome else None
            ),
            plan_fingerprint=plan_fingerprint,
            restoration_succeeded=(
                deferred_outcome.restoration_succeeded
                if deferred_outcome else True
            ),
            elapsed=time.monotonic() - t0,
        )

    elapsed = time.monotonic() - t0

    # A non-zero backend exit means the apply failed and ``apply_finding``
    # already restored its snapshot — record it as a failed (non-terminal)
    # result, not a benign no-op, so the tail marks the gap ``failed`` and it
    # is re-prompted rather than silently recorded as resolved.
    if result.exit_code != 0:
        return FindingApplyResult(
            rec=rec, verdict=result.verdict or "UNKNOWN",
            summary=result.summary or "",
            exit_code=result.exit_code,
            error=f"apply exited {result.exit_code}",
            recordable_verdict=(
                deferred_outcome.verdict if deferred_outcome else None
            ),
            resolved_step_id=getattr(result, "step_id", rec.step_id),
            plan_fingerprint=plan_fingerprint,
            restoration_succeeded=(
                deferred_outcome.restoration_succeeded
                if deferred_outcome else True
            ),
            elapsed=elapsed,
        )

    # NOTE: ``_capture_changes`` diffs every path in ``apply_finding``'s
    # ``pre_snapshot``. A declared-but-absent detail path is tracked with
    # ``pre=None``, so a worker-created file becomes a ``FileChange`` the
    # replay tail would write — ``apply_finding`` removes such files on
    # accepted applies instead.
    changes = _capture_changes(result.pre_snapshot, repo_root)
    return FindingApplyResult(
        rec=rec,
        verdict=result.verdict,
        summary=result.summary or "",
        exit_code=result.exit_code,
        changes=changes,
        recordable_verdict=(
            deferred_outcome.verdict if deferred_outcome else result.verdict
        ),
        resolved_step_id=getattr(result, "step_id", rec.step_id),
        plan_fingerprint=plan_fingerprint,
        restoration_succeeded=(
            deferred_outcome.restoration_succeeded
            if deferred_outcome else True
        ),
        elapsed=elapsed,
    )


# --- Deterministic serial replay tail ---------------------------------------

# Apply order: correctness (design gaps) before completeness (what's missing).
_SOURCE_RANK = {"plan-correctness": 0, "plan-completeness": 1}
# Most-severe first within a source.
_SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "nit": 3, "info": 4}


def replay_sort_key(rec: Recommendation) -> tuple:
    """Stable, completion-order-independent ordering for the serial tail:
    ``(source_rank, severity_rank, id)`` — correctness before completeness,
    most-severe first, id as the final tiebreak."""
    return (
        _SOURCE_RANK.get(rec.source, 99),
        _SEVERITY_RANK.get(rec.severity.lower(), 98),
        rec.id,
    )


@dataclass
class ReplayOutcome:
    """What the serial tail did, in deterministic finding order.

    ``applied`` / ``failed`` are ``(rec, note)`` pairs; ``conflicts`` counts
    findings whose captured changes no longer applied cleanly and were re-run
    serially against the now-current canonical tree (re-spending their Claude
    tokens to preserve correctness)."""

    applied: list = field(default_factory=list)
    failed: list = field(default_factory=list)
    conflicts: int = 0


def annotation_status(res: "FindingApplyResult") -> tuple[str, str]:
    """Map an applied-and-parse-clean result to a saved ``(status, note)``.

    Mirrors the serial walk's semantics: ``APPLIED`` → ``applied``;
    ``NOT-APPLICABLE`` → a deliberate ``skip``; ``BLOCKED`` /
    ``BLOCKED-STRUCTURAL`` / ``UNKNOWN`` → a **non-terminal** ``failed`` so the
    gap is re-prompted on the next walk rather than pre-skipped as resolved."""
    v = res.verdict
    if v == "APPLIED":
        return ("applied", v)
    if v == "NOT-APPLICABLE":
        return ("skip", v)
    return ("failed", v)


def _write_change(repo_root: Path, change: FileChange) -> None:
    """Write ``change.post`` to the canonical tree (or delete on ``None``)."""
    target = repo_root / change.path
    if change.post is None:
        if target.exists():
            target.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(change.post, encoding="utf-8")


def _restore(repo_root: Path, changes: "Sequence[FileChange]") -> None:
    """Undo a set of writes by restoring each file's ``pre`` content."""
    for change in changes:
        target = repo_root / change.path
        if change.pre is None:
            if target.exists():
                target.unlink()
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(change.pre, encoding="utf-8")


def _conflicts(repo_root: Path, changes: "Sequence[FileChange]") -> bool:
    """True when any tracked file's current canonical content differs from the
    worker's captured ``pre`` — i.e. an earlier replay already touched it, so
    this worker's isolated ``post`` can't be trusted and must be recomputed."""
    for change in changes:
        target = repo_root / change.path
        try:
            current = target.read_text(encoding="utf-8")
        except FileNotFoundError:
            current = None
        if current != change.pre:
            return True
    return False


def _finding_label(rec: Recommendation) -> str:
    """First non-blank line of the finding body, mirroring the serial
    ``completeness-apply`` walk's ``apply_finding_dispatch`` label so the
    parallel and serial paths produce comparable run-log entries."""
    return next(
        (ln.strip() for ln in rec.body.splitlines() if ln.strip()), rec.source
    )


def replay_results(
    results: "Sequence[FindingApplyResult]",
    *,
    repo_root: Path,
    plan_path: Path,
    plan_name: str,
    rerun_fn=None,
    persist=None,
    run_logger=None,
) -> ReplayOutcome:
    """Replay each worker's captured changes onto the canonical tree, one
    finding at a time in :func:`replay_sort_key` order, with a parse gate.

    For a clean result (no conflict) the captured ``post`` content is written
    to the canonical tree. When an earlier replay already touched one of the
    finding's files (:func:`_conflicts`), the finding is **re-run serially**
    against the now-current canonical tree via ``rerun_fn`` (which mutates the
    canonical tree in place, exactly like the single-writer serial path).
    After either path the plan is re-parsed; a parse failure reverts that
    finding's writes and records it as failed — no partial, unparseable plan
    is left behind. Ordering of the returned outcome is independent of the
    order results completed in.

    ``persist(rec, status, note)`` — when given — is called for each finding
    the *instant* its disposition is decided (edit landed / reverted / failed),
    so an interrupt mid-tail loses at most the in-flight finding's annotation
    rather than every one (matching the serial walk's incremental persist).

    When ``run_logger`` is given, each finding also gets an ``apply_finding_
    dispatch`` ``phase_start``/``phase_end`` pair, emitted here in this same
    deterministic order rather than thread-completion order."""
    from plan_tool.parser import ParseError, ValidationError, parse_plan

    if rerun_fn is None:
        def rerun_fn(rec):
            return apply_finding_in_tree(
                rec, repo_root=repo_root, plan_path=plan_path,
                plan_name=plan_name,
            )

    outcome = ReplayOutcome()

    def _record_telemetry(res: FindingApplyResult) -> None:
        verdict = res.recordable_verdict
        if verdict is None or res.restoration_succeeded is False:
            return
        # APPLIED is authoritative only when an edit actually landed.
        if verdict == "APPLIED" and not res.changes:
            return
        try:
            record_apply_verdict(
                repo_root,
                plan_slug=plan_name,
                verdict=verdict,
                step_id=(
                    str(res.resolved_step_id)
                    if res.resolved_step_id is not None
                    else None
                ),
                anchor=res.rec.anchor or "",
                plan_fingerprint=res.plan_fingerprint,
            )
        except Exception:
            pass

    def _record_failed(rec, note):
        outcome.failed.append((rec, note))
        if persist is not None:
            persist(rec, "failed", note)

    def _record_result(rec, res):
        # Route by the mapped annotation status so the outcome buckets match
        # what's persisted: a BLOCKED/UNKNOWN result (status "failed") lands in
        # ``failed``, an APPLIED/NOT-APPLICABLE one (applied/skip) in
        # ``applied`` — the summary counts stay honest.
        status, note = annotation_status(res)
        if status == "failed":
            outcome.failed.append((rec, note))
        else:
            outcome.applied.append((rec, res.verdict))
        if persist is not None:
            persist(rec, status, note)

    ordered = sorted(results, key=lambda r: replay_sort_key(r.rec))
    for res in ordered:
        rec = res.rec
        # The logged duration/verdict — reassigned to the rerun's result on a
        # conflict (below) so the run-log reflects the finding's real final
        # state rather than the stale worker result that triggered the rerun.
        final_res = res
        final_reverted = False
        if run_logger is not None:
            run_logger.phase_start(
                "apply_finding_dispatch",
                step_id=rec.step_id,
                source=rec.source,
                finding_label=_finding_label(rec),
            )
        try:
            if not res.ok:
                _record_telemetry(res)
                _record_failed(rec, res.error or "apply failed")
                continue
            if not res.changes:
                # A verdict with no edits (NOT-APPLICABLE / clean noop): nothing
                # to replay, just record the mapped disposition.
                _record_telemetry(res)
                _record_result(rec, res)
                continue

            applied_changes = res.changes
            if _conflicts(repo_root, res.changes):
                # Stale isolated post — recompute against current canonical.
                outcome.conflicts += 1
                fresh = rerun_fn(rec)
                final_res = fresh
                if not fresh.ok:
                    _record_telemetry(fresh)
                    _record_failed(rec, fresh.error or "re-run failed")
                    continue
                # ``apply_finding`` already wrote the fresh edits to canonical.
                applied_changes = fresh.changes
                res = fresh
            else:
                for change in res.changes:
                    _write_change(repo_root, change)

            # Parse gate: a broken plan wedges the rest of the tail.
            try:
                parse_plan(plan_path)
            except UnsupportedPlanFormatVersionError:
                _restore(repo_root, applied_changes)
                final_reverted = True
                raise
            except (ParseError, ValidationError) as exc:
                _restore(repo_root, applied_changes)
                final_reverted = True
                _record_failed(rec, f"reverted — plan failed to parse: {exc}")
                continue
            _record_telemetry(res)
            _record_result(rec, res)
        finally:
            if run_logger is not None:
                run_logger.phase_end(
                    "apply_finding_dispatch",
                    int(final_res.elapsed * 1000),
                    (
                        "reverted" if final_reverted
                        else "error" if final_res.error
                        else final_res.verdict.lower()
                    ),
                    step_id=rec.step_id,
                    source=rec.source,
                    verdict=(
                        "REVERTED" if final_reverted
                        else final_res.verdict
                    ),
                )
    return outcome


# --- Concurrent dispatch ----------------------------------------------------


def dispatch_parallel(
    recs: "Sequence[Recommendation]",
    apply_one: "Callable[[Recommendation], FindingApplyResult]",
    *,
    jobs: int,
) -> list[FindingApplyResult]:
    """Run ``apply_one`` over ``recs`` on a bounded thread pool and return the
    results (order-independent — the serial tail re-sorts).

    Concurrency is capped at ``min(jobs, len(recs))``; threads (not processes)
    because each ``apply_one`` blocks on a ``claude`` subprocess and shares no
    Python state that needs pickling. Failure isolation matches B1: an
    ordinary exception escaping ``apply_one`` for one finding becomes a failed
    :class:`FindingApplyResult` for *that* finding and never aborts its
    siblings. ``DetailFormatError`` and an unsupported plan format instead
    abort without replaying any isolated-tree candidate into the canonical tree.
    """
    recs = list(recs)
    if not recs:
        return []
    workers = min(max(1, jobs), len(recs))

    def _guarded(rec: Recommendation) -> FindingApplyResult:
        t0 = time.monotonic()
        try:
            return apply_one(rec)
        except (DetailFormatError, UnsupportedPlanFormatVersionError):
            # A hard, named refusal — never the ordinary per-item failure
            # this isolation exists for. Abort the batch before it records
            # a failed finding result or replays a sibling candidate into the
            # canonical tree. Already-running isolated workers may finish, but
            # their disposable changes are never published.
            raise
        except Exception as exc:  # failure isolation — never abort siblings
            if getattr(exc, "apply_finding_restore_succeeded", None) is False:
                raise
            # Stamp elapsed even on this fallback path: apply_one may have
            # already run a real (timed) claude call before a *later* step
            # (e.g. _capture_changes) raised, and the replay tail's run-log
            # phase_end reports this duration — an unstamped 0.0 would
            # under-report exactly the failure case where it matters most.
            return FindingApplyResult(
                rec=rec, verdict="UNKNOWN", summary="",
                exit_code=1, error=f"worker crashed: {exc}",
                elapsed=time.monotonic() - t0,
            )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(_guarded, recs))


# --- Worktree isolation pool ------------------------------------------------


@dataclass(frozen=True)
class IsolatedTree:
    """One isolated working copy handed to a worker: its ``repo_root`` and the
    plan file's path inside it."""

    repo_root: Path
    plan_path: Path


def _git(repo_root: Path, *args: str) -> "tuple[int, str]":
    proc = subprocess.run(
        ["git", *args], cwd=repo_root, stdin=subprocess.DEVNULL,
        capture_output=True, text=True,
    )
    return proc.returncode, (proc.stderr or proc.stdout).strip()


class WorktreePool:
    """A pool of ``count`` git worktrees off HEAD, one working copy per worker
    slot, handed out via :meth:`acquire`.

    Each worktree is a full checkout (shares the object store — cheap) so
    ``apply_finding``'s deterministic re-checks see the real code tree.
    :meth:`acquire` resets its worktree to HEAD before yielding, so every
    worker applies against a pristine copy of the canonical tree — the
    invariant the replay tail's conflict detection relies on. The clean-tree
    gate (caller's) guarantees HEAD == the canonical working tree.

    Setup/teardown mutate shared worktree admin and run serially; the
    per-worktree resets during :meth:`acquire` are independent (each worktree
    locks its own index).
    """

    def __init__(
        self, repo_root: Path, count: int, plan_rel: str, slug: str,
    ) -> None:
        import os
        import time

        self._repo_root = repo_root
        self._count = count
        self._plan_rel = plan_rel
        self._slug = slug
        # A per-run token keeps worktree paths and branch names unique across
        # runs, so a crashed/killed prior run's stale branch never blocks a
        # later provisioning (``worktree add -b`` refuses an existing branch)
        # and two concurrent runs of the same plan don't collide.
        self._token = f"{os.getpid()}-{time.monotonic_ns()}"
        self._free: "queue.Queue[Path]" = queue.Queue()
        self._all: list[Path] = []
        self._branches: list[str] = []
        self._base: Optional[Path] = None

    def __enter__(self) -> "WorktreePool":
        from plan_tool.cli.gitcommit import worktree_add
        from plan_tool.worktree import worktree_base

        rc, head = _git(self._repo_root, "rev-parse", "HEAD")
        if rc != 0:
            raise RuntimeError(f"could not resolve HEAD for isolation: {head}")
        base = (
            worktree_base(self._repo_root)
            / f".parallel-apply-{self._slug}-{self._token}"
        )
        self._base = base
        for i in range(self._count):
            wt = base / f"slot-{i}"
            branch = f"plan-tool/parallel-apply/{self._slug}-{self._token}-{i}"
            rc, tail = worktree_add(
                self._repo_root, wt, branch, create=True, start_point=head,
            )
            if rc != 0:
                self.__exit__(None, None, None)
                raise RuntimeError(
                    f"could not provision isolation worktree {i}: {tail}"
                )
            self._all.append(wt)
            self._branches.append(branch)
            self._free.put(wt)
        return self

    @contextlib.contextmanager
    def acquire(self):
        wt = self._free.get()
        try:
            # Pristine HEAD state before this worker's apply.
            _git(wt, "reset", "--hard", "--quiet", "HEAD")
            _git(wt, "clean", "-fdq")
            yield IsolatedTree(repo_root=wt, plan_path=wt / self._plan_rel)
        finally:
            self._free.put(wt)

    def __exit__(self, *exc) -> None:
        import shutil

        from plan_tool.cli.gitcommit import worktree_remove

        for wt in self._all:
            worktree_remove(self._repo_root, wt, force=True)
        for branch in self._branches:
            _git(self._repo_root, "branch", "-D", branch)
        # Best-effort: drop the pool's base dir so no empty slot skeleton
        # leaks under the worktree base after removal.
        if self._base is not None:
            shutil.rmtree(self._base, ignore_errors=True)
        _git(self._repo_root, "worktree", "prune")
        self._all.clear()
        self._branches.clear()


def run_parallel_apply(
    recs: "Sequence[Recommendation]",
    *,
    repo_root: Path,
    plan_path: Path,
    plan_name: str,
    jobs: int,
    invoker=None,
    run_logger=None,
    pool_factory=None,
    persist=None,
    plan_fingerprint: str = "",
    compute_plan_fingerprint_fn=None,
    pre_apply_presentation: Optional[Callable[[], None]] = None,
) -> ReplayOutcome:
    """Apply ``recs`` concurrently in isolated worktrees, then replay the
    captured changes serially onto the canonical tree.

    Provisions ``min(jobs, len(recs))`` isolated worktrees (or uses
    ``pool_factory`` — injected in tests), fans the per-finding applies out
    with :func:`dispatch_parallel`, and merges the results with
    :func:`replay_results`. Conflicting findings are re-run serially against
    the canonical tree inside the replay tail. ``persist(rec, status, note)``
    is forwarded to :func:`replay_results` for incremental annotation writes.
    ``pre_apply_presentation`` runs once in the parent before worker
    provisioning and remains outside the finding queue.
    Returns the replay outcome.
    """
    recs = list(recs)
    if pre_apply_presentation is not None:
        pre_apply_presentation()
    if not recs:
        return ReplayOutcome()
    workers = min(max(1, jobs), len(recs))
    plan_rel = plan_path.resolve().relative_to(repo_root.resolve()).as_posix()

    if pool_factory is None:
        def pool_factory(count):
            return WorktreePool(
                repo_root, count, plan_rel, plan_name,
            )

    with pool_factory(workers) as pool:
        def apply_one(rec: Recommendation) -> FindingApplyResult:
            with pool.acquire() as tree:
                return apply_finding_in_tree(
                    rec, repo_root=tree.repo_root, plan_path=tree.plan_path,
                    plan_name=plan_name, invoker=invoker,
                    run_logger=run_logger,
                    plan_fingerprint=plan_fingerprint,
                )

        results = dispatch_parallel(recs, apply_one, jobs=workers)

    # Conflict re-runs happen against the canonical tree — thread the same
    # invoker so a custom (e.g. test) backend is honored there too.
    def _rerun(rec: Recommendation) -> FindingApplyResult:
        rerun_plan_fingerprint = ""
        if compute_plan_fingerprint_fn is not None:
            try:
                rerun_plan_fingerprint = compute_plan_fingerprint_fn()
            except Exception:
                pass
        return apply_finding_in_tree(
            rec, repo_root=repo_root, plan_path=plan_path,
            plan_name=plan_name, invoker=invoker,
            run_logger=run_logger,
            plan_fingerprint=rerun_plan_fingerprint,
        )

    return replay_results(
        results, repo_root=repo_root, plan_path=plan_path,
        plan_name=plan_name, rerun_fn=_rerun, persist=persist,
        run_logger=run_logger,
    )
