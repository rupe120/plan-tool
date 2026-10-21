> **Replaced**: this file has been superseded by `docs/implementation-plans/2-lazy-deferral-confirmation.md`.
> Preserved here for history; do not edit.

# Plan seed: lazy deferral confirmation — confirm what the tool defers, decompose nothing up front

This file is a `plan-tool create` input. Use it via:

    plan-tool create lazy-deferral-confirmation --from-existing plan-seeds/lazy-deferral-confirmation.md --iterate

> **Scope boundary — this is the MVP of the original desire ("confirm the list of deferred
> concepts"), reached by making concept materialization LAZY instead of eager.** It stops the
> tool from decomposing every plan into a full concept tree at `create` time, and instead
> surfaces — for operator confirmation — only the concepts the tool actually proposes to
> **defer** or mark **won't-do**. It does **not** rip out the shipped hierarchical concept
> machinery (the tree, `Step.concept_ids`, `synchronize_concepts`); that stays in place but
> dormant-by-default. Expected decomposition: **~5–7 steps.** If convergence pressure grows it
> past that, defer to the backlog (see the step-ceiling discipline in BACKLOG #129) rather than
> growing this plan.

Source: 2026-07-15 review of the concept sign-off arc. The original need (BACKLOG #121, an
operator missed a concept the tool silently deferred) grew into an eager hierarchical
decomposition (~28 concepts per plan) whose upkeep spawned a six-plan remediation program
(distilled to `concept-write-integrity`, then reconsidered). This seed returns to the MVP.
When this work ships, its final docs/status step must update `BACKLOG.md`: note that it
supersedes the eager-machinery hardening path (`concept-write-integrity` / #126–#128) for the
common flow, and reconcile #121's disposition.

---

## Overview

Today `create` **eagerly** builds a concept tree for every plan whether or not anything is
deferred: `bootstrap_concepts` (`plan_tool/concept_bootstrap.py:55`, called unconditionally at
`plan_tool/create.py:5932`) emits one node per body section (~8), and `emit_concept_tree`
(`plan_tool/concept_tree.py:330`, invoked at `plan_tool/create.py:5956` when no saved tree
exists) enriches that to ~20 more speculative sub-concepts — **28 nodes in the shipped
`concept-write-integrity` example, all `review_state="unreviewed"`, `decision="include"`.**
Almost none are ever deferred; they are the plan's prose re-encoded as a second structure that
then has to be kept in sync (the coupling that produced the write-integrity bugs and the
whole-bundle-fingerprint staleness that broke this very plan's audit twice during authoring).

The desire was never "decompose the whole plan." It was **"when the tool defers something, let
me confirm or override that, and record it so it can't be silently dropped."** Deliver exactly
that, lazily: materialize a concept record entry **only at a deferral decision**, surface those
(and only those) for confirmation, and leave un-deferred plans with no concept record at all.

The good news from grounding: most of the lazy behavior is **already latent**.

- `scope-review` (`plan_tool/cli/scope_review_cmd.py:41-119`) already **re-derives** the tree
  from live plan text every run and tolerates an absent record (`original_tree is None` →
  bootstrap directly, `scope_review_cmd.py:57-64`). It is the natural materialize+sign-off hook.
- The coverage findings (`check_concept_coverage`, `plan_tool/review.py:2290-2380`) are already
  **inert** on an absent/`None`/all-unreviewed tree (`review.py:2312, 2317`); they only fire on
  `review_state=="approved"` nodes. So an empty-until-deferred record behaves identically to
  today's eager-but-unreviewed tree: **zero findings** until an operator signs off.

So the change is small: stop eager enrichment, make the confirm gate deferral-focused and safe
under `-y`, and hang materialization on the defer points.

## Problem statement — grounded

1. **Eager over-decomposition.** `emit_concept_tree` at `create.py:5956` adds ~20 speculative
   sub-concepts nobody signs off on. That enrichment is the bloat, the sync surface, and (via
   the whole-bundle `compute_plan_fingerprint` on `load_concepts`,
   `plan_tool/concept_tree.py:234`) the staleness coupling — any plan/detail edit invalidates
   the record even when no deferral decision changed.
2. **The confirm gate reviews the wrong thing, and is silent under `-y`.** The single human gate
   `_review_create_concepts` (`plan_tool/create.py:4506-4537`) walks the **whole tree**
   (include/defer/wont_do per node) and is **skipped** non-interactively (`create.py:4516-4517`),
   accepting the tool's suggestions silently — the exact founding-incident failure, since these
   plans are authored with `-y`.
3. **The deferral producers already exist but don't gate.** The three defer points —
   create-synthesis (already concept-record-driven and told to abstain,
   `prompts/synthesize-body.md:88-94`), the decomposition "a branch with no namable live
   scenario is NOT a step — defer it" instruction (`create.py:1983-1984`, silently omits from
   the step array), and detail's shared-find routing (`detail.py:399-427`, bounded to a
   pre-approved `decision="defer"` node by `detail.py:1683-1691`) — none stop to confirm a *new*
   deferral.

## Architecture — the lazy MVP

Keep the shipped record format and its writer; change *when and how much* gets materialized.

- **A. Stop eager enrichment.** Do not call `emit_concept_tree` at create. The record is either
  absent (preferred for the common case) or a thin section-only bootstrap — decide during
  detailing which is cleaner given the `create`-writes-a-tree test coupling
  (`create.py:5932-5974`; tests assert `concepts.json` exists post-create — the main breakage
  surface to reconcile). Enrichment becomes dead code for the create path; leave the function
  for possible reuse but stop invoking it eagerly.
- **B. Deferral-focused confirmation.** Replace the whole-tree walk with a gate that surfaces
  **only proposed `defer` / `wont_do` decisions** — the decisions that actually matter. An
  included concept needs no confirmation and no record (a committed step is its own proof;
  coverage is already inert on unreviewed).
- **C. Safe under `-y` (closes the founding incident).** Non-interactively, a proposed deferral
  is recorded **unconfirmed**, never silently accepted. Make an unconfirmed proposed deferral a
  **blocking** signal so it cannot ship unseen — the `concept-unsigned-deferral` source exists
  (`review.py:2235`, today info-only); this plan's decision is whether to promote a *proposed
  but unconfirmed defer* to blocking, or surface it in the run summary + `list --status`. The
  operator confirms later via `scope-review` (already lazy).
- **D. Materialize at the defer points, via the existing hook.** At each defer decision (B/C
  above, and detail's shared-find routing), materialize the one concept + its proposed decision
  through `scope-review`'s derive+sign-off path, which already runs on an absent tree. Preserve
  detail's precondition that a deferral references a signed-off `decision="defer"` node
  (`detail.py:1683-1691`) — lazy means "materialize+sign off as part of the defer action," not
  "reference nothing."
- **E. Record stays small and decision-keyed.** Only defer/wont_do decisions and their
  confirmation state. This is what breaks the whole-bundle-fingerprint staleness coupling for
  the common case: an un-deferred plan has no record, so no fingerprint to go stale.

## Out of scope

- Removing the hierarchical tree, `parent_path`/`depth`, or `Step.concept_ids` — leave the
  shipped machinery in place but dormant; migration/deletion is a separate decision. `split` /
  `merge` / `reground` / `scope-out` conservation of `concept_ids` keeps working on whatever ids
  exist (empty is the valid default).
- The `concept-write-integrity` transactional hardening and BACKLOG #126–#128 — largely moot for
  the lazy path (fewer/smaller writers, no big record to diverge from prose); this seed supersedes
  that path for the common flow rather than completing it.
- New schema, commands, or a rewrite of `concept_sync` — reuse `scope-review`'s derive+sign-off.

## Risks

- The `create`-writes-a-tree test coupling is the main breakage surface (A) — budget a step to
  reconcile those tests to "absent record is valid."
- Promoting unconfirmed deferrals to blocking (C) could block legitimate `-y` batch authoring;
  gate the decision behind evidence and offer a surface-not-block fallback.

## Testing

- Un-deferred plan: `create -y` produces **no** blocking findings and (per A's decision) either
  no `concepts.json` or a thin section-only one; no `emit_concept_tree` call.
- Founding-incident regression: a `create -y` whose decomposition proposes a deferral leaves an
  **unconfirmed** deferral that the completeness/run summary surfaces (or blocks on), never a
  silently-accepted one.
- Lazy materialization: a `scope-review` defer on a plan with no prior record creates exactly the
  one deferred concept, signed off, and renders it into `## Deferred` (reuses the existing
  `render_scope_decisions` path).
- Staleness: editing an un-deferred plan's prose does not raise `StaleConceptTreeError` anywhere
  (there is no record to invalidate).

## Deferred

- Whether to keep a thin section bootstrap or go fully record-absent at create (A) — decide from
  the test-coupling cost during detailing.
- Enforcing a seed-declared step ceiling and the program-scale monitoring that would have caught
  the original blowup — BACKLOG **#129**.
