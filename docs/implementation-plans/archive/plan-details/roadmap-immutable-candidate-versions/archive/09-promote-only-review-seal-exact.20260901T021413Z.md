> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Promote only a review seal’s exact candidate by replacing the accepted-head selector while preserving every version file

## Summary

Create `plan_tool/roadmap_version_promotion.py` and `tests/test_roadmap_version_promotion.py` as the deterministic approval boundary for an enrolled roadmap. The module validates one explicit immutable review seal against its stored replacement candidate and the current accepted predecessor, then publishes a replacement accepted-head selector through the shared durable publication boundary. The key decision is that promotion changes the selector only: it never regenerates, copies, or rewrites candidate, root, source, or review files. On green, accepted-head resolution selects the sealed candidate while every existing stored file retains its exact bytes.

## Table of Contents

- [Summary](#summary) — The promotion outcome and narrow file footprint.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why a review seal needs a deterministic selector-only approval path.
- [Input](#input) — The version, candidate, seal, gate, and publication contracts promotion reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and their roles.
- [Implementation](#implementation) — Exact seal validation, stale-head protection, and selector-only publication.
- [Tests](#tests) — Coverage for promotion, refusals, and unchanged stored files.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completing promotion.
- [References](#references) — Durable replacement and exact-record guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that limit approval behavior.
- [Deferred](#deferred) — Reader, writer, CLI, and lifecycle work owned elsewhere.

## Why

`plan_tool/roadmap_revision_publish.py:_publish_generation()` can durably replace recorded files, but its current wrappers publish artifact generations rather than approving a completed immutable review lineage. Step 3 establishes accepted-head selection, and step 8 establishes a seal for one answer-informed replacement candidate; this step must connect those records without turning a candidate, a seal, or a newest-file rule into implicit canonical authority.

## Input

- **Accepted-head state:** Step 3 provides `plan_tool/roadmap_versions.py:load_accepted_version()` and its selector-owned version boundary. Use that boundary to identify the currently selected version and to verify the candidate’s recorded predecessor; do not rebuild version paths, inspect directory order, or read top-level roadmap artifacts.

- **Stored candidate:** Step 6 provides the fixed materialized content identity, while steps 3, 7, and 8 provide one shared-contract stored candidate version with its answer-bound version identity, predecessor binding, exact raw brief bytes and digest, complete artifact bytes, persisted predecessor diff, final capsule binding, and full-roadmap gate evidence. Promotion must load the candidate through the accepted-version storage boundary and reject a missing, changed, or substituted candidate.

- **Review seal:** Step 8 provides the immutable review seal binding the replacement candidate, question inventory, answer identities, and answer-incorporation record. Treat the seal as evidence to verify, not as a command that can move the head by itself.

- **Full-roadmap gates:** Step 1 provides the created complete-candidate input and direct `check_complete_roadmap_gates()` route. Rebuild one matched all-stage gate input only from the complete stored candidate before promotion; do not capture live sources or construct a `RoadmapImpactSnapshot`, and do not trust a previously recorded green result alone.

- **Publication transaction:** Step 2 exposes the guarded publication boundary built from `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Use `plan_tool/roadmap_source_identity.py:PendingGeneration` and `GenerationMember` with the active `RoadmapWriterToken` required by `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_version_promotion.py` — Define the explicit review-seal approval entry point, exact lineage checks, full-candidate recheck, stale-head protection, and selector-only publication.
  - `tests/test_roadmap_version_promotion.py` — Cover successful approval, exact-binding refusals, stale-head refusal, gate rechecks, and unchanged stored files.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic:** Approve one sealed replacement candidate only when its recorded predecessor remains the current accepted head, then atomically replace only the accepted-head selector.

- **Keep approval explicit and narrow.** Expose one small entry point, such as `promote_review_seal()`, that accepts an explicit review-seal reference, roadmap identity, and active writer token. It must not choose a candidate by recency, scan a candidate directory, accept model output, or prompt a reviewer.

- **Validate the full immutable lineage.** Load the selected seal, its feedback-lineage admission, question inventory, every answer record, answer-incorporation record, and replacement candidate version through the storage boundaries from steps 3 and 6 through 8. Require the admitted feedback and predecessor, version identity, materialized content identity, predecessor diff, final capsule binding, and review identities to agree exactly with one another and with the seal's candidate binding. A missing admission, question, answer, incorporation record, candidate, or mismatched identity must refuse before selector publication.

- **Require the sealed candidate version, not equivalent content.** Compare both candidate version and content identities named by the seal with the loaded stored version. Do not regenerate a delta, re-render an artifact, compare semantic meaning, or substitute another candidate version whose bytes or content identity happen to match but whose answer lineage differs.

- **Recheck complete candidate content.** Verify the stored candidate's shared version record, exact raw brief bytes and digest, complete stage-ordered bytes, content identity, version identity, final capsule binding, and persisted diff. Reparse every stored stage, build step 1's complete-candidate input from its key, exact text, parsed artifact, and raw digest, then call `check_complete_roadmap_gates()` once. Any malformed stored artifact, evidence mismatch, missing stage, predecessor fallback, live-source dependency, or gate outcome with violations must refuse without moving the head.

- **Protect against a stale accepted head.** Require the sealed candidate’s predecessor identity to equal the version selected by the accepted-head boundary. Repeat that comparison in the final callback passed to the step 2 publication boundary, after journaling and before replacement, so a head change between preflight and publication cannot promote from an obsolete predecessor.

- **Publish the selector only.** Build one `PendingGeneration` whose sole `GenerationMember` replaces the accepted-head selector's current bytes with the exact selector bytes naming the sealed candidate-version identity. Do not include candidate storage, root records, stored artifacts, review records, top-level roadmap artifacts, baselines, seed state, or unrelated files in that generation.

- **Let exact promotion terminally consume the admission.** Do not write a consumption sidecar. After selector publication, the immutable admission and review seal plus the accepted head naming that seal's candidate are the terminal-consumption proof step 7 checks for the same stable feedback identity. The stored `FeedbackRow` remains byte-identical and may remain open; it cannot admit another lineage.

- **Reuse the guarded publisher.** Require the active matching `RoadmapWriterToken` before loading mutable selection state, and send the finished generation through the shared step 2 publication boundary. Do not duplicate `recover_roadmap_publication()`, journal encoding, byte replacement, or cleanup logic in `plan_tool/roadmap_version_promotion.py`.

- **Keep legacy publication separate.** `plan_tool/roadmap_revision_publish.py:publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()` retain their step 4 enrolled-roadmap refusal and unversioned contracts. This step must not route them through promotion or change that behavior.

## Tests

### Tests for this step

- `test_promotion_replaces_only_the_accepted_head_selector_for_the_exact_sealed_candidate` — A valid seal moves accepted-head selection to its replacement candidate, and the version boundary returns that candidate’s stored stage bytes.

- `test_promotion_preserves_every_existing_candidate_root_and_review_file` — Capture all stored version, candidate, and review bytes before approval and assert they remain unchanged after selector publication.

- `test_promotion_requires_one_complete_exact_review_seal_lineage` — A missing, changed, substituted, or unincorporated question or answer record refuses without changing the selector.

- `test_promotion_refuses_a_candidate_version_other_than_the_one_bound_by_the_review_seal` — A different candidate version, including one with matching content identity and bytes but different answer lineage, cannot replace the version identity named by the seal.

- `test_promotion_rechecks_complete_stored_candidate_bytes_raw_brief_and_full_roadmap_gates` — A changed raw brief binding, malformed, incomplete, or gate-failing stored candidate refuses before selector publication; a valid CRLF brief is verified without normalization.

- `test_promotion_rechecks_one_matched_complete_candidate_gate_input` — Promotion reparses and gates every stored candidate stage together; a missing, digest-mismatched, or predecessor-substituted member refuses before selector publication.

- `test_promotion_requires_the_current_head_to_match_the_sealed_candidate_predecessor` — A seal whose replacement starts from a non-current accepted predecessor refuses and leaves the head unchanged.

- `test_promotion_rechecks_head_predecessor_inside_the_journal_window` — A head change after preflight but before replacement causes refusal, removes the pre-write journal, and preserves the newer selector.

- `test_promotion_requires_an_active_matching_writer_token_and_never_writes_a_nonselector_member` — Missing, inactive, or foreign tokens refuse before mutation, while a successful generation contains only the accepted-head selector.

- `test_promotion_has_no_model_or_candidate_regeneration_path` — Promotion accepts stored deterministic records only and does not invoke a model, delta materializer, or artifact renderer.

- `test_promoted_head_terminally_consumes_the_feedback_admission_without_an_extra_member` — After selector-only promotion, the admission, seal, and accepted head classify the feedback as consumed, and a repeated proposal cannot open another lineage even though the stored feedback row is unchanged.

Every named test in `tests/test_roadmap_version_promotion.py` must be green before this step is complete.

## Acceptance criteria

- An explicit valid review seal promotes only the fixed candidate-version identity and materialized content identity it binds.

- Promotion verifies the complete sealed question-and-answer lineage, stored candidate version/content identities, exact raw brief bytes and digest, candidate bytes, persisted diff, final capsule binding, and full-roadmap gate result before changing selection.

- Promotion rechecks one matched complete-candidate gate input for all stages and never substitutes one candidate artifact into predecessor gate context.

- The sealed candidate’s predecessor must equal the accepted head during preflight and during the journaled final recheck.

- The promotion generation replaces only the accepted-head selector; all stored candidate, version, review, source, baseline, and seed-state files remain unchanged.

- A stale head, missing or substituted lineage member, changed candidate, malformed stored record, or gate failure refuses without changing the accepted-head selector.

- Promotion uses the shared guarded journal publisher and requires an active matching writer token.

- Exact accepted-head selection of the sealed candidate terminally consumes its immutable feedback admission without changing the selector-only generation or stored feedback bytes.

- `tests/test_roadmap_version_promotion.py` passes.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review the atomic replacement semantics used by the durable selector publication path.

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Review strict record decoding for selector and immutable-record validation.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Review SHA-256 bindings when verifying stored candidate and version bytes.

## Applicable guardrails

- **The plan’s “## Plan intent” and step intent** — Make explicit deterministic approval the only selector-changing operation; do not add another canonical write path.

- **The plan’s “## Scope guardrails”, binary observables** — Verify stored bytes, identities, predecessor equality, seals, and gate outcomes directly rather than judging equivalence or quality.

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit this step to promotion and accepted-head selection; preserve unversioned behavior and existing writer behavior.

- **The plan’s “## Scope guardrails”, model authority** — Keep promotion free of model calls, model-written manifests, candidate regeneration, and automatic approval.

- **The plan’s “## Scope guardrails”, lifecycle order and distinct bindings** — Require the completed review lineage before promotion and keep the seal, candidate, predecessor, feedback, and answers as separate records.

- **The plan’s “## Scope guardrails”, smallest functional happy path** — Build one direct approval path and reuse the existing publication primitive instead of adding workflow states or version-management features.

- **The plan’s “## Out of scope”, direct writes and operational hardening** — Do not add rollback UI, retention, concurrency features, bulk migration, or a second recovery protocol.

## Deferred

- **Version-aware downstream reader migration** — Step 10 owns routing `plan_tool/roadmap_view.py:load_roadmap()` through accepted-head resolution.

- **CLI parsing and the end-to-end operator flow** — Step 11 owns command-level approval input and presentation.

- **Rollback, history, retention, and concurrent workflow support** — These remain outside the plan’s bounded promotion proof.
