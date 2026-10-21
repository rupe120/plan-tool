> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-immutable-candidate-versions.md`.
> Preserved here for history; do not edit.

# Immutable roadmap candidate versions and accepted-head promotion

Source: `BACKLOG.md` #328. The resulting plan updates #328 when this capability
ships.

## Outcome

One representative cross-artifact feedback message completes an accepted-head
to inert candidate to question to reviewer answer to replacement candidate to
exact promotion lifecycle across all four roadmap artifacts; the promoted
version is what a real downstream reader resolves, and every previously stored
version remains byte-identical.

## Overview

This is the smallest proof of conversational roadmap revision that preserves
human authority: the complete functional happy path without its production
lifecycle. The model returns inert proposals from bounded, recorded contexts;
deterministic code owns assembly, gates, questions, promotion, and head selection.

Decision (2026-08-31): this seed replaces the archived direct conversational
impact-transaction direction. It does not import that plan or its audit findings
as requirements, and it does not reopen model-authored operation manifests as
canonical write authority.

The bounded local route still omits source text from its typed context
(`roadmap_revision.py:build_stage_revision_context`) and permits one material
operation per active feedback item. Existing-row edits preserve their declared
relations; admitted additions and removals can change the stage relation set.
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

Explicit enrollment stores one gate-valid current four-artifact roadmap as an
immutable root, stores and binds the exact recorded brief used by candidate
context, and selects that root as accepted head without changing its bytes. No
other migration is included.

Accepted-head resolution is the sole canonical selector and loads roots and
candidates through one immutable stored-version contract. Candidate
materialization has a fixed content identity binding its predecessor, four
artifact contents, feedback, issued context receipt, and diff. Candidate storage
adds a fixed version identity that also binds its immutable review lineage, so
an unchanged answer-informed payload remains a distinct replacement version.
Once its questions have no unanswered item and every earlier answer is
incorporated through a replacement, an immutable review seal binds that
candidate-version identity, its content identity, and the exact question/answer
lineage. Equivalent regenerated text cannot substitute. No review record, seal,
or “newest candidate” convention can select canonical content without promotion.

Existing in-place writers retain unversioned behavior and refuse enrolled
roadmaps rather than bypass the head. Version-aware integration is later work.

### Deterministic bounded context

Candidate analysis starts from the current accepted version, immutable reviewer
feedback, and a deterministically compiled context capsule. The initial capsule
contains:

- the feedback and its target;
- the full bodies of rows reached through declared relation closure and the
  relations that connect them;
- a compact inventory of every other row, carrying artifact/type, stable id,
  title, and content digest so omitted content remains discoverable by identity;
- the recorded roadmap brief and settled decisions admitted by the roadmap
  artifacts; and
- an exact membership receipt with inclusion reasons, content identities, byte
  count, and the declared context budget.

The model may identify one additional row from the compact inventory. Expansion
treats it as an additional closure root, recomputes declared relation closure,
and adds the full body of every newly reached row plus the relations connecting
the reached set. The receipt and byte accounting cover that complete membership.
If the capsule exceeds its hard budget, the route refuses before candidate
materialization and reports the measured size and members.

One expansion budget belongs to the entire feedback lineage. The initial or the
first answer-driven replacement proposal may spend it. The candidate that
establishes the final capsule stores its complete canonical capsule bytes and
receipt; every later replacement loads and reuses that exact pair. A second
expansion request refuses. There is no silent truncation, lossy summary,
embedding search, or arbitrary model browsing.

Full-content membership is also delta authority. A proposal may change an
existing row or relation only when the capsule issued for that proposal carries the content
needed to evaluate that change; the compact inventory permits discovery, not an
edit. The model must spend its one expansion before changing omitted existing
content. New content must anchor to the feedback and reached artifact/relations.

### Judged edges and deterministic envelope

There are two directed judged behaviors: proposing a complete typed delta for a
candidate and proposing clarification questions from a candidate diff. Each has
its own deterministically assembled input, forced output schema, resolvable
anchors, response gates, and total disposition of accepted output, correctable
invalid output, and terminal refusal. `create` derives the exact closed response
delta-operation, and route-outcome vocabularies and gives every value a
definition, producer, precedence, consumer, and operator exit; the seed does not
fossilize those low-level names. The delta contract can express the row and
declared-relation changes needed by the representative cross-artifact case, but
cannot grant itself content authority outside the final capsule.

The model is necessary only for mapping free-form reviewer intent to semantic
roadmap changes and for phrasing unresolved choices. Mechanical target
resolution, declared relation closure, diffing, schema/anchor validation, and
promotion checks stay deterministic. No model judgment decides whether its own
output becomes canonical.

An accepted delta is applied copy-on-write to the accepted predecessor:
unchanged artifact content is copied exactly, changed content is assembled and
rendered through the typed roadmap contracts, and the result is a complete inert
candidate. The full-roadmap gates run over the assembled candidate before it can
enter review. A failed delta or gate changes neither accepted-head state nor any
stored version.

### Diff, questions, and replacement candidates

A deterministic diff compares the complete candidate with its accepted
predecessor and records changed rows, relations, and artifact identities. The
question prompt receives the original feedback, accumulated reviewer answers,
changed before/after row bodies, changed relations, closure or gate facts, and a
compact identity inventory for unchanged content; it does not receive the full
roadmap merely because the candidate is complete.

The candidate's immutable predecessor diff and version identity are also the
bounded reviewer handoff. The operator sees the persisted comparison for the
initial candidate and the replacement before exact seal approval; the route does
not reconstruct either comparison from live artifacts.

Model-proposed questions must anchor to the feedback, diff, or a resolvable
roadmap identity. Deterministic consumption assigns stable question identities
and records every question in one inventory. Every question requires a
reviewer-owned answer, and an answer requires a replacement candidate before
promotion sealing; question generation cannot answer, waive, or authorize.

An answer never edits a candidate or its identity. The route uses the same
accepted predecessor, original feedback, prior grounded diff, accumulated
immutable answers, and the lineage's stored capsule to assemble and gate a
replacement. If the expansion remains unused, that replacement may spend it and
stores the resulting final capsule and receipt; otherwise it reuses the stored
pair. Its answer-bound version identity remains distinct from its materialized
content identity. The previous candidate remains unchanged and cannot receive
the promotion seal. Once the current candidate has no unanswered question and
incorporates all earlier answers, deterministic code creates its immutable
review seal. The proof exercises one question, one answer, and one replacement.

### Exact promotion and canonical reading

Approval names one immutable review seal and its bound candidate-version
identity after the reviewer-visible persisted diff handoff.
Promotion performs no model call, regeneration, reconciliation, or artifact
rewrite: it atomically moves only the accepted-head selection after rechecking
the seal, incorporated answers, candidate gates/content, and current predecessor.
Any mismatch refuses without changing the head.

One real downstream roadmap reader resolves an enrolled roadmap through the
accepted-head boundary and observes the promoted version. Other reader migration
is deferred; this vertical consumer proves that promotion changes behavior, not
only metadata.

## In scope

- Explicit enrollment of one admitted four-artifact roadmap as an immutable root
  version and accepted head.
- Complete immutable candidates, fixed content and answer-bound version
  identities, and immutable review seals for the feedback, question, answer,
  replacement, and promotion lifecycle.
- Deterministic bounded context, one recorded expansion, exact accounting,
  directed delta/question contracts, and fail-closed gates.
- Copy-on-write assembly from the accepted predecessor, full-roadmap validation,
  deterministic diff, answer-driven replacement, and exact promotion.
- Accepted-head resolution for the version lifecycle and one real downstream
  consumer.
- Refusal of in-place writers on enrolled roadmaps, with unversioned behavior
  unchanged.

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
  replacement; answer incorporation precedes an immutable review seal; approval
  of that seal precedes promotion. Promotion changes only the head.
- Feedback, answers, predecessor, fixed candidate content identity, answer-bound
  candidate-version identity, and immutable review seal remain distinct; later
  non-deterministic output cannot substitute for the approved binding.
- Context omission is inspectable; there is no silent truncation, summary, or
  widening beyond one recorded expansion for the full feedback lineage.
- A compact-inventory identity is not edit authority. Existing content must be
  present in full in the issued capsule before a delta may change it.
- Bounded feedback and structural rewrite stay intact for unversioned roadmaps;
  neither becomes a free-form cross-artifact writer.
- Validation may not judge whether feedback, a delta, a question, an answer, or
  roadmap prose is true, high-quality, complete, or equivalent to other prose;
  use shape, count, or length as a quality proxy; or add gates/exit changes
  outside the new route and enrollment fence. Declared byte budgets only produce
  mechanical acceptance or refusal.
- The implementation is the smallest complete functional happy path. Production
  hardening and adjacent version management remain outside the plan.

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
  selection. Writer refusal and one converted reader test the local fence; a
  non-local remedy triggers redesign rather than tool-wide migration.
- **Prompt growth:** full closure rows or the recorded brief may exceed the
  context budget. Exact accounting and refusal expose the boundary without lossy
  compression.
- **Question theater:** unconstrained questions could merely restate the diff.
  Anchors and reviewer-owned answers make the channel inspectable; tests do not
  predict question quality.

## Testing

Use one representative cross-artifact fixture and a deterministic fake backend
to prove the complete lifecycle: byte-preserving enrollment with exact recorded
brief carriage; exact initial and expanded closure membership/reasons/bytes;
gated inert candidate with fixed content and version identities; persisted
reviewer-visible predecessor diff; diff-anchored question; an answer-driven
replacement that may spend only the lineage's still-unused expansion and then
stores the final capsule; immutable review seal; exact promotion; and downstream
head resolution while prior versions remain byte-identical.

Negative controls prove that over-budget context, invalid or unanchored model
output, a gate-failing candidate, an unanswered question, a stale accepted head,
an unincorporated answer, or changed/substituted candidate content identity,
candidate-version identity, or review seal cannot promote or mutate canonical
state. A second lineage expansion
refuses. In-place writers refuse only after enrollment.

The bare plan retains the authority boundary, bounded-context membership,
single-expansion rule, complete candidate/answer/replacement lifecycle, exact
promotion checks, real-reader proof, and every negative-control property above.
Storage paths, carrier shapes, prompt/command spelling, and fixture construction
belong to `detail`; its audit may require concrete mechanics for these properties
but cannot broaden the lifecycle or add hardening.

The handoff records one real-backend observation of prompt bytes, membership,
expansion use, and response disposition. This monitors the chosen path; it is
not a comparison, semantic-quality claim, or acceptance prediction.

## Acceptance criteria

- The representative four-artifact lifecycle reaches the exact reviewer-displayed,
  answer-informed replacement candidate version and promotes it without changing
  any stored version.
- Accepted-head resolution returns the promoted bytes to one real downstream
  consumer; no newest-candidate or model-output fallback can select them.
- Every model output is inert until deterministic assembly, gates, question
  completion, answer incorporation, exact review-seal approval, and stale-head
  recheck succeed in order.
- Context membership and byte size are reproducible, at most one expansion is
  possible across the full feedback lineage, the candidate that spends it stores
  the complete final capsule and receipt for later replacement reuse, and an
  over-budget or insufficient capsule fails closed without silent truncation or
  summarization.
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
