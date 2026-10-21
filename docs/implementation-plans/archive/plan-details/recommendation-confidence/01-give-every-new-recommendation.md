> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Give every Recommendation a conservative confidence without losing legacy evidence

## Summary

Add an additive confidence field to `Recommendation` that gives every newly created finding a conservative `limited` value by default without changing legacy saved or cached findings into false certainty. Mark only the direct file-state, dependency-graph, and data-contract drift predicates as `supported` in `plan_tool/review.py` and `plan_tool/cli/completeness_phases.py`. Keep granularity, model-derived, cached, and source-name-only findings limited. On green, new findings are classified while absent or null persisted values remain unknown and invalid values fail before a reader.

## Table of Contents

- [Summary](#summary) — The step’s outcome and key design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why evidence support needs its own finding field.
- [Input](#input) — The existing finding and detector contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test changes.
- [Implementation](#implementation) — Required classification behavior and boundaries.
- [Tests](#tests) — Focused coverage and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the additive field contract.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Later work deliberately left outside this step.

## Why

`plan_tool/review.py:Recommendation` currently carries severity but not the strength of evidence behind a finding. Deterministic findings can be directly checked, while heuristics, structural advice, and model output cannot earn the same claim merely by sharing a source name or severity. A conservative default makes the distinction complete for new producers without requiring every existing constructor to opt in.

## Input

- **Finding shape:** `plan_tool/review.py:Recommendation` is constructed across review, completeness, granularity, and model-backed paths. Its existing identity fields and defaulted metadata must remain compatible with current constructor calls and `dataclasses.replace`.
- **Direct predicates:** `plan_tool/review.py:_file_check_recommendation`, `plan_tool/review.py:_dep_recommendation`, and `plan_tool/cli/completeness_phases.py:_data_contract_rec_for_record` have directly checked inputs and are the only supported producers in this step.
- **Source-name collision:** `plan_tool/review.py:_input_contract_reference_recommendation` also emits `source="data-contract"`, but it must remain limited. A source label alone is not enough evidence to classify a finding as supported.
- **Legacy records:** `plan_tool/review_persistence.py:_load_recommendations` and `plan_tool/purity_cache.py:_entry_from_json` currently reconstruct raw mappings through `Recommendation(**raw)`. This step changes both boundaries before the defaulted field can reinterpret an absent historical value.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Add the defaulted confidence field to `Recommendation`; explicitly mark direct file-check and dependency recommendations as supported while leaving input-contract references and all other producers on the default.
  - `plan_tool/granularity.py` — Keep `_split_rec`, `_merge_rec`, and `parse_mixed_step_findings` on the limited default for deterministic and model-judged structural advice.
  - `plan_tool/cli/completeness_phases.py` — Mark `_data_contract_rec_for_record` as supported and ensure the purity reuse path around `_grade_purity_cache_miss` preserves a finding’s confidence.
  - `plan_tool/review_persistence.py` — Normalize and validate persisted confidence before constructing a `Recommendation`; retain normalized unknown through annotation rewrites.
  - `plan_tool/purity_cache.py` — Apply the same accepted-value rule to cached findings while retaining its malformed-cache miss-and-recheck behavior.
  - `DATA_CONTRACT.md` — Document the field, fresh and persisted states, legacy handling, rewrite-to-null behavior, and distinct sidecar/cache failure results.
  - `tests/test_review.py` — Cover the default, direct review predicates, source-name collision, and metadata-only behavior.
  - `tests/test_granularity.py` — Cover limited confidence for deterministic split/merge and MIXED-STEP findings.
  - `tests/cli/test_completeness_cmd.py` — Cover supported data-contract drift and confidence preservation through the completeness purity path.
  - `tests/test_review_persistence.py` — Cover valid, legacy, null, and invalid sidecar values.
  - `tests/test_purity_cache.py` — Cover valid, legacy, and invalid cached values.
  - `tests/test_data_contract.py` — Keep the discovered `Recommendation` field set and the complete persisted contract in sync.

## Implementation

- **Make confidence additive and conservative.** Extend `plan_tool/review.py:Recommendation` with a defaulted confidence field. Fresh construction must produce `limited`; reserve `None` for the legacy representation this step loads and normalizes.

- **Use only the plan’s named direct predicates for `supported`.** Set `confidence="supported"` in:
  - `plan_tool/review.py:_file_check_recommendation` for every emitted file-state finding.
  - `plan_tool/review.py:_dep_recommendation` for dependency findings.
  - `plan_tool/cli/completeness_phases.py:_data_contract_rec_for_record` for code-registry versus `DATA_CONTRACT.md` drift.

- **Do not infer confidence from metadata.** `plan_tool/review.py:_input_contract_reference_recommendation` must stay limited even though it uses the `data-contract` source. Do not add a source-based classifier, anchor-based classifier, or model self-scoring path.

- **Keep structural advice limited.** `plan_tool/granularity.py:assess_granularity`, `_split_rec`, `_merge_rec`, and `parse_mixed_step_findings` may be deterministic or model-judged, but they are advisory structural signals. Let the new default classify them as limited rather than adding a special override.

- **Preserve copied findings.** `plan_tool/cli/completeness_phases.py:_grade_purity_cache_miss` uses `dataclasses.replace` to add purity provenance. It must retain the incoming confidence while its separately created reuse advisory receives the fresh limited default.

- **Normalize persisted confidence before construction.** At both `plan_tool/review_persistence.py:_load_recommendations` and `plan_tool/purity_cache.py:_entry_from_json`, accept only `supported`, `limited`, JSON `null`, or an absent key. Map absent and null to `None` before constructing `Recommendation`; an invalid sidecar raises `ReviewLoadError`, while invalid cache content takes the established empty-cache path. Do not import one loader into the other.

- **Persist the normalized state and contract atomically.** Keep sidecar annotation rewrites and purity-cache writes using the dataclass value, so an unknown writes as JSON `null`. Update `DATA_CONTRACT.md` and its field-coverage tests in this step with the fresh vocabulary, legacy unknown, rewrite-to-null rule, and the distinct sidecar/cache failure behavior.

- **Preserve existing finding behavior.** Do not alter `_make_rec_id`, severity assignment, recommendation ordering in `extract_recommendations`, apply eligibility, blocking checks, or convergence decisions. Confidence is metadata only in this step.

- **Leave display to the next step.** Do not add reader-facing confidence labels in this step. The next step consumes only normalized stored values and cannot repair a loader that already converted unknown into limited.

## Tests

### Tests for this step

- `test_recommendation_defaults_to_limited` — A newly constructed `Recommendation` has `confidence == "limited"` without changing its existing required arguments.
- `test_created_missing_on_done_step_flagged`, `test_missing_parent_emits_medium_severity`, and `test_new_on_done_emits_medium_severity` — Emitted branches from `plan_tool/review.py:_file_check_recommendation` are supported and retain their current ID, severity, and file-path behavior.
- `test_blocked_dep_high` and `test_unknown_dep_critical` — Blocked and unknown dependency findings from `plan_tool/review.py:_dep_recommendation` are supported while retaining their current severities.
- `test_collect_deterministic_findings_reports_stale_input_contract_reference` — `plan_tool/review.py:_input_contract_reference_recommendation` stays limited despite using the same source string as data-contract drift.
- `test_confidence_is_metadata_only_for_finding_identity_and_order` — Adding confidence does not change recommendation IDs, severity, or the selected finding order.
- `test_rec_shape_and_sources` and `test_mixed_block_yields_split_finding` (`tests/test_granularity.py`) — Split, merge, and MIXED-STEP findings from `plan_tool/granularity.py` remain limited and retain their advisory/apply-eligibility behavior.
- `test_data_contract_drift_recommendation_is_supported` — `plan_tool/cli/completeness_phases.py:_data_contract_rec_for_record` emits supported findings for verified contract drift.
- `test_audit_miss_below_floor_reuses_verdict_no_claude` — The purity reuse path (`plan_tool/cli/completeness_phases.py:_grade_purity_cache_miss`) retains the reused finding’s confidence and creates its advisory with limited confidence.
- `test_recommendation_confidence_contract_documented` (`tests/test_data_contract.py`) — The persisted Recommendation table names the new field in the same change that introduces it.
- `test_saved_recommendation_confidence_round_trips` (`tests/test_review_persistence.py`) — Saved `supported` and `limited` values load unchanged.
- `test_legacy_sidecar_confidence_loads_unknown_and_rewrite_writes_null` (`tests/test_review_persistence.py`) — An absent key loads as `None`, then an annotation rewrite persists JSON `null`.
- `test_sidecar_null_confidence_remains_unknown` and `test_load_rejects_invalid_recommendation_confidence` (`tests/test_review_persistence.py`) — Explicit null remains unknown and invalid values fail before readers.
- `test_findings_recommendation_fields_round_trip`, `test_legacy_cached_confidence_loads_unknown_and_rewrite_writes_null`, and `test_invalid_cached_confidence_degrades_to_empty_cache` (`tests/test_purity_cache.py`) — Cache parsing preserves valid values, preserves unknown, and turns invalid content into a safe miss.
- `test_recommendation_confidence_contract_documented` and `test_purity_cache_confidence_contract_documented` (`tests/test_data_contract.py`) — The published contract covers the vocabulary, unknown state, and failure behavior.

Green-before-done gate: all tests above pass, along with `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- Fresh `Recommendation` instances receive `limited` confidence by default.
- Every emitted file-check and dependency finding is `supported`.
- Every data-contract drift finding from `plan_tool/cli/completeness_phases.py:_data_contract_rec_for_record` is `supported`.
- Input-contract reference findings, granularity findings, model-derived findings, and purity reuse advisories remain `limited`.
- Purity provenance replacement preserves the confidence already attached to a finding.
- Saved and cached `supported` or `limited` values round-trip unchanged; absent or JSON-null values load as `None` and write back as JSON `null`.
- Invalid sidecar values fail before readers; invalid cache values produce no usable cache entry.
- `DATA_CONTRACT.md` names the persisted field, vocabulary, unknown state, and failure behavior before this step is marked done.
- Existing finding IDs, severities, selection, apply behavior, blocking behavior, and convergence behavior remain unchanged.
- `tests/test_review.py`, `tests/test_granularity.py`, `tests/cli/test_completeness_cmd.py`, `tests/test_review_persistence.py`, `tests/test_purity_cache.py`, and `tests/test_data_contract.py` pass.

## References

- [dataclasses — Data Classes — Python 3.13 documentationhttps: — Use the field-default and replacement semantics for an additive `Recommendation` member.
- [typing — Support for type hints — Python 3.13 documentationhttps: — Keep the legacy absent value distinct from a fresh finding’s required default.
- [How to parametrize fixtures and test functions — pytest documentationhttps: — Cover each direct supported predicate and the limited default without duplicating fixtures.

## Applicable guardrails

- **The plan’s “## Plan intent”, evidence support:** Keep confidence separate from severity and do not turn it into a calibrated probability claim.
- **The plan’s “## Step intent”, direct-predicate classification:** Mark findings supported only at the directly verified producers the plan names; all other fresh findings use the conservative default.
- **The plan’s “## Out of scope”, informational behavior:** Do not change gates, exit codes, apply behavior, blocking, or convergence while adding the field.

## Deferred

- Reader-facing confidence labels — plan step 2 owns rendering normalized values in user-facing output and direct LLM finding prompts.
- Annotate confidence and calibration work — remain separate follow-up work because they use different contracts and need evidence this step does not create.
