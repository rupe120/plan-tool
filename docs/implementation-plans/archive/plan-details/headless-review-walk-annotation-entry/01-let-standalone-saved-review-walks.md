> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Let standalone saved-review walks accept remote skip or quit, limit authoritative review-state writes to the existing skip sidecar rewrite, and preserve full terminal actions

## Summary

This step adds a restricted remote path to `plan_tool/cli/review_cmd.py:cmd_review_walk` and covers it in `tests/test_review_walk.py`. When stdin is not a TTY and `PLAN_TOOL_HUMAN_IO` is exactly `remote`, a standalone saved-review walk accepts only skip or quit. A skip updates the existing saved-review sidecar; quit, normal headless use, and TTY walks keep their current observable behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the change and green result.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The missing standalone remote annotation path.
- [Input](#input) — Saved-review and input-mode contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step edits.
- [Implementation](#implementation) — Restricted remote routing and terminal invariants.
- [Tests](#tests) — Focused command and sidecar coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary documentation for the touched interfaces.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this step.

## Why

`plan_tool/cli/review_cmd.py:cmd_review_walk` currently reports findings and exits whenever stdin is not a TTY, even though `plan_tool/review_walk.py:walk_recommendations` already supports a skip-or-quit response policy through the configured human-input provider. This leaves a saved review created by an earlier command without the narrow remote annotation path that inline review walks provide. The standalone command needs that path without turning a remote annotation into permission to apply findings, collect feedback, or mutate the plan.

## Input

- **Saved-review eligibility remains intact.** `plan_tool/cli/review_cmd.py:cmd_review_walk` must keep its existing candidate selection and `_direct_walk_ineligibility` checks before any remote prompt; only an eligible final saved review reaches the new path.
- **Annotations remain the persisted review state.** `plan_tool/review_persistence.py:SavedReview.annotations` and `plan_tool/review_persistence.py:update_annotation` define the existing sidecar rewrite used after a completed response.
- **The walk owns response handling.** `plan_tool/review_walk.py:walk_recommendations` already accepts `WalkResponsePolicy.SKIP_OR_QUIT`; this step selects that policy for one command mode rather than changing the saved-review schema or the walk engine.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py` — Route `cmd_review_walk` through the restricted remote policy only for exact remote, non-TTY input while keeping its current report-only and full terminal routes.
  - `tests/test_review_walk.py` — Extend standalone walk command coverage for remote skip, quit, rejected full-menu responses, non-remote headless input, aliases, and terminal behavior.

## Implementation

- **Foundational logic: standalone walk input-mode gate.** In `plan_tool/cli/review_cmd.py:cmd_review_walk`, distinguish three modes after the saved review has passed existing selection and eligibility checks:
  - A TTY keeps the current full `walk_recommendations` route and its action setup.
  - Non-TTY input with `PLAN_TOOL_HUMAN_IO` exactly equal to `remote` enters a restricted walk.
  - Every other non-TTY case keeps the current warning and report-only result.

- **Keep the remote condition narrow.** Require both non-TTY stdin and the exact environment value. Do not treat a set-but-different value as remote mode, and do not let remote configuration restrict an actual terminal session.

- **Use the existing restricted policy.** Pass `WalkResponsePolicy.SKIP_OR_QUIT` to `plan_tool/review_walk.py:walk_recommendations` on the remote standalone route. Preserve `rewalk` and `--include-info` selection behavior so the command asks only about findings that the normal walk would present.

- **Do not build an action path for remote input.** The restricted branch must not call `plan_tool/cli/review_actions.py:_build_review_action_fn` or dispatch an action. A remote skip must reach the existing `update_annotation` persistence path through `walk_recommendations`; quit and every response outside skip must leave the sidecar annotations unchanged.

- **Keep authoritative writes limited.** `cmd_review_walk` must not add its own saved-review rewrite, plan write, code action, or feedback path. The existing sidecar rewrite for a completed skip remains the sole authoritative review-state update in this mode.

- **Preserve terminal actions.** Keep the existing TTY branch’s `WalkState`, `_build_review_action_fn`, and default `WalkResponsePolicy.FULL` behavior. Terminal users retain apply, feedback, run, apply-all, skip, help, and quit rather than inheriting the remote menu.

- **Keep command names equivalent.** `plan_tool/cli/review_cmd.py:register_review_commands` maps `reconcile-plan-walk`, `reconcile-walk`, and `review-walk` to `cmd_review_walk`; all three names must reach the same restricted remote behavior.

- **Prefer a command-local decision over widening another caller.** `plan_tool/cli/review_cmd.py:_remote_non_tty_review_walk_allowed` serves the inline `cmd_review` flow, which is outside this step. Reuse its exact condition only if doing so leaves `cmd_review` outcomes unchanged; otherwise keep the standalone decision inside `cmd_review_walk`.

## Tests

### Tests for this step

- `test_cmd_review_walk_remote_non_tty_skip_persists_only_skip_annotation` — Parametrize the three walk command names and skip spellings; assert an eligible saved finding becomes `Annotation(status="skip", note="")` in its existing sidecar and no action builder runs.
- `test_cmd_review_walk_remote_non_tty_skip_continues_to_later_promptable_finding` — Give the selected review two promptable findings and remote skip responses; assert each response creates only its finding’s skip annotation and the second request is issued after the first skip.
- `test_cmd_review_walk_remote_non_tty_quit_leaves_sidecar_unmodified` — Parametrize quit spellings; assert the command exits successfully without an annotation or action dispatch.
- `test_cmd_review_walk_remote_non_tty_rejects_full_menu_response_without_dispatch` — Send an apply, feedback, run, or apply-all response through remote input; assert it ends the restricted walk without feedback input, action dispatch, or sidecar annotation.
- `test_cmd_review_walk_non_tty_without_exact_remote_mode_remains_report_only` — Cover an unset and a non-`remote` environment value; assert the existing warning and finding summary remain, with no remote request or sidecar mutation.
- `test_cmd_review_walk_remote_non_tty_preserves_rewalk_and_info_selection` — Use an already annotated finding and an informational finding to show that `--rewalk` and `--include-info` reach the restricted walk’s normal selection rules without widening its response menu.
- `test_cmd_review_walk_tty_keeps_full_policy_and_action_setup` — Run with TTY stdin, including when the environment says `remote`; assert the walk receives `WalkResponsePolicy.FULL` and an action function.
- `test_cmd_review_walk_aliases_share_remote_restricted_route` — Assert each registered alias reaches the same skip-or-quit policy rather than a separate handler behavior.

Every listed case must be green, along with `uv run pytest tests/test_review_walk.py -q`, before this step is complete.

## Acceptance criteria

- With an eligible saved review, non-TTY stdin, and `PLAN_TOOL_HUMAN_IO=remote`, each standalone walk command name sends the remote operator a skip-or-quit annotation prompt.
- A remote `s` or `skip` creates only the existing skip annotation in the selected saved-review sidecar.
- A remote skip continues to each later finding selected by the normal `--rewalk` and `--include-info` rules.
- A remote `q`, `quit`, or non-skip response creates no annotation and dispatches no action or feedback request.
- `cmd_review_walk` does not call `_build_review_action_fn` on the restricted remote route.
- Non-TTY input without the exact remote mode keeps the current report-only warning and finding summary.
- TTY walks retain the full response menu and their existing action setup.
- `tests/test_review_walk.py` passes with the new coverage.

## References

- [io — Core tools for working with streamshttps: — Use `isatty()` semantics to keep terminal and piped-input behavior separate.
- [os — Miscellaneous operating system interfaceshttps: — Use process-environment access for the exact `PLAN_TOOL_HUMAN_IO` gate.
- [argparse — Parser for command-line options, arguments and subcommandshttps: — Preserve alias dispatch to the same standalone walk handler.
- [How to monkeypatch/mock modules and environmentshttps: — Replace TTY detection, environment values, providers, and forbidden callbacks in focused tests.
- [How to capture stdout/stderr outputhttps: — Assert report-only warnings and remote-walk output.
- [How to parametrize fixtures and test functionshttps: — Cover aliases and restricted response spellings without duplicating test setup.

## Applicable guardrails

- **The plan’s “## Plan intent” applies.** Restrict the new behavior to an explicitly configured remote, non-TTY standalone saved-review walk; all other input modes keep their existing behavior.
- **The plan’s “## Step intent” applies.** Limit this step to safe remote annotation of eligible final saved findings.
- **The plan’s “## Out of scope” applies.** Do not change inline review paths, other `walk_recommendations` callers, remote feedback, action execution, transport behavior, or response-file lifecycle ownership.
