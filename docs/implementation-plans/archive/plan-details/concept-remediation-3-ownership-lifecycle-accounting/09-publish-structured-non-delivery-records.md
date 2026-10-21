# Step 9 — Publish reviewed non-delivery records during scope-out

## Summary

This step makes `plan_tool/scope_out.py:scope_out_step()` publish structured non-delivery records when a carve removes a concept’s final committed owner. It replaces the direct sign-off in `plan_tool/scope_out.py:_prepare_concept_narrow_update()` with the review and transition contract delivered by steps 2 and 3. The key design decision is that `--yes` may skip the carve confirmation but may not approve a new non-delivery record; approval requires explicit interactive review. On green, a successful carve publishes the narrowed plan and approved accounting together, while recommend-only, unattended, declined, stale, and failed paths leave both unchanged.

## Table of Contents

- [Summary](#summary) — The scope-out accounting change and observable result.
- [Why](#why) — Why the current automatic deferral is not valid lifecycle accounting.
- [Input](#input) — The durable record and transition contracts consumed from dependencies.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test changes.
- [Implementation](#implementation) — Final-owner detection, review, publication, and rollback rules.
- [Tests](#tests) — Unit and CLI cases for reviewed and refused scope-out operations.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Primary documentation relevant to persisted models and test matrices.
- [Deferred](#deferred) — Seed-envelope and CLI wording work owned elsewhere.

## Why

`plan_tool/scope_out.py:_prepare_concept_narrow_update()` currently changes every ownerless carved concept to `defer` by calling `plan_tool/concept_review.py:review_concept_scope()` with `sign_off=True`. That records a concept-level decision without the structured rationale, artifact reference, and record-specific approval required by steps 2 and 3, and it lets `--yes` claim operator approval without a review. Scope-out must instead use the shared transition policy, require explicit review when final ownership is lost, and publish the reviewed record through the existing stale-check and rollback boundary.

## Input

- **Step 2 output:** Consume the durable non-delivery record on `plan_tool/concept_tree.py:ConceptTree`, including its stable identity, concept ID, disposition, rationale or evidence, artifact reference, optional routing link, and review state. Do not define another scope-out-specific persisted shape.
- **Step 3 output:** Use step 3’s public non-delivery transition preparation and approval contract. Scope-out must not reproduce its rules for preserving approval, clearing approval, or validating `include → defer`.
- **Ownership snapshot:** `plan_tool/scope_out.py:NarrowPreview.new_steps` is the proposed survivor set. Only exact `Step.concept_ids` links on committed survivors count as delivery ownership.
- **Scope-out transaction:** `plan_tool/scope_out.py:_ConceptNarrowUpdate` carries the original sidecar snapshot and prepared candidate into `apply_narrow()`. Preserve the original snapshot as the stale-state and rollback authority.
- **Forward artifact:** `plan_tool/scope_out.py:_carved_seed_path()` and `_carved_region_seed_path()` select the durable artifact that receives the carved work. Its repo-relative path is the natural stable artifact reference for records created by this operation.
- **Verification limit:** This step can prove that the selected seed was written before the plan and sidecar publication begins. It cannot prove that the carved work is later re-planned or delivered.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — prepare complete non-delivery records for concepts losing their final committed owner, require explicit review, and publish the reviewed candidate through the existing narrow transaction.
  - `plan_tool/cli/convergence_cmd.py` — replace unattended `-y` actuation guidance with the exact interactive resume command when accounting review is required.
  - `tests/test_scope_out.py` — cover record preparation, approval gates, surviving owners, stale state, publication failure, and rollback.
  - `tests/cli/test_scope_out_cmd.py` — cover interactive application and unattended refusal through the real CLI dispatch path.
  - `tests/cli/test_convergence_cmd.py` — cover the same refusal and resume guidance through convergence actuation.

## Implementation

The foundational logic is a **final-owner transition gate**: a carve may publish only when each concept losing its final committed owner has an approved structured `defer` record tied to the carved seed.

- **Keep exact final-owner detection.** Retain `plan_tool/scope_out.py:ownerless_carved_concept_ids()` as the scope-out entry point to the shared accounting helper delivered by step 1. Preserve first-authored order, one result per concept, many-owner support, and the rule that parked survivors are not committed owners.

- **Replace direct sign-off.** Change `plan_tool/scope_out.py:_prepare_concept_narrow_update()` so it no longer calls `plan_tool/concept_review.py:review_concept_scope()` with unconditional `sign_off=True`. Use step 3’s shared transition preparation for every ownerless concept and let that contract create or replace an initially unapproved `defer` record.

- **Build complete records from real scope-out evidence.**
  - Use the exact stable concept ID selected by final-owner detection.
  - Use `defer` as the scope-out disposition; scope-out must not infer `wont_do`.
  - Use the selected carved seed’s repo-relative path as the stable `artifact_ref`.
  - Require non-empty rationale or evidence and show it during review. One reasonable approach is to seed the review with the carved step titles and let the operator confirm or replace the rationale.
  - Do not choose an arbitrary `source_step_id` when a concept has several carved owners. Leave an optional routing link unset unless the shared step-2 contract provides an unambiguous representation for the whole carved region.

- **Select one seed identity for the operation.** Determine the collision-safe path through `plan_tool/scope_out.py:_carved_seed_path()` or `_carved_region_seed_path()` before preparing the records, then reuse that same path for record preparation and the later write. Do not call the path selector twice, because an existing seed or concurrent filesystem change could produce different references.

- **Keep recommendation paths write-free.** A graph blocker, `allow_scope_out=False`, a declined carve confirmation, or an incomplete accounting review must write no seed, plan, detail move, or concept sidecar. Read-only validation may still reject a malformed or stale sidecar rather than hiding an invalid source state.

- **Separate the two confirmations.** `plan_tool/scope_out.py:_confirm_scope_out()` answers whether the operator wants the structural carve. The step-3 review workflow answers whether the operator approves each new or changed non-delivery record. Skipping the first confirmation must never imply approval of the second.

- **Treat `--yes` as carve consent only.** If no concept loses its final owner, preserve the existing non-interactive apply behavior. If any record needs approval, a non-TTY or unattended `yes=True` call must refuse before writing and print an exact interactive scope-out command that resumes the same step or `N..M` region without `-y`.

- **Update both operator surfaces.** `plan_tool/cli/scope_out_cmd.py:render_scope_out_result` and `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` must distinguish carve consent from accounting review, avoid saying `-y` can complete a review-required carve, and emit the same exact interactive resume command.

- **Approve only after showing every reviewed field.** On an interactive run, show each affected concept’s disposition, rationale or evidence, and artifact reference. A declined, interrupted, or incomplete review returns without mutation and leaves any existing approval unchanged.

- **Prepare the whole candidate before publication.** Validate every ownerless concept and its record before writing the seed. One bad concept must reject the entire carve; do not publish records for a subset.

- **Publish through the prerequisite authority.** After all reviews succeed, submit the carved seed, narrowed plan, detail moves/archives, rendered scope prose, and reviewed concept candidate as one typed scope-out bundle through the prerequisite publication API. Do not write the seed first or retain a local competing transaction.

- **Preserve stale checks through typed compare-and-swap.** Carry `_ConceptNarrowUpdate.original_sidecar_text`, plan fingerprint, seed-target absence, detail sources/targets, and every current artifact digest into the prerequisite authority. Its durable journal and common restored-failure/rollback-failed results replace `apply_narrow()`’s local publication journal.

- **Refresh only the final fingerprint.** After writing the narrowed plan, copy the reviewed candidate, update its `plan_fingerprint` from the narrowed plan, and save it through the existing concept-sidecar writer. Do not change stable non-delivery record identity during this refresh.

- **Report common publication outcomes.** A recoverable failure restores the original plan, detail layout, sidecar, and seed absence. A rollback-failed result reports every uncertain path. No failure path deliberately retains a seed orphan outside the reviewed concept generation.

- **Keep caller compatibility.** `plan_tool/cli/scope_out_cmd.py:cmd_scope_out()` and `plan_tool/cli/convergence_cmd.py:_actuate_scope_out()` both call `scope_out_step()`. Prefer keeping its existing arguments and `ScopeOutResult` outcomes so neither caller needs production changes in this step; put any new prompt behavior behind the existing `prompt_fn` seam.

- **Do not add seed accounting serialization here.** This step makes the sidecar record point to the carved seed. Step 10 owns the machine-readable accounting envelope inside `render_carved_seed()` and `render_carved_region_seed()`.

## Tests

- `test_scope_out_prepares_non_delivery_record_for_final_owner` — a sole carved owner produces one complete `defer` record tied to the selected seed.
- `test_scope_out_preserves_shared_concept_without_new_record` — a committed surviving owner prevents a new non-delivery transition.
- `test_scope_out_region_deduplicates_non_delivery_records` — several carved owners of one concept produce one record in first-authored order.
- `test_scope_out_parked_survivor_does_not_count_as_delivery` — a parked survivor still requires non-delivery accounting.
- `test_scope_out_record_uses_written_seed_artifact_ref` — the approved record and actual single-step seed use the same repo-relative path.
- `test_scope_out_region_record_uses_written_region_seed_artifact_ref` — all affected concepts point to the one region seed that was written.
- `test_scope_out_review_shows_every_approved_field` — interactive review displays disposition, rationale or evidence, and artifact reference before approval.
- `test_scope_out_declined_accounting_review_writes_nothing` — declining record review leaves the seed, plan, details, and sidecar unchanged.
- `test_scope_out_interrupted_accounting_review_writes_nothing` — EOF or interrupt cannot leave a partially approved candidate.
- `test_scope_out_yes_without_ownerless_concepts_still_applies` — unattended apply remains available when no new approval is needed.
- `test_scope_out_yes_cannot_approve_non_delivery_record` — `yes=True` with an ownerless concept refuses before mutation and prints an interactive retry command.
- `test_scope_out_non_tty_review_required_writes_nothing` — non-TTY execution cannot approve a new record even when structural apply is enabled.
- `test_scope_out_invalid_record_rejects_entire_region` — one invalid ownerless concept prevents all seed and publication writes.
- `test_scope_out_stale_sidecar_refuses_before_seed_write` — changed source accounting cannot be published from an old preparation snapshot.
- `test_scope_out_publication_failure_restores_original_accounting` — a concept save failure restores the plan, details, and original sidecar while retaining only the seed.
- `test_scope_out_success_publishes_narrow_and_approved_records` — the narrowed plan and refreshed sidecar contain consistent final ownership accounting.
- `tests/cli/test_scope_out_cmd.py::TestScopeOutThroughCLI::test_apply_interactive_publishes_approved_non_delivery_record` — the real command publishes reviewed accounting for a sole owner.
- `tests/cli/test_scope_out_cmd.py::TestScopeOutThroughCLI::test_apply_yes_refuses_when_non_delivery_review_is_required` — `--apply -y` returns without mutation and prints the exact interactive resume command.
- `tests/cli/test_scope_out_cmd.py::TestScopeOutThroughCLI::test_apply_yes_keeps_shared_concept_included` — shared ownership still permits unattended scope-out without creating a record.
- `tests/cli/test_scope_out_cmd.py::TestScopeOutThroughCLI::test_through_reviews_only_concepts_without_external_owner` — a region carve reviews only concepts whose final committed owners are inside the region.

### Test-creation order (feature step)

Add the pure final-owner and record-preparation tests with the `plan_tool/scope_out.py:_prepare_concept_narrow_update()` change. Add the interactive, `yes`, non-TTY, decline, and interruption cases with the review gate. Add publication, stale-state, and rollback cases before changing the apply sequence, then finish with the real CLI cases in `tests/cli/test_scope_out_cmd.py`. Every new test and the existing focused scope-out suite must be green before this step is considered finished.

## Acceptance criteria

- Carving the final committed owner of a reviewed concept prepares exactly one structured `defer` record for that concept.
- A committed surviving owner prevents creation of a scope-out non-delivery record.
- Multiple carved owners of the same concept produce one record, not duplicates.
- Every scope-out record contains the exact concept ID, `defer` disposition, non-empty rationale or evidence, the selected seed artifact reference, and approved review state.
- The record’s `artifact_ref` points to the exact seed path written by the successful operation.
- `--apply -y` continues to work when no non-delivery approval is required.
- `--apply -y` and non-TTY execution cannot approve a new or changed non-delivery record.
- An unattended refusal prints an exact command for retrying the same single-step or region carve interactively.
- A declined or interrupted accounting review writes no seed, plan, detail, or sidecar changes.
- A successful interactive carve writes the seed before publishing the narrowed plan and approved sidecar.
- A stale plan or sidecar is rejected before publication.
- A recoverable failure restores the original plan, detail layout, concept sidecar, and seed absence; rollback failure reports every uncertain path.
- The final concept sidecar fingerprint identifies the narrowed plan without changing stable non-delivery record IDs.
- Focused tests in `tests/test_scope_out.py` and `tests/cli/test_scope_out_cmd.py` pass.

## References

- [Pydantic Models](https://docs.pydantic.dev/latest/concepts/models/) — Read for copying, validating, and serializing the dependency-owned persisted record without weakening its field contract.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for the sole-owner, shared-owner, region, TTY, and approval-state matrices.

## Deferred

- Machine-readable accounting inside carved seeds — step 11 owns changes to `plan_tool/scope_out.py:render_carved_seed()` and `render_carved_region_seed()`.
- Restoration of carved accounting during create — step 12 owns parsing and reviewing the seed envelope.
- General publication mechanics — this step consumes the prerequisite authority and changes only scope-out preparation, review, caller wiring, and operator guidance.
