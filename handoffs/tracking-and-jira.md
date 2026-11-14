# Tracking, Jira and backlog

Work tracking, the Jira board and tickets, backlog guards, branch hygiene and the settled tracking decisions. Each section below is one change or route in this workstream, ordered by the date it was opened; new work in the workstream appends a section here instead of creating a file (`README.md` § "Naming").

| Section | Opened |
| --- | --- |
| [Team handoff: tracking-model decisions and remaining work](#team-handoff-tracking-model-decisions-and-remaining-work) | 2026-09-17 |
| [Unpushed `main` code review](#unpushed-main-code-review) | 2026-09-21 |
| [the `BACKLOG.md` id guard](#the-backlogmd-id-guard) | 2026-09-23 |
| [first Jira tickets, the short ticket format, and the `run` merge guard](#first-jira-tickets-the-short-ticket-format-and-the-run-merge-guard) | 2026-09-24 |
| [general branch cleanup](#general-branch-cleanup) | 2026-09-29 |
| [Jira-grade retirement execution and review](#jira-grade-retirement-execution-and-review) | 2026-11-03 |

## Team handoff: tracking-model decisions and remaining work

*Opened 2026-09-17.*

### Status

The decisions below are settled. Each names the live doc that holds its rule.
[Remaining execution work](#remaining-execution-work) lists what is still open.

Decisions 1–10 and 12 are the owner's. The parts of decision 11 marked *applied*
are defaults that can change without reopening a decision.

### Decisions

#### 1. Tracking model

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

#### 2. Remote of record: Bitbucket

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

#### 3. Committed evidence: keep committing every report

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

#### 4. Code-review tail rules: signal-based convergence, no round cap

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

#### 5. Checker independence: not required, at any tier

The checker never has to be a different person or a fresh session, at any tier:
the same author or session can author and check. A different checker is used
sometimes, purely for efficiency (parallelizing, or a fresh session skipping the
cost of re-deriving context), never because independence is itself a
requirement.

#### 6. `CLAUDE.md` split

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

#### 7. Persona tiers

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

#### 8. Promotion stubs

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

#### 9. Roadmap boundary

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

#### 10. Release process

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

#### 11. Jira board structure

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

#### 12. `plan-tool --version`

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

### Considered and not taken

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

### Remaining execution work

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
  [`docs/how-to/jira-management.md`](../docs/how-to/jira-management.md), which owns
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
  `docs/implementation-plans/archive/plan-details/roadmap-decision-settlement/07-document-settlement-route-retire-every.md`:
  line 77 cites `BUG_BACKLOG.md:275`, an entry that now sits under `## ROADMAP`.
  Fix it at that plan's next re-audit, because editing the detail makes its saved
  reports stale.

Candidate entry, not filed: `tests/test_cli.py::test_no_existing_tests_were_modified`
compares against `main` with a hardcoded allowlist from an old plan, so it skips
on every branch that edits other tests and guards nothing there. Removing it, or
replacing the allowlist, is a small direct change.

## Unpushed `main` code review

*Opened 2026-09-21.*

### Summary

| Field | Value |
| --- | --- |
| Review range | `origin/main..main`, then each round's own fix commits |
| Range base (origin/main) | `f0f4c3ab` |
| Round 1 head (initial review target) | `ded951aa` |
| Review purpose | Preserve the finding explanations, dispositions and settled decisions below |
| Checks run | `/code-review` (report-only, no `--fix`), effort `high` every round; final full unit/component suite: 12365 passed, 158 skipped |
| Reviewer/session | `code-review-loop` skill |
| Current disposition | **Converged** after 4 rounds — see Convergence status |

The ledger covers the 69 commits on `main` not yet on `origin/main`, edited in
place across rounds (convention: `handoffs/README.md` § "Review ledgers").
Reports carried no severity or `CONFIRMED`/`PLAUSIBLE` tag, so none is recorded
below. Finding ids are `R<round>-<n>`; round 2 is the full report (its partial
report is R2P). All 15 round-1 findings cluster in the roadmap
terminal-disposition/lifecycle machinery (`roadmap.py`, `roadmap_cmd.py`,
`roadmap_revision_run.py`, `roadmap_versions.py`, `roadmap_candidate.py`) and
`ROADMAP_FORMAT.md`.

### Settled decisions (hand to the next reviewer)

*Compression note (added 2026-11-13; the ledger was compressed 2026-09-29): this ledger had no original settled-decisions list; the list below was assembled from its own declined and refuted findings.*

- Materialize exception tracking uses the `materialize_disposition_emitted`
  tag on the exception object (`d795b3f6`), accessed via
  `_materialize_disposition_emitted` / `_mark_materialize_disposition_emitted`
  (`8004bd95`). A superseding exception is a distinct failure and gets its own
  "unexpected-error" disposition.
- `run_roadmap`'s writer-teardown `OSError` (R2-1 / R4-1) is pre-existing and
  needs a disposition-contract decision; it is filed in `BUG_BACKLOG.md`
  (`ab04f4e6`), not patched in-loop.
- `RoadmapEnvironmentalError` (unreadable-but-existing template) stays rc=1
  regardless of timing; pinned by
  `test_escaping_environmental_prompt_read_failure_returns_incomplete`.
- The pre-existing "stale writer token" comment in `roadmap_revision_run.py`
  keeps its original wording: CLAUDE.md says match the terse style when
  touching a pre-rule module rather than extending it.
- `run_local_feedback_revision` does not consult `roadmap_stage_started`.
- Comment-length terseness is no longer an audit axis (self-seeded-finding
  rule).

### Fix guidance (applies to every disposition in this ledger)

A change that closes a finding as `fixed` must:

- Be true and proportional to the intent of the code it touches — no bigger,
  smaller, or more general than the defect calls for.
- Apply the smallest proof that completes the intent, not the eventual
  capability the finding gestures toward.
- Stay at the altitude the finding names (do not fold detail-level mechanics
  into a plan/bare-level concern or the reverse).
- Run an identifier + vocabulary sweep for sibling sites, then check the remedy
  against the goal of the bug rather than replaying one patch verbatim at every
  match.

### Round 1 — `origin/main..main` (`f0f4c3ab..ded951aa`, 69 commits)

- **R1-1 — preflight prompt errors marked "stage started"** (`roadmap.py`): a missing prompt template returned rc=1 (retryable) instead of rc=2. **Disposition:** fixed 02463e41 — `_preflight_prompt_error` marks `False` at origin, guard fills only when absent; tests `test_render_stage_prompt_missing_template_marks_stage_not_started`, `test_render_stage_feedback_prompt_missing_template_marks_stage_not_started`, two `TestStageRunGuard` cases.
- **R1-2 — stale writer token escapes revision publish** (`roadmap_revision_run.py`): `RoadmapWriterGuardError` uncaught instead of `publication-failed`. **Disposition:** fixed a82cb7b4 — added to the `except OSError` clause; `test_publication_failed_when_publish_raises_stale_writer_token`.
- **R1-3 — materialize preflight lifecycle can raise `OSError`** (`roadmap_cmd.py`): nested `except RoadmapError` missed `RunLogWriter.start()` errors. **Disposition:** fixed a4359236 — `(RoadmapError, OSError)`; `test_materialize_preflight_lifecycle_survives_a_broken_run_log`.
- **R1-4 — writer-guard teardown failure after success gets no disposition** (`roadmap_cmd.py`). **Disposition:** fixed a4359236 — flags `owned_call_entered`/`owned_call_returned` (superseded by the R2-2 tag); `test_materialize_emits_unexpected_error_when_writer_teardown_fails_after_success`.
- **R1-5 — second contradictory lifecycle from outer `RoadmapError` handler** (`roadmap_cmd.py`, latent). **Disposition:** fixed a4359236 — re-raises while inside the owned call; `test_materialize_does_not_double_report_a_roadmap_error_from_the_owned_call`.
- **R1-6 — trailing `except BaseException` omits the disposition emit** (`roadmap_cmd.py`). **Disposition:** fixed a4359236 — merged into the `except Exception:` clause; `test_materialize_owned_emits_disposition_for_a_baseexception_escape`.
- **R1-7 — `_ordered_stage_collections` hand-copies the collection table** (`roadmap_candidate.py`): drift from `stage_row_collections()`. **Disposition:** fixed 08000ee5 — delegates; `test_ordered_stage_collections_matches_the_shared_dispatch_table`, `test_ordered_stage_collections_refuses_an_unsupported_artifact_type`.
- **R1-8 — unreachable `record.version_id` check** (`roadmap_versions.py`). **Disposition:** fixed 4c4551f4 — deleted; sibling call sites swept, none have it.
- **R1-9 — duplicated category-to-disposition mapping** (`roadmap_cmd.py`): `_cmd_roadmap_revise_feedback` duplicated `_terminal_disposition()`. **Disposition:** fixed 7cd1c19b — reuses it and `_result_return_code`; parametrized over all 4 categories plus an interrupted-skips-emission test.
- **R1-10 — six copies of the preflight-refusal pairing** (`roadmap_cmd.py`). **Disposition:** fixed 0bc732a9 — `_refuse_materialize_preflight`.
- **R1-11 — shared digest helpers inlined at five sites** (`roadmap_versions.py`, `roadmap_candidate_context.py`). **Disposition:** fixed 45d54826 — `VERSION_ARTIFACT_KEYS` and `sha256_digests()` restored verbatim from `origin/main`.
- **R1-12 — duplicated dict-by-id diff loops** (`roadmap_candidate.py`). **Disposition:** fixed 5b9e549a — `_diff_by_id`.
- **R1-13 — stale "later roadmap steps" sentence** (`ROADMAP_FORMAT.md`), violating forward-looking docs. **Disposition:** fixed 3e6f3c55 — deleted.
- **R1-14 — opposite `getattr` defaults for `roadmap_stage_started`** (`roadmap_cmd.py`). **Disposition:** fixed b828499c — `_roadmap_stage_started(exc, default=...)`; pinned by `test_escaping_disk_failure_returns_incomplete_not_usage`, `test_escaping_preflight_error_emits_refusal_terminal_status`.
- **R1-15 — no-op `try/except: raise`** (`roadmap.py`). **Disposition:** fixed 4c4551f4 — deleted.

### Round 2 — partial report (conventions angle only; `ded951aa..HEAD`, fixes `d1a10a70`..`b828499c`)

All one class: comments added while fixing round 1 ran past "a line or two". This partial result was wrongly taken as the whole round (see Convergence status).

- **R2P-1..R2P-5 — over-long comments/docstrings** in `_roadmap_stage_started`, the `except OSError` comment (`roadmap_revision_run.py`, pre-rule module: revert to original wording), `_stage_run_guard`, the `owned_call_*` comment, `_ordered_stage_collections`. **Disposition:** fixed 6cade212 — each trimmed to 1-2 lines.
- **R2P-sweep — 7 uncited instances** across round-1 fix commits (revise-feedback and materialize comments, `except BaseException:` comment, docstrings of `_refuse_materialize_preflight`, `_preflight_prompt_error`, `_diff_by_id`). **Disposition:** fixed 6cade212.

### Round 2 — full report (`ded951aa..HEAD`)

Refuted leads: R1-8 and R1-15 deletions are genuinely redundant/no-op; R1-9's refactor is exactly equivalent for all 4 `LocalRevisionResult.category` values.

- **R2-1 — `run_roadmap` teardown `OSError` replaces a successful result** (`roadmap.py`): `return _run_roadmap(...)` inside `with _roadmap_writer_owner(...)` turns a finished run into `error`/rc=1. **Disposition:** tracked `BUG_BACKLOG.md` (`ab04f4e6`; no numeric id cited) — pre-dates the range; `ROADMAP_FORMAT.md`'s matrix has no row for "completed, then teardown failed", so the fix is a contract decision.
- **R2-2 — flags cannot tell a superseding exception apart** (`roadmap_cmd.py`): `_roadmap_command_lifecycle`'s unguarded `run_end(...)` can replace the pending exception. **Disposition:** fixed d795b3f6 — `materialize_disposition_emitted` tag on the exception replaces the flags.
- **R2-3 — post-return `RoadmapError` treated as preflight (rc=2)** (`roadmap_cmd.py`, latent). **Disposition:** fixed d795b3f6 — `test_materialize_treats_a_fresh_roadmap_error_after_entry_as_unexpected`.
- **R2-4 — `_rebind_failure_error` forwards only a truthy `roadmap_stage_started`** (`roadmap.py`). **Disposition:** fixed de16b43d — forwards whenever present; `TestRebindFailureError` (3 tests).
- **R2-5 — rc literals in `_result_return_code` duplicated** (`roadmap_revision_run.py`; shared import would be circular). **Disposition:** fixed — test-only, `test_result_return_code_matches_roadmap_cmd_rc_constants` (moved in R4-14).
- **R2-6 — hand-listed `isinstance` tuple** (`roadmap_candidate.py`). **Disposition:** fixed 0e32dcdf — `isinstance(artifact, RoadmapArtifact)`.
- **R2-7 — hand-looped digests at 4 sites** (`roadmap_candidate_run.py`, `roadmap_candidate_review.py`): the R1-11 sweep stopped early. **Disposition:** fixed c8e12584 — repointed to `sha256_digests`; no other site remains.
- **R2-8 — timing-inferred "already dispositioned" state** (`roadmap_cmd.py`): root cause of R2-2, R2-3, R2-11. **Disposition:** fixed d795b3f6 — closed by the tag redesign.
- **R2-9 — `_roadmap_stage_started` docstring 11+ lines.** **Disposition:** refuted — stale snapshot; 6cade212 (R2P-1) already trimmed it. Source label: `no_change_needed`.
- **R2-10 — `render_local_revision_prompt` missing-template raise not marked** (`roadmap_revision_run.py`, latent). **Disposition:** declined — its outcome model never reads `roadmap_stage_started`, so wiring it builds for a capability nothing consumes; revisit only if that flow adopts the convention.
- **R2-11 — outer net swallows a dispositioned error** (`roadmap_cmd.py`, latent). **Disposition:** fixed d795b3f6 — the net re-raises a tagged exception; `test_materialize_owned_does_not_let_its_outer_net_swallow_a_dispositioned_error`.

Suite after round 2 fixes: 12365 passed, 158 skipped.

### Round 3 — `b828499c..HEAD` (`6cade212`, ledger update `bc7305ad`)

No executable line changed. It excluded the round-2 full-report fixes, so it is not convergence evidence.

- **R3-1 — ledger sweep count typo** ("4 more instances", 7 listed). **Disposition:** fixed — corrected to 7 (recorded in R2P-sweep).

### Round 4 — `b828499c..HEAD` (`d795b3f6`, `0e32dcdf`, `c8e12584`, `de16b43d`, `ab04f4e6`, `7aee4e10`)

14 findings; 10 describe the loop's own prior edits (self-seeded-finding shape).

- **R4-1 — teardown defect fixed only at materialize, not `run_roadmap`** (`roadmap.py`). **Disposition:** declined — reaffirms the `ab04f4e6` entry: the lost `RoadmapResult` cannot be recovered once `__exit__` discards it, so the fix is a disposition-contract decision (new matrix row or explicit rc=1 acceptance); no new information.
- **R4-2 — `run_end()` can replace a tagged exception with an untagged one** (`roadmap.py`, untested). **Disposition:** declined — intended: a superseding exception is a distinct failure with its own disposition; root cause is pre-existing shared infrastructure, same class as R4-1.
- **R4-3 — tag read/set via hand-typed `getattr`/`setattr`** (`roadmap_cmd.py`). **Disposition:** fixed 8004bd95 — `_materialize_disposition_emitted` / `_mark_materialize_disposition_emitted` at all four sites.
- **R4-4 — `_roadmap_stage_started` docstring lost its why.** **Disposition:** fixed 8004bd95.
- **R4-5 — new 5-line `owned_call_entered` comment.** **Disposition:** fixed 8004bd95 — 2 lines.
- **R4-6 — `_preflight_prompt_error` lost the `_stage_run_guard` fill-if-absent reason** (`roadmap.py`). **Disposition:** fixed a9dd7d90.
- **R4-7 — reverted "stale writer token" comment lacks a pointer to `publish_revision_candidate`** (`roadmap_revision_run.py`). **Disposition:** declined — contradicts R2P-2 (match the terse style in pre-rule modules rather than extend); the gap pre-dates the range.
- **R4-8 — bindings hashed twice from one `content`** (`roadmap_candidate_review.py`, `roadmap_candidate_run.py`): pre-existing, no correctness impact. **Disposition:** pending — not filed; a numbered `BACKLOG.md` slot costs more than the item is worth. Do a bind-once-reuse pass when either function is next touched. (Source: "noted, not filed"; set to `pending` by the owner 2026-09-29.)
- **R4-9 — two outer except blocks reimplement "emit unless dispositioned"** (`roadmap_cmd.py`). **Disposition:** fixed 8004bd95 (via R4-3) — the remaining 3-vs-2 outcome difference is genuine.
- **R4-10 — `BaseException` handler comment lost why a fixed "unexpected-error" string is emitted** (persisted record must not expose exception text). **Disposition:** fixed 8004bd95.
- **R4-11 — revise-feedback comment lost the shared-mapping reason.** **Disposition:** fixed 8004bd95.
- **R4-12 — `_diff_by_id` docstring lost the two-part ordering contract** (`roadmap_candidate.py`). **Disposition:** fixed b87d8e7c.
- **R4-13 — dead imports `ComponentsArtifact`, `ConstraintsArtifact`, `DomainArtifact`** (`roadmap_candidate.py`; ruff F401 is disabled for an unrelated re-export pattern). **Disposition:** fixed b87d8e7c.
- **R4-14 — rc-drift test in the wrong mirror file** (`tests/cli/test_roadmap_cmd.py`). **Disposition:** fixed 8b782515 — moved to `test_roadmap_revision_run.py`.

Suite after round 4: 12365 passed, 158 skipped.

### Out-of-range / recall-mode findings

_(none)_

### Convergence status

**Converged after 4 rounds.** An earlier "Converged" call, made after round 3
on the round-2 partial report alone, was premature and is retracted: the full
round-2 report arrived afterward and held real logic fixes (the materialize
tag redesign, the rebind fact-forwarding bug, a missed duplication sweep, the
rc-drift test), one backlog filing (R2-1) and one declined item (R2-10).

Final triage: round 4's 14 findings resolve as 5 fixed genuine hygiene/accessor
gaps, 6 fixed under-trimmed or over-trimmed comments, 2 declined with reasoning
(R4-1 reaffirms a documented backlog tradeoff; R4-7 is settled by a rule a
prior round correctly applied), and 1 pending (R4-8; R4-2, R4-9 fall
in the counts above per the source). Ten of the 14 describe the loop's own
prior edits, the self-seeded-finding shape, whose stated response is to finish
applying and stop auditing that dimension. No round past round 2 found a new
runtime correctness defect; every later round was consistency polish on the
loop's own edits, which is the convergence signal here, not a zero-finding
round. The loop stops; no round 5.

Open follow-ups: `BUG_BACKLOG.md` entry for the `run_roadmap` teardown
disposition contract (R2-1 / R4-1, `ab04f4e6`), pending a contract decision;
R4-8 bind-once-reuse pass, unfiled.

Lesson: treat a background `/code-review` hand-back as provisional until the
launching call itself reports completion; a partial finder-angle result can
arrive first and read as complete.

## the `BACKLOG.md` id guard

*Opened 2026-09-23.*

| Field | Value |
| --- | --- |
| Change | `tests/test_backlog_ids.py`; the id-selection rule and command in `docs/TRACKING.md`; the `#404` → `#425` renumber; `BACKLOG #233` closed |
| Branch | `fix/backlog-entry-id-uniqueness`, stacked on `cleanup/backlog-drift-and-version-flag` (`443fa912`); pull request #16 |
| Review range | `443fa912..7776e7a6`; later commits on the branch are follow-ups the review turned up |
| Reviewer | Two `/code-review` sessions, run one after the other |
| Checks | Full suite on the branch tip: 13389 passed, 190 skipped. On the real `BACKLOG.md`, a duplicated id fails only `test_backlog_entry_ids_are_unique` (in `tests/test_backlog_ids.py`); a malformed opener or an unclosed fence fails only `test_backlog_is_fully_readable_by_the_id_guard` (in `tests/test_backlog_readability.py`) |
| Disposition | All in-diff findings are fixed or declined. Out-of-range: A is `tracked` in `#308`; B, C and D are `fixed` (`6115a097`, `dabc00f0`, `4e1e5a71`); E is `pending` |

### Settled decisions for the next reviewer

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

### Round 1: 13 findings, all fixed

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

### Round 2: 13 in-diff findings

Commits: `b02e3791` test, `7776e7a6` docs. Twelve of the 13 describe round 1's
own edits; #5 is a missed site round 1 had declined.

| # | Finding | Disposition |
| --- | --- | --- |
| 1 | `git log -p` prints no diff for a merge, so ids introduced only by a merge are invisible; 19 ids on `origin/main`, `#399`–`#401` among them, are live | fixed `7776e7a6`: `-m`, verified in the case matrix |
| 2 | The command reads only committed history, so a session's uncommitted entry is not counted | fixed `7776e7a6`: adds `git grep` over the working tree |
| 3 | A hard-wrapped prose line starting `**#97** …` fails `blind_spots` with a misleading message; 107 historical versions | fixed `b02e3791`: a malformed opener needs a dash or colon after the id. Replayed over 583 versions: 0 flagged. The message says to rewrap |
| 4 | The collision-dating recipe breaks on an apostrophe in the title and does not say which date decides | fixed `7776e7a6` |
| 5 | `docs-and-onboarding.md` § "developer docs and work tracking" still cites the removed `#233` as open | fixed `7776e7a6`: a pointer to the check; the rest of that frozen record is untouched |
| 6 | "Per-finding dispositions are in the fix commit messages" is false for this branch | fixed in the commit that adds this ledger |
| 7 | "Ids have collided 23 times … most recently #404" misstates the measurement | fixed `7776e7a6`; the figure was then dropped from `CONTRIBUTING.md` because it goes stale |
| 8 | `_explain` runs in no test; a stub's title prints with its pointer; two mutants stay green | fixed `b02e3791` |
| 9 | The docstring names one `**Closed …**` shape; the file has two | fixed `b02e3791` (docstring, parametrized test), `7776e7a6` (decisions log) |
| 10 | `blind_spots` widens the deleted `#233` entry's one-fact fence | `fixed 5dfe7839`: the owner chose to split it from the id test and keep it, so the id test is back to one fact and the readability check is its own file with its own scope statement. The decisions log records the split |
| 11 | The decisions-log record departs from that file's conventions | fixed `7776e7a6`: now `### #233` under "Shipped records" |
| 12 | The Id item packs four contracts into one bullet | fixed `7776e7a6` |
| 13 | An unclosed fence that a later bare closer pairs with is not reported | declined: CommonMark parses it identically, and flagging it would flag valid documents. Named as a residual in the docstring (`b02e3791`) |

### Out of range (recall mode, not part of either round's core count)

| # | Finding | Evidence | Disposition |
| --- | --- | --- | --- |
| A | `jira_grade.fenced_spans` reads a line like `` ```inline``` wrapped text `` as an unclosed fence opener that swallows the rest of the document; `scope_fence._fenced_code_spans` does not | Reproduced. `plan_tool/review.py` imports the helper for two parsers that are not Jira-grade code (`_find_redirect_heading` at line 5985, `_split_audit_fix` at line 7125). The swap the review suggested was tried in a scratch edit of `review.py` and reverted: it fails `test_indented_citation_fence_protects_the_boundary`, because `review.py` deliberately accepts fences indented past three spaces and `scope_fence` allows only three. The two scanners are wrong in opposite directions, so there is no drop-in | `tracked #308` (`9675112b`): its **Allowed reorganization** now says the relocation keeps the indentation behavior and decides the inline-code flaw |
| B | `docs/history/backlog-decisions.md` links to 12 plans under `../implementation-plans/2-*.md` that now live in `../implementation-plans/archive/` | Checked: 12 broken relative links (lines 23–34, 74, 75), each resolving under `archive/`. Enumerating the file also found one stale inline path, `docs/implementation-plans/2-roadmap-01-domain-constraints.md`, now under `archive/` | `fixed 6115a097`: the 12 links and the inline path repointed, each target checked; the other 6 links, the anchored link, and the two live inline paths already resolved |
| C | 9 links in three other files point at plans that now live under `archive/`: 4 in `handoffs/2026-09-08-authored-artifact-structure-versioning.md`, 3 in `roadmap-aidlc.md` § "deliver AI-DLC-compatible roadmap integration", 2 in `docs/explanations/audit-pass-persistence.md` | Found by enumerating B's class across every tracked `.md` outside the archives and saved reports; each target exists under `archive/` | `fixed dabc00f0`: path-only (each changed line differs by one inserted `archive/`); the two handoffs are dated records, edited on the owner's explicit request. One test, `test_non_stage_brief_drift_handoff_records_delivery_and_367_closeout`, pinned the old link string and was updated in the same commit; no other test names any of the 18 repointed targets |
| D | 2 links in `handoffs/2026-09-08-authored-artifact-structure-versioning.md` (lines 575, 6480) point at `docs/ROADMAP_EVIDENCE_V1_RETIREMENT.md` | The doc was renamed, with no content change, to `docs/history/roadmap-evidence-v1-retirement.md` by `79a8e131` (the PR #13 restructure), so no `archive/` path exists: a moved doc, not a moved plan | `fixed 4e1e5a71`: both links repointed; line 575's label, which was the literal old path, changed with its target |
| E | By my count about 144 broken relative links in 30 tracked `.md` files, outside the archives and saved reports | 26 sit in intentionally fictional test fixtures (`tests/fixtures/reformat/`); 10 are in `RUNBOOK.md` (e.g. `docs/ROADMAP_WALKTHROUGH.md`); many are frozen plan-detail files whose edit would make their saved audit reports stale. Not classified further | `pending`: a link guard, or a triage of the live-doc share, is the owner's call |

### Exit

No further round is scheduled. Round 2's findings mostly described round 1's own
edits, which is the "the loop is auditing your own edits" exit in `CLAUDE.md`,
and three were real defects in round 1's remedies. The two properties were
therefore re-verified directly: the id command against a case matrix, and the
readability check against every historical version of `BACKLOG.md`. Another
round is the owner's call.

## first Jira tickets, the short ticket format, and the `run` merge guard

*Opened 2026-09-24.*

This handoff records where the first `IPPT` tickets stand, the ticket format and
tier rules settled while writing them, and the owner decisions still open. It is
the entry point for the next session. The policy lives in
[`docs/TRACKING.md`](../docs/TRACKING.md); the promotion procedure and the
recurring loop live in [`docs/how-to/jira-management.md`](../docs/how-to/jira-management.md).
This file does not repeat either.

### State on 2026-09-25

| Surface | State |
| --- | --- |
| Repository | `origin/main` last contained `bc212011` of this work. Everything after it is local and unpushed (`git log origin/main..HEAD`): this handoff's first commit (`34341f8c`), the `jira-ticket` skill and its two lint-fix rounds (`73ef318b`, `aeba15f8`, `64d5c8ef`), the `IPPT-8` promotion stub (`7db46ee9`), and the commit that records this state. |
| Last full suite | 13788 passed, 189 skipped (2026-09-25), on the tree through `73ef318b`. The 2026-09-24 run through `9e504d6e` (the merge guard) was 13787 passed, 190 skipped; the one-test difference is not investigated. Later commits change only `.claude/skills/jira-ticket/` and one `BUG_BACKLOG.md` stub; on the stub, `test_backlog_ids.py`, `test_backlog_readability.py`, `test_data_contract.py`, `test_drift_detection.py`, and `test_roadmap_format.py` passed (348 tests). |
| Jira `IPPT` | Seven tickets, all in To Do (below). `IPPT-3` was created, then withdrawn and deleted; its number is not reused. |
| Beginner floor | 5 of 5, met 2026-09-25. The saved-filter query returns `IPPT-1`, `IPPT-2`, `IPPT-4`, `IPPT-5`, and `IPPT-8`. |
| To Do rank | `ORDER BY Rank ASC` returns `IPPT-1`, `2`, `4`, `5`, `6`, `7`, `8` (2026-09-25): creation order, so no reordering of To Do is visible. |
| Jira connector | Reads and writes work through `twg` and the `mcp__atlassian__` tools (2026-09-25). On 2026-09-24 one connector refused a read of `IPPT` and board `3971` because it could not verify that its saved default site belongs to the organization's site; the cause is not recorded. If a call is refused, report it and do not retry a write. |

| Ticket | Type | Priority | Tier label | What |
| --- | --- | --- | --- | --- |
| `IPPT-1` | Bug | High | `beginner` | `plan-tool sweep` can crash printing its report when the repository path goes through a symlink. |
| `IPPT-2` | Bug | High | `beginner` | `create` and `reprocess` tell users to run `plan-tool completeness`, which does not exist. |
| `IPPT-4` | Task | Medium | `beginner` | 13 broken links in `RUNBOOK.md` and two dated handoffs (backlog #426). Every target is known. |
| `IPPT-5` | Bug | Low | `beginner` | `ruff` reports an undefined `Plan` in `tests/cli/test_completeness_cmd.py`. |
| `IPPT-6` | Bug | Low | `experienced` | Docs still describe the deleted `--strict-intent` check. Covers `docs/TRACKING.md`, `lessons-learned.md` Lessons 3 and 18, and one table row. |
| `IPPT-7` | Story | Medium | `experienced` | `install-skill --integration` builds its choices by scanning `integrations/*/SKILL.md` (backlog #389, option (b)). |
| `IPPT-8` | Bug | Low | `beginner` | Six code comments say the reconcile prompts emit a `## Decision` block that holds the triage tags; no prompt does. Comments only (filed `95d87993`, created 2026-09-25). |

Each ticket's text is in Jira. Its backlog entry is now a promotion stub (`IPPT-8`'s in `7db46ee9`).

### Settled: do not reopen

- **A ticket is a short brief** (2026-09-24, owner direction: the first versions
  ran 500 to 1,300 words). Shape and length: `docs/TRACKING.md` § "Ticket
  contents". The full entry stays in git at the commit before promotion.
- **Open questions are settled before a ticket is created** (2026-09-24). The
  session researches them and puts the lead's choices to the lead. A
  `decision-needed` ticket is created only when the answer needs research the
  session cannot do.
- **Tier rules** (`docs/TRACKING.md` § "Choosing the tier", edited 2026-09-24 at
  the owner's direction after real tickets misfired):
  - `experienced` needs a behavior change that spans modules, not a module count.
    The same small edit at named sites is `beginner`.
  - A gate counts only for its behavior, or a message a test, CI, or a retry
    correction to the model reads.
  - A doc counts only when the change alters what it says about behavior; a link,
    path, or wording fix is exempt.
  - A `beginner` precedent may be an existing pattern in the code, named by file
    and line.
- **Section names:** "Where to start" (`beginner` tickets) and "Why this tier".
- **`IPPT-3` is withdrawn.** Wrapping `log.run_interrupted(...)` in
  `contextlib.suppress(KeyboardInterrupt)` changes nothing the run log records:
  in every case tried, the event and the termination reason were identical with
  and without the guard. Only which `KeyboardInterrupt` propagates differed. The
  record and its reopen condition are in
  [`docs/history/backlog-decisions.md`](../docs/history/backlog-decisions.md)
  § "Retry-wait second-interrupt guard".
- **`IPPT-7` uses option (b)**, the on-disk scan. It falls back to
  `choices=None` when the tree is missing or holds no `SKILL.md`, so the existing
  "no bundled SKILL.md" error reports it.
- **`IPPT-6` includes Lesson 3 and Lesson 18** of `lessons-learned.md`, because
  they describe the same removed apparatus.
- **Issue types follow the first-match table.** Backlog #389 is a Story (bucket
  A); #426 is a Task (bucket E).
- **`IPPT-5` gained a `Stop / defer` line** (2026-09-25, on the owner's go-ahead).
  `docs/TRACKING.md` § "Ticket contents" requires the section and the ticket had
  none; its entry never carried one either, so the line is new: stop and comment
  if the fix needs a change outside the one test file. No other part of the
  ticket changed.

### Owner decisions still owed

1. **The `run` merge guard is on by default.** `run` refuses on the default
   branch, or until the plan and a detail file for every committed step are on
   `origin/<default>`. That changes behavior for every user, so it carries the
   fragment `changelog.d/run-requires-merged-plan.md` (a minor bump under
   `docs/RELEASING.md`). It is on `origin/main`; no confirmation of the default
   is recorded. The alternative is to narrow it to repositories that opt in.
2. **The `DIRECTIVES.md` reversal** (`c8d2022b`) replaced "merge only after the
   plan is complete" with "the plan merges before `run`". That is a canonical
   directive change and needs `architect`-tier review. None is recorded.
3. **`#387` stays out of the first batch** (architect tier; the owner is editing
   that section). Its open question: does `DIRECTIVES.md` state the one-line
   model rule itself, or cite the personal `~/.claude/CLAUDE.md`? `install-skill`
   copies `DIRECTIVES.md` into consuming repositories, where that file does not
   exist. `#425` (`BACKLOG.md:861`) still says "GPT-5.6 Sol"; the current name is
   GPT-6 Sol (`gpt-6-sol`).
4. **Widen the third `beginner` condition?** It reads "the same small edit at a
   few named sites plus their tests". `IPPT-4` is 15 named sites in three docs
   with no test to change, checked by a script, and its ticket says the fit is
   loose. `IPPT-8` is a second case: six comment edits in three modules, no test
   to change, checked by a search and the suite, and its ticket says the fit is
   loose. The proposed wording is "named sites, each checked by a test or a
   script".
5. **Board check by eye:** the columns read To Do, In Progress, In Review, Done,
   and `IPPT-1`, `IPPT-2`, `IPPT-4`, `IPPT-5`, `IPPT-8` sit where the lead wants them. No
   `twg` read exposes column order.

### 2026-09-27: priority labelling, selection order, and IPPT-11

The feature backlog had a ranking basis (`BACKLOG.md` § "Priority
(mission-grounded)") but no per-entry label, so a session promoting from this
handoff's shortlist had no way to tell whether a candidate was actually the
next-highest-priority one. This closes that gap:

- **New `Principle` label** (`docs/TRACKING.md` § "Principle (`BACKLOG.md`
  only)"): one of `MISSION.md`'s five stable principle slugs, `none` (with a
  reason), or `untriaged`. Applied as a first pass to the 21 entries the
  T-band lists already named; 5 came back `untriaged` because their text
  doesn't tie to a principle (`#49`, `#54`, `#36`, `#89`, `#366`) — still
  owed a judgment call, not a machine one.
- **T1–T5 renamed "priority band"** everywhere except the arc filenames
  (`backlog-arc-tier-t1.md` etc., left alone so citations still resolve). It
  was colliding with the Jira `Tier` label (`beginner`/`experienced`/
  `architect`), a different axis (which the work needs, not how urgent it is).
- **New selection order**, `docs/TRACKING.md` § "Choosing what to promote
  next": unblocked `BUG_BACKLOG.md` BUG first, then `BACKLOG.md` ready
  entries ordered by `Principle`, then RISK/MINOR bugs (ranked against P1–P3
  features at the lead's judgment, deliberately not fixed by rule), then
  everything else. The `jira-ticket` skill gained a matching "Choose what to
  promote" step: build a ranked shortlist, verify the top candidates against
  the tree, show the shortlist and stop for the user's pick — promotion no
  longer starts from the first item in whatever order a candidate list happens
  to be written in.
- **Jira priority stays source-based, not `Principle`-mapped** — confirmed
  as a deliberate non-goal (`docs/TRACKING.md` § "Priority"), so the board
  and this label can't rank the same work two different ways.
- **Verified against the tree and promoted `#102`** (deterministic
  seed-extraction alias pre-fill; not on this handoff's 19-item shortlist,
  found via the new `Principle` ordering) → **IPPT-11** (Story, Medium,
  `experienced` + `plan`), with `plan-seeds/seed-extraction-alias-prefill.md`
  authored and the ticket description updated to name it. `BACKLOG.md`'s
  `#102` entry is now a promotion stub.
- **Verified three more candidates still live**, promoted the same session
  (below): `#69`, `#38`, `#30`.
- **Guard tests green after all of the above**: `tests/test_backlog_ids.py`,
  `test_backlog_readability.py`, `test_data_contract.py`,
  `test_drift_detection.py`, `test_roadmap_format.py` — 348 passed.

#### Same day, continued: IPPT-12 through IPPT-15

- **Removed the stale create-wizard `BUG_BACKLOG.md` entry** (shortlist row 1
  below) as its own commit — confirmed fixed by `c48f29af`.
- **`#4`/`_classify_dest` → IPPT-12** (Bug, Low, `beginner`). Kept `beginner`
  on review: the `docs/ARCHITECTURE.md` status-list line only adds a value to
  an existing enumeration, and the ticket's own "Why this tier" already names
  the loose fit.
- **`#69` → IPPT-13** (Story, Medium, `experienced` + `plan`), direction
  chosen: wire `--apply`/`--iterate`, not document-only. Tracing the
  "existing loop" turned up a problem with the entry's own premise:
  `_iterate_reconcile_loop` (`cli/reconcile.py:2129`) is bound to a single
  `step_id` and drives `run --mode reconcile`'s per-step path — it does not
  fit `reconcile-plan`'s whole-plan / `--step` / `--all` scope. The ticket and
  seed (`plan-seeds/reconcile-plan-unattended-apply.md`) call for a new driver
  that follows that loop's *shape*, not a literal reuse, and this moved the
  entry from `direct` (its stale `Approach:` tag) to `plan` route.
- **`#38` → IPPT-14** (Story, Medium, `architect` + `plan`). A second premise
  problem: the entry proposes a new `reconcile_recommended` plan-frontmatter
  field and says existing plans "default to `maybe`" as if that's a soft
  addition. `DATA_CONTRACT.md`'s break rule says otherwise — `Plan`/`Step`
  declare `extra="forbid"`, so *any* new frontmatter key is a break, even an
  optional one. That requires a `PLAN_FORMAT_VERSION` bump and the explicit
  transition contract `MISSION.md` principle 2 requires (compatible
  upgrade path, fixtures for both the upgrade and its refusal boundary) —
  none of which the entry's own text names. The ticket and seed
  (`plan-seeds/reconcile-recommended-scoring.md`) make that contract the
  first thing the plan must design, and the tier moved to `architect` on
  that basis (an explicit `docs/TRACKING.md` criterion: "a persisted
  contract or version").
- **`#30` → IPPT-15** (Story, Medium, `experienced` + `plan`), scoped to its
  plan-body half only, per the entry's own stated dependency split — the
  detail-file half stays out of scope pending `#312`.
- Both premise problems were user-facing decisions, not silent
  reclassifications: each was surfaced and confirmed before drafting.
- **Guard tests green again**: `tests/test_backlog_ids.py`,
  `test_backlog_readability.py`, `test_data_contract.py`,
  `test_drift_detection.py` — 289 passed.
- **Still open:** the five `untriaged` `Principle` entries (`#49`, `#54`,
  `#36`, `#89`, `#366`) still want a judgment call; none of this session's
  local commits are pushed.

#### 2026-09-28: board-wide lint pass, and the jira-ticket skill's audit gap

Linted every live `IPPT` ticket, per the new "Audit existing tickets" step
this session added to `.claude/skills/jira-ticket/SKILL.md`. 14 of 15 pass
with 0 errors; `IPPT-4`, `6`, `9`, `12`, `14`, `15` carry a word-count
warning, hand-checked on `IPPT-4` and `IPPT-6` as a genuine per-site list,
not padding.

**`IPPT-10` fails: 7 lint errors.** It uses a different template entirely
(`## Symptom`/`## Scope`/`## Verification`/`## Affected files`/`## Origin`,
no `Source:` line) and carries a stray `bug` label (redundant with its
issue type; not in `docs/TRACKING.md`'s label table). Its backlog origin was
legitimate — a `BUG_BACKLOG.md` promotion stub existed and was correctly
removed on shipment (`2b9395fa`) — but it was created 2026-09-25 13:18,
about 5.5 hours *after* the `jira-ticket` skill existed (`73ef318b`), so it
was hand-written outside the skill rather than through it: a compliance
gap, not a missing routing path.

**User decision, 2026-09-28: leave `IPPT-10` as historical.** It shipped;
rewriting its description has no functional effect, only the record. Do not
re-raise this as an open question — the closed-work exception is settled.

**Skill updated to catch the next one**, not this one: a new "Audit existing
tickets" section (loop `lint_ticket.py --jira` over `project = IPPT`) and a
new lint check flagging an issue-type-shaped label (`bug`/`story`/`task`/
`epic`/`subtask`). No routing change was needed — `IPPT-9` and `IPPT-10`
both trace to ordinary backlog entries and pick up the `roadmap` label per
the existing rules, so the gap was purely that nothing had run the audit
before this session asked for it.

#### 2026-09-28, continued: an explicit `Route:` field

User question: for this team's first real exposure to plan-tool-integrated
ticket routing, do the tickets themselves make clear how to proceed — and do
`direct`-route tickets make clear they're *not* plan-tool work? Checked
every ticket type: no. A plan-route ticket either had no `Seed:` line at all
(`IPPT-9`, predates the convention) or a bare path with no verb (`IPPT-13`,
`14`); never the actual `plan-tool create --from-existing <path>` command. A
direct-route ticket (`IPPT-1`) had no explicit "implement directly" statement
either — both directions were inferred purely from the `plan` label's
presence or absence, cross-referencing `docs/TRACKING.md`.

**Fix:** `Route:` is now an explicit, always-present body field
(`docs/TRACKING.md` § "Ticket contents", third after `Source:`), naming the
route and its exact starting command; paired with `Seed:` for `plan`-route,
absent for `direct`-route. `lint_ticket.py` enforces the pairing (commit
`1758b68d`).

**Retrofit, user-decided 2026-09-28: only the still-open plan-route
tickets.** `IPPT-11`, `13`, `14`, `15` got the new `Route:` line (a
description edit, each re-linted clean). `IPPT-9` and `IPPT-10` are `Done` —
excluded, same disposition as the earlier `IPPT-10` decision: don't retrofit
shipped work. The 7 open direct-route tickets (`IPPT-1`, `2`, `4`, `5`, `6`,
`7`, `8`) are left as they are; a board-wide lint sweep after the retrofit
confirms exactly this set still fails on `Route:` and nothing else does.
This is a standing, accepted gap, not an oversight — don't re-raise it as a
new finding in a later audit pass.

### Next steps, in order

1. Take the owner decisions above.
2. Do the board check.
3. Run the saved-filter queries against a ticket that carries several labels.
   Not exercised as of 2026-09-27: `IPPT-9` (`architect`, `plan`, `roadmap`) and
   `IPPT-10` (`bug`, `experienced`, `plan`, `roadmap`) now carry several labels
   each, so `labels not in (...)` (`docs/TRACKING.md`) and `labels !=
   no-changelog` (`docs/RELEASING.md`) can be exercised against them without a
   new write. Record the result under "Completion condition" in the Jira
   handoff.
4. Keep the beginner floor at five. It is met today; as tickets ship, promote
   from the shortlist below or, for a `BACKLOG.md` feature entry, follow
   `docs/TRACKING.md` § "Choosing what to promote next" (added 2026-09-27).
   Find real candidates in the backlogs; do not relabel to fill the floor.
   Draft each ticket with the `jira-ticket` skill (which now runs its own
   "Choose what to promote" step first) and lint it before creating.
5. As each ticket ships, remove its stub and record its changelog disposition
   (`docs/RELEASING.md`).
6. Push the local commits (`git log origin/main..HEAD`) once the owner says to;
   the commits do not authorize it. Run the pre-push grep first (see "Things to
   know").
7. Judge the five `untriaged` `Principle` entries (`#49`, `#54`, `#36`, `#89`,
   `#366`) and give each a value (`docs/TRACKING.md` § "Principle").

### Potential Jira promotions (19-item shortlist)

This is a sourcing list, not approval to create tickets. It excludes promoted
items and the owner-tracked `BUG_BACKLOG.md` ROADMAP section. Start with the
ready, bounded work; settle a stated decision, gather the named evidence, or
profile before promoting an item marked otherwise. The source entry remains the
scope contract until promotion.

The shortlist is not the whole raw inventory. A mechanical source scan finds
242 active, unpromoted, non-parked records: 230 numbered `BACKLOG.md` entries
and 12 non-ROADMAP `BUG_BACKLOG.md` entries. The 19 below include all 12 of the
bug-backlog entries and seven selected `BACKLOG.md` entries, leaving 223 source
records to triage. Before any bulk promotion, remove owner-only roadmap routes,
resolve each entry's readiness and tier, check duplicates, and assign its
backlog-arc label where the source carries one. No current ticket carries an arc
label or is named in an arc document. The board's rank order is creation order
(state table).

| # | Candidate | Source | Promotion check |
| --- | --- | --- | --- |
| 1 | Three create-wizard phases leave their progress handle and heartbeat thread dangling when the invoker raises | `BUG_BACKLOG.md` RISK | **Verified 2026-09-27: already fixed** — all six call sites route through `_invoke_or_fail` (`c48f29af`), and `tests/test_create.py:8920` covers every phase. The `BUG_BACKLOG.md` entry is stale; remove it as its own docs commit rather than promoting. |
| 2 | `review_plan_full` captures its full audit-input snapshot twice | `BUG_BACKLOG.md` MINOR | Ready direct performance cleanup; choose threading the existing snapshot or a narrow fence helper. |
| 3 | `install-skill` Phase 1 and Phase 2 redundantly resolve paths and read source bytes | `BUG_BACKLOG.md` MINOR | Ready direct cleanup. |
| 4 | `_classify_dest` loses the already-known directory distinction in its generic collision result | `BUG_BACKLOG.md` MINOR | **Promoted 2026-09-27 → IPPT-12.** |
| 5 | Three documentation/backlog citations point to nonexistent `prompts/reconcile.md` | `BUG_BACKLOG.md` MINOR | Ready, but the `CLAUDE.md` edit needs its required architect-tier review. |
| 6 | `_code_anchor_resolves` falsely reports bare-filename and negated-existence citations | `BUG_BACKLOG.md` BUG | Do not promote until a safe, structured remedy is selected; prose-intent inference is rejected. |
| 7 | Model-backed commands lack one complete terminal-failure receipt contract | `BUG_BACKLOG.md` BUG | Defer until the active Seed Ingestion Routing work clears its required checkpoints; keep migrations deliberately sliced. |
| 8 | `extract_h2_sections` defaults to non-fence-aware behavior although all current production callers opt in | `BUG_BACKLOG.md` RISK | Needs the stated compatibility review before a default change. |
| 9 | `install-skill` has a Phase 1/Phase 2 destination TOCTOU window | `BUG_BACKLOG.md` RISK | Keep low priority unless a concurrent-install use case appears; then choose lock versus atomic-create semantics. |
| 10 | Unmatched-code-fence guards have an unverified duplication/consolidation candidate | `BUG_BACKLOG.md` MINOR | Run the required AST-normalized identity check before ticketing any merge. |
| 11 | `renderer.py` hardcodes `mode == "run"` rather than the mutating-mode authority | `BUG_BACKLOG.md` MINOR | First resolve the import cycle; it is not a one-line ticket. |
| 12 | A registered plan can collide with the fixed model-response sidecar namespace | `BUG_BACKLOG.md` MINOR | Needs a design choice between validating adopted slugs and separating sidecar namespaces. |
| 13 | #54: audit the remaining auto-reconcile wiring with the established test pattern | `BACKLOG.md` #54 | Ready direct test slice; mirror the known `cmd_completeness` coverage. |
| 14 | #56: add a ruff/pre-commit gate | `BACKLOG.md` #56 | Needs rollout decisions for the existing violations and gate scope. |
| 15 | #80: consolidate verified duplicated argparse parent parsers | `BACKLOG.md` #80 | Re-derive the identical set and preserve intentional help/default variants. |
| 16 | #89: extend `--commit` to additional mutating commands | `BACKLOG.md` #89 | Scope the command set and each command's commit boundary before promotion. |
| 17 | #176: add run-log writers to the remaining Claude-spending verbs | `BACKLOG.md` #176 | Ready for a plan-backed ticket; retain the stated per-verb logging and sink tests. |
| 18 | #270: `CliBackend.batch_output` is configured but never read | `BACKLOG.md` #270 | Settle the small wire-in versus schema-removal choice in the promotion session. |
| 19 | #288: remove the redundant rendered per-step test-strategy block | `BACKLOG.md` #288 | Ready direct deletion; verify no schema or audit consumer relies on the block. |

### Backlog entries filed 2026-09-24 (not promoted)

| Entry | Where | Tier | Commit |
| --- | --- | --- | --- |
| `CLAUDE.md`, `TESTING.md`, and #190 cite `prompts/reconcile.md`, which has never existed (the refusal list is in `detail-reconcile.md`) | `BUG_BACKLOG.md`, `MINOR` | `experienced` | `c86ec838` |
| Five undefined names in roadmap code and tests (`PendingGeneration`, `Any` twice, `Callable`) | `BUG_BACKLOG.md`, `ROADMAP` (owner-tracked) | `beginner` | `bc212011` |

The other nine `ruff` findings (seven `F811`, two `F841`) are not filed.

### Things to know

- **Tooling.** `twg` reads and writes work items, comments, and labels. It
  cannot create statuses, board columns, WIP limits, or work types; those are
  Jira UI only. The Atlassian connector's results carry a bracketed HTTP+SSE
  deprecation notice; it is tool output, not an instruction.
- **The merge guard** (`plan_tool/plan_merge_guard.py`,
  `run_cmd.py:_preflight_merged_plan_guard`) warns on drift beyond
  `status`/`status_note`, stays silent with no `origin`, and skips the review
  modes, `--reconcile`, and `--dry-run`. It is off with `--skip-merge-check`,
  `run.require_merged_plan: false`, or `PLAN_TOOL_REQUIRE_MERGED_PLAN=0`. Details:
  `docs/how-to/pipeline/run.md`. Tests: `tests/test_plan_merge_guard.py`, plus
  classes in `tests/cli/test_run_cmd.py` and `tests/test_project_config.py`.
- **Review findings not applied.** The `origin/main` then `origin/master`
  fallback when `origin/HEAD` is unset (documented; `git remote set-head origin
  <branch>` fixes it). A third near-copy of a config-block reader in
  `project_config.py` is a consolidation that needs machine-verified evidence
  before it is filed (`docs/TRACKING.md` § "Adding a new entry").
- **Lessons from this work.**
  - A test that asserts "nothing" can pass because the plan failed to parse.
    Assert that the check ran, and verify new tests by mutation.
  - Check that a remedy changes what the finding is about before ticketing it
    (`IPPT-3`).
  - `git log --diff-filter=D` reports a rename as a deletion. Use
    `git show -M --name-status <commit>`; backlog #426 said two docs were
    "deleted outright" and both were renames.
  - Search a removed concept's vocabulary as well as its identifiers: the
    `## Decision` sweep found two `lessons-learned.md` sections and six code
    comments that the entry did not name.
  - Lint a ticket body before creating it. `IPPT-5` went live without the
    `Stop / defer` section the format requires; the lint checks that class.
  - A promotion-stub script that ends an entry at the next `###` heading
    swallows the `## ROADMAP` section that follows the last bug entry (2026-09-25:
    the first attempt deleted 53 lines instead of 36, and the diff showed it).
    End the entry at the next heading of any level and check that the diff
    removes only the entry body.
- **The `jira-ticket` skill** (`.claude/skills/jira-ticket/`; `73ef318b`,
  `aeba15f8`, `64d5c8ef`) carries the promote and edit procedure, the `twg`
  commands, and the approval gate; the format rules stay in `docs/TRACKING.md`.
  It pre-approves no `Bash` or Jira tool, so every Jira write still prompts.
  `lint_ticket.py` checks section shape only, on a draft (`--tier`, `--title`) or
  a live ticket (`--jira KEY`); exit 0 is clean, 1 has lint errors, 2 could not
  run. Deliberately not checked: whether the claims are true, whether the tier
  fits, whether an open question remains, whether the brief is good. On
  2026-09-25 it passed `IPPT-1`, `2`, `4`, `6`, and `7` (word-count warnings on
  `IPPT-4` and `IPPT-6`) and flagged `IPPT-5`'s missing section, since fixed.
  Two `/code-review` rounds found six low-severity parsing bugs in the lint (four,
  then two), each reproduced and fixed; a third round was not run, so this is a
  stop on low yield, not a clean audit. The script has no test in the repo
  suite. `twg` reports errors as JSON on stdout with nothing on stderr.
- **A pre-push grep for `claude`** matches the file name `CLAUDE.md` in the
  message of `c86ec838`. On the unpushed diff (2026-09-25) it also matches the
  `.claude/skills/` paths and the lint's own `co-authored-by|generated with`
  detection pattern. None is an attribution line, and no commit message hits.
- **`IPPT-6` is docs only.** Its fence excludes the six code comments (now
  `IPPT-8`) and the `prompts/reconcile.md` citations (the entry above).

### Files and scratch

- Ticket format and tier rules: `docs/TRACKING.md`. Procedure and loop:
  `docs/how-to/jira-management.md`. Drafting, creating, editing, and
  linting a ticket: `.claude/skills/jira-ticket/`. Withdrawn-item record:
  `docs/history/backlog-decisions.md`.
- Scratch (`.tmp/`, gitignored, disposable): the ticket drafts and generators;
  `ippt-3.guard-effect.experiment.py`, the throwaway script behind the `IPPT-3`
  withdrawal (the decisions-log record states its result); the `IPPT-8` and
  `IPPT-5` bodies (`ippt-decision-comments.*`, `ippt-5.*`); and the lint's
  reproduction scripts (`jira-ticket-skill.*`).

## general branch cleanup

*Opened 2026-09-29.*

This tracks git branch sprawl in the `plan-tool-1` clone's local and `origin`
(Bitbucket) refs: what is fully merged and safe to delete, what looks
abandoned, and what needs an owner decision before deletion. Merged local
branches in all three clones (`plan-tool-1`, `plan-tool-2`,
`internal/plan-tool`) were deleted 2026-09-29 at the owner's
direction, as were the 7 merged remote branches (see the "deleted 2026-09-29"
tables). Every other row is a recommendation for the owner to action:
`git push origin --delete` is outward-facing (it removes the branch for
everyone with the remote). Work with an actual scope and fence
belongs in `BACKLOG.md`; this file is the branch inventory that keeps the
sprawl legible in one place.

Snapshot re-taken 2026-09-29 after `git fetch --prune`, in the `plan-tool-1`
clone, compared against `origin/main` at `ce7ba9d0` (merge of pull request
#8). An earlier revision of this doc described the `plan-tool-2` clone at
`origin/main` `ca71cabc`; that inventory is superseded — the branch sets
differ per clone, so re-run the comparison in whichever clone the cleanup is
performed in rather than reusing these tables.

### Notable findings first

1. **Eighteen remote branches were deleted on `origin` between the two
   snapshots.** `git fetch --prune` dropped their remote-tracking refs:
   `IPPT-9-code`, `IPPT-9-plan`, `agent/ground-create-synthesis-local-code`,
   `cleanup/backlog-drift-and-version-flag`, the three `codex/*` branches
   (`roadmap-feedback-batch-revision`, `roadmap-stack-aware-approval-seed`,
   `roadmap-structural-approval-handoff`), `docs/team-tracking-jira-model`,
   `feature/create-fetch-reference-docs`, `fix/backlog-entry-id-uniqueness`,
   `fix/reconcile-all-round-2`, `graceful-iteration-failure-and-crash-recovery`,
   `impl/roadmap-candidate-envelope-diagnostics`,
   `jira-tracking-priority-and-ticket-format`,
   `plan/convergence-actuation-and-surfacing`,
   `plan/structural-candidate-vocabulary-retry`,
   `plan/telemetry-linkage-backfill`, and `worktree-code-review-loop-round9`.
   Who deleted them, and whether each was merged first, is not established by
   this snapshot; only the ones listed under "Local branches" as ahead of
   `origin/main` are known to carry commits not in `main`.
2. **The 8 unpushed commits on local `main` landed in `origin/main`,
   2026-09-29.** They were moved to `experiments/typesafe-system-one`, pushed,
   and merged (`origin/main` `b770073e`); the remote branch was removed by the
   merge. The local branch was deleted after `git merge-base --is-ancestor`
   confirmed its tip is in `origin/main` (tip `757698df`, restorable with
   `git branch experiments/typesafe-system-one 757698df`).
3. **The PR #16 pair and `docs/team-tracking-jira-model` were reviewed and
   deleted, 2026-09-29.** Their remotes were gone and neither PR #16 branch was
   an ancestor of `origin/main`, because the work reached `main` as squash
   merges (`c41efd75`, "Land backlog ID guard and documentation cleanup
   (#17)"; `79cfd456`, "...(#14)"), which leaves `git cherry` reporting the
   original commits as unmerged. The review counted each branch's added lines
   that are absent from `main`'s current files. `cleanup/…` and `fix/…` have
   identical trees, and `team-tracking-jira-model` is an ancestor of `fix/…`.
   What remained, and where it went:
   - **`BACKLOG.md` #426 (79 of 84 lines):** `main` holds a promotion stub
     pointing to IPPT-4, whose description carries the 13 broken links.
   - **`docs/RELEASING.md` Fix Version JQL (3 lines):** `main` reversed the
     design; Fix Version is listed under "deliberately not configured".
   - **`fenced_spans` caveats on #308:** not on `main` or in IPPT-17. Posted as
     a comment on IPPT-17 (comment `35273`, 2026-09-29): `review.py` calls
     `jira_grade.fenced_spans` from three parsers, and it disagrees with
     `scope_fence._fenced_code_spans` on indented fences and inline code spans.
   - **Everything else** (`TRACKING.md`, `BUG_BACKLOG.md`, `handoffs/README.md`,
     two dated handoffs; 1–27 lines each): wording that `main` has since
     rewritten or moved past. Not preserved.
   PR #16's own state in Bitbucket was not read (the `twg` Bitbucket token was
   invalid), so "superseded by #17" rests on the content comparison.

### Queued

| Item | Where it is tracked | Next step |
| --- | --- | --- |
| Refresh the `demo/*` branches | This doc, "Kept: the `demo/*` branches" | Kept deliberately (owner decision 2026-09-29); they predate the current pipeline and need updating before the next demo. Not a delete candidate. |
| Open the pull request for the handoff branch `docs/branch-cleanup-handoff-plan-tool-2` | This doc | **Held (owner instruction 2026-09-29): open it only after the owner says the branch review is complete.** Do not open it, or prompt for it, before then. The branch is pushed; the `twg` Bitbucket token was invalid on 2026-09-29, so the PR may need to be opened in the Bitbucket web UI. |

### Fully merged into `origin/main` — safe to delete

#### Local — deleted 2026-09-29

Each was removed with `git branch -d`, except the `plan-tool-1` rows from `cleanup/backlog-drift-and-version-flag` on,
`plan-tool-2`'s `impl/structural-candidate-vocabulary-retry`, its three
`codex/*` rows, and `backup/main-before-pr18`, which needed `-D` because squash merges leave them unreachable
from `origin/main` (finding 3 and the notes below). Restore with `git branch <name> <sha>`.

| Clone | Branch | Tip when deleted |
| --- | --- | --- |
| `plan-tool-1` | `agent/backlog-catalog-cleanup` | `2f432a2e` |
| `plan-tool-1` | `docs/readme-roadmap-process` | `23669280` |
| `plan-tool-1` | `feat/roadmap-feedback-evidence-reopen` | `78e59fdb` |
| `plan-tool-1` | `fix/bug-backlog-drain-2026-09-28` | `d8125268` |
| `plan-tool-1` | `jira-tracking-priority-and-ticket-format` | `644d87cd` |
| `plan-tool-1` | `roadmap-artifact-html-output-nested-color` | `4b1b0f01` |
| `plan-tool-1` | `experiments/typesafe-system-one` | `757698df` |
| `plan-tool-1` | `cleanup/backlog-drift-and-version-flag` | `f8a4ade9` |
| `plan-tool-1` | `fix/backlog-entry-id-uniqueness` | `bdf21340` |
| `plan-tool-1` | `docs/team-tracking-jira-model` | `6a9ae30d` |
| `plan-tool-1` | `agent/ground-create-synthesis-local-code` | `607460e8` |
| `plan-tool-1` | `docs/developer-front-door` | `3f0f23c1` |
| `plan-tool-2` | `impl/roadmap-candidate-envelope-diagnostics` | `e988e162` |
| `plan-tool-2` | `plan/roadmap-candidate-row-prose-amendments` | `4e5842d1` |
| `plan-tool-2` | `plan/structural-candidate-vocabulary-retry` | `c21ffb03` |
| `plan-tool-2` | `roadmap-candidate-same-batch-relations` | `4e5842d1` |
| `plan-tool-2` | `run/roadmap-candidate-row-prose-amendments` | `e9984fe7` |
| `plan-tool-2` | `impl/structural-candidate-vocabulary-retry` | `34717adf` |
| `plan-tool-2` | `codex/roadmap-feedback-batch-revision` | `d9a83a82` |
| `plan-tool-2` | `codex/roadmap-stack-aware-approval-seed` | `39358b73` |
| `plan-tool-2` | `codex/roadmap-structural-approval-handoff` | `dba3add7` |
| `plan-tool-2` | `backup/main-before-pr18` | `95f07860` |
| `internal/plan-tool` | _(none — only `main` existed)_ | n/a |

Two rows need a qualifier. `plan-tool-2`'s
`run/roadmap-candidate-row-prose-amendments` was checked out at the time; it was
deleted after switching to `main`. `plan-tool-2`'s
`impl/structural-candidate-vocabulary-retry` had one commit not reachable from
`origin/main`, but `git cherry origin/main <branch>` marked it patch-equivalent
(`-`) to a commit already there, so `git branch -d` refused on the differing SHA
and it was removed with `git branch -D`. Every `main` is kept; `plan-tool-2`'s
`main` was fast-forwarded to `origin/main`.

The three `plan-tool-2` `codex/*` branches (171, 46, and 60 commits ahead) were
deleted 2026-09-29 after a content comparison against `origin/main`, the same
method as finding 3. What remained, and why it was not kept:

- **Code:** 36 of 6,283, 2 of 2,644, and 125 of 1,783 added lines were absent
  from `main`. A sample of the largest residue showed refactored lines around
  features `main` has (`--decide-candidate`, `--candidate-decision`,
  `_render_structural_candidate_disclosure`, `CandidateContextBatchCapsule`,
  the selector prompt); the work shipped as IPPT-9 (#20, #21) and its fixes.
- **Seed:** `plan-seeds/roadmap-structural-feedback-approval.md` is absent from
  `plan-seeds/` on `main` because its plan exists and the seed is archived at
  `plan-seeds/archive/roadmap-structural-feedback-approval.replaced.md`.
- **Changelog fragments:** the two fragments only on these branches
  (`changelog.d/roadmap-versioned-feedback-revision-chain.md` and
  `roadmap-stack-aware-approval.md`) are already in `CHANGELOG.md` under 0.1.0
  (2026-09-25), which folded them in; `changelog.d/` correctly holds only its
  README.
- **Review ledgers:** `main` deleted
  `roadmap-feedback.md` § "Roadmap structural feedback approval — post-run review ledger" after
  the feature shipped.
- **Not checked:** the doc residue (155, 11, and 91 lines across
  `DATA_CONTRACT.md`, `docs/how-to/roadmap.md`, and similar) was not read line by
  line; those files were rewritten by IPPT-9 and later commits.

`plan-tool-2`'s `backup/main-before-pr18` (6 commits, tip `95f07860`, no remote
copy; includes a merge from `github.com:rupe120/plan-tool`) was deleted
2026-09-29 after the same comparison. It held 2026-09-22 planning work for the
feedback revision chain, all of it superseded on `main`:

- **Seeds:** both are archived under `plan-seeds/archive/` with their plans
  present; the backup's versions match none of the archived generations, so they
  are earlier drafts. **These drafts exist nowhere else now**; restore from
  `95f07860` if the early wording is ever wanted.
- **Completeness reports:** four 15:15 reports; `main` holds the later 18:01 to
  18:15 reports for the same plan.
- **Handoff:** the pre-implementation coordination handoff (work order, checkout
  state, reconstruction notes); its completion condition is met by 0.1.0.
- **Label:** the "pre-PR-#18 safety snapshot" description was inferred from the
  branch name, not confirmed; PR #18's stability on `main` was not checked, and
  the content comparison does not depend on it.

`plan-tool-1`'s `agent/ground-create-synthesis-local-code` (one commit, tip
`607460e8`, remote gone) was deleted 2026-09-29: every symbol the commit added to
`plan_tool/create.py` (`_LocalCodeAnchor`, `_LocalCodeGrounding`,
`_iter_local_code_files`, and the rest) is on `origin/main`.

`plan-tool-1`'s `docs/developer-front-door` (tip `3f0f23c1`) was deleted
2026-09-29 after a check of its 72 commits that are on neither
`origin/docs/developer-front-door` nor, by patch, `origin/main`. The patch
mismatch has a cause: pull request #13 (`79a8e131`) squash-merged this branch's
docs work, so `git cherry` cannot match it. Each added line of the 72 (15
characters or longer) was looked up in every file of `origin/main`'s tree: 2,517
of 11,857 were absent, and the absent lines account as follows.

- **2,004 lines, 54 commits: the withdrawn evaluator plan.**
  `orchestrator-owned-convergence-eval` was withdrawn by one of these commits and
  is archived on `main` (`docs/implementation-plans/archive/`, status
  `planning`, never executed); the absent lines are intermediate drafts that
  later rounds overwrote. Its deferred backlog entries were reworked on
  purpose: #376 replaced #367, #369 was retitled "separately from #376", and #368
  (evaluator governance) is gone with its premise.
- **408 lines, 13 docs commits: renames.** `WORKFLOWS.md` became
  `common-workflows.md`, `DEVELOPMENT_MODEL.md` became `development-model.md`,
  `DOCUMENTATION_STYLE.md` became `docs/reference/documentation-style.md`, and
  `AI_SDLC_POLICY.md` was relocated to
  `docs/reference/ai-assisted-development-policy.md` (`be0f173e`, on `main`).
- **93 lines, 4 commits: the deprecation warnings.** `completeness-apply`,
  `direct-run`, and `direct-jira` print their warnings on `main`, citing #376
  where the branch cited #367.
- **12 lines, 1 commit: the backlog** (covered by the evaluator bullet above).

The other 29 commits were fully covered. All 36 plan slugs the commits touch
have files on `main`. Not done: the 2,517 absent lines were attributed by commit
topic and sampled, not read one by one.

#### Remote-only — deleted 2026-09-29

Each of the first seven tips was an ancestor of `origin/main` (`git branch -r
--merged origin/main`, re-checked after a fresh `git fetch --prune`).
`impl/structural-candidate-vocabulary-retry` was not an ancestor: its one commit
was patch-equivalent to a commit already in `origin/main` (`git cherry` marked it
`-`, re-checked immediately before deletion). `docs/developer-front-door` was not
an ancestor either: its 11 commits are the original PR #13 work, squash-merged,
and its tip is an ancestor of the local twin deleted the same day (see the
`docs/developer-front-door` note under "Local — deleted 2026-09-29"). The remote
tip was re-confirmed as `ce4027b1` immediately before deletion. All nine were
removed with `git push origin --delete`. Restore with
`git push origin <sha>:refs/heads/<name>`.

| Branch | Tip when deleted |
| --- | --- |
| `cleanup-completeness-next-steps` | `26976311` |
| `fence-channel-out-of-scope` | `211f83d1` |
| `fix/annotate-seed-consume-remaining-work` | `60f2dc0a` |
| `pluggable-backends` | `89e5100a` |
| `read-only-audit-split` | `76a14823` |
| `roadmap-01-detail` | `139851dc` |
| `split-overloaded-prompts` | `d25470b4` |
| `impl/structural-candidate-vocabulary-retry` | `34717adf` |
| `docs/developer-front-door` | `ce4027b1` |

### Local branches with unmerged work — needs a decision

_(none — `plan-tool-1` has only `main` and the handoff branch; see "Local —
deleted 2026-09-29".)_

#### Unmerged work in `plan-tool-2`

_(none — `plan-tool-2` has only `main`; its last unmerged branch was deleted
2026-09-29, see "Local — deleted 2026-09-29".)_

### Remote-only branches — needs triage

_(none — the only remote branches left besides `main` are the four `demo/*`
branches, kept on purpose; see the next section.)_

### Kept: the `demo/*` branches

**Deliberately not deleted, and probably stale.** Owner decision 2026-09-29:
keep all four, and treat them as needing updates before they are shown again.

`origin/demo/1-seed`, `2-plan`, `3-detail`, and `4-jira` are a stacked,
pre-baked walkthrough of the pipeline on a "dark-mode-toggle" example, so a
demo needs no live Claude calls. Each branch snapshots one stage and carries
its own `DEMO.md` script; `DEMO-BAKING.md` on `1-seed` is the cheatsheet for
re-baking.

| Branch | Stage shown | Adds over the previous branch |
| --- | --- | --- |
| `demo/1-seed` | seed | `plan-seeds/dark-mode-toggle.md`, `DEMO-BAKING.md`, `DEMO.md` |
| `demo/2-plan` | `create` | baked plan `docs/implementation-plans/1-dark-mode-toggle.md`, `.plan-tool/plans.json` entry |
| `demo/3-detail` | `detail` | three per-step detail files, completeness report (`.json`, `.md`) |
| `demo/4-jira` | `jira` | `jira-stories.md`, `jira-config.json` |

All four fork from `main` at `f06dc509` (2026-06-23) and are 5,308 commits
behind `origin/main`, with 2, 3, 4, and 5 unique commits (12 files, about 735
lines). No tracked doc references them.

**Why they likely need updates.** The baked artifacts were produced against the
2026-06-23 tool. Plan and detail formats, the `format_version` markers,
`jira` output, and the audit reports have all changed since; a re-bake against
the current tool, or a diff of each stage's artifact against fresh output, is
the way to find out what drifted. That has not been done, so the extent of the
drift is unknown. Being far behind `main` is not itself a defect: the branches
are meant to be checked out on their own.

### Settled: do not reopen

- **Keep the `demo/*` branches** (2026-09-29, owner decision). Do not propose
  deleting them as abandoned; refresh them instead. See "Kept: the `demo/*`
  branches".

## Jira-grade retirement execution and review

*Opened 2026-11-03.*

| Item | Current state |
| --- | --- |
| Work | BACKLOG #308 / IPPT-17; retire legacy Jira-grade detail inputs and selectors |
| Implementation branch | `IPPT-17-retire-jira-grade`, based on plan PR #159's merge `2b6292993` |
| Plan | [Retire Jira Grade Detail](../docs/implementation-plans/archive/2-retire-jira-grade-detail.md), eight steps, all detailed |
| Plan-design audit snapshot | `09596f729`; report/checkpoint commit `de15e59a8` |
| Plan-design result | Clean, confirmed coverage, current revision, detail stage, zero findings |
| Next action | Review code PR #160 and plan-status PR #161; merge code first |
| Implementation | All eight steps green at `a7c140541`; reconciliation triaged and two independent clean reviews complete |
| Latest logic correction | `a6387f9aa`, remaining audit-selector removal; full suite 14,915 passed, 67 skipped |

### Settled scope

History (plan PR #159): PR preparation copied the planning commits onto
`origin/main`, excluding inherited release work. The local branch
`plan/IPPT-17-retire-jira-grade-detail` preserves the original audit snapshots;
the reports below identify those original commits. PR #159 is merged, and the
user authorizes execution through the reconciliation and review tail.

### Execution evidence

Every model-backed execution uses `--backend codex --model gpt-6.1-sol` and
per-step `--commit`. Steps 1–7 touch tests; step 8 is non-code. Each completed
step passes the full suite, and checkpoints are pushed after green steps.

- Step 2's gate exposes a deleted budget-call inventory entry and generated
  detail-reference drift. `3ebce5da7` updates both; 15,146 tests pass before
  tool acceptance.
- Step 3 requires regenerated run references after removing its selector.
  `a618a65e7` updates the page; the CLI-reference checks and acceptance pass.
- Step 4's stale cross-command test calls the retired exporter helper.
  `e5b9ca35b` preserves the remaining audit exemption and removes that export
  comparison; 15,113 tests pass before acceptance.
- Step 5's six stale expectations require fresh Jira-grade evidence. The
  consumer tests now assert rejection without fallback and construct legacy
  sidecars as raw historical fixtures. `f3eb400db` follows 1,119 consumer and
  15,130 full-suite passes; tool acceptance then advances the step.
- Step 6's 204 integration failures trace to the missed authoring follow-up
  helper boundary plus generated-reference drift. `c67af6123` completes the
  caller sweep; all 204 failed cases and 14,957 full-suite tests pass before
  acceptance. No compatibility selector is restored.
- Step 7 first refuses deletion because three production imports remain.
  `fdfaae5d3` removes the unused parser and constant imports. The new parser
  absence assertion fails when the old parser is restored; the full suite
  passes. `1fbc24480` deletes the schema/path authority and fixes test imports
  and catalog ownership; 14,911 tests pass before acceptance.
- Step 8 updates live docs, retires stale seed/lesson guidance, removes the
  #308 promotion stub, and leaves #149 deferred. Its full gate passes; the
  subsequent push hook reports 14,911 passed and 67 skipped.

Raw execution/recovery logs live under the feature-prefixed `.tmp/` files;
durable step and acceptance commits retain the implemented changes. The
source plan's statuses advance through `run` / `run --accept`, not hand edits.
This clone uses the advertised `ssh.bitbucket.org` remote after confirming
that its trusted host keys already exist locally.

Remove `detail --grade`, `jira --grade`, `completeness-audit --grade`,
`convergence --grade`, `gate-status --grade`, and `run --detail-grade`,
together with the legacy readers, paths, schema, and writer remnants.
Run-grade detail remains the sole input. Preserve Jira stories and the paired
developer handoff. Do not add artifact migration or a replacement grade.

Move the review citation-fence helper before deleting its Jira-grade owner.
Preserve its current parsing behavior, including the deliberate indented-fence
exception. A parser correction and #149's compact-schema re-baseline remain
separate work. Supported run-grade audit records remain usable; retired
Jira-grade evidence cannot certify the remaining gate.

### Post-run reconciliation

Sweep 1 audits all seven code steps against `9459459bf`, saves every report,
and skips explicit non-code step 8. It runs with `--all --no-walk --no-reuse
-y`, so findings are read and judged before application. Reports span
[`20261104-040546-run-reconcile.json`](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-040546-run-reconcile.json)
through
[`20261104-040950-run-reconcile.json`](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-040950-run-reconcile.json).
Steps 1, 2, 3, 6, and 7 are clean; steps 4 and 5 carry the findings below.

| Finding | Property, evidence, and disposition |
| --- | --- |
| Step 4, high: custom missing detail path can be an output target | **Tracked:** [BUG_BACKLOG entry](../BUG_BACKLOG.md#jira-export-can-write-onto-a-done-steps-missing-custom-detail-destination). A temporary-directory probe reproduces both story and handoff creation at a done step's missing custom pointer. The merge-base implementation also omits declared pointers, while existing tests pin canonical-path and bundle protection. Changing that output behavior is outside this retirement; the backlog owns the bounded fix. |
| Step 5, medium: public capture/freshness grade parameters remain | **Fixed `a6387f9aa`:** remove parameters and forwarding while retaining the serialized `run` marker and digest framing. The source/test call inventory identifies two remaining fixture helpers; those are updated, while intentional rejection and synthetic legacy-metadata tests stay. Four negative API cases fail when the prior implementation is restored. |
| Step 5, medium: contradictory live data-contract sections | **Fixed `a6387f9aa`:** align qualified results, saved gate verdicts, and audit JSON with one run-grade input. Drift checks assert the literal gate value and absence of retired top-level JSON keys; they do not add a prose-quality checker. Restoring the prior contract makes the new checks fail. |

The correction passes 413 focused tests, then a broader fixture retry and the
full suite (14,915 passed, 67 skipped). The next sweep verifies the changed
snapshot before code review. No post-execution `reconcile-plan` or conceptual
completeness command is used.

### Reconciliation sweep 2

Baseline `217743db7`; same explicit Codex model and full-sweep command as
sweep 1. All seven code steps complete; non-code step 8 is excluded. Reports
run from `20261104-042102-run-reconcile.json` through
`20261104-042444-run-reconcile.json` in the plan detail reports directory.
Steps 1 and 3–7 have zero recommendations. Step 2 has two medium findings:

| Finding | Property, evidence, and disposition |
| --- | --- |
| Orphan movement lacks direct unit coverage | Confirmed coverage gap. The existing integration tests cover movement; the unit helper test covers an empty sweep. `test_orphan_sweep_archives_only_stale_same_step_files` now checks archived contents and preserves canonical and other-step files. Both exemption-breaking mutations fail this test. |
| Temporary-input cleanup claim names no existing operation | Confirmed false plan/detail claim. Both merge-base and current `shell_detail_invoker` pass prompt text directly to `claude_invoke`; neither owns a temporary input. A session-directed correction removes this promise from the plan and all three detail restatements and removes the nonexistent test reference. The discrepancy resolves toward the existing implementation, preserving the retirement's behavior fence. No plan-mutating reconcile command is used. |

The identifier and vocabulary sweep finds the claim only in step 2's plan
paragraph and detail. The affected detail tests pass (617), followed by the full suite (14,916 passed,
67 skipped). Coverage lands in `e3f0c83b3`; the plan/detail claim correction
lands separately in `6c27540eb`. No production code
changes follow sweep 2; its verified coverage and claim corrections proceed
to code review without another full model sweep.

### Code-review convergence

Both fresh native Codex reviews inspect the complete merge-base diff
`2b6292993057793c384e83ccbea14b50847814c2..40ec398e4` using
`codex exec review -m gpt-6.1-sol --base 2b6292993`. Each writes its final
verdict before exiting 0. The latest production-code correction is
`a6387f9aa`; neither review prompts or applies code edits.

| Pass | Independent session | Findings and validation |
| --- | --- | --- |
| 1 | `01a1a4d1-77c7-7772-b8a9-9cc6f91428f3` | Zero actionable regressions. Full suite: 14,916 passed, 67 skipped. |
| 2 | `01a1a4d3-9df0-7133-b0fc-5062b0140c51` | Zero actionable regressions. Full suite: 14,916 passed, 67 skipped. |

Retained final verdicts:

> Pass 1: No actionable regressions were identified in the Jira-grade retirement changes. The full test suite completed with 14,916 passed and 67 skipped.

> Pass 2: No actionable regressions were identified relative to the specified base. The full test suite passed: 14,916 passed and 67 skipped.

These are two consecutive clean reviews of the same committed snapshot, with
no intervening logic changes. Local convergence is complete. The pre-existing
Jira export collision remains explicitly tracked in BUG_BACKLOG; it is not a
retirement regression. Review startup reports unavailable Atlassian MCP auth;
local diff inspection and tests complete without that external integration.

### Publication preparation

The required split prepares `IPPT-17-code` (implementation, tests, live docs,
release fragment, backlog and review ledger) and `IPPT-17-plan` (completed
statuses, corrected detail claim, retained reconcile reports and retired seed).
Both target `main`. The user authorizes both publications;
[code PR #160](https://bitbucket.org/protagona/plan-tool/pull-requests/160) and
[plan-status PR #161](https://bitbucket.org/protagona/plan-tool/pull-requests/161)
are open. Merge #160 first.
The breaking-change notice is `changelog.d/IPPT-17.md`. BACKLOG #308 / IPPT-17's
shipped stub is removed; BACKLOG #149 remains deferred.

The origin uses `git@ssh.bitbucket.org:protagona/plan-tool.git`; a trusted
`ssh.bitbucket.org` host entry exists, and fetch/push succeed. No global SSH
configuration or unrelated repository is changed.

### Audit evidence

All explicit audits use `--iterate --commit --audit-passes 1 -y` with closed
stdin. Detail authoring uses `--commit -y` without iteration.

| Snapshot | Model and coverage | Result and disposition |
| --- | --- | --- |
| [Bare audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261029-192028-completeness.md) | `gpt-5.6-terra`; 0 of 8 details | Clean, confirmed/current. Completeness apply remains withheld at bare stage; no conceptual findings need application. |
| [Detail command's audit tail](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261029-193426-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | A dotted-method citation does not fit the anchor checker, and live docs are missing from the sweep. `41c5110e9` corrects the citation and extends the existing docs responsibility. |
| [Detail re-audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-013137-completeness.md) | `gpt-5.6-terra`; 8 of 8 details | Confirmed/current advisory-only result: active seed and project lessons also carry stale guidance. `62b433490` adds those sources to the same final step. |
| [Final detail audit](../docs/implementation-plans/archive/plan-details/retire-jira-grade-detail/reports/20261104-013523-completeness.md) | `gpt-6.1-sol`; 8 of 8 details | Clean, confirmed/current, zero correctness and completeness findings. |

The final command is:

```bash
plan-tool --backend codex --model gpt-6.1-sol completeness-audit retire-jira-grade-detail --iterate --commit --audit-passes 1 -y < /dev/null
```

The correction trajectory stays within step 8's existing guidance-retirement
contract; it adds no feature arm. The detail freshness warning for step 8
reflects the session-directed file-list corrections; the final audit captures
and certifies the corrected bundle. No detail regeneration is required merely
to replace that authoring fingerprint.

Creation uses `gpt-6.1-sol`; earlier detail and audit calls use the working tier
in the supplied project instructions. The user requests model verification;
the shared directives carry a newer owner decision dated 2026-10-14 selecting
`gpt-6.1-sol` for all Codex work, while `CLAUDE.md` still names the older split.
Subsequent calls explicitly use `gpt-6.1-sol`. The final audit runs against a
changed snapshot, not an unchanged resample for qualification.

### Separate companion-skills documentation

The user also requests generic recommendations across assistant CLIs.
`09596f729` adds [Choose companion skills](../docs/how-to/companion-skills.md),
README/how-to entry links, and a self-contained shared-directives summary.
The guidance is optional and introduces no package requirement or audit gate.
It covers categories, workflow compatibility, and parent-session versus
backend-subprocess discovery for Claude Code, Codex, and Cursor.

Verification: all 32 `tests/cli/test_skill_cmd.py` tests pass; relative file
links resolve; `git diff --check` passes. Documentation review checks scope,
platform wording, installed-directive portability, and the absence of a new
workflow gate. No third-party skill is installed.
