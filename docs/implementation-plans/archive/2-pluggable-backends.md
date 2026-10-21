> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Pluggable Backends
status: completed
priority: medium
steps:
- id: 1
  title: Ship integrations/ in the wheel via hatch force-include (settle packaging
    first)
  files:
  - pyproject.toml
  complexity: low
  change_type: non-code
  detail: docs/implementation-plans/plan-details/pluggable-backends/01-ship-integrations-wheel-hatch-force.md
  status: done
- id: 2
  title: Author backend.json manifests reproducing the claude/codex literals, plus
    a new codex SKILL.md
  creates:
  - integrations/claude/backend.json
  - integrations/codex/backend.json
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: non-code
  detail: docs/implementation-plans/plan-details/pluggable-backends/02-author-backend-json-manifests.md
  status: done
- id: 3
  title: Add load_backend_from_dir + parser registry + CliBackend manifest fields,
    with a round-trip golden test
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/pluggable-backends/03-load-backend-dir-parser-registry.md
  status: done
- id: 4
  title: Add backend_config.py reader for .plan-tool/backends.json backends.<name>
    overrides (model + extra argv only)
  creates:
  - plan_tool/backend_config.py
  - tests/test_backend_config.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/pluggable-backends/04-backend-config-py-reader-plan-tool.md
  status: done
- id: 5
  title: 'Add startup discovery: importlib.resources resolver iterates integrations/*/backend.json
    and registers each over the in-code fallback seed'
  files:
  - plan_tool/backend.py
  - tests/test_backend.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/pluggable-backends/05-startup-discovery-importlib-resources.md
  status: done
- id: 6
  title: Add --model flag, model precedence, argv assembly with extra_argv, and effective-backend
    production at selection
  files:
  - plan_tool/cli/parser.py
  - plan_tool/cli/app.py
  - plan_tool/backend.py
  - tests/test_backend.py
  - tests/test_cli.py
  complexity: high
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/pluggable-backends/06-model-flag-model-precedence-argv.md
  status: done
---
# Pluggable Backends

## Overview

Turns plan-tool's backend abstraction from frozen Python literals (`plan_tool/backend.py`) into a **declarative, tunable, drop-in** surface, and gives `integrations/<backend>/` a real runtime job. Each `integrations/<backend>/` directory ships a declarative `backend.json` manifest read at startup to build a `CliBackend`; a shared per-project `.plan-tool/backends.json` (`backends.<name>` block) tunes model and extra argv per project; and a new `--model` flag enables model selection. `claude` and `codex` keep working byte-for-byte — manifests reproduce today's literals, and a missing/malformed manifest falls back to the built-in defaults. A dropped-in third backend is registered and runnable, but reachable only via `PLAN_TOOL_BACKEND`; the `--backend` flag retains `choices=("claude","codex")` (extending the flag's choices is deferred to `BACKEND_SELECTION.md`). Closes [`BACKLOG.md` #46 "Pluggable agent runtime"](../../BACKLOG.md). Scope is backend *definition* only; selection/routing/failover live in the sibling [`BACKEND_SELECTION.md`](../design-plans/BACKEND_SELECTION.md), which shares the same config file but owns its `default`, `aspects`, and `failover` keys.

## Problem statement

The backend seam (`plan_tool/backend.py`) is clean but entirely code-literal, so there is **no tuning surface**:

- argv flags are baked into functions — `_claude_streaming_argv` hardcodes `--permission-mode acceptEdits` (`backend.py:372`); codex hardcodes `_CODEX_COMMON_FLAGS` (`backend.py:413`). Changing a flag means editing source.
- there is **no model selection** anywhere — no `--model` passthrough, no way to pick `opus` vs `sonnet` or a codex model per run or per project.
- **adding a backend means editing `backend.py`** and cutting a release; there is no external registration path.
- there is **no per-project backend config** — only the process-wide `--backend` flag / `PLAN_TOOL_BACKEND` env.

Meanwhile `integrations/claude/SKILL.md` is read by **zero Python code** — it is a Claude Code skill router installed by a manual symlink (`README.md:182`). `BACKLOG.md` #46 anticipated that the runtime work pairs with the `integrations/<runtime>/` layout, but the abstraction landed as code literals and the two were never connected.

## Architecture

**Manifest schema.** Each `integrations/<backend>/backend.json` is hand-edit-friendly JSON (sorted keys, stable indent, like `jira-config.json`) declaring everything in a `CliBackend` *except* the parser body, which it references by name. Fields: `name`, `binary`, `parser`, `model_flag`, `default_model`, `batch_argv`, `streaming_argv`, and a `classification` map of regex strings (`rate_limit`, `provider_limit`, `context_overflow`, `transient`, and optional `auth`). Any `_`-prefixed key (e.g. `_comment`) is a human-facing note the loader ignores — the codex manifest carries a `_comment` recording that its four limit patterns are shared with claude's and must be edited in lockstep.

- **`parser`** is a discriminator selecting a registered parse function (`"claude"` → `_claude_parse_stream_line`, `"codex"` → `_codex_parse_stream_line`); an unknown parser is a load error listing the registered names. This is the one field that names code, not data.
- **`batch_argv` / `streaming_argv`** are the flags between binary and prompt; the loader builds the final argv as `[binary, *argv_flags, prompt]` (codex's `exec` subcommand is the first flag entry). This externalizes the hardcoded `--permission-mode acceptEdits` and `_CODEX_COMMON_FLAGS`.
- **`model_flag` / `default_model`** are NEW: when a model is set, the loader injects `[model_flag, model]` into both argvs; `null` model = omit (today's behavior).
- **`classification`** carries the four regex strings (+ optional `auth`); `null` `auth` = no distinct auth class (claude), a string = compiled and consulted (codex). Each string is a bare pattern and the loader compiles every one with `re.IGNORECASE` uniformly; the claude/codex manifests store today's patterns verbatim (no inline `(?i)`) so each manifest's `.pattern` matches the in-code literal byte-for-byte.

**Layout.** `integrations/` ships *with the package* (claude/ and codex/, each with `SKILL.md` + new `backend.json`; codex gets a new `SKILL.md`). `.plan-tool/backends.json` lives *in the driven project*, found via `_resolve_cmd_repo_root(args)` (honoring `--repo-root` / `PLAN_TOOL_REPO_ROOT` / cwd-walk), consistent with `plans.json`, `runs/`, `reviews/`, `lessons/`.

**Per-project override** (`.plan-tool/backends.json` → `backends.<name>`). Optional, additive-and-tuning-only: `model` overrides the manifest `default_model`; `extra_streaming_argv` / `extra_batch_argv` append after manifest flags, before the prompt. Deliberately narrow — no binary swap, no parser swap, no regex override from a project (tool-author concerns). `backend_config.py` reads the whole file; this design consumes only the `backends` block (the file's `default`/`aspects`/`failover` belong to `BACKEND_SELECTION.md`). A `backends.<name>` key matching no registered backend is a likely typo, so override application writes a warning to stderr (the CLI's `error()` channel, not `warnings.warn`, which is filtered in normal CLI runs) naming the unknown key and the registered backend names (sourced from `registered_names()`, not the private `_REGISTRY`) rather than silently dropping it; the `test_unknown_override_key_warns` assertion captures stderr.

**Precedence.** Model selection: `--model` flag > `.plan-tool/backends.json` `backends.<name>.model` > manifest `default_model` > omit. argv assembly: `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]`.

**Loader & registration flow** in `backend.py`:
1. `load_backend_from_dir(path) -> CliBackend` reads `backend.json`, resolves `parser` to a registered function, compiles each classification regex uniformly with `re.IGNORECASE`, and curries `batch_argv`/`streaming_argv` closures over the flag lists + model; raises a diagnostic (same spirit as `JiraConfigError`) on malformed JSON / unknown parser.
2. A parser registry `{"claude": _claude_parse_stream_line, "codex": _codex_parse_stream_line}` — the only code→manifest link; a future custom-shaped backend adds a function here.
3. Discovery at startup iterates `integrations/*/backend.json` (packaged via `importlib.resources` so it works from an installed wheel) and `register_backend`s each. The in-code literals `CLAUDE_BACKEND` / `CODEX_BACKEND` become the **fallback seed**: registered first so a broken/missing manifest still yields a working backend; a valid same-name manifest replaces it. A per-directory manifest defect (malformed JSON, unknown parser, bad regex, missing field) is caught, skipped, and **writes a warning to stderr** (the CLI's `error()` channel, not `warnings.warn`, which is filtered in normal CLI runs) naming the offending directory and the load error before falling back to the seed — same channel as the unknown-key override warning; discovery never swallows a defect silently.
4. When a backend is selected, its `.plan-tool/backends.json` `backends.<name>` block (model + extra argv) is applied to produce the effective `CliBackend`.

`registered_binaries()` is unchanged — it already iterates `_REGISTRY`, so a manifest-registered backend's binary is auto-blocked by the test-suite subprocess guard. A parallel `registered_names()` accessor is added alongside it so callers (e.g. the unknown-key override warning in `app.py`) read the registered backend names through a public accessor rather than reaching into the private `_REGISTRY`.

## References

- [importlib.resources — Python Standard Library](https://docs.python.org/3/library/importlib.resources.html) — Official API for reading package-bundled resources that works from an installed wheel, the exact mechanism the plan needs to discover integrations/*/backend.json.
- [setuptools — Data Files Support](https://setuptools.pypa.io/en/latest/userguide/datafiles.html) — How to declare non-Python files as package-data in pyproject.toml, needed to ship integrations/ inside the plan_tool package per the packaging risk.
- [json — JSON encoder and decoder (Python Standard Library)](https://docs.python.org/3/library/json.html) — Reference for json.load/loads and decode-error handling used to parse and validate the backend.json manifest and .plan-tool/backends.json.
- [re — Regular expression operations (Python Standard Library)](https://docs.python.org/3/library/re.html) — Reference for re.compile and error behavior, used to compile the manifest's classification regex strings (rate_limit, provider_limit, etc.).
- [argparse — Parser for command-line options (Python Standard Library)](https://docs.python.org/3/library/argparse.html) — Reference for adding the new --model flag and preserving --backend semantics in the CLI parser layer.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — Official flag list (--permission-mode, --model, stream-json output) that the claude backend.json manifest must reproduce byte-for-byte.
- [OpenAI Codex CLI (GitHub)](https://github.com/openai/codex) — Source of truth for the codex exec subcommand, --json output schema, and model flag that the codex manifest and CODEX_CLI_CONTRACT.md are pinned to.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Stream parser stays in code** — NDJSON event-shape mapping (`_claude_parse_stream_line`, `_codex_parse_stream_line`) is logic, not data; a manifest selects one by name, it does not describe the parse.
- **No prompt-per-backend system** — `prompts/*.md` stay backend-agnostic; a separate future item if a backend ever needs different phrasing.
- **No change to the exit-code convention, gates, or orchestrators.**
- **Selection and failover** — which backend runs which aspect, and quota-limit failover, are owned by [`BACKEND_SELECTION.md`](../design-plans/BACKEND_SELECTION.md).
- **Per-project binary swap, parser swap, and regex override** — deliberately excluded from the override surface; these are tool-author concerns handled by editing the manifest, not per-repo tuning.

## Risks

- **Packaging of `integrations/`** — it currently lives at repo-root, *outside* the `plan_tool/` package, so discovery may not work from `uv tool install` / an installed wheel. It likely needs to move under `plan_tool/integrations/` or be declared as package-data. This is the one structural decision that affects packaging and should be settled first (mitigation: confirm `pyproject.toml` package-data / `importlib.resources` access before building the loader).
- **Lossy externalization** — a manifest that does not reproduce today's literals would silently change behavior; mitigated by a golden round-trip test asserting `load_backend_from_dir("integrations/claude")` equals `CLAUDE_BACKEND` (and same for codex).
- **Malformed/missing manifest** — could break startup discovery; mitigated by registering the in-code `CLAUDE_BACKEND` / `CODEX_BACKEND` literals first as a fallback seed so a broken manifest still yields a working backend.
- **Manifest loader hermeticity** — a new real-filesystem read could leak host state into tests; mitigated by pointing discovery at a `tmp_path` integrations dir.
- **Codex limit patterns silently diverging from claude's** — in code `CODEX_BACKEND` aliases claude's compiled `rate_limit`/`provider_limit`/`context_overflow`/`transient` objects by reference, so step 2's self-contained manifests duplicate those regex strings into `integrations/codex/backend.json`; a later edit to claude's manifest no longer propagates. Mitigated by a test asserting the codex manifest's `rate_limit`/`provider_limit`/`context_overflow`/`transient` patterns equal claude's, and a `_comment` string key in `integrations/codex/backend.json` (loader ignores `_`-prefixed keys) recording that the four limit patterns are intentionally shared with claude's manifest and must be edited in lockstep.

## Testing

Per `TESTING.md`'s unit-first convention; keep the invoker-neutralization table current (the seam doesn't move, but the manifest loader is a new real-filesystem read to keep hermetic — point discovery at a `tmp_path` integrations dir).

- **Round-trip golden** — manifest → `CliBackend` equals the in-code literal (proves no behavior change on day one); pin against `docs/CODEX_CLI_CONTRACT.md` as the codex argv source of truth.
- **Loader unit tests** — malformed JSON, unknown `parser`, missing required field, `null` vs string `auth` → typed errors carrying the registered-names list.
- **Precedence tests** — `--model` flag > project-file > manifest default; argv assembly order with `extra_*_argv` + model pair.
- **Discovery test** — a temp `integrations/<fake>/backend.json` registers and is blockable by the conftest subprocess guard (no real spawn).
- **Override scoping** — the `backends.<name>` block cannot swap binary/parser (those keys ignored or rejected), only tune model/argv.

Existing suites must still pass, and the codex fixtures under `tests/fixtures/codex/` stay pinned to `docs/CODEX_CLI_CONTRACT.md`.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 2 (non-code) — verification appropriate to the artifacts; no test-ordering directive.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (feature) — unit tests added with the implementation; green before completion.
- step 6 (feature) — unit tests added with the implementation; green before completion.

## Acceptance criteria

- `load_backend_from_dir("integrations/claude")` returns a `CliBackend` equal to the in-code `CLAUDE_BACKEND` literal; `load_backend_from_dir("integrations/codex")` equals `CODEX_BACKEND`.
- A `backend.json` with malformed JSON, an unknown `parser`, or a missing required field raises a typed load error whose message lists the registered parser names.
- Dropping in `integrations/<new>/backend.json` that reuses a registered parser registers a usable backend with no edit to `backend.py`.
- With no manifest present, `CLAUDE_BACKEND` / `CODEX_BACKEND` literals serve exactly as today; with no `.plan-tool/backends.json`, selection/model behavior is identical to today.
- Model resolution follows `--model` flag > `.plan-tool/backends.json` `backends.<name>.model` > manifest `default_model` > omit; a `null` effective model omits the `model_flag` from the argv.
- Final argv is assembled as `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]`.
- `--backend` / `PLAN_TOOL_BACKEND` semantics and precedence are preserved.
- `registered_binaries()` includes a manifest-registered backend's binary (so the conftest subprocess guard blocks it) with no source edit.
- A `backends.<name>` override block cannot change the backend's binary or parser; only `model` and `extra_*_argv` take effect.
- A `backends.<name>` key matching no registered backend writes a warning to stderr (the CLI's `error()` channel, not `warnings.warn`) naming the unknown key and the registered backend names, rather than being silently ignored.
- A malformed/unloadable `backend.json` encountered during startup discovery writes a warning to stderr (the CLI's `error()` channel, not `warnings.warn`) naming the offending directory and the load error, then falls back to the seed, rather than being silently skipped.

## Deferred

- **`.plan-tool/backends.json` config wizard** (a `backends config` analog to `jira config`) — hand-edit-only for v1; add a wizard if friction shows (the selection doc proposes `plan-tool backends` subcommands that could host it).
- **Config format choice (JSON vs TOML)** — recommended JSON for consistency with the other `.plan-tool/` files and `jira-config.json`; left as an open question to confirm before implementation.
- **Doc updates on landing** — `README.md` (`## Backends`, `## Current code layout` tree), `RUNBOOK.md` (`## Backends` recipe + `--model` / `.plan-tool/backends.json` quick-reference), `integrations/claude/SKILL.md` + new `integrations/codex/SKILL.md` (`argument-hint` gains `--model`), and `docs/CODEX_CLI_CONTRACT.md` (note the codex manifest is generated from / pinned to the contract). `PLAN_FORMAT.md` needs no change.
