# Step 1 — Make the shared history helpers in convergence_diagnosis public

## Summary

Rename the focus/matching and window/shrinkage helpers in `plan_tool/convergence_diagnosis.py` from leading-underscore names to public ones, and update every call site: inside the module, inside `plan_tool/telemetry_analysis.py` (which already reaches into the private names today), and in `tests/test_convergence_diagnosis.py`. No behavior changes — same functions, same signatures, same return values, new names. The key decision is to rename outright rather than add public wrappers or keep private aliases, so there is exactly one name per helper. On green, step 3's new `plan_tool/impact_recurrence.py` can import `normalized_focus`, `findings_match`, `windowed_open_counts`, and `no_shrinkage` as a supported API instead of reaching under the underscore.

## Table of Contents

- [Summary](#summary) — what this step does and what it leaves alone.
- [Why](#why) — why the private-name reach is a problem now.
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files edited, including one added to the step's footprint.
- [Implementation](#implementation) — which helpers become public, the names to use, and the call sites to sweep.
- [Tests](#tests) — the characterization tests to pin first and the import sweep afterwards.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the docs worth reading for this step.
- [Deferred](#deferred) — what stays private and why.

## Why

`plan_tool/convergence_diagnosis.py` is the one owner of region focus keys, cross-run finding matching, and the trailing-window / no-shrinkage trajectory rules. Two consumers already exist outside it. `plan_tool/telemetry_analysis.py` calls `convergence_diagnosis._step_token`, `._title_slug`, `._title_ratio`, `._normalized_focus`, and `._matches` directly — its own comments say matching is "wholly delegated to its tested matcher," yet every one of those calls goes through a private name. Step 3 of this plan adds a third consumer, `plan_tool/impact_recurrence.py`, which needs the same focus keys and the same shrinkage test to decide whether one high-impact region kept recurring. Promoting the helpers first makes that a normal import instead of a second private reach, and keeps the alternative — re-deriving focus/match/shrinkage rules inside the new module — off the table.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — rename the promoted helpers to public names; update every in-module caller (`_freeze_region`, `recurring_regions`, `_series_verdict`, `_region_spins`, `_region_step_focus`, and the render helpers that use them). Refresh the one-line docstrings and the section comments that name the old identifiers.
  - `plan_tool/telemetry_analysis.py` — **added to this step's footprint** (not in the plan's `files:` for step 1). Its ~8 `convergence_diagnosis._<name>(...)` call sites break the moment the names change, so they move in the same commit. Behavior there is untouched.
  - `tests/test_convergence_diagnosis.py` — update the module-level import block and the body-local imports to the new names.

## Implementation

**Promote these helpers, keeping signatures and bodies exactly as they are:**

- `_step_token` → `step_token`
- `_title_slug` → `title_slug`
- `_title_ratio` → `title_ratio`
- `_finding_step_focus` → `finding_step_focus`
- `_normalized_focus` → `normalized_focus`
- `_matches` → `findings_match` — the bare `_matches` reads as a generic predicate once it is public; `findings_match(candidate, representative)` says what it compares.
- `_window_start` → `window_start`
- `_windowed_open_counts` → `windowed_open_counts`
- `_recurs_in_window` → `recurs_in_window`
- `_no_shrinkage` → `no_shrinkage`

**Constraints that are not free to vary:**

- **Pure rename, no signature drift.** Argument names, order, keyword-vs-positional, and return types stay as they are at HEAD. `recurs_in_window(trend, window_start, recurrence_min)` keeps `recurrence_min` callable as a keyword — the existing tests pass it that way.
- **No aliases left behind.** Do not keep `_matches = findings_match`-style shims. Two names for one function is the duplication this step exists to remove, and a leftover private name invites the next consumer to use it. The absence of the old names is an acceptance criterion, not just successful use of the new ones.
- **`no_shrinkage` keeps its polarity.** It returns `True` when the region did *not* shrink (spinning). Renaming a negated predicate is the easy place to silently flip meaning; the characterization tests below pin both directions.
- **Public helpers stay in the same module and keep the same import graph.** `plan_tool/convergence_diagnosis.py` remains a leaf importing only `convergence`, `granularity`, `locator`, `review`, and `review_persistence` — no new imports, and nothing new imports it.
- **The module has no `__all__` today.** Don't add one as part of this step; it would be a second surface to keep in sync and is not needed for the imports step 3 makes.

**Recommended order of work:** write the characterization tests against the current private names first, run them green, then do the rename in one pass with the tests' import block updated in the same edit, then sweep `plan_tool/telemetry_analysis.py`. A grep for `convergence_diagnosis\._` plus `_matches(`, `_no_shrinkage(`, etc. across `plan_tool/` and `tests/` is the completeness check — one way is to finish with that grep returning only the helpers this step deliberately leaves private.

**Left private on purpose** (name them in the code comments so the boundary is visible): `_finding_from_recommendation` (step 2 extends it in place), `_region_spins` (it folds in the `closed` rule, which step 3's impact classifier does not want baked in — `RegionTrend.closed` is already a public field it can read), `_is_decline_close`, `_is_resolved_in_run`, `_max_severity_str`, `_freeze_region`, `_fingerprint_stable_streak`, `_series_verdict`, and the render helpers.

## Tests

All test cases live in `tests/test_convergence_diagnosis.py`.

### Test-creation order (refactor step)

This is a behavior-preserving refactor. Write these characterization tests **first**, against the current private names, and get them green before renaming anything. After the rename, the same assertions must still pass with only the imported names changed — no assertion edits.

Characterization tests to pin first (several already exist at HEAD and can be reused as-is; add the ones that are missing):

- `test_normalized_focus_prefers_finding_step_id` — a finding with `step_id=5` keys as `step5` (exists).
- `test_normalized_focus_parses_step_token_from_anchor` — anchor `step7-…` keys as `step7` (exists).
- `test_normalized_focus_falls_back_to_anchor_then_title` — anchor wins over title slug; a bare title slugifies (exists).
- `test_step_token_matches_hyphen_and_plain` — `step5-x` and `step-5-x` parse to 5; a non-prefixed anchor and `None` return `None` (exists).
- `test_no_shrinkage_flat_counts_spins` / `test_no_shrinkage_declining_counts_converges` — `(3,3,3)` and `(2,3,3,2)` are no-shrink; `(3,2,1)` shrinks (exist; these pin the polarity).
- `test_recurs_in_window_counts_only_trailing_runs` and its 3-run sibling — window arithmetic over series-local indices (exist).
- `test_no_shrinkage_ignores_absent_final_run` — `windowed_open_counts` reads the region's own sampled runs (exists).
- `title_ratio` / `title_slug` similarity check at `TITLE_SIMILARITY_CUTOFF` — the near-duplicate title pair still clears the cutoff (exists as a body-local import inside the tier-3 test).
- `test_findings_match_tier_precedence` — **add if absent**: two findings with equal step focus match; a step-focused finding and an anchor-only finding fall to the title tier; two equal non-step anchors match without a title compare.
- `test_finding_step_focus_prefers_step_id_over_anchor` — **add if absent**: `step_id` wins when both are set; the anchor token is used when `step_id` is `None`.

Import-surface tests to add after the rename:

- `test_shared_history_helpers_are_public` — importing each promoted name from `plan_tool.convergence_diagnosis` succeeds.
- `test_private_helper_aliases_are_gone` — `hasattr(convergence_diagnosis, "_matches")` and the other nine old names are all `False`.

Regression coverage for the swept consumer: `tests/test_telemetry_analysis.py` must stay green unmodified — in particular `test_async_anchor_reuses_step_token_matcher`, which exercises the delegated step-token match through `resolve_decision_async`.

## Acceptance criteria

- `plan_tool.convergence_diagnosis` exports all ten public helpers: `step_token`, `title_slug`, `title_ratio`, `finding_step_focus`, `normalized_focus`, `findings_match`, `window_start`, `windowed_open_counts`, `recurs_in_window`, `no_shrinkage`.
- None of the ten old underscore names remain as module attributes (no aliases, no wrappers).
- `grep -rn "convergence_diagnosis\._" plan_tool tests` returns no hits for the ten promoted helpers.
- `normalized_focus` returns `"step5"` for a finding with `step_id=5` and `"step7"` for one whose anchor is `step7-over-pack`.
- `no_shrinkage((3, 3, 3))` is `True`; `no_shrinkage((3, 2, 1))` is `False`.
- Every characterization test listed above passes both before and after the rename, with only its import names changed.
- `uv run pytest tests/test_convergence_diagnosis.py tests/test_telemetry_analysis.py tests/cli/test_telemetry_cmd.py -q` is green, and so is the full suite.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Confirms `frozen=True` semantics for `RunFinding` / `RegionTrend`, the records these helpers read.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Table-driven form for the focus-key and shrinkage characterization cases.

## Deferred

- **Adding `__all__` to `plan_tool/convergence_diagnosis.py`** — a second export surface to keep in sync; the public names alone are enough for step 3.
- **Promoting `_finding_from_recommendation`** — step 2 owns that function and extends it to carry impact; leave its visibility alone here.
- **Promoting `_region_spins`, `_fingerprint_stable_streak`, `_series_verdict`, and the render helpers** — they encode the offline spinning verdict, which step 3's impact classifier deliberately does not reuse.
- **Any change to what the helpers compute** — matching tiers, the title cutoff, window size, and the shrinkage rule are untouched by this step; changing them is separate work.
- **Rewriting `plan_tool/telemetry_analysis.py`'s local strict-match helpers (`_strict_finding_match`, `_origin_identity`) to use the newly public API differently** — this step only updates the names it calls; its matching policy stays as-is.
