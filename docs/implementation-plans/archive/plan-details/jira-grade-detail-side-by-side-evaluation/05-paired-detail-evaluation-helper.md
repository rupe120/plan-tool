# Step 5 — Add a paired detail evaluation helper

## Summary

Create `plan_tool/detail_evaluation.py` as the reusable owner of paired run-grade versus jira-grade evaluation records and verdict calculation. Add `docs/JIRA_GRADE_EVALUATION.md` to define the required provenance, metrics, predeclared threshold, and human review inputs, and update `docs/PROMPT_AB_TESTING.md` to point readers to this separate detail-grade evaluation. Add a representative paired-trial fixture and focused tests for validation, matched-input checks, metric comparison, and indeterminate evidence. On green, a later operator can record a durable, machine-checked comparison without changing any `detail`, `jira`, or `run` default.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the evaluation helper and documentation.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why detail grades need a matched evaluation record.
- [Input](#input) — Upstream grade-selection contracts and evaluation evidence this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New helper, fixture, tests, and documentation changes.
- [Implementation](#implementation) — Paired-record validation, metric comparison, and recommendation rules.
- [Tests](#tests) — Unit coverage for valid, invalid, and inconclusive trials.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for validation, provenance, and tests.
- [Deferred](#deferred) — Work intentionally left to the report and any later default-change plan.

## Why

Steps 3 and 4 are earlier-step prerequisites intended to make either detail grade selectable, but separate executions are not evidence that the compact contract is safe to adopt. Confirm their actual exported grade-routing and artifact-selection contracts before implementing this helper. The project needs one small, dependency-light evaluator that rejects unmatched trials, preserves the raw evidence needed to review nondeterministic results, and applies a threshold chosen before measurement. Without that boundary, each report can calculate or describe “no worse” differently, making a later default decision impossible to audit.

## Input

- **Step 3 Jira export prerequisite:** Before implementation, confirm Step 3’s exported contract for selecting and consuming the jira-grade artifact while retaining run-grade as the control. This step records the export and verification evidence; it does not alter artifact selection.
- **Step 4 Jira execution prerequisite:** Before implementation, confirm Step 4’s exported contract for an opt-in `run` path that consumes jira-grade detail while preserving the ordinary run-grade path. This step compares matched executions only after both paths exist.
- **Scenario-capture precedent:** `plan_tool/scenario_capture.py:SCHEMA_VERSION`, `Experiment`, `capture_scenario()`, and `repo_sha()` establish the project’s existing approach to versioned JSON evidence, revision provenance, and best-effort capture. Keep the evaluation record independent from scenario capture because this step evaluates detail grades, not prompt-mode arms.
- **Plan decision gate:** `docs/implementation-plans/2-jira-grade-detail-side-by-side-evaluation.md:## Architecture` requires the report to record matched baseline inputs, repository revision, backend/model settings, commands, raw artifact locations, outcomes, and a threshold declared before measurement.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/detail_evaluation.py` — Define the versioned paired-trial record, validation rules, metric comparison, and recommendation result.
  - `tests/fixtures/detail_evaluation/paired-trial.json` — Provide one complete, realistic paired record for parser and outcome tests.
  - `tests/test_detail_evaluation.py` — Cover record validation and the evaluator’s decision rules.
  - `docs/JIRA_GRADE_EVALUATION.md` — Specify how to create, review, store, and interpret a paired evaluation.

- **Existing files (edits only):**
  - `docs/PROMPT_AB_TESTING.md` — Cross-link the existing prompt-mode corpus guidance to the separate jira-grade paired-evaluation procedure without presenting it as another prompt-mode arm.

## Implementation

- **Foundational logic:** paired-trial validity and threshold evaluation. `plan_tool/detail_evaluation.py` should accept one structured record containing both run-grade and jira-grade outcomes, verify that they describe the same planned work, and return a clear recommendation rather than silently comparing unrelated runs.

- **Use a strict, versioned record model.** Define self-describing models such as `PairedTrial`, per-grade outcome data, and an evaluation result in `plan_tool/detail_evaluation.py`. Reject unknown or malformed fields so a misspelled metric cannot become unreviewed evidence. Preserve the raw paths or identifiers for artifacts, run logs, verification output, and completeness-audit reports rather than copying their contents into the record.

- **Require matched provenance before comparing.** Both outcomes must name the same baseline plan, selected step set, repository revision, backend/model configuration, verification command, and controlled scope-change replay. A pair that differs on any comparison key is invalid evidence, not a degraded comparison. Record timestamps for traceability, but do not require equal timestamps.

- **Keep the grade labels fixed.** The two sides must be exactly one run-grade control and one jira-grade treatment. Do not let caller-supplied labels redefine the control, and do not accept a missing jira-grade artifact as a run-grade substitute. This protects the explicit-grade behavior introduced by steps 3 and 4.

- **Separate measurements from judgment.** Record a Boolean first-pass verification outcome for each grade, retry count, elapsed time, available cost and tool-use telemetry, and a completed manual-convergence trajectory of three `completeness-audit --iterate` snapshots: baseline, post-correction, and third audit. For each snapshot, preserve the canonical identities and severities of material findings, compare stable identities and material severities across the three snapshots, and record the controlled scope-change replay result. Derive audit churn only from that completed trajectory; a single replay's distinct-finding count is insufficient evidence. For this one-pair record, “no worse” first-pass verification means jira-grade succeeds whenever the run-grade control succeeds; it is not an aggregate rate. Record human-reviewed scope-adherence and diff-quality verdicts as explicit inputs with a reviewer note or evidence reference. The helper should aggregate and compare supplied values; it must not pretend it can infer human diff quality from a numeric metric.

- **Make the threshold an input captured with the trial.** Require the record to state the predeclared adoption gate together with declaration provenance: a declaration timestamp, a repository path pinned to an immutable commit revision, and the declaration record's SHA-256 content digest. Validate that the declared digest matches the referenced, commit-pinned record and that the declaration predates both grade executions; a threshold declared after either execution is invalid evidence. The evaluator should return a passing recommendation only when jira-grade meets every required gate: no worse Boolean first-pass verification outcome and scope/diff verdict, no material regression in retries or elapsed time, no material regression in cost or tool-use telemetry when it is available, and a strictly lower audit-churn result from the completed three-snapshot trajectory than run-grade. Equal or higher audit churn fails the gate. Unavailable cost or tool-use telemetry is non-comparable and must retain its reason or evidence location; a missing snapshot or other required evidence must produce an indeterminate result, not a pass.

- **Represent unavailable telemetry honestly.** Distinguish an unavailable cost or tool-use field from a measured zero. Preserve the reason or evidence location for unavailable values so a report can explain what could not be compared. Do not invent cost estimates from elapsed time.

- **Use explicit decision states.** A result should distinguish invalid input, failed threshold, passed threshold, and indeterminate evidence. A passing result is evidence for a later plan only; it must not trigger a default change or mutate plan artifacts.

- **Document the operator workflow once.** In `docs/JIRA_GRADE_EVALUATION.md`, define the paired-run checklist, record format, threshold declaration, three-snapshot manual-convergence trajectory, controlled scope-change replay, review responsibilities, and report handoff. Require baseline, post-correction, and third `completeness-audit --iterate` snapshots with stable-identity and material-severity comparison before audit churn can inform the recommendation. State that the document specifies a future evaluation process and does not claim an evaluation has run. Link to `docs/PROMPT_AB_TESTING.md` only for shared ideas such as reproducible provenance; do not duplicate prompt-mode capture schema or instructions.

- **Keep prompt-mode documentation scoped.** In `docs/PROMPT_AB_TESTING.md`, add a short boundary note that combined versus split prompt experiments use `plan_tool/scenario_capture.py`, while run-grade versus jira-grade evaluation uses `plan_tool/detail_evaluation.py` and `docs/JIRA_GRADE_EVALUATION.md`. Do not register a new `Experiment` or change `PROMPT_MODE_EXPERIMENT`.

## Tests

- `test_parses_complete_paired_trial_fixture` — loads `tests/fixtures/detail_evaluation/paired-trial.json` and preserves both grade outcomes, provenance, raw-evidence locations, threshold, and threshold-declaration provenance.
- `test_rejects_unknown_or_missing_record_fields` — proves the strict record contract rejects ambiguous input instead of ignoring it.
- `test_rejects_unmatched_baseline_or_revision` — refuses to compare runs with different plans, step sets, repository revisions, backend/model settings, verification commands, or scope-change replay inputs.
- `test_requires_one_run_grade_control_and_one_jira_grade_treatment` — rejects duplicate, missing, or mislabeled grade outcomes.
- `test_requires_immutable_threshold_declaration_locator` — rejects a mutable declaration path, an unpinned revision, or a declaration-record digest mismatch.
- `test_rejects_threshold_declared_after_an_execution` — rejects a threshold whose declaration timestamp follows either grade execution.
- `test_passes_only_when_every_predeclared_gate_passes` — returns a passing recommendation when jira-grade satisfies first-pass, scope/diff, retry, elapsed, telemetry, and churn requirements.
- `test_failed_gate_returns_non_adoption_recommendation` — identifies the failed required metric and does not report a pass.
- `test_missing_required_evidence_is_indeterminate` — distinguishes absent human verdicts and other required evidence from successful zero-valued measurements while treating unavailable telemetry as non-comparable.
- `test_requires_completed_manual_convergence_trajectory` — returns indeterminate unless each grade records baseline, post-correction, and third `completeness-audit --iterate` snapshots with canonical material-finding identities and severities.
- `test_compares_manual_convergence_audit_churn` — compares stable finding identities and material severities across each grade's three snapshots, passes only when jira-grade has a strictly lower churn result than run-grade, and fails equal or higher results.
- `test_evaluation_does_not_change_detail_defaults_or_artifacts` — confirms the helper is pure evaluation logic with no calls into detail authoring, Jira export, or run execution.

### Test-creation order (feature step)

1. `test_parses_complete_paired_trial_fixture` — establish the valid record shape before implementing comparison logic.
2. `test_rejects_unknown_or_missing_record_fields` — lock down strict input validation.
3. `test_rejects_unmatched_baseline_or_revision` — add the matched-pair invariant before metric aggregation.
4. `test_requires_one_run_grade_control_and_one_jira_grade_treatment` — pin control/treatment identity.
5. `test_requires_immutable_threshold_declaration_locator` — prove the referenced declaration is commit-pinned and digest-verified.
6. `test_rejects_threshold_declared_after_an_execution` — prove the adoption gate was fixed before measurement.
7. `test_passes_only_when_every_predeclared_gate_passes` — implement the successful evaluation path.
8. `test_failed_gate_returns_non_adoption_recommendation` — cover required threshold failures.
9. `test_missing_required_evidence_is_indeterminate` — cover incomplete required evidence while treating unavailable telemetry as non-comparable.
10. `test_requires_completed_manual_convergence_trajectory` — require all three audit snapshots before evaluation.
11. `test_compares_manual_convergence_audit_churn` — cover stable-identity and material-severity comparisons plus lower, equal, and higher churn results.
12. `test_evaluation_does_not_change_detail_defaults_or_artifacts` — keep the helper isolated from consumer behavior.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/detail_evaluation.py` can load and validate the complete paired record in `tests/fixtures/detail_evaluation/paired-trial.json`.
- A record with unknown fields, missing required evidence, or invalid grade labels fails clearly rather than being partially accepted.
- The evaluator rejects a pair whose baseline plan, steps, repository revision, backend/model settings, verification command, or controlled scope-change replay differs between grades.
- The evaluator distinguishes measured zero telemetry from unavailable telemetry.
- A passing recommendation requires every threshold declared before either execution in a record identified by a commit-pinned repository path and verified SHA-256 content digest, including the Boolean per-run first-pass verification outcome, scope adherence/diff-quality review, retry and elapsed-time limits, available telemetry limits, and a strictly lower audit-churn result from completed baseline, post-correction, and third `completeness-audit --iterate` snapshots that compare stable material-finding identities and severities.
- Incomplete required evidence returns an indeterminate result and cannot recommend adoption; unavailable cost or tool-use telemetry remains non-comparable with its reason or evidence location recorded.
- A failed required gate returns a non-adoption result that identifies the failed comparison.
- `docs/JIRA_GRADE_EVALUATION.md` specifies the required record, evidence locations, review checklist, and report handoff without claiming that an evaluation already exists.
- `docs/PROMPT_AB_TESTING.md` points to the separate detail-grade evaluation without changing `PROMPT_MODE_EXPERIMENT`, scenario capture, or prompt-mode defaults.
- The helper does not alter run-grade defaults, rewrite detail artifacts, invoke `jira`, or invoke `run`.

## References

- [Pydantic Configuration](https://docs.pydantic.dev/latest/api/config/) — Use strict model configuration to reject ambiguous paired-trial fields.
- [Pydantic Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Use model validation for cross-field matched-provenance and grade-pair rules.
- [pytest API Reference](https://docs.pytest.org/en/stable/reference/reference.html) — Use fixtures and parametrization for valid, invalid, and indeterminate paired records.
- [Git rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Record the repository revision needed to reproduce a paired trial.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Store and validate artifact and evidence paths without platform-specific string handling.

## Deferred

- Running the evaluation and publishing `docs/JIRA_GRADE_EVALUATION_REPORT.md` — step 6 owns the real trial, recorded evidence, and recommendation.
- Changing any `detail`, `jira`, or `run` default — require a later plan after a passing, reviewed evaluation.
- Corpus-wide benchmarking, repeated-sample statistical analysis, and model comparison — outside this focused paired decision record.
- Automatic diff-quality or scope-adherence judgment — retain an explicit human-reviewed verdict until a separate plan defines a trustworthy automated measure.
