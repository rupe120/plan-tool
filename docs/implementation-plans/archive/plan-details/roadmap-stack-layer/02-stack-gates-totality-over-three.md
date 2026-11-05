> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add stack gates: totality, unknown-concern and duplicate-id reports, and stack ids in the anchor union

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Adds one stack gate to `plan_tool/roadmap_gates.py` and registers it in `CONSTRAINTS_GATES` next to `check_hosting_totality`. It reports a missing required concern, an unknown concern, a duplicate stack id, a second row for an already-present concern, and a row that is not exactly one of chosen or `open`.
- Adds stack ids to the anchor union in `_envelope_rows`, so a decision in the constraints or components stage can anchor to a stack row.
- On green, a stack-less artifact passes every gate-envelope call, including a first run that omitted the collection, which the first-run output and `INDEX.md` then show as "stack not recorded". An artifact that carries the collection, including a candidate that introduces a partial or empty one, is refused for a missing concern. A concern recorded as `open` is accepted.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the compatibility and visibility problems the gate solves
- [Input](#input) — what step 1 hands this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — gate, signal, anchor union, and what must not change
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth reading for this step
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs to other steps

## Why

- Step 1 gives `ConstraintsArtifact` a `stack` collection, but nothing checks it. A candidate could drop a required concern, repeat an id, or invent a concern name, and every gate would pass.
- Accepted versions are immutable and mostly have no stack. A rule that demands the collection everywhere would refuse every unrelated candidate over those versions. The rule must therefore bind on what the artifact carries and never on absence. A first run that omits the collection is not refused: the callouts show "stack not recorded", so the omission is seen rather than blocked (decided 2026-10-08).
- `check_decision_records` resolves a decision anchor against `_envelope_rows`. Stack ids are not in that union today, so a pending decision about an undecided stack concern has nothing to anchor to.

## Input

- **Step 1 output.** `ConstraintsArtifact.stack` is `None` (not recorded), `()` (present and empty), or a source-ordered tuple of the stack row type. Duplicate ids and unknown concerns survive parsing as separate rows. This step reports both.
- **Names come from the landed module.** Step 1 proposed `StackRow`, `STACK_CONCERNS`, and row fields `id`, `concern`, `choice`, and `open`. Read the landed `plan_tool/roadmap_artifacts.py` and use what shipped. The landed names win over this file.
- **Not verifiable here.** Step 1 had not landed when this file was written. The stack names above are step 1's proposal, not HEAD.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py`:
    - add the violation kind constants;
    - add the stack gate and register it in `CONSTRAINTS_GATES`;
    - add stack rows to the constraints entry of `_envelope_rows`, and a stack term to `_constraints_identity_rows` and `_envelope_identity_rows`;
    - import the stack concern constant from `plan_tool/roadmap_artifacts.py`.
  - `tests/test_roadmap_gates.py`: add the cases under Tests and update only assertions that the new gate or the wider anchor union breaks.

## Implementation

**Violation kinds.** Add constants in the style of the hosting ones, for example `VIOLATION_MISSING_STACK_CONCERN`, `VIOLATION_UNKNOWN_STACK_CONCERN`, `VIOLATION_DUPLICATE_STACK_ID`, `VIOLATION_DUPLICATE_STACK_CONCERN` (kind `duplicate-stack-concern`), and `VIOLATION_STACK_ROW_STATE` (kind `stack-row-state`).
- Each is a plain string constant. Do not add a severity or `blocking` axis. `Violation` has none, and every violation feeds a retry.

**The gate.** One function, for example `check_stack_totality`, placed next to `check_hosting_totality` in `CONSTRAINTS_GATES`. The gate takes the same `ArtifactEnvelope` and returns `list[Violation]`, like every other gate.
- Return `[]` when `envelope.constraints` is `None`.
- Decide whether the gate is **bound**:
  - bound when `constraints.stack is not None`, including `()`;
  - otherwise (`stack is None`) return `[]`.
- The key property: a stack-less artifact is never refused for the absence, on any envelope path: first run, resumed first run, below-stage re-gating, revision gates, candidate narrative evidence, or the impact snapshot. The gate reads only what the artifact carries, and it needs no envelope field and no knowledge of `predecessor`.
- When bound, report:
  - **Missing concern.** One violation per required concern with no row. Anchor the message on the expected concern name, because a missing row has no id. Name the file by `CONSTRAINTS_FILENAME`, list all required concerns, and say that `open` is a legal answer. This last point is what keeps the gate from pushing a model to invent a vendor.
  - **Unknown concern.** One violation per row whose `concern` is not in the concern constant. Name the row id and the bad value.
  - **Duplicate id.** One violation per duplicated id, not per occurrence, listing the rows that share it. Mirror `check_hosting_totality`'s once-per-defect style.
  - **Duplicate concern.** One violation per concern carried by more than one row under different ids, naming the concern and every row id that carries it. A duplicate id is a different defect and keeps its own report; a pair that shares both id and concern is reported once, as a duplicate id.
  - **Row state.** One violation per row that carries both `choice` and `open: true`, or neither, naming the row id. The parser accepts every combination, so this gate is the only owner of the rule.
- A row recorded as `open` counts as covering its concern. The gate must not read `choice` text. It judges presence and shape only. It must not compare a stack row with a hosting or store `product`.
- A decision anchored to an `open` row is not a violation. `check_decision_records` never reads `status`, so this stays true as long as stack ids resolve.
- Messages must be self-contained. They are pasted into a retry prompt as bare `- {message}` bullets. Name every identifier involved, and never cite positions.

**The anchor union.** Add the stack ids to the constraints entry of `_envelope_rows`, which `check_decision_records` uses to build `resolvable`.
- The components stage reads the same union, so this one edit covers both stages. Do not add a gate or a second union to the components side.
- Caution: `_constraints_rows` also feeds `_rows_of`, `design_row_ids`, and `check_inventory_has_prose`. Never put stack rows there: it would make stack ids local selectors and demand prose naming for every stack row. A stack row carries its own `choice` or `open` marker and an optional description, so it is exempt from the prose-inventory gate, as hosting rows are. Add the stack ids as an explicit local term inside `_envelope_rows`, labelled `"stack"` so the anchor hint names the kind.
- Identity rows: add an explicit stack term to `_constraints_identity_rows` (which `_feedback_target_rows`, `feedback_target_ids`, and `_continuity_rows` read) and to the constraints entry of `_envelope_identity_rows` (which `check_duplicate_row_ids` reads), labelled `"stack"`, the way hosting ids are added. This step owns it because it owns `roadmap_gates.py`; step 3 registers the collection in the row-type maps and relies on these identity rows so feedback can name a stack row.
- Handle `stack is None` as no rows.
- Collision with other row ids: with stack ids in `_envelope_identity_rows`, `check_duplicate_row_ids` reports a stack id that equals a domain, constraint, or components id. The stack gate reports only duplicates among stack rows themselves.

**Constraints to keep.**
- Do not add gates to `COMPONENTS_GATES`, `DOMAIN_GATES`, or `PLANS_GATES`.
- Do not change `Violation`, `run_constraints_gates`, or the `Gate` call shape. The stage table holds gate sets by identity.
- `plan_tool/gates.py` is unrelated (it suggests `gate:` shell commands). Do not import it or mirror its invoker seam.

**Other places that touch the same logic.**
- `check_hosting_totality` (same style, same file): the model for message wording and cardinality. It stays unchanged.
- `check_duplicate_row_ids` and `check_attribute_totality`: neighbors in `CONSTRAINTS_GATES`. They stay unchanged unless the collision check above requires otherwise.

## Tests

All cases go in `tests/test_roadmap_gates.py` (unit tests, no backend seam). Build fixtures by constructing row dataclasses directly. Approx. 14 cases.

- `test_stack_gate_inert_when_collection_absent` — `stack=None`: no violations, so a stack-less artifact is never refused for the absence on any envelope path, including a first run.
- `test_present_empty_stack_is_refused` — `stack=()`: one missing-concern violation per required concern, because the collection is carried.
- `test_partial_stack_is_refused_and_names_the_missing_concern` — two of three concerns: exactly one violation, naming the third.
- `test_open_concern_satisfies_totality` — all three concerns, one `open`: no violations. This pins the carve-out that `open` is legal.
- `test_gate_does_not_read_choice_text` — a chosen row with arbitrary text passes, and no comparison with a hosting or store `product` happens.
- `test_unknown_concern_is_reported_with_the_row_id` — a row with a concern outside the constant: one violation naming the row id and value.
- `test_stack_row_needs_no_prose_naming_and_is_not_a_design_row_id` — a constraints artifact whose `stack` rows are never named in the prose passes `check_inventory_has_prose`, and `design_row_ids` omits the stack ids.
- `test_stack_id_is_a_feedback_target_and_a_continuity_identity` — `feedback_target_ids` of a stack-bearing artifact includes the stack ids, and `_continuity_rows` reports them.
- `test_stack_id_colliding_with_a_domain_or_constraint_id_is_reported_once` — `check_duplicate_row_ids` reports the shared id.
- `test_duplicate_stack_id_reported_once_per_id` — three rows sharing one id: one violation listing all three.
- `test_second_row_for_the_same_concern_is_reported_as_a_duplicate_concern` — two rows with different ids and the same valid concern: one `duplicate-stack-concern` violation naming the concern and both row ids; two rows with distinct concerns pass.
- `test_stack_row_with_both_or_neither_choice_and_open_is_reported` — a row with `choice` and `open: true`, and a row with neither, each yield one `stack-row-state` violation naming the row id; a row with exactly one passes.
- `test_missing_concern_message_says_open_is_allowed` — the message names `open`, so a retry does not invent a vendor.
- `test_decision_anchored_to_a_stack_row_resolves_in_constraints` — a decision anchored to a stack id yields no unresolved-anchor violation.
- `test_decision_anchored_to_an_open_stack_row_is_accepted` — same, with the row recorded as `open` and the decision `pending`.
- `test_components_stage_resolves_a_decision_anchor_to_a_stack_row` — a components-stage decision anchored to a stack id resolves through the same union.
- `test_stack_ids_are_not_local_selectors_or_feedback_targets` — `design_row_ids` and `feedback_target_ids` do not include stack ids yet. This pins that the union edit stayed narrow.

Also update the existing anchor-hint tests only if the added `"stack"` kind changes their expected text.

### Tests for this step

- Every case above must be green before this step is finished.
- The existing `CONSTRAINTS_GATES` roster and stack-less fixtures must stay green unchanged; that is the check that absence is never refused.
- One parse-then-gate case with real text (step 1's parser) may be added to the existing seam test. Keep the other cases on directly built rows.
- The cases cover only what this step changes: the bound/unbound split, the three reports, and the anchor union.

## Acceptance criteria

- With `stack=None`, `run_constraints_gates` returns no stack violation.
- With `stack=()` or a partial tuple, missing concerns are reported.
- A concern recorded as `open` counts as present; no violation reads `choice`.
- An unknown concern yields one violation naming the row id. A duplicated id yields one violation per id.
- Two rows carrying one concern under different ids yield one `duplicate-stack-concern` violation naming the concern and both ids.
- A row carrying both `choice` and `open: true`, or neither, yields one `stack-row-state` violation naming the row id.
- A decision anchored to a stack id (including an `open` row) produces no unresolved-anchor violation in the constraints or components stage.
- `design_row_ids` and `_constraints_rows` are unchanged, and `check_inventory_has_prose` does not demand prose naming for a stack row. `_constraints_identity_rows`, `feedback_target_ids`, and `_envelope_identity_rows` gain the stack term.
- `tests/test_roadmap_gates.py` passes.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — read for frozen dataclass defaults, for the frozen stack row type.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — read for the absent, empty, partial, and complete case matrix.

## Applicable guardrails

- **The plan's "## Out of scope", fifth-artifact item:** this step adds no artifact file or filename constant; the gate reads `02-constraints.md` only.
- **The plan's "## Out of scope", concerns beyond those named and a closed vendor vocabulary:** the gate uses the plan's concerns only and never judges `choice` text.
- **The plan's "## Out of scope", judging a choice and approval blocks:** the gate reports presence and shape. It adds no comparison with a hosting or store `product` and no approval refusal.
- **The plan's "## Out of scope", rewriting accepted versions:** the gate never requires a stack where the collection is absent.
- **The step intent, components stage:** the components stage gets no gate of its own; the shared anchor union is the whole components-side change.

## Deferred

- Making stack rows feedback targets, local selectors, or inventory-prose rows, and their candidate operation policy — the feedback and candidate step.
- Flagging two rows that share a concern under different ids — not named in the plan; file it in `BACKLOG.md` if the Integration replay shows it.
- Prompt wording, summary and review callouts, seed rendering, and `ROADMAP_FORMAT.md` — later steps.
