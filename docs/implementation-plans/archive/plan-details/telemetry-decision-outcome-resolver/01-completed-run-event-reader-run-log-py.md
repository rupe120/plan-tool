> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a completed-run event reader to run_log.py

## Summary

Adds a fail-safe reader to `plan_tool/run_log.py` that reads a *finished* run's JSONL event log — the sibling to today's `read_in_flight`, which only reads the live in-progress snapshot. Ships two public functions: `read_run_events(path)`, a tolerant JSONL parser that returns the run's event dicts (empty list when the file is missing or garbage), and `read_run_outcome(path)`, a thin typed summary that pulls the terminal `run_end` outcome/rc plus any per-step `iteration_end` outcomes into a frozen `RunOutcome`. The key decision: this is a plain leaf primitive with **no** first-party imports and no Claude — the later resolver leaf (step 3) joins a decision to its run by calling these on the path it builds from a `DecisionEvent`'s `run_id`/`plan_slug`, without reaching into `plan_tool.cli`. On green, both readers parse real logs written by `RunLogWriter`, degrade to empty/`None` on missing or damaged files, and never reject a line on schema-version mismatch.

## Table of Contents

- [Why](#why) — what's missing today and why the resolver needs it now
- [Input](#input) — the run-log JSONL contract this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the two readers, the summary shape, and the tolerance rules to hold
- [Tests](#tests) — unit cases added with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/format docs relevant to this step
- [Deferred](#deferred) — the JSONL-reader consolidation left for reconcile

## Why

`plan_tool/run_log.py` today can write a run's events and read the live `in-flight.json` snapshot (`read_in_flight`), but there is **no leaf-level way to read a completed run's events back**. The only JSONL readers that exist — `plan_tool/cli/runs.py:_iter_events` and `_load_events_with_skips` — live in the `plan_tool.cli` layer, which the telemetry resolver (step 3, a cycle-free leaf) is forbidden to import. The resolver's whole async-outcome path joins a recorded decision to its later run outcome on `run_id` and reads `RunEnd.outcome`/`rc` (and, where present, `IterationEnd.outcome`). Without a reader sitting at the `run_log` leaf, step 3 would either duplicate the tolerant-parse logic inside a leaf or be unable to reach the run outcome at all. This step lands that reader as the shared foundation steps 2–3 build on.

## Input

This step reads the **run-log JSONL** written by `plan_tool/run_log.py`'s `append_event` / `RunLogWriter`. The shape it depends on:

- **One JSON object per line**, each with a string `event` discriminator (`"run_start"`, `"run_end"`, `"iteration_end"`, …). See the `Event` union and `_BaseEvent` in `plan_tool/run_log.py`.
- **`run_end` line** carries `outcome` (str), `rc` (int), `duration_ms` (int), and `run_id`; `error` (str) is present **only when set** — `RunLogWriter.run_end` merges it via `**extra`, so it is not a guaranteed key. Read it with `.get("error")`.
- **`iteration_end` line** (from the `IterationEnd` dataclass) carries `step_id` (int) and `outcome` (str). Note: no code emits `iteration_end` today — the dataclass exists in the union but has no `RunLogWriter` method or producer. So on real logs the per-step map is empty; the reader must tolerate zero of them, not assume they exist.
- **Schema versions may be mixed.** Appenders never reject a line on `schema_version` (pinned by `tests/test_run_log.py:test_append_event_does_not_reject_mismatched_schema_version`); the reader must not reject on it either. Old and new lines coexist in one log.
- **Lines can be blank, truncated, or non-dict** (a partial last line from a crash). The reader skips those rather than raising.

The path is composed by the caller via `plan_tool/run_log.py:run_log_path(repo_root, slug, run_id)` — this step takes a `Path`, mirroring `read_in_flight(path)`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/run_log.py` — add the `RunOutcome` frozen dataclass, `read_run_events(path)`, and `read_run_outcome(path)`, placed beside `read_in_flight` in the reader region.
  - `tests/test_run_log.py` — add unit tests for both readers and the `RunOutcome` shape, in a new section (mirror the existing `# ----------` section-comment style).

## Implementation

**Add `read_run_events(path: Path) -> list[dict[str, Any]]` — the core "completed-run event reader" the title names.**
- **Return the run's event dicts in file order.** Open the JSONL, `json.loads` each non-blank line, keep only dict top-level values. This is the leaf twin of `plan_tool/cli/runs.py:_iter_events`, but returns a list (not a generator) and is import-clean.
- **Degrade to an empty list, never raise.** A missing file or any `OSError` returns `[]`. This mirrors the fail-safe stance of `read_in_flight` (which returns `None`) and `plan_tool/telemetry.py:read_decisions` (which returns `[]` on `OSError`). Empty-on-missing is exactly what the resolver wants: a decision whose run wrote no log joins to nothing.
- **Skip damage, don't reject the file.** Blank lines, lines that fail `json.loads`, and non-dict top-level values (a bare list/number) are skipped; the surviving good lines are still returned. This tolerates a truncated final line from a crash mid-write.
- **Do not filter on `schema_version` or the `event` discriminator.** Keep the reader/appender asymmetry: appenders write everything, readers degrade — never drop a line for a stale version. Typed interpretation is the caller's job.

**Add a `RunOutcome` frozen dataclass — the typed terminal summary the resolver joins on.** Suggested fields:
- `run_id: str`
- `completed: bool` — `True` only when a `run_end` line was present. This is the key distinction: a log with events but no `run_end` (a crashed or still-running invocation) returns `completed=False`, which step 3 can read as `still-open`.
- `outcome: str`, `rc: int`, `duration_ms: int` — from the `run_end` line (defaults `""`/`0`/`0` when absent).
- `error: Optional[str]` — from `run_end`'s optional `error` extra; `None` when not set.
- `iteration_outcomes` — per-step `step_id → outcome` from any `iteration_end` lines. Empty today. One way: a tuple of `(step_id, outcome)` pairs to stay immutable like the frozen intent; a `dict` default via `field(default_factory=dict)` is also fine and matches how `RunStart.argv` already carries a mutable default inside a frozen dataclass.

Mark it `@dataclass(frozen=True)` to match every other event record in this module.

**Add `read_run_outcome(path: Path) -> Optional[RunOutcome]` — a thin summary over `read_run_events`.**
- **Return `None` when there is nothing to summarize** — no readable file, or an empty/all-blank/all-garbage log (i.e. `read_run_events` yields `[]`). This mirrors `read_in_flight`'s `Optional` contract: `None` means "no completed run at this path".
- **Find the terminal `run_end` by scanning for `event == "run_end"`; take the last match** if more than one exists (append-only, last writer wins). Set `completed=True` and copy `outcome`/`rc`/`duration_ms`/`error` off it.
- **When events exist but no `run_end` is found,** still return a `RunOutcome` with `completed=False`, `outcome=""`, `rc=0`, and `run_id` taken from the first event. Do not collapse this into `None` — the crashed-run vs. missing-file distinction is what the resolver needs to tell `still-open` apart from `no run`.
- **Collect `iteration_end` outcomes** into `iteration_outcomes` (empty when none, which is the norm today).
- **Resolve `run_id`** from the `run_end` line when present, else the first event's `run_id`, else `""`.

**Constraints that are not free to vary:**
- **No first-party imports.** `run_log.py` is a leaf whose module top must stay free of `plan_tool.*` imports (its only such imports today are lazy, in-method `from plan_tool import shell` / `telemetry`). Both new readers use only `json`, `pathlib`, and existing module-level names — add nothing at module top.
- **Take a `Path`, not `(repo_root, slug, run_id)`.** Mirror `read_in_flight(path)`; the caller composes the path via `run_log_path`. Keeps the readers trivially testable against `tmp_path`.
- **Never raise on I/O or parse errors.** Both readers are observational; a broken filesystem or half-written log must degrade, not escalate.

**Shared logic (audit note):** the tolerant "one JSON dict per line, skip damage" parse now lives in three places — `plan_tool/cli/runs.py:_iter_events`, `plan_tool/cli/runs.py:_load_events_with_skips`, and this new `read_run_events`. Consolidating the two cli readers onto this leaf primitive would edit `plan_tool/cli/runs.py`, which is outside this step's declared files and is a behavior-preserving refactor `detail` cannot mint here — see `## Deferred`.

## Tests

Add to `tests/test_run_log.py` (unit, `tmp_path`, no Claude), authored with the implementation.

**`read_run_events`:**
- `test_read_run_events_returns_empty_when_missing` — absent path returns `[]`.
- `test_read_run_events_returns_empty_on_oserror` — a path that can't be read (e.g. a directory) returns `[]`, no raise.
- `test_read_run_events_parses_each_line_in_order` — three appended events read back as three dicts in file order.
- `test_read_run_events_skips_blank_lines` — blank lines between events are ignored.
- `test_read_run_events_skips_malformed_trailing_line` — a truncated non-JSON final line is skipped; earlier good lines survive.
- `test_read_run_events_skips_non_dict_lines` — a line that is a bare JSON list/number is skipped.
- `test_read_run_events_keeps_mismatched_schema_version` — a line with `schema_version` 99 is still returned (reader/appender asymmetry).

**`read_run_outcome`:**
- `test_read_run_outcome_returns_none_when_missing` — absent path returns `None`.
- `test_read_run_outcome_returns_none_on_empty_log` — empty/all-blank file returns `None`.
- `test_read_run_outcome_extracts_run_end` — a `run_end` line yields `completed=True` with matching `outcome`/`rc`/`duration_ms`.
- `test_read_run_outcome_reads_optional_error` — `run_end` with an `error` extra surfaces it; without it, `error is None`.
- `test_read_run_outcome_incomplete_when_no_run_end` — events with no `run_end` yield `completed=False` and `run_id` from the first event.
- `test_read_run_outcome_takes_last_run_end` — two `run_end` lines: the last wins.
- `test_read_run_outcome_collects_iteration_outcomes` — synthetic `iteration_end` lines populate the per-step map; a log with none yields an empty map.
- `test_read_run_outcome_from_real_writer` — drive `RunLogWriter.start(...)` then `run_end(outcome=..., rc=...)`, read `read_run_outcome(writer.log_path)`, assert the outcome round-trips.

**`RunOutcome`:**
- `test_run_outcome_is_frozen` — reassigning a field raises `FrozenInstanceError`.

### Test-creation order (feature step)

This is a **feature** step. Write each test above alongside the code that makes it pass. Green-before-done gate: every new test in `tests/test_run_log.py` must pass (`uv run pytest tests/test_run_log.py -q`) before this step is considered finished.

## Acceptance criteria

- `read_run_events(path)` returns a `list[dict]` of events in file order, and `[]` for a missing/unreadable file — no exception.
- `read_run_events` skips blank, malformed, and non-dict lines while returning the good ones, and does not drop a line for a mismatched `schema_version`.
- `read_run_outcome(path)` returns `None` when the log is missing or has no events, and a `RunOutcome` otherwise.
- A `RunOutcome` from a log with a `run_end` line has `completed=True` and the line's `outcome`/`rc`/`duration_ms`; a log with events but no `run_end` has `completed=False`.
- `RunOutcome` is a frozen dataclass.
- `plan_tool/run_log.py` module top still has no `plan_tool.*` imports.
- All new tests in `tests/test_run_log.py` pass.

## References

- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — `json.loads` semantics and `JSONDecodeError`, the basis for the per-line tolerant parse.
- [JSON Lines format specification](https://jsonlines.org/) — the newline-delimited JSON format the run-log JSONL follows and this reader streams.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` and `field(default_factory=...)`, used for `RunOutcome` (and `FrozenInstanceError`, asserted by the frozen test).

## Deferred

- **Consolidating the tolerant JSONL parse** — `plan_tool/cli/runs.py:_iter_events` and `_load_events_with_skips` duplicate the parse `read_run_events` now owns; folding them onto the leaf reader edits `cli/runs.py` (outside this step's files) and is a behavior-preserving refactor. Route to reconcile.
- **Run discovery / listing** — enumerating a slug's `run_id`s (scanning `run_dir`) is not added here; the resolver builds a path directly from a `DecisionEvent`'s `run_id`/`plan_slug`. Add only if a later step shows it necessary.
- **Emitting `iteration_end` events** — no producer writes `IterationEnd` today; the reader tolerates their absence but this step does not add an emitter. Owned by whatever step wires per-step run-log outcomes, if ever.
- **The decision→run-log join and verdict derivation** — matching a decision to its `RunOutcome` and deriving `acted-on`/`no-op`/`reverted`/`still-open` is step 3's work (which may reuse `plan_tool/convergence_diagnosis.py`'s region-matching approach for the sidecar-transition path); this step only supplies the read.
