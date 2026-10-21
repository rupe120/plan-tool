> **Replaced**: this file has been superseded by `docs/implementation-plans/2-lazy-deferral-confirmation.md`.
> Preserved here for history; do not edit.

# Plan seed: lazy deferral confirmation — flat decision records, not fingerprint-validated

This file is a `plan-tool create` input. Use it via:

    plan-tool create lazy-deferral-confirmation --from-existing plan-seeds/lazy-deferral-confirmation.md --iterate

> **Scope boundary — the leanest MVP of "confirm the deferred concepts."** A deferred concept is
> a **flat decision record** `{bucket, title, rationale, decision, review_state}` — an operator/tool
> *decision*, not a derived cache. The key move: a decision record is **not fingerprint-validated
> against plan text at all** (a recorded decision does not go stale when unrelated prose changes —
> that is the real staleness fix). Its only validity check is "does its bucket still exist." There is
> **no concept hierarchy and no drill** in this MVP — the bucket (a coarse section-level tag) is the
> leaf; the pending list is grouped by bucket. This supersedes the prior two lazy attempts, whose
> whole-bundle fingerprint dead-ended the confirm loop (v1) and whose per-bucket **content hash**
> turned out decorative — nothing acted on a mismatch differently — while the promised drill had no
> sub-concepts to navigate to once enrichment was removed (v2). It does not rip out the shipped
> hierarchical machinery; it stops using it. Expected ~5–7 steps.

Source: 2026-07-15 first audit of the v2 (guide-post + concept-scoped-anchor) plan. Two findings
drove this simplification: `[concept-scoped-anchor]` — the SHA-over-bucket-text gated no decision on
any read/confirm path, so the real fix was simply not fingerprint-checking decision records; and
`[lazy-drill-subconcepts]` — removing `emit_concept_tree` left `bucket == title == section name`, so
there was nothing below a bucket to drill into. The lean design keeps the working parts and drops
both over-builds. When this ships, its final docs/status step must update `BACKLOG.md`: close #121
(lazy shipped), note it supersedes the eager-hardening path (#126–#128 residue stands), reconcile #129.

---

## Overview

BACKLOG #121's desire was to **confirm the concepts the tool defers** so none is silently dropped.
The shipped machinery over-solved it: `create` eagerly decomposes every plan into a ~28-node concept
tree kept in sync with prose via a whole-bundle fingerprint (`compute_plan_fingerprint` on
`load_concepts`, `concept_tree.py:234`). A pending deferral must survive until the operator confirms
it *later* — after more edits — so any whole-bundle fingerprint on that record is stale by confirm
time, and `scope-review` (`scope_review_cmd.py:cmd_scope_review`, which returns
`SCOPE_REVIEW_INVALID_STATE_EXIT` on `StaleConceptTreeError`) then refuses to confirm it.

The fix is to treat a deferral as a **decision, not a derived value**: record it flat, don't validate
it against plan text, and only check that its bucket still exists. A recorded decision then never goes
stale on an unrelated edit, so the confirm loop works — with no fingerprint machinery and no
pre-computed hierarchy.

## Problem statement — grounded

1. **A decision record must not be fingerprint-validated against plan text.** `load_concepts` raises
   `StaleConceptTreeError` on a `plan_fingerprint` mismatch (`concept_tree.py:234`), which cascades
   through `scope-review` (dead-ends confirm), `check_concept_coverage` → `load_concepts` (crashes
   `status`, the completeness audit, and the `--iterate` gate via `collect_smell_findings` /
   `collect_self_consistency_findings`). A pending deferral is confirmed after edits by design, so it
   is normally stale — the guard is simply wrong for this record.
2. **Eager decomposition + a hierarchy is unneeded.** `bootstrap_concepts` (`concept_bootstrap.py:55`,
   `create.py:5932`) emits a node per body section and `emit_concept_tree` (`concept_tree.py:330`,
   `create.py:5956`) enriches ~20 more that nobody signs off on. A deferral only needs its coarse
   **bucket** (the body-section it sits under — cheap to know); nothing finer is required to confirm it.
3. **The confirm gate reviews the whole tree and is silent under `-y`.** `_review_create_concepts`
   (`create.py:4506-4537`) walks every node and is skipped non-interactively (`create.py:4516`),
   silently accepting the tool's suggestions — the founding incident.

## Architecture

Keep what is already lazy; remove the fingerprint guard and the pre-computed tree.

- **A. Flat decision record.** A deferred concept is `{bucket, title, rationale, decision
  (defer|wont_do), review_state}`. `bucket` is a coarse section-level tag. No `parent_path`/`depth`,
  no hierarchy, no per-record hash. An un-deferred plan has **no record at all**.
- **B. Not fingerprint-validated (the staleness fix — the whole point).** These records skip the
  whole-bundle `plan_fingerprint` guard on load: a decision record is not a cache of plan text, so it
  does not go stale when the plan is edited. Every read/confirm path (`scope-review`, `status`,
  `check_concept_coverage` and its `collect_*` callers) loads and acts on the record **without** a
  `StaleConceptTreeError` gate. The only validity question is C.
- **C. Bucket-existence check, not a content hash.** The one thing that can invalidate a deferral is
  its bucket no longer existing (the section it referred to was deleted/renamed). Read/confirm paths
  check whether the record's `bucket` still resolves to a current body section (a **name lookup**, no
  hash). A missing bucket **surfaces the record for operator re-review** (not a silent stand, not a
  hard crash) — the dismiss/re-home action is the operator's `scope-review`, not automatic.
- **D. Deferral-only confirm gate, safe under `-y`.** Replace the whole-tree walk with a gate that
  records only proposed `defer`/`wont_do` decisions. Under `-y` a proposal is recorded **pending**
  (never auto-signed); interactively the operator may confirm (`defer`/`wont_do`) or **decline** (the
  declined proposal is dropped — no record). Included concepts get nothing (a committed step is proof).
- **E. Surface as a flat, bucket-grouped list.** Surface pending decisions (grouped by bucket; each with
  title + the bare `node.id` token `scope-review --concept` consumes) in `status`, the completeness
  report, and a `create` run-summary line — **non-blocking** (only an operator `scope-review` decision
  resolves it; blocking would wedge the `--iterate` loop). No drilling — the bucket grouping *is* the
  navigation. Confirming signs it off and renders it into `## Deferred` via the existing
  `render_scope_decisions` path.
- **F. Detail records a flat pending decision.** Detail's shared-find routing records a new deferral as
  a flat pending decision (bucket-tagged), with no dependency on a pre-materialized tree — so it works
  on any plan. Never auto-signed under `-y`.

## Out of scope

- **Any concept hierarchy / drill / sub-concepts** — the bucket is the leaf. On-demand sub-concept
  derivation (the drill vision) is a deliberate non-goal here; if wanted it is a separate feature that
  re-introduces a scoped producer. Flat bucket-level deferrals fully solve the founding incident.
- **Per-record content fingerprints** — decisions are not caches; validity is bucket-existence only.
- Removing the shipped hierarchical tree / `Step.concept_ids` — left dormant, not deleted.
- The `concept-write-integrity` transactional hardening / #126–#128 — moot for the lazy path.
- A dismiss/remove verb for a wrong pending decision — inert until confirmed; active dismissal deferred.

## Risks

- The record must coexist with legacy full-tree `concepts.json`: a flat decision record and a legacy
  record must both remain loadable, or legacy is explicitly migrated. The load path gains a record-kind
  branch — keep it minimal.
- "Bucket still exists" needs a stable notion of a body-section name; a renamed section reads as a
  missing bucket and surfaces the record for re-review — intended, but validate it isn't noisy on
  ordinary section edits (an edit to a section's *body* must not read as a missing bucket).

## Testing

- **Staleness (the root):** a plan with a pending decision, then any unrelated edit, leaves the decision
  fully usable — `scope-review defer` confirms it, `status`/`check_concept_coverage` act on it, no
  `StaleConceptTreeError` anywhere.
- **Bucket gone:** deleting/renaming the decision's bucket surfaces it for re-review (not a silent stand,
  not a crash).
- **Founding incident:** `create -y` proposing a deferral leaves a pending decision surfaced with its bare
  id in all three surfaces, never silently signed; interactive **decline** drops it.
- **Confirm loop end-to-end:** surface → `scope-review defer` → rendered in `## Deferred`, on a plan edited
  since the deferral was recorded.
- **Detail:** shared-find records a flat pending decision on any plan (record-absent or legacy).
- **Un-deferred plan:** no `concepts.json`, no `emit_concept_tree` call, no staleness anywhere.

## Deferred

- Sub-concept drill / on-demand per-bucket derivation — a separate feature; the MVP is flat.
- Migrating existing eager full-tree records to the flat shape — legacy stays loadable; migration is separate.
- Program-scale / authoring-time decomposition monitoring — BACKLOG #129.
