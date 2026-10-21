# Tier T5 — export leg / UX / hygiene / cosmetic backlog arc

## File intent

This file is the baseline priority router for tier T5: export-leg work, UX
polish, process/hygiene refactors, and cosmetic/churn items — the lowest of
the five tiers. It is one of five tier-baseline docs (`backlog-arc-tier-t1`
… `t5`) that catalog `BACKLOG.md`'s own curated `Priority (mission-grounded)`
tier membership as standalone routing guides.

## Choose this arc when

Tier T4 is clear (`backlog-arc-tier-t4.md`'s exit
condition holds) and no active feature-breakout arc or `BACKLOG.md`
Now/Next/Blocked/Parked board item is your session's constraint. **Read the
gate below before picking an item from this tier** — several T5 candidates
are deliberately parked behind a concrete demonstrated need, not ready by
default just because they are tier-listed.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool
work uses committed green-step checkpoints; direct changes include their
regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Decision gates

- [The operator-workflow arc](backlog-arc-operator-workflow.md) selection
  step 4 parks T5 documentation/export/cosmetic candidates "behind a concrete user
  workflow" — a surface is ready when it has a named reader, a named action,
  and a way to tell the action improved. Do not treat tier membership alone
  as readiness.
- **#79 carries a warning**: four of its five original "duplicated helper"
  claims were wrong in the direction that breaks things once machine-checked
  (see `BACKLOG.md` § "How this squares with `tests/test_duplication.py`").
  Re-verify every claim in #79–#81 before any merge; do not act on the
  original list's wording.

## Ordered route

1. **#308** — user-confirmed retirement of legacy Jira-grade detail artifacts
   and readers. Keep the run-grade implementation-detail export to concise
   Jira stories plus its paired developer handoff; do not preserve a second
   detail lane as compatibility.
2. **#107** — deferred pending a demonstrated export blocker.
3. **#49**, **#102**, **#43**, **#54**, **#55**, **#56** — read each item's
   full `BACKLOG.md` entry before acting.
4. **#36** — theoretical; investigation may close with "no action."
5. **#89** — commit-hygiene coverage (extend `--commit` to more mutating
   commands). Observed orphaning gap on `reconcile-code`; see the entry's
   "Evidence it recurs" bullet in `BACKLOG.md`.
6. **#79–#81** — the Bucket D consolidation cluster. See the decision gate
   above before touching #79's claims specifically.
7. **#366** — theoretical; survey `aidlc-workflows`'s multi-harness patterns
   (core/adapter split, provider-agnostic tier aliasing, build-determinism
   guard) for plan-tool applicability. Read-only against both repos; may
   close with "no action" per its own Output-of-investigation gate. No
   dependency on the items above — pick it independently of the rest of
   this route.

## Exit and handoff

This is the last tier. There is no next tier to hand off to — once T5 is
clear, return to `BACKLOG.md`'s Now/Next/Blocked/Parked board for the
current session pick, or `backlog-arc-tier-t1.md` to re-check
whether new T1 work has surfaced since the last full pass.

## Out of scope

This file does not carry any of its items' implementation content — read
each one's full `BACKLOG.md` entry before acting. It does not relax the
decision gate above merely because an item is tier-listed.
