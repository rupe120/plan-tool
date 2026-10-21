> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Render structural-split recommendations in `triage_reason` + `emit_triage_summary`

## Summary

- Add `"structural-split"` to the `STRUCTURAL_SOURCES` frozenset (created by step 1, currently `{"granularity-split"}`) so it holds both the live advisor source and the bridge's recommend-only source.
- **Add** the `if is_structural(rec):` branch to `triage_reason` (step 1 left `triage_reason` untouched), ordered **before** the generic `if not is_apply_eligible(rec):` fallback, dispatching per source: both `granularity-split` and `structural-split` point the operator at **`plan-tool split`** (not `plan-tool detail`). Routing `granularity-split` here is the **behavior change** this step owns — at HEAD it falls through to the generic "structural diagnostic — not auto-fixable" text.
- Teach `emit_triage_summary` to print each structural finding's `rec.body` and `rec.suggested_action` as extra indented sub-lines, gated on `is_structural(rec)` so every non-structural rec keeps its current single-line form.
- Both edits land in `plan_tool/review.py`; tests in `tests/test_review.py`.
- This is **new output behavior** (a `feature`). It is **not** inert: `is_structural(rec)` is `True` for the live `granularity-split` source, so it immediately changes that source's `triage_reason` text and adds `body`/`suggested_action` sub-lines on the real `detail --iterate` path (convergence loop → `partition_findings_for_triage` → `emit_triage_summary`). The `structural-split` branch is forward-wiring until step 4's bridge produces that source, exercised by a synthetic rec in tests.
- On green: a `granularity-split` or `structural-split` rec renders with a split-specific reason plus its body/action, a non-structural rec is unchanged, and `is_structural("structural-split")` is `True` while `is_apply_eligible` stays `False`.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the dead-ended structural recommendation this surfaces
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the `triage_reason` branch + `emit_triage_summary` sub-line rendering
- [Tests](#tests) — feature tests added with the code
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — the producer and downstream wiring left to later steps

## Why

- Step 1 single-sourced the structural predicate behind `review.is_structural(rec)` but kept it output-silent — `STRUCTURAL_SOURCES` holds only `granularity-split`, nothing routes through the predicate, and a `granularity-split` finding still gets the generic "structural diagnostic — not auto-fixable" line that points at `plan-tool detail`, the wrong remedy for a step that must be **split**. Separately, the bridge in step 4 (`escalate_to_split`) emits a recommendation under a new `structural-split` source whenever it declines to mutate structure (unattended / unsafe / non-TTY), and nothing renders that either. This step adds the operator-facing output — a split-specific reason and the recommendation's own body/action — so both the live advisor signal and the bridge's "always validate the more-correct plan" recommendation are visible and actionable. The predecessor plan illegally bundled this output change into the refactor step and was BLOCKED for refactor+feature impurity; this step is that output, kept separate.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review.py` — add `"structural-split"` to `STRUCTURAL_SOURCES`; add `triage_reason`'s `is_structural` branch (per-source message pointing at `plan-tool split`); extend `emit_triage_summary` to print `rec.body`/`rec.suggested_action` sub-lines for structural recs.
  - `tests/test_review.py` — add the new `triage_reason` and `emit_triage_summary` sub-line tests in the existing `TestApplyTriage` class (which holds `test_triage_reason_for_structural_diagnostic`), plus the structural-predicate tests beside step 1's. The key `test_triage_summary_plain_byte_identical` lives in `TestReviewStyleOutput` (tests/test_review.py:6772), not `TestApplyTriage`; leave that guard in `TestReviewStyleOutput` unmodified.

## Implementation

### `plan_tool/review.py`

- **Extend `STRUCTURAL_SOURCES`** to two members:
  - `STRUCTURAL_SOURCES: frozenset[str] = frozenset({"granularity-split", "structural-split"})`.
  - Keep it independent of `APPLY_ELIGIBLE_SOURCES` — `structural-split` is **not** added to that set, so `is_apply_eligible` stays `False` and the disjointness invariant step 1 pinned still holds.
  - Update the constant's comment to name `structural-split` as the bridge-emitted producer (alongside `granularity-split`, emitted by `granularity.py` and surfaced through detail).

- **Add `triage_reason`'s structural arm.** Insert an `if is_structural(rec):` check ordered **before** the `if not is_apply_eligible(rec):` generic fallback (a `granularity-split`/`structural-split` rec is also non-apply-eligible, so without this ordering it would fall through to the generic text and lose the split message). Inside it, dispatch on `rec.source`:
  - `structural-split` → a message pointing the operator at `plan-tool split`: the only correct fix is to split this step into two type-pure steps, so run `plan-tool split`, not an apply edit.
  - else (`granularity-split`) → a split-specific message that names the mixed/over-packed step and likewise points at `plan-tool split` (replacing the generic text it gets at HEAD).

  ```python
  if is_structural(rec):
      if rec.source == "structural-split":
          return (
              "structural-split: the only correct fix is to split this step "
              "into two type-pure steps; run `plan-tool split`, not an apply edit"
          )
      return (
          "granularity-split: structural — step is over-packed / mixes "
          "concerns; the fix is to split it into type-pure steps via "
          "`plan-tool split`, not an apply edit"
      )
  ```

- **Render structural recs richer in `emit_triage_summary`.** After the existing per-rec bullet (`  - {rec.id}: {rec.title} [{triage_reason(rec)}]`), when `is_structural(rec)` is `True`, print extra indented sub-lines:
  - `rec.body` on its own indented line (the recommendation's human-readable detail / rationale).
  - `rec.suggested_action` on a following indented line **only when it is not `None`** (the bridge sets this to the concrete `plan-tool split …` invocation; the live `granularity-split` producer in `granularity.py` also sets a non-`None` action, so both live sources print this line — the `None` branch is the defensive path for a hypothetical action-less structural rec, never reached by today's producers).
  - Gate the entire sub-line block on `is_structural(rec)` so non-structural recs (`reconcile`, `body-completeness`, …) emit exactly the single bullet line they do today. This is what keeps `test_triage_summary_plain_byte_identical` and `test_emit_triage_summary_lists_each_deferred_rec` unchanged.
  - Use a deeper indent than the bullet (e.g. six spaces vs the bullet's two-space `  - `) so the body/action read as children of the bullet.

- **No new struct field, no new function.** `Recommendation` already carries `source`, `body`, and `suggested_action` — this step only reads them. `partition_findings_for_triage` is unchanged: a `structural-split` rec lands in `open_deferred` automatically because it is not apply-eligible (the first gate), exactly as `granularity-split` and the other structural diagnostics do.

## Tests

All in `tests/test_review.py`, added alongside the implementation. Reuse the existing `TestApplyTriage._rec_src` / `_rec` helpers (extend `_rec_src` only if a `body`/`suggested_action` argument is needed; otherwise build the `Recommendation` inline like the byte-identical tests do).

- `test_structural_split_is_structural` — `is_structural(rec)` is `True` for a rec with `source="structural-split"`.
- `test_structural_split_not_apply_eligible` — `is_apply_eligible(rec)` is `False` for `source="structural-split"` (stays out of `APPLY_ELIGIBLE_SOURCES`).
- `test_structural_sources_disjoint_from_apply_eligible` — re-confirm (or extend step 1's test) that `STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()` now that the set has two members.
- `test_triage_reason_for_structural_split_points_at_split` — `triage_reason` for a `structural-split` rec contains `plan-tool split` and does **not** contain `plan-tool detail`.
- `test_triage_reason_for_granularity_split_now_points_at_split` — `triage_reason` for a `granularity-split` rec now contains `plan-tool split` and is ordered ahead of the generic `not is_apply_eligible` fallback (it no longer returns the generic "structural diagnostic" text). **This replaces step 1's `test_triage_reason_for_granularity_split_unchanged_this_step` characterization test** — update that test here to assert the new routed message, documenting the behavior flip this step owns.
- `test_emit_triage_summary_renders_body_and_action_for_structural_split` — a deferred `structural-split` rec (body set, `suggested_action="plan-tool split …"`) prints its body text and the suggested-action text on indented sub-lines under the bullet.
- `test_emit_triage_summary_renders_body_for_granularity_split` — a live-shape `granularity-split` deferred rec (body set, non-`None` `suggested_action` matching the `granularity.py` producer) prints both its body sub-line and its action sub-line, pinning that this rendering change reaches the real `detail --iterate` path (not just the forward-inert `structural-split` source).
- `test_emit_triage_summary_omits_action_line_when_none` — a structural rec with `suggested_action=None` prints the body sub-line but no action sub-line.
- `test_emit_triage_summary_non_structural_unchanged` — a `reconcile` rec still emits exactly the single bullet line (no body/action sub-lines), guarding the gate. (The existing `test_triage_summary_plain_byte_identical` and `test_emit_triage_summary_lists_each_deferred_rec` must also stay green unmodified.)

### Test-creation order (feature step)

- This is a **feature** step — new output (including the `granularity-split` `triage_reason` behavior flip). Write each test above with the implementation; the one exception is the *update* of step 1's `granularity-split` characterization test, which flips from "generic text" to "split message" precisely because this step adds the routing.
- Green-before-done gate: every new test, plus the unchanged existing `triage_reason`/`emit_triage_summary` tests (`test_triage_reason_for_structural_diagnostic`, `test_triage_summary_plain_byte_identical`, `test_emit_triage_summary_lists_each_deferred_rec`), must be green before this step is considered finished.
- Run `uv run pytest tests/test_review.py -q` (unit tier; no invoker seam is exercised here, so no `claude` shell-out).

## Acceptance criteria

- `is_structural(rec)` returns `True` for `rec.source == "structural-split"` and `is_apply_eligible(rec)` returns `False` for it.
- `STRUCTURAL_SOURCES == frozenset({"granularity-split", "structural-split"})` and `STRUCTURAL_SOURCES & APPLY_ELIGIBLE_SOURCES == frozenset()`.
- `triage_reason` for a `structural-split` rec **and** for a `granularity-split` rec both contain `plan-tool split` and not `plan-tool detail`; both are ordered ahead of the generic `not is_apply_eligible` fallback.
- `emit_triage_summary` prints `rec.body` and (when present) `rec.suggested_action` on indented sub-lines for a structural rec, and prints exactly the single bullet line for a non-structural rec.
- All existing `triage_reason`/`emit_triage_summary` tests pass unmodified (only step 1's `granularity-split` characterization test is intentionally updated here).

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `Recommendation` is a `@dataclass`; confirms the `source`/`body`/`suggested_action` fields this step reads and `suggested_action`'s `Optional[str] = None` default that gates the action sub-line.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Not needed for these pure-function tests, but the reference for the invoker seams the rest of the plan's steps neutralize.

## Deferred

- **The `structural-split` producer.** No code emits a `structural-split` recommendation yet; step 4's `escalate_to_split` bridge sets `source="structural-split"`, `body=<split rationale>`, and `suggested_action=<plan-tool split invocation>` on its recommend-only outcomes. Until then that branch is forward-wiring, exercised only by synthetic recs in tests.
- **Wiring the bridge into the create/detail/review loops** that call `emit_triage_summary` — steps 4–8.
- **Persisting the `structural-split` recommendation** as a saved finding — out of scope (plan Deferred).
- **Pairing more deeply with the granularity advisor** (e.g. an actuating bridge from a `granularity-split` finding to a split command) — out of scope; this step only renders the advisor's existing finding with a split-pointing reason. `granularity-merge` is deliberately **not** structural and stays in the generic triage arm.
