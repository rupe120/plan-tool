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

A new handoff or ledger is named for its concept, not its date:
`<concept>.md` for a handoff and `<concept>-code-review.md` for a ledger. The
concept is the change or route in a few lowercase words
(`roadmap-feedback-revision`, not `notes` or `handoff`).

- **The date lives in the file, not the name.** The summary table carries an
  `Opened` row (and the closure paragraph carries its closure date); `git log`
  holds the rest.
- **One concept, one file.** A second record for a concept already here is an
  update to that file. If the work is genuinely separate, name the narrower
  concept instead of adding a suffix or a date.
- **Dated prefixes were dropped 2026-11-13.** `git log --follow <file>` gives a file's
  history and its original date.

## Review ledgers

A review ledger records how one bounded change is judged while it is in review: local
code review, pull-request review, and the decisions a later reviewer needs. Keep
one tracked ledger per change, named
`<concept>-code-review.md` (see § "Naming"). A handoff records what a future session
does next; a ledger records how the current change was judged. A file may do
both jobs when the same change is still in flight.

Put a small summary table at the top: the date opened (an `Opened` row), the review range, the current head, the
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
  passes), stopped by the owner, closed by owner decision, or stopped at exit 2
  (the loop was auditing its own edits, so it is neither converged nor clean;
  `CLAUDE.md` § "Driving the convergence loops"). The four are not
  interchangeable, and a compressed ledger keeps its own label; rows closed
  before this rule keep the label they carry.
- Every file in this directory except `README.md` is linked from at least one section
  below, and every link resolves. Check with
  `for f in *.md; do [ $f = README.md ] || grep -qF "]($f)" README.md || echo "NOT INDEXED: $f"; done; grep -oE '\]\(([^)#]+\.md)' README.md | sed 's/](//' | sort -u | while read l; do [ -e "$l" ] || echo "DEAD: $l"; done`;
  empty output means both hold. Run it from `handoffs/`. It does not count sections: a link anywhere in this
  file counts as indexed, so check that each
  file also has its own entry in a list or table. A section that routes to a file
  listed in another section (the release pickup) may link it twice.

## Release preparation

Use the [selection record](../docs/evidence/public-release-content-snapshot.md)
for content decisions, reference ownership and retained conclusions. Use the
[verification receipt](../docs/evidence/public-release-content-snapshot-verification-20261020.md)
for exact candidate identity, environment and measured results. The
[release pickup](public-onboarding-and-release.md) owns the next action.
Keep decisions and finding explanations in their maintained owners when
compressing or retiring a handoff.

## Live handoffs

- [Bug backlog drain](bug-backlog-drain.md) — standing procedure, queue order, stop conditions, and session log for draining `BUG_BACKLOG.md`.

- [Overengineering checkpoints](overengineering-checkpoints.md) — merged checkpoints, instruction refresh after project model selection, behavioral-test limits, and observation on the next real task.

- [Project model selection plan review](project-model-selection-code-review.md) — audited project backend/model defaults plan, proportionality correction, and separate copied-skill backlog item.

- [Jira-grade retirement execution and review](jira-grade-retirement-plan.md) — eight
  completed steps, reconciliation findings and corrections, model provenance,
  two clean independent reviews, and prepared publication branches.

- [Skill-router recipe repair review](skill-router-recipes-code-review.md) — router instruction fixes, parser/installer evidence and review dispositions.

- [Skill-led demo conversion review](skill-led-demo-examples-code-review.md) — completed execution, live rehearsal, two independent review verdicts and the separately tracked skill issue.

- [Demo and example refresh](demo-refresh.md) — skill-driven pickup,
  current demo placement, earlier task-list preparation and verification/publication boundaries.

Each records a next action or an open decision, or is a completed pickup kept until its retirement is decided (its entry says so). Parked backlog routes (#216,
#242, #322, #355, #359, #361) carry their pickup and fence in `BACKLOG.md` and
its arc documents, not here; the successor-slug rule lives in
`docs/how-to/roadmap.md`.

### Roadmap and AI-DLC integration

- [Sibling planned Input paths](sibling-planned-input-paths.md) — repair delivery and the paused isolated Integration regeneration test.
- [Sibling planned Input paths review](sibling-planned-input-paths-code-review.md) — reconciliation and independent code-review dispositions.
- [Roadmap plan handoff investigation](roadmap-plan-handoff-investigation.md) — #492 delivery, audit/review evidence and pending delivery-PR publication.
- [Integration full-Ideation roadmap intake review](integration-ideation-roadmap-intake-review.md)
  — the review question, criteria, and execution fence for whether roadmap's
  single-brief intake makes adequate use of the first complete AI-DLC
  Ideation corpus.
- [Integration seam resume order](integration-seam-resume-order.md) — where the
  Ideation-to-roadmap seam work stands across Integration and `plan-tool`; the entry
  point for the next session on this seam.
- [Roadmap AI-DLC integration delivery](roadmap-aidlc-integration-delivery.md)
  — the delivery record: what shipped (#367, #384), the seam contract, and the
  selection conditions for the held capabilities (#383, #385).
- [Roadmap feedback revision and structural approval](roadmap-feedback-revision-approval.md)
  — the order and completion record of the two plans behind #423.
- [Roadmap candidate vocabulary retry](roadmap-candidate-vocabulary-retry.md)
  — plan review pickup for IPPT-10: the plan pull request and architect review
  before `run`.

- [Sanitized release publication](sanitized-publication.md) — completed 2026-10-21 publication record; kept because the release pickup and the demo refresh cite it as the owner of exact publication identity. Retire with the release cluster.
- [Roadmap base-plan business-logic loop](roadmap-business-logic-base-plan-loop.md) — owner decisions (stop at base plans, business-logic focus, `gpt-6.1-sol`) and the Integration benchmark loop.
- [Roadmap plan derivation implementation](roadmap-plan-derivation-implementation.md) — execution checkpoint and evidence for the derivation plan.

### Token ledger

- [Token-ledger logging recovery](token-ledger-recovery.md) — site decisions and review-converged recovery of prompt identity and call telemetry.

### Developer docs, tracking, Jira, and cleanup

- [Documentation placement review](documentation-placement-review.md) — placement and initial-workflow screen of the how-to pages.
- [Smallest proof first review](smallest-proof-first-review.md) — the owner-requested direct change requiring concrete present need before new machinery.
- [Project model selection implementation](project-model-selection-implementation.md) — four done steps, reconciliation, and the #525 copied-skill follow-up.

- [Public-release content snapshot plan review](public-release-content-snapshot-plan-review.md)
  — six-step plan, audit evidence, known PDF advisory and implementation boundary.

- [Public-release prerequisite cleanup review](public-release-cleanup-review.md)
  — cleanup-only review range, settled decisions and separate plan/publication boundaries.

- [Public onboarding and release](public-onboarding-and-release.md)
  — approved scope, #508–#515 routing, sanitization-first pickup and open
  publication decisions.

- [Developer docs and work tracking](developer-docs-and-tracking.md)
  — the docs restructure for a team of developers: what's settled, the owner's
  open decisions, and the next bounded actions.
- [Documentation readability and onboarding](documentation-readability-and-onboarding.md)
  — a reader-journey-led review of the live developer docs, its directive and
  style-guide boundary, pilot, fact fences, and validation route.
- [Team handoff: tracking-model decisions and remaining work](team-handoff-open-decisions-proposal.md)
  — the settled decisions (tracking model, remote of record, review tail
  rules, persona tiers, promotion stubs, roadmap boundary, release process,
  Jira board, `--version`), where each is recorded, and the work still open.
- [First Jira tickets and the `run` merge guard](first-jira-tickets-and-run-merge-guard.md)
  — the seven live `IPPT` tickets, the short ticket format and tier rules, the
  owner decisions still open, and the next steps.
- [General documentation cleanup](doc-cleanup.md) — queued doc
  hygiene: the broken-link scan (`BACKLOG.md` #426), an undecided link-check
  test, the Jira board's remaining setup, and the `CLAUDE.md` evidence
  extraction. Distinct from the branch and handoff cleanups below, which
  each cover one kind of artifact.
- [General branch cleanup](branch-cleanup.md) — the local and
  `origin` branch inventory: what is merged and safe to delete, what is active,
  and the ancient remote-only branches.
- [Handoff directory cleanup](handoff-directory-cleanup.md)
  — this directory's remaining cleanup, scope fence, and open items.

## Review ledgers

Closure labels follow § "Retention". Every table row states its compression state (`compressed 2026-09-29`, `compressed 2026-11-13` or `not compressed`); bulleted entries below state it or are not compressed.

| Ledger | Closed | Backlog references |
| --- | --- | --- |
| [Loop-termination lists](loop-termination-lists-code-review.md) | **Stopped at exit 2** 2026-11-13 (neither converged nor clean); not compressed | None open; the `no_progress` RUNBOOK troubleshooting entry is a possible later addition, not filed |
| [Iteration-budget hints](iteration-budget-hints-code-review.md) | **Stopped at exit 2** 2026-11-13 (neither converged nor clean); merged through PR #205; not compressed | Two open `BUG_BACKLOG.md` entries: the `--iterate` / `--max-iterations 5` hint residual and the unrendered `WHY["open"]` text |
| [Onboarding guidance entry removal](onboarding-guidance-code-review.md) | **Stopped at exit 2** 2026-11-13 (neither converged nor clean); merged through PR #203; not compressed | One open `BUG_BACKLOG.md` entry (the `BACKLOG.md` recipes); the `RUNBOOK.md` iteration budget entry was fixed in `9f8c67e9b`; #510 owns the first-task path |
| [Detail empty-heading refusal](detail-empty-heading-code-review.md) | Low-yield convergence 2026-11-13 (not a clean audit); merged through PR #202; not compressed | None open; `scope-review` is unguarded by design |
| [Dockerfile mention recognition](files-coherence-dockerfile-code-review.md) | **Stopped at exit 2** 2026-11-13 (neither converged nor clean); merged through PR #201; not compressed | None open; the `_claim_delivered` fuzzy match was declined and the `detail` follow-up shipped in PR #202 |
| [Multiline concept decisions](multiline-concept-decisions-code-review.md) | **Stopped at exit 2** 2026-11-13 (neither converged nor clean); merged through PR #198; not compressed | None open; the repeated-heading and empty-heading follow-ups shipped in PRs #199 and #200 |
| [Row-linked prose amendments](roadmap-candidate-row-prose-amendments-code-review.md) | Converged after pass 5; not compressed | Source `BUG_BACKLOG.md` entry (version comparison omits row-linked prose amendments) |
| [Candidate capsule fixes](candidate-capsule-fixes-code-review.md) | Passes 1–2 triaged; **pass 3 `pending`** (convergence not recorded); not compressed | Two `BUG_BACKLOG.md` entries (capsule Decision-row restore, source-span evidence) |
| [Roadmap versioned-from-birth](roadmap-versioned-from-birth-code-review.md) | **Stopped at exit 2** (loop concluded 2026-10-06 after pass 4; neither converged nor clean); compressed 2026-11-13 | See "Loop conclusion" in the ledger |
| [Roadmap stack layer](roadmap-stack-layer-code-review.md) | Converged (passes 4–5 LOW-only); PR #46; compressed 2026-11-13 | #461 |
| [Prompt-budget model window](prompt-budget-model-window-code-review.md) | Converged 2026-10-09 (passes 6–7 low-yield); compressed 2026-11-13 | #470 |
| [Roadmap context ceiling](roadmap-context-ceiling-code-review.md) | Converged 2026-10-09 (passes 2–3 low-yield); PR #58; compressed 2026-11-13 | #469 (removed on merge) |
| [Completeness next-steps blocking set](completeness-next-steps-blocking-set-code-review.md) | **Closed non-converging by agreement** (four passes); PR #71; not compressed | #479; pass-4 findings tracked as #480 |
| [Completeness next-step verdict finish](completeness-next-step-verdict-finish-code-review.md) | Three rounds; bare-plan audit **stopped at exit 2**; PR #74; not compressed | #480; open remainder routed to #481. Step-4 [reader enumeration](completeness-next-step-verdict-finish-reader-enumeration.md) is its attached deliverable |
| [Tail verdict whose artifacts moved](tail-artifacts-moved-code-review.md) | Two review rounds; not compressed | #481 |
| [`run --accept`](run-accept-code-review.md) | One round plus one delta review; not compressed | #463 |
| [Leftover `0N-*.md` warning](leftover-artifact-warning-code-review.md) | Single review, findings dispositioned; not compressed | `BUG_BACKLOG.md` "bare `0N-*.md` names" part 2 |
| [Multi-line finding bullets](multiline-report-bullets-code-review.md) | Single review, findings dispositioned; not compressed | `BUG_BACKLOG.md` bullet-indent entry |
| [Roadmap seed `## Risks` rule](roadmap-seed-risks-code-review.md) | Single review, findings dispositioned; not compressed | Owner decision 2026-10-10 |
| [Unpublished seed overwrite](seed-overwrite-code-review.md) | Single review, findings dispositioned; not compressed | `BUG_BACKLOG.md` seed-overwrite entry |
| [`run` no-edits-applied block](no-edits-applied-code-review.md) | Converged after 6 rounds; not compressed | #456 |
| [Gate-status review](gate-status-code-review.md) | Converged after two Claude Code passes; not compressed | #500 |
| [Completeness-apply retirement](completeness-apply-retirement-implementation.md) | Low-yield convergence; merged through PRs #162–164; compressed 2026-11-13 | #369, #519, #520 retain their independent owners |
| [Completed maintenance](completed-maintenance-code-review.md) | Converged; merged through PRs #165–167 and #169; not compressed | Deferred stability bugs, nested-function citations, and run-ID collision in `BUG_BACKLOG.md` |
| [`BACKLOG.md` id guard](backlog-id-guard-code-review.md) | All in-diff findings fixed or declined | Finding E, the wider broken-link count (#426); not compressed |
| [Roadmap brief-source drift](roadmap-brief-source-drift-code-review.md) | Converged 2026-09-14 (10 rounds, 55 findings); compressed 2026-09-29 | `BUG_BACKLOG.md` external-replacement risk (F26); closed route-local record and #367 |
| [Roadmap concept comparison](roadmap-concept-comparison-code-review.md) | **Stopped by the owner** 2026-09-21, 11 rounds; compressed 2026-09-29 | #406–#422 |
| [Unpushed `main`](unpushed-main-code-review.md) | Converged after 4 rounds; compressed 2026-09-29 | R2-1 tracked in `BUG_BACKLOG.md`; R4-8 `pending` (unfiled) |
| [Roadmap model-failure receipts](roadmap-model-failure-receipts-code-review.md) | Converged, loop stopped; compressed 2026-09-29 | One `BUG_BACKLOG.md` entry |
| [Versioned feedback revision chain](roadmap-versioned-feedback-revision-chain-code-review.md) | Converged, low-yield; compressed 2026-09-29 | #395, #427–#429 and `BUG_BACKLOG.md` |
| [Structural feedback approval](roadmap-structural-feedback-approval-code-review.md) | **Closed by owner decision** 2026-09-24; compressed 2026-09-29 | Owner direction: run-log coverage for approve, reject, discard, promote, tracked as #434; cites #423, #429, #430 |
| [Stack-aware approval](roadmap-stack-aware-approval-code-review.md) | Converged 2026-09-25; compressed 2026-09-29 | Cites #428, #429, #431 and `BUG_BACKLOG.md` |
| [Detail deferrals-envelope repair](detail-deferrals-envelope-repair-code-review.md) | Converged 2026-09-25; compressed 2026-09-29 | Source `BUG_BACKLOG.md` entry removed at `8491289f` |
| [Candidate envelope diagnostics](roadmap-candidate-envelope-diagnostics-code-review.md) | Converged, low-yield, 2026-09-27; compressed 2026-09-29 | `BUG_BACKLOG.md` entry for P1.3/P2.2 |
| [Candidate anchor/gate correction](candidate-anchor-gate-correction-code-review.md) | Converged, low-yield, after 8 passes; compressed 2026-09-29 | #431, #432 |
| [Roadmap stack propagation](roadmap-stack-propagation-code-review.md) | Converged 2026-10-08, four passes (3 and 4 consecutive and clean); compressed 2026-11-13 | #463, #464, one `BUG_BACKLOG.md` entry; its pickup section lists the next session's work (the audit replay, #461's last audit, the directives branch's pull request) |

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

## Closed ledgers and completed pickups, 2026-10-20 onward

Closure labels are those each file records. None of these is compressed unless its entry says so.

- [Public-release reference-repair correction review](public-release-reference-repair-review.md) — bounded plan correction, audit qualification and execution recovery.

- [Public-release snapshot execution review](public-release-content-snapshot-execution-review.md) — six-step local result, two clean review passes and remaining #513 limits.

- [New-seed default placement](seed-default-location-code-review.md) — nested defaults, retained existing seeds, compatibility tests and Claude review dispositions. Compressed 2026-11-13.
- [Iteration route documentation repair](iteration-guide-routes-code-review.md) — source-backed defaults, supported flags and reconciliation guidance.

- [Run iteration guidance accuracy](run-iteration-guidance-code-review.md) — protected policy, help and warning text align with shipped behavior. Compressed 2026-11-13.

- [Step description alias implementation](step-description-alias-code-review.md) — four green steps, clean reconciliation and two independent Claude Code logic reviews; source plan PR #139. Compressed 2026-11-13.

- [Committed test authorship gate](committed-test-authorship-code-review.md) — committed test evidence, preserved dirty-path exclusions, ancestry/decoder regressions and actual Claude Code review dispositions. Compressed 2026-11-13.

- [Step description diagnostics](step-description-diagnostics-code-review.md) — preferred/legacy field advice, unchanged validation and two independent clean Claude Code reviews; feature-container wording remains separately tracked.

- [Plan body newline preservation](plan-body-newline-preservation-code-review.md) — raw concept-sync snapshots, exact scope-out restoration, compatibility regressions and two final clean Claude Code reviews. Compressed 2026-11-13.

- [Scope-out rollback ownership](scope-out-rollback-ownership-code-review.md) — exact publication receipts, concurrent-edit preservation, durable writes and two final independent clean Claude Code reviews. Compressed 2026-11-13.

- [Concept-sync H1 boundaries](concept-sync-h1-boundaries-code-review.md) — shared reader/writer section boundaries, raw unowned-content regressions and two independent clean Claude Code reviews.

- [Post-1.0 release versioning](post-1-release-versioning-code-review.md) — explicit Breaking notes, major/minor/patch derivation, retained release guards and independent review convergence.

- [Release 1.1.0 preparation](release-1.1.0.md) — fragment coverage, green tests, two independent artifact reviews, and pending Jira/tag publication prerequisites.

- [Release tag publication](release-tag-publication.md) — explicit post-merge publication, verified Bitbucket 1.0.0/1.1.0 tags, isolated Git tests and two final Claude Code reviews.

- [Use-case guidance correction](use-case-guidance.md) — supported assistant routes, both audit gates, explicit CI failure flags, current seed preparation and independent Claude Code review dispositions.

- [Roadmap seed examples](roadmap-seed-examples.md) — explicit materialization, reviewed source alternatives, retained legacy paths and low-yield Claude Code review evidence.

- [README roadmap seed handoff](readme-roadmap-seeds.md) — explicit materialization and review, corrected overview tables, and two final independent Claude Code reviews.

- [Roadmap plan-row selector documentation](roadmap-plan-id-selector.md) — existing row IDs before seeds, separate create semantics, corrected starting-point guidance and low-yield Claude Code reviews.

- [Demo workflow alignment](demo-workflow-alignment.md) — preferred sample fields, accepted-head scaffold timing, bounded promotion requests, readiness review and low-yield Claude Code evidence.

- [Roadmap plan breakdown review](roadmap-plan-breakdown.md) — stage-4 plan-list responsibilities, comparison with seed decomposition, named-evidence review and explicit assessment scope.

- [General onboarding documentation](general-onboarding-docs.md) — concise README routing, execution prerequisites, usable frontmatter, contributor setup and verification.

- [Direct-edit onboarding clarity](direct-edit-onboarding.md) — explicit skip-plan-tool guidance, retained review obligations and first-plan learning context.
