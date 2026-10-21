> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Narrow bare-step edge-case findings in the audit prompt's detail-coverage block

## Summary

Add one rule to the bare-step instruction that `plan_tool/review.py:_format_detail_bundle_status_block` renders into the conceptual-audit prompt: for a step with no detail file, a **Missing edge-case concept** finding is admissible only when its fix is a new step or a new acceptance criterion, and is dropped when the fix is "spell it out in the detail file". The change is text inside that one function plus new cases in `tests/test_review.py::TestDetailBundleStatus`. The key decision is *where* the rule lives — in the bare-only block, not in the shared `plan_tool/prompts/plan-audit.md` template, because on a fully-detailed plan "specify it in the detail" is the right remedy and the template is read by every audit. On green, a bare or partially-detailed plan's audit prompt carries the narrowing and a fully-detailed plan's prompt is unchanged, because the function still returns `""` there.

## Table of Contents

- [Summary](#summary) — what the step does and what stays the same.
- [Why](#why) — the gap the current block leaves, and what it costs a bare audit.
- [Input](#input) — the contracts this text is written against, and the one thing it cannot verify.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — where the rule goes, the wording rules, the alternative rejected, and the sites left alone.
- [Tests](#tests) — new cases, the inherited cases that must stay green, and what is deliberately not tested.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — what to read before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby work this step does not take, and why.

## Why

The bare-step block already tells the auditor not to raise a detail-contradiction, a detail-vs-code, or a "the detail omits X" finding for a step with no detail file. It does not cover the one shape that slips past all three: a gap framed as a plan-level concept whose actual remedy is detail prose. `plan_tool/prompts/plan-audit.md` lists **Missing edge-case concept** as a first-class Completeness gap kind — "a failure / empty / concurrent / rollback / partial-failure case the design clearly implies but never names" — and nothing in the block narrows it. So on a bare plan the auditor reliably reports edge cases whose fix is "specify the retry behavior", "state what happens on an empty batch", and the operator's only way to close them is to write the detail file the audit ran *before*. That is the `detail` stage's job, and the audit is doing it early and by hand.

The plan's `## Problem statement` states the harm and its `intent:` carries the scope, so this step is one of the effort's three decisions rather than an aside: the apply route steps 2–5 open is worth less when the findings filling it can only be closed by the stage that has not run. The volume makes it worth fixing rather than tolerating: the plan's `## Architecture` records **8.7** conceptual findings per bare run against **5.1** for detailed runs (n=19 bare of 370 completeness reports, measured 2026-08-03). That is a real elevation and this step treats it as one — it is not saturation, and the block's wording must not describe it as saturation. The narrowing keeps the edge-case findings that are decomposition gaps, which is exactly what an audit run before `detail` should be catching, and drops the ones that pre-empt a stage that has not run.

## Input

- **`DetailBundleStatus`** (`plan_tool/review.py`) — the only input the block reads. `is_bare` is `True` when at least one step has no detail file for the grade being audited; `is_fully_bare` picks the "bare" vs "partially-detailed" label; `bare_step_ids` names the steps. This step adds no field and reads no new one.
- **The finding format in `plan_tool/prompts/plan-audit.md`** — two facts the new rule is written against. The Completeness list names the gap kind **Missing edge-case concept**, and the prompt requires every finding to end with `→ fix: <one-line remediation>` stated at the conceptual level. Key the rule on that fix clause: the auditor already writes it for every finding, so the rule reads against something it produces rather than asking for a fresh judgment.
- **`render_plan_audit_prompt`** (`plan_tool/review.py`) — substitutes the block as the `detail_bundle_status_block` template variable and reports its size into `collect_blocks` under the `"detail-bundle status"` label. Growing the block flows into the prompt-budget advisory automatically; no wiring change is needed.
- **What this step cannot verify.** The rule is a directive to a Claude auditor. Nothing machine-checks that a given audit honored it, and the plan's `## Risks` fixes that as the intended line. The observable this step ships is that the text is present in the rendered prompt on a bare plan and absent on a detailed one — assert that and nothing about auditor behavior.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — extend the text `_format_detail_bundle_status_block` returns with the edge-case rule, and update its docstring to say the block now carries two instructions (which findings not to raise, and when an edge-case gap counts) rather than one.
  - `tests/test_review.py` — new cases in `TestDetailBundleStatus` covering the new text and its absence on a fully-detailed plan.

## Implementation

**What must be true when the step is done:**

- On a status with a non-empty `bare_step_ids`, the returned text names the **Missing edge-case concept** gap kind and both halves of the rule — admissible when the fix is a new step or a new acceptance criterion, dropped when the fix belongs in the detail file.
- On a status with no bare steps, `_format_detail_bundle_status_block` still returns exactly `""`, so a fully-detailed plan's prompt is unchanged.
- The function keeps its signature `(status: DetailBundleStatus) -> str`, stays pure, and makes no Claude call.

**Recommended approach.** Add the rule as one more entry in the list of lines the function joins, after the existing "Judge bare steps solely on the plan body's concepts and the code at HEAD." sentence. Keep the trailing `""` so the block still ends with a blank line — the template drops it into place as a standalone chunk. One way to word it:

> For a bare step, raise a **Missing edge-case concept** finding only when its `→ fix:` is a new step or a new acceptance criterion — a decomposition gap this audit should catch. Skip it when the fix is "specify it in the detail file": `detail` has not run for that step yet, so naming it here does that stage's job for it.

The exact prose is the implementer's to settle; three things about it are not free to vary:

- **Reuse the template's own name for the gap kind.** Write **Missing edge-case concept** the way `plan_tool/prompts/plan-audit.md`'s Completeness list writes it. The block and the list are read in one prompt; a paraphrase leaves the auditor guessing which bullet the rule modifies.
- **State both halves.** A rule that only says what to skip reads as "stop reporting edge cases on bare plans", which is the opposite of the plan's decision — the decomposition-gap half is the point.
- **Keep it short.** This block rides in every bare audit prompt. Two or three sentences; do not restate the elevated-finding measurement or characterize bare audits as saturated.

**The key decision: the rule lives in the bare-only block, not in the prompt template.** `plan_tool/prompts/plan-audit.md` is rendered for every audit, and on a step that *has* a detail file "specify it in the detail" is the correct remedy — putting the rule there would suppress good findings on detailed plans. The block is the only place the tool already knows a step is bare, and it is the declared file for this step. Rejected alternative: edit the template's **Missing edge-case concept** bullet and have it self-qualify ("unless the step has a detail file"). That asks the auditor to re-derive per-step coverage from the bundle listing, which is a judgment the deterministic `audit_detail_bundle_status` already made.

**Second decision: keep the block grade-generic.** `audit_detail_bundle_status` takes `detail_grade`, but `_format_detail_bundle_status_block` takes only the resulting status and so renders the same words at run grade and jira grade. Keep it that way — a jira-grade step with no artifact is bare for the same reason, and the rule reads the same there. Rejected alternative: thread `detail_grade` into the block and emit the rule at run grade only. That adds a parameter and a branch to buy a difference nobody asked for, and forks a piece of machinery this codebase deliberately shares across grades. Note the consequence plainly for the reviewer: a jira-grade bare prompt gains the same sentences. That is prompt text, not the jira-grade fence, sidecar, or next-step output the plan holds out of scope — and the plan's `## Acceptance criteria` names this shared bare-step prompt text as the one thing that changes at both grades, so the two agree.

**Sites deliberately left alone.** Three other places restate the bare-plan grounding stance, and all three stay true after this step because they describe how the audit was *grounded*, not what the auditor may report:

- `plan_tool/cli/completeness_phases.py:_render_grouped_report` — the report's bare-plan grounding line ("bare steps are judged at the plan/concept level only").
- `plan_tool/cli/completeness_phases.py:emit_bare_plan_banner` — the operator's stderr banner.
- `plan_tool/cli/completeness_cmd.py:cmd_completeness` — the docstring/help text that says a bare step is judged at the plan/concept level.

Do not add the edge-case rule to any of them. It is an instruction to the auditor, and an operator reading a report does not act on it.

## Tests

All cases land in `tests/test_review.py`, in the existing `TestDetailBundleStatus` class beside the other block cases.

### Tests for this step

New cases:

- `test_status_block_admits_edge_case_gaps_whose_fix_is_a_step_or_criterion` — a bare status's block names the edge-case gap kind and both admissible remedies (a step, an acceptance criterion).
- `test_status_block_refuses_edge_case_gaps_whose_fix_is_detail_prose` — the same block says an edge-case gap whose fix belongs in the detail file is not raised for a bare step.
- `test_status_block_reuses_the_audit_prompts_edge_case_phrase` — reads `plan_tool/prompts/plan-audit.md` through `plan_tool/renderer.py:prompts_dir` and asserts the gap-kind phrase the block uses also appears in the template, so renaming that bullet reddens instead of silently orphaning the rule.
- `test_status_block_has_no_edge_case_rule_when_all_detailed` — a status with empty `bare_step_ids` returns `""`, so none of the new wording can reach a fully-detailed prompt.
- `test_render_prompt_carries_edge_case_narrowing_on_a_bare_plan` — end-to-end through `render_plan_audit_prompt` on a plan with one bare step: the rendered prompt contains the rule.
- `test_render_prompt_omits_edge_case_narrowing_when_all_detailed` — the same call on a fully-detailed plan contains none of the new wording.

Inherited cases that must stay green untouched — the addition is additive, so their substring assertions still hold: `test_status_partial_bare`, `test_status_fully_bare`, `test_status_block_empty_when_all_detailed`, `test_status_block_names_bare_steps_and_forbids_detail_findings`, `test_status_block_labels_fully_bare`, `test_render_prompt_injects_bare_status_block`, `test_render_prompt_no_status_block_when_all_detailed`.

Deliberately not tested: whether an audit run actually honors the rule. The plan's `## Risks` settles this as delivered, not verified — do not add a conformance check, a fixture audit response, or a real-backend case.

**Green-before-done gate:** every case above passes before the step is finished (`uv run pytest tests/test_review.py -q`).

## Acceptance criteria

- `_format_detail_bundle_status_block(DetailBundleStatus(total=2, detailed_step_ids=(1, 2), bare_step_ids=()))` returns `""`.
- For a status with any bare step, the returned text contains the gap-kind phrase **Missing edge-case concept** and names both a step and an acceptance criterion as admissible fixes.
- That same gap-kind phrase appears in `plan_tool/prompts/plan-audit.md`.
- `render_plan_audit_prompt` on a plan with at least one bare step contains the new rule; on a fully-detailed plan the rendered prompt matches HEAD's output.
- `_format_detail_bundle_status_block`'s signature is unchanged and it takes no `detail_grade` parameter.
- `uv run pytest tests/test_review.py -q` is green.
- `git diff --name-only` for this step lists only `plan_tool/review.py` and `tests/test_review.py`.
- No new finding source, severity, exit-code branch, or gate anywhere in the diff.

## References

- `plan_tool/review.py` — `_format_detail_bundle_status_block` (the function this step edits), `DetailBundleStatus`, `audit_detail_bundle_status`, and `render_plan_audit_prompt`'s substitution of `detail_bundle_status_block`.
- `plan_tool/prompts/plan-audit.md` — the Completeness list's **Missing edge-case concept** bullet, the `→ fix:` clause contract, and the concept-anchor rule that makes per-finding step routing unavailable.
- `plan_tool/cli/completeness_phases.py` — `emit_bare_plan_banner` and `_render_grouped_report`'s bare grounding line; read them to confirm the operator-facing statement stays true and needs no edit.
- `plan_tool/cli/completeness_cmd.py` — `cmd_completeness`'s help text restating the same grounding stance; also left alone.
- `docs/AUDIT_FLOW.md` — the audit flow's gate/sequence reference for where this block sits in the run.

## Applicable guardrails

- **The plan's "## Out of scope", no new gate / exit-code flip / blocking severity / refusal-to-advance.** This step ships prompt text and tests only. Do not add a detector, a finding source, or a check that fires when an audit reports an edge-case gap on a bare step.
- **The plan's "## Risks", decision 3 is delivered, not verified.** The acceptance criteria above may only assert that the text is present or absent. Do not add a criterion or test about what an auditor does with it.
- **The plan's "## Architecture", decision 3's "small delta" framing.** The block's new wording must not describe bare audits as saturated, and must not restate the per-run finding averages.
- **The plan's "## Out of scope", per-finding coverage routing refused.** State the rule at the bare-step level, which `DetailBundleStatus` already knows. Do not ask the auditor to decide per finding which step it belongs to.
- **The plan's "## Out of scope", jira-grade behavior.** Leave the jira-grade fence, the sidecar suppression, and `_format_bundle_framing_block` alone. The shared bare block is bare-plan machinery, and this step keeps one wording for both grades rather than forking it.
- **The plan's "## Out of scope", `detail`'s own behavior and BACKLOG #224.** Nothing in `plan_tool/detail.py` changes, and this step does not touch audit-shape detection.

## Deferred

- Machine-checking that an auditor honored the rule — permanently refused by the plan's `## Risks`, not a follow-up.
- Editing `plan_tool/prompts/plan-audit.md`'s Completeness list — outside this step's file list, and the rule is bare-only by design.
- Updating the three operator-facing grounding restatements (`_render_grouped_report`, `emit_bare_plan_banner`, `cmd_completeness`) — they describe grounding, which this step does not change.
- The bare-plan apply-fence split and the BLOCKED remedy — steps 1–5 of this plan, in different files.
- Measuring whether the narrowing actually lowers the 8.7-per-run bare average — needs audit runs against a real backend across many plans, which no unit test can supply; file it in `BACKLOG.md` if someone wants the number.
