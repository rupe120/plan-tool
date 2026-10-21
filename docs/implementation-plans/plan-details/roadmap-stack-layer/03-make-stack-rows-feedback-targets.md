# Step 3 — Make stack rows feedback targets and revisable through candidates

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Registers the `stack` collection (the row type and collection name step 1 mints) in every place that decides which rows feedback can target, edit, add, or remove. Those places are the stage-row policy, the candidate and revision row-type maps, the revision payload and patch checks, and the candidate-delta selector prompt.
- The key decision is the policy entry. The `concern` field is fixed on edit, and rows are addable. This lets a candidate introduce the stack on an existing roadmap that has none.
- Adding rows is the opposite of `hosting`, which can be neither added nor removed. `stack` therefore must not be listed with the "non-addable" relationless collections, even though a stack row carries no anchor ids.
- Files: `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_candidate.py`, `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate_context.py`, `plan_tool/roadmap_revision.py`, `plan_tool/roadmap_revision_patch.py`, `plan_tool/prompts/roadmap-candidate-delta-selector.md`, and the four test files.
- On green:
  - feedback targeting a stack row can be revised in place without changing its concern;
  - a candidate can add and replace stack rows;
  - the selector prompt lists `stack` under `constraints`.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the gap that keeps the stack out of the feedback lifecycle
- [Input](#input) — what steps 1 and 2 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — policy, maps, payload, prompt, and what must not change
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- Step 1 gives `ConstraintsArtifact` a `stack` collection and step 2 gates it. Neither makes it reachable from the feedback lifecycle.
- Every collection is looked up by name in several tables:
  - `plan_tool/roadmap_artifacts.py:_STAGE_ROW_TYPE_BY_COLLECTION`;
  - `plan_tool/roadmap_candidate.py:_ROW_TYPE_BY_CLASS_NAME` and `_DELTA_ROW_TYPES`;
  - `plan_tool/roadmap_candidate_run.py`'s class-name to collection map (the one containing `"HostingRow": "hosting"`);
  - `plan_tool/roadmap_revision.py:_PAYLOAD_BY_ROW_TYPE`.
- A collection missing from those tables is not a legal target. Feedback on a stack row therefore cannot be edited, and a candidate cannot introduce a stack.
- The plan's acceptance round-trip needs an existing roadmap to gain its stack through the ordinary feedback and candidate lifecycle, not through regeneration.

## Input

- **Step 1 output.** A stack row type with an id, a `concern`, and either a `choice` or an `open` marker, plus the `ConstraintsArtifact.stack` collection (`None`, `()`, or a tuple).
- **Step 2 output.** A gate that refuses a partial or empty stack on an artifact that carries the collection.
- **Names come from the landed code.** Step 1 had not landed when this file was written; HEAD has no `stack` symbol in `plan_tool/roadmap_artifacts.py`. Use the landed row-type, field, and collection names. They win over every name used here.
- **Consequence of step 2.** Because totality binds once the collection is present, a delta that introduces the stack on a stack-less roadmap must add all three required concerns in one candidate. A one-row delta is refused by the gate. This step does not relax that rule.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py`:
    - add the `stack` entry to `_STAGE_ROW_OPERATION_POLICIES`;
    - add the entry to `_STAGE_ROW_TYPE_BY_COLLECTION`;
    - add the stack row type to the `StageRow` union;
    - make `stage_row_collections` return the stack rows when the collection is present and not `None`.
  - `plan_tool/roadmap_candidate.py`: add the collection to `_ROW_TYPE_NAMES`, `_ROW_TYPE_BY_CLASS_NAME`, `_DELTA_ROW_TYPES`, and `_expected_row_type`, plus a `_parse_stage_row` branch.
  - `plan_tool/roadmap_candidate_run.py`: add the class-name to collection mapping beside `"HostingRow": "hosting"`.
  - `plan_tool/roadmap_candidate_context.py`: add the collection and row type wherever it enumerates stage collections and row classes. This file imports `_STAGE_ROW_TYPE_BY_COLLECTION` and `stage_row_collections`, so most of the reach likely comes through the artifacts change. Confirm by running the context tests rather than assuming.
  - `plan_tool/roadmap_revision.py`:
    - add the collection to the `StageRowType` literal and the `StageRow` alias;
    - add a stack payload model and an entry in `_PAYLOAD_BY_ROW_TYPE`;
    - add the collection to `_STAGE_ADD_ROW_TYPES["constraints"]`;
    - add an entry to `TEXT_FIELDS_BY_ROW_TYPE`.
  - `plan_tool/roadmap_revision_patch.py`: extend the fixed-field error text and any `isinstance` branches that name `HostingRow`.
  - `plan_tool/prompts/roadmap-candidate-delta-selector.md`: add `stack` to the `constraints` collection list.
  - `tests/test_roadmap_candidate.py`, `tests/test_roadmap_candidate_run.py`, `tests/test_roadmap_revision.py`, `tests/test_roadmap_revision_patch.py`: add the cases under Tests.

## Implementation

**Foundational logic.** A collection's operation boundary is declared once, in `StageRowOperationPolicy`, and every other table only has to know the collection exists. The work is to declare the stack's boundary once and register the name everywhere a sibling collection is registered.

**Policy entry.** Add a stack entry beside `hosting` and `stores` in `_STAGE_ROW_OPERATION_POLICIES`.
- `immutable_fields=("concern",)`. `stage_row_edit_preserves_fixed_fields` then rejects an edit that moves a row to another concern. This is the same mechanism `hosting` uses for `facet`.
- `allow_add=True`, so a candidate can introduce the stack. This is the deliberate difference from `hosting`.
- `allow_remove=False`, required. A candidate cannot drop a stack row or the whole collection, so a recorded stack can never silently read as "stack not recorded" after a candidate; `hosting` is the precedent. This step owns the refusal: a candidate is a set of row operations on its predecessor, no operation drops a collection key, and emptying the collection needs every row removed, which this policy refuses. Step 2's totality gate refuses a partial stack as a second line.
- `allow_prose=False`, matching `stores`. A stack row carries its own `choice` text, so no row-owned prose span is needed.
- The implementer may choose differently on prose only. If a choice changes, write it down in the policy comment so it is explicit.

**Do not list `stack` as non-addable.**
- `_RELATIONLESS_ADD_ROW_TYPES` in `plan_tool/roadmap_candidate.py` groups collections whose rows declare no anchor ids. Its sorted tuple `NON_ADDABLE_ROW_TYPES` feeds `_build_non_addable_collections_notice` in `plan_tool/roadmap_candidate_run.py`.
- A stack row also declares no anchors, so copying the `hosting` pattern by reflex would block the one capability this step exists to add.
- Check how the add path decides a row has "reached" an anchor. That check lives in `materialize_candidate` and the `_add_row_anchor_diagnostic` path. Make the stack follow the path that needs no anchor. Do this with a policy-driven check, not a new name list, if that is the smallest change.
- Confirm that `add-row` for a stack row passes `parse_candidate_delta` end to end.

**Row type maps.**
- Register the new collection wherever `HostingRow` is registered, as listed under Files.
- `_parse_stage_row` takes a new branch with `_require_keys`. It requires `id` and `concern` and takes `choice` and `open` as optional, mirroring the hosting branch's use of `_text` and `_nullable_text`.
- Enforce the exactly-one-of rule only if step 1 enforces it at parse time. Otherwise leave it to the gate.

**Revision payload.**
- Add a stack payload model on `_StageWireModel`. Use `StackRowPayload` unless step 1 chose a different row-type name, and give it a `to_row()` method.
- Register it in `_PAYLOAD_BY_ROW_TYPE`.
- `_preserve_omitted_row_metadata` keeps omitted optional fields on an edit, and an explicit null clears them. Decide whether `choice` and `open` are metadata under that rule. They must not be. An edit that swaps a `choice` for `open` is the main legal edit and must say so explicitly.
- Fix the hardcoded error text "a hosting edit must preserve its fixed facet" in `roadmap_revision.py` and the matching text in `roadmap_revision_patch.py`. Make both messages name the collection and the fixed field instead of "hosting" and "facet", for example by building them from `StageRowOperationPolicy.immutable_fields`. The existing hosting tests pin the old wording, so update them to the new text.

**Text fields.**
- `TEXT_FIELDS_BY_ROW_TYPE` is the only local presentation surface, and "a collection absent from this table is not a targetable design-row collection".
- Add `"stack": ()`. This matches `dispositions`, so a presentation patch has nothing to rewrite. Edits go through the row replacement path instead.
- Check that `hosting` and `stores` are intentionally absent from this table before copying their pattern. If the lookup at `TEXT_FIELDS_BY_ROW_TYPE[collection]` is reached for a stack target, the empty entry is the safe choice.

**Feedback targeting.** A feedback row whose target is a stack row id resolves through the live-row lookup that builds `StageFeedbackAuthority`, which reads `_constraints_identity_rows`; step 2 adds the stack term there, and this step relies on it and adds no change to `roadmap_gates.py`. Once the collection appears in `stage_row_collections`, that lookup finds it. An artifact-level feedback target gets `allow_add=True` with no further change.

**Selector prompt.**
- Add `stack` to the `constraints` bullet in the collection list of `plan_tool/prompts/roadmap-candidate-delta-selector.md`.
- The prompt restates the contract inline instead of citing a FORMAT doc, so the new name must appear in the prompt text itself. Keep the placeholders unchanged.
- The prompt text says only a plan addition may carry `ordering`, and that every eligible `add-row` carries a `prose_amendment`. For `stack`, add one sentence that `add-row` needs no prose amendment, because the policy sets `allow_prose=False`. Check how `stores` is handled in the prompt first and follow that.

**Constraints that are not free to vary.**
- Existing roadmaps with no stack must behave as before. `stage_row_collections` must not return a `stack` key when the collection is `None`. Check how the function treats the empty `hosting` tuple and keep absent and empty distinct.
- Impact participation: `stage_collection_participates_in_impact` is true when `allow_add or allow_remove`, so an addable stack joins the impact graph. Confirm that `impact_node_collections` and the closure code handle a row with no declared relations.
- Do not touch accepted versions. This step changes what a candidate may propose; it does not rewrite any stored artifact.

**Rejected alternative.** A separate stack-only proposal route. It would duplicate the feedback lifecycle, and the plan's out-of-scope fence rules out new routes beside the ordinary one.

## Tests

Existing files get new cases. Build fixtures by constructing row dataclasses directly, as the neighbouring tests do.

### Tests for this step

All of these must be green before the step is done. They cover only behavior this step changes.

`tests/test_roadmap_revision.py`
- `test_stack_policy_fixes_concern_and_allows_add` — `stage_row_operation_policy("stack")` has `allow_add` true and `immutable_fields == ("concern",)`, and differs from `hosting` on `allow_add`.
- `test_stack_policy_refuses_row_removal_so_a_recorded_stack_cannot_become_not_recorded` — `stage_row_operation_policy("stack")` has `allow_remove` false, and a candidate delta removing a stack row is refused.
- `test_stack_edit_may_change_choice_but_not_concern` — a `replace-row` that swaps `choice` for `open` parses. One that changes `concern` raises `RevisionContractError`.
- `test_stack_is_a_targetable_collection` — feedback naming a stack row id gets an authority with `target_row_type == "stack"` and `allow_edit` true.
- `test_constraints_stage_allows_stack_additions` — `_STAGE_ADD_ROW_TYPES["constraints"]` includes the stack and `domain` does not.
- `test_stack_edit_error_names_collection_and_field` — the fixed-field error names `stack` and `concern`, not "hosting". Update the existing hosting assertion to the new wording.

`tests/test_roadmap_revision_patch.py`
- `test_stack_edit_that_changes_concern_is_a_merge_error` — `merge_stage_revision` raises `RevisionMergeError` and the message names the row.
- `test_stack_edit_preserves_every_other_row_and_the_body` — only the targeted stack row changes.
- `test_absent_stack_stays_absent_after_an_unrelated_edit` — a `None` stack stays `None` and renders no `stack` key. This pins the missing-versus-empty split from step 1.

`tests/test_roadmap_candidate.py`
- `test_add_row_is_accepted_for_stack` — `parse_candidate_delta` accepts an `add-row` for `stack` with no anchor ids.
- `test_stack_is_not_in_the_non_addable_row_types` — `NON_ADDABLE_ROW_TYPES` does not contain `stack` while it still contains `hosting`. This pins the deliberate difference from `hosting`.
- `test_replace_row_cannot_move_a_stack_row_to_another_concern` — materialization refuses the replacement.
- `test_candidate_introduces_a_complete_stack_on_a_stackless_roadmap` — adding all three concerns materializes with a green stack gate. A delta adding fewer is refused by that gate.
- `test_class_name_maps_cover_the_stack_row` — the stack row class appears in `_ROW_TYPE_BY_CLASS_NAME` and `_DELTA_ROW_TYPES`.

`tests/test_roadmap_candidate_run.py`
- `test_non_addable_notice_omits_stack` — the rendered notice names `hosting` and not `stack`.
- `test_selector_prompt_lists_stack_under_constraints` — the rendered prompt names `stack` in the `constraints` bullet and has no unresolved `${` placeholder.
- `test_stack_row_class_name_maps_to_its_collection` — the run module's class-name map resolves the stack row.

Run `uv run pytest tests/test_roadmap_candidate.py tests/test_roadmap_candidate_run.py tests/test_roadmap_revision.py tests/test_roadmap_revision_patch.py -q`, then `uv run pytest -m "not integration" tests/ -q -n auto`. Expect a few existing tests that pin the full collection list to need a stack added, and read each before changing it.

## Acceptance criteria

- `stage_row_operation_policy("stack")` returns `allow_add=True` and `immutable_fields=("concern",)`.
- An edit that changes a stack row's `concern` is refused in both `roadmap_revision.py` and `roadmap_revision_patch.py`.
- A stack row is a valid feedback target, and an artifact-level feedback target can add stack rows to `constraints`.
- `parse_candidate_delta` accepts `add-row` and `replace-row` for `stack`. `NON_ADDABLE_ROW_TYPES` does not contain `stack`.
- A stack-less constraints artifact stays stack-less after any candidate that does not touch the stack.
- `rg -n "stack" plan_tool/prompts/roadmap-candidate-delta-selector.md` finds the `constraints` collection entry.
- The four listed test files pass and the full non-integration suite is green.
- No stored roadmap version is read or rewritten by this step's code paths.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — frozen dataclasses and `replace()`, for the policy and row types.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — for one parametrized test over the collections.

## Applicable guardrails

- **The plan's "## Out of scope", fifth artifact:** this step adds a collection inside `02-constraints.md` and nothing that touches the four-member version layout.
- **The same section, no regeneration of accepted versions:** the step changes only what a new candidate may propose. It must not read or rewrite a stored version.
- **The same section, no narrative-evidence class and no approval block:** do not add a gate, finding class, or refusal for stack content here. Step 2 owns the totality gate.
- **The same section, no judgment of a choice:** the policy and prompt text constrain structure only. They must not say whether a choice is good.
- **The same section, closed vendor vocabulary:** do not add a list of products to the prompt or the payload model. `choice` stays free text.
- **The same section, the Integration HTML aid:** nothing in this step touches review rendering.

## Deferred

- Review callouts for the stack in the candidate-review markdown and the generated `INDEX.md` — belongs to the plan's review-surface step, not this one.
- Plan-seed `## Stack` propagation and the audit treatment of a plan's stack — separate plan, `roadmap-stack-propagation`.
- First-publish and stage-prompt support for generating the stack — a stage-run step in this plan, not the candidate route.
- `ROADMAP_FORMAT.md` and `docs/how-to/roadmap.md` text for stack feedback — the plan's docs step.
- Consolidating the several per-collection name maps (`_ROW_TYPE_BY_CLASS_NAME`, `_DELTA_ROW_TYPES`, `_expected_row_type`, `_PAYLOAD_BY_ROW_TYPE`) into one — a cross-module refactor, to be filed in `BACKLOG.md` with the normalization used to confirm identity. This step adds one entry to each and consolidates none.
- A stack-specific removal path — removal stays refused by the policy because step 2's totality gate would refuse the result.
