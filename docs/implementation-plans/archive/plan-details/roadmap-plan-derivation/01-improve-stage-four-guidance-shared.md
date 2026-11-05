> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Improve stage-four plan mapping guidance

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/prompts/roadmap-plans.md` to guide responsibility-based plan mapping around shared producers, consumer integration, dependency order, and eventual acceptance. Extend `tests/test_roadmap.py` to pin delivery of that guidance and preserve the existing template contract. Express the guidance through existing rows and prose without adding schema fields or semantic gates. Green tests demonstrate that the instructions reach stage four and remain compatible with its parser and checks.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Gap in the current mapping instructions.
- [Input](#input) — Existing inputs, output contract, and verification limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Mapping guidance and preserved boundaries.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Checks required before completion.
- [References](#references) — Relevant source contracts and evidence.
- [Applicable guardrails](#applicable-guardrails) — Scope constraints applied here.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

`plan_tool/prompts/roadmap-plans.md` specifies row fields, component coverage, ordering validity, and the smallest proof boundary, but gives little guidance on assigning shared production and consumer integration responsibilities across bounded plans. Structurally valid mappings can therefore leave those responsibilities or their eventual proof unclear. `docs/evidence/roadmap-plan-set-benchmark.md`, under “Witnessed failures to retain,” identifies these gaps without establishing that finer granularity fixes them. Improve the mapping instructions so stage four considers the complete implementation route rather than treating component coverage as sufficient.

## Input

- **Generation inputs:** `plan_tool/prompts/roadmap-plans.md`, under “Your inputs,” receives the concept brief and the domain, constraints, and components artifacts. Preserve its instruction to work from supplied text without repository inspection.
- **Existing output contract:** `plan_tool/roadmap_artifacts.py:PlanRow`, `OrderingEntry`, `AssumptionRow`, and `PlansArtifact` provide the available fields and narrative body. Express the added guidance through these existing structures.
- **Verification limits:** Prompt assertions prove that instructions are present and delivered. Canned responses passing the real parser and gates prove structural compatibility; neither establishes that a model usually produces a complete mapping.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/prompts/roadmap-plans.md` — Add concise mapping guidance and align nearby prose where necessary.
  - `tests/test_roadmap.py` — Extend `TestPlansPromptTemplate` with focused instruction and delivery assertions; retain the existing example checks.

## Implementation

Each generated plan has a cohesive implementation outcome, an explicit scope boundary, identifiable prerequisites and a verifiable completion result. Separate independently implementable responsibilities when combining them would leave the route overly broad; splitting steps inside the same broad plan alone does not satisfy this objective. Several plans per component are expected where needed, without imposing a target count. The prompt must ask for this plan-level decomposition explicitly; retaining high-level component rows and merely describing their handoffs is insufficient.

- **Foundational logic: assign complete implementation responsibilities across bounded plan rows.** Add a compact guidance section to `plan_tool/prompts/roadmap-plans.md`, likely before “The frontmatter inventory.” Keep it separate from “The rules your artifact is checked against,” because these are instructions for model judgment.

- **Assign shared producers and consumer integration explicitly.** Direct stage four to identify who produces a shared capability or contract, which plans consume it, and who connects those consumers to the producer. Record those responsibilities using existing row descriptions and plan-id-linked narrative. A producer’s existence alone must not stand in for consumer integration.

- **Choose boundaries by responsibility.** Explain how existing `keep`, `merge`, `split`, and `cross-cutting` dispositions support coherent implementation routes. Preserve support for several plans covering one component. Do not prescribe a plan count, directory-based boundary, or separate plan for every shared concern.

- **Make dependency order reflect required handoffs.** Direct the model to use `ordering.depends_on` for prerequisite plans and describe what consumers need from them. Preserve the existing meaning of `assumption_targets` and inter-plan assumptions; do not turn an unknown prerequisite into an invented settled result.

- **Assign eventual acceptance within the requested outcome.** Require the narrative to identify responsibility for proving that the bounded route works, including integration and observed runtime or deployment evidence when the source outcome requires it. A drafting-only restriction must not replace that eventual completion requirement with document review. This guidance must stay within the prompt’s existing smallest proof boundary.

- **Reuse the existing contract unchanged.** Keep `PlanRow`, `OrderingEntry`, and `AssumptionRow` as orientation, not edit targets. Do not add acceptance fields, producer registries, template variables, or semantic checks. The rejected alternative is a machine-enforced responsibility or coverage model, which exceeds this step’s purpose.

- **Preserve template behavior.** Retain the supplied-input boundary, inherited-decision instructions, strict response format, shared proof-boundary placeholders, and schema inventory. Keep the guidance self-contained rather than directing the model to repository-only reference documents.

- **Extend the existing test home.** Use `tests/test_roadmap.py:TestPlansPromptTemplate` and `_plans_prompt_text()` for focused assertions. For rendered delivery, extend the existing `test_plans_prompt_renders_with_no_unresolved_placeholder` case to inspect the captured fourth-stage prompt. Avoid another orchestrator run solely to repeat the same assertion.

## Tests

### Tests for this step

All added or changed cases in `tests/test_roadmap.py` must be green before this step is finished. Keep direct template checks isolated; use the existing shipped-stage fixture for rendered delivery.

- `test_plans_prompt_assigns_shared_producers_and_consumer_integration` — Assert that the prompt asks for producer ownership, consuming plans, and responsibility for connecting them.
- `test_plans_prompt_sizes_rows_by_responsibility_without_fixed_count` — Assert that the guidance supports existing dispositions and several plans per component without imposing a count or directory rule.
- `test_plans_prompt_orders_required_handoffs_and_keeps_unknowns_explicit` — Assert that prerequisite delivery informs dependencies and unknown assumptions remain visible.
- `test_plans_prompt_preserves_eventual_observed_acceptance_within_source_scope` — Assert that acceptance responsibility follows the requested outcome and drafting restrictions do not weaken eventual proof.
- `test_plans_prompt_renders_with_no_unresolved_placeholder` — Extend the existing case to assert that the new guidance reaches the captured fourth-stage prompt.
- `TestPlansPromptExample.test_prompt_example_parses_through_the_plans_parser` — Retain the real-parser check for the embedded example.
- `TestPlansPromptExample.test_prompt_example_clears_run_plans_gates` — Retain the real-gate check for the embedded example.

Run the affected prompt tests, then the plan’s full test command. Temporarily remove each new guidance clause and confirm that its focused assertion fails; restore it before finishing. These checks pin instruction delivery, not generated-output quality.

## Acceptance criteria

- The guidance explicitly asks for appropriately granular implementation plans and splitting overly broad scopes at the plan level, with cohesive outcomes, boundaries, prerequisites and verifiable completion.

- The stage-four prompt explicitly assigns shared production, consumer integration, prerequisite handoffs, and eventual acceptance responsibilities.
- The guidance uses existing fields and prose; the frontmatter inventory, template variable set, and deterministic gate contract remain unchanged.
- Responsibility-based splitting and merging remain available without a target plan count or directory-based rule.
- Source-required observed acceptance remains distinct from restrictions on drafting or benchmark execution.
- The captured fourth-stage prompt contains the new guidance and no unresolved placeholders.
- The embedded example still parses and clears the existing plans gates.
- Focused tests and `uv run pytest tests/ -q -n auto` pass.
- The implementation diff touches only the two declared files.

## References

- [Roadmap format](../../../../ROADMAP_FORMAT.md) — Read for existing plan dispositions, ordering fields, and accepted-version authority.
- [Stage-four prompt](../../../../plan_tool/prompts/roadmap-plans.md) — Read the input boundary, inventory, checked rules, and example before editing.
- [Pinned benchmark evidence](../../../evidence/roadmap-plan-set-benchmark.md) — Read “Witnessed failures to retain” and “Comparison contract” for the observed gaps and limits on interpretation.
- [Source backlog](../../../../BACKLOG.md) — Read entry #496 for the effort’s scope and shipment bookkeeping.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing pipeline boundary:** Limit this step to mapping instructions and their tests; leave orchestration and materialization behavior unchanged.
- **The plan’s “Scope guardrails,” semantic judgment boundary:** Test that guidance reaches the model. Do not turn responsibility assignment or acceptance quality into output gates.
- **The plan’s “Scope guardrails,” accepted authority:** Prompt changes do not authorize rewriting accepted mappings or bypassing their review routes.
- **The plan’s “Out of scope,” allowed reorganization:** Keep the change local to the declared files and preserve the existing artifact contract.
- **The plan’s “Out of scope,” execution boundary:** Describe eventual application proof without performing application implementation or provider execution.

## Deferred

- Seed responsibility preservation in `plan_tool/prompts/roadmap-seed.md`, under “Seed requirements” — Step 2 owns carrying the accepted row’s obligations into materialized seeds.
- Seed-to-create delivery in `plan_tool/create.py` — Step 3 owns retaining source obligations and references through single-plan authoring.
- Full workflow coverage and accepted-head boundary verification in `tests/test_roadmap.py` — Step 4 owns the cross-stage handoff cases.
- Model hit-rate and witnessed-gap comparison — Step 5 owns the isolated comparison; canned-response tests cannot establish generation quality.
- Changes to `plan_tool/prompts/roadmap-components.md` or shared proof-boundary templates — Their existing contracts remain unchanged; this step improves downstream mapping guidance without changing upstream authority.
