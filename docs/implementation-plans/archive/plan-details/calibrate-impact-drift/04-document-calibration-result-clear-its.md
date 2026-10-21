> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document the calibration result and clear its backlog block

## Summary

Document the verified read-only calibration result in `DATA_CONTRACT.md`, remove the completed #154 backlog block from `BACKLOG.md`, and update the completed impact-convergence plan so it no longer describes calibration as pending. The key decision is to record the result as a runtime analysis of existing evidence, not as a new persisted telemetry schema or a live gate change. Verify steps 1–3 before changing status wording. On green, operators can find the calibration contract, #152’s demote work is no longer shown as blocked on #154, and related backlog references remain accurate.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog update.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why shipped status must follow verified behavior.
- [Input](#input) — Runtime and documentation contracts to verify first.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact documentation footprint.
- [Implementation](#implementation) — Documentation, backlog, and cross-reference updates.
- [Tests](#tests) — Non-code verification cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON compatibility reference for documented sidecars.
- [Deferred](#deferred) — Work that calibration unlocks but does not implement.

## Why

The calibration result gives #152’s remaining demote slice outcome-based evidence, but its status is currently tracked as unfinished in `BACKLOG.md` and in `docs/implementation-plans/2-gate-convergence-by-impact.md`. Leaving those references unchanged makes shipped work look blocked and hides the boundary between the completed read-only analysis and the still-separate policy change. Documentation must follow the verified implementation, not the earlier plan wording.

## Input

- **Step 3 telemetry surface** — Verify that `plan_tool/telemetry_analysis.py:TelemetryAnalysis`, `analysis_to_dict`, and `render_analysis` expose the calibration result, and that `plan_tool/cli/telemetry_cmd.py:cmd_telemetry` presents it without writes.

- **Read-only evidence contract** — Confirm the result reads existing saved reports and run evidence only. `DATA_CONTRACT.md:## Decision telemetry log` must continue to describe `DecisionEvent` persistence accurately and must not imply a calibration cache or new telemetry event schema.

- **Impact-gate boundary** — Verify `plan_tool/convergence.py:is_blocking_impact` remains the existing augment-only predicate. This step documents the calibration result as a future input to #152’s demote slice; it does not claim that live convergence behavior changed.

- **Backlog references** — Start with `BACKLOG.md:#154 — Calibrate the impact axis against observed reconcile-code drift`, `BACKLOG.md:#152 — Key convergence blocking on the impact axis`, `BACKLOG.md:#153 — Route a recurring high-impact seam` (superseded), and `BACKLOG.md:#158 — Add an impact-recurrence classifier`. Sweep remaining #154 references before removing its block.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — document the read-only calibration output and its relationship to existing persisted report, run, and decision-telemetry evidence; state that calibration creates no new persisted store.
  - `BACKLOG.md` — remove the completed #154 entry, update #152 to show its demote slice is unblocked but still unimplemented, preserve #153 as superseded, and reword #158 or other references that treat #154 as pending.
  - `docs/implementation-plans/2-gate-convergence-by-impact.md` — update completed-plan prose, acceptance criteria, and deferred wording that still says calibration is pending or blocks #152’s demote.

## Implementation

- **Foundational logic: verified calibration closeout.** Treat this as a documentation and backlog reconciliation step. Make the written contract match the implemented, operator-visible calibration result from steps 1–3 without changing production behavior.

- **Document runtime behavior, not a new schema.** Extend `DATA_CONTRACT.md:## Decision telemetry log` or its nearby telemetry-reading description to explain that `plan-tool telemetry` combines persisted decision telemetry with saved report and run evidence to compute calibration on read. Identify the public analysis anchors `plan_tool/telemetry_analysis.py:analyze_decisions`, `classify_calibration_recommendation`, `analysis_to_dict`, and `render_analysis` so a later #152 demote design can derive the same class key without changing this completed plan.

- **Preserve the read-only boundary.** State that calibration is advisory, remains separate from `DecisionEvent`, creates no calibration sidecar or cache, and does not mutate plans, configuration, or live gates. Do not add a table for a guessed JSON field name; verify the implemented output shape from step 3 before documenting its exact labels.

- **Close #154 without losing remaining work.** Remove only the `BACKLOG.md:#154 — Calibrate the impact axis against observed reconcile-code drift` block after verification. Keep #152 open for the impact-only demote, but replace “blocked on #154” wording with an accurate statement that the calibration evidence is available and the demote implementation remains separate.

- **Repair inbound references.** Update all surviving `BACKLOG.md` references that describe #154 as a pending prerequisite, especially the arc descriptions for #152 and #158. Preserve #153 as a superseded record; retain #158 and #155 as open work.

- **Update the completed gate plan.** In `docs/implementation-plans/2-gate-convergence-by-impact.md`, revise its `## Out of scope`, `## Acceptance criteria`, and `## Deferred` references to distinguish completed calibration from the still-deferred #152 demote implementation. Keep its historical scope clear: the completed plan shipped the augment rule, not the demote.

- **Verify before claiming shipment.** If steps 1–3 do not provide the documented result, provenance cohorts, unresolved-evidence handling, and telemetry output, stop without removing #154 or unblocking #152 in prose.

## Tests

`test_telemetry_analysis` coverage in `tests/test_telemetry_analysis.py` — verify the implemented calibration result remains separate from decision aggregates and preserves unresolved evidence and provenance cohorts.

`test_telemetry_command` coverage in `tests/cli/test_telemetry_cmd.py` — verify text and JSON telemetry output expose the verified calibration result without writes.

`test_data_contract` coverage in `tests/test_data_contract.py` — verify `DATA_CONTRACT.md` still matches registered persisted telemetry shapes after the documentation update.

`test_high_impact_nit_blocks` in `tests/test_convergence.py` — verify the documented #152 boundary remains the existing augment predicate rather than an implemented demote.

### Verification (non-code step)

- `telemetry result matches documentation` — Run the focused telemetry tests and compare `TelemetryAnalysis`, `analysis_to_dict`, and `render_analysis` with the documented result and read-only limits.

- `data-contract wording is accurate` — Run `tests/test_data_contract.py` and confirm the update describes existing persisted evidence without inventing a calibration persistence contract.

- `backlog references are reconciled` — Search `BACKLOG.md` and `docs/implementation-plans/2-gate-convergence-by-impact.md` for `#154`; every surviving reference must describe calibration as completed, not pending or blocking.

- `demote remains separate` — Confirm `plan_tool/convergence.py:is_blocking_impact` and its focused tests show no impact-only demotion change.

## Acceptance criteria

- `DATA_CONTRACT.md` documents calibration as a read-only analysis over existing evidence and does not describe a new persisted calibration store or `DecisionEvent` variant.
- `BACKLOG.md` no longer contains the #154 backlog block.
- `BACKLOG.md:#152 — Key convergence blocking on the impact axis` remains open for the impact-only demote and no longer says that work is blocked on #154.
- Surviving #153 (superseded), #158, #155, and other backlog references do not describe #154 calibration as unfinished.
- `docs/implementation-plans/2-gate-convergence-by-impact.md` no longer states that #154 is pending or blocks the demote, while still excluding the demote from the completed augment plan.
- `tests/test_data_contract.py`, `tests/test_telemetry_analysis.py`, `tests/cli/test_telemetry_cmd.py`, and `tests/test_convergence.py` pass before the documentation claims completion.

## References

- [RFC 8259: JSON Data Interchange Format](https://www.rfc-editor.org/info/rfc8259/) — Use when checking that documentation of existing JSON sidecars and telemetry output remains compatible with the standard format.

## Deferred

- **Impact-only demotion** (`bafd6791befc230e29100c87744ed929a6cb00c4e71a1168fdcba790706ccf06`) — #152 can consume the documented calibration result in a separate implementation slice; this step does not re-key `is_blocking_impact`.

- **Live-loop impact-recurrence structural stop and purity-cache hardening** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — #158 and #155 remain separate backlog work; #153 remains the superseded source record.
