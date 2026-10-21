> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Promote `_compute_content_hash` to public `compute_content_hash` and add `compute_code_fingerprint` in `completeness_report.py`

## Summary

- Rename `plan_tool/drift_detection.py:_compute_content_hash` to a public `compute_content_hash` (behavior-preserving) so a second consumer can share the repo's canonical streamed-SHA-256 helper instead of inlining it.
- Add `compute_code_fingerprint(plan, plan_path, repo_root) -> dict[str, str]` to `plan_tool/completeness_report.py`: hash every path in `plan_tool/scope_guard.py:compute_drift_watched_paths` (the code surface minus plan/detail), keyed by **repo-relative posix string**, emitted in **sorted key order**.
- **Load-bearing decision:** the fingerprint omits missing/unreadable paths (the `None` arm of `compute_content_hash`) so a not-yet-created `creates:` file doesn't poison the map; the dict is the opaque `code_fingerprint` value step 1's `SavedReview` stores verbatim.
- On green: `compute_content_hash` is importable by name and all drift call sites still pass; `compute_code_fingerprint` returns a deterministic sorted `{rel_path: sha256_hex}` map that changes iff a watched code file's bytes change.

## Table of Contents

- [Why](#why) — what reuse needs from a shared hash helper and a code-surface fingerprint.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and their tests.
- [Implementation](#implementation) — the promotion, the new fingerprint function, key normalization, and import topology.
- [Tests](#tests) — promotion call-site coverage plus fingerprint determinism/sensitivity cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib hashlib / pathlib / sorted.
- [Deferred](#deferred) — call-site wiring and `compute_plan_fingerprint`'s inline loop left untouched.

## Why

The reuse feature compares the code state captured when a completeness audit was saved against the code state at reuse time. Step 1 added the storage slot — `SavedReview.code_fingerprint: dict[str, str]` — but deferred *computing* it, and (per the captured lesson) inlined a private SHA-256 loop in `compute_plan_fingerprint` specifically to avoid coupling the `review_persistence.py` leaf to `drift_detection`. This step supplies the missing producer: it promotes the existing `_compute_content_hash` to a shareable public symbol (so the new producer reuses the repo's canonical chunked-hash posture rather than minting a third copy) and adds `compute_code_fingerprint`, which turns the plan's watched code surface into the path→hash map the save step will pass through to `code_fingerprint`. It lands second because the lookup/staleness steps downstream consume the map this step produces.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/drift_detection.py` — rename `_compute_content_hash` → `compute_content_hash`; update its three internal call sites (the snapshot call in `acquire_lock`, the snapshot rebuild in `refresh_snapshot`, and the re-hash call in `check_drift`). Docstring loses the "private helper" framing.
  - `plan_tool/completeness_report.py` — add `compute_code_fingerprint`; add top-level imports of `compute_content_hash` (from `drift_detection`), `compute_drift_watched_paths` (from `scope_guard`), and `Plan` (from `schema`) for the type hint.
  - `tests/test_drift_detection.py` — repoint the five existing `_compute_content_hash` cases to the public `compute_content_hash`.
  - `tests/test_completeness_report.py` — add `compute_code_fingerprint` determinism, sorting, key-normalization, missing-file-skip, and digest-sensitivity cases (approx. 7 tests).

## Implementation

### `plan_tool/drift_detection.py`

- **Rename `_compute_content_hash` → `compute_content_hash`.** Pure rename; the body (chunked 64 KB `hashlib.sha256` read, `OSError` → `None` skip-silently posture) is byte-unchanged. Drop the "private" wording from the docstring; keep the missing/unreadable → `None` contract — downstream callers depend on it.
- **Update the three internal references.** The `watched_paths` digest snapshot in `acquire_lock`, the `content_hash_snapshot` rebuild in `refresh_snapshot`, and the re-hash in `check_drift` now call `compute_content_hash`. `release_lock` reaches it transitively through `check_drift` — no separate edit; `refresh_snapshot` is itself a direct (non-transitive) caller already covered by the three references above, so `check_drift` is not the only remaining call site.
- **No backward-compat alias.** A whole-repo grep shows `_compute_content_hash` is referenced only inside `drift_detection.py` and `tests/test_drift_detection.py`, both in this step's footprint — so a `_compute_content_hash = compute_content_hash` shim would be dead weight. Rename outright.

### `plan_tool/completeness_report.py`

- **Add `compute_code_fingerprint(plan: Plan, plan_path: Path, repo_root: Path) -> dict[str, str]`.** Place it near the other module-level helpers (e.g. after `deferred_kind` / before `build_report_md`). Steps:
  - Call `compute_drift_watched_paths(plan, plan_path, repo_root)` → the set of absolute resolved code paths (the `step.all_files` surface **minus** the plan markdown and per-step detail files — exactly the right surface, since plan/detail churn during the iterate loop and must not register as code drift).
  - For each path, compute `compute_content_hash(path)`; **skip when it returns `None`** (missing/unreadable — e.g. a declared `creates:` file not yet on disk). Including absent files would either crash or make the fingerprint non-reproducible across machines.
  - **Key normalization:** key each surviving entry by its **repo-relative posix string** — `path.relative_to(repo_root.resolve()).as_posix()` (resolve `repo_root` so an unresolved symlinked root — e.g. darwin `tmp_path` `/var`→`/private/var` — still matches the `.resolve()`d watched paths instead of falling through to the absolute fallback); fall back to `path.as_posix()` (absolute) if `relative_to` raises `ValueError` for a path outside `repo_root`. Relative posix keys keep the stored map portable so the reuse-time comparison is machine-independent.
  - **Return a sorted-key dict:** build the result by iterating `sorted(...)` over the keys so the map's insertion order is deterministic regardless of the set's iteration order — matching the "sorted keys" contract in the title and the determinism step 1's `compute_plan_fingerprint` already established for the plan side.
- **Imports — top-level, no cycle.** Add `from plan_tool.drift_detection import compute_content_hash`, `from plan_tool.scope_guard import compute_drift_watched_paths`, and `from plan_tool.schema import Plan`. Verified acyclic: `scope_guard` imports `launcher`/`schema` and `drift_detection` imports only `style`; neither imports `completeness_report`, and `launcher` imports neither — so no import cycle is introduced. This module is an assembly layer (already importing `review` + `review_persistence`), not the `review_persistence` leaf, so the leaf-preservation rule that forced step 1's inline loop does **not** apply here.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Author every case below alongside the implementation; all must be green before the step is done.

**`tests/test_drift_detection.py`** (repoint existing — promotion is behavior-preserving, so the assertions are unchanged, only the imported name):
- `test_compute_content_hash_returns_sha256_hex` — imports `compute_content_hash`; round-trips a known payload's SHA-256.
- `test_compute_content_hash_empty_file_has_empty_sha256` — empty file → canonical empty-SHA-256 constant.
- `test_compute_content_hash_returns_none_on_missing_file` — missing path → `None`.
- `test_compute_content_hash_returns_none_on_directory` — directory → `None` (`IsADirectoryError` is `OSError`).
- `test_compute_content_hash_handles_multi_chunk_file` — >64 KB payload hashes identically to a single-shot digest.
- (Optional) `test_acquire_still_snapshots_after_rename` — `acquire_lock` over a watched file still records its hash, proving the internal call sites were repointed.

**`tests/test_completeness_report.py`** (new `compute_code_fingerprint` cases; build a `Plan` with `Step(files=[...], creates=[...])` and write tmp files under `tmp_path` as `repo_root`):
- `test_code_fingerprint_hashes_watched_code_files` — a `files:` entry on disk appears in the map with its SHA-256 hex.
- `test_code_fingerprint_keys_are_repo_relative_posix` — keys equal `rel/path.py` (posix, repo-relative), not absolute.
- `test_code_fingerprint_keys_sorted` — `list(result) == sorted(result)`.
- `test_code_fingerprint_excludes_plan_and_detail` — plan markdown and a step `detail` file are absent from the map (it mirrors `compute_drift_watched_paths`, not the full in-scope set).
- `test_code_fingerprint_skips_missing_creates_file` — a declared `creates:` path with no file on disk is omitted, not crashing.
- `test_code_fingerprint_changes_when_file_bytes_change` — editing a watched file's bytes changes its hash; touching mtime without a byte change does not.
- `test_code_fingerprint_empty_when_no_code_surface` — a plan whose steps declare no `files`/`creates` yields `{}`.

## Acceptance criteria

- `from plan_tool.drift_detection import compute_content_hash` succeeds; `_compute_content_hash` no longer exists in the module.
- `compute_content_hash(p)` returns the SHA-256 hex of `p`, and `None` for a missing/unreadable path or a directory.
- `acquire_lock` / `refresh_snapshot` / `check_drift` / `release_lock` still detect content drift (existing drift tests green) — the rename changed no behavior.
- `compute_code_fingerprint(plan, plan_path, repo_root)` returns a `dict[str, str]` whose keys are repo-relative posix strings in sorted order and whose values are SHA-256 hex digests.
- The map covers exactly `compute_drift_watched_paths(...)` minus paths that don't resolve to a readable file; the plan and per-step detail files never appear.
- Editing a watched file's bytes changes that file's digest in the map; an mtime-only touch does not.
- Full suite green under `uv run pytest tests/test_drift_detection.py tests/test_completeness_report.py -q`.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — confirms the `sha256().update()/hexdigest()` streaming interface the promoted helper uses.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.relative_to` / `Path.as_posix` for the repo-relative posix key normalization.
- [Built-in `sorted()`](https://docs.python.org/3/library/functions.html#sorted) — the deterministic key ordering that makes the fingerprint enumeration-order independent.

## Deferred

- **Wiring `compute_code_fingerprint` into the save path** (`cmd_completeness` → `save_review(..., code_fingerprint=...)`) — owned by the downstream save/lookup step; this step only produces the function.
- **Rewiring `review_persistence.py:compute_plan_fingerprint` to call `compute_content_hash`** — intentionally left inlined to keep `review_persistence.py` a leaf importing only `plan_tool.review`; promoting it here would re-introduce the `drift_detection` import the leaf-preservation decision avoids.
- **Staleness comparison / warning rendering** over the stored vs. recomputed `code_fingerprint` — separate downstream step.
