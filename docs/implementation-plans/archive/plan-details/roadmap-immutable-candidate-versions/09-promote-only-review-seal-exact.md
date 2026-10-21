> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Promote only a review seal’s exact candidate by replacing the accepted-head selector while preserving every version file

## Summary

Create `plan_tool/roadmap_version_promotion.py` and `tests/test_roadmap_version_promotion.py` as the deterministic approval boundary for an enrolled roadmap. The module validates one explicit review seal, confirms its replacement candidate still descends from the current accepted head, and publishes a replacement selector through step 2’s shared journal boundary. Promotion changes only the accepted-head selector; it must not regenerate, copy, or rewrite candidate, root, source, or review records. On green, accepted-head resolution selects the sealed candidate and every existing stored version file keeps its original bytes.

## Table of Contents

- [Summary](#summary) — The promotion result and narrow file scope.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why sealed review evidence needs an explicit selector move.
- [Input](#input) — The upstream version, review, gate, and publication contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files this step creates.
- [Implementation](#implementation) — Exact binding checks, stale-head protection, and selector-only publication.
- [Tests](#tests) — Focused promotion and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable write and identity references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this approval path.
- [Deferred](#deferred) — Lifecycle work owned by later steps.

## Why

`plan_tool/roadmap_revision_publish.py:_publish_generation()` already journals exact file replacements, but its current callers publish live roadmap artifacts rather than approve an immutable review lineage. Step 3 provides accepted-head selection, and step 8 provides a seal for one answer-informed replacement. This step connects those records without allowing seal presence, candidate recency, or equivalent regenerated content to become implicit canonical authority.

## Input

- **Accepted version:** Step 3 provides the selector-owned immutable version reader. Use it to load the current accepted predecessor and the candidate named by the seal; do not derive storage paths from directory order or fill missing members from live roadmap files.

- **Candidate evidence:** Step 6 provides complete candidate bytes, content identity, predecessor diff, and complete-bundle gate evidence. Revalidate the stored candidate rather than reconstructing a delta or rendering replacement artifacts.

- **Review evidence:** Step 8 provides the immutable review seal and its bound question inventory, answers, incorporation record, replacement candidate, and final capsule. Treat the seal as evidence to validate, not an object that moves the accepted head itself.

- **Gate walk:** Step 1 preserves the ordered evaluator currently reached through `plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()`, and step 6 adds its direct complete-bundle input. Promotion must use the direct route for the stored candidate.

- **Publication:** Step 2 exposes the guarded publication boundary currently implemented around `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Build its input with `plan_tool/roadmap_source_identity.py:PendingGeneration` and `GenerationMember`, and retain the active-token requirement from `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_version_promotion.py` — Add explicit review-seal promotion, exact lineage validation, complete candidate rechecks, stale-head protection, and selector-only publication.
  - `tests/test_roadmap_version_promotion.py` — Cover successful promotion, refusal paths, final-recheck timing, and unchanged stored members.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Promote one sealed replacement only when its recorded predecessor remains the current accepted head, then replace only the accepted-head selector.

- **Keep approval explicit.** Add one narrow entry point, such as `promote_review_seal()`, in `plan_tool/roadmap_version_promotion.py`. It must accept an explicit seal identity, roadmap identity, and active `RoadmapWriterToken`. It must not choose a candidate by recency, scan storage for a candidate, prompt a reviewer, or accept model output.

- **Validate the complete sealed lineage.** Load the seal, immutable lineage admission, question inventory, answer records, incorporation record, replacement candidate, and accepted predecessor through the boundaries delivered by steps 3, 6, and 8. Their identities and bindings must agree with the candidate version and content identities named by the seal. Missing, malformed, changed, or substituted evidence must refuse before selector publication.

- **Require the sealed version, not equivalent content.** Confirm both the candidate-version identity and content identity named by the seal. Do not accept another stored candidate because its bytes, parsed form, or content identity match.

- **Recheck stored candidate evidence.** Validate the stored raw brief bytes and digest, stage bytes and digests, content identity, predecessor diff, and final capsule binding. Reparse every staged artifact in `plan_tool/roadmap.py:STAGES` order, then run step 6’s direct complete-bundle gate route once over that matched set. Do not build a `RoadmapImpactSnapshot`, read live inputs, or use a single-stage substitution.

- **Protect against stale selection twice.** Before publication, require the sealed candidate’s predecessor identity to equal the current accepted head. Repeat that check in the final callback passed to step 2’s publisher after journaling and before replacement. Follow the final-recheck shape used by `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof()`, without calling that live-artifact writer.

- **Publish one member only.** Build a `PendingGeneration` containing one `GenerationMember`: the accepted-head selector’s recorded old bytes and the exact selector bytes naming the sealed candidate version. Do not include stored candidates, roots, review records, top-level artifacts, baselines, seed state, or other files.

- **Reuse the existing write boundary.** Require the active matching token before reading mutable selector state, then send the prepared generation through step 2’s public publisher. Do not copy `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`, `plan_tool/roadmap_source_identity.py:render_pending_generation()`, or `plan_tool/roadmap_revision_publish.py:_replace_generation_members()` into the new module.

- **Keep the fixed admission terminal through promotion.** After successful publication, rely on the immutable roadmap admission, review seal, and accepted head as the terminal proof that the representative feedback lineage is consumed. Do not clear or replace the admission for another feedback, add a consumption sidecar, or rewrite the stored feedback row.

- **Keep existing writers unchanged.** `plan_tool/roadmap_revision_publish.py:publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()` retain the enrolled-roadmap refusal from step 4 and their unversioned behavior.

## Tests

### Tests for this step

- `tests/test_roadmap_version_promotion.py:test_promotion_replaces_only_the_accepted_head_selector_for_the_exact_sealed_candidate` — A valid seal moves accepted-head resolution to its bound replacement candidate.

- `tests/test_roadmap_version_promotion.py:test_promotion_preserves_every_existing_stored_version_and_review_file` — Capture stored member bytes before promotion and prove that only the selector changes.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_one_complete_exact_review_seal_lineage` — Missing, changed, or substituted admission, question, answer, incorporation, capsule, or candidate evidence refuses without moving the head.

- `tests/test_roadmap_version_promotion.py:test_promotion_refuses_a_candidate_version_other_than_the_one_bound_by_the_review_seal` — Equal content does not permit a different answer-bound candidate version to replace the sealed version.

- `tests/test_roadmap_version_promotion.py:test_promotion_rechecks_complete_stored_candidate_bytes_raw_brief_and_gates` — Malformed, incomplete, digest-mismatched, or gate-failing stored evidence refuses without normalization or live-file reads.

- `tests/test_roadmap_version_promotion.py:test_promotion_uses_one_complete_stage_ordered_gate_input` — Every stored stage is reparsed and gated together, without predecessor or live-file substitution.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_the_current_head_to_match_the_sealed_candidate_predecessor` — A seal from a non-current predecessor refuses and leaves the selector unchanged.

- `tests/test_roadmap_version_promotion.py:test_promotion_rechecks_head_predecessor_inside_the_journal_window` — A selector change after preflight makes the final recheck refuse, preserves the newer selector, and removes the pre-write journal.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_an_active_matching_writer_token_and_writes_only_the_selector` — Missing, inactive, and foreign tokens refuse before mutation; success records one selector member.

- `tests/test_roadmap_version_promotion.py:test_promotion_has_no_model_or_candidate_regeneration_path` — Promotion uses stored deterministic evidence and does not invoke a model, delta materializer, or artifact renderer.

- `tests/test_roadmap_version_promotion.py:test_promoted_head_keeps_the_fixed_roadmap_admission_terminal_without_an_extra_member` — Promotion does not clear the admission or permit a different feedback lineage while stored feedback bytes remain unchanged.

**Green-before-done gate:** Every listed test in `tests/test_roadmap_version_promotion.py` must be green before this step is complete.

## Acceptance criteria

- A valid explicit review seal promotes only its fixed candidate-version identity and content identity.

- Promotion validates the complete sealed review lineage, stored candidate evidence, raw brief binding, predecessor diff, capsule binding, and complete gate result before changing selection.

- Promotion checks the sealed candidate’s predecessor against the accepted head before publication and inside the journaled final recheck.

- The published generation replaces only the accepted-head selector.

- Missing, malformed, stale, substituted, or gate-failing evidence refuses without changing the selector or stored version files.

- Promotion requires an active matching `RoadmapWriterToken` and uses the shared journal publication boundary.

- Accepted-head selection of the sealed candidate leaves the fixed roadmap admission as terminal proof and cannot admit a different feedback without a sidecar or feedback rewrite.

- `tests/test_roadmap_version_promotion.py` passes.

## References

- [os — Miscellaneous operating system interfaceshttps: — Review atomic replacement semantics used by the shared publication boundary.

- [json — JSON encoder and decoderhttps: — Review strict record decoding for selectors and immutable evidence.

- [hashlib — Secure hashes and message digestshttps: — Review SHA-256 bindings for stored candidate and review identities.

- [RFC 8785: JSON Canonicalization Schemehttps: — Review stable JSON identity inputs for immutable records.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Make deterministic approval the only selector-changing operation in this step.

- **The plan’s “## Scope guardrails”, binary observables** — Validate stored bytes, identities, predecessor equality, seal bindings, and gate outcomes directly.

- **The plan’s “## Scope guardrails”, model authority** — Keep promotion free of model calls, generated manifests, candidate regeneration, and automatic approval.

- **The plan’s “## Scope guardrails”, lifecycle ordering and distinct bindings** — Require the completed sealed lineage and keep its feedback, predecessor, candidate, answers, and seal distinct.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit the behavior change to accepted-head promotion while preserving unversioned and legacy-writer behavior.

- **The plan’s “## Out of scope”** — Do not add rollback, retention, branching, broader recovery, or a general version-management workflow.

## Deferred

- **Version-aware downstream reader migration** — Step 10 owns `plan_tool/roadmap_view.py:load_roadmap()` routing through accepted-head selection.

- **CLI approval input and result presentation** — Step 11 owns the operator-facing lifecycle surface.

- **Rollback, history, retention, and concurrent workflows** — These exceed the plan’s single-reviewer promotion proof.
