> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Parse and merge one single-field target-row replacement and one feedback response

## Summary

Add `plan_tool/roadmap_revision_patch.py` as the pure merger for the selection and operation records that step 1 supplies. Extend `plan_tool/roadmap_artifacts.py` with the narrow typed reconstruction support the merger needs, and pin its preservation behavior in `tests/test_roadmap_artifacts.py`. The key decision is to merge immutable typed artifact rows, never generic YAML mappings or raw backend text. Green means one optional allowed field replacement and one selected feedback response produce a typed one-artifact candidate while every other artifact value remains unchanged.

## Table of Contents

- [Summary](#summary) — The step’s outcome and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing local patch boundary.
- [Input](#input) — Contracts from step 1 and existing artifact types.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step creates or changes.
- [Implementation](#implementation) — Merger rules, preservation requirements, and module boundaries.
- [Tests](#tests) — Unit coverage for typed replacement and rejection paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Strict response-model reference.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that bind this merger.
- [Deferred](#deferred) — Later validation, publication, and command work.

## Why

`plan_tool/roadmap_artifacts.py` can parse and render complete artifacts, but it has no bounded operation that changes one selected presentation field and answers one selected feedback row. Broad revision behavior in `plan_tool/roadmap.py:_render_revision_prompt` works on whole artifacts, so it cannot safely serve the local-feedback mode without a separate typed merger. This step creates that boundary before any command can turn a backend reply into a candidate artifact.

## Input

- **Step 1 contract:** Step 1 supplies the selected same-artifact feedback and target-row context, the allowed-field table, and parsed two-operation response records from `plan_tool/roadmap_revision.py`. Consume those typed values; do not add a second raw-JSON parser or a second field-table definition.

- **Artifact shape:** `plan_tool/roadmap_artifacts.py:DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, and `PlansArtifact` hold frozen, ordered row tuples and the prose `body`. Their row dataclasses, including `FeedbackRow` and `FeedbackTarget`, are the values the merger must preserve or replace.

- **Feedback lifecycle:** `plan_tool/roadmap_artifacts.py:FeedbackState` defines the only state value this merger may set on the selected row. `FeedbackRow.id`, `FeedbackRow.target`, and `FeedbackRow.request` remain reviewer-owned source data.

- **Later validation:** `plan_tool/roadmap.py:RoadmapStage` and `STAGES` own stage parsers, renderers, and gate sets. This step returns a typed candidate only; step 3 supplies candidate serialization, re-parsing, and gate validation.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_revision_patch.py` — Pure operation-to-candidate merger and merge-specific rejection surface.
  - `tests/test_roadmap_revision_patch.py` — Unit tests for allowed updates, preservation, and rejected operations.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add the typed artifact reconstruction support needed to replace one existing design row without rebuilding artifacts as untyped mappings.
  - `tests/test_roadmap_artifacts.py` — Test the reconstruction support beside the existing artifact fixtures and parse/render round-trip coverage.

## Implementation

- **Foundational logic:** Provide one public merger in `plan_tool/roadmap_revision_patch.py` that accepts the step-1 selection plus its parsed operations and returns one candidate artifact. It may change only the selected target row’s one permitted text field, when a replacement operation exists, and the selected feedback row’s state and proposed response.

- **Keep parsing separate from merging:** Use the closed operation records from `plan_tool/roadmap_revision.py`; reject mismatched selected row or feedback identities at the merger boundary, but do not parse raw JSON, strip prose, or reinterpret operation ordering here.

- **Rebuild typed values:** Use the frozen row and artifact types in `plan_tool/roadmap_artifacts.py` to replace only the selected row and selected feedback entry while retaining tuple order. A direct `dataclasses.replace`-style reconstruction is a suitable approach if it keeps every untouched value intact.

- **Preserve the selected row’s non-presentation data:** A replacement updates only the field the step-1 table permits for that row type. Keep its id, relation-bearing fields, collection membership, and every other field unchanged.

- **Preserve feedback ownership:** Set the selected `FeedbackRow` from `FeedbackState.OPEN` to `FeedbackState.AWAITING_REVIEW` and add the returned nonempty response. Keep that row’s id, target, and request unchanged. Leave every unselected feedback row, including other open rows, exactly as loaded.

- **Preserve artifact content:** Keep all unselected design rows, removals, and the artifact `body` unchanged. Do not add, remove, sort, or normalize rows, and do not turn the artifact into YAML during merging.

- **Reject unsupported patch shapes:** Return a merge-specific failure for an operation that does not name the selected row or feedback, uses a disallowed field, attempts an update outside the bounded pair, or lacks the required feedback response. The failure must identify the relevant row or feedback id without exposing reviewer text.

- **Keep module boundaries narrow:** `plan_tool/roadmap_revision_patch.py` stays in-memory and does not write files, load artifacts, invoke gates, discover paths, or import `plan_tool/roadmap.py` or `plan_tool/roadmap_gates.py`. Step 3 owns candidate validation and publication.

## Tests

### Tests for this step

- `test_replace_design_row_rebuilds_only_the_selected_tuple_entry` — `tests/test_roadmap_artifacts.py` proves the artifact helper preserves row order, sibling rows, review collections, and prose.
- `test_replace_design_row_handles_each_supported_artifact_shape` — `tests/test_roadmap_artifacts.py` covers the four artifact dataclasses without converting rows to untyped mappings.
- `test_merge_replacement_and_response_updates_the_selected_pair` — `tests/test_roadmap_revision_patch.py` proves one allowed presentation replacement and one feedback response produce the expected candidate.
- `test_merge_response_without_replacement_keeps_the_target_row_unchanged` — `tests/test_roadmap_revision_patch.py` proves the optional replacement does not imply a row edit.
- `test_merge_accepts_every_allowed_target_field` — `tests/test_roadmap_revision_patch.py` parameterizes the step-1 field table and proves each permitted field updates only itself.
- `test_merge_rejects_a_row_id_other_than_the_selected_target` — `tests/test_roadmap_revision_patch.py` proves the backend cannot redirect the replacement.
- `test_merge_rejects_a_feedback_id_other_than_the_selected_feedback` — `tests/test_roadmap_revision_patch.py` proves the backend cannot answer another request.
- `test_merge_rejects_a_disallowed_or_non_targetable_field` — `tests/test_roadmap_revision_patch.py` proves structural and no-field row types cannot become local patches.
- `test_merge_requires_the_selected_feedback_response` — `tests/test_roadmap_revision_patch.py` proves a target-row replacement cannot publish without an answer.
- `test_merge_preserves_unselected_feedback_and_artifact_prose` — `tests/test_roadmap_revision_patch.py` proves other feedback state, reviewer-owned fields, removals, relations, and body bytes stay unchanged.
- `test_merge_does_not_mutate_the_loaded_artifact` — `tests/test_roadmap_revision_patch.py` proves the candidate is separate from the selected source artifact.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A valid selected replacement and response return a typed candidate with only the allowed target field, selected feedback state, and selected proposed response changed.
- A valid response with no replacement leaves the selected target row unchanged.
- Every non-selected row, feedback record, removal record, relation, identifier, and prose body compares unchanged between the source artifact and candidate.
- A row-id mismatch, feedback-id mismatch, disallowed field, or incomplete operation set is rejected without returning a candidate.
- `tests/test_roadmap_artifacts.py` and `tests/test_roadmap_revision_patch.py` pass.

## References

- [Pydantic Configuration API](https://docs.pydantic.dev/latest/api/config/) — Read the strict-model rules that step 1 uses for the closed operation records this merger consumes.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded local revision:** Change only the selected same-artifact row and feedback response; preserve all other canonical content.

- **The plan’s “## Step intent”, selector-owned identities:** Enforce that both operations belong to the already selected target row and feedback row.

- **The plan’s “## Out of scope”, excluded revision shapes:** Do not expand this merger into structural editing, cross-artifact work, prose editing, persistence, seed handling, recovery, or command behavior.

## Deferred

- Candidate serialization, re-parsing, upstream-envelope construction, and gate execution — Step 3 owns validation and publication of the candidate.
- CLI selection, backend invocation, and run-log outcomes — Step 4 owns the command surface and one-attempt behavior.
- Consolidating `plan_tool/roadmap_gates.py:StageArtifact` with any patch-module type alias — this would widen a focused merger into a cross-module refactor.
