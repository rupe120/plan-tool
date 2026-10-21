> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-candidate-policy-review.md`.
> Preserved here for history; do not edit.

# Seed: carry candidate policy review through the existing feedback lifecycle

## Outcome

A structurally valid roadmap candidate whose exact, bounded materializer policy
impact needs human judgment reaches the existing candidate review instead of a
terminal refusal. The selected feedback row remains the sole user request, the
existing question and answer remain the sole review exchange, and explicit
review-seal promotion remains the sole approval that can change the accepted
roadmap.

## In scope

- The candidate materializer's distinction between hard refusal, review-required
  inert candidate, and ordinary gate-clean candidate.
- Immutable evidence binding a review-required impact to the selected feedback,
  predecessor, capsule, normalized delta, complete candidate diff, affected
  rows, and impact identity.
- The existing initial-candidate, question-inventory, exact-answer,
  answer-bound-replacement, seal, and promotion lifecycle.
- One initial review-requirement reason for an otherwise valid declared-relation
  impact. The record shape remains usable by another explicitly added
  materializer-policy reason without creating another user workflow.
- Deterministic tests and live contract documentation, including retirement of
  `BACKLOG.md` #354 and reconciliation of both roadmap backlog arcs when the
  work ships.

## Overview

This seed implements `BACKLOG.md` #354. It extends the immutable candidate route
delivered by #328 at the point where deterministic materialization has enough
information to prove the proposed change is structurally bounded but not enough
authority to decide whether its relationship effect matches the user's intent.
That remaining judgment belongs in the review the route already requires.

The first consumer is the Integration `project-workspace-membership-proof` feedback:
removing persisted project selection also changes declared membership-scope
relations on surviving, capsule-authorized rows. The scenario establishes the
need for the capability; it does not define a Integration-specific state, relation
exception, feedback kind, or command.

## Problem statement

At HEAD, `plan_tool/roadmap_candidate.py:CandidateMaterializationResult` exposes
only a `GateCleanCandidate` or `CandidateRefusal`.
`plan_tool/roadmap_candidate.py:_validate_operation_authority` refuses any
replacement of an existing row that changes its declared relations, and
`plan_tool/roadmap_candidate.py:_validate_relation_authority` permits relation
removal only when the relation-owning row is removed. Those checks correctly
prevent an undisclosed relationship rewrite, but they classify an exact,
fully grounded change and an unauthorized one through the same terminal
`relation-authority` result.

`plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` stores an
initial candidate only after materialization returns gate-clean, while
`plan_tool/roadmap_candidate_review.py:generate_candidate_question` can begin
only from that stored candidate. The user therefore cannot reach the existing
review surface to judge the materializer's exact concern.

`plan_tool/roadmap_candidate_review.py:request_replacement` invokes the same
materializer after binding the question and opaque answer, but that review
binding currently grants no narrow authority to retain a disclosed policy
impact. Weakening relation validation globally would remove the safety property;
adding a separate confirmation route would divide one feedback conversation
across two user mechanisms.

## Architecture

The materializer owns one ordered disposition contract:

| Disposition | Definition and producer | Precedence | Consumer and exit |
| --- | --- | --- | --- |
| Hard refusal | The materializer finds malformed input, missing capsule authority, an invalid or dangling relation, a failed render or roadmap gate, an out-of-lineage change, or any policy impact that cannot be exactly bounded. | Wins over every review-required condition. | The proposal or replacement keeps its existing fail-closed result and publishes no candidate. The operator corrects the request or implementation before re-entry. |
| Review required | Every ordinary structural and roadmap check passes, but one typed materializer policy identifies an exact impact that requires human judgment. | Available only when no hard refusal exists. | The tool stores an inert initial candidate with immutable review-requirement evidence and routes it through the existing candidate review. |
| Gate clean | Every materializer policy and roadmap gate passes without a review requirement. | Reached only when neither earlier disposition applies. | The current inert-candidate review path continues unchanged. |

The review-requirement evidence is deterministic and content-addressed. It is
not a new feedback row and contains no inferred answer. The existing question
inventory binds the requirement and surfaces its complete affected facts in
the same review contact. The question may ask whether the impact reflects the
reviewer's intent, but the exact answer stays opaque guidance: the tool does not
parse `yes`, `no`, sentiment, or semantic agreement.

An answer-bound replacement is eligible to seal only when it eliminates the
review-required impact or retains no more than the exact disclosed impact. The
replacement comparison is mechanical: it binds the same predecessor and
selected feedback, recomputes the complete diff, and rejects a changed impact
identity, new affected row, wider relation set, or new policy requirement. The
review binding grants no new row, capsule, artifact, or standalone-relation
authority.

Explicit `promote-review-seal` remains approval. An answer can guide a new
candidate and allow an inert replacement to be sealed, but it never changes the
accepted head. This separation avoids interpreting free text as confirmation
and preserves the existing final human decision.

For the initial declared-relation reason, review-required eligibility is
strictly structural: every changed predecessor row and affected predecessor
endpoint has full capsule authority; each changed relation is mechanically
derived from an authorized row operation; the assembled candidate has no
dangling relation and clears every roadmap gate; and the complete ordered
relation diff is present in the requirement. Failure of any condition is a hard
refusal, not a review prompt.

## Scope guardrails

- The selected roadmap feedback row is the only user-authored request. Do not
  add relation-specific feedback, a synthetic feedback row, another question
  inventory, a confirmation command, or an `--allow-*` escape.
- The binary observable is: an otherwise valid candidate with an exact eligible
  policy impact produces one immutable review-bound candidate, while the same
  candidate with any ungrounded or widened impact produces no candidate.
- Do not ask the validator to judge prose quality, whether feedback and
  candidate prose semantically agree, whether a relationship change is
  desirable or necessary, or whether an opaque answer means approval.
- Do not add shape or length caps, a new roadmap-content gate, or a new
  outcome-to-exit-code policy. A stored review-required candidate uses the
  existing stored-proposal behavior; a hard refusal keeps the existing
  fail-closed behavior.
- Do not turn the typed review-requirement record into a plugin system, policy
  registry, rule language, or general-purpose approval framework.
- Do not weaken accepted-head authority: initial and replacement candidates,
  answers, and seals remain inert until exact review-seal promotion.

## Scope of work

- Establish the three materializer dispositions and the immutable identity of
  a bounded review requirement without changing hard-refusal precedence.
- Persist a review-required initial candidate and bind its exact requirement
  into the existing single-question inventory.
- Carry that same review binding into replacement materialization, allowing
  only elimination or equal-or-narrower retention of the disclosed impact.
- Preserve the existing seal and promotion authority boundary, replay and
  staleness rules, and ordinary gate-clean candidate path.
- Document the resulting lifecycle, add deterministic regression coverage, and
  reconcile `BACKLOG.md` #354 plus the roadmap and Integration MVP backlog arcs when
  the implementation ships.

## Out of scope

- A second feedback or confirmation mechanism, multiple reviewer questions,
  browser or remote feedback transport, chat, or changes to human-I/O formats.
- A generic policy engine or conversion of unrelated candidate refusals into
  review requirements. Additional typed reasons require separate evidence and
  scope.
- Standalone relation operations, broader relation-edit authority, automatic
  repair of candidate deltas, or model judgment of whether a relation change is
  correct.
- Changes to feedback-row states, response history, reopening, structural
  rewrite, source baselines, seed invalidation, or roadmap generation stages.
- Automatic promotion, mutation of live top-level roadmap artifacts, or any
  direct update to Integration's accepted roadmap.

## Allowed behavior changes

- A candidate proposal that currently ends only at `relation-authority` may
  instead store an inert review-required candidate when every eligibility
  condition is mechanically proven.
- The existing candidate question will include the bound materializer concern,
  and its answer-bound replacement may retain only the same or a narrower
  disclosed impact.
- Hard-invalid proposals and replacements continue to refuse without a
  candidate, and ordinary gate-clean candidate review continues unchanged.

## Allowed reorganization

The plan may separate materialization's structural result from its review-policy
result, or introduce the smallest shared comparison needed by initial and
replacement materialization. It may not reorganize the candidate lifecycle,
generalize policy dispatch, or merge review, sealing, and promotion ownership.

## Risks

- Treating an opaque answer as semantic approval would make arbitrary text an
  authority token. Keep answer incorporation distinct from accepted-head
  promotion.
- Persisting a candidate described as gate-clean while it carries an unresolved
  requirement would make the stored contract misleading. Give the state an
  explicit review-required representation and prevent direct sealing or
  promotion around it.
- Comparing only relation counts or row ids could let a different impact reuse
  old review. Bind and compare the complete ordered diff and every affected
  identity.
- Turning the Integration example into a named exception would hide the same policy
  shape elsewhere. Eligibility derives from capsule authority and candidate
  diffs only.
- Re-running existing clean-path tests alone could miss weakened refusal
  behavior. Preserve adversarial coverage for ungrounded endpoints, untouched
  owners, widened replacements, stale predecessors, and direct promotion
  attempts.

## Testing

At the bare-plan gate, retain the single-review lifecycle, the three disposition
contracts, hard-refusal precedence, opaque-answer boundary, exact-impact
invalidation, and promotion-only accepted-head authority. Leave concrete record
placement and fixture construction to detail authoring.

At the detail-grounded gate, require deterministic tests covering the initial
proposal, question/answer replacement, seal, and promotion routes. A fixture
matching the membership-proof shape must store a review-required candidate,
surface its exact relation impact through the existing review, allow an
equal-or-narrower answer-bound replacement, and change the accepted head only
after promotion. Counterexamples must prove that malformed deltas, missing full
membership, dangling or undisclosed relations, impact widening, stale lineage,
and direct promotion remain fail-closed. Existing gate-clean candidate replay
and promotion tests remain green. Backend-facing tests use injected invokers;
the plan-tool clone does not write to Integration.

## Acceptance criteria

- One selected feedback row drives the complete proposal, review, answer,
  replacement, seal, and promotion lineage; no second user mechanism exists.
- Materialization exposes deterministic hard-refusal, review-required, and
  gate-clean dispositions with the documented precedence and exit paths.
- Every review-required candidate binds the selected feedback, predecessor,
  capsule, normalized delta, complete candidate diff, affected rows, and exact
  impact identity.
- The existing question inventory exposes and binds the exact requirement, while
  the reviewer answer remains opaque guidance rather than parsed approval.
- An answer-bound replacement can eliminate the requirement or retain no more
  than its disclosed impact; stale, different, wider, or additional impacts
  refuse without a candidate or seal.
- Only exact review-seal promotion changes the accepted head, and existing
  gate-clean candidate behavior remains compatible.
- Focused and full regression suites pass, and the shipped plan reconciles
  `BACKLOG.md` #354 plus both owning backlog-arc records.

## Deferred

Additional materializer-policy reasons, multiple-question review, UI transport,
generic approval infrastructure, response-history changes, and broader relation
authoring remain separate work justified by their own evidence.

## Stop / defer

File any newly discovered policy reason, feedback lifecycle redesign, generic
framework, or Integration product change in `BACKLOG.md` or `BUG_BACKLOG.md`; do not add
it to this plan. Stop and return to plan-level design if the implementation
cannot preserve one user review path, exact impact identity, or promotion-only
accepted-head authority.

## References

- `BACKLOG.md` #354 — source scope contract and reconciliation destination.
- `docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` — owning
  roadmap-capability arc and immutable-candidate ordering.
- `docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md` — real-project
  evidence and current delivery boundary.
- `ROADMAP_FORMAT.md` — accepted-head, candidate-review, seal, and promotion
  authority contract.
- `plan_tool/roadmap_candidate.py:materialize_candidate` — materializer result,
  operation authority, relation authority, assembly, and deterministic diff.
- `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` — initial
  candidate admission and storage boundary.
- `plan_tool/roadmap_candidate_review.py:generate_candidate_question` and
  `plan_tool/roadmap_candidate_review.py:request_replacement` — existing single
  question/answer replacement lifecycle.
- `plan_tool/roadmap_version_promotion.py:promote_review_seal` — sole
  accepted-head mutation boundary.
