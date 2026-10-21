> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add tests that show which high-impact findings are non-blocking

## Summary

Add deterministic tests that identify every current `Recommendation` shape carrying `impact="high"` while remaining non-blocking under the severity-only rule. Update `tests/test_review.py` to prove how audit and reconcile parsing normalize those shapes, and update `tests/test_convergence.py` to prove the resulting normalized severities are advisory to `is_blocking`. Keep production behavior unchanged. On green, the suite gives step 2 a concrete, reproducible list of candidate findings to trace through continuation gates.

## Table of Contents

- [Summary](#summary) — The test-only outcome and green-state result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — Why the current high-impact example needs evidence.
- [Input](#input) — The recommendation and severity contracts the tests read.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two existing test files to extend.
- [Implementation](#implementation) — The parsing and blocking facts the tests must establish.
- [Tests](#tests) — Named deterministic coverage to add.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for fixtures and parser output.
- [Deferred](#deferred) — Work intentionally left to later steps.

## Why

`plan_tool/convergence.py:is_blocking` decides continuation from normalized severity alone, while `plan_tool/review.py:Recommendation.impact` can carry `high`. The proposed #152 example uses a medium-severity finding, which already blocks, so it does not prove an impact-aware augment would change anything. These tests must establish whether parser-supported `impact="high"` findings can instead normalize to `nit` or `info` and therefore currently fail to block.

## Input

- **Recommendation contract:** Read `plan_tool/review.py:Recommendation`, especially the `severity` and optional `impact` fields. Do not change its shape.
- **Severity normalization:** Exercise `plan_tool/review.py:_CLAUDE_SEVERITY_MAP` through public extraction helpers, rather than asserting against a copied mapping.
- **Continuation rule:** Use `plan_tool/convergence.py:is_blocking` as the current severity-only baseline. The tests document current behavior; they do not add an impact-aware predicate.
- **Parser paths:** Cover `plan_tool/review.py:extract_reconcile_recommendations` and the review/audit extraction path that constructs `Recommendation` instances from Claude-style findings.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `tests/test_review.py` — Add focused fixtures and assertions for high-impact findings that normalize to advisory severities through supported review and reconcile parsing paths.
  - `tests/test_convergence.py` — Add focused assertions that those normalized `nit` and `info` severities are non-blocking under `is_blocking`.

## Implementation

- **Foundational logic:** Trace a high-impact finding from parsed label to the severity-only blocking predicate.

- **Test normalized, not prompt, severity:** Build minimal Claude-style findings with `impact=high` that use the parser-supported `NIT` and unspecified-label forms. Assert the resulting `Recommendation` instances preserve `impact == "high"` while their normalized severities are `nit` and `info`, respectively. Do not treat the raw `LOW` label as non-blocking: `plan_tool/review.py:_CLAUDE_SEVERITY_MAP` folds it into `medium`.

- **Use real extraction seams:** Extend the nearby coverage for `plan_tool/review.py:extract_reconcile_recommendations` and the existing review/audit extraction tests in `tests/test_review.py`. Keep the fixtures deterministic and inject response text; no CLI or backend invocation is needed.

- **Prove the current gate result separately:** In `tests/test_convergence.py`, test `plan_tool/convergence.py:is_blocking` with the normalized advisory severities established by the review tests. Keep the assertion scoped to the existing severity-only predicate so the test records the baseline rather than implying that `impact` is already consulted.

- **Preserve the existing contract:** Do not add a predicate, alter `Recommendation`, change `_CLAUDE_SEVERITY_MAP`, or update continuation call sites. Step 2 owns tracing which live collections can receive these candidates.

## Tests

- `test_reconcile_high_impact_nit_normalizes_to_non_blocking_severity` — A `NIT` reconcile finding with `impact=high` produces `severity="nit"` and retains `impact="high"`.
- `test_reconcile_high_impact_unspecified_normalizes_to_non_blocking_severity` — An unspecified reconcile finding with `impact=high` produces `severity="info"` and retains `impact="high"`.
- `test_review_or_audit_high_impact_advisory_shapes_preserve_tags` — The review-side extraction path preserves the same high-impact advisory shapes without changing their normalized severity.
- `test_nit_and_info_are_non_blocking_under_current_rule` — `is_blocking` returns false for the normalized advisory severities identified above.
- `test_low_label_remains_medium_and_blocking` — A `LOW` finding remains a control case that normalizes to `medium`, preventing the tests from claiming it is a candidate.

### Verification (non-code step)

- Run `pytest tests/test_review.py tests/test_convergence.py`.
- Confirm the new tests use injected finding text and no production module is edited.
- Confirm the assertions distinguish raw finding labels from the normalized `Recommendation.severity` consumed by `is_blocking`.

## Acceptance criteria

- `tests/test_review.py` proves every parser-supported high-impact advisory candidate covered by this step has `impact="high"` and normalized severity `nit` or `info`.
- `tests/test_review.py` proves a `LOW` label is not a candidate because it normalizes to `medium`.
- `tests/test_convergence.py` proves `is_blocking("nit")` and `is_blocking("info")` return false.
- The targeted pytest command passes without invoking an external backend.
- No production file or `Recommendation` field changes in this step.

## References

- [Claude Code CLI reference](https://docs.anthropic.com/en/docs/claude-code/cli-usage) — Read the response-format options that define the text shape parser fixtures model.
- [Python dataclasses documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for safely inspecting and building `Recommendation` fixtures.
- [Python unittest documentation](https://docs.python.org/3/library/unittest.html) — Reference for deterministic test and fixture design.

## Deferred

- Live continuation-path reachability — Step 2 traces which completeness, reconcile, and review collections can receive the identified candidates.
- Any impact-aware predicate or call-site change — This evidence-gathering plan does not alter production behavior.
- Impact emission, schema, or prompt changes — Require separate scope if current parser paths do not supply a needed candidate.
