# Step 4 — Publish scope reviews through the new authority

## Summary

This step routes `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` through the typed, all-or-recoverable publication authority delivered by steps 2 and 3. The handler keeps ownership of plan lookup, concept derivation, scoped review, exit codes, and operator messages; the authority owns validation, compare-and-swap checks, plan and sidecar publication, recovery, and final fingerprinting. The key design decision is to submit one signed-review publication request instead of calling the older synchronization path or writing either artifact in the handler. On green, a successful scope review publishes the reviewed concept record and rendered plan changes together, while every failure either restores both artifacts or reports the exact paths whose state is uncertain.

## Table of Contents

- [Summary](#summary) — The result and main design boundary.
- [Why](#why) — Why the scope-review handler must move to the new authority.
- [Input](#input) — The dependency-step and review contracts consumed by this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files changed by this step.
- [Implementation](#implementation) — The authority handoff, result mapping, and required invariants.
- [Tests](#tests) — Feature coverage for success, recovery, and diagnostics.
- [Acceptance criteria](#acceptance-criteria) — Observable proof that scope review uses the new publication path.
- [References](#references) — Test guidance relevant to the orchestration seams.
- [Deferred](#deferred) — Publication work owned by other steps.

## Why

`plan_tool/cli/scope_review_cmd.py:cmd_scope_review` already prepares a reviewed tree and sends it to `plan_tool/concept_sync.py:synchronize_concepts`, but that HEAD path has the older request shape and reduces rollback uncertainty to `ConceptSyncResult.rollback_error`. Steps 2 and 3 replace that boundary with typed intents and an all-or-recoverable result that distinguishes restored failure from uncertain repository state. Scope review must use that new contract so the plan’s scope prose, step scopes, concept record, and final fingerprint cannot be published through a weaker path or reported as unchanged when restoration failed.

## Input

- **Step 2 output:** the typed signed-decision publication intent and validated request/result contract in `plan_tool/concept_sync.py`. Use that contract directly; do not recreate its validation rules in the CLI handler.
- **Step 3 output:** the command-facing all-or-recoverable publication entry point and its distinct success, conflict, invalid-state, restored-failure, and rollback-failed outcomes. The scope-review command must preserve the exact uncertain-path set returned by this authority.
- `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` supplies the exact source plan text, parsed `Plan`, original `ConceptTree` snapshot or absence, and reviewed candidate required by the signed-review intent.
- `plan_tool/concept_review.py:review_concept_scope` remains the authority for checking that every requested concept has exactly one valid decision and for applying approval metadata with `sign_off=True`.
- `plan_tool/concept_bootstrap.py:bootstrap_concepts` and `plan_tool/concept_bootstrap.py:rederive_concepts` remain the source of the fresh candidate and conflict list. Derivation conflicts must still stop before publication.
- `plan_tool/cli/scope_review_cmd.py:SCOPE_REVIEW_CONFLICT_EXIT` and `plan_tool/cli/scope_review_cmd.py:SCOPE_REVIEW_INVALID_STATE_EXIT` remain the command’s public exit-code contract.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/scope_review_cmd.py` — replace the older `synchronize_concepts` handoff with the step-3 publication authority and map its typed outcomes to accurate exit codes and messages.
  - `tests/cli/test_scope_review_cmd.py` — add focused orchestration tests for the signed-review request, successful joint publication, restored failure, rollback uncertainty, and removal of the older publication path.

## Implementation

The foundational logic is: **turn one validated signed scope review into one authority-owned publication and report its typed outcome without losing recovery information**.

- **Keep review preparation in `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`.** Continue loading the exact source Markdown, parsing the plan, computing the current fingerprint, loading the original concept record, bootstrapping fresh concepts, and re-deriving saved decisions. These values define the source snapshot and reviewed candidate; the handler should not publish while building them.

- **Preserve early no-write exits.** `InvalidConceptTreeError`, `StaleConceptTreeError`, conflicts returned by `rederive_concepts`, and `ConceptReviewError` must still stop before calling the publication authority. Keep reporting every derivation conflict rather than stopping after the first.

- **Keep `review_concept_scope(..., sign_off=True)` as the decision authority.** Pass the complete `args.concept` scope and parsed `args.decision` pairs through this function. Do not duplicate its unknown-ID, duplicate-ID, incomplete-scope, stale-source, decision-vocabulary, or approval-metadata rules in the publication request builder.

- **Submit a signed-review intent through the step-3 command-facing authority.** The request must carry the immutable original snapshot separately from the reviewed candidate, plus the parsed plan and exact source plan text required for compare-and-swap validation. The authority must compare durable state with the original snapshot, never with the reviewed candidate.

- **Remove the older publication handoff.** `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` must no longer call the legacy form of `plan_tool/concept_sync.py:synchronize_concepts` or perform any plan, sidecar, fingerprint, staging, rollback, or provenance write itself. One way to keep the handler small is a local result-to-exit mapping around the step-3 public request, but the exact helper layout is up to the implementer.

- **Use the already-locked command path.** `scope-review` is already listed in `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS`, and `plan_tool/cli/app.py:main` dispatches it inside `repo_mutation_lock`. Call the step-3 entry point intended for an already-locked command; do not use a direct-call wrapper that acquires the same non-reentrant lock again.

- **Preserve conflict and invalid-state exits.**
  - Map derivation conflicts and publication compare-and-swap or mapping conflicts to `SCOPE_REVIEW_CONFLICT_EXIT`.
  - Map malformed records, invalid review requests, rejected publication requests, and publication failures to `SCOPE_REVIEW_INVALID_STATE_EXIT`.
  - Return `0` only after the authority confirms the full publication.

- **Report restored failure honestly.** When the authority reports that publication failed but recovery restored every original artifact, say that no changes remain or that the original state was restored. Do not reuse wording that implies the operation never began if the distinction matters in the step-3 result.

- **Preserve rollback-failed details.** When recovery cannot prove restoration, print the distinct rollback-failed outcome and every uncertain path returned by step 3. Do not flatten the path set into a generic exception string, claim that no changes were written, or reduce the message to “repository state may be partial” without identifying the affected artifacts.

- **Keep success reporting after commit.** The existing success message may retain its reviewed-concept count and plan slug, but it must run only after the authority verifies the live plan and concept record. The published sidecar fingerprint must identify the exact final plan bytes selected by the authority.

- **Do not broaden command syntax.** `plan_tool/cli/scope_review_cmd.py:_decision` and `plan_tool/cli/scope_review_cmd.py:register` remain compatible with the existing repeated `--concept` and `--decision CONCEPT_ID=DECISION` interface.

## Tests

- `tests/cli/test_scope_review_cmd.py:test_scope_review_submits_signed_review_to_publication_authority` — the handler passes the original tree, reviewed candidate, parsed plan, and exact source text through the step-2 signed-review request.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_bootstraps_and_persists_scoped_result` — success publishes approved scoped decisions, rendered plan prose, and a matching final fingerprint while leaving unrelated prose and concepts unchanged.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_calls_publication_authority_once` — one command invocation creates exactly one publication request and has no second plan or sidecar writer.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_recoverable_publication_failure_restores_both_artifacts` — a failure after one replacement returns exit 4 and leaves the original plan and concept-record bytes and existence restored.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_rollback_failed_reports_exact_uncertain_paths` — rollback failure returns exit 4, names every uncertain path from the authority result, and does not claim that no changes were written.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_maps_publication_conflict_to_conflict_exit` — source divergence or mapping conflict returned by the authority produces `SCOPE_REVIEW_CONFLICT_EXIT`.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_invalid_record_has_distinct_exit_and_writes_nothing` — malformed or stale concept state still returns exit 4 before publication.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_reports_all_derivation_conflicts_without_writes` — all re-derivation conflicts are shown and the authority is not called.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_invalid_requested_scope_skips_publication` — `ConceptReviewError` returns exit 4 and leaves the authority uncalled.
- `tests/cli/test_scope_review_cmd.py:test_scope_review_parser_rejects_malformed_decision` — argparse still rejects an unknown decision with exit 2.

### Test-creation order (feature step)

1. Add the authority-request test and the once-only publication test to pin the new orchestration boundary.
2. Add successful joint-publication coverage, including the final fingerprint and preservation of unrelated content.
3. Add recoverable publication-failure coverage that compares both artifacts’ original bytes and existence.
4. Add rollback-failed coverage that checks the complete uncertain-path set and forbids a false no-change message.
5. Add typed conflict and invalid-state mapping tests.
6. Retain the existing malformed-record, derivation-conflict, and parser tests as regression coverage.

Every new test in `tests/cli/test_scope_review_cmd.py` must pass before this step is considered finished.

## Acceptance criteria

- `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` publishes a valid signed review through the step-3 command-facing authority exactly once.
- A successful command returns `0` only after the reviewed concept record and rendered plan changes are both verified as published.
- The stored concept record contains the signed decisions from `review_concept_scope(..., sign_off=True)` and a fingerprint for the exact final plan bytes.
- Derivation conflicts and authority-reported source or mapping conflicts return `SCOPE_REVIEW_CONFLICT_EXIT`.
- Invalid concept records, invalid requested scopes, and non-conflict publication failures return `SCOPE_REVIEW_INVALID_STATE_EXIT`.
- A recoverable publication failure restores the original plan and concept-record contents and existence.
- A rollback-failed result prints every uncertain path returned by the authority and never says that no changes were written.
- Invalid records, stale records, incomplete review scopes, and derivation conflicts do not call the publication authority.
- `plan_tool/cli/scope_review_cmd.py` contains no direct plan or concept-record publication path outside the step-3 authority call.
- All focused tests in `tests/cli/test_scope_review_cmd.py` pass.

## References

- [pytest — Monkeypatching functions and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use injected authority results and failure seams to test handler orchestration without duplicating coordinator internals.

## Deferred

- Typed publication request and result definitions — step 2 owns these contracts in `plan_tool/concept_sync.py`.
- Staging, durable journals, restart recovery, final-byte verification, restoration, and uncertain-path calculation — step 3 owns the common publication authority.
- Create, detail, and scope-out migration — steps 7, 9, and 11 route those callers through the same authority.
- Direct-write enforcement across all production callers — step 12 owns the repository-wide bypass check.
- CLI mutation-lock redesign — this step relies on the step-3 command-facing contract and the existing lock around `plan_tool/cli/app.py:main`; if that contract requires a new `plan_tool/cli/app.py` handoff, reconcile the plan’s file ownership before implementation instead of acquiring the lock again here.
