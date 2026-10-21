> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Let a bare plan's correctness gaps keep the completeness-apply route

## Summary

Split the conceptual apply fence in `plan_tool/completeness_report.py` by axis: a bare plan keeps the `plan-tool completeness-apply` route for its conceptual-**correctness** gaps and still withholds it for its conceptual-**completeness** gaps. The whole change lands inside the fence helper step 1 extracted, so both `suggested_next_steps` (report prose) and `suggested_next_step_commands` (console block) pick it up from one edit. Three further sites in this module state the same axis claim in prose and move with it: the correctness bullet's tail (it may no longer promise "then the completeness gaps" on a bare plan, because that half is still withheld there), `build_report_md`'s bare-plan "Apply actions are withheld until a complete detail bundle exists" paragraph, and `console_summary`'s conceptual-completeness line. Jira grade keeps withholding both axes, and a fully-detailed plan's output does not change. On green, a bare-plan audit whose only findings are correctness gaps prints a `completeness-apply` next step in both next-step surfaces instead of the current "No gaps left to close — `plan-tool run <name>`".

## Table of Contents

- [Summary](#summary) — what changes and what stays the same.
- [Why](#why) — one flag doing two jobs, and the wrong-answer case it produces today.
- [Input](#input) — the fence helper from step 1, the landed verb from step 4, and the two plan-level facts the fence reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — where the split goes, the three prose sites that must follow it, and the sites deliberately left alone.
- [Tests](#tests) — new cases, the two inherited cases this step rewrites, and the regression net that must stay green untouched.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the files worth reading before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby work this step does not take, and who owns it.

## Why

`is_bare` means "at least one step has no detail file", and the apply fence uses it to withhold `plan-tool completeness-apply` from **both** conceptual axes. That is right for completeness gaps, which lean on the detail bundle. It is wrong for correctness gaps: an unsound concept, an internal contradiction, or a bad ordering targets the plan body, step titles, and acceptance criteria, all of which exist on a bare plan — and `plan_tool/prompts/apply-finding.md` already edits the plan file "and/or the step's detail file **if applicable**", reserving `BLOCKED` for a finding that genuinely needs a missing detail file. So the apply path handles a plan-body-only edit and the fence refuses to name it anyway. The visible cost: a bare plan whose only findings are correctness gaps hits the `not steps` fallback in `suggested_next_steps` and prints "No gaps left to close — `plan-tool run <name>`", which is false, and `suggested_next_step_commands` returns an empty list for the same run. (The neighbouring "No structural gaps left to close in this bare-plan audit" line is a *different* branch — it needs `bare_detail_diagnostic_count or advisory_conceptual` to be non-empty, so a correctness-only bare run never reaches it. Pin the branch that actually fires.) The report body already disagrees with both — `build_report_md`'s `## Conceptual correctness — fix these first` section renders `CORRECTNESS_INTRO` on any non-jira grade, bare or not, so it names the apply verb while the next-step lists withhold it. This step makes the next-step lists match, which is the direction that is correct rather than the one that is convenient.

**Step 4 lands first, so this step advertises a verb that already works.** The plan reorders `depends_on` for exactly this reason: before the reorder, step 2 could ship a commit naming a route that warns and exits, which step 4's own Why calls worse than an honest refusal. Nothing here needs step 4's mechanism — only the fact that the verb walks `plan-correctness` on a bare plan by the time this lands.

## Input

- **The fence helper landed by step 1** — one module-level function in `plan_tool/completeness_report.py` that both renderers call to get their actionable correctness and completeness lists. Step 1's outcome is that the fence exists exactly once; this step changes what that one definition returns. Read the landed helper before editing: its name, parameter shape, and return type are whatever step 1 actually shipped, and the landed version wins over the shape step 1's detail recommended.
- **Step 4's outcome, not its mechanism.** `plan-tool completeness-apply` already walks a bare plan's `plan-correctness` gaps and reports every other saved source as withheld. That is the fact this step is allowed to advertise; do not import from `plan_tool/cli/completeness_cmd.py` or restate its wording.
- **`DetailBundleStatus.is_bare`** (`plan_tool/review.py`, computed by `audit_detail_bundle_status`) — `True` when at least one step lacks a detail file for the grade being audited. This is the only coverage fact the fence may read. Both renderers reach it through a defensive `getattr(bundle_status, "is_bare", False)` because the parameter defaults to `None` and the suites pass a `SimpleNamespace`; keep that defensive read wherever it now lives.
- **`detail_grade`** — compared against `GRADE_JIRA` from `plan_tool/jira_grade.py`; the renderers default to `GRADE_RUN`. Jira grade withholds both axes for its own reason (it writes no findings sidecar, so no verb can replay anything), and that reason is untouched by this step.
- **`correctness` and `advisory_conceptual`** — both `list[Recommendation]`. `correctness` defaults to an empty **tuple** `()`, so anything downstream must tolerate a tuple.
- **What this step cannot read.** A `Recommendation`'s `step_id` is `None` on ~94% of conceptual findings, so the fence stays at plan level. See the plan's `## Out of scope` refusal.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — change the fence helper so `is_bare` no longer suppresses the correctness list; make the correctness next-step bullet in `suggested_next_steps` phrase its tail from whether completeness gaps are actionable; axis-scope `build_report_md`'s bare-plan withheld paragraph; give `console_summary` a `bundle_status` parameter and axis-scope its conceptual-completeness line; update the helper's docstring and the renderers' docstrings so the prose states the axis split.
  - `tests/test_completeness_report.py` — add the new bare-plan correctness cases, rewrite the inherited cases that pin the old both-axes fence and the old blanket withheld paragraph.

**One call site this step does not own.** `console_summary`'s new `bundle_status` argument has to be passed from `_persist_and_present_report` in `plan_tool/cli/completeness_phases.py`, which is **step 5's** declared file. Give the parameter a `None` default so this step is complete and correct on its own — an un-wired caller keeps today's line — and step 5 wires the one-line call site when it edits that module. Do not edit `completeness_phases.py` here.

## Implementation

**The behavior change, stated as the property that must hold.** For each combination of coverage and grade, both renderers must give the same answer to "does this run name `plan-tool completeness-apply`":

- **bare + correctness gaps** → yes, for the correctness gaps.
- **bare + completeness gaps only** → no; unchanged.
- **bare + both** → yes, and the run names only the correctness half as appliable.
- **jira grade, any coverage** → no; unchanged.
- **fully detailed** → unchanged in every case.

**Put the split in the fence helper, not in the renderers.** Step 1 exists so this is a one-place edit: the helper stops gating the correctness list on bare and keeps gating it on jira grade, while the completeness list keeps both gates. One way to say it inside the helper: correctness is withheld only at jira grade; completeness is withheld when the plan is bare **or** the grade is jira. Do not reintroduce a `bare_plan or jira_grade` local — the step-1 `gate:` still holds, and the two axes no longer share one expression.

**Fix the correctness bullet's tail in `suggested_next_steps`, or the report promises a walk that will not happen.** The bullet today reads "apply the N conceptual-correctness gap(s) first (design gaps; not auto-applied under #85), then the completeness gaps." On a bare plan the "then the completeness gaps" clause is false — the completeness gaps stay unappliable. Derive the tail from whether the completeness list came back actionable rather than hard-coding it:

- **When completeness gaps are actionable** (the detailed run-grade case), keep the current sentence. Two existing tests assert the literal phrase `conceptual-correctness gap(s) first`, and they must stay green untouched.
- **When they are not** (the bare case), say the correctness gaps can be applied now and that the completeness gaps stay informational until a detail bundle exists. Keep it to one sentence and reuse the vocabulary already in the file — `build_report_md`'s bare-plan paragraph says "Apply actions are withheld until a complete detail bundle exists", and staying close to that wording keeps the report internally consistent.

**The console renderer needs no wording branch.** `suggested_next_step_commands` builds its description from the `apply_effects` list, appending one clause per effect that actually applies. On a bare plan the correctness clause is appended and the completeness clause is not, so the emitted description is already right once the helper returns the split lists. Check this rather than assume it — if the landed helper differs from step 1's recommended shape, the effects list may need the same treatment.

**Axis-scope `build_report_md`'s bare-plan withheld paragraph — it is a blanket claim this step falsifies.** The conceptual-completeness section's bare arm reads "Coverage gaps in the plan's own ideas are reported for visibility in this bare-plan audit. Apply actions are withheld until a complete detail bundle exists, so these findings are informational for now." The first and third sentences stay true; the middle one is now false as written, because apply actions are withheld **for this axis**, not at all. Narrow it to the completeness axis in one sentence — the coverage gaps below are the half that stays informational until a detail bundle exists — and keep the paragraph's shape. The same report's `CORRECTNESS_INTRO`, two sections above, already names `completeness-apply` on a bare plan, so leaving the blanket sentence in place would have one report contradicting itself. `tests/test_completeness_report.py` pins the old phrase; rewrite that assertion with the sentence.

**Axis-scope `CORRECTNESS_INTRO` the same way — it makes the joint promise this step breaks.** The constant says the paired apply verb walks correctness gaps "before the completeness gaps" and its example comment is `# walk + apply each correctness gap, then the completeness gaps`. On a bare plan that second half is false: step 4's allow-list withholds every non-`plan-correctness` source. Select a bare-only variant (or a bare branch inside `build_report_md`) whose wording names `completeness-apply` for the correctness gaps only and does **not** promise a completeness-gap walk in the same command. Detailed and jira paths keep today's text. Its `reconcile-plan-walk` line is a separate, pre-existing defect — filed in `BUG_BACKLOG.md` and named in the plan's `## Deferred`. Leave that line alone here; the bare variant keeps it until that backlog fix ships. Do not "fix" it while touching the intro.

**Axis-scope `console_summary`'s conceptual-completeness line.** On the `--iterate` path this is one of the six surfaces describing one run (the plan's `## Risks` lists all six). It always tells the operator to "apply via `plan-tool completeness-apply`" for `advisory_conceptual`, and it takes no coverage input at all. Give it a keyword-only `bundle_status=None` and, when the plan is bare, say those gaps stay informational until a detail bundle exists instead of naming the verb. The `correctness` line above it needs no branch — it names the verb, which is now true on a bare plan too. Read bareness with the same defensive `getattr(bundle_status, "is_bare", False)` the renderers use; `None` keeps today's output, which is what makes the un-wired call site in step 5's module safe until step 5 wires it.

**Sites in the same file that read `is_bare` and must not change:**

- **`build_report_md`'s `not bare_plan and not jira_grade` gate on the per-finding `Address: plan-tool completeness-apply --anchor` sub-bullet** — that sub-bullet hangs off the *completeness* findings, which stay unappliable on a bare plan. Already correct.
- **`build_report_md`'s conceptual-correctness section on a detailed plan** — keeps today's `CORRECTNESS_INTRO`. The bare arm is the edit above; do not change the detailed path's text.
- **The `DETAIL_LEVEL_DIAGNOSTIC_SOURCES` filter and `bare_detail_diagnostic_count`** in both renderers — these suppress *detail-authoring* actions on a bare plan, a different job from the conceptual apply fence. Leave them alone. This is also what keeps the step inside the plan's `## Architecture` rule on when `plan-tool detail` may be named: the verb is an unblock for a specific BLOCKED or withheld finding (steps 3 and 4), never a detail-coverage remedy, and nothing this step emits may name it.
- **`diagnostic_remedies`** — reads `jira_grade` only, has no bare arm, not part of this fence.
- **`_blocked_next_step`** — step 3 owns it. This step does not make its `split`-first wording live; the plan's `## Problem statement` records that a bare `--iterate` run already reaches it through the deterministic applies. Opening the conceptual route adds traffic to a path that already fires.

**One caller outside this module changes, and it is step 5's.** `plan_tool/cli/completeness_phases.py` calls `suggested_next_step_commands` with `bundle_status=` and `correctness=` keywords and falls back to a `run` pointer only when the returned list is empty — with a correctness gap present that list is now non-empty, so the bare fallback description simply stops firing on that path, with no edit. The one thing that does need wiring is `console_summary`'s new `bundle_status` argument in `_persist_and_present_report`; that is step 5's file and step 5's line. Both next-step renderers' public signatures stay exactly as they are.

**Sweep the prose in the same edit.** The helper docstring, both renderer docstrings, and `console_summary`'s docstring state the fence in words ("Both are withheld in a bare-plan audit"). A stale sentence beside the new behavior is the defect this plan's step 7 exists to prevent at the repo level; do not leave one here.

## Tests

All cases live in `tests/test_completeness_report.py`. Reuse the existing `_steps(**kw)` and `_cmds(**kw)` builders and the `_rec(...)` factory — no new fixtures.

### Tests for this step

New cases (approx. 9):

- `test_next_steps_bare_plan_keeps_correctness_apply_route` — `_steps(correctness=[...], bundle_status=SimpleNamespace(is_bare=True))` names `plan-tool completeness-apply p` and does not fall through to the "No gaps left to close — `plan-tool run p`" bullet. That is the branch a correctness-only bare run actually reaches; the "No structural gaps left to close in this bare-plan audit" line needs `bare_detail_diagnostic_count or advisory_conceptual` and never fires here.
- `test_next_steps_bare_plan_correctness_bullet_omits_completeness_promise` — the same bare run's correctness bullet does not promise to walk the completeness gaps, and says they stay informational until a detail bundle exists.
- `test_next_steps_bare_plan_both_axes_names_only_correctness_as_appliable` — bare, both finding sets supplied: exactly one `completeness-apply` bullet, counting only the correctness gaps.
- `test_next_step_commands_bare_plan_keeps_correctness_apply_route` — `_cmds` with the same bare + correctness input returns a `plan-tool completeness-apply p` tuple whose description names the correctness effect and omits the conceptual-walk effect.
- `test_next_step_commands_bare_plan_correctness_still_omits_detail_authoring` — bare + correctness + a `detail-coverage` finding: the apply command appears, `plan-tool detail p` does not. Pins that opening the conceptual route did not reopen the detail-authoring vocabulary.
- `test_jira_grade_withholds_correctness_apply_on_a_bare_plan` — `detail_grade=GRADE_JIRA` with `is_bare=True` withholds both axes in both renderers. Pins that the two gates are independent, not that bare implies jira.
- `test_report_bare_plan_withheld_paragraph_names_the_completeness_axis` — `build_report_md` on a bare plan: the conceptual-completeness intro scopes "withheld" to that axis and does not claim apply actions are withheld outright.
- `test_report_bare_plan_correctness_intro_omits_completeness_walk_promise` — bare plan with correctness gaps: the `## Conceptual correctness` intro names `completeness-apply` and does not say "then the completeness gaps" / "before the completeness gaps".
- `test_report_detailed_plan_correctness_intro_unchanged` — `is_bare=False`: today's joint-walk wording is unchanged.
- `test_console_summary_bare_plan_completeness_line_omits_the_apply_verb` — `console_summary(..., bundle_status=SimpleNamespace(is_bare=True))` with `advisory_conceptual` recs says those gaps stay informational and does not name `plan-tool completeness-apply` for them.
- `test_console_summary_bare_plan_keeps_the_correctness_apply_verb` — the same call with `correctness` recs still names the verb on the correctness line.
- `test_console_summary_without_bundle_status_is_unchanged` — `bundle_status=None` reproduces today's output for every combination, which is what makes the un-wired call site safe.

Inherited cases this step **rewrites** (they pin the old both-axes fence or the old blanket withheld paragraph, and are expected to change):

- `test_next_step_commands_correctness_withheld_in_bare_plan` — invert it: a bare plan now emits the `completeness-apply` line for correctness gaps. Rename it to match.
- Step 1's `test_actionable_conceptual_gaps_bare_plan_withholds_both` — becomes a withholds-completeness-only case against whatever the landed helper's name and return shape are.
- The case asserting the literal `Apply actions are withheld until a complete detail bundle exists` in `build_report_md`'s output — rewrite it against the axis-scoped sentence, keeping its "the completeness findings are informational" intent.

Cases that must stay green **with no edits** — this is the regression net:

- `test_next_steps_bare_plan_suppresses_conceptual_apply_action` (completeness gaps only, still withheld)
- `test_next_step_commands_bare_plan_suppresses_conceptual_apply_action`
- `test_next_steps_bare_plan_suppresses_detail_authoring_actions`
- `test_next_step_commands_bare_plan_suppresses_detail_authoring_actions`
- `test_next_steps_correctness_points_at_completeness_apply_not_reaudit`
- `test_next_steps_correctness_and_completeness_emit_one_apply_line`
- `test_next_step_commands_count_correctness_gaps`
- `test_next_step_commands_detailed_plan_keeps_detail_level_actions`
- `test_suggested_next_steps_grade_jira_withholds_apply_bullets`
- `test_suggested_next_step_commands_grade_jira_withholds_apply`
- `test_report_bare_plan_omits_conceptual_apply_address`
- `test_next_step_commands_parse_against_live_parser`
- Step 1's `test_next_steps_and_commands_share_one_apply_fence` — written as an agreement assertion between the two renderers, so it stays meaningful across this change. If it needs an edit, the two renderers drifted.

**Green-before-done gate:** every case above must pass before this step is finished. Run `uv run pytest tests/test_completeness_report.py -q` for the fast loop, then `uv run pytest -m "not integration" tests/ -q` before calling it done, since `plan_tool/cli/completeness_phases.py` consumes one of these renderers.

## Acceptance criteria

- On a bare plan at run grade with at least one `plan-correctness` finding, `suggested_next_steps` returns a bullet containing `plan-tool completeness-apply <name>`, and `suggested_next_step_commands` returns a tuple whose command is `plan-tool completeness-apply <name>`.
- On a bare plan with only `plan-completeness` findings, neither renderer names `completeness-apply` — output is unchanged from before this step.
- At `GRADE_JIRA`, neither renderer names `completeness-apply` for either axis, bare or detailed.
- With `bundle_status=SimpleNamespace(is_bare=False)` (and with `bundle_status=None`), both renderers produce the same output as before this step for every combination of finding sets.
- The bare correctness bullet does not contain a promise to apply the completeness gaps.
- `grep -c 'bare_plan or jira_grade' plan_tool/completeness_report.py` still returns 0 or 1 (step 1's `gate:`, unbroken).
- `grep -c 'Apply actions are withheld until a complete detail bundle exists' plan_tool/completeness_report.py` returns 0.
- `build_report_md`'s bare-plan conceptual-correctness intro names `completeness-apply` for correctness gaps only and does not promise a completeness-gap walk; the detailed-plan intro text is unchanged. The per-finding `Address:` sub-bullet gate is unchanged.
- `console_summary` names `plan-tool completeness-apply` on its correctness line for a bare plan and does not name it on its conceptual-completeness line; with `bundle_status=None` its output is byte-identical to before this step.
- The public signatures of `suggested_next_steps` and `suggested_next_step_commands` are unchanged (same parameter names, order, defaults). `console_summary` gains exactly one keyword-only parameter, defaulting to `None`.
- No output this step produces names `plan-tool detail` — the verb is reserved for a specific BLOCKED or withheld finding (steps 3 and 4) per the plan's `## Architecture`.
- `plan_tool/cli/completeness_phases.py` is not modified by this step.
- `uv run pytest tests/test_completeness_report.py -q` is green; `uv run pytest -m "not integration" tests/ -q` is green.

## References

- [`plan_tool/completeness_report.py`](../../../plan_tool/completeness_report.py) — the whole step lands here; read the step-1 fence helper, both next-step renderers, and `CORRECTNESS_INTRO` / `_HAND_FIX_INTRO`.
- [`plan_tool/review.py`](../../../plan_tool/review.py) — `DetailBundleStatus.is_bare` and `audit_detail_bundle_status`, the binary fact the fence routes on.
- [`plan_tool/prompts/apply-finding.md`](../../../plan_tool/prompts/apply-finding.md) — the apply contract that edits the plan file "and/or the step's detail file **if applicable**" and reserves `BLOCKED` for a genuinely missing detail file; the evidence a plan-body-only correctness edit needs no detail bundle.
- [`plan_tool/cli/completeness_phases.py`](../../../plan_tool/cli/completeness_phases.py) — the console caller of `suggested_next_step_commands` and its empty-list fallback; confirms no caller change is needed.
- [`tests/test_completeness_report.py`](../../../tests/test_completeness_report.py) — the `_steps` / `_cmds` / `_rec` builders and the bare/jira regression net.
- [`docs/AUDIT_FLOW.md`](../../../docs/AUDIT_FLOW.md) — the audit flow's gate reference, which restates this fence; step 7 updates it.

## Applicable guardrails

- **The plan's `## Out of scope`, per-finding coverage routing refusal** — the fence stays at plan level. Do not read `rec.step_id`, an anchor prefix, or any per-finding coverage signal to decide whether a single finding is appliable.
- **The plan's `## Out of scope`, "no new gate, exit-code flip, blocking severity, or refusal-to-advance"** — this step changes rendering only. Nothing it computes may reach a severity check, `has_blocking_findings`, or an exit code.
- **The plan's `## Out of scope`, jira-grade behavior** — the jira arm of the fence is untouched. Widening the split to jira grade is out of bounds.
- **The plan's `## Out of scope`, no new persisted detail-coverage field** — this step persists nothing and adds no field to any saved artifact or to `DATA_CONTRACT.md`.
- **The plan's `## Architecture`, decision 1 (split by axis at plan level)** — this step is that split, and nothing more. It does not touch decision 2's `BLOCKED` remedy or decision 3's prompt directive.
- **The plan's `## Architecture`, when `plan-tool detail` may be named on a bare plan** — only as the unblock for a specific BLOCKED or withheld finding. This step names no per-finding blocker, so it names the verb nowhere.
- **The plan's `## Risks`, six surfaces describe one run** — this step owns three of them (the report prose, the console block, `console_summary`). Any wording change must leave all three answering the same question the same way, and matching the surfaces steps 4 and 5 own (including step 4's `--iterate` halt stderr).

## Deferred

- **The `BLOCKED` next-step remedy** — step 3 owns `_blocked_next_step`. Its `split`-first wording is already reachable on a bare plan through the `--iterate` loop's deterministic applies (the plan's `## Problem statement` records the mechanism); this step adds the conceptual applies to that traffic and step 3 is what stops the bullet pointing an operator at `plan-tool split` for a detailing problem.
- **Wiring `console_summary`'s new `bundle_status` argument at its call site** — `_persist_and_present_report` lives in `plan_tool/cli/completeness_phases.py`, which is step 5's declared file. The parameter's `None` default keeps this step correct on its own until step 5 passes it.
- **The grouped report's bare-plan next-steps surface** — step 5 owns `plan_tool/cli/completeness_phases.py`. It is the last surface to come into line and must end up saying the same thing as these.
- **Narrowing bare-step edge-case findings in the audit prompt** — step 6, in `plan_tool/review.py`. Unrelated to the fence.
- **`CLAUDE.md` § "Correctness gates", `docs/AUDIT_FLOW.md`, and BACKLOG #83** — step 7 sweeps the blanket "detail-level actions unlock only once a complete detail bundle exists" claim this step falsifies.
- **Consolidating the `getattr(bundle_status, "is_bare", False)` read across the three sites in this module** — a wider cleanup touching `build_report_md`'s unrelated prose selection. File it in `BACKLOG.md` if it still looks worth doing.
