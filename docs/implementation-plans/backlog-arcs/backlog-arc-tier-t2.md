# Tier T2 — convergence & structural-remedy machinery (P1/P3) backlog arc

## File intent

This file is the baseline priority router for tier T2: convergence and
structural-remedy machinery, spanning `MISSION.md`'s P1 (converge/correctness)
and P3 (keep-true-to-live-code). It is one of five tier-baseline docs
(`backlog-arc-tier-t1` … `t5`) that catalog `BACKLOG.md`'s own curated
`Priority (mission-grounded)` tier membership as standalone routing guides.

## Choose this arc when

Tier T1 is clear (`backlog-arc-tier-t1.md`'s exit condition holds)
and no active feature-breakout arc or `BACKLOG.md` Now/Next/Blocked/Parked
board item is your session's constraint. This tier is currently small — one
theoretical, decision-first item — so most sessions will pass through it
quickly to T3.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool
work uses committed green-step checkpoints; direct changes include their
regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **#71** — parked. Unpark when a `detail --reconcile` apply is seen
   narrowing scope or softening a criterion despite the prompt; until then
   this tier has no active route position. Read its full entry in
   `BACKLOG.md` § A (New capability, well-scoped) before acting.

## Exit and handoff

This tier is clear — proceed to
[tier T3](backlog-arc-tier-t3.md) while #71 is parked; if #71 is unparked, resolve it (implemented, or
closed with a recorded "no action" result) first.

## Out of scope

This file does not itself carry #71's investigation content or decision
criteria — read its full `BACKLOG.md` entry before acting. It does not widen
to cover unrelated convergence/structural-remedy work that has not been
tier-tagged T2 in `BACKLOG.md`.
