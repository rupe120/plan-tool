> **Auto-archived**: this plan was swept on 2026-06-14 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Persist both fingerprints at every reconcile save seam

## Summary

- **Threads `plan_fingerprint` + `code_fingerprint` into all six reconcile-family `save_review(...)` calls** so every saved reconcile sidecar (`*-detail-reconcile.json`, `*-run-reconcile.json`) carries the same two staleness axes the completeness sidecar already persists (step 3 of the completeness plan).
- **Primary files:** `plan_tool/cli/reconcile.py` (three saves: `_save_and_walk_reconcile`, `_save_and_walk_run_reconcile`, the `_iterate_reconcile_loop` per-iteration save), `plan_tool/cli/review_cmd.py:cmd_review` (the `reconcile-plan` save), `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` (the drift auto-reconcile save), and `plan_tool/cli/review_actions.py` (the walk sub-reconcile save inside `_build_review_action_fn`).
- **Load-bearing decision:** compute the two fingerprints **inline at each seam** — no shared two-fingerprint helper — because no single module can host one without violating the import topology (`auto_reconcile` sits below `cli`; `fingerprint.py`/`review_persistence.py` must stay leaves). Each seam parses the plan (or reuses an already-parsed `Plan` where one is in scope) and calls `compute_plan_fingerprint(plan_path)` + `compute_code_fingerprint(plan, plan_path, repo_root)` from step 1's `plan_tool/fingerprint.py`.
- **On green:** every reconcile-family sidecar written from any seam has a non-empty `plan_fingerprint` and `code_fingerprint_present == True`, keyed by the step's code files; legacy and `--no-save` behavior is unchanged.

## Table of Contents

- [Why](#why) — what the missing fingerprints block downstream
- [Files (creates vs edits)](#files-creates-vs-edits) — the four production files + two test files
- [Implementation](#implementation) — the six seams, the inline-compute decision, plan-availability per seam
- [Tests](#tests) — per-seam fingerprint-presence assertions
- [Test-creation order (feature step)](#test-creation-order-feature-step) — author-with-implementation, green-before-done
- [Acceptance criteria](#acceptance-criteria) — observable sidecar-content checks
- [References](#references) — fingerprint producers and the SavedReview persistence leaf
- [Deferred](#deferred) — the consolidated helper and the staleness consumer (step 5)

## Why

Step 1 promoted `compute_code_fingerprint` to the shared leaf `plan_tool/fingerprint.py` and step 1 of the completeness plan already added `plan_fingerprint`/`code_fingerprint`/`code_fingerprint_present` to `SavedReview` + `save_review`/`load_review`/`update_annotation`. Those fields exist but the **reconcile family never populates them** — every reconcile-family `save_review(...)` call omits both kwargs, so each reconcile sidecar writes the legacy-shaped record (`plan_fingerprint == ""`, `code_fingerprint_present == False`). The downstream reuse-staleness check (step 4/5: compare a saved reconcile's captured fingerprints against current plan/code state) has nothing to compare against until each save seam captures the two axes at write time. This step closes that gap at all six call sites so a fingerprinted reconcile sidecar is the new norm.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/reconcile.py` — add fingerprint computation at three `save_review(...)` calls: in `_save_and_walk_reconcile` (the `detail-reconcile`/kind-parametrized save), in `_save_and_walk_run_reconcile` (the `run-reconcile`/code-side save), and in `_iterate_reconcile_loop`'s per-iteration `detail-reconcile` save. Add `compute_plan_fingerprint` to the existing `from plan_tool.review_persistence import (...)` block and a new `from plan_tool.fingerprint import compute_code_fingerprint` at module top. `parse_plan` is already imported at module top.
  - `plan_tool/cli/review_cmd.py:cmd_review` — add fingerprint computation at the `reconcile-plan` `save_review(...)` call. Add `compute_plan_fingerprint` to the existing `from plan_tool.review_persistence import (...)` block, add `from plan_tool.fingerprint import compute_code_fingerprint`, and add `from plan_tool.parser import parse_plan` (not currently imported here; `ReviewResult` carries no `Plan`).
  - `plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift` — add fingerprint computation at the per-step `save_review(...)` call. Add lazy `from plan_tool.fingerprint import compute_code_fingerprint`, `from plan_tool.parser import parse_plan`, and `compute_plan_fingerprint` to the existing lazy `from plan_tool.review_persistence import save_review` line — keeping the module's lazy-import discipline (`run_auto_reconcile_on_drift`'s "Local imports keep the module's load-time graph clean" block).
  - `plan_tool/cli/review_actions.py` — add fingerprint computation at the `sub_saved_path = save_review(...)` call inside `_build_review_action_fn`'s `_dispatch_detail_reconcile` closure. `parse_plan` is already imported at module top; add `compute_plan_fingerprint` to the existing `from plan_tool.review_persistence import load_review, save_review` line and add `from plan_tool.fingerprint import compute_code_fingerprint`.
  - `tests/test_review.py` — new fingerprint-presence case under `TestCmdReviewSaveByDefault` (drives `main(["reconcile", "review-test"])`, inspects the saved JSON via `load_review`).
  - `tests/cli/test_reconcile_engine.py` — new cases driving `_save_and_walk_reconcile` and `_save_and_walk_run_reconcile` directly and asserting the saved sidecar carries both fingerprints.

  Beyond the declared `files:` list — genuinely required to cover two of the six seams:
  - `tests/test_auto_reconcile.py` — extend the existing `save_review` spy (`TestRunAutoReconcileOnDrift`, the `save_review=` injection fixture) to assert `plan_fingerprint`/`code_fingerprint` reach the call. The auto-reconcile seam lives in `auto_reconcile.py` (in scope), so its test home must move with it.

## Implementation

**Foundational logic (one phrase):** *at each reconcile `save_review` call, capture `plan_fingerprint = compute_plan_fingerprint(plan_path)` and `code_fingerprint = compute_code_fingerprint(plan, plan_path, repo_root)` and pass both as kwargs.* This same three-line shape is added at six call sites; it duplicates the per-site `plan_rel` `try/except` block those sites already carry.

**Why inline, not a shared helper (load-bearing):**
- A `(plan_fingerprint, code_fingerprint)` pair-producer would need both `compute_plan_fingerprint` (lives in `plan_tool/review_persistence.py`, the persistence leaf that must import only `plan_tool.review`) and `compute_code_fingerprint` (lives in `plan_tool/fingerprint.py`, the stdlib+`scope_guard`/`drift_detection`/`schema` leaf). No module can import both without coupling a leaf to the heavier subsystem.
- The four edited files span three import tiers: `auto_reconcile.py` is imported *by* `cli` modules (so it cannot import `cli.reconcile`), and `review_cmd.py` does not top-import `cli.reconcile`. There is no common host below all four.
- **Decision:** inline at each seam, matching the codebase's existing per-site duplication of the `plan_rel` resolution. Threading a parsed `Plan` through `_save_and_walk_reconcile`/`_save_and_walk_run_reconcile` signatures was the considered alternative — rejected for caller blast-radius versus a localized 3-line addition. A consolidated helper is routed to `## Deferred`.

**Per-seam plan availability** (`compute_plan_fingerprint(plan_path)` needs no `Plan`; `compute_code_fingerprint` needs the parsed `Plan` — see the asymmetric-signature lesson):

- **`plan_tool/cli/review_cmd.py:cmd_review`** — the `reconcile-plan` save inside the `if not result.dry_run and not args.no_save:` block. `ReviewResult` carries no `Plan` (only `report`/`recommendations`/`dry_run`), so parse fresh: `plan = parse_plan(path)`. Compute both, pass `plan_fingerprint=` / `code_fingerprint=` into the existing `save_review(plan_slug=args.name, ...)` call. The block is already guarded by `not args.dry_run` so the watched-code surface is real.

- **`plan_tool/cli/reconcile.py:_save_and_walk_reconcile`** — the `save_review(..., kind=kind, step_id=step_id)` after `extract_reconcile_recommendations`. No `Plan` in scope; `plan = parse_plan(plan_path)`. Compute and pass both. This seam serves the `detail --reconcile` path (and any future kind via the `kind=` param).

- **`plan_tool/cli/reconcile.py:_save_and_walk_run_reconcile`** — the `save_review(..., kind="run-reconcile", step_id=step_id)` after `extract_run_reconcile_recommendations`. Same shape: `plan = parse_plan(plan_path)`, compute, pass both. This is the run-reconcile / reconcile-code seam named in the step title.

- **`plan_tool/cli/reconcile.py:_iterate_reconcile_loop`** — the per-iteration `save_review(..., kind="detail-reconcile", step_id=step_id)`. **Reuse the already-parsed `scope_plan`** (`scope_plan = _parse_plan(plan_path)` near the loop top) for `compute_code_fingerprint(scope_plan, plan_path, ctx.repo_root)` rather than re-parsing per iteration — the loop edits plan/detail prose, but `compute_code_fingerprint`'s watched surface excludes plan/detail files (`compute_drift_watched_paths` subtracts them), so the structure `scope_plan` provides (step `files`/`creates` declarations) is stable across iterations. Call `compute_plan_fingerprint(plan_path)` fresh each iteration so the plan-side digest reflects the current detail-bundle bytes.

- **`plan_tool/auto_reconcile.py:run_auto_reconcile_on_drift`** — the `save_review(..., kind="detail-reconcile", step_id=step_id)` inside the `try/except OSError` per-step loop. No `Plan` in scope (`file_to_step` is pre-built, the `Plan` is not threaded in). **Wrap the parse + `compute_code_fingerprint` in best-effort handling** consistent with this function's "best-effort throughout" contract: on a parse failure, fall back to passing `code_fingerprint=None` (records "never computed") and `plan_fingerprint=""` rather than poisoning the drift halt. `compute_plan_fingerprint(plan_path)` is a pure file hash and won't raise. Keep all new imports lazy inside the function.

- **`plan_tool/cli/review_actions.py:_build_review_action_fn` → `_dispatch_detail_reconcile`** — the `sub_saved_path = save_review(..., kind="detail-reconcile", step_id=step_id)`. No `Plan` in scope; `plan = parse_plan(plan_path)` (`parse_plan` already imported at module top), compute, pass both. This is the walk sub-reconcile seam.

**Non-obvious points:**
- **`code_fingerprint=None` vs `code_fingerprint={}`** — pass the computed dict (even when empty) on success so `code_fingerprint_present == True`; pass `None` only on the auto-reconcile parse-failure fallback. An empty watched surface (`{}`, present) and an unset capture (`None`, absent) must stay distinguishable per `save_review`'s contract.
- **No re-parse where a `Plan` exists** — only `_iterate_reconcile_loop` already holds one (`scope_plan`); reuse it. The other five seams have no in-scope `Plan` and must `parse_plan(plan_path)`.
- **No `save_review` signature change** — step 1 of the completeness plan already added the kwargs (defaulting to `""`/`None`); this step only supplies them.

## Tests

`tests/test_review.py` (under `TestCmdReviewSaveByDefault`, mirroring `test_saved_file_round_trips`):
- `test_saved_review_carries_fingerprints` — after `main(["reconcile", "review-test"])`, `load_review(reviews[0])` has `plan_fingerprint != ""`, `code_fingerprint_present is True`, and `code_fingerprint` keys include `parser.py` / `renderer.py` (the fixture's step `files`).

`tests/cli/test_reconcile_engine.py` (import the seams from `plan_tool.cli`, drive with an `argparse.Namespace` + `PlanToolContext`, per the file's split-proof convention):
- `test_save_and_walk_reconcile_persists_fingerprints` — call `_save_and_walk_reconcile(args=..., ctx=..., plan_path=..., step_id=..., stdout=..., report=...)` with `--no-walk`; `load_review` the written `*-detail-reconcile.json` and assert both fingerprints present + keyed by the step's code file.
- `test_save_and_walk_run_reconcile_persists_fingerprints` — same for `_save_and_walk_run_reconcile`, asserting the `*-run-reconcile.json` sidecar carries both axes.

`tests/test_auto_reconcile.py` (extend the existing `save_review`-spy fixture):
- `test_auto_reconcile_save_includes_fingerprints` — spy captures the `save_review` kwargs; assert `plan_fingerprint` is a non-empty str and `code_fingerprint` is a dict for a step whose files exist on disk.
- `test_auto_reconcile_parse_failure_falls_back` — when `parse_plan` raises, the save still fires with `code_fingerprint=None` (drift halt not poisoned).

### Test-creation order (feature step)

- This is a **feature** step — new persisted data at six seams. Author each test **with** the seam edit it covers:
  1. `tests/test_review.py` → `cmd_review` reconcile-plan seam.
  2. `tests/cli/test_reconcile_engine.py` → `_save_and_walk_reconcile` + `_save_and_walk_run_reconcile` seams.
  3. `tests/test_auto_reconcile.py` → the auto-reconcile seam.
- The `_iterate_reconcile_loop` and `review_actions` sub-reconcile seams are covered transitively by their existing loop/walk tests once the kwargs are threaded; add a direct assertion only if an existing test already loads the saved sidecar.
- **Green-before-done gate:** every new test above must pass, and the full unmarked suite (`uv run pytest -m "not integration" tests/ -q`) plus `tests/test_review.py`/`tests/cli/test_reconcile_engine.py`/`tests/test_auto_reconcile.py` must stay green before this step is finished.

## Acceptance criteria

- A `reconcile-plan` save (`main(["reconcile", <plan>])`) writes a `.json` sidecar whose `load_review` yields `plan_fingerprint != ""` and `code_fingerprint_present is True`.
- A `detail --reconcile` save (`_save_and_walk_reconcile`) and a `run --reconcile` save (`_save_and_walk_run_reconcile`) each write a sidecar with both fingerprints populated, keyed by repo-relative posix paths of the step's `files`/`creates`.
- The auto-reconcile-on-drift save passes `plan_fingerprint` (non-empty) and a `code_fingerprint` dict (or `None` on parse failure) to `save_review`; a parse failure does not raise out of `run_auto_reconcile_on_drift`.
- `code_fingerprint` never contains the plan markdown or any per-step detail file (it is `compute_drift_watched_paths`, which excludes them).
- `--no-save` and `--dry-run` paths write no sidecar (unchanged); existing `TestCmdReviewSaveByDefault` cases stay green.
- `uv run pytest tests/test_review.py tests/cli/test_reconcile_engine.py tests/test_auto_reconcile.py -q` is green.

## References

- `plan_tool/fingerprint.py` (in-repo) — `compute_code_fingerprint(plan, plan_path, repo_root)`, step 1's shared leaf; import it from here, not from `completeness_report`.
- `plan_tool/review_persistence.py` (in-repo) — `compute_plan_fingerprint(plan_path)` and `save_review`'s `plan_fingerprint`/`code_fingerprint`/`code_fingerprint_present` kwargs (added by the completeness plan); the persistence leaf this step feeds.
- `plan_tool/scope_guard.py` (in-repo) — `compute_drift_watched_paths`, the code-minus-docs surface `compute_code_fingerprint` hashes; explains why plan/detail churn never enters `code_fingerprint`.
- `plan_tool/completeness_report.py:write_completeness_report` (in-repo) — the already-landed sibling that forwards both fingerprints into `save_review`; the pattern this step mirrors for the reconcile family.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — the streamed SHA-256 backing both fingerprint producers.

## Deferred

- **Consolidated two-fingerprint helper** — a single `(plan_fingerprint, code_fingerprint)` producer would de-duplicate the six inline blocks, but no module can host it without coupling a leaf (`review_persistence`/`fingerprint`) to the heavier subsystem or creating an upward edge from `auto_reconcile`. Route to a reconcile/refactor step once a non-leaf common home exists (e.g. after `compute_plan_fingerprint` itself relocates to `fingerprint.py`).
- **Staleness comparison / reuse gating** — reading these captured fingerprints back and comparing them to current plan/code state to decide reuse is step 4/5's job; this step only *persists* the axes.
- **`review_actions` sub-reconcile dedicated test** — covered transitively by the existing walk tests; a focused unit case is deferred unless the sub-reconcile save gains independent behavior.
- **Threading a parsed `Plan` through the save-seam signatures** — rejected here for caller blast-radius; revisit only if profiling shows the per-save `parse_plan` is a hotspot (it is not on the current single-step reconcile paths).
