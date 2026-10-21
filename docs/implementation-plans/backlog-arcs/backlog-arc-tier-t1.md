# Tier T1 — trust core (P1) backlog arc

## File intent

This file is the baseline priority router for tier T1: `MISSION.md`'s P1
(converge/correctness), the highest-priority tier and the one every other
tier and arc is ranked below. It is one of five tier-baseline docs
(`backlog-arc-tier-t1` … `t5`) that catalog `BACKLOG.md`'s own curated
`Priority (mission-grounded)` tier membership as standalone routing guides,
so a session can open one file instead of re-deriving tier order from
`BACKLOG.md`'s prose each time.

## Choose this arc when

You need the single highest-priority pick and want to confirm nothing
outranks it. Choose a **feature-breakout arc** (see `BACKLOG.md` §
"Execution-routing arcs" for the current list) or the `BACKLOG.md`
Now/Next/Blocked/Parked board instead when your session is already
committed to a themed push — the tier docs are the fallback for "what's
next in general," not a supersede of an active named arc or board pick.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool
work uses committed green-step checkpoints; direct changes include their
regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **`BUG_BACKLOG.md`'s unblocked BUG, always first.** T1 leads every other
   tier and every arc while an unblocked BUG entry exists —
   `BUG_BACKLOG.md`'s own `## Triage` section carries its drain order and
   closure checklist directly; it has no separate arc doc.
2. **Historical: the original T1 work is delivered.** The plan-execution and
   post-run-reconciliation trust prerequisites that defined this tier shipped
   as [the trust-core arc](archive/backlog-arc-trust-core.md), complete
   2026-08-19. Do not reopen it; a genuinely new P1 need is a fresh
   item, not a reopening.
3. **No live T1-tagged backlog item exists today beyond step 1.** When a
   future session identifies P1-tier work (a convergence or correctness
   prerequisite that must land before other work is trustworthy), tag it T1
   in `BACKLOG.md`'s `Priority` section and add it here as an ordered item
   before moving to T2.

## Exit and handoff

This tier is clear — proceed to
[tier T2](backlog-arc-tier-t2.md) whenever `BUG_BACKLOG.md` has no unblocked
BUG and no live T1 item is recorded in step 3 above.

## Out of scope

This file does not resolve BUGs itself — see `BUG_BACKLOG.md`. It does not
re-litigate `archive/backlog-arc-trust-core.md`'s settled decisions.
