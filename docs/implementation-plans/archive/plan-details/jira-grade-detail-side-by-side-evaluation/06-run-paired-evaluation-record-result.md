# Step 6 — Run the paired evaluation and record the result

## Summary

Run one real, matched run-grade versus jira-grade trial using the evaluation contract from step 5. Create `docs/JIRA_GRADE_EVALUATION_RECORD.json` as the evaluator input and `docs/JIRA_GRADE_EVALUATION_REPORT.md` as its human-readable result, with a clear recommendation that does not change any default. Update `BACKLOG.md` entry `#164` to link the report and state the evidence-backed next decision. On green, a reviewer can trace the reported verdict to the same baseline, commands, artifacts, audit evidence, and predeclared gate for both grades.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the recorded evaluation.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why the side-by-side path needs real evidence.
- [Input](#input) — Upstream evaluation contract and paired-run prerequisites.
- [Files (creates vs edits)](#files-creates-vs-edits) — Report creation and backlog reconciliation.
- [Implementation](#implementation) — Required matched trial, evidence capture, and decision rules.
- [Tests](#tests) — Existing evaluator coverage to run against the completed structured record.
- [Acceptance criteria](#acceptance-criteria) — Checkable report and backlog outcomes.
- [References](#references) — Provenance and path-handling references.
- [Deferred](#deferred) — Default changes and broader experiments left out of this step.

## Why

The explicit Jira-grade paths from steps 3 and 4 make a comparison possible, but they do not show whether the thinner detail remains safe for real execution or reduces audit churn. `BACKLOG.md` entry `#164` requires a durable, matched result before anyone can consider changing the default. This step turns step 5’s record-validation and gate rules into that evidence without weakening audits or treating a one-sided run as proof.

## Input

- **Step 5 paired-evaluation contract:** Step 5 must first create `plan_tool/detail_evaluation.py` and `docs/JIRA_GRADE_EVALUATION.md`; once those not-yet-created outputs exist, use their strict paired-trial record and evaluator. Confirm the actual public record-loading and evaluation API from the implemented step rather than inventing a second report calculation.
- **Step 3 and step 4 selected-grade behavior:** Run one run-grade control and one explicitly selected Jira-grade treatment over the same plan, step set, repository revision, backend/model settings, verification command, and controlled scope-change replay. Do not accept a default run-grade artifact in place of a missing Jira-grade artifact.
- **Provenance precedent:** `plan_tool/scenario_capture.py:repo_sha()` shows the project’s repository-revision convention, but scenario capture remains separate from this durable paired-outcome record.

## Files (creates vs edits)

- **New files:**
  - `docs/JIRA_GRADE_EVALUATION_RECORD.json` — Store the complete paired-trial record as the sole evaluator input and source of the reported verdict.
  - `docs/JIRA_GRADE_EVALUATION_REPORT.md` — Record the completed paired trial, evidence locations, evaluator output, and decision.

- **Existing files (edits only):**
  - `BACKLOG.md` — Update entry `#164` with the report link, observed result, and the remaining decision status without removing the backlog item merely because this experiment was completed.

## Implementation

- **Foundational logic:** Store the completed matched trial only in `docs/JIRA_GRADE_EVALUATION_RECORD.json`, then use step 5's implemented evaluator entry point or public API before writing `docs/JIRA_GRADE_EVALUATION_REPORT.md`. Use its evaluator result as the sole source for the verdict; do not reproduce its comparison rules in Markdown or `BACKLOG.md`.

- **Declare the gate before either execution.** Preserve the threshold declaration evidence required by step 5, including its commit-pinned location, content digest, and declaration time. The report must show that it predates both grade executions.

- **Keep every comparison input matched.** Record the baseline plan and selected steps, repository revision, backend/model configuration, verification command, and controlled scope-change replay for both grades. Treat any mismatch as invalid evidence, not as a tolerable difference.

- **Capture raw, reviewable evidence.** Record full repo-root-relative paths or stable identifiers for both detail artifacts, run logs, verification output, scope-change replay evidence, and each `completeness-audit --iterate` report. Keep raw outputs at their source locations; the report should summarize and link them rather than copy large logs.

- **Complete both audit trajectories.** For each grade, record baseline, post-correction, and third-audit snapshots from `completeness-audit --iterate`. Review the saved reports, make any in-scope conceptual corrections manually, and do not auto-drive `completeness-apply` before recording the post-correction and third snapshots; `--iterate` applies only deterministic findings. Compare stable material-finding identities and severities through the completed trajectory so audit churn is measured consistently rather than inferred from one audit.

- **Record human judgment explicitly.** Include the reviewer’s scope-adherence and diff-quality verdict for each run, plus a brief evidence reference or note. Do not replace that judgment with an unvalidated automated score.

- **Make the report decision-focused.** Copy the completed record location and evaluator result from step 5's implemented interface into `docs/JIRA_GRADE_EVALUATION_REPORT.md`, then organize the report so a reader can find the predeclared gate, matched provenance, per-grade outcomes, telemetry availability, audit-churn comparison, and resulting recommendation. Preserve the evaluator's `invalid-input`, `failed-gate/non-adoption`, `passed`, or `indeterminate` verdict exactly as returned by the step 5 contract.

- **Retain the default regardless of outcome.** A passing report is evidence for a later plan, not authorization to invert defaults. If the result is failed, mixed, invalid, or indeterminate, state that run-grade remains the default and name the missing or regressed evidence.

- **Reconcile `#164` precisely.** In `BACKLOG.md`, keep the original problem and scope contract intact, add the report result and link, and state whether a separate default-inversion plan remains blocked by the recorded outcome. Do not claim the Jira-grade path is the new default or delete `#164` solely because this step produced evidence.

## Tests

- `tests/test_detail_evaluation.py` — Step 5 must first create this evaluator suite; then run it against `docs/JIRA_GRADE_EVALUATION_RECORD.json` to confirm its matched provenance, gate declaration, evidence, and verdict rules hold.
- `tests/fixtures/detail_evaluation/paired-trial.json` — Step 5 must first create this representative fixture; then use it only to understand the required record shape, not as trial evidence.

### Verification (non-code step)

- **Record validation** — Use step 5's implemented evaluator entry point or public API with `docs/JIRA_GRADE_EVALUATION_RECORD.json`, retain its output, and copy its returned verdict into the report.
- **Evidence paths** — Confirm every backticked repo path in `docs/JIRA_GRADE_EVALUATION_REPORT.md` exists and points to the stated artifact or output.
- **Provenance check** — Confirm the recorded repository revision and predeclared threshold declaration match the evidence used for both executions.
- **Decision consistency** — Confirm the report summary, evaluator output, and `BACKLOG.md` entry `#164` state the same recommendation and retain run-grade as the current default.
- **Link integrity** — Confirm relative links from `docs/JIRA_GRADE_EVALUATION_REPORT.md` resolve from the `docs/` directory.

## Acceptance criteria

- `docs/JIRA_GRADE_EVALUATION_RECORD.json` contains one real run-grade control and one real Jira-grade treatment with matched baseline plan, steps, repository revision, backend/model settings, verification command, and controlled scope-change replay.
- The report identifies the predeclared threshold declaration, its immutable provenance, and evidence that it predates both executions.
- The structured record contains first-pass verification, retries, elapsed time, available cost and tool-use telemetry, human scope-adherence and diff-quality verdicts, and raw evidence locations for both grades; the report copies its evaluator result.
- Each grade includes baseline, post-correction, and third `completeness-audit --iterate` snapshots in the structured record after saved-report review and manual in-scope conceptual corrections without auto-driving `completeness-apply`, and the report records the resulting audit-churn comparison.
- Step 5's implemented evaluator entry point or public API accepts the completed record, or the report preserves its `invalid-input` verdict for malformed or otherwise invalid records and its `indeterminate` verdict for incomplete required evidence rather than collapsing either into failed-gate/non-adoption.
- `BACKLOG.md` entry `#164` links to the report and reflects its recorded result without claiming a default inversion.
- Run-grade remains the default for `detail`, `jira`, and `run`.

## References

- [Git rev-parse Documentation](https://git-scm.com/docs/git-rev-parse) — Record and verify the repository revision used by both executions.
- [pathlib — Object-oriented filesystem paths](https://docs.python.org/3/library/pathlib.html) — Keep report evidence locations portable and reviewable.

## Deferred

- Default inversion for `detail`, `jira`, or `run` — requires a separate plan even if this report passes the gate.
- Corpus-wide benchmarking, repeated trials, and statistical confidence analysis — this step records the focused paired evaluation required by `BACKLOG.md` entry `#164`.
- Automated scope-adherence or diff-quality scoring — retain the explicit human-reviewed verdict until a later plan defines a trustworthy measure.
