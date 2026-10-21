> **Replaced**: this file has been superseded by `docs/implementation-plans/2-orchestrator-owned-convergence-eval.md`.
> Preserved here for history; do not edit.

## Overview

Add one non-mutating `plan-tool convergence-eval` command that gives developers and orchestrators a shared, evidence-bound convergence outlook across plan audits, code reconciliation, local code review, and pull-request review. It replaces the public `plan-tool convergence` verdict while retaining deterministic history, fingerprints, finding identities, detail coverage, qualification, and evidence-ledger assembly as labeled inputs. Each invocation returns one allowed advisory outlook or an evidence-bound refusal without changing its subject. The combined source remains at `plan-seeds/archive/orchestrator-owned-convergence-eval.combined.replaced.md`.

## Problem statement

The existing `plan-tool convergence` command turns useful mechanical history into a convergence verdict, but that evidence cannot by itself determine whether work should continue, finish its current correction, be redesigned, or proceed. Developers and orchestrators also lack one identity-bound outlook spanning plan-level and detail-grounded audits, plan-canonical code reconciliation, local review, and pull-request review.

Without current-input validation, qualification, stable identities, dispositions, checks, intervening changes, and an explicit premise check, a judge can sound authoritative about stale or incomparable evidence. The replacement must preserve useful calculations from `plan_tool/cli/convergence_cmd.py` and `plan_tool/convergence_diagnosis.py` while making them evidence for a read-only judged decision rather than a competing mechanical answer such as `converging`.

## Architecture

The evaluator follows the deterministic-chassis design. A context adapter validates required current inputs and assembles one immutable, identity-bound evidence envelope; explicit context selection wins, while mixed, stale, or ambiguous evidence refuses before a model call. The supported adapters remain context-specific: `plan-audit` uses the current plan, selected-grade detail coverage, completed audit snapshots, dispositions, and qualification; `code-reconcile` uses the authoritative plan, current code identity, saved reconcile snapshots, changed files, tests, and redirects; `code-review` uses a pinned merge-base/head range, tracked ledger, checks, intervening changes, and settled decisions; and `pull-request-review` adds PR findings materialized in that ledger.

A single directed judge receives the stated intent, settled decisions, qualified completed snapshots, stable finding identities and severities, dispositions, intervening changes, tests, and current subject identity. It checks premise validity before deciding how findings should close. Deterministic response gates require exactly one allowed outlook, resolvable evidence references, coverage of every current material finding, and an explanation of the next orchestration action; they validate binding and response shape rather than the semantic correctness or prose quality of the judgment.

Plan bundle state stays separate from evaluation basis. `plan-only` means 0 of N detail files and requires `plan-level`; `partial-detail` means 1 through N-1 and also requires `plan-level`; only `detail-complete` at N of N permits `detail-grounded`. Code reconciliation uses `code-grounded`, while local and pull-request review use `review-grounded`.

Outlooks are selected in precedence order: `insufficient-evidence` when current comparable evidence is absent, stale, unqualified, or incomplete; `redesign-or-rescope` when the premise fails, a material structural finding recurs without narrowing, or the remedy exceeds authority; `finish-current-fix` when the remaining material work is the bounded tail of the last accepted correction; `continue` when material in-scope findings remain but are narrowing or becoming less severe; and `converged` when current qualified evidence meets the applicable clean or low-yield rule.

The backend runs in a supported read-only mode, and the command compares subject identity before and after the judged call. The first release is ephemeral: it writes the existing observability run log but creates no durable outlook record. The rendered result remains advisory, leaving application, scope, execution, and merge decisions to the developer and orchestration conversation.

## Out of scope

- The evaluator is advisory. It does not apply a finding, select scope,
  invoke a structural remedy, advance a step, run/export a plan, alter a
  command's success exit code from an outlook, modify CI, or merge a PR.
- Gates may validate input identities, allowed vocabulary, evidence-envelope
  completeness, current material-finding coverage, and cited anchors. They
  may not judge prose quality, artifact shape, a finding's triviality, or the
  semantic correctness of the judged conclusion.
- Missing required evidence forces `insufficient-evidence` before a judged
  call can certify any substantive outlook. A partial detail bundle never
  receives a detail-grounded claim.
- No provider integration, credential, remote query, evaluator-independence
  policy, or CI gate belongs here. The tracked ledger is the only review input.
- Retiring `completeness-apply`, `direct-run`, `direct-jira`, or their private
  helpers is explicitly deferred. Existing completeness findings, report
  annotations, direct pipelines, and unrelated `apply_finding` callers retain
  their current contracts during this effort.
- Keep the change narrow: extract only the evidence and response seams the
  evaluator needs. Do not add a generic judgment framework or rewrite saved
  report readers.

## Risks

- A judge can sound authoritative on stale or incomparable evidence. Adapter
  identity checks, qualification, and `insufficient-evidence` precedence are
  load-bearing.
- A generic schema can erase meaningful differences among plan, code, and
  review contexts. Each adapter owns required evidence; only the outlook
  vocabulary is shared.
- A model-generated evaluation can amplify model-generated audit bias. It must
  receive intent, settled decisions, dispositions, tests, intervening changes,
  and an explicit premise check.
- A read-only claim is insufficient if the backend can still edit the subject.
  The invocation mode and before/after identity comparison must both be tested.
- A new review-ledger parser could make current handoffs unreadable. Accept
  established ledger forms or refuse with a clear missing-evidence outcome;
  never rewrite an existing ledger as a side effect of evaluation.
- Mechanical history can be valuable evidence but cannot remain a competing
  verdict. Keep it labeled and ensure the old command surface no longer emits
  `converging` as the answer.

## Testing

- Freeze a self-contained corpus from saved histories and tracked review
  ledgers, including its sample count and interpretation rule. Test the safety
  failure and record real-model variance without pinning subjective outcomes.
- Use hermetic invokers for every context and outlook. Assert deterministic
  evidence construction for identical inputs; no unit test invokes a backend.
- Prove plan-audit bundle-state boundaries at 0/N, partial, and N/N coverage,
  including that only N/N can claim `detail-grounded`.
- Prove stale/mixed/missing plan, code, range, ledger, disposition,
  qualification, and budget evidence refuses before the judge can return a
  substantive outlook.
- Prove unknown/multiple outlooks, omitted material findings, unresolved
  citations, mismatched subject identities, or missing next actions retry or
  refuse without mutation.
- Prove the evaluator runs in the supported read-only backend mode; a judged
  call that changes the subject returns a refusal and does not publish a
  successful result.
- Prove the old command and mechanical verdict are absent, generated CLI
  reference stays current, legacy audit/reconcile reports remain readable, and
  current `completeness-apply`, `direct-run`, and `direct-jira` behavior stays
  unchanged.
- Run focused evaluator, review-ledger, convergence, completeness, reconcile,
  and CLI-reference tests, then the full suite.

## Acceptance criteria

- `plan-tool convergence-eval` is the only public convergence answer and
  returns one valid outlook or an evidence-bound refusal without changing the
  subject.
- Every plan-audit evaluation renders `bundle_state`, exact `N of M` coverage,
  and `evaluation_basis`; `plan-only` and `partial-detail` never claim detail
  grounding.
- Code reconciliation, local review, and pull-request review each provide
  their own identity-bound adapter rather than relying on inferred remote
  state or a flattened generic context.
- Valid replies cite current evidence, cover all current material findings,
  explain their next orchestration action, and use exactly one allowed outlook.
- Read-only invocation and before/after subject identity checks prevent the
  evaluator from silently modifying plan, detail, code, report, ledger, or
  disposition state.
- Legacy reports remain readable, current apply/direct pipeline behavior stays
  unchanged, and all current guidance describes the evaluator as advisory.
- The corpus, focused tests, generated CLI reference tests, and full suite
  pass.

## Deferred

- Retire `completeness-apply`, direct pipelines, their recommendations, and
  their hidden consumers after the evaluator ships and its evidence informs
  the migration.
- Decide evaluator independence, durable evaluation records, provider
  integration, and whether an outlook can become a remote or CI gate only
  after real review evidence exists.
- Evaluate other `apply_finding` callers in `create`, `detail`, generic review,
  and reconcile as separately scoped work.

## Input

- Replace `plan-tool convergence` with `plan-tool convergence-eval`; no second
  public convergence verdict remains. Useful deterministic history,
  fingerprints, finding identities, detail coverage, qualification, and
  evidence-ledger assembly become evaluator inputs rather than a conclusion.

- Define a tracked, read-only review-ledger format sufficient to bind a
  merge-base/head range, findings and dispositions, checks, intervening
  changes, and settled decisions. Existing ledgers remain readable and do not
  require a rewrite.

| Context | Required evidence | Basis and handoff |
| --- | --- | --- |
| `plan-audit` | Current plan, selected-grade detail coverage, completed audit snapshots, dispositions, and qualification | `plan-level` for `plan-only` / `partial-detail`; `detail-grounded` only for `detail-complete`. Hand off to plan correction/detail work or execution readiness. |
| `code-reconcile` | Authoritative plan, current code identity, saved reconcile snapshots, changed files, tests, and redirects | `code-grounded`. Hand off to bounded code correction, a plan-side redirect, or review. |
| `code-review` | Pinned merge-base/head range, tracked ledger, checks, intervening changes, and settled decisions | `review-grounded`. Hand off to another local correction/review round or PR review. |
| `pull-request-review` | The same pinned range plus PR findings materialized in the tracked review ledger | `review-grounded`. Hand off to correction/review or the developer's merge decision. |

## Scope guardrails

- For one accepted current envelope, emit one schema-valid evaluation or refuse;
  the subject remains byte-identical in either case.
- The evaluator is advisory. It does not apply a finding, select scope,
  invoke a structural remedy, advance a step, run/export a plan, alter a
  command's success exit code from an outlook, modify CI, or merge a PR.
- Gates may validate input identities, allowed vocabulary, evidence-envelope
  completeness, current material-finding coverage, and cited anchors. They
  may not judge prose quality, artifact shape, a finding's triviality, or the
  semantic correctness of the judged conclusion.
- Missing required evidence forces `insufficient-evidence` before a judged
  call can certify any substantive outlook. A partial detail bundle never
  receives a detail-grounded claim.
- No provider integration, credential, remote query, evaluator-independence
  policy, or CI gate belongs here. The tracked ledger is the only review input.
- Retiring `completeness-apply`, `direct-run`, `direct-jira`, or their private
  helpers is explicitly deferred. Existing completeness findings, report
  annotations, direct pipelines, and unrelated `apply_finding` callers retain
  their current contracts during this effort.
- Keep the change narrow: extract only the evidence and response seams the
  evaluator needs. Do not add a generic judgment framework or rewrite saved
  report readers.
