# Step 3 — Retire completeness-apply and its exclusive machinery

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Remove `completeness-apply` from registration, dispatch, help, and package exports. Delete its serial application walk and parallel worker/replay module, including its files-coherence writer and commit path. Preserve shared finding application, audit repair, review/reconcile behavior, and saved-artifact readers. On green, the command is rejected by argparse and existing audit evidence remains readable.

## Table of Contents

- [Summary](#summary) — Result and main boundaries.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Why the dedicated application paths retire.
- [Input](#input) — Existing contracts and upstream outcomes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Removal targets and preservation checks.
- [Implementation](#implementation) — Removal approach and shared-code boundaries.
- [Tests](#tests) — Command removal and compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Scope decisions and contract owners.
- [Applicable guardrails](#applicable-guardrails) — Limits on this removal.
- [Deferred](#deferred) — Work outside this step.

## Why

`plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` still exposes a dedicated saved-finding application command, and `plan_tool/cli/completeness_apply_parallel.py:run_parallel_apply()` supplies its unattended lane. Their existence is the removal target, not evidence that retirement is partly complete. Removing only registration leaves application, replay, and workspace machinery behind; deleting shared application or persistence code instead would change routes the plan explicitly preserves.

## Input

- **Step 1:** Supplies actionable completeness guidance that does not depend on the retiring command. Preserve that outcome in surviving audit output.
- **Step 2:** Removes the direct pipelines. Base the caller sweep on the resulting tree rather than retaining helpers for those deleted callers.
- **Saved reviews:** `plan_tool/review_persistence.py:SavedReview`, `Annotation`, and `load_review()` define existing sidecar interpretation. Command removal must not change their formats or accepted values.
- **Shared walks:** `plan_tool/review_walk.py:should_apply_as_finding()` and `plan_tool/cli/review_actions.py:_build_review_action_fn()` serve surviving review routes. Their current behavior remains the contract.
- **Generated references:** `plan_tool/cli_reference.py:write_reference()` regenerates parser-derived documentation but does not remove obsolete pages.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py` — remove the handler, its registration, and exclusive imports.
  - `plan_tool/cli/completeness_phases.py` — remove exclusive saved-audit application helpers, source-order constants, files-coherence writing, serial walking, parallel dispatch, and application commits.
  - `plan_tool/cli/completeness_apply_parallel.py` — delete the module.
  - `plan_tool/cli/app.py` — remove the handler re-export and mutation-lock entry.
  - `plan_tool/cli/parser.py` — remove the canonical command-order entry.
  - `plan_tool/cli/__init__.py` — remove the command catalog entry and public export.
  - `plan_tool/cli/gitcommit.py` — remove the retired caller from explanatory text; preserve shared primitives.
  - `plan_tool/cli/review_cmd.py` — remove comparisons with the retired command from surviving explanations.
  - `plan_tool/cli/review_actions.py` — update retiring-command explanations without changing surviving dispatch.
  - `plan_tool/review_walk.py` — update explanations while retaining shared source classification and walk behavior.
  - `plan_tool/review.py` — remove live command references without changing finding identity or checks.
  - `plan_tool/convergence.py` — update application guidance without changing blocking predicates.
  - `plan_tool/convergence_diagnosis.py` — describe annotation-based history without requiring the retired writer.
  - `plan_tool/backend_runner.py` and `plan_tool/claude_errors.py` — remove the retired parallel caller from comments; retain shared concurrency support.
  - `CAPABILITIES.md` — remove the retired surface from “Plan completeness & convergence.”
  - `DATA_CONTRACT.md` — remove current writer claims while preserving persisted-field contracts.
  - `TESTING.md` — remove retired invoker-seam and parallel-lane instructions.
  - `tests/cli/COVERAGE_BASELINE.md` — remove the retired handler’s coverage obligation and correct affected inventory claims.
  - `docs/cli/completeness-apply.md` — delete the generated page.
  - `docs/cli/README.md` — regenerate the command index.
  - `tests/cli/package_surface_help.golden.txt` — refresh public help.
  - `tests/cli/test_completeness_apply_parallel.py` — delete exclusive worker/replay tests.
  - `tests/cli/test_completeness_cmd.py` and `tests/test_cli.py` — remove command-only tests and retain surviving audit coverage.
  - `tests/cli/test_cli_parser.py` — add command rejection and surviving-registration checks.
  - `tests/test_data_contract.py` — align documentation assertions without weakening schema checks.
  - `tests/test_review_persistence.py` and `tests/test_convergence_diagnosis.py` — pin compatibility with saved application annotations and audit history.

## Implementation

- **Foundational logic: remove dedicated completeness application authority.** Delete the command and its exclusive execution paths. Do not replace them with an alias, private runner, or alternate dispatch entry.

- **Remove both entry points and exports.** Delete `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` and its parser block in `register()`. Remove its entries from `plan_tool/cli/app.py:_LOCKED_MUTATING_COMMANDS`, `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`, and the exports in `plan_tool/cli/__init__.py`.

- **Delete exclusive phase helpers by caller ownership.** Start with `plan_tool/cli/completeness_phases.py:_resolve_saved_completeness_audit()`, `_resolve_apply_walk_targets()`, `_run_apply_walk()`, `_apply_walk_recs_parallel()`, `_apply_files_coherence()`, and `_completeness_apply_commit_subject()`. Include their exclusive result types, ordering constants, payload redirects, and freshness helpers after checking remaining references. Do not delete a contiguous section merely because most of it serves the command.

- **Retire the files-coherence writer outright.** Remove automatic `allowed_mentions` promotion through `plan_tool/cli/completeness_phases.py:_apply_files_coherence()`. Preserve `plan_tool/review.py:check_files_coherence()` and its report behavior. Do not move the writer into audit iteration or another command.

- **Delete the complete parallel lane.** Remove `plan_tool/cli/completeness_apply_parallel.py`, including `apply_finding_in_tree()`, `replay_results()`, `dispatch_parallel()`, and `WorktreePool`. Its overwrite/restore logic, temporary branch creation, workspace cleanup, and durable replay ownership retire together. Do not add cleanup or migration of artifacts left by earlier runs.

- **Reuse shared owners unchanged.** Preserve `plan_tool/launcher.py:apply_finding()` and its surviving callers. Keep `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop()` and its deterministic repair behavior. Shared helpers such as `_resolution_for_verdict()` must remain when surviving callers use them.

- **Preserve generic review semantics.** `plan_tool/review_walk.py:_APPLY_AS_FINDING_SOURCES` includes `plan-completeness`; removal of the dedicated command does not authorize changing that set. Keep `extra_apply_sources`, structural handling, and `WalkResponsePolicy` where surviving callers use them. `plan_tool/cli/data_contract_cmd.py` owns a separate application route and remains unchanged.

- **Preserve shared infrastructure.** Keep git provisioning and commit primitives in `plan_tool/cli/gitcommit.py`. Keep backend observer and rate-limit synchronization in `plan_tool/backend_runner.py` and `plan_tool/claude_errors.py`; surviving parallel detail authoring still needs shared support.

- **Keep historical evidence readable.** Remove current replay-writer claims from `DATA_CONTRACT.md` without deleting annotation statuses, verdict values, sidecar fields, or run-log interpretation. `plan_tool/convergence_diagnosis.py:load_report_history()` must continue using saved annotations as evidence without requiring an available application command.

- **Sweep identifiers and vocabulary.** Check declared files for the command name, deleted helper names, parallel replay, files-coherence promotion, and application commit descriptions. Classify remaining references as compatibility coverage or live stale guidance. Avoid a blanket zero-match rule that would forbid tests containing the rejected command name.

- **Refresh generated surfaces from the parser.** Regenerate the CLI reference and refresh the help snapshot through their existing mechanisms. Explicitly delete `docs/cli/completeness-apply.md`, since generation does not remove obsolete pages.

## Tests

### Tests for this step

The names below describe proposed cases. Update existing equivalent cases rather than adding duplicates. Every added or changed case must be green before this step finishes.

- `tests/cli/test_cli_parser.py:test_completeness_apply_is_rejected_before_dispatch` — the retired command raises argparse’s unknown-command error without invoking a handler.
- `tests/cli/test_cli_parser.py:test_completeness_retirement_preserves_surviving_commands` — audit, data-contract application, and review/reconcile commands remain registered.
- `tests/cli/test_completeness_cmd.py:test_retired_apply_handler_and_walk_helpers_are_absent` — the handler and exclusive helpers are absent without removing surviving audit helpers.
- `tests/cli/test_completeness_cmd.py:test_files_coherence_findings_do_not_promote_allowed_mentions` — a surviving audit reports the drift without performing the retired frontmatter write.
- `tests/cli/test_completeness_cmd.py:test_deterministic_audit_repairs_survive_apply_retirement` — audit iteration retains its existing deterministic application path.
- `tests/test_review_persistence.py:test_saved_apply_annotations_remain_readable_without_apply_command` — raw saved sidecars retain their annotation statuses and recommendation fields through loading.
- `tests/test_convergence_diagnosis.py:test_saved_apply_annotations_keep_their_history_meaning` — existing annotations retain their resolved/open interpretation in diagnosis.
- `tests/test_cli.py:test_generic_review_application_behavior_survives_completeness_retirement` — surviving review actions retain their existing dispatch and confirmation behavior.
- `tests/test_data_contract.py` existing contract guards — documentation changes preserve the persisted schema and accepted legacy values.

Run the affected suites, generated-reference and package-surface checks, then `uv run pytest tests/ -q -n auto`. Keep real backend calls stubbed. Verify the new removal and compatibility assertions by temporarily restoring the relevant retired entry or breaking the reader behavior and observing the focused test fail.

## Acceptance criteria

- `completeness-apply` is absent from parser registration, dispatch, canonical ordering, package exports, help, and capability surfaces.
- The parallel module, its exclusive test module, and its generated command page are absent.
- Exclusive serial walking, files-coherence promotion, application commit, replay, and pool cleanup code are absent.
- Shared finding application, deterministic audit repair, generic review dispatch, and infrastructure retain their behavior.
- Existing saved annotations, sidecars, and run logs remain readable without conversion.
- Generated references and help match the surviving parser.
- Focused checks and the full test suite pass.

## References

- [BACKLOG.md — #376](../../../BACKLOG.md) — Read the dedicated-command retirement decision.
- [BACKLOG.md — #369](../../../BACKLOG.md) — Keep other finding-application authorities outside this removal.
- [DATA_CONTRACT.md](../../../DATA_CONTRACT.md) — Preserve saved-review and apply-verdict contracts.
- [TESTING.md](../../../TESTING.md) — Follow surviving invoker seams and hermetic test requirements.

## Applicable guardrails

- **Plan intent, command retirement:** Delete application machinery only where the retiring command owns it; do not create another route to perform the same job.
- **Plan “Scope guardrails,” preserved behavior:** Keep surviving audit, review, and reconcile decisions unchanged while removing their stale command references.
- **Plan “Out of scope,” legacy artifacts:** Treat existing saved content as reader input. Do not rewrite it to remove command vocabulary.
- **Step intent, bounded removal:** Keep shared helpers when surviving consumers require them; do not turn this deletion into a shared-code redesign.

## Deferred

- Other finding-application authorities — BACKLOG #369 owns their separate assessment.
- Broader narrative guidance and instruction-file updates — leave them to the plan’s documentation work.
- Shared-helper consolidation or infrastructure simplification — neither is required to remove this command.
