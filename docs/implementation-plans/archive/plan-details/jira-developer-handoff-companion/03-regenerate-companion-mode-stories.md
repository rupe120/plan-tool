> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Regenerate companion-mode stories with provable Jira-key ownership and state

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Add companion-only story regeneration in `plan_tool/jira.py` and focused coverage in `tests/test_jira.py`. Consume step 1’s immutable snapshot and step 2’s prepared-story rendering boundary so regeneration never rereads live plan inputs or uses append-mode preservation rules. Render only committed steps with visible status, and carry a human Jira key and its handoff state only after strict same-plan, unique, one-to-one committed-coverage matching. On green, companion mode produces a current story source plus explicit created-ticket update metadata, while parked and valid dropped records remain visible only as non-actionable story-source history.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why companion regeneration needs stricter ownership proof than append mode.
- [Input](#input) — Captured inputs and existing export contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Regeneration, state, and Jira-key ownership rules.
- [Tests](#tests) — Focused ownership and compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Test-fixture reference.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Later companion work intentionally left out.

## Why

`plan_tool/jira.py:_export_jira_append` preserves live tickets by id and frozen content, which is correct for ordinary append export but cannot prove that a regenerated companion story still owns a human-entered Jira key. Companion mode needs current stories from one captured input set, while preventing an ambiguous, foreign, or malformed existing source from attaching a real Jira ticket to the wrong regenerated story.

## Input

- **Captured companion inputs:** Step 1 supplies the immutable plan, selected detail, source excerpt, destination, prior-source identity, and parsed-record snapshot. Use only that captured representation during regeneration.

- **Prepared story rendering:** Step 2 supplies the rendering boundary for a prepared current story collection. It must not read paths, append frozen records, or publish files.

- **Current story contract:** `plan_tool/jira.py:Story`, `plan_tool/jira.py:parse_jira_response`, and `plan_tool/jira.py:build_story_id_re` provide the model-response shape, committed-plan coverage check, and epic-scoped story-id validation.

- **Existing-source contract:** `plan_tool/jira.py:_FrozenTicket`, `plan_tool/jira.py:_ExistingExport`, and `plan_tool/jira.py:_resolve_export_state` show the existing state and Jira-key vocabulary. Companion handling is stricter than `plan_tool/jira.py:read_existing_export`, whose permissive `None` fallback remains story-only behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Add companion-only current-story regeneration, strict existing-source validation, state/key carry-forward, and created-ticket update metadata.
  - `tests/test_jira.py` — Add fixtures and focused companion regeneration tests without weakening append-mode or story-only coverage.

## Implementation

- **Foundational logic — render only committed coverage and prove Jira-key ownership by canonical set.** Regenerate the complete committed story collection from the step 1 snapshot, expose each covered step's captured `pending`, `current`, or `done` status, and attach a prior non-dropped `jira_issue_key` only when exactly one same-plan source record and exactly one regenerated story share the same nonempty canonical committed-step set. Canonicalize a set as sorted unique step ids before comparing it; order in a source record must not affect a valid match. An all-done story is visibly historical; a mixed story visibly marks each done step complete.

- **Keep regeneration separate from append mode.** Do not adapt `plan_tool/jira.py:_export_jira_append` for companion mode. Its frozen-ticket behavior preserves old live prose and carries handoff fields by story id, while companion mode must render current prose and prove ownership by current plan coverage. Keep `plan_tool/jira.py:export_jira` and ordinary append semantics unchanged unless a caller explicitly enters the later companion path.

- **Render only from captured active inputs.** Build the companion-specific prompt, response validation, and prepared-story collection from step 1’s committed render set and captured statuses. Do not give deferred or `wont_do` steps to the model, and do not call `plan_tool/jira.py:render_jira_prompt`, `plan_tool/jira.py:_render_export_prompt`, or `plan_tool/jira.py:_render_step_detail` in a way that rereads the plan, details, or source files after capture.

- **Reuse the strict response parser where it fits.** Continue to validate the model response with `plan_tool/jira.py:parse_jira_response` using the captured committed plan ids, epic, first story number, and a reserved `known_ids` set containing every retained historical story id, including dropped records. Add companion-only checks after parsing for canonical-set uniqueness and historical-key ownership; do not tighten the public parser in ways that change story-only acceptance.

- **Require a proven same-plan source.** Treat a source-plan identity captured by step 1 as required proof for any existing keyed record. Do not infer ownership from a matching title, output path, epic prefix, or story id alone. Refuse a malformed, legacy-unproven, or foreign existing source before returning a publishable companion story result.

- **Apply state before matching.** Use `plan_tool/jira.py:_resolve_export_state` semantics on captured records: a keyed draft becomes created, a keyed created record remains created, and a dropped record stays dropped. A non-dropped created record without a nonempty Jira key is invalid in companion mode and must refuse regeneration.

- **Preserve parked and dropped history without reviving it.** A dropped source record may remain in the regenerated story source only when none of its covered steps are committed. Keep it out of the current regenerated collection and expose it separately so step 4 cannot render it as a companion plan-path section. A record covering only deferred or `wont_do` steps becomes visible dropped history. Refuse a dropped record that names any committed step, or any source record that mixes parked and committed coverage, rather than silently narrowing a live Jira ticket.

- **Reject every ambiguous key path.** Refuse before producing a publishable result when a keyed source record has an empty, repeated, unparseable, or duplicate covered-step set; when a nonempty key appears in more than one source record; when multiple keyed records or multiple regenerated stories claim one canonical set; or when a keyed source set has no regenerated match. Do not drop the key, pick the first record, or create a replacement ticket as a fallback.

- **Return complete created-ticket lifecycle information.** When a proven created record is reattached to regenerated story content that differs from its captured source, return its regenerated story id and Jira key in companion-only result metadata. When a keyed created record becomes dropped history because its coverage is parked or removed, return its story id and Jira key in a distinct created-to-dropped follow-up. Step 6 will present both notices; this step only supplies reliable data for them.

- **Use the extracted renderer.** Send the prepared current stories and valid dropped-history records to step 2’s rendering boundary. Preserve Markdown and JSON state/key placement through `plan_tool/jira.py:_render_story_block` and `plan_tool/jira.py:_story_to_json_dict`; keep `jira_issue_key` human-owned and last on rendered surfaces.

- **Leave publication to step 5.** This step may return rendered story text and metadata, but it must not write, stage, replace, or recover either output target.

## Tests

Add companion cases beside `tests/test_jira.py:TestExportJiraAppend`, `tests/test_jira.py:TestExportStateVocabulary`, and `tests/test_jira.py:TestStoryStateRendering`. Keep existing append fixtures as compatibility evidence; companion fixtures should use the step 1 snapshot boundary rather than mutable files.

### Tests for this step

- `test_companion_regeneration_uses_the_captured_snapshot_after_live_inputs_change` — Regeneration uses the captured plan, detail, and excerpt values after the corresponding files change.
- `test_companion_regeneration_covers_only_committed_steps_and_marks_done_status` — Deferred and `wont_do` steps never reach the model or current stories, while every committed step has visible status and a fully done story is historical.

- `test_companion_regeneration_replaces_live_story_content_instead_of_appending_it` — A current regenerated story replaces prior live source content rather than retaining an old frozen block.

- `test_companion_regeneration_promotes_keyed_draft_before_matching` — A keyed draft record becomes `created` and transfers its state and key only to its proven regenerated story.

- `test_companion_regeneration_preserves_created_key_and_reports_changed_ticket` — A matching created record keeps its Jira key and returns the regenerated story id plus key when its rendered source changes.

- `test_companion_regeneration_keeps_parked_or_dropped_record_as_story_history_only` — A dropped record with no committed covered step, or a record covering only parked steps, remains visible in story history but is excluded from current companion input.

- `test_companion_regeneration_rejects_dropped_or_mixed_record_covering_a_committed_step` — A dropped record naming a committed step, or any record mixing committed and parked coverage, produces no publishable companion result.

- `test_companion_regeneration_rejects_created_record_without_jira_key` — A non-dropped created record with a blank key is rejected rather than treated as draft.

- `test_companion_regeneration_matches_equivalent_step_orders_as_one_canonical_set` — Source `[2, 1]` and regenerated `[1, 2]` match after canonicalization.

- `test_companion_regeneration_rejects_empty_repeated_or_unparseable_source_step_sets` — Invalid existing covered-step mappings never reach key matching.

- `test_companion_regeneration_rejects_foreign_or_legacy_unproven_keyed_source` — A keyed source without captured same-plan proof cannot donate its Jira key.

- `test_companion_regeneration_rejects_repeated_jira_key_across_source_records` — One nonempty Jira key may occur in only one existing source record.

- `test_companion_regeneration_rejects_duplicate_source_or_regenerated_step_set` — More than one candidate on either side of a canonical set is rejected instead of selecting one.

- `test_companion_regeneration_rejects_changed_keyed_step_set_without_dropping_the_key` — A keyed source record without exactly one regenerated match refuses the run.

- `test_companion_regeneration_reserves_retained_dropped_story_ids` — A model response that reuses a visible dropped history ID is rejected before publication.

- `test_companion_regeneration_reports_keyed_created_to_dropped_transition` — A keyed created record that leaves committed coverage becomes dropped history and returns its story id plus Jira key for manual lifecycle action.

- `test_story_only_append_remains_permissive_when_companion_regeneration_is_unused` — `plan_tool/jira.py:read_existing_export` and `plan_tool/jira.py:_export_jira_append` retain their existing fallback and preservation behavior.

Every listed case in `tests/test_jira.py` must be green before this step is complete.

## Acceptance criteria

- Companion regeneration consumes the step 1 committed render set and does not reread live plan, detail, excerpt, or existing-source files.

- The regenerated current story collection covers every committed plan step, excludes parked steps, visibly labels each committed status, and renders through the step 2 prepared-story boundary.

- A non-dropped `jira_issue_key` is attached only when one proven same-plan source record and one regenerated story share one nonempty canonical covered-step set.

- A keyed draft renders as created; a keyed created record stays created; and a created record without a Jira key fails companion regeneration.

- A valid dropped record with no committed covered step, or a source record covering only parked steps, remains story-source history only; a dropped record naming a committed step or a mixed parked/committed source record fails companion regeneration.

- Ambiguous, duplicate, foreign, malformed, or unmatched keyed mappings return no publishable companion story result.

- A changed regenerated created story reports its regenerated story id and Jira key through companion-only result metadata.

- A keyed created record that becomes dropped history reports a separate story-id-and-Jira-key manual lifecycle follow-up, without an external Jira action.

- `uv run pytest tests/test_jira.py -q` passes.

## References

- [How to use temporary directories and files in testshttps: — Use isolated existing-source and captured-input fixtures for ownership and regeneration cases.

## Applicable guardrails

- **The plan’s `## Plan intent`, one captured input set:** Keep companion story rendering bound to the snapshot; do not add a live-file fallback.

- **The plan’s step intent, Jira-key ownership:** Carry state and keys only through the required proof path, while preserving valid historical state.

- **The plan’s `## Out of scope`, protected behavior boundaries:** Do not add external Jira operations, plan mutation, detail-grade changes, audit behavior, or prose-conflict classification.

- **The plan’s `## Risks`, story-only compatibility:** Keep ordinary Jira export and append behavior unchanged for callers that do not request a companion.

## Deferred

- Generated developer-handoff structure and current-plan-path rendering — Step 4 owns the companion document contract.

- Paired output staging, replacement, and recovery — Step 5 owns publication and target protection.

- Companion CLI flags and operator-facing created-ticket notices — Step 6 owns command wiring and presentation.
