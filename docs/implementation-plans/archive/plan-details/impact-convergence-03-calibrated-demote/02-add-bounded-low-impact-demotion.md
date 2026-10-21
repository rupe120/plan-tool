> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add the bounded low-impact demotion extension

## Summary

Add an optional demotion callback to `plan_tool/convergence.py:is_blocking_impact` after the baseline decision has been isolated. The helper itself must invoke that callback only for an explicit `impact="low"`, `severity="medium"` baseline block; high impact, `high`/`critical`, and advisory findings never reach it. This is a feature step, not a behavior-preserving refactor.

## Implementation

- Add a keyword-only optional callback, defaulting to no demotion. Existing callers and `is_blocking_impact(rec)` retain step 1 behavior.
- Evaluate high impact first, then preserve `high` and `critical` severity blocks. Invoke the callback only after confirming the recommendation is exactly low impact and medium severity; a truthy callback cannot override any other shape.
- Keep this module dependency-light: the callback receives the live recommendation, while the later telemetry step owns evidence and class matching.

## Tests

- A supplied callback demotes an otherwise blocking low-impact medium recommendation.
- A truthy callback cannot demote missing/non-low impact, high impact, high, critical, `nit`, or `info` recommendations; it is not invoked for fixed outcomes.
- Omitting the callback preserves the characterization test from step 1 unchanged.

## Acceptance criteria

- `is_blocking_impact` has an opt-in demotion seam with no default behavior change.
- The shared helper enforces the explicit low-impact/medium-severity boundary before consulting the callback.
- High-impact, high, and critical recommendations always block; advisory results stay advisory.

## Deferred

- Step 3 supplies only evidence-backed callback results. Steps 4 and 5 wire one such callback into reconcile and audit materiality.
