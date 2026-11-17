# Step 4 — detail creation (`demo/4-detail`)

**Open:** `docs/implementation-plans/plan-details/due-dates/` (three files)

**Decision to explain:** Each detail file turns a plan step into an implementation route: what must hold, a recommended approach, the tests, and checkable acceptance bullets. Review them for anything the seed's fence rules out.

## Live command

Run from the previous checkpoint (`./step.sh live` puts you there on a throwaway
`live/4-detail` branch so this branch stays untouched):

```bash
mkdir -p .tmp
set -o pipefail && plan-tool --model claude-sonnet-5-5 detail due-dates --commit \
  2>&1 | tee .tmp/due-dates.detail.log
```

## Baked state

Three run-grade detail files, one per step, and `steps[].detail` set in the plan. All three pass the real `parse_detail_response` gate.

Console output for this step without running it: `./step.sh transcript`.

**Next:** `./step.sh next`
