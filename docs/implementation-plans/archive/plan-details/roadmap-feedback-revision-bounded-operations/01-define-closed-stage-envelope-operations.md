# Step 1 — Define closed stage-envelope operations, explicit add-row types, their local compatibility profile, isolated row-prose amendments, and plan-ordering companions

## Summary

Extend `plan_tool/roadmap_revision.py` with a separate typed profile for stage-level feedback envelopes, and add its contract coverage in `tests/test_roadmap_revision.py`. Keep the selector-bound `RevisionOperations` profile intact for `--revise-feedback`; the stage profile adds only the closed `add-row`, `edit-row`, `remove-row-with-record`, and feedback-response records. Use strict discriminated models, typed row payloads, bounded prose-amendment records, a plans-only ordering companion, and fixed response limits. Update the rendered artifact feedback-structure comments with concise reviewer-facing limit guidance. Green means invalid or ambiguous operation envelopes fail before any merge code receives them.

## Table of Contents

- [Summary](#summary) — The step’s outcome and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why the existing local operation pair needs a separate stage profile.
- [Input](#input) — Existing artifact, feedback, and local-revision contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The files this step changes.
- [Implementation](#implementation) — Closed operation types, ordering, authority, and compatibility rules.
- [Tests](#tests) — Contract cases that define the new envelope.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for strict JSON and Pydantic validation.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this contract.
- [Deferred](#deferred) — Later context, merge, routing, and consolidation work.

## Why

`plan_tool/roadmap_revision.py:RevisionOperations` and `parse_revision_operations` already enforce the local two-record sequence, but they cannot represent an artifact-targeted addition, a typed row edit or removal, row-owned prose, or a plans ordering companion. The stage route needs those operations without turning the local selector route into a multi-feedback protocol or accepting a general patch document. Define the stage contract now so later context-building and merge work receive typed, limited inputs rather than raw JSON maps.

## Input

- **Artifact row shapes and reviewer guidance:** Read the frozen row and artifact types in `plan_tool/roadmap_artifacts.py`, especially `DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, `PlansArtifact`, `OrderingEntry`, `FeedbackRow`, and `RemovalRecord`. The stage payload must represent those shapes without changing their on-disk parser or render data shape. The rendered `_FEEDBACK_KEY_COMMENT` and `_NO_FEEDBACK_KEY_COMMENT` are the reviewer-visible feedback-structure guidance that this step updates with the hard ceilings and the fact that a project may use stricter numeric limits.

- **Project configuration leaf:** Extend `plan_tool/project_config.py` rather than adding a second config file. The new project-only `roadmap_feedback.stage_limits` reader must remain a stdlib-only leaf and return one frozen effective-limit value for callers to pass explicitly; it must not import roadmap execution or read user configuration for this repository-owned contract.

- **Registered JSON contract:** Add `roadmap_feedback`, `stage_limits`, and its three numeric leaves to `plan_tool/data_contract.py:json_object_contracts`. The registry must document this project-only addition while preserving the existing user-config path only for its unrelated keys.

- **Collection dispatch:** Treat `plan_tool/roadmap_artifacts.py:design_row_collections` as the source for current live design rows, but do not use it as the stage add-row profile. It deliberately excludes `HostingRow` and `StoreRow`, while the stage contract must handle their different authority rules.

- **Local compatibility:** Preserve the existing `RevisionPreflight`, `RevisionOperations`, `ReplaceRowPresentationOperation`, `RespondFeedbackOperation`, and `parse_revision_operations` contract consumed by `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` and `plan_tool/roadmap_revision_patch.py:merge_feedback_revision`.

- **Relation rules:** Use the current meaning of `PlansArtifact.ordering`, `OrderingEntry`, `AssumptionRow.consuming_plan_ids`, and `DecisionRow.anchor` from `plan_tool/roadmap_artifacts.py`, plus the ordering rules in `plan_tool/roadmap_gates.py:check_plan_ordering_totality` and `check_assumption_plan_references`. Existing gates remain the final artifact validators.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Keep the two rendered feedback-structure comments concise while adding the four stage-feedback limits and the split-feedback action.
  - `plan_tool/data_contract.py` — Register the project-only `roadmap_feedback.stage_limits` object and its three numeric leaves in the generated JSON-object contract.
  - `plan_tool/project_config.py` — Add strict project-only resolution of the three numeric stage-feedback caps and its frozen effective-limit value.
  - `plan_tool/roadmap_revision.py` — Add the stage-envelope wire models, typed operation records, row and prose payload types, stage ordering checks, and the separate stage-profile parser or binding seam.
  - `tests/test_roadmap_artifacts.py` — Pin the reviewer-visible feedback comments so both paths retain the agreed limit guidance.
  - `tests/test_data_contract.py` — Pin generated contract coverage for the new project-only configuration keys.
  - `tests/test_project_config.py` — Cover defaults, valid stricter project values, invalid blocks, and the deliberate absence of user-level fallback.
  - `tests/test_roadmap_revision.py` — Add focused contract tests for the stage profile and strengthen local-profile compatibility coverage.

## Implementation

- **Keep two operation profiles.** Leave `RevisionOperations.operations` and `parse_revision_operations` as the selector-bound local contract: an optional `ReplaceRowPresentationOperation`, followed by exactly one `RespondFeedbackOperation` for the selected feedback. Add a separate stage result type, such as `StageRevisionOperations`, rather than making local callers handle every stage operation.

- **Keep the envelope closed.** Reuse the strict behavior of `plan_tool/roadmap_revision.py:_decode_single_json_object`: accept one unfenced JSON object, reject duplicate keys and non-standard constants, and reject non-whitespace trailing data. Model the root and every operation with strict, frozen Pydantic models that forbid unknown members. Select stage records through the `op` discriminator; do not add an extensible registry or a loose `dict` payload escape hatch.

- **Enforce the effective response budget before semantic binding.** Define the stage hard ceilings beside the typed stage-envelope contract: 32 active feedback items, 32 KiB of UTF-8 JSON reply bytes, 4 KiB of UTF-8 bytes per prose amendment, and one material operation per active feedback id. Receive one resolved `StageFeedbackLimits` value for the three numeric checks, and measure raw reply bytes before JSON decoding and amendment bytes before typed records reach merge code. A violation carries the applicable feedback id when one exists, the measured value, the effective limit, and a split-feedback action; it is an `invalid` result rather than a correction or retry candidate. Keep the limits and closed response schema available to the prompt renderer from this one typed contract.

- **Resolve only stricter project caps.** Define a frozen `StageFeedbackLimits` value in `plan_tool/project_config.py` with the hard defaults. Resolve `roadmap_feedback.stage_limits` from `.plan-tool/config.json` only: `max_active_feedback_items`, `max_response_bytes`, and `max_prose_amendment_bytes` are optional positive JSON integers that may be lower but never higher than the defaults, and prose bytes may not exceed response bytes. Reject the whole present block on an unknown key, a missing mapping, a boolean, any non-integer, an out-of-range value, or an invalid cross-field relation. Do not make the one-material-operation-per-feedback rule configurable, and do not read `~/.plan-tool/config.json`; this is a repository-wide behavior contract. Expose configuration failure as a typed pre-invocation error instead of silently falling back to a larger effective budget.

- **Register the config schema beside the resolver.** Extend `json_object_contracts` so the project configuration contract names `roadmap_feedback`, `stage_limits`, `max_active_feedback_items`, `max_response_bytes`, and `max_prose_amendment_bytes`. Keep the registry as a documentation and drift boundary, not a second parser or a route to user-level fallback.

- **Keep reviewer-facing artifact comments aligned.** Update `_FEEDBACK_KEY_COMMENT` and `_NO_FEEDBACK_KEY_COMMENT` in `plan_tool/roadmap_artifacts.py` with the hard 32-item, 32 KiB, 4 KiB, and one-material-operation ceilings, the instruction to split oversized feedback, and a short note that the project may set stricter numeric caps. Keep the addition concise and do not turn the comments into a duplicate JSON schema or render local configuration into canonical artifact text; the prompts and `ROADMAP_FORMAT.md` remain the detailed operation-contract owners.

- **Define only four stage operations.** The stage union contains `add-row`, `edit-row`, `remove-row-with-record`, and `respond-feedback`. Every material operation carries its authorizing feedback id; `respond-feedback` carries only the feedback id and non-blank proposed response. Do not expose a state field: the only model-driven lifecycle move remains the existing open-to-awaiting-review transition.

- **Return typed semantic records.** Make each accepted row payload a typed value matching the corresponding dataclass in `plan_tool/roadmap_artifacts.py`, including nested `FieldRow` and rejected-alternative data where applicable. One practical approach is a strict wire model per row shape that converts to the frozen artifact row before the operation result is exposed. Do not hand later merge code raw JSON objects.

- **Make additions explicit.** Require `add-row` to name `row_type` and carry a payload of that exact type. Admit additions only for the stage and collection pairs in the plan’s authority matrix: domain rows, non-hosting constraints rows, component rows including `stores`, and plans rows including assumptions and decisions. Reject an omitted, unknown, or payload-mismatched type instead of guessing from payload keys.

- **Treat identity-only rows separately.** `hosting` is editable only as its existing fixed facet and is never addable or removable. `stores` may be added, edited, or removed, but never carries a prose amendment. Keep this profile separate from `TEXT_FIELDS_BY_ROW_TYPE`, which is the local presentation surface and does not describe these stage rules.

- **Couple prose to the material row operation.** Define a compact row-prose amendment value for prose-inventory rows. An edit or removal identifies one context-issued row span and its replacement or deletion; an addition carries one appended fragment that names its new row id. Do not add a generic `body`, body-replacement, or arbitrary text-patch field. Step 2 supplies the bounded span context, and step 3 verifies and applies the byte-preservation rules.

- **Make plans ordering part of the add record.** A `plans` addition carries exactly one typed `OrderingEntry` companion for the added plan; no other row type may carry one. Its `depends_on` and `assumption_targets` may name only earlier predecessor plan ids. Do not create a standalone ordering operation or allow reordering an existing plan.

- **Protect relation targets globally.** The stage binding rules reject an edit that retargets an existing `DecisionRow.anchor`, including pending decisions, and reject a Plans edit that changes an existing `AssumptionRow.consuming_plan_ids`. Every relationship-bearing field on every added row must name only an id in the frozen live predecessor inventory, never another row added in the same envelope, regardless of operation order.

- **Freeze every existing relation field.** An `edit-row` preserves reference `FieldRow.entity_id`; `BusinessRuleRow.entity_ids`; `WorkflowRow.entity_ids`; `ConstraintRow.anchor_ids`; `ComponentRow.entity_ids`, `pattern_ids`, `constraint_ids`, and `store_ids`; `PlanRow.component_ids`; `OrderingEntry.depends_on` and `assumption_targets`; `AssumptionRow.consuming_plan_ids`; and `DecisionRow.anchor`. It may not replace, add, remove, or reorder any of their endpoints. Step 2 supplies them as context facts and step 3 rechecks preservation; no relation field is silently editable because it lacks a specialized operation model.

- **Enforce envelope order before merge.** Preserve material-operation order, require all material operations before responses, and require one response for each active predecessor feedback row in predecessor feedback order. Reject duplicate live-row material targets, material work against a carried removal, follow-up work on a row added in the same envelope, missing responses, and response ids outside the active set.

- **Keep validation ownership narrow.** Use the typed stage context introduced in step 2 to bind feedback ids, live row ids, artifact type, prose-span ids, predecessor relation ids, and plan ordering. Leave parser/renderer changes, existing stage-gate changes, and atomic candidate construction to later steps.

## Tests

### Tests for this step

- `test_stage_envelope_rejects_non_json_framing_duplicate_keys_and_unknown_members` — Rejects preambles, fences, trailing data, duplicate keys, non-standard constants, and extra root or operation members.

- `test_stage_envelope_accepts_only_the_closed_operation_vocabulary` — Rejects an unknown operation discriminator and a loose or incorrectly typed operation payload.

- `test_add_row_requires_explicit_supported_row_type_and_matching_typed_payload` — Accepts each admitted collection shape and rejects omitted, unknown, or mismatched `row_type` values.

- `test_hosting_add_and_removal_are_rejected_but_hosting_edit_keeps_its_identity` — Pins the fixed-facet exception and prevents a hosting edit from changing its id or facet.

- `test_store_operations_reject_row_prose_amendments` — Proves identity-only stores never gain a body-prose surface.

- `test_prose_inventory_material_operations_require_one_row_owned_amendment` — Requires the amendment record for prose-inventory additions, edits, and removals, without accepting a general body field.

- `test_stage_material_operations_precede_feedback_responses` — Rejects a material record after the response block and preserves accepted material order.

- `test_stage_envelope_requires_one_response_for_each_active_feedback_in_predecessor_order` — Rejects missing, duplicate, out-of-order, and unknown feedback responses.

- `test_stage_envelope_rejects_duplicate_live_row_targets_and_added_row_follow_ups` — Rejects repeated material work on one live row and attempts to edit or remove a same-envelope addition.

- `test_stage_envelope_rejects_over_effective_limit_reply_prose_and_feedback_materiality_without_retry` — Rejects a reply or amendment over its supplied effective limit, or a second material operation for one active feedback id, with an actionable invalid result rather than a partial parse or correction candidate.

- `test_rendered_feedback_comments_state_stage_feedback_limits_and_split_action` — Pins both artifact feedback-structure comments to the 32-item, 32 KiB, 4 KiB, and one-material-operation-per-item guidance.

- `test_stage_feedback_limits_default_to_hard_ceilings_and_accept_only_stricter_project_values` — Verifies project config may lower each numeric cap but cannot raise one, while the material-operation cardinality stays fixed.

- `test_stage_feedback_limit_config_is_project_only_and_fails_closed` — Rejects a user-level override and malformed, unknown, boolean, non-integer, or inconsistent project block before it can broaden the effective budget.

- `test_project_config_contract_registers_stage_feedback_limits` — Verifies the generated JSON-object contract names the project-only block and every supported numeric leaf.

- `test_plan_addition_requires_one_predecessor_only_ordering_companion` — Requires exactly one matching `OrderingEntry` for a new plan and rejects missing, duplicate, dangling, or later-plan references.

- `test_new_row_relations_cannot_target_same_envelope_additions` — Allows every relationship-bearing added-row field to name only a predecessor id.

- `test_existing_relation_fields_cannot_be_retargeted` — Rejects every listed relation field's endpoint, membership, and ordering change, including pending-decision anchors and Component Store ids.

- `test_local_revision_profile_remains_optional_presentation_then_selected_response` — Preserves the existing local two-record sequence and does not require responses for other open feedback rows.

Every listed test in `tests/test_roadmap_revision.py`, `tests/test_roadmap_artifacts.py`, `tests/test_data_contract.py`, and `tests/test_project_config.py` must be green before this step is complete.

## Acceptance criteria

- A stage reply parses only as one strict JSON operation envelope with the four published operation kinds.

- Every accepted stage operation is a frozen typed record; no accepted operation carries an untyped row map or a general body-edit field.

- An `add-row` names an explicit, admitted `row_type` whose typed payload matches the selected artifact profile.

- `hosting` cannot be added or removed, and `stores` cannot carry a prose amendment.

- A prose-inventory material record carries its row-owned amendment contract, while no operation can replace unrelated body prose.

- A new plan carries exactly one valid predecessor-only ordering companion; no standalone ordering or existing-plan reorder record parses.

- Every relationship-bearing field on every added row accepts only frozen predecessor ids, never an id introduced in the same envelope.

- No existing relationship-bearing field can be retargeted, have membership changed, or be reordered through an edit record.

- The parser applies the resolved numeric limits, bounded by the 32-item, 32 KiB, and 4 KiB hard ceilings, plus the fixed one-material-operation-per-feedback rule before any operation is available to merge. Both artifact feedback-structure comments state the hard ceilings and split action.

- `.plan-tool/config.json` may tighten the three numeric caps in `roadmap_feedback.stage_limits`, but cannot raise a hard ceiling, change material-operation cardinality, or inherit a user-level override; an invalid project block fails before invocation.

- `json_object_contracts` registers the project-only stage-limit object and its three leaves, and the generated data-contract test covers it.

- `parse_revision_operations` retains the local optional-presentation-plus-selected-response behavior consumed by `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`.

- `uv run pytest tests/test_roadmap_revision.py tests/test_roadmap_artifacts.py tests/test_data_contract.py tests/test_project_config.py -q` passes.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — Use its object and member rules when defining the single closed reply envelope.

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use `JSONDecoder`, `raw_decode`, `object_pairs_hook`, and `parse_constant` to preserve the strict decoder boundary.

- [Pydantic: Unions](https://docs.pydantic.dev/latest/concepts/unions/) — Use discriminated unions to select the closed operation and typed-row payload vocabulary.

- [Pydantic: Configuration](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen models with forbidden extra fields for operation records.

- [Pydantic: Validators](https://docs.pydantic.dev/latest/concepts/validators/) — Use model-level validation for cross-record ordering, response coverage, and plans ordering companions.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded model output:** Keep the stage reply to typed operations only. This step must not add an artifact-text or authoring-contract return path.

- **The plan’s “## Out of scope”, bounded edit surface:** Limit row prose to coupled amendments and reject generic body or diff operations.

- **The plan’s “## Out of scope”, relation and ordering authority:** Do not add a standalone relation or ordering operation, and do not permit edits to existing plan-internal relations.

- **The plan’s “## Out of scope”, route compatibility:** Preserve the selector-bound local profile and leave structural revision’s contract unchanged.

- **The plan’s “## Out of scope”, gate and lifecycle behavior:** Define operation validity only; do not change stage gates, retry policy, CLI outcomes, publisher behavior, or retention semantics.

## Deferred

- `plan_tool/roadmap_revision.py` stage-context construction — Step 2 supplies the bounded active-feedback, row, prose-span, relation, and ordering context used to bind these records.

- `plan_tool/roadmap_revision_patch.py:merge_feedback_revision` stage candidate merging — Step 3 applies the typed records atomically and proves untouched rows and prose remain unchanged.

- `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` stage-route selection and prompt execution — Step 5 adopts the stage profile without widening the existing local route.

- `plan_tool/roadmap_structural_operations.py:parse_structural_revision_operations` decoder consolidation — Its strict JSON parsing is parallel but its structural rewrite schema differs; share behavior only through a separately scoped refactor if duplication becomes a maintenance problem.
