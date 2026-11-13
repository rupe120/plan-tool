# Project backend defaults and command-specific models

## Outcome

A repository can select its default execution backend and a model per command for each backend in `.plan-tool/backends.json`, so scripts and assistant sessions use project choices without repeating flags. Explicit invocation overrides remain authoritative.

## Overview

Extend the existing backend configuration and invocation-level selection. The first proof is one project selecting Codex by default, using one configured model for `create` and another for `detail`, while `--backend` and `--model` still override it.

## Problem statement

`plan_tool/backend_config.py:BackendOverride` supports one model per backend and extra batch/streaming arguments. `plan_tool/cli/app.py:main` selects the backend before dispatch from flags, recognized explicit model family, environment, then Claude. Neither path selects a project backend default or a command-specific model. These are code-grounded limits, rather than a need for a general settings framework.

## Architecture

Keep `.plan-tool/backends.json` as the backend configuration owner. Add optional `default_backend` and optional `backends.<name>.commands.<command>.model`. Models remain free-form backend-specific strings; do not infer quality tiers or bake vendor model names into code. A command override belongs to its backend, preventing an explicit backend switch from inheriting another provider's model.

Backend precedence is explicit `--backend`, recognized explicit `--model` family, `PLAN_TOOL_BACKEND`, project `default_backend`, then Claude. Project model strings do not infer or change the selected backend. Model precedence for that backend is explicit `--model`, its command-specific model, its existing `model`, manifest default, then omission so the provider CLI chooses. Missing or null command model inherits; empty or wrong-typed values are configuration errors. `default_backend` is optional but must be a non-empty string when present.

Use the parsed top-level command as the selection unit, with accepted aliases normalized to their canonical command. All calls within that invocation share its selected model, including nested audits and applies. `run --mode check` uses `run`; `detail --reconcile` uses `detail`. Do not introduce phase, step, or task-family selection. Derive and document the supported command-key set from the existing CLI; reject unknown command keys with an actionable configuration error. Existing commandless backend selection APIs retain their current behavior.

Resolve project inputs against the command's resolved repository root before selecting and activating the backend. Preserve existing backend registration, provisional-backend support, effective argv construction, and preflight semantics except that an explicitly configured project backend receives the same executable-availability treatment as an environment-selected backend. Read-only commands must retain their current ability to operate without an installed default Claude binary. Preserve the existing rate-limit switch contract: the fallback selects its own per-backend base model, without borrowing the primary backend's explicit or command-specific model, and restores the primary selection afterward.

The new keys are opt-in. Existing files without them preserve behavior, including the inert `default`, `aspects`, and `failover` keys tolerated by the current reader. Use `default_backend` rather than activating the older design's `default` key. Update the older backend-selection design's scope/status where needed to avoid contradictory ownership, without implementing its phase routing or failover proposals.

Operator documentation and all three bundled skill routers must allow project selection to take effect: explicit user backend/model requests still win, while ordinary skill-driven invocations defer to project configuration where present and retain documented guidance for unconfigured projects. Keep shared operational policy in `integrations/shared/DIRECTIVES.md`; do not edit repository governance rules in `CLAUDE.md` or `AGENTS.md`. Document configuration with examples and precedence tables, including the fact that explicit flags bypass configured model defaults.

## In scope

The project backend reader, invocation-level backend/model resolution, supported command normalization, selection tests, operator documentation, and bundled skill guidance needed to honor project choices. Related backlog #254 proposes a fixed strong/fast tier mapping; this user-requested design uses explicit command models instead. Reconcile that overlapping entry only when this work ships, preserving any deferred scope. This is a user-directed effort, not an execution of #254's narrower scope contract.

## Out of scope

General settings consolidation; changing `.plan-tool/config.json`; user-wide backend settings; command-specific backends; named model tiers; automatic model discovery/ranking; per-step or per-phase routing; new retry/failover policy; model quality enforcement; configuration writer commands or a settings UI; automatically refreshing copied skills; and unrelated backend refactors.

## Scope guardrails

- Add only project backend defaults and per-backend, per-command model defaults. Preserve explicit invocation overrides and unconfigured behavior.
- No semantic model-quality checks, model-name allowlists, model-based findings, convergence gates, or exit-code changes.
- No phase routing, generalized configuration framework, new concurrency, or relocation of existing configuration files.
- Copied-skill freshness validation is a separate backlog effort; do not absorb it here.

## Allowed behavior changes

Only the new opt-in backend/model selection, errors for malformed newly supported fields, and skill guidance that honors those settings. Existing backend tuning and rate-limit behavior remain supported.

## Allowed reorganization

None beyond the smallest shared configuration/selection helper needed to keep CLI wiring thin and backend leaves cycle-free.

## Risks

Precedence errors can send a model to the wrong provider; stale skill instructions can override the project; alias handling can silently miss configuration; and activating a previously inert key can change existing projects. The architecture's backend-scoped command models, explicit precedence, guidance updates, and new key address these risks without phase routing.

## Testing

Use hermetic config-reader and selection tests plus CLI integration tests with fake invokers. Verify the precedence combinations, absent/null inheritance and malformed fields, alias selection, repository-root isolation, both batch and streaming argv, nested-call consistency, and fallback restoration. Existing tests that pin the legacy behavior remain the compatibility evidence. Run the full pytest suite before shipment and regenerate generated CLI references only if parser/help text changes. Review the seed before create, audit the bare plan before detail, then audit the complete detail bundle; keep the plan at contract altitude and put fixtures and implementation choices in detail.

## Acceptance criteria

- The first proof selects the project backend and distinct `create`/`detail` models without explicit flags, with explicit overrides and all documented precedence combinations verified.
- Existing project files retain selection and argv behavior; project isolation, aliases, nested calls, and fallback behavior meet the architecture contract.
- Skill-driven ordinary invocations can honor project choices, and the documentation presents one consistent configuration contract.
- The final implementation step reconciles backlog #254 only after full shipment; authoring alone does not remove it. The separate copied-skill validation effort remains separate.

## Deferred

Other project settings and copied-skill freshness validation remain independent work. File out-of-scope defects in `BUG_BACKLOG.md` and forward-looking work in `BACKLOG.md`; do not broaden this plan to absorb them.

## References

- `plan_tool/backend_config.py` — project override schema and tolerant sibling keys.
- `plan_tool/backend.py:_select_effective_backend`, `select_active_backend`, and `scoped_select_active_backend` — effective model/argv selection and scoped fallback seam.
- `plan_tool/cli/app.py:main` and `plan_tool/cli/context.py:_resolve_cmd_repo_root` — invocation selection and repository resolution.
- `plan_tool/cli/skill_cmd.py` — bundled integration installation, including Codex copies.
- `docs/BACKENDS.md` and `integrations/shared/DIRECTIVES.md` — operator selection policy.
- `docs/design-plans/BACKEND_SELECTION.md` — separate unimplemented aspect-routing proposal.
- `BACKLOG.md` #254 — overlapping fixed-tier proposal, not this effort's scope authority.
