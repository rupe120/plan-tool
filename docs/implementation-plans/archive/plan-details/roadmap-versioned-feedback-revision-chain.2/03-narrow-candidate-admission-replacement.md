> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 3 — Narrow candidate admission to one accepted-head generation and store one inert batch successor

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_candidate_run.py` so candidate admission is tied to one accepted-head generation and its complete active-feedback batch, rather than to a caller-selected feedback row. Keep one admission reusable while that accepted head remains current, then replace it only when promotion makes a different accepted head current. Update `plan_tool/prompts/roadmap-candidate-delta.md` so model output may cite only feedback ids from the issued batch. Extend `tests/test_roadmap_candidate_run.py` to prove retry, stale-admission replacement, and inert storage behavior. On green, one accepted head produces at most one stored batch candidate, without moving the accepted-head selector.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the admission and storage change.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why a selector-bound admission cannot safely span accepted-head generations.
- [Input](#input) — Upstream batch and successor contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three scoped file edits.
- [Implementation](#implementation) — Accepted-head admission, batch prompt, and inert-storage rules.
- [Tests](#tests) — Focused coverage for admission replacement and retries.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant lifecycle and persistence contracts.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope limits for this step.
- [Deferred](#deferred) — Adjacent lifecycle work left to other steps.

## Why

`plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()` currently creates an admission from one `ARTIFACT:FEEDBACK_ID` selector and then refuses another selector indefinitely. That leaves a promoted accepted head unable to begin its own complete feedback generation, while also allowing the old admission to remain the runner’s effective selection source. Admission must instead follow the accepted-head selector: retries retain one exact batch for the current head, and a later accepted head starts one new batch successor.

## Input

- **Step 1 batch contract:** Consume the ordered active-feedback batch and exact identity from step 1’s `plan_tool/roadmap_candidate_context.py` capsule and receipt. Do not rebuild eligibility, reorder members, or select one member inside this runner.

- **Step 2 successor contract:** Store the complete materialized batch successor from step 2 through `plan_tool/roadmap_candidate.py:materialize_candidate()`. Its typed operation and feedback-lifecycle rules remain owned by that module.

- **Accepted-head authority:** Read the current accepted version through `plan_tool/roadmap_versions.py:load_accepted_version()` while holding `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`. The admission’s predecessor must match that accepted version before it can be reused.

- **Persisted admission and evidence:** Preserve the closed-record and canonical-byte rules in `CandidateProposalAdmission`, `CandidateProposalEvidence`, `render_candidate_admission()`, and `render_candidate_evidence()`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py` — Bind admission reuse and replacement to the current accepted-head generation, carry the batch identity through storage and replay checks, and retain one inert candidate per admitted batch.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Replace singular selected-feedback instructions with exact issued-batch authorization instructions.
  - `tests/test_roadmap_candidate_run.py` — Update selector-based fixtures and add accepted-head generation, batch, retry, and inert-storage coverage.

## Implementation

- **Make the accepted head the admission boundary.** Adapt `run_initial_candidate_proposal()` and the admission path around `load_candidate_admission()` so an existing admission is reusable only when its predecessor is the current accepted version. A matching admission must retain its issued capsule, receipt, expansion state, and stored candidate binding for retries.

- **Replace only for a new accepted-head generation.** When the accepted-head selector identifies a different immutable version, build one fresh batch context from that accepted version and replace the stale admission under the existing writer guard. Do not use a caller-provided feedback selector to decide whether an admission is compatible.

- **Keep retries exact.** For an admission whose predecessor still matches the accepted head, do not recompile context from live artifacts or replace the batch because a caller supplies different routing input. Re-entry before storage must resume the persisted batch; re-entry after storage must return the recorded candidate without a backend call.

- **Store one inert successor for the admitted batch.** Keep `_store_candidate()` and its publication generation as the only storage path. The stored candidate, `CandidateProposalEvidence`, and visible admission must bind the same predecessor, batch identity, capsule receipt, complete artifact set, and gate evidence. Candidate storage must not update `AcceptedRoadmapHead`.

- **Reject stale work before model invocation.** If the accepted head changes after an admission was formed but before a compatible candidate can be used, refuse or replace only through the accepted-head-generation rule before invoking the backend. Do not materialize a candidate against a predecessor that is no longer the accepted head.

- **Make the prompt batch-authorized.** Update `plan_tool/prompts/roadmap-candidate-delta.md` and `render_candidate_delta_prompt()` so the prompt does not nominate one feedback id. Each delta operation must name an exact feedback id from the issued batch in the capsule; ids outside that batch remain invalid through the materializer’s existing authority checks.

- **Keep the bounded expansion flow.** Preserve the one-expansion limit and its persisted `expansion_available` state. Expansion may enrich the already admitted batch context, but it must not create a second admission generation or loosen the batch identity.

- **Retain current persistence owners.** Reuse `publish_roadmap_generation()` and the existing admission/evidence paths. Do not add a second candidate store, accepted-head writer, checkpoint format, or recovery path.

## Tests

### Tests for this step

- `test_current_accepted_head_creates_one_batch_admission` — asserts a first run binds the accepted version and complete batch, then stores one candidate whose evidence matches that admission.

- `test_matching_accepted_head_reuses_persisted_batch_before_storage` — asserts a retry uses the persisted capsule and receipt rather than rebuilding context or changing batch membership.

- `test_stored_batch_candidate_reentry_skips_backend_call` — asserts a matching accepted head returns the admitted stored candidate with zero calls.

- `test_new_accepted_head_replaces_stale_admission_with_one_new_batch` — promotes or otherwise supplies a later accepted head, then asserts the next proposal binds that head and stores a successor whose predecessor is the new head.

- `test_new_accepted_head_does_not_reuse_old_candidate_or_batch` — asserts an old admission’s candidate id, capsule, and batch identity cannot satisfy a run for the newer accepted head.

- `test_routing_selector_cannot_override_admitted_batch` — asserts caller routing input cannot select a different feedback row or alter a matching admission’s batch.

- `test_batch_prompt_requires_operation_feedback_ids_from_issued_batch` — asserts `plan_tool/prompts/roadmap-candidate-delta.md` gives batch-based authorization and does not instruct the model to use one selected feedback id.

- `test_batch_candidate_storage_keeps_accepted_head_unchanged` — asserts successful storage publishes candidate and evidence records while leaving `AcceptedRoadmapHead` unchanged.

- `test_expanded_batch_retry_preserves_one_admission_generation` — asserts a persisted expansion resumes as the same admitted batch and cannot request another expansion.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `run_initial_candidate_proposal()` reuses an admission only when its predecessor version is the current accepted-head version.

- A later accepted-head version replaces the old admission with one fresh complete-feedback batch before candidate storage.

- A retry against an unchanged accepted head uses the persisted batch identity and does not allow routing input to substitute a feedback member.

- One admitted batch stores at most one inert candidate, and later re-entry returns that candidate without another backend call.

- Stored evidence, admission, candidate record, capsule, receipt, and batch identity all name the same accepted predecessor.

- A successful candidate proposal does not modify the accepted-head selector.

- The candidate-delta prompt authorizes operation feedback ids from the issued batch without naming a singular selected feedback id.

- `tests/test_roadmap_candidate_run.py` passes with the updated batch and accepted-head generation cases.

## References

- [ROADMAP_FORMAT.md — Read the immutable-version, candidate, feedback lifecycle, and accepted-head contracts.](../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read the persisted admission, candidate, review, and publication record requirements.](../DATA_CONTRACT.md)

- [docs/how-to/roadmap.md — Read the operator lifecycle from enrollment through candidate storage and promotion.](../docs/how-to/roadmap.md)

- [plan_tool/roadmap_candidate_run.py — Read the current fixed-admission, bounded proposal, evidence replay, and publication flow.](../plan_tool/roadmap_candidate_run.py)

- [plan_tool/roadmap_candidate_context.py — Read the batch capsule and receipt contract supplied by step 1.](../plan_tool/roadmap_candidate_context.py)

- [plan_tool/roadmap_candidate.py — Read complete batch successor materialization and operation authority supplied by step 2.](../plan_tool/roadmap_candidate.py)

- [plan_tool/roadmap_versions.py — Read accepted-head loading and immutable version storage contracts.](../plan_tool/roadmap_versions.py)

- [plan_tool/roadmap_revision_publish.py — Read the shared guarded publication boundary.](../plan_tool/roadmap_revision_publish.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, accepted-head authority** — This step must treat `AcceptedRoadmapHead` as the only canonical selector. Candidate admission and storage may not make a candidate canonical.

- **The plan’s “## Scope guardrails”, exact predecessor and batch identity** — This step must refuse stale bindings before accepted-head movement and must retain one exact batch for retries.

- **The plan’s “## Scope guardrails”, inert candidate behavior** — This step may store a candidate and its evidence, but it must not consume feedback or alter the accepted version.

- **The plan’s “## Scope guardrails”, existing owner reuse** — This step must use the existing version, candidate, journal, and recovery owners instead of adding a parallel persistence or authority path.

- **The plan’s “## Out of scope”, lifecycle and review protocol changes** — This step must not add feedback states, change review behavior, alter promotion, or expand individual candidate operation semantics.

## Deferred

- `plan_tool/roadmap_candidate_review.py` and `plan_tool/roadmap_version_promotion.py` batch-field migration — Later lifecycle steps own review and promotion adaptation; this step keeps the admission boundary compatible with their existing ownership.

- CLI removal or redesign of selector-shaped proposal input — This step prevents selector input from controlling admission, but command-surface changes belong to the CLI-routing work.
