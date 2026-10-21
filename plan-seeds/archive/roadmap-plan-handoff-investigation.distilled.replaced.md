> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-plan-handoff-investigation.md`.
> Preserved here for history; do not edit.

## Overview

Produce one reviewed design record at `docs/explanations/roadmap-plan-handoff.md` identifying the minimum shared input, its source/version authority, and whether `create`, `detail` and `completeness-audit` need new support. This is BACKLOG #492, the first investigation in its staged arc; each follow-on receives an explicit build/use-existing/no-action disposition. Tool behavior remains unchanged, and the observable is the record and its named consumer decisions, not a certified good decomposition.

## Problem statement

The investigation determines whether existing source-reference routes carry the information needed to hand an approved roadmap outcome into bounded plan increments. It must distinguish existing code from approved intent and observed provider behavior from approved obligations before proposing missing tool-side delivery. A missing feature is not presumed: the investigation closes with use-existing/no-action when no delivery gap is demonstrated.

## Architecture

The deliverable is `docs/explanations/roadmap-plan-handoff.md`, grounded in the selected Integration owner-answer journey and current plan-tool input paths. Start with two sections—ownership/authority and critical contracts/evidence—plus outcome references and unresolved decisions; add views only when a decision needs them. Cover application journey and layer ownership, critical provider and consumer obligations including required fields and behavior, versioned evidence, bounded increment composition, and compatibility for projects without shared context. Keep full outcome coverage as references.

Use the owner-answer journey: Integration receives an answer to its current question, the harness carries it in a resumed invocation, and the asking methodology tool supplies acceptance evidence. This is the recorded pilot under Integration owner decisions O03, O05 and O09, a study input rather than a new plan-tool runtime requirement. Trace the existing interface extension against current consumer code, distinguishing approved obligations, fixtures and observed provider behavior.

Review existing source-reference routes before proposing any feature. Inspect `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/review.py` and `plan_tool/cli/inspect.py`, including `plan_tool/create.py:_project_context_block`, `plan_tool/detail.py:render_detail_prompt` and `plan_tool/review.py:render_plan_audit_prompt`. Record whether `create`, `detail` and `completeness-audit` need new support; build, use-existing and no-action remain possible dispositions without changing the investigation's artifacts or procedure.

Record the exact Integration source revision used and explain any change from baseline `25d6517dd47949040b94904669128a5f0ba9aa06`; the earlier bounded evidence record retains provenance `2cb1e7283f9d23363b0ff185d223eecf76fc5036`. Read the layer map alongside the later probe and explicit owner decisions so answered questions are not reopened. Owner direction and observed behavior have different authority, and neither rewrites the accepted roadmap. Resolve roadmap content through its accepted head using `ROADMAP_FORMAT.md` and `plan_tool/roadmap_versions.py:load_accepted_version`, recording that version.

Choose a provider question that remains unresolved at the inspected revision without running another probe. If a required source cannot be read, record the limitation and leave its conclusion unresolved. Inspect #490, #485, #262 and #403 as ownership boundaries without implementing them. #493 and #494 remain unauthored and evidence-gated.

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

The design record traces the approved outcome through layer ownership, a critical contract, evidence and a bounded increment; includes an unresolved provider question and extension of an existing interface; compares existing references for create, detail and completeness-audit; and records source/revision authority, compatibility and a disposition for each follow-on. Evidence limits remain explicit.

The final step reconciles BACKLOG.md #492 only when the investigation ships, preserving the anchor arc and recording dispositions for the gated follow-ons. Plan authoring alone retains #492 and marks its plan-authored status. No follow-on seed is authored during this investigation.

## Deferred

close with use-existing/no-action if no missing tool-side
  delivery is demonstrated. Unresolved product choices stay with their owner.
  If one consumer needs shared lifecycle/schema authority, separate that contract
  before authoring an implementation seed; do not absorb it into the study.

## Input

Use the owner-answer journey: Integration receives an answer to its current question, the harness carries it in a resumed invocation, and the asking methodology tool supplies acceptance evidence. This is the recorded pilot under Integration owner decisions O03, O05 and O09; it is a study input, not a new plan-tool runtime requirement. Trace the existing interface extension against current consumer code and distinguish approved obligations, fixtures and observed provider behavior. Keep full outcome coverage as references rather than expanding the study to implement all runtimes.

The Integration source baseline for this seed review is commit `25d6517dd47949040b94904669128a5f0ba9aa06`; the three named source documents are clean at that revision. The earlier bounded evidence record retains its own `2cb1e7283f9d23363b0ff185d223eecf76fc5036` provenance. Record the exact source revision used by the investigation and explain any change from this baseline. Read the layer map alongside the later probe and explicit owner decisions: an earlier unresolved question is not still open merely because the map retains it. Owner direction and observed behavior have different authority; neither silently rewrites the accepted roadmap. Resolve roadmap content through its accepted head and record that version.

Choose a provider question that remains unresolved at the inspected revision; do not reopen the probe's answered questions or run another probe. If a required source cannot be read, record the limitation and leave the affected conclusion unresolved rather than inventing evidence. Inspect #490, #485, #262 and #403 as ownership boundaries; the investigation implements none of them.

## Scope guardrails

Documentation-only investigation. No production code, CLI, schema, persisted version, semantic validation, quality/agreement checks, prose caps, execution gates or exit-code changes. No Integration writes or new live probes. No implementation of #493, #494, #462, #490, #485 or #484. Unresolved product decisions remain owner decisions; cite them rather than inventing an answer.
