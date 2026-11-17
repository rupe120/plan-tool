# Step 7 — reconcile code (`demo/7-reconcile-code`)

**Open:** `git diff demo/6-run demo/7-reconcile-code -- todo tests`

**Decision to explain:** `reconcile-code` treats the plan as canonical and edits the code to match it. Here the plan's step 3 says `list` shows `(due YYYY-MM-DD)`, which the run omitted. Never use `reconcile-plan` after a run: it would edit the plan toward the code.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/7-reconcile-code` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-sonnet-5-5 reconcile-code due-dates --all \
  2>&1 | tee .tmp/due-dates.reconcile-code.log
```

## Baked state

One drift fixed: `todo list` prints ` (due YYYY-MM-DD)` for tasks with a date, plus a test. `uv run pytest -q` passes (11 tests). The plan is unchanged.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
