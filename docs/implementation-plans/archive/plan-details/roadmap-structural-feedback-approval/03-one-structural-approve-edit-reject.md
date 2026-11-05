> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add one explicit structural approve, edit, or reject decision while retaining immutable candidate history

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add one explicit structural decision boundary over the stored structural candidate in `plan_tool/roadmap_candidate_review.py`. Approval seals the exact displayed active candidate directly, including an initial proposal; edit uses one correction to make an unapproved replacement for a fresh decision; rejection releases the active candidate. Extend the existing review seal and journaled candidate lifecycle for these outcomes. On green, focused tests prove that each decision preserves the accepted head and candidate history.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the decision boundary and result.
- [Table of Contents](#table-of-contents) — Quick links to this detail file.
- [Why](#why) — Why the existing review sequence needs an explicit user outcome.
- [Input](#input) — Stored candidate and review contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The five existing files changed by this step.
- [Implementation](#implementation) — Decision behavior, atomicity, and lifecycle boundaries.
- [Tests](#tests) — Focused decision, history, and refusal coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contracts governing candidates, feedback, and promotion.
- [Applicable guardrails](#applicable-guardrails) — Plan fences that bind this decision surface.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/roadmap_candidate_review.py:seal_review` currently needs a generated question, answer, and replacement before it can seal. That sequence cannot approve the initial candidate a reviewer sees without an extra user gate. Structural work needs one explicit decision over the exact active candidate; edit may produce a replacement, but only a later approve decision can seal it.

## Input

- **Step 2 stored route facts:** Consume the persisted structural route and normalized operations from `plan_tool/roadmap_candidate_run.py:CandidateProposalEvidence`. Do not infer structural status from model prose, a current ledger view, or a fresh diff.
- **Active-candidate identity:** Use `plan_tool/roadmap_candidate_run.py:CandidateProposalAdmission` and `load_candidate_admission` as the current root and active-candidate selector. A decision must bind the candidate it observed and refuse if that pointer changes before publication.
- **Review lineage:** Preserve existing question, answer, replacement, and seal bindings for legacy review. A direct structural approval extends `CandidateReviewSeal` to bind an active candidate without inventing question or answer records; an edit may use the existing replacement lineage internally.
- **Terminal history:** Reuse `plan_tool/roadmap_candidate_run.py:CandidateTerminalResolution`, `new_terminal_resolution`, and `build_terminal_resolution_generation` for rejection. Their batch receipt and root/source bindings remain the evidence for a released candidate.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py` — Add the shared structural approve, edit, or reject decision behavior around the existing review and release records.
  - `plan_tool/roadmap_candidate_run.py` — Extend only the existing candidate evidence, pointer, supersession, or terminal-generation helpers if the explicit decision needs a durable binding they do not already provide.
  - `plan_tool/prompts/roadmap-candidate-delta.md` — Clarify the closed replacement prompt contract for an edit decision without granting new operation authority.
  - `tests/test_roadmap_candidate_review.py` — Add decision lifecycle, stale-state, atomic-publication, and immutable-history coverage.
  - `tests/test_roadmap_candidate_run.py` — Add focused persistence or replay coverage for any candidate-run contract extended by this step.

## Implementation

- **Make the outcome explicit.** Add one closed structural decision surface near `plan_tool/roadmap_candidate_review.py:seal_review`, `answer_candidate_question`, and `reject_candidate_review`. It must accept exactly approve, edit, or reject semantics for one active structural candidate; unknown, incomplete, stale, or invalid requests must refuse without changing canonical roadmap state.

- **Approve the displayed candidate directly.** Extend `CandidateReviewSeal` with a structural direct-approval form that binds the active candidate's stored identity and exact bytes without a question inventory, answer, or replacement. Keep existing seal identities and validation for answered replacements unchanged. Approval writes the seal but does not move the active pointer, update `AcceptedRoadmapHead`, or call the promotion writer.

- **Treat edit as an unapproved replacement.** Use the supplied correction as the only user answer. Reuse the question/answer/replacement records as internal bindings where needed, but do not require a separate user question or call `seal_review` as part of edit. Revalidate the replacement's normalized operations and deterministic route against its own source; a replacement that no longer qualifies as structural cannot enter this structural decision path. Persist the valid structural route and operations in its `CandidateProposalEvidence`, never inheriting the initial route by assumption. Store the replacement immutably, then make it active with its supersession and ledger effects in one existing journaled publication; leave it unsealed for a fresh approve/edit/reject decision.

- **Keep rejection a release.** Reuse `reject_candidate_review` and `_release_active_candidate` so rejection writes the immutable `CandidateTerminalResolution` and clears only the matching active pointer through `build_terminal_resolution_generation`. Do not delete candidate bytes, rewrite ledger history, or create a replacement candidate on rejection.

- **Preserve publication atomicity.** Use `publish_roadmap_generation` and the existing before-replace checks. Approval publishes only its exact seal; edit couples supersession, active-pointer replacement, and selected-ledger effects; reject pairs the terminal record with pointer release. A changed admission, ledger, root, candidate, or review binding must refuse before a partial generation becomes visible.

- **Keep the prompt bounded.** Update `plan_tool/prompts/roadmap-candidate-delta.md` so an edit decision can use the supplied review pair as context while retaining the closed JSON envelope, issued-reviewer-item authority, and typed-operation restrictions. The prompt must not let the question, answer, or decision text authorize extra feedback items, operations, relation edits, or artifact content.

- **Do not widen into CLI work.** Keep this step at the lifecycle and prompt boundary. A later CLI step can map user-facing arguments to the closed decision surface; do not add command registration or capability-catalog changes here.

## Tests

### Tests for this step

- `tests/test_roadmap_candidate_review.py::test_structural_approval_seals_the_displayed_initial_candidate_without_a_question` — approval succeeds for the exact active initial candidate without generating a question, answer, or replacement and leaves the accepted head unchanged.
- `tests/test_roadmap_candidate_review.py::test_structural_edit_publishes_an_unapproved_replacement_without_an_extra_user_answer` — one correction creates a distinct active replacement, preserves prior candidate history, and leaves that replacement unsealed for a fresh decision.
- `tests/test_roadmap_candidate_review.py::test_structural_edit_persists_its_own_validated_operations_and_route` — the active replacement reloads with its own normalized operation set and structural route; a mismatched or bounded replacement cannot become active through the structural decision path.
- `tests/test_roadmap_candidate_review.py::test_structural_rejection_records_terminal_history_and_releases_only_the_active_pointer` — rejection writes the matching terminal resolution, clears the active pointer, and changes neither the accepted head nor stored candidate bytes.
- `tests/test_roadmap_candidate_review.py::test_structural_decision_refuses_stale_or_nonactive_candidate_without_writes` — a stale, superseded, released, or substituted candidate produces no publication.
- `tests/test_roadmap_candidate_review.py::test_edit_keeps_ledger_and_pointer_updates_in_one_generation` — selected awaiting-review items and the pointer change together on edit; unrelated or reopened items remain unchanged.
- `tests/test_roadmap_candidate_run.py::test_structural_decision_persistence_replays_the_stored_route_and_candidate_binding` — any new stored decision binding reloads only when it agrees with the persisted candidate evidence and admission pointer.
- `tests/test_roadmap_candidate_run.py::test_structural_decision_generation_refuses_a_changed_pointer_or_ledger_before_publication` — final currentness checks prevent partial decision publication.
- `tests/test_roadmap_candidate_run.py::test_candidate_delta_prompt_keeps_review_pair_context_from_granting_operation_authority` — the rendered batch prompt names the review-pair context while retaining its closed operation and reviewer-item limits.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A structural candidate has one explicit approve, edit, or reject outcome.
- Approval creates or reuses an exact direct review seal for the displayed active candidate without requiring question, answer, or replacement records and does not advance `AcceptedRoadmapHead`.
- Edit consumes one user correction, produces an active immutable replacement without a seal, and records supersession through the existing publication path; it needs a fresh decision.
- Reject writes a matching `CandidateTerminalResolution` and releases only the current active pointer.
- Stale, invalid, interrupted, rejected, and edited proposals do not rewrite canonical roadmap artifacts, seeds, or the accepted head.
- Candidate and review history remains readable after edit, approval, or rejection.
- `tests/test_roadmap_candidate_review.py` and `tests/test_roadmap_candidate_run.py` pass.

## References

- [Roadmap Structural Feedback Approval handoff — Read the settled single-decision direction and reuse boundary.](../../../../../handoffs/2026-09-22-roadmap-feedback-revision-approval.md)
- [ROADMAP_FORMAT.md — Read the canonical artifact, feedback, and structural rewrite contracts.](../../../../../ROADMAP_FORMAT.md)
- [ROADMAP_FEEDBACK_FORMAT.md — Read mutable ledger ownership and reviewer-feedback lifecycle rules.](../../../../../ROADMAP_FEEDBACK_FORMAT.md)
- [DATA_CONTRACT.md — Read persisted candidate, review, publication, and recovery contracts.](../../../../../DATA_CONTRACT.md)
- [plan_tool/roadmap_candidate_review.py — Read the existing question, replacement, seal, and release bindings.](../../../../../plan_tool/roadmap_candidate_review.py)
- [plan_tool/roadmap_candidate_run.py — Read active-pointer, supersession, terminal-resolution, and publication helpers.](../../../../../plan_tool/roadmap_candidate_run.py)
- [plan_tool/roadmap_version_promotion.py — Read the sole accepted-head promotion path.](../../../../../plan_tool/roadmap_version_promotion.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, explicit structural decision boundary** — Keep approve, edit, and reject tied to one fully validated structural successor; do not add a second intake or candidate store.
- **The plan’s “## Scope guardrails”, canonical selector boundary** — Do not make this step an accepted-head writer or a live-artifact rewrite path.
- **The plan’s “## Scope guardrails”, exact approval boundary** — Bind approval to the stored reviewed candidate and refuse stale or broken evidence rather than recovering through mutable state.
- **The plan’s “## Scope guardrails”, retained-history boundary** — Keep edits and rejection journaled through existing immutable records and generation publication.
- **The plan’s “## Out of scope”, decision-surface limits** — Do not add route-selection input, automatic approval, parallel queues, broad feedback grouping, or new transaction infrastructure.

## Deferred

- CLI arguments, parser registration, operator output, and capability-catalog registration for the decision surface — A later CLI-focused step owns user-facing wiring and must land its capability entry with the registered command.
- Promotion after approval — `plan_tool/roadmap_version_promotion.py` remains a separate exact-seal and accepted-head operation.
