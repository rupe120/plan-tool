# Step 5 — detail audit (`demo/5-detail-audit`)

**Open:** the saved report (live run) and the three detail files

**Decision to explain:** The grounded audit now reads the detail bundle and the code at HEAD. Check the coverage line, qualification and convergence outcome, not just the exit code: a clean exit does not mean a clean audit.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/5-detail-audit` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-sonnet-5-5 completeness-audit due-dates --iterate --commit \
  2>&1 | tee .tmp/due-dates.detail-audit.log
```

## Baked state

No file changes: this baked audit comes back clean, so the branch differs from `demo/4-detail` only in its card and transcript. A real run may find something; apply real findings by judged hand-edit.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
