# Handoff directory

This directory's own upkeep: scope fence, owner decisions and open items. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Handoff directory cleanup](#handoff-directory-cleanup) | 2026-11-13 |

## Handoff directory cleanup

*Opened 2026-11-13.*

| Field | Value |
| --- | --- |
| Opened | 2026-11-13 |
| Branch | `docs/handoff-retire-and-move` |
| Disposition | Open: owner items listed under Still open |

Route: docs hygiene only. No code, plan, or backlog-entry semantics change.
`README.md` owns the directory contract (naming, ledger shape, retention, index).

### Scope contract

- **Outcome:** every file here is indexed in `README.md` with a live purpose, or retired
  with its durable content moved to its canonical home.
- **In scope:** `handoffs/*.md` and the `README.md` index.
- **Out of scope (deliberately not touched):** frozen plans, plan details, saved reports
  and `docs/evidence/*.json` receipts, which cite handoffs by path and pin their text;
  rewriting a ledger finding's substance; the gitignored `.tmp/` scratch handoffs
  (owner decision, 2026-09-29).
- **Per retirement:** grep the retired filename across tracked files; nothing outside
  `handoffs/README.md` and frozen files may cite it (README § "Policy").

### State, 2026-11-13

- The directory holds two workstream files (`run-and-completeness.md`, `tracking-and-jira.md`),
  `bug-backlog-drain.md`, this file and `README.md` (`README.md` § "Workstreams"). About 90
  per-change files were merged into workstreams, compressed, then retired once their work
  shipped and their durable decisions moved to docs.
- Durable content moved out: the AI-DLC fit design to `docs/design-plans/`, the Jira
  procedure to `docs/how-to/jira-management.md`, the AI-DLC seam contract to
  `docs/reference/contracts/aidlc-seam.md`, and the settled design, contract and
  procedure decisions of the retired workstreams to `docs/ARCHITECTURE.md`, the FORMAT
  documents, `DATA_CONTRACT.md`, `RUNBOOK.md`, `docs/how-to/pipeline/run.md`,
  `docs/TRACKING.md`, `docs/history/backlog-decisions.md` and the evidence pages.
- Retired workstreams: `model-and-budget`, `roadmap-candidates`, `roadmap-feedback`,
  `roadmap-plans`, `roadmap-aidlc`, `create-and-detail`, `docs-and-onboarding`, `release`,
  `review-process`.
- Live follow-ups were filed as `BACKLOG.md` #527 (remote demo-ref refresh), #528
  (stage-4 plan breakdown assessment), #529 (live-doc link guard) and #530 (remaining
  readability audit batches and walkthrough), plus `BUG_BACKLOG.md` entries.
- Deliberately dropped, not filed: the Integration replay and its observation-index decision
  (separate repository), the lessons-surface ablation (`BACKLOG.md` #195 owns shrinking the
  lessons surface), the `claude-personal` alias (personal configuration), the Linux
  per-argument limit (recorded as unverified in
  `docs/evidence/integration-context-budget-2026-10-09/sizing.md`), the unsent release
  announcement, GitHub mirror state, 1.1.0 Jira coverage, review case studies, the
  iterate-convention pointer swap, two assistant-tooling ideas, the PR-template readability
  item, and the five PR #195 review findings (`declined`: low value).
- One local-only note (`2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`, excluded
  by `.git/info/exclude`) is untracked and unindexed on purpose.

### Still open

- **`unpushed-main` R4-8** (in `tracking-and-jira.md`) stays `pending` and unfiled until
  either function is next touched.
- **Owner items held in `tracking-and-jira.md` and `run-and-completeness.md`:** Bitbucket
  approval and merge-queue settings, remaining Jira configuration, architect review of the
  `CLAUDE.md` and `DIRECTIVES.md` edits (A2/G1), #473 and #474, IPPT-16, and the reading of
  `awaiting-human-action`. Each retires its section when decided.
- **Local `stash@{0}`** holds an abandoned stack-propagation attempt; drop it in the clone
  that holds it.
- **`2-roadmap-candidate-vocabulary-retry.md`** still reads `status: planning`; archive or
  supersede it by owner decision.
