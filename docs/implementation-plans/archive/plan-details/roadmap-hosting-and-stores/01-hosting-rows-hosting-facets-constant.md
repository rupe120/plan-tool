# Step 1 — Add typed hosting rows to the constraints artifact

## Summary

Add a parse/render-only `hosting` collection to `ConstraintsArtifact`. It carries the fixed hosting facets but does not gate values yet; step 3 owns totality, vocabulary membership, prompt behavior, and format documentation.

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

Derived plans need hosting choices that the roadmap owns, while step 3 remains responsible for requiring and validating those choices.

## Input

`ConstraintRow.attribute` is the parser precedent: a present row's structural keys are required, while its value remains a plain string for a gate to judge later. `_iter_rows` is the collection precedent: an absent collection parses as empty.

## Files

- `plan_tool/roadmap_artifacts.py` — add the row type, artifact field, row-key registration, parsing, and rendering.
- `plan_tool/prompts/roadmap-constraints.md` — name the new key and fields in the frontmatter inventory only.
- `tests/test_roadmap_artifacts.py`, `tests/test_roadmap.py`, `tests/cli/test_roadmap_cmd.py` — extend fixtures and round-trip coverage.

## Implementation

Define `HOSTING_FACETS = ("compute", "model", "topology")` and a frozen `HostingRow(id, facet, value, product=None)`. Add `hosting: tuple[HostingRow, ...] = ()` to `ConstraintsArtifact` and register `hosting` in `CONSTRAINTS_ROW_KEYS` ahead of dispositions.

Parse a missing `hosting:` block as `()`. For every present row, require `id`, `facet`, and `value` through the existing required-string helpers. Parse `product` as optional free text. Reject it only when the facet is the known non-compute `model` or `topology`; preserve it on an unknown facet so step 3 can report the facet violation rather than hide it behind a product-placement error. This is not a vocabulary check. Render the same shape and omit an absent product.

Do not add hosting rows to `_constraints_rows`, decision-anchor resolution, feedback targeting, prose inventory, or revision continuity. Step 3 adds them only to the identity-only view used by `check_duplicate_row_ids`, preserving the existing global id rule without exposing those routes. Those integrations need end-to-end revision support and are not part of this plan.

The prompt inventory names `hosting`, `id`, `facet`, `value`, and the compute-only optional `product`, but adds no behavioral rule or worked example yet.

## Tests

- A valid hosting block round-trips and renders in `CONSTRAINTS_ROW_KEYS` order.
- Missing `hosting` parses as `()`.
- Deleting `id`, `facet`, or `value` from a present row raises `RoadmapArtifactError` naming the row.
- An unknown facet or value still parses; an unknown facet with a product also still parses so step 3 can report the named facet violation.
- A compute product round-trips; an absent product is omitted; a product on known model or topology fails parsing.
- Existing constraints and CLI fixtures remain valid without a hosting block until step 3 changes the real gate set.

## Acceptance criteria

`HostingRow` is a frozen, parse/rendered row with the stated structural contract. No gate, decision, feedback, or revision behavior changes in this step.

## Deferred

Hosting totality, values, prompt behavior, and format documentation are step 3.
