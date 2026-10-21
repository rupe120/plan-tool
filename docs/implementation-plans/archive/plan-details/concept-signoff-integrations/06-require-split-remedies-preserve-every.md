> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Require split remedies to preserve every concept id

## Summary

Make every step-splitting path preserve the target step’s explicit concept ownership. Update `plan_tool/create.py:_apply_step_split` to enforce exact concept-ID conservation, extend Claude-proposed splits to return a valid distribution, and make `plan_tool/detail.py:split_step` copy ownership safely when the operator supplies titles only. Keep `plan_tool/launcher.py:escalate_to_split` on the same shared transform so structural escalation cannot bypass the rule. On green, a successful split may redistribute or repeat ownership across its replacements, but it can neither drop an existing concept ID nor introduce a new one.

## Table of Contents

- [Summary](#summary) — The ownership-preserving split result.
- [Why](#why) — Why structural remedies must not reopen signed-off coverage gaps.
- [Input](#input) — The ownership and completeness contracts consumed by this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six scoped files and their changes.
- [Implementation](#implementation) — The conservation rule and its use across all split paths.
- [Tests](#tests) — Unit and integration coverage for valid and invalid splits.
- [Acceptance criteria](#acceptance-criteria) — Observable requirements for completion.
- [References](#references) — Validation semantics relevant to concept-ID arrays.
- [Deferred](#deferred) — Related structural transformations owned by later steps.

## Why

A split currently replaces one step with new `Step` objects while preserving dependencies and status, but it has no rule for the target’s signed-off concept ownership. Once step 5 makes explicit ownership or structured deferral the only valid completeness link, dropping `Step.concept_ids` during a create-time split, on-demand split, or `BLOCKED-STRUCTURAL` escalation would turn a valid plan into one with missing concept coverage. The split transform must therefore treat concept IDs like dependencies and lifecycle state: they are part of the target’s contract and cannot disappear during structural repair.

## Input

- **Step 1 — explicit ownership:** step 1 adds `plan_tool/schema.py:Step.concept_ids`, including the rules that IDs are unique within one step while the same ID may appear on more than one step.
- **Step 5 — explicit-link completeness:** step 5 treats an exact concept ID on a committed step as authoritative coverage. Split behavior must preserve that coverage without relying on titles, features, files, or detail prose.
- **Existing split transform:** `plan_tool/create.py:_apply_step_split` is the shared pure transform that splices replacements, renumbers steps, rewires dependencies, and preserves the target status.
- **Split callers:** `plan_tool/create.py:_review_step_change_types`, `plan_tool/detail.py:split_step`, and `plan_tool/launcher.py:escalate_to_split` all reach the shared transform with different replacement sources.
- **Ownership set rule:** compare concept IDs as sets for conservation. Order within an individual replacement remains authored data, and the same target ID may be assigned to more than one replacement because cross-step ownership is valid.

## Files (creates vs edits)

- **New files:**

  - None.

- **Existing files (edits only):**

  - `plan_tool/create.py` — parse concept IDs from split proposals, tell the split proposer to distribute the target’s IDs, and enforce exact ownership conservation in `_apply_step_split`.
  - `plan_tool/detail.py` — make `split_step` preserve the target’s ownership when it constructs replacements from operator-supplied titles.
  - `plan_tool/launcher.py` — keep `escalate_to_split` aligned with the shared conservation failure behavior and its existing no-partial-write contract.
  - `tests/test_create.py` — cover parsing, valid redistribution, repeated ownership, dropped IDs, and invented IDs in the core split transform and create review flow.
  - `tests/test_detail.py` — cover on-demand, dry-run, and detail-authoring splits of concept-owning steps.
  - `tests/test_launcher.py` — cover valid and invalid concept distributions through `escalate_to_split`.

## Implementation

- **Make exact concept-ID conservation the foundational logic.** For target concept set `T` and replacement concept sets `R1..Rn`, require `T == union(R1..Rn)`. This permits a concept to remain on multiple halves, which step 1 explicitly allows, while rejecting both silent loss and ownership invented by a split.

- **Enforce the rule in the shared transform.** Add the check to `plan_tool/create.py:_apply_step_split` before returning the rewritten list. This is the only common point reached by create review, on-demand `plan-tool split`, and structural escalation, so the invariant cannot depend only on prompt compliance or caller discipline.

- **Fail before publishing a partial split.** A conservation failure from `plan_tool/create.py:_apply_step_split` must raise `CreateError` without mutating the input list. Preserve the function’s existing pure list-to-list behavior and graph-validation contract.

- **Keep all existing split invariants.** Concept handling must not change contiguous renumbering, dependency rewiring, terminal-edge redirection, target-status inheritance, or the validation performed by the dry-run `Plan` construction in `plan_tool/create.py:_apply_step_split`.

- **Carry concept IDs through structured proposals.** Extend `plan_tool/create.py:_parse_steps_json` to validate and populate `Step.concept_ids` when the field is present. Use the validation rules supplied by step 1 rather than adding a second ID format or silently dropping malformed values.

- **Ask for a distribution, not new concepts.** Update the inline request in `plan_tool/create.py:_propose_step_split` to include the target’s existing `concept_ids` and require every ID to appear on at least one of the two proposed halves, with no additional IDs. Keep the existing refactor-first, feature-second shape and deterministic dependency wiring.

- **Treat a bad proposal as unusable.** `plan_tool/create.py:_propose_step_split` should reject a parsed two-step response whose union does not exactly match the target’s IDs. This avoids asking the operator to approve a proposal already known to violate ownership, while `_apply_step_split` remains the final defense for every caller.

- **Preserve the create review loop.** `plan_tool/create.py:_review_step_change_types` should continue to leave the original step unchanged and re-prompt when `_propose_step_split` returns no usable replacement pair. A successful proposal carries its validated distribution into `_apply_step_split`.

- **Use a conservative rule for title-only splits.** `plan_tool/detail.py:split_step` has replacement titles but no evidence for deciding which half owns which concept. Copy the target’s complete `concept_ids` list onto every replacement. This preserves every explicit owner link without guessing from titles; later operator review may narrow duplicate ownership if needed.

- **Preserve dry-run truthfulness.** The replacements used by `plan_tool/detail.py:split_step` must carry the same ownership in both real and `dry_run=True` paths. The preview should represent a split that would pass the real conservation check, while still performing no plan write, detail migration, or authoring.

- **Keep escalation on the shared contract.** `plan_tool/launcher.py:escalate_to_split` already obtains replacements from `plan_tool.create._propose_step_split` and writes only after `plan_tool.create._apply_step_split` succeeds. Preserve that ordering. If a proposal is missing or invents concept IDs, return `proposal-unusable`; if the final transform still rejects it, retain the existing `recommended` outcome and leave the plan unchanged.

- **Do not infer ownership from other fields.** Files, titles, `change_type`, rationale, dependencies, and generated detail are not substitutes for `concept_ids`. The rejected alternative is to derive ownership from title similarity during the split, because that would conflict with step 5’s exact-link completeness rule.

- **Do not mutate the concept record.** Splitting changes plan-step ownership links only. It must not rewrite concept decisions, deferrals, stable IDs, or sign-off state in the concept sidecar.

## Tests

- `tests/test_create.py:test_parse_steps_json_preserves_concept_ids` — valid proposal ownership lists populate `Step.concept_ids`.
- `tests/test_create.py:test_parse_steps_json_rejects_malformed_concept_ids` — malformed proposal ownership is rejected rather than dropped.
- `tests/test_create.py:test_apply_step_split_redistributes_all_concept_ids` — disjoint replacement lists whose union equals the target set succeed.
- `tests/test_create.py:test_apply_step_split_allows_repeated_cross_half_ownership` — the same target ID may appear on multiple replacements.
- `tests/test_create.py:test_apply_step_split_rejects_dropped_concept_id` — omitting any target ID raises `CreateError` and leaves the input list unchanged.
- `tests/test_create.py:test_apply_step_split_rejects_invented_concept_id` — adding an ID absent from the target raises `CreateError`.
- `tests/test_create.py:test_apply_step_split_empty_ownership_requires_empty_replacements` — an unowned target cannot gain concept IDs through splitting.
- `tests/test_create.py:test_propose_step_split_rejects_nonconserving_distribution` — a parseable two-step response with missing or extra IDs is unusable.
- `tests/test_create.py:test_review_split_preserves_concept_ids` — the create review loop writes a valid proposed distribution without losing target ownership.
- `tests/test_detail.py:test_split_step_copies_concept_ids_to_each_named_half` — an operator-named split assigns the complete target list to every replacement.
- `tests/test_detail.py:test_split_step_dry_run_preserves_concept_ids_without_writing` — preview construction passes the ownership rule and leaves disk unchanged.
- `tests/test_detail.py:test_split_step_authors_halves_without_losing_concept_ids` — detail generation and subsequent plan writes retain ownership on both halves.
- `tests/test_launcher.py:test_escalate_applied_split_preserves_concept_ids` — an accepted structural escalation writes a conserving distribution.
- `tests/test_launcher.py:test_escalate_rejects_proposal_that_drops_concept_id` — an invalid proposal returns `proposal-unusable` and leaves the plan unchanged.
- `tests/test_launcher.py:test_escalate_rejects_proposal_that_invents_concept_id` — an extra proposal ID cannot reach confirmation or publication.

### Test-creation order (feature step)

1. Add the `_apply_step_split` conservation tests in `tests/test_create.py` with the core predicate.
2. Add proposal parsing and `_propose_step_split` rejection tests in `tests/test_create.py` with the structured split changes.
3. Add `split_step` real, dry-run, and authoring tests in `tests/test_detail.py` with the conservative copy rule.
4. Add applied and rejected escalation tests in `tests/test_launcher.py` with the launcher integration.
5. Run the existing split, renumbering, detail migration, and `BLOCKED-STRUCTURAL` suites to confirm their prior behavior remains intact.

Every new test and the existing split-related tests in all three test files must be green before this step is considered finished.

## Acceptance criteria

- `plan_tool/create.py:_apply_step_split` succeeds only when the union of replacement `concept_ids` exactly equals the target step’s concept-ID set.
- A valid split may place the same concept ID on more than one replacement.
- A split that drops or invents any concept ID raises or returns the caller’s existing non-applied outcome without changing the plan.
- `plan_tool/create.py:_propose_step_split` rejects a parseable proposal whose ownership distribution does not conserve the target IDs.
- `plan_tool/detail.py:split_step` copies every target concept ID to every operator-named replacement in real and dry-run flows.
- `plan_tool/launcher.py:escalate_to_split` never confirms or writes a proposal known to violate concept ownership.
- Successful create, on-demand, Phase B, and `BLOCKED-STRUCTURAL` splits preserve every target concept ID on at least one committed replacement.
- Split operations do not modify the persisted concept record or structured deferral state.
- All new tests in `tests/test_create.py`, `tests/test_detail.py`, and `tests/test_launcher.py` pass alongside the existing split suites.

## References

- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Use the array, string, and uniqueness semantics when validating structured `concept_ids` proposal data.
- [Structured outputs — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Read for schema-constrained split responses and invalid-output handling.
- [Structured model outputs — OpenAI API](https://developers.openai.com/api/docs/guides/structured-outputs) — Read for equivalent JSON Schema-conforming behavior through the injected backend.

## Deferred

- **Merge ownership rules** — step 7 owns unioning concept IDs when several steps become one.
- **Re-ground ownership rules** — step 8 owns preserving or revising ownership when plan structure is re-derived.
- **Scope-out ownership rules** — step 9 owns concept links when steps leave committed scope.
- **Automatic narrowing after title-only splits** — assigning a concept to only one named half requires an explicit operator decision; this step uses safe duplicate ownership instead of guessing.
