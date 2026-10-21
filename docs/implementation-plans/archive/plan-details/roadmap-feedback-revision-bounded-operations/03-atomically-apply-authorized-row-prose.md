# Step 3 — Apply authorized row, prose, and ordering operations atomically

## Summary

Extend `plan_tool/roadmap_artifacts.py` with narrow immutable mutation support and `plan_tool/roadmap_revision_patch.py` with a stage-envelope merger. Apply only the typed, context-bound operations from steps 1 and 2, while retaining `merge_feedback_revision` as the unchanged selector-bound local path. Keep row-prose changes limited to issued spans, make plan ordering a companion effect only, and retain each new `RemovalRecord` as continuity evidence. Green means a failed stage merge returns no candidate, while a successful candidate changes only authorized rows, prose, ordering, and feedback responses.

## Table of Contents

- [Summary](#summary) — The step’s outcome and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why typed operations need a deterministic candidate merger.
- [Input](#input) — The artifact, operation, context, gate, and local-route contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six existing files this step changes.
- [Implementation](#implementation) — Immutable candidate construction, prose preservation, ordering companions, and removal evidence.
- [Tests](#tests) — Focused merge, artifact, gate, and local-route regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary documentation for canonical YAML rendering and hermetic tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this merge surface.
- [Deferred](#deferred) — Routing, publication, and structural-patch work that stays later.

## Why

`plan_tool/roadmap_revision_patch.py:merge_feedback_revision` safely handles one selected presentation replacement and response, but it cannot apply the broader typed stage operations without either leaking a general patch surface or risking partial changes. The stage route needs one deterministic in-memory candidate that preserves every unselected row, review record, ordering entry, and body byte before existing gates judge it.

## Input

- **Stage contract from steps 1 and 2:** Consume the landed typed stage-operation result and bounded stage context from those steps. Use their landed names as the source of truth; this step binds and applies them but does not redefine their wire format or authority matrix.

- **Artifact contract:** Use `plan_tool/roadmap_artifacts.py:RoadmapArtifact`, the four artifact dataclasses, `RemovalRecord`, `OrderingEntry`, and the existing renderers. Keep `design_row_collections` as the local design-row view; it intentionally does not define the stage authority of hosting or store rows.

- **Local compatibility:** Preserve `plan_tool/roadmap_revision_patch.py:merge_feedback_revision`, `plan_tool/roadmap_revision.py:RevisionOperations`, and `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`. The local path remains a selected-feedback presentation change plus response.

- **Final validation:** Keep `check_feedback_integrity`, `check_settled_decisions`, `check_plan_ordering_totality`, and `check_assumption_plan_references` as candidate validators. `check_feedback_integrity` resolves every stage-admissible predecessor target, including fixed `hosting` edits and `stores` edits or removals. Update `check_design_row_continuity` to enumerate Components `stores` as valid predecessor/current removal identities, so an authorized cited Store removal passes continuity. Keep `design_row_collections` unchanged as the narrower local presentation selector; neither gate-specific identity set widens that selector.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add narrow immutable helpers or equivalent support for typed stage row insertion, replacement, removal, removal-record retention, and Plans ordering companions without widening the existing local presentation helper.
  - `plan_tool/roadmap_gates.py` — Resolve stage-admissible feedback targets and add the narrow Components continuity identity enumeration that includes stores, without changing the local design-row selector.
  - `plan_tool/roadmap_revision_patch.py` — Add a stage-envelope merge entry point beside `merge_feedback_revision` and retain the local merger’s behavior.
  - `tests/test_roadmap_artifacts.py` — Cover immutable row and ordering mutations across artifact shapes and the hosting/store boundary.
  - `tests/test_roadmap_gates.py` — Pin that a merge-created current-format removal record remains valid continuity evidence under existing gates.
  - `tests/test_roadmap_revision_patch.py` — Cover stage candidate atomicity, authorization, prose preservation, ordering companions, and local-profile regression behavior.
  - `tests/test_roadmap_revision_run.py` — Strengthen the local runner regression proving shared merge work does not widen the selected-feedback route.

## Implementation

- **Build one in-memory candidate.** Add a stage merge entry point alongside `plan_tool/roadmap_revision_patch.py:merge_feedback_revision`. It should accept only the typed stage operations and their context, return a new `RoadmapArtifact`, and raise `RevisionMergeError` before returning a candidate when any operation no longer matches its authorization or source facts. Do not read files, write files, or invoke gates from this merge layer.

- **Keep the merge atomic.** Re-check the context-bound feedback, target row, collection, row identity, and issued prose authority before applying changes. Apply all material operations in accepted envelope order and feedback responses in predecessor feedback order, but expose no partial result if one later operation fails. The loaded artifact must remain unchanged on both success and failure.

- **Keep local mutation narrow.** Retain `plan_tool/roadmap_artifacts.py:replace_design_row` for the local text-field profile. Add separate typed mutation support for stage work rather than broadening its string-only field contract or changing `design_row_collections` to classify `HostingRow` or `StoreRow` as ordinary design rows.

- **Change only the authorized row.** Additions append one typed row to its admitted collection. Edits replace only the selected row while preserving its id and every field the operation is not allowed to change, including the full existing-relation set from step 1: reference-field entity ids; business-rule and workflow entity ids; constraint anchors; component entity, pattern, constraint, and Store ids; plan component ids; ordering links; assumption consumers; and decision anchors. Removals drop only the selected predecessor row after the context proves no surviving current-stage or upstream relation names it. Preserve every unselected row object and every untouched artifact collection.

- **Preserve identity-only boundaries.** A hosting edit must retain its id and facet, and hosting remains outside add and removal paths. Store rows may use the admitted stage row operations but never receive a body-prose amendment. Keep these rules separate from `TEXT_FIELDS_BY_ROW_TYPE`, which remains the local route’s presentation contract.

- **Apply prose against the issued source facts.** Derive the new `artifact.body` only from the exact row-owned spans or append authority issued by step 2. Reject a missing, stale, shared, overlapping, cross-target, or identity-only prose amendment. An edit or removal changes only its own issued span; an addition appends only its authorized fragment. Verify that every byte outside selected spans remains unchanged and that every unselected row’s prose remains unchanged.

- **Keep ordering coupled to plan rows.** For `PlansArtifact`, append exactly the matching `OrderingEntry` with an admitted plan addition and remove exactly the matching entry with an admitted plan removal. Do not add a standalone ordering mutation, reorder existing entries, or alter another plan’s entry. Before removing any row, reject the merge if its selected current-stage or upstream incident relation facts show a surviving reference; this includes ordering, assumption-consumer, decision-anchor, and component-to-Store references. A downstream-only reference is deliberately left to that later stage's re-gate. A plan removal then removes its matching ordering entry only after that general check passes.

- **Retain removal continuity evidence.** A successful removal appends one current-format `RemovalRecord` containing the removed id, supplied rationale, and authorizing feedback id. Keep carried removal records unchanged and do not add retention fields or alter their rendering through `plan_tool/roadmap_artifacts.py:_removal_mapping`. Make `check_design_row_continuity` compare Components stores through a gate-specific identity set that includes `components_design_rows` plus stores, for both predecessor and current rows; do not route this through `design_row_collections` or `TEXT_FIELDS_BY_ROW_TYPE`.

- **Advance feedback only through responses.** Update only the feedback ids the accepted response records name, moving each from `open` to `awaiting-review` with its proposed response. Preserve every unselected feedback target, request, state, and response. Do not add a model-controlled lifecycle field.

- **Keep the existing final boundary.** Render and parse behavior stays owned by `plan_tool/roadmap_artifacts.py:render_domain_artifact`, `render_constraints_artifact`, `render_components_artifact`, and `render_plans_artifact`; publication and gate execution stay outside this merger. The candidate must retain enough continuity evidence for the existing gates to reject an invalid relationship rather than silently repairing it.

## Tests

### Tests for this step

- `test_stage_artifact_mutations_replace_or_remove_only_the_named_tuple_entry` — Verifies immutable row helpers preserve all unselected rows, review collections, and body text.

- `test_stage_artifact_mutations_keep_hosting_and_stores_out_of_design_row_collections` — Verifies stage support does not widen `design_row_collections` or the local presentation surface.

- `test_stage_merge_applies_material_operations_before_feedback_responses` — Verifies accepted operation order produces one candidate with responses applied only after material changes.

- `test_stage_merge_returns_no_candidate_when_any_context_bound_operation_fails` — Verifies an invalid later operation raises and leaves the loaded artifact unchanged.

- `test_stage_merge_preserves_unselected_rows_feedback_removals_and_body_bytes` — Verifies a successful candidate changes no unselected canonical content.

- `test_stage_merge_applies_only_issued_row_owned_prose_spans` — Verifies selected replacements and append fragments work while stale, shared, overlapping, cross-target, and identity-only spans fail.

- `test_stage_merge_adds_and_removes_only_the_matching_plan_ordering_entry` — Verifies plan additions and removals carry their sole ordering companion without reordering or changing another entry.

- `test_stage_merge_rejects_removal_with_surviving_references` — Verifies ordering, assumption-consumer, decision-anchor, and component-to-Store references block removal before a candidate is returned.

- `test_stage_merge_preserves_every_existing_relation_field` — Verifies all relation-bearing edit fields remain unchanged, including membership and order, while additions retain their separately bound predecessor-only relations.

- `test_stage_merge_retains_current_format_removal_evidence` — Verifies a removed row receives one unchanged-format `RemovalRecord` citing its authorizing open feedback.

- `test_dropped_row_with_a_cited_removal_passes` — Extends the existing gate case to prove the merger’s removal record remains acceptable to `check_design_row_continuity`, including an authorized Components Store removal.

- `test_store_removal_continuity_does_not_widen_local_design_row_selection` — Verifies the continuity identity set accepts Store removal evidence while `design_row_collections` and the local presentation profile still exclude stores.

- `test_hosting_ids_stay_out_of_local_design_resolution_but_are_feedback_targets` and `test_store_ids_stay_out_of_local_design_resolution_but_are_feedback_targets` — Verify the primary stage-feedback gate admits those identity-only targets without widening local selector or decision-anchor resolution.

- `test_merge_preserves_unselected_feedback_and_artifact_prose` — Retains the local merger regression for its narrower selector-bound profile.

- `test_valid_local_revision_writes_only_the_selected_artifact` — Retains the runner-level proof that `run_local_feedback_revision` changes only its selected row and feedback item.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A stage merge returns a new typed artifact only when every context-bound operation can apply; otherwise it raises without mutating the input artifact.

- Successful stage candidates preserve all unselected rows, feedback records, carried removal records, ordering entries, and body bytes.

- Prose changes use only issued row-owned spans or an admitted append fragment; no merge path accepts a whole-body replacement.

- A plan-row addition or removal changes only its matching ordering entry and leaves existing ordering unchanged.

- Any row removal with a surviving current-stage or upstream reference, including a Store named by a component, fails before candidate publication; a downstream-only break is the later stage's re-gate result, and a plan removal also removes only its matching ordering entry after the available-reference check passes.

- Every successful row removal retains one current-format `RemovalRecord` citing its authorizing feedback, and continuity accepts a valid result, including a Components Store removal, without widening local row selection.

- `merge_feedback_revision` and `run_local_feedback_revision` retain their selected-feedback-only behavior.

- `uv run pytest tests/test_roadmap_artifacts.py tests/test_roadmap_gates.py tests/test_roadmap_revision_patch.py tests/test_roadmap_revision_run.py -q` passes.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Review the safe-load and safe-dump behavior used by the existing canonical artifact renderers.

- [pytest: How to Monkeypatch/Mock Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Keep local-runner regressions hermetic while asserting the candidate passed to publication.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded canonical change:** Apply only typed, feedback-authorized changes. This step must not accept artifact text, a broad diff, or unselected model-owned content.

- **The plan’s “## Out of scope”, body-edit boundary:** Limit prose work to row-owned amendments and preserve all other body content.

- **The plan’s “## Out of scope”, relation and ordering authority:** Keep ordering effects coupled to admitted plan-row operations and preserve every existing relation field; the stage envelope admits no retarget, membership, or ordering change.

- **The plan’s “## Out of scope”, route compatibility:** Preserve the selector-bound local revision profile and leave structural revision selection and authority unchanged.

- **The plan’s “## Out of scope”, gate and lifecycle behavior:** Keep stage-gate predicates, retry behavior, completed-result behavior, and reviewer-owned feedback transitions unchanged, except that feedback-target resolution admits the stage operations this plan authorizes and continuity includes Store identities. Neither exception widens local selector behavior.

- **The plan’s “## Out of scope”, retention semantics:** Retain only the existing `RemovalRecord` continuity fields and do not add future removal-history behavior.

## Deferred

- **Stage prompt execution and route selection** — Step 5 consumes the stage candidate without widening `plan_tool/roadmap_revision_run.py:run_local_feedback_revision`.

- **Baseline and seed-state publication** — Step 4 adds the trusted baseline and recoverable publication set around a successful candidate.

- **Structural patch consolidation** — `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch` keeps its exact-source rewrite contract; merging it with the typed artifact merger requires separately scoped design work.
