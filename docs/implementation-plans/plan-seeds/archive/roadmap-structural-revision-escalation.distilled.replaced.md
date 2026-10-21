> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-structural-revision-escalation.md`.
> Preserved here for history; do not edit.

## Overview

`plan-tool roadmap` adds an explicit, review-first escalation path for one artifact-qualified feedback row that cannot safely use the bounded local revision mode. It writes durable, canonical-roadmap-adjacent evidence describing the escalation reason, affected artifacts and stable targets, bounded context estimate, digest state, and recommended operator action. The path is deterministic and read-only: it does not rewrite roadmap artifacts, seeds, feedback lifecycle state, drafts, or Git state, and it does not automatically invoke a broad revision.

## Problem statement

The narrowed `roadmap-incremental-revision` path is safe because it has a closed write set: one existing artifact, one target row, a few scalar presentation fields, and one proposed feedback response. Structural requests can affect prose, row membership, relations, decisions, or multiple artifacts, so silently widening the local command would remove its central safety guarantee. Directing operators only to `--from-stage` is also insufficient because the broad path receives full-stage context without a reviewable account of scope, source revision, or expected impact.

## Architecture

The escalation surface accepts one stable `<artifact>:<feedback-id>` selector and performs strict preflight validation. It may reject an unknown, duplicate, closed, or stale selector, but a selector can remain valid for escalation even when it is ineligible for local revision. Selection helpers may be shared with the local revision surface where appropriate without changing that surface's single-artifact write rules or error semantics.

A deterministic classifier uses canonical target kind, artifact ownership, and an explicit operator-selected escalation reason. Supported reasons cover prose, row or collection structure, relationship or decision semantics, and cross-artifact impact. The classifier records why review is required without claiming that the feedback prose has been semantically solved or asking a backend to invent a patch or impact set.

The command writes a compact, versioned escalation report under the roadmap's own directory. The report records canonical input digests, the selected feedback and target identities, directly declared relation neighbors, target type, classification and reason, included context slices and their byte/count accounting, recommended next action, creation time, and a stale/current result. One report covers one selected feedback row and is immutable by convention; it is supporting evidence rather than a fifth roadmap artifact.

The context estimate includes the selected feedback, its owning artifact and target, and the declared relation closure needed to understand that target. It excludes unrelated artifact prose, unselected feedback, plan-seed drafts, and repository code. Every named artifact carries its current digest so later routing can reject stale evidence and require regeneration.

Ownership-stage resolution is deterministic and comes from the roadmap artifact model. The report recommends the existing broad `--from-stage` command only when an owner stage is unambiguous; otherwise it reports that a schema or ownership decision is required. The operator reviews the report and chooses the next action, and the escalation command never invokes `--from-stage` itself.

Read-only CLI and view output expose the selected item, escalation reason, affected artifacts, digest state, context estimate, and exact no-write guarantee. Existing read-only views remain canonical-artifact views. Command lifecycle observability records command start, result, or failure with the selector, report digest, and stale/current outcome, while ordinary read-only views continue not to create run logs merely by being read.

Shared reorganization is limited to deterministic feedback selection, artifact digest, relation summary, or owning-stage helpers needed by both local revision and escalation paths. Broad stage generation, artifact schemas, seed machinery, and run logging are not refactored merely to make the commands uniform.

## Out of scope

- Backend-generated patches, model-selected impact sets, automatic broad revision, multi-artifact writers, and transaction or publication protocols are excluded because this plan provides evidence and routing only.
- Editing roadmap prose; adding, removing, or reordering rows; changing relations or decisions; responding to or closing feedback; and updating reviewer-owned state are excluded by the read-only contract.
- Changes to the local `--revise-feedback` allowlist, one-artifact atomic replacement behavior, conservative seed invalidation policy, or failure and recovery semantics are excluded so the existing bounded path retains its safety model.
- Changes to `--from-stage` prompt construction, full-stage output schema, retry behavior, timeouts, or broad-stage publication are excluded; the report may expose the size of that route but does not reduce it.
- Seed materialization, refresh, promotion, acceptance, and related observability are excluded because `roadmap-seed-materialization-observability.md` owns materialization lifecycle telemetry.
- Git commits, branches, pull requests, external tickets, user identities, and a general workflow or task-management system are excluded.
- A manual arbitrary-text editing interface and an external database or service are excluded.

## Risks

- **Silent widening of local revision:** structural work could escape the closed write set and remove the local command's central safety guarantee. The mitigation is a distinct, explicitly invoked, read-only escalation surface.
- **Stale evidence reused as approval:** changes to named canonical artifacts or the selected feedback row could invalidate the report. The mitigation is revision-bound digests, a visible stale/current result, rejection of stale routing evidence, and regeneration before reuse.
- **Over-broad context collection:** estimating impact could expose unrelated artifact prose, unselected feedback, seed drafts, or repository code. The mitigation is a conservative declared-relation closure with explicit slice byte/count accounting and tests of the included inputs.
- **Heuristic routing:** an invented owner-stage or relation heuristic could recommend an unsafe broad command. The mitigation is deterministic ownership-stage and relation-summary resolution; if the artifact model cannot provide either, the command stops and surfaces the schema decision.
- **Escalation becoming execution:** automatically invoking `--from-stage` or asking a backend to design a patch would turn review evidence into an implicit broad rewrite. The mitigation is an operator-reviewed recommendation with no backend invocation, retry policy, or automatic broad command.

## Testing

Use unit, CLI, and fixture tests for selector validation, deterministic classification, artifact ownership, relation closure, report determinism, digest staleness, read-only behavior, and output routing. Fixtures verify that a valid row and explicit structural reason produce the expected input digests, relation summary, context counts, and recommended route, and that repeated execution on unchanged inputs produces the same semantic report.

Error-path coverage includes unknown, duplicate, closed, removed, and cross-artifact-invalid selectors, all failing before a report write or backend invocation. Tests also prove that escalation eligibility is independent of local-revision eligibility.

Context-boundary tests assert the exact reported inputs and byte/count accounting and prove that unrelated artifact prose, unselected feedback, seed draft text, and repository-code content are absent. Staleness tests modify each named canonical artifact and the selected feedback row, while confirming that an unrelated file change does not stale the report.

Read-only tests verify that every canonical roadmap artifact, feedback state, seed-state sidecar, draft seed, and Git worktree file remains byte-for-byte unchanged except for the declared report location and permitted command telemetry. The roadmap-focused suite runs without credentials and proves that no backend is invoked in normal or error paths. An opt-in disposable-repository smoke test verifies the no-write boundary against a real roadmap.

## Acceptance criteria

- A valid selected feedback row and explicit structural reason produce a deterministic, versioned escalation report with matching input digests, relation summary, context byte/count accounting, classification, and recommended route.
- Repeating the escalation command on unchanged canonical inputs produces the same semantic report.
- Unknown, duplicate, closed, removed, and cross-artifact-invalid selectors fail before any report write or backend invocation.
- A selector valid for escalation remains accepted even when it is not eligible for local revision.
- The report includes only the selected feedback, its owning artifact and target, and the declared relation closure; it excludes unrelated artifact prose, unselected feedback, plan-seed drafts, and repository code.
- Editing any named canonical artifact or the selected feedback row makes the report stale, while editing an unrelated file does not.
- A stale report is visibly rejected as the basis for a later routing decision until it is regenerated.
- The command changes no canonical roadmap artifact, feedback lifecycle state, seed-state sidecar, draft seed, or Git state apart from its explicitly declared report location and permitted command telemetry.
- The existing broad `--from-stage` command is recommended only when a deterministic owner stage is available; otherwise the output states that a schema or ownership decision is required.
- No backend is invoked in either normal or error paths, and the roadmap-focused test suite passes without credentials.
- Ordinary read-only views do not create run logs merely by inspecting an escalation report.

## Deferred

- Batch selection, related-feedback clustering, and a persistent review queue are postponed until the single-row evidence and staleness contract is correct.
- A transactional, bounded multi-artifact patch writer is postponed until observed reports demonstrate recurring structural cases and their actual relation closures.
- Executing the recommended broad command is postponed because this plan ends at evidence and operator routing.
- Reducing broad-stage prompt context is postponed as a separately evidenced follow-on.

## Input

This plan consumes the existing canonical roadmap artifact model, one feedback row selected by the stable `<artifact>:<feedback-id>` form, stable feedback and target identities, canonical target kind, artifact ownership, directly declared relations, feedback identity and lifecycle state, and the current digest of each named artifact. It also relies on the existing broad `--from-stage` command as a possible operator-selected route when a deterministic owner stage can be identified. Context estimation is limited to the selected feedback, its owning artifact and target, and the declared relation closure; unrelated artifact prose, unselected feedback, plan-seed drafts, and repository code are not inputs.
