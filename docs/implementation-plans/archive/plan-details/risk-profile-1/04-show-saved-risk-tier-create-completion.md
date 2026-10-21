> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Show the saved risk tier in create's completion summary

## Summary

Extend `plan_tool/cli/authoring.py:cmd_create` so a successful single-plan create reports the risk tier saved on the published plan. Update `README.md` to describe that confirmation, with focused command-level coverage in `tests/cli/test_authoring_cmds.py`. Read the persisted declaration rather than reusing a proposal or inferring risk from priority; a parse-valid plan with no declaration emits an unconfirmed-summary warning. On green, operators see the recorded `low`, `standard`, or `high` tier immediately after create completes, or a warning that the saved declaration cannot be confirmed.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and key display rule.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why create must confirm the saved declaration.
- [Input](#input) — Upstream persistence and current summary contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Required completion-summary behavior and boundaries.
- [Tests](#tests) — Focused CLI regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Typed-model reference for the persisted plan read.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this display change.

## Why

`plan_tool/cli/authoring.py:cmd_create` currently reports the created path and manifest result but does not confirm the risk declaration step 3 saved. That leaves an operator unable to tell whether create recorded the intended tier without reopening frontmatter, and showing a proposal or `Plan.priority` instead would report the wrong decision.

## Input

- **Step 3 published declaration:** Step 3 creates and persists the paired risk declaration before publication. A normal new-plan result therefore has an explicit saved tier.
- **Result boundary:** Step 3 keeps `plan_tool/create.py:CreateResult` unchanged. Use `CreateResult.plan_path` as the handoff to the published artifact; do not add a risk field to the result type.
- **Current summary flow:** `plan_tool/cli/authoring.py:cmd_create` handles `split_proposal` before its normal `success` and `detail` summary output. `plan_tool/parser.py:parse_plan` is already available in this module and reads the persisted `Plan`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` — Add the saved-tier line to `cmd_create`’s successful single-plan completion summary.
  - `README.md` — Document the single-plan completion confirmation in the `### 1. create` section.
  - `tests/cli/test_authoring_cmds.py` — Add summary assertions and update any affected create stub to provide a valid published plan.

## Implementation

- **Foundational logic:** Render the persisted `Plan.risk_profile` in the normal create completion summary when it is present; otherwise preserve success and emit an unconfirmed-declaration warning.

- **Read the saved plan, not create-time state.** After `plan_tool/cli/authoring.py:cmd_create` receives a normal `CreateResult`, read `CreateResult.plan_path` through `plan_tool/parser.py:parse_plan` and use its raw `Plan.risk_profile` value for the display. If parsing succeeds but the raw declaration is absent, warn that the saved declaration cannot be confirmed; do not render `None` as a tier.

- **Keep the display tied to the final declaration.** Place one clear tier line with the existing `success` and `detail` summary helpers. It must describe the tier stored on disk after `plan_tool/create.py:create_plan` returns, not step 2’s proposal, its rationale, decision mode, or `Plan.priority`.

- **Do not invent a legacy fallback.** Do not use step 1’s effective-standard accessor for this summary. Step 3 guarantees an explicit declaration for newly created plans, and a fallback would hide a missing saved declaration.

- **Make confirmation fail soft.** If the post-create persisted-plan read fails or succeeds without a raw declaration, warn that the saved tier could not be confirmed and continue the already-successful registered create path. Do not turn either display-only state into a recovery state, roll back branch ownership, or suppress the existing source/distilled-artifact archival tail.

- **Preserve terminal routing.** Keep `cmd_create`’s split-proposal early return unchanged: a split creates no plan and therefore has no saved risk tier to report. Do not change source archival, manifest handling, grounding, next-step suggestions, checkpoint behavior, or exit codes.

- **Keep documentation narrow.** In `README.md`’s `### 1. create` section, state that a completed single-plan create confirms its saved tier. Do not add a new option, change the proposal flow, or document downstream tier behavior.

## Tests

Add command-level coverage in `tests/cli/test_authoring_cmds.py` using the existing `main(...)`, `CreateResult`, and captured-output seams.

### Tests for this step

- `test_create_completion_summary_reports_persisted_risk_tier` — A normal create reports each saved `low`, `standard`, and `high` tier from its published plan.
- `test_create_completion_summary_uses_saved_tier_not_plan_priority` — A plan whose priority differs from its saved risk tier reports the risk tier only.
- `test_main_create_split_proposal_does_not_stamp` — Extend the existing split-path test to prove no saved-tier summary appears when no plan is created.
- `test_create_completion_summary_read_failure_warns_without_rollback` — A persisted-plan read failure warns but preserves success status, branch binding, and the normal post-create tail.
- `test_create_completion_summary_missing_declaration_warns_without_fallback` — A parse-valid plan with an omitted legacy declaration warns without rendering `None` or inferred `standard`, and preserves the same success tail.
- `test_main_create_off_config_unchanged` — Update its fake created plan to include a valid explicit declaration so the branch-awareness regression still drives the normal summary path.

Every listed test must be green before this step is complete. Run `uv run pytest tests/cli/test_authoring_cmds.py -q`, then run the plan’s configured full test command before handoff.

## Acceptance criteria

- A successful single-plan `create` completion summary reports the exact persisted `risk_profile` value.
- A saved `standard` tier is reported as `standard` even when `Plan.priority` is `low`.
- The summary never reports a classifier proposal, inferred fallback, rationale, or decision mode as the saved tier.
- A saved-tier read failure or parse-valid missing declaration emits an unconfirmed warning but does not change a completed create’s success or branch ownership.
- A split proposal retains its existing no-plan output and has no risk-tier summary.
- `README.md` states that normal single-plan create output confirms the saved tier.
- `tests/cli/test_authoring_cmds.py` passes with the saved-tier and split-path coverage.

## References

- [Models | Pydantic Docshttps: — Use for the typed `Plan` value returned by the persisted-plan read.

## Applicable guardrails

- **The plan’s “## Plan intent”, operator-owned signal:** Report the saved declaration without reclassifying work or presenting model output as the decision.
- **The plan’s “## Step intent”, immediate confirmation:** Keep the change focused on the completion summary operators see after a new plan is written.
- **The plan’s “## Scope contract”, allowed behavior changes:** Limit user-visible changes to the completion confirmation and its README description; do not reorganize adjacent create behavior.
- **The plan’s “## Out of scope”, downstream consumers and silent acceptance:** Do not change tier consumption, non-TTY decision rules, existing-plan handling, split behavior, annotate, or scope-out flows.
