> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Concept Signoff Integrations
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add explicit concept ownership to plan steps
  files:
  - plan_tool/schema.py
  - plan_tool/parser.py
  - DATA_CONTRACT.md
  - tests/test_parser.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/01-explicit-concept-ownership-plan-steps.md
  status: done
- id: 2
  title: Add the evidence-only concept enrichment producer on the shipped core
  files:
  - plan_tool/concept_tree.py
  - plan_tool/shell.py
  - TESTING.md
  creates:
  - plan_tool/prompts/concept-emit.md
  - tests/test_concept_emit.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/02-evidence-only-concept-enrichment.md
  status: done
- id: 3
  title: Wire concept review and explicit ownership into create
  files:
  - plan_tool/create.py
  - plan_tool/prompts/distill-seed.md
  - tests/test_create.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/03-wire-concept-review-explicit-ownership.md
  status: done
- id: 4
  title: Add structured detail deferrals and regenerate on include
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - plan_tool/cli/authoring.py
  - tests/test_detail.py
  - tests/cli/test_authoring_cmds.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/04-structured-detail-deferrals-regenerate.md
  status: done
- id: 5
  title: Add explicit-link concept completeness findings
  files:
  - plan_tool/review.py
  - plan_tool/completeness_report.py
  - plan_tool/cli/completeness_phases.py
  - tests/test_review.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/05-explicit-link-concept-completeness.md
  status: done
- id: 6
  title: Require split remedies to preserve every concept id
  files:
  - plan_tool/create.py
  - plan_tool/detail.py
  - plan_tool/launcher.py
  - tests/test_create.py
  - tests/test_detail.py
  - tests/test_launcher.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 5
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/06-require-split-remedies-preserve-every.md
  status: done
- id: 7
  title: Make merge remedies union concept ownership
  files:
  - plan_tool/create.py
  - plan_tool/detail.py
  - tests/test_create.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 5
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/07-make-merge-remedies-union-concept.md
  status: done
- id: 8
  title: Make re-grounding preserve concept ownership
  files:
  - plan_tool/reground.py
  - tests/test_reground.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 5
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/08-make-re-grounding-preserve-concept.md
  status: done
- id: 9
  title: Make scope-out defer concepts with no surviving owner
  files:
  - plan_tool/scope_out.py
  - tests/test_scope_out.py
  - tests/cli/test_scope_out_cmd.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 5
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/09-make-scope-out-defer-concepts-no.md
  status: done
- id: 10
  title: Document concept ownership integrations and update the backlog
  files:
  - CLAUDE.md
  - RUNBOOK.md
  - CAPABILITIES.md
  - BACKLOG.md
  - docs/cli/README.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 5
  - 6
  - 7
  - 8
  - 9
  detail: docs/implementation-plans/plan-details/concept-signoff-integrations/10-document-concept-ownership-integrations.md
  status: done
---
# Concept Signoff Integrations

## Overview

This plan adds explicit concept IDs to plan steps so the tool can track which step owns each signed-off concept and report concepts that are missing an owner. Concept ownership remains backward compatible by defaulting to an empty list, then flows through create, detail generation, completeness review, and scope changes. Split, merge, re-ground, and scope-out operations must preserve ownership or record a structured deferral when no owner survives.

**Execution prerequisite:** `concept-decision-record-core` must be fully implemented before this plan starts. This plan consumes its shipped `concept_tree`, bootstrap/re-derivation, review, synchronization, and `scope-review` contracts and must not recreate or fork them.

## Problem statement

Plan steps do not currently carry explicit concept IDs, so the tool cannot reliably connect each signed-off concept to the implementation step responsible for it. That ownership gap matters because create, detail generation, completeness review, and scope-changing remedies can silently lose or redistribute conceptual commitments without a durable record. Users therefore cannot distinguish a concept that is intentionally deferred from one that was accidentally dropped, and completeness reporting cannot identify signed-off concepts with no surviving owner.

## Architecture

Concept ownership is represented on each plan step as an explicit list of concept IDs. The schema and parser treat the list as optional and default it to empty so existing plans remain valid, while the data contract validates IDs and uniqueness when ownership is present. Feature IDs and `step.features` remain the authoritative ownership link; prose labels are descriptive rather than an alternate source of ownership.

The already-shipped concept record core sits between concept discovery and plan authoring. This plan adds only an evidence-only structured producer that enriches deterministic core seeds through the core merge API; it does not create a second concept-tree model or writer. Create assigns stable core IDs to steps before publishing the plan. Detail generation consumes the same record and ownership links, may emit structured concept deferrals, and regenerates affected detail when a deferred concept is included so the plan, concept record, and detail view remain synchronized.

Completeness review compares the signed-off concept record with explicit step ownership and structured deferrals. It reports a concept only when no valid ownership or deferral link accounts for it, keeping the check deterministic instead of inferring coverage from similar prose. This review layer follows schema, producer, create, and detail support in the dependency graph because its findings rely on those durable records.

Scope-changing operations preserve the same ownership contract at their boundaries: splits distribute every source concept ID, merges take the union, re-grounding carries ownership forward, and scope-out records a structured deferral when no surviving step owns a concept. The main trade-off is additional persisted metadata and validation in exchange for traceable, machine-checkable commitments; empty ownership remains accepted for backward compatibility, while completeness findings expose the resulting gap rather than making older plans unreadable.

## References

- [Structured outputs — Claude API Docs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) — Defines schema-constrained Claude responses, strict tool inputs, validation limits, and invalid-output handling for concept and detail candidates.
- [Structured model outputs — OpenAI API](https://developers.openai.com/api/docs/guides/structured-outputs) — Documents JSON Schema-conforming model outputs for implementing the injected Codex backend and validating producer responses.
- [JSON Schema Validation: A Vocabulary for Structural Validation of JSON](https://json-schema.org/draft/2020-12/json-schema-validation) — Specifies authoritative validation semantics for typed objects, string identifiers, arrays, required fields, and uniqueness constraints.
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Covers generated data models, field defaults, default factories, and serialization-related behavior needed for backward-compatible concept ID lists.
- [concurrent.futures — Launching parallel tasks — Python documentation](https://docs.python.org/3/library/concurrent.futures.html) — Documents executors, futures, worker exception propagation, and result collection for concurrent detail generation followed by serial merging.
- [os.replace — Python documentation](https://docs.python.org/3/library/os.html#os.replace) — Defines atomic same-filesystem replacement semantics relevant to safely publishing synchronized plan, seed, and concept-record files.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Inferring concept ownership from prose — feature IDs and `step.features` remain the only authoritative ownership link.
- Requiring concept ownership on existing plans — empty ownership stays valid for backward compatibility and is surfaced by completeness review.
- Changing concept content after signoff — this plan tracks ownership and deferral of the signed-off concept set rather than revising that set.

## Risks

- Concept ownership can be silently dropped or duplicated as steps pass through create, detail, split, merge, re-ground, and scope-out flows. Severity: high. Mitigation: validate concept IDs and uniqueness at persistence boundaries and add operation-specific preservation tests. Residual gap: integrations outside these enumerated flows may still need explicit ownership handling.
- The signed-off concept record, plan ownership links, and generated detail can diverge after partial writes or interrupted regeneration. Severity: high. Mitigation: publish synchronized artifacts with atomic replacement where possible and regenerate affected detail when deferrals are included. Residual gap: atomic replacement does not provide a transaction across multiple files, so recovery must detect and reconcile mixed generations.
- Backward-compatible empty ownership can make a valid legacy plan appear conceptually incomplete. Severity: medium. Mitigation: keep parsing permissive and surface missing ownership through completeness findings rather than rejecting the plan. Residual gap: users must distinguish legacy metadata gaps from newly dropped commitments.
- Structured model output can be syntactically valid while assigning the wrong concept IDs or emitting an unjustified deferral. Severity: high. Mitigation: constrain output schemas, validate IDs against the signed-off record, and require explicit ownership or structured deferral links. Residual gap: schema validation cannot establish semantic correctness, so review remains necessary.
- Concurrent detail generation can produce nondeterministic or conflicting ownership and deferral updates. Severity: medium. Mitigation: collect worker results before a deterministic serial merge and propagate worker failures without publishing partial state. Residual gap: large plans may still expose ordering-sensitive defects unless tests cover repeated and failure-path runs.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.
- step 7 (feature) — unit tests added with the implementation; green before completion.
- step 8 (feature) — unit tests added with the implementation; green before completion.
- step 9 (feature) — unit tests added with the implementation; green before completion.
- step 10 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- Plans with omitted concept ownership continue to parse with an empty ownership list, while plans with unknown or duplicate concept IDs fail validation; `tests/test_parser.py` and `tests/test_data_contract.py` cover both cases.
- Create persists the signed-off concept record and assigns every non-deferred concept ID to at least one step before publishing the plan; `tests/test_create.py` and `tests/test_concept_tree.py` verify the persisted record and ownership links.
- Detail generation accepts only concept IDs from the signed-off record, persists structured deferrals, and regenerates affected detail when a deferred concept is included; `tests/test_detail.py` and `tests/cli/test_authoring_cmds.py` verify these outcomes.
- Completeness review reports each signed-off concept that has neither a valid step owner nor a structured deferral, and does not infer ownership from prose; `tests/test_review.py`, `tests/test_completeness_report.py`, and `tests/cli/test_completeness_cmd.py` verify the emitted findings.
- Split remedies preserve every source concept ID across their replacement steps, and merge remedies assign the union of source ownership without duplicates; `tests/test_create.py`, `tests/test_detail.py`, and `tests/test_launcher.py` verify both transformations.
- Re-grounding preserves each step's concept ownership, and scope-out records a structured deferral for every concept with no surviving owner; `tests/test_reground.py`, `tests/test_scope_out.py`, and `tests/cli/test_scope_out_cmd.py` verify both operations.
- The documented data contract and CLI guidance describe explicit concept ownership, signed-off concept records, structured deferrals, and completeness findings consistently with the implemented behavior; documentation verification covers `DATA_CONTRACT.md`, `RUNBOOK.md`, `CAPABILITIES.md`, `BACKLOG.md`, and `docs/cli/README.md`.

## Deferred

- None at this time.
