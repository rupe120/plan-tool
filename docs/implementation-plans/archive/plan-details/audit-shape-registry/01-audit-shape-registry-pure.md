> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

# Step 1 — Add the audit-shape registry and pure classification helpers

## Summary

Create `plan_tool/audit_shapes.py` as a stdlib-only source of truth for the five audit-shape IDs, their tells, and their classifications. Add `tests/test_audit_shapes.py` to pin the ordered immutable registry and its fail-closed eligibility helpers. The key design decision is that classification data, not prose matching or report logic, decides whether a shape may emit advisory output. When the tests are green, only `arm-clustering` is eligible for a future advisory emitter.

## Table of Contents

- [Summary](#summary) — What this step adds and the green result.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — Why the audit-shape boundary needs code ownership.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files created and confirmation that no existing files change.
- [Implementation](#implementation) — Registry, helper, and leaf-module rules.
- [Tests](#tests) — Focused coverage for the registry boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Standard-library and test references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Related work left to later steps or plans.

## Why

The codebase has `plan_tool/review.py:recommend_audit_passes()` for pass-count advice, but no code-owned definition of which audit shapes are measurable and allowed to advise. A small immutable registry makes the checked-versus-judgment-only boundary explicit before any report code consumes it, so a later emitter cannot quietly turn a human judgment into a detector.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/audit_shapes.py` — canonical audit-shape registry and pure lookup and eligibility helpers.
  - `tests/test_audit_shapes.py` — focused registry, fail-closed, and leaf-import tests.

- **Existing files (edits only):**
  - None.

## Implementation

- **Create one canonical record type.** In `plan_tool/audit_shapes.py`, add a frozen `AuditShape` dataclass with stable `id`, human-readable `tell`, and `classification` fields. Keep the record limited to registry facts; do not add report text, severity, blocking, persistence, or remedy fields.

- **Keep the registry ordered and immutable.** Export `AUDIT_SHAPES` as the single tuple of `AuditShape` records. Its fixed order and classifications are:
  - `arm-clustering` — `checked`.
  - `check-saturation` — `judgment_only`.
  - `measurement-instrument-adequacy` — `judgment_only`.
  - `self-seeded-finding` — `judgment_only`.
  - `remedy-proportionality` — `judgment_only`.

- **Keep tells descriptive only.** Give every record one concise tell drawn from the plan’s settled shape description. Helpers must never parse tell text or infer a classification from it.

- **Expose fail-closed pure helpers.** Add a by-ID lookup such as `audit_shape_by_id()` and an eligibility predicate such as `is_advisory_emitter_eligible()`. A known ID must return its canonical record; an unknown, missing, or unclassified ID must produce no record or `False`, never an inferred eligible result. Derive eligibility from the registry classification so there is no second allowlist that can drift.

- **Make the module a true leaf.** `plan_tool/audit_shapes.py` may use only the standard library. Do not import `plan_tool/review.py:Recommendation`, CLI modules, report modules, an invoker, or filesystem and subprocess helpers. Do not re-export the new symbols through `plan_tool/__init__.py`; later consumers should import this small module directly.

- **Leave report behavior for the next step.** No current production call site changes in this step. Step 2 owns importing the helper into the audit flow and adding the arm-clustering evaluator and advisory; this step supplies only the boundary it will consult.

## Tests

### Tests for this step

All cases below belong in `tests/test_audit_shapes.py` and must be green before this step is complete.

- `test_registry_has_the_canonical_five_shapes_in_order` — asserts the five IDs, their classifications, and one non-empty single-line tell per record.
- `test_registry_entries_are_immutable` — asserts both the registry sequence and its records cannot be mutated.
- `test_audit_shape_by_id_returns_the_canonical_record` — asserts a known ID returns the registered object and an unknown ID has no match.
- `test_only_arm_clustering_is_advisory_emitter_eligible` — asserts the checked shape is eligible and every judgment-only shape is not.
- `test_unknown_shape_is_not_advisory_emitter_eligible` — pins the fail-closed result for an unrecognized ID.
- `test_leaf_has_no_first_party_runtime_import` — scans `plan_tool/audit_shapes.py` so a lazy first-party import cannot bypass the leaf rule.
- `test_leaf_imports_without_other_plan_tool_modules` — imports `plan_tool/audit_shapes.py` through a stub package in a subprocess and asserts it loads no other `plan_tool` module.

## Acceptance criteria

- `plan_tool/audit_shapes.py:AUDIT_SHAPES` is an ordered immutable registry with exactly the five planned stable IDs and classifications.
- `plan_tool/audit_shapes.py:audit_shape_by_id()` returns the registered shape for a known ID and no match for an unknown ID.
- `plan_tool/audit_shapes.py:is_advisory_emitter_eligible()` returns `True` only for `arm-clustering` and returns `False` for every judgment-only or unknown shape.
- `plan_tool/audit_shapes.py` has no first-party `plan_tool` import at module scope or inside a helper.
- Every test in `tests/test_audit_shapes.py` passes.

## References

- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) — Use frozen dataclasses for immutable registry records.
- [Python unittest documentation](https://docs.python.org/3/library/unittest.html) — Reference for focused behavior-boundary tests.

## Applicable guardrails

- **The plan intent, advisory classification boundary** — encode the current allowed advisory eligibility without adding a decision about whether any arm, producer, instrument, or remedy is correct.

- **The step intent, executable five-shape boundary** — limit this step to registry data and pure classification helpers; do not connect them to an audit run or report.

- **The plan’s `## Out of scope`, detector and automation fence** — do not add emitters for deferred shapes, persistence, Git analysis, gates, exit-code behavior, mutation, or automatic remediation.

## Deferred

- `plan_tool/review.py:recommend_audit_passes()` and `plan_tool/convergence_diagnosis.py:diagnose_convergence()` — these pass-count and cross-report diagnoses are related but are not audit-shape classification; leave them unchanged here.

- Arm-clustering detection and report advice — step 2 consumes this registry to add the within-report advisory.

- Documentation/registry drift validation and the bounded BACKLOG record — step 3 owns the documented classification check and follow-up record.

- Check-saturation and self-seeded emitters — `plan-seeds/audit-shape-saturation-and-provenance.md` owns any future observable-contract investigation.

- Measurement-instrument adequacy and remedy proportionality detectors — remain judgment-only under the plan’s scope fence.
