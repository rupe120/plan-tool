> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add explicit concept ownership to plan steps

## Summary

Add an optional `concept_ids` list to `plan_tool/schema.py:Step` so each plan step can persist the stable concept IDs it owns. Keep older plans compatible by defaulting the field to an empty list and leaving that default out when `plan_tool/parser.py:write_plan` rewrites frontmatter. Reject malformed or repeated IDs within one step, while leaving concept-record membership checks to code that has the signed-off concept record available. Document the ownership field in `DATA_CONTRACT.md` and prove parsing, validation, and round-trip behavior in `tests/test_parser.py` and `tests/test_data_contract.py`.

## Table of Contents

- [Summary](#summary) — Overview of the ownership field and its compatibility rules.
- [Why](#why) — Why durable concept-to-step links are needed.
- [Input](#input) — Existing plan and concept-ID contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Declared files and their expected changes.
- [Implementation](#implementation) — Required schema, validation, and serialization behavior.
- [Tests](#tests) — Unit and documentation checks for the new contract.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Authoritative schema-validation guidance.
- [Deferred](#deferred) — Membership and integration work owned by later steps.

## Why

`plan_tool/schema.py:Step` currently has no durable link to the signed-off concepts a step promises to deliver. Existing `Step.features` tags describe plan-local capabilities and cannot safely stand in for stable concept-record IDs without changing their established advisory contract in `PLAN_FORMAT.md:Feature-ref checks (advisory)` and `plan_tool/review.py:validate_feature_refs`. A separate, backward-compatible ownership list gives later create, completeness, split, merge, re-ground, and scope-out work a machine-readable contract instead of relying on titles or detail prose.

## Input

- **Plan step frontmatter:** `plan_tool/schema.py:Step` is the typed source for each item under `steps`, and `plan_tool/parser.py:parse_plan_text` validates that shape through `Plan.model_validate`.
- **Stable concept IDs:** each `concept_ids` entry refers to the concept-record core’s stable `ConceptNode.id`. That prerequisite is external to this step; this step stores the identifiers but does not create or revise concept records.
- **Current feature tags:** `Plan.features`, `Step.features`, and `plan_tool/review.py:validate_feature_refs` keep their existing plan-local, advisory meaning. They are not an alternate persisted owner link.
- **Round-trip rules:** `plan_tool/parser.py:write_plan` uses `model_dump(exclude_defaults=True, exclude_none=True)`, so a default empty list must remain absent from rewritten YAML while a non-empty list must survive unchanged.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/schema.py` — add the defaulted `Step.concept_ids` ownership field and local validation for valid, unique string IDs.
  - `plan_tool/parser.py` — keep `parse_plan_text` and `write_plan` aligned with the new field, including useful validation-error output and default omission.
  - `DATA_CONTRACT.md` — document `steps[].concept_ids` as persisted authored-plan ownership metadata, including its empty default and validation limits.
  - `tests/test_parser.py` — cover absent, valid, malformed, repeated, and round-tripped ownership lists.
  - `tests/test_data_contract.py` — add a drift check that ties the documented ownership field and rules to `plan_tool/schema.py:Step`.

## Implementation

- **Add one authoritative owner field.** Extend `plan_tool/schema.py:Step` with `concept_ids: list[str]` using an independent empty-list default. A step may own zero or more concepts, and the same concept may be owned by more than one step; only duplicates within one step are invalid.

- **Keep legacy plans valid.** An omitted `concept_ids` field must produce `step.concept_ids == []`. Do not make ownership required based on `Step.status` or `Step.scope`; later completeness work decides whether a signed-off included concept lacks an acceptable committed owner.

- **Validate the local shape at parse time.** Require every entry to be a non-empty string in the stable concept-ID format supplied by the concept-record core, and reject a repeated ID within the same step. Preserve input order rather than sorting because later structural operations may already have a deterministic order to retain.

- **Do not claim membership validation without the concept record.** `plan_tool/parser.py:parse_plan_text` receives only plan text, so it cannot prove that an otherwise valid ID names a real signed-off concept. Avoid filesystem reads or sidecar lookup inside `Step` or `Plan` validators; those would make identical frontmatter validate differently by location and would break the pure `parse_plan_text` contract.

- **Use the existing parser path.** `plan_tool/parser.py:parse_plan_text` already sends the full YAML mapping through `Plan.model_validate`, and `plan_tool/parser.py:write_plan` already serializes model fields recursively. The recommended approach is to let those generic paths carry `concept_ids`, adding parser-specific logic only if concise validation rendering needs to name the new field clearly.

- **Preserve rewrite behavior.** A non-empty `concept_ids` list must be written under its owning step and survive parse-write-parse unchanged. An empty default must stay out of rewritten frontmatter through `write_plan`’s existing `exclude_defaults=True` behavior.

- **Keep feature validation separate.** Do not reuse `Step.features`, change `Feature`, or move the advisory rules from `plan_tool/review.py:validate_feature_refs` into the plan schema. That would mix stable concept-record ownership with the existing plan-local feature registry and change behavior outside this step’s declared files.

- **Document the persistence boundary.** Add a focused authored-plan ownership section to `DATA_CONTRACT.md` even though its general scope points authored formats to `PLAN_FORMAT.md`. State that `concept_ids` is stored in plan frontmatter, defaults to `[]`, contains stable concept-record IDs, rejects malformed or repeated entries within one step, and does not by itself prove that the referenced record exists.

- **Make documentation drift testable.** In `tests/test_data_contract.py`, add a schema-backed check against `plan_tool.schema.Step.model_fields` rather than a prose-only substring assertion where practical. The check should fail if `concept_ids` disappears from the model or its documented contract disappears.

## Tests

- `test_concept_ids_absent_default_empty` — an older plan without ownership parses with `Step.concept_ids == []`.
- `test_step_concept_ids_parse` — a valid ordered list is exposed unchanged on the owning step.
- `test_step_concept_ids_reject_non_string_entry` — a non-string list member raises `ValidationError`.
- `test_step_concept_ids_reject_empty_id` — an empty or whitespace-only identifier raises `ValidationError`.
- `test_step_concept_ids_reject_duplicate` — the same identifier repeated within one step raises `ValidationError`.
- `test_concept_ids_may_be_owned_by_multiple_steps` — the same valid identifier on different steps remains valid.
- `test_concept_ids_round_trip` — `write_plan` followed by `parse_plan` preserves a non-empty ownership list and the prose body.
- `test_empty_concept_ids_elided_on_write` — a default empty list is absent from rewritten frontmatter.
- `test_concept_ownership_contract_documented` — `DATA_CONTRACT.md` names `steps[].concept_ids`, its default, and its persisted meaning.
- `test_concept_ownership_contract_matches_step_schema` — the documentation drift guard is tied to `Step.model_fields`.

### Test-creation order (feature step)

1. Add the absent/default, valid-parse, and invalid-entry tests with the `Step.concept_ids` model change.
2. Add duplicate-within-step and shared-across-steps tests with the ownership validation rule.
3. Add non-empty round-trip and empty-default omission tests against `plan_tool/parser.py:write_plan`.
4. Add the `DATA_CONTRACT.md` drift checks with the documentation update.

Every new test must be green before this step is considered finished.

## Acceptance criteria

- Parsing a plan whose step omits `concept_ids` returns an empty list for that step.
- Parsing a step with valid, distinct concept IDs preserves their order.
- Parsing a step with a malformed, empty, non-string, or repeated concept ID raises `plan_tool.parser.ValidationError`.
- Two different steps may explicitly own the same valid concept ID.
- `plan_tool/parser.py:write_plan` writes non-empty ownership lists and leaves empty default lists out of frontmatter.
- A parse-write-parse cycle preserves every non-empty `concept_ids` list and leaves the markdown body unchanged.
- `DATA_CONTRACT.md` documents the ownership field, default, persistence location, and validation boundary.
- All new tests in `tests/test_parser.py` and `tests/test_data_contract.py` pass.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the array, string, and uniqueness rules as the reference model for the ownership-list contract.

## Deferred

- **Concept-record membership checks** — later create and completeness steps have the signed-off concept record needed to reject or report IDs that do not name a real concept; plan-text parsing alone lacks that input.
- **Ownership assignment during create and detail generation** — steps 3 and 4 consume this field and own those workflows.
- **Coverage findings and owner eligibility** — step 5 decides whether a concept has a valid committed owner and reports uncovered concepts.
- **Split, merge, re-ground, and scope-out transformations** — steps 6 through 9 own preservation or redistribution of existing `concept_ids`.
- **Consolidating concept and feature validation** — do not duplicate `plan_tool/review.py:validate_feature_refs`; any broader validation refactor needs reconcile to update its file scope and settle the plan’s conflicting feature-versus-concept ownership wording.
