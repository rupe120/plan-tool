> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Ask for row-owned prose in candidate proposals and corrections while preserving publication writes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update the candidate-delta prompts so proposal and correction responses supply the row-owned prose required by step 2 for eligible `add-row` operations. Adjust `plan_tool/roadmap_candidate_run.py` prompt-shape rendering to remain aligned with the landed closed operation schema. Use focused tests in `tests/test_roadmap_candidate_run.py` and `tests/test_roadmap_candidate_review.py` to prove prompts request the field and accepted results still use the existing publication paths. On green, a model receives enough instruction to submit an admissible prose-bearing addition without widening candidate authority or changing publication behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the prompt-contract change.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why admitted prose must be requested from the model.
- [Input](#input) — Upstream candidate amendment contract and existing prompt routes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Prompt and rendering rules that preserve candidate authority.
- [Tests](#tests) — Focused prompt and publication regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Source contracts and implementation anchors.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this step.
- [Deferred](#deferred) — Related work outside this prompt-focused step.

## Why

Step 2 makes row-owned prose mandatory for eligible candidate additions, but `plan_tool/prompts/roadmap-candidate-delta.md` and `plan_tool/prompts/roadmap-candidate-delta-selector.md` currently describe only typed rows. A proposal or structural correction that omits the amendment will be rejected despite adding an otherwise valid row. The prompts must ask for the required record directly while keeping the existing model response limited to the issued capsule, closed delta envelope, and reviewer authority.

## Input

- **Step 2 candidate contract:** Step 2 lands the required `CandidateAddRow.prose_amendment` contract and preserves immutable normalized-operation replay. Read the landed parser-owned key sets and validation rules rather than copying names or limits from this detail.

- **Prompt rendering:** `plan_tool/roadmap_candidate_run.py:render_candidate_delta_prompt()` chooses the batch or selector template. `plan_tool/roadmap_candidate_run.py:_render_batch_operation_shapes()` derives batch examples from the parser-owned operation keys.

- **Correction routes:** `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal()` retries rejected batch responses with `correction_reason`. `plan_tool/roadmap_candidate_review.py:_edit_structural_candidate()` and `plan_tool/roadmap_candidate_review.py:request_replacement()` use the same rendered batch-delta contract with review context.

- **Publication boundary:** `plan_tool/roadmap_candidate_run.py:_store_batch_candidate()` and `plan_tool/roadmap_candidate_review.py:_store_active_structural_replacement()` own immutable candidate, ledger, pointer, and supersession publication. This step must leave their write contract unchanged.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — keep parser-derived operation examples renderable after step 2 and make proposal retry instructions consistently request complete prose-bearing additions.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — describe the required row-owned amendment for eligible batch `add-row` operations, including correction responses.
  - `plan_tool/prompts/roadmap-candidate-delta-selector.md` — describe the same requirement for eligible selector-era additions without changing its delta-or-expand disposition.
  - `tests/test_roadmap_candidate_run.py` — cover rendered prompt shapes, prose instructions, retries, and unchanged batch storage behavior.
  - `tests/test_roadmap_candidate_review.py` — cover structural-edit and answer-bound replacement prompts and retain publication-path regression coverage.

## Implementation

- **Ask for the parser-owned addition field.** Update both templates to require the step-2 row-owned prose record when an `add-row` targets a prose-enabled collection. The prompt must identify that the record belongs to the added row and must be included in the operation, not emitted as artifact body text or a separate response field.

- **Keep the closed response shape.** Retain the existing top-level response forms, operation names, `feedback_id` binding, and batch response requirements. The selector template must still permit only its existing `delta` or `expand` disposition; an expansion must not carry prose outside a later delta.

- **Keep authority separate from context.** The review pair and retry correction may explain what needs changing, but they must not grant a new row, prose fragment, or feedback id. The model may act only through an authorized delta operation against the issued capsule.

- **Make examples follow the landed schema.** Update `plan_tool/roadmap_candidate_run.py:_render_batch_operation_shapes()` so its generated `add-row` example remains a complete valid envelope after step 2 adds the required amendment. Continue deriving the visible key set from `CandidateAddRow` constants rather than maintaining a second schema.

- **Preserve row ownership and bounded prose rules.** Direct the model to use the validation contract from step 2: prose is required only where that contract allows it, names the added row, and stays within its established content and byte limits. Do not ask the model to synthesize whole-body text, markers, spans, replacement-row prose, or removal prose.

- **Cover correction paths with the same contract.** Ensure a batch retry created by `plan_tool/roadmap_candidate_run.py:_run_batch_candidate_proposal()` and review-driven calls through `plan_tool/roadmap_candidate_review.py:_edit_structural_candidate()` and `plan_tool/roadmap_candidate_review.py:_invoke_replacement()` see the same prose requirement as an initial proposal.

- **Do not alter publication writes.** Leave `plan_tool/roadmap_candidate_run.py:_store_batch_candidate()`, `plan_tool/roadmap_candidate_run.py:apply_replacement_ledger_patch()`, and `plan_tool/roadmap_candidate_review.py:_store_active_structural_replacement()` responsible for their current atomic candidate, ledger, active-pointer, and supersession writes. Prompt work must not create a parallel writer or change when a response becomes publishable.

## Tests

### Tests for this step

- `test_batch_prompt_add_row_example_includes_required_row_owned_prose` — asserts the parser-derived batch `add-row` example contains the landed amendment field and remains a closed operation shape.

- `test_batch_prompt_requires_row_owned_prose_only_for_eligible_additions` — asserts the batch template requires the amendment where step 2 permits it and does not grant prose authority to other operation kinds.

- `test_selector_prompt_requires_row_owned_prose_in_delta_additions` — asserts the selector template keeps its closed disposition contract while requiring eligible added rows to carry their prose record.

- `test_batch_retry_prompt_repeats_the_row_owned_prose_requirement` — drives a rejected first batch response and asserts the correction prompt still requests a complete, prose-bearing replacement delta.

- `test_structural_edit_prompt_requests_row_owned_prose_without_granting_review_pair_authority` — asserts an edit decision’s prompt contains the correction context and the same delta requirement without treating the review pair as writable artifact content.

- `test_answer_bound_replacement_prompt_requests_row_owned_prose_and_preserves_answer_binding` — asserts `request_replacement()` keeps its stored question-and-answer binding while rendering the updated operation contract.

- `test_prose_bearing_batch_candidate_stores_through_existing_publication_path` — submits a valid eligible addition and asserts immutable candidate storage and ledger transition still occur through the existing batch route.

- `test_prose_bearing_structural_replacement_updates_existing_active_candidate_route` — submits a valid structural correction and asserts the existing replacement, pointer, and supersession publication behavior remains intact.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Eligible `add-row` operations in both candidate templates explicitly require the step-2 row-owned prose record.

- The batch prompt’s generated `add-row` example contains every parser-owned required key after the step-2 schema change.

- A retry correction prompt requires one complete replacement object under the same issued batch and still requires eligible row-owned prose.

- Structural-edit and answer-bound replacement prompts retain review context without granting it independent artifact-content authority.

- Selector-era responses retain their existing `delta` or `expand` disposition contract.

- Valid prose-bearing proposal and correction responses reach the existing immutable publication paths without changing ledger, pointer, supersession, or accepted-head behavior.

## References

- [BUG_BACKLOG.md — Structural candidates cannot satisfy described-row gates for newly added rows](../../../../BUG_BACKLOG.md#structural-candidates-cannot-satisfy-described-row-gates-for-newly-added-rows) — Read the source problem, amendment shape, and prompt requirement.

- [ROADMAP_FORMAT.md — Roadmap validation rules](../../../../ROADMAP_FORMAT.md) — Read the `undescribed-row` rule and prose-amendment bounds that prompts must not bypass.

- [plan_tool/roadmap_candidate.py](../../../../plan_tool/roadmap_candidate.py) — Read the landed candidate operation admission and immutable materialization contract from step 2.

- [plan_tool/roadmap_candidate_run.py](../../../../plan_tool/roadmap_candidate_run.py) — Read `render_candidate_delta_prompt()`, `_render_batch_operation_shapes()`, and batch publication ownership.

- [plan_tool/roadmap_candidate_review.py](../../../../plan_tool/roadmap_candidate_review.py) — Read correction invocation and structural replacement publication boundaries.

## Applicable guardrails

- **The plan’s “## Step intent”, proposal and retry input boundary** — limit this step to obtaining the prose the candidate contract requires; do not add unrelated candidate capabilities.

- **The plan’s “## Out of scope”, prose authority boundary** — keep replace and remove operations, body-level edits, and generated narrative outside this step.

- **The plan’s “## Out of scope”, gate and lifecycle boundary** — retain the existing `undescribed-row` enforcement and candidate-driven ledger, accepted-head, and seed behavior.

- **The plan’s “## Plan intent”, inert-until-promotion boundary** — preserve existing immutable publication and promotion separation while changing only what the model is asked to return.

## Deferred

- Prompt hit-rate measurement against live model traffic — canned-response tests prove the contract is satisfiable, not that a model follows it reliably.

- General prompt-schema generation — the parser-derived batch operation example is sufficient here; consolidating all template prose with schema rendering is broader work.
