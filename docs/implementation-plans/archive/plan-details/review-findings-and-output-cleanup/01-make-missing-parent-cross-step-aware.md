> **Auto-archived**: this plan was swept on 2026-06-01 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Make MISSING_PARENT cross-step aware in `check_file_existence`

## Summary

- Teach `check_file_existence` (`plan_tool/review.py`) to read the plan as a whole instead of one step at a time: accumulate the directories that earlier steps' `creates:` entries will bring into existence, then downgrade a later step's `files:` entry from `MISSING_PARENT` to `NEW` when its parent directory is covered by that set.
- The load-bearing decision (resolved in the plan's Architecture section) is **positional / list order** — credit `creates:` from any step earlier in `plan.steps`, mirroring the list-order iteration in `next_runnable_step` (`plan_tool/schema.py`). No `depends_on` topological sort.
- Touch only the classification of `files:` (`created=False`) entries. `creates:` entries keep their on-disk status and `created=True`, so `detect_path_style_mismatch` and the `_describe_file_check` / `_file_check_recommendation` exemptions are unchanged.
- Observable result on green: a plan where step 1 creates `pkg/__init__.py` and step 3 edits `pkg/foo.py` no longer flags step 3's file as a suspect path; existing single-step and no-`creates:` classifications are byte-for-byte identical.

## Table of Contents

- [Why](#why) — the cross-step blind spot this fixes and why it matters now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited files and their changes
- [Implementation](#implementation) — the will-exist accumulation, the downgrade branch, and ordering invariants
- [Tests](#tests) — new cross-step cases plus the unchanged-behavior guards
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — pathlib / pytest docs relevant to this step
- [Deferred](#deferred) — out-of-scope items and the launcher consumer to watch

## Why

- `check_file_existence` classifies each declared file's parent against the **current on-disk state only**, independently per step. A pending step whose `files:` entry lives under a directory an *earlier* step's `creates:` will materialize is falsely flagged `MISSING_PARENT` — a `high`-severity finding (`_FILE_CHECK_MISSING_PARENT_SEV`) that nags the user about a path that is correct by plan design.
- Created files are already exempt (the `created=True` flag short-circuits `_describe_file_check` before the MISSING_PARENT branch), but the **directories** those created files imply do not propagate forward to later steps. This step closes that gap.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — rework the per-step loop in `check_file_existence` to thread a plan-wide will-exist directory set across steps in list order, and add the MISSING_PARENT→NEW downgrade for `created=False` entries whose parent is covered.
  - `tests/test_review.py` — add a test class for cross-step coverage and explicit unchanged-behavior guards (single-step, no-`creates:`, path-style, allow-missing-parent).

## Implementation

### `plan_tool/review.py` — `check_file_existence`

- **Keep the function signature and return type** (`(plan: Plan, repo_root: Path) -> list[StepFileCheck]`). The cross-step state lives entirely inside the function; no new public symbol.
- **Add the `PurePosixPath` import:** `plan_tool/review.py` imports only `Path` from `pathlib`; add `PurePosixPath` to that import for the will-exist math.
- **Add a will-exist accumulator** before the `for step in plan.steps` loop — a `set` of directory paths relative to repo root. Use `pathlib.PurePosixPath` for the relative-path math (plan paths are always posix); do not touch the filesystem for the projection.
- **Classify-then-accumulate ordering, per step (load-bearing):**
  1. Classify every entry for the current step exactly as today (`p = repo_root / f`; `exists()` → OK, else `p.parent.exists()` → NEW, else MISSING_PARENT).
  2. When an entry is `MISSING_PARENT` **and** `created=False`, compute its relative parent `PurePosixPath(f).parent` and downgrade to `FileExistence.NEW` if that parent is in the will-exist set.
  3. *After* building this step's `FileCheck` list, fold the current step's `creates:` parents+ancestors into the will-exist set.
  - Accumulating *after* classification guarantees a step's own `creates:` never downgrade its own `files:` — only **earlier** steps credit a later step, matching the step title's "earlier steps' creates / later steps' files" wording.
- **Ancestor expansion:** for each created path `c`, add `PurePosixPath(c).parent` and every entry of `PurePosixPath(c).parent.parents` to the set, stopping at (and excluding) the `.` root — a file directly under repo root already classifies as NEW because `repo_root` exists, so the root sentinel carries no signal. Add parents for **all** `creates:` entries regardless of their own on-disk status (an earlier step that itself has a MISSING_PARENT `creates:` still legitimately produces the directory).
- **Only `files:` entries are downgraded.** Leave `created=True` entries at their on-disk status; they are exempt from warnings via the `created` flag and `detect_path_style_mismatch` already skips them (`if fc.created: continue`).
- **Membership test detail:** compare `PurePosixPath(f).parent` against the set of `PurePosixPath` ancestors. This matches a later file's parent dir exactly against a directory an earlier `creates:` declares or nests under, without resolving symlinks or hitting disk.

### Ordering invariants this preserves (no code change, but must not regress)

- `review_plan_full` calls `check_file_existence`, then (when `allow_missing_parent`) `_promote_missing_parents`, then `detect_path_style_mismatch`. The downgrade lands *before* both, so:
  - **`--allow-missing-parent` escape hatch** still works: `_promote_missing_parents` promotes whatever `MISSING_PARENT` entries remain. Fewer entries reach it, but its contract (`MISSING_PARENT → NEW`, everything else untouched) is unchanged.
  - **`detect_path_style_mismatch` counts** are preserved in spirit: it counts non-`created` `MISSING_PARENT` entries. With no cross-step `creates:` coverage (the genuine wrong-repo-root case and all existing fixtures) nothing downgrades, so its numerator/denominator and the `_PATH_STYLE_MISMATCH_THRESHOLD` verdict are identical. The only intended change is suppressing the false hint a multi-step new-tree plan used to trip. Do **not** edit `detect_path_style_mismatch` itself.

## Tests

Add to `tests/test_review.py`. The existing `TestCheckFileExistence` and `TestCreatesFootprint` classes are the unchanged-behavior controls; add a new `TestCrossStepMissingParent` class.

- `test_earlier_creates_downgrades_later_files` — step 1 `creates: pkg/__init__.py`, step 2 `files: pkg/foo.py` with `pkg/` absent on disk → step 2's entry is `NEW`, not `MISSING_PARENT`.
- `test_ancestor_directory_credited` — step 1 `creates: a/b/c.py`, step 2 `files: a/d.py` → `a/` is credited as an ancestor → step 2 `NEW`.
- `test_own_creates_does_not_downgrade_own_files` — a single step with `creates: pkg/x.py` and `files: pkg/y.py`, `pkg/` absent → the `files:` entry stays `MISSING_PARENT` (only earlier steps credit).
- `test_later_creates_does_not_credit_earlier_step` — step 1 `files: pkg/foo.py`, step 2 `creates: pkg/__init__.py`, `pkg/` absent → step 1 stays `MISSING_PARENT` (list order, not reverse).
- `test_no_creates_unchanged` — re-assert the `_REVIEW_PLAN` fixture: step 3's `missing_dir/foo_endpoint.py` is still `MISSING_PARENT` (no step creates `missing_dir/`).
- `test_cross_step_excluded_from_path_style` — a multi-step new-tree plan whose later `files:` are all covered by an earlier `creates:` → `detect_path_style_mismatch` returns `None`.
- `test_genuine_path_style_still_fires` — a plan where ≥`_PATH_STYLE_MISMATCH_THRESHOLD` of `files:` resolve to a missing tree that **no** `creates:` covers → hint still fires with unchanged `missing_count`/`total`.
- `test_allow_missing_parent_still_promotes` — a remaining `MISSING_PARENT` (uncovered) entry is promoted to `NEW` by `_promote_missing_parents` after the cross-step pass.

## Acceptance criteria

- `check_file_existence` returns `FileExistence.NEW` for a `files:` entry whose parent directory is covered (parent or any ancestor) by an earlier step's `creates:`, given that directory is absent on disk.
- A step's own `creates:` does not downgrade that same step's `files:`; only earlier-in-list steps credit (positional order).
- For any plan with no `creates:` entries, every `FileCheck.status` is identical to the pre-change output (the `TestCheckFileExistence` fixture asserts step 3 stays `MISSING_PARENT`).
- `detect_path_style_mismatch` returns `None` for a multi-step plan whose later `files:` parents are all covered by earlier `creates:`, and still returns a `PathStyleHint` with unchanged counts for a genuine wrong-repo-root plan.
- `--allow-missing-parent` (`_promote_missing_parents`) still promotes any uncovered `MISSING_PARENT` entry to `NEW`.
- `pytest tests/test_review.py` passes, including the new `TestCrossStepMissingParent` cases.

## References

- [pathlib — Object-oriented filesystem paths (Python docs)](https://docs.python.org/3/library/pathlib.html) — `PurePosixPath.parent` and `.parents` for accumulating each created path's parent plus all ancestors without touching disk.
- [pytest — Full documentation](https://docs.pytest.org/en/stable/) — test framework used in `tests/test_review.py`.
- [How to use temporary directories and files in tests (pytest tmp_path)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — `tmp_path` fixture for constructing the on-disk layouts that distinguish `MISSING_PARENT` from `NEW`.

## Deferred

- **Full `depends_on` topological-sort semantics** — out of scope per the plan. List order is the resolved decision; a step with a *forward* `depends_on` (higher id) may mis-credit, at worst suppressing one advisory WARN.
- **Launcher preflight behavior change** — `plan_tool/launcher.py:preflight_step_paths` consumes `check_file_existence` (then applies its own `_promote_new_subdir_paths`). The cross-step downgrade will also flow into that runtime gate, slightly relaxing the single-step "parent dir absent" check when an earlier step's `creates:` covers it. This step does not edit `launcher.py`; confirm against the launcher's existing tests (`tests/test_launcher.py`) that no preflight assertion regresses, and flag for the launcher owner if a runtime-vs-projection distinction is desired later.
- **`plan_tool/create.py` consumer** — `create.py` also calls `check_file_existence` then `detect_path_style_mismatch(promoted, ...)`; same shared-primitive note applies. No change in scope here beyond verifying its tests still pass.
