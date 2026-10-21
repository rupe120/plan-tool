> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extract a companion-ready story renderer without changing story-only output

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Extract the current Jira story formatting and append assembly in `plan_tool/jira.py` behind one controlled rendering boundary. Keep `format_markdown`, `format_json`, `export_jira`, and append-mode output behavior unchanged for existing callers. The key decision is that rendering consumes already-prepared story inputs and never reads files, invokes Claude, or publishes output. On green, fresh and append-mode story-only exports render the same Markdown and JSON as before.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the story renderer needs a dedicated boundary.
- [Input](#input) — Existing story and append-mode contracts the renderer preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Rendering boundary, compatibility rules, and call sites.
- [Tests](#tests) — Focused regression coverage for fresh and append output.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this extraction.
- [Deferred](#deferred) — Later companion work intentionally left out of this step.

## Why

`plan_tool/jira.py:format_markdown`, `plan_tool/jira.py:format_json`, `plan_tool/jira.py:_merge_markdown`, and `plan_tool/jira.py:_merge_json` each assemble parts of the same story-source artifact. A later companion flow needs to render a prepared current story source without borrowing file reads, append decisions, or publication behavior from `plan_tool/jira.py:export_jira`. Extracting that boundary now lets later work reuse the proven rendering contract instead of creating a second formatter that can drift from story-only export.

## Input

- **Story records:** `plan_tool/jira.py:Story` supplies the complete logical story shape, including the human-owned `jira_issue_key` field that must remain last on rendered surfaces.

- **Fresh-render inputs:** `plan_tool/jira.py:format_markdown` and `plan_tool/jira.py:format_json` currently combine the plan title, stories, `plan_tool/jira_config.py:Epic`, selected detail-path map, and optional plan tag.

- **Append-mode inputs:** `plan_tool/jira.py:_FrozenTicket` carries preserved Markdown blocks or JSON objects. `plan_tool/jira.py:reconcile_existing_statuses` may change only a dropped ticket's state before rendering.

- **Output contract:** `plan_tool/jira.py:JiraResult` carries the exact text the existing fresh and append paths write. The extracted boundary must return that text without taking ownership of filesystem writes.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Extract one prepared-story rendering boundary and route the fresh and append branches through it while retaining the current public formatter behavior.
  - `tests/test_jira.py` — Add exact-output regression cases for the extracted boundary and preserve fresh and append-mode coverage.

## Implementation

- **Foundational logic:** Render an already-prepared story collection into the selected Jira source format. The boundary receives rendering data; it does not decide which stories are current, read an existing export, call an invoker, or write a destination.

- **Extract one rendering seam:** Build a small renderer function or value around the work now split among `plan_tool/jira.py:format_markdown`, `plan_tool/jira.py:format_json`, `plan_tool/jira.py:_merge_markdown`, and `plan_tool/jira.py:_merge_json`. One approach is an explicit input object that distinguishes newly rendered stories from preserved append records; the exact internal shape may follow the code as long as the renderer does not reacquire live inputs.

- **Keep public formatter contracts stable:** Preserve the signatures and output of `plan_tool/jira.py:format_markdown` and `plan_tool/jira.py:format_json`. They may delegate to the new boundary, but callers must still get the current Markdown header, JSON payload shape, title decorations, detail links, sentinels, and field ordering.

- **Route both existing paths through the seam:** Update the fresh branch in `plan_tool/jira.py:export_jira` and the append branch in `plan_tool/jira.py:_export_jira_append` so their final story text comes from the same rendering boundary. Keep parsing, linting, warning emission, state reconciliation, and file writes in their current orchestration paths.

- **Preserve append semantics:** Keep `plan_tool/jira.py:_FrozenTicket` Markdown material unchanged except for the existing state update from `plan_tool/jira.py:_set_markdown_block_state`. Preserve frozen JSON records as records, recompute the combined header or total estimate as today, sort by story number, and apply a plan tag only to newly rendered stories.

- **Do not add companion behavior:** Do not add snapshot capture, provenance, destination checks, Jira-key matching rules, or paired publication here. This step provides the renderer boundary only; later steps supply the companion-specific inputs and lifecycle decisions.

## Tests

### Tests for this step

- `test_story_renderer_matches_current_fresh_markdown_output` — A representative fresh story set with optional fields, detail paths, and a plan tag renders the established Markdown text exactly.

- `test_story_renderer_matches_current_fresh_json_output` — The same prepared fresh story set renders the established pretty-printed JSON shape, field order, titles, and totals.

- `test_story_renderer_preserves_frozen_markdown_and_tags_only_new_story` — An append render retains a frozen Markdown block and its human Jira key while tagging only the newly rendered story.

- `test_story_renderer_preserves_frozen_json_record_and_recomputes_total` — An append JSON render retains the frozen record content, orders records by story number, and recomputes the combined estimate.

- `test_export_jira_story_only_output_is_unchanged_after_renderer_extraction` — Fake-invoker fresh and append exports still return and write the expected story-only source text.

Every added and affected case in `tests/test_jira.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/jira.py:format_markdown` and `plan_tool/jira.py:format_json` keep their existing call signatures and render the same output for fixed inputs.

- The fresh `plan_tool/jira.py:export_jira` path and `plan_tool/jira.py:_export_jira_append` both obtain final story text through the extracted rendering boundary.

- The rendering boundary performs no filesystem reads or writes, model invocation, export parsing, linting, or state reconciliation.

- Markdown append output retains frozen story content and human Jira keys, except for the existing dropped-state update.

- JSON append output retains frozen story records, while its top-level total and story ordering remain correct.

- `uv run pytest tests/test_jira.py -q` passes.

## Applicable guardrails

- **The plan’s step intent, controlled story-side rendering boundary:** Keep this step behavior-preserving for both normal export and append mode; do not make companion mode observable yet.

- **The plan’s `## Risks`, story-only compatibility:** Preserve the current story-only contract for callers that do not request a companion.

- **The plan’s `## Out of scope`, protected product boundaries:** Do not change detail-grade behavior, independent authoring behavior, external Jira behavior, or other excluded surfaces while extracting the renderer.

## Deferred

- Companion input capture — Step 1 owns the immutable render-input snapshot; this renderer must not recreate that capture work.

- Companion-mode story regeneration and Jira-key ownership checks — Step 3 owns those behavior changes; this step preserves the current append semantics.

- Paired output staging and publication — Step 5 owns synchronized writes and target protection; this step returns rendered story text only.
