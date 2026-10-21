> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-plan-derivation.md`.
> Preserved here for history; do not edit.

## Overview

Improve the existing roadmap mapping → per-row seed materialization → create pipeline so it produces dependency-ordered, bounded implementation plans that retain shared producers, consumer integration and eventual acceptance obligations. Improve stage-four decomposition and source-context delivery through the existing workflow while preserving accepted-head authority and ordinary create’s single-plan contract. Verify the changes with focused regression coverage and an isolated Integration comparison of raw generated output.

## Problem statement

Generated plans need to retain the roadmap’s shared responsibilities, prerequisites, source references and eventual observed-proof requirements across mapping, seed materialization and create. The Integration replay supplies witnessed gaps in shared producers, ordering, integration and eventual observed proof, but retrospective evidence and manual repairs do not establish that granularity causes those gaps. This work distinguishes upstream mapping defects from context lost during the handoff.

## Architecture

Stage four derives the full mapping from the concept and stages one through three through plan_tool/prompts/roadmap-plans.md. Preserve its existing repository-independent boundary and support for several plans per component. Improve its selection of coherent implementation routes around shared producers, their consumers, ordering and end-to-end acceptance. Use existing split/merge dispositions according to independent implementation responsibilities, without a target plan count or directory-based rule.

Per-row materialization in plan_tool/prompts/roadmap-seed.md and plan_tool/roadmap.py receives all four accepted artifacts and repository grounding. Preserve that complete context while selecting the accepted row’s scope and naming relevant sibling-owned prerequisites; materialization does not create additional rows beneath it. Deliver source-backed obligations and local References through the existing seed-to-create path in plan_tool/create.py and docs/how-to/pipeline/create-from-existing.md. Seeds follow SEED_FORMAT.md, including Testing and Acceptance criteria.

Limit changes to existing mapping prompts, seed materialization and create input delivery. Existing accepted mappings change only through existing candidate/review/acceptance routes, and ordinary create remains single-plan authoring. Document the existing workflow in docs/how-to/roadmap.md. A drafting-only benchmark restriction does not weaken generated plans’ eventual runtime or observed deployment evidence requirements.

## Out of scope

No alternate creation mode, new CLI entry, separate plan-set record, new lifecycle, batch runner or downstream repartition of accepted rows. No application implementation, deployments, provider probes or manual Integration repair as the deliverable. No semantic completeness gate, coverage score, fixed plan count, size cap, automatic approval, new roadmap stage, source migration, cross-plan audit (#462), shared-context admission (#493), prerequisite projection (#494), execution scheduling or Jira changes.

None beyond the smallest changes to existing mapping prompts, seed materialization and create input delivery required by the Outcome; no new orchestration or artifact layer.

## Risks

The Integration replay contains retrospective evidence and manual repairs; it supplies witnessed failure cases, not causal proof about granularity. Stage-four mapping and later seed grounding see different inputs; comparisons must distinguish upstream mapping defects from losses in the handoff. Unknown prerequisites remain visible without manufacturing an implementation design that depends on their outcome.

## Testing

Hermetic tests demonstrate complete source-context delivery and retention through existing mapping, materialization and create boundaries, with existing lifecycle and authority behavior preserved. A judged isolated comparison uses equivalent concept, upstream artifacts, repository baseline, model and declared evidence for baseline and candidate. Retain raw mappings, seeds and plans before repairs; trace witnessed shared-producer, ordering, integration and eventual observed-proof gaps. More plans, clean audits and one sample do not establish semantic certification or efficiency.

## Acceptance criteria

The standard roadmap → materialize → accept/apply seed → create workflow retains the accepted scope and source references, assigns shared producers and consumer integration, and preserves eventual observed acceptance requirements. Newly generated mappings use existing split/merge choices where responsibilities require separate bounded plans. No alternative plan-set mode or persistent set layer is introduced. The isolated benchmark records raw output and judged coverage of witnessed gaps with equivalent inputs and explicit limitations.

Source: BACKLOG #496. The resulting plan updates BACKLOG.md when work ships; authoring alone retains a plan-authored entry, and deferred work stays explicit.

## Deferred

Surface conflicts with accepted scope or settled decisions. Retain unknown evidence as an explicit prerequisite rather than inventing its result. File unrelated defects in BUG_BACKLOG.md and forward-looking work in BACKLOG.md. Stop if the improvement requires a new authoring route or source-authority system; do not absorb #462/#493/#494.

## Input

Stage four derives the full mapping from the concept and stages one through three. It already supports several plans per component; retain that contract and its existing repository-independent stage boundary. Ask it to choose coherent implementation routes from source responsibilities, including shared producers, their consumers, ordering and end-to-end acceptance. Splitting follows independent implementation responsibilities, without a target count or directory-based rule.

Per-row materialization receives all four accepted artifacts and repository grounding today. Preserve that complete context while selecting the row’s scope and naming relevant sibling-owned prerequisites. Deliver source-backed obligations and local References through the existing seed-to-create path. Seeds follow SEED_FORMAT.md, including Testing and Acceptance criteria. A drafting-only benchmark restriction must not weaken the generated plans’ eventual runtime or observed deployment evidence requirements.

## Scope guardrails

Improve the existing roadmap-to-seeds-to-plans path only. Do not create a second plan-set workflow or repartition an accepted row during materialization. Deliver semantic context for judgment; do not check semantic agreement, quality, prose length or coverage with machine gates, scores or exit-code changes. Preserve accepted-head authority and existing review/acceptance routes. No application implementation or live provider execution is part of this tool-development effort.
