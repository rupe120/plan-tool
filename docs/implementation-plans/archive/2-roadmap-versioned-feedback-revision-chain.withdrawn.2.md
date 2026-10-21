> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Versioned Feedback Revision Chain
intent: One ordinary roadmap feedback run processes the accepted head's complete active
  feedback set into one immutable successor revision. The successor preserves the
  whole feedback channel, including every existing `awaiting-review` response, and
  becomes canonical only through exact review-seal promotion. Each later run starts
  from the promoted successor rather than from live top-level artifacts.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-versioned-feedback-revision-chain.md
steps:
- id: 1
  title: Build one ordered accepted-head feedback batch and exact batch identity
  intent: Each revision starts from the accepted version and binds every currently
    open feedback row without relying on live artifacts.
  files:
  - plan_tool/roadmap_candidate_context.py
  - tests/test_roadmap_candidate_context.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/01-build-one-ordered-accepted-head.md
  status: current
- id: 2
  title: Build one complete successor for the batch while preserving existing typed
    row removals and untouched feedback
  intent: Every admitted open request can contribute to one successor while awaiting-review
    and deferred rows remain unchanged.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the ordered feedback inventory and exact batch binding used to authorize
      and verify the successor.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/02-build-one-complete-successor-batch.md
- id: 3
  title: Narrow candidate-admission replacement to one accepted-head generation and
    store one inert batch successor
  intent: Retries re-enter one exact batch, while promotion leaves later accepted
    heads free to start a new feedback generation.
  files:
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the reproducible batch identity and context payload.
    2: Provides batch-aware successor materialization and full-roadmap validation.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/03-narrow-candidate-admission-replacement.md
- id: 4
  title: Block enrolled decision settlement only on an unpromoted candidate for the
    current accepted-head generation
  intent: An old promoted generation no longer strands decision settlement, while
    a live candidate on the current head still blocks competing publication.
  files:
  - plan_tool/roadmap_decision_settlement_enrolled.py
  - tests/test_roadmap_decision_settlement_enrolled.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Defines how the current accepted-head generation owns and exposes its candidate
      admission.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/04-block-enrolled-decision-settlement-only.md
- id: 5
  title: Bind review questions and answers to the exact batch while preserving journaled
    review-state replacements
  intent: Reviewer questions, answers, replacement candidates, and seals cannot drift
    to a different feedback inventory or predecessor.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/prompts/roadmap-candidate-questions.md
  - tests/test_roadmap_candidate_review.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Provides the batch-bound candidate and successor evidence reviewed by this
      lifecycle.
    3: Provides the generation-scoped admitted initial candidate that review must
      resolve.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/05-bind-review-questions-answers-exact.md
- id: 6
  title: Preserve exact-seal accepted-head replacement and reject stale or changed
    batches before promotion
  intent: Only the reviewed successor for the current predecessor becomes canonical,
    and every failed promotion leaves the prior head unchanged.
  files:
  - plan_tool/roadmap_version_promotion.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 5
  depends_on_notes:
    3: Provides generation-scoped admission and stored batch evidence.
    5: Provides the exact batch-bound replacement candidate and review seal.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/06-preserve-exact-seal-accepted-head.md
- id: 7
  title: Route selector-free --revise-feedback and --propose-candidate to the batch
    lifecycle and retire legacy live-artifact replacements
  intent: Ordinary feedback uses one immutable accepted-head workflow and can no longer
    overwrite live artifacts, baselines, or seed state.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 5
  - 6
  depends_on_notes:
    3: Provides the selector-free batch proposal entry point and its terminal outcomes.
    5: Provides the existing review action reported after candidate storage.
    6: Completes the exact promotion path exercised by the CLI history test.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/07-route-selector-free-revise-feedback.md
- id: 8
  title: Document the batch-to-successor workflow and reconcile obsolete selector
    and live-writer records
  intent: Operators and future changes see one consistent model for enrollment, batch
    admission, review, promotion, failure preservation, and later revisions.
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - README.md
  - CAPABILITIES.md
  - RUNBOOK.md
  - TESTING.md
  - docs/ARCHITECTURE.md
  - docs/cli/roadmap.md
  - docs/how-to/common-workflows.md
  - docs/how-to/roadmap.md
  - docs/reference/commands.md
  - BACKLOG.md
  - BUG_BACKLOG.md
  - tests/test_roadmap_format.py
  - tests/cli/test_cli_reference.py
  complexity: high
  change_type: non-code
  depends_on:
  - 4
  - 7
  depends_on_notes:
    4: Provides the landed rule for sibling accepted-head writers while a batch generation
      is active.
    7: Provides the final command syntax, output, refusal, and end-to-end lifecycle
      behavior.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/08-document-batch-successor-workflow.md
---
# Roadmap Versioned Feedback Revision Chain

## Overview

Replace selector-driven, once-per-roadmap candidate admission with one
accepted-head-scoped feedback batch. `--revise-feedback` does not require an
`ARTIFACT:FEEDBACK_ID`: it derives the complete eligible batch from the current
accepted version, invokes the roadmap feedback machinery once for that batch,
and stores the result as an inert candidate. Existing `awaiting-review` and
`deferred` rows remain byte-for-value unchanged; active `open` rows may move to
`awaiting-review` with proposed responses under the existing feedback-integrity
rules. Review binds the exact candidate bytes, and promotion advances the
accepted head only after the existing lineage and predecessor checks pass.

## Problem statement

The immutable candidate lifecycle currently admits one fixed feedback selector
for the lifetime of an enrolled roadmap. That admission supports retries for
one row but permanently refuses a different row, even after the first candidate
is promoted. It therefore cannot represent ordinary roadmap revision history,
where one accepted revision may answer several open requests and later accepted
revisions must process newly opened or reopened requests.

The selector also makes the command's unit of work smaller than the feedback
channel's existing semantics. Roadmap feedback already distinguishes active
`open` guidance from reviewer-owned `awaiting-review` and `deferred` rows. A
revision should derive its work from that complete state rather than require an
operator to nominate one row while other eligible requests remain beside it.

## Architecture

Keep explicit enrollment as the only way to establish the root accepted
version. `plan_tool/roadmap.py:enroll_roadmap_root()` owns root enrollment, and
`plan_tool/roadmap_versions.py` remains the owner of immutable version records
and `AcceptedRoadmapHead`; no feedback command silently enrolls a roadmap.

For an enrolled roadmap, feedback revision resolves the current accepted
version and deterministically derives one batch from its complete feedback
inventory. Every `open` row in the admitted envelope is active guidance.
Existing `awaiting-review` rows, including their nonblank `proposed_response`,
and existing `deferred` rows are carried unchanged. The batch identity binds
the accepted predecessor and the exact eligible feedback inventory so a retry
can re-enter the same lineage while drift or accepted-head movement refuses or
requires a fresh candidate.

Adapt the existing candidate admission and proposal owners to be scoped to one
accepted-head generation rather than one feedback selector for the roadmap's
whole life. Candidate construction continues to use the established roadmap
gates and stores one complete inert successor. Promotion of the exact reviewed
candidate ends that generation; a later run derives a fresh batch from the new
accepted head. This is a change to the existing candidate lifecycle, not a
second candidate store, version chain, or accepted-head authority.

`plan_tool/roadmap_candidate_review.py` continues to own reviewer questions,
answers, replacement candidates, and exact review seals.
`plan_tool/roadmap_version_promotion.py:promote_review_seal()` remains the only
feedback-candidate writer that advances `AcceptedRoadmapHead`; enrolled
decision settlement remains the other existing, untouched accepted-head
writer. `plan_tool/roadmap_revision_publish.py` remains the publication journal
and recovery boundary used by version-owned writers.

For an unenrolled roadmap, feedback revision reads only enough state to refuse
with the explicit `--enroll-version` next action. It makes no backend call and
writes no roadmap, baseline, seed, candidate, admission, or version state.
Enrollment remains a separate operator decision.

Retire the legacy local feedback writer from ordinary routing rather than
adapting it to mutate enrolled state. Live top-level roadmap files are not the
canonical predecessor or a pending mutable candidate for an enrolled roadmap.

## Input

The implementation consumes the current feedback lifecycle in
`ROADMAP_FORMAT.md`, the immutable version contracts in
`plan_tool/roadmap_versions.py`, and the existing candidate, review, promotion,
and recovery owners. It replaces the selected-feedback and roadmap-fixed
admission semantics currently exposed by `--revise-feedback` and
`run_initial_candidate_proposal()` with deterministic batch admission rooted in
the accepted head. It does not redefine the allowed state transition or typed
changes for an individual feedback row.

## Scope guardrails

`AcceptedRoadmapHead` is the sole selector of canonical content for an enrolled
roadmap. Candidate storage, batch admission, model output, review questions,
reviewer answers, replacement candidates, and review seals do not make a
candidate canonical. Feedback-candidate promotion changes the selector only
after exact-seal and current-predecessor verification and does not rewrite live
top-level roadmap artifacts.

Every candidate has one explicit accepted predecessor and one exact feedback
batch identity. A stale predecessor, changed eligible set, changed feedback
source, or changed response binding refuses before accepted-head movement. An
unpromoted, rejected, interrupted, or failed candidate does not consume
feedback or alter the accepted version. Promotion does not invent a new
feedback state: rows remain `awaiting-review` until the reviewer closes,
defers, or reopens them through the existing lifecycle.

No command silently enrolls or promotes a roadmap. The implementation reuses
the existing version, candidate, review, promotion, journal, checkpoint, and
recovery owners and introduces no parallel authority for any of them.

## References

- [`ROADMAP_FORMAT.md`](../ROADMAP_FORMAT.md) — Feedback lifecycle, immutable
  version, candidate, and accepted-head contracts.
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md) — Persisted version, candidate,
  review, and publication data contracts.
- [`docs/how-to/roadmap.md`](../docs/how-to/roadmap.md) — Operator workflow for
  enrollment, feedback, candidate review, and promotion.
- [`plan_tool/roadmap.py`](../plan_tool/roadmap.py) — Explicit immutable-root
  enrollment.
- [`plan_tool/roadmap_versions.py`](../plan_tool/roadmap_versions.py) —
  Immutable roadmap versions and `AcceptedRoadmapHead`.
- [`plan_tool/roadmap_candidate_context.py`](../plan_tool/roadmap_candidate_context.py)
  — Candidate context and current selected-feedback binding.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py)
  — Current roadmap-fixed admission, candidate construction, gates, and inert
  storage.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py)
  — Reviewer question, answer, replacement, and exact review-seal lifecycle.
- [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py)
  — Sealed feedback-candidate promotion path.
- [`plan_tool/roadmap_revision_run.py`](../plan_tool/roadmap_revision_run.py) —
  Legacy local feedback runner to retire from ordinary routing.
- [`plan_tool/roadmap_revision_publish.py`](../plan_tool/roadmap_revision_publish.py)
  — Shared publication journal and recovery boundary.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Creating, editing, classifying, accepting, deferring, reopening, or deleting
  reviewer feedback outside the existing feedback lifecycle.
- A new consumed, processed, or approved feedback state.
- Structural-versus-bounded operation classification or any structural
  feedback proposal format.
- A new approve/edit/reject gate or other user-review protocol.
- A second immutable-version schema, candidate store, accepted-head writer,
  review-seal format, checkpoint system, recovery system, or transaction
  framework.
- Multiple simultaneous candidate branches from one accepted head.
- Multi-artifact structural authoring, automatic feedback grouping or
  splitting, and scope-narrowing advice.
- Changes to stage operation authority, roadmap gates, or individual candidate
  operation semantics beyond accepting a complete feedback batch.
- Automatic enrollment or promotion.

## Risks

A batch can silently omit an eligible request, mutate an existing response, or
change membership between review and promotion. A generation reset can admit a
new batch before the previous candidate is promoted or rejected, while a
roadmap-lifetime admission can strand every later update. Reading live files
instead of the accepted version can fork history. Retiring the selector in one
dispatcher while leaving it in help, retry, review, or documentation paths can
preserve two incompatible workflows. The implementation must define batch
ordering and identity once, prove the full consumer set, and fail closed on
predecessor or membership drift.

## Testing

Prove the complete linear history property across both enrollment states and
multiple feedback states. An unenrolled feedback run makes no backend call or
write and identifies explicit enrollment. An enrolled run admits every eligible
`open` row in deterministic artifact-and-row order, carries pre-existing
`awaiting-review` responses and `deferred` rows unchanged, and stores one inert
candidate without changing the accepted head or live artifacts. A zero-eligible
run is a non-writing no-op.

Prove retry of the same accepted-head batch re-enters the same lineage; batch
membership, feedback-source, and predecessor drift refuse without accepted-head
movement. Existing review and exact-seal promotion advance the head to the
reviewed candidate. Failure, rejection, interruption, stale predecessor, gate
failure, review failure, promotion failure, and recovery preserve the prior
accepted head. After promotion, newly added, reopened, or otherwise newly
eligible feedback forms a fresh batch whose predecessor is the promoted
successor, while the earlier `awaiting-review` rows remain unchanged.

At bare-plan stage, retain these eligibility, preservation, ordering,
authority, and non-mutation properties without selecting new storage mechanics.
At detail-grounded stage, enumerate every feedback selector parser,
`--revise-feedback` and `--propose-candidate` dispatcher, candidate admission
reader/writer, help path, lifecycle writer, documentation consumer, and
regression surface so the roadmap-fixed selector contract cannot remain
reachable accidentally.

## Acceptance criteria

- Ordinary roadmap feedback follows one immutable accepted-head revision model
  after explicit enrollment.
- Ordinary revision requires no operator-supplied feedback selector and derives
  one deterministic batch from the accepted head.
- Every eligible `open` row is admitted once into that batch; pre-existing
  `awaiting-review` and `deferred` rows remain unchanged in the successor.
- The batch binds the exact accepted predecessor, feedback inventory, and
  source identities used to construct the candidate.
- Candidate creation remains inert and never moves the accepted head or
  rewrites live top-level roadmap artifacts.
- Exact review-seal promotion remains the only feedback-candidate accepted-head
  writer and retains all lineage and current-predecessor checks.
- A failed or unpromoted generation consumes no feedback and changes no
  canonical state.
- Promotion permits a later batch to derive from the promoted successor without
  retaining a roadmap-lifetime selector lock.
- No eligible feedback produces a deterministic no-work result without a model
  call or state publication.
- No parallel version, candidate, review, promotion, journal, checkpoint, or
  recovery subsystem is introduced.
- CLI documentation and contract checks describe the same batch-to-successor
  workflow.

## Deferred

Structural feedback classification, structural proposal construction, and the
structural approve/edit/reject gate remain outside this plan. They may consume
the completed batch revision-history contract but do not change its outcome or
scope.
