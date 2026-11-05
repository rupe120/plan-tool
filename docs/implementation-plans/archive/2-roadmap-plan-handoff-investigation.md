> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
format_version: 1
title: Roadmap Plan Handoff Investigation
intent: one reviewed design record identifies the minimum shared input, its source/version
  authority, and whether `create`, `detail` and `completeness-audit` need new support,
  with an explicit build/use-existing/no-action disposition for each follow-on. The
  observable is that record and its named consumer decisions, not a certified good
  decomposition.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/roadmap-plan-handoff-investigation.md
steps:
- id: 1
  title: Document the owner-answer journey and decide what shared input each consumer
    needs
  intent: Give plan authors a grounded decision about the minimum evidence needed
    to turn an accepted roadmap outcome into bounded increments; missing required
    evidence keeps this step incomplete.
  creates:
  - docs/explanations/roadmap-plan-handoff.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/roadmap-plan-handoff-investigation/01-document-owner-answer-journey-decide.md
  status: done
- id: 2
  title: 'Review the record against source evidence and reconcile #492 while preserving
    its staged arc'
  intent: Close the investigation only when its evidence, authority boundaries and
    follow-on decisions are explicit and reviewable; retain
  files:
  - docs/explanations/roadmap-plan-handoff.md
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the record to review through source and accepted-version checks, journey
      tracing, consumer-reference comparison, unresolved-question checks and explicit
      follow-on dispositions.
  detail: docs/implementation-plans/plan-details/roadmap-plan-handoff-investigation/02-review-record-against-source-evidence.md
  status: done
---
# Roadmap Plan Handoff Investigation

## Overview

Produce one reviewed design record at `docs/explanations/roadmap-plan-handoff.md` identifying the minimum shared input, its source/version authority, and whether `create`, `detail` and `completeness-audit` need new support. This is BACKLOG #492, the first investigation in its staged arc; each follow-on receives an explicit build/use-existing/no-action disposition. Missing required evidence prevents completion of the investigation and keeps #492 open; it is not a use-existing/no-action conclusion. Tool behavior remains unchanged, and the observable is the record and its named consumer decisions, not a certified good decomposition.

## Problem statement

The investigation determines whether existing source-reference routes carry the information needed to hand an approved roadmap outcome into bounded plan increments. It must distinguish existing code from approved intent and observed provider behavior from approved obligations before proposing missing tool-side delivery. A missing feature is not presumed: the investigation closes with use-existing/no-action when no delivery gap is demonstrated.

## Architecture

The deliverable is `docs/explanations/roadmap-plan-handoff.md`, grounded in the selected Integration owner-answer journey and current plan-tool input paths. Start with two sections—ownership/authority and critical contracts/evidence—plus outcome references and unresolved decisions; add views only when a decision needs them. Cover application journey and layer ownership, critical provider and consumer obligations including required fields and behavior, versioned evidence, bounded increment composition, and compatibility for projects without shared context. Keep full outcome coverage as references.

Use the owner-answer journey: Integration receives an answer to its current question, the harness carries it in a resumed invocation, and the asking methodology tool supplies acceptance evidence. This is the recorded pilot under Integration owner decisions O03, O05 and O09, a study input rather than a new plan-tool runtime requirement. Trace the existing interface extension against current consumer code, distinguishing approved obligations, fixtures and observed provider behavior.

Review existing source-reference routes before proposing any feature. Inspect `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py` and `plan_tool/cli/inspect.py`, including `plan_tool/create.py:_project_context_block`, `plan_tool/detail.py:render_detail_prompt` and `plan_tool/review.py:render_plan_audit_prompt`. Record whether `create`, `detail` and `completeness-audit` need new support; build, use-existing and no-action remain possible dispositions without changing the investigation's artifacts or procedure.

Record the exact Integration source revision used and explain any change from baseline `25d6517dd47949040b94904669128a5f0ba9aa06`; the earlier bounded evidence record retains provenance `2cb1e7283f9d23363b0ff185d223eecf76fc5036`. Read the layer map alongside the later probe and explicit owner decisions so answered questions are not reopened. Owner direction and observed behavior have different authority, and neither rewrites the accepted roadmap. Resolve roadmap content through its accepted head using `ROADMAP_FORMAT.md` and `plan_tool/roadmap_versions.py:load_accepted_version`, recording that version.

Choose a provider question that remains unresolved at the inspected revision without running another probe. If a required source cannot be read, record the limitation and leave its conclusion unresolved; #492 stays open until the evidence supports each required follow-on disposition. Inspect #490, #485, #262 and #403 as ownership boundaries without implementing them. #493 and #494 remain unauthored and evidence-gated.

### Decision targets

Record a separate need decision for each of `create`, `detail` and `completeness-audit`: what information it needs, what its existing input route delivers, and any demonstrated missing delivery. Then record a disposition for each follow-on in #492's arc: #493 (shared-context delivery), #462 (advisory cross-plan conflicts) and #494 (recorded-prerequisite status). These targets are backlog efforts, not the three prompt consumers. #490, #485 and #484 remain consulted independent owners, not additional disposition targets.

For each target, `build` recommends a later bounded feature only when a delivery gap is demonstrated, `use-existing` identifies the existing route that meets the need, and `no-action` records why no additional work is justified. Each conclusion cites its evidence and remaining prerequisites. #493's recommendation derives from the three consumer need decisions; #494 requires its distinct status-information need; #462 keeps its own scope and evidence gate, so this record assesses its applicability without declaring that gate met or blocking independent progress. #462’s disposition includes an applicability and gate-status note: when its gate is unmet, a build recommendation is conditional on that gate and does not close, promote or unblock #462. An unmet #462 gate does not keep #492 open; the required result is the evidenced recommendation and recorded gate status, not #462 eligibility. Use-existing/no-action for #462 requires evidence supporting that recommendation, never merely an unmet gate. A recommendation does not authorize implementation or change readiness by itself. Missing required evidence keeps the target unresolved and #492 open; an unresolved provider question may remain explicitly assigned when it does not prevent the required tool-side decisions.

## Input

Use the owner-answer journey: Integration receives an answer to its current question, the harness carries it in a resumed invocation, and the asking methodology tool supplies acceptance evidence. This is the recorded pilot under Integration owner decisions O03, O05 and O09; it is a study input, not a new plan-tool runtime requirement. Trace the existing interface extension against current consumer code and distinguish approved obligations, fixtures and observed provider behavior. Keep full outcome coverage as references rather than expanding the study to implement all runtimes.

The Integration source baseline for this seed review is commit `25d6517dd47949040b94904669128a5f0ba9aa06`; the three named source documents are clean at that revision. The earlier bounded evidence record retains its own `2cb1e7283f9d23363b0ff185d223eecf76fc5036` provenance. Record the exact source revision used by the investigation and explain any change from this baseline. Read the layer map alongside the later probe and explicit owner decisions: an earlier unresolved question is not still open merely because the map retains it. Owner direction and observed behavior have different authority; neither silently rewrites the accepted roadmap. Resolve roadmap content through its accepted head and record that version.

Choose a provider question that remains unresolved at the inspected revision; do not reopen the probe's answered questions or run another probe. If a required source cannot be read, record the limitation and leave the affected conclusion unresolved rather than inventing evidence; #492 stays open until the evidence supports each required follow-on disposition. Inspect #490, #485, #262 and #403 as ownership boundaries; the investigation implements none of them.

## Scope guardrails

Documentation-only investigation. No production code, CLI, schema, persisted version, semantic validation, quality/agreement checks, prose caps, execution gates or exit-code changes. No Integration writes or new live probes. No implementation of #493, #494, #462, #490, #485 or #484. Unresolved product decisions remain owner decisions; cite them rather than inventing an answer.

## References

- BACKLOG.md #492 (scope and single stage-arc authority), #493, #494, #462, #490, #485, #262 and #403.
- docs/evidence/integration-roadmap-to-plan-handoff.md (source checkout, revision and bounded observations).
- docs/reference/documentation-style.md (design record readability).
- plan_tool/create.py, plan_tool/detail.py, plan_tool/review.py and plan_tool/cli/inspect.py (inspect current input delivery and status capabilities).
- ROADMAP_FORMAT.md and plan_tool/roadmap_versions.py:load_accepted_version (immutable accepted-head authority).
- plan_tool/create.py:_project_context_block, plan_tool/detail.py:render_detail_prompt and plan_tool/review.py:render_plan_audit_prompt (existing project-context inputs to inspect, not a presumed missing feature).
- <integration-consumer-root>/docs/engine-sessions/signal-layer-map.md
- <integration-consumer-root>/docs/engine-sessions/2026-10-15-aidlc-probe-record.md
- <integration-consumer-root>/docs/proposals/2026-10-15-roadmap-to-plan-collaborative-approach.md
- Within the selected Integration checkout: docs/engine-sessions/signal-layer-map.md, “Outcome coverage pointer”, and docs/proposals/2026-10-15-live-runtime-next-plan-composition.md (full outcome coverage and the evidence-grounded proposed increment; proposals do not supply accepted-roadmap authority).

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

new CLI commands, schemas or persisted versions;
  implementing #493, #462, #494, #490, #485 or #484; a fifth roadmap artifact;
  rewriting accepted roadmaps; automatic splitting, blocking or semantic
  validation; a full inventory unrelated to the selected journey; treating CLI
  names as complete contracts; Integration product/runtime changes or live model probes.

none; this investigation produces a design
  decision and proposed follow-on scopes only.

none.

## Risks

turning a useful shared record into another large design
  phase, interpreting observed code as approved contract, or making an
  unobservable feasibility judgment into an execution gate.

## Testing

trace the selected Integration journey from approved outcome to
  responsible layer, relevant contract, available evidence and proposed increment.
  Include an unresolved provider question and an extension to an existing
  interface. Review whether existing source references already carry the needed
  information. The record names evidence limits and each follow-on disposition;
  no synthetic example or report silence is claimed as proven feasibility.

## Acceptance criteria

The design record traces the approved outcome through layer ownership, a critical contract, evidence and a bounded increment; includes an unresolved provider question and extension of an existing interface; compares existing references for create, detail and completeness-audit; and records source/revision authority, compatibility and a disposition for #493, #462 and #494, separately from the three consumer need decisions. Evidence limits remain explicit.

Missing required evidence leaves both the investigation and #492 open; it never counts as a final disposition or permits shipment. The final step reconciles BACKLOG.md #492 only when the investigation ships, preserving the anchor arc and recording dispositions for the gated follow-ons. Plan authoring alone retains #492 and marks its plan-authored status. No follow-on seed is authored during this investigation.

## Deferred

close with use-existing/no-action if no missing tool-side
  delivery is demonstrated. Unresolved product choices stay with their owner.
  If one consumer needs shared lifecycle/schema authority, separate that contract
  before authoring an implementation seed; do not absorb it into the study.
