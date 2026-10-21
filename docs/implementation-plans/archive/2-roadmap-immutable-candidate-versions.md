> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Immutable Candidate Versions
intent: One representative cross-artifact feedback message completes an accepted-head
  to inert candidate to question to reviewer answer to replacement candidate to exact
  promotion lifecycle across all four roadmap artifacts; the promoted version is what
  a real downstream reader resolves, and every previously stored version remains byte-identical.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
enforce_step_tests: true
source_seed: plan-seeds/roadmap-immutable-candidate-versions.md
steps:
- id: 1
  title: Extract one reusable full-roadmap gate evaluator without changing current
    snapshot or structural-revision results
  intent: This isolates the existing ordered gate behavior so a later feature can
    add complete-candidate evidence without mixing that API with the refactor.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/01-extract-one-reusable-full-roadmap-gate.md
  status: done
- id: 2
  title: Expose journaled roadmap publication while preserving every overwrite, rollback
    delete, and journal cleanup
  intent: This gives accepted-head updates a proven atomic publication path instead
    of duplicating recovery logic.
  files:
  - plan_tool/roadmap_revision_publish.py
  - tests/test_roadmap_revision_publish.py
  allowed_mentions:
  - plan_tool/roadmap_revision_run.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/02-expose-journaled-roadmap-publication.md
  status: done
- id: 3
  title: Define exact immutable root and candidate records plus accepted-head resolution
    and enrollment preparation
  intent: This establishes the inert storage and validation contract that atomic enrollment
    uses before any accepted head can become observable.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  creates:
  - plan_tool/roadmap_versions.py
  - tests/test_roadmap_versions.py
  allowed_mentions:
  - plan_tool/roadmap_view.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: The version contract receives one gate-valid complete roadmap bundle and its
      exact raw brief binding.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/03-define-exact-immutable-root-candidate.md
  status: done
- id: 4
  title: Enroll an exact immutable root and atomically fence every legacy writer before
    accepted head becomes observable
  intent: This publishes root and selector authority only in the same delivered boundary
    that prevents every existing in-place writer from bypassing it.
  files:
  - plan_tool/roadmap.py
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_revision_run.py
  - plan_tool/roadmap_structural_revision_run.py
  - plan_tool/roadmap_feedback_reopen.py
  - plan_tool/roadmap_versions.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_revision_run.py
  - tests/test_roadmap_structural_revision_run.py
  - tests/test_roadmap_feedback_reopen.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_versions.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  depends_on_notes:
    2: Root-version and accepted-head publication reuse the durable journal boundary.
    3: Enrollment publishes the exact root and selector through the inert version
      contract, and every legacy route uses that contract's enrollment decision.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/04-enroll-exact-immutable-root-atomically.md
  status: done
- id: 5
  title: Build one lineage-bounded candidate context with a single recorded expansion
  intent: This gives model proposals enough inspectable context without allowing silent
    truncation, replacement-time widening, or arbitrary browsing.
  files:
  - plan_tool/roadmap_revision.py
  - tests/test_roadmap_revision.py
  creates:
  - plan_tool/roadmap_candidate_context.py
  - tests/test_roadmap_candidate_context.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: The context compiler reads the exact accepted predecessor rather than current
      top-level files or a newest candidate.
    4: Candidate work begins only after enrolled legacy writers are fenced.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/05-build-one-lineage-bounded-candidate.md
  status: done
- id: 6
  title: Add direct complete-bundle gate evidence, apply capsule-authorized deltas,
    and bind deterministic candidate diffs
  intent: This adds the first complete-candidate gate caller and turns model interpretation
    into an inert, reviewable version while preserving unchanged artifact bytes.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_snapshot.py
  creates:
  - plan_tool/roadmap_candidate.py
  - tests/test_roadmap_candidate.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  - 5
  depends_on_notes:
    1: The new direct input delegates only to the extracted existing full-roadmap
      gate evaluator.
    3: Candidates are stored immutably beside their exact accepted predecessor.
    5: Existing rows can change only with full-content authority and must preserve
      their relations; only admitted row additions or removals change the relation
      set.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/06-direct-complete-bundle-gate-evidence.md
  status: done
- id: 7
  title: Run the initial bounded candidate proposal within the lineage's one-expansion
    budget and store only a gate-clean inert version
  intent: This maps free-form reviewer feedback to a complete proposal without letting
    a model write canonical state.
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap_candidate_run.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 6
  depends_on_notes:
    6: Accepted model output is materialized only through the typed candidate boundary.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/07-run-initial-bounded-candidate-proposal.md
  status: done
- id: 8
  title: Generate diff-anchored questions, record reviewer answers, and request replacements
    from the same predecessor
  intent: This keeps clarification and authority with the reviewer while retaining
    every prior candidate unchanged.
  files:
  - TESTING.md
  creates:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/prompts/roadmap-candidate-questions.md
  - tests/test_roadmap_candidate_review.py
  allowed_mentions:
  - plan_tool/prompts/roadmap-candidate-delta.md
  complexity: high
  change_type: feature
  depends_on:
  - 6
  - 7
  depends_on_notes:
    6: Question anchors and replacement inputs come from the candidate-bound diff.
    7: An answered review starts from the lineage's stored capsule, may spend its
      still-unused expansion once, and then persists and reuses the resulting final
      capsule rather than editing the prior candidate.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/08-generate-diff-anchored-questions-record.md
  status: done
- id: 9
  title: Promote only a review seal's exact candidate by replacing the accepted-head
    selector while preserving every version file
  intent: This makes explicit deterministic approval the only operation that changes
    canonical version selection.
  creates:
  - plan_tool/roadmap_version_promotion.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  - 6
  - 8
  depends_on_notes:
    2: The accepted-head move uses the durable exact-member publication boundary.
    3: Promotion compares against the current accepted predecessor and immutable stored
      bytes.
    6: Promotion rechecks the exact stored bytes through the direct complete-candidate
      gates and requires the fixed candidate-version and content identities.
    8: Review completion seals the exact question inventory, incorporated answers,
      and current answer-informed candidate binding.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/09-promote-only-review-seal-exact.md
  status: done
- id: 10
  title: Route roadmap views through accepted head while keeping unversioned reads
    unchanged
  intent: This proves that promotion changes downstream behavior rather than only
    metadata.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - plan_tool/roadmap.py
  - plan_tool/roadmap_versions.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 9
  depends_on_notes:
    3: The view reads complete artifact bytes only through accepted-head resolution.
    9: The reader proof observes the exact promoted replacement candidate.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/10-route-roadmap-views-through-accepted.md
  status: done
- id: 11
  title: Expose enrollment, candidate review, answers, and promotion in roadmap CLI
    without changing the HTML overwrite or other modes
  intent: This makes the complete authority lifecycle usable and proves its ordered
    happy path and negative controls with a fake backend.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  - CAPABILITIES.md
  - TESTING.md
  allowed_mentions:
  - plan_tool/roadmap_revision_publish.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 7
  - 8
  - 9
  - 10
  depends_on_notes:
    3: The command can explicitly enroll and resolve an immutable root.
    4: Legacy command modes refuse enrolled roadmaps before bypass writes.
    7: The command can request an inert candidate through the bounded proposal edge.
    8: The command can present questions, record answers, and request a replacement.
    9: The command can approve one immutable review seal and its exact candidate binding.
    10: The integration proof reads the promoted bytes through a real roadmap consumer.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/11-expose-enrollment-candidate-review.md
  status: done
- id: 12
  title: 'Document version authority, record the remaining direct-reader migrations,
    and close #328 after the real-backend observation'
  intent: This keeps the shipped contract discoverable and records plan_tool/create.py,
    plan_tool/cli/authoring.py, plan_tool/cli/roadmap_cmd.py, plan_tool/roadmap.py,
    plan_tool/roadmap_impact_snapshot.py, plan_tool/roadmap_escalation_run.py, plan_tool/roadmap_feedback_reopen.py,
    and plan_tool/roadmap_revision_publish.py as deferred accepted-head reader candidates.
  files:
  - ROADMAP_FORMAT.md
  - CLAUDE.md
  - BACKLOG.md
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 11
  depends_on_notes:
    11: The documentation and backlog describe the landed command, storage, authority,
      refusal, and observed lifecycle rather than proposed names.
  detail: docs/implementation-plans/plan-details/roadmap-immutable-candidate-versions/12-document-version-authority-record.md
  status: done
---
# Roadmap Immutable Candidate Versions

## Overview

This is the smallest proof of conversational roadmap revision that preserves
human authority: the complete functional happy path without its production
lifecycle. The model returns inert proposals from bounded, recorded contexts;
deterministic code owns assembly, gates, questions, promotion, and head selection.

Decision (2026-08-31): this seed replaces the archived direct conversational
impact-transaction direction. It does not import that plan or its audit findings
as requirements, and it does not reopen model-authored operation manifests as
canonical write authority.

Decision (2026-09-01, user-confirmed): the post-run reconciliation findings for
a falsely labelled `root-enrollment` journal and a canonical-but-conflicting
persisted proposal capsule are operational persistence-integrity hardening, not
part of this representative happy-path proof. Normal lifecycle writers do not
produce either state. Do not add exact journal-member validation or
pre-invocation revalidation solely for those states here; deferred hardening
items [#329 and [#330 own them if they
become required.

The bounded local route omits whole-artifact source text from its typed context
(`roadmap_revision.py:build_stage_revision_context`) but retains exact,
unambiguous row-owned source blocks for the selected row, and it permits one
material operation per active feedback item. Existing-row edits preserve their
declared relations; admitted additions and removals can change the stage relation set.
Reusable deterministic seams already bind four admitted artifacts
(`roadmap_impact_snapshot.py:RoadmapImpactSnapshot`),
resolve relation closure (`roadmap_impact_relations.py:resolve_impact_closure`),
run full-roadmap gates
(`roadmap_structural_revision_proof.py:prove_structural_revision_candidate`),
and journal publication (`roadmap_revision_publish.py:_publish_generation`).
This effort adds version authority instead of widening that local writer.

## Problem statement

A cross-artifact correction should not require a reviewer to pre-split one
thought into local operations, but model interpretation cannot become canonical
write authority. In-place regeneration also hides unrelated output variance.

The proof must compare a complete proposal with its accepted predecessor,
clarify it, replace it immutably, and promote exactly what the reviewer saw. A
draft-only mechanism proves storage or prompting, not this authority loop.

## Architecture

### Version authority and enrollment

The inert version contract can build and validate roots, candidates, and
accepted-head records, but it exposes no operation that selects a root. Explicit
enrollment and every legacy-writer refusal land as one delivered boundary:
enrollment stores one gate-valid current four-artifact roadmap as an immutable
root, stores and binds the recorded brief's exact raw UTF-8 bytes used by
candidate context, and selects that root as accepted head only after every
listed legacy entry has the shared enrollment guard. The version route decodes
only those stored bytes for model context; it does not treat the shipped
snapshot's normalized-text digest as version content. No other migration is
included.

Enrollment revalidates the complete captured artifact bundle and raw recorded
brief in the journaled final pre-write window. A mismatch refuses before any
root member or selector is replaced; the held roadmap-writer lease makes this
the final freshness check against every supported in-place writer.

Accepted-head resolution is the sole canonical selector and loads roots and
candidates through one immutable stored-version contract. Candidate
materialization has a fixed content identity binding its predecessor, four
artifact contents, feedback, issued context receipt, and diff. Candidate storage
adds a fixed version identity that also binds its immutable review lineage
(empty for the initial proposal and answer-bound for a replacement), so an
unchanged answer-informed payload is still a distinct replacement version. Once
its questions have no unanswered item and every earlier answer is incorporated
through a replacement, an immutable review seal binds that candidate-version
identity, its content identity, and the exact question/answer lineage.
Equivalent regenerated text cannot substitute. No review record, seal, or
“newest candidate” convention can select canonical content without promotion.

The version contract owns one leaf-safe fixed inventory of the four literal
artifact keys and the member names from `plan_tool/roadmap_artifacts.py`'s
filename constants, rather than deriving either from `plan_tool/roadmap.py`.
A parity test compares that inventory with `STAGES` and
`RoadmapStage.artifact_path`; version resolution and the downstream view import
only the leaf-safe contract, so accepted-head reading does not pull the roadmap
orchestrator into the reader layer.

One fixed immutable roadmap admission binds the representative selected feedback
row's stable identity to its accepted predecessor and initial capsule before a
model call. That admission is the only lineage this proof permits: repeated
proposal, question, or replacement entry resumes or returns it, while a
different feedback selector refuses before a model call and cannot create a
sibling branch. After exact promotion, the same admission, review seal, and
accepted head naming the sealed candidate are the terminal consumption proof;
it is not cleared for a second feedback, and no feedback or answer bytes are
rewritten. A sequential multi-feedback admission lifecycle is not added here.

Existing in-place writers retain unversioned behavior and refuse enrolled
roadmaps rather than bypass the head. No accepted-head writer is delivered in
an earlier step than that fence. Version-aware integration is later work.

The enrollment boundary also recognizes its exact root-generation journal. It
may recover an incomplete root before a head exists and may remove the journal
without rewriting members when every root member and the final selector already
match the recorded new bytes. After enrollment, the only other admitted journal
shape is the exact selector-only promotion generation; every legacy or mixed
generation remains untouched on refusal. This uses the existing journal kind and
exact member evidence, not a new ownership registry or recovery framework.

### Deterministic bounded context

Candidate analysis starts from the current accepted version, immutable reviewer
feedback, and a deterministically compiled context capsule. The initial capsule
contains:

- the feedback and its target;
- the complete typed values and exact deterministically row-owned source blocks
  of rows reached through declared relation closure, plus the relations that
  connect them;
- a compact inventory of every other row, carrying artifact/type, stable id,
  title, and content digest so omitted content remains discoverable by identity;
- the recorded roadmap brief and settled decisions admitted by the roadmap
  artifacts; and
- an exact membership receipt with inclusion reasons, content identities, byte
  count, and the fixed context ceiling.

`plan_tool/roadmap_candidate_context.py` owns one literal 64 KiB ceiling for
the canonical capsule-payload bytes. No CLI, runner, or review caller can
override it. Initial compilation, the one expansion, and answer-driven reuse
all measure against and record that same ceiling; selecting a context limit is
not a workflow input or configuration surface in this proof.

The model may identify one additional row from the compact inventory. Expansion
treats it as an additional closure root, recomputes declared relation closure,
and adds every newly reached row's complete typed value and exact row-owned
source blocks plus the relations connecting the reached set. The receipt binds
the source-span identities and digests, and byte accounting covers their exact
text as part of that complete membership.
If the capsule exceeds that fixed ceiling, the route refuses before candidate
materialization and reports the measured size and members.

One expansion budget belongs to the entire feedback lineage. The initial or the
first answer-driven replacement proposal may spend it. The candidate that
establishes the final capsule stores its complete canonical capsule bytes and
receipt; every later replacement loads and reuses that exact pair. A second
expansion request refuses. An explicit re-entry loads any already-recorded
expansion rather than spending another. There is no silent truncation, lossy
summary, embedding search, or arbitrary model browsing.

Full-content membership is also delta authority. A proposal may change an
existing row only when the capsule issued for that proposal carries that row's
content, and the replacement must preserve every declared relation. Only an
admitted row addition or removal may add or remove declared relations; every
endpoint that already exists in the predecessor and participates in that
consequence must be a full-content member. The compact inventory permits
discovery, not an edit. The model must spend its one expansion before changing
omitted existing content. New content must anchor to the feedback and reached
artifact/relations.

### Judged edges and deterministic envelope

There are two directed judged behaviors: proposing a complete typed delta for a
candidate and proposing clarification questions from a candidate diff. Each has
its own deterministically assembled input, forced output schema, resolvable
anchors, response gates, and total disposition of accepted output, correctable
invalid output, and terminal refusal. `create` derives the exact closed response
delta-operation, and route-outcome vocabularies and gives every value a
definition, producer, precedence, consumer, and operator exit; the seed does not
fossilize those low-level names. The delta contract can express the row changes
needed by the representative cross-artifact case, with relation-set changes only
as consequences of admitted row additions or removals, but cannot grant itself
content authority outside the final capsule.

The model is necessary only for mapping free-form reviewer intent to semantic
roadmap changes and for phrasing unresolved choices. Mechanical target
resolution, declared relation closure, diffing, schema/anchor validation, and
promotion checks stay deterministic. No model judgment decides whether its own
output becomes canonical.

An accepted delta is applied copy-on-write to the accepted predecessor:
unchanged artifact content is copied exactly, changed content is assembled and
rendered through the typed roadmap contracts, and the result is a complete inert
candidate. Step 1 first isolates the existing ordered gate evaluator without a
new public input. Step 6 then adds one direct gate input derived only from
validated complete-candidate evidence—assembled evidence during materialization
and stored evidence during promotion—and binds the stage-ordered text, parsed
artifact, and raw digest for every candidate artifact. The direct route and the
existing snapshot route use that one evaluator, so materialization and promotion
do not fabricate or recapture live snapshot state. A failed delta or gate
changes neither accepted-head state nor any stored version.

### Diff, questions, and replacement candidates

A deterministic diff compares the complete candidate with its accepted
predecessor and records changed rows, relations, and artifact identities. The
question prompt receives the original feedback, changed before/after row bodies,
changed relations, and the issued capsule's stored closure-member identities,
inclusion reasons, and declared-relation evidence, plus a compact identity
inventory for unchanged content; it does not receive the full roadmap merely
because the candidate is complete.

The candidate's immutable predecessor diff and version identity are also the
bounded reviewer handoff. The CLI presents that persisted comparison for the
initial candidate and presents the replacement's persisted comparison and seal
identity after the answer-driven proposal, so promotion can name exactly the
version the reviewer saw without reconstructing it from live artifacts.

Model-proposed questions must anchor to the feedback, diff, or a resolvable
roadmap identity. Deterministic consumption assigns stable question identities
and records one candidate-bound inventory. Re-entry returns that inventory
rather than asking for a sibling question. Every question requires a
reviewer-owned answer, and an answer requires a replacement candidate before
promotion sealing; question generation cannot answer, waive, or authorize.

An answer never edits a candidate or its identity. The route uses the same
accepted predecessor, original feedback, prior grounded diff, the immutable
question-and-answer pair, and the lineage's stored capsule to assemble
and gate a replacement. The prompt pair carries the question id, anchor, exact
opaque question text, answer id, and exact reviewer answer text from immutable
records; it is never reconstructed from live output or reduced to answer text
alone. If the one expansion remains unused, that replacement may spend it and
persists the resulting final capsule and receipt; otherwise it reuses the stored
final pair unchanged. The replacement's version identity binds the answer
lineage separately from its materialized content identity. The previous
candidate remains unchanged and cannot receive the promotion seal. Once the
current candidate has no unanswered question and incorporates that exact
question-and-answer pair, deterministic code creates its immutable review seal.
The proof exercises one question, one answer, and one replacement. If
replacement does not finish, replaying the exact same question-and-answer pair
through the existing action resumes that recorded replacement input; different
answer bytes refuse, and a completed replacement is returned without another
model call.

### Exact promotion and canonical reading

Approval names one immutable review seal and its bound candidate-version
identity after the reviewer-visible persisted diff handoff.
Promotion performs no model call, regeneration, reconciliation, or artifact
rewrite: it atomically moves only the accepted-head selection after rechecking
the seal, incorporated answers, candidate gates/content, and current predecessor.
Any mismatch refuses without changing the head. Once the head names the sealed
candidate, the same admission prevents the still-open stored feedback row from
starting another lineage.

One real downstream roadmap reader resolves an enrolled roadmap through the
accepted-head boundary and observes the promoted version. Other reader migration
is deferred; this vertical consumer proves that promotion changes behavior, not
only metadata.

## Scope guardrails

- **Binary observables:** candidate/version bytes, content and version identities,
  persisted predecessor diffs shown to the reviewer, immutable review seals,
  accepted-head predecessor equality, context membership/bytes, resolvable
  anchors, gate results, answer incorporation, and bytes returned by head
  resolution.
- **Allowed behavior changes:** the new enrollment, candidate-review, answer,
  promotion, and accepted-head read path; refusal by legacy in-place writers for
  an enrolled roadmap; no behavior change for an unversioned roadmap.
- **Allowed reorganization:** one shared accepted-head selection boundary may
  become the owner for version-aware reads. No unrelated roadmap pipeline or
  artifact-model reorganization is allowed.
- Model output may create only inert proposed deltas and questions. It never
  mutates a stored version, moves the accepted head, answers a question, or
  authorizes promotion.
- Candidate materialization precedes questions; each answer precedes a
  replacement whose prompt carries the immutable question-and-answer pair;
  pair incorporation precedes an immutable review seal; approval of that seal
  precedes promotion. Promotion changes only the head.
- Feedback, answers, predecessor, fixed candidate content identity, answer-bound
  candidate-version identity, and immutable review seal remain distinct; later
  non-deterministic output cannot substitute for the approved binding.
- One fixed persisted roadmap admission owns the representative feedback's
  proposal, question, answer, and replacement lineage. Exact command replay may
  continue or return that lineage; a different feedback refuses, and replay
  cannot change reviewer input, spend another expansion, or create a branch.
- Context omission is inspectable; the canonical capsule payload has one
  module-owned 64 KiB ceiling, and there is no caller override, silent
  truncation, summary, or widening beyond one recorded expansion for the full
  feedback lineage.
- A compact-inventory identity is not edit authority. Existing content must be
  present in full in the issued capsule before a delta may change it, and an
  existing-row change preserves its declared relations. A relation-set change
  occurs only as the consequence of an admitted row addition or removal, with
  every affected predecessor endpoint present in full.
- Bounded feedback and structural rewrite stay intact for unversioned roadmaps;
  neither becomes a free-form cross-artifact writer.
- Validation may not judge whether feedback, a delta, a question, an answer, or
  roadmap prose is true, high-quality, complete, or equivalent to other prose;
  use shape, count, or length as a quality proxy; or add gates/exit changes
  outside the new route and enrollment fence. The fixed capsule byte ceiling
  produces only mechanical acceptance or refusal.
- The implementation is the smallest complete functional happy path. Production
  hardening and adjacent version management remain outside the plan.

## References

- [Structured outputs - Claude Platform Docshttps: — Explains schema-constrained Claude responses for producing validated inert deltas and clarification questions.
- [Configuration | Pydantic Docshttps: — Documents strict validation, forbidden extra fields, and frozen models for closed immutable record contracts.
- [os — Miscellaneous operating system interfaceshttps: — Documents atomic replacement and filesystem synchronization primitives needed for durable accepted-head promotion.
- [json — JSON encoder and decoderhttps: — Covers deterministic JSON serialization and strict decoding hooks used for sealed records and reproducible identities.
- [hashlib — Secure hashes and message digestshttps: — Provides the SHA-256 APIs used to bind candidate contents, predecessors, contexts, and review records.
- [RFC 8785: JSON Canonicalization Scheme (JCS)https: — Defines canonical JSON rules for producing stable hashable representations across repeated serialization.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Direct model-to-canonical writes, model-authored transaction manifests,
  automatic promotion, promotion of a regenerated equivalent, or in-place
  mutation of any version.
- Multiple reviewers, concurrent branches, merges, leases, collaborative editing,
  or arbitrary workflow states.
- Rollback/history/comparison UI, garbage collection, retention, or bulk legacy
  migration.
- Crash recovery and operational hardening beyond the durable publication
  primitive needed for the exact accepted-head move on the happy path.
- General retrieval, embeddings, unbounded expansion, model-selected filesystem
  access, silent summarization, or a configurable context framework.
- Migration of every roadmap reader or integration of existing local/structural
  writers with candidate versions; this proof converts one downstream reader and
  refuses bypass writes on enrolled roadmaps.
- Integration/browser transport, generic document chat/versioning, or a generic editor.
- #242's in-document feedback-retention direction, which remains paused and
  unchanged.

## Risks

- **Missing semantic context:** declared relations may not expose an implicit
  dependency. The compact inventory plus one expansion tests the bounded remedy;
  the stop rule prevents silent growth.
- **Non-deterministic replacement drift:** an answer-driven model call may alter
  unrelated content. Same-predecessor rebuilding, complete diffs, retained
  candidates, and exact approval make it visible and inert.
- **Split authority:** a legacy writer or reader could bypass accepted-head
  selection. Enrollment and writer refusal land atomically, and one converted
  reader tests the local fence; a non-local remedy triggers redesign rather than
  tool-wide migration.
- **Prompt growth:** full closure rows or the recorded brief may exceed the
  context budget. Exact accounting and refusal expose the boundary without lossy
  compression.
- **Question theater:** unconstrained questions could merely restate the diff.
  Anchors and reviewer-owned answers make the channel inspectable; tests do not
  predict question quality.

## Testing

Use one representative cross-artifact fixture and a deterministic fake backend
to prove the complete lifecycle: byte-preserving enrollment with exact raw
UTF-8 recorded-brief carriage, including CRLF preservation; exact initial and
expanded closure membership/reasons/bytes, including deterministic row-owned
source-span identity, digest, and exact text;
the same module-owned 64 KiB capsule ceiling on initial, expanded, and
answer-driven context compilation;
gated inert candidate with fixed content and version identities; persisted
reviewer-visible predecessor diff; diff-anchored question; an answer-driven
replacement prompt containing the exact stored question id, anchor, opaque text,
answer id, and answer text, which may spend only the lineage's still-unused
expansion and then stores the final capsule; immutable review seal; exact
promotion; and downstream head resolution while prior versions remain
byte-identical.

Negative controls prove that over-budget context, invalid or unanchored model
output, a relation naming a compact-only predecessor endpoint, a gate-failing
complete candidate, a candidate whose stage evidence does not match its parsed
artifacts, an unanswered question, a stale accepted head,
an unincorporated answer, or changed/substituted candidate content identity,
candidate-version identity, or review seal cannot promote or mutate canonical
state. An over-budget refusal reports the fixed ceiling, measured bytes, and
complete deterministic member identities and inclusion reasons without returning
member content. A repeated proposal returns the fixed admission, a different
feedback selector cannot create a second lineage, review entry on an answer-bound
replacement refuses, an existing-row edit cannot change its relations, an exact
answer replay can finish but not replace the recorded answer, and a second
lineage expansion refuses. The leaf-safe version inventory must match the
orchestrator's four stage keys and member names exactly.
Enrollment refuses when any captured artifact or raw brief changes before its
final pre-write recheck. In-place writers refuse as part of the same delivered
boundary that exposes enrollment. A fully committed root-enrollment journal
cleans up after the selector makes the roadmap enrolled, while an enrolled
legacy or mixed generation remains untouched.

The bare plan retains the authority boundary, bounded-context membership,
single-expansion rule, complete candidate/answer/replacement lifecycle, exact
promotion checks, real-reader proof, and every negative-control property above.
Storage paths, carrier shapes, prompt/command spelling, and fixture construction
belong to `detail`; its audit may require concrete mechanics for these properties
but cannot broaden the lifecycle or add hardening.

The handoff records one real-backend observation of prompt bytes, membership,
expansion use, and response disposition. This monitors the chosen path; it is
not a comparison, semantic-quality claim, or acceptance prediction.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — tests covering the behavior this step changes; green before completion.
- step 2 (refactor) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (feature) — tests covering the behavior this step changes; green before completion.
- step 8 (feature) — tests covering the behavior this step changes; green before completion.
- step 9 (feature) — tests covering the behavior this step changes; green before completion.
- step 10 (feature) — tests covering the behavior this step changes; green before completion.
- step 11 (feature) — tests covering the behavior this step changes; green before completion.
- step 12 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- The representative four-artifact lifecycle reaches the exact reviewer-displayed,
  answer-informed replacement candidate version and promotes it without changing
  any stored version.
- Accepted-head resolution returns the promoted bytes to one real downstream
  consumer; no newest-candidate or model-output fallback can select them.
- Every model output is inert until deterministic assembly, gates, question
  completion, immutable question-and-answer-pair incorporation, exact review-seal
  approval, and stale-head recheck succeed in order.
- An answer-driven replacement prompt contains the exact stored question id,
  anchor, opaque question text, answer id, and answer text; answer text alone
  never supplies its meaning, and no live source reconstructs the pair.
- Materialization and promotion each gate one stage-ordered candidate input whose
  text, parsed artifact, and raw digest agree for every roadmap stage; neither
  validates a cross-artifact candidate through single-stage substitutions.
- Context membership and byte size are reproducible, at most one expansion is
  possible across the fixed admitted feedback lineage, explicit re-entry reuses
  its recorded capsule and exact answer, a different feedback cannot create a
  second lineage before or after promotion, the candidate that spends the
  expansion stores the complete final capsule and receipt, every compilation
  uses the module-owned 64 KiB capsule ceiling without a caller override, and an
  over-budget refusal reports that ceiling, measured bytes, and deterministic
  full-member identities and inclusion reasons without silent truncation,
  summarization, or partial content.
- Existing-row replacements preserve every declared relation. Relation-set
  changes occur only through admitted row additions or removals, with each
  affected predecessor endpoint present in full in the issued capsule.
- The leaf-safe fixed version inventory matches the orchestrator's four stage
  keys and member names without making the accepted-head reader import the
  orchestrator.
- Root enrollment revalidates every captured artifact and the raw recorded brief
  in its final pre-write window, so an accepted head cannot select a root that
  became stale after capture.
- Unversioned roadmap routes preserve their current contracts; enrolled
  roadmaps cannot be mutated through a legacy in-place writer.
- The plan updates `BACKLOG.md` #328 when the capability ships.

## Deferred

If the representative semantic effect cannot be expressed from the initial
capsule plus one expansion, stop and record the exact prompt size, included and
missing context, and observed failure as a separate design decision. Do not add
another expansion, full-roadmap prompt, retrieval layer, or silent summary to
make the proof pass.

If accepted-head authority cannot be protected with a local enrollment fence
and one version-aware reader, stop and split the necessary writer/reader
migration into a separately authorized effort rather than absorbing a global
roadmap-storage migration here.

Any concurrency, recovery, history, retention, transport, generalized
versioning, or legacy-writer integration discovered during implementation goes
to `BACKLOG.md` or `BUG_BACKLOG.md`. It does not expand this plan.
