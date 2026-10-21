> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Startup discovery: register `integrations/*/backend.json` manifests over the in-code seed

## Summary

Add `discover_and_register_backends()` plus a `_packaged_integrations_dir()` resolver to `plan_tool/backend.py`, auto-invoked once at module import after the seed registration (`register_backend(CODEX_BACKEND)`). The resolver locates the bundled `integrations/` tree two ways — `importlib.resources.files("plan_tool") / "integrations"` (built wheel, where step 1's force-include lands it) and `Path(__file__).resolve().parent.parent / "integrations"` (editable / source checkout, where the force-include does not exist) — then iterates each `integrations/<name>/backend.json`, calls step 3's `load_backend_from_dir`, and `register_backend`s the result **over** the in-code fallback seed. The load-bearing decision: register-over (manifests are authoritative — they externalize argv flags), per-directory `BackendManifestError` isolation (a broken manifest leaves that name's seed intact), and leaving `_active_backend` (the module default) untouched so `get_active_backend()` still defaults to `CLAUDE_BACKEND`. On green, a dropped-in `integrations/<new>/backend.json` is resolvable via `resolve_backend("<new>")` / `registered_binaries()` with zero edit to `backend.py`, while claude/codex stay byte-faithful because their committed manifests reproduce the literals.

## Table of Contents

- [Why](#why) — the discovery wiring that connects the loader to a working registry
- [Files (creates vs edits)](#files-creates-vs-edits) — two edits, zero new files
- [Implementation](#implementation) — the resolver, the discovery loop, register-over semantics, the auto-call
- [Tests](#tests) — discovery cases plus the four identity→equality updates replacement forces
- [Acceptance criteria](#acceptance-criteria) — observable resolve / register / fallback checks
- [References](#references) — importlib.resources + the loader source of truth
- [Deferred](#deferred) — `--backend` choices, per-project overrides, zip-safe extraction

## Why

`plan_tool/backend.py` has the loader (`load_backend_from_dir`, step 3) and the manifests (`integrations/<backend>/backend.json`, step 2), but **nothing calls the loader** — the registry is still seeded only from the in-code `CLAUDE_BACKEND` / `CODEX_BACKEND` literals, so the manifests are dead data. Until discovery runs, externalizing a flag (the plan's core goal — moving `--permission-mode acceptEdits` and `_CODEX_COMMON_FLAGS` out of code into JSON) has no effect on the run path. This step wires the loader to startup: iterate the packaged `integrations/` tree and register each manifest-built `CliBackend` over the seed, so `resolve_backend` / `set_active_backend` (and through them `cli.main`'s selection at `plan_tool/cli/app.py:main`) route through the manifest-loaded descriptors. The seed survives a missing or malformed manifest, so a fresh install with a broken JSON still drives a working backend.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/backend.py` —
    - Add `import importlib.resources` and `import warnings` (both stdlib — preserve the leaf import topology; `Path` is already imported).
    - Add `_packaged_integrations_dir() -> Optional[Path]` (dual-mode wheel/source resolver).
    - Add `discover_and_register_backends(integrations_root: Optional[Path] = None) -> None` (the iterate-load-register loop).
    - Add the bottom-of-module auto-call `discover_and_register_backends()` immediately after `register_backend(CODEX_BACKEND)`.
    - Extend the module docstring's "Public surface" list with `discover_and_register_backends`.
  - `tests/test_backend.py` — add the discovery cases (enumerated under [Tests](#tests)) and update the four registry-**identity** assertions to value-equality that replacement semantics invalidate.

## Implementation

### `plan_tool/backend.py`

**Preflight (depends on step 3).** Before writing the discovery loop, confirm step 3's exported `load_backend_from_dir(path: Path) -> CliBackend` signature/arity and the `BackendManifestError` / `_PARSER_REGISTRY` symbols exist at HEAD (step 3 is `depends_on` for this step); this loop consumes them directly, so adjust the call site if step 3 landed a different signature.

**`_packaged_integrations_dir() -> Optional[Path]`** — resolve the bundled `integrations/` directory, dual-mode:

- **Wheel candidate (force-included under the package anchor).** `Path(str(importlib.resources.files("plan_tool"))) / "integrations"`. Step 1's `[tool.hatch.build.targets.wheel.force-include]` maps repo-root `integrations` → `plan_tool/integrations`, so from a built wheel the manifests sit *under* the importable `plan_tool` package — exactly where `importlib.resources.files("plan_tool")` traverses. Return it if `.is_dir()`.
- **Source / editable candidate.** `Path(__file__).resolve().parent.parent / "integrations"`. `backend.py` lives at `plan_tool/backend.py`, so `parent.parent` is the repo root and `/ "integrations"` is the repo-root tree. Under `uv tool install --editable .` (the documented dev-loop install) the force-include never runs, so `plan_tool/integrations/` is absent on disk and the real files stay at repo-root `integrations/`. Return it if `.is_dir()`.
- **Neither exists** → return `None` (discovery becomes a no-op; the seeds stand).
- **Anchor on `__file__`, not `locator.find_repo_root_from_cwd`.** The step-1 Deferred note suggested the locator for the editable fallback, but `find_repo_root_from_cwd` resolves the **driven project's** root (cwd-relative) — and plan-tool installed editable is normally driving a *different* repo, whose root has no `integrations/`. `Path(__file__)` anchors on plan-tool's own installed source regardless of cwd, and keeps `backend.py` stdlib-only (no `locator` import, no leaf-topology violation — mirrors the `jira_config.py` / `backend_config.py` leaf discipline).

**`discover_and_register_backends(integrations_root: Optional[Path] = None) -> None`** — the iterate-load-register loop:

- **Resolve the root** — `integrations_root or _packaged_integrations_dir()`. The parameter exists for hermetic tests (point discovery at a `tmp_path` tree); production passes nothing.
- **No-op on a missing root** — `if root is None or not root.is_dir(): return`.
- **Iterate child directories in sorted order** — `for child in sorted(root.iterdir())`; skip any whose `child / "backend.json"` is not a file (e.g. a `SKILL.md`-only directory).
- **Load and register, warning-and-skipping per-directory failures:**
  ```
  try:
      register_backend(load_backend_from_dir(child))
  except (BackendManifestError, re.error, TypeError, ValueError) as exc:
      warnings.warn(
          f"plan-tool: skipping backend manifest in {child}: {exc}",
          stacklevel=2,
      )
      continue
  ```
  A malformed / unknown-`parser` / missing-field manifest raises step 3's `BackendManifestError`, but a malformed `classification` regex surfaces as `re.error` and a wrong-typed field as `TypeError`/`ValueError` — step 3's `load_backend_from_dir` only wraps the JSON/parser/missing-field cases in `BackendManifestError`, so the broader `except` catches every manifest defect. The `except` **emits a warning naming the offending directory and the load error, then skips that directory** — never silently — parallel to step 4's unknown-override-key warning; discovery never swallows a defect. The warn-and-skip is **per directory**, which is the fallback-seed guarantee: `CLAUDE_BACKEND` / `CODEX_BACKEND` (registered before this runs) survive a broken same-name manifest, and one bad directory never aborts discovery (and, since discovery is auto-called at import, never aborts `import plan_tool.backend`) of the rest. (`re` is imported at module top for the classification regex compilation.)
- **Reuse `register_backend`** (the existing `_REGISTRY[backend.name] = backend` mutation) rather than touching `_REGISTRY` directly — keeps the single registry-write seam.

**Register-over (replacement) semantics — the load-bearing choice.**

- Discovery always calls `register_backend`, which overwrites the same-name seed; always-register makes the manifest authoritative.
- This is mandatory for flag externalization: `CliBackend.__eq__` excludes `batch_argv` / `streaming_argv` and the classification patterns (`field(compare=False)`, step 3), so a manifest that changes only a flag is `==` the seed by the dataclass comparison.
- Any "skip if `loaded == seed`" shortcut would therefore silently ignore flag edits to `integrations/claude/backend.json` — defeating the whole point.
- Because the committed claude/codex manifests reproduce the literals (step 3's round-trip golden), the replacement is value-equal at the run path; only the registry-stored *object identity* changes.

**Leave `_active_backend` untouched.**

- `register_backend` mutates only `_REGISTRY`, never `_active_backend`, so `get_active_backend()` still returns the literal `CLAUDE_BACKEND` by default (the pre-selection value).
- `plan_tool/cli/app.py:main` always calls `set_active_backend(resolve_backend(name))` before dispatch, so the live run path picks up the manifest-loaded descriptor from `_REGISTRY`; the literal default only matters to a library caller that never selects.
- This keeps `test_get_active_backend_defaults_to_claude` (`is CLAUDE_BACKEND`) green without a refresh branch.

**Auto-call at import.**

- Append `discover_and_register_backends()` at the very bottom of the module, **after** `register_backend(CODEX_BACKEND)` and after `load_backend_from_dir` is defined.
- Ordering encodes the plan's seed-first / manifest-over flow: literals register first (fallback), then manifests layer on.
- The step's `files:` list is `backend.py` + its test only — wiring the call into `cli.main` would pull `app.py` into scope, so the self-contained import-time call is the in-scope mechanism.
- The import-time read targets the repo's own committed manifests (deterministic), and the function's injectable `integrations_root` keeps the discovery *tests* hermetic against `tmp_path`.

**Foundational logic:** discover manifest directories under the bundled `integrations/` tree and register each `CliBackend` over the in-code seed. Parallel locations the audit surfaces:

- **The seed itself** — `_REGISTRY = {CLAUDE_BACKEND.name: CLAUDE_BACKEND}` and `register_backend(CODEX_BACKEND)` are the fallback this discovery layers over; discovery does not replace those lines, it runs after them. The `registered_binaries()` consumer (the conftest subprocess guard) reads `_REGISTRY` unchanged and auto-blocks any discovered backend's binary — no guard edit.
- **`plan_tool/lessons.py:discover_lessons_files`** is a sibling "walk a tree and collect files" routine, but a different domain (per-project lessons, not packaged manifests) — cited as precedent, not consolidated.
- **`importlib.resources` package-resource access** appears only here in `plan_tool/`; no existing helper to reuse or duplicate.

## Tests

All cases in `tests/test_backend.py`. This is a **feature** step: every new test is authored with the implementation and must be green before the step is done (green-before-done gate). Discovery cases run under the existing `_restore_backend_state` fixture (snapshots + restores `_REGISTRY` and the active backend) and build crafted `integrations/<name>/backend.json` trees under `tmp_path` for hermeticity; valid crafted manifests reuse `parser: "claude"` so they resolve through `_PARSER_REGISTRY` without a real binary.

New discovery cases:

- `test_discover_registers_new_backend` — a `tmp_path` integrations tree with a valid `fake/backend.json` (binary `"fakebin"`) → after `discover_and_register_backends(tmp_root)`, `resolve_backend("fake").binary == "fakebin"` and `"fakebin" in registered_binaries()`.
- `test_discover_replaces_seed_when_manifest_differs` — a crafted `claude/backend.json` with `binary: "claude-custom"` → after discovery, `resolve_backend("claude").binary == "claude-custom"` (register-over the seed; `binary` is a compared field).
- `test_discover_broken_manifest_keeps_seed` — a crafted `claude/backend.json` with invalid JSON → discovery does **not** raise, emits a warning (`pytest.warns(UserWarning)`) whose message names the offending directory, and `resolve_backend("claude") == CLAUDE_BACKEND` (the seed survives; per-directory isolation). Value-equality, not `is`: import-time register-over already replaced the registry object with the committed manifest's, so assert `==` (or capture `before = resolve_backend("claude")` and assert `is before`).
- `test_discover_regex_malformed_manifest_keeps_seed` — a crafted `claude/backend.json` valid except for an unbalanced `classification` regex (e.g. `"rate_limit": "("`) → discovery does **not** raise (the broadened `except` catches `re.error`), emits a warning naming the directory, and `resolve_backend("claude") == CLAUDE_BACKEND` (seed survives the non-`BackendManifestError` defect).
- `test_discover_skips_directory_without_backend_json` — an integrations tree whose `claude/` holds only `SKILL.md` → no raise, registry unchanged.
- `test_discover_missing_root_is_noop` — `discover_and_register_backends(tmp_path / "nope")` → no raise, `registered_binaries() == {"claude", "codex"}`.
- `test_discover_iterates_multiple_dirs` — two valid dirs (`alpha/`, `beta/`) → both resolvable after one call (proves the loop, not a single-dir read).
- `test_packaged_integrations_dir_finds_real_manifests` — `_packaged_integrations_dir()` returns a directory containing `claude/backend.json` in the dev checkout (exercises the `__file__`-relative source candidate).
- `test_import_time_discovery_keeps_claude_runnable` — at rest (post-import), `resolve_backend("claude")` returns a `CliBackend` whose `batch_argv("P")` equals `CLAUDE_BACKEND.batch_argv("P")` (the committed manifest reproduces the literal, so the run path is byte-identical after import-time discovery).

Identity→equality updates forced by replacement (these step-3 / pre-step-3 cases assert registry **object identity**, which import-time register-over invalidates):

- `test_resolve_backend_claude` — change `resolve_backend("claude") is CLAUDE_BACKEND` → `== CLAUDE_BACKEND`.
- `test_resolve_backend_codex` — change `resolve_backend("codex") is CODEX_BACKEND` → `== CODEX_BACKEND`.
- `test_codex_backend_registered` — change `backend._REGISTRY["codex"] is CODEX_BACKEND` → `== CODEX_BACKEND` (keep the `"codex" in registered_binaries()` and `CODEX_BACKEND.name == "codex"` assertions).
- `test_set_active_backend_round_trips` — change the trailing `get_active_backend() is CLAUDE_BACKEND` (after `set_active_backend("claude")`) → `== CLAUDE_BACKEND`. The mid-test `is fake` identity assertion stays (a registered throwaway, not a seed-replaced name).

Untouched / confirm-green: `test_get_active_backend_defaults_to_claude` (`is CLAUDE_BACKEND` — discovery never touches `_active_backend`), `test_claude_batch_argv_byte_identical` / `test_claude_streaming_argv_byte_identical` / `test_codex_*argv*` (call the literals, not the registry), `test_registered_binaries_contains_claude` (`{"claude", "codex"}` — names unchanged), and the `_codex_active` classify cases (set active to the literal `CODEX_BACKEND` directly).

## Acceptance criteria

- After import, a dropped-in `integrations/<new>/backend.json` is reachable: `resolve_backend("<new>")` returns its `CliBackend` and `registered_binaries()` includes its binary — with no edit to `plan_tool/backend.py`.
- `discover_and_register_backends(<tmp tree>)` registers every valid `<name>/backend.json` and raises nothing for a malformed one (that name's seed, if any, is retained).
- A malformed `claude/backend.json` leaves `resolve_backend("claude") == CLAUDE_BACKEND` (seed fallback; value-equal, since import-time register-over already replaced the registry object) and emits a warning naming the offending directory and the load error — never a silent skip.
- `_packaged_integrations_dir()` returns an existing directory containing `claude/backend.json` from the source checkout.
- `get_active_backend()` still returns `CLAUDE_BACKEND` by default; the live run path for claude/codex is byte-identical (committed manifests reproduce the literals).
- `registered_binaries() == {"claude", "codex"}` at rest; the conftest subprocess guard blocks a discovery-registered binary with no guard edit.
- New and updated cases pass under `uv run pytest tests/test_backend.py -q`, and the full `uv run pytest -m "not integration" tests/ -q` stays green.

## References

- [importlib.resources — Python Standard Library](https://docs.python.org/3/library/importlib.resources.html) — `files()` package-anchor traversal that locates the force-included `plan_tool/integrations` tree from an installed wheel.
- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — decode-error surface behind `load_backend_from_dir`'s `BackendManifestError` (the per-directory failure this loop isolates).
- `docs/implementation-plans/plan-details/pluggable-backends/03-load-backend-dir-parser-registry.md` — `load_backend_from_dir` signature, `BackendManifestError`, and the `compare=False` equality design this step consumes.
- `docs/implementation-plans/plan-details/pluggable-backends/01-ship-integrations-wheel-hatch-force.md` — the force-include destination (`plan_tool/integrations`) and the editable-vs-wheel asymmetry the dual-mode resolver answers.

## Deferred

- **`--backend` flag choices stay hardcoded** — `plan_tool/cli/parser.py` pins `choices=("claude", "codex")`, so a discovered third backend is selectable via `PLAN_TOOL_BACKEND` (routed through `resolve_backend`, not choices-constrained) but not yet via the `--backend` flag. Dynamic choices belong to step 6 / the selection plan.
- **Per-project `backends.<name>` overrides** — applying `.plan-tool/backends.json` model + extra argv on top of the discovered descriptor is step 6 (`depends_on: 3, 4, 5`); this step registers the bare manifest backend only.
- **Refreshing `_active_backend` after discovery** — left as the literal default; manifest-edited flags reach the run path only after `set_active_backend` (always called by `cli.main`). A library caller that skips selection sees the literal's flags — acceptable, since every CLI path selects.
- **Wheel-positive branch coverage** — the wheel candidate of `_packaged_integrations_dir()` (`importlib.resources.files("plan_tool") / "integrations"`) has no step-5 test; `test_packaged_integrations_dir_finds_real_manifests` only exercises the source-candidate fallthrough (the wheel candidate is absent in an editable/source checkout). The "resolves `plan_tool/integrations` from a built wheel" path is verified by step 1's `uv build`, not a unit test — acceptable given wheel-build cost.
- **Zip-safe resource extraction** — plan-tool installs unzipped (uv/pip unpack the wheel; editable uses source), so a direct `Path` from `importlib.resources.files` is valid; wrap with `importlib.resources.as_file` only if a zipimport install is ever supported.
- **Doc updates** (`README.md` `## Backends` / layout tree, `RUNBOOK.md` discovery recipe) — plan-level landing sweep.
