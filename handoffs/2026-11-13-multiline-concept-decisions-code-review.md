# Multiline concept decisions: code review ledger

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
`render_scope_decisions` renders a concept's title and rationale on one line so
a heading- or fence-looking line inside them cannot start a document boundary.
The drain procedure lives in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review ranges | Passes 1–2: `282e75b9f..af59e779c`. Passes 3–4: `origin/main..` the branch head named in the next row |
| Head reviewed by pass 4 | `7beb3090b`. Corrections to pass 4: `9be9acf65`, then this ledger revision (the next commit) |
| Checks | Full suite 14,859 passed, 67 skipped, 2026-11-13, at `0b20bcbb1` (code unchanged since); `tests/test_concept_sync.py` 36 passed, run by the pass-2, pass-3 and pass-4 reviewers |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/multiline-concept-decisions-code-review-N.*`, gitignored); the findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

## Settled decisions

- Flattening multi-line rationales to one line is intended; the source entry
  excluded broader Markdown sanitization, schema tightening, parser boundary
  rules and publication protocols.
- `foundational_logic.py:474` builds a prompt-advice block, not an owned plan
  section, and is unchanged. `detail.py:2374` already collapses whitespace.
- The whitespace-collapse idiom is not consolidated here.
- `U+2028` and `U+0085` are not boundaries to this parser; a bare CR is.
- The test's repeat-sync block is a labeled smoke check.

## The fix itself

- **Behavior:** `render_scope_decisions` (`plan_tool/concept_sync.py`) collapses
  whitespace in each concept's title and rationale, so a heading-, fence- or
  bare-CR-looking line inside them stays inside the owned `## Deferred` /
  `## Out of scope` body. Fixed in `a0cda5b53`; the test is tightened in
  `0b20bcbb1`.
- **Evidence (this session's runs; no reviewer could re-run mutants, because
  the reviewers' sandboxes refused them):** the four cases in the original
  test failed on the pre-fix code and passed with it; after the bare-CR case
  was added, a `\n`-only mutant failed on that case and a `.strip()` mutant
  failed on all five.

## Findings and dispositions

Pass 1 (code and tests; no material defect):

- Test pinned only `\n` — `fixed 0b20bcbb1` (bare-CR case). `declined`: the
  `U+2028`/`U+0085` cases (not boundaries here) and the `wont_do` /
  nested-concept cases (same code path as the fix).
- Repeat-sync assertion was vacuous — `fixed 0b20bcbb1` (each case asserts the
  exact one-line rendering).
- Another copy of the whitespace-collapse idiom — `declined` (no shared helper
  is importable without a cycle; a consolidation needs AST evidence and a
  `BACKLOG.md` entry).

Pass 2 (low-yield; two low documentation findings):

- Handoff omitted the commit that removed the backlog entry — `fixed 10bb51757`.
- Handoff counted "four" cases after a fifth was added — `fixed 10bb51757`.

Pass 3 (documentation accuracy; nine findings, four medium):

1. Handoff said "Nothing is pushed" after the branch was pushed — `fixed 7beb3090b`.
2. Queue rule "a `Priority` line goes first" was not a repo rule — `fixed 7beb3090b`
   (see pass-4 finding 1 for the replacement).
3. `needs investigation` is not a Readiness label — `fixed 7beb3090b`.
4. The `source_seed` entry's Fix covered the plain case its own evidence says
   needs no fix — `fixed 12bb69d52`.
5. The duplicate-ID entry said the normalized path "does not append the raw
   seed's sections", but it appends the raw `## References` — `fixed 12bb69d52`.
6. The same entry still said "the joining code has not been read" — `fixed 12bb69d52`.
7. Evidence for two entries rested only on a gitignored scratch log —
   `fixed 12bb69d52`.
8. The session log embedded review passes without a ledger shape —
   `fixed 7beb3090b` (this file).
9. Imprecise citation for the "measures vocabulary" rule — `fixed 12bb69d52`.

Pass 4 (ten findings: three medium, seven low):

1. Drain rule 4 imported the lead's Jira-promotion order, contradicting rule 1 —
   `fixed 9be9acf65`: rule 4 now says the handoff drains `BUG_BACKLOG.md` only
   and cross-file ordering is the lead's call.
2. Procedure step 6 restated the stopping rule as one low-yield round —
   `fixed 9be9acf65`: it now points at `CLAUDE.md` § "Severity-aware
   conceptual-audit stopping rule" (two consecutive low-yield passes).
3. The duplicate-ID entry parked a reproducible clause behind the
   unreproducible one — `fixed 9be9acf65`. **Verified by probe, 2026-11-13:** a
   direct-ready seed repeating `## Notes` crashes `create` with "concept scope
   contains duplicate IDs", and the same seed with `## Notes` once does not.
   It is now its own `ready` entry; the 0.1.0 distill-side cause stays
   `evidence-gated`. The bug itself is **not** fixed on this branch
   (`tracked`: `BUG_BACKLOG.md`, the repeated-heading entry).
4. Ledger used a moving `HEAD` range, no current-head row, and relative
   "this commit" dispositions — `fixed` in this ledger revision.
5. Ledger claimed "pre-push suite passed" with no date or count — `fixed` in
   this ledger revision: replaced by a dated full-suite row.
6. Moving the record dropped the fix's own evidence and the caveat that the
   mutation claims are this session's — `fixed` in this ledger revision (section
   "The fix itself").
7. Date-less review-status claims in three files — `fixed` in `9be9acf65` (README
   and drain log are status-free) and this ledger revision (status is dated and
   anchored in the table).
8. The duplicate-ID entry cited "the same-day throwaway run" without
   identifying it — `fixed 9be9acf65`: the run is described by its seed shape,
   version and scope.
9. Stale line numbers in the duplicate-ID entry — `fixed 9be9acf65` (cited by
   symbol). `declined`: relabeling the untouched entry that carries
   `Readiness: needs investigation` — it is not part of this change; the drain
   handoff's rule 6 covers unlabeled and non-standard labels by surfacing them.
10. Trim rule had no exit for `refuted`/`declined`/`tracked` lines, and the
    `source_seed` entry's Files cited archive constants instead of the code that
    archives — `fixed 9be9acf65` (both).

## Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 3 returned
four medium findings and pass 4 three, so the low-yield condition (two
consecutive diminishing passes) never held after pass 2. Most of pass 4's
findings describe this branch's own earlier documentation edits (the ledger,
the queue and stopping rules, the entries' evidence wording), the shape
`CLAUDE.md` calls the loop auditing its own edits; pass 4's one new defect
(finding 3) is a real bug in a neighboring code path, filed rather than fixed
here. All ten pass-4 findings are applied or dispositioned above. The code and
test change (`a0cda5b53`, `0b20bcbb1`) drew no material finding in any pass. No
fifth pass is planned.
