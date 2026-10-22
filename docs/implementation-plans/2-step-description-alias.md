---
format_version: 1
title: Step Description Alias
intent: New plans use `steps[].description`; existing plans using `steps[].title`
  remain readable and usable throughout the pipeline.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/step-description-alias.md
steps:
- id: 1
  title: Accept step description and legacy title with explicit dual-key validation
  intent: Both new and legacy plans retain their step text without silently discarding
    conflicting or invalid input.
  files:
  - plan_tool/schema.py
  - tests/test_parser.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/step-description-alias/01-accept-step-description-legacy-title.md
  status: current
- id: 2
  title: Emit description from both plan serializers while preserving guarded frontmatter
    replacement and body bytes
  intent: New plans and ordinary rewrites use description while existing plans remain
    writable at format version 1.
  files:
  - plan_tool/parser.py
  - tests/test_parser.py
  - tests/test_renderer.py
  - tests/test_detail.py
  - tests/test_review.py
  - tests/test_launcher.py
  - tests/test_jira.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Alias validation lets rendered description fields parse back into the unchanged
      Step.title API.
  detail: docs/implementation-plans/plan-details/step-description-alias/02-emit-description-both-plan-serializers.md
- id: 3
  title: Request description in step proposals and accept legacy responses while preserving
    existing create writes, archive moves, deletions, and rollback
  intent: Generated proposals supply the preferred step field and reach a usable plan
    through the existing authoring pipeline.
  files:
  - plan_tool/create.py
  - tests/test_create.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Proposal ingestion follows the same equal-value, conflict, and invalid-alias
      rules as plan input.
    2: Existing create entry paths reuse the canonical writer to publish description
      frontmatter.
  detail: docs/implementation-plans/plan-details/step-description-alias/03-request-description-step-proposals.md
- id: 4
  title: 'Document the version-1 alias exception and reconcile BACKLOG #517 with shipment
    status'
  intent: Readers understand the preferred spelling, legacy compatibility, dual-key
    rules, and limits of older installations.
  files:
  - PLAN_FORMAT.md
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
  depends_on_notes:
    1: Document the implemented alias rules while retaining unrelated unknown-field
      rejection.
    2: Document description-only writes, unchanged version 1, byte-preserving reads,
      and older strict-reader rejection.
    3: Mark the backlog entry plan-authored while execution is pending and remove
      it only after full shipment.
  detail: docs/implementation-plans/plan-details/step-description-alias/04-document-version-alias-exception.md
---
# Step Description Alias

## Overview

Prefer the clearer step field name while retaining title input compatibility.

## Problem statement

Bare-plan steps use `title`, but the owner selects `description` for future authoring. A prompt-only rename would generate rejected plans, so alias acceptance must precede preferred output.

## Architecture

The preferred authored step key is `description`; `title` remains accepted input. Keep plan-level and feature-level `title` meanings unchanged. Internal Python attribute renaming is not the goal; retain existing consumer APIs wherever an input/output boundary alias suffices.

Proposed dual-key policy for plan review: accept equal valid string values as one description and reject conflicting values with an actionable error. Do not silently choose one conflicting value or discard invalid input because its alias is present.

Owner decision, 2026-10-22: retain format version 1. Treat this as an additive accepted alias and preferred output spelling, with no explicit upgrade requirement. Existing absent-version and version-1 plans remain readable and writable. Revise the strict new-key break rule narrowly for this compatible alias; arbitrary unknown fields remain rejected. Document that older installations reject newly emitted `description` plans. No existing plan is bulk rewritten by this effort.

Newly serialized authored plans use only `description` for step text, including ordinary rewrites of legacy inputs. Reading alone never rewrites a file. Keep internal and unrelated persisted payload contracts stable unless an alias-specific consumer genuinely requires a change.

The final documentation/status step updates BACKLOG.md #517: mark it plan-authored while execution is pending, remove it only after full shipment, and retain any deferred follow-up.

## Scope guardrails

This effort implements BACKLOG.md #517 only. Retain format version 1 and existing-plan read/write support without an explicit upgrade. Do not add an upgrade command or weaken unrelated version/unknown-key validation. Do not bulk migrate existing plans, rename plan/feature titles, redesign execution, or rename internal step APIs merely for terminology consistency. File unrelated findings in BACKLOG.md or BUG_BACKLOG.md rather than expanding the plan.

## References

- `BACKLOG.md` #517 supplies the scope and the owner-confirmed policy exception.
- `PLAN_FORMAT.md` owns step field semantics and authored frontmatter.
- `DATA_CONTRACT.md` owns the format-version policy to amend narrowly.
- `plan_tool/schema.py` and `plan_tool/parser.py` own current strict input validation and plan serialization; their mirrored tests pin the existing contracts.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Migrating existing plans; renaming plan or feature titles; changing step meaning, execution order or detail requirements; unrelated schema cleanup.

## Risks

The current `Step` model forbids unknown keys; adding only prompt wording produces plans the parser rejects. Writer defaults and model payloads can also accidentally change persisted reports or internal contracts beyond authored plan frontmatter. Keep those boundaries explicit.

## Testing

Cover description-only and legacy title-only plans, agreeing and conflicting dual-key inputs, and read/write round trips. Verify affected detail, audit, run and Jira consumers retain the step text; update authoring examples and format-contract tests for the preferred spelling.

Verify new plans and legacy absent/version-1 declarations remain readable and writable without an upgrade. Reading preserves source bytes; ordinary plan writes emit the preferred key without changing step meaning. Pin rejection by an older strict reader as a documented limitation, not a promised compatibility property.

## Acceptance criteria

New authoring emits the preferred step key and legacy title input preserves its meaning. Dual-key behavior is deterministic and documented. Relevant consumers retain step text, and unrelated plan/feature titles and execution semantics remain unchanged. The unchanged-version alias policy has executable read/write compatibility evidence. BACKLOG.md #517 reflects authoring versus shipment accurately.

## Deferred

Unrelated schema and format-version redesign remain outside #517.
