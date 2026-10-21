> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-candidate-same-batch-relations.md`.
> Preserved here for history; do not edit.

# Same-batch candidate relation authority

Source: `BUG_BACKLOG.md` — “Candidate relation authority rejects endpoints added by the same admitted batch.”

## Overview

Permit one admitted multi-feedback roadmap candidate to declare relations to rows that the same candidate validly adds, while preserving exact per-operation feedback traceability and fail-closed candidate publication.

## Problem statement

`materialize_candidate` currently requires every changed declared-relation endpoint to exist in the predecessor. A coherent batch therefore cannot add a Domain business rule and update a Constraints row to anchor to it. The added-owner anchor check independently retains the same predecessor-only assumption, so a partial membership fix cannot support added-owner to added-endpoint relations.

## Architecture

Keep candidate authority at the typed-operation boundary. Each changed relation remains attributable to the operation that owns its relation-bearing row. A new endpoint is permitted only when a distinct valid `add-row` operation in the same normalized candidate creates its exact artifact/row identity. The owner operation and endpoint-addition operation retain their independent admitted `feedback_id` bindings; they may refer to different reviewer items. No separate relation-feedback item is needed.

The relation validator must distinguish predecessor endpoints from same-candidate additions. A predecessor endpoint continues to require exact full-content capsule membership. A same-candidate endpoint must be an exact operation-created identity that survives operation preparation, typed-row validation, collision checks, feedback binding, application, render/reparse, and complete-roadmap gates. An added row is not a general context anchor: the exception authorizes only the exact declared relation whose endpoint addition is present in that candidate.

Update both relation-authority paths together: predecessor membership and the added-owner reached-anchor rule. Preserve operation-order independence through normalized operations and do not change candidate classification, review/promotion semantics, canonical artifact writing, feedback lifecycle effects, or seed effects.

## Scope of work

1. Define one internal exact added-operation identity lookup and apply it to every changed declared-relation endpoint and added-owner anchor decision.
2. Retire the predecessor-only new-sibling prohibition and add focused materialization coverage for both allowed same-candidate shapes and every preserved refusal boundary.
3. Add a candidate-run regression for the Integration manual-session-recovery batch, proving it reaches the inert structural approval surface and does not publish canonical state.
4. Remove the source BUG_BACKLOG entry when the implementation and its regressions ship.

## Out of scope

- Broadening a feedback item into authority for unrelated operations or endpoints.
- Inventing, synthesizing, or automatically adding endpoints.
- A separate relation-feedback protocol or a generic same-candidate context expansion mechanism.
- Changing roadmap gates, candidate review/promotion behavior, accepted-head selection, or seed lifecycle.

## Risks

- A membership-only implementation leaves the added-owner reached-anchor guard rejecting valid new-to-new relations. Test both guards through materialization, not only their helpers.
- A row-id-only lookup could accept an endpoint from the wrong artifact or typed collection. Bind exact artifact, row type, and row id to the `add-row` operation.
- Allowing an added endpoint to act as a generic context anchor could authorize unrelated additions. Test that authorization is relation-local and retain failure for endpoints without a valid admitted addition.

## Testing

- Materialize a gate-clean candidate with `fb-domain-session-recovery` adding `rule-manual-session-recovery` and `fb-constraints-session-recovery` replacing `constraint-no-auto-restart` to name it in `anchor_ids`.
- Cover existing-owner to added-endpoint and added-owner to added-endpoint relations in both input operation orders.
- Preserve refusals for missing endpoints, an endpoint without a valid admitted `add-row`, ID collisions, wrong typed rows, and predecessor endpoints absent from full membership.
- Exercise the candidate-run route and assert structural review/approval readiness without canonical artifact, accepted-head, feedback-state, or seed publication.

## Acceptance criteria

- A coherent admitted batch can form an inert, gate-clean structural candidate using relations between its valid added rows, including across artifacts and across different feedback ids.
- Every allowed new endpoint is traceable to one exact valid same-candidate `add-row` operation and its admitted feedback binding.
- Existing predecessor endpoint authority and every unrelated or malformed endpoint refusal remain fail-closed.
- The former backlog entry is removed only after focused tests and the relevant suite are green.

## References

- `BUG_BACKLOG.md` — source bug, Integration evidence, settled traceability decision, and scope fence.
- `plan_tool/roadmap_candidate.py:_validate_operation_authority` and `_validate_relation_authority` — typed-operation admission and both relation guards.
- `tests/test_roadmap_candidate.py:test_candidate_new_siblings_cannot_authorize_each_other` — predecessor-only regression that the new exact-linkage tests replace.
- `docs/implementation-plans/2-roadmap-structural-feedback-approval.md` — structural candidate classification and approval lifecycle that remain unchanged.

## Deferred

- General relation-authority redesigns and independent relation-feedback items remain out of scope.
