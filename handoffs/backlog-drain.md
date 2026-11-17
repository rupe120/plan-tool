# Backlog drain: standing pickup

Use this handoff to take `BACKLOG.md` entries one at a time. It records the
procedure and its fence, not a queue: `BACKLOG.md`'s Now board, priority bands
and arc documents own what competes for the next session, and
[`docs/TRACKING.md`](../docs/TRACKING.md) owns the labels, the pick order and
promotion. Delete this file when the drain route is retired; per
[`README.md`](README.md) § Retention, anything durable moves to its canonical
home first.

| Section | Opened |
| --- | --- |
| [Queue order](#queue-order) | 2026-11-16 |
| [Per-entry procedure](#per-entry-procedure) | 2026-11-16 |
| [Stop conditions](#stop-conditions) | 2026-11-16 |
| [Session log](#session-log) | 2026-11-16 |

## Queue order

1. **`BUG_BACKLOG.md` first.** While it holds an unpromoted, unblocked `BUG`
   outside `ROADMAP`, drain it through
   [`bug-backlog-drain.md`](bug-backlog-drain.md) instead (`BACKLOG.md` §
   "Priority": `BUG_BACKLOG.md` leads the execution order).
2. **An active arc or a Now-board pick outranks everything below.** Read the
   Now / Next / Blocked / Parked board and § "Execution-routing arcs" in
   `BACKLOG.md`. If the board's "checked" date is stale against the tree,
   surface that to the user rather than re-ranking it here.
3. **Otherwise use `docs/TRACKING.md` § "Choosing what to promote next",
   row 2:** Readiness `ready`, ordered by Principle (P1 first, `none` last),
   then by bucket (A and B before D and E).
4. **Skip:** promotion stubs (`→ promoted to IPPT-…`; the Jira ticket holds
   the brief), roadmap-owned entries (`backlog-arc-roadmap.md` routes and any
   entry whose Arc assignment names it), and every Readiness other than
   `ready` (`decision-needed`, `evidence-gated`, `blocked-on #N`, `parked`).
   A parked entry moves only through its `Unpark when:` line.
5. **Take an entry only when its Route is `direct`.** Surface a `Route: plan`
   entry to the user (it goes through `plan-tool create` from a seed that
   inherits the entry's scope contract) instead of picking it up.
6. **An entry with `Principle untriaged`, or no labels:** judge and write the
   missing labels when you touch it (TRACKING § "Labels every entry
   carries"), then place it by the result. Do not bulk-label untouched
   entries.
7. **Jira promotion and ordering across the two backlog files are the
   lead's call.** This handoff takes unpromoted entries directly, under
   TRACKING § "Promotion stubs" ("Unpromoted items keep the entry rule").

## Per-entry procedure

1. **Verify the entry against the tree before editing.** An entry can
   already be shipped, stale, or wrong about the code. A claim about the code
   is checked against the code and the covering tests; a stale entry is
   corrected or retired (with its re-open condition in
   [`docs/history/backlog-decisions.md`](../docs/history/backlog-decisions.md)),
   not implemented.
2. **Search for overlap.** Grep `BACKLOG.md` and `BUG_BACKLOG.md` for the
   entry's identifiers and vocabulary; a duplicate is folded into the entry
   that is cited elsewhere, not worked twice.
3. **Hold the scope contract.** Outcome, In scope, Out of scope, Allowed
   behavior changes and Stop / defer bound the change. A finding outside them
   becomes a new entry, not part of this one.
4. **Name the class and enumerate its sites** by identifier and by vocabulary
   before editing any of them; apply at every site, or say per site why it
   stays.
5. **State the property the change must produce,** trace the mechanic against
   the common input, and make the smallest change that delivers it.
6. **Add coverage that fails under the prior behavior,** named for the
   invariant it pins, and verify by mutation.
7. **Run focused tests, then the full suite**
   (`uv run pytest tests/ -q -n auto`, in the background with a named log under
   `.tmp/`, prefixed `set -o pipefail &&` when piped).
8. **Commit, then run `/code-review` at `high`,** and stop under `CLAUDE.md` §
   "Severity-aware conceptual-audit stopping rule" or one of its three exits.
   Record each finding with a disposition from the closed set in
   `README.md` § "Review ledgers".
9. **Remove the shipped entry** and any reference that cites it as open, and
   refresh the Now board when the change ships a board item.
10. **Commit one bounded concern per commit,** on a branch, never on `main`.
    Pushing or opening a pull request needs a separate go-ahead.

## Stop conditions

- The same finding resurfaces across review rounds, or a fix needs structural
  rework that cannot land inline: stop and surface it to the user, or file it.
- The entry's scope contract cannot hold the change: stop and surface it; do
  not widen the contract on your own.
- A scope or design decision appears, or the entry's premise looks false:
  surface it to the user rather than self-adjudicating.

## Session log

Record each taken entry as one dated line: entry id and title, disposition
(`fixed <commit>`, `refuted <evidence>`, `declined <reason>`,
`tracked <backlog id>`, or `pending`), and the commit that removed the entry.
Drop a `fixed` line once its change has merged to `main`, and a `refuted`,
`declined`, or `tracked` line once its evidence lives in `BACKLOG.md`,
`BUG_BACKLOG.md`, or `docs/history/backlog-decisions.md`; keep `pending` lines
until they resolve.

- 2026-11-17 — Principle triage of the twelve Readiness `ready`, Route `plan`
  entries with Principle `untriaged` (#89, #142, #149, #156, #180, #198, #202,
  #230, #312, #332, #377, #385): `fixed da81abc64`. An owner-directed batch,
  a one-time exception to Queue order step 6 and `docs/TRACKING.md`'s
  label-on-touch rule; the rule stands. `pending`: #149's `ready` label
  disagrees with the board's Blocked lane for its plan.

## Deliberately not in this handoff

- A snapshot or ranking of the queue: the Now board and TRACKING own it, and a
  copy here goes stale on the next drain.
- Roadmap-owned entries and Jira promotion: the owner and the lead own them.
- Driving `plan`-route entries: they go through `plan-tool` and its own gates.
- New concurrency or parallel fan-out to speed the drain: the tool is serial by
  design.
