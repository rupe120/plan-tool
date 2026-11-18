# Due dates for tasks

## Outcome

A task can carry an optional due date, and `todo list --overdue` shows only the open tasks whose due date has passed.

## In scope

- The `Task` model and the JSON store, so a due date survives a save and a load.
- `todo add --due YYYY-MM-DD` to set the date, rejecting a malformed date with a clear error.
- `todo list --overdue` to filter, and a visible due date on every listed task that has one.

## Out of scope

- Recurring tasks, reminders or notifications.
- Time-of-day, time zones or relative dates such as "tomorrow".
- Editing the due date of an existing task.
- Changes to task ordering.
- Any change to the storage location or file format beyond one optional `due` key.

## Allowed behavior changes

- `todo add` accepts `--due`; `todo list` accepts `--overdue` and prints a due date when one is set.
- Task files written before this change keep loading unchanged.

## Allowed reorganization

None.

## Testing

Prove the Outcome with the existing pytest suite: a due date round-trips through the store, an invalid date is refused with a non-zero exit, a pre-change task file still loads, and `--overdue` excludes done tasks and tasks without a due date.

## Stop / defer

File anything outside this fence (for example editing a due date) in `BACKLOG.md` instead of widening the plan.

## References

- `todo/model.py:Task`, `todo/store.py`, `todo/cli.py:main`

## Scope guardrails

Keep existing task files readable and preserve task ordering. Limit the
stored format change to the optional `due` key.

## Audit guardrails

None

## Expected placement

Use the existing task model, JSON store, CLI, and their tests.
