# Step 2 — Add store definitions and component store references

## Summary

Add parse/render-only store definitions to `ComponentsArtifact` and store references to `ComponentRow`. Step 4 owns all requiredness, uniqueness, resolution, coverage, vocabularies, prompt behavior, and format documentation.

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

Derived plans need reviewed store definitions and component references instead of inventing persistence claims. This step adds that representation while preserving the existing feedback and revision boundary; step 4 separately owns its validation and authoring contract.

## Input

`constraint_ids` supplies the absence-tolerant list precedent: `_optional_id_list` makes an omitted or empty list `()`. `_iter_rows` supplies the absent-collection behavior. Stores are ordinary definitions, not additions to the design-row inventory.

## Files

- `plan_tool/roadmap_artifacts.py` — add the row type, artifact and component fields, row-key registration, parsing, and rendering.
- `plan_tool/prompts/roadmap-components.md` — name the new key and fields in the frontmatter inventory only.
- `tests/test_roadmap_artifacts.py`, `tests/test_roadmap.py`, `tests/cli/test_roadmap_cmd.py` — extend fixtures and round-trip coverage.

## Implementation

Define a frozen `StoreRow(id, category, sharing, product=None)`. Add `stores: tuple[StoreRow, ...] = ()` to `ComponentsArtifact` and `store_ids: tuple[str, ...] = ()` to `ComponentRow`. Register `stores` between component patterns and components in `COMPONENTS_ROW_KEYS`.

Parse missing `stores:` as `()` and missing or empty `store_ids` as `()`. They remain parse-tolerant so step 4 can report a named violation; the later gate requires an explicit `in-process` definition, owned by that component alone, when it has no durable store. This parse/render step permits references normally; step 4 supplies the ownership validation. A present store row requires `id`, `category`, and `sharing`; its optional `product` is free text, renders only when present, and is never gated. Values remain plain strings so step 4 can return violations rather than parser failures.

Do not add stores to `components_design_rows`, `design_row_ids`, feedback preflight, local revision, structural revision, prose inventory, or revision continuity. Step 4 adds them only to the identity-only view used by `check_duplicate_row_ids`, preserving the existing global id rule without exposing those routes. This prevents a store from being accepted as a feedback or decision target that the existing revision paths cannot edit.

The prompt inventory names `stores`, `id`, `category`, `sharing`, `product`, and `store_ids`; it does not yet require the stage to author them.

## Tests

- Stores and `store_ids` round-trip in rendered key order.
- A missing stores collection, an omitted `store_ids`, and an empty `store_ids` list each parse to `()`; step 4 will return their named missing-store violations.
- A present store row missing `id`, `category`, or `sharing` raises `RoadmapArtifactError` naming the row.
- Unknown category or sharing values parse successfully; step 4 gates them.
- `design_row_ids` omits a store id, so the existing feedback-target selection rejects it rather than offering a revision path that cannot edit stores.
- No new decision-anchor, prose, or continuity behavior is exposed.

## Acceptance criteria

The artifact exposes the stated fields with no new gate behavior. Store rows remain ordinary definitions until a later end-to-end revision design exists.

## Deferred

Store definition, coverage, and value gates are step 4. Feedback targeting, decision anchoring, and revision continuity are outside this plan.
