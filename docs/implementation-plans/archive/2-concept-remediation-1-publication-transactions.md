---
title: Concept Remediation 1 — Publication Transactions
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Centralize concept change preparation
  files:
  - plan_tool/concept_sync.py
  - plan_tool/detail.py
  - plan_tool/scope_out.py
  - tests/test_concept_sync.py
  - tests/test_concept_tree.py
  - tests/test_detail.py
  - tests/test_scope_out.py
  complexity: high
  change_type: refactor
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/01-centralize-concept-change-preparation.md
  status: current
- id: 2
  title: Add typed concept publication intents
  files:
  - plan_tool/concept_sync.py
  - plan_tool/concept_tree.py
  - tests/test_concept_sync.py
  - tests/test_concept_tree.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/02-typed-concept-publication-intents.md
- id: 3
  title: Add all-or-recoverable concept publication
  files:
  - plan_tool/concept_sync.py
  - plan_tool/cli/app.py
  - plan_tool/cli/publication_recovery_cmd.py
  - plan_tool/repo_lock.py
  - tests/test_concept_sync.py
  - tests/cli/test_app_lock.py
  - tests/cli/test_publication_recovery_cmd.py
  - tests/test_repo_lock.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/03-all-recoverable-concept-publication.md
- id: 4
  title: Publish scope reviews through the new authority
  files:
  - plan_tool/cli/scope_review_cmd.py
  - tests/cli/test_scope_review_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/04-publish-scope-reviews-through-new.md
- id: 5
  title: Make create concept review resumable and terminal-driven
  files:
  - plan_tool/concept_tree.py
  - plan_tool/create.py
  - plan_tool/data_contract.py
  - DATA_CONTRACT.md
  - tests/test_concept_tree.py
  - tests/test_create.py
  - tests/test_data_contract.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/05-make-create-concept-review-resumable.md
- id: 6
  title: Prepare create publication as one artifact bundle
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: refactor
  depends_on:
  - 5
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/06-prepare-create-publication-one-artifact.md
- id: 7
  title: Publish create results through the concept authority
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 6
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/07-publish-create-results-through-concept.md
- id: 8
  title: Have detail generation return prepared writes
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: refactor
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/08-have-detail-generation-return-prepared.md
- id: 9
  title: Publish detail files and deferrals together
  files:
  - plan_tool/detail.py
  - tests/test_detail.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 8
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/09-publish-detail-files-deferrals-together.md
- id: 10
  title: Extract scope-out publication preparation
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  complexity: high
  change_type: refactor
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/10-extract-scope-out-publication.md
- id: 11
  title: Publish scope-out changes transactionally
  files:
  - plan_tool/scope_out.py
  - plan_tool/cli/scope_out_cmd.py
  - plan_tool/cli/convergence_cmd.py
  - tests/test_scope_out.py
  - tests/cli/test_scope_out_cmd.py
  - tests/cli/test_convergence_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 10
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/11-publish-scope-out-changes.md
- id: 12
  title: Block direct production concept writes
  files:
  - tests/test_concept_sync.py
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  - 7
  - 9
  - 11
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/12-block-direct-production-concept-writes.md
- id: 13
  title: Document concept publication and recovery
  files:
  - CLAUDE.md
  - RUNBOOK.md
  complexity: low
  change_type: non-code
  depends_on:
  - 12
  detail: docs/implementation-plans/plan-details/concept-remediation-1-publication-transactions/13-document-concept-publication-recovery.md
---
# Concept Publication Transactions

## Overview

Establish one all-or-recoverable publication authority for every operation that changes a plan and its concept record. Extend the concept synchronizer to publish signed decisions, preserve unsigned proposal prose, replace structured detail deferrals, and apply explicit ownership changes without direct sidecar writes by callers. Route create, detail deferral persistence, scope review, and scope-out through that authority, while making create review durable before the plan exists. Keep validation and rendering separate from the filesystem coordinator, and report exact uncertain paths if rollback itself fails.

## Problem statement

`create_plan()` can archive collision plans before synchronization succeeds, then delete the new plan without restoring the archived plan after failure. Signed create uses `synchronize_concepts()`, but unsigned create fingerprints and saves the sidecar directly because the synchronizer erases unsigned scope prose. `detail` locally mutates and persists deferrals because no public deferral-replacement contract exists, while `apply_narrow()` directly saves its prepared sidecar, allowing the narrowed plan, rendered scope sections, and concept record to diverge.

Create review also cannot resume durably when the prospective plan file does not exist: accepted review choices remain in memory until final publication. Approval prompting is incorrectly affected by backend injection rather than terminal availability and `--yes`. These failures share one cause: the canonical writer's request model is too narrow, leaving callers responsible for publication steps they cannot reliably roll back.

## Architecture

Expose a narrow request/result contract in or beside `plan_tool/concept_sync.py`. Callers provide immutable original snapshots plus a prepared target plan and concept tree, using a discriminated intent, typed helpers, or equivalently explicit request shapes. Supported intents cover signed decision publication, unsigned proposal persistence that preserves existing plan scope prose, explicit step-ownership changes, structured detail-deferral replacement/removal, and scope-out include-to-defer transitions with forward-seed publication inputs. Invalid intent combinations must fail before staging.

Before changing live artifacts, validate record integrity, original fingerprint/CAS provenance, target plan schema, concept-id references, structured deferral references, approval transitions, and the final record fingerprint derived from the bytes that will ship. Keep validation and rendering separable from filesystem coordination so they remain independently testable. Preserve the corrected original-tree versus reviewed-tree comparison.

Use an all-or-recoverable publication coordinator: capture exact original bytes and existence, render and validate every target, compute the sidecar fingerprint from the fully rendered staged plan bytes plus the final ordered detail set, and stage all targets on the same filesystem before live mutation. The typed request contract represents file replacements, creations/removals, directory moves, manifest edits, archive actions, and read-only fingerprint inputs explicitly; it remains bounded to concept-publication operations rather than becoming a general transaction API. A directory move carries a deterministic recursive tree manifest of every relative path, entry type, file digest, and symlink target without following links; unsupported special entries are rejected. Compare-and-swap every file target, complete directory-tree manifest, required source/destination absence, and unchanged fingerprint input immediately before its commit operation. After publication, verify that the entire live bundle matches the staged generation whose fingerprint was recorded. On failure, replay the journal in reverse only while transaction-produced file and tree manifests still match, then verify exact restoration; if restoration fails or external descendant drift prevents safe reversal, return a distinct rollback-failed result naming every uncertain artifact.

Make the rollback journal durable before the first live replacement. Persist the operation id, original and staged paths, original existence/digests, ordered operations, and completion markers under a transaction-specific `.plan-tool` recovery path; fsync staged files, journal updates, and affected parent directories at the documented durability boundaries. Definitely mutating commands recover before dispatch, while dry runs do not recover. Interactive/blockable commands defer recovery until immediately before their first actual write: a decline before that boundary is byte-for-byte non-mutating, but create concept review crosses the boundary before its first durable unsigned resume save, so later approval decline intentionally retains that reviewed progress without publishing plan or concept authority. The explicit operator recovery command is the sole dispatch exemption: it acquires the mutation lock but bypasses ordinary automatic recovery so its handler can inspect and resolve the selected `operator_required` transaction instead of being blocked by that marker. Before another concept publication begins, detect an incomplete journal and either finish a provably staged generation or replay a provably recoverable original generation. A journal marked rollback-failed or containing contradictory evidence is operator-owned: normal commands block and report its exact uncertain paths without choosing a generation. Step 3 also implements that explicit locked recovery command, which applies an operator-selected original or staged generation only when every source digest remains available, verifies the result, and then clears the marker. Abrupt process/host termination tests use a subprocess boundary and inspect restart recovery rather than relying only on caught exception injection. Remove durable recovery state only after final-byte verification and directory durability complete.

The mutating CLI dispatch remains the owner of `repo_mutation_lock`; step 3 changes dispatch to retain the yielded token and expose an explicit lock-ownership capability through scoped command context to every publishing core. The coordinator must not reacquire that non-reentrant lock. Expose a direct-call wrapper that acquires the lock before invoking the same core. Tests must prove nested acquisition is absent, effective-mutation recovery ordering respects dry-run and decline gates, and unguarded direct publication is rejected or routed through the wrapper.

Store pre-publication create review under a dedicated resume namespace such as `.plan-tool/create-resume/<slug>/`, keyed by the prospective plan identity and seed/evidence digest, rather than at `concepts_path(predicted_plan_path)`. The resume path must never alias or overwrite an incumbent collision plan's `plan-details/<slug>/concepts.json`. Define an explicit unsigned-resume record that does not pretend a finalized plan fingerprint exists, and persist each accepted scoped review decision before advancing. Each acknowledged save flushes the file and fsyncs its parent-directory entry before the next prompt. Resume only compatible unsigned state, skip accepted decisions, stop or explicitly resolve changed seed/evidence conflicts, preserve deterministic seeds when enrichment fails, and never treat resume state as approval. During staging, compute the record fingerprint from the final rendered plan bytes; promote the resume state to the final sidecar only inside the successful publication transaction.

Terminal availability and `--yes`, rather than injected backend or input-function identity, determine whether create requests approval. Non-TTY and `--yes` runs may preserve unsigned proposals but cannot synthesize approval. Production callers may prepare concept trees but may not persist decision-bearing updates through `save_concepts()`, its `write_concepts` alias, raw writes to `concepts_path()`, or equivalent filesystem helpers; the low-level serializer may remain for bootstrap/tests if permitted call sites are explicit and mechanically enforced.

## References

- [Python 3.13 os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Documents os.replace, fsync, file metadata, and isatty semantics needed for staged publication, durability, CAS checks, and terminal detection.
- [Python 3.13 tempfile — Generate temporary files and directories](https://docs.python.org/3.13/library/tempfile.html) — Covers secure same-directory temporary files used to stage publication artifacts before replacement.
- [POSIX.1-2024 Rationale — File-system atomicity and durability](https://pubs.opengroup.org/onlinepubs/9799919799/xrat/V4_xbd_chap01.html) — Explains why atomic directory operations are not necessarily durable and describes the fsync-then-rename update pattern.
- [Python 3.13 fcntl — File locking interfaces](https://docs.python.org/3.13/library/fcntl.html) — Documents flock and lockf behavior for coordinating publication under a repository mutation lock on Unix.
- [Pydantic — Unions and discriminated unions](https://pydantic.dev/docs/validation/latest/concepts/unions/#discriminated-unions) — Shows how to model and validate explicit tagged publication intents while rejecting incompatible request shapes.
- [Python hashlib — Secure hashes and message digests](https://docs.python.org/3/library/hashlib.html) — Provides the SHA-256 byte-digest APIs needed for final-byte fingerprints and compare-and-swap provenance.
- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Covers controlled dependency and failure-seam injection for rollback, filesystem, terminal, and orchestration tests.

## Steps

See the `steps:` block in the frontmatter.

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
- Add a focused source scan or static assertion proving production decision-bearing callers do not bypass the authority through `save_concepts()`, `write_concepts`, raw writes to `concepts_path()`, or equivalent filesystem helpers.
- Run the focused tests, the full suite, data-contract drift checks, and `reconcile-code`; publication-authority changes must not produce a redirect.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 9 (feature) — unit tests added with the implementation; green before completion.
- step 10 (refactor) — characterization tests pinned before the change; pass unchanged after.
- step 11 (feature) — unit tests added with the implementation; green before completion.
- step 12 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 13 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `create_plan()` cannot archive or alter an existing plan until the replacement plan and concept record pass synchronization validation, as verified in `tests/test_create.py`.
- Every failed create publication restores the prior plan, detail directory, sidecar, archive state, and manifest byte-for-byte, or returns a distinct rollback-failed result containing every uncertain path.
- An abrupt process or host stop between live replacements leaves a durable incomplete journal; the next command recovers or completes the bundle before accepting another publication, and removes the journal only after staged/live byte verification and required directory fsyncs.
- Compatible sidecar-only create state resumes accepted review progress without creating approval; changed or conflicting inputs stop or require explicit resolution.
- Create resume state uses a dedicated path that cannot alias an incumbent collision plan's sidecar, and promotion to the final `concepts.json` occurs only inside successful publication.
- Signed and unsigned create finalization both use the public publication API with distinct explicit intents.
- Terminal availability and `--yes` are the only inputs that determine whether approval is requested; injected backend or input-function identity has no effect.
- Scope review publishes the reviewed record and rendered plan sections together; successful synchronization, recoverable failure restoration, rollback-failed diagnostics, and removal of its former direct/pre-write path are verified in `tests/cli/test_scope_review_cmd.py`.
- `detail` and `apply_narrow()` no longer directly call `save_concepts()`, `write_concepts`, raw `concepts_path()` writes, or equivalent helpers for decision-bearing concept trees, as proven by a focused source scan or static assertion.
- A detail publication failure after active-detail replacement but before sidecar replacement restores the prior active detail and concept state, or returns the common rollback-failed result with the exact uncertain path set.
- `apply_narrow()` keeps plan scope prose, the sidecar, forward seed, details, and fingerprint synchronized after success and after recoverable failure.
- Scope review, detail, scope-out, and create all preserve the common rollback-failed status and exact uncertain-path set at their command surfaces.
- CLI dispatch owns the repository mutation lock, the coordinator consumes explicit proof of ownership without reacquiring it, and direct library publication uses the lock-acquiring wrapper.
- Blocked, declined, dry-run, stale, and malformed detail or scope-out paths remain non-mutating. Legacy no-sidecar paths retain their established detail-only or carve behavior without inventing concept authority.
- Detail deferral add, replace, and remove operations use the public deferral mutation contract and pass `tests/test_detail.py`.
- Focused tests, the full suite, data-contract drift checks, and `reconcile-code` pass with no publication-authority redirect.

## Deferred

- Concept authoring/output validation — owned by `concept-remediation-2-authoring-boundary-hardening` as a separate concern.
- Lifecycle accounting and structural deferral conservation — owned by `concept-remediation-3-ownership-lifecycle-accounting` as a separate concern.
