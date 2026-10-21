> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-decision-record-core.md`.
> Preserved here for history; do not edit.

# Concept Decision Record Core

## Overview

Build the minimal, authoritative concept-decision subsystem that later authoring and structural-remedy integrations can consume. This plan owns the persisted concept record, stable identity, deterministic bootstrap, three-state navigation, sign-off invalidation, stale/integrity handling, and one canonical synchronization operation that renders plan scope prose from the record. It deliberately does not wire concept collection into `create` or `detail`, does not enforce delivery coverage, and does not modify split/merge/re-ground/scope-out.

The subsystem must be useful on its own through `plan-tool scope-review`: an operator can bootstrap a record from an existing plan, review every concept, change `include` / `defer` / `wont_do`, sign the reviewed decisions, and leave the plan markdown synchronized with the machine record.

## Problem statement

The previous combined plan did not converge because identity, hierarchy, approval, prose rendering, authoring-time proposal, coverage inference, and structural remedies were specified simultaneously across several owners. In particular, parent-path-derived ids could not survive re-parenting, several commands could mutate the tree without re-rendering plan prose, and unattended review semantics conflicted with approval invalidation.

This plan establishes a small state machine and a single writer contract before any producer or remedy integration is added.

## Architecture

Persist `plan-details/<slug>/concepts.json` as a flat record. `ConceptNode.id` is an opaque stable id generated once and retained across title edits, hierarchy changes, and re-derivation. Hierarchy uses `parent_id`; duplicate sibling titles are legal because identity is not derived from title or path. A deterministic `source_key` records the originating plan bullet or step identity for bootstrap/merge matching, but it is not the primary id.

Each node has an independent `state` of `include`, `defer`, or `wont_do`. Parent changes never cascade. Mixed markers are display-only. Each node carries `signed_off` and `signed_off_at`; changing that node's state or accepting conflicting refreshed evidence clears its approval. Unchanged nodes retain existing approval during unattended runs. Only an interactive confirmation after all descendant-bearing frames have been displayed or explicitly accepted can approve reviewed nodes.

Reads distinguish missing, invalid, current, and stale records. Missing enables deterministic bootstrap. Invalid raises a typed integrity error and is never silently replaced. Stale is valid data but cannot be navigated or synchronized until explicit `scope-review --rederive` refreshes it. Re-derivation matches deterministic `source_key` first and stable id second, preserves unchanged decisions, appends new nodes unsigned, and exposes conflicts through a transient review model understood by the navigator.

One canonical operation owns record-to-plan synchronization. Given a valid current tree, it atomically writes `concepts.json`, renders every `defer` node into `## Deferred`, every `wont_do` node into `## Out of scope`, and updates mapped step scope where an explicit deterministic source mapping exists. It stages all outputs before publication and restores prior bytes on partial failure. No command may save a decision-bearing tree directly outside this operation.

## Steps

### 1. Add the stable concept record and persisted data contract

Files:
- `plan_tool/concept_tree.py`
- `plan_tool/data_contract.py`
- `DATA_CONTRACT.md`
- `tests/test_concept_tree.py`
- `tests/test_data_contract.py`

Change type: feature

Create the stdlib-only concept-tree leaf with opaque stable ids, deterministic `source_key`, independent node state, hierarchy fields, approval fields, schema versioning, atomic JSON serialization, and canonical path resolution. Define typed results/errors that distinguish missing, invalid, current, and stale records. Register `ConceptTree` and `ConceptNode` in the persisted-data contract and test malformed input, duplicate titles, re-parenting with stable ids, and exact round trips.

### 2. Add deterministic bootstrap and conflict-aware re-derivation

Files:
- `plan_tool/concept_tree.py`
- `tests/test_concept_tree.py`

Depends on: 1

Change type: feature

Seed every existing `## Deferred` bullet, `## Out of scope` bullet, and committed step without a model call. Assign deterministic source keys so refresh can match those nodes. Add a merge operation for optional enriched candidates: preserve stable ids and unchanged decisions, append new nodes unsigned, allow hierarchy enrichment without identity changes, and return explicit transient conflicts when refreshed evidence proposes a different state or incompatible source match. Invalid persisted data must stop; it must never fall through to bootstrap.

### 3. Add three-state navigation with scoped approval

Files:
- `plan_tool/concept_tree.py`
- `tests/test_concept_tree.py`

Depends on: 1, 2

Change type: feature

Implement an injected-input level-stack navigator supporting `include → defer → wont_do → include`, drill/up, explicit frame acceptance, conflict markers, and terminal confirmation. Parent state is independent and never cascades. Confirmation is blocked until all descendant-bearing/conflicted frames are reviewed or accepted. State changes clear approval before persistence; unchanged nodes keep prior approval, including under `--yes` and non-TTY. Unattended execution never creates new approval.

### 4. Add atomic concept-to-plan synchronization

Files:
- `plan_tool/concept_tree.py`
- `plan_tool/schema.py`
- `tests/test_concept_tree.py`

Depends on: 1

Change type: feature

Add the sole decision-record writer/synchronizer. It stages the record and updated plan markdown, renders `defer` and `wont_do` nodes into the canonical plan sections, applies deterministic step-scope mappings from source keys, publishes atomically or rolls back byte-for-byte, and refreshes the fingerprint only after the final plan bytes exist. Test failures at every publication boundary. Expose a narrow API that later commands must call instead of saving decisions directly.

### 5. Add the standalone scope-review command

Files:
- `plan_tool/cli/scope_review_cmd.py`
- `plan_tool/cli/app.py`
- `plan_tool/cli/__init__.py`
- `plan_tool/cli/parser.py`
- `plan_tool/cli/context.py`
- `CAPABILITIES.md`
- `docs/cli/scope-review.md`
- `docs/cli/index.md`
- `tests/cli/package_surface_help.golden.txt`
- `tests/cli/test_scope_review_cmd.py`

Depends on: 2, 3, 4

Change type: feature

Register `scope-review <name> [-y] [--rederive]`. Missing records bootstrap deterministically; current records navigate without model work; stale records fail with an actionable message unless `--rederive` is supplied; invalid records fail with integrity diagnostics. Re-derivation preserves ids/decisions and displays conflicts. Every completed mutation flows through the canonical synchronizer so JSON, plan prose, mapped scopes, and fingerprint remain aligned. Register mutation locking, capability ownership, CLI docs, help golden, and package surface.

### 6. Document the core contract and operator workflow

Files:
- `CLAUDE.md`
- `RUNBOOK.md`
- `TESTING.md`

Depends on: 5

Change type: docs

Document the leaf boundaries, stable identity rules, state/approval transition table, missing-invalid-stale behavior, canonical writer rule, and `scope-review` workflow. Explicitly reserve authoring producers, delivery coverage, and structural-remedy integration for the follow-on plan.

## Out of scope

- Model-based concept discovery during `create` or `detail`.
- Candidate-deferral extraction from detail responses.
- Delivery coverage or automatic creation of covering steps.
- Scope-out, split, merge, or re-ground integration.
- Telemetry for concept decisions.
- Automatic migration of experimental sidecars produced by the abandoned combined plan.

## Risks

- Stable opaque ids require deterministic source matching during bootstrap; tests must distinguish source keys from primary identity.
- Atomic synchronization spans plan markdown and JSON; publication-boundary failure injection is required.
- Re-derivation conflicts must remain transient review data rather than polluting the persisted node schema.
- Existing plan-section rendering must preserve unrelated prose and ordering.

## Testing

Use hermetic unit tests with injected clocks, ids, input, and filesystem failure hooks. Pin the full state-transition table, duplicate-title behavior, re-parenting identity, stale/invalid distinctions, conflict review, unattended approval preservation, and atomic rollback. Exercise the real CLI registration and mutation lock without invoking a real model backend.

## Acceptance criteria

- Stable concept ids survive title edits, re-parenting, and re-derivation; duplicate sibling titles remain distinct.
- Missing, invalid, current, and stale records have distinct typed outcomes.
- All three states are selectable and parent decisions never cascade.
- Changed decisions clear approval; unchanged decisions retain approval; unattended runs never create approval.
- Unseen descendants and unresolved conflicts cannot be globally signed off.
- Every decision mutation synchronizes JSON, plan scope prose, mapped step scope, and fingerprint atomically.
- `scope-review` works on treeless and current plans, refuses invalid/stale input appropriately, and supports explicit conflict-aware `--rederive`.
- Data-contract, CLI drift-guard, unit, and operator-workflow tests pass.

## Deferred

The follow-on `concept-signoff-integrations` plan owns authoring producers, explicit delivery linkage, completeness enforcement, and structural-remedy behavior after this contract ships.
