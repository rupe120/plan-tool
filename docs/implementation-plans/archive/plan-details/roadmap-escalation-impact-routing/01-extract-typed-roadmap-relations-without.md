> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Extract typed roadmap relations without changing views or gates

## Summary

Create `plan_tool/roadmap_relations.py` as the single typed source for declared design relations across roadmap artifacts. Refactor `plan_tool/roadmap_view.py:build_citation_map` to consume that source without changing its public output, rendering, modes, or resolution behavior. Add focused extractor tests and extend the gate tests to keep the closed relation inventory tied to existing validation ownership. Green means later impact analysis can read ordered relation records without copying field lists, while existing views and gates behave the same.

## Table of Contents

- [Summary](#summary) — The step’s outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the roadmap needs one relation source.
- [Input](#input) — Existing artifact, gate, and view contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New modules and targeted edits.
- [Implementation](#implementation) — Required relation contract, ordering, and compatibility boundaries.
- [Tests](#tests) — Focused coverage for extraction and unchanged consumers.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/roadmap_view.py:build_citation_map` currently carries a partial, view-specific copy of roadmap relation knowledge, while `plan_tool/roadmap_gates.py` validates a broader set of declared references. Impact routing needs one complete, ordered design-only inventory so later closure code can rely on typed evidence instead of re-creating field lists and silently missing a relation class.

## Input

- **Artifact rows:** Read the immutable row types and collection order from `plan_tool/roadmap_artifacts.py:DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, and `PlansArtifact`. The extractor reads already-parsed artifacts only; it does not read files or parse text.

- **Design-row ownership:** Use the existing stable row identity rules in `plan_tool/roadmap_artifacts.py:design_row_collections` and `plan_tool/roadmap_gates.py:design_row_ids` as context. `FieldRow` and `OrderingEntry` have no own row id, so their relations belong to their containing entity or named plan row.

- **Existing view contract:** Preserve `plan_tool/roadmap_view.py:build_citation_map`, `Citation`, `MODE_CURRENT`, and `MODE_REVIEW`. Its review-only feedback and removal citations remain view behavior, not declared design relations.

- **Gate ownership:** Keep the relation inventory aligned with `plan_tool/roadmap_gates.py:check_entity_references`, `check_constraint_anchors`, `check_decision_records`, `check_component_entity_references`, `check_component_pattern_references`, `check_component_constraint_references`, `check_plan_component_references`, `check_plan_ordering_totality`, and `check_assumption_plan_references`. Extraction reports declared data; gates remain the authority that decides whether it is valid.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_relations.py` — Define the typed declared-relation record, closed kind vocabulary, artifact ownership mapping, and pure extraction entry point.
  - `tests/test_roadmap_relations.py` — Test the complete relation inventory, ownership, direction, ordering, exclusions, and leaf-import boundary.

- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — Make `build_citation_map` derive its existing design-only citations from the new relation source while retaining its current exclusions and review-only citation handling.
  - `tests/test_roadmap_view.py` — Keep the existing citation-map and rendered-view assertions as compatibility coverage; update the leaf-import expectation for the new relation module.
  - `tests/test_roadmap_gates.py` — Add inventory coverage that shows each extracted relation class still has an existing gate owner. Do not change gate behavior or gate ordering.

## Implementation

- **Create one closed, typed relation source.** `plan_tool/roadmap_relations.py` should expose a frozen relation record and an extractor over the four parsed artifact types. Each emitted record needs a closed relation kind, stable owner id, endpoint id, owner artifact key, and declared direction from owner to endpoint. Keep records data-only: no display labels, prose, disk access, view formatting, persistence, telemetry, or backend seam.

- **Emit exactly the declared design inventory.** Cover `FieldRow.entity_id` for reference fields; `BusinessRuleRow.entity_ids`; `WorkflowRow.entity_ids`; `DecisionRow.anchor` in every artifact; `ConstraintRow.anchor_ids`; `ComponentRow.entity_ids`, `pattern_ids`, and `constraint_ids`; `PlanRow.component_ids`; `OrderingEntry.depends_on` and `assumption_targets`; and `AssumptionRow.consuming_plan_ids`. Treat this list as exhaustive rather than discovering fields through generic dataclass inspection.

- **Give nested values a stable owner.** A field relation belongs to its containing `EntityRow`. Both relations from an `OrderingEntry` belong to the `PlanRow` named by that entry’s `plan_id`; the ordering entry does not become a graph node. Every other relation belongs to the row declaring the field.

- **Keep the order deterministic and lossless.** Emit artifact groups in the configured domain, constraints, components, plans order; within each artifact, follow its frontmatter collection order, row order, and declared tuple order. Preserve repeated declared endpoints as repeated relation records rather than deduplicating them. Do not emit reverse records: later closure logic can traverse the stored directions both ways.

- **Keep extraction separate from validation.** The new module should not call gate aggregates, decide whether an id is receipt-safe, or reject a relation merely because its identifier has the receipt-safe grammar. Step 4 owns current-state gate execution. Step 5 checks `plan_tool/roadmap_feedback.py:is_receipt_safe_id` only after step 2 has selected the closure, before any selected owner, endpoint, or node can be persisted, logged, or rendered. An unsafe relation outside that closure remains internal inventory and cannot block a route or escape this module.

- **Keep the relation module below views and orchestration.** Import only the artifact contract needed to inspect row types and artifact keys. In particular, do not import `plan_tool/roadmap_view.py`, `plan_tool/roadmap_gates.py`, `plan_tool/roadmap.py:STAGES`, or receipt and analysis modules. Mirror the four stable artifact keys locally so the extractor remains usable without importing an orchestrator.

- **Preserve the existing citation-map contract.** Refactor `plan_tool/roadmap_view.py:build_citation_map` to use the new records only for the design relation classes it already exposes. Keep `FieldRow.entity_id`, `OrderingEntry.depends_on`, and `OrderingEntry.assumption_targets` out of that map because `render_traceability_walk` owns their presentation. Keep `FeedbackTarget.row_id` and `RemovalRecord.feedback_ids` in the existing review-mode branch, so `MODE_CURRENT` and `MODE_REVIEW` output remains unchanged.

- **Leave gates unchanged.** Keep `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, `PLANS_GATES`, their violation order, and every `check_*` function’s responsibilities intact. The added gate-suite coverage documents the relation-to-gate mapping; it must not turn extraction into another validation path.

## Tests

### Tests for this step

- `test_extracts_every_declared_design_relation_kind` — Asserts one fixture spanning all artifacts emits each of the 12 closed relation kinds and no unlisted kind.

- `test_reference_field_relation_is_owned_by_its_entity` — Asserts a `FieldRow.entity_id` relation uses the containing entity as its owner.

- `test_ordering_relations_are_owned_by_the_named_plan` — Asserts `depends_on` and `assumption_targets` use `OrderingEntry.plan_id` as their stable owner.

- `test_decision_anchors_are_emitted_from_each_artifact` — Asserts `DecisionRow.anchor` is extracted from domain, constraints, components, and plans artifacts.

- `test_relations_preserve_stage_collection_row_and_tuple_order` — Asserts extraction follows the declared artifact and source ordering without sorting.

- `test_repeated_declared_endpoint_is_not_deduplicated` — Asserts repeated entries in a relation tuple remain separate records.

- `test_relation_extraction_excludes_review_and_seed_sidecars` — Asserts feedback targets, removals, draft-seed paths, provenance, and state add no declared relation.

- `test_extraction_retains_untrusted_identifiers_without_emitting_them_to_an_external_surface` — Confirms receipt-safe grammar is not an inventory filter; later selected-closure validation, rather than extraction, owns the persistence boundary.

- `test_relation_module_imports_only_the_artifact_contract` — Asserts `plan_tool/roadmap_relations.py` stays a leaf through both source inspection and an isolated import.

- `test_citation_map_keeps_walk_owned_relations_excluded` — Updates `tests/test_roadmap_view.py` to confirm field and ordering relations remain absent from `build_citation_map`.

- `test_existing_citation_map_and_view_order_remain_unchanged` — Keeps the existing citation labels, fields, stage order, and review-mode behavior stable after the refactor.

- `test_every_declared_relation_kind_has_an_existing_gate_owner` — Adds `tests/test_roadmap_gates.py` coverage tying every extracted kind to its current `check_*` validation owner without modifying a gate.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_relations.py tests/test_roadmap_view.py tests/test_roadmap_gates.py -q` passes.

## Acceptance criteria

- The new extractor returns one typed, ordered record for every declared design relation in the closed 12-kind inventory.

- Every relation record identifies its owner row, endpoint id, owner artifact key, kind, and owner-to-endpoint declared direction; field and ordering relations use their containing stable design owner.

- Extraction preserves artifact, collection, row, and tuple order, including duplicate declared endpoints.

- Feedback, removals, seed metadata, and other review-only or sidecar data produce no relation records.

- `plan_tool/roadmap_view.py:build_citation_map` produces the same public citations and mode-specific behavior as before; it does not add field or ordering citations.

- `plan_tool/roadmap_gates.py` source and gate tuples remain unchanged, and the gate suite identifies a current gate owner for every extracted relation kind.

- The focused relation, view, and gate test command passes.

## Applicable guardrails

- **The plan’s “## Step intent,” bounded design relations:** Limit this step to extraction and compatibility refactoring. Do not add closure traversal, classification, or routing behavior.

- **The plan’s “## Architecture,” closed relation inventory:** Emit only declared design relations and preserve their declared direction and deterministic order. Do not infer relationships from prose or review context.

- **The plan’s “## Out of scope,” existing command and canonical behavior:** Do not change receipt handling, broad generation, canonical artifacts, feedback state, writers, or any backend-facing surface.

- **The plan’s “## Out of scope,” view and gate stability:** Preserve existing rendering and validation contracts while moving relation knowledge behind the new typed source.

## Deferred

- Bidirectional traversal, row and artifact roots, and closure deduplication — step 2 consumes this inventory and owns those graph rules.

- Current-state snapshot gating — step 4 owns complete gate execution over captured artifacts.

- Selected-closure receipt-safe identifier rejection, immutable relation evidence, and route classification — step 5 owns the persistence-facing safety boundary and resulting outcomes. An unsafe disconnected inventory relation stays irrelevant and internal.

- Review-target and removal relationships — remain excluded from this design-only inventory; later analysis uses only the selected receipt target as its root.
