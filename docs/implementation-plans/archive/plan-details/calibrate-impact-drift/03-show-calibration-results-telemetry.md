> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Show calibration results in telemetry output

## Summary

Extend the read-only telemetry report to include the per-class calibration results produced by step 2. Update `plan_tool/telemetry_analysis.py` to project and render the new typed result alongside existing decision-event aggregates, and keep `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` as the thin text/JSON dispatch layer. The key decision is to add calibration as a separate output section rather than merge it into decision aggregates, because the two analyses have different evidence and outcome rules. On green, `plan-tool telemetry` shows deterministic human-readable calibration results and `plan-tool telemetry --json` exposes the same data without writes or behavior changes to decision analysis.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the telemetry presentation change.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why operators need the step 2 signal in the existing telemetry surface.
- [Input](#input) — Analysis and CLI output contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact edit footprint.
- [Implementation](#implementation) — Output shape, rendering rules, and read-only constraints.
- [Tests](#tests) — Unit and command-contract coverage for both output modes.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON and filesystem compatibility references.
- [Deferred](#deferred) — Work left outside this presentation step.

## Why

Step 2 computes the audit-finding calibration signal below the CLI layer, but `plan-tool telemetry` currently presents only `TelemetryAnalysis.aggregates` and `TelemetryAnalysis.recommendations`. Operators therefore cannot inspect the evidence needed to judge whether a finding class predicts later drift. Surface the completed read-only result through the existing telemetry command while keeping decision-event tuning and future impact-gate policy separate.

## Input

- **Step 2 calibration result** — Consume the typed, deterministic per-class result delivered by step 2, which discovers histories from manifest plan paths rather than decision events. Preserve its class identity, purity provenance cohort where present, confirmed/cleared/unresolved counts, resolved-only confirmation rate, and `insufficient-evidence` state without recalculating or reclassifying saved evidence in this step.

- **Existing telemetry contract** — `plan_tool/telemetry_analysis.py:TelemetryAnalysis`, `analysis_to_dict`, and `render_analysis` define the current machine-readable and text output shapes for `plan_tool/cli/telemetry_cmd.py:cmd_telemetry`.

- **CLI boundary** — `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` loads `ctx.repo_root`, calls `analyze_decisions`, and chooses JSON or text. Keep analysis and rendering in `plan_tool/telemetry_analysis.py`; the command remains read-only wiring.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/telemetry_analysis.py` — carry step 2’s calibration result through the top-level analysis, JSON projection, and text renderer.
  - `plan_tool/cli/telemetry_cmd.py` — keep `cmd_telemetry` wired to the extended analysis output if its imports or command-level behavior need adjustment.
  - `tests/test_telemetry_analysis.py` — cover JSON-compatible projection, text rendering, empty-state behavior, and stable separation from decision aggregates.
  - `tests/cli/test_telemetry_cmd.py` — cover the public text and `--json` command contracts for calibration output.

## Implementation

- **Foundational logic: telemetry calibration presentation.** Extend the `plan_tool/telemetry_analysis.py:TelemetryAnalysis` result so one read gathers both existing decision-event analysis from `analyze_decisions` and the per-class calibration result from step 2. Call the manifest-based calibration reader independently of decision-event resolution, so zero decision events never suppress saved-history calibration. Keep the calibration values typed and separate from `DecisionAggregate` and `TuningRecommendation`.

- **Use one analysis result for both formats.** Have `plan_tool/telemetry_analysis.py:analysis_to_dict` include a named calibration collection in addition to the existing `total_events`, `aggregates`, and `recommendations` keys. Serialize each class’s stable identity and the counts needed to interpret its signal, including unresolved evidence and purity provenance cohorts when step 2 provides them.

- **Render a distinct calibration section.** Update `plan_tool/telemetry_analysis.py:render_analysis` to place calibration after the existing decision aggregate and recommendation output. Make each row identify the finding class and cohort clearly enough for an operator to distinguish a positive drift signal, a resolved non-drift result, and insufficient evidence.

- **Keep empty-state semantics truthful.** Do not hide calibration merely because `TelemetryAnalysis.total_events` is zero. The current `"No telemetry recorded yet."` shortcut in `render_analysis` should apply only when neither decision telemetry nor calibration evidence exists; saved report history can provide calibration rows without decision events.

- **Preserve established decision telemetry output.** Keep `ResolvedDecision`, `DecisionAggregate`, `recommend_tuning`, and their thresholds unchanged. Existing decision aggregates and recommendations must retain their names, counts, ordering, and JSON fields; calibration is an added sibling output, not a reinterpretation of those records.

- **Keep the CLI thin and read-only.** `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` should continue to call the analysis leaf once, print `json.dumps(..., sort_keys=True)` for `--json`, print `render_analysis(...)` otherwise, and return zero. Do not add a second sidecar read, persistence path, backend call, or CLI-only classification rule.

- **Keep the analysis leaf below the CLI layer.** `plan_tool/telemetry_analysis.py` must continue to avoid imports from `plan_tool.cli`; `tests/test_telemetry_analysis.py:test_telemetry_analysis_does_not_import_cli` remains the boundary guard.

## Tests

`test_analysis_projection_includes_calibration_results` — `analysis_to_dict` includes the new calibration collection while preserving the existing decision-analysis keys and values.

`test_render_analysis_shows_calibration_section_and_cohorts` — `render_analysis` prints class identity, confirmed/cleared/unresolved counts, resolved-only rate or `insufficient-evidence`, and any purity provenance cohort from a synthetic step 2 result.

`test_render_analysis_shows_calibration_without_decision_events` — calibration evidence renders when `total_events` is zero instead of returning the no-telemetry message.

`test_render_analysis_empty_when_no_decisions_or_calibration_exist` — an analysis with neither evidence source retains the compact empty-state message.

`test_decision_aggregate_rendering_remains_present_with_calibration` — existing decision totals and recommendations remain visible when calibration rows are also present.

`test_telemetry_json_includes_calibration_results` — `plan-tool telemetry --json` emits a parseable payload with the new calibration collection.

`test_telemetry_default_prints_calibration_report` — `plan-tool telemetry` prints the same extended text produced by `plan_tool/telemetry_analysis.py:render_analysis`.

`test_telemetry_command_remains_read_only_with_calibration` — running either output mode creates no run log or calibration store and does not mutate saved evidence.

### Test-creation order (feature step)

1. `test_analysis_projection_includes_calibration_results` — define the machine-readable contract with the extended analysis result.
2. `test_render_analysis_shows_calibration_section_and_cohorts` — add the operator-facing text behavior with the renderer.
3. `test_render_analysis_shows_calibration_without_decision_events` — pin the independent empty-state rule.
4. `test_telemetry_json_includes_calibration_results` — verify the public JSON command contract.
5. `test_telemetry_default_prints_calibration_report` — verify the public text command contract.
6. `test_telemetry_command_remains_read_only_with_calibration` — retain the read-only guarantee.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/telemetry_analysis.py:TelemetryAnalysis` carries the per-class calibration result produced by step 2 without merging it into `DecisionAggregate`.
- `plan_tool/telemetry_analysis.py:analysis_to_dict` emits calibration data alongside the existing decision telemetry keys.
- `plan_tool/telemetry_analysis.py:render_analysis` shows a distinct calibration section with class identity, outcome signal, and evidence counts.
- Calibration rows preserve unresolved evidence and purity provenance cohorts supplied by step 2.
- `plan-tool telemetry --json` emits the calibration collection as valid JSON.
- `plan-tool telemetry` renders calibration even when no decision events exist but calibration evidence does.
- An analysis with no decision events and no calibration evidence still prints `No telemetry recorded yet.`
- `tests/test_telemetry_analysis.py` and `tests/cli/test_telemetry_cmd.py` pass, including the read-only and no-CLI-import guards.

## References

- [Python json documentation](https://docs.python.org/3/library/json.html) — Preserve the existing machine-readable JSON behavior and compatibility expectations.
- [RFC 8259: JSON Data Interchange Format](https://www.rfc-editor.org/info/rfc8259/) — Reference for the public JSON telemetry payload.
- [Python pathlib documentation](https://docs.python.org/3/library/pathlib.html) — Read saved evidence deterministically without mutating repository state.

## Deferred

- Impact-gate demotion — a later #152 slice may consume the advisory calibration output; this step must not change live convergence policy.
- Calibration threshold tuning — presentation must report the step 2 evidence, not auto-tune thresholds.
- Persisted calibration caches or configuration — telemetry continues to compute read-only results from existing evidence.
- Purity-cache reuse policy — provenance is displayed for interpretation, but cache hardening and threshold changes remain separate work.
