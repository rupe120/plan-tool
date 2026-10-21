> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Route each carried decision only to its owning stage and preserve gate-before-atomic-overwrite publication with seed writes unchanged

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap.py` and the four Roadmap stage prompts so each approved carried decision reaches only the stage whose artifact owns its anchor. Keep the stage table and its uniform gate call shape intact while giving each prompt the inherited decision rows it must reproduce. Preserve the existing sequence: validate generated output before publishing it through the guarded, atomic stage-publication path. On green, a carried decision appears once in its owning artifact, rejected output changes neither artifacts nor seeds, and existing re-entry behavior remains unchanged.

## Table of Contents

- [Summary](#summary) — The step outcome and main design choice.
- [Table of Contents](#table-of-contents) — Quick links to this detail.
- [Why](#why) — Why inherited decisions need stage-scoped delivery.
- [Input](#input) — The upstream source, row, and gate contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed by this step.
- [Implementation](#implementation) — Prompt routing and publication-order requirements.
- [Tests](#tests) — Focused orchestration and prompt coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant format and delivery contracts.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep this work narrow.

## Why

`plan_tool/roadmap.py:_render_stage_prompt` currently supplies a shared brief-and-upstream context to every authoring stage, while the prompts describe every decision as Roadmap-derived. Steps 1 through 3 add an approved, typed inherited-decision path and its deterministic gate, but Roadmap still needs to deliver each approved choice to the one stage that can legally publish it. Routing the rows at the orchestration boundary prevents a model from copying a settled source choice into unrelated artifacts and keeps publication safety independent of prompt content.

## Input

- **Step 1 source contract:** Step 1 provides the current recorded-source carried-decision records, including each record’s owning Roadmap artifact and confirmed citation. This step consumes that parsed contract; it must not reinterpret source admission, confirmation, or rebind rules.

- **Step 2 artifact contract:** Step 2 provides the inherited `DecisionRow` representation. This step must present that representation to the authoring prompt without asking the model to invent Roadmap rationale or rejected alternatives.

- **Step 3 gate contract:** Step 3 makes the stage gate reject invalid inherited rows. This step must continue to pass the same `ArtifactEnvelope` through each stage’s gate function and rely on that gate before publication.

- **What tests prove:** Canned responses can prove that routing, parsing, gating, and publication fit together. They cannot measure whether a model usually follows the new prompt wording on real briefs.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Project carried decisions by the current `RoadmapStage`, remove the raw block from common brief prompt text, and retain gate-before-publication.
  - `plan_tool/roadmap_revision.py` — Refuse material feedback operations targeting inherited decisions while preserving them during unrelated edits.
  - `plan_tool/prompts/roadmap-domain.md` — Tell the domain stage how to reproduce only its supplied inherited decisions.
  - `plan_tool/prompts/roadmap-constraints.md` — Tell the constraints stage how to reproduce only its supplied inherited decisions.
  - `plan_tool/prompts/roadmap-components.md` — Tell the components stage how to reproduce only its supplied inherited decisions.
  - `plan_tool/prompts/roadmap-plans.md` — Tell the plans stage how to reproduce only its supplied inherited decisions.
  - `tests/test_roadmap.py` — Cover stage-scoped prompt context, rejection-before-overwrite behavior, and unchanged seed state.
  - `tests/test_roadmap_revision.py` — Cover bounded feedback refusal and inherited-row preservation.

## Implementation

- **Route by the owning artifact.** Make `plan_tool/roadmap.py:_render_stage_prompt` receive the carried-decision context selected for its `RoadmapStage`. Select records using the stage’s established artifact identity rather than a new `stage.number` branch. The result must contain every carried record for that artifact and no record owned by another stage.

- **Exclude the raw input block.** Remove the validated `## Carried decisions` fenced JSON section from the brief text passed as common context to all four stages. Pass only the typed owner-selected rows as explicit prompt data. The full brief stays the recorded digest-bound source for citation checks.

- **Keep the loop table-driven.** `plan_tool/roadmap.py:RoadmapStage`, `STAGES`, `_run_stage`, and `_build_envelope` must keep their uniform stage-table behavior. One way is to add stage-scoped prompt input as data derived from the existing stage row; do not add per-stage control-flow branches or gate wrappers.

- **Render source facts, not a second source format.** Use the typed output from steps 1 and 2 when preparing prompt content. Include the selected decision identity, chosen option, anchor, status, confirmed citation, and any source-provided rationale or rejected alternatives. Do not make `plan_tool/roadmap.py` parse raw source JSON again or create a second inherited-row schema.

- **Make the prompt instruction strict and local.** Each template under `plan_tool/prompts/` must distinguish supplied inherited rows from Roadmap-derived decisions. It must direct the model to reproduce supplied inherited rows only in that stage’s `decisions` collection, preserve their citation and any explicitly supplied deliberation exactly, and omit rationale or rejected alternatives when the source omits them. It must not mention carried rows assigned to another artifact.

- **Leave ordinary decisions available.** The prompt change must not prohibit Roadmap-derived decisions where the model genuinely makes a new decision. Keep the existing `pending` review path and ordinary decision-row guidance for those rows.

- **Preserve publication ordering.** Keep `_run_stage` parsing and running `stage.gates` before `_run_roadmap` reaches `publish_stage_artifact`. A gate refusal must remain a retry or invalid-stage outcome and must not replace an existing artifact. Do not move prompt routing into `plan_tool/roadmap_revision_publish.py` or bypass its guarded publication path.

- **Keep seed behavior unchanged.** Do not alter `plan_tool/roadmap.py` seed-state loading, invalidation, promotion, materialization, or refresh routes. A rejected carried-decision attempt must not write a draft seed, promoted seed, or seed-state update; a successful artifact replacement must retain the existing seed invalidation behavior.

- **Keep non-authoring routes unchanged.** Re-entry through `_load_and_regate_below`, `_load_predecessors`, and `_run_feedback_free_stage` must continue to read and re-gate existing artifacts without injecting or materializing carried rows. Legacy artifacts and handwritten briefs keep their current behavior unless an inherited row is actually being validated by the landed step-3 gate.

- **Close the bounded feedback path.** `plan_tool/roadmap_revision.py:DecisionRowPayload` and `_decode_row_payload` currently construct only Roadmap-derived rows. Reject add, edit, or remove operations targeting an inherited decision before merge; do not allow the decoder to convert it to an uncited row. An unrelated operation leaves inherited rows unchanged in the candidate. Pass the current brief's typed records to the candidate gate in `_run_bounded_stage_feedback`, so stale citations refuse before publication. Source-owned changes require an updated approved brief and, for a material decision change, a successor lineage.

## Tests

### Tests for this step

- `test_carried_decision_context_reaches_only_its_owning_stage` — a carried record assigned to each artifact appears only in that stage’s rendered prompt and never in another stage prompt.

- `test_stage_prompt_renders_all_carried_decisions_for_its_artifact` — multiple carried records for one owning artifact all reach that stage together.

- `test_stage_prompt_preserves_carried_decision_fields_needed_for_inherited_row` — the rendered context includes the approved decision facts and citation needed to author the step-2 inherited row form.

- `test_domain_prompt_explains_inherited_decisions_without_roadmap_rationale` — `plan_tool/prompts/roadmap-domain.md` directs the model to preserve supplied inherited rows without invented deliberation.

- `test_constraints_prompt_explains_inherited_decisions_without_roadmap_rationale` — `plan_tool/prompts/roadmap-constraints.md` carries the same local inherited-row rule.

- `test_components_prompt_explains_inherited_decisions_without_roadmap_rationale` — `plan_tool/prompts/roadmap-components.md` carries the same local inherited-row rule.

- `test_plans_prompt_explains_inherited_decisions_without_roadmap_rationale` — `plan_tool/prompts/roadmap-plans.md` carries the same local inherited-row rule.

- `test_invalid_carried_decision_gate_refusal_does_not_overwrite_stage_artifact` — a response refused by the real inherited-decision gate leaves the prior artifact bytes unchanged.

- `test_invalid_carried_decision_gate_refusal_leaves_seed_state_and_seed_files_unchanged` — a refused response does not mutate seed state, draft seeds, or promoted seeds.

- `test_carried_decision_routing_keeps_reentry_without_model_authorship` — a feedback-free re-entry re-gates existing artifacts without invoking a prompt path that adds inherited rows.

- `test_raw_carried_block_is_not_shared_brief_context` — other stages never see the JSON block through the common brief prompt.

- `test_bounded_feedback_cannot_mutate_inherited_decision` — `tests/test_roadmap_revision.py` refuses add, edit, and remove operations on source-owned rows before merge.

- `test_unrelated_bounded_feedback_preserves_inherited_row_and_regates_source` — an unrelated operation keeps the inherited row and refuses publication if its current citation is stale.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A carried decision appears in the rendered prompt for the stage whose artifact owns its anchor and appears in no other stage prompt.

- Each affected prompt tells the model how to preserve supplied inherited decisions while retaining the existing route for Roadmap-derived decisions.

- `plan_tool/roadmap.py:_run_stage` still runs the stage gate before `plan_tool/roadmap.py:_run_roadmap` calls `publish_stage_artifact`.

- A carried-decision gate refusal leaves an existing stage artifact unchanged.

- A carried-decision gate refusal leaves draft seeds, promoted seeds, and seed state unchanged.

- Existing feedback-free re-entry remains a no-write, no-model-call route when its artifact passes gates.

- Bounded feedback cannot convert an inherited row into a Roadmap-derived row; unrelated feedback preserves and re-gates inherited provenance.

- `tests/test_roadmap.py` passes with the added routing, prompt, overwrite, and seed-preservation coverage.

## References

- [ROADMAP_FORMAT.md — Read the Roadmap artifact and decision-row contract that prompts must describe without weakening.](../../../../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read the repository’s source, validation, and durable-publication expectations.](../../../../DATA_CONTRACT.md)

- [Roadmap AI-DLC intake comparison — Read the selected #384 scope and the held multi-source alternative.](../../../../docs/evidence/roadmap-aidlc-intake-comparison-20260916.md)

- [Roadmap AI-DLC integration delivery handoff — Read the agreed delivery order and non-goals.](../../../../handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md)

## Applicable guardrails

- **The plan’s “## Plan intent”, inherited-row distinction** — This step may route approved inherited rows, but it must not blur them with Roadmap-derived decisions or create source authority for other artifact content.

- **The plan’s “## Step intent”, owning-artifact publication** — This step may deliver each carried row to its owning authoring stage only; it must not widen routing to handwritten, legacy, re-entry, or non-stage routes.

- **The plan’s “## Scope guardrails”, source authority boundary** — Keep carried-decision input limited to selected decision rows. Do not add new writer, lifecycle, rebind, or prompt authority beyond this stage-scoped delivery.

- **The plan’s “## Scope guardrails”, rebind safety** — Revalidation may block a later publication, but this step must not make baseline-only rebind mutate artifacts, feedback, or seeds.

- **The plan’s “## Out of scope”** — Do not add supplementary sources, generic source roles, broader identity handling, open-question workflows, or runtime-specific behavior while routing these rows.
