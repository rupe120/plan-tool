> **Replaced**: this file has been superseded by `docs/implementation-plans/2-root-enrollment-rollback.md`.
> Preserved here for history; do not edit.

# Seed: root-enrollment rollback

Source: `BUG_BACKLOG.md` — "Root enrollment can strand post-enrollment
feedback before any candidate exists." The resulting plan updates that source
entry only after the complete rollback route ships.

## Outcome

An operator who enrolled a roadmap as an immutable root before recording
review feedback has one explicit, operator-confirmed command that clears the
root's active `accepted-head` selection and returns the roadmap to a
feedback-driven revision state, without deleting the immutable root content
and without ever asking the operator to delete a file by hand.

## In scope

- One new CLI-reachable rollback route for `plan_tool/roadmap.py`, gated to
  fire only when the accepted head names a `root` version with no accepted
  descendant version, no stored `candidate-proposal` admission
  (`roadmap_candidate_run.py:load_candidate_admission`), no candidate review
  or promotion seal record, no pending lifecycle generation
  (`roadmap_source_identity.py:load_pending_generation`), and no tracked
  roadmap seed state (`roadmap_seed_state.py`).
- Validation of the accepted root's stored inventory and brief digest against
  its `StoredRoadmapVersion` record before any mutation
  (`roadmap_versions.py`), so rollback never fires against a corrupt or
  partially-written root.
- A durable rollback receipt recording which root was un-selected, when, and
  under what confirmed operator intent. Check whether the existing
  git-committed receipt mechanism in `roadmap_escalation.py`
  (`build_receipt`/`render_receipt`/`receipt_worktree_for_plans_dir`) already
  fits before adding a second receipt implementation.
- Atomic removal of only the `accepted-head.json` selector
  (`roadmap_versions.py:accepted_head_path`) under the existing roadmap
  writer lock (`_roadmap_writer_owner`), leaving the stored root version
  directory, its record, and its artifact/brief members untouched.
- Idempotent behavior: running the route again after a successful rollback
  (accepted head already absent) reports the already-rolled-back state rather
  than erroring or re-writing a receipt.
- Focused lifecycle tests proving the exact allow/refuse boundary and the
  before/after immutable-storage state.

## Overview

`enroll_roadmap_root` captures a roadmap's four staged artifacts into
immutable version storage and points `accepted-head.json` at that root. Once
enrolled, `require_unenrolled_roadmap_writer` refuses every legacy stage
writer, and `--propose-candidate` builds its feedback view strictly from the
frozen bytes captured at enrollment (`roadmap_candidate_context.py:
_verify_predecessor` parses `predecessor.artifact_bytes`, not the live
working artifacts). Feedback recorded in the working artifacts after
enrollment is therefore invisible to both the legacy writer and candidate
proposal, and today no supported command reopens the lineage.

## Problem statement

An operator who enrolls a clean root and only then records valid feedback has
no way back to a feedback-driven revision state. The legacy writer refuses
because the roadmap reads as enrolled; candidate proposal refuses because it
resolves feedback against the accepted root's frozen snapshot, which predates
the feedback; and no command exists to bind that feedback to the root or
unwind the selection. The root itself is not wrong — it is a valid, unpromoted
version with no candidate, review seal, or materialized seed depending on
it — so the correct remedy is reopening the *selection*, not repairing or
discarding the root.

## Architecture

Rollback is a state transition on the accepted-head selector alone, not a
mutation of immutable version storage. It runs under the same writer lock
every other lifecycle writer uses, and it composes with the existing recovery
boundary: reuse `recover_roadmap_publication`'s pending-generation check
rather than adding a second one, so a route never fires while a lifecycle
journal is mid-write. The eligibility check is a closed predicate over five
conditions (root-only accepted head, no accepted descendant, no candidate
admission, no review/seal record, no pending generation, no tracked seed
state) evaluated before any write; any one violated condition is a refusal,
not a partial rollback. The operator confirmation is a required, explicit
argument on the CLI surface, not a default-yes flag — this is a state
transition on an immutable lineage, not a convenience toggle.

## Out of scope

- Rolling back an enrolled root that already has a candidate, review, seal,
  or promoted descendant. That state has no rollback target and is unrelated
  to this route.
- The separate incomplete-journal recovery bug (interrupted candidate
  proposal, review, replacement, or promotion) — that route resumes a
  mid-write journal; this route reopens the selection of a *complete,
  valid* root after the fact. Keep the two mechanisms and their tests
  separate.
- Deleting or rewriting immutable version storage content. The stored root
  version, its record, and its artifact/brief members are never modified or
  removed by this route.
- A general-purpose accepted-head repair, journal-inspection, or operator
  repair framework.
- Binding post-enrollment feedback into the root's stored content. Rollback
  only reopens the selection so the existing legacy writer can record that
  feedback the normal way; it does not itself materialize or migrate
  feedback.

## Risks

- An eligibility check that is too permissive could clear a selection that a
  candidate, review, or seed already depends on, silently orphaning that
  dependent state. Every one of the five eligibility conditions needs its own
  mutation test (violate one condition at a time, prove refusal, prove no
  write).
- An eligibility check that reads live working-artifact state instead of the
  stored root's own record could refuse or allow based on drift unrelated to
  enrollment. Validate against the stored `StoredRoadmapVersion` and its
  digests, not the working tree.
- Running rollback concurrently with another lifecycle writer for the same
  slug must not race; both must serialize through the existing writer lock.

## Allowed behavior changes

- A roadmap whose accepted head names a root version with no descendant,
  admission, review, seal, pending generation, or tracked seed state can have
  that selection cleared by an explicit, operator-confirmed command, after
  which the legacy stage writer resumes normally.
- Every other enrolled state (a descendant, admission, review, seal, pending
  generation, or tracked seed present) continues to refuse rollback exactly
  as it refuses every other unsupported lifecycle transition today.

## Allowed reorganization

None beyond exposing what the eligibility predicate needs from
`roadmap_versions.py`, `roadmap_candidate_run.py`, `roadmap_seed_state.py`,
and `roadmap_source_identity.py` as read-only calls; no changes to their
existing write paths.

## Testing

- Add focused tests alongside the existing immutable-lifecycle/recovery
  suites (`tests/test_roadmap_versions.py`, `tests/test_roadmap.py`, and
  wherever the new route's module lands).
- Prove the eligibility boundary by mutation: for each of the five
  conditions, construct a fixture that violates only that one condition and
  assert refusal with the accepted-head selector and stored root untouched.
- Prove the happy path: enroll a root, record feedback in the working
  artifacts with no candidate ever admitted, roll back, then run the existing
  legacy stage writer and `--propose-candidate` flow through to a normal
  admitted proposal.
- Prove idempotence: roll back twice and assert the second call reports the
  already-rolled-back state without a second receipt write or error.
- Run the complete test suite and review every root-enrollment and
  candidate-proposal call site for a rollback bypass.

## Acceptance criteria

- A root enrolled with no candidate, review, seal, pending generation, or
  tracked seed can be rolled back by one explicit, operator-confirmed
  command, after which the legacy stage writer and `--propose-candidate`
  both operate normally against the (now unenrolled) working artifacts.
- Any accepted descendant, candidate admission, review/seal record, pending
  generation, or tracked seed state blocks rollback with a clear refusal and
  no mutation.
- The stored root version, its record, and its artifact/brief members are
  byte-identical before and after a rollback.
- Rollback is idempotent and never instructs the operator to delete a file by
  hand.
- `BUG_BACKLOG.md` no longer lists this bug after focused tests and the
  complete suite pass.

## Deferred

If an eligible-but-ambiguous state turns up (for example a candidate
admission that was itself rolled back or abandoned), leave it refused and
record the separate requirement in `BUG_BACKLOG.md` or `BACKLOG.md` rather
than widening this route's eligibility predicate.

## References

- `BUG_BACKLOG.md` — source bug, its exact symptom trace, and its fail-closed
  requirement.
- `BACKLOG.md` #328 (closed) — the immutable accepted-head lifecycle contract
  this route reopens; #329/#330 are separate pending-generation and admission
  hardening, not this route.
- `plan_tool/roadmap.py:enroll_roadmap_root`,
  `_roadmap_writer_owner` — enrollment and the writer lock rollback reuses.
- `plan_tool/roadmap_versions.py:load_accepted_version`,
  `is_roadmap_enrolled`, `accepted_head_path` — the selector this route
  clears.
- `plan_tool/roadmap_revision_publish.py:require_unenrolled_roadmap_writer` —
  the legacy-writer refusal that flips once rollback clears the selector.
- `plan_tool/roadmap_candidate_context.py:_verify_predecessor` — why
  candidate proposal cannot see post-enrollment feedback today.
- `plan_tool/roadmap_candidate_run.py:load_candidate_admission`,
  `plan_tool/roadmap_source_identity.py:load_pending_generation`,
  `plan_tool/roadmap_seed_state.py` — the three other eligibility checks.
- `plan_tool/roadmap_escalation.py` — existing durable-receipt mechanism to
  evaluate for reuse before adding a second one.
