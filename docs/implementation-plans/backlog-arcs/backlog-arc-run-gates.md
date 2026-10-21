# Run-gate backlog arc

## File intent

This file is the execution guide for what happens around a `plan-tool run`
step's gates: what the model is told before it finishes, what the retry sees
after a gate fails, which outcome a failed step reports, and what the
test-authoring and suite gates observe. It routes #454, #455, and #457
through #459, filed 2026-10-06 from one plan's run (`roadmap-versioned-from-birth`,
12 steps, seven of them halting at least once). `BACKLOG.md` owns each item;
this file owns only their working order. The five items are untiered in the
priority (mission-grounded) sense — this arc is their sole router. #463
(`run --step N --accept`) shipped 2026-10-10 and #456 (the "no edits applied"
outcome and failure receipt) shipped 2026-10-13; both left this arc.

Adjacent items that stay routed elsewhere and are not owned here: #87 (the
test-authoring gate's baseline; it also records the two causes seen in this
run), #88 (memoizing a `run` step's `claude` call), #108 (durable per-step
run marker), and #488 (routing a failed step's receipt to roadmap feedback,
routed by `backlog-arc-roadmap`).

## Details

- **#454** — run prompt: run the touched tests, check remaining uses of every
  deleted or renamed symbol, sweep tests and docs that pin the old behavior.
- **#455** — the retry gets the complete failure list; decide whether a failed
  gate gets one bounded in-run repair attempt.
- **#457** — re-run only the failed tests once before the suite gate fails the
  step.
- **#458** — advisory list of detail-named test identifiers no test file contains.
- **#459** — decide what `reconcile-code --no-walk` promises.

These items were collected without reading `launcher.py` or `run_log.py`;
each entry's first step is to read the code and may close it as already handled.

## Choose this arc when

A session is already committed to changing how `run` steps are prompted, gated,
retried, or reported — not merely because a gate misbehaved during other work
(file that as an out-of-scope finding instead). Do not choose it for the
test-authoring gate's dirty-baseline problem (#87) or call memoization (#88).

## Delivery cadence

Commit each resolved item before starting the next one. Direct changes include
their regression coverage and backlog retirement in one bounded commit. Do not
push automatically; push only when the user explicitly requests it.

## Ordered route

1. **#454.** `ready`, `direct`, and independent: a prompt change.
2. **#455 (a), then its decision (b).** The failure-list change is `direct`; the
   repair-attempt decision follows #88's memoization so a repair does not re-spend
   a successful call.
3. **#459** — a decision on its own; independent of the rest.
4. **#457 and #458 wait on their gates** (a second non-reproducing gate failure;
   a measured false-positive rate). Do not build either before its evidence exists.

## Decision gates

- **Every item is a prompt change, an outcome name, a log field, or a retry rule.**
  None adds a gate on semantic quality or an exit-code flip (`CLAUDE.md` §
  "Validating a semantic property you cannot observe"). The one carve is #457's
  re-run, which still fails a test that fails twice.
- **#458 follows "a high false-positive rate means kill, not tune".**
- **No unattended retry loop without a bound** (#455).

## Exit and handoff

The arc is done when each item is shipped, closed as already handled, or closed
by its recorded decision. A new gap of the same theme is filed against this arc
rather than opening another.

## Out of scope

Changing which checks the suite gate runs, the plan format, `detail` or `create`,
the `--commit` mandate, or any parallel execution of steps.
