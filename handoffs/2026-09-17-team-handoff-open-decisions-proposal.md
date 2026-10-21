# Team handoff: tracking-model decisions and remaining work

## Status

The decisions below are settled. Each names the live doc that holds its rule.
[Remaining execution work](#remaining-execution-work) lists what is still open.

Decisions 1–10 and 12 are the owner's. The parts of decision 11 marked *applied*
are defaults that can change without reopening a decision.

## Decisions

### 1. Tracking model

Jira is the system of record for assigned team work. `BACKLOG.md` and
`BUG_BACKLOG.md` stay in the repo as the assistant's continuous discovery and
triage log: any contributor's Claude session keeps filing new entries there.
The project lead periodically triages that log. For each item selected to
build, the lead opens the Jira ticket (assignment, status, priority) and, when
the work will run through `plan-tool`, authors the seed under `plan-seeds/`
naming that ticket. Promoting an entry leaves a stub (decision 8), and the board
has its own structure (decision 11). The backlog files feed the triage step;
they are not where an engineer picks up work.

One file per backlog item is not needed: engineers work assigned Jira tickets,
so they do not hand-edit `BACKLOG.md` day to day. The entry format and the
route, readiness, and tier labels stay, and they inform the lead's triage
judgment.

Concurrent appends to a shared file can collide on the next sequential id, and
a team means more concurrent appends. `tests/test_backlog_ids.py` fails a
duplicate, and [`docs/TRACKING.md`](../docs/TRACKING.md#adding-a-new-entry) §
"Adding a new entry" holds the rule and the command that picks the next id. The
test fails on the first test run over a tree that holds both entries: a pre-push
hook after a rebase or merge, or CI once one exists. A clean server-side merge
of two branches that add the same id runs nothing. A second test,
`tests/test_backlog_readability.py`, is separate on purpose: it refuses a
`BACKLOG.md` the id test cannot read completely (an id line outside
`**#N — title**`, an unclosed code fence, or no entries). Neither sees an id that
only a `**Closed #N — …**` record holds.

### 2. Remote of record: Bitbucket

The remote of record is Bitbucket. There is no CD or deployment pipeline:
nothing is published, and a release is a tagged commit plus a changelog entry
(decision 10). Install stays a git clone plus an editable install
(`CONTRIBUTING.md` § "Which `plan-tool` is running?").

The migration is a separate, one-time action, not a documentation change.
`origin` is `git@github.com:rupe120/plan-tool.git`, and `README.md` and
`CONTRIBUTING.md` give a GitHub clone URL. When the team stands up the Bitbucket
repo and pushes history over: update both clone-URL lines, decide and fill in
the required-approval, CI, and merge-queue settings `CONTRIBUTING.md` leaves
open, and re-point `origin`. Leave the historical GitHub links (PR #13, this
handoff's own citations) as they are; they record what happened there.

### 3. Committed evidence: keep committing every report

Every saved report (completeness, detail-reconcile, run-reconcile) keeps being
committed. The purpose is tool calibration over time: is round-to-convergence
falling, does a finding class recur across plans, did a directive change reduce
self-seeded findings. That is a trend question, and it needs the full series,
including intermediate rounds a PR would never cite. Committing only what a PR
cites would drop those data points unnoticed.

A raw corpus does not answer a calibration question by itself; it has to be
mined. The routine step is to periodically mine the raw reports and write a
durable conclusion, the pattern in `docs/evidence/roadmap-run-measurements.md`
and `docs/evidence/backend-recommendations.md`. The distilled doc is what gets
read and cited, and the raw corpus is its reproducibility backing. If repo size
becomes an operational cost at team scale, compact or archive already-distilled
raw reports; do not stop recording new ones.

### 4. Code-review tail rules: signal-based convergence, no round cap

Reuse the three exits the completeness-audit loop already uses, applied to
`/code-review` rounds. A fixed round cap is wrong: it can end a review because a
counter ran out, not because the signal said so, and a long trajectory can be
legitimate. What matters is whether the pattern across rounds trends toward
resolution or is flat or recurring.

1. **Converged.** A round is clean, or two consecutive rounds add only cosmetic
   findings. Signal-based, not count-based.
2. **Diagnosing your own edits, not the code.** New findings mostly describe the
   previous round's own fix. Do not stop: finish applying the current batch,
   then go execute.
3. **Spinning.** The same finding or region keeps resurfacing with no shrinking
   severity, or needs structural rework that cannot land inline. Stop and
   escalate, to the human operator or the orchestrating session. This targets
   the failure mode `CONTRIBUTING.md` § "Code review: where the craft gets
   taught" names ("same function, new bug every round? stop patching").

**No round limit.** Whether a round reviews the full pinned range or a
deliberately narrower focus is a judgment call each round, by the human operator
or the orchestrating session. What the tail converges on is the full scope,
through several full passes if needed, not a shrinking review window.

### 5. Checker independence: not required, at any tier

The checker never has to be a different person or a fresh session, at any tier:
the same author or session can author and check. A different checker is used
sometimes, purely for efficiency (parallelizing, or a fresh session skipping the
cost of re-deriving context), never because independence is itself a
requirement.

### 6. `CLAUDE.md` split

This applies only to the project's tracked `CLAUDE.md`. The owner's personal
`~/.claude/CLAUDE.md` is not team-shared and is untouched.

**Where the evidence moves.** Move the multi-paragraph measured incidents (the
arm-clustering measurement, the per-`change_type` test-ordering withdrawal, the
convergence-evaluator withdrawal, and similar) to pages under `docs/evidence/`,
the destination `docs/evidence/roadmap-layering-measurement.md` and
`docs/evidence/backend-recommendations.md` already use. `CLAUDE.md`'s own §
"Code comments" rule argues for this shape ("put it in the relevant doc… and
cite it from the code instead of inlining a long block"). Keep inline only the
rule and, where a decision is settled, a short "don't reopen — here's why"
verdict. The work is mechanical (verify nothing else links into the moved
sections) and is its own bounded pass, not a piecemeal edit.

**Who approves changes to the rules half.** `architect`-tier review, reusing
`docs/TRACKING.md`'s architect-tier trigger ("the canonical directives"). It is
enforced through pull-request review: an architect approves the PR before a
`CLAUDE.md` rules change merges. Request that review explicitly.

### 7. Persona tiers

With Jira as the assignment system, the labels serve the lead's triage first and
the engineer second: "a minimum of 5 ready starter items" and "when a newcomer
picks up work" are about the tickets the lead surfaces.

- **Tiers on work items only, not people.** Request architect-tier review
  explicitly for the high-stakes surfaces named in `docs/TRACKING.md`;
  `CONTRIBUTING.md` names the current Architect for that review.
- **Bucket C folds into the Readiness label; Buckets A, B, D, and E stay.**
  `BACKLOG.md`'s Triage framework table and "Readiness lens" section mark
  Bucket C retired, pointing at the `decision-needed` and `evidence-gated` values
  it duplicated. The other four buckets classify a different axis, the character
  of the work, that Route, Readiness, and Tier do not capture.
- **A minimum of 5 ready starter items.** The Architect keeps them replenished
  (`CONTRIBUTING.md` § "Architect: guarding the intent").
- **A newcomer drives a guided plan** after landing 1–2 `beginner`-tier direct
  items reviewed clean: an `experienced`-tier plan, with an Architect reviewing
  the plan and detail bundle before `run` (`CONTRIBUTING.md` § "Experienced:
  mentoring the assistant through a loop"). It reuses the `Getting started` →
  `Experienced` → `Architect` ladder.
- **The first Architect is the project owner (Josh Russo), the sole holder.**
  Future promotions: land some number of `plan`-route changes without the same
  `plan-correctness` finding recurring across rounds, the convergence loop's own
  "does the same finding recur" signal, and not a subjective call each time.

### 8. Promotion stubs

Promoting an entry leaves a stub that keeps its id and title and names the
ticket; the change that ships the work removes the stub.

- **Why.** The code and tests cite `BACKLOG #N` in 208 places, code comments cite
  bug entries by title, and a session that searches the backlog before filing
  must see that an item is already tracked. Removing the entry at promotion
  would break the citations and invite duplicate filing.
- **One home at a time.** The ticket holds the content and the stub holds only
  the pointer. A ticket that starts in Jira never gets a backlog entry.
- **The ticket holds the scope contract, and the seed carries a copy**, because
  `create` reads only the seed and the ticket is not in the repository. Older
  seeds and plans that say "remove the entry when this ships" mean the stub.
- **Unpromoted items keep the entry rule**: plan-authored while a plan is
  pending, removed when the work ships.
- **`BACKLOG.md` keeps no copy of the tracking rules.** Sections that would
  restate them are headings with pointers to `docs/TRACKING.md`.
- **Recorded in** `docs/TRACKING.md` § "Promotion stubs", and mirrored in
  `BUG_BACKLOG.md`, `SEED_FORMAT.md`, `integrations/shared/DIRECTIVES.md`, and
  `CLAUDE.md` § "Authoring hygiene and anti-creep".

### 9. Roadmap boundary

The `roadmap` verb and Integration are experimental, owner-tracked work and stay off the
team's queue. The team's part of plan-tool comes first; the owner works on the
rest when able.

| Surface | How the boundary is marked |
| --- | --- |
| Code and docs | Request owner review explicitly for roadmap-specific changes. |
| `BUG_BACKLOG.md` | Roadmap-owned entries live under `## ROADMAP`, each with a `Severity` line. |
| `BACKLOG.md` | Items the roadmap arc routes are not promoted. |
| Jira | No roadmap tickets. A `roadmap` component marks a team ticket that depends on owner work. |

- **Roadmap-owned** follows the responsibility-based definition and case table
  in `docs/TRACKING.md` § "Roadmap boundary".
- **Mixed entries stay with the team**, because a defect in shared code is team
  work.
- **Recorded in** `docs/TRACKING.md` § "Roadmap boundary".

### 10. Release process

- **Versioning.** Semantic versioning; below 1.0 a minor bump is a feature, a
  CLI-surface change, or a persisted-contract change, and a patch is fixes only.
- **Changelog.** One `scriv` fragment per ticket in `changelog.d/`, collected
  into `CHANGELOG.md` at release. A change with no user-visible effect skips the
  fragment and carries the `no-changelog` label.
- **A release** is a tagged commit on `main` plus a changelog entry, cut in six
  steps. The Jira board carries no Fix Version; the release check uses resolution
  dates and `changelog.d/` (reversed 2026-09-23).
- **Deliberately not decided:** publishing to a package index, scripting the
  steps, and backport branches.
- **Recorded in** `docs/RELEASING.md`, `changelog.d/README.md`, and
  `CONTRIBUTING.md`.

### 11. Jira board structure

*Decided by the owner:* one project for the team's part of plan-tool; Kanban; a
simple priority rule; branch, commit, and pull-request naming that allows one
ticket to span many commits and one commit to serve several tickets; and
`plan-tool jira` stays a supported feature, because architects use its story
export to hand plans to teams on other projects.

*Applied as defaults:* the priority mapping (Highest for a blocked user or broken
release, High for `BUG`, Medium for `RISK` and features, Low for `MINOR`, with
the board order as the ranking); an ordered, first-match issue-type table (an
`evidence-gated` item is a Spike even when it is a `RISK` entry); a
`needs-triage` label for tickets filed directly in Jira; and a ticket
description that is the whole entry.

*Reversed 2026-09-23 (owner):* the board keeps four statuses (To Do, In Progress,
In Review, Done), and labels and comments carry the rest. Needs Decision, Plan
Review, WIP limits, a Spike type, and the `Tier`, `Route`, and `Backlog ref`
fields are not configured; `docs/TRACKING.md` § "Deliberately not configured"
holds each reason and the condition that would add it.

**Recorded in** `docs/TRACKING.md` § "Jira board", and in `CONTRIBUTING.md` §
"Picking work" and § "Commits".

### 12. `plan-tool --version`

The global flag prints `plan-tool <version>` and exits 0 without a subcommand. In
a source checkout it reads `pyproject.toml` (only when that file declares
plan-tool); otherwise it reads the installed package's metadata; when neither is
readable it prints `unknown` and does not guess.

- **Why not metadata alone.** In an editable install, metadata keeps reporting the
  old version after `pyproject.toml` is bumped, and clone plus editable install is
  how this tool is distributed.
- **Side effect, accepted.** `--v`, `--ve`, and `--ver` do not abbreviate
  `--verbose`, because they also match `--version`. `-v`, `--verbose`, and
  `--verb` work. The changelog fragment says so, and tests pin the choice.
- **Recorded in** `docs/reference/commands.md`, `CONTRIBUTING.md` § "Which
  `plan-tool` is running?", `docs/RELEASING.md`, and the fragment
  `changelog.d/plan-tool-version-flag.md`.

## Considered and not taken

| Option | Why not |
| --- | --- |
| Bulk-import the backlog into Jira | A second backlog that goes stale; it contradicts decision 1. |
| Scrum sprints | Work is drained by severity and triaged continuously; the owner chose Kanban. |
| Separate bug and feature projects | It splits one priority queue in two. |
| A sync between the backlog and Jira | Promotion is a manual copy by the lead; a sync adds a permanent maintained surface. |
| Removing the entry at promotion | It breaks the `BACKLOG #N` citations and invites duplicate filing (decision 8). |
| `allow_abbrev=False` to avoid the `--ver` ambiguity | It changes every global flag's abbreviations for one flag's sake. |
| Package metadata alone for `--version` | Stale in an editable install after a version bump. |
| `towncrier` | `scriv` is Markdown-native and simpler. |
| Editing a roadmap plan's detail file to fix a stale citation | An edit makes the plan's saved audit reports stale. |

## Remaining execution work

Each item names the decision it belongs to.

For the owner:

- **Bitbucket migration** (decision 2): done — the repo is standing on
  Bitbucket Cloud, history moved, `origin` fetches from it, both clone-URL
  lines point at it, and `bitbucket-pipelines.yml` runs the suite on pull
  requests and on `main`. **Still open, and only settable in the Bitbucket
  UI:** the required-approval count and the merge-queue setting on `main`.
- **`CLAUDE.md` evidence extraction** (decision 6): move the multi-paragraph
  measurements out to `docs/evidence/`.
- **Bucket C to readiness, per entry** (decision 7): check that each entry the
  "Readiness lens" section once cited as bucket C (for example its "Theoretical"
  list) carries the right `readiness` value.
- **Finish the Jira configuration** (decision 11) through
  [`2026-09-23-jira-management.md`](2026-09-23-jira-management.md), which owns
  the ticket seeding and the recurring management loop.
- **Review the three `CLAUDE.md` commits** (`b0b21e8c`, `8ecef0c2`, `bdd8e6b1`)
  in the tracking-model PR (#14), since that file's own rule requires Architect
  review.
- **Choose the first release version and tag** (decision 10): done — tagged
  `v0.1.0`. `scripts/release.py` (`docs/RELEASING.md`) now derives every
  later release's version from the pending `changelog.d/` fragments.
- **Merge the stack in order:** #14, then #15, then #16. `origin/main` carries the
  `#404` duplicate until #16 merges.
- **Check `#424` and `#425` against the in-flight branch.**
  `origin/codex/roadmap-feedback-batch-revision` holds `#424`, which the renumber
  skipped, and both `#404` entries. Any id that branch files above 424 must be
  checked against `#425`.

For the roadmap owner:

- **One stale citation** in the detail file
  `docs/implementation-plans/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md`:
  line 77 cites `BUG_BACKLOG.md:275`, an entry that now sits under `## ROADMAP`.
  Fix it at that plan's next re-audit, because editing the detail makes its saved
  reports stale.

Candidate entry, not filed: `tests/test_cli.py::test_no_existing_tests_were_modified`
compares against `main` with a hardcoded allowlist from an old plan, so it skips
on every branch that edits other tests and guards nothing there. Removing it, or
replacing the allowlist, is a small direct change.
