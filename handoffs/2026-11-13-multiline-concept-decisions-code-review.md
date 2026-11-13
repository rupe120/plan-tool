# Multiline concept decisions: code review ledger

One bounded change, reviewed headlessly (`claude-personal -p`, report-only):
`render_scope_decisions` renders a concept's title and rationale on one line so
a heading- or fence-looking line inside them cannot start a document boundary.
The drain procedure lives in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review ranges | Passes 1–2: `282e75b9f..HEAD`. Pass 3: `origin/main..HEAD` (ten commits, five documentation-only commits not covered before) |
| Head at pass 3 | `10bb51757`; pass-3 corrections: `12bb69d52` |
| Checks | Full suite 14,859 passed, 67 skipped (after pass 1); `tests/test_concept_sync.py` 36 passed (run by the reviewers in passes 2 and 3); pre-push suite passed |
| Reviewer | Headless sessions on `claude-sonnet-5-5`; findings files and stream logs are local scratch (`.tmp/multiline-concept-decisions-code-review-N.*`, gitignored) |
| Disposition | **In progress.** Pass 3 returned four medium documentation findings, so the earlier low-yield exit does not carry; pass 4 on the corrections is pending |

## Settled decisions

- Flattening multi-line rationales to one line is intended; the source entry
  excluded broader Markdown sanitization, schema tightening, parser boundary
  rules and publication protocols.
- `foundational_logic.py:474` builds a prompt-advice block, not an owned plan
  section, and is unchanged. `detail.py:2374` already collapses whitespace.
- The whitespace-collapse idiom is not consolidated here.
- `U+2028` and `U+0085` are not boundaries to this parser; a bare CR is.
- The test's repeat-sync block is a labeled smoke check.

## Findings and dispositions

Pass 1 (code and tests; no material defect):

- Test pinned only `\n` — `fixed 0b20bcbb1` (bare-CR case; a `\n`-only mutant
  fails on it). `declined`: the `U+2028`/`U+0085` cases (not boundaries here)
  and the `wont_do` / nested-concept cases (same code path as the fix).
- Repeat-sync assertion was vacuous — `fixed 0b20bcbb1` (each case asserts the
  exact one-line rendering).
- Another copy of the whitespace-collapse idiom — `declined` (no shared helper
  is importable without a cycle; a consolidation needs AST evidence and a
  `BACKLOG.md` entry).

Pass 2 (low-yield; two low documentation findings):

- Handoff omitted the commit that removed the backlog entry — `fixed 10bb51757`.
- Handoff counted "four" cases after a fifth was added — `fixed 10bb51757`.

Pass 3 (documentation accuracy; no code or test defect; nine findings):

1. Handoff said "Nothing is pushed" after the branch was pushed (medium) —
   `fixed` in the commit that adds this ledger: the sentence is deleted and no
   publication state is kept in the handoff.
2. Queue rule "a `Priority` line goes first" was not a repo rule and matched
   only an entry under `## ROADMAP` (medium) — `fixed` in the same commit: the
   rule is replaced by a pointer to `docs/TRACKING.md` § "Choosing what to
   promote next".
3. `needs investigation` is not a Readiness label (low) — `fixed` in the same
   commit: the handoff points at TRACKING's label table and says what to do
   with an unlabeled entry.
4. The `source_seed` entry's Fix still covered the plain case its own evidence
   says needs no fix (medium) — `fixed 12bb69d52`: heading, Symptom and Fix are
   scoped to the roadmap-published seed.
5. The duplicate-ID entry said the normalized path "does not append the raw
   seed's sections", but it appends the raw `## References` (medium; checked
   against `create.py` and `_render_distilled_markdown`) — `fixed 12bb69d52`.
6. The same entry still said "the joining code has not been read" beside a
   paragraph describing it (low) — `fixed 12bb69d52`: the earlier state is
   dated.
7. Evidence for two entries pointed only at a gitignored scratch log (low) —
   `fixed 12bb69d52`: the load-bearing facts are inline and the log is named as
   local scratch.
8. The session log embedded per-change review passes without a ledger shape
   (low) — `fixed` in the commit that adds this ledger: this file holds them.
9. Imprecise citation for the "measures vocabulary" rule (info) — `fixed
   12bb69d52`: cites § "Validating a semantic property you cannot observe"
   rule 5, with the Withdrawn section as the measured instance.
