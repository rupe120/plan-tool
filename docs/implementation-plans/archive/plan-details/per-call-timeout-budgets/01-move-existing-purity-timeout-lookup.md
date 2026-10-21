# Step 1 — Move the existing purity timeout lookup into the shell layer

## Summary

Move purity timeout resolution from `plan_tool/cli/completeness_phases.py` into `plan_tool/shell.py`. Keep `PURITY_CLAUDE_TIMEOUT_S` as the purity phase’s default, but have the shell layer decide whether the legacy global setting replaces or disables it before the purity scope is entered. Preserve the existing dynamic timeout scope and unscoped `claude_invoke` behavior. On green, purity scans retain their current default and legacy override semantics, while later phase-specific settings have one precedence owner.

## Table of Contents

- [Summary](#summary) — The step’s outcome and unchanged behavior.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why timeout lookup needs one owner.
- [Input](#input) — Existing timeout and scope contracts this refactor relies on.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped file changes.
- [Implementation](#implementation) — Required ownership, precedence, and scope rules.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the affected APIs.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this refactor.

## Why

`plan_tool/cli/completeness_phases.py:_purity_timeout_s` reads `PLAN_TOOL_CLAUDE_TIMEOUT` itself and imports `plan_tool/shell.py:_parse_timeout_seconds`, while `plan_tool/shell.py:_effective_subprocess_timeout` also owns timeout parsing for the subprocess boundary. That splits precedence across two layers and makes the next step’s phase settings likely to duplicate or bypass shell behavior. Put the lookup beside the dynamic scope and subprocess timeout resolution so purity keeps its current behavior and later settings have one clear owner.

## Input

- **Purity default and current lookup:** `plan_tool/cli/completeness_phases.py:PURITY_CLAUDE_TIMEOUT_S` supplies the 900-second default, and `_purity_timeout_s` currently applies the legacy environment override before `_collect_purity_split_findings` enters `scoped_claude_timeout`.

- **Shell timeout contract:** `plan_tool/shell.py:_parse_timeout_seconds` accepts only positive numeric values; `plan_tool/shell.py:_effective_subprocess_timeout` feeds the active scope or legacy global setting to `plan_tool/shell.py:_run_once`.

- **Dynamic-scope contract:** `plan_tool/shell.py:scoped_claude_timeout` uses a `ContextVar` token, so nested scopes must restore the value that was active before entry.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/shell.py` — Add the shell-owned timeout resolver and preserve the distinction between no active timeout scope and an active scope that intentionally disables timeouts.
  - `plan_tool/cli/completeness_phases.py` — Remove `_purity_timeout_s` and use the shell-owned resolution path while retaining the purity default and the existing scope around `_collect_purity_split_findings`.
  - `tests/test_shell.py` — Cover resolver precedence, explicit disabled values, and nested scope restoration.
  - `tests/cli/test_completeness_cmd.py` — Replace the direct phase-private lookup test with coverage that observes the timeout bound during a real purity-collector call.

## Implementation

- **Make timeout resolution shell-owned.** Add a resolver near `plan_tool/shell.py:_parse_timeout_seconds` and `plan_tool/shell.py:_effective_subprocess_timeout` that can combine a caller-provided default, a future named phase setting, and the legacy `PLAN_TOOL_CLAUDE_TIMEOUT` fallback. This step must use it only for the existing purity path; step 2 owns introducing phase-specific setting names.

- **Keep purity’s default in the phase module.** `plan_tool/cli/completeness_phases.py:PURITY_CLAUDE_TIMEOUT_S` describes the purity scan’s current default, so `_collect_purity_split_findings` should pass that default to the shell layer rather than moving purity policy into generic shell code.

- **Preserve the current purity result.** With no usable legacy override, purity remains bounded at 900 seconds. A positive legacy value replaces that default. The current non-empty disabled or malformed values still produce no timeout rather than silently returning to 900 seconds.

- **Represent explicit no-timeout separately from no scope.** The shell layer must distinguish an unscoped call, where `plan_tool/shell.py:_effective_subprocess_timeout` may read the legacy global setting, from a scoped purity call that intentionally resolves to no timeout. This is required so a later explicit phase setting can disable only its phase without falling back to a positive legacy value.

- **Keep scope lifetime unchanged.** Continue to wrap the existing scan loop in `plan_tool/cli/completeness_phases.py:_collect_purity_split_findings`; do not move the scope inside the per-step loop or change completed-step, non-code-step, cache-hit, or coverage-finding behavior.

- **Preserve shell invocation behavior.** `plan_tool/shell.py:claude_invoke`, `_run_once`, timeout classification, and retry recovery must keep their current contracts. Unscoped callers must still obtain their timeout directly through `plan_tool/shell.py:_effective_subprocess_timeout` and the legacy setting.

- **Reject duplicated phase parsing.** Do not leave `os.environ` access or `_parse_timeout_seconds` imports in `plan_tool/cli/completeness_phases.py` for purity timeout resolution. The shell resolver is the single source before step 2 adds phase settings.

## Tests

### Tests for this step

- `tests/test_shell.py:test_effective_subprocess_timeout_precedence` — Update the existing scope-versus-legacy test to confirm unscoped legacy behavior remains unchanged and outer scope values are restored after nested scopes exit.

- `tests/test_shell.py:test_phase_timeout_resolver_precedence` — Assert a supplied phase setting wins, an absent phase setting falls back to the legacy setting, and an absent setting pair returns the caller’s default.

- `tests/test_shell.py:test_phase_timeout_resolver_disabled_value_masks_legacy` — Assert zero, negative, and malformed explicit phase values select no timeout even when the legacy setting is positive.

- `tests/cli/test_completeness_cmd.py:TestRunDeterministicChecks.test_purity_timeout_uses_shell_resolution` — Observe the active shell timeout inside the purity producer for the default, positive legacy override, and disabled legacy cases; use fresh cache state so read-through reuse cannot skip the observation.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Purity scans use `PURITY_CLAUDE_TIMEOUT_S` when the legacy timeout is absent or empty.

- A positive `PLAN_TOOL_CLAUDE_TIMEOUT` still replaces the purity default.

- The current zero, negative, and malformed legacy override behavior still results in no purity timeout.

- A shell timeout scope can intentionally disable timeouts without allowing `_effective_subprocess_timeout` to reapply a legacy value.

- Exiting a nested timeout scope restores the outer scope, and exiting the outer scope restores unscoped legacy behavior.

- `plan_tool/cli/completeness_phases.py` no longer owns purity timeout environment lookup or imports the shell timeout parser.

- The focused tests in `tests/test_shell.py` and `tests/cli/test_completeness_cmd.py` pass.

## References

- [Python `os.getenv`](https://docs.python.org/3/library/os.html#os.getenv) — Use for environment-variable lookup semantics and fallback behavior.

- [Python `contextvars`](https://docs.python.org/3/library/contextvars.html) — Use for token-based nested scope set and reset behavior.

- [Python `subprocess`](https://docs.python.org/3/library/subprocess.html) — Confirm the timeout value continues to reach `subprocess.run` without changing timeout handling.

- [pytest monkeypatch fixture](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use reversible environment and shell seam patches for precedence tests.

## Applicable guardrails

- **The plan’s “## Out of scope”, unrelated timeout behavior:** Limit this work to centralizing the purity lookup and scope representation; do not change retry, backend, or non-purity timeout policy.

- **The plan’s “## Out of scope”, configuration surface:** Do not add a CLI flag, persisted configuration, or named phase environment setting in this step.

- **The plan’s “## Out of scope”, purity findings:** Keep purity verdict interpretation and advisory/blocking behavior unchanged; this refactor only changes where its timeout value is selected.
