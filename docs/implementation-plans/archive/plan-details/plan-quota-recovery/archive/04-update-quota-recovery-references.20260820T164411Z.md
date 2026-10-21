> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Update quota recovery references for providers and operators

## Summary

Update the maintained recovery, provider-contract, architecture, and audit references to describe the quota behavior delivered by steps 1–3. The edits cover `README.md`, `RUNBOOK.md`, the recovery and audit flow documents, both provider contracts, and the backend-selection design. The key rule is that a confirmed Cursor monthly plan quota is terminal and keeps its reset as date-only context; `--on-rate-limit` remains the policy for ordinary short rate limits. On green, operators and maintainers see one consistent explanation of recovery, audit stopping, and unchanged fallback behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation sweep.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — The documentation conflict this step resolves.
- [Input](#input) — The shipped quota contracts from steps 1–3.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files and their scoped updates.
- [Implementation](#implementation) — Required terminology, policy, provider, and audit documentation changes.
- [Tests](#tests) — Upstream behavior evidence and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and consistency checks.
- [References](#references) — Provider and HTTP recovery guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this documentation-only step.
- [Deferred](#deferred) — Follow-up work outside the confirmed quota contract.

## Why

The current references describe usage and rate-limit failures as recoverable, while `docs/design-plans/BACKEND_SELECTION.md` also proposes quota failover. That conflicts with the shipped provider-scoped terminal quota from steps 1–3 and can lead an operator to expect a wait, prompt, switch, retry, or completed conceptual audit that will not occur.

## Input

- **Step 1 outcome:** use the landed provider-scoped quota evidence and date-only reset context from `plan_tool/backend.py:CliBackend` and `plan_tool/claude_errors.py:ClaudeFailure`. Read the landed Cursor descriptor rather than copying a proposed regex or inventing provider wording.

- **Step 2 outcome:** document the landed provider-specific plan-quota classification as a terminal recovery outcome. The recovery leaf stays provider-neutral; verify the exact symbols after the dependency steps land rather than treating future names as current anchors.

- **Step 3 outcome:** document the quota-stop result owned by `plan_tool/review.py:audit_plan_until_stable`, `plan_tool/cli/completeness_cmd.py:finalize_completeness_run`, and `plan_tool/cli/completeness_phases.py:_persist_and_present_report`: no later conceptual pass, unconfirmed coverage, and no reusable normal findings sidecar.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `README.md` — update `### Rate-limit recovery` and the `plan-tool completeness-audit <name>` description so operator-facing recovery distinguishes terminal plan quotas from ordinary policy-controlled rate limits.
  - `RUNBOOK.md` — update `### backend rate-limit choice`, the backend-selection summary, and `## Recovery: common failures` with a clear terminal-quota response.
  - `docs/ARCHITECTURE.md` — update `## Backend abstraction` and `## Rate-limit recovery loop` to describe provider-scoped evidence, terminal mapping, and the shared leaf boundary.
  - `docs/AUDIT_FLOW.md` — update `## TL;DR`, `## High-level flow`, `## completeness — conceptual audit`, coverage/persistence rules, and `## Source map` for the early quota stop.
  - `docs/CODEX_CLI_CONTRACT.md` — update `## Error shapes`, `## codex⇄claude mapping table`, the verification checklist, and `## References` to show that uncaptured Codex usage text remains ordinary rate-limit handling.
  - `docs/CURSOR_AGENT_CLI_CONTRACT.md` — update `## Error shapes` and `## Re-capture procedure` with Cursor’s confirmed monthly plan-quota contract.
  - `docs/RUN_FLOW.md` — update `## Rate-limit / transient recovery seam` and `## Source map` with the terminal path’s skipped recovery seams.
  - `docs/ROADMAP_DEMO_ORCHESTRATION.md` — update the rate-limiting failure-mode row so roadmap operators distinguish ordinary shared-budget backoff from a terminal plan quota.
  - `docs/design-plans/BACKEND_SELECTION.md` — update `## Why`, `### 5. Failover on quota limit`, and `## Verification` so future failover design excludes terminal plan quotas.
  - `DATA_CONTRACT.md` — update the completeness-audit JSON coverage contract with the explicit quota early-stop reason and its no-sidecar consequence.
  - `integrations/claude/SKILL.md` — qualify the generic rate-limit policy description so a confirmed terminal plan quota is not described as a wait, switch, stop, or prompt choice.
  - `integrations/codex/SKILL.md` — make the same terminal-plan-quota qualification for Codex-driving operators.

## Implementation

- **Foundational rule:** document one split everywhere: a confirmed Cursor monthly plan quota is terminal, while `ClaudeFailureKind.RATE_LIMIT` remains recoverable under the existing policy. Do not describe generic `usage limit` text as quota evidence.

- **Keep operator policy narrow.** In `README.md: ### Rate-limit recovery` and the matching `RUNBOOK.md` sections, state that wait, ask, switch, and stop are choices for ordinary short rate limits. Explain that a plan quota returns after the failed attempt, names any reset date without a time or timezone, and must be addressed outside the invocation before rerunning.

- **Give operators a distinct recovery path.** Add a focused entry under `RUNBOOK.md: ## Recovery: common failures` that tells readers not to expect a fallback backend or an interactive choice after the terminal quota result. Keep instructions limited to the surfaced outcome and the provider’s stated reset context; do not add account-management or spending guidance.

- **Document providers asymmetrically.** In `docs/CURSOR_AGENT_CLI_CONTRACT.md: ## Error shapes`, describe the confirmed Cursor-only evidence from step 1 and its terminal handling. In `docs/CODEX_CLI_CONTRACT.md: ## Error shapes` and `### Failure kinds (ClaudeFailureKind)`, state that no equivalent Codex plan-quota evidence is captured; broad Codex usage/rate-limit wording stays on the normal `RATE_LIMIT` path until provider-scoped evidence exists.

- **Preserve the recovery layering.** Update `docs/ARCHITECTURE.md: ## Rate-limit recovery loop` and `docs/RUN_FLOW.md: ## Rate-limit / transient recovery seam` to show that `plan_tool/claude_errors.py:build_classification` performs the typed mapping and that `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery` receives only neutral `AttemptCategory` values. A terminal plan quota must bypass the wait, sleep, prompt, fallback-selection, retry-guard, and re-invoke seams without adding provider logic to the leaf.

- **Describe the audit stop as incomplete, not converged.** In `docs/AUDIT_FLOW.md`, make the `audit_plan_until_stable` exception explicit: after a terminal quota outcome, the current invocation starts no later conceptual pass. Record actual attempted passes, unconfirmed coverage, and incomplete audit state; do not call the outcome dry, low-yield, budget-limited, or a successful pass-cap completion.

- **Keep persistence claims accurate.** Where `docs/AUDIT_FLOW.md` explains final reports and reusable evidence, retain the operator-readable Markdown report but carve out the quota-stopped case from normal reusable findings-sidecar claims. Point readers to the landed finalization and persistence symbols rather than duplicating internal implementation details.

- **Document the typed audit boundary.** In `docs/AUDIT_FLOW.md`, `DATA_CONTRACT.md`, and the CLI reference, state that the early stop is driven by a classified plan-quota outcome, never a response-text heuristic. Document `coverage.early_stop_reason: "plan_quota"` as incomplete and unconfirmed, distinct from a pass-cap `budget_limited` result; it is operator-visible JSON/report context, not reusable evidence.

- **Qualify packaged operator instructions.** In both integration skills, retain `--on-rate-limit` for ordinary short rate limits but add the explicit exception: a confirmed provider plan quota is terminal and returns after the failed attempt without applying that policy. Do not claim any special Codex detection until provider-scoped evidence exists.

- **Include roadmap operators.** In `docs/ROADMAP_DEMO_ORCHESTRATION.md: Failure modes to expect and film rather than hide`, split the current generic rate-limit row: ordinary shared-budget rate limiting keeps inherited backoff, while a confirmed terminal plan quota returns after the failed attempt and must be resolved outside that roadmap invocation. Do not add roadmap-specific recovery or concurrency behavior.

- **Correct the future failover design without expanding it.** In `docs/design-plans/BACKEND_SELECTION.md: ### 5. Failover on quota limit`, limit the proposed failover branch to recoverable short-rate-limit outcomes and explicitly exclude `PLAN_QUOTA`. Remove stale claims that a provider-limit outcome joins cooldown or fallback selection; retain the document’s design status and do not turn this documentation step into backend-policy work.

- **Sweep repeated wording before finishing.** Search all twelve declared files for `rate limit`, `usage limit`, `quota`, `retry`, `switch`, `wait`, `coverage unconfirmed`, and `budget limited`. Resolve every statement that could imply a terminal plan quota is recoverable or a quota stop is a pass-cap result, while leaving ordinary short-rate-limit and transient behavior unchanged.

## Tests

- `tests/test_claude_errors.py:test_classify_cursor_monthly_plan_quota_returns_plan_quota` — confirms the documented Cursor-specific classification and excludes generic usage-limit text.

- `tests/test_rate_limit_loop.py:test_terminal_plan_quota_bypasses_wait_prompt_switch_retry_and_guard` — confirms the recovery-flow claim that no recovery seam runs.

- `tests/test_review.py:test_plan_quota_stops_conceptual_audit_after_first_pass` — confirms the documented conceptual-pass boundary.

- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_writes_markdown_without_reusable_sidecar` — confirms the report and persistence distinction described in the audit references.
- `tests/cli/test_completeness_cmd.py:test_plan_quota_audit_json_names_early_stop_reason` — confirms the documented quota-stop JSON state differs from a budget-limited pass cap.

### Verification (non-code step)

1. **Symbol check** — use `rg` to confirm every code symbol cited in the changed documentation exists after steps 1–3 land.

2. **Provider check** — compare `docs/CURSOR_AGENT_CLI_CONTRACT.md` with `integrations/cursor/backend.json` and `plan_tool/claude_errors.py:classify`; confirm `docs/CODEX_CLI_CONTRACT.md` does not claim a special case without Codex-specific evidence.

3. **Policy check** — read the changed `README.md` and `RUNBOOK.md` recovery sections together; confirm they reserve wait, ask, switch, and retry for ordinary short rate limits.

4. **Audit check** — read `docs/AUDIT_FLOW.md` against `plan_tool/review.py:audit_plan_until_stable` and `plan_tool/cli/completeness_phases.py:_persist_and_present_report`; confirm the quota result is early, incomplete, and non-reusable.

5. **Integration, roadmap, and contract check** — read `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`, `docs/ROADMAP_DEMO_ORCHESTRATION.md`, and `DATA_CONTRACT.md` with the changed audit reference; confirm ordinary rate-limit policy is not extended to plan quota, the roadmap row has the same exception, the early-stop JSON field is accurate, and no sidecar claim remains absolute.

6. **Link check** — follow every changed relative Markdown link and heading anchor in the twelve documentation files.

7. **Regression check** — run `uv run pytest tests/ -q -n auto` after the dependency-step tests and documentation edits are present.

## Acceptance criteria

- Every declared documentation file distinguishes a confirmed plan quota from an ordinary short rate limit where it discusses recovery or failure classification.

- `README.md` and `RUNBOOK.md` tell operators that a plan quota does not wait, prompt, switch backends, or retry, and show any provider reset only as date-only context.

- `docs/CURSOR_AGENT_CLI_CONTRACT.md` documents the confirmed Cursor-specific condition, while `docs/CODEX_CLI_CONTRACT.md` keeps uncaptured Codex usage-limit wording on the normal recoverable path.

- `docs/ARCHITECTURE.md` and `docs/RUN_FLOW.md` preserve the provider-neutral `AttemptCategory.TERMINAL` boundary and name the recovery seams a plan quota bypasses.

- `docs/AUDIT_FLOW.md` states that a terminal quota stops later conceptual passes in the current invocation, leaves coverage unconfirmed, and does not create normal reusable findings evidence.

- `DATA_CONTRACT.md`, `integrations/claude/SKILL.md`, and `integrations/codex/SKILL.md` distinguish a classified terminal quota from ordinary policy-controlled rate limits; the JSON contract calls the former `early_stop_reason: "plan_quota"`, not `budget_limited`.

- `docs/ROADMAP_DEMO_ORCHESTRATION.md` reserves inherited backoff for ordinary shared-budget rate limits and gives confirmed plan quotas the same terminal exception.

- `docs/design-plans/BACKEND_SELECTION.md` does not propose waiting, cooldown tracking, or backend failover for `PLAN_QUOTA`.

- The named upstream tests and `uv run pytest tests/ -q -n auto` pass, and all changed Markdown links resolve.

## References

- [Models & Pricing | Cursor Docs](https://cursor.com/docs/models-and-pricing#usage-pools) — Confirm the operator-facing description of monthly usage pools and reset timing.

- [Output format | Cursor Docs](https://cursor.com/docs/cli/reference/output-format) — Confirm how terminal Cursor CLI errors reach batch and streaming callers.

- [RFC 6585 — 429 Too Many Requests](https://www.rfc-editor.org/rfc/rfc6585.html#section-4) — Keep ordinary rate-limit behavior distinct from the terminal provider-specific quota.

- [RFC 9110 — Retry-After](https://www.rfc-editor.org/rfc/rfc9110.html#section-10.2.3) — Preserve the existing short-limit retry guidance without applying it to date-only plan quotas.

## Applicable guardrails

- **The plan’s “## Step intent”, documentation alignment:** update descriptions only; use the landed behavior from steps 1–3 as the source of truth.

- **The plan’s “## Out of scope”, unchanged short-limit behavior:** do not document a changed wait, switch, prompt, transient-retry, or fallback policy for ordinary rate limits.

- **The plan’s “## Risks”, false special case and misleading recovery:** keep the special case provider-scoped, keep generic usage-limit text ordinary, and never turn a reset date into a claimed reset time.

## Deferred

- Uncaptured plan-quota wording from Codex or another provider — wait for provider-scoped evidence before documenting another terminal classification.

- Account, credential, spend-limit, and quota-forecast operations — remain outside this recovery-reference update.

- New backend failover policy or durable quota coordination — remain separate design and implementation work.
