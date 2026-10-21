> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Check Input Contract Field References Against HEAD

## Summary

This step adds deterministic validation for contract field and code-location references written in optional `## Input` sections. The main work is in `plan_tool/data_contract.py`, with integration through `plan_tool/review.py:collect_deterministic_findings` and `plan_tool/cli/completeness_phases.py:_run_deterministic_checks`. The key design decision is to validate only explicit data-contract references against the code-owned registry from step 1, not every backticked word in prose. On green, a plan or detail `## Input` section that names a stale persisted field such as `SavedReview.missing_field` or a stale code anchor such as `plan_tool/review_persistence.py:MissingSymbol` produces a `data-contract` recommendation with a plan/detail target, shows in completeness output, participates in blocking behavior, and is explicitly not routed to the `DATA_CONTRACT.md` apply actuator.

## Table of Contents

- [Summary](#summary) — The behavior this step adds and the main files it touches.
- [Why](#why) — Why `## Input` needs a HEAD-backed contract check.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped files and what each owns.
- [Implementation](#implementation) — The validation rule, integration points, and constraints.
- [Tests](#tests) — The focused regression cases for the new check.
- [Test-creation order (feature step)](#test-creation-order-feature-step) — The order to add tests while building.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary docs relevant to this step.
- [Deferred](#deferred) — Related work left outside this step.

## Why

Step 5 makes `## Input` a conditional place to name existing contracts a plan or step consumes. When the section is present, it can still cite fields or code locations that do not exist in the current code. That is exactly the failure the data-contract subsystem is meant to prevent: a later implementer follows a detail file that says to read `SavedReview.foo`, `DecisionEvent.context.bar`, or `plan_tool/review_persistence.py:SavedReview.missing_symbol`, while HEAD exposes different persisted fields, registered context keys, or symbols. This step closes that gap by checking explicit Input-section contract references against the same code-owned registry and conservative code-location checks that drive the data-contract drift checks.

## Files (creates vs edits)

- **New files:**
  - None. `plan_tool/data_contract.py` is expected from step 1; if it is absent in the working tree, land step 1 first rather than creating a parallel registry module.

- **Existing files (edits only):**
  - `plan_tool/data_contract.py` — Add the Input-section field-reference detector and any small issue dataclass/helper it needs, using the step 1 registry as the source of valid contract owners, fields, aliases, and registered open-dict keys.
  - `plan_tool/review.py` — Convert Input contract reference issues into `Recommendation` objects with `source="data-contract"` and stable ids, then include them in deterministic recommendation collection and review/completeness report assembly without changing persisted recommendation schema.
  - `plan_tool/cli/completeness_phases.py` — Feed the new `data-contract` recommendations into the existing step 2 data-contract completeness bucket/source in `_run_deterministic_checks`, `_render_grouped_report`, `_render_completeness_json`, and `_persist_and_present_report` forwarding.
  - `tests/test_data_contract.py` — Add direct tests for the detector: valid fields, serialized aliases, registered context keys, stale fields, and ignored non-contract prose.
  - `tests/test_review.py` — Add review-level tests that deterministic collection turns stale Input references into stable `data-contract` recommendations and keeps valid references quiet.
  - `tests/cli/test_completeness_cmd.py` — Add phase-helper tests that Input contract findings reuse the existing data-contract bucket/source, render, emit in JSON, remain blocking at medium severity through that bucket, and forward into saved completeness sidecars.

## Implementation

- **Foundational logic: Input contract reference validation.** Add a detector in `plan_tool/data_contract.py` that scans only present `## Input` sections and validates explicit references to registered data-contract shapes and code locations against HEAD. The detector should answer: “does this Input section name a contract owner and field/key that the current registry says exists, and does each required code-location anchor still resolve?”

- **Use the registry from step 1 as the source of truth.** Derive persisted dataclass fields with `dataclasses.fields`, honor registered serialized aliases such as `SavedReview.schema_version` persisting as `version`, and honor first-class open-bag keys registered for variants such as telemetry context keys. Do not read `DATA_CONTRACT.md` for this check; this step validates plan/detail instructions against code, not documentation against code.

- **Keep the field reference grammar conservative.** One good shape is to validate backticked tokens that look like registered contract references, such as `SavedReview.recommendations`, `SavedReview.version`, `Recommendation.source`, or a registered context key path. Ignore ordinary prose, commands, and unknown owner names that are not registered contract owners. False negatives are acceptable here; false positives would make `## Input` too noisy to use.

- **Require resolvable code-location anchors for explicit contract fields.** Step 5's `Input` guidance should ask authors to name code locations such as `plan_tool/review_persistence.py:SavedReview`, `plan_tool/review_persistence.py:save_review`, or `plan_tool/review.py:Recommendation.source` when they cite a registered contract field. This step should validate those explicit anchors with a conservative repo-path and symbol check: the path must exist, Python symbols should resolve via `ast` for classes/functions/module-level assignments where practical, and dataclass field anchors should be checked through the registry. A bare field token such as `SavedReview.recommendations` is valid only in test fixtures that also include a corresponding code-location anchor in the same `## Input` section; otherwise report a medium data-contract recommendation asking for the missing HEAD anchor.

- **Scan the right authoring surfaces.** Cover the plan-level `## Input` section and each pending step detail file’s `## Input` section when present. For detail files, reuse the existing section parser used by `plan_tool/review.py:check_detail_body_completeness` when possible, most likely through a body-local import from `plan_tool.detail:parse_detail_file_sections`. Missing `## Input` is normal for plans/steps that do not consume existing contracts; this step should not emit a missing-section finding.

- **Return neutral issue records from `plan_tool/data_contract.py`.** Prefer a small detector result such as an `InputContractReferenceIssue` carrying location, owner, field/key or code anchor, detail path or plan path, and a plain reason. Let `plan_tool/review.py` convert those issues into `Recommendation` objects using `plan_tool/review.py:_make_rec_id`, so the registry module does not need to own review routing or saved-review semantics.

- **Avoid import cycles.** `plan_tool/data_contract.py` may import persisted dataclass owners such as `plan_tool.review:Recommendation` and `plan_tool.review:Redirect` as part of the step 1 registry. Any `plan_tool/review.py` use of `plan_tool.data_contract` should therefore be body-local inside detector wiring functions, matching the existing body-local imports around `check_detail_body_completeness` and `_run_deterministic_checks`.

- **Thread the new findings through review ordering.** In `plan_tool/review.py:collect_deterministic_findings`, run the Input contract detector with the other synchronous no-Claude primitives. In `plan_tool/review.py:extract_recommendations`, place `data-contract` findings with the plan/detail completeness findings, after required-section checks and before Claude findings. Preserve `step_filter` behavior: plan-level Input findings appear only in full-plan runs, while step detail findings respect the selected step.

- **Use `source="data-contract"` with a plan/detail target.** Steps 2 through 4 already make this source visible in completeness saved-audit workflows, but Input-reference findings are not `DATA_CONTRACT.md` edits. Tag their structured payload or recommendation metadata with `target="plan-detail"` or equivalent so `data-contract-apply` and generic `completeness-apply` do not route them to the contract-document actuator. Do not add a new source token unless the earlier steps chose a different canonical data-contract source; if they did, use that existing source and keep the target metadata stable across all data-contract findings.

- **Keep persistence generic.** Adding more `Recommendation` instances does not change `SavedReview`, `Annotation`, or sidecar JSON schema. Do not add fields to `Recommendation`, `SavedReview`, or `DecisionEvent` for this step.

- **Reuse the existing data-contract completeness bucket.** Step 2 owns the data-contract completeness bucket/source and the blocking integration that lives partly in `plan_tool/cli/completeness_phases.py`. This step must extend that existing bucket with Input contract reference recommendations instead of appending a separate `_DeterministicReport` bucket. In `_run_deterministic_checks`, include the detector result after detail/body checks and before advisory `smell_recs`. Unlike smells, stale Input contract references are medium-severity data-contract drift and should remain blocking by flowing through the existing data-contract bucket/source.

- **Render every completeness surface.** In `plan_tool/cli/completeness_phases.py:_render_grouped_report`, reuse the `### Data contract` or equivalent section so it names the stale Input references and their locations. In `_render_completeness_json`, extend the existing data-contract `checks` entry with enough fields for headless callers to identify the bad reference and its `target="plan-detail"` metadata. In `_persist_and_present_report`, forward the original `Recommendation` objects into the saved sidecar alongside the existing data-contract/completeness recommendations, preserving ids, source, body, suggested action, and non-applyable target metadata.

- **Do not move section ownership into this step.** Step 5 owns making `Input` a conditional recognized section in `plan_tool/detail.py` and plan-body creation. This step should consume the section if present and report stale references; it should not add or change the required-section parser contract outside the scoped review/data-contract surfaces.

## Tests

- `tests/test_data_contract.py::test_input_contract_reference_accepts_registered_dataclass_field_with_anchor` — `SavedReview.recommendations` or an equivalent registered persisted field is valid when the same `## Input` section includes a matching code-location anchor.
- `tests/test_data_contract.py::test_input_contract_reference_accepts_serialized_alias_with_anchor` — a registered alias such as `SavedReview.version` is valid when the registry maps it to the underlying dataclass field and the section includes a matching code-location anchor.
- `tests/test_data_contract.py::test_input_contract_reference_flags_unknown_field` — a token like `SavedReview.not_a_field` produces one issue with the correct owner, field, and location.
- `tests/test_data_contract.py::test_input_contract_reference_requires_code_location_anchor` — an Input section that names a contract field without a corresponding HEAD code-location anchor produces one issue.
- `tests/test_data_contract.py::test_input_contract_reference_accepts_valid_code_location_anchor` — a token like `plan_tool/review_persistence.py:SavedReview` or `plan_tool/review.py:Recommendation.source` resolves cleanly.
- `tests/test_data_contract.py::test_input_contract_reference_flags_stale_code_location_anchor` — a token like `plan_tool/review_persistence.py:MissingSymbol` produces one issue with the stale anchor.
- `tests/test_data_contract.py::test_input_contract_reference_accepts_registered_context_key` — registered open-bag keys such as telemetry context keys are valid when named in the supported reference form.
- `tests/test_data_contract.py::test_input_contract_reference_ignores_non_contract_backticks` — commands, paths, and unregistered owner names in `## Input` do not create findings.
- `tests/test_data_contract.py::test_missing_input_section_has_no_issue` — a plan or detail without `## Input` produces no data-contract issue from this detector.
- `tests/test_review.py::test_collect_deterministic_findings_reports_stale_input_contract_reference` — review deterministic collection converts a stale detail Input reference into a `Recommendation` with `source="data-contract"` and a stable id.
- `tests/test_review.py::test_input_contract_recommendation_has_plan_detail_target` — stale Input reference recommendations carry target metadata that prevents `data-contract-apply` from editing `DATA_CONTRACT.md`.
- `tests/test_review.py::test_collect_deterministic_findings_respects_step_filter_for_input_contract_references` — a single-step review reports only that step’s detail Input reference and omits other step findings.
- `tests/cli/test_completeness_cmd.py::test_run_deterministic_checks_collects_input_contract_findings` — `_run_deterministic_checks` places detector results in the existing data-contract bucket.
- `tests/cli/test_completeness_cmd.py::test_grouped_report_renders_input_contract_findings` — `_render_grouped_report` shows the data-contract section and the stale field reference.
- `tests/cli/test_completeness_cmd.py::test_json_payload_includes_input_contract_findings` — `_render_completeness_json` extends the existing data-contract `checks` entry with stable fields.
- `tests/cli/test_completeness_cmd.py::test_input_contract_findings_are_blocking` — medium+ data-contract findings set `has_blocking_findings` when the orchestrator computes the blocking verdict.
- `tests/cli/test_completeness_cmd.py::test_persist_report_forwards_input_contract_recommendations` — `_persist_and_present_report` saves the `data-contract` recommendations for visibility while preserving their non-applyable plan/detail target metadata.

### Test-creation order (feature step)

1. Add direct detector tests in `tests/test_data_contract.py` for valid fields, aliases, stale fields, valid/stale code anchors, missing anchors, context keys, absent `Input` sections, and ignored prose.
2. Add `tests/test_review.py` coverage proving stale Input references become `source="data-contract"` recommendations and that `step_filter` narrows per-step detail findings.
3. Add `tests/cli/test_completeness_cmd.py` collection and report tests for `_run_deterministic_checks`, `_render_grouped_report`, and `_render_completeness_json`.
4. Add the blocking and persistence-forwarding completeness tests after the existing data-contract bucket accepts Input contract findings.
5. Green-before-done gate: every new test above must pass, and the existing `tests/test_data_contract.py`, `tests/test_review.py`, and `tests/cli/test_completeness_cmd.py` suites must stay green.

## Acceptance criteria

- `plan_tool/data_contract.py` exposes a deterministic Input contract reference check that validates explicit registered contract field/key references and required code-location anchors against the current code-owned registry and HEAD.
- A plan-level `## Input` reference to a valid registered field plus a matching code-location anchor produces no issue.
- A detail-file `## Input` reference to a valid registered alias plus a matching code-location anchor produces no issue.
- A stale registered-owner reference such as `SavedReview.not_a_field` produces a medium `Recommendation` with `source="data-contract"`.
- A stale code-location anchor such as `plan_tool/review_persistence.py:MissingSymbol` produces a medium `Recommendation` with `source="data-contract"`.
- An absent `## Input` section produces no issue from this detector.
- Non-contract backticked text in `## Input` does not produce a data-contract finding.
- `plan_tool/review.py:collect_deterministic_findings` includes stale Input contract references in its returned recommendations without invoking Claude.
- `plan_tool/cli/completeness_phases.py:_render_grouped_report` renders stale Input contract references in a data-contract section.
- `plan_tool/cli/completeness_phases.py:_render_completeness_json` includes stale Input contract references in the `checks` payload.
- Completeness blocking logic treats medium+ Input contract reference findings as blocking, unlike advisory `smell_recs`.
- Saved completeness sidecars include the original `data-contract` recommendations and their plan/detail target metadata for visibility, but the apply path from steps 3 and 4 does not route stale `## Input` references to the `DATA_CONTRACT.md` actuator.

## References

- [Python dataclasses](https://docs.python.org/3/library/dataclasses.html) — Use for HEAD-backed persisted field discovery from registered dataclasses.
- [Python ast](https://docs.python.org/3/library/ast.html) — Use only if the detector needs static parsing for registered constants or key declarations that are not available through dataclass introspection.
- [CommonMark Specification](https://spec.commonmark.org/) — Use for deterministic Markdown section handling when scanning `## Input` bodies.
- [pytest Documentation](https://docs.pytest.org/en/stable/) — Use for focused unit tests and assertion patterns around detector issues and CLI report payloads.

## Deferred

- `DATA_CONTRACT.md` prose updates — this step checks plan/detail Input references against code; documentation wording changes belong to the earlier registry/doc-drift steps unless this detector exposes a missing registered contract.
- Broad code-symbol validation in `## Input` — checking arbitrary function, class, module, or CLI references would need a separate symbol-reference subsystem and different false-positive rules.
- Runtime enforcement while applying findings — steps 3 and 4 own saved-audit replay and apply routing; this step only produces and forwards `data-contract` recommendations.
- Additional persisted sidecars outside the step 1 registry — objects such as future grounding sidecars should be added by a plan step that explicitly expands the data-contract registry scope.
