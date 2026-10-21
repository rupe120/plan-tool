# Plan seed: unified structural-remedy vocabulary + a code-grounded reconcile structural check (the *advisory* arms)

Unifies BACKLOG **#70** (model the structural remedies as one split/merge axis +
add **scope-out**) and **#67** (give `reconcile` a **code-grounded**
structural-decomposition check) — they share one remedy vocabulary, so plan them
together.

> **Scope: detection + recommendation only.** This plan ships the *advisory* arms —
> the `convergence` **scope-out recommendation**, the `reconcile` code-grounded
> **finding**, and the docs that frame the unified vocabulary. The **actuator** —
> the gated `plan-tool scope-out` executor — is the separate follow-up plan
> `plan-seeds/scope-out-executor.md`. The scope-out recommendation renders
> **prose-only** (no runnable `plan-tool scope-out` command) until that executor
> lands; the executor plan flips it.

## Guiding principle

Model the tool's three separate structural primitives — **re-split** a step
(`granularity-split`), **merge** adjacent steps (`granularity-merge`), **re-seed**
the whole plan (the `convergence` structural fork) — as **one split/merge axis
parameterized by altitude × disposition**, and add the *recommendation* for the one
remedy the tool can detect the need for but cannot yet recommend: **reduce-scope**
(scope-out). Everything here is **advisory / recommend-only** — detection is
unconditional; mutation stays gated + confirmed (Principle 1, *converge; mutate
only when allowed*). The mutation itself lives in the follow-up executor plan.

## The two-parameter model (#70)

A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a
**step** (→ two sibling steps) vs the **plan's scope** (→ a narrowed plan + a
carved-out remainder) — and (2) **disposition of the carved-off side** — **retained
as a sibling step** (ordinary split) vs **carved out of the plan into a
forward-seed** (**scope-out**). The space collapses to one axis:

- **scope-out = split at the plan-scope altitude with the carved side emitted as a
  forward-seed** — *not a 4th primitive*.
- **merge** = the inverse of split (fold a sibling back in / re-ground).
- **re-seed** = the limit (split everything / restart).

**Altitude: triggered local, acts at plan scope.** scope-out is *triggered* inside
the **localized (step-altitude) fork** (`classify_fork → FORK_LOCALIZED`, one
resolved step) — a localized/single-step spin is the entry condition — yet it
*acts* at **plan-scope altitude** (it carves that step out of the plan). The docs
must state both halves rather than labeling scope-out purely "plan-scope altitude,"
which would contradict its step-altitude trigger. (`scope-out-altitude`)

### scope-out is a fork-arm + an executor — NOT a review.py finding source

A subtle but load-bearing correction (the prior audit's `scope-out-token-orphan`
HIGH): unlike `granularity-split` / `granularity-merge` (emitted as
`review.Recommendation` objects by `granularity.py`) and `structural-split` (a
`review.py` source), **scope-out is not a `review.Recommendation` source at all**.
It surfaces as a **`ForkRecommendation` arm in `convergence_diagnosis.py`** (prose,
not a `Recommendation`) and, in the follow-up plan, as a **CLI executor**. Nothing
in either plan ever produces a `review.Recommendation` with `source="scope-out"`,
so **this plan introduces no such token** — adding one would be dead vocabulary with
no producer. The unified model is a *conceptual* doc framing, not a new review
source. (This is why the old "add a scope-out source token + per-source triage
message" step is dropped.)

### Why scope-out is the missing remedy (motivating evidence)

A *spinning* region (the PPW `prune`/clone-lifecycle work — recurred as HIGH across
rounds, then **backfired into data-loss HIGHs when patched**) had exactly one right
remedy: **carve the work out of scope and defer it**. The tool detected the spin
(`convergence` sees recurrence + no-shrinkage across saved reports) but had **no
scope-out remedy in its vocabulary** — only *rebuild* remedies (re-seed / re-split).
This plan adds the **recommendation**; the executor plan adds the action.

## The code-grounded structural check in reconcile (#67)

`reconcile` judges the plan **code-centrically**; its strongest unique signal is a
collection of steps **already partially implemented in the code → merge /
re-ground**, visible only via `review.py:heuristic_already_done`. This plan gives
that signal a home as an advisory, recommend-only finding.

## Resolved decisions (pin these — they fix the prior audits' design errors)

1. **Decidable scope-out trigger over the localized fork's region *set*.**
   `convergence_diagnosis.py` carries only `_SEVERITY_RANK = {medium, high,
   critical}` — no "data-loss" grade; none is invented. Scope-out is selected
   **inside the localized fork** (`classify_fork → FORK_LOCALIZED`). That fork can
   resolve **several `RegionTrend`s onto one over-packed step** (the docstring's
   "several regions all on step N" case), so the trigger is defined over the set:
   **scope-out fires when *any* co-located region on the resolved step clears both
   bars — `region.max_severity ≥ high` AND a non-decreasing `first_severity →
   last_severity` trend** (`RegionTrend` keeps only first/last/max severity — no
   per-run sequence — so the check is first→last, not across-the-window). One
   stubborn severe-and-not-improving region is enough; otherwise the localized case
   stays re-split. Re-split and scope-out are the two sub-arms of the localized
   fork; structural re-seed is unchanged.
2. **Reconcile reuses the remedy *vocabulary literal*, not the granularity
   *detectors* — and the literal is `granularity-merge`, NOT `granularity-split`.**
   `granularity.py` imports `plan_tool.review`, so `review.py` cannot import
   `granularity` (the cycle CLAUDE.md guards), and the granularity detectors are
   plan-structure-only — they never read code. The reconcile arm reuses **only the
   source-token string literal** + the `Recommendation` shape. **Pin
   `granularity-merge`**: it is *not* in `review.py:STRUCTURAL_SOURCES`
   (`{"granularity-split", "structural-split"}`), so `is_structural()` is False and
   the finding reaches the **neutral generic `triage_reason` branch** an advisory
   re-ground wants. `granularity-split` would make `is_structural()` True and route
   the apply walk through `_dispatch_structural_escalation → escalate_to_split` with
   a "split this step / run `plan-tool split`" message — the **inverse** of a
   re-baseline. (Do not be misled by decision 3's "re-ground not merge" framing into
   picking `granularity-split`; the *routing*, not the verb, dictates the literal.)
   The **code signal** comes from `review.py:heuristic_already_done` (source
   `"heuristic"`).
3. **The reconcile structural finding fires on a ≥2-DISTINCT-STEP set (re-ground),
   scoped to the reconcile lane, carrying its own remedy text.** `reconcile` already
   emits a per-step `source="heuristic"` `heuristic_already_done` recommendation
   (`review.py:_heuristic_recommendation`) for each already-built step. The new
   finding has a **distinct trigger** (avoiding the prior `reconcile-already-done-dedup`
   contradiction): it fires only when **≥2 distinct `step_id`s** are flagged
   already-built (a *collection* → "re-ground / re-baseline this set"), emitted once
   for the set. Three load-bearing specifics:
   - **Count distinct step ids, not raw hits.** `heuristic_already_done` appends one
     `HeuristicHit` per (step, symbol, file), so one over-broad step can yield ≥2
     hits; the trigger is `len({hit.step_id}) ≥ 2`. (`step-dedup-count`)
   - **Gate the emit to the reconcile lane.** `review.py:extract_recommendations` is
     **shared** — `review_plan_full` feeds it `heuristic_already_done` hits on every
     completeness/review/run-gate path (the completeness builder opts out via
     `heuristic_hits=[]`). An unconditional emit leaks the finding outside reconcile,
     which #67 scopes it to; condition it on the reconcile surface.
     (`reconcile-finding-scope`)
   - **Carry the re-ground remedy text in the finding's own message.**
     `triage_reason`'s neutral branch names no re-ground remedy and the per-source
     triage step was dropped, so the finding must self-describe "mark done /
     re-baseline this set." (`reconcile-triage-message`)
   A **single** already-built step stays the existing plain heuristic hit. Remedy is
   **re-ground**, not blindly `merge` (`heuristic_already_done` flags steps that may
   not be adjacent/contiguous/PENDING, while `merge_steps` needs a contiguous
   all-PENDING run).
4. **Scope-out recommendation renders prose-only (no forward-ref command).** The
   `convergence` scope-out recommendation renders **prose-only** — `render_diagnosis`
   prints no runnable `plan-tool scope-out …` line — because the executor ships in
   the follow-up plan, which flips it. No recommendation points at a command that
   does not yet exist.

## The unified remedy vocabulary (conceptual — for the docs)

| Remedy | Altitude × disposition | Surface |
|---|---|---|
| **split** (step) | step → two siblings | `granularity-split` (`granularity.py`) → `plan-tool split` / `escalate_to_split` |
| **merge** / **re-ground** | fold sibling back / re-baseline | `granularity-merge` + the reconcile already-built signal → `plan-tool merge` |
| **scope-out** (plan + defer) | plan scope → narrow + carved side to a forward-seed | `convergence` **fork-arm** (prose here) + the **executor** (follow-up plan) |
| **re-seed** (plan limit) | split everything / restart | the `convergence` structural fork → `create --from-existing` |

## Seams already in place (verify before extending)

- **`convergence_diagnosis.py`** — `classify_fork` (the localized-vs-structural
  fork; note FORK_LOCALIZED can carry several regions on one step),
  `RegionTrend.max_severity` + `first_severity` / `last_severity` (the trigger
  data), `render_diagnosis` / `_split_command` / `_reseed_command` (where the
  prose-only scope-out recommendation renders). Surfaced read-only by `plan-tool
  convergence` (exits 0, no Claude, no mutation).
- **`granularity.py`** — the `granularity-split` / `granularity-merge` source-token
  literals (reuse the literals only, not the detectors — decision 2); kept out of
  `APPLY_ELIGIBLE_SOURCES`.
- **`review.py`** — `heuristic_already_done` + `_heuristic_recommendation` (the
  code signal + existing per-step hit for #67); `STRUCTURAL_SOURCES` /
  `APPLY_ELIGIBLE_SOURCES` / `triage_reason` (the routing the reconcile finding
  joins — note `granularity-merge` already routes to the neutral generic branch, so
  no per-source "split" misrouting exists to fix); `review_plan_full` /
  `render_review_prompt` (the reconcile audit #67 extends; recent `creates:`
  grounding fix — declared files = `files:` ∪ `creates:`).

## Scope of work

1. **Convergence scope-out recommendation (#70):** add scope-out as a **sub-arm of
   the localized fork** in `classify_fork`, fired by the decidable set-trigger
   (decision 1); `render_diagnosis` renders it **prose-only** (decision 4).
   Read-only / advisory.
2. **Code-grounded reconcile structural pass (#67):** a code-vs-plan **re-ground**
   finding built on `heuristic_already_done`, firing on a **≥2-step already-built
   set** (decision 3), reusing the `granularity-*` literals (decision 2). Advisory,
   recommend-only, never flips the exit code.
3. **Unified-vocabulary docs:** document the four remedies as **one altitude ×
   disposition model**; clarify scope-out is a fork-arm + executor (not a review
   source); note the actuator ships in `scope-out-executor`; trim BACKLOG #70/#67 to
   reflect this advisory/actuator split.

## Non-goals / out of scope

- **The `plan-tool scope-out` executor / any plan mutation** — the separate
  `scope-out-executor` plan.
- **A `review.py` `scope-out` source token** — dropped (no producer; scope-out is a
  fork-arm + executor, decision in §"scope-out is a fork-arm").
- A **new split/merge algorithm** — reuse the existing executors.
- **A programmatic BACKLOG.md writer** or an **in-plan `DEFERRED`** disposition — the
  scope-out destination is a forward-seed (settled; realized in the executor plan).
- Removing the BUG_BACKLOG reconcile-lane bookkeeping noise — separate fix.

## Risks

- **False "already implemented" calls** on superficial symbol overlap — reuse
  `heuristic_already_done` carefully; keep it advisory; the ≥2-step trigger + the
  re-ground framing reduce noise (decision 3).
- **Forward-ref** — the recommendation must stay prose-only until the executor plan
  ships (decision 4).

## Acceptance criteria (plan-level)

- `plan-tool convergence` emits a **prose-only** scope-out / defer recommendation
  when, for the single step the localized fork resolves to, **any** co-located
  region has `max_severity ≥ high` and a non-decreasing first→last trend — distinct
  from re-split and the structural re-seed. Read-only, advisory, exits 0. No invented
  severity grade; no runnable command rendered.
- `reconcile` surfaces a **code-grounded re-ground finding** when **≥2 distinct
  step ids** are flagged already-built — **scoped to the reconcile lane** (not the
  shared completeness/review/run-gate paths), sourced as **`granularity-merge`** (so
  it routes to the neutral triage branch, not the split bridge), and **carrying its
  own re-ground/re-baseline remedy text**. Distinct from the existing per-step
  heuristic hit; advisory, never flips the exit code.
- The four remedies read as **one altitude × disposition model** in the docs, with
  scope-out documented as a fork-arm + executor (not a review source) and its
  actuator noted as shipping in the follow-up plan.
- No `review.py` `scope-out` source token is introduced; existing structural routing
  tokens and their `APPLY_ELIGIBLE_SOURCES` exclusion are unchanged; the granularity
  advisor and `escalate_to_split` behave as before.
