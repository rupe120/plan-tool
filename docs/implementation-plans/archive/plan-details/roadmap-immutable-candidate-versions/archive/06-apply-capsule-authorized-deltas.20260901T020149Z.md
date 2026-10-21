> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Apply capsule-authorized deltas into complete gate-checked candidates and bind their deterministic diffs

## Summary

Create `plan_tool/roadmap_candidate.py` and `tests/test_roadmap_candidate.py` as the pure materialization boundary for one proposed roadmap candidate. The module accepts an immutable accepted predecessor, the exact context capsule issued for this proposal, and a typed delta; it returns one complete four-artifact candidate only when every change is authorized and the full roadmap passes its gates. The key design decision is copy-on-write assembly: unchanged stage bytes stay exactly as stored, while changed stages are rebuilt through their typed parser and renderer. On green, the result carries a fixed content identity, deterministic diff, and stage-ordered gate evidence without writing a version or changing the accepted head.

## Table of Contents

- [Summary](#summary) — The candidate materialization outcome and its narrow boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why a cross-artifact proposal needs deterministic assembly before review.
- [Input](#input) — The predecessor, issued capsule, stage, and relation contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and their roles.
- [Implementation](#implementation) — Delta authority, copy-on-write assembly, gates, diffing, and identity rules.
- [Tests](#tests) — Direct coverage for authorization, byte preservation, gates, and deterministic bindings.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a complete inert candidate.
- [References](#references) — Closed-record and deterministic-identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that constrain candidate materialization.
- [Deferred](#deferred) — Lifecycle work that remains with later steps.

## Why

`plan_tool/roadmap_revision_patch.py:merge_stage_revision()` and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` each build a bounded candidate for one existing writer route, but neither can assemble one immutable cross-artifact proposal from a lineage capsule. Step 5 establishes which complete row bodies and relations are safe edit authority, so this step must turn only that authority into a complete, inspectable candidate before any question, answer, storage, or promotion path can act on it.

## Input

- **Accepted predecessor:** Step 3 supplies one selected accepted version with its fixed version identity and all stored artifact bytes in `plan_tool/roadmap.py:STAGES` order. Parse those stored bytes only through the matching `RoadmapStage.parse`; do not read top-level roadmap files or select another stored version.

- **Issued proposal capsule:** Step 5 supplies the exact capsule and receipt issued for this proposal, including its predecessor binding, selected feedback identity, full-content members, declared-relation evidence, compact inventory, and any recorded expansion. Require an exact predecessor and feedback match before applying a delta. The storage/review layers decide whether an unexpanded issued capsule later becomes final or is replaced by the one permitted expanded capsule.

- **Typed artifact operations:** `plan_tool/roadmap_artifacts.py:design_row_collections()` exposes stable design-row membership, while `replace_stage_row()`, `append_stage_row()`, `remove_stage_row()`, `append_plan_ordering_entry()`, and `remove_plan_ordering_entry()` show the typed immutable-update style. Keep candidate operations within typed artifact values; do not accept raw artifact text or source-span edits.

- **Relation inventory:** `plan_tool/roadmap_relations.py:extract_declared_relations()` provides the stage- and source-ordered relation inventory used to prove changed relations and build the deterministic diff.

- **Full-roadmap gates:** Step 1 supplies the created complete-candidate input and its direct `check_complete_roadmap_gates()` route. Materialization must derive one matched, stage-ordered text/artifact/digest input from the assembled complete candidate; it must not capture live sources or construct a `RoadmapImpactSnapshot`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate.py` — Define the closed typed-delta contract, candidate materialization boundary, deterministic diff and identity records, authorization checks, and full-roadmap gate result.
  - `tests/test_roadmap_candidate.py` — Cover complete assembly, authority refusals, byte preservation, gate rejection, diff ordering, and identity bindings.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Apply a capsule-authorized typed delta copy-on-write, then bind the complete candidate’s deterministic diff.

- **Keep the boundary pure.** Accept immutable predecessor and capsule values plus one already-decoded typed delta. Do not accept a plans directory, filesystem callback, model callback, writer token, answer, review seal, or accepted-head selector. Materialization must neither write candidate storage nor change any source or version file.

- **Require exact input binding.** Confirm that the issued capsule names the supplied predecessor version and selected feedback exactly. Treat a mismatched predecessor, feedback row, context receipt, malformed typed delta, unknown operation, or invalid row or relation anchor as a refusal with no partial candidate.

- **Use full content as edit authority.** Permit an existing row change only when that exact predecessor row appears as a full-content capsule member. For every added, removed, or changed relation, require each endpoint that exists in the predecessor to appear as a full-content capsule member. A compact-inventory item may identify a row but must never authorize changing it or attaching a relation to it.

- **Anchor new content.** Require each new row or relation to name the selected feedback and a reached full-content member or declared relation that justifies its placement. A newly created row may be one relation endpoint, but every other endpoint that already exists must satisfy the full-membership rule above. Do not let a typed delta create an unanchored row, relation, artifact, or broad rewrite.

- **Preserve feedback as input evidence.** Bind the selected feedback to the candidate record and keep predecessor feedback rows unchanged by candidate materialization. Do not treat a proposal as a feedback response, review decision, answer, or promotion authorization.

- **Assemble all stages before checking gates.** Start from the predecessor’s complete `plan_tool/roadmap.py:STAGES`-ordered artifact set. Copy bytes for every unchanged stage exactly. For a changed typed artifact, render it with its matching `RoadmapStage.render`, parse the rendered text again with `RoadmapStage.parse`, and retain the rendered bytes as that candidate stage’s bytes.

- **Run one complete gate walk.** Build step 1's complete-candidate input from every assembled stage's key, exact candidate text, parsed artifact, and raw text digest, then pass it once to `plan_tool/roadmap_impact_snapshot.py:check_complete_roadmap_gates()`. Do not capture a live snapshot, run separate `CandidateSubstitution` checks, or let an omitted stage fall back to predecessor content. Reject the candidate when evidence validation fails or any `RoadmapGateOutcome` carries violations, and retain the ordered all-green outcomes as candidate evidence.

- **Compute a deterministic diff from typed facts.** Compare the predecessor and assembled artifacts in stage order. Record changed artifact identities, changed design rows with their before and after values, and added or removed declared relations using `design_row_collections()` and `extract_declared_relations()` ordering. Do not use sets, directory order, raw delta operation order, semantic equivalence, or prose-quality judgment as the diff contract.

- **Bind one fixed content identity.** Derive the materialized candidate's content identity from deterministic encoding of the predecessor version identity, selected feedback identity, exact issued capsule receipt, complete candidate bytes or digests, and deterministic diff. The result identifies the exact proposed content rather than a newest candidate, a re-read source state, or a logically similar later model response. It deliberately does not encode answers: steps 7 and 8 derive the stored candidate-version identity from this content identity plus the immutable review lineage, allowing an unchanged answer-informed payload to remain a distinct replacement version.

- **Keep the legacy mergers separate.** Do not extend `plan_tool/roadmap_revision_patch.py:merge_stage_revision()` or `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` into a cross-artifact authority path. Their stage and evidence contracts remain independent from this new capsule-bound route.

## Tests

Use a four-stage predecessor fixture with one selected feedback row, a cross-artifact relation, one full-content closure member, and one compact-inventory-only row.

### Tests for this step

- `test_candidate_applies_an_authorized_cross_artifact_delta_as_one_complete_stage_ordered_bundle` — An authorized delta changes the intended typed artifacts and returns all stages in `plan_tool/roadmap.py:STAGES` order.

- `test_candidate_copies_unchanged_predecessor_bytes_without_re_rendering` — Every untouched stage retains the exact stored predecessor bytes even when parsing those bytes would allow a different rendered form.

- `test_candidate_renders_and_reparses_each_changed_typed_artifact` — Each changed stage byte sequence comes from its stage renderer and parses back to the retained candidate artifact.

- `test_candidate_requires_the_final_capsule_to_bind_the_supplied_predecessor_and_feedback` — A capsule for another predecessor, receipt, or selected feedback row refuses before assembly.

- `test_candidate_rejects_an_existing_row_change_authorized_only_by_compact_inventory` — An omitted row’s compact identity cannot authorize a replacement or removal.

- `test_candidate_requires_full_membership_for_every_predecessor_relation_endpoint` — Adding, removing, or changing a relation refuses when any endpoint that exists in the predecessor lacks full-content capsule authority, including a new relation anchored at another full member.

- `test_candidate_requires_new_content_to_anchor_to_feedback_and_reached_context` — An added row or relation without the selected feedback and a valid reached anchor refuses.

- `test_candidate_preserves_predecessor_feedback_rows_and_binds_selected_feedback_separately` — Materialization does not convert feedback into a response or review action, while the candidate record retains the selected feedback binding.

- `test_candidate_runs_one_full_roadmap_gate_walk_over_all_candidate_artifacts` — A later-stage gate receives every assembled candidate artifact and a violation rejects the whole candidate.

- `test_candidate_gate_input_binds_text_parsed_artifact_and_digest_for_every_stage` — A two-artifact delta is gated only through one complete matched input; missing or predecessor-substituted evidence refuses before a gate result can be retained.

- `test_candidate_diff_is_stage_and_source_ordered_for_rows_relations_and_artifacts` — The diff records changed rows, relations, and artifact identities in deterministic order rather than operation or mapping order.

- `test_candidate_content_identity_binds_predecessor_feedback_issued_capsule_complete_bytes_and_diff` — Changing any required content-identity input produces a different materialized binding or a refusal; answer lineage remains a storage-layer version binding.

- `test_candidate_materialization_has_no_filesystem_or_accepted_head_side_effect` — The boundary returns an in-memory candidate or refusal without storing a version or changing accepted-head state.

Every named test in `tests/test_roadmap_candidate.py` must be green before this step is complete.

## Acceptance criteria

- The new materialization boundary accepts only a typed delta bound to one accepted predecessor and the exact capsule issued for that proposal.

- The result contains complete stage-ordered candidate bytes, parsed candidate artifacts, all-green full-roadmap gate outcomes, a deterministic diff, and a fixed content identity for later candidate-version storage.

- Full-roadmap acceptance receives one complete stage-ordered text/artifact/digest input and never validates a multi-artifact candidate through one-stage substitutions.

- An unchanged stage’s candidate bytes equal its predecessor’s stored bytes exactly.

- A changed stage’s candidate bytes come from its matching `RoadmapStage.render()` result and parse back through the matching `RoadmapStage.parse()` result.

- A delta cannot change an existing row or add, remove, or change a relation when any predecessor endpoint lacks full-content capsule authority; a compact-inventory entry cannot bypass that rule.

- A delta cannot add content without a selected-feedback and reached-context anchor.

- A gate failure, malformed delta, stale binding, or unauthorized change returns no candidate and causes no write or accepted-head change.

- `tests/test_roadmap_candidate.py` passes.

## References

- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use a closed response shape for typed proposed deltas that deterministic code can reject safely.

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen records with forbidden extra fields for the delta and candidate contracts.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use deterministic JSON encoding and strict decoding for candidate and diff identity inputs.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 to bind the complete candidate, its predecessor, issued capsule, and diff.

- [RFC 8785: JSON Canonicalization Scheme (JCS)](https://datatracker.ietf.org/doc/html/rfc8785) — Review canonical JSON rules before fixing the candidate content-identity preimage.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Materialize one reviewable inert candidate only; do not add a broader roadmap editing path.

- **The plan’s “## Scope guardrails”, binary observables** — Make candidate bytes, content identity, gate outcomes, context membership, and diff records deterministic and directly testable.

- **The plan’s “## Scope guardrails”, model authority** — Treat the delta as inert input. This module must not let it mutate stored versions, move the accepted head, answer a question, or authorize promotion.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Keep predecessor, feedback, candidate content identity, later answer-bound version identity, answers, and review seals separate. This step stops after candidate materialization and gate acceptance.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Enforce full-content authority for existing content and refuse rather than widening capsule membership or using inventory data as an edit grant.

- **The plan’s “## Scope guardrails”, validation authority** — Validate shape, bindings, anchors, diffs, and existing gates only. Do not score or judge the quality, completeness, truth, or equivalence of roadmap prose.

- **The plan’s “## Out of scope”, direct writes and lifecycle expansion** — Do not add candidate persistence, direct model-to-canonical writes, automatic promotion, review workflow, retrieval, or a generic editor.

## Deferred

- **Candidate storage and proposal orchestration** — Step 7 owns invoking the model and storing only a gate-clean inert candidate.

- **Question generation, answers, replacement version identities, and immutable review seals** — Step 8 owns the review lineage that consumes this candidate's diff and content identity.

- **Accepted-head promotion** — Step 9 owns approving an exact review seal and changing only the accepted-head selector.

- **Shared merger consolidation** — `plan_tool/roadmap_revision_patch.py:merge_stage_revision()` and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` have different authority contracts. Consolidating them with this new boundary requires a separate reconcile or refactor step.
