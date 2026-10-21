---
format_version: 1
title: Roadmap Structural Feedback Approval
intent: Ordinary roadmap feedback that requires typed structural changes produces
  one inert, fully validated successor revision and reaches one explicit approve/edit/reject
  gate. For a structural proposal, only approval may advance the accepted head; rejection,
  edit, staleness, invalid model output, and failed application leave canonical roadmap
  state unchanged.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-structural-feedback-approval.md
steps:
- id: 1
  title: Classify validated candidate operations, keeping row removals and semantic
    changes inert and structural while reusing the existing presentation-field rules
  intent: Ensure ordinary feedback reaches structural review only when its validated
    operation set changes more than the established presentation surface.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  allowed_mentions:
  - plan_tool/roadmap_candidate_run.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/01-classify-validated-candidate-operations.md
  status: done
- id: 2
  title: Persist the typed operation set and structural route while preserving atomic
    ledger overwrite and active-candidate replacement
  intent: Give later review and promotion exact stored facts instead of requiring
    them to reconstruct route selection from mutable input.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the deterministic classification and normalized operation evidence
      that candidate storage must bind.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/02-persist-typed-operation-set-structural.md
  status: done
- id: 3
  title: Add one structural approve, edit, or reject decision while preserving journaled
    edit replacement, reject release, and immutable candidate history
  intent: Let a reviewer inspect the exact affected artifacts, rows, relations, ordering
    effects, consequences, and non-goals before choosing one explicit outcome.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - tests/test_roadmap_candidate_review.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: Provides the stored structural route, typed operations, candidate bytes, and
      batch bindings used by every decision.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/03-one-structural-approve-edit-reject.md
  status: done
- id: 4
  title: Add enrolled seed invalidation and recover complete promotion publications
  intent: Keep the accepted head, active pointer, and seed state together when an
    approved structural promotion is published or recovered.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Establishes which accepted candidate transitions are structural and therefore
      require promotion-time seed invalidation.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/04-enrolled-seed-invalidation-recover.md
  status: done
- id: 5
  title: Promote only exact approved candidate bytes while preserving atomic accepted-head
    overwrite and active-pointer release and adding seed invalidation
  intent: Make approval the only structural outcome that can advance the accepted
    head, with all freshness, binding, gate, pointer, and seed effects committed together.
  files:
  - plan_tool/roadmap_version_promotion.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: Provides an exact approval seal for the active candidate; an edit alone does
      not seal its replacement.
    4: Provides the seed-state member that joins the existing journaled promotion
      generation.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/05-promote-only-exact-approved-candidate.md
  status: done
- id: 6
  title: Expose the structural proposal and approve, edit, or reject choices through
    the ordinary roadmap feedback command
  intent: Give users one feedback intake and one decision surface with distinct results
    for invalid, stale, rejected, failed, edited, and promoted proposals.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 5
  depends_on_notes:
    3: Provides proposal rendering and the three exact decision outcomes.
    5: Provides backend-free approved promotion and its terminal success or refusal
      results.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/06-expose-structural-proposal-approve-edit.md
  status: done
- id: 7
  title: Document the unified feedback approval lifecycle and reconcile the approval
    work record
  intent: Make the bounded and structural routes, persisted bindings, failure preservation,
    seed effects, and second-revision behavior discoverable from their owning references.
  files:
  - ROADMAP_FEEDBACK_FORMAT.md
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - README.md
  - CAPABILITIES.md
  - docs/ARCHITECTURE.md
  - docs/how-to/roadmap.md
  - docs/cli/roadmap.md
  - tests/test_roadmap_feedback_format.py
  - tests/test_roadmap_format.py
  - tests/cli/test_cli_reference.py
  - BACKLOG.md
  - handoffs/2026-09-22-roadmap-feedback-revision-approval.md
  complexity: high
  change_type: non-code
  depends_on:
  - 6
  depends_on_notes:
    6: Provides the final command forms, outcomes, and complete stage-separated replay
      that the documentation must describe.
  detail: docs/implementation-plans/plan-details/roadmap-structural-feedback-approval/07-document-unified-feedback-approval.md
  status: done
---
# Roadmap Structural Feedback Approval

## Overview

Add the structural-approval layer that follows the versioned feedback revision chain. Users continue to submit ordinary feedback without classifying it. Plan Tool classifies a valid typed operation set internally, lets bounded presentation changes proceed through the current batch candidate lifecycle without structural approval, and routes broader same-artifact or cross-artifact operations to one reviewable proposal. The proposal reuses the existing immutable candidate, review binding, promotion, and publication authorities.

The approval-gate capability and its Integration provenance are recorded in `handoffs/2026-09-22-roadmap-feedback-revision-approval.md` and BACKLOG #423.

## Problem statement

The candidate delta vocabulary in `plan_tool/roadmap_candidate.py` admits `add-row`, `replace-row`, and `remove-row` operations with separate reviewer responses. Ordinary CLI feedback enters the candidate batch route, but no user-facing structural approval decision follows a valid structural candidate. The user should see the exact proposed roadmap change and a decision without choosing a structural feedback type or interpreting a generic parser failure. The older selected-local revision runner is not a CLI route (BACKLOG #429).

The immutable revision-history contract makes ordinary enrolled feedback enter the selector-free `--propose-candidate` batch route in `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()` from the current `AcceptedRoadmapHead` in `plan_tool/roadmap_versions.py`. A batch candidate binds its accepted root, its direct source, the eligible ledger-item snapshot, derived context, exact candidate bytes, and its receipt. This plan begins at that candidate boundary. It does not recreate enrollment, candidate storage, accepted-head selection, review sealing, promotion, or recovery.

## Architecture

Route selection is deterministic over a successfully parsed and authority-valid candidate delta, never over feedback wording. Bounded presentation changes retain their current candidate behavior without the new structural gate. Any authorized row addition, removal, non-presentation replacement, relation or ordering change, or multi-artifact effect becomes a structural proposal.

Each structural feedback process creates an immutable successor candidate from the current accepted head: accepted predecessor -> proposed successor -> approved promotion, with an unapproved replacement and fresh decision only when the reviewer chooses edit. This is a commit-like revision chain. The next feedback process starts from the successor promoted by the previous one, so revision history and feedback lineage remain explicit.

The successor candidate binds the admitted feedback identities, accepted root and direct source, brief identity, exact proposed artifact bytes, typed operation set, and validation result. Candidate construction carries changes through the full proposed artifact chain so downstream stages validate references and ordering against proposed upstream bytes. Invalid or incomplete proposals never reach approval.

One approval surface presents the requested outcome, affected artifacts and rows, relation or ordering effects, material consequences, and explicit non-goals. `approve` seals the exact displayed active candidate, including an initial proposal, without requiring a separate question and answer. `edit` uses the correction to make a replacement proposal, validates and stores that replacement's own operation set and route, then returns a valid structural replacement for a fresh decision without sealing it. `reject` releases the active candidate. The existing review, replacement, seal, supersession, and terminal-resolution owners carry these choices; an answer or replacement alone is not structural approval.

The approval binds persisted candidate and review facts. Initial batch evidence does not retain the model response, so a question cannot anchor on that response; replacement evidence retains what its identity recheck needs. The read-only ledger current/stale label (#428) and selector-era lineage release gap (#395) remain separate work.

Approved promotion rechecks the stored brief, recorded feedback binding, current accepted root and active candidate, candidate bytes, and validation binding before advancing `AcceptedRoadmapHead`. It uses the stored batch rather than rediscovering live ledger eligibility; unrelated reviewer edits do not invalidate recorded evidence. The existing publication journal and recovery boundary own the accepted-head write. The plan must identify any necessary feedback and seed effects within their existing owners. No failure may leave a partial accepted-head update or partial effects tied to that update.

Create must derive the per-outcome contract for `approve`, `edit`, and `reject`: producer, precedence, persisted binding, consumers, invalidation rule, operator-visible result, and exit path. It must also derive the structural-route boundary for each existing operation kind without broadening stage authority.

## Input

The immutable feedback revision-history surface supplies the ordinary-feedback handoff to an inert candidate rooted at the current accepted head. The existing candidate, review, promotion, and publication records are the contracts this effort consumes. This plan does not own their delivery or migration.

## Scope guardrails

There is one user-facing feedback intake and one active structural decision per proposal. An edit presents a replacement for a fresh decision. Users never pre-classify feedback as structural. Classification operates only on validated typed operations and grants no operation authority beyond the current candidate and stage policies.

`AcceptedRoadmapHead` remains the sole canonical selector for enrolled roadmaps. Proposal creation, review, edit, rejection, candidate storage, and validation never advance it or rewrite live top-level roadmap artifacts. Approval authorizes only the exact reviewed candidate; promotion remains the sole accepted-head writer and must reject a stale accepted root or active candidate, or a broken stored brief, feedback, candidate, decision, or gate binding. It does not rediscover live ledger eligibility. Every later feedback revision selects the promoted accepted version as its predecessor.

The implementation reuses the existing immutable candidate, review-seal, promotion, publication-journal, recovery, feedback, and seed-invalidation contracts wherever they satisfy this outcome. It may extend their structural metadata and user decision surface, but it must not create a second candidate store, accepted-head writer, version schema, checkpoint system, or publication transaction.

No proposal may be approved while invalid. Failed, rejected, edited, interrupted, and stale proposals cannot advance the accepted head or rewrite canonical artifacts or seeds. The existing lifecycle may retain immutable candidate/review history and update selected ledger items as the proposal progresses. Unselected feedback remains byte-for-byte unchanged.

## References

- [`handoffs/2026-09-22-roadmap-feedback-revision-approval.md`](../handoffs/2026-09-22-roadmap-feedback-revision-approval.md) — Approved work order, reconstruction provenance, and prerequisite boundaries.
- [`ROADMAP_FORMAT.md`](../ROADMAP_FORMAT.md) — Canonical roadmap artifacts, feedback rows, stage authority, and structural rewrite contracts.
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md) — Persisted roadmap version, candidate, review, and publication contracts.
- [`docs/how-to/roadmap.md`](../docs/how-to/roadmap.md) — Operator-facing roadmap, candidate review, and promotion workflow.
- [`docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`](../docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md) — Prerequisite routing of ordinary enrolled feedback into the immutable candidate chain.
- [`plan_tool/roadmap_candidate.py`](../plan_tool/roadmap_candidate.py) — Typed candidate operations, authority checks, and full-roadmap materialization.
- [`ROADMAP_FEEDBACK_FORMAT.md`](../ROADMAP_FEEDBACK_FORMAT.md) — Mutable ledger ownership and feedback lifecycle.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py) — Existing inert full-roadmap candidate construction and accepted-predecessor binding.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py) — Existing reviewer question, answer, replacement, and exact review-seal bindings.
- [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py) — Sole promotion path for a sealed candidate and current accepted predecessor.
- [`plan_tool/roadmap_versions.py`](../plan_tool/roadmap_versions.py) — Immutable version records and `AcceptedRoadmapHead` selector.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A second feedback type, structural flag, or user-authored route selection.
- Silent enrollment, automatic approval, automatic promotion, or acceptance without an exact user decision.
- New immutable-version, candidate-storage, accepted-head, checkpoint, recovery, or general transaction subsystems.
- Weakening candidate-delta or stage operation authority, or reviving the unreachable selected-local CLI route.
- Arbitrary project editing, workflow authoring, multi-user review, voting, assignments, or parallel approval queues.
- Automatic feedback grouping or splitting, and any specific scope-narrowing recommendation; broad or incoherent feedback may receive only the existing generic guidance outside this plan.
- A new raw-response retention or parser-forensics subsystem. Invalid model envelopes produce no proposal and use the existing safe failure-reporting boundary; richer protocol diagnostics remain separate work.
- Structural operations that current full-roadmap gates or stage authority cannot validate.

## Risks

Reusing candidate review can accidentally require a second question/answer gate before approving the displayed initial proposal, or mistake an edited replacement for approval. Building only the selected stage can validate against stale upstream bytes and admit a cross-artifact contradiction. Regenerating after approval can apply bytes the user never reviewed. Promotion recovery currently recognizes a completed selector-only journal but not the batch head-and-pointer publication; adding seed state widens that existing mismatch unless the publication owner recognizes the complete generation. A natural-language classifier can misroute requests and silently expand authority. The plan must keep these risks visible as ordering and identity properties.

## Testing

Use a stage-separated replay covering both route classes. At bare-plan stage, retain the properties that classification follows validated operations, one decision binds exact inert bytes, and every nonpublication exit preserves all canonical state; leave storage layout and prompt mechanics to detail. At detail-grounded stage, require focused coverage for presentation-only feedback, same-artifact addition/removal/edit, cross-artifact relation change, approve/edit/reject, stale predecessor or feedback, invalid envelope, pre-approval gate failure, completed promotion-journal cleanup and incomplete promotion refusal, unselected feedback preservation, and a second revision based on the first promoted successor.

The recovered Integration current-question case is the representative structural replay: a valid typed response requiring a Domain entity plus downstream ownership and plan references reaches one proposal and approval decision, or a specific authority/gate refusal. Invalid operation syntax creates neither a candidate nor a canonical write.

## Acceptance criteria

- Ordinary feedback needs no user-selected type; validated typed operations deterministically select the bounded or structural route.
- The structural route presents exactly one approve/edit/reject decision over a complete, gate-valid, inert proposal identifying all affected artifacts, rows, consequences, and non-goals.
- Approval can promote only the exact reviewed candidate after currentness rechecks; edit and reject end the prior candidate's eligibility for structural approval.
- The displayed initial structural candidate can be approved directly; edit alone creates an unapproved replacement for a fresh decision, with no extra user question or answer.
- Each feedback revision has one explicit accepted predecessor, preserves its immutable successor history, and makes the next revision derive from the newly promoted head.
- Existing candidate/version, review binding/replacement/seal, promotion, publication/recovery, feedback-state, and seed-invalidation owners are reused rather than duplicated.
- Presentation-only feedback retains its current candidate authority and behavior without the structural approval gate.
- Same-artifact and cross-artifact proposals consume proposed upstream bytes and pass existing full-roadmap gates before approval and again where required before promotion.
- A completed structural promotion with accepted-head, active-pointer, and seed-state effects is recoverable as one publication; incomplete or changed members remain refused.
- Invalid, stale, rejected, interrupted, or failed proposals cannot advance the accepted head, rewrite canonical artifacts or seeds, or promote a candidate; selected ledger items and immutable candidate/review history follow the existing lifecycle.
- Unselected feedback remains byte-for-byte unchanged on every route.
- A valid typed Integration current-question replay reaches the structural approval path or a specific authority/gate refusal.

## Deferred

Read-only feedback-breakdown advice, automatic subset generation, richer parser/protocol failure receipts, and structural operations outside current roadmap stage authority remain separate backlog work. None is a prerequisite for the approval gate.
