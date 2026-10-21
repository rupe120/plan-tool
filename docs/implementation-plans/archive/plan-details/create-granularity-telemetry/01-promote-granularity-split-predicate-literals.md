> **Auto-archived**: this plan was swept on 2026-06-27 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Promote granularity split predicate literals to stable constants

## Summary

Refactor the three deterministic `granularity-split` predicate literals in
`plan_tool/granularity.py` into named module-level constants, without changing
their string values or any recommendation ids. This is the make-the-change-easy
half of the split: it creates a stable vocabulary that later steps can import,
but it does not add a recovery helper or any new telemetry behavior.

## Table of Contents

- [Summary](#summary) — what this refactor ships
- [Why](#why) — why the literals need names before telemetry consumes them
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — constants and call-site replacement
- [Constraints and Gotchas](#constraints-and-gotchas) — compatibility rules
- [Tests](#tests) — value-pinning and characterization tests
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — local code and stdlib references
- [Deferred](#deferred) — feature work left to later steps

## Why

Create-side telemetry needs to count which split smell fired, but the current
detectors spell the predicate keys inline at each `_split_rec` call site. Lifting
those literals into constants gives the codebase one named vocabulary while
preserving current behavior. The existing recommendation ids are derived from
these values, so the values are part of the compatibility contract.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/granularity.py` — add named constants for the three deterministic
    split predicate keys and route the three deterministic `_split_rec` call
    sites through them.
  - `tests/test_granularity.py` — add value-pinning tests that prove the
    constants match the current strings and that existing rec ids stay stable.

## Implementation

Add constants near the existing `GRANULARITY_SPLIT_SOURCE` declaration:

- `SPLIT_PREDICATE_MIXED_VERBS = "mixed-verbs"`
- `SPLIT_PREDICATE_CONJOINED_CLAUSES = "two-clauses"`
- `SPLIT_PREDICATE_UNRELATED_AREAS = "multi-area"`

Then replace only the three deterministic `_split_rec` predicate-key arguments:

- `_title_mixes_refactor_and_feature` uses
  `SPLIT_PREDICATE_MIXED_VERBS`.
- `_title_conjoins_clauses` uses
  `SPLIT_PREDICATE_CONJOINED_CLAUSES`.
- `_step_spans_unrelated_areas` uses
  `SPLIT_PREDICATE_UNRELATED_AREAS`.

Do not touch `parse_mixed_step_findings` in this step. The prose MIXED-STEP
producer gets its own key in step 2 when the recovery helper needs to classify
the non-deterministic producer set. Keeping this step to constant promotion
keeps it a behavior-preserving refactor.

## Constraints and Gotchas

- **Do not change the string values.** `_make_rec_id` hashes a fingerprint that
  includes the predicate key. Renaming an existing key, even to a more
  descriptive value, moves existing recommendation ids.
- **The plan body describes concepts, not literal values.** The persisted
  telemetry contract uses the real code values: `"mixed-verbs"`,
  `"two-clauses"`, and `"multi-area"`.
- **No new helper yet.** This step must not add `split_predicate_key`, an
  exported set, or create-side telemetry wiring. Those are feature work in
  later steps.

## Tests

Add or update tests in `tests/test_granularity.py`:

- `test_split_predicate_constants_have_expected_values` pins the three constant
  values exactly.
- Existing id-stability coverage stays green, proving the refactor did not move
  recommendation ids.
- A focused detector smoke test can assert a rec still emits for each predicate,
  but it should not duplicate step 2's helper recovery tests.

### Test-creation order (refactor step)

This is a refactor step. Add the value-pinning test before replacing the inline
literals, then run `uv run pytest tests/test_granularity.py -q`.

## Acceptance criteria

- `plan_tool/granularity.py` exports named constants for the three deterministic
  split predicate keys.
- The constants equal exactly `"mixed-verbs"`, `"two-clauses"`, and
  `"multi-area"`.
- The three deterministic split detectors call `_split_rec` with the constants,
  not inline string literals.
- Existing recommendation ids remain stable.
- No telemetry code, `split_predicate_key` helper, or `Recommendation` schema
  change is introduced by this step.

## References

- [hashlib — Secure hashes and message digests — Python documentation](https://docs.python.org/3/library/hashlib.html) — SHA-256 behavior behind `review._make_rec_id`, explaining why the predicate-key values are compatibility-sensitive.

## Deferred

- **Predicate recovery helper and exported vocabulary set** — step 2.
- **Create-stage `predicate_counts` wiring** — step 4.
