"""Auto-reconcile on drift (, Lesson 13).

When an iteration loop's drift halt fires, run a focused reconcile
against the step(s) that own the drifted files and persist the
findings. Replaces the legacy "drift detected on file X; halt + bare
warning" UX with structured findings the operator can act on via
``plan-tool reconcile-plan-walk``.

The helper lives in its own module so the four iteration entry
points (``cmd_completeness``, ``_iterate_reconcile_loop``,
``create_plan``, ``generate_detail``) share one implementation
without create.py / detail.py taking a backward dependency on
cli.py. Module dependencies:

- ``plan_tool.launcher`` for ``run_step`` + ``LauncherError``
- ``plan_tool.review`` for ``extract_reconcile_recommendations``
- ``plan_tool.review_persistence`` for ``save_review``

stdlib-only at the public-API boundary except ``plan_tool.style``
(cheap, stdlib-only) for diagnostic styling, which is imported
eagerly; the ``launcher`` / ``review`` / ``review_persistence``
imports happen lazily inside :func:`run_auto_reconcile_on_drift` so
this module stays cheap to import from any iteration-loop call site.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from plan_tool.style import tool


def run_auto_reconcile_on_drift(
    *,
    drifted,
    file_to_step,
    plan_path: Path,
    plan_slug: str,
    repo_root: Path,
    run_logger: Optional[object] = None,
    file=None,
) -> int:
    """Run a focused reconcile on the step(s) that own drifted files,
    save findings to disk, and print a structured summary.

    Implements Lesson 13 ("audit beats observe"): instead of just
    surfacing "drift on file X" as a raw signal that puts the
    investigative burden on the operator, run the downstream analysis
    primitive (``reconcile``) on the affected scope and emit findings
    inline with the halt. The reconcile findings are persisted via
    ``save_review`` so ``plan-tool reconcile-plan-walk`` can pick them up
    interactively.

    Best-effort throughout: launcher errors, non-zero claude exits,
    and disk-write failures emit fallback notes and continue rather
    than crashing the iteration loop. Returns the total number of
    findings raised across all reconciled steps so the caller can
    include a count in further output if useful.

    Runtime-cost note: each affected step spawns a fresh ``run_step``
    (``shell_invoker``) — a real, potentially multi-minute claude call —
    from the drift-halt path, i.e. at the moment concurrent edits were
    just noticed. This is deliberate (Lesson 13: audit beats observe),
    but callers wiring it into a tight loop should know it can spend one
    backend call per drifted step, not a cheap local check.

    ``file_to_step`` shape is ``dict[Path, tuple[int, str]]`` mapping
    resolved absolute paths to ``(step_id, step_title)`` -- typically
    produced by :func:`scope_guard.build_file_to_step_map`.
    """
    out = file if file is not None else sys.stderr

    # Bucket drifted paths by owning step. Files outside any step's
    # files declaration (rare but possible if scope_guard surfaces
    # paths not in step.files) get skipped -- there's no step to
    # scope a reconcile to.
    buckets: dict[int, tuple[str, list[Path]]] = {}
    unmapped: list[Path] = []
    for p in drifted:
        # Resolve absolute first; build_file_to_step_map stores
        # resolved keys.
        key = p.resolve() if p.is_absolute() else (repo_root / p).resolve()
        info = file_to_step.get(key)
        if info is None:
            unmapped.append(p)
            continue
        step_id, step_title = info
        existing = buckets.get(step_id)
        if existing is None:
            buckets[step_id] = (step_title, [p])
        else:
            existing[1].append(p)

    if not buckets:
        # No mapped files → can't run reconcile against a specific
        # step. Surface this so the operator knows the auto-audit
        # didn't fire.
        tool(
            "auto-reconcile skipped: no drifted file maps "
            "to a plan step (run `plan-tool detail <slug> --reconcile "
            "--step N` manually to investigate)",
            stream=out,
        )
        return 0

    tool(
        f"running auto-reconcile on {len(buckets)} affected "
        f"step(s) to surface what the drift means for the plan "
        f"(Lesson 13: audit > observe)...",
        stream=out,
    )

    # Local imports keep the module's load-time graph clean -- the
    # auto-reconcile path is opt-in and we don't want to pull in
    # launcher/review at every iteration-loop import.
    from plan_tool.detail_artifacts import DetailFormatError
    from plan_tool.fingerprint import compute_code_fingerprint
    from plan_tool.launcher import run_step, LauncherError
    from plan_tool.parser import ParseError, ValidationError, parse_plan
    from plan_tool.review import extract_reconcile_recommendations
    from plan_tool.review_persistence import compute_plan_fingerprint, save_review
    from plan_tool.review_walk import stamp_target_signatures

    # Capture both staleness axes once for the per-step saves below. The
    # plan is unchanged during a drift halt, so parse a single time.
    # Best-effort per this function's contract: a parse failure falls back
    # to plan_fingerprint="" + code_fingerprint=None ("never computed")
    # rather than poisoning the drift halt. ``compute_plan_fingerprint`` is
    # a pure file hash and won't raise.
    plan_fp = compute_plan_fingerprint(plan_path)
    code_fp: Optional[dict[str, str]] = None
    # Init to None before the try: on a parse failure ``_parsed_plan`` would be
    # unbound, so a later ``is not None`` guard would raise UnboundLocalError.
    _parsed_plan = None
    try:
        _parsed_plan = parse_plan(plan_path)
        code_fp = compute_code_fingerprint(_parsed_plan, plan_path, repo_root)
    except (ParseError, ValidationError):
        plan_fp = ""
        code_fp = None

    total_findings = 0
    for step_id in sorted(buckets):
        step_title, _files = buckets[step_id]
        # Direction-of-truth choice: drifted code that wasn't in scope means
        # "the operator needs to know what the drift means for the plan",
        # which is exactly what detail --reconcile (code-is-truth,
        # plan-edit findings) is designed for.
        try:
            result = run_step(
                plan_path,
                repo_root=repo_root,
                step_id=step_id,
                mode="detail-reconcile",
                dry_run=False,
                run_logger=run_logger,
            )
        except LauncherError as exc:
            # A detail-format refusal is a hard, named error, not the
            # ordinary launcher failure this per-step skip exists for —
            # continuing here would turn the new fail-closed rule back
            # into a best-effort skip. Walk the cause chain rather than
            # checking only ``__cause__`` directly: ``run_step`` wraps the
            # renderer's ``DetailGradeError`` into this ``LauncherError``,
            # and the renderer itself wrapped the original
            # ``DetailFormatError``.
            cause = exc.__cause__
            while cause is not None:
                if isinstance(cause, DetailFormatError):
                    raise
                cause = cause.__cause__
            tool(
                f"auto-reconcile on step {step_id}: "
                f"launcher error ({exc}); skipping",
                stream=out,
            )
            continue
        if result.exit_code != 0:
            tool(
                f"auto-reconcile on step {step_id} "
                f"(\"{step_title}\"): claude exited "
                f"{result.exit_code}; skipping (run "
                f"`plan-tool detail {plan_slug} --reconcile "
                f"--step {step_id}` manually)",
                stream=out,
            )
            continue

        recs = extract_reconcile_recommendations(
            result.stdout, step_id=step_id, source="detail-reconcile",
        )
        # Persist a canonical repo-relative POSIX value, not a lexical warning path.
        try:
            plan_rel = plan_path.resolve().relative_to(
                repo_root.resolve()
            ).as_posix()
        except ValueError:
            plan_rel = str(plan_path.resolve())
        # No-op today (detail-reconcile recs carry no directive), wired for the
        # uniform "stamp before save" rule. Fall back to unstamped recs when the
        # plan didn't parse — the best-effort contract must not raise here.
        stamped_recs = (
            stamp_target_signatures(_parsed_plan, recs)
            if _parsed_plan is not None
            else recs
        )
        try:
            saved_path = save_review(
                plan_slug=plan_slug,
                plan_path=plan_rel,
                repo_root=repo_root,
                report_md=result.stdout,
                recommendations=stamped_recs,
                kind="detail-reconcile",
                step_id=step_id,
                plan_fingerprint=plan_fp,
                code_fingerprint=code_fp,
                plan=_parsed_plan,
            )
        except OSError as exc:
            # Best-effort persistence: a disk-write failure (full
            # disk, permissions, parallel cleanup) shouldn't poison
            # the drift halt. Surface the gap on stderr; the operator
            # can still see the reconcile findings in the claude
            # stdout streamed above by shell_invoker.
            tool(
                f"auto-reconcile on step {step_id} "
                f"(\"{step_title}\"): {len(recs)} finding(s) raised "
                f"but save failed ({exc}); see claude stdout above "
                f"for the raw report",
                stream=out,
            )
            total_findings += len(recs)
            continue
        total_findings += len(recs)
        tool(
            f"auto-reconcile on step {step_id} "
            f"(\"{step_title}\"): {len(recs)} finding(s) raised "
            f"(saved to {saved_path})",
            stream=out,
        )

    if unmapped:
        tool(
            f"auto-reconcile skipped {len(unmapped)} "
            f"drifted file(s) outside any step.files declaration",
            stream=out,
        )

    if total_findings > 0:
        tool(
            f"walk findings interactively with "
            f"`plan-tool reconcile-plan-walk {plan_slug}`",
            stream=out,
        )

    return total_findings
