> **Archived:** this completed plan moved here on 2026-08-20 after all steps reached `done`.

---
title: Roadmap Hosting And Stores
intent: '`02-constraints.md` records how and where the application runs, and `03-components.md`
  records which store each component persists to, so a plan derived from the roadmap
  cites a store the roadmap defined instead of inventing one.'
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add typed hosting rows to the constraints artifact
  intent: Add the fixed `compute`, `model`, and `topology` hosting answers to the
    stage-2 artifact, preserving a free-text product only where compute has a concrete
    product name.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/prompts/roadmap-constraints.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-hosting-and-stores/01-hosting-rows-hosting-facets-constant.md
  status: done
- id: 2
  title: Add store definitions and component store references
  intent: Add a `stores` collection and `store_ids` on component rows so stage 3 can
    name every component's persisted or in-process store without making stores feedback
    or revision targets.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/prompts/roadmap-components.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-hosting-and-stores/02-stores-rows-store-ids-components.md
  status: done
- id: 3
  title: Require complete, concrete hosting answers
  intent: Gate the fixed hosting facets and their vendor-neutral values, then teach
    the constraints prompt and format example to produce a valid hosting block.
  files:
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-constraints.md
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-hosting-and-stores/03-enforce-hosting-block-totality-value.md
  status: done
- id: 4
  title: Require resolved, concrete store references
  intent: Gate store categories and sharing, require every component to reference
    defined stores, reject duplicate or unused definitions, and teach the components
    prompt and format example to produce that shape.
  files:
  - plan_tool/roadmap_gates.py
  - plan_tool/prompts/roadmap-components.md
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  - tests/test_roadmap_format.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-hosting-and-stores/04-enforce-stores-definition-resolution.md
  status: done
---
# Roadmap Hosting And Stores

## Overview

The roadmap currently leaves two facts to derived-plan prose: how the application runs, and which store each component persists to. This plan adds those facts to the existing stage-2 constraints and stage-3 components artifacts, then gates them. `hosting:` contains one row for each fixed facet: `compute`, `model`, and `topology`. `stores:` defines named stores; every component names one or more of them through `store_ids`, including its own `in-process` definition when it has no durable store.

The goal is a stable, machine-readable source for those decisions. It is not a deployment design engine. The roadmap records a coarse application-level answer and store categories; it does not infer whether a particular runtime/store pairing works in every deployment unit.

## Steps

The machine-readable step list is maintained in the `steps:` frontmatter.

## Problem statement

Derived plans have already invented persistence and hosting claims because no roadmap artifact owns them. In the TTRPG roadmap, a plan cited a database library while its implementation used only in-process stand-ins; another constraint is ambiguous between a shared service and software each group operates. Those choices alter the code a plan should propose, so they belong in reviewed roadmap data rather than unconstrained prose.

## Architecture

**Fields on existing artifacts, not another stage.** A store is a component property, so its ids belong on `ComponentRow`. Hosting must be available before stage 3 authors components, so it belongs on the existing constraints artifact. This plan adds no artifact, stage, filename, or CLI surface.

**Hosting is a fixed, coarse answer.** `HOSTING_FACETS` is `("compute", "model", "topology")`. `HOSTING_FACET_VALUES` is exactly: `compute` = `("per-request", "managed-containers", "long-lived", "mixed")`; `model` = `("self-hosted", "silo", "pool", "bridge")`; and `topology` = `("single-unit", "multi-unit")`. `mixed` is the concrete application-level answer when its deployable units use more than one named compute mode, and it requires `topology: multi-unit`; `model: bridge` also requires `topology: multi-unit` because it records both dedicated and shared application deployments. Neither rule identifies the units or compares them with stores. A `HostingRow` has a model-chosen `id`, its fixed `facet`, and a gate-checked `value`. The `compute` row alone may carry an optional ungated free-text `product`, such as a named cloud service; a product on a known `model` or `topology` facet is a parse error. An unknown facet and its product parse unchanged so the totality gate reports the unknown facet before a later repair can make product placement relevant.

**Stores are definitions, not design-row targets.** `STORE_CATEGORIES` is exactly `("in-process", "relational", "document", "key-value", "object")`; `STORE_SHARING_MODELS` is exactly `("silo", "pool", "bridge")`. `in-process` means component-local volatile storage during a process lifetime: it is the explicit category for a component with no durable store, rather than an absent store declaration. An accepted `in-process` definition has exactly one component owner, so a shared id never denotes shared process memory; durable-store definitions may be referenced by more than one component. A `StoreRow` has a model-chosen `id`, gate-checked `category` and `sharing` values, and optional ungated free-text `product`. Every `ComponentRow.store_ids` list references one or more of those ids. Hosting and store ids join the existing global row-id namespace through an identity-only view used by `check_duplicate_row_ids`, so they cannot collide with a design row or each other. At the components stage, that shared duplicate-id gate is the explicit cross-artifact exception: it may read hosting and store identity, but no store-specific validation reads hosting. They remain outside `_constraints_rows` and `components_design_rows`: global identity does not make them feedback targets, decision anchors, prose-inventory members, or revision-continuity subjects. `check_store_definitions` separately rejects repeated ids within one component's `store_ids` and an `in-process` id referenced by a second component.

**The two tenancy fields have different owners.** In `hosting.model`, `self-hosted` means each tenant or group operates its own application deployment; `silo` means one operator runs dedicated application deployments; `pool` means one operator runs a shared multi-tenant deployment; and `bridge` means that operator combines dedicated and shared application deployments. In a store's `sharing`, `silo` means a dedicated data resource per tenant, `pool` means one shared resource with logically partitioned tenant data, and `bridge` means the store role combines dedicated and pooled placement. A shared application service can keep one store siloed, and a self-hosted application can use a pooled local store, so no gate compares the fields. `self-hosted` is not a store-sharing value because it answers who operates the application, not how a store's data is partitioned.

**Parsing preserves recoverable defects for gates.** A missing `hosting:` or `stores:` collection, and a missing or empty component `store_ids`, parse to empty collections. The store gates then require every component to reference a defined store; a component without a durable store names an `in-process` definition that it alone references instead of relying on an empty list. A present hosting row requires `id`, `facet`, and `value`; a present store row requires `id`, `category`, and `sharing`. Missing required row keys are parse errors. An out-of-vocabulary value, including an unknown hosting facet with an optional product, parses and reaches the appropriate gate as a violation.

**Compatibility is deferred deliberately.** `compute: mixed` with `topology: multi-unit` records a multi-mode application truthfully without asserting which unit uses which mode. This plan therefore has no compute/store pair gate or compatibility matrix. BACKLOG #294 owns a future per-unit model if evidence requires that judgment.

**Existing artifacts remain parseable, but must be regenerated at the owning stage before they can pass the new gates.** A later `--from-stage` re-entry does not regenerate an earlier missing block. An operator with a missing hosting block reruns from stage 2 (or hand-edits it before re-entering later); a missing stores block reruns from stage 3.

## Scope guardrails

In scope:

- typed hosting and store rows, row-key registration, parsing, rendering, gates, prompts, format documentation, and tests;
- membership, hosting-facet totality, global row-id uniqueness, store-reference resolution, and store coverage.

## Out of scope

- A new stage or artifact, or changes to stages 1 or 4; the existing constraints and components stages own these facts.
- Feedback targeting, decision anchoring, or revision continuity for store rows; those routes need end-to-end support before stores can participate.
- A runtime/store compatibility rule, a compatibility matrix, or a per-unit deployment model; the application-level `compute` value cannot judge mixed deployment units.
- Vendor-specific gates, infrastructure-as-code, capacity, pricing, schema, physical types, indexes, migrations, or connection handling; this plan records coarse categories rather than deployment design.
- Making a product field gated or threading these fields into `create`, `detail`, `run`, or `jira`; BACKLOG #244 owns later derived-plan consumption and research of named products.
- Migration automation or changes to shared `--from-stage` behavior; operators regenerate the owning stage or hand-edit the missing block.

## References

- `ROADMAP_FORMAT.md` — defines the roadmap artifact format that the new hosting and store sections extend.
- `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` — define the existing parsing, rendering, and validation boundaries this plan extends.
- `BACKLOG.md` #244 — owns later derived-plan consumption and research of named products.
- `BACKLOG.md` #294 — owns any future per-deployable-unit runtime/store compatibility model.

## Testing

Tests use parsed artifacts and the real gate sets. They prove collection absence is parse-tolerant, present rows enforce their structural keys, values outside the vocabulary become violations, and a valid block clears its stage gates. They cover both coarse hosting topology invariants without a compute/store comparison, the parser precedence for an unknown hosting facet with a product, the distinct application and store readings of every tenancy term, the explicit single-owner `in-process` no-durable-store policy without forbidding a shared durable definition, global id collisions involving every supporting-row pairing, and mutations of each required store relationship. Prompt and format examples must parse and clear the same gates. The CLI fixtures retain valid blocks so the real orchestrator path stays covered.

## Acceptance criteria

- `02-constraints.md` can render and parse one `hosting` row for each of `compute`, `model`, and `topology`; valid values clear the hosting gates and invalid or incomplete blocks do not.
- A mixed-compute application records `compute: mixed` with `topology: multi-unit`, and a bridge application model also records `topology: multi-unit`, without a per-unit compatibility claim or a compute/store gate; either incompatible `single-unit` combination is a hosting-gate violation.
- A `compute` product is preserved without a gate; a product on a known non-compute facet is rejected at parse time, while an unknown facet with a product parses and receives the named facet violation.
- `03-components.md` can render and parse named stores and component `store_ids`; missing collections/lists parse empty, while a present store row missing a required key fails clearly.
- Every component references at least one defined store, using an `in-process` definition that it alone references when it has no durable store. A repeated id within one component's `store_ids`, a shared `in-process` id, an undefined id, an unused store, and values outside either store vocabulary are violations; a durable definition may be shared.
- Hosting and store ids are globally unique with all design-row ids, including a hosting/store collision checked by the explicit global-id exception, while the rows stay unavailable to feedback, decision-anchor, prose-inventory, and revision-continuity routes.
- `hosting.model` and `stores[].sharing` stay independently recorded and no gate compares them.
- Store rows are not accepted as feedback targets or decision anchors until a later plan implements end-to-end support.
- The constraints and components prompts and the corresponding `ROADMAP_FORMAT.md` examples state and clear the new gate contracts.

## Risks

The required fields can create ceremony when a brief is silent. The prompt must use the brief where possible and make a concrete, reviewable category choice rather than inventing vendor detail. Closed vocabulary changes re-gate old artifacts, so the vocabularies remain small and vendor-neutral. Per-unit runtime/store compatibility is intentionally not approximated by a global rule; it stays deferred until a model can represent the units it would judge.

## Deferred

- Per-deployable-unit runtime and store compatibility (BACKLOG #294).
- Feedback targeting, decision anchors, and revision continuity for stores.
- Derived-plan consumption and research of named products (BACKLOG #244).
- Automated migration of roadmaps authored before these required blocks.
