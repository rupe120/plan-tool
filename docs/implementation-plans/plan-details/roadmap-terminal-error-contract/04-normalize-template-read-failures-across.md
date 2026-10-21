# Step 4 — Normalize template read failures across roadmap rendering routes

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Make template read and decode failures follow the terminal-disposition contract across stage authoring, stage feedback, local feedback revision, and draft-seed materialization. Update `plan_tool/roadmap.py` and `plan_tool/roadmap_revision_run.py` to preserve the shared reader seam from step 2 while giving each named route the matrix-selected roadmap-domain outcome. Extend `tests/test_roadmap.py` and `tests/test_roadmap_revision_run.py` with focused failure-path coverage. On green, these expected template failures never escape as unexpected crashes or invoke a backend after prompt construction has failed.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the route-normalization change.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains the inconsistent template-read treatment.
- [Input](#input) — Names the upstream error and terminal contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the bounded code and test footprint.
- [Implementation](#implementation) — Defines the shared failure behavior and route boundaries.
- [Tests](#tests) — Lists focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the governing roadmap contracts and tracked gaps.
- [Applicable guardrails](#applicable-guardrails) — Keeps terminal normalization inside the plan fence.
- [Deferred](#deferred) — Separates adjacent renderer and lifecycle work.

## Why

The stage authoring and bounded stage-feedback renderers already translate unreadable template inputs into a roadmap-domain error, while `render_local_revision_prompt` and `_render_seed_materialize_prompt` leave equivalent failures to their callers or the generic crash boundary. That makes the operator-visible error, result category, and crash-report behavior depend on which named roadmap route happened to read the template. This step applies the terminal contract established by steps 1 and 2 without changing model retries, publication behavior, or the broader CLI error framework.

## Input

- **Step 1 terminal-disposition matrix:** Use the landed terminal-disposition section in `ROADMAP_FORMAT.md` as the authority for the selected human error, roadmap-domain classification, run-log ending, exit code, and crash-report behavior. The matrix wins over older route-specific tests or comments.

- **Step 2 text-reader seam:** Build on the shared UTF-8 reader in `plan_tool/roadmap.py` and retain its distinction between a missing template and a template that cannot be read or decoded. Do not recreate route-local raw `Path.read_text()` wrapping.

- **Local revision result contract:** Preserve `plan_tool/roadmap_revision_run.py:LocalRevisionResult` and `run_local_feedback_revision` as the local revision terminal-fact boundary. A prompt-build failure remains pre-invocation and must retain an empty prompt context digest.

- **Seed materialization lifecycle:** Preserve `plan_tool/roadmap.py:_materialize_plan_seed` and `_materialize_seed_rows` ownership of row-level phases, partial-batch reporting, and terminal lifecycle completion.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Route `_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_render_seed_materialize_prompt` through the step-2 reader contract; ensure their caller-visible failures use the matrix-selected roadmap error family.
  - `plan_tool/roadmap_revision_run.py` — Normalize the local revision's update-guidance read at its caller boundary and handle the resulting prompt-build failure at `_run_accepted_revision` before any backend call.
  - `tests/test_roadmap.py` — Cover normalized template failures for stage authoring, stage feedback, and seed materialization.
  - `tests/test_roadmap_revision_run.py` — Cover the local revision result, run-log facts, and invoker non-reachability for normalized prompt-build failures.

## Implementation

- **Use one template-read rule.** The foundational logic is translating an expected UTF-8 template read or decode failure into the terminal matrix’s roadmap-domain error. Route the named renderers through the reader seam step 2 establishes so equivalent failures do not depend on which prompt builder encountered them.

- **Keep missing and unreadable inputs distinct where the matrix requires it.** Use the existing `RoadmapError` and `RoadmapEnvironmentalError` boundary rather than string matching at a caller. Preserve cause chaining so the operator-facing error retains useful filesystem or decode context without exposing an unexpected traceback.

- **Cover stage authoring and stage feedback together.** In `plan_tool/roadmap.py:_render_stage_prompt` and `_render_stage_feedback_prompt`, retain the current template-variable behavior and only normalize expected template input failures. Placeholder errors and programming defects must keep their existing behavior.

- **Normalize update guidance only at the named local route.** Keep `plan_tool/roadmap.py:render_update_judgment_section` unchanged because structural revision also consumes it. At `plan_tool/roadmap_revision_run.py:render_local_revision_prompt` or its local caller boundary, translate its expected read or decode failure into the matrix-selected roadmap-domain error; do not change the structural-rewrite consumer's exception family.

- **Treat local revision prompt construction as pre-invocation.** In `plan_tool/roadmap_revision_run.py:_run_accepted_revision`, recognize the normalized roadmap-domain template failure from `render_local_revision_prompt` alongside the existing prompt-build failure handling. Return the matrix-aligned failed result, record the existing terminal attempt facts, leave `context_digest` unset, and do not call the injected invoker.

- **Normalize seed materialization before its retry loop.** In `plan_tool/roadmap.py:_render_seed_materialize_prompt` and `_materialize_plan_seed`, convert expected template input failures before a seed attempt starts. Do not consume a model-attempt budget, write a draft seed, alter seed state, or change `_materialize_seed_rows` partial-batch and lifecycle ownership.

- **Do not widen the exception catch.** Catch only the named roadmap-domain errors needed to preserve the selected route contract. Do not catch arbitrary exceptions, `KeyboardInterrupt`, `SystemExit`, or `BaseException`; unexpected defects must still reach `plan_tool/cli/app.py`’s crash boundary.

## Tests

- `tests/test_roadmap.py::TestRenderStagePromptReadErrors` — Extend the existing renderer failure cases to prove the shared reader preserves the matrix-selected distinction for stage authoring and bounded stage feedback.

- `tests/test_roadmap.py::test_seed_materialize_prompt_wraps_an_unreadable_template` — Assert seed prompt construction classifies an expected template read failure without entering the model retry path.

- `tests/test_roadmap.py::test_seed_materialization_template_failure_writes_no_seed_or_state` — Assert a failed seed prompt build leaves the draft path and seed-state publication unchanged.

- `tests/test_roadmap_revision_run.py::test_local_revision_template_read_failure_returns_failed_before_invocation` — Assert normalized local prompt failure returns the established failed result, names the error, leaves `context_digest` unset, and never calls the invoker.

- `tests/test_roadmap_revision_run.py::test_local_revision_template_read_failure_records_one_terminal_attempt` — Assert the local revision run log records the existing pre-invocation failure outcome without claiming a backend call occurred.

### Tests for this step

Every listed test must be green before this step is complete. Keep the tests focused on expected template filesystem and decode failures; retain separate existing coverage for malformed template placeholders and unexpected exceptions.

## Acceptance criteria

- Every named template route classifies expected read and decode failures through the step-2 reader contract or its local caller boundary without changing the structural-rewrite consumer.

- A missing template and an unreadable or undecodable present template produce the distinct matrix-selected roadmap-domain treatment for every named route.

- Stage authoring and stage-feedback prompt failures retain their current non-backend behavior and do not become raw filesystem exceptions.

- A local feedback revision prompt failure returns a failed `LocalRevisionResult`, does not invoke its backend seam, and records no prompt context digest.

- A seed-materialization prompt failure does not consume a model attempt, write a draft seed, or update roadmap seed state.

- `tests/test_roadmap.py` and `tests/test_roadmap_revision_run.py` pass with the focused cases above.

## References

- [ROADMAP_FORMAT.md — Read the terminal-disposition matrix for the selected error, status, run-log, exit, and crash-report contract.](ROADMAP_FORMAT.md)

- [BACKLOG.md #347 — Read the shared roadmap text-reader rationale and caller-specific error-family boundary.](BACKLOG.md)

- [BUG_BACKLOG.md — “Two prompt-template renderers have no read-failure handling in their caller chain” identifies the unnormalized routes.](BUG_BACKLOG.md)

- [plan_tool/cli/app.py — Retain the generic unexpected-error and crash-report boundary for defects outside the named error families.](plan_tool/cli/app.py)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, model-reply handling:** This step may not capture, persist, or otherwise add model-response evidence while handling failures before an invocation.

- **The plan’s “## Scope guardrails”, interrupt handling:** Keep interrupt behavior outside these template-read branches and preserve the current interrupt owners.

- **The plan’s “## Scope guardrails”, retry and lifecycle preservation:** Normalize only expected template failures; do not redesign retries, result outcomes, publication recovery, checkpoints, or writer locking.

- **The plan’s “## Scope guardrails”, unexpected defects:** Preserve the generic crash path for errors outside the named expected template failure families.

- **The plan’s “## Out of scope”:** Do not add success-output changes, retry behavior, receipt sidecars, or broader application exception infrastructure.

## Deferred

- `plan_tool/roadmap_structural_revision_run.py:render_structural_revision_prompt` template-read and terminal treatment — This shared update-guidance consumer keeps its existing exception family because its separate structural-rewrite result contract is outside this step’s named-route and file fence.
