> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Require bounded prose for new candidate additions and preserve removal, feedback stripping, and legacy replay

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend candidate `add-row` operations with a bounded row-owned prose amendment in `plan_tool/roadmap_candidate.py`. Use the append rule supplied by step 1 when materializing changed artifact bodies, while leaving remove and replace operations without prose capability. Preserve batch feedback stripping and immutable replay in `plan_tool/roadmap_candidate_run.py`. On green, eligible new rows can clear the unchanged prose gate, and stored candidates remain reproducible.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the candidate contract change.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — The current gap between added rows and prose validation.
- [Input](#input) — Upstream append behavior and current immutable-candidate contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test edits.
- [Implementation](#implementation) — Candidate admission, assembly, stripping, and replay rules.
- [Tests](#tests) — Focused regression coverage for the changed contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Current contract and implementation anchors.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this feature.
- [Deferred](#deferred) — Adjacent work owned by later steps.

## Why

`plan_tool/roadmap_candidate.py:materialize_candidate()` can add a typed row while retaining its predecessor body, so `plan_tool/roadmap_gates.py:check_inventory_has_prose()` rejects otherwise valid additions as undescribed. Candidate additions need a bounded, row-linked fragment that becomes part of the immutable artifact body, without giving candidates general body-editing authority or changing the existing review lifecycle.

## Input

- **Step 1 append rule:** Step 1 provides the reusable append-spacing behavior from `plan_tool/roadmap_revision_patch.py:_apply_stage_prose_amendments()`. Consume that rule for candidate additions rather than copying its separator logic.
- **Candidate envelope:** `plan_tool/roadmap_candidate.py:CandidateDelta`, `CandidateAddRow`, `parse_candidate_delta()`, and `_operation_diagnostics()` define the closed model response contract.
- **Candidate replay:** `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence._requires_normalized_operations()` reparses stored normalized operations, and `_require_reproducible_batch_operations()` rebuilds batch artifacts from them.
- **Artifact gate:** `plan_tool/roadmap_gates.py:check_inventory_has_prose()` remains the final check that every inventoried row id appears in artifact body prose.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — add and validate the add-row prose-amendment payload, append admitted fragments during candidate assembly, and retain immutable operation serialization.
  - `plan_tool/roadmap_candidate_run.py` — preserve normalized-operation reparsing and reproducible batch replay for amendments.
  - `tests/test_roadmap_candidate.py` — cover candidate parsing, validation, body assembly, gate success, removal behavior, and feedback stripping.
  - `tests/test_roadmap_candidate_run.py` — cover stored-evidence replay and legacy evidence compatibility.

## Implementation

- **Limit the new field to additions.** Extend `CandidateAddRow` and `ADD_ROW_REQUIRED_KEYS` with one row-owned amendment record. `CandidateReplaceRow` and `CandidateRemoveRow` must retain their current closed shapes and must not accept prose fields.

- **Match the existing prose policy.** Use `plan_tool/roadmap_artifacts.py:stage_row_operation_policy()` to require an amendment for prose-enabled added row types and reject it for identity-only types. The amendment must name the added row id, contain nonblank text, and contain that id as a whole identifier using the same boundary rule as `plan_tool/roadmap_revision.py:contains_whole_row_id()`.

- **Enforce the fixed fragment limit.** Measure each fragment as UTF-8 bytes and reject one above `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES`. Do not use the configurable stage-feedback limits or the stage route’s per-feedback operation limit.

- **Keep authority on the parent operation.** `CandidateAddRow.feedback_id` remains the only reviewer binding for its amendment. `_validate_operation_authority()` must continue to admit multiple valid additions for one batch reviewer item.

- **Append only admitted new-row prose.** In the `materialize_candidate()` path, apply each eligible amendment to its target artifact body in `_prepare_operations()`’s normalized order, using the reusable step-1 append rule. Preserve predecessor body text other than the required append separators and fragments.

- **Preserve existing non-addition behavior.** `_apply_operation()` and the assembly flow must retain current typed replacement and removal behavior. A removal must not require, delete, or otherwise infer prose.

- **Keep feedback out of immutable batch artifacts.** `_assemble_candidate_artifacts(..., feedback_free=True)` must still remove reviewer-owned collections before rendering. An unchanged member already free of those collections must keep its stored bytes rather than being re-rendered.

- **Bind replay to the amended operation.** Keep prose amendments in the normalized operation wire form used by `_operations_wire_for_reparse()`, `CandidateProposalEvidence`, and `_require_reproducible_batch_operations()`. Replaying stored batch evidence must reproduce the exact candidate artifact bytes and operation classification.

- **Keep selector-era evidence compatible.** Evidence written before normalized batch operations remain valid and render back to their existing canonical bytes. Do not add absent batch-only fields to legacy records.

## Tests

### Tests for this step

- `test_candidate_add_row_requires_row_owned_prose_amendment` — asserts an eligible added row is refused when its amendment is absent.
- `test_candidate_add_row_rejects_invalid_row_owned_prose_amendment` — asserts a non-prose-enabled row, mismatched row id, blank fragment, partial-id fragment, and over-limit fragment are each refused.
- `test_candidate_add_row_accepts_multiple_amendments_for_one_reviewer_item` — asserts multiple eligible additions bound to one admitted feedback item remain valid and append in normalized operation order.
- `test_candidate_materialization_appends_row_prose_and_clears_undescribed_row_gate` — asserts added Domain and Components rows appear in body prose and the unchanged complete gate is clean.
- `test_candidate_remove_row_does_not_accept_or_require_prose_amendment` — asserts removals retain their current closed operation contract and body behavior.
- `test_candidate_materializes_feedback_free_batch_artifacts_and_response_patch` — retain or adapt coverage that batch candidates strip feedback and removals while preserving the response patch.
- `test_batch_candidate_retains_the_verified_bytes_of_an_unchanged_feedback_free_member` — retains the exact-byte rule for unchanged feedback-free members.
- `test_batch_candidate_replay_reproduces_amended_artifact_bytes` — asserts stored normalized operations with amendments reparse and recreate the persisted batch artifacts without a backend call.
- `test_pre_change_gate_clean_candidate_evidence_replays_with_existing_identity` — retains selector-era evidence replay and canonical-byte compatibility.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Eligible `add-row` operations require exactly one valid row-owned prose amendment.
- Non-prose-enabled additions reject an amendment, and replace and remove operations do not gain prose fields.
- Each accepted fragment is nonblank, names its added row id as a whole identifier, and is at most `HARD_MAX_PROSE_AMENDMENT_BYTES` UTF-8 bytes.
- Candidate assembly appends accepted fragments in normalized operation order and the unchanged `undescribed-row` gate sees each added row id.
- A batch can carry multiple valid additions and amendments for one admitted reviewer item.
- Batch artifact assembly still strips reviewer-owned collections and preserves stored bytes for unchanged feedback-free members.
- Replaying stored amended batch evidence reproduces its artifact bytes, while pre-change selector-era evidence retains its existing identity and serialized form.
- `tests/test_roadmap_candidate.py` and `tests/test_roadmap_candidate_run.py` pass.

## References

- [BUG_BACKLOG.md — Read “Structural candidates cannot satisfy described-row gates for newly added rows” for the candidate amendment contract and regression cases.](BUG_BACKLOG.md)
- [plan_tool/roadmap_candidate.py — Read `CandidateAddRow`, `materialize_candidate()`, `_prepare_operations()`, and `_assemble_candidate_artifacts()` for candidate admission and assembly.](plan_tool/roadmap_candidate.py)
- [plan_tool/roadmap_candidate_run.py — Read `CandidateProposalEvidence` and `_require_reproducible_batch_operations()` for persisted-operation replay.](plan_tool/roadmap_candidate_run.py)
- [plan_tool/roadmap_revision.py — Read `contains_whole_row_id()` for the established whole-id rule.](plan_tool/roadmap_revision.py)
- [plan_tool/roadmap_gates.py — Read `check_inventory_has_prose()` for the unchanged gate this work must satisfy.](plan_tool/roadmap_gates.py)
- [plan_tool/project_config.py — Read `HARD_MAX_PROSE_AMENDMENT_BYTES` for the fixed fragment ceiling.](plan_tool/project_config.py)

## Applicable guardrails

- **The plan’s “## Out of scope”, prose amendment boundary:** Limit candidate prose to eligible additions and append-only fragments; do not add general body editing or prose behavior for replacements or removals.
- **The plan’s “## Out of scope”, prose-gate enforcement:** Keep `undescribed-row` unchanged and satisfy it through admitted artifact content.
- **The plan’s “## Out of scope”, candidate authority and lifecycle:** Preserve reviewer binding, ledger behavior, accepted-head selection, seed effects, and correction diagnostics.
- **The plan’s “## Architecture”, batch cardinality boundary:** Do not add a per-feedback material-operation cap to batch candidate additions.

## Deferred

- Structural review disclosure and stack-digest binding for amendments — step 3 owns review-visible amendment records.
- Proposal and retry prompt instructions for amendments — step 4 owns model-facing contract guidance.
- Replacement-span and removal-prose semantics — remain outside this plan’s candidate-addition boundary.
