# Step 5 — Make detail replacement restore the previous body on failure

## Summary

Make active-detail replacement in `plan_tool/detail.py` recoverable when a canonical detail already exists. Replace the current best-effort archive-and-write behavior with one operation that preserves the old body, verifies the replacement, and restores the old body after a failed write or verification. Route both serial and concurrent publication through that operation, while keeping the canonical filename and existing `DetailResult` contract. Extend `tests/test_detail.py` to prove successful archival, exact restoration, and clear reporting when restoration itself fails.

## Table of Contents

- [Summary](#summary) — The recoverable replacement outcome and affected files.
- [Why](#why) — Why the current archive-first flow can remove a valid active detail.
- [Input](#input) — The validated prepared body and existing-file state consumed by replacement.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing files changed by this step.
- [Implementation](#implementation) — The required replacement, verification, and restoration rules.
- [Tests](#tests) — Failure injection and successful replacement coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Filesystem replacement semantics relevant to recovery.
- [Deferred](#deferred) — Broader publication protocols that remain outside this step.

## Why

`plan_tool/detail.py:_archive_existing_detail` currently treats archival as best-effort and removes the active file before `Path.write_text` has produced a valid replacement. If the new write fails, the canonical path can disappear even though the archived body was the last known-good detail. A replacement must instead be one recoverable operation: either the verified new body becomes active under the same canonical name, or the prior body returns to that name and the failure remains visible.

## Input

- **Validated response:** Step 4 ensures `plan_tool/detail.py:_author_step_detail` accepts only the structured detail protocol and produces a validated body. This step must not add a legacy Markdown fallback or move response validation into filesystem recovery.
- **Prepared detail write:** Consume the write-free prepared-detail outcome supplied by the prerequisite publication plan. Preserve its canonical output path, stored plan-relative path, exact Markdown bytes, validated deferrals, and checkpoint relationship rather than rebuilding them during replacement.
- **Existing active state:** Replacement reads whether the canonical output path exists and records the old active path and chosen archive destination before changing either path. The canonical path remains the location referenced by plan frontmatter and downstream readers.
- **Result contract:** `plan_tool/detail.py:DetailResult` may report `written=True` only after replacement and post-write verification succeed. A restored or restoration-failed operation remains a failed result and must retain its checkpoint for retry.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/detail.py` — make active-detail replacement recoverable, carry enough replacement state to restore the prior body, route serial and concurrent publication through the same operation, and distinguish ordinary replacement failure from restoration failure.
  - `tests/test_detail.py` — add successful replacement and injected failure coverage for archive setup, archive move, candidate write, post-write verification, and restoration.

## Implementation

- **Make recoverable active-detail replacement the foundational logic.** A replacement succeeds only when the prepared bytes are active and verified at the canonical path. Any failure after moving an existing body must restore that body or return a distinct restoration error that names the recoverable archive path.

- **Keep validation before mutation.** Step 4 owns structured response validation, and the prerequisite prepared-write contract supplies the final Markdown bytes. Do not move the old active file until those bytes are complete and accepted.

- **Use the prerequisite authority for concept-backed publication.** Add or adapt a narrow active-detail replacement primitive that produces typed archive, write, verification, and restoration actions. Legacy no-sidecar detail-only paths may execute that primitive locally. When a concept record is present, `generate_detail` and `_generate_detail_concurrent` must submit those actions inside the prerequisite step-9 publication request with the plan pointer and concept deferrals; they must not invoke a competing per-step transaction or publish the active detail first.

- **Record a small replacement journal.** Track whether an active file existed, its canonical path, and the exact archive destination chosen by `plan_tool/detail.py:_archive_existing_detail`. The journal must distinguish “nothing changed,” “old body moved,” “new body active,” and “old body restored” well enough to choose the correct cleanup after each failure.

- **Make archive setup and move failures stop replacement.** Once an existing body needs protection, failure to create the archive directory or move that body must leave the canonical bytes unchanged and must prevent the candidate write. The current best-effort behavior is not safe for replacement.

- **Verify the active result.** After publishing the candidate, confirm that the canonical path contains the exact prepared bytes. One suitable approach is a read-back byte comparison; do not rely only on a successful write call. Treat a missing, unreadable, truncated, or different body as a failed replacement.

- **Restore after post-move failure.** If the candidate write or read-back verification fails after the old body moved, remove any incomplete candidate as needed and move the archived body back to the canonical path. A successful restoration must leave the same active bytes that existed before replacement and must not report `written=True`.

- **Clean up failed first publication.** When no prior body existed, record original absence before creating the candidate. A partial write, unreadable or truncated read-back, verification mismatch, or cleanup failure must remove and verify absence of the candidate. If absence cannot be restored, return the same distinct restoration-failed or uncertain result with the canonical path; never leave an incomplete first detail while claiming an ordinary failure.

- **Report restoration failure separately.** If returning the old body to the canonical path fails, preserve the archive copy and include its exact path in the failure reason. Do not describe the operation as restored, hide the original replacement error, or delete the remaining recovery copy.

- **Preserve successful archive behavior.** On success, keep the old body at the selected archive destination, keep the new body at the unchanged canonical filename, and retain the existing operator notice identifying the archive path.

- **Preserve publication ordering.** Do not update the plan pointer, discard the checkpoint, archive same-step orphans through `plan_tool/detail.py:_archive_orphan_details`, complete the progress handle, capture a written-success scenario, extract lessons, invoke the per-step commit callback, or append a successful `DetailResult` until replacement verification succeeds.

- **Preserve failure visibility.** Map an ordinary replacement failure to the existing not-written result and reporter/run-log error flow. Map restoration failure to a distinct reason containing both the replacement problem and recoverable archive location; keep the checkpoint available in both cases.

- **Keep serial and concurrent behavior equal.** Concurrent workers may prepare candidates, but replacement and restoration must remain in deterministic step order in `_generate_detail_concurrent`’s serial tail. One step’s recoverable failure must not alter a successfully published sibling or scramble returned result order.

- **Do not build a second general transaction layer.** `plan_tool/concept_sync.py:synchronize_concepts` and `plan_tool/scope_out.py:apply_narrow` cover broader multi-artifact publication and rollback rules. This step changes only the active-detail replacement behavior used from `plan_tool/detail.py`.

## Tests

Tests in `tests/test_detail.py`:

- `test_detail_replacement_success_keeps_canonical_path_and_archives_prior_body` — a verified replacement leaves the new bytes active and the exact old bytes at the reported archive path.
- `test_detail_replacement_without_prior_body_writes_canonical_file` — first-time publication succeeds without creating an unnecessary recovery archive.
- `test_first_detail_write_failure_restores_original_absence` — partial first-write and verification failure remove the new canonical artifact and verify it is absent.
- `test_first_detail_cleanup_failure_reports_uncertain_canonical_path` — failure to restore original absence is distinct and names the incomplete path.
- `test_detail_replacement_validates_before_moving_prior_body` — an invalid prepared candidate cannot move or change the active detail.
- `test_detail_replacement_archive_directory_failure_preserves_prior_body` — archive setup failure stops before candidate publication and leaves the canonical bytes unchanged.
- `test_detail_replacement_archive_move_failure_preserves_prior_body` — failure to move the old body leaves it active and prevents the new write.
- `test_detail_replacement_write_failure_restores_prior_body` — candidate write failure after archival returns the old bytes to the canonical path and reports not written.
- `test_detail_replacement_verification_failure_restores_prior_body` — missing or different read-back bytes cause restoration rather than success.
- `test_detail_replacement_restoration_removes_incomplete_candidate` — recovery does not leave failed candidate bytes at the canonical path.
- `test_detail_replacement_restore_failure_reports_archive_path` — restoration failure has a distinct error and retains the old body at the named archive destination.
- `test_detail_replacement_failure_retains_checkpoint_and_skips_success_effects` — failure does not discard the checkpoint, update the plan pointer, archive orphans, extract lessons, commit the step, or report `written=True`.
- `test_generate_detail_serial_replacement_failure_restores_prior_body` — the ordinary `generate_detail` path returns a failed result with the old active bytes intact.
- `test_generate_detail_concurrent_replacement_failure_restores_only_failed_step` — the concurrent serial tail restores the failed step, preserves successful siblings, and keeps results in step order.
- `test_detail_replacement_phase_end_distinguishes_restore_failure` — run-log reporting separates a restored replacement failure from a failed restoration.

### Test-creation order (feature step)

Add the successful replacement and first-write cases with the replacement helper. Add archive setup, move, candidate-write, and post-write verification failures with the journal and restoration path. Add restoration-failure reporting before wiring the helper into both publication tails. Finish with serial/concurrent orchestration and success-side-effect regressions. Every new test must be green before this step is considered finished.

## Acceptance criteria

- A successful replacement leaves the prepared Markdown bytes at the unchanged canonical detail path and preserves the prior bytes at the reported archive destination.
- Failure to create or move the recovery archive leaves the prior canonical body unchanged and performs no candidate write.
- Candidate write or post-write verification failure restores the exact prior active bytes and returns `DetailResult.written=False`.
- Restoration failure returns a distinct error that contains the surviving archive path and does not delete that recovery copy.
- First-time detail publication still succeeds without requiring a prior body or recovery archive.
- Serial and concurrent publication use the same replacement behavior; a failed concurrent step does not alter sibling detail bytes or result ordering.
- Plan-pointer updates, checkpoint discard, orphan archival, written-success reporting, lesson extraction, and per-step commit occur only after verified replacement success.
- All new replacement cases in `tests/test_detail.py` pass.

## References

- [Python os — Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Use the replacement and rename guarantees when choosing how to publish and restore files on the same filesystem.

## Deferred

- **General-purpose filesystem transactions** — this step hardens only active-detail replacement; it does not create another transaction framework.
- **Multi-artifact concept publication and restart recovery** — retain the prerequisite publication authority’s contracts rather than changing `plan_tool/concept_sync.py:synchronize_concepts` from this step.
- **Scope-out rollback consolidation** — `plan_tool/scope_out.py:apply_narrow` has a separate journal and publication boundary; reconcile should decide whether any low-level recovery primitive can be shared later.
- **Include-triggered regeneration bounds and deduplication** — step 6 owns candidate grouping, retry limits, contradiction handling, and shared publication behavior.
