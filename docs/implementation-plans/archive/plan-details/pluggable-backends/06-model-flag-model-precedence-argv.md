> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add `--model` flag, model precedence, and effective-backend production at selection

## Summary

Wire model selection and per-project argv tuning into the run path. Add a global `--model` flag to `plan_tool/cli/parser.py:make_base_parser` (parallel to the existing `--backend`), add a pure `build_effective_backend(base, *, model, extra_batch_argv, extra_streaming_argv) -> CliBackend` to `plan_tool/backend.py` that splices `[*extra_argv, model_flag, model]` in front of the prompt of the base backend's `batch_argv`/`streaming_argv` closures, and extend the backend-selection block in `plan_tool/cli/app.py:main` to read `.plan-tool/backends.json` overrides (step 4), resolve model precedence (`--model` > `backends.<name>.model` > `default_model` > omit), build the effective backend, and `set_active_backend` it before dispatch. The load-bearing decision: produce a transient *effective* `CliBackend` at selection (the registry keeps the manifest-loaded seeds untouched) by currying the base argv builders rather than re-deriving flag lists — so the splice point is uniform (`base_argv[:-1]` + extras/model + prompt) across all four builders and the no-config default short-circuits to the base object, preserving today's byte-identical argv. On green, `plan-tool --model opus run …` makes `get_active_backend().streaming_argv(P)` carry `--model opus` before the prompt, a `backends.<name>` block's `extra_streaming_argv` appends after manifest flags, and an unconfigured repo with no `--model` drives a byte-identical command line.

## Table of Contents

- [Why](#why) — the model/tuning surface that has a reader and fields but no consumer
- [Files (creates vs edits)](#files-creates-vs-edits) — three code edits, two test edits, one golden regen
- [Implementation](#implementation) — the flag, the splice function, the selection-time wiring and precedence
- [Tests](#tests) — argv-splice unit cases + parse/precedence/effective-backend cases
- [Acceptance criteria](#acceptance-criteria) — observable argv / precedence / default-byte-identity checks
- [References](#references) — argparse + the two CLI flag references
- [Deferred](#deferred) — doc sweep, umbrella-root scoping, failover/aspects keys

## Why

Steps 3–5 land the data and reader but no consumer: `plan_tool/backend.py:CliBackend` now carries inert `model_flag` / `default_model` fields (step 3), `plan_tool/backend_config.py` reads `backends.<name>` overrides into `BackendOverride` (`model`, `extra_batch_argv`, `extra_streaming_argv`) (step 4), and discovery registers manifest-built backends (step 5) — but nothing injects a model or extra argv into a live command line. `_claude_streaming_argv` / `_codex_streaming_argv` still hardcode their flag lists with no model passthrough, and `plan_tool/cli/app.py:main`'s selection block stops at `set_active_backend(resolve_backend(name))`. This step is the pure wiring that turns those fields into observable argv: a `--model` flag, the precedence resolution the plan's Architecture section pins (`--model` > project file > `default_model` > omit), and the `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]` assembly — closing the last gap so `opus`/`sonnet`/a codex model can be picked per run or per project without editing source.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/parser.py` — add a `--model` global flag in `make_base_parser`, immediately after the `--backend` `add_argument` block (both are process-wide backend-shaping flags applied once in `main`).
  - `plan_tool/backend.py` — add `build_effective_backend(base, *, model, extra_batch_argv, extra_streaming_argv) -> CliBackend`; extend the module docstring's "Public surface" list with it.
  - `plan_tool/cli/app.py` — in `main`, extend the backend-selection block (the `env_backend` / `name` / `explicit` / `resolve_backend` / `set_active_backend` sequence) to read overrides, resolve model precedence, build the effective backend, and set *it* active; add the `backend_config` + `build_effective_backend` imports.
  - `tests/test_backend.py` — add the `build_effective_backend` splice/short-circuit/guard cases.
  - `tests/test_cli.py` — add the `--model` parse, precedence, and effective-backend selection cases.
- **Edit required beyond the declared `files:` list (flagged):**
  - `tests/cli/package_surface_help.golden.txt` — regenerate (`UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py::…::test_help_matches_golden`). Adding `--model` to the global parser changes `plan-tool --help`; the golden in `tests/cli/test_package_surface.py` is byte-compared and will fail without this. No code edit to `test_package_surface.py` itself — only its golden data file.

## Implementation

> **Cross-step contract caveat.** This step consumes symbols landed by steps 3/4/5 that do not exist at HEAD and whose exact names/arity are asserted as fact below: `CliBackend.model_flag` / `default_model`, `batch_argv` / `streaming_argv` as `field(compare=False)`, codex `model_flag="-m"` (step 3), and `backend_config.py`'s `BackendOverride` (attributes `model` / `extra_batch_argv` / `extra_streaming_argv`) / `load_backend_overrides` / `BackendConfigError` (step 4). Before implementing, confirm the exported names and arity at HEAD once 3–5 have landed — if any upstream shape diverges (a differently-named field, a renamed `BackendOverride` attribute, a different model flag), reconcile this step's references to match; the wiring breaks silently otherwise. Step 5 also re-registers the claude/codex seeds as manifest-built objects at import time, so `resolve_backend(...)` / `get_active_backend()` returns an object that is `== CLAUDE_BACKEND` / `== CODEX_BACKEND` but not `is` the in-code literal — assert value/argv equality against the literals in this step's tests and criteria, never object identity.

### `plan_tool/cli/parser.py`

- **Add the `--model` flag** in `make_base_parser`, alongside the other once-per-process backend-shaping flags (`--backend`, `--prompt-mode`, `--experiment-arm`) consumed in `main`, not per-subcommand — exact placement within that group is open, the golden regen covers ordering:
  - `choices` — **none.** Model names are backend-specific and open-ended (`opus`, `sonnet`, a codex model id, future names); an enum would stale on every model release. `--backend` keeps its `choices=("claude", "codex")` because the registry is closed; `--model` is free-form `type=str`.
  - `default=None`, `dest="model"` — `None` means "unset, fall through to the project file / `default_model`", mirroring `--backend`'s `default=None` / `explicit` pattern.
  - `help` — state the precedence verbatim: `this flag > .plan-tool/backends.json backends.<name>.model > the backend's default_model > omit`. Note the model is passed to the active backend's `model_flag` (`--model` for claude, `-m` for codex).
- **No change to `CANONICAL_COMMAND_ORDER` / `_reorder_subcommands`** — `--model` is a base-parser flag, not a subcommand.

### `plan_tool/backend.py`

- **Add `build_effective_backend`** as a stdlib-only leaf function (uses `dataclasses.replace`; add `replace` to the `from dataclasses import …` line, or import it locally). Also add `Sequence` to the `from typing import Callable, Iterator, Optional` line (the module imports no `Sequence` today), or type the extra-argv params `list[str]`. Signature:
  - `build_effective_backend(base: CliBackend, *, model: Optional[str], extra_batch_argv: Sequence[str], extra_streaming_argv: Sequence[str]) -> CliBackend`
- **Short-circuit the no-op case first** — if `model is None` and both extra lists are empty, `return base` unchanged. This keeps the default selection path returning the exact registry object, so `get_active_backend() == CLAUDE_BACKEND` (value-equal to the literal, not `is` it — step 5 registers a manifest-built seed) and the byte-identity argv tests stay green with zero perturbation.
- **Resolve the model pair** — `model_pair = [base.model_flag, model] if model else []`. If `model` is set but `base.model_flag is None`, raise `ValueError(f"backend {base.name!r} declares no model_flag but a model was requested")` rather than silently dropping the requested model (the silent-no-op antipattern). Both registered backends set `model_flag` (step 3: `--model` / `-m`), so this guard only fires on a misconfigured manifest.
- **Curry new argv closures** that splice extras + model before the prompt, capturing the base builders by value:
  - Capture `base_batch = base.batch_argv`, `base_stream = base.streaming_argv` *before* `replace` so the closures don't recurse into the effective object.
  - Each wrapped builder: `argv = base_builder(prompt); return [*argv[:-1], *extra, *model_pair, argv[-1]]`.
  - **`argv[-1]` is always the prompt** in all four builders (`_claude_batch_argv`, `_claude_streaming_argv`, `_codex_batch_argv`, `_codex_streaming_argv` all put `prompt` last), so `argv[:-1]` is exactly `[binary, *manifest_flags]` — a uniform splice point that needs no per-backend branching and inherits any manifest-loaded flag changes (step 5) for free.
  - **Order matches the plan:** `[*manifest_flags, *extra_argv, *model_pair, prompt]`.
- **Return `replace(base, batch_argv=wrapped_batch, streaming_argv=wrapped_streaming)`** — `parse_stream_line`, `binary`, `name`, and all classification patterns are preserved by `replace`. `batch_argv` / `streaming_argv` are `field(compare=False)` (step 3), so the effective backend `==` the base under the dataclass `__eq__`; fidelity is asserted by argv *output*, never equality.
- **Do not mutate `_REGISTRY` or `_active_backend`** here — `build_effective_backend` is a pure transform; `main` calls `set_active_backend(effective)`.

### `plan_tool/cli/app.py`

- **Add imports** — `from plan_tool.backend import build_effective_backend` (extend the existing `plan_tool.backend` import group) and `from plan_tool.backend_config import BackendConfigError, load_backend_overrides` (step 4 module).
- **Extend the selection block in `main`** (between the existing `set_active_backend(selected)` and the missing-binary preflight). The current block resolves `selected = resolve_backend(name)`; replace the bare `set_active_backend(selected)` with the effective-backend production:
  - **Resolve repo root cheaply** via `_resolve_cmd_repo_root(args)` (already imported from `plan_tool.cli.context`). It honors `--repo-root` → `PLAN_TOOL_REPO_ROOT` → cwd-`.git`/`.plan-tool` walk with a cwd fallback — the right cwd-scoped surface for the *driven* project's `.plan-tool/backends.json`.
  - **Read overrides** — `overrides = load_backend_overrides(repo_root)`; `override = overrides.get(name)` (returns `None` when the repo has no `backends.<name>` block). Wrap in `try/except BackendConfigError as exc:` → `error(str(exc)); return 2`, mirroring the existing `resolve_backend` `ValueError` arm (malformed `backends.json` fails fast with the file named).
  - **Warn on unknown override keys** — after loading, compare `overrides` keys against the registered backend names (`set(_REGISTRY)` / a names accessor parallel to `registered_binaries()`); for each `backends.<name>` key matching no registered backend, emit a non-fatal warning naming the unknown key and the registered backend names (e.g. `unknown backend {key!r} in .plan-tool/backends.json; registered: {sorted(names)}`). A likely typo must not be silently dropped — this satisfies the plan's Architecture promise and acceptance criterion; the run still proceeds with the selected backend.
  - **Resolve model precedence** — `model = args.model or (override.model if override else None) or selected.default_model`. `args.model` (flag) wins; then the project file's `model`; then the manifest `default_model`; `None` omits.
  - **Resolve extra argv** — `extra_batch = override.extra_batch_argv if override else []`; `extra_streaming = override.extra_streaming_argv if override else []`.
  - **Build + activate** — `effective = build_effective_backend(selected, model=model, extra_batch_argv=extra_batch, extra_streaming_argv=extra_streaming)`; `set_active_backend(effective)`. Wrap the `build_effective_backend` call in `try/except ValueError as exc:` → `error(str(exc)); return 2` (fold into the same `try` as `load_backend_overrides`, or add a sibling arm): a `--model` against a backend whose manifest omits `model_flag` raises `ValueError`, and the convention requires a graceful `return 2` with the message — never an uncaught traceback.
- **Preflight unchanged** — the missing-binary check reads `selected.binary`; `effective.binary == selected.binary` (override cannot swap binary, step 4's structural guarantee), so the existing `shutil.which(selected.binary)` block needs no edit. Keep it referencing `selected` (or switch to `effective` — identical).
- **No change to `set_default_wait_on_rate_limit` or the verbosity block** below.

#### Foundational logic and shared call sites

- **The rule this step adds:** *the active backend's argv = base argv with `[*project_extra_argv, model_flag, model]` spliced before the prompt.* This logic lives in exactly one place — `build_effective_backend` — and is consumed at the two existing live argv call sites with **no edit**: `plan_tool/shell.py:_run_once` (`get_active_backend().batch_argv(prompt)`) and `plan_tool/launcher.py` (`get_active_backend().streaming_argv(prompt)`). Both already route through `get_active_backend()`, so activating the effective backend at selection propagates the model/extras to every backend-driving subcommand (create / detail / run / review / completeness / jira / verify / bench) without per-call-site changes.
- **No duplicated splice logic elsewhere** — grep confirms `batch_argv` / `streaming_argv` are invoked only at those two sites; argv is never re-assembled inline in `shell.py` or `launcher.py`. The plan's `_CODEX_COMMON_FLAGS` / `_claude_streaming_argv` flag lists stay in `backend.py` as the seed builders the effective wrapper layers on top of.

## Tests

This is a **feature** step. Enumerate the unit tests below alongside the implementation; **every new test must be green before the step is done** (green-before-done gate). Existing argv byte-identity tests in `tests/test_backend.py` (`test_claude_batch_argv_byte_identical`, `test_claude_streaming_argv_byte_identical`) call the literal backends directly and must remain green unchanged.

### `tests/test_backend.py` — `build_effective_backend` unit cases

- `test_build_effective_backend_no_overrides_returns_base` — `model=None`, empty extras → returns the *same* base object (`is CLAUDE_BACKEND`); preserves default byte-identity and registry identity.
- `test_build_effective_backend_inserts_claude_model_pair` — claude base, `model="opus"` → `batch_argv("P") == ["claude", "-p", "--permission-mode", "acceptEdits", "--model", "opus", "P"]` and `streaming_argv("P")` ends `… "--permission-mode", "acceptEdits", "--model", "opus", "P"`.
- `test_build_effective_backend_inserts_codex_model_pair` — codex base, `model="o3"` → `batch_argv("P") == ["codex", "exec", "-s", "workspace-write", "--skip-git-repo-check", "--ephemeral", "-m", "o3", "P"]`.
- `test_build_effective_backend_appends_extra_before_model` — `extra_batch_argv=["--foo"]`, `model="opus"` → `["claude", "-p", "--permission-mode", "acceptEdits", "--foo", "--model", "opus", "P"]` (asserts extras precede the model pair, both before prompt).
- `test_build_effective_backend_extra_only_no_model` — extras set, `model=None` → extras spliced, no model pair, prompt last.
- `test_build_effective_backend_model_without_flag_raises` — a base with `model_flag=None` + `model="x"` → `ValueError` naming the backend (no silent drop).
- `test_build_effective_backend_preserves_parser_and_patterns` — effective `.parse_stream_line is base.parse_stream_line`, `.binary == base.binary`, classification patterns identical (only argv builders change).
- `test_build_effective_backend_eq_base_under_dataclass_eq` — effective with a model `== base` (argv fields are `compare=False`), documenting why fidelity is output-asserted not equality-asserted.

### `tests/test_cli.py` — flag + selection cases

- `test_model_flag_parses` — `build_parser().parse_args(["--model", "opus", "list"]).model == "opus"`.
- `test_model_flag_defaults_none` — `parse_args(["list"]).model is None`.
- `test_model_flag_applies_to_active_backend` — `main(["--model", "opus", <read-only cmd>])` with `load_backend_overrides` stubbed `{}` → `get_active_backend().streaming_argv("P")` contains `["--model", "opus"]`.
- `test_model_precedence_flag_beats_config` — stub `load_backend_overrides` to a `backends["claude"].model="sonnet"`; `--model opus` → effective argv carries `opus`.
- `test_model_precedence_config_beats_default` — no `--model`, stubbed override `model="sonnet"` → argv carries `sonnet`.
- `test_extra_streaming_argv_from_config_applied` — stubbed override `extra_streaming_argv=["--foo"]` → `get_active_backend().streaming_argv("P")` contains `"--foo"` before the prompt.
- `test_no_model_no_config_byte_identical` — default path, stubbed `{}` → `get_active_backend() == CLAUDE_BACKEND` and `get_active_backend().streaming_argv("P") == CLAUDE_BACKEND.streaming_argv("P")` (assert value/argv equality, not `is`: post-step-5 the registered claude seed is a manifest-built object that is `== CLAUDE_BACKEND` but not the in-code literal; the effective short-circuit returns that registry object unchanged).
- `test_malformed_backends_json_returns_2` — stub `load_backend_overrides` to raise `BackendConfigError` → `main` returns `2` and prints an error naming the file.
- `test_model_against_no_model_flag_returns_2` — select a backend with `model_flag=None` and pass `--model x` → `main` returns `2` with the error message (no uncaught `ValueError`).
- `test_unknown_override_key_warns` — stub `load_backend_overrides` to return a block keyed by an unregistered name (e.g. `"gemini"`); `main` proceeds (rc != 2) and emits a warning naming the unknown key and the registered backend names.

Use a `set_active_backend(CLAUDE_BACKEND)` teardown fixture (mirror `tests/cli/test_package_surface.py:_restore_active_backend`) so the process-global active backend is reset between cases. Stub `plan_tool.cli.app.load_backend_overrides` rather than writing on-disk `.plan-tool/backends.json` to keep cases hermetic.

## Acceptance criteria

- `plan-tool --model opus run …` makes `get_active_backend().streaming_argv("P")` end with `… --model opus P`; codex makes it `… -m <model> P`.
- `build_effective_backend(CLAUDE_BACKEND, model=None, extra_batch_argv=[], extra_streaming_argv=[])` returns `CLAUDE_BACKEND` itself (`is`).
- Model precedence resolves `--model` > `backends.<name>.model` > `default_model` > omit, verified by the three precedence tests.
- `extra_*_argv` from a `backends.<name>` block appears after manifest flags and before `model_pair`/prompt in the effective argv.
- An unconfigured repo with no `--model` drives a byte-identical command line — existing `test_claude_batch_argv_byte_identical` / `test_claude_streaming_argv_byte_identical` stay green; `get_active_backend() == CLAUDE_BACKEND` (value-equal, argv byte-matches the literal — not `is`, since step 5 registers a manifest-built seed) after a default `main`.
- A malformed `.plan-tool/backends.json` makes `main` return `2` with the file named (no traceback).
- A `backends.<name>` key matching no registered backend emits a non-fatal warning naming the unknown key and the registered backend names, and the run still proceeds with the selected backend.
- `build_effective_backend` raises `ValueError` when a model is requested against a backend with `model_flag=None`, and `main` catches it to `return 2` with the message rather than surfacing an uncaught traceback.
- `plan-tool --help` lists `--model`; `tests/cli/test_package_surface.py::…::test_help_matches_golden` passes against the regenerated golden.

## References

- [argparse — Parser for command-line options](https://docs.python.org/3/library/argparse.html) — adding the free-form `--model` flag (`default=None`, no `choices`) to the base parser while preserving `--backend` semantics.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — confirms `--model` is the claude model flag the effective argv injects (`model_flag="--model"`).
- [OpenAI Codex CLI (GitHub)](https://github.com/openai/codex) — confirms codex's `-m` model flag and `exec` argv shape the effective argv injects for the codex backend.

## Deferred

- **Doc sweep** (`README.md` `## Backends`, `RUNBOOK.md` `--model` / `.plan-tool/backends.json` quick-reference, `integrations/claude/SKILL.md` + `integrations/codex/SKILL.md` `argument-hint` gaining `--model`, `docs/CODEX_CLI_CONTRACT.md`) — explicitly the plan's "Doc updates on landing" deferral, not step 6's code footprint. `PLAN_FORMAT.md` needs no change (`--model` is a flag, not a frontmatter field).
- **Umbrella-root vs cwd-root scoping** — `main` reads `backends.json` from `_resolve_cmd_repo_root(args)` (cwd-scoped). A subcommand that later resolves a different *umbrella* root keeps the cwd-resolved model/extras; acceptable for v1 (backends.json sits at the project root). Revisit only if a multi-repo umbrella needs per-sub-repo model tuning.
- **`default` / `aspects` / `failover` keys** in `.plan-tool/backends.json` — owned by `docs/design-plans/BACKEND_SELECTION.md`, not consumed here; `load_backend_overrides` tolerates and ignores them (step 4).
- **Per-subcommand `--model` override** — the flag is global/process-wide (like `--backend`); a future per-step or per-call model is out of scope.
