> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Keep Contract Tests As The Durable Coverage Gate

## Summary

This step hardens the test suite so the data-contract subsystem from steps 1-6 stays enforced after the feature ships. The work is test-only across `tests/test_data_contract.py`, `tests/test_review.py`, `tests/test_create.py`, `tests/test_detail.py`, `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, `tests/cli/test_review_actions.py`, and `tests/cli/test_data_contract_cmd.py`. The key design decision is to keep durable coverage at the contract boundaries: registry-to-doc drift, structured apply payloads, freshness guards, conditional `## Input` sections, deterministic `data-contract` findings, completeness reporting, saved-audit replay, and dedicated data-contract apply routing. On green, changing persisted fields, contract-reference syntax, completeness buckets, or saved-walk routing without updating the matching contract tests should fail in CI.

## Table of Contents

- [Summary](#summary) — The coverage gate this step adds and the main test files it touches.
- [Why](#why) — Why the subsystem needs durable contract tests instead of only feature-path tests.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact test files this step changes.
- [Implementation](#implementation) — The intended coverage shape and the seams each test should pin.
- [Tests](#tests) — The test cases to add or adjust.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — A practical order for landing the tests with the implementation.
- [Acceptance criteria](#acceptance-criteria) — The observable gates for completion.
- [References](#references) — Primary docs useful while writing the tests.
- [Deferred](#deferred) — Related work this step does not take on.

## Why

Steps 1-6 add several linked contracts: a code-owned data-contract registry, `DATA_CONTRACT.md` drift reporting, structured saved-audit apply payloads, freshness guards, conditional `## Input` sections, and HEAD-backed validation of explicit contract references in those sections. Without a focused final test pass, those contracts can regress independently: the doc check can become broad substring matching again, `data-contract` findings can drop out of completeness JSON or saved sidecars, optional Input sections can become mandatory noise, plan/detail Input-reference findings can be sent to the wrong actuator, or saved replay can show a generic plan-edit apply option for a documentation repair. This step makes the tests the durable gate for the whole subsystem, with production behavior owned by the earlier dependent steps.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `tests/test_data_contract.py` — Replace or extend broad doc substring checks with registry-driven, section-aware checks from step 1; add direct detector coverage for step 6 `## Input` references, structured drift payloads, freshness fingerprints, and intentional exclusions.
  - `tests/test_review.py` — Add review-level coverage that `collect_deterministic_findings` emits stable `source="data-contract"` recommendations for stale `## Input` references, marks them as plan/detail targets, and stays quiet for valid references with anchors.
  - `tests/test_create.py` — Pin that generated bodies omit `## Input` for unrelated plans and can render/preserve it for contract-consuming plans from step 5.
  - `tests/test_detail.py` — Pin that detail prompt rendering and `parse_detail_response` treat `## Input` as optional/conditional from step 5.
  - `tests/test_completeness_report.py` — Add only report-assembly or persistence assertions that belong to `plan_tool/completeness_report.py`; leave phase wiring in the CLI test file.
  - `tests/cli/test_completeness_cmd.py` — Add completeness phase-helper coverage for `data-contract` collection, grouped markdown, JSON, blocking status, saved sidecar forwarding, and structured payload persistence.
  - `tests/cli/test_review_actions.py` — Add saved-walk action coverage that `source="data-contract"` is not dispatched through generic `apply_finding`, while command-local callbacks can make it actionable for `data-contract-apply`.
  - `tests/cli/test_data_contract_cmd.py` — Add focused command coverage proving the dedicated `data-contract-apply` callback requires structured payloads, checks freshness, updates `DATA_CONTRACT.md`, leaves `## Input` plan/detail findings non-applyable, and records the saved annotation.

## Implementation

- **Foundational logic: contract-boundary coverage gate.** Treat this step as test hardening, not another production feature step. The tests should prove the behavior produced by steps 1-6 is reachable through the public or near-public seams that future changes are likely to touch.

- **Keep production ownership with earlier steps.** Do not move registry logic, completeness wiring, or apply routing in this step. If a new test fails because `plan_tool/data_contract.py`, `plan_tool/review.py:collect_deterministic_findings`, `plan_tool/cli/completeness_phases.py:_run_deterministic_checks`, or `plan_tool/cli/review_actions.py:_build_review_action_fn` is missing behavior from steps 1-6, fix that in the owning step’s implementation before considering this gate green.

- **Strengthen `tests/test_data_contract.py` around the registry.** After step 1, this file should consume `plan_tool/data_contract.py` instead of owning a local `_PERSISTED_DATACLASSES` list. Keep dataclass field discovery tied to real fields, but assert the doc section for each registered contract contains its own persisted fields, aliases, schema constants, registered open-dict keys, and intentional exclusions. Include the step 6 detector cases here: valid references such as a registered persisted field with a matching code anchor, valid serialized aliases with anchors, valid registered context keys with anchors where applicable, stale fields, missing anchors, stale anchors, and ignored non-contract backticked prose.

- **Pin conditional Input section generation in `tests/test_create.py`.** Use existing anchors such as `tests/test_create.py:TestRenderPlanBody`, `tests/test_create.py:TestWriteNewPlanBody`, and the synthesis/key seams around `propose_body_sections`, `_parse_body_sections_json`, and `_canonical_body_section_keys`. The tests should fail if default creation starts adding `## Input` to unrelated plans, if contract-consuming seeds cannot render/preserve `## Input`, or if body-section synthesis treats optional `Input` as a required canonical key. Avoid duplicating every create wizard path unless the conditional rendering seam does not cover it.

- **Pin Input section parsing in `tests/test_detail.py`.** Add focused cases near `tests/test_detail.py:TestRenderDetailPrompt` and the `parse_detail_response` tests. The required behavior is: `render_detail_prompt` describes when to include `## Input` without listing it as required, `parse_detail_response` accepts and preserves a well-formed response containing `## Input`, and a response that omits `Input` still passes when all required sections are present. Use `plan_tool/detail.py:_REQUIRED_H2_TOKENS` and `plan_tool/detail.py:_REQUIRED_H2_DISPLAY` as orientation anchors for the unchanged required set.

- **Pin review recommendation conversion in `tests/test_review.py`.** Add tests beside the existing `collect_deterministic_findings` coverage. Assert stale explicit references in a plan-level `## Input` section and a pending step detail file’s `## Input` section produce `Recommendation` objects with `source="data-contract"`, stable ids, useful anchors or titles, plan/detail target metadata, and appropriate `step_id` values. Also assert valid references with matching code anchors produce no data-contract recommendations and that `step_filter` does not leak unrelated detail-file findings into a filtered review.

- **Pin completeness phase surfaces in `tests/cli/test_completeness_cmd.py`.** Use the existing phase-helper classes as the coverage map: `TestRunDeterministicChecks`, `TestRenderGroupedReport`, and `TestRenderCompletenessJson`, including the current `_persist_and_present_report` coverage under `TestRenderCompletenessJson`. The same `data-contract` recommendation should be collected into the deterministic report, rendered in grouped markdown, emitted in `checks` JSON, count as blocking at medium-or-higher severity, and be forwarded into saved completeness sidecars with its structured payload when it targets `DATA_CONTRACT.md`. If `_DeterministicReport` gains a `data_contract_recs` bucket from step 2, keep it last with a default factory so existing `_empty_det()` helpers and partial constructors stay valid.

- **Pin saved apply routing in `tests/cli/test_review_actions.py`.** Add focused tests around `_build_review_action_fn` and the command-local callback used by `data-contract-apply`. The generic action builder must not call `apply_finding` for `source="data-contract"`, even when saved walks carry the source for ordering and annotation. The dedicated data-contract command should prove its own callback can update `DATA_CONTRACT.md` only when the payload target is `DATA_CONTRACT.md`, and should leave `target="plan-detail"` Input-reference findings non-applyable. This preserves the step 4 rule that data-contract applyability is caller-owned and actuator-specific, not global.

- **Use `tests/test_completeness_report.py` only for report-owned behavior.** If the implementation adds disposition prose or saved-report assembly behavior in `plan_tool/completeness_report.py`, add a focused test there. Do not duplicate CLI phase tests in this file; `tests/cli/test_completeness_cmd.py` owns collection, JSON, blocking, and persistence forwarding.

- **Keep test data small and direct.** Prefer small in-memory plans and temporary detail files over end-to-end CLI runs. Use monkeypatching at the domain seam already used in these files, such as patching `plan_tool.review.collect_deterministic_findings` for completeness phase tests when the test is about phase routing rather than detector internals.

## Tests

- `tests/test_data_contract.py:test_registered_persisted_fields_are_documented_in_their_sections` — asserts every registered persisted field is documented in the correct `DATA_CONTRACT.md` section, not merely somewhere in the file.
- `tests/test_data_contract.py:test_saved_review_alias_and_in_memory_field_contract_documented` — asserts `SavedReview.schema_version` maps to the serialized `version` key and `SavedReview.path` is documented as in-memory only.
- `tests/test_data_contract.py:test_plan_manifest_contract_is_documented` — asserts the non-dataclass plan manifest contract from step 1 is covered.
- `tests/test_data_contract.py:test_intentional_exclusion_requires_rationale` — asserts intentionally undocumented serialized fields are explicit registry entries with a rationale and mirrored documentation.
- `tests/test_data_contract.py:test_data_contract_drift_record_contains_apply_payload` — asserts contract-document drift records include operation, target section, candidate field metadata, and freshness fingerprints.
- `tests/test_data_contract.py:test_input_contract_reference_detector_accepts_registered_references_with_anchors` — asserts valid persisted fields, aliases, and registered context keys produce no issues when their `## Input` section also names the matching code-location anchor.
- `tests/test_data_contract.py:test_input_contract_reference_detector_flags_stale_fields` — asserts stale explicit references produce neutral detector issues.
- `tests/test_data_contract.py:test_input_contract_reference_detector_flags_missing_or_stale_anchors` — asserts missing or stale code-location anchors produce neutral detector issues.
- `tests/test_data_contract.py:test_input_contract_reference_detector_ignores_non_contract_backticks` — asserts commands, paths, flags, and unknown owners are ignored.
- `tests/test_create.py:test_default_plan_body_omits_input_section` — asserts unrelated plan creation does not render `## Input`.
- `tests/test_create.py:test_contract_consuming_plan_body_renders_input_section` — asserts a contract-consuming seed or synthesis result can render/preserve `## Input`.
- `tests/test_create.py:test_body_section_synthesis_does_not_require_input_key` — asserts body-section synthesis keeps `Input` out of the required canonical key set.
- `tests/test_detail.py:test_render_detail_prompt_documents_conditional_input_section` — asserts `render_detail_prompt` describes conditional `## Input` guidance without adding it to the required output structure.
- `tests/test_detail.py:test_parse_detail_response_accepts_optional_input_section` — asserts a complete response with `## Input` parses successfully and preserves the section.
- `tests/test_detail.py:test_parse_detail_response_accepts_missing_input` — asserts a response with all required H2s and no `Input` parses without stubbing.
- `tests/test_review.py:test_collect_deterministic_findings_reports_plan_input_contract_drift` — asserts stale plan-body Input references become `source="data-contract"` recommendations.
- `tests/test_review.py:test_collect_deterministic_findings_reports_detail_input_contract_drift` — asserts stale detail-file Input references become step-scoped `data-contract` recommendations.
- `tests/test_review.py:test_collect_deterministic_findings_ignores_valid_input_contract_references` — asserts valid references with matching code-location anchors stay quiet.
- `tests/test_review.py:test_input_contract_findings_have_plan_detail_target` — asserts stale `## Input` findings carry non-applyable plan/detail target metadata.
- `tests/test_review.py:test_collect_deterministic_findings_filters_detail_input_contract_by_step` — asserts `step_filter` keeps unrelated detail Input findings out.
- `tests/cli/test_completeness_cmd.py:test_run_deterministic_checks_collects_data_contract_recs` — asserts data-contract recommendations enter the deterministic report.
- `tests/cli/test_completeness_cmd.py:test_grouped_report_renders_data_contract_section` — asserts grouped markdown names data-contract drift.
- `tests/cli/test_completeness_cmd.py:test_json_payload_includes_data_contract_group` — asserts `--json` includes data-contract findings with id, source, severity, title, body, target, and payload metadata where applicable.
- `tests/cli/test_completeness_cmd.py:test_data_contract_medium_findings_are_blocking` — asserts medium-or-higher data-contract findings affect `has_blocking_findings` and `--fail-on-findings`.
- `tests/cli/test_completeness_cmd.py:test_persist_and_present_report_forwards_data_contract_recs` — asserts saved completeness sidecars include the original data-contract recommendations.
- `tests/cli/test_completeness_cmd.py:test_persist_and_present_report_forwards_data_contract_payloads` — asserts saved or colocated payload artifacts include structured `DATA_CONTRACT.md` payloads and preserve plan/detail target metadata for stale `## Input` findings.
- `tests/cli/test_review_actions.py:test_data_contract_source_does_not_dispatch_apply_finding` — asserts `_build_review_action_fn` does not route a data-contract finding through generic `apply_finding`.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_uses_document_callback` — asserts the dedicated data-contract apply command updates `DATA_CONTRACT.md` through its command-local callback.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_requires_structured_payload` — asserts a saved recommendation without a payload is blocked rather than inferred from prose.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_refuses_stale_fingerprint` — asserts changed code/registry or `DATA_CONTRACT.md` fingerprints block mutation and ask for a new audit.
- `tests/cli/test_data_contract_cmd.py:test_data_contract_apply_does_not_apply_input_reference_findings` — asserts `target="plan-detail"` stale `## Input` recommendations are reported but not sent to the document callback.
- `tests/cli/test_review_actions.py:test_data_contract_source_defaults_to_terminal_noop` — asserts the same source is not globally applyable without `extra_apply_sources`.
- `tests/test_completeness_report.py:test_report_mentions_data_contract_disposition` — add only if `plan_tool/completeness_report.py` owns new data-contract disposition text.

### Test-creation order (feature step)

1. Add the registry and detector tests in `tests/test_data_contract.py`; these are the lowest-level contract and should fail before steps 1 and 6 are complete.
2. Add the create/detail conditional Input section tests in `tests/test_create.py` and `tests/test_detail.py`; these pin step 5 before higher-level review tests rely on `## Input`.
3. Add the `collect_deterministic_findings` tests in `tests/test_review.py`; these prove step 6 converts neutral issues into saved recommendations.
4. Add the completeness phase tests in `tests/cli/test_completeness_cmd.py`; these prove step 2 surfaces the same recommendations through reports, JSON, blocking, and persistence.
5. Add the saved apply routing tests in `tests/cli/test_review_actions.py`; these prove step 4 keeps data-contract applyability caller-owned.
6. Add `tests/test_completeness_report.py` coverage only if report-owned data-contract disposition text exists.

Every new or changed test in these files must be green before this step is finished. Do not mark this step done with expected failures or tests skipped because an upstream step is incomplete.

## Acceptance criteria

- `tests/test_data_contract.py` no longer relies on a local `_PERSISTED_DATACLASSES` list when step 1’s registry exists.
- `tests/test_data_contract.py` fails when a registered persisted field is documented only in the wrong `DATA_CONTRACT.md` section.
- `tests/test_data_contract.py` covers valid and stale explicit `## Input` contract references, missing/stale anchors, structured drift payloads, and intentional exclusions without flagging ordinary backticked prose.
- `tests/test_create.py` fails if default creation makes `Input` mandatory or contract-consuming creation cannot render/preserve `Input`.
- `tests/test_detail.py` fails if `plan_tool/detail.py:parse_detail_response` stops accepting optional `## Input` or starts requiring it for unrelated details.
- `tests/test_review.py` proves stale plan-body and detail-file `## Input` references produce stable `source="data-contract"` recommendations with plan/detail target metadata through `collect_deterministic_findings`.
- `tests/cli/test_completeness_cmd.py` proves data-contract findings appear in grouped markdown, `--json`, blocking status, saved completeness sidecars, and structured payload persistence.
- `tests/cli/test_review_actions.py` proves data-contract findings do not dispatch through generic `apply_finding`, while the dedicated data-contract command owns actual document edits only for fresh `DATA_CONTRACT.md` payloads.
- Running `pytest tests/test_data_contract.py tests/test_review.py tests/test_create.py tests/test_detail.py tests/test_completeness_report.py tests/cli/test_completeness_cmd.py tests/cli/test_review_actions.py tests/cli/test_data_contract_cmd.py` passes.

## References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Use for field introspection expectations in the registry-driven contract tests.
- [Python json](https://docs.python.org/3/library/json.html) — Use for saved sidecar and JSON payload assertions.
- [CommonMark Specification](https://spec.commonmark.org/) — Use for H2 section expectations in plan/detail/Input markdown tests.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Use for fixtures, monkeypatching, parametrization, and assertion style in the coverage gate.

## Deferred

- Production behavior changes — Owned by steps 1-6; this step should expose missing behavior with tests, not redesign the subsystem.
- New CLI commands or help snapshots — Covered by step 3’s command-surface work, not this coverage-gate step.
- Broad end-to-end CLI duplication — Keep this step focused on durable unit and phase-helper tests; existing CLI integration tests can remain the end-to-end smoke layer.
- Additional persisted sidecars outside the data-contract plan scope — Do not add new contract families here unless a prior step registered them as part of the subsystem.
