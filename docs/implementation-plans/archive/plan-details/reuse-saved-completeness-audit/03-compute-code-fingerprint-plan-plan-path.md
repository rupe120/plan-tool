> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `compute_code_fingerprint(plan, plan_path, repo_root)` in `completeness_report.py`

## Summary

- Add `compute_code_fingerprint(plan, plan_path, repo_root) -> dict[str, str]` to `plan_tool/completeness_report.py` — the **code-side** producer counterpart to step 1's plan-side `compute_plan_fingerprint`. It hashes exactly the plan's in-scope **code** surface (every `step.files`/`creates` entry, excluding the plan markdown and per-step detail files) and returns an opaque repo-relative `{path: sha256}` map.
- Primary files: `plan_tool/completeness_report.py` (new function + three top-level imports) and `tests/test_completeness_report.py` (~7 fresh feature cases).
- **Load-bearing decision:** the watched code surface is `plan_tool/scope_guard.py:compute_drift_watched_paths(plan, plan_path, repo_root)` and the per-file digest is step 2's promoted `plan_tool/drift_detection.py:compute_content_hash` — reuse both, do **not** re-derive "code minus docs" or re-inline a hash loop. `completeness_report.py` is an assembly module (already imports `plan_tool.review` / `plan_tool.review_persistence`), so adding `drift_detection` / `scope_guard` / `schema` imports at top level is cycle-free; the leaf-preservation rule that forced step 1 to inline a loop in `review_persistence.py` does **not** apply here.
- **Reproducibility decision:** skip the missing/unreadable arm (digest `None` → omit the key) so a declared-but-not-yet-created `creates:` file never crashes or embeds a placeholder, and key every survivor by `path.relative_to(repo_root).as_posix()` in sorted-key order — an absolute key or a host-dependent crash would defeat the cross-time, cross-machine comparison the fingerprint exists for.
- **On green:** the returned map is the complement of `compute_plan_fingerprint`'s detail-bundle surface (no plan/detail key ever appears), it is deterministic across calls, it changes iff a watched code file's bytes change, and a missing declared file simply has no key.

## Table of Contents

- [Summary](#summary) — what the step adds and the two reuse decisions.
- [Why](#why) — why the code-fingerprint producer lands in the assembly module now.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and the edits per file.
- [Implementation](#implementation) — the function shape, the surface/hash reuse, the skip-missing + relative-key rules, and import topology.
- [Tests](#tests) — surface-coverage, exclusion, skip-missing, relative-key, determinism, and byte-sensitivity cases.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the cases to author alongside the code and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib hashlib / pathlib and the in-repo producers this step consumes.
- [Deferred](#deferred) — the persist seam and the reuse/staleness verdict left to later steps.

## Why

The "Reuse Saved Completeness Audit" feature decides whether a saved audit is still valid by comparing the plan **and** code state captured at save time against current state. Step 1 added the storage slots (`SavedReview.plan_fingerprint` / `code_fingerprint`) and the plan-side digest helper `compute_plan_fingerprint(plan_path)`; step 2 promoted the private streamed-hash primitive to the public `plan_tool/drift_detection.py:compute_content_hash`. Nothing yet **produces** the code-side digest. This step adds that producer so the populate seam (step 4) can compute both fingerprints at save time and the verdict helper (step 5) can recompute the code side against current disk. It lands in `plan_tool/completeness_report.py` — not the `review_persistence` leaf — because computing a code fingerprint needs `scope_guard`/`drift_detection`, and this assembly module already carries those-class imports freely while the persistence leaf must stay import-thin.

## Files (creates vs edits)

- **New files:** none. (The frontmatter's `plan_tool/completeness_report.py::compute_code_fingerprint` entry is a **new symbol** created inside an edit to that file — not a new file, no `creates:`.)
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add three top-level imports (`compute_content_hash` from `plan_tool.drift_detection`, `compute_drift_watched_paths` from `plan_tool.scope_guard`, `Plan` from `plan_tool.schema`); add the `compute_code_fingerprint` function.
  - `tests/test_completeness_report.py` — add ~7 fresh feature cases for the new function (surface coverage, plan/detail exclusion, skip-missing, relative-posix key, determinism, byte-sensitivity).

## Implementation

### `plan_tool/completeness_report.py`

**New top-level imports** (assembly module — acyclic, verified: `scope_guard` and `drift_detection` import neither `completeness_report` nor each other's consumer of it):

- `from plan_tool.drift_detection import compute_content_hash` — step 2's promoted public streamed-SHA-256 helper (chunked 64 KB read, returns `None` for missing/unreadable instead of raising). At HEAD only the private `_compute_content_hash` exists, so this import is unresolvable until step 2 merges — confirm step 2 exported the public `compute_content_hash` before adding this import.
- `from plan_tool.scope_guard import compute_drift_watched_paths` — the canonical "in-scope code surface minus plan/detail docs" set.
- `from plan_tool.schema import Plan` — the parameter type for the new function.

**New function `compute_code_fingerprint(plan: Plan, plan_path: Path, repo_root: Path) -> dict[str, str]`:**

- **Surface:** call `compute_drift_watched_paths(plan, plan_path, repo_root)` to get the absolute, resolved code-file set. This is exactly `step.files`/`creates` minus the plan markdown and per-step detail files — its plan/detail exclusion is load-bearing: those files churn every `apply_finding` iteration and must never register as code drift. Do not subtract docs by hand.
- **Hash each path** with `compute_content_hash(p)`. **Skip the `None` arm:** a declared `creates:` file not yet on disk (or a transiently unreadable file) yields `None` → omit its key rather than crash or store a placeholder. A vanished declared file therefore simply has no key (step 5's deletion-aware diff, not this producer, decides whether absence is staleness).
- **Key by repo-relative posix string:** `p.relative_to(repo_root.resolve()).as_posix()`, never the absolute path — an absolute key couples the map to the machine that computed it and breaks cross-clone equality. `compute_drift_watched_paths` returns `.resolve()`-d paths but `repo_root` arrives unresolved, so relate against `repo_root.resolve()` (the `jira_config.py` / `lessons.py` / `create.py` convention) or `p.relative_to` raises `ValueError` under a symlinked root (darwin `tmp_path`).
- **Deterministic order:** build the dict by iterating `sorted(...)` of either the path set or the resulting items, so the emitted key order is independent of filesystem enumeration order and the map reproduces byte-for-byte across runs.
- **Return type is an opaque `dict[str, str]`** — the exact shape step 1's `SavedReview.code_fingerprint` field stores verbatim and step 5 recomputes-and-diffs. This producer interprets nothing.

**Foundational logic:** "hash the plan's code surface (excluding plan/detail docs) into a reproducible path→digest map." The only other location that hashes a watched-path set is `plan_tool/drift_detection.py:acquire_lock` (it snapshots `compute_drift_watched_paths` output via `compute_content_hash` into `content_hash_snapshot`, keyed by `str(p)` absolute, deletions ignored — a same-process live snapshot). Keep that one separate: this fingerprint is a **persisted, cross-save** snapshot keyed repo-relative, semantically distinct from the live in-process lock snapshot. No consolidation; cite the parallel but do not touch `acquire_lock`.

## Tests

All in `tests/test_completeness_report.py` (the canonical home for this module's unit tests). Seed a small `Plan` via the project's existing plan-construction helpers/fixtures with a couple of `step.files` code paths under `tmp_path`, then write real bytes to those paths.

- `test_code_fingerprint_covers_declared_code_files` — every on-disk `step.files`/`creates` code path appears as a key; the value is its SHA-256 hex.
- `test_code_fingerprint_excludes_plan_and_detail` — neither the plan markdown nor any per-step detail file appears as a key (complement of `compute_plan_fingerprint`'s surface).
- `test_code_fingerprint_skips_missing_declared_file` — a declared `creates:` path that isn't on disk yields **no** key and does not raise.
- `test_code_fingerprint_keys_are_relative_posix` — every key is a repo-relative posix string (no absolute path, no backslash), i.e. `Path(key).is_absolute()` is `False`.
- `test_code_fingerprint_is_deterministic` — two calls on identical disk state return equal maps with identical key order.
- `test_code_fingerprint_changes_on_byte_edit` — mutating one watched file's bytes changes only that file's digest; unrelated keys are unchanged.
- `test_code_fingerprint_empty_when_no_code_files` — a plan whose steps declare only docs (or nothing) returns `{}`.

### Test-creation order (feature step)

- This is a **feature** step — `compute_code_fingerprint` is net-new behavior. Author each case above **alongside** the function.
- **Green-before-done gate:** every new test in `tests/test_completeness_report.py` must pass (`uv run pytest tests/test_completeness_report.py -q`) before the step is finished. The existing cases in that file must stay green (this step adds a symbol and three imports; it changes no existing function).

## Acceptance criteria

- `compute_code_fingerprint(plan, plan_path, repo_root)` returns a `dict[str, str]` mapping each on-disk watched code file to its SHA-256 hex digest.
- No plan-markdown or per-step-detail path ever appears as a key (output is the complement of `compute_plan_fingerprint`'s surface).
- A declared-but-absent `creates:` file produces no key and no exception.
- Every key is a repo-relative posix string; output key order is sorted/deterministic across calls.
- Editing a watched file's bytes changes exactly that file's digest.
- `plan_tool/completeness_report.py` imports `compute_content_hash`, `compute_drift_watched_paths`, and `Plan` at top level with no import cycle.
- `uv run pytest tests/test_completeness_report.py -q` is green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 constructor / `hexdigest` contract underlying `compute_content_hash` (consumed, not re-implemented).
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.relative_to` / `as_posix` for the machine-independent repo-relative keys, and sorting for deterministic order.
- [sorted() — built-in functions](https://docs.python.org/3/library/functions.html#sorted) — deterministic key ordering independent of filesystem enumeration.
- `plan_tool/scope_guard.py:compute_drift_watched_paths` (in-repo) — the in-scope code surface (minus plan/detail) this step hashes; its docstring explains why plan/detail are excluded.
- `plan_tool/drift_detection.py:compute_content_hash` (in-repo, promoted in step 2) — the streamed-SHA-256 / skip-on-missing primitive used per file.

## Deferred

- **Persisting the fingerprint** — wiring `compute_code_fingerprint` (and `compute_plan_fingerprint`) into `_persist_and_present_report` → `write_completeness_report` → `save_review` is step 4's populate seam, not this producer.
- **The reuse/staleness verdict** — recomputing this map against current disk and diffing it (changed/deleted/new keys) for a `fresh` verdict belongs to step 5's `resolve_reusable_audit`; this step only produces the current-state map.
- **A shared "diff two fingerprint maps" helper** — deferred until a second consumer exists; the live-snapshot `acquire_lock` differ stays separate (deletion-ignoring, absolute-keyed) by design.
