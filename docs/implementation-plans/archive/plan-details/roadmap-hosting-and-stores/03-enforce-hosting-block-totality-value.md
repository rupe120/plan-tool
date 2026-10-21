# Step 3 — Require complete, concrete hosting answers

## Summary

Make the fixed hosting block required and vendor-neutral. Three constraints-stage gates require exactly one row for every hosting facet, a value from that facet's vocabulary, and topology that is coherent with either mixed compute or a bridge application model. The constraints prompt and format example then author the same contract.

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

The parseable hosting rows from step 1 become a reliable roadmap contract only when the constraints stage rejects incomplete or ambiguous answers. These gates keep hosting categories concrete and vendor-neutral without turning product names or deployment compatibility into gate decisions.

## Input

Step 1 has already made the rows parseable. `check_attribute_totality` is the pattern for fixed-facet totality, while the existing gate vocabulary checks are the pattern for reporting an unrecognized value as a `Violation`.

## Files

- `plan_tool/roadmap_gates.py` — add `HOSTING_FACET_VALUES`, totality and membership gates, and register them in `CONSTRAINTS_GATES`.
- `plan_tool/prompts/roadmap-constraints.md` and `ROADMAP_FORMAT.md` — state the rules, vocabulary, schema, and valid examples.
- `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py`, and `tests/cli/test_roadmap_cmd.py` — prove mutations fail and examples, including the real-orchestrator constraints fixture, clear the real gates.

## Implementation

Define the gate-owned `HOSTING_FACET_VALUES` mapping keyed exactly by `HOSTING_FACETS`: `compute` is `("per-request", "managed-containers", "long-lived", "mixed")`; `model` is `("self-hosted", "silo", "pool", "bridge")`; and `topology` is `("single-unit", "multi-unit")`. `mixed` means the application uses more than one of the other compute modes across its deployable units, without representing those units or judging their stores, and requires `topology: multi-unit`. For `model`, `self-hosted` means each tenant or group operates its own application deployment; `silo`, `pool`, and `bridge` mean that one operator respectively runs dedicated deployments, a shared multi-tenant deployment, or both. Because `bridge` records both dedicated and shared deployments, it also requires `topology: multi-unit`. These are the complete literals: the constraints prompt, `ROADMAP_FORMAT.md`, their worked examples, and membership tests reproduce the mapping and its meanings rather than choosing alternate spellings. Neither set contains an undecided member.

`check_hosting_totality` reports a missing, duplicate, or unknown facet. `check_hosting_value_membership` reports a recognized facet whose value is outside its allowed set. `check_hosting_topology_coherence` reports `compute: mixed` or `model: bridge` unless the recognized topology row is `multi-unit`; it skips an absent or unknown topology because totality or membership already reports that defect. It reads only the hosting block and never identifies a deployment unit or a store. Add hosting rows to an identity-only enumeration consumed by `check_duplicate_row_ids`, so their ids participate in the existing global id namespace without joining `_constraints_rows`, anchor resolution, feedback, prose, or revision machinery. All three hosting gates operate only on the constraints artifact and return ordinary violations.

Add concise prompt rules and a valid `hosting:` example. Add the same schema, value tables, gate rows, parse-versus-gate distinction, and valid example to `ROADMAP_FORMAT.md`. Update `_e2e_constraints_text` in `tests/cli/test_roadmap_cmd.py` with a valid hosting block, so its two real-orchestrator callers continue to clear `CONSTRAINTS_GATES`. The prompt chooses a concrete category from the brief; it does not invent vendor detail or a new pending-decision requirement.

## Tests

- A full valid block clears `CONSTRAINTS_GATES`.
- Each missing, duplicate, and unknown facet mutation returns a named violation.
- Each out-of-vocabulary value returns a named violation while parsing succeeds.
- The vocabulary equals the declared facet-to-literal mapping, its keys equal `HOSTING_FACETS`, its values are deduplicated, and no value is an undecided placeholder.
- A multi-unit application with per-request handlers and a long-lived worker uses `compute: mixed`, clears the hosting gates, and still has no compute/store comparison; `mixed` with `topology: single-unit` returns the named hosting-coherence violation.
- A bridge application model clears the hosting gates with `topology: multi-unit` and returns the same named coherence violation with `topology: single-unit`.
- A hosting id colliding with a design-row id fails the global duplicate-id gate while the hosting row remains unavailable as a feedback or decision target.
- A vendor-operated pooled hosting model and a self-hosted-per-group model are distinct valid values, proving the operator boundary is expressible without a vendor name.
- Prompt and format examples parse and clear the real gate set.
- The real-orchestrator CLI fixture includes a valid hosting block and both callers clear the constraints gate set.

## Acceptance criteria

Every accepted constraints artifact has one concrete vendor-neutral value for compute, model, and topology. No hosting gate evaluates a store, a product, a prose claim, or a deployment-unit compatibility relationship.

## Deferred

Per-unit runtime/store compatibility is BACKLOG #294. Store gates are step 4.
