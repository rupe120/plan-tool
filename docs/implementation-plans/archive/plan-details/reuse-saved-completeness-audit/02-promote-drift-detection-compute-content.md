> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Promote `drift_detection._compute_content_hash` to public `compute_content_hash`

## Summary

- Rename `plan_tool/drift_detection.py:_compute_content_hash` to the public `compute_content_hash`, repointing all three in-module call sites (`acquire_lock`, `refresh_snapshot`, `check_drift`).
- **Behavior-preserving refactor.** The function body — streamed 64 KB SHA-256, `OSError → None` skip-on-missing — is byte-identical; only the name (and its leading underscore) changes. No signature, return-type, or semantics change.
- **Load-bearing decision: outright rename, NO backward-compat alias.** Repo-wide grep shows every reference to `_compute_content_hash` lives inside `plan_tool/drift_detection.py` (3 call sites) and `tests/test_drift_detection.py` (5 tests) — both in this step's footprint. A `_compute_content_hash = compute_content_hash` shim would be dead code with no external caller to protect.
- **Why now:** step 3's `compute_code_fingerprint` (in the assembly module `plan_tool/completeness_report.py`) needs a *shared* public streamed-hash helper; promoting the existing private one is the leaf-friendly alternative to inlining a second copy of the chunk loop.
- On green: `from plan_tool.drift_detection import compute_content_hash` resolves to the same streamed-hash function, the five repointed characterization tests pass unchanged in assertion, and `_compute_content_hash` no longer exists on the module.

## Table of Contents

- [Why](#why) — why a shared public hash helper, and why promotion beats a second inline copy.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-footprint files and the per-file edits.
- [Implementation](#implementation) — the rename, the three repointed call sites, and the no-alias decision.
- [Tests](#tests) — the five characterization tests repointed to the public name.
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — characterization-first ordering and the pass-unchanged gate.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib hashlib / pathlib for the streamed hash.
- [Deferred](#deferred) — the downstream consumer wiring left to step 3 (and steps 4–5).

## Why

`plan_tool/drift_detection.py:_compute_content_hash` is the codebase's canonical streamed file-hash primitive (chunked 64 KB SHA-256, returns `None` for missing/unreadable files instead of raising), but it is **private** — its leading underscore signals module-internal use. Step 1 deliberately *inlined* a copy of this loop into `review_persistence.py:compute_plan_fingerprint` rather than import the private symbol, to keep that persistence leaf off a `drift_detection` import edge. Step 3's `compute_code_fingerprint` lives in `plan_tool/completeness_report.py` — an assembly module that already imports `drift_detection`/`scope_guard` freely — and needs the same streamed hash to compute code fingerprints. Importing a private helper across modules is a smell; this step promotes `_compute_content_hash` to the public `compute_content_hash` so the assembly-layer consumer can import a real public symbol, eliminating the second inline copy. It lands as its own refactor step (depends_on: 1) because the rename touches the shared drift-detection module and must be proven behavior-preserving before any consumer wires to it.

## Files (creates vs edits)

- **New files:** none. (The frontmatter's `plan_tool/drift_detection.py::compute_content_hash` "new" entry is a *new symbol* created by renaming the existing private function — not a new file.)
- **Existing files (edits only):**
  - `plan_tool/drift_detection.py` — rename `def _compute_content_hash` → `def compute_content_hash`; repoint the three internal call sites in `acquire_lock`, `refresh_snapshot`, and `check_drift`. Optionally refresh the docstring's framing (keep it terse — no historical narration).
  - `tests/test_drift_detection.py` — repoint the five `_compute_content_hash` characterization tests to import/call `compute_content_hash`; update the `# ---------- _compute_content_hash (#31 helper) ----------` section comment to the public name. Assertions stay byte-identical.

## Implementation

### `plan_tool/drift_detection.py`

- **Rename the definition.** `def _compute_content_hash(p: Path) -> Optional[str]:` → `def compute_content_hash(p: Path) -> Optional[str]:`. Body unchanged: `hashlib.sha256()`, the `while True` 64 KB chunk loop (`fh.read(65_536)`), `return h.hexdigest()`, `except OSError: return None`.
- **Repoint all three internal call sites** (all currently `_compute_content_hash(...)`):
  - `acquire_lock` — the `digest = _compute_content_hash(p)` call in the `for p in watched_paths:` loop.
  - `refresh_snapshot` — the `digest = _compute_content_hash(Path(p_str))` call in the snapshot-rebuild loop.
  - `check_drift` — the `current_hash = _compute_content_hash(p)` call in the per-tracked-path loop.
- **No backward-compat alias.** Do **not** add `_compute_content_hash = compute_content_hash`. Repo-wide grep (`grep -rn _compute_content_hash --include="*.py"`) returns only the four definition/call references in this module plus the five test references — all in-footprint. An alias would be unreferenced dead weight; an outright rename is correct precisely because no out-of-footprint caller exists.
- **Module topology unchanged.** `drift_detection.py` stays a stdlib + `plan_tool.style` leaf (imports `hashlib`, `os`, `sys`, `time`, `Path`, `tool`). Promotion changes visibility only — it adds no import edge. The downstream `from plan_tool.drift_detection import compute_content_hash` edge is introduced by the *consuming* step (step 3 in `completeness_report.py`), not here.
- **Foundational logic — streamed content hashing.** This step changes only the *name* of that logic, not its rule. The other in-repo location exercising the same streamed-SHA-256 rule is `plan_tool/review_persistence.py:compute_plan_fingerprint`, which carries an inlined copy of the loop (kept inline by step 1 to preserve the persistence leaf's import isolation). **Leave it inlined** — collapsing it onto the now-public `compute_content_hash` would force `review_persistence.py` to import `drift_detection`, breaking the leaf discipline the project intentionally maintains. Routed to [Deferred](#deferred) as a consolidation a future step owns, not this one.

### `tests/test_drift_detection.py`

- **Repoint the five characterization tests** under the `# ---------- _compute_content_hash (#31 helper) ----------` comment. Each currently does a body-local `from plan_tool.drift_detection import _compute_content_hash`; change the imported name to `compute_content_hash` and the call sites accordingly. **Assertions, payloads, and expected digests stay byte-identical.**
- **Update the section comment** to `# ---------- compute_content_hash (#31 helper) ----------` so the file's own marker matches the public name.
- The top-of-file `from plan_tool.drift_detection import (...)` block does **not** currently list `_compute_content_hash` (the five tests import it body-locally), so the shared import block needs no edit unless you choose to hoist the import — keep the body-local pattern to minimize the diff.

## Tests

All five are **existing** cases, repointed only (file: `tests/test_drift_detection.py`):

- `test_compute_content_hash_returns_sha256_hex` — known payload hashes to the standard `hashlib.sha256(...).hexdigest()`; pins the algorithm.
- `test_compute_content_hash_empty_file_has_empty_sha256` — zero-byte file yields the canonical empty-input SHA-256 (`e3b0c442…b855`).
- `test_compute_content_hash_returns_none_on_missing_file` — nonexistent path returns `None`, not a raise.
- `test_compute_content_hash_returns_none_on_directory` — a directory (raises `IsADirectoryError ⊂ OSError`) returns `None`.
- `test_compute_content_hash_handles_multi_chunk_file` — a >64 KB non-uniform payload hashes identically to a single-shot digest; pins chunked-read correctness.

### Test-creation order (refactor step)

- **Characterization tests already exist** — the five cases above are the characterization battery, written against the private name. For this refactor the "write first" work is a **mechanical repoint**, not authoring new behavior.
- **Order:**
  1. Repoint the five tests' imports/calls to `compute_content_hash` (assertions untouched), and run them — they should **fail to import** (`compute_content_hash` doesn't exist yet), confirming the tests bind to the new public name.
  2. Rename the definition + the three call sites in `plan_tool/drift_detection.py`.
  3. Re-run the five tests — they pass with **byte-identical assertions**.
- **Pass-unchanged gate:** the five tests' assertions/payloads/expected digests must be identical before and after the rename. A changed assertion would mean the "behavior-preserving" claim is false — back it out. Only the imported/called symbol name may differ.

## Acceptance criteria

- `from plan_tool.drift_detection import compute_content_hash` succeeds; `compute_content_hash(<file>)` returns the SHA-256 hex digest.
- `compute_content_hash` returns `None` for a missing path and for a directory (no raise).
- `_compute_content_hash` no longer exists on `plan_tool.drift_detection` (`grep -rn _compute_content_hash --include="*.py"` returns zero hits).
- No `_compute_content_hash = compute_content_hash` alias is present.
- `acquire_lock`, `refresh_snapshot`, and `check_drift` call `compute_content_hash`; their existing behavior tests in `tests/test_drift_detection.py` pass unchanged.
- The five repointed characterization tests pass with byte-identical assertions.
- `uv run pytest tests/test_drift_detection.py -q` is green; the full suite (`uv run pytest -m "not integration" tests/ -q`) shows no new failures.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — confirms the `sha256()` / `update()` / `hexdigest()` interface the promoted helper preserves verbatim.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.open("rb")` and the `IsADirectoryError ⊂ OSError` behavior the `None`-on-directory test pins.

## Deferred

- **Consolidating `review_persistence.py:compute_plan_fingerprint`'s inlined hash loop onto `compute_content_hash`** — intentionally NOT done. Importing `drift_detection` into the `review_persistence` leaf would break its import isolation (step 1 inlined the loop precisely to avoid this edge). A future cross-module-dependency decision owns any consolidation; route to reconcile, not this step's footprint.
- **Wiring the public `compute_content_hash` into `plan_tool/completeness_report.py`** — that import + the `compute_code_fingerprint` code-fingerprint compute land in step 3, the first consumer. This step only makes the symbol public.
- **A generic "diff two fingerprint maps" helper** — out of scope; deferred to the saved-vs-current diff in `resolve_reusable_audit` (step 5) and any later second consumer.
