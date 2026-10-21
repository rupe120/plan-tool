> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Apply capsule-authorized deltas into complete gate-checked candidates and bind their deterministic diffs

## Summary

Create `plan_tool/roadmap_candidate.py` and `tests/test_roadmap_candidate.py` as the pure materialization boundary for one proposed roadmap candidate. The module parses one closed typed delta, applies only capsule-authorized changes to an immutable predecessor, and returns a complete stage-ordered candidate only when the shared full-roadmap gates pass. The key design decision is copy-on-write assembly: unchanged stored artifact bytes remain unchanged, while changed typed artifacts are rendered and reparsed through their matching stage contract. On green, the result carries fixed candidate content identity, deterministic predecessor diff, and ordered gate evidence without writing a version or moving the accepted head.

## Table of Contents

- [Summary](#summary) — The candidate materialization outcome and narrow boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why a cross-artifact proposal needs deterministic assembly before review.
- [Input](#input) — The predecessor, issued capsule, stage, relation, and gate contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and their roles.
- [Implementation](#implementation) — Delta parsing, authority checks, assembly, gates, diffs, and identity rules.
- [Tests](#tests) — Direct coverage for parsing, authority, byte preservation, gates, and bindings.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for a complete inert candidate.
- [References](#references) — Closed-record and deterministic-identity guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that constrain candidate materialization.
- [Deferred](#deferred) — Lifecycle work that remains with later steps.

## Why

`plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `merge_stage_revision()` build candidates for existing same-artifact writer routes, while `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` produces one source-bound structural candidate. None can apply a bounded cross-artifact proposal from immutable context. Step 5 supplies the exact full-content authority needed to make that proposal safe, so this step must turn only that authority into a complete inspectable candidate before storage, questions, answers, or promotion can act on it.

## Input

- **Accepted predecessor:** Step 3 supplies one selected immutable version with complete stored artifact bytes in `plan_tool/roadmap.py:STAGES` order. Parse those bytes only through the matching `RoadmapStage.parse`; do not read top-level roadmap files or select another version.

- **Issued capsule:** Step 5 supplies the exact issued capsule and receipt, including its predecessor binding, selected feedback identity, full-content members, declared-relation evidence, compact inventory, and recorded expansion state. Require exact predecessor, feedback, and receipt bindings before applying a delta.

- **Typed artifact updates:** `plan_tool/roadmap_artifacts.py:stage_row_collections()`, `append_stage_row()`, `replace_stage_row()`, and `remove_stage_row()` show the immutable typed-update style. `plan_tool/roadmap_artifacts.py:append_plan_ordering_entry()` and `remove_plan_ordering_entry()` cover the plans-specific ordering value.

- **Relations:** `plan_tool/roadmap_relations.py:extract_declared_relations()` provides the stage- and source-ordered relation inventory for authorization checks and deterministic diffs.

- **Strict response precedent:** `plan_tool/roadmap_revision.py:parse_revision_operations()` defines the existing one-object JSON refusal shape. Mirror its duplicate-key, non-finite-value, trailing-content, and extra-field refusals in this module’s delta parser without importing its live-revision types.

- **Complete gate boundary:** Step 1 supplies the direct complete-candidate gate route in `plan_tool/roadmap_impact_snapshot.py`. Build its complete evidence from the assembled candidate; do not use the snapshot-based `check_full_roadmap_gates()` or `CandidateSubstitution` path.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_candidate.py` — Define the closed delta parser and records, materialization boundary, authorization checks, deterministic diff, content identity, and gate result.
  - `tests/test_roadmap_candidate.py` — Cover parsing, complete assembly, authority refusals, byte preservation, gates, diff order, and identity bindings.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Apply a capsule-authorized typed delta copy-on-write, then bind the complete candidate’s deterministic diff.

- **Own one closed parser and materializer.** Define clear public boundaries such as `parse_candidate_delta()` and `materialize_candidate()`. The parser must accept exactly one closed JSON delta object and return immutable typed operation records. The materializer must accept only that parsed delta, the immutable predecessor, and the exact issued capsule.

- **Keep model output inert.** The delta vocabulary must express only the typed row and declared-relation changes needed for the representative cross-artifact case. It must not accept raw artifact text, source spans, filesystem paths, feedback state changes, version selection, answers, seals, or promotion instructions.

- **Reject malformed input before assembly.** Refuse duplicate keys, non-standard JSON constants, trailing data, unknown fields, unknown operations, invalid typed rows, invalid anchors, and any mismatched predecessor, feedback, or capsule receipt. Return no partial candidate.

- **Use full content as edit authority.** Permit an existing row change only when that exact predecessor row is a full-content capsule member. A compact-inventory entry may identify omitted content but must never authorize an edit.

- **Protect relation endpoints.** For every added, removed, or changed declared relation, require each endpoint that already exists in the predecessor to be a full-content capsule member. A new row may be one endpoint, but every existing endpoint must meet the membership rule.

- **Require a bounded anchor for new content.** Require each added row and each added or changed relation to bind to the selected feedback and to a reached full-content member or declared relation. Do not let a delta create an unanchored row, relation, artifact, or broad rewrite.

- **Preserve feedback evidence.** Keep every predecessor feedback row unchanged. Bind the selected feedback separately in the materialized result; candidate materialization must not treat a proposal as a feedback response or review action.

- **Assemble every stage before gates run.** Begin from the predecessor’s complete `plan_tool/roadmap.py:STAGES`-ordered bundle. Copy each unchanged stage’s stored bytes exactly. For each changed artifact, use its matching `RoadmapStage.render()`, encode the result as UTF-8 bytes, and verify that `RoadmapStage.parse()` recreates the retained typed artifact.

- **Use one complete gate walk.** Build Step 1’s direct gate input from every assembled stage’s key, exact text, parsed artifact, and raw-byte SHA-256 digest. Reject missing, mismatched, or substituted evidence before retaining any gate result. Reject the candidate when any ordered `RoadmapGateOutcome` contains a violation.

- **Produce a deterministic diff from typed facts.** Compare predecessor and candidate artifacts in stage order. Record changed artifact identities, complete before-and-after values for changed rows, and added or removed declared relations using `design_row_collections()` and `extract_declared_relations()` ordering. Do not use mapping order, sets, directory order, raw operation order, or prose-quality judgment as the diff contract.

- **Bind one fixed content identity.** Derive the candidate content identity from deterministic encoding of its predecessor identity, selected feedback identity, issued capsule receipt, complete candidate bytes or digests, and deterministic diff. The identity must not include later answer lineage; steps 7 and 8 own the separate stored candidate-version binding.

- **Leave legacy mergers separate.** Keep `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()`, `merge_stage_revision()`, and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` unchanged. Their authority and source contracts remain separate from this capsule-bound route.

## Tests

Build a four-stage predecessor fixture with one selected feedback row, a cross-artifact relation, one full-content closure member, and one compact-inventory-only row.

### Tests for this step

- `test_parse_candidate_delta_refuses_non_single_duplicate_or_extra_json_input` — Duplicate keys, non-standard constants, trailing text, unknown fields, and unknown operations refuse before materialization.

- `test_candidate_applies_an_authorized_cross_artifact_delta_as_one_complete_stage_ordered_bundle` — An authorized delta changes the intended typed artifacts and returns all stages in `plan_tool/roadmap.py:STAGES` order.

- `test_candidate_copies_unchanged_predecessor_bytes_without_re_rendering` — Every untouched stage retains its exact stored predecessor bytes.

- `test_candidate_renders_and_reparses_each_changed_typed_artifact` — Each changed stage uses its matching renderer and parses back to the retained candidate artifact.

- `test_candidate_requires_the_final_capsule_to_bind_the_supplied_predecessor_feedback_and_receipt` — A capsule for another predecessor, feedback row, or receipt refuses before assembly.

- `test_candidate_rejects_an_existing_row_change_authorized_only_by_compact_inventory` — An omitted row’s compact identity cannot authorize replacement or removal.

- `test_candidate_requires_full_membership_for_every_existing_relation_endpoint` — Added, removed, and changed relations refuse when an existing endpoint lacks full-content capsule authority.

- `test_candidate_requires_new_content_to_anchor_to_feedback_and_reached_context` — An added row or relation without selected-feedback and reached-context anchors refuses.

- `test_candidate_preserves_predecessor_feedback_rows_and_binds_selected_feedback_separately` — Materialization changes neither feedback state nor response fields while retaining the selected feedback binding.

- `test_candidate_runs_one_complete_gate_walk_over_all_candidate_artifacts` — A later-stage gate receives the assembled candidate bundle and one violation rejects the candidate.

- `test_candidate_gate_input_binds_text_parsed_artifact_and_digest_for_every_stage` — Missing, stale, or predecessor-substituted evidence refuses before green outcomes are retained.

- `test_candidate_diff_is_stage_and_source_ordered_for_rows_relations_and_artifacts` — The diff records changed rows, relations, and artifact identities independently of operation or mapping order.

- `test_candidate_content_identity_binds_predecessor_feedback_capsule_complete_bytes_and_diff` — Changing any identity input changes the materialized binding or causes refusal, while later answer lineage stays outside this identity.

- `test_candidate_materialization_has_no_filesystem_or_accepted_head_side_effect` — The boundary returns an in-memory candidate or refusal without storing a version or changing accepted-head state.

Every named test in `tests/test_roadmap_candidate.py` must be green before this step is complete.

## Acceptance criteria

- `plan_tool/roadmap_candidate.py` parses only a closed typed delta contract and refuses malformed or unauthorized input without returning a partial candidate.

- The materialization result contains complete stage-ordered candidate bytes, parsed artifacts, all-green full-roadmap gate outcomes, deterministic predecessor diff, and fixed content identity.

- Full-roadmap acceptance receives one complete stage-ordered text, artifact, and digest input. It does not validate a multi-artifact candidate through snapshot capture or single-stage substitutions.

- An unchanged stage’s candidate bytes equal its predecessor’s stored bytes exactly.

- A changed stage’s candidate bytes come from the matching `RoadmapStage.render()` result and parse through the matching `RoadmapStage.parse()` result.

- A delta cannot change an existing row or add, remove, or change a relation when an existing endpoint lacks full-content capsule authority. Compact inventory cannot bypass that rule.

- A delta cannot add content without selected-feedback and reached-context anchors.

- A gate failure, malformed delta, stale binding, or unauthorized change returns no candidate and causes no write or accepted-head change.

- `tests/test_roadmap_candidate.py` passes.

## References

- [Structured outputs - Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Use a closed response shape for proposed deltas that deterministic code can reject safely.

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen records with forbidden extra fields for delta and candidate contracts.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Use strict decoding and deterministic encoding for delta and identity inputs.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind complete candidate evidence and identity inputs with SHA-256.

- [RFC 8785: JSON Canonicalization Scheme](https://datatracker.ietf.org/doc/html/rfc8785) — Review stable JSON rules before fixing the candidate content-identity preimage.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Materialize one inert reviewable candidate only; do not add a broader roadmap editing path.

- **The plan’s “## Scope guardrails”, binary observables** — Keep candidate bytes, content identity, gate outcomes, context membership, and diff records deterministic and directly testable.

- **The plan’s “## Scope guardrails”, model authority** — Treat the delta as inert input. This module must not mutate stored versions, move the accepted head, answer a question, or authorize promotion.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Keep predecessor, feedback, candidate content identity, later candidate-version identity, answers, and seals separate. Stop after candidate materialization and gate acceptance.

- **The plan’s “## Scope guardrails”, context omission and compact inventory authority** — Require full-content authority and refuse rather than widening capsule membership or treating compact inventory as edit authority.

- **The plan’s “## Scope guardrails”, validation authority** — Validate shape, bindings, anchors, diffs, and existing gates only. Do not judge roadmap prose quality, completeness, truth, or equivalence.

- **The plan’s “## Out of scope”, direct writes and lifecycle expansion** — Do not add candidate persistence, direct model-to-canonical writes, automatic promotion, review workflow, retrieval, or a generic editor.

## Deferred

- **Candidate storage and proposal orchestration** — Step 7 owns backend invocation and persistence of gate-clean inert candidates.

- **Questions, answers, replacement version identities, and review seals** — Step 8 owns the review lineage that consumes this candidate’s diff and content identity.

- **Accepted-head promotion** — Step 9 owns approval of a review seal and accepted-head replacement.

- **Shared merger consolidation** — The existing candidate mergers have different authority contracts. Consolidation requires a separate reconcile or refactor step.
