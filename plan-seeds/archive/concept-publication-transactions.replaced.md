> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-publication-transactions.md`.
> Preserved here for history; do not edit.

# Plan seed: Concept Publication Transactions

This file is a `plan-tool create` input. Use the Codex backend and create from
this seed only after the completed `concept-decision-record-core` and
`concept-signoff-integrations` plans are present at HEAD.

Evidence source:
`docs/implementation-plans/plan-details/concept-signoff-integrations/convergence-evidence-and-split-recommendation.md`.

## Overview

Establish one all-or-recoverable publication authority for every operation that
changes a plan and its concept record. Extend the shipped concept synchronizer so
it can publish signed decisions, preserve unsigned proposal prose, replace
structured detail deferrals, and apply explicit ownership changes without
callers writing the sidecar directly. Then route create and scope-out through
that authority and make interrupted create review durable before the plan exists.

This plan owns mutation and publication ordering. It does not change how model
output is validated, define the policy for `wont_do`, or redesign split, merge,
and re-ground ownership algorithms.

## Problem statement

The completed integration plan has multiple writers for one logical state:

- `create_plan()` archives collision plans before the reviewed concept state is
  synchronized. If synchronization fails, it deletes the new plan but does not
  restore the archived prior plan.
- Signed create state uses `synchronize_concepts()`, while unsigned create state
  fingerprints and saves the sidecar directly because the synchronizer would
  erase unsigned scope prose.
- `detail` implements local deferral mutation and persistence because the core
  exposes no public deferral-replacement contract.
- `apply_narrow()` fingerprints and saves its prepared sidecar directly, so the
  narrowed plan, rendered scope sections, and concept record can diverge.
- Create review is not durably resumable when the prospective plan file does not
  yet exist, and accepted review choices are held only in memory until final
  publication.

These are not independent caller bugs. They show that the canonical writer's
request model is too narrow and that callers own transaction steps they cannot
reliably roll back. Fix the authority first; caller adoption follows.

## Reconciliation evidence to close

- `step3-run-reconcile-f405ee40` — critical create collision mutation before
  synchronization validation.
- `step3-run-reconcile-7574ef9c` — missing sidecar-only resume and durable scoped
  review progress.
- `step3-run-reconcile-80b9cde2` — unsigned proposals bypass synchronization.
- `step3-run-reconcile-e6e44173` — backend injection incorrectly affects whether
  create asks for operator approval.
- `step3-run-reconcile-9d3324a4` — missing create publication-boundary tests.
- `step4-run-reconcile-5830b0ac` — missing public deferral replacement, review,
  and synchronization contract.
- `step9-run-reconcile-e9b34ca4` — scope-out bypasses synchronization.
- `step9-run-reconcile-2b18c36e` — missing scope-out refusal and rollback tests.

## Architectural contract

### One preparation model

Expose a narrow request/result contract in or beside `plan_tool/concept_sync.py`.
A caller supplies immutable original snapshots plus a prepared target plan and
concept tree. The request identifies the mutation intent rather than asking the
synchronizer to infer it. Supported intents must include:

- signed decision publication;
- unsigned proposal persistence that preserves existing plan scope prose;
- explicit step-ownership changes;
- structured detail-deferral replacement/removal;
- scope-out's include-to-defer transitions and forward-seed publication inputs.

The API must validate the prepared relationship before changing a live artifact:
record integrity, original fingerprint/CAS provenance, target plan schema,
concept-id references, structured deferral references, approval transitions, and
the final record fingerprint derived from the bytes that will actually ship.

Do not create one permissive bag of optional fields. Use a discriminated intent,
typed helpers, or equivalently explicit request shapes so invalid combinations
fail before staging.

### One publication model

Multi-file replacement cannot be perfectly atomic on all filesystems, so the
contract is **all-or-recoverable**:

1. Capture exact original bytes/existence for every target that might change.
2. Render and validate all target bytes before touching live files.
3. Stage targets on the same filesystem where atomic replacement is possible.
4. Publish under the repository mutation lock with compare-and-swap checks.
5. Include collision archives, detail moves, forward seeds, and manifest edits in
   the rollback journal when an operation owns them.
6. On any exception, replay the journal in reverse and verify restoration.
7. If restoration itself fails, return a distinct rollback-failed result naming
   every artifact whose state is uncertain; never report ordinary rejection.

The transaction coordinator may live outside the stdlib-only concept leaf if it
needs manifest, archive, or command-layer dependencies. Keep validation/rendering
separable from the filesystem coordinator so unit tests can cover both.

### Durable create-resume state

The predicted final plan path gives create a stable sidecar location before the
plan exists. Define an explicit unsigned-resume record state that can be loaded
without pretending a finalized plan fingerprint exists. Persist each accepted
scoped review decision before moving to the next frame. A resumed create must:

- recognize compatible unsigned state and skip already accepted decisions;
- reject or explicitly resolve conflicts with changed seed/evidence inputs;
- never treat resume state as signed approval;
- preserve deterministic seeds when enrichment fails;
- fingerprint only after final plan bytes are published; and
- remove or promote resume metadata only as part of successful publication.

Terminal availability and `--yes`, not injected backend/input function identity,
determine whether approval is requested. Non-TTY and `--yes` runs may preserve
unsigned proposals but must not synthesize approval.

### Caller rule

After this plan, production callers may prepare a tree but may not directly call
`save_concepts()` for a decision-bearing update. Keep the low-level serializer
for bootstrap/tests if necessary, but make bypasses obvious and mechanically
searchable. Create, detail deferral persistence, scope review, and scope-out must
all use the public publisher.

## Proposed implementation sequence

### 1. Expand the synchronizer's typed preparation contract

Files likely involved:

- `plan_tool/concept_sync.py`
- `plan_tool/concept_tree.py`
- `plan_tool/schema.py`
- `tests/test_concept_sync.py`
- `tests/test_concept_tree.py`

Add explicit mutation intents, pure rendering/validation, unsigned-preserving
scope behavior, ownership validation, and structured deferral replacement.
Preserve the already-fixed original-tree versus reviewed-tree comparison. Pin
invalid intent combinations, stale originals, unknown concept IDs, malformed
deferral links, approval transitions, and final-byte fingerprint calculation.

### 2. Add an all-or-recoverable publication coordinator

Files likely involved:

- `plan_tool/concept_sync.py` or a narrowly named publication module
- existing archive/manifest helpers used by `plan_tool/create.py`
- `tests/test_concept_sync.py`

Stage all outputs before live mutation and add an explicit rollback journal.
Inject failure seams rather than relying on global monkeypatching of unrelated
filesystem calls. Test failures before the first write, after each replacement,
during archive/manifest operations, and during rollback. Assert exact bytes,
existence, archive placement, manifest contents, and provenance after recovery.

### 3. Make create review resumable and publish transactionally

Files likely involved:

- `plan_tool/create.py`
- `tests/test_create.py`

Load compatible sidecar-only resume state before enrichment/review, persist
accepted scoped progress, derive interactivity solely from terminal/`--yes`
state, and prepare the final plan without archiving live collisions. Validate and
stage the synchronized plan/record first; then commit collision archival, new
plan, record, renamed detail directory, and manifest as one recoverable action.
Signed and unsigned finalization must use the same authority with different
explicit intents.

### 4. Route detail deferral persistence and scope-out through the authority

Files likely involved:

- `plan_tool/detail.py`
- `plan_tool/scope_out.py`
- `tests/test_detail.py`
- `tests/test_scope_out.py`

Replace local source-metadata/save behavior with the public deferral mutation
contract. Make `apply_narrow()` publish its narrowed plan, prepared concept tree,
forward seed, detail moves, and scope prose through the recoverable coordinator.
Retain compute/apply separation and keep blocked, declined, dry-run, stale,
malformed, and legacy-no-sidecar paths non-mutating.

### 5. Document the single-writer and recovery contract

Files likely involved:

- `DATA_CONTRACT.md`
- `RUNBOOK.md`
- `TESTING.md`
- `CLAUDE.md`

Document mutation intents, unsigned resume state, publication ordering,
rollback-failed diagnostics, failure injection, and the ban on direct
decision-bearing saves. Update data-contract documentation only for persisted
shape changes actually introduced by the implementation.

## Out of scope

- Evidence grounding and malformed-Unicode behavior in concept enrichment.
- Mandatory structured-response parsing and detail-body replacement mechanics.
- Whether `wont_do` requires a structured accounting link.
- Split/merge/re-ground ownership or deferral-link transformation policy.
- Automatic recovery after a rollback itself fails; the command must stop and
  report exact uncertain paths.
- A general repository transaction framework unrelated to concepts.

## Risks and controls

- **Over-general transaction abstraction:** keep the coordinator bounded to the
  known concept publication artifacts and intents.
- **False atomicity claims:** use “all-or-recoverable,” test rollback failure, and
  report uncertainty honestly.
- **Resume state mistaken for approval:** unsigned resume carries no approval and
  only interactive confirmation can create it.
- **Collision path drift:** derive and lock final paths before staging; re-check
  compare-and-swap provenance immediately before commit.
- **Caller bypass persists:** add a focused test or static assertion enumerating
  permitted `save_concepts()` call sites.
- **Cross-plan overlap:** this plan supplies persistence APIs to the authoring and
  lifecycle plans but must not absorb their validation/accounting policy.

## Testing matrix

- Signed create, unsigned non-TTY create, `--yes`, and interactive create.
- Sidecar-only resume with unchanged inputs, changed evidence, stale finalized
  state, malformed state, and conflicting deterministic seeds.
- Collision replacement with failure before archive, after archive, after plan
  replacement, after sidecar replacement, during detail rename, and during
  manifest mutation.
- Synchronizer intent validation and final-byte fingerprints.
- Detail deferral add/replace/remove through the public authority.
- Scope-out with surviving owner, sole owner, no sidecar, stale/malformed record,
  blocked/declined/dry-run, plan failure, sidecar failure, detail failure, seed
  failure, and rollback failure.
- A source scan proving production decision-bearing callers do not bypass the
  authority.

## Acceptance criteria

- Create cannot archive or alter an existing plan unless the replacement plan
  and concept record have already passed synchronization validation.
- Any failed create publication restores the old plan, detail directory,
  sidecar, archive state, and manifest byte-for-byte, or reports a distinct
  rollback failure with exact uncertain paths.
- Compatible sidecar-only create state resumes accepted review progress without
  creating approval; conflicts stop or require explicit resolution.
- Signed and unsigned create finalization both use the public publication API.
- Detail and scope-out no longer directly save decision-bearing concept trees.
- Scope-out keeps plan scope prose, sidecar, forward seed, details, and
  fingerprint synchronized through success and rollback.
- Interactivity depends only on terminal/`--yes` state.
- Focused tests, the full suite, data-contract drift checks, and
  `reconcile-code` pass with no publication-authority redirect.

## Deferred

- Concept authoring/output validation is owned by
  `concept-authoring-boundary-hardening`.
- Lifecycle accounting and structural deferral conservation are owned by
  `concept-ownership-lifecycle-accounting`.

