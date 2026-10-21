> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Bind current receipt and impact evidence without treating the route as write authority

## Summary

Create `plan_tool/roadmap_structural_revision.py` as the read-only exact-pair preflight for structural rewrites, with focused coverage in `tests/test_roadmap_structural_revision.py`. It loads only the requested receipt and impact-analysis finals, verifies their canonical immutable bytes and current full-roadmap binding, then returns a frozen context containing the selected artifact slice, feedback row, target row, snapshot, and raw evidence digests. The key decision is that `same-artifact` and `cross-artifact` routes are evidence for later review, never permission to widen the write set; only `requires-scope-review` refuses here. On green, later steps can start candidate work from one verified current pair without reselecting evidence or trusting stale route metadata.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and affected surfaces.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why exact, current evidence must be bound before rewrite work.
- [Input](#input) — Existing evidence, snapshot, and feedback contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Exact file footprint.
- [Implementation](#implementation) — Exact-pair preflight rules and returned context.
- [Tests](#tests) — Focused coverage for evidence binding and refusal cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Digest API used for immutable evidence binding.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this read-only preflight.
- [Deferred](#deferred) — Work intentionally left outside this step.

## Why

`plan_tool/roadmap_impact_analysis.py:ImpactAnalysis` records a route from one earlier current snapshot, while `plan_tool/roadmap_escalation.py:EscalationReceipt` records only redacted selection facts. Neither record alone proves that the named pair still describes the same current roadmap, current feedback row, and complete snapshot. This step supplies one strict preflight so later candidate construction never treats a stored route as current write authority or silently selects newer, different evidence.

## Input

- **Immutable evidence storage:** `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `_read_exact_existing`, and `scan_evidence` establish the fixed namespace grammar, existing exact-entry primitive, and current listing behavior. This step promotes a public exact-final reader that reads records only by the caller-supplied final names.

- **Receipt contract:** `plan_tool/roadmap_escalation.py:parse_receipt`, `validate_receipt_final_name`, and `validate_receipt_source_path` validate the requested receipt against the configured `plan_tool/roadmap.py:RoadmapStage`.

- **Analysis contract:** `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis`, `validate_impact_analysis_final_name`, and `build_impact_analysis` validate the requested analysis and reconstruct its current immutable identity.

- **Current roadmap state:** `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` supplies the source-record digest, brief digest, stage order, canonical artifact texts, parsed artifacts, and raw artifact digests that the analysis must still match.

- **Selected feedback and target:** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` and `plan_tool/roadmap_artifacts.py:design_row_collections` identify one live selected row. The reviewer request remains private input, but it must contain at least one non-whitespace character.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_structural_revision.py` — Add the read-only exact-pair preflight and its frozen accepted context.
  - `tests/test_roadmap_structural_revision.py` — Add isolated fixture-based coverage for accepted and rejected evidence pairs.

- **Existing files (edits only):**
  - `plan_tool/roadmap_evidence_store.py` — Add the narrow public exact-final
    reader used by this preflight and the guarded step-6 recheck. It must not
    enumerate or read other finals, and it must leave scan behavior unchanged.
  - `tests/test_roadmap_evidence_store.py` — Prove that an exact read opens only
    its requested grammar-valid final and that unrelated unreadable finals do
    not affect it.

## Implementation

- **Foundational logic:** Add an exact-pair current-evidence preflight.

- **Expose one read-only binding entry point.** Provide a small public preflight function and frozen result type, such as `load_structural_revision_preflight` and `StructuralRevisionPreflight`. Accept the explicit receipt and analysis final names plus resolved roadmap inputs; do not accept a selector, route, timestamp, or directory-order fallback.

- **Add one no-enumeration exact-final reader.** Expose a small public reader,
  such as `read_evidence_final`, in `plan_tool/roadmap_evidence_store.py`.
  It validates its namespace and grammar-valid final name, opens only the fixed
  existing namespace without creating it, confirms that exact entry, then reads
  only that entry's bytes. Its typed result distinguishes invalid input, a
  missing exact final, and storage failure without inspecting another
  grammar-matching final. Preserve `scan_evidence` and its listing callers
  unchanged; this reader is the narrow path for named immutable identity.

- **Load exactly the requested records.** Use `read_evidence_final` once for
  the requested receipt final and once for the requested analysis final. Do
  not call `scan_evidence`, filter a listing, or tolerate a different valid
  final. Missing, unreadable, malformed, noncanonical, or
  final-name-mismatched evidence must refuse without choosing another record.

- **Bind the pair in both directions.** Require the parsed analysis’s `ImpactAnalysis.receipt.final_name` and retained receipt facts to agree with the parsed `EscalationReceipt` and the explicitly requested receipt final. Require both parsed records’ own `final_name` values to equal their named storage records.

- **Carry raw evidence digests.** Hash the raw bytes of both named records and retain their final names and digests in the accepted context. Step 6 will use these facts to detect an evidence replacement before publication; do not substitute semantic IDs for raw-record digests.

- **Recapture the complete current roadmap before accepting.** Call `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot` and require the current source-record digest, brief digest, ordered stage keys, and every stage artifact digest to match `ImpactAnalysis.snapshot`. A change outside the selected artifact is still stale evidence.

- **Rebuild the analysis from current facts.** Recreate the selected closure from the captured artifacts through `plan_tool/roadmap_relations.py:extract_declared_relations` and `plan_tool/roadmap_impact_relations.py:resolve_impact_closure`, then use `build_impact_analysis` to require the rebuilt analysis to equal the named analysis. This validates its closure evidence and route against the current snapshot instead of trusting persisted route fields.

- **Return the bounded selected slice.** The accepted context must retain the full `RoadmapImpactSnapshot` for step 5, plus the selected stage, canonical selected artifact text and parsed artifact, selected `FeedbackRow`, target collection, and exactly one live target row for steps 3 and 4. Do not persist this context or expose its reviewer request in failure text.

- **Revalidate selected feedback now.** Require one currently open, response-absent, row-targeted feedback item whose id, target, reason, and selected-artifact digest agree with the receipt. Refuse artifact targets, missing or ambiguous live targets, changed feedback state, and blank or whitespace-only reviewer requests.

- **Keep route metadata informational.** Refuse `requires-scope-review`, but allow both `same-artifact` and `cross-artifact` records to produce the same one-artifact preflight context. Do not branch on `ImpactAnalysis.next_workflow`, authorize additional artifact writes, or claim that a static route proves a candidate’s semantic safety.

- **Keep this module free of side effects.** It may read evidence and current inputs, but it must not acquire `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`, invalidate seeds, invoke a backend, write canonical artifacts, or emit lifecycle events. Later runner and publication steps own those boundaries.

- **Do not import run-owned private helpers.** `plan_tool/roadmap_impact_run.py:_load_requested_receipt` and `_resolve_selected_closure` serve receipt-to-analysis creation. Build this stricter pair validation from their public dependencies rather than coupling the new contract to an orchestrator.

## Tests

### Tests for this step

- `test_preflight_binds_exact_current_receipt_analysis_snapshot_and_selected_slice` — Assert that a valid named pair returns the selected stage, canonical artifact text, parsed artifact, open feedback row, target collection, target row, full snapshot, and both raw evidence digests.

- `test_exact_evidence_reader_reads_only_its_named_final` — Proves the shared
  reader does not open the bytes of unrelated grammar-matching finals and
  reports missing or storage failure without a fallback.

- `test_preflight_reads_only_the_two_requested_evidence_finals` — Asserts that
  missing or mismatched requested names refuse even when other valid receipt or
  analysis records exist, and that an unrelated unreadable final cannot reject
  the named pair.

- `test_preflight_requires_the_analysis_embedded_receipt_identity_to_match_the_named_receipt` — Assert that a valid receipt and valid analysis cannot be combined when the analysis binds another receipt final or retained receipt fact.

- `test_preflight_rejects_noncanonical_or_invalid_evidence_without_returning_partial_context` — Assert that malformed, duplicate-member, noncanonical, or storage-unavailable evidence refuses without exposing parsed records or raw content.

- `test_preflight_rejects_drift_in_each_full_snapshot_binding_member` — Assert that changes to the recorded source, brief, selected artifact, or unselected artifact refuse rather than accepting selected-artifact-only freshness.

- `test_preflight_rebuilds_current_closure_before_accepting_the_analysis` — Assert that changed relation or closure evidence refuses when rebuilding the current `ImpactAnalysis` no longer reproduces the named record.

- `test_preflight_requires_one_open_response_absent_live_row_target_with_nonblank_request` — Assert that artifact targets, closed or already-responded feedback, missing or duplicate targets, and empty or whitespace-only requests refuse.

- `test_preflight_allows_same_and_cross_routes_without_granting_write_authority` — Assert that both allowed route classes return the same bounded one-artifact context and do not select a broader write target.

- `test_preflight_rejects_requires_scope_review_before_returning_context` — Assert that scope-review evidence cannot reach candidate construction.

- `test_preflight_failure_does_not_echo_reviewer_request_or_artifact_prose` — Assert that rejection details remain redacted even though accepted contexts retain the request for later prompt construction.

Green-before-done gate: `uv run pytest tests/test_roadmap_structural_revision.py -q` passes.

## Acceptance criteria

- A caller can obtain a preflight context only by naming one exact receipt final and one exact analysis final from their respective evidence namespaces.

- The exact reader and both preflight passes read no unrelated immutable final;
  an unreadable, malformed, or otherwise invalid sibling cannot affect the
  requested pair.

- The accepted context carries raw SHA-256 digests for both named evidence records and the complete current snapshot binding.

- A changed source record, brief, stage order, selected artifact, unselected artifact, receipt, analysis, relation closure, or selected-feedback fact refuses before candidate work begins.

- The accepted feedback is exactly one open, response-absent, row-targeted item with a nonblank request and one live target row in the selected artifact.

- `same-artifact` and `cross-artifact` routes remain evidence only, while `requires-scope-review` refuses and no route can widen the selected artifact write set.

- `plan_tool/roadmap_structural_revision.py` performs no backend call, seed invalidation, lock acquisition, canonical write, or lifecycle emission.

- `uv run pytest tests/test_roadmap_structural_revision.py -q` passes.

## References

- [Python hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html#hashlib.file_digest) — Use deterministic SHA-256 digests to bind the exact raw receipt and analysis bytes.

## Applicable guardrails

- **The plan’s `## Architecture`, exact-evidence boundary:** Bind only the explicitly named receipt-analysis pair and current snapshot; do not infer evidence from a selector or storage listing.

- **The plan’s `## Architecture`, static-route boundary:** Keep route class out of write authorization and leave candidate semantic assessment to later reviewer-facing work.

- **The plan’s intent, one-artifact boundary:** Return context for one selected artifact and feedback row only; this step must not add a broader mutation path.

- **The plan’s `## Out of scope`, contract boundary:** Do not change canonical
  roadmap schemas, artifact generation, existing revision modes, immutable
  final grammar, publication semantics, or scan/listing behavior. This step may
  add only the shared no-enumeration reader required by the named-pair boundary.

## Deferred

- **Candidate-aware semantic-impact classification** (`74b73f49705a852b50f557668e68847846dfbb86c7128a8a3a3e8a8c026fd252`) — The plan’s `## Out of scope` keeps this work in BACKLOG #289; this step binds current route evidence without deciding a candidate’s downstream meaning.

- **Receipt-to-analysis preflight consolidation** — Leave `plan_tool/roadmap_impact_run.py:_load_requested_receipt` and `_resolve_selected_closure` unchanged. A wider shared refactor would change an existing runner outside this step’s file set and belongs in reconcile work.
