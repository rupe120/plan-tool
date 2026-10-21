"""Convergence-diagnostic command module — the ``convergence`` verb.

``plan-tool convergence <name>`` loads a plan's saved completeness/reconcile
report history, runs the diagnostic (:mod:`plan_tool.convergence_diagnosis`),
and prints the rendered verdict — whether the audit/apply loop is converging,
plus any run-readiness (blocking findings / code drift) or finding-churn
advisory.

A pure "tell me the state" diagnostic: it spends no Claude, mutates nothing,
writes no run-log entry, and always exits 0 — there is no
``--fail-on-findings`` rc-flip and no ``--min-runs`` floor.

Modeled on :func:`plan_tool.cli.inspect.cmd_status` (an ``args``-only read-only
handler), not :func:`~plan_tool.cli.inspect.cmd_validate`, precisely because
this command omits the rc-flip. Like every per-intent command module it
imports only the cycle-free leaves (:mod:`plan_tool.cli.context`,
:mod:`plan_tool.cli.parser`) and domain packages — never :mod:`plan_tool.cli.app`.
"""

from __future__ import annotations

import argparse

from plan_tool.cli.context import _load_context
from plan_tool.cli.parser import Handler
from plan_tool.convergence_diagnosis import (
    diagnose_convergence,
    load_audit_evidence_ledger,
    load_report_history,
    load_saved_reviews,
    render_audit_evidence_ledger,
    render_diagnosis,
)
from plan_tool.jira_grade import GRADE_DEFAULT, JIRA_GRADE_VALUES
from plan_tool.locator import resolve_plan_for_context
from plan_tool.review_persistence import compute_plan_fingerprint, list_report_artifacts


def _current_audit_stage(ctx, path, *, detail_grade: str) -> str | None:
    """The plan's *current* bare/detail audit stage, or ``None`` on failure.

    ``detail_grade`` must match the grade the operator wants to agree with
    (``completeness-audit --grade``'s default is run grade) -- a plan
    audited only at jira grade has no run-grade detail files, so resolving
    at the wrong grade silently reads it as bare.

    Best-effort: this diagnostic's contract is to always exit 0 and never
    require a valid plan parse (unlike ``completeness-audit``, which needs
    the plan anyway). A parse failure or missing plan here degrades to the
    pre-stage-bar blanket blocking behavior (:func:`diagnose_convergence`'s
    defaults) rather than surfacing an error.
    """
    from plan_tool.cli.completeness_phases import derive_audit_stage
    from plan_tool.parser import parse_plan
    from plan_tool.review import audit_detail_bundle_status

    try:
        plan = parse_plan(path)
        bundle_status = audit_detail_bundle_status(
            plan, path, ctx.repo_root, detail_grade=detail_grade
        )
        return derive_audit_stage(bundle_status)
    except Exception:
        return None


def cmd_convergence(args: argparse.Namespace) -> int:
    """Diagnose whether a plan's audit/apply loop is converging.

    Resolves the plan, loads its saved report history, diagnoses it, and
    prints the rendered verdict. Always returns 0 (``no-history`` /
    ``insufficient-history`` / ``converging``). Read-only: no Claude call, no
    mutation, no run-log entry. An unresolvable ``name`` still surfaces a
    non-zero error from name resolution upstream.

    Diagnoses against the plan's *current* bare/detail audit stage
    (:func:`_current_audit_stage`) using the same stage-differentiated
    blocking bar ``completeness-audit`` uses, so the two commands agree on
    whether a still-open medium conceptual finding counts as blocking.
    ``--grade`` selects which detail bundle to resolve the stage against —
    match whichever grade ``completeness-audit`` was run at, or the two
    commands can disagree about a plan audited only at jira grade. Falls
    back to :func:`~plan_tool.convergence_diagnosis.diagnose_convergence`'s
    blanket-blocking defaults when the stage can't be determined.
    """
    ctx = _load_context(args)
    path = resolve_plan_for_context(ctx, args.name)
    artifact_paths = list_report_artifacts(path)
    saved_reviews = load_saved_reviews(path, artifact_paths=artifact_paths)
    history = load_report_history(path, saved_reviews=saved_reviews)
    audit_stage = _current_audit_stage(ctx, path, detail_grade=args.grade)
    if audit_stage is None:
        diagnosis = diagnose_convergence(
            history, mechanism_advisory_grade=args.grade
        )
    else:
        diagnosis = diagnose_convergence(
            history,
            audit_stage=audit_stage,
            classify_domain=lambda f: f.domain or "unknown",
            mechanism_advisory_grade=args.grade,
        )
    diagnosis_output = render_diagnosis(diagnosis)
    ledger_output = render_audit_evidence_ledger(
        load_audit_evidence_ledger(
            path,
            saved_reviews=saved_reviews,
            artifact_paths=artifact_paths,
        )
    )
    print(f"{diagnosis_output}\n\n{ledger_output}")
    # Decision telemetry (#72, best-effort): the verdict + how many saved runs
    # it read — the recurrence signal #57's tuning would aggregate.
    from plan_tool.locator import slug_from_filename
    from plan_tool.telemetry import record_convergence

    # plan_fingerprint only (best-effort): the verdict is about report recurrence
    # keyed to the plan, not code state; a compute error must not perturb this
    # command's always-exits-0 read-only contract. No parsed Plan here, so no map.
    try:
        _conv_plan_fp = compute_plan_fingerprint(path)
    except Exception:
        _conv_plan_fp = ""
    record_convergence(
        ctx.repo_root,
        plan_slug=slug_from_filename(path) or args.name or "",
        verdict=diagnosis.verdict,
        runs=len(history.runs),
        plan_fingerprint=_conv_plan_fp,
    )
    return 0


def register(subparsers) -> dict[str, Handler]:
    """Add the ``convergence`` subparser and return its handler map."""
    p = subparsers.add_parser(
        "convergence",
        help="diagnose whether a plan's audit/apply loop is converging",
    )
    p.add_argument(
        "name",
        help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md",
    )
    p.add_argument(
        "--grade",
        choices=JIRA_GRADE_VALUES,
        default=GRADE_DEFAULT,
        dest="grade",
        help=(
            f"which detail bundle to resolve the bare/detail audit stage "
            f"against (default: {GRADE_DEFAULT}) — match whichever grade "
            "`completeness-audit` was run at, or the two commands can "
            "disagree about a plan audited only at jira grade"
        ),
    )
    return {"convergence": cmd_convergence}
