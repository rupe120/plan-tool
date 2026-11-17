---
format_version: 1
title: Due dates for tasks
intent: A task can carry an optional due date, and `todo list --overdue` shows only the open tasks whose due date has passed.
status: planning
priority: medium
risk_profile: low
risk_profile_rationale: Small additive change to a local CLI with no external consumers.
test_command: uv run pytest -q
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/due-dates.md
steps:
- id: 1
  description: Store an optional due date on tasks
  intent: Make a due date survive a save and a load without breaking existing task files.
  files:
  - todo/model.py
  - todo/store.py
  - tests/test_store.py
  complexity: low
  change_type: feature
  status: pending
- id: 2
  description: Accept --due when adding a task
  intent: Let a user set the due date, refusing a malformed date with a clear error.
  files:
  - todo/cli.py
  - tests/test_cli.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  status: pending
- id: 3
  description: Add list --overdue and show due dates
  intent: Let a user see which open tasks are past due.
  files:
  - todo/cli.py
  - tests/test_cli.py
  complexity: low
  change_type: feature
  depends_on:
  - 2
  status: pending
---
# Due dates for tasks

## Overview

Tasks in the `todo` CLI gain an optional due date. A new `--overdue` filter on
`todo list` shows the open tasks whose due date is before today.

## Problem statement

A task list with no dates cannot answer "what am I late on?". Users keep dates in
titles and scan by eye.

## Architecture

`Task` gains an optional `due` date. The JSON store writes it as an ISO-8601
string under an optional `due` key and reads rows that lack the key as `due=None`,
so files written before this change keep loading. `todo add` parses `--due` with
`date.fromisoformat` and refuses anything else through argparse. `todo list`
prints the due date when set and filters with `--overdue`, comparing against an
injectable `today` so tests do not depend on the clock.

## References

- `todo/model.py:Task`, `todo/store.py:load`, `todo/store.py:save`
- `todo/cli.py:main`, `todo/cli.py:build_parser`
- `docs/implementation-plans/plan-seeds/due-dates.md` — the source seed and its scope fence.

## Steps

1. Store an optional due date on tasks.
2. Accept `--due` when adding a task.
3. Add `list --overdue` and show due dates.

## Out of scope

- Recurring tasks, reminders or notifications.
- Time-of-day, time zones or relative dates.
- Editing the due date of an existing task.
- Any storage change beyond one optional `due` key.

## Risks

- A task file written before this change has no `due` key; loading it must not fail.
- `--overdue` must not list done tasks or tasks without a due date.

## Testing

Run `uv run pytest -q`. Each step adds or updates a test: store round-trip and
legacy-file load (step 1), `add --due` success and refusal of a bad date (step 2),
and `--overdue` filtering plus due-date display (step 3).

## Acceptance criteria

- A due date round-trips through `store.save` and `store.load`.
- A task file with no `due` key loads with `due=None`.
- `todo add "x" --due 2026-01-31` stores the date; `--due 31/01/2026` exits non-zero with an error.
- `todo list --overdue` lists only open tasks whose due date is before today.
- `todo list` shows `(due YYYY-MM-DD)` after the title of a task that has a due date.

## Deferred

Editing a due date and recurring tasks stay in the backlog.
