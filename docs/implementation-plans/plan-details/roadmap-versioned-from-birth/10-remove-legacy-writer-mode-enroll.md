# Step 10 — Remove the legacy writer mode, baselines, checkpoint, and `source.json` helpers (the no-head journal rollback stays)

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step deletes the legacy (unversioned, in-place) writer mode from the roadmap code. It removes the CLI routes `--enroll-version`, `--enroll-baselines`, `--migrate-feedback-ledger`, `--restore-revision` (with `--confirm-restore-revision`), and `--reopen-feedback` from `plan_tool/cli/roadmap_cmd.py`. It deletes the modules `plan_tool/roadmap_revision_checkpoint.py`, `plan_tool/roadmap_revision_rollback.py`, `plan_tool/roadmap_revision_run.py`, and `plan_tool/roadmap_feedback_reopen.py`. It removes the legacy publishers and the unenrolled-writer guard from `plan_tool/roadmap_revision_publish.py`. It also deletes the `source.json` recorded-source helpers and the run-log events built on them. The key decision is that **deletion follows a caller trace, not the file list**: several callers outside the declared list import the legacy symbols and must be trimmed in this step. On green, the version store is the only write target, `recover_roadmap_publication` keeps its no-head rollback and completed-generation paths, and the `migration-pending` ledger state is no longer modelled, and a ledger file that carries it is refused with a named successor-slug message.

## Table of Contents

- [Why](#why) — what the legacy mode still does after steps 3, 6, and 9
- [Input](#input) — what earlier steps supply and what the trace must settle first
- [Files (creates vs edits)](#files-creates-vs-edits) — deletions, edits, and the declared additions
- [Implementation](#implementation) — removal order, recovery rule, constraints
- [Tests](#tests) — what is deleted, what is rewritten, what is added
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to others

## Why

- After step 3 the stage run no longer calls the revision checkpoint or the stage baselines. After step 6 the seed routes no longer call the unenrolled-writer guard. After step 9 the escalation, impact-analysis, and structural-rewrite routes are gone. What remains is dead legacy code plus a few callers that still import it.
- Leaving it in place keeps a second write target alive. `publish_stage_artifact` and `publish_revision_candidate` in `plan_tool/roadmap_revision_publish.py` write top-level `0N-*.md` files. The plan's intent is one stored copy that every command reads, and no code path may recreate a second one.
- `recover_roadmap_publication` has one generic path after the `accepted is not None` block: it compares each member's bytes to the recorded `old_bytes` and `new_bytes` and rolls the generation back. That path serves a legacy stage-file generation and also a root-version generation with no head, which is exactly the crash the first stage run must recover from. It must stay; only the writers that create stage-file generations are legacy.
- `plan_tool/roadmap_feedback_ledger.py` still models a `migration-pending` ledger state, and `plan_tool/roadmap_feedback_ledger_run.py:migrate_legacy_feedback` still imports embedded legacy feedback. Step 3 makes every new ledger ledger-native, so both are unreachable for new roadmaps.

## Input

- **Step 1 output:** the `BACKLOG.md` #441 inventory. It lists these routes as removed and records the `source.json` reader list and the `migration-pending` finding. Take the removal list from there. If this step's caller trace disagrees, correct the record and raise it under the plan's stop rule.
- **Step 3 output:** the stage run publishes the root version itself, refuses once a head exists, and no longer calls `enroll_roadmap_baselines`, `capture_checkpoint`, or `_write_brief_source`. Read the landed `plan_tool/roadmap.py` before deleting anything there.
- **Step 6 output:** the seed routes no longer call `_require_unenrolled_roadmap_writer_or_raise` or `require_unenrolled_roadmap_writer`.
- **Step 9 output:** the escalation, impact, and structural-rewrite routes and their modules are gone or trimmed. `plan_tool/roadmap_structural_revision_run.py` calls `publish_structural_revision_proof` and `require_unenrolled_roadmap_writer`, so it must already be deleted. If it still exists at implementation time, step 9 is incomplete. Stop and raise it.
- **Caller trace (run first, at HEAD, by identifier and by vocabulary).** Search these identifiers across `plan_tool/` and `tests/`: `require_unenrolled_roadmap_writer`, `EnrolledRoadmapWriteError`, `publish_stage_artifact`, `enroll_stage_baselines`, `publish_revision_candidate`, `publish_feedback_reopen_candidate`, `publish_structural_revision_proof`, `capture_checkpoint`, `restore_roadmap_revision`, `run_confirmed_feedback_reopen`, `migrate_legacy_feedback`, `enroll_roadmap_baselines`, `run_local_feedback_revision`, `read_recorded_brief_source`, `RoadmapSourceResolved`, `RoadmapSourceRecorded`, `MIGRATION_PENDING`. Also search the words "legacy", "unenrolled", "baseline", "checkpoint", "recorded brief". Known callers outside the declared list at HEAD:
  - `plan_tool/roadmap_decision_settlement_run.py` — imports `EnrolledRoadmapWriteError`, `publish_stage_artifact`, `require_unenrolled_roadmap_writer`. It is also imported by `plan_tool/roadmap_decision_settlement_enrolled.py` and by `plan_tool/cli/roadmap_cmd.py`, so it cannot be deleted whole. Trim only its legacy write path.
  - `plan_tool/roadmap_decision_settlement.py` — a comment and a branch about a `migration-pending` ledger.
  - `plan_tool/data_contract.py` — registers `RoadmapSourceResolved`, `RoadmapSourceRecorded`, and `RoadmapSourceAdmission` events. Its drift guard is `tests/test_data_contract.py`.
  - `plan_tool/roadmap_impact_snapshot.py` — reads `read_recorded_brief_source`. Step 9 decides whether it survives. Confirm the landed state.
- **Limit:** a static trace shows importers, not roadmaps on disk. The tests cannot show that Integration's hand-converted folder works after this step. The post-ship hand run covers that.

## Files (creates vs edits)

- **New files:** none.
- **Deleted files:**
  - `plan_tool/roadmap_revision_checkpoint.py`, `plan_tool/roadmap_revision_rollback.py`, `plan_tool/roadmap_revision_run.py`, `plan_tool/roadmap_feedback_reopen.py`
  - `tests/test_roadmap_revision_checkpoint.py`, `tests/test_roadmap_revision_rollback.py`, `tests/test_roadmap_revision_run.py`, `tests/test_roadmap_feedback_reopen.py`
- **Existing files (edits only), all in the declared list:**
  - `plan_tool/cli/roadmap_cmd.py` — remove the six routes' parser entries, handlers, pre-dispatch checks, module docstring paragraphs, and the `--enroll-baselines` hint near the comparison error path. Remove the restore hint printed after a failed run.
  - `docs/cli/roadmap.md` — regenerate with `python -m plan_tool.cli_reference --write` after the parser drops the removed legacy flags; the full-suite gate runs the drift test in `tests/cli/test_cli_reference.py` at this step.
  - `plan_tool/roadmap.py` — remove `enroll_roadmap_baselines`, `BaselineEnrollmentResult`, `_require_unenrolled_roadmap_writer_or_raise`, the `_checkpoint_*` helpers, `_write_brief_source`, and the `read_recorded_brief_source` uses (with the source events they emit). Keep `enroll_roadmap_root` only if step 3 left it as a live caller; otherwise delete it.
  - `plan_tool/roadmap_revision_publish.py` — remove `require_unenrolled_roadmap_writer`, `EnrolledRoadmapWriteError`, `publish_stage_artifact`, `enroll_stage_baselines`, `publish_revision_candidate`, `publish_feedback_reopen_candidate`, `publish_structural_revision_proof`, and their private helpers (`_require_successful_structural_proof`, `_require_current_proof_binding`, `_structural_stage_table`, `_stage_replacement_boundary`, `_require_feedback_snapshot*`). Remove `StaleFeedbackPublicationError`, `StructuralRevisionPublicationError`, `StaleStructuralRevisionPublicationError`, and the `_RoadmapStage` protocol if nothing else uses them. Narrow `recover_roadmap_publication` (see Implementation).
  - `plan_tool/roadmap_feedback_ledger.py` — remove `LedgerState.MIGRATION_PENDING`, make a ledger file that still carries `migration-pending` fail on read with a message that names the successor-slug remedy, keeping only the parsing of that one value needed to produce the message (replacing the old migration-pending refusal in `check_ledger_processing_ready`), and `LEGACY_BLANK_REQUEST_MARKER` / `LegacyFeedbackSource` if the trace shows no surviving use.
  - `plan_tool/roadmap_feedback_ledger_run.py` — remove `migrate_legacy_feedback`, `_read_legacy_items`, and the `migration-required` / `migrated` / `already-migrated` result values. Keep reviewer mutations.
  - `plan_tool/roadmap_versions.py` — remove only code the trace proves has no caller left (for example enrollment-only helpers). Do not change the version, head, or candidate records.
  - `plan_tool/roadmap_source.py` — delete the recorded-source readers: `read_recorded_brief_source`, `load_recorded_brief_path`, `digest_source_record`, `RecordedBriefSource`. Keep `read_brief_text`, `digest_decoded_text`, and `parse_carried_decisions` (step 3 and the stage run use them).
  - `plan_tool/roadmap_artifacts.py` — remove `brief_source_path` and `BRIEF_SOURCE_FILENAME` once no caller is left.
  - `plan_tool/run_log.py` — delete `RoadmapSourceResolved`, `RoadmapSourceRecorded`, and the revision-run events that only the deleted modules emit (`RoadmapLocalRevisionPreflight`, `RoadmapLocalRevisionAttempt`, `RevisionFeedbackDelivered`) if the trace shows no other emitter. Remove them from the event union. Keep `RoadmapSourceAdmission` only if a surviving caller emits it.
  - `CAPABILITIES.md` — drop the surfaces for the removed flags and modules. `plan_tool/capability_catalog.py:check_capabilities` raises `absent-surface` for a capability that cites a missing module, and there is no allowlist.
  - `TESTING.md` — remove invoker-neutralization rows for deleted orchestrators (`roadmap_revision_run`).
  - `tests/test_roadmap_revision_publish.py`, `tests/test_roadmap_feedback_ledger_run.py`, `tests/test_roadmap_source.py`, `tests/test_run_log.py`, `tests/test_roadmap.py`, `tests/cli/test_roadmap_cmd.py` — see Tests.
- **Declared additions (outside the step's `files:` list; the trace requires them):**
  - `plan_tool/roadmap_decision_settlement_run.py` — delete `run_unenrolled_decision_settlement`, `ENROLLED_ROADMAP_FALLBACK_REFUSAL`, `_StaleDecisionSettlementSource`, and the `require_unenrolled_roadmap_writer`, `publish_stage_artifact`, and `EnrolledRoadmapWriteError` imports and handling. This runner is the last production caller of the legacy publishers, so it goes in this step: deleting the publishers while it still imports them would leave the step red. Keep `DecisionSettlementRunResult`, `DecisionSettlementRunOutcome`, `DecisionSettlementRunRefusal`, and `_STATUS_BY_OUTCOME` if `plan_tool/roadmap_decision_settlement_enrolled.py` imports them; delete the module only if nothing survives.
  - `plan_tool/cli/roadmap_cmd.py` — `_cmd_roadmap_decision_settlement` calls the enrolled runner directly. Remove the unenrolled-first attempt, the fallback condition, and the unenrolled import. Step 11 changes the no-head verdict to the no-published-version refusal.
  - `plan_tool/roadmap_decision_settlement.py` — delete the migration-pending comment and branch.
  - `plan_tool/data_contract.py`, `tests/test_data_contract.py`, `DATA_CONTRACT.md` — drop the removed run-log events from the registry and the doc together, so the drift guard stays green.
  - `tests/test_roadmap_decision_settlement_run.py` and `tests/test_roadmap_feedback_ledger.py` — update cases that pinned the legacy path or the `migration-pending` state.

## Implementation

**Behavior that must hold when the step is done:**

- **No stage-file writer.** No production code writes `01-domain.md`, `02-constraints.md`, `03-components.md`, or `04-roadmap.md` at the top level, or a stage baseline, checkpoint, or `source.json`. The version store is the only write target.
- **Journal recovery keeps its no-head rollback.** `recover_roadmap_publication` is not edited in this step. Its `accepted is not None` path (using `_is_completed_version_owned_generation`) and its generic no-head path (compare member bytes to `old_bytes`/`new_bytes`, restore with `_replace_generation_members`) both stay, because the no-head path is what rolls back a crashed first-run root publication. Delete the legacy stage-file writers and their callers, not the recovery that a root generation shares with them.
- **Removed flags are unknown flags.** argparse rejects each of the six flags as an unrecognized argument. Do not keep a stub that prints a deprecation message (the plan names no replacement).
- **Surviving routes keep their behavior.** The writer guard (`roadmap_writer_guard`, `roadmap_reader_guard`), `publish_roadmap_generation`, `seed-state.json` writes, draft-seed writes, `plan-seeds/` promotion, candidate, review-seal, and promotion routes are unchanged.

**Recommended approach (the order has latitude; the end state does not):**

- **Trace first, then delete leaves before callers.** Delete the four modules and their tests, then fix the importers the trace lists, then remove the now-unused symbols from `plan_tool/roadmap_revision_publish.py`, then the source helpers and events. Run `uv run pytest -m "not integration" tests/ -q -n auto` between groups so a missed importer fails at import time, not later.
- **Trim, don't rewrite, `plan_tool/roadmap_decision_settlement_run.py`.** The enrolled settlement route reuses parts of it. Remove only the branches the deleted guard and publisher served.
- **`migration-pending` removal.** Step 1 records whether any roadmap is in that state. If the record says one exists, stop and raise it under the plan's stop rule before removing the state. Otherwise remove the enum member and every branch on it together, and make a ledger file that names the removed state fail `load_ledger` with a named message whose remedy is a successor slug. Keep that one literal in a single module constant used only to produce the message. Do not add a migration path.
- **Rejected alternative:** keep `enroll_roadmap_baselines` and the stage-file recovery branch "for old folders". The plan converts Integration by hand and names no tool-driven migration, so a kept branch has no caller and would keep the second write target alive.

**Constraints and gotchas:**

- **Sweep vocabulary, not only identifiers.** After deleting, search the words "enroll", "unenrolled", "baseline", "checkpoint", "restore", "recorded brief", "legacy" across `plan_tool/`, `docs/`, `ROADMAP_FORMAT.md`, and `ROADMAP_FEEDBACK_FORMAT.md`. `ROADMAP_FORMAT.md` § "Revision checkpoint and restore" describes removed surfaces. The doc rewrite belongs to the plan's docs step (the plan-level references name it); this step lists each stale doc site in its commit message so that step can find them.
- **Do not delete a shared leaf by name.** `plan_tool/roadmap_source_identity.py` supplies `pending_generation_path`, `load_pending_generation`, `GenerationMember`, and `PendingGeneration`, which the version store and the surviving recovery use. Only its baseline functions (`baseline_path`, `baseline_record`, `load_baseline_record`, `admit_baseline_backed_source`, `compare_baseline`) are legacy. Remove them only where the trace shows no surviving caller, and keep the file out of scope otherwise.
- **`RoadmapStage.artifact_path` and the `domain_path` / `constraints_path` / `components_path` / `plans_path` helpers** are tracked by step 1's inventory. This step removes the callers it owns; leave any that the plan assigns to another step.
- **Duplication guard.** `tests/test_duplication.py` fails if deleting one of a deliberately duplicated pair breaks its second check. Run it after the deletions.
- **Import-cycle rules.** `plan_tool/roadmap_revision_publish.py` must not gain first-party imports in this step.

## Tests

Tests deleted with their modules:

- `tests/test_roadmap_revision_checkpoint.py`, `tests/test_roadmap_revision_rollback.py`, `tests/test_roadmap_revision_run.py`, `tests/test_roadmap_feedback_reopen.py` — removed whole.

Tests rewritten or removed in surviving files (approx. counts are unknown until the trace runs; read each case):

- `tests/test_roadmap_revision_publish.py` — remove cases for the removed publishers, the unenrolled guard, and stale-feedback and structural publication errors. Keep cases for the writer and reader guards, `publish_roadmap_generation`, and enrolled decision settlement.
- `tests/test_roadmap_feedback_ledger_run.py` — remove migration cases. Keep reviewer mutation and grouped-render cases.
- `tests/test_roadmap_source.py` — remove recorded-source reader cases. Keep carried-decision and digest cases.
- `tests/test_run_log.py` — remove cases for the deleted events and update the union and round-trip lists.
- `tests/test_roadmap.py` — remove baseline-enrollment and checkpoint cases. A red sibling test here is expected; decide per case whether it pins removed behavior (delete) or a surviving carve-out (assert it).
- `tests/cli/test_roadmap_cmd.py` — remove cases for the six routes (including the `enroll` stub the heuristic flagged, which is a fake for `--enroll-baselines`).

New cases:

- `test_removed_legacy_flags_are_rejected_by_the_parser` — parametrized over all six flags (plus `--confirm-restore-revision`): each exits non-zero as an unrecognized argument, so a flag cannot silently return.
- `test_pending_root_generation_with_no_head_still_rolls_back` — a pending root-version generation whose head selector was not written makes `recover_roadmap_publication` restore its recorded pre-publication state and clear the journal. It pins the path the first stage run depends on.
- `test_completed_version_owned_generation_is_still_recognized` — a pending generation whose head and members all landed is recognized as completed and its journal cleared. It pins the `accepted is not None` path the plan keeps.
- `test_migration_pending_ledger_is_refused_with_the_successor_slug_remedy` — a ledger file with `ledger_state: migration-pending` fails on read, the message names a successor slug, and the file is left unchanged.
- `test_settle_decision_dispatches_to_the_enrolled_runner_directly` — the handler never imports or calls an unenrolled runner, and a roadmap with a head settles through the enrolled runner as before.
- `test_no_production_module_writes_a_top_level_stage_file` — a source scan over every roadmap module under `plan_tool/` (file names beginning `roadmap`) for the removed writer names (`publish_stage_artifact`, `enroll_stage_baselines`, `capture_checkpoint`, `_write_brief_source`). It only catches names; step 11 owns the broader guard.
- `tests/test_data_contract.py` — the registry/doc drift guard stays green after the event removal. Break it by mutation: re-add one removed event to the registry only and watch it go red.

### Tests for this step

- Every case above, plus the surviving suites for the files in scope, must be green before the step is finished: `uv run pytest tests/ -q -n auto`, including `tests/test_duplication.py` and `tests/cli/test_roadmap_cmd.py`.
- Verify the two recovery tests by mutation: delete the generic no-head rollback and confirm the rollback test goes red; delete the version-owned branch and confirm the completed-generation test goes red.

## Acceptance criteria

- `plan_tool/roadmap_revision_checkpoint.py`, `plan_tool/roadmap_revision_rollback.py`, `plan_tool/roadmap_revision_run.py`, and `plan_tool/roadmap_feedback_reopen.py` do not exist, and their four test files are gone.
- `plan-tool roadmap <slug> --enroll-version`, `--enroll-baselines`, `--migrate-feedback-ledger`, `--restore-revision`, and `--reopen-feedback` each fail as an unrecognized argument.
- `plan-tool roadmap <slug> --revise-feedback` still parses and runs the same candidate proposal as `--propose-candidate` (the alias is unchanged).
- `rg 'run_unenrolled_decision_settlement|ENROLLED_ROADMAP_FALLBACK_REFUSAL|_StaleDecisionSettlementSource' plan_tool tests` returns nothing, and `--settle-decision` dispatches straight to the enrolled runner.
- A ledger file carrying `ledger_state: migration-pending` is refused on read with a message that names the successor-slug remedy, and `LedgerState.MIGRATION_PENDING` is gone.
- `rg 'require_unenrolled_roadmap_writer|EnrolledRoadmapWriteError|publish_stage_artifact|enroll_stage_baselines|publish_revision_candidate|publish_feedback_reopen_candidate|publish_structural_revision_proof|capture_checkpoint|restore_roadmap_revision|enroll_roadmap_baselines' plan_tool tests` returns nothing.
- `rg 'read_recorded_brief_source|load_recorded_brief_path|brief_source_path|RoadmapSourceRecorded|RoadmapSourceResolved' plan_tool tests` returns nothing.
- `rg 'MIGRATION_PENDING' plan_tool` returns nothing. The literal `migration-pending` appears in `plan_tool/roadmap_feedback_ledger.py` only as the removed-state constant that produces the named refusal, and a ledger naming that state is refused on load with the successor-slug message.
- `recover_roadmap_publication` still rolls back a pending root-version generation that has no head, and still recognizes a completed version-owned generation.
- `plan-tool validate` reports no `absent-surface` or `orphan-subcommand` finding for the roadmap capability.
- `uv run pytest tests/ -q -n auto` is green.
- Every file this step adds to the plan's list (the decision-settlement, data-contract, and ledger-test files above) is named in the commit message.
- `uv run pytest tests/cli/test_cli_reference.py -q` passes with `docs/cli/roadmap.md` regenerated.

## References

- `BACKLOG.md` #441 — source entry, scope contract, and step 1's recorded inventory.
- `ROADMAP_FORMAT.md` § "Revision checkpoint and restore" and § "Stage re-entry selection and bounded feedback" — the removed surfaces; the doc edit belongs to the plan's docs step.
- `ROADMAP_FEEDBACK_FORMAT.md` — ledger states, including the `migration-pending` state removed here.
- `plan_tool/roadmap_versions.py` — `load_accepted_version`, `create_root_version`, `version_directory_path`: the surviving write and read contract.
- `plan_tool/roadmap_revision_publish.py` — `publish_roadmap_generation`, `recover_roadmap_publication`, `roadmap_writer_guard`: what stays.
- `DATA_CONTRACT.md` and `plan_tool/data_contract.py` — the run-log event registry and its drift guard.
- `TESTING.md` — the invoker neutralization table to update.

## Applicable guardrails

- **The plan's "## Out of scope", candidate/review-seal/promotion/version-record contracts:** this step must not edit those records or their writers. It removes only legacy callers and symbols.
- **The plan's "## Out of scope", ledger format:** the only ledger change allowed is removing legacy migration (the `migration-pending` state and `migrate_legacy_feedback`). Reviewer-item fields and states are unchanged.
- **The plan's "## Out of scope", tool-driven migration and read-only mirror:** removal leaves no replacement route, no conversion command, and no top-level mirror. A refusal message may name hand conversion and nothing else.
- **The plan's "## Out of scope", structural rewrite and restore routes:** no version-store route replaces `--rewrite-structural` or `--restore-revision`. Do not add one.
- **The plan's step intent for this step:** the version store ends as the only write target, and the `source.json` helpers and their run-log event are deleted. Any change that does not serve those two outcomes stays out.

## Deferred

- Rewriting `ROADMAP_FORMAT.md`, `ROADMAP_FEEDBACK_FORMAT.md`, and `docs/how-to/roadmap.md` for the removed surfaces — the plan's docs step owns it; this step records each stale site in its commit message.
- The guard that checks no production code reads the resume directory or a top-level artifact — step 11 owns it. This step adds only the narrow name scan above.
- Deleting stored receipts, checkpoints, or `source.json` files already on disk — the plan names no tool-driven migration; Integration is converted by hand.
- Consolidating the remaining duplicated roadmap guard and recovery helpers — a cross-module refactor, so it goes to `BACKLOG.md` if the trace finds one.
- Any version-store replacement for structural rewrite or revision restore — listed as out of scope; a recurring need becomes a new backlog entry.
