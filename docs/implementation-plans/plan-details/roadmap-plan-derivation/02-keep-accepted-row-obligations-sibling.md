# Step 2 — Preserve accepted obligations in materialized seeds

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/prompts/roadmap-seed.md` to carry the selected accepted row’s responsibilities, sibling prerequisites, source references, and eventual proof requirements into its seed. Use canonical `Testing` and `Acceptance criteria` sections for proof obligations. Extend `tests/test_roadmap.py` to pin these instructions and their delivery through the existing materialization path. Preserve the current artifact schema, accepted-head authority, and tool-owned stack section.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Missing guidance in seed materialization.
- [Input](#input) — Accepted contracts and verification limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Responsibility and proof preservation.
- [Tests](#tests) — Focused instruction and delivery checks.
- [Acceptance criteria](#acceptance-criteria) — Observable completion requirements.
- [References](#references) — Source contracts and orientation.
- [Applicable guardrails](#applicable-guardrails) — Boundaries applied to this step.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

`plan_tool/prompts/roadmap-seed.md`, under “Seed requirements,” preserves intent, non-goals, references, and ordering, but leaves shared production, consumer integration, and sibling handoffs largely implicit. It also requests `Verification`, while `SEED_FORMAT.md`, under “Explicit scope boundaries,” identifies `Testing` as the canonical heading recognized during file-backed ingestion and requires non-negotiable results in `Acceptance criteria`. Clearer materialization instructions keep accepted responsibilities available to plan authoring without reopening the roadmap’s decomposition.

## Input

- **Step 1 output:** Step 1 improves stage-four mapping guidance. This step carries the resulting accepted responsibilities forward; it does not reconsider their assignment.
- **Accepted mapping:** `plan_tool/roadmap_artifacts.py:PlanRow` carries `intent`, `non_goals`, and component ownership. `OrderingEntry` carries `depends_on` and `assumption_targets`; `AssumptionRow` carries statements and consuming plan ids. Read relevant narrative alongside these records.
- **Existing delivery:** `plan_tool/roadmap.py:_render_seed_materialize_prompt` supplies the selected plan id and complete accepted artifact texts. `plan_tool/roadmap.py:_materialize_plan_seed` obtains those artifacts through `load_accepted_roadmap_artifacts`.
- **Verification limits:** Prompt assertions prove instruction presence and delivery. A canned response passing existing validation proves compatibility and preservation of supplied content; it does not prove that a model reliably retains every semantic obligation.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-seed.md` — Clarify responsibility preservation, sibling handoffs, and canonical proof sections.
  - `tests/test_roadmap.py` — Extend seed prompt tests and add focused materialization coverage.

## Implementation

Preserve the implementation boundary chosen by the accepted mapping in the seed’s Outcome, scope and acceptance result. Do not collapse several accepted implementation routes into a generic component-level brief. If the accepted mapping itself remains too broad, surface that limitation through existing roadmap review rather than silently repartitioning it during materialization.

- **Foundational logic: carry accepted responsibility into one bounded seed.** Extend “Seed requirements” in `plan_tool/prompts/roadmap-seed.md`. Use the accepted artifacts already supplied by `plan_tool/roadmap.py:_render_seed_materialize_prompt`; no additional context loader or template variable is required.

- **Preserve the selected row’s complete obligation.** The prompt must direct the author to retain its accepted shared production, consumer integration, required handoffs, and contribution to eventual acceptance wherever the accepted mapping assigns them. Relevant source ids and artifact references must remain identifiable. Do not invent missing assignments.

- **Describe sibling prerequisites without absorbing sibling work.** Carry the selected row’s dependencies and relevant inter-plan assumptions as inputs, expected handoffs, or conditions for its work. Distinguish what this row delivers from what another row supplies. The prompt must prohibit repartitioning accepted rows or implementing a prerequisite merely because the selected row consumes it.

- **Use canonical proof headings.** Replace the requested `Verification` section with `Testing` and add `Acceptance criteria`. Align nearby prose so `Testing` states what proves the selected outcome and `Acceptance criteria` retains its required results. Keep these sections at seed level; do not request fixture lists, source-file inventories, or implementation mechanics.

- **Preserve the kind of proof the source requires.** When accepted artifacts require observed end-to-end behavior or an operational result, the seed must retain that requirement. A restriction on executing application work during seed drafting must not weaken the eventual proof into document inspection or a simulated result.

- **Keep existing authority and ownership unchanged.** Retain provenance keys, component rules, accepted references, intent and non-goals, source-backed risks, repository grounding, and the tool-owned `Stack` instructions. Keep the existing placeholder set. The alternative of adding deterministic semantic checks is outside this step’s purpose.

- **Reuse shared paths unchanged.** `plan_tool/roadmap.py:materialize_plan_seed`, `materialize_and_diff_one_plan`, and `refresh_roadmap_seeds` share the materialization path and inherit the prompt change. `plan_tool/create.py:validate_from_existing_seed` remains the existing structural compatibility check. Do not change their behavior or broaden the general seed authoring prompt in `plan_tool/prompts/distill-seed.md`.

## Tests

### Tests for this step

Add focused cases beside `tests/test_roadmap.py:TestSeedPromptTemplate` and `TestMaterializePlanSeed`. Use the shipped template for instruction-delivery cases, `_StubInvoker` for backend responses, and existing isolated accepted-artifact fixtures. The following proposed tests must all be green before completion:

- `test_seed_prompt_preserves_selected_row_responsibilities_and_source_references` — Asserts explicit instructions to carry accepted production, integration, handoff, and proof obligations with their source references.
- `test_seed_prompt_keeps_sibling_prerequisites_outside_selected_row_scope` — Asserts that prerequisite delivery remains sibling-owned and accepted rows cannot be repartitioned.
- `test_seed_prompt_requests_testing_and_acceptance_criteria_as_output_sections` — Asserts both canonical headings appear in the requested section inventory and `Verification` is no longer requested as an output section.
- `test_seed_prompt_preserves_required_observed_proof_without_authorizing_execution` — Asserts that eventual observed acceptance remains required while drafting stays within its execution boundary.
- `test_materialization_delivers_obligation_guidance_with_accepted_sibling_context` — Captures a prompt rendered from the shipped template and verifies that the new instructions, selected id, relevant accepted dependency and assumption text, and artifact references reach the invoker without unresolved placeholders.
- `test_materialization_preserves_supplied_testing_and_acceptance_sections` — Supplies a conforming canned seed containing distinct proof and handoff statements, then checks that the written draft retains them alongside the tool-owned stack section.

Retain the existing provenance, scope-section, risk, stack ownership, and placeholder tests. Also retain `tests/test_roadmap.py:TestAcceptedVersionSeedRoutes.test_materialize_prompt_embeds_the_accepted_versions_artifact_text` as the accepted-source authority regression.

Run the affected test classes, then `uv run pytest tests/ -q -n auto`. Temporarily remove each new instruction or disrupt the corresponding preservation behavior and confirm its focused test fails; restore the change before finishing. Do not interpret a canned-response assertion as a model-quality measurement.

## Acceptance criteria

- The prompt explicitly carries the selected row’s accepted responsibilities, relevant source references, sibling prerequisites, and eventual proof requirements.
- The requested section inventory includes `Testing` and `Acceptance criteria`, with no requested `Verification` section.
- Sibling handoffs remain inputs or conditions; the selected seed does not gain authority to absorb or repartition sibling work.
- Source-required observed acceptance remains distinct from restrictions on executing work during drafting.
- The shipped template renders with the existing variables and delivers accepted dependency context without unresolved placeholders.
- A conforming canned seed retains its supplied proof sections through materialization and passes existing structural validation.
- Existing accepted-head, provenance, component, risk, and stack ownership regressions remain green.
- Focused tests and the full parallel suite pass.
- The implementation diff touches only the two declared files.

## References

- [Seed format](../../../../SEED_FORMAT.md) — Read “Explicit scope boundaries” for canonical proof headings and seed-level content.
- [Roadmap format](../../../../ROADMAP_FORMAT.md) — Read for accepted-version authority, plan mapping, ordering, and assumptions.
- [Seed materialization prompt](../../../../plan_tool/prompts/roadmap-seed.md) — Read “Seed requirements” and the accepted-artifact inputs before editing.
- [Materialization implementation](../../../../plan_tool/roadmap.py) — Read `_render_seed_materialize_prompt` and `_materialize_plan_seed` for existing context delivery and ownership.
- [Create from existing](../../../how-to/pipeline/create-from-existing.md) — Read for the downstream interpretation of supplied seed sections.
- [Source backlog](../../../../BACKLOG.md) — Read #496 for the effort’s scope and shipment requirements.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing pipeline boundary:** Limit changes to seed instructions and their tests; reuse current materialization.
- **The plan’s “Scope guardrails,” semantic judgment boundary:** Assert instruction delivery and supplied-content preservation without adding semantic validators.
- **The plan’s “Scope guardrails,” accepted authority:** Treat accepted assignments as input; seed drafting must not revise them.
- **The plan’s “Out of scope,” execution boundary:** Preserve eventual application proof in seed prose without performing application work.
- **The plan’s “Out of scope,” allowed reorganization:** Keep shared code and artifact contracts unchanged.

## Deferred

- Seed-to-plan delivery in `plan_tool/create.py` — Step 3 owns retaining supplied obligations through single-plan authoring.
- Cross-stage workflow coverage in `tests/test_roadmap.py` — Step 4 owns the broader mapping-to-create handoff cases; this step tests materialization only.
- Model-quality comparison — Step 5 owns the isolated comparison; canned responses cannot establish generation reliability.
- Changes to `plan_tool/prompts/distill-seed.md` or shared materialization authority — The focused property uses their existing contracts and requires no shared behavior change.
