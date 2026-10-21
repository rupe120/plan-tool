> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Define closed impact identity, immutable analyses, and route precedence

## Summary

Create `plan_tool/roadmap_impact_analysis.py` and `tests/test_roadmap_impact_analysis.py` as the pure contract for a valid impact-routing analysis. The module binds one validated receipt, step 4 snapshot, and step 2 selected closure into a frozen, canonical JSON record with a semantic id that is also its final name. Its key decision is that `invalid` is a transient build result, while only `same-artifact`, `cross-artifact`, and `requires-scope-review` can become immutable analyses. The record owns route class, while the later runner owns the separate `created`/`reused` publication fact. Green means a later runner can safely distinguish an exact reuse from every collision without recomputing identity rules.

## Table of Contents

- [Summary](#summary) — The completed contract and observable result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why impact evidence needs one closed identity and route rule.
- [Input](#input) — The receipt, snapshot, closure, and safety contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new analysis-contract files.
- [Implementation](#implementation) — Immutable schema, validation, routing, and collision rules.
- [Tests](#tests) — Focused cases that prove the analysis contract.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Primary references for strict JSON, models, and hashing.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Storage, telemetry, runner, and CLI work owned later.

## Why

`plan_tool/roadmap_escalation.py:EscalationReceipt` proves one selected feedback target needs a closed, redacted identity, but it does not describe the current snapshot or declared impact. Without an equivalent analysis contract, later publication could treat a reason as evidence, reuse an occupied final with different bytes, or persist an `invalid` result as if it were a durable route.

## Input

- **Step 2 closure:** Consume step 2’s successful `plan_tool/roadmap_impact_relations.py` selected-closure result, including its ordered node, relation-evidence, and owning-artifact sequences. Do not recreate relation extraction or traversal here.

- **Step 4 snapshot:** Consume step 4’s `plan_tool/roadmap_impact_snapshot.py` immutable current snapshot, including its stage-ordered artifact digests, source-record digest, decoded-text brief digest, and parsed selected artifact.

- **Receipt contract:** Validate the selected receipt through `plan_tool/roadmap_escalation.py:parse_receipt`, `validate_receipt_final_name`, and `validate_receipt_source_path`. Recheck its target against the captured selected artifact through `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback`.

- **Safe identifiers:** Apply `plan_tool/roadmap_feedback.py:is_receipt_safe_id` to every artifact key and row id copied from the selected closure evidence. Reject unsafe selected evidence; never sanitize, truncate, or drop it. An unsafe relation outside the selected closure remains internal to steps 1 and 2 and is not an analysis input.

- **Canonical identity:** Follow the canonical hashing rule in `plan_tool/checkpoint.py:compute_input_hash` and the strict JSON shape in `plan_tool/roadmap_escalation.py:receipt_semantic_preimage`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_impact_analysis.py` — Define the frozen analysis schema, receipt-and-snapshot binding, semantic identity, route classifier, strict parser and renderer, and exact occupied-final comparison.
  - `tests/test_roadmap_impact_analysis.py` — Cover valid construction, strict decoding, safe evidence, route precedence, immutable identity, and reuse versus collision.

- **Existing files (edits only):**
  - None.

## Implementation

- **Make one pure analysis boundary.** Expose `build_impact_analysis` in `plan_tool/roadmap_impact_analysis.py` as the only operation that combines a receipt, current snapshot, and step 2 closure. It must return either a valid `ImpactAnalysis` or a distinct `invalid` result with no partial analysis to persist.

- **Define a closed frozen record.** Model `ImpactAnalysis` after `plan_tool/roadmap_escalation.py:EscalationReceipt`: strict, extra-field-forbidden, immutable, and versioned. Its semantic fields must cover the receipt final name and semantic id; receipt selector, target, reason, and source digest; ordered snapshot digest evidence including raw-source-record and decoded-brief digests; ordered selected-closure evidence; route class; and nullable `next_workflow`. Do not add mutable `created`/`reused`, exit-status, or lifecycle fields: the runner and telemetry report those independently.

- **Keep the record redacted.** Copy only the listed safe facts. Do not retain a brief path or text, artifact contents, feedback request or response prose, removal rationale, receipt creation time, review state beyond the receipt facts required for validation, or mutable publication status.

- **Revalidate against captured data.** Before construction, prove that the receipt final name and configured source path are valid, its source digest matches the captured selected artifact, and `select_receipt_feedback` accepts the same selector, reason, and target from that captured artifact. Do not reread disk or use a second artifact snapshot.

- **Validate closure evidence defensively.** Require the selected artifact to appear in the closure’s ordered artifact projection, require its artifact projection to agree with the reached nodes, and require every selected node plus every selected relation owner and endpoint id to be receipt-safe. Step 2 remains the owner of traversal correctness; this step rejects a malformed or unsafe selected result rather than repairing it. Do not inspect or reject raw inventory that was disconnected from this selected closure.

- **Classify routes in one precedence order.** Keep `invalid` outside `ImpactAnalysis`. For valid inputs, a one-artifact closure with reason `cross-artifact-impact` yields `requires-scope-review` and `next_workflow: null`; a multi-artifact closure yields `cross-artifact` and `roadmap-cross-artifact-revision-transaction`; every other one-artifact closure yields `same-artifact` and `roadmap-same-artifact-structural-revision`. Receipt reason never adds nodes or artifacts.

- **Make identity fully deterministic.** Add `impact_analysis_semantic_preimage`, `impact_analysis_semantic_id`, and `validate_impact_analysis_final_name` with the same canonical JSON rules as `plan_tool/roadmap_escalation.py:render_receipt`. The semantic id must hash every semantic field, equal the record’s opaque final name, and exclude no field that affects routing or evidence.

- **Parse and render strictly.** Provide `parse_impact_analysis` and `render_impact_analysis` for duplicate-member-free UTF-8 JSON and canonical bytes. Mirror the strict decoding behavior of `plan_tool/roadmap_escalation.py:parse_receipt`; do not import its private decoder helpers or accept equivalent noncanonical JSON as a stored analysis.

- **Give occupied finals one outcome rule.** Provide a pure exact-byte comparison for an existing final and a canonical candidate: only equal canonical bytes are `reused`; any different bytes are `collision`, including malformed data, a valid record with a different final name, or semantically equal content encoded differently. Do not copy `plan_tool/roadmap_escalation_run.py:_classify_existing`, whose receipt-specific invalid-existing outcome has different semantics.

- **Stay below storage and orchestration.** Do not import `plan_tool/roadmap_evidence_store.py`, acquire a writer guard, write evidence, emit telemetry, inspect command arguments, or call a backend. Steps 6 through 9 consume this pure contract.

## Tests

### Tests for this step

- `test_build_analysis_binds_only_receipt_snapshot_and_closure_identity` — A valid captured receipt, snapshot, and closure produce one frozen analysis containing only the allowed safe evidence.

- `test_analysis_schema_is_frozen_closed_and_rejects_mutable_metadata` — Unknown fields, including timestamps and mutable status fields, are rejected and parsed values cannot be changed.

- `test_analysis_json_rejects_duplicate_nonfinite_and_wrong_typed_members` — Strict parsing rejects duplicate JSON members at every persisted-object level, nonstandard constants, floats, and wrong field types.

- `test_analysis_semantic_id_hashes_the_exact_complete_preimage_and_is_the_final_name` — Every route and evidence field affects identity, while the computed semantic id equals the opaque final name.

- `test_receipt_revalidation_uses_the_captured_selected_artifact` — Receipt source, selector, reason, and target must match the step 4 snapshot’s selected artifact without any second read.

- `test_unsafe_or_inconsistent_closure_evidence_is_invalid_and_not_persistable` — Unsafe owner or endpoint ids, a missing selected artifact, or an inconsistent artifact projection produce the distinct invalid result with no analysis object.

- `test_disconnected_unsafe_inventory_cannot_block_or_leak_into_selected_analysis` — A safe selected closure remains valid despite an unsafe disconnected relation in the inventory, while every selected node and relation fact remains safe in the record.

- `test_one_artifact_cross_artifact_reason_requires_scope_review` — A complete one-artifact closure with `cross-artifact-impact` yields `requires-scope-review` and `next_workflow is None`.

- `test_multi_artifact_closure_is_cross_artifact_for_every_receipt_reason` — More than one reached artifact always yields `cross-artifact` and the named cross-artifact workflow.

- `test_other_complete_one_artifact_closures_are_same_artifact` — A one-artifact closure without the uncorroborated cross-artifact reason yields `same-artifact` and the named same-artifact workflow.

- `test_invalid_input_precedes_route_classification_and_reason_never_expands_closure` — Invalid receipt, snapshot, or closure input cannot obtain a route, and changing only a reason cannot add closure members.

- `test_only_exact_canonical_candidate_bytes_are_reused` — Exact candidate bytes yield `reused`; formatted-equivalent, malformed, mismatched-final, and different semantic bytes yield `collision`.

- `test_impact_analysis_module_has_no_storage_or_orchestration_side_effects` — Construction, parsing, rendering, and comparison do not import evidence storage, write files, acquire locks, emit telemetry, or invoke a backend.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_impact_analysis.py -q` passes.

## Acceptance criteria

- A valid receipt, step 4 snapshot, and step 2 closure produce one frozen version-1 analysis with a canonical semantic id and matching final name.

- The persisted analysis contains only safe receipt facts, ordered digest evidence including raw-source-record and decoded-brief digests, ordered selected-closure evidence, route class, and nullable workflow; it contains no source path, content, reviewer prose, timestamp, publication outcome, process status, or mutable lifecycle field.

- Unsafe, incomplete, stale, inconsistent, or invalid receipt, snapshot, or selected-closure input returns transient `invalid` and creates no `ImpactAnalysis`; disconnected unsafe inventory is neither selected evidence nor a route blocker.

- `requires-scope-review` takes precedence for an uncorroborated one-artifact `cross-artifact-impact` receipt; multi-artifact closure takes `cross-artifact`; every other valid one-artifact closure takes `same-artifact`.

- The two routable classes name only their documented follow-on workflows, and `requires-scope-review` has `next_workflow: null`.

- Parsing rejects duplicate or noncanonical analysis JSON, and only exact canonical candidate bytes qualify as reuse for an occupied final.

- `uv run pytest tests/test_roadmap_impact_analysis.py -q` passes.

## References

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Read this for JSON object and duplicate-member interoperability rules.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Read this for duplicate-aware decoding and canonical serialization controls.

- [Configuration — Pydantic](https://docs.pydantic.dev/latest/api/config/) — Read this for strict, frozen, extra-forbidden versioned models.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Read this for the SHA-256 semantic-id boundary.

## Applicable guardrails

- **The plan’s “## Step intent,” bound impact outcome:** Limit this step to pure receipt, snapshot, and closure binding plus route classification.

- **The plan’s “## Architecture,” immutable analysis identity:** Keep the analysis closed, canonical, redacted, and safe to store under its semantic final name.

- **The plan’s “## Architecture,” route precedence:** Preserve the documented invalid, scope-review, cross-artifact, and same-artifact decision order without inferring scope from prose.

- **The plan’s “## Out of scope,” no operational workflow changes:** Do not publish evidence, modify roadmap artifacts or reviewer state, invoke broad generation, call a backend, or choose a patch.

## Deferred

- Evidence namespace registration and durable publication — steps 6 and 8 own storage paths, no-overwrite writes, and temporary cleanup.

- Lifecycle telemetry — step 7 owns recording analysis admission and terminal outcomes.

- Guarded capture, freshness recheck, and retry behavior — step 8 owns the execution sequence around this pure contract.

- CLI creation and coordinated views — step 9 owns argument handling, result rendering, and reader coordination.
