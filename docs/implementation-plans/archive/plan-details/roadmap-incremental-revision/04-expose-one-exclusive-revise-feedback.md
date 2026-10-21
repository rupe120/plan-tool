> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Expose one exclusive `--revise-feedback` command with one physical backend request and machine-checkable event evidence

## Summary

Add `plan_tool/roadmap_revision_run.py` as the local-revision orchestrator and `plan_tool/prompts/roadmap-feedback-revision.md` as its bounded backend prompt. Extend `plan_tool/cli/roadmap_cmd.py` with the exclusive `--revise-feedback` surface, and extend `plan_tool/run_log.py` plus `DATA_CONTRACT.md` with two safe, typed local-revision events. The key decision is that one accepted preflight permits exactly one physical backend request with all transport recovery disabled; every later failure is terminal. Green means a valid command updates only the candidate selected by steps 1–3, while logs prove the preflight and final attempt outcome without storing reviewer or model text.

## Table of Contents

- [Summary](#summary) — The command, runner, prompt, and evidence this step adds.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current broad roadmap path cannot express a bounded local revision.
- [Input](#input) — The contracts from steps 1–3 and existing backend logging this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New runner assets and command, event, and documentation edits.
- [Implementation](#implementation) — Exclusive dispatch, one-request execution, prompt boundaries, and terminal evidence.
- [Tests](#tests) — Focused command, runner, prompt, and run-log coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable local-mode and event-contract results.
- [References](#references) — Command-mode and publication API references.
- [Applicable guardrails](#applicable-guardrails) — The plan boundaries that keep this a local revision mode.
- [Deferred](#deferred) — Workflow documentation and broader recovery work left to later scope.

## Why

`plan_tool/roadmap.py:run_roadmap` is a staged authoring loop with content retries and transport recovery through `plan_tool/roadmap.py:shell_roadmap_invoker`, while `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` dispatches only broad stages, seed work, and views. That path cannot prove that one selected feedback request produced only one backend call or one bounded candidate. This step gives the local contracts from steps 1–3 an operator entry point that makes its cost, scope, and outcome queryable.

## Input

- **Step 1 selection and response contract:** Consume the typed preflight and bounded prompt context from `plan_tool/roadmap_revision.py`. Do not repeat selector parsing, retained-feedback checks, the text-field table, or JSON operation parsing in this runner.

- **Step 2 candidate merger:** Consume the typed candidate result from `plan_tool/roadmap_revision_patch.py`. The runner supplies the response text and handles its terminal outcome; it does not reconstruct artifact rows or interpret raw operations itself.

- **Step 3 writer boundary:** Use `plan_tool/roadmap_revision_publish.py` for the writer guard, pre-backend seed-state invalidation, candidate validation, and one-artifact publication. Acquire its guard before local preflight and keep its token through publication; invalidation completes before backend context exists, and publication occurs only after the candidate passes its normal local envelope.

- **Roadmap stage identity:** Read the selected stage from `plan_tool/roadmap.py:STAGES` and `RoadmapStage`. Reuse its artifact path, parser, renderer, and gates rather than creating a local stage or artifact mapping.

- **Backend and run-log seams:** `plan_tool/shell.py:claude_invoke` supports rate-limit and transient-retry controls, while `plan_tool/run_log.py:RunLogWriter`, `bind_shell_sink`, and `run_end` provide the existing lifecycle pattern. The local runner must remain testable with an injected invoker and run logger.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_revision_run.py` — Local preflight-to-publication orchestrator, one-call production invoker, typed result surface, and terminal run-log ordering.
  - `plan_tool/prompts/roadmap-feedback-revision.md` — Bounded prompt that requests only the closed JSON operations response.
  - `tests/test_roadmap_revision_run.py` — Unit and composed tests for local execution, prompt scope, terminal outcomes, and runner-owned logs.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Add `--revise-feedback`, reject every incompatible local-mode input, dispatch the local runner, print the accepted selection before invocation, and map its result to the existing command exit-code style.
  - `plan_tool/run_log.py` — Add the two local-revision event dataclasses, include them in `Event`, and add closed public emit helpers with no text-bearing parameter or open `**extra` channel.
  - `plan_tool/data_contract.py` — Required addition to this step’s `files` metadata: register both new persisted event contracts so the `DATA_CONTRACT.md` drift guard recognizes their sections.
  - `tests/cli/test_roadmap_cmd.py` — Cover parser and dispatch ownership without re-testing the runner’s merge or publication behavior.
  - `tests/test_run_log.py` — Cover event discriminators, serialized fields, closed values, nullability, and structural redaction.
  - `DATA_CONTRACT.md` — Document each new event’s fields, fixed vocabularies, phase-unreached values, and intentional absence of reviewer or backend text.
  - `TESTING.md` — Add the injected-invoker recipe for `plan_tool/roadmap_revision_run.py`, including the production-wrapper test that proves transport recovery is disabled.

## Implementation

- **Foundational logic:** Run one local-revision sequence: shared-guard acquisition, preflight, pre-backend seed invalidation, bounded prompt construction, one backend request, operation parse, typed merge, local validation, and publication. Any failure after preflight ends that sequence; never retry content or transport work.

- **Keep `--revise-feedback` semantically exclusive.** Add `--revise-feedback ARTIFACT:FEEDBACK_ID` in `plan_tool/cli/roadmap_cmd.py:register` and route it before the existing broad, seed, and view dispatch in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Reject every local-mode combination instead of ignoring values, including brief, view refinements, seed flags, confirmation flags, and an explicitly supplied `--from-stage`, even when its value equals the ordinary default.

- **Preserve evidence for parseable conflicting local commands.** Keep the local selector independent enough that `cmd_roadmap` can send a parseable conflicting local invocation through local preflight rejection rather than silently dropping it. Record whether `--from-stage` was explicitly supplied so its default does not hide an incompatible argument. Existing non-local mode conflicts can retain their current `argparse` behavior.

- **Keep the CLI thin.** Let `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` resolve the repository and plans directory, call the new runner, print the accepted feedback ID, target row ID, artifact token, path, and allowed fields before the backend call, and render a concise terminal summary. Do not make the CLI rebuild preflight data, prompt context, operations, or candidates.

- **Own the local run lifecycle in `plan_tool/roadmap_revision_run.py`.** Start a `RunLogWriter` when the caller supplies none, use one `finally` path for `run_end`, and expose seams for tests and non-CLI callers. Use a result value for terminal local outcomes so the command can distinguish usage-style preflight rejection, ordinary failure, and interruption without guessing from text.

- **Acquire the shared writer guard before preflight.** After a parseable local-mode conflict has been rejected, acquire the step-3 per-roadmap guard before loading the selected artifact or seed-state sidecar. Hold its token through preflight, invalidation, prompt construction, the one backend request, merge, validation, and publication; pass it to the publisher rather than reacquiring. This prevents a broad or seed owner from replacing the selected artifact between preflight and local publication.

- **Make the production request physically single-shot.** Do not call `plan_tool/roadmap.py:shell_roadmap_invoker`, because that path intentionally allows recovery. Instead, have the new module’s production invoker call `plan_tool/shell.py:claude_invoke` with rate-limit recovery disabled and a transient attempt limit of one. Bind the existing shell sink around that call so ordinary call timing remains visible, and ensure no wrapper, retry loop, or fallback backend can invoke the transport a second time.

- **Build no context before invalidation.** After accepted preflight, invoke the step-3 invalidation operation before rendering the prompt. If it fails, do not create context or call the backend; emit the one attempt event with a `null` context digest and terminal `seed-invalidation-failed` outcome.

- **Keep prompt data bounded.** Render `plan_tool/prompts/roadmap-feedback-revision.md` through `plan_tool/renderer.py:prompts_dir()` and the project’s `string.Template` rendering convention. Supply only the step-1 prompt context: selected feedback identity, request, and state; selected artifact identity and path; target row identity and type; allowed field names and current values; and the immutable relation summary.

- **Make the prompt self-contained.** State the closed JSON response shape and the optional-replacement-then-response ordering directly in `plan_tool/prompts/roadmap-feedback-revision.md`. Do not point the backend at repository documentation, ask it to inspect files, or ask it to write a file. Require an unfenced JSON object and no surrounding text.

- **Treat every post-preflight failure as terminal.** An invocation failure, empty reply, operation rejection, merge rejection, candidate parse failure, gate rejection, or publication failure must leave canonical artifacts unchanged unless publication itself reports failure or interruption. Preserve step 3’s already-written invalidation whenever it completed; do not refresh, promote, materialize, or overwrite seed prose.

- **Add two closed event contracts.** Add one preflight event and one attempt event in `plan_tool/run_log.py`, both with fixed event discriminators and emit helpers that accept only their documented fields. Register both in `plan_tool/data_contract.py` and document them in `DATA_CONTRACT.md`; this prevents a new event section from becoming an unregistered data contract.

- **Define the exact event matrix.** `roadmap_local_revision_preflight` always contains `artifact_key`, `feedback_id`, `target_row_id`, `artifact_digest`, `render_canonical`, and `verdict`. The first five fields are nullable and use no empty-string sentinel. For `mode-rejected`, only the parsed selector fields are present; for an early selector rejection every unavailable field is `null`; for retained-feedback rejection the selector, selected target, and loaded-artifact digest are present but `render_canonical` is `null`; for render-canonical rejection those fields are present and `render_canonical` is `false`; and for `accepted` they are present and `render_canonical` is `true`.

- **Make every attempt field closed.** `roadmap_local_revision_attempt` always contains `attempt` (the integer `1`), `context_digest` (string or `null`), `invalidated_seed_count` (nonnegative integer or `null`), `operation_verdict` (`not-reached`, `accepted`, or `rejected`), `merge_verdict` (`not-reached`, `accepted`, or `rejected`), `validation_verdict` (`not-reached`, `candidate-parse-failed`, `gate-rejected`, or `accepted`), `publication_outcome` (`not-reached`, `published`, `failed`, or `unknown-after-interrupt`), and `outcome` (`seed-invalidation-failed`, `invoke-failed`, `empty-reply`, `operation-rejected`, `merge-rejected`, `candidate-parse-failed`, `gate-rejected`, `publication-failed`, `published`, or `interrupted`). No event field or helper accepts an extension bag.

- **Map terminal outcomes by completed phase.** Invalidation failure has `null` context and count with every later phase `not-reached`. Invocation failure and empty reply have a context digest and count with operation and later phases `not-reached`; an operation rejection sets only operation to `rejected`; a merge rejection sets operation `accepted` and merge `rejected`; parse and gate rejection preserve accepted prior phases and set their named validation value; publication failure preserves accepted prior phases and sets publication to `failed`; success sets every phase to its accepted or published value. An interruption preserves only phases completed before the interruption, sets the active and later phases to `not-reached`, and uses `unknown-after-interrupt` only if the single-path replacement may have completed. Persist this exact matrix in `DATA_CONTRACT.md` and test every row.

- **Record preflight once.** Emit `roadmap_local_revision_preflight` exactly once for every invocation that reaches the local runner. Record selector data when available, target-row ID only when resolved, artifact digest only when loaded, and render-canonical status only when reached. Use `null` for an unavailable phase value and one of `accepted`, `mode-rejected`, `selector-rejected`, `retained-feedback-rejected`, or `render-canonical-rejected` for its verdict. A parseable local-mode conflict records `mode-rejected` before artifact preflight, so target, digest, and render-canonical fields are `null` and no invalidation or backend call begins.

- **Record one terminal attempt after accepted preflight.** Emit `roadmap_local_revision_attempt` exactly once with `attempt: 1`. Its context digest is a digest of the bounded rendered context and is `null` when invalidation fails or an interruption happens before context construction. In either case operation, merge, validation, and publication are `not-reached`; an interrupted invalidation also has a `null` invalidated-seed count and terminal `interrupted` outcome. Use the plan’s closed operation, merge, validation, publication, and terminal-outcome vocabularies; use `not-reached` and `null` only where the phase did not run.

- **Represent interruptions honestly.** Report `unknown-after-interrupt` only when an interruption occurs at the single-path replacement boundary and the runner cannot establish whether replacement completed. An interruption during invalidation has no context and a `not-reached` publication outcome; an interruption after context construction but before publication also has a `not-reached` publication outcome. Do not claim a recovery protocol.

- **Keep text structurally out of events.** Neither new event dataclass nor its writer helper may expose a field or extension bag for the feedback request, proposed response, artifact prose, raw reply, or rendered prompt. Test both field sets and raw JSONL output with distinctive sentinels.

## Tests

### Tests for this step

- `tests/cli/test_roadmap_cmd.py::test_revise_feedback_is_dispatched_to_the_local_runner` — Confirms `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` forwards the selector, resolved paths, and injected invoker without calling `plan_tool/roadmap.py:run_roadmap`.

- `tests/cli/test_roadmap_cmd.py::test_revise_feedback_rejects_each_broad_seed_view_and_brief_input` — Covers every incompatible parseable argument combination, including explicit `--from-stage 1`, with one `mode-rejected` preflight event and no broad, seed, or view handler, invalidation, or backend request reached.

- `tests/cli/test_roadmap_cmd.py::test_revise_feedback_prints_the_accepted_bounded_target_before_invoke` — Confirms the operator receives the selected feedback, target, artifact, path, and allowed-field summary before backend work.

- `tests/test_roadmap_revision_run.py::test_local_runner_preflights_and_invalidates_before_rendering_or_invoking` — Proves rejected selection and failed invalidation stop before prompt construction and backend work.

- `tests/test_roadmap_revision_run.py::test_local_runner_holds_the_guard_across_preflight_and_publication` — Starts a broad or seed writer while the local runner is between preflight and publication and proves it cannot replace the selected artifact until the local runner releases its shared token.

- `tests/test_roadmap_revision_run.py::test_local_runner_makes_exactly_one_physical_request_with_recovery_disabled` — Patches `plan_tool/shell.py:claude_invoke` and proves one call uses disabled rate-limit recovery and a one-attempt transient limit.

- `tests/test_roadmap_revision_run.py::test_local_prompt_contains_only_the_selected_context` — Uses distinctive sibling-row, feedback, prose, and upstream markers to prove they never enter the rendered prompt.

- `tests/test_roadmap_revision_run.py::test_local_prompt_renders_a_closed_json_request_without_unresolved_placeholders` — Confirms every template placeholder has a supplied value and the template requires the step-1 response contract without a repository-doc reference.

- `tests/test_roadmap_revision_run.py::test_valid_local_revision_publishes_only_the_selected_candidate` — Composes steps 1–3 with one other open feedback row and proves only the selected row and feedback response change.

- `tests/test_roadmap_revision_run.py::test_each_terminal_outcome_emits_one_attempt_record` — Parameterizes invalidation, invocation, empty reply, operation, merge, parse, gate, publication, success, and interruption outcomes, including interruption during invalidation before context construction, with the required verdict and unreached values.

- `tests/test_roadmap_revision_run.py::test_preflight_rejection_emits_no_attempt_record` — Confirms an invalid selector, retained-feedback failure, or noncanonical artifact produces only its preflight evidence and performs no invalidation or backend call.

- `tests/test_roadmap_revision_run.py::test_local_run_ends_and_cleans_up_after_failure_or_interrupt` — Confirms the runner-owned `RunLogWriter` emits one `run_end` and does not leave a stale in-flight record.

- `tests/test_run_log.py::test_local_revision_event_discriminators_and_closed_fields` — Confirms both event dataclasses join `Event` and serialize the documented machine-readable fields.

- `tests/test_run_log.py::test_local_revision_events_preserve_nullability_and_closed_verdicts` — Pins every preflight and attempt field, unavailable phase values, every allowed verdict, and every terminal matrix row.

- `tests/test_run_log.py::test_local_revision_events_cannot_store_feedback_or_backend_text` — Inspects dataclass fields and raw JSONL to prove request, response, prose, prompt, and reply sentinels cannot reach either event.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --revise-feedback <artifact>:<feedback-id>` routes to the local runner and cannot combine with any broad, seed, materialization, view, confirmation, or brief input.

- A parseable local-mode rejection produces one `roadmap_local_revision_preflight` event with `mode-rejected` and reaches neither artifact preflight, seed invalidation, nor a backend call.

- Accepted preflight invalidates existing seed-state entries before context construction and before the sole backend request.

- The local runner acquires the shared writer guard before it reads the selected artifact for preflight and retains that token through publication, so no participating broad or seed writer can replace its baseline in between.

- The local production invoker makes exactly one physical backend request with rate-limit recovery disabled and no transient retry.

- The rendered backend context contains only the selected feedback and target-row information from step 1; no sibling artifact, row, feedback, prose, or upstream artifact enters it.

- Every post-preflight exit emits exactly one attempt-one event using the exact closed field and terminal matrix; an interruption during invalidation has no context digest or invalidated-seed count and `not-reached` later phases.

- Successful execution invokes the step-2 merger and step-3 publisher, changing at most the selected canonical artifact. Failed execution does not publish a new artifact and leaves completed invalidation conservative.

- `roadmap_local_revision_preflight` and `roadmap_local_revision_attempt` contain no reviewer request, proposed response, artifact prose, prompt, or backend reply text.

- `tests/cli/test_roadmap_cmd.py`, `tests/test_roadmap_revision_run.py`, and `tests/test_run_log.py` pass, along with the existing `DATA_CONTRACT.md` drift checks.

## References

- [Python argparse documentation](https://docs.python.org/3.13/library/argparse.html) — Use its parser and action behavior to preserve explicit local-mode exclusivity.
- [Python `os.replace` documentation](https://docs.python.org/3.13/library/os.html#os.replace) — Read the single-path replacement semantics that the step-3 publisher uses for the final local artifact write.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded feedback revision:** Use the contracts from steps 1–3 without adding another selection, patch, or publication shape.

- **The plan’s “## Step intent”, one physical backend request:** Keep all failure handling terminal inside one invocation. Do not add a retry, fallback, interactive recovery, or hidden multi-request path.

- **The plan’s “## Out of scope”, structural and cross-artifact work:** Keep the command on one selected artifact and route requests outside the closed operation contract to the existing broad workflow.

- **The plan’s “## Out of scope”, prose and seed work:** Do not add prose editing or derived-seed generation, promotion, refresh, or overwrite behavior to this runner.

- **The plan’s “## Out of scope”, recovery and reader guarantees:** Do not add a Git checkpoint, persistent revision record, multi-file recovery, or reader-snapshot behavior while recording terminal evidence.

## Deferred

- `README.md`, `docs/cli/roadmap.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md`, and `CAPABILITIES.md` — Step 5 owns the broader operator workflow and capability documentation.

- Changes to `plan_tool/roadmap.py:run_roadmap` retry, overwrite, and recovery behavior — The local runner must remain separate from broad `--from-stage` execution.

- A shared abstraction for one-shot backend transport policy — `plan_tool/shell.py:claude_invoke` already exposes the controls this runner needs; extracting a new shared layer would be a separate refactor.
