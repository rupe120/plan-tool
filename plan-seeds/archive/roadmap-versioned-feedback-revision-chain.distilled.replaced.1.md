> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`.
> Preserved here for history; do not edit.

## Overview

This plan moves roadmap feedback out of immutable artifact versions and into one reviewer-owned, roadmap-scoped ledger. Reviewers can edit and submit ledger items without amending an accepted artifact, while an ordinary feedback run snapshots the current `AcceptedRoadmapHead` and every eligible `open` item into one exact batch that produces an inert candidate revision. Exact review-seal promotion remains the only operation that advances the accepted artifact head and never rewrites the ledger.

## Problem statement

The current format embeds mutable feedback in roadmap artifacts, so adding or reopening a request rewrites an artifact that should remain immutable. The candidate lifecycle also binds one `ARTIFACT:FEEDBACK_ID` selector for a roadmap lifetime even though ordinary work needs a deterministic batch of submitted requests. The design needs separate reviewer-facing mutable input and model-facing immutable artifact content, joined by exact batch evidence without making either channel silently authoritative for the other.

## Architecture

Keep explicit root enrollment and `AcceptedRoadmapHead` as the only authority for canonical artifact content. `plan_tool/roadmap_versions.py` continues to own immutable version records and the accepted-head selector, while the existing candidate storage, review, promotion, and journaled publication boundary retain their ownership.

Add one closed, canonically rendered feedback ledger under each roadmap's managed state, outside version artifacts. Each stable-id item records its target, request, reviewer-controlled state, proposed response when applicable, submitted-against accepted version, and admitted target fingerprint. An `open` item is eligible only when its target resolves with that fingerprint in the current accepted head; absent or changed targets remain unchanged and ineligible until a reviewer retargets, defers, or closes them.

A reviewer edits the ledger, and a submit/validation action checks it against the current accepted head before persisting canonical bytes. Selector-free `--revise-feedback` snapshots all eligible `open` items in stable order with that head, after which the existing candidate lifecycle proposes an immutable successor. The batch identity binds the accepted predecessor version id, canonical ledger digest, and ordered immutable item snapshots, and retry, review, and promotion do not recompute it from later ledger edits.

`awaiting-review` and `deferred` items remain byte-for-value unchanged during candidate creation and promotion. A batch item may move from `open` to `awaiting-review` only through the existing model-response integrity rule and under the same guarded operation that stores candidate evidence. Failed, rejected, interrupted, or unpromoted candidates leave both the ledger and accepted head unchanged; one unpromoted candidate generation may exist per accepted head, so later ledger edits wait until that generation finishes or is explicitly resolved.

Migrate embedded feedback only through an explicit, idempotent ledger-import boundary that preserves every item and its response/state. Once an enrolled roadmap is migrated, candidate, review, promotion, and ordinary-feedback routes read the ledger, and the artifact feedback field is retired from immutable version content without leaving dual writable authority. The implementation must choose and document the compatibility boundary for unenrolled legacy roadmaps before removing their embedded field.

## Out of scope

- Structural-feedback classification, structural proposal construction, or a
  new approve/edit/reject protocol.
- Automatic retargeting, semantic matching, grouping, splitting, or closing of
  stale feedback.
- Multiple concurrent candidate branches for one accepted head.
- Changing stage operation authority, roadmap gates, or individual candidate
  operations except to consume a batch snapshot rather than embedded feedback.
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

Prove that a reviewer can add feedback, retarget it, or reopen a valid
awaiting-review item in the ledger without changing an accepted artifact
version. Prove explicit migration imports embedded feedback exactly once and
never leaves two writable authorities. Prove selector-free revision batches all
and only `open` items whose submitted target fingerprints match the accepted
head, in deterministic order; stale-target, `awaiting-review`, and `deferred`
items remain in the ledger unchanged and are excluded as appropriate.

Prove candidate proposal snapshots ledger bytes and item identities before the
model call; retry, review, and promotion use that snapshot even if the ledger
later changes. Prove the response transition changes only batch items and that
failure, rejection, interruption, stale predecessor, gate failure, review
failure, promotion failure, and recovery preserve the prior accepted head and
all unaffected ledger items. Prove a successful promotion enables a later
ledger batch against the new accepted head without carrying a roadmap-lifetime
selector lock.

At detail stage, enumerate every embedded-feedback parser/renderer, lifecycle
writer, candidate/review/promotion evidence consumer, CLI help/parser route,
format/data-contract section, migration reader, and regression fixture. The
implementation must either migrate or explicitly fence every legacy consumer;
no ordinary command may retain a live-artifact feedback writer.

## Acceptance criteria

- Immutable roadmap artifact versions contain no mutable feedback channel.
- Each enrolled roadmap has one validated, canonically rendered feedback ledger
  with per-item target provenance and reviewer-controlled lifecycle state.
- Creating or editing feedback changes only the ledger and never requires an
  immutable feedback-amendment version.
- An ordinary feedback run needs no feedback selector and snapshots every
  eligible `open` ledger item with the current accepted artifact head.
- Stale-target items are preserved and fail closed until a reviewer changes
  them; they are never silently applied to a different target.
- Candidate retry, review, and promotion bind the exact predecessor and batch
  snapshot rather than later ledger state.
- Unrelated awaiting-review and deferred ledger items survive every candidate
  and promotion unchanged.
- Exact review-seal promotion remains the only feedback-candidate
  accepted-head writer; promotion never rewrites the ledger.
- No eligible item returns a deterministic non-writing no-work result without
  a backend call, candidate, admission, ledger mutation, or head change.
- Legacy embedded-feedback and selector/live-writer vocabulary has no ordinary
  route after the selected compatibility migration is complete.

## Deferred

cannot reuse the existing recovery boundary. Defer structural workflows and
general feedback-user-interface work rather than expanding this plan around
them.

## Input

Keep explicit root enrollment and `AcceptedRoadmapHead` as the only authority
for canonical artifact content. `plan_tool/roadmap_versions.py` continues to
own immutable version records and the accepted-head selector. Candidate
storage, review, and promotion retain their existing ownership and journaled
publication boundary.

## Scope guardrails

The ledger is mutable reviewer input, not canonical artifact content.
`AcceptedRoadmapHead` remains the sole canonical-artifact selector. Only exact
review-seal promotion advances it. Ledger submission and review actions never
enroll, promote, or rewrite a roadmap artifact.

One candidate must bind one accepted predecessor and one immutable ledger
snapshot. A candidate, review seal, or promotion cannot substitute items,
responses, target fingerprints, or ledger bytes from a later edit. Promotion
must not rediscover live ledger eligibility. Conversely, a batch must not
rewrite unrelated ledger items or consume them merely because they were
included in a prompt.

Use the existing writer guard, durable publication, recovery, candidate store,
review store, and accepted-head writer. A ledger-specific persistence module is
permitted only as the owner of the new ledger; do not create a second version
chain, candidate store, review protocol, transaction framework, or
accepted-head authority.
