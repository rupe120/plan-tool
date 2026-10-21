> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Retry malformed reference research once with attempt provenance

## Summary

Update `plan_tool/create.py:propose_references_from_claude` to repair one unparseable generic reference-research reply. The change stays in `plan_tool/create.py`, with focused behavior and run-log coverage in `tests/test_create.py`. The key decision is a single local retry that carries the rejected reply and JSON-array contract, rather than a reusable retry framework. Every malformed reply emits the existing `attempt_failed(parse)` event with its attempt number, including attempt 1 when the repair succeeds. On green, a parseable repair returns the step-1 typed result and checkpoints only its accepted raw response; a second malformed reply remains visible and uncheckpointed.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the bounded repair.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why one repair belongs at the research boundary.
- [Input](#input) — Contracts from step 1 and existing observability seams.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Required retry, provenance, and checkpoint behavior.
- [Tests](#tests) — Focused repair-path coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the response contract and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries for this change.
- [Deferred](#deferred) — Adjacent work owned by later steps.

## Why

After step 1, generic research can identify an unparseable reply, but it has no chance to recover from a transient formatting mistake. A single corrective request can recover useful research while keeping repeated malformed output explicit, bounded, and safe to resume.

## Input

- **Step 1 typed result:** Step 1 supplies the generic research outcome that distinguishes populated, valid-empty, and unparseable replies; this step keeps that result contract and changes only the unparseable live-response path.
- **Response contract:** `plan_tool/create.py:_REFERENCE_RESPONSE_CONTRACT` and `plan_tool/create.py:_parse_references_json` remain the source of truth for tolerated JSON arrays and `Reference` filtering.
- **Checkpoint contract:** `plan_tool/create.py:_REFERENCES_CHECKPOINT_NAME`, `plan_tool/create.py:_references_input_hash`, `plan_tool/checkpoint.py:load_if_valid`, and `plan_tool/checkpoint.py:save_checkpoint` retain their existing resume and payload format.
- **Attempt seams:** `plan_tool/progress.py:ProgressReporter`, `plan_tool/progress.py:StderrReporter`, and `plan_tool/run_log.py:RunLogWriter` carry phase, rejected-attempt, and request provenance without a new logging surface. Use the existing run logger’s `attempt_failed` method with local failure kind `parse` rather than importing a retry abstraction.
- **Test limit:** Canned responses in `tests/test_create.py` prove control flow, prompts, diagnostics, and persistence; they do not measure real-model formatting quality.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — add one local malformed-response repair path to `propose_references_from_claude`, preserving typed outcomes, progress, rejected-attempt and request provenance, and checkpoint eligibility.
  - `tests/test_create.py` — add and update focused generic-research tests for repair prompts, rejected-attempt and two-call provenance, accepted checkpoint replacement, and terminal malformed diagnostics.

## Implementation

- **Foundational logic: one bounded repair for an unparseable generic-reference reply.** In `plan_tool/create.py:propose_references_from_claude`, inspect the typed result from step 1 after the first live response. A populated or valid-empty result must complete normally without another call. An unparseable result must make exactly one corrective request.

- **Keep the repair local and specific.** Build the corrective request from `plan_tool/create.py:_render_references_prompt`’s existing request plus the rejected raw reply and a clear restatement of the JSON-array contract from `plan_tool/create.py:_REFERENCE_RESPONSE_CONTRACT`. The repair must ask for a replacement response, not merge or reuse entries from malformed text.

- **Preserve `Reference` parsing rules.** Route the repair response through `plan_tool/create.py:_parse_references_json` and the step-1 result contract. Do not widen URL, title, description, chatter-tolerance, or invalid-row filtering rules to avoid a retry.

- **Record every rejected attempt as well as both sent attempts.** Label the original request as attempt 1 and the repair request as attempt 2 under the existing `propose_references` phase. Immediately after each malformed parse, call the existing run logger’s `attempt_failed` method with `phase="propose_references"`, that attempt number, and local failure kind `parse`, before either issuing the repair or returning the terminal typed outcome. This event remains in `runs show` when attempt 2 recovers, so successful repair has a durable reason for its retry. Surface the first rejection as retry progress, but reserve the raw-response terminal diagnostic for the second malformed response.

- **Keep checkpoint replacement parseable-only.** A parseable repair, including a valid empty array, must save its accepted raw response through the existing references checkpoint path when this call is eligible to save. The first malformed response and a terminal second malformed response must not write or replace a successful references checkpoint.

- **Keep existing checkpoint handling unchanged.** Preserve cache-hit behavior, the TTY resume-decline path through `plan_tool/checkpoint.py:discard_checkpoint`, and the successful-create cleanup that discards references checkpoint shards. Do not add a checkpoint kind, alter `_references_input_hash`, or make malformed output resumable.

- **Use the existing terminal diagnostic convention.** When attempt 2 remains unparseable, preserve the typed terminal outcome and emit a bounded diagnostic through `plan_tool/create.py:_dump_failed_response` and the existing parse-failure run-log path when repository context is available. The diagnostic must point to the second rejected response and carry attempt 2 provenance.

- **Leave caller policy to later steps.** Do not change `plan_tool/create.py:_prepare_create_plan`, `plan_tool/create.py:_converge_create_plan`, `_render_plan_body`, `_render_references_body`, or `_patch_plan_body_section` in this step. Steps 3 and 4 own the initial and iteration failure boundaries.

- **Keep roadmap research separate.** Do not alter `plan_tool/create.py:propose_roadmap_references_from_claude` or `plan_tool/create.py:_parse_roadmap_references_json`; their strict product-research contract remains independent.

## Tests

### Tests for this step

- `TestProposeReferencesFromClaude::test_unparseable_first_response_retries_once` — an unparseable first reply followed by valid references makes exactly two invoker calls, returns the populated typed result, and retains one `attempt_failed(parse)` event for attempt 1.
- `TestProposeReferencesFromClaude::test_repair_prompt_includes_rejected_reply_and_json_array_contract` — the second prompt contains the first raw reply and directs the model back to the generic JSON-array response contract.
- `TestProposeReferencesFromClaude::test_parseable_empty_response_does_not_retry` — `[]` remains a successful valid-empty result with one invoker call.
- `TestProposeReferencesFromClaude::test_repair_records_propose_references_attempts_one_and_two` — the repair path records both generic-research calls with attempts 1 and 2.
- `TestProposeReferencesFromClaude::test_parseable_repair_replaces_references_checkpoint_payload` — a valid repair saves the repair response as the normal references checkpoint payload.
- `TestProposeReferencesFromClaude::test_twice_unparseable_dumps_attempt_two_and_skips_references_checkpoint` — two malformed replies return the terminal unparseable result, emit `attempt_failed(parse)` for attempts 1 and 2, preserve a bounded second-response diagnostic, and leave no successful checkpoint.
- `TestProposeReferencesFromClaude::test_propose_references_writes_and_loads_checkpoint` — an existing parseable checkpoint still resumes without an invoker call or repair.

Green-before-done gate: `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- A first malformed generic reference-research reply causes exactly one repair request.
- The repair request includes the rejected reply and restates the JSON-array response contract.
- Valid populated and valid-empty first replies make one request only.
- Every malformed generic-research reply emits `attempt_failed(parse)` under `propose_references` with its own attempt number, including attempt 1 when the repair succeeds; repair calls remain recorded as attempts 1 and 2.
- A parseable repair returns the step-1 typed populated or valid-empty outcome and can save the repair raw response in the existing references checkpoint.
- A second malformed reply returns the terminal unparseable outcome, records a bounded diagnostic for attempt 2, and creates no successful references checkpoint.
- Existing parseable checkpoint resume, forced discard, and successful-create checkpoint cleanup behavior remain unchanged.
- `uv run pytest tests/ -q -n auto` passes.

## References

- [json — JSON encoder and decoderhttps: — Use for the parse boundary between a valid empty array and malformed text.
- [Increase output consistencyhttps: — Use for the corrective prompt’s explicit output-format reminder.
- [pytest API Referencehttps: — Use for hermetic response sequences, temporary checkpoints, and run-log assertions.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Formathttps: — Use for the JSON-array response requirement.

## Applicable guardrails

- **The plan’s “## Plan intent”, trustworthy resumable create** — Keep malformed output visible while retaining the existing checkpoint recovery behavior for accepted responses.
- **The plan’s “## Step intent”, bounded recovery** — Limit this change to one repair request with explicit attempt provenance.
- **The plan’s “## Out of scope”, adjacent surfaces** — Do not extend roadmap research, retrieval, rendering, CLI flags, or shared retry machinery.

## Deferred

- Initial create failure and publication prevention — Step 3 owns the caller boundary after this step returns a terminal unparseable result.
- Iteration-stage failure, plan preservation, and iteration run-log outcome — Step 4 owns the post-publication caller boundary.
- Shared retry abstraction across `plan_tool/create.py:propose_steps_from_claude`, body synthesis, and reference research — a broader consolidation exceeds this local feature step.
