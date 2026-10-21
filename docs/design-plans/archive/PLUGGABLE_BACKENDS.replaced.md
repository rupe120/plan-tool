> **Replaced**: this file has been superseded by `implementation-plans/2-pluggable-backends.md`.
> Preserved here for history; do not edit.

# Pluggable, tunable CLI backends

Design for turning plan-tool's backend abstraction from frozen Python
literals into a **declarative, tunable, drop-in** surface — and for giving
the `integrations/<backend>/` folder a real job in the runtime logic instead
of being a static skill asset. Closes [`BACKLOG.md` #46 "Pluggable agent
runtime"](../../BACKLOG.md).

Status: **design** (no code yet). Author: research pass, 2026-06-10.

> **Scope split.** This doc covers backend *definition* — what a backend is
> and how it's declared/tuned. Its sibling
> [`BACKEND_SELECTION.md`](BACKEND_SELECTION.md) covers backend
> *selection/routing* — which backend runs which aspect of processing, and
> failover when one hits a quota limit. They share **one** per-project config
> file, `.plan-tool/backends.json`: this doc owns its `backends.<name>` block
> (per-backend model/flag overrides); the selection doc owns `default`,
> `aspects`, and `failover`.

## Why

The backend seam (`plan_tool/backend.py`) is clean but entirely code-literal,
so there is **no tuning surface**:

- argv flags are baked into functions — `_claude_streaming_argv` hardcodes
  `--permission-mode acceptEdits` (`backend.py:372`); codex hardcodes
  `_CODEX_COMMON_FLAGS` (`backend.py:413`). Changing a flag means editing
  source.
- there is **no model selection** anywhere — no `--model` passthrough, no way
  to pick `opus` vs `sonnet` or a codex model per run or per project.
- **adding a backend means editing `backend.py`** and cutting a release; there
  is no external registration path.
- there is **no per-project backend config** — only the process-wide
  `--backend` flag / `PLAN_TOOL_BACKEND` env.

Meanwhile `integrations/claude/SKILL.md` is read by **zero Python code** — it
is a Claude Code skill router installed by a manual symlink (`README.md:182`).
`BACKLOG.md` #46 already anticipated that the runtime work "naturally pairs
with the `integrations/<runtime>/` layout — each runtime gets its own
skill/agent manifest there." The folder was meant to become the per-backend
home; the abstraction landed as code literals instead and the two were never
connected. This design connects them.

## Goals / non-goals

**Goals**

- Each `integrations/<backend>/` directory **declares** its backend: binary,
  argv flags (batch + streaming), default model, and failure-classification
  regexes — read at startup to build a `CliBackend`.
- The shared per-project `.plan-tool/backends.json` **overrides** a backend's
  settings per project (model, extra flags) via its `backends.<name>` block,
  mirroring the existing per-project `.plan-tool/` convention.
- Dropping in `integrations/<new>/` registers a usable backend with **no
  source edit**.
- `claude` and `codex` keep working byte-for-byte: the manifests reproduce
  today's literals, and a missing/malformed manifest falls back to the
  built-in defaults.

**Non-goals**

- The **stream parser stays in code.** NDJSON event-shape mapping is logic,
  not data (`_claude_parse_stream_line`, `_codex_parse_stream_line`); a
  manifest selects one by name, it does not describe the parse.
- No new prompt-per-backend system. `prompts/*.md` stay backend-agnostic; that
  is a separate future item if a backend ever needs different phrasing.
- No change to the exit-code convention, gates, or orchestrators.
- **Selection and failover are out of scope here** — see
  [`BACKEND_SELECTION.md`](BACKEND_SELECTION.md).

## Layout

```
integrations/
  claude/
    SKILL.md       agent-facing skill router (unchanged role)
    backend.json   NEW: declarative CliBackend manifest
  codex/
    SKILL.md       NEW: codex skill router (closes BACKLOG #46's "future integrations/codex/…")
    backend.json   NEW
<repo-root>/.plan-tool/
  plans.json       existing
  backends.json    NEW (optional): shared per-project backend config —
                   this doc reads its `backends.<name>` block;
                   BACKEND_SELECTION.md reads `default` / `aspects` / `failover`
```

`integrations/` ships *with the package* (it is the tool's own source of
backend descriptors). `.plan-tool/backends.json` lives *in the driven project*
and is created/edited there — consistent with `plans.json`, `runs/`,
`reviews/`, `lessons/`.

## `integrations/<backend>/backend.json` schema

A backend manifest is hand-edit-friendly JSON (sorted keys, stable indent,
like `jira-config.json`). It declares everything in a `CliBackend` *except*
the parser body, which it references by name.

```json
{
  "name": "claude",
  "binary": "claude",
  "parser": "claude",
  "model_flag": "--model",
  "default_model": null,
  "batch_argv":     ["-p", "--permission-mode", "acceptEdits"],
  "streaming_argv": ["-p", "--output-format", "stream-json", "--verbose",
                     "--permission-mode", "acceptEdits"],
  "classification": {
    "rate_limit":       "(rate[- ]?limit|too many requests|usage limit|try again at|Retry-After)",
    "provider_limit":   "You've hit your limit",
    "context_overflow": "(prompt is too long|input too long|too many tokens|…)",
    "transient":        "(timed out|timeout|ECONNRESET|…|\\b429\\b)",
    "auth":             null
  }
}
```

Field notes:

- **`parser`** — discriminator selecting a registered parse function
  (`"claude"` → `_claude_parse_stream_line`, `"codex"` →
  `_codex_parse_stream_line`). A manifest naming an unknown parser is a load
  error listing the registered names. This is the one field that *cannot* be
  pure data — it names code.
- **`batch_argv` / `streaming_argv`** — the flags between the binary and the
  prompt. The loader builds the final argv as
  `[binary, *argv_flags, prompt]` (codex's `exec` subcommand is the first
  entry of its flag list). This externalizes today's hardcoded
  `--permission-mode acceptEdits` and `_CODEX_COMMON_FLAGS`.
- **`model_flag` / `default_model`** — NEW capability. When `default_model`
  (or a `--model` / per-project override) is set, the loader injects
  `[model_flag, model]` into both argvs. `null` model = omit (today's
  behavior). This is the smallest addition that unlocks model selection
  without bespoke per-backend code.
- **`classification`** — the four regex strings (+ optional `auth`). codex's
  three shared patterns are identical strings to claude's today; keeping them
  per-manifest is explicit and lets a backend diverge without code. `null`
  `auth` = no distinct auth class (claude); a string = compiled and consulted
  (codex).

## Per-project override: `.plan-tool/backends.json` → `backends.<name>`

Optional. The shared per-project config file is loaded like `plans.json`
(`<repo-root>/.plan-tool/backends.json`, found via
`locator.find_repo_root_from_cwd`). This doc owns the `backends` block, a map
of backend name → per-project tuning of that backend's manifest defaults:

```json
{
  "backends": {
    "codex": {
      "model": "gpt-5-codex",
      "extra_streaming_argv": ["--reasoning", "high"],
      "extra_batch_argv": []
    }
  }
}
```

(The same file's `default`, `aspects`, and `failover` keys are owned by
[`BACKEND_SELECTION.md`](BACKEND_SELECTION.md); `backend_config.py` reads the
whole file and each design consumes its own keys.)

- **`model`** — overrides the manifest `default_model` for this project.
- **`extra_*_argv`** — appended after the manifest flags, before the prompt.
  Additive only (a project tunes, it does not rewrite the base contract). A
  project that needs to *remove* a base flag is a signal the base manifest is
  wrong — handle by editing the manifest, not the override.

Deliberately narrow: no binary swap, no parser swap, no regex override from a
project (those are tool-author concerns, not per-repo tuning). Keeping the
override additive-and-tuning-only stops per-project quirks from forking the
backend contract.

## Precedence

**Model selection** (for a chosen backend):

```
--model flag (new)  >  .plan-tool/backends.json backends.<name>.model  >  manifest default_model  >  omit
```

**argv assembly** for a call:

```
[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]
```

(Which *backend* is chosen — the `--backend` / env / `default` / per-aspect
precedence — is defined in [`BACKEND_SELECTION.md`](BACKEND_SELECTION.md).)

## Loader & registration flow

`backend.py` gains a manifest loader and discovers backends at import/startup:

1. **`load_backend_from_dir(path) -> CliBackend`** — reads `backend.json`,
   resolves `parser` to a registered parse function, compiles the regexes,
   and curries `batch_argv`/`streaming_argv` closures over the flag lists +
   model. Raises a diagnostic on malformed JSON / unknown parser (same spirit
   as `JiraConfigError`).
2. **A parser registry** — `{"claude": _claude_parse_stream_line, "codex":
   _codex_parse_stream_line}`, the only code→manifest link. A future
   custom-shaped backend adds a parser function here (the irreducible code
   cost) and a manifest references it.
3. **Discovery at startup** — iterate `integrations/*/backend.json` (packaged
   with the tool via `importlib.resources` so it works from an installed
   wheel, not just an editable clone) and `register_backend` each. The two
   in-code literals (`CLAUDE_BACKEND`, `CODEX_BACKEND`) become the **fallback
   seed**: registered first so a missing/broken manifest still yields a
   working backend; a valid manifest of the same name replaces it.
4. **Per-project layer** — when a backend is selected, apply its
   `.plan-tool/backends.json` `backends.<name>` block (model + extra argv) to
   produce the effective `CliBackend`.

`registered_binaries()` keeps working unchanged — it already iterates
`_REGISTRY`, so a manifest-registered backend's binary is auto-blocked by the
test-suite subprocess guard with no edit.

## Backward compatibility

- **No manifest present** → in-code `CLAUDE_BACKEND` / `CODEX_BACKEND` literals
  serve, exactly as today.
- **Manifests added** → must reproduce today's literals byte-for-byte; a
  golden test asserts `load_backend_from_dir("integrations/claude")` equals
  `CLAUDE_BACKEND` (and same for codex) so the externalization is provably
  lossless.
- **No `.plan-tool/backends.json`** → selection/model behavior identical to
  today.
- `--backend` / `PLAN_TOOL_BACKEND` semantics and precedence are preserved.

## Testing implications

- **Round-trip golden** — manifest → `CliBackend` equals the in-code literal
  (proves no behavior change on day one). Pin against
  `docs/CODEX_CLI_CONTRACT.md` as the codex argv source of truth.
- **Loader unit tests** — malformed JSON, unknown `parser`, missing required
  field, `null` vs string `auth` → typed errors with the registered-names
  list.
- **Precedence tests** — `--model` flag > project-file > manifest default;
  argv assembly order with `extra_*_argv` + model pair.
- **Discovery test** — a temp `integrations/<fake>/backend.json` registers and
  is blockable by the conftest subprocess guard (no real spawn).
- **Override scoping** — the `backends.<name>` block cannot swap binary/parser
  (those keys are ignored or rejected), only tune model/argv.
- Keep `TESTING.md`'s invoker-neutralization table current — the seam doesn't
  move, but the manifest loader is a new real-filesystem read to keep hermetic
  (tests point discovery at a `tmp_path` integrations dir).

## Docs to update when this lands

Per the repo's documented doc-ownership split:

- **`PLAN_FORMAT.md`** — no change (this is not plan frontmatter).
- **`README.md`** — extend `## Backends` (adjacent to `## Modes`) with the
  manifest layout + `--model` flag + per-project override; update the
  `## Current code layout` tree to show `integrations/<backend>/backend.json`
  and `.plan-tool/backends.json`.
- **`RUNBOOK.md`** — a `## Backends` recipe: "tune a backend for one project"
  + "add a new backend." Quick-reference rows for `--model` and
  `.plan-tool/backends.json`.
- **`integrations/claude/SKILL.md`** + **new `integrations/codex/SKILL.md`** —
  `argument-hint` gains `--model`; `## Invocation` notes the per-project file.
- **`docs/CODEX_CLI_CONTRACT.md`** — note the codex manifest is generated from
  / pinned to the contract.

## Open questions

1. **Config format** — JSON (matches `jira-config.json`, `plans.json`) vs TOML
   (matches `pyproject.toml`). Recommendation: **JSON**, for consistency with
   the other `.plan-tool/` files and the existing config precedent.
2. **`integrations/` packaging** — confirm `integrations/` ships in the wheel
   (`pyproject.toml` package-data / `importlib.resources`) so discovery works
   from `uv tool install`, not just the editable clone. Today `integrations/`
   is repo-root, *outside* the `plan_tool/` package — it likely needs to move
   under `plan_tool/integrations/` or be declared as data. **This is the one
   structural decision that affects packaging and should be settled first.**
3. **Should `.plan-tool/backends.json` get a `backends config` wizard** (like
   `jira config`), or stay hand-edit-only initially? Recommendation:
   hand-edit-only for v1; add a wizard if friction shows. (The selection doc
   proposes `plan-tool backends` subcommands that would host such a wizard.)
