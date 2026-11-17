# Step 2 — Accept --due when adding a task

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`todo add` gains `--due YYYY-MM-DD`. The value is parsed with `date.fromisoformat` through an argparse `type=` callable, so a malformed date is refused by argparse with a clear message and exit status 2 before any task is written. Depends on step 1's `Task.due`. On green, `todo add "x" --due 2026-01-31` stores the date and a bad date stores nothing.

## Table of Contents

- [Summary](#summary) — what the step ships
- [Why](#why) — why it comes at this point in the plan
- [Files](#files) — creates vs edits
- [Implementation](#implementation) — what must hold and the recommended approach
- [Tests](#tests) — coverage and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [Deferred](#deferred) — work this step leaves alone

## Why

The seed's Outcome needs a way to set the date, and the plan's risks require malformed input to be refused rather than stored. Parsing at the argparse boundary keeps that check in one place.

## Files

- **Edits:** `todo/cli.py` (`build_parser`, `main`), `tests/test_cli.py`.
- **New files:** none.

## Implementation

**Add a `parse_date` function and use it as `type=` on `--due`.** It wraps `date.fromisoformat` and raises `argparse.ArgumentTypeError(f"invalid date {text!r}; use YYYY-MM-DD")` on `ValueError`. Argparse then exits with status 2 and prints the message.

**Pass the parsed date into `Task(..., due=args.due)`** when adding. Leave `due=None` when the flag is absent.

Do not widen the accepted formats; the seed fences out relative dates and time zones.

## Tests

Extend `tests/test_cli.py`: `add --due` stores the date (read it back with `store.load`); `add --due 31/01/2026` raises `SystemExit` with code 2 and leaves the file unwritten. Green before the step finishes.

## Acceptance criteria

- `todo add "x" --due 2026-01-31` stores `due=date(2026, 1, 31)`.
- `todo add "x" --due 31/01/2026` exits with status 2 and writes no task.
- `todo add "x"` without `--due` still stores `due=None`.

## Deferred

Editing the due date of an existing task is out of scope (seed: Out of scope).
