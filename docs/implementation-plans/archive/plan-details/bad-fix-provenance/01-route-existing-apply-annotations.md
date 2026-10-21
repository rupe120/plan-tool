> **Withdrawn 2026-08-11** — Withdrawn after the detail-stage audit exposed an unresolved high-severity provenance-ordering defect and non-convergent correctness contracts; re-seed the capability from the audited invariants before implementation.
> Preserved here for history; do not edit.

# Step 1 — Route existing apply annotations through one writer

## Summary

Create one persistence-level annotation writer and route the interactive walk plus serial and parallel `completeness-apply` dispositions through it. The main changes sit in `plan_tool/review_persistence.py`, `plan_tool/review_walk.py`, `plan_tool/cli/completeness_cmd.py`, and `plan_tool/cli/completeness_apply_parallel.py`. Keep the `Annotation` data shape, status decisions, notes, halt reasons, sidecar role handling, and command output unchanged. On green, every existing apply disposition reaches the same durable sidecar-write seam, ready for step 2 to add provenance without missing a producer.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the refactor and its unchanged behavior.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why one durable annotation path is needed before provenance work.
- [Input](#input) — Existing saved-review and callback contracts this step preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by the refactor and their roles.
- [Implementation](#implementation) — The shared-writer design and routing constraints.
- [Tests](#tests) — Regression coverage for each annotation producer.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary documentation for the persistence mechanics.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that keep this behavior-preserving.

## Why

`plan_tool/review_persistence.py:update_annotation` already safely rewrites a saved sidecar, but the generic walk and the parallel replay path prepare and pass dispositions through separate seams. Step 2 needs one place where every newly recorded annotation can be extended consistently, so this refactor must make the existing durable writer the shared producer boundary without changing what any operator choice means today.

## Input

- **Saved-review contract:** `plan_tool/review_persistence.py:Annotation` currently contains `status`, `note`, and `halt_reason`; `SavedReview.annotations` maps recommendation ids to those records. Preserve this shape and its existing legacy-load behavior in this step.
- **Durable rewrite contract:** `plan_tool/review_persistence.py:update_annotation` loads the full sidecar and preserves report content, recommendations, fingerprints, audit metadata, and checkpoint-role behavior while writing through `plan_tool/fileio.py:durable_write_text`.
- **Disposition callback contracts:** `plan_tool/review_walk.py:PersistFn` receives a saved path, recommendation id, and complete `Annotation`; `plan_tool/cli/completeness_apply_parallel.py:replay_results` currently reports the parallel tail’s final disposition through its `persist` callback. Keep incremental persistence timing intact.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — establish the single producer-facing annotation writer at the existing `update_annotation` persistence boundary while retaining compatibility for existing callers.
  - `plan_tool/review_walk.py` — make `walk_recommendations` use the shared writer for every completed interactive disposition.
  - `plan_tool/cli/completeness_cmd.py` — bind the serial and parallel completeness-apply paths to the shared writer rather than owning a second annotation-write shape.
  - `plan_tool/cli/completeness_apply_parallel.py` — carry the parallel replay tail’s final disposition as an `Annotation` through its callback seam.
  - `tests/test_review_persistence.py` — cover the central writer’s sidecar-preservation and failure behavior.
  - `tests/test_review_walk.py` — cover interactive applied, skipped, failed, and drift-halt annotations through the shared seam.
  - `tests/cli/test_completeness_cmd.py` — cover serial and `--jobs` completeness-apply routing to the same writer.
  - `tests/cli/test_completeness_apply_parallel.py` — cover the replay callback’s complete-annotation and incremental-persistence contract.

## Implementation

- **Foundational logic: one durable annotation-disposition writer.** Introduce one producer-facing helper beside `plan_tool/review_persistence.py:update_annotation`; `write_annotation` is a suitable name. Give it the current writer inputs: saved sidecar path, recommendation id, and a complete `Annotation`. It must own the load, replacement in `annotations`, and durable full-sidecar rewrite.

- **Keep `update_annotation` compatible.** `plan_tool/__init__.py:update_annotation` is an existing package re-export outside this step’s file list. Retain its current callable behavior, whether it delegates to the new seam or remains the implementation behind it. Do not require an `__init__` change or break callers that import the existing name.

- **Preserve the whole sidecar, not just annotations.** Reuse the behavior at `plan_tool/review_persistence.py:update_annotation`: preserve recommendations, report markdown, plan and code fingerprints, audit coverage, plan mass, audit stage, and the checkpoint-role/version matrix. Keep `durable_write_text` as the durable atomic write path. A write failure must leave the prior sidecar valid and must not advance the walk’s in-memory annotation state.

- **Keep annotation construction separate from persistence.** `plan_tool/review_walk.py:_auto_apply` and `_prompt_for_annotation` remain responsible for choosing `applied`, `skip`, or `failed`, composing the note, and setting `halt_reason="drift"` when appropriate. The new writer records that completed `Annotation` unchanged; it must not reinterpret status, strip notes, or infer provenance.

- **Route every interactive disposition through the seam.** Change `plan_tool/review_walk.py:walk_recommendations` so its default `PersistFn` reaches the shared writer, then retain the existing order: persist successfully first, update `saved.annotations` second, then increment the answered count and honor a halt request. Keep the injectable persistence seam for deterministic walk tests.

- **Let existing generic walkers inherit the change.** `plan_tool/cli/review_cmd.py:cmd_review`, `plan_tool/cli/review_cmd.py:cmd_review_walk`, `plan_tool/cli/reconcile.py:_walk_saved`, `plan_tool/cli/reconcile.py:_walk_with_reconcile_phase`, and `plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply` already use `walk_recommendations`. Do not edit those callers; changing the walk default must cover them without creating parallel writer paths.

- **Route serial completeness apply through the walk.** `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` must continue to rely on `walk_recommendations` for serial dispositions, including command-local data-contract redirects. Do not add an annotation rewrite in the action dispatcher or change its apply, skip, failed, note, or drift-halt behavior.

- **Normalize the parallel handoff before persistence.** In `plan_tool/cli/completeness_apply_parallel.py:annotation_status`, `replay_results`, and `run_parallel_apply`, have the replay callback receive the final complete `Annotation`, rather than requiring each downstream caller to rebuild one from status and note strings. `plan_tool/cli/completeness_cmd.py:_apply_walk_recs_parallel` should bind that callback to the shared writer for the selected sidecar.

- **Preserve parallel ordering and failure timing.** Workers must still never write the canonical sidecar. `replay_results` must invoke the writer only after it has decided the final replay outcome: after conflict reruns, and after the parse gate restores a failed change when needed. Continue writing one final disposition at a time in replay order so interruption loses at most the in-flight finding.

- **Do not add provenance yet.** Leave `Annotation` serialization, schema version selection, CLI flags, report selection, and recommendation matching unchanged. Step 2 owns timestamps, note-source classification, and source-report identity.

## Tests

### Tests for this step

`tests/test_review_persistence.py:TestUpdateAnnotation.test_writes_only_annotations` — extend or replace it to show the shared writer updates one recommendation while preserving report markdown and recommendations.

`tests/test_review_persistence.py:TestUpdateAnnotation.test_update_annotation_preserves_checkpoint_role_and_v3_matrix` — keep direct compatibility and prove delegation does not alter role or schema behavior.

`tests/test_review_persistence.py:TestAtomicJsonWrite.test_update_annotation_replace_failure_preserves_prior_content` — run the central writer’s failure path and prove prior valid sidecar bytes and parsed annotations remain intact.

`tests/test_review_walk.py:TestWalkRecommendationsHappyPath.test_marks_done` — verify an interactive applied disposition reaches the shared writer with the same empty note as before.

`tests/test_review_walk.py:TestWalkRecommendationsHappyPath.test_marks_skip` — verify an interactive skip disposition keeps its status and note through the same writer.

`tests/test_review_walk.py:test_pre_apply_drift_halt_records_drift_halt_reason` — verify the drift skip still persists `halt_reason="drift"` without a separate write path.

`tests/cli/test_completeness_cmd.py:test_serial_completeness_apply_uses_shared_annotation_writer` — drive the serial completeness walk and assert its final sidecar annotation comes through the central writer with unchanged disposition data.

`tests/cli/test_completeness_cmd.py:TestCompletenessApplyParallel.test_parallel_applies_and_persists_annotations` — assert the `--jobs` path sends applied and failed final annotations through the same writer.

`tests/cli/test_completeness_apply_parallel.py:TestReplayPersistCallback.test_persist_fires_per_finding_incrementally` — update the callback expectation to receive complete annotations and preserve one callback per final replay result.

Every listed test, plus the existing tests in these four suites, must be green before this step is considered finished.

## Acceptance criteria

- Every production annotation written by `walk_recommendations`, serial `cmd_completeness_apply`, or parallel `run_parallel_apply` reaches one persistence-level writer before the sidecar changes.
- Interactive applied, skipped, failed, and drift-halt dispositions retain their current `status`, `note`, and `halt_reason` values.
- The parallel replay tail persists only final outcomes, after conflict handling and the parse gate, one finding at a time.
- A shared-writer update preserves all non-annotation saved-review fields, including checkpoint-role behavior and existing schema versions.
- A durable-write failure leaves the existing sidecar valid and leaves the current walk state unadvanced.
- Existing callers of `update_annotation` continue to work without a package-surface change.
- No annotation provenance fields, new sidecar store, CLI option, matcher behavior, stop reason, or exit-code behavior is added.

## References

- [Python dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Review frozen `Annotation` records and `asdict` serialization behavior.
- [Python json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review JSON serialization and parsing requirements for saved-review sidecars.
- [Python os.replace](https://docs.python.org/3/library/os.html#os.replace) — Review the atomic replacement primitive used by the durable sidecar writer.

## Applicable guardrails

- **The plan’s “## Plan intent”, recommend-only evidence boundary** — this step only creates the annotation-writing seam; it must not add or evaluate a bad-fix advisory.
- **The plan’s “## Step intent”, behavior-preserving routing boundary** — preserve all current disposition semantics while consolidating their persistence path.
- **The plan’s “## Out of scope”, mutation and gate boundaries** — do not expand apply behavior, structural actions, convergence gating, or command exit behavior.
- **The plan’s “## Out of scope”, provenance and matching boundaries** — keep data in existing annotations only and do not add provenance fields or change finding-identity logic before their owning steps.
