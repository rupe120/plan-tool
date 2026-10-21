> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `load_backend_from_dir` + parser registry + `CliBackend` manifest fields, with a round-trip golden

## Summary

Add `load_backend_from_dir(path) -> CliBackend` to `plan_tool/backend.py`: it reads a `backend.json` manifest (authored in step 2, `depends_on: 2`), resolves the `parser` discriminator through a new `_PARSER_REGISTRY` to a real parse function, compiles the `classification` regex strings with `re.IGNORECASE`, curries the `batch_argv`/`streaming_argv` flag lists into closures, and returns a `CliBackend` — raising a typed `BackendManifestError` (modeled on `plan_tool/jira_config.py:JiraConfigError`) on malformed JSON, an unknown `parser`, or a missing required field. Two new `CliBackend` fields, `model_flag` and `default_model`, ship inert (set on `CLAUDE_BACKEND` / `CODEX_BACKEND` to match the manifests). The load-bearing decision: keep `batch_argv`/`streaming_argv` as `Callable` closures (per the plan) and mark them `field(compare=False)` so the round-trip golden `load_backend_from_dir(...) == CLAUDE_BACKEND` works through the auto-generated dataclass `__eq__` — argv fidelity is verified separately by comparing builder output. On green, `load_backend_from_dir("integrations/claude")` equals `CLAUDE_BACKEND` and `"integrations/codex"` equals `CODEX_BACKEND`, with no behavior change to the live run path.

## Table of Contents

- [Why](#why) — the loader the manifests (step 2) exist to feed, and the equality design it needs
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, zero new files
- [Implementation](#implementation) — fields, parser registry, loader, typed error, and the `compare=False` equality seam
- [Tests](#tests) — round-trip goldens, loader-error cases, field assertions
- [Acceptance criteria](#acceptance-criteria) — observable equality / error / field checks
- [References](#references) — json / re stdlib + the manifest source of truth
- [Deferred](#deferred) — discovery (step 5), `--model` precedence + extra_argv (step 6), project config (step 4)

## Why

`plan_tool/backend.py` defines `CLAUDE_BACKEND` / `CODEX_BACKEND` as frozen Python literals with no external construction path; step 2 lands `integrations/<backend>/backend.json` manifests that reproduce those literals as data, but **nothing reads them yet**. This step adds the loader that turns a manifest directory into a `CliBackend`, the parser registry that is the single code↔manifest link, and the two new descriptor fields (`model_flag` / `default_model`) the manifest schema declares. It must prove byte-fidelity — a manifest that fails to reproduce the literal would silently change run behavior — which is exactly what the round-trip golden (`load_backend_from_dir("integrations/claude") == CLAUDE_BACKEND`) pins. Step 5 then reuses this loader for `importlib.resources` startup discovery; step 6 reuses `model_flag` / `default_model` for `--model`. This step ships them inert so those later steps are pure wiring.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/backend.py` —
    - Add fields `model_flag: Optional[str] = None` and `default_model: Optional[str] = None` to `CliBackend`; mark the existing `batch_argv` / `streaming_argv` fields `field(compare=False)`.
    - Set `model_flag` / `default_model` on the `CLAUDE_BACKEND` and `CODEX_BACKEND` literals to match the step-2 manifests (`"--model"` / `"-m"`, both `default_model=None`).
    - Add `class BackendManifestError(Exception)`, the module-level `_PARSER_REGISTRY`, an optional `register_parser`, and `load_backend_from_dir`.
  - `tests/test_backend.py` — add the round-trip golden + loader-error + new-field test cases (enumerated under [Tests](#tests)).

## Implementation

### `plan_tool/backend.py`

**`CliBackend` field changes** (the descriptor at `CliBackend`):

- **Add two manifest fields**, both defaulted so existing construction stays valid and they sort after the already-defaulted `auth_pattern`:
  - `model_flag: Optional[str] = None` — the flag name (`"--model"` for claude, `"-m"` for codex) that step 6 will pair with a model value.
  - `default_model: Optional[str] = None` — the manifest's default model; `None` = inject no model pair (today's behavior).
- **Mark the argv callables and the regex-pattern fields non-comparable.** Change `batch_argv` and `streaming_argv` to `Callable[[str], list[str]] = field(compare=False)`, and mark the four classification patterns + `auth_pattern` `field(compare=False)` too (import `field` from `dataclasses`). Rationale:
  - The loader curries **closures** over the flag lists (per the plan's "curries `batch_argv`/`streaming_argv` closures"); two distinct closures never compare `==`, so leaving them in the generated `__eq__` would make the round-trip golden impossible.
  - `re.Pattern` has no value equality, so the generated `__eq__` compares the pattern fields by identity. That relies on `re`'s compile cache returning the *same* object for the literal and the loader's `re.compile`, but CPython clears `re._cache` wholesale at `_MAXCACHE` (512 distinct compiles), so under the full-suite `uv run pytest tests/ -q` whole-object `==` can flake to `False`. Excluding the pattern fields from `__eq__` and asserting them by value (`.pattern`/`.flags`) in the round-trip tests removes that flake.
  - `compare=False` excludes only those seven fields. Every other field stays compared: `name`/`binary` (str), `parse_stream_line` (same function object via the registry → identity-equal), `model_flag`/`default_model` (str/None). Argv fidelity is verified by **output**, and pattern fidelity by `.pattern`/`.flags` value, in the test — not by `__eq__`.
- **Keep `batch_argv` / `streaming_argv` as `Callable` fields** — do **not** convert them to data tuples + methods. The two live call sites — the batch argv in `plan_tool/shell.py` (`get_active_backend().batch_argv(prompt)`) and the streaming argv in `plan_tool/launcher.py` (`get_active_backend().streaming_argv(prompt)`) — stay byte-identical, and the existing `_claude_batch_argv` / `_codex_batch_argv` functions remain the fallback-seed builders.

**Set the new fields on the literals.** Add `model_flag="--model", default_model=None` to the `CLAUDE_BACKEND` constructor and `model_flag="-m", default_model=None` to `CODEX_BACKEND`. This is mandatory for the golden: a loaded backend carries `model_flag="--model"`, so the literal must too, or whole-object `==` fails on that field.

**Parser registry** — the one code→manifest link:

- Add `_PARSER_REGISTRY: dict[str, Callable[..., Optional[_StreamLineParse]]] = {"claude": _claude_parse_stream_line, "codex": _codex_parse_stream_line}`, declared after both parse functions exist.
- Add `register_parser(name: str, fn: Callable) -> None` (mutates `_PARSER_REGISTRY`) so a future custom-shaped backend adds its parser without editing the loader — mirrors `register_backend`'s shape.
- Resolution helper raises on a miss listing the registered names: `BackendManifestError(f"unknown parser {name!r}; registered: {sorted(_PARSER_REGISTRY)}")`. The registered-names list in the message is an acceptance requirement.

**`BackendManifestError`** — typed load error, defined near the top of the module (stdlib-only, preserving the leaf import topology). Mirror `plan_tool/jira_config.py:JiraConfigError`'s usage: subclass `Exception`, carry a message naming the offending file/field.

**`load_backend_from_dir(path: Path) -> CliBackend`** — takes a manifest **directory** (not the packaged-resource handle; `importlib.resources` discovery is step 5):

1. **Read** `path / "backend.json"`. On `FileNotFoundError` → `BackendManifestError` naming the missing manifest; on `json.JSONDecodeError` → `BackendManifestError(f"invalid JSON in {manifest_file}: {exc}")` (the `jira_config.py` invalid-JSON precedent).
2. **Validate required keys** — `name`, `binary`, `parser`, `batch_argv`, `streaming_argv`, `classification` — raising `BackendManifestError(f"missing required field {key!r} in {manifest_file}")` on the first absent one. Then validate the required `classification` sub-keys `rate_limit`, `provider_limit`, `context_overflow`, `transient` (each maps to a non-optional `CliBackend` pattern field), raising `BackendManifestError(f"missing required field 'classification.{key}' in {manifest_file}")` on the first absent one, so a missing limit pattern surfaces as a typed error rather than a raw `TypeError` from `re.compile(None)`. `classification.auth` stays optional (`null`/absent → `auth_pattern=None`). `model_flag` / `default_model` default to `None` when absent.
3. **Resolve `parser`** through the resolution helper (unknown → typed error with the registered-parser list).
4. **Compile classification regexes** with `re.IGNORECASE` — the uniform compile flag the literals use, so the loaded patterns match by `.pattern`/`.flags` value (the round-trip tests assert value, not object identity). `classification.auth`: `null`/absent → `auth_pattern=None`; a string → `re.compile(s, re.IGNORECASE)`.
5. **Curry the argv closures** over `binary` and the manifest flag lists only. The closure assembles `[binary, *flags, prompt]` — no model pair (claude/codex: byte-identical to the literal functions). Model injection is solely step 6's job: `build_effective_backend` is the single point that resolves precedence and splices `[model_flag, model]` via `base_argv[:-1]`, so this closure must leave `argv[:-1]` exactly `[binary, *flags]`. The project `extra_*_argv` and `--model` override layer on top in step 6.
6. **Return** `CliBackend(name=…, binary=…, batch_argv=<closure>, streaming_argv=<closure>, parse_stream_line=<resolved fn>, rate_limit_pattern=…, provider_limit_pattern=…, context_overflow_pattern=…, transient_pattern=…, auth_pattern=…, model_flag=…, default_model=…)`.

**Foundational logic:** deserialize a `backend.json` manifest into a `CliBackend` (parser-name→function resolution + IGNORECASE regex compilation + argv-closure currying). The parallel locations the audit surfaces:

- The `CLAUDE_BACKEND` / `CODEX_BACKEND` literal constructions are the equality target this loader must reproduce; step 5 makes them the **fallback seed** registered before manifests — left to [Deferred](#deferred), not changed here.
- `plan_tool/jira_config.py:JiraConfigError` + its `load`-time `f"invalid JSON in {mf}: {exc}"` raise is the typed-error shape reused (cited, not consolidated — a different config domain).
- The `re.IGNORECASE` uniform compile flag is the same one applied to every literal pattern in this module; the loader must apply it identically so the loaded pattern's `.pattern`/`.flags` match the literal by value (object identity is not relied on — see the `compare=False` note above).

## Tests

All cases in `tests/test_backend.py`. This is a **feature** step: every test below is authored with the implementation and must be green before the step is done (green-before-done gate). Round-trip goldens read the real committed `integrations/<backend>/backend.json` (the manifests are this step's input via `depends_on: 2`); resolve the repo root with `Path(__file__).parents[1] / "integrations" / "<backend>"` (mirroring the existing `_CODEX_FIXTURES = Path(__file__).parent / ...` in this test module), since `integrations/` lies outside step 3's declared files. Loader-error cases write crafted manifests under `tmp_path` for hermeticity.

- `test_load_backend_from_dir_claude_round_trips` — `load_backend_from_dir(<repo>/integrations/claude) == CLAUDE_BACKEND`; `loaded.batch_argv("P") == CLAUDE_BACKEND.batch_argv("P")` and same for `streaming_argv` (argv fidelity, since argv is `compare=False`); and for each classification pattern + `auth_pattern`, `loaded.<field>.pattern == CLAUDE_BACKEND.<field>.pattern` and `.flags` match (value fidelity, since patterns are `compare=False` and `re.Pattern` lacks value equality — never depend on whole-object `==` for the pattern fields).
- `test_load_backend_from_dir_codex_round_trips` — `== CODEX_BACKEND`, argv outputs match, per-pattern `.pattern`/`.flags` value-equal (including `auth_pattern`, asserted `is not None` and value-matching codex's literal).
- `test_load_backend_malformed_json_raises` — a `tmp_path` manifest with invalid JSON raises `BackendManifestError` whose message names the manifest file.
- `test_load_backend_unknown_parser_raises` — `parser: "bogus"` raises `BackendManifestError` listing the registered parser names (`claude`, `codex`).
- `test_load_backend_missing_required_field_raises` — dropping `binary` raises `BackendManifestError` naming the missing field.
- `test_load_backend_missing_classification_subkey_raises` — dropping `classification.rate_limit` raises `BackendManifestError` naming `'classification.rate_limit'` (not a raw `TypeError`/`KeyError` from `re.compile(None)`).
- `test_load_backend_null_auth_yields_none` — manifest `classification.auth: null` → loaded `auth_pattern is None`.
- `test_load_backend_string_auth_compiles` — manifest `classification.auth` string → loaded `auth_pattern` compiled and matches a sample.
- `test_parser_registry_keys` — `_PARSER_REGISTRY` maps `"claude"`→`_claude_parse_stream_line` and `"codex"`→`_codex_parse_stream_line` (identity), so the round-trip parser field compares equal.
- `test_claude_backend_model_fields` — `CLAUDE_BACKEND.model_flag == "--model"` and `default_model is None`.
- `test_codex_backend_model_fields` — `CODEX_BACKEND.model_flag == "-m"` and `default_model is None`.
- `test_load_omits_default_model_from_closure` — a `tmp_path` manifest with `default_model` set produces argv with no `[model_flag, model]` pair (the closure emits `[binary, *flags, prompt]`; model injection is step 6's `build_effective_backend`, keeping `argv[:-1]` exactly `[binary, *flags]`).

## Acceptance criteria

- `load_backend_from_dir(<repo>/integrations/claude) == CLAUDE_BACKEND` and `load_backend_from_dir(<repo>/integrations/codex) == CODEX_BACKEND` return `True`.
- `loaded.batch_argv("P")` / `loaded.streaming_argv("P")` equal the corresponding `CLAUDE_BACKEND` / `CODEX_BACKEND` builder outputs element-for-element.
- A manifest with malformed JSON, an unknown `parser`, a missing top-level required field, or a missing required `classification` sub-key (`rate_limit`/`provider_limit`/`context_overflow`/`transient`) raises `BackendManifestError`; the unknown-`parser` message lists `claude` and `codex`.
- `CLAUDE_BACKEND.model_flag == "--model"`, `CODEX_BACKEND.model_flag == "-m"`, both `default_model is None`.
- A manifest with `classification.auth: null` yields `auth_pattern is None`; a string yields a compiled, matching pattern.
- The live run path is unchanged: `CLAUDE_BACKEND.batch_argv("P")` and `streaming_argv("P")` byte-identity tests still pass, and `get_active_backend()` still returns `CLAUDE_BACKEND` by default.
- New test cases in `tests/test_backend.py` pass under `uv run pytest tests/test_backend.py -q`.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — `json.load` and `JSONDecodeError` handling for the manifest read.
- [re — Regular expression operations](https://docs.python.org/3/library/re.html) — `re.compile` + `re.IGNORECASE`; the uniform flag the loader applies so compiled patterns match the cached literals.
- [dataclasses — `field()`](https://docs.python.org/3/library/dataclasses.html#dataclasses.field) — `compare=False` semantics that exclude the argv callables from the generated `__eq__`.
- `docs/CODEX_CLI_CONTRACT.md` — pinned source of codex's `batch_argv`/`streaming_argv` flags and `-m` model flag that the codex manifest (this step's round-trip input) reproduces.

## Deferred

- **`importlib.resources` startup discovery** — iterating `integrations/*/backend.json` and registering each over the in-code fallback seed is step 5; `load_backend_from_dir` here takes a plain directory `path` so step 5 only supplies the resource-resolved path (and the editable-vs-wheel fallback the step-1 packaging note flagged).
- **`--model` flag, model precedence, `extra_*_argv`, effective-backend production** — step 6, the sole model injector; `model_flag` / `default_model` ship inert here and the step-3 closure emits no model pair, so step 6's `build_effective_backend` owns all argv model splicing.
- **`.plan-tool/backends.json` reader (`plan_tool/backend_config.py`)** — step 4; this loader reads only the packaged manifest, not the per-project override.
- **Making `CLAUDE_BACKEND` / `CODEX_BACKEND` the registered fallback seed** — they stay the in-code defaults here; registration ordering (seed-first, manifest-replaces) is step 5.
- **Doc updates** (`README.md`, `RUNBOOK.md`, SKILL.md `--model`) — plan-level landing sweep.
