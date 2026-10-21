> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Build one lineage-bounded candidate context with a single recorded expansion

## Summary

Create `plan_tool/roadmap_candidate_context.py` and `tests/test_roadmap_candidate_context.py` as the deterministic context boundary for candidate proposals. The module compiles one accepted predecessor, one selected feedback row, its declared-relation closure, settled decisions, a compact omitted-row inventory, and an inspectable receipt. Its key decision is that expansion accepts one recorded inventory entry and rebuilds membership from the same immutable predecessor rather than reading live roadmap files. On green, callers receive repeatable context bytes and identity, or a structured refusal with no truncation, write, model call, or fallback.

## Table of Contents

- [Summary](#summary) — The step’s outcome and narrow footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why candidate proposals need fixed, inspectable context.
- [Input](#input) — The accepted-root, artifact, feedback, relation, and brief contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and their roles.
- [Implementation](#implementation) — Context compilation, receipt identity, budget, and expansion rules.
- [Tests](#tests) — Direct coverage for membership, refusal, and repeatability.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Strict record, JSON, and digest guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that constrain the context boundary.
- [Deferred](#deferred) — Later candidate lifecycle work outside the pure context boundary.

## Why

The existing local revision context in `plan_tool/roadmap_revision.py:build_stage_revision_context()` deliberately omits source text and works one stage at a time, so it cannot show a model the complete cross-artifact facts needed for an inert candidate. `plan_tool/roadmap_impact_relations.py:resolve_impact_closure()` already provides deterministic relation closure, but no module turns one accepted immutable version and one feedback request into a bounded, reusable model context with visible omissions. This step supplies that boundary before candidate materialization can treat included content as edit authority.

## Input

- **Enrollment fence:** Step 4 must be complete before this candidate-lifecycle step, so an enrolled predecessor cannot still be changed through a legacy in-place writer while its context is compiled.

- **Accepted predecessor:** Step 3 supplies one selected immutable stored version, root or promoted candidate, with its version identity, four stored artifact byte sequences in `plan_tool/roadmap.py:STAGES` order, and exact bound raw recorded-brief bytes. Parse those stored artifact bytes through each `RoadmapStage.parse`; do not read top-level artifact paths, inspect another version, or select a directory by recency.

- **Recorded brief:** Step 3's stored-version contract retains the exact raw UTF-8 recorded-brief bytes and raw-byte digest captured at enrollment and carried by later candidate versions. Verify that binding, then decode those stored bytes strictly once for the model-facing payload. A missing, mismatched, or non-UTF-8 binding must refuse; never fall back to `plan_tool/roadmap_source.py:read_recorded_brief_source()`, a normalized-text digest, or another live brief path.

- **Feedback selection:** Use `plan_tool/roadmap_feedback.py:parse_feedback_selector()` and `matching_feedback_rows()` against the parsed stored artifact. Require exactly one `plan_tool/roadmap_artifacts.py:FeedbackRow` in the open state and retain its target and request unchanged.

- **Rows and relations:** Use `plan_tool/roadmap_artifacts.py:design_row_collections()` for stable design-row membership, `plan_tool/roadmap_relations.py:extract_declared_relations()` for the ordered relation inventory, and `plan_tool/roadmap_impact_relations.py:resolve_impact_closure()` for bidirectional closure. Keep identity-only review records outside the row inventory; ordering remains represented by its declared relations rather than a made-up row identity.

- **Settled decisions:** Include every `plan_tool/roadmap_artifacts.py:DecisionRow` whose status is `DecisionStatus.SETTLED`, even when it is outside the feedback closure.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate_context.py` — Define the immutable candidate-context records, deterministic compiler, canonical renderer, budget refusal, and single-expansion operation.
  - `tests/test_roadmap_candidate_context.py` — Cover accepted-root input, exact membership, expansion, accounting, and fail-closed behavior.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Compile a deterministic, lineage-bounded context capsule from one accepted predecessor and one selected feedback request.

- **Keep the boundary pure and narrow.** Expose a small compiler and expansion pair, such as `build_candidate_context()` and `expand_candidate_context()`. Accept immutable predecessor data, exact brief data, and a feedback selector as explicit inputs. Do not accept a plans directory, candidate directory, filesystem search callback, model callback, or writer token.

- **Build the initial membership deterministically.** Resolve the feedback target with `ImpactTarget` and `resolve_impact_closure()`. Full-content members must include the selected closure and every settled decision. Preserve `ImpactClosure.nodes` order and `ImpactClosure.relations` source order; the compact inventory must contain every remaining stable design row in `ARTIFACT_KEYS` and source order.

- **Keep full content distinct from discovery.** Each full member must carry its complete typed row representation and a deterministic content digest. Each compact inventory item must carry only its artifact key, row type, stable id, source-derived label, and content digest. An inventory digest identifies omitted content but must not appear in the full-member set or represent edit authority.

- **Record membership reasons.** Give the receipt an ordered membership record for every full member, including all applicable reasons such as feedback target, closure, settled decision, and expansion. Retain predecessor version identity, exact feedback identity, relation evidence, compact inventory, declared budget, measured payload bytes, and the context identity.

- **Use one deterministic payload representation.** Render the model-facing payload with a closed, canonical JSON shape and count the UTF-8 bytes of that exact payload. Normalize enum values with `plan_tool/roadmap_json.py:unwrap_enum_value()` or an equivalent local recursive conversion. Do not call private helpers such as `plan_tool/roadmap_source_identity.py:_canonical_value()` or use `RoadmapStage.render()` to recreate stored artifact content.

- **Fail closed on size or invalid input.** A non-positive budget, malformed accepted-root data, non-unique selected feedback, invalid closure verdict, missing bound brief, or payload above budget must produce a structured refusal. Include the measured bytes, budget, and selected or omitted member identities where applicable. Do not drop rows, shorten text, summarize content, or choose a smaller closure.

- **Spend one expansion only.** Expansion must accept one entry from the initial compact inventory, treat it as an additional relation-closure root, and rebuild the final full-member and relation sets from the immutable predecessor. Reuse `resolve_impact_closure()` for both roots and merge its ordered evidence; do not create a second relation walker.

- **Bind expansion to the lineage value.** The expanded context must retain the exact selected inventory item and its pre-expansion context identity in an immutable expansion record. `expand_candidate_context()` must reject a context that already records an expansion. A context with no expansion remains the currently issued capsule; it becomes the lineage's final capsule only when review closes without spending the remaining expansion.

- **Keep later lifecycle ownership separate.** This module produces immutable values only. Step 6 consumes full-content membership as delta authority. Steps 7 and 8 canonically persist the issued capsule and receipt with the candidate that establishes the lineage's final context, then load that exact pair for later replacements rather than recompiling it.

## Tests

Use a four-artifact fixture with a row-targeted feedback request, a cross-artifact declared relation, an unrelated row, a settled decision outside the closure, and an expandable row.

### Tests for this step

- `test_context_uses_the_selected_accepted_root_not_live_artifacts_or_another_version` — Changing top-level roadmap files or providing another stored version does not change the compiled capsule.

- `test_context_decodes_bound_raw_recorded_brief_bytes_without_a_live_fallback` — A CRLF brief reaches the canonical payload from the selected version's verified raw bytes, while missing or mismatched facts refuse and `plan_tool/roadmap_source.py:read_recorded_brief_source()` is never used during compilation.

- `test_initial_context_contains_feedback_closure_settled_decisions_and_compact_inventory` — The capsule contains unchanged feedback, all closure rows, all settled decisions, connecting relations, and every remaining design row only in the inventory.

- `test_context_receipt_records_ordered_membership_reasons_and_content_digests` — Each full member records its source-derived digest and all inclusion reasons in deterministic order.

- `test_compact_inventory_identifies_omitted_content_without_granting_full_membership` — An inventory item exposes only its compact fields and remains absent from the full-content member set.

- `test_context_bytes_and_identity_are_repeatable_for_identical_inputs` — Recompiling identical immutable inputs returns identical rendered payload bytes, receipt accounting, and context identity.

- `test_over_budget_context_refuses_with_measured_bytes_and_members_without_truncation` — A hard budget refusal reports the complete measured payload and membership without returning a shortened capsule.

- `test_expansion_requires_an_initial_inventory_entry_and_recomputes_closure` — One valid inventory selection adds its full closure and connecting relations while retaining initial members and settled decisions.

- `test_expansion_records_the_selected_entry_and_refuses_a_second_expansion` — The final capsule records its one selected entry and any further expansion request refuses.

- `test_context_refuses_invalid_feedback_or_unmappable_closure_without_partial_output` — Invalid selector state, duplicate selection, or an invalid closure produces no partial capsule.

Every named test in `tests/test_roadmap_candidate_context.py` must be green before this step is complete.

## Acceptance criteria

- The compiler reads one accepted predecessor’s stored bytes and exact bound brief facts, never live top-level roadmap artifacts or a newest candidate.

- An initial capsule contains unchanged selected feedback, full declared-relation closure content, settled decisions, connecting relations, an inventory of omitted stable design rows, and an ordered receipt.

- The compact inventory contains no full row body and does not identify content as authorized for a later delta.

- Capsule bytes, membership, digests, receipt, and identity are reproducible for identical inputs.

- An over-budget, malformed, or incomplete input refuses with measured facts and no truncation, summary, write, model access, or fallback.

- One expansion can select only an initial inventory entry, rebuilds full closure membership from the same predecessor, records that selection, and prevents a second expansion.

- `tests/test_roadmap_candidate_context.py` passes.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen models for closed immutable context and receipt records.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use deterministic JSON encoding for the exact model-facing payload and receipt identity input.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for row content and context identities.

- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) — Review canonical JSON requirements before fixing the context identity encoding.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Build inspectable context only; do not materialize candidates, ask questions, or move accepted-head state.

- **The plan’s “## Scope guardrails”, binary observables** — Make membership, content digests, receipt identity, and byte accounting deterministic and testable.

- **The plan’s “## Scope guardrails”, context omission and expansion** — Record every omission through the compact inventory, allow only the one recorded expansion, and refuse rather than truncate or widen.

- **The plan’s “## Scope guardrails”, compact inventory authority** — Keep compact entries distinct from full content so later delta handling can reject changes to omitted existing content.

- **The plan’s “## Scope guardrails”, model and validation authority** — Keep this module deterministic and structural. Do not add quality scores, semantic judgments, model calls, or new roadmap gates.

- **The plan’s “## Out of scope”, retrieval and configurable context** — Do not add search, embeddings, arbitrary file access, summaries, configurable expansion counts, or a general context framework.

## Deferred

- **Candidate delta application and full-content authorization enforcement** — Step 6 owns applying a typed delta and rejecting changes that the issued capsule does not authorize.

- **Model orchestration and durable capsule reuse** — Steps 7 and 8 own proposal calls, lineage records, persistence of each issued capsule, and exact reuse after the lineage's final capsule is established.

- **A shared public canonical-value encoder** — `plan_tool/roadmap_source_identity.py:_canonical_value()` and `_json_bytes()` are private source-identity helpers. Extracting a shared contract is a cross-module refactor and belongs in reconcile work, not this two-file feature step.
