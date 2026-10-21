> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Report Data Contract Drift In Completeness Audits

## Summary

This step threads the data-contract drift checks from step 1 into `completeness-audit` so the audit report names contract/documentation drift alongside the existing deterministic findings. The main code path is `plan_tool/cli/completeness_phases.py:_run_deterministic_checks`, with rendering and persistence flowing through `plan_tool/cli/completeness_phases.py:_render_grouped_report`, `plan_tool/cli/completeness_phases.py:_render_completeness_json`, and `plan_tool/cli/completeness_phases.py:_persist_and_present_report`. The key design choice is structured pass-through reporting: consume the step 1 contract drift records, keep their apply payloads and freshness fingerprints stable, and add them to completeness outputs without changing saved-review schema. On green, a completeness audit that finds `DATA_CONTRACT.md` drift reports it in stdout/markdown, includes it in `--json`, persists the recommendation plus structured data-contract payload when findings are saved, and marks blocking status according to severity.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and the main integration points.
- [Why](#why) — Why data-contract drift belongs in completeness audits.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step edits and what each edit owns.
- [Implementation](#implementation) — The intended reporting path and constraints for wiring it.
- [Tests](#tests) — The test cases that cover the new audit surface.
- [Acceptance criteria](#acceptance-criteria) — The observable checks for completion.
- [References](#references) — Primary docs relevant to the implementation.
- [Deferred](#deferred) — Related work this step leaves out.

## Why

Step 1 makes the data contract checkable from code, but `completeness-audit` still cannot tell an operator that persisted data shapes and `DATA_CONTRACT.md` have drifted unless they know to run the dedicated tests. That is a gap because completeness audits already collect deterministic project-health findings in the local deterministic phase, and data-contract drift is the same class of problem: code is the source of truth, the persisted-shape documentation is stale, and the plan should not be considered complete until the drift is visible in the normal audit path.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — Extend `_DeterministicReport` with a data-contract drift bucket, call the step 1 detector from `_run_deterministic_checks`, include the bucket in deterministic counts, render it in `_render_grouped_report`, include it in `_render_completeness_json`, and pass any recommendation-shaped findings through `_persist_and_present_report`.
  - `plan_tool/cli/completeness_cmd.py` — Update any completeness blocking or finalization wiring that consumes `_DeterministicReport`, especially paths that compute `has_blocking_findings` or assemble the persisted recommendation union.
  - `plan_tool/completeness_report.py` — Teach report assembly about the new data-contract diagnostic only if the bucket needs disposition text outside the existing grouped report; keep saved sidecar persistence generic.
  - `plan_tool/review_persistence.py` — No schema change should be needed; edit only comments or docstrings if the implementation needs to clarify that adding more `Recommendation` instances does not change `SavedReview`.
  - `tests/cli/test_completeness_cmd.py` — Add phase-helper tests for collection, grouped markdown, JSON payload, blocking behavior, and persisted recommendation forwarding.
  - `tests/test_completeness_report.py` — Add report/persistence tests only for behavior that lands in `plan_tool/completeness_report.py`, such as disposition text or sidecar contents.

## Implementation

- **Foundational logic: data-contract drift recommendation aggregation.** Treat step 1 as the owner of contract discovery and drift detection. This step should call that code from the completeness deterministic phase, then report the returned drift findings without re-deriving dataclass fields or parsing `DATA_CONTRACT.md` in the CLI layer.

- **Use the deterministic phase as the entry point.** `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` already gathers local findings with no Claude call: `check_body_completeness`, `check_detail_coverage`, `check_files_coherence`, `check_lessons_coverage`, `collect_smell_findings`, and `assess_granularity`. Add data-contract drift there so it participates in the no-Claude deterministic checks and still works when the audit has no invoker. Under the current `completeness-audit --iterate` flow, this deterministic phase is reported after the up-front conceptual sample; do not claim token-saving preflight behavior unless a separate step changes that ordering.

- **Keep the producer single-sourced.** Import and call the step 1 API from `plan_tool/data_contract.py`; do not copy the logic from `tests/test_data_contract.py`. If step 1 exposes a registry plus a lower-level check helper, prefer the helper that returns structured drift records. If it only exposes registry primitives, add the smallest adapter in `plan_tool/cli/completeness_phases.py` needed to turn those records into completeness findings.

- **Use existing `Recommendation` behavior with a payload sidecar.** The new bucket should hold `plan_tool.review:Recommendation` objects with source `data-contract`, stable ids, and medium-or-higher severity for drift that should fail `--fail-on-findings`. Because `Recommendation` itself has no typed fields for contract target section, candidate fields, operations, or freshness fingerprints, persist the step 1 structured drift records in a sidecar-compatible payload map keyed by `Recommendation.id` or `Recommendation.anchor`. Keep the saved-review schema unchanged by storing this map in an existing extensibility location if one exists, or by writing a colocated data-contract payload file with the same saved-audit id; step 3 must read this payload before applying.

- **Extend `_DeterministicReport` conservatively.** Add the new bucket at the end with `field(default_factory=list)`, matching the existing `smell_recs` compatibility pattern in `plan_tool/cli/completeness_phases.py:_DeterministicReport`. This keeps test helpers such as `tests/cli/test_completeness_cmd.py:_empty_det` and partial constructors stable.

- **Render the drift in every completeness output.** Add a `### Data contract` section in `plan_tool/cli/completeness_phases.py:_render_grouped_report` that names the drift plainly and points readers at the affected contract section or field when the producer exposes that detail. Add the same bucket to `plan_tool/cli/completeness_phases.py:_render_completeness_json` under a stable key such as `data_contract`, including source, severity, id, and message fields rather than burying it in free-form text.

- **Make blocking status include the new bucket.** Update the completeness blocking path in `plan_tool/cli/completeness_cmd.py` so `--fail-on-findings` treats data-contract drift like other medium+ deterministic findings. Preserve the existing distinction that advisory smells in `_DeterministicReport.smell_recs` do not flip the exit code.

- **Persist recommendation-shaped drift without changing schema.** In `plan_tool/cli/completeness_phases.py:_persist_and_present_report`, include data-contract recommendations in the sidecar recommendation list if the bucket uses `Recommendation`, and persist the structured payload map needed by `data-contract-apply`. Keep `plan_tool/review_persistence.py:SavedReview` unchanged unless there is already a generic extension field; this is more instances of an already persisted record type plus a data-contract-specific payload artifact, not a new saved-review schema version.

- **Keep completeness-apply behavior narrow.** Data-contract drift should be reported and persisted for visibility, but this step should not invent an apply bridge that edits `DATA_CONTRACT.md`. If `completeness-apply` sees the saved finding, it should behave like other non-apply-eligible diagnostics unless an existing eligibility rule already covers it.

- **Avoid new whole-document contract checks here.** Step 1 owns section-aware contract drift detection. This step should not add a second Markdown parser or a looser substring check in `plan_tool/cli/completeness_phases.py`; duplicated checks will disagree and create false audit noise.

## Tests

- `tests/cli/test_completeness_cmd.py::TestRunDeterministicChecks::test_run_deterministic_checks_collects_data_contract_drift` — `_run_deterministic_checks` calls the step 1 detector and stores returned data-contract findings on `_DeterministicReport`.
- `tests/cli/test_completeness_cmd.py::TestRunDeterministicChecks::test_run_deterministic_checks_no_data_contract_drift_yields_empty_bucket` — a clean detector result leaves the new bucket empty and preserves existing deterministic counts.
- `tests/cli/test_completeness_cmd.py::TestRenderGroupedReport::test_grouped_report_renders_data_contract_drift` — `_render_grouped_report` includes a `### Data contract` section with the finding body and stable anchor/id.
- `tests/cli/test_completeness_cmd.py::TestRenderGroupedReport::test_grouped_report_no_issues_stays_clean_when_only_data_contract_bucket_empty` — the no-issues message still appears when all buckets, including data contract drift, are empty.
- `tests/cli/test_completeness_cmd.py::TestRenderCompletenessJson::test_json_payload_includes_data_contract_drift` — `_render_completeness_json` emits the new drift bucket in the machine-readable payload.
- `tests/cli/test_completeness_cmd.py::TestCompletenessBlocking::test_data_contract_drift_can_make_fail_on_findings_block` — `_completeness_has_blocking_findings` or `finalize_completeness_run` treats the new bucket as blocking for `--fail-on-findings`.
- `tests/cli/test_completeness_cmd.py::TestRenderCompletenessJson::test_persist_passes_data_contract_recommendations` — `_persist_and_present_report` includes data-contract recommendations in the saved sidecar union without dropping correctness or conceptual findings.
- `tests/cli/test_completeness_cmd.py::TestRenderCompletenessJson::test_persist_passes_data_contract_payloads` — `_persist_and_present_report` persists structured data-contract payloads keyed by the saved recommendation id so `data-contract-apply` does not infer edits from prose.
- `tests/test_completeness_report.py::test_write_report_persists_data_contract_recommendations_without_schema_change` — if report persistence is touched, `write_completeness_report` saves the new recommendations through the existing `SavedReview.recommendations` list.

### Test-creation order (feature step)

Add the `_DeterministicReport` and `_run_deterministic_checks` tests first, because they define the new bucket and prove the detector is reached. Add grouped report and JSON tests next, so the operator and machine-readable surfaces are pinned before persistence wiring. Add the persistence test last, only after the bucket uses `Recommendation` objects or an equivalent saved shape. The green-before-done gate is that every new test listed above passes, and the existing completeness-report and completeness-command tests still pass.

## Acceptance criteria

- `plan_tool/cli/completeness_phases.py:_run_deterministic_checks` returns a `_DeterministicReport` whose data-contract bucket contains the drift findings returned by the step 1 detector.
- `plan_tool/cli/completeness_phases.py:_render_grouped_report` prints a `### Data contract` section when that bucket is non-empty.
- `plan_tool/cli/completeness_phases.py:_render_completeness_json` includes data-contract drift in the `--json` payload under a stable key.
- `plan_tool/cli/completeness_cmd.py` includes medium+ data-contract drift in the completeness blocking verdict used by `--fail-on-findings`.
- `plan_tool/cli/completeness_phases.py:_persist_and_present_report` saves data-contract recommendations in the completeness JSON sidecar when sidecar writing is enabled.
- The saved audit or colocated payload artifact includes structured data-contract payloads keyed by recommendation id, including target section, operation, candidate fields, and freshness fingerprints.
- `plan_tool/review_persistence.py:SCHEMA_VERSION` is unchanged, and `plan_tool/review_persistence.py:SavedReview` gains no new persisted field for this step.
- The new tests in `tests/cli/test_completeness_cmd.py` pass.
- Any new `tests/test_completeness_report.py` test added for this step passes.

## References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Read for the field-introspection contract owned by step 1 and consumed indirectly here.
- [Python json](https://docs.python.org/3/library/json.html) — Read for the saved sidecar payload behavior reused by `plan_tool/review_persistence.py:save_review`.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Read for parametrized unit tests and monkeypatching the detector seam in completeness phase tests.

## Deferred

- `DATA_CONTRACT.md` content updates — Step 1 owns the contract documentation and its section-aware drift tests; this step only reports drift discovered by that subsystem.
- `tests/test_data_contract.py` changes — Step 1 owns the dedicated drift guard tests; this step tests only completeness-audit integration.
- Automatic fixes for data-contract drift — This step reports and persists findings but does not add an apply bridge that edits documentation.
- Additional persisted sidecars outside step 1's registry — If a future sidecar becomes part of the data-contract subsystem, add it to the registry in step 1's contract model before completeness reports it.
