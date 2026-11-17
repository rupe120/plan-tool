# Step 6 — run (`demo/6-run`)

**Open:** `git diff demo/5-detail-audit demo/6-run -- . ':!DEMO.md' ':!DEMO.transcript.txt'` (code, tests, and the plan's step statuses)

**Decision to explain:** `run` executes each step in a fresh model subprocess, gates it on a changed test file plus `test_command`, and commits each green step. Review the diff against the detail files' acceptance criteria.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/6-run` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-sonnet-5-5 run due-dates --all --commit \
  2>&1 | tee .tmp/due-dates.run.log
```

## Baked state

Implementation and tests for all three steps, every step marked `done`, plan `completed`. `uv run pytest -q` passes (10 tests). The baked code deliberately omits showing the due date in `todo list`, which step 7 finds.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
