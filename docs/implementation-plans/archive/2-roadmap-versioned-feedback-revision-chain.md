> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Versioned Feedback Revision Chain
intent: Roadmap artifacts are immutable versions and never contain mutable feedback.
  Each roadmap has one reviewer-owned feedback ledger outside the artifact set. An
  operator can edit and submit ledger items without amending an accepted artifact.
  An ordinary feedback run snapshots eligible reviewer feedback and current roadmap-derived
  context into one exact batch, then stores an inert candidate revision. Guarded root
  enrollment, exact review-seal promotion, and enrolled decision settlement are the
  only accepted-head writers; none rewrites reviewer feedback.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-versioned-feedback-revision-chain.md
steps:
- id: 1
  title: Define the canonical mutable feedback ledger, target fingerprints, and eligibility
    rules
  intent: Give every roadmap one reviewer-owned mutable feedback format that distinguishes
    durable reviewer input from revision-bound roadmap-derived context, with deterministic
    bytes, stable item identities, and fail-closed target provenance.
  creates:
  - plan_tool/roadmap_feedback_ledger.py
  - tests/test_roadmap_feedback_ledger.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/01-define-canonical-mutable-feedback.md
  status: done
- id: 2
  title: Make root enrollment store feedback-free versions while blocking legacy feedback
    processing until explicit ledger migration
  intent: Establish ledger authority without silently migrating embedded feedback,
    rewriting legacy working artifacts, or creating a second version chain.
  files:
  - plan_tool/roadmap.py
  - tests/test_roadmap.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides canonical ledger bytes and the projection that removes embedded feedback
      from stored artifact content.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/02-make-root-enrollment-store-feedback.md
  status: done
- id: 3
  title: Build one ordered root-and-active-candidate batch from eligible reviewer
    feedback and current roadmap-derived context
  intent: Bind each proposal to the current accepted root, its direct source revision,
    the canonical ledger digest, ordered eligible reviewer snapshots, and nondeleted
    derived context in stable order.
  files:
  - plan_tool/roadmap_candidate_context.py
  - tests/test_roadmap_candidate_context.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the shared eligibility predicate, target fingerprints, canonical digest,
      and immutable item shape.
    2: Establishes the feedback-free enrollment boundary and blocks embedded-feedback
      processing until the explicit migration completes.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/03-build-one-ordered-root-active-candidate.md
  status: done
- id: 4
  title: Build feedback-free successor artifacts, a response patch, and a fresh roadmap-derived
    feedback set
  intent: Let one model response propose an immutable artifact successor while changing
    only admitted reviewer items from open to awaiting-review with candidate-revision
    provenance, while deriving a new revision-bound feedback set rather than carrying
    one forward.
  files:
  - plan_tool/roadmap_candidate.py
  - plan_tool/prompts/roadmap-candidate-delta.md
  - plan_tool/prompts/roadmap-candidate-delta-selector.md
  - tests/test_roadmap_candidate.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Provides the exact ordered item snapshots and predecessor binding that authorize
      operations and proposed responses.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/04-build-feedback-free-successor-artifacts.md
  status: done
- id: 5
  title: Store batch responses with one root-and-active-candidate pointer while retaining
    superseded candidate history
  intent: Ensure successful candidate storage records exact root/source evidence,
    batch responses, and its fresh derived set; replacing an active candidate retains
    prior evidence as superseded while retries and pre-storage failures preserve state.
  files:
  - plan_tool/roadmap_candidate_run.py
  - tests/test_roadmap_candidate_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: Provides the root, direct-source, and immutable batch identity persisted in
      admission and candidate evidence.
    4: Provides the validated successor artifacts and the bounded ledger response
      patch stored in one guarded publication.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/05-store-batch-responses-one-root-active.md
  status: done
- id: 6
  title: Add explicit idempotent legacy migration and guarded mutable reviewer edits
    in predecessor-grouped ledger sections
  intent: Let reviewers submit, retarget, defer, close, or reopen retained mutable
    items without changing artifact versions, moving items between predecessor sections
    when retargeted, and blocking only legacy ledger processing until migration completion.
  creates:
  - plan_tool/roadmap_feedback_ledger_run.py
  - tests/test_roadmap_feedback_ledger_run.py
  files:
  - plan_tool/roadmap_feedback_ledger.py
  - tests/test_roadmap_feedback_ledger.py
  - ROADMAP_FEEDBACK_FORMAT.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 5
  depends_on_notes:
    1: Provides canonical validation, rendering, target provenance, and ledger path
      ownership.
    5: Defines the root/active-candidate pointer, supersession history, and batch
      transition that reviewer edits must not race.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/06-explicit-idempotent-legacy-migration.md
  status: done
- id: 7
  title: Gate enrolled decision settlement behind an atomic active-candidate confirmation
  intent: Let a caller confirm an accepted-head change that stales an active candidate,
    or decline with no write, using a container/front-end-safe response handshake.
  files:
  - plan_tool/roadmap_decision_settlement_enrolled.py
  - plan_tool/roadmap_decision_settlement.py
  - tests/test_roadmap_decision_settlement_enrolled.py
  - tests/test_roadmap_decision_settlement.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 5
  - 6
  depends_on_notes:
    1: Provides the ledger item and target-provenance contract used as settlement
      evidence.
    5: Provides the root/active-candidate pointer and terminal stale-resolution facts
      that settlement must recheck and update atomically.
    6: Provides the guarded authoritative ledger loader and completed-migration boundary.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/07-gate-enrolled-decision-settlement.md
  status: done
- id: 8
  title: Bind candidate questions, answers, rejection, and discard resolution to the
    exact active-candidate batch
  intent: Prevent review activity from substituting later ledger edits or a different
    root/source pair, and release a rejected or explicitly discarded active candidate
    without deleting history.
  files:
  - plan_tool/roadmap_candidate_review.py
  - plan_tool/prompts/roadmap-candidate-questions.md
  - tests/test_roadmap_candidate_review.py
  complexity: high
  change_type: feature
  depends_on:
  - 4
  - 5
  depends_on_notes:
    4: Provides batch-limited response evidence and feedback-free successor semantics.
    5: Provides the stored root/source-bound active candidate, pointer publication,
      and supersession lineage reviewed or discarded here.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/08-bind-candidate-questions-answers.md
  status: done
- id: 9
  title: Promote only the exact active candidate for the current root and keep promotion
    from reading or rewriting the live ledger
  intent: Make the reviewed active successor canonical only for its exact root, direct
    source, and snapshot, regardless of later ledger changes.
  files:
  - plan_tool/roadmap_version_promotion.py
  - tests/test_roadmap_version_promotion.py
  complexity: high
  change_type: feature
  depends_on:
  - 5
  - 8
  depends_on_notes:
    5: Provides immutable candidate evidence containing the root, direct source, active
      pointer, and ledger batch snapshot.
    8: Provides the exact batch-bound replacement candidate and review seal.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/09-promote-only-exact-active-candidate.md
  status: done
- id: 10
  title: Route selector-free feedback commands to the ledger lifecycle, retire the
    live-artifact overwrite, and preserve unenrolled legacy writers behind their existing
    fence
  intent: Expose one reviewer workflow for ledger import and edits, deterministic
    candidate creation, review, and promotion without an artifact feedback selector.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - tests/cli/test_roadmap_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 5
  - 6
  - 7
  - 8
  - 9
  depends_on_notes:
    2: Provides the enrollment compatibility boundary; legacy feedback remains blocked
      until step 6 records explicit migration completion.
    5: Provides selector-free candidate creation and its no-work, failure, and stored
      outcomes.
    6: Provides legacy import and the reviewer-facing ledger mutations.
    7: Keeps enrolled decision settlement on the ledger authority.
    8: Provides the batch-bound review, rejection, and discard commands reported after
      candidate storage.
    9: Provides the exact promotion behavior exercised by the end-to-end CLI path.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/10-route-selector-free-feedback-commands.md
  status: done
- id: 11
  title: Document the ledger-to-candidate workflow and remove ordinary embedded-feedback
    and selector guidance
  intent: Give operators and future implementers one discoverable contract for ledger
    ownership, migration, batching, review, promotion, compatibility, and failure
    preservation.
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - README.md
  - CAPABILITIES.md
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - docs/cli/roadmap.md
  - docs/how-to/roadmap.md
  - tests/test_roadmap_format.py
  creates:
  - ROADMAP_FEEDBACK_FORMAT.md
  - tests/test_roadmap_feedback_format.py
  complexity: high
  change_type: non-code
  depends_on:
  - 10
  depends_on_notes:
    10: Provides the final command syntax, compatibility fences, terminal outcomes,
      and complete shipped workflow the references must describe.
  detail: docs/implementation-plans/plan-details/roadmap-versioned-feedback-revision-chain/11-document-ledger-candidate-workflow.md
  status: done
---
# Roadmap Versioned Feedback Revision Chain

## Overview

This plan moves roadmap feedback out of immutable artifact versions and into one reviewer-owned, roadmap-scoped ledger. Reviewers can edit and submit feedback without amending an accepted artifact, while an ordinary feedback run snapshots eligible reviewer input and current roadmap-derived context into one exact batch that produces an inert candidate revision. Guarded root enrollment, exact review-seal promotion, and enrolled decision settlement are the only accepted-head writers; none rewrites reviewer feedback.

## Problem statement

The current format embeds mutable feedback in roadmap artifacts, so adding or reopening a request rewrites an artifact that should remain immutable. The candidate lifecycle also binds one `ARTIFACT:FEEDBACK_ID` selector for a roadmap lifetime even though ordinary work needs a deterministic batch of submitted requests. The design needs separate reviewer-facing mutable input and model-facing immutable artifact content, joined by exact batch evidence without making either channel silently authoritative for the other.

## Architecture

Keep explicit root enrollment and `AcceptedRoadmapHead` as the authority for canonical artifact content. Guarded root enrollment creates the initial accepted head; exact review-seal promotion and the existing enrolled decision-settlement path are the only subsequent accepted-head writers. All use the shared guarded publication boundary. Add one explicit active-candidate pointer beside that root. Processing reads only this pair: the accepted root and the active candidate, when present. `plan_tool/roadmap_versions.py` continues to own immutable version records and the accepted-head selector, while the existing candidate storage, review, promotion, and journaled publication boundary retain their ownership.

Add one canonically rendered but reviewer-mutable feedback ledger under each roadmap's managed state, outside version artifacts. Organize its human-facing sections by direct predecessor revision, with the accepted root shown in each section header and the current root/active section first. The ledger distinguishes durable reviewer-created items from the current roadmap-derived set. A reviewer-created stable-id item records its target, request, reviewer-controlled state, proposed response when applicable, submitted-against predecessor, and admitted target fingerprint. Its closed vocabulary includes `open`, `awaiting-review`, `deferred`, and retained `closed`: a closed item keeps its stable id and current fields, is never eligible, and may later be reopened or retargeted as that same mutable item. An `open` item is eligible only when its target resolves with that fingerprint in its processing source; absent or changed targets remain unchanged and ineligible until a reviewer retargets, defers, or closes them. Closing, reopening, retargeting, and editing are ordinary mutable ledger operations on the same item; retargeting moves that item to the new predecessor section. Immutable candidate evidence, not a frozen ledger-item history, preserves every process-observed request and target through the batch receipt's reviewer-item snapshots and the stored candidate itself. The proposed response text lives on the ledger item until a sealed replacement's evidence carries its own response patch, so a batch question cannot anchor on a response.

A reviewer edits the ledger, and a submit/validation action checks it against the current processing source before persisting canonical bytes. Reopening an `awaiting-review` item, or editing its request or target, clears its live proposal fields and makes it `open`; closing any item clears those fields and makes it `closed`. These reviewer actions never alter an existing candidate, review, or active pointer. Rejection and discard likewise leave the ledger item unchanged: its recorded proposal remains visible but stale because its candidate has left the processing pair, until the reviewer reopens, retargets, or closes it. Deleting a roadmap-derived item removes it from later regeneration context; closing or deferring it does not. Selector-free `--revise-feedback` returns deterministic `no-work` without a backend call or write only when it has zero eligible reviewer-created `open` items and zero nondeleted current roadmap-derived items; otherwise it snapshots both inputs in stable order with the root-and-active-candidate pair. The direct source is the accepted root when no active candidate exists, and the active candidate when one exists. Every candidate records both `root_version_id` and `source_revision_id`; validation walks source ancestry back to the declared root and refuses any disagreement. The batch identity binds both ids, the canonical ledger digest, ordered immutable reviewer item snapshots, and derived context. At storage, the digest remains immutable evidence of the model input, not a whole-ledger equality precondition: the guard rechecks the processing pair and each admitted reviewer snapshot only. Retry, review, and promotion do not recompute batch evidence from later ledger edits.

Reopening any retained ineligible reviewer-created state (`awaiting-review`, `deferred`, or `closed`), or editing that item's request or target, clears its live proposal fields and makes it `open`. This is the only return-to-eligibility transition; immutable candidate evidence remains unchanged.

Derived context is selected only from the current direct source: the active
candidate when one exists, otherwise the accepted root. Each source owns its
own revision-bound derived set, which may be empty. Successful successor
storage selects the successor's set; promotion selects that same set through
the newly accepted root. Rejection, discard, and affirmed settlement release
the active candidate and immediately restore the accepted root's set; they
never retain context from the released candidate.

Successful candidate storage creates the model proposal: under the same guarded operation that stores candidate evidence, every admitted reviewer-created item moves from `open` to `awaiting-review`, records its proposed response, and records the immutable candidate revision id that produced it. The candidate also stores a fresh, complete roadmap-derived feedback set for its own revision. That set replaces the prior current derived set without carrying prior derived items forward; prior sets remain immutable candidate evidence for later orchestration-layer comparison. That same atomic write publishes the stored candidate as the active candidate for its declared root. A proposal is current only while its bound candidate revision is one member of the current processing pair: the accepted root or the active candidate. It becomes stale when supersession, rejection, discard, or an independent accepted-head change leaves its bound revision outside that pair. Existing reviewer-created awaiting-review, deferred, and closed items outside the admitted batch remain byte-for-value unchanged by that storage operation. Later reviewer edits clear live proposal fields as defined above and never mutate immutable candidate evidence. Failed, rejected, and interrupted attempts before candidate storage leave the ledger, accepted head, active-candidate pointer unchanged.

Derived-set replacement performs no matching, omission check, or warning. The
prior set remains only immutable candidate evidence for optional
orchestration-layer comparison; the earlier non-carry-forward statement does
not require a comparison.

Creating a successor from the active candidate replaces only the active-candidate pointer after the successor has stored successfully. A sealed review replacement is also a successor: its immediate reviewed predecessor is its `source_revision_id`, while its retained original batch records the predecessor's original source separately. It atomically replaces that candidate as active and owns a fresh derived feedback set for the replacement revision. The former active candidate, its batch, reviews, proposals, and derived set remain immutable history marked `superseded`; the explicit root/active pair makes that status informational rather than a second processing selector. A review rejection automatically records a terminal rejected resolution, releases the active-candidate pointer, and preserves that candidate and its proposals as historical stale evidence. An operator may invoke the same candidate-lifecycle owner through an explicit discard command to record a discarded resolution and release an active candidate that will not enter review. Promotion advances only the artifact head, clears the active-candidate pointer, and never rewrites reviewer feedback. Reviewer ledger edits remain allowed throughout, and an ordinary batch may use the active candidate as its direct source to create a superseding successor; no second concurrent candidate is permitted.

A sealed review replacement carries its predecessor's live awaiting-review items and proposed responses into the replacement revision, rebinding their live proposal provenance to that replacement while retaining the predecessor's immutable evidence. A feedback run returns `no-work` only when it has neither an eligible reviewer-created item nor nondeleted current roadmap-derived context.

When enrolled decision settlement would move the accepted root while an active candidate exists, the first request returns a structured `confirmation-required` result without a write. It includes the exact root, active-candidate id, and immutable facts the caller must present to the user. A CLI or web frontend submits a separate affirmative or negative response; on affirmation the writer guard rechecks that exact pair and then atomically publishes the settlement and records the active candidate as stale-resolved. A negative response changes nothing. A changed root, active candidate, or confirmation binding refuses rather than applying a stale approval. This request/response contract is non-interactive and durable enough for a containerized Integration frontend; it does not depend on terminal input or an in-memory prompt.

An affirmed settlement atomically releases the active-candidate pointer while preserving the candidate as terminal stale-resolved evidence. The new accepted root is then the only processing source until another candidate stores successfully.

New feedback-free enrollment creates a ledger-native state and may immediately use ledger routes; it is not a migrated legacy roadmap. Embedded-feedback enrollment creates a distinct legacy-pending-migration state. Migrate that state only through an explicit, idempotent ledger-import function that preserves every item and its response/state and records completion. Ledger-based candidate, review, promotion, and ordinary-feedback routes return migration-required for legacy-pending state until that record exists; they never silently migrate or fall back to embedded feedback. Enrollment blocks every old write route — stage regeneration and feedback processing alike — for the entire migration-pending window, so migration reads embedded feedback from those frozen legacy working artifacts rather than a separately preserved version. Migration never rewrites them: their embedded feedback remains frozen, non-authoritative historical content, while the ledger becomes the sole mutable feedback authority. Every version created after ledger-native enrollment or migration is feedback-free. The implementation must document the compatibility boundary for unenrolled legacy roadmaps before removing their embedded field.

## Input

Keep explicit root enrollment and `AcceptedRoadmapHead` as the only authority
for canonical artifact content. `plan_tool/roadmap_versions.py` continues to
own immutable version records and the accepted-head selector. Candidate
storage, review, and promotion retain their existing ownership and journaled
publication boundary.

## Scope guardrails

The ledger is mutable reviewer input, not canonical artifact content or an
immutable feedback-history store. `AcceptedRoadmapHead` remains the sole
canonical-artifact selector. Guarded root enrollment creates its initial value;
exact review-seal promotion and enrolled decision settlement are its only
subsequent writers. Ledger submission and review actions never enroll, advance,
or rewrite a roadmap artifact.

One candidate must bind one accepted root, one direct source, and one immutable
ledger snapshot. A candidate, review seal, or promotion cannot substitute
reviewer items, responses, target fingerprints, derived context, or ledger
bytes from a later edit. A sealed review replacement is the permitted focused
review-protocol extension: it replaces the active candidate and retains exact
root/source/batch evidence; rejection and discard are the only other lifecycle
extensions in this plan.
Candidate storage must refuse when the processing pair changes or an admitted
item no longer matches its snapshot, preserving the reviewer edit and leaving
no candidate or pointer change. The recorded whole-ledger digest is evidence,
not a refusal condition for an unrelated later edit. Promotion must not
rediscover live ledger eligibility. Conversely, a batch must not rewrite or
consume unrelated ledger items merely because they were included in a prompt.

Use the existing writer guard, durable publication, recovery, candidate store,
review store, and accepted-head writer. A ledger-specific persistence module is
permitted only as the owner of the new ledger; do not create a second version
chain, candidate store, review protocol, transaction framework, or
accepted-head authority.

## References

- [Models — Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Covers typed models, strict validation, forbidden extra fields, and immutable record configuration for ledger and snapshot schemas.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents safe YAML loading and deterministic dumping controls needed for the reviewer-edited ledger format.
- [json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Defines Python's JSON serialization options for stable ordering, compact separators, Unicode handling, and exact snapshot bytes.
- [RFC 8785: JSON Canonicalization Scheme](https://www.rfc-editor.org/rfc/rfc8785.html) — Specifies invariant JSON serialization rules for reproducible hashes and immutable batch identities.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Documents SHA-256 and byte-oriented digest APIs for ledger, artifact, fingerprint, and batch evidence.
- [os — Miscellaneous Operating System Interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Documents atomic replacement and fsync-related primitives used by durable journaled publication and recovery.
- [fcntl — The fcntl and ioctl System Calls](https://docs.python.org/3.13/library/fcntl.html) — Documents shared and exclusive advisory file locking for serializing ledger edits with candidate publication.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Structural-feedback classification, structural proposal construction, or a
  general new approve/edit/reject protocol beyond the focused review
  replacement, rejection, and discard lifecycle extensions in this plan.
- Automatic retargeting, semantic matching, grouping, splitting, or closing of
  stale feedback.
- Multiple concurrent candidate branches for one accepted head.
- Changing stage operation authority, roadmap gates, or individual candidate
  operations beyond consuming a batch snapshot and the focused replacement,
  rejection, and discard lifecycle extensions.
- Additional roadmap-derived feedback families beyond ordinary roadmap feedback.
- A general user-editing interface beyond the ledger file and focused command
  validation/mutation actions.

## Risks

The migration can create dual truth or lose a reviewer response. A mutable
ledger can drift after candidate admission, silently include an item against a
changed target, or let a promotion validate live rather than snapshotted input.
An implementation can incorrectly couple normal ledger editing to immutable
artifact publication, or allow a model response to overwrite reviewer-owned
items. The plan must establish one canonical ledger encoding, clear locking and
recovery behavior, target-fingerprint validation, exact snapshot evidence, and
failure-preservation tests before retiring embedded feedback.

## Testing

Prove that a reviewer can add feedback, retarget it, close it, or reopen a valid
awaiting-review item in the ledger without changing an accepted artifact
version. Prove `closed` retains the same item id and fields, is ineligible, and
can later reopen or retarget; closing clears live proposal fields, while
reopening or editing a pending request or target clears those fields and
restores `open`. Prove rejection and discard retain the stale proposal in the
ledger without changing the candidate's review or pointer. These mutations
affect the same ledger item while immutable candidate evidence preserves any
earlier process proposal.
Prove reopening or editing request/target from every retained ineligible
reviewer-created state (`awaiting-review`, `deferred`, and `closed`) clears live
proposal fields and restores `open` without changing candidate evidence.
Prove the predecessor-grouped ledger renders the current root/active pair
before historical groups and moves a retargeted item to its new predecessor
section. Prove new feedback-free enrollment enters ledger-native state
immediately; legacy enrollment enters pending-migration state; and explicit
migration imports embedded feedback exactly once, records completion, blocks
only the latter's ledger processing before completion, leaves no two writable
authorities, and keeps legacy embedded fields as frozen, non-authoritative
history.
Prove selector-free revision batches all and only eligible reviewer-created
`open` items whose submitted target fingerprints match the root or active
processing source, plus every nondeleted ordinary roadmap-derived item as
context, in deterministic order. Prove deletion removes a derived item from
later context while close and defer do not; stale-target, `awaiting-review`,
and `deferred` reviewer items remain in the ledger unchanged and are excluded
as appropriate.

Prove candidate proposal snapshots ledger bytes and item identities before the
model call; retry, review, and promotion use that snapshot even if the ledger
later changes. Prove every candidate declares its root and direct source, and
ancestry must resolve to that root. Prove successful first and successor storage
atomically publish their candidate as active, changes only admitted reviewer
items to awaiting-review, attaches the stored candidate revision id to every
proposal, and replaces the current derived set with a fresh revision-bound set
without matching, warning about, or carrying prior derived items.
Prove that a failed or interrupted pre-storage attempt changes neither ledger
nor pointers; a changed processing pair or edited admitted item causes storage
refusal without overwriting the edit; an unrelated edit preserves that item and
still permits storage of the exact admitted batch. Prove a rejected review or
explicit discard releases the active candidate
while preserving its proposals as stale history; and a candidate successor
supersedes rather than deletes its former active source. Prove a sealed review
replacement atomically becomes active with the reviewed candidate's exact
root/source/batch evidence and its own fresh derived set. Prove only the exact
root/active pair is processed, and a proposal is current exactly when its
candidate revision belongs to that pair; prove supersession, rejection,
discard, or independent settlement makes a proposal stale when its candidate
leaves the pair. Prove promotion never rewrites the ledger, and successful
promotion clears the active pointer and enables a later ledger batch from the
new accepted head. Prove
enrolled decision settlement with an active candidate first returns durable
confirmation-required facts, then either atomically settles and stale-resolves
the rechecked candidate after affirmative response or leaves every record
unchanged after decline or binding drift.
Prove an affirmed settlement releases the active pointer atomically with the
accepted-head change and leaves the stale-resolved candidate as history.
Prove derived context comes only from the current direct source: promotion uses
the promoted root's set, while rejection, discard, and settlement restore the
accepted root's set and never pass a released candidate's context to a later
batch.

At detail stage, enumerate every embedded-feedback parser/renderer, lifecycle
writer, candidate/review/promotion evidence consumer, CLI help/parser route,
format/data-contract section, migration reader, and regression fixture. The
implementation must either migrate or explicitly fence every legacy consumer;
no ordinary command may retain a live-artifact feedback writer.

## Acceptance criteria

- Artifact versions created after ledger-native enrollment or migration contain
  no feedback channel. A legacy version may retain its frozen,
  non-authoritative embedded feedback as historical content.
- Each enrolled roadmap has one validated, canonically rendered feedback ledger
  with per-item target provenance, reviewer-controlled mutable lifecycle state,
  and a distinction between durable reviewer-created items and current ordinary
  roadmap-derived feedback; immutable candidates preserve prior derived sets.
- Ledger `closed` is a retained, ineligible mutable state whose item can later
  reopen or retarget without losing its stable identity.
- Reopening or editing any retained ineligible reviewer-created item clears its
  live proposal and makes it open; this never changes immutable candidate
  evidence.
- Reopening an awaiting-review item, or editing its request or target, clears
  its live proposal and makes it open; closing clears it and makes it closed.
  Rejection and discard leave that ledger proposal visible but stale until a
  reviewer changes the item, without changing the resolved candidate evidence.
- New feedback-free enrollment is ledger-native; embedded-feedback enrollment
  is migration-pending and ledger routes return migration-required until the
  explicit idempotent import records completion.
- Creating or editing feedback changes only the ledger and never requires an
  immutable feedback-amendment version.
- Candidate creation uses all nondeleted ordinary roadmap-derived feedback as
  context, then replaces that revision's derived set without carrying old items
  forward, matching them, or warning about their absence. Only deletion removes
  a derived item from later context; close and defer do not.
- Derived context is the current direct source's revision-bound set only.
  Promotion preserves the promoted source's set through the new root; rejection,
  discard, and settlement restore the accepted root's set and never retain a
  released candidate's context.
- Processing considers only the explicit accepted-root and active-candidate
  pair; candidates outside that pair remain preserved history and are ignored.
- Every candidate declares both its accepted root and its direct source, and
  validated ancestry must resolve the source back to that root.
- An ordinary feedback run needs no feedback selector and snapshots every
  eligible `open` ledger item with the current root or active candidate source.
- Stale-target items are preserved and fail closed until a reviewer changes
  them; they are never silently applied to a different target.
- Candidate retry, review, and promotion bind the exact root, direct source,
  and batch snapshot rather than later ledger state.
- The whole-ledger digest records the model input but does not lock unrelated
  items: storage refuses only for a changed processing pair or admitted item;
  an unrelated edit survives unchanged and waits for a later batch.
- Candidate storage, not promotion, creates an awaiting-review proposal and
  records the immutable candidate revision that produced it.
- Successful candidate storage atomically publishes that candidate as the
  active candidate for its declared root.
- A sealed review replacement atomically becomes the active candidate with the
  reviewed candidate's exact root and batch evidence. Its direct source is the
  reviewed candidate; its original batch separately retains that candidate's
  original source, and its derived set is fresh for the replacement revision.
- A proposal remains current exactly while its bound candidate revision is the
  accepted root or active candidate. It becomes stale when supersession,
  rejection, discard, or independent settlement removes that revision from the
  root/active pair.
- A review rejection automatically resolves and releases the active candidate;
  an explicit discard command may do the same without review; candidate
  supersession preserves prior candidates as informational history.
- An ordinary batch may atomically supersede an active candidate from that
  candidate's exact source; an admitted-item edit makes storage refuse without
  overwriting the reviewer edit.
- An enrolled decision settlement with an active candidate uses a durable,
  non-interactive confirmation request/response handshake; only an affirmative
  response with unchanged bindings may atomically settle, stale-resolve it, and
  release the active-candidate pointer.
- Unrelated awaiting-review and deferred ledger items survive every candidate
  and promotion unchanged.
- Guarded root enrollment creates the initial accepted head; exact review-seal
  promotion and enrolled decision settlement are the only subsequent
  accepted-head writers. Promotion never rewrites the ledger.
- A selector-free feedback run returns the exact deterministic non-writing
  no-work result only with zero eligible reviewer-created open items and zero
  nondeleted current roadmap-derived items; otherwise it may run without a
  reviewer batch. No-work has no backend call, candidate, admission, ledger
  mutation, or head change.
- Legacy embedded-feedback and selector/live-writer vocabulary has no ordinary
  route: only migration-pending legacy processing blocks until explicit import
  records completion.

## Deferred

cannot reuse the existing recovery boundary. Defer structural workflows and
general feedback-user-interface work rather than expanding this plan around
them.
