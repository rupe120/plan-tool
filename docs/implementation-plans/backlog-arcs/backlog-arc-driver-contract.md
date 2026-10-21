# Driver-contract backlog arc

## File intent

This file is the execution guide for what an unattended driver can read from
`plan-tool` without inferring it: the result of `create` and `detail`, a
refused `create`, a plan's gate verdict, each finding's triage label, and a
run's usage totals. It routes #499, #502, and #506, filed
2026-10-19 from the design of Integration's Construction batch driver. `BACKLOG.md`
owns each item; this file owns only their working order. The three items are
untiered in the priority (mission-grounded) sense — this arc is their sole
router. #501 (`run_end.result` for `create` and `detail`), #505 (`run_end.usage`
totals), and #500 (`gate-status`) shipped 2026-10-19 and left this arc.

Adjacent items that stay routed elsewhere and are not owned here: #504 (plan
level dependencies; routed by `backlog-arc-roadmap`), #385 (a roadmap status
projection; routed by `backlog-arc-roadmap`), #495 (default audit pass count;
it reads the same per-call events that `run_end.usage` totals), and the `BUG_BACKLOG.md` entries
on `source_seed` after archiving, on the unbuilt-sibling plan shape, and on a
path a sibling roadmap plan creates.

## Details

- **#499** — the audit's own altitude label and carried-to-detail flag per
  finding; the first slice covers D only.
- **#502** — a record for a `create` refused before its slug resolves.
- **#506** — an optional total budget across an audit loop; builds on the shipped `run_end.usage` totals.

## Choose this arc when

A session is already committed to making plan-tool's state machine-readable
for an external driver. Do not choose it because a driver misbehaved during
other work (file that as an out-of-scope finding), and do not choose it for
roadmap status (#385) or plan dependencies (#504).

## Delivery cadence

Commit each resolved item before starting the next one. Direct changes include
their regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **#499 and #502** are `decision-needed`. Settle who owns the altitude label
   (#499) and where a pre-slug refusal records itself (#502) before building.
2. **#506** waits on its own decision on unit and persistence.

## Decision gates

- **Every item exposes state a machine can already observe.** None judges the
  quality of a finding or flips an exit code (`CLAUDE.md` § "Validating a
  semantic property you cannot observe"). A label (#499) is recorded, never
  gated on.
- **One definition of "converged".** `gate-status` reuses the existing audit
  `--json` field definitions; it never defines a second one.
- **Persisted fields need `architect`-tier review**: #502 and #506 change `DATA_CONTRACT.md`.

## Exit and handoff

The arc is done when each item is shipped, closed as already handled, or closed
by its recorded decision. A new driver-facing gap is filed against this arc
rather than opening another. Integration's findings ledger
(`backlog-arc-integration-mvp.md`) points here for these items and owns none of them.

## Out of scope

Running or scheduling plans in dependency order, a roadmap status projection,
reading a subscription's remaining allowance, and any gate on a semantic
property.
