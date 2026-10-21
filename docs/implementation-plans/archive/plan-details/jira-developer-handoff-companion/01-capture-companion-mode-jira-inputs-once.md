> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Capture companion-mode Jira inputs once without changing story-only detail tolerance

> **Historical delivery evidence — superseded 2026-08-23.** This detail records
> the completed opt-in companion design. The unified paired-export contract in
> `JIRA_FORMAT.md` replaces its story-only compatibility claims.

## Summary

Add a companion-only input snapshot in `plan_tool/jira.py` that freezes every value later needed to render the story source and developer handoff. The snapshot captures the exact plan document, selected detail inputs, source excerpts, resolved export settings, normalized destinations, complete pair identity, and existing Jira handoff records. Keep `export_jira`’s normal story-only path and its missing-detail behavior unchanged. On green, later companion steps can render from one immutable in-memory input set without rereading live files.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why companion rendering needs a single captured input boundary.
- [Input](#input) — Existing export, plan, detail, and append-mode contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Companion-only snapshot rules and compatibility boundaries.
- [Tests](#tests) — Focused capture and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — External APIs relevant to path and model handling.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.

## Why

`plan_tool/jira.py:export_jira` currently reads the plan, details, source excerpts, and existing export at different points in the export flow, while `plan_tool/jira.py:_render_step_detail` deliberately tolerates absent run-grade detail by rendering a placeholder. A companion must give both generated artifacts the same inputs, but making the existing story-only path strict would break a supported export behavior. Capture companion inputs separately so later renderers receive stable data while ordinary Jira export remains tolerant.

## Input

- **Plan source:** `plan_tool/parser.py:parse_plan`, `plan_tool/parser.py:parse_plan_text`, and `plan_tool/parser.py:split_plan_document` provide validated frontmatter and the exact Markdown body. The snapshot needs both because `plan_tool.schema.Plan` does not retain plan-body context.
- **Selected detail source:** `plan_tool/jira.py:_build_jira_grade_detail_map` selects and validates Jira-grade artifacts; run grade currently uses each `Step.detail` through `plan_tool/jira.py:_render_step_detail`. Capture the selected path, exact text, and validation result without substituting one grade for the other.
- **Source excerpts:** `plan_tool/jira.py:_render_step_files_contents` builds symbol-aware excerpts through `plan_tool/prompt_excerpt.py:build_prompt_excerpt`, including missing and unreadable-file markers. Preserve that rendered state in the snapshot rather than regenerating it later.
- **Existing story source:** `plan_tool/jira.py:read_existing_export`, `plan_tool/jira.py:_ExistingExport`, `plan_tool/jira.py:_FrozenTicket`, and `plan_tool/jira.py:_resolve_export_state` supply current append-mode records. Their permissive `None` result remains valid for story-only export, but companion capture must distinguish an absent source from an existing source that cannot prove its records.
- **Resolved export settings:** `plan_tool/jira.py:derive_jira_output_path`, `plan_tool/jira.py:compute_start_number`, and `plan_tool/jira_config.py:Epic` supply the destination, numbering, and epic values that affect rendering. Companion callers will supply both final artifact destinations; capture normalizes them and records both resolved destinations plus format as the pair identity.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/jira.py` — Add immutable companion-input capture and companion-only validation without changing the story-only renderer contract.
  - `tests/test_jira.py` — Add direct snapshot tests and retain regression coverage for ordinary export behavior.

## Implementation

- **Foundational logic — companion-only immutable export-input capture.** Introduce an internal, self-describing snapshot value in `plan_tool/jira.py` for later companion rendering. Freeze collections and copy mutable records from `Plan`, `_ExistingExport`, and `_FrozenTicket`; later code must consume captured text and values rather than live `Path` objects, mutable lists, or raw JSON dictionaries.

- **Read the plan as one source document.** Capture the plan path, validated frontmatter model, exact frontmatter text, and exact Markdown body from the same read. Use `plan_tool/parser.py:parse_plan_text` and `plan_tool/parser.py:split_plan_document` or an equivalent one-read flow; do not parse with `plan_tool/parser.py:parse_plan` and then reread the file for body context.

- **Capture actionability before either renderer starts.** Preserve every step's `scope`, `status`, and status note. Build the active render set from `plan_tool.schema.py:Plan.committed_steps`; retain parked declarations only for step 4's non-actionable history appendix. Include selected detail paths and exact bodies, per-step excerpt or missing/unreadable state, resolved epic, plan tag, format, maximum hours, first story number, both normalized destinations, pair identity, explicit rendering-contract revision values, and every existing story record's complete rendered source representation, canonical covered-step set, normalized state, and Jira key. Store predecessor output provenance separately as ownership data, not as a render input or future fingerprint input.

- **Capture target-preflight inputs independently of rendering.** Before any companion model invocation or handoff/story render, resolve each final target, collect every run- and Jira-grade detail artifact path for collision checks (without selecting or validating parked detail), and capture whether each target exists plus the SHA-256 digest of its complete raw content before parsing it for ownership. Step 5 uses this to refuse an unsafe target before work begins and later compares the proof immediately before replacement, so a human edit outside a parsed ticket field is detected. The proof remains ownership evidence rather than a render input or fingerprint field.

- **Keep destination handling narrow.** Normalize concrete companion-mode destinations during capture, including explicit paths supplied by later callers. `plan_tool/jira.py:derive_jira_output_path` remains the story destination helper; this step does not add CLI flag precedence, output publication, or handoff-path policy beyond recording the normalized paths it receives.

- **Preserve grade and actionability boundaries.** Continue using `plan_tool/jira.py:_build_jira_grade_detail_map` for Jira-grade selection and its no-fallback rule. For companion run-grade input, require every committed non-done step to have a structurally valid selected detail; record a committed done step with no selected detail as an explicit missing-source state for the later historical fallback. A present detail must be checked even for a committed done step. Do not select, validate, excerpt, or reject parked-step detail.

- **Validate stored text without repairing it.** Do not use `plan_tool/detail.py:parse_detail_response` as a companion input validator because it can add a stub section to a generated response. Use a read-only structural check over the on-disk detail text so the snapshot contains the exact bytes it validated.

- **Keep story-only tolerance intact.** Do not route the default `plan_tool/jira.py:export_jira` flow through companion-only missing-detail or existing-source checks. `plan_tool/jira.py:_render_step_detail` must still render the established no-detail marker for ordinary run-grade export, and `plan_tool/jira.py:read_existing_export` must retain its permissive append-mode fallback.

- **Separate strict companion history from append compatibility.** A companion capture must retain prior record identity, covered steps, normalized handoff state, and Jira key ownership when an existing story source is parseable. It must also distinguish an absent story source from an existing unreadable or unrecognized source, without changing `read_existing_export`’s existing meaning for story-only export.

- **Do not broaden this into a shared snapshot framework.** `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` captures a different stage-artifact contract. Keep this Jira-specific capture local; a cross-domain abstraction would be a separate refactor.

- **Leave public and CLI callers unchanged for now.** `plan_tool/__init__.py:render_jira_prompt` and `plan_tool/cli/jira_cmd.py:cmd_jira` remain on their current story-only contracts. If an internal companion switch is needed before step 6, keep it optional and disabled by default.

## Tests

### Tests for this step

- `test_companion_capture_preserves_plan_body_details_and_excerpts_after_source_changes` — Capture inputs, change the plan, selected detail, and declared source file, then prove the snapshot still contains the originally captured text and excerpt state.
- `test_companion_capture_records_complete_generated_source_pair_identity` — Assert that normalized story and companion destinations plus format form one captured pair identity, and that changing either destination makes a distinct pair.
- `test_companion_capture_selects_only_committed_steps_and_records_parked_history` — Assert that the active render set contains committed steps, while deferred and `wont_do` declarations retain only id, title, scope, and status-note history.
- `test_companion_capture_requires_selected_detail_for_each_committed_non_done_step` — Assert that companion capture rejects an absent selected detail for a committed non-done step before a renderer can run.
- `test_companion_capture_records_done_step_without_detail_for_historical_fallback` — Assert that a done step with no selected detail is represented as missing input rather than rejected or replaced with invented content.
- `test_companion_capture_rejects_malformed_present_done_detail` — Assert that a present but structurally invalid selected detail fails even when its step is done.
- `test_companion_capture_ignores_missing_or_malformed_parked_detail` — Assert that parked-step detail is not selected or validated and cannot block active companion output.
- `test_companion_capture_keeps_jira_grade_selection_without_run_grade_fallback` — Assert that Jira-grade capture uses only validated Jira-grade paths and never reads the run-grade detail as a substitute.
- `test_companion_capture_preserves_existing_ticket_state_and_key_ownership` — Assert that captured existing records retain their canonical covered-step set and that a keyed draft is captured as created through `plan_tool/jira.py:_resolve_export_state`.
- `test_companion_capture_preserves_complete_existing_record_representation` — Assert that the snapshot retains all rendered record data as well as covered-step, state, and Jira-key mappings for the shared render-input fingerprint.
- `test_companion_capture_records_raw_target_content_state_proofs` — Assert that existing and absent story and handoff targets retain distinct existence/digest proofs even when their parsed ownership data is the same.
- `test_companion_target_preflight_rejects_any_grade_detail_before_rendering` — An output equal to any run- or Jira-grade detail artifact, including the unselected grade, is rejected before model or handoff rendering work.
- `test_companion_capture_distinguishes_absent_story_source_from_unparseable_existing_source` — Assert that companion capture rejects an existing source it cannot establish while ordinary append-mode export retains its current fallback behavior.
- `test_predecessor_companion_provenance_is_not_a_render_input` — Assert that predecessor ownership provenance can be retained for later ownership checks without appearing in the snapshot’s render-input projection.
- `test_story_only_run_grade_export_still_allows_missing_detail` — Assert that `plan_tool/jira.py:export_jira` still succeeds and renders the existing missing-detail marker when companion capture is not requested.

Every listed case in `tests/test_jira.py` must be green before this step is complete.

## Acceptance criteria

- Companion-only capture produces one immutable value containing the exact plan document, committed render set, parked-step history, selected details and excerpt states only for committed steps, complete existing story records, resolved export settings, normalized destinations, the two-destination-plus-format pair identity, and rendering-contract revisions.
- Changing an input file after capture cannot change data later read from the snapshot.
- Companion capture rejects a missing selected detail on a committed non-done step and a malformed present detail on a committed step before rendering or publication.
- A committed done step without selected detail remains represented as a deliberate missing-source state, while parked detail is outside companion validation.
- Jira-grade capture never falls back to a run-grade detail.
- Predecessor companion provenance is available only for ownership validation and is absent from captured render inputs.
- Each target has an existence and complete-content digest proof for final ownership confirmation; that proof is not a render input or fingerprint field.
- Target preflight rejects collision, prohibited location, foreign ownership, and every run- or Jira-grade detail artifact before companion model or renderer work begins.
- Story-only `export_jira` retains its current missing-detail placeholder behavior and append-mode compatibility.
- All listed `tests/test_jira.py` cases pass.

## References

- [pathlib — Object-oriented filesystem pathshttps: — Use for stable path resolution and normalized destination handling.
- [Pydantic BaseModel APIhttps: — Use for safely copying the validated plan model into an immutable snapshot boundary.

## Applicable guardrails

- **The plan’s “## Plan intent”, one captured source state:** Keep this step focused on collecting the values both future artifacts need; do not render, publish, or change the developer-facing handoff here.
- **The plan’s “## Step intent”, predecessor provenance boundary:** Retain predecessor provenance only for later ownership checks and keep it out of render inputs.
- **The plan’s “## Out of scope”, existing contracts:** Do not change detail-grade schemas or defaults, mutate plans, add external Jira behavior, or introduce audit, reconcile, or source-conflict classification work.
