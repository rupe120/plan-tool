# Loop-termination lists: code review ledger

One bounded documentation change, fact-checked headlessly (`claude-personal -p`,
report-only): `docs/ITERATION.md` § "How the loop terminates" lists every reason
`should_continue` returns with its code, `RUNBOOK.md` points there for the stops
it does not define, and a drift test pins the list. The drain procedure lives in
[`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head. The branch also carries one housekeeping commit, the drain-log trim `165156208` |
| Heads reviewed | Pass 1: `ea5396a14`. Pass 2: `b954b6ce7`. Corrections: `77fddec1a`, `b954b6ce7`, `37bdc1786`, then this ledger revision (the next commit) |
| Checks | `tests/test_convergence.py` green at `37bdc1786`; the full suite ran green (14,926 passed, 67 skipped, 2026-11-13) at `ea5396a14`, and later commits change documentation and that one test. The reviewers could not run mutants, so the mutation claims are the author's runs |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/loop-termination-lists-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

## The change itself

- **Behavior:** the section names each stop by its code and states per command
  where it applies and what it exits with; the drift test fails when a
  `should_continue` code has no bullet, or a bullet names a code the function
  no longer returns. Dropping a bullet failed it, and so did adding a stale code.
- **Settled decisions:** no RUNBOOK troubleshooting entry is added for
  `no_progress` (a separate addition); `docs/ITERATION.md` lines 10-12 ("a plan
  that converges under audit → apply is sound") stay, qualified by the gotcha
  near line 30; `docs/how-to/pipeline/run.md` and `CLAUDE.md` "no new findings"
  describe the `/code-review` loop and stay.

## Findings and dispositions

Pass 1 (four medium, three lower):

1. "Converged … apply-eligible" is true only for `detail` — `fixed 77fddec1a`.
2. `no_blocking_findings` is not set by `create` or `detail`, and a round-0
   advisory-only plan gets no apply pass under triage — `fixed 77fddec1a`.
3. A flat "Exit code 0" omitted `completeness-audit --fail-on-findings` —
   `fixed 77fddec1a` (one "Exit codes" paragraph).
4. The list omitted `completeness-audit`'s extra codes and listed `disabled`,
   which never prints — `fixed 77fddec1a` (pointer to `audit.md`; reworded).
5. The drift test was vacuous for `marginal` — `fixed 77fddec1a` (anchor on
   "(`code`" once per code; AST extraction).
6. `docs/ITERATION.md` line ~30 used the hyphenated spelling with another
   meaning — `fixed 77fddec1a`.
7. The drain line lacked hashes and narrated the session — `fixed b954b6ce7`.
   `declined`: a RUNBOOK troubleshooting entry for `no_progress`.

Pass 2 (three medium, five lower):

1. "Reconcile loops set `no_blocking_findings`" — no CLI path runs that loop —
   `fixed 37bdc1786`.
2. The RUNBOOK Budget bullet and the `--time-budget` Defaults row contradicted
   the `--fail-on-findings` rule — `fixed 37bdc1786`.
3. "Every stop exits 0" omitted the drift-halt exit 2 and a failed `--commit` —
   `fixed 37bdc1786`.
4. The `terminal_hand_apply` remap sentence omitted
   `all_auto_apply_findings_deferred` — `fixed 37bdc1786`.
5. "Final stderr line" is loose: halts print no code and the reconcile loop uses
   stdout — `fixed 37bdc1786` (the section now says "stop banner").
6. "No worse than the prior iteration" does not follow from the marginal
   predicate — `fixed 37bdc1786`.
7. `docs/GLOSSARY.md` kept the hyphenated meaning — `fixed 37bdc1786`.
8. The drift test was one-directional — `fixed 37bdc1786` (reverse direction added; it
   caught one parenthesized mention of the author's own).

## Closure

**Stopped at exit 2 on 2026-11-13; not converged, not clean.** Pass 1 returned
four medium findings and pass 2 three, so the low-yield condition never held.
Most findings describe this branch's own new wording (per-command scope and
exit-code claims the first rewrite stated too broadly), the shape `CLAUDE.md`
calls the loop auditing its own edits; the original omission the entry named was
real and the drift test pins it. All findings are applied or dispositioned. No
third pass is planned.
