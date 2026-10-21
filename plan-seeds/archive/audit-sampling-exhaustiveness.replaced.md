> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-sampling-exhaustiveness.md`.
> Preserved here for history; do not edit.

# Plan seed: make the conceptual audit's sampling exhaustion-aware (stop dry, not mid-discovery)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/audit-sampling-exhaustiveness.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Scope: lean v1 = the adaptive stop condition only.** Make
> `audit_plan_until_stable` keep sampling while it is *still discovering* and
> stop only when it genuinely goes dry, with a hard safety cap. The bigger
> coverage levers — per-step audit fan-out, diversified sample lenses, an
> in-loop post-apply re-sample — are parked in `## Deferred`. v1 fixes the one
> defect with the clearest evidence: the audit quits mid-discovery.

---

## Overview

The conceptual completeness audit samples a non-deterministic Claude check N
times and unions the findings by stable slug (`review.audit_plan_until_stable`).
Today it stops at `max_samples = 3` or after a single dry sample
(`dry_rounds = 1`). On a deep plan that ceiling truncates an **unconverged**
sampling process: the audit stops while it is still finding new issues, so each
pass captures only a partial slice of the true finding set. Make the stop
condition **exhaustion-aware** — continue while marginal-new findings stay
above a threshold, stop only after `dry_rounds ≥ 2` consecutive zero-new
samples, bounded by a hard safety cap — so one audit pass captures the stable
set instead of the first three samples' worth.

## Problem statement — the audit stops mid-discovery, and that masquerades as churn

`review.py:audit_plan_until_stable` (defaults at `review.py:4319`):

```python
AUDIT_DEFAULT_MAX_SAMPLES = 3
AUDIT_DEFAULT_DRY_ROUNDS  = 1
```

The loop unions findings by stable slug and breaks on `consecutive_dry >=
dry_rounds` **or** at `max_samples`. Two defects:

1. **The cap truncates while still discovering.** Observed on a real 9-step plan
   (`escalate-structural-findings-to-split`), the marginal-new sequence was:

   ```
   sample 1/3 → +3 new   (3 unique)
   sample 2/3 → +2 new   (5 unique)
   sample 3/3 → +1 new   (6 unique)   ← still positive
   unioned 6 findings over 3 samples
   ```

   It stopped at the **budget ceiling**, not on dryness — sample 3 was still
   surfacing a new finding. Sample 4+ would very likely have found more.

   A second pass corroborates: a *fresh* `--no-reuse-audit` run on the same
   plan surfaced a **HIGH** finding (`guard-b-create-side`, a real create-side
   trigger-2 inconsistency) that the earlier 3-sample pass — which capped at 3
   while still discovering — never reported. One pass does not see the whole
   set; a different pass sees a different slice.

2. **`dry_rounds = 1` is too weak a convergence proof.** A single no-new sample
   declares the set complete — but the code's own comment admits "one sample
   can't prove itself complete." With the `known_anchors` slug-reuse feedback
   (`review.py:4441`) nudging later samples to re-confirm what's already found, a
   sample can come back dry by *redundancy* while the tail is still unsampled.

**Why it matters beyond cost.** Because the audit stops before going dry, *every*
non-trivial plan keeps yielding new findings on each fresh look. That confounds
two very different situations the operator must distinguish:

- the plan is genuinely **mis-shaped** (real non-convergence → re-decompose), vs.
- the audit simply **never exhausted the finding set** (a sampling artifact; the
  plan may be fine).

So the recurrence signal that BACKLOG #57 (the non-convergence detector) and the
RUNBOOK "won't converge → re-decompose" workflow lean on is **polluted by
undersampling**. Making one audit pass exhaustive is what lets recurrence
actually *mean* "the plan is mis-shaped" — the same-concept-recurs vs.
different-concept-each-pass distinction only holds if a single pass saw the whole
set. This work is a prerequisite for trusting #57's signal.

## Design

### Adaptive, exhaustion-aware stop (the v1 core)

In `audit_plan_until_stable`, replace "stop at `max_samples` or one dry sample"
with:

- **Keep sampling while productive.** Continue as long as the last sample's
  marginal-new count is `>= new_threshold` (default 1 — any new finding means
  the set isn't exhausted).
- **Stop on genuine dryness.** Break only after `dry_rounds` (default raised to
  **2**) *consecutive* zero-new samples — two dry samples in a row is a real
  convergence signal; one is noise.
- **Hard safety cap.** Bound total samples by a `max_samples` ceiling raised to
  a safe upper bound (e.g. 6–8) so a pathological plan can't sample forever;
  when the cap is hit while marginal-new is still positive, **log that the audit
  stopped at the cap, not on dryness** (no silent truncation — the operator must
  know coverage was budget-limited).
- **No cost regression on shallow plans.** A plan that goes dry in two samples
  still costs two Claude calls; only a plan that *keeps* discovering pays for the
  extra samples it actually needs.

### Keep the existing seams

- The `invoker=` seam stays — sampling must remain stubbable so tests script a
  marginal sequence without spawning Claude (per `TESTING.md`).
- Union-by-stable-slug and the `known_anchors` feedback are unchanged; only the
  stop condition changes.
- `--audit-samples N` keeps working as an explicit override (pins the cap); add a
  `--audit-dry-rounds N` surface if a CLI lever is warranted, else keep the
  raised default internal.

## Step decomposition (apply the single-concern rule — BACKLOG #58)

- **Feature step** — exhaustion-aware stop in `review.audit_plan_until_stable`:
  raise `dry_rounds` default, raise the safety cap, continue-while-productive,
  and emit a "stopped at cap, not dry" log when truncated. Unit tests script
  marginal sequences (`[3,2,1,0,0]` → stops after the 2nd consecutive dry;
  `[1,1,1,1,1,1,…]` → stops at the safety cap with the truncation log).
- **Feature step (optional)** — CLI/default surface: thread any new
  `--audit-dry-rounds` and the raised cap through `parser.py` /
  `completeness_cmd.py`, regen the CLI reference.
- **Non-code step** — note the new sampling behavior in RUNBOOK (the convergence
  workflow) and cross-link #57: recurrence is only trustworthy once a pass is
  exhaustive.

## Out of scope

- Changing the conceptual-audit *prompt* content or what counts as a finding.
- The union/dedup mechanism (stable-slug keying, `known_anchors`) — reused as-is.
- Auto-applying anything — this changes only how *thoroughly* the audit samples.

## Risks

- **Cost blow-up on a genuinely deep plan.** Severity: medium (minimize-Claude
  posture). Mitigation: the hard safety cap + the continue-while-productive
  threshold mean extra calls happen only when each one is still returning
  findings; a dry plan pays nothing extra. Surface the per-run sample count so
  cost stays visible.
- **More samples → more slug drift / semantic dupes.** Severity: low. The
  `known_anchors` feedback already collapses re-found concepts onto established
  slugs; more samples lean on it harder but don't change its mechanism.
- **Test seam not neutralized.** Severity: low. Mitigation: tests inject a
  scripted invoker returning a fixed marginal sequence; the conftest gate
  catches a real `claude` spawn.

## Acceptance criteria

- `dry_rounds` default is **≥ 2**: a single no-new sample no longer stops
  sampling; two consecutive zero-new samples do.
- Sampling continues while the last sample's marginal-new count is `>=
  new_threshold`, up to a raised hard cap; a plan still discovering at the old
  3-sample point keeps going.
- When the hard cap is reached while marginal-new is still positive, the run
  logs that coverage was **budget-limited (stopped at cap, not dry)** — no
  silent truncation.
- A shallow plan that goes dry in two samples costs exactly two Claude calls (no
  regression).
- `audit_plan_until_stable` stays driven through the `invoker=` seam; unit tests
  script marginal sequences and assert the stop point without spawning Claude.
- Existing `audit_plan_until_stable` / completeness tests stay green.

## Deferred

- **Per-step audit fan-out** — audit each step's detail independently and union,
  so step-local issues aren't drowned out when one call reasons over all 9 steps
  at once. Bigger change to the audit's shape; revisit after v1 proves the
  adaptive stop helps.
- **Diversified sample lenses** — vary each sample's framing (correctness /
  completeness / edge-case) to decorrelate samples and raise coverage per call,
  instead of N identical prompts.
- **In-loop post-apply conceptual re-sample** — today `--iterate` re-runs only
  *deterministic* checks after an apply ("no new claude audit"), so convergence
  is declared without re-checking the conceptual layer against the mutated plan.
  A single fresh sample after applying would catch issues the edit introduced.
- **Feeding the per-run sample count / "stopped at cap" signal into BACKLOG #57**
  so the non-convergence detector can distinguish budget-limited coverage from
  real recurrence.

## References

- `review.py:audit_plan_until_stable` (the sampling loop) and
  `AUDIT_DEFAULT_MAX_SAMPLES` / `AUDIT_DEFAULT_DRY_ROUNDS` (`review.py:4319`).
- BACKLOG #57 (decomposition convergence loop) — its recurrence signal is
  confounded by this defect; this work is a prerequisite for trusting it.
- RUNBOOK → "When repeated audit/apply doesn't converge" — the same-concept vs.
  different-concept distinction only holds once a pass is exhaustive.
