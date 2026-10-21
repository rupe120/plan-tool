> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Characterize generate_detail’s exact signature and extract parse to Jira or run-grade dispatch

## Summary

Make `plan_tool/detail.py:generate_detail` enter through a named same-file parse-and-dispatch phase. Preserve its exact public callable contract, current mode validation order, single `parse_plan` call, and direct Jira-grade handoff to `plan_tool/detail.py:_generate_jira_detail`. Update `tests/test_detail.py` to pin the complete signature and the outer dispatch boundary. On green, Jira authoring cannot enter run-grade setup, while existing callers keep the same API and results.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the extraction and its green result.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why the outer boundary needs a direct characterization.
- [Input](#input) — Public API and parsed-plan contracts this phase reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two files this step changes.
- [Implementation](#implementation) — Required dispatch behavior and extraction boundary.
- [Tests](#tests) — Regression coverage for the public contract and dispatch order.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for signature and test assertions.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this refactor.
- [Deferred](#deferred) — Later phase work deliberately left out of this step.

## Why

HEAD already sends `GRADE_JIRA` from `plan_tool/detail.py:generate_detail` to `plan_tool/detail.py:_generate_jira_detail` after parsing the plan, and `tests/test_detail.py:TestJiraGradeAuthoring` covers many Jira-lane outcomes. What remains is to make that outer boundary independently reviewable and pin the complete public contract, so later phase extractions cannot silently move run-grade work before the Jira fork or alter a direct caller’s keyword-only API.

## Input

- **Public callable contract:** `plan_tool/detail.py:generate_detail` keeps `plan_path` as its sole positional-or-keyword argument and retains, in order, the keyword-only parameters `repo_root`, `step_id`, `force`, `dry_run`, `invoker`, `reporter`, `extract_lessons`, `lessons_invoker`, `foundational_invoker`, `capture_scenarios`, `arm`, `strict_check`, `equivalence_invoker`, `resume`, `prompt_fn`, `yes`, `run_logger`, `budget`, `allow_drift`, `auto_reconcile_on_drift`, `collision_sidecar`, `triage`, `include_info`, `allow_split`, `jobs`, `commit_step`, `prior_body`, and `grade`.
- **Parsed plan:** `plan_tool/parser.py:parse_plan`, imported by `plan_tool/detail.py`, supplies the single `Plan` instance that the Jira lane and later run-grade phases consume. Preserve its existing `ParseError` and `ValidationError` conversion to `DetailError`.
- **Grade selection:** `plan_tool/jira_grade.py:GRADE_JIRA` selects `plan_tool/detail.py:_generate_jira_detail`; every other current path remains the run-grade path selected by `GRADE_RUN`.
- **Separate parsing concern:** `plan_tool/detail.py:parse_detail_response`, `plan_tool/detail.py:parse_jira_detail_response`, and `plan_tool/detail.py:_author_step_detail` parse model responses after authoring. They are not part of this plan-file parse-and-dispatch phase.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — extract the public entry’s validation, plan parse, and Jira/run-grade selection into a named same-file phase without changing its callable surface or lane behavior.
  - `tests/test_detail.py` — add direct regression coverage for the full signature, parse error conversion, pre-parse mode guards, and Jira bypass of run-grade setup.

## Implementation

- **Foundational logic:** preserve grade-selected plan parsing and outer dispatch.

- **Keep `plan_tool/detail.py:generate_detail` as the public entry.** Retain `@spawn_cwd_from_repo_root`, the exact ordered signature, every parameter kind, each default object or value, annotations, and the `list[DetailResult]` return annotation. `plan_tool/__init__.py` re-exports this function, while `plan_tool/cli/authoring.py:cmd_detail`, `plan_tool/cli/review_actions.py:_dispatch_detail`, `plan_tool/bench.py:_run_detail`, and recursive calls in `plan_tool/detail.py` depend on that stable surface.

- **Extract one named outer phase.** One approach is a self-descriptive same-file helper that owns the existing early validation, calls `plan_tool/parser.py:parse_plan` once through its existing import, and either returns Jira results immediately or hands the parsed `Plan` to the later run-grade phases. Do not require a new module, a schema change, or caller rewrites for this boundary.

- **Preserve validation before parsing.** Keep the `jobs < 1` serial floor and the existing incompatible-mode `DetailError` guards in their current order before plan parsing. Jira-grade rejection of an enabled convergence budget or `jobs > 1` must still occur before any plan or authoring work.

- **Keep the Jira fork immediate.** After a successful parse, `GRADE_JIRA` must call `plan_tool/detail.py:_generate_jira_detail` with the same Jira-lane inputs and return its results directly. Do not enter run-grade concept loading, detail-pointer handling, orphan adoption, checkpoint pre-scan, or run-grade artifact work first.

- **Keep run-grade handoff explicit.** The non-Jira path must receive the one parsed `Plan` and continue with the existing run-grade code. This step does not extract that setup or lifecycle; it only establishes the boundary that later phases consume.

- **Do not merge response gates.** Leave `plan_tool/detail.py:parse_detail_response` and `plan_tool/detail.py:parse_jira_detail_response` in their current lanes. Their similar envelope cleanup serves different run-grade and Jira-grade contracts, and combining them is outside this extraction.

## Tests

### Tests for this step

- `test_generate_detail_signature_is_exact` — assert `inspect.signature(plan_tool.detail.generate_detail)` has the complete ordered parameter list, parameter kinds, defaults, annotations, and `list[DetailResult]` return annotation.
- `test_parse_dispatch_wraps_plan_parse_failure_as_detail_error` — pass an invalid plan and assert the public entry retains the current `DetailError` parse-failure behavior.
- `test_jira_mode_rejections_happen_before_plan_parse` — parameterize the Jira-only invalid mode combinations and assert they raise before `plan_tool/parser.py:parse_plan` can run through `plan_tool.detail`.
- `test_jira_dispatch_parses_once_and_bypasses_run_grade_setup` — spy on `plan_tool.detail`'s imported `parse_plan` binding, defined by `plan_tool/parser.py:parse_plan`, make the first run-grade setup operation fail if reached, and assert a Jira invocation writes through its existing lane after exactly one parse.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail` retains its exact introspected signature, including keyword-only parameters, defaults, annotations, and return annotation.
- A malformed plan still raises `DetailError` through the public entry.
- Jira-only invalid mode combinations fail before parsing or invoking an authoring backend.
- A Jira-grade call parses its plan once, returns through `plan_tool/detail.py:_generate_jira_detail`, and does not enter run-grade setup.
- Existing Jira-lane assertions in `tests/test_detail.py:TestJiraGradeAuthoring` continue to show that Jira authoring leaves run-grade pointers and artifacts alone.
- `uv run pytest tests/test_detail.py -q` passes.

## References

- [Python inspect.signature API](https://docs.python.org/3.13/library/inspect.html#inspect.signature) — Use it to characterize parameter order, kinds, defaults, annotations, and the return annotation.
- [Python 3.13 Execution Model](https://docs.python.org/3.13/reference/executionmodel.html) — Use it when moving local orchestration state into a same-file phase helper.
- [pytest Monkeypatching Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use scoped spies and fail-fast replacements to prove the dispatch bypass.
- [pytest Assertion and Exception Testing](https://docs.pytest.org/en/stable/how-to/assert.html) — Use `pytest.raises` to pin the preserved public error behavior.

## Applicable guardrails

- **The plan’s “## Plan intent”, named phase map:** limit this step to the first parse-and-dispatch boundary; leave later run-grade phases for their owning steps.
- **The plan’s “## Step intent”, direct Jira routing:** make the Jira return point precede any run-grade-only work.
- **The plan’s “## Out of scope”, public contract:** do not add, remove, rename, reorder, or reinterpret `generate_detail` parameters or observable behavior.
- **The plan’s “## Out of scope”, separate structural mechanisms:** do not move, merge, or redesign Phase B, Trigger 2, the convergence loop, `create_plan`, or `plan_tool/cli/run_cmd.py:cmd_run`.

## Deferred

- Run-grade setup and lifecycle extraction — steps 2 and 3 own the preparation and authoring phases after this handoff.
- Post-loop split handling and concept persistence extraction — steps 4 through 6 own those later outer phases.
- Shared response-envelope parsing for `plan_tool/detail.py:parse_detail_response` and `plan_tool/detail.py:parse_jira_detail_response` — leave their distinct contracts unchanged; this step only separates plan parsing and grade dispatch.
