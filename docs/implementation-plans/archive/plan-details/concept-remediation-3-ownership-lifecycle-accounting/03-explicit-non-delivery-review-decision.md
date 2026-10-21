# Step 3 — Add explicit non-delivery review and decision transitions

## Summary

This step adds one transition policy for the structured non-delivery records introduced by step 2. `plan_tool/concept_tree.py` defines record comparison and approval rules, `plan_tool/concept_sync.py` prepares and publishes valid transitions, and `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` collects explicit operator approval when accounting changes. The key design decision is to represent a reviewed `defer|wont_do → include` request as a durable pending transition: keep the approved non-delivery record and its current plan effect until step 4 makes replacement delivery durable. On green, scoped review cannot silently approve changed accounting, lose a pending include request, or publish contradictory plan and sidecar state.

## Table of Contents

- [Summary](#summary) — Overview of the transition policy and affected files.
- [Why](#why) — The approval and pending-transition gaps this step closes.
- [Input](#input) — Contracts consumed from step 2 and the existing review flow.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Transition rules, pending include behavior, and review integration.
- [Tests](#tests) — Unit and CLI cases for the transition matrix.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Authoritative validation and test guidance.
- [Deferred](#deferred) — Lifecycle work owned by later steps.

## Why

`plan_tool/concept_review.py:review_concept_scope` clears concept sign-off when a decision changes, but `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` immediately calls it with `sign_off=True` for every valid command payload. That is not enough once step 2 makes rationale, origin, artifact routing, and record approval part of deliberate non-delivery. The flow also needs a durable representation for an approved request to move from `defer` or `wont_do` to `include`: rejecting the request before publication would leave step 4 nothing to resume, while removing the old record immediately would claim delivery before regenerated output is durable.

## Input

- **Step 2 output:** Consume the structured non-delivery record on `plan_tool/concept_tree.py:ConceptTree`, including its stable ID, exact concept ID, disposition, rationale, immutable origin reference, current artifact reference, linked step IDs, and review state. Do not define a second persisted record shape.
- **Identity and routing split:** Follow step 2’s rule that concept, disposition, and immutable origin determine record identity, while current artifact and linked-step routing may change during validated lifecycle operations.
- **Scoped decision contract:** Continue using `plan_tool/concept_review.py:CONCEPT_DECISIONS` and `review_concept_scope()` for exact-scope validation, stale-source checks, concept decisions, and concept-level sign-off. This step does not edit that module.
- **Publication contract:** Preserve `plan_tool/concept_sync.py:synchronize_concepts` as the guarded publication boundary. `original_tree` remains the compare-and-swap snapshot; the reviewed candidate carries intended changes.
- **CLI payload:** Preserve `plan_tool/cli/scope_review_cmd.py:_decision` and the rule that every repeated `--concept` has exactly one matching `--decision`.
- **Durability limit:** Operator approval proves that the requested accounting was reviewed. It does not prove that replacement detail output exists, so a pending include must retain its prior non-delivery record until step 4 completes regeneration.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add pure helpers for comparing reviewed record meaning, distinguishing routing-only changes, and applying approval preservation or invalidation.
  - `plan_tool/concept_sync.py` — add shared transition preparation, validate pending include states, and make rendering and scope mapping use the still-effective parked disposition until delivery becomes durable.
  - `plan_tool/cli/scope_review_cmd.py` — review new or replaced records explicitly, persist reviewed pending include requests, and refuse unattended approval where operator input is required.
  - `tests/test_concept_tree.py` — cover semantic comparison, routing comparison, approval preservation, and approval invalidation.
  - `tests/test_concept_sync.py` — cover the transition table, pending include publication, validation order, and no-write failures.
  - `tests/cli/test_scope_review_cmd.py` — cover interactive review, unattended refusal, resumable include requests, exit codes, and publication behavior.

## Implementation

The foundational logic is a **non-delivery transition predicate**: compare the original and proposed concept decision plus its structured records, then classify the change as unchanged, review-required, pending delivery, or invalid.

- **Keep comparison and transformation write-free.** Put the record-level comparison helpers beside the step-2 record contract in `plan_tool/concept_tree.py`. They should return copied values or classifications and must not call `save_concepts()`.

- **Compare reviewed meaning separately from routing.**
  - Treat concept ID, disposition, rationale, immutable origin reference, and any other step-2 field that states why the work is not delivered as operator-reviewed meaning.
  - Treat current artifact reference and linked step IDs as routing fields. A routing-only change may preserve approval only when a lifecycle operation supplies and validates an exact rename, split, merge, or renumber mapping.
  - Treat an arbitrary routing edit with no validated mapping as review-required. This prevents callers from disguising a semantic replacement as a file move.
  - Preserve the record ID rules owned by step 2; this step must not mint a new identity for a routing-only update.

- **Centralize the transition table.** Add one public, write-free preparation surface in `plan_tool/concept_sync.py` near `_accepted_decisions()`, `render_scope_decisions()`, and `_mapped_scopes()`. A name such as `prepare_non_delivery_transition` is reasonable. It should validate the complete requested scope before returning a candidate so one bad item cannot partially change the input.

- **Return explicit transition information.** The preparation result should let callers distinguish:
  - an unchanged approved state;
  - a candidate that needs operator review;
  - a reviewed pending include that still needs durable regeneration;
  - an invalid or conflicting request.

  One approach is a small frozen result type containing the copied candidate and the concept or record IDs in each category. Avoid an opaque in-memory approval token that step 4 could not recover after the command exits.

- **Apply the parked-decision rules.**
  - `include → defer` and `include → wont_do` require a complete step-2 record. Create it as unapproved, collect the required rationale and references from the operator, and approve it only after explicit review.
  - `defer → wont_do` and `wont_do → defer` replace the old semantic record. Reused rationale or references do not carry approval across the disposition change.
  - An unchanged parked decision with unchanged reviewed meaning preserves approval and record identity.
  - A changed rationale, origin, or other reviewed semantic field clears approval and requires review.
  - A validated routing-only remap preserves approval and identity. An unproven routing edit does not.

- **Represent include as a resumable pending transition.** For `defer|wont_do → include`, persist the reviewed concept-level `include` request while retaining the approved prior non-delivery record. This relation is the durable pending state that step 4 can discover from the sidecar after the `scope-review` command exits.

- **Keep the parked plan effect while include is pending.** Update `plan_tool/concept_sync.py:render_scope_decisions()` and `_mapped_scopes()` so an approved `include` decision with a retained approved non-delivery record continues to render and map according to that record’s `defer` or `wont_do` disposition. Do not publish committed scope or remove parked Markdown until step 4 removes the record after durable regeneration.

- **Reject ambiguous pending states.** A pending include is invalid when the retained approved records disagree on disposition, identify the wrong concept, or otherwise fail the step-2 publication validator. Multiple records for the same concept are valid only when they agree on the effective parked disposition.

- **Do not use rejection as the pending-state mechanism.** `synchronize_concepts()` must be able to publish the reviewed pending request to the sidecar while leaving the plan’s effective scope and parked section unchanged. A no-write rejection would make the request undiscoverable to step 4.

- **Enforce the policy at publication.** Before `synchronize_concepts()` calls `_mapped_scopes()`, `render_scope_decisions()`, `_fingerprint()`, or either `Publisher`, validate the original-to-candidate transition. A direct caller must not bypass approval invalidation or publish an unreviewed replacement.

- **Keep compare-and-swap roles separate.** Compare current durable state with `original_tree`, not the reviewed candidate. Use the candidate only to derive the intended decision, records, and effective plan state.

- **Preserve synchronization ordering.** Continue rendering the complete candidate plan, calculating `plan_tool/concept_sync.py:_fingerprint` over the rendered plan and ordered detail files, placing that fingerprint on the final tree, validating the tree, and then publishing through the existing rollback path.

- **Review every changed record explicitly.** In `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, show the disposition, rationale, immutable origin, current artifact reference, and linked step IDs for every new or semantically replaced record. A small injected prompt helper is one reasonable approach and keeps tests independent of a real terminal.

- **Collect complete records before sign-off.** If an `include → defer|wont_do` request has no matching record, prompt for the fields required by step 2 or refuse the request. Do not invent an artifact or origin reference from the concept title or plan prose.

- **Sign off after the accounting review.** Call `plan_tool/concept_review.py:review_concept_scope()` with `sign_off=True` only after every review-required record in the requested scope has been completed and confirmed. A declined, interrupted, incomplete, or invalid review writes nothing.

- **Keep unattended behavior honest.** If stdin is not a TTY, refuse any request that needs new operator approval and print the exact `scope-review` command that can resume the same concept and decision scope. An unchanged approved record needs no new sign-off. If a future `--yes` value reaches this command, it must not forge record approval.

- **Preserve failure mapping.** Keep `SCOPE_REVIEW_CONFLICT_EXIT` for source divergence and mapping conflicts. Use `SCOPE_REVIEW_INVALID_STATE_EXIT` for malformed records, incomplete review, ambiguous pending state, and unattended requests that require approval. Retain the existing distinction between a confirmed no-write failure and `ConceptSyncResult.rollback_error`.

## Tests

- `test_reviewed_record_comparison_covers_semantic_fields` — changes to disposition, rationale, origin, or other reviewed meaning require renewed approval.
- `test_routing_only_comparison_is_distinct_from_semantic_change` — artifact and linked-step changes are classified as routing changes.
- `test_validated_routing_remap_preserves_record_identity_and_approval` — an exact lifecycle mapping changes routing without changing reviewed meaning.
- `test_unproven_routing_edit_requires_review` — arbitrary routing edits cannot retain approval.
- `test_unchanged_non_delivery_record_preserves_approval` — the same decision and record remain approved.
- `test_parked_disposition_change_clears_approval` — `defer ↔ wont_do` cannot inherit approval.
- `test_include_to_parked_requires_complete_record` — a parked request with missing step-2 evidence is invalid.
- `test_include_to_parked_can_be_approved_after_review` — a complete confirmed record and matching concept decision form a valid candidate.
- `test_parked_to_include_prepares_pending_transition` — an approved include request retains the prior approved non-delivery record.
- `test_pending_include_keeps_effective_parked_scope` — step scope and parked Markdown remain deferred or out of scope while the record exists.
- `test_pending_include_is_durable_and_resumable` — the synchronized sidecar contains enough state for step 4 to discover the request after reload.
- `test_pending_include_rejects_conflicting_dispositions` — inconsistent retained records fail before publication.
- `test_transition_scope_preserves_unselected_accounting` — concepts and records outside the requested scope remain unchanged.
- `test_invalid_transition_does_not_mutate_inputs` — whole-scope validation returns no partial candidate.
- `test_sync_rejects_bypassed_unreviewed_replacement_without_writes` — direct publication cannot evade the transition policy.
- `test_sync_publishes_pending_include_without_committing_plan_scope` — the sidecar records the request while the plan keeps its current parked effect.
- `test_sync_transition_publication_preserves_fingerprint_order` — accepted transitions retain the established render and fingerprint sequence.
- `test_sync_transition_publication_failure_rolls_back` — transition handling preserves existing restoration behavior.
- `test_scope_review_prompts_for_every_changed_record` — the CLI presents all reviewed fields and signs off only after confirmation.
- `test_scope_review_decline_writes_nothing` — declining record review leaves the plan and sidecar unchanged.
- `test_scope_review_non_tty_refuses_new_approval` — unattended execution returns invalid state, prints a resumable command, and writes nothing.
- `test_scope_review_unchanged_approval_needs_no_prompt` — an unchanged approved record is not signed again.
- `test_scope_review_include_persists_pending_request` — the command records the approved include intent without removing prior accounting.
- `test_scope_review_pending_include_reports_regeneration_next_step` — success output tells the operator that delivery remains parked pending regeneration.
- `test_scope_review_transition_success_publishes_consistent_artifacts` — an approved transition produces a matching plan and concept sidecar.

### Test-creation order (feature step)

Add the semantic-versus-routing comparison cases in `tests/test_concept_tree.py` with the pure helpers. Add the complete transition table, pending include behavior, and publication guards in `tests/test_concept_sync.py` with the preparation surface. Add the interactive, non-TTY, and resumability cases in `tests/cli/test_scope_review_cmd.py` with the CLI gate. Every new test and all existing focused tests in these three files must be green before this step is considered finished.

## Acceptance criteria

- An unchanged approved parked decision and unchanged reviewed record preserve approval and record identity.
- Changing a parked disposition or reviewed semantic field clears approval and requires explicit operator review.
- A validated artifact or linked-step remap preserves approval and identity; an arbitrary routing edit does not.
- `include → defer|wont_do` cannot publish without a complete matching step-2 record.
- `defer|wont_do → include` persists a reviewed pending request while retaining its approved non-delivery record.
- A pending include continues to render and map to its prior parked disposition until the record is removed after durable regeneration.
- Reloading the sidecar preserves enough pending state for step 4 to identify the requested include transition without another CLI payload.
- Conflicting retained dispositions or invalid record links fail before either artifact is written.
- `plan_tool/concept_sync.py:synchronize_concepts` rejects unreviewed or bypassed semantic replacements.
- Non-TTY execution cannot approve new or changed accounting and prints a runnable resume command.
- Declined or incomplete interactive review leaves the plan and concept sidecar unchanged.
- Successful publication retains the fingerprint, compare-and-swap, rollback, and status behavior of `synchronize_concepts()`.
- All focused tests in `tests/test_concept_tree.py`, `tests/test_concept_sync.py`, and `tests/cli/test_scope_review_cmd.py` pass.

## References

- [JSON Schema Validation Draft 2020-12](https://json-schema.org/draft/2020-12/json-schema-validation) — Use its conditional-validation model when defining valid combinations of decisions, record dispositions, and approval state.
- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Use its copying and validation guidance when preparing complete candidates without mutating the source snapshot.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use parametrization for the decision and record-field transition matrices.

## Deferred

- **Removal after durable regeneration** — step 4 updates `plan_tool/detail.py:generate_detail()` so successful replacement detail publication removes the retained non-delivery record and makes the pending `include` effective.
- **Completeness findings** — step 5 updates `plan_tool/review.py:check_concept_coverage()` and reporting surfaces for missing, dangling, unsigned, or contradictory accounting.
- **Split and merge routing transforms** — steps 6 and 7 supply the validated exact mappings that allow `artifact_ref` and `linked_step_ids` changes to preserve approval.
- **Scope-out production of reviewed records** — step 8 replaces `plan_tool/scope_out.py:_prepare_concept_narrow_update()` direct sign-off with this transition contract.
- **Seed production and restoration** — steps 9 through 11 carry and restore the reviewed accounting state through re-baseline, carved seeds, and create.
- **Lifecycle-wide integration coverage** — step 12 exercises the complete transition sequence after the implementation steps land.
