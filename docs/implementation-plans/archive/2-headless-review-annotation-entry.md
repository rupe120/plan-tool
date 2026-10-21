> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Headless Review Annotation Entry
intent: When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not
  a TTY, the `review` command handler (`review`, `reconcile`, and `reconcile-plan`)
  will start one saved-review walk only when an ordinary fresh result (not `--refresh`)
  or an eligible saved review has a promptable finding. It accepts only remote skip
  and quit responses and will not dispatch an action or mutate a plan in that mode.
  Existing remote TTY behavior, terminal behavior, ordinary non-TTY skipping, and
  report visibility will remain unchanged.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/archive/headless-review-annotation-entry.replaced.md
steps:
- id: 1
  title: Add a remote-only closed skip-or-quit response set that rejects every other
    spelling by ending the walk without action dispatch
  intent: Make remote review responses safe to accept before a headless caller can
    enter the shared walk.
  files:
  - plan_tool/review_walk.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/headless-review-annotation-entry/01-remote-only-closed-skip-quit-response.md
  status: done
- id: 2
  title: Let explicit remote non-TTY cmd_review walk only ordinary fresh or eligible
    saved reviews with a promptable finding while keeping excluded findings visible
  intent: Allow a remote operator to skip newly generated or reused review findings
    from a headless process without authorizing plan edits or hiding other findings;
    leave the separate --refresh workflow unchanged.
  files:
  - plan_tool/cli/review_cmd.py
  - docs/cli/reconcile-plan.md
  - tests/test_review.py
  - tests/test_review_walk.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the non-mutating walk policy that makes remote caller entry safe.
  detail: docs/implementation-plans/plan-details/headless-review-annotation-entry/02-let-explicit-remote-non-tty-cmd-review.md
  status: done
  status_note: '2026-08-28: the initial run passed test authoring but stopped on CLI-reference
    drift; recovery regenerated the reference and the complete suite passed (11,164
    passed, 188 skipped).'
- id: 3
  title: Document the restricted remote review prompt and saved-skip behavior
  intent: Keep the documented remote prompt, allowed responses, and caller scope aligned
    with the implemented proof.
  files:
  - HUMAN_IO_FORMAT.md
  complexity: low
  change_type: non-code
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Defines the restricted skip-or-quit response contract.
    2: Defines fresh and saved-review remote entry, help, and opt-out behavior.
  detail: docs/implementation-plans/plan-details/headless-review-annotation-entry/03-document-restricted-remote-review.md
  status: done
---
# Headless Review Annotation Entry

## Overview

When `PLAN_TOOL_HUMAN_IO=remote` is explicitly configured and stdin is not a TTY, `plan_tool.cli.review_cmd.cmd_review` will start one saved-review walk for `review`, `reconcile`, and `reconcile-plan` only when an ordinary fresh result (not `--refresh`) or eligible saved review has a promptable finding. The walk accepts only remote skip and quit responses; every other spelling ends that restricted walk after its one annotation request without mutating a plan. Every finding excluded from that restricted walk remains visible in the fresh or reused report. Existing remote TTY behavior, terminal behavior, ordinary non-TTY skipping, and the separate `--refresh` workflow remain unchanged, while `--no-walk`, `--no-save`, and `--dry-run` continue to suppress the walk.

## Problem statement

The completed `human-input-seam` plan establishes filesystem request and resolution records only after `walk_recommendations` starts, but the caller gate in `plan_tool.cli.review_cmd.cmd_review` still requires `sys.stdin.isatty()`. A configured headless process therefore reports findings and returns without reaching the provider. Simply opening the gate is unsafe because the existing annotation default dispatches `apply`, downstream review actions can retain an applied change automatically in a non-TTY process, and some actions include terminal-only confirmation prompts.

## Architecture

`cmd_review` and `_review_walk_environment_allows` will add one caller-specific gate: explicit remote mode plus non-TTY stdin. A missing TTY alone will not imply remote mode. The selected path uses the existing `plan_tool.human_io` provider and `review_walk.walk_recommendations` without introducing another provider or transport.

For this caller only, `walk_recommendations` will accept exactly `s`/`skip` to persist a skip and `q`/`quit` to end without an annotation. Blank input; `a`/`apply`; `d`/`done`; `aa`/`apply-all`/`all`; `f`/`feedback`/`n`/`note`; `r`/`run`; `?`/`help`; and every other spelling will end the selected walk after that one `review-walk.annotation` request, with no annotation, feedback request, second annotation request, or action dispatch. The selected entry does not establish a feedback handoff.

The gate table is fixed. Explicit remote mode with non-TTY stdin uses the restricted response set. Explicit remote mode with a TTY preserves the existing full remote-provider walk. Unset remote mode with a TTY preserves the existing terminal walk, and unset remote mode with non-TTY stdin preserves the existing skip. `--no-walk`, `--no-save`, and `--dry-run` suppress a walk in every row.

A finding is promptable exactly when the existing normal, non-rewalk `walk_recommendations` selection would prompt it at the supplied `--include-info` setting. An unannotated finding or one with a `failed` annotation remains promptable; `applied`, `skip`, and `open` annotations remain report-only. This preserves the existing default INFO selection and its `--include-info` override rather than adding a remote-specific filter.

The remote non-TTY report remains a complete reading surface. It does not enter the detail-suppressing presentation used by a terminal full walk: a fresh report keeps its full finding detail and suggested actions, and a reused report shows every finding excluded from the restricted walk, including hidden and terminally annotated items. The restricted walk supplements that report; it never makes a finding disappear.

The change is limited to `plan_tool.cli.review_cmd.cmd_review`, its shared environment gate, and `plan_tool.review_walk.walk_recommendations` as needed for the restricted command surface. It does not establish a common headless policy for other `walk_recommendations` callers, `input_fn(` users, or TTY-gated routes.

## Input

This plan consumes the existing `plan_tool.human_io` provider contract established by the completed `human-input-seam` plan: filesystem request records, resolution matching, and no-clobber publication after `walk_recommendations` starts. The selected entry emits only `review-walk.annotation`; the existing feedback prompt remains outside this caller-specific proof. The plan does not verify or alter transport, cancellation, remote defaults, or record-retention policy.

## References

- [sys — System-specific parameters and functionshttps: — Documents sys.stdin and standard-stream behavior needed for the review walk’s TTY entry gate.
- [io — Core tools for working with streamshttps: — Defines isatty() semantics for distinguishing terminal and headless input streams.
- [os — Miscellaneous operating system interfaceshttps: — Documents process-environment access used to require explicit PLAN_TOOL_HUMAN_IO remote configuration.
- [How to monkeypatch/mock modules and environmentshttps: — Covers safely patching environment variables, stdin behavior, and callbacks in focused pytest coverage.
- [pytest API Reference — tmp_pathhttps: — Documents the isolated temporary-directory fixture used to test remote request and annotation records.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- `cmd_review_walk` remains terminal-only because it is a separate entry command; `cmd_review --reuse` can resume the selected proof.
- `reconcile-plan --refresh` remains unchanged because its fingerprint-gated auto-reconcile workflow reaches a separate saved-review and terminal-walk contract.
- `cli/review_actions` remains unchanged because apply, file-check, structural, keep/revert, and confirmation routes must be unreachable from the selected walk.
- Remote feedback remains outside this caller-specific proof because a later terminal action needs its own durable re-entry contract.
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

- **Unsafe mutation or terminal prompting in a headless process:** the current annotation default can dispatch `apply`, a non-TTY action can retain a change, and some downstream actions use raw terminal confirmation. The restricted remote response set mitigates this by ending after every rejected response and making blank, apply, run, and apply-all fail closed before action dispatch; broader action behavior remains unresolved and out of scope.
- **Unintended behavior changes for terminal or unrelated callers:** broadening TTY handling could affect distinct reuse, authoring, reconciliation, execution-selection, or destructive-confirmation contracts. The fixed gate table retains remote TTY, terminal TTY, and ordinary non-TTY behavior; it opts in only through explicit remote configuration and limits the change to `cmd_review`.
- **A restricted walk can hide excluded findings:** a fresh report currently suppresses detail when a walk is expected, while a reused non-TTY report prints its findings. The selected remote path keeps every excluded finding visible; it does not treat walking a subset as report suppression.
- **Remote record lifecycle remains unsettled:** a remote session leaves request and resolution records for a future owner to clean up. #322 retains this unresolved lifecycle-policy decision.

## Testing

Add focused coverage in `tests/test_review_walk.py` for the selected `cmd_review` path. Verify that explicit remote mode with non-TTY stdin reaches request-record publication for an ordinary fresh result or an eligible saved review with a promptable finding; zero-finding and otherwise unpromptable saves retain their existing no-walk behavior. Cover the normal selection at both `--include-info` settings, a `failed` annotation that remains promptable, and `applied`, `skip`, and `open` annotations that remain report-only. Verify that fresh hidden-only and mixed results retain all excluded finding detail and suggested actions, and that reused hidden or terminally annotated findings remain visible to the caller. Verify that `s`/`skip` persists a skip without calling raw terminal input or the action callback, while `q`/`quit` leaves no annotation. Verify that blank, `a`/`apply`, `d`/`done`, `aa`/`apply-all`/`all`, `f`/`feedback`/`n`/`note`, `r`/`run`, `?`/`help`, and an unknown spelling end the walk with one annotation request and without an annotation, feedback request, or action callback. Retain the existing `--refresh` output and terminal-walk behavior, the fixed gate table, opt-out flags, and the existing terminal command menu, default apply behavior, and feedback semantics outside the selected entry. Update the command help and `HUMAN_IO_FORMAT.md` together so their remote non-TTY exception is accurate.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- With `PLAN_TOOL_HUMAN_IO=remote` explicitly configured and stdin non-TTY, an ordinary fresh result or eligible `--reuse` review starts one restricted saved-review walk and reaches provider request records only when it has a promptable finding. Promptable means the existing normal, non-rewalk selection at the supplied `--include-info` setting: unannotated and `failed` findings prompt, while `applied`, `skip`, and `open` findings remain report-only.
- A fresh report retains full finding detail and suggested actions, and a reused report leaves each hidden or terminally annotated finding visible, whether or not another finding enters the restricted walk.
- In that walk, `s`/`skip` persists an annotation without calling raw terminal input or the action callback, and `q`/`quit` ends without an annotation or action.
- Blank input; `a`/`apply`; `d`/`done`; `aa`/`apply-all`/`all`; `f`/`feedback`/`n`/`note`; `r`/`run`; `?`/`help`; and unknown input end the restricted walk after one annotation request and cannot persist an annotation, request feedback, execute, or mutate a plan.
- The selected entry does not emit `review-walk.feedback`.
- The gate table preserves the existing full remote-provider walk with a TTY, the existing terminal walk with remote mode unset and a TTY, and the existing ordinary non-TTY skip with remote mode unset.
- `--no-walk`, `--no-save`, and `--dry-run` continue to suppress the walk.
- `cmd_review_walk` and every other `walk_recommendations` caller retain their existing behavior.
- `reconcile-plan --refresh` retains its existing auto-reconcile report and terminal-walk direction.
- The `--no-walk` and `--reuse` help, and `HUMAN_IO_FORMAT.md`, state the explicit-remote non-TTY exception and its restricted response set.
- Before completion, run identifier (`cmd_review`, `--refresh`, `_render_refresh`, `_review_walk_environment_allows`, `assemble_report`, `walk_recommendations`, `--include-info`, `review-walk.annotation`, and `review-walk.feedback`) and vocabulary (remote, TTY, report, visible, hidden, promptable, skip, quit, reject, action, feedback, headless, and annotation) sweeps across the active plan, direct code/test/doc sites, and peer walk callers. Pass only when the selected entry still has the stated gate, inherited promptable selection, complete report, one-request rejection, and closed response set, every direct site supports that property, and no peer is changed without its own contract.

## Deferred

- Resolved record retention is deferred to #322 because cleanup and lifecycle policy require a separate decision.
- Remote feedback and a later terminal action handoff are deferred to #322 because they require a durable annotation and re-entry policy.
- Remote defaults, cancellation, and transport changes are deferred to #322 rather than being selected by this caller-entry proof.
