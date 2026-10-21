> **Auto-archived**: this plan was swept on 2026-06-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract the saved→current code-fingerprint map-diff into one shared `fingerprint.py` helper

## Summary

- **Add one pure helper** `diff_code_fingerprint(saved_fp, current_fp, repo_root) -> tuple[bool, list[Path]]` to `plan_tool/fingerprint.py`, encoding the deletion-aware `changed | deleted | new` map-diff that produces `(code_match, drifted_code)`.
- **Replace the two byte-identical inline diff blocks** in `plan_tool/completeness_report.py:resolve_reusable_audit` and `plan_tool/cli/reconcile.py:resolve_reusable_reconcile` with a call to the new helper. The `code_fingerprint_present` legacy gate and the `compute_code_fingerprint` call stay in each caller (they read the `SavedReview` marker and parse the plan — the helper stays pure and dict-only).
- **Load-bearing decision:** the helper operates on two `dict[str, str]` maps plus `repo_root`, **not** on a `SavedReview` — so `fingerprint.py` gains no import of `review_persistence`/`parser` and the import graph stays acyclic.
- **Behavior-preserving refactor.** On green, `resolve_reusable_audit` and `resolve_reusable_reconcile` return identical `code_match` / `drifted_code` for every input, and the existing `test_resolve_reusable_audit_*` + reconcile-engine characterization tests pass unmodified.

## Table of Contents

- [Why](#why) — the duplicated map-diff and what consolidating it buys
- [Files (creates vs edits)](#files-creates-vs-edits) — the new helper plus the two delegating call sites
- [Implementation](#implementation) — the helper signature, the two caller rewrites, the acyclic-graph constraint
- [Tests](#tests) — new helper unit cases + the unchanged caller characterization suite
- [Acceptance criteria](#acceptance-criteria) — observable post-refactor behaviors
- [References](#references) — hashlib/pathlib docs for the diff primitives
- [Deferred](#deferred) — the third copy in `review_cmd.py`, left out of footprint

## Why

- **The saved→current code-fingerprint map-diff is copy-pasted three times.** The exact `changed = {…} ; deleted = set(saved_fp) - set(current_fp) ; new = set(current_fp) - set(saved_fp) ; drifted_rel = changed | deleted | new ; code_match = not drifted_rel` block, followed by `drifted_code = sorted((root / rel).resolve() for rel in drifted_rel)`, appears verbatim in `plan_tool/completeness_report.py:resolve_reusable_audit` and `plan_tool/cli/reconcile.py:resolve_reusable_reconcile`, and as a near-copy in `plan_tool/cli/review_cmd.py`.
- **Drift between copies is a silent correctness risk.** The diff is deletion-aware on purpose (a hashed-then-vanished file is staleness across the save/reload boundary, unlike the live-edit `check_drift`). If one copy is touched and the others aren't, two audit families disagree on what counts as drift — invisible until a deleted-file or new-file case hits one path but not the other.
- **`fingerprint.py` already owns the producer** (`compute_code_fingerprint`) for exactly this reason — neither family imports the other to reach the code-side digest. The map-diff is the producer's natural sibling and belongs in the same leaf.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/fingerprint.py` — add the pure `diff_code_fingerprint` helper beside `compute_code_fingerprint`; no new import needed, `pathlib.Path` is already imported.
  - `plan_tool/completeness_report.py` — in `resolve_reusable_audit`, replace the inline `changed/deleted/new/drifted_rel/code_match` + `drifted_code` computation (the `--- Code verdict` block) with a `diff_code_fingerprint(...)` call; keep the `if not saved.code_fingerprint_present:` legacy gate and the `compute_code_fingerprint(plan, plan_path, repo_root)` call.
  - `plan_tool/cli/reconcile.py` — same replacement in `resolve_reusable_reconcile`'s `--- Code verdict` block.
  - `tests/test_fingerprint.py` — add unit cases for `diff_code_fingerprint`.

## Implementation

### `plan_tool/fingerprint.py`

- **Add** `diff_code_fingerprint(saved_fp: dict[str, str], current_fp: dict[str, str], repo_root: Path) -> tuple[bool, list[Path]]` immediately after `compute_code_fingerprint`.
- **Body** is the consolidated diff, moved verbatim from the callers:
  - `changed = {rel for rel, digest in saved_fp.items() if rel in current_fp and current_fp[rel] != digest}`
  - `deleted = set(saved_fp) - set(current_fp)`
  - `new = set(current_fp) - set(saved_fp)`
  - `drifted_rel = changed | deleted | new`
  - `root = repo_root.resolve()` then `drifted_code = sorted((root / rel).resolve() for rel in drifted_rel)`
  - `return (not drifted_rel, drifted_code)` — the `(code_match, drifted_code)` pair the callers assign.
- **Preserve the `changed` predicate exactly:** `rel in current_fp and current_fp[rel] != digest` (a key present in both with a differing digest). Do not simplify to a plain inequality over the union — that would misclassify deleted/new keys as "changed" and re-derive the wrong sets.
- **Keep it pure — dicts + `Path` only.** Do **not** take a `SavedReview`, parse the plan, or read the `code_fingerprint_present` marker here. Those are caller concerns: the present-marker decides *whether* to diff at all (legacy capture → stale, no baseline), and that gate stays in each resolver. Pulling `SavedReview` in would force `fingerprint.py` to import `plan_tool.review_persistence`, inverting the leaf's place in the graph (both `completeness_report` and `reconcile` sit *above* both `fingerprint` and `review_persistence`).
- **Docstring** states: deletion-aware (a saved key absent from current is drift); returns `code_match` (`True` iff no key drifted) and `drifted_code` (the `changed|deleted|new` keys resolved to absolute, sorted) so it aligns with the resolved-absolute keys `plan_tool.scope_guard.build_file_to_step_map` attributes against without re-resolving.

### `plan_tool/completeness_report.py`

- **In `resolve_reusable_audit`**, the `--- Code verdict (deletion-aware saved→current map diff)` block becomes:
  - legacy branch unchanged: `if not saved.code_fingerprint_present: code_match = False ; drifted_code: list[Path] = []`
  - else branch: `plan = parse_plan(plan_path)` ; `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` ; `code_match, drifted_code = diff_code_fingerprint(saved.code_fingerprint, current_code_fp, repo_root)`
- **Delete** the now-dead `root = repo_root.resolve()` line and the standalone `drifted_code = sorted(...)` line below the branch — the helper does both. The legacy branch must set `drifted_code = []` directly (previously it produced `[]` via `sorted(... for rel in set())`; the explicit empty list preserves that).
- **Import:** `compute_code_fingerprint` is already imported from `plan_tool.fingerprint`; extend that import to `from plan_tool.fingerprint import compute_code_fingerprint, diff_code_fingerprint`.
- **Untouched:** the plan-verdict block, the axis split (`correctness_recs`/`conceptual_recs`), and the `ReusableAudit(...)` construction — they consume `code_match`/`drifted_code` by the same names.

### `plan_tool/cli/reconcile.py`

- **In `resolve_reusable_reconcile`**, apply the identical replacement to its `--- Code verdict (deletion-aware saved→current map diff)` block, mapping its local `current_code_fp`/`saved_fp` names through the helper.
- **Delete** the trailing `root = repo_root.resolve()` + `drifted_code = sorted(...)` lines; the legacy branch sets `drifted_code = []`.
- **Import:** extend the existing `from plan_tool.fingerprint import compute_code_fingerprint` to also import `diff_code_fingerprint`.
- **Untouched:** the `_RECONCILE_KINDS` lookup, candidate filtering, `kind.accepted_kinds` gate, plan verdict, and the `ReusableReconcile(...)` construction.

### Shared-logic scan

- **Foundational logic:** the deletion-aware saved→current fingerprint set-diff that yields `(code_match, drifted_code)`.
- **Third call site:** `plan_tool/cli/review_cmd.py` (the plan-wide "review" reuse gate, the function whose comment reads *"mirroring `completeness_report.resolve_reusable_audit`'s changed|deleted|new diff"*) carries a near-copy. It differs structurally — wrapped in `try/except (ParseError, ValidationError, OSError)`, keyed on `ctx.repo_root`, and it reuses `drifted_rel` truthiness later to choose between `_note_reuse_code_drift` and the plan-stale `info(...)` line. It is **not** in this step's declared `files:` — see `## Deferred`. The new helper is shaped to accept it (`if not code_match and drifted_code:` is equivalent to its current `if not code_match and drifted_rel:`), so adopting it there is a one-block follow-up, not a redesign.

## Tests

### Test-creation order (refactor step)

This is a **behavior-preserving refactor.** Write/confirm the characterization tests FIRST, restructure second, and require those same tests to stay green **unmodified** afterward.

**Characterization tests that already exist and pin the callers' observable behavior (the pass-unchanged gate):**

- `tests/test_completeness_report.py::test_resolve_reusable_audit_fresh` — pins `fresh=True`, empty `drifted_code` when plan + code unchanged.
- `tests/test_completeness_report.py::test_resolve_reusable_audit_stale_by_code` — pins `code_match=False` and `drifted_code` populated on a byte-edit.
- `tests/test_completeness_report.py::test_resolve_reusable_audit_deleted_in_scope_file` — pins the deletion-aware branch (a hashed file removed → drift).
- `tests/test_completeness_report.py::test_resolve_reusable_audit_new_file_landed` — pins the `new` branch (a previously-absent file now on disk → drift).
- `tests/test_completeness_report.py::test_resolve_reusable_audit_legacy_sidecar_is_stale` — pins `code_match=False`, empty `drifted_code` when `code_fingerprint_present` is false (gate stays in caller).
- `tests/test_completeness_report.py::test_resolve_reusable_audit_computed_empty_code_fingerprint_reusable` — pins that a computed-but-empty map stays reusable on a plan match.
- `tests/cli/test_reconcile_engine.py` — the `resolve_reusable_reconcile` freshness/drift cases mirror the above for the reconcile family.

**New unit cases to add for the helper in `tests/test_fingerprint.py`:**

- `test_diff_code_fingerprint_identical_maps_match` — equal maps → `(True, [])`.
- `test_diff_code_fingerprint_changed_digest` — same key, differing digest → `code_match=False`, that file in `drifted_code`.
- `test_diff_code_fingerprint_deleted_key` — key in saved, absent from current → drift (deletion-aware).
- `test_diff_code_fingerprint_new_key` — key in current, absent from saved → drift.
- `test_diff_code_fingerprint_combined` — one changed + one deleted + one new → all three in `drifted_code`, sorted.
- `test_diff_code_fingerprint_drifted_code_is_absolute_resolved_sorted` — every returned path is absolute, under `repo_root.resolve()`, and the list is sorted.
- `test_diff_code_fingerprint_empty_maps_match` — `({}, {}, root)` → `(True, [])`.

## Acceptance criteria

- `plan_tool.fingerprint.diff_code_fingerprint` exists with signature `(saved_fp: dict[str, str], current_fp: dict[str, str], repo_root: Path) -> tuple[bool, list[Path]]`.
- `diff_code_fingerprint({"a": "h"}, {"a": "h"}, root)` returns `(True, [])`.
- `diff_code_fingerprint({"a": "h1"}, {"a": "h2"}, root)` returns `(False, [<root>/a])` with the path absolute and resolved.
- A deleted key and a new key each produce `code_match=False` and the corresponding absolute path in `drifted_code`.
- `resolve_reusable_audit` and `resolve_reusable_reconcile` no longer contain inline `set(saved_fp) - set(current…)` arithmetic (grep for `deleted = set(saved_fp)` returns only `fingerprint.py` and `cli/review_cmd.py`).
- `plan_tool/fingerprint.py` imports nothing from `plan_tool.review_persistence` or `plan_tool.parser` (the leaf stays acyclic).
- The full existing `test_resolve_reusable_audit_*` suite and the reconcile-engine reuse tests pass **unmodified**.
- `uv run pytest -m "not integration" tests/test_fingerprint.py tests/test_completeness_report.py tests/cli/test_reconcile_engine.py -q` is green.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 hexdigests the helper compares; confirms equal bytes ⟺ equal digest, so a digest inequality is genuine content drift.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `Path.resolve()` semantics for producing the absolute, symlink-resolved `drifted_code` keys that align with `build_file_to_step_map`.

## Deferred

- **`plan_tool/cli/review_cmd.py`'s third copy of the map-diff** — out of this step's declared `files:` and structurally different (try/except wrapper, `ctx.repo_root`, reuse of `drifted_rel` for branch selection between `_note_reuse_code_drift` and the plan-stale notice). Fold it onto `diff_code_fingerprint` in a follow-up that owns `review_cmd.py`; the helper is already shaped to serve it (`if not code_match and drifted_code:` replaces its `drifted_rel` check). Until that follow-up lands, this copy remains a **known divergence point** from the shared helper — the same "drift between copies is a silent correctness risk" this step cites still applies between `diff_code_fingerprint` and the untouched `review_cmd` block, so the residual risk is tracked here rather than implied resolved by this step.
- **Merging the three `resolve_reusable_*` resolvers into one kind-parametrized resolver** — a standing cross-module refactor noted elsewhere; this step consolidates only the shared map-diff primitive, not the resolver scaffolding.
