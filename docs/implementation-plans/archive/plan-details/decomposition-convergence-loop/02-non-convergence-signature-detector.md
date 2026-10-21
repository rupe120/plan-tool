# Step 2 — Add non-convergence signature detector (recurrence + no-shrinkage → converging/spinning)

## Summary

- Adds the **detector** layer to `plan_tool/convergence_diagnosis.py`: a pure function `diagnose_convergence(history)` that reads the step-1 `ReportHistory` and returns a frozen `ConvergenceDiagnosis` carrying a `converging` / `spinning` verdict plus the recurring region(s) and the signals that fired.
- Keys on three deterministic, cross-run signals from the plan's Problem statement: **region recurrence** (same anchor slug or step id re-flagged unresolved across N consecutive runs), **no shrinkage** (open medium+ finding count fails to trend down across that window), and **monotone growth** (`report_bytes` grows run over run) as a corroborating proxy.
- Most important design decision: **reuse `plan_tool/convergence.py: is_blocking`** for the medium+ threshold (one source for "what counts as blocking"), and key recurrence on a single `_region_key` (anchor when present, else `step{N}`) so step 3's localized-vs-structural fork has a clean per-region record. No classification, no recommendation text, no CLI here — those are steps 3 and 4.
- Stays a leaf: only new `plan_tool` import is `plan_tool/convergence.py` (stdlib-only, acyclic). Spends zero Claude, writes nothing.
- On green: `diagnose_convergence(load_report_history(plan_path))` returns `verdict == "spinning"` for the committed 3-run spinning fixture and `verdict == "converging"` for a series whose recurring region's own open count trends down (or that has no recurring region) or whose history is shorter than the spin threshold.

## Table of Contents

- [Why](#why) — what the model from step 1 still can't tell you
- [Files (creates vs edits)](#files-creates-vs-edits) — edits to the two step-1 files only
- [Implementation](#implementation) — the result model, the three signals, the verdict rule, reuse decisions
- [Tests](#tests) — unit cases per signal + the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — stdlib docs for the surfaces this step touches
- [Deferred](#deferred) — fork classifier, recommendation renderer, CLI, verdict-reading left for later steps

## Why

- Step 1 built the normalized cross-run view (`ReportHistory` / `RunSnapshot` / `RunFinding`) but added **no detection** — it can list every run's open findings, but nothing yet decides whether the audit/apply loop is *converging* or *spinning*. That decision is exactly the missing pipeline signal: the loop edits prose forever and reports `converged` while re-finding the same boundary problem under a new anchor each pass.
- This step turns the model into a verdict. It implements the deterministic non-convergence signature the plan's Problem statement enumerates (recurrence + no-shrinkage + monotone-growth), keeping the result purely structural so step 3 can fork it (localized over-pack vs structural) and step 4 can print it. Everything stays read-only and Claude-free — it analyzes report JSON already on disk.

## Files (creates vs edits)

**New files:**
- None.

**Existing files (edits only):**
- `plan_tool/convergence_diagnosis.py` — add the detector on top of step 1's reader/model:
  - one new top-level import (`plan_tool/convergence.py: is_blocking`),
  - two module constants (`SPIN_MIN_RUNS` and `_BLOCKING_SEVERITY_ORDER`); the medium+ threshold is the imported `is_blocking`, not a constant,
  - two new frozen dataclasses (`RegionTrend`, `ConvergenceDiagnosis`),
  - the public `diagnose_convergence(history, *, min_runs=SPIN_MIN_RUNS)` function and its private helpers (`_region_key`, `_open_blocking_counts`, `_recurring_regions`, `_no_shrinkage`, `_monotone_growth`).
- `tests/test_convergence_diagnosis.py` — add the detector test cases (per-signal unit tests + the spinning/converging end-to-end over the fixture). Keep step 1's reader/model tests unchanged.

No new fixture file is needed: the committed `tests/fixtures/convergence/sample-report-history.json` is already a 3-run spinning series (step 1 authored it for this purpose); converging / short-history / shrinking variants are built inline by mutating loaded fixture payloads (mirroring step 1's inline construction of the non-`completeness` kinds).

## Implementation

### `plan_tool/convergence_diagnosis.py` (edits)

**New top-level import (acyclic — state why so a later reader doesn't body-localize it).**
- `from plan_tool.convergence import is_blocking`.
- `plan_tool/convergence.py` imports only stdlib (`time`, `dataclasses`, `typing`) and never imports this module — so this is a safe top-level import, same posture as step 1's `review_persistence` / `locator` imports. Do **not** lazy-import it.
- This is the medium+ threshold reuse step 1 explicitly deferred to step 2 ("the medium+ threshold … belongs to step 2's detector, not this model"). Do not re-declare a parallel severity set — `is_blocking(severity)` is the single source for "counts as blocking" (`medium` | `high` | `critical`).

**New module constant.**
- `SPIN_MIN_RUNS: int = 3` — the minimum number of trailing consecutive runs a region must be re-flagged (unresolved) before the detector will call the plan `spinning`. Matches the plan's Risks mitigation ("require N≥3 consecutive no-shrinkage runs") and the RUNBOOK rule of thumb. Exposed as the `min_runs` default so step 4's CLI can make it tunable without touching the detector.

**New frozen dataclasses (`@dataclass(frozen=True)`, matching the step-1 model posture).**

- `RegionTrend` — one recurring region's cross-run trend (the unit step 3 forks on):
  - `key: str` — the recurrence key (the anchor slug, or `step{N}` when the anchor is `None`). Stable across runs.
  - `anchor: Optional[str]` — the underlying anchor slug when the region was keyed on one, else `None`.
  - `step_id: Optional[int]` — the per-finding step id when present (the localized-vs-structural fork in step 3 reads this; a region with a non-`None` `step_id` and a quiet rest-of-plan is the localized over-pack signal).
  - `run_count: int` — length of the trailing consecutive streak of runs in which this region appears unresolved (the "4 of the last 4 audits" number).
  - `open_counts: tuple[int, ...]` — the region's **own** open medium+ finding count in each run of the streak, oldest→newest. The per-region trend the verdict gates on (distinct from the diagnosis-level global count).
  - `no_shrinkage: bool` — the region's own open count does not strictly decrease across its streak (`open_counts[-1] >= open_counts[0]`). True means this region is stuck on its own terms even if the rest of the plan's findings are resolving; the signal step 6's verdict reads.
  - `max_severity: str` — the highest severity this region carried across the streak, ranked by a module-local tuple `_BLOCKING_SEVERITY_ORDER = ("critical", "high", "medium")` (only blocking severities are ranked, so no need to import `plan_tool/review.py`'s private `_SEVERITY_BANNER_ORDER`); used for the diagnosis line in step 3.
  - `first_seen: str` / `last_seen: str` — the `created_at` of the oldest and newest run in the streak, for human-readable output.

- `ConvergenceDiagnosis` — the whole verdict for one plan:
  - `plan_slug: str` — copied from `ReportHistory.plan_slug`.
  - `verdict: str` — `"spinning"` or `"converging"`. Two values only (the plan's output examples show exactly these); a history too short to judge resolves to `"converging"` (not enough evidence to claim spinning), recorded honestly via `runs_examined`.
  - `regions: tuple[RegionTrend, ...]` — recurring regions whose `run_count >= min_runs`, sorted highest `run_count` first, then highest `max_severity`, then `key` (deterministic). Empty when nothing recurs.
  - `runs_examined: int` — `len(history.runs)`; lets a caller see when the verdict rests on too little history.
  - `no_shrinkage: bool` — the **global** open medium+ count failed to trend down across the trailing window (see below). Reported as a corroborating signal; the verdict gates on each `RegionTrend.no_shrinkage`, not this diagnosis-level total.
  - `monotone_growth: bool` — `report_bytes` is non-decreasing across the trailing window with at least one strict increase (the "patching, not resolving" proxy). Reported as a corroborating signal, **not** required for the verdict.

**The public detector — `diagnose_convergence`.**
- Signature: `def diagnose_convergence(history: ReportHistory, *, min_runs: int = SPIN_MIN_RUNS) -> ConvergenceDiagnosis:`.
- No `invoker`, no I/O — pure function over the in-memory model. The reader (`load_report_history`) already did all disk work.
- Steps:
  1. **Short-history guard.** If `len(history.runs) < min_runs`, return `ConvergenceDiagnosis(verdict="converging", regions=(), runs_examined=len(history.runs), no_shrinkage=False, monotone_growth=False)`. Cannot declare spinning without `min_runs` runs to compare — this is the mid-authoring false-positive mitigation from the plan's Risks.
  2. **Two reads of the run series** (`history.runs` is oldest→newest from step 1). Recurrence reads a **trailing consecutive streak anchored at the newest run** via `_recurring_regions(history.runs, min_runs)` — it walks all runs and `RegionTrend.run_count` is the full streak length, which may exceed `min_runs`. The shrinkage and growth signals (`_no_shrinkage`/`_monotone_growth`) read a **fixed trailing `min_runs` window** (`history.runs[-min_runs:]`).
  3. **Recurring regions.** Compute via `_recurring_regions(history.runs, min_runs)`. A region recurs when its `_region_key` appears among the **open medium+** findings of every run in a trailing consecutive streak of length `>= min_runs`. Build one `RegionTrend` per recurring key.
  4. **No shrinkage.** `no_shrinkage = _no_shrinkage(window)`.
  5. **Monotone growth.** `monotone_growth = _monotone_growth(window)`.
  6. **Verdict.** `verdict = "spinning" if any(r.no_shrinkage for r in regions) else "converging"`. Spinning requires a recurring region whose **own** open-count trend (`RegionTrend.no_shrinkage`) does not shrink — gate on the per-region trend, not the global total. This is the case the command exists to catch: a plan stuck on one over-packed step (its region re-flagged unresolved every run) while apply closes unrelated prose findings (global count trending down) must still resolve to `spinning`. The diagnosis-level global `no_shrinkage` and `monotone_growth` are recorded as corroborating signals but never gate the verdict.
  7. Return the assembled `ConvergenceDiagnosis`.

**Private helpers.**
- `_region_key(finding: RunFinding) -> Optional[str]` — `finding.anchor` when not `None`; else `f"step{finding.step_id}"` when `step_id` is not `None`; else `None` (an untrackable finding with neither anchor nor step id — excluded from recurrence, never synthesized). This mirrors step 1's "preserve the `None`, don't synthesize" rule for the underlying fields.
- `_open_blocking_findings(run: RunSnapshot) -> tuple[RunFinding, ...]` — `tuple(f for f in run.open_findings if is_blocking(f.severity))`. Reuses step 1's `open_findings` property (resolved already filtered) and layers the medium+ threshold. The single place the severity gate is applied — recurrence and shrinkage both read it.
- `_open_blocking_counts(window) -> tuple[int, ...]` — per-run count of `_open_blocking_findings`, in window order; the shrinkage signal's input.
- `_no_shrinkage(window) -> bool` — `True` when the **global** open medium+ count is no lower at the end of the window than at its start, i.e. `counts[-1] >= counts[0]`. This is a first-vs-last endpoint comparison, **not** the per-round stall rule in `plan_tool/convergence.py` (whose `no_progress` resets on any net reduction, so a window like `[3,2,3]` would read as progress there but as no-shrinkage here); do not claim equivalence in the comment — state the endpoint rule on its own terms. This feeds the corroborating diagnosis-level `no_shrinkage`; the same endpoint comparison is applied per region inside `_recurring_regions` to produce the `RegionTrend.no_shrinkage` the verdict gates on.
- `_monotone_growth(window) -> bool` — `report_bytes` non-decreasing across the window with at least one strict increase: `all(b <= n for b, n in pairs) and any(b < n for b, n in pairs)` over consecutive `(report_bytes)` pairs.
- `_recurring_regions(runs, min_runs) -> list[RegionTrend]` — for each region key, walk the runs newest→oldest counting the trailing consecutive streak in which the key is among that run's `_open_blocking_findings`; keep keys whose streak `>= min_runs`; build the `RegionTrend` (run_count = streak, max_severity ranked over the streak's findings, first/last_seen from the streak's runs). For `open_counts`, record the region's **own** count of `_open_blocking_findings` carrying that key in each streak run (oldest→newest); set `no_shrinkage = open_counts[-1] >= open_counts[0]` (the same first-vs-last endpoint comparison as the global `_no_shrinkage`, applied to this region's series). This is the per-region trend the verdict gates on — a region whose own count holds steady or grows while the plan's global count falls still reads as stuck.

**Foundational logic and where else it lives.**
- This step's core rule is **"a region re-flagged unresolved across ≥N consecutive runs with no open-count shrinkage means the loop is spinning."** The only existing sibling of this rule is the *within-run* stall logic in `plan_tool/convergence.py` (`should_continue` / `record_iteration` / `IterativeBudget.max_stall_rounds`), which counts non-shrinking rounds **inside one** `--iterate` invocation. This step deliberately implements the **cross-invocation** analogue over saved reports — a distinct concern (different time horizon, different data source) — and **reuses `convergence.py`'s severity primitive** (`is_blocking`) rather than re-deriving the threshold. No consolidation step is warranted: the two stall notions read different inputs (live `ConvergenceState` vs on-disk `ReportHistory`) and must stay separate. Note this reuse in the Implementation so a reviewer sees the threshold is single-sourced.
- The `granularity-split` source (`plan_tool/granularity.py: GRANULARITY_SPLIT_SOURCE`) is the plan's strongest localized over-pack signal, but **consuming it is step 3's classifier job**, not step 2's. Step 2 treats every medium+ open finding uniformly for recurrence regardless of `source`; do not special-case `granularity-split` here.

## Tests

Reference file: `tests/test_convergence_diagnosis.py`. Fixture: `tests/fixtures/convergence/sample-report-history.json` (committed by step 1; reused here).

- `test_spinning_series_yields_spinning_verdict` — the committed 3-run spinning fixture (same anchor re-flagged medium, unresolved, non-shrinking) → `verdict == "spinning"` with one `RegionTrend` whose `run_count == 3`.
- `test_converging_series_yields_converging_verdict` — a series built from the fixture where the recurring region's **own** open medium+ count strictly decreases run over run → `verdict == "converging"`, the region's `RegionTrend.no_shrinkage is False`.
- `test_stuck_region_spins_even_while_global_shrinks` — a series where one region stays re-flagged unresolved every run (its own count flat) while unrelated findings resolve so the **global** open medium+ count trends down → `verdict == "spinning"` with that region's `no_shrinkage is True`, even though diagnosis-level `no_shrinkage is False`. This pins the per-region gate.
- `test_short_history_is_converging` — a history with fewer than `SPIN_MIN_RUNS` runs → `verdict == "converging"`, `regions == ()`, `runs_examined` reflects the short count (no spinning on thin evidence).
- `test_recurrence_requires_consecutive_runs` — a region flagged in runs 1 and 3 but not 2 → not recurring (streak `< min_runs`), so not in `regions`.
- `test_resolved_region_not_recurring` — a region whose finding is `resolved` (annotation `status=="applied"`) in one window run breaks the streak → excluded from `regions`.
- `test_only_medium_plus_counts_for_recurrence` — a region carried only at `nit`/`info` severity across the window → `is_blocking` False → not recurring (proves the threshold gate).
- `test_no_shrinkage_true_when_count_not_decreasing` — open medium+ counts `[2,2,2]` → `_no_shrinkage`/`no_shrinkage is True`; `[3,2,1]` → `False`.
- `test_monotone_growth_reported_not_gating` — a window with strictly growing `report_bytes` but no recurring region whose own count holds (the recurring region's open count shrinks) → `monotone_growth is True` yet `verdict == "converging"` (growth corroborates, never decides).
- `test_region_keyed_on_step_id_when_anchor_none` — findings with `anchor=None` but a shared `step_id` recur and produce a `RegionTrend` with `key == "step{N}"`, `anchor is None`, `step_id == N`.
- `test_untrackable_finding_excluded` — a finding with both `anchor=None` and `step_id=None` re-flagged every run → never produces a `RegionTrend` (no synthesized key).
- `test_regions_sorted_by_run_count_then_severity` — two recurring regions with different streak lengths / severities sort highest `run_count` first, then highest `max_severity`.
- `test_diagnose_spends_no_io` — `diagnose_convergence` takes only a `ReportHistory` and constructs no invoker / reads no disk (guards the read-only, zero-Claude invariant).

### Test-creation order (feature step)

- This is a **feature** step. Write each test above **alongside** the symbol it covers — the helpers (`_region_key`, `_no_shrinkage`, `_monotone_growth`) and their unit cases first, then `_recurring_regions`, then the end-to-end `diagnose_convergence` verdict cases over the fixture.
- Green-before-done gate: every new test in `tests/test_convergence_diagnosis.py` (step 1's plus step 2's) must pass before this step is finished. Run `uv run pytest tests/test_convergence_diagnosis.py -q`.

## Acceptance criteria

- `diagnose_convergence(load_report_history(plan_path))` returns a `ConvergenceDiagnosis` with `verdict in {"spinning", "converging"}`.
- The committed 3-run spinning fixture yields `verdict == "spinning"` with exactly one `RegionTrend` (`run_count == 3`).
- A series whose recurring region's own open medium+ count strictly decreases run over run yields `verdict == "converging"`.
- A series where a region stays re-flagged unresolved every run (its own count non-shrinking) while the global open medium+ count trends down yields `verdict == "spinning"` — the verdict gates on the per-region trend, not the global total.
- A history shorter than `SPIN_MIN_RUNS` runs yields `verdict == "converging"`, `regions == ()`, and `runs_examined == len(history.runs)`.
- A region must appear unresolved in `SPIN_MIN_RUNS` trailing **consecutive** runs to count as recurring; a gap or a resolved annotation breaks the streak.
- Only `medium`/`high`/`critical` findings (`plan_tool/convergence.py: is_blocking`) drive recurrence and the shrinkage count; `nit`/`info` are ignored.
- `monotone_growth` is reported on the result but a `converging` verdict can carry `monotone_growth is True` (growth never flips the verdict alone).
- `diagnose_convergence` takes no `invoker`, performs no disk I/O, and writes no files.
- `plan_tool/convergence_diagnosis.py` still imports cleanly with no import cycle after the `plan_tool/convergence.py` import is added.

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for `RegionTrend` / `ConvergenceDiagnosis`, matching the step-1 model posture.
- [Built-in Functions — `sorted`, `all`, `any`, `max`](https://docs.python.org/3/library/functions.html) — the deterministic region sort and the all/any predicates behind the no-shrinkage and monotone-growth signals.

## Deferred

- **Localized-vs-structural fork classifier** (recurrence on a single `step_id` → localized over-pack; recurrence spanning multiple steps or inter-step shape → structural) — step 3. Step 2 emits `RegionTrend.step_id`/`anchor` so step 3 can fork; it makes no localized/structural decision.
- **Forked recommendation renderer** (the copy-paste `plan-tool split …` vs `create --from-existing … --iterate` text, and the ambiguous→cautious-re-seed rule) — step 3. Step 2 emits no recommendation strings.
- **Consuming `granularity-split` as the localized over-pack signal** — step 3's classifier reads `Recommendation.source`; step 2 treats all medium+ findings uniformly.
- **`plan-tool convergence <plan>` CLI seam and zero-Claude integration test** — step 4 (`plan_tool/cli/convergence_cmd.py`, parser registration, generated reference).
- **Structural `[BLOCKED]` verdict signal** — `AppliedOutcome.verdict` (`BLOCKED` / `BLOCKED-STRUCTURAL`) is not persisted to the report JSON (per step 1), so step 2 keys on recurrence + no-shrinkage instead. Parsing `report_md` for a blocked marker is a follow-up only if recurrence proves insufficient in practice.
- **Tuning `SPIN_MIN_RUNS` from the CLI** — exposed as the `min_runs` keyword default for step 4 to wire to a flag; step 2 hardcodes the default.
