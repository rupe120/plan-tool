# Step 2 — Build bounded stage-envelope feedback context from the authority matrix, selected isolated row-prose spans, declared relations, and plan ordering

## Summary

Add a stage-only preflight context in `plan_tool/roadmap_revision.py` and a small ordered relation-selection helper in `plan_tool/roadmap_relations.py`. The context projects only active reviewer requests, their permitted targets, selected live-row facts, safe row-owned prose spans, relevant declared relations, and the Plans ordering facts that the stage envelope may use. Preserve `RevisionPreflight` and `parse_revision_operations` as the selector-bound local route. Green means later prompt, parser, and merge work can bind every stage operation to explicit context without receiving a whole artifact body or unrelated row content.

## Table of Contents

- [Summary](#summary) — The stage-context outcome and compatibility boundary.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why bounded operations need a bounded source of facts.
- [Input](#input) — Contracts from step 1, artifacts, relations, and stage order.
- [Files (creates vs edits)](#files-creates-vs-edits) — The four files this step changes.
- [Implementation](#implementation) — Context authority, relation projection, prose spans, and ordering rules.
- [Tests](#tests) — Focused context and relation-contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary reference for immutable source-span identifiers.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this context.
- [Deferred](#deferred) — Merge, prompt, and unrelated relation-consumer work.

## Why

`plan_tool/roadmap.py:_active_feedback_block` currently passes the active requests beside a whole predecessor artifact, while `plan_tool/roadmap_revision.py:RevisionPreflight` only supports one local row. The stage envelope from step 1 needs enough current facts to choose and bind an authorized operation, but giving it unrelated rows or the complete body recreates the drift and prompt-size problem this plan removes. A typed, target-specific context makes missing, ambiguous, or unsafe source facts fail before an operation can reach the merge layer.

## Input

- **Step 1 operation contract:** Consume step 1’s closed stage-envelope records and authority matrix. This step supplies the preflight values that bind those records; it does not redefine their JSON shape or local-route compatibility.

- **Artifact and feedback shapes:** Read `plan_tool/roadmap_artifacts.py:DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, `PlansArtifact`, `FeedbackRow`, `RemovalRecord`, `OrderingEntry`, and `design_row_collections`. The body remains source text for span selection, while typed rows remain the source for row and relation facts.

- **Active-feedback rule:** Follow `plan_tool/roadmap.py:_open_feedback`: `FeedbackState.OPEN` determines stage activity, in artifact order. Do not import the local route’s response-less eligibility rule from `plan_tool/roadmap_revision.py:preflight_feedback_revision`.

- **Relation inventory:** Build from `plan_tool/roadmap_relations.py:extract_declared_relations`, `RoadmapRelation`, and `RelationKind`. Extend that closed inventory with `ComponentRow.store_ids`, which currently has no record, so selected Store removals receive their incoming component references. Its records stay ordered and unvalidated; existing gates still decide whether every reference points to a valid row.

- **Stage order:** Use the artifact-key order established by `plan_tool/roadmap_relations.py:ARTIFACT_KEYS` and matched by `plan_tool/roadmap.py:STAGES`. Context may use the current stage and its earlier artifacts, never downstream stage content. A removal therefore rejects only on current/upstream references available to its bounded context; a downstream break remains the later stage's re-gate result, not hidden downstream prompt payload or rollback authority.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision.py` — Add the typed stage-context preflight, target-specific projections, prose-span selection, relation and reference-id inputs, and Plans ordering context.
  - `plan_tool/roadmap_relations.py` — Add `ComponentRow.store_ids` to the closed declared-relation inventory and a narrow ordered helper that selects relation records touching a supplied row-id set without changing other extraction semantics.
  - `tests/test_roadmap_gates.py` — Record the existing Components gate that owns the new closed relation kind.
  - `tests/test_roadmap_revision.py` — Add focused stage-context fixtures and authority, span, relation, and ordering tests.
  - `tests/test_roadmap_relations.py` — Test the new relation-selection helper and preserve the relation module’s ordered leaf contract.

## Implementation

- **Add a separate stage context.** Add a frozen stage-only context in `plan_tool/roadmap_revision.py`, with a builder such as `build_stage_revision_context`. It should accept the current typed artifact, its stage-ordered upstream artifacts, and the command's resolved `StageFeedbackLimits`, then return only the data needed to bind the stage envelope. Keep `RevisionPreflight`, `RevisionOperations`, `preflight_feedback_revision`, and `parse_revision_operations` unchanged for `--revise-feedback`.

- **Keep the context smaller than an artifact.** Do not retain a whole artifact, a complete body, or unrelated row payloads on the returned context. Expose active feedback, selected rows, permitted row types, concise identifier inventories, selected spans, relation records, and ordering entries as distinct immutable values.

- **Bind feedback one request at a time.** Validate unique retained feedback ids and require every retained row target to identify exactly one live design row or one recorded removal. Include only `open` feedback in stage context, in predecessor feedback order, with its id, target, request, and allowed operation kinds. Do not expose deferred feedback or carried responses as active guidance.

- **Refuse an over-limit active set before invocation.** Count active feedback against the command's resolved item cap before rendering any prompt. An excess returns the stage as `invalid` without invoking the backend, and explains the actual count, the effective limit, and that the reviewer must split the feedback. Do not truncate the set, choose a subset, or turn the excess into a retry.

- **Apply the authority matrix per feedback row.** An artifact target receives response and admitted add-row authority only. A live row target receives response plus edit/remove authority only for that exact typed row and collection. A target found only in `RemovalRecord.removed_id` receives response authority only. Do not merge authority across feedback rows, infer a target from payload fields, or let the presence of an old response remove an otherwise open row from the stage context.

- **Project selected row facts only.** For each live row that active feedback may edit or remove, include its typed current values, collection, and id so the stage parser can reject a cross-row update. Preserve the `HostingRow` fixed-facet rule and the `StoreRow` identity-only rule from the plan’s authority matrix. Do not use `TEXT_FIELDS_BY_ROW_TYPE` as the stage authority source; it remains the narrower local presentation contract.

- **Select relations through one ordered helper.** Extend `plan_tool/roadmap_relations.py` with a `COMPONENT_STORE` relation kind and records for `ComponentRow.store_ids`, plus a helper that selects records from `extract_declared_relations` by owner or endpoint id. Preserve stage order, source order, duplicate endpoints, `RelationDirection`, and `owner_row_index`; do not resolve ids, deduplicate records, or create inferred relations. Use this projection for the selected row’s incoming and outgoing relations, rather than rebuilding a second relation extractor in `plan_tool/roadmap_revision.py`.

- **Provide only the reference facts an operation needs.** Include one frozen concise inventory of live predecessor ids for every relationship-bearing field on every typed addition, and the selected row’s incident current-stage or upstream relation records for edits and removals. This lets later binding reject any same-envelope relation target regardless of operation order and lets the merger reject every existing relation-field edit or removal with surviving available references, including a Store named by `ComponentRow.store_ids`, without embedding downstream artifacts or referenced rows’ prose.

- **Treat Plans ordering as context, not a general relation-edit surface.** For `PlansArtifact`, expose the current ordered `OrderingEntry` facts and earlier plan ids needed for the allowed add/remove companion effects. A plan addition may use only existing earlier plan ids in its companion; a plan removal must see every surviving ordering, assumption, and decision reference that would block it. Do not expose an authority path to reorder an existing plan or retarget an existing relation.

- **Issue prose authority only for an exact isolated source block.** Derive a span from the original `artifact.body`, not from rendered text. Issue an opaque context token and the exact text only when one contiguous block names the selected row id as a whole token, contains no other live design-row id, and does not overlap another issued span. One practical approach is to use blank-line-delimited prose blocks, but the required outcome is an unambiguous, row-owned source span rather than a particular scanner.

- **Fail closed on prose ambiguity.** Do not manufacture a span from a broad section, a whole body, or text shared with another row. When no safe span exists, omit material prose authority for that row so a later operation that names a missing, foreign, shared, or stale span rejects. An addition may receive only an append-only prose slot and must still supply a fragment naming its new row id; `hosting` and `stores` receive no prose surface.

- **Keep validation ownership separate.** This builder proves context identity and boundedness. `plan_tool/roadmap_gates.py:check_inventory_has_prose`, `check_plan_ordering_totality`, and `check_assumption_plan_references` remain the final candidate validators; atomic mutation and byte-preservation checks belong to step 3.

## Tests

### Tests for this step

- `test_stage_context_includes_only_open_feedback_in_predecessor_order` — Includes open rows in source order and excludes deferred rows and carried responses from active guidance.

- `test_stage_context_accepts_reopened_feedback_with_a_prior_response` — Treats an open row as active even when the reviewer kept its earlier proposed response.

- `test_stage_context_rejects_duplicate_feedback_and_unresolvable_row_targets` — Refuses ambiguous feedback ids and row targets that are neither uniquely live nor recorded removals.

- `test_stage_context_binds_each_feedback_to_its_authority_matrix_operations` — Gives artifact, live-row, and removal-only targets their distinct response and material-operation authority.

- `test_stage_context_rejects_more_than_its_effective_active_feedback_limit_before_prompt_or_invocation` — Proves an over-limit active set reports its count and effective split action without selecting a subset or making a backend request.

- `test_stage_context_exposes_selected_typed_rows_without_artifact_or_body` — Includes only selected row values and verifies the context carries neither a whole artifact nor whole body text.

- `test_stage_context_preserves_hosting_and_store_identity_only_exceptions` — Exposes fixed hosting facts and omits prose authority for hosting and stores.

- `test_stage_context_projects_incident_relations_and_predecessor_reference_ids` — Includes the selected row’s incoming and outgoing declared relations, including component-to-Store references, plus the concise live-id facts needed by a permitted addition.

- `test_store_removal_context_exposes_incoming_component_store_references` — Gives a selected Store removal every incoming `ComponentRow.store_ids` record before prompt rendering, so an attempted referenced removal rejects before a candidate reaches the gates.

- `test_stage_context_admits_only_predecessor_relation_targets_for_every_added_row_type` — Gives every relation-bearing add payload the same frozen predecessor inventory, excludes same-envelope and downstream ids, and keeps downstream artifacts out of context.

- `test_stage_context_issues_only_unambiguous_row_owned_prose_spans` — Returns a context-issued token and exact block only for one isolated selected-row span.

- `test_stage_context_omits_ambiguous_shared_overlapping_and_cross_target_prose_spans` — Never broadens a span when the source block is unsafe or belongs to another row.

- `test_plans_stage_context_preserves_ordering_and_blocks_nonpredecessor_companions` — Provides ordered entries and earlier plan ids while excluding existing-plan reordering authority.

- `test_select_declared_relations_for_ids_preserves_order_direction_and_duplicates` — Verifies the relation helper includes both owners and endpoints, including `COMPONENT_STORE`, without changing source order or repeated declarations.

- `test_relation_context_helper_keeps_roadmap_relations_a_leaf` — Keeps the existing `plan_tool/roadmap_relations.py` first-party import boundary intact.

- `test_every_declared_relation_kind_has_an_existing_gate_owner` — Records `COMPONENT_STORE` as owned by the existing component-to-Store definition gate.

Every listed test in `tests/test_roadmap_revision.py` and `tests/test_roadmap_relations.py` must be green before this step is complete.

## Acceptance criteria

- A stage-context builder returns only active-feedback, authorized-row, relation, prose-span, reference-id, and ordering facts; it does not return a whole predecessor artifact or body.

- Every open feedback row has explicit, target-specific stage authority, while deferred and removal-only rows cannot gain material row authority.

- More than the resolved active-feedback limit is an explicit `invalid` input outcome before context rendering or backend invocation; no subset is silently selected.

- Selected relation records preserve `extract_declared_relations` order, direction, and duplicates without resolving or deduplicating identifiers.

- A Store removal sees incoming component-to-Store relation records, while the relation inventory remains a closed, ordered representation rather than a new mutation surface.

- A downstream-only reference is intentionally absent from selected context and is left to the later stage's re-gate; it does not create downstream prompt payload, publication rollback, or a new relation-edit surface.

- A selected prose-inventory row receives a source span only when its exact block is isolated from every other live row; unsafe spans are unavailable rather than broadened.

- Identity-only hosting and store rows receive no body-prose context.

- Plans context exposes only the ordering facts needed for the allowed plan add/remove companions and does not authorize existing-plan reordering or relation retargeting.

- Every relationship-bearing field in an added row binds against the same frozen predecessor-id inventory; no context or operation order admits a same-envelope target.

- `uv run pytest tests/test_roadmap_revision.py tests/test_roadmap_relations.py -q` passes.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use a digest only if an opaque source-span token needs a stable binding to its exact preflight text.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded model input:** Keep context limited to operation-relevant facts; this step must not restore a whole-artifact or authoring-prompt payload.

- **The plan’s “## Out of scope”, body-edit boundary:** Issue only row-owned source spans and append slots. Do not add a generic body editor, diff language, or whole-body replacement.

- **The plan’s “## Out of scope”, relation and ordering authority:** Represent existing relations and ordering as facts for deterministic rejection, never as editable stage-envelope targets.

- **The plan’s “## Out of scope”, route compatibility:** Preserve the selector-bound local revision surface and do not alter structural revision selection or authority.

- **The plan’s “## Out of scope”, gate and lifecycle behavior:** Do not change existing stage gates, retry policy, publication behavior, recovery selection, or feedback-retention semantics.

## Deferred

- **Atomic candidate merge and byte preservation** — Step 3 applies the context-bound operations and proves that rows and prose outside the selected surface stay unchanged.

- **Stage prompt rendering and route selection** — Step 5 passes this context to the bounded stage prompt and retains feedback-free no-op handling outside the model path.

- **Other relation consumers** — `plan_tool/roadmap_structural_revision.py:_resolve_current_closure`, `plan_tool/roadmap_impact_run.py:_resolve_selected_closure`, and `plan_tool/roadmap_view.py:build_citation_map` retain their full-graph relation uses. Changing those routes would exceed this stage-context feature.
