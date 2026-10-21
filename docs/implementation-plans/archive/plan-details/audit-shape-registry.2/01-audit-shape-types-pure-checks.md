> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add audit shape types and pure checks

## Summary

Create `plan_tool/audit_shapes.py` as the stdlib-only source of truth for five audit-shape records and their advisory eligibility. Add `tests/test_audit_shapes.py` to pin the ordered immutable registry, lookup behavior, fail-closed eligibility, and leaf-import boundary. The key decision is that eligibility comes only from registry classification, never from finding prose or an extra allowlist; step 4 copies the registry's settled records into `CLAUDE.md`, not the reverse. When green, only `arm-clustering` is eligible for a later advisory emitter.

## Table of Contents

- [Summary](#summary) — The files, design choice, and green result.
- [Table of Contents](#table-of-contents) — Links to every section.
- [Why](#why) — Why the audit-shape boundary needs code ownership.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new files and no edits.
- [Implementation](#implementation) — Registry, helpers, and leaf-module rules.
- [Tests](#tests) — Focused coverage for the new pure behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for immutable records and tests.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this step.
- [Deferred](#deferred) — Later audit-flow and documentation work.

## Why

`plan_tool/review.py:Recommendation` has no typed definition of which audit shapes may produce advice, so a later audit-flow change could turn a human judgment into an emitter through prose checks or a local string comparison. This step establishes the small, non-executable boundary before step 2 parses audit tags and evaluates arms, while keeping `Recommendation.step_id` unchanged as an execution-target field.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/audit_shapes.py` — canonical audit-shape records and pure lookup and eligibility helpers.
  - `tests/test_audit_shapes.py` — focused registry and leaf-boundary tests.

- **Existing files (edits only):**
  - None.

## Implementation

- **Make the foundational logic registry-based, fail-closed advisory eligibility.** Create `plan_tool/audit_shapes.py` with a frozen record type, such as `AuditShape`, holding a stable `id`, concise `tell`, and `classification`.

- **Export one ordered immutable registry.** `AUDIT_SHAPES` should contain exactly these settled records, in order: `arm-clustering` — tell: “Material conceptual findings form a strict-majority, contiguous proper arm of committed plan steps”; classification: `checked`. `check-saturation` — tell: “Every part is correct but no producer delivers the intended value”; classification: `judgment_only`. `measurement-instrument-adequacy` — tell: “A measurement instrument cannot see the data on which a decision relies”; classification: `judgment_only`. `self-seeded-finding` — tell: “Findings describe the prior audit edit rather than the artifact”; classification: `judgment_only`. `remedy-proportionality` — tell: “The proposed remedy outgrows the defect”; classification: `judgment_only`. Keep each tell as descriptive registry data; no helper should parse or infer meaning from tell text.

- **Provide pure, direct consumers.** Add an ID lookup such as `audit_shape_by_id()` and an eligibility predicate such as `is_advisory_emitter_eligible()`. A known ID returns the canonical record; unknown, absent, or otherwise invalid input returns no record or `False`. Derive eligibility from the registered classification so `arm-clustering` is the sole eligible shape now and no second allowlist can drift.

- **Keep the module a leaf.** Use only the standard library. Do not import `plan_tool/review.py:Recommendation`, `plan_tool/schema.py:Plan`, CLI modules, persistence code, filesystem helpers, subprocess helpers, or model-invocation code. Do not change `plan_tool/__init__.py`; later consumers should import `plan_tool/audit_shapes.py` directly.

- **Do not connect this registry to runtime behavior yet.** Leave `plan_tool/review.py:check_plan_audit()`, `plan_tool/review.py:audit_plan_until_stable()`, and `plan_tool/review_persistence.py:SavedReview` unchanged. Step 2 owns audit-tag parsing, arm evaluation, and advisory persistence; step 3 owns rendering.

## Tests

### Tests for this step

Every test below belongs in `tests/test_audit_shapes.py` and must be green before this step is complete.

- `test_audit_shapes_are_the_canonical_ordered_records` — asserts the five exact IDs, settled tells (including the count-free arm tell), classifications, and declared order.
- `test_audit_shape_records_and_registry_are_immutable` — asserts callers cannot mutate a record or reorder the registry.
- `test_audit_shape_by_id_returns_the_registered_record` — asserts a known ID returns its canonical registry object.
- `test_audit_shape_by_id_returns_no_match_for_unknown_or_missing_id` — pins the lookup’s fail-closed behavior.
- `test_only_arm_clustering_is_advisory_emitter_eligible` — asserts `True` only for the checked arm-clustering record.
- `test_judgment_only_and_unknown_shapes_are_not_eligible` — asserts every judgment-only and unknown ID returns `False`.
- `test_leaf_has_no_first_party_runtime_import` — scans `plan_tool/audit_shapes.py` so a lazy first-party import cannot bypass the leaf rule.
- `test_leaf_imports_without_other_plan_tool_modules` — loads the module through a stub `plan_tool` package and asserts no other first-party module is imported.

## Acceptance criteria

- `plan_tool/audit_shapes.py:AUDIT_SHAPES` is an ordered immutable registry with exactly five records.
- The registry classifies only `arm-clustering` as `checked`; all other planned shapes are `judgment_only`.
- `plan_tool/audit_shapes.py:audit_shape_by_id()` returns the canonical record for a known ID and no match for an unknown ID.
- `plan_tool/audit_shapes.py:is_advisory_emitter_eligible()` returns `True` only for `arm-clustering` and `False` for judgment-only or unknown IDs.
- `plan_tool/audit_shapes.py` imports no first-party `plan_tool` module, including inside helper functions.
- Every test in `tests/test_audit_shapes.py` passes.

## References

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Use frozen dataclasses for immutable registry records.
- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Cover the fixed shape-classification matrix without duplicating test structure.

## Applicable guardrails

- **The plan’s `## Plan intent`, dedicated advisory transport** — keep this step limited to non-executable classification data; do not use or extend `Recommendation.step_id`.

- **The plan’s step 1 intent, typed registry boundary** — create only the registry and pure checks, with no audit-flow, persistence, or report integration.

- **The plan’s `## Out of scope`, automation and detector fence** — do not add an emitter, gate, automatic action, historical analysis, or new detector for any shape.

## Deferred

- Audit-tag parsing, consensus, contiguous-arm evaluation, and `AuditShapeAdvisory` persistence — step 2 owns the audit-flow behavior that consumes this registry.

- Advisory rendering and count-only guidance retirement — step 3 owns report and manual-apply presentation.

- Documentation drift validation and the backlog record — step 4 owns keeping documented classifications aligned with the landed registry.

- `check-saturation` and `self-seeded-finding` emitters — remain future observable-contract work in `plan-seeds/audit-shape-saturation-and-provenance.md`.

- Measurement-instrument adequacy and remedy proportionality detectors — remain judgment-only under the plan’s scope fence.
