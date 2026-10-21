# Step 2 — Restore the archived colliding plan when a create fails after archiving it

## Summary

Make `plan_tool/create.py:create_plan` undo its collision archive when the create fails before the new plan is durably registered. Today the `should_replace` block moves the colliding plan (and its `plan-details/<slug>/` bundle) into `archive/` and drops its manifest entry, then runs `write_new_plan`, the post-write reparse, concept synchronization, and `append_to_manifest` — any failure in that stretch strands the old plan in `archive/` with a "Replaced by …" notice pointing at a plan that never landed. The step adds a restore path: on failure inside that window, create removes its own partial outputs, moves every archived file back to its original path with the replacement notice stripped, re-adds the removed manifest entries, and re-raises the original error. The key design decision is restore-on-failure rather than archive-after-publication: when the collision shares the slug and priority bucket, the old plan sits at the exact path `predict_plan_path` gives the new plan, so the archive move cannot be deferred past the write. Files: `plan_tool/create.py` and `tests/test_create.py`.

## Table of Contents

- [Summary](#summary) — what the step does and the main design decision
- [Table of Contents](#table-of-contents) — this list
- [Why](#why) — how a failed create strands the archived collision plan today
- [Input](#input) — the in-memory and on-disk contracts the restore path reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the edits per file
- [Implementation](#implementation) — the failure window, the restore helper's contract, and the parts that must not vary
- [Tests](#tests) — new unit and integration tests plus the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — stdlib docs for the move/replace semantics the restore relies on
- [Deferred](#deferred) — neighboring recovery work owned by other steps

## Why

In `create_plan`, the `should_replace` block (the `for collision in collisions:` loop) calls `archive_existing_source` and `remove_from_manifest` for each colliding plan *before* the new plan exists. `remove_from_manifest` writes the manifest to disk immediately, and `archive_existing_source` moves the old plan to `archive/<stem>.replaced[.N].md` (plus its detail bundle to `archive/plan-details/<slug>[.replaced.N]/`) with a `_replacement_notice` prepended to every `.md` file. Several things can still fail after that point: `write_new_plan`, the post-write reparse (`CreateError` "plan was written but fails post-write reparse"), a `synchronize_concepts` rejection on the signed path — which already unlinks the new plan and its concepts sidecar before raising — the unsigned arm's `save_concepts`, or `append_to_manifest` itself. On every one of those paths the operator ends up with no usable plan: the old one is buried in `archive/`, deregistered, and stamped with a notice claiming it was superseded. This is gap 1 in the plan's problem statement ("a failed create can strand an archived collision plan"), and it is the create-side twin of step 6's detail-replacement fix.

## Input

- **Archive pair contract** (`plan_tool/create.py:ArchiveResult`): `archived` is a list of `(original, archived)` `Path` pairs — first the plan source pair, then one pair per detail-bundle *file* (directories are never listed). `create_plan` accumulates these into its local `replaced_archives` list, which is exactly the restore path's work list. Pairs carry the resolved numbered-generation targets (`.replaced.N`), so restore needs no target arithmetic of its own.
- **Replacement notice shape** (`plan_tool/create.py:_replacement_notice`): a two-line blockquote ending in a blank line, parameterized only by `_display_path(predicted, repo_root)`. Both the archived plan and every archived detail `.md` get this exact prefix; non-`.md` detail files are copied byte-for-byte with no notice.
- **Manifest contract** (`plan_tool/create.py:append_to_manifest` / `remove_from_manifest`): a JSON object `{"plans": [<repo-relative str>, ...]}` written immediately via `atomic_write_text`. `create_plan`'s local `replaced_manifest_entries` holds the repo-relative strings that were removed and is the re-add work list.
- **Predicted plan path** (`plan_tool/create.py:predict_plan_path`): deterministic from `output_dir`, `slug`, and priority, computed before the archive loop — the failure handler uses it (plus `concepts_path` from `plan_tool/concept_tree.py`) to find create's own partial outputs even when `write_new_plan` itself was the thing that failed.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/create.py` — add a public restore helper (e.g. `restore_archived_collisions`) that inverts `archive_existing_source` from a list of `(original, archived)` pairs; wrap the stretch of `create_plan` from the `should_replace` archive loop through `append_to_manifest` in a failure handler that removes create's partial outputs, calls the restore helper, re-adds the removed manifest entries, and re-raises.
  - `tests/test_create.py` — unit tests for the restore helper plus integration tests driving `create_plan` through archive-then-fail scenarios (modeled on `TestCreatePlanReplaceOnCollision` and `TestCreatePlanPostWriteReparse`).

## Implementation

**What must be true on green:** when `create_plan` archives one or more colliding plans and then fails anywhere before `append_to_manifest` returns, the on-disk state after the raise matches the state before the archive: old plan back at its original path with its original bytes (notice stripped), detail bundle back under `plan-details/<slug>/`, manifest listing the old entry again, no `.replaced*` leftovers in `archive/`, and no partial new plan or `concepts.json` at the predicted path. The original exception still propagates. A create that fails *without* having archived anything, or *after* the manifest commit, behaves exactly as today.

- **Design decision — restore-on-failure, not reorder.** The plan's Architecture section frames this as "ordering over journaling": either archive only after publication succeeds, or restore on failure. Reordering is impossible in the common case — a collision with the same slug and priority occupies the exact path `write_new_plan` will use (`predict_plan_path`), so the old plan must move before the write. Restore-on-failure is therefore the required shape. Per the same Architecture rule, add no on-disk journal or lock: the restore works from the in-memory `replaced_archives` / `replaced_manifest_entries` lists, and a hard process kill mid-window stays a git-recovery scenario (document that limit in the helper's docstring).
- **The failure window.** It opens at the first successful `archive_existing_source` call and closes when `append_to_manifest` returns. After that the new plan is written, reparsed, concept-synchronized, and registered — a later failure (e.g. inside the `--iterate` convergence loop) leaves a valid registered plan, and restoring then would destroy good work. Do not extend the window past the manifest commit.
- **Failure-handler ordering (not free to vary).** On an exception inside the window, with `replaced_archives` non-empty:
  1. Remove create's own partial outputs first: the file at the predicted plan path and `concepts_path(predicted)`, both under `contextlib.suppress(FileNotFoundError)` — the signed sync-failure arm has already unlinked both before raising, so tolerate absence. This must precede the file restore so the old plan can reclaim a same-slug path without the helper ever overwriting a file it can't account for.
  2. Restore the archived files via the helper.
  3. Re-add each entry in `replaced_manifest_entries` (one way: `append_to_manifest(mf, repo_root, repo_root / rel)` per entry).
  4. Re-raise the original exception. Restore problems become printed warnings (match `archive_existing_source`'s `skipped` style), never a raise that masks the real failure.

  Likely shape: a `try/except` around the region with the handler in the `except`; catching `BaseException` (so Ctrl-C during the window also restores) is recommended but the implementer can weigh that — the window contains no Claude calls, only fast deterministic work.
- **Restore helper contract.** Public function in `plan_tool/create.py`, sibling of `archive_existing_source`, taking the `(original, archived)` pairs plus whatever it needs to reconstruct the notice (the predicted path and `repo_root`, or the notice text itself). Behavior per pair:
  - `.md` files: read the archived bytes, strip the exact `_replacement_notice(...)` prefix when present, write to the original path (`mkdir(parents=True)` as needed), delete the archived copy. When the prefix does not match, restore the bytes unchanged — never guess-strip.
  - non-`.md` files: restore byte-for-byte.
  - **Never overwrite:** if the original path already exists, skip that file with a warning and leave the archived copy in place. Step (1) of the handler is what keeps this from firing on create's own leftovers.
  - After restoring, prune the now-empty archived detail directory and, best-effort, an empty `archive/` dir. Return a result the caller and tests can inspect (an `ArchiveResult`-style restored/skipped split is the natural shape).
- **What stays untouched.** `archive_existing_source`, `_archive_targets`, and the happy-path replace flow keep their current behavior — the existing `TestCreatePlanReplaceOnCollision` assertions must stay green unmodified. The sync-failure arm's existing unlink-then-raise cleanup also stays; the new handler wraps around it.
- **Shared-logic check.** The same archive-without-restore shape exists in `plan_tool/detail.py:_archive_existing_detail` (detail replacement) — that is step 6's scope, not this step's. The CLI-side seed archive (`TestCliArchivesOriginalSeed` flow) runs only after `create_plan` returns successfully, so it is outside the window and needs no change.

## Tests

All in `tests/test_create.py`. Unit tests for the helper stage a real archive with `archive_existing_source` first, so the two functions are tested as inverses.

- `test_restore_moves_plan_back_and_strips_notice` — after archive + restore, the original path holds the pre-archive bytes and the `.replaced.md` copy is gone.
- `test_restore_details_bundle_round_trips` — a bundle with a `.md` (notice stripped) and a non-`.md` file (bytes unchanged) lands back under `plan-details/<slug>/`; the archived bundle dir is removed.
- `test_restore_handles_numbered_generation` — a `.replaced.1` pair restores to the original path correctly.
- `test_restore_skips_occupied_original_path` — a foreign file at the original path is left untouched; the pair is reported skipped and the archived copy stays.
- `test_restore_leaves_unrecognized_prefix_intact` — an archived `.md` whose head doesn't match the notice restores byte-for-byte.
- `test_create_failure_after_archive_restores_collision` (integration) — `replace_on_collision=True` plus a monkeypatched `parse_plan` failing the post-write reparse: `CreateError` raises, old plan and details are back, manifest lists the old entry, no file remains at the predicted new path and no `concepts.json` beside it, `archive/` has no `.replaced*` leftovers.
- `test_create_manifest_append_failure_restores_collision` (integration) — monkeypatch `append_to_manifest` to raise on the new plan's registration; same restored end state.
- `test_failure_after_manifest_commit_does_not_restore` (integration) — force a failure just past the commit point (e.g. monkeypatch `collect_deterministic_findings` to raise); the archive and new plan both survive.
- `test_restore_failure_does_not_mask_create_error` — a restore-time `OSError` (monkeypatched write) still surfaces the original `CreateError`, with a warning about the unrestored file.

### Test-creation order (feature step)

This is a **feature** step. Add the five helper unit tests alongside the helper, then the four `create_plan` integration tests alongside the failure handler (reuse the `_stub_propose_references` fixture and `_basic_metadata_answers`/`_single_step_answers` builders the sibling classes use). Gate: every test above is green — plus the existing `TestCreatePlanReplaceOnCollision` and `TestCreatePlanPostWriteReparse` classes unchanged and green — before this step is finished.

## Acceptance criteria

- `create_plan(..., replace_on_collision=True)` with a forced post-write reparse failure raises `CreateError` and leaves: the colliding plan at its original path with its pre-archive bytes, its detail bundle under `plan-details/<slug>/`, its manifest entry present, no `.replaced*` files under `archive/`, and no plan file or `concepts.json` at the predicted new path.
- The restore helper skips (with a warning) any original path that already exists and any unrecognized notice prefix; it never overwrites and never raises past the original failure.
- A failure raised after `append_to_manifest` returns performs no restore: the new plan stays registered and the archive stays put.
- A create with no collisions (or a declined replace) has zero behavior change.
- All new tests plus the existing `TestCreatePlanReplaceOnCollision`, `TestArchiveExistingSource`, and `TestCreatePlanPostWriteReparse` classes pass; `uv run pytest tests/test_create.py -q` is green.

## References

- [shutil — High-level file operations: shutil.move](https://docs.python.org/3/library/shutil.html) — os.rename-first/copy-fallback and overwrite semantics governing the archive-move and its inverse.
- [pathlib — Path.replace, Path.rename, Path.write_text](https://docs.python.org/3/library/pathlib.html) — rename/replace/write semantics (overwrite behavior, platform differences) for moving the archived plan back and cleaning up archive dirs.
- [os — Files and directories: os.replace](https://docs.python.org/3/library/os.html#os.replace) — the atomic same-filesystem rename primitive behind `atomic_write_text`, which the manifest re-add reuses.

## Deferred

- Detail-file replacement restore (`plan_tool/detail.py:_archive_existing_detail`) — same archive-before-validate shape, owned by step 6.
- Routing the unsigned `save_concepts` fallbacks through `synchronize_concepts` — step 3; this step only deletes the sidecar as a partial output on failure.
- Undoing `rename_plan_details_to_slug`'s rename of a `--from-existing` details bundle on a post-rename failure — a rename, not a data-losing archive; leave as-is and revisit via BACKLOG if it bites.
- Crash-hard (process-kill) recovery mid-window — stays git + fingerprint per the plan's no-journal rule; the restore covers in-process failures only.
