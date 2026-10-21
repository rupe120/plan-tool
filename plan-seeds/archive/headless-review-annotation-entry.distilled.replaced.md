> **Replaced**: this file has been superseded by `docs/implementation-plans/2-headless-review-annotation-entry.md`.
> Preserved here for history; do not edit.

## Overview

When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not a TTY, `plan_tool.cli.review_cmd.cmd_review` will start one saved-review walk for `review`, `reconcile`, and `reconcile-plan`. The walk accepts only remote annotation, feedback, skip, and quit responses; blank input dispatches nothing, and apply, run, and apply-all fail closed without mutating a plan. With remote mode unset, existing terminal behavior and ordinary non-TTY skipping remain unchanged, while `--no-walk`, `--no-save`, and `--dry-run` continue to suppress the walk.

## Problem statement

The completed `human-input-seam` plan establishes filesystem request and resolution records only after `walk_recommendations` starts, but the caller gate in `plan_tool.cli.review_cmd.cmd_review` still requires `sys.stdin.isatty()`. A configured headless process therefore reports findings and returns without reaching the provider. Simply opening the gate is unsafe because the existing annotation default dispatches `apply`, downstream review actions can retain an applied change automatically in a non-TTY process, and some actions include terminal-only confirmation prompts.

## Architecture

`cmd_review` and `_review_walk_environment_allows` will allow entry only when the existing remote mode is explicitly configured and stdin is non-TTY; a missing TTY alone will not imply remote mode. The selected path uses the existing `plan_tool.human_io` provider and `review_walk.walk_recommendations`, which already publish `review-walk.annotation` and `review-walk.feedback`, without introducing another provider or transport.

For this caller only, `walk_recommendations` will present and enforce a non-mutating response set. Skip and feedback remain annotations, blank input dispatches no action, and apply, run, apply-all, file-check, and structural commands cannot reach `cli/review_actions`. Remote feedback remains pending until a later terminal walk handles action.

The change is limited to `plan_tool.cli.review_cmd.cmd_review`, its shared environment gate, and `plan_tool.review_walk.walk_recommendations` as needed for the restricted command surface. It does not establish a common headless policy for other `walk_recommendations` callers, `input_fn(` users, or TTY-gated routes.

## Out of scope

- `cmd_review_walk` remains terminal-only because it is a separate entry command; `cmd_review --reuse` can resume the selected proof.
- `cli/review_actions` remains unchanged because apply, file-check, structural, keep/revert, and confirmation routes must be unreachable from the selected walk.
- `cli/reconcile` remains unchanged because detail and run reconciliation use separate reuse, iteration, and automated-apply rules.
- `cli/data_contract_cmd` and `cli/completeness_phases` remain unchanged because their manual audit-application walks modify authoritative documents.
- `cli/run_cmd` remains unchanged because missing-detail confirmation and run-scope choices are execution-selection or destructive-confirmation decisions.
- `create.py`, `intent_proposal.py`, and `cli/authoring.py` remain unchanged because their interactive choices, risk declarations, and save confirmations belong to authoring contracts.
- `detail.py`, `reground.py`, `scope_out.py`, `roadmap.py`, and `change_collision.py` remain unchanged because their TTY gates protect structural, replacement, or collision decisions.
- `cli/jira_cmd`, `cli/manifest.py`, `cli/worktree_cmd.py`, `cli/lessons_cmd.py`, `cli/gates_cmd.py`, and `cli/completeness_cmd.py` remain unchanged because they configure external work, modify manifests, or apply operator decisions.
- `claude_errors.py` remains unchanged because its rate-limit and backend-selection prompts recover a subprocess failure rather than handle a review-walk response.
- Repository-wide TTY detection, all other direct-input and availability routes, remote defaults, cancellation, transport changes, and record retention are excluded; #322 owns the later lifecycle-policy decisions.
- No second command will migrate merely because it has an `input_fn` or TTY check; each later route must establish its own behavior and owner.

## Risks

- **Unsafe mutation or terminal prompting in a headless process:** the current annotation default can dispatch `apply`, a non-TTY action can retain a change, and some downstream actions use raw terminal confirmation. The restricted remote response set mitigates this by making blank, apply, run, apply-all, file-check, and structural responses fail closed before action dispatch; broader action behavior remains unresolved and out of scope.
- **Unintended behavior changes for terminal or unrelated callers:** broadening TTY handling could affect distinct reuse, authoring, reconciliation, execution-selection, or destructive-confirmation contracts. The mitigation is to opt in only through the existing explicit remote configuration and limit the change to `cmd_review`; every other caller remains excluded.
- **Remote record lifecycle remains unsettled:** a remote session leaves request and resolution records for a future owner to clean up. #322 retains this unresolved lifecycle-policy decision.

## Testing

Add focused coverage in `tests/test_review_walk.py` for the selected `cmd_review` path. Verify that explicit remote mode with non-TTY stdin reaches request-record publication; that skip and feedback annotations persist without calling raw terminal input or the action callback; and that blank, apply, run, and apply-all responses fail closed. Retain the existing terminal-walk and ordinary non-TTY skip coverage, including preservation of the current command menu, default apply behavior, and feedback semantics when remote mode is unset.

## Acceptance criteria

- With `PLAN_TOOL_HUMAN_IO=remote` explicitly configured and stdin non-TTY, `plan_tool.cli.review_cmd.cmd_review` starts one saved-review walk and reaches provider request records.
- In that walk, remote skip and feedback responses persist as annotations without calling raw terminal input or the action callback.
- Blank input dispatches no action, and apply, run, apply-all, file-check, and structural responses cannot execute or mutate a plan.
- Remote feedback remains an annotation until a later terminal walk handles action.
- With remote mode unset, the current terminal command menu, default apply behavior, feedback semantics, and ordinary non-TTY skip remain unchanged.
- `--no-walk`, `--no-save`, and `--dry-run` continue to suppress the walk.
- `cmd_review_walk` and every other `walk_recommendations` caller retain their existing behavior.
- The completed scope is checked against `cmd_review`, `walk_recommendations`, remote mode, action commands, headless, annotation-only, mutation, skip, feedback, and TTY.

## Deferred

- Resolved record retention is deferred to #322 because cleanup and lifecycle policy require a separate decision.
- Remote defaults, cancellation, and transport changes are deferred to #322 rather than being selected by this caller-entry proof.

## Input

This plan consumes the existing `plan_tool.human_io` provider contract established by the completed `human-input-seam` plan: filesystem request records, resolution matching, and no-clobber publication after `walk_recommendations` starts. It also relies on `review_walk.walk_recommendations` publishing `review-walk.annotation` and `review-walk.feedback`. The proof covers consumption of that landed provider through `cmd_review`; it does not verify or alter transport, cancellation, remote defaults, or record-retention policy.
