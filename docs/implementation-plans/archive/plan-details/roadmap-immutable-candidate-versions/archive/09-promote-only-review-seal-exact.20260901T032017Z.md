> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Promote only a review seal’s exact candidate by replacing the accepted-head selector while preserving every version file

## Summary

Create `plan_tool/roadmap_version_promotion.py` and `tests/test_roadmap_version_promotion.py` as the deterministic approval boundary for an enrolled roadmap. The new module validates one explicit immutable review seal, confirms its replacement candidate still descends from the current accepted head, and publishes the replacement selector through the shared journal boundary. The key design decision is selector-only promotion: it must not regenerate, copy, or rewrite candidate, root, source, or review records. On green, accepted-head resolution returns the sealed candidate while every stored version file keeps its original bytes.

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

`plan_tool/roadmap_revision_publish.py:_publish_generation()` already journals exact member replacements, but its current wrappers publish live roadmap artifacts rather than approving an immutable review lineage. Step 3 provides accepted-head selection, and step 8 provides a review seal for one answer-informed replacement. This step connects those two records without letting a seal, candidate recency, or equivalent regenerated content become implicit canonical authority.

## Input

- **Complete candidate gate check:** Step 1 provides the direct complete-bundle gate route. Its current full-roadmap anchor is `plan_tool/roadmap_impact_snapshot.py:check_full_roadmap_gates()`. Promotion must recheck the stored complete candidate rather than trust a recorded green result alone.

- **Immutable version selection:** Step 3 provides the accepted-head selector and complete stored root-or-candidate contract. Use that contract to load the current accepted predecessor and the sealed candidate; do not derive paths from directory order or fill a missing member from live roadmap files.

- **Candidate evidence:** Step 6 provides the materialized candidate’s content identity, complete artifact bytes, raw brief binding, predecessor diff, and gate evidence. Promotion must verify the stored record, not reconstruct a delta or render a replacement.

- **Review seal:** Step 8 provides the immutable seal, question inventory, answer records, answer-incorporation record, and answer-bound replacement identity. Treat the seal as evidence to verify, not as authority that moves the head by itself.

- **Durable publication:** Step 2 exposes the shared guarded publication boundary from `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Build its input with `plan_tool/roadmap_source_identity.py:PendingGeneration` and `GenerationMember`, and require the active token through `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_version_promotion.py` — Add explicit review-seal promotion, exact lineage validation, candidate gate rechecks, stale-head protection, and selector-only publication.
  - `tests/test_roadmap_version_promotion.py` — Cover successful promotion, binding failures, publication timing, and unchanged stored members.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Promote one sealed replacement only when its recorded predecessor is still the current accepted head, then replace only the accepted-head selector.

- **Keep the entry point explicit.** Add a narrow operation such as `promote_review_seal()` in `plan_tool/roadmap_version_promotion.py`. It must take an explicit seal reference, roadmap identity, and active `RoadmapWriterToken`. It must not choose a candidate by recency, scan storage for a candidate, prompt a reviewer, or accept model output.

- **Verify the whole sealed lineage.** Load the seal, its feedback admission, question inventory, answer records, answer-incorporation record, replacement candidate, and accepted predecessor through the contracts delivered by steps 3, 6, and 8. Every stored identity and binding must agree with the seal’s candidate-version and content identities. Missing, malformed, changed, or substituted evidence must refuse before publishing the selector.

- **Require the sealed version, not equivalent content.** Confirm both the candidate-version identity and content identity named by the seal. Do not accept another stored candidate merely because its bytes, parsed form, or content identity match.

- **Recheck the stored candidate as a complete bundle.** Verify the stored raw brief bytes and digest, each staged artifact’s bytes and digest, the stored content identity, predecessor diff, and final capsule binding. Reparse every staged artifact in `plan_tool/roadmap.py:STAGES` order, then use step 1’s complete-bundle gate route once over that matched set. Do not build a `RoadmapImpactSnapshot`, read live sources, or substitute a predecessor member into the candidate gate context.

- **Protect against stale selection twice.** Before publication, require the candidate’s predecessor identity to equal the current accepted head. The final recheck callback supplied to step 2’s publication boundary must repeat that comparison after journaling and before selector replacement. `plan_tool/roadmap_revision_publish.py:publish_structural_revision_proof()` provides the current final-recheck pattern; promotion must reuse the shared publisher, not that live-artifact writer.

- **Publish one member only.** Create a `PendingGeneration` with one `GenerationMember`: the accepted-head selector’s recorded old bytes and the exact selector bytes for the sealed candidate-version identity. Do not include candidate storage, root records, review records, top-level artifacts, baselines, seed state, or any other member.

- **Reuse the writer guard and journal.** Validate the active matching token before reading mutable selection state. Send the completed generation through step 2’s public publication boundary. Do not copy `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()`, `plan_tool/roadmap_source_identity.py:render_pending_generation()`, or `plan_tool/roadmap_revision_publish.py:_replace_generation_members()` into the new module.

- **Consume admission through the promoted selector.** After the selector names the sealed candidate, rely on the immutable admission, seal, and accepted head as the terminal proof that the feedback lineage is consumed. Do not add a consumption sidecar or rewrite the stored `FeedbackRow`.

- **Leave legacy writers unchanged.** `plan_tool/roadmap_revision_publish.py:publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()` retain the enrolled-roadmap refusal delivered by step 4 and their unversioned behavior.

## Tests

### Tests for this step

- `tests/test_roadmap_version_promotion.py:test_promotion_replaces_only_the_accepted_head_selector_for_the_exact_sealed_candidate` — A valid seal moves accepted-head resolution to its bound replacement candidate.

- `tests/test_roadmap_version_promotion.py:test_promotion_preserves_every_existing_candidate_root_and_review_file` — Capture stored member bytes before promotion and prove that only the selector changes.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_one_complete_exact_review_seal_lineage` — Missing, changed, or substituted admissions, questions, answers, incorporation records, or candidates refuse without moving the head.

- `tests/test_roadmap_version_promotion.py:test_promotion_refuses_a_candidate_version_other_than_the_one_bound_by_the_review_seal` — Equal content does not permit a different answer-bound version to replace the sealed version.

- `tests/test_roadmap_version_promotion.py:test_promotion_rechecks_complete_stored_candidate_bytes_raw_brief_and_full_roadmap_gates` — Malformed, incomplete, digest-mismatched, or gate-failing stored evidence refuses; valid raw brief bytes are checked without normalization.

- `tests/test_roadmap_version_promotion.py:test_promotion_uses_one_matched_complete_candidate_gate_input` — Every stored stage is reparsed and gated together, with no predecessor or live-file substitution.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_the_current_head_to_match_the_sealed_candidate_predecessor` — A seal from a non-current predecessor refuses and keeps the selector unchanged.

- `tests/test_roadmap_version_promotion.py:test_promotion_rechecks_head_predecessor_inside_the_journal_window` — A selector change after preflight causes the final recheck to refuse, preserves the newer selector, and removes the pre-write journal.

- `tests/test_roadmap_version_promotion.py:test_promotion_requires_an_active_matching_writer_token_and_writes_only_the_selector` — Missing, inactive, and foreign tokens refuse before mutation; success records one selector member.

- `tests/test_roadmap_version_promotion.py:test_promotion_has_no_model_or_candidate_regeneration_path` — Promotion uses stored deterministic evidence and does not invoke a model, delta materializer, or artifact renderer.

- `tests/test_roadmap_version_promotion.py:test_promoted_head_terminally_consumes_the_feedback_admission_without_an_extra_member` — The promoted head prevents another lineage for the same admission while stored feedback bytes remain unchanged.

**Green-before-done gate:** Every listed test in `tests/test_roadmap_version_promotion.py` must be green before this step is complete.

## Acceptance criteria

- A valid explicit review seal promotes only its fixed candidate-version identity and content identity.

- Promotion verifies the complete sealed review lineage, stored candidate evidence, raw brief binding, predecessor diff, and complete gate result before changing selection.

- Promotion checks the sealed candidate’s predecessor against the accepted head before publication and inside the journaled final recheck.

- The published generation replaces only the accepted-head selector.

- Missing, malformed, stale, substituted, or gate-failing evidence refuses without changing the selector or stored version files.

- Promotion requires an active matching `RoadmapWriterToken` and uses the shared journal publication boundary.

- Accepted-head selection of the sealed candidate consumes the stored feedback admission without a new sidecar or feedback rewrite.

- `tests/test_roadmap_version_promotion.py` passes.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review atomic replacement semantics used by the shared publication boundary.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Review strict record decoding for selectors and immutable evidence.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 bindings for stored candidate and review identities.

- [RFC 8785: JSON Canonicalization Scheme](https://datatracker.ietf.org/doc/html/rfc8785) — Review stable JSON identity inputs for immutable records.

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
