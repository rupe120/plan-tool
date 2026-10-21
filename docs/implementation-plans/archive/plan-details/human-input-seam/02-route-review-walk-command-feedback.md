> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Route review-walk command and feedback reads through the seam without changing terminal behavior

## Summary

Update `plan_tool/review_walk.py` so one human-input provider serves every interactive read in a single `walk_recommendations` run. Route only the annotation command and free-text feedback reads in `_prompt_for_annotation` through the provider delivered by step 1. Keep `input_fn`, action dispatch, output, and annotation persistence unchanged for terminal mode. Green behavior proves that remote resolutions drive the same persisted annotation and feedback-steering outcomes as terminal input.

## Table of Contents

- [Summary](#summary) — The completed step at a glance.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The direct reads this step routes through the seam.
- [Input](#input) — The step-1 provider and walk-state contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files changed by the slice.
- [Implementation](#implementation) — Provider construction, prompt identities, and behavior that stays fixed.
- [Tests](#tests) — Terminal and remote review-walk coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for the terminal and filesystem-backed paths.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this integration.
- [Deferred](#deferred) — Nearby work this slice leaves out.

## Why

`plan_tool/review_walk.py:_prompt_for_annotation` reads the annotation command and feedback text directly from `input_fn`, so a remote operator cannot answer either read even after a provider exists. Routing those two reads through the same provider gives the plan one real interactive proof while keeping the review walk’s annotation, feedback, and terminal behavior intact.

## Input

- **Step 1 provider contract:** Step 1 delivers the typed request, resolution, and provider-selection interface in `plan_tool/human_io.py`. Use its landed interface as the source of truth for request construction and returned text.
- **Walk state:** Preserve `plan_tool/review_walk.py:WalkState`; its `pending_feedback` field remains the handoff from the feedback read to the next action dispatch.
- **Persistence contract:** Preserve `plan_tool/review_persistence.py:update_annotation` use in `plan_tool/review_walk.py:walk_recommendations`; remote answers change only where the text comes from.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — Lazily construct and share one provider per walk, then route the two approved reads through typed requests.
  - `tests/test_review_walk.py` — Keep terminal regressions and add direct remote walk coverage.

## Implementation

- **Foundational logic:** Construct one human-input provider at the first actual read in each `plan_tool/review_walk.py:walk_recommendations` invocation, then use it for every later annotation-command and feedback-text read in that invocation.

- **Keep provider selection at the walk boundary.** When `walk_recommendations` first needs a human response, create the step-1 provider once from the existing `input_fn`. Pass that provider into `plan_tool/review_walk.py:_prompt_for_annotation` rather than selecting a mode for each prompt or caching a provider across separate walks. A walk with no pending prompt must return without validating remote configuration.

- **Keep test injection narrow.** Add an optional keyword-only provider injection to `plan_tool/review_walk.py:walk_recommendations` so `tests/test_review_walk.py` can drive the request contract without a live terminal. Calls that omit it must use the step-1 factory and retain the existing `input_fn` default.

- **Route only the two direct reads.** Replace the command read and the `feedback:` read in `plan_tool/review_walk.py:_prompt_for_annotation`. Do not route action dispatch, `output_fn`, annotation persistence, or the automatic apply path through the provider.

- **Give each request a stable purpose and fresh identity.** Command reads must use prompt id `review-walk.annotation`; feedback reads must use prompt id `review-walk.feedback`. Create a distinct request identity for every actual read, including the command read that follows feedback, so remote records cannot collide or reuse an earlier resolution.

- **Preserve text handling exactly.** Feed returned command text through the existing command normalization before action selection. Feed returned feedback text through the existing feedback trimming before storing it in `pending_feedback` and the annotation note. The terminal provider must receive the same displayed prompt strings that `input_fn` receives now.

- **Do not hide remote-provider failures.** Let configuration, request-record, and resolution-validation failures from the step-1 provider reach the walk. Do not fall back to terminal input, create a default answer, or convert a provider error into an annotation.

- **Leave callers unchanged.** `plan_tool/cli/review_cmd.py:cmd_review`, `plan_tool/cli/review_cmd.py:cmd_review_walk`, `plan_tool/cli/reconcile.py:_walk_saved`, `plan_tool/cli/reconcile.py:_walk_with_reconcile_phase`, `plan_tool/cli/completeness_phases.py:_run_apply_walk`, and `plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply` must continue calling `walk_recommendations` without new wiring. Their start and TTY decisions stay outside this step.

## Tests

### Tests for this step

Green-before-done gate: every added or changed case in `tests/test_review_walk.py` must pass before this step is complete.

- `test_terminal_annotation_command_preserves_prompt_and_annotation` — With remote mode unset, the supplied `input_fn` receives the unchanged annotation prompt and its answer persists the same applied annotation.
- `test_terminal_feedback_preserves_note_and_action_steering` — Terminal feedback remains trimmed, stored in `WalkState.pending_feedback`, passed to the action handler, and persisted as the annotation note.
- `test_provider_is_constructed_once_for_multi_read_walk` — A feedback flow with several reads uses one provider instance for the whole walk.
- `test_remote_annotation_command_request_uses_annotation_prompt_id` — A remote command request carries `review-walk.annotation`; a matching resolution resumes the walk and persists the normal annotation.
- `test_remote_feedback_request_uses_feedback_prompt_id_and_distinct_request_ids` — A remote feedback flow emits the feedback prompt id, uses distinct request identities for each read, and preserves the resolved text as action steering and annotation note.
- `test_apply_all_does_not_call_human_input_provider` — A walk already in `WalkState.yes_to_all` auto-applies without creating a human-input request.
- `test_walk_without_pending_recommendations_skips_provider_configuration` — A completed walk returns without validating remote configuration or reading input.

## Acceptance criteria

- `plan_tool/review_walk.py:walk_recommendations` constructs or receives exactly one provider when a walk needs a prompt and shares it with every `_prompt_for_annotation` call.
- The two direct reads in `plan_tool/review_walk.py:_prompt_for_annotation` use `review-walk.annotation` and `review-walk.feedback` respectively; each read has a distinct request identity.
- With remote mode unset, existing `input_fn` prompt text, command handling, feedback handling, action dispatch, and annotation persistence remain unchanged.
- With remote mode configured, a matching resolution can complete an annotation-command interaction and a feedback interaction with the same persisted outcomes as terminal input.
- Provider failures do not create fallback answers or terminal reads.
- `tests/test_review_walk.py` passes.

## References

- [Built-in Functions — input()https: — Preserve the supplied terminal callback’s prompt-and-text behavior.
- [pathlib — Object-oriented filesystem pathshttps: — Inspect remote request and resolution records in the integration tests.
- [json — JSON encoder and decoderhttps: — Write matching resolution fixtures for the remote walk tests.
- [How to monkeypatch/mock modules and environmentshttps: — Isolate remote configuration and provider construction in tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, single-consumer proof:** Change only `plan_tool/review_walk.py`; do not migrate another production input route.
- **The plan’s “## Step intent”, command and feedback proof:** Cover both approved reads and retain annotation persistence.
- **The plan’s “## Out of scope”, walk-start behavior:** Do not change caller-side TTY checks, `sys.stdin.isatty()` handling, or other logic that decides whether a walk starts.
- **The plan’s “## Out of scope”, remote-answer policy:** Do not add answer defaults, advisory behavior, transport variants, timeouts, authorization, or resolution-conflict rules.
- **The plan’s declared risk profile:** Let the step-1 provider own configured-directory filesystem effects; `plan_tool/review_walk.py` must only supply request data and consume returned text.

## Deferred

- Remaining direct-input and human-availability routes — The plan’s `## Deferred` section assigns fresh inventory and follow-up migration to #322.
- Caller-side walk-start and terminal-availability behavior — The plan’s `## Out of scope` section keeps these CLI decisions outside this integration.
- Operator protocol documentation — Step 3 owns `HUMAN_IO_FORMAT.md` and the backlog record for the wider migration.
