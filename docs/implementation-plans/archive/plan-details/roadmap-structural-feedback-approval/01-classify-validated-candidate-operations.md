> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Classify validated candidate operations, keeping row removals and semantic changes inert and structural while reusing the existing presentation-field rules

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add a deterministic classification of validated `CandidateDeltaOperation` values in `plan_tool/roadmap_candidate.py`. The classifier distinguishes presentation-only replacements from structural additions, removals, ordering changes, and replacements that alter any non-presentation field. Reuse `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` as the sole presentation-field policy. On green, `tests/test_roadmap_candidate.py` proves that classification is stable, does not grant new authority, and leaves every result inert.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the classifier and its outcome.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why relation-only review detection is too narrow.
- [Input](#input) — Validated candidate operations and the presentation policy this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files changed by this step.
- [Implementation](#implementation) — Classification rules, boundaries, and integration point.
- [Tests](#tests) — Focused coverage for the new operation classes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts governing candidate and feedback behavior.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep classification inert.
- [Deferred](#deferred) — Lifecycle routing that later steps own.

## Why

`plan_tool/roadmap_candidate.py:materialize_candidate` currently identifies review-required work from declared relation impact, so a validated row removal or a replacement that changes meaning without changing a declared relation can remain a plain gate-clean candidate. The candidate boundary needs one deterministic answer to whether the validated operation set exceeds the existing local presentation surface, so later decision handling can route structural work without trusting model labels or changing canonical state during classification.

## Input

- **Validated operations only:** Classify the normalized operations returned by `plan_tool/roadmap_candidate.py:_prepare_operations` only after `plan_tool/roadmap_candidate.py:_validate_operation_authority` accepts them. Invalid, unauthorized, or gate-failing input must continue through the existing refusal path rather than receiving a structural classification.
- **Predecessor rows:** Compare a `CandidateReplaceRow` with its authorized predecessor row so the classifier can identify which fields actually changed.
- **Presentation policy:** Read `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` directly as the established local presentation surface. Its table, including the empty `dispositions` entry, defines the only fields a replacement may change without becoming structural.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py` — Add the typed, deterministic operation-set classification and apply it only after the existing candidate validation boundary.
  - `tests/test_roadmap_candidate.py` — Add focused cases for presentation-only, structural, invalid, and order-independent operation sets.

## Implementation

- **Classify the operation set, not model prose.** Add a small typed result or predicate near `CandidateDeltaOperation` and `CandidateDelta` that reports whether the complete normalized operation set is presentation-only or structural. Keep its result inert: it must not write artifacts, mutate feedback, advance `AcceptedRoadmapHead`, or itself approve a candidate.

- **Treat additions and removals as structural.** Every `CandidateAddRow` and `CandidateRemoveRow` exceeds the local presentation surface, including a plan operation with its inseparable `OrderingEntry`. A removal must remain structural even when complete-roadmap gates accept the resulting candidate.

- **Compare replacements field by field.** For `CandidateReplaceRow`, use the authorized predecessor row and its declared `row_type` to identify changed fields. A replacement is presentation-only only when every changed field belongs to `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` for that collection. An unchanged replacement is not structural.

- **Keep semantic changes structural.** A replacement that changes an id, relation, enum, decision state, ordering-related value, or any other field outside the presentation table must classify as structural. Do not infer meaning from a relation diff alone; declared-relation changes remain one structural example, not the full definition.

- **Reuse the existing policy without copying it.** Import or otherwise reference `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` rather than adding another field table in `plan_tool/roadmap_candidate.py`. The classifier must preserve the existing distinction that decisions may change `rationale` locally while fields such as `chosen_option` remain structural.

- **Preserve existing validation order.** Keep `plan_tool/roadmap_candidate.py:materialize_candidate`’s parsing, binding verification, `_prepare_operations`, `_validate_operation_authority`, application, relation-authority, rendering, and complete-roadmap-gate checks intact. Classification must consume validated typed operations and known predecessor data; it must not become a shortcut around any existing authority or gate.

- **Keep existing review-requirement behavior separate for now.** `plan_tool/roadmap_candidate.py:_has_reviewable_existing_row_relation_impact` and `_candidate_diff_requires_review_requirement` still own the current relation-impact review requirement. Do not broaden those lifecycle-facing predicates or modify `plan_tool/roadmap_candidate_run.py` or `plan_tool/roadmap_candidate_review.py` in this focused step; later steps consume the new classifier when they add the structural decision surface.

- **Make normalization irrelevant to the verdict.** Use the normalized operation set from `_prepare_operations`, and ensure equivalent input orders produce the same classification. The classifier must inspect every operation rather than stop after finding a presentation-only replacement.

## Tests

### Tests for this step

- `test_candidate_operation_set_with_only_allowed_presentation_fields_is_not_structural` — A replacement changing only a collection’s fields from `TEXT_FIELDS_BY_ROW_TYPE` is classified as presentation-only.
- `test_candidate_operation_set_with_a_non_presentation_replacement_is_structural` — A replacement changing a semantic field, such as a decision’s selected outcome, is structural even when no relation change is involved.
- `test_candidate_operation_set_with_row_addition_is_structural` — An authorized `CandidateAddRow` is structural.
- `test_candidate_operation_set_with_row_removal_is_structural` — An authorized `CandidateRemoveRow`, including the plan-and-ordering removal shape, is structural even when materialization remains gate-clean.
- `test_candidate_operation_set_with_no_changed_replacement_fields_is_not_structural` — Replacing a row with equivalent content does not create a false structural classification.
- `test_candidate_operation_classification_uses_existing_text_field_policy` — A decision rationale replacement remains presentation-only while a field outside `TEXT_FIELDS_BY_ROW_TYPE["decisions"]` is structural.
- `test_candidate_operation_classification_is_order_independent_after_normalization` — The same mixed operation set has the same structural result regardless of model-supplied order.
- `test_invalid_or_unauthorized_operations_are_not_classified_as_structural_candidates` — Existing invalid-delta and authority refusals occur before any candidate classification can be used.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A validated operation set containing any add-row or remove-row operation classifies as structural.
- A validated replacement classifies as presentation-only only when all changed fields are allowed by `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` for its row collection.
- A validated replacement that changes any field outside that table classifies as structural, even without a declared relation diff.
- Classification reads the normalized, validated operation set and produces the same result for equivalent operation orders.
- Invalid or unauthorized operations retain the existing refusal behavior and do not gain candidate or decision authority.
- The classifier performs no artifact writes, feedback mutation, accepted-head update, approval, or promotion.
- `tests/test_roadmap_candidate.py` passes with the focused classification coverage.

## References

- [Roadmap Structural Feedback Approval handoff — approved work order and prerequisite boundaries](../../../../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md)
- [ROADMAP_FORMAT.md — local presentation fields and immutable candidate outcome contract](../../../../../ROADMAP_FORMAT.md)
- [DATA_CONTRACT.md — persisted candidate and review contracts](../../../../../DATA_CONTRACT.md)
- [ROADMAP_FEEDBACK_FORMAT.md — mutable ledger ownership and feedback lifecycle](../../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [plan_tool/roadmap_candidate.py — candidate operation validation and materialization boundary](../../../../../plan_tool/roadmap_candidate.py)
- [plan_tool/roadmap_revision.py — `TEXT_FIELDS_BY_ROW_TYPE`, the existing presentation-field policy](../../../../../plan_tool/roadmap_revision.py)

## Applicable guardrails

- **Plan intent, explicit approval gate:** This step may identify structural work but must not approve, promote, or otherwise advance it.
- **Plan scope guardrails, validated typed operations:** Classification may use only the existing candidate operation types and established stage policies; it must not create a user-authored structural flag or new operation authority.
- **Plan scope guardrails, canonical selector:** `AcceptedRoadmapHead` remains untouched by this step’s classifier and all candidate results remain inert.
- **Plan scope guardrails, reuse existing contracts:** Reuse the existing candidate boundary and presentation-field policy rather than adding a candidate store, lifecycle system, or second authority path.
- **Plan out of scope, structural operations:** Do not expand the operation vocabulary or attempt to validate structural changes outside the current full-roadmap gates and stage authority.

## Deferred

- **Structural decision routing and persistence** — Later steps must consume this inert classification to create, review, edit, reject, and promote the exact structural proposal; this step only establishes the validated-operation boundary.
- **Unifying relation-impact review with the broader structural classification** — Keep `plan_tool/roadmap_candidate.py:_has_reviewable_existing_row_relation_impact` and its downstream replay consumers unchanged until the lifecycle-facing step can update their complete contract together.
