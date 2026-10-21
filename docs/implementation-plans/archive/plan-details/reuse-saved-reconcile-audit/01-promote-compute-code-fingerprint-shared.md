> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Promote `compute_code_fingerprint` to a shared leaf (`plan_tool/fingerprint.py`)

## Summary

- **Moves** the code-side digest producer `compute_code_fingerprint(plan, plan_path, repo_root)` out of `plan_tool/completeness_report.py` into a new stdlib-plus-leaves module `plan_tool/fingerprint.py`, so the new reconcile family can compute the code fingerprint **without importing the heavyweight `completeness_report` assembly module**.
- **Re-exports** the symbol from `plan_tool/completeness_report.py` (top-level `from plan_tool.fingerprint import compute_code_fingerprint`), so `completeness_report.compute_code_fingerprint` and `resolve_reusable_audit`'s recompute call keep resolving unchanged.
- **Repoints** the one body-local importer, `plan_tool/cli/completeness_phases.py:_persist_and_present_report`, from `plan_tool.completeness_report` to `plan_tool.fingerprint`.
- **Load-bearing decision:** `fingerprint.py` imports only `drift_detection`/`scope_guard`/`schema` leaves — never `completeness_report` — keeping the import graph acyclic so both families share the producer with no edge between them.
- **On green:** the function behaves byte-identically; existing `completeness_report` callers and tests stay green via the re-export; new `tests/test_fingerprint.py` characterizes the producer at its new home.

**Already landed in the working tree.** `plan_tool/fingerprint.py` and `tests/test_fingerprint.py` exist as untracked files; `completeness_report.py` and `completeness_phases.py` are modified to match. Remaining work is verification + commit — see Why.

## Table of Contents

- [Why](#why) — what the move buys and the current landed state
- [Files (creates vs edits)](#files-creates-vs-edits) — the new leaf, the two repointed importers
- [Implementation](#implementation) — the move, the re-export, the repoint, acyclicity
- [Tests](#tests) — characterization set + the re-export pin
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — characterize first, prove inert after
- [Acceptance criteria](#acceptance-criteria) — observable green-state checks
- [References](#references) — stdlib hashing/path docs and the template plan
- [Deferred](#deferred) — what this step deliberately does not touch

## Why

The "Reuse Saved Reconcile Audit" plan needs the code-side digest producer to recompute a reconcile sidecar's freshness, exactly as the completeness reuse feature does. The producer currently lives in `plan_tool/completeness_report.py`, an **assembly module** that imports `plan_tool.review` and `plan_tool.review_persistence`. A reconcile-family consumer importing `compute_code_fingerprint` from there would drag in that whole subsystem and risk a cycle. Promoting the producer to a dependency leaf that imports only `drift_detection`/`scope_guard`/`schema` lets both families reach it cleanly. The move is **behavior-preserving** — the function body is unchanged; only its home and the import sites move. The work is already present in the working tree (untracked `fingerprint.py`/`test_fingerprint.py`, modified callers); what remains is confirming the suite is green at the new home and committing.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/fingerprint.py` — the shared leaf housing `compute_code_fingerprint`; imports `compute_content_hash` (from `plan_tool.drift_detection`), `Plan` (from `plan_tool.schema`), `compute_drift_watched_paths` (from `plan_tool.scope_guard`). No other production imports.
  - `tests/test_fingerprint.py` — characterization suite for the producer at its new home, plus the re-export identity test.

- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — replace the in-module `def compute_code_fingerprint` with a top-level `from plan_tool.fingerprint import compute_code_fingerprint` re-export; keep the explanatory comment block noting the producer now lives in the leaf and is re-exported so `resolve_reusable_audit` and existing callers keep working. The `resolve_reusable_audit` call site (`current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)`) is unchanged.
  - `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`, change the body-local `from plan_tool.completeness_report import compute_code_fingerprint` to `from plan_tool.fingerprint import compute_code_fingerprint`. The call (`code_fp = compute_code_fingerprint(plan, path, ctx.repo_root)`) is unchanged.

## Implementation

### `plan_tool/fingerprint.py` (new leaf)

- **Houses `compute_code_fingerprint(plan: Plan, plan_path: Path, repo_root: Path) -> dict[str, str]`** verbatim from `completeness_report.py` — the body that iterates `sorted(compute_drift_watched_paths(plan, plan_path, repo_root))`, digests each survivor via `compute_content_hash`, skips `None` (missing/unreadable declared `creates:`), and keys by `path.relative_to(repo_root.resolve()).as_posix()` in sorted order.
- **Imports only the three leaves:** `compute_content_hash` (`plan_tool.drift_detection`), `Plan` (`plan_tool.schema`), `compute_drift_watched_paths` (`plan_tool.scope_guard`). **Must not import `completeness_report`** — that edge is exactly what the move exists to break.
- **Module docstring states the leaf-preservation rationale:** both families digest the in-scope code surface; this module owns the producer so neither imports the other to reach it.

### `plan_tool/completeness_report.py` (re-export)

- **Replace the function definition with a top-level import** so the name still binds into the module namespace: `from plan_tool.fingerprint import compute_code_fingerprint`. This keeps `completeness_report.compute_code_fingerprint` a valid attribute (the re-export identity the test pins) and leaves `resolve_reusable_audit`'s recompute call working with no signature change.
- **Keep the comment** marking that the producer moved to the leaf and is re-exported here for `resolve_reusable_audit` and existing callers.
- **No call-site change.** `resolve_reusable_audit` still calls `compute_code_fingerprint(plan, plan_path, repo_root)` inside its code-verdict branch (gated on `saved.code_fingerprint_present`).

### `plan_tool/cli/completeness_phases.py` (repoint)

- **`_persist_and_present_report` is the single production write site** for a completeness sidecar; its body-local import block already pulls `compute_plan_fingerprint` from `review_persistence`. Change only the `compute_code_fingerprint` source line to `from plan_tool.fingerprint import compute_code_fingerprint`. Body-local placement and the call are unchanged — relocating the import target retargets nothing else.

### Acyclicity check

- **`scope_guard` / `drift_detection` / `schema` import neither `fingerprint` nor `completeness_report`**, so `fingerprint` → those three is a clean downward edge. `completeness_report` → `fingerprint` and `completeness_phases` → `fingerprint` are both downward into the new leaf. No cycle introduced.

## Tests

`tests/test_fingerprint.py` characterizes the producer at its new import home (`from plan_tool.fingerprint import compute_code_fingerprint`):

- `test_code_fingerprint_covers_declared_code_files` — every on-disk declared code path is a key mapped to its SHA-256.
- `test_code_fingerprint_excludes_plan_and_detail` — neither plan markdown nor detail files appear as keys.
- `test_code_fingerprint_skips_missing_declared_file` — a declared file absent from disk yields no key and does not raise.
- `test_code_fingerprint_keys_are_relative_posix` — every key is repo-relative posix (no absolute path, no backslash).
- `test_code_fingerprint_is_deterministic` — two calls on identical disk state return equal maps with identical key order (sorted).
- `test_code_fingerprint_changes_on_byte_edit` — mutating one watched file's bytes changes only that file's digest.
- `test_code_fingerprint_empty_when_no_code_files` — a plan declaring no code files returns `{}`.
- `test_code_fingerprint_reexported_from_completeness_report` — `completeness_report.compute_code_fingerprint is compute_code_fingerprint` (same object via the re-export).

Existing `tests/test_completeness_report.py` keeps its `compute_code_fingerprint` cases (imported from `plan_tool.completeness_report`, i.e. through the re-export) — these are the **pass-unchanged** characterization set proving the move is inert.

## Test-creation order (refactor step)

This is a **behavior-preserving** refactor — a move plus re-export. Characterization tests go first.

- **Write first (characterize the producer):** the seven behavioral cases above (`covers_declared_code_files`, `excludes_plan_and_detail`, `skips_missing_declared_file`, `keys_are_relative_posix`, `is_deterministic`, `changes_on_byte_edit`, `empty_when_no_code_files`). Each pins one observable contract of the digest map; together they fully describe the producer's output so the move can't silently alter it.
- **Then add the seam test:** `test_code_fingerprint_reexported_from_completeness_report` pins that the old import site still resolves to the same object — the one assertion the *move itself* must satisfy.
- **Pass-unchanged gate:** the existing `tests/test_completeness_report.py` `compute_code_fingerprint` cases (which import via the re-export) must stay **green and unmodified** after the move. If any needs an edit beyond the import source, the move was not behavior-preserving — stop and reconcile.

## Acceptance criteria

- `plan_tool/fingerprint.py` exists, defines `compute_code_fingerprint`, and imports no module other than `plan_tool.drift_detection`, `plan_tool.schema`, `plan_tool.scope_guard` (plus stdlib `pathlib`/`__future__`).
- `from plan_tool.fingerprint import compute_code_fingerprint` succeeds; `completeness_report.compute_code_fingerprint is plan_tool.fingerprint.compute_code_fingerprint` is `True`.
- `compute_code_fingerprint(plan, plan_path, repo_root)` returns a `{repo-relative-posix-path: sha256-hex}` map, sorted, omitting missing/unreadable declared files and excluding plan/detail markdown.
- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` imports `compute_code_fingerprint` from `plan_tool.fingerprint`.
- `uv run pytest tests/test_fingerprint.py tests/test_completeness_report.py -q` passes with the existing `completeness_report` cases unmodified.
- No import cycle: `python -c "import plan_tool.fingerprint"` succeeds and `plan_tool.completeness_report` is not in `fingerprint`'s import set.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the streamed SHA-256 that `compute_content_hash` (and thus this producer) computes per file.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `relative_to` / `resolve` / `as_posix` used to build the repo-relative, machine-independent keys.
- `plan_tool/scope_guard.py` (in-repo) — `compute_drift_watched_paths`, the exact code surface (step `files`/`creates` minus plan/detail) this producer digests.
- `plan_tool/drift_detection.py` (in-repo) — `compute_content_hash`, the per-file streamed digest with the missing-file-returns-`None` posture.
- `docs/implementation-plans/2-reuse-saved-completeness-audit.md` (in-repo) — the template plan whose `compute_code_fingerprint` producer this step relocates for reuse.

## Deferred

- **Recompute logic and freshness verdicts** (`resolve_reusable_audit`, saved→current map diff) — owned by the reconcile-family read/verdict step; this step only relocates the producer.
- **Reconcile-family consumer wiring** — the new family's import of `plan_tool.fingerprint` lands in its own step; here the leaf is merely made available.
- **Consolidating the live in-process snapshot** (`acquire_lock`'s absolute-keyed, deletion-ignoring map) with this persisted producer — deliberately kept separate by design; not in scope.
- **`compute_plan_fingerprint`** — stays in `plan_tool/review_persistence.py` (its inline-hash leaf home); only the *code*-side producer moves here.
