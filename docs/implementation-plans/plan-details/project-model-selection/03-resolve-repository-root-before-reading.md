# Step 3 — Honor project selection at CLI entry

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Read validated project configuration at invocation entry. Choose the backend, look up its command model, and activate the existing selector once before dispatch.

## Table of Contents

- [Why](#why) — Purpose.
- [Files](#files) — Edit footprint.
- [Implementation](#implementation) — Smallest delivery path.
- [Tests](#tests) — Evidence.
- [Acceptance criteria](#acceptance-criteria) — Completion checks.

## Why

CLI entry already owns backend precedence and repository resolution. Connecting these owners enables project defaults without routing inside orchestrators.

## Files

Edit `plan_tool/cli/app.py` and `tests/cli/test_app.py`; extend existing selection tests in `tests/cli/test_package_surface.py` where they own the compatibility assertion. Create no files.

## Implementation

In `main`, resolve the repository root with `_resolve_cmd_repo_root` before reading project settings. Derive the command map from the assembled parser and use step 1's expanded reader to validate and normalize the configuration. Keep these reads inside the existing configuration-error boundary.

Choose the backend by explicit `--backend`, recognized explicit `--model` family, nonempty `PLAN_TOOL_BACKEND`, project `default_backend`, then Claude. Infer a backend only from an explicit model. After backend selection, look up that backend's model for the normalized top-level command in the validated configuration. Pass that value as `command_model` and preserve `args.model` as the explicit model input to `select_active_backend`. This is the complete handoff; the backend selector needs no command map. Reuse the resolved repository root for all configuration reads.

Keep parsed dispatch/locking behavior unchanged. Parent commands own modes and nested calls: `run --mode check` uses `run`, `detail --reconcile` uses `detail`, and internal audits/applies reuse the active descriptor. Do not add selection to downstream handlers.

Preserve provisional synthesis, warning behavior, and executable-failure codes. Supply the available explicit-or-command project model when deciding whether provisional synthesis needs catalog default discovery; do not let discovery displace a configured model. Project backend selection gets environment-equivalent executable preflight, including explicit Claude selection. Preserve implicit and model-only Claude exemptions. Diagnostics must account for a project default when suggesting overrides or explaining model inference. Malformed configuration returns the existing code 2 before dispatch.

## Tests

Use integration tests through `main` with real configuration/selection and fake invokers. Extend existing fixtures rather than duplicating them.

| Property | Evidence |
| --- | --- |
| End-to-end outcome | one project, Codex default, distinct `create`/`detail` models, no selection flags |
| Precedence | conflicting sources; explicit backend retains its own model defaults; explicit model wins; recognized and opaque model names |
| Command identity | real alias, run mode, detail reconciliation, one nested audit/apply path with conflicting nested defaults |
| Project isolation | resolver flag/env/ancestor routes and sequential invocations for two repositories |
| Compatibility | malformed fields, project/environment executable checks, implicit/model-only Claude exemptions, provisional backend and warnings |

Stub catalog access and keep the real-backend guard enabled. Run the affected CLI tests and full suite. Break the project-selection branch temporarily to confirm the end-to-end assertion detects its absence.

## Acceptance criteria

- The CLI resolves and validates project settings before backend activation.
- Backend precedence and selected-backend command-model lookup match the plan.
- The validated model value reaches step 2's selector; CLI registries stay above backend leaves.
- Aliases, modes, nested calls, repository isolation, errors, and executable checks have passing evidence.
- Affected and full tests pass without provider calls or network access.
