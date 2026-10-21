> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Signature & verdict (M-of-N recurrence + no-shrinkage + four-state)

## Summary

This step adds the **decision layer** on top of step 2's region model: it reads each series' `RegionTrend` list, decides per series whether the audit/apply loop is **spinning** (a medium+ region recurs across a trailing M-of-N window without shrinking and is not closed) or **converging**, and rolls the per-series calls into one plan-level four-state headline. It edits only `plan_tool/convergence_diagnosis.py` and `tests/test_convergence_diagnosis.py` (the step declares no `files:`, so this is a minimal extension of the same pair steps 1–2 built). The key design decision: evaluate recurrence and no-shrinkage **over each region's own sampled runs inside the trailing window**, never over raw global endpoints, so a plan stuck on one over-packed step while resolving peripheral findings still reads `spinning`. On green, `diagnose_convergence(history)` returns a `ConvergenceDiagnosis` carrying the headline verdict, the per-series verdicts, and the regions that tripped — with **no** localized-vs-structural fork and **no** rendered string (those are step 4).

## Table of Contents

- [Why](#why) — what steps 1–2 leave undecided and why the verdict is its own step
- [Files (creates vs edits)](#files-creates-vs-edits) — the two-file set and the no-`files:` note
- [Implementation](#implementation) — the recurrence/no-shrinkage predicates, the four-state series verdict, the worst-of headline, and the result records
- [Tests](#tests) — unit cases for each signal, each verdict state, the converging paths, and the headline combine
- [Acceptance criteria](#acceptance-criteria) — checkable outputs of `diagnose_convergence`
- [References](#references) — datetime/difflib docs for this step's surfaces
- [Deferred](#deferred) — the fork, the render, the CLI, and the producer-change limits

## Why

Steps 1–2 land the reader (`load_report_history` → `ReportHistory`) and the per-region trend model (`build_region_trends` → `RegionTrend`), but neither one **calls** spinning vs. converging — step 2 explicitly "makes no verdict." The whole point of the command is that call: deciding when a region recurring at medium+ without shrinking means the audit/apply loop is patching *around* a mis-decomposition rather than closing it, and saying so with a four-state verdict that never mistakes "no data" or "still mid-authoring" for a reassuring "converging." This step is the one place that reads the already-scoped `RegionTrend` records and turns them into that verdict, leaving the *shape* of the failure (localized over-pack vs. structural) and the rendered recommendation to step 4.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add the verdict-state string constants and worst-of rank map, the `SeriesDiagnosis` and `ConvergenceDiagnosis` records, the recurrence/no-shrinkage/closed predicates over a trailing window, the per-series four-state verdict, the fingerprint-stable converging path, the worst-of headline combine, and the `diagnose_convergence` entry point. No new imports beyond stdlib (`datetime`/`difflib` already present from steps 1–2); reuses step 2's `build_region_trends`, `partition_series`, `series_key`, `RegionTrend`, and `_SEVERITY_RANK`.
  - `tests/test_convergence_diagnosis.py` — add the verdict unit classes (recurrence window, no-shrinkage, closed suppression, four states, converging paths a/b, worst-of headline) alongside steps 1–2's reader and region tests, driven off step 1's committed `tests/fixtures/convergence/sample-report-history.json` plus in-memory `RunSnapshot`/`RunFinding`/`RegionTrend` built in-test.

> **Files note.** Step 3 omits the `files:` key entirely (functionally an empty list). It edits the same two files steps 1, 2, and 4 touch (`plan_tool/convergence_diagnosis.py`, `tests/test_convergence_diagnosis.py`) and creates nothing new. No file outside that pair is touched.

## Implementation

### Cross-step input contract (depends_on: 2)

This step consumes step 2's model and step 1's reader. It reads these and nothing else; if an upstream step names a field differently, align there, not here:

- **`build_region_trends(history) -> dict[tuple, list[RegionTrend]]`** (step 2) — per-series-key region lists, already scoped to apply-eligible + medium+ and already carrying `closed`. This step **never re-filters** by source or severity — step 2 applied both floors once, by design.
- **`partition_series(history) -> dict[tuple, list[RunSnapshot]]`** (step 2) — the per-series snapshots, used here to get each series' run count and trailing fingerprints (including series that produced **no** regions, which `build_region_trends` drops).
- **`RegionTrend`** (step 2) — reads `run_indices`, `open_counts`, `closed`, `kind`, `step_id`, `focus`, `anchor`, `title`, `sources`, `max_severity`, `first_severity`, `last_severity`. `run_indices` are series-local; `open_counts` aligns with them.
- **`RunSnapshot`** (step 1) — reads `plan_fingerprint: str` (`""` = unset, matching `review_persistence.SavedReview.plan_fingerprint`) and `code_fingerprint` (path→hash dict; empty = not computed) for the fingerprint-stable converging path.
- **`ReportHistory`** (step 1) — reads `plan_slug` (from the reader's `slug_from_filename(path)`) for the diagnosis, and the ordered runs `build_region_trends`/`partition_series` consume. **Step-1/2 dependency:** if `plan_slug` is not exposed on `ReportHistory`, surface it there, not here — `render_diagnosis` (step 4) reads `diagnosis.plan_slug` and must not recompute it.

### `plan_tool/convergence_diagnosis.py` — symbols to add

- **Module constants**
  - `WINDOW_SIZE: int = 3` — the trailing window N and the floor for a path-(a) `spinning`/`converging` verdict. Default-only, a detector keyword, **not** an operator flag (no `--min-runs` in v1; see Deferred). Plumb it as a keyword on `diagnose_convergence` so tests can shrink the window without 3+ runs.
  - `RECURRENCE_TOLERANCE: int = 1` — the one-missed-run slack. The M of M-of-N is `recurrence_min = max(1, window - RECURRENCE_TOLERANCE)` (with the default N=3 → M=2: a region must appear in ≥2 of the trailing 3 runs to count as recurring). The tolerance is applied **uniformly** to every v1 series, with no per-`kind` gate: even a `completeness`-kind full audit is Claude-driven and non-deterministic, so a region's absence in a single run is not conclusive evidence it was resolved — the audit may have failed to re-surface it that pass, and tolerating one missed run keeps a flaky-absent run from masking a genuine spin (leaning toward `spinning` per the cautious-default principle). Stated as the rule, not claimed equivalent to `convergence.py`'s consecutive-stall semantics.
  - `VERDICT_NO_HISTORY = "no-history"`, `VERDICT_INSUFFICIENT_HISTORY = "insufficient-history"`, `VERDICT_CONVERGING = "converging"`, `VERDICT_SPINNING = "spinning"` — the four states, as string constants (step 4's render and step 5's CLI key on these; do not inline the literals downstream).
  - `_VERDICT_RANK: dict[str, int] = {VERDICT_NO_HISTORY: 0, VERDICT_INSUFFICIENT_HISTORY: 1, VERDICT_CONVERGING: 2, VERDICT_SPINNING: 3}` — the worst-of ordering `spinning > converging > insufficient-history > no-history`. The plan-level headline is the **max-rank** verdict across the per-series verdicts, so a `no`/sub-threshold kind can never mask a `spinning` kind.

- **`@dataclass(frozen=True) class SeriesDiagnosis`** — one record per series (one `kind`, or one `(kind, step_id)` for reconcile). Fields:
  - `key: tuple[str, ...]` — the step-2 `series_key` (e.g. `("completeness",)`, `("detail-reconcile", 5)`).
  - `kind: str` and `step_id: int | None` — for step 4's labels.
  - `verdict: str` — one of the four states for this series.
  - `run_count: int` — number of saved runs in the series (from `partition_series`).
  - `recurring: tuple[RegionTrend, ...]` — the regions that **tripped** (recur + no-shrinkage + not closed) inside the trailing window. Empty unless `verdict == VERDICT_SPINNING`. Carried so step 4 forks on these without re-walking; the render shows their run-count and `max_severity` / first→last trend.

- **`@dataclass(frozen=True) class ConvergenceDiagnosis`** — the step-3 output step 4 (`classify_fork`/`render_diagnosis`) and step 5 (CLI) consume. Fields:
  - `plan_slug: str` — from `history.plan_slug`.
  - `verdict: str` — the worst-of headline.
  - `window: int` — the N actually used (for the render's "… of the last N audits").
  - `series: tuple[SeriesDiagnosis, ...]` — every series' verdict, in `partition_series` order, so the render can print the headline followed by the per-kind breakdown.

- **`def _window_start(run_count: int, window: int) -> int`** — `max(0, run_count - window)`; the series-local index where the trailing window begins. All recurrence/no-shrinkage math is restricted to run indices `>= _window_start`.

- **`def _windowed_open_counts(trend: RegionTrend, window_start: int) -> tuple[int, ...]`** — the region's `open_counts` for only its sampled runs whose `run_indices` value is `>= window_start`, preserving order. This is the trajectory the no-shrinkage rule reads — the region's **own** sampled runs inside the window, never the global per-run count and never the two raw endpoints.

- **`def _recurs_in_window(trend: RegionTrend, window_start: int, recurrence_min: int) -> bool`** — `sum(1 for i in trend.run_indices if i >= window_start) >= recurrence_min`. The count of distinct sampled runs in the window meets M.

- **`def _no_shrinkage(counts: tuple[int, ...]) -> bool`** — the trajectory test over the windowed sampled counts:
  - Fewer than 2 entries → `True` (a single windowed sample shows no decline; such a region also fails M-of-N at the default N, so it never reaches `spinning` on its own).
  - The region **shrinks** when its latest windowed count fell below both its first windowed count and its windowed peak: `shrinks = counts[-1] < counts[0] and counts[-1] < max(counts)`. `_no_shrinkage = not shrinks`.
  - **Why over sampled runs, not raw endpoints:** a region absent from the final *global* run is excluded from `open_counts` entirely (step 2 samples appearances), so `counts[-1]` is always the last run the region actually appeared in — never a spurious `0`. This removes the endpoint pitfall the plan calls out ("a region absent from the final run misreads as shrinkage"). The `max(counts)` term keeps the test trajectory-aware rather than a bare endpoint compare. Plan motivation: `3,3,3` and `2,3,3,2` read no-shrink (spinning), `3,2,1` reads shrink (converging). The exact monotone threshold is this step's call within that intent; both flat-return sequences in the plan's `2,3,3,2` / `1,3,3,1` aside read no-shrink under this rule, and that is acceptable — the rule is conservative toward `spinning`, which the cautious-default principle wants.

- **`def _region_spins(trend: RegionTrend, window_start: int, recurrence_min: int) -> bool`** — `not trend.closed and _recurs_in_window(...) and _no_shrinkage(_windowed_open_counts(...))`. The closed check comes first: a region the operator deliberately skipped (step 2's sticky `closed`) never drives `spinning`, even if it recurs without shrinking.

- **`def _fingerprint_stable_streak(snapshots: list[RunSnapshot], trends: list[RegionTrend]) -> bool`** — the path-(b) converging certificate for a sub-threshold series:
  - Need ≥2 trailing snapshots. The trailing run(s) share an identical `plan_fingerprint` (skip the unset `""` sentinel — an all-`""` streak is **not** stable evidence), and an identical `code_fingerprint` among the trailing runs whose `code_fingerprint` is non-empty (truthiness, matching `review_persistence`'s `code_fingerprint_present` note; an all-empty `code_fingerprint` does not block the streak — plan fingerprint alone certifies).
  - **And** no region recurs across those trailing runs: no `trend.run_indices` covers ≥2 of the streak's indices (the plan/apply loop has stopped re-finding anything medium+). This is the "the plan stopped changing" evidence that separates converged-and-stable from genuinely-too-little-data.

- **`def _series_verdict(snapshots: list[RunSnapshot], trends: list[RegionTrend], window: int) -> SeriesDiagnosis`** — the per-series four-state call:
  - `run_count = len(snapshots)`; `window_start = _window_start(run_count, window)`; `recurrence_min = max(1, window - RECURRENCE_TOLERANCE)`.
  - `spinners = tuple(t for t in trends if _region_spins(t, window_start, recurrence_min))`.
  - **`spinning`** when `run_count >= window and spinners`. Carry `spinners` in `recurring`.
  - **`converging`** when either (a) `run_count >= window and not spinners`, **or** (b) `_fingerprint_stable_streak(snapshots, trends)`. Path (b) lets a genuinely converged plan certify `converging` with fewer than N runs — a hard ≥N floor would freeze the most-done plans at `insufficient-history` forever, since an unchanged-plan reuse persists no sidecar (`skip_sidecar_write`) and converged plans stop accruing history.
  - **`insufficient-history`** when `1 <= run_count < window` and not path (b) — sub-threshold and still churning, reported as "not enough data," never a reassuring `converging`.
  - **`no-history`** when `run_count == 0` (a series in `partition_series` always has ≥1 run, so this arises only for the whole-plan empty case below).

- **`def diagnose_convergence(history, *, window: int = WINDOW_SIZE) -> ConvergenceDiagnosis`** — the step-3 entry point:
  - Compute `partition_series(history)` (snapshots per series, including region-less series) and `build_region_trends(history)` (regions per series; missing key → `[]`).
  - For each series key in `partition_series` order, build a `SeriesDiagnosis` via `_series_verdict`.
  - **Whole-plan `no-history`:** when `partition_series` is empty (reports dir missing/empty per step 1), return `ConvergenceDiagnosis(plan_slug, VERDICT_NO_HISTORY, window, series=())`.
  - **Headline:** `max(series, key=lambda s: _VERDICT_RANK[s.verdict]).verdict` — the worst-of across kinds. Return `ConvergenceDiagnosis(plan_slug, headline, window, tuple(series))`.

### Foundational logic and where else it lives

- **The spin call (recur + no-shrinkage + not-closed over a trailing window)** is the step's core rule and lives **only** here — there is no parallel cross-run spin detector elsewhere. The nearest sibling is `plan_tool/convergence.py`'s **within-run** stall machinery (`should_continue`, `record_iteration`, `IterativeBudget.max_stall_rounds`), which reads live `ConvergenceState`, not on-disk report history. Reuse its severity primitive (`is_blocking`, already consumed in step 2's scoping) but **do not** route this cross-invocation decision through it — the two read different inputs (live in-memory state vs. saved sidecars) over different time horizons; no consolidation step is warranted.
- **Severity ordering** for any `max`/first/last display reuses step 2's `_SEVERITY_RANK` (the single source step 2 minted after grep confirmed no order constant in `review.py`/`convergence.py`). This step does not rank severity itself — it reads the already-computed `RegionTrend.max_severity`/`first_severity`/`last_severity` and passes them through on `recurring`.

### Acyclicity

No new cross-package edges. `convergence_diagnosis.py` stays a leaf below the CLI (no `plan_tool.cli` import); the verdict logic is pure over steps 1–2's records plus stdlib.

## Tests

All new cases land in `tests/test_convergence_diagnosis.py`, unit (unmarked), built off step 1's `tests/fixtures/convergence/sample-report-history.json` (the 3-run spinning series) plus in-test `RunSnapshot`/`RunFinding`/`RegionTrend` fixtures. Mutate the loaded payload in-memory for variants — do not author new fixture files.

- `test_recurs_in_window_counts_only_trailing_runs` — a region in runs 0,1 of a 5-run series does **not** recur in the trailing-3 window; one in runs 2,3,4 does.
- `test_recurrence_min_tolerates_one_missed_run` — at N=3, a region in 2 of the last 3 runs trips recurrence; a region in 1 of 3 does not.
- `test_no_shrinkage_flat_counts_spins` — windowed `open_counts (3,3,3)` and `(2,3,3,2)` read no-shrinkage.
- `test_no_shrinkage_declining_counts_converges` — `(3,2,1)` reads shrinkage (not no-shrinkage).
- `test_no_shrinkage_evaluates_region_not_global` — a region with flat own-counts trips `spinning` even though the global open-count trends down (a plan stuck on one step while resolving peripherals).
- `test_no_shrinkage_ignores_absent_final_run` — a region absent from the final global run (so its last sampled count is its real last appearance, not 0) does not fake shrinkage.
- `test_closed_region_never_spins` — a region with `closed=True` that recurs without shrinking yields no `spinning` driver.
- `test_series_spinning_requires_window_runs` — a 2-run series with a recurring region reads `insufficient-history`, not `spinning`; a 3-run one reads `spinning`.
- `test_series_converging_path_a_full_window_no_trip` — ≥N runs, no region trips → `converging`.
- `test_series_converging_path_b_fingerprint_stable_substhreshold` — 2 runs, identical non-empty `plan_fingerprint`, no recurring region → `converging` despite < N runs.
- `test_path_b_ignores_unset_plan_fingerprint` — two runs both with `plan_fingerprint=""` do **not** certify `converging` (stay `insufficient-history`).
- `test_path_b_code_fingerprint_optional` — empty `code_fingerprint` on the streak still certifies on plan fingerprint alone; differing non-empty `code_fingerprint` blocks the streak.
- `test_series_insufficient_history_substhreshold_churning` — 2 runs, differing `plan_fingerprint`, region not yet recurring → `insufficient-history`.
- `test_diagnose_no_history_empty_reports` — empty `partition_series` (no saved runs) → headline `no-history`, `series=()`.
- `test_headline_worst_of_spinning_beats_converging` — `completeness` series `converging` + `detail-reconcile` series `spinning` → headline `spinning`, both series present in `.series`.
- `test_headline_converging_outranks_insufficient` — a `converging` kind plus an `insufficient-history` kind → headline `converging`.
- `test_diagnosis_carries_spinning_regions_for_fork` — on the committed spinning fixture, the `spinning` `SeriesDiagnosis.recurring` is non-empty and carries the region's `focus`/`max_severity` (the input step 4 forks and renders on); `ConvergenceDiagnosis.plan_slug` matches the fixture slug.
- `test_diagnose_does_not_refilter_sources` — feeding trends already scoped by step 2, `diagnose_convergence` makes no source/severity exclusion of its own (a sub-`medium`/`plan-completeness` finding never reached the trend, and the verdict does not re-derive it).

### Test-creation order (feature step)

This is a **feature** step — new verdict behavior on steps 1–2's module. Add every test above **with** the implementation in the same change. Green-before-done gate: all new `tests/test_convergence_diagnosis.py` cases (plus steps 1–2's existing reader and region tests) must pass before this step is complete. Run the fast loop `uv run pytest tests/test_convergence_diagnosis.py -q` during development.

## Acceptance criteria

- `diagnose_convergence(history)` returns a `ConvergenceDiagnosis` with a four-state headline `verdict`, a `window` (default 3), a `plan_slug`, and a per-series `SeriesDiagnosis` tuple — making **no** localized-vs-structural fork and rendering **no** string.
- A series reads `spinning` only when it has ≥`window` runs **and** some region recurs in ≥`window - RECURRENCE_TOLERANCE` of the trailing-window runs, does not shrink over its own windowed sampled counts, and is not `closed`.
- A series reads `converging` when ≥`window` runs and nothing trips, **or** when its trailing runs are fingerprint-stable (identical non-empty `plan_fingerprint`, compatible `code_fingerprint`) with no region recurring — the latter even with fewer than `window` runs.
- A 1…`window-1`-run series that is neither fingerprint-stable nor recurring reads `insufficient-history`; an empty reports history reads `no-history`.
- The headline is the worst per-series verdict by `_VERDICT_RANK` (`spinning > converging > insufficient-history > no-history`); a sub-threshold kind never masks a `spinning` kind.
- No-shrinkage is evaluated over the region's own sampled runs inside the window, never the global per-run count and never two raw endpoints; a region absent from the final global run does not fake shrinkage.
- The `spinning` series' `recurring` regions carry the focus and severity trend step 4 needs; `diagnose_convergence` does no source/severity re-filtering.
- `convergence_diagnosis.py` imports no `plan_tool.cli` module and adds no import cycle.

## References

- [datetime — Basic date and time types (Python docs)](https://docs.python.org/3/library/datetime.html) — `created_at` ordering already lands in step 1's reader; relevant here only as the basis for the trailing-window indexing this step slices.
- [difflib — Helpers for computing deltas (Python docs)](https://docs.python.org/3/library/difflib.html) — `SequenceMatcher.ratio()` backs step 2's title tier; this step consumes the resulting `RegionTrend` and adds no new similarity logic.

## Deferred

- **Localized-vs-structural fork classification and `render_diagnosis` output** — step 4. The classifier (`classify_fork`) reads this step's `ConvergenceDiagnosis.series[*].recurring` (region `focus`/`sources`) and the renderer reads `plan_slug` + the four-state verdict; neither is built here. The `step<N>`-anchor-only localization caveat and the ambiguous→cautious-re-seed default also live in step 4.
- **`plan-tool convergence` CLI wiring** — step 5 (`load_report_history` → `diagnose_convergence` → `print(render_diagnosis(...))`, zero Claude, exits 0). No flags this step.
- **`--min-runs` exposing `WINDOW_SIZE`** — v1 ships no operator flag for N; it stays a detector keyword. Producer/plan `## Deferred`.
- **Closed-state inertness on iterate-only history** — step 2's `closed` only flips on history through an interactive `completeness-apply` walk; the mandated `--iterate`-only workflow persists empty annotations, so every region reads open and a deliberately-deferred region can still drive `spinning`. Persisting iterate disposition as annotations is the producer-change in the plan's `## Deferred`; this step's predicates honor `closed` correctly but cannot manufacture the signal.
- **`applied`-as-closed reconciliation** — step 2 deliberately diverges from the seed/schema-contract D2 (`applied` does **not** close, only a deliberate `skip` with `halt_reason == ""` does), because an `applied`-yet-reappearing finding *is* the spin signature. This step inherits that `closed` flag verbatim; no re-decision here.
- **Per-iteration sidecar persistence / surfacing the diagnosis inside the completeness report** — producer-side follow-ups in the plan's `## Deferred`; out of scope for the reader-only verdict.
