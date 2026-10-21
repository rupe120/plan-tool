> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-seed-materialization-observability.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Seed Materialization Observability

## Outcome

Every backend call made by `plan-tool roadmap --materialize` or
`--refresh-seeds` will have the same durable liveness contract as a roadmap
stage run: one command-level JSONL run record, a current `in-flight.json`
snapshot, redacted backend lifecycle/progress/retry/termination events, and
reliable cleanup on success, exhaustion, partial completion, or interrupt.
An operator can identify the selected plan ID for a single materialization and
each independently attempted plan ID in a refresh batch without inferring it
from a mutation lock or process table.

## In scope

- Bind a `RunLogWriter` for the two backend-calling seed actions,
  `--materialize` and `--refresh-seeds`, at the roadmap CLI/orchestrator
  boundary. Reuse the shipped shared-runner observer and event vocabulary;
  do not create a second materialization-specific log format.
- Define a stable command-level run identity for both actions and a
  plan-ID-attributed phase convention. A selected `--materialize <plan-id>`
  has one materialization phase; a refresh has one parent command run and one
  sequential phase per attempted plan. Every event and in-flight snapshot
  identifies the command, roadmap slug, and active plan ID where one exists.
- Thread the writer only through the standalone materializer and refresh loop
  so their existing `shell_roadmap_invoker` calls bind the shipped observer.
  Preserve the materializer's one-plan atomic write/state-update contract and
  refresh's independent failure isolation.
- Record the existing result distinctions at the command boundary: completed
  selected materialization, refresh completed, refresh partial, refresh
  exhausted, preflight refusal, and operator interrupt. The terminal log and
  snapshot teardown must describe the actual terminal reason rather than
  conflating a per-plan backend failure with a successfully completed batch.
- Keep redaction and retry behavior uniform with the shipped batch runner,
  including `backend_spawn`, stream activity/progress, stall suspicion,
  `backend_termination`, `backend_recovery_wait`, and `run_interrupted` when
  those events occur. No raw provider transcript or seed body belongs in the
  log.
- Add deterministic integration coverage using fake invokers and temporary
  roadmap roots for one success, one retry/exhaustion, an interrupted call,
  and a mixed refresh batch. The tests inspect JSONL ordering, in-flight
  fields while the call is active, final teardown, plan-ID attribution, and
  unchanged non-targeted drafts after a failed row.

## Architecture

`run_roadmap` already owns a run-log lifecycle around stage invocations;
`materialize_plan_seed` and `refresh_roadmap_seeds` currently own backend work
without that lifecycle. This effort gives the materialization command path the
same command-level owner, then passes its writer through the existing
materialization seams. The writer remains append-only history and
`in-flight.json` remains a small current projection; neither becomes seed
state, a source of truth for draft validity, or a replacement for
`seed-state.json`.

The refresh parent does not flatten independent seed attempts into one opaque
phase. It opens and closes a named phase per plan ID in roadmap order, allowing
one failed row to be visible without suppressing later rows. The command still
returns its existing aggregate result after every planned row has been
attempted. A single selected materialization uses the same per-plan phase
shape, so operators and future views have one vocabulary.

Read-only views, `--apply`, and `--accept-seed` do not invoke a backend and
remain outside this logging expansion. Stage runs retain their existing log
ownership; this work must not wrap them a second time.

## Out of scope / Non-goals

- Changing materialization prompt content, seed validity gates, retry counts,
  timeout values, seed-state schema, draft paths, promotion semantics, or the
  refresh report.
- Reducing stage-4 or materialization prompt size; that is owned by
  `roadmap-incremental-revision.md` and future prompt-budget work.
- Raw NDJSON provider transcripts, `runs show`/`runs watch`, browser streaming,
  percent-complete estimation, or a new monitoring service.
- A general observability rollout for other `claude_invoke` callers, concurrent
  same-slug snapshot isolation, or a production partial-stage command.
- Persisting seed bodies, prompts, or unredacted tool inputs in any log.

## Allowed behavior changes

- `--materialize` and `--refresh-seeds` create roadmap run directories and
  current in-flight snapshots while they are active, then leave a completed
  JSONL record after cleanup.
- Their output/run metadata gains command and active-plan attribution; normal
  draft/state/report writes and command exit-result meaning stay unchanged.

## Allowed reorganization

Only extract or reuse the smallest shared roadmap-command run-lifecycle helper
needed to prevent stage runs and materialization actions from duplicating
writer setup/teardown. Do not move artifact parsing, seed validation, or the
shared backend runner merely for symmetry.

## Verification

- A selected materialization produces a run start, its attributed phase,
  backend lifecycle/progress events, a terminal result, and no in-flight file
  after completion; the draft and sidecar write exactly as before.
- A refresh batch records each attempted plan ID in order, continues after one
  row fails, and ends with the correct aggregate completed/partial/exhausted
  outcome while preserving the failed row's prior draft and sidecar state.
- Retry, configured/silence termination, recovery wait, and Ctrl-C cases use
  the shipped event names and termination-reason rules; no raw seed text or
  unsafe tool-input data appears in JSONL or the snapshot.
- Backend-free modes create no lifecycle log merely because they read a
  roadmap. Existing stage-run logging remains single-owned and byte-compatible
  outside the new materialization actions.
- The roadmap-focused suite and the new materialization observability cases
  pass without a live backend; one disposable opt-in smoke verifies the active
  snapshot and its cleanup for a selected stale draft.

## Stop / defer

Record discoveries outside this command-path observability outcome in
`BACKLOG.md` or `BUG_BACKLOG.md`. Do not absorb prompt reduction, seed-content
quality, artifact migration, an operator dashboard, or generic multi-command
logging. If a shared lifecycle helper would alter stage-run output or leave the
existing atomic materialization write ambiguous, stop and surface that
ownership decision rather than widening the refactor.
