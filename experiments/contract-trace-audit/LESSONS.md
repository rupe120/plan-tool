# Spike: contract-trace / path-enumeration audit (BACKLOG #66)

**Question.** Can the *control-flow / contract-coverage* findings the conceptual
sampler catches only stochastically be caught **deterministically** by walking a
grid over the plan's declared contracts? Use the
`escalate-structural-findings-to-split` plan's three known findings as the
fixture.

**Run.** `uv run python experiments/contract-trace-audit/spike.py`

## What the spike validated (the DOWNSTREAM half)

Given a hand-encoded contract model (outcome enum, per-outcome field discipline,
the two callers + which outcomes each surfaces, the `step_id ∈ {None, concrete}`
input dimension, and the prompt verdict-injection contract), **one deterministic
grid-walk surfaces all three known finding classes in a single pass**, as four
precise cells:

| # | Finding class (how the sampler reported it) | Grid-walk cell(s) |
|---|---|---|
| 1 | step8 plan-level KeyError | `step8 × step_id=None` (no guard) |
| 2 | step7 "silently drops the unsafe outcome" | `step7 × unsafe` **and** `step7 × proposal-unusable` |
| 3 | step3 gate leak | prompt verdict-literal static in template |

And it **traces clean** on the post-fix contract (this session's fixes), so it's
a real regression gate, not a one-way detector.

Two wins over the conceptual sampler for this finding class:

- **No variance.** The sampler found these three across *three separate audit
  runs* at varying severity (an 11-sample run missed the step3 HIGH a later
  3-sample run caught — the exact variance #59/#60 sample-count tuning fights).
  The grid-walk covers every cell once.
- **More precise.** It splits the audit's single prose finding "step7 drops the
  unsafe outcome" into the two real cells (`unsafe` + `proposal-unusable`) — the
  exact two branches the fix had to add.

## What it did NOT prove (the UPSTREAM half — the real risk)

The contract model here is **hand-encoded** from the plan. The hard, unproven
part of #66 is **extracting that model from plan/detail prose** without a full
executable mock and without manufacturing mock-artifact findings. That extraction
is where #66's risk lives and is deliberately out of this spike's scope.

## Meta-finding (worth keeping)

The spike's **own first iteration mis-modeled the contract** — it keyed coverage
on "does the caller read the field populated on this outcome," which (a) false-
flagged `applied` (handled via step 7's break+re-author, not a field read) and
(b) couldn't see `proposal-unusable` at all (it carries no result field). The
grid-walk's precision *forced* a correct model (explicit "outcomes surfaced" per
caller). That cuts both ways: a contract-trace is only as good as its model, so
the extraction step must itself be validated — which is exactly why #66 is
**spike-first / plan-tool**, not a direct one-shot.

## Verdict / recommendation

The downstream value is real and strong for control-flow-contract-heavy plans:
deterministic, complete, more precise than sampling, and a clean regression gate.
**Greenlight the full #66 — but the build's center of gravity is the extraction
step**, which needs its own validation (does an LLM-extracted contract model, or
a structured contract schema authored into the plan, reproduce these four cells
without noise on a plan it wasn't tuned for?). Recommend the full build go
through the create→detail→audit pipeline (its filed Approach), with this spike's
four cells as an acceptance fixture and a second, *different* plan as a
held-out test that the extraction generalizes.
