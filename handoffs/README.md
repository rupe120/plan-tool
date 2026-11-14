# Handoffs and review ledgers

This directory carries handoffs and review ledgers. Start with `BACKLOG.md`'s
working board; a handoff records a route and its fence, not a queue override.

## Policy: temporary, and cited only here

Handoffs and review ledgers are temporary working records. This README is the only
document that refers to them, and other documents (`CLAUDE.md`, the how-to guides, the
backlog, plans, evidence) point at this README, never at an individual file. Anything
durable (a design, a procedure, a decision, a measurement) lives in `docs/`, a plan, or
a backlog entry, and is moved there before its handoff is retired. A handoff can then be
renamed, merged or deleted without sweeping references.

Frozen files (archived plans, plan details, saved reports, seeds, `docs/evidence/*.json`
receipts, experiment data) pin their text and can still contain paths to handoffs that no
longer exist. They are not edited, and a dead path there is expected.

## Naming

A handoff or ledger file is a **workstream**: a long-lived area of work, named in a few
lowercase words (for example `tracking-and-jira`), not one change and not a date. A change
joins the workstream it belongs to as a new section; a new file needs a new workstream.
The workstream names are the list under § "Workstreams".

- **One workstream, one file.** New work appends a `## <change>` section with an
  `*Opened YYYY-MM-DD.*` line and its own summary table. Do not add a `-round2`, a date,
  or a per-change file. This keeps related work, its decisions and its review findings in
  one place, so prior work is found before it is repeated.
- **A file is never split by change.** If a workstream grows too large to read, compress
  its closed sections (§ "Retention"); do not branch it into per-change files.
- **A new workstream is a deliberate act.** Add it only when no listed workstream fits,
  name it for the area, and add its entry under § "Workstreams" in the same commit.
- **The date lives in the section**, not the filename. `git log --follow <file>` gives a
  file's history.

## Review ledgers

A review ledger section records how one bounded change is judged while it is in review: local
code review, pull-request review, and the decisions a later reviewer needs. Keep
one ledger section per change inside its workstream file (see § "Naming"). A handoff records what a future session
does next; a ledger records how the current change was judged. A file may do
both jobs when the same change is still in flight.

Put a small summary table at the top of the section: the date opened (an `Opened` row), the review range, the current head, the
checks run, the reviewer or review session, and the current disposition. Give
the reviewer the settled decisions before each pass. Then record every
substantive finding, including pull-request comments, with one disposition:

- `fixed <commit>`
- `refuted <evidence>`
- `declined <reason>`
- `tracked <backlog id>`
- `pending`

A pull-request thread may link to the ledger, but it is not the ledger: a future session
needs the finding, its evidence, and its disposition without searching a remote review
UI. A `fixed <commit>` disposition also states the corrected behavior and the
evidence for the fix. Update the ledger when a PR comment changes the
branch, and hand the updated settled-decision list to the next reviewer.

## Retention

- A **handoff or workstream section** is deleted, not archived in place, when its work ships or its
  route is retired; anything durable moves to its canonical home first
  (`BACKLOG.md`, a plan, `docs/evidence/`). Keep the decisions and evidence needed to continue the work in their canonical documents.
- A **review ledger** is compressed when its loop closes: keep the summary
  table, settled decisions, one line per finding with a disposition from the
  closed set above, the closure paragraph, and every `tracked`/`pending` item.
  The compressed file keeps the evidence and reasoning needed to understand each decision. Do not remove the sole explanation of a finding or its disposition.
- A ledger records **how** it closed: converged (two consecutive low-yield
  passes), stopped by the owner, closed by owner decision, or stopped at exit 2
  (the loop was auditing its own edits, so it is neither converged nor clean;
  `CLAUDE.md` § "Driving the convergence loops"). The four are not
  interchangeable, and a compressed ledger keeps its own label; rows closed
  before this rule keep the label they carry.
- Every file in this directory except `README.md` appears in § "Workstreams" below. Check
  with `cd handoffs && for f in *.md; do [ $f = README.md ] || grep -qF "]($f)" README.md || echo "NOT INDEXED: $f"; done`;
  empty output means every file is indexed.

## Release preparation

Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for content decisions, reference ownership and retained conclusions. Use the
[verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
for exact candidate identity, environment and measured results.
[`docs/RELEASING.md`](../docs/RELEASING.md) owns the release procedure; the
[public-release arc](../docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md)
with `BACKLOG.md` #514, #515 and #523 owns the remaining distribution work and the next action.
Keep decisions and finding explanations in their maintained owners when
compressing or retiring a handoff.

## Workstreams

| File | Scope |
| --- | --- |
| [run-and-completeness.md](run-and-completeness.md) | `run` gates and receipts, completeness next steps and verdicts, loop behavior, hints and maintenance fixes. |
| [tracking-and-jira.md](tracking-and-jira.md) | Work tracking, the Jira board and tickets, backlog guards, branch hygiene and settled tracking decisions. |
| [handoff-directory.md](handoff-directory.md) | This directory's own upkeep: scope fence, owner decisions, open items. |
| [bug-backlog-drain.md](bug-backlog-drain.md) | Standing procedure, queue order, stop conditions and session log for draining `BUG_BACKLOG.md`. Kept as its own file because sessions append to its log; not a merge candidate. |

Each file opens with a table of its sections, with the date each was opened. Parked backlog routes carry their pickup and fence in `BACKLOG.md` and its arc documents, not here.
