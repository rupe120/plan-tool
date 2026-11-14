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
| Branch | `docs/handoff-undated-names` |
| Disposition | Open: release-cluster decision pending. The review loop was stopped by the owner after pass 4 (not converged; findings had turned to this branch's own wording) |

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

- The directory holds 12 workstream files, `bug-backlog-drain.md` and `README.md`
  (`README.md` § "Workstreams"). The roughly 90 per-change files are merged into their
  workstreams, one section per change with its opened date. No section text was dropped in
  the merge; each section keeps the source file's original title.
- Twelve closed ledgers were compressed to the retention shape before the merge;
  compression dropped only reviewer session UUIDs and a few non-commit ids.
  `roadmap-versioned-from-birth` records its deferrals as `tracked` to fit the closed
  disposition set.
- Durable content moved out: the AI-DLC fit design to `docs/design-plans/`, the Jira
  procedure to `docs/how-to/jira-management.md`, the AI-DLC seam contract to
  `docs/reference/contracts/aidlc-seam.md`.
- One local-only note (`2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`, excluded
  by `.git/info/exclude`) is untracked and unindexed on purpose.

### Still open

- **Compress the large workstreams.** `docs-and-onboarding.md` (about 1,800 lines),
  `tracking-and-jira.md` and `roadmap-feedback.md` hold uncompressed sections; compress
  closed sections per `README.md` § "Retention", never by splitting by change.
- **Retire shipped sections.** Release sections whose work shipped are candidates for
  deletion once nothing live depends on them. Owner decision needed.
- **`unpushed-main` R4-8** (in `tracking-and-jira.md`) stays `pending` and unfiled until
  either function is next touched.
