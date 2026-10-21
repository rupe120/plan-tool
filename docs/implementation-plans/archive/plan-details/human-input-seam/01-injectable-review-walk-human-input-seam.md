> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add an injectable review-walk human-input seam with an always-ask filesystem remote provider

## Summary

Add `plan_tool/human_io.py` as the small, typed provider boundary that step 2 will use for review-walk prompts. The module selects either the existing terminal callback or a filesystem-backed remote provider once when constructed. Remote calls publish a complete request record without overwriting a final path and return only after a matching complete resolution is present. Add focused unit coverage in `tests/test_human_io.py` and document the test seam in `TESTING.md`.

## Table of Contents

- [Summary](#summary) — The completed step at a glance.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The missing boundary this step establishes.
- [Input](#input) — Existing callback and record contracts this step supports.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files created and documentation updated.
- [Implementation](#implementation) — Provider contract, filesystem behavior, and limits.
- [Tests](#tests) — Focused unit coverage for the new seam.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for terminal, filesystem, JSON, and pytest behavior.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Integration and wider migration work left out of this step.

## Why

`plan_tool/review_walk.py:walk_recommendations` already accepts an injectable `InputFn`, but that callback only represents immediate terminal input. The vertical slice needs one small boundary that can preserve that callback when remote mode is unset and can instead wait for an operator-owned filesystem resolution when remote mode is selected. Defining and testing the record contract before wiring a caller keeps the first proof narrow and makes step 2 an integration change rather than a second design exercise.

## Input

- **Terminal callback shape:** Match `plan_tool/review_walk.py:InputFn`, which accepts the displayed prompt and returns text. The default provider must pass that prompt through unchanged.
- **Future consumer:** `plan_tool/review_walk.py:walk_recommendations` and `_prompt_for_annotation` remain unchanged in this step. Step 2 will construct one provider and use the typed requests defined here for its command and feedback reads.
- **Verification limit:** `tests/test_human_io.py` proves provider and record behavior with `tmp_path`; a real review-walk interaction belongs to step 2.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/human_io.py` — Define the typed request and resolution values, provider factory, remote filesystem behavior, and clear failure type.
  - `tests/test_human_io.py` — Add isolated unit tests for configuration, records, blocking, validation, and collision safety.

- **Existing files (edits only):**
  - `TESTING.md` — Add a concise human-input seam recipe near `## Backend fallback seams` explaining how tests inject terminal input or arrange a remote resolution without waiting indefinitely.

## Implementation

- **Foundational logic:** Select one human-input provider, then turn each typed request into either the existing terminal callback result or a matching filesystem resolution.

- **Expose a small typed boundary in `plan_tool/human_io.py`.** Define `HumanInputRequest` with the generated `request_id`, stable `prompt_id`, and prompt text, plus `HumanInputResolution` carrying the matching request id and returned text. Define a callable type such as `HumanInputProvider` and a factory such as `make_human_input_provider` that accepts the existing terminal callback and returns that callable.

- **Select the provider at construction time.** With `PLAN_TOOL_HUMAN_IO` unset, return a terminal provider that delegates to the supplied callback. With `PLAN_TOOL_HUMAN_IO=remote`, validate `PLAN_TOOL_HUMAN_IO_DIR` before any request write and return a provider bound to that directory. Reject unsupported explicit modes rather than silently treating a configuration typo as terminal mode.

- **Keep the default path behavior-neutral.** The terminal provider must give `plan_tool/review_walk.py:InputFn` the exact prompt text and return its text through the resolution value. It must not trim, normalize, add defaults, or inspect terminal availability.

- **Use one directory and fixed record names for remote mode.** For a request id, use `<request_id>.request.json` for the request and `<request_id>.resolution.json` for the answer in `PLAN_TOOL_HUMAN_IO_DIR`. Serialize the request id, prompt id, and prompt text. Require the resolution record to contain the same request id and a text value.

- **Publish complete final records without clobbering.** Serialize each record before publishing it. The provider uses `plan_tool.fileio.py:durable_create_text` for its request: that helper fsyncs a sibling temporary file, then hard-links it to the final path so a collision fails without replacement. The operator-side protocol uses the same complete-before-visible rule for a resolution. Poll only the final resolution path, ignore an in-progress temporary path, and continue waiting until a complete final record appears. Do not use `plan_tool/fileio.py:atomic_write_text`, because its replacement behavior conflicts with the required existing-record refusal.

- **Validate paths before joining them.** Treat a request id as a single safe filename component so it cannot escape the configured directory. Require the configured directory to already exist, be a directory, and support the reads and writes the provider needs; do not create it as a side effect of provider selection.

- **Always ask in remote mode.** Poll for the matching resolution after the request record is created. A missing resolution must keep waiting; it must not return a default, advisory result, or fallback answer. A malformed resolution or mismatched request id must fail clearly and leave both records intact.

- **Keep the module narrow.** Do not import or modify `plan_tool/review_walk.py` here. Do not add a provider registry, alternate transport interface, timeout, authorization rule, or conflict policy; the factory only distinguishes the terminal path from this one filesystem remote path.

- **Document the test seam in `TESTING.md`.** State that unit tests inject a terminal callback directly, use `monkeypatch` for remote configuration, use `tmp_path` for records, and arrange a matching resolution before waiting for a remote result.

## Tests

### Tests for this step

Green-before-done gate: every test below must pass in `tests/test_human_io.py` before this step is complete.

- `test_terminal_provider_forwards_the_exact_prompt_to_input_fn` — The unset-mode provider calls the supplied callback once with unchanged prompt text and returns its text.
- `test_remote_mode_requires_an_existing_usable_directory` — Missing, non-directory, or unusable `PLAN_TOOL_HUMAN_IO_DIR` values fail before a request record exists.
- `test_unknown_human_io_mode_is_rejected` — An explicit unsupported `PLAN_TOOL_HUMAN_IO` value fails instead of falling back to terminal input.
- `test_provider_mode_is_fixed_when_constructed` — Later environment changes do not change an already-created provider’s selected mode.
- `test_remote_request_record_preserves_request_identity_and_prompt` — A remote request record contains the request id, prompt id, and prompt text supplied in `HumanInputRequest`.
- `test_remote_waits_for_matching_text_resolution` — The provider remains pending after request creation and returns only after a matching text resolution is written.
- `test_remote_ignores_in_progress_resolution_until_complete_publication` — A sibling temporary resolution does not become an answer; the provider returns only after the complete final record is published.
- `test_remote_rejects_malformed_resolution` — Invalid JSON or a resolution without the required text contract raises clearly and does not alter either record.
- `test_remote_rejects_mismatched_resolution_request_id` — A resolution for another request id is rejected rather than being accepted as the current answer.
- `test_existing_request_record_is_never_overwritten` — A request-path collision fails and preserves the existing bytes.
- `test_existing_resolution_record_is_never_overwritten` — A pre-existing resolution path fails without replacement and without creating a new request.
- `test_request_id_cannot_escape_the_remote_directory` — A path-bearing request id is rejected before it can name a record outside the configured directory.

## Acceptance criteria

- `plan_tool/human_io.py:make_human_input_provider` returns a terminal provider when `PLAN_TOOL_HUMAN_IO` is unset, and that provider preserves the supplied terminal callback’s prompt and response text.
- With `PLAN_TOOL_HUMAN_IO=remote`, a valid configured directory receives one complete, no-clobber `<request_id>.request.json` record containing the typed request identity and prompt.
- A remote call returns text only from a complete matching `<request_id>.resolution.json` record, remains pending while its final path is absent, and ignores an in-progress temporary record.
- Invalid remote configuration, unsafe request ids, malformed resolutions, mismatched resolution ids, and either record-path collision raise without overwriting a record.
- `tests/test_human_io.py` passes, and `TESTING.md` tells future tests how to inject or resolve this seam without a live terminal.

## References

- [Built-in Functions — input()https: — Preserve the terminal callback’s prompt-and-text behavior.
- [pathlib — Object-oriented filesystem pathshttps: — Validate configured directories and derive record paths safely.
- [json — JSON encoder and decoderhttps: — Serialize request records and reject invalid resolution payloads.
- [How to monkeypatch/mock modules and environmentshttps: — Isolate environment and filesystem configuration in unit tests.

## Applicable guardrails

- **The plan’s “## Plan intent”, single-consumer proof:** Build only the reusable provider and record contract needed for the review-walk slice; do not migrate another production input route.
- **The plan’s “## Out of scope”, caller-start behavior:** Do not change terminal-availability checks or command paths that decide whether a review walk begins.
- **The plan’s “## Out of scope”, remote-answer policy:** Remote mode must wait for a resolution and must not gain defaults, advisory events, timeout behavior, authorization, or conflict handling.
- **The plan’s declared risk profile:** Limit filesystem effects to the explicitly configured request and resolution directory, and make collision failures preserve existing records.

## Deferred

- `plan_tool/review_walk.py:walk_recommendations` and `_prompt_for_annotation` integration — Step 2 owns construction of the provider and routing of the two approved reads.
- `HUMAN_IO_FORMAT.md` and the wider migration record — Step 3 owns the operator protocol and backlog update.
- Remaining direct-input and human-availability routes — #322 owns a fresh inventory and any justified follow-up migration.
