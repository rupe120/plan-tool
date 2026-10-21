> **Replaced**: this file has been superseded by `docs/implementation-plans/2-lazy-deferral-confirmation.md`.
> Preserved here for history; do not edit.

# Plan seed: lazy deferral confirmation — bucket-tagged guide posts, concept-scoped fingerprints

This file is a `plan-tool create` input. Use it via:

    plan-tool create lazy-deferral-confirmation --from-existing plan-seeds/lazy-deferral-confirmation.md --iterate

> **Scope boundary — the MVP of "confirm the deferred concepts," rebuilt on a lazy foundation
> that fixes the staleness root.** A deferred concept is a **guide post** (a coarse bucket tag +
> title + decision), not a node in a pre-computed hierarchical tree. The full hierarchy is
> **drilled lazily** (materialized on demand when the operator navigates in), and the staleness
> **fingerprint is scoped to only the concepts actually drilled/materialized** — not the whole
> plan+detail bundle. This supersedes the prior `concept-write-integrity` hardening AND the prior
> 5-step lazy-deferral plan (which reused the bundle-wide fingerprint and hit an unfixable
> staleness residual). It does **not** rip out the shipped hierarchical machinery; it stops
> pre-computing it. Deliberately **grows past the old ~5–7 step ceiling** — the staleness fix is
> load-bearing (it breaks the core confirm loop otherwise), a decision made per BACKLOG #129's
> "grow only when the root demands it," not silent creep.

Source: 2026-07-15 convergence of the prior lazy-deferral plan. A 2-pass completeness audit
showed the deferred-plan record goes stale before the operator can confirm it (the bundle-wide
`plan_fingerprint` invalidates on any unrelated edit), so `scope-review` refuses and the confirm
loop dead-ends — the residual the prior plan deferred was actually central. When this work ships,
its final docs/status step must update `BACKLOG.md`: close #121 (lazy shipped), note it supersedes
the eager-hardening path (#126–#128 residue stands), and reconcile #129.

---

## Overview

The original desire (BACKLOG #121) was to **confirm the concepts the tool defers** so none is
silently dropped. The shipped machinery over-solved it: `create` eagerly decomposes every plan
into a ~28-node concept tree (`bootstrap_concepts` + `emit_concept_tree` enrichment) kept in sync
with prose via a **whole-bundle fingerprint** (`compute_plan_fingerprint` on `load_concepts`,
`concept_tree.py:234`). A prior lazy attempt stopped the enrichment but reused that bundle
fingerprint — and a pending deferral, which must survive until the operator confirms it *later*,
goes stale on the next unrelated edit, so `scope-review` (`scope_review_cmd.py:cmd_scope_review`,
which returns `SCOPE_REVIEW_INVALID_STATE_EXIT` on `StaleConceptTreeError`) refuses to confirm it.

The fix is to **disconnect the deferred concept from the pre-computed tree**: record it as a
lightweight *guide post* anchored only to its coarse bucket, drill the hierarchy lazily, and scope
the staleness fingerprint to just the concepts actually materialized. An unrelated plan edit then
never invalidates a pending deferral, so the confirm loop works.

## Problem statement — grounded

1. **Bundle-wide fingerprint is wrong for a persist-until-confirmed record.** `load_concepts`
   raises `StaleConceptTreeError` when the stored `plan_fingerprint` ≠ `compute_plan_fingerprint`
   (whole plan + every detail file, `concept_tree.py:234`, `review_persistence.py:58-87`). A
   pending deferral is confirmed *after* more edits by design, so it is normally stale by confirm
   time. This raises through `scope-review` (dead-ends the confirm), `check_concept_coverage` →
   `load_concepts` (crashes `status`, the completeness audit, and the `--iterate` gate via
   `collect_smell_findings` / `collect_self_consistency_findings`).
2. **Eager decomposition + a pre-computed tree is unnecessary.** `bootstrap_concepts`
   (`concept_bootstrap.py:55`, called at `create.py:5932`) emits a node per body section and
   `emit_concept_tree` (`concept_tree.py:330`, `create.py:5956`) enriches ~20 more — none of which
   anyone signs off on. Knowing a concept's coarse **bucket** (its body section / top-level area)
   is cheap; the full path/sub-tree only matters when someone actually drills in.
3. **The confirm gate reviews the whole tree and is silent under `-y`.** `_review_create_concepts`
   (`create.py:4506-4537`) walks every node and is skipped non-interactively (`create.py:4516`),
   silently accepting the tool's suggestions — the founding incident.

## Architecture

Reuse what is already lazy, replace only the fingerprint model and the record shape.

- **A. Guide-post record, not a tree.** A deferred concept is `{bucket, title, rationale,
  decision (defer|wont_do), review_state}`. `bucket` is a coarse tag (the body-section / top-level
  concept it belongs to — derivable cheaply without drilling). No `parent_path`/`depth`
  pre-computed. An un-deferred plan has no record at all.
- **B. Concept-scoped fingerprint (the staleness fix — the load-bearing change).** Replace the
  bundle-wide `plan_fingerprint` guard for these records with a **per-guide-post anchor hash** over
  only the concept's own bucket source text (the section it was drilled from), not the whole
  bundle. A guide post goes stale only if *its* bucket changes materially; an unrelated
  prose/detail edit leaves it valid. Every read/confirm path (`scope-review`, `status`,
  `check_concept_coverage` and its `collect_*` callers) validates against this scoped anchor and
  treats a genuine bucket-level mismatch as "re-derive," never a hard crash. This is new machinery
  the prior plan deliberately avoided; it is the reason to re-seed.
- **C. Lazy drill.** The sub-concepts under a bucket are derived on demand (reuse
  `bootstrap_concepts` / `scope_review_cmd.py`'s already-lazy derive-from-plan-text, which tolerates
  an absent record) when the operator navigates into that bucket to browse or confirm — never
  pre-computed at create. Only drilled concepts get materialized + fingerprinted.
- **D. Deferral-only confirm gate, safe under `-y`.** Replace the whole-tree walk with a gate that
  records only proposed `defer`/`wont_do` guide posts. Under `-y` a proposal is recorded **pending**
  (never auto-signed); interactively the operator may confirm (`defer`/`wont_do`) or **decline**
  (the declined proposal is dropped — no guide post — not silently signed). Included concepts get
  nothing (a committed step is its own proof).
- **E. Present as a drillable list.** Surface the pending guide posts (bucket + title + the bare
  `node.id` token `scope-review --concept` consumes) in `status`, the completeness report, and a
  `create` run-summary line — non-blocking (only an operator `scope-review` decision resolves it;
  blocking would wedge the `--iterate` loop). The operator drills the high-level bucket list to land
  on a specific deferred concept and confirm it; confirming signs it off and renders it into
  `## Deferred` via the existing `render_scope_decisions` path.
- **F. Detail materializes a guide post, not a tree node.** Detail's shared-find routing records a
  new deferral as a bucket-tagged pending guide post (deriving the target lazily), with no dependency
  on a pre-materialized section tree — so it works on any plan, including one already carrying a
  narrowed record (the conflict that broke the prior plan). Never auto-signed under `-y`.

## Out of scope

- Removing the shipped hierarchical tree / `Step.concept_ids` — left dormant; this stops
  pre-computing the tree, it does not delete the types. `split`/`merge`/`reground`/`scope-out`
  conservation keeps working on whatever ids exist.
- The `concept-write-integrity` transactional hardening / #126–#128 — moot for the lazy path.
- A dismiss/remove verb for a wrong pending guide post, and "the concept should be implemented
  instead" (a re-plan) — a wrong pending guide post is inert until confirmed; active dismissal is
  a deferred nicety.

## Risks

- The concept-scoped fingerprint is genuinely new machinery — the highest-risk step; it must
  interoperate with the existing `concepts.json` record without breaking the eager/legacy readers
  (a guide-post record and a legacy full-tree record must both remain loadable, or legacy is
  explicitly migrated).
- Bucket granularity is a judgment call — too coarse and a guide post never goes stale even when it
  should; too fine and it re-computes the pre-materialization it avoids. Anchor to the body-section
  bucket as the default and validate against real plans.

## Testing

- **Staleness (the root):** a plan with a pending guide post, then an edit to an **unrelated**
  section, leaves the guide post valid — `scope-review`, `status`, and `check_concept_coverage` all
  still act on it (no `StaleConceptTreeError`), and `scope-review defer` confirms it successfully.
  An edit to the guide post's **own bucket** marks it for re-derive.
- **Founding incident:** `create -y` proposing a deferral leaves a pending guide post surfaced with
  its bare id in all three surfaces, never silently signed; interactive **decline** drops it.
- **Confirm loop end-to-end:** surface → drill → `scope-review defer` → rendered in `## Deferred`,
  on a plan that has been edited since the deferral was recorded.
- **Detail on a narrowed/absent record:** detail's shared-find records a pending guide post with no
  dependency on a pre-materialized section tree.
- **Un-deferred plan:** no `concepts.json`, no `emit_concept_tree` call, no staleness anywhere.

## Deferred

- Per-bucket drill caching / incremental materialization beyond first-drill — the MVP derives on
  demand each time; caching is an optimization.
- Migrating existing eager full-tree `concepts.json` records to the guide-post shape — legacy
  records stay loadable; a migration is a separate step if wanted.
- Program-scale / authoring-time decomposition monitoring — BACKLOG #129.
