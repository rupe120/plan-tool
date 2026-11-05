> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document and test roadmap-to-create handoffs and accepted-head boundaries

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `tests/test_roadmap.py` and `tests/test_create.py` to demonstrate context delivery through the existing draft and promoted-seed handoffs. Update `docs/how-to/roadmap.md` to explain how accepted responsibilities reach ordinary plan creation. Reuse existing accepted-head readers, review routes, and create behavior without adding production machinery. Green tests demonstrate delivery of supplied obligations and local References while preserving accepted authority.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Remaining workflow coverage and documentation gaps.
- [Input](#input) — Upstream outcomes and existing contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Handoff coverage and preserved authority.
- [Tests](#tests) — Focused regression cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion requirements.
- [References](#references) — Source contracts and orientation.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries applied here.
- [Deferred](#deferred) — Work outside this step.

## Why

`tests/test_roadmap.py:TestMaterializePlanSeed` proves that materialized and promoted seeds pass create preflight, and `tests/test_roadmap.py:TestAcceptedVersionSeedRoutes` pins accepted-version selection. These checks do not demonstrate the complete delivery of the responsibilities addressed by steps 1–3 into create authoring and published plans. `docs/how-to/roadmap.md`, under “Promote accepted draft seeds, or create directly from them,” already describes both handoffs but needs to explain their context-preservation contract and distinguish normal per-row creation from the direct fallback.

## Input

- **Steps 1–3:** Consume their mapping guidance, materialized obligations, and create context retention. Read the landed implementation before choosing assertions; landed symbols and behavior take precedence over proposed names in sibling details.
- **Accepted artifacts:** `plan_tool/roadmap.py:load_accepted_roadmap_artifacts` supplies canonical content. `tests/test_roadmap.py:TestAcceptedVersionSeedRoutes` provides existing coverage for advanced heads and inert top-level leftovers.
- **Source intake:** `plan_tool/create.py:select_file_backed_source` and `classify_file_backed_source` own source precedence and route selection. Exercise their existing behavior without introducing roadmap-specific intake rules.
- **Verification limits:** Canned responses prove that supplied context reaches prompts and published output. They do not prove semantic completeness, model understanding, or reliable implementation of the resulting plans.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `tests/test_roadmap.py` — Extend existing materialization, promotion, and accepted-version cases with focused handoff assertions.
  - `tests/test_create.py` — Cover both seed sources reaching authoring and publication, plus ordinary file-backed compatibility.
  - `docs/how-to/roadmap.md` — Clarify context delivery, accepted-head authority, review boundaries, and the separate direct fallback.

## Implementation

- **Foundational logic: demonstrate context delivery without transferring scope authority.** Test the existing accepted mapping → materialized seed → ordinary create path. The step must add coverage and explanation within the declared files; it must not introduce a second workflow or production semantic checker.

- **Compose the real handoff seams.** Extend `tests/test_roadmap.py:TestMaterializePlanSeed` around `test_materialized_and_promoted_seed_passes_create_preflight`. Use actual materialization and promotion with injected backend responses, then exercise create with the resulting seed text. Place create-specific prompt and publication assertions in `tests/test_create.py`, following `TestFileBackedSourceIntake` and `TestTrackedRoadmapReferences`.

- **Cover both supported sources.** The slug-relative draft and its promoted copy must each deliver the selected row’s supplied responsibilities, sibling prerequisites, proof obligations, and local References into create authoring and the published plan. Use distinguishable fixture content so assertions identify the source obligation rather than merely finding a generic heading. Do not require identical generated plans from the two routes.

- **Retain upstream ownership.** Steps 1–3 own the prompt and retention changes. Reuse their test coverage where it already proves a requirement; add only the missing composition checks here. A sibling prerequisite must remain context for the selected plan rather than becoming an instruction to absorb the sibling’s work.

- **Preserve accepted-head selection.** Extend `tests/test_roadmap.py:TestAcceptedVersionSeedRoutes` where needed to connect accepted content to the tested handoff. Its `test_materialize_prompt_embeds_the_accepted_versions_artifact_text` and `test_loader_never_falls_back_to_top_level_files_beside_an_accepted_head` already pin important boundaries. Use distinct accepted and leftover markers to prove which content reaches materialization; reuse the existing no-head refusal cases rather than creating another loader.

- **Preserve review authority.** Materialization must remain draft production, seed acceptance must remain the existing digest-recording operation, and promotion must remain the existing opt-in copy operation. Retain the coverage in `tests/test_roadmap.py:TestAcceptRoadmapSeed` and `TestApplyRoadmapSeeds`; neither context delivery nor successful create may imply candidate approval or accepted-head advancement.

- **Keep ordinary create behavior visible.** Extend `tests/test_create.py:TestFileBackedSourceIntake` with a plain file-backed seed using the relevant retention path. Keep roadmap-specific research expectations separate in `TestTrackedRoadmapReferences`. The new tests must not require roadmap metadata for ordinary creation or change existing source selection.

- **Document the normal route before its exception.** Update `docs/how-to/roadmap.md`, under “Stage 4 — read the plan mapping before creating plans,” “Promote accepted draft seeds, or create directly from them,” and “Continue as an ordinary plan,” only where those sections need the clarified contract. Explain that accepted row responsibilities travel through the chosen seed, while create grounds the bounded plan against current code. Link to `docs/how-to/pipeline/create-from-existing.md` for intake details.

- **Keep the direct fallback separate.** Clarify `docs/how-to/roadmap.md` under “Direct fallback” against the current accepted-head lifecycle. It must describe deliberate seed authorship outside the normal per-row handoff without suggesting that materialization repartitions accepted rows or that immutable artifacts are edited directly. Retain links to the existing feedback and review procedure for changes to accepted scope.

- **Keep documentation edits bounded.** Prefer existing headings. If a heading changes, check inbound anchors before renaming it. Update repeated handoff explanations within `docs/how-to/roadmap.md` together without turning this step into a general command-guide rewrite.

## Tests

### Tests for this step

The following proposed test names describe the required invariants. Extend equivalent cases from steps 2–3 instead of duplicating them. Every added or changed case must be green before this step finishes.

- `tests/test_roadmap.py:test_both_seed_handoffs_deliver_materialized_obligations_to_create` — Both the real draft and promoted copy provide create with the selected row’s supplied responsibilities, sibling prerequisites, proof obligations, and local References.
- `tests/test_roadmap.py:test_materialization_uses_advanced_accepted_head_and_ignores_leftovers` — Materialization receives the advanced accepted content and excludes conflicting top-level leftovers.
- `tests/test_roadmap.py:test_seed_handoffs_leave_accepted_head_and_artifacts_unchanged` — Materialization, seed acceptance, promotion, and create leave the accepted head identity and stored artifact bytes unchanged.
- `tests/test_create.py:test_draft_and_promoted_sources_retain_obligations_in_authoring_and_publication` — Parameterized source routes retain supplied obligations and local References in captured authoring input and the published plan.
- `tests/test_create.py:test_ordinary_file_backed_seed_retains_context_without_roadmap_metadata` — Plain file-backed creation retains supplied context without acquiring roadmap-specific prerequisites.

Use isolated filesystem fixtures and injected invokers. Mark cases that drive orchestrators across modules as integration tests. Run focused cases during development, then the affected modules and the required full suite. Temporarily remove a retained field or substitute leftover content to confirm the corresponding assertion fails; restore the implementation before final verification.

## Acceptance criteria

- Both supported seed sources pass through actual handoff operations and ordinary create with the supplied context present in authoring input and published output.
- Accepted-head tests distinguish current accepted content from conflicting leftovers and retain existing no-head refusal coverage.
- The handoff operations leave accepted artifact bytes and accepted-head identity unchanged.
- Ordinary file-backed create remains usable without roadmap metadata.
- `docs/how-to/roadmap.md` explains responsibility preservation, optional promotion, review authority, and the separate direct fallback without introducing another workflow.
- New and changed tests pass in `tests/test_roadmap.py` and `tests/test_create.py`; the full suite passes.
- Every added documentation link and symbolic citation points to an existing target.
- The implementation diff remains within the three declared files.

## References

- [Roadmap format](../../../../ROADMAP_FORMAT.md) — Read “Draft seeds under the roadmap slug” and “Immutable candidate-version authority” for source and lifecycle boundaries.
- [Roadmap walkthrough](../../../how-to/roadmap.md) — Update the existing mapping, handoff, fallback, and continuation sections.
- [Create from existing material](../../../how-to/pipeline/create-from-existing.md) — Reuse the intake and retention explanation owned by step 3.
- [Seed format](../../../../SEED_FORMAT.md) — Use canonical proof and scope sections in handoff fixtures.
- [Roadmap orchestration tests](../../../../tests/test_roadmap.py) — Reuse materialization, promotion, and accepted-head test anchors.
- [Create tests](../../../../tests/test_create.py) — Reuse file-backed intake and tracked-roadmap reference coverage.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing workflow:** Keep this step’s changes in tests and the walkthrough; exercise existing production entry points.
- **The plan’s “Scope guardrails,” context for judgment:** Assert delivery of supplied content without adding semantic agreement checks or treating green fixtures as proof of model quality.
- **The plan’s “Scope guardrails,” accepted authority:** Keep accepted-head selection and review decisions with their current owners.
- **The plan’s “Out of scope,” workflow expansion:** Keep the documentation and fixtures inside the plan’s listed exclusions; do not turn the handoff tests into downstream orchestration.

## Deferred

- Production context-retention changes — Owned by steps 1–3; this step verifies their composition.
- Changes to shared source authority or lifecycle — `plan_tool/roadmap.py:load_accepted_roadmap_artifacts` and `plan_tool/create.py:select_file_backed_source` remain unchanged; any required policy change needs separate intentional scope.
- Live model quality measurement — Canned handoff tests establish delivery, not success rates across real briefs.
