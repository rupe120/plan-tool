---
format_version: 1
title: Project Model Selection
intent: A repository can select its default execution backend and a model per command
  for each backend in `.plan-tool/backends.json`, so scripts and assistant sessions
  use project choices without repeating flags. Explicit invocation overrides remain
  authoritative.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/project-model-selection.md
steps:
- id: 1
  intent: Projects can declare a default backend and command models in their existing
    backend configuration file.
  files:
  - plan_tool/backend_config.py
  - plan_tool/cli/parser.py
  - tests/test_backend_config.py
  complexity: medium
  change_type: feature
  status: current
  description: Extend the existing backend configuration reader to expose optional
    default_backend and per-backend commands.<command>.model settings. Preserve load_backend_overrides
    and backend_override_for compatibility, existing model and extra-argv behavior,
    and inert default, aspects, and failover keys. Derive supported command names
    and alias normalization from the assembled CLI registrations in plan_tool/cli/parser.py;
    reject unknown command keys with the config path and supported choices, without
    importing CLI code into backend leaves. Missing or null command models inherit;
    empty or wrong-typed models and invalid default_backend values fail clearly. Add
    unmarked reader and command-normalization tests. Keep configuration read-only;
    introduce no writer, persisted state, package dependency, or environment variable.
- id: 2
  intent: Every ordinary call in an invocation uses its selected model while fallback
    recovery keeps its existing independent model selection.
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  - tests/test_shell.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides validated backend-scoped command models and command normalization.
  description: Extend the existing effective-backend selection owner with optional
    command context so model precedence is explicit model, selected backend's command
    model, selected backend's base model, manifest default, then provider omission.
    Keep commandless selection behavior unchanged and reuse build_effective_backend
    unchanged for batch and streaming arguments. Add unmarked tests for inheritance,
    explicit overrides, backend isolation, unchanged registry descriptors, and both
    argument paths. Extend existing shell and launcher recovery tests to prove their
    unchanged commandless scoped selection uses the fallback backend's base model
    and restores the primary selection after success or failure; do not add command
    routing to either recovery loop. The existing dataclass replace calls remain descriptor-only
    operations and perform no artifact replacement.
- id: 3
  intent: Scripts and assistant sessions honor project backend and model choices without
    repeating flags.
  files:
  - plan_tool/cli/app.py
  - tests/cli/test_app.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides project defaults and canonical command lookup.
    2: Provides command-aware model selection with preserved fallback semantics.
  description: Resolve the repository root before reading project selection inputs
    in main, then select the backend by explicit --backend, recognized explicit --model
    family, PLAN_TOOL_BACKEND, project default_backend, then Claude. Pass the normalized
    parsed top-level command into model selection once before dispatch; run modes
    and detail reconciliation retain their parent command, and nested audits and applies
    reuse the active selection. Preserve registration, provisional-backend synthesis,
    warnings, and preflight behavior, treating a project-selected backend like an
    environment-selected backend while keeping unconfigured read-only commands usable
    without Claude installed. Add pytest integration coverage with fake invokers for
    one project selecting Codex with distinct create and detail models, explicit overrides,
    precedence combinations, aliases, repository-root isolation, malformed configuration,
    executable availability, and nested-call consistency. Reuse the existing root
    resolver and selection owners; add no phase routing or new runtime dependencies.
- id: 4
  intent: Operators and bundled skills use one consistent project selection contract,
    and shipped work is reflected in tracking.
  files:
  - docs/BACKENDS.md
  - docs/reference/commands.md
  - README.md
  - docs/design-plans/BACKEND_SELECTION.md
  - integrations/shared/DIRECTIVES.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  - integrations/cursor/SKILL.md
  - tests/cli/test_skill_cmd.py
  - BACKLOG.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  depends_on_notes:
    3: Provides the verified invocation behavior that documentation and skill guidance
      describe.
  description: 'Document the configuration fields, supported canonical command keys
    and aliases, backend and model precedence tables, and the Codex create/detail
    proof. Explain that --backend selects the backend while retaining its configured
    model defaults, and --model overrides model defaults.
    Update all three bundled routers to honor explicit user requests and otherwise
    allow project selection, keeping shared operational policy in DIRECTIVES.md and
    guidance for unconfigured projects. Extend temporary-install integration coverage
    to verify the routers and shared guidance ship together; preserve installation
    and copied-skill replacement behavior without changing skill_cmd.py or refreshing
    installed copies. Mark overlapping portions of BACKEND_SELECTION.md as superseded
    while leaving aspect routing and failover proposals unimplemented. After the implementation
    and full pytest suite pass, reconcile BACKLOG.md #254 with the shipped explicit-command
    design and preserve deferred scope, including copied-skill freshness validation.
    Leave CLAUDE.md and AGENTS.md unchanged; regenerate CLI references only if parser
    help changes.'
---
# Project Model Selection

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

Operator documentation and all three bundled skill routers must allow project selection to take effect: explicit user backend/model requests still win, while ordinary skill-driven invocations defer to project configuration where present and retain documented guidance for unconfigured projects. Keep shared operational policy in `integrations/shared/DIRECTIVES.md`; do not edit repository governance rules in `CLAUDE.md` or `AGENTS.md`. Document configuration with examples and precedence tables: `--backend` selects the backend while retaining its configured model defaults; `--model` overrides model defaults.

## Scope guardrails

- Add only project backend defaults and per-backend, per-command model defaults. Preserve explicit invocation overrides and unconfigured behavior.
- No semantic model-quality checks, model-name allowlists, model-based findings, convergence gates, or exit-code changes.
- No phase routing, generalized configuration framework, new concurrency, or relocation of existing configuration files.
- Copied-skill freshness validation is a separate backlog effort; do not absorb it here.

## References

- `plan_tool/backend_config.py` — project override schema and tolerant sibling keys.
- `plan_tool/backend.py:_select_effective_backend`, `select_active_backend`, and `scoped_select_active_backend` — effective model/argv selection and scoped fallback seam.
- `plan_tool/cli/app.py:main` and `plan_tool/cli/context.py:_resolve_cmd_repo_root` — invocation selection and repository resolution.
- `plan_tool/cli/skill_cmd.py` — bundled integration installation, including Codex copies.
- `docs/BACKENDS.md` and `integrations/shared/DIRECTIVES.md` — operator selection policy.
- `docs/design-plans/BACKEND_SELECTION.md` — separate unimplemented aspect-routing proposal.
- `BACKLOG.md` #254 — overlapping fixed-tier proposal, not this effort's scope authority.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

General settings consolidation; changing `.plan-tool/config.json`; user-wide backend settings; command-specific backends; named model tiers; automatic model discovery/ranking; per-step or per-phase routing; new retry/failover policy; model quality enforcement; configuration writer commands or a settings UI; automatically refreshing copied skills; and unrelated backend refactors.

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
