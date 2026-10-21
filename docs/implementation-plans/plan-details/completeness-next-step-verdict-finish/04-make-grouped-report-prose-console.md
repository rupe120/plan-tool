# Step 4 — Make the grouped report, prose, console, and `_authoring_guidance` take their gap list, count, and next command from the verdict

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes every reader that names gaps, counts them, or prints a next command take those three things from the one `BlockingVerdict` that `finalize_completeness_run` builds. The readers are the grouped report in `plan_tool/cli/completeness_phases.py:_render_grouped_report`, the prose and console helpers in `plan_tool/completeness_report.py`, and `_authoring_guidance` in `plan_tool/cli/authoring.py`. Steps 1–3 supply the verdict (three untrusted causes, retained ids on an incomplete audit, a single finalize input). This step then fixes whatever a reader still derives from a second source. The key decision is that readers differ only in presentation: the close list, the count, and the next command come from `next_step_gaps`, `blocking_count`, and `next_stage_command`/`_reaudit_command`, and no reader recomputes any of them. On green, an incomplete or stale verdict names the same gaps and the same command in the report, the summary bullets, the console block, and the post-authoring guidance. The `--json` payload, `--fail-on-findings`, and exit codes do not change.

## Table of Contents

- [Why](#why) — which reader seams still disagree
- [Input](#input) — what steps 1–3 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — enumerate first, then one source per reader
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — observable results
- [Applicable guardrails](#applicable-guardrails) — fences that bind this step
- [Deferred](#deferred) — work left out

## Why

A reader that names gaps can reach them by several routes today: the verdict, the raw gate ids, the saved findings, or a bare "no verdict, so nothing" default. Once step 2 gives an incomplete verdict its ids and step 1 gives it a stale-revision cause, any reader still on an older route will print a count that disagrees with the console, or a close list that the next-command text contradicts. One reader is the clearest case: `_authoring_guidance` in `plan_tool/cli/authoring.py` falls back to a fixed fresh-audit follow-up whenever the tail result no longer matches the artifacts on disk. That answer carries no gap list and no cause, so it cannot say why a re-audit is needed or which gaps were established. This step removes those seams so the verdict's wording stays the same across surfaces.

## Input

- **Step 1** supplies `untrusted_cause` with `transient`, `persistent`, and `stale-revision`, plus the reason text `_reaudit_command` returns for each. Read the landed constant names from `plan_tool/completeness_report.py`; HEAD wins over this file.
- **Step 2** supplies retained blocking ids on an `incomplete` verdict, so `BlockingVerdict.blocking_count` and `next_step_gaps` see them. The gate pair (`has_blocking`, `conceptual_bar_blocking_ids`, `audit_incomplete`) stays on `--json`, `--fail-on-findings`, and exit codes.
- **Step 3** makes `finalize_completeness_run` hand the verdict to every reader and removes the dead deterministic splice in `_render_grouped_report`'s fresh-audit branch.
- **Verdict readers at HEAD** (the enumeration below starts here; it is not complete until the searches are run):
  - `next_step_gaps`, `_reaudit_command`, `next_stage_command`, `reaudit_step`, `_close_conceptual_steps`, `_blocking_deterministic_steps` in `plan_tool/completeness_report.py`.
  - `suggested_next_steps`, `suggested_next_step_commands`, `console_summary`, and `build_report_md` in the same file.
  - `_render_grouped_report` in `plan_tool/cli/completeness_phases.py` (its "Suggested next steps" block).
  - `_authoring_guidance`, `_CompletenessTailOutcome`, and `_run_completeness_tail` in `plan_tool/cli/authoring.py`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — move any list, count, or command still computed outside the verdict onto `next_step_gaps` / `blocking_count` / `_reaudit_command`; make the prose and console text name the cause the verdict carries.
  - `plan_tool/cli/completeness_phases.py` — `_render_grouped_report`: derive the close list, count, and command only from the `verdict` argument and the helpers above.
  - `plan_tool/cli/authoring.py` — `_authoring_guidance`: when the tail result is not current, carry the tail verdict's gap count and re-audit reason into the follow-up row instead of the fixed fresh-audit row alone.
  - `plan_tool/cli/completeness_cmd.py` — only if a call into the readers still passes raw gate ids where the verdict belongs; likely a no-op after step 3, confirm by search.
  - `tests/test_completeness_report.py`, `tests/cli/test_authoring_cmds.py`, `tests/cli/test_completeness_cmd.py` — the cases listed under Tests.

## Implementation

- **Enumerate before editing.** Name the defect class in one sentence: a reader derives a gap list, count, or next command from something other than the verdict. Then run two searches and write the result into `handoffs/2026-10-10-completeness-next-step-verdict-finish-reader-enumeration.md` as the step's first deliverable, before any reader edit:
  - **By identifier:** `blocking_ids`, `conceptual_bar_blocking_ids`, `blocking_count`, `next_step_gaps`, `_verdict_offers_stage`, `_blocking_deterministic_steps`, `_reaudit_command`, `reaudit_step`, `next_stage_command`, `_fresh_audit_required`, and `ABSENT_BLOCKING_VERDICT`, across `plan_tool/` and `tests/`.
  - **By vocabulary:** the phrases readers print — "no gaps", "gaps remain", "blocking gap(s)", "verdict incomplete", "advisory", "re-audit", "fresh audit" — in `plan_tool/completeness_report.py`, `plan_tool/cli/`, `docs/how-to/pipeline/audit.md`, and `docs/OPERATIONS.md`.
  - For each site, record one of: moved onto the verdict, already on the verdict, or stays on the gate (with the reason). Sites that stay on the gate are `_render_completeness_json`, `_completeness_has_blocking_findings`, and the qualified-result classifier.
- **One source per fact.** The close list comes from `next_step_gaps(verdict, …)`. The count comes from `verdict.blocking_count` and `NextStepGaps.close_count`. The command comes from `next_stage_command` (which returns `_reaudit_command` for anything but a completed empty set). A reader must not reach the same fact by a second route.
- **An incomplete or stale verdict reads as open.** It names its retained gaps, offers no stage, and prints the re-audit with the reason for its cause. A stale-revision verdict must not present its saved gaps as text to close, which is step 1's rule in `next_step_gaps`; readers only need to honor `NextStepGaps`.
- **`_authoring_guidance` rule.** Keep the freshness check (`_tail_result_matches_current_artifacts`) as the gate for offering a stage row. In the not-current branch, name the re-audit with the verdict's reason (`_reaudit_command` for the tail verdict) rather than only the fixed fresh-audit row. An `absent` tail verdict keeps today's wording. This is a recommended shape; the exact row text is the implementer's.
- **Do not widen.** Do not change what blocks, the `--json` payload, `--fail-on-findings`, or exit codes. Do not add a second blocking predicate. Do not reword a reader that already takes the verdict unless the enumeration shows a disagreement.
- **Gotcha:** `suggested_next_steps` and `_render_grouped_report` each have their own early return for a fresh-audit-required result. Both must keep naming the same command as `_reaudit_command`, so check the two returns together.
- **Rejected alternative:** a single shared renderer for all four readers. It would pull the report, summary, console, and guidance into one new abstraction for a change whose goal is only one source of facts; the existing helpers already carry that.

## Tests

- `tests/test_completeness_report.py`
  - `test_incomplete_verdict_with_ids_names_gaps_and_offers_no_stage` — an `incomplete` verdict carrying ids lists them under close, counts them, and returns the re-audit command.
  - `test_every_reader_agrees_on_gap_count_for_each_verdict_state` — parametrized over `set`, `incomplete` (each untrusted cause), and `absent`: `next_step_gaps`, `suggested_next_steps`, `suggested_next_step_commands`, `console_summary`, and `build_report_md` give the same count and the same command.
  - `test_stale_revision_verdict_does_not_list_saved_gaps_as_text_to_close` — the stale-revision rule from step 1 holds in the prose and console readers, not only in `next_step_gaps`.
  - `test_no_gaps_message_is_unreachable_for_an_untrusted_verdict` — the "No gaps to close" bullet appears only when the verdict is a completed empty set.
- `tests/cli/test_completeness_cmd.py`
  - `test_grouped_report_close_list_and_command_come_from_verdict_for_budget_limited_audit` — a budget-limited audit with HIGH correctness findings prints them as gaps to close and the re-audit command.
  - `test_json_payload_and_exit_code_unchanged_for_incomplete_verdict` — pins the carve-out: `has_blocking_findings`, `conceptual_bar_blocking_ids` (null when incomplete), and the exit code are the same as before this step.
- `tests/cli/test_authoring_cmds.py`
  - `test_authoring_guidance_not_current_names_verdict_reason_and_count` — a stale or incomplete tail verdict yields a re-audit row carrying the verdict's reason.
  - `test_authoring_guidance_absent_verdict_keeps_fresh_audit_row` — the `absent` default keeps today's wording.
  - `test_authoring_guidance_offers_stage_only_for_current_completed_empty_set` — the stage row is still gated on both freshness and a completed empty set.

### Tests for this step

The cases above are the whole roster. Each must be green before the step is finished. Run `tests/test_completeness_report.py`, `tests/cli/test_completeness_cmd.py`, and `tests/cli/test_authoring_cmds.py` first, then the full suite with `-n auto`. Expect existing cases that pinned a reader's old text for an incomplete or stale verdict to need rewriting; read each one and decide whether it is a carve-out (assert it as one) or a missed site (update it).

## Acceptance criteria

- `handoffs/2026-10-10-completeness-next-step-verdict-finish-reader-enumeration.md` records the two searches (identifier and vocabulary) and a per-site disposition.
- For an `incomplete` verdict that carries ids, the grouped report, the summary bullets, the console block, and `_authoring_guidance` each name the same gap count and the same re-audit command.
- A stale-revision verdict never prints its saved gaps as text to close in any of those four readers.
- "No gaps to close" and any stage command (`run`, `jira`, `detail`) appear only for a current, completed empty-set verdict.
- `--json` `has_blocking_findings`, `conceptual_bar_blocking_ids`, `--fail-on-findings`, and exit codes are unchanged; the cases above pin this.
- `tests/test_duplication.py` stays green: no helper is added that duplicates an existing one.

## Applicable guardrails

- **The plan's "## Out of scope" — blocking bar and external contract.** This step must not touch `is_blocking_finding`, `is_blocking_impact`, or the finalize gate's JSON, flag, and exit-code behavior. Readers change presentation only.
- **The plan's "## Out of scope" — no new advisories, gates, or signals.** Do not add a convergence signal or an audit-shape advisory to explain the new wording.
- **The plan's "## Out of scope" — #479's settled states.** Use the `set` / `incomplete` / `absent` states and the trust-follows-the-gate rule as given; this step does not re-decide them or add a second blocking predicate.
- **The plan's step intent for this step.** No reader may bring back a "no gaps remain" message or recompute the stage on its own; every shared seam is found by identifier and by vocabulary before any edit.

## Deferred

- Giving incomplete audits their own blocking predicate — outside the plan's fence; this effort only makes the cause reachable and the ids complete.
- Wording changes to readers that already agree with the verdict — only disagreements found by the enumeration are in scope.
- Consolidating the report, summary, console, and guidance renderers into one — a cross-module refactor; route to `BACKLOG.md` if the enumeration shows it is worth doing.
- Updating `docs/how-to/pipeline/audit.md` for the new cause wording — owned by the plan's documentation step, not this one.
