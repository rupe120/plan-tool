> **Replaced 2026-08-31:** this seed has been superseded by
> `plan-seeds/roadmap-conversational-feedback.md`, whose former branch-local
> #325 route is now retired. Closed `BACKLOG.md` #328 supersedes it. Preserved
> here for history; do not edit.

# Plan seed: Roadmap Cross-Artifact Revision Transaction

## Outcome

After a current structural-escalation receipt and a current
`cross-artifact` impact-routing analysis demonstrate that one selected feedback
item requires more than one canonical roadmap artifact, `plan-tool roadmap`
will revise the deterministically declared artifact closure through a bounded,
typed patch session. It will build and validate every candidate before changing
canonical files, persist sufficient recovery evidence, invalidate derived seed
state before the first canonical replacement, and either publish the complete
gate-valid closure or recover every participating artifact to its pre-session
bytes.

The backend receives only the selected feedback, the impact-analysis-declared closure,
and the bounded artifact slices needed for each typed patch. It never decides
which artifacts are writable, performs broad `--from-stage` authoring, or
returns whole roadmap documents.

## Admission criteria

Do not materialize this seed merely because it exists. It becomes actionable
only when all of the following are true:

1. `roadmap-structural-revision-escalation` is implemented and an operator has
   a current closed-version receipt for a selected open feedback row; its
   target/source binding has been revalidated by impact routing.
2. `roadmap-escalation-impact-routing` is implemented and a current analysis
   classifies that receipt as `cross-artifact`.
3. A separately verified generic candidate-aware structural-operation and
   single-artifact publisher contract exists. The rewrite-only
   `roadmap-same-artifact-structural-revision` workflow deliberately preserves
   identities and relations, so it is not a general patch language this
   transaction may widen or reuse for creation, removal, ordering, or relation
   changes.
4. The analysis records a deterministic, inspectable relation closure involving
   more than one canonical artifact. A vague concern that an artifact “might”
   be related is not evidence for a multi-file writer.
5. The operator explicitly chooses this transaction after reviewing its exact
   planned write set, context accounting, and recovery model. No local or
   escalation command may silently promote itself into this mode.

## Why this is separate work

The original incremental-revision intent included affected-collection planning
and complete publication. The delivered local path correctly narrowed that to
one atomically replaceable artifact, and the same-artifact structural follow-on
preserves that simple failure boundary for the next common feedback shape.
Cross-artifact revisions introduce a qualitatively different problem: ordinary
filesystem replacement cannot atomically expose several files. A correct
implementation needs deterministic closure calculation, candidate-set gates,
durable preimages, crash recovery, reader/writer coordination, and a defined
relationship to the seed-state sidecar. It must therefore not be an option flag
or a hidden loop inside either earlier revision command.

## Decisions this seed settles (the plan must not re-open them)

1. **One selected feedback item starts one explicit session.** A current
   escalation receipt supplies the root selector and a current impact-routing
   analysis supplies the named, ordered, finite artifact closure. The
   transaction validates those evidence artifacts rather than re-deriving scope
   from feedback or prose. It prints the full write set and refuses if either
   evidence artifact, any source digest, or the relation model is stale or
   ambiguous.
2. **Generic candidate-aware patches are separately verified and artifact-scoped.**
   Each artifact receives only the closed generic operation and publisher
   contract that a later widening request has verified. The rewrite-only
   same-artifact workflow is not reused or widened here. An artifact-specific
   request contains its current canonical slice, immutable closure summary, and
   already-validated upstream candidate summary where needed. No request
   accepts a full YAML/Markdown replacement, dynamic filename, arbitrary write
   operation, or backend-selected artifact.
3. **No canonical file changes until the complete candidate set validates.**
   Under one participating-writer guard, the runner preflights every source,
   obtains the bounded patch replies in deterministic dependency order, merges
   candidates in memory/staging, parses each candidate, and runs all relevant
   cross-artifact gates against the complete candidate set. Backend, parse,
   gate, or interrupt failure before preparation leaves canonical files and
   seed state unchanged.
4. **Publication is recoverable, not falsely described as one filesystem
   atomic operation.** Before the first canonical replacement, the session
   stores a durable journal containing the exact ordered paths, source digests,
   preimage bytes or protected preimage locations, candidate digests, and a
   state machine such as `prepared`, `publishing`, `committed`, or
   `rolled-back`. It flushes journal updates around the seed-state invalidation
   and each replacement. Every participating roadmap reader/writer detects an
   unfinished session before acting and deterministically rolls it back to the
   stored preimages; it never guesses whether a partial set is healthy.
5. **Seed correctness takes precedence over minimizing refresh.** Only after
   all candidates and the journal are durable, and before the first canonical
   artifact replacement, the runner durably invalidates the existing seed
   state using the established conservative form. The present materializer
   consumes all canonical artifact context, so this initial transaction
   invalidates all extant draft entries—not a guessed per-plan subset. A crash
   can create safe stale drafts but cannot leave any revised artifact presented
   by a current draft.
6. **Session evidence is durable but noncanonical.** The journal and a safe
   session summary live beside the roadmap as operational evidence, linked to
   the selected feedback and source/candidate digests. They are not a fifth
   roadmap artifact, a reviewer decision, a Git checkpoint, or authority to
   close feedback. On success, only the selected feedback response transitions
   to `awaiting-review`; acceptance remains human-owned.
7. **Visibility has an explicit boundary.** Participating plan-tool commands
   provide a recovered, complete view by resolving an unfinished journal before
   reading or writing. Direct filesystem readers/writers and external tools do
   not receive a promise of a simultaneous multi-file snapshot; document this
   rather than pretending a lock changes their behavior.

## In scope

- A cross-artifact revision-session CLI surface requiring a current escalation
  receipt plus `cross-artifact` impact-routing analysis and showing the
  resolved closure, topological order, exact write set,
  context bytes/counts, and no-write confirmation before its first backend
  call.
- Deterministic closure and ownership algorithms over existing canonical
  artifact relations, including refusal of cycles, missing endpoints,
  ambiguous owner stages, stale source digests, and a relation that cannot be
  mapped to the closed structural operation language.
- Reuse of the separately verified generic candidate-aware patch contract with
  a session coordinator that builds the complete candidate set and evaluates
  both per-artifact and cross-artifact gates before publication. The
  rewrite-only workflow remains unchanged.
- A filesystem-safe session journal, staging/preimage handling, session-state
  transitions, rollback routine, and participating reader/writer recovery
  hook. Define cleanup/retention after committed or rolled-back sessions
  without deleting the evidence needed for diagnosis too early.
- Shared writer-guard ownership, conservative seed invalidation at the defined
  pre-publication point, and a clear error/recovery result for backend failure,
  rejection, interruption, crash discovery, failed replacement, and rollback
  failure.
- Redacted command/session telemetry recording root selector, closure identities
  and digests, candidate/gate verdicts, journal state transitions, seed-state
  invalidation, recovery action, and terminal outcome—never roadmap prose,
  feedback request text, prompts, backend replies, or draft seed content.
- Documentation and fixtures showing the progression: local presentation
  revision → read-only escalation → same-artifact structural revision →
  cross-artifact session → explicit seed materialization/review/promotion.

## Out of scope / Non-goals

- Implementing this work before the admission criteria and observed relation
  closure exist.
- Automatic escalation, automatic broad-stage re-entry, arbitrary feedback
  batching, a general YAML diff engine, or a backend-defined change set.
- Revising `--from-stage` generation, its prompts/retries/timeouts, or treating
  its broader recovery behavior as this session's recovery model.
- Per-plan selective seed invalidation or changing what materialization prompts
  consume; a later evidence-backed materializer-context plan may enable that.
- Git commits, branches, pull requests, worktree requirements, external
  databases, real-time collaborative editing, or a browser implementation.
- A promise that arbitrary shell processes or raw filesystem readers observe an
  all-files-at-once snapshot.

## Allowed behavior changes

- An operator can intentionally revise a validated, relation-declared set of
  canonical artifacts from one selected feedback item without broad stage
  regeneration.
- A completed session updates only the impact-analysis-declared artifact closure and
  selected feedback response; a failed or recovered session leaves the closure
  at its recorded pre-session bytes and leaves seed state safely stale only
  after the defined invalidation point.
- Participating roadmap commands can block or recover an unfinished session
  before proceeding, rather than consuming a known partial publication.

## Allowed reorganization

Extract only the generic candidate-aware patch, candidate-gate,
impact-analysis/closure, writer-guard, and roadmap read-boundary helpers this
transaction needs. Do not widen the rewrite-only workflow or rewrite canonical
schemas, broad generation, seed materialization, or unrelated CLI logging to
force a common framework.

## Verification

- A fixture with one impact-analysis-declared two- or three-artifact closure produces
  per-artifact bounded requests, validates each candidate and the complete set,
  invalidates seed state before the first replacement, and commits the ordered
  journal to `committed`. Unselected artifacts, feedback, prose, seed drafts,
  and plan-seeds remain byte-for-byte unchanged.
- Candidate construction rejects a patch addressed to a non-closure artifact,
  an operation that broadens a typed patch, a stale/missing receipt or impact
  analysis, changed
  source digest, relation cycle, unknown endpoint, or incomplete candidate set
  before seed invalidation and publication.
- Inject failures at every journal transition and canonical replacement. A new
  participating command recovers to the exact preimage set, reports the
  recovery, and cannot continue against a partially published closure. Test
  rollback failure as a distinct blocking outcome that preserves journal
  evidence rather than continuing.
- Interleavings prove that broad authoring, local revision, structural
  single-artifact revision, materialize/refresh/accept/apply, and participating
  roadmap views cannot derive work from a session baseline while its guard is
  held or journal remains unfinished.
- Existing local revision, escalation, rewrite-only same-artifact structural
  revision, seed workflows, and broad `--from-stage` retain their documented
  behavior.
  Run unit/CLI suites backend-free and one opt-in disposable-repository smoke;
  never trial an unproven transaction on the canonical Integration roadmap.

## Stop / defer

If no real request establishes the generic candidate-aware operation contract
and a multi-artifact closure, keep this seed dormant. A rewrite-only
one-artifact request is not that evidence. If atomic/recoverable multi-file
publication cannot be made correct with the repository's supported filesystem
and participating command boundaries, stop and surface that platform decision;
do not fall back to sequential live writes or a hidden broad re-entry.
