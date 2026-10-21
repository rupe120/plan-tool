> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Update quota recovery references for providers and operators

## Summary

Update the recovery, audit, provider-contract, and operator-facing documentation to describe the terminal monthly plan-quota outcome delivered by steps 1–3. The primary edits are in `README.md`, `RUNBOOK.md`, `docs/how-to/pipeline/audit.md`, `DATA_CONTRACT.md`, and the backend contract and skill documents. Keep one clear distinction throughout: the confirmed Cursor plan quota stops the current call or conceptual audit, while ordinary short rate limits retain the existing policy-driven recovery behavior. On green, every maintained reference gives operators the same next step and does not promise a wait, prompt, switch, retry, reusable audit result, or confirmed coverage where none exists.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation sweep.
- [Table of Contents](#table-of-contents) — Navigation for this detail file.
- [Why](#why) — The current wording treats different provider limits as one recoverable case.
- [Input](#input) — Upstream quota and audit outcomes that the documentation must reflect.
- [Files (creates vs edits)](#files-creates-vs-edits) — Every documentation surface updated by this step.
- [Implementation](#implementation) — Required wording, ownership boundaries, and consistency rules.
- [Tests](#tests) — Non-code verification for accuracy and reference consistency.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation outcomes.
- [References](#references) — Provider and protocol sources behind the operator guidance.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this to an accurate documentation sweep.
- [Deferred](#deferred) — Follow-up work outside the documentation change.

## Why

The current recovery references describe rate and usage limits as policy-controlled cases that can wait, prompt, switch backends, or retry. Steps 1–3 introduce a narrower, provider-confirmed monthly plan quota that is terminal for the current backend call and ends conceptual sampling with unconfirmed coverage. Leaving the existing broad wording in place would send operators toward actions that do not run and would make an incomplete audit look reusable or converged.

## Input

- **Step 1 outcome:** use the landed provider-scoped evidence and date context from `plan_tool/claude_errors.py:classify` and `integrations/cursor/backend.json`. Document only the confirmed Cursor signal; do not turn generic provider wording into a plan quota.

- **Step 2 outcome:** read the landed terminal failure member in `plan_tool/claude_errors.py:ClaudeFailureKind` and its mapping into the recovery loop’s existing terminal category. The code decides the exact identifier and user hint; the documentation must describe its observable effect without treating a future enum member as a current input anchor.

- **Step 3 outcome:** read the landed behavior in `plan_tool/review.py:audit_plan_until_stable`, `plan_tool/cli/completeness_cmd.py:finalize_completeness_run`, and `plan_tool/review_persistence.py:normalize_audit_coverage`. Use the actual coverage field and final-sidecar rule from those landed changes rather than inventing a parallel name in prose.

- **Documentation source of truth:** when a sibling detail file and landed code disagree, document the landed code. This step writes only the declared documentation files; it does not adjust the recovery or audit implementation.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `README.md` — qualify `### Rate-limit recovery` so the policy actions apply to ordinary short rate limits and add the terminal monthly plan-quota operator result.
  - `RUNBOOK.md` — add a recovery entry for the terminal plan-quota message and qualify `### backend rate-limit choice` and the backend quick reference.
  - `docs/ARCHITECTURE.md` — update `## Rate-limit recovery loop` to show that the provider-specific terminal result maps into the existing neutral terminal branch and has an audit-local consumer.
  - `docs/how-to/pipeline/audit.md` — document the early conceptual-audit stop, unconfirmed coverage, Markdown-report retention, and withheld ordinary final findings sidecar; update `## Source map` for the responsible symbols.
  - `docs/reference/contracts/codex-cli.md` — update `## Error shapes`, `### Failure kinds (\`ClaudeFailureKind\`)`, and `## References` so the table covers the new terminal kind without claiming Codex has a confirmed provider-specific signal.
  - `docs/reference/contracts/cursor-agent-cli.md` — extend `## Error shapes` with the confirmed Cursor monthly plan-quota shape, its date-only context, and its terminal handling.
  - `docs/how-to/pipeline/run.md` — qualify `## Rate-limit / transient recovery seam` and its source map: a terminal plan quota performs one attempt and does not enter any recovery seam.
  - `docs/how-to/roadmap-demo.md` — split the generic rate-limiting failure-mode row and add a clear early-stop branch to the Phase 5 and Phase 6 completeness-audit instructions.
  - `docs/design-plans/BACKEND_SELECTION.md` — correct `## Why` and `### 5. Failover on quota limit (shared helper + both retry loops)` so the future failover design does not claim terminal monthly plan quotas are eligible for automatic failover.
  - `DATA_CONTRACT.md` — extend the `completeness-audit --json` coverage contract with step 3’s explicit early quota-stop state and sidecar consequence.
  - `integrations/claude/SKILL.md` — qualify the `## Backend` recovery guidance for agents driving a Cursor-backed command.
  - `integrations/codex/SKILL.md` — keep the Codex-specific guidance accurate while explaining that the registered Cursor plan-quota result is outside normal rate-limit policy actions.
  - `plan_tool/cli/parser.py` — qualify the public `--on-rate-limit` and `--fallback-backend` help so their actions apply only to ordinary recoverable short rate limits.
  - `tests/cli/package_surface_help.golden.txt` — update the public-help snapshot for the intentional parser-help change.

## Implementation

- **Use one behavior split everywhere.** Describe ordinary short rate limits as the only inputs to `--on-rate-limit wait|switch|stop|ask`. Describe the confirmed Cursor monthly plan quota as a terminal result: the current call returns after its first failed attempt and does not wait, prompt, choose a fallback backend, sleep for backoff, consult the retry guard, or retry.

- **Make the global CLI help equally precise.** In `plan_tool/cli/parser.py`, say that `--on-rate-limit` chooses an action for an ordinary recoverable rate limit and that a confirmed terminal plan quota bypasses those actions. Describe `--fallback-backend` as retrying an ordinary rate-limited call only. Preserve flag names, choices, precedence, defaults, and validation; update `tests/cli/package_surface_help.golden.txt` through its existing snapshot test.

- **Keep provider evidence narrow.** In `docs/reference/contracts/cursor-agent-cli.md:## Error shapes`, record the exact confirmed provider wording and date context from the landed Cursor manifest and classifier. In `docs/reference/contracts/codex-cli.md:## Error shapes` and `### Failure kinds (\`ClaudeFailureKind\`)`, say that Codex’s broad usage-limit wording remains on its existing path unless separately confirmed; do not imply that the Cursor detector applies to Codex or Claude.

- **Preserve date meaning.** Explain in `README.md:### Rate-limit recovery`, `RUNBOOK.md:## Recovery: common failures`, and `docs/reference/contracts/cursor-agent-cli.md:## Error shapes` that the provider’s displayed reset is a calendar date, not a local reset time or a timer target. Tell operators to address the provider quota or wait for the provider’s actual reset, then begin a new command invocation.

- **Keep recovery architecture provider-neutral.** In `docs/ARCHITECTURE.md:## Rate-limit recovery loop` and `docs/how-to/pipeline/run.md:## Rate-limit / transient recovery seam`, anchor the explanation on `plan_tool/claude_errors.py:KIND_TO_CATEGORY` and `plan_tool/rate_limit_loop.py:run_with_rate_limit_recovery`. The recovery leaf remains neutral: the provider-specific classification maps to `AttemptCategory.TERMINAL`; it does not gain a provider branch or a new recovery action.

- **Document audit scope precisely.** In `docs/how-to/pipeline/audit.md` and `DATA_CONTRACT.md`, explain that `plan_tool/review.py:audit_plan_until_stable` stops later conceptual passes only after the typed terminal quota result. State that the result records the actual attempted-pass count and configured cap, is unconfirmed for coverage, is not a pass-cap budget stop, cannot qualify as reusable evidence, and cannot produce a clean qualified result.

- **Separate readable evidence from reusable evidence.** Document the behavior implemented through `plan_tool/cli/completeness_phases.py:_persist_and_present_report`: a non-JSON quota-stopped audit still leaves an operator-readable Markdown report, but it does not write the ordinary final reusable findings sidecar. Do not describe the missing sidecar as a lost report or as a general rule for all failed audits.

- **Keep the demo instructions honest.** In `docs/how-to/roadmap-demo.md:Failure modes to expect and film rather than hide`, split the generic rate-limiting row: ordinary shared-budget rate limits keep inherited backoff, while a confirmed plan quota returns after the failed attempt and needs provider recovery before a new command. In `### Phase 5 — audit the bare plan, before detail` and `### Phase 6 — \`detail\``, add the matching explicit branch for the quota-stopped report. The demo must record its unconfirmed result, avoid treating it as a completed gate, resolve the provider condition, and rerun the audit as a fresh invocation before continuing.

- **Correct the future failover design without expanding it.** In `docs/design-plans/BACKEND_SELECTION.md:### 5. Failover on quota limit (shared helper + both retry loops)`, limit automatic failover claims to recoverable short-rate-limit behavior. Make the terminal plan-quota exclusion explicit, but do not redesign that future feature or add a new fallback policy.

- **Keep agent guidance concise and headless-safe.** Update the backend paragraphs in `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` so an agent does not expect closed stdin, `-y`, or an `--on-rate-limit` setting to recover a confirmed terminal plan quota. Point to `README.md:## Backends` or `RUNBOOK.md:## Recovery: common failures` for the operator procedure instead of duplicating it.

- **Preserve existing short-limit documentation.** Retain the documented precedence, fallback scope, and interactive behavior for short rate limits. A documentation change that makes `wait`, `switch`, `stop`, or `ask` sound unavailable generally is incorrect.

## Tests

### Verification (non-code step)

This is a non-code step. The test-authoring gate does not apply because the step changes documentation only; use these checks instead.

1. `tests/test_data_contract.py` — run the existing data-contract drift guard after updating `DATA_CONTRACT.md` so the documented coverage shape matches the landed persisted contract.

2. `README.md:### Rate-limit recovery`, `RUNBOOK.md:### backend rate-limit choice`, `docs/how-to/pipeline/run.md:## Rate-limit / transient recovery seam`, both integration skills, and the global `plan-tool --help` text — verify that ordinary short limits retain the same four policy actions while a confirmed plan quota names none of them.

3. `docs/reference/contracts/cursor-agent-cli.md:## Error shapes` and `docs/reference/contracts/codex-cli.md:### Failure kinds (\`ClaudeFailureKind\`)` — verify that the provider-specific signal is Cursor-only and that the failure-kind table still accounts for every landed member.

4. `docs/how-to/pipeline/audit.md` and `DATA_CONTRACT.md` — verify that the early quota stop names the actual coverage field, marks coverage unconfirmed, distinguishes it from `budget_limited`, and says no ordinary final reusable sidecar is written.

5. `docs/how-to/roadmap-demo.md:Failure modes to expect and film rather than hide`, `### Phase 5 — audit the bare plan, before detail`, and `### Phase 6 — \`detail\`` — verify that inherited backoff remains limited to ordinary shared-budget rate limits and the demo stops for a fresh rerun after plan-quota provider recovery rather than continuing from the incomplete audit.

6. `docs/ARCHITECTURE.md`, `docs/how-to/pipeline/run.md`, and `docs/design-plans/BACKEND_SELECTION.md` — verify that all three describe the terminal branch consistently and do not assign provider-specific logic to `plan_tool/rate_limit_loop.py`.

7. All changed Markdown links and heading anchors — verify that existing internal links still resolve after any heading edit.

8. `tests/cli/test_package_surface.py` — run the existing global-help snapshot test after updating `tests/cli/package_surface_help.golden.txt`.

9. `rg -n 'plan quota|plan-quota|monthly.*quota|quota' README.md RUNBOOK.md docs/ARCHITECTURE.md docs/how-to/pipeline/audit.md docs/reference/contracts/codex-cli.md docs/reference/contracts/cursor-agent-cli.md docs/how-to/pipeline/run.md docs/how-to/roadmap-demo.md docs/design-plans/BACKEND_SELECTION.md DATA_CONTRACT.md integrations/claude/SKILL.md integrations/codex/SKILL.md plan_tool/cli/parser.py` — review every remaining quota reference for the same short-limit versus terminal-plan-quota split.

## Acceptance criteria

- `README.md` and `RUNBOOK.md` tell operators that a confirmed Cursor monthly plan quota ends the current call and must be resolved before a new invocation.

- The ordinary `--on-rate-limit` policy remains documented as short-rate-limit behavior, with its existing precedence and action meanings unchanged.

- Global `plan-tool --help` says that `--on-rate-limit` and `--fallback-backend` apply to ordinary recoverable rate limits, while a confirmed terminal plan quota bypasses those actions.

- `docs/reference/contracts/cursor-agent-cli.md` records the landed Cursor-specific terminal condition and date context, while `docs/reference/contracts/codex-cli.md` does not claim unsupported Codex detection.

- `docs/ARCHITECTURE.md` and `docs/how-to/pipeline/run.md` state that provider classification maps into the existing terminal recovery category without changing the stdlib-only leaf’s responsibilities.

- `docs/how-to/pipeline/audit.md` and `DATA_CONTRACT.md` state that a terminal plan quota stops later conceptual passes, leaves coverage unconfirmed, records the real stop reason, and does not write the ordinary final reusable findings sidecar.

- `docs/how-to/roadmap-demo.md` reserves inherited backoff for ordinary shared-budget rate limits and does not direct the demo to apply, reuse, or treat a quota-stopped audit as complete.

- `docs/design-plans/BACKEND_SELECTION.md` excludes the terminal plan-quota result from its proposed automatic-failover path.

- `tests/test_data_contract.py` passes, and the documentation sweep contains no contradictory recovery instruction.

## References

- [Models & Pricing | Cursor Docshttps: — Confirm the monthly usage-pool and billing-cycle language used in operator guidance.

- [Output format | Cursor Docshttps: — Confirm where Cursor CLI failure output appears when documenting the provider contract.

- [Cursor Python SDK — Errorshttps: — Use the retryability distinction to keep monthly quota guidance separate from short retry windows.

- [RFC 6585 — 429 Too Many Requestshttps: — Use the standard short-rate-limit meaning as the contrast for the existing recovery policy.

- [RFC 9110 — Retry-Afterhttps: — Confirm that a retry delay is not implied by a provider-supplied calendar date.

## Applicable guardrails

- **The plan’s “## Plan intent”, distinct quota outcome:** keep the documentation centered on the difference between the confirmed monthly plan quota and ordinary short rate limits.

- **The plan’s “## Step intent”, maintained descriptions:** update every declared provider, operator, flow, architecture, and data-contract reference that describes this behavior.

- **The plan’s “## Out of scope”, recovery-policy boundaries:** do not turn this reference sweep into a new fallback, account-management, quota-state, or cross-command behavior proposal.

- **The plan’s “## Out of scope”, unchanged short-limit behavior:** preserve the existing short-rate-limit and transient-recovery contract in every document.

- **The plan’s “## Out of scope”, audit behavior:** describe only the audit-local terminal stop delivered by step 3; do not claim a new scheduler, timeout policy, or external-provider test.

## Deferred

- Additional provider-specific plan-quota signatures — require confirmed provider evidence and a separate planned change; do not broaden this documentation to generic usage-limit wording.

- Automatic failover policy for terminal plan quotas — keep it outside this documentation-only step and outside the existing short-rate-limit design proposal.
