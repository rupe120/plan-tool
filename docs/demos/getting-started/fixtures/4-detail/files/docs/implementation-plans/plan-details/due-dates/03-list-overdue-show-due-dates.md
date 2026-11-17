# Step 3 — Add list --overdue and show due dates

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`todo list` gains `--overdue` and prints a due date after the title of any task that has one. `--overdue` keeps only open tasks whose due date is strictly before today; a task due today is not overdue. `main` takes an optional `today` so tests control the clock. Depends on step 2. On green, the filter and the display both behave as the acceptance criteria state.

## Table of Contents

- [Summary](#summary) — what the step ships
- [Why](#why) — why it comes at this point in the plan
- [Files](#files) — creates vs edits
- [Implementation](#implementation) — what must hold and the recommended approach
- [Tests](#tests) — coverage and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [Deferred](#deferred) — work this step leaves alone

## Why

This step delivers the seed's Outcome: seeing what is late. It comes last because it needs both the stored date (step 1) and a way to set it (step 2).

## Files

- **Edits:** `todo/cli.py` (`build_parser`, `main`), `tests/test_cli.py`.
- **New files:** none.

## Implementation

**Add `--overdue` (`store_true`) to the `list` subparser.** Filter with `not t.done and t.due is not None and t.due < today`. Use strict `<`: the plan fixes that a task due today is not overdue.

**Add `today: date | None = None` to `main`** and default it to `date.today()` inside, so tests pass a fixed date instead of patching the clock.

**Print the due date in the normal listing**: append ` (due YYYY-MM-DD)` after the title when `due` is set, and print nothing extra when it is not.

## Tests

Extend `tests/test_cli.py` with a fixed `today`: `--overdue` excludes done tasks, tasks with no due date, and a task due today, and includes one due yesterday; the plain listing shows `(due 2026-01-31)` for a task that has a date. Green before the step finishes.

## Acceptance criteria

- `todo list --overdue` lists only open tasks due strictly before today.
- A task due today does not appear under `--overdue`.
- `todo list` shows `(due YYYY-MM-DD)` after the title of a task that has a due date.

## Deferred

Sorting by due date and a non-zero exit when something is overdue are not part of the Outcome.
