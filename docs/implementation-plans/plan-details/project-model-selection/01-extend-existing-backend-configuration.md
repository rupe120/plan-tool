# Step 1 — Read project backend defaults and command models

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/backend_config.py` to expose project backend defaults and per-backend command models. Add command-name normalization in `plan_tool/cli/parser.py`, derived from assembled registrations. Keep CLI knowledge outside the configuration leaf and preserve existing reader APIs. Unmarked tests in `tests/test_backend_config.py` cover the new settings, validation, normalization, and compatibility.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — The reader’s current limitation.
- [Input](#input) — Existing configuration and registration contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Reader extension and CLI boundary.
- [Tests](#tests) — Required reader and normalization cases.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant source contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries.
- [Deferred](#deferred) — Selection behavior owned outside this step.

## Why

`plan_tool/backend_config.py:load_backend_overrides` reads a backend-wide model and extra arguments, but exposes neither `default_backend` nor command models. `tests/test_backend_config.py:TestLoadBackendOverrides` pins the existing tuning contract and tolerance of unrelated settings. The existing reader is the right place to expose the additional project choices without introducing another configuration file or changing execution selection in this step.

## Input

- **Configuration:** `plan_tool/backend_config.py:default_backends_config_path` identifies `.plan-tool/backends.json`; `BackendOverride`, `_argv_field`, and `BackendConfigError` define its current typed values and validation.
- **Registrations:** `plan_tool/cli/parser.py:assemble` receives command modules, builds subparsers, and returns the parser and dispatch map. Actual parser registrations supply canonical names and aliases; `CANONICAL_COMMAND_ORDER` supplies help ordering only.
- **Compatibility:** `plan_tool/backend.py:_select_effective_backend` calls `load_backend_overrides(repo_root)` without command context. That call must remain valid and retain its backend-wide model and argv behavior.
- **Validation limits:** Read model names as free-form strings. Reading configuration does not establish model availability, suitability, or executable availability.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `plan_tool/backend_config.py` — Expose the expanded configuration, validate its new fields, and retain compatible reader entry points.
  - `plan_tool/cli/parser.py` — Expose canonical command names and alias normalization from assembled registrations.
  - `tests/test_backend_config.py` — Add unmarked configuration and command-normalization tests.

## Implementation

- **Foundational logic: parse project selection defaults using registration-derived command identities.** The shortest path is an additive configuration result plus a parser-owned normalization helper. Do not introduce a general settings registry or duplicate the command vocabulary in the reader.

- **Expose the complete configuration without replacing compatibility APIs.** Recommend a typed result containing optional `default_backend` and the backend overrides, with command models retained separately from each backend’s base `model`. Preserve the existing positional arguments, `path=` support, return shapes, and hit/miss behavior of `load_backend_overrides` and `backend_override_for`. New fields on `BackendOverride`, if used, must have defaults so existing construction remains valid.

- **Keep registration knowledge above the leaf.** In `plan_tool/cli/parser.py`, derive a canonical-name/alias mapping from the assembled top-level subparsers. Recommend accepting an assembled parser and returning plain data that the expanded reader receives explicitly. Preserve `assemble`’s existing return contract; neither `plan_tool/backend_config.py` nor backend leaves may import CLI modules or assemble the application themselves.

- **Normalize actual aliases, not spelling guesses.** Registrations in `plan_tool/cli/review_cmd.py:register` include `review` and `reconcile` for `reconcile-plan`, and `verify` for `verify-all`. Parser identity provides a way to associate aliases with their primary registration. Do not infer identity from handler equality, help-order constants, punctuation changes, or command modes. Normalize configuration keys and later lookup inputs through the same mapping.

- **Make unknown commands actionable.** The expanded reader must reject unknown command keys with `BackendConfigError` naming the configuration path, backend, offending key, and supported choices derived from the supplied registrations. Do not silently disable validation when command authority is absent: keep legacy projection calls separate from the command-aware entry point. Preserve their existing commandless behavior without requiring CLI initialization.

- **Validate the new field shapes.** An absent `default_backend` means no project default; a present value must be a non-empty string, so null and other types fail. Trim valid strings consistently with the existing model reader. Do not require the default backend to have a tuning block or hard-code provider names; backend registration and availability checks remain selection work.

- **Keep inheritance explicit.** An absent `commands` block means no command overrides. When present, `commands` and each command entry must be JSON objects. A missing or null command `model` means inherit the backend-wide model; empty, whitespace-only, and non-string models must fail with the full field location. Preserve this absence signal rather than copying the base model into each command entry.

- **Avoid order-dependent alias collisions.** If distinct supplied keys normalize to one command, reject the ambiguity with a path-bearing error rather than silently selecting a model by JSON insertion order.

- **Preserve the old tuning contract.** Keep backend-wide model trimming, extra-argv validation and ordering, arbitrary backend tuning names, and inert unrelated keys. In particular, `default`, `aspects`, and `failover` must remain uninspected; `default` must not become an alias for `default_backend`. Existing `binary`, `parser`, and `classification` keys must remain unable to change backend behavior.

- **Keep reads side-effect free.** Missing files must return unconfigured values without creating directories. Reading valid or invalid configuration must not change file bytes or persist normalized values. Update touched docstrings tersely to describe the expanded reader.

## Tests

### Tests for this step

Add these cases in `tests/test_backend_config.py`, without integration markers. Use small fake registration modules with `plan_tool/cli/parser.py:assemble` for normalization tests; do not invoke command handlers. Existing regression cases and every added case must be green before this step finishes.

- `test_expanded_reader_missing_file_returns_unconfigured_without_creating_directory` — Missing configuration yields no default or overrides and creates nothing.
- `test_default_backend_is_optional_and_trimmed` — Omission yields no default; a non-empty string is exposed without requiring a backend tuning entry.
- `test_present_default_backend_requires_nonempty_string` — Null, empty, whitespace-only, and wrong-typed values fail with the path and field.
- `test_command_models_are_separate_for_each_backend` — The same command retains distinct provider-specific models without changing either base model.
- `test_missing_and_null_command_models_preserve_inheritance` — Both forms retain the inheritance signal alongside a configured base model.
- `test_command_model_requires_nonempty_string_when_set` — Empty and wrong-typed models fail; valid strings are trimmed.
- `test_commands_and_command_entries_require_objects` — Malformed containers fail with the configuration path and field.
- `test_unknown_command_names_path_backend_key_and_supported_choices` — Unknown keys fail using the supplied registration vocabulary.
- `test_command_aliases_normalize_from_parser_registrations` — Primary names and aliases share one canonical identity, including a synthetic alias absent from production registrations.
- `test_distinct_commands_sharing_handler_keep_distinct_identities` — Handler reuse does not collapse unrelated commands.
- `test_command_names_do_not_come_from_help_order_or_nested_modes` — Synthetic registered commands work without entering `CANONICAL_COMMAND_ORDER`; nested options do not become command keys.
- `test_alias_and_primary_configuration_collision_is_rejected` — Two keys naming the same command cannot select a model by insertion order.
- `test_legacy_reader_calls_need_no_cli_context_and_preserve_results` — Existing signatures, explicit paths, return shapes, base tuning, and hit/miss behavior remain usable.
- `test_reserved_sibling_keys_remain_inert_even_when_malformed` — Unrelated sibling values are neither validated nor activated.
- `test_reader_preserves_unknown_backend_tuning_names_and_inert_fields` — Existing tolerance and the binary/parser boundary remain intact.
- `test_configuration_reads_leave_source_bytes_unchanged` — Successful reads and validation failures perform no writes.

Retain `tests/test_backend_config.py:TestBackendConfigErrors` and the existing model, argv, and structural-evaluator regression cases. Run `uv run pytest tests/test_backend_config.py tests/cli/test_cli_parser.py -q` to check the reader and unchanged parser assembly contract.

## Acceptance criteria

- The expanded reader exposes `default_backend` and normalized per-backend command models from the existing configuration file.
- Missing or null command models preserve inheritance; invalid model values and invalid present `default_backend` values raise field-specific, path-bearing errors.
- Unknown command errors include registration-derived supported choices.
- Canonical names and aliases share one identity; unrelated commands sharing a handler remain distinct.
- `load_backend_overrides` and `backend_override_for` remain callable through their existing signatures without CLI context.
- Existing model and argv behavior, arbitrary tuning backend names, and inert sibling keys remain covered by passing regression tests.
- `plan_tool/backend_config.py` has no CLI imports, and `plan_tool/backend.py` requires no edit.
- Configuration reads create no files or directories and leave source bytes unchanged.
- All added tests are unmarked, and the focused reader and parser suites pass.

## References

- [Configuration reader](../../../..//plan_tool/backend_config.py) — Read `BackendOverride`, `load_backend_overrides`, and `backend_override_for` for compatibility requirements.
- [CLI assembly](../../../../plan_tool/cli/parser.py) — Read `assemble` and `_reorder_subcommands` to distinguish registrations from help ordering.
- [Backend selection](../../../../plan_tool/backend.py) — Read `_select_effective_backend` for the unchanged commandless consumer.
- [Backend documentation](../../../BACKENDS.md) — Read the existing project tuning contract.
- [Separate backend-selection proposal](../../../design-plans/BACKEND_SELECTION.md) — Distinguish its reserved sibling keys from this step’s new settings.

## Applicable guardrails

- **The plan’s “Scope guardrails,” project defaults:** Restrict the reader extension to exposing the approved project choices; leave invocation precedence outside this step.
- **The plan’s “Scope guardrails,” model validation:** Validate field shape in `plan_tool/backend_config.py` without judging model quality or changing audit outcomes.
- **The plan’s “Out of scope,” configuration surfaces:** Keep parser normalization and configuration reading inside the declared files; add no configuration-writing or storage mechanism.
- **The plan’s “Out of scope,” routing:** Treat the registered top-level command as the identity boundary; do not interpret execution phases or modes as separate selections.

## Deferred

- Invocation selection — `plan_tool/cli/app.py:main` consumes project choices outside this reader step.
- Effective model precedence and fallback — `plan_tool/backend.py:_select_effective_backend`, `select_active_backend`, and `scoped_select_active_backend` remain unchanged here; execution selection is separate intentional work.
- Operator policy and integration updates — `docs/BACKENDS.md`, `integrations/shared/DIRECTIVES.md`, and `plan_tool/cli/skill_cmd.py` are reference-only for this step.
