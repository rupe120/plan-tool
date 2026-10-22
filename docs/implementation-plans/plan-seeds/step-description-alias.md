# Prefer step description with legacy title compatibility

Source: BACKLOG.md #517. Route: plan; tier: architect.

## Outcome

New plans use `steps[].description`; existing plans using `steps[].title` remain readable and usable throughout the pipeline.

## In scope

Step-field input aliases, authoring and serialization contracts, relevant prompts, format documentation and consumers that depend on that field. Narrowly amend the format policy to allow this compatible alias without a version bump or an upgrade requirement. Define deterministic handling when both keys occur, including conflicting values, without silently losing step content.

## Out of scope

Migrating existing plans; renaming plan or feature titles; changing step meaning, execution order or detail requirements; unrelated schema cleanup.

## Allowed behavior changes

Prefer `description` in newly authored output while preserving legacy `title` input compatibility. Document the selected serialization and duplicate-key policy explicitly.

## Allowed reorganization

None beyond changes necessary for the alias.

## Architecture

The preferred authored step key is `description`; `title` remains accepted input. Keep plan-level and feature-level `title` meanings unchanged. Internal Python attribute renaming is not the goal; retain existing consumer APIs wherever an input/output boundary alias suffices.

Proposed dual-key policy for plan review: accept equal valid string values as one description and reject conflicting values with an actionable error. Do not silently choose one conflicting value or discard invalid input because its alias is present.

Owner decision, 2026-10-22: retain format version 1. Treat this as an additive accepted alias and preferred output spelling, with no explicit upgrade requirement. Existing absent-version and version-1 plans remain readable and writable. Revise the strict new-key break rule narrowly for this compatible alias; arbitrary unknown fields remain rejected. Document that older installations reject newly emitted `description` plans. No existing plan is bulk rewritten by this effort.

Newly serialized authored plans use only `description` for step text, including ordinary rewrites of legacy inputs. Reading alone never rewrites a file. Keep internal and unrelated persisted payload contracts stable unless an alias-specific consumer genuinely requires a change.

The final documentation/status step updates BACKLOG.md #517: mark it plan-authored while execution is pending, remove it only after full shipment, and retain any deferred follow-up.

## Risks

The current `Step` model forbids unknown keys; adding only prompt wording produces plans the parser rejects. Writer defaults and model payloads can also accidentally change persisted reports or internal contracts beyond authored plan frontmatter. Keep those boundaries explicit.

## Testing

Cover description-only and legacy title-only plans, agreeing and conflicting dual-key inputs, and read/write round trips. Verify affected detail, audit, run and Jira consumers retain the step text; update authoring examples and format-contract tests for the preferred spelling.

Verify new plans and legacy absent/version-1 declarations remain readable and writable without an upgrade. Reading preserves source bytes; ordinary plan writes emit the preferred key without changing step meaning. Pin rejection by an older strict reader as a documented limitation, not a promised compatibility property.

## Acceptance criteria

New authoring emits the preferred step key and legacy title input preserves its meaning. Dual-key behavior is deterministic and documented. Relevant consumers retain step text, and unrelated plan/feature titles and execution semantics remain unchanged. The unchanged-version alias policy has executable read/write compatibility evidence. BACKLOG.md #517 reflects authoring versus shipment accurately.

## Stop / defer

Surface any required format-version or migration decision before broadening this into a rewrite of stored plans or internal step APIs.

## Scope guardrails

This effort implements BACKLOG.md #517 only. Retain format version 1 and existing-plan read/write support without an explicit upgrade. Do not add an upgrade command or weaken unrelated version/unknown-key validation. Do not bulk migrate existing plans, rename plan/feature titles, redesign execution, or rename internal step APIs merely for terminology consistency. File unrelated findings in BACKLOG.md or BUG_BACKLOG.md rather than expanding the plan.

## Overview

Prefer the clearer step field name while retaining title input compatibility.

## Problem statement

Bare-plan steps use `title`, but the owner selects `description` for future authoring. A prompt-only rename would generate rejected plans, so alias acceptance must precede preferred output.

## Deferred

Unrelated schema and format-version redesign remain outside #517.

## References

- `BACKLOG.md` #517 supplies the scope and the owner-confirmed policy exception.
- `PLAN_FORMAT.md` owns step field semantics and authored frontmatter.
- `DATA_CONTRACT.md` owns the format-version policy to amend narrowly.
- `plan_tool/schema.py` and `plan_tool/parser.py` own current strict input validation and plan serialization; their mirrored tests pin the existing contracts.
