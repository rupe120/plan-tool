> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Show the mechanism advisory in convergence and combine matching edit drift

## Summary

Add a convergence advisory for open, likely mechanism-only `plan-correctness` findings from a completed bare audit. Update `plan_tool/convergence_diagnosis.py` to select eligible findings, combine them with the existing `edit_drift` signal only when they are the same current finding, and render the result without changing the verdict. Extend `tests/test_convergence_diagnosis.py` and `tests/cli/test_convergence_cmd.py` with unit and command-path coverage. On green, one eligible bare pass produces guidance, paired findings produce one combined message, and unrelated findings keep their separate advice.

## Table of Contents

- [Summary](#summary) — The advisory and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing convergence guidance for a likely detail-owned request.
- [Input](#input) — The saved-history and upstream classifier contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The existing implementation and test files to update.
- [Implementation](#implementation) — Eligibility, same-finding composition, and rendering rules.
- [Tests](#tests) — Unit and command-path coverage for the advisory.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for immutable diagnostic data and test seams.
- [Applicable guardrails](#applicable-guardrails) — Policy boundaries that keep this advisory non-enforcing.
- [Deferred](#deferred) — Presentation and provenance work outside this step.

## Why

`plan_tool/convergence_diagnosis.py:render_diagnosis()` can currently report edit drift, but it cannot point out that a current bare-stage correctness finding looks like an internal delivery choice that detail should own. That leaves an operator with a blocking-looking finding but no warning that the wording may be at the wrong level of detail. The advisory must help the operator reconsider that finding without weakening the existing audit or treating an apply-set match as proof of cause.

## Input

- **Step 2 derived signal:** Step 2 adds a deterministic per-finding mechanism signal to `plan_tool/convergence_diagnosis.py:RunFinding`. This step consumes that outcome and does not repeat its text classification.

- **Completed report history:** `plan_tool/convergence_diagnosis.py:load_report_history()` keeps only ordinary final reports, while `build_collapsed_completeness_passes()` supplies the stage-aware, reuse-collapsed completeness passes this advisory must inspect. The existing audit-revision grade decides whether a pass can supply the new advice; legacy or ungraded history cannot.

- **Open-state contract:** `plan_tool/convergence_diagnosis.py:_is_resolved_in_run()` reads the latest pass annotations to distinguish an open finding from an applied or closed one.

- **Existing comparison signal:** `plan_tool/convergence_diagnosis.py:EditDriftAdvisory` carries the current `matched_findings` that matched the prior apply set. It is comparison evidence only, not causal provenance.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — Derive the bare mechanism advisory, compose it with `EditDriftAdvisory`, and render the resulting advice through the convergence diagnosis.
  - `plan_tool/cli/convergence_cmd.py` — Hand the operator-selected grade to the new advisory boundary while retaining the command's existing diagnosis and read-only exit behavior.
  - `tests/test_convergence_diagnosis.py` — Cover eligibility, one-pass rendering, same-finding composition, residual edit-drift advice, and unchanged diagnosis behavior.
  - `tests/cli/test_convergence_cmd.py` — Seed real saved sidecars and verify the `convergence` command prints the standalone and combined guidance while retaining its read-only, exit-zero contract.

## Implementation

- **Foundational logic: current bare mechanism-advisory selection with exact edit-drift composition.** Select findings only from the newest completed `plan_tool/convergence_diagnosis.py:CompatiblePass` produced by `build_collapsed_completeness_passes()`.

- **Keep eligibility narrow.** Include a finding only when the selected pass is bare, the finding is an open `plan-correctness` finding, and Step 2’s derived signal identifies it as likely mechanism-only. Do not add a severity, domain, or blocking-predicate condition: this is an operator advisory, not another enforcement rule.

- **Respect final and collapsed history.** Use `load_report_history()` and `build_collapsed_completeness_passes()` rather than raw sidecars or raw snapshots. This keeps pre-apply checkpoints, unknown stages, and duplicate reuse replays out of the advice, and it makes one completed logical bare pass sufficient.

- **Keep the mechanism advice run-grade-only.** Retain the existing persisted audit-revision grade through the in-memory history needed for this advisory. Select only completed run-grade passes; Jira-grade and legacy or ungraded passes cannot supply, merge into, or trigger mechanism advice. Keep every pre-existing convergence verdict and non-mechanism diagnostic on its current history behavior.

- **Honor the selected convergence grade.** Have `plan_tool/cli/convergence_cmd.py:cmd_convergence()` hand `args.grade` to the new advisory boundary. Jira convergence suppresses only the mechanism advice; it retains the command's existing verdict, other diagnostics, read-only behavior, and exit-zero contract.

- **Add a diagnosis-level advisory payload.** Extend `plan_tool/convergence_diagnosis.py:ConvergenceDiagnosis` with a defaulted result for this advice so existing direct construction in tests remains valid. Keep the result derived from saved finding text, annotations, and the existing audit-revision grade; do not add a saved-review field or alter its persisted schema.

- **Combine by current finding identity only.** Intersect the eligible current findings with the `matched_findings` carried by `EditDriftAdvisory`, using the current finding identifier. Do not call `_matches()` again for this intersection: its cross-run similarity rules can join distinct current findings and would let one finding absorb another finding’s advice.

- **Render each advice class once.** Give a matching finding one combined message that names both the likely mechanism classification and the prior-apply comparison, with guidance to check whether the plan should state an observable property instead or leave the delivery choice to detail. Keep a standalone mechanism message for eligible non-matches, and keep edit-drift guidance for drift matches outside that intersection.

- **Preserve the drift evidence when presenting a remainder.** If some edit-drift matches are combined and others are not, retain the original strict-majority evidence while naming only the unmatched drift findings in the separate drift message. Do not recalculate the threshold from the remainder, because it may no longer be a majority on its own.

- **Keep wording advisory and bounded.** Reuse the existing bounded-title approach around `_EDIT_DRIFT_TITLE_CAP` so a large finding set cannot flood convergence output. State that the combined signal is not causal proof and does not alter the convergence verdict or run-readiness behavior.

- **Use one reusable line composer.** Have `render_diagnosis()` call the same mechanism/edit-drift composition helper that a later output surface can reuse. Keep existing impact-recurrence ordering and all verdict, series-breakdown, telemetry, and command behavior unchanged.

## Tests

### Tests for this step

- `test_bare_mechanism_advisory_appears_after_one_completed_pass` — verifies one open, positively classified `plan-correctness` finding in a final bare pass produces advice even though the verdict remains `insufficient-history`.

- `test_bare_mechanism_advisory_requires_open_bare_plan_correctness_finding` — verifies detail-stage findings, `plan-completeness` findings, closed findings, and unclassified findings produce no mechanism advisory.

- `test_bare_mechanism_advisory_uses_only_completed_run_grade_history` — verifies Jira-grade and legacy or ungraded passes cannot supply or merge into the advisory, while the existing non-mechanism diagnosis remains unchanged.

- `test_bare_mechanism_advisory_combines_only_same_current_edit_drift_match` — verifies one eligible finding in `EditDriftAdvisory`'s `matched_findings` receives combined guidance, while a similar but distinct current finding does not.

- `test_bare_mechanism_advisory_keeps_unrelated_standalone_and_edit_drift_advice` — verifies an eligible non-match retains standalone mechanism advice and a non-mechanism drift match retains separate edit-drift advice with the original threshold evidence.

- `test_render_combined_mechanism_edit_drift_advisory_is_recommend_only` — verifies the rendered combined message names the finding, suggests reconsidering plan-level wording or detail deferral, avoids causal wording, and does not claim to change the verdict or gate.

- `test_diagnose_mechanism_advisory_does_not_change_existing_diagnosis_fields` — verifies equivalent history with and without the advisory signal has the same verdict, blocking findings, churn, and existing edit-drift classification.

- `test_convergence_prints_standalone_mechanism_advisory_after_one_bare_pass` — drives `plan_tool.cli.app:main()` against a real saved sidecar and verifies the command prints the advice while exiting zero.

- `test_convergence_prints_combined_mechanism_edit_drift_advisory` — drives the command with a matching three-pass edit-drift history and verifies one combined message replaces duplicate per-finding advice.

- `test_convergence_jira_grade_suppresses_mechanism_advisory` — drives `convergence --grade jira` with otherwise eligible saved history and verifies the command stays read-only and exit-zero without mechanism guidance.

Every listed test and affected existing convergence tests must be green before this step is complete:

`uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q`

## Acceptance criteria

- A completed bare pass with one open, positively classified `plan-correctness` finding renders the mechanism advisory without requiring a convergence window.

- Detail-stage, closed, non-`plan-correctness`, and unclassified findings do not render the mechanism advisory.

- Only completed run-grade history can render the mechanism advisory; Jira-grade and legacy or ungraded history cannot supply or merge into it, and Jira-grade convergence remains suppressed.

- `cmd_convergence()` passes the selected grade to the new advisory boundary without changing its verdict, existing diagnostics, read-only behavior, or exit status.

- A mechanism-advisory finding that is in `EditDriftAdvisory`'s `matched_findings` renders one combined message rather than separate mechanism and drift messages for that finding.

- Eligible findings outside the edit-drift intersection retain standalone mechanism advice, and edit-drift matches outside the intersection retain their own advice.

- The combined and standalone messages do not change `ConvergenceDiagnosis.verdict`, blocking behavior, continuation behavior, failure behavior, command exit status, or persisted review schema.

- `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q` passes.

## References

- [dataclasses — Data Classes](https://docs.python.org/3.13/library/dataclasses.html) — Use for the immutable diagnosis payload and safe defaults on diagnostic data classes.

- [How to monkeypatch/mock modules and environments — pytest documentation](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for focused rendering and composition tests without changing the saved-history contract.

## Applicable guardrails

- **The plan’s “## Plan intent”, advisory-only enforcement boundary:** Keep the mechanism signal outside every blocking, continuation, failure, and exit decision.

- **The plan’s “## Step intent”, one-pass and same-finding behavior:** Show guidance after one eligible bare pass and combine only the exact current finding shared with edit drift.

- **The plan’s “## Out of scope”, existing audit policy:** Do not change `plan_tool/convergence.py:is_blocking_finding()`, convergence pass counts, the detail-stage bar, or existing failure behavior.

- **The plan’s “## Out of scope”, domain and provenance policy:** Leave domain classification unchanged and describe edit drift as a comparison signal rather than proof that an earlier edit caused a finding.

- **The plan’s “## Out of scope”, grade-specific presentation:** Keep Jira-grade suppression in convergence and `plan_tool/cli/completeness_cmd.py`; this step selects only run-grade history for the shared advice.

## Deferred

- **Completeness stderr presentation** — Step 4 updates `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines()` to reuse this step’s mechanism/edit-drift composition for run-grade audit output.

- **Mechanism classification policy** — Steps 1 and 2 own the prompt boundary and text classifier; this step only consumes their landed result.

- **Causal provenance for edit drift** — Remains outside this advisory; the apply-set comparison must not become a provenance system.
