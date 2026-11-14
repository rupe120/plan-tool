# Tail verdict whose artifacts moved (#481) — review ledger

| Field | Value |
| --- | --- |
| Change | BACKLOG #481: the authoring follow-up row reads `stale-revision` whenever the tail result's recorded audit revision no longer matches the files on disk, whatever the verdict's original cause, and no longer calls an unprovable result stale |
| Branch | `fix/tail-verdict-artifacts-moved` |
| Reviewer | `/code-review high` in-session (forked), report-only |

## Settled decisions

- No new persisted field: the saved result already records `audit_revision`. ""Moved" means a recorded revision for this detail grade that differs from the bundle now on disk.
- A missing result, a malformed one, one for another detail grade, or a capture that fails is not evidence the files moved; the verdict keeps its own cause and count. A failed capture is `unknown` in `project_saved_completeness_result` (what `status` and `list` show), so the authoring tail agrees with it. **Decided in the delta review; round 1's finding 2 argued the opposite and was reversed on that basis.**
- A moved tail drops its deterministic blockers (computed on the old text); an unmoved one keeps them.
- One capture of the bundle serves both freshness checks.

## Findings (round 1)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | A `set` verdict not proven current lost its gap count although the text was unchanged | **Fixed.** It keeps its count; only an empty set reads as the fixed fresh-audit row |
| 2 | A capture failure after a recorded revision was treated as "not moved" | **Fixed in round 1, reversed in the delta review** (see Settled decisions): a failed capture is `unknown`, not `moved` |
| 3 | Duplicated absent-wording branch; dead ids passed into the stale verdict | **Fixed.** One condition; the stale verdict is built empty |
| 4 | Two captures of the bundle on the not-current path | **Fixed.** One shared capture; a call-counting test and a mutation of the sharing pin it |
| 5 | Docstring contradicted the code and was too long | **Fixed.** Short, points at the how-to |
| 6 | `audit.md` did not describe the authoring follow-up | **Fixed.** New section |
| 7 | Grade-mismatch and capture-failure carve-outs unpinned | **Fixed.** Tests; each goes red under mutation |

## Findings (delta review of the round-1 fix commit)

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | A failed capture was called moved; `project_saved_completeness_result` calls it `unknown`, so the tail disagreed with `status` and `list` | **Fixed.** Capture failure is unproven; a carve-out test pins it |
| 2 | The bundle was captured eagerly on every guidance call | **Fixed.** Captured only once a result with a recorded revision for this grade exists |
| 3 | A dead absent-verdict guard contradicted the doc table | **Fixed.** Removed; the doc says an absent verdict reads the fixed row |
| 4 | Hand-derived copy of "completed empty set" | **Fixed.** `verdict.is_completed_empty_set` |
| 5, 6 | Two helpers plus a threaded `captured=` tuple re-implemented the persistence layer's freshness classification | **Fixed.** One `_tail_result_freshness` (current / moved / unproven) from one capture; the tests patch that seam |
| 7 | The deterministic-only case was unpinned | **Fixed.** Pinned for a real finding (a counted gap) and a synthetic arm (a failing check); mutation-checked |

Closure: two review rounds. The delta review reversed a round-1 fix on the evidence of an existing canonical classification, which is the case for running it.
