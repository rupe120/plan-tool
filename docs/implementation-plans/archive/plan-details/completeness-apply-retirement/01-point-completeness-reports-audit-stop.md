> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Point completeness guidance at hand-editing

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update completeness reports, audit messages, and authoring help to direct readers to edit the plan or detail files themselves. Preserve the conceptual hand-edit guidance already present in `plan_tool/completeness_report.py` and replace its remaining files-coherence remedies that recommend the retiring command. Keep command suggestions separate from prose instructions. Generated help and focused tests must reflect the new guidance without changing audit decisions or repair behavior.

## Table of Contents

- [Summary](#summary) — What changes and what remains stable.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why the remaining remedies need attention.
- [Input](#input) — Existing report and command contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Guidance changes and boundaries.
- [Tests](#tests) — Cases that prove the guidance works.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant decisions and documentation.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Related work outside this step.

## Why

Conceptual findings already receive session-directed edit guidance in several report paths, but `plan_tool/completeness_report.py:diagnostic_remedies()` and `plan_tool/completeness_report.py:suggested_next_step_commands()` still recommend `completeness-apply` for files-coherence drift. Those recommendations become unusable when the command retires. Complete the guidance change across saved reports, terminal output, and help while preserving the distinction between editing findings, authoring missing details, and running a fresh audit.

## Input

- **Report dispositions:** `plan_tool/completeness_report.py:next_step_gaps()`, `plan_tool/completeness_report.py:deferred_kind()`, and `plan_tool/completeness_report.py:BlockingVerdict` determine which guidance applies. Consume their existing results without changing classification.
- **Command suggestions:** `plan_tool/completeness_report.py:suggested_next_step_commands()` returns command/description tuples. Preserve that shape; hand-edit instructions belong in prose.
- **Audit qualification:** `plan_tool/completeness_report.py:suggested_next_steps()` handles fresh-audit requirements before ordinary remedies. Preserve that ordering and its distinction between stale evidence and findings requiring edits.
- **Generated reference:** `plan_tool/cli_reference.py` generates `docs/cli/` from the live parser. Change help at its owning registration site and regenerate the reference.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/completeness_report.py` — replace retired-command remedies and update explanatory text for surviving report behavior.
  - `plan_tool/cli/completeness_phases.py` — align surviving audit stop, grouped-report, and persistence guidance with hand-editing.
  - `plan_tool/cli/completeness_cmd.py` — align completeness-audit help and surviving audit explanations.
  - `plan_tool/cli/authoring.py` — align detail-tail explanations and detail help.
  - `docs/cli/completeness-audit.md` — regenerate the audit reference from parser help.
  - `docs/cli/detail.md` — regenerate the detail reference from parser help.
  - `docs/cli/README.md` — regenerate affected command descriptions.
  - `tests/cli/package_surface_help.golden.txt` — refresh affected help text.
  - `tests/test_completeness_report.py` — update remedy expectations and preserve report contracts.
  - `tests/cli/test_completeness_cmd.py` — cover surviving audit output and policy preservation.
  - `tests/cli/test_authoring_cmds.py` — update detail-tail guidance fixtures and assertions.
  - `tests/test_cli.py` — preserve public CLI behavior and cover help changes.

## Implementation

- **Foundational logic: choose an actionable next step for each finding disposition.** Inspect `plan_tool/completeness_report.py:diagnostic_remedies()`, `plan_tool/completeness_report.py:suggested_next_steps()`, and `plan_tool/completeness_report.py:suggested_next_step_commands()` together. Follow their consumers through `plan_tool/cli/completeness_phases.py:_render_grouped_report()`, `plan_tool/cli/completeness_phases.py:_persist_and_present_report()`, and `plan_tool/cli/authoring.py:cmd_detail()` so terminal and saved guidance agree.

- **Preserve existing conceptual guidance.** Retain the instructions in `plan_tool/completeness_report.py:WHY` and the conceptual report sections that already direct a session-directed edit. Make it clear that either a human or an orchestrating session reads the findings and edits the relevant plan or detail files. Do not replace this with another application command.

- **Replace files-coherence remedies with a reviewable edit.** In `plan_tool/completeness_report.py:diagnostic_remedies()`, tell the reader to inspect the cited path and correct the detail citation or the step’s `files:`/`allowed_mentions:` declaration as appropriate. A real path alone must not imply that it belongs in `files:` or deserves an exemption. Preserve the advice to correct typo citations.

- **Keep manual work out of command tuples.** Remove the files-coherence `completeness-apply` row from `plan_tool/completeness_report.py:suggested_next_step_commands()`. Carry its remedy through prose instead. Preserve surviving detail, split, reconciliation, and re-audit suggestions under their existing conditions; do not invent a shell-shaped manual-edit placeholder.

- **Preserve stage and freshness distinctions.** Bare-plan output must retain its existing treatment of detail-level diagnostics and conceptual findings. Fresh-audit requirements must retain precedence over ordinary saved-finding guidance. Editing guidance must not grant permission to advance a stage that the existing verdict withholds.

- **Sweep surviving audit messages by responsibility.** Review `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop()`, `plan_tool/cli/completeness_phases.py:_render_grouped_report()`, and `plan_tool/cli/completeness_cmd.py:finalize_completeness_run()` for references that assign conceptual edits to the retiring walker. Update explanations without changing continuation, blocking, persistence, or exit behavior. Leave source-specific remedies for surviving deterministic and review/reconcile routes intact.

- **Update help at its source.** Review `plan_tool/cli/completeness_cmd.py:register()` and `plan_tool/cli/authoring.py:register()` alongside `plan_tool/cli/authoring.py:cmd_detail()`. Describe the automatic completeness tail accurately: deterministic repair retains its authority, while conceptual findings require the reader’s edits. Regenerate references with `python -m plan_tool.cli_reference --write`; do not hand-edit generated pages.

- **Keep this a guidance change.** Prefer edits to existing strings and the obsolete command-suggestion branch. Do not extract a shared guidance framework or alter function signatures, saved schemas, parser registration, or application machinery. The retiring commands remain registered until their removal work lands, so their own help entries are not a zero-match target for this step.

## Tests

### Tests for this step

The names below describe cases to add or adapt in the named files. Every affected test must be green before this step finishes.

- `tests/test_completeness_report.py:test_files_coherence_remedy_requires_reviewing_the_citation_and_scope` — real-file and typo findings receive explicit manual remedies without automatic exemption advice.
- `tests/test_completeness_report.py:test_files_coherence_hand_edit_never_becomes_a_command_tuple` — files-coherence findings emit no retired-command row or manual-edit placeholder.
- `tests/test_completeness_report.py:test_conceptual_findings_keep_hand_edit_guidance_for_bare_and_detailed_plans` — both conceptual sources retain guidance appropriate to the existing stage policy.
- `tests/test_completeness_report.py:test_fresh_audit_requirement_precedes_hand_edit_remedies` — stale evidence retains the existing fresh-audit instruction.
- `tests/test_completeness_report.py:test_manual_remedies_preserve_surviving_command_order_and_tuple_shape` — mixed findings retain valid detail, split, and re-audit suggestions in their existing order.
- `tests/test_completeness_report.py:test_saved_report_keeps_findings_and_sidecar_fields_when_guidance_changes` — report wording changes without dropping persisted finding data.
- `tests/cli/test_completeness_cmd.py:test_audit_stop_and_grouped_output_direct_conceptual_edits_to_the_reader` — surviving output routes the reader to the findings and relevant files.
- `tests/cli/test_completeness_cmd.py:test_guidance_changes_preserve_blocking_fields_and_exit_policy` — equivalent audit results retain their blocking metadata and return codes.
- `tests/cli/test_authoring_cmds.py:test_detail_tail_preserves_hand_edit_prose_and_surviving_command_suggestions` — the detail tail presents actionable guidance without supplying a retired command in its fake audit results.
- `tests/test_cli.py:test_audit_and_detail_help_describe_reader_owned_conceptual_edits` — public help distinguishes conceptual edits from retained deterministic repair.

Update existing expectations such as `tests/test_completeness_report.py:test_next_step_commands_are_command_description_tuples()`, `tests/test_completeness_report.py:test_next_step_commands_order_urgent_first()`, and `tests/test_completeness_report.py:test_next_step_commands_detailed_plan_keeps_detail_level_actions()` rather than retaining their obsolete files-coherence command assertions. Keep `tests/test_completeness_report.py:test_next_step_commands_parse_against_live_parser()` as the executable-command check.

Run the affected suites, the generated-reference checks in `tests/cli/test_cli_reference.py`, the help checks in `tests/cli/test_package_surface.py`, and the full regression suite. Verify the new assertions by temporarily restoring an obsolete remedy and confirming the relevant test fails.

## Acceptance criteria

- Newly rendered completeness report prose directs conceptual findings to reader-owned edits and retains existing stage-specific distinctions.
- Files-coherence remedies explain how to review declarations and citations without recommending `completeness-apply`.
- `plan_tool/completeness_report.py:suggested_next_step_commands()` emits no retiring command for any covered disposition combination and retains its command/description tuple contract.
- Saved report guidance, grouped terminal output, and the detail tail agree on who performs conceptual edits.
- Audit blocking fields, qualification handling, continuation decisions, exit codes, and saved finding data remain unchanged.
- Generated references and the help golden file match the live parser.
- A residual search over the declared production files classifies remaining retired-command mentions as removal-owned machinery or documentation for still-registered commands; no surviving audit remedy recommends them.
- Focused tests, generated-reference checks, help checks, and the full regression suite pass.

## References

- [BACKLOG.md — retirement decision](BACKLOG.md) — Read item #376 for the command-retirement boundary and item #369 for the separate treatment of other application callers.
- [DETAIL_FORMAT.md — detail contract](DETAIL_FORMAT.md) — Read for the maintained structure and ownership of implementation details.
- [docs/how-to/pipeline/audit.md — audit procedure](docs/how-to/pipeline/audit.md) — Preserve the qualified-result and stage-aware operator contract.

## Applicable guardrails

- **The plan’s “Step intent,” guidance ownership:** Limit changes to guidance emitted by the declared report, audit, and help surfaces.
- **The plan’s “Scope guardrails,” retained behavior:** Keep the existing repair and review/reconcile routes unchanged, including their source-specific instructions.
- **The plan’s “Scope guardrails,” legacy readers:** Preserve report and sidecar readability; change newly produced guidance without rewriting stored artifacts.
- **The plan’s “Out of scope,” other application authorities:** Do not redirect or remove shared application callers merely because searches find related vocabulary.
- **The plan’s “Scope guardrails,” no replacement route:** Do not turn the removed suggestion into a private conceptual application path or a new workflow abstraction.

## Deferred

- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` and its registration — command removal belongs to the plan’s removal work, rather than this guidance step.
- `plan_tool/cli/completeness_phases.py:_run_apply_walk()` and its exclusive helpers — remove with their owning application route; do not restructure them here.
- `plan_tool/cli/direct_cmd.py` — retire the direct pipelines through their dedicated removal work.
- `plan_tool/cli/app.py` command catalog and command-removal wiring — coordinate with parser removal; this step updates only the declared help sources and resulting artifacts.
- Historical report text and legacy annotations — retain their readable contents under the plan’s compatibility boundary.
- Other `apply_finding` callers — leave their authority unchanged under BACKLOG #369.
