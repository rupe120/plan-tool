# Seed: immutable lifecycle journal recovery

Source: `BUG_BACKLOG.md` — "Incomplete immutable lifecycle journals can
permanently block a resumed proposal, review, or promotion." The resulting
plan updates that source entry only after the complete recovery contract ships.

## Outcome

Every incomplete journal shape that the immutable roadmap lifecycle writers
produce recovers to a retryable state when all members are wholly old, wholly
new, or a recorded valid mixed state. A forged, unknown, or incompletely
specified journal remains untouched and refuses the lifecycle operation.

## In scope

- Define the exact recovery predicates for writer-produced `candidate-proposal`,
  `candidate-review-record`, `candidate-review-replacement`, and
  `review-seal-promotion` generations, including their immutable bindings and
  promotion seal/accepted-head selector state.
- Extend `recover_roadmap_publication` only with those exact predicates and
  route candidate proposal, candidate review, and promotion through the
  appropriate enrolled recovery entry before retrying a lifecycle write.
- Add focused recovery fixtures for wholly old, wholly new, valid recorded
  mixed, and rejected forged/unknown/partial states for each writer shape.
- Remove the source BUG entry only after its focused tests and the complete
  suite verify the shipped behavior.

## Overview

The immutable roadmap lifecycle records a pending generation before replacing
its members, which makes interrupted writes detectable instead of silently
partial. Its recovery path currently recognizes only some writer shapes, so an
interrupted candidate proposal, candidate review record/replacement, or
review-seal promotion can block every later write for that slug even when its
on-disk members prove one safe recovery outcome.

## Problem statement

`recover_roadmap_publication` is the recovery boundary for a pending roadmap
generation, but candidate writers do not consistently enter it before retrying.
The recovery recognizer also cannot classify all of the immutable member sets
their writers create. A retry then refuses on the same journal indefinitely,
although the writer recorded enough exact identity and digest information to
recognize a safe old, new, or known mixed state without guessing.

## Architecture

The recovery contract remains writer-shaped and fail-closed. Each enrolled
lifecycle entry first recognizes only its own generation kind and complete
member inventory, validates the immutable candidate/review/seal bindings that
writer recorded, and classifies disk state as wholly old, wholly new, or an
explicitly allowed mixed state. Recovery performs only the deterministic
member/selector action its writer already owns. Any absent, extra, malformed,
or unrecognized member remains a refusal with no mutation.

## Out of scope

- A generic journal ownership, repair, inspection, or operator-repair
  framework.
- Recovery of legacy, unrecorded, malformed, or forged member sets; those
  states continue to fail closed without mutation.
- Changing roadmap admission, candidate semantics, accepted-head authority,
  direct-reader migration, model invocation, or raw-response retention.
- Root-enrollment recovery, the separately deferred #329 hardening, and any
  lifecycle writer migration beyond the four named writer-produced shapes.

## Risks

- A recognizer that treats a partial or forged member set as a writer-produced
  state could make an immutable lifecycle ambiguous; every accepted shape must
  be exact and mutation tests must reject one-member deviations.
- Candidate retry paths can bypass recovery or recover a different writer kind;
  tests must pin recovery before any later lifecycle write or model call.
- Promotion changes only the accepted-head selector; recovery must never
  rewrite a candidate or review record while restoring that selector state.

## Allowed behavior changes

- A retry of an enrolled candidate proposal, candidate review, replacement, or
  promotion can clear only its exact interrupted writer journal and resume from
  the deterministic lifecycle state it records.
- An unsupported pending generation continues to refuse before a lifecycle
  writer changes any member.

## Allowed reorganization

None beyond narrow shared recovery validation that prevents the named lifecycle
entry points from duplicating one exact generation predicate.

## Testing

- Run focused recovery and lifecycle tests in `tests/test_roadmap_revision_publish.py`,
  `tests/test_roadmap_candidate_run.py`, `tests/test_roadmap_candidate_review.py`,
  and `tests/test_roadmap_version_promotion.py`.
- Prove each accepted recovery state by mutation: omit, replace, or corrupt one
  member and verify the retry refuses without changing the journal or canonical
  selector.
- Run the complete test suite and review every named lifecycle entry for a
  bypass around recovery.

## Acceptance criteria

- Every named writer-produced pending generation has a recovery result for its
  complete, validated old/new/mixed state, and a resumed lifecycle operation
  reaches its normal retryable state.
- A missing, changed, extra, or unrecorded member refuses without changing the
  generation or accepted-head selector.
- Candidate proposal, review, replacement, and promotion all reach their
  recovery boundary before performing a lifecycle write.
- `BUG_BACKLOG.md` no longer lists this bug after focused recovery tests and
  the complete suite pass.

## Deferred

If a recovery case needs semantic reconstruction, a previously unrecorded
generation member, cross-kind recovery, or operator judgment, leave its journal
untouched and record the separate requirement in `BUG_BACKLOG.md` or
`BACKLOG.md` rather than broadening this effort.

## References

- `BUG_BACKLOG.md` — source bug and its fail-closed boundary.
- `BACKLOG.md` #328 — closed immutable accepted-head lifecycle contract the
  recovery predicates consume; #329 remains separate root-enrollment hardening.
- `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication` — current
  generation recovery entry.
- `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal`,
  `plan_tool/roadmap_candidate_review.py`, and
  `plan_tool/roadmap_version_promotion.py:promote_review_seal` — lifecycle
  writers and retries that require the same fail-closed recovery boundary.
