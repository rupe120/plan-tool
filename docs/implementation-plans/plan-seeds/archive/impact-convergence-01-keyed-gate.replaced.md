> **Replaced**: this file has been superseded by `docs/implementation-plans/2-gate-convergence-by-impact.md`.
> Preserved here for history; do not edit.

# Plan seed: key convergence-loop blocking on the `impact` axis, not `severity` alone (augment slice only)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing docs/implementation-plans/plan-seeds/impact-convergence-01-keyed-gate.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source:** `BACKLOG.md` **#152** — "Key convergence blocking on the `impact`
> axis, not `severity` alone (augment now; the demoting form gated on #154)."
> This is the **entry point** of the impact-convergence arc **#152 → {#153,
> #154} → #152 demote**. This seed covers the **augment slice of #152 ONLY**.
> Its final docs/status step must update `BACKLOG.md`'s #152 entry once the
> augment slice lands: mark the augment slice shipped and leave the **demote
> form explicitly still-pending and blocked on #154** (do not remove the whole
> entry — the demote half is out of scope here).

## Problem statement

The iterate/completeness convergence loop decides "keep going vs. stop" purely
from **severity**. `plan_tool/convergence.py:49`'s `is_blocking(severity)`
(`BLOCKING_SEVERITIES = {medium, high, critical}`) is folded into
`state.has_blocking_findings = any(is_blocking(r.severity) for r in ...)` by the
loop drivers, and `should_continue` exits with `"no_blocking_findings"` when that
is False.

But every `Recommendation` already carries a **second, downstream-cost axis** —
`impact` / `complexity` (`plan_tool/review.py:358`), parsed from the
`(impact=…, complexity=…)` tag that `plan_tool/prompts/plan-audit.md` mandates —
and it is consumed **only** by the *apply* short-circuit
(`plan_tool/review.py:4814` `should_apply`, the `complexity <= impact` rule),
**never** by the stop decision. Severity measures the plan's *internal*
coherence; impact measures *downstream cost* (does the gap break at a jira ticket
boundary?). They diverge: a `medium`-severity **seam** finding (an inter-step
contract) with `impact=high` should hold the loop open though the severity rule
alone wouldn't; a `high`-severity fill-in-for-free detail with `impact=low`
shouldn't.

## Ground truth (confirmed at HEAD)

- **The predicate:** `plan_tool/convergence.py:49` `is_blocking(severity)` +
  `BLOCKING_SEVERITIES` (line ~47). Keep this function; add a sibling.
- **The impact data already reaches the gate:** the `current_findings` /
  `recs` lists the loop drivers iterate are the same `Recommendation` objects
  that carry `.impact`. No new plumbing, prompt, or schema is needed — the
  signal is *collected but not consulted at the stop gate*.
- **Impact is populated on ≈70% of findings** (measured 144/206 across the
  saved completeness corpus): `impact=high` on 30 (the true blockers),
  low/medium-impact + low-complexity on ~90 (the oscillation sink), and
  **`None` on 62** — the deterministic well-formedness and `data-contract`
  sources, which the prompt never asks for an impact tag.
- **The loop-continuation gate sites** (the ONLY sites this plan changes) — the
  `has_blocking_findings` assignments:
  - `plan_tool/cli/completeness_cmd.py:1695` and `:2327`
  - `plan_tool/cli/reconcile.py:1561`, `:1945`, `:2041`, `:2075`
  - `plan_tool/review.py:6422` — the low-yield rule's `material_new` filter
    (`docs/AUDIT_FLOW.md`'s "Severity-aware low-yield convergence").
- **Sites that MUST stay severity-based (do NOT touch):**
  - `plan_tool/cli/completeness_cmd.py:2411–2415` — the exit-code determination
    over `data_contract_recs` / `self_consistency_recs` / `audit_recs`. These
    are the `None`-impact deterministic findings that must **always** block.
  - `plan_tool/cli/completeness_cmd.py:1772` and `:1905` — the two
    `SELF_CONSISTENCY_SOURCES`-filtered gates (manual-fix hint at 1772; the
    `_loop_stop_reason = "manual_fix_blocking_findings"` gate at 1905).
    Self-consistency findings are deterministic and `None`-impact, so even the
    `None`-fallback would leave them unchanged — but leave them on
    `is_blocking(severity)` explicitly to keep the diff surgical and the intent
    clear (they are manual-fix-required gates, not the impact-gradable
    conceptual-audit continuation).
  - `plan_tool/convergence_diagnosis.py:459` — the spin-detection filter;
    that surface belongs to #153, not this plan.
  - `plan_tool/review.py:4814` `should_apply` — the *apply* short-circuit
    already reads impact correctly; leave it.
  - **Completeness note:** these plus the 7 loop-continuation sites above
    account for **every** `is_blocking(r.severity)` call site at HEAD — the
    allowlist is total, so a plan author never has to guess whether an
    unlisted site is in or out of scope.

## Resolved design decisions

1. **Add `is_blocking_impact(rec: Recommendation) -> bool` in
   `convergence.py`** (next to `is_blocking`). Contract — the **augment**
   (monotonic) wiring:
   - `True` if `rec.impact == "high"` **OR** `is_blocking(rec.severity)`.
   - When `rec.impact is None`, fall back to `is_blocking(rec.severity)`
     (reusing the existing `None → treat-by-default` convention) — so
     deterministic / `data-contract` findings still block exactly as today.
   - This is strictly **additive**: impact can only *promote* a finding to
     blocking, never *demote* one that severity already blocks. It therefore
     cannot cause earlier convergence than today's behavior — the safety
     property that lets it ship before #154.
2. **Swap `is_blocking(r.severity)` → `is_blocking_impact(r)` at the
   loop-continuation sites listed above, and nowhere else.** The `data-contract`
   / self-consistency exit-code sites and the apply short-circuit stay on
   `is_blocking(severity)` / their existing reads.
3. **Do not add the demote form.** The demote wiring (`block ⟺ impact == high`,
   which *removes* severity-based blocks) is **out of scope** and blocked on
   #154's calibration — keying *stop* on a self-graded axis without ground
   truth is unsafe. The plan must leave a clear, named seam (e.g. a comment /
   the predicate shape) so #154 + the demote slice can extend it, but must not
   implement demotion.
4. **No prompt, schema, or data-contract change.** `impact` is already emitted
   and parsed; this plan only *reads* it at a new site.

## Seams to reuse (verified at HEAD)

- `plan_tool/convergence.py` — `is_blocking`, `BLOCKING_SEVERITIES`,
  `ConvergenceState.has_blocking_findings`, `should_continue`.
- `plan_tool/review.py:358` — `Recommendation.impact` / `.complexity` fields
  (already populated by `check_plan_audit` / `extract_reconcile_recommendations`
  via `_split_triage_tags`).
- The seven `has_blocking_findings` assignment sites enumerated above.

## Scope of work (indicative — let create decompose)

1. `is_blocking_impact(rec)` in `convergence.py` (augment/monotonic contract,
   `None`-fallback), with unit tests in `tests/test_convergence.py`.
2. Swap the predicate at the loop-continuation sites in `completeness_cmd.py`,
   `reconcile.py`, and `review.py:6422` — leaving the deterministic/data-contract
   and apply sites untouched.
3. Tests proving the behavior change and its bounds (see acceptance).
4. Docs: a one-line update where `docs/AUDIT_FLOW.md` and `CLAUDE.md` already
   note the severity-keyed gate (both carry a pointer to this arc) to say the
   augment slice has landed; update `BACKLOG.md` #152 (augment shipped, demote
   still pending on #154).

## Non-goals / out of scope (guardrails — do not cross)

> Inherits BACKLOG **#152**'s `Scope / Non-goals` fence — the section below
> elaborates that boundary and introduces no new scope.

- **The demote form of #152.** Do not make blocking key on `impact` *alone*,
  do not remove any severity-based block. Augment only. (Blocked on #154.)
- **Recurrence / report-history routing (#153).** Do not read cross-run
  history, do not touch `convergence_diagnosis.py`, do not add a structural
  escalation from the loop. That is a separate arc step.
- **Impact calibration / drift correlation (#154).** Do not build any
  learning, correlation, or auto-tuning of the impact axis. This plan *trusts*
  the impact tag as-emitted, safely, because augment is monotonic.
- **Prompt / schema changes.** Do not modify `plan-audit.md`, the
  `Recommendation` shape, or `DATA_CONTRACT.md` — impact already flows.
- **The data-contract / self-consistency / apply sites.** Do not re-key
  `completeness_cmd.py:2411–2415`, `convergence_diagnosis.py:459`, or
  `review.py:4814` onto impact.
- **Widening to new severities or a new triage vocabulary.** Reuse the existing
  `impact` values (`low`/`medium`/`high`/`None`); invent nothing.

## Acceptance criteria (plan-level)

- `is_blocking_impact(rec)` exists in `convergence.py`, blocks on
  `impact=="high"` OR `is_blocking(severity)`, and falls back to
  `is_blocking(severity)` when `impact is None`.
- A `medium`-severity, `impact=high` finding **keeps the loop running**
  (regression: today it would let it stop).
- A `None`-impact / `data-contract` finding **still blocks** (no regression).
- Advisory (`nit`/`info`, `impact=low`) findings still exit via
  `no_blocking_findings` — no new spinning.
- The change is **monotonic**: no test input converges *earlier* than under the
  pre-change severity gate. The demote form is not present.
- The deterministic/data-contract exit-code sites and the apply short-circuit
  are unchanged.
- `BACKLOG.md` #152 records the augment slice shipped with the demote form
  still pending on #154.
