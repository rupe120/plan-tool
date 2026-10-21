# Scored-run results, 2026-10-14

36 trials ran to completion from the frozen `schedule.json`: no nonzero exit,
failed turn, or limit breach; 3,896,340 non-cached tokens in total. Per-trial
values are in `scored-results.json`. These are automated external-check results
only; owner scope/rule assessment is not yet done.

| Measure | A (full CLAUDE.md) | B (compact + reference) |
|---|---|---|
| Passes external check | 18 / 18 | 13 / 18 |
| Median pair change, input+output tokens | baseline | +48.6% (more) |
| Median pair change, non-cached tokens | baseline | +21.6% (more) |
| Median pair change, elapsed time | baseline | +38.9% (more) |

B failures: T6 repetitions 1–3 (Stack is not recognized as a guardrail heading
in the fence), T2 repetitions 1–2 (Stack row display labels lack the `stack`
prefix). Against the DESIGN.md screening bar (B accepted wherever A is accepted;
median reduction of at least 20% tokens or 15% time) B does not qualify on
these automated results. Limits: 18 pairs; reviewer-session usage is not
separately observable; two graders were relaxed after seeing outputs
(RECHECK.md).
