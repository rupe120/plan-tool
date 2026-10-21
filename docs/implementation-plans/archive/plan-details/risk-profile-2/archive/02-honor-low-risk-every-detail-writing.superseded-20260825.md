> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Honor low risk in every detail-writing route

## Summary

Thread step 1’s shared low-risk directives into initial detail authoring, detail-quality review, and the detail loop’s rewrite pass. Update `plan_tool/detail.py`, `plan_tool/launcher.py`, and the three detail-writing templates while keeping the shared finding writer unchanged unless the detail loop opts in. Preserve the empty behavior for standard, high, and undeclared plans. On green, all run-grade detail-writing prompts follow one policy without changing replacement or archive behavior.

## Table of Contents

- [Summary](#summary) — The prompt-routing result and preserved behavior.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why inconsistent prompt context creates procedure churn.
- [Input](#input) — The upstream policy and declaration contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — The prompt, orchestration, and test footprint.
- [Implementation](#implementation) — Required routing and safety boundaries.
- [Tests](#tests) — Focused coverage for every affected route.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Relevant primary documentation.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work owned by later steps.

## Why

`plan_tool/detail.py:render_detail_prompt`, `collect_detail_quality_findings`, and `plan_tool/launcher.py:apply_finding` build separate prompts today. Without one policy block in all three, a quality-loop rewrite can add procedure that the initial authoring prompt should exclude. Step 1 supplies the policy source; this step carries it through the run-grade detail routes while leaving detail-file lifecycle behavior alone.

## Input

- **Step 1 output:** `plan_tool/plan_directives.py:render_low_risk_directives` is not yet present at HEAD; step 1 creates it as the only source of low-risk ceremony policy. Confirm its landed signature before wiring callers, and treat an empty render as no extra prompt context.

- **Declaration integrity:** The `risk_profile` and `risk_profile_rationale` fields of `plan_tool/schema.py:Plan`, together with `Plan.model_fields_set`, distinguish an explicit declaration from an inherited default. Preserve both field presence and values during automatic detail-loop applies.

- **Existing context:** Keep `plan_tool/scope_fence.py:render_scope_fence` and `plan_tool/detail.py:extract_plan_guardrails` separate from directives. Intent and guardrails remain context; the directives block supplies the low-risk policy.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Render and route the shared block through initial authoring and detail-quality review.
  - `plan_tool/launcher.py` — Allow `apply_finding` to receive optional directives for its first and follow-up prompts, and protect the declaration during opted-in automatic applies.
  - `plan_tool/prompts/detail.md` — Accept the optional policy block for initial authors.
  - `plan_tool/prompts/detail-quality.md` — Give reviewers the same policy boundary.
  - `plan_tool/prompts/apply-finding.md` — Bind rewrites to a supplied policy block without widening the finding.
  - `tests/test_detail.py` — Cover authoring, review, prompt-budget, and archive regressions.
  - `tests/test_launcher.py` — Cover rewrite prompts and declaration protection.

## Implementation

- **Use the step 1 renderer only.** Pass the rendered block from `plan_tool/plan_directives.py:render_low_risk_directives` through the detail routes. Do not copy ceremony vocabulary or authorization parsing into `plan_tool/detail.py`, `plan_tool/launcher.py`, or a template.

- **Keep the block optional.** Extend `plan_tool/detail.py:render_detail_prompt` and `render_detail_quality_prompt` with an already-rendered directives input. Each template render must receive that variable, including an empty value, and the empty path must leave the existing prompt text unchanged.

- **Cover each initial-authoring route.** Supply the block where `plan_tool/detail.py:_run_grade_detail_lifecycle` and `_generate_detail_concurrent` build prompts. `_author_step_detail` consumes a prepared prompt, so it must not become a second policy-rendering site.

- **Measure what is sent.** When `render_detail_prompt` embeds a nonempty block, include it in its `collect_blocks` accounting so prompt-budget output matches the prompt.

- **Give review the same boundary.** In `plan_tool/detail.py:collect_detail_quality_findings`, derive the block from its freshly parsed plan and pass it to `render_detail_quality_prompt`. The `plan_tool/prompts/detail-quality.md` instructions must require reviewers to preserve the supplied policy while retaining normal grounding and safety checks.

- **Restrict rewrite context to the detail loop.** Add a default-empty directives input to `plan_tool/launcher.py:apply_finding`, and pass it to both its initial `extra_vars` and `followup_extra_vars` prompt renders. Only the per-finding call in `plan_tool/detail.py:_converge_run_grade_step_detail` opts in; other callers remain on the empty path.

- **Protect policy inputs before a follow-up.** An automatic apply that changes either risk declaration field, including its explicit-presence state, must be rejected and restored before `apply_finding` can invoke its regression follow-up. Apply the same protection to any follow-up result, so the detail loop never continues under altered policy input.

- **Preserve lifecycle order.** Do not change `plan_tool/detail.py:_author_step_detail`’s archive-before-write behavior, `_archive_orphan_details`, `_migrate_downstream_details_after_merge`, or `merge_steps`. Prompt wiring must not affect prior-detail retention, orphan cleanup, or folded-detail archiving.

- **Leave other lanes alone.** `plan_tool/detail.py:render_jira_detail_prompt`, audit prompts, finding classification, and risk-profile schema work stay with their owning steps.

## Tests

- `tests/test_detail.py::test_low_risk_initial_detail_prompt_includes_shared_directives` — A declared-low plan embeds the exact shared block in `render_detail_prompt`.

- `tests/test_detail.py::test_non_low_initial_and_quality_prompts_keep_empty_block_output` — Standard, high, and undeclared declarations render no policy text and match the empty-context prompts.

- `tests/test_detail.py::test_serial_and_concurrent_detail_authoring_pass_low_risk_directives` — Both initial-authoring dispatch paths send the policy to their invoker.

- `tests/test_detail.py::test_detail_quality_prompt_includes_shared_low_risk_directives` — `render_detail_quality_prompt` includes the supplied block.

- `tests/test_detail.py::test_detail_quality_collection_renders_current_low_risk_directives` — `collect_detail_quality_findings` supplies current-plan policy to the reviewer.

- `tests/test_detail.py::test_detail_prompt_budget_counts_low_risk_directives` — Prompt-budget blocks include policy bytes only when the block is rendered.

- `tests/test_launcher.py::test_apply_finding_uses_directives_for_primary_and_followup_prompts` — Both rewrite attempts receive the same opted-in block.

- `tests/test_launcher.py::test_apply_finding_default_omits_low_risk_directives` — A caller that does not opt in remains directive-free, including for a declared-low plan.

- `tests/test_launcher.py::test_detail_loop_rejects_risk_profile_mutation_before_followup` — A primary apply that changes declaration presence or values restores the snapshot and makes no follow-up call.

- `tests/test_launcher.py::test_followup_cannot_change_risk_profile_declaration` — A follow-up cannot leave an altered declaration behind.

- `tests/test_detail.py::TestDetailStyleOutput::test_archived_previous_detail_plain` — Replacement still archives the prior canonical detail.

- `tests/test_detail.py::TestDetailStyleOutput::test_archived_orphan_detail_plain` — Stale same-step detail files still move to `archive/`.

- `tests/test_detail.py::TestMergeSteps::test_folded_files_archived_after_merge` — Merge still retains folded detail files in `archive/`.

### Tests for this step

All listed tests must be green before this step is complete. Run the focused suites with `uv run pytest tests/test_detail.py tests/test_launcher.py -q`.

## Acceptance criteria

- A declared-low plan sends step 1’s directives block to initial authoring, detail-quality review, and both detail-loop rewrite prompts.

- An explicitly authorized procedure remains available, while every quality-loop review and rewrite receives the policy context against unlisted ceremony.

- Standard, high, and undeclared plans receive no tier-specific context and retain their existing prompt text.

- The shared `apply_finding` path remains directive-free unless the detail loop explicitly opts in.

- An automatic detail-loop apply cannot change the risk-profile declaration or run a follow-up under changed policy input.

- Initial-detail prompt-budget output includes the policy block when present.

- Existing replacement, orphan-cleanup, and merge-fold archive tests remain green.

- `uv run pytest tests/test_detail.py tests/test_launcher.py -q` passes.

## References

- [string — Template strings](https://docs.python.org/3.13/library/string.html#template-strings-strings) — Use optional `string.Template` values without leaving unresolved placeholders.

- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Check declared-field presence as well as validated values.

- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover low, standard, high, and undeclared declaration states.

- [Prompting best practices | Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Keep shared policy context explicit across prompt routes.

## Applicable guardrails

- **The plan’s “Plan intent”** — Keep low-risk work proportionate without weakening the policy’s safety boundary.

- **The plan’s “Step intent”** — Apply one policy to initial authoring and quality-loop review while retaining authorized procedure.

- **The plan’s “Out of scope”** — Do not change classification, schema, execution, Jira, reconciliation, or retroactive-audit behavior.

## Deferred

- Jira-grade detail authoring — `plan_tool/detail.py:render_jira_detail_prompt` is outside this step’s run-grade prompt boundary.

- Audit finding and reporting behavior — Steps 3 and 4 own tier challenges, audit prompts, and downstream routing.
