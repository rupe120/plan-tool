# Tier T3 — deterministic verifiability & grounding (P2), larger backlog arc

## File intent

This file is the baseline priority router for tier T3: `MISSION.md`'s P2
(deterministic verifiability), larger-scoped items. It is one of five
tier-baseline docs (`backlog-arc-tier-t1` … `t5`) that catalog `BACKLOG.md`'s
own curated `Priority (mission-grounded)` tier membership as standalone
routing guides.

## Choose this arc when

Tier T2 is clear (`backlog-arc-tier-t2.md`'s exit
condition holds) and no active feature-breakout arc or `BACKLOG.md`
Now/Next/Blocked/Parked board item is your session's constraint. #327 is
complete; its [seed-ingestion arc](backlog-arc-seed-ingestion.md) records the
delivered route and is not a current T3 pick.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool
work uses committed green-step checkpoints; direct changes include their
regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **#66** — contract-trace audit mode.
2. **#97** — symbol-aware prompt excerpts replacing head-only 4 KB (mission
   P3 "grounded in live code"). Run its excerpt-strategy spike before the
   build — this item is investigation-first, not implementation-ready as
   written.

## Exit and handoff

This tier is clear — proceed to the remaining idle plans (see `BACKLOG.md`'s
Now/Next/Blocked/Parked board, "Next (idle plans)" row, for the current list
— it is a working, frequently-refreshed list and is not duplicated here to
avoid drift), then to
[tier T4](backlog-arc-tier-t4.md) once #66 and #97 are each resolved or
explicitly deferred with a stated reason in `BACKLOG.md`.

## Out of scope

This file does not carry #66's or #97's implementation content — read each
item's full `BACKLOG.md` entry before acting. It does not widen to cover
unrelated verifiability/grounding work
that has not been tier-tagged T3 in `BACKLOG.md`.
