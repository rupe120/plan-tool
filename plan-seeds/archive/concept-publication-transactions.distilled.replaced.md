> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-publication-transactions.md`.
> Preserved here for history; do not edit.

## Overview

Establish one all-or-recoverable publication authority for every operation that changes a plan and its concept record. Extend the concept synchronizer to publish signed decisions, preserve unsigned proposal prose, replace structured detail deferrals, and apply explicit ownership changes without direct sidecar writes by callers. Route create, detail deferral persistence, scope review, and scope-out through that authority, while making create review durable before the plan exists. Keep validation and rendering separate from the filesystem coordinator, and report exact uncertain paths if rollback itself fails.

## Problem statement

`create_plan()` can archive collision plans before synchronization succeeds, then delete the new plan without restoring the archived plan after failure. Signed create uses `synchronize_concepts()`, but unsigned create fingerprints and saves the sidecar directly because the synchronizer erases unsigned scope prose. `detail` locally mutates and persists deferrals because no public deferral-replacement contract exists, while `apply_narrow()` directly saves its prepared sidecar, allowing the narrowed plan, rendered scope sections, and concept record to diverge.

Create review also cannot resume durably when the prospective plan file does not exist: accepted review choices remain in memory until final publication. Approval prompting is incorrectly affected by backend injection rather than terminal availability and `--yes`. These failures share one cause: the canonical writer's request model is too narrow, leaving callers responsible for publication steps they cannot reliably roll back.

## Architecture

Expose a narrow request/result contract in or beside `plan_tool/concept_sync.py`. Callers provide immutable original snapshots plus a prepared target plan and concept tree, using a discriminated intent, typed helpers, or equivalently explicit request shapes. Supported intents cover signed decision publication, unsigned proposal persistence that preserves existing plan scope prose, explicit step-ownership changes, structured detail-deferral replacement/removal, and scope-out include-to-defer transitions with forward-seed publication inputs. Invalid intent combinations must fail before staging.

Before changing live artifacts, validate record integrity, original fingerprint/CAS provenance, target plan schema, concept-id references, structured deferral references, approval transitions, and the final record fingerprint derived from the bytes that will ship. Keep validation and rendering separable from filesystem coordination so they remain independently testable. Preserve the corrected original-tree versus reviewed-tree comparison.

Use an all-or-recoverable publication coordinator: capture exact original bytes and existence, render and validate every target, stage targets on the same filesystem, then publish under the repository mutation lock with compare-and-swap checks. The rollback journal covers collision archives, detail moves, forward seeds, manifest edits, and every other artifact owned by an operation. On failure, replay the journal in reverse and verify restoration; if restoration fails, return a distinct rollback-failed result naming every uncertain artifact. The coordinator may sit outside the stdlib-only concept leaf when manifest, archive, or command-layer dependencies require it, but remains limited to concept publication artifacts and intents.

Use the predicted final plan path as a stable sidecar location for create before the plan exists. Define an explicit unsigned-resume record that does not pretend a finalized plan fingerprint exists, and persist each accepted scoped review decision before advancing. Resume only compatible unsigned state, skip accepted decisions, stop or explicitly resolve changed seed/evidence conflicts, preserve deterministic seeds when enrichment fails, and never treat resume state as approval. Compute the fingerprint only after final plan bytes are published, and remove or promote resume metadata only in the successful publication transaction.

Terminal availability and `--yes`, rather than injected backend or input-function identity, determine whether create requests approval. Non-TTY and `--yes` runs may preserve unsigned proposals but cannot synthesize approval. Production callers may prepare concept trees but may not directly call `save_concepts()` for decision-bearing updates; the low-level serializer may remain for bootstrap/tests if bypasses stay obvious and mechanically searchable.

## Out of scope

- Evidence grounding and malformed-Unicode behavior in concept enrichment — owned elsewhere.
- Mandatory structured-response parsing and detail-body replacement mechanics — not part of publication authority.
- Whether `wont_do` requires a structured accounting link — policy remains outside this plan.
- Split/merge/re-ground ownership or deferral-link transformation policy — this plan does not redesign those algorithms.
- Automatic recovery after rollback itself fails — the command stops and reports exact uncertain paths.
- A general repository transaction framework unrelated to concepts — the coordinator remains bounded to concept publication.

## Risks

- **Over-general transaction abstraction** — Failure shape: the coordinator expands beyond known concept publication artifacts and intents. Severity: not stated in the seed. Mitigation: keep it bounded to those artifacts and intents. Unresolved gap: none stated.
- **False atomicity claims** — Failure shape: multi-file replacement is described as atomic even though the filesystem cannot guarantee it. Severity: not stated in the seed. Mitigation: use “all-or-recoverable,” test rollback failure, and report uncertainty honestly. Unresolved gap: restoration can itself fail.
- **Resume state mistaken for approval** — Failure shape: unsigned progress creates or implies signed approval. Severity: not stated in the seed. Mitigation: unsigned resume carries no approval, and only interactive confirmation can create it. Unresolved gap: none stated.
- **Collision path drift** — Failure shape: final paths change between preparation and publication. Severity: critical when an existing collision plan is mutated before synchronization validation. Mitigation: derive and lock final paths before staging, then re-check compare-and-swap provenance immediately before commit. Unresolved gap: none stated.
- **Caller bypass persists** — Failure shape: a production caller continues to call `save_concepts()` for a decision-bearing update. Severity: not stated in the seed. Mitigation: add a focused test or static assertion enumerating permitted `save_concepts()` call sites. Unresolved gap: low-level bootstrap/test use may remain.
- **Cross-plan overlap** — Failure shape: publication work absorbs validation or accounting policy owned by other plans. Severity: not stated in the seed. Mitigation: provide persistence APIs to the authoring and lifecycle plans without taking ownership of their policy. Unresolved gap: none stated.

## Testing

Use unit tests for preparation, validation, rendering, resume-state handling, and rollback-journal behavior; use integration coverage where command orchestration and multi-artifact publication are the behavior under test. The seed does not provide concrete test class or test-function names, so no names are invented.

- `tests/test_concept_sync.py`: cover mutation-intent validation, invalid intent combinations, stale originals, unknown concept IDs, malformed deferral links, approval transitions, final-byte fingerprint calculation, staging, failure seams after each replacement, rollback, rollback failure, and exact restoration of bytes and existence.
- `tests/test_concept_tree.py`: cover ownership validation and structured deferral replacement/removal while preserving the original-tree versus reviewed-tree comparison.
- `tests/test_create.py`: cover signed create, unsigned non-TTY create, `--yes`, interactive create, and sidecar-only resume with unchanged inputs, changed evidence, stale finalized state, malformed state, and conflicting deterministic seeds. Integration cases cover collision failure before archive, after archive, after plan replacement, after sidecar replacement, during detail rename, and during manifest mutation, asserting archive placement, manifest contents, provenance, and byte-for-byte recovery.
- `tests/test_detail.py`: cover detail deferral add, replace, and remove through the public authority.
- `tests/test_scope_out.py`: cover `apply_narrow()` with a surviving owner, sole owner, no sidecar, stale/malformed record, blocked/declined/dry-run, plan failure, sidecar failure, detail failure, seed failure, and rollback failure. Integration coverage verifies synchronized publication of the plan, concept tree, forward seed, detail moves, scope prose, and fingerprint.
- Add a focused source scan or static assertion proving production decision-bearing callers do not bypass the authority through `save_concepts()`.
- Run the focused tests, the full suite, data-contract drift checks, and `reconcile-code`; publication-authority changes must not produce a redirect.

Per-step test strategy:
1. Expand the synchronizer's typed preparation contract — tests-with-implementation for the new intents and characterization-first coverage for preserved comparison behavior.
2. Add an all-or-recoverable publication coordinator — tests-with-implementation, including injected failure seams and rollback verification.
3. Make create review resumable and publish transactionally — tests-with-implementation plus integration tests for command orchestration and multi-artifact recovery.
4. Route detail deferral persistence and scope-out through the authority — characterization-first for existing non-mutating paths, then tests-with-implementation and integration coverage for publication wiring.
5. Document the single-writer and recovery contract — artifact-appropriate verification through documentation review and data-contract drift checks.

## Acceptance criteria

- `create_plan()` cannot archive or alter an existing plan until the replacement plan and concept record pass synchronization validation, as verified in `tests/test_create.py`.
- Every failed create publication restores the prior plan, detail directory, sidecar, archive state, and manifest byte-for-byte, or returns a distinct rollback-failed result containing every uncertain path.
- Compatible sidecar-only create state resumes accepted review progress without creating approval; changed or conflicting inputs stop or require explicit resolution.
- Signed and unsigned create finalization both use the public publication API with distinct explicit intents.
- Terminal availability and `--yes` are the only inputs that determine whether approval is requested; injected backend or input-function identity has no effect.
- `detail` and `apply_narrow()` no longer directly call `save_concepts()` for decision-bearing concept trees, as proven by a focused source scan or static assertion.
- `apply_narrow()` keeps plan scope prose, the sidecar, forward seed, details, and fingerprint synchronized after success and after recoverable failure.
- Blocked, declined, dry-run, stale, malformed, and legacy-no-sidecar detail or scope-out paths remain non-mutating.
- Detail deferral add, replace, and remove operations use the public deferral mutation contract and pass `tests/test_detail.py`.
- Focused tests, the full suite, data-contract drift checks, and `reconcile-code` pass with no publication-authority redirect.

## Deferred

- Concept authoring/output validation — owned by `concept-authoring-boundary-hardening` as a separate concern.
- Lifecycle accounting and structural deferral conservation — owned by `concept-ownership-lifecycle-accounting` as a separate concern.
