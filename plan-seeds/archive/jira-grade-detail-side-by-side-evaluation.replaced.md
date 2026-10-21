> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-grade-detail-side-by-side-evaluation.md`.
> Preserved here for history; do not edit.

# Plan seed: side-by-side jira-grade detail evaluation before any default inversion

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/jira-grade-detail-side-by-side-evaluation.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Decision-first scope.** Build an explicit jira-grade detail path beside the
> existing run-grade path, then evaluate them using the same plans and steps.
> The current run-grade authoring/execution path remains the default throughout
> this plan. A default inversion is explicitly deferred to a later decision based
> on the recorded results.
>
> **Source and lifecycle.** This seed implements BACKLOG #164 and inherits its
> full scope contract. The final documentation/status step must reconcile
> `BACKLOG.md`: leave #164 marked plan-authored while execution is pending, then
> remove it only after the side-by-side experiment ships; retain or add any
> default-inversion follow-up only when the recorded gate warrants it.

---

## Overview

Today `detail` authors implementation-grade prose for `run`, while `jira`
down-converts that prose into a story. This plan adds a second, jira-grade
authoring altitude that both `jira` and an opt-in `run` path can consume. It
does not replace the current path. Instead it makes the central claim testable:
does less prescriptive detail reduce scope-change contradiction churn without
hurting execution quality?

The work must leave a durable, reproducible paired-evaluation report. That
report — rather than an implementation preference — determines whether a
follow-up may make jira-grade the default.

## Problem statement

Run-grade detail commits to many volatile implementation facts: precise edits,
named call sites, test rosters, and prescribed mechanics. When plan scope moves,
those facts commonly become stale even when the design is correct. In the
2026-07-21 `example-app-amplify` mentor-observability plan, narrowing from 18
steps to 10 and then 6 left previous run-grade prose behind; subsequent audits
raised `ingestion-capture-and-rethrow`, `trace-subspans-scope`, and
`instance-name-scope-contradiction`, and convergence spun. Those were stale
implementation commitments, not unsettled design.

Jira-grade detail — what changes, why, constraints, acceptance, and exclusions
— has a smaller contradiction surface. But run-grade prose may also be carrying
useful execution work. Switching the default without a control would conflate
reduced audit churn with an unknown change in first-pass run quality, retry cost,
and diff scope adherence.

## Design

### Two explicit, coexisting contracts

Keep the current run-grade detail format, parser, artifact selection, and `run`
renderer as the control. Add an explicit jira-grade depth/mode, with an
unambiguous way to select and retain its artifacts separately from the control.
The same plan may therefore have comparable run-grade and jira-grade detail
bundles. Legacy bundles are always interpreted as run-grade; never silently
reinterpret or rewrite them.

The jira-grade schema should be the smallest shared contract that supports both
consumers: `Intent`/problem, `Change`, `Constraints`, `Done when`, and
`Out of scope` (the exact H2 vocabulary should align with or be sequenced after
BACKLOG #149's compact schema). It must state outcomes and boundaries, not
pre-bake file edits, named tests, or mechanical algorithms unless a declared
constraint makes one essential.

`jira` consumes this schema directly. The opt-in jira-grade `run` renderer
receives that same schema plus its normal plan/repository grounding and asks the
executor to derive the implementation. Its output must be separately selectable
from the unchanged run-grade renderer.

### Paired evaluation and evidence

Provide a repeatable harness or documented command sequence that runs both
depths against the same declared baseline, plan steps, repository revision, and
verification command. The evaluation report records:

- plan, steps, repository revision, backend/model settings, commands, and
  timestamps;
- for each depth: first-pass green result, retries, elapsed time and available
  cost/tool-use telemetry, verification outcome, and a human-reviewed
  scope-adherence/diff-quality verdict;
- a controlled scope-change replay followed by `completeness-audit`, including
  finding count and severity/kind; and
- raw artifact/report locations and an explicit pass, fail, or indeterminate
  recommendation.

Keep the experiment small but representative: at least one real plan with
nontrivial implementation work and a deliberately scoped change. Do not use
unmatched ad-hoc runs as evidence — the paired inputs and baseline must be
recorded.

### Predeclared adoption gate

Write the evaluation criteria before collecting results. Jira-grade is eligible
for a later default-inversion plan only when it is no worse than run-grade on
first-pass green rate and scope adherence/diff quality, does not materially
regress retries, elapsed time, or available cost telemetry, and reduces
scope-change audit churn. The report must state any tolerance used for
"materially" before results are read.

Mixed, insufficient, or regressive evidence is a valid outcome: retain
run-grade as the default and leave jira-grade opt-in. Do not add a hidden
fallback that masks which contract `run` actually executed.

### Audit-convergence arc

Follow the repository's `CLAUDE.md` manual-convergence policy after the detail
bundle exists. Run `completeness-audit` with `--iterate` to settle deterministic
findings and save the conceptual gap map; do **not** auto-drive
`completeness-apply` in a non-interactive session. Instead, read each saved
report, apply any in-scope conceptual corrections to the plan or detail prose
with explicit judgment, and re-audit.

Capture at least three completed audit snapshots: a baseline, a post-correction
snapshot, and a third snapshot that distinguishes a trend from reviewer
variation. Compare stable finding identities and material severities across the
three reports, not just raw counts. Continue only while findings become fewer,
narrower, or less material. If a high-impact finding recurs, material findings
stay flat, or an architecture contradiction emerges, stop patching; keep the
scope fence and file a focused backlog/redesign direction rather than silently
expanding this experiment. Finish only once the latest audit is clean or
confirmed low-yield under that policy.

## Suggested decomposition

Keep these as separate concerns:

- **Schema/parse step:** define jira-grade required sections and validation while
  preserving all run-grade and legacy read behavior.
- **Artifact-selection step:** add explicit depth selection and isolated,
  collision-safe storage/read routing so the two bundles coexist.
- **Consumer step:** have `jira` consume jira-grade detail directly and add the
  opt-in jira-grade `run` prompt renderer; retain the run-grade control intact.
- **Evaluation step:** add the reproducible paired-run recording/report surface
  and fixture coverage for provenance and metric calculations.
- **Evidence step:** execute the agreed representative A/B and commit the report
  plus a clear recommendation. This step never changes the default.

Do not combine the default inversion with any of these steps. It requires a new
plan that cites a passing report and separately handles migration policy.

## Out of scope

- Making jira-grade detail the default for `detail`, `run`, or `jira`.
- Re-authoring or bulk-rewriting existing run-grade bundles.
- Changing plan-body schema, step decomposition, `change_type`, or completeness
  audit logic.
- Weakening audit checks to make the experiment appear more successful.
- A corpus-wide benchmark or broad model comparison; this is a focused decision
  experiment with recorded provenance.

## Risks and mitigations

- **Run quality regression:** thinner detail may cause more rediscovery, retries,
  or incorrect diffs. Mitigation: unchanged run-grade control, paired inputs,
  predeclared gate, and no default flip here.
- **Artifact ambiguity:** mixed-depth files could cause a run to consume the
  wrong contract. Mitigation: explicit mode/depth selection, isolated storage or
  equivalently unambiguous metadata, and tests that reject ambiguous selection.
- **Metric noise:** backend nondeterminism can swamp one-off outcomes.
  Mitigation: record every setting and raw result, compare matched runs, and mark
  thin evidence indeterminate rather than extrapolating.
- **Schema duplication with #149:** two compact contracts could drift.
  Mitigation: sequence #149 first or define one shared token/alias layer; do not
  create competing required-section authorities.

## Acceptance criteria

- Run-grade detail remains the default and legacy run-grade bundles remain
  readable/executable without a rewrite.
- An explicit jira-grade mode produces and selects artifacts independently from
  run-grade for the same plan; ambiguous/mislabeled selection fails clearly.
- Jira-grade detail has a validated compact schema focused on intent, change,
  constraints, acceptance, and exclusions, aligned with #149 where applicable.
- `jira` consumes jira-grade detail directly, and an opt-in `run` path renders
  from it while the existing run-grade renderer remains available as the control.
- Tests cover both contracts, legacy read compatibility, artifact selection,
  prompt routing, and the fact that no default changed.
- A durable, reproducible paired-evaluation report records matched baseline,
  commands, raw outcomes, the specified execution metrics, the controlled
  scope-change audit result, and a recommendation against a threshold declared
  before measurement.
- No default inversion ships from this plan. A later plan may propose one only
  when the report passes its declared gate.
- The final documentation/status step reconciles BACKLOG #164 without removing
  it merely because this plan was authored; any out-of-scope audit finding is
  routed to `BACKLOG.md` or `BUG_BACKLOG.md`, not used to expand this plan.

## Deferred

- Default inversion and any migration/re-authoring policy for the existing
  corpus; require passing evidence and a separate plan.
- An escape hatch for individual jira-grade steps that need mechanically
  prescriptive supplemental detail; determine from experiment failures, rather
  than preemptively expanding the base schema.
- Wider benchmark automation and repeated-sample statistical confidence beyond
  the focused paired experiment.
