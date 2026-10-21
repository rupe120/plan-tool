> **Auto-archived**: this plan was swept on 2026-06-11 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Ship `integrations/` in the wheel via hatch force-include

## Summary

Add a `[tool.hatch.build.targets.wheel.force-include]` table to `pyproject.toml` mapping the repo-root `integrations/` directory into the wheel at `plan_tool/integrations/`, so the bundled `integrations/<backend>/` tree becomes a package-discoverable resource without physically moving the source. The load-bearing decision is the **destination path**: nesting under the `plan_tool` package anchor (not the wheel root) is what lets step 5's `importlib.resources.files("plan_tool") / "integrations"` resolver locate `backend.json` manifests from an installed wheel. This is a packaging-only change — no Python touched, behavior byte-identical at runtime today (nothing reads `integrations/` yet). On green, a built wheel contains `plan_tool/integrations/claude/SKILL.md` and `importlib.resources` can read it.

## Table of Contents

- [Why](#why) — the packaging risk this step settles before any loader code lands
- [Files (creates vs edits)](#files-creates-vs-edits) — single `pyproject.toml` edit
- [Implementation](#implementation) — the force-include table, destination choice, and editable-install caveat
- [Tests](#tests) — build-and-inspect the wheel + `importlib.resources` smoke check
- [Acceptance criteria](#acceptance-criteria) — observable wheel-contents and resolver checks
- [References](#references) — hatchling build config + `importlib.resources`
- [Deferred](#deferred) — the resolver, editable-mode fallback, and doc/layout updates left to later steps

## Why

The plan's #1 structural risk: `integrations/` lives at repo root, **outside** the `plan_tool/` package, so `packages = ["plan_tool"]` in `pyproject.toml` excludes it from the wheel entirely. Today that is harmless — `integrations/claude/SKILL.md` is read by zero Python (a manual symlink workflow, `README.md:182`). But steps 3–5 turn `integrations/<backend>/backend.json` into a runtime-loaded manifest discovered via `importlib.resources`. If packaging is not settled first, that discovery silently finds nothing from an `uv tool install` / installed wheel, and every later step builds on a resolver that only works from a source checkout. This step proves the files ship and are resource-accessible **before** any loader code depends on it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `pyproject.toml` — add a `[tool.hatch.build.targets.wheel.force-include]` table mapping `"integrations"` → `"plan_tool/integrations"`. Leave the existing `[tool.hatch.build.targets.wheel]` `packages = ["plan_tool"]` line unchanged.

## Implementation

### `pyproject.toml`

- **Add the force-include table** immediately after the existing `[tool.hatch.build.targets.wheel]` block:
  ```toml
  [tool.hatch.build.targets.wheel.force-include]
  "integrations" = "plan_tool/integrations"
  ```
  - **Key** = source path relative to the project root (`integrations/`, the directory holding `claude/SKILL.md` today and `claude/backend.json` + `codex/` after step 2).
  - **Value** = destination path inside the built wheel. `plan_tool/integrations` places the tree under the `plan_tool` package so it is reachable as package data.

- **Destination must be `plan_tool/integrations`, not `integrations`.** The whole point is step 5's resolver. `importlib.resources` traverses *packages*: `importlib.resources.files("plan_tool")` returns a `Traversable` for the installed `plan_tool` package, and `.joinpath("integrations")` reaches the bundled tree only when it physically sits under `plan_tool/` in the wheel. Mapping to the wheel root (`"integrations" = "integrations"`) ships the files but leaves them outside any package, unreachable by the resolver — the silent-failure mode this step exists to prevent.

- **Do not move the source tree.** The step title fixes the mechanism as *force-include*, not a `git mv integrations plan_tool/integrations`. Keeping the source at repo root preserves:
  - the symlink install instruction (`README.md:182`: `ln -s /path/to/plan-tool/integrations/claude/SKILL.md …`),
  - the layout tree (`README.md:76`, `integrations/` shown at top level),
  - the human-facing convention that `integrations/<backend>/` is a sibling of `plan_tool/`, per the plan's Architecture section.
  Force-include is a build-time remap: source stays at `integrations/`, the wheel sees it at `plan_tool/integrations/`.

- **No overlap conflict with `packages = ["plan_tool"]`.** hatchling layers force-include entries on top of the package selection; `plan_tool/` (the Python sources) and the force-included `plan_tool/integrations/` (data) coexist in the wheel. No `__init__.py` is required inside `integrations/` — `importlib.resources` traverses directory resources without one.

- **Editable-install caveat (load-bearing for step 5, not fixed here).** `force-include` applies to the *built wheel only*. `uv tool install --editable .` / `pip install -e .` expose the live source tree via a `.pth`/path hook, so no `plan_tool/integrations/` directory exists on disk — the real files stay at repo-root `integrations/`. Therefore `files("plan_tool") / "integrations"` resolves to a non-existent `<repo>/plan_tool/integrations` in editable mode. Step 5's resolver must fall back to the package-source `integrations/` (resolved relative to the package via `Path(__file__).parent.parent`, not the driven project's repo root — which has no `integrations/`) when the packaged path is absent. This step only guarantees the **installed-wheel** path; the dual-mode resolution is step 5's responsibility (see Deferred).

## Tests

Non-code step — no unit tests. Verify the build artifact and resource accessibility:

- **Wheel contains the tree** — `uv build` (or `uv run python -m build --wheel`), then `unzip -l dist/plan_tool-0.1.0-*.whl | grep integrations` lists `plan_tool/integrations/claude/SKILL.md`. After step 2 lands, the same listing also shows `plan_tool/integrations/claude/backend.json`, `plan_tool/integrations/codex/backend.json`, `plan_tool/integrations/codex/SKILL.md`.
- **Resource is readable from the installed wheel** — install the built wheel into a throwaway venv and run `python -c "from importlib.resources import files; print((files('plan_tool') / 'integrations' / 'claude' / 'SKILL.md').read_text()[:40])"`; it prints the SKILL.md head rather than raising `FileNotFoundError`/`ModuleNotFoundError`.
- **sdist still carries the source** — `tar tzf dist/plan_tool-0.1.0.tar.gz | grep integrations` shows `integrations/claude/SKILL.md` at its repo-root path (the sdist includes VCS-tracked files regardless of the wheel-target remap).
- **No regression** — `uv run pytest -m "not integration" tests/ -q` stays green; this edit changes no importable code, so the suite is unaffected.
- **TOML parses** — `uv run python -c "import tomllib, pathlib; tomllib.loads(pathlib.Path('pyproject.toml').read_text())"` exits 0 (the new table is well-formed).

## Acceptance criteria

- `pyproject.toml` contains a `[tool.hatch.build.targets.wheel.force-include]` table with `"integrations" = "plan_tool/integrations"`.
- A freshly built wheel (`uv build`) lists `plan_tool/integrations/claude/SKILL.md` in `unzip -l dist/*.whl`.
- From an environment with that wheel installed, `importlib.resources.files("plan_tool").joinpath("integrations", "claude", "SKILL.md").is_file()` returns `True`.
- The existing `[tool.hatch.build.targets.wheel]` `packages = ["plan_tool"]` line is unchanged, and `uv run pytest -m "not integration" tests/ -q` passes.
- The repo-root `integrations/` directory is not moved or deleted (source path still `integrations/claude/SKILL.md`).

## References

- [Hatch build configuration — `force-include`](https://hatch.pypa.io/latest/config/build/#forced-inclusion) — Exact semantics of the `force-include` table (source-path key → artifact-path value) and that it is per build-target, used to remap repo-root `integrations/` into the wheel under `plan_tool/`.
- [importlib.resources — Python Standard Library](https://docs.python.org/3/library/importlib.resources.html) — The `files()`/`Traversable` API step 5 uses to read the bundled manifests; this step's destination choice exists to make that API resolve from an installed wheel.
- [setuptools — Data Files Support](https://setuptools.pypa.io/en/latest/userguide/datafiles.html) — Cross-reference for the package-data concept the plan's packaging risk cites; informs why the destination must live under a package, even though the build backend here is hatchling not setuptools.

## Deferred

- **The `importlib.resources` discovery resolver** — iterating `plan_tool/integrations/*/backend.json` and registering each backend is step 5 (`plan_tool/backend.py`), gated on this step (`depends_on: 1, 3`). This step only proves the files ship and are resource-readable.
- **Editable-install fallback** — resolving `integrations/` from the package source (via `Path(__file__).parent.parent`, not the driven project's repo root) when the packaged `plan_tool/integrations/` is absent (the `uv tool install --editable .` / `pip install -e .` case) belongs to step 5's resolver. Flagged here as the known gotcha so step 5 handles both modes.
- **`backend.json` manifests** — `integrations/claude/backend.json`, `integrations/codex/backend.json`, and the new `integrations/codex/SKILL.md` are authored in step 2; this step packages whatever `integrations/` contains, so they ride into the wheel automatically once added.
- **Doc/layout updates** — `README.md`'s `## Current code layout` tree (`README.md:76`) and any note that `integrations/` now ships inside the wheel are part of the plan's landing-doc sweep (plan Deferred), not this packaging edit. `PLAN_FORMAT.md` needs no change (no frontmatter field added).

