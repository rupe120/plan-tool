> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add deterministic bidirectional impact closure for one roadmap target

## Summary

Create `plan_tool/roadmap_impact_relations.py` and `tests/test_roadmap_impact_relations.py` for the pure closure calculation over one artifact-or-row target. The module consumes step 1’s typed relation inventory and the four parsed roadmap artifacts, then returns ordered node, relation, and artifact evidence. It follows declared edges in both directions while preserving their original direction and source order. Green means later analysis code can classify the complete declared impact without reading views, feedback, prose, or disk.

## Table of Contents

- [Summary](#summary) — The completed closure behavior and its new files.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why a pure closure is needed before routing.
- [Input](#input) — The typed relations, target vocabulary, and artifact rows this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New module and focused tests only.
- [Implementation](#implementation) — Closure membership, ordering, failure, and module-boundary rules.
- [Tests](#tests) — Focused cases that prove the closure contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Later snapshot, safety, routing, and command work.

## Why

`plan_tool/roadmap_view.py:build_citation_map` is a rendering-focused reverse index, not a complete graph: it excludes field and ordering relations and can include review-only citations. The impact workflow needs one deterministic, design-only answer for every row and artifact reached from a selected target. A pure closure module lets later steps use that answer without copying relation fields or treating an escalation reason as evidence.

## Input

- **Step 1 relation inventory:** Consume the ordered typed records landed by step 1 in `plan_tool/roadmap_relations.py`. Step 2 must use that inventory rather than re-reading relation fields or creating a second field list.

- **Parsed design rows:** Use `plan_tool/roadmap_artifacts.py:design_row_collections` to enumerate stable design rows from the four parsed artifacts. This is required for artifact roots and for rows with no declared relation.

- **Target vocabulary:** Accept artifact and row targets through `plan_tool/roadmap_artifacts.py:FeedbackTargetKind`. A row target remains tied to its selected artifact; an artifact target names that artifact’s key.

- **Validation boundary:** Treat full relation validity as a caller precondition. `plan_tool/roadmap_gates.py:check_duplicate_row_ids` and the other stage gates remain step 4’s current-snapshot checks; this module only rejects input it cannot map into one unambiguous closure.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_impact_relations.py` — Define the pure target, node, relation-evidence, and closure result contract plus deterministic bidirectional traversal.
  - `tests/test_roadmap_impact_relations.py` — Cover roots, traversal, ordering, incomplete input, exclusions, and module boundaries.

- **Existing files (edits only):**
  - None.

## Implementation

- **Build a finite declared-relation closure.** Expose a pure entry point in `plan_tool/roadmap_impact_relations.py` that accepts one selected artifact-or-row target, the four parsed roadmap artifacts, and step 1’s ordered relation records. Return immutable closure data suitable for step 5: reached row nodes, reached declared-relation evidence, and distinct owning artifact keys.

- **Use stable node identity.** Represent a reached row by both its artifact key and row id, not by an id alone. `plan_tool/roadmap_gates.py:check_duplicate_row_ids` makes a gate-valid snapshot globally unique, but the artifact key remains required provenance for closure evidence and artifact projection.

- **Root exactly once.** For a row target, start with the one matching stable design row in the selected artifact. For an artifact target, start with every stable design row owned by that artifact, including rows that have no relation. Do not turn `OrderingEntry` or nested `FieldRow` values into nodes; `plan_tool/roadmap_artifacts.py:design_row_collections` defines the stable row set.

- **Traverse both ways without reversing evidence.** Treat each step 1 relation as reachable when either its owner or endpoint is already reached, then add the other node. Preserve the record’s declared owner-to-endpoint direction in emitted evidence even when the traversal reaches it through the endpoint. Do not synthesize a reverse relation record.

- **Terminate cycles and preserve repeated declarations.** Visit each node once so cyclic relations finish. Keep each source relation record once in closure evidence, including repeated declared relations that have equal endpoints; do not collapse evidence into a set of `(owner, endpoint)` pairs.

- **Project results in canonical order.** Determine membership through traversal, then render the result from the original deterministic inputs: nodes in artifact, collection, and row order from `plan_tool/roadmap_artifacts.py:design_row_collections`; relations in step 1 extractor order; artifacts by their first reached node. Do not expose hash-set order, lexical id sorting, or traversal-discovery order as the result contract.

- **Fail closed at the selected-closure boundary.** A malformed target or a row target absent from its selected artifact produces an explicit non-success result with no partial closure. When expansion reaches a relation whose owner or endpoint maps to zero or multiple stable rows, return the same non-success result rather than select a first match or silently drop it. A malformed or receipt-unsafe relation disconnected from the selected component is not closure evidence and cannot block this target; step 5 separately rejects unsafe identifiers that do reach the selected closure before persistence or rendering.

- **Keep the module below views and orchestration.** Import only `plan_tool/roadmap_artifacts.py` and the landed `plan_tool/roadmap_relations.py` contract. Do not import `plan_tool/roadmap_view.py:build_citation_map` or `build_design_row_index`, `plan_tool/roadmap_gates.py`, `plan_tool/roadmap.py:STAGES`, receipt modules, filesystem helpers, or backend seams.

- **Keep safety and routing outside this step.** Do not call `plan_tool/roadmap_feedback.py:is_receipt_safe_id`, inspect feedback or removals, accept receipt reasons, classify a route, or persist evidence. Step 5 owns the selected-closure persisted-id boundary and route precedence; a reason must never add closure members. This module can carry raw typed identifiers only in its in-memory closure result, never to telemetry or a view.

## Tests

### Tests for this step

- `test_row_target_expands_over_incoming_and_outgoing_declared_relations` — A row root reaches both a row it declares and a row that declares it, while each emitted relation retains its owner-to-endpoint direction.

- `test_artifact_target_roots_every_stable_design_row_including_an_isolated_row` — An artifact root includes every row from `design_row_collections`, even when a row has no incident relation.

- `test_closure_visits_each_node_once_and_keeps_cyclic_relation_evidence` — A cycle terminates with unique nodes and retains each declared source relation once.

- `test_repeated_declared_relations_remain_distinct_closure_evidence` — Repeated relation records stay separate evidence entries in their source order.

- `test_closure_projects_nodes_relations_and_artifacts_in_canonical_order` — Output follows artifact, collection, row, and relation order instead of discovery or lexical ordering.

- `test_unmappable_or_ambiguous_relation_returns_no_partial_closure` — Missing or multiply mapped owners or endpoints return the explicit non-success result without a partial node, relation, or artifact list.

- `test_disconnected_unmappable_relation_does_not_block_the_selected_component` — An invalid relation outside the selected component remains absent from its closure, while an incident invalid relation still returns no partial closure.

- `test_row_target_must_be_live_in_its_selected_artifact` — A row id from another artifact or no matching row cannot become a root.

- `test_feedback_removals_seed_data_and_receipt_reason_cannot_expand_closure` — Review-only and sidecar data do not add nodes or relations, and the closure API has no reason-based input.

- `test_impact_relations_module_imports_only_artifact_and_relation_contracts` — Source inspection and isolated import prove the module has no view, gate, receipt, filesystem, subprocess, or backend dependency.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_impact_relations.py -q` passes.

## Acceptance criteria

- A row target returns the complete declared connected component reached through incoming and outgoing step 1 relation records.

- An artifact target includes every stable row in the selected artifact before expanding through declared relations.

- Closure nodes are unique `(artifact_key, row_id)` identities; every source relation record in the closure retains its declared direction and source-order position.

- Output node, relation, and artifact sequences are deterministic and do not depend on hash iteration or traversal discovery order.

- Missing or mismatched roots, and missing or ambiguous mappings reached from the selected component, return no partial closure. A disconnected malformed relation is not selected evidence.

- Feedback, removals, seed sidecars, prose, receipt reasons, views, gates, disk reads, and backend calls do not affect closure membership.

- `uv run pytest tests/test_roadmap_impact_relations.py -q` passes.

## Applicable guardrails

- **The plan’s “## Step intent,” declared closure only:** Limit this step to expanding one target through typed design relations and projecting its owning artifacts.

- **The plan’s “## Architecture,” preserved relation direction and deterministic order:** Traverse relations both ways without adding inferred edges or changing the evidence’s stored direction.

- **The plan’s “## Out of scope,” no operational workflow changes:** Do not create receipts, alter canonical artifacts or feedback state, invoke broad generation, call a backend, or choose a patch.

- **The plan’s “## Out of scope,” no generic graph refactor:** Keep the implementation specific to the closed roadmap relation inventory and its parsed artifact model.

## Deferred

- Current coherent snapshot capture and full gate execution — step 4 owns validation of the exact roadmap bytes before this closure is used for analysis.

- Receipt-safe identifier checks over the selected closure, immutable analysis records, and route precedence — step 5 owns the persistence-facing safety boundary and route result.

- Evidence publication, telemetry, and command wiring — steps 6 through 9 own durable storage, observability, guarded execution, and operator surfaces.
