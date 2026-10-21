> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add the `plan-tool telemetry` command wiring the analysis leaf, with optional `--json`

## Summary

Adds the read-only `plan-tool telemetry` command — the operator surface over the resolver leaf. It creates `plan_tool/cli/telemetry_cmd.py` with a `cmd_telemetry(args)` handler plus a `register(subparsers)` map, modeled on `plan_tool/cli/convergence_cmd.py` but repo-wide like `plan_tool/cli/inspect.py:cmd_list` (no plan-name argument). The handler calls step 4's `analyze_decisions(repo_root)`, then prints step 4's `render_analysis(...)` text block, or a JSON payload under `--json`. Wiring lands in `plan_tool/cli/app.py` (import the module + add it to `COMMAND_MODULES`) and `plan_tool/cli/parser.py` (add `"telemetry"` to `CANONICAL_COMMAND_ORDER`); `CAPABILITIES.md` gains an owning capability so the honesty check passes, and `docs/cli/telemetry.md` is the generator's output for the new subcommand. On green, `plan-tool telemetry` prints the cross-plan tuning report, `--json` emits a machine-readable form, and the command spends no Claude, writes no run-log entry, mutates nothing, and always exits 0.

## Table of Contents

- [Why](#why) — what's missing between the resolver leaf and an operator
- [Input](#input) — the step 4 analysis contract this command renders
- [Files (creates vs edits)](#files-creates-vs-edits) — three new files, four edits
- [Implementation](#implementation) — the handler, the `--json` shape, the registration wiring, and the doc/capability edits
- [Tests](#tests) — command-contract cases in the new cli test file
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse / json / dataclasses docs for this step
- [Deferred](#deferred) — the cache, time-windowing, and USE_CASES/BACKLOG left for other steps

## Why

Steps 2–4 built the whole resolver leaf (`plan_tool/telemetry_analysis.py`): it reads the decision log, resolves each event to an outcome, groups by `(kind, decision)` across plans, and derives advisory tuning recommendations — but nothing calls it. There is no way for an operator to see the report. This step lands the thin CLI surface that turns `analyze_decisions(repo_root)` into `plan-tool telemetry`, the mission payoff BACKLOG #72 names: read the distribution of what each heuristic signal actually led to, and get a tuning nudge, rather than eyeballing a raw log. It mirrors the `convergence` command exactly — read-only, no Claude, always exit 0, advisory — so the surface is thin wiring over a leaf that already computed everything.

## Input

This step renders **step 4's analysis output**; it owns none of that shape.

- **`analyze_decisions(repo_root: Path) -> TelemetryAnalysis`** (`plan_tool/telemetry_analysis.py`, step 4). The single entry the command calls. It does every disk read and returns a frozen `TelemetryAnalysis`.
- **`TelemetryAnalysis` fields step 4 owns** (read them, don't recompute): `total_events: int`, `aggregates: tuple[DecisionAggregate, ...]`, `recommendations: tuple[TuningRecommendation, ...]`. Each `DecisionAggregate` carries the `(kind, decision)` group with its counts and outcome breakdown; each `TuningRecommendation` carries `kind`, `decision`, `message`, and a `category` slug.
- **`render_analysis(analysis: TelemetryAnalysis) -> str`** (step 4). The printable text block the command emits on the default path with one `print(...)`. Step 4 already made it degrade gracefully on an empty analysis ("no telemetry yet" line, not an empty string).
- **The empty-log case is normal, not an error.** With no decision log on disk, `analyze_decisions` returns `total_events == 0` with empty aggregates/recommendations (step 4). The command prints the graceful text and still exits 0 — never treat "no data" as a failure.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/telemetry_cmd.py` — the `cmd_telemetry(args)` handler + `register(subparsers)` map.
  - `tests/cli/test_telemetry_cmd.py` — the command-contract tests.
  - `docs/cli/telemetry.md` — the generated per-subcommand flag reference (produced by `python -m plan_tool.cli_reference --write`, not hand-authored).
- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — import the new module (`from plan_tool.cli import telemetry_cmd as _telemetry_commands` + the `cmd_telemetry` name) and add `_telemetry_commands` to the `COMMAND_MODULES` tuple.
  - `plan_tool/cli/parser.py` — add `"telemetry"` to `CANONICAL_COMMAND_ORDER` so `--help` renders it in a stable slot.
  - `CAPABILITIES.md` — register the `telemetry` subcommand under an owning capability so `plan-tool validate`'s honesty check doesn't flag it as orphaned.
  - `plan_tool/telemetry_analysis.py` — add a small JSON-shaping helper (see Implementation) so the leaf owns its serialized shape; the CLI stays free of the analysis internals.

## Implementation

### The command handler (`plan_tool/cli/telemetry_cmd.py`)

- **Model the module on `plan_tool/cli/convergence_cmd.py`** — a `cmd_*` handler plus `register(subparsers) -> dict[str, Handler]`, importing only cycle-free leaves (`plan_tool.cli.context`, `plan_tool.cli.parser`) and domain modules, never `plan_tool.cli.app`. Match its module docstring style: state up front that this is read-only, spends no Claude, writes no run-log entry, mutates nothing, and always exits 0.
- **This command is repo-wide, not per-plan — the one place it diverges from `convergence_cmd`.** `cmd_convergence` takes a `name` and calls `resolve_plan_for_context`; telemetry aggregates across *all* plans, so it takes **no positional plan argument**. Load context and pass the repo root straight through, the way `plan_tool/cli/inspect.py:cmd_list` does:
  - `ctx = _load_context(args)` then call `analyze_decisions(ctx.repo_root)`.
  - Do not resolve or parse any plan — there is no plan focus here.
- **Default (text) path:** `print(render_analysis(analysis))` and `return 0`. That is the whole path — the leaf did the work.
- **`--json` path:** serialize the same `TelemetryAnalysis` and `print(json.dumps(payload, ...))`, then `return 0`. Follow the existing emit shape in `plan_tool/cli/runs.py:cmd_runs` (the `if args.json:` block that builds a dict and prints `json.dumps`). Print only the JSON on stdout in this mode — no incidental text lines — so a CI consumer can parse stdout directly.
- **Always exit 0.** There is no `--fail-on-findings` and no rc flip. Recommendations are advisory; a non-empty report is not a failure. This matches the `convergence` default-path contract and the plan's acceptance criteria.
- **No mutation, no Claude, no run-log entry.** The handler has no `invoker=` seam and opens no `RunLogWriter`. Keep it that way — the leaf reads disk; the command only prints.

### The JSON shape lives in the leaf (`plan_tool/telemetry_analysis.py`)

- **Add a small `analysis_to_dict(analysis: TelemetryAnalysis) -> dict` helper to the leaf** and have the CLI call it. This is the reason `plan_tool/telemetry_analysis.py` is in this step's file list.
  - **Why the leaf, not the CLI:** the leaf is the single owner of the analysis shape (steps 2–4). Keeping the JSON projection there means the serialized schema is defined and tested in one place, and the CLI never reaches into the frozen dataclasses' fields. The alternative — `dataclasses.asdict(analysis)` inline in the handler — works but scatters the JSON schema into the CLI and couples the on-disk-facing payload to the exact private field layout. Prefer the leaf helper.
  - **One way to shape it:** a top-level object with `total_events`, an `aggregates` list, and a `recommendations` list, each element a flat dict of that record's fields. The exact keys are the implementer's; the constraint is that a CI consumer can read a per-signal count and outcome breakdown, and each recommendation's `category`/`message`, off the payload.
  - If the implementer instead uses `dataclasses.asdict` directly and leaves the leaf untouched, drop `plan_tool/telemetry_analysis.py` from this step's edits — don't claim an edit that didn't happen.

### Registration wiring

- **`plan_tool/cli/app.py`:** add the two-line import pair that every command module gets (`from plan_tool.cli import telemetry_cmd as _telemetry_commands` and `from plan_tool.cli.telemetry_cmd import cmd_telemetry`), then add `_telemetry_commands` to the `COMMAND_MODULES` tuple. Placement in the tuple doesn't affect help order (that's `CANONICAL_COMMAND_ORDER`'s job) — next to `_convergence_commands` reads well since both are read-only analysis surfaces.
- **`plan_tool/cli/parser.py`:** add `"telemetry"` to the `CANONICAL_COMMAND_ORDER` tuple. This tuple drives `--help` render order via `_reorder_subcommands`; a command absent from it sorts last, so add it explicitly. Placing it right after `"convergence"` groups the two analysis commands together. (Per the tuple's own comment, appending at the end also works — but a chosen slot beside `convergence` reads better.)

### Docs and capability

- **`docs/cli/telemetry.md` is generated, not written by hand.** After the parser wiring is in place, run `python -m plan_tool.cli_reference --write`; it emits `telemetry.md` from the live argparse parser. `tests/cli/test_cli_reference.py` fails unless the committed file is exactly what the generator emits, so do not author this file by hand. Also regenerate the `--help` golden if one covers this surface (`tests/cli/package_surface_help.golden.txt`) — check whether it lists per-command help and re-baseline if so.
- **`CAPABILITIES.md` needs an owning entry for `telemetry`.** `plan_tool/capability_catalog.py:check_capabilities` flags any subcommand with no owning capability (`orphan-subcommand`). Two grounded options:
  - **Add a new `decision-telemetry` capability** — `surfaces:` listing `telemetry`, `plan_tool/telemetry.py`, `plan_tool/telemetry_analysis.py`, `plan_tool/cli/telemetry_cmd.py`; `principles:` a valid subset of the MISSION ids (e.g. `converge-on-correct-plan`, `deterministic-non-determinism`). This also gives the recorder leaf `plan_tool/telemetry.py` a home in the catalog, which it lacks today.
  - **Or fold `telemetry` into an existing capability's `surfaces:`.** Cleaner is the new capability, because the surface is a distinct decision-telemetry analysis lane, not plan discovery or completeness.
  - Use only real MISSION principle ids (`converge-on-correct-plan`, `deterministic-non-determinism`, `keep-the-plan-true-to-code`, `survive-interruption`, `write-for-the-human`) — an invalid id is its own honesty-check finding.

## Tests

New unit/component tests in `tests/cli/test_telemetry_cmd.py`, driving the real parse → dispatch path through `plan_tool.cli.app:main([...])` (mirror `tests/cli/test_convergence_cmd.py`'s structure). This is a **feature** step — write these with the implementation; every one must be green before the step is done.

- `test_telemetry_default_prints_report` — `main(["telemetry"])` over a `tmp_path` repo with a seeded decision log prints the `render_analysis` text (headline count + a line per aggregate) and returns 0.
- `test_telemetry_empty_log_exits_zero` — no decision log → prints the graceful "no telemetry yet" text and returns 0 (not an error).
- `test_telemetry_json_emits_parseable_payload` — `main(["telemetry", "--json"])` prints a single JSON object on stdout that `json.loads` parses, carrying `total_events` and the per-group / recommendation lists.
- `test_telemetry_json_matches_analysis` — the JSON payload's counts agree with `analyze_decisions` over the same seeded log (aggregates and total line up).
- `test_telemetry_spends_no_claude` — the run is caught by the autouse real-backend gate with no opt-out (the command has no invoker seam), confirming zero Claude; assert no `RunLogWriter` entry is written.
- `test_telemetry_registered_and_ordered` — `telemetry` is a real subparser, dispatches to `cmd_telemetry`, and renders in its `CANONICAL_COMMAND_ORDER` slot in `--help`.
- `test_telemetry_has_owning_capability` — `plan_tool.capability_catalog.check_capabilities(repo_root)` returns no `orphan-subcommand` finding for `telemetry` (guards the CAPABILITIES.md edit).

Green-before-done gate: all new `tests/cli/test_telemetry_cmd.py` cases pass, plus `tests/cli/test_cli_reference.py` (after regenerating `docs/cli/telemetry.md`) and any `--help` golden.

## Acceptance criteria

- `plan-tool telemetry` runs, prints the cross-plan `render_analysis` report, and exits 0.
- `plan-tool telemetry --json` prints one `json.loads`-parseable object with the per-signal counts and recommendations, and exits 0.
- With no decision log present, both forms exit 0 and print the graceful empty-state output (no traceback, no non-zero rc).
- The command spends no Claude (caught by the real-backend gate with no opt-out), writes no run-log entry, and mutates nothing.
- `telemetry` is registered: it dispatches to `cmd_telemetry` and appears in `--help` in its `CANONICAL_COMMAND_ORDER` slot.
- `plan_tool/cli/telemetry_cmd.py` imports no `plan_tool.cli.app`.
- `plan_tool.capability_catalog.check_capabilities` reports no `orphan-subcommand` for `telemetry`.
- `docs/cli/telemetry.md` is byte-identical to the `cli_reference` generator output (`tests/cli/test_cli_reference.py` green).
- All new `tests/cli/test_telemetry_cmd.py` cases pass.

## References

- [argparse — Parser for command-line options (Python 3.13)](https://docs.python.org/3/library/argparse.html) — `add_subparsers` / sub-command wiring for `register(subparsers)`, mirroring `plan_tool/cli/convergence_cmd.py`.
- [json — JSON encoder and decoder (Python 3.13)](https://docs.python.org/3/library/json.html) — `json.dumps` for the `--json` payload, following `plan_tool/cli/runs.py:cmd_runs`.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `dataclasses.asdict` reference if the implementer serializes the frozen `TelemetryAnalysis` directly instead of via a leaf helper.

## Deferred

- **Persisting derived verdicts as a cache sidecar** — the whole surface stays compute-on-read (plan §Deferred); no cache lands here.
- **Time-windowing / capping the log read** — a full `read_decisions` per call is the design; a `--since`-style window is added only if a later step proves the read too slow (plan §Deferred).
- **A `--fail-on-findings` rc flip** — out of scope; the command always exits 0, matching the `convergence` default. Advisory output never flips an exit code.
- **`USE_CASES.md`, `CLAUDE.md`, and the BACKLOG #72 phase-3 close** — owned by step 6 (the non-code docs step); this step touches only `CAPABILITIES.md` and the generated `docs/cli/telemetry.md`.
- **The resolver and aggregation logic itself** — owned by steps 2–4; this step only wires the CLI over `analyze_decisions` / `render_analysis`.
