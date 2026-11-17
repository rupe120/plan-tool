# Step 2 — create plan (`demo/2-plan`)

**Open:** `docs/implementation-plans/due-dates.md`

**Decision to explain:** The seed's Outcome became the plan `intent`, each step carries its own intent and files, and the body repeats the seed's scope fence. Correct the plan or approve the bare-plan audit.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/2-plan` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-opus-5-5 create due-dates \
  --from-existing docs/implementation-plans/plan-seeds/due-dates.md \
  2>&1 | tee .tmp/due-dates.create.log
```

## Baked state

Adds the three-step plan and registers it in `.plan-tool/plans.json`. `plan-tool validate due-dates` and `plan-tool status due-dates` pass against it.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
