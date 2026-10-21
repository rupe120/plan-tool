> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Document the restricted remote review prompt and saved-skip behavior

## Summary

Update `HUMAN_IO_FORMAT.md` to describe the restricted remote non-TTY review path that steps 1 and 2 establish. Keep the existing provider-record protocol, while separating the restricted `cmd_review` entry from the full remote TTY walk. Document the closed skip-or-quit prompt, rejected-response outcome, and how a saved skip affects later reuse. On green, operators can tell exactly when a remote request is expected and which responses can change saved review state.

## Table of Contents

- [Summary](#summary) — Gives the documentation change and its observable result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Explains the missing operator-facing contract.
- [Input](#input) — Names the landed walk, command, and saved-review behavior this doc describes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the single documentation edit.
- [Implementation](#implementation) — Defines the restricted prompt, saved-skip, and caller-scope documentation.
- [Tests](#tests) — Identifies the upstream behavior coverage and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Gives checkable documentation outcomes.
- [References](#references) — Links to the stream and environment APIs behind the documented gate.
- [Applicable guardrails](#applicable-guardrails) — Records the plan boundaries this documentation must preserve.
- [Deferred](#deferred) — Names lifecycle and broader-route documentation left outside this step.

## Why

`HUMAN_IO_FORMAT.md` currently documents the remote provider’s general annotation prompt, which advertises actions that the new remote non-TTY entry must reject. Without a caller-specific section, an operator cannot distinguish a full remote TTY walk from the closed headless path or know that a saved skip remains visible without being prompted again. This update keeps the protocol reference aligned with the implemented proof without presenting the restricted behavior as a repository-wide input policy.

## Input

- **Step 1 closed response contract:** Read the landed behavior from `plan_tool/review_walk.py:walk_recommendations` and `plan_tool/review_walk.py:_prompt_for_annotation`. The landed code names and accepted responses win over either earlier detail file if they differ.

- **Step 2 caller contract:** Read the selected entry behavior from `plan_tool/cli/review_cmd.py:cmd_review`, `_cmd_review_body`, and `_review_walk_environment_allows`. Step 2 owns the command behavior; this step documents it without changing it.

- **Saved-review state:** Use `plan_tool/review_persistence.py:SavedReview`, `Annotation`, and `update_annotation` to describe the observable saved-skip result. The documentation must distinguish a persisted skip from a response that only ends the walk.

- **Provider records:** Keep `plan_tool/human_io.py:make_human_input_provider`, `HumanInputRequest`, and `HumanInputResolution` as the source of the filesystem-record format. This step adds no record field, transport, or lifecycle rule.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `HUMAN_IO_FORMAT.md` — update the source-of-truth orientation and scope, then add the restricted remote-review prompt, response, saved-skip, and caller-boundary documentation.

## Implementation

- **Foundational logic:** Document the caller-specific restricted remote review contract: explicit remote configuration plus non-TTY input can open one closed annotation prompt, while all other review-walk modes retain their existing response sets.

- **Keep the provider protocol separate from the entry rule.** Retain `HUMAN_IO_FORMAT.md`’s record-format and publication guidance. Extend its source-of-truth orientation to point readers to `plan_tool/review_walk.py:walk_recommendations` and `plan_tool/cli/review_cmd.py:cmd_review` for the restricted behavior.

- **Add a distinct restricted-review section.** State that the exception applies only to the `reconcile-plan` command surface registered by `plan_tool/cli/review_cmd.py:register`, including its `reconcile` and `review` aliases. It requires explicit `PLAN_TOOL_HUMAN_IO=remote`, non-TTY stdin, a promptable ordinary fresh result or eligible saved review, and no walk-suppressing option. Do not describe `--yes` or non-TTY input alone as an activation path.

- **Document the closed prompt as an operator contract.** Show that the restricted `review-walk.annotation` request advertises skip and quit only. State that `s` and `skip` persist a skip, `q` and `quit` end the walk without an annotation, and blank or every other response ends the walk after that one annotation request without an annotation, action, or feedback request.

- **Explain saved-skip behavior beside the response rules.** A valid restricted skip becomes the finding’s saved `Annotation(status="skip", note="")`. On eligible saved-review reuse, a skipped finding stays visible in the report but is not promptable; the same report-only treatment applies to other terminal annotations. A `failed` annotation remains promptable under the normal selection rule.

- **Preserve the full remote walk’s scope.** Make clear that remote mode with a TTY retains the full annotation and feedback menu. Keep `plan_tool/cli/review_cmd.py:cmd_review_walk`, `plan_tool/cli/review_cmd.py:_render_refresh`, other direct-input routes, remote feedback handoff, and provider lifecycle policy outside this documented exception.

- **Avoid new protocol claims.** Do not add JSON fields, retention guidance, cancellation behavior, transport defaults, or a general headless-input policy. The documentation must describe only behavior steps 1 and 2 prove.

## Tests

- `tests/test_review_walk.py` — use step 1’s restricted-response cases to verify the documented prompt, skip persistence, quit behavior, and rejected-response outcome.
- `tests/test_review.py` — use step 2’s remote non-TTY entry and saved-review selection cases to verify the documented caller scope and report-only saved skips.

### Verification (non-code step)

1. Confirm the restricted prompt text and response outcomes against `plan_tool/review_walk.py:walk_recommendations` and `_prompt_for_annotation`.
2. Confirm the entry, opt-out, saved-review, and refresh boundaries against `plan_tool/cli/review_cmd.py:cmd_review`, `_cmd_review_body`, and `_review_walk_environment_allows`.
3. Confirm the saved annotation wording against `plan_tool/review_persistence.py:Annotation` and `update_annotation`.
4. Search `HUMAN_IO_FORMAT.md`, `plan_tool/review_walk.py`, and `plan_tool/cli/review_cmd.py` for `review-walk.annotation`, `review-walk.feedback`, `remote`, `TTY`, `skip`, and `quit`; resolve any conflicting operator-facing claim.
5. Run `uv run pytest tests/test_review_walk.py tests/test_review.py -q` and the plan test command after the landed documentation matches the upstream behavior.
6. Run `git diff --check` and confirm `HUMAN_IO_FORMAT.md` contains no line-number anchors.

## Acceptance criteria

- `HUMAN_IO_FORMAT.md` identifies `plan_tool/review_walk.py:walk_recommendations` and `plan_tool/cli/review_cmd.py:cmd_review` as the enforcing surfaces for the restricted remote-review behavior.

- The document states the explicit remote non-TTY gate, its ordinary fresh and eligible saved-review scope, and its walk-suppressing conditions without presenting them as a general remote-input rule.

- The restricted `review-walk.annotation` prompt documents only skip and quit as accepted responses.

- The document states that valid skip persists a saved skip, while quit and rejected input leave no new annotation and end the restricted walk after one annotation request.

- The document states that a saved skip remains visible but does not prompt again during eligible saved-review reuse.

- The document distinguishes the restricted path from the full remote TTY walk, `cmd_review_walk`, and the separate refresh route.

- `HUMAN_IO_FORMAT.md` adds no transport, record-schema, lifecycle, or feedback-handoff rule.

- The focused review-walk and review-command tests pass, and documentation verification completes without conflicting terminology.

## References

- [sys — System-specific parameters and functionshttps: — Read for the standard-input surface behind the caller entry rule.
- [io — Core tools for working with streamshttps: — Read for the TTY distinction the documentation describes.
- [os — Miscellaneous operating system interfaceshttps: — Read for the explicit remote-provider environment configuration.

## Applicable guardrails

- **Caller-specific entry:** The plan’s `## Plan intent`, selected review-command boundary limits this documentation to the explicit remote non-TTY `cmd_review` path and its aliases.

- **No action routes:** The plan’s `## Out of scope`, review-action boundary requires the restricted-path documentation to state that it cannot dispatch actions or mutate a plan.

- **No feedback handoff:** The plan’s `## Out of scope`, remote-feedback boundary requires the restricted-path documentation to omit feedback capture while preserving the separate full-walk behavior.

- **Refresh separation:** The plan’s `## Out of scope`, refresh boundary requires the documentation to keep the fingerprint-gated refresh workflow outside the remote exception.

- **Provider ownership:** The plan’s `## Out of scope`, lifecycle-policy boundary requires this step to leave transport, cancellation, defaults, and record retention undescribed beyond the existing provider protocol.

## Deferred

- Remote feedback, cancellation, retention, and documentation for additional input routes — remain with the lifecycle-policy follow-up tracked as #322.
