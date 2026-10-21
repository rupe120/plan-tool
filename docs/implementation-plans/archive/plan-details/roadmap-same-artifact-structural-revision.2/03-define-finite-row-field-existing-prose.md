> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Define finite row-field and existing prose-region rewrite operations

## Summary

Create `plan_tool/roadmap_structural_operations.py` and `tests/test_roadmap_structural_operations.py` for the closed V1 rewrite reply contract. The module parses one duplicate-free JSON envelope, binds every operation to step 2’s selected artifact and target row, and validates reusable metadata for one existing prose region. The key design decision is to express edits as finite scalar-field and pre-marked-region replacements, never as rows, mappings, relations, or a generic patch language. On green, downstream code receives only validated operations whose targets and scalar encodings are safe to splice into the selected canonical artifact.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why structural rewrites need a closed contract.
- [Input](#input) — Current evidence and artifact contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Envelope, allowlist, scalar, and region rules.
- [Tests](#tests) — Focused contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Strict JSON and model-validation references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this contract.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/roadmap_revision.py:parse_revision_operations` supports the narrower local-feedback path, including a decision-rationale replacement that this structural path must never admit. Step 2 supplies one current selected artifact, feedback row, and target row, but there is no contract yet that turns a backend reply into finite, uniquely targeted rewrite instructions. This step closes that gap before a raw-text merger can change canonical bytes.

## Input

- **Selected rewrite context:** Step 2 returns the current selected stage, canonical artifact text, parsed artifact, target collection, and live target row from `plan_tool/roadmap_structural_revision.py`. Bind every accepted operation to that context; do not accept a selector or discover another row.

- **Artifact shape:** `plan_tool/roadmap_artifacts.py:design_row_collections` defines the existing row collections, while the `render_*_artifact` functions define the YAML rendering behavior scalar replacements must match.

- **Stage rendering:** `plan_tool/roadmap.py:RoadmapStage` carries the selected artifact’s parser and renderer. Use its current renderer behavior for scalar admission rather than inventing quoting or multiline rules.

- **Local-revision precedent:** `plan_tool/roadmap_revision.py:parse_revision_operations`, `_decode_single_json_object`, and `_require_trimmed_text` show the existing strict JSON and text-validation shape. Keep this structural grammar separate because its root fields, discriminators, and allowed field surface differ.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_structural_operations.py` — Add the strict V1 envelope parser, finite row-field allowlist, reusable prose-region parser, and typed accepted-operation result.
  - `tests/test_roadmap_structural_operations.py` — Add fixture-based contract tests for accepted and rejected rewrite envelopes.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Parse and bind one finite V1 rewrite envelope to the exact selected row and any already-marked prose region in step 2’s current artifact.

- **Expose one closed parser boundary.** Provide a public parser and frozen result records, such as `parse_structural_revision_operations`, `RowFieldOperation`, and `ProseRegionOperation`. A row-field result carries the validated raw value and its renderer-derived replacement-scalar fragment. Accept raw reply text plus the accepted step-2 context; return validated operations and the single feedback response without writing, invoking a backend, or changing an artifact.

- **Require the exact V1 root shape.** Accept one unfenced JSON object with exactly `version`, `operations`, and `feedback_response`. Require native integer `1`, one nonblank string feedback response, and a nonempty operation array; V1 rejects a response-only envelope. Reject a string, float, boolean, unknown version, missing key, extra key, prefix, fence, trailing data, JSON Lines, and non-standard JSON constants.

- **Reject duplicate members at every nesting level.** Decode with a duplicate-member check before model validation, following `plan_tool/roadmap_revision.py:_decode_single_json_object`. Do not rely on ordinary JSON object construction, which would silently keep one duplicate value.

- **Use strict discriminated operation records.** Model `kind: "row-field"` with exactly `collection`, `row_id`, `field`, and `value`; model `kind: "prose-region"` with exactly `region_id` and `value`. Forbid extra members and wrong types in the root and every operation record.

- **Keep the row-field surface finite and structural-only.** Define a module-owned allowlist for the permitted collection-field pairs in the plan’s `## Architecture`. Require the operation collection and row id to equal step 2’s selected target, then require the field to be listed for that collection. Exclude `decisions.rationale` and every disposition field even though `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE` permits the separate local-revision path to name decision rationale.

- **Validate and retain scalar replacements through renderer behavior.** Require row-field values and `feedback_response` to be strings with no CR or LF, at least one non-whitespace character, and no surrounding whitespace. Admit each value only when the current YAML rendering configuration emits one physical scalar mapping line for that field. Derive and retain the exact scalar fragment from that rendered mapping so step 4 never splices the raw JSON value; do not infer safety from character checks alone.

- **Allow several distinct row-field operations but no repeated target.** Treat `(collection, row_id, field)` as a unique target. Reject duplicate targets rather than relying on last-write-wins behavior.

- **Parse prose markers from the artifact body only.** Make the marker grammar reusable by step 4’s raw-text merger so it does not grow a second parser. Validate standalone opening and closing delimiter lines, the plan-defined region-id grammar, unique ids, pairing, and non-nesting. An operation must name one uniquely found existing region in the selected artifact.

- **Refuse unbounded prose regions.** Reject markerless artifacts, unknown or ambiguous region ids, malformed or nested delimiters, and a region that covers the body except whitespace. Preserve the delimiter lines as region metadata; step 4 owns replacing only the interior.

- **Keep prose content deliberately less restricted than scalars.** Allow empty or multiline prose-region values, but reject a value that introduces a rewrite-region delimiter line. This permits rewriting a legitimate interior while preserving the predecessor’s marker inventory.

- **Limit prose-operation count.** Accept at most one prose-region operation in an envelope and reject repeated region targets. Do not impose an operation ordering rule that the plan does not define; later span application must use validated, non-overlapping targets.

- **Keep candidate construction out of this module.** Do not locate final YAML spans, mutate feedback state, re-render an artifact, or claim candidate canonicality here. `plan_tool/roadmap_revision_patch.py:merge_feedback_revision` remains the typed local-revision merger; step 4 owns structural raw-text splicing, and step 5 owns candidate proof.

## Tests

### Tests for this step

- `test_v1_envelope_accepts_selected_row_fields_region_and_feedback_response` — Accepts a valid V1 envelope bound to the step-2 target, including distinct row-field operations and one existing prose region.

- `test_v1_envelope_rejects_noncanonical_root_version_and_framing` — Rejects missing or extra root members, every non-integer or unsupported version, empty operations, fences, prefixes, trailing data, JSON Lines, and non-standard constants.

- `test_v1_envelope_rejects_duplicate_members_at_root_and_operation_depth` — Rejects duplicate JSON names before closed-model validation can discard one value.

- `test_row_field_allowlist_accepts_every_structural_collection_field_pair` — Pins every allowed row-field pair and proves each binds to the selected collection and row id.

- `test_row_field_rejects_decision_rationale_and_every_unlisted_target` — Proves the structural path cannot reuse the local-revision decision-rationale exception or target another collection, row, or field.

- `test_row_field_rejects_duplicate_target_and_invalid_scalar_value` — Rejects repeated field targets, blank or untrimmed values, and CR/LF-containing values.

- `test_row_field_scalar_admission_uses_current_yaml_renderer_shape` — Accepts a safely rendered one-line scalar and rejects values whose current YAML rendering would require another physical form.

- `test_row_field_scalar_admission_retains_renderer_fragment` — Proves values such as `"true"` retain the renderer-quoted scalar fragment required for a canonical row-field replacement.

- `test_feedback_response_requires_one_trimmed_single_line_renderer_safe_value` — Rejects blank, untrimmed, multiline, non-string, or non-single-line-renderable response values.

- `test_prose_region_accepts_one_existing_non_full_body_interior` — Returns region metadata only for a unique, valid marker pair in the selected artifact body.

- `test_prose_region_rejects_markerless_unknown_duplicate_nested_malformed_and_full_body_regions` — Refuses every region lookup that lacks one eligible existing interior.

- `test_prose_region_allows_multiline_or_empty_interior_without_delimiters` — Preserves the deliberate allowance for empty and multiline prose replacements.

- `test_prose_region_rejects_replacement_text_that_introduces_delimiter_lines` — Rejects content that would change the marker inventory.

- `test_envelope_rejects_multiple_prose_operations_and_repeated_region_targets` — Enforces the finite prose-operation limit without silently choosing one operation.

Green-before-done gate: `uv run pytest tests/test_roadmap_structural_operations.py -q` passes.

## Acceptance criteria

- The new parser accepts only one duplicate-free V1 JSON object with the declared root members, a nonempty operation list, and one selected-feedback response.

- Every accepted row-field operation names the step-2 selected row and a collection-field pair from the structural allowlist.

- `decisions.rationale`, every disposition field, and every identity-, relation-, decision-, or collection-changing surface remain unrepresentable by an accepted operation.

- Row-field values and feedback responses are nonblank, trimmed, newline-free strings that the current YAML renderer can emit as one physical scalar line, and every accepted row-field operation retains its renderer-derived replacement fragment.

- A prose operation can target only one valid existing, non-full-body marker region in the selected artifact, and its value cannot introduce delimiter lines.

- `plan_tool/roadmap_structural_operations.py` does not write files, render or splice a candidate, invoke a backend, or alter step 2’s accepted context.

- `uv run pytest tests/test_roadmap_structural_operations.py -q` passes.

## References

- [Pydantic Configuration](https://docs.pydantic.dev/latest/api/config/) — Use strict frozen models with forbidden extra fields for the closed envelope.

- [Pydantic Discriminated Unions](https://docs.pydantic.dev/latest/concepts/unions/#discriminated-unions) — Validate the finite `kind`-tagged operation set.

- [Python json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html#json.load) — Use decoder hooks to reject duplicate members and non-standard constants.

- [RFC 8259 — The JavaScript Object Notation Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html#section-4) — Follow the unique-member requirement for interoperable JSON objects.

## Applicable guardrails

- **The plan’s intent, selected-artifact boundary:** Bind every accepted operation to step 2’s one selected artifact and row; do not expose another artifact or feedback target.

- **The plan’s step intent, finite rewrite boundary:** Keep backend output limited to selected scalar fields and pre-existing prose interiors that the parser can validate.

- **The plan’s `## Out of scope`, structural-change boundary:** Do not add operation shapes that can express identity, relation, decision, row, marker, or file changes.

- **The plan’s `## Out of scope`, schema and revision-mode boundary:** Leave canonical artifact schemas and the existing local-revision contract unchanged while introducing this separate structural contract.

## Deferred

- **Raw span splicing and selected-feedback transition** — Step 4 owns changing exact canonical source spans and moving the selected feedback row to its review state.

- **Candidate preservation and full-roadmap gate proof** — Step 5 owns comparing the completed candidate with its predecessor and evaluating candidate gate contexts.

- **Candidate-aware semantic-impact classification** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` routes this broader analysis to BACKLOG #289.

- **Generic operation-parser consolidation** — Keep `plan_tool/roadmap_revision.py:parse_revision_operations` separate because its local-revision envelope has a different contract; a shared patch-language refactor exceeds this step’s file set.
