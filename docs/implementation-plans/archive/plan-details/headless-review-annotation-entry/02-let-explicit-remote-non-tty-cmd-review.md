> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Let explicit remote non-TTY cmd_review walk only ordinary fresh or eligible saved reviews with a promptable finding while keeping excluded findings visible

## Summary

Extend `plan_tool/cli/review_cmd.py:cmd_review` so explicit remote mode can start the restricted step-1 walk from non-TTY stdin. Keep the normal TTY walk unchanged, and keep ordinary non-TTY runs unchanged unless `PLAN_TOOL_HUMAN_IO=remote` is set. Use the existing saved-review eligibility and normal walk-selection rules to decide whether any finding can prompt. On green, the remote operator can skip a promptable finding, while all excluded findings remain visible and no action path becomes reachable.

## Table of Contents

- [Summary](#summary) — Gives the reviewer the change and its result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Explains the missing headless entry behavior.
- [Input](#input) — Names the saved-review, provider, and step-1 contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the scoped code and test edits.
- [Implementation](#implementation) — Defines the remote entry gate, report behavior, and safety limits.
- [Tests](#tests) — Covers fresh, reused, excluded, and unchanged-mode behavior.
- [Acceptance criteria](#acceptance-criteria) — Lists observable completion checks.
- [References](#references) — Links to the relevant standard-library and pytest documentation.
- [Applicable guardrails](#applicable-guardrails) — Records the plan boundaries that bind this step.
- [Deferred](#deferred) — Names nearby work that remains outside this step.

## Why

`plan_tool/cli/review_cmd.py:_cmd_review_body` currently treats every non-TTY run as report-only, even when `plan_tool.human_io` has an explicitly configured remote provider. The existing `cmd_review` implementation is the correct entry point, but it needs a narrow remote exception that can reach step 1’s closed response policy without opening plan-edit or terminal-only action paths.

## Input

- **Step 1 response policy:** Step 1 supplies the opt-in restricted policy for `plan_tool/review_walk.py:walk_recommendations`. This step selects that policy only for the explicit remote non-TTY `cmd_review` entry.

- **Saved-review contract:** `plan_tool.review_persistence:SavedReview` provides `recommendations`, `annotations`, `report_md`, and the ordinary-final review metadata already checked by `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review`.

- **Promptable selection:** Match the normal non-rewalk selection in `plan_tool/review_walk.py:walk_recommendations`: unannotated findings and findings annotated `failed` can prompt; `applied`, `skip`, and `open` findings remain report-only. Preserve the existing `skip_info` behavior, including its pairwise merge exception, through the supplied `--include-info` setting.

- **Provider contract:** Let `plan_tool/review_walk.py:walk_recommendations` continue to select the configured `plan_tool.human_io:HumanInputProvider`. This step must not create another remote transport or change request-record behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py` — add the explicit remote non-TTY entry decision, keep the fresh report complete, select step 1’s restricted walk policy, preserve reuse eligibility, and update the relevant `register` help text.
  - `docs/cli/reconcile-plan.md` — regenerate the command reference from the changed `--no-walk` and `--reuse` help with `python -m plan_tool.cli_reference --write`.
  - `tests/test_review.py` — cover the environment and report-presentation decisions that `cmd_review` passes into review generation.
  - `tests/test_review_walk.py` — add command-level remote-provider coverage using saved-review fixtures and request records.

## Implementation

- **Foundational logic:** Define the remote headless entry predicate in `plan_tool/cli/review_cmd.py` as: walk opt-outs are absent, stdin is not a TTY, and `PLAN_TOOL_HUMAN_IO` explicitly selects `remote`. A non-TTY stream alone must not enable the walk, and `--yes` must not widen this entry.

- **Keep the report decision separate from walk availability.** `plan_tool/review.py:assemble_report` treats `walk_will_run=True` as permission to hide finding detail because a full terminal walk will repeat it. The restricted remote walk covers only promptable findings, so `plan_tool/cli/review_cmd.py:_cmd_review_body` must retain the complete report for this mode even when it later starts a restricted walk.

- **Update both `cmd_review` paths.** Apply the same remote entry rules after `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` returns an eligible saved review and after a normal `review_plan_full` result is saved. Do not route `cmd_review_walk` through this behavior.

- **Reuse existing saved-review eligibility.** Keep `_review_reuse_ineligibility`, freshness checks, `--reuse-id` pinning, and the fallback-to-fresh behavior intact. A reused review enters the restricted walk only when it is already eligible and fresh; an ineligible or stale save still takes the existing fresh-review path.

- **Preflight promptability before entering the walk.** Do not create a remote request record merely to discover that every finding is hidden by the current `--include-info` setting or terminally annotated. Use the same normal-selection rules that `walk_recommendations` uses, including `failed` annotations, before calling the walk.

- **Keep excluded findings visible.** Render the fresh result before walking with its full finding detail and suggested actions. For a reused result, show the saved findings before the restricted walk without filtering out INFO findings or terminal annotations; do not rely on the restricted walk to present those records.

- **Use step 1’s policy and omit action wiring.** For the selected remote non-TTY path, call `plan_tool/review_walk.py:walk_recommendations` with the restricted response policy from step 1 and without an `action_fn`. Do not build the review-action callback or create a mutation-capable `WalkState` for this path.

- **Keep full walks full.** Remote mode with a TTY must retain the existing provider-backed menu and action wiring. A TTY with remote mode unset must retain the terminal walk, and remote mode unset with non-TTY stdin must retain the existing report-only behavior.

- **Leave refresh outside the entry.** Preserve `plan_tool/cli/review_cmd.py:cmd_review`’s early `--refresh` return and `plan_tool/cli/review_cmd.py:_render_refresh` output. The remote provider must not be selected on that route.

- **Update command help at `plan_tool/cli/review_cmd.py:register`.** Make `--no-walk` distinguish the explicit remote non-TTY exception from ordinary non-TTY skipping, and make `--reuse` describe that exception and its restricted skip-or-quit response set. Leave user-facing format documentation to step 3.

- **Do not merge similar annotation filters.** `plan_tool/cli/completeness_phases.py` has a related unannotated-or-failed selection for completeness application, but it owns a different mutating workflow. Keep that module unchanged.

## Tests

### Tests for this step

- `test_review_walk_environment_allows_explicit_remote_non_tty_only` — assert explicit remote non-TTY input is eligible while ordinary non-TTY input remains ineligible; assert `--no-walk`, `--no-save`, and `--dry-run` override both modes.

- `test_cmd_review_remote_non_tty_fresh_promptable_result_keeps_full_report_and_walks` — assert a fresh ordinary review publishes one remote annotation request, retains finding body and suggested-action output, and can persist a restricted skip.

- `test_cmd_review_remote_non_tty_fresh_mixed_result_keeps_hidden_findings_visible` — assert a promptable fresh finding opens one restricted remote prompt while a default-hidden INFO finding still appears with its detail and suggested action in the same report.

- `test_cmd_review_remote_non_tty_default_info_only_result_does_not_request_input` — assert INFO-only findings remain visible but open no remote request without `--include-info`.

- `test_cmd_review_remote_non_tty_default_pairwise_merge_info_remains_promptable` — assert the existing default-visible INFO `granularity-merge` exception opens one restricted remote prompt rather than being filtered as ordinary INFO.

- `test_cmd_review_remote_non_tty_include_info_makes_info_finding_promptable` — assert `--include-info` changes only selection and permits one restricted remote prompt.

- `test_cmd_review_remote_non_tty_reused_failed_finding_reprompts` — assert an eligible fresh saved review with a `failed` annotation opens the restricted remote prompt.

- `test_cmd_review_remote_non_tty_reused_terminal_annotations_remain_report_only` — parameterize `applied`, `skip`, and `open`; assert each finding remains visible and opens no request.

- `test_cmd_review_remote_non_tty_reused_mixed_findings_keeps_excluded_findings_visible` — assert one promptable finding can walk while hidden or terminally annotated findings remain in the reused report surface.

- `test_cmd_review_remote_non_tty_does_not_build_or_dispatch_review_actions` — assert the selected path does not build the review action callback or invoke terminal input.

- `test_cmd_review_remote_tty_and_terminal_tty_keep_full_walk_contracts` — retain controls proving remote TTY and terminal TTY use the unrestricted walk behavior.

- `test_cmd_review_refresh_bypasses_remote_walk` — assert explicit remote non-TTY configuration does not alter the `--refresh` route or create a provider request.

- `test_walk_and_reuse_help_describe_remote_non_tty_restricted_walk` — assert `--no-walk` distinguishes ordinary non-TTY skipping from the explicit remote exception, and `--reuse` states the restricted response set.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Explicit `PLAN_TOOL_HUMAN_IO=remote` plus non-TTY stdin can start one restricted `cmd_review` walk only when a fresh ordinary result or eligible saved review has a promptable finding.

- Unset remote mode with non-TTY stdin remains report-only.

- `--no-walk`, `--no-save`, and `--dry-run` suppress the selected remote walk.

- A fresh remote non-TTY result retains full finding detail and suggested actions before any restricted walk starts.

- A fresh mixed result keeps each default-hidden finding’s detail and suggested action visible while a promptable sibling enters the restricted walk.

- A reused remote non-TTY result keeps every excluded finding visible, including INFO findings hidden by default and findings with terminal annotations.

- The selected remote path passes step 1’s restricted policy and does not build or call an action callback.

- `failed` annotations remain promptable; `applied`, `skip`, and `open` annotations remain report-only.

- The default-visible INFO pairwise-merge exception remains promptable without `--include-info`; other INFO findings require that flag.

- Remote TTY, terminal TTY, `cmd_review_walk`, and `--refresh` retain their existing behavior.

- `--no-walk` and `--reuse` help describe the explicit remote non-TTY exception without claiming every non-TTY context skips the walk.

- `docs/cli/reconcile-plan.md` is regenerated from the changed command help and passes the existing CLI-reference drift guard.

- `tests/test_review.py` and `tests/test_review_walk.py` pass with the focused cases above.

## References

- [sys — System-specific parameters and functionshttps: — Read for the stdin surface used by the entry gate.
- [io — Core tools for working with streamshttps: — Read for the TTY distinction the gate preserves.
- [os — Miscellaneous operating system interfaceshttps: — Read for explicit remote-mode configuration.
- [How to monkeypatch/mock modules and environmentshttps: — Use for isolated environment and TTY tests.
- [pytest API Reference — tmp_pathhttps: — Use for remote request, resolution, and saved-review fixtures.

## Applicable guardrails

- **Explicit-mode gate:** The plan’s `## Architecture`, fixed gate table limits this step to explicit remote non-TTY input; it must preserve terminal, remote-TTY, and ordinary non-TTY behavior.

- **No action routes:** The plan’s `## Out of scope`, review-action boundary requires the selected path to leave the review-action module unchanged and unreachable.

- **No feedback handoff:** The plan’s `## Out of scope`, remote-feedback boundary requires the selected path to emit no feedback request or durable feedback state.

- **Refresh direction:** The plan’s `## Out of scope`, refresh boundary keeps `--refresh` outside this walk entry.

- **Provider ownership:** The plan’s `## Input`, human-input provider boundary keeps `plan_tool/human_io.py`, transport, cancellation, and record lifecycle unchanged.

- **Caller-specific scope:** The plan’s `## Out of scope`, peer-walk boundary prevents this step from migrating `cmd_review_walk` or other interactive command routes.

## Deferred

- `HUMAN_IO_FORMAT.md` — step 3 owns the durable user documentation for the restricted remote prompt and saved-skip behavior.

- Remote feedback, cancellation, transport defaults, and request-record retention — remain with the plan’s deferred lifecycle work under #322.

- `plan_tool/cli/completeness_phases.py` promptability parallel — stays separate because its annotation walk applies authoritative-document findings under a different contract.
