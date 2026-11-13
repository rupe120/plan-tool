# Step 3 — Honor project selection at CLI entry

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Wire project backend defaults and command models into `plan_tool/cli/app.py:main`. Resolve the repository root before reading project settings, then pass the normalized top-level command to the existing effective-backend selector once before dispatch. Preserve explicit overrides, backend registration, provisional synthesis, warnings, and executable checks. Add integration coverage in `tests/cli/test_app.py` proving that project choices reach ordinary and nested calls without changing unconfigured behavior.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Missing project selection at CLI entry.
- [Input](#input) — Dependency outputs and existing selection contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Invocation selection and compatibility.
- [Tests](#tests) — Integration cases and verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant source owners.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on selection changes.
- [Deferred](#deferred) — Work outside invocation wiring.

## Why

`plan_tool/cli/app.py:main` selects a backend from invocation flags, model-family inference, or the environment before resolving the repository root. It passes no command context to `plan_tool/backend.py:select_active_backend`, so project command models cannot affect that selection. The existing root resolver and effective-backend owner provide the necessary boundaries; this step connects them so scripts and assistant sessions honor repository choices without repeating flags. The heuristic match on `main` confirms the host function exists, not that project-default or command-aware selection is implemented.

## Input

- **Step 1 output:** Consume the project configuration reader and registration-derived command normalization from `plan_tool/backend_config.py` and `plan_tool/cli/parser.py`. Read their landed names and signatures; those take precedence over names proposed in sibling details.
- **Step 2 output:** Use the optional command context on `plan_tool/backend.py:select_active_backend`. Step 2 owns effective-model precedence and compatibility for callers without command context.
- **Repository identity:** Reuse `plan_tool/cli/context.py:_resolve_cmd_repo_root`. Its existing flag, environment, ancestor-search, and fresh-directory behavior defines which project supplies settings.
- **Selection result:** Preserve `plan_tool/backend.py:BackendSelection`, including the distinction between `selected` and `effective` and its unknown-override diagnostics.
- **Invocation identity:** Use the parsed top-level command. `args.mode` and reconciliation options select behavior within a command; they do not establish another command-model lookup.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — Read project selection inputs after root resolution, extend backend precedence, forward canonical command context, and preserve selection diagnostics and preflight behavior.
  - `tests/cli/test_app.py` — Add integration tests through `cli.main` with real project configuration and fake backend invokers.

## Implementation

- **Foundational logic: choose one backend and effective model for the top-level invocation.** The shortest path is to resolve the root, read project defaults through step 1’s reader, choose the backend in `main`, and call step 2’s existing selector with command context. Keep model precedence in `plan_tool/backend.py:_select_effective_backend`; do not recreate it in the CLI or downstream handlers.

- **Resolve the root before project reads.** Move the existing `plan_tool/cli/app.py:main` root-resolution call ahead of configuration-dependent selection. Both the project-default read and `select_active_backend` must receive that same root. Do not infer the configuration location from the plan path, plans directory, or package checkout.

- **Apply backend precedence in this order:**
  1. Explicit `--backend`.
  2. Backend family recognized from explicit `--model`.
  3. Nonempty `PLAN_TOOL_BACKEND`.
  4. Project `default_backend`.
  5. Claude.

- **Infer only from the explicit model.** Keep `plan_tool/model_specs.py:backend_for_model` as the inference owner. A model read from project configuration must not switch the selected backend. An unrecognized explicit model must remain an explicit model override while backend selection continues through the remaining precedence levels.

- **Normalize command identity once before selection.** Use step 1’s registration-derived normalization against the assembled parser. Forward the canonical command through `select_active_backend` without replacing the parsed dispatch key unless the landed parser API requires it. Aliases must use their canonical command’s model setting while existing dispatch and locking behavior remains intact.

- **Keep the parent command throughout execution.** Every `run` mode must use the `run` command setting, and detail reconciliation must use `detail`. Nested audits and applies must reuse the active effective descriptor rather than selecting the settings for independently invokable audit or reconciliation commands.

- **Reuse downstream selection unchanged.** `plan_tool/cli/authoring.py:cmd_create` and `cmd_detail`, `plan_tool/cli/run_cmd.py:cmd_run`, and the apply path in `plan_tool/cli/completeness_phases.py:_run_iterate_convergence_loop` remain consumers of invocation selection. `plan_tool/shell.py:claude_invoke` and `plan_tool/launcher.py:apply_finding` reach the active backend through the existing backend seams. Verify these paths through tests; do not add routing calls to them.

- **Preserve registration and provisional synthesis.** Continue selecting through `select_active_backend` with `plan_tool/cli/app.py:_synthesize_unregistered_backend` as the fallback factory. Preserve its explicit-model handling and catalog fallback, along with provisional and unknown-override warnings. Stub catalog access in tests that exercise synthesis.

- **Treat a project-selected backend like an environment-selected backend for preflight.** A project-selected Claude backend must receive an executable check, just as explicit environment selection of Claude does. Preserve lazy behavior for an unconfigured implicit Claude default and the existing model-only Claude case. Preserve the existing interaction with an explicitly configured environment value.

- **Keep diagnostic reasoning consistent with precedence.** When determining whether explicit model inference changes selection, compare against the backend that environment, project, and default selection would otherwise choose. Missing-executable guidance must account for project defaults: unsetting `PLAN_TOOL_BACKEND` alone cannot promise a return to Claude when the project selects another backend.

- **Keep failures inside the existing selection error boundary.** Malformed project configuration must produce the normal `BackendConfigError` diagnostic and return code 2 before dispatch. Preserve existing executable-failure codes, warning behavior, rate-limit policy setup, console verbosity, and repository mutation locking.

## Tests

Add the following cases in `tests/cli/test_app.py`. Mark tests that drive `cli.main` as integration tests. Use real configuration parsing and effective selection; fake invokers must record the active backend and resolved model instead of launching a backend binary. Keep the subprocess guard in `tests/conftest.py` enabled and restore environment, active selection, and registry changes between cases.

### Tests for this step

- `test_project_codex_default_uses_distinct_create_and_detail_models` — Separate create and detail invocations in one project reach fake invokers with Codex and their respective command models.
- `test_explicit_backend_wins_over_model_environment_and_project` — Conflicting lower-priority choices cannot replace an explicit backend; the explicit model remains authoritative.
- `test_recognized_explicit_model_family_wins_over_environment_and_project` — Model-family inference chooses the backend ahead of environment and project defaults.
- `test_unrecognized_explicit_model_preserves_lower_priority_backend_selection` — An opaque model string overrides the model without supplying a backend family.
- `test_environment_backend_wins_over_project_default` — Environment selection uses the selected backend’s command model rather than another backend’s settings.
- `test_project_default_precedes_implicit_claude_and_empty_environment` — Project selection wins when no higher-priority backend input exists.
- `test_command_alias_uses_canonical_command_model` — Registered aliases select the canonical command setting and still dispatch successfully.
- `test_run_modes_keep_run_command_model` — Supported run modes retain `run` selection even when configuration contains different settings for related commands.
- `test_detail_reconciliation_keeps_detail_command_model` — Detail reconciliation uses the detail setting rather than a reconciliation command setting.
- `test_nested_audits_and_applies_reuse_parent_selection` — A driven nested audit/apply path records the same active backend and model throughout, despite conflicting nested-command defaults.
- `test_project_selection_uses_resolved_repository_root` — Parameterized flag, environment, and ancestor-search cases read the resolver-selected project rather than a competing project under cwd.
- `test_sequential_projects_do_not_reuse_previous_project_selection` — Invocations for differently configured repositories replace active selection without leaking command models.
- `test_malformed_project_selection_returns_usage_error_before_dispatch` — Invalid JSON and invalid new configuration fields report the offending configuration and return 2 without invoking a handler.
- `test_selected_backend_executable_is_checked_for_project_and_environment_sources` — Explicit project and environment choices, including Claude, preserve missing-executable failure behavior.
- `test_unconfigured_read_only_command_does_not_require_claude` — An unconfigured `list` invocation succeeds when Claude is unavailable.
- `test_model_only_claude_selection_preserves_lazy_preflight` — The existing model-only Claude exemption remains intact.
- `test_project_selection_preserves_registration_synthesis_and_warnings` — Registered and provisional descriptors retain their existing selection paths and warning contracts.
- `test_missing_executable_guidance_accounts_for_project_default` — Diagnostics offer a valid override and do not claim that removing an environment setting necessarily restores Claude.

Every added or changed test must be green before this step finishes. Run the affected integration cases during development, then the full pytest suite. Verify the new precedence and preflight assertions by temporarily breaking the relevant branch and confirming that the corresponding test fails.

## Acceptance criteria

- `plan_tool/cli/app.py:main` resolves the repository root before reading project selection settings.
- Backend selection follows the specified precedence across conflicting inputs.
- The existing selector receives the normalized parsed top-level command once before dispatch.
- One project can select Codex with distinct create and detail models without invocation flags.
- Aliases, run modes, detail reconciliation, nested audits, and applies retain the intended command selection.
- Project-selected backends receive environment-equivalent executable checks; unconfigured read-only commands remain usable without Claude installed.
- Malformed configuration returns 2 before dispatch, and executable failures retain their existing return code.
- Registration, provisional synthesis, unknown-override warnings, and model-inference guidance remain covered.
- Production changes are confined to `plan_tool/cli/app.py`; the shared reader, selector, root resolver, and downstream consumers remain unchanged in this step.
- The affected integration tests and full pytest suite pass without real backend calls or catalog network access.

## References

- [Project configuration reader](plan_tool/backend_config.py) — Read the landed step 1 API and configuration error contract.
- [Effective backend selection](plan_tool/backend.py) — Use `select_active_backend` and `_select_effective_backend` for effective descriptors and model precedence.
- [CLI entry point](plan_tool/cli/app.py) — Inspect `main` and `_synthesize_unregistered_backend` for selection, warnings, and preflight.
- [Repository root resolution](plan_tool/cli/context.py) — Reuse `_resolve_cmd_repo_root` without another root-search implementation.
- [Command registration](plan_tool/cli/parser.py) — Read `assemble` and step 1’s registration-derived normalization.
- [Backend operator guide](docs/BACKENDS.md) — Preserve established invocation overrides and backend behavior.

## Applicable guardrails

- **The plan’s “Scope guardrails,” project selection boundary:** Limit `main` to connecting the project reader and existing selector; do not add another settings framework or relocate configuration.
- **The plan’s “Scope guardrails,” explicit overrides and compatibility:** Preserve higher-priority invocation inputs and the unconfigured read-only path.
- **The plan’s “Out of scope,” routing boundary:** Use command context only at invocation entry; nested backend calls must not introduce another routing layer.
- **The plan’s “Scope guardrails,” validation boundary:** Preserve existing configuration and preflight diagnostics without adding semantic model judgments or changing exit-code policy.

## Deferred

- Shared configuration parsing and effective-model precedence — Steps 1 and 2 own these contracts; this step consumes their landed APIs unchanged.
- Fallback recovery selection in `plan_tool/shell.py` and `plan_tool/launcher.py` — Preserve the independent scoped recovery contract covered by step 2.
- Operator documentation and copied integration content — Keep this step’s edits within its declared CLI and test files.
- Aspect-based routing in `docs/design-plans/BACKEND_SELECTION.md` — It is a separate proposal and supplies no additional implementation requirements here.
