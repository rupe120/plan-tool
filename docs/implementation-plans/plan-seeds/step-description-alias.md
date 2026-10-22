# Prefer step description with legacy title compatibility

Source: BACKLOG.md #517. Route: plan; tier: architect.

## Outcome

New plans use `steps[].description`; existing plans using `steps[].title` remain readable and usable throughout the pipeline.

## In scope

Step-field input aliases, authoring and serialization contracts, relevant prompts, format documentation and consumers that depend on that field. Define deterministic handling when both keys occur, including conflicting values, without silently losing step content.

## Out of scope

Migrating existing plans; renaming plan or feature titles; changing step meaning, execution order or detail requirements; unrelated schema cleanup.

## Allowed behavior changes

Prefer `description` in newly authored output while preserving legacy `title` input compatibility. Document the selected serialization and duplicate-key policy explicitly.

## Allowed reorganization

None beyond changes necessary for the alias.

## Architecture

The preferred authored step key is `description`; `title` remains accepted input. Keep plan-level and feature-level `title` meanings unchanged. Internal Python attribute renaming is not the goal; retain existing consumer APIs wherever an input/output boundary alias suffices.

Proposed dual-key policy for plan review: accept equal valid string values as one description and reject conflicting values with an actionable error. Do not silently choose one conflicting value or discard invalid input because its alias is present.

The format-version decision below must be settled before `create`. Once settled, the plan owns the compatible read/write transition before new authoring emits the key. No existing plan is bulk rewritten by this effort.

The final documentation/status step updates BACKLOG.md #517: mark it plan-authored while execution is pending, remove it only after full shipment, and retain any deferred follow-up.

## Risks

The current `Step` model forbids unknown keys; adding only prompt wording produces plans the parser rejects. Writer defaults and model payloads can also accidentally change persisted reports or internal contracts beyond authored plan frontmatter. Keep those boundaries explicit.

## Testing

Cover description-only and legacy title-only plans, agreeing and conflicting dual-key inputs, and read/write round trips. Verify affected detail, audit, run and Jira consumers retain the step text; update authoring examples and format-contract tests for the preferred spelling.

Verify the selected format transition against both new plans and legacy absent/version-1 declarations, including the operator-visible result before and after any explicitly requested upgrade. The transition may not silently migrate an existing file.

## Acceptance criteria

New authoring emits the preferred step key and legacy title input preserves its meaning. Dual-key behavior is deterministic and documented. Relevant consumers retain step text, and unrelated plan/feature titles and execution semantics remain unchanged. The approved format transition has executable compatibility evidence. BACKLOG.md #517 reflects authoring versus shipment accurately.

## Stop / defer

Surface any required format-version or migration decision before broadening this into a rewrite of stored plans or internal step APIs.

## Scope guardrails

This effort implements BACKLOG.md #517 only. Do not bulk migrate existing plans, rename plan/feature titles, redesign execution, or rename internal step APIs merely for terminology consistency. File unrelated findings in BACKLOG.md or BUG_BACKLOG.md rather than expanding the plan.

## Decision required before creation

DATA_CONTRACT.md's authored-plan break rule requires a version bump before any writer emits a new frontmatter key. Its current writer eligibility refuses effective-older plans, and its first-refusal obligation requires an operator-invocable upgrade route and shared compatibility preflight before affected mutating commands change state.

Proposed owner decision: include format v2 plus that explicit upgrade/preflight path in #517, preserving v1 reading and leaving existing files untouched until the operator requests an upgrade. This extends the original no-migration fence only for an explicitly requested upgrade; automatic and bulk migration remain excluded. Owner confirmation is pending; do not run `create` against this draft until it is settled.
