# Step 3 — Widen candidate span issuance for shared narrative blocks

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step changes `plan_tool/roadmap_revision.py:project_row_owned_prose_spans` so a blank-line block that names several live rows is issued as one shared span. The span is bound to the full set of live rows the block names (its owning set). It is issued only when every row in that set is visible in the candidate context. `plan_tool/roadmap_candidate_context.py` carries the owning set through the capsule. Legacy capsules, whose spans have one `row_id` and no owning set, must still load unchanged. The local revision selector `_select_row_owned_prose_spans` stays narrow. On green, a shared Decisions-style paragraph becomes a correction target with no typed-row change, and a reference to a removed row neither joins the owning set nor is required of it.

## Table of Contents

- [Why](#why) — the one-owner rule blocks correcting shared paragraphs
- [Input](#input) — step 1's contract and the current span and capsule shapes
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files touched
- [Implementation](#implementation) — owning-set rule, span identity, capsule carriage, compatibility
- [Tests](#tests) — cases pinning the rule and its carve-outs
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — work left to other steps

## Why

`project_row_owned_prose_spans` skips any block that names a second live row, and `StageProseSpan` carries exactly one `row_id`. A stale paragraph that names several rows therefore never reaches the candidate context, so no correction can target it. Step 1 defines the shared span and its owning set in `ROADMAP_FORMAT.md`. This step makes the candidate context issue spans to match that contract. Later steps consume the issued span for the operation, the splice, and the gate state.

## Input

- **Step 1 contract:** the owning-set, authority-binding, and removed-row rules come from `ROADMAP_FORMAT.md` § "Reviewer feedback and candidate lifecycle". Read the landed text first. Where this detail and the doc disagree, the doc wins on the contract and this step follows it.
- **Current issuance:** the function builds `live_rows` from `_design_rows_by_collection(artifact)` and `live_ids` from those rows. It marks a selected id unambiguous only when it appears once among live rows. It walks `_prose_blocks(artifact.body)` and issues a span only when exactly one unambiguous selected id matches via `contains_whole_row_id` and no other live id matches.
- **Span identity today:** `stage_prose_span_id(row_id, text)` hashes `row_id`, a NUL, and the text, and returns `row-prose-<sha256>`. `plan_tool/roadmap_revision_patch.py` recomputes it in its span check (`span.span_id != stage_prose_span_id(span.row_id, span.text)`). Single-owner ids must stay exactly as they are, or stored capsules and that check break.
- **Capsule today:** `CandidateContextSourceSpan` and `CandidateContextSourceSpanReceipt` carry `{row_id, span_id, text/digest}` under a frozen, `extra="forbid"` base. `_full_members_and_inventory` calls the projection with the full-member ids and groups results by `span.row_id`. `_source_span_facts` converts a span. The wire form is built through `_wire_value(member.source_spans)`. The same `source_spans` attribute is also read in `plan_tool/roadmap_candidate_run.py` and `plan_tool/roadmap_candidate_review.py`.
- **Removed rows:** `live_ids` is built only from live design rows. Removal records (`artifact.removals`) are never part of it, so a removed id in a block is not a live row today.
- **Limit on verification:** the new operation that consumes shared spans does not exist yet (step 4 onward). This step can only prove issuance and capsule round-trips.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_revision.py`: add the owning-set field and shared identity to the span, and widen `project_row_owned_prose_spans`.
  - `plan_tool/roadmap_candidate_context.py`: carry the owning set on the source-span record and receipt, and thread it through the member build and wire form.
  - `tests/test_roadmap_revision.py`: projection cases.
  - `tests/test_roadmap_candidate_context.py`: capsule carriage and legacy-load cases.

## Implementation

- **Owning set rule:** for each block, the owning set is every live row id the block names (whole-token match). Removed-row ids are not live, so they never join the set and are never required of it.
- **Issue conditions:**
  - the set is nonempty;
  - every id in it is unambiguous (appears once among live rows);
  - every id in it is in `selected_row_ids`, which is the candidate context's visible set. A block naming a live row that is not visible is not issued, which also covers a live row outside the selection.
  - A block with exactly one owner issues as today, so every existing span is unchanged.
- **Span shape (recommended):** add an `owning_row_ids` field to `StageProseSpan` with a default of the single owner, kept in a stable sorted order. Keep `row_id` as the first owner so existing single-owner readers keep working. The implementer owns the exact field design.
- **Span identity (must hold):**
  - A single-owner span keeps the current `stage_prose_span_id(row_id, text)` value.
  - A shared span's id must bind the whole owning set and the text. One way: hash the sorted ids joined with a separator that cannot appear in a row id, plus the text. Editing the owning set must change the id.
  - Keep one helper that produces both forms and update the check in `roadmap_revision_patch.py` only if it cannot already accept the shared form. That check is step 5's territory otherwise (see Deferred).
- **Source order:** the function keeps returning spans in body order. A shared span appears once, not once per owner.
- **Capsule carriage:**
  - Add an optional owning-set field to `CandidateContextSourceSpan` and its receipt. Single-owner spans must omit the field from the wire form, and legacy records, which lack it, must still validate. This keeps existing capsule bytes and digests the same.
  - In `_full_members_and_inventory`, group spans by owner so each owner member lists the shared span. One way: every owner's `source_spans` carries it. The capsule byte ceiling (`CANDIDATE_CONTEXT_MAX_BYTES`) counts the repeated text, so check the ceiling case.
  - Update `_source_span_facts` and the receipt builder together so receipt and full record agree.
  - `_CONTEXT_SCHEMA_VERSION` stays at 1 unless the additive field cannot load old records. Do not bump it just for the field.
- **Local selector stays narrow:** do not edit `_select_row_owned_prose_spans`. It keeps the first-block, prose-editable-row, one-owner rule. A test pins that it still refuses a shared block.
- **Gotcha:** a block naming two rows where one id is a duplicate live id is ambiguous and must not issue. Do not downgrade it to a single-owner span.

## Tests

In `tests/test_roadmap_revision.py`:

- `test_shared_block_naming_two_visible_live_rows_is_issued_with_both_owners` — one span, owning set holds both ids, issued once.
- `test_shared_span_id_binds_the_whole_owning_set_and_text` — changing either the set or the text changes the id.
- `test_single_owner_span_id_is_unchanged_by_shared_issuance` — id equals `stage_prose_span_id(row_id, text)` for one owner.
- `test_shared_block_is_not_issued_when_an_owner_is_not_visible` — a live row named in the block but absent from `selected_row_ids` blocks issuance.
- `test_removed_row_reference_neither_joins_nor_is_required_of_the_owning_set` — a block naming a visible live row and a removed row issues with only the live row as owner. A block naming two live rows and a removed row issues with the two live rows.
- `test_block_naming_an_ambiguous_duplicate_live_id_is_not_issued` — duplicate live ids refuse issuance.
- `test_local_revision_selector_still_refuses_a_shared_block` — `_select_row_owned_prose_spans` through `build_stage_revision_context` issues nothing for a shared block.

In `tests/test_roadmap_candidate_context.py`:

- `test_shared_span_is_carried_with_its_owning_set_through_the_capsule` — build, receipts, and wire form show the owners.
- `test_single_owner_span_wire_form_omits_the_owning_set_field` — existing capsule bytes and digest stay the same.
- `test_legacy_capsule_without_owning_set_still_loads` — a record in the old shape validates and round-trips.
- `test_shared_span_text_counts_toward_the_capsule_byte_ceiling` — repeated owner carriage cannot pass the ceiling unnoticed.

**Green-before-done gate:** every case above, plus the existing tests in both files, must be green before this step is finished.

## Acceptance criteria

- A block naming two or more visible live rows yields one span whose owning set is exactly those rows.
- A block naming a live row outside the visible set yields no span.
- A removed-row id in a block never appears in an owning set and never blocks issuance.
- Single-owner span ids and capsule wire bytes are the same as before.
- A capsule record without the owning-set field still loads.
- `_select_row_owned_prose_spans` is unchanged, and a test shows it refuses a shared block.
- `tests/test_duplication.py` still passes (no duplicated helper bodies added).

## Applicable guardrails

- The plan's "## Scope guardrails", stale-row reference: a removed-row reference must not grant authority. Issuance here never counts removal records toward the owning set.
- The plan's "## Out of scope", arbitrary body replacement: issuance stays limited to a blank-line block that names live rows. No marker-based or free-range span is added.
- The plan's "## Scope guardrails", no weaker described-row gates: this step touches issuance only and changes no gate.

## Deferred

- Candidate operation that consumes a shared span, its fragment ceiling, and refusal values — later steps in this plan (step 1 defines the contract).
- Authority check on a shared span at apply time in `plan_tool/roadmap_revision_patch.py` — the step that applies the correction; this step only keeps single-owner identity compatible.
- Widening the local revision selector — deliberately left narrow by this step's intent.
- Gate state for the corrected body — step 1's contract, later steps' implementation.
