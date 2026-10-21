> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3c-seed-restoration.md`.
> Preserved here for history; do not edit.

## Overview

Add deterministic restoration of reviewed concept accounting when `plan-tool create` consumes modern re-baseline or carved seeds. The create flow parses and validates the versioned seed-accounting envelope before model synthesis, requires interactive review of destination ownership, and publishes matching `Step.concept_ids` and `ConceptTree` accounting through the existing synchronization/publication tail. Legacy seeds without an envelope keep the existing flow, while malformed or unsupported modern metadata and unattended restoration attempts fail before mutation.

## Problem statement

Create cannot yet restore exact reviewed accounting from modern re-baseline and carved seeds without relying on model or prose inference. That can lose, invent, or contradict concept identities and ownership, especially when mappings are ambiguous or a concept transitions between required delivery and approved non-delivery. The missing restoration path also leaves the owner-or-valid-non-delivery conservation invariant unproven across create, split, merge, re-ground/mark-done, re-baseline, scope-out, include regeneration, completeness, and reconcile operations.

## Architecture

This plan depends on shipped `concept-remediation-3a-accounting-core` and `concept-remediation-3b-lifecycle-publication` contracts. It consumes their record types, exact validation helpers, transition semantics, and shared versioned seed-accounting envelope without redefining producer formats.

Add one strict, write-free parser in `plan_tool/concept_tree.py` and run it on the original raw seed before distillation or any other model pass. A seed without an envelope follows the legacy flow; a present envelope must reject duplicate JSON keys, unknown fields, invalid types or actions, malformed source references, duplicate identities, mismatched fingerprints, and concept IDs whose canonical node projections do not recompute from required fields including `title` and `parent_path`. Producer-defined ordering is preserved, and a malformed, stale, or unsupported envelope never falls back to headings, bullets, or title matching.

Update `plan_tool/prompts/distill-seed.md` so the envelope is treated as opaque control metadata already consumed by the caller. The model must not copy, paraphrase, reinterpret, or invent its identifiers or decisions.

Restoration applicability is determined only by the validated producer action. `context_only` may supply provenance and bounded prompt context but is excluded from destination conservation; `require_delivery` enters the conservation set and needs at least one explicitly selected committed destination owner; `preserve_non_delivery` retains its exact approved record unless the operator reviews a semantic transition. Re-baseline `done_context` is excluded, `replan` requires delivery, `parked` preserves non-delivery, and carved destination concepts require delivery. A carved source defer is retired only after its matching `require_delivery` concept receives durable reviewed ownership.

Build restoration candidates from complete canonical concept-node projections and preserve exact IDs and reviewed record state. Run review only after destination change types, gates, splits, dependencies, and step IDs are settled. The operator must select ordered, non-duplicate committed owners for every `require_delivery` concept, confirm or transition every `preserve_non_delivery` record, and resolve ambiguity explicitly; ownership cannot be inferred from titles, paths, source step numbers, model-proposed `concept_ids`, or a lone apparent candidate.

`--yes` and non-TTY create cannot approve restoration choices. They refuse before archive, plan, sidecar, manifest, or other mutation and print an exact interactive resume instruction. After approval, the existing create synchronization/publication tail writes matching `Step.concept_ids` and `ConceptTree` accounting while preserving create-owned cleanup and manifest ordering on publication failure.

## Out of scope

- Producer serialization and split/merge/scope-out transforms; these belong to part 2.
- Core record schema, transition review, and completeness finding semantics; these belong to part 1.
- Automatic covering-step generation, heuristic restoration, and automatic division of one envelope among multiple new plans; these remain prohibited.

## Risks

- Invalid modern metadata could be mistaken for a legacy seed, allowing model or prose inference to replace reviewed accounting. The parser mitigates this by treating any present malformed, stale, or unsupported envelope as a pre-model, pre-mutation failure.
- Textual similarity or model-proposed `concept_ids` could assign ownership to the wrong destination step. Restoration mitigates this by preserving opaque source IDs and requiring explicit operator selection after destination steps are settled.
- Ambiguous mappings could be silently accepted, leaving dropped, invented, contradictory, or stale identities. Review must leave ambiguous mappings unresolved until the operator chooses, and unattended execution must write nothing.
- Plan ownership and concept-sidecar accounting could diverge during publication failure. The existing synchronization/publication tail must preserve create-owned cleanup and manifest ordering and prevent partial committed generations.
- A weakened `check_concept_coverage()` could make the lifecycle matrix pass despite corrupt persisted state. Integration tests pair the production policy oracle with direct persisted-state assertions.
- Recoverable publication failure and rollback-failed uncertainty can interrupt lifecycle transitions. The integration matrix explicitly exercises both failure classes and interrupted then resumed include regeneration.

## Testing

Add focused coverage in `tests/test_create.py` for parsing before model invocation, legacy seeds without an envelope, rejection of malformed or unsupported modern envelopes, exact identity and fingerprint restoration, action-table applicability, explicit mapping review, ambiguous mappings, unattended refusal, synchronized publication, and failure cleanup.

Add production-level lifecycle integration tests spanning create, detail, re-ground, scope-out, completeness, and CLI behavior. Start with multiple concepts, shared and sole owners, `defer`, `wont_do`, unsigned proposals, and reviewed records, then exercise in dependency order: create restoration from re-baseline and carved envelopes; split with one-to-many routing; merge with deterministic deduplication; re-ground/mark-done and re-baseline publication; scope-out with surviving-owner and final-owner cases; interrupted and resumed include regeneration; and completeness/reconcile after every successful transition.

Use `check_concept_coverage()` as the production policy oracle and pair it with direct persisted-state assertions. Verify exact IDs, routing, approval, fingerprints, absence of title inference, and absence of partial committed generations, including recoverable publication failure and rollback-failed uncertainty.

Run focused tests, the lifecycle integration tests, the full suite, generated-documentation drift checks, the completeness audit, and `reconcile-code`. Documentation verification covers `RUNBOOK.md`, `CLAUDE.md`, `BACKLOG.md`, and generated CLI documentation after parser or help sources are changed.

## Acceptance criteria

- Modern seed accounting is parsed and provenance-validated before any model call; malformed modern metadata never falls back to prose.
- Exact canonical `ConceptNode` state is reconstructable and independently fingerprinted; opaque IDs are never treated as reversible.
- Restoration scope follows the closed action table, including exclusion of contextual done concepts and reviewed transition of carved concepts to delivery.
- Every required mapping is explicit, ambiguous cases remain unresolved, and unattended `--yes` or non-TTY execution writes no archive, plan, sidecar, manifest, or other mutation.
- Successful create publishes matching `Step.concept_ids` and `ConceptTree` accounting; publication failure leaves no create-owned partial generation or manifest entry.
- The lifecycle integration matrix proves exact owner-or-valid-non-delivery conservation after every supported operation and exercised failure class.
- `RUNBOOK.md`, `CLAUDE.md`, `BACKLOG.md`, and generated CLI documentation match shipped command behavior, and generated rows are produced from parser or help sources rather than hand-edited.
- Focused tests, lifecycle integration tests, the full suite, generated-documentation drift checks, the completeness audit, and `reconcile-code` pass.

## Deferred

- No work within the seed-restoration and lifecycle-proof boundary is intentionally deferred.
- Producer serialization and accounting-core behavior remain prerequisites owned by `concept-remediation-3b-lifecycle-publication` and `concept-remediation-3a-accounting-core`, respectively.
