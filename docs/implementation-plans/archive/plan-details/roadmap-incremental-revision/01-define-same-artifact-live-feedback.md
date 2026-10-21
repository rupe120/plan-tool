> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define the same-artifact live-feedback selector, render-canonical preflight, closed text-field table, and two-operation revision schema

## Summary

Add `plan_tool/roadmap_revision.py` as the pure contract for selecting one feedback row, proving its artifact can be safely re-rendered, and parsing the bounded response format. Define the allowed text fields by roadmap row type and return immutable preflight data that later steps can use for prompt construction and merging. Update `ROADMAP_FORMAT.md` with the local revision format contract and extend its drift guard in `tests/test_roadmap_format.py`. Green means the selector, preflight, field table, and response schema reject every unsupported local revision before any future writer or backend call.

## Table of Contents

- [Summary](#summary) — The scope and green result for this contract step.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why local feedback needs a stricter contract than broad re-entry.
- [Input](#input) — Existing artifact, stage, and feedback contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New contract files and format-reference edits.
- [Implementation](#implementation) — Selector, preflight, field-table, and response-schema rules.
- [Tests](#tests) — Unit and documentation-drift coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Strict-model configuration reference.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Later-step work and a separate shared-parser refactor.

## Why

`plan_tool/roadmap.py:_render_revision_prompt` and `_active_feedback_block` treat broad re-entry as a full-stage revision and send every open request as guidance. The code has no local contract that selects one live row, limits which presentation field may change, or proves that parsing and rendering an edited artifact will not drop data. This step establishes that boundary before a merger or command can turn a routine feedback response into an unbounded revision.

## Input

- **Stage identity:** `plan_tool/roadmap.py:STAGES` and `RoadmapStage.artifact_key` are the source for the accepted artifact tokens. The new module must receive that stage-derived token set rather than create a second token-to-path or token-to-parser mapping.

- **Artifact shape and rendering:** `plan_tool/roadmap_artifacts.py` exposes the four artifact dataclasses, their `parse_*_artifact` and `render_*_artifact` pairs, `FeedbackRow`, `FeedbackTarget`, `RemovalRecord`, and the fixed renderer comments in `_render`. The preflight must use the selected stage’s parser and renderer as a pair.

- **Feedback validity:** `plan_tool/roadmap.py:_check_predecessor_review_rows` and `plan_tool/roadmap_gates.py:design_row_ids` establish the current meaning of a resolvable retained feedback target: a live design row or a recorded removal. The local selector is stricter for its selected row: it requires one live row, not a historical removal.

- **Response-model precedent:** `plan_tool/schema.py:Step` shows the project’s strict Pydantic configuration pattern. The local operation records need the same closed-field behavior, but remain a separate response contract.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_revision.py` — Pure selector, render-canonical preflight, text-field table, prompt-context value, and strict operation parser.
  - `tests/test_roadmap_revision.py` — Unit coverage for the complete local revision contract.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Extend the source-of-truth banner and add the local revision selector, canonical-input, field-table, and JSON operation contract. Keep command workflow and broad-reentry guidance for step 5.
  - `tests/test_roadmap_format.py` — Add a documentation drift guard that compares the documented local field table and operation example with `plan_tool/roadmap_revision.py`.

## Implementation

- **Keep the stage mapping single-sourced.** Add `parse_feedback_selector` in `plan_tool/roadmap_revision.py` to split `<artifact-token>:<feedback-id>` at its first colon, reject empty or colon-bearing feedback ids, and accept only artifact keys supplied from `plan_tool/roadmap.py:STAGES`. Do not add a second token-to-path, token-to-parser, or token-to-renderer table in the new module.

- **Keep this module pure.** Expose immutable selector and preflight values, such as `FeedbackSelector` and `RevisionPreflight`, without reading paths, writing files, invoking a backend, or importing `plan_tool/roadmap.py` or CLI code. A later caller supplies the selected stage’s parser and renderer and owns path resolution.

- **Select one eligible feedback row.** `preflight_feedback_revision` should parse the selected artifact, find exactly one matching feedback id, and require that row to be `open`, have no `proposed_response`, target `kind: row`, and point to exactly one live design row in the same artifact. Count matching rows before selecting: `plan_tool/roadmap_gates.py:design_row_ids` is useful for membership but its set result cannot detect duplicate target ids.

- **Validate every retained feedback row.** Reject duplicate feedback ids and unresolved retained row targets before a selected row can proceed. Continue to allow retained artifact-wide feedback and retained targets recorded in `RemovalRecord`; they follow the broad review contract. Apply the no-existing-response rule only to the selected row, so an unselected reopened `open` row can retain its earlier response unchanged.

- **Require render-canonical input.** Parse the loaded text, render the parsed artifact with the matching `render_*_artifact` function, and require exact text equality. Do not strip comments, normalize whitespace, or separately ban comments: `plan_tool/roadmap_artifacts.py:_render` deliberately emits `_FEEDBACK_KEY_COMMENT` for an artifact carrying feedback, and that exact generated comment is canonical. Reject any input the renderer would change or drop.

- **Make the field table closed and type-owned.** Publish one module-level table, such as `TEXT_FIELDS_BY_ROW_TYPE`, with exactly these entries:

  | Row collection | Allowed presentation fields |
  |---|---|
  | `entities` | `name` |
  | `business_rules` | `statement` |
  | `workflows` | `name` |
  | `decisions` | `rationale` |
  | `dispositions` | none |
  | `constraints` | `statement` |
  | `system_patterns` | `name`, `statement` |
  | `component_patterns` | `name`, `statement` |
  | `components` | `name` |
  | `plans` | `title`, `sizing_rationale` |
  | `assumptions` | `statement` |

  Treat every field outside this table as immutable. `FieldRow` and `OrderingEntry` are not targetable design rows, and a disposition row deliberately has no patchable field.

- **Define bounded prompt data, not a prompt template.** Have the preflight result expose only the selected feedback identity, request, and state; artifact token; target row identity and collection; allowed fields with current values; and an immutable summary of the target’s non-patchable relation data. Do not include another feedback row, another design row, artifact prose, or an upstream artifact. Step 4 owns rendering `plan_tool/prompts/roadmap-feedback-revision.md`.

- **Parse only the two permitted operations.** Add `parse_revision_operations` for one unfenced JSON object with exactly the `operations` key. Reject prefixes, fences, trailing data, JSON Lines, duplicate JSON keys, unknown root keys, and non-object or non-array shapes before model validation.

- **Use strict closed records.** Model the envelope and records with strict Pydantic configuration that forbids extra fields. Accept an optional first `replace-row-presentation` record containing only `op`, `row_id`, `field`, and `value`, followed by exactly one final `respond-feedback` record containing only `op`, `feedback_id`, and `proposed_response`.

- **Make replacement an explicit one-field delta.** A replacement names the selected row and one field from that row type’s table. It does not carry a replacement row or imply a value for omitted fields. Reject mismatched identities, duplicate replacements or responses, unallowlisted fields, and non-string, blank, or surrounding-whitespace values rather than silently changing the reply.

- **Document code-owned names.** Update the `ROADMAP_FORMAT.md` source-of-truth banner to name `plan_tool/roadmap_revision.py` as the local revision contract owner. Document the selector grammar, render-canonical requirement, selected-versus-retained feedback distinction, field table, and operation schema with an executable JSON example; do not duplicate future CLI or publication behavior.

## Tests

### Tests for this step

Every listed test must be green before this step is complete.

- `tests/test_roadmap_revision.py::test_selector_accepts_each_stage_artifact_key` — Accepts each key supplied by `plan_tool/roadmap.py:STAGES`.

- `tests/test_roadmap_revision.py::test_selector_rejects_missing_unknown_empty_and_colon_bearing_parts` — Rejects malformed selector forms without choosing an artifact.

- `tests/test_roadmap_revision.py::test_preflight_selects_one_open_response_less_live_row` — Returns the selected feedback, row type, allowed fields, and bounded prompt data only for an eligible same-artifact target.

- `tests/test_roadmap_revision.py::test_preflight_rejects_duplicate_feedback_and_duplicate_live_target_ids` — Refuses ambiguous feedback or target-row selection.

- `tests/test_roadmap_revision.py::test_preflight_rejects_non_open_artifact_removed_and_reopened_selected_feedback` — Refuses every selected-row state or target outside the local contract.

- `tests/test_roadmap_revision.py::test_preflight_checks_retained_feedback_without_rejecting_an_unselected_reopened_row` — Rejects dangling retained targets while preserving the broad lifecycle rule for unselected feedback.

- `tests/test_roadmap_revision.py::test_preflight_requires_exact_parser_renderer_round_trip` — Rejects unknown data, changed formatting, and changed comments while accepting the renderer’s fixed feedback guidance comment.

- `tests/test_roadmap_revision.py::test_text_field_table_covers_every_targetable_row_type` — Pins every allowed field and confirms dispositions, fields, and ordering entries are not patch targets.

- `tests/test_roadmap_revision.py::test_operations_require_optional_replacement_then_one_final_response` — Accepts the two legal operation counts and ordering only.

- `tests/test_roadmap_revision.py::test_operations_reject_non_json_framing_duplicate_keys_and_unknown_fields` — Rejects fences, preambles, trailing data, JSON Lines, duplicate keys, and closed-schema violations.

- `tests/test_roadmap_revision.py::test_operations_bind_to_selected_ids_and_one_allowed_field` — Rejects identity mismatches, unsupported fields, duplicate records, and blank or untrimmed values.

- `tests/test_roadmap_format.py::test_local_revision_reference_matches_the_contract_module` — Verifies the documented field table and JSON operation example match `plan_tool/roadmap_revision.py`.

## Acceptance criteria

- `plan_tool/roadmap_revision.py` exposes a pure selector and preflight contract that takes stage-derived artifact keys rather than duplicating `plan_tool/roadmap.py:STAGES`.

- A selector reaches preflight only when it identifies one known artifact token and one colon-free feedback id.

- Preflight accepts only an exactly rendered artifact with one selected `open`, response-less, row-targeted feedback row and one live target row in that artifact.

- Preflight checks all retained feedback for broad target validity, while leaving an unselected reopened row with its prior response eligible to remain unchanged.

- The fixed renderer feedback guidance comment passes canonical preflight only in the exact form emitted by `plan_tool/roadmap_artifacts.py:_render`.

- The closed text-field table permits only the row collections and scalar fields listed in this detail; all relation, identity, membership, decision-state, prose, and unlisted fields remain outside the local contract.

- The operation parser accepts only the optional one-field presentation replacement followed by one selected-feedback response, with strict identity, ordering, field, and nonempty trimmed-string checks.

- `ROADMAP_FORMAT.md`, `tests/test_roadmap_format.py`, and every test in `tests/test_roadmap_revision.py` are green.

## References

- [Pydantic Configuration API](https://docs.pydantic.dev/latest/api/config/) — Use `ConfigDict` settings to make the local operation records strict and reject extra fields.

## Applicable guardrails

- **The plan’s “## Overview”, bounded local revision:** Keep this module limited to one selected canonical artifact and its selected feedback row; do not give the contract a multi-artifact selection path.

- **The plan’s “## Out of scope”, structural and relation changes:** Make the closed field table the only mutation surface the response schema can name. Do not add a structural operation record or an escape hatch for relation-bearing changes.

- **The plan’s “## Out of scope”, prose and format migration:** Use render-canonical preflight to refuse data or formatting the current renderer cannot preserve. Do not add a lossless extension or prose-editing format.

- **The plan’s “## Out of scope”, publication and recovery behavior:** Keep filesystem mutation, writer coordination, seed invalidation, publication, and recovery outside this module for step 3.

- **The plan’s “## Out of scope”, roadmap-derived seeds:** Do not read, regenerate, promote, refresh, or otherwise mutate seed state in this step.

## Deferred

- `plan_tool/roadmap_revision_patch.py` — Step 2 owns applying the parsed operations, preserving every unselected artifact value, and validating the candidate.

- `plan_tool/roadmap_revision_publish.py` — Step 3 owns seed-state invalidation, writer serialization, and atomic publication.

- `plan_tool/roadmap_revision_run.py` and `plan_tool/prompts/roadmap-feedback-revision.md` — Step 4 owns the exclusive command, bounded backend context rendering, and one-request execution.

- `README.md`, `docs/cli/roadmap.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `CAPABILITIES.md` — Step 5 owns the operator workflow and broad-reentry boundary documentation.

- `plan_tool/concept_tree.py:_reject_duplicate_keys` — This module has a similar duplicate-JSON-key check but a different response and error contract. Any shared helper needs a separately scoped refactor; keep the local rejection rule independent here.
