> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Build one lineage-bounded candidate context with a single recorded expansion

## Summary

Create `plan_tool/roadmap_candidate_context.py` and `tests/test_roadmap_candidate_context.py` as the pure context boundary for candidate proposals. The module compiles one immutable, inspectable capsule from a selected accepted predecessor, one open feedback row, declared-relation closure, source blocks, settled decisions, and an inventory of omitted rows under one module-owned 64 KiB payload ceiling. Extend `plan_tool/roadmap_revision.py` only with the read-only source-span projection needed to give full context members their exact row-owned prose without changing local revision behavior. On green, callers receive reproducible capsule and receipt data, a recorded one-time expansion, or a structured refusal with no partial context.

## Table of Contents

- [Summary](#summary) — The context-boundary outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why candidate proposals need fixed context authority.
- [Input](#input) — The immutable predecessor and current roadmap contracts consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — The new context boundary and narrow source-span edit.
- [Implementation](#implementation) — Capsule membership, byte accounting, and expansion rules.
- [Tests](#tests) — Focused context and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Record and deterministic encoding guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_revision.py:build_stage_revision_context()` serves the bounded same-artifact writer, while `plan_tool/roadmap_impact_relations.py:resolve_impact_closure()` supplies relation closure without a model-facing context record. No current boundary turns one accepted immutable predecessor and selected feedback request into complete, byte-bounded context with visible omissions. This step supplies that authority record before step 6 materializes an inert cross-artifact candidate.

## Input

- **Accepted predecessor:** Step 3 provides one resolved immutable predecessor with complete stored artifact bytes and the recorded brief’s raw bytes. Parse artifact bytes in `plan_tool/roadmap.py:STAGES` order through each `RoadmapStage.parse`; do not select a version or read current artifact paths.

- **Enrollment fence:** Step 4 ensures a candidate lineage starts only after legacy in-place writers are fenced. This module consumes the immutable predecessor value and does not acquire a writer lease.

- **Feedback selection:** Use `plan_tool/roadmap_feedback.py:parse_feedback_selector()` and `matching_feedback_rows()` against the parsed selected artifact. The selected row must be exactly one `plan_tool/roadmap_artifacts.py:FeedbackRow` in `FeedbackState.OPEN`.

- **Rows and relations:** Use `plan_tool/roadmap_artifacts.py:design_row_collections()`, `plan_tool/roadmap_relations.py:extract_declared_relations()`, and `plan_tool/roadmap_impact_relations.py:resolve_impact_closure()`. Only a `complete` closure can produce a capsule.

- **Source blocks:** `plan_tool/roadmap_revision.py:StageProseSpan` and `stage_prose_span_id()` provide the existing exact row-owned source-block identity rule. The candidate route needs the generalized read-only projection, not local revision authority.

- **Wire values:** `plan_tool/roadmap_json.py:unwrap_enum_value()` provides the shared enum-to-wire conversion used before canonical JSON encoding.

- **Context ceiling:** This proof fixes canonical capsule payloads at 64 KiB. `plan_tool/roadmap_candidate_context.py` owns the literal; callers do not select or configure it.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_context.py` — Define immutable capsule and receipt records, deterministic compilation, budget refusal, and one recorded expansion.
  - `tests/test_roadmap_candidate_context.py` — Cover membership, source content, deterministic payloads, budget refusal, and expansion.

- **Existing files (edits only):**
  - `plan_tool/roadmap_revision.py` — Add a narrow read-only projection of unambiguous row-owned prose spans for selected design rows while preserving `build_stage_revision_context()` behavior.
  - `tests/test_roadmap_revision.py` — Cover the shared source-span projection and retain the local-context behavior it must not alter.

## Implementation

- **Foundational logic:** Compile a deterministic full-content capsule from one immutable predecessor, one selected feedback row, and at most one inventory-selected closure expansion.

- **Keep the boundary pure.** Give `plan_tool/roadmap_candidate_context.py` resolved predecessor content and a selector. Define `CANDIDATE_CONTEXT_MAX_BYTES: Final[int] = 64 * 1024` in that module and do not accept a caller-supplied ceiling, paths, filesystem callbacks, model callbacks, writer tokens, or a current-head resolver.

- **Require exact stored inputs.** Verify the predecessor’s artifact and raw-brief bindings before parsing. Decode the brief as strict UTF-8 for the payload and refuse invalid, absent, or mismatched stored content without calling `plan_tool/roadmap_source.py:read_recorded_brief_source()` or `read_brief_text()`.

- **Require one open feedback row.** Refuse malformed or unknown selectors, zero or duplicate matches, and non-open feedback. Preserve the selected feedback’s artifact key, id, target, request, state, and deterministic digest in the capsule.

- **Use declared closure as the membership rule.** Build an `ImpactTarget` from the selected feedback target, extract relations from the parsed predecessor bundle, and require `resolve_impact_closure()` to return `complete`. Preserve its node order and relation source order; do not infer links from prose, inventory labels, or current files.

- **Include settled decisions deterministically.** Add every `DecisionRow` with `DecisionStatus.SETTLED`, including decisions outside the feedback closure. Merge this set with closure members by stable artifact-and-row identity, retaining the configured artifact and source order.

- **Include exact row-owned source blocks.** Extend `plan_tool/roadmap_revision.py:StageProseSpan` support with a read-only projection that returns every non-overlapping, unambiguous selected-row block in source order. A block that names another live design row must not become one row’s content. Keep `build_stage_revision_context()` on its current local-edit selection rule.

- **Keep full members and inventory separate.** A full member must contain its complete typed row value, row-content digest, ordered exact source-span texts and identities, plus fixed inclusion reasons. The compact inventory must contain every other design row in stage and source order with only artifact key, row type, stable id, verbatim human-facing label, and digest. It must not contain row bodies, source text, feedback, removals, or edit authority.

- **Bind an inspectable receipt.** Bind predecessor identity, feedback identity, full-member identities and ordered reasons, relation evidence, source-span identities and digests, compact inventory, the fixed 64 KiB ceiling, measured payload bytes, and capsule identity. Preserve a documented fixed order when a member has multiple reasons.

- **Render one closed payload form.** Serialize the exact model-facing payload once, measure its UTF-8 bytes, and derive its identity from deterministic encoded facts. Use `unwrap_enum_value()` recursively or an equivalent local conversion. Do not depend on private serialization helpers or render whole roadmap artifacts just to construct context.

- **Refuse rather than trim.** Invalid predecessor data, non-complete closure, and payloads over the fixed ceiling must return structured refusals. An over-budget refusal must report 64 KiB as the ceiling, measured payload bytes, and the complete ordered full-member identities and inclusion reasons used for measurement, while omitting member bodies. It must not summarize, drop content, write files, or fall back to live inputs.

- **Spend one expansion from the initial inventory.** Require an expansion request to identify one exact entry from an unexpanded capsule’s original inventory. Rebuild closure from the same verified predecessor with both the feedback target and selected inventory row as roots, retaining settled decisions and ordered relation evidence.

- **Bind expansion to the lineage.** The expanded capsule must record its parent capsule identity and selected inventory entry. Reject expansion of an expanded capsule, a substituted entry, or an entry absent from the original inventory. Keep the initial capsule unchanged.

- **Leave lifecycle actions outside this module.** Step 6 uses full-member authority for typed deltas. Steps 7 and 8 decide when to persist a capsule and whether an unused expansion is spent by an initial or answer-driven proposal.

## Tests

Use a four-artifact fixture with row- and artifact-targeted feedback, cross-artifact relations, multiple row-owned prose blocks, an unrelated row, an outside settled decision, and an expandable inventory entry.

### Tests for this step

- `test_row_owned_span_projection_returns_all_unambiguous_selected_blocks` — `plan_tool/roadmap_revision.py` returns every exact selected-row block in source order and excludes shared blocks.

- `test_stage_context_keeps_its_existing_local_prose_selection` — `build_stage_revision_context()` keeps its current local revision result after the new read-only projection lands.

- `test_context_uses_only_the_selected_accepted_predecessor` — Live artifacts and another stored version cannot affect compiled context.

- `test_context_uses_verified_raw_brief_bytes_without_live_fallback` — The payload uses only bound strict-UTF-8 brief bytes and refuses invalid bindings.

- `test_context_requires_exactly_one_open_selected_feedback_row` — Malformed, unknown, absent, duplicate, and non-open feedback selections refuse.

- `test_row_and_artifact_targets_build_declared_closure` — Both target kinds include only members and relation evidence returned from stored declared relations.

- `test_context_includes_settled_decisions_and_exact_row_owned_source_blocks` — Settled decisions outside closure and all eligible source blocks are present in deterministic order.

- `test_compact_inventory_has_no_content_or_edit_authority` — Omitted rows remain discoverable by compact metadata only.

- `test_context_receipt_payload_and_identity_are_repeatable` — Identical immutable inputs produce identical bytes, digests, receipt facts, and capsule identity.

- `test_context_uses_one_module_owned_64_kib_ceiling_without_caller_override` — Initial and expanded compilation record `CANDIDATE_CONTEXT_MAX_BYTES`, and the public boundary exposes no per-call ceiling.

- `test_payload_uses_enum_wire_values` — Enum-bearing row values use stable wire values rather than Python enum representations.

- `test_over_budget_context_reports_complete_membership_without_partial_content` — A payload above the fixed 64 KiB ceiling reports that ceiling, measured bytes, and every measured member identity and reason without source or row bodies.

- `test_expansion_requires_an_exact_initial_inventory_item_and_rebuilds_closure` — One original inventory item adds its complete stored closure while retaining prior members and settled decisions.

- `test_expansion_records_parent_and_refuses_a_second_expansion` — The expansion binds its parent and selected item, and another expansion cannot alter it.

- `test_invalid_predecessor_or_closure_returns_no_partial_capsule` — Invalid stored data and incomplete closure results refuse without a capsule.

Every named test in `tests/test_roadmap_candidate_context.py` and `tests/test_roadmap_revision.py` must be green before this step is complete.

## Acceptance criteria

- The compiler consumes only one accepted predecessor’s stored artifact and bound brief bytes.

- An initial capsule contains selected open feedback, declared closure members, all settled decisions, exact row-owned source blocks, relation evidence, compact omitted-row inventory, and an inspectable receipt.

- Compact inventory entries contain no full content and cannot grant edit authority.

- Payload bytes, member order, source-span identities, digests, receipt facts, and capsule identity are reproducible for identical inputs under one module-owned 64 KiB ceiling with no caller override.

- Invalid, incomplete, or oversized inputs return structured refusals with no partial capsule, trimming, summary, write, model call, or live fallback.

- An oversized refusal reports the fixed 64 KiB ceiling, measured bytes, and complete ordered full-member identities and inclusion reasons without member content.

- One expansion selects only an exact initial inventory entry, records its parent identity, rebuilds from the same predecessor, and prevents later expansion.

- `tests/test_roadmap_candidate_context.py` and `tests/test_roadmap_revision.py` pass.

## References

- [Configuration | Pydantic Docshttps: — Use strict, frozen, closed record configuration for capsule and receipt data.

- [json — JSON encoder and decoderhttps: — Use deterministic JSON encoding for the model payload and receipt facts.

- [hashlib — Secure hashes and message digestshttps: — Bind row content, source blocks, payloads, and capsules with SHA-256.

- [RFC 8785: JSON Canonicalization Schemehttps: — Review canonical JSON requirements before fixing capsule identity encoding.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Build inspectable proposal context only; do not materialize candidates, ask questions, store versions, or move the accepted head.

- **The plan’s “## Scope guardrails”, binary observables** — Keep membership, source blocks, relation evidence, digest bindings, receipt facts, and byte accounting deterministic and testable.

- **The plan’s “## Scope guardrails”, context omission and expansion** — Make omissions visible, refuse budget overflow, and limit the lineage to its recorded expansion.

- **The plan’s “## Scope guardrails”, compact inventory authority** — Keep compact discovery data separate from the full content that later steps may authorize for edits.

- **The plan’s “## Scope guardrails”, model and validation authority** — Keep this boundary structural and deterministic; do not add quality scoring, semantic judgments, model calls, or new roadmap gates.

- **The plan’s “## Out of scope”, retrieval and configurable context** — Do not add search, embeddings, arbitrary browsing, summaries, configurable expansion policy, or a general context framework.

## Deferred

- **Typed delta application and full-content authorization** — Step 6 owns candidate materialization and delta enforcement.

- **Proposal calls, lineage admission, and durable capsule storage** — Steps 7 and 8 own backend calls, persistence, replay, and answer-driven reuse.

- **Changes to local revision behavior** — `plan_tool/roadmap_revision.py:build_stage_revision_context()` remains the existing same-artifact revision contract.
