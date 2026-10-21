# Run-grade plan-audit convergence-eval v1

## Outcome

`plan-tool convergence-eval` gives a developer one non-mutating,
evidence-bound advisory outlook for an explicitly selected final run-grade
plan-audit report. It replaces the public mechanical convergence verdict but
does not apply findings, alter plan scope, or replace developer judgment.

## In scope

- One required `plan-audit` context with a required plan name and a
  root-contained final run-grade audit-report id. Zero or multiple plan matches
  are usage errors before the command reads a report.
- Current artifact admission only: the selected report's canonical-plan digest
  and run-grade detail-bundle revision must match the canonical plan and bundle
  when the in-memory envelope is built.
- Current final material findings, qualification, closed refusal conditions,
  deterministic eligibility for `converged` and `continue`, set-equal finding
  coverage, envelope-resolved citations, and only the fixed
  `review-selected-report` action with the exact material-finding set.
- One isolated, fixed, read-only `gpt-5.6-terra` judgment with no retry,
  fallback, model override, evaluator log, telemetry event, cache, sidecar, or
  other repository artifact.
- Replacement of the public mechanical command and its dead telemetry writer,
  including command order, continuation guidance, sibling references, and
  focused tests, after dated supersession of the unimplemented arm-clustering
  plan.
- Forward-looking docs and explicit, developer-pickup backlog handoffs.

## Scope guardrails

- The evaluator remains advisory and ephemeral. It never applies a finding,
  progresses a pipeline, creates a decision record, or decides scope.
- Explicit selectors are mandatory. Missing, stale, ambiguous, incompatible,
  malformed, escaped, non-final, or non-run-grade evidence refuses; the command
  never substitutes a newest report or plan.
- The source plan and selected run-grade bundle are canonical for the one
  report-to-artifact binding. The command makes no live-code, project-profile,
  source-seed, or other external-subject currentness claim.
- The evaluator accepts only an outcome the admitted envelope makes eligible.
  It never infers history, a redesign route, a premise verdict, or scope change
  from a finding's prose or severity.
- Its only action field is the envelope-bound `review-selected-report` object;
  it has no free-text action or model-authored command form.
- Preserve current completeness application and direct-pipeline behavior.

## Out of scope

- Jira-grade evidence, a grade-neutral reader, or report conversion.
- Audit histories, trajectory/recurrence logic, finish-current-fix, and
  redesign-or-rescope outcomes.
- Audit-produced premise or scope evidence, report-schema changes, or
  evaluator-directed scope decisions.
- Live code, project profile, source seed, configuration, or invocation-state
  admission.
- Persistent evaluator outlooks, logs, telemetry, provider integration, or CI
  authority.
- A free-text or multi-form action recommendation.
- Code-reconcile, local-review, and pull-request-review adapters.
- Retiring `completeness-apply`, `direct-run`, `direct-jira`, or other
  `apply_finding` callers.

## Deferred handoffs

- BACKLOG #367: evidence-gated application/direct-pipeline migration.
- BACKLOG #368: governance only after representative first-release evidence.
- BACKLOG #369: inventory other application authorities.
- BACKLOG #370: code-reconcile adapter.
- BACKLOG #371: local-review adapter and noncircular ledger publication.
- BACKLOG #372: pull-request-review adapter after #371.
- BACKLOG #373: any later live-subject admission or invocation-observation
  model.
- BACKLOG #374: historical or redesign-oriented outcomes and their evidence
  model.
- BACKLOG #375: any later Jira-grade evaluator decision and reader contract.
