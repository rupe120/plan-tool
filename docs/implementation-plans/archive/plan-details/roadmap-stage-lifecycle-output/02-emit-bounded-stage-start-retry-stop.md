> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Emit bounded stage start, retry or stop, write, and re-gate facts from the roadmap runner

## Summary

This step adds an optional, fail-open status callback to `plan_tool/roadmap.py` and emits bounded facts at confirmed stage transitions. It updates `tests/test_roadmap.py` with deterministic collector-based coverage for fresh, revision, retry, stop, write, and feedback-free re-gate routes. The runner remains silent without the callback, leaving the CLI connection to stderr for step 3. On green, a caller can observe safe stage facts without changing retries, artifacts, results, run logs, or backend behavior.

## Table of Contents

- [Summary](#summary) — The completed runner-level status capability.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current silent transition gap.
- [Input](#input) — Existing stage, outcome, and retry contracts the callback reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — The callback seam, safe labels, and lifecycle placement.
- [Tests](#tests) — Deterministic coverage for status order and failure boundaries.
- [Acceptance criteria](#acceptance-criteria) — Observable runner-level outcomes.
- [References](#references) — The roadmap sources that define this work.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this step must preserve.
- [Deferred](#deferred) — Related work owned by later steps or separate decisions.

## Why

`plan_tool/roadmap.py:_run_roadmap` can spend multiple backend attempts and publish several artifacts before `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` presents its final result. The runner already knows when a selected stage starts, retries, stops, writes, or safely re-gates, but it has no narrow way to expose those facts to its caller. A local callback makes those transitions available without making a quiet backend call look healthy or adding shared progress machinery.

## Input

- **Stage identity:** `plan_tool/roadmap.py:RoadmapStage` supplies the configured `number` and `name` that identify a selected stage. Treat both as terminal-untrusted labels even though the shipped `STAGES` names are simple: the shared roadmap status formatter escapes and caps every dynamic field and its callback body. Step 3 reserves six printable characters for `style.note`’s `note: ` prefix, so this step caps that body at 250 characters rather than treating 256 as its own budget.

- **Existing result vocabulary:** `plan_tool/roadmap.py:RoadmapResult`, `OUTCOMES`, and the `FAILURE_*` constants define the existing outcomes and retry failure kinds. Status may name those existing structural values but must not add or reinterpret them.

- **Existing route split:** `plan_tool/roadmap.py:_run_stage` and `_run_bounded_stage_feedback` own backend attempts, while `_run_feedback_free_stage` re-gates an admitted predecessor without an invoker call or publication.

- **Existing preflight boundary:** `plan_tool/roadmap.py:_load_and_regate_below` and `_load_predecessors` run before the selected-stage loop. A failure there has no selected stage to describe in this step.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Add the optional runner status callback, private safe-label and delivery helpers, and calls at the confirmed stage transitions.
  - `tests/test_roadmap.py` — Add collector-based tests beside the existing stage-loop, re-entry, retry, halting, and run-log coverage.

## Implementation

- **Foundational logic:** emit a fail-open, bounded status callback only after a roadmap runner transition is confirmed.

- **Keep the seam local and optional.** Add a keyword-only callback to `plan_tool/roadmap.py:run_roadmap` and carry it through `_run_roadmap` and the three stage routes. Its default must preserve today’s silent direct-caller behavior. `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` is the sole production caller at HEAD, but step 3 owns supplying the stderr sink; do not edit that command in this step.

- **Centralize safe delivery.** Use one private helper in `plan_tool/roadmap.py` to build and invoke status messages. Catch callback `Exception` and drop that one message without fallback output, retries, or result changes. Do not catch `BaseException`, so `KeyboardInterrupt` and other control-flow exceptions retain their current behavior.

- **Make dynamic labels safe before callback delivery.** Use a private formatter for the roadmap slug and `RoadmapStage.name` that emits escaped ASCII, stays on one line, and caps the rendered label at 80 characters. Cap the complete callback body at 250 printable characters, preserving a short stable digest when either a field or body is clipped. Step 3’s `style.note` presentation adds its fixed `note: ` prefix and verifies the final textual stderr line is at most 256 characters. Do not pass exception text, prompt text, reply text, gate messages, or transport text through this formatter or any status message.

- **Emit `started` before route selection.** In `plan_tool/roadmap.py:_run_roadmap`, emit one stage-start fact immediately before choosing the fresh-authoring, active-feedback, or feedback-free route. This lets a selected feedback-free stage appear as work that was checked without claiming that it invoked a backend or wrote an artifact.

- **Emit retry facts only when another attempt will start.** In both `plan_tool/roadmap.py:_run_stage` and `_run_bounded_stage_feedback`, retain the existing source/admission recheck before a later attempt. After that check succeeds and immediately before the next invoker call, emit a retry fact naming the existing failure kind. A final failed attempt, or a failed recheck before the next call, must not emit a retry fact.

- **Emit re-gate and write facts after their proof points.** Emit `re-gated without write` only after `plan_tool/roadmap.py:_run_feedback_free_stage` returns a passing reused predecessor. Emit `wrote` only after `publish_stage_artifact` succeeds and the subsequent `admit_stage_artifact` read-back succeeds. Do not report a write for failed publication or failed read-back.

- **Emit one stopped fact for each post-start non-success result.** In `plan_tool/roadmap.py:_run_roadmap`, cover invalid and exhausted outcomes after a `started` fact, including retry-budget exhaustion, source admission, feedback-free re-gate, publication, and post-write read-back failures. An exhausted retry may name its existing failure kind; failures without one must stay a fixed bounded stopped message. Prevent duplicate stopped facts when a route has several internal checks.

- **Preserve escaping errors.** If `RoadmapError` or `RoadmapArtifactError` escapes after `started`, emit one bounded stopped fact and re-raise the same exception. Do not turn it into a `RoadmapResult`, change the CLI’s existing error mapping, or emit a terminal result here.

- **Leave shared and durable surfaces alone.** Keep `MAX_STAGE_ATTEMPTS`, correction prompts, stage gates, source admission, artifact publication, `RoadmapResult`, `OUTCOMES`, `FAILURE_*`, and run-log calls such as `phase_start`, `attempt_failed`, `roadmap_stage_written`, and `run_end` unchanged. `plan_tool/progress.py` already owns heartbeat behavior for other commands and is not a dependency of this local callback.

## Tests

### Tests for this step

- `test_run_roadmap_is_silent_without_a_status_callback` — Calls `plan_tool/roadmap.py:run_roadmap` without the new callback and proves it adds no direct output while preserving the result and artifact set.

- `test_status_callback_reports_started_retry_and_written_in_transition_order` — Uses a fresh stage that fails gates once, then passes, and asserts the collected started, retry, and write facts bracket the corresponding invocations and publication.

- `test_fresh_stage_retry_uses_the_existing_failure_kind` — Exercises `plan_tool/roadmap.py:_run_stage` and proves the retry fact names an existing failure kind rather than a reply-derived diagnostic.

- `test_feedback_revision_retry_uses_the_existing_failure_kind` — Exercises `plan_tool/roadmap.py:_run_bounded_stage_feedback` with active feedback and proves its retry follows the same rule as fresh authoring.

- `test_source_failure_before_a_next_attempt_emits_stopped_without_retry_or_call` — Forces the between-attempt source check to fail for each backend route and asserts one stopped fact, no retry fact, and no extra invoker call.

- `test_exhausted_retry_budget_emits_stopped_not_retry` — Covers both backend retry routes and proves their final failed attempt produces one stopped fact without falsely promising another attempt.

- `test_feedback_free_reentry_reports_regated_without_invocation_or_write` — Reuses the existing feedback-free re-entry setup and proves a passing re-gate emits its distinct fact while the invoker and artifact bytes remain unchanged.

- `test_post_start_invalid_paths_emit_one_stopped_fact` — Covers source admission, feedback-free re-gate, publication, and post-write re-admission failures after a selected stage starts; each route emits one stopped fact and no write fact.

- `test_escaping_roadmap_error_after_stage_start_emits_stopped_and_reraises` — Forces prompt or route construction to raise after start, preserves the raised error, and proves no result-shaped status is fabricated.

- `test_status_lines_are_single_line_ascii_capped_and_distinguishable` — Uses control characters and overlong slugs, names, and injected stage numbers, then asserts every collected callback body is a safe single ASCII line of at most 250 printable characters, every dynamic field is bounded, and equal visible prefixes retain distinct stable suffixes. Step 3 covers the additional `note: ` presentation prefix at the stderr boundary.

- `test_status_callback_exception_is_fail_open` — Raises `Exception` from the collector and proves invocations, retries, artifact publication, and `RoadmapResult` remain the same.

- `test_status_callback_keyboard_interrupt_propagates` — Raises `KeyboardInterrupt` from the collector and proves the runner does not swallow it.

- `test_status_facts_omit_prompt_reply_exception_and_transport_content` — Injects distinctive unsafe strings into retry and failure paths and proves none appears in a status fact.

- `test_status_callback_preserves_existing_run_log_events` — Replays the existing run-log assertions with a collector and proves event order and payloads remain unchanged.

Every test above must be green, along with `uv run pytest tests/test_roadmap.py -q`, before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap.py:run_roadmap` accepts an optional status callback and stays silent when callers omit it.

- A selected fresh or revision stage emits `started`, emits a retry only before a real next attempt, emits `wrote` only after publication and read-back, and emits one stopped fact when it ends unsuccessfully.

- A selected feedback-free stage emits `started` followed by `re-gated without write` only after its gates pass, without calling the invoker or changing artifact bytes.

- Dynamic slugs and configured stage names reach the callback as single-line ASCII labels of at most 80 rendered characters, with a stable distinguishing suffix when clipped.

- Every callback body is a single printable ASCII line of at most 250 characters, retaining a stable distinguishing suffix when the full body is clipped; step 3 owns the final 256-character stderr presentation boundary.

- Status facts contain only fixed lifecycle text, safe slug and stage labels, existing failure kinds, and existing structural values; they contain no model, exception, prompt, reply, or transport content.

- A callback `Exception` cannot change attempts, artifacts, outcomes, exceptions, exit handling, or run-log records; a callback `KeyboardInterrupt` still propagates.

- `plan_tool/roadmap.py:MAX_STAGE_ATTEMPTS`, correction prompts, gates, publication, source admission, `RoadmapResult`, `OUTCOMES`, `FAILURE_*`, and run-log JSONL remain unchanged.

## References

- [Roadmap lifecycle plan — Read the stage-transition contract and the split between this runner step and step 3’s CLI work.

- [Roadmap runner — Read `run_roadmap`, `_run_roadmap`, the retry loops, and the feedback-free route.

- [Roadmap demo orchestration](../../../how-to/roadmap-demo.md) — Read the motivating long-running roadmap run and the retained JSONL diagnostic role.

## Applicable guardrails

- **The plan’s `## Scope guardrails`, normal stage-run boundary:** Limit the callback to the standard roadmap stage loop. Do not add it to apply, seed, view, structural, or other roadmap routes.

- **The plan’s `## Scope guardrails`, output boundary:** This step supplies facts to an injected callback only. It must not write stdout or stderr directly; step 3 owns the command-side stderr connection.

- **The plan’s `## Scope guardrails`, transition-only boundary:** Do not add heartbeat, timing, background, cancellation, streaming, configuration, or durable-status behavior.

- **The plan’s `## Scope guardrails`, preserved runner contract:** Keep retry decisions, gates, publication, result vocabularies, exit behavior, and run-log records unchanged.

- **The plan’s `## Scope guardrails`, safe-content boundary:** Sanitize dynamic labels before delivery and keep model-derived or exception-derived text out of every status fact.

- **The plan’s `## Scope guardrails`, fail-open boundary:** A delivery failure must drop only the affected fact, while control-flow exceptions keep their existing path.

## Deferred

- **Accepted-range and terminal-result facts** — Step 3 owns the CLI connection and brackets these runner-level facts with command-level status.

- **Heartbeat or liveness reporting** — The plan’s `## Out of scope` keeps a quiet backend call distinct from a confirmed transition.

- **Status for non-stage roadmap routes or other commands** — The plan’s scope fence requires separate evidence and a separate backlog decision.
