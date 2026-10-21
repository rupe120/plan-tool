# Step 6 — Validate the replacement detail body before archiving the old file and restore it when the write fails

## Summary

Close the detail-replacement data-loss window in `plan_tool/detail.py:_author_step_detail`: today the write block moves the active detail file into `archive/` (`_archive_existing_detail`) and then writes the replacement with `output_path.write_text`, so a write failure strands the prior body in `archive/` while the step's canonical path — which `step.detail` may still point at — holds nothing (or a truncated partial file). The step adds two guarantees: the prior file is never displaced before the replacement bytes are proven writable, and when the final write still fails, the archived prior is moved back to the canonical path before the failed outcome is returned. The key design decision is to write the replacement to a temp file in the same directory first and promote it with `os.replace` (validate-then-swap), rather than keeping the direct `write_text` and relying on restore alone — the direct write can truncate the prior body in place when the best-effort archive silently fails, and no restore can fix that. On green, an interrupted or rejected regeneration always leaves the step with a readable detail file: the prior one on failure, the new one on success. Files: `plan_tool/detail.py` and `tests/test_detail.py`.

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — the failure window in the archive-then-write sequence, and what is already in place
- [Input](#input) — the existing contracts the fix builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the edits per file
- [Implementation](#implementation) — the swap ordering, the restore arm, and the parts that must not vary
- [Tests](#tests) — new unit tests, the sanctioned seam retargets, and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib docs for the temp-write and atomic-replace semantics
- [Deferred](#deferred) — sibling archive sites and recovery work owned elsewhere

## Why

This is gap 3 in the plan's problem statement ("detail replacement safety") and the detail-side twin of step 2's create-collision restore. Half of the step's title is already true and needs only pinning: the seven-section gate runs before the write block — `_author_step_detail`'s retry loop parses each response through `parse_structured_detail_response` (falling back to `parse_detail_response`), and an unparseable response returns a failed `_StepAuthoringOutcome` before `_archive_existing_detail` is ever reached — so a *rejected* body never displaces the prior file today, but no test asserts that ordering. The remaining work is the write-failure window: after the archive move succeeds, `output_path.write_text(body + "\n")` can raise (disk full, permissions), leaving the prior body buried in `archive/` under a timestamp name, the canonical path empty, and — on a force/replace re-run — the plan's existing `step.detail` pointer dangling. Worse, `_archive_existing_detail` is deliberately best-effort (returns `None` on a failed move without blocking the write), and in that case `write_text` truncates the prior file in place, so a mid-write failure destroys the prior body with no archived copy at all. Because `_author_step_detail` is the shared authoring unit for both the serial loop and `_generate_detail_concurrent`, one fix here covers serial and `jobs>1` runs alike.

## Input

- **Archive helper contract** (`plan_tool/detail.py:_archive_existing_detail`): returns the archive destination `Path` on success, `None` when there was nothing to archive *or the move failed* — so a non-`None` return is exactly the "restore is possible and may be needed" discriminator, and a `None` return with a pre-existing file is the truncate-in-place hole the temp-write closes.
- **Failed-outcome contract** (`plan_tool/detail.py:_StepAuthoringOutcome` / `DetailResult`): the write-failure arm returns `succeeded=False`, `written=False`, `skipped_reason` starting `"write failed: "`, `handle.fail(...)`, and `phase_outcome="error"`. Run-log consumers and several existing tests key on these strings; the fix must keep them unchanged.
- **Checkpoint durability** (the `save_checkpoint` call just above the write block, discarded only by the caller after the plan pointer is set): the parsed raw response survives a write failure, so the *replacement* body is already recoverable on the next run. This step protects the *prior* body; together they mean a failed replacement loses nothing.
- **`*.md` discovery surfaces**: `_archive_orphan_details` globs `{step_id:02d}-*.md`, `_discover_siblings` and the concurrent sibling snapshot glob `*.md`, and `plan_tool/review_persistence.py:compute_plan_fingerprint` frames every `plan-details/<slug>/*.md` file into the plan fingerprint. Any temp file this step introduces must not match `*.md`, or it leaks into sibling prompts and silently perturbs the fingerprint that concept-sync compare-and-swaps (step 4's routed tail) key on.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — rework the write block at the tail of `_author_step_detail` (the `try:` around `output_path.parent.mkdir`, `_archive_existing_detail`, and `output_path.write_text`) into temp-write → archive → atomic promote, with a restore arm on failure; add a small restore helper next to `_archive_existing_detail` (one way: `_restore_archived_detail(archived: Path, output_path: Path) -> bool`).
  - `tests/test_detail.py` — new unit tests for the ordering, the restore, and the no-partial-file guarantees; retarget the three existing write-failure tests whose `Path.write_text` monkeypatch keys on the detail path (named in Tests).

## Implementation

What must be true when the step is done:

- **A rejected body never displaces the prior file.** The existing gate-before-archive ordering holds (it already does — the parse-exhaustion return precedes the write block) and is pinned by a regression test.
- **A failed write never leaves the step without a detail file.** If the prior file was archived and the replacement write fails, the prior file is back at the canonical path when `_author_step_detail` returns; if there was no prior file, the canonical path holds no partial/truncated file.
- **The prior body is never truncated in place.** No code path opens the canonical path for writing while it still holds the prior body.

Recommended shape (the swap ordering is the constraint; the exact helper layout is the implementer's):

- **Write the replacement to a temp file first.** After `output_path.parent.mkdir(...)`, write `body + "\n"` to a uniquely named temp file in `output_path.parent` (same directory ⇒ same filesystem, which `os.replace` atomicity requires). One way: `tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=output_path.parent, prefix=f".{output_path.stem}.", suffix=".tmp", delete=False)`. A failure here returns the existing `"write failed: ..."` outcome with the prior file completely untouched — not even archived. Two constraints on the temp name: it must not end in `.md` (see Input — sibling globs and `compute_plan_fingerprint`), and it must be race-free under `jobs>1` (`tempfile` gives this; hand-rolled fixed names don't).
- **Then archive, then promote.** Call `_archive_existing_detail(output_path)` exactly as today (best-effort, message unchanged — `test_archived_previous_detail_plain` pins the wording), then `os.replace(temp_path, output_path)`. On success the temp file is consumed; nothing else changes downstream (the deferred plan-update record, orphan sweep, and checkpoint discard all stay caller-side as they are).
- **Restore arm on failure after the archive.** If anything raises after `_archive_existing_detail` returned a non-`None` destination: first unlink the temp file (`contextlib.suppress(FileNotFoundError)` — it is this operation's own partial output), then move the archived prior back to `output_path` — only when `output_path` does not exist, so restore can never clobber anything — then return the failed outcome with the *original* error in `skipped_reason`. A restore-time `OSError` degrades to a printed warning naming the archive path (`warn(...)` from `plan_tool/console.py`, matching the module's messaging) and must not replace the original error; this mirrors step 2's handler discipline (delete own partials → restore → surface the original failure).
- **Keep the failed-outcome contract frozen.** `written=False`, the `"write failed: "` reason prefix, `handle.fail`, and `phase_outcome="error"` are consumed by run-log tests and the concurrent failure-isolation test; the fix changes what's on disk after a failure, never how the failure is reported.

Rejected alternative: keep the direct `output_path.write_text` and add restore-on-failure only. It is a smaller diff and needs no test retargeting, but it cannot fix the truncate-in-place case (best-effort archive returned `None`, prior file still at the canonical path, `write_text` truncates before failing) and still leaves a partial file when there was no prior detail. The plan's architecture section calls for detail files "never left half-written"; only the temp-write/replace shape delivers that.

Foundational logic — *restore a displaced artifact when the operation that displaced it fails* — appears elsewhere in the codebase in shapes this step must not absorb: step 2 owns the create-collision restore in `plan_tool/create.py`, and `plan_tool/scope_out.py:apply_narrow` owns journaled rollback for narrows. The other three `_archive_existing_detail` call sites do not have this step's failure mode (see Deferred).

## Tests

All in `tests/test_detail.py`, driving `generate_detail` with a stub invoker (per TESTING.md — no real backend).

New tests:

- `test_unparseable_response_leaves_prior_detail_unarchived` — prior detail on disk, invoker returns garbage on every attempt; the prior file is unchanged at the canonical path and no `archive/` entry exists (pins gate-before-archive).
- `test_temp_write_failure_leaves_prior_detail_in_place` — the temp-file write fails (monkeypatched); prior file unchanged at the canonical path, no `archive/` entry, result `written=False` with a `write failed` reason.
- `test_write_failure_restores_archived_prior_detail` — prior detail on disk, the final promote fails (monkeypatch `os.replace` on the detail module or key on the destination path); prior body is back at the canonical path unchanged, no leftover temp file in the plan-details directory, result carries the `write failed` reason.
- `test_write_failure_without_prior_detail_leaves_no_partial_file` — no prior file, write fails; the canonical path does not exist and no temp file remains.
- `test_restore_failure_does_not_mask_write_error` — restore raises (monkeypatched); `skipped_reason` still carries the original write error and stderr warns with the archive path.
- `test_restore_after_real_archive_round_trip` — unit test of the restore helper staged by the real `_archive_existing_detail` (not hand-built fixtures): archive, then restore, prior bytes identical at the canonical path.
- `test_failed_replacement_keeps_plan_fingerprint_stable` — with a prior detail file, a failed replacement leaves `compute_plan_fingerprint(plan_path)` equal to its pre-run value (pins both the restore and the not-`.md` temp name).

Sanctioned seam retargets (the `Path.write_text` monkeypatch in each keys on the detail path and no longer fires once the write moves to temp+`os.replace`; the asserted behavior stays identical, only the patch target/key changes — this is the only permitted edit to these tests):

- `test_fail_on_write_failure` (in `TestGenerateDetailProgress`) — still asserts `handle.failed` with `write failed` / `disk full`.
- `test_phase_end_error_on_write_failure` — still asserts the `phase_end` error reason.
- `test_concurrent_write_oserror_isolated` (in the concurrent test class) — still asserts one failed step isolated among green siblings; its `"beta" in self.name` key needs the retarget too.

Unchanged and expected to stay green as-is: `test_archived_previous_detail_plain` (archive message wording and single-archive count on the success path).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the seven new tests with the implementation; each covers one guarantee listed above. Retarget the three seam-coupled tests in the same change, keeping their assertions byte-identical apart from the patch target. Gate: every new and retargeted test, plus the full `tests/test_detail.py` module, must be green before this step is done.

## Acceptance criteria

- With a prior detail file present, an invoker response that fails the seven-section gate on every attempt leaves the prior file byte-for-byte at its canonical path and creates no `archive/` entry.
- With a prior detail file present, a failure of the replacement write at any point leaves the prior body back at the canonical path, no temp file in the plan-details directory, and a `DetailResult` with `written=False` and a `skipped_reason` starting `write failed:`.
- With no prior detail file, a failed write leaves nothing at the canonical path — no partial or truncated file.
- A restore-time failure prints a warning naming the archive location and does not replace the original write error in the returned outcome.
- The temp file's name does not match `*.md`, and `compute_plan_fingerprint(plan_path)` is unchanged after a failed replacement.
- The success path is unchanged: `test_archived_previous_detail_plain` passes unmodified; the three retargeted write-failure tests pass with their original assertions.
- `uv run pytest tests/test_detail.py -q` is green; no Claude call is added anywhere in the change.

## References

- [tempfile — mkstemp and NamedTemporaryFile (Python 3 standard library)](https://docs.python.org/3/library/tempfile.html) — Race-free temp-file creation for the validate-then-swap pattern; `dir=`/`prefix=`/`suffix=` control the same-directory, not-`.md` naming this step requires.
- [os — Files and directories: os.replace (Python 3 standard library)](https://docs.python.org/3/library/os.html#os.replace) — The atomic same-filesystem rename that promotes the temp file so the detail file is never left half-written.
- [pathlib — Path.replace, Path.rename, Path.write_text (Python 3 standard library)](https://docs.python.org/3/library/pathlib.html) — Rename/replace overwrite semantics and platform differences relevant to the restore move and the never-clobber guard.
- [shutil — High-level file operations: shutil.move (Python 3 standard library)](https://docs.python.org/3/library/shutil.html) — `os.rename`-first/copy-fallback semantics, relevant if the restore move must survive a cross-device archive location.

## Deferred

- The stray-file archives in `_migrate_downstream_details_after_split` and `_migrate_downstream_details_after_merge` (`plan_tool/detail.py`) — they archive an *orphan* already sitting at a rename destination, not the active detail; a failure there leaves the active file (`old_path`) untouched, so no restore window exists. Left as-is.
- The folded-file archives at the tail of `merge_steps` (`plan_tool/detail.py`) — they run only after the merged step's re-author succeeded, the same post-success shape as the CLI seed archive noted in step 2; nothing can be stranded. Left as-is.
- The create-side collision restore — owned by step 2 (`plan_tool/create.py`); this step neither touches nor re-tests it.
- Consolidating this restore with step 2's `restore_archived_collisions` into one shared helper — the two differ materially (notice stripping and manifest re-adds vs a single rename-back), so a shared abstraction needs its own refactor decision; route to reconcile if it surfaces again.
- Repointing or validating a dangling `step.detail` pointer beyond what restore fixes — pointer maintenance stays with the existing caller-side `update_step_detail_field` flow.
