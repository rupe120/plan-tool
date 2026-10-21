> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Document both caller-specific restricted remote review entries

## Summary

Update `HUMAN_IO_FORMAT.md` to document the two restricted remote review entry points: inline `cmd_review` and standalone `cmd_review_walk`. Keep their entry conditions distinct while documenting their shared skip-or-quit response policy. On completion, the protocol names the correct commands and aliases, preserves terminal behavior, and does not imply that other review-walk callers gain remote access.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation change.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The missing standalone caller in the protocol.
- [Input](#input) — The landed step-1 behavior and existing protocol contract.
- [Files (creates vs edits)](#files-creates-vs-edits) — The single documentation file this step changes.
- [Implementation](#implementation) — Caller-specific entry rules and shared restricted behavior.
- [Tests](#tests) — Non-code verification against the landed command behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Primary references for input mode, environment, and aliases.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this documentation work.
- [Deferred](#deferred) — Work this documentation step does not perform.

## Why

`HUMAN_IO_FORMAT.md:Restricted remote review` describes only the inline `plan_tool/cli/review_cmd.py:cmd_review` route and explicitly excludes `cmd_review_walk`. Step 1 adds the same narrow remote annotation capability to the standalone saved-review route, so the protocol must name both callers and their different eligibility paths before readers treat the old terminal-only statement as current behavior.

## Input

- **Step 1 supplies the standalone route.** Read the landed `plan_tool/cli/review_cmd.py:cmd_review_walk` behavior from step 1 before documenting it. Resolve a discrepancy against this detail through the plan’s selected skip-only contract; do not let the documentation redefine the step-1 response boundary.

- **The existing protocol owns provider setup.** Keep `HUMAN_IO_FORMAT.md:Configure a provider`, `HUMAN_IO_FORMAT.md:Records`, and `HUMAN_IO_FORMAT.md:Operator lifecycle` as the source for filesystem-provider configuration and record handling.

- **The command entry points have different selection rules.** Ground the inline route in `plan_tool/cli/review_cmd.py:_remote_non_tty_review_walk_allowed` and `_cmd_review_body`; ground the standalone route in `plan_tool/cli/review_cmd.py:cmd_review_walk` and `_direct_walk_ineligibility`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `HUMAN_IO_FORMAT.md` — Update the source-of-truth introduction, `## Scope`, and `## Restricted remote review` so they describe both caller-specific remote entries and their shared restricted response rules.

## Implementation

- **Foundational logic: caller-specific restricted remote entry inventory.** Document `plan_tool/cli/review_cmd.py:cmd_review` and `plan_tool/cli/review_cmd.py:cmd_review_walk` as the only two command handlers that may start the restricted remote non-TTY annotation walk.

- **Name each command family correctly.** Use `plan_tool/cli/review_cmd.py:register` as the authority for the canonical command and aliases: the inline review family reaches `cmd_review`, while the saved-review walk family reaches `cmd_review_walk`.

- **Keep the entries separate.** Describe the inline route’s fresh-review and saved-review reuse conditions separately from the standalone route’s eligible saved-review selection. Do not copy inline-only flags or checks onto the standalone command.

- **Describe the shared remote gate precisely.** Both entries require configured remote human input and non-TTY stdin. Preserve the existing provider configuration requirements in `HUMAN_IO_FORMAT.md:Configure a provider`; do not imply that setting only `PLAN_TOOL_HUMAN_IO=remote` is sufficient to start a request.

- **Document the closed response policy once.** `plan_tool/review_walk.py:walk_recommendations` with `WalkResponsePolicy.SKIP_OR_QUIT` accepts skip and quit only. State that a skip uses the existing saved-review annotation path, while quit, blank input, and other responses end the restricted walk without an action or feedback request.

- **Separate protocol traffic from authoritative review state.** The filesystem provider creates request and resolution records as part of remote input. The restricted route’s only review-state update is the existing skip annotation; it must not apply a finding, collect feedback, or mutate the plan or code.

- **Preserve terminal behavior.** Make clear that TTY use retains the full annotation and feedback menu for both callers, including when remote provider configuration is present.

- **Scope the exception by caller, not by the shared walk function.** `plan_tool/cli/data_contract_cmd.py`, `plan_tool/cli/reconcile.py`, and `plan_tool/cli/completeness_phases.py` also call `plan_tool/review_walk.py:walk_recommendations`, but the protocol must not list them as restricted remote entries.

## Tests

This non-code step adds no automated tests or production code changes.

### Verification (non-code step)

1. Compare every documented command name and alias with `plan_tool/cli/review_cmd.py:register`.
2. Compare the inline entry conditions with `plan_tool/cli/review_cmd.py:_remote_non_tty_review_walk_allowed` and `_cmd_review_body`.
3. Compare the standalone entry conditions with the step-1 result in `plan_tool/cli/review_cmd.py:cmd_review_walk`, including its saved-review eligibility boundary.
4. Confirm the documented response outcomes match `plan_tool/review_walk.py:WalkResponsePolicy.SKIP_OR_QUIT` and `plan_tool/review_walk.py:walk_recommendations`.
5. Read `tests/test_review_walk.py:TestCliReviewRemoteNonTty` and the step-1 standalone remote-walk coverage to confirm the documented modes and exclusions are covered.
6. Verify the `Restricted remote review` link in `HUMAN_IO_FORMAT.md:Scope` still targets the heading after the edit.

## Acceptance criteria

- `HUMAN_IO_FORMAT.md` names both `cmd_review` and `cmd_review_walk` as caller-specific restricted remote review entries.
- Each entry names its canonical command and aliases as registered by `plan_tool/cli/review_cmd.py:register`.
- The document distinguishes the inline review route from the standalone saved-review route without assigning one caller’s eligibility rules to the other.
- The document states that restricted remote input accepts skip or quit only and that every other annotation response ends without an action or feedback request.
- The document distinguishes normal provider request and resolution records from the saved-review skip annotation.
- The document states that terminal use retains the full review-walk menu.
- The restricted-entry list does not expand to other `walk_recommendations` callers.

## References

- [io — Core tools for working with streamshttps: — Verify the terminal versus non-TTY distinction used by both documented entries.
- [os — Miscellaneous operating system interfaceshttps: — Verify the environment configuration the remote-entry text describes.
- [argparse — Parser for command-line options, arguments and subcommandshttps: — Verify canonical command and alias dispatch terminology.

## Applicable guardrails

- **The plan’s “## Plan intent” applies.** Keep the protocol focused on the narrow remote annotation path and preserve ordinary terminal and headless behavior.

- **The plan’s “## Step intent” applies.** Align the documented caller list and restricted behavior with the landed command boundaries.

- **The plan’s “## Out of scope” applies.** Do not use this documentation edit to widen behavior beyond the plan’s listed surfaces.

## Deferred

- Command behavior and automated coverage — Step 1 owns the standalone implementation and its tests; this step only documents the landed behavior.
- Provider lifecycle policy and record cleanup — Remain governed by the existing protocol and the plan’s out-of-scope boundary.
