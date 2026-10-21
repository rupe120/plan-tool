> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Supply advisory risk context to every run-grade detail prompt

## Summary

Wire step 1’s advisory context into initial detail authoring, detail-quality review, and detail-loop rewrites. Update `plan_tool/detail.py` for the authoring and review routes, and extend `plan_tool/launcher.py:apply_finding` so its primary and automatic follow-up prompts can share one captured context. Keep the new apply input optional and empty by default, preserving every non-detail caller’s prompt output. On green, an explicit declaration reaches each named route, while an omitted declaration changes no prompt bytes.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the prompt-route wiring.
- [Table of Contents](#table-of-contents) — Navigation for this detail.
- [Why](#why) — Why the renderer must reach every detail-writing route.
- [Input](#input) — The declaration and upstream renderer this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Existing files changed by this step.
- [Implementation](#implementation) — Route wiring, capture rules, and unchanged callers.
- [Tests](#tests) — Focused prompt and lifecycle coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Plan contract and detail-loop behavior.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this change.
- [Deferred](#deferred) — Related surfaces that remain outside this step.

## Why

Step 1 provides the advisory block and prompt insertion points, but the current authoring, review, and rewrite orchestration does not supply that block. `plan_tool/detail.py:_run_grade_detail_lifecycle`, `plan_tool/detail.py:_generate_detail_concurrent`, and `plan_tool/detail.py:collect_detail_quality_findings` each render a prompt through separate paths, while `plan_tool/launcher.py:apply_finding` renders both its first edit prompt and any automatic follow-up. Wiring only one path would leave the same detail work guided by different information.

## Input

- **Explicit declaration:** Read the `risk_profile` and `risk_profile_rationale` fields of `plan_tool/schema.py:Plan` through the renderer supplied by step 1. Do not substitute the `Plan.effective_risk_profile` fallback; legacy omission must remain empty context.

- **Step 1 renderer:** Use the finalized public renderer and context-block arguments produced by step 1. Confirm their name and signature after step 1 lands rather than relying on this plan’s prose.

- **Rewrite lifecycle:** `plan_tool/detail.py:_converge_run_grade_step_detail` owns the opted-in `plan_tool/launcher.py:apply_finding` call. `plan_tool/launcher.py:apply_finding` already builds a primary prompt and may build one automatic follow-up from a reparsed plan.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Supply step 1’s context block to both initial-authoring paths and to `collect_detail_quality_findings`; capture the block for each detail-loop apply attempt.
  - `plan_tool/launcher.py` — Add an optional context-block input to `apply_finding` and include it in both primary and follow-up prompt variables.
  - `plan_tool/prompts/apply-finding.md` — Add one optional insertion point for the supplied advisory block without duplicating its wording.
  - `tests/test_detail.py` — Cover authoring, quality-review, legacy-empty, and refreshed-context behavior.
  - `tests/test_launcher.py` — Cover opt-in apply rendering and shared context across primary and follow-up prompts.

## Implementation

- **Use one rendered block:** Build the advisory context with step 1’s renderer and pass that exact string to each run-grade detail route. Do not copy tier wording or add another renderer in `plan_tool/detail.py`, `plan_tool/launcher.py`, or `plan_tool/prompts/apply-finding.md`.

- **Cover both initial-authoring paths:** Supply the context when `plan_tool/detail.py:_generate_detail_concurrent` and `plan_tool/detail.py:_run_grade_detail_lifecycle` call `plan_tool/detail.py:render_detail_prompt`. The serial and concurrent paths must send the same block for the same parsed plan.

- **Refresh at the serial after-apply boundary:** `plan_tool/detail.py:collect_detail_quality_findings` continues to use its freshly parsed plan for every quality scan. After `plan_tool/detail.py:_converge_run_grade_step_detail` returns for a serial step, and after its parse-revert protection has retained a valid accepted edit, reload `plan_path` before preparing the next serial step. Replace the lifecycle's in-memory plan used by the next `render_detail_prompt`; do not reload or re-render either prompt within the apply that made the edit. A blocked, reverted, or structurally split apply must not advance the serial route under a changed declaration.

- **Make rewrite context explicitly opt-in:** Extend `plan_tool/launcher.py:apply_finding` with an optional keyword-only context-block input whose default is `""`. Add that value to the template variables for both `plan_tool/renderer.py:render_prompt` calls inside `apply_finding`; `Template.safe_substitute` leaves an unresolved placeholder if the variable is omitted.

- **Capture once per apply attempt:** At the start of every individual `plan_tool/detail.py:_converge_run_grade_step_detail` apply attempt, read the current valid plan from `plan_path`, then render and retain that attempt's context block. Do not reuse the function-entry plan after an earlier accepted apply changes the declaration. Pass the retained value through that attempt's primary and automatic follow-up prompts even if the primary edit changes the declaration. The next apply attempt, later quality scan, and completed apply's serial handoff each read fresh context from the accepted plan.

- **Preserve ordinary declaration edits:** Do not reject, rewrite, validate, or specially persist risk-profile changes in the detail loop. A valid pair update remains an ordinary accepted plan edit; only the timing of advisory context is constrained.

- **Keep the shared writer unchanged by default:** `plan_tool/bench.py`, `plan_tool/create.py`, `plan_tool/cli/completeness_apply_parallel.py`, `plan_tool/cli/completeness_phases.py`, and `plan_tool/cli/review_actions.py` must continue calling `plan_tool/launcher.py:apply_finding` without the new argument. The detail-loop call is the only opt-in caller.

- **Keep the template inert when empty:** Put the new slot in `plan_tool/prompts/apply-finding.md` where its empty substitution preserves the existing spacing and prompt bytes. The rendered advisory block supplies its own visible content; the template must not add a second policy statement.

- **Leave adjacent lanes alone:** Do not change `plan_tool/detail.py:render_jira_detail_prompt`, `plan_tool/prompts/run.md`, completeness-audit prompts, reconciliation, execution, or frontmatter validation. The rejected approach is deriving risk policy separately in each prompt route, which would let wording and behavior drift.

## Tests

### Tests for this step

- `tests/test_detail.py::test_run_grade_detail_authoring_routes_receive_declared_risk_context` — Serial and concurrent initial authoring send step 1’s rendered block for an explicit declaration.

- `tests/test_detail.py::test_detail_quality_review_receives_current_declared_risk_context` — `collect_detail_quality_findings` gives the reviewer the current explicit context and leaves a legacy plan empty.

- `tests/test_detail.py::test_serial_detail_lifecycle_refreshes_context_after_accepted_declaration_change` — A two-step serial lifecycle changes the valid declaration in step 1's accepted apply; step 2's initial-authoring prompt and the later quality review render the updated block, while both prompts inside the first apply retain the original block.

- `tests/test_detail.py::test_detail_quality_loop_recaptures_context_for_each_accepted_apply` — Two accepted applies in one detail-quality loop change the declaration in the first; the first primary and follow-up retain the original block, while the second apply captures and sends the updated block.

- `tests/test_detail.py::test_undeclared_profile_keeps_detail_authoring_and_review_prompts_unchanged` — The routed empty context preserves the prompt text produced by the empty-default renderers.

- `tests/test_launcher.py::test_apply_finding_context_reaches_primary_and_followup_prompts` — An opted-in apply that triggers automatic follow-up sends the same captured advisory block to both prompts.

- `tests/test_launcher.py::test_apply_finding_empty_context_preserves_shared_caller_prompt` — Omitting the new argument and passing `""` produce the same apply prompt for an explicitly declared plan.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An explicit profile and rationale reach initial run-grade authoring, detail-quality review, and the detail-loop rewrite prompt.

- Serial and concurrent initial authoring receive the same advisory block for the same plan.

- Primary and automatic follow-up prompts from one opted-in `apply_finding` call use the same captured context.

- Every later detail-loop apply reads the plan after earlier accepted applies and captures its own advisory block.

- After a valid declaration update is accepted, the serial lifecycle reloads before it renders the next selected step, and later authoring and quality-review calls see the updated block.

- A plan with no explicit declaration preserves the affected prompt bytes.

- Every non-detail `plan_tool/launcher.py:apply_finding` caller retains the empty-default behavior.

- `uv run pytest tests/test_detail.py tests/test_launcher.py -q` and the plan’s `test_command` pass.

## References

- [Plan frontmatter contract — Read the explicit-pair and legacy-omission rules for `risk_profile` and `risk_profile_rationale`.

- [Detail flow](../../../how-to/pipeline/detail.md) — Read the initial authoring and detail-quality apply loop this step wires.

## Applicable guardrails

- **The plan’s “## Plan intent,” advisory context:** Keep the declaration informational and retain normal grounding, testing, and safety-review duties.

- **The plan’s “## Step intent,” current declaration after rewrites:** Use one captured context for an apply attempt, then let later detail routes read the accepted declaration.

- **The plan’s “## Scope contract,” allowed behavior changes:** Limit behavior changes to the named detail prompt routes and preserve empty behavior outside them.

- **The plan’s “## Out of scope,” other pipeline lanes:** Do not extend this work into audits, reconciliation, execution, Jira, classification, or validation.

## Deferred

- **Risk-profile enforcement or tier-specific policy rules** — The plan’s scope keeps advisory context separate from any future cross-pipeline proposal.

- **Jira-grade and execution prompts** — These are outside the run-grade detail routes this step owns.
