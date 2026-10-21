---
title: Structural Remedy Vocabulary
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a scope-out sub-arm to the localized convergence fork, rendered prose-only
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Add a code-grounded ≥2-step re-ground finding to reconcile via extract_recommendations
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
- id: 3
  title: 'Document the four remedies as one altitude × disposition model and trim
    BACKLOG #70/#67'
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
---
# Structural Remedy Vocabulary

## Overview

Ships the **advisory arms** of a unified structural-remedy vocabulary, planning BACKLOG **#70** (model the structural remedies as one split/merge axis + add **scope-out**) and **#67** (give `reconcile` a code-grounded structural-decomposition check) together because they share one remedy vocabulary. It adds two recommend-only surfaces — a **prose-only scope-out recommendation** as a `ForkRecommendation` arm in `convergence_diagnosis.py`, and a **code-grounded re-ground finding** in `reconcile` built on `review.py:heuristic_already_done` — plus docs framing the four remedies as one model. Everything is detection + recommendation only: detection is unconditional, mutation stays gated, and the scope-out recommendation renders prose-only (no runnable `plan-tool scope-out` command) until the separate `plan-seeds/scope-out-executor.md` plan lands. Exit codes never flip.

## Problem statement

The tool has three separate structural primitives — **re-split** a step (`granularity-split`), **merge** adjacent steps (`granularity-merge`), and **re-seed** the whole plan (the `convergence` structural fork) — but no vocabulary for the one remedy it can detect the need for yet cannot recommend: **reduce-scope** (scope-out). A *spinning* region (the PPW `prune`/clone-lifecycle work — recurred as HIGH across rounds, then backfired into data-loss HIGHs when patched) had exactly one right remedy: carve the work out of scope and defer it. `convergence` detected the spin (recurrence + no-shrinkage across saved reports) but offered only *rebuild* remedies (re-seed / re-split). Separately (#67), `reconcile` judges plans code-centrically and its strongest unique signal — a collection of steps already partially implemented in code → merge / re-ground, visible only via `review.py:heuristic_already_done` — has no home as an advisory finding.

## Architecture

**Two-parameter model (#70).** A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a **step** (→ two sibling steps) vs the **plan's scope** (→ a narrowed plan + carved-out remainder) — and (2) **disposition of the carved-off side** — retained as a sibling step (ordinary split) vs carved out into a forward-seed (**scope-out**). The space collapses to one axis: **scope-out = split at the plan-scope altitude with the carved side emitted as a forward-seed** (not a 4th primitive); **merge** = the inverse of split (fold a sibling back in / re-ground); **re-seed** = the limit (split everything / restart).

**scope-out is a fork-arm, not a `review.py` source.** Unlike `granularity-split` / `granularity-merge` (emitted as `review.Recommendation` objects by `granularity.py`) and `structural-split` (a `review.py` source), scope-out surfaces as a **`ForkRecommendation` arm in `convergence_diagnosis.py`** (prose, not a `Recommendation`) and, in the follow-up plan, as a CLI executor. Nothing produces a `review.Recommendation` with `source="scope-out"`, so this plan introduces **no such token** (it would be dead vocabulary with no producer); the old "add a scope-out source token + per-source triage message" step is dropped.

**Resolved decisions (pin these — they fix prior audits' design errors):**
1. **Decidable scope-out trigger over the localized fork's region *set*.** `convergence_diagnosis.py` carries only `_SEVERITY_RANK = {medium, high, critical}` — no "data-loss" grade is invented. Scope-out is selected **inside the localized fork** (`classify_fork → FORK_LOCALIZED`), which can resolve several `RegionTrend`s onto one over-packed step. The trigger fires when **any** co-located region on the resolved step clears both bars — `region.max_severity ≥ high` **AND** a non-decreasing `first_severity → last_severity` trend (`RegionTrend` keeps only first/last/max severity, no per-run sequence, so the check is first→last). One stubborn severe-and-not-improving region is enough; otherwise the localized case stays re-split. Re-split and scope-out are the two sub-arms of the localized fork; structural re-seed is unchanged.
2. **Reconcile reuses the remedy *vocabulary literals*, not the granularity *detectors*.** `granularity.py` imports `plan_tool.review`, so `review.py` cannot import `granularity` (the guarded cycle), and the granularity detectors are plan-structure-only (never read code). The reconcile arm reuses **only the source-token string literals** (`granularity-split` / `granularity-merge`) and the `Recommendation` shape (duplicating the literal as `STRUCTURAL_SOURCES` already does). The code signal comes from `review.py:heuristic_already_done` (source `"heuristic"`).
3. **The reconcile structural finding fires on a MULTI-STEP set (re-ground), distinct from the existing per-step hit.** `reconcile` already emits a per-step `source="heuristic"` recommendation (`review.py:_heuristic_recommendation`) per already-built step. To avoid the prior `reconcile-already-done-dedup` contradiction, the new structural finding has a distinct trigger: it fires only when **≥2 steps** are flagged already-built (a *collection* → the re-ground / re-baseline signal), emitted **once for the set** through the reused `granularity-*` vocabulary. A single already-built step stays the existing plain heuristic hit. The remedy framing is **re-ground** (mark done / re-baseline), **not** blindly `merge`: `heuristic_already_done` flags steps that may not be adjacent/contiguous/PENDING, while `merge_steps` needs a contiguous all-PENDING run.
4. **Scope-out recommendation renders prose-only.** `render_diagnosis` prints no runnable `plan-tool scope-out …` line because the executor ships in the follow-up plan, which flips it. No recommendation points at a command that does not yet exist.

**Seams already in place (verify before extending):** `convergence_diagnosis.py` — `classify_fork`, `RegionTrend.max_severity` / `first_severity` / `last_severity`, `render_diagnosis` / `_split_command` / `_reseed_command`; surfaced read-only by `plan-tool convergence` (exits 0, no Claude, no mutation). `granularity.py` — the `granularity-split` / `granularity-merge` source-token literals (reuse literals only, not detectors), kept out of `APPLY_ELIGIBLE_SOURCES`. `review.py` — `heuristic_already_done` + `_heuristic_recommendation`; `STRUCTURAL_SOURCES` / `APPLY_ELIGIBLE_SOURCES` / `triage_reason` (note `granularity-merge` already routes to the neutral generic branch); `review_plan_full` / `render_review_prompt` (the reconcile audit #67 extends; recent `creates:` grounding fix — declared files = `files:` ∪ `creates:`).

## References

- [dataclasses — Data Classes — Python 3 documentation](https://docs.python.org/3/library/dataclasses.html) — Official reference for `@dataclass`, `frozen=True`, and `field()` — consulted when adding the plan's frozen recommendation/trend structures (e.g. the `ForkRecommendation` arm and `RegionTrend` fields) and their hashing/immutability semantics.
- [typing — Support for type hints — Python 3 documentation](https://docs.python.org/3/library/typing.html) — Standard-library typing reference covering `Literal` and other hints, relevant for typing the reused `granularity-split`/`granularity-merge` source-token string literals and the `_SEVERITY_RANK` annotations.
- [PEP 586 – Literal Types](https://peps.python.org/pep-0586/) — Primary specification for `typing.Literal`, useful when constraining source-token and severity values to a fixed set of string literals across the convergence/reconcile vocabulary.
- [argparse — Parser for command-line options — Python 3 documentation](https://docs.python.org/3/library/argparse.html) — Official argparse guide, consulted because the read-only `plan-tool convergence` and `reconcile` surfaces extending this plan are wired through the project's argparse parser.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **The `plan-tool scope-out` executor / any plan mutation** — lives in the separate `scope-out-executor` plan.
- **A `review.py` `scope-out` source token** — dropped (no producer; scope-out is a fork-arm + executor).
- **A new split/merge algorithm** — reuse the existing executors.
- **A programmatic BACKLOG.md writer** or an **in-plan `DEFERRED` disposition** — the scope-out destination is a forward-seed (settled; realized in the executor plan).
- **Removing the BUG_BACKLOG reconcile-lane bookkeeping noise** — separate fix.

## Risks

- **False "already implemented" calls** on superficial symbol overlap — reuse `heuristic_already_done` carefully, keep it advisory; the ≥2-step trigger + re-ground framing reduce noise (decision 3).
- **Forward-ref** — the scope-out recommendation must stay prose-only until the executor plan ships (decision 4); a recommendation pointing at a non-existent `plan-tool scope-out` command would mislead operators.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence` emits a **prose-only** scope-out / defer recommendation when, for the single step the localized fork resolves to, **any** co-located region has `max_severity ≥ high` and a non-decreasing first→last trend — distinct from re-split and the structural re-seed. Read-only, advisory, exits 0. No invented severity grade; no runnable command rendered.
- `reconcile` surfaces a **code-grounded re-ground finding** when **≥2 steps** are flagged already-built (one finding for the set, through the reused `granularity-*` vocabulary), distinct from the existing per-step heuristic hit; advisory, never flips the exit code.
- The four remedies read as **one altitude × disposition model** in the docs, with scope-out documented as a fork-arm + executor (not a review source) and its actuator noted as shipping in the follow-up plan.
- No `review.py` `scope-out` source token is introduced; existing structural routing tokens and their `APPLY_ELIGIBLE_SOURCES` exclusion are unchanged; the granularity advisor and `escalate_to_split` behave as before.

## Deferred

- **Flipping the scope-out recommendation from prose-only to a runnable command** — the prose-only rendering is intentionally temporary; the follow-up `scope-out-executor` plan ships the actuator and flips it (decision 4). Returns with that plan, so deferred rather than excluded.
- **Actuating the reconcile re-ground finding** — it stays recommend-only, mirroring `granularity-merge`; wiring it to a re-baseline/merge command is postponed until the re-ground remedy has a settled executor.
- **The create-side convergence loop routing through this vocabulary** — `create.py` does not yet surface the scope-out fork-arm (trigger deferred, as with `escalate_to_split`); folding it in waits on a separate change.
