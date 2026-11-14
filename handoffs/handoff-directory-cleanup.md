# Handoff directory cleanup

| Field | Value |
| --- | --- |
| Opened | 2026-11-13 |
| Branch | `docs/handoff-cleanup` |
| Disposition | Open: release-cluster decision pending. The review loop was stopped by the owner after pass 4 (not converged; findings had turned to this branch's own wording) |

Route: docs hygiene only. No code, plan, or backlog-entry semantics change.
`README.md` owns the directory contract (naming, ledger shape, retention, index).

## Scope contract

- **Outcome:** every file here is indexed in `README.md` with a live purpose, or retired
  with its durable content moved to its canonical home.
- **In scope:** `handoffs/*.md` and the `README.md` index.
- **Out of scope (deliberately not touched):** frozen plans, plan details, saved reports
  and `docs/evidence/*.json` receipts, which cite handoffs by path and pin their text;
  rewriting a ledger finding's substance; the gitignored `.tmp/` scratch handoffs
  (owner decision, 2026-09-29).
- **Per retirement:** also add the path to `former-dated-names.md`'s retired list.
- **Per retirement (grep):** grep the retired filename across tracked files. Hits may remain only
  in frozen files, each named in README § "Known dangling citations".

## State, 2026-11-13

- `README.md` links every other file at least once.
- Twelve closed ledgers are compressed to the retention shape; compression dropped only
  reviewer session UUIDs and a few non-commit ids. `roadmap-versioned-from-birth` records
  its deferrals as `tracked` to fit the closed disposition set.
- Two superseded roadmap pickups and the dated consolidation handoff are retired.
- All handoffs are named by concept; the dated prefixes were dropped 2026-11-13 and
  `former-dated-names.md` keeps the old-name map and dates. One local-only note
  (`2026-10-16-token-ledger-logging-gaps-reverted-attempt.md`, excluded by
  `.git/info/exclude`) is untracked, unrenamed and unindexed on purpose.

## Still open

- **Release cluster (2026-10-19 to 10-23, about 15 files):** retire or keep as the record
  behind the release tags. Owner decision needed. The release pickup owns the next action
  and says to preserve the token-ledger reverted-attempt note.
- **`unpushed-main` R4-8** stays `pending` and unfiled until either function is next touched.
