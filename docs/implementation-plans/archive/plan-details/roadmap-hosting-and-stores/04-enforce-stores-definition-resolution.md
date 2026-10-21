# Step 4 — Require resolved, concrete store references

## Summary

Make store definitions and component references required. Components must name defined stores, every store must be used, `in-process` definitions stay local to one component, duplicate store ids are rejected, and category/sharing values must be from small vendor-neutral vocabularies.

## Table of Contents

- [Summary](#summary)
- [Why](#why)
- [Input](#input)
- [Files](#files)
- [Implementation](#implementation)
- [Tests](#tests)
- [Acceptance criteria](#acceptance-criteria)
- [Deferred](#deferred)

## Why

Step 2 keeps missing and unresolved store data recoverable during parsing. This step turns those gaps into named gate violations so derived plans rely on reviewed store definitions and component references without coupling stores to hosting, feedback, or revision machinery.

## Input

Step 2 has made rows parseable. Existing component-reference and coverage gates provide the message and iteration patterns. Store-specific gates read only `ComponentsArtifact`; the existing global duplicate-id gate is the explicit identity-only exception that may read hosting ids to reject a cross-artifact collision. No store validation reads hosting semantics or revision machinery.

## Files

- `plan_tool/roadmap_gates.py` — add store vocabularies and definition, coverage, and value-membership gates to `COMPONENTS_GATES`.
- `plan_tool/prompts/roadmap-components.md` and `ROADMAP_FORMAT.md` — state the rules, vocabularies, schema, and valid examples.
- `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py`, and `tests/cli/test_roadmap_cmd.py` — prove every relationship and example, including the real-orchestrator components fixture, through the real gate set.

## Implementation

Define gate-owned `STORE_CATEGORIES = ("in-process", "relational", "document", "key-value", "object")` and `STORE_SHARING_MODELS = ("silo", "pool", "bridge")`. `in-process` means component-local volatile storage during a process lifetime. It is the explicit category for a component with no durable store, so the component still names a reviewed definition instead of using empty `store_ids`. An `in-process` definition may appear in exactly one component's `store_ids`; a second component reference is a named violation rather than an assertion of shared process memory. This ownership constraint does not restrict a durable-store definition from serving more than one component. In store sharing, `silo` means a dedicated data resource per tenant, `pool` means a shared resource with logically partitioned tenant data, and `bridge` combines dedicated and pooled placement for the store role. These terms describe data partitioning, not who operates the application; `self-hosted` is therefore not a store-sharing value. The components prompt, `ROADMAP_FORMAT.md`, their worked examples, and membership tests reproduce these tuples and meanings rather than choosing alternate spellings. Neither tuple contains an undecided value. Extend the identity-only enumeration consumed by `check_duplicate_row_ids` with store rows. At the components stage, that global gate reads hosting and store identity together, so duplicate `StoreRow.id` definitions and collisions with either design or hosting rows fail the existing global id rule without adding stores to `components_design_rows`. `check_store_definitions` rejects a component with no `store_ids`, a repeated id within its list, an undefined id, or an `in-process` id used by a second component. `check_store_coverage` rejects a defined store no component names. `check_store_value_membership` rejects an unknown category or sharing value. All violations name the relevant component or store and allowed values where appropriate.

The components prompt tells the stage to define every named store, point every component to at least one definition, use a distinct `in-process` definition when a component has no durable store, and choose concrete category and sharing values. `ROADMAP_FORMAT.md` documents the same schema and gates, including that absent collections/lists parse but the gates reject a component without an explicit store. Update `_e2e_components_text` in `tests/cli/test_roadmap_cmd.py` with valid store definitions and component references, so its two real-orchestrator callers continue to clear `COMPONENTS_GATES`. Its worked example and the prompt's example clear `COMPONENTS_GATES`.

Do not compare category or sharing with `hosting`, component behavior, cost, latency, or prose. Apart from the one-owner `in-process` rule, do not compare components' store ids. Do not make stores feedback targets or decision anchors.

## Tests

- A valid components artifact clears the new gates.
- A component that uses an `in-process` store clears the new gates as the no-durable-store case. Empty `store_ids`, an undefined id, a duplicate `StoreRow.id` definition, a store id colliding with a design-row id, a store id colliding with a hosting id, a repeated id within one component's `store_ids`, a shared `in-process` id, and an unused store each produce a named violation; the definition and repeated-reference cases exercise their separate gates, and the hosting/store collision proves the explicit global-id exception without exposing either row to target routes.
- Unknown category and sharing values produce named violations while parsing succeeds; the exact category and sharing tuples are asserted.
- A pooled application may use a siloed store, and a self-hosted application may use a pooled store; no gate compares the two tenancy fields.
- Two components may refer to different valid stores without comparison, and may share one durable-store definition; only an `in-process` definition has one component owner.
- Prompt and format examples parse and clear the real components gate set.
- The real-orchestrator CLI fixture includes valid stores and component references, and both callers clear the components gate set.

## Acceptance criteria

An accepted components artifact has unique, concrete store definitions; every component references at least one defined store; a component without a durable store uses an `in-process` definition that it alone references; and every definition is used. Products remain recorded but ungated. Store-specific gates never read `envelope.constraints.hosting`; only the shared global duplicate-id gate reads hosting identity to enforce the declared namespace.

## Deferred

No compute/store pair rule or compatibility matrix is part of this plan. Feedback and revision support for store rows remain outside it.
