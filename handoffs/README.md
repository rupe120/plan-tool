# Handoffs and review ledgers

This directory carries handoffs and review ledgers. Start with `BACKLOG.md`'s
working board; a handoff records a route and its fence, not a queue override.

## Review ledgers

A review ledger is the durable record for one bounded change: local code
review, pull-request review, and the decisions a later reviewer needs. Keep
one tracked ledger per change, normally named
`YYYY-MM-DD-<change>-code-review.md`. A handoff records what a future session
does next; a ledger records how the current change was judged. A file may do
both jobs when the same change is still in flight.

Put a small summary table at the top: the review range, the current head, the
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

- A **handoff** is deleted, not archived in place, when its work ships or its
  route is retired; anything durable moves to its canonical home first
  (`BACKLOG.md`, a plan, `docs/evidence/`). Keep the decisions and evidence needed to continue the work in their canonical documents.
- A **review ledger** is compressed when its loop closes: keep the summary
  table, settled decisions, one line per finding with a disposition from the
  closed set above, the closure paragraph, and every `tracked`/`pending` item.
  The compressed file keeps the evidence and reasoning needed to understand each decision. Do not remove the sole explanation of a finding or its disposition.
- A ledger records **how** it closed: converged (two consecutive low-yield
  passes), stopped by the owner, or closed by owner decision. The three are not
  interchangeable, and a compressed ledger keeps its own label.
- Every file in this directory except `README.md` appears below.

## Release preparation

Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for content decisions, reference ownership and retained conclusions. Use the
[verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
for exact candidate identity, environment and measured results. The
[release pickup](2026-10-19-public-onboarding-and-release.md) owns the next action.
Keep decisions and finding explanations in their maintained owners when
compressing or retiring a handoff.

## Live handoffs

- [Skill-router recipe repair review](2026-10-21-skill-router-recipes-code-review.md) — router instruction fixes, parser/installer evidence and review dispositions.

- [Skill-led demo conversion review](2026-10-21-skill-led-demo-examples-code-review.md) — completed execution, live rehearsal, two independent review verdicts and the separately tracked skill issue.

- [Demo and example refresh](2026-10-21-demo-refresh.md) — skill-driven pickup,
  current demo placement, earlier task-list preparation and verification/publication boundaries.

Each records a next action or an open decision. Parked backlog routes (#216,
#242, #322, #355, #359, #361) carry their pickup and fence in `BACKLOG.md` and
its arc documents, not here; the successor-slug rule lives in
`docs/how-to/roadmap.md`.

### Roadmap and AI-DLC integration

- [Sibling planned Input paths](2026-10-15-sibling-planned-input-paths.md) — repair delivery and the paused isolated Integration regeneration test.
- [Sibling planned Input paths review](2026-10-15-sibling-planned-input-paths-code-review.md) — reconciliation and independent code-review dispositions.
- [Roadmap plan handoff investigation](2026-10-15-roadmap-plan-handoff-investigation.md) — #492 delivery, audit/review evidence and pending delivery-PR publication.
- [Integration full-Ideation roadmap intake review](2026-09-11-integration-ideation-roadmap-intake-review.md)
  — the review question, criteria, and execution fence for whether roadmap's
  single-brief intake makes adequate use of the first complete AI-DLC
  Ideation corpus.
- [Roadmap fit to the AI-DLC workflow framework](2026-09-11-roadmap-aidlc-inception-fit.md)
  — approach-level design for `roadmap` as an Inception implementation, with
  its settled decisions and the open design choices; the owner of that list.
- [Integration seam resume order](2026-09-11-integration-seam-resume-order.md) — where the
  Ideation-to-roadmap seam work stands across Integration and `plan-tool`; the entry
  point for the next session on this seam.
- [Roadmap AI-DLC integration delivery](2026-09-14-roadmap-aidlc-integration-delivery.md)
  — the delivery record: what shipped (#367, #384), the seam contract, and the
  selection conditions for the held capabilities (#383, #385).
- [Roadmap feedback revision and structural approval](2026-09-22-roadmap-feedback-revision-approval.md)
  — the order and completion record of the two plans behind #423.
- [Roadmap candidate vocabulary retry](2026-09-25-roadmap-candidate-vocabulary-retry.md)
  — plan review pickup for IPPT-10: the plan pull request and architect review
  before `run`.

### Developer docs, tracking, Jira, and cleanup

- [Public-release content snapshot plan review](2026-10-20-public-release-content-snapshot-plan-review.md)
  — six-step plan, audit evidence, known PDF advisory and implementation boundary.

- [Public-release prerequisite cleanup review](2026-10-20-public-release-cleanup-review.md)
  — cleanup-only review range, settled decisions and separate plan/publication boundaries.

- [Public onboarding and release](2026-10-19-public-onboarding-and-release.md)
  — approved scope, #508–#515 routing, sanitization-first pickup and open
  publication decisions.

- [Developer docs and work tracking](2026-09-14-developer-docs-and-tracking.md)
  — the docs restructure for a team of developers: what's settled, the owner's
  open decisions, and the next bounded actions.
- [Documentation readability and onboarding](2026-09-15-documentation-readability-and-onboarding.md)
  — a reader-journey-led review of the live developer docs, its directive and
  style-guide boundary, pilot, fact fences, and validation route.
- [Team handoff: tracking-model decisions and remaining work](2026-09-17-team-handoff-open-decisions-proposal.md)
  — the settled decisions (tracking model, remote of record, review tail
  rules, persona tiers, promotion stubs, roadmap boundary, release process,
  Jira board, `--version`), where each is recorded, and the work still open.
- [Jira project setup and management](2026-09-23-jira-management.md) — the
  live `IPPT` state against the lean board, the ticket promotion procedure,
  and the recurring management loop.
- [First Jira tickets and the `run` merge guard](2026-09-24-first-jira-tickets-and-run-merge-guard.md)
  — the seven live `IPPT` tickets, the short ticket format and tier rules, the
  owner decisions still open, and the next steps.
- [General documentation cleanup](2026-09-23-doc-cleanup.md) — queued doc
  hygiene: the broken-link scan (`BACKLOG.md` #426), an undecided link-check
  test, the Jira board's remaining setup, and the `CLAUDE.md` evidence
  extraction. Distinct from the branch and handoff cleanups below, which
  each cover one kind of artifact.
- [General branch cleanup](2026-09-29-branch-cleanup.md) — the local and
  `origin` branch inventory: what is merged and safe to delete, what is active,
  and the ancient remote-only branches.
- [Handoff-directory cleanup and consolidation](2026-09-29-handoff-consolidation.md)
  — this directory's own queued cleanup, with the compression record.

## Review ledgers

Closure labels follow § "Retention". Compressed 2026-09-29 unless noted.

| Ledger | Closed | Backlog references |
| --- | --- | --- |
| [`BACKLOG.md` id guard](2026-09-23-backlog-id-guard-code-review.md) | All in-diff findings fixed or declined | Finding E, the wider broken-link count (#426); not compressed |
| [Roadmap brief-source drift](2026-09-12-roadmap-brief-source-drift-code-review.md) | Converged 2026-09-14 (10 rounds, 55 findings) | `BUG_BACKLOG.md` external-replacement risk (F26); closed route-local record and #367 |
| [Roadmap concept comparison](2026-09-21-roadmap-concept-comparison-code-review.md) | **Stopped by the owner** 2026-09-21, 11 rounds | #406–#422 |
| [Unpushed `main`](2026-09-21-unpushed-main-code-review.md) | Converged after 4 rounds | R2-1 tracked in `BUG_BACKLOG.md`; R4-8 `pending` (unfiled) |
| [Roadmap model-failure receipts](2026-09-22-roadmap-model-failure-receipts-code-review.md) | Converged, loop stopped | One `BUG_BACKLOG.md` entry |
| [Versioned feedback revision chain](2026-09-23-roadmap-versioned-feedback-revision-chain-code-review.md) | Converged, low-yield | #395, #427–#429 and `BUG_BACKLOG.md` |
| [Structural feedback approval](2026-09-23-roadmap-structural-feedback-approval-code-review.md) | **Closed by owner decision** 2026-09-24 | Owner direction: run-log coverage for approve, reject, discard, promote, tracked as #434; cites #423, #429, #430 |
| [Stack-aware approval](2026-09-24-roadmap-stack-aware-approval-code-review.md) | Converged 2026-09-25 | Cites #428, #429, #431 and `BUG_BACKLOG.md` |
| [Detail deferrals-envelope repair](2026-09-25-detail-deferrals-envelope-repair-code-review.md) | Converged 2026-09-25 | Source `BUG_BACKLOG.md` entry removed at `8491289f` |
| [Candidate envelope diagnostics](2026-09-26-roadmap-candidate-envelope-diagnostics-code-review.md) | Converged, low-yield, 2026-09-27 | `BUG_BACKLOG.md` entry for P1.3/P2.2 |
| [Candidate anchor/gate correction](2026-09-27-candidate-anchor-gate-correction-code-review.md) | Converged, low-yield, after 8 passes | #431, #432 |
| [Roadmap stack propagation](2026-10-08-roadmap-stack-propagation-code-review.md) | Converged 2026-10-08, four passes (3 and 4 consecutive and clean) | #463, #464, one `BUG_BACKLOG.md` entry; its pickup section lists the next session's work (the audit replay, #461's last audit, the directives branch's pull request) |

## Known dangling citations

Two citations in `docs/implementation-plans/2-roadmap-source-baseline-recovery.md`
(lines 67 and 104) name `handoffs/2026-08-27-integration-roadmap-evidence-preflight.md`,
which no longer exists. The plan is deferred and its saved reports pin its text,
so the citations stay. Use the retained summary in
[the roadmap arc](../docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md) (the #242
"Paused" entry). Three frozen archive files (`docs/implementation-plans/archive/2-authored-artifact-format-version.md` and its step-7 detail) and the id-guard ledger cite the old `handoffs/` path of the authored-artifact record, now [the authored-artifact evidence](../docs/evidence/authored-artifact-structure-versioning.md); use that retained replacement while frozen citations stay as written. Citations of `handoffs/2026-09-08-aidlc-authoring-route.md` in
`backlog-arc-integration-mvp.md` name Integration's own handoff, not a file in this repository. Use Integration's owning repository when continuing that work. The [selection record](../docs/evidence/public-release-content-snapshot.md) summarizes the decisions relevant to this repository.

## 2026-09-08 consolidation record

The following completed records are retired without a replacement: reused audit
coverage verdict, checkpoint identity, reconcile-plan-walk checkpoint role,
escalation receipt persistence, roadmap impact-store nodes, and the converged
`literal_path` review. Their evidence remains in canonical plans, backlog
entries, tests, and Git history.

The remaining records consolidate by current route: the human-input and two
headless-review proofs feed #322; the Integration preflight feeds #242; the quality
proof feeds #216; the candidate-context review feeds #355; the completed
`literal_path` review feeds #359; and roadmap lineage remains a separate
future tool-decision route (its successor-slug rule moved to
`docs/how-to/roadmap.md` on 2026-09-29).

- [Public-release reference-repair correction review](2026-10-20-public-release-reference-repair-review.md) — bounded plan correction, audit qualification and execution recovery.

- [Public-release snapshot execution review](2026-10-20-public-release-content-snapshot-execution-review.md) — six-step local result, two clean review passes and remaining #513 limits.
