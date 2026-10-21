# Seed: retire `completeness-apply` and standardize convergence evaluation

## Outcome

Make orchestration the owner of conceptual-finding application and convergence
decisions: retire `completeness-apply` and every hidden consumer of its saved-gap
mutation path, then provide one evidence-grounded, non-mutating convergence
evaluation that gives an assistant and developer the same bounded question,
inputs, outlook vocabulary, and handoff across plan audit, reconciliation, code
review, and pull-request review.

## In scope

- Remove the public `completeness-apply` verb, its serial interactive walk, its
  parallel worktree apply path, and code that exists only to make those paths
  mutate plan or detail artifacts.
- Remove or replace every call, next-step recommendation, prompt instruction,
  process contract, CLI reference, test, benchmark cell, direct-pipeline stage,
  and active work item that assumes conceptual completeness findings are applied
  by `plan-tool`.
- Retire `direct-run` and `direct-jira`. Their one-shot contract owns
  orchestration inside `plan-tool` and depends on unattended conceptual apply;
  retaining them would preserve the behavior this effort removes.
- Replace the current `plan-tool convergence` diagnostic with one
  `plan-tool convergence-eval` surface. Preserve useful deterministic history,
  fingerprint, finding-identity, coverage, and evidence-ledger assembly as
  inputs to the evaluation rather than publishing a second competing verdict.
- Support the convergence contexts developers actually orchestrate:
  plan-level completeness audit, detail-grounded completeness audit,
  plan-canonical code reconciliation, local code review, and pull-request
  review. Remote review evidence reaches the evaluator through a tracked review
  ledger; the evaluator does not fetch it from GitHub or Bitbucket.
- Report plan bundle state separately from evaluation basis so a plan-level
  result cannot read as detail-grounded: `plan-only` (0 of N details),
  `partial-detail` (1 through N-1), and `detail-complete` (N of N), alongside
  `plan-level` or `detail-grounded` where those bases apply.
- Produce a structured convergence outlook and a concise human explanation,
  grounded in comparable snapshots, stable finding identities, material
  severities, dispositions, intervening changes, current artifact identity,
  qualification/budget state, and settled decisions.
- Preserve legacy completeness reports and their annotations as readable
  evidence. No migration rewrites an old report merely because its producer or
  suggested next action is retired.
- Update `MISSION.md`, the shared directives, process/flow/reference docs,
  generated CLI docs, glossary, developer workflow, active seeds, both
  backlogs, and tests so the repository has one current orchestration-first
  contract.

## Overview

The developer runs `plan-tool` through an orchestration layer. Audits and
reviews produce evidence; a coding-assistant conversation verifies the
findings, applies the class-wide corrections, runs tests, and discusses the
convergence outlook with the developer. A second interactive or unattended
apply layer inside the CLI duplicates that orchestration and can apply a saved
finding without the surrounding intent, code evidence, or scope decision.

The replacement standardizes the useful part of that conversation. It assembles
the evidence deterministically, asks one directed convergence question, gates
the response, and returns an outlook. It never edits the subject. The
orchestrator and developer decide what to do, apply any correction directly,
commit it, and re-run the producing audit or review before evaluating again.

## Problem statement

`completeness-apply` presents itself as the sole mutator of conceptual
completeness findings, while the maintained assistant-driven workflow already
tells non-interactive sessions not to use it. Its interactive path assumes a
human walks one finding at a time; its parallel path applies every eligible gap
without judgment; and `direct-run` / `direct-jira` invoke that parallel path as
a mandatory hidden stage. The result is two authorities for the same decision:
the orchestration conversation that developers actually use and a CLI apply
workflow the docs still teach and the code must maintain.

The existing `plan-tool convergence` command assembles useful saved history but
answers only a mechanical trajectory question. It cannot standardize the
content judgment developers make in conversation: whether the remaining
finding is material, whether it describes the artifact or the last fix, whether
the premise still holds, and whether the next move is another bounded
correction or a structural stop. That judgment currently has no shared input or
output contract across plan audits, reconcile sweeps, local review, and PR
review.

## Architecture

**Settled direction, user-confirmed 2026-09-14; do not reopen:** `plan-tool` is
used through an orchestration layer. The tool produces grounded evidence and a
standard evaluation; the orchestration layer owns conceptual application and
the developer owns scope and convergence decisions. No interactive-TTY or
unattended blanket apply path is retained as an alternative workflow.

The convergence evaluation follows the repository's deterministic-chassis
pattern:

1. **Deterministic assembly** selects one evaluation context, resolves the
   current subject and its immutable identity, gathers the applicable completed
   snapshots and dispositions, records coverage/budget limitations, and renders
   the exact evidence sent to the judge. Incomparable or stale evidence remains
   visible; it is never silently folded into a trend.
2. **One directed judged call** asks whether the evidence supports one outlook.
   It checks the work's stated intent and premise before judging how to close
   findings, compares stable identities and severity rather than raw counts,
   and distinguishes artifact defects from findings introduced by the latest
   correction.
3. **Deterministic response gates** require the closed outlook vocabulary,
   resolvable evidence references, coverage of every current material finding,
   and one next-action explanation. They validate response shape and evidence
   binding, not whether the judgment is philosophically correct.
4. **Deterministic consumption** renders machine-readable and human-readable
   forms and may persist only an append-only evaluation record with its input
   identities. It never edits the plan, details, code, review ledger, finding
   dispositions, or source audit reports. The orchestrator records any accepted
   decision in the normal handoff or review ledger.

The judged call is the last reachable rung: deterministic identity and trend
calculations plus new audit/review observations supply the evidence, but none
can decide premise validity, materiality, or whether the remaining tail
describes the artifact or the last correction.

**Binary observable:** for one accepted, current evidence envelope, the command
either emits one schema-valid evaluation bound to that envelope or refuses; in
neither case does any plan, detail, code, review ledger, finding disposition, or
source report change. The evaluation owner enforces a read-only backend mode and
compares subject fingerprints before and after the judged call. Only an
evaluation-record writer may run after that check, and it owns no subject path.

Exactly one evaluation context is selected. The caller or orchestration adapter
produces it; explicit selection wins over inference, mixed or ambiguous evidence
refuses before the judged call, and the resulting evaluation returns to the
same orchestrator:

| Context | Required evidence | Evaluation basis and exit |
| --- | --- | --- |
| `plan-audit` | Current plan, selected-grade detail coverage, completed completeness snapshots, dispositions, and audit qualification | `plan-level` for `plan-only` / `partial-detail`; `detail-grounded` only for `detail-complete`. A plan-level result hands off to remaining detail work or another plan correction; a detail-grounded result hands off to execution/export readiness. |
| `code-reconcile` | Authoritative plan, current code identity, saved reconcile snapshots, changes, tests, and redirects | Code-grounded. It hands off to a bounded code correction, plan-side redirect, or post-run review. |
| `code-review` | Pinned merge-base/head range, review ledger, test evidence, changes between rounds, and settled decisions | Review-grounded. It hands off to another local correction/review round or PR review. |
| `pull-request-review` | The same pinned range plus PR findings materialized in the tracked review ledger | Review-grounded. It hands off to another correction/review round or the developer's merge decision. |

For `plan-audit`, bundle state is deterministic and mutually exclusive:

| Bundle state | Producer and precedence | Consumer and exit path |
| --- | --- | --- |
| `plan-only` | Detail coverage computes 0 of N; it excludes both sibling states. | Selects `plan-level`; authoring the first detail moves it to `partial-detail`. |
| `partial-detail` | Coverage computes more than 0 and less than N; it excludes both sibling states. | Selects `plan-level`; authoring all missing details moves it to `detail-complete`. |
| `detail-complete` | Coverage computes N of N for the selected grade; it excludes both sibling states. | Permits `detail-grounded`; a removed, stale, or newly added undetailed step leaves this state. |

Evaluation basis is also a closed, mutually exclusive value produced by the
selected context adapter; no worst-of merge combines sibling bases:

| Evaluation basis | Producer and precedence | Consumer and exit path |
| --- | --- | --- |
| `plan-level` | The `plan-audit` adapter produces it whenever bundle state is `plan-only` or `partial-detail`; it is mandatory over `detail-grounded` in those states. | Limits claims to the plan body and available plan-level evidence; completing the selected detail bundle permits a later `detail-grounded` evaluation. |
| `detail-grounded` | The `plan-audit` adapter produces it only for `detail-complete` at the selected grade. | Supports the post-detail audit decision; any coverage loss returns a later evaluation to `plan-level`. |
| `code-grounded` | The `code-reconcile` adapter produces it from the authoritative plan, current code identity, reconcile evidence, and tests; other contexts cannot select it. | Supports a code correction, plan-side redirect, or handoff to review; a changed plan/code identity requires a new envelope. |
| `review-grounded` | The `code-review` or `pull-request-review` adapter produces it from a pinned range, ledger, checks, and settled decisions; missing pin or ledger evidence prevents this basis. | Supports another review round or the developer's PR/merge decision; a changed head requires a new envelope. |

The judged call returns exactly one outlook. The evaluator produces it, the
gates reject unknown or multiple values, precedence is evaluated top to bottom,
and the orchestrator consumes the named exit:

| Outlook | Meaning and precedence | Orchestrator exit |
| --- | --- | --- |
| `insufficient-evidence` | Required current/comparable evidence or applicable confirmation is missing. It takes precedence over every substantive conclusion. | Gather or regenerate evidence; do not declare convergence or change scope from this result. |
| `redesign-or-rescope` | The premise no longer holds, a material/structural finding recurs without narrowing, or the remedy cannot land inside the current authority and fence. It takes precedence over the remaining sufficient-evidence outcomes. | Stop applying and surface the premise, structure, or scope decision to the developer. |
| `finish-current-fix` | The new material tail predominantly describes the last accepted correction and the governing property has a bounded completion. It takes precedence over `continue` and `converged`. | Finish that correction, run its tests, commit it, and move to the applicable execution/review stage without launching another full audit merely for a cleaner label. |
| `continue` | Real in-scope material findings remain and the trajectory is narrowing or becoming less severe. It takes precedence over `converged`. | The orchestrator applies the next judged correction and reruns the producing audit or review. |
| `converged` | Current qualified evidence meets the applicable clean or low-yield rule and none of the outcomes above applies. | Record the basis and proceed to the next workflow stage; the developer still owns any merge or scope decision. |

Retiring the apply path includes its consumers. `completeness-audit` reports
conceptual findings as evidence for orchestration and points to
`convergence-eval`, never to a mutating paired verb. `direct-run` and
`direct-jira` are retired with it: their job is to own an unattended pipeline,
including blanket conceptual application and automatic progression, which is
the orchestration authority this effort assigns outside the tool. The ordinary
`create`, `detail`, audit, `run`, and `jira` stages remain available for an
orchestrator to compose explicitly.

The implementation performs both halves of the retirement sweep. Identifier
searches cover `completeness-apply`, `cmd_completeness_apply`, its serial and
parallel helpers, parser/handler registration, report suggestions, and direct
pipeline calls. Vocabulary searches cover phrases such as “sole mutator,”
“paired apply verb,” “walk and apply,” “human at a TTY,” “apply-all,” and
“audit/apply loop.” Every active site is updated or receives a stated reason to
remain. Active backlog entries and seeds whose outcome depends on the removed
surface are retired, reframed toward orchestration/evaluation, or explicitly
left for another surviving caller; archived evidence stays unchanged.

## Scope guardrails

- The binary observable is evaluation conformance plus subject non-mutation:
  one accepted current envelope yields one bound result or a refusal, while the
  subject remains byte-identical.
- The evaluation is advisory evidence. It does not apply a finding, choose a
  scope change, invoke a structural remedy, advance a plan step, merge a PR, or
  change a command's success exit code from an outlook alone.
- Deterministic gates may check input identity, completeness of the evidence
  envelope, allowed vocabulary, total finding coverage, and resolvable cited
  anchors. They may not judge prose quality, agreement between prose
  artifacts, artifact shape or length, whether a finding is “really” trivial,
  or whether the evaluator's conclusion is semantically correct.
- The effort adds no workflow gate and flips no existing command exit code
  from an outlook. These prohibitions are separate from the deterministic
  response gates that validate the evaluator's schema and evidence binding.
- No second convergence verdict remains beside `convergence-eval`. Mechanical
  history signals survive only as labeled evidence supplied to the evaluator.
- Plan bundle state and evaluation basis remain separate fields. A partial
  bundle never receives a detail-grounded claim, and detail coverage never
  demotes a plan-level correctness finding by itself.
- No hidden private rename preserves `completeness-apply` behavior for
  `direct-run`, `direct-jira`, or another command.

## Out of scope

- Removing `apply_finding` from `create`, `detail`, generic review walks, or
  reconcile flows that do not consume the completeness saved-gap application
  path. Evaluate those contracts as follow-up work under the same
  orchestration-first principle; do not silently bundle that larger rewrite
  here.
- Changing what completeness or reconcile audits inspect, their finding
  severities, the bare/detail conceptual bar, audit sampling, or existing
  deterministic well-formedness fixes.
- Fetching PR comments, approvals, or CI state from GitHub, Bitbucket, or any
  other remote; choosing the remote of record; or adding provider credentials.
- Requiring a different person, model, or fresh session as evaluator. The
  evaluation records its producer so independence policy can be decided later.
- Turning an outlook into a CI gate, automatic split/scope-out/re-seed,
  automatic backlog entry, merge decision, or generalized workflow engine.
- Rewriting archived plans, reports, seeds, presentations, or historical
  evidence solely to replace retired vocabulary. Live readers keep accepting
  legacy saved records.

## Allowed behavior changes

- `completeness-apply` is no longer a supported command and no current output
  recommends it.
- `direct-run` and `direct-jira` are no longer supported commands;
  orchestrators compose the ordinary stage commands and make the intervening
  decisions.
- The current deterministic `convergence` command becomes the standardized
  `convergence-eval` surface and may spend one bounded judged call after its
  deterministic evidence assembly. It no longer presents a mechanical
  `converging` label as the convergence answer.
- `completeness-audit` reports an orchestration handoff for conceptual findings
  and preserves those findings without offering a tool-owned mutation path.
- Append-only convergence evaluation records may be added, with explicit
  schema/version, source identities, compatibility reading, and recovery rules
  in `DATA_CONTRACT.md` if they persist on disk.

## Allowed reorganization

- Remove modules, helpers, tests, benchmark cells, and exports made callerless
  by `completeness-apply` retirement.
- Extract a cycle-free evidence-envelope builder and response parser shared by
  the supported evaluation contexts. Do not create a generic judgment or
  workflow framework.
- Move the useful deterministic parts of `convergence_diagnosis.py` behind the
  evaluator's input boundary without changing the underlying saved-report
  readers unnecessarily.

## Risks

- Removing only the parser entry leaves hidden auto-application in direct
  pipelines or stale report instructions. The identifier-plus-vocabulary sweep
  and a negative production-call test must prove the whole behavior class is
  gone.
- A convergence judge can sound authoritative while reading incomparable,
  stale, or incomplete evidence. Input identities and qualification are
  load-bearing, and missing evidence must force `insufficient-evidence` before
  the judged call can certify another outcome.
- A generic context schema can flatten meaningful differences between
  plan-level, detail-grounded, code-grounded, and review-grounded evidence. Each
  adapter owns its required evidence; only the outlook vocabulary is shared.
- An evaluator stacked on model-generated audits can amplify their bias. It
  must see the stated intent, settled decisions, dispositions, tests, and
  intervening diff, and must explicitly check whether the premise still holds.
- Retiring the interactive walker invalidates active backlog and seed rationale.
  Leaving those items in current prose would reintroduce the removed workflow
  through future work, so their disposition is part of delivery, not cleanup.
- Persisting evaluation output creates a new data contract. If durable storage
  is selected, legacy reading and interrupted-write recovery are designed
  before the new writer becomes default; otherwise keep the result ephemeral
  and require the orchestrator to record it in the existing ledger.

## Testing

- Prove the command and vocabulary retirement: the parser/help/command index,
  report renderers, active docs, active prompts, direct pipelines, imports, and
  production call graph contain no route that applies completeness conceptual
  findings or recommends `completeness-apply`.
- Preserve fixtures for legacy saved reports carrying apply annotations and
  verify the new evaluator can read them without rewriting them or treating a
  historical annotation as a current orchestration decision.
- Use hermetic invoker fixtures for each evaluation context and every outlook.
  The assembled evidence is deterministic for the same artifact identities;
  no test invokes a real backend.
- Gate mutations of the judged reply: an unknown/multiple outlook, omitted
  current material finding, unresolved evidence reference, mismatched subject
  identity, or missing next-action explanation retries or refuses without
  changing the subject.
- Prove bundle-state boundaries at 0/N, partial, and N/N detail coverage for the
  selected grade, including that only N/N permits `detail-grounded`.
- Feed improving, self-seeded, recurring structural, premise-invalidated,
  low-yield, stale, budget-limited, and insufficient-history evidence through
  the deterministic envelope and stubbed judged-reply boundary. Assert the
  evidence and constraints presented to the judge and the routing of every
  valid outlook; assess real-model judgment against a predeclared review corpus
  without turning its exact content into a deterministic unit-test fact.
- Before prompt tuning, freeze a self-contained corpus from current saved
  histories and tracked review ledgers with their recorded human exits. `create`
  derives and records the sample count and interpretation rule from the
  available corpus before detail authoring. Real-model trials report variance;
  any `converged` answer for a case whose current grounded record retains a
  material open finding is a safety failure, while other outcome disagreements
  remain review evidence rather than brittle unit-test expectations.
- Prove `direct-run` and `direct-jira` are absent from parser/help/dispatch and
  that their former shared helpers do not preserve a callable hidden pipeline.
- Run generated CLI reference checks, documentation link checks, focused
  completeness/convergence/direct-pipeline tests, then the complete suite.

## Acceptance criteria

- No supported `plan-tool` command applies conceptual completeness findings;
  `completeness-apply` and its serial/parallel implementation are absent, and
  no current output or active workflow points to them.
- `direct-run` and `direct-jira` are absent; their former auto-apply pipeline is
  not preserved under a private helper or replacement command.
- One `convergence-eval` contract covers plan audit, reconcile, local review,
  and PR review without conflating their evidence requirements.
- Every plan-audit evaluation renders `bundle_state`, exact `N of M` detail
  coverage, and `evaluation_basis`; `plan-only` and `partial-detail` results
  never claim detail grounding.
- Every completed evaluation returns exactly one of
  `insufficient-evidence`, `redesign-or-rescope`, `finish-current-fix`,
  `continue`, or `converged`, with current evidence references and the next
  orchestration action.
- The evaluator cannot mutate the subject or turn its outlook into a scope,
  execution, export, CI, or merge decision without an explicit orchestration
  action bound to that current evidence.
- Existing completeness/reconcile reports remain readable, while any new
  persisted evaluation record has a versioned compatibility and recovery
  contract before it becomes the default writer.
- `MISSION.md`, shared directives, process contracts, developer docs, active
  backlog entries, and active seeds describe orchestration-owned application
  and evaluation-owned convergence outlook in one vocabulary.
- The caller-and-vocabulary sweep records a disposition for every live site;
  the focused and complete test suites pass.

## Deferred

- Apply the orchestration-first test to the other `apply_finding` callers in
  `create`, `detail`, review, and reconcile as a separate effort after this
  retirement establishes the evaluation contract.
- Decide evaluator independence requirements and whether an evaluation outlook
  ever becomes a required remote check only after the team selects its remote
  and observes the advisory process in real reviews.
- Add GitHub/Bitbucket integrations, a PR template, `CODEOWNERS`, or a merge
  queue in their existing separate tooling work.
- Calibrate model choice, cost, or outcome precision from saved evaluation
  evidence; do not add thresholds or automated policy before that evidence
  exists.

## Stop / defer

Stop this effort if a supported context cannot assemble a current,
identity-bound evidence envelope without inventing a new authority or semantic
inference. File that missing evidence substrate in `BACKLOG.md` or
`BUG_BACKLOG.md`, as applicable, rather than weakening
`insufficient-evidence`, adding a hidden apply, or letting the evaluator infer
absent plan, code, range, ledger, or qualification facts.

## References

- `MISSION.md` § “Converge on the more-correct plan; mutate only when allowed”
  and § “Deterministically driven non-determinism” — the principle this effort
  updates and the judged-feature architecture it preserves.
- `integrations/shared/DIRECTIVES.md` § “The manual convergence loop” — the
  current assistant-vs-TTY split and three exits that become one
  orchestration-first evaluation contract.
- `docs/NONDETERMINISM_PLAN_DESIGN.md` — deterministic assembly, one directed
  judged call, response gates, and deterministic consumption.
- `docs/PROCESS_CONTRACTS.md` — current completeness-audit/apply authority and
  handoff table.
- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply`,
  `plan_tool/cli/completeness_phases.py:_run_apply_walk`, and
  `plan_tool/cli/completeness_apply_parallel.py` — serial and parallel mutation
  surfaces being retired.
- `plan_tool/cli/direct_cmd.py:cmd_direct_run` and `cmd_direct_jira` — packaged
  pipelines that currently invoke the apply surface without a conversational
  judgment boundary.
- `plan_tool/cli/convergence_cmd.py:cmd_convergence` and
  `plan_tool/convergence_diagnosis.py:diagnose_convergence` — deterministic
  history/evidence assembly the new evaluator consumes rather than exposing as
  a competing convergence answer.
- `plan_tool/review_persistence.py` and `plan_tool/completeness_report.py` —
  legacy report, annotation, identity, and presentation contracts that remain
  readable while their apply instructions change.
- `docs/GLOSSARY.md`, `CONTRIBUTING.md`, and `handoffs/README.md` — shared
  convergence vocabulary, orchestrated team workflow, and review-ledger
  destination.
- Active backlog entries #106, #114, #140, #209, #212, #256, #280, #81,
  #83, #89, and #98, plus active seeds found by the required vocabulary sweep —
  each is rechecked against the retired surface rather than left to recreate it.
