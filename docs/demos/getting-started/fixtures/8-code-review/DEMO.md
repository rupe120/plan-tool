# Step 8 — code review (`demo/8-code-review`)

**Open:** `git diff demo/7-reconcile-code demo/8-code-review -- todo tests`

**Decision to explain:** `/code-review` is a Claude Code session activity, not a plan-tool verb. It reviews the diff for bugs the plan could not see. Verify each finding against the code and existing tests before applying; repeat until two rounds are clean or low-yield.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/8-code-review` branch so this branch stays untouched):

```bash
mkdir -p .tmp
# In a Claude Code session on this branch (not a shell command):
/code-review
```

## Baked state

One finding applied: a hand-edited `due` string in the task file raised a raw `ValueError` traceback; it is now a `StoreError` that the CLI reports with exit 2, with a test. `uv run pytest -q` passes (12 tests).

Deliberately not covered: other corrupt-file shapes (a non-string `due`, a missing `id`, invalid JSON) still raise raw tracebacks. The review found one finding and the fix closes that one; widening it is a later review round.

Console output for this step without running it: `./step.sh transcript`.

**Next:** this is the last step; `./step.sh goto 1` restarts the walk.
