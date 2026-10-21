> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Prove row, relation, decision, order, feedback, and full-snapshot gate invariants

## Summary

Create `plan_tool/roadmap_structural_revision_proof.py` and `tests/test_roadmap_structural_revision_proof.py` for the read-only candidate proof boundary. Compare the step 4 candidate against step 2’s captured predecessor for structural invariants, then run the shared full-roadmap gate traversal from step 1 with the candidate substituted. Keep structural rejection distinct from gate rejection and retain the complete proof binding for step 6. On green, only a canonical candidate that preserves the declared structure and clears every affected gate can proceed to guarded publication.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the existing revision gates are not enough for this bounded rewrite path.
- [Input](#input) — Upstream candidate, snapshot, relation, and gate contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Structural comparison and full-roadmap gate proof rules.
- [Tests](#tests) — Focused proof coverage and green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — Observable proof outcomes.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the proof.
- [Deferred](#deferred) — Work left to publication or later evidence-backed design.

## Why

`plan_tool/roadmap_gates.py:check_design_row_continuity`, `check_feedback_integrity`, and `check_settled_decisions` support general revision and deliberately allow changes this structural command must reject, including approved removals and some decision prose changes. Step 4’s source-span merger constrains how a candidate is built, but publication also needs an independent proof that the parsed candidate preserves row identity, relations, decisions, order, and protected feedback before it enters the complete gate context.

## Input

- **Shared gate traversal:** Step 1 extracts the candidate-aware full-roadmap traversal from `plan_tool/roadmap_impact_snapshot.py:_require_current_gates`. Use its stage order, `plan_tool/roadmap.py:RoadmapStage` artifact-key mapping, and `plan_tool/roadmap_gates.py:ArtifactEnvelope` construction rules.

- **Accepted predecessor:** Step 2 provides the selected stage, selected canonical artifact text and parsed artifact, selected feedback row, full `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot`, and exact receipt/analysis final names with raw digests.

- **Completed candidate:** Step 4 provides the selected candidate text and its parsed artifact. The proof must confirm that candidate data still belongs to the selected stage rather than infer another snapshot position.

- **Structural inventories:** `plan_tool/roadmap_artifacts.py:design_row_collections` preserves design-row collection order, while `plan_tool/roadmap_relations.py:extract_declared_relations` returns declared relations in stage and source order.

- **Snapshot binding:** `plan_tool/roadmap_impact_snapshot.py:_binding` defines the recorded-source digest, brief digest, ordered artifact keys, and raw artifact digests that step 6 must recheck.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_structural_revision_proof.py` — Add the pure structural and full-gate candidate proof boundary, typed proof result, and rejection categories.
  - `tests/test_roadmap_structural_revision_proof.py` — Add fixture-based proof coverage.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Prove that one canonical candidate preserves the selected artifact’s declared structure and clears the complete captured-roadmap gate walk.

- **Expose one pure proof boundary.** Add a public entry point such as `prove_structural_revision_candidate`, a frozen `StructuralRevisionProof` result, and a typed proof error or result category that distinguishes structural rejection from gate rejection. Accept only step 2’s accepted context and step 4’s completed candidate; do not read current files, acquire a writer guard, invalidate seeds, invoke a backend, or publish.

- **Bind the candidate to the selected snapshot position.** Require the selected `RoadmapStage`, its artifact key, its captured predecessor text and parsed artifact, and the candidate’s parsed form to agree. Reparse and render the candidate through the selected stage when needed to prove `RoadmapStage.render(RoadmapStage.parse(candidate_text)) == candidate_text`; do not repair or re-render a mismatched candidate.

- **Compare row identity and collection order separately.** Use `design_row_collections` to require the same collection keys and the same row-id sequence in every collection. Treat `PlansArtifact.ordering` as an ordered structural collection too. This must reject created, removed, moved, renamed, duplicated, or reordered rows without deep-comparing the selected allowed text fields.

- **Compare the complete declared relation inventory.** Build predecessor and candidate relation tuples through `extract_declared_relations`, substituting the candidate into the full captured artifact set at the selected stage. Require exact equality, including relation order; do not infer equivalence from gate success alone.

- **Freeze every decision.** Require the selected artifact’s `decisions` collection to remain exactly equal. `check_settled_decisions` cannot stand in for this rule because its contract intentionally leaves some decision content outside its comparison.

- **Permit exactly one feedback transition.** Require the selected feedback row to retain its id, target, and request, move from its captured open state to `awaiting-review`, and gain the candidate response. Require every non-selected feedback row, including its position, to remain exactly unchanged.

- **Reuse the shared full-roadmap gate traversal.** After structural checks pass, call the step-1 traversal with the candidate substituted at its selected stage and in every later context. Each context must keep `ArtifactEnvelope.predecessor=None`; revision gates must not become an alternate proof path.

- **Retain the full proof binding.** Return enough immutable evidence for step 6 to compare the exact receipt-final and analysis-final names and raw digests plus the complete `RoadmapImpactSnapshot._binding` value. Do not reduce this to the selected artifact digest.

- **Keep the semantic boundary explicit.** A successful proof says only that declared structure and current gates remain valid. It must not classify whether changed text or prose creates a downstream obligation, and it must not turn static impact route metadata into candidate-write authority.

- **Keep generic revision gates separate.** Leave `plan_tool/roadmap_gates.py:check_design_row_continuity`, `check_feedback_integrity`, and `check_settled_decisions` unchanged; their broader revision rules are not this command’s structural contract.

## Tests

### Tests for this step

- `test_proof_accepts_permitted_candidate_and_retains_complete_binding` — Accept a canonical candidate that changes allowed content and the selected feedback transition, then retain both evidence-record facts and the full snapshot binding.

- `test_proof_rejects_candidate_that_is_not_canonical_for_the_selected_stage` — Refuse a candidate whose selected stage parser and renderer do not reproduce its supplied text.

- `test_proof_rejects_row_id_creation_removal_move_duplicate_and_collection_reordering` — Refuse every changed design-row inventory or collection row-id sequence.

- `test_proof_rejects_changed_plans_ordering_sequence` — Refuse a reordered or otherwise changed `PlansArtifact.ordering` sequence even when its rows still exist.

- `test_proof_rejects_changed_declared_relation_inventory` — Refuse a candidate whose full substituted `extract_declared_relations` result differs from the predecessor inventory.

- `test_proof_rejects_all_decision_changes` — Refuse changes to any selected-artifact decision field, including changes the general settled-decision gate does not compare.

- `test_proof_requires_selected_feedback_to_only_advance_and_add_response` — Refuse selected-feedback id, target, request, state, or response shapes outside the one permitted transition.

- `test_proof_rejects_nonselected_feedback_mutation_removal_or_reordering` — Preserve every unselected feedback row and its order exactly.

- `test_proof_uses_shared_full_gate_traversal_with_predecessor_none` — Assert that the candidate reaches its own and later stage contexts through the step-1 traversal while every envelope keeps `predecessor is None`.

- `test_proof_reports_candidate_gate_failure_from_selected_or_later_stage` — Return the gate-rejection category when the substituted candidate fails any affected stage gate.

- `test_proof_rejects_mismatched_selected_stage_or_snapshot_artifact` — Refuse inconsistent caller-supplied context instead of selecting a stage or artifact by fallback.

- `test_proof_does_not_classify_semantic_effect_of_structurally_valid_text` — Accept a structurally valid, gate-clean allowed text change without claiming that it has no downstream semantic effect.

Green-before-done gate: `uv run pytest tests/test_roadmap_structural_revision_proof.py -q` passes.

## Acceptance criteria

- The proof returns a `StructuralRevisionProof` only when the candidate is render-canonical for the selected stage.

- The proof rejects any changed row-id inventory, design-row collection order, plans ordering sequence, declared relation tuple, decision collection, or non-selected feedback row.

- The selected feedback row can change only through the declared review-state transition and proposed response while preserving its identity, target, and request.

- Candidate gate evaluation uses the shared step-1 traversal, substitutes the candidate from its stage onward, and supplies `predecessor=None` in every context.

- The returned proof retains exact receipt and analysis evidence identity plus every `RoadmapImpactSnapshot._binding` member for step 6.

- `plan_tool/roadmap_structural_revision_proof.py` performs no filesystem read, write, lock acquisition, seed invalidation, backend call, or semantic-impact classification.

- `uv run pytest tests/test_roadmap_structural_revision_proof.py -q` passes.

## Applicable guardrails

- **The plan’s intent, one-artifact publication boundary:** Prove only the selected artifact candidate and selected feedback transition; do not create a path that authorizes another artifact.

- **The plan’s step intent, declared-invariant boundary:** Check structural and complete gate-input facts only, and leave semantic effect assessment to the selected feedback review.

- **The plan’s `## Architecture`, complete-binding boundary:** Preserve the full snapshot and immutable evidence facts for final comparison; do not narrow freshness to the selected artifact.

- **The plan’s `## Out of scope`, structural-operation boundary:** Do not add a generic edit, schema, relation, decision, marker, or cross-artifact transaction surface while proving this bounded candidate.

## Deferred

- **Guarded final snapshot comparison and atomic replacement** — Step 6 owns rereading the current inputs under the participating-writer guard and publishing the already-proved candidate.

- **Generic revision-gate consolidation** — Keep `plan_tool/roadmap_gates.py:check_design_row_continuity`, `check_feedback_integrity`, and `check_settled_decisions` separate because their normal revision contract is broader; any shared comparison redesign belongs in reconcile work.

- **Candidate-aware semantic-impact classification** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` leaves this work with BACKLOG #289.
