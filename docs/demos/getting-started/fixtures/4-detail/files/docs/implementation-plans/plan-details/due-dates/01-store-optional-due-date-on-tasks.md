# Step 1 — Store an optional due date on tasks

<!-- plan-tool:detail-format-version: 1 -->

## Summary

`Task` gains an optional `due` date and the JSON store round-trips it as an ISO-8601 string under an optional `due` key. Rows without the key still load, with `due=None`, so task files written before this change keep working. No CLI behavior changes in this step. On green, a due date survives `save` then `load` and a pre-change file loads unchanged.

## Table of Contents

- [Summary](#summary) — what the step ships
- [Why](#why) — why it comes at this point in the plan
- [Files](#files) — creates vs edits
- [Implementation](#implementation) — what must hold and the recommended approach
- [Tests](#tests) — coverage and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [Deferred](#deferred) — work this step leaves alone

## Why

Steps 2 and 3 both read `Task.due`. Landing the model and storage first gives the CLI steps a stable shape and isolates the one risk the plan names: breaking existing task files.

## Files

- **Edits:** `todo/model.py` (`Task`), `todo/store.py` (`load`, `save`), `tests/test_store.py`.
- **New files:** none.

## Implementation

**Add `due: date | None = None` to `Task`**, after the existing defaulted fields so positional construction elsewhere keeps working.

**Serialize explicitly instead of `vars(task)`.** `vars` would put a `date` object in the row and `json.dumps` would fail. Write `due` as `task.due.isoformat()` and omit the key entirely when `due` is `None`, so files without due dates stay byte-for-byte what they were.

**Read with `row.get("due")`** and parse with `date.fromisoformat` only when present. A missing key is the legacy-file case and must yield `due=None`, not an error.

## Tests

Extend `tests/test_store.py`: a task with a due date round-trips; a task without one writes no `due` key; a hand-written legacy file (rows with only `id`, `title`, `done`) loads with `due=None`. `uv run pytest -q` must be green before the step finishes.

## Acceptance criteria

- `Task(1, "a", due=date(2026, 1, 31))` survives `store.save` then `store.load` unchanged.
- A saved task with no due date has no `due` key in the JSON file.
- A task file with no `due` keys loads with every `due` equal to `None`.

## Deferred

The `--due` option and `--overdue` filter belong to steps 2 and 3. Validating stored dates beyond `fromisoformat` is out of scope.
