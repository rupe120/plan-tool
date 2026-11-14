# Handoff directory cleanup

| Field | Value |
| --- | --- |
| Opened | 2026-11-13 |
| Branch | `docs/handoff-cleanup` |
| Disposition | Open: release-cluster decision and pre-push review pending |

Route: docs hygiene only. No code, plan, or backlog-entry semantics change.
Start with `BACKLOG.md`'s working board; this file does not override it.
`README.md` owns the directory contract (naming, ledger shape, retention, index);
this file records what remains to clean and the owner decisions that fence it.

## Scope contract

- **Outcome:** every file here is indexed in `README.md` with a live purpose, or retired
  with its durable content moved to its canonical home.
- **In scope:** `handoffs/*.md` and the `README.md` index.
- **Out of scope (deliberately not touched):** frozen plans, plan details and saved
  `reports/` under `docs/implementation-plans/` and `docs/evidence/*.json` receipts,
  which pin their text and cite handoffs by path; rewriting any ledger finding or
  disposition; the gitignored `.tmp/` scratch handoffs and logs.
- **Stop / defer:** when a record's live or retired status is unclear, leave it and ask.

## Standing owner decisions

- **2026-09-29:** `.tmp/` scratch handoffs and logs are left as they are; nothing there is
  sorted or deleted.
- **2026-09-29:** push is held by the owner; cleanup commits stay local until review.
- **2026-11-13:** new handoffs and ledgers are named by concept, not date
  (`README.md` § "Naming"). Existing dated files keep their names.

## State, 2026-11-13

`README.md` links each of the 94 other files exactly once; the index check in § "Retention" returns empty.
Twelve closed ledgers were compressed to the retention shape; two superseded roadmap
pickups were retired (their scope lives in BACKLOG #492 and the closed #496 record in `docs/history/backlog-decisions.md`).

Compression omissions, kept so a later reader does not restore them:

| Ledger | Dropped | Why |
| --- | --- | --- |
| `roadmap-brief-source-drift` | `40e76f91` | Documentation-only commit cited in a scope note, never for a finding |
| `roadmap-structural-feedback-approval` | `509cd49f`, `8dc2e9d0`, `df582bab`, `4561ff6e` | Documentation- or ledger-only commits in scope lines |
| `roadmap-concept-comparison` | `#1`, `#6` | Cross-references to finding numbers, not backlog ids |
| `committed-test-authorship`, `scope-out-rollback-ownership`, `seed-default-location`, `step-description-alias` | reviewer session UUIDs | Not commits or backlog ids; the review range, report path and heads stay |
| `run-iteration-guidance`, `plan-body-newline-preservation` | nothing | No id, hash or backlog reference was dropped |
| `completeness-apply-retirement` | `#74`, `#139`, `#176` | Dated-provenance references in a verified-clean list, with no disposition |
| `roadmap-context-ceiling` | Integration candidate id `c886d0f2` | Not a commit; the finding line describes the case |
| `prompt-budget-model-window` | 9-character forms `0c06447a1`, `203d575b4`, `bcb89a6af`, `e058d8be6`, `f17befcf4` | Each survives in its 8-character form |

## Still open

- **Release cluster (2026-10-19 to 10-23, about 15 files):** retire or keep as the record
  behind the release tags. Owner decision needed; `2026-10-19-public-onboarding-and-release.md`
  owns the next action, and it says to preserve the token-ledger reverted-attempt note.
- **Reader enumeration:** `2026-10-10-completeness-next-step-verdict-finish-reader-enumeration.md`
  stays beside its ledger because archived plan details cite it by path.
- **Uncompressed closed ledgers:** the 2026-11-13 ledgers, `iteration-guide-routes`
  (tracked items) and the 2026-10-10 small ledgers are already short; compress on the
  next pass only if they grow.
- **`unpushed-main` R4-8** stays `pending` and unfiled until either function is next touched.
- **Review before push:** run `/code-review` over this branch before any push.
