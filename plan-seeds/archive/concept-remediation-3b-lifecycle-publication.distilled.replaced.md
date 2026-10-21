> **Replaced**: this file has been superseded by `docs/implementation-plans/2-concept-remediation-3b-lifecycle-publication.md`.
> Preserved here for history; do not edit.

## Overview

Conserve exact ownership and reviewed non-delivery accounting through split, merge, scope-out, and re-baseline operations. Each operation prepares and validates one candidate generation before mutation, then publishes related plan, detail, sidecar, and seed changes through the public transaction/recovery API from `concept-remediation-1-publication-transactions`. The plan also defines the deterministic, reconstructable seed-accounting envelope consumed by `concept-remediation-3c-seed-restoration`, while leaving create-time restoration to that follow-on plan.

## Problem statement

Structural transforms and seed producers need one consistent way to preserve concept identity, ownership, routing, approval, artifact paths, and reviewed non-delivery state. Without a validated candidate and atomic publication, dry-run and apply can disagree, scope-out can treat an unsigned transition as valid accounting, and failures can leave ambiguous generations or seed orphans. Existing CLI and convergence surfaces also imply that `-y` can approve a carve, even though final-owner removal requires explicit review.

## Architecture

This plan requires `concept-remediation-3a-accounting-core` to be shipped and consumes its `NonDeliveryRecord`, routing fields, candidate-publication validator, transition policy, and accounting helpers without redefining them. It also consumes the public transaction/recovery API from `concept-remediation-1-publication-transactions` and produces the exact seed-accounting envelope consumed by `concept-remediation-3c-seed-restoration`.

Split and merge extend the existing exact-ownership path. Split prepares replacement steps, ownership distribution, non-delivery routing, and detail renames before writing; remaps ordered `linked_step_ids` across selected children while preserving `record_id` and immutable `origin_ref`; updates `artifact_ref`; and publishes the plan, details, and sidecar together. Merge maps members to the surviving step, preserves external many-owner semantics, deterministically deduplicates routing links and equivalent records, updates artifact paths, preserves approval for routing-only remaps, and requires review for semantic changes. Dry-run and apply share candidate preparation and never infer identity from titles.

Scope-out uses the part-1 structured non-delivery transition when removing a concept's final committed owner. Explicit review is required before mutation; non-TTY or `--yes` execution without reviewed inputs refuses and prints an exact resumable scope-review/scope-out command. The carved seed, narrowed plan, migrated details, and reviewed concept candidate are submitted as one typed prerequisite transaction, with recoverable failures restoring the original generation and seed absence and rollback failures reporting every uncertain path through transaction recovery.

Re-baseline and carved-seed producers share one versioned, clearly delimited JSON envelope. It carries a format discriminator and schema version; source kind, plan path, plan fingerprint, and complete concept-record fingerprint; canonical `ConceptNode` projections including `title`, `parent_path`, decision/review state, evidence, and supported metadata; ordered source-step accounting; structured non-delivery records; the prepared post-operation projection where applicable; and one validated restoration action per relevant concept. Because `ConceptNode` validation recomputes IDs from `title` and `parent_path`, opaque IDs and prose are not reconstruction fallbacks.

The restoration vocabulary is `context_only`, `require_delivery`, and `preserve_non_delivery`. Re-baseline maps `done_context -> context_only`, `replan -> require_delivery`, and `parked -> preserve_non_delivery`, independently of `defer`/`wont_do`. Carved destination concepts use `require_delivery`; the source plan's approved defer record remains signed transition provenance rather than active destination non-delivery. Serialization uses a documented format tag, UTF-8 encoding, canonical key/separator rules, preserved authored list order, and golden digest vectors, while renderers receive already-prepared projections and remain pure.

Implementation surfaces are `plan_tool/concept_tree.py`, `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/scope_out.py`, `plan_tool/reground.py`, `plan_tool/cli/scope_out_cmd.py`, and `plan_tool/cli/convergence_cmd.py`.

## Out of scope

- The persisted accounting model and completeness policy belong to part 1.
- Parsing envelopes, create-time mapping/review, and lifecycle integration/docs belong to part 3.
- Heuristic title/path matching and automatic destination-step invention are prohibited rather than deferred.

## Risks

- Split or merge can drop, invent, duplicate, or leave dangling concept ownership and routing. Mitigation: validate the complete candidate before writing, preserve immutable identities, deterministically deduplicate equivalent links and records, and require dry-run and apply to report the same exact distribution.
- Scope-out can remove the final committed owner without valid reviewed accounting. Mitigation: require the part-1 structured transition and explicit review; refuse non-TTY or `--yes` execution without reviewed inputs before mutation.
- A publication failure can leave a seed orphan or an uncertain generation. Mitigation: publish all related artifacts in one prerequisite transaction, restore the original generation and seed absence on recoverable failure, and report every uncertain path plus transaction-recovery guidance when rollback fails.
- An envelope containing only opaque concept IDs cannot reconstruct `ConceptNode` state. Mitigation: carry canonical node projections, include them in the documented fingerprint, and prohibit prose as an identity fallback.
- Stale, malformed, blocked, declined, dry-run, recommend-only, or non-TTY paths could mutate persisted state. Mitigation: these paths write nothing.

## Testing

Add focused split, merge, scope-out, re-ground, and CLI tests. Verify exact ownership and routing conservation, shared dry-run/apply candidate preparation, reviewed scope-out transitions, atomic transaction recovery, deterministic envelope parsing, complete reconstructable `ConceptNode` projections, restoration-action mapping, and carved-destination transition semantics. Cover canonical serialization with golden digest vectors. The full suite, completeness audit, and `reconcile-code` must pass.

## Acceptance criteria

- Split and merge conserve exact concept IDs, record IDs, approval, artifact paths, and one-to-many routing without dangling removed steps.
- Dry-run and apply expose the same prepared distribution and reject invented or dropped IDs before writing.
- Scope-out never treats an unsigned transition as valid accounting and never publishes a seed orphan through the normal recoverable-failure path.
- Every modern seed contains one parseable deterministic envelope with complete reconstructable concept projections and explicit restoration actions.
- Re-baseline role/action mapping and carved-destination transition semantics are unambiguous and golden-tested.
- All generation changes use the prerequisite transaction and recovery result types.
- Focused tests, the full suite, completeness audit, and `reconcile-code` pass.

## Deferred

- Create-time parsing, mapping review, restoration, and lifecycle proof are dependency-ordered follow-on work assigned to `concept-remediation-3c-seed-restoration`.
- No work inside the lifecycle-publication boundary is intentionally deferred.
