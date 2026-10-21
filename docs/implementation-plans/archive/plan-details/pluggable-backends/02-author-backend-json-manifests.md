> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Author `backend.json` manifests reproducing the claude/codex literals, plus a new codex `SKILL.md`

## Summary

Author three new data/doc files that externalize today's in-code `CliBackend` literals as hand-editable JSON: `integrations/claude/backend.json` and `integrations/codex/backend.json` reproduce `CLAUDE_BACKEND` / `CODEX_BACKEND` (`plan_tool/backend.py`) field-for-field, and `integrations/codex/SKILL.md` adds the codex-flavored variant of the plan-tool skill router. The load-bearing decision is **byte-fidelity**: each manifest's `batch_argv` / `streaming_argv` flag lists and `classification` regex strings must decode to the exact argv flags and `re.Pattern.pattern` strings the literals carry, so step 3's round-trip golden (`load_backend_from_dir(...) == CLAUDE_BACKEND`) passes. This is a **non-code, data-only** step — no Python is touched, nothing reads these files yet (the loader is step 3, discovery step 5). On green, both manifests parse as JSON, every `classification` string compiles under `re.IGNORECASE`, and their decoded argv/pattern values match the literals.

## Table of Contents

- [Why](#why) — the data the loader (step 3) needs to exist before it can be read
- [Files (creates vs edits)](#files-creates-vs-edits) — three new files, zero edits
- [Implementation](#implementation) — exact manifest contents, JSON-escaping rules, codex SKILL.md shape
- [Tests](#tests) — JSON parse, regex compile, fidelity cross-check
- [Acceptance criteria](#acceptance-criteria) — observable file-contents and decode checks
- [References](#references) — json/re stdlib, the two CLI references, the codex contract
- [Deferred](#deferred) — loader, IGNORECASE application, discovery, `--model`, doc sweep

## Why

- **The loader has nothing to load.** Step 3's `load_backend_from_dir` and its round-trip golden (`docs/implementation-plans/2-pluggable-backends.md` step 3, depends_on: 2) need real `integrations/<backend>/backend.json` files on disk that reproduce the in-code literals. This step produces that ground truth before any loader code depends on it.
- **The literals are the spec.** `plan_tool/backend.py` already holds the authoritative argv builders (`_claude_batch_argv`, `_claude_streaming_argv`, `_codex_batch_argv`, `_codex_streaming_argv`) and compiled classification patterns (`_CLAUDE_RATE_LIMIT_PATTERN`, `_CLAUDE_PROVIDER_LIMIT_PATTERN`, `_CLAUDE_CONTEXT_OVERFLOW_PATTERN`, `_CLAUDE_TRANSIENT_PATTERN`, `_CODEX_AUTH_PATTERN`). The manifests transcribe those values into data — they do not invent new ones.
- **codex needs a skill router too.** `integrations/claude/SKILL.md` exists; `integrations/codex/` does not exist at all yet (only `integrations/claude/SKILL.md` is on disk). This step creates the codex directory and its SKILL.md sibling so the `integrations/<backend>/` layout is symmetric.

## Files (creates vs edits)

- **New files:**
  - `integrations/claude/backend.json` — manifest reproducing `CLAUDE_BACKEND`.
  - `integrations/codex/backend.json` — manifest reproducing `CODEX_BACKEND`.
  - `integrations/codex/SKILL.md` — codex-backend variant of the plan-tool skill router.
- **Existing files (edits only):** none. Leave `integrations/claude/SKILL.md` byte-unchanged — its `argument-hint` gains `--model` only when that flag lands (step 6; see [Deferred](#deferred)).

## Implementation

### Manifest schema (both `backend.json` files)

Top-level keys (per `docs/implementation-plans/2-pluggable-backends.md` "Manifest schema"): `name`, `binary`, `parser`, `model_flag`, `default_model`, `batch_argv`, `streaming_argv`, `classification`. The `classification` object carries `rate_limit`, `provider_limit`, `context_overflow`, `transient`, and `auth`.

- **Formatting:** match `plan_tool/jira_config.py:write_jira_config`'s `json.dumps(payload, indent=2)` + trailing newline, and additionally pass `sort_keys=True` to emit **sorted keys** (the plan calls for "sorted keys, stable indent, like jira-config.json") so hand-edits diff cleanly.
- **`parser` is the only field naming code** — a discriminator resolved by step 3's parser registry: `"claude"` → `_claude_parse_stream_line`, `"codex"` → `_codex_parse_stream_line`. The NDJSON parse bodies stay in `plan_tool/backend.py`; the manifest selects one by name, it does not describe the parse (plan "Out of scope": *Stream parser stays in code*).
- **`batch_argv` / `streaming_argv` hold the flags between binary and prompt only** — no binary, no prompt, no model pair. Step 3's loader assembles the final argv as `[binary, *manifest_argv, …, prompt]`. For codex the `exec` subcommand is the **first** flag-list entry.
- **`model_flag` / `default_model` are new, inert today** — `default_model: null` means "inject no model pair", reproducing the literals exactly (the current argv builders pass no model flag). `model_flag` records the flag name for when step 6 wires `--model`.

### `integrations/claude/backend.json`

Reproduces `CLAUDE_BACKEND`. `batch_argv` mirrors `_claude_batch_argv` minus the `"claude"` head and trailing `prompt`; `streaming_argv` mirrors `_claude_streaming_argv` likewise. `classification.auth` is `null` (claude defines no `auth_pattern` — `CliBackend.auth_pattern` defaults `None`). `model_flag` is `"--model"`.

```json
{
  "batch_argv": [
    "-p",
    "--permission-mode",
    "acceptEdits"
  ],
  "binary": "claude",
  "classification": {
    "auth": null,
    "context_overflow": "(prompt is too long|input too long|too many tokens|maximum[ \\t]+(context|tokens)|context[ \\t]+(length|window|size).*(exceed|limit)|exceed(ed)?[ \\t]+(the[ \\t]+)?max(imum)?[ \\t]+(context|tokens)|reduc(e|ing).*token)",
    "provider_limit": "You've hit your limit",
    "rate_limit": "(rate[- ]?limit|too many requests|usage limit|try again at|Retry-After)",
    "transient": "(timed out|timeout|ECONNRESET|EAI_AGAIN|network error|temporarily unavailable|connection reset|connection was closed|socket hang ?up|\\b429\\b)"
  },
  "default_model": null,
  "model_flag": "--model",
  "name": "claude",
  "parser": "claude",
  "streaming_argv": [
    "-p",
    "--output-format",
    "stream-json",
    "--verbose",
    "--permission-mode",
    "acceptEdits"
  ]
}
```

### `integrations/codex/backend.json`

Reproduces `CODEX_BACKEND`. `batch_argv` = `["exec", *_CODEX_COMMON_FLAGS]`; `streaming_argv` = `["exec", "--json", *_CODEX_COMMON_FLAGS]` (where `_CODEX_COMMON_FLAGS` = `-s workspace-write --skip-git-repo-check --ephemeral`, per `plan_tool/backend.py` and `docs/CODEX_CLI_CONTRACT.md` "Batch invocation" / "Streaming invocation"). `classification.auth` is the codex `_CODEX_AUTH_PATTERN` string (the one genuinely new failure class). The four other `classification` strings are **identical to claude's** — `CODEX_BACKEND` reuses claude's compiled patterns, so copy the same strings verbatim. `model_flag` is `"-m"` (the codex model flag verified in `docs/CODEX_CLI_CONTRACT.md` "Error shapes", via the bogus `-m` probe).

```json
{
  "batch_argv": [
    "exec",
    "-s",
    "workspace-write",
    "--skip-git-repo-check",
    "--ephemeral"
  ],
  "binary": "codex",
  "classification": {
    "auth": "(not logged in|not authenticated|unauthorized|\\b401\\b|auth\\.json|codex login|please (re-?)?login|invalid api key|authentication (failed|required))",
    "context_overflow": "(prompt is too long|input too long|too many tokens|maximum[ \\t]+(context|tokens)|context[ \\t]+(length|window|size).*(exceed|limit)|exceed(ed)?[ \\t]+(the[ \\t]+)?max(imum)?[ \\t]+(context|tokens)|reduc(e|ing).*token)",
    "provider_limit": "You've hit your limit",
    "rate_limit": "(rate[- ]?limit|too many requests|usage limit|try again at|Retry-After)",
    "transient": "(timed out|timeout|ECONNRESET|EAI_AGAIN|network error|temporarily unavailable|connection reset|connection was closed|socket hang ?up|\\b429\\b)"
  },
  "default_model": null,
  "model_flag": "-m",
  "name": "codex",
  "parser": "codex",
  "streaming_argv": [
    "exec",
    "--json",
    "-s",
    "workspace-write",
    "--skip-git-repo-check",
    "--ephemeral"
  ]
}
```

### JSON-escaping rules (the load-bearing fidelity concern)

The classification values are **regex source strings**, and JSON decode must yield the exact `re.Pattern.pattern` attribute of the in-code literal. Two escape classes:

- **`\t` in `context_overflow`** — the in-code pattern (`plan_tool/backend.py:_CLAUDE_CONTEXT_OVERFLOW_PATTERN`) is a raw string `r"…[ \t]+…"`, so `.pattern` contains the two characters **backslash-t**, not a tab. In JSON write it as `[ \\t]` so `json.loads` returns `[ \t]`. Do **not** emit a literal tab character.
- **`\b` / `\.`** — `transient`'s `\b429\b` and codex `auth`'s `\b401\b` / `auth\.json` are word-boundary / literal-dot regex escapes. Write each backslash doubled in JSON (`\\b429\\b`, `auth\\.json`) so the decoded string matches the literal's `.pattern`.

- **Store the bare pattern — never an inline flag.** The literals are compiled with `re.IGNORECASE` (every one of the five). The manifest carries **no flag information**; step 3's loader applies `re.IGNORECASE` uniformly. Do **not** prepend an inline `(?i)` to any string — that would change the decoded `.pattern`, and step 3's equality (which relies on `re.compile(s, re.I)` resolving to the same cached `re.Pattern` object as the literal) would break.

### `integrations/codex/SKILL.md`

- **Clone the structure of `integrations/claude/SKILL.md`**, retargeting only the backend-specific copy to codex. Keep the same YAML frontmatter key set: `name`, `description`, `allowed-tools`, `model`, `argument-hint`.
- **Retarget backend-specific lines:**
  - `description` — replace claude's "spawning a fresh claude subprocess per step" with the codex equivalent (a fresh `codex exec` subprocess per step); keep the rest (frontmatter-plan routing, per-project `plans.json` discovery, legacy-plan fallback) verbatim.
  - The **Invocation → Backend** paragraph — frame codex as the selected backend (`--backend codex` / `PLAN_TOOL_BACKEND=codex`), and keep the README "Backends" pointer.
  - Any "spawns a `claude` subprocess" prose in the body → codex.
- **Keep the shared router content backend-agnostic** — "Which tool", "Running from chat / automation", "Decision tree", "Subcommands at a glance", "Authoring conventions", "Going deeper" describe plan-tool itself, not the runtime; carry them across unchanged.
- **`argument-hint` matches claude's current shape** — do **not** add `--model` yet (the flag is step 6). The `--model` addition to **both** SKILL.md files is part of the step-6 / doc-landing sweep.
- **No runtime consumer in this plan.** Step 5's discovery iterates `integrations/*/backend.json` only — it never reads `SKILL.md`. This file is a human/skill-router asset paralleling `integrations/claude/SKILL.md` (installed via `uv tool install --editable .`), not loaded by plan-tool.

### Foundational logic & intentional duplication

- **Foundational logic of this step:** declarative externalization — the argv flags and classification regexes that today live only as Python literals in `plan_tool/backend.py` now also exist as JSON data.
- **The same values live in two places after this step** (the literals in `plan_tool/backend.py` and these manifests). This duplication is **intentional and temporary**: the plan makes the manifest the source of truth with the literals demoted to a fallback seed (step 5 "registered first so a broken/missing manifest still yields a working backend; a valid same-name manifest replaces it"). Collapsing the duplication into a single source is **steps 3 + 5**, not this step — see [Deferred](#deferred). Do not edit `plan_tool/backend.py` here.

## Tests

No production code changes (data-only step), so the tests are direct artifact verifications run by hand; the authoritative `CliBackend`-equality golden lands in step 3:

- **JSON parse-validity** — `python -c "import json; json.load(open('integrations/claude/backend.json')); json.load(open('integrations/codex/backend.json'))"` exits 0.
- **Schema conformance** — each manifest has all eight top-level keys (`name`, `binary`, `parser`, `model_flag`, `default_model`, `batch_argv`, `streaming_argv`, `classification`) and `classification` has `rate_limit`, `provider_limit`, `context_overflow`, `transient`, `auth`.
- **Regex compile-validity** — each `classification` string value (skip `null`) compiles: `re.compile(value, re.IGNORECASE)` raises nothing.
- **Argv fidelity cross-check** — `["claude", *claude_manifest["batch_argv"], "P"] == _claude_batch_argv("P")` and the streaming analog; same for codex against `_codex_batch_argv` / `_codex_streaming_argv`. (The authoritative `CliBackend`-equality golden is step 3's; this is the lightweight manual confirmation that the data matches before the loader exists.)
- **Pattern fidelity cross-check** — each decoded classification string equals the corresponding in-code `.pattern` (e.g. `claude_manifest["classification"]["rate_limit"] == _CLAUDE_RATE_LIMIT_PATTERN.pattern`), and codex's `auth` equals `_CODEX_AUTH_PATTERN.pattern`. claude's `classification.auth` is `null`.
- **codex SKILL.md** — frontmatter parses as YAML; its key set equals `integrations/claude/SKILL.md`'s; internal links resolve; no claude-only copy ("a fresh `claude` subprocess") remains where codex is meant.

## Acceptance criteria

- `integrations/claude/backend.json`, `integrations/codex/backend.json`, and `integrations/codex/SKILL.md` exist.
- Both `backend.json` files `json.load` without error and re-serialize stably (sorted keys, 2-space indent, trailing newline).
- claude `batch_argv == ["-p", "--permission-mode", "acceptEdits"]`; claude `streaming_argv == ["-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits"]`.
- codex `batch_argv == ["exec", "-s", "workspace-write", "--skip-git-repo-check", "--ephemeral"]`; codex `streaming_argv == ["exec", "--json", "-s", "workspace-write", "--skip-git-repo-check", "--ephemeral"]`.
- Every `classification` string decodes byte-identically to the matching `plan_tool/backend.py` pattern's `.pattern`, and each compiles under `re.IGNORECASE`.
- claude `classification.auth is null`; codex `classification.auth` equals `_CODEX_AUTH_PATTERN.pattern`.
- `parser` is `"claude"` / `"codex"` respectively; `model_flag` is `"--model"` / `"-m"`; both `default_model` are `null`.
- `integrations/codex/SKILL.md` frontmatter parses and carries the same key set as `integrations/claude/SKILL.md`, with no `--model` in `argument-hint`.

## References

- [json — JSON encoder and decoder (Python Standard Library)](https://docs.python.org/3/library/json.html) — `json.load`/`json.dumps(indent=2, sort_keys=…)` semantics for writing and validating the manifests.
- [re — Regular expression operations (Python Standard Library)](https://docs.python.org/3/library/re.html) — confirms backslash/`\b`/`\t` handling so the JSON-escaped strings compile to the intended patterns.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — `--permission-mode`, `--output-format stream-json`, `--verbose`, `--model`: the flags the claude manifest reproduces.
- [OpenAI Codex CLI (GitHub)](https://github.com/openai/codex) — the `codex exec` subcommand, `--json`, sandbox flags, and `-m` model flag the codex manifest reproduces.
- `docs/CODEX_CLI_CONTRACT.md` — the pinned source of codex's `batch_argv` / `streaming_argv` working forms (`-s workspace-write --skip-git-repo-check --ephemeral`) and the `-m` model flag.

## Deferred

- **`load_backend_from_dir`, the parser registry, regex compilation, `CliBackend` manifest fields, and the round-trip golden** — step 3 (depends_on: 2). The `CliBackend == literal` equality and `re.IGNORECASE` application live there; this step only produces the data they consume.
- **Uniform `re.IGNORECASE` application by the loader** — step 3. The manifest deliberately stores bare patterns with no inline flag.
- **Startup discovery + registration over the in-code fallback seed** — step 5; iterates `integrations/*/backend.json` via `importlib.resources`. Resolves the intentional literal-vs-manifest duplication this step creates.
- **`--model` flag, model precedence, and argv assembly with `extra_*_argv` + model pair** — step 6. `model_flag` / `default_model` ship inert here.
- **Adding `--model` to both SKILL.md `argument-hint`s and the README/RUNBOOK "Backends" updates** — plan-level "Deferred" doc sweep on landing; out of scope for this data step.
- **codex consuming `SKILL.md`** — there is no runtime consumer; it is a skill-router asset paralleling `integrations/claude/SKILL.md`, not loaded by plan-tool.

