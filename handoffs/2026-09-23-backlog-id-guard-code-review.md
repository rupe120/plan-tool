# Code review ledger: the `BACKLOG.md` id guard

| Field | Value |
| --- | --- |
| Change | `tests/test_backlog_ids.py`; the id-selection rule and command in `docs/TRACKING.md`; the `#404` → `#425` renumber; `BACKLOG #233` closed |
| Branch | `fix/backlog-entry-id-uniqueness`, stacked on `cleanup/backlog-drift-and-version-flag` (`443fa912`); pull request #16 |
| Review range | `443fa912..7776e7a6`; later commits on the branch are follow-ups the review turned up |
| Reviewer | Two `/code-review` sessions, run one after the other |
| Checks | Full suite on the branch tip: 13389 passed, 190 skipped. On the real `BACKLOG.md`, a duplicated id fails only `test_backlog_entry_ids_are_unique` (in `tests/test_backlog_ids.py`); a malformed opener or an unclosed fence fails only `test_backlog_is_fully_readable_by_the_id_guard` (in `tests/test_backlog_readability.py`) |
| Disposition | All in-diff findings are fixed or declined. Out-of-range: A is `tracked` in `#308`; B, C and D are `fixed` (`6115a097`, `dabc00f0`, `4e1e5a71`); E is `pending` |

## Settled decisions for the next reviewer

- **Two tests, two files.** `tests/test_backlog_ids.py` asserts that no id opens
  two entries and nothing else, which is the deleted `#233` entry's "one binary
  fact, deliberately all it asserts". Whether that test can read the whole file
  is a separate precondition, checked in `tests/test_backlog_readability.py`: a
  malformed opener, a code fence unclosed to the end of the text, or no entries.
  They are split because a scope contract has one Outcome (round 2, #10). The readability test is not a `BACKLOG.md` format validator, and
  it imports the shared parser from the id test.
- **Not guarded, each a larger check:** `BUG_BACKLOG.md` (no ids); an id held
  only by a `**Closed …**` record, in either of its two shapes; reuse of a
  removed id by the *test* (the documented command covers it); a fence that a
  later stray closer pairs with (CommonMark reads it the same way); every other
  entry structure.
- **Which entry keeps an id.** The one cited elsewhere; with equal citations,
  the one filed later. Rule from `c0ac23c1`, stated once in
  `docs/TRACKING.md`. Date the entries by author date, never by `git log
  --reverse` order, which is not chronological across branches.
- **The id command reads history and the working tree.** It was checked in a
  scratch repo against ids on another branch, introduced only by a merge
  resolution, removed since, committed, staged, unstaged, and run from a
  subdirectory; on the real repo it prints `425` from the root and from `docs/`.
  It cannot see an id a sibling clone has not pushed or a pull-request ref that
  is not fetched.
- **No CI exists.** The test runs on the first test run over a tree holding both
  entries (a pre-push hook after a rebase or merge). Nothing runs it on a clean
  server-side merge. No doc may say it catches a collision "at merge".

## Round 1: 13 findings, all fixed

Commits: `986e6795` renumber, `77f6dec9` test, `52414309` docs, `44ac6bb8` handoff.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | A stray fence flips parity and hides later entries | fixed `77f6dec9`: the guard uses `scope_fence._fenced_code_spans` and refuses an unclosed fence |
| 2 | Ids in other opener shapes are invisible | fixed `77f6dec9` (`blind_spots`, moved to its own file in `5dfe7839`); the `**Closed …**` residual is documented |
| 3 | The command prints nothing from a subdirectory | fixed `52414309`: `:(top)` pathspec, and empty output is documented as failure |
| 4 | The command reads only this clone's refs, and the doc never says to fetch | fixed `52414309` |
| 5 | The renumber moved the earlier-filed entry | fixed `986e6795`: the skills entry (10:19) moves; verified by commit dates |
| 6 | "Catches a collision at merge" has no mechanism | fixed `52414309`, `44ac6bb8` |
| 7 | The handoff contradicts itself on branch counts | fixed `44ac6bb8` |
| 8 | "A third collision" understates the history | fixed `77f6dec9`, `52414309`, `44ac6bb8`: 23 ids across 583 commits |
| 9 | Stale `#233` citations | fixed `44ac6bb8` (09-17 handoff), `52414309` (decisions log); the 09-14 handoff was left in round 1 and fixed in round 2, #5 |
| 10 | "Never fill a gap" contradicts a command that reads the file | fixed `52414309`: reads history; refined by round 2, #1 and #2 |
| 11 | The guard imports from `jira_grade`, which `#308` retires | fixed `77f6dec9` |
| 12 | The failure message truncates titles and does not say who moves | fixed `77f6dec9`; refined by round 2, #8 |
| 13 | One commit bundles the test, the docs, and the entry removal | fixed `986e6795`, `77f6dec9`, `52414309` |

## Round 2: 13 in-diff findings

Commits: `b02e3791` test, `7776e7a6` docs. Twelve of the 13 describe round 1's
own edits; #5 is a missed site round 1 had declined.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `git log -p` prints no diff for a merge, so ids introduced only by a merge are invisible; 19 ids on `origin/main`, `#399`–`#401` among them, are live | fixed `7776e7a6`: `-m`, verified in the case matrix |
| 2 | The command reads only committed history, so a session's uncommitted entry is not counted | fixed `7776e7a6`: adds `git grep` over the working tree |
| 3 | A hard-wrapped prose line starting `**#97** …` fails `blind_spots` with a misleading message; 107 historical versions | fixed `b02e3791`: a malformed opener needs a dash or colon after the id. Replayed over 583 versions: 0 flagged. The message says to rewrap |
| 4 | The collision-dating recipe breaks on an apostrophe in the title and does not say which date decides | fixed `7776e7a6` |
| 5 | `handoffs/2026-09-14-developer-docs-and-tracking.md` still cites the removed `#233` as open | fixed `7776e7a6`: a pointer to the check; the rest of that frozen record is untouched |
| 6 | "Per-finding dispositions are in the fix commit messages" is false for this branch | fixed in the commit that adds this ledger |
| 7 | "Ids have collided 23 times … most recently #404" misstates the measurement | fixed `7776e7a6`; the figure was then dropped from `CONTRIBUTING.md` because it goes stale |
| 8 | `_explain` runs in no test; a stub's title prints with its pointer; two mutants stay green | fixed `b02e3791` |
| 9 | The docstring names one `**Closed …**` shape; the file has two | fixed `b02e3791` (docstring, parametrized test), `7776e7a6` (decisions log) |
| 10 | `blind_spots` widens the deleted `#233` entry's one-fact fence | `fixed 5dfe7839`: the owner chose to split it from the id test and keep it, so the id test is back to one fact and the readability check is its own file with its own scope statement. The decisions log records the split |
| 11 | The decisions-log record departs from that file's conventions | fixed `7776e7a6`: now `### #233` under "Shipped records" |
| 12 | The Id item packs four contracts into one bullet | fixed `7776e7a6` |
| 13 | An unclosed fence that a later bare closer pairs with is not reported | declined: CommonMark parses it identically, and flagging it would flag valid documents. Named as a residual in the docstring (`b02e3791`) |

## Out of range (recall mode, not part of either round's core count)

| # | Finding | Evidence | Disposition |
| --- | --- | --- | --- |
| A | `jira_grade.fenced_spans` reads a line like `` ```inline``` wrapped text `` as an unclosed fence opener that swallows the rest of the document; `scope_fence._fenced_code_spans` does not | Reproduced. `plan_tool/review.py` imports the helper for two parsers that are not Jira-grade code (`_find_redirect_heading` at line 5985, `_split_audit_fix` at line 7125). The swap the review suggested was tried in a scratch edit of `review.py` and reverted: it fails `test_indented_citation_fence_protects_the_boundary`, because `review.py` deliberately accepts fences indented past three spaces and `scope_fence` allows only three. The two scanners are wrong in opposite directions, so there is no drop-in | `tracked #308` (`9675112b`): its **Allowed reorganization** now says the relocation keeps the indentation behavior and decides the inline-code flaw |
| B | `docs/history/backlog-decisions.md` links to 12 plans under `../implementation-plans/2-*.md` that now live in `../implementation-plans/archive/` | Checked: 12 broken relative links (lines 23–34, 74, 75), each resolving under `archive/`. Enumerating the file also found one stale inline path, `docs/implementation-plans/2-roadmap-01-domain-constraints.md`, now under `archive/` | `fixed 6115a097`: the 12 links and the inline path repointed, each target checked; the other 6 links, the anchored link, and the two live inline paths already resolved |
| C | 9 links in three other files point at plans that now live under `archive/`: 4 in `handoffs/2026-09-08-authored-artifact-structure-versioning.md`, 3 in `handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md`, 2 in `docs/explanations/audit-pass-persistence.md` | Found by enumerating B's class across every tracked `.md` outside the archives and saved reports; each target exists under `archive/` | `fixed dabc00f0`: path-only (each changed line differs by one inserted `archive/`); the two handoffs are dated records, edited on the owner's explicit request. One test, `test_non_stage_brief_drift_handoff_records_delivery_and_367_closeout`, pinned the old link string and was updated in the same commit; no other test names any of the 18 repointed targets |
| D | 2 links in `handoffs/2026-09-08-authored-artifact-structure-versioning.md` (lines 575, 6480) point at `docs/ROADMAP_EVIDENCE_V1_RETIREMENT.md` | The doc was renamed, with no content change, to `docs/history/roadmap-evidence-v1-retirement.md` by `79a8e131` (the PR #13 restructure), so no `archive/` path exists: a moved doc, not a moved plan | `fixed 4e1e5a71`: both links repointed; line 575's label, which was the literal old path, changed with its target |
| E | By my count about 144 broken relative links in 30 tracked `.md` files, outside the archives and saved reports | 26 sit in intentionally fictional test fixtures (`tests/fixtures/reformat/`); 10 are in `RUNBOOK.md` (e.g. `docs/ROADMAP_WALKTHROUGH.md`); many are frozen plan-detail files whose edit would make their saved audit reports stale. Not classified further | `pending`: a link guard, or a triage of the live-doc share, is the owner's call |

## Exit

No further round is scheduled. Round 2's findings mostly described round 1's own
edits, which is the "the loop is auditing your own edits" exit in `CLAUDE.md`,
and three were real defects in round 1's remedies. The two properties were
therefore re-verified directly: the id command against a case matrix, and the
readability check against every historical version of `BACKLOG.md`. Another
round is the owner's call.
