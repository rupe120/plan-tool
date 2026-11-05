> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extract the exact-span splice and overlap refusal into a shared helper

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step moves the span-splicing and overlap-refusal part of `_apply_stage_prose_amendments` into a public helper in `plan_tool/roadmap_revision_patch.py`. The helper takes plain `(start, end, replacement)` edits and a body. It refuses overlapping ranges with the message `stage prose amendments overlap`, then splices the edits back to front. `_apply_stage_prose_amendments` keeps its per-operation validation and its append step. It calls the helper instead of running the splice inline. The helper takes plain offsets instead of `StageProseSpan` so later steps can reuse it for candidate spans. This is a refactor with no behavior change: stage-revision replace, delete, and append output and the overlap refusal must be unchanged. On green, the existing stage-revision tests pass untouched and new direct tests pin the helper.

## Table of Contents

- [Why](#why) — the single splice copy that later steps would otherwise duplicate
- [Input](#input) — the current code shape the extraction preserves
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — what the helper must do and what stays put
- [Tests](#tests) — direct helper tests plus the existing regression net
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — related work this step does not do

## Why

`plan_tool/roadmap_revision_patch.py:_apply_stage_prose_amendments` is the only place that splices exact spans into an artifact body and refuses overlapping edits. The candidate correction path needs the same two behaviors. If it copies them, the two copies drift, and the repo's duplicate-body guard (`tests/test_duplication.py`) also objects to the copy. Extracting the splice first lets the later candidate steps reuse it. This step does only the extraction, so it can be reviewed as a pure move.

## Input

- **Current inline logic:** `_apply_stage_prose_amendments` collects `(StageProseSpan, replacement)` pairs, sorts `(span.start, span.end)`, and refuses when any range starts before the previous range's end. It then applies replacements from the highest start to the lowest and finally calls `append_row_prose_fragments`.
- **Boundary rule to keep:** a range that starts exactly where the previous one ends is allowed. Only `start < prior_end` is an overlap.
- **Refusal type and text:** `RevisionMergeError("stage prose amendments overlap")`, defined in the same module. No other file raises or matches this text at HEAD.
- **Other users:** `plan_tool/roadmap_candidate.py` imports `append_row_prose_fragments` from this module. It does not use the splice, so it needs no change.
- **Limit on verification:** no test at HEAD asserts the overlap message by name. The existing stage-revision tests in `tests/test_roadmap_revision_patch.py` cover replace, delete, and append end to end. Overlap behavior is pinned only by the new tests in this step.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_revision_patch.py`: add the public splice helper next to `append_row_prose_fragments`. Replace the inline sort, overlap check, and reverse splice in `_apply_stage_prose_amendments` with one call to it.
  - `tests/test_roadmap_revision_patch.py`: add direct helper tests (see Tests). Existing cases are not edited.

## Implementation

- **Helper shape (recommended):** a public function such as `splice_exact_spans(body: str, edits: Iterable[tuple[int, int, str]]) -> str`. Each edit is `(start, end, replacement)` over `body` offsets. The name and signature are the implementer's choice, but the inputs must be plain offsets and text. Do not make it depend on `StageProseSpan`, because the candidate step has its own span type.
- **Overlap rule:** sort by `(start, end)`, refuse when a range starts before the previous range's end, and raise `RevisionMergeError` with the exact text `stage prose amendments overlap`. The check must run before any splice.
- **Splice order:** apply from the highest start to the lowest so earlier offsets stay valid. Return the new body. An empty edit list returns `body` unchanged.
- **Caller change:** in `_apply_stage_prose_amendments`, build edits as `(span.start, span.end, replacement)` from the existing `replacements` list. Pass the result and `artifact.body` to the helper, then call `append_row_prose_fragments` on the returned body exactly as today.
- **What stays in place:**
  - Every per-operation check (identity-only rows, add-row append requirements, issued-span matching, nonblank replacement) stays in `_apply_stage_prose_amendments`. The helper does not validate meaning.
  - The helper does not append. Appending stays with `append_row_prose_fragments`.
  - The helper does not check that offsets lie inside the body or that `start <= end`. Source verification (`_verify_stage_source`, `_verify_stage_prose_spans`) already owns that. Keeping the helper unchecked keeps stage behavior the same.
- **Rejected alternative:** a helper that takes `StageProseSpan` objects. It would force the candidate path to build fake spans or add a second copy.
- **Ordering gotcha:** the overlap check runs after all per-operation checks, as today. An operation error must still win over an overlap error when both exist. Do not move the helper call earlier.

## Tests

All in `tests/test_roadmap_revision_patch.py`. Every test below, and every existing test in the file, must be green before this step is done.

### Tests for this step

- `test_splice_exact_spans_replaces_and_deletes_by_offset` — one replacement and one empty-string deletion produce the expected body.
- `test_splice_exact_spans_applies_edits_independent_of_input_order` — edits given in any order produce the same result, so offsets stay valid.
- `test_splice_exact_spans_allows_adjacent_ranges` — a range starting exactly at the previous range's end is not an overlap (the deliberate `start < prior_end` boundary).
- `test_splice_exact_spans_refuses_overlap_with_stage_message` — overlapping ranges raise `RevisionMergeError` with the exact text `stage prose amendments overlap`.
- `test_splice_exact_spans_refuses_overlap_before_changing_anything` — the refusal happens as an exception with no partial body returned.
- `test_splice_exact_spans_with_no_edits_returns_body_unchanged` — an empty edit list returns the same body.
- `test_stage_revision_two_amendments_on_overlapping_spans_still_refuses` — a `merge_stage_revision` case with two issued spans that overlap keeps the same refusal text through the stage path. Build it from the existing span fixtures in the file.
- The existing stage-revision replace, delete, and append cases act as the unchanged-behavior net. They must pass with no edits.

## Acceptance criteria

- `plan_tool/roadmap_revision_patch.py` exposes one public splice helper, and `_apply_stage_prose_amendments` calls it instead of sorting and splicing inline.
- `rg "prose amendments overlap" plan_tool` returns exactly one hit, inside the helper.
- The refusal text is exactly `stage prose amendments overlap` and the exception type is `RevisionMergeError`.
- `uv run pytest tests/test_roadmap_revision_patch.py -q` passes, with no existing test edited.
- `uv run pytest tests/test_duplication.py -q` passes with no new allowlist entry.
- `git diff --stat` shows only `plan_tool/roadmap_revision_patch.py` and `tests/test_roadmap_revision_patch.py`.

## Applicable guardrails

- **The plan's "## Scope guardrails" and "## Out of scope" (no arbitrary body replacement, no generic document editing):** the helper only applies caller-supplied exact offsets. It has no search, marker, or pattern matching, and it gives no authority by itself.
- **Step intent (reuse of exact-span application and overlap protection):** this step only extracts. It adds no candidate operation, parser, or span type.

## Deferred

- Candidate correction operation, span issuance, and authority binding — owned by later steps of this plan.
- Using the helper from `plan_tool/roadmap_candidate.py` — the later candidate application step does this.
- Merging `append_row_prose_fragments` into the helper — it stays separate because add-row append has different spacing rules and a second importer in `plan_tool/roadmap_candidate.py`.
