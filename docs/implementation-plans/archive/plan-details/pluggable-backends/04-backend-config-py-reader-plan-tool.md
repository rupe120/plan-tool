> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add `backend_config.py` reader for `.plan-tool/backends.json` `backends.<name>` overrides (model + extra argv only)

## Summary

Add `plan_tool/backend_config.py`: a stdlib-only leaf that reads the per-project `.plan-tool/backends.json` and parses **only** its `backends.<name>` block into a typed `BackendOverride` (`model`, `extra_batch_argv`, `extra_streaming_argv`). Modeled field-for-field on `plan_tool/jira_config.py` — `BackendConfigError` mirrors `JiraConfigError`, `load_backend_overrides(repo_root)` mirrors `load_jira_config(repo_root)`, and a missing file returns an empty map (today's behavior). The load-bearing decision: `BackendOverride` carries **no** `binary`/`parser`/`classification` fields, so those keys structurally cannot take effect from a project file — the per-project surface is deliberately tuning-only. The reader also **tolerates** the sibling [`BACKEND_SELECTION.md`](../../../design-plans/BACKEND_SELECTION.md)'s `default`/`aspects`/`failover` keys (ignores them, never errors). On green, `load_backend_overrides(tmp)` returns `{}` for an absent file, a well-formed `backends` block decodes to `BackendOverride` objects keyed by name, and malformed JSON / wrong-typed fields raise `BackendConfigError` naming the file.

## Table of Contents

- [Why](#why) — the per-project tuning surface that has no reader today
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files, zero edits
- [Implementation](#implementation) — the dataclass, the typed error, the loader, and the shared-file tolerance contract
- [Tests](#tests) — round-trip, validation errors, absent-file, key-tolerance, inert binary/parser
- [Acceptance criteria](#acceptance-criteria) — observable load / error / scoping checks
- [References](#references) — json stdlib + the shared-config design doc
- [Deferred](#deferred) — precedence/argv-assembly (step 6), registry-name validation, default/aspects/failover reading

## Why

- **No per-project tuning surface exists.** `plan_tool/backend.py`'s argv builders and model behavior are code-literal: `_claude_streaming_argv` hardcodes `--permission-mode acceptEdits`, codex hardcodes `_CODEX_COMMON_FLAGS`, and there is no `default_model` plumbing. The plan's whole point is letting a driven project tune `model` and append extra argv flags per backend without editing source.
- **This step provides only the reader.** It produces `BackendOverride` objects from `.plan-tool/backends.json`; step 6 (`depends_on: 3, 4, 5`) consumes them to assemble the effective argv (`[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]`) and resolve model precedence. Landing the reader first keeps step 6 pure wiring.
- **The config file is shared.** `.plan-tool/backends.json` is co-owned with the selection design: this plan reads the `backends.<name>` block; `BACKEND_SELECTION.md` reads `default`/`aspects`/`failover`. The reader must parse its own block and leave the others untouched so the two readers coexist on one file.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/backend_config.py` — the module: `BackendConfigError`, `BackendOverride`, `BACKENDS_CONFIG_SUBPATH`, `default_backends_config_path`, `load_backend_overrides`, and a `backend_override_for` convenience lookup.
  - `tests/test_backend_config.py` — the unit suite enumerated under [Tests](#tests).
- **Existing files (edits only):** none.

## Implementation

### `plan_tool/backend_config.py`

Build the module as a parallel of `plan_tool/jira_config.py` — same import discipline (stdlib only: `json`, `dataclasses`, `pathlib`, `typing`), same error-message shape, same `repo_root`-parameterized loader. Keep it a **leaf**: do not import `plan_tool/backend.py`, `locator`, or any orchestrator, so it stays below the backend seam in the import graph (consistent with `backend.py`'s leaf constraint).

- **`BACKENDS_CONFIG_SUBPATH`** — `Path(".plan-tool") / "backends.json"`, mirroring `plan_tool/locator.py:DEFAULT_MANIFEST_SUBPATH` (`.plan-tool/plans.json`).

- **`default_backends_config_path(repo_root: Path) -> Path`** — return `(repo_root / BACKENDS_CONFIG_SUBPATH).resolve()`, mirroring `plan_tool/jira_config.py:default_config_path`. Take `repo_root` as a parameter (do **not** call `locator.find_repo_root_from_cwd` inside the module) — keeps the loader hermetic and lets tests point it at `tmp_path`.

- **`class BackendConfigError(Exception)`** — typed config-load error mirroring `plan_tool/jira_config.py:JiraConfigError`. Raise it (never bare `ValueError`/`KeyError`) for malformed JSON, a non-object top level, a non-object `backends` block, a non-object per-backend entry, or a wrong-typed field. Message names the offending file and key, e.g. the invalid-JSON shape `f"invalid JSON in {mf}: {exc}"` off `json.JSONDecodeError`.

- **`@dataclass(frozen=True) class BackendOverride`** — the parsed per-backend tuning record. Fields:
  - `model: Optional[str] = None` — the project-file model tier (step 6 slots it into the `--model` > project > manifest-default precedence chain).
  - `extra_batch_argv: list[str] = field(default_factory=list)` — flags appended after manifest batch flags, before the prompt.
  - `extra_streaming_argv: list[str] = field(default_factory=list)` — same for the streaming argv.
  - **No `binary`/`parser`/`classification` fields.** Their absence is the enforcement: a project file structurally cannot swap the binary, the parser, or the regexes. This is the acceptance criterion "a `backends.<name>` override block cannot change the backend's binary or parser." (Mutable `list[str]` defaults on a frozen dataclass are fine via `field(default_factory=list)` — the freeze blocks rebinding the attribute, not mutating the list.)

- **`load_backend_overrides(repo_root: Path, *, path: Optional[Path] = None) -> dict[str, BackendOverride]`** — the loader, structured like `load_jira_config`:
  - **Resolve** `mf = path or default_backends_config_path(repo_root)`.
  - **Absent file → return `{}`** — the legitimate "no per-project tuning" state (today's behavior). Do not raise. Mirrors `load_jira_config`'s missing-file → empty-`JiraConfig` branch.
  - **Parse** with `json.loads(mf.read_text(encoding="utf-8"))`, wrapping `json.JSONDecodeError` in `BackendConfigError(f"invalid JSON in {mf}: {exc}")`.
  - **Top level must be a JSON object** → else `BackendConfigError` naming the actual type (mirror `load_jira_config`'s top-level check).
  - **Read only `data.get("backends", {})`.** Absent `backends` key → return `{}`. Present but not a dict → `BackendConfigError`. **Tolerate sibling keys**: `default`, `aspects`, `failover` may be present — never inspect or reject them (they belong to `BACKEND_SELECTION.md`).
  - **Per-backend entry**: for each `name -> block` in the `backends` map:
    - `name` must be a non-empty string; `block` must be a dict → else `BackendConfigError`.
    - `model` = `block.get("model")`: accept `None` (omit) or a non-empty string; reject non-string / empty-or-whitespace string with `BackendConfigError` naming the backend.
    - `extra_batch_argv` / `extra_streaming_argv` = `block.get(..., [])`: each must be a list whose every element is a string; reject a non-list or a non-string element with `BackendConfigError` naming the backend and field.
    - **Other keys in the block are ignored** (inert) — `binary`, `parser`, `classification`, or anything else. Do not error on them; `BackendOverride` simply has nowhere to put them, which is the scoping guarantee.
  - **Return** `{name: BackendOverride(...)}`.

- **`backend_override_for(name: str, repo_root: Path, *, path: Optional[Path] = None) -> Optional[BackendOverride]`** — thin convenience for step 6's selection-time lookup: `return load_backend_overrides(repo_root, path=path).get(name)`. Returns `None` when the file is absent or has no block for `name` — the "no override, use manifest defaults" signal.

### Shared-file design decision (load-bearing)

- **Read-tolerant, write-nothing.** This step ships **no writer** for `.plan-tool/backends.json` — v1 is hand-edit-only (plan Deferred: "config wizard … hand-edit-only for v1"). A future writer must round-trip the sibling's `default`/`aspects`/`failover` keys untouched; flag that as the writer's contract when it lands, not here.
- **No registry coupling.** Do not validate `name` against `plan_tool/backend.py`'s registered backends here — that would import the seam and couple config-load to registry state (which only fills after step 5's discovery). Overrides for unknown names are returned verbatim; step 6 looks up by the active backend's name and ignores the rest. Registry-name validation is the selection plan's concern (see [Deferred](#deferred)).

## Tests

All tests live in `tests/test_backend_config.py`, mirror `tests/test_jira_config.py`'s structure (hermetic `tmp_path`, write a JSON file then load), and are **unit** (unmarked, no `main([...])`, no backend spawn). This is a **feature** step: author every case **with** the implementation; all must be green before the step is done.

- `test_missing_file_returns_empty` — `load_backend_overrides(tmp_path)` returns `{}` when no `.plan-tool/backends.json` exists (the unconfigured-project state).
- `test_absent_backends_key_returns_empty` — a file with only `default`/`aspects` and no `backends` key returns `{}` (covers the absent-block path and sibling-key presence together).
- `test_round_trip_model_and_argv` — a `backends` block with `model` + both `extra_*_argv` lists decodes to a `BackendOverride` carrying those exact values.
- `test_model_null_is_none` — `"model": null` (and an omitted `model`) both yield `BackendOverride.model is None`.
- `test_extra_argv_default_empty` — a block setting only `model` yields empty `extra_batch_argv` / `extra_streaming_argv` lists.
- `test_tolerates_sibling_keys` — a file carrying `default`, `aspects`, and `failover` alongside `backends` loads without error and returns only the `backends` overrides.
- `test_binary_and_parser_keys_ignored` — a block with `binary`/`parser`/`classification` keys loads without error and the resulting `BackendOverride` exposes no such fields (only `model` + extra argv) — pins the scoping guarantee.
- `test_backend_override_for_hit_and_miss` — `backend_override_for("codex", tmp)` returns the codex override; `backend_override_for("nope", tmp)` and the absent-file case return `None`.
- `test_malformed_json_raises` — a non-JSON file raises `BackendConfigError` whose message names the file.
- `test_top_level_not_object_raises` — a top-level JSON array raises `BackendConfigError`.
- `test_backends_not_object_raises` — `"backends": []` raises `BackendConfigError`.
- `test_block_not_object_raises` — `"backends": {"codex": "gpt-5"}` raises `BackendConfigError` naming the backend.
- `test_model_wrong_type_raises` — `"model": 7` raises `BackendConfigError`; `"model": ""` (empty/whitespace) likewise.
- `test_extra_argv_wrong_type_raises` — `extra_streaming_argv` set to a string, and a list containing a non-string element, each raise `BackendConfigError` naming the field.

## Acceptance criteria

- `load_backend_overrides(tmp_path)` returns `{}` when no `.plan-tool/backends.json` is present.
- A well-formed `backends.<name>` block decodes to a `BackendOverride` with the exact `model` (or `None`), `extra_batch_argv`, and `extra_streaming_argv` from the file.
- `BackendOverride` has no `binary`, `parser`, or `classification` attribute; a file setting those keys loads without error and they take no effect.
- A file carrying `default` / `aspects` / `failover` keys loads successfully and they are ignored.
- Malformed JSON, a non-object top level, a non-object `backends` block, a non-object per-backend entry, or a wrong-typed `model`/`extra_*_argv` raises `BackendConfigError` whose message names the offending file (and backend/field where applicable).
- `backend_override_for(name, repo_root)` returns the matching `BackendOverride` or `None` (absent file / no block for `name`).
- `plan_tool/backend_config.py` imports only stdlib — no import of `plan_tool/backend.py`, `locator`, or any orchestrator.
- `uv run pytest tests/test_backend_config.py -q` passes.

## References

- [json — JSON encoder and decoder (Python Standard Library)](https://docs.python.org/3/library/json.html) — `json.loads` and `JSONDecodeError` handling for parsing and validating `.plan-tool/backends.json`.
- [`docs/design-plans/BACKEND_SELECTION.md`](../../../design-plans/BACKEND_SELECTION.md) — the sibling design that co-owns `.plan-tool/backends.json` (`default`/`aspects`/`failover`); read its `### 3. Shared per-project config .plan-tool/backends.json` block for the keys this reader must tolerate and the `BackendConfigError` naming convention they share.

## Deferred

- **Model precedence + argv assembly** — `--model` flag > project `model` > manifest `default_model` > omit, and `[binary, *manifest_argv, *project_extra_argv, *model_pair, prompt]` assembly, belong to step 6 (`depends_on: 3, 4, 5`). This step only surfaces the project-file tier as `BackendOverride.model` / `extra_*_argv`.
- **Registry-name validation** — warning on a `backends.<name>` whose `name` is not a registered backend (with the registered-names list) requires the post-discovery registry, so it is done at selection in step 6, not here; this reader returns overrides for unknown names verbatim.
- **Reading `default` / `aspects` / `failover`** — owned by `BACKEND_SELECTION.md`; this reader tolerates but never consumes them. A future consolidation that has `backend_config.py` own the whole file (per the design doc) must extend, not fragment, this module.
- **Config writer / `backends config` wizard** — v1 is hand-edit-only (plan Deferred); any future writer must round-trip the sibling keys untouched.
