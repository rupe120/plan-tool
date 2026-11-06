# Harness instruction-loading experiment protocol, 2026-10-13

This dated protocol defines the experiment summarized in `RESULTS.md` and
`RECHECK.md`. It tests whether a compact, task-routed instruction entry point
reduces the cost of developing plan-tool without losing required behavior.
The owner uses the result to decide whether to propose an instruction-layout
change. This document defines the experiment; it does not report results or
authorize production policy changes.

## Question and scope

Can an agent deliver the same bounded changes with fewer tokens and less time
when detailed repository rules are retrieved as needed rather than loaded at
startup? The treatment changes delivery of instructions, not their authority.

In scope: two instruction-loading conditions, six fixed tasks, three repeated
runs per task and condition, behavioral grading, and cost measurement.
Out of scope: orchestration redesign, new agents, removing audit gates,
changing convergence policy, semantic-quality gates, model selection, or
modifying the shipped tool. Audit count alone is not a quality score.

This experiment concerns the outer development session's repository guidance.
It does not isolate plan-tool's internally assembled prompts or injected
lessons. The existing `experiments/lessons-utility/` owns that separate question.

## Conditions

| Condition | Startup guidance | Guidance available on demand |
| --- | --- | --- |
| A: full | The pinned clone's complete CLAUDE.md, also exposed by AGENTS.md | All existing reference documents |
| B: routed | A compact entry point retaining essential constraints and a task-to-document map | The identical full instruction text and reference documents |

Prepare B only inside disposable trial clones. Move the exact full text to
`experiment-full-instructions.md` at repository root; replace CLAUDE.md with the compact
entry point and preserve AGENTS.md's symlink. Include section anchors in its
routing table. Keep the full text out of automatic instruction discovery, but
make it available through ordinary file reads. Preserve relative-reference
meaning by keeping the full text at its original directory depth. Verify that
both the compact entry point and the full reference resolve their local links.
Do not change the controller clone's CLAUDE.md or AGENTS.md.

The compact entry point retains: mission and machine/prose ownership; scope
and user-decision boundaries; observable-only enforcement; test/invoker safety;
bounded commits; canonical-document ownership; applicable audit/reconcile
direction and convergence obligations. Route detailed procedures, architecture
constraints, and incident evidence to their exact owners. Before any run,
the owner verifies a rule-to-destination coverage table and freezes its hash.
The table checks preservation of rules, not semantic equivalence by word count.

## Freeze the inputs before sampling

The initial controller baseline is commit
`5ec159791f20070c9db890fe021deafc673e1bb1` in
`<controller-clone>`.
Record the experiment-definition commit separately. This result applies to
that baseline's guidance, which can differ from the main development checkout.

Use six historical, bounded tasks, reconstructed at their pre-fix commits:

| Slot | Task family | Required behavioral check |
| --- | --- | --- |
| T1 | Single-module bug | Reported failure closes; a previously correct sibling case remains correct |
| T2 | Shared contract across consumers | Every named consumer follows the contract; deliberate exemptions remain |
| T3 | CLI behavior and documentation | Observable command behavior, help, and owning reference agree |
| T4 | Persisted artifact compatibility | Legacy reading and unsupported-version refusal remain correct |
| T5 | Retry or interruption recovery | Normal recovery works; a partial mutation cannot be blindly replayed |
| T6 | Small bounded feature | User-visible acceptance behavior works without adjacent scope expansion |

Select concrete source commits, task prompts, allowed paths, and acceptance
checks before either condition runs. Use public-facing task descriptions;
withhold the original patch, review ledger, and answer tests from the agent.
Include ordinary tasks as well as instruction-sensitive tasks; do not select
only incidents the guidance specifically discusses. Selection is a prerequisite,
not permission to invent six new features.

Freeze the standing instructions and development policies at the controller
baseline. Freeze versioned code contracts, schema examples, and generated CLI
references at each task's pre-fix snapshot; both conditions receive the identical
task-specific reference corpus. A reference solution includes its own required
documentation changes. Do not overwrite historical code contracts with newer
ones: that creates unrelated schema/help failures instead of testing instruction
loading. Check the applicable pinned rules against each task, and reject real
rule conflicts before sampling. Hash prompts,
snapshots, overlays, and external answer tests in the selected task manifest
(`replacement-tasks.json` for this cohort; `tasks.json` retains rejected preparation).
Keep grading tests outside trial repositories. Prove each answer test fails
on the pre-fix snapshot and passes on the known reference solution. Verify
deliberate exemptions with an appropriate negative mutation.

### Prevent answer leakage

Prepare each trial repository from an exported pre-fix tree with an independent
Git repository and one initial commit containing the frozen overlay. Retain
source commit identities in the controller manifest, not reachable trial
history. Trial repositories have no remotes, alternate object stores, later
commits, or access to controller solutions and grading files. Restrict network
and filesystem access so agents cannot fetch those answers elsewhere.

Inspect the frozen guidance and reference corpus for each task's original
solution, review findings, reproducer, and answer-bearing incident narrative.
Reject a task if preserving the retained rules requires exposing its answer;
do not selectively redact one condition. Freeze a per-task leakage checklist
covering files, Git objects, global context, and accessible external sources.
Ordinary descriptions of the required behavior remain part of the task prompt.

## Run procedure

1. Freeze one available backend/model, exact model identifier, reasoning
   setting, CLI version, permissions, environment, and task prompt per pair.
   Follow repository model-tier guidance. If the selected model is unavailable,
   amend the protocol before sampling; do not silently mix models.
2. Create a fresh fully isolated repository from the frozen fixture for each
   trial, with its own .git, .plan-tool,
   manifest, branch namespace, and copied frozen lesson state. Sanitize global
   instructions, user lessons, memory, and connector access identically. Log
   their presence explicitly; avoid leaking prior outputs between trials.
3. Verify startup loading in disposable probes for both conditions. Confirm
   that A receives the complete pinned instruction text without truncation,
   B receives the complete compact entry point without automatic full-text
   injection, and B can read the full reference and routed documents. Record
   effective discovery settings, size limits, and evidence of actual injected
   content; an agent's claim that it read the rules is insufficient. If the
   backend cannot expose sufficient evidence, mark isolation unverified and
   do not claim a causal instruction-loading result.
4. Run all six tasks three times in each condition: 36 trials. Within each
   repetition, randomize task order and balance A-first/B-first pairs. Record
   the random seed. Run serially; do not merge trial outputs into the controller.
5. Let each agent perform the same required development/test/review workflow.
   Capture tool reads, diffs, tests, commits, audit reports, usage, and elapsed
   time. No coaching during a trial. A necessary scope question is recorded
   as an intervention; use a frozen answer identically for paired runs.
6. Grade anonymized final artifacts with external checks, then have the owner
   assess scope and material rule violations against a frozen rubric. A
   passing agent-authored test is evidence, not the grading oracle.
7. Save raw evidence under `.tmp/harness-instruction-loading/`; keep the task
   manifest, compact entry point, coverage table, and aggregate report in this
   experiment directory. Do not commit private data or provider credentials.

Before execution the owner sets a total spend ceiling and scheduling envelope
from six unscored calibration probes, one per task using A. Freeze limits before
scored trials. Exhaustion pauses scheduling of new trials and yields incomplete
coverage; it does not convert partial results into success. Do not terminate a
running plan-tool command without explicit user permission. No paid trials are
part of defining this experiment.

Freeze equal per-trial elapsed-time and provider-usage limits for A and B,
including nested review/backend calls, and a response deadline for scope
questions. Use the same predeclared answer policy for paired trials; an
unanticipated question receives no improvised coaching and is recorded as an
unresolved intervention. A trial completes when the agent returns its final
delivery after its required workflow, or is recorded as incomplete when a
limit or response deadline prevents completion. Incomplete trials are
unaccepted and retain all observed costs; they are not environment failures
eligible for replacement. Stop further agent calls at a limit. If a plan-tool
command remains active, request permission to stop it, pause new scheduling,
and include its eventual usage and elapsed time; limits are scheduling bounds,
not a guarantee of a hard spend cap. Reserve headroom and obtain approval for
this possible overrun before execution.

## Measures and grading

| Measure | Definition |
| --- | --- |
| Accepted delivery (primary quality measure) | All mandatory external behavior checks pass, with no material scope or repository-rule violation |
| Material defect | Confirmed failure of a frozen acceptance property; cite a reproducer or exact violated rule |
| Instruction retrieval | Which referenced sections B reads before the relevant action; missing reads alone are not defects |
| Tokens and cost | Whole-trial provider usage including retries and review; separate input, output, cached usage, and estimates |
| Time | Whole-trial elapsed time and active execution time; identify provider waits separately when observable |
| Human intervention | Number and purpose of required clarifications or corrections |
| Process diagnostics | Test/review/audit calls, self-seeded edits, and scope expansion; explanatory measures, not success proxies |

Missing usage is unknown, not zero. Include failed trials in resource totals.
Report cost per accepted delivery as total condition cost divided by accepted
trials; it is undefined when no trial is accepted. Report all 18 matched pairs,
per-task distributions, medians, and within-task variation. Preserve failures
and infrastructure errors separately; replace an invalid trial only under a
predeclared environment-failure rule, and retain its record and cost.

For each matched pair and resource measure, compute percentage reduction as
`100 * (A - B) / A`; the headline reduction is the median of the 18 pair
percentages, not a percentage computed from condition medians. Token use is
provider-reported input plus output tokens across all trial calls; cached input
counts once within input, and separately reported reasoning counts only when
it is not already included in output. Freeze the backend-specific field mapping.
Report billed cost separately because caching can change price independently
of token volume. Elapsed time spans trial launch through completion, including
clarification and provider waits. Missing totals or nonpositive A denominators
make that measure unevaluable; do not drop pairs or substitute estimates into
the threshold calculation. Report estimates separately.

## Decision rule

This is a screening experiment, not a powered proof of quality equivalence.
Use these owner-selected thresholds, frozen before runs:

- Propose a larger confirmation only if every pair accepted in A is also
  accepted in B, at least one A trial is accepted, B introduces no material
  safety/ownership regression, and B
  reduces median paired token use by at least 20% or elapsed time by at least
  15%. Report both measures even when only one improves, plus cost per accepted
  delivery and the task-level variability. For a resource measure to qualify,
  its median percentage reduction across each task's three repetitions must
  also be nonnegative for all six tasks. All 18 pairs must have evaluable data
  for that measure and all quality grades must be complete.
- Reject this compact entry point if it introduces a confirmed material
  regression attributable to missed guidance. Preserve the counterexample;
  do not tune B and pool new runs with the original condition.
- Report inconclusive when neither measure meets its headline threshold
  and per-task consistency requirement, or when the quality condition fails
  without an attributable guidance regression. Missing data for one resource
  measure does not invalidate an otherwise qualifying second measure; report
  that limitation explicitly. Unless the rejection rule applies, incomplete
  scheduled coverage, any incomplete trial, or unverified startup isolation
  makes the screening inconclusive.

Apply rejection first when its attributable material regression is confirmed;
otherwise apply the favorable-screening requirements, then inconclusive. A
confirmed counterexample remains a rejection even if other trials are missing.

No observed quality loss in 18 pairs is not evidence that rare failures are
absent. Any follow-up uses held-out tasks and a separately frozen protocol.
Production instruction changes require the repository's architect-tier review
and normal pull-request flow. A favorable screening result authorizes a
proposal, not replacement of standing rules.

## Evidence behind the question

- [OpenAI, Harness engineering](https://openai.com/index/harness-engineering/):
  a production experience report favoring a short entry point and discoverable
  deeper repository knowledge.
- [Evaluating AGENTS.md](https://arxiv.org/abs/2602.11988), September 2026
  revision: context files do not generally improve task success in its tested
  settings and add inference cost. This is not a measurement of plan-tool.
- [Anthropic, Harness design](https://www.anthropic.com/engineering/harness-design-long-running-apps):
  component-by-component removal helps identify which scaffolding earns its cost.
- [LangChain, Improving Deep Agents](https://www.langchain.com/blog/improving-deep-agents-with-harness-engineering):
  trace-guided changes and executable verification improve a fixed-model
  benchmark result, without isolating instruction loading as the cause.

## Readiness and next action

Status: protocol defined; no trials or results. Before running, prepare and
freeze the six task fixtures, compact entry point, rule coverage table,
startup-isolation probe, model configuration, and resource envelope. Review
those concrete inputs before sampling. This experiment needs no new runtime
framework, semantic validator, or change to plan-tool's gates.
