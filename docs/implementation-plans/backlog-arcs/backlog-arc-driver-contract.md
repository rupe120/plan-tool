# Driver-contract backlog arc

## File intent

This file is the execution guide for what an unattended driver can read from
`plan-tool` without inferring it: the result of `create` and `detail`, a
refused `create`'s reason, a plan's gate verdict, each finding's triage label, and a
run's usage totals. It routes #499 and #502, filed
2026-10-19 from the design of Integration's Construction batch driver. `BACKLOG.md`
owns each item; this file owns only their working order. The two items are
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

- **#499** — the audit's own detail-level (D) label per bare-stage finding,
  built only after a label-agreement measurement; it lands with #192's
  finding-record version bump.
- **#502** — a stable stderr reason token for a `create` refused before its slug resolves.

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

1. **#499** is `decision-needed`. Settle who owns the D label and measure
   its pass-to-pass agreement before building.
2. **#502** is `ready`: print the closed reason token on each pre-slug refusal.

## Decision gates

- **Every item exposes state a machine can already observe.** None judges the
  quality of a finding or flips an exit code (`CLAUDE.md` § "Validating a
  semantic property you cannot observe"). A label (#499) is recorded, never
  gated on.
- **One definition of "converged".** `gate-status` reuses the existing audit
  `--json` field definitions; it never defines a second one.
- **Persisted fields need `architect`-tier review**: #499's sidecar version bump changes `DATA_CONTRACT.md`.

## Exit and handoff

The arc is done when each item is shipped, closed as already handled, or closed
by its recorded decision. A new driver-facing gap is filed against this arc
rather than opening another.

## Out of scope

Running or scheduling plans in dependency order, a roadmap status projection,
reading a subscription's remaining allowance, and any gate on a semantic
property.
