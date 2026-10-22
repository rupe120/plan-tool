# Step 4 — Document the version-1 alias exception and reconcile shipment status

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `PLAN_FORMAT.md` to describe preferred step `description`, accepted legacy `title`, and the dual-key rules supplied by step 1. Amend `DATA_CONTRACT.md` with the narrow, owner-approved version-1 exception while retaining the general version policy. Extend `tests/test_data_contract.py` to guard that distinction. Reconcile `BACKLOG.md` #517 with verified shipment status, retaining it while execution remains pending.

## Table of Contents

- [Summary](#summary) — The change and observable result.
- [Table of Contents](#table-of-contents) — Navigation through this detail.
- [Why](#why) — The documentation and policy gap.
- [Input](#input) — Dependency outcomes and authoritative contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four files this step edits.
- [Implementation](#implementation) — Documentation, exception boundaries, and shipment bookkeeping.
- [Tests](#tests) — Drift guards and document verification.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Contract and tracking sources.
- [Applicable guardrails](#applicable-guardrails) — Limits on this step.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

`PLAN_FORMAT.md` documents step `title` as required, and `DATA_CONTRACT.md` under “Plan format version” requires a version bump before emitting any new frontmatter key. `BACKLOG.md` #517 explicitly authorizes the step alias at version 1 and requires a warning about older installations. Readers need those documents to agree with the dependency steps without mistaking the exception for general permission to add keys. The backlog also needs an accurate distinction between an authored plan and shipped behavior.

## Input

- **Step 1 supplies accepted input behavior.** Read the landed `plan_tool/schema.py:Step` implementation and its coverage in `tests/test_parser.py`. The landed names and behavior govern documentation; surface any disagreement with the plan rather than documenting a different contract.
- **Step 2 supplies preferred frontmatter output.** Read `plan_tool/parser.py:render_plan_text` and `plan_tool/parser.py:write_plan` after that step lands.
- **Step 3 supplies authoring behavior.** Confirm its outcome through `plan_tool/create.py:_STEP_PROPOSAL_RESPONSE_CONTRACT` and `plan_tool/create.py:_parse_steps_json`.
- **The exception has explicit authority.** `BACKLOG.md` #517 records the owner-confirmed decision dated 2026-10-22. Preserve that authority in the maintained policy before removing a fully shipped backlog entry.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — Update the step schema, field semantics, relevant validation prose, and worked example.
  - `DATA_CONTRACT.md` — Document the specific version-1 exception and its compatibility limits.
  - `tests/test_data_contract.py` — Add focused guards for the exception and preserve existing version-policy checks.
  - `BACKLOG.md` — Reconcile #517 with actual shipment status and any references to its pending work.

## Implementation

- **Foundational logic: document one named version-1 exception without weakening the general version boundary.** Keep step field semantics in `PLAN_FORMAT.md`; keep version policy and exception authority in `DATA_CONTRACT.md`. Prefer cross-links over repeating the full contract in both documents.

- **Enumerate affected statements before editing.** Search the declared files for `steps[].title`, `description`, `#517`, and vocabulary about new keys, version bumps, upgrades, and older readers. Review each match in context: plan titles, feature titles, and internal `Step.title` references remain valid.

- **Make preferred authored output clear.** In `PLAN_FORMAT.md` under “Frontmatter schema,” “Field semantics,” and “Example,” use step `description` as the preferred spelling. Retain plan and feature `title`. Explain that legacy step `title` remains accepted and that the internal attribute remains `plan_tool/schema.py:Step.title`.

- **Document the complete input boundary.** Describe description-only and title-only acceptance, acceptance of exactly equal valid strings under both keys, and rejection of conflicting or invalid supplied values. Neither spelling may conceal an invalid value under the other. Distinguish these two field names from repeated occurrences of the same YAML key; this step adds no duplicate-YAML-key policy.

- **Describe ordinary rewriting accurately.** State that both plan serializers emit `description`, including when rewriting a legacy-title plan, while retaining format version 1 without an explicit upgrade. Do not imply that preserving existing-plan support requires retaining the input spelling on output.

- **Amend the policy narrowly.** In `DATA_CONTRACT.md` under “Plan format version,” qualify the “Break rule” with the named step alias exception. Record the dated owner decision, unchanged version, continued legacy-plan support, and older-reader limitation. Review “Version-evolution policy,” “Writer eligibility,” and “First-refusal obligation” for contradictory wording; preserve their general obligations and distinguish older installations rejecting new output from this release refusing existing plans.

- **State compatibility in the correct direction.** Older installations that do not recognize step `description` reject newly emitted keys through strict validation, even though the declared version remains 1. The documentation must not promise that every installation accepting version 1 accepts this spelling.

- **Reuse shared authority unchanged.** `plan_tool/schema.py:PLAN_FORMAT_VERSION`, `plan_tool/schema.py:SUPPORTED_PLAN_FORMAT_VERSIONS`, and `plan_tool/parser.py:_require_supported_plan_format_version` remain the version authorities. `plan_tool/data_contract.py:artifact_format_version_contracts` already reads the live constants; no registry extension or new exception framework belongs here.

- **Close #517 only on shipment evidence.** Remove its entry only when the dependency outcomes and this step’s verification establish full shipment. While execution or required verification remains pending, retain the entry and update its plan-status wording accurately. Sweep other #517 references in `BACKLOG.md` so removal leaves no pending-work claim for the shipped item. Keep the exception’s durable policy record in `DATA_CONTRACT.md`, rather than relying on the removable backlog entry.

## Tests

The following names are proposed additions in `tests/test_data_contract.py`; existing names identify checks to retain.

- `test_step_description_alias_exception_is_documented_as_version_one_only` — The plan-version section names the specific alias, version 1, and dated owner approval.
- `test_step_description_alias_exception_documents_older_reader_rejection` — The exception explicitly describes rejection by older installations without claiming universal version-1 compatibility.
- `test_step_description_alias_exception_preserves_strict_validation_and_general_break_rule` — The documented exception remains specific while unrelated new keys and unknown-field validation retain the general policy.
- `test_plan_format_version_class_rules_documented` — Preserve the existing assertions for strict models, writer eligibility, support, retirement, and upgrade obligations.
- `test_plan_format_version_binds_live_constant` — Preserve the live registry-to-code binding.
- `test_plan_format_version_documented_with_live_value` — Preserve agreement between the documented current version and the registered constant.

### Verification (non-code step)

The test-authoring gate does not apply to this `non-code` step; it keys on code change types. The scoped drift-guard additions still belong here because this step changes the documented contract.

1. Run `uv run pytest tests/test_data_contract.py tests/test_parser.py tests/test_backlog_ids.py -q`, then the required full suite.
2. Feed the complete worked plan under `PLAN_FORMAT.md` “Example” through `plan_tool/parser.py:parse_plan_text`; verify successful schema validation.
3. Round-trip that example through `plan_tool/parser.py:render_plan_text` and reparse it; verify unchanged plan values, preferred step keys, and retained plan and feature titles.
4. Review the alias prose against the dependency steps’ tests, including invalid dual-key values and unchanged internal dumps.
5. Check relative links and symbolic references. If a heading changes, check inbound anchors before renaming it.
6. Remove each newly guarded policy clause temporarily and confirm its focused test fails; restore the document afterward.
7. Review the #517 disposition against shipment evidence and search `BACKLOG.md` for remaining references that need reconciliation.

## Acceptance criteria

- `PLAN_FORMAT.md` documents preferred step `description`, legacy `title`, exact-equality dual-key acceptance, and conflict or invalid-value rejection.
- The schema example uses preferred step output while retaining plan and feature title semantics.
- The complete worked example parses and survives a render/reparse round trip with unchanged values.
- `DATA_CONTRACT.md` identifies the dated version-1 exception and explicitly warns that older installations reject the new spelling.
- The exception does not contradict the general new-key, strict-validation, support, or upgrade policy.
- The focused drift guards pass and fail when their guarded clauses are removed.
- `BACKLOG.md` #517 is removed only after full shipment; otherwise it remains with accurate pending status.
- No production code, version constant, or stored-plan collection changes in this step.

## References

- [BACKLOG.md — #517](../../../../BACKLOG.md) — Read the scope contract and dated owner-approved exception.
- [PLAN_FORMAT.md — Frontmatter schema](../../../../PLAN_FORMAT.md#frontmatter-schema) — Owns authored step fields, examples, and validation semantics.
- [DATA_CONTRACT.md — Version-evolution policy](../../../../DATA_CONTRACT.md#version-evolution-policy) — Owns the general transition policy and plan-format exception.
- [plan_tool/schema.py — Step](../../../../plan_tool/schema.py) — Verify the landed input contract and internal attribute.
- [plan_tool/parser.py — Plan parsing and serialization](../../../../plan_tool/parser.py) — Verify version handling and preferred output.
- [docs/TRACKING.md — Promotion stubs](../../../TRACKING.md#promotion-stubs) — Read the shipment bookkeeping rule before closing the source entry.

## Applicable guardrails

- **The plan’s “Scope guardrails,” version compatibility:** Document the selected exception in the two reference files without broadening its authority.
- **The plan’s “Scope guardrails,” bounded implementation:** Keep this step’s edits within the declared documentation, drift-test, and backlog files.
- **The plan’s “Out of scope,” unrelated changes:** Preserve unaffected field meanings and contracts while updating examples and policy prose.
- **The step intent, reader understanding:** Treat compatibility explanations and accurate shipment status as the deliverables; do not add runtime behavior.

## Deferred

- Alias implementation, serializer changes, and proposal handling — Steps 1–3 own those outcomes; this step verifies and documents them.
- Broader format-policy changes or shared registry restructuring — The named exception needs neither and grants no authority for them.
- Bulk plan rewriting or an upgrade command — Outside the plan’s scope fence.
