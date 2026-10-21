> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-versioned-from-birth.md`.
> Preserved here for history; do not edit.

# Plan seed: store roadmap content only in the version store

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/roadmap-versioned-from-birth.md
```

Source: BACKLOG #441. This seed carries that entry's scope contract and its
recorded decision (2026-10-06, owner; do not reopen without new evidence).
The roadmap verb has not shipped, so no backward compatibility is kept.

## Outcome

A roadmap has exactly one stored copy of its content, and every command,
including seed refresh and `create --from-existing`, reads the accepted
version.

## Overview

Today a roadmap holds current content twice: the top-level `01-domain.md`
through `04-roadmap.md`, and immutable versions under `.roadmap-versions/`
selected by `accepted-head.json`. This plan makes the version store the only
content location from the first stage run, converts every reader to
`roadmap_versions.py:load_accepted_version`, deletes the unversioned (legacy)
mode, and adds a generated `INDEX.md` so a person browsing the folder can
find the current version.

## Problem statement

Enrollment (`roadmap.py:enroll_roadmap_root`) copies the top-level files into
the version store and promotion changes only `accepted-head.json`, so the two
copies differ from enrollment onward and each reader picks one. Two failures
follow:

- **An enrolled roadmap cannot reach execution.** `--refresh-seeds`,
  `--materialize`, `--apply`, and `--accept-seed` refuse on an enrolled
  roadmap (`roadmap.py:_require_unenrolled_roadmap_writer_or_raise`), so no
  seed can be derived from an accepted version. Integration's `integration-aidlc-mvp` has an
  empty `seed-state.json` and no way to fill it.
- **Six routes read stale top-level files with no enrollment check:**
  `create --from-existing <roadmap seed>` (`create.py:_load_roadmap_research_targets`,
  `cli/authoring.py:_confirm_invalidated_roadmap_seed`), `--escalate-feedback`
  (`roadmap_escalation_run.py:_resolve_preflight`), `--analyze-escalation`
  (`roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`),
  `--view escalations` and `--view impact-analyses`
  (`current_escalation_receipt`, `current_impact_analysis`), and default-target
  `--compare` (`roadmap_compare_run.py:_load_working_snapshot`), which shows
  promoted changes as reverted. `--apply` also reads `04-roadmap.md` before its
  guard (`roadmap.py:_reject_unmatched_operator_draft_fences`).

## In scope

- The first stage run: held stage results, the resume file, and root-version
  publication after stage 4.
- Converting the seed routes, `--apply`, `create --from-existing`, and
  `--compare` to the accepted version, and removing the escalation and
  impact-analysis routes (see Route disposition).
- Removing `--from-stage` and `--confirm-brief-rebind`.
- Generating `INDEX.md`.
- Deleting the legacy mode: `roadmap_revision_publish.py:require_unenrolled_roadmap_writer`
  and its refusals, `--enroll-version`, `--enroll-baselines`, the stage
  baselines, the revision checkpoint and `--restore-revision`,
  `--migrate-feedback-ledger`, the legacy publishers in
  `roadmap_revision_publish.py`, journal recovery for stage-file
  generations (recovery of a root-version generation stays), the unversioned
  fallback branches in readers that already prefer the accepted version
  (`roadmap_view.py:load_roadmap`,
  `roadmap_decision_settlement.py:build_decision_settlement_candidate`,
  `roadmap_decision_settlement_receipt.py:_unenrolled_receipt_proves_completion`),
  and the uncalled `roadmap_revision_run.py`.
- `ROADMAP_FORMAT.md`, `ROADMAP_FEEDBACK_FORMAT.md`, `docs/how-to/roadmap.md`,
  `docs/how-to/roadmap-demo.md`, `docs/ARCHITECTURE.md`,
  `integrations/shared/DIRECTIVES.md`, and the roadmap routing in
  `integrations/{claude,codex,cursor}/SKILL.md`, which name removed routes.

## Architecture

**Settled decisions (BACKLOG #441, 2026-10-06):**

- **No canonical draft.** The stage run holds each gate-clean stage result and
  publishes the root version only after stage 4 passes, through the existing
  root-version builders (`roadmap_versions.py:create_root_version`,
  `prepare_root_version_from_snapshot`). Nothing is written to the roadmap
  folder before then. Root publication is one journaled generation
  (`roadmap_revision_publish.py:publish_roadmap_generation`) in this order:
  version members and a `ledger-native` feedback ledger, then
  `accepted-head.json` last; after the head commits, the resume file is
  deleted and `INDEX.md` is written. A crash before the head commits is
  recovered by the existing no-head branch of
  `recover_roadmap_publication`, which this plan keeps.
- **Resume.** A failed first run leaves a resume file in the run-log
  directory, `.plan-tool/runs/<slug>/`, holding the gate-clean stages and the
  brief digest. Re-running the same command re-gates the held stages and
  continues from the first missing one. A brief whose digest differs from the
  resume file's refuses with a named error that names the file. The file is
  deleted only after the accepted head commits; a resume file found beside
  an accepted head is a leftover from a crash in that gap, and the stage
  command deletes it before refusing. Only the stage run reads it; one module
  owns its path.
- **After the root version.** The stage command refuses on a roadmap with an
  accepted head and names the candidate lifecycle (`--submit-feedback`,
  `--propose-candidate`) as the route for changes. `--from-stage` and
  `--confirm-brief-rebind` are removed. A changed product definition starts a
  successor slug, as `docs/how-to/roadmap.md` § 1 already directs.
- **One reader path.** Every command that reads roadmap content resolves it
  through `load_accepted_version`. `RoadmapStage.artifact_path` has no
  production reader.
- **`INDEX.md`.** Written at the roadmap folder root by one owning renderer,
  called after every command that writes a version, candidate admission,
  terminal resolution, supersession, or accepted-head record, once that
  write commits. A failed `INDEX.md` write is a warning and never
  fails or rolls back the command. No command reads it. It links the accepted
  head's four artifacts and lists every version in lineage order with its
  short id, kind, status, predecessor, and the feedback items it answered.
  Status values and the record each comes from:

  | Status | Source |
  |---|---|
  | `accepted head` | `accepted-head.json` |
  | `promoted` | an ancestor of the accepted head on its predecessor chain |
  | `active` | `candidate-admission.json` `active_candidate_version_id` |
  | `rejected`, `discarded`, `settled` | `candidate-terminal-resolutions/` `reason` |
  | `superseded` | `candidate-supersessions/` |

  Precedence follows the table top to bottom; a version matching no row is a
  defect the renderer reports rather than guesses. Precedence is
  load-bearing: a stack hop gets a supersession record when the stack is
  extended and is still promoted with it (Integration `8a802c3c…`, superseded by
  and promoted with `191f8156…`). All twelve Integration versions resolve to exactly
  one status under this order.
- **Route disposition.** Each roadmap route is either converted to the
  accepted version, removed, or unchanged:
  - Converted: `--refresh-seeds`, `--materialize`, `--apply`,
    `--accept-seed`, `create --from-existing` on a roadmap seed, and
    `--compare`, whose default target becomes the active candidate and which
    refuses without `--comparison-target` when no candidate is active (the
    base already defaults to the accepted head).
  - Removed: `--from-stage`, `--confirm-brief-rebind`, `--enroll-version`,
    `--enroll-baselines`, `--migrate-feedback-ledger`, `--restore-revision`,
    `--reopen-feedback` (replaced by `--reopen-ledger-feedback`),
    `--rewrite-structural` (its only publisher writes top-level files), the
    unenrolled `--settle-decision` branch, and the escalation chain:
    `--escalate-feedback`, `--analyze-escalation`, `--view escalations`,
    `--view impact-analyses`, and
    `roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`. Escalation
    selects an open feedback row embedded in an artifact
    (`roadmap_escalation_selection.py:select_receipt_feedback`); no stored
    version carries embedded feedback, both routes admit through the stage
    baselines, and their receipts and analyses are consumed only by
    `--rewrite-structural`. Structural changes go through the candidate
    lifecycle's structural route.
  - Unchanged: the candidate lifecycle (`--propose-candidate` and its alias
    `--revise-feedback`, `--review-candidate`, `--answer-question`,
    `--decide-candidate`, `--reject-candidate`, `--discard-candidate`,
    `--promote-review-seal`), the ledger commands, the enrolled
    `--settle-decision` and `--respond-decision-settlement` routes, and
    `--view summary|walk|ledger|index|seeds|html`, which read through
    `roadmap_view.py:load_roadmap`. The bare stage run is in scope above.
  - These lists elaborate #441 rather than widen it: each removed route
    already refuses on an enrolled roadmap or has no input in the version
    store, so it is legacy-only under #441's allowance, and the `INDEX.md`
    statuses are the ones the stored records actually carry.
- **Inventory first.** The route list comes from one code reading. The plan's
  first step traces callers and confirms or corrects it before any deletion.
  `source.json` and any other root sidecar are removed when every reader of
  them is a removed route; otherwise they stay and the plan states why.

## Out of scope

- Changing the candidate, review-seal, promotion, or version-record contracts.
- Changing the ledger format beyond removing legacy migration.
- A tool-driven migration for existing roadmaps. Integration is converted by hand
  after this ships.
- A read-only top-level mirror of the accepted version.
- Dates or timestamps in `INDEX.md` or version records.
- A version-store route for structural rewrites or revision restore; those
  needs, if they recur, are new backlog entries.

## Allowed behavior changes

Stage runs write no top-level artifacts and publish the root version after
stage 4; a failed first run resumes from its run-directory file; the stage
command refuses once an accepted head exists; the removed routes and flags
are gone or refuse with a named error; seed routes work on every roadmap;
`--compare` defaults its target to the active candidate and otherwise
requires `--comparison-target`; `INDEX.md` is written.

## Allowed reorganization

Deleting legacy-only modules and functions, and folding a converted reader
onto the accepted-version loader. Nothing else.

## Risks

- **Test churn.** Tests that build top-level artifacts as fixtures, or pin
  legacy refusals, are rewritten or deleted; `tests/test_roadmap_format.py`
  pins doc text that changes. Expect red sibling tests during the sweep.
- **Held results lengthen the window a crash can lose.** The resume file
  bounds it to the stage in flight.
- **The inventory can change the route list.** A route the trace shows is
  still needed and has no version-store path triggers the stop rule.

## Testing

- On a roadmap whose accepted head has advanced past its root,
  `--refresh-seeds` derives seeds from the accepted plans, and
  `create --from-existing` research targets match the accepted `02` and `03`.
- A stage-3 failure followed by a re-run calls the backend only for stages 3
  and 4.
- The roadmap folder holds no `0N-*.md` file at any point of a first run.
- A tree search finds no production read of `RoadmapStage.artifact_path`, of
  the resume file outside the stage run, or of `INDEX.md`.
- One test per converted route proves it never reads the folder root.
- A crash after the version members land but before `accepted-head.json`
  recovers through the no-head journal branch, and a re-run then publishes.
- `--compare` with no target compares the accepted head with the active
  candidate, and refuses when none is active.
- `INDEX.md` lists the accepted head and every candidate with its status.

## Acceptance criteria

- No command reads or writes roadmap content outside `.roadmap-versions/`.
- Seed routes and `create --from-existing` work on a roadmap with an advanced
  accepted head.
- A failed first run resumes without repeating gate-clean stages.
- The removed routes and flags are absent from the CLI and docs.
- `INDEX.md` is written as specified and read by nothing.
- The full suite is green.
- BACKLOG #441 is removed from `BACKLOG.md` when the plan ships.

## Stop / defer

If holding stage results until stage 4, or writing `INDEX.md`, needs a change
to the version, candidate, or promotion contracts, stop and raise it as its
own decision. Out-of-scope findings go to `BACKLOG.md` or `BUG_BACKLOG.md`.

## Deferred

- Timestamps for versions (a separate identity decision).
- BACKLOG #339's two open questions on the stage loop's "stopped" emission.
  This plan rewrites that loop; it must not settle #339, and its loop change
  must not make either answer harder.

## References

- `BACKLOG.md` #441 — source entry, decision, and scope contract.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — accepted
  head and direct-reader boundary; § "Revision checkpoint and restore" and
  § "Stage re-entry selection and bounded feedback" — removed surfaces.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger states, including the
  `migration-pending` state this plan removes.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`,
  `create_root_version`, `version_directory_path`.
- `plan_tool/roadmap.py` — the stage loop, enrollment, and seed routes.
- `plan_tool/roadmap_revision_publish.py` — the legacy publishers and guard.
- `docs/how-to/roadmap.md` — operator procedure to rewrite.

## Backlog reconciliation

The plan's final docs step removes BACKLOG #441 from `BACKLOG.md` once the
plan fully ships. While execution is pending, the entry stays and notes that
this plan is authored.
