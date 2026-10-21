> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Log source-ordered, plan-attributed materialization attempts through a redacting observer

## Summary

Add a roadmap-local observer that records materializer attempts through the existing run-log writer without storing generated content. Update `plan_tool/roadmap.py:materialize_plan_seed()` and `materialize_and_diff_one_plan()` so later command lifecycles can supply the observer for each selected `PlanRow`. Keep nested backend retries distinct from candidate-seed corrections, and forward only safe lifecycle fields to the writer. On green, a logged materialization identifies its plan and attempt counters while prompts, replies, validation prose, and tool-input summaries stay out of JSONL and `in-flight.json`.

## Table of Contents

- [Summary](#summary) — The change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why materializer calls need a safe logging boundary.
- [Input](#input) — Upstream lifecycle, context, and materializer contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Observer behavior, counters, redaction, and compatibility.
- [Tests](#tests) — Deterministic coverage for logged materialization attempts.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary lifecycle and structured-logging references.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this work.
- [Deferred](#deferred) — Command lifecycle and documentation work owned by later steps.

## Why

`plan_tool/roadmap.py:materialize_plan_seed()` currently calls its `StageInvoker` and retains reply-derived diagnostics for the human-facing result, but it has no safe path for recording candidate attempts or the shared runner’s inner activity. Reusing the stage logger directly would copy prompts, reply heads, validation messages, and tool summaries into durable records. This step adds one redacting boundary so later materialize and refresh commands can expose useful liveness without turning the run log into a copy of seed content.

## Input

- **Step 1 lifecycle ownership:** Step 1 supplies the private roadmap-command lifecycle owner that later command paths use to create and finish an owned writer. This step only supplies per-candidate observability.
- **Step 2 writer context:** Step 2 makes `plan_tool/run_log.py:RunLogWriter` carry the active roadmap context through normal events, shell call-end events, and snapshot refreshes. This observer adds attempt facts without replacing that plan attribution.
- **Materializer seam:** `plan_tool/roadmap.py:materialize_plan_seed()` owns the candidate-seed retry loop, while `materialize_and_diff_one_plan()` owns its baseline reads and forwards to the materializer.
- **Shared backend seam:** `plan_tool/roadmap.py:shell_roadmap_invoker()` delegates to `plan_tool/shell.py:claude_invoke()`, whose active observer reaches `plan_tool/backend_runner.py:run_streaming_once()` lifecycle signals.
- **Result boundary:** `RoadmapSeedMaterializeResult.failure_detail`, `RoadmapSeedRefreshFailure.failure_detail`, and `_render_seed_refresh_report()` remain human-facing result and report data. They are not run-log fields.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Add the optional materialization-observer seam, safe event forwarding, and nested attempt tracking around `materialize_plan_seed()`.
  - `tests/test_roadmap.py` — Cover safe per-candidate records, nested backend recovery, no-child failures, and unchanged materialization results.

## Implementation

- **Make the foundational logic a redacting materialization observer.** Add a private, roadmap-local observer that translates one candidate seed’s backend activity into calls on the effective `RunLogWriter`. It must receive the row ID and the phase supplied by a later command owner; it must not choose rows, sort them, or inspect `PlansArtifact.ordering`.

- **Keep observability optional and forwardable.** Extend `plan_tool/roadmap.py:materialize_plan_seed()` and `materialize_and_diff_one_plan()` with an optional instrumentation path that a later materialize or refresh lifecycle can supply. Preserve the current `StageInvoker` default, result types, and behavior when no observer is supplied. Keep lightweight injected test loggers working without requiring writer-only context or shell-binding methods.

- **Record candidate attempts separately from backend attempts.** Treat each iteration of `materialize_plan_seed()`’s existing correction loop as one-based `seed_attempt`. Track each child process started by `claude_invoke()` as one-based `backend_attempt` within that seed attempt. A correction retry increments `seed_attempt` and resets the child count; an inner rate-limit, backend-switch, or transient recovery increments only `backend_attempt`.

- **Keep child state accurate at every point.** Before a candidate has started a child, record its `seed_attempt`, literal-null `backend_attempt`, and `backend_child_started: false`. On `backend_spawn`, set `backend_child_started: true` and retain the child ordinal through stream activity, progress, stall, termination, recovery wait, call end, and interruption. A recovery wait stays attached to the child that just failed; the next spawn replaces the ordinal.

- **Use the final observed child for post-call failures.** When `_lift_artifact_text()` cannot produce a seed, `validate_draft_seed_content()` rejects it, or the invoker returns unusable output, emit safe failure facts using the greatest child ordinal observed in that candidate. If `claude_invoke()` returns before spawning a process, retain literal-null `backend_attempt` and `backend_child_started: false`.

- **Reuse the existing shell binding without widening its rollout.** Bind the writer through `plan_tool/run_log.py:RunLogWriter.bind_shell_sink()` so `claude_call_end` continues to use the writer’s step-2 context. Within that scoped call, route backend lifecycle callbacks through the redacting observer and restore the prior shell state on every exit. One workable approach is to replace only the active backend observer for the call scope; do not change `plan_tool/shell.py` or `plan_tool/backend_runner.py` for this roadmap-specific policy.

- **Preserve useful lifecycle facts and drop unsafe values.** Forward the shipped lifecycle and timing events, including `claude_call_start`, `claude_call_end`, `backend_spawn`, `backend_termination`, `claude_call_progress`, `claude_call_stall_suspected`, `backend_recovery_wait`, and `run_interrupted`, with the current counter fields. For stream activity, retain safe kind, tool name, and byte-count data where present, but remove `tool_input_summary`.

- **Use safe post-call failure records.** Record the existing failure kind, numeric return code when available, attempt and violation counts, and boolean presence facts. Do not emit `gate_violations` for materializer validation failures because its message list would persist gate prose. Do not forward `failure_detail`, reply heads, lifted text, prompts, seed bodies, validation messages, stderr, or provider transcripts.

- **Leave materialization behavior unchanged.** Keep `_corrections_block()` input, `MAX_STAGE_ATTEMPTS`, `validate_draft_seed_content()`, draft and promoted writes, sidecar ordering, and `RoadmapSeedMaterializeResult` unchanged. The observer must not alter whether a candidate retries, succeeds, exhausts, or leaves prior files and state untouched.

- **Keep command concerns out of this step.** Steps 4 and 5 own command writer startup, source-order row phases, `active_plan_id` transitions, terminal outcomes, and snapshot cleanup. This step only makes one row’s materializer capable of safely reporting when those owners provide a writer and phase.

- **Map nested legacy ordinals deliberately.** Make `seed_attempt` and `backend_attempt` authoritative. Materializer candidate events retain legacy `attempt = seed_attempt`; child lifecycle events retain legacy `attempt = backend_attempt`; and recovery wait carries the failed child as `attempt` plus its next child as `next_attempt`. The materialization call-end forwarding must preserve the child ordinal instead of accepting the generic bind-time candidate ordinal. Test an outer correction containing an inner recovery across candidate, child, call-end, recovery, and snapshot records.

## Tests

### Tests for this step

- `TestMaterializePlanSeed::test_materialization_observer_records_safe_candidate_attempt_fields` — A logged successful candidate emits its plan attribution, `seed_attempt`, child state, and lifecycle facts without prompt or seed text.
- `TestRealInvoker::test_materialization_observer_distinguishes_candidate_retry_from_backend_recovery` — One corrected candidate attempt containing multiple shared-runner children records the two counter levels correctly on calls, lifecycle events, and snapshots.
- `TestMaterializePlanSeed::test_materialization_failure_uses_the_final_observed_backend_attempt` — An invoke, parse, or validation failure after multiple children reports the last child ordinal and safe counts.
- `TestRealInvoker::test_materialization_no_child_failure_uses_null_backend_attempt` — A missing executable or equivalent no-subprocess return records `backend_child_started: false` and a literal-null backend attempt.
- `TestRealInvoker::test_materialization_observer_omits_tool_and_reply_derived_text` — Tool-use summaries, reply text, validation messages, and failure detail remain absent from JSONL and the active snapshot while safe event fields remain.
- `TestMaterializePlanSeed::test_materialization_observer_does_not_change_result_or_retry_behavior` — Existing success, correction retry, and exhausted-result behavior remains the same with an observer attached.
- `TestRealInvoker::test_materialization_observer_restores_shell_binding_after_each_call` — A materializer call does not leave its redacting observer bound for a later stage or unrelated backend call.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `materialize_plan_seed()` can receive optional instrumentation without changing its default invoker, retry budget, result shape, or file-write behavior.
- A materialization observer records safe lifecycle events for every candidate it observes and carries the supplied plan attribution through them.
- Candidate corrections increment `seed_attempt`; shared-runner retries increment only `backend_attempt`.
- Every post-call materializer failure uses the final observed child ordinal, while a no-child return records null `backend_attempt` and `backend_child_started: false`.
- Materialization JSONL records and snapshots contain no prompt, seed body, reply text, reply head, validation prose, failure detail, provider transcript, or tool-input summary.
- Existing `RoadmapSeedMaterializeResult` and refresh-report diagnostics retain their current human-facing behavior.
- The observer restores shell-scoped state after success, ordinary failure, and interruption.
- `uv run pytest tests/test_roadmap.py -q` passes.

## References

- [Python subprocess — Subprocess Management](https://docs.python.org/3.13/library/subprocess.html#popen-objects) — Review child-process lifecycle and cleanup behavior behind nested backend attempts.
- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Confirm interrupt handling remains visible without suppressing `KeyboardInterrupt`.
- [JSON Lines Format](https://jsonlines.org/) — Keep each retained lifecycle record independently parseable.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Apply sensitive-data exclusion to durable structured records.

## Applicable guardrails

- **The plan’s “## Plan intent”, durable liveness contract:** Use the existing writer and snapshot surfaces so materializer activity remains visible through the same durable run record.
- **The plan’s “## Step intent”, redacting observer:** Record deterministic counters and safe descriptors only; do not treat redaction as optional cleanup after an event is built.
- **The plan’s “## Out of scope”, seed behavior:** Do not change materialization prompts, seed validity checks, retry limits, draft paths, sidecar schema, promotion behavior, or refresh reports.
- **The plan’s “## Out of scope”, limited rollout:** Keep the observer inside `plan_tool/roadmap.py`; do not change generic `claude_invoke` callers, the shared backend runner, or snapshot-isolation behavior.
- **The plan’s “## Out of scope”, durable data:** Do not persist content-bearing backend or seed values in either JSONL or `in-flight.json`.

## Deferred

- Command-owned writer startup, row phases, context transitions, terminal outcomes, and snapshot cleanup — steps 4 and 5 own these command paths.
- Source-row selection and refresh-report grouping — steps 4 and 5 preserve these command-level ordering rules.
- Operator-facing documentation of materializer event fields and redaction — step 6 owns the documentation surface.
