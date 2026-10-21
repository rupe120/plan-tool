> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Merge allowed rewrites and update only the selected feedback response

## Summary

Create `plan_tool/roadmap_structural_revision_patch.py` and `tests/test_roadmap_structural_revision_patch.py` to build one raw-text candidate from step 2’s accepted predecessor and step 3’s validated operations. The merger replaces only located scalar spans, one eligible prose-region interior, and the selected feedback row’s state plus response insertion point. The key decision is to splice the canonical source directly rather than re-rendering the artifact. On green, the returned candidate parses and renders back to the same bytes while every unselected byte and feedback row remains unchanged.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why this path needs a source-span merger.
- [Input](#input) — Upstream context and operation contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Candidate construction, span limits, and invariants.
- [Tests](#tests) — Focused merger coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the merger.
- [Deferred](#deferred) — Work owned by later steps or separate follow-up.

## Why

`plan_tool/roadmap_revision_patch.py:merge_feedback_revision` returns a typed artifact for the narrower local-revision path, and `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` renders that artifact before writing it. That is not suitable for a structural rewrite that must prove unchanged source bytes outside a small set of approved spans. This step adds the missing raw-text candidate boundary so later proof and publication can evaluate one exact candidate without turning a bounded rewrite into a whole-artifact formatting change.

## Input

- **Accepted predecessor:** Step 2 supplies the one selected stage, canonical artifact text, parsed artifact, selected feedback row, and selected target row. Treat that context as immutable; do not reselect feedback, discover another target, or load another artifact.

- **Validated operations:** Step 3 supplies the accepted row-field operations, optional prose-region operation, feedback response, scalar admission facts, and region metadata. Consume those validated records rather than accepting raw backend text.

- **Canonical parser and renderer:** `plan_tool/roadmap.py:RoadmapStage` supplies the selected stage's parser and renderer for the final candidate check. `plan_tool/roadmap_artifacts.py:_feedback_mapping` establishes the canonical state-before-response ordering for a feedback row.

- **Existing local-revision boundary:** `plan_tool/roadmap_revision_patch.py:merge_feedback_revision` remains a separate typed merger for local revision. Its behavior does not establish byte-preserving structural rewrite behavior.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_structural_revision_patch.py` — Add the pure source-span merger, candidate result, and typed rejection boundary.
  - `tests/test_roadmap_structural_revision_patch.py` — Add canonical-fixture tests for accepted candidates and every source-span refusal.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Build one render-canonical candidate by applying only validated, non-overlapping source-span replacements to the selected artifact text.

- **Expose a pure merger boundary.** Add one public function, such as `merge_structural_revision_patch`, that accepts step 2’s accepted context and step 3’s accepted operations and returns the candidate text plus the parsed candidate if useful to later proof. Raise a dedicated patch error for invalid direct callers or unlocatable source shapes. Do not read files, invoke a backend, acquire a writer guard, invalidate seeds, or publish.

- **Start from exact predecessor text.** Use only the canonical selected artifact text retained by step 2. Do not call `RoadmapStage.render` to construct the candidate; rendering is a final equality check, not the editing mechanism.

- **Locate row-field spans by structure, not text coincidence.** Find the selected collection, selected row id, and permitted field in the canonical frontmatter. Require exactly one block-style row mapping and exactly one single-line scalar span for each operation. Replace that span with step 3's renderer-derived scalar fragment, never the raw JSON value. Refuse zero or multiple matches and source forms that cannot safely identify one scalar span, including block scalars, flow collections, aliases, and tags.

- **Keep operation targets bounded.** Recheck that each accepted row-field operation still names step 2’s selected collection and row, and that each field is permitted by step 3’s operation contract. Reject duplicate or overlapping spans rather than choosing an order that changes their meaning.

- **Apply prose only within retained metadata.** Replace only the interior of the one region step 3 identified. Preserve both delimiter lines and reject a candidate whose marker inventory, pairing, or nesting no longer matches the predecessor.

- **Update exactly one feedback row.** Locate the selected open feedback row in the predecessor source, replace only its `state` scalar with `awaiting-review`, and insert one `proposed_response` mapping line immediately after that state line. Build the inserted scalar using the same YAML rendering configuration as `plan_tool/roadmap_artifacts.py:_render`; it must be the admitted one-line form from step 3. Do not rewrite the reviewer’s request or any unselected feedback row.

- **Apply spans without offset drift.** One workable approach is to collect all approved replacements against the original text, verify they do not overlap, then apply them from the end of the text toward the start. The result must preserve every predecessor byte outside those spans and the one allowed zero-width insertion point.

- **Require final canonicality.** Parse the completed candidate through the selected `RoadmapStage.parse`, then require `RoadmapStage.render` to reproduce the candidate text exactly. Reject a candidate that parses but would normalize to different bytes.

- **Keep proof and publication separate.** Step 5 owns predecessor-versus-candidate structural and full-roadmap gate proof. Step 6 owns guarded rechecks, seed invalidation, and `plan_tool/roadmap_revision_publish.py`-style atomic publication.

## Tests

### Tests for this step

- `test_merge_applies_selected_row_field_operations_and_feedback_response` — Replaces permitted selected-row scalars, changes the selected state, and inserts the one canonical response line.

- `test_merge_applies_one_existing_prose_region_without_changing_delimiters` — Replaces only a valid region interior and preserves both marker lines.

- `test_merge_combines_non_overlapping_row_region_and_feedback_spans` — Applies distinct approved operation kinds without offset corruption.

- `test_merge_rejects_response_only_envelope` — Confirms the merger receives no response-only envelope because V1 requires at least one accepted operation alongside the selected feedback response.

- `test_merge_preserves_every_unpermitted_predecessor_byte` — Keeps comments, unrelated rows, region delimiters, body text, and unselected feedback source unchanged.

- `test_merge_updates_only_selected_feedback_state_and_response` — Preserves every selected-feedback fact except its permitted state and inserted response, and preserves every unselected feedback row.

- `test_merge_rejects_unlocatable_or_ambiguous_scalar_source_shapes` — Refuses missing, duplicate, block-style, flow-style, aliased, tagged, or otherwise non-single-line target spans.

- `test_merge_uses_renderer_quoted_scalar_fragment` — Proves an admitted value such as `"true"` replaces a row field as the renderer's quoted scalar and remains canonical after parsing.

- `test_merge_rejects_operations_outside_selected_target_or_overlapping_spans` — Refuses caller-created operations that name another row, collection, field, region, or conflicting source span.

- `test_merge_rejects_selected_feedback_that_no_longer_matches_preflight` — Refuses missing, duplicate, non-open, already-responded, or changed selected feedback before producing a candidate.

- `test_merge_requires_renderer_canonical_candidate_bytes` — Rejects a spliced candidate when the selected stage parser and renderer do not reproduce its exact text.

Green-before-done gate: `uv run pytest tests/test_roadmap_structural_revision_patch.py -q` passes.

## Acceptance criteria

- The new merger returns a candidate only from step 2’s selected canonical artifact and step 3’s accepted operations.

- The candidate changes only approved selected-row scalar spans, one eligible prose-region interior, and the selected feedback state plus response insertion point.

- Every byte outside those approved locations remains unchanged, including unselected feedback rows and region delimiters.

- The selected feedback row changes to `awaiting-review` and gains exactly one canonical single-line `proposed_response`; its request remains unchanged.

- The merger rejects ambiguous, unsupported, overlapping, or out-of-context source spans rather than selecting a replacement heuristically.

- Every row-field replacement uses the renderer-derived scalar fragment retained by step 3, not the raw JSON value.

- Every returned candidate satisfies `RoadmapStage.render(RoadmapStage.parse(candidate_text)) == candidate_text`.

- `uv run pytest tests/test_roadmap_structural_revision_patch.py -q` passes.

## Applicable guardrails

- **The plan’s intent, selected-artifact boundary:** Limit candidate construction to the selected artifact and selected feedback response; do not expose a wider write set.

- **The plan’s step intent, source-span boundary:** Preserve source bytes except at the permitted replacements and selected response insertion point.

- **The plan’s `## Out of scope`, structural-change boundary:** Do not expand the merger into a general document editor or admit unsupported structural changes.

- **The plan’s `## Out of scope`, revision-mode boundary:** Keep the existing local-revision path and canonical artifact schema unchanged.

## Deferred

- **Candidate preservation and full-roadmap gate proof** — Step 5 owns comparing the finished candidate with its predecessor and evaluating candidate-aware gate contexts.

- **Guarded atomic publication and seed invalidation** — Step 6 owns final snapshot checks, writer coordination, and canonical replacement.

- **Runner and command wiring** — Steps 8 and 9 own backend invocation, lifecycle reporting, and the explicit CLI surface.

- **Candidate-aware semantic-impact classification** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` routes this broader decision to BACKLOG #289.

- **Merger consolidation with `plan_tool/roadmap_revision_patch.py:merge_feedback_revision`** — Keep the typed local merger separate because it has a different contract; a shared patch abstraction exceeds this step’s file set.
