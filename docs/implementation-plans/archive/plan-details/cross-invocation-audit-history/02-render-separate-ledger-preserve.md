> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Render the separate ledger and preserve the convergence diagnosis's meaning

## Summary

Render step 1’s saved-audit evidence ledger beside the existing convergence diagnosis. Update `plan_tool/convergence_diagnosis.py` with the display logic and `plan_tool/cli/convergence_cmd.py:cmd_convergence` with the read-only command wiring. Keep the ledger separate from `plan_tool/convergence_diagnosis.py:diagnose_convergence` so evidence visibility never changes a verdict or advisory. On green, `plan-tool convergence <name>` prints its existing diagnosis first, then an ordered ledger with saved states and next actions.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the rendered ledger and preserved diagnosis.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the command needs both evidence visibility and an unchanged diagnosis.
- [Input](#input) — Step 1’s ledger contract and the existing diagnosis contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by rendering and command wiring.
- [Implementation](#implementation) — Rendering rules, output order, and isolation boundaries.
- [Tests](#tests) — Renderer and command-path coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for immutable models and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this an evidence view.
- [Deferred](#deferred) — Comparison and persistence work outside this step.

## Why

`plan_tool/convergence_diagnosis.py:load_report_history` deliberately filters saved files to eligible final history, while step 1 exposes all saved completeness artifacts as evidence. The command must show both views without implying that a visible report-only, checkpoint, unknown-role, malformed, or orphaned artifact counted toward convergence. It will share one sidecar load between those two views. The current no-history message is too broad once the ledger can show such evidence, so this step narrows that wording without changing the diagnosis itself.

## Input

- **Step 1 output:** Consume the immutable ordered ledger produced by step 1’s reader in `plan_tool/convergence_diagnosis.py`. Use its display state and saved metadata as provided; do not reopen files, reclassify rows, or validate them against the current repository.

- **Diagnosis contract:** Preserve `plan_tool/convergence_diagnosis.py:load_report_history`, `diagnose_convergence`, and `render_diagnosis` as the sole convergence-decision path. Eligible final history remains distinct from the ledger’s complete artifact inventory.

- **Command contract:** Keep `plan_tool/cli/convergence_cmd.py:cmd_convergence` read-only with its existing best-effort `plan_tool/telemetry.py:record_convergence` append. Load each saved JSON sidecar once for both history and ledger readers; do not add a telemetry event or change the recorded verdict or eligible-history run count.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/convergence_diagnosis.py` — Add the ledger renderer and correct the no-history explanation in `render_diagnosis`.

  - `plan_tool/cli/convergence_cmd.py` — Load step 1’s ledger and print it after the existing diagnosis output.

  - `tests/test_convergence_diagnosis.py` — Cover ledger rendering, state-specific actions, and the eligible-history no-history wording.

  - `tests/cli/test_convergence_cmd.py` — Cover command output order, diagnosis isolation, telemetry preservation, and the zero-Claude, zero-exit path.

## Implementation

- **Foundational logic:** Render the ordered evidence ledger next to, never inside, the convergence diagnosis. Keep the ledger renderer in `plan_tool/convergence_diagnosis.py` with the ledger reader so it consumes display-safe rows rather than raw files.

- **Keep the decision paths separate:** Leave `load_report_history`, `diagnose_convergence`, finding matching, verdict selection, and advisory classification unchanged. The ledger must not become input to `ReportHistory`, `ConvergenceDiagnosis`, or any advisory helper.

- **Render diagnosis first:** In `plan_tool/cli/convergence_cmd.py:cmd_convergence`, retain the current diagnosis flow and place the ledger after `render_diagnosis` with a clear separate heading. An empty ledger must render its `no-saved-audits` state rather than disappearing.

- **Trust step 1’s row state:** Render each row’s saved path, filename-time display, and saved metadata without changing its state. Do not infer freshness, identity, coverage validity, matching findings, or a relationship between rows.

- **Give every state one action:** Render the action associated with the row state from step 1. A `saved-final` whose saved headline is `no-qualified-current-evidence` directs a fresh audit because the saved result itself says it has no qualified current evidence. Other known final results point to the saved report and result. An unknown result directs the operator to inspect the saved report and only run a fresh audit when a qualified result is needed. Other visible states name the artifact and direct the operator to inspect it or run a fresh audit when new structured evidence is needed.

- **Correct no-history precisely:** Update `render_diagnosis` so `no-history` means no eligible ordinary-final completeness or reconcile history sidecars. Do not let visible ledger artifacts weaken or upgrade that verdict.

- **Preserve command behavior:** Keep `cmd_convergence`’s name resolution, audit-stage handling, advisory output, always-zero return after a resolved plan, and single existing `record_convergence` call. Continue passing `runs=len(history.runs)`, not the number of ledger rows.

- **Reject a combined renderer:** Do not extend `render_diagnosis` to discover or render ledger artifacts. Its `ConvergenceDiagnosis` input intentionally lacks complete saved-artifact evidence, and coupling the two would make visibility look like decision evidence.

## Tests

### Tests for this step

- `test_render_audit_evidence_ledger_empty` — An empty ledger renders the separate `no-saved-audits` state.

- `test_render_audit_evidence_ledger_renders_rows_in_reader_order` — The renderer preserves step 1’s ordered rows rather than sorting or pairing them again.

- `test_render_audit_evidence_ledger_state_actions_are_specific` — Every ledger state names its artifact and renders only its assigned next action.

- `test_render_audit_evidence_ledger_saved_final_unknown_result_does_not_claim_a_result` — A supported final sidecar without a qualified result remains visible and directs inspection rather than inventing a result.

- `test_render_audit_evidence_ledger_no_qualified_current_evidence_requests_fresh_audit` — A valid saved final whose headline is `no-qualified-current-evidence` directs a fresh audit rather than presenting an ordinary final-result action.

- `test_render_no_history_names_eligible_final_history_only` — `render_diagnosis` explains that no-history concerns eligible final history sidecars, not all saved artifacts.

- `test_convergence_renders_ledger_after_existing_diagnosis` — `plan_tool/cli/convergence_cmd.py:cmd_convergence` prints the unchanged diagnosis before the separate ledger.

- `test_convergence_visible_nonfinal_ledger_does_not_change_no_history_verdict` — Report-only, checkpoint, unknown-role, orphan, or malformed ledger evidence remains visible while the diagnosis stays `no-history` when no eligible final history exists.

- `test_convergence_loads_each_saved_sidecar_once` — The command shares the saved-sidecar load between the diagnosis and ledger readers.

- `test_convergence_malformed_sidecar_is_visible_not_an_error` — A paired JSON sidecar with an unsafe kind, optional audit-metadata collection, or diagnosis-consumed recommendation value is either classified as `malformed-sidecar` or retained with unknown optional metadata, as step 1 specifies, and leaves the resolved command on its zero exit path.

- `test_convergence_ledger_preserves_diagnosis_advisories_and_eligible_run_count` — Ledger rows do not alter the verdict, advisory text, or the `runs` value recorded through `record_convergence`.

- `test_convergence_ledger_spawns_no_backend_and_exits_zero` — Rendering saved evidence performs no backend call and retains the command’s successful informational exit.

Every listed test in `tests/test_convergence_diagnosis.py` and `tests/cli/test_convergence_cmd.py` must be green before this step is complete.

## Acceptance criteria

- `plan-tool convergence <name>` prints the existing convergence diagnosis followed by one separate saved-audit ledger.

- The ledger renders step 1’s row order, state, saved metadata, artifact path, and state-specific action without reopening or validating source artifacts.

- An empty ledger renders `no-saved-audits`.

- A visible report-only, orphaned, malformed, checkpoint, or unknown-role artifact does not alter `no-history`, `insufficient-history`, `converging`, or any diagnosis advisory.

- The no-history explanation states that no eligible final convergence-history sidecar exists.

- `cmd_convergence` retains its existing telemetry event and eligible-history `runs` count, performs no additional write, invokes no backend, and returns zero after successful plan resolution.

- An unsafe persisted kind or diagnosis-consumed required field cannot abort history loading before the ledger renders its malformed state; malformed optional audit metadata renders as unknown instead.

- `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q` passes.

## References

- [dataclasses — Data Classeshttps: — Use for consuming step 1’s immutable display models without mutating evidence.

- [How to parametrize fixtures and test functionshttps: — Use to cover each rendered state and action consistently.

## Applicable guardrails

- **The plan’s `## Plan intent`, separate read-only ledger:** Keep the ledger an evidence display. It must not compare entries or make a cross-invocation decision.

- **The plan’s `## Step intent`, preserve diagnosis meaning:** Keep verdicts, advisories, telemetry behavior, and exit behavior independent from ledger rows.

- **The plan’s `## Out of scope`, no new authority:** Do not add a command surface, sidecar schema, gate, freshness check, or plan mutation while rendering.

## Deferred

- Trusted cross-invocation trajectory comparison — Deferred #303 owns provenance, evidence admission, and pairwise comparison.

- Audit cache and recheck behavior — #173 remains outside this display-only command path.

- Persisted audit-coverage schema migration — #301 owns any saved-schema change.
