> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Build one lineage-bounded candidate context with a single recorded expansion

## Summary

Create `plan_tool/roadmap_candidate_context.py` and `tests/test_roadmap_candidate_context.py` as a pure context boundary for candidate proposals. The module builds one inspectable capsule from one selected immutable predecessor, one open feedback row, its declared-relation closure, settled decisions, and a compact inventory of omitted rows. Its key design decision is that context membership comes only from stored predecessor content and one recorded inventory expansion, never from live roadmap files or silent trimming. On green, callers receive repeatable payload bytes and receipt facts, or a complete refusal with no partial context.

## Table of Contents

- [Summary](#summary) — The outcome and narrow file footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the candidate lifecycle needs fixed proposal context.
- [Input](#input) — The predecessor, feedback, relation, and artifact contracts consumed here.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files this step creates.
- [Implementation](#implementation) — Capsule membership, receipt, budget, and expansion rules.
- [Tests](#tests) — Focused behavior and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Record, JSON, and digest guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this context builder.
- [Deferred](#deferred) — Lifecycle work left to later steps.

## Why

`plan_tool/roadmap_revision.py:build_stage_revision_context()` intentionally serves same-artifact live revision and does not retain complete cross-artifact authority. `plan_tool/roadmap_impact_relations.py:resolve_impact_closure()` can find a deterministic relation closure, but no current boundary turns one accepted immutable version and one feedback request into bounded model context with visible omissions. This step supplies that missing authority record before step 6 can materialize an inert cross-artifact candidate.

## Input

- **Accepted predecessor:** Step 3 provides the selected immutable version and its exact stored artifact and brief bytes. Parse the stored artifact bytes in `plan_tool/roadmap.py:STAGES` order through each `RoadmapStage.parse`; do not select a version, read top-level artifact paths, or fill missing content from current files.

- **Enrollment fence:** Step 4 completes before this step, so legacy in-place writers cannot change the accepted predecessor while a candidate lineage starts.

- **Recorded brief:** Step 3 provides the stored raw brief bytes and digest. Verify that binding and decode the stored bytes as UTF-8 for the payload; do not call `plan_tool/roadmap_source.py:read_recorded_brief_source()` or `read_brief_text()` as a fallback.

- **Feedback selection:** Use `plan_tool/roadmap_feedback.py:parse_feedback_selector()` and `matching_feedback_rows()` against the parsed selected artifact. Require exactly one `plan_tool/roadmap_artifacts.py:FeedbackRow` in `FeedbackState.OPEN`.

- **Rows and relations:** Use `plan_tool/roadmap_artifacts.py:design_row_collections()` for ordered design rows and `plan_tool/roadmap_relations.py:extract_declared_relations()` for relation evidence. Turn the selected feedback target into `plan_tool/roadmap_impact_relations.py:ImpactTarget` and require a `resolve_impact_closure()` result with the `complete` verdict.

- **Settled decisions:** Include every `plan_tool/roadmap_artifacts.py:DecisionRow` in `DecisionStatus.SETTLED`, including decisions outside the feedback closure.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_context.py` — Define immutable capsule and receipt records, deterministic compilation, byte-budget refusal, and the one-expansion operation.
  - `tests/test_roadmap_candidate_context.py` — Cover context membership, deterministic rendering, refusal, and expansion behavior.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Compile one deterministic, lineage-bounded context capsule from an accepted predecessor and selected feedback row.

- **Keep the boundary pure.** Accept already-resolved immutable predecessor data, a feedback selector, and an explicit byte ceiling. Do not accept a plans directory, filesystem callback, model callback, writer token, or current-head selector.

- **Require one exact selected feedback row.** Preserve its artifact key, stable id, target, request, state, and deterministic digest in the capsule. Refuse malformed selectors, an unknown artifact, zero or multiple matching rows, and every state other than `FeedbackState.OPEN`.

- **Build initial membership from stored typed artifacts only.** Use `extract_declared_relations()` and `resolve_impact_closure()` to include the selected target’s complete bidirectional closure. Preserve `ImpactClosure.nodes` order and relation source order. Add settled decisions as a stable union, not as a second relation walk.

- **Keep full content and discovery separate.** Full members must carry the complete typed row value and deterministic content digest. The compact inventory must list every remaining design row in stage and source order, with only its artifact key, row type, stable id, label, and digest. Do not include feedback, removals, raw row bodies, or an edit grant in inventory entries.

- **Record why each member is present.** The receipt must bind the predecessor identity, selected feedback identity, full-member identities and inclusion reasons, relation evidence, compact inventory, byte ceiling, measured payload bytes, and capsule identity. When a row has more than one reason, preserve a fixed reason order.

- **Render one closed payload form.** Produce the exact model-facing JSON once, count its UTF-8 bytes, and derive its identity from deterministic encoded facts. Convert enum values to their wire values using `plan_tool/roadmap_json.py:unwrap_enum_value()` or an equivalent local recursive conversion. Do not depend on private canonicalization helpers or render whole staged artifacts through `RoadmapStage.render()`.

- **Refuse instead of trimming.** A bad predecessor binding, malformed stored bytes, invalid closure, invalid byte ceiling, or oversized payload must return a structured refusal. An over-budget refusal must carry the declared ceiling, measured payload bytes, and the complete deterministic full-member identity and inclusion-reason sequence used for that measurement, without carrying member bodies. Do not summarize, drop members, shorten text, return a partial capsule, write files, or retry against live content.

- **Spend the one expansion from the initial inventory.** An expansion request must match one exact item from the unexpanded capsule’s inventory. Rebuild membership from the same immutable predecessor using both the original feedback target and selected inventory row, then retain all settled decisions and ordered relation evidence.

- **Bind the expansion to its lineage.** The expanded capsule must retain the selected initial inventory item and the unexpanded capsule identity. Reject expansion of an already-expanded capsule, a substituted inventory item, or an item not present in that initial inventory. Keep the original capsule immutable.

- **Leave lifecycle actions outside this module.** Step 6 consumes full-member authority when it validates typed deltas. Steps 7 and 8 decide when to persist an issued capsule and whether an unused expansion is spent by the initial proposal or an answer-driven replacement.

## Tests

Use a four-artifact fixture with row- and artifact-targeted feedback, cross-artifact relations, an unrelated row, an outside settled decision, and one expandable inventory row.

### Tests for this step

- `test_context_uses_only_the_selected_accepted_predecessor` — Changes to live roadmap files or another stored version do not affect the capsule.

- `test_context_uses_verified_raw_brief_bytes_without_live_fallback` — The payload uses the selected predecessor’s bound UTF-8 brief bytes and refuses missing, mismatched, or invalid bindings.

- `test_context_requires_exactly_one_open_selected_feedback_row` — Malformed, unknown, duplicate, absent, and non-open feedback selections refuse.

- `test_row_and_artifact_feedback_targets_build_their_declared_closure` — Both target kinds include only the closure produced from stored parsed artifacts and declared relations.

- `test_context_includes_settled_decisions_and_preserves_member_and_relation_order` — Settled decisions outside the closure are included without changing source ordering.

- `test_compact_inventory_omits_row_bodies_and_never_grants_full_membership` — Omitted rows appear only as compact discovery records.

- `test_context_receipt_and_payload_identity_are_repeatable` — Identical immutable inputs produce identical payload bytes, digests, receipt facts, and capsule identity.

- `test_payload_uses_enum_wire_values` — Enum-bearing row content renders as stable wire values rather than Python enum representations.

- `test_over_budget_context_reports_complete_membership_without_truncation_or_partial_capsule` — An oversized complete payload returns its ceiling, measured bytes, and the complete ordered full-member identities and inclusion reasons, but no member bodies or shortened context.

- `test_expansion_requires_an_exact_initial_inventory_item_and_rebuilds_closure` — One valid initial-inventory selection adds its full stored closure while retaining original members and settled decisions.

- `test_expansion_records_its_parent_and_refuses_a_second_expansion` — The expanded capsule records its parent and selected item, while another expansion cannot change it.

- `test_invalid_closure_or_predecessor_data_returns_no_partial_context` — Invalid stored inputs and non-complete closures refuse without a capsule.

Every named test in `tests/test_roadmap_candidate_context.py` must be green before this step is complete.

## Acceptance criteria

- The context compiler consumes one accepted predecessor’s stored artifact and bound brief bytes without reading live roadmap content.

- An initial capsule contains the selected open feedback, its complete declared-relation closure, all settled decisions, ordered relation evidence, compact omitted-row inventory, and an inspectable receipt.

- Compact inventory entries contain no full row bodies and do not act as edit authority.

- Payload bytes, member order, digests, receipt facts, and capsule identity are reproducible for identical inputs.

- Invalid, incomplete, or over-budget inputs return a structured refusal with no truncation, summary, write, model call, or live fallback; an over-budget refusal includes its ceiling, measured bytes, and complete ordered full-member identities and inclusion reasons without member content.

- One expansion selects only an exact initial inventory entry, records that selection and parent identity, rebuilds from the same predecessor, and prevents further expansion.

- `tests/test_roadmap_candidate_context.py` passes.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Review strict and frozen record options for closed immutable capsule data.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use deterministic JSON encoding for the exact payload and receipt facts.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 to bind row content and capsule identity.

- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) — Review canonical JSON rules before fixing identity encoding.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Build inspectable context only; do not materialize candidates, ask questions, store versions, or move the accepted head.

- **The plan’s “## Scope guardrails”, binary observables** — Make membership, relation evidence, digest bindings, receipt facts, and byte accounting deterministic and testable.

- **The plan’s “## Scope guardrails”, context omission and expansion** — Record omissions, refuse budget overflow, and limit context growth to the recorded expansion.

- **The plan’s “## Scope guardrails”, compact inventory authority** — Keep inventory data distinct from full content so later delta validation can reject edits to omitted rows.

- **The plan’s “## Scope guardrails”, model and validation authority** — Keep this boundary deterministic and structural; do not add quality scoring, semantic judgments, model calls, or gates.

- **The plan’s “## Out of scope”, retrieval and configurable context** — Do not add search, embeddings, arbitrary browsing, summaries, configurable expansion policies, or a general context framework.

## Deferred

- **Typed delta application and full-content authorization** — Step 6 owns candidate materialization and enforcement of capsule authority.

- **Proposal calls, storage, and final-capsule reuse** — Steps 7 and 8 own backend calls, persistence, and answer-driven lineage handling.

- **Changes to `plan_tool/roadmap_revision.py:build_stage_revision_context()`** — That remains the current local-revision contract; converting its live same-artifact route is outside this immutable candidate-context step.

- **A shared public canonical-value encoder** — Extracting one from existing private source-identity internals is a cross-module refactor and belongs in later reconcile work.
