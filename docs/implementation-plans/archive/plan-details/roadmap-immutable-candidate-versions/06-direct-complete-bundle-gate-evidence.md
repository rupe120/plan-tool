> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add direct complete-bundle gate evidence, apply capsule-authorized deltas, and bind deterministic candidate diffs

## Summary

Add a direct complete-bundle gate route in `plan_tool/roadmap_impact_snapshot.py` and create `plan_tool/roadmap_candidate.py` as the pure candidate materialization boundary. The new route verifies complete candidate evidence before it reuses step 1’s extracted ordered gate walk; the candidate boundary parses a closed typed delta, applies only capsule-authorized changes, and produces a deterministic predecessor diff. Preserve stored bytes for unchanged artifacts and render changed artifacts through their matching `RoadmapStage` contract. On green, callers receive an in-memory, gate-clean, complete candidate with fixed content identity and no storage or accepted-head side effect.

## Table of Contents

- [Summary](#summary) — The direct gate and candidate-materialization outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why snapshot substitution cannot validate immutable complete candidates.
- [Input](#input) — The upstream predecessor, capsule, stage, and relation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two edited and two new files.
- [Implementation](#implementation) — Complete evidence checks, authorized assembly, gates, diffs, and identity.
- [Tests](#tests) — Focused direct-gate and candidate-boundary coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Closed-record and deterministic-identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on model authority and lifecycle scope.
- [Deferred](#deferred) — Storage, review, and promotion work left to later steps.

## Why

`plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()` validates a captured live snapshot and can substitute one artifact through `CandidateSubstitution`; it cannot prove that four immutable candidate artifacts form one valid complete bundle without fabricating snapshot state or rereading live files. The existing tests confirm the ordered envelope behavior, but the direct-evidence route and candidate module do not exist. This step adds that missing boundary so step 7 can store only a deterministic, gate-clean proposal.

## Input

- **Shared gate walk:** Step 1 extracts the ordered evaluator currently reached through `plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()`. This step adds a complete-evidence adapter to that evaluator without changing the snapshot-facing route or `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()`.

- **Immutable predecessor:** Step 3 provides one selected accepted version with complete stored artifact bytes, raw-byte digests, and a fixed predecessor identity. Parse only its stored stage bytes through `plan_tool/roadmap.py:STAGES`; do not read live artifact paths or select another version.

- **Issued capsule:** Step 5 provides the selected open feedback, exact receipt, full-content members, relation evidence, compact inventory, and expansion state. The compact inventory remains discoverable metadata, not edit authority.

- **Typed rows and relations:** `plan_tool/roadmap_artifacts.py:stage_row_collections()`, `append_stage_row()`, `replace_stage_row()`, `remove_stage_row()`, `append_plan_ordering_entry()`, and `remove_plan_ordering_entry()` provide the existing immutable typed-update shapes. `plan_tool/roadmap_relations.py:extract_declared_relations()` provides the ordered relation inventory, and `same_declared_row_relations()` provides the existing-row preservation predicate.

- **Strict response shape:** `plan_tool/roadmap_revision.py:parse_revision_operations()` and its single-object decoder establish the current refusal rules for duplicate keys, non-standard constants, trailing content, and unknown fields. Mirror that behavior locally without importing live-revision operation types.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate.py` — Define closed delta records, materialization, authority checks, deterministic diffs, candidate content identity, and gate-clean candidate results.
  - `tests/test_roadmap_candidate.py` — Cover delta parsing, complete assembly, authority refusals, byte preservation, gates, diff order, identity, and purity.

- **Existing files (edits only):**
  - `plan_tool/roadmap_impact_snapshot.py` — Add the direct complete-bundle evidence input and checker that validates every candidate stage before delegating to step 1’s shared evaluator; keep the snapshot route compatible.
  - `tests/test_roadmap_impact_snapshot.py` — Add direct complete-bundle tests and retain characterization of the snapshot substitution route.

## Implementation

- **Foundational logic:** Validate one complete candidate bundle, then materialize only capsule-authorized typed changes into that bundle.

- **Add a direct complete-bundle gate boundary.** Accept one ordered candidate evidence value containing every stage key, text, parsed artifact, and raw SHA-256 digest. It must require the supplied stage table’s exact order and keys, strict UTF-8 text-to-byte agreement, matching digests, and successful parsing back to the supplied artifact before any gate runs.

- **Reuse the extracted evaluator.** Once direct evidence validates, delegate to step 1’s stage-ordered `ArtifactEnvelope(predecessor=None, ...)` walk. Return one `RoadmapGateOutcome` per supplied `RoadmapStage`, in supplied order, retaining the same stage objects. Do not use `capture_roadmap_impact_snapshot()`, `RoadmapImpactSnapshot`, or `CandidateSubstitution` for the direct route.

- **Keep snapshot callers unchanged.** `check_full_roadmap_gates()` must retain its current snapshot validation and substitution behavior. `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` remains on that compatible path; this step must not redirect it to immutable candidate evidence.

- **Own a closed delta parser and materializer.** In `plan_tool/roadmap_candidate.py`, define one parser for a single closed JSON delta and one materialization boundary that accepts only a parsed delta, step 3’s selected predecessor, and step 5’s issued capsule and receipt. Refuse malformed input before assembling any candidate.

- **Keep model output structural and inert.** The delta may express only typed row additions, replacements, and removals needed by the representative cross-artifact case. An added row may declare relations and removing a row removes its incident relations. A plan-row addition or removal may carry only its matching ordering-entry addition or removal as an inseparable consequence. The delta has no standalone relation or ordering-entry operation. It must not accept raw artifact text, filesystem paths, source-span edits, feedback state changes, version selection, answers, seals, or promotion instructions.

- **Require exact authority bindings.** Refuse a capsule, receipt, predecessor, or selected feedback that does not match the supplied immutable inputs. An existing row may change only when its exact predecessor content is a full-content capsule member, and its replacement must satisfy `same_declared_row_relations()` against that predecessor row. Compact inventory entries must never authorize replacement or removal.

- **Limit relation-set changes to row membership changes.** Only an admitted row addition or removal, including its matching plan ordering entry, may add or remove declared relations. For each resulting relation change, require full-content membership for every affected endpoint that exists in the predecessor. A new row may be an endpoint, but an omitted predecessor row cannot be reached through adding or removing another row, and a relation between two retained existing rows cannot change.

- **Anchor new content mechanically.** Each added row and every relation it introduces must bind to the selected feedback and to a reached full-content member or declared relation from the issued capsule. Refuse unanchored additions instead of widening the capsule.

- **Preserve reviewer evidence.** Keep all predecessor `FeedbackRow` values unchanged. Bind the selected feedback in the candidate result separately; materialization must not treat the proposal as a feedback response or review action.

- **Assemble copy-on-write.** Start from the predecessor’s complete `plan_tool/roadmap.py:STAGES`-ordered bytes. Copy every unchanged artifact byte-for-byte. For a changed artifact, apply its typed update, render it through that stage’s `RoadmapStage.render`, encode it as UTF-8, and require `RoadmapStage.parse` to recreate the retained typed artifact.

- **Gate the complete assembled candidate.** Build direct gate evidence from all assembled stage texts, parsed artifacts, and raw digests. Any evidence mismatch or gate violation must refuse candidate materialization; an accepted result contains only all-green ordered outcomes.

- **Bind a deterministic predecessor diff.** Compare predecessor and candidate in stage and source order. Record changed artifact identities, complete before-and-after typed row values, and added or removed declared relations. Do not derive ordering from mappings, sets, directories, or operation order, and do not judge prose quality.

- **Bind content, not lifecycle state.** Derive the candidate content identity from the predecessor identity, selected feedback identity, issued capsule receipt, complete candidate bytes or digests, and deterministic diff. Do not include later answer lineage or candidate-version identity; steps 7 and 8 own those bindings.

- **Keep existing merger routes separate.** `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()`, `merge_stage_revision()`, and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` retain their current authority contracts and receive no candidate-version integration in this step.

## Tests

Use a four-stage predecessor fixture with an open selected feedback row, a cross-artifact relation, a full-content closure member, and a compact-inventory-only row.

### Tests for this step

- `test_direct_complete_bundle_checker_rejects_invalid_evidence_before_gates` — Invalid stage evidence refuses before a gate callable runs.

- `test_direct_complete_bundle_checker_reuses_the_shared_ordered_gate_walk` — Direct evidence runs every injected stage gate once in stage order with `predecessor=None` and accumulated candidate artifacts.

- `test_candidate_applies_only_an_authorized_complete_row_replacement` — An authorized full-content replacement is materialized as one complete candidate bundle.

- `test_candidate_materialization_refuses_a_caller_supplied_stage_table` — The candidate materializer owns the fixed stage order rather than accepting a caller override.

- `test_candidate_rejects_compact_inventory_as_existing_row_authority` — A compact-only row cannot be replaced or removed.

- `test_candidate_existing_row_edit_preserves_every_declared_relation` — An existing-row replacement with a changed relation signature refuses even when the row is a full-content member.

- `test_candidate_adds_a_cross_artifact_row_only_when_full_endpoints_anchor_it` — A cross-artifact addition requires full-content authority for its endpoints.

- `test_candidate_plan_ordering_companion_is_retained_in_the_predecessor_diff` — A plan-ordering change remains visible as its companion predecessor diff.

- `test_candidate_rejects_substituted_capsule_receipt_before_assembly` — Substituted capsule evidence refuses before assembly.

- `test_candidate_returns_no_candidate_when_the_complete_gate_bundle_fails` — A failed complete-bundle gate prevents an accepted candidate.

- `test_candidate_content_identity_ignores_delta_operation_order` — Equivalent delta order produces the same deterministic content identity.

Every listed test in `tests/test_roadmap_impact_snapshot.py` and `tests/test_roadmap_candidate.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_impact_snapshot.py` provides a direct complete-bundle checker that validates every stage’s key, text, parsed artifact, and raw digest before it invokes the shared gate evaluator.

- The direct checker returns stage-ordered `RoadmapGateOutcome` values without reading live roadmap files, constructing a snapshot, or accepting a single-stage substitution.

- `check_full_roadmap_gates()` and `plan_tool/roadmap_structural_revision_proof.py:prove_structural_revision_candidate()` keep their existing snapshot-based behavior.

- `plan_tool/roadmap_candidate.py` accepts only a closed, authorized typed delta and returns no partial candidate on malformed input, stale bindings, missing full-content authority, missing anchors, or gate failure.

- An accepted candidate contains complete stage-ordered bytes and parsed artifacts, all-green direct gate outcomes, a deterministic predecessor diff, and a fixed content identity.

- Unchanged candidate artifacts retain their predecessor bytes exactly; changed artifacts are rendered and reparsed through their matching `RoadmapStage`.

- An existing-row change preserves its declared relations. Relation-set changes occur only through admitted row additions or removals, and compact inventory never authorizes an existing-row change or supplies an omitted predecessor endpoint.

- Candidate materialization performs no filesystem write, version storage, accepted-head move, feedback transition, question, answer, or promotion.

- `tests/test_roadmap_impact_snapshot.py` and `tests/test_roadmap_candidate.py` pass.

## References

- [Configuration | Pydantic Docshttps: — Use strict, frozen, extra-field-forbidden records for the delta and candidate contract.

- [json — JSON encoder and decoderhttps: — Use strict decoding and deterministic encoding for delta parsing and identity inputs.

- [hashlib — Secure hashes and message digestshttps: — Bind candidate evidence and identity inputs with SHA-256.

- [RFC 8785: JSON Canonicalization Schemehttps: — Review stable JSON rules before fixing the content-identity preimage.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Limit this step to one inert, reviewable candidate and its complete gate evidence.

- **The plan’s “## Scope guardrails”, binary observables** — Keep candidate bytes, gate evidence, content identity, diff records, and capsule authority deterministic and testable.

- **The plan’s “## Scope guardrails”, model authority and lifecycle order** — Treat the delta as inert input and stop after materialization; do not add storage, review, promotion, or canonical mutation.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Refuse unauthorized edits rather than treating compact inventory as authority or widening the capsule.

- **The plan’s “## Scope guardrails”, validation boundary** — Validate shape, bindings, anchors, digests, diffs, and existing gates only; do not score or judge roadmap prose.

- **The plan’s “## Out of scope”, writer and workflow expansion** — Do not add direct model writes, automatic promotion, generic editing, retrieval, or broader lifecycle management.

## Deferred

- **Candidate storage and proposal orchestration** — Step 7 owns backend invocation, lineage admission, and persistence of gate-clean candidates.

- **Questions, reviewer answers, replacement bindings, and review seals** — Step 8 owns the review lifecycle that consumes the persisted candidate diff.

- **Accepted-head promotion** — Step 9 owns approval and selector-only promotion of a sealed candidate.

- **Merger consolidation** — Combining the existing local, structural, and capsule-bound merger families requires a separately authorized reconcile or refactor step.
