# Step 6 — Document bounded stage feedback and its feedback-free re-gate boundary across roadmap references

## Summary

Align the roadmap format reference, operator guides, architecture description, capability catalog, run-log contract, and generated CLI reference with the per-stage selection rule delivered by step 5. Distinguish initial authoring, a re-entered stage with active `open` feedback, and a feedback-free re-gate without presenting `--from-stage` as automatic broad regeneration. Keep `ROADMAP_FORMAT.md` as the detailed contract and use the other guides for their own audiences. Green means every public roadmap reference describes the same boundary, generated CLI output is current, and `tests/test_roadmap_format.py` prevents the old rewrite promise from returning.

## Table of Contents

- [Summary](#summary) — The documentation outcome and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current documentation conflict this step removes.
- [Input](#input) — The shipped route, telemetry, and generated-reference contracts to read.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-guard changes.
- [Implementation](#implementation) — How each reference presents the bounded route.
- [Tests](#tests) — Documentation drift checks and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Reviewable completion conditions.
- [References](#references) — Test guidance for the drift guard.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this documentation work.
- [Deferred](#deferred) — Work that needs a later product or implementation step.

## Why

Current roadmap guides describe `--from-stage` as rewriting every stage from its entry point upward, including examples that promise downstream regeneration after an unrelated hand edit. Step 5 changes the re-entry decision: active feedback is the only existing-stage path that invokes the bounded feedback operation, while feedback-free stages validate in memory and leave canonical roadmap state unchanged. Leaving both stories published would send operators toward calls that no longer regenerate or overwrite work, and it would hide the bounded feedback contract that protects untouched content.

## Input

- **Step 5’s landed route is authoritative.** Read `plan_tool/roadmap.py:run_roadmap`, `plan_tool/roadmap.py:_load_and_regate_below`, `plan_tool/roadmap.py:RoadmapStage`, `plan_tool/roadmap.py:STAGES`, and `plan_tool/roadmap.py:RoadmapResult` after step 5 lands. Use the code’s final names and result states when prose or examples need an identifier; do not copy a proposed name from this plan when the landed implementation differs.

- **Feedback activation stays code-owned.** Ground the documentation in `plan_tool/roadmap_artifacts.py:FeedbackState` and the stage selection logic around `plan_tool/roadmap.py:_has_open_feedback`. The documentation must distinguish an active `open` row from retained feedback that does not activate a stage.

- **Telemetry remains redacted.** Read the landed producer calls and event shapes in the run-log module, including `RevisionFeedbackDelivered` and `RoadmapStageWritten`. `DATA_CONTRACT.md` must describe the actual write and invocation boundaries without adding reviewer request text, model replies, or invented fields.

- **The CLI reference is generated.** `docs/cli/roadmap.md` comes from the parser registered by `plan_tool/cli/roadmap_cmd.py:register` through `plan_tool/cli_reference.py:write_reference`. Step 5 supplies any changed `--from-stage` help; this step regenerates the committed reference instead of editing it by hand.

- **Worked examples are executable documentation.** `tests/test_roadmap_format.py:test_every_artifact_example_parses`, `tests/test_roadmap_format.py:test_every_artifact_example_round_trips`, and `tests/test_roadmap_format.py:test_the_revision_example_clears_its_gates_against_its_predecessor` define the format examples that must remain valid.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Update the source-of-truth routing description, feedback lifecycle, revision-route table, and feedback example so they explain bounded stage feedback and the no-write re-gate path.
  - `DATA_CONTRACT.md` — Correct the per-stage feedback-delivery and stage-write event descriptions to match the landed telemetry boundary and redaction contract.
  - `README.md` — Replace the broad-rewrite command summary and re-entry-cost guidance with concise selection-rule guidance.
  - `RUNBOOK.md` — Update the quick reference and roadmap workflow so operator instructions select the stage that owns active feedback and do not promise feedback-free downstream regeneration.
  - `CAPABILITIES.md` — Describe the roadmap capability as per-stage bounded feedback plus feedback-free re-gating, not as a broad re-entry writer.
  - `docs/ARCHITECTURE.md` — Update the Roadmap architecture boundary, module responsibilities, and re-entry behavior to match the landed stage route.
  - `docs/ROADMAP_WALKTHROUGH.md` — Rework the decision and feedback walkthroughs so their commands and outcomes match the bounded selection rule.
  - `docs/ROADMAP_DEMO_ORCHESTRATION.md` — Update the review-loop script and demo expectations so it demonstrates active feedback and a feedback-free re-gate accurately.
  - `docs/cli/roadmap.md` — Regenerate from the argparse parser after step 5’s help text lands.
  - `tests/test_data_contract.py` — Keep the generated project-configuration contract aligned with the documented stage-limit keys.
  - `tests/test_roadmap_format.py` — Add a focused cross-guide drift guard for the selection rule and update existing example assertions when their prose changes.

## Implementation

- **Use one three-way selection rule everywhere.** Document that a fresh stage still follows its authoring path, a re-entered stage with active `open` feedback uses the bounded stage-feedback route, and a re-entered stage without active feedback only re-gates admitted state. Keep the second and third cases visibly separate.

- **Make the feedback-free boundary explicit.** State that a feedback-free re-gate performs deterministic admission and validation but makes no backend request, canonical artifact rewrite, or seed-state publication. Describe run-log lifecycle effects only as the landed implementation records them; do not imply that “no write” suppresses every observability record.

- **Document concurrent-reviewer refusal.** Explain in `ROADMAP_FORMAT.md` and operator guidance that feedback remains reviewer-owned mutable input. If the route observes it changed after bounded revision preflight, including before a correction prompt, it refuses before publication rather than overwriting the current row; the reviewer reruns against current feedback. Keep this separate from the baseline's semantic source-drift message and do not imply the tool merges concurrent feedback changes or preserves an uncoordinated raw write that races after the final check during atomic replacement.

- **Document whole-prefix enrollment recovery.** State in the runbook that baseline enrollment records one requested contiguous prefix as one recoverable bootstrap generation. A retry first recovers an interrupted enrollment and then reports a fully enrolled prefix; it never asks an operator to repair a half-enrolled prefix by hand.

- **Describe bounded feedback by its authority, not an implementation recipe.** In `ROADMAP_FORMAT.md`, explain that the stage route receives only the selected feedback context and returns the closed operation result delivered by steps 1–3. It may publish only an accepted, gate-clean candidate and must preserve content outside its permitted operations. Keep the detailed operation schema in this format reference; other guides should link to it rather than duplicate the wire contract.

- **Publish the response limits and their recovery action once.** In `ROADMAP_FORMAT.md`, state the stage route's fixed limits: 32 active feedback items, a 32 KiB UTF-8 JSON reply, a 4 KiB UTF-8 prose amendment, and one material operation per active feedback id. State that an excess is `invalid`, identifies the value and limit, and asks the reviewer to split the feedback; it never partially merges or retries. Keep summaries in operator guides brief and link them to this source-of-truth limit contract.

- **Document the project tightening block.** In `DATA_CONTRACT.md` and `ROADMAP_FORMAT.md`, document `.plan-tool/config.json`'s project-only `roadmap_feedback.stage_limits` object and its three numeric keys from the `json_object_contracts` registry. It can lower, never raise, the documented item, response-byte, and prose-byte ceilings; the one-material-operation rule stays fixed. Explain that invalid config fails command preflight before a backend call and that each run snapshots valid limits once. Do not document a user-level fallback or a setting that changes canonical artifact comments.

- **Remove the broad-reentry vocabulary as a class.** Sweep the listed roadmap references for claims that `--from-stage` rewrites every later stage, regenerates downstream work after any hand edit, or sends every re-entered stage to the model. Replace each with the per-stage decision rule or remove the stale workflow when no supported action remains.

- **Describe actual-write summaries.** State that CLI output lists only artifacts actually published and that feedback-free stages re-gate without joining that list. Send an operator who needs another construct or prose change to feedback; do not retain old copy-aside or hand-edit-preservation guidance, because admitted direct semantic edits fail before a rewrite.

- **Keep route ownership clear.** Let `ROADMAP_FORMAT.md` own the feedback and operation contract, `RUNBOOK.md` own operator actions, `docs/ROADMAP_WALKTHROUGH.md` and `docs/ROADMAP_DEMO_ORCHESTRATION.md` show concrete outcomes, `docs/ARCHITECTURE.md` explain module ownership, and `README.md` and `CAPABILITIES.md` remain concise summaries.

- **Preserve existing route boundaries.** Keep `--revise-feedback` selector-bound, structural rewrite evidence-bound, and feedback-free re-gating non-authoring. Do not describe `--from-stage` as a fallback recovery or a general patch mechanism.

- **Update telemetry prose from the producer.** Revise `DATA_CONTRACT.md` around `RevisionFeedbackDelivered` and `RoadmapStageWritten` so their cardinality, trigger, and omitted data match the landed `plan_tool/run_log.py` calls. Retain the rule that reviewer requests and proposed responses never enter run logs.

- **Regenerate the CLI reference.** After confirming `plan_tool/cli/roadmap_cmd.py:register` has the landed help text, run `python -m plan_tool.cli_reference --write`. Do not hand-edit `docs/cli/roadmap.md`.

- **Add a guide-level drift guard.** Extend `tests/test_roadmap_format.py` beside `_STRUCTURAL_ROUTE_GUIDES` and `test_structural_rewrite_route_guidance_sweep_covers_every_named_public_guide`. Check the eight narrative and CLI guides in this step’s file list for the active-feedback and feedback-free outcomes, and check `DATA_CONTRACT.md` separately for the redacted telemetry boundary. Keep the assertions scoped to the relevant sections so unrelated uses of “rewrite” cannot create false failures.

## Tests

- `test_stage_feedback_route_guidance_sweep_keeps_active_feedback_and_feedback_free_regate_distinct` — asserts every selected public guide says active feedback is the only existing-stage backend path and feedback-free re-gating does not publish canonical changes.
- `test_stage_feedback_telemetry_reference_matches_landed_writer_contract` — asserts `DATA_CONTRACT.md` matches the landed feedback-delivery and stage-write event boundary without documenting reviewer or model prose.
- `test_stage_feedback_limit_guidance_matches_the_landed_contract` — asserts the source-of-truth format guide and operator summaries retain the four limits, the invalid outcome, and the split-feedback action without duplicating a competing wire schema.
- `test_stage_feedback_limit_config_guidance_matches_the_project_only_contract` — asserts the format and data-contract references name the registry-covered, project-only, lowering-only keys, the fixed material-operation rule, the snapshot, and the fail-closed command-preflight error.
- `test_stage_feedback_concurrent_input_guidance_matches_the_landed_contract` — asserts format and operator guidance distinguish observed concurrent-feedback refusal from semantic source drift, direct the reviewer to rerun against current feedback, and do not promise raw-editor compare-and-swap preservation.
- `test_baseline_enrollment_prefix_recovery_guidance_matches_the_landed_contract` — asserts enrollment guidance describes one recoverable prefix and retry-after-recovery behavior without a manual half-enrollment workaround.
- `test_every_artifact_example_parses` — confirms any updated `ROADMAP_FORMAT.md` feedback example still parses through the real artifact parser.
- `test_every_artifact_example_round_trips` — confirms the updated example renders and parses without schema drift.
- `test_the_revision_example_clears_its_gates_against_its_predecessor` — confirms the revised before-and-after feedback example remains gate-clean against its predecessor.

### Verification (non-code step)

The test-authoring gate does not apply because this is a non-code step; it applies only to feature and refactor changes. Verify the documentation change with:

1. Run `uv run pytest tests/test_roadmap_format.py -q`.
2. Run `uv run pytest tests/test_data_contract.py -q`.
3. Regenerate `docs/cli/roadmap.md` with `python -m plan_tool.cli_reference --write`, then run `uv run pytest tests/cli/test_cli_reference.py -q`.
4. Search the listed roadmap references for stale promises such as “every stage from N up is rewritten”, copy-aside advice for direct semantic hand edits, and “regenerate only downstream work”; each remaining match must describe a supported current behavior.
5. Review changed Markdown links and headings, including the `ROADMAP_FORMAT.md` links from `README.md`, `RUNBOOK.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `docs/ROADMAP_DEMO_ORCHESTRATION.md`.

## Acceptance criteria

- Every listed operator and architecture guide distinguishes initial authoring, active-feedback revision, and feedback-free re-gating.
- No listed guide promises that `--from-stage` rewrites or regenerates an existing feedback-free stage.
- `ROADMAP_FORMAT.md` states the bounded operation authority and links readers to the operator workflow without duplicating a second schema.
- `ROADMAP_FORMAT.md` states the fixed 32-item, 32 KiB, 4 KiB, and one-material-operation-per-feedback limits, including the invalid split-feedback outcome; operator summaries link to that source of truth.
- `ROADMAP_FORMAT.md` and `DATA_CONTRACT.md` describe only the project-level `roadmap_feedback.stage_limits` lowering-only configuration, including validation, snapshot timing, and the absence of a user-level fallback.
- `ROADMAP_FORMAT.md` and operator guidance explain observed concurrent-feedback refusal before retry/write and the one-prefix enrollment recovery boundary without promising feedback merging, raw-editor compare-and-swap preservation, or manual repair of a partial enrollment.
- The project-configuration registry and `tests/test_data_contract.py` name the same three stage-limit leaves that the format and data-contract references describe.
- `DATA_CONTRACT.md` matches the landed `plan_tool/run_log.py` event fields and explicitly retains redaction of reviewer and model prose.
- `docs/cli/roadmap.md` is regenerated from `plan_tool/cli/roadmap_cmd.py:register`, and `tests/cli/test_cli_reference.py` reports no drift.
- Updated format examples parse, round-trip, and clear their existing gate checks.
- `uv run pytest tests/test_roadmap_format.py -q` and `uv run pytest tests/test_data_contract.py -q` pass.

## References

- [pytest: How to Monkeypatch/Mock Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use the project’s normal pytest patterns when adding documentation drift assertions around code-owned route facts.

## Applicable guardrails

- **The plan’s “Plan intent”, bounded stage operations.** Document the closed, deterministic stage-feedback contract and do not present the route as whole-artifact re-authoring.

- **The plan’s “Step intent”, reference alignment.** Limit changes to operator guidance, architecture boundaries, examples, CLI reference output, and run-log semantics for the shipped selection rule.

- **The plan’s “Out of scope”, broad behavior changes.** Do not add documentation that suggests a general patch language, a feedback-free regeneration path, changed gate behavior, or new recovery authority.

- **The plan’s “Out of scope”, neighboring feedback routes.** Preserve the documented boundaries of `--revise-feedback` and structural rewrite; this step must not widen either route while describing stage feedback.

- **Step 5 dependency.** Treat the landed implementation as the source of truth and correct this detail’s documentation from its final behavior rather than from the current broad-reentry prose.

## Deferred

- A new recovery or feedback-free regeneration command — requires a separate operator-facing design and implementation step.
- Telemetry fields not implemented by step 5 — documentation must not create a new run-log schema by implication.
