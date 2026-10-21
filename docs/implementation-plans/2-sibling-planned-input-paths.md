---
format_version: 1
title: Sibling Planned Input Paths
intent: Input-contract checks accept an absent file declared for creation by an eligible
  sibling plan, while still reporting undeclared missing paths and stale symbols in
  existing files. The plan-level and detail-level checks apply the same repository-scoped
  eligibility rule.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/sibling-planned-input-paths.md
steps:
- id: 1
  title: Select eligible sibling creates from registered plans using existing roadmap
    identity
  intent: Missing-path exemptions include only creation promises from plans eligible
    to support the audited plan.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/sibling-planned-input-paths/01-select-eligible-sibling-creates.md
  status: done
- id: 2
  title: Use eligible creates in both Input checks and preserve existing-file symbol
    validation
  intent: Plan and detail Input checks accept the same eligible creation promises
    without hiding typos or stale symbols.
  files:
  - plan_tool/review.py
  - tests/test_review.py
  - tests/test_data_contract.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides read-only sibling selection that preserves own creates, repository
      containment, archived identity, and fail-closed roadmap membership.
  detail: docs/implementation-plans/plan-details/sibling-planned-input-paths/02-use-eligible-creates-both-input-checks.md
  status: done
- id: 3
  title: Document the exemption boundary and remove the source bug entry only after
    delivery
  intent: Readers understand the limited exemption and can resume the separate Integration
    experiment from verified delivery evidence.
  files:
  - DATA_CONTRACT.md
  - BUG_BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: Delivers both routes with unit rejection and exemption coverage, focused cross-module
      wiring coverage, mutation verification, and passing affected and full suites.
  detail: docs/implementation-plans/plan-details/sibling-planned-input-paths/03-document-exemption-boundary-remove.md
  status: done
---
# Sibling Planned Input Paths

## Overview

Source: BUG_BACKLOG.md, “The data-contract check reports a path another plan in the same roadmap creates as missing, so a greenfield plan's report fills with MEDIUM false positives.” This is its plan-route repair, followed by resumption of the separate Integration regeneration experiment after delivery. Existing runtime schemas and command interfaces remain unchanged.

## Problem statement

`plan_tool/review.py:_planned_paths` includes only the audited plan's step creates. Its two consumers, `check_plan_input_contract_references` and `check_step_input_contract_references`, supply that set to `data_contract.check_input_contract_references`. The saved Integration replay at `/private/tmp/integration-roadmap-plan-regeneration-20261015` reproduces eight blocking occurrences over four files declared by its connector sibling. Catalog report `20261016-003744-completeness` has zero conceptual findings; all eight diagnostics are this deterministic class. The reproduction and per-occurrence declared-path proof are in `docs/experiments/roadmap-plan-regeneration/result.json` in that isolated repository.

## Architecture

Inherit the bug's eligibility contract: for a roadmap-derived plan, use other registered plans belonging to the same roadmap; otherwise use plans registered in the repository's plan index. Use existing provenance and accepted-head contracts to establish roadmap membership, not prose resemblance or coincident filenames. No new link record, persisted field, schema or version is introduced. Unknown, malformed or unavailable identity must not silently broaden a known-roadmap plan to unrelated roadmap members. Invalid/missing sibling records provide no exemption. Leave exact helper placement and discovery mechanics to create/detail, within the existing cycle-free import constraints.

The machine-observable exemption is that the missing path is explicitly declared for creation by an eligible registered plan. It does not certify delivery, the future symbol's existence, plan quality or contract agreement. Existing files continue through ordinary symbol validation. Repository boundaries and same-roadmap isolation must hold; source-seed archival must not silently lose a valid membership when an existing reader can resolve it. Directory-only explicit-plan workflows keep the audited plan's own exemption even when no manifest exists; no recursive global plan discovery is added.

## Scope guardrails

Only widen the absent-path exemption to explicitly declared creates in the eligible repository-scoped plan set. Do not broaden semantic audit policy, weaken existing-symbol validation, accept edit-only missing files, invent provenance or change source artifacts. No new schema, CLI, version, concurrency, semantic checker or implementation of upstream Integration code.

## References

- BUG_BACKLOG.md — source entry and inherited eligibility/non-downgrade contract.
- plan_tool/review.py:_planned_paths, check_plan_input_contract_references, check_step_input_contract_references — two affected consumers.
- plan_tool/data_contract.py:_code_anchor_resolves — existing missing-path exemption and existing-symbol validation.
- tests/test_data_contract.py:test_input_contract_reference_accepts_path_the_plan_creates and test_planned_path_does_not_excuse_a_stale_symbol_on_a_real_file — existing opposite invariants.
- plan_tool/locator.py:load_manifest_plan_paths — repository manifest reader.
- plan_tool/review_persistence.py:_resolve_source_seed_path, _read_source_seed_bytes — existing archived-source resolution.
- plan_tool/roadmap_seed_state.py:locate_tracked_seed and plan_tool/roadmap_versions.py:load_accepted_version — existing durable roadmap/seed inputs to evaluate.
- DATA_CONTRACT.md, ROADMAP_FORMAT.md, PLAN_FORMAT.md, docs/ARCHITECTURE.md, TESTING.md — owning contracts, layer constraints and invoker seams.
- /private/tmp/integration-roadmap-plan-regeneration-20261015/docs/experiments/roadmap-plan-regeneration/README.md and result.json — isolated reproduction and resume evidence.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Blanket downgrading or suppressing missing-path findings; changes to conceptual prompts, audit blocking predicates, convergence policy or exit codes; accepting a typo no eligible plan creates; inferring semantic dependency/contract correctness; treating an existing file's missing symbol as future work; source/roadmap/seed mutation; implementing siblings or creating placeholders; a new dependency registry, plan provenance format, lifecycle, migration or CLI; unrelated missing-upstream behavior, source-seed writing bugs, References preservation, consolidation or cleanup.

## Risks

Overbroad sibling selection can hide typos or cross-roadmap missing dependencies. Stale or archived source identity can incorrectly widen a set. Re-reading or re-parsing the plan index per detail would multiply deterministic work. Preserve one read-only eligible set per sweep without adding a cache lifecycle or concurrency.

## Testing

Hermetic neutralized tests cover both plan and detail routes with absent own creates, eligible sibling creates, undeclared typos, cross-roadmap exclusion, repository isolation, absent/malformed sibling entries and archived-source identity. Existing-file stale-symbol validation remains rejecting even when that file appears in an eligible create set. Pin exclusion of edit-only paths and preservation of own-plan behavior with no manifest. Verify new/tightened tests by mutation. Use a small fixture matching the replay's connector/catalog relationship, not a snapshot of the full Integration project. Run affected tests and the full suite, then the normal post-run reconcile/review tail.

## Acceptance criteria

Both Input-reference routes accept the same eligible absent creates and retain the exclusion cases above. No source artifact, roadmap, manifest or seed is written by discovery. No test invokes a real model. The implementation is verified against existing tests before changing behavior; new exemption and rejection coverage fails under targeted mutation. The final docs/status step removes the originating BUG_BACKLOG entry only when the complete repair ships; during plan authoring, retain and mark the entry plan-authored. Record the original replay location and exact resume command in the handoff; do not mark its remaining seven plans complete or re-create its two existing plans.

## Deferred

Resume the saved Integration catalog detail audit after the repair is delivered, record the new tool commit, and continue the nine-plan authoring test through the previously selected order. Integration application execution remains outside that experiment. Any need for new provenance or a new shared lifecycle is separate work; surface it rather than expanding this repair.
