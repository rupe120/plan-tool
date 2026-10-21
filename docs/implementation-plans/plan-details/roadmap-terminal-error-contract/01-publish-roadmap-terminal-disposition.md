# Step 1 — Publish the roadmap terminal disposition matrix

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Add one terminal-disposition matrix to `ROADMAP_FORMAT.md` for ordinary failures in the primary roadmap stage run and named prompt-renderer routes. The matrix must map failure origin to the human error, roadmap terminal status, run-log ending, exit code, crash-report behavior, and operator action. It must separate preflight refusal, expected failure after work begins, and unexpected exceptions without changing runtime behavior. On green, later implementation and test steps have one documented contract to apply and verify.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation change.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Explains the missing terminal contract.
- [Input](#input) — Names the current error and lifecycle boundaries the matrix documents.
- [Files (creates vs edits)](#files-creates-vs-edits) — Lists the documentation-only footprint.
- [Implementation](#implementation) — Defines the matrix content and ownership boundaries.
- [Tests](#tests) — Lists non-code verification.
- [Acceptance criteria](#acceptance-criteria) — States observable completion checks.
- [References](#references) — Points to the source contracts and tracked gaps.
- [Applicable guardrails](#applicable-guardrails) — Keeps the documentation within the plan fence.
- [Deferred](#deferred) — Identifies related work left outside this step.

## Why

`ROADMAP_FORMAT.md` explains returned roadmap outcomes and stage validation, but it does not give operators or implementers one source for exception exits that cross `plan_tool/roadmap.py:run_roadmap`, `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`, and `plan_tool/cli/app.py`'s crash boundary. That leaves the same kind of failure vulnerable to inconsistent status output, return codes, run-log endings, and crash reporting depending on where it originates.

## Input

- **Stage-run boundary:** Use `plan_tool/roadmap.py:run_roadmap`, `_roadmap_command_lifecycle`, `_error_run_end_fields`, and `_stage_run_guard` to distinguish command-level terminal facts from per-stage status facts.
- **CLI boundary:** Use `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` and its `run_roadmap` exception handling as the current return-code and human-error boundary.
- **Renderer routes:** Include `plan_tool/roadmap.py:_render_stage_prompt`, `_render_stage_feedback_prompt`, and `_render_seed_materialize_prompt`, plus `plan_tool/roadmap_revision_run.py:render_local_revision_prompt`, because their file-read failures enter different caller chains today.
- **Unexpected-error boundary:** Use `plan_tool/cli/app.py`'s generic `except Exception` path as the boundary that retains crash reporting for defects outside the roadmap error families.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Add a terminal-disposition section and matrix that documents the selected failure categories, their precedence, their consumers, and their operator actions.

## Implementation

- **Add one dedicated terminal-disposition section.** Place it near the existing roadmap run and enforcement-contract material so it is read as a command behavior contract, not as part of the on-disk artifact schema.

- **Make the matrix exhaustive for this plan’s ordinary exception scope.** Cover at least:
  - preflight refusal before stage work starts;
  - expected failure after work has started, including the mid-run writer-guard case and expected prompt-template read or decode failures;
  - unexpected exceptions that remain owned by `plan_tool/cli/app.py`.

- **Give every row the same fields.** Document the failure origin and precedence, whether work may already have occurred, the shared human-facing error treatment, roadmap-level terminal status fact, run-log outcome, CLI exit code, crash-report behavior, and the operator’s next action.

- **Define origin as the deciding rule.** `RoadmapWriterGuardError` must not be treated as one uniform disposition merely because its exception type is shared: `plan_tool/roadmap.py:run_roadmap` owns the preflight normalization path, while the publish path can fail after stage work. The matrix must make the distinction visible before a common catch in `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` loses it.

- **Treat equivalent renderer read failures consistently.** The matrix must name the four renderer seams and require equivalent missing-template, unreadable-template, or decode failures to select the same expected-failure treatment when their route reaches the primary roadmap command. Preserve each route’s legitimate preflight-versus-mid-run origin; consistency does not require flattening those origins.

- **Separate stage status from command status.** `plan_tool/roadmap.py:_stage_run_guard` owns the stage-level `stopped` fact for an exception within a stage. The roadmap-level terminal fact belongs at the command boundary, must occur once, and must follow any final stage fact without replacing the original return or exception path.

- **Keep unexpected defects unexpected.** The matrix must state that errors outside the documented roadmap-domain and environmental families continue through `plan_tool/cli/app.py`’s crash-report path. Do not describe broad exception handling as a way to make programming defects look like clean roadmap failures.

- **Keep the document authoritative but code-subordinate.** Match the source-of-truth convention at the top of `ROADMAP_FORMAT.md`: cite `plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`, and `plan_tool/cli/app.py` by symbolic anchor, and state that code remains authoritative if the matrix later disagrees with implementation.

## Tests

### Verification (non-code step)

1. **Matrix route coverage** — Confirm every ordinary exception route named in the plan references a matrix row: `run_roadmap`, `cmd_roadmap`, the four prompt renderers, and the generic application crash boundary.
2. **Matrix field completeness** — Confirm every row states origin, precedence, human error, terminal status, run-log ending, exit code, crash behavior, and operator action.
3. **Writer-guard distinction** — Confirm the matrix separately describes preflight and post-start writer-guard failures.
4. **Renderer consistency** — Confirm the four named renderer routes receive the same expected-failure treatment for equivalent read or decode failures while retaining their own origin.
5. **Status ordering** — Confirm the text assigns per-stage status to `_stage_run_guard` and one final roadmap status to the command boundary.
6. **Crash preservation** — Confirm unexpected exceptions remain assigned to `plan_tool/cli/app.py` and are not documented as clean roadmap errors.
7. **Reference accuracy** — Confirm every cited symbol exists at HEAD with `rg`, and no raw line-number anchors appear in the new section.

## Acceptance criteria

- `ROADMAP_FORMAT.md` contains one terminal-disposition matrix for the roadmap command’s ordinary exception exits.
- Each matrix row names the failure origin, precedence, human error treatment, terminal status, run-log outcome, exit code, crash-report behavior, and operator action.
- The matrix distinguishes preflight writer-guard refusal from a writer-guard failure after work begins.
- The matrix names all four prompt-renderer routes and gives equivalent read or decode failures one expected-failure treatment.
- The matrix assigns stage-level status ownership to `plan_tool/roadmap.py:_stage_run_guard` and roadmap-level terminal status ownership to `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`.
- The matrix preserves `plan_tool/cli/app.py`’s crash-report behavior for unexpected exceptions.
- No production code or test file is changed by this step.

## References

- [BACKLOG.md #344](BACKLOG.md) — Read for the preflight versus mid-run writer-guard exit-code distinction.
- [BACKLOG.md #347](BACKLOG.md) — Read for the prompt-reader exception-family boundary.
- [BACKLOG.md #348](BACKLOG.md) — Read for the missing terminal-status path on raised stage-run exceptions.
- [BUG_BACKLOG.md](BUG_BACKLOG.md) — Read “Two prompt-template renderers have no read-failure handling in their caller chain.”
- [ROADMAP_FORMAT.md](ROADMAP_FORMAT.md) — Update the existing roadmap lifecycle and enforcement reference.
- [plan_tool/roadmap.py](plan_tool/roadmap.py) — Read `run_roadmap`, `_roadmap_command_lifecycle`, `_stage_run_guard`, and the prompt renderers.
- [plan_tool/cli/roadmap_cmd.py](plan_tool/cli/roadmap_cmd.py) — Read `cmd_roadmap`’s primary stage-run dispatch and exception mapping.
- [plan_tool/cli/app.py](plan_tool/cli/app.py) — Read the generic unexpected-error and crash-report boundary.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, model-reply evidence boundary** — Document dispositions only; this step must not introduce a response-capture or receipt contract.
- **The plan’s “## Scope guardrails”, interrupt boundary** — Keep `KeyboardInterrupt`, `SystemExit`, and broader interrupt behavior outside the matrix’s implementation direction.
- **The plan’s “## Scope guardrails”, existing lifecycle boundary** — Describe current result, retry, publication, checkpoint, and writer-lock boundaries without redesigning them.
- **The plan’s “## Scope guardrails”, unexpected-defect boundary** — Preserve the application crash path as the documented treatment for unexpected programming defects.
- **The plan’s “## Out of scope”** — Do not turn this documentation step into rollback, recovery, lock-policy, success-output, or retry work.

## Deferred

- Runtime exception classification and CLI wiring — Later steps apply this matrix to `plan_tool/roadmap.py` and `plan_tool/cli/roadmap_cmd.py`.
- Prompt-reader consolidation — Later work may select a shared helper only if it preserves each caller’s error family and message.
- Interrupt and normal stage-stop semantics — Remain outside this step under the plan’s stated scope fence.
