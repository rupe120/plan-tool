> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Retain source obligations and local References through create

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/create.py` so file-backed plan authoring retains source-backed obligations and local References through preparation and publication. Reuse existing source selection, evidence materialization, and publication paths. Preserve supplied local context alongside any applicable reference research without changing research authority or route selection. Green tests demonstrate delivery to authoring prompts and retention in the published plan.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Context at risk during preparation.
- [Input](#input) — Source contracts and verification limits.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Context delivery and publication rules.
- [Tests](#tests) — Focused regression and handoff coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion requirements.
- [References](#references) — Relevant contracts and source anchors.
- [Applicable guardrails](#applicable-guardrails) — Scope constraints applied here.
- [Deferred](#deferred) — Work owned elsewhere.

## Why

`plan_tool/create.py:_prepare_create_plan` replaces the selected input with normalized markdown before downstream authoring. `plan_tool/create.py:_render_distilled_markdown` excludes References, while `plan_tool/create.py:_render_plan_body` gives explicit reference output precedence over seed References. Direct publication already protects its source body; normalized publication also protects materialized evidence sections. The remaining work is to keep the selected seed’s local References available across normalization and publication, and prove that source-backed responsibilities and proof obligations reach plan authoring through those existing protections.

## Input

- **Step 2 output:** Step 2 supplies materialized seeds carrying accepted responsibilities, sibling prerequisites, local references, and canonical proof obligations. Consume that result without changing the accepted assignment.
- **Selected source:** `plan_tool/create.py:select_file_backed_source` selects `seed_body` when present, otherwise `from_description`. Read retained context from that selected source rather than introducing another precedence rule.
- **Preparation evidence:** `plan_tool/create.py:_validate_and_materialize_evidence_sections` materializes evidence-backed fields from source spans. Preserve this contract; model-written summaries do not replace source evidence.
- **Reference publication:** `plan_tool/create.py:_selected_roadmap_references_for_publication` checks selected product research results. Keep its authority over those results while retaining supplied local context separately.
- **Verification limits:** Canned tests prove that supplied text reaches prompts and published output. They do not prove that a model understands or completely implements every obligation.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/create.py` — Retain selected source context across normalized preparation, reference publication, and applicable continuation work.
  - `tests/test_create.py` — Add focused context-delivery, publication, and compatibility regressions.
  - `tests/test_roadmap.py` — Exercise materialized seed delivery into the existing create path.
  - `docs/how-to/pipeline/create-from-existing.md` — Explain local References retention and update the source map where needed.

## Implementation

- **Foundational logic: retain selected source context through normalization and publication.** Work within `plan_tool/create.py:_prepare_create_plan`, `_publish_create_plan`, and `_finalize_create_plan`. Prefer a bounded extension to existing invocation-local state over a separate context loader or artifact.

- **Capture local References before preparation replaces the input.** Use the selected raw source and the existing fence-aware section reader. Preserve its supplied References content, including repository paths, symbolic anchors, source ids, and explanatory notes. Do not require local references to fit the developer-document URL research result shape.

- **Deliver retained context to plan authoring.** Ensure `plan_tool/create.py:propose_steps_from_claude` receives the normalized obligations together with retained source References. Preserve the existing single selected-source rule when `seed_body` and `from_description` differ. Do not substitute the unselected description or append the entire raw source as a competing plan specification.

- **Reuse evidence protection for obligations.** Keep source-backed Testing, Acceptance criteria, and other protected sections on the existing evidence-materialization path. Inspect `plan_tool/create.py:_restore_materialized_evidence_sections` and `_restore_materialized_evidence_and_sync_concepts` before adding any protection. Extend only the missing local-reference behavior; do not create another obligation parser or judge whether source prose and generated steps agree.

- **Keep local context alongside applicable research.** At `plan_tool/create.py:_render_plan_body`, retain supplied local References when generated links or an explicit roadmap References body also exist. Research output must not erase local source context, and retained local context must not count as evidence satisfying selected product research requirements. Preserve existing product disclosures and failure behavior in `plan_tool/create.py:_selected_roadmap_references_for_publication`.

- **Preserve route authority.** Direct sources already retain authoritative References and bypass generic post-write convergence; keep that behavior. For normalized sources, retain local References through applicable reference refreshes, concept synchronization, finalization, and restoration after failure when a published plan remains. Use the existing continuation and restoration boundaries rather than adding a lifecycle.

- **Keep preparation and resume consistent.** Retained References must come from the current selected source on both fresh and resumed calls. Inspect existing checkpoint inputs before changing them; change a hash only if a cached result otherwise depends on context it does not identify.

- **Document the operator-visible result.** Update “Preparation and normalized publication” in `docs/how-to/pipeline/create-from-existing.md` to explain retained local context and its relationship to research. Link to `docs/reference/contracts/seed-ingestion.md` for route and archival rules rather than duplicating them.

## Tests

### Tests for this step

Add or extend the following cases using injected invokers and isolated filesystem fixtures. Every added or changed case must be green before this step finishes.

- `tests/test_create.py:test_normalized_authoring_receives_source_obligations_and_local_references` — Capture the step proposal input and assert source-backed responsibilities, Testing, Acceptance criteria, and local References remain available after preparation.
- `tests/test_create.py:test_retained_context_comes_only_from_the_selected_source` — Supply conflicting source inputs and assert the existing `seed_body` precedence controls retained obligations and References.
- `tests/test_create.py:test_local_references_survive_generated_reference_publication` — Publish with generated reference links and assert the supplied local paths, anchors, and notes also remain.
- `tests/test_create.py:test_local_references_do_not_satisfy_selected_product_research` — Assert local context cannot bypass an existing selected-product research failure.
- `tests/test_create.py:test_normalized_local_references_survive_continuation_and_finalization` — Exercise a reference refresh and concept synchronization that would replace References; assert local context and protected obligations remain in the final plan.
- `tests/test_create.py:test_retained_plan_keeps_source_context_after_continuation_failure` — Force a failure after publication and assert the retained plan preserves the protected source content.
- `tests/test_create.py:test_resume_retains_references_from_the_current_selected_source` — Exercise checkpoint reuse and source changes without carrying stale or unselected References forward.
- `tests/test_create.py:test_direct_source_references_remain_authoritative` — Extend existing direct-route coverage to assert supplied References remain authoritative and no replacement research occurs.
- `tests/test_create.py:test_inline_create_keeps_existing_reference_behavior` — Assert the bounded file-backed change preserves inline authoring behavior.
- `tests/test_roadmap.py:test_materialized_seed_context_reaches_create_and_the_published_plan` — Extend the materialization fixtures around `_prepare_seed_materialization` and `_materialize`; pass the resulting seed into real `create_plan` with fake backend responses and assert context at both authoring and publication boundaries.

Run the affected create and roadmap tests, then the full pytest suite. Mark the cross-module materialization-to-create case as integration coverage. Verify new retention assertions by temporarily removing the retention behavior and observing the relevant tests fail.

## Acceptance criteria

- A normalized file-backed source delivers its source-backed obligations and local References to step authoring.
- The published plan retains supplied local reference paths, anchors, and notes alongside applicable generated research.
- Selected product research requirements and disclosures retain their existing behavior.
- Direct publication, selected-source precedence, and inline compatibility tests pass.
- Applicable continuation, finalization, failure restoration, and resume tests preserve the same source context.
- The materialization-to-create integration case uses the existing handoff and publishes one plan without adding an orchestration path.
- `docs/how-to/pipeline/create-from-existing.md` describes local References retention and points to the existing ingestion contract.
- All added and affected tests and the full pytest suite pass.

## References

- [SEED_FORMAT.md](../../../../SEED_FORMAT.md) — Read “Explicit scope boundaries” for canonical proof sections and source obligations.
- [Seed ingestion contract](../../../reference/contracts/seed-ingestion.md) — Read “Section contract” and “Source authority” for preparation and publication boundaries.
- [Create-from-existing workflow](../../../how-to/pipeline/create-from-existing.md) — Follow the existing route, publication, and archival flow.
- [plan_tool/create.py](../../../../plan_tool/create.py) — Inspect `_prepare_create_plan`, `_render_plan_body`, and the materialized-evidence restoration helpers.
- [ROADMAP_FORMAT.md](../../../../ROADMAP_FORMAT.md) — Read the accepted-version authority and plan mapping contracts.
- [Roadmap plan-set benchmark](../../../evidence/roadmap-plan-set-benchmark.md) — Read the witnessed obligation-retention failures and comparison limits.

## Applicable guardrails

- **The plan’s “Scope guardrails,” existing pipeline:** Keep changes within the existing create handoff; materialization output remains the source supplied by step 2.
- **The plan’s “Scope guardrails,” semantic context:** Test transport and retention of supplied content. Do not add a semantic agreement or completeness checker inside preparation or publication.
- **The plan’s “Scope guardrails,” accepted authority:** Preserve the existing accepted-product research and roadmap source-selection rules.
- **The plan’s “Out of scope,” allowed reorganization:** Limit code changes to the missing context delivery and retention behavior; shared helpers remain unchanged when their existing contracts suffice.

## Deferred

- Mapping and seed-writing guidance — Steps 1 and 2 own the source content; this step carries their output forward.
- Changes to shared heading interpretation — `plan_tool/scope_fence.py:extract_h2_sections` remains the shared reader; this step reuses its current contract.
- Changes to CLI archival and source ownership — `plan_tool/cli/authoring.py:cmd_create` retains its existing responsibilities.
- Semantic retention measurement with real model output — Hermetic transport tests cannot establish model reliability; live benchmark work remains outside this step.
