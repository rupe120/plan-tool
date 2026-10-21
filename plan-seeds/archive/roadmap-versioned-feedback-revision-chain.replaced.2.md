> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-versioned-feedback-revision-chain.md`.
> Preserved here for history; do not edit.

## Outcome

Roadmap artifacts are immutable versions and never contain mutable feedback.
Each roadmap has one reviewer-owned feedback ledger outside the artifact set.
An operator can edit and submit ledger items without amending an accepted
artifact. An ordinary feedback run snapshots the current accepted artifact
version and the eligible ledger items into one exact batch, then stores an
inert candidate revision. Exact review-seal promotion advances only the
accepted artifact head; it never rewrites the ledger.

## Problem statement

The current format embeds feedback in mutable roadmap artifacts. That makes a
new request or a reviewer reopening an existing request an artifact rewrite,
which conflicts with immutable accepted versions. It also forces the current
candidate lifecycle to bind one `ARTIFACT:FEEDBACK_ID` selector for a roadmap
lifetime, despite ordinary work needing a deterministic group of submitted
requests.

The ledger is the reviewer-facing mutable channel. Artifact versions are the
model-facing immutable content channel. A batch receipt bridges them without
making either channel silently authoritative for the other.

## Architecture

Keep explicit root enrollment and `AcceptedRoadmapHead` as the only authority
for canonical artifact content. `plan_tool/roadmap_versions.py` continues to
own immutable version records and the accepted-head selector. Candidate
storage, review, and promotion retain their existing ownership and journaled
publication boundary.

Add one roadmap-scoped feedback ledger under the roadmap's managed state, not
inside a version artifact. It is a closed, canonically rendered document with
stable item ids. A ledger item records its target, request, reviewer-controlled
state, proposed response when applicable, and the accepted version against
which the reviewer submitted or last retargeted it. The target's admitted
fingerprint makes that provenance actionable: an `open` item is eligible only
when its target still resolves with the submitted fingerprint in the current
accepted head. If the target is absent or changed, retain the item unchanged
and report it as ineligible until the reviewer retargets, defers, or closes it.

The normal path is: a reviewer edits the ledger; a submit/validation action
checks it against the current accepted head and persists its canonical bytes;
`--revise-feedback` snapshots all eligible `open` items in stable order with
that accepted head; the candidate lifecycle proposes an immutable artifact
successor; review and promotion use the snapshot evidence; the ledger remains
the same file throughout. `awaiting-review` and `deferred` items remain in the
ledger byte-for-value during candidate creation and promotion. A batch-processed
item may transition from `open` to `awaiting-review` only through the existing
model-response integrity rule, recorded in the ledger under the same guarded
operation that stores the candidate evidence. A failed, rejected, interrupted,
or unpromoted candidate leaves the ledger and accepted head unchanged.

The batch identity includes the accepted predecessor version id, canonical
ledger digest, and ordered immutable item snapshots. It is not recomputed from
later ledger edits during retry, review, or promotion. One unpromoted candidate
generation may exist for one accepted head; a ledger edit after admission waits
for that generation to finish or be explicitly resolved, then forms a later
batch against the then-current head.

Migrate the existing embedded feedback only through an explicit, idempotent
ledger-import boundary while preserving every item and its response/state. Do
not leave two writable sources of truth. Once imported for an enrolled roadmap,
candidate, review, promotion, and ordinary-feedback routes read the ledger;
the artifact feedback field is retired from immutable version content. The
plan must choose and document the compatibility boundary for unenrolled legacy
roadmaps before removing their embedded field.

## In scope

- Define, validate, render, load, and atomically publish the roadmap-scoped
  feedback ledger, including stable ids, target fingerprints, submitted-against
  version provenance, state/response rules, and exact ledger snapshots.
- Provide reviewer-facing submission, retarget, defer, close, and confirmed
  reopen operations that mutate only the ledger after validation against the
  current accepted head; new feedback is a ledger insertion, not a version
  amendment.
- Introduce an explicit idempotent migration from embedded feedback to the
  ledger at the chosen enrollment/compatibility boundary and remove dual-write
  or fallback authority once migrated.
- Make selector-free ordinary feedback derive one deterministic batch of all
  eligible `open` ledger items for the accepted head.
- Bind candidate admission, retry, candidate evidence, review questions and
  answers, and promotion to the exact artifact predecessor and ledger batch.
- Store model-proposed responses as guarded ledger changes while preserving
  unrelated `awaiting-review`, `deferred`, stale-target, and later-submitted
  items unchanged.
- Retire the ordinary live-artifact feedback writer and selector-based
  `--revise-feedback` route.
- Update format, data-contract, CLI, architecture, workflow, reference, and
  regression documentation to describe the ledger/snapshot model.

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

## Stop / defer

Stop for a focused design decision if preserving legacy unenrolled roadmap
editing requires a permanent dual-write or fallback source of truth, if target
fingerprints cannot distinguish a safe carried target from a changed one, or if
atomic coupling of candidate storage and the batch-response ledger update
cannot reuse the existing recovery boundary. Defer structural workflows and
general feedback-user-interface work rather than expanding this plan around
them.

## References

- [`ROADMAP_FORMAT.md`](../ROADMAP_FORMAT.md) — Existing feedback lifecycle,
  target schema, candidate rules, and immutable-version contract.
- [`DATA_CONTRACT.md`](../DATA_CONTRACT.md) — Persisted candidate, review, and
  publication records that must gain exact ledger-batch evidence.
- [`plan_tool/roadmap_artifacts.py`](../plan_tool/roadmap_artifacts.py) —
  Current embedded feedback schema and artifact rendering boundary.
- [`plan_tool/roadmap_candidate_context.py`](../plan_tool/roadmap_candidate_context.py)
  — Current selected-feedback context to replace with a batch snapshot.
- [`plan_tool/roadmap_candidate_run.py`](../plan_tool/roadmap_candidate_run.py)
  — Admission, retry, evidence, and inert candidate storage.
- [`plan_tool/roadmap_candidate.py`](../plan_tool/roadmap_candidate.py) —
  Candidate materialization and feedback integrity integration.
- [`plan_tool/roadmap_feedback_reopen.py`](../plan_tool/roadmap_feedback_reopen.py)
  — Existing confirmed reopen semantics to move to the ledger boundary.
- [`plan_tool/roadmap_candidate_review.py`](../plan_tool/roadmap_candidate_review.py)
  and [`plan_tool/roadmap_version_promotion.py`](../plan_tool/roadmap_version_promotion.py)
  — Existing review and promotion lineage.
