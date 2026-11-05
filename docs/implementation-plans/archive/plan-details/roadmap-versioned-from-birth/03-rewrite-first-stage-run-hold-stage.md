> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Rewrite the first stage run to publish the root version after stage 4

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step rewrites the stage run in `plan_tool/roadmap.py` so a first run keeps each gate-clean stage result in memory, with a copy of each in step 2's resume directory. After stage 4 passes, it publishes one root version with the accepted head written last. It no longer writes top-level `0N-*.md` files, and it no longer calls the revision checkpoint or the stage baselines. It refuses once an accepted head exists, refuses a folder with no head that holds pre-head state (top-level `0N-*.md` files, a ledger, seed state, a populated version store, or draft seeds), and refuses a changed brief, each with a named `RoadmapError` that states the operator's remedy. A held stage that is unreadable or fails its re-gate is regenerated with a warning, not refused. `--from-stage` and `--confirm-brief-rebind` are removed from `plan_tool/cli/roadmap_cmd.py` and from `run_roadmap`. On green, a first run on a clean folder leaves only the version store and a ledger-native feedback ledger. A failed run leaves only the resume directory, and a later run resumes from it.

## Table of Contents

- [Why](#why) — what the legacy stage run does today and why it has to change
- [Input](#input) — what steps 1 and 2 supply and what this step cannot verify
- [Files (creates vs edits)](#files-creates-vs-edits) — the four files touched
- [Implementation](#implementation) — behavior that must hold, recommended approach, constraints
- [Tests](#tests) — cases per behavior and invariant
- [Acceptance criteria](#acceptance-criteria) — observable end state
- [References](#references) — docs and symbols to read
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves to other steps

## Why

- `plan_tool/roadmap.py:run_roadmap` writes each stage to a top-level `0N-*.md` file and tracks it with the revision checkpoint and stage baselines. Enrollment into the version store happens later, through `enroll_roadmap_root`.
- Until enrollment, the roadmap's content has two homes: the top-level files and the version store. The plan's intent is one stored copy that every command reads.
- `run_roadmap` today starts by calling `_require_legacy_roadmap_run_available`, which refuses an enrolled roadmap with "refuse legacy mutation". That makes the stage run unusable for any roadmap in the version store, so the run needs a new owner for the "is there already a head" decision.
- `--from-stage` and `--confirm-brief-rebind` exist only for the top-level-file model (re-entry at a stage, re-binding a changed brief). Neither has a meaning once stage results live in memory and the resume directory.

## Input

- **Step 1 output:** the route inventory recorded on `BACKLOG.md` #441. It confirms which flags and functions this step removes and that nothing else reads the top-level files from the stage run. Take the removal list from there, not from this detail.
- **Step 2 output:** `plan_tool/roadmap_stage_resume.py`, the only code that builds, writes, reads, or deletes the resume directory. Use its API as landed and read the real names from the module. Where they differ from this detail, the landed names win. A damaged held stage comes back as a warning and a shorter held run, not an error; its one refusal is a changed brief digest.
- **Version store (unchanged by this step):** `plan_tool/roadmap_versions.py` supplies `prepare_root_version_from_snapshot`, `build_root_enrollment_generation`, `load_accepted_head`, `is_roadmap_enrolled`, and `accepted_head_path`. The generation builder already puts the head selector in the same pending generation as the version members. `plan_tool/roadmap_revision_publish.py` supplies `publish_roadmap_generation` and `recover_roadmap_publication`.
- **Existing ledger helper:** `plan_tool/roadmap.py:_with_initial_feedback_ledger` adds the initial ledger to a generation. Reuse it; `_ledger_state_for_enrollment` is the enrollment-only caller and needs a ledger-native replacement.
- **Brief digest:** `plan_tool/roadmap_source.py:digest_decoded_text` computes the digest that step 2's resume check compares against.
- **Limit:** unit tests drive the stage loop with canned replies through the `invoker=` seam. They prove the control flow and the publish result. They cannot prove that a real model's replies reach the gates.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap.py`
    - Rewrite `run_roadmap` and `_run_roadmap` as the first-run path described below.
    - Remove the `from_stage` and `confirm_brief_rebind` parameters.
    - Remove the calls to `_capture_or_continue_revision_checkpoint`, `_checkpoint_verify_before_write`, `_checkpoint_update_after_write`, `enroll_roadmap_baselines`, `_write_brief_source`, and `_resolve_brief_path`'s recorded-source handling. Step 10 deletes the code behind those calls.
    - Stop using `_check_from_stage` and `_load_and_regate_below` in the stage run.
    - Stop calling `_require_legacy_roadmap_run_available` from `run_roadmap`.
  - `plan_tool/cli/roadmap_cmd.py`
    - Remove the `--from-stage` and `--confirm-brief-rebind` argparse entries and the `from_stage_supplied` marker action.
    - Remove the namespace attributes they set and every handler branch that reads them (the stage-run call, the `_selects_non_stage_roadmap_route` check, and the route-selector tuples).
    - Update the module docstring, the `--help` text, and the failure messages that tell the operator to re-run with `--from-stage N`.
  - `tests/test_roadmap.py` — add the cases listed under Tests; rewrite the existing stage-run cases that assert top-level `0N-*.md` files, checkpoints, baselines, or `from_stage`.
  - `docs/cli/roadmap.md` — regenerate with `python -m plan_tool.cli_reference --write` after the parser changes. The full-suite gate runs `tests/cli/test_cli_reference.py` at this step, so leaving it stale fails the step.
  - `tests/cli/test_roadmap_cmd.py` — add the removed-flag cases; rewrite parser and handler cases that pass `--from-stage` or `--confirm-brief-rebind`.

## Implementation

**Behavior that must hold when the step is done:**

- **Order of preflight checks.** Run them in this order, each before any model call and before any brief read beyond what the check needs:
  1. Acquire the writer token (`_roadmap_writer_owner`).
  2. Recover any pending root journal (`recover_roadmap_publication`). This happens before the resume directory is read.
  3. If an accepted head exists, refuse. Then, if a resume directory sits beside that head, delete it (stale leftover from a run that committed but crashed before cleanup). The refusal names the head and states that a roadmap with a head is changed through feedback and review, not through a stage run.
  4. If there is no head but the folder holds any pre-head roadmap state (top-level `0N-*.md` files, `feedback-ledger.yaml`, `seed-state.json`, a `.roadmap-versions/` directory with entries, or draft seeds), refuse with one named error that lists each path found. Recovery (step 2 of this order) has already run, so a partial root generation counts as pre-head state only if recovery left it behind. The message states that a tool-driven migration does not exist and that these folders are converted by hand: move or delete the listed files (deleting the ledger discards its feedback rows) or start a successor slug.
  5. Read the held stages through step 2's module. A brief digest that differs from the current brief refuses with step 2's named error, which states the remedy (restore the brief, delete the named `roadmap-stage-resume/` directory by hand, or start a successor slug); use its check and do not re-derive the verdict. An unverifiable digest (`brief_digest=None`) means the held stages are regenerated, with the module's warnings printed.
- **Stage results are held, not written.** Each gate-clean stage result is kept in memory and, in the same loop iteration, written to the resume directory through step 2's write calls (the brief digest first, then each stage). Later stages' gates receive the earlier results from memory (the same gate envelope the loop builds today), never from disk.
- **Resume.** Held stages are re-gated in memory in order before use, and a stage is not re-run only if it passes. The loop starts at the first stage that is missing or fails its re-gate. When a held stage fails its re-gate, print a warning naming its file, call `discard_stages_from` for that stage so no stale later file remains, and regenerate from there: only the failing stage and those after it are lost, and no stage that passed is re-run.
- **Publish after stage 4.** Once the last stage passes its gates, build one root version from the held stage texts and the current brief bytes, build the root generation with the head selector, add the initial ledger, and publish it as a single generation. Use the existing `prepare_root_version_from_snapshot`, `build_root_enrollment_generation`, and `publish_roadmap_generation` chain; supply it a plain value with the fields `prepare_root_version_from_snapshot` reads (`brief_bytes`, `brief_raw_digest`, `artifact_keys`, `artifact_texts`, `artifact_digests`) rather than a legacy impact snapshot. The head is written last, as the generation builder already orders it.
- **Resume directory deleted only after the head commits.** Delete it after `publish_roadmap_generation` returns, never before and never in a `finally:` that also runs on failure.
- **A stage that exhausts its attempts halts the arc.** The resume directory keeps the stages that passed; nothing else is written; the next stage's invoker is not called. This behavior is unchanged; only where results live changes.
- **No top-level writes.** The stage run does not create a `0N-*.md` file, a baseline, a checkpoint, or `source.json` at any point, including on failure.
- **Removed flags.** `roadmap --from-stage N` and `roadmap --confirm-brief-rebind` are rejected by argparse as unknown arguments. `run_roadmap` takes neither keyword.

**Recommended approach (latitude on the exact code):**

- Keep `_run_stage` and the attempt loop as they are. They already hand back a parsed artifact and its rendered text, which are the two things the held-results map needs. Replace only the code around them: what happens after a stage passes, and what feeds the next stage.
- Replace the per-stage `_load_predecessors` / `_load_and_regate_below` reads with a small in-memory mapping from stage number to the parsed artifact, filled from the held stages at start and from each passing stage afterwards.
- Hold the "which preflight failed" decision in one small helper that returns or raises, so the order above is readable in one place and testable case by case.
- Take the brief from the path the operator gave, as today, but without the recorded-source lookup. Compute its digest with `digest_decoded_text` for the resume comparison, and keep the exact bytes for the version's `brief.md`.

**Constraints (not free to vary):**

- **Recovery comes before the resume read.** A pending root journal may already have committed the head. Reading the resume directory first could resume a run that finished.
- **The refusal for an accepted head must not read the brief or invoke the model.**
- **Do not add a second publisher.** Use `publish_roadmap_generation`; do not write version members and the head with separate atomic writes. A crash between them is the case the journal exists for.
- **The ledger is ledger-native.** Build the initial ledger as a feedback-free empty ledger in the generation. Do not carry over the enrollment path's `migration-pending` state; the plan removes that state, and the replacement of `_ledger_state_for_enrollment` is this step's, limited to what the first run needs.
- **Do not call or edit step 10's targets beyond removing the calls.** The checkpoint, stage-baseline, and `source.json` modules still exist after this step; they just have no caller in the stage run.
- **`RoadmapResult` stays the return type.** Keep its fields that the CLI summary reads. Drop or leave empty only the fields that described `from_stage` and overwritten stages, and update the handler summary in the same change. `emit_roadmap_terminal_status` and the outcome vocabulary (`is_successful_roadmap_outcome`) are unchanged.
- **Main alternative rejected:** writing the held stage texts to top-level `0N-*.md` files and enrolling them afterwards, as `enroll_roadmap_root` does. It keeps two content homes between the first write and the head commit, which the plan's intent rules out.

**Shared locations (foundational logic: "the first run's only durable state is the resume directory until the head commits"):**

- `plan_tool/roadmap.py:enroll_roadmap_root`, `enroll_roadmap_baselines`, `_require_root_enrollment_recovery_only`, and `_require_legacy_roadmap_run_available` implement the legacy enrollment half of the same rule. They are removed by step 10 and are not changed here beyond dropping the stage run's calls.
- `plan_tool/cli/roadmap_cmd.py` summary and failure texts that print `--from-stage {failed_stage}` are in this step's footprint, because the flag they name is removed here.
- `docs/how-to/roadmap.md` and the FORMAT docs name `--from-stage`; the plan's docs step owns those edits (see Deferred).

## Tests

All cases drive `run_roadmap` through the `invoker=` seam with canned replies. None may call a real backend.

### `tests/test_roadmap.py`

- `test_first_run_publishes_one_root_version_and_head_after_stage_four` — a four-stage canned run leaves a version directory and `accepted-head.json` naming it.
- `test_first_run_writes_no_top_level_stage_files` — after success, no `0N-*.md` exists under the roadmap folder.
- `test_first_run_writes_no_baseline_checkpoint_or_source_json` — none of those files exist after success or after a failed run.
- `test_head_is_written_last_in_the_published_generation` — the generation's last member is the head selector (pins "head written last").
- `test_later_stage_gates_see_earlier_results_from_memory` — a hand-built resume directory differs from nothing on disk; the stage 2 gate receives stage 1's held value.
- `test_failed_stage_four_leaves_only_the_resume_directory_holding_stages_one_to_three` — the folder has the resume directory and nothing else new.
- `test_rerun_after_stage_four_failure_does_not_call_the_invoker_for_stages_one_to_three` — the recorded invoker calls are stage 4 only.
- `test_exhausted_stage_halts_the_arc_and_never_calls_the_next_invoker` — kept from the existing suite, rewritten for in-memory results.
- `test_resume_directory_survives_until_the_head_commits` — a publish failure (injected) leaves the resume directory in place.
- `test_resume_directory_is_deleted_only_after_head_commits` — after success the directory is gone and the head exists.
- `test_run_refuses_when_an_accepted_head_exists` — raises `RoadmapError` naming the head; invoker never called; brief not read.
- `test_resume_directory_beside_an_accepted_head_is_deleted_on_refusal` — the refusal still happens, and the stale directory is removed.
- `test_a_held_stage_that_is_unreadable_is_regenerated_with_a_warning` — `stage-2.md` unreadable: the invoker is called for stages 2–4 only, stage 1 is not re-run, and the warning names the stage 2 file.
- `test_a_held_stage_that_fails_its_regate_is_regenerated_with_the_stages_after_it` — held stages 1–3 with a stage 2 that fails its gates: stage 1 is not re-run, stages 2–4 are, and no stale `stage-3.md` remains.
- `test_folder_with_pre_head_state_refuses_naming_every_path_found` — parametrized over each kind (top-level `0N-*.md` files, a ledger, `seed-state.json`, a populated `.roadmap-versions/`, a draft seed) and one case with two kinds at once: raises before any model call, the message lists each path, offers no migration, and no file is changed or deleted.
- `test_pending_root_journal_is_recovered_before_the_resume_directory_is_read` — a pending root journal that committed the head, plus a resume directory whose digest differs from the brief, yields the head-exists refusal and not the changed-brief error (pins the preflight order).
- `test_crash_before_the_head_commit_recovers_then_republishes_instead_of_refusing` — members and ledger landed, no head: the re-run recovers, the pre-head-state refusal does not fire, and the root is republished from the held stages.
- `test_changed_brief_refuses_with_the_remedy_and_deletes_nothing` — a held digest that differs from the current brief raises `RoadmapError`, the invoker is never called, the message states restore, delete-the-directory, and successor-slug, and every held file is still on disk.
- `test_run_roadmap_rejects_from_stage_and_confirm_brief_rebind_keywords` — both keywords raise `TypeError`.
- `test_initial_ledger_is_feedback_free_and_not_migration_pending` — the published ledger has no rows and no `migration-pending` state.

### `tests/cli/test_roadmap_cmd.py`

- `test_from_stage_flag_is_rejected_as_unknown` — argparse exits 2 for `--from-stage 2`.
- `test_confirm_brief_rebind_flag_is_rejected_as_unknown` — argparse exits 2 for `--confirm-brief-rebind`.
- `test_failure_summary_does_not_mention_from_stage` — a failed run's printed text names no removed flag and says the next plain run resumes.
- `test_help_text_names_neither_removed_flag` — `--help` output contains neither flag.
- `test_cli_refusal_for_accepted_head_exits_nonzero_with_the_named_message` — the handler maps the new refusals to the existing failure-to-complete exit code.

### Tests for this step

Every case above must be green before the step is done. Run `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q`, then the full suite with `-n auto`. Existing cases that pinned the old behavior (top-level files, checkpoints, `from_stage` re-entry, `--confirm-brief-rebind`) are expected to go red and must be rewritten or deleted in this step. Do not narrow the change to keep them green. Cases for the other routes (feedback, seeds, structural rewrite) that still call the baseline or checkpoint code are step 10's; do not touch them unless they call the stage run.

## Acceptance criteria

- A first run on a clean roadmap folder, with canned stage replies, leaves `.roadmap-versions/<id>/` and `accepted-head.json` and no top-level `0N-*.md`.
- `rg 'from_stage|confirm_brief_rebind|--from-stage|--confirm-brief-rebind' plan_tool/roadmap.py plan_tool/cli/roadmap_cmd.py` returns nothing, except where the text names the removed flag as removed (none expected).
- `rg '_capture_or_continue_revision_checkpoint|enroll_roadmap_baselines|_write_brief_source' plan_tool/roadmap.py` shows no call inside `run_roadmap` or `_run_roadmap`.
- A run beside an accepted head raises a `RoadmapError`, calls no invoker, and removes any stale resume directory.
- A folder with no head that holds any pre-head state refuses before any invoker call, naming each path found, and changes nothing.
- A held stage that is unreadable or fails its re-gate is regenerated with a warning, and only it and the stages after it are re-run. A changed brief refuses with step 2's named error and removes nothing.
- After a failed stage 4, a second run calls the invoker for stage 4 only.
- After a successful run, the resume directory is absent. After a failed publish, it is present.
- `rg 'input\(|isatty' plan_tool/roadmap.py` returns nothing new (stage runs stay non-interactive).
- The listed test cases pass, and the full suite is green.
- `uv run pytest tests/cli/test_cli_reference.py -q` passes with `docs/cli/roadmap.md` regenerated.

## References

- `BACKLOG.md` #441 — scope contract and the step 1 inventory this step removes from.
- `ROADMAP_FORMAT.md` § "Immutable candidate-version authority" — the accepted head and root version contract this step publishes into.
- `plan_tool/roadmap_versions.py` — `prepare_root_version_from_snapshot`, `build_root_enrollment_generation`, `load_accepted_head`, `accepted_head_path`.
- `plan_tool/roadmap_revision_publish.py` — `publish_roadmap_generation`, `recover_roadmap_publication`.
- `plan_tool/roadmap_stage_resume.py` — step 2's resume API.
- `plan_tool/roadmap.py` — `run_roadmap`, `_run_roadmap`, `_run_stage`, `_with_initial_feedback_ledger`.
- `docs/how-to/roadmap.md` — operator procedure that step 12 (docs) rewrites.

## Applicable guardrails

- **The plan's "## Out of scope", candidate/review-seal/promotion/version-record contracts:** this step uses the root version record and head as they are. It must not change their schema, identity, or validation.
- **The plan's "## Out of scope", ledger format:** the first run publishes a ledger in the existing format. This step must not change the format; it only chooses the feedback-free initial state.
- **The plan's "## Out of scope", tool-driven migration:** the pre-head-state refusal must not offer, hint at, or implement a conversion. The message says the roadmap is converted by hand.
- **The plan's "## Out of scope", top-level mirror:** the stage run must not write a read-only top-level copy of the published version, even as a convenience.
- **The plan's "## Out of scope", dates or timestamps:** neither the resume directory contents this step writes nor the published version may carry one.
- **The plan's "## Out of scope", structural rewrite and restore routes:** this step must not add a version-store route for either. It only removes the stage run's use of the old checkpoint code.
- **Stage runs stay non-interactive** (the `roadmap.py` module contract): the new refusals must be plain errors, never prompts.

## Deferred

- Deleting the revision checkpoint, stage baseline, `source.json`, and legacy publisher code — step 10 owns it. This step only removes the stage run's calls.
- Reading or writing the resume directory anywhere outside the stage run, and the guard that searches for it — owned by the plan's guard step.
- Converting the other routes (feedback, seed refresh, `create --from-existing`) to read the accepted version — owned by the plan's route-conversion steps, not the first stage run.
- Rewriting `docs/how-to/roadmap.md`, `ROADMAP_FORMAT.md`, and `CLAUDE.md` text that names `--from-stage` and `--confirm-brief-rebind` — owned by the plan's docs step.
- Updating `CAPABILITIES.md` for the removed flags — the docs step owns it. The generated `docs/cli/roadmap.md` is **not** deferred: regenerate it in this step.
- Converting existing roadmaps (for example Integration) that hold top-level `0N-*.md` files — done by hand after the plan ships; this step only refuses them.
