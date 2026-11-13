# Iteration-budget hints: code review ledger

One bounded change, reviewed headlessly (`claude-personal -p`, report-only): the
`deadline_exceeded` resume hint in `create`, `detail` and `completeness-audit`
prints `larger_iteration_budget_seconds(state.budget.budget_seconds)` instead of
the literal `1800`, and calls the deadline a no-progress deadline instead of a
wall-clock budget. The drain procedure lives in
[`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head. The branch also carries one housekeeping commit, the handoff trim `3bec745bc` |
| Heads reviewed | Pass 1: `2403fec96`. Pass 2: `9dc1d748e`. Pass 3: `06a8f0988`. Corrections: `9dc1d748e`, `4d8da8c95`, `2438c88f0`, then this ledger revision (the next commit) |
| Checks | Full suite 14,926 passed, 67 skipped, 2026-11-13, at `2403fec96`; later commits touch the helper's type and docstring, a comment, tests and docs, and the affected test files were re-run green (2,997 passed at `4d8da8c95`). The reviewers could not run mutants, so the mutation claims are the author's runs |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/iteration-budget-hints-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

## The fix itself

- **Behavior:** the three `deadline_exceeded` hints print a value above the
  loop's effective deadline (`convergence.larger_iteration_budget_seconds`:
  double the deadline, floored at the default). Fixed in `bab3c18a2`.
- **Evidence (the author's runs):** hardcoding `1800` at each site failed exactly
  that site's test; the helper test pins that the value always exceeds the
  deadline.
- **Not fixed, filed in `BUG_BACKLOG.md`:** the `detail` and `completeness-audit`
  hints omit `--iterate`, and the `max_iterations` hints print a literal
  `--max-iterations 5`, so those printed commands still do not change the run.

## Findings and dispositions

Pass 1 (no high finding):

1. `WHY["open"]` enumerated stops and dropped the stall stop — `fixed 9dc1d748e`
   (see pass-2 finding 1 for why the text matters less than assumed).
2. The `detail` and `completeness-audit` hints omit `--iterate` — `tracked`:
   `BUG_BACKLOG.md`. Probed: the printed command builds a disabled budget.
3. The handoff line cited no hash — `fixed 9dc1d748e`.
4. Site tests use a 0-second deadline — `declined`: `budget.budget_seconds` and
   `state.budget.budget_seconds` are equal in production, and the helper test
   pins the property.
5. A missing blank line and an over-wide comment — `fixed 9dc1d748e`.

Pass 2 (one medium, five low):

1. `WHY["open"]` and `_HEADINGS["open"]` are never rendered, so the reword and
   its test touched dead text — `fixed 4d8da8c95` (test dropped), `tracked`:
   `BUG_BACKLOG.md` (deleting the unused entries).
2. The `--max-iterations 5` hints are the same class — `tracked`: widened into
   the residual entry.
3. The entry's locator for the skip-without-`--force` comment was off —
   `fixed 4d8da8c95`.
4. The handoff cited "(this commit)" — `fixed 06a8f0988`.
5. A `should_continue` docstring example named a stop the code never emits —
   `fixed 4d8da8c95`.
6. The helper was typed `float` and its test pinned an unreachable float —
   `fixed 4d8da8c95`.

Pass 3 (three low, all documentation):

1. The residual entry's site list omitted the `detail --force` hint —
   `fixed 2438c88f0`.
2. The drain log line carried a pass-by-pass record inline — `fixed` in this
   ledger revision: the record lives here and the line points to it.
3. The dead-text finding lived only in a line dropped at merge — `fixed 2438c88f0`
   (filed in `BUG_BACKLOG.md`).

## Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 2 returned a
medium finding, so the low-yield streak restarted and pass 3 (three low findings)
is one pass, not two. Pass 3's findings describe this branch's own new entry and
handoff text, the shape `CLAUDE.md` calls the loop auditing its own edits. The
code change drew no material finding in any pass; the one medium was a false
premise inherited from the removed backlog entry. All pass-3 findings are applied.
No fourth pass is planned.
