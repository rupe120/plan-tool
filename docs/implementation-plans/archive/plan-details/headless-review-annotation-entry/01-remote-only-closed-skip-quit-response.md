> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add a remote-only closed skip-or-quit response set that rejects every other spelling by ending the walk without action dispatch

## Summary

Add a default-off restricted response policy to `plan_tool/review_walk.py:walk_recommendations` for a caller that needs a remote skip-or-quit-only walk. Thread that policy through `plan_tool/review_walk.py:_prompt_for_annotation` so the restricted prompt accepts only skip and quit after the walk’s existing input normalization. Keep unrestricted walks on their current full annotation, feedback, and action paths. On green, a rejected restricted response ends the walk after one annotation request without persisting an annotation or dispatching an action.

## Table of Contents

- [Summary](#summary) — Reviewer-level description of the restricted walk change.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains why the shared walk needs an opt-in safe response set.
- [Input](#input) — Names the saved-review and human-input contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the two existing files this step changes.
- [Implementation](#implementation) — Defines the closed response policy and unchanged caller behavior.
- [Tests](#tests) — Covers accepted, quit, rejected, and unrestricted paths.
- [Acceptance criteria](#acceptance-criteria) — Gives checkable completion conditions.
- [References](#references) — Links to the relevant testing and environment documentation.
- [Applicable guardrails](#applicable-guardrails) — Records the caller and mutation boundaries for this step.

## Why

`plan_tool/review_walk.py:_prompt_for_annotation` currently treats blank input as apply and exposes feedback, run, apply-all, and action-dispatch routes. A later `cmd_review` entry can safely start this shared walk from remote non-TTY input only if the walk itself has an opt-in response policy that makes every response except skip or quit fail closed before those routes run.

## Input

- **Saved review state:** `plan_tool.review_persistence:SavedReview` supplies recommendations and persisted `Annotation` records. The restricted path must use the normal walk’s persistence path only for a valid skip.
- **Human-input contract:** `plan_tool.human_io:HumanInputProvider`, `HumanInputRequest`, and `HumanInputResolution.text` remain the source of the annotation response. Rejected input must consume only the existing `review-walk.annotation` request.
- **Action state:** `plan_tool/review_walk:WalkState` and the optional `action_fn` remain available to unrestricted walks. The restricted path must not set fast-forward or feedback state and must not invoke the callback.
- **Caller selection:** step 2 owns choosing this policy for the eligible remote non-TTY `plan_tool/cli/review_cmd.py:cmd_review` paths. This step must expose the policy without inspecting environment configuration or TTY state itself.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add the explicit restricted per-walk response policy and route it through the annotation prompt.
  - `tests/test_review_walk.py` — add focused remote-provider coverage for the closed response set and retain unrestricted-walk controls.

## Implementation

- **Add an explicit opt-in policy to `plan_tool/review_walk.py:walk_recommendations`.** Keep its default on the current full walk behavior so existing callers do not change until they deliberately select the restricted policy.

- **Keep the choice at the walk boundary.** Pass the policy into `plan_tool/review_walk.py:_prompt_for_annotation`, or an equivalent single annotation-response boundary. Do not infer it from `PLAN_TOOL_HUMAN_IO`, the provider type, or `sys.stdin`; remote TTY walks must retain the full menu, and the shared walk has callers with separate contracts.

- **Use a closed normalized response set.** In restricted mode, only normalized `s` and `skip` may return `Annotation(status="skip", note="")`; only normalized `q` and `quit` may return the normal quit signal. Blank input and every other response, including current apply, done, apply-all, feedback, run, help, and unknown aliases, must return that quit signal immediately.

- **Fail closed before all action-capable branches.** A rejected restricted response must not reach `action_fn`, `is_dispatchable`, `_auto_apply`, feedback handling, `HELP_TEXT`, or a second annotation prompt. It must not persist an annotation, mutate `WalkState`, or request `review-walk.feedback`.

- **Keep the request shape narrow and clear.** The restricted annotation request must still use `plan_tool/review_walk.py:_request_human_input` and prompt id `review-walk.annotation`, while its displayed prompt must advertise only the allowed skip and quit choices.

- **Preserve normal walk results.** Returning the quit signal must let `walk_recommendations` produce its existing early-exit behavior through `WalkResult`, leaving the current and later recommendations untouched. A valid skip must retain the ordinary persistence and continuation behavior.

- **Leave peer callers on the default policy.** `plan_tool/cli/reconcile.py:cmd_reconcile` and `_walk_with_reconcile_phase`, plus `plan_tool/cli/review_cmd.py:cmd_review_walk`, must retain the unrestricted walk. Step 2 alone updates the `cmd_review` entry paths to opt into this policy.

- **Reject a broader remote-mode branch.** Do not add provider transport behavior, environment checks, lifecycle handling, or a common headless policy to `plan_tool/review_walk.py`; those concerns belong to the caller and the plan’s later lifecycle work.

## Tests

### Tests for this step

- `test_restricted_remote_skip_spellings_persist_skip_without_dispatch` — parameterize `s` and `skip`; each remote response persists one skip and never calls terminal input or `action_fn`.
- `test_restricted_remote_quit_spellings_leave_no_annotation` — parameterize `q` and `quit`; each response ends early with no annotation and no action callback.
- `test_restricted_remote_rejects_every_non_skip_quit_response_after_one_request` — cover blank, apply, done, apply-all, feedback, run, help, and an unknown response; each ends the walk after one `review-walk.annotation` request with no annotation, feedback request, action dispatch, or second recommendation prompt.
- `test_restricted_remote_annotation_prompt_advertises_only_skip_and_quit` — assert the published remote request does not offer apply, feedback, run, or help choices.
- `test_unrestricted_walk_keeps_existing_remote_annotation_and_feedback_behavior` — retain the full remote-provider path as a control, including normal action and feedback handling when the new policy is not selected.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A caller can explicitly select a restricted response policy on `plan_tool/review_walk.py:walk_recommendations` without changing the default full-walk behavior.
- In restricted mode, normalized `s` and `skip` persist only `Annotation(status="skip", note="")`.
- In restricted mode, normalized `q` and `quit end the walk without adding an annotation.
- Blank input, existing action aliases, feedback aliases, help, and unknown input end the restricted walk after one `review-walk.annotation` request.
- No rejected restricted response calls `action_fn`, emits `review-walk.feedback`, changes `WalkState`, or persists an annotation.
- `tests/test_review_walk.py` passes with both the restricted remote-provider cases and the unrestricted regression cases.

## References

- [os — Miscellaneous operating system interfaceshttps: — Use for focused tests that configure the existing remote human-input provider.
- [How to monkeypatch/mock modules and environmentshttps: — Use for isolated environment and callback setup in the walk tests.
- [pytest API Reference — tmp_pathhttps: — Use for remote request, resolution, and persisted annotation records.

## Applicable guardrails

- **Caller-specific scope:** The plan’s `## Out of scope`, caller-specific route fence limits this step to an opt-in policy in `plan_tool/review_walk.py`; it must not migrate peer walk callers or introduce repository-wide headless behavior.
- **No action routes:** The plan’s `## Out of scope`, review-action boundary requires the restricted branch to make apply, structural, file-check, confirmation, and keep-or-revert routes unreachable by ending before dispatch.
- **No feedback handoff:** The plan’s `## Out of scope`, remote-feedback boundary requires the restricted branch to omit feedback capture and `review-walk.feedback` requests.
- **No transport changes:** The plan’s `## Input`, human-input provider boundary keeps `plan_tool/human_io.py` and record lifecycle behavior unchanged.
- **Preserve existing modes:** The plan’s `## Architecture`, fixed gate table requires the policy to be explicit and default-off so terminal and remote-TTY walks keep their current full response set.
