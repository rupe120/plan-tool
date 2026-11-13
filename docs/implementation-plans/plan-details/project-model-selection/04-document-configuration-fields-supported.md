# Step 4 — Document project selection and align bundled routers

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document project backend and command-model configuration in `docs/BACKENDS.md`, with shorter routes from `README.md` and `docs/reference/commands.md`. Update the bundled routers to honor explicit user requests and otherwise let project selection apply, with shared operational policy in `integrations/shared/DIRECTIVES.md`. Extend temporary-install integration coverage without changing installation code or refreshing installed skills. After implementation and the full pytest suite pass, reconcile `BACKLOG.md` #254 with the shipped explicit-command design and retain deferred work.

## Table of Contents

- [Summary](#summary) — Change and observable result.
- [Table of Contents](#table-of-contents) — Section index.
- [Why](#why) — Conflicting selection guidance.
- [Input](#input) — Dependency outputs and existing installation contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded edit footprint.
- [Implementation](#implementation) — Documentation, routers, and tracking changes.
- [Tests](#tests) — Installation coverage and document verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant source owners.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries.
- [Deferred](#deferred) — Work outside this step.

## Why

`docs/BACKENDS.md:Selecting a backend` and `docs/reference/commands.md:Global flags` describe selection without project defaults. `integrations/shared/DIRECTIVES.md:Which model to run a subcommand with` requires explicit backend and model flags on every invocation, while the Codex and Cursor routers direct sessions toward their own backend. Those instructions override the project choices this plan introduces. Existing installation tests already prove routers and shared directives install together; this step extends that coverage to the selection guidance. The heuristic heading matches identify existing documents, not implementation of this contract.

## Input

- **Steps 1–3:** Consume the configuration schema, registration-derived command normalization, effective-model selection, and CLI wiring those steps produce. Read the landed names and behavior from `plan_tool/backend_config.py`, `plan_tool/cli/parser.py`, `plan_tool/backend.py`, and `plan_tool/cli/app.py`; landed identifiers take precedence over sibling detail proposals.
- **Selection ownership:** `plan_tool/backend.py:_select_effective_backend` owns model precedence. `plan_tool/cli/app.py:main` owns invocation backend selection, using the repository identified by `plan_tool/cli/context.py:_resolve_cmd_repo_root`.
- **Installation:** `plan_tool/cli/skill_cmd.py:cmd_install_skill` installs a selected router and shared directives. Its `_classify_dest` distinguishes matching files, mode changes, and collisions; retain those semantics unchanged.
- **Existing coverage:** `tests/cli/test_skill_cmd.py:TestInstallSkill` covers temporary installations, Codex copy defaults, collisions, idempotence, and forced replacement. Its `_bundled`, `_bundled_directives`, `_dest`, and `_directives_dest` helpers provide the existing test path.
- **Proof limits:** Stubbed CLI tests prove configuration reaches backend calls. Text and installation checks prove guidance ships; they do not prove an assistant follows it or establish model quality.

## Files (creates vs edits)

- **New files:** None.
- **Existing files (edits only):**
  - `docs/BACKENDS.md` — Document fields, command keys and aliases, precedence tables, compatibility, and the Codex create/detail example.
  - `docs/reference/commands.md` — Correct global selection guidance and link to the configuration reference.
  - `README.md` — Add a short project-selection route and example or pointer.
  - `docs/design-plans/BACKEND_SELECTION.md` — Mark overlapping selection proposals as superseded and distinguish remaining proposals from shipped behavior.
  - `integrations/shared/DIRECTIVES.md` — Make project-aware invocation policy authoritative and retain guidance for unconfigured projects.
  - `integrations/claude/SKILL.md` — Align router wording with explicit requests and project selection.
  - `integrations/codex/SKILL.md` — Remove instructions that force Codex regardless of project selection.
  - `integrations/cursor/SKILL.md` — Remove instructions that force Cursor regardless of project selection.
  - `tests/cli/test_skill_cmd.py` — Extend temporary-install coverage for all bundled routers and shared selection guidance.
  - `BACKLOG.md` — Reconcile #254 after implementation and full-suite verification, preserving deferred scope.

## Implementation

- **Foundational logic: instructions preserve explicit requests and otherwise allow project selection.** Apply this rule across the operator documents, shared directives, and bundled routers. Reuse the selection implementation from steps 1–3 unchanged; do not introduce assistant-side configuration resolution.

- **Enumerate conflicting instructions before editing.** Search the declared files by identifiers such as `--backend`, `--model`, `default_backend`, and `commands`, then by wording such as “targets,” “explicitly on every,” and “per-backend, not per-subcommand.” Inspect router descriptions, introductory prose, invocation sections, examples, and backend-specific table labels as well as the obvious selection paragraphs. Repeat both searches after editing and account for legitimate surviving backend-specific guidance.

- **Make `docs/BACKENDS.md` the detailed operator reference.** Document `.plan-tool/backends.json` fields from the landed reader, including `default_backend`, backend-wide `model`, command models, and existing extra-argument fields. Explain omitted and null command-model inheritance, invalid empty or wrong-typed values, free-form model names, and unknown command-key errors. Preserve documentation of existing settings that remain supported.

- **Document the supported command vocabulary from registrations.** List canonical command keys and accepted aliases using the normalization produced by step 1 in `plan_tool/cli/parser.py`. State that selection uses the top-level invocation: `run --mode check` selects the `run` model, and `detail --reconcile` selects the `detail` model. Nested audits and applies retain that invocation’s selection; aliases identify the same canonical command.

- **Use separate precedence tables.** Document backend selection as explicit `--backend`, recognized explicit `--model` family, `PLAN_TOOL_BACKEND`, project `default_backend`, then Claude. Document model selection for the selected backend as explicit `--model`, command model, backend-wide model, manifest default, then omission so the provider CLI chooses. Project model strings must not be described as selecting a backend.

- **Explain each override independently.** `--backend` selects a backend while retaining that backend’s configured command and base-model defaults. `--model` overrides model defaults and retains its existing family-inference behavior when no explicit backend is supplied. An explicit backend switch must not inherit another backend’s model.

- **Include the Codex create/detail proof.** Show valid JSON selecting Codex with distinct configured models for `create` and `detail`, followed by invocations without selection flags. Add examples demonstrating backend-only and model overrides. Use illustrative model strings without claiming availability or quality; tie the behavior claim to step 3’s integration evidence in `tests/cli/test_app.py`. Keep normal authoring gates and commit requirements intact when presenting an ordered workflow.

- **Keep shared policy in `integrations/shared/DIRECTIVES.md`.** Replace the unconditional explicit-flags requirement under `Which model to run a subcommand with` with explicit-user-request precedence followed by project-aware invocation guidance. Retain the existing backend-specific recommendations as guidance for unconfigured projects, clearly separated from configured behavior. Do not translate recommendations into named tiers or a fixed command mapping.

- **Keep routers thin and consistent.** Update `integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`, and `integrations/cursor/SKILL.md` to direct sessions to the installed shared directives. Their host integration must not force an execution backend or model over project choices. Preserve explicit user requests, headless invocation rules, installation instructions, and provider-specific prerequisites. Adjust universal claims about which executable runs where project selection makes them inaccurate.

- **Mark proposal overlap precisely.** In `docs/design-plans/BACKEND_SELECTION.md`, mark the project-default and command-model overlap as superseded by the explicit-command configuration, with a link to `docs/BACKENDS.md`. Distinguish active `default_backend` from the tolerated inert `default`, `aspects`, and `failover` keys. Leave per-aspect routing and the proposal’s failover machinery unimplemented; preserve the distinction from existing short-rate-limit switching documented in `docs/BACKENDS.md:Rate-limit recovery`.

- **Verify installation through existing behavior.** Extend `tests/cli/test_skill_cmd.py:TestInstallSkill` using temporary destinations. Check installed router and directives contents, their relationship, and selection guidance for every integration. Preserve Codex’s `.agents` copy default and existing symlink/copy replacement rules. Do not edit `plan_tool/cli/skill_cmd.py` or touch real installed copies.

- **Reconcile tracking last.** After the implementation and full pytest suite pass, update `BACKLOG.md` #254 to reflect shipment through explicit command models rather than named strong/fast tiers. Remove stale claims that operator memory is the only available route. Preserve outstanding work, including copied-skill freshness validation, without claiming it ships here. Follow the backlog disposition rules in `docs/TRACKING.md`; authoring this detail alone does not close the entry.

## Tests

Extend `tests/cli/test_skill_cmd.py`; retain existing regression tests.

- `test_each_installed_router_ships_with_shared_project_selection_guidance` — Parameterize integrations and supported installation modes; installed files match bundled sources, the router links its adjacent directives, and both contain the required selection guidance.
- `test_installed_routers_honor_explicit_requests_and_allow_project_defaults` — Assert each installed router states the invocation rule and delegates shared policy without instructing sessions to force its host backend.
- `test_installed_directives_keep_unconfigured_guidance_without_overriding_project_defaults` — Assert shared guidance distinguishes explicit requests, configured defaults, and unconfigured recommendations.
- `test_codex_integration_defaults_to_agents_root_and_copies_because_codex_skips_symlinks` — Retain coverage of the Codex root, copied router, and copied directives.
- `test_switching_to_copy_with_force_rewrites_an_existing_correct_symlink` — Retain forced replacement coverage for both installed files.
- `test_switching_to_symlink_with_force_rewrites_an_existing_correct_copy` — Retain reverse mode-switch coverage.
- `test_collision_on_directives_only_refuses_and_leaves_skill_uninstalled` — Retain paired-install refusal behavior.

### Verification (non-code step)

This step changes documentation, bundled instructions, and integration tests, with no production-code changes. The test-authoring gate applies only to `feature` and `refactor`; the declared `non-code` classification does not require it, but the installation coverage remains an explicit deliverable.

1. Compare documented fields and precedence against the landed outputs of steps 1–3.
2. Compare the documented canonical command and alias inventory against assembled parser registrations.
3. Feed the JSON example through the real configuration reader and command validation; confirm the expected effective backend and models without invoking a provider.
4. Run `uv run pytest tests/cli/test_skill_cmd.py tests/cli/test_app.py -q` with existing backend stubs.
5. Check changed links and heading anchors; search inbound links before renaming headings.
6. Run `uv run pytest tests/ -q -n auto`. Reconcile #254 only after it passes, then verify the final tracking edit preserves deferred scope.
7. Confirm no changes to governance files, installation code, or installed copies. Check whether parser help changes elsewhere in the plan require generated CLI references; this step introduces no parser-help change itself.

## Acceptance criteria

- `docs/BACKENDS.md` documents the landed configuration fields, complete supported canonical command keys and aliases, and separate backend/model precedence tables.
- The Codex example selects distinct `create` and `detail` models without invocation selection flags and explains both override forms accurately.
- `README.md` and `docs/reference/commands.md` point readers to the same selection contract without contradictory precedence claims.
- All bundled routers honor explicit user requests and allow project selection; shared operational policy remains in `integrations/shared/DIRECTIVES.md`.
- Temporary-install tests verify the selected router and shared guidance ship together for every integration, while existing installation and replacement tests pass.
- `docs/design-plans/BACKEND_SELECTION.md` identifies superseded overlap without presenting deferred proposals as shipped.
- The full pytest suite passes before `BACKLOG.md` #254 is reconciled; the final entry disposition preserves outstanding scope, including copied-skill freshness validation.
- `plan_tool/cli/skill_cmd.py`, `CLAUDE.md`, `AGENTS.md`, and installed skill copies remain unchanged.
- Generated CLI references remain unchanged unless parser help changes.

## References

- [plan_tool/backend_config.py](plan_tool/backend_config.py) — Read the configuration owner and compatibility reader APIs.
- [plan_tool/backend.py](plan_tool/backend.py) — Read `_select_effective_backend`, `select_active_backend`, and `scoped_select_active_backend` for effective-model ownership.
- [plan_tool/cli/app.py](plan_tool/cli/app.py) — Read `main` for invocation backend selection.
- [plan_tool/cli/parser.py](plan_tool/cli/parser.py) — Read `assemble` and the landed command-normalization API for supported names and aliases.
- [plan_tool/cli/skill_cmd.py](plan_tool/cli/skill_cmd.py) — Read installation and replacement behavior without modifying it.
- [docs/BACKENDS.md](docs/BACKENDS.md) — Maintain the detailed operator selection reference.
- [integrations/shared/DIRECTIVES.md](integrations/shared/DIRECTIVES.md) — Maintain shared invocation policy.
- [docs/design-plans/BACKEND_SELECTION.md](docs/design-plans/BACKEND_SELECTION.md) — Distinguish superseded overlap from deferred proposals.
- [docs/TRACKING.md](docs/TRACKING.md) — Apply backlog disposition rules to `BACKLOG.md` #254.
- [docs/reference/documentation-style.md](docs/reference/documentation-style.md) — Structure mappings, precedence, and task routes for scanning.

## Applicable guardrails

- **The plan’s “Scope guardrails,” project selection:** Document the outputs of steps 1–3 without adding another selection owner or configuration surface.
- **The plan’s “Scope guardrails,” explicit overrides and compatibility:** Router instructions must preserve user requests and retain guidance for projects without configuration.
- **The plan’s “Scope guardrails,” validation limits:** Documentation and content tests must not introduce model-quality judgments, findings, or execution gates.
- **The plan’s “Out of scope,” routing and settings boundaries:** Supersession notes must not activate proposals left outside this effort.
- **The plan’s “Scope guardrails,” copied-skill freshness:** Temporary installation tests must not become installed-copy validation or refresh machinery.
- **The step’s protected-file boundary:** Leave governance files and installation implementation unchanged; edit bundled sources only.

## Deferred

- Copied-skill freshness validation — Preserve as follow-up tracking in `BACKLOG.md`; temporary-install assertions do not inspect existing installations.
- Refreshing installed skill copies — This step changes bundled sources and temporary test destinations only.
- Per-aspect routing and proposed failover machinery in `docs/design-plans/BACKEND_SELECTION.md` — Keep these proposals separate from explicit-command model selection and existing rate-limit recovery.
- Selection implementation and precedence changes — Steps 1–3 own these changes; this step documents and verifies their outputs.
