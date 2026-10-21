> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `resolve_reusable_reconcile` — fingerprinted reconcile-sidecar reuse resolver

## Summary

- **Adds `resolve_reusable_reconcile(plan_name, repo_root, *, plan_path, review_id=None, kind_filter)`** to `plan_tool/cli/reconcile.py` — the reconcile-family analog of `plan_tool/completeness_report.py:resolve_reusable_audit`. It locates the newest (or `review_id`-pinned) saved reconcile sidecar for one kind, recomputes both fingerprints from current on-disk state, and returns a `ReusableReconcile` carrying the loaded `SavedReview`, a `fresh` verdict (plan **AND** code match), and a `drifted_code` list of absolute paths.
- **Primary file:** `plan_tool/cli/reconcile.py` (new `ReusableReconcile` dataclass + the resolver). **Test file:** `tests/cli/test_reconcile_engine.py`.
- **Load-bearing decision:** key sidecar selection off the existing `_RECONCILE_KINDS[kind_filter]` descriptor (`name_includes` / `name_excludes` / `accepted_kinds`) so the suffix-matching is single-sourced with the live `_find_saved_for_step` machinery — no second copy of the `-run-reconcile` / `-detail-reconcile` literal.
- **Load-bearing decision:** the saved→current code diff reports **changed | deleted | new** keys across the save/reload boundary (deletion is genuine staleness here, the opposite of the same-process live drift differ), and `drifted_code` entries are `(repo_root / rel).resolve()` absolute Paths so they align key-for-key with `plan_tool/scope_guard.py:build_file_to_step_map` for downstream attribution.
- **On green:** a fingerprinted reconcile sidecar with unchanged plan+code resolves `fresh=True, drifted_code=[]`; any edited/deleted/newly-landed in-scope code file yields `fresh=False` with the offending absolute path in `drifted_code`; a legacy sidecar (`code_fingerprint_present=False`) is never fresh.

## Table of Contents

- [Why](#why) — what the missing resolver blocks downstream
- [Files (creates vs edits)](#files-creates-vs-edits) — one production file, one test file
- [Implementation](#implementation) — the dataclass, the resolver, the descriptor reuse, the two-direction diff
- [Tests](#tests) — fresh/stale-by-plan/stale-by-code/deleted/new/pin/legacy cases
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author-with-implementation, green-before-done
- [Acceptance criteria](#acceptance-criteria) — observable verdict checks
- [References](#references) — fingerprint producers, persistence locators, the upstream template
- [Deferred](#deferred) — the reuse prompt/flag wiring and step-scoping

## Why

The reconcile-reuse feature needs a single producer that answers "is the newest saved reconcile sidecar for this kind still trustworthy?" before any consumer (a future `--reuse` flag, step 4+) can substitute saved findings for a fresh Claude reconcile. Step 2 now persists `plan_fingerprint` + `code_fingerprint` at all six reconcile save seams, so every freshly-written sidecar carries the two staleness axes — but nothing reads them back. The completeness family already has its reader (`plan_tool/completeness_report.py:resolve_reusable_audit`); the reconcile family has the stored data and no reader. This step adds that reader so reconcile sidecars become reusable on the same fingerprint-gated terms.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py`:
    - Add `ReusableReconcile` dataclass (alongside the existing `ReconcileKind` dataclass near the top of the saved-reconcile reuse section).
    - Add `resolve_reusable_reconcile(...)` near the `_find_saved_for_step` core (it shares that function's `_RECONCILE_KINDS` lookup and `list_saved_reviews` scan).
    - Add `from plan_tool.fingerprint import compute_code_fingerprint` at module top.
    - Add `compute_plan_fingerprint`, `list_saved_reviews`, and `SavedReview` to the existing `from plan_tool.review_persistence import (...)` block (currently importing `ReviewLoadError, load_review, save_review`); `list_saved_reviews` is currently imported only body-locally inside `_find_saved_for_step`, so the new resolver needs it at module top (or its own body-local import). `parse_plan` is already imported at module top; `SavedReview` is the loaded type returned by `load_review` and is named in the `ReusableReconcile.saved` annotation, so it must be imported.
  - `plan_tool/cli/app.py`:
    - Add `ReusableReconcile` and `resolve_reusable_reconcile` to the existing `from plan_tool.cli.reconcile import (...)` block (around `app.py:279`), so both symbols enter `app`'s globals and are re-exported through `cli/__init__.py`. The split-proof tests import `resolve_reusable_reconcile` from `plan_tool.cli`; without this block edit `from plan_tool.cli import resolve_reusable_reconcile` raises `ImportError` and every new test fails at collection.
  - `tests/cli/test_reconcile_engine.py`:
    - Add a `resolve_reusable_reconcile` test class with fresh/stale/drift fixtures, persisting fingerprinted sidecars via the existing `_seed_save` helper (extended to forward `plan_fingerprint` / `code_fingerprint`, or a sibling seeder).

## Implementation

### `plan_tool/cli/reconcile.py` — `ReusableReconcile` dataclass

- **Mirror the relevant subset of `completeness_report.py:ReusableAudit`** — drop the audit-only `correctness_recs` / `conceptual_recs` axis split (reconcile saves are single-axis):
  - `saved: SavedReview` — the loaded sidecar.
  - `fresh: bool` — `plan_match and code_match`.
  - `plan_match: bool` — saved plan fingerprint non-empty **and** equal to the recomputed current digest.
  - `code_match: bool` — `saved.code_fingerprint_present` **and** the saved→current code diff is empty.
  - `drifted_code: list[Path]` — absolute, resolved, sorted paths that changed | were deleted | newly landed.
- **Plain `@dataclass`** (not frozen) matching `ReusableAudit`'s shape; all fields data-typed (`str`/`bool`/`list[Path]`/`SavedReview`) so no `field(compare=False)` concerns.

### `plan_tool/cli/reconcile.py` — `resolve_reusable_reconcile`

- **Signature:** `def resolve_reusable_reconcile(plan_name: str, repo_root: Path, *, plan_path: Path, review_id: Optional[str] = None, kind_filter: str) -> Optional[ReusableReconcile]:`
  - `plan_name` is the `plan_slug` the persistence locators key on (`list_saved_reviews` / `resolve_saved_review` both take `plan_slug`) — the parameter is named `plan_name` per the step title but threads straight through as the slug.
  - `kind_filter` is a **required keyword** naming a key in `_RECONCILE_KINDS` (`"detail-reconcile"` or `"run-reconcile"`). Resolve `kind = _RECONCILE_KINDS[kind_filter]` once; reuse its `name_includes`, `name_excludes`, `accepted_kinds` — do **not** re-spell the `-run-reconcile` suffix.

- **Locate the candidate sidecar** (mirror `_find_saved_for_step` + `resolve_reusable_audit`'s locator):
  - Call `list_saved_reviews(plan_name, repo_root, plan_path=plan_path)` (newest-first, `.json` only).
  - Filter to entries where `kind.name_includes` is in `p.name` and none of `kind.name_excludes` is in `p.name` (`name_excludes=()` for both reconcile kinds today, so the exclude check is vacuous — mirror `_find_saved_for_step` for forward-proofing only).
  - **`review_id` pinning:** when `review_id` is set, match a candidate whose stem equals either the bare `<ts>` or the full `<ts>-<kind_filter>` form (e.g. `20260612-025825` or `20260612-025825-run-reconcile`); an unresolvable id returns `None`. When unset, take the newest filtered candidate.
  - `load_review(path)` the chosen candidate; confirm `saved.kind in kind.accepted_kinds` (guards a suffix collision). Return `None` if no candidate survives.

- **Recompute both fingerprints from current on-disk state** (asymmetric signatures — the plan side needs only `plan_path`, the code side needs the parsed `Plan` + `repo_root`):
  - `current_plan_fp = compute_plan_fingerprint(plan_path)` — from `plan_tool/review_persistence.py`.
  - `plan = parse_plan(plan_path)` then `current_code_fp = compute_code_fingerprint(plan, plan_path, repo_root)` — from `plan_tool/fingerprint.py`. `parse_plan` can raise `ParseError`/`ValidationError`; let those propagate (the caller resolves a real plan path) rather than swallowing — this resolver is not best-effort.

- **Plan match:** `plan_match = saved.plan_fingerprint != "" and saved.plan_fingerprint == current_plan_fp`. An empty saved digest (legacy sidecar) is never a match.

- **Code match + drift diff** (the deletion-significant, three-direction diff — distinct from `drift_detection.check_drift`):
  - Gate on `saved.code_fingerprint_present` — a legacy sidecar (`False`) forces `code_match = False`, `drifted_code = []`.
  - With `saved_fp = saved.code_fingerprint` and `current_code_fp`:
    - `changed = {rel for rel in saved_fp if rel in current_code_fp and saved_fp[rel] != current_code_fp[rel]}`
    - `deleted = set(saved_fp) - set(current_code_fp)`
    - `new = set(current_code_fp) - set(saved_fp)`
    - `drifted_rel = changed | deleted | new`
  - `code_match = not drifted_rel`.
  - `drifted_code = sorted((repo_root / rel).resolve() for rel in drifted_rel)` — absolute/resolved so the keys align with `build_file_to_step_map`'s `(repo_root / entry).resolve()` keys for downstream per-step attribution.

- **Return** `ReusableReconcile(saved=saved, fresh=plan_match and code_match, plan_match=plan_match, code_match=code_match, drifted_code=drifted_code)`.

### Foundational logic + shared locations

- **Core rule:** "find the newest kind-matching saved sidecar, recompute the two fingerprints, diff saved-vs-current both ways." The **identical rule already lives in `plan_tool/completeness_report.py:resolve_reusable_audit`** for the completeness kind — this step is the reconcile sibling, not a consolidation. The two differ on axis-split (audit splits correctness/conceptual; reconcile is single-axis) and on `kind_filter` parametrization, so they stay separate producers. A future "one fingerprint-reuse resolver parametrized over kind" merge is a refactor `detail` cannot mint — see Deferred.
- **The save/reload three-direction diff** is duplicated in spirit from `resolve_reusable_audit`'s `changed | deleted | new` block; reproduce it inline here rather than extracting a shared `diff_fingerprint_maps` helper (no second-consumer-justified home below both `cli/reconcile.py` and `completeness_report.py` yet) — Deferred.
- **⚠️ Plan-wide selection — a consumer MUST add step-scoping before substituting findings.** Unlike completeness (one plan-level audit), reconcile sidecars are **per-step** and carry `step_id` — the live reconcile machinery (`_find_saved_for_step`) filters `saved.step_id == step_id` for exactly this reason. This resolver deliberately omits `step_id` and picks the newest kind-matching sidecar plan-wide, matching `resolve_reusable_audit`'s scope. That means the returned `SavedReview` may belong to a different step than the one being reconciled. A future consumer (the step-4 reuse wiring) **must** filter to the current `step_id` before replaying these findings, or it will reuse wrong-step recommendations. Treat the absence of `step_id` here as a known gap the consumer closes, not a property safe to reuse as-is.

## Tests

All in `tests/cli/test_reconcile_engine.py`, imported from the `plan_tool.cli` package entry point per the split-proof convention. Drive `resolve_reusable_reconcile` directly with a real on-disk sidecar seeded through `save_review` (extend `_seed_save` to forward `plan_fingerprint` + `code_fingerprint`, mirroring `tests/test_completeness_report.py:_save_completeness_sidecar`). Seed a minimal plan + detail bundle + one in-scope code file under the resolved `repo` root.

- `test_resolve_reusable_reconcile_fresh` — unchanged plan+code ⇒ `fresh=True`, `plan_match=True`, `code_match=True`, `drifted_code == []`.
- `test_resolve_reusable_reconcile_stale_by_plan` — edit a detail-bundle file after save ⇒ `plan_match=False`, `fresh=False`, `drifted_code == []`.
- `test_resolve_reusable_reconcile_stale_by_code` — edit an in-scope code file ⇒ `code_match=False`, `fresh=False`, the file's absolute resolved path in `drifted_code`.
- `test_resolve_reusable_reconcile_deleted_in_scope_file` — delete a saved-fingerprinted code file ⇒ deleted path appears in `drifted_code`, `fresh=False`.
- `test_resolve_reusable_reconcile_new_file_landed` — a declared `creates:` file absent at save lands before resolve ⇒ new path in `drifted_code`, `fresh=False`.
- `test_resolve_reusable_reconcile_legacy_sidecar_is_stale` — sidecar with `code_fingerprint_present=False` ⇒ `code_match=False`, `fresh=False`, `drifted_code == []`.
- `test_resolve_reusable_reconcile_missing_returns_none` — no matching sidecar on disk ⇒ `None`.
- `test_resolve_reusable_reconcile_kind_filter_isolation` — a `detail-reconcile` sidecar present, `kind_filter="run-reconcile"` ⇒ `None` (and vice-versa); proves the descriptor's `name_includes`/`accepted_kinds` scope the scan.
- `test_resolve_reusable_reconcile_picks_newest` — two same-kind sidecars at different `created_at` ⇒ resolves the newer; co-located completeness/review sidecars ignored.
- `test_resolve_reusable_reconcile_pinned_by_id` — `review_id` matches both the bare `<ts>` and full `<ts>-run-reconcile` stems.
- `test_resolve_reusable_reconcile_pinned_id_missing_returns_none` — unresolvable `review_id` ⇒ `None`.
- `test_resolve_reusable_reconcile_docs_only_empty_code_fp_is_fresh` — `code_fingerprint={}` with `code_fingerprint_present=True` (no in-scope code surface) ⇒ `code_match=True`, `fresh=True`.

### Test-creation order (feature step)

This is a **feature** step — `resolve_reusable_reconcile` is net-new behavior. Author each test above **with** the implementation:

1. Add the `ReusableReconcile` dataclass + resolver skeleton; write `test_resolve_reusable_reconcile_fresh` and `_missing_returns_none` first to pin the happy/empty paths.
2. Add the plan/code recompute + diff; write the stale-by-plan, stale-by-code, deleted, new tests.
3. Add the `kind_filter` descriptor reuse + `review_id` pinning; write the isolation, newest, pin, and pin-missing tests.
4. Add the legacy + docs-only guards; write those two tests.

**Green-before-done gate:** every test above must pass (`uv run pytest tests/cli/test_reconcile_engine.py -q`) before the step is complete. Use a far-future `created_at` (the file's `FUTURE_TS` precedent) when wording/age determinism matters; assert content/stems, never sidecar file count, since same-second saves overwrite at an identical timestamp stem.

## Acceptance criteria

- `resolve_reusable_reconcile` exists in `plan_tool/cli/reconcile.py` with the exact signature `(plan_name, repo_root, *, plan_path, review_id=None, kind_filter)` and returns `Optional[ReusableReconcile]`.
- A fingerprinted same-kind sidecar with unchanged plan+code resolves `fresh=True`, `drifted_code == []`.
- Editing/deleting/adding any in-scope code file resolves `fresh=False` with the file's **absolute resolved** path in `drifted_code`.
- A sidecar of the other reconcile kind is invisible under a given `kind_filter` (returns `None`).
- A legacy sidecar (`code_fingerprint_present=False`) resolves `code_match=False, fresh=False`.
- `review_id` resolves against both the bare `<ts>` and full `<ts>-<kind>` stems; an unresolvable id returns `None`.
- All listed tests in `tests/cli/test_reconcile_engine.py` pass; the full suite stays green.

## References

- `docs/implementation-plans/2-reuse-saved-completeness-audit.md` (in-repo) — the template plan; `plan_tool/completeness_report.py:resolve_reusable_audit` + `ReusableAudit` is the direct structural model for this resolver.
- `plan_tool/review_persistence.py` (in-repo) — `compute_plan_fingerprint(plan_path)`, `list_saved_reviews(plan_slug, repo_root, *, plan_path)`, `resolve_saved_review`, `load_review`, and the `SavedReview` fields (`plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `kind`, `step_id`, `created_at`).
- `plan_tool/fingerprint.py` (in-repo) — `compute_code_fingerprint(plan, plan_path, repo_root)`; import the code-side producer from here, never from `completeness_report`.
- `plan_tool/scope_guard.py` (in-repo) — `build_file_to_step_map(plan, repo_root)` keys on `(repo_root / entry).resolve()`; the reason `drifted_code` must be absolute/resolved.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the SHA-256 backing both fingerprints.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — `resolve()` and repo-relative key handling for the diff.

## Deferred

- **The reuse prompt / `--reuse` flag wiring + drift warning** — this step only adds the resolver. Consuming the `fresh` verdict (substitute saved findings, warn on `drifted_code` via `_print_attributed_files`) belongs to a later step, mirroring `completeness_cmd.py:_resolve_audit_reuse` / `_warn_code_drift`.
- **Step-scoping the locator** — the signature carries no `step_id`; this resolver picks the newest kind-matching sidecar plan-wide, matching `resolve_reusable_audit`'s plan-level scope. Per-step sidecar selection (reconcile sidecars carry `step_id`) is out of scope until a consumer needs it.
- **A shared `diff_fingerprint_maps(saved, current)` helper** — the `changed | deleted | new` diff is reproduced inline here and in `resolve_reusable_audit`; extracting it is a consolidation refactor `detail` cannot mint, deferred until a common-home module below both call sites exists.
- **A kind-parametrized merge of `resolve_reusable_audit` and `resolve_reusable_reconcile`** — they diverge on axis-split and live in different import tiers; unifying them is a separate refactor step.
