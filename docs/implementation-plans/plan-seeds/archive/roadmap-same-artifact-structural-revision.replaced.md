> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-same-artifact-structural-revision.md`.
> Preserved here for history; do not edit.

# Plan seed: Roadmap Same-Artifact Structural Revision

## Outcome

`plan-tool roadmap` will turn one current structural-escalation receipt and its
one selected open feedback row into a bounded, reviewable revision of exactly
one canonical roadmap artifact. It will support explicitly typed operations on
that artifact's prose and live rows—including controlled row creation,
replacement, removal, and relationship changes—plus one proposed feedback
response. It will validate the resulting artifact and its existing read-only
upstream dependencies before atomically publishing the single artifact.

This is the next practical expansion of feedback revision: it can address a
whole-artifact request or a row request that needs a new rule, entity, flow,
decision, relation, or prose section, without re-entering every later roadmap
stage. It does not become a cross-artifact transaction, a generic document
editor, or an automatic broad `--from-stage` run.

## Why this is a separate plan

`roadmap-incremental-revision` is intentionally a narrow safety boundary: one
same-artifact row, one allowlisted presentation-field replacement, and one
feedback response. The current Integration feedback demonstrates the next distinct
shape: several requests target all of `01-domain.md`, and a row-targeted
request needs a lifecycle map made of additional rules rather than one text
field. Treating either as a local presentation edit would falsely report a
partial answer as a satisfied revision.

The existing `roadmap-structural-revision-escalation` plan supplies an
immutable, read-only receipt and current selected-source evidence first. This
seed consumes that evidence and provides the first write-capable structural
path, but keeps the write boundary at one artifact so the current local
publisher's atomic single-path guarantee remains meaningful.

## Decisions this seed settles (the plan must not re-open them)

1. **An explicit escalation receipt is required.** The command takes one
   artifact-qualified feedback selector and the semantic id/digest of a current
   version-1 escalation receipt for that selector. It revalidates the receipt's
   closed schema and duplicate-member-free JSON, shared selector grammar,
   semantic identity, source digest, source-derived target kind/id, and the
   complete receipt-selection predicate;
   it refuses a missing, stale, source-target-mismatched,
   selection-ineligible, invalid, or non-structural receipt before seed
   invalidation or a backend call. A normal `--revise-feedback` attempt does
   not silently fall through into this mode.
2. **One artifact is the complete write set.** The selected feedback may target
   a row or the artifact, but every canonical write is confined to that
   artifact. Required upstream artifacts can be read only for existing gates;
   sibling and downstream artifacts, draft seeds, repository code, and
   unselected feedback never enter backend context or the write set.
3. **The backend returns typed operations, never a whole artifact.** The
   operation schema has closed variants for a marked prose replacement and
   create/replace/remove/reorder row operations. Every operation declares its
   row type and stable target identity where one exists. A new row carries a
   schema-valid stable ID and all relation endpoints explicitly; the
   deterministic merger rejects collisions, unrecognized row types, duplicate
   operations, inferred targets, incompatible row ordering, or anything
   outside the selected artifact. The backend may propose content, but cannot
   choose another artifact or silently widen the write set.
4. **Preservation is explicit.** Rows, removals, feedback, decisions, prose
   segments, and accepted serialized data absent from an allowed operation stay
   unchanged. Before any mutation work, the artifact must pass the same
   render-canonical preflight used by local revision; opaque or lossy input is
   rejected rather than normalized away.
5. **Feedback remains reviewer-owned.** The reply contains exactly one
   `respond-feedback` operation for the selected open feedback row. A valid
   candidate can move only that row to `awaiting-review` with its proposed
   response. It cannot close feedback, alter other feedback, infer acceptance,
   or treat a generated structural change as human approval.
6. **Reuse the existing conservative state and writer guarantees.** The
   structural runner uses the shared participating-writer guard from local
   revision, invalidates existing seed state through the established durable
   pre-backend seam, and never materializes, refreshes, accepts, or promotes
   seed prose. A failed attempt may conservatively leave drafts stale; it must
   not leave changed roadmap content represented by a current derived draft.
7. **The backend context is a bounded artifact slice.** It includes the current
   receipt, selected feedback, the selected artifact's canonical prose and rows,
   immutable row/relation inventory, and the closed operation schema. It
   excludes all other artifact text and generated seeds. The command records
   context bytes/counts and one explicit backend-attempt outcome; it never
   retries by invoking broad stage authoring.

## In scope

- An exclusive structural-revision command surface, preflight, current-receipt
  verification, and clear operator output that names its one-artifact write
  set before a backend call.
- A versioned, strict operation schema and deterministic merger for the four
  canonical artifact row models and their prose boundary. Define row ordering,
  relation-endpoint, removal-history, and ID-collision rules instead of relying
  on prompt prose.
- Artifact-specific operation allowlists. The plan must identify which row
  types can be created, changed, removed, or reordered in each stage, and what
  structural gate protects each allowed relation change.
- Candidate construction, parser/gate validation, atomic one-artifact
  publication, shared writer ownership, conservative seed invalidation, and
  failure/interrupt behavior that reuse the local revision seams where their
  contracts already fit.
- Safe lifecycle evidence: selector/receipt semantic ids and digests, write-set summary,
  bounded-context counts, operation verdicts, validation/publish result, and
  termination reason; no feedback request, roadmap prose, prompt, backend
  reply, or raw seed content in logs.
- Documentation that differentiates presentation revision, structural
  same-artifact revision, escalation, and broad stage re-entry; include how a
  reviewer inspects the candidate response and explicitly accepts or reopens
  feedback through the existing lifecycle.
- Unit and CLI tests for every operation type, forbidden widening, stale receipt
  rejection, byte preservation of unmentioned content, gate failures, writer
  interleavings, sidecar invalidation, and observability. Include fixtures
  shaped like Integration's artifact-level domain feedback and row-targeted
  lifecycle-map feedback.

## Out of scope / Non-goals

- Selecting multiple feedback rows, coalescing requests, or inferring which
  feedback items are related.
- Writing more than one canonical roadmap artifact, deriving a dependency
  closure, or providing a multi-file publication/recovery protocol.
- A backend-created free-form YAML/Markdown replacement, arbitrary manual text
  editing, collaborative editing, or lossless editing of unknown extensions.
- Altering `--from-stage`, its prompts, retry/timeouts, or its broad write and
  recovery semantics.
- Per-plan selective seed invalidation, seed generation/promotion, or any
  change to materialization state semantics.
- Git checkpoints, worktree requirements, external tickets, identity changes,
  or a browser workflow.

## Allowed behavior changes

- A reviewer can request a bounded structural change to one artifact and
  receive a proposed response without re-emitting later canonical artifacts.
- A same-artifact candidate can add, revise, remove, or reorder explicit
  structural rows and allowed prose sections when the deterministic merger and
  existing gates accept it.
- Unsupported or cross-artifact feedback is rejected with a precise routing
  message, leaving canonical artifacts untouched and retaining the escalation
  evidence for a later workflow.

## Allowed reorganization

Extract shared selector, receipt-identity validation, operation-validation, candidate-gate,
or writer-guard helpers only when ownership remains clear between local and
structural single-artifact modes. Do not refactor broad stage generation,
artifact schemas, seed machinery, or readers merely to make revision modes
look uniform.

## Verification

- A current artifact-target escalation receipt for a fixture domain artifact can
  add a new rule/entity/flow and its declared relations; a current row-targeted
  receipt can add a multi-row lifecycle map. Both publish only their selected
  artifact and selected feedback response after parser and gate success.
- Each operation attempts to create an ID collision, change an unmentioned
  row, mutate an unselected feedback row, alter an upstream/sibling artifact,
  invent a relation endpoint, replace the entire document, or omit the selected
  response; every case fails before publication.
- The runner rejects stale/mismatched receipts and noncanonical input before
  invalidating seed state or contacting a backend. After accepted preflight,
  backend/parse/gate/interrupt failures leave the artifact byte-for-byte intact
  and retain only the existing conservative seed-state result.
- Existing local `--revise-feedback`, structural escalation, `--from-stage`,
  materialize/refresh/apply, and all roadmap views retain their documented
  contracts. Tests use no live backend; one disposable opt-in smoke exercises
  a real structural feedback row and verifies the event/redaction boundary.

## Stop / defer

If an observed request needs another canonical artifact, preserve the current
receipt and route it to the cross-artifact seed rather than adding a second
writer to this command. If a row type cannot be safely represented by explicit
typed operations and existing gates, stop and record the schema gap. Do not
weaken preflight, type checks, or conservative invalidation merely to make a
real feedback item pass.
