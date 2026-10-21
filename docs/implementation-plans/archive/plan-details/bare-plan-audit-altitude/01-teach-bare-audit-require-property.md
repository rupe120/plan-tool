> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Teach the bare audit to require property coverage and leave delivery mechanisms to detail

## Summary

Update the conceptual-audit prompt and its bare-plan status block so a bare audit checks whether each named property has a covered route, while leaving an unselected internal delivery choice for detail authoring. Edit `plan_tool/prompts/plan-audit.md` and `plan_tool/review.py`, then add replay coverage in `tests/test_review.py` and `tests/fixtures/convergence/bare-altitude-two-stage-replay.json`. The key decision is that a mechanism remains actionable at bare stage only when the plan explicitly makes it an observable contract. On green, an uncovered named property remains a correctness finding, but a typed attachment, dependency ordering, or similar internal choice produces no bare finding in either axis.

## Table of Contents

- [Summary](#summary) — The changed audit rule and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The bare-stage gap this step closes.
- [Input](#input) — The prompt, coverage state, and replay contracts this work reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New fixture and existing files to change.
- [Implementation](#implementation) — Required property-versus-mechanism guidance.
- [Tests](#tests) — Prompt-contract and replay coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Prompt and test-design guidance.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this step.
- [Deferred](#deferred) — Work this step intentionally leaves out.

## Why

The current bare-plan guidance correctly avoids asking for missing detail prose, but it does not clearly separate a missing route for a named observable property from an unselected way to deliver that property. That lets an internal implementation preference appear as a blocking correctness finding before `detail` has selected it. The audit needs to keep plan-level coverage, ownership, safety, ordering, and acceptance commitments actionable without turning detail authoring into an early audit requirement.

## Input

- **Audit template:** `plan_tool/prompts/plan-audit.md` defines the Correctness, Completeness, and Ambiguity lenses the conceptual auditor follows.
- **Bare-state signal:** `plan_tool/review.py:DetailBundleStatus` and `_format_detail_bundle_status_block()` identify the steps that lack detail and provide the conditional instruction inserted by `render_plan_audit_prompt()`.
- **Existing result contract:** `plan_tool/review.py:Recommendation`, `_parse_plan_audit_findings_with_evidence()`, `check_plan_audit()`, and `audit_plan_until_stable()` consume the existing two finding axes. This step must not add another result shape or response field.
- **Replay source:** `plan_tool/create.py:_render_from_prompt()`, `_PROPOSAL_FOUNDATIONAL_ITEM`, and `_render_sweep_context()` provide the combined and split proposal-route examples represented by the new fixture. They are evidence only; this step does not edit them.
- **Verification limit:** Canned prompt and fixture tests prove the audit receives the intended rule. They do not prove a future model always follows it.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/convergence/bare-altitude-two-stage-replay.json` — Record the bare and detail-stage policy cases for the combined and split proposal routes.

- **Existing files (edits only):**
  - `plan_tool/prompts/plan-audit.md` — State the property-coverage rule, the bare-only deferral of unselected internal mechanisms, and the explicit observable-contract exception.
  - `plan_tool/review.py` — Extend `_format_detail_bundle_status_block()` with bare-only wording that agrees with the template and reaches `render_plan_audit_prompt()` through the existing substitution path.
  - `tests/test_review.py` — Add prompt-rendering and fixture-driven tests beside `TestDetailBundleStatus` and the existing plan-audit prompt tests.

## Implementation

- **Keep route coverage at plan level.** For a bare step, require the audit to report a correctness finding when a plan names an observable property, acceptance result, ownership boundary, safety guarantee, or ordering rule but provides no route that delivers it. The finding must describe the missing property and route, not prescribe an internal implementation.

- **Leave delivery choices to detail.** Tell the bare audit not to raise a correctness or completeness finding solely because it prefers a typed carrier, serializer, dependency edge, fixture shape, telemetry value, parser arrangement, or similar internal mechanism that the plan has not selected. Do not merely move that request to Completeness or lower its severity; omit it from both axes until detail authoring chooses it.

- **Keep the explicit-contract exception narrow.** A mechanism remains a bare correctness obligation when the plan itself names that mechanism as the observable compatibility, safety, ordering, ownership, or bypass contract that satisfies a named property. Require the contract to be explicit in the supplied text; do not infer it from a plausible implementation choice.

- **Preserve detail-stage scrutiny.** The new guidance must apply only while the relevant step is bare. Once a detail file chooses a delivery mechanism, the existing detail-grounded audit may require that chosen mechanism and its supporting evidence.

- **Keep the two prompt surfaces aligned.** Put the durable policy in `plan_tool/prompts/plan-audit.md`, where the auditor learns how to classify commitments. Put the stage-specific qualification in `plan_tool/review.py:_format_detail_bundle_status_block()`, where the tool knows that a step is bare. Keep `render_plan_audit_prompt()` as the existing assembly path and retain its signature and prompt-budget accounting.

- **Retain existing bare guidance.** Preserve the current instruction that a missing detail file is not itself a detail contradiction, detail-vs-code issue, or omitted-detail finding. The new property rule must complement the existing **Missing edge-case concept** rule rather than weakening it.

- **Use the replay as policy evidence.** Make `tests/fixtures/convergence/bare-altitude-two-stage-replay.json` cover both `_render_from_prompt(..., omit_foundational_item=False)` and `_render_from_prompt(..., omit_foundational_item=True)` with `_render_sweep_context()`. For each route, record the named refactor-boundary property, a missing-route case that belongs in bare correctness, an unselected delivery-choice case that belongs in neither bare axis, and an explicit observable-contract case that remains bare correctness. Include the detail-stage expectation that a mechanism selected by detail can be checked there.

- **Do not change enforcement.** Do not modify `plan_tool/convergence.py:is_blocking_finding`, convergence continuation, audit-pass accounting, `Recommendation` parsing, or any exit path. This step changes only the guidance supplied to the audit and its replay evidence.

## Tests

### Tests for this step

- `test_bare_prompt_requires_a_named_property_to_have_a_route` — verifies a rendered bare prompt treats missing coverage of a named observable property as a Correctness finding.
- `test_bare_prompt_omits_unselected_delivery_mechanisms_from_both_axes` — verifies typed attachments, dependency ordering, and similar unselected internal choices are not redirected to either bare finding axis.
- `test_bare_prompt_keeps_explicit_observable_mechanisms_in_correctness` — verifies an explicitly named compatibility, safety, ordering, ownership, or bypass contract remains actionable at bare stage.
- `test_detail_grounded_prompt_can_require_a_selected_delivery_mechanism` — verifies the bare-only wording does not relax the detail-grounded audit once a detail file exists.
- `test_bare_altitude_status_block_reaches_rendered_prompt` — verifies `_format_detail_bundle_status_block()` contributes the stage-specific rule through `render_plan_audit_prompt()` only when at least one step is bare.
- `test_bare_altitude_two_stage_replay_covers_combined_and_split_routes` — loads `tests/fixtures/convergence/bare-altitude-two-stage-replay.json` and verifies both proposal routes carry the same refactor-boundary property cases.
- `test_bare_altitude_replay_separates_missing_property_from_delivery_choice` — verifies fixture expectations distinguish an uncovered property route, an unselected mechanism, and an explicit observable mechanism contract.

Every listed test and the affected existing tests in `tests/test_review.py` must be green before this step is complete: `uv run pytest tests/test_review.py -q`.

## Acceptance criteria

- A rendered bare-plan prompt requires a correctness finding for an uncovered route to a named observable property.
- A rendered bare-plan prompt requests no finding in either axis for an unselected internal delivery mechanism, including one described as severe.
- A mechanism explicitly named as an observable compatibility, safety, ordering, ownership, or bypass contract remains a bare correctness obligation.
- The rendered prompt keeps the existing detail-grounded bar once a detail file selects a mechanism.
- `tests/fixtures/convergence/bare-altitude-two-stage-replay.json` covers bare and detail expectations for both combined and split proposal routes.
- `plan_tool/review.py:_format_detail_bundle_status_block()` remains the only bare-state insertion point, and `render_plan_audit_prompt()` keeps its existing assembly and accounting behavior.
- No blocking predicate, convergence outcome, failure behavior, or exit-code path changes.
- `uv run pytest tests/test_review.py -q` passes.

## References

- [Prompting best practices — Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Use for clear, conditional audit instructions and explicit output constraints.
- [Define success criteria and build evaluations — Claude Platform Docs](https://platform.claude.com/docs/en/test-and-evaluate/develop-tests) — Use for the replay’s observable policy cases and the limits of canned prompt tests.
- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use for the combined and split route matrix.

## Applicable guardrails

- **The plan’s “## Plan intent”, property coverage:** Keep an uncovered route for a named property actionable without requiring an internal delivery choice.
- **The plan’s “## Step intent”, selected delivery:** Preserve coverage for both proposal routes while leaving unselected mechanisms for detail authoring.
- **The plan’s “## Out of scope”, enforcement behavior:** Do not add a gate, response field, classifier input, automatic action, or outcome change.
- **The plan’s “## Out of scope”, existing audit policy:** Do not alter blocking predicates, convergence behavior, failure handling, pass counts, or the detail-grounded bar.
- **The plan’s “## Out of scope”, create-path mechanics:** Use the proposal paths only as replay evidence; do not edit create behavior.
- **The plan’s “## Risks”, conservative policy boundary:** Require explicit observable-contract text before treating a mechanism as a bare correctness obligation.

## Deferred

- **Recommendation-text classification and advisory presentation** — Keep interpretation of persisted findings and operator messaging outside this prompt-guidance step.
- **Real-backend hit-rate measurement** — Canned cases verify the policy text and replay structure, not model behavior across live audits.
