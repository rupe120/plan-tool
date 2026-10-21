> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add three-state concept review and scoped sign-off

## Summary

Add `plan_tool/concept_review.py` as the domain layer for applying `include`, `defer`, and `wont_do` decisions to an explicit concept scope. Sign-off covers only the requested concepts and only when every concept in that scope has a complete decision against the current source state. Keep the operation deterministic and independent of terminal prompts or persistence; later CLI and synchronization steps will orchestrate those concerns. `tests/test_concept_review.py` proves that valid scoped reviews succeed while incomplete, stale, unknown, and out-of-scope changes leave the input record unchanged.

## Table of Contents

- [Summary](#summary) — The review layer and its observable result.
- [Why](#why) — Why concept decisions need scope-aware approval rules.
- [Input](#input) — The concept-tree and bootstrap contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files created by this step.
- [Implementation](#implementation) — Three-state updates, scope validation, and sign-off invariants.
- [Tests](#tests) — Unit coverage for successful and rejected review operations.
- [Acceptance criteria](#acceptance-criteria) — Checks that prove scoped sign-off is safe.
- [References](#references) — Primary documentation relevant to source-state digests.
- [Deferred](#deferred) — CLI, persistence, synchronization, and dependency work left to later steps.

## Why

Steps 1 and 3 provide a durable concept record and deterministic source-derived concepts, but neither defines how an operator may change decisions or approve part of the tree. Without one review authority, callers could invent different state vocabularies, approve concepts outside the requested scope, or retain approval after the source has changed. This step adds the foundational rule: **apply a complete three-state decision set to an explicit concept scope, and sign off only when that scope still matches the source state the reviewer saw**.

## Input

- **Step 1 — stable concept record:** Consume the concept tree, node identity, source linkage, three-state review fields, sign-off metadata, and integrity/source-state metadata established by step 1. Do not duplicate its persisted dataclasses, identifier generation, serialization, or fingerprint validation in `plan_tool/concept_review.py`.
- **Step 3 — deterministic bootstrap and re-derivation:** Consume the current tree produced or reconciled by step 3. Re-derivation conflicts remain step 3 outcomes; this step must not choose a winner or rewrite conflicted source identity.
- **Explicit scope:** Accept a concrete set of concept IDs. An empty scope, duplicate IDs, or an ID absent from the supplied tree is invalid rather than an implicit request for the whole tree.
- **Decision set:** Require exactly one requested state for every concept in scope. The accepted values are `include`, `defer`, and `wont_do`; missing, duplicate, unknown, or extra concept decisions make the request invalid.
- **Expected source state:** Require the caller to supply the source-state fingerprint or equivalent integrity value from the record it presented for review. Compare it with the current tree value before applying any change or sign-off.
- **Tree hierarchy:** Treat each node independently unless its descendants are explicitly included in the requested scope. Selecting a parent must not silently select or rewrite descendants.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/concept_review.py` — Define the pure scoped-review operation, its result or error vocabulary, and the sign-off validation rules.
  - `tests/test_concept_review.py` — Cover all three states, exact scope boundaries, source-state checks, sign-off completeness, and failure atomicity.

- **Existing files (edits only):**
  - None.

## Implementation

The foundational logic is: **validate the complete review request first, then apply and sign off exactly the selected concepts against the source state the reviewer saw**.

- **Keep this module at the domain boundary.** `plan_tool/concept_review.py` should accept an in-memory concept tree and return an updated tree or a typed outcome. It must not read or write the sidecar, parse Markdown, prompt on a terminal, or call a backend. Step 6 will provide CLI orchestration, while step 5 will own record-to-plan synchronization.
- **Expose one clear review entry point.** A public function such as `review_concept_scope(...)` is recommended. Its inputs should make the tree, explicit concept IDs, requested decisions, expected source state, and whether sign-off is requested visible rather than hiding them in ambient state.
- **Validate before mutation.** Check the source-state value, scope membership, one-decision-per-scoped-node rule, and three-state vocabulary before changing any node. Return or raise a specific stale-state, invalid-scope, or incomplete-review outcome so step 6 can map failures to stable CLI exits.
- **Apply all three states directly.** Preserve `include`, `defer`, and `wont_do` as distinct values. Do not collapse `wont_do` into `defer`, infer a state from ancestors, or add a fourth persisted “mixed” state.
- **Enforce exact scope.** Update only IDs in the requested scope. A decision for an unselected node is an error, not permission to widen the scope; nodes outside the scope must remain equal to their input values, including their review and sign-off metadata.
- **Require a complete scope for sign-off.** A sign-off request succeeds only when every scoped concept has exactly one valid final decision. Reject the whole operation if any selected concept is missing, duplicated, or otherwise unresolved.
- **Bind approval to current source state.** Compare the caller’s expected source-state value with the tree’s current value before applying decisions. A mismatch must produce a stale result and no updated record, even if the requested decisions happen to match existing states.
- **Invalidate approval when a decision changes.** If a scoped node changes from one review state to another, clear that node’s prior sign-off metadata before any new approval is applied. An unsigned review leaves changed nodes unsigned.
- **Sign only the selected scope.** Successful sign-off marks the scoped nodes according to the step 1 model and records the current source-state binding required by that model. It must not approve ancestors, descendants, siblings, or other nodes merely because they share a source section.
- **Preserve unchanged scoped approvals carefully.** Reapplying the same state without sign-off should not forge a new approval or timestamp. If the existing approval is already valid for the same decision and source state, preserving it is acceptable; any source or decision change must invalidate it.
- **Make failure atomic.** Prefer building validated replacements and returning a new tree over mutating the caller’s object in place. Whichever approach fits the step 1 dataclasses, every rejected request must leave the supplied tree observably unchanged.
- **Keep outcome categories usable by later callers.** A small typed result or exception set should distinguish success, invalid scope or decision input, incomplete scope, and stale source state. Do not assign CLI exit numbers here; `plan_tool/cli/scope_review_cmd.py` in step 6 owns that policy.
- **Do not add interactive navigation.** Input loops in `plan_tool/create.py:_ask_choice`, `_ask_yn`, and `_ask_int_list`, plus confirmation policy in `plan_tool/scope_out.py:_confirm_scope_out`, are presentation-layer examples only. Sharing or copying them into this pure review module would mix terminal behavior with the review rule.
- **Do not infer semantic dependencies.** Descendant or cross-concept dependency expansion would make an explicit scope unpredictable. The plan defers semantic dependency detection, so this step validates only the IDs the caller supplies.

## Tests

- `tests/test_concept_review.py:test_review_accepts_include_defer_and_wont_do` — applies each supported state without normalization or loss.
- `tests/test_concept_review.py:test_review_updates_only_selected_scope` — changes selected nodes while preserving all fields on unselected nodes.
- `tests/test_concept_review.py:test_parent_scope_does_not_include_descendants` — selecting a parent alone does not rewrite or sign its children.
- `tests/test_concept_review.py:test_unknown_scope_id_is_rejected_atomically` — rejects an ID absent from the tree and leaves the input unchanged.
- `tests/test_concept_review.py:test_empty_scope_is_rejected` — does not treat an empty selection as whole-tree review.
- `tests/test_concept_review.py:test_duplicate_scope_id_is_rejected` — rejects an ambiguous scope rather than silently removing duplicates.
- `tests/test_concept_review.py:test_unknown_review_state_is_rejected_atomically` — accepts only the three declared state values and drops no node.
- `tests/test_concept_review.py:test_decision_outside_scope_is_rejected` — prevents a decision payload from widening the requested scope.
- `tests/test_concept_review.py:test_incomplete_scope_cannot_be_signed_off` — rejects sign-off when any scoped concept lacks a decision.
- `tests/test_concept_review.py:test_stale_source_state_cannot_be_reviewed_or_signed_off` — rejects a mismatched expected source state before mutation.
- `tests/test_concept_review.py:test_signoff_marks_exactly_the_selected_scope` — approves every and only selected concept after complete validation.
- `tests/test_concept_review.py:test_state_change_invalidates_prior_signoff` — clears approval tied to an earlier decision before applying the changed state.
- `tests/test_concept_review.py:test_unsigned_review_does_not_forge_signoff` — applies valid decisions without creating approval metadata when sign-off was not requested.
- `tests/test_concept_review.py:test_reapplying_same_state_does_not_refresh_approval` — avoids creating or refreshing approval metadata for a no-op unsigned review.
- `tests/test_concept_review.py:test_rejected_review_leaves_input_tree_unchanged` — pins failure atomicity across invalid, incomplete, and stale requests.

### Test-creation order (feature step)

1. Add fixtures in `tests/test_concept_review.py` using the step 1 concept model and a tree containing parent, child, and sibling nodes.
2. Add the three-state and exact-scope success cases with the review implementation.
3. Add invalid-scope, invalid-state, extra-decision, and incomplete-sign-off cases before exposing the API to later steps.
4. Add stale-source and prior-approval invalidation cases with the sign-off implementation.
5. Add the failure-atomicity and no-op approval cases last to verify the complete operation.
6. Run all of `tests/test_concept_review.py`; every new test must be green before this step is considered finished.
7. Run `tests/test_concept_tree.py` and `tests/test_concept_bootstrap.py` as dependency regressions so review does not change persistence, identity, or re-derivation behavior.

## Acceptance criteria

- `plan_tool/concept_review.py` exposes a reusable in-memory operation for reviewing an explicit set of concept IDs.
- The operation accepts `include`, `defer`, and `wont_do` and rejects every other state.
- Every selected concept must have exactly one decision before its scope can be signed off.
- Empty, duplicate, unknown, incomplete, or widened scopes are rejected without changing the supplied tree.
- A source-state mismatch returns a distinct stale outcome and applies no decisions or sign-off.
- A successful review changes only nodes named by the explicit scope.
- Selecting a parent does not implicitly change or sign descendants.
- Changing a decision invalidates approval associated with its prior state.
- An unsigned review never creates sign-off metadata.
- Successful sign-off approves every and only concept in the selected scope against the current source state.
- `tests/test_concept_review.py`, `tests/test_concept_tree.py`, and `tests/test_concept_bootstrap.py` pass.

## References

- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3/library/hashlib.html) — Read for the deterministic digest behavior behind the source-state value that scoped sign-off validates.

## Deferred

- **Concept-record persistence** — Step 1 owns serialization, integrity validation, and atomic sidecar publication.
- **Bootstrap and re-derivation conflicts** — Step 3 owns source-derived tree updates and conflict detection.
- **Concept-to-plan synchronization** — Step 5 owns Markdown propagation, unrelated-body preservation, and divergent-edit conflicts.
- **Interactive review and CLI exit codes** — Step 6 owns prompting, command flags, persistence orchestration, and mapping typed review outcomes to process exits.
- **Automatic scope expansion from semantic dependencies** — The plan explicitly postpones dependency detection because it would weaken the exact-scope guarantee.
- **Transactional record-and-Markdown publication** — Cross-artifact recovery remains a plan-level deferred durability concern.
