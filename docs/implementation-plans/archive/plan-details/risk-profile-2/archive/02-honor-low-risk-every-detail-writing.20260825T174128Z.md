> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Honor low risk in every detail-writing route

## Summary

Wire step 1’s shared low-risk directives block into initial detail authoring, detail-quality review, and the `detail` quality loop's `apply_finding` rewrites. Update `plan_tool/detail.py`, `plan_tool/launcher.py`, and the three prompt templates so those routes receive the same optional context while the shared writer stays empty for create, completeness-apply, and reconciliation. Keep the block absent for standard, high, and undeclared plans, preserving their current prompt text. The automatic detail loop preserves the explicit risk-profile declaration rather than silently changing its own policy input. On green, low-risk detail authoring is guided and reviewed by one policy source while replacement, orphan, and merge archiving behavior stays unchanged.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the prompt wiring and preserved behavior.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — The current route gap and why it causes churn.
- [Input](#input) — The upstream directives contract and plan metadata this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Prompt, orchestrator, and test changes.
- [Implementation](#implementation) — Required routing and preservation rules.
- [Tests](#tests) — Coverage for each authoring and rewrite route.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for templating, model fields, and tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this work.
- [Deferred](#deferred) — Related work left to later steps.

## Why

`plan_tool/detail.py:render_detail_prompt` supplies initial authors with scope-fence context, while `plan_tool/detail.py:collect_detail_quality_findings` and `plan_tool/launcher.py:apply_finding` render separate review and rewrite prompts without a shared low-risk policy. That lets a later rewrite reintroduce procedure that initial authoring should have omitted. Step 1 supplies the single policy source; this step must carry it through every run-grade detail-writing route without changing unrelated detail-file lifecycle behavior.

## Input

- **Step 1 directive contract:** Consume step 1’s `plan_tool/plan_directives.py:render_low_risk_directives(plan, plan_path)` result. Confirm its landed signature before wiring it, and treat its empty result as no tier-specific prompt context.
- **Plan declaration:** Read the validated plan declaration only through step 1's renderer, which uses `plan_tool/schema.py:RiskProfile` and the stored tier/rationale pair. Do not infer a low tier from prose or the scope fence.
- **Existing context:** Keep `plan_tool/scope_fence.py:render_scope_fence` and `extract_plan_guardrails` as separate inputs. Directives constrain ceremony; they do not replace step intent, plan intent, or guardrails.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Pass the shared directives block into both initial-detail dispatch paths and the detail-quality prompt path.
  - `plan_tool/launcher.py` — Offer a default-off directives input to both the first and follow-up `apply_finding` prompts; non-detail callers retain the empty path.
  - `plan_tool/prompts/detail.md` — Render the optional low-risk directives context for initial detail authoring.
  - `plan_tool/prompts/detail-quality.md` — Render the optional low-risk directives context for quality review.
  - `plan_tool/prompts/apply-finding.md` — Tell rewrite authors that the optional directives block binds their edits.
  - `tests/test_detail.py` — Cover initial authoring, quality review, non-low regressions, and preserved archival behavior.
  - `tests/test_launcher.py` — Cover first-pass and follow-up rewrite prompt context.

## Implementation

- **Use one policy source.** Import and call step 1’s `plan_tool/plan_directives.py:render_low_risk_directives` rather than copying ceremony vocabulary or authorization rules into prompt templates or orchestrators. The renderer’s output is the only tier-specific input these routes receive.

- **Keep the context optional and low-only.** Extend `plan_tool/detail.py:render_detail_prompt` and `render_detail_quality_prompt` with an optional directives-block input whose empty default leaves existing direct callers unchanged. Insert the complete block through a template slot that adds no heading or explanatory text when it is empty.

- **Cover both initial-detail dispatch paths.** In `plan_tool/detail.py:_generate_detail_concurrent` and the per-step loop in `_run_grade_detail_lifecycle`, derive the directives block from the parsed plan and `plan_path` before calling `render_detail_prompt`. The worker `_author_step_detail` receives an already-rendered prompt, so it must not become a second policy-rendering route.

- **Count the added prompt context.** Include the directives block in `render_detail_prompt`’s `collect_blocks` output when present so its prompt-budget advisory measures the bytes actually sent.

- **Give quality review the same rule.** In `plan_tool/detail.py:collect_detail_quality_findings`, derive the block from the freshly parsed plan and pass it to `render_detail_quality_prompt`. Update `plan_tool/prompts/detail-quality.md` so the reviewer treats the block as binding: unlisted ceremony is a problem on declared-low plans, an explicitly authorized procedure remains permitted, and ordinary grounding and safety checks still apply.

- **Limit rewrite directives to the detail quality loop.** `apply_finding` is a shared plan/detail repair writer, not itself a detail-writing route. Give it a default-off directives input, and make only `plan_tool/detail.py:_converge_run_grade_step_detail` opt in for its quality-loop rewrites. Capture the explicit `risk_profile`/rationale pair before each automatic apply, and reject that entire apply result if either field’s presence or value changes; only a retained declaration may render the follow-up prompt. `create.py`, `completeness_phases.py`, `completeness_apply_parallel.py`, and `review_actions.py` leave the input unset, so create, completeness-apply, and reconcile behavior stays unchanged. Update `plan_tool/prompts/apply-finding.md` to require edits that respect a supplied block without widening the finding’s scope.

- **Do not repurpose the scope fence.** The rejected approach is adding low-risk branches or copied ceremony wording to `plan_tool/scope_fence.py` or each prompt. That would make policy drift likely and would confuse authorization with intent context.

- **Preserve detail-file lifecycle behavior.** Do not change `plan_tool/detail.py:_author_step_detail`’s archive-before-write order, `_archive_orphan_details` cleanup, `merge_steps`, or `_migrate_downstream_details_after_merge`. A new prompt block must not affect when prior detail is archived, when stale siblings move to `archive/`, or how folded details are retained during a merge.

- **Stay on the run-grade routes in this step.** Leave `plan_tool/detail.py:render_jira_detail_prompt`, execution prompts, audit prompts, report plumbing, and risk-profile schema work to their owning steps.

## Tests

- `test_initial_detail_prompt_includes_shared_low_risk_directives` — A declared-low plan’s rendered `plan_tool/prompts/detail.md` prompt contains the exact shared directives block.
- `test_generate_detail_serial_and_concurrent_routes_use_shared_low_risk_directives` — Both `_run_grade_detail_lifecycle` and `_generate_detail_concurrent` send the shared block to their authoring invoker.
- `test_detail_quality_prompt_includes_shared_low_risk_directives` — `plan_tool/detail.py:render_detail_quality_prompt` includes the block when supplied.
- `test_collect_detail_quality_findings_passes_low_risk_directives_to_reviewer` — The quality-review call built by `collect_detail_quality_findings` carries the low-risk policy.
- `test_non_low_directives_leave_initial_and_quality_prompts_byte_identical` — Parameterized standard, high, and undeclared plans render no new tier-specific context and preserve the no-directive prompt output.
- `test_apply_finding_initial_and_followup_prompts_include_low_risk_directives` — Both `apply_finding` attempts receive the block, including the prompt rebuilt from the post-edit plan.
- `test_apply_finding_non_low_prompt_omits_low_risk_directives` — A non-low plan never receives low-risk procedure instructions in the rewrite route.
- `test_apply_finding_directives_are_opt_in_for_detail_quality_only` — The detail quality-loop dispatch opts in, while the shared writer's no-argument path—the path used by create, completeness-apply, and reconcile—stays on the empty-directive rendering for a low-tier plan.
- `test_detail_quality_rejects_risk_profile_mutation_before_followup` — A quality-loop apply that changes either declaration field is rejected with its detail change, and no follow-up can render under a different tier.
- `TestDetailStyleOutput::test_archived_previous_detail_plain` — Retain the existing proof that replacement archives the old canonical detail before writing the new body.
- `TestDetailStyleOutput::test_archived_orphan_detail_plain` — Retain the existing proof that stale same-step siblings move to `archive/`.
- `TestMergeSteps::test_folded_files_archived_after_merge` — Retain the existing proof that a merge archives folded detail files without disturbing the surviving detail.

### Tests for this step

Add or update the prompt-routing tests in `tests/test_detail.py` and `tests/test_launcher.py`; every listed test must be green before this step is complete. Run the existing archive and merge regression tests with them so prompt integration cannot silently change detail-file lifecycle behavior.

## Acceptance criteria

- A declared-low plan sends the same block from `plan_tool/plan_directives.py:render_low_risk_directives` to initial authoring, detail-quality review, and both quality-loop `apply_finding` attempts.
- The authoring, reviewer, and rewrite prompts receive one policy that prohibits unlisted ceremony while allowing only exceptions that the shared block authorizes.
- An automatic detail-quality apply cannot change the declared risk-profile pair or render a follow-up under a changed tier.
- Standard, high, and undeclared plans render no tier-specific block; initial-detail and quality-review prompt text remains unchanged from the empty-directive path.
- The shared `apply_finding` default remains directive-free, so create, completeness-apply, and reconcile do not gain low-risk behavior.
- Prompt-budget reporting for initial detail authoring includes the directives block when it is rendered.
- `plan_tool/detail.py:_author_step_detail` still archives an existing canonical detail before replacement.
- `plan_tool/detail.py:_archive_orphan_details` and `merge_steps` keep their current orphan and merge-fold archival behavior.
- `uv run pytest tests/test_detail.py tests/test_launcher.py -q` passes.

## References

- [string — Template strings](https://docs.python.org/3.13/library/string.html#template-strings-strings) — Use `string.Template` substitution so an empty optional block leaves no unresolved placeholder.
- [Models | Pydantic Documentation](https://docs.pydantic.dev/latest/concepts/models/) — Review validated optional plan fields used by the directives renderer.
- [How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover low, standard, high, and undeclared profile prompt behavior.
- [Prompting best practices | Claude Platform Docs](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices) — Keep the shared policy context explicit and consistent across prompt routes.

## Applicable guardrails

- **The plan’s “Plan intent”** — Keep low-risk work proportionate while retaining the safety and evidence checks the shared block preserves.
- **The plan’s “Step intent”** — Give initial authoring and quality-loop review the same policy context while preserving explicitly authorized procedure.
- **The plan’s “Out of scope”** — Do not change risk classification, frontmatter schema, execution surfaces, Jira behavior, reconciliation, or retroactive audit behavior.

## Deferred

- Jira-grade detail authoring — The plan’s “## Out of scope” leaves `plan_tool/detail.py:render_jira_detail_prompt` and Jira surfaces unchanged.
- Audit finding and report behavior — Steps 3 and 4 own `tier-challenge`, audit prompting, blocking, and manual-resolution behavior.
- Additional shared directives — The plan’s `## Deferred` keeps `enforce_step_tests` policy integration outside this step.
