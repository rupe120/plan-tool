> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Versioned From Birth
intent: A roadmap has exactly one stored copy of its content, and every command, including
  seed refresh and `create --from-existing`, reads the accepted version.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-versioned-from-birth.md
steps:
- id: 1
  title: 'Confirm the roadmap route inventory and record it on BACKLOG #441'
  intent: 'Confirms or corrects the converted/removed/unchanged route lists and the
    source.json and module-deletion dispositions from one caller trace, before any
    code is deleted, confirms the source.json reader list and whether any roadmap
    is in the migration-pending ledger state, and marks #441 as plan-authored.'
  files:
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/01-confirm-roadmap-route-inventory-record.md
  status: done
- id: 2
  title: Add a resume module that owns the first-run resume directory under .plan-tool/runs/<slug>/
  intent: Gives a failed first stage run one durable, single-owner place to keep its
    gate-clean stages, one file per stage, so a re-run continues without repeating
    them and a damaged held stage costs only its own regeneration.
  creates:
  - plan_tool/roadmap_stage_resume.py
  - tests/test_roadmap_stage_resume.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the confirmed run-directory layout and the statement that no other route reads
      the resume directory
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/02-resume-file-module-that-owns-first-run.md
  status: done
- id: 3
  title: Rewrite the first stage run to hold stage results and publish the root version
    after stage 4, refuse once an accepted head exists, and remove --from-stage and
    --confirm-brief-rebind (stops writing top-level 0N-*.md files and stops calling
    the revision checkpoint and stage baselines, whose code step 10 deletes; the resume
    directory is deleted only after the head commits, or when found beside an accepted
    head; a held stage that is unreadable or fails its re-gate is regenerated with
    a warning, while a changed brief and a folder with pre-head state (top-level 0N-*.md
    files, a ledger, seed state, a populated version store, or draft seeds) each refuse
    with a named error that states the operator's remedy)
  intent: Makes the version store the only content location from the first stage run,
    publishing one journaled root generation with a ledger-native ledger and the head
    written last, recovering any pending root journal before the pre-head-state refusal
    and before it reads the resume directory, never publishing a second root beside
    legacy files, and no longer reading or writing source.json.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 1
  - 2
  depends_on_notes:
    2: the resume read, per-stage write, and delete API plus the brief-digest refusal
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/03-rewrite-first-stage-run-hold-stage.md
  status: done
- id: 4
  title: Add the INDEX.md renderer for the accepted head and version lineage
  intent: Lets a person browsing the roadmap folder find the current version and every
    version's status, including `unrecorded` for a version with no status record,
    without reading the store's JSON.
  creates:
  - plan_tool/roadmap_index.py
  - tests/test_roadmap_index.py
  complexity: medium
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/04-index-md-renderer-accepted-head-version.md
  status: done
- id: 5
  title: Rewrite INDEX.md after every command that commits a version, candidate admission,
    terminal resolution, supersession, or accepted-head write, including root publication
    and the stage command's post-head refusal path (whole file replaced each time;
    a failed write warns and never rolls back; this step owns every INDEX.md call)
  intent: Keeps INDEX.md current after every version-store change without letting
    a failed index write fail the command.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/roadmap_version_promotion.py
  - plan_tool/roadmap_decision_settlement_enrolled.py
  - tests/test_roadmap_candidate_run.py
  - tests/test_roadmap_version_promotion.py
  complexity: medium
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: the root-publication commit point and the post-head refusal path
    4: the INDEX.md renderer
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/05-rewrite-index-md-after-every-command.md
  status: done
- id: 6
  title: Make --refresh-seeds, --materialize, --apply, and --accept-seed read the
    accepted version (enrolled-roadmap refusal retired; seed-state and plan-seed writes
    kept)
  intent: Lets an enrolled roadmap whose accepted head has moved past its root produce
    seeds and reach execution, and defines the one no-published-version error (with
    its hand-conversion pointer) that refuses a folder with no accepted head.
  files:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_seed_manifest.py
  - tests/test_roadmap.py
  - tests/test_roadmap_seed_manifest.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  depends_on_notes:
    3: roadmaps that exist only in the version store
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/06-make-refresh-seeds-materialize-apply.md
  status: done
- id: 7
  title: Make create --from-existing on a roadmap seed read research targets and invalidation
    state from the accepted version
  intent: Grounds create --from-existing research targets in the accepted 02 and 03
    instead of stale top-level files.
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/07-make-create-existing-on-roadmap-seed.md
  status: done
- id: 8
  title: Default the --compare target to the active candidate and refuse without --comparison-target
    when none is active (working-tree snapshot loader retired)
  intent: Stops --compare from showing promoted changes as reverted by comparing against
    stale top-level files, and refuses a folder with no accepted head with the no-published-version
    error the seed-routes step defines.
  files:
  - plan_tool/roadmap_compare_run.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_compare_run.py
  - tests/cli/test_roadmap_cmd.py
  complexity: low
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/08-default-compare-target-active-candidate.md
  status: done
- id: 9
  title: Remove the escalation, impact-analysis, and --rewrite-structural routes and
    the modules they alone use (a module is deleted only if the caller trace leaves
    it orphaned and trimmed otherwise; receipt and analysis writes retired; stored
    records left unread)
  intent: Retires routes that admit through stage baselines and select feedback embedded
    in artifacts, which no stored version carries, and orphans the structural-proof
    publisher in roadmap_revision_publish.py that only the retired rewrite route called.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - plan_tool/roadmap_view.py
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_impact_run.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_relations.py
  - plan_tool/roadmap_structural_revision_run.py
  - plan_tool/roadmap_structural_revision.py
  - plan_tool/roadmap_structural_revision_patch.py
  - plan_tool/roadmap_structural_revision_proof.py
  - plan_tool/roadmap_structural_operations.py
  - plan_tool/roadmap_revision_publish.py
  - CAPABILITIES.md
  - TESTING.md
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_relations.py
  - tests/test_roadmap_structural_revision_run.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_proof.py
  - tests/test_roadmap_structural_operations.py
  - tests/test_roadmap_revision_publish.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_view.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 1
  - 8
  depends_on_notes:
    1: the confirmed list of modules whose only callers are removed routes
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/09-remove-escalation-impact-analysis.md
  status: done
- id: 10
  title: 'Remove the legacy writer mode: --enroll-version, --enroll-baselines, --migrate-feedback-ledger,
    --restore-revision, --reopen-feedback, the unenrolled-writer guard, the legacy
    publishers, the stage baselines and the revision checkpoint and rollback code
    (step 3 already stopped calling them), and the unenrolled --settle-decision runner
    with its CLI fallback (the last caller of the legacy publishers); journal recovery
    stays, because its no-head rollback serves the first-run root publication'
  intent: Leaves the version store as the only write target so no code path can recreate
    a second copy of roadmap content, and deletes the source.json recorded-source
    helpers and its run-log event.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - docs/cli/roadmap.md
  - plan_tool/roadmap.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_revision_checkpoint.py
  - plan_tool/roadmap_revision_rollback.py
  - plan_tool/roadmap_revision_run.py
  - plan_tool/roadmap_feedback_reopen.py
  - plan_tool/roadmap_feedback_ledger.py
  - plan_tool/roadmap_feedback_ledger_run.py
  - plan_tool/roadmap_versions.py
  - plan_tool/roadmap_decision_settlement.py
  - plan_tool/roadmap_decision_settlement_run.py
  - plan_tool/roadmap_source.py
  - plan_tool/roadmap_artifacts.py
  - plan_tool/run_log.py
  - CAPABILITIES.md
  - TESTING.md
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_revision_checkpoint.py
  - tests/test_roadmap_revision_rollback.py
  - tests/test_roadmap_revision_run.py
  - tests/test_roadmap_feedback_reopen.py
  - tests/test_roadmap_feedback_ledger.py
  - tests/test_roadmap_decision_settlement_run.py
  - tests/test_roadmap_feedback_ledger_run.py
  - tests/test_roadmap_source.py
  - tests/test_run_log.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 3
  - 6
  - 9
  depends_on_notes:
    3: the stage run no longer calls the legacy publishers
    6: seed routes no longer call the unenrolled guard
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/10-remove-legacy-writer-mode-enroll.md
  status: done
- id: 11
  title: Remove the unversioned fallback branches from roadmap readers, and add a
    guard that no production code reads RoadmapStage.artifact_path, the resume directory
    outside the stage run, or INDEX.md, or reads or writes source.json
  intent: Closes the one-reader-path property so every accepted-roadmap reader resolves
    the four stage artifacts' content through load_accepted_version and every candidate
    reader through the stored-version loaders, and refuses --view and --settle-decision
    on a folder with no accepted head with the no-published-version error the seed-routes
    step defines (one refusal covers all six views), and keeps source.json from returning
    through the same no-production-reader guard.
  files:
  - plan_tool/roadmap_view.py
  - plan_tool/roadmap_decision_settlement.py
  - plan_tool/roadmap_decision_settlement_receipt.py
  - plan_tool/cli/roadmap_cmd.py
  - tests/test_roadmap_view.py
  - tests/test_roadmap_decision_settlement.py
  - tests/test_roadmap_decision_settlement_receipt.py
  - tests/test_roadmap.py
  complexity: medium
  change_type: feature
  enforce_test_authoring: false
  depends_on:
  - 9
  - 10
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/11-remove-unversioned-fallback-branches.md
  status: done
- id: 12
  title: 'Update the roadmap docs, skills, directives, and generated CLI reference
    for the version-only store, and remove BACKLOG #441'
  intent: Leaves no doc naming a removed route (outside dated replacement and hand-conversion
    notes) and documents the resume directory and the remedy for a brief-digest refusal,
    the post-head stage refusal, the no-published-version refusal and its hand-conversion
    procedure for both a no-head folder and an enrolled folder with leftover top-level
    files, the --compare default, INDEX.md, and --reopen-ledger-feedback as the replacement
    for --reopen-feedback.
  files:
  - ROADMAP_FORMAT.md
  - ROADMAP_FEEDBACK_FORMAT.md
  - docs/how-to/roadmap.md
  - docs/how-to/roadmap-demo.md
  - docs/ARCHITECTURE.md
  - integrations/shared/DIRECTIVES.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - integrations/cursor/SKILL.md
  - README.md
  - RUNBOOK.md
  - DATA_CONTRACT.md
  - CLAUDE.md
  - docs/cli/roadmap.md
  - tests/test_roadmap_format.py
  - BACKLOG.md
  complexity: high
  change_type: non-code
  depends_on:
  - 3
  - 5
  - 6
  - 7
  - 8
  - 9
  - 10
  - 11
  detail: docs/implementation-plans/plan-details/roadmap-versioned-from-birth/12-update-roadmap-docs-skills-directives.md
  status: done
---
# Roadmap Versioned From Birth

## Overview

Today a roadmap holds current content twice: the top-level `01-domain.md`
through `04-roadmap.md`, and immutable versions under `.roadmap-versions/`
selected by `accepted-head.json`. This plan makes the version store the only
content location from the first stage run, converts every accepted-roadmap reader to
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

## Architecture

**Settled decisions (BACKLOG #441, 2026-10-06):**

- **No canonical draft.** The stage run holds each gate-clean stage result and
  publishes the root version only after stage 4 passes, through the existing
  root-version builders (`roadmap_versions.py:create_root_version`,
  `prepare_root_version_from_snapshot`). Nothing is written to the roadmap
  folder before then. Root publication is one journaled generation
  (`roadmap_revision_publish.py:publish_roadmap_generation`) in this order:
  version members and a `ledger-native` feedback ledger, then
  `accepted-head.json` last; after the head commits, the resume directory is
  deleted and `INDEX.md` is written (the `INDEX.md` call belongs to the
  `INDEX.md` hook step, not to the stage-run step). A crash before the head
  commits is
  recovered by the existing no-head branch of
  `recover_roadmap_publication`, which this plan keeps; that branch rolls the
  partial generation back to its recorded pre-publication state. A re-run
  runs that recovery before it reads the resume directory, then re-gates the
  held stages and republishes from them, so a stale journal never publishes a
  root and a changed brief still refuses on its digest.
- **Resume.** A failed first run leaves a resume directory,
  `.plan-tool/runs/<slug>/roadmap-stage-resume/`, inside the run-log
  directory `.plan-tool/runs/<slug>/` (which also holds the run logs and is
  never the directory to delete), holding one file per gate-clean stage and
  one file with the brief digest. Re-running the same command re-gates
  the held stages in order and continues from the first stage that is missing
  or fails its re-gate; a held stage that is unreadable or fails its re-gate
  is regenerated, as are the stages after it, with a warning that names the
  file, because only the stage that failed is lost and no valid result is
  discarded. The one refusal is a brief whose digest differs from the held
  digest, which makes every held stage stale: the named error says the
  remedy is to restore the brief, delete the named `roadmap-stage-resume/`
  directory by hand, or start a successor slug. The directory is deleted only after the accepted
  head commits; one found beside an accepted head is a leftover from a crash
  in that gap, and the stage command deletes it before refusing. Only the
  stage run reads it; one module owns its path.
- **After the root version.** The stage command refuses on a roadmap with an
  accepted head and names the candidate lifecycle (`--submit-feedback`,
  `--propose-candidate`) as the route for changes. It also refuses a folder
  with no accepted head that already holds any pre-head roadmap state
  (top-level `0N-*.md` files, `feedback-ledger.yaml`, `seed-state.json`, a
  `.roadmap-versions/` directory with entries, or draft seeds) with one named
  error that lists what it found and points at hand conversion, so a second
  root is never published beside old files and no ledger or seed state is
  silently replaced. Journal recovery runs before this refusal and before the
  resume directory is read; a partial root generation counts as pre-head state
  only if recovery leaves it behind, so a crash after the version members land
  recovers and republishes instead of refusing. Every accepted-roadmap
  reader on a folder with no accepted head (`--view`, the seed routes,
  `--settle-decision`, and `--compare`) refuses with one named error that
  says the roadmap has no published version and, when top-level `0N-*.md`
  files exist, points at the same hand conversion. Hand conversion is
  documented in `docs/how-to/roadmap.md` § 1: move or delete the files the
  error lists (deleting `feedback-ledger.yaml` discards its feedback rows) and
  regenerate under the same slug, or start a successor slug from the brief.
  The seed-routes step defines this one error, including its hand-conversion
  pointer, as the first consumer; the `--compare` step and the reader-closing
  step reuse it, and the reader-closing step adds the `--view` and
  `--settle-decision` refusals. All six remaining views (`summary`, `walk`,
  `ledger`, `index`, `seeds`, `html`) share the single `load_roadmap` call at
  the top of the view handler, so one refusal there covers each of them. Top-level `0N-*.md` files beside an accepted
  head (an enrolled roadmap, Integration's shape), along with `source.json`,
  `.roadmap-baselines/`, and `.roadmap-rollbacks/`, are inert leftovers that
  no command reads or flags; hand conversion there is deleting them. The removed
  `--migrate-feedback-ledger` leaves a `migration-pending` ledger with no
  route, so such a roadmap is regenerated under a successor slug; the
  inventory step confirms whether any roadmap in this repository or in Integration
  is in that state (Integration's ledger is `ledger-native`). A ledger file that
  still carries the removed `migration-pending` state is refused on read with
  a named message whose remedy is a successor slug; the ledger-removal step
  owns this refusal, and the ledger parser keeps just enough handling of that
  one value to produce the message. `--from-stage` and
  `--confirm-brief-rebind` are removed. A changed product definition starts a
  successor slug, as `docs/how-to/roadmap.md` § 1 already directs.
- **One reader path.** "Roadmap content" means the bodies of the four stage
  artifacts (domain, constraints, components, plans). A command that reads
  the accepted roadmap resolves that content through `load_accepted_version`;
  a candidate command reads its candidate's stored version through the
  stored-version loaders, as it does today. The only roadmap-folder files
  outside `.roadmap-versions/` are the feedback ledger, `seed-state.json`,
  `INDEX.md`, the draft-seed directory, and the evidence directory
  `.plan-tool/evidence/` inside the roadmap folder (decision-settlement
  receipts, plus unread escalation and impact-analysis records left on disk);
  the resume directory lives in the repository's run-log directory, a
  different `.plan-tool/`. `RoadmapStage.artifact_path` has no production reader.
- **`INDEX.md`.** Written at the roadmap folder root by one owning renderer,
  called after every command that writes a version, candidate admission,
  terminal resolution, supersession, or accepted-head record, once that
  write commits, including root publication. The stage command's refusal
  path on a roadmap with an accepted head, which already deletes a leftover
  resume directory, also rewrites `INDEX.md` best-effort, so a crash between the
  head commit and the first `INDEX.md` write heals on the next run. A failed
  `INDEX.md` write is a warning and never fails or rolls back the command. No command reads it
  (`--view index`, the citation map rendered from the store, is unrelated to
  the file). It links the accepted
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
  | `unrecorded` | a stored version with none of the records above, as a crash between the version write and its admission leaves |

  Precedence follows the table top to bottom; the `unrecorded` row is the
  last, so every stored version has exactly one status, and the renderer
  still writes the rest of the file when it lists one. Precedence is
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
    `roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` (the module is
    trimmed, not deleted, while surviving code imports its other symbols). Escalation
    selects an open feedback row embedded in an artifact
    (`roadmap_escalation_selection.py:select_receipt_feedback`); no stored
    version carries embedded feedback, both routes admit through the stage
    baselines, and their receipts and analyses are consumed only by
    `--rewrite-structural`. Structural changes go through the candidate
    lifecycle's structural route.
  - Unchanged: the candidate lifecycle (`--propose-candidate` and its alias
    `--revise-feedback`, `--review-candidate`, `--answer-question`,
    `--decide-candidate`, `--reject-candidate`, `--discard-candidate`,
    `--promote-review-seal`), the ledger commands including
    `--reopen-ledger-feedback` (the replacement for the removed
    `--reopen-feedback`), the enrolled
    `--settle-decision` and `--respond-decision-settlement` routes, and
    `--view summary|walk|ledger|index|seeds|html`, which read through
    `roadmap_view.py:load_roadmap`. The bare stage run is in scope above.
  - These lists elaborate #441 rather than widen it: each removed route
    already refuses on an enrolled roadmap or has no input in the version
    store, so it is legacy-only under #441's allowance, and the `INDEX.md`
    statuses are the ones the stored records actually carry.
- **Generated CLI reference.** Every step that changes a roadmap flag or its
  help text regenerates `docs/cli/roadmap.md` in the same step
  (`python -m plan_tool.cli_reference --write`), because the full-suite gate
  runs its drift test at every step, not only at the docs step.
- **Retirement split.** The stage-run step stops calling the stage baselines
  and the revision checkpoint and stops writing top-level files; the
  legacy-writer step deletes their code, `--restore-revision`, and their
  tests. No step deletes code a later step still calls.
- **Inventory first.** The route list comes from one code reading. The plan's
  first step traces callers and confirms or corrects it before any deletion.
  `source.json` is removed. Its readers are the stage run's brief admission
  and rebind (replaced by the root version's stored `brief.md` and
  `brief_digest`, and the resume directory's digest file for a first run), the revision
  checkpoint, the impact snapshot, the uncalled revision run, and the run-log
  event for its first write; every one is removed or replaced here, and no
  candidate, ledger, or seed code reads it. The roadmap folder holds no
  `source.json` after a first run. The inventory step re-checks that reader
  list; a surviving reader it finds triggers the stop rule.

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

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Changing the candidate, review-seal, promotion, or version-record contracts.
- Changing the ledger format beyond removing legacy migration.
- A tool-driven migration for existing roadmaps. Integration is converted by hand
  after this ships.
- A read-only top-level mirror of the accepted version.
- Dates or timestamps in `INDEX.md` or version records.
- A version-store route for structural rewrites or revision restore; those
  needs, if they recur, are new backlog entries.

## Risks

- **Test churn.** Tests that build top-level artifacts as fixtures, or pin
  legacy refusals, are rewritten or deleted; `tests/test_roadmap_format.py`
  pins doc text that changes. Expect red sibling tests during the sweep.
- **Held results lengthen the window a crash can lose.** The resume
  directory bounds it to the stage in flight.
- **The inventory can change the route list.** A route the trace shows is
  still needed and has no version-store path triggers the stop rule.

## Testing

- On a roadmap whose accepted head has advanced past its root,
  `--refresh-seeds` derives seeds from the accepted plans, and
  `create --from-existing` research targets match the accepted `02` and `03`.
- A stage-3 failure followed by a re-run calls the backend only for stages 3
  and 4.
- The roadmap folder holds no `0N-*.md` file and no `source.json` at any point
  of a first run.
- A tree search (the reader-closing step's guard) finds no production read of
  `RoadmapStage.artifact_path`, of the resume directory outside the stage run, or
  of `INDEX.md`, and no production read or write of `source.json`.
- One test per converted route proves it never reads the folder root.
- A crash after the version members land but before `accepted-head.json`
  recovers through the no-head journal branch, and a re-run then publishes.
  When the crash left both a pending journal and a resume directory, the re-run
  recovers first and publishes only from the held stages, and a changed brief
  refuses on its digest.
- On a folder with no accepted head, each of the six views (`summary`,
  `walk`, `ledger`, `index`, `seeds`, `html`), a seed route,
  `--settle-decision`, and `--compare` refuses with the same named error.
- `--compare` with no target compares the accepted head with the active
  candidate, and refuses when none is active.
- `INDEX.md` lists the accepted head and every candidate with its status.
- Each command that writes a version, candidate admission, terminal
  resolution, supersession, or accepted-head record rewrites `INDEX.md`.
- A failing `INDEX.md` write warns and leaves the command's committed result
  intact with its normal exit code.
- A stored version with no admission, terminal, supersession, or head record
  is listed with status `unrecorded`, and the rest of `INDEX.md` is still
  written.
- A held stage file that is unreadable or fails its re-gate is regenerated
  with a warning naming it, along with the stages after it, and the stages
  before it are not re-run.
- A changed brief refuses with a named error whose message states the
  remedy (restore the brief, delete the named `roadmap-stage-resume/`
  directory, or start a successor slug), and the stage run never deletes the held stages itself.
- A crash after the version members and ledger land but before
  `accepted-head.json` recovers through the no-head journal branch and
  republishes, and does not hit the pre-head-state refusal.
- Loading a ledger file that carries the removed `migration-pending` state
  refuses with the named successor-slug message, not a generic invalid-value
  error.
- A folder with no accepted head but any pre-head state (top-level `0N-*.md`
  files, a ledger, `seed-state.json`, a populated `.roadmap-versions/`, or
  draft seeds) refuses with an error listing what it found, and a stage run
  publishes no second root beside it.
- A crash after the head commits but before `INDEX.md` is written leaves a
  roadmap whose next stage-command refusal rewrites `INDEX.md`.

## Acceptance criteria

- `.roadmap-versions/` holds the only stored copy of accepted roadmap
  content, and no command reads or writes the four stage artifacts' content
  anywhere else in the roadmap folder. The feedback ledger, `seed-state.json`,
  `INDEX.md`, the draft-seed directory, and the evidence directory
  `.plan-tool/evidence/` (inside the roadmap folder, not the repository's
  run-log `.plan-tool/`) are the only other roadmap-folder files. The resume directory (`.plan-tool/runs/<slug>/roadmap-stage-resume/`) is a
  transient pre-publication holding area in the run-log directory, not a
  roadmap-folder file, read and written only by
  the stage run.
- Seed routes and `create --from-existing` work on a roadmap with an advanced
  accepted head.
- A failed first run resumes without repeating gate-clean stages.
- A ledger file carrying the removed `migration-pending` state is refused on
  read with a message naming the successor-slug remedy.
- The removed routes and flags are absent from the CLI, and the docs name
  them only in dated replacement and hand-conversion notes.
- `INDEX.md` is written as specified and read by nothing.
- The full suite is green.
- BACKLOG #441 is removed from `BACKLOG.md` when the plan ships.

## Deferred

- Timestamps for versions (a separate identity decision).
- BACKLOG #339's two open questions on the stage loop's "stopped" emission.
  This plan rewrites that loop; it must not settle #339, and its loop change
  must not make either answer harder.
