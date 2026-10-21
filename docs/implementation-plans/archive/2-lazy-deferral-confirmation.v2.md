---
title: Lazy Deferral Confirmation
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a concept-scoped anchor hash over a single bucket's source text
  files:
  - plan_tool/review_persistence.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/01-concept-scoped-anchor-hash-over-single.md
  status: current
- id: 2
  title: Add the guide-post record shape and a loader that validates against the scoped
    anchor instead of the bundle fingerprint, keeping legacy full-tree records loadable
  files:
  - plan_tool/concept_tree.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/02-guide-post-record-shape-loader-that.md
- id: 3
  title: Stop pre-computing the concept tree — remove create's emit_concept_tree enrichment
    call and reconcile the prompt-count couplings in test_create.py
  files:
  - plan_tool/create.py
  - tests/test_create.py
  - tests/test_concept_emit.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/03-stop-pre-computing-concept-tree-remove.md
- id: 4
  title: Replace create's whole-tree confirm walk with a deferral-only gate that records
    proposed defer/wont_do as pending guide posts, safe under -y
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/04-replace-create-whole-tree-confirm-walk.md
- id: 5
  title: Make scope-review drill a bucket lazily and confirm a guide post against
    the scoped anchor, re-deriving on a bucket mismatch instead of dead-ending on
    StaleConceptTreeError
  files:
  - plan_tool/cli/scope_review_cmd.py
  - tests/cli/test_scope_review_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/05-make-scope-review-drill-bucket-lazily.md
- id: 6
  title: Make check_concept_coverage and its collect_* callers validate the scoped
    anchor and never crash on a bucket-level mismatch
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/06-make-check-concept-coverage-its-collect.md
- id: 7
  title: Surface pending guide posts as a drillable bucket + title + bare-id list
    in status, the completeness report, and a create run-summary line, non-blocking
  files:
  - plan_tool/cli/inspect.py
  - plan_tool/completeness_report.py
  - plan_tool/create.py
  - tests/test_review.py
  - tests/test_completeness_report.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 4
  - 6
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/07-surface-pending-guide-posts-drillable.md
- id: 8
  title: Make detail's shared-find routing record a new deferral as a bucket-tagged
    pending guide post, deriving the target lazily, with no dependency on a pre-materialized
    section tree and never auto-signed under -y
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/08-make-detail-shared-find-routing-record.md
- id: 9
  title: 'Update BACKLOG.md and CLAUDE.md to close #121, note the lazy path supersedes
    the eager-hardening #126-#128 residue, and reconcile #129'
  files:
  - BACKLOG.md
  - CLAUDE.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  - 5
  - 6
  - 7
  - 8
  detail: docs/implementation-plans/plan-details/lazy-deferral-confirmation/09-update-backlog-md-claude-md-close-121.md
---
# Lazy Deferral Confirmation

> **Superseded — parked 2026-07-15.** This 9-step guide-post plan built a per-bucket
> **content-hash anchor** that the first audit showed was decorative (nothing acted on a
> bucket-content mismatch differently), and a **lazy drill** with no sub-concepts to
> navigate to (removing enrichment left bucket == title == section). Superseded by a
> simplification to **flat decision records, not fingerprint-validated** —
> `plan-seeds/lazy-deferral-confirmation.md`. Kept in `archive/` as reference.

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

## Input

This plan reads and extends the persisted concept record contract, so its correctness depends on that schema staying loadable across shapes:

- **`plan-details/<slug>/concepts.json`** via `load_concepts` (`concept_tree.py:234`) — the plan consumes the existing record's fields and must keep both a legacy eager full-tree record and the new guide-post record parseable.
- **The staleness guard it replaces** — `plan_fingerprint` (stored) vs `compute_plan_fingerprint` (whole plan + every detail file), and the `StaleConceptTreeError` raised on mismatch (`review_persistence.py:58-87`). The new per-guide-post anchor hash supplants this guard only for guide-post records.
- **`Step.concept_ids`** — left dormant but still the ownership token that `split`/`merge`/`reground`/`scope-out` conservation reads; this plan must not break it.
- **The scope-review / render surfaces it hooks** — `scope_review_cmd.py:cmd_scope_review` (and its `SCOPE_REVIEW_INVALID_STATE_EXIT` / `SCOPE_REVIEW_*` exit codes), `check_concept_coverage` and its `collect_smell_findings` / `collect_self_consistency_findings` callers, and `render_scope_decisions` (the existing path that renders a confirmed deferral into `## Deferred`).

Limit on verifying the contract: legacy full-tree records must remain loadable (or be explicitly migrated); the plan cannot assume the guide-post shape is the only shape on disk.

## References

- [hashlib — Secure hashes and message digests (Python docs)](https://docs.python.org/3/library/hashlib.html) — Official reference for SHA-256 and other hash constructors used to compute the concept-scoped anchor hash / fingerprint over a bucket's source text.
- [dataclasses — Data Classes (Python docs)](https://docs.python.org/3/library/dataclasses.html) — Documents @dataclass with frozen=True (and FrozenInstanceError), the pattern for the immutable guide-post record {bucket, title, rationale, decision, review_state}.
- [json — JSON encoder and decoder (Python docs)](https://docs.python.org/3/library/json.html) — Covers dumps/loads and serialization behavior needed to persist and load the concepts.json record while keeping legacy full-tree records loadable.
- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — Reference for the 'append' action and option parsing behind the repeated --concept IDs that scope-review consumes.
- [pytest — How to use temporary directories and files in tests](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — The tmp_path fixture used to write hermetic tests for the staleness/confirm-loop scenarios required by the plan's testing section.

## Steps

See the `steps:` block in the frontmatter.

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

Follow the project's unit-first convention (`tests/test_X.py` mirroring `plan_tool/X.py`); reserve `@pytest.mark.integration` for the end-to-end confirm loop that drives `scope-review`/`status`/`create` across modules. The existing concept-record and scope-review suites must still pass.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- A plan carrying a pending guide post, after an edit to an **unrelated** section, resolves through `scope-review`, `status`, and `check_concept_coverage` without raising `StaleConceptTreeError`, and `scope-review defer` confirms it (exits 0).
- An edit to a guide post's **own bucket** source marks that guide post for re-derive (its scoped anchor mismatches); an unrelated edit does not.
- `create -y` proposing a deferral records a **pending** guide post surfaced with its bare `node.id` in `status`, the completeness report, and the `create` run-summary line, and never auto-signs it.
- Interactively **declining** a proposed deferral drops it — no guide post is written.
- The confirm loop (surface → drill → `scope-review defer`) renders the concept into `## Deferred` via `render_scope_decisions`, even on a plan edited since the deferral was recorded.
- Detail's shared-find routing records a pending guide post on a plan with a narrowed **or absent** `concepts.json`, with no dependency on a pre-materialized section tree, and never auto-signs it under `-y`.
- An un-deferred plan has no `concepts.json`, triggers no `emit_concept_tree` call at create, and raises no staleness on any read path.
- Both a legacy eager full-tree `concepts.json` record and a new guide-post record remain loadable (or legacy is explicitly migrated).
- Guide-post surfacing is non-blocking: unresolved pending guide posts do not wedge the `--iterate` convergence loop.
- The final docs/status step updates `BACKLOG.md`: closes #121, notes the supersession of the eager-hardening path (#126–#128 residue stands), and reconciles #129.

## Deferred

- Per-bucket drill caching / incremental materialization beyond first-drill — the MVP derives on demand each time; caching is an optimization.
- Migrating existing eager full-tree `concepts.json` records to the guide-post shape — legacy records stay loadable; a migration is a separate step if wanted.
- Program-scale / authoring-time decomposition monitoring — BACKLOG #129.
