> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Single-source the structural-finding predicate behind `review.is_structural`

## Summary

- Add a `STRUCTURAL_SOURCES` frozenset + `is_structural(rec)` predicate to `plan_tool/review.py`, seeded with the one structural source that exists at HEAD: `granularity-split` (the live source produced by `plan_tool/granularity.py`, surfaced through detail's MIXED-STEP purity check).
- **Introduce the predicate only — add no consumer.** No call site routes through `is_structural` in this step; `triage_reason` is left untouched. That makes this a genuinely behavior-preserving move (the new predicate is dead until step 2 wires it in).
- **Pure refactor, behavior-preserving** — no command output changes, no new finding rendering. Routing `triage_reason` through `is_structural` and giving structural findings a split-specific message is step 2's job (a `feature`), deliberately kept out of this step.
- On green: `is_structural(rec)` is the single place that answers "is this a split-worthy structural finding," `granularity-split` stays out of `APPLY_ELIGIBLE_SOURCES`, and every existing `triage_reason` test passes unchanged (nothing routes through the new predicate yet).

## Table of Contents

- [Summary](#summary) — what this step does and the observable result
- [Why](#why) — the soon-to-be-duplicated predicate this single-sources
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the predicate pair (no `triage_reason` change)
- [Tests](#tests) — predicate + invariant tests
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — pin existing behavior, add predicate tests
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — what later steps own

## Why

- The rule "this finding's only fix is to split a step, not an apply edit" has no single home in `review.py` today. Steps 2, 4, 7, and 8 all need to ask the same question (render a split recommendation, route a `BLOCKED-STRUCTURAL` verdict, gate the escalate bridge). Without a predicate, each consumer would repeat a `rec.source == "granularity-split"` literal, and the source set would drift the moment step 2 adds `structural-split`.
- Single-sourcing the predicate now — before any consumer is added — means later steps extend one frozenset, not hunt down scattered `== "granularity-split"` compares. This mirrors the existing `APPLY_ELIGIBLE_SOURCES`/`is_apply_eligible` and `AUDIT_FIX_SOURCES`/`audit_targeted_fix` pairs already in `review.py`.
- This step is the plan's deliberate **refactor-first** move: the predecessor plan bundled the predicate's introduction with the new structural *output* and was BLOCKED for refactor+feature impurity. Keep this step output-silent — predicate only, no consumer.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `STRUCTURAL_SOURCES` frozenset + `is_structural(rec)` predicate beside the existing `APPLY_ELIGIBLE_SOURCES`/`is_apply_eligible` pair. Do **not** edit `triage_reason` in this step.
  - `tests/test_review.py` — add predicate + disjointness tests in the `TestApplyTriage` class.

## Implementation

### `plan_tool/review.py`

- **Add the source set + predicate as a contiguous pair**, placed directly after `is_apply_eligible` and before the `AUDIT_FIX_SOURCES` block — the same set+predicate idiom those neighbors use:

  ```python
  # Sources whose only correct fix is to split a step into two type-pure
  # steps, not an apply edit. ``granularity-split`` is the live producer at
  # HEAD (``plan_tool/granularity.py``'s split detectors + the MIXED-STEP
  # purity kernel, surfaced through detail); step 2 adds ``structural-split``
  # (the escalate bridge's recommend-only source). Kept independent of
  # APPLY_ELIGIBLE_SOURCES (a structural source is never apply-eligible) — the
  # disjointness is pinned by test, not derived here.
  #
  # The "granularity-split" string is duplicated from
  # ``granularity.GRANULARITY_SPLIT_SOURCE`` deliberately, NOT imported:
  # ``granularity`` imports ``review`` (Recommendation/_make_rec_id), so the
  # reverse import would cycle. Keep the literal in sync with that constant; a
  # test pins the value so a future rename of the granularity source is caught.
  STRUCTURAL_SOURCES: frozenset[str] = frozenset({"granularity-split"})


  def is_structural(rec: Recommendation) -> bool:
      """True when ``rec``'s only correct fix is to split its step into two
      (see :data:`STRUCTURAL_SOURCES`). These route to the split bridge, not
      ``apply_finding``; step 2 gives them a split-specific ``triage_reason``."""
      return rec.source in STRUCTURAL_SOURCES
  ```

- **Do not touch `triage_reason`.** At HEAD a `granularity-split` rec (non-apply-eligible) already flows through `triage_reason`'s generic `if not is_apply_eligible(rec):` arm and gets the "structural diagnostic — not auto-fixable" text. Re-pointing it through `is_structural` to a split-specific message is a **behavior change** and belongs to step 2 (whose title is exactly "Render structural-split recommendations in `triage_reason` + `emit_triage_summary`"). Leaving `triage_reason` alone here is what makes this step behavior-preserving and keeps every existing `triage_reason` test green unmodified.

- **Keep `STRUCTURAL_SOURCES` independent, not a subset/difference of any sibling set.** `APPLY_ELIGIBLE_SOURCES` and `STRUCTURAL_SOURCES` are disjoint concepts that evolve separately; declaring one in terms of the other couples them and hides the real invariant. A dedicated disjointness test (below) makes "a finding is never both apply-eligible and structural" a checkable property that survives step 2 widening the set.

- **No package re-export.** Import `is_structural`/`STRUCTURAL_SOURCES` in tests via `from plan_tool.review import ...`. Do not add them to `plan_tool/__init__.py` — matches the `is_apply_eligible` convention.

### Foundational logic and other call sites

- **The single shared rule:** "is this finding a split-worthy structural diagnostic." This step makes `is_structural` its sole home, before any consumer exists.
- **Producer is not a classifier (leave it).** `plan_tool/granularity.py` emits the source (`parse_mixed_step_findings` and the deterministic split detectors, all using `GRANULARITY_SPLIT_SOURCE`), surfaced into the convergence/triage path via detail's MIXED-STEP purity check (`plan_tool/detail.py`). That is finding *production*, not classification — it stays where it is and is **not** in this step's set of files.
- **Generic structural-diagnostic text stays separate.** `triage_reason`'s `if not is_apply_eligible(rec):` arm (covering `file-check`, `path-style`, `granularity-merge`, `files-coherence`, etc.) is a *broader* notion — "not prose-fixable," not "split-worthy." Do not fold those sources into `STRUCTURAL_SOURCES`; `is_structural` is strictly the split-bridge set. In particular `granularity-merge` is **not** structural-split — it is recommend-only and stays in the generic arm.

## Tests

All in `tests/test_review.py`, class `TestApplyTriage` (alongside `test_is_apply_eligible_by_source`, `test_triage_reason_for_structural_diagnostic`). Use the class's existing `_rec_src(rec_id=, source=, severity=)` helper.

- `test_is_structural_by_source` — `is_structural` is `True` for `source="granularity-split"`, `False` for every member of `APPLY_ELIGIBLE_SOURCES` and for the generic diagnostics (`file-check`, `path-style`, `granularity-merge`, `files-coherence`, `plan-completeness`, `heuristic`).
- `test_structural_sources_value_matches_granularity_constant` — `STRUCTURAL_SOURCES` contains `granularity.GRANULARITY_SPLIT_SOURCE` (import the constant *in the test* — the test layer may depend on `granularity`; `review.py` may not). Guards the deliberately-duplicated literal against a future rename of the granularity source.
- `test_structural_sources_disjoint_from_apply_eligible` — `STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()`. Guards the independence invariant when step 2 widens the set.
- `test_triage_reason_for_granularity_split_unchanged_this_step` — characterization: at this step a `granularity-split` rec's `triage_reason` is still the generic `"structural diagnostic — not auto-fixable"` text (it has **not** yet been routed through `is_structural`). Pins that step 1 changes no output; step 2 flips this.

### Test-creation order (refactor step)

This is a **refactor** step — behavior-preserving (a new, unused predicate). The behavior baseline is unchanged, so:

1. **`test_triage_reason_for_granularity_split_unchanged_this_step`** — written and green **against HEAD** (the generic `not is_apply_eligible` arm). It pins that `granularity-split` still gets the generic text, documenting that this step adds no routing. Step 2 will replace this test with its split-specific assertion.

**Pass-unchanged-after gate:** after adding `STRUCTURAL_SOURCES`/`is_structural`, every pre-existing `triage_reason` test (`test_triage_reason_renders_levels`, `test_triage_reason_handles_missing_tags`, `test_triage_reason_distinguishes_info_exclusion`, `test_triage_reason_for_structural_diagnostic`) must stay green **unmodified** — `triage_reason` is not touched. The new predicate/invariant tests are the only added green-required cases.

## Acceptance criteria

- `from plan_tool.review import is_structural, STRUCTURAL_SOURCES` succeeds; `STRUCTURAL_SOURCES == frozenset({"granularity-split"})`.
- `is_structural(rec)` returns `True` for `rec.source == "granularity-split"`, `False` for every source in `APPLY_ELIGIBLE_SOURCES` and for `file-check`/`path-style`/`granularity-merge`.
- `STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()`, and `granularity.GRANULARITY_SPLIT_SOURCE in STRUCTURAL_SOURCES`.
- `triage_reason` is unmodified: a `granularity-split` rec still returns the generic `"structural diagnostic"` text this step (step 2 changes it); a `file-check` rec is likewise unchanged.
- `uv run pytest tests/test_review.py -q` passes; no pre-existing `triage_reason`/`is_apply_eligible` test was modified.
- `review.py` does **not** import from `plan_tool.granularity` (no import cycle introduced); `plan_tool/__init__.py` is unchanged (no re-export).

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `Recommendation`'s `source`/`severity` fields are the inputs `is_structural` reads; reference for the frozen-dataclass shape the predicate matches against.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — for the unit-test conventions (`TestApplyTriage` class, no markers needed — these are fast unit tests) the new cases follow.

## Deferred

- The split-specific `triage_reason` message for `granularity-split` + the `structural-split` source and its `emit_triage_summary` rendering — step 2 (`feature`). This step adds the predicate only; it routes nothing and changes no output.
- Adding `structural-split` to `STRUCTURAL_SOURCES` — step 2 extends the frozenset.
- Any consumer of `is_structural` (the `BLOCKED-STRUCTURAL` verdict, the `escalate_to_split` bridge gate) — steps 3, 4, 7, 8.
