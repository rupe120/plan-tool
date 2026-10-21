> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-signoff-integrations.md`.
> Preserved here for history; do not edit.

# Concept Signoff Integrations

## Overview

Integrate the shipped Concept Decision Record Core into `create`, `detail`, completeness auditing, and structural remedies. This plan consumes the core's stable ids, deterministic bootstrap/merge, approval rules, conflict review, and canonical synchronizer; it does not redefine them.

The central integration decision is explicit delivery ownership: committed steps carry stable concept ids. Heuristic title/body matching may propose links, but only explicit ids satisfy blocking coverage. This makes the “included concepts cannot be silently dropped” guarantee deterministic and preserves it across title changes and structural remedies.

## Problem statement

The earlier combined design attempted to infer coverage from titles, features, and detail prose while also promising guaranteed delivery. It allowed later surfaces to mutate the concept record without synchronizing plan prose and allowed post-authoring decisions to contradict already-authored details. Structural remedies had no authoritative ownership contract.

With the core state machine isolated, this plan can focus on producer and consumer behavior and on explicit concept-to-step linkage.

## Architecture

Extend committed steps with `concept_ids: list[str]` (or an equivalent persisted field selected consistently in schema and data-contract documentation). The ids refer to stable core `ConceptNode.id` values. Candidate generation may recommend ownership, but operator confirmation or deterministic structural transformation establishes it. Completeness treats only explicit links on committed/done steps as coverage; heuristic matches are advisory suggestions and never suppress a blocking uncovered-concept finding.

`create` deterministically seeds required concepts, optionally enriches them through an injected backend, obtains operator decisions before final plan synthesis, assigns included concept ids to proposed committed steps, and finalizes through the core synchronizer. Emit/enrichment failure cannot erase deterministic seeds or bypass review; unattended runs persist unsigned proposals.

`detail` has two distinct phases. Before authoring, it reads the current synchronized scope and supplies it to every serial/concurrent prompt. Each response returns a structured candidate-deferral block. After authoring, candidates merge into the tree unsigned. The post-authoring review may confirm deferral/won't-do immediately; changing a candidate to include requires regenerating the affected detail before synchronization succeeds. Malformed candidate output is a failure for that result when its body contains deferred material, not a silent skip.

Structural remedies transform explicit ownership. Split partitions concept ids among replacements and requires every source id to appear on at least one child. Merge unions ids. Re-ground preserves ids. Scope-out removes the carved ownership, changes sole-owned included concepts to defer, clears their approval, writes them to the forward seed in canonical `## Deferred`, and synchronizes atomically. Operator approval is never preserved across the include-to-defer change.

## Steps

### 1. Add explicit concept ownership to the step schema

Files:
- `plan_tool/schema.py`
- `plan_tool/data_contract.py`
- `DATA_CONTRACT.md`
- `tests/test_schema.py`
- `tests/test_data_contract.py`

Change type: feature

Add the persisted concept-id ownership field with backward-compatible empty defaults, validation against string ids, serialization, and data-contract documentation. Define committed and done steps as valid owners; deferred/won't-do steps cannot satisfy delivery coverage. Add helpers for union, partition validation, and dangling-id diagnostics.

### 2. Add the evidence-only concept producer and deterministic merge envelope

Files:
- `plan_tool/concept_tree.py`
- `plan_tool/prompts/concept-emit.md`
- `plan_tool/shell.py`
- `TESTING.md`
- `tests/test_concept_tree.py`

Depends on: 1

Change type: feature

Add an injected Codex/Claude-backend producer that can enrich deterministic core seeds and propose concept-to-step ownership. Validate structured output, retain every deterministic seed, preserve stable ids/decisions through the core merge, and represent proposed ownership separately until accepted. Backend failure returns the deterministic seed plus a warning rather than no tree. Update the real-backend neutralization contract.

### 3. Wire pre-finalization concept decisions and ownership into create

Files:
- `plan_tool/create.py`
- `plan_tool/prompts/distill-seed.md`
- `tests/test_create.py`

Depends on: 1, 2

Change type: feature

Run deterministic seed plus optional enrichment before final plan synthesis. Review concepts interactively when possible, apply explicit accepted ownership to proposed committed steps, render scope from the core synchronizer, and fingerprint only final bytes. Unattended runs retain unsigned proposals and do not claim operator approval. Producer failure cannot omit deterministic seed nodes or finalize through an unreviewed silent-drop branch.

### 4. Add structured detail candidates with regeneration on include

Files:
- `plan_tool/detail.py`
- `plan_tool/prompts/detail.md`
- `plan_tool/cli/authoring.py`
- `tests/test_detail.py`

Depends on: 2, 3

Change type: feature

Before authoring, inject current synchronized concept scope and ownership into every serial and concurrent prompt. Require each result to return structured candidates for every item routed to `## Deferred` or `## Out of scope`; reject a result whose candidate block is malformed or inconsistent with its prose. Merge candidates serially after worker join. A post-authoring choice of defer/won't-do synchronizes normally; choosing include schedules regeneration of affected details with the new scope, then revalidates that the deferred prose disappeared before final synchronization. Never mutate the shared record inside a worker.

### 5. Add deterministic explicit-link completeness checks

Files:
- `plan_tool/review.py`
- `plan_tool/completeness_report.py`
- `plan_tool/cli/completeness_phases.py`
- `tests/test_review.py`

Depends on: 1, 3, 4

Change type: feature

Add blocking findings for a signed-off included concept with no explicit committed/done owner, dangling step concept ids, and invalid ownership by deferred/won't-do steps. Add advisory heuristic suggestions that may recommend ownership links but never count as coverage. Add unsigned-deferral and stale/integrity reporting using the core typed read outcomes. Keep passive audits read-only and inert when no record exists.

### 6. Preserve explicit ownership across split, merge, and re-ground

Files:
- `plan_tool/detail.py`
- `plan_tool/launcher.py`
- `plan_tool/create.py`
- `tests/test_detail.py`
- `tests/test_launcher.py`
- `tests/test_create.py`

Depends on: 1, 5

Change type: feature

Require split proposals to partition every source `concept_id` among replacement children; reject loss or unknown ids. Merge replacements receive the ordered union. Re-ground preserves ids exactly. Add end-to-end remedy tests proving coverage remains satisfied after title changes and renumbering because ownership is id-based rather than slug-based.

### 7. Make scope-out defer sole-owned concepts and invalidate approval atomically

Files:
- `plan_tool/scope_out.py`
- `tests/test_scope_out.py`

Depends on: 1, 5

Change type: feature

When carving steps, find concept ids with no surviving committed/done owner. Change those concepts from include to defer, clear `signed_off` and `signed_off_at`, include them as ordinary bullets under the forward seed's canonical `## Deferred`, and publish the narrowed plan, seed, and synchronized record through an all-or-recoverable transaction. Concepts with surviving owners remain included and signed as before.

### 8. Reconcile CLI/docs and retire the superseded backlog item

Files:
- `CLAUDE.md`
- `RUNBOOK.md`
- `CAPABILITIES.md`
- `BACKLOG.md`
- `docs/cli/index.md`

Depends on: 5, 6, 7

Change type: docs

Document authoring integration, explicit ownership, detail regeneration, completeness findings, and structural-remedy behavior. Update capability surfaces and retire the relevant backlog entry only after verifying every named production surface exists.

## Out of scope

- Redefining stable concept identity, navigation, approval semantics, or canonical synchronization from the core plan.
- Heuristic matches counting as delivery coverage.
- Automatic creation of new implementation steps from uncovered concepts.
- Concept-decision telemetry.
- Migrating arbitrary experimental sidecars lacking stable core ids.

## Risks

- Adding a persisted step field affects schema/data-contract compatibility and every structural rewrite.
- Detail regeneration can loop if generated prose repeatedly contradicts structured candidates; cap attempts and fail with an actionable unresolved-candidate report.
- Split partition proposals must be validated before mutation to prevent ownership loss.
- Concurrent detail generation must collect candidates in workers but merge and synchronize only in the serial parent.

## Testing

Use explicit-id fixtures rather than title coincidences. Test create failure/unattended paths, serial and concurrent detail collection, malformed candidate rejection, include-triggered regeneration, blocking uncovered/dangling ownership, advisory-only heuristics, title changes, and all four structural remedies. Inject filesystem failures for scope-out transaction boundaries and model invokers for all producer paths.

## Acceptance criteria

- Every signed-off included concept is covered only by an explicit id on a committed/done step; heuristic matches never suppress findings.
- Create cannot silently lose deterministic concepts when enrichment fails.
- Detail candidates exactly mirror deferred/out-of-scope prose, and choosing include regenerates affected artifacts before completion.
- Concurrent workers never write the shared record.
- Split partitions, merge unions, and re-ground preserves concept ownership without coverage loss.
- Scope-out defers only concepts lacking surviving owners, invalidates their prior approval, emits canonical deferred seed bullets, and rolls back partial publication.
- All schema, data-contract, create, detail, completeness, structural-remedy, CLI, and documentation tests pass.

## Deferred

Automatic covering-step generation and concept-decision telemetry remain separate future work.
