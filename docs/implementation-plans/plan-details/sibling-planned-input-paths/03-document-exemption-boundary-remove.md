# Step 3 — Document the exemption boundary and close the delivered bug

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the delivered Input-reference exemption in `DATA_CONTRACT.md`. Remove only the originating entry from `BUG_BACKLOG.md`, after steps 1–2 and their required verification complete. Describe creation promises as evidence for accepting absent paths, without implying that future symbols or sibling contracts are verified. Provide the verified tool revision and Integration resume command through the completion handoff.

## Table of Contents

- [Summary](#summary) — Scope and completion result.
- [Table of Contents](#table-of-contents) — Section map.
- [Why](#why) — Why the boundary and delivery status need documentation.
- [Input](#input) — Landed behavior and delivery evidence.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two documentation edits.
- [Implementation](#implementation) — Contract wording and delivery-dependent closure.
- [Tests](#tests) — Non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Contract owners and source evidence.
- [Applicable guardrails](#applicable-guardrails) — Limits on documentation and closure.
- [Deferred](#deferred) — Separate experiment work.

## Why

`DATA_CONTRACT.md` distinguishes stale Input-reference findings from structured documentation edits but does not explain sibling creation promises. The originating entry in `BUG_BACKLOG.md` remains plan-authored while execution is pending. Readers need a precise account of the delivered exemption, and the separate Integration experiment needs verified delivery evidence before its blocked audit resumes.

## Input

- **Step 2 delivery:** Consume its completed consumer wiring, exemption and rejection coverage, mutation evidence, and affected/full-suite results. Detail authoring alone is not delivery.
- **Landed contract:** Read `plan_tool/review.py:check_plan_input_contract_references`, `plan_tool/review.py:check_step_input_contract_references`, and the selector delivered by step 1. Landed names take precedence over proposed names in earlier details.
- **Validator boundary:** Read `plan_tool/data_contract.py:_code_anchor_resolves` and `plan_tool/data_contract.py:check_input_contract_references`. Creation promises apply only when the referenced file is absent.
- **Experiment evidence:** Read `docs/experiments/roadmap-plan-regeneration/README.md` and `docs/experiments/roadmap-plan-regeneration/result.json` inside `/private/tmp/integration-roadmap-plan-regeneration-20261015`. They identify the stopped catalog audit and retained authoring state; they do not establish that this repair ships.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — document sibling eligibility and the absent-path exemption beside the existing Input-reference discussion.
  - `BUG_BACKLOG.md` — remove the originating missing-path entry only after verified delivery; otherwise retain its pending status.

## Implementation

- **Foundational logic: document a limited exemption and close its source entry only on delivery.** Keep this step to documentation and status. Reuse the behavior delivered by steps 1–2 without changing code or introducing another eligibility rule.

- **Extend the existing Input-reference discussion.** In `DATA_CONTRACT.md`, use the paragraph containing “stale plan/detail `## Input` references” as the insertion anchor. Explain that both review consumers use the same eligible creation promises, and cite their landed enforcing symbols.

- **Describe eligibility from the landed selector.** Cover repository registration, same-roadmap restrictions for roadmap-derived plans, preservation of own creates, and exclusion of unusable sibling records. Reference step 1 for selection ownership rather than transcribing its discovery procedure.

- **Make the acceptance boundary explicit.** The documentation must distinguish absent eligible creates from undeclared or edit-only missing paths. Existing files must still undergo ordinary symbol validation, even when an eligible plan declares that file for creation. Acceptance of an absent path must not claim delivery, future symbol existence, or agreement between sibling contracts.

- **Preserve the existing finding distinction.** Keep `DATA_CONTRACT.md` clear that stale Input references remain ordinary repair findings rather than structured `DATA_CONTRACT.md` payload edits. Add no persisted fields or format-version changes.

- **Close only the matching bug.** Locate `BUG_BACKLOG.md` by the heading beginning “The data-contract check reports a path another plan in the same roadmap creates as missing”. Remove the complete entry only after steps 1–2 ship with their required verification and the plan’s delivery checks complete. Preserve the neighboring unbuilt-upstream and archived-`source_seed` entries; this repair does not close them.

- **Supply a concrete resume handoff.** Record the delivered tool commit, the isolated repository location, and the exact catalog audit command, including backend/model selection and the applicable iterative/commit flags. Verify the command against the current CLI before recording it. Identify the retained `workflow-catalog-core` plan and its saved report `20261016-003744-completeness`; do not claim that the resumed audit passes before it runs. Return this information through the completion handoff without adding another file to this step.

## Tests

### Verification (non-code step)

The test-authoring gate does not apply: this step has `change_type: non-code`, while that gate requires `feature` or `refactor`. Add no test files.

1. **Documented eligibility matches delivery** — compare the new `DATA_CONTRACT.md` prose with the landed step 1 selector and both consumers in `plan_tool/review.py`.
2. **Absent-path acceptance remains bounded** — confirm step 2’s passing coverage in `tests/test_review.py` includes eligible siblings and the required exclusion cases.
3. **Existing symbols remain checked** — confirm `tests/test_data_contract.py:test_planned_path_does_not_excuse_a_stale_symbol_on_a_real_file` passes alongside `tests/test_data_contract.py:test_input_contract_reference_accepts_path_the_plan_creates`.
4. **Closure follows delivery** — inspect steps 1–2’s verification evidence, including mutation checks and affected/full-suite results, before removing the source entry.
5. **Only the source bug closes** — inspect the `BUG_BACKLOG.md` diff and confirm neighboring entries remain unchanged.
6. **References and resume instructions are usable** — check every documented path and symbol, and verify the handoff command against CLI help and the isolated experiment’s retained plan.
7. **Documentation checks remain green** — run `uv run pytest tests/test_data_contract.py -q` after the documentation edit.

## Acceptance criteria

- `DATA_CONTRACT.md` names both Input-reference consumers and accurately describes the delivered sibling eligibility boundary.
- The documentation states that creation promises excuse absent paths only and do not excuse stale symbols in existing files.
- The existing distinction between Input-reference repair findings and structured documentation payload edits remains intact.
- `BUG_BACKLOG.md` retains the source entry while delivery is pending and removes only that entry once delivery evidence is complete.
- The completion handoff contains the delivered tool commit, original isolated replay location, and exact verified catalog resume command.
- The handoff preserves the experiment’s two existing plans and leaves the remaining seven plans pending.
- Only `DATA_CONTRACT.md` and `BUG_BACKLOG.md` receive edits in this step, and the documentation verification passes.

## References

- [DATA_CONTRACT.md](../../../../DATA_CONTRACT.md) — Read the existing Input-reference finding discussion before extending it.
- [BUG_BACKLOG.md](../../../../BUG_BACKLOG.md) — Identify the originating missing-path entry and preserve adjacent independent bugs.
- [plan_tool/review.py](../../../../plan_tool/review.py) — Verify the landed selector and both Input-reference consumers.
- [plan_tool/data_contract.py](../../../../plan_tool/data_contract.py) — Verify the absent-path and existing-symbol boundary.
- [tests/test_data_contract.py](../../../../tests/test_data_contract.py) — Read the opposite acceptance and rejection invariants.
- [tests/test_review.py](../../../../tests/test_review.py) — Check step 2’s delivered consumer and eligibility coverage.
- [Experiment README](/private/tmp/integration-roadmap-plan-regeneration-20261015/docs/experiments/roadmap-plan-regeneration/README.md) — Read the stop condition and resume procedure.
- [Experiment result](/private/tmp/integration-roadmap-plan-regeneration-20261015/docs/experiments/roadmap-plan-regeneration/result.json) — Check the saved per-occurrence reproduction evidence.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, exemption boundary:** `DATA_CONTRACT.md` must describe the delivered rule without broadening its authority.
- **The plan’s “## Out of scope”, policy and artifact changes:** keep these edits descriptive; change no validation policy, source artifact, or schema.
- **The plan’s “## Acceptance criteria”, delivery-dependent closure:** remove the source bug only when the complete repair ships.
- **The plan’s “## Deferred”, experiment separation:** provide verified resume information without treating experiment continuation as completed work.

## Deferred

- Resume the catalog audit and continue the separate Integration authoring experiment — perform this after repair delivery through the existing experiment procedure; this step supplies the handoff only.
- Change shared eligibility or validator behavior — steps 1–2 own the focused repair; any broader change requires separate intentional work.
- Repair the neighboring unbuilt-upstream and archived-source bugs — they remain independently tracked in `BUG_BACKLOG.md`.
