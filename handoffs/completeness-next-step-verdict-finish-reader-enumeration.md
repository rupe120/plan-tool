# Reader enumeration — completeness next-step verdict finish, step 4

**Defect class.** A reader derives a gap list, count, or next command from something other than the verdict.

## Searches

- By identifier: `blocking_ids`, `conceptual_bar_blocking_ids`, `blocking_count`, `next_step_gaps`, `_verdict_offers_stage`, `_blocking_deterministic_steps`, `_reaudit_command`, `reaudit_step`, `next_stage_command`, `_fresh_audit_required`, `ABSENT_BLOCKING_VERDICT` over `plan_tool/`.
- By vocabulary: "No gaps", "gaps remain", "blocking … gap(s)", "verdict incomplete", "advisory", "re-audit", "fresh audit" in `plan_tool/completeness_report.py`, `plan_tool/cli/`.

## Dispositions

| Site | Disposition |
| --- | --- |
| `completeness_report.next_step_gaps` / `NextStepGaps` | already on the verdict |
| `completeness_report._reaudit_command`, `next_stage_command`, `reaudit_step` | already on the verdict (single command source) |
| `completeness_report.suggested_next_steps`, `suggested_next_step_commands` | already on the verdict; both fresh-audit returns name `_reaudit_command` |
| `completeness_report.console_summary` blocking line | moved onto the verdict: a counted incomplete verdict names its `untrusted_cause` |
| `completeness_phases._render_grouped_report` | already on the verdict (`next_step_gaps`, `next_stage_command`, `reaudit_step`) |
| `authoring._authoring_guidance` not-current branch | moved onto the verdict: count and re-audit reason come from the tail verdict; a `set` verdict that is not current reads as stale-revision; `absent` keeps the fixed row |
| `authoring._authoring_guidance` stage row | already gated on freshness and a completed empty set |
| `completeness_cmd` call sites | already pass the verdict; no edit |
| `_render_completeness_json`, `_completeness_has_blocking_findings`, qualified-result classifier | stay on the gate: external `--json` / `--fail-on-findings` / exit-code contract |
