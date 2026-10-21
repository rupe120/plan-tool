> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Use typed generic reference-research results without changing checkpoint, plan, or References replacements

## Summary

Add a small typed result for generic developer-document research in `plan_tool/create.py` and update its callers and tests. The result separates populated references, a valid empty array, and an unparseable reply while retaining `Reference` as the owner of entry validation. It establishes the parsing and checkpoint handoff that step 2 extends with bounded repair; plan rendering and iteration References replacement remain unchanged. On green, callers can inspect the research outcome without treating malformed output as deliberate emptiness.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the result-contract refactor.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The ambiguity this result type removes.
- [Input](#input) — Existing parser, caller, and checkpoint contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed in this step.
- [Implementation](#implementation) — Required result shape and unchanged boundaries.
- [Tests](#tests) — Focused coverage for all three outcomes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for the typed JSON result.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Later work deliberately left out.

## Why

`plan_tool/create.py:propose_references_from_claude` uses `None` for malformed output and `[]` for a parseable empty array, so callers can erase the difference through a false-value check. The create flow needs a typed handoff now so the later bounded repair and failure-boundary steps can act on an unparseable result without changing the meaning of valid empty research.

## Input

- **Generic response contract:** `plan_tool/create.py:_REFERENCE_RESPONSE_CONTRACT` and `plan_tool/create.py:_parse_references_json` accept a JSON array with surrounding chatter and retain only entries that satisfy `plan_tool/create.py:Reference`.
- **Research boundary:** `plan_tool/create.py:propose_references_from_claude` owns the generic developer-document call, progress result, resume lookup, and checkpoint write.
- **Caller boundaries:** `plan_tool/create.py:_prepare_create_plan` and `plan_tool/create.py:_converge_create_plan` consume generic research before plan rendering or an iteration References patch.
- **Checkpoint contract:** `plan_tool/create.py:_REFERENCES_CHECKPOINT_NAME` and `plan_tool/create.py:_references_input_hash` retain their existing names, inputs, payload format, and resume behavior.
- **Test limit:** Canned replies in `tests/test_create.py` prove result handling and side effects, not real-model response quality.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add the typed generic-research result, return it from the generic parser and proposal boundary, and adapt internal consumers without changing their existing rendering or checkpoint policies.
  - `tests/test_create.py` — update generic-research assertions and mocked proposal results to use the typed contract.

## Implementation

- **Foundational logic: discriminated generic-reference result.** Define one small frozen result type beside `plan_tool/create.py:Reference`, with a closed outcome vocabulary for populated, empty, and unparseable replies. A populated outcome must carry retained `Reference` entries; empty and unparseable outcomes must remain distinguishable even though neither carries entries.

- **Keep `Reference` validation in place.** Have `plan_tool/create.py:_parse_references_json` use `plan_tool/response_contract.py:JsonResponseContract.decode` as it does now, retain chatter tolerance and invalid-row filtering, and convert the parser result into the typed outcome. Do not widen accepted URLs, titles, or descriptions.

- **Change only the generic proposal handoff.** Update `plan_tool/create.py:propose_references_from_claude` to return the typed result rather than `Optional[list[Reference]]`. Keep its initial request and cache/checkpoint mechanism intact as the base for step 2's bounded repair; the completed plan permits the step-2 repair only after an unparseable initial result.

- **Preserve progress and checkpoints.** Keep the existing progress completion for parseable populated and empty replies, and preserve the failed progress result and checkpoint ineligibility for a terminal unparseable reply. Preserve `plan_tool/create.py:checkpoint_path`, `load_if_valid`, and `save_checkpoint` behavior: accepted parseable raw responses remain eligible for the existing checkpoint, while rejected unparseable replies remain ineligible.

- **Adapt callers without changing policy.** Update `plan_tool/create.py:_prepare_create_plan` and `plan_tool/create.py:_converge_create_plan` to inspect the typed outcome before passing its reference payload into existing plan code. Do not use truthiness of the result object as a substitute for checking its outcome. This step keeps the existing initial TODO rendering and iteration no-clobber behavior; steps 3 and 4 own failure handling at those boundaries.

- **Leave rendering and patching alone.** Keep `plan_tool/create.py:PreparedCreatePlan.references`, `write_new_plan`, `_render_plan_body`, `_render_references_body`, and `_patch_plan_body_section` on their existing `list[Reference]` inputs. A typed result must not become a second plan-body or replacement contract.

- **Keep roadmap research separate.** Do not alter `plan_tool/create.py:_ROADMAP_REFERENCE_RESPONSE_CONTRACT`, `_parse_roadmap_references_json`, or `propose_roadmap_references_from_claude`; that path already has its own validated result contract.

- **Update test doubles as contract users.** Make monkeypatched `propose_references_from_claude` results in `tests/test_create.py` return the typed result so tests exercise the same boundary as production callers.

## Tests

Update `tests/test_create.py` with focused parser, proposal, checkpoint, and caller-regression coverage.

### Tests for this step

- `TestParseReferencesJson::test_happy_path` — a valid populated array returns the populated outcome and retains the validated `Reference` fields.
- `TestParseReferencesJson::test_empty_array_returns_empty_result` — `[]` returns the valid-empty outcome, not the unparseable outcome.
- `TestParseReferencesJson::test_no_json_returns_unparseable_result` — non-JSON text returns the unparseable outcome with no references.
- `TestParseReferencesJson::test_drops_entries_with_non_http_url` — invalid rows remain filtered while a surviving valid row produces the populated outcome.
- `TestProposeReferencesFromClaude::test_complete_on_success` — a populated typed result preserves the completed progress report.
- `TestProposeReferencesFromClaude::test_unparseable_first_response_retries_once` — the completed research seam uses the typed unparseable result to trigger the single repair that step 2 owns.
- `TestProposeReferencesFromClaude::test_parseable_empty_response_keeps_references_checkpoint` — a valid empty result preserves the parseable-response checkpoint behavior.
- `TestProposeReferencesFromClaude::test_unparseable_response_does_not_save_references_checkpoint` — an unparseable result leaves no successful references checkpoint.
- `TestReferencesRenderedIntoBody::test_no_references_falls_back_to_todo` — a typed valid-empty result retains initial TODO References rendering.
- `TestCreatePlanReferencesIteration::test_iteration_loop_preserves_references_when_refs_empty` — a typed valid-empty iteration result leaves the published References body unchanged.

Green-before-done gate: `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- Generic reference research returns a typed result with distinct populated, empty, and unparseable outcomes.
- A valid empty JSON array is distinguishable from malformed model output.
- `plan_tool/create.py:Reference` filtering and normalization remain unchanged.
- A parseable first response makes one generic research call and retains the existing checkpoint behavior; step 2 adds one repair call only after an unparseable first response.
- A terminal unparseable reply records failed research progress and does not create a successful references checkpoint.
- Initial valid-empty rendering and iteration valid-empty References preservation remain unchanged.
- `plan_tool/create.py:_render_references_body` and `plan_tool/create.py:_patch_plan_body_section` retain their existing list-based replacement contract.
- `uv run pytest tests/ -q -n auto` passes.

## References

- [json — JSON encoder and decoderhttps: — Use for the JSON parsing and `JSONDecodeError` boundary behind the unparseable outcome.
- [dataclasses — Data Classeshttps: — Use for the frozen result record beside `Reference`.
- [typing — Support for type hintshttps: — Use for the closed outcome vocabulary and typed payload.
- [pytest API Referencehttps: — Use for hermetic assertions around checkpoints and proposal outcomes.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Formathttps: — Use for JSON-array semantics at the response boundary.

## Applicable guardrails

- **The plan’s “## Plan intent”, trustworthy resumable create** — Make malformed output explicit at the generic research boundary without changing the durable checkpoint or publication contracts.
- **The plan’s “## Step intent”, deliberate emptiness** — Preserve valid empty research as its own successful outcome and keep it separate from unparseable output.
- **The plan’s “## Out of scope”, exclusions** — Leave the named adjacent research, rendering, recovery, and command surfaces unchanged; this step owns only the generic result contract.

## Deferred

- Malformed-response repair and attempt recording — Step 2 owns the bounded recovery behavior after this result contract lands.
- Initial create failure before publication — Step 3 owns the initial caller-boundary policy.
- Iteration failure staging and reporting — Step 4 owns the iteration caller-boundary policy.
- Roadmap-specific research — `plan_tool/create.py:_parse_roadmap_references_json` remains on its separate contract.
