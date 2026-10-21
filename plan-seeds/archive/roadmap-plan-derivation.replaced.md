> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-plan-derivation.md`.
> Preserved here for history; do not edit.

# Roadmap plan derivation through the existing pipeline

## Outcome

The existing roadmap mapping → per-row seed materialization → create pipeline produces a dependency-ordered set of bounded implementation plans that retains the roadmap’s shared producers, consumer integration and eventual acceptance obligations.

## In scope

Improve stage-four plan decomposition and the existing per-row seed-to-create handoff; retain source references, sibling responsibilities and prerequisites in generated content; document the existing workflow; add focused regression coverage and an isolated Integration comparison of raw generated output.

## Out of scope / Non-goals

No alternate creation mode, new CLI entry, separate plan-set record, new lifecycle, batch runner or downstream repartition of accepted rows. No application implementation, deployments, provider probes or manual Integration repair as the deliverable. No semantic completeness gate, coverage score, fixed plan count, size cap, automatic approval, new roadmap stage, source migration, cross-plan audit (#462), shared-context admission (#493), prerequisite projection (#494), execution scheduling or Jira changes.

## Allowed behavior changes

Improve newly generated stage-four mappings and existing seed content within their source scope. Stage four chooses the bounded plan rows, including existing split/merge dispositions; materialization preserves the selected accepted row rather than creating additional rows beneath it. Existing accepted mappings change only through the existing candidate/review/acceptance routes. Ordinary create remains single-plan authoring.

## Allowed reorganization

None beyond the smallest changes to existing mapping prompts, seed materialization and create input delivery required by the Outcome; no new orchestration or artifact layer.

## Testing

Hermetic tests demonstrate complete source-context delivery and retention through existing mapping, materialization and create boundaries, with existing lifecycle and authority behavior preserved. A judged isolated comparison uses equivalent concept, upstream artifacts, repository baseline, model and declared evidence for baseline and candidate. Retain raw mappings, seeds and plans before repairs; trace witnessed shared-producer, ordering, integration and eventual observed-proof gaps. More plans, clean audits and one sample do not establish semantic certification or efficiency.

## Stop / defer

Surface conflicts with accepted scope or settled decisions. Retain unknown evidence as an explicit prerequisite rather than inventing its result. File unrelated defects in BUG_BACKLOG.md and forward-looking work in BACKLOG.md. Stop if the improvement requires a new authoring route or source-authority system; do not absorb #462/#493/#494.

## Architecture

Stage four derives the full mapping from the concept and stages one through three. It already supports several plans per component; retain that contract and its existing repository-independent stage boundary. Ask it to choose coherent implementation routes from source responsibilities, including shared producers, their consumers, ordering and end-to-end acceptance. Splitting follows independent implementation responsibilities, without a target count or directory-based rule.

Per-row materialization receives all four accepted artifacts and repository grounding today. Preserve that complete context while selecting the row’s scope and naming relevant sibling-owned prerequisites. Deliver source-backed obligations and local References through the existing seed-to-create path. Seeds follow SEED_FORMAT.md, including Testing and Acceptance criteria. A drafting-only benchmark restriction must not weaken the generated plans’ eventual runtime or observed deployment evidence requirements.

## Risks

The Integration replay contains retrospective evidence and manual repairs; it supplies witnessed failure cases, not causal proof about granularity. Stage-four mapping and later seed grounding see different inputs; comparisons must distinguish upstream mapping defects from losses in the handoff. Unknown prerequisites remain visible without manufacturing an implementation design that depends on their outcome.

## Acceptance criteria

The standard roadmap → materialize → accept/apply seed → create workflow retains the accepted scope and source references, assigns shared producers and consumer integration, and preserves eventual observed acceptance requirements. Newly generated mappings use existing split/merge choices where responsibilities require separate bounded plans. No alternative plan-set mode or persistent set layer is introduced. The isolated benchmark records raw output and judged coverage of witnessed gaps with equivalent inputs and explicit limitations.

Source: BACKLOG #496. The resulting plan updates BACKLOG.md when work ships; authoring alone retains a plan-authored entry, and deferred work stays explicit.

## Scope guardrails

Improve the existing roadmap-to-seeds-to-plans path only. Do not create a second plan-set workflow or repartition an accepted row during materialization. Deliver semantic context for judgment; do not check semantic agreement, quality, prose length or coverage with machine gates, scores or exit-code changes. Preserve accepted-head authority and existing review/acceptance routes. No application implementation or live provider execution is part of this tool-development effort.

## References

- BACKLOG.md — #496 owns the scope and shipment bookkeeping.
- ROADMAP_FORMAT.md — existing plan mapping dispositions and accepted-version authority.
- plan_tool/prompts/roadmap-plans.md — stage-four mapping from the concept and upstream artifacts.
- plan_tool/prompts/roadmap-seed.md and plan_tool/roadmap.py — existing grounded per-row materialization.
- plan_tool/create.py and docs/how-to/pipeline/create-from-existing.md — selected seed delivery and single-plan creation.
- SEED_FORMAT.md — canonical seed headings and concept altitude.
- docs/how-to/roadmap.md — existing staged handoff and direct fallback.
- docs/evidence/roadmap-plan-set-benchmark.md — pinned Integration evidence and comparison limitations.
