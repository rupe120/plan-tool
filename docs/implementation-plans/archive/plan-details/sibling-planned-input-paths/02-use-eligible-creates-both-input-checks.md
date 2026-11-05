> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Use eligible creates in both Input checks and preserve existing-file symbol validation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update both Input-reference checks in `plan_tool/review.py` to use the eligible creation paths supplied by step 1. Keep the shared anchor validator unchanged: creation promises excuse absent paths only, while existing files still undergo symbol validation. Add coverage in `tests/test_review.py` and strengthen the relevant regression cases in `tests/test_data_contract.py`. Both plan and detail Input sections accept eligible sibling creates and continue reporting undeclared missing paths and stale symbols.

## Table of Contents

- [Summary](#summary) — Scope and observable result.
- [Table of Contents](#table-of-contents) — Section map.
- [Why](#why) — The consumer gap this step closes.
- [Input](#input) — Dependency output and existing validator contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three files this step changes.
- [Implementation](#implementation) — Shared eligibility and preserved validation.
- [Tests](#tests) — Consumer parity and rejection cases.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Relevant code and contract owners.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on the change.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/review.py:check_plan_input_contract_references` and `plan_tool/review.py:check_step_input_contract_references` both pass only `_planned_paths(plan)` to the shared validator. An absent path declared by an eligible sibling therefore still produces a missing-path finding. Wiring step 1’s selection into both consumers closes that gap while retaining the distinction pinned by `tests/test_data_contract.py:test_planned_path_does_not_excuse_a_stale_symbol_on_a_real_file`.

## Input

- **Step 1 output:** Consume its read-only, immutable set of eligible explicit creation paths, including the audited plan’s own creates. Read the landed helper’s name and signature from `plan_tool/review.py`; step 1 owns eligibility.
- **Plan Input body:** `plan_tool/review.py:check_plan_input_contract_references` reads the supplied plan file through `_split_frontmatter`.
- **Detail Input bodies:** `plan_tool/review.py:check_step_input_contract_references` reads current detail content through `_resolve_detail_body`, including canonical files without an explicit detail pointer.
- **Shared validator:** `plan_tool/data_contract.py:check_input_contract_references` accepts `planned_paths` and normalizes them. Its `_code_anchor_resolves` checks a creation promise only when `_resolve_anchor_path` finds no existing file.
- **Verification limit:** Eligible creates establish declared future paths. They do not establish future symbol contents or agreement between sibling contracts.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/review.py` — wire step 1’s eligible creates into both Input-reference consumers.
  - `tests/test_review.py` — cover matching behavior across both consumers and their existing dispatch routes.
  - `tests/test_data_contract.py` — strengthen regression coverage for absent-path acceptance and existing-file symbol validation.

## Implementation

- **Foundational logic: eligible creation promises excuse absent Input paths only.** Both `plan_tool/review.py:check_plan_input_contract_references` and `plan_tool/review.py:check_step_input_contract_references` must obtain their `planned_paths` from step 1’s selector. Recommend calling the same helper from each arm so separately dispatched checks receive the same eligibility rule.

- **Keep selection outside the shared validator.** Reuse `plan_tool/data_contract.py:check_input_contract_references` unchanged. Reject moving sibling discovery into that module or copying its anchor-validation logic into `plan_tool/review.py`; the existing argument already carries the required information.

- **Select once for the detail sweep.** Replace the own-plan collection before the loop in `plan_tool/review.py:check_step_input_contract_references`. Reuse that immutable result across checked detail bodies. Preserve the existing per-sweep `tree_provider` cache.

- **Keep existing-file validation authoritative.** Passing an eligible path must not bypass symbol checks when the anchor points to an existing file. Preserve `plan_tool/data_contract.py:_code_anchor_resolves`, including registered-owner, field, and Python-symbol checks. Do not filter findings after validation to achieve sibling acceptance.

- **Preserve independent and combined entry points.** `plan_tool/review.py:check_input_contract_references` combines the two arms, while `plan_tool/review.py:INPUT_CONTRACT_DETECTORS` dispatches them separately. Both routes must inherit the change through the two consumer functions; no detector or caller signature change is required.

- **Preserve sweep boundaries and finding identity.** Keep `step_filter`, done-step exclusion, `max_bytes`, canonical detail lookup, plan-first combined ordering, and existing issue locations and step attribution. Filtering the checked step must not narrow the eligible creation promises supplied by step 1.

- **Keep rejection behavior visible.** An undeclared typo, an edit-only missing file, or a path declared only by an ineligible sibling must still produce its existing finding. Eligibility must affect only the supplied creation-path set.

## Tests

Use hermetic repository fixtures and the real step 1 selector for consumer tests. Reuse its landed fixture support where practical; do not reproduce its eligibility algorithm in test helpers. Preserve the existing recomposition case in `tests/test_review.py:test_input_contract_arms_recompose_into_the_single_call`.

### Tests for this step

Each listed test must be green before this step is finished. The proposed new test names describe the required invariants.

- `tests/test_review.py:test_both_input_checks_accept_eligible_sibling_creates` — parameterize plan and detail Input sections; each accepts an absent Python anchor explicitly created by an eligible sibling.
- `tests/test_review.py:test_both_input_checks_preserve_own_creates_without_siblings` — each arm retains the audited plan’s own creation exemption when sibling discovery supplies nothing.
- `tests/test_review.py:test_both_input_checks_reject_paths_without_an_eligible_create` — parameterize undeclared typos, edit-only paths, and ineligible sibling declarations across both arms.
- `tests/test_review.py:test_both_input_checks_validate_existing_symbols_despite_sibling_creates` — each arm reports a missing symbol in an existing file even when an eligible sibling declares that path under creates.
- `tests/test_review.py:test_step_filter_limits_checked_bodies_not_creation_promises` — the combined check omits plan-level and unrelated detail findings while the selected detail still accepts an eligible sibling create.
- `tests/test_review.py:test_sibling_create_wiring_preserves_detail_resolution_and_done_exclusion` — a canonical detail without a pointer receives the exemption; a done step remains excluded.
- `tests/test_review.py:test_input_contract_dispatch_routes_share_sibling_eligibility` — separate detector dispatch and the combined check agree on eligible and rejected anchors, preserving issue location and step attribution.
- `tests/test_data_contract.py:test_input_contract_reference_accepts_path_the_plan_creates` — retain the positive absent-path exemption beside its rejection controls.
- `tests/test_data_contract.py:test_planned_path_does_not_excuse_a_stale_symbol_on_a_real_file` — strengthen the existing assertion to pin the stale anchor and symbol-failure reason when its path is also planned.
- `tests/test_data_contract.py:test_existing_valid_symbol_remains_valid_when_path_is_planned` — an existing valid Python symbol passes with and without its path in `planned_paths`.

Run the affected suites with `uv run pytest tests/test_review.py tests/test_data_contract.py -q -n auto`. Verify the new sibling cases fail when either consumer temporarily uses only `_planned_paths(plan)`. Verify the stale-symbol cases fail when a temporary mutation accepts planned paths before checking existing files; restore each mutation afterward.

## Acceptance criteria

- Both Input-reference consumers accept absent anchors declared by eligible siblings through step 1’s selector.
- Both consumers retain own-plan creation acceptance without eligible siblings.
- Undeclared, edit-only, and ineligible-sibling missing paths still produce findings.
- Existing-file stale symbols still produce findings even when their paths occur in the eligible creation set; existing valid symbols pass.
- Independent detector dispatch and combined checking apply the same eligibility rule.
- Step filtering, done-step exclusion, canonical detail lookup, and issue attribution retain their existing behavior.
- The affected test suites pass, and the temporary mutations demonstrate that the new tests detect missing consumer wiring and weakened symbol validation.
- Production changes remain confined to `plan_tool/review.py`; `plan_tool/data_contract.py` remains unchanged.

## References

- [Source backlog — Read the sibling planned-path entry for the eligibility and non-downgrade contract.](../../../../../BUG_BACKLOG.md)
- [Input consumers — Locate `_planned_paths`, both Input-check arms, their combined wrapper, and `INPUT_CONTRACT_DETECTORS`.](../../../../../plan_tool/review.py)
- [Shared anchor validator — Read `check_input_contract_references` and `_code_anchor_resolves` for the absent-path boundary.](../../../../../plan_tool/data_contract.py)
- [Consumer tests — Read `_write_input_contract_plan` and the Input-check recomposition coverage for existing fixture and dispatch conventions.](../../../../../tests/test_review.py)
- [Validator regressions — Read the planned-path acceptance and existing-file stale-symbol tests together.](../../../../../tests/test_data_contract.py)
- [Data contract — Consult the owning reference for Input-contract finding structures.](../../../../../DATA_CONTRACT.md)
- [Testing guide — Follow hermetic test and backend-neutralization requirements.](../../../../../TESTING.md)

## Applicable guardrails

- **The plan’s “Scope guardrails,” absent-path exemption:** Limit this step’s production edit to supplying step 1’s eligible paths to the two existing consumers.
- **The plan’s “Step intent,” typo and symbol protection:** Keep missing-path rejection and existing-file symbol validation covered together in both consumer tests.
- **The plan’s “Out of scope,” audit policy:** Preserve finding severity, dispatch policy, blocking behavior, and exit behavior.
- **The plan’s “Out of scope,” source artifacts:** Keep discovery read-only; tests use temporary fixtures, and production code must not create promised files or alter sibling sources.

## Deferred

- Eligibility selection and roadmap identity — Step 1 owns these rules; this step consumes its result without changing discovery or provenance.
- Changes to `plan_tool/data_contract.py:_code_anchor_resolves` — Its existing absent-path boundary already supports the focused behavior; this step verifies and reuses it unchanged.
- Semantic agreement between sibling contracts — The plan’s scope fence excludes judging whether a declared future implementation satisfies its consumers.
