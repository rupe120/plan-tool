> **Auto-archived**: this plan was swept on 2026-06-24 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Structural Remedy Vocabulary
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add prose-only scope-out fork-arm to the localized convergence fork
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/structural-remedy-vocabulary/01-prose-only-scope-out-fork-arm-localized.md
  status: done
- id: 2
  title: Emit a code-grounded re-ground finding (granularity-merge) on a >=2-distinct-step
    already-built set, scoped to the reconcile lane
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/structural-remedy-vocabulary/02-emit-code-grounded-re-ground-finding.md
  status: done
- id: 3
  title: 'Document the four remedies as one altitude x disposition model and trim
    BACKLOG #70/#67 to the advisory/actuator split'
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/structural-remedy-vocabulary/03-document-four-remedies-one-altitude.md
  status: done
---
# Structural Remedy Vocabulary

## Overview

Ships the **advisory arms** of a unified structural-remedy vocabulary, joining BACKLOG **#70** (model the structural remedies as one split/merge axis + add **scope-out**) and **#67** (give `reconcile` a **code-grounded** structural-decomposition check), which share one remedy vocabulary. It adds (1) a `convergence` **scope-out / defer recommendation** surfaced as a `ForkRecommendation` arm in `convergence_diagnosis.py`, rendered **prose-only**, (2) a code-grounded **re-ground finding** in `reconcile` built on `review.py:heuristic_already_done`, and (3) docs framing the four remedies as one model. Everything is **detection + recommendation only**: detection is unconditional, mutation stays gated. The **actuator** — the gated `plan-tool scope-out` executor — is the separate follow-up plan `plan-seeds/scope-out-executor.md`, which flips the prose-only recommendation into a runnable command.

## Problem statement

The tool can detect a *spinning* region (`convergence` sees recurrence + no-shrinkage across saved reports) but has **no scope-out remedy in its vocabulary** — only *rebuild* remedies (re-seed / re-split). The motivating evidence: a spinning region (the PPW `prune`/clone-lifecycle work, recurred as HIGH across rounds, then **backfired into data-loss HIGHs when patched**) had exactly one right remedy — **carve the work out of scope and defer it** — which the tool could not recommend. Separately, `reconcile` judges the plan **code-centrically**, and its strongest unique signal — a collection of steps **already partially implemented in the code → merge / re-ground**, visible only via `review.py:heuristic_already_done` — has no advisory home. This plan adds the recommendations; the executor plan adds the action.

## Architecture

**Unified two-parameter model (#70).** A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a **step** (→ two sibling steps) vs the **plan's scope** (→ a narrowed plan + a carved-out remainder) — and (2) **disposition of the carved-off side** — retained as a sibling step (ordinary split) vs carved out into a forward-seed (**scope-out**). The space collapses to one axis: scope-out = split at the plan-scope altitude with the carved side emitted as a forward-seed (*not a 4th primitive*); merge = the inverse of split; re-seed = the limit (split everything / restart).

**Altitude — triggered local, acts at plan scope.** scope-out is *triggered* inside the **localized (step-altitude) fork** (`classify_fork → FORK_LOCALIZED`, one resolved step) yet *acts* at plan-scope altitude (it carves that step out of the plan). The docs must state both halves rather than labeling it purely "plan-scope altitude." (`scope-out-altitude`)

**scope-out is a fork-arm + executor, NOT a `review.py` finding source.** Unlike `granularity-split` / `granularity-merge` (emitted as `review.Recommendation` objects by `granularity.py`) and `structural-split` (a `review.py` source), scope-out surfaces as a **`ForkRecommendation` arm in `convergence_diagnosis.py`** (prose, not a `Recommendation`) and, in the follow-up plan, as a CLI executor. Nothing produces a `review.Recommendation` with `source="scope-out"`, so **this plan introduces no such token** — it would be dead vocabulary with no producer.

**Resolved decisions (pin these):**
1. **Decidable scope-out trigger over the localized fork's region *set*.** `convergence_diagnosis.py` carries only `_SEVERITY_RANK = {medium, high, critical}` — no "data-loss" grade is invented. The `FORK_LOCALIZED` fork can resolve several `RegionTrend`s onto one over-packed step, so the trigger is defined over the set: **scope-out fires when *any* co-located region on the resolved step clears both bars — `region.last_severity ≥ high` AND a non-decreasing `first_severity → last_severity` trend** (`RegionTrend` keeps only first/last/max severity). Bar 1 keys on the region's **current** severity (`last_severity`), not the peak it ever reached (`max_severity`): a region that spiked to high once and recovered to medium has `last_severity = medium` and does **not** fire, so the trigger matches "stays severe" rather than "was ever severe." One stubborn severe-and-not-improving region suffices; otherwise the localized case stays re-split. Re-split and scope-out are the two sub-arms of the localized fork; structural re-seed is unchanged.
2. **Reconcile reuses the remedy *vocabulary literal*, not the granularity *detectors* — and the literal is `granularity-merge`, NOT `granularity-split`.** `granularity.py` imports `plan_tool.review`, so `review.py` cannot import `granularity` (the guarded cycle), and the granularity detectors are plan-structure-only. The reconcile arm reuses only the **source-token string literal** + the `Recommendation` shape. Pin `granularity-merge`: it is *not* in `review.py:STRUCTURAL_SOURCES` (`{"granularity-split", "structural-split"}`), so `is_structural()` is False and the finding takes the **non-apply-eligible `triage_reason` branch** (merge/re-ground-aware in step 2, decision 3(c)) rather than the split bridge. `granularity-split` would make `is_structural()` True and route the apply walk through `_dispatch_structural_escalation → escalate_to_split` with a "split this step" message — the inverse of a re-baseline. The **code signal** comes from `review.py:heuristic_already_done` (source `"heuristic"`).
3. **The reconcile structural finding fires on a ≥2-DISTINCT-STEP set (re-ground), scoped to the reconcile lane, carrying its own remedy text.** `reconcile` already emits a per-step `source="heuristic"` recommendation (`review.py:_heuristic_recommendation`) for each already-built step. The new finding has a distinct trigger: it fires only when **≥2 distinct `step_id`s** are flagged already-built, emitted once for the set. Three specifics: (a) **Count distinct step ids, not raw hits** — `heuristic_already_done` appends one `HeuristicHit` per (step, file), so the trigger is `len({hit.step_id}) ≥ 2` (`step-dedup-count`); (b) **Gate the emit to the reconcile lane** — `review.py:extract_recommendations` is shared, but `review_plan_full` is the reconcile-only surface; the completeness/run-gate paths reach `extract_recommendations` via `collect_deterministic_findings` (which passes `heuristic_hits=[]` and the default `reconcile_lane=False`), so condition the emit on `review_plan_full` setting `reconcile_lane=True` (`reconcile-finding-scope`); (c) **Carry the re-ground remedy in the finding's own message *and* make `triage_reason` merge/re-ground-aware without identifying a producer from the shared source token** — `triage_reason`'s non-apply-eligible branch does **not** stay silent: for a `granularity-merge` source it emits a concrete *wrong* remedy (`"… resolve directly (fix the path / run plan-tool detail / author lessons)"`), so the skip rollup actively misdirects operators away from merge/re-baseline decisions. So the finding self-describes "mark done / re-baseline this set" in its `body`/`suggested_action` (`reconcile-triage-message`) **and** step 2 adds a `granularity-merge` arm to `triage_reason` whose wording is producer-neutral: it covers both structure-grounded merge findings from `granularity.py` and reconcile's code-grounded re-ground finding, telling the operator to inspect the finding and either merge a contiguous all-`PENDING` run or re-baseline / mark done / re-decompose an already-built set. The branch keys on `rec.source` only and leaves `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `is_structural` / `is_apply_eligible` unchanged; because the shared source cannot distinguish producers, the skip text must not say "code already implements this set" unconditionally. A single already-built step stays the existing plain heuristic hit. Remedy is **re-ground**, not blindly `merge` (`heuristic_already_done` may flag non-adjacent/non-PENDING steps, while `merge_steps` needs a contiguous all-PENDING run). The finding **intentionally does not evaluate** the contiguity/all-`PENDING` precondition — `_reground_already_built_recommendation` receives only the hits, not the `Plan`, so it cannot compute whether the flagged steps form the run `merge_steps` requires. The `merge`-if-contiguous branch is therefore **operator-verified guidance, not a computed claim**: the finding names `merge` as a conditional the operator confirms by hand and leaves merge-vs-re-decompose to the operator rather than pre-resolving it. (d) **Visibility is `--include-info`-gated on the default surface (accepted limitation).** The finding is `severity="info"`, so on the default `reconcile-plan` walk (`skip_info=True`) `assemble_report` renders only the `Findings:` banner tally for this plan-wide rec; its re-ground remedy text surfaces only under `--include-info`. The per-step `heuristic` hits it derives from still render as `hint:` lines in each step's body, so the default operator is not left blind — but the aggregate re-ground remedy text is reachable only via `--include-info`, and this plan accepts that rather than un-deferring a report-body section (`reground-info-visibility`).
4. **Scope-out recommendation renders prose-only (no forward-ref command).** `render_diagnosis` prints no runnable `plan-tool scope-out …` line, because the executor ships in the follow-up plan, which flips it.

**Seams already in place (verify before extending):**
- `convergence_diagnosis.py` — `classify_fork`, `RegionTrend.max_severity` + `first_severity` / `last_severity`, `render_diagnosis` / `_split_command` / `_reseed_command`; surfaced read-only by `plan-tool convergence` (exits 0, no Claude, no mutation).
- `granularity.py` — the `granularity-split` / `granularity-merge` source-token literals (reuse literals only, not detectors); kept out of `APPLY_ELIGIBLE_SOURCES`.
- `review.py` — `heuristic_already_done` + `_heuristic_recommendation`; `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `triage_reason` (`granularity-merge` takes the non-apply-eligible branch, made merge/re-ground-aware with producer-neutral wording in step 2); `review_plan_full` / `render_review_prompt` (recent `creates:` grounding fix — declared files = `files:` ∪ `creates:`).

**Unified remedy vocabulary (conceptual, for the docs):** split (step → two siblings) via `granularity-split` → `plan-tool split` / `escalate_to_split`; merge / re-ground (fold sibling back / re-baseline) via `granularity-merge` + the reconcile already-built signal → `plan-tool merge`; scope-out (plan scope → narrow + carved side to a forward-seed) via the `convergence` fork-arm (prose here) + the executor (follow-up plan); re-seed (split everything / restart) via the `convergence` structural fork → `create --from-existing`.

## References

- `BACKLOG.md` #70 (model the structural remedies as one split/merge axis + add scope-out) and #67 (give `reconcile` a code-grounded structural-decomposition check) — the two backlog items this plan ships the advisory arms of; trimmed to the advisory/actuator split in step 3.
- `plan-seeds/scope-out-executor.md` — the follow-up executor plan that flips the prose-only scope-out recommendation into a runnable `plan-tool scope-out` command; this plan's out-of-scope actuator.
- `plan_tool/convergence_diagnosis.py` — `classify_fork`, `RegionTrend` (first/last/max severity), `render_diagnosis` / `_split_command` / `_reseed_command`; where step 1 adds the localized fork's scope-out arm.
- `plan_tool/review.py` — `heuristic_already_done` / `_heuristic_recommendation` (the code signal), `extract_recommendations`, `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `triage_reason`; where step 2 emits the reconcile-lane re-ground finding.
- `plan_tool/granularity.py` — the `granularity-split` / `granularity-merge` source-token literals reused (literals only, not the detectors) and their exclusion from `APPLY_ELIGIBLE_SOURCES`.
- `MISSION.md` — the *always surface the more-correct plan* grounding principle (detection unconditional, mutation gated) this plan obeys.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The `plan-tool scope-out` executor / any plan mutation** — handled by the separate `scope-out-executor` plan (`plan-seeds/scope-out-executor.md`).
- **A `review.py` `scope-out` source token** — dropped; no producer exists (scope-out is a fork-arm + executor), so adding one would be dead vocabulary.
- **A new split/merge algorithm** — reuse the existing executors.
- **A programmatic BACKLOG.md writer or an in-plan `DEFERRED` disposition** — the scope-out destination is a forward-seed (settled; realized in the executor plan).
- **Removing the BUG_BACKLOG reconcile-lane bookkeeping noise** — a separate fix.

## Risks

- **False "already implemented" calls** on superficial symbol overlap — reuse `heuristic_already_done` carefully and keep it advisory; the ≥2-step trigger + the re-ground framing reduce noise (decision 3). Severity: noise/false-positive finding; mitigated, not eliminated.
- **Forward-ref** — the scope-out recommendation must stay prose-only until the executor plan ships (decision 4); rendering a runnable command early would point at a command that does not exist.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence` emits a **prose-only** scope-out / defer recommendation when, for the single step the localized fork resolves to, **any** co-located region has `last_severity ≥ high` and a non-decreasing first→last trend — distinct from re-split and the structural re-seed. Read-only, advisory, exits 0. No invented severity grade; no runnable command rendered.
- `reconcile` surfaces a **code-grounded re-ground finding** when **≥2 distinct step ids** are flagged already-built — **scoped to the reconcile lane** (not the shared completeness/review/run-gate paths), sourced as **`granularity-merge`** (so it takes the non-apply-eligible triage branch — made merge/re-ground-aware with producer-neutral skip text, not the split bridge), and **carrying its own re-ground/re-baseline remedy text**. Distinct from the existing per-step heuristic hit; advisory, never flips the exit code. Because the finding is `severity="info"`, its aggregate remedy text is `--include-info`-gated on the default `reconcile-plan` walk (`skip_info=True` hides it; the per-step `heuristic` `hint:` lines it derives from still render) — an accepted limitation, not an un-deferred report-body section.
- The four remedies read as **one altitude × disposition model** in the docs, with scope-out documented as a fork-arm + executor (not a review source) and its actuator noted as shipping in the follow-up plan.
- No `review.py` `scope-out` source token is introduced; existing structural routing tokens and their `APPLY_ELIGIBLE_SOURCES` exclusion are unchanged; the granularity advisor and `escalate_to_split` behave as before.

## Deferred

- **Flipping the prose-only scope-out recommendation to a runnable `plan-tool scope-out …` line in `render_diagnosis`** — held prose-only until the `scope-out-executor` follow-up plan ships the executor and flips it (decision 4).
- **An automatic bridge from the reconcile re-ground finding to an actuating command** — kept recommend-only (operator hand-runs `merge` / re-plans), mirroring `granularity-merge`; a wired actuator may return later.
- **Recording which convergence fork arm fired (scope-out vs re-split vs structural) in telemetry** — `cli/convergence_cmd.py:record_convergence` captures only the headline `verdict`, not the fork arm, so the `telemetry.py` (#72) surface gets no signal to tune `_region_triggers_scope_out`'s bars (`last_severity ≥ high` + non-decreasing first→last). This is a pre-existing limitation (the localized/structural fork is also unrecorded) the new threshold inherits, not one this plan introduces; recording the fork arm to support threshold tuning is deferred.
