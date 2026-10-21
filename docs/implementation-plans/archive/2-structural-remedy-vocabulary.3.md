---
title: Structural Remedy Vocabulary
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add scope-out source token and per-source triage_reason messages (recommend-only,
    out of APPLY_ELIGIBLE_SOURCES)
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: low
  change_type: feature
  status: current
- id: 2
  title: Add the scope-out sub-arm to convergence's localized fork (max_severity ≥
    high + non-decreasing first→last trend), rendered prose-only
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
- id: 3
  title: Emit a code-grounded reconcile structural finding (steps already partially
    implemented → merge/re-ground) built on heuristic_already_done, deduped to one
    finding per cause via the reused granularity-* vocabulary
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
- id: 4
  title: Document the unified altitude × disposition remedy model (split/merge/scope-out/re-seed)
    and note the scope-out actuator ships in the follow-up plan
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - CAPABILITIES.md
  - DATA_CONTRACT.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
---
# Structural Remedy Vocabulary

## Overview

This plan unifies BACKLOG **#70** and **#67** by modeling the tool's structural remedies as **one split/merge axis** parameterized by altitude (step vs plan scope) and disposition (retained sibling vs carved-out forward-seed), and adds the *recommendation* for the one remedy the tool can detect but cannot yet recommend: **scope-out** (reduce-scope). It ships only the **advisory arms** — the `scope-out` source token + triage wiring, a `convergence` scope-out recommendation, a code-grounded `reconcile` structural finding, and the docs. Everything stays **detection + recommendation only** (Principle 1, *converge; mutate only when allowed*): detection is unconditional, mutation stays gated. The `plan-tool scope-out` **actuator** is a separate follow-up plan (`plan-seeds/scope-out-executor.md`), so this plan's scope-out recommendation renders **prose-only** (no runnable command) until that executor lands.

## Problem statement

Today the tool's structural remedies are three separate primitives — re-split a step (`granularity-split`), merge adjacent steps (`granularity-merge`), and re-seed the whole plan (the `convergence` diagnostic's structural fork). There is no **reduce-scope** (scope-out) remedy. This session a *spinning* region (the PPW `prune`/clone-lifecycle work — recurred as HIGH across rounds, then **backfired into data-loss HIGHs when patched**) had exactly one right remedy: carve the work out of scope and defer it. The tool had the *detection* signal (`convergence` detects recurrence + no-shrinkage across saved reports) but **no scope-out remedy in its vocabulary** — it only offers *rebuild* remedies (re-seed / re-split), never *reduce-scope*. Separately (#67), the structural-decomposition assessment belongs in **both** `completeness` (plan-centric, already covered via the granularity advisor + `convergence`) and `reconcile` (code-centric). `reconcile`'s strongest unique signal — a collection of steps **already partially implemented in the code**, visible only via `review.py:heuristic_already_done` — has no home as a finding.

## Architecture

**The two-parameter model (#70).** A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a step (→ two sibling steps) vs the plan's scope (→ a narrowed plan + a carved-out remainder); and (2) **disposition of the carved-off side** — retained as a sibling step (ordinary split) vs carved out into a forward-seed (**scope-out**). The space collapses to one axis: **scope-out = split at the plan-scope altitude with the carved side emitted as a forward-seed** (not a 4th primitive); **merge** = the inverse of split (fold a sibling back in / re-ground); **re-seed** = the limit (split everything / restart).

**Unified remedy vocabulary (emit through what already exists):**

| Remedy | Sources / executors |
|---|---|
| **split** (step altitude) | `granularity-split` (`granularity.py`) → `plan-tool split` → `escalate_to_split` (`launcher.py`) |
| **merge** | `granularity-merge` (`granularity.py`) → `plan-tool merge` |
| **re-seed** (plan limit) | the `convergence` structural fork → `create --from-existing` |
| **scope-out** (plan altitude + defer) | recommendation here (prose-only); **actuator in the `scope-out-executor` plan**. New `scope-out` source token, recommend-only. |

**Resolved decisions (pin these — they fix the prior audit's design errors):**

- **(3) Decidable scope-out trigger (no "data-loss-grade").** `convergence_diagnosis.py` carries only `_SEVERITY_RANK = {medium, high, critical}` — there is no "data-loss" grade; do not invent one. Scope-out is selected **inside the localized fork** (the single-step case `classify_fork` today always sends to re-split) by a falsifiable condition on data already on `RegionTrend`: the region spins (recurs ≥ `recurrence_min` + no-shrinkage), **and** `region.max_severity` is **≥ high**, **and** the **first→last** severity trend is **non-decreasing** (`RegionTrend` keeps only `first_severity`/`last_severity`/`max_severity` — no per-run sequence — so the check is first→last, *not* across-the-window). All three → recommend scope-out; otherwise the localized case stays re-split. Re-split and scope-out are the two sub-arms of the localized fork; structural re-seed is unchanged.
- **(4) Reconcile reuses the remedy *vocabulary*, not the granularity *detectors*.** `granularity.py` imports `plan_tool.review`, so `review.py` cannot import `granularity` (the cycle CLAUDE.md guards), and the granularity detectors are deterministic **plan-structure-only** — they never read code. The reconcile arm reuses **only the source-token string literals** (`granularity-split` / `granularity-merge`) and the `Recommendation` shape (duplicating the literal as `STRUCTURAL_SOURCES` already does). The **code signal** comes from reconcile's own `review.py:heuristic_already_done` (source `"heuristic"`).
- **(5) Dedup the code-grounded merge finding, and prefer *re-ground* over *merge*.** `reconcile` already surfaces "step already (partially) implemented" as a `source="heuristic"` `heuristic_already_done` hit. The new structural finding keys on the **same** signal, so emit **one** finding per step set (annotate the existing hit, or suppress the structural one when a heuristic hit covers that set). The remedy is usually **re-ground** (mark done / re-baseline), not `merge`: `heuristic_already_done` flags individual already-built steps that may not be adjacent/contiguous/PENDING, and `merge_steps` needs a contiguous all-PENDING run — so don't conflate "already built" with `granularity-merge`'s native "adjacent dependent steps fragmented" cause.
- **(6) Scope-out source token + bucket.** Introduce an explicit `scope-out` source token. Like every other structural-diagnostic source it stays **out of** `review.py:APPLY_ELIGIBLE_SOURCES` (recommend-only) and routes through the generic structural `triage_reason`. Because `triage_reason` today hardcodes a single "split it into type-pure steps" message, add **per-source** reason strings so merge/scope-out don't emit the inverse remedy. The existing `granularity-split` / `granularity-merge` / `structural-split` tokens and their exclusion are **unchanged**.
- **(7) Scope-out recommendation renders prose-only (no forward-ref command).** The `convergence` scope-out recommendation renders **prose-only** — it does not print a runnable `plan-tool scope-out …` line — because the executor ships in the follow-up plan. That plan flips `render_diagnosis` to render the runnable command once the executor exists. Resolved decisions **1 (destination = forward-seed)** and **2 (seed-first atomicity)** govern the *actuator* and are realized in `scope-out-executor`; noted here only so the recommendation prose describes the right disposition.

**Seams already in place (verify before extending):** `convergence_diagnosis.py` — `classify_fork` (the localized-vs-structural fork the scope-out sub-arm joins), `RegionTrend.max_severity` + `first_severity`/`last_severity` (the trigger data), `render_diagnosis` / `_split_command` / `_reseed_command` (where the prose-only recommendation renders); surfaced read-only by `plan-tool convergence` (exits 0, no Claude, no mutation). `granularity.py` — the `granularity-split` / `granularity-merge` source-token literals (reuse literals only, not detectors). `review.py` — `heuristic_already_done` (the code signal for #67), `APPLY_ELIGIBLE_SOURCES` / `triage_reason` (the token bucket + per-source message), `review_plan_full` / `render_review_prompt` (the reconcile audit #67 extends; note the recent `creates:` grounding fix — declared files = `files:` ∪ `creates:`). `escalate_to_split` (`launcher.py`) — the recommend-only/never-mutate model the scope-out executor mirrors; referenced here for vocabulary framing only.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — Official reference for building subcommands with add_subparsers/add_parser — consulted when wiring the read-only `plan-tool convergence`/`reconcile` CLI surfaces and their per-source argument handling.
- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — Defines frozen/eq dataclass semantics and field defaults — the reference for the immutable Recommendation/RegionTrend/EscalateResult shapes (first_severity/last_severity/max_severity) the new scope-out trigger reads.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — Primary API for dump/load and custom JSONEncoder.default — needed to read and emit the persisted completeness/reconcile report sidecars and telemetry JSONL the convergence diagnostic consumes.
- [Python Frontmatter — documentation](https://python-frontmatter.readthedocs.io/) — Library guide for parsing/serializing YAML frontmatter in markdown — relevant because plan files store their machine-readable source of truth as frontmatter that the structural-remedy findings annotate.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Primary PyYAML reference covering safe_load/SafeLoader semantics — the safe parsing contract for plan-file frontmatter that detection logic round-trips without arbitrary code execution.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The `plan-tool scope-out` executor / any plan mutation** — the actuator is the separate `scope-out-executor` plan; this plan only detects + recommends.
- A **new split/merge algorithm** — reuse the existing executors.
- **Auto-mutating structure unattended** — the arms here only recommend; the default path spends no Claude.
- A **programmatic BACKLOG.md writer** or an **in-plan `DEFERRED`** disposition — the scope-out destination is a forward-seed (settled; realized in the executor plan), not BACKLOG, not a parked in-plan step.
- Removing the BUG_BACKLOG reconcile-lane bookkeeping noise — separate fix.

## Risks

- **False "already implemented" calls** on superficial symbol overlap — reuse `heuristic_already_done` carefully; keep it advisory; dedup against the existing hit; prefer re-ground over merge (decision 5).
- **Vocabulary churn** — the new `scope-out` token + per-source triage messages must not break the existing `granularity-split` / `granularity-merge` / `structural-split` routing tokens or their `APPLY_ELIGIBLE_SOURCES` exclusion (decision 6).
- **Forward-ref** — the recommendation must stay prose-only until the executor plan ships (decision 7); rendering a runnable command early points at a missing command.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence` emits a **prose-only** scope-out / defer recommendation on a spinning single-step region whose `max_severity ≥ high` and whose first→last severity trend is non-decreasing — a sub-arm of the localized fork, distinct from re-split and the structural re-seed. Read-only, advisory, exits 0. No invented "data-loss" severity grade; no runnable command rendered.
- `reconcile` surfaces a **code-grounded** structural finding when the code implies a merge/re-ground (headline: steps already partially implemented), built on `heuristic_already_done`, emitted through the reused `granularity-*` vocabulary, **deduped** against the existing hit (one finding per cause) and framed as re-ground where merge can't run, advisory and never flipping the exit code.
- The four remedies read as **one altitude × disposition model** in the docs; the scope-out actuator is documented as shipping in the follow-up plan.
- The new `scope-out` token stays **out of** `APPLY_ELIGIBLE_SOURCES`; `triage_reason` emits a correct per-source message for merge/scope-out (not the inverse "split" advice); existing structural routing tokens and their exclusion are unchanged; the granularity advisor and `escalate_to_split` behave as before.

## Deferred

- **Flipping `render_diagnosis` to render a runnable `plan-tool scope-out …` command** — deferred to the follow-up `scope-out-executor` plan; until that executor lands the recommendation stays prose-only (decision 7).
- **Resolved decisions 1 (destination = forward-seed) and 2 (seed-first atomicity)** — govern the actuator and are realized in `scope-out-executor`; noted here only so the recommendation prose describes the right disposition.
