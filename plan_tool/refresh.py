"""Reusable plan-refresh entry point: drift-gate, scoped reconcile, re-stamp.

One call answers "is this plan still grounded against the code, and if
not, re-ground it." It is pure wiring over existing primitives — it mints
no judgement of its own:

- :func:`plan_tool.grounding.read_grounding` +
  :func:`plan_tool.grounding.check_grounding_drift` decide drift with
  **zero Claude** (a streamed-SHA-256 map diff, no backend).
- :func:`plan_tool.auto_reconcile.run_auto_reconcile_on_drift` is the
  supported seam for scoping a reconcile to the drifted files — it saves
  findings for ``reconcile-plan-walk`` rather than applying them, honoring
  the plan's *No auto-apply without surfacing* boundary.
- :func:`plan_tool.grounding.write_grounding` re-stamps the sidecar so the
  next refresh's gate clears.

Three branches: no stored grounding → treat as "needs grounding",
reconcile over the whole declared surface, then write a first baseline;
stored grounding + no code drift → fast no-op, no Claude, no sidecar
rewrite; stored grounding + drift → reconcile scoped to exactly the
drifted files, then re-stamp. Footprint membership alone (a ``files:``/
``creates:`` rewrite) restamps without reconcile; a still-declared path
that vanished from disk is routed through reconcile instead of a silent
restamp.

The module is the shared implementation behind the step-4
``reconcile-plan --refresh`` CLI shim and the branch-awareness
branch-creation hook; both import :func:`refresh_plan` directly. It
imports nothing from ``plan_tool/cli/*``; the reconcile seam is imported
function-locally so the no-drift path never even pulls in
``launcher``/``review``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from plan_tool.fingerprint import compute_code_fingerprint
from plan_tool.grounding import (
    check_grounding_drift,
    read_grounding,
    write_grounding,
)
from plan_tool.locator import slug_from_filename
from plan_tool.parser import parse_plan
from plan_tool.review_persistence import compute_plan_fingerprint
from plan_tool.scope_guard import build_file_to_step_map
from plan_tool.telemetry import (
    DRIFT_VERDICT_DRIFTED,
    DRIFT_VERDICT_NO_BASELINE,
    DRIFT_VERDICT_NO_DRIFT,
    code_fingerprint_digest,
    record_drift_gate,
)


@dataclass
class RefreshOutcome:
    """What one :func:`refresh_plan` call did, so the CLI shim (step 4)
    and the branch hook can render/branch on it without re-deriving it.

    ``needs_grounding`` is ``True`` only on the no-baseline path (a
    pre-feature plan whose drift scope was synthesized as the whole
    declared surface). ``drifted`` is ``True`` whenever a reconcile ran;
    ``reconciled`` mirrors it (both ``False`` only on the fast no-op path).
    ``drifted_files`` are absolute, resolved, sorted paths the reconcile
    was scoped to (empty on the fresh path). ``grounding_path`` is the
    re-stamped sidecar path, or ``None`` when nothing was written — the
    fast no-op path, *and* the pending-findings path: the baseline is
    re-stamped only when the reconcile surfaced **zero** findings, so a
    drift with unapplied findings leaves the gate dirty (BACKLOG #68).
    """

    plan_slug: str
    needs_grounding: bool = False
    drifted: bool = False
    drifted_files: list[Path] = field(default_factory=list)
    findings: int = 0
    reconciled: bool = False
    grounding_path: Optional[Path] = None


def refresh_plan(
    plan_path: Path,
    repo_root: Path,
    *,
    run_logger: Optional[object] = None,
    file=None,
) -> RefreshOutcome:
    """Drift-gate ``plan_path`` against the code, reconcile + re-stamp on drift.

    Reads the grounding baseline and compares it to the current code
    fingerprint with no Claude call. On an unchanged tree returns a clean
    :class:`RefreshOutcome` having spawned no invoker and rewritten no
    sidecar. On drift (or an absent baseline) runs a focused reconcile
    over the owning steps via
    :func:`plan_tool.auto_reconcile.run_auto_reconcile_on_drift` and
    re-stamps the grounding sidecar to record the examined code state.

    A malformed plan markdown lets ``parse_plan``'s ``ParseError`` /
    ``ValidationError`` propagate — a hard caller error, distinct from the
    soft "absent sidecar" case ``read_grounding`` swallows.
    """
    plan = parse_plan(plan_path)
    plan_slug = slug_from_filename(plan_path)  # default_to_stem=True → non-None
    assert plan_slug is not None

    current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)

    def _emit_drift_gate(
        verdict: str,
        drifted_count: int,
        findings_count: int,
        plan_fp: Optional[str] = None,
    ) -> None:
        # Best-effort at the caller: the plan-fingerprint compute runs in refresh's
        # code before record_drift_gate (itself best-effort), so wrap the whole
        # body — a raising fingerprint compute must not change the outcome. Skip
        # the extra plan-file read on the hot no-drift path (code_fp is in hand).
        # ``plan_fp`` may be passed in when the caller already hashed the plan file
        # (the findings==0 restamp path), avoiding a redundant read+SHA.
        try:
            if verdict == DRIFT_VERDICT_NO_DRIFT:
                plan_fp = ""
            elif plan_fp is None:
                plan_fp = compute_plan_fingerprint(plan_path)
            code_state = code_fingerprint_digest(current_code_fp)
            record_drift_gate(
                repo_root,
                plan_slug=plan_slug,
                verdict=verdict,
                drifted_files=drifted_count,
                findings=findings_count,
                plan_fingerprint=plan_fp,
                code_fingerprint=code_state,
            )
        except Exception:
            return

    grounding = read_grounding(plan_path)

    if grounding is None:
        # No baseline (pre-feature or corrupt sidecar): treat as "needs
        # grounding" — synthesize a whole-plan drift scope, reconcile the
        # declared surface, and write a first baseline so the next refresh
        # gate clears.
        file_to_step = build_file_to_step_map(plan, repo_root)
        drifted_files = sorted(file_to_step)
        needs_grounding = True
    else:
        code_diff = check_grounding_drift(
            grounding, current_code_fp, repo_root
        )
        if code_diff.match:
            # Fast no-op: stored fingerprints unchanged. No Claude call,
            # no sidecar rewrite — the working tree stays byte-identical. The
            # only write is one gitignored telemetry line (no tracked file).
            _emit_drift_gate(DRIFT_VERDICT_NO_DRIFT, 0, 0)
            return RefreshOutcome(plan_slug=plan_slug)
        file_to_step = build_file_to_step_map(plan, repo_root)
        # Declared paths missing from the current fingerprint (deleted on
        # disk while still in files:/creates:). Same shape as a files:
        # rewrite in the map — must not silent-restamp.
        still_declared = [
            p for p in code_diff.footprint_removed if p in file_to_step
        ]
        if not code_diff.content_drifted:
            # Footprint membership only. A files:/creates: rewrite is not
            # code drift — restamp without reconcile. Still-declared
            # deletes go through reconcile instead.
            if still_declared:
                drifted_files = still_declared
                needs_grounding = False
            else:
                plan_fp = compute_plan_fingerprint(plan_path)
                grounding_out = write_grounding(
                    plan_path,
                    plan_fingerprint=plan_fp,
                    code_fingerprint=current_code_fp,
                    # Already in hand from the read above — pass it through
                    # rather than let write_grounding's preserve-sentinel
                    # re-read+re-parse the same sidecar (BACKLOG #165 review).
                    step_authoring_fingerprints=grounding.step_authoring_fingerprints,
                )
                _emit_drift_gate(DRIFT_VERDICT_DRIFTED, 0, 0, plan_fp=plan_fp)
                return RefreshOutcome(
                    plan_slug=plan_slug,
                    drifted=True,
                    drifted_files=[],
                    findings=0,
                    reconciled=False,
                    grounding_path=grounding_out,
                )
        else:
            # Content edits ∪ still-declared deletes (do not let a clean
            # content reconcile restamp those away unscoped).
            drifted_files = sorted(
                set(code_diff.content_drifted) | set(still_declared)
            )
            needs_grounding = False

    # Reconcile-and-restamp tail (no-baseline + drift branches). The seam
    # is imported function-locally so the no-drift path above never pulls
    # in launcher/review, reinforcing the zero-Claude guarantee and letting
    # tests patch the reconcile entry point.
    from plan_tool.auto_reconcile import run_auto_reconcile_on_drift

    findings = run_auto_reconcile_on_drift(
        drifted=drifted_files,
        file_to_step=file_to_step,
        plan_path=plan_path,
        plan_slug=plan_slug,
        repo_root=repo_root,
        run_logger=run_logger,
        file=file,
    )

    # Re-stamp ONLY when the reconcile surfaced nothing to apply. The seam
    # SAVES findings (for reconcile-plan-walk) but does NOT apply them, so
    # restamping while findings are pending would clear the drift gate against
    # a plan that's still unreconciled — the next --refresh would read
    # "no drift" and mask the staleness (BACKLOG #68). ``findings == 0`` is the
    # convergence signal: the code fingerprint moved but nothing plan-affecting
    # remains, so stamping is safe. With pending findings we leave the baseline
    # un-stamped, keeping the gate dirty until a walk applies them.
    grounding_out: Optional[Path] = None
    tail_plan_fp: Optional[str] = None
    if findings == 0:
        # Hash the plan file once here and reuse it for the drift-gate event
        # below, avoiding a second read+SHA on this reconcile-clean path.
        tail_plan_fp = compute_plan_fingerprint(plan_path)
        grounding_out = write_grounding(
            plan_path,
            plan_fingerprint=tail_plan_fp,
            code_fingerprint=current_code_fp,
            # ``grounding`` is None on the no-baseline branch — nothing to
            # carry forward there. Otherwise already in hand from the read
            # above (BACKLOG #165 review; same reasoning as the tail above).
            step_authoring_fingerprints=(
                grounding.step_authoring_fingerprints
                if grounding is not None
                else {}
            ),
        )

    _emit_drift_gate(
        DRIFT_VERDICT_NO_BASELINE if needs_grounding else DRIFT_VERDICT_DRIFTED,
        len(drifted_files),
        findings,
        plan_fp=tail_plan_fp,
    )

    return RefreshOutcome(
        plan_slug=plan_slug,
        needs_grounding=needs_grounding,
        drifted=True,
        drifted_files=drifted_files,
        findings=findings,
        reconciled=True,
        grounding_path=grounding_out,
    )
