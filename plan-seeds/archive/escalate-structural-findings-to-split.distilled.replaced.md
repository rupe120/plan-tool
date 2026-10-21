> **Replaced**: this file has been superseded by `docs/implementation-plans/2-escalate-structural-findings-to-split.md`.
> Preserved here for history; do not edit.

## Overview

This plan builds a bridge that routes an already-classified **structural finding** (one whose only correct fix is to split a step into two) to the **already-existing split engine**, under the same safety gates used by `detail --split` Phase B. Today such a finding is recognized but dead-ended: the audit tags it `detail-purity` and the convergence loop skips it, or `apply_finding` returns a bare `BLOCKED` and the caller reverts and reports. This is routing and plumbing — no new split capability — so the apply/convergence path can finish what it starts instead of dead-ending. Hard invariant: a structural plan edit never happens unattended; unattended escalation only recommends.

## Problem statement

A finding whose only correct fix is "split this step into two" is recognized but dead-ended. The purity self-check tags a step that mixes refactor + feature as `detail-purity` (`review.py`), excludes it from `APPLY_ELIGIBLE_SOURCES`, and the convergence loop skips it with the triage reason *"the fix is to split it into type-pure steps, not an apply edit."* Separately, when Claude determines mid-apply that the only correct fix is a split, `apply_finding` returns a bare `BLOCKED` and the caller reverts and reports. The split engine that would resolve these (`create._propose_step_split` / `create._apply_step_split`, gated by `detail._split_is_safe`, confirmed by `detail._confirm_split`, with downstream migration via `detail._migrate_downstream_details_after_split`) already exists and is already wired to this exact trigger in `detail --split` Phase B — just nowhere else. The result is that `apply_finding`/convergence cannot finish what they start.

## Architecture

A new seam — `escalate_to_split(plan_path, *, step_id, repo_root, invoker, ...)` — given a structural finding and its target step, behaves as follows:

- **Always first:** re-parse the plan and run `_split_is_safe(plan, step_id)`. If a downstream step has already run/started, do **not** split — surface a recommendation to re-plan instead. (Mirrors `detail.py` Phase B; honors the non-PENDING-run-state gate.)
- **Propose:** call `_propose_step_split(step, invoker, ...)` to get the replacement `--into` titles + rationale from Claude.
- **Interactive + opt-in (TTY and the split opt-in flag set):** run `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` — the exact Phase-B sequence. The convergence loop then finishes in one pass.
- **Unattended (CI / `--yes` / non-TTY):** never mutate structure. Emit a structured split *recommendation* (proposed titles + rationale) into the findings report so the operator runs `plan-tool split` later.

**What "structural finding" means — two triggers, both in scope:**

1. **Pre-classified — `detail-purity`.** The skip in the convergence loop becomes an escalation.
2. **Discovered mid-apply — `BLOCKED-STRUCTURAL`.** A new verdict bucket on `apply_finding`. When Claude, mid-apply, determines the only correct fix is a split (not a prose edit), it emits `## Verdict: BLOCKED-STRUCTURAL` rather than a bare `BLOCKED`. This catches structural needs the audit did not pre-classify.

A single predicate `review.is_structural(rec)` (seeded with `detail-purity`) and the new verdict together define the escalation set.

The split engine (`create._propose_step_split` / `create._apply_step_split`), the safety gate (`detail._split_is_safe`), the operator confirm (`detail._confirm_split`), and downstream-detail migration (`detail._migrate_downstream_details_after_split`) are all reused verbatim.

**Composes with the granularity advisor.** `step-granularity-advisor.md` *produces* `granularity-split` (formerly `detail-purity`) findings; this bridge *executes* them. This work stands alone on today's classification, but the two are designed to pair.

**Touch points (for step decomposition):**

- `review.py` — add `is_structural(rec)`; keep `detail-purity` out of `APPLY_ELIGIBLE_SOURCES` but route it to escalation instead of skip.
- `launcher.py` — extend `parse_apply_verdict` / `ApplyFindingResult` with `BLOCKED-STRUCTURAL`; add the `escalate_to_split` helper (reusing the lazy `create` imports already used in `detail.py` Phase B).
- the `apply-finding` prompt template — teach it to emit `BLOCKED-STRUCTURAL`.
- the `create`/`detail` convergence loop — call the bridge where `detail-purity` is currently skipped.
- `cli/review_actions.py` — handle `BLOCKED-STRUCTURAL` in the apply walk's verdict branch (currently reverts + reports at the `BLOCKED` / `NOT-APPLICABLE` arm).

## Out of scope

- New split *algorithm* or any change to renumbering / dependency rewiring — reuse `_apply_step_split` as-is.
- Auto-splitting in unattended mode — the repo invariant is that a structural plan edit never happens unattended.
- Restructuring beyond a single-step split (e.g. merging steps, N-way re-plan).

## Risks

- **Unattended structural mutation.** Failure shape: a split executes in CI / `--yes` / non-TTY, violating the repo invariant. Severity: high. Mitigation: callers gate on TTY + the split opt-in flag; unattended paths emit a recommendation only, never mutate structure.
- **Splitting a step whose downstream work already started.** Failure shape: structure is mutated after a downstream step has run/started, corrupting run state. Mitigation: `_split_is_safe(plan, step_id)` runs before any split; on failure, surface a re-plan recommendation instead. Unresolved gap: relies on the non-PENDING-run-state gate being correctly honored, mirroring `detail.py` Phase B.
- **Invoker seam not neutralized in tests.** Failure shape: tests spawn the real `claude` binary because the bridge shells out via `_propose_step_split`. Mitigation: neutralize the invoker seams per `TESTING.md`.

## Testing

Mirror source modules per `TESTING.md` (`plan_tool/X.py` → `tests/test_X.py`), defaulting to unit tests. Neutralize the invoker seams — the bridge shells out to Claude via `_propose_step_split`, so any test driving `escalate_to_split` must override the invoker or the autouse gate in `tests/conftest.py` will raise.

- `tests/test_review.py` — cover `review.is_structural(rec)` returning true for `detail-purity` and false otherwise; confirm `detail-purity` stays excluded from `APPLY_ELIGIBLE_SOURCES`.
- `tests/test_launcher.py` — cover `parse_apply_verdict` / `ApplyFindingResult` recognizing `BLOCKED-STRUCTURAL`; unit-test `escalate_to_split` for the safe-split, unsafe-split (re-plan recommendation), interactive-opt-in (apply sequence runs), and unattended (recommendation only, no mutation) paths.
- `tests/cli/test_review_actions.py` (or the mirror of `cli/review_actions.py`) — cover the `BLOCKED-STRUCTURAL` branch in the apply walk's verdict handling.
- Integration (`@pytest.mark.integration`): exercise the `create`/`detail` convergence loop end-to-end so a `detail-purity` finding routes to escalation instead of being skipped, and converges in one interactive pass. Run these when modifying the convergence loop, `launcher.py`, or `review.py`.

Existing suites for `review.py`, `launcher.py`, and `cli/review_actions.py` must still pass.

## Acceptance criteria

- `review.is_structural(rec)` returns true for a `detail-purity` finding and false for non-structural findings.
- `detail-purity` remains excluded from `APPLY_ELIGIBLE_SOURCES` and is routed to `escalate_to_split` rather than skipped by the convergence loop.
- `apply_finding` emits `## Verdict: BLOCKED-STRUCTURAL` (parsed by `parse_apply_verdict` into `ApplyFindingResult`) when Claude determines mid-apply that the only correct fix is a split.
- `escalate_to_split` runs `_split_is_safe(plan, step_id)` before any split; when a downstream step has run/started it does not split and surfaces a re-plan recommendation.
- In interactive mode with the split opt-in flag set, `escalate_to_split` runs `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` and the convergence loop finishes in one pass.
- In unattended mode (CI / `--yes` / non-TTY), `escalate_to_split` never mutates plan structure and emits a structured split recommendation (proposed titles + rationale) into the findings report.
- A surfaced split recommendation keeps rc 0 unless `--fail-on-findings` is passed (exit-code convention).
- Auto-execution of a split occurs only behind the explicit opt-in flag (aligned with `detail --split`'s `allow_split`), never default-on in the convergence loop.
