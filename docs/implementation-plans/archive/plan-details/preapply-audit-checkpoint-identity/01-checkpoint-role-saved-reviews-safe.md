> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a checkpoint role to saved reviews with safe legacy handling

## Summary

Add an optional persisted `is_pre_apply_checkpoint` role to `SavedReview` and preserve it through save, load, and annotation updates. Update `plan_tool/review_persistence.py`, the saved-review registry in `plan_tool/data_contract.py`, and the matching contract documentation and tests. Treat a valid version-3 completeness checkpoint, legacy version-1/2 final sidecars, and malformed or role/version-mismatched metadata as distinct states without changing filenames. On green, new persistence callers write a confirmed checkpoint only behind the version-3 fence, normal final saves still omit the key and retain their current version, and legacy or malformed sidecars remain inspectable without being normalized into a trusted final role.

## Table of Contents

- [Summary](#summary) — Scope and green result.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — Why saved reviews need a durable role.
- [Input](#input) — Existing sidecar and rewrite contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Role normalization and persistence rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for dataclasses and JSON handling.
- [Applicable guardrails](#applicable-guardrails) — Scope and compatibility boundaries.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` currently produces the same saved-review shape as a final completeness report, so later consumers cannot tell crash-recovery evidence from a converged result. The persistence layer needs to expose that distinction before producers and readers can use it safely. A three-state role policy also prevents malformed metadata, or an annotation rewrite, from silently turning an unsafe sidecar into an ordinary final artifact.

## Input

- **Saved-review payload:** `plan_tool/review_persistence.py:SavedReview`, `plan_tool/review_persistence.py:save_review`, and `plan_tool/review_persistence.py:load_review` define the JSON fields and the supported `version` values.
- **Rewrite path:** `plan_tool/review_persistence.py:update_annotation` loads and rewrites a whole sidecar, so it must retain the normalized role instead of changing a checkpoint or unknown sidecar into a final one.
- **Contract registry:** `plan_tool/data_contract.py:persisted_dataclass_contracts` derives documented fields from `SavedReview`; `DATA_CONTRACT.md` is checked against that registry by `tests/test_data_contract.py`.
- **Later consumers:** `plan_tool/completeness_report.py:resolve_reusable_audit` and `plan_tool/convergence_diagnosis.py:load_report_history` will consume the role in later steps; this step supplies their stable input contract only.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review_persistence.py` — add the saved-review role, normalize it on load, serialize valid checkpoint requests, and preserve the safe role through `update_annotation`.
  - `plan_tool/data_contract.py` — register the new `SavedReview` field as conditionally persisted.
  - `DATA_CONTRACT.md` — document the role values, omission behavior, malformed-role handling, and supported-version policy.
  - `tests/test_review_persistence.py` — cover the save/load/rewrite role matrix.
  - `tests/test_data_contract.py` — cover registry and documentation expectations for the optional field.

## Implementation

- **Foundational logic:** normalize each sidecar into a confirmed checkpoint, an ordinary final artifact, or an unknown role.

- **Add the persisted role to `plan_tool/review_persistence.py:SavedReview`.** Use the plan’s `is_pre_apply_checkpoint` name. The in-memory representation must retain enough information for later readers to distinguish confirmed version-3 `true`, ordinary final raw version-3 `false` or unmarked version-1/2, and unknown metadata; an optional boolean with an explicit unknown state is one suitable approach.

- **Fence the role with schema version 3.** Versions 1 and 2 remain legacy formats: an unmarked sidecar keeps its ordinary-final behavior, but any marker in either version is a role/version mismatch and normalizes to unknown. Version 3 is role-aware: for `kind="completeness"`, `true` means confirmed checkpoint and raw `false` means ordinary final. A version-3 sidecar with no marker is unknown. Do not coerce strings, numbers, `null`, collections, or truthy values.

- **Fail closed for invalid role metadata.** A present non-boolean marker, any marker on a non-completeness sidecar, a marker in version 1 or 2, or a marker-less version-3 sidecar must load without `ReviewLoadError` but normalize to an unknown role. Later steps will exclude unknown roles from reuse and convergence; this step must not treat them as final.

- **Write checkpoints behind the version fence.** Extend `plan_tool/review_persistence.py:save_review` so a valid checkpoint request persists `is_pre_apply_checkpoint: true` with version 3. Default and final writes must continue to omit the optional key and retain their current version and payload shape. The version-3 writer must preserve any otherwise valid completeness metadata, including an advisory payload, while role-unaware version-1/2 readers reject it. Ensure the supported writer cannot deliberately emit a checkpoint role for a non-completeness sidecar; raw invalid sidecars remain the loader’s compatibility case.

- **Preserve role and version safety through `plan_tool/review_persistence.py:update_annotation`.** The annotation rewrite must keep a confirmed version-3 checkpoint confirmed and must not convert an unknown role into an omitted marker or explicit `false`. It must also preserve version 3 and its advisory behavior, if present. Preserve the raw marker where practical, or write a durable unknown representation; preserving role semantics matters more than preserving malformed bytes exactly.

- **Add only the checkpoint schema version; keep filenames unchanged.** `plan_tool/review_persistence.py:SCHEMA_VERSION`, `plan_tool/review_persistence.py:_ADVISORY_SCHEMA_VERSION`, `plan_tool/review_persistence.py:load_review`, and `plan_tool/review_persistence.py:_timestamp_filename` already define the compatibility boundaries. Add a role-aware version 3 that newer readers accept and role-unaware version-1/2 readers reject; keep version-1/2 unmarked-sidecar compatibility and reject unsupported future versions.

- **Register and document the optional field and fence.** Add the field to the `SavedReview` entry in `plan_tool/data_contract.py:persisted_dataclass_contracts` as conditionally persisted. Update the `SavedReview` table in `DATA_CONTRACT.md` with the exact version-1/2/3 role policy: new final writes omit the key and retain their current version, legacy absence is final, version 3 carries recognized roles, and malformed, misplaced, or role/version-mismatched metadata is unknown rather than trusted.

## Tests

Every test below must be green before this step is complete.

### Tests for this step

- `test_save_writes_v3_true_checkpoint_marker_for_completeness` — `plan_tool/review_persistence.py:save_review` writes version 3 plus `true`, and `plan_tool/review_persistence.py:load_review` returns the confirmed checkpoint role.
- `test_final_save_omits_checkpoint_marker_and_retains_current_version` — a normal completeness save keeps the optional key absent, retains its current version, and loads as an ordinary final role.
- `test_load_v3_explicit_false_checkpoint_marker_is_final` — a raw version-3 completeness sidecar with `false` loads as an ordinary final role.
- `test_load_unmarked_v1_v2_legacy_checkpoint_role_is_final` — supported historical version-1 and version-2 sidecars without the key remain readable and final.
- `test_load_invalid_checkpoint_marker_is_unknown` — parameterized non-boolean version-3 marker values remain loadable but normalize to unknown.
- `test_load_marker_on_non_completeness_or_legacy_version_is_unknown` — a present marker outside completeness or in version 1/2 remains inspectable but is not trusted.
- `test_load_markerless_v3_sidecar_is_unknown` — a role-aware version-3 sidecar without its marker remains inspectable but is not trusted.
- `test_role_unaware_reader_rejects_v3_checkpoint` — a simulated version-1/2 reader rejects an emitted version-3 checkpoint before it can interpret the unknown key as final.
- `test_update_annotation_preserves_checkpoint_role_and_v3_matrix` — annotation updates preserve confirmed checkpoint, ordinary final, unknown role, and version-3 advisory semantics.
- `test_saved_review_checkpoint_marker_is_conditionally_persisted` — `plan_tool/data_contract.py:persisted_dataclass_contracts` exposes the field without making it required on every payload.
- `test_saved_review_checkpoint_marker_documented` — `DATA_CONTRACT.md` documents the field and its legacy and malformed-value policy.

## Acceptance criteria

- `plan_tool/review_persistence.py:save_review` can persist version-3 `is_pre_apply_checkpoint: true` only for a valid completeness checkpoint request.
- Normal final saves omit `is_pre_apply_checkpoint` and retain their current version; raw version-3 `false` and unmarked version-1/2 values load as ordinary-final roles.
- `plan_tool/review_persistence.py:load_review` accepts version 3, preserves version-1/2 unmarked compatibility, and rejects unsupported future versions; a role-unaware version-1/2 reader rejects a version-3 checkpoint.
- A non-boolean marker, any marker on a non-completeness sidecar or in version 1/2, and a marker-less version-3 sidecar remains loadable but has an unknown role.
- `plan_tool/review_persistence.py:update_annotation` does not downgrade a confirmed checkpoint or unknown sidecar into an ordinary final role and preserves version-3 checkpoint semantics.
- `plan_tool/data_contract.py:persisted_dataclass_contracts` and the `SavedReview` section of `DATA_CONTRACT.md` agree that the field is conditional.
- `pytest tests/test_review_persistence.py tests/test_data_contract.py` passes.
- Existing timestamp filenames and report paths remain unchanged.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Review defaulted dataclass fields for the additive `SavedReview` state.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Review JSON parsing and serialization behavior for optional marker values.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use the JSON value rules when defining valid boolean markers.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use a compact raw-sidecar matrix for valid, legacy, and malformed role values.

## Applicable guardrails

- **Durable recovery evidence:** the plan’s “## Plan intent” requires this step to preserve a checkpoint as a readable sidecar; role normalization must not discard its report, findings, or annotations.
- **Checkpoint identity only:** the plan’s “## Step intent” limits this step to creating the durable role contract and preserving legacy reads.
- **Path compatibility:** the plan’s “## Out of scope”, report naming and filename compatibility, means `plan_tool/review_persistence.py:_timestamp_filename` and report locations stay unchanged.
- **Historical data:** the plan’s “## Out of scope”, historical sidecars, means absence maps to legacy final behavior without a migration or bulk rewrite.
- **Reader boundaries:** the plan’s “## Out of scope”, convergence and reuse behavior, means this step exposes safe role states but does not change `plan_tool/completeness_report.py:resolve_reusable_audit` or `plan_tool/convergence_diagnosis.py:load_report_history`.

## Deferred

- Marking the pre-apply producer through `plan_tool/cli/completeness_phases.py:write_pre_apply_audit_checkpoint` and `plan_tool/completeness_report.py:write_completeness_report` — step 2 owns the first production `true` write.
- Reuse selection in `plan_tool/completeness_report.py:resolve_reusable_audit` — step 3 owns filtering marked and unknown roles.
- Convergence filtering in `plan_tool/convergence_diagnosis.py:load_report_history` — step 4 owns the shared history rule.
- Positional checkpoint removal in `plan_tool/cli/completeness_phases.py:_completeness_convergence_diagnosis` — step 5 removes that now-redundant behavior after shared filtering lands.
- Bulk migration or deletion of existing report sidecars — outside this plan’s compatibility boundary.
