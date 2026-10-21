# Step 2 — Centralize roadmap text reads without changing their exception meanings

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Centralize the existing roadmap text-read pattern in `plan_tool/roadmap.py` and route the local revision prompt read in `plan_tool/roadmap_revision_run.py` through the same bounded seam. Preserve each caller’s current exception family, message, cause chain, and caller-visible timing; this step only removes duplicated read-and-wrap control flow. Update focused tests in `tests/test_roadmap.py` and `tests/test_roadmap_revision_run.py` to pin the preserved contracts. On green, later terminal-disposition work has one reader boundary to extend without first rediscovering route-specific read behavior.

## Table of Contents

- [Summary](#summary) — Gives the reviewer the change and its completion result.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Explains why the duplicated read paths need one seam.
- [Input](#input) — Names the existing exception contracts this refactor preserves.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the bounded code and test footprint.
- [Implementation](#implementation) — Defines the shared reader and preserved route behavior.
- [Tests](#tests) — Names the focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the existing contract and tracking records.
- [Applicable guardrails](#applicable-guardrails) — Applies the plan fence to this refactor.
- [Deferred](#deferred) — Separates later failure normalization and terminal handling.

## Why

`plan_tool/roadmap.py:_render_stage_prompt`, `plan_tool/roadmap.py:_render_stage_feedback_prompt`, and `plan_tool/roadmap.py:_load_stage_artifact` each implement the same UTF-8 read failure shape while choosing different meaningful exception outcomes. `plan_tool/roadmap_revision_run.py:render_local_revision_prompt` has a related raw-read route whose caller currently owns its failure outcome. Keep those choices intact while creating one narrow reader seam, so later work can normalize the named template routes without changing behavior accidentally during a broad copy-and-edit sweep.

## Input

- **Step 1 terminal matrix:** Treat step 1’s `ROADMAP_FORMAT.md` terminal-disposition section as the source for the existing distinction between input-shaped failures and environmental failures. This step preserves that distinction; it does not apply the later common terminal behavior.

- **Primary reader contracts:** Preserve the exception behavior at `plan_tool/roadmap.py:_render_stage_prompt`, `plan_tool/roadmap.py:_render_stage_feedback_prompt`, and `plan_tool/roadmap.py:_load_stage_artifact`, including their route-specific messages and exception chaining.

- **Local revision contract:** Preserve `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` handling of read or decode failures from `render_local_revision_prompt` as a failed result before any backend call.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Add the bounded roadmap text-reader seam and replace the duplicate read-and-wrap blocks in `_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_load_stage_artifact`.
  - `plan_tool/roadmap_revision_run.py` — Use the shared reader from `render_local_revision_prompt` without changing the local runner’s existing failure result.
  - `tests/test_roadmap.py` — Extend renderer and artifact-read tests to prove the shared seam preserves each primary-route exception contract.
  - `tests/test_roadmap_revision_run.py` — Prove the local revision renderer retains its pre-invocation failure result when its template cannot be read or decoded.

## Implementation

- **Centralize only the foundational logic:** Create one narrowly scoped helper in `plan_tool/roadmap.py` for reading UTF-8 text and translating only expected filesystem or decode failures according to caller-provided error behavior. The helper must not become a general application exception framework.

- **Keep exception selection with the route.** The helper must let each caller retain its current exception family and route-specific message:
  - `_render_stage_prompt` and `_render_stage_feedback_prompt` retain `RoadmapEnvironmentalError` for a file that passed their presence checks but cannot be read or decoded.
  - `_load_stage_artifact` retains `RoadmapError`, including its path, stage identity, and `--from-stage` recovery guidance.
  - `render_local_revision_prompt` retains the current local-runner behavior: expected prompt read or decode failure reaches `run_local_feedback_revision` as the existing pre-invocation `invoke-failed` result, with no backend call.

- **Preserve missing-file meaning.** Do not fold each renderer’s `Path.is_file()` validation into a broad catch that changes a missing template from its current base `RoadmapError` path into an environmental error. The helper handles read and decode failures after the route has established the file’s expected presence.

- **Preserve unexpected defects.** Catch only the current expected read and UTF-8 decode failures. `KeyboardInterrupt`, `SystemExit`, `BaseException`, and programming errors such as `AttributeError` must continue to escape their existing boundaries.

- **Preserve messages and causes.** Keep the caller-owned message content rather than replacing it with generic helper text. Wrap expected failures with `raise ... from exc` wherever the current route does so; do not erase the underlying filesystem or decode cause.

- **Keep the helper’s reach bounded.** Do not sweep unrelated `Path.read_text()` uses in `plan_tool/roadmap.py`, including seed acceptance, seed refresh, baseline enrollment, or reviewer-feedback rechecks. Their lifecycle and exception meanings differ from the prompt and stage-artifact reader family.

- **Use the existing dependency direction.** `plan_tool/roadmap_revision_run.py` already imports roadmap types and functions, so it can reuse the roadmap-owned helper without creating an import cycle. Do not move the helper to `plan_tool/roadmap_source.py`; `read_brief_text` owns the recorded-brief contract, not prompt or artifact exception classification.

- **Leave terminal behavior for later steps.** Do not edit CLI handlers, run-log calls, status emission, retry flow, publication recovery, or result outcome definitions. Step 4 changes the named template failure classification and step 5 applies the shared terminal disposition after this refactor is independently green.

## Tests

- `test_render_stage_prompt_wraps_an_unreadable_template` — Assert `_render_stage_prompt` still raises `RoadmapEnvironmentalError` with readable route context when its template read raises `OSError`.

- `test_render_stage_feedback_prompt_wraps_an_unreadable_template` — Assert `_render_stage_feedback_prompt` still raises `RoadmapEnvironmentalError` for an expected template read failure.

- `test_render_stage_prompt_missing_template_stays_base_roadmap_error` — Assert the presence-check route remains distinct from an unreadable-file route.

- `test_load_stage_artifact_preserves_preflight_roadmap_error` — Assert `_load_stage_artifact` still raises `RoadmapError`, retaining its path and recovery guidance, when an artifact read or decode fails.

- `test_local_revision_prompt_read_failure_returns_invoke_failed_without_backend_call` — Assert an `OSError` or Unicode decode failure from `render_local_revision_prompt` produces the current `invoke-failed` result, leaves `context_digest` unset, and never invokes the backend.

- `test_unexpected_accepted_revision_boundary_error_propagates` — Retain the existing proof that an unexpected prompt-rendering defect is not converted into an expected read failure.

### Tests for this step

Every listed test must be green before this refactor is complete. Run the focused roadmap suites first, then the plan’s configured full suite: `uv run pytest tests/ -q -n auto`.

## Acceptance criteria

- `plan_tool/roadmap.py` has one shared UTF-8 text-read seam used by `_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_load_stage_artifact`.

- Each migrated primary caller preserves its current exception class, route-specific message, and chained expected read or decode cause.

- A missing prompt template remains a base `RoadmapError`; an existing-but-unreadable prompt input remains a `RoadmapEnvironmentalError`.

- A stage artifact read or decode failure remains a `RoadmapError` with the current stage, path, and recovery context.

- `plan_tool/roadmap_revision_run.py:render_local_revision_prompt` uses the shared seam while `run_local_feedback_revision` still returns `invoke-failed` before any backend call for expected prompt read or decode failures.

- Unexpected rendering defects still propagate rather than becoming clean roadmap read failures.

- The named tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [ROADMAP_FORMAT.md terminal-disposition section — Read the step 1 matrix for the exception meanings this refactor must preserve.](/ROADMAP_FORMAT.md)

- [BACKLOG.md #347 — Read the existing read-or-raise duplication analysis and its exception-family constraint.](/BACKLOG.md)

- [BUG_BACKLOG.md, “Two prompt-template renderers have no read-failure handling in their caller chain” — Read the remaining named renderer routes that step 4 will normalize.](/BUG_BACKLOG.md)

- [plan_tool/roadmap.py — Read `_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_load_stage_artifact` as the primary reader consumers.](/plan_tool/roadmap.py)

- [plan_tool/roadmap_revision_run.py — Read `render_local_revision_prompt` and `run_local_feedback_revision` for the local pre-invocation boundary.](/plan_tool/roadmap_revision_run.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, model-reply evidence boundary:** Do not add response capture or persistence while moving read logic.

- **The plan’s “## Scope guardrails”, interrupt boundary:** Do not catch or translate interrupt-related exception classes in the shared reader.

- **The plan’s “## Scope guardrails”, result and lifecycle boundary:** Do not change roadmap outcomes, retry loops, publication recovery, checkpoints, or writer locking.

- **The plan’s “## Scope guardrails”, unexpected-defect boundary:** Do not turn arbitrary rendering or programming defects into roadmap domain errors.

- **The plan’s “## Scope guardrails”, framework boundary:** Keep the helper roadmap-local and limited to the named read family.

- **The plan’s “## Out of scope”, success and retry boundary:** Do not change successful output or add retry behavior.

## Deferred

- **Named prompt-template failure normalization** — Step 4 chooses and applies the common roadmap-domain treatment for the four named rendering routes after this helper is in place.

- **CLI status, run-log, exit-code, and crash-report disposition** — Step 5 applies the step 1 matrix at the primary, materialization, and local-revision boundaries.

- **Writer-guard origin distinction** — Step 3 owns the before-versus-after-start behavior without widening this read refactor.
