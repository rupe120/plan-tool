> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a non-final sampler checkpoint to saved reviews

## Summary

Add the conceptual-audit sampler producer role to `SavedReview` in `plan_tool/review_persistence.py`, with resumable `in-progress` and non-resumable `terminal-residue` lifecycle states. Store it at one stable reports-directory path, replace that path atomically on each save, and keep its sampler payload in a new conditionally persisted `SavedReview.sampler_state` field. Reuse the existing non-final checkpoint marker so every current final-evidence gate rejects the artifact without reader changes. Green means the checkpoint round-trips safely, never collides with report stems, and remains outside the final-result contract.

## Table of Contents

- [Summary](#summary) — The change and its completed behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why sampler progress needs its own persisted role.
- [Input](#input) — Existing saved-review and durability contracts this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — The five in-scope files and their changes.
- [Implementation](#implementation) — The storage, role, and fail-closed rules.
- [Tests](#tests) — Persistence and contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for durable JSON replacement.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.

## Why

`plan_tool/review.py:audit_plan_until_stable` currently has no saved-review artifact that represents completed sampler passes without looking like a finished audit. The existing `SavedReview.is_pre_apply_checkpoint` state already keeps incomplete completeness evidence out of final readers, but it cannot identify an in-progress sampler checkpoint or carry its recovery state. This step establishes that safe storage boundary before later steps write, resume, classify, and present it.

## Input

- **Saved-review role** — Read `plan_tool/review_persistence.py:SavedReview`'s `is_pre_apply_checkpoint` field and `_normalize_checkpoint_role`; current final-evidence readers admit only the ordinary-final `False` state.
- **Saved-review serialization** — Reuse `plan_tool/review_persistence.py:save_review`, `load_review`, `update_annotation`, and `Recommendation` persistence rather than creating another report format.
- **Reports-directory discovery** — Use `plan_tool/review_persistence.py:plan_reports_dir` for the canonical location. Leave `list_saved_reviews` as a raw JSON listing; downstream code owns candidate eligibility.
- **Durable replacement** — Use `plan_tool/fileio.py:durable_write_text` after creating the reports directory, because that helper requires an existing parent directory.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — Add the stable checkpoint path, its save/load helpers, the sampler-checkpoint discriminator, `SavedReview.sampler_state`, and fail-closed role normalization.
  - `plan_tool/data_contract.py` — Register `SavedReview.sampler_state` as conditionally persisted.
  - `DATA_CONTRACT.md` — Document the stable artifact, both sampler lifecycle states, and the sampler-state field.
  - `tests/test_review_persistence.py` — Cover stable replacement, state round trips, malformed-role handling, and raw listing behavior.
  - `tests/test_data_contract.py` — Cover registry and documentation drift checks for `SavedReview.sampler_state`.

## Implementation

- **Use one fixed checkpoint path.** Add a named path helper and filename constant in `plan_tool/review_persistence.py` for one JSON file under `plan_reports_dir`. Use a clear stable name such as `in-progress-sampler-checkpoint.json`; it must not end in `COMPLETENESS_SIDECAR_SUFFIX` or overlap the timestamped completeness-report stems.

- **Keep timestamped report saving unchanged.** Keep `save_review` and `_timestamp_filename` as the normal final-report path. Add a focused sampler-checkpoint save helper that targets the stable path and uses `durable_write_text` after creating its parent directory.

- **Replace in place.** Every sampler-checkpoint write must target the same path, so a completed pass replaces the prior durable boundary rather than creating one artifact per pass. The helper must preserve the atomic replacement behavior supplied by `durable_write_text`.

- **Represent sampler lifecycle with a positive discriminator.** Add the step's planned `SavedReview.sampler_state` mapping and expose a read-side predicate such as `SavedReview.is_in_progress_sampler_checkpoint`. A valid continuing checkpoint must be `kind="completeness"`, carry `is_pre_apply_checkpoint=True`, have `qualified_result` set to JSON `null`, and carry a valid mapping whose lifecycle is `in-progress`; the same non-final carrier with lifecycle `terminal-residue` is non-resumable diagnostic evidence.

- **Reuse the existing non-final role marker.** Keep newly written sampler checkpoints in the recognized version-4 role-aware form instead of minting a new `kind` or a marker that older role handling could read as final. This makes every existing predicate that requires `is_pre_apply_checkpoint is False` reject the checkpoint before step 4 adds its explicit reader coverage.

- **Fail closed on contradictory state.** Extend `_normalize_checkpoint_role` and `load_review` so a sampler-state field paired with an ordinary-final marker, an unsupported kind, or an invalid serialized shape loads as unknown or fails loading; it must never normalize to `False`. A malformed sampler checkpoint may become unusable for resume, but it must remain non-final.

- **Keep pre-apply, in-progress, and terminal residue distinct.** A pre-apply checkpoint has no `sampler_state`; the positive sampler-state lifecycle lets later ledger work identify an in-progress checkpoint or non-resumable terminal residue without treating either as pre-apply.

- **Keep sampler data separate from audit evidence.** Persist sampler recovery data only through `SavedReview.sampler_state`. Do not add keys to the exact-shape `audit_coverage` object, `qualified_result`, or the public `completeness-audit --json` payload.

- **Preserve the field on rewrites.** Update `update_annotation` to retain a valid sampler checkpoint’s state and role if called directly. When a malformed state normalizes to unknown, preserve an unknown non-final role rather than rewriting it as a final artifact.

- **Provide a narrow checkpoint loader.** Add a loader for the stable path that distinguishes absent, valid, and unreadable/non-sampler artifacts without treating read failure as usable state. Step 3 owns semantic validation of the sampler payload, identity comparison, and fresh-start messaging.

- **Leave reader modules alone in this step.** Do not filter `list_saved_reviews` or edit final-evidence readers now. The `True` non-final role is the storage-layer guarantee they already reject; step 4 owns the full reader and ledger test matrix.

- **Reject a new standalone `kind`.** A new kind alone is not safe because `plan_tool/cli/review_cmd.py:_direct_walk_ineligibility` first trusts the role and only gives extra treatment to completeness saves. The checkpoint must therefore retain the completeness kind and fail the established role check.

## Tests

### Tests for this step

- `test_sampler_checkpoint_path_is_stable_and_outside_completeness_stems` — asserts the path is under `plan_reports_dir`, has one fixed filename, and does not match the timestamped completeness report or sidecar suffixes.
- `test_save_sampler_checkpoint_replaces_the_same_artifact_and_round_trips_state` — saves two checkpoints and asserts one stable file remains with the later sampler state and persisted `Recommendation` data.
- `test_sampler_checkpoint_uses_a_nonfinal_role` — asserts a newly written checkpoint loads as in-progress and never exposes `is_pre_apply_checkpoint is False`.
- `test_terminal_sampler_residue_uses_the_nonresumable_lifecycle` — asserts a published terminal transition has the terminal-residue lifecycle and cannot satisfy the in-progress predicate.
- `test_sampler_state_with_a_final_or_invalid_role_fails_closed` — asserts contradictory marker, kind, or state-shape inputs load as unknown or fail loading rather than becoming an ordinary final artifact.
- `test_load_sampler_checkpoint_declines_absent_or_unreadable_artifacts` — asserts absence and malformed JSON do not return resumable state.
- `test_update_annotation_preserves_sampler_checkpoint_state_and_nonfinal_role` — asserts the rewrite path does not strip the state field or turn a sampler checkpoint into final evidence.
- `test_list_saved_reviews_keeps_sampler_checkpoint_in_the_raw_listing` — asserts raw saved-review discovery remains unfiltered so later readers can apply their own role checks.
- `test_saved_review_sampler_state_is_conditionally_registered` — asserts `plan_tool/data_contract.py:persisted_dataclass_contracts` registers the new field as conditional.
- `test_saved_review_sampler_state_and_role_are_documented` — asserts `DATA_CONTRACT.md` documents the field, stable artifact, and both sampler lifecycle states.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A sampler checkpoint has one stable JSON path under the plan’s reports directory, and a second save replaces that same artifact.
- The stable checkpoint filename does not match `COMPLETENESS_REPORT_SUFFIX` or `COMPLETENESS_SIDECAR_SUFFIX`.
- A valid checkpoint loads with a positive in-progress discriminator and a non-final role; it never loads as `is_pre_apply_checkpoint is False`.
- A missing, malformed, or contradictory checkpoint cannot become ordinary final evidence.
- `SavedReview.sampler_state` persists separately from `audit_coverage`, round-trips through `load_review`, and is preserved by `update_annotation`.
- `list_saved_reviews` still returns the stable checkpoint as a raw candidate; the checkpoint’s non-final role is what keeps existing downstream role checks from admitting it.
- `plan_tool/data_contract.py:persisted_dataclass_contracts` and `DATA_CONTRACT.md` both describe `SavedReview.sampler_state`.
- Existing timestamped review and completeness saves retain their current filenames and final-role behavior.

## References

- [os — Miscellaneous operating system interfaceshttps: — Read `os.replace()` and `os.fsync()` behavior behind durable replacement.
- [tempfile — Generate temporary files and directorieshttps: — Read the temporary-file pattern used before atomic replacement.
- [json — JSON encoder and decoderhttps: — Read JSON encoding and decode-failure behavior for the checkpoint payload.
- [dataclasses — Data Classeshttps: — Read `asdict()` and field behavior used by persisted `Recommendation` values.

## Applicable guardrails

- **The plan’s `## Step intent` — persistence substrate only:** Limit this step to the saved-review role, stable path, loader, and contract field. Pass-boundary writes and terminal transitions belong to step 2.
- **The plan’s `## Out of scope`, audit-surface boundary:** Do not extend checkpointing to other audit or execution lanes, and do not add a new CLI surface.
- **The plan’s `## Out of scope`, final-evidence boundary:** Do not change reusable-final selection, finding semantics, or the public JSON payload.
- **The plan’s `## Out of scope`, concurrency and artifact-history boundary:** Rely only on atomic replacement here; do not add locking, migration, backfill, or cleanup of historical artifacts.
- **The plan’s `## Architecture`, reader-ordering fence:** Make the checkpoint non-final in persistence first. Step 4 owns reader-specific edits and the ledger’s explicit in-progress classification.
