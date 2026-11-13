# Step 2 — Select effective models with optional command context

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend effective-backend selection in `plan_tool/backend.py` with optional command context. Keep model precedence in `_select_effective_backend` and reuse `build_effective_backend` unchanged for batch and streaming arguments. Preserve commandless selection, including fallback recovery. Add unmarked tests in `tests/test_backend.py`, `tests/test_shell.py`, and `tests/test_launcher.py` that prove precedence, backend isolation, descriptor preservation, and recovery restoration.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Missing command-aware selection.
- [Input](#input) — Configuration and descriptor contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Selection precedence and compatibility.
- [Tests](#tests) — Selection and recovery coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant source anchors.
- [Applicable guardrails](#applicable-guardrails) — Step-specific boundaries.
- [Deferred](#deferred) — Invocation wiring outside this step.

## Why

`plan_tool/backend.py:_select_effective_backend` selects an explicit model, a project backend model, or a manifest default, but accepts no command context. `tests/test_backend.py:test_select_active_backend_sets_effective_backend_globally` pins the project-model behavior and both argument paths. Extending this existing owner lets ordinary invocations use command defaults without creating another precedence implementation or changing the independent selection used during fallback recovery.

## Input

- **Step 1 output:** Consume the project configuration reader’s per-backend command models. Read the landed API and field names from `plan_tool/backend_config.py`; its implementation takes precedence over names suggested in sibling detail prose.
- **Selected descriptor:** `plan_tool/backend.py:CliBackend` supplies `name`, `default_model`, and `model_flag`. `resolved_model` records the effective choice separately from the manifest default.
- **Selection result:** Preserve `plan_tool/backend.py:BackendSelection`, including its selected descriptor, effective descriptor, and unknown-override diagnostics.
- **Command identity:** Accept canonical command context supplied by the caller. Step 1 owns registration-derived normalization in `plan_tool/cli/parser.py`; this step must not import CLI registration knowledge into `plan_tool/backend.py`.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/backend.py` — Extend the selection owner and its public entry points with optional command context; document precedence and commandless compatibility.
  - `tests/test_backend.py` — Add unmarked precedence, inheritance, isolation, descriptor, and argument-path tests.
  - `tests/test_shell.py` — Extend existing recovery tests with configured fallback models and restoration assertions.
  - `tests/test_launcher.py` — Extend existing recovery tests through real scoped selection while retaining fake subprocesses.

## Implementation

- **Foundational logic: select one effective model for the already-selected backend.** Extend `plan_tool/backend.py:_select_effective_backend` rather than adding precedence logic to argument builders or recovery loops. The shortest path is one additional lookup before the existing backend-wide model lookup.

- **Add optional command context consistently.** Add a keyword-only `command` parameter defaulting to `None` to `_select_effective_backend`, `select_active_backend`, and `scoped_select_active_backend`. Both public entry points must forward it to the shared owner. Existing arguments and commandless calls must retain their behavior.

- **Apply this precedence in order:**
  1. Caller-supplied explicit model.
  2. Selected backend’s model for the supplied command.
  3. Selected backend’s base project model.
  4. Selected descriptor’s manifest `default_model`.
  5. No injected model; leave the provider to choose.

- **Keep lookups backend-local.** Continue choosing project overrides through the resolved descriptor’s `selected.name`. A missing command entry must inherit that backend’s base model; it must not borrow another backend’s command model or the currently active descriptor’s `resolved_model`. An absent command must skip command-model selection entirely.

- **Reuse argument construction unchanged.** Pass the chosen model and existing project extras to `plan_tool/backend.py:build_effective_backend`. Keep its transport wrappers, prompt placement, model-flag validation, `resolved_model` handling, and no-op identity behavior unchanged. Do not add a second batch or streaming model-injection path.

- **Preserve descriptors and diagnostics.** Selection must leave registry descriptors, their builders, and manifest defaults unchanged. Retain unknown-override reporting and synthesized-backend handling. Existing `dataclasses.replace` calls create descriptor variants only; they perform no artifact replacement and need no artifact lifecycle work.

- **Keep the complete production caller set bounded.** Inside `plan_tool/backend.py`, update the forwarding calls in `select_active_backend` and `scoped_select_active_backend`. Leave `plan_tool/cli/app.py:main` unchanged here; invocation command forwarding belongs to the later wiring work. Leave the scoped-selection calls in `plan_tool/shell.py:_select_switch_backend` and `plan_tool/launcher.py:_select_switch_backend` commandless and unchanged.

- **Prove recovery independence through real selection.** Extend the existing shell and launcher switch tests with distinct primary, fallback base, and fallback command models. The primary selection must use a model different from the fallback base model. Recovery must choose the fallback base model despite the configured command entry, then restore the exact primary effective descriptor after success or terminal failure. Keep subprocesses fake; a selector stub that directly installs a prepared fallback descriptor cannot prove this property.

## Tests

Keep all added coverage unmarked and hermetic. Establish commandless regression cases before changing selection; these can pass against HEAD. New command-aware cases land with the additive API. Every listed case must be green before the step finishes.

### Tests for this step

- `tests/test_backend.py:test_command_model_precedence_uses_the_first_available_source` — Parameterize both public selection entry points across explicit, command, backend base, manifest, and provider-omission choices.
- `tests/test_backend.py:test_missing_command_model_inherits_the_selected_backends_base_model` — A command without an entry inherits the selected backend’s base model.
- `tests/test_backend.py:test_commandless_selection_ignores_configured_command_models` — Omitted command context and `command=None` preserve the existing selection chain.
- `tests/test_backend.py:test_explicit_model_overrides_command_and_base_models` — An explicit invocation model remains authoritative when all lower sources exist.
- `tests/test_backend.py:test_command_models_do_not_cross_backend_boundaries` — Selection uses only the resolved backend’s settings, including when another backend has the requested command.
- `tests/test_backend.py:test_command_selection_preserves_registry_descriptors_and_manifest_defaults` — Extend the invariant beside `test_select_active_backend_does_not_replace_registry_seed`; registry identity, original arguments, and `default_model` remain unchanged.
- `tests/test_backend.py:test_selected_command_model_reaches_both_argument_paths` — Batch and streaming arguments contain the same selected model, with their own extras before it and prompt transport preserved.
- `tests/test_backend.py:test_provider_omission_preserves_the_unconfigured_descriptor` — With no model source or extras, selection retains the registry object and injects no model pair.
- `tests/test_backend.py:test_scoped_command_selection_restores_the_primary_descriptor` — Scope exit restores the prior effective descriptor after normal return and an exception.
- `tests/test_shell.py:test_claude_invoke_switch_policy_switches_backend_without_prompt` — Extend the existing success case to assert fallback base-model arguments, ignored fallback command defaults, and exact primary restoration.
- `tests/test_shell.py:test_claude_invoke_scoped_switch_restores_after_fallback_failure` — Extend the existing failure case with the same model assertions and restoration after recovery stops.
- `tests/test_launcher.py:test_shell_invoker_switch_policy_switches_without_prompt` — Exercise real scoped selection with project configuration; assert fallback base-model streaming arguments and primary restoration while retaining existing recovery assertions.
- `tests/test_launcher.py:test_shell_invoker_switch_policy_restores_after_fallback_rate_limit` — Exercise real scoped selection on terminal fallback failure and assert the fallback base model and exact primary restoration.

## Acceptance criteria

- Both public selection entry points accept optional command context and use the same precedence owner.
- Explicit model, selected-backend command model, selected-backend base model, manifest default, and provider omission win in that order.
- Commandless calls retain existing behavior, even when command models exist in project configuration.
- Batch and streaming arguments use the chosen model through unchanged `plan_tool/backend.py:build_effective_backend`.
- Registry descriptors and manifest defaults remain unchanged; the unconfigured no-op selection retains descriptor identity.
- Recovery tests prove fallback base-model selection and primary restoration after success and failure.
- `plan_tool/shell.py`, `plan_tool/launcher.py`, and `plan_tool/cli/app.py` have no changes from this step.
- All tests in `tests/test_backend.py`, `tests/test_shell.py`, and `tests/test_launcher.py` pass, followed by the full pytest suite.

## References

- [Effective-backend selection](../../../../plan_tool/backend.py) — Read `_select_effective_backend`, `select_active_backend`, `scoped_select_active_backend`, and `build_effective_backend` for ownership and descriptor behavior.
- [Project backend configuration](../../../../plan_tool/backend_config.py) — Read the landed step 1 output for command-model settings and compatible reader APIs.
- [Backend operator guide](../../../BACKENDS.md) — Read the existing selection policy and project override behavior.
- [Invocation boundary](../../../../plan_tool/cli/app.py) — Read `main` to distinguish this selection extension from later command forwarding.

## Applicable guardrails

- **Plan “Scope guardrails,” explicit overrides and compatibility:** Keep the new lookup inside `plan_tool/backend.py` and preserve existing commandless callers and explicit-model authority.
- **Plan “Scope guardrails,” model validation:** Treat model names as configuration values; add no quality judgment or availability check to selection.
- **Plan “Out of scope,” recovery policy:** Change recovery tests only. Neither recovery loop gains command context or routing behavior.
- **Plan “Out of scope,” configuration framework:** Consume step 1’s reader output without introducing another configuration source or selection framework.

## Deferred

- Command forwarding from `plan_tool/cli/app.py:main` — Later invocation wiring supplies normalized command context; this step exposes the compatible API.
- Command-name normalization in `plan_tool/cli/parser.py` — Step 1 owns command identities; selection consumes them without importing the parser.
- Operator documentation and bundled integration guidance — Later plan work describes the completed invocation behavior.
