# Onboarding guidance entry removal: code review ledger

One bounded change, fact-checked headlessly (`claude-personal -p`, report-only):
the `BUG_BACKLOG.md` entry "Onboarding and installed skill instructions conflict
with canonical audit and iteration rules" is removed with a dated record in
`docs/history/backlog-decisions.md`, two passages the entry's class still
reached (`docs/how-to/roadmap.md`, `RUNBOOK.md`) are corrected, and the
leftovers are filed as two `BUG_BACKLOG.md` entries. The drain procedure lives
in [`bug-backlog-drain.md`](bug-backlog-drain.md).

| Item | State |
| --- | --- |
| Review range | `origin/main..HEAD` at each pass's head. The branch also carries two housekeeping commits (the handoff trim `8b40cdbb0` and the ledger move `2c3e829aa`) |
| Heads reviewed | Pass 1: the head before `9ca3bb6b3` (that commit was amended before the first push, so the pre-amend hash is not cited). Pass 2: `c8dc895b7`. Pass 3: `881047f62`. Corrections to pass 3: `9bb43e535`, `71a053ece`, `3a6b9a773`, then this ledger revision (the next commit) |
| Checks | Full suite 14,916 passed, 66 skipped, 2026-11-13, after the last change; documentation and backlog only, no code. The reviewers read the repo and git history but could not run scripts, so the 24-hit sweep breakdown was re-derived by hand in pass 3 |
| Reviewer | Headless sessions on `claude-sonnet-5-5`. Findings files and stream logs are local scratch (`.tmp/onboarding-docs-entry-code-review-N.*`, gitignored); findings and dispositions are recorded here |
| Disposition | **Stopped at exit 2, 2026-11-13: neither converged nor clean.** See Closure |

## Settled decisions

- The entry's named files (README first-task path, `common-workflows.md`, the
  three routers) read correctly at `1d8a47974`; the entry is removed, not
  described as fixed by this change.
- The shorthand `create → detail → audit → run` collapses the two audit gates and
  does not contradict them; edits to `CLAUDE.md` need architect-tier review, and
  `AGENTS.md` is a symlink to it.
- The `BACKLOG.md` recipes and the `RUNBOOK.md` iteration budget were filed, not
  fixed here, as separate classes of defect and queue records; the
  iteration-budget entry was fixed afterwards in `9f8c67e9b`.
- Restructuring the first-task path belongs to onboarding #510.

## Evidence (this session's runs)

- Provenance from git: at the `9c10d74ca` snapshot `common-workflows.md` already
  put the bare-plan audit before `detail`; the routers' recipe row ran `detail`
  before any audit and their iteration paragraph called `--iterate` "on by
  default for `create`/`detail`"; `31fdf2f22` fixed both.
- The command-sequence sweep (a `plan-tool detail` command that follows a
  `plan-tool create` within 80 lines with no `plan-tool completeness-audit`
  between, over fenced blocks of the tracked instructional documents) returned
  24 hits: 2 in `docs/how-to/roadmap.md`, 11 in `BACKLOG.md`, 11 independent
  examples. The script was session-local; the rule is recorded in the filed
  entry and the history record.
- `plan_tool/convergence.py` gives `DEFAULT_ITERATION_BUDGET_SECONDS = 1800`, and
  `plan-tool create --help` describes `--iteration-budget` as a debounced
  no-progress deadline.
- `completeness-audit --commit` refuses a dirty working tree
  (`plan_tool/cli/completeness_cmd.py`).

## Findings and dispositions

Pass 1 (two medium, four low, one info):

1. The record said the routers had no one-shot wording at the snapshot (they did:
   the recipe row said "one-shot; not `detail --iterate`") — `fixed 9ca3bb6b3`.
2. The record attributed "a missing detail file is coverage, not a design defect"
   to README and the routers; only `common-workflows.md`, `DIRECTIVES.md` Gate 1
   and `docs/how-to/pipeline/audit.md` say it — `fixed 9ca3bb6b3`.
3. `docs/ITERATION.md` was cited for `run --iterate` having no effect; only
   `docs/cli/run.md` says it — `fixed 9ca3bb6b3`.
4. The sweep missed `RUNBOOK.md`, whose closing audit-iteration line recommended
   `detail --iterate` without the opt-in qualifier — `fixed c8dc895b7`.
5. Present-tense status in the record — `fixed 9ca3bb6b3` (checks anchored to
   `1d8a47974`, the "(blocked on #508)" parenthetical dropped).
6. The README table's detail row dropped "not a clean audit", and the "Stopped at
   exit 2" label was outside the Retention rule's closure kinds — `fixed
   9ca3bb6b3` (label), `fixed 881047f62` (Retention now names it).
7. Trailing blank line at the end of the history file — `fixed 9ca3bb6b3`.

Pass 2 (one medium, two low, one info):

1. `docs/how-to/roadmap.md` skipped Gate 1 in its command list and in section 8 —
   `fixed 977b02cbb` (the `--commit` flags added then are corrected in pass 3,
   finding 1).
2. The README lead-in contradicted Retention — `fixed 881047f62`.
3. The `RUNBOOK.md` "narrow variant" sentence — `fixed 977b02cbb`; the stale
   300-second budget — `tracked`: `BUG_BACKLOG.md`, filed in `94c9b4171` and fixed
   afterwards in `9f8c67e9b`.
4. Present-tense status that goes stale — `fixed 881047f62` ("as of 2026-11-13",
   "open on 2026-11-13").

Pass 3 (one medium, seven low):

1. The roadmap how-to's `--commit` audits follow a stage that leaves the tree
   dirty, so Gate 2 would exit 2 — `fixed 9bb43e535`: the two audits drop
   `--commit`. This was a regression from pass 2's fix.
2. The budget entry understated its class (the "Bump the cap ... 600" advice and
   the tuning example assume the same low default; the third quoted passage is an
   illustrative string no code prints) — `fixed 71a053ece`.
3. `integrations/shared/DIRECTIVES.md`'s headless block listed `create` and
   `detail` side by side without the "not a stage sequence" note the routers
   carry — `fixed 9bb43e535`.
4. The record's list of independent examples and shorthand sites was incomplete —
   `fixed 3a6b9a773`.
5. The record said "archived plans" for what the sweep skipped, which was all of
   `docs/implementation-plans/` — `fixed 3a6b9a773`.
6. The two filed entries lacked a Verification line — `fixed 71a053ece`.
7. Wording: "one `completeness-audit`" was not true of every recipe; the record said
   `Iterate:` for blocks labeled `Iterate:` or `Iteration:`; a "left as is" item
   gave no reason — `fixed 71a053ece` and `3a6b9a773`.
8. The Retention bullet said "the four are not interchangeable" while older
   table rows carry other labels — `fixed 3a6b9a773` (rows closed before the rule
   keep their label).

## Closure

**Stopped at exit 2 on 2026-11-13; neither converged nor clean.** Each of the
three passes returned a medium finding, so the two-consecutive-low-yield-passes
condition never held. The mediums moved from errors in the history record
(pass 1) to an uncovered member of the entry's own class (pass 2) to a regression
in pass 2's own fix (pass 3), which is the shape `CLAUDE.md` calls the loop
auditing its own edits. Every finding is applied or dispositioned above, and no
fourth pass is planned unless the owner asks for one.
