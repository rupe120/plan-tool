> **Replaced**: this file has been superseded by `implementation-plans/2-pluggable-backends.md`.
> Preserved here for history; do not edit.

## Overview

Turns plan-tool's backend abstraction from frozen Python literals (`plan_tool/backend.py`) into a **declarative, tunable, drop-in** surface, and gives `integrations/<backend>/` a real runtime job. Each `integrations/<backend>/` directory ships a declarative `backend.json` manifest read at startup to build a `CliBackend`; a shared per-project `.plan-tool/backends.json` (`backends.<name>` block) tunes model and extra argv per project; and a new `--model` flag enables model selection. `claude` and `codex` keep working byte-for-byte — manifests reproduce today's literals, and a missing/malformed manifest falls back to the built-in defaults. Closes [`BACKLOG.md` #46 "Pluggable agent runtime"](../../BACKLOG.md). Scope is backend *definition* only; selection/routing/failover live in the sibling [`BACKEND_SELECTION.md`](BACKEND_SELECTION.md), which shares the same config file but owns its `default`, `aspects`, and `failover` keys.

## Problem statement

The backend seam (`plan_tool/backend.py`) is clean but entirely code-literal, so there is **no tuning surface**:

- argv flags are baked into functions — `_claude_streaming_argv` hardcodes `--permission-mode acceptEdits` (`backend.py:372`); codex hardcodes `_CODEX_COMMON_FLAGS` (`backend.py:413`). Changing a flag means editing source.
- there is **no model selection** anywhere — no `--model` passthrough, no way to pick `opus` vs `sonnet` or a codex model per run or per project.
- **adding a backend means editing `backend.py`** and cutting a release; there is no external registration path.
- there is **no per-project backend config** — only the process-wide `--backend` flag / `PLAN_TOOL_BACKEND` env.

Meanwhile `integrations/claude/SKILL.md` is read by **zero Python code** — it is a Claude Code skill router installed by a manual symlink (`README.md:182`). `BACKLOG.md` #46 anticipated that the runtime work pairs with the `integrations/<runtime>/` layout, but the abstraction landed as code literals and the two were never connected.

## Architecture

**Manifest schema.** Each `integrations/<backend>/backend.json` is hand-edit-friendly JSON (sorted keys, stable indent, like `jira-config.json`) declaring everything in a `CliBackend` *except* the parser body, which it references by name. Fields: `name`, `binary`, `parser`, `model_flag`, `default_model`, `batch_argv`, `streaming_argv`, and a `classification` map of regex strings (`rate_limit`, `provider_limit`, `context_overflow`, `transient`, and optional `auth`).

- **`parser`** is a discriminator selecting a registered parse function (`"claude"` → `_claude_parse_stream_line`, `"codex"` → `_codex_parse_stream_line`); an unknown parser is a load error listing the registered names. This is the one field that names code, not data.
- **`batch_argv` / `streaming_argv`** are the flags between binary and prompt; the loader builds the final argv as `[binary, *argv_flags, prompt]` (codex's `exec` subcommand is the first flag entry). This externalizes the hardcoded `--permission-mode acceptEdits` and `_CODEX_COMMON_FLAGS`.
- **`model_flag` / `default_model`** are NEW: when a model is set, the loader injects `[model_flag, model]` into both argvs; `null` model = omit (today's behavior).
- **`classification`** carries the four regex strings (+ optional `auth`); `null` `auth` = no distinct auth class (claude), a string = compiled and consulted (codex).

**Layout.** `integrations/` ships *with the package* (claude/ and codex/, each with `SKILL.md` + new `backend.json`; codex gets a new `SKILL.md`). `.plan-tool/backends.json` lives *in the driven project*, found via `locator.find_repo_root_from_cwd`, consistent with `plans.json`, `runs/`, `reviews/`, `lessons/`.

**Per-project override** (`.plan-tool/backends.json` → `backends.<name>`). Optional, additive-and-tuning-only: `model` overrides the manifest `default_model`; `extra_streaming_argv` / `extra_batch_argv` append after manifest flags, before the prompt. Deliberately narrow — no binary swap, no parser swap, no regex override from a project (tool-author concerns). `backend_config.py` reads the whole file; this design consumes only the `backends` block (the file's `default`/`aspects`/`failover` belong to `BACKEND_SELECTION.md`).

**Precedence.** Model selection: `--model` flag > `.plan-tool/backends.json` `backends.<name>.model` > manifest `default_model` > omit. argv assembly: `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]`.

**Loader & registration flow** in `backend.py`:
1. `load_backend_from_dir(path) -> CliBackend` reads `backend.json`, resolves `parser` to a registered function, compiles regexes, and curries `batch_argv`/`streaming_argv` closures over the flag lists + model; raises a diagnostic (same spirit as `JiraConfigError`) on malformed JSON / unknown parser.
2. A parser registry `{"claude": _claude_parse_stream_line, "codex": _codex_parse_stream_line}` — the only code→manifest link; a future custom-shaped backend adds a function here.
3. Discovery at startup iterates `integrations/*/backend.json` (packaged via `importlib.resources` so it works from an installed wheel) and `register_backend`s each. The in-code literals `CLAUDE_BACKEND` / `CODEX_BACKEND` become the **fallback seed**: registered first so a broken/missing manifest still yields a working backend; a valid same-name manifest replaces it.
4. When a backend is selected, its `.plan-tool/backends.json` `backends.<name>` block (model + extra argv) is applied to produce the effective `CliBackend`.

`registered_binaries()` is unchanged — it already iterates `_REGISTRY`, so a manifest-registered backend's binary is auto-blocked by the test-suite subprocess guard.

## Out of scope

- **Stream parser stays in code** — NDJSON event-shape mapping (`_claude_parse_stream_line`, `_codex_parse_stream_line`) is logic, not data; a manifest selects one by name, it does not describe the parse.
- **No prompt-per-backend system** — `prompts/*.md` stay backend-agnostic; a separate future item if a backend ever needs different phrasing.
- **No change to the exit-code convention, gates, or orchestrators.**
- **Selection and failover** — which backend runs which aspect, and quota-limit failover, are owned by [`BACKEND_SELECTION.md`](BACKEND_SELECTION.md).
- **Per-project binary swap, parser swap, and regex override** — deliberately excluded from the override surface; these are tool-author concerns handled by editing the manifest, not per-repo tuning.

## Risks

- **Packaging of `integrations/`** — it currently lives at repo-root, *outside* the `plan_tool/` package, so discovery may not work from `uv tool install` / an installed wheel. It likely needs to move under `plan_tool/integrations/` or be declared as package-data. This is the one structural decision that affects packaging and should be settled first (mitigation: confirm `pyproject.toml` package-data / `importlib.resources` access before building the loader).
- **Lossy externalization** — a manifest that does not reproduce today's literals would silently change behavior; mitigated by a golden round-trip test asserting `load_backend_from_dir("integrations/claude")` equals `CLAUDE_BACKEND` (and same for codex).
- **Malformed/missing manifest** — could break startup discovery; mitigated by registering the in-code `CLAUDE_BACKEND` / `CODEX_BACKEND` literals first as a fallback seed so a broken manifest still yields a working backend.
- **Manifest loader hermeticity** — a new real-filesystem read could leak host state into tests; mitigated by pointing discovery at a `tmp_path` integrations dir.

## Testing

Per `TESTING.md`'s unit-first convention; keep the invoker-neutralization table current (the seam doesn't move, but the manifest loader is a new real-filesystem read to keep hermetic — point discovery at a `tmp_path` integrations dir).

- **Round-trip golden** — manifest → `CliBackend` equals the in-code literal (proves no behavior change on day one); pin against `docs/CODEX_CLI_CONTRACT.md` as the codex argv source of truth.
- **Loader unit tests** — malformed JSON, unknown `parser`, missing required field, `null` vs string `auth` → typed errors carrying the registered-names list.
- **Precedence tests** — `--model` flag > project-file > manifest default; argv assembly order with `extra_*_argv` + model pair.
- **Discovery test** — a temp `integrations/<fake>/backend.json` registers and is blockable by the conftest subprocess guard (no real spawn).
- **Override scoping** — the `backends.<name>` block cannot swap binary/parser (those keys ignored or rejected), only tune model/argv.

Existing suites must still pass, and the codex fixtures under `tests/fixtures/codex/` stay pinned to `docs/CODEX_CLI_CONTRACT.md`.

## Acceptance criteria

- `load_backend_from_dir("integrations/claude")` returns a `CliBackend` equal to the in-code `CLAUDE_BACKEND` literal; `load_backend_from_dir("integrations/codex")` equals `CODEX_BACKEND`.
- A `backend.json` with malformed JSON, an unknown `parser`, or a missing required field raises a typed load error whose message lists the registered parser names.
- Dropping in `integrations/<new>/backend.json` registers a usable backend with no edit to `backend.py`.
- With no manifest present, `CLAUDE_BACKEND` / `CODEX_BACKEND` literals serve exactly as today; with no `.plan-tool/backends.json`, selection/model behavior is identical to today.
- Model resolution follows `--model` flag > `.plan-tool/backends.json` `backends.<name>.model` > manifest `default_model` > omit; a `null` effective model omits the `model_flag` from the argv.
- Final argv is assembled as `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]`.
- `--backend` / `PLAN_TOOL_BACKEND` semantics and precedence are preserved.
- `registered_binaries()` includes a manifest-registered backend's binary (so the conftest subprocess guard blocks it) with no source edit.
- A `backends.<name>` override block cannot change the backend's binary or parser; only `model` and `extra_*_argv` take effect.

## Deferred

- **`.plan-tool/backends.json` config wizard** (a `backends config` analog to `jira config`) — hand-edit-only for v1; add a wizard if friction shows (the selection doc proposes `plan-tool backends` subcommands that could host it).
- **Config format choice (JSON vs TOML)** — recommended JSON for consistency with the other `.plan-tool/` files and `jira-config.json`; left as an open question to confirm before implementation.
- **Doc updates on landing** — `README.md` (`## Backends`, `## Current code layout` tree), `RUNBOOK.md` (`## Backends` recipe + `--model` / `.plan-tool/backends.json` quick-reference), `integrations/claude/SKILL.md` + new `integrations/codex/SKILL.md` (`argument-hint` gains `--model`), and `docs/CODEX_CLI_CONTRACT.md` (note the codex manifest is generated from / pinned to the contract). `PLAN_FORMAT.md` needs no change.
