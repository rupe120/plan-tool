> **Auto-archived**: this plan was swept on 2026-07-04 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Wire the split-criteria CLI command and its capabilities/reference docs

## Summary

Adds a new read-only subcommand, `plan-tool split-criteria [<plan>]`, backed by a thin command module `plan_tool/cli/split_criteria_cmd.py` modeled on `plan_tool/cli/convergence_cmd.py`. With no plan argument it prints the plan-independent legend (`render_split_criteria()`, from step 2); with a plan argument it resolves the plan and prints the per-plan breakdown (`evaluate_split_criteria(...)` plus its breakdown renderer, from step 3). The key design decision: the handler stays a pure "tell me the state" diagnostic — no Claude, no mutation, no run-log entry, and it always exits 0 — and it does **not** record telemetry itself, because `evaluate_split_criteria` already writes the `plan-criteria-breakdown` event (the write wired by step 5 through step 1's `record_plan_criteria_breakdown` recorder). On green the command is registered and dispatchable, `plan-tool validate` finds no orphan subcommand (the new surface is listed in `CAPABILITIES.md`), and the generated `docs/cli/split-criteria.md` + README index row match the live parser.

## Table of Contents

- [Summary](#summary) — what the step wires up and the observable result on green
- [Why](#why) — the missing operator entry point the earlier steps' code has no surface for
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files and the wiring/doc edits
- [Implementation](#implementation) — the two-mode handler, the registration wiring, the capabilities + generated docs, and the constraints
- [Tests](#tests) — CLI unit + integration cases in tests/test_split_criteria.py plus the drift guards
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse optional-positional + pytest marker docs
- [Deferred](#deferred) — SKILL routers, USE_CASES prose, and cross-plan aggregation left for later

## Why

Steps 1–3 land the recorder, the criteria catalog + legend, and the per-plan evaluator — but all of that is library code with no operator entry point. Nothing lets a developer run "show me the split criteria" or "why is *this* plan shaped this way?" from the command line. This step wires the thin CLI shell around the step 2/3 renderers so the feature is reachable, discoverable in `--help`, owned by a capability (so `plan-tool validate` stays honest), and documented in the generated CLI reference. It mirrors how `plan-tool convergence` is a thin `plan_tool/cli/convergence_cmd.py` over `convergence_diagnosis` — landing the CLI last, after its logic is reviewable on its own.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/split_criteria_cmd.py` — the `cmd_split_criteria` handler and `register(subparsers)`. Thin: imports only cycle-free leaves (`plan_tool.cli.context`, `plan_tool.cli.parser`) and domain modules (`plan_tool.split_criteria`, `plan_tool.locator`, `plan_tool.parser` for `parse_plan`), never `plan_tool.cli.app`.
  - `docs/cli/split-criteria.md` — **generated**, not hand-written. Produced by `python -m plan_tool.cli_reference --write` once the subparser exists.
- **Existing files (edits only):**
  - `plan_tool/cli/parser.py` — append `"split-criteria"` to the `CANONICAL_COMMAND_ORDER` tuple (the docstring already says new post-split commands extend the tuple).
  - `plan_tool/cli/app.py` — add `from plan_tool.cli import split_criteria_cmd as _split_criteria_commands`, re-import `from plan_tool.cli.split_criteria_cmd import cmd_split_criteria` (so the name is a module global `__init__` mirrors), and append `_split_criteria_commands` to the `COMMAND_MODULES` tuple.
  - `plan_tool/cli/__init__.py` — add the catalog help line in the module docstring and `"cmd_split_criteria"` to `__all__`.
  - `CAPABILITIES.md` — add `split-criteria` and `plan_tool/split_criteria.py` to an existing capability's `surfaces`.
  - `docs/cli/README.md` — **generated** index row, re-baselined by the same `cli_reference --write` run.
  - `tests/test_split_criteria.py` — add the CLI unit + integration tests (this file already exists from step 2).

## Implementation

**Build a thin command module, cloning `plan_tool/cli/convergence_cmd.py`.** That module is the closest sibling: a read-only, `args`-only handler plus a `register` that returns a one-entry handler map. Copy its shape — module docstring stating no-Claude / no-mutation / always-exit-0, a `cmd_split_criteria(args) -> int`, and a `register(subparsers) -> dict[str, Handler]`.

**The handler splits by kind on whether a plan name was given.** Two modes, one positional argument:
- **No plan (legend mode).** Call `render_split_criteria(color=style.color_enabled(sys.stdout))` (step 2, no plan argument — pass color so the legend is colored on a TTY and plain when piped, delivering AC1), `print` it, return 0. Do **not** resolve a plan or load context here — the legend is plan-independent, and calling `resolve_plan_for_context` with no name would error. This is the important constraint: the plan-resolution path must be reached only when a name is present.
- **Plan given (breakdown mode).** Load context with `_load_context(args)` (from `plan_tool.cli.context`), resolve the plan *path* with `resolve_plan_for_context(ctx, args.name)` (from `plan_tool.locator`, same two calls `cmd_convergence` uses — it returns a `Path`), then parse that path into a `Plan` with `parse_plan(path)` (from `plan_tool.parser`, the same acquisition sibling read-only handlers `inspect.py:cmd_status`/`cmd_validate` do), then call `evaluate_split_criteria(plan, plan_path=path, repo_root=...)` (step 3). Follow step 3's actual signature — `evaluate_split_criteria(plan, *, plan_path, repo_root)` (parsed `Plan` first positional, then keyword `plan_path`/`repo_root`); it needs the parsed plan object, its path, and the repo root to compute the fingerprint and read history.
  - **Render the breakdown; the evaluator owns the drift note.** The handler does **not** read decisions, compute drift, or record — `evaluate_split_criteria` owns the read→diff→record order (step 5): it reads prior decisions, computes the drift note against the most recent different-fingerprint run, records this run's event, and attaches the result as `breakdown.drift`. So the handler just renders `render_plan_breakdown(breakdown, color=style.color_enabled(sys.stdout))` — no `drift=` kwarg; the renderer reads `breakdown.drift` — then `print`, return 0.

**Do not record telemetry in the handler.** This is the one deliberate divergence from `cmd_convergence`, which calls `record_convergence` itself. Step 5 wires the `plan-criteria-breakdown` write into `evaluate_split_criteria` (via step 1's `telemetry.record_plan_criteria_breakdown` recorder), so it already writes the event as part of evaluating. A second write in the handler would double-count. So the breakdown mode calls `evaluate_split_criteria` and prints; the legend mode records nothing at all (there is no per-plan run to log).

**Wire the optional positional in `register`.** Add the subparser with an optional `name` positional — one way: `p.add_argument("name", nargs="?", default=None, help=...)`. Mirror `convergence`'s `name` help text and its local `-y/--yes` parent if you want parity, though `-y` is inert here (there is no confirm prompt in a read-only diagnostic — keep it only if you want to stay identical to the sibling; otherwise omit it). Return `{"split-criteria": cmd_split_criteria}`.

**Register the module in the four wiring sites** — the same set every command module touches:
- `plan_tool/cli/parser.py`: append `"split-criteria"` to `CANONICAL_COMMAND_ORDER`. A command absent from the tuple sorts after all canonical ones; appending pins it right after `scope-out` in `--help`.
- `plan_tool/cli/app.py`: the two imports named above plus the `COMMAND_MODULES` append. The re-import of `cmd_split_criteria` matters because `plan_tool/cli/__init__.py` mirrors every module global from `app` into the package namespace, and `__all__` names must resolve.
- `plan_tool/cli/__init__.py`: the catalog help line and the `__all__` entry.

**Place the catalog help line where it reads best.** The `## …` groupings in the `__init__.py` docstring are by intent. This command answers "why is this plan shaped this way / what are the split criteria" — a read-only diagnostic. One reasonable home is beside `convergence` under the audit/completeness grouping; another is near the structural verbs (`split`/`merge`/`scope-out`). Pick one and keep the line terse, matching the `convergence` line's format (`plan-tool split-criteria [<plan>]   <one-liner>`). The `help=` string in `register` is the source of truth the generated docs mirror — keep the docstring line consistent with it, and if they drift, treat the shipped `help=` as authoritative.

**Give the subcommand an owning capability or `validate` fails.** `plan_tool/capability_catalog.py:check_capabilities` emits an `orphan-subcommand` finding for any primary name no capability lists in `surfaces` (see `_surface_exists` / the `orphan-subcommand` branch). Add both `split-criteria` (the subcommand) and `plan_tool/split_criteria.py` (the module) to one capability's `surfaces`. Recommended home: **`structural-remedies`** (it already lists `plan_tool/granularity.py` and the `split`/`merge`/`scope-out` verbs — this command visualizes exactly that split axis). The alternative is `plan-completeness` (it owns `convergence` + `convergence_diagnosis.py`, which the evaluator reads). Either is fine as long as `plan-tool validate` is green; don't add a new capability block for a single read-only surface.

**Regenerate the CLI reference — don't hand-write it.** `docs/cli/split-criteria.md` and the README index row are produced by `python -m plan_tool.cli_reference --write` from the live parser and are drift-guarded by `tests/cli/test_cli_reference.py`. After the subparser is wired, run the generator to emit the new file and re-baseline `docs/cli/README.md`. Hand-editing either would fail the drift test.

## Tests

Add these to `tests/test_split_criteria.py`. Drive `main([...])` cases are cross-module — mark them `@pytest.mark.integration` at the class level. Unit-test `register` and the handler directly where you can. Every new test must be green before this step is done.

- `test_register_returns_handler_map` — `register(subparsers)` returns `{"split-criteria": cmd_split_criteria}` and adds the subparser.
- `test_no_arg_renders_legend` — `main(["split-criteria"])` prints the legend text (`render_split_criteria()` output) and returns 0, with no plan resolution attempted.
- `test_with_plan_renders_breakdown` — `main(["split-criteria", <name>])` prints the per-plan breakdown and returns 0 (stub/point `evaluate_split_criteria` at a fixture plan).
- `test_exits_zero_when_criteria_fire` — a plan whose evaluator reports fired criteria still returns 0 (no `--fail-on-findings` rc-flip).
- `test_spends_no_claude` — the command runs under the autouse real-backend gate without opting out (no `@pytest.mark.allow_real_claude`); no invoker is wired.
- `test_handler_does_not_double_record` — after one breakdown run, exactly one `plan-criteria-breakdown` event is present (read back via `telemetry.read_decisions`), proving the handler does not record a second event on top of `evaluate_split_criteria`.
- `test_legend_mode_records_nothing` — `main(["split-criteria"])` (no plan) writes no telemetry event.
- `test_split_criteria_sorts_after_scope_out_in_help` — the rendered `--help` lists `split-criteria` in its canonical position (after `scope-out`).
- `test_validate_reports_no_orphan_subcommand` — `check_capabilities` (or `plan-tool validate`) returns no `orphan-subcommand` finding for `split-criteria`.

The generated-doc drift is already covered by `tests/cli/test_cli_reference.py::TestCliReferenceDrift` — after `cli_reference --write`, that suite must stay green (it will fail if the new `.md` or README row is missing or stale).

## Acceptance criteria

- `plan-tool split-criteria` (no argument) prints the legend and exits 0.
- `plan-tool split-criteria <plan>` prints the per-plan breakdown and exits 0, including when criteria fire.
- `cmd_split_criteria` calls neither a Claude invoker nor any plan-mutating function, and writes no run-log entry.
- Exactly one `plan-criteria-breakdown` telemetry event is written per breakdown run (none in legend mode) — the handler adds no second write.
- `plan-tool validate` reports no `orphan-subcommand` finding; `CAPABILITIES.md` lists `split-criteria` and `plan_tool/split_criteria.py` under a capability.
- `split-criteria` appears in `plan-tool --help` after `scope-out`.
- `docs/cli/split-criteria.md` exists and `tests/cli/test_cli_reference.py` passes (new file + README row match the generator).
- `plan_tool/cli/split_criteria_cmd.py` imports no `plan_tool.cli.app` symbol.
- All new `tests/test_split_criteria.py` CLI cases pass.

## References

- [argparse — add_argument / nargs='?' (Python docs)](https://docs.python.org/3/library/argparse.html#nargs) — for the optional `name` positional that toggles legend vs per-plan mode.
- [argparse — add_subparsers / add_parser (Python docs)](https://docs.python.org/3/library/argparse.html#sub-commands) — the `register(subparsers)` seam every command module follows.
- [How to mark test functions with attributes (pytest docs)](https://docs.pytest.org/en/stable/how-to/mark.html) — for the `@pytest.mark.integration` marker on the `main([...])` cases.

## Deferred

- **SKILL routers** (`integrations/claude/SKILL.md`, `integrations/codex/SKILL.md`) — out of the declared file set. Read-only diagnostics like `convergence` and `status` are not listed as discoverable subcommand rows there, so `split-criteria` follows the same precedent; a later discoverability pass can add all three together if wanted.
- **`USE_CASES.md` / `README.md` narrative prose** — not in scope; this step wires the command and the generated reference only.
- **Telemetry analysis / cross-plan aggregation surface** — reading the accumulated `plan-criteria-breakdown` events across plans stays deferred (owned by the metrics-tuning work, BACKLOG #57/#72), not this CLI wiring.
- **The `-y/--yes` flag semantics** — inert on a read-only diagnostic; kept only to stay identical to `convergence` if adopted, with no confirm prompt to accept.
