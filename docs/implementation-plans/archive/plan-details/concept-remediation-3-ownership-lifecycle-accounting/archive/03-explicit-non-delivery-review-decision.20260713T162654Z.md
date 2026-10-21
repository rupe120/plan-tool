# Step 3 — Add explicit non-delivery review and decision transitions

## Summary

This step adds one explicit transition policy for the structured non-delivery records introduced by step 2. `plan_tool/concept_tree.py` defines the record comparison and approval rules, `plan_tool/concept_sync.py` prepares and validates transitions, and `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` requires real operator review before approving changed `defer` or `wont_do` accounting. The key design decision is to treat a changed decision or changed accounting field as a replacement that loses approval, while preserving approval for an unchanged record. On green, scoped review cannot publish contradictory, silently approved, or prematurely removed non-delivery accounting.

## Table of Contents

- [Summary](#summary) — Overview of the transition policy and affected files.
- [Why](#why) — The current approval and accounting gap this step closes.
- [Input](#input) — Contracts consumed from step 2 and the existing review flow.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and test changes.
- [Implementation](#implementation) — Required transition rules and recommended integration.
- [Tests](#tests) — Unit and CLI cases for every transition.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Directly relevant authoritative documentation.
- [Deferred](#deferred) — Lifecycle callers owned by later steps.

## Why

`plan_tool/concept_review.py:review_concept_scope` invalidates a concept’s sign-off when its decision changes, but `plan_tool/cli/scope_review_cmd.py:cmd_scope_review` immediately calls it with `sign_off=True` for every valid command payload. Once step 2 adds structured non-delivery records, that behavior could approve a new `defer` or `wont_do` decision without reviewing its rationale, evidence, and stable source or artifact reference. It also leaves no shared rule for replacing an approved parked record, preserving an unchanged approval, or removing a parked record only after an `include` transition has durable delivery evidence.

## Input

- **Step 2 output:** consume the durable non-delivery record contract added to `plan_tool/concept_tree.py`, including its concept identity, disposition, rationale or evidence, approval state, and stable source or artifact reference. This step must use that contract as delivered instead of defining a second record shape.
- **Scoped decision contract:** continue using `plan_tool/concept_review.py:CONCEPT_DECISIONS` and `plan_tool/concept_review.py:review_concept_scope` for scope validation, stale-source checks, and concept-level decision state.
- **Publication contract:** preserve `plan_tool/concept_sync.py:synchronize_concepts` as the guarded publication path over the original snapshot and reviewed candidate. The original tree remains the compare-and-swap precondition.
- **CLI payload:** retain `plan_tool/cli/scope_review_cmd.py:_decision` and the existing exact-scope rule: every `--concept` must have exactly one matching `--decision`.
- **Verification limit:** approval can prove that an operator reviewed the supplied accounting fields; it cannot prove a missing or regenerated artifact is durable. Removal that depends on regeneration must require explicit durable-artifact evidence from the owning caller.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/concept_tree.py` — add pure comparison and approval-state helpers for the step-2 non-delivery record, keeping concept identity separate from accounting-record identity.
  - `plan_tool/concept_sync.py` — add the shared transition preparation and validation policy, and enforce it before `synchronize_concepts` renders or publishes either artifact.
  - `plan_tool/cli/scope_review_cmd.py` — add the operator review gate for changed non-delivery accounting and stop unconditional sign-off of unreviewed transitions.
  - `tests/test_concept_tree.py` — cover semantic equality, approval preservation, and approval invalidation for structured records.
  - `tests/test_concept_sync.py` — cover the full transition table, durable-removal guard, validation ordering, and no-write failures.
  - `tests/cli/test_scope_review_cmd.py` — cover interactive review, non-TTY refusal, unchanged approval, exit codes, and publication behavior.

## Implementation

The foundational logic is a **non-delivery transition predicate** that compares the original and proposed decision plus the complete step-2 accounting record, then decides whether approval may be preserved, must be cleared and renewed, or whether removal must wait for durable delivery evidence.

- **Keep record comparison pure.** Add a helper beside the step-2 record contract in `plan_tool/concept_tree.py`. It should compare every field that an operator approves, including disposition, rationale or evidence, and stable source or artifact identity. Do not use only the concept ID or decision string: those values cannot show that the approved evidence changed.

- **Treat approval as record-specific.** Approval may survive only when the decision and every reviewed record field are unchanged. Cosmetic object replacement with the same persisted values may preserve approval; any meaningful field change must clear it.

- **Centralize the transition table.** Add one public preparation helper in `plan_tool/concept_sync.py`, with a descriptive name such as `prepare_non_delivery_transitions`. It should take the original snapshot, proposed reviewed state, and any explicit durable-artifact evidence, validate the full requested scope first, and return a copied candidate or a typed invalid-state result. Callers must not reproduce the transition rules.

- **Apply these transition rules:**
  - `include → defer` or `include → wont_do` creates the corresponding step-2 record as unapproved. It becomes approved only after the operator reviews its decision, rationale or evidence, and stable source or artifact reference.
  - `defer → wont_do` and `wont_do → defer` replace the old record. Do not carry the old approval onto the replacement, even if some evidence fields are reused.
  - An unchanged `defer` or `wont_do` decision with an unchanged record preserves its existing approval and stable accounting-record identity.
  - An unchanged decision with changed rationale, evidence, source, artifact reference, or other reviewed field invalidates approval and requires review of the replacement.
  - `defer → include` or `wont_do → include` removes the old record only when the caller supplies evidence that every linked artifact requiring regeneration is already durable. Without that evidence, reject the transition before publication; do not publish an `include` decision beside a stale parked record, and do not remove the record early.
  - A transition must affect only the requested concept IDs. Preserve unrelated concepts and records exactly.

- **Separate preparation from publication.** Run transition preparation before `plan_tool/concept_sync.py:synchronize_concepts` calls `_mapped_scopes`, `render_scope_decisions`, `_fingerprint`, or either `Publisher` call. Validate the whole candidate before changing files so one bad concept leaves the plan and sidecar unchanged.

- **Enforce the policy at the publication boundary.** `synchronize_concepts` must compare `original_tree` with the reviewed candidate and reject a transition that bypassed the shared preparation rules. This protects existing callers in `plan_tool/create.py` and future callers without moving their publication protocols into this step.

- **Keep compare-and-swap roles distinct.** Use `original_tree` to verify the durable source state and the reviewed candidate to derive intended changes. Never compare the current sidecar against the candidate.

- **Preserve synchronization ordering.** Continue rendering the candidate plan, computing `plan_tool/concept_sync.py:_fingerprint` over that rendered plan plus ordered detail files, assigning the fingerprint to the final tree, validating it, and only then publishing. The transition helper must not write either artifact.

- **Add an operator-only review gate.** In `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, present every newly created or replaced non-delivery record with its decision, rationale or evidence, and stable source or artifact reference. One reasonable approach is a small injected prompt helper that allows correction and requires an explicit confirmation for each changed record.

- **Do not let unattended execution create approval.** When stdin is not a TTY, a transition needing review must refuse before `synchronize_concepts` and print an exact command the operator can rerun on a TTY. If a future local `--yes` path reaches this command, treat it the same way. An already approved, semantically unchanged record may retain approval because the command is not creating a new sign-off.

- **Sign off only after review completes.** Continue using `plan_tool/concept_review.py:review_concept_scope`, but do not pass `sign_off=True` until the transition payload has passed the operator gate. A declined, interrupted, incomplete, or invalid review writes nothing.

- **Keep the parser surface stable unless required by the step-2 contract.** The existing repeated `--concept` and `--decision` arguments already identify the transition scope. Prefer interactive review of the structured fields so this step does not require generated CLI reference or package-help changes outside its declared files.

- **Map failures consistently.** Preserve `SCOPE_REVIEW_CONFLICT_EXIT` for source divergence and mapping conflicts and `SCOPE_REVIEW_INVALID_STATE_EXIT` for malformed records, incomplete review, missing durable-removal evidence, and other invalid transitions. Messages must say whether no changes were written or rollback left partial state, matching the existing `ConceptSyncResult.rollback_error` handling.

## Tests

- `test_non_delivery_record_equality_covers_every_reviewed_field` — changing any approved record field makes the records semantically different.
- `test_unchanged_non_delivery_record_preserves_approval` — the same decision and record retain approval and stable identity.
- `test_changed_non_delivery_record_clears_approval` — changed rationale, evidence, source, or artifact reference requires renewed review.
- `test_include_to_parked_creates_unsigned_record` — either parked disposition prepares a complete but unapproved record.
- `test_parked_disposition_change_replaces_record` — `defer ↔ wont_do` cannot inherit approval from the old record.
- `test_parked_to_include_requires_durable_resolution` — removal is rejected when required durable-artifact evidence is absent.
- `test_parked_to_include_removes_record_after_durable_resolution` — valid evidence permits record removal in the same candidate as the `include` decision.
- `test_transition_scope_preserves_unselected_concepts` — records outside the requested scope remain unchanged.
- `test_invalid_transition_is_atomic` — one invalid item rejects the entire candidate without mutating either input.
- `test_sync_rejects_bypassed_transition_without_writes` — direct publication cannot evade the transition policy.
- `test_sync_transition_publication_keeps_fingerprint_and_ordering` — an accepted transition retains the established render, fingerprint, and publication contract.
- `test_sync_transition_publication_failure_rolls_back` — transition work does not weaken existing restoration behavior.
- `test_scope_review_prompts_for_changed_non_delivery_record` — the CLI shows every reviewed field and signs off only after explicit confirmation.
- `test_scope_review_declined_record_review_writes_nothing` — a declined review leaves the plan and sidecar unchanged.
- `test_scope_review_non_tty_cannot_approve_transition` — unattended execution returns invalid state, prints a resumable command, and writes nothing.
- `test_scope_review_unchanged_approved_record_needs_no_new_signoff` — an unchanged approved record retains approval without forging a new review.
- `test_scope_review_include_waits_for_durable_artifact` — the CLI refuses premature removal and reports the required regeneration route.
- `test_scope_review_transition_success_publishes_consistent_artifacts` — an explicitly reviewed transition updates the plan and concept sidecar together.

### Test-creation order (feature step)

Add the pure transition-table tests in `tests/test_concept_tree.py` and `tests/test_concept_sync.py` with the transition helpers. Add the CLI review and unattended-refusal tests in `tests/cli/test_scope_review_cmd.py` with the operator gate. Then run the existing synchronization conflict and rollback cases unchanged to catch publication regressions. Every new test and every existing focused test in these three files must be green before this step is considered finished.

## Acceptance criteria

- `include → defer` and `include → wont_do` produce complete step-2 non-delivery records whose approval remains unset until explicit operator review.
- `defer → wont_do` and `wont_do → defer` replace the old record and do not carry its approval forward.
- Repeating the same parked decision with exactly the same record preserves approval and stable record identity.
- Changing any operator-reviewed record field clears approval and requires renewed review.
- `defer|wont_do → include` cannot remove a record until required regenerated artifacts are confirmed durable.
- `plan_tool/concept_sync.py:synchronize_concepts` rejects a candidate that bypasses the transition policy before either artifact is written.
- Non-TTY execution cannot approve a new or changed non-delivery record and prints a runnable recovery command.
- A declined or incomplete interactive review leaves both the plan and concept sidecar unchanged.
- Successful scoped review publishes a matching plan and sidecar with the fingerprint produced by `plan_tool/concept_sync.py:_fingerprint`.
- Existing source-divergence, mapping-conflict, publication-failure, and rollback tests remain green.
- All new tests in `tests/test_concept_tree.py`, `tests/test_concept_sync.py`, and `tests/cli/test_scope_review_cmd.py` pass.

## References

- [argparse — Parser for Command-Line Options, Arguments and Subcommands](https://docs.python.org/3/library/argparse.html) — Use for the existing repeated scoped-decision arguments and any parser-level validation that remains necessary.
- [pytest: How to Parametrize Fixtures and Test Functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use to cover the decision-transition matrix and record-field change cases without duplicating test setup.

## Deferred

- `plan_tool/detail.py:_replace_detail_deferrals` include-triggered regeneration — step 4 must call the shared transition policy only after detail regeneration is durable.
- `plan_tool/scope_out.py:_prepare_concept_narrow_update` currently signs off ownerless deferrals directly — step 8 must replace that bypass with the shared review workflow while preserving scope-out’s own transaction and rollback sequence.
- Completeness checks for missing, dangling, unsigned, or contradictory accounting — step 5 owns those findings and their report behavior.
- Split, merge, re-ground, and seed-restoration callers — steps 6, 7, 9, 10, and 11 apply this transition contract to their respective lifecycle operations.
- Generated CLI references and operator documentation — later command/documentation steps own regeneration and workflow prose; this step keeps the existing parser shape stable.
