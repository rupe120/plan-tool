# Step 5 — Add a `structural_stop` reason to `should_continue` for a caller-supplied recurring seam

## Summary

Give `plan_tool/convergence.py` a way to stop an iterate loop when the caller has already decided that the same high-impact region keeps recurring. `ConvergenceState` gains one defaulted boolean field the caller sets, and `should_continue` gains a matching `"structural_stop"` reason returned only where it would otherwise have returned `(True, "continue")`. The key decision: the recurrence fact is **supplied by the caller**, never derived inside this module — `convergence.py` keeps its no-first-party-imports rule and never learns about report history. On green, a state carrying the new flag stops with `(False, "structural_stop")` while every existing stop reason keeps winning exactly as it does today.

## Table of Contents

- [Summary](#summary) — what changes and the observable result.
- [Why](#why) — why the fact is caller-supplied instead of computed here.
- [Input](#input) — the recurrence fact step 3 produces and this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched.
- [Implementation](#implementation) — the new field, the new reason, and the required check order.
- [Tests](#tests) — unit cases to add in `tests/test_convergence.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes.
- [References](#references) — the two docs worth opening for this step.
- [Deferred](#deferred) — what this step deliberately leaves to steps 6 and 7.

## Why

`should_continue` today has no way to express "stop — the same high-impact seam keeps coming back". A loop hitting that case burns to `max_iterations` and reports a limit stop, which reads to an operator like an ordinary budget exhaustion rather than a structural problem. Steps 6 and 7 wire the completeness and reconcile loops to a recurrence classifier, and both need one shared stop token so the two call sites cannot drift into separate ad-hoc exits. `convergence.py` is the right home for the token and the ordering rule, but it must stay a dependency-light leaf: its module docstring pins "no first-party `plan_tool.*` imports", and `plan_tool/review.py` already imports it, so a reverse import would be a cycle. The fact therefore travels **in**, as data.

## Input

- **The recurrence fact comes from step 3's classifier** (`plan_tool/impact_recurrence.py`, created by step 3). This step reads only its boolean answer — "is there a still-open high-impact region recurring across three passes?" — not its record shape, module, or matching rules.
- **This step imports nothing from step 3.** The caller (steps 6 and 7) runs the classifier, turns its result into a bool, and assigns it onto `ConvergenceState` before each `should_continue` call — the same pattern `has_blocking_findings` already uses.
- **Limit on verification here:** with `plan_tool/impact_recurrence.py` not yet on disk, nothing in this step can be tested against a real classifier result. Tests set the field directly, which is the whole point of the seam.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence.py` — add one defaulted bool field to `ConvergenceState`; add the matching check and reason to `should_continue`, plus its docstring bullet.
  - `tests/test_convergence.py` — add the new-reason cases and the ordering regression cases described below.

## Implementation

**What must be true when the step is done**

- `ConvergenceState` carries a caller-set boolean naming the recurring high-impact seam. Suggested name: `has_recurring_structural_seam`, mirroring the existing `has_blocking_findings` field's shape and comment style. It **must default to `False`**, so every current caller (`plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/cli/reconcile.py`, `plan_tool/cli/completeness_cmd.py`) keeps today's behavior with no edit.
- `should_continue` returns `(False, "structural_stop")` when that field is `True` **and no earlier check fired**. The reason string is `"structural_stop"` — the token the plan's acceptance criteria name and the one steps 6 and 7 will print.
- The `should_continue` docstring gains a bullet for the new reason in the same list style as `"no_progress"` and `"time_budget_exceeded"`, stating plainly that the caller owns the fact.

**Required check order**

- Put the new check **after every existing stop check**, including the `budget.hard_budget_seconds` branch, immediately before the final `return True, "continue"`. This is the one part that is not free to vary: it makes `structural_stop` an *otherwise-continuing* stop, so `disabled`, `converged`, `max_iterations`, `deadline_exceeded`, `no_blocking_findings`, `marginal`, `no_progress`, and `time_budget_exceeded` all keep winning when they apply.
- The hard-cap block's comment says it is "checked LAST"; update that wording so the next reader isn't misled about the tail order.
- Rejected alternative: placing `structural_stop` ahead of the hard wall-clock cap, on the argument that a structural verdict is more actionable than "out of time". It reorders an existing terminal reason, which the plan's risk section calls out as the regression to avoid, and it buys nothing — both cases end the loop.

**Constraints and gotchas**

- **No new imports.** No `plan_tool.impact_recurrence`, no `plan_tool.convergence_diagnosis`, no `plan_tool.review` at runtime. The only existing runtime `Recommendation` reference is the `TYPE_CHECKING`-guarded annotation used by `is_blocking_impact`; keep that shape.
- **No iteration guard.** Unlike `no_blocking_findings` and `marginal`, do not gate the new check on `state.iteration > 0`. The caller only sets the flag once a three-pass streak exists, so a round-0 guard here would be dead code that hides a legitimate stop. Say so in the docstring bullet.
- **Don't touch `record_iteration` or `touch`.** They own the finding-set roll and the debounce timer; the new field is not derived from either and must not be reset by them. A caller that wants the flag cleared assigns `False`.
- **Leave `is_blocking` / `is_blocking_impact` alone.** The plan's "Out of scope" bars widening the calibrated impact policy, and this step needs no impact predicate at all — it consumes a bool.

## Tests

All cases go in `tests/test_convergence.py`, in a new `# ---------- structural_stop ----------` section following the existing `no_progress` section. The `_state(...)` helper does not know the new field — either add a keyword to it or set the attribute on the returned state; either is fine, pick one and use it consistently.

- `test_structural_stop_fires_when_caller_sets_the_flag` — a state that would otherwise return `(True, "continue")` returns `(False, "structural_stop")`.
- `test_structural_stop_defaults_off` — a freshly built `ConvergenceState` has the field `False` and still returns `(True, "continue")`.
- `test_structural_stop_fires_at_iteration_zero` — the flag stops the loop even on round 0, pinning the no-iteration-guard decision.
- `test_disabled_outranks_structural_stop` — `budget.enabled=False` still reports `"disabled"`.
- `test_converged_outranks_structural_stop` — empty `current_finding_ids` after iteration 1 still reports `"converged"`.
- `test_max_iterations_outranks_structural_stop` — still reports `"max_iterations"`.
- `test_deadline_outranks_structural_stop` — still reports `"deadline_exceeded"`.
- `test_no_blocking_findings_outranks_structural_stop` — still reports `"no_blocking_findings"`.
- `test_marginal_outranks_structural_stop` — still reports `"marginal"`.
- `test_no_progress_outranks_structural_stop` — still reports `"no_progress"`.
- `test_time_budget_outranks_structural_stop` — with `hard_budget_seconds` exceeded, still reports `"time_budget_exceeded"`, pinning the tail order.

### Test-creation order (feature step)

This is a feature step: write the tests above alongside the implementation, not before it. Green-before-done gate — every new test, plus the whole existing `tests/test_convergence.py` file, must pass (`uv run pytest tests/test_convergence.py -q`) before the step is finished. The 10 ordering/default cases are the regression surface that proves no existing reason moved.

## Acceptance criteria

- `ConvergenceState` has a bool field for the recurring seam whose default is `False`.
- `should_continue(state)` returns `(False, "structural_stop")` when the field is `True` and no earlier check fires.
- `should_continue` returns each of `"disabled"`, `"converged"`, `"max_iterations"`, `"deadline_exceeded"`, `"no_blocking_findings"`, `"marginal"`, `"no_progress"`, and `"time_budget_exceeded"` unchanged when that condition holds *and* the new flag is also `True`.
- `plan_tool/convergence.py` still has zero runtime `plan_tool.*` imports (`grep -n "^from plan_tool\|^import plan_tool" plan_tool/convergence.py` returns nothing outside the `TYPE_CHECKING` block).
- `should_continue`'s docstring lists `"structural_stop"` among its reason codes.
- `uv run pytest tests/test_convergence.py -q` is green, and the full suite (`uv run pytest tests/ -q`) shows no new failures.

## References

- [Python `dataclasses` — Data Classes](https://docs.python.org/3/library/dataclasses.html) — field defaults on a mutable dataclass, which is how the new `ConvergenceState` field stays backward compatible with every current caller.
- [pytest — How to parametrize fixtures and test functions](https://docs.pytest.org/en/stable/how-to/parametrize.html) — a table over the eight existing stop reasons is the compact way to write the ordering regression cases.

## Deferred

- **Running the recurrence classifier** — `plan_tool/impact_recurrence.py` is step 3's and step 4's work; this step only accepts its answer as a bool.
- **Setting the flag from real history in the completeness loop** — step 6 owns that wiring in `plan_tool/cli/completeness_cmd.py`.
- **Setting the flag from real history in the reconcile loop** — step 7 owns that wiring in `plan_tool/cli/reconcile.py`.
- **Printing the follow-up command on a structural stop** — the recommendation text comes from step 4 and is rendered by the loop call sites, not by `should_continue`.
- **Threading the flag into the `create` and `detail` loops** — the plan defers both; those loops keep the default `False` and behave as they do today.
- **Any change to `is_blocking` / `is_blocking_impact`** — the calibrated impact policy boundary is out of scope for this plan.
