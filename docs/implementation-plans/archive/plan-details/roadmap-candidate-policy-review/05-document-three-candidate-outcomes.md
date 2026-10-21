> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the three candidate outcomes, retire BACKLOG.md #354, and reconcile the roadmap and Integration backlog arcs

## Summary

Document the landed three-outcome candidate-materialization contract in `ROADMAP_FORMAT.md`, using the final names and behavior from steps 1–4. Remove the completed #354 item from `BACKLOG.md`, then update both backlog arcs so they describe the delivered lifecycle rather than a pending capability. Keep the existing candidate review and accepted-head promotion as the only authority path. On green, the format reference, backlog, arcs, and drift guard all describe the same shipped state.

## Table of Contents

- [Summary](#summary) — The completed documentation and backlog result.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — The stale lifecycle descriptions this step removes.
- [Input](#input) — The landed lifecycle facts and existing documentation guard.
- [Files (creates vs edits)](#files-creates-vs-edits) — The documentation and test files in scope.
- [Implementation](#implementation) — The three-outcome contract, retirement, and arc updates.
- [Tests](#tests) — Documentation drift checks and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Record-validation references behind the documented contract.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries the documentation must preserve.

## Why

`ROADMAP_FORMAT.md`, `BACKLOG.md`, and both backlog arcs describe the relation-impact route as pending while steps 1–4 establish a bounded review-required path. Leaving those statements in place makes a valid exact impact appear to remain a terminal `relation-authority` refusal, and it obscures that the existing question, answer, seal, and promotion lifecycle remains the only approval route.

## Input

- **Landed candidate contract:** Read the final behavior from step 4 in `plan_tool/roadmap_candidate.py:materialize_candidate` and `CandidateMaterializationResult`. The landed record names and outcome arms win over terminology in this plan or its earlier detail files.
- **Stored review lifecycle:** Use `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal`, `plan_tool/roadmap_candidate_review.py:generate_candidate_question`, `answer_candidate_question`, `request_replacement`, and `seal_review` to describe the established candidate path.
- **Canonical authority:** Preserve the accepted-head boundary owned by `plan_tool/roadmap_versions.py:AcceptedRoadmapHead`, `load_accepted_version`, `plan_tool/roadmap_version_promotion.py:promote_review_seal`, and `plan_tool/roadmap_view.py:load_roadmap`.
- **Documentation guard:** Extend `tests/test_roadmap_format.py:_immutable_candidate_version_reference_block` and `test_immutable_candidate_version_reference_matches_landed_authority_contract` rather than creating an unconnected documentation check.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — document the ordered materialization outcomes and their existing review, replacement, and promotion boundaries.
  - `tests/test_roadmap_format.py` — guard the documented outcome order, lifecycle authority, and backlog/arc retirement against drift.
  - `BACKLOG.md` — remove the completed active #354 record.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — replace the pending #354 route with the delivered candidate-policy lifecycle.
  - `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` — update the candidate-policy boundary and dated finding ledger to point to the delivered route without authorizing a Integration mutation.

## Implementation

- **Foundational logic:** document the ordered three-outcome materializer contract.

- **Use the landed outcome names.** After step 4 lands, update the `ROADMAP_FORMAT.md` `### Immutable candidate-version authority` reference using the final `CandidateMaterializationResult` representation. Do not preserve a proposed type or field name when the landed code selects another clear name.

- **State the required ordering.** Describe hard refusal first, review-required candidate second, and gate-clean candidate third. A hard refusal must publish no candidate; review-required classification must occur only after ordinary authority, rendering, relation, and roadmap checks pass; gate clean must apply only when no review requirement remains.

- **Describe the containment proof precisely.** State that every review-required-lineage replacement, including a gate-clean result, recomputes candidate-impact atoms and must be contained by the initial disclosure. Preserve repeated relation occurrences in the documented comparison; do not describe a set-membership or identity-equality shortcut.

- **Keep valid candidates inert.** Document that review-required and gate-clean candidates use the established candidate-review lifecycle, while a hard refusal cannot enter it. The selected feedback remains the user request, and the existing question and opaque answer remain the only review exchange.

- **Describe the review and replacement boundaries as deterministic facts.** Record that the existing review result renders the stored requirement beside its one opaque-question response, and that review-required replacements compare recomputed impact facts with the initial disclosure, reuse the initially admitted capsule, and refuse when their predecessor is no longer the accepted head. Do not describe opaque answer text as approval or semantic validation.

- **Keep promotion as the sole canonical write.** Retain the existing statement that only `plan_tool/roadmap_version_promotion.py:promote_review_seal` changes `AcceptedRoadmapHead`; candidate creation, questions, answers, seals, and replacement storage remain inert.

- **Preserve the existing reference block.** Keep the `immutable-candidate-version-authority` markers intact so `tests/test_roadmap_format.py:_immutable_candidate_version_reference_block` continues to select the complete lifecycle contract. Extend that block instead of duplicating outcome rules in a new competing reference section.

- **Retire the active backlog item.** Remove #354 from `BACKLOG.md` rather than moving its planned text to another active backlog section. The completed plan and updated roadmap arc remain the delivery record; do not create a replacement backlog entry.

- **Reconcile the roadmap arc.** Update the candidate-policy paragraphs in `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` from future routing to delivered behavior. Retain a compact route summary and point lifecycle detail to `ROADMAP_FORMAT.md`; remove stale `BACKLOG.md` #354 ownership and planned-status language.

- **Reconcile the Integration arc.** Update `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` so its current candidate-policy boundary describes the delivered three-outcome route. Keep the dated `project-workspace-membership-proof` observation as provenance, but update its resolution to the shipped lifecycle and retain the canonical-delivery gate and no-direct-Integration-mutation boundary.

## Tests

- `tests/test_roadmap_format.py:test_immutable_candidate_version_reference_matches_landed_authority_contract` — asserts the format reference names the final materializer and lifecycle owners.
- `tests/test_roadmap_format.py:test_candidate_policy_reference_orders_hard_refusal_review_required_and_gate_clean` — asserts hard refusal precedes review-required classification, review-required precedes gate clean, and refusal publishes no candidate.
- `tests/test_roadmap_format.py:test_candidate_policy_reference_requires_multiplicity_preserving_containment_for_every_replacement_arm` — asserts the reference covers gate-clean replacements and repeated relation occurrences without treating the impact identity as authority.
- `tests/test_roadmap_format.py:test_candidate_policy_reference_keeps_review_inert_until_exact_promotion` — asserts initial-disclosure containment, initial-capsule reuse, opaque answers, and accepted-head-only promotion remain documented together.
- `tests/test_roadmap_format.py:test_candidate_policy_retirement_reconciles_backlog_and_arcs` — asserts `BACKLOG.md` has no active #354 record and both arcs contain no pending #354 or “until it ships” guidance.

### Verification (non-code step)

The plan’s test-authoring gate does not apply because this step is `non-code`; use these checks instead.

1. Run `uv run pytest tests/test_roadmap_format.py -q`.
2. Confirm `rg -n '#354' BACKLOG.md` returns no matches.
3. Review the immutable-authority block and both arc sections for stale pending-route wording.
4. Run `git diff --check`.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents hard refusal, review-required, and gate-clean outcomes in their required precedence order.
- The format reference states that review-required and gate-clean candidates remain inert until exact review-seal promotion changes the accepted head.
- The format reference states that review-required replacements use the initial capsule and that every result arm, including gate clean, requires multiplicity-preserving containment by the initial disclosure.
- The format reference states that stored requirement facts, rather than model question text, provide the deterministic review disclosure and that stale review-required lineages cannot write replacement or seal artifacts.
- `BACKLOG.md` contains no #354 entry.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` describes the candidate-policy route as delivered and does not assign it to an active backlog item.
- `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` records the delivered route without directing a change to Integration’s accepted roadmap.
- `uv run pytest tests/test_roadmap_format.py -q` passes.

## References

- [Configuration | Pydantic Docshttps: — Use the immutable-record configuration concepts when checking that documentation matches the landed candidate records.
- [Validators | Pydantic Docshttps: — Use the exclusive-outcome validation model when describing the three materializer dispositions.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, single-review contact:** Documentation must not introduce another feedback surface, confirmation action, or authority escape.
- **The plan’s “## Scope guardrails”, policy boundary:** Describe deterministic materializer outcomes without claiming prose interpretation or reviewer-intent judgment.
- **The plan’s “## Scope guardrails”, replacement authority:** State the initial-capsule and disclosed-impact limits without changing the established gate-clean route.
- **The plan’s “## Scope guardrails”, accepted-head authority:** Keep exact review-seal promotion as the only documented canonical-content transition.
- **The plan’s “## Out of scope”, Integration changes:** The Integration arc may describe the route but must not authorize direct accepted-roadmap updates.
