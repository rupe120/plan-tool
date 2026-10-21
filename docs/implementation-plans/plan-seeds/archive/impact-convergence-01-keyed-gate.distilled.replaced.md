> **Replaced**: this file has been superseded by `docs/implementation-plans/2-gate-convergence-by-impact.md`.
> Preserved here for history; do not edit.

## Overview

Add an augment-only impact-aware convergence gate so a finding blocks when `rec.impact == "high"` or its severity already blocks. The new predicate will be used only at the seven loop-continuation assignments, preserving deterministic/data-contract exit-code behavior, self-consistency manual-fix gates, and the existing apply short-circuit. This monotonic change can keep loops open for high-downstream-cost findings without allowing earlier convergence.

## Problem statement

The convergence loop currently uses only `plan_tool/convergence.py:49` `is_blocking(severity)` and `BLOCKING_SEVERITIES` to decide whether to continue. Although `Recommendation.impact` is already parsed and present on the findings handled by the loop drivers, it is only used by `plan_tool/review.py:4814` `should_apply`, not by the stop decision. As a result, a `medium`-severity seam finding with `impact=high` can fail to hold the loop open even though its downstream cost is high.

## Architecture

Add `is_blocking_impact(rec: Recommendation) -> bool` beside `is_blocking` in `plan_tool/convergence.py`. It returns true for `rec.impact == "high"` or `is_blocking(rec.severity)`; when `rec.impact is None`, it follows the existing severity behavior. The predicate is deliberately additive, so it promotes high-impact findings but never removes an existing severity-based block.

Replace `is_blocking(r.severity)` with `is_blocking_impact(r)` only in the seven `has_blocking_findings` loop-continuation assignments: `plan_tool/cli/completeness_cmd.py:1695`, `plan_tool/cli/completeness_cmd.py:2327`, `plan_tool/cli/reconcile.py:1561`, `plan_tool/cli/reconcile.py:1945`, `plan_tool/cli/reconcile.py:2041`, `plan_tool/cli/reconcile.py:2075`, and `plan_tool/review.py:6422`. Keep the predicate shape or a clear named seam for #154 and the future demote slice, without implementing demotion.

`Recommendation.impact` / `.complexity` already flow from `plan_tool/review.py:358` through `_split_triage_tags`, so this plan adds no prompt, schema, or data-contract plumbing. Update the existing severity-gate notes in `docs/AUDIT_FLOW.md` and `CLAUDE.md`, and update `BACKLOG.md` #152 after the augment slice lands.

## Out of scope

- The demote form of #152: do not make blocking depend on `impact` alone or remove severity-based blocks; it is blocked on #154 calibration.
- Recurrence / report-history routing (#153): do not read cross-run history, touch `convergence_diagnosis.py`, or add structural escalation.
- Impact calibration / drift correlation (#154): do not add learning, correlation, or auto-tuning.
- Prompt / schema changes: do not modify `plan_tool/prompts/plan-audit.md`, the `Recommendation` shape, or `DATA_CONTRACT.md`.
- Existing deterministic/data-contract, self-consistency, and apply gates: do not re-key `plan_tool/cli/completeness_cmd.py:2411–2415`, `plan_tool/cli/completeness_cmd.py:1772`, `plan_tool/cli/completeness_cmd.py:1905`, `convergence_diagnosis.py:459`, or `plan_tool/review.py:4814` onto impact.
- New severities or triage vocabulary: reuse `low`/`medium`/`high`/`None`.

## Risks

- A high-impact tag could cause additional loop iterations; severity: bounded by the monotonic augment design. Mitigation: only `impact == "high"` promotes a finding, while `low` and `medium` impact do not.
- `None`-impact deterministic and `data-contract` findings could stop blocking if fallback behavior is wrong; severity: regression in required blocking behavior. Mitigation: `rec.impact is None` falls back to `is_blocking(rec.severity)`.
- Broad replacement of `is_blocking(r.severity)` could alter manual-fix, exit-code, spin-detection, or apply behavior; severity: unintended scope expansion. Mitigation: restrict changes to the enumerated seven loop-continuation sites.
- Re-keying stop on impact alone without calibration could converge earlier or trust an ungrounded self-graded axis; severity: unsafe demotion. Mitigation: do not implement the demote form before #154.

## Testing

- Add unit tests in `tests/test_convergence.py` for `is_blocking_impact(rec)`: `impact="high"` blocks even when severity would not; blocking severity still blocks; `impact is None` follows `is_blocking(rec.severity)`; and `nit`/`info` with `impact=low` remain non-blocking.
- Test the loop-continuation wiring in `plan_tool/cli/completeness_cmd.py`, `plan_tool/cli/reconcile.py`, and `plan_tool/review.py:6422` so a `medium`-severity, `impact=high` recommendation keeps the relevant loop open, while low-impact advisory findings reach `no_blocking_findings`.
- Verify that `plan_tool/cli/completeness_cmd.py:2411–2415`, `plan_tool/cli/completeness_cmd.py:1772`, `plan_tool/cli/completeness_cmd.py:1905`, `convergence_diagnosis.py:459`, and `plan_tool/review.py:4814` remain unchanged.
- Include a regression proving the augment wiring is monotonic: no test input converges earlier than under the prior severity gate.

## Acceptance criteria

- `plan_tool/convergence.py` defines `is_blocking_impact(rec: Recommendation) -> bool` that returns true when `rec.impact == "high"` or `is_blocking(rec.severity)` is true, including when `rec.impact is None`.
- A `medium`-severity finding with `impact=high` keeps each updated loop-continuation gate running rather than exiting through `no_blocking_findings`.
- A `None`-impact / `data-contract` finding continues to block under the existing severity behavior.
- `nit` or `info` findings with `impact=low` can still exit through `no_blocking_findings`.
- The updated gate is monotonic: it does not make any input converge earlier than the severity-only gate.
- `plan_tool/cli/completeness_cmd.py:2411–2415`, `plan_tool/cli/completeness_cmd.py:1772`, `plan_tool/cli/completeness_cmd.py:1905`, `convergence_diagnosis.py:459`, and `plan_tool/review.py:4814` are unchanged.
- `docs/AUDIT_FLOW.md` and `CLAUDE.md` state that the augment slice has landed, and `BACKLOG.md` #152 records the augment slice as shipped while the demote form remains pending on #154.

## Deferred

- The demote form of #152 (`block ⟺ impact == high`) remains pending and blocked on #154 calibration.
- Recurrence / report-history routing is deferred to #153.
- Impact calibration, drift correlation, and auto-tuning are deferred to #154.
