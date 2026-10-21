> **Replaced**: this file has been superseded by `docs/implementation-plans/2-lazy-deferral-confirmation.md`.
> Preserved here for history; do not edit.

## Overview

Rebuild the "confirm the deferred concepts" MVP (BACKLOG #121) on a lazy foundation that fixes the staleness root. A deferred concept becomes a lightweight **guide post** — a coarse bucket tag + title + `defer`/`wont_do` decision + `review_state` — instead of a node in a pre-computed hierarchical tree. The full hierarchy is drilled lazily (materialized on demand when the operator navigates in), and the staleness fingerprint is scoped to only the concepts actually drilled — not the whole plan+detail bundle. This supersedes both the `concept-write-integrity` hardening and the prior 5-step lazy-deferral plan (which reused the bundle-wide fingerprint and hit an unfixable staleness residual). It does not rip out the shipped hierarchical machinery or `Step.concept_ids`; it stops pre-computing the tree. It deliberately grows past the old ~5–7 step ceiling because the staleness fix is load-bearing (per BACKLOG #129's "grow only when the root demands it"). When this work ships, its final docs/status step updates `BACKLOG.md`: close #121 (lazy shipped), note it supersedes the eager-hardening path (#126–#128 residue stands), and reconcile #129.

## Problem statement

The shipped machinery over-solved BACKLOG #121: `create` eagerly decomposes every plan into a ~28-node concept tree (`bootstrap_concepts` + `emit_concept_tree` enrichment) kept in sync with prose via a whole-bundle fingerprint (`compute_plan_fingerprint` on `load_concepts`, `concept_tree.py:234`).

1. **Bundle-wide fingerprint is wrong for a persist-until-confirmed record.** `load_concepts` raises `StaleConceptTreeError` when the stored `plan_fingerprint` ≠ `compute_plan_fingerprint` (whole plan + every detail file, `concept_tree.py:234`, `review_persistence.py:58-87`). A pending deferral is confirmed *after* more edits by design, so it is normally stale by confirm time. This raises through `scope-review` (`scope_review_cmd.py:cmd_scope_review`, which returns `SCOPE_REVIEW_INVALID_STATE_EXIT` on `StaleConceptTreeError`, dead-ending the confirm), and through `check_concept_coverage` → `load_concepts`, crashing `status`, the completeness audit, and the `--iterate` gate via `collect_smell_findings` / `collect_self_consistency_findings`.
2. **Eager decomposition + a pre-computed tree is unnecessary.** `bootstrap_concepts` (`concept_bootstrap.py:55`, called at `create.py:5932`) emits a node per body section and `emit_concept_tree` (`concept_tree.py:330`, `create.py:5956`) enriches ~20 more — none of which anyone signs off on. Knowing a concept's coarse bucket (its body section / top-level area) is cheap; the full path/sub-tree only matters when someone drills in.
3. **The confirm gate reviews the whole tree and is silent under `-y`.** `_review_create_concepts` (`create.py:4506-4537`) walks every node and is skipped non-interactively (`create.py:4516`), silently accepting the tool's suggestions — the founding incident.

A prior lazy attempt stopped the enrichment but reused the bundle fingerprint, so a pending deferral goes stale on the next unrelated edit and `scope-review` refuses to confirm it. A 2-pass completeness audit on 2026-07-15 confirmed the deferred-plan record goes stale before the operator can confirm it — the residual the prior plan deferred was actually central to the confirm loop.

## Architecture

Reuse what is already lazy; replace only the fingerprint model and the record shape.

- **A. Guide-post record, not a tree.** A deferred concept is `{bucket, title, rationale, decision (defer|wont_do), review_state}`. `bucket` is a coarse tag (the body-section / top-level concept it belongs to — derivable cheaply without drilling). No `parent_path`/`depth` pre-computed. An un-deferred plan has no record at all.
- **B. Concept-scoped fingerprint (the staleness fix — the load-bearing change).** Replace the bundle-wide `plan_fingerprint` guard for these records with a per-guide-post anchor hash over only the concept's own bucket source text (the section it was drilled from), not the whole bundle. A guide post goes stale only if *its* bucket changes materially; an unrelated prose/detail edit leaves it valid. Every read/confirm path (`scope-review`, `status`, `check_concept_coverage` and its `collect_*` callers) validates against this scoped anchor and treats a genuine bucket-level mismatch as "re-derive," never a hard crash. This is new machinery the prior plan deliberately avoided; it is the reason to re-seed.
- **C. Lazy drill.** The sub-concepts under a bucket are derived on demand (reuse `bootstrap_concepts` / `scope_review_cmd.py`'s already-lazy derive-from-plan-text, which tolerates an absent record) when the operator navigates into that bucket — never pre-computed at create. Only drilled concepts get materialized + fingerprinted.
- **D. Deferral-only confirm gate, safe under `-y`.** Replace the whole-tree walk with a gate that records only proposed `defer`/`wont_do` guide posts. Under `-y` a proposal is recorded **pending** (never auto-signed); interactively the operator may confirm (`defer`/`wont_do`) or **decline** (the declined proposal is dropped — no guide post — not silently signed). Included concepts get nothing (a committed step is its own proof).
- **E. Present as a drillable list.** Surface the pending guide posts (bucket + title + the bare `node.id` token `scope-review --concept` consumes) in `status`, the completeness report, and a `create` run-summary line — non-blocking (only an operator `scope-review` decision resolves it; blocking would wedge the `--iterate` loop). The operator drills the high-level bucket list to land on a specific deferred concept and confirm it; confirming signs it off and renders it into `## Deferred` via the existing `render_scope_decisions` path.
- **F. Detail materializes a guide post, not a tree node.** Detail's shared-find routing records a new deferral as a bucket-tagged pending guide post (deriving the target lazily), with no dependency on a pre-materialized section tree — so it works on any plan, including one already carrying a narrowed record (the conflict that broke the prior plan). Never auto-signed under `-y`.

## Out of scope

- Removing the shipped hierarchical tree / `Step.concept_ids` — left dormant; this stops pre-computing the tree, it does not delete the types. `split`/`merge`/`reground`/`scope-out` conservation keeps working on whatever ids exist.
- The `concept-write-integrity` transactional hardening / #126–#128 — moot for the lazy path.
- A dismiss/remove verb for a wrong pending guide post, and "the concept should be implemented instead" (a re-plan) — a wrong pending guide post is inert until confirmed; active dismissal is a deferred nicety.

## Risks

- The concept-scoped fingerprint is genuinely new machinery — the highest-risk step; it must interoperate with the existing `concepts.json` record without breaking the eager/legacy readers (a guide-post record and a legacy full-tree record must both remain loadable, or legacy is explicitly migrated).
- Bucket granularity is a judgment call — too coarse and a guide post never goes stale even when it should; too fine and it re-computes the pre-materialization it avoids. Anchor to the body-section bucket as the default and validate against real plans.

## Testing

- **Staleness (the root):** a plan with a pending guide post, then an edit to an **unrelated** section, leaves the guide post valid — `scope-review`, `status`, and `check_concept_coverage` all still act on it (no `StaleConceptTreeError`), and `scope-review defer` confirms it successfully. An edit to the guide post's **own bucket** marks it for re-derive.
- **Founding incident:** `create -y` proposing a deferral leaves a pending guide post surfaced with its bare id in all three surfaces, never silently signed; interactive **decline** drops it.
- **Confirm loop end-to-end:** surface → drill → `scope-review defer` → rendered in `## Deferred`, on a plan that has been edited since the deferral was recorded.
- **Detail on a narrowed/absent record:** detail's shared-find records a pending guide post with no dependency on a pre-materialized section tree.
- **Un-deferred plan:** no `concepts.json`, no `emit_concept_tree` call, no staleness anywhere.

## Deferred

- Per-bucket drill caching / incremental materialization beyond first-drill — the MVP derives on demand each time; caching is an optimization.
- Migrating existing eager full-tree `concepts.json` records to the guide-post shape — legacy records stay loadable; a migration is a separate step if wanted.
- Program-scale / authoring-time decomposition monitoring — BACKLOG #129.
