# Step 1 — Add `settle_pending_decision` to the roadmap artifact leaf and correct `DecisionStatus`'s hand-edit docstring

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one pure helper, `settle_pending_decision(artifact, *, decision_id)`, to `plan_tool/roadmap_artifacts.py`. It returns a copy of any of the four roadmap artifacts with exactly one Roadmap-derived `pending` decision moved to `settled`. Every other field of that row, every other row, the review collections, and the body stay the same objects. The key design decision is a fixed-direction transition with no status parameter. The helper refuses a missing id, a duplicated id, an inherited row, and a row that is already settled, and it checks inheritance before status. The step also rewrites `DecisionStatus`'s docstring, which today names a hand edit as the way to accept a decision. `replace_design_row` keeps refusing enum fields, and no existing write path changes. When the step is green, the rendered artifact before and after settlement differs by exactly one line (`status: pending` → `status: settled`) on all four artifact types. Later steps rely on this as their field-preservation contract.

## Table of Contents

- [Why](#why) — why the plan needs one owner for the transition, and why neither existing mutation helper can be that owner
- [Input](#input) — the row type, render contract, and shared helpers this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches and the symbols deliberately left unchanged
- [Implementation](#implementation) — the helper's contract, the order of its checks, the docstring fix, and the rejected alternatives
- [Tests](#tests) — the named cases, which ones are green at HEAD, and which land with the helper
- [Acceptance criteria](#acceptance-criteria) — the checks a reviewer can run
- [References](#references) — plan-level references that bear on this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind the helper, and where breaking them is tempting
- [Deferred](#deferred) — neighboring work this step leaves to later steps or the backlog

## Why

No code path at HEAD changes only a decision's `status`. `replace_design_row` refuses any enum-valued field, and it does so on purpose: its guard comment names `DecisionStatus`. `tests/test_roadmap_artifacts.py::test_replace_design_row_rejects_a_str_backed_enum_field` pins that refusal. `replace_stage_row` swaps in a whole caller-built row, so every caller would have to rebuild `chosen_option`, `rejected_alternatives`, `rationale`, `anchor`, and `source` by hand and prove they were copied correctly. Three later steps build settled content: the preflight candidate in step 2, the un-enrolled publish in step 4, and the enrolled version bytes in step 5. Without one owner, each of them would re-derive the rule "only `status` changes, on exactly one Roadmap-derived row", and three copies of that rule can drift. Separately, the `DecisionStatus` docstring still says an operator accepts a `PENDING` decision "by editing its status to it". That is false for any stage with a recorded baseline: `status` is part of `canonical_projection`, so a hand-edited artifact fails source admission on re-entry (`roadmap.py:_admit_loaded_stage_artifact`). Fixing that claim is in this step's scope because the claim lives in this step's file.

## Input

- **`DecisionRow`** (`plan_tool/roadmap_artifacts.py`). Fields: `id`, `chosen_option`, `rejected_alternatives`, `rationale`, `anchor`, `status: DecisionStatus`, `source: Optional[str] = None`. It is a frozen dataclass, so `dataclasses.replace` is the only way to derive a changed row. A non-`None` `source` marks an inherited row. `roadmap_gates.check_inherited_decisions` requires inherited rows to be settled, but parsing does not enforce that, so an inherited `pending` row can still reach this helper.
- **`decisions` exists on all four artifact dataclasses**: `DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, and `PlansArtifact`. That lets `replace(artifact, decisions=...)` work on the `RoadmapArtifact` union with no `isinstance` branching.
- **The render contract** (`_decision_mapping`). Status renders last, as `row.status.value`, and the other keys depend only on the row's other fields. That is why a status-only change produces a one-line rendered difference. The contract is about **rendered** text. It says nothing about non-canonical on-disk bytes. Step 2's render-canonical check is what makes `render(parse(source)) == source` true for the artifact being settled.
- **Shared private helpers, reused unchanged:** `_exactly_one_index` (its "must occur exactly once, found N" `ValueError` covers both a missing id and a duplicated id) and `_replace_tuple_item`.
- **Already-implemented signal:** the heuristic hit on `class DecisionStatus` is the enum this step documents, not prior work. `rg -n "def settle|status=DecisionStatus.SETTLED" plan_tool/` returns nothing at HEAD, so the transition helper does not exist yet.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py`:
    - Add `settle_pending_decision` in the row-mutation block beside `replace_design_row`.
    - Rewrite the `DecisionStatus` docstring's second paragraph.
    - Make no other change. `replace_design_row`, `replace_stage_row`, `append_stage_row`, `remove_stage_row`, `_coerce_status`, `_decision_mapping`, every `parse_*`, `render_*`, and `load_*` function, and `StageRowOperationPolicy` all stay unchanged.
  - `tests/test_roadmap_artifacts.py`:
    - Add `settle_pending_decision` to the module import list.
    - Add a `# Decision settlement` section next to the existing `replace_design_row` tests.
    - Add one new `replace_design_row` status-refusal case beside the existing one. The existing test stays unchanged.

## Implementation

**The contract `settle_pending_decision(artifact: RoadmapArtifact, *, decision_id: str) -> RoadmapArtifact` must satisfy:**

- **It returns an artifact of the same type** in which the selected row equals `replace(row, status=DecisionStatus.SETTLED)` and sits at the same tuple index.
- **Every other decision row is the same object** (`is`), not just an equal one.
- **Every other attribute of the artifact is the same object**, including `feedback` and `removals`. `body` is equal.
- **Status is compared by identity** (`row.status is DecisionStatus.PENDING`), matching the idiom `roadmap_gates.py` already uses.
- **It stays pure.** No filesystem access, no new imports, no first-party import. The module is a stdlib-plus-YAML leaf, and `test_leaf_imports_no_first_party_module` guards that.

**The refusals must run in this order**, each raising `ValueError` whose message names `decision_id`:

1. **The id must occur exactly once in `artifact.decisions`.** Reuse `_exactly_one_index` with a `"decision {decision_id!r}"` label. It already refuses both zero matches and two or more. A duplicated id must never settle the first match.
2. **The row must be Roadmap-derived** (`source is None`). Refuse an inherited row whatever its status is.
3. **The row must be `PENDING`.** Refuse a row that is already `SETTLED`. Do not return it unchanged: the helper is a transition, not a setter that tolerates repeats.

- **The inheritance check must come before the status check.** An inherited row is normally settled, so checking status first would report every inherited row as "already settled". That would hide the real reason and leave the inherited-row refusal untested. The plan's Architecture ("Scope of the transition") states the same ordering for the operator-facing route.
- **Use `ValueError`, not `RoadmapArtifactError`.** The sibling mutation helpers (`replace_design_row`, `append_stage_row`, `_exactly_one_index`) raise `ValueError`. `RoadmapArtifactError`'s own docstring limits it to unreadable or off-shape artifacts.
- **These refusals are a backstop, not the operator-facing vocabulary.** Step 2's preflight owns one named refusal per rejection class and checks them before building its candidate. That matches the existing precedent in `plan_tool/roadmap_revision_patch.py:merge_feedback_revision`, which pre-checks and then wraps `replace_design_row`'s `ValueError`. The helper's checks exist so that no caller can produce a non-conforming artifact, even one that skips the preflight.

**The `DecisionStatus` docstring fix:**

- Replace the sentence claiming acceptance happens "by editing its status to it".
- Say that `settle_pending_decision` moves one Roadmap-derived row from `PENDING` to `SETTLED` and changes nothing else.
- Say that a hand edit of `status` makes a stage with a recorded baseline drift from that baseline, so re-entry refuses it.
- Keep the existing "queue that can be worked to zero" point.
- Keep it to a few lines, per the repo's terse-comment rule.
- **Do not name a CLI flag.** Step 6 creates the flags, and a docstring written now cannot point to something that does not exist yet.
- **Do not claim the helper is the only way a row becomes `SETTLED`.** Stage authoring, un-enrolled revisions, and enrolled candidates can all still write it.
- The other two docstrings stay accurate as they are. `DecisionRow`'s "operator confirming a `PENDING` decision" is neutral. `FeedbackState`'s claim that `--reopen-feedback` is the only tool exception stays true, because settlement never moves a feedback row.

**What must not change.** These guards are what keep "no existing write path is narrowed or retired" true:

- **`replace_design_row` keeps its `isinstance(current_value, enum.Enum)` refusal.** It still refuses `field="status"` even when the value is a real member. Together with `plan_tool/roadmap_revision.py:TEXT_FIELDS_BY_ROW_TYPE`, which lists only `("rationale",)` for `decisions`, this keeps `status` out of the unconfirmed `--revise-feedback` path.
- **`replace_stage_row` gets no new status guard.** `roadmap_revision_patch._apply_stage_material_operation` and `roadmap_candidate`'s apply path use it to carry whole-row edits, which today can include a status change. Narrowing it is out of scope.
- **`_coerce_status` and the parse/render functions are unchanged.** Model-authored stages and parsed files keep their current status behavior.

**Rejected alternatives:**

- **A general `set_decision_status(artifact, id, status)`.** It could also move `settled → pending`, a reopen route the plan's Out of scope excludes, and it is the general version of a fixed transition.
- **Widening `replace_design_row` to accept validated enum values.** That removes the guard that keeps `status` out of the text-revision path.
- **A typed exception carrying a closed reason token.** Step 2 owns the refusal names. A second reason vocabulary in the leaf would mean two sources for one set of names.
- **A helper that takes several decision ids.** That is the batch form the plan forbids.

## Tests

All cases go in `tests/test_roadmap_artifacts.py`, built from the module's existing fixtures and frontmatter helpers (`DOMAIN_TEXT`, `_constraints_frontmatter`, `_components_frontmatter`, `_plans_frontmatter`, `_domain_with_feedback`, `_feedback_row`). Approximately 8 test functions, some parametrized over the four artifact types. `CONSTRAINTS_TEXT`'s only decision (`decision-2`) is `settled`, so the constraints case flips it to `pending` through `_constraints_frontmatter()` before parsing.

**Green at HEAD — write this first; it guards the refusal while the helper is added:**

- `test_replace_design_row_refuses_status_even_when_the_value_is_a_real_member` — `replace_design_row(..., field="status", value="settled")` raises `ValueError` ("no replaceable text field"). This pins that the settle helper is the only status route in the leaf and that a valid member does not get through. The existing `test_replace_design_row_rejects_a_str_backed_enum_field` stays unchanged.

**Land with the helper.** Adding the import breaks the whole module at HEAD, so these cannot be written first:

- `test_settle_pending_decision_changes_only_the_selected_rows_status` — on a domain artifact with two decisions and both review collections:
  - the selected row's `status` is `DecisionStatus.SETTLED`;
  - its `id`, `chosen_option`, `rejected_alternatives`, `rationale`, `anchor`, and `source` equal the originals;
  - the other decision `is` the original object;
  - every other collection, `feedback`, and `removals` `is` the original, and `body` is equal.
- `test_settle_pending_decision_changes_exactly_one_rendered_line` (parametrized over the four parse/render pairs) — rendering before and after differs in exactly one line, `status: pending` → `status: settled`, and `parse(render(after)) == after`. This is the field-preservation contract steps 2, 4, and 5 build on.
- `test_settle_refuses_an_unknown_decision_id` — `ValueError` naming the id.
- `test_settle_refuses_a_duplicated_decision_id_rather_than_settling_the_first` — two rows sharing an id raise `ValueError` ("found 2"). This pins that a duplicate never quietly settles the first match.
- `test_settle_refuses_an_inherited_decision_before_checking_its_status` (parametrized over `settled` and `pending` on a row with `source` set) — the message names inheritance and never the not-pending reason. This pins the check order.
- `test_settle_refuses_an_already_settled_decision_rather_than_returning_it_unchanged` — pins that the helper is a one-way transition, not a setter that tolerates repeats.
- `test_settle_never_touches_feedback_targeting_the_decision` — a feedback row with `target={"kind": "row", "row_id": "decision-1"}` in `awaiting-review`, with a `proposed_response`, comes back as the same object with its `state` unchanged.

**Unchanged and still green:** `test_leaf_imports_no_first_party_module`, `test_leaf_declares_no_invoker_seam`, and every existing `replace_design_row` / `replace_stage_row` / round-trip test.

**Verify by breaking the code, not by reading it.** Each change below must turn at least one case red:

| Deliberate break | Case that must go red |
| --- | --- |
| Drop the `source` check | The inherited-row case |
| Swap the two checks | The inherited-row case (its message) |
| Settle every row with a matching id | The duplicate-id case |
| Accept `SETTLED` input | The already-settled case |
| Rebuild the row by hand and drop a field | The rendered-line case |

### Tests for this step

The nine cases above: one `replace_design_row` refusal case that is green at HEAD, and eight settle cases that land with the helper. Every one must be green before this step counts as finished, along with the unchanged tests listed above. The list covers only the behavior this step changes: the new transition, its refusals, and the unchanged `replace_design_row` refusal. It adds no cases for publication, receipts, or named refusal reasons, which later steps own.

## Acceptance criteria

- `settle_pending_decision(parse_domain_artifact(DOMAIN_TEXT), decision_id="decision-1")` returns a `DomainArtifact` whose `decision-1` has `status is DecisionStatus.SETTLED`, with every other field equal to the input.
- For each of the four artifact types, rendering before and after settlement differs in exactly one line (`status: pending` → `status: settled`).
- The helper raises `ValueError` naming the id for:
  - an unknown id;
  - a duplicated id;
  - an inherited row of either status, where the message names inheritance;
  - an already-settled Roadmap-derived row.
- `replace_design_row(..., field="status", value="settled")` still raises `ValueError`, and `test_replace_design_row_rejects_a_str_backed_enum_field` is unchanged and green.
- `settle_pending_decision`'s signature takes exactly `artifact` and a keyword-only `decision_id`, with no status parameter and no collection of ids.
- `rg -n "by editing its status" plan_tool/` returns nothing. The `DecisionStatus` docstring names `settle_pending_decision` and names no CLI flag.
- The step's diff touches only `plan_tool/roadmap_artifacts.py` and `tests/test_roadmap_artifacts.py`. In the module, only the `DecisionStatus` docstring and the new function change. `replace_design_row` (including its `isinstance(current_value, enum.Enum)` guard), `replace_stage_row`, `_coerce_status`, `_decision_mapping`, and every `parse_*` and `render_*` function are unchanged.
- `test_leaf_imports_no_first_party_module` and `test_leaf_declares_no_invoker_seam` pass unchanged.
- `uv run pytest tests/test_roadmap_artifacts.py -q` passes, and so does `uv run pytest tests/ -q -n auto`.

## References

- **`plan_tool/roadmap_artifacts.py`** (`DecisionStatus`, `DecisionRow`, `FeedbackState`, `replace_design_row`) — the types and the enum-refusing sibling this step extends without widening.
- **`plan_tool/roadmap_revision.py`** (`TEXT_FIELDS_BY_ROW_TYPE`, `preflight_feedback_revision`) — the precedent for refusing inherited rows unconditionally (`source is not None`), and the text-only allowlist this step leaves unchanged.
- **`plan_tool/roadmap_gates.py`** (`check_inherited_decisions`, `check_settled_decisions`) — why inherited rows are normally settled, which explains the check order, and the gate this step does not touch.
- **`docs/how-to/roadmap.md` §4** ("Settle a pending decision or re-gate an existing stage") — the hand-edit procedure behind the docstring claim this step corrects. The doc itself changes in step 7.
- **`ROADMAP_FORMAT.md`** "Decision row forms" — the schema prose the new helper must not contradict. Step 7 owns its edits.

## Applicable guardrails

- **The plan's "## Scope guardrails": only `pending → settled` on exactly one Roadmap-derived row.**
  - The helper takes one `decision_id` and no target status, and refuses inherited, non-pending, and non-unique rows.
  - The tempting site is the signature. A `status` or `ids` parameter "for flexibility" would build the reopen or batch route this fence forbids.
  - Check: `rg -n "def settle_pending_decision" plan_tool/roadmap_artifacts.py` shows exactly the two-argument signature.
- **The plan's "## Scope guardrails": other fields and other rows are never mutated.**
  - This is the helper's whole contract, pinned by identity (`is`) assertions and the one-line rendered-difference test.
  - Build the row with `replace(row, status=...)`, never by constructing a new `DecisionRow` by hand.
- **The plan's "## Scope guardrails": the cited feedback row's `FeedbackState` is never mutated.**
  - The helper takes no feedback argument and returns the `feedback` tuple unchanged, pinned by the feedback-untouched case.
- **The plan's "## Scope guardrails" and "## Out of scope", batch/bulk settlement.**
  - Exactly one id per call. No loop over ids anywhere in this step.
- **The plan's "## Out of scope", `check_settled_decisions` and a decision reopen route.**
  - This step does not edit `plan_tool/roadmap_gates.py`.
  - This step adds no `settled → pending` path.

## Deferred

- **Named, operator-facing refusal reasons, and the receipt-safe id check** (`RECEIPT_SAFE_ID_RE`) — step 2's preflight owns both. The helper's `ValueError`s are a backstop, not a vocabulary.
- **Baseline admission, render-canonical checks, and staleness digests** — step 2. This step's byte contract covers rendered text only.
- **Writing settled bytes to disk or into a version record** — steps 4 and 5.
- **Retiring the hand-edit settlement instructions in the docs** (`docs/how-to/roadmap.md` §4, `ROADMAP_FORMAT.md` Decision status, and the rest of step 7's list) — step 7. This step fixes only the docstring in its own file.
- **`plan_tool/cli/roadmap_cmd.py:_newly_settled_summary_lines`'s advice to "set its status to 'pending'"** — this is also a hand-edit status instruction, but for the reverse transition (`settled → pending`). The plan's Out of scope excludes a decision reopen route, and the file is not in this step's list. If that hand edit is confirmed to fail baseline admission, file it in `BUG_BACKLOG.md` rather than widening this step.
- **Merging `settle_pending_decision` with `replace_design_row` or `replace_stage_row`** — not wanted. The three have different contracts: text field only, fixed status transition, and whole caller-built row.
