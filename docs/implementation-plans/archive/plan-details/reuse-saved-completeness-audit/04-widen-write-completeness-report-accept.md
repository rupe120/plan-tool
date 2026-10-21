> **Auto-archived**: this plan was swept on 2026-06-12 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Persist both correctness + completeness axes and both fingerprints from the completeness audit writer

## Summary

- Widen `plan_tool/completeness_report.py:write_completeness_report` with two new keyword params — `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None` — and thread both into the `save_review(...)` call so every persisted completeness sidecar carries the plan-side digest and the code-surface path→hash map alongside its recommendations.
- Change `plan_tool/cli/completeness_phases.py:_persist_and_present_report` to (a) compute both fingerprints at save time — `compute_plan_fingerprint(path)` (step 1, in `review_persistence.py`) and `compute_code_fingerprint(plan, path, ctx.repo_root)` (step 3, in `completeness_report.py`) — and (b) persist the **union** of both axes by passing `correctness_recs + conceptual_recs` as the sidecar recommendations (today only `conceptual_recs` is saved).
- **Load-bearing decision:** keep `write_completeness_report`'s existing `recommendations` param unchanged (axis-agnostic — each `Recommendation` already carries its `source`, `plan-correctness` vs `plan-completeness`, so the axis is recoverable on load). The caller assembles the union; the writer only gains the two fingerprint params. This keeps the three existing `recommendations`-based sidecar tests green and avoids a wider signature break.
- **Observable result on green:** a saved completeness sidecar loads with a non-empty `plan_fingerprint`, a populated `code_fingerprint` dict, and recommendations spanning both axes; omitting the fingerprint args still writes a legacy-shaped sidecar (`plan_fingerprint == ""`, `code_fingerprint == {}`).

## Table of Contents

- [Why](#why) — what reuse needs persisted at save time and why both axes + both fingerprints land together.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files, the in-footprint test, and one out-of-footprint test addition.
- [Implementation](#implementation) — the writer's two new params, the caller's fingerprint compute + union assembly, and import topology.
- [Tests](#tests) — fingerprint persistence, default-empty back-compat, both-axes union, and the caller-wiring spy.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — stdlib json / dataclasses for the widened sidecar payload.
- [Deferred](#deferred) — the reuse toggle, staleness comparison, and lookup helper left to later steps.

## Why

The "Reuse Saved Completeness Audit" feature decides whether a previously-saved audit is still valid by comparing the plan and code state captured at save time against current state — but the completeness sidecar written today captures neither fingerprint, and it persists only the `plan-completeness` (conceptual) subset, dropping every `plan-correctness` finding. Step 1 added the storage slots (`SavedReview.plan_fingerprint` / `code_fingerprint`) and `compute_plan_fingerprint`; step 3 added the `compute_code_fingerprint` producer. This step is the **populate** seam: it is the single production call site (`plan_tool/cli/completeness_phases.py:_persist_and_present_report` → `write_completeness_report` → `save_review`) where both fingerprints get computed and both recommendation axes get persisted. Without it, a later reuse/staleness step has nothing to look up — the sidecar exists but is fingerprint-blind and axis-incomplete.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — add `plan_fingerprint` + `code_fingerprint` params to `write_completeness_report`; forward both into the `save_review(...)` call; refresh the docstring.
  - `plan_tool/cli/completeness_phases.py` — in `_persist_and_present_report`: body-local import `compute_code_fingerprint` (from `completeness_report`) and `compute_plan_fingerprint` (from `review_persistence`); compute both; build `sidecar_recs` as the correctness+conceptual union; pass `plan_fingerprint=` / `code_fingerprint=` to `write_completeness_report`.
  - `tests/test_completeness_report.py` — add `write_completeness_report` fingerprint-persistence, default-empty, and both-axes cases (approx. 4 tests).
- **Existing files (edit beyond declared `files:`):**
  - `tests/cli/test_completeness_cmd.py` (addition) — add one `_persist_and_present_report` spy test asserting the caller computes both fingerprints and passes the union. Required because `_persist_and_present_report` tests live here (it patches the module-level `write_completeness_report`, the `OSError` precedent at `test_oserror_is_swallowed_returns_none`), not in `tests/test_completeness_report.py` — per the project convention that command-module behavior is exercised through the CLI test surface.
  - `tests/cli/test_completeness_cmd.py` (edit) — update the two pre-existing `TestPersistAndPresentReport` tests (`test_writes_report_and_returns_path`, `test_oserror_is_swallowed_returns_none`): their `SimpleNamespace(title="Demo Plan")` plan stubs have no `.steps`, so the new unconditional `compute_code_fingerprint(plan, …)` call (→ `scope_guard.compute_in_scope_paths`, which iterates `plan.steps`) raises `AttributeError` — not caught by `except OSError`. Fix both by passing a real `Plan` (or one with a `.steps` list) or monkeypatching `compute_plan_fingerprint` / `compute_code_fingerprint` to sentinels in those tests, so the suite stays green.

## Implementation

### `plan_tool/completeness_report.py` — `write_completeness_report`

- **Add two keyword-only params** after `recommendations`, before `plan_rel_path`:
  - `plan_fingerprint: str = ""` — the plan-side digest from `compute_plan_fingerprint`; `""` is the unset/legacy sentinel matching `SavedReview.plan_fingerprint`'s default.
  - `code_fingerprint: Optional[dict[str, str]] = None` — the opaque path→hash map from `compute_code_fingerprint`; `None` normalizes to `{}` (the `SavedReview.code_fingerprint` unset sentinel).
- **Forward both into the existing `save_review(...)` call** inside the `if recommendations is not None:` block (the sidecar-write branch). Add `plan_fingerprint=plan_fingerprint` and `code_fingerprint=code_fingerprint or {}` to the keyword args alongside the existing `plan_slug` / `plan_path` / `report_md` / `recommendations` / `kind="completeness"` / `now=ts_dt`. Step 1 widened `save_review` to accept both (defaulted), so this is a pure pass-through.
- **Leave the `recommendations` param and its `plan_rel_path`-required gate unchanged.** The fingerprints ride only on the sidecar write — when `recommendations is None` (markdown-only mode) no sidecar exists and the fingerprints are inert. This preserves `test_write_report_no_sidecar_when_no_recommendations`.
- **Design note (axis-agnostic writer):** the writer does **not** take separate `correctness_recs` / `conceptual_recs` params. The union is assembled by the caller and stored flat; `Recommendation.source` (`plan-correctness` / `plan-completeness`) is the discriminator a reuse consumer splits on at load time — mirroring how `_persist_and_present_report`'s `open_findings` derivation already filters on `r.source == "plan-correctness"`. Alternative (separate axis params on the writer) was rejected: it would break the three existing `recommendations=`-keyword tests for no behavioral gain, since the saved JSON shape is one flat list either way.
- **Refresh the docstring** of `write_completeness_report` to state that, when a sidecar is written, the plan and code fingerprints captured at save time are persisted so a later reuse check can compare them against current state. Drop no existing wording about the timestamped-filename accumulation.

### `plan_tool/cli/completeness_phases.py` — `_persist_and_present_report`

- **Extend the existing body-local import** from `plan_tool.completeness_report` (currently `build_report_md`, `console_summary`, `write_completeness_report`) to also import `compute_code_fingerprint`.
- **Add a body-local import** `from plan_tool.review_persistence import compute_plan_fingerprint` (step 1's helper lives in the persistence leaf, not in `completeness_report`).
- **Compute both fingerprints** before the `write_completeness_report` call, inside the existing `try:` that already guards the sidecar write against `OSError`:
  - `plan_fp = compute_plan_fingerprint(path)` — hashes the plan markdown + its `plan-details/<slug>/*.md` bundle.
  - `code_fp = compute_code_fingerprint(plan, path, ctx.repo_root)` — hashes the watched code surface (`scope_guard.compute_drift_watched_paths`), keyed repo-relative-posix, sorted.
- **Build the union** — replace `sidecar_recs = list(conceptual_recs)` with `sidecar_recs = list(correctness_recs) + list(conceptual_recs)` so both axes persist. The conceptual subset still leads with the `plan-completeness` findings `completeness-apply` walks; correctness findings now travel in the same sidecar for the reuse replay.
- **Pass the fingerprints** to `write_completeness_report` — add `plan_fingerprint=plan_fp` and `code_fingerprint=code_fp` to the existing call (which already passes `path`, `report_md`, `repo_root=ctx.repo_root`, `recommendations=sidecar_recs`, `plan_rel_path=plan_rel`).
- **Leave untouched:** the `plan_rel` computation (`path.resolve().relative_to(ctx.repo_root.resolve()).as_posix()` with the `ValueError` fallback), the `build_report_md(...)` call (it keeps receiving `correctness=correctness_recs` for the markdown body — unchanged), the `console_summary` / `render_markdown_for_console` presentation tail, and the `OSError` swallow that returns `None`.
- **Import-topology note:** `completeness_report` is an assembly module (already imports `review`/`review_persistence`, and after step 3 also `drift_detection`/`scope_guard`), so `compute_code_fingerprint` carries the heavy imports there; `_persist_and_present_report` only calls it. `compute_plan_fingerprint` stays in the `review_persistence` leaf (inline hash loop, no `drift_detection` edge). Both imports are body-local, matching the file's established "import next to use" posture for the persistence/report tail.

## Tests

### Test-creation order (feature step)

This is a **feature** step. Author each test alongside the implementation; every new test must be green before the step is done (green-before-done gate).

In `tests/test_completeness_report.py` (writer-level, fast, no CLI):

- `test_write_report_persists_plan_fingerprint` — call `write_completeness_report(..., recommendations=recs, plan_rel_path=..., plan_fingerprint="abc123")`; `load_review` on the sidecar → `saved.plan_fingerprint == "abc123"`.
- `test_write_report_persists_code_fingerprint` — pass `code_fingerprint={"plan_tool/x.py": "deadbeef"}`; loaded sidecar round-trips the exact dict.
- `test_write_report_fingerprints_default_empty` — omit both fingerprint args (pass only `recommendations` + `plan_rel_path`); loaded sidecar has `plan_fingerprint == ""` and `code_fingerprint == {}` (back-compat / legacy-sentinel shape).
- `test_write_report_persists_both_axes` — pass `recommendations` containing a `plan-correctness` rec and a `plan-completeness` rec (via `_rec("a", "plan-correctness")`, `_rec("b", "plan-completeness")`); loaded `saved.recommendations` preserves both ids and both `source` values — proves the writer stores a mixed-axis list verbatim.
- `test_write_report_none_code_fingerprint_stored_as_empty_dict` — pass `code_fingerprint=None` explicitly; loaded sidecar has `code_fingerprint == {}` (the `None`→`{}` normalization).

In `tests/cli/test_completeness_cmd.py` (caller wiring — patches module-level `write_completeness_report`):

- `test_persist_passes_union_and_fingerprints` — monkeypatch `plan_tool.completeness_report.write_completeness_report` with a recording spy; call `_persist_and_present_report(..., correctness_recs=[corr], conceptual_recs=[concept], ...)`; assert the spy's captured `recommendations` kwarg equals `[corr, concept]` (union, correctness first) and that `plan_fingerprint` / `code_fingerprint` kwargs are present and non-defaulted (monkeypatch `compute_plan_fingerprint` / `compute_code_fingerprint` on their domain modules to return sentinel values, then assert they flow through). Mirrors the existing `test_oserror_is_swallowed_returns_none` setup (same direct `_persist_and_present_report` call, same `SimpleNamespace` ctx/args), but with a plan stub carrying a `.steps` attribute (or monkeypatched fingerprint helpers) so `compute_code_fingerprint` does not raise.

Update the two pre-existing `TestPersistAndPresentReport` tests (`test_writes_report_and_returns_path`, `test_oserror_is_swallowed_returns_none`): their `SimpleNamespace(title="Demo Plan")` plan stub has no `.steps`, so the new unconditional `compute_code_fingerprint(plan, …)` call raises `AttributeError` (uncaught by `except OSError`). Give the plan stub a `.steps` list (or a real `Plan`), or monkeypatch `compute_plan_fingerprint` / `compute_code_fingerprint` to sentinels, so both stay green.

Existing tests that must stay green unchanged: `test_write_report_emits_json_sidecar_when_recommendations_given`, `test_write_report_requires_plan_rel_path_for_sidecar`, `test_write_report_no_sidecar_when_no_recommendations` — the `recommendations` param and its gate are untouched, so these need no repoint.

## Acceptance criteria

- `write_completeness_report` accepts `plan_fingerprint: str = ""` and `code_fingerprint: Optional[dict[str, str]] = None` keyword params and forwards both to `save_review`.
- A sidecar written with `plan_fingerprint="X"` / `code_fingerprint={"p": "h"}` loads (via `load_review`) with exactly those values.
- A sidecar written without the fingerprint args loads with `plan_fingerprint == ""` and `code_fingerprint == {}`.
- `code_fingerprint=None` persists as `{}` (not `None`) on the loaded `SavedReview`.
- `_persist_and_present_report` saves a sidecar whose `recommendations` is the concatenation `correctness_recs + conceptual_recs` (both `source` axes present), not the conceptual subset alone.
- `_persist_and_present_report` computes `compute_plan_fingerprint(path)` and `compute_code_fingerprint(plan, path, ctx.repo_root)` and passes both to the writer.
- The three pre-existing `recommendations`-sidecar tests in `tests/test_completeness_report.py` pass without modification.
- The two `TestPersistAndPresentReport` tests (`test_writes_report_and_returns_path`, `test_oserror_is_swallowed_returns_none`) are updated to give the plan stub a `.steps` attribute (real `Plan` or monkeypatched fingerprint helpers) so the unconditional `compute_code_fingerprint` call does not raise `AttributeError`, and both stay green.
- Full suite green: `uv run pytest tests/test_completeness_report.py tests/cli/test_completeness_cmd.py -q`.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — how the widened sidecar payload (now carrying both fingerprint keys plus the union recommendations list) serializes and deserializes through `save_review` / `load_review`.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — `SavedReview`'s defaulted `plan_fingerprint` / `code_fingerprint` fields (step 1) that this step populates; defaults are what make the omit-args path round-trip to the empty sentinels.

## Deferred

- The `--reuse-audit` / `--no-reuse-audit` toggle and `--reuse-audit-id` flag — plan-level argparse wiring, a later step.
- The staleness comparison itself (compare a loaded sidecar's `plan_fingerprint` / `code_fingerprint` against freshly recomputed values, warn on drift) — consumes what this step persists; not in scope here.
- The newest-sidecar lookup helper (locate the most recent `*-completeness.json` for a plan) — a later step reads the persisted fingerprints through it.
- Per-path code-drift attribution in the staleness warning (`scope_guard.build_file_to_step_map`, `drift_detection.render_attributed_path_line`) — rendering concern owned by the warning step, not the persistence step.
