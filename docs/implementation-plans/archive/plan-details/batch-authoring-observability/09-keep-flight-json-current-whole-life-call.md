> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Keep in-flight.json current for the whole life of a call

## Summary

Adds `write_in_flight()` refresh calls inside `plan_tool/run_log.py:RunLogWriter`'s own emit methods — `phase_start()`, `backend_spawn()` (step 5), `claude_call_progress()` (the heartbeat), `backend_termination()` (step 5), and `backend_recovery_wait()` (step 5) — so `in-flight.json` tracks a call from spawn through heartbeats to termination, with a distinct "awaiting retry" state during `claude_invoke`'s recovery-loop sleep. The key design decision: the writer keeps one shared snapshot dict on the instance and every refresh merges field updates into it under a per-writer lock before writing, so a late heartbeat can never overwrite a termination status, and no caller anywhere adds its own refresh logic — `plan_tool/launcher.py`, `plan_tool/shell.py`, `plan_tool/backend_runner.py`, `plan_tool/roadmap.py`, and every CLI writer-opener stay at zero diff. `README.md`'s "The in-flight snapshot" section, which today promises refresh behavior the code doesn't deliver, becomes true and gains the status vocabulary and the explicit list of writer-less callers that produce no snapshot. Green when an operator can `cat` the snapshot mid-call and read the current phase, `elapsed_ms`/`silent_ms`, and a status that distinguishes running, awaiting retry, and terminated.

## Table of Contents

- [Summary](#summary) — what refreshes, where the writes live, and the merge-under-lock decision
- [Why](#why) — the one-write-then-stale gap, and the README claim the code doesn't back
- [Input](#input) — the step 4/5/7/8 contracts and HEAD facts this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — no new files; three edits
- [Implementation](#implementation) — the shared snapshot state, the five refresh sites, the status field, and the failure stance
- [Tests](#tests) — the new writer-level cases in tests/test_run_log.py
- [Acceptance criteria](#acceptance-criteria) — observable, checkable facts
- [References](#references) — the atomic-replace contract behind every refresh
- [Applicable guardrails](#applicable-guardrails) — plan fences this step's writes sit inside
- [Deferred](#deferred) — reads/rendering, per-run identity, and the emit sites that deliberately don't refresh

## Why

`write_in_flight()` has exactly one call site at HEAD — inside `plan_tool/run_log.py:RunLogWriter.start()` — so `in-flight.json` is a photograph of the run's first instant: it never learns the current phase, never moves during a 20-minute claude call, and looks identical whether the backend is streaming happily or has been wedged for 15 minutes. `README.md`'s "The in-flight snapshot" section already tells operators the file is "written atomically … on every phase and claude-call boundary" and documents a `current_phase` / `last_event_ts` schema — a promise the code does not keep, since neither field is ever written. Steps 5–8 built the events that mark every interesting moment of a call's life (spawn, heartbeat, termination, recovery wait, interrupt); this step makes the one-file summary reflect those same moments, so an operator can answer "is it alive?" with `cat … | jq .` instead of tailing the whole JSONL. The refresh on `backend_recovery_wait` matters specifically: without it, the snapshot after a failed attempt would show a terminated call during the retry-loop sleep — indistinguishable from the call actually being over.

## Input

- **Step 5's writer surface** — `RunLogWriter` gains `backend_spawn()`, `backend_termination()`, and `backend_recovery_wait()` emit methods plus internal tracking of the most recent termination reason. This step adds refresh calls inside those methods; read the landed field names off the step-5/7 code rather than out of those steps' detail prose — the landed names win.
- **Step 7's observer routing** — batch calls' spawn/heartbeat/stall/termination signals reach the writer through the observer `claude_invoke` builds, and `run`'s lane keeps passing a bare writer. Both lanes land in the same `RunLogWriter` methods, which is what lets this step refresh in one place. If the landed observer routes a signal to a different writer method than named below, put the refresh in the method the landed code actually calls.
- **Step 8's interrupt handling** — `run_end()` is guaranteed on interrupt paths (roadmap's `finally` wrapper, `run_cmd.py`'s handlers), and `run_end()` unlinks the snapshot. This step keeps `run_end()` as the only delete site but adds one guard to the unlink (see Implementation): before this step, the snapshot barely changed after `start()`, so a same-slug sibling deleting it mid-run cost little; after this step the snapshot is the operator's live answer for the whole call, which is exactly what makes an unguarded unlink a total loss of signal worth preventing.
- **HEAD facts** — `plan_tool/launcher.py`'s heartbeat daemon calls `run_logger.claude_call_progress(...)` directly from a daemon thread, already wrapped so an IO-failing emit can't kill the thread; `plan_tool/run_log.py:read_in_flight()` returns `None` on any `schema_version` mismatch; `write_in_flight()` is atomic per call (sibling tempfile + `os.replace`); `RunLogWriter` uses `__slots__`, so new instance state means new slot entries.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `plan_tool/run_log.py` — keep the snapshot dict built in `RunLogWriter.start()` as instance state (new `__slots__` entries for the state dict and a lock); add a private refresh helper; call it from `phase_start()`, `backend_spawn()`, `claude_call_progress()`, `backend_termination()`, and `backend_recovery_wait()`; extend the start snapshot with a status field; update the module docstring's in-flight paragraph.
- `tests/test_run_log.py` — approx. 12 new writer-level cases (roster below), reusing the existing `_make_writer` helper.
- `README.md` — rewrite the "### The in-flight snapshot" section to match what ships: the refresh triggers, the status vocabulary, the heartbeat fields, and the explicit statement of which callers produce no snapshot; touch the `in-flight.json` bullet under "## Run logs" so its refresh claim names the new triggers.

## Implementation

- **Hold the snapshot as writer state, refresh by merging.** `RunLogWriter.start()` already builds the snapshot dict it writes; keep that dict on the instance instead of discarding it. Add a private helper — one way: `_refresh_in_flight(**updates)` — that, under a new per-writer lock, merges the updates into the held dict, stamps `last_event_ts` with `utc_now_iso()`, and calls `write_in_flight()` with the merged result. Merging (never rebuilding from scratch) is what guarantees every write still carries `schema_version`, `run_id`, `command`, `plan_slug`, `started_at`, and `log_path`, so `read_in_flight()` keeps accepting the file after any refresh. `__slots__` must grow entries for the state dict and the lock.
- **The five refresh sites, all inside `plan_tool/run_log.py`:**
  - `phase_start(phase)` — sets `current_phase` and returns `status` to the running state.
  - `backend_spawn()` (step 5's method) — running status plus the identifying fields the landed spawn event carries: `child_pid` (the one an operator can act on directly), `effective_timeout_ms`, `transport`, and `prompt_bytes` — populated by step 7's runner-native bracket for every streaming-lane call, and `None` only in step 5's short-lived pre-step-7 batch bracket.
  - `claude_call_progress()` — writes `elapsed_ms`, `silent_ms`, and `last_tool` into the snapshot. This method **never writes `status`** — that single rule is what makes a late heartbeat harmless (see below).
  - `backend_termination()` (step 5's method) — a terminated status plus the termination reason the writer already tracks (step 5), which is step 4's closed vocabulary.
  - `backend_recovery_wait()` (step 5's method) — a distinct awaiting-retry status plus the wait details the landed event carries, so the snapshot during a rate-limit or backoff sleep reads as "sleeping on purpose", not "over".
- **Status vocabulary.** Recommend a small closed set — likely `running`, `awaiting_retry`, `backend_terminated` — with the exact spellings the implementer's to choose. Three properties are not free to vary: a status field exists; the retry wait is distinguishable from termination; and the next `phase_start()`/`backend_spawn()` flips the status back to running so a multi-phase run doesn't stay marked terminated between calls. Whatever ships, `README.md` documents those spellings — read them off the landed code.
- **Why merge-under-lock rather than each site writing its own dict:** the heartbeat refresh runs on `launcher.py`'s daemon thread (and, after step 7, the runner's threads for batch calls) while `phase_start`/`backend_termination` run elsewhere. `write_in_flight()` already makes each individual write atomic, so the file can't tear — the hazard is ordering: a heartbeat that fires just after termination would, with rebuild-per-site, write a "running" snapshot over a terminated one. Because the heartbeat merges into the shared dict and never touches `status`, its late write re-emits the terminated status with fresher timing fields — correct either way. The lock serializes the merge+write pairs; keep it separate from the module-level `_APPEND_LOCK`, which guards the JSONL fd write.
- **Refreshes are best-effort; the JSONL is not.** Swallow `OSError` (and `Exception` from serialization, if you prefer the wider net) inside the refresh helper, matching `run_end()`'s unlink stance — a broken snapshot write must not fail the run or kill the heartbeat daemon. The JSONL append's existing raise behavior (`RunLogLineTooLarge`, IO errors surfacing to the emit guard) is unchanged; only the snapshot write is forgiving.
- **Deliberately no refresh** on `claude_call_stall_suspected()` (the same heartbeat tick that detects the stall already refreshed `silent_ms`), on `claude_call_start()`/`phase_end()`/the `bind_shell_sink` call-end path (spawn, heartbeat, and termination already bracket the same moments — more writes buy no operator-visible freshness), and on the iteration/checkpoint/roadmap emit methods.
- **`run_end()` stays the only delete site, with one new guard on the unlink.** Before removing the snapshot, read it back (`read_in_flight()`) and skip the unlink when its `run_id` no longer matches this writer's own — a newer same-slug run has since claimed the file, and deleting it would erase a still-running sibling's liveness signal entirely (reading as "nothing is running" until that sibling's next refresh — the false-negative window this whole step exists to close). This is a read-check-skip on the one existing file: no run-id-scoped file names, no cross-process lock, matching the plan's Out of scope as revised. Wrap the read in the same best-effort stance as the unlink itself (`OSError` → proceed with today's behavior). While in the file, correct `in_flight_path`'s docstring, which describes teardown as "last-writer-wins... overwrites" — the code unlinks; the docstring should say writes overwrite and teardown is a guarded delete.
- **No `RUN_LOG_SCHEMA_VERSION` bump.** The snapshot is deliberately a free-form dict (`write_in_flight()`'s docstring) and the new fields are additive; a bump would make `read_in_flight()` reject every older snapshot and `plan-tool runs show` exit 1 on every existing log for no compatibility gain.
- **Zero-diff callers, by design.** Because every write rides inside the writer's own methods, no file outside the three declared ones changes: not `plan_tool/launcher.py`, `plan_tool/shell.py`, `plan_tool/backend_runner.py`, or `plan_tool/roadmap.py`, and none of the `RunLogWriter.start` openers across `plan_tool/cli/` and `plan_tool/create.py`/`detail.py`/`bench.py`. They all inherit snapshot freshness the moment their existing emit calls run. Callers with no open writer — `plan_tool/annotate.py`, `plan_tool/jira.py`, and `create.py`'s slug-generation call — keep producing no snapshot, and the README states that plainly instead of leaving it implied.

## Tests

All in `tests/test_run_log.py`, reusing `_make_writer` (which roots a real writer at `tmp_path`) and `read_in_flight` for assertions.

### Tests for this step

Every test below must be green before this step is finished.

- `test_start_snapshot_reports_running_status` — `start()`'s snapshot carries the running status alongside the existing fields.
- `test_phase_start_refreshes_current_phase` — after `phase_start("propose_steps")`, the snapshot shows that phase and a `last_event_ts`.
- `test_refresh_keeps_snapshot_readable` — after several refreshes, `read_in_flight()` still returns the dict (schema_version, run_id, and the other start fields survive every merge).
- `test_backend_spawn_refreshes_snapshot` — a spawn emit updates the snapshot with the spawn fields and running status.
- `test_heartbeat_refreshes_elapsed_and_silent_ms` — `claude_call_progress()` lands `elapsed_ms`/`silent_ms`/`last_tool` in the snapshot.
- `test_heartbeat_never_writes_status` — a heartbeat after `backend_recovery_wait()` leaves the awaiting-retry status in place while updating the timing fields.
- `test_backend_termination_writes_status_and_reason` — the snapshot shows the terminated status and the tracked termination reason.
- `test_recovery_wait_status_distinct_from_termination` — the awaiting-retry snapshot is distinguishable from a terminated one by status value.
- `test_late_heartbeat_after_termination_keeps_terminated_status` — emit termination, then a heartbeat; the snapshot's status still reads terminated (the merge rule, pinned).
- `test_next_phase_start_returns_status_to_running` — termination followed by `phase_start()` flips the status back.
- `test_refresh_swallows_snapshot_write_failure` — with `write_in_flight` monkeypatched to raise `OSError`, `phase_start()` neither raises nor skips its JSONL append.
- `test_distinct_slugs_keep_independent_snapshots` — two writers on different slugs refresh without touching each other's files (the plan's Testing note about concurrent runs means distinct slugs).
- `test_run_end_skips_unlink_when_a_newer_run_owns_the_snapshot` — writer A starts, then writer B on the same slug starts (its `start()` overwrites the snapshot with B's `run_id`); A's `run_end()` leaves the file in place, still carrying B's `run_id`; B's own `run_end()` then removes it.
- `test_run_end_still_unlinks_own_snapshot` — the ordinary single-run case: `run_end()` with the writer's own `run_id` on disk removes the file, pinning that the guard changed nothing for the common path.
- Existing cases stay green untouched: the `write_in_flight`/`read_in_flight` round-trip and fail-safe tests assert the primitives, not the writer's call pattern, and no existing test pins "start is the only write".

## Acceptance criteria

- `grep -c "write_in_flight(" plan_tool/run_log.py` shows the refresh helper's single write call plus `start()`'s — and `rg "write_in_flight" plan_tool/ --glob '!run_log.py'` still returns nothing: no caller-side refresh logic anywhere.
- Mid-run, after a `phase_start` and one heartbeat, `read_in_flight()` returns a dict containing `current_phase`, `elapsed_ms`, `silent_ms`, `last_event_ts`, and a running status.
- During a recovery-loop sleep the snapshot's status is the awaiting-retry value, not the terminated one; after `backend_termination()` it carries the termination reason.
- A heartbeat emitted after termination leaves the terminated status in place.
- `run_end()` removes the snapshot when the on-disk `run_id` is its own (or the file is unreadable), and leaves it in place when a newer same-slug run's `run_id` is on disk — both pinned by direct writer-level tests.
- A snapshot-write `OSError` during any emit method does not raise and does not suppress that method's JSONL row.
- `RUN_LOG_SCHEMA_VERSION` is unchanged, and every refresh's output still passes `read_in_flight()`.
- `git diff --stat` for the step touches only `plan_tool/run_log.py`, `tests/test_run_log.py`, and `README.md`.
- `README.md`'s "### The in-flight snapshot" section names the refresh triggers and status spellings that actually shipped, and states that `annotate`, `jira`, and `create`'s slug-generation call produce no snapshot.
- The full suite is green (`uv run pytest tests/ -q -n auto`).

## References

- [os — os.replace](https://docs.python.org/3/library/os.html#os.replace) — the atomic-overwrite contract every refresh leans on: a reader always sees a complete previous or complete new snapshot, never a partial write.

## Applicable guardrails

- **The step intent's ownership rule** — every snapshot write lives in a `RunLogWriter` method; this step may not add refresh calls in `launcher.py`, `shell.py`, `backend_runner.py`, `roadmap.py`, or any CLI handler, and may not give writer-less callers a snapshot.
- **The plan's "## Out of scope", runs rendering** — this step only writes the file; no `runs show`/`runs watch` work, and README's examples stay `cat … | jq`.
- **The plan's "## Out of scope", same-slug concurrency** — `in_flight_path` stays one file per slug and *writes* stay last-writer-wins; do not add run-id-scoped snapshot names or locking across processes. The one in-scope carve, stated there: `run_end()`'s teardown gets the read-check-skip guard above so a completing call cannot delete a newer sibling's live snapshot — a guard on the existing delete, not a second identity.
- **The plan's "## Out of scope", percent-complete estimation** — the snapshot carries liveness facts only (phase, timing, status, reason); no progress fractions or ETA fields.
- **The plan intent's unchanged-contracts fence** — `claude_invoke`'s `(rc, stdout)` contract and all parsing/gate logic are untouched; this step changes nothing outside the writer's snapshot behavior and its docs.

## Deferred

- Rendering or tailing the snapshot (`runs show` / `runs watch`) — the carved-out follow-on plan's concern; operators read the file directly.
- Separate snapshot identities for concurrent same-slug calls — the plan's Out of scope keeps last-writer-wins.
- Refresh on `claude_call_start`, `phase_end`, the `bind_shell_sink` call-end path, and `claude_call_stall_suspected` — spawn, heartbeat, and termination already bracket those moments; stated above as deliberate, not left implied.
- Registering the snapshot shape in `DATA_CONTRACT.md` — the snapshot stays a deliberately free-form dict per `write_in_flight()`'s docstring; pinning a schema there is a separate decision no step in this plan takes.
- Giving the seven inherited `claude_invoke` callers roadmap-quality operator rendering of the fresher snapshot — the plan's Out of scope routes per-command rendering to follow-up work.
