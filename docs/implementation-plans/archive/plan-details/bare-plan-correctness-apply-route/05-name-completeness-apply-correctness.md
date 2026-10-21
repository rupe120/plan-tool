> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Name `completeness-apply` for correctness gaps in the grouped report's bare-plan next steps

## Summary

Make the `### Suggested next steps` block inside `_render_grouped_report` (`plan_tool/cli/completeness_phases.py`) say the same thing about a bare plan's conceptual-correctness gaps that the report prose and console block already say after step 2: name `plan-tool completeness-apply <name>` for them, and keep withholding it for the conceptual-completeness gaps. The key decision is that **one flag decides which bullet owns the correctness findings** — when the new bare-plan apply bullet takes them, they stop feeding the `_structural` trigger, so the block never offers two different remedies for one finding set. A fully-detailed plan's next steps and every jira-grade next step stay exactly as they are. On green, a bare-plan audit with a correctness gap ends its embedded report with a runnable apply command instead of a re-audit suggestion that cannot apply it.

## Table of Contents

- [Summary](#summary) — what changes and what stays the same.
- [Why](#why) — the last next-steps surface still describing the old fence.
- [Input](#input) — the contracts this block reads and the one limit on checking it.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — where the bullet goes, the flag that keeps the remedies from doubling, the jira trap, and the alternative rejected.
- [Tests](#tests) — the new cases, the three inherited assertions this step rewrites, and the regression net.
- [Acceptance criteria](#acceptance-criteria) — checkable facts.
- [References](#references) — what to read before starting.
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step.
- [Deferred](#deferred) — nearby work this step does not take, and who owns it.

## Why

One completeness run prints *next steps* in three places (the plan's `## Risks` counts six operator surfaces in total, adding step 4's withheld notice, `console_summary`, and the `--iterate` halt stderr). Two of the three — `suggested_next_steps` and `suggested_next_step_commands` in `plan_tool/completeness_report.py` — are step 2's, and after it lands they name `plan-tool completeness-apply` for a bare plan's correctness gaps. The third is the `### Suggested next steps` block at the bottom of the grouped report that `_render_grouped_report` builds; it is embedded in the saved report through `build_report_md(grouped_report_md=…)` and printed straight to stdout on the audit-only path, so an operator reads it on every non-`--iterate` run. That block still routes correctness through its `_structural` trigger, which offers `plan-tool completeness-audit <name> --iterate` — a command that, under the read-only-audit split, re-audits and applies deterministic findings but never applies a `plan-correctness` gap. So after step 2 the same run tells the operator to run `completeness-apply` at the top of the report and to re-run `--iterate` at the bottom. This step makes the third surface agree, which is the whole reason it is in the plan.

## Input

- **Step 2's outcome, not its mechanism.** Step 2 splits the apply fence by axis so a bare plan's correctness gaps keep the `completeness-apply` route and its completeness gaps do not. This step owes the same answer in the grouped block. Read step 2's landed helper only to confirm the axis — do not import from `plan_tool/completeness_report.py` here and do not copy its sentence.
- **The two rec lists the callers already split.** `finalize_completeness_run` in `plan_tool/cli/completeness_cmd.py` and `write_pre_apply_audit_checkpoint` in this module both split the audit set on each rec's `source` field (`plan_tool/review.py:Recommendation`) before calling: `correctness_recs` is the `plan-correctness` subset, `conceptual_recs` is the `plan-completeness` subset, and `audit_recs` is the whole set. The block never re-splits; it reads the two lists it is handed. No persisted contract surface is involved — this is an in-memory field read.
- **`DetailBundleStatus.is_bare`** (`plan_tool/review.py`, computed by `audit_detail_bundle_status`) — `True` when at least one step has no detail file for the grade being audited. `_render_grouped_report` already reads it once, defensively, into its `_bare_plan` flag, because `bundle_status` defaults to `None` and the suites pass a `SimpleNamespace`. Reuse that flag; do not add a second read.
- **`detail_grade`** — compared against `GRADE_JIRA` into the function's `jira_grade` flag. The jira arm is a separate rule with a separate reason (no sidecar is written, so no apply verb can replay anything) and this step does not touch it.
- **What cannot be checked here.** The grouped report is rendered *before* `_persist_and_present_report` writes the sidecar, so naming `completeness-apply` is a promise about a write that has not happened yet. That is the same assumption the existing completeness bullet already makes on a detailed plan, and this step does not change it. There is no reordering to do — the sidecar write is not conditional on anything the block can see.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_phases.py` — inside `_render_grouped_report`'s `### Suggested next steps` block: add the bare-plan correctness apply bullet, add the flag that decides whether `_structural` still claims the correctness findings, adjust **both** `_structural` arms' wording so neither names findings it no longer owns, and narrow the bare-plan fallback line so it stops asserting a blanket detail-bundle rule. Separately, in `_persist_and_present_report`: pass `bundle_status` into `console_summary` (step 2 added the parameter).
  - `tests/cli/test_completeness_cmd.py` — new cases in `TestRenderGroupedReport` (bare + correctness, at both grades, and the bare `--iterate` arm) and one in `TestGradedGroupedReportProse` for the detailed-plan no-change guard; rewrite the three inherited assertions that pin the old fallback wording.

## Implementation

**What must be true when this is done**

- On a bare plan at run grade with at least one `plan-correctness` finding, the block names `plan-tool completeness-apply <name>` and counts only the correctness gaps.
- The same run does **not** also point the correctness findings at `plan-tool completeness-audit --iterate` or `plan-tool reconcile-plan-walk` — on **either** arm of `_structural`, including the `iterate_enabled` one. One finding set, one remedy.
- Completeness gaps on a bare plan stay unappliable — the existing `conceptual_recs and not _bare_plan and not jira_grade` condition on the completeness bullet is unchanged.
- Nothing in the block names `plan-tool detail` on a bare plan.
- A fully-detailed plan (`bundle_status=None` or `is_bare=False`) and every jira-grade run produce the same text as before.

**Recommended shape**

- **Give the decision one name.** Compute a single flag near the existing `_bare_plan` / `_structural` / `_missing_detail` / `_detail_level` flags — something like `_correctness_apply = bool(correctness_recs) and _bare_plan and not jira_grade` — and let both the new bullet and the `_structural` expression read it. Two independent conditions that must stay in step is the drift this plan's Risks section is about.
- **Take correctness out of `_structural` only when the new bullet takes it.** `_structural`'s correctness term becomes "correctness recs that the apply bullet is not covering" (`correctness_recs and not _correctness_apply`), not "correctness recs on a non-bare plan". This is the part that is **not free to vary** — see the trap below.
- **Place the new bullet just before the completeness bullet**, so the block reads correctness first, then completeness — the same order `suggested_next_steps` uses. The exact position among the earlier deterministic bullets is not critical; keeping it ahead of the completeness bullet is.
- **Wording:** one line, naming the verb, the count, and what it does *not* cover. Something in the shape of `` `plan-tool completeness-apply <name>` — walk the N conceptual-correctness gap(s) and apply the edits (plan-body design gaps; the completeness gaps stay informational until a detail bundle exists) ``. Stay close to the vocabulary already in this block and in step 2's bullet; do not invent a third phrasing for the same idea.

**The trap: do not key the `_structural` narrowing on `_bare_plan`**

At jira grade a bare plan's correctness findings have no apply route at all — they reach the reader through `_structural`'s jira arm, the "Read and fix the finding(s) above by hand — this grade writes no findings sidecar" line. If the correctness term is narrowed with `and not _bare_plan`, a jira-grade bare audit whose only findings are correctness gaps loses that arm, `_next_steps` comes back empty, and the tail falls through to the `elif has_any` branch, which labels them "Remaining finding(s) above are advisory (info/nit)". A HIGH correctness finding reported as advisory is a worse defect than the one this step fixes. Keying the narrowing on the flag above avoids it because the flag is already `False` at jira grade. Test 6 below exists for exactly this case.

**The `_structural` bullet must stop naming what it no longer owns — on both arms**

Its run-grade text ends "…to auto-apply the deterministic/correctness finding(s) above." When the flag is on, that bullet is about the deterministic findings only, so pick the noun from the flag — one f-string variable, no new branch. Leave the text alone when the flag is off, so the detailed path does not move.

**The `iterate_enabled` arm is not exempt, and this is the part that is easy to get wrong.** That arm prints `plan-tool reconcile-plan-walk <name>` and says "the finding(s)" with no axis claim, which reads as harmless — but the generic review walk **cannot apply `plan-correctness`**: `_APPLY_AS_FINDING_SOURCES` in `plan_tool/review_walk.py` excludes it and `cmd_review_walk` passes no `extra_apply_sources`. So on a bare `--iterate` run carrying any other structural finding, `_structural` stays true and the block offers the correctness gaps a second remedy that is guaranteed not to close them. Narrow the correctness term with `_correctness_apply` on this arm too, and make its noun follow the flag the same way. When the flag is on, the reconcile bullet is about the findings the apply bullet did not claim.

**Narrow the bare fallback line — and know it is one of two copies**

The `if not _next_steps:` tail's bare branch currently says apply actions require a complete detail bundle. That is the blanket claim step 7 is removing from `CLAUDE.md`. It ships in **two** places in the code: this block, and `build_report_md`'s bare-plan conceptual-completeness paragraph in `plan_tool/completeness_report.py` ("Apply actions are withheld until a complete detail bundle exists"), which **step 2** narrows in its own file. This step owns only the copy in this module — step 7's files reach neither, so between them steps 2 and 5 cover both. Keep the branch's condition as it is (it can only fire when no correctness gaps exist, since the new bullet fills the list) and narrow the sentence to the axes it is actually about: detail-level and conceptual-**completeness** findings stay informational until a detail bundle exists. One line, same shape, and close enough to step 2's sentence that a reader sees one rule.

**Wire `console_summary`'s `bundle_status` argument**

Step 2 gives `console_summary` a keyword-only `bundle_status=None` so its conceptual-completeness line can be axis-scoped on a bare plan. The call site is `_persist_and_present_report` in this module, which is why the one-line wiring is here rather than there. Pass the same `bundle_status` the function already hands `suggested_next_step_commands`; add no second read and no new parameter to `_persist_and_present_report` itself. Without this line step 2's branch is dead code on the real path.

**Same-file sites to leave alone — confirm zero diff rather than improving them**

- `emit_bare_plan_banner` — a stderr banner about grounding; it names no apply verb and needs none.
- `_render_completeness_json` — the `--json` payload carries findings, not next steps.
- `_persist_and_present_report`'s empty-list console fallback — that block delegates to step 2's `suggested_next_step_commands`; with a correctness gap present the returned list is no longer empty, so the fallback simply stops firing there. No edit. (The `console_summary` call in the same function *is* edited — one added keyword argument, nothing else.)
- `write_pre_apply_audit_checkpoint` — renders through the same function and inherits the new behavior for free.

**Alternative rejected: import step 1/2's fence helper into this block.** It would give all three surfaces one definition of the fence, which is attractive. It does not fit: the helper answers "which axes are appliable", while this block additionally decides *which of its bullets* names the verb — and on a detailed plan it deliberately routes correctness through `_structural` rather than an apply bullet. Wiring the helper in straight would add a correctness apply bullet to detailed-plan output, which the plan's acceptance requires to be unchanged. Reuse the same fact (`is_bare`), not the same code.

## Tests

All cases live in `tests/cli/test_completeness_cmd.py`. Reuse the existing `_rec(severity, source=…)` factory, `_empty_det()`, `_DeterministicReport`, and the `SimpleNamespace(is_bare=…, is_fully_bare=…, detailed_count=…, total=…)` bundle-status stand-in the bare cases already use — no new fixtures, no monkeypatching (this function is pure string assembly and makes no claude call).

### Tests for this step

New cases (9), in `TestRenderGroupedReport` unless noted:

- `test_bare_plan_correctness_names_completeness_apply` — bare plan, one `plan-correctness` rec: the suggested block contains `plan-tool completeness-apply p` and does not fall through to the informational tail.
- `test_bare_plan_correctness_bullet_counts_only_correctness_gaps` — bare, 2 correctness + 3 completeness recs: exactly one `completeness-apply` bullet, its count is 2, and it does not promise to walk the completeness gaps.
- `test_bare_plan_correctness_replaces_the_iterate_reaudit_bullet` — bare, correctness recs and no deterministic findings: `completeness-audit p --iterate` is absent from the block, so the correctness findings carry one remedy.
- `test_bare_plan_deterministic_finding_keeps_its_own_iterate_bullet` — bare, a body issue plus correctness recs: both bullets appear, and the `--iterate` bullet no longer names the correctness findings.
- `test_bare_plan_iterate_arm_does_not_offer_reconcile_walk_for_correctness` — bare, `iterate_enabled=True`, correctness recs plus one other structural finding: the `plan-tool reconcile-plan-walk` bullet is present for that other finding and does not name the correctness findings. Guards the arm the generic walk cannot apply `plan-correctness` on.
- `test_persist_and_present_passes_bundle_status_to_console_summary` — the printed summary for a bare `--iterate` run omits `plan-tool completeness-apply` on its conceptual-completeness line. Pins the wiring, not step 2's branch.
- `test_bare_plan_correctness_omits_detail_authoring` — bare, correctness recs plus a `missing_on_disk` `DetailCoverageIssue`: `plan-tool detail` stays out of the block.
- `test_jira_grade_bare_plan_correctness_keeps_hand_fix_bullet` — bare at `GRADE_JIRA` with correctness recs: the hand-fix line is present, `completeness-apply` is absent, and the block never labels the findings advisory (info/nit). Guards the trap named in Implementation.
- `test_detailed_plan_correctness_next_steps_unchanged` (in `TestGradedGroupedReportProse`) — `is_bare=False` with correctness recs: still the `completeness-audit demo --iterate` bullet, and no correctness `completeness-apply` bullet. Guards the plan's "fully-detailed unchanged" criterion.

Inherited assertions this step **rewrites** — they pin the fallback line's old blanket wording and are expected to change; the behavior each one covers stays the same:

- `test_bare_plan_missing_detail_omits_detail_authoring_next_step` — update the fallback-phrase assertion; keep the `plan-tool detail` absence assertion untouched.
- `test_bare_plan_conceptual_findings_omit_apply_next_step` — keep the `completeness-apply`-absent assertion (completeness-only on a bare plan is still withheld); update the fallback phrase.
- `test_partial_detail_body_issue_omits_iterate_next_step` — same fallback-phrase update; keep the `completeness-audit p --iterate` absence assertion.

Cases that must stay green **with no edits** — the regression net:

- `test_grade_run_next_steps_unchanged` and `test_grade_jira_next_steps_omit_apply_and_iterate` (both in `TestGradedGroupedReportProse`)
- `test_bare_plan_header_drops_false_grounding_claim`
- `test_blocking_self_consistency_next_step_names_no_apply_verb_at_jira_grade`
- `test_non_intent_self_consistency_next_step_says_manual_edit` and `test_advisory_self_consistency_rec_keeps_the_advisory_tail`
- `test_correctness_group_always_present`

**Green-before-done gate:** every case above passes before this step is finished. Fast loop: `uv run pytest tests/cli/test_completeness_cmd.py -q`. Before calling it done: `uv run pytest -m "not integration" tests/ -q`, since `tests/test_completeness_report.py` and `tests/test_cli.py` also read the report this block is embedded in.

## Acceptance criteria

- `_render_grouped_report` with `bundle_status` reporting `is_bare=True`, `detail_grade=GRADE_RUN`, and a non-empty `correctness_recs` returns markdown whose `### Suggested next steps` block contains `plan-tool completeness-apply <name>`.
- The same call's block does not contain `plan-tool completeness-audit <name> --iterate` when the deterministic buckets are empty.
- On the same input with `iterate_enabled=True` and one non-correctness structural finding, the `plan-tool reconcile-plan-walk <name>` bullet does not name the correctness findings.
- The same call's block does not contain `plan-tool detail` — the block names no per-finding blocker, so the plan's `## Architecture` rule gives it no occasion to.
- `_persist_and_present_report` passes `bundle_status` to `console_summary`, and a bare `--iterate` run's printed summary does not name `completeness-apply` on its conceptual-completeness line.
- With `is_bare=True` and only `conceptual_recs` (source `plan-completeness`), the block still contains no `completeness-apply` — the completeness axis is unchanged.
- With `is_bare=True`, `detail_grade=GRADE_JIRA`, and correctness recs, the block contains the hand-fix line, contains no `completeness-apply`, and does not describe the findings as advisory.
- With `bundle_status=None` or `is_bare=False`, the block's text is the same as before this step for every combination of `correctness_recs` / `conceptual_recs` / deterministic buckets.
- The bare-plan fallback line no longer states that apply actions require a complete detail bundle; it names the detail-level and conceptual-completeness axes only. `grep -c 'apply actions require a complete detail bundle' plan_tool/cli/completeness_phases.py` returns 0.
- `_render_grouped_report`'s signature is unchanged — same parameter names, order, and defaults.
- The function reads `is_bare` exactly once (the existing `_bare_plan` flag); `grep -c 'is_bare' plan_tool/cli/completeness_phases.py` does not grow beyond its current count plus the `emit_bare_plan_banner` uses already there.
- `uv run pytest tests/cli/test_completeness_cmd.py -q` is green; `uv run pytest -m "not integration" tests/ -q` is green.

## References

- `plan_tool/cli/completeness_phases.py` — this step's file: `_render_grouped_report`'s `### Suggested next steps` block and its `_bare_plan` / `_structural` / `_missing_detail` / `_detail_level` / `_next_steps` locals; also `emit_bare_plan_banner`, `_render_completeness_json`, `write_pre_apply_audit_checkpoint`, and `_persist_and_present_report`'s console fallback — the same-file sites this step leaves alone.
- `plan_tool/completeness_report.py` — step 2's landed fence in `suggested_next_steps` / `suggested_next_step_commands`, plus `CORRECTNESS_INTRO` and `build_report_md`. Read to confirm the axis and borrow vocabulary; not to import from.
- `plan_tool/cli/completeness_cmd.py` — `finalize_completeness_run`, the main caller that splits `audit_recs` on `Recommendation.source` and passes `bundle_status` and `detail_grade`; `cmd_completeness_apply`'s bare gate is step 4's, not this step's.
- `plan_tool/review.py` — `audit_detail_bundle_status` and `DetailBundleStatus.is_bare`, the one fact this block routes on.
- `plan_tool/prompts/apply-finding.md` — the apply contract that edits the plan file "and/or the step's detail file **if applicable**"; the evidence a plan-body-only correctness edit needs no detail bundle.
- `tests/cli/test_completeness_cmd.py` — `TestRenderGroupedReport` and `TestGradedGroupedReportProse`, plus the `_rec` / `_empty_det` / `_DeterministicReport` builders.
- `CLAUDE.md` § "Correctness gates" and `docs/AUDIT_FLOW.md` — restate the blanket detail-bundle contract this plan replaces; step 7 corrects them, not this step.

## Applicable guardrails

- **The plan's `## Out of scope`, per-finding coverage routing refusal** — the decision stays at plan level. Do not read `rec.step_id`, an anchor prefix, or any per-finding coverage signal to decide whether an individual correctness finding gets the bullet.
- **The plan's `## Out of scope`, "no new gate, exit-code flip, blocking severity, or refusal-to-advance"** — this step renders text. Nothing it computes may reach `_completeness_has_blocking_findings`, a severity check, or the `--fail-on-findings` return code.
- **The plan's `## Out of scope`, jira-grade behavior** — the jira arm keeps its own rule and its own text. The only jira-related work here is making sure the narrowing does not accidentally remove its hand-fix bullet.
- **The plan's `## Out of scope`, no new persisted field** — this step writes nothing and adds no field to the sidecar or `DATA_CONTRACT.md`.
- **The plan's `## Architecture`, decision 1 (split by axis at plan level)** — this step carries that split into the last next-steps surface and nothing more. It does not touch decision 2's `BLOCKED` remedy or decision 3's prompt directive.
- **The plan's `## Architecture`, when `plan-tool detail` may be named on a bare plan** — only as the unblock for a specific BLOCKED or withheld finding. This block surfaces neither, so it names the verb nowhere. That is the rule, not an arbitrary omission.
- **The plan's `## Risks`, six surfaces describe one run** — the grouped block must answer the same question the same way as step 2's three surfaces, step 4's withheld notice, and the `--iterate` halt stderr. A wording difference here is the defect, not a style choice.
- **The plan's `## Acceptance criteria`, fully-detailed and jira-grade unchanged** — this is the boundary on the whole edit: every new condition is gated so the detailed and jira paths render the same text as before.

## Deferred

- **The `completeness-apply` verb's own bare-plan gate** — step 4 owns `cmd_completeness_apply` in `plan_tool/cli/completeness_cmd.py`, and it lands before this step, so the command this block names already works.
- **`build_report_md`'s copy of the blanket withheld sentence** — step 2 narrows it in `plan_tool/completeness_report.py`. The claim ships in two places; this step owns one of them.
- **The `BLOCKED` next-step remedy** — step 3 owns `_blocked_next_step` in `plan_tool/completeness_report.py`. That surface renders after an apply walk and never appears in this block.
- **`CLAUDE.md`, `docs/AUDIT_FLOW.md`, and BACKLOG #83** — step 7 sweeps the blanket detail-bundle claim from the docs. This step only fixes the copy of that claim inside its own rendered output.
- **The `--iterate` bullet's "deterministic/correctness" wording on a fully-detailed plan** — under the read-only-audit split the loop does not apply conceptual-correctness findings there either, so the same reader question exists on the detailed path. Out of bounds here because the plan requires detailed output unchanged; file it in `BACKLOG.md` if it still looks worth doing once step 7 lands.
- **One shared definition of the bare fence across all three next-step surfaces plus the apply verb's gate** — a cross-module change touching `plan_tool/completeness_report.py`, this module, and `plan_tool/cli/completeness_cmd.py`, which a detail file cannot mint. Route it to `BACKLOG.md` after the plan ships, with the evidence rule for consolidation entries in mind.
