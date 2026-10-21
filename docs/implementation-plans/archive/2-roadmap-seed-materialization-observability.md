> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Seed Materialization Observability
intent: 'Every backend call made by `plan-tool roadmap --materialize` or `--refresh-seeds`
  will have the same durable liveness contract as a roadmap stage run: one command-level
  JSONL run record, a current `in-flight.json` snapshot, redacted backend lifecycle/progress/retry/termination
  events, and reliable cleanup on success, exhaustion, partial completion, or interrupt.
  An operator can identify the selected plan ID for a single materialization and each
  independently attempted plan ID in a refresh batch without inferring it from a mutation
  lock or process table.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Extract behavior-preserving roadmap command lifecycle setup
  intent: Provides one lifecycle owner for seed actions without changing existing
    stage or `--apply` records.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/01-extract-behavior-preserving-roadmap.md
  status: done
- id: 2
  title: Add an optional per-run context envelope to the shared run-log writer
  intent: Gives seed-action lifecycles a context path that reaches every event and
    snapshot while writer callers that opt out retain byte-compatible records.
  files:
  - plan_tool/run_log.py
  - plan_tool/roadmap.py
  - tests/test_run_log.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Supplies the behavior-preserving lifecycle owner that will opt into writer
      context.
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/02-optional-per-run-context-envelope.md
  status: done
- id: 3
  title: Log source-ordered, plan-attributed materialization attempts through a redacting
    observer
  intent: Records every materializer candidate, inner backend recovery, and post-call
    failure with deterministic counters and only safe descriptors, never prompts,
    seed contents, reply-derived text, or tool-input summaries.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Supplies command lifecycle ownership without changing existing records.
    2: Supplies context on every writer event and snapshot for the redacting observer.
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/03-log-source-ordered-plan-attributed.md
  status: done
- id: 4
  title: Give selected and all-eligible --materialize commands one lifecycle and clean
    up in-flight.json across every terminal outcome
  intent: Lets operators inspect the selected row from its preparation through completion
    or failure for selected, multi-row, and zero-eligible materialization commands,
    including partial, validation-refused, and unexpected-error paths, without changing
    report replacement or command-result semantics.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Supplies command-level writer setup and terminal cleanup.
    2: Supplies writer context on run start, call end, run end, and snapshots.
    3: Supplies redacted per-attempt and failure event behavior.
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/04-give-selected-all-eligible-materialize.md
  status: done
- id: 5
  title: Give --refresh-seeds one ordered run, preserve successful seed and report
    replacements plus failed-row state, and remove in-flight.json
  intent: Shows which plan is active from per-row preparation through completion or
    failure during a refresh and retains evidence for every attempted source-order
    row, including an empty completed batch, while retaining the existing changes-then-failures
    refresh-report format.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Supplies command-level writer setup and terminal cleanup.
    2: Supplies writer context on every event and snapshot.
    3: Supplies the safe per-plan phase and failure event vocabulary.
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/05-give-refresh-seeds-one-ordered-run.md
  status: done
- id: 6
  title: Document materialization and refresh run phases, outcomes, redaction, and
    backend-free command boundaries
  intent: Keeps operators and contributors aligned on which roadmap actions log, what
    they record, and how their tests avoid a live backend.
  files:
  - README.md
  - DATA_CONTRACT.md
  - TESTING.md
  - CAPABILITIES.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    2: Defines the writer context schema and byte-compatibility behavior.
    3: Defines the landed per-plan event and redaction behavior.
    4: Defines materialization outcomes and cleanup contract.
    5: Defines refresh ordering, report format, aggregate outcomes, and cleanup contract.
  detail: docs/implementation-plans/plan-details/roadmap-seed-materialization-observability/06-document-materialization-refresh-run.md
  status: done
---
# Roadmap Seed Materialization Observability

## Overview

`plan-tool roadmap --materialize` and `--refresh-seeds` gain the durable liveness contract already used by roadmap stage runs: a command-level JSONL run record, a current `in-flight.json` snapshot, redacted backend lifecycle events, and reliable terminal cleanup. A selected materialization identifies its plan ID; an all-eligible materialization and a refresh record one parent command run and a sequential phase for every attempted source-order plan row, beginning before that row's baseline and prompt preparation. A materialization-specific observer retains the shipped lifecycle vocabulary while removing unsafe tool inputs and reply-derived failure text before JSONL or snapshot writes. Draft, promotion, state-sidecar, report, source-row processing, and command-result semantics remain unchanged.

## Problem statement

`run_roadmap` already owns a run-log lifecycle around stage invocations, but `materialize_plan_seed` and `refresh_roadmap_seeds` perform backend work without that lifecycle. Operators therefore cannot durably inspect whether these actions are active or identify the selected or independently attempted plan IDs without relying on a mutation lock or process table. The missing command-level lifecycle also leaves success, exhaustion, partial completion, preflight refusal, and operator interrupt without the same observable terminal contract as stage runs.

## Architecture

After a slug is safe to use as a run-log path, bind one behavior-preserving roadmap-command lifecycle owner for `--materialize` and `--refresh-seeds`. `_cmd_roadmap_materialize` owns the materialize writer across artifact loading, classification, selected refusal, zero-row no-op, row work, report rendering, and terminal cleanup; `refresh_roadmap_seeds` owns the equivalent refresh lifecycle. The shared writer then gains a small optional per-run context envelope, used only by those owners: it includes immutable `command: "roadmap"` plus the materialization fields, and is merged into run start, every writer-emitted event (including the shell call-end sink), run end, and every in-flight snapshot refresh. The owner may update only the row and attempt fields atomically as a phase begins and ends; it must not replace the command identity. With no envelope, the writer keeps its existing bytes and snapshot shape, so stage and `--apply` records do not change. Their `shell_roadmap_invoker` calls bind a materialization-specific observer that preserves shipped lifecycle, retry, progress, and termination events but removes unsafe fields before they reach JSONL or the current snapshot. The writer remains append-only history, while `in-flight.json` remains a small current projection; neither becomes seed state, a draft-validity source of truth, or a replacement for `seed-state.json`.

Both actions use a stable command-level run identity and a plan-ID-attributed phase convention. Materialization and refresh retain the existing `artifact.plans` source-row order for selecting, invoking, writing, and logging rows; they do not adopt `04-roadmap.md`’s `ordering` execution sequence. The existing refresh report remains out of the execution-order contract: it continues rendering all change blocks followed by all failure blocks, with source order preserved inside each group. A selected `--materialize <plan-id>` has one `seed-materialize:<plan-id>` phase. `--materialize` without an ID has one such phase for every recoverable source-order row; if no row is eligible the command records an explicit completed no-op with no phase. A refresh has the same source-order phase shape for every attempted plan, including a failed row, and records a completed empty batch when the roadmap contains no rows. Each selected row phase begins before its baseline reads, artifact reload, prompt rendering, and backend invocation, then ends after that row's result handling; a pre-backend row failure is therefore attributed to its row instead of being silently outside the plan-ID guarantee.

Every JSONL event and every `in-flight.json` projection created by these two actions carries immutable `command: "roadmap"` plus four materialization-only context fields owned by that lifecycle envelope: `roadmap_action` (`"materialize"` or `"refresh-seeds"`), `roadmap_slug` (the CLI slug), `requested_plan_id` (the selected ID for `--materialize <plan-id>`, otherwise `null`), and `active_plan_id` (the row ID while that row is being processed, otherwise `null`). The envelope reaches run start, phase-start, backend lifecycle/progress/retry, call-end, phase-end, safe per-row failure, and run-end events as well as every snapshot. A phase-end event retains its row ID. Immediately after it, the lifecycle clears `active_plan_id` and writes one inter-phase snapshot with literal `null`; terminal records and snapshots also carry `null`. Command-level preflight failure records preserve a selected requested ID but set `active_plan_id` to `null`; all-eligible preflight, no-op, and empty-refresh records set both plan-ID fields to `null` when no selected ID applies.

`seed_attempt` is the materializer's one-based candidate-seed attempt and remains stable across any recovery inside that call. `backend_attempt` is the shared runner's one-based child-process attempt within that seed attempt. The observer retains the greatest child ordinal it observed for the active `seed_attempt`; every post-call materializer failure, including an unusable reply or a validation rejection, uses that final-child ordinal rather than an arbitrary first or last child. If the shared wrapper returns before a child starts, such as the missing-executable fast path, that failure carries the current `seed_attempt`, literal-null `backend_attempt`, and `backend_child_started: false`; a child-bearing failure sets that marker true. The new pair is authoritative. For compatibility, candidate-level materializer events use legacy `attempt = seed_attempt` and do not carry `next_attempt`; child lifecycle events (`claude_call_*`, spawn, stream/progress, termination, interruption) use legacy `attempt = backend_attempt`; and a recovery-wait uses legacy `attempt = backend_attempt` for the failed child plus `next_attempt = backend_attempt + 1` for the upcoming child. The materialization observer preserves that child ordinal at call end instead of allowing the generic bind-time sink to replace it with a candidate attempt. At run start, phase start/end, the immediate cleared inter-phase snapshot, and terminal snapshots both new counters are literal `null`. Before every row `phase_end`, the owner clears both counters while retaining the row ID; after phase end it clears the row ID and writes the immediate literal-null inter-phase snapshot. This makes a model correction retry distinguishable from a rate-limit or transient recovery without changing the shared runner's semantics.

Known command-level artifact, classification, selection, validation, or refusal errors preserve their current halt-and-usage behavior: the command lifecycle records `preflight-refused` before a row is selected, then exits without processing later rows. Once a row is selected, its phase is already active for baseline, artifact, and prompt setup; a known row-scoped validation/refusal closes that phase as `preflight-refused` with its plan ID and null counters, then retains the same halt behavior. The shared shell wrapper normalizes a runner failure to a nonzero invocation result, so it remains a retryable `failure_kind=invoke` within the current `seed_attempt` and becomes `exhausted` only after the existing materializer attempt budget is spent. Exhausted model rows retain the existing independent batch continuation; known validation errors do not gain that behavior. An exception that escapes writer startup during active row work — including baseline, backend, draft, promoted-copy, or sidecar writes — records `error` through that row's failure event and phase-end with its active ID and only a static safe error class. A command-scoped report-publication error occurs after all row phases, records `error` without a row failure or phase, and has literal-null inactive row context. Both paths clear the envelope before their terminal record and final snapshot. Every active phase closes and every path tears down the snapshot.

Materialization failure events carry only `failure_kind`, a numeric return code when one exists, attempt and violation counts, and boolean presence markers. They never copy `failure_detail`, validation messages, reply heads, prompts, seed bodies, or tool-input summaries into JSONL or a snapshot. The existing human-facing refresh report is outside that log contract and retains its current content and grouping.

The terminal record uses one closed outcome mapping. `completed` means the selected materialization succeeded, every eligible all-eligible row succeeded, or every refresh row succeeded (including an empty refresh); `no-op` means all-eligible materialization found no recoverable row; `partial` means a batch landed at least one row and had at least one exhausted model row; `exhausted` means no row landed and at least one row spent its backend attempt budget; `preflight-refused` means a known validation or refusal halted command processing before a backend attempt; `interrupted` means Ctrl-C stopped the action and maps to its existing exit 130; and `error` means an exception escaped after writer startup. Every terminal record, including `error`, preserves the command's existing error rendering and exit behavior, contains only its static safe class where applicable, and uses literal-null inactive row context before it clears the snapshot. Batch processing continues after exhausted model rows, while preflight refusal, error, and interruption stop the command.

The materializer preserves an ordered per-file write and mismatch-detection contract, not a multi-file transaction: it atomically replaces the draft first, writes an already-published promoted copy next when needed, then writes `seed-state.json` last. A later failure can leave an earlier file replaced while the prior sidecar remains; the digest mismatch is the detectable recovery state. Refresh keeps independent row failure isolation and the existing aggregate result and exit status after every planned row has been attempted.

Only the smallest shared writer context envelope, roadmap-command lifecycle helper, and materialization observer boundary needed to avoid duplicated writer setup, teardown, attribution, and filtering may be extracted or reused. Artifact parsing, seed validation, and the shared backend runner do not move merely for symmetry. Stage runs retain their existing single owner and must not be wrapped a second time. Read-only views and `--accept-seed` remain log-free. `--apply` remains backend-free but retains its existing apply-specific run record unchanged and gains no materialization events.

## Input

This plan consumes the existing `run_roadmap` run-log lifecycle, `RunLogWriter`, the shared-runner observer, and the shipped event vocabulary and termination-reason rules. It introduces only an optional writer context envelope and a materialization-specific observer boundary; together they attach defined command and plan attribution fields while filtering unsafe tool inputs and reply-derived failure text from every scoped event and snapshot. It also relies on existing source-row materialization/refresh execution, grouped refresh-report rendering, ordered per-file draft/promotion/state writes with mismatch detection, refresh independent failure isolation and aggregate result semantics, `--apply`'s existing apply-specific run record, and `seed-state.json` remaining the seed-state source of truth. Verification is limited to preserving these named contracts and byte compatibility; the seed provides symbolic anchors but no file paths or schema field definitions.

## References

- [Claude Code CLI Reference](https://code.claude.com/docs/en/cli-usage) — Documents non-interactive execution, stream-json output, partial messages, and lifecycle-related CLI flags used by backend invocations.
- [Python subprocess — Subprocess Management](https://docs.python.org/3.13/library/subprocess.html#popen-objects) — Defines Popen streaming, waiting, termination, timeout, and child-process cleanup behavior needed for backend lifecycle handling.
- [Python signal — Asynchronous Event Handlers](https://docs.python.org/3.13/library/signal.html#general-rules) — Explains SIGINT translation to KeyboardInterrupt and signal delivery rules relevant to reliable interrupt logging and cleanup.
- [Python os.replace](https://docs.python.org/3.13/library/os.html#os.replace) — Specifies atomic replacement semantics used to publish and remove current in-flight snapshots without torn state.
- [POSIX write() Specification](https://pubs.opengroup.org/onlinepubs/9699919799/functions/write.html) — Defines O_APPEND and write atomicity guarantees relevant to concurrent append-only JSONL run records.
- [JSON Lines Format](https://jsonlines.org/) — Defines UTF-8 newline-delimited JSON conventions for producing durable, independently parseable lifecycle event records.
- [OWASP Logging Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html) — Provides security guidance for structured event logging, sensitive-data exclusion, sanitization, correlation, and log integrity.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing materialization prompt content, seed validity gates, retry counts, timeout values, the `seed-state.json` schema, draft paths, promotion semantics, or the refresh report; these are outside command-path observability.
- Reducing stage-4 or materialization prompt size; `roadmap-incremental-revision.md` and future prompt-budget work own that concern.
- Raw NDJSON provider transcripts, `runs show`/`runs watch`, browser streaming, percent-complete estimation, or a new monitoring service; this plan is limited to the existing durable lifecycle contract.
- A general observability rollout for other `claude_invoke` callers, concurrent same-slug snapshot isolation, or a production partial-stage command; these are separate concerns.
- Persisting seed bodies, prompts, or unredacted tool inputs in any log; lifecycle data remains redacted.

## Risks

- A shared lifecycle helper could alter existing stage-run output. Severity: not stated. Mitigation: extract or reuse only the smallest helper, retain single ownership, and require existing stage-run logging to remain byte-compatible. If that cannot be preserved, stop and surface the ownership decision.
- Writer setup or teardown could obscure the existing ordered draft, promotion, and sidecar writes. Severity: not stated. Mitigation: preserve their per-file order, distinguish the detectable sidecar mismatch from a transaction, and never roll it back from a logging path.
- A per-plan backend failure, all-eligible no-op, mixed batch, empty refresh, command refusal, or setup error could be conflated with the aggregate command result. Severity: not stated. Mitigation: start the command lifecycle before selection, start each row phase before that row's preparation, distinguish command preflight from row-scoped pre-backend failure and normalized backend failure, apply the closed terminal-outcome precedence, and preserve existing exhaustion-only batch continuation.
- A reader could infer the wrong active plan or retry from a phase name or stale snapshot field. Severity: not stated. Mitigation: emit the defined context and the `seed_attempt`/`backend_attempt` pair, retain the active row through phase end, preserve the final observed child ordinal on post-call failure, and then write one immediate literal-null inter-phase snapshot.
- An observer-only implementation could leave run-start, call-end, run-end, or a snapshot without attribution. Severity: not stated. Mitigation: the lifecycle-owned writer envelope reaches every writer event path and snapshot refresh, and unit tests preserve default writer bytes when no envelope is supplied.
- A write or setup error could leave an active snapshot or falsely report a completed/exhausted command. Severity: not stated. Mitigation: map every unexpected error after writer startup to terminal `error`, preserve current command behavior, and test teardown on each path.
- Lifecycle records could expose seed text, reply-derived failure detail, provider transcripts, or unsafe tool-input data. Severity: not stated. Mitigation: permit only the defined safe failure descriptors and exclude reply heads, validation prose, seed bodies, prompts, and tool inputs from JSONL and the snapshot.
- The new lifecycle could accidentally replace `--apply`'s existing record or add materialization events to it. Severity: not stated. Mitigation: retain its current apply-specific run owner and byte-compatible event shape, then characterize it alongside the new log-free read-only and accept paths.

## Testing

Add deterministic integration coverage using fake invokers and temporary roadmap roots. Characterize the behavior-preserving lifecycle extraction first. Then unit-test the optional writer envelope on run start, every event path including call-end, run end, and every snapshot refresh, and prove untouched writer callers retain byte-compatible records. Use a fixture whose `plans` source order differs from `ordering` to prove selected and all-eligible materialization plus refresh retain source-row invocation, write, phase, and event order while the existing refresh report still groups changes before failures. Assert that a row phase starts before its baseline and prompt setup, phase-end keeps its row ID, then the next snapshot immediately clears it. Drive one outer candidate correction retry containing multiple inner backend retries and prove the two counters distinguish `seed_attempt` from `backend_attempt` on every call, lifecycle, recovery, and snapshot event; prove every post-call materializer failure uses the final observed child ordinal, while a no-subprocess return uses null `backend_attempt` plus `backend_child_started: false`. Cover selected materialization success, command preflight refusal, row-scoped validation/refusal before a backend attempt, exhaustion, and interrupt; multi-row all-eligible completion, partial, and zero-row no-op; plus refresh completed, partial, exhausted, interrupted, and empty-batch completion. Exercise unexpected setup/baseline and draft/promoted-copy/sidecar write errors inside a row, asserting active-row failure/phase attribution, null backend counters where no child started, a static safe error class, literal-null terminal row context, and teardown. Separately force the post-phase refresh-report write to fail, asserting command-scoped `error` with no active row or row failure/phase, current command behavior, teardown, and the ordered partial-write/mismatch state.

Exercise retry, configured/silence termination, recovery wait, and Ctrl-C behavior with the shipped event names and termination-reason rules. Feed fake tool-use, failed-reply, and validation-prose values through the materialization observer and verify that JSONL and snapshots contain only the allowed safe fields while lifecycle and progress events remain. Verify that views and `--accept-seed` create no record, `--apply` preserves its existing apply-specific record without materialization events, and existing stage-run logging remains single-owned and byte-compatible.

Run the roadmap-focused suite and the new materialization observability cases without a live backend. Use one disposable opt-in smoke to verify the active snapshot and its cleanup for a selected stale draft. The seed supplies no test file paths or test-case identifiers.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A selected materialization emits a command-level run start, an attributed plan phase, applicable backend lifecycle/progress events, and the actual terminal result, then removes `in-flight.json` while leaving a completed JSONL record.
- All materialization and refresh selection, invocation, writes, phases, and lifecycle events retain the current `artifact.plans` source-row order even when `ordering` differs; the existing refresh report continues to render change blocks before failure blocks, with source order within each group.
- An all-eligible materialization emits an attributed phase for every recoverable source-order row; when no row is eligible, it emits an explicit completed no-op command record with no plan phase and still removes `in-flight.json`.
- A selected materialization atomically replaces the draft, then any already-published promoted copy, then `seed-state.json`; a later failure preserves the earlier replacement and prior sidecar so mismatch detection remains possible.
- A refresh records every attempted plan ID from row preparation through its result in source-row order, continues after one exhausted model row, and returns the existing aggregate refresh result after every planned row has been attempted; an empty roadmap records a completed run with zero phases and cleans up its snapshot.
- The terminal record uses `completed`, `no-op`, `partial`, `exhausted`, `preflight-refused`, `interrupted`, or `error` exactly as the defined outcome mapping requires; command preflight preserves its current halt-and-usage behavior before a row is selected, row-scoped pre-backend refusal retains its plan ID and null counters through phase end, normalized backend faults exhaust only after their retry budget and retain existing batch continuation, escaping post-start failures use only a static safe error class, and every terminal record has literal-null `active_plan_id`.
- All-eligible materialization and refresh preserve the failed row's prior draft and sidecar state plus unchanged non-targeted drafts, including when a non-empty batch ends partial or exhausted.
- When they occur, `backend_spawn`, stream activity/progress, stall suspicion, `backend_termination`, `backend_recovery_wait`, and `run_interrupted` follow the shipped event names, retry behavior, redaction, and termination-reason rules.
- Every scoped event and active snapshot, including run start, call end, and run end, carries `command`, `roadmap_action`, `roadmap_slug`, `requested_plan_id`, and `active_plan_id`; phase end retains the row ID, and the immediately following inter-phase snapshot plus every terminal record uses literal `null`.
- Every backend-bearing event and snapshot carries stable `seed_attempt` and inner `backend_attempt` counters, so correction retries and backend recoveries remain distinguishable; a post-call materializer failure takes its `backend_attempt` from the final observed child, a no-child return uses literal `null` with `backend_child_started: false`, inactive snapshots set both counters to `null`, and recovery snapshots retain the just-finished backend attempt.
- No raw provider transcript, seed body, prompt, tool-input summary, reply head, failure detail, or validation prose appears in materialization JSONL or `in-flight.json`; safe shared-runner lifecycle, progress, failure kind, numeric status, and count fields remain present.
- Read-only views and `--accept-seed` create no lifecycle log merely because they read a roadmap. `--apply` retains its existing apply-specific JSONL record unchanged and contains no materialization events.
- Existing stage-run logging remains single-owned and byte-compatible outside `--materialize` and `--refresh-seeds`.
- The roadmap-focused suite and deterministic materialization observability cases pass without a live backend, and one disposable opt-in smoke verifies active-snapshot creation and cleanup for a selected stale draft.

## Deferred

- Materialization and stage-4 prompt reduction remains with `roadmap-incremental-revision.md` and future prompt-budget work.
- Discoveries outside command-path observability are recorded in `BACKLOG.md` or `BUG_BACKLOG.md` instead of being absorbed into this plan.
- Seed-content quality, artifact migration, an operator dashboard, and generic multi-command logging remain separate future concerns.
