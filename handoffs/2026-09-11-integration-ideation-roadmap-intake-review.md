# Handoff: evaluate full AI-DLC Ideation intake for roadmap

## Purpose

Integration is producing the first complete AI-DLC Ideation corpus intended to feed
`plan-tool roadmap`. This is an opportunity to evaluate the roadmap intake
contract against real upstream lifecycle output, not just to run the current
command.

The review should answer two questions:

1. Does the current one-file `roadmap --from-existing <brief>` contract make
   adequate use of the approved Ideation evidence?
2. If it does not, what is the smallest roadmap change that preserves the
   useful evidence without coupling plan-tool to AI-DLC?

This document does not presume that multi-file intake is better. It defines the
corpus, the comparison, the invariants, and the decision required before Integration's
roadmap run.

## Current status

- Source repository: `<integration-consumer-root>`
- Target repository: `<repo-root>`
- Roadmap lineage: `integration-aidlc-mvp`
- AI-DLC intent: `260909-integration-mvp`
- AI-DLC scope: `feature`
- Current lifecycle boundary: Verification Gate 1 completes and the runtime
  is parked at `practices-discovery` without producing an Inception artifact.
- Completed Ideation work: Intent Capture, Feasibility, Scope Definition,
  Rough Mockups, and Approval & Handoff; Market Research and Team Formation
  are explicitly skipped.
- The complete corpus includes `initiative-brief.md`, `decision-log.md`, and
  `phase-check-ideation.md`.
- At pickup on 2026-09-11, the Integration source tree is clean at `0527be7`, and
  local `main` is one commit ahead of `origin/main`. That commit directly
  corrects four approval-handoff prose sites after the Gate receipt records
  its output fingerprints.

Therefore this remains a review intake, not authorization to invoke roadmap.
Before any run, refresh Approval & Handoff validation so the Gate receipt
binds `0527be7`'s exact source bytes, commit the resulting audit/state record,
push Integration's local commit, and use that approval-bound revision as the frozen
source.

## The product boundary the intake must preserve

Integration is a generic web control plane over dynamic workflow steps. A workflow
step selects its runtime; runtime names do not define the user-facing flow.

For the MVP:

- User input reaches an isolated Claude or Codex instance through chat only.
- That instance runs the runtime CLI configured for the current workflow step.
- AI-DLC Runtime happens to serve the early Ideation steps.
- Plan-tool happens to serve roadmap/Inception and Construction steps.
- The UI streams the model and CLI console output read-only.
- The UI shows repository artifacts in a read-only tree and can insert an
  unambiguous repository-relative file reference into chat.
- Repository artifact editing in the UI is deferred.
- Browser shell access, browser-held credentials, a user-facing engine chooser,
  and a second eligible runtime per MVP step are out of scope.
- Plan-tool owns local execution and Jira export; Integration does not duplicate them.

The roadmap must treat the AI-DLC-to-plan-tool assignment as the configured MVP
workflow, not as Integration's permanent domain model.

## Full Ideation corpus

All paths below are relative to the Integration repository.

### Intent Capture

- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/intent-capture/intent-statement.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/intent-capture/stakeholder-map.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/intent-capture/intent-capture-questions.md`

These establish the problem, users, success signal, trigger, decision authority,
and confirmed workflow scope. The Q&A is the evidence behind the synthesized
statements; it is not a second product brief.

### Feasibility & Constraints

- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/feasibility/feasibility-assessment.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/feasibility/constraint-register.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/feasibility/raid-log.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/feasibility/feasibility-questions.md`

These carry the exact plan-tool hosting facets:

- `compute = managed-containers`
- `model = pool`
- `topology = multi-unit`

They also record one environment, the separate interactive application and
credential-bearing worker, Git plus relational storage, roughly 100 internal
users with human-paced bursty load, the internal-data posture, and explicit
quality-attribute trade-offs.

### Scope Definition

- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/scope-definition/scope-document.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/scope-definition/intent-backlog.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/scope-definition/scope-definition-questions.md`

The scope document is the product fence. The intent backlog is prioritization
evidence and proto-decomposition; it must not be copied into the roadmap source
as preselected plan rows.

### Rough Mockups

- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/rough-mockups/wireframes.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/rough-mockups/user-flow.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/rough-mockups/rough-mockups-questions.md`

These clarify the generic workflow surface, chat-only input path, streamed raw
output, read-only repository tree, file references, and step-completion state.
The review findings about chat acknowledgement and repository empty/error/stale
states remain downstream design considerations, not extra roadmap rows by
default.

### Final Approval & Handoff — pending

- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/approval-handoff-questions.md`
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/initiative-brief.md` — pending
- `aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/decision-log.md` — pending
- `aidlc/spaces/default/intents/260909-integration-mvp/verification/phase-check-ideation.md` — pending

The initiative brief is the expected current `--from-existing` input. The
decision log and phase check are evidence used to review that brief; they are
not automatically co-equal source prompts.

### Records that are not roadmap source prose

- `memory.md` files are stage diaries and learning candidates.
- `learnings-selections.json` files are persistence receipts.
- `aidlc-state.md` is workflow state.
- `audit/*.md` is lifecycle evidence.
- The empty Market Research and Team Formation stage directories reflect
  explicit skips, not missing required product analysis.

These records may prove provenance or explain a skip, but should not be passed
to a model as undifferentiated product instructions.

## Current roadmap intake contract

The documented command accepts one Markdown brief:

```bash
plan-tool roadmap integration-aidlc-mvp \
  --from-existing <integration-consumer-root>/aidlc/spaces/default/intents/260909-integration-mvp/ideation/approval-handoff/initiative-brief.md
```

Plan-tool describes that input as one project-sized concept brief in the
author's words. It then creates `01-domain.md`, `02-constraints.md`,
`03-components.md`, `04-roadmap.md`, and native draft plan seeds. Disk—not
inherited model context—is the interface between roadmap stages.

That contract has valuable properties: a small explicit input, one frozen
identity, bounded prompt scope, and no knowledge of the upstream workflow.
The review should preserve those properties unless the corpus demonstrates a
specific loss that matters.

## Review experiment

Use the completed corpus as a benchmark before changing plan-tool.

### Baseline: one composed initiative brief

After Gate 1, review the initiative brief against every authoritative artifact
above. Record which facts are preserved, summarized, omitted, contradicted, or
prematurely decomposed. Do not run roadmap until this source review is complete.

The brief should preserve at least:

- central outcome and target users;
- the dynamic step/runtime distinction;
- the MVP runtime assignment without making it permanent product structure;
- chat-only user input through an isolated model worker;
- raw console streaming;
- the read-only repository tree and chat file references;
- the credential boundary;
- hosting facet values and scale assumptions;
- quality dispositions and material risks;
- the exact in/out scope fence;
- skipped-stage reasons and unresolved decisions that affect roadmap output.

It should not copy the intent backlog into a roadmap decomposition, enumerate
components, prescribe plan rows, or convert review suggestions into committed
scope.

### Compare possible intake designs

Assess these designs using the same corpus and expected four roadmap artifacts:

1. **Keep the single-brief contract.** Improve only the upstream initiative
   brief composition and its review checklist.
2. **Add a generic source manifest.** Accept one manifest that names ordered,
   typed Markdown sources with pinned digests and roles such as `intent`,
   `constraints`, `scope`, `experience`, and `decision-evidence`.
3. **Add a generic intake capsule.** Introduce a preprocessing command that
   deterministically creates one frozen roadmap brief plus a provenance index
   from a source set; roadmap itself still consumes one file.
4. **Add an AI-DLC-specific adapter outside roadmap.** Translate AI-DLC output
   into the existing generic brief contract without teaching roadmap about
   AI-DLC directories or stage names.

Do not select a design because it can ingest more text. Select it only if it
improves material decision coverage, traceability, or contradiction handling
without creating hidden instruction precedence or unstable source identity.

## Required evaluation criteria

For each design, record:

- which source documents are read and in what deterministic order;
- whether their exact bytes or digests are frozen before the first backend call;
- how duplicate, conflicting, stale, missing, symlinked, or out-of-repository
  sources are handled;
- how source roles and precedence are represented without trusting arbitrary
  document instructions;
- how question answers, approved synthesis, review findings, accepted risks,
  and skipped stages retain distinct meanings;
- whether prompt size remains bounded and observable;
- whether later roadmap stages can cite a stable source identity;
- whether roadmap remains usable by projects that do not use AI-DLC;
- whether a failed or interrupted intake can resume without silently changing
  its source set;
- whether the output meaningfully improves `01-domain.md`,
  `02-constraints.md`, `03-components.md`, `04-roadmap.md`, or the native seeds.

The preferred design should be the least new machinery that closes an observed
gap. If the composed initiative brief retains the decisions and produces strong
roadmap artifacts, keep the current contract.

## Artifact-by-artifact review after the run

If the source review approves a roadmap run, inspect:

- `01-domain.md`: Does it model dynamic workflows, steps, runtime assignments,
  chat submissions, runs, output events, and repository artifacts without
  hard-coding AI-DLC phases as Integration's domain?
- `02-constraints.md`: Does it preserve the exact hosting facets, quality
  dispositions, scale, credential boundary, and internal-data posture?
- `03-components.md`: Does ownership separate the web experience from the
  credential-bearing execution worker and assign stores explicitly?
- `04-roadmap.md`: Do plan rows prove the central outcome in dependency/risk
  order, carry explicit non-goals, and avoid treating AI-DLC or plan-tool as
  permanent UI structure?
- Draft seeds: Do they retain the originating decisions and scope fence without
  copying the entire Ideation corpus or inventing implementation detail?

Use the read-only views first:

```bash
plan-tool roadmap integration-aidlc-mvp --view summary --mode review
plan-tool roadmap integration-aidlc-mvp --view walk --mode review
plan-tool roadmap integration-aidlc-mvp --view ledger --mode review
plan-tool roadmap integration-aidlc-mvp --view seeds
```

## Decision record to add here

After reviewing the completed corpus and, if authorized, the baseline roadmap
run, update this document with:

- frozen Integration source commit;
- selected roadmap input and its digest;
- source-set inventory and digests if a multi-source experiment is performed;
- coverage findings by source artifact;
- contradictions or lost decisions;
- output comparison by roadmap artifact;
- selected intake design and rejected alternatives;
- whether plan-tool changes are required before the Integration roadmap can be
  accepted.

Any proposed plan-tool behavior change belongs in `BACKLOG.md` before code is
changed. This handoff supplies evidence and a decision boundary; it does not
authorize implementation by itself.

## Execution fence

- Do not run roadmap before Integration completes and commits Verification Gate 1.
- Do not pass the whole directory to a model as unordered text.
- Do not treat audit logs, memory diaries, or question options as co-equal
  approved product requirements.
- Do not let a plan-tool intake feature depend on AI-DLC paths or stage names.
- Do not let a richer intake bypass roadmap's existing artifact gates,
  feedback lifecycle, source identity, or seed invalidation rules.
- Do not materialize or apply seeds until the four roadmap artifacts and this
  intake decision are reviewed.

## Next

1. Finish Integration's Approval & Handoff stage and approve Verification Gate 1.
2. Commit the complete Integration Ideation corpus and record its commit here.
3. Review the final initiative brief against the corpus using the baseline
   checklist above.
4. Decide whether the current single-brief intake is sufficient for the first
   baseline roadmap run.
5. If it is sufficient, run and review roadmap before considering changes.
6. If it is not sufficient, record the observed gaps, add a bounded plan-tool
   backlog item, and compare the intake designs before implementation.
