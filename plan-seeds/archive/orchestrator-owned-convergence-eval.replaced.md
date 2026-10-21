> **Replaced**: this file has been superseded by `docs/implementation-plans/2-orchestrator-owned-convergence-eval.md`.
> Preserved here for history; do not edit.

# Seed: add `convergence-eval`

## Outcome

Add one non-mutating `plan-tool convergence-eval` command that gives the
orchestrator and developer a shared, evidence-bound convergence outlook across
plan audits, code reconciliation, local code review, and pull-request review.
It replaces the current mechanical `plan-tool convergence` verdict while
preserving its useful saved-history calculations as labeled evidence.

`completeness-apply`, `direct-run`, and `direct-jira` remain supported during
this effort. Their retirement follows after the evaluator has shipped and has
been used to assess that migration. The combined pre-split seed is retained at
`plan-seeds/archive/orchestrator-owned-convergence-eval.combined.replaced.md`.

## In scope

- Replace `plan-tool convergence` with `plan-tool convergence-eval`; no second
  public convergence verdict remains. Useful deterministic history,
  fingerprints, finding identities, detail coverage, qualification, and
  evidence-ledger assembly become evaluator inputs rather than a conclusion.
- Support the contexts that developers orchestrate: plan-level completeness
  audit, detail-grounded completeness audit, plan-canonical code
  reconciliation, local code review, and pull-request review.
- Assemble one deterministic, current, identity-bound evidence envelope before
  a single directed judged call. The evaluator reads tracked review-ledger
  evidence and never fetches a provider.
- Keep plan bundle state separate from evaluation basis. Plan audit emits
  `plan-only` (0 of N details), `partial-detail` (1 through N-1), or
  `detail-complete` (N of N), alongside `plan-level` or `detail-grounded`.
- Return exactly one closed outlook: `insufficient-evidence`,
  `redesign-or-rescope`, `finish-current-fix`, `continue`, or `converged`.
  Render a concise explanation, the cited evidence, and the next orchestration
  action.
- Define a tracked, read-only review-ledger format sufficient to bind a
  merge-base/head range, findings and dispositions, checks, intervening
  changes, and settled decisions. Existing ledgers remain readable and do not
  require a rewrite.
- Enforce a read-only evaluator backend mode and compare the subject identity
  before and after the judged call. The command returns an accepted bound
  evaluation or a refusal; it never mutates the plan, detail bundle, code,
  source reports, review ledger, finding dispositions, execution state, or
  scope.
- Add an immutable, self-contained evaluation corpus before prompt tuning.
  It records case count and the interpretation rule derived from current saved
  histories and review ledgers. Real-model trials record variance; only a
  `converged` result for evidence with a current material open finding is a
  safety failure.
- Update the evaluator's CLI reference, capability catalog, data and review
  contracts, developer workflow, shared directives, integrations, and tests.
  Documentation describes the evaluator as advisory evidence; it does not
  imply that current apply or direct-pipeline commands have been retired.

## Architecture

The evaluator follows the repository's deterministic-chassis design:

1. A context adapter validates required current inputs and builds one immutable
   envelope. Explicit context selection wins; mixed, stale, or ambiguous
   evidence refuses before any model call.
2. A single judge sees the work's stated intent, settled decisions, qualified
   completed snapshots, stable finding identities and severities,
   dispositions, intervening changes, test evidence, and the current subject
   identity. It checks premise validity before asking how to close findings.
3. Deterministic response gates require one allowed outlook, resolvable
   evidence references, coverage of every current material finding, and an
   explanation of the next orchestration action. They validate binding and
   shape, not philosophical correctness.
4. The evaluator renders an advisory result. The developer and orchestration
   conversation decide whether to apply work, change scope, execute a plan, or
   merge a pull request.

The command is ephemeral for its first release. It writes the existing
observability run log but creates no durable outlook record, so this effort
does not add a new persisted data contract or recovery writer. A later
evidence-backed decision may add an append-only record with a versioned
compatibility and interrupted-write contract.

Each context owns its evidence rather than flattening it into a generic
workflow framework:

| Context | Required evidence | Basis and handoff |
| --- | --- | --- |
| `plan-audit` | Current plan, selected-grade detail coverage, completed audit snapshots, dispositions, and qualification | `plan-level` for `plan-only` / `partial-detail`; `detail-grounded` only for `detail-complete`. Hand off to plan correction/detail work or execution readiness. |
| `code-reconcile` | Authoritative plan, current code identity, saved reconcile snapshots, changed files, tests, and redirects | `code-grounded`. Hand off to bounded code correction, a plan-side redirect, or review. |
| `code-review` | Pinned merge-base/head range, tracked ledger, checks, intervening changes, and settled decisions | `review-grounded`. Hand off to another local correction/review round or PR review. |
| `pull-request-review` | The same pinned range plus PR findings materialized in the tracked review ledger | `review-grounded`. Hand off to correction/review or the developer's merge decision. |

For plan audit, bundle state is deterministic and mutually exclusive:

| Bundle state | Required basis |
| --- | --- |
| `plan-only` | `plan-level` |
| `partial-detail` | `plan-level` |
| `detail-complete` | permits `detail-grounded` |

The evaluator chooses the first applicable outlook, in this order:

| Outlook | Meaning | Orchestrator action |
| --- | --- | --- |
| `insufficient-evidence` | Current or comparable evidence is absent, stale, unqualified, or incomplete. | Gather or regenerate evidence; do not declare convergence or change scope. |
| `redesign-or-rescope` | The premise fails, a material structural finding recurs without narrowing, or the remedy exceeds authority. | Stop applying and surface the decision to the developer. |
| `finish-current-fix` | The material tail describes the last accepted correction and has a bounded completion. | Finish that correction, test and commit it, then advance without another full audit solely for a cleaner label. |
| `continue` | Real in-scope material findings remain but are narrowing or becoming less severe. | Apply the next judged correction and rerun the producing audit or review. |
| `converged` | Current qualified evidence meets the applicable clean or low-yield rule. | Record the basis in the normal handoff/ledger and proceed to the next workflow stage. |

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

## References

- `MISSION.md` — deterministic-chassis and mutation-authority principles.
- `docs/NONDETERMINISM_PLAN_DESIGN.md` — deterministic assembly, one judged
  call, response gates, and deterministic consumption.
- `docs/PROCESS_CONTRACTS.md` and `docs/WORKFLOWS.md` — current audit,
  reconcile, review, and handoff behavior.
- `plan_tool/cli/convergence_cmd.py` and `plan_tool/convergence_diagnosis.py`
  — current public diagnostic and reusable evidence calculations.
- `plan_tool/review_persistence.py`, `handoffs/README.md`, and
  `CONTRIBUTING.md` — current review evidence and durable ledger conventions.
- `plan_tool/roadmap_structural_revision_run.py` and `plan_tool/backend.py` —
  precedent for a read-only Codex boundary and identity-checked judged call.
