> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-seed-materialization-observability.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool roadmap --materialize` and `--refresh-seeds` gain the durable liveness contract already used by roadmap stage runs: a command-level JSONL run record, a current `in-flight.json` snapshot, redacted backend lifecycle events, and reliable terminal cleanup. A selected materialization identifies its plan ID, while a refresh records one parent command run and a sequential phase for every attempted plan ID. The change reuses the shipped shared-runner observer without changing draft, state, report, promotion, or command-result semantics.

## Problem statement

`run_roadmap` already owns a run-log lifecycle around stage invocations, but `materialize_plan_seed` and `refresh_roadmap_seeds` perform backend work without that lifecycle. Operators therefore cannot durably inspect whether these actions are active or identify the selected or independently attempted plan IDs without relying on a mutation lock or process table. The missing command-level lifecycle also leaves success, exhaustion, partial completion, preflight refusal, and operator interrupt without the same observable terminal contract as stage runs.

## Architecture

Bind one `RunLogWriter` at the roadmap CLI/orchestrator boundary for `--materialize` and `--refresh-seeds`. Thread that writer only through the standalone materializer and refresh loop so their existing `shell_roadmap_invoker` calls bind the shipped observer and event vocabulary. The writer remains append-only history, while `in-flight.json` remains a small current projection; neither becomes seed state, a draft-validity source of truth, or a replacement for `seed-state.json`.

Both actions use a stable command-level run identity and a plan-ID-attributed phase convention. A selected `--materialize <plan-id>` has one materialization phase. A refresh has one parent command run and one sequential phase per attempted plan in roadmap order, allowing a failed row to remain visible while later rows continue. Every event and active snapshot identifies the command, roadmap slug, and active plan ID where one exists.

The command boundary records completed selected materialization, refresh completed, refresh partial, refresh exhausted, preflight refusal, and operator interrupt without treating a per-plan backend failure as a failed completed batch. The implementation preserves the materializer's one-plan atomic write/state-update contract, refresh's independent failure isolation, and the existing aggregate refresh result after all planned rows have been attempted.

Only the smallest shared roadmap-command run-lifecycle helper needed to avoid duplicated writer setup and teardown may be extracted or reused. Artifact parsing, seed validation, and the shared backend runner do not move merely for symmetry. Stage runs retain their existing single owner and must not be wrapped a second time; read-only views, `--apply`, and `--accept-seed` remain backend-free and outside this logging expansion.

## Out of scope

- Changing materialization prompt content, seed validity gates, retry counts, timeout values, the `seed-state.json` schema, draft paths, promotion semantics, or the refresh report; these are outside command-path observability.
- Reducing stage-4 or materialization prompt size; `roadmap-incremental-revision.md` and future prompt-budget work own that concern.
- Raw NDJSON provider transcripts, `runs show`/`runs watch`, browser streaming, percent-complete estimation, or a new monitoring service; this plan is limited to the existing durable lifecycle contract.
- A general observability rollout for other `claude_invoke` callers, concurrent same-slug snapshot isolation, or a production partial-stage command; these are separate concerns.
- Persisting seed bodies, prompts, or unredacted tool inputs in any log; lifecycle data remains redacted.

## Risks

- A shared lifecycle helper could alter existing stage-run output. Severity: not stated. Mitigation: extract or reuse only the smallest helper, retain single ownership, and require existing stage-run logging to remain byte-compatible. If that cannot be preserved, stop and surface the ownership decision.
- Writer setup or teardown could make the existing atomic materialization write ambiguous. Severity: not stated. Mitigation: preserve the one-plan atomic write/state-update contract. If ownership remains ambiguous, stop rather than widening the refactor.
- A per-plan backend failure could be conflated with the aggregate refresh result. Severity: not stated. Mitigation: use one attributed phase per attempted plan, preserve independent failure isolation, and emit the actual completed, partial, or exhausted terminal reason.
- Lifecycle records could expose seed text, provider transcripts, or unsafe tool-input data. Severity: not stated. Mitigation: reuse the shipped redaction behavior and exclude raw provider transcripts, seed bodies, prompts, and unredacted tool inputs.

## Testing

Add deterministic integration coverage using fake invokers and temporary roadmap roots. Cover one selected-materialization success, one retry/exhaustion, one interrupted call, and one mixed refresh batch. Inspect JSONL ordering, command and plan-ID attribution, active `in-flight.json` fields, terminal teardown, and preservation of non-targeted drafts plus the failed row's prior draft and sidecar state.

Exercise retry, configured/silence termination, recovery wait, and Ctrl-C behavior with the shipped event names and termination-reason rules. Verify that no raw seed text or unsafe tool-input data reaches JSONL or the snapshot, backend-free modes create no lifecycle log, and existing stage-run logging remains single-owned and byte-compatible.

Run the roadmap-focused suite and the new materialization observability cases without a live backend. Use one disposable opt-in smoke to verify the active snapshot and its cleanup for a selected stale draft. The seed supplies no test file paths or test-case identifiers.

## Acceptance criteria

- A selected materialization emits a command-level run start, an attributed plan phase, applicable backend lifecycle/progress events, and the actual terminal result, then removes `in-flight.json` while leaving a completed JSONL record.
- The selected materialization's draft and sidecar are written with the same atomic write/state-update behavior as before.
- A refresh records every attempted plan ID in roadmap order, continues after one row fails, and returns the existing aggregate refresh result after every planned row has been attempted.
- A refresh ends with the correct refresh completed, refresh partial, or refresh exhausted outcome and preserves the failed row's prior draft and sidecar state plus unchanged non-targeted drafts.
- Completed selected materialization, refresh completed, refresh partial, refresh exhausted, preflight refusal, and operator interrupt are recorded with their actual terminal reasons.
- When they occur, `backend_spawn`, stream activity/progress, stall suspicion, `backend_termination`, `backend_recovery_wait`, and `run_interrupted` follow the shipped event names, retry behavior, redaction, and termination-reason rules.
- Every event and active snapshot identifies the command, roadmap slug, and active plan ID where one exists.
- No raw provider transcript, seed body, prompt, or unredacted tool input appears in JSONL or `in-flight.json`.
- Read-only views, `--apply`, and `--accept-seed` create no lifecycle log merely because they read a roadmap.
- Existing stage-run logging remains single-owned and byte-compatible outside `--materialize` and `--refresh-seeds`.
- The roadmap-focused suite and deterministic materialization observability cases pass without a live backend, and one disposable opt-in smoke verifies active-snapshot creation and cleanup for a selected stale draft.

## Deferred

- Materialization and stage-4 prompt reduction remains with `roadmap-incremental-revision.md` and future prompt-budget work.
- Discoveries outside command-path observability are recorded in `BACKLOG.md` or `BUG_BACKLOG.md` instead of being absorbed into this plan.
- Seed-content quality, artifact migration, an operator dashboard, and generic multi-command logging remain separate future concerns.

## Input

This plan consumes the existing `run_roadmap` run-log lifecycle, `RunLogWriter`, the shared-runner observer, and the shipped event vocabulary and termination-reason rules. It also relies on the existing materializer one-plan atomic write/state-update contract, refresh independent failure isolation and aggregate result semantics, and `seed-state.json` remaining the seed-state source of truth. Verification is limited to preserving these named contracts and byte compatibility; the seed provides symbolic anchors but no file paths or schema field definitions.
