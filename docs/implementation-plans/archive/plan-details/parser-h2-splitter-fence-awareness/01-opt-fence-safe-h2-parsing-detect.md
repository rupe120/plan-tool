> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add opt-in fence-safe H2 parsing, detect unmatched opening fences, and limit section replacement to real headings

## Summary

Add shared fenced-code detection to `plan_tool/scope_fence.py` and opt-in fence-safe parsing to `plan_tool/parser.py`. Keep default parser behavior and existing `extract_h2_sections` defaults unchanged. Make `parse_body_sections`, `split_body_sections`, and `replace_body_sections` able to use only real headings when a caller requests fence safety. On green, later steps can select boundary-only or content-stripping reads and can detect an unmatched opening fence without duplicating fence grammar.

## Table of Contents

- [Summary](#summary) — The step’s outcome and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The parser defect this shared primitive addresses.
- [Input](#input) — Existing parser and fence-scanner contracts to preserve.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed in this step.
- [Implementation](#implementation) — Required parser, scanner, and replacement behavior.
- [Tests](#tests) — Focused regression coverage for the new modes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Markdown, regex, and test references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/parser.py:parse_body_sections` currently treats H1 and H2-looking lines inside fenced examples as real boundaries, so `split_body_sections` can truncate or replace plan-body content that `plan_tool/review.py` and `plan_tool/concept_sync.py` consume. `plan_tool/scope_fence.py:_fenced_code_spans` already recognizes closed fences, but its unmatched-opening behavior silently hides later sections. This step supplies one narrow, opt-in foundation so later consumer and write-path work can fix those cases without changing every existing reader at once.

## Input

- **`plan_tool/parser.py:BodySection`** — Preserve its `name`, `heading`, `body`, and `order` contract, including current heading normalization and source ordering when fence safety is not requested.
- **`plan_tool/parser.py:parse_body_sections`, `split_body_sections`, and `replace_body_sections`** — Preserve default duplicate handling, H1/H2 boundary behavior, H3 inclusion, and source-preserving replacement behavior.
- **`plan_tool/scope_fence.py:_fenced_code_spans` and `extract_h2_sections`** — Reuse the existing backtick/tilde fence grammar and retain `ignore_fenced_code=False` and `strip_fenced_code=False` defaults.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/parser.py` — Add opt-in fence-safe section parsing and ensure `replace_body_sections` selects only real H2 headings.
  - `plan_tool/scope_fence.py` — Make the fence scanner expose an unmatched-opening signal while remaining a stdlib-only leaf.
  - `tests/test_parser.py` — Cover default compatibility, safe parsing modes, and safe replacement.
  - `tests/test_scope_fence.py` — Cover fence grammar, unmatched-opening detection, and existing extractor guarantees.

## Implementation

- **Share fence recognition, not whole extractors.** Build on `plan_tool/scope_fence.py:_fenced_code_spans` and its `_FENCE_OPEN_RE` / `_FENCE_CLOSE_RE` grammar so `plan_tool/parser.py` does not add a third scanner. Keep `plan_tool/scope_fence.py` free of first-party imports. Do not merge `parse_body_sections` into `extract_h2_sections`: their duplicate-winner and heading-normalization contracts differ.

- **Make fence safety explicit.** Give `plan_tool/parser.py:parse_body_sections` and `split_body_sections` opt-in boundary-safe and content-stripping behavior aligned with `plan_tool/scope_fence.py:extract_h2_sections`. Both default paths must retain current output. Content stripping must imply boundary safety.

- **Keep boundary-only reads lossless.** In boundary-safe mode, ignore H1 and H2-looking lines inside a closed fence when finding section starts and ends, but retain the fenced text in the returned real section body. Content-stripping mode may remove fenced text only for consumers that match extracted content.

- **Keep replacements source-preserving.** Make `plan_tool/parser.py:replace_body_sections` use the same real-heading set for owned H2 targets and replacement boundaries. A fenced pseudo-heading must neither select a replacement nor end a real replacement range. Replacing a real section must not remove or rewrite a fenced example in an unowned part of the body.

- **Give unmatched openers one read meaning.** Evolve `plan_tool/scope_fence.py:_fenced_code_spans` or a narrowly named shared helper so a supported opening fence without a valid closer is distinguishable from a closed span. For fence-safe reads, the opener through EOF is code: later heading-looking lines do not begin sections. Return that state separately from an ordinary closed span so step 3 can refuse parser-driven writes; boundary-only reads retain the source text and content-stripping reads remove it only when selected.

- **Preserve the supported closure rule.** A closer must use the opening marker type, meet or exceed its marker length, and contain only trailing whitespace. A different marker, shorter run, or trailing content remains fenced content until a later valid closer appears.

- **Leave existing consumers unchanged here.** `plan_tool/annotate_render.py:render_annotated_report`, `plan_tool/create.py`, `plan_tool/detail.py:extract_plan_references`, `plan_tool/reprocess.py`, `plan_tool/roadmap_gates.py`, and `plan_tool/scope_out.py` keep their current `extract_h2_sections` calls. Step 2 selects parser modes for plan-body readers; step 3 consumes unmatched-opening detection before writes; step 4 applies safe replacement in `plan_tool/concept_sync.py`.

## Tests

### Tests for this step

- `test_default_split_keeps_fenced_pseudo_heading_behavior` — `plan_tool/parser.py:split_body_sections` without an opt-in retains its current fenced-heading interpretation.
- `test_fence_safe_split_ignores_fenced_h1_and_h2_boundaries` — Boundary-safe splitting keeps a fenced pseudo-heading inside the preceding real section and finds the following real section.
- `test_fence_safe_split_preserves_fenced_body_text` — Boundary-only mode returns fenced examples verbatim inside their real section.
- `test_fence_safe_split_strips_fenced_body_text_only_when_requested` — Content-stripping mode removes fenced examples while retaining real section text.
- `test_fence_safe_parse_keeps_existing_duplicate_and_normalization_rules` — Fence-safe parsing retains `BodySection` ordering and the parser’s existing normalized duplicate behavior for real headings.
- `test_fence_safe_replacement_uses_only_real_h2_headings` — `replace_body_sections` updates the intended real section without treating a fenced pseudo-heading as a target or boundary.
- `test_fence_safe_replacement_preserves_unowned_fenced_content` — Replacing an owned section leaves adjacent, unowned fenced examples unchanged.
- `test_unmatched_opening_fence_is_reported` — The shared scanner distinguishes an unmatched supported opener from a closed fence.
- `test_fence_safe_unmatched_opening_keeps_later_pseudo_heading_out_of_sections` — Fence-safe parsing treats the opener through EOF as code and does not expose later heading-looking lines as sections.
- `test_nonclosing_marker_lines_do_not_report_unmatched_when_a_later_valid_closer_exists` — Different markers, short markers, and trailing closer content do not close the fence, while a later valid closer does.
- `test_extract_h2_sections_keeps_default_modes_off` — `plan_tool/scope_fence.py:extract_h2_sections` retains its existing default behavior.
- `test_leaf_has_no_first_party_runtime_import` — `plan_tool/scope_fence.py` remains a leaf after exposing the shared fence result.

Green-before-done gate: `uv run pytest tests/test_parser.py tests/test_scope_fence.py -q` must pass.

## Acceptance criteria

- `parse_body_sections` and `split_body_sections` offer explicit fence-safe behavior without changing their default results.
- Boundary-safe parsing ignores fenced H1/H2 pseudo-headings and preserves fenced text in the containing real section.
- Content-stripping parsing removes fenced content only when the caller explicitly selects that mode.
- `replace_body_sections` does not target or use a fenced pseudo-heading as a replacement boundary and preserves unowned source text.
- Fence-safe reads treat an unmatched supported opening fence through EOF as code while the shared result reports that state separately from a closed span.
- A valid later closer resolves an earlier opener; marker-like nonclosers do not independently raise an unmatched-opening result.
- `plan_tool/scope_fence.py:extract_h2_sections` retains default-off fence flags and leaf-import discipline.
- `uv run pytest tests/test_parser.py tests/test_scope_fence.py -q` passes.

## References

- [CommonMark Spec — Fenced code blockshttps: — Use the opener and valid-closer rules for the shared scanner.
- [CommonMark Spec — ATX headingshttps: — Keep real heading recognition limited to text outside fenced code.
- [Python 3.13 documentation — re: Regular expression operationshttps: — Use multiline matching and spans without losing source boundaries.
- [pytest documentation — How to parametrize fixtures and test functionshttps: — Parameterize valid and invalid closer cases.

## Applicable guardrails

- **Plan `## Plan intent`, canonical plan-body splitting** — Establish the shared primitive without claiming that unswept parser consumers are already fence-safe.
- **Plan `## Step intent`, opt-in behavior** — Keep parser defaults unchanged until a consumer explicitly chooses fence safety.
- **Plan `## Out of scope`, allowed behavior changes** — Do not add command-level write refusal in these files; later steps own those paths.
- **Plan `## Out of scope`, named parser exclusions** — Do not alter `plan_tool/detail.py:parse_detail_file_sections`, the Jira-grade scanner, or unrelated Markdown scanners.

## Deferred

- **Parser-consumer adoption** — Step 2 selects and tests the appropriate read mode for `plan_tool/review.py`, `plan_tool/create.py`, `plan_tool/detail.py`, and the other parser consumers; deferred under signed-off concept `74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`.
- **Write-path refusal and concept-sync protection** — Steps 3 and 4 own target-preserving unmatched-fence failures and `plan_tool/concept_sync.py` integration; deferred under signed-off concept `74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`.
- **Default-on policy and further splitter consolidation** — Keep both as follow-up work after consumer behavior is established; deferred under signed-off concept `74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`.
