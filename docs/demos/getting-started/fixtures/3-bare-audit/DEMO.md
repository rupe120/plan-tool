# Step 3 — bare plan audit (`demo/3-bare-audit`)

**Open:** the plan's `## Acceptance criteria` and `## Risks` (the audit finding is applied there)

**Decision to explain:** At bare stage the audit judges the plan body, not detail coverage (0 of 3 steps have details; that is not a defect). It found one real plan-level gap, the due-today boundary. Read the finding, make one judged hand-edit, re-audit.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/3-bare-audit` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-sonnet-5-5 completeness-audit due-dates --iterate --commit \
  2>&1 | tee .tmp/due-dates.bare-audit.log
```

## Baked state

The plan after one judged hand-edit: a due-today acceptance criterion and a matching risk. The saved audit report lives under `docs/implementation-plans/plan-details/due-dates/reports/` after a live run; it is not baked.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
