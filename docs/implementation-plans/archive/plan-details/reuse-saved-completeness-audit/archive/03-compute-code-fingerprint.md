> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `compute_code_fingerprint(plan, plan_path, repo_root)` to `completeness_report.py`

## Summary

- Add a public `compute_code_fingerprint(plan, plan_path, repo_root) -> dict[str, str]` to `plan_tool/completeness_report.py` that hashes the plan's **code surface** — exactly `plan_tool/scope_guard.py:compute_drift_watched_paths(plan, plan_path, repo_root)` (in-scope `step.files`/`step.creates` **minus** the plan markdown and per-step detail files) — into an opaque `{repo-relative-posix-path: sha256-hex}` map.
- **Load-bearing decision:** the producer lives in this assembly module (which already imports `plan_tool.review`/`plan_tool.review_persistence`), so adding top-level imports of `compute_content_hash` (from `plan_tool/drift_detection.py`), `compute_drift_watched_paths` (from `plan_tool/scope_guard.py`), and `Plan` (from `plan_tool/schema.py`) is cycle-free. The leaf-inline-the-loop discipline that bound step 1's `review_persistence.py` does **not** apply here.
- **Second load-bearing decision:** skip every path whose `compute_content_hash` returns `None` (a declared `creates:` file not yet on disk, or an unreadable file) and key survivors by `path.relative_to(repo_root).as_posix()`, emitted in sorted-key order — so the map is reproducible across machines/checkouts, the only property that makes the later save→reload comparison meaningful.
- Primary file: `plan_tool/completeness_report.py` (new function + three imports). Tests: `tests/test_completeness_report.py` (approx. 7 fresh cases).
- **Observable result on green:** `compute_code_fingerprint` returns a stable dict that (a) covers exactly the code surface, never the plan/detail markdown; (b) changes iff a watched code byte changes; (c) drops not-yet-created `creates:` paths; and (d) is byte-for-byte reproducible regardless of filesystem enumeration order.

## Table of Contents

- [Why](#why) — why the code-side fingerprint producer lands here as its own step.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and the edits per file.
- [Implementation](#implementation) — the function shape, the consumed helpers, the skip-and-key rules, and import topology.
- [Tests](#tests) — surface-scoping, sensitivity, missing-file, opacity, and reproducibility cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib hashlib / pathlib and the in-repo producers this step consumes.
- [Deferred](#deferred) — the writer wiring and the reuse/staleness consumer left to later steps.

## Why

The "Reuse Saved Completeness Audit" feature decides whether a saved audit is still valid by comparing the plan **and** code state captured at save time against current state. Step 1 added the storage slots (`SavedReview.plan_fingerprint` / `code_fingerprint`) and the plan-side `compute_plan_fingerprint(plan_path)`; step 2 promoted `drift_detection._compute_content_hash` to the public `compute_content_hash` so an assembly-layer consumer can import a real public symbol. But nothing yet **produces** the code-side digest — `code_fingerprint` is stored as an opaque caller-supplied dict, and there is no function that computes it. This step adds that producer. It lands after step 2 (`depends_on: 2`) because it imports the just-promoted `compute_content_hash`, and it is the complement of `compute_plan_fingerprint`: together the two fingerprints partition a plan's footprint into code (this step) vs plan/detail markdown (step 1) with no overlap. The populate seam (step 4) and the read/verdict seam (step 5) both consume this function, so it must exist as a standalone, Claude-free helper first.

## Files (creates vs edits)

- **New files:** none. (The frontmatter's `plan_tool/completeness_report.py::compute_code_fingerprint` entry is a **new symbol** created inside an edit to that file — not a new file.)
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add three top-level imports (`compute_content_hash`, `compute_drift_watched_paths`, `Plan`) and the `compute_code_fingerprint` function.
  - `tests/test_completeness_report.py` — add approx. 7 fresh cases for surface-scoping, digest sensitivity, missing/uncreated-file skipping, opacity, and enumeration-order reproducibility.

## Implementation

### `plan_tool/completeness_report.py`

**New top-level imports** (place alongside the existing `from plan_tool.review import (...)` / `from plan_tool.review_persistence import (...)` block):
- `from plan_tool.drift_detection import compute_content_hash` — the streamed 64 KB chunked SHA-256 helper, **public as of step 2**. Returns `None` for missing/unreadable files instead of raising.
- `from plan_tool.scope_guard import compute_drift_watched_paths` — returns `set[Path]` of the in-scope code surface (absolute + `.resolve()`d), already excluding the plan markdown and every step's detail file via `compute_in_scope_paths - _plan_owned_paths`.
- `from plan_tool.schema import Plan` — for the `plan: Plan` parameter annotation.
- **Import topology is acyclic:** `completeness_report.py` is an assembly node, not a leaf. `scope_guard.py` and `drift_detection.py` import neither `completeness_report` nor each other's consumer of it, so these three edges add no cycle. Do **not** re-inline a SHA-256 loop here out of misplaced leaf caution — that caution was specific to step 1's `review_persistence.py` leaf.

**New function `compute_code_fingerprint(plan, plan_path, repo_root) -> dict[str, str]`:**
- **Signature** — `compute_code_fingerprint(plan: Plan, plan_path: Path, repo_root: Path) -> dict[str, str]`. Note the asymmetry with `compute_plan_fingerprint(plan_path)`: the code side needs all three args (the `Plan` to enumerate `step.files`/`step.creates`, `plan_path` + `repo_root` to resolve the watched set and to re-relativize keys). A consumer that has only `plan_path` must `parse_plan(plan_path)` first to obtain the `Plan` — that wiring belongs to the consumer steps (4/5), not here.
- **Body:**
  1. `watched = compute_drift_watched_paths(plan, plan_path, repo_root)` — the canonical code-minus-docs surface. Reuse it; do **not** re-derive the `step.files`/`step.creates` enumeration or the plan/detail subtraction.
  2. Iterate `watched` in deterministic order (`sorted(watched)`), hash each via `compute_content_hash(path)`.
  3. **Skip the missing/unreadable arm:** when `compute_content_hash(path)` returns `None`, omit the entry entirely — never embed a placeholder, never crash. A declared `creates:` file legitimately does not exist yet at fingerprint time.
  4. **Key by repo-relative posix string:** `path.relative_to(repo_root).as_posix()`. `watched` paths are already absolute + resolved (from `compute_in_scope_paths`), so `relative_to(repo_root)` is well-defined. An absolute key would couple the map to the machine that computed it and defeat the cross-time comparison the fingerprint exists for.
  5. Return the `dict[str, str]`. Build it from the sorted iteration so insertion order is stable (dict preserves insertion order in 3.7+), giving byte-identical maps regardless of `set` enumeration order.
- **Foundational logic** — *content-fingerprint over a declared, possibly-incomplete file surface, keyed machine-independently*. The sibling instance is `plan_tool/review_persistence.py:compute_plan_fingerprint` (step 1), which applies the same skip-on-`None` + repo-relative-posix-key + sorted-order discipline over the **detail-bundle** surface (`plan-details/<slug>/*.md`). The two are deliberately **complementary, not consolidated**: one owns code, the other owns plan/detail markdown, and they share no path. No consolidation is warranted — `compute_plan_fingerprint` inlines its hash loop to keep `review_persistence.py` a leaf, while this function imports the shared `compute_content_hash`; forcing a single shared producer would re-introduce the leaf import edge step 1 specifically avoided. Leave them separate.
- **No docstring narration of history.** Keep the docstring terse: what it hashes (the code surface), what it skips (uncreated/unreadable), how it keys (repo-relative posix, sorted), and that the returned map is opaque to storage.

## Tests

`tests/test_completeness_report.py` — add a `compute_code_fingerprint` group. Build a real `Plan` (via the file's existing seeding helpers / `parse_plan` against a `tmp_path` plan + on-disk code files) so `compute_drift_watched_paths` resolves a genuine surface.

- `test_code_fingerprint_covers_step_files` — a plan with two `step.files` entries on disk yields a 2-key map; both keys are the repo-relative posix paths.
- `test_code_fingerprint_excludes_plan_and_detail` — the plan markdown path and a per-step `detail` file are **absent** from the returned map (they live on the plan side, not the code side).
- `test_code_fingerprint_skips_uncreated_creates` — a `creates:` path with no file on disk is omitted (not a placeholder, no error), while sibling existing files remain.
- `test_code_fingerprint_changes_on_content_edit` — editing one watched file's bytes changes that key's hex digest; untouched keys stay identical.
- `test_code_fingerprint_stable_across_calls` — two calls on unchanged disk return equal dicts (digest reproducibility).
- `test_code_fingerprint_keys_are_repo_relative_posix` — every key is relative (no leading `/`, no drive), `as_posix`-shaped, and re-resolves under `repo_root`.
- `test_code_fingerprint_deterministic_key_order` — the map's key order is sorted, independent of `step` declaration order / filesystem enumeration.

### Test-creation order (feature step)

This is a **feature** step — new behavior, freshly authored cases (no characterization/repoint posture; step 2 owned the refactor's repointed tests). Write each test alongside the function: the surface-scoping and skip cases pin the load-bearing rules (code-only surface, drop-uncreated), the sensitivity case pins digest correctness, the reproducibility cases pin machine-independence. **Green-before-done gate:** all approx. 7 new tests in `tests/test_completeness_report.py` must pass before this step is considered finished — `uv run pytest tests/test_completeness_report.py -q`.

## Acceptance criteria

- `compute_code_fingerprint(plan, plan_path, repo_root)` exists in `plan_tool/completeness_report.py` and returns `dict[str, str]`.
- The returned map's keys are exactly the repo-relative posix paths of `compute_drift_watched_paths(plan, plan_path, repo_root)` that exist on disk — never the plan markdown or per-step detail files.
- A `creates:`/missing/unreadable path contributes **no** key (skip-on-`None`), with no exception raised.
- Editing a watched file's content changes only that file's digest; an unchanged tree returns an equal dict across calls.
- Key order is sorted and independent of filesystem/`set` enumeration order.
- `completeness_report.py` imports `compute_content_hash`, `compute_drift_watched_paths`, and `Plan` at top level with no import cycle (`uv run python -c "import plan_tool.completeness_report"` succeeds).
- All new `tests/test_completeness_report.py` cases pass.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 constructor/`update`/`hexdigest` interface backing `compute_content_hash`'s streamed digest.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.relative_to` and `as_posix` for the machine-independent keys, and `sorted(set[Path])` for deterministic ordering.
- `plan_tool/scope_guard.py` (in-repo) — `compute_drift_watched_paths(plan, plan_path, repo_root)` is the canonical code surface (`compute_in_scope_paths - _plan_owned_paths`) this step hashes.
- `plan_tool/drift_detection.py` (in-repo) — `compute_content_hash` (public as of step 2) is the streamed 64 KB SHA-256 helper with skip-on-missing semantics.
- `plan_tool/review_persistence.py` (in-repo) — `compute_plan_fingerprint` is the complementary plan-side producer (step 1) whose skip/key/sort discipline this function mirrors.

## Deferred

- **Wiring the producer into the save path** — computing `compute_code_fingerprint(...)` at sidecar-write time and forwarding it into `save_review(...)` lands in step 4 (`plan_tool/cli/completeness_phases.py:_persist_and_present_report` → `write_completeness_report`). This step only adds the producer.
- **Reading/diffing the fingerprint back** — the save→reload freshness verdict (`resolve_reusable_audit`, the deletion-aware changed/deleted/new diff) is step 5. This step computes a current-state map only; it never compares two maps.
- **A shared "diff two fingerprint maps" helper** — not introduced; defer until a second consumer of map-comparison exists (the reload-boundary diff has deletion-significant semantics opposite to `drift_detection.check_drift`'s live differ, so they must not be consolidated prematurely).
- **`parse_plan` in the consumer** — obtaining the `Plan` from a bare `plan_path` is the consumer's responsibility (steps 4/5 call `parse_plan(plan_path)` before this function); not wired here.
