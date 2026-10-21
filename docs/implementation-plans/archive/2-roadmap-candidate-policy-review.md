> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Candidate Policy Review
intent: A structurally valid roadmap candidate whose exact, bounded materializer policy
  impact needs human judgment reaches the existing candidate review instead of a terminal
  refusal. The selected feedback row remains the sole user request, the existing question
  and answer remain the sole review exchange, and explicit review-seal promotion remains
  the sole approval that can change the accepted roadmap.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-candidate-policy-review.md
steps:
- id: 1
  title: Add a review-required result with an immutable initial impact identity for
    exact relation changes after all hard refusals
  intent: This lets fully grounded relation impacts reach human judgment without weakening
    refusal precedence or accepted-head authority, while keeping the disclosure being
    reviewed distinct from future replacement impacts.
  files:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-candidate-policy-review/01-review-required-result-immutable.md
  status: done
- id: 2
  title: Store review-required initial candidates while preserving atomic admission
    replacement and append-only candidate evidence
  intent: This preserves the exact policy requirement across storage and replay so
    the existing review can open from the inert candidate.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The runner receives the review-required candidate record, normalized delta
      binding, and initial disclosed-impact identity it must persist and reproduce.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-policy-review/02-store-review-required-initial.md
  status: done
- id: 3
  title: Bind the exact requirement into the one question inventory while keeping
    question records create-only
  intent: This lets one existing question cover the complete disclosed impact while
    `plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` renders the same
    stored facts beside that question and the reviewer answer remains opaque guidance.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/prompts/roadmap-candidate-questions.md
  - tests/test_roadmap_candidate_review.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: The question inventory reads the exact review requirement from the validated
      stored initial candidate.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-policy-review/03-bind-exact-requirement-one-question.md
  status: done
- id: 4
  title: Accept answer-bound replacements only when their recomputed impact is contained
    by the initial disclosure and the admitted capsule
  intent: This prevents an old review from authorizing a changed, wider, stale, or
    additional impact or authority, and keeps canonical mutation behind exact seal
    promotion.
  files:
  - plan_tool/roadmap_candidate.py
  - plan_tool/roadmap_candidate_review.py
  - tests/test_roadmap_candidate.py
  - tests/test_roadmap_candidate_review.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: The answer-bound replacement receives one immutable inventory that binds the
      initially disclosed requirement and its exact question.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-policy-review/04-accept-answer-bound-replacements-only.md
  status: done
- id: 5
  title: 'Document the three candidate outcomes, retire BACKLOG.md #354, and reconcile
    the roadmap and Integration backlog arcs'
  intent: This keeps the live authority contract and both owning delivery records
    aligned with the shipped single-review lifecycle.
  files:
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_format.py
  - BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-integration-mvp.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 4
  depends_on_notes:
    4: The documentation records the landed materialization, replacement, seal, and
      promotion behavior rather than proposed internal names.
  detail: docs/implementation-plans/plan-details/roadmap-candidate-policy-review/05-document-three-candidate-outcomes.md
  status: done
---
# Roadmap Candidate Policy Review

## Overview

This plan implements `BACKLOG.md` #354. It extends the immutable candidate route
delivered by #328 at the point where deterministic materialization has enough
information to prove the proposed change is structurally bounded but not enough
authority to decide whether its relationship effect matches the user's intent.
That remaining judgment belongs in the review the route already requires.
The existing candidate-review result renderer,
`plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result`, is the
observable consumer: it will display the stored materializer requirement beside
the one existing question.

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
not a new feedback row and contains no inferred answer. It has an immutable
initial disclosed-impact identity that binds the complete initial impact, while
each answer-bound replacement receives a separately recomputed replacement
impact identity. The existing question inventory binds the initial requirement
and surfaces its complete affected facts in the same review contact. The
question may ask whether the impact reflects the reviewer's intent, but the
exact answer stays opaque guidance: the tool does not parse `yes`, `no`,
sentiment, or semantic agreement.

`plan_tool/cli/roadmap_cmd.py:_render_candidate_review_result` consumes that
inventory to render the stored requirement deterministically beside the single
model-written question; this is the existing review contact, not another one.

The requirement keeps its full normalized operation sequence and predecessor
diff snapshot as immutable disclosure evidence, but it derives a separate,
ordered, multiplicity-preserving candidate-impact atom stream for containment.
A relation-independent row atom contains an affected row's artifact, collection,
id, and the typed before/after row projection with declared-relation fields
removed. A declared-relation atom contains one added or removed complete
relation occurrence. The relation-difference helper compares relation
occurrences as an ordered multiset, not through `_relation_key` sets or
dictionaries: duplicate declared relations remain separate atoms. The atom
stream is complete: an added, removed, or non-relation-changed row produces its
row atom, and every relation occurrence change produces its relation atom.
Artifact after-digests, whole replacement rows, and whole normalized operations
remain full-disclosure evidence rather than containment atoms because narrowing
one relation legitimately changes each of those enclosing values.

One candidate-owned helper derives that atom stream from the predecessor and
assembled candidate for every materialization disposition. It supplies the hard
relation checks, review-required eligibility, review evidence and identity, and
answer-bound containment. `CandidatePredecessorDiff` remains a compatible
display snapshot; it is not the source for exact repeated-relation authority.

No-requirement evidence remains backward-compatible: pre-change gate-clean
candidate evidence, inventories, replacements, and seals remain valid with
their existing serialized fields and identities. The optional requirement is
omitted from no-requirement records and their identity preimages; only a
review-required record carries and hashes it. The existing review result also
renders the stored requirement's reason, affected facts, normalized operations,
complete diff, and identity deterministically beside its one model-written
question, so the model cannot omit or replace the materializer concern.

An answer-bound replacement is eligible to seal only when its independently
recomputed candidate-impact atom stream is contained by the initial stream. A
`GateCleanCandidate` proves only that the typed review reason has been
eliminated; it still undergoes the same containment comparison. Containment
means the replacement has either that initial typed policy reason or no
remaining policy reason, and every remaining row or relation atom occurs no
more often than in the initial stream; removing atoms is permitted. Source
order remains in persisted evidence and identities, while containment compares
atom multiplicity rather than set membership. The replacement comparison does
not require the two identities to match: it compares independently recomputed
atoms against the fixed initial disclosure while binding the same predecessor
and selected feedback. This allows a narrower relation removal on a surviving
row, because its unchanged relation-independent row atom and its remaining
relation occurrence remain contained. It rejects a new affected row, any
non-relation row change, a repeated or new relation occurrence beyond the
initial multiplicity, a new policy requirement, or any other non-disclosed
candidate change. A review-required replacement reuses exactly the admitted
initial capsule: it cannot request context expansion or persist a
`CandidateReviewReplacementState`. Gate-clean candidate review retains its
existing one-expansion behavior. The review binding grants no new row, capsule,
artifact, or standalone-relation authority.

For a review-required lineage, `request_replacement` and `seal_review` require
the stored predecessor to remain the accepted head before writing a replacement
or seal. The replacement route checks again at its writer boundary; promotion
retains its existing final current-head check for the race after sealing.

Explicit `promote-review-seal` remains approval. An answer can guide a new
candidate and allow an inert replacement to be sealed, but it never changes the
accepted head. This separation avoids interpreting free text as confirmation
and preserves the existing final human decision.

For the initial declared-relation reason, review-required eligibility is
strictly structural and limited to the formerly refused `CandidateReplaceRow`
route for a surviving predecessor row. Every changed predecessor row and
affected predecessor endpoint has full capsule authority; each changed relation
occurrence is mechanically derived from an authorized replacement; the
assembled candidate has no dangling relation and clears every roadmap gate; and
the complete ordered, multiplicity-preserving relation difference is present in
the requirement. Valid existing `CandidateRemoveRow` removal of its owner's
relations and valid `CandidateAddRow` relation anchoring retain their current
gate-clean routes. Failure of any condition is a hard refusal, not a review
prompt.

## Scope guardrails

- The selected roadmap feedback row is the only user-authored request. Do not
  add relation-specific feedback, a synthetic feedback row, another question
  inventory, a confirmation command, or an `--allow-*` escape.
- The binary observable is: an otherwise valid candidate with an exact eligible
  policy impact produces one immutable review-bound candidate, while an initial
  or answer-bound candidate with an ungrounded, unbounded, or
  disclosure-external impact produces no candidate.
- Do not ask the validator to judge prose quality, whether feedback and
  candidate prose semantically agree, whether a relationship change is
  desirable or necessary, or whether an opaque answer means approval.
- Do not add shape or length caps, a new roadmap-content gate, or a new
  outcome-to-exit-code policy. A stored review-required candidate uses the
  existing stored-proposal behavior; a hard refusal keeps the existing
  fail-closed behavior.
- Do not turn the typed review-requirement record into a plugin system, policy
  registry, rule language, or general-purpose approval framework.
- A review-required replacement reuses its initial capsule. Do not let its
  answer request context expansion, write replacement-expansion state, or gain
  authority that the initial candidate did not admit. This does not change the
  existing expansion behavior for gate-clean candidate review.
- A stale review-required lineage writes neither a replacement nor a seal. Do
  not broaden this new check into a change to the existing gate-clean route.
- Do not weaken accepted-head authority: initial and replacement candidates,
  answers, and seals remain inert until exact review-seal promotion.

## References

- [Configuration | Pydantic Docshttps: — Documents frozen, strict, and extra-forbid model configuration for immutable fail-closed candidate records.
- [Validators | Pydantic Docshttps: — Explains model validators for enforcing exclusive dispositions and cross-field lifecycle invariants.
- [Serialization | Pydantic Docshttps: — Covers deterministic model dumping and JSON round-tripping for persisted review evidence.
- [json — JSON encoder and decoderhttps: — Defines Python JSON serialization options such as sorted keys, compact separators, and non-finite-number rejection.
- [hashlib — Secure hashes and message digestshttps: — Documents SHA-256 digest generation for content-addressed candidates, diffs, and review-impact identities.
- [RFC 8785: JSON Canonicalization Scheme (JCS)https: — Specifies invariant JSON encoding rules for reliably hashing structured evidence across repeated materialization.
- [How to parametrize fixtures and test functionshttps: — Shows how to express deterministic disposition, widening, staleness, and promotion counterexample matrices in pytest.

## Steps

See the `steps:` block in the frontmatter.

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

## Risks

- Treating an opaque answer as semantic approval would make arbitrary text an
  authority token. Keep answer incorporation distinct from accepted-head
  promotion.
- Persisting a candidate described as gate-clean while it carries an unresolved
  requirement would make the stored contract misleading. Give the state an
  explicit review-required representation and prevent direct sealing or
  promotion around it.
- Requiring a replacement identity to equal the initial disclosure would make
  the permitted narrower path impossible; comparing only counts, row ids, or
  set-deduplicated relation keys would let a different impact reuse old review.
  Keep the initial and replacement identities distinct, then prove
  multiplicity-preserving atom containment.
- Letting an answer-bound review-required replacement use context expansion
  would grant new capsule authority through the existing review exchange. Keep
  that lineage on its originally admitted capsule and preserve expansion only
  for the existing gate-clean route.
- Turning the Integration example into a named exception would hide the same policy
  shape elsewhere. Eligibility derives from capsule authority and candidate
  diffs only.
- Re-running existing clean-path tests alone could miss weakened refusal
  behavior. Preserve adversarial coverage for ungrounded endpoints, untouched
  owners, widened replacements, stale predecessors, and direct promotion
  attempts.

## Testing

At the bare-plan gate, retain the single-review lifecycle, the three disposition
contracts, hard-refusal precedence, opaque-answer boundary, separate initial
and replacement impact identities with containment, initial-capsule-only
review-required replacements, and promotion-only accepted-head authority.
Leave concrete record placement and fixture construction to detail authoring.

At the detail-grounded gate, require deterministic tests covering the initial
proposal, question/answer replacement, seal, and promotion routes. A fixture
matching the membership-proof shape must store a review-required candidate,
surface its exact relation impact through the existing review, allow an
answer-bound replacement whose recomputed candidate-impact atoms, including a
gate-clean one, are contained by the initial disclosure, and change the accepted
head only after promotion. Counterexamples must prove that malformed deltas,
missing full membership, dangling or undisclosed relations, repeated-relation
multiplicity loss, impact widening, a new non-relation row change, a gate-clean
replacement with an undisclosed change, or non-contained replacement atoms,
context-expansion requests on review-required lineages, stale lineage, and
direct promotion remain fail-closed. Existing gate-clean candidate replay,
including a pre-change persisted lineage and its existing expansion behavior,
and promotion tests remain green.
Backend-facing tests use injected invokers; the plan-tool clone does not write
to Integration.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- One selected feedback row drives the complete proposal, review, answer,
  replacement, seal, and promotion lineage; no second user mechanism exists.
- Materialization exposes deterministic hard-refusal, review-required, and
  gate-clean dispositions with the documented precedence and exit paths.
- Every review-required candidate binds the selected feedback, predecessor,
  capsule, normalized delta, complete candidate diff, affected rows, and exact
  initial disclosed-impact identity.
- The existing question inventory exposes and binds the exact requirement, while
  the review result deterministically displays its complete stored facts beside
  the one question and the reviewer answer remains opaque guidance.
- An answer-bound replacement recomputes its own impact identity and can
  eliminate the requirement or retain its typed reason only when its complete,
  multiplicity-preserving candidate-impact atom stream is contained by the
  initial disclosure; stale, different, wider, or additional impacts refuse
  without a candidate or seal.
- A review-required answer-bound replacement reuses the initial admitted
  capsule and cannot request expansion or persist replacement-expansion state;
  existing gate-clean review expansion remains compatible.
- Pre-change gate-clean evidence, inventory, replacement, and seal records
  replay with their existing identities, while stale review-required lineages
  refuse before replacement or seal writes and promotion retains its final
  race check.
- Only exact review-seal promotion changes the accepted head, and existing
  gate-clean candidate behavior remains compatible.
- Focused and full regression suites pass, and the shipped plan reconciles
  `BACKLOG.md` #354 plus both owning backlog-arc records.

## Deferred

Additional materializer-policy reasons, multiple-question review, UI transport,
generic approval infrastructure, response-history changes, and broader relation
authoring remain separate work justified by their own evidence.
