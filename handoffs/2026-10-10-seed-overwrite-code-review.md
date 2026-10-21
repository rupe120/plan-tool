# Unpublished seed overwrite — review ledger

| Field | Value |
| --- | --- |
| Change | BUG_BACKLOG "`--refresh-seeds` and `--accept-seed` overwrite an existing `plan-seeds/` file for a seed that was never published": refresh and accept rewrite a promoted copy only when the seed state records `published: true` |
| Branch | `fix/seed-overwrite-unpublished` |
| Review range | `c4c936029..HEAD` |
| Reviewer | `/code-review high main` in-session (forked), report-only |

## Settled decisions

- The recorded `published` flag is the only publication proof, for apply, refresh, and accept (`_seed_recorded_published`). An existing destination or a same-named archive is not proof: it may be hand-written or another roadmap's.
- An unpublished seed's existing `plan-seeds/` file is left untouched, not refused; `--apply` still refuses it as a collision.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `--apply` links copies before recording `published`; a failure between leaves an unrecoverable file the tool wrote | **Filed** in BUG_BACKLOG (with 2). Accepting the in-file marker as proof needs a new parser; the window is narrow |
| 2 | `--accept-seed` writes the sidecar before the promoted copy | **Fixed in the follow-up branch `fix/accept-seed-write-order`** (copy first, sidecar second; `test_accept_failed_copy_write_leaves_the_draft_re_acceptable`). Pre-existing order, not introduced by this change |
| 3 | The flag rule is hand-copied at three sites | **Fixed.** `_seed_recorded_published` |
| 4 | Refresh reads and reports an unpublished seed's foreign `plan-seeds/` file (non-UTF-8 aborts refresh) | **Fixed.** Targets drop the promoted path unless recorded published; pinned by `test_an_unpublished_seeds_plan_seeds_file_is_neither_read_nor_reported`, red under mutation |
| 5 | Module docstring and ROADMAP_FORMAT.md still state the unconditional rule | **Fixed** |
| 6 | The skip prints nothing | **Fixed.** Accept names the untouched file and why; pinned by a CLI test, red under mutation |
| 7 | No refresh-route test | **Fixed** with 4 |

Mutation: restoring the old predicates turns the three round-0 tests red; dropping the target filter and the message turns the two round-1 tests red.

## Follow-up review: accept write order (`fix/accept-seed-write-order`)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `--accept-seed` hard-codes `status: current`, so accepting a hand edit of an invalidated seed clears the invalidation | **Filed** (BUG_BACKLOG, decision-needed). Pre-existing (`bf3a546b3` already hard-codes it); whether a hand edit after invalidation counts as re-review is a design call |
| 2 | A failed copy write surfaces as a bare `OSError` with no retry hint | **Fixed.** Wrapped in `RoadmapError` stating nothing was recorded and re-running is safe |
| 3 | The recovery test checks retry only, not that the sidecar is byte-identical; the mirror failure is untested | **Fixed.** Bytes asserted unchanged; `test_accept_failed_sidecar_write_after_the_copy_is_re_acceptable` added |
| 4 | This ledger listed finding 2 as filed | **Fixed** (row above) |
