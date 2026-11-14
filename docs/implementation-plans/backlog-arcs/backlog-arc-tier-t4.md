# Tier T4 — grounding/workflow refinements (P3) + blocked backlog arc

## File intent

This file is the baseline priority router for tier T4: `MISSION.md`'s P3
(keep-true-to-live-code) grounding/workflow refinements, plus items currently
blocked on a design decision. It is one of five tier-baseline docs
(`backlog-arc-tier-t1` … `t5`) that catalog `BACKLOG.md`'s own curated
`Priority (mission-grounded)` tier membership as standalone routing guides.

## Choose this arc when

Tier T3 and the idle-plans list are clear
(`backlog-arc-tier-t3.md`'s exit condition holds) and
no active feature-breakout arc or `BACKLOG.md` Now/Next/Blocked/Parked board
item is your session's constraint.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool
work uses committed green-step checkpoints; direct changes include their
regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **#69**, **#38**, **#30** — read each item's full `BACKLOG.md` entry
   before acting; this file does not restate their content.

## Exit and handoff

This tier is clear — proceed to
[tier T5](backlog-arc-tier-t5.md) once #69, #38, and #30
are each resolved or explicitly deferred with a stated reason in
`BACKLOG.md`. In practice T4 and T5 are
routinely worked in either order; this ordering is the tier-number default,
not a hard dependency.

## Out of scope

This file does not carry any of its items' implementation content — read
each one's full `BACKLOG.md` entry before acting. It does not authorize
in-process parallelism; `CLAUDE.md` § "Architecture" sets that burden of proof.
