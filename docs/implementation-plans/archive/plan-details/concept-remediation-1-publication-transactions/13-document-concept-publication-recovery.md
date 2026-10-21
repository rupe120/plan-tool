# Step 13 — Document concept publication and recovery

## Summary

This step updates `CLAUDE.md` and `RUNBOOK.md` to describe the concept publication authority delivered by steps 1–12. `CLAUDE.md` will register the authority, its single-writer boundary, and its all-or-recoverable guarantee in the Architecture section. `RUNBOOK.md` will explain publication outcomes, create-review resume state, restart recovery, uncertain-path failures, and which `.plan-tool/` state operators must preserve. On green, maintainers and operators can distinguish a safe retry from a failed rollback without treating multi-file publication as atomic or deleting required recovery data.

## Table of Contents

- [Summary](#summary) — The documentation changes and expected result.
- [Why](#why) — Why the completed transaction behavior needs an accurate operator contract.
- [Input](#input) — The dependency-step outcomes this documentation must verify.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two documentation files changed.
- [Implementation](#implementation) — The Architecture and recovery guidance to add.
- [Tests](#tests) — Documentation checks against the shipped implementation.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that the documentation is complete and accurate.
- [References](#references) — Repository sources used to verify the prose.
- [Deferred](#deferred) — Recovery and transaction work outside this docs-only step.

## Why

Steps 1–12 replace several independent concept writers with one typed, recoverable publication boundary, but the durable guides do not yet explain that boundary or its recovery states. In particular, `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)` currently describes all ignored state as freely deletable, which is unsafe when an incomplete publication journal or create-review resume record is needed for recovery. The documentation must also avoid calling a multi-file operation atomic: success is fully verified, an ordinary failure restores and verifies the original generation, and a rollback failure leaves named paths uncertain and requires operator review.

## Input

- **Step 3 — publication authority.** Verify the landed coordinator, recovery entry point, durable journal location, lock contract, result vocabulary, and uncertain-path representation in `plan_tool/concept_sync.py`. Document the implemented public names rather than names proposed by an earlier detail.
- **Step 5 — create-review resume.** Verify the resume record, path helper, compatibility checks, and read/write behavior in `plan_tool/concept_tree.py`, plus its use by `plan_tool/create.py:create_plan`. Resume progress is unsigned local state, not a finalized concept record.
- **Steps 4, 7, 9, and 11 — caller migrations.** Confirm that `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, and `plan_tool/scope_out.py:apply_narrow` publish through the common authority and preserve its distinct failure results.
- **Step 3 — startup recovery and lock handoff.** Confirm that `plan_tool/cli/app.py:main` runs recovery at each command’s effective mutation boundary and passes the yielded lock token without nested acquisition. Dry runs never recover; declines before any write remain non-mutating; create review recovers before its first unsigned resume save and may retain that progress after a later approval decline. The explicit operator-recovery command acquires the lock but bypasses ordinary automatic recovery so it can resolve the selected `operator_required` marker.
- **Step 11 — scope-out reporting.** Confirm the operator messages emitted by `plan_tool/cli/scope_out_cmd.py` and `plan_tool/cli/convergence_cmd.py` preserve restored-failure and rollback-failed distinctions.
- **Step 12 — single-writer enforcement.** Confirm the source assertion in `tests/test_concept_sync.py` permits only the intended low-level concept writers and blocks production bypasses.
- **Plan boundary.** Use `docs/implementation-plans/2-concept-remediation-1-publication-transactions.md:Out of scope` and `docs/implementation-plans/2-concept-remediation-1-publication-transactions.md:Deferred` to preserve two limits: rollback-failed state is reported rather than automatically repaired, and the authority is not a general repository transaction framework.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `CLAUDE.md` — reconcile the Architecture section with the shipped concept publication authority, its callers, lock ownership, single-writer rule, and all-or-recoverable guarantee.
  - `RUNBOOK.md` — add a Table-of-contents-linked publication recovery workflow and correct the storage, create-resume, concept-review, detail, scope-out, common-failure, and undo guidance where the new contract changes operator behavior.

## Implementation

The foundational logic is: **document one verified publication generation, one verified restored generation, or an explicitly uncertain path set—never implied multi-file atomicity**.

- **Verify before writing.** Read the implementation and focused tests from steps 3–12 before describing the capability as shipped. If a required publication path still writes concepts directly, loses uncertain paths, reacquires the repository lock, or lacks restart recovery, route that gap to its owning implementation step. Do not compensate with production changes in this step.

- **Reconcile `CLAUDE.md:Architecture`.** Add a sibling Architecture paragraph for the concept publication authority, or extend the existing concept subsystem paragraph if that avoids duplicate entries. Model the result on the other bold-lead subsystem paragraphs and cover:

  - `plan_tool/concept_sync.py` owns typed validation, staging, publication, final-byte verification, restoration, and restart recovery for concept-related artifact bundles.
  - `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, `plan_tool/create.py:create_plan`, `plan_tool/detail.py:generate_detail`, and `plan_tool/scope_out.py:apply_narrow` prepare operation-specific inputs but do not publish decision-bearing concept state themselves.
  - The guarantee is all-or-recoverable, not atomic across files. A rollback-failed result names every path whose original or target state cannot be proved.
  - `plan_tool/cli/app.py:main` owns the non-reentrant repository mutation lock for CLI publication. The publishing core consumes that ownership and does not acquire it again.
  - `plan_tool/concept_tree.py:save_concepts` remains a low-level serializer only for the permitted finalized-sidecar bootstrap and test cases established by step 12; it is not an alternate production publication path. Create-review resume state uses its dedicated unsigned resume serializer and never calls `concepts_path`, `load_concepts`, or `save_concepts`.

- **Add `RUNBOOK.md:Workflow: recover concept publication`.** Add a matching entry under `RUNBOOK.md:Table of contents` with the GitHub anchor `#workflow-recover-concept-publication`. Place the workflow near `RUNBOOK.md:Workflow: recover from an interrupted create/detail run`, while keeping backend checkpoints and concept publication recovery as separate kinds of state.

- **Explain the normal publication contract.** State that scope review, create finalization, successful detail publication with deferral changes, and scope-out each submit one complete artifact bundle. Validation, stale-state checks, and staging finish before live replacement; success is reported only after the final live bytes match the staged generation.

- **Explain the three operator outcomes using the landed names.**

  - **Success:** every requested artifact matches the verified target generation and incomplete recovery state is gone.
  - **Restored failure:** publication failed, but the original bytes and original absent paths were restored and verified. The operator may correct the reported cause and retry.
  - **Rollback failed or uncertain:** restoration could not be proved. The output lists the uncertain paths; the operator must stop, inspect those paths and the recovery record, and choose the intended generation before retrying.

  Do not tell operators to retry an uncertain operation blindly, delete its journal, or infer repository state from the first failed path.

- **Describe restart recovery.** Explain that definitely mutating CLI commands and every direct publication preflight check recovery state under the repository lock at their effective mutation boundary, where its durable state lives, and what operators will see when recovery completes a provable generation or blocks on malformed, contradictory, or rollback-failed state. Dry runs do not recover, and interactive declines before any write remain non-mutating. Create review recovers before its first durable unsigned resume save; a later approval decline retains that resume progress but publishes no final artifacts. The explicit operator-recovery command is the sole dispatch exemption: it still owns the lock but bypasses ordinary automatic recovery so it can inspect and resolve the selected `operator_required` marker. A rollback-failed marker is never auto-replayed; the operator chooses the intended generation and uses only that implemented workflow to clear it. Use the exact path constants and messages that landed in `plan_tool/concept_sync.py`; do not invent a recovery directory name from the plan prose.

- **Correct `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)`.** Split disposable checkpoints and debug output from publication-critical local state:

  - Publication journals, staged files, and backups for an incomplete operation are not safe to delete.
  - Create concept-review resume records may be removed only when the operator intentionally abandons that saved review or follows the implemented fresh-start path.
  - Completed cleanup state may be removable only when the implementation can prove no incomplete transaction refers to it.
  - Backend checkpoints remain separate memoized responses and keep their existing `plan-tool checkpoint` cleanup guidance.

  Avoid retaining the blanket claim that every ignored `.plan-tool/` path is safe to delete at any time.

- **Update create recovery guidance.** In `RUNBOOK.md:Workflow: recover from an interrupted create/detail run`, distinguish backend-response checkpoints from the unsigned create concept-review record. Explain that compatible create inputs resume accepted review selections, changed evidence or settled steps stop rather than reuse old choices, and a failed final publication keeps compatible progress available. Use the actual fresh-start flag or command behavior from `plan_tool/create.py:create_plan`; do not assume that clearing a backend checkpoint also clears operator review progress.

- **Update concept-review guidance.** In `RUNBOOK.md:Workflow: review concept decisions and ownership (scope-review)`, state that a successful review publishes the plan and concept record together. Replace any failure description that treats all publication failures as “no changes were written” with the implemented distinction between preflight refusal, verified restoration, and uncertain rollback.

- **Update detail guidance.** Reconcile `RUNBOOK.md:Workflow: author detail files for developer hand-off` and its partial-success recovery note with step 9. A detail write and its plan pointer or structured concept deferrals now follow the landed publication boundary; retain checkpoint instructions only for authoring work that is still outside that transaction. Do not preserve an old manual-repair recipe if the authority now restores the earlier detail generation.

- **Update scope-out and common-failure guidance.** Ensure the scope-out workflow says the narrowed plan, concept record, scope prose, forward seed, and detail moves publish as one recoverable bundle. Add the landed rollback-failed signal to `RUNBOOK.md:Recovery: common failures`, including the rule to inspect every uncertain path and preserve the recovery record.

- **Correct undo claims.** Update `RUNBOOK.md:Backing up / undoing` so it does not present concept publication recovery as a general undo feature. The journal restores or completes an interrupted operation; it does not provide arbitrary history after a verified success.

- **Keep terms consistent.** Use “publication journal” or the exact implemented term for transaction state, “create-review resume” for unsigned operator progress, and “checkpoint” for cached backend responses. Do not call these three artifacts interchangeable caches.

## Tests

No production tests are added by this docs-only step. Use these named documentation checks and the verification commands below.

- `verify_publication_symbols_at_head` — every function, result state, constant, path, and command message named in `CLAUDE.md` or `RUNBOOK.md` exists in the owning source at HEAD.
- `verify_all_publication_callers_documented` — the docs cover scope review, create, detail, and scope-out without claiming that any caller remains an independent concept writer.
- `verify_publication_outcomes_are_distinct` — the docs separately explain success, verified restoration, and rollback-failed uncertainty.
- `verify_runbook_recovery_anchor` — `RUNBOOK.md:Table of contents` links to the exact `RUNBOOK.md:Workflow: recover concept publication` heading.
- `verify_dot_plan_tool_deletion_rules` — `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)` no longer marks incomplete journals, staging data, backups, or create-review progress as freely deletable.
- `verify_resume_and_checkpoint_terms` — `RUNBOOK.md` clearly separates create-review resume records from backend checkpoints.
- `verify_no_atomicity_overclaim` — neither edited file describes a multi-artifact publication as atomic.
- `verify_declared_files_only` — the final diff changes only `CLAUDE.md` and `RUNBOOK.md`.

### Verification (non-code step)

- Run `uv run pytest tests/test_concept_sync.py tests/test_create.py tests/test_detail.py tests/test_scope_out.py tests/cli/test_scope_review_cmd.py tests/cli/test_scope_out_cmd.py tests/cli/test_convergence_cmd.py -q` before making shipped claims.
- Inspect the step 12 enforcement test in `tests/test_concept_sync.py` and confirm its production-writer allowlist passes at HEAD.
- Grep `plan_tool/` for `save_concepts`, `write_concepts`, raw writes using `concepts_path`, and the legacy `synchronize_concepts` path; compare every production hit with the step 12 allowlist.
- Compare every documented recovery state and message with the landed result handling in `plan_tool/concept_sync.py`, `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/scope_out.py`, `plan_tool/cli/scope_review_cmd.py`, `plan_tool/cli/scope_out_cmd.py`, and `plan_tool/cli/convergence_cmd.py`.
- Check that the new `RUNBOOK.md:Table of contents` link points to the exact recovery heading.
- Grep `CLAUDE.md` and `RUNBOOK.md` for claims such as “atomic,” “no changes were written,” “safe to delete anytime,” and “last writer wins”; keep them only where the surrounding text remains true for a non-publication path.
- Review the final prose against `docs/implementation-plans/2-concept-remediation-1-publication-transactions.md:Out of scope` and `docs/implementation-plans/2-concept-remediation-1-publication-transactions.md:Deferred`.

## Acceptance criteria

- `CLAUDE.md:Architecture` names `plan_tool/concept_sync.py` as the concept publication authority and describes its caller, lock, single-writer, and all-or-recoverable boundaries.
- `CLAUDE.md` does not claim that concept-related multi-file publication is atomic.
- `RUNBOOK.md` contains `## Workflow: recover concept publication` and a matching `#workflow-recover-concept-publication` Table-of-contents link.
- `RUNBOOK.md` distinguishes success, verified restoration, and rollback-failed uncertainty using the exact landed result terms.
- `RUNBOOK.md` tells operators to preserve incomplete publication recovery state and inspect every reported uncertain path before another attempt.
- `RUNBOOK.md:What's in .plan-tool/ (commit vs. delete)` distinguishes publication-critical recovery data, create-review resume state, and disposable backend checkpoints.
- Create recovery guidance explains compatible review resume, changed-input refusal, intentional fresh start, and resume retention after failed final publication.
- Scope-review, detail, and scope-out guidance agrees with the common authority and no longer promises “no changes” when restoration itself is uncertain.
- Every source symbol, path, result name, and command form cited by the edited prose exists at HEAD.
- The focused publication, caller, and enforcement tests pass, and the documentation diff changes only `CLAUDE.md` and `RUNBOOK.md`.

## References

- [`docs/implementation-plans/2-concept-remediation-1-publication-transactions.md`](../../2-concept-remediation-1-publication-transactions.md) — Use its Architecture, Out of scope, Deferred, and Acceptance criteria as the documentation boundary.
- [`plan_tool/concept_sync.py`](../../../../plan_tool/concept_sync.py) — Verify the landed publication state machine, recovery entry point, journal paths, result states, and uncertain-path contract.
- [`plan_tool/concept_tree.py`](../../../../plan_tool/concept_tree.py) — Verify the finalized concept sidecar and unsigned create-review resume contracts.
- [`plan_tool/create.py`](../../../../plan_tool/create.py) — Verify create publication, compatible review resume, fresh-start behavior, and failure reporting.
- [`plan_tool/detail.py`](../../../../plan_tool/detail.py) — Verify the detail, plan-pointer, checkpoint, and concept-deferral publication boundaries.
- [`plan_tool/scope_out.py`](../../../../plan_tool/scope_out.py) — Verify which scope-out artifacts publish together and how failure states reach `ScopeOutResult`.
- [`plan_tool/cli/scope_review_cmd.py`](../../../../plan_tool/cli/scope_review_cmd.py) — Verify scope-review exit outcomes and operator messages.
- [`plan_tool/cli/app.py`](../../../../plan_tool/cli/app.py) — Verify repository lock ownership and startup recovery wiring.
- [`tests/test_concept_sync.py`](../../../../tests/test_concept_sync.py) — Verify restart recovery, rollback uncertainty, lock behavior, and the production direct-writer guard.

## Deferred

- **Production fixes found during verification** — route them to the owning step among steps 3–11; this step changes documentation only.
- **Automatic repair after rollback failure** — the authority reports uncertain paths and stops, as required by the plan’s out-of-scope boundary.
- **General-purpose repository transactions** — the documented coordinator remains limited to concept-related publication bundles.
- **Arbitrary undo after verified success** — publication recovery handles interrupted or failed operations and is not a version-history feature.
- **Schema, command, or generated CLI-reference changes** — no such changes belong in the declared `CLAUDE.md` and `RUNBOOK.md` scope.
