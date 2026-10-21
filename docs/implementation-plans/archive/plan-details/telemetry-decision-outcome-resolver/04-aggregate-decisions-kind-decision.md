> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Aggregate decisions by kind and decision across plans and emit advisory tuning recommendations

## Summary

Adds the aggregation-and-recommend layer on top of step 3's per-event resolver, all inside the `plan_tool/telemetry_analysis.py` leaf. It groups every `ResolvedDecision` by the `(kind, decision)` pair across all plans, tallies the outcome distribution (`acted-on` / `no-op` / `reverted` / `still-open`) and the resolved-vs-unresolved split per group, and derives advisory **tuning recommendations** from that distribution — e.g. a signal that fires a lot but is mostly `no-op` reads as over-sensitive. The key decision: aggregation and recommendation are **pure functions over the resolved list** (no disk, no Claude, no mutation), with a thin `analyze_decisions(repo_root)` caller that wires the read — mirroring how step 3 kept the derivation pure and how `convergence_diagnosis.py` keeps its verdict pure over `ReportHistory`. On green, `analyze_decisions` returns a frozen `TelemetryAnalysis` (totals + per-group aggregates + recommendations), a `render_analysis` helper prints it as a text block, and the leaf still imports no `plan_tool.cli`.

## Table of Contents

- [Why](#why) — what the per-event resolver still can't answer and why aggregation lands now
- [Input](#input) — the `ResolvedDecision` contract step 3 produces that this step groups over
- [Files (creates vs edits)](#files-creates-vs-edits) — the one edited leaf and its test file
- [Implementation](#implementation) — the aggregate shape, the recommendation heuristics, the pure/caller split, and the render helper
- [Tests](#tests) — unit cases added with the code and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — stdlib/format docs relevant to this step
- [Deferred](#deferred) — the CLI command, `--json`, and the cache left for later steps

## Why

Steps 2–3 resolve **one decision at a time** into a verdict, but a single verdict is the anecdote BACKLOG #72 warns against tuning by. The mission payoff — *set a threshold from the distribution over scenarios and time, not from one session* — needs the decisions rolled up: how often does `code-reveals-split` fire, and across all those fires, how often did the split actually land vs get ignored vs get reverted? Nothing today turns the flat `list[ResolvedDecision]` into that per-signal picture, and without it the `plan-tool telemetry` command (step 5) would have nothing to print but a raw dump. This step lands the roll-up and the advisory recommendations so step 5 is thin wiring over a computed analysis, exactly as `cli/convergence_cmd.py` is thin over `convergence_diagnosis.py`.

## Input

This step consumes **step 3's resolver output** — it owns none of that shape, only groups over it.

- **`resolve_decisions(repo_root) -> list[ResolvedDecision]`** (`plan_tool/telemetry_analysis.py`, step 2 seam filled by step 3). Returns **one `ResolvedDecision` per event**, so the input length equals the decision-log line count.
- **The `ResolvedDecision` fields this step reads** (step 2 owns the dataclass): `kind`, `decision`, `plan_slug` — the grouping keys; `outcome` — one of `OUTCOME_ACTED_ON` / `OUTCOME_NO_OP` / `OUTCOME_REVERTED` / `OUTCOME_STILL_OPEN`; `resolution` — one of `RESOLUTION_INLINE` / `RESOLUTION_ASYNC` / `RESOLUTION_UNRESOLVED`.
- **The verdict and resolution constants** are already module-level names in the leaf (steps 2–3). Reuse them; do not re-type the literals.
- **Two contract facts that shape the grouping:**
  - **The `granularity` kind is overloaded across ≥4 decisions** (`assessed`, `code-reveals-split`, `create-review`, `create-step-outcome`). Group on the `(kind, decision)` pair, never `kind` alone, or four unrelated signals collapse into one bucket.
  - **The log carries an ownerless tail** — `plan_slug == ""` authoring rows and the `prompt-budget` family (the bulk of real events). These still get counted per `(kind, decision)`; they just don't contribute to a group's distinct-plan count. Aggregation must tolerate them, not skip or crash on them.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/telemetry_analysis.py` — add the `DecisionAggregate` and `TuningRecommendation` and `TelemetryAnalysis` frozen dataclasses; add the pure `aggregate_decisions` and `recommend_tuning` functions and the recommendation-threshold constants; add the thin `analyze_decisions(repo_root)` caller; add the `render_analysis` text helper.
  - `tests/test_telemetry_analysis.py` — add unit tests for grouping, the outcome/resolution tallies, the ownerless-tail tolerance, each recommendation heuristic and its min-sample guard, the render output, and the still-green leaf-boundary guard.

No new module and no new imports are needed — this step adds only pure computation over the resolver output already in the leaf.

## Implementation

**Foundational logic:** roll a flat `list[ResolvedDecision]` up into one aggregate per `(kind, decision)` group, then read tuning recommendations off each group's outcome distribution. Both are pure and deterministic. Grep confirms there is no existing per-signal roll-up of decisions to reuse or duplicate — this is net-new leaf computation.

**Add three frozen dataclasses** (mirror `convergence_diagnosis.py`'s frozen records — `SeriesDiagnosis`, `ConvergenceDiagnosis`, `ForkRecommendation`):

- **`DecisionAggregate`** — one per `(kind, decision)` group. Recommended fields: `kind: str`, `decision: str`, `total: int` (rows in the group), `plan_count: int` (distinct non-empty `plan_slug`), the four outcome counts (`acted_on` / `no_op` / `reverted` / `still_open`, or one `dict[str, int]` keyed on the `OUTCOME_*` constants), and the resolution split (`resolved: int` for `inline` + `async`, `unresolved: int`). The exact field layout is the implementer's; the constraint is that step 5 can read a per-signal count and outcome breakdown off it.
- **`TuningRecommendation`** — one advisory note. Recommended fields: `kind: str`, `decision: str`, `message: str` (the human-facing advisory line), and a short `category: str` slug (e.g. `over-sensitive` / `reverting` / `low-coverage`) so step 5 can group or filter them. Advisory only — no command, no severity that flips an exit code.
- **`TelemetryAnalysis`** — the top-level result step 5 renders and serializes. Recommended fields: `total_events: int`, `aggregates: tuple[DecisionAggregate, ...]`, `recommendations: tuple[TuningRecommendation, ...]`.

**Write `aggregate_decisions(resolved: list[ResolvedDecision]) -> list[DecisionAggregate]` as a pure function:**

- Group rows by the `(kind, decision)` tuple. One `DecisionAggregate` per distinct pair.
- **`plan_count` is the count of distinct non-empty `plan_slug` values** in the group — a `plan_slug == ""` row bumps `total` but not `plan_count`. This is what keeps the ownerless tail counted-but-not-attributed.
- **Tally every row's `outcome` into the four buckets** using the `OUTCOME_*` constants as keys. Every `ResolvedDecision` carries an outcome (an unresolved row carries `still-open`), so the four counts sum to `total`.
- **Tally the resolution split**: `resolved` = rows whose `resolution` is `inline` or `async`; `unresolved` = the rest. This is the denominator the recommender needs — a `still-open` outcome on an *unresolved* row means "nothing joined yet," not "the signal fired and led nowhere," and the two must not be conflated.
- **Sort the returned list deterministically** by `(kind, decision)`. No clock, no randomness — the output must be stable for the same input (the tool forbids `Date.now()`/random in this subsystem's spirit, and a stable order keeps step 5's tests and any `--json` diff clean).
- **Empty input returns `[]`.**

**Write `recommend_tuning(aggregates: list[DecisionAggregate]) -> list[TuningRecommendation]` as a pure function over the aggregates.** State the heuristics; the exact thresholds are the implementer's to tune, but name them as module constants so they aren't inlined magic numbers:

- **Guard on sample size first.** Define `MIN_SAMPLE_FOR_RECOMMENDATION` (recommend ~10). A group with fewer *resolved* rows than that yields no tuning recommendation — the mirror of `convergence_diagnosis.py`'s `VERDICT_INSUFFICIENT_HISTORY` refusal to call a verdict on thin data. Say so in the message only if you emit a low-coverage note (below).
- **Over-sensitive signal.** A group with enough resolved rows where the `no_op` share is high (define `HIGH_NO_OP_RATE`, ~0.6) reads as firing on cases not worth acting on → recommend reviewing the threshold to fire less. Category `over-sensitive`.
- **Reverting signal.** A group where the `reverted` share crosses a low bar (define `REVERTED_RATE_FLAG`, ~0.2) reads as leading to actions that get undone → recommend the threshold is too aggressive. Category `reverting`. `reverted` can only come from the async source (step 3), so this heuristic keys on real join evidence.
- **Low join coverage.** A group with many rows but a high `unresolved` share (define `LOW_COVERAGE_RATE`, ~0.7) can't be tuned yet — flag it as *not enough correlated outcomes to assess*, so an operator knows the silence is missing data, not a clean signal. Category `low-coverage`. This is honest reporting, not a tuning nudge.
- **Well-calibrated → no recommendation.** A group that is mostly `acted-on` needs no note. Silence here is correct — do not emit a "looks fine" line per group or the output drowns.
- **Advisory only — never mutate.** `recommend_tuning` returns text records and nothing else. It must not touch a threshold, a plan, or a config. This is the plan's hard rule (design decision #3 / Out of scope).

**Write `analyze_decisions(repo_root: Path) -> TelemetryAnalysis` as the thin caller:**

- Call `resolve_decisions(repo_root)`, pass the list to `aggregate_decisions`, pass the aggregates to `recommend_tuning`, and assemble `TelemetryAnalysis(total_events=len(resolved), aggregates=..., recommendations=...)`.
- This is the only function here that reaches disk (indirectly, through the step 3 reader). Keeping the read in one place and the roll-up pure is the same testability split step 3 used for `resolve_decision_async` — every aggregation and recommendation test hands in a built list of `ResolvedDecision`, no filesystem, no Claude.
- An empty/absent log flows through as `total_events == 0`, `aggregates == ()`, `recommendations == ()` (inherited free from `resolve_decisions` returning `[]`).

**Write `render_analysis(analysis: TelemetryAnalysis) -> str`** — the printable block step 5 emits with one `print(...)`, mirroring `convergence_diagnosis.py:render_diagnosis`:

- A headline with the total event count, then one line per `DecisionAggregate` (the `kind/decision`, its total, plan count, and outcome breakdown), then the recommendations. An empty analysis prints a plain "no telemetry recorded yet" line rather than an empty string.
- Keep it pure text off the frozen object — never recompute anything, never re-read disk. Step 5 owns the `--json` path (serialize the same `TelemetryAnalysis`) and the CLI wiring; this render is the text form only.

**Constraints and gotchas that are not free to vary:**

- **Group on `(kind, decision)`, never `kind` alone** — the `granularity` overload makes kind-only grouping wrong.
- **Stay total — never raise.** Read fields off `ResolvedDecision` directly (they're typed), but a surprise value must degrade, not crash: an unrecognized `outcome` or `resolution` string should fall into a safe bucket (count it in `total`, skip it from the four/two known buckets) rather than throw, matching the "unknown enum → safe default, never drop" rule this subsystem already follows.
- **Determinism.** Stable sort order for both aggregates and recommendations; no clock or randomness. Two runs over the same log produce identical output, byte for byte — required for step 5's `--json` to be diffable and for the tests to pin order.
- **Leaf boundary holds.** This step adds no imports; the existing `test_telemetry_analysis_does_not_import_cli` guard must stay green. `plan_tool.cli` stays forbidden.
- **Frozen dataclasses** for all three new records (`@dataclass(frozen=True)`), like every record in this leaf and in `convergence_diagnosis.py`.

## Tests

All in `tests/test_telemetry_analysis.py` (extend steps 2–3's file). Build `ResolvedDecision` values directly and hand them to the pure functions — no disk, no Claude. Approx 14–16 unit tests.

**Aggregation (`aggregate_decisions`):**
- `test_aggregate_groups_by_kind_and_decision` — two `granularity` rows with different `decision` land in two separate aggregates.
- `test_aggregate_same_kind_decision_merges` — rows sharing `(kind, decision)` roll into one aggregate with summed `total`.
- `test_aggregate_counts_outcomes` — the four outcome buckets tally `acted-on` / `no-op` / `reverted` / `still-open` and sum to `total`.
- `test_aggregate_resolution_split` — `inline` + `async` rows count as `resolved`; `unresolved` rows count separately.
- `test_aggregate_plan_count_distinct_slugs` — `plan_count` equals the number of distinct non-empty `plan_slug` values.
- `test_aggregate_empty_slug_counted_not_in_plan_count` — a `plan_slug == ""` row bumps `total` but not `plan_count`.
- `test_aggregate_stable_order` — aggregates come back sorted by `(kind, decision)` regardless of input order.
- `test_aggregate_empty_input_returns_empty` — `[]` in → `[]` out.
- `test_aggregate_tolerates_unknown_outcome` — an unexpected `outcome` string is counted in `total` and does not raise.

**Recommendations (`recommend_tuning`):**
- `test_recommend_high_no_op_flags_over_sensitive` — a group past `MIN_SAMPLE_FOR_RECOMMENDATION` with a `no_op` share over `HIGH_NO_OP_RATE` emits an `over-sensitive` recommendation.
- `test_recommend_high_reverted_flags_reverting` — a group with a `reverted` share over `REVERTED_RATE_FLAG` emits a `reverting` recommendation.
- `test_recommend_low_coverage_flags_uncorrelated` — a group with a high `unresolved` share emits a `low-coverage` note.
- `test_recommend_below_min_sample_is_silent` — a group with fewer than `MIN_SAMPLE_FOR_RECOMMENDATION` resolved rows yields no tuning recommendation.
- `test_recommend_well_calibrated_is_silent` — a mostly `acted-on` group emits nothing.
- `test_recommend_is_advisory_only` — `recommend_tuning` returns records and mutates none of its inputs (inputs unchanged after the call).

**Top-level + render:**
- `test_analyze_decisions_end_to_end` — over a written decision log on `tmp_path`, `analyze_decisions` returns a `TelemetryAnalysis` whose `total_events` matches the log and whose aggregates group correctly.
- `test_analyze_decisions_empty_log` — no log → `total_events == 0`, empty aggregates and recommendations.
- `test_render_analysis_contains_headline_and_recommendations` — `render_analysis` output includes the total count, a line per aggregate, and each recommendation message.
- `test_render_analysis_empty_is_graceful` — an empty analysis renders a "no telemetry yet" line, not an empty string.
- `test_aggregate_and_recommendation_frozen` — mutating a `DecisionAggregate` / `TuningRecommendation` / `TelemetryAnalysis` field raises `FrozenInstanceError`.
- `test_telemetry_analysis_does_not_import_cli` — the existing boundary guard stays green (no new imports added).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write each aggregation test alongside `aggregate_decisions`, each recommendation test alongside `recommend_tuning` (and its threshold constants), and the `analyze_decisions` / `render_analysis` tests last since they compose the pure pieces. Green-before-done gate: every test above must pass (`uv run pytest tests/test_telemetry_analysis.py -q`) before this step is considered finished.

## Acceptance criteria

- `aggregate_decisions(resolved)` returns one `DecisionAggregate` per distinct `(kind, decision)` pair, sorted by that pair, with outcome counts summing to `total`.
- A `plan_slug == ""` row is counted in `total` but excluded from `plan_count`.
- `resolved` counts `inline` + `async` rows; `unresolved` counts the rest.
- `recommend_tuning(aggregates)` emits an `over-sensitive` recommendation for a high-`no_op` group, a `reverting` recommendation for a high-`reverted` group, and a `low-coverage` note for a high-`unresolved` group — each only past `MIN_SAMPLE_FOR_RECOMMENDATION`; it stays silent on a well-calibrated or thin group and mutates nothing.
- The recommendation thresholds (`MIN_SAMPLE_FOR_RECOMMENDATION`, `HIGH_NO_OP_RATE`, `REVERTED_RATE_FLAG`, `LOW_COVERAGE_RATE`) are module-level named constants, not inlined literals.
- `analyze_decisions(repo_root)` returns a `TelemetryAnalysis` with `total_events` equal to the resolved-list length; an empty/absent log returns totals of 0 and empty aggregates/recommendations.
- `render_analysis(analysis)` returns a text block containing the total, a line per aggregate, and each recommendation; an empty analysis renders a graceful line.
- `DecisionAggregate`, `TuningRecommendation`, and `TelemetryAnalysis` are frozen dataclasses.
- `plan_tool/telemetry_analysis.py` imports no `plan_tool.cli` (existing boundary test still green).
- `uv run pytest tests/test_telemetry_analysis.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the three new aggregate/recommendation records, mirroring `convergence_diagnosis.py`'s frozen `SeriesDiagnosis` / `ConvergenceDiagnosis` / `ForkRecommendation`.
- [collections — Container datatypes (Python 3.13)](https://docs.python.org/3/library/collections.html) — `defaultdict` / `Counter` for the per-`(kind, decision)` grouping and outcome tally.

## Deferred

- **The `plan-tool telemetry` command** (`plan_tool/cli/telemetry_cmd.py`, `register(subparsers)`, `cmd_telemetry`) and the `--json` serialization of `TelemetryAnalysis` — owned by step 5 (depends on 4), which wires this leaf into the CLI modeled on `cli/convergence_cmd.py`. This step produces the structured analysis and the text `render_analysis`; step 5 prints/serializes it.
- **Time-windowing the aggregation** (last-N-days, per-run) — the plan defaults to aggregating the whole log; a window lands only if a full read proves too slow (plan Deferred).
- **Persisting the analysis as a cache sidecar** — design decision #4 is compute-on-read; this step adds no persisted shape and touches no `DATA_CONTRACT.md` / drift guard.
- **Tuning any threshold automatically** — the surface only recommends; a human edits. Never mutate a threshold, plan, or config (plan Out of scope).
