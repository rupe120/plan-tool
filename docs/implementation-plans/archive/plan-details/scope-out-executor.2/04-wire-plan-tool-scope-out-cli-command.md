> **Auto-archived**: this plan was swept on 2026-06-25 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Wire the `plan-tool scope-out` CLI command (handler + dispatch + generated docs + integration test)

## Summary

Adds the operator-facing front door for the scope-out actuator: a new single-command module `plan_tool/cli/scope_out_cmd.py` (`cmd_scope_out` + `register`) that resolves a plan, calls step 3's deterministic `plan_tool/scope_out.py:scope_out_step(...)`, and renders its frozen `ScopeOutResult` to the console. The command is `plan-tool scope-out <name> --step N [--apply] [-y]`: recommend-only by default, mutating the plan only when `--apply` plus either an interactive confirm or the deliberate second opt-in `-y/--yes` hold — exactly the gate step 3 already encodes. Wiring is the standard single-command fan-out modeled on `plan_tool/cli/convergence_cmd.py`: dual-import into `plan_tool/cli/app.py`, append to `COMMAND_MODULES`, extend `CANONICAL_COMMAND_ORDER` in `plan_tool/cli/parser.py`, add the catalog line + `__all__` entry in `plan_tool/cli/__init__.py`, add the `scope-out` surface to the **Structural remedies** capability in `CAPABILITIES.md` (so `plan-tool validate` stays green the moment the subcommand registers), regenerate `docs/cli/scope-out.md`, and re-baseline `tests/cli/package_surface_help.golden.txt`. On green, `plan-tool scope-out` appears in `--help`, dispatches to the handler, and an integration test in `tests/test_scope_out.py` proves the end-to-end carve writes the seed, narrows the plan, and round-trips the emitted seed through `create --from-existing` — with `create`'s Claude invoker stubbed (no real decomposition) — asserting the seed ingests cleanly through the deterministic seed-ingestion/provenance path without error.

## Table of Contents

- [Why](#why) — the actuator has no operator entry point yet
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files, five edits
- [Implementation](#implementation) — the handler, the register seam, the dispatch fan-out, generated docs
- [Tests](#tests) — the CLI integration test and the package-surface guards
- [Acceptance criteria](#acceptance-criteria) — observable behaviors a reviewer can check
- [References](#references) — argparse + pytest docs for this step
- [Deferred](#deferred) — convergence flip, telemetry, reconcile-side routing

## Why

Steps 1–3 build the whole scope-out actuator in `plan_tool/scope_out.py` — the seed renderer, the narrow primitive, and the `scope_out_step(...)` orchestrator with its apply-or-recommend gate — but nothing lets an operator *run* it. The convergence diagnostic's scope-out fork-arm — produced by the sibling advisory plan (`structural-remedy-vocabulary`), not yet at HEAD — recommends scope-out in prose with `command=""` (the empty command the advisory plan deliberately leaves for this executor plan to fill). This step ships the missing verb: it adds the thin CLI handler that turns the operator's `plan-tool scope-out <name> --step N` into a `scope_out_step(...)` call, renders the result, and registers the command across the parser/dispatch/docs surface so it is discoverable, help-stable, and integration-tested.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/scope_out_cmd.py` — the command module: `cmd_scope_out(args) -> int` handler + `register(subparsers) -> dict[str, Handler]`. Mirrors `plan_tool/cli/convergence_cmd.py`.
  - `docs/cli/scope-out.md` — **generated**, not hand-authored; written by `python -m plan_tool.cli_reference --write` from the argparse parser. Drift-guarded by `tests/cli/test_cli_reference.py`.
- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — dual-import the new module (`from plan_tool.cli import scope_out_cmd as _scope_out_commands` + `from plan_tool.cli.scope_out_cmd import cmd_scope_out`), and append `_scope_out_commands` to the `COMMAND_MODULES` tuple.
  - `plan_tool/cli/parser.py` — append `"scope-out"` to `CANONICAL_COMMAND_ORDER` (after `"detach-branch"`), so help renders it in a fixed position rather than sorting it into the trailing un-ordered group.
  - `plan_tool/cli/__init__.py` — add a `scope-out` line to the **Authoring** catalog block (beside `split` / `merge`, the other restructure verbs) and add `"cmd_scope_out"` to `__all__`.
  - `CAPABILITIES.md` — add the `scope-out` surface to the **Structural remedies** capability's `surfaces:` list (beside `split`, `merge`, `plan_tool/granularity.py`), landing the catalog row in the same step that registers the subcommand so `plan-tool validate`'s honesty check never sees an orphan.
  - `tests/cli/package_surface_help.golden.txt` — re-baseline with `UPDATE_CLI_GOLDEN=1` to capture the new usage-line entry + catalog line.
  - `tests/test_scope_out.py` — add the one CLI integration test class (extends the unit file steps 1–3 created).

## Implementation

### `plan_tool/cli/scope_out_cmd.py` (new)

- **Module docstring** — two lines: the `scope-out` verb actuates the scope-out remedy by calling the deterministic `plan_tool/scope_out.py:scope_out_step`; it spends **no Claude**, mutates the plan only under `--apply` plus confirm or `-y/--yes`, and imports only cycle-free leaves (`plan_tool.cli.context`, `plan_tool.cli.parser`) and domain modules — never `plan_tool.cli.app`. Cite `plan_tool/cli/convergence_cmd.py` as the sibling pattern.
- **Imports** — `from __future__ import annotations`; `import argparse`; `from plan_tool.cli.context import _load_context`; `from plan_tool.cli.parser import Handler`; `from plan_tool.locator import resolve_plan_for_context`; `from plan_tool.scope_out import scope_out_step` (and `ScopeOutResult` if a type annotation is wanted). Do **not** thread an `invoker=` — `scope_out_step` takes none (both halves are deterministic, pinned by step 3's `test_scope_out_step_takes_no_invoker`).
- **`cmd_scope_out(args: argparse.Namespace) -> int`** — the handler:
  - `ctx = _load_context(args)`
  - `path = resolve_plan_for_context(ctx, args.name)`
  - `result = scope_out_step(path, carved_id=args.step, repo_root=ctx.repo_root, allow_scope_out=args.apply, yes=args.yes)` — pass `allow_scope_out=args.apply` (the opt-in) and `yes=args.yes` (the explicit non-interactive second opt-in); leave `prompt_fn` defaulted (step 3's `_confirm_scope_out` owns the `builtins.input` TTY prompt when `-y` is absent).
  - **Render `result.outcome`** to the console, one branch per outcome value (`applied` / `recommended` / `unsafe` / `empty-plan` / `step-missing`). Use the repo's `plan_tool.style` helpers (`success` / `info` / `warn` / `error`) as the other command modules do:
    - `applied` → `success(...)` naming the written seed (`result.seed_path`) and the narrowed plan (the survivor renumber + new CURRENT from `result.narrow`).
    - `recommended` → `info(...)` stating the carve is safe and printing the exact opt-in line to actuate it interactively (`plan-tool scope-out <name> --step N --apply`) plus a note that `--apply -y` is the deliberate non-interactive apply path; this is the default no-`--apply` path.
    - `unsafe` → `warn(...)` listing `result.blockers` (each `NarrowBlocker`'s kind + message) **and printing the ready-to-run `plan-tool create --from-existing` re-seed line** alongside the blockers, so the refused case (the common convergence-recommended mid-plan spinning CURRENT step with a surviving inbound dependent) lands on a next action rather than a bare blocker list — the `scope-out-refusal-fallback` dead-end the design names; nothing written.
    - `empty-plan` → `warn(...)` explaining the refusal **and printing the same ready-to-run `plan-tool create --from-existing` re-seed line**, pointing the operator at a full re-seed; nothing written.
    - `step-missing` → `warn(...)` explaining the refusal (bad step id), nothing written.
  - **`return 0` for every outcome.** Per the repo's exit-code convention, a completed command exits 0 even on a refusal/recommendation verdict — the carve either happened or was deliberately not performed; neither is a failure-to-complete. An unresolvable `name` still surfaces a non-zero error from `resolve_plan_for_context` upstream, matching `cmd_convergence`.
- **`register(subparsers) -> dict[str, Handler]`** — add the one subparser and return `{"scope-out": cmd_scope_out}`:
  - Build a **local** `-y/--yes` parent (`argparse.ArgumentParser(add_help=False)` with `-y`/`--yes`, `action="store_true"`), mirroring `convergence_cmd.register` until the shared flag is consolidated. The `--yes` bypasses the confirm in `scope_out_step` and is a deliberate second opt-in that may mutate without a TTY (relevant only with `--apply`).
  - `p = subparsers.add_parser("scope-out", help="carve a spinning step out of a plan into a create --from-existing seed (recommend-only; --apply to mutate)", parents=[yes_parent])`.
  - `p.add_argument("name", help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md")`.
  - `p.add_argument("--step", type=int, required=True, help="step id to carve out of the plan")` — names the carved step (`carved_id`).
  - `p.add_argument("--apply", action="store_true", help="opt in to mutating the plan: write the forward-seed and narrow the plan (default: recommend only). Requires an interactive confirm unless paired with -y/--yes.")` — the opt-in gate (`allow_scope_out`).
  - Return `{"scope-out": cmd_scope_out}`. The handler name `cmd_scope_out` is the mechanical `cmd_<name-with-hyphens→underscores>` form, so `tests/cli/test_package_surface.py` resolves it with no `_HANDLER_NAME_EXCEPTIONS` entry.

### `plan_tool/cli/app.py` (edit)

- **Dual-import**, placed beside the `convergence_cmd` block (the structural sibling):
  - `from plan_tool.cli import scope_out_cmd as _scope_out_commands`
  - `from plan_tool.cli.scope_out_cmd import cmd_scope_out`
  - The `cmd_scope_out` re-import into the `app` namespace satisfies the package-surface re-export and keeps the bare-name resolution convention the module documents.
- **Append `_scope_out_commands`** to the `COMMAND_MODULES` tuple. Order within the tuple feeds the registry pass only; `_reorder_subcommands` re-sorts help by `CANONICAL_COMMAND_ORDER`, so append at the end (next to `_skill_commands`).

### `plan_tool/cli/parser.py` (edit)

- **Append `"scope-out"`** to `CANONICAL_COMMAND_ORDER` after `"detach-branch"`. A new command absent from the tuple sorts after every canonical one in registration order; adding it pins a deterministic help position. The recently-added `convergence` entry is the precedent for extending this tuple on a new command.

### `plan_tool/cli/__init__.py` (edit)

- **Add a catalog line** under the **Authoring — produce or restructure plan files on disk** block, beside the `split` and `merge` lines (scope-out is a structural restructure verb that carves a step out, not an audit/inspection verb):
  - `plan-tool scope-out <name> --step N [--apply] [-y]   Carve a spinning step out of a plan into a create --from-existing forward-seed and narrow the plan; recommend-only by default, --apply plus confirm or -y to mutate.`
- **Add `"cmd_scope_out"`** to `__all__` (next to `"cmd_convergence"`).
- Keep the module docstring's category structure intact — this docstring is the source the base parser threads into `--help`, so its text drives the golden re-baseline.

### `CAPABILITIES.md` (edit)

- **Catalogue the new `scope-out` surface** under the existing **Structural remedies** capability (`id: structural-remedies`): add `scope-out` to its `surfaces:` list, beside `split`, `merge`, and `plan_tool/granularity.py`. The catalog row must land in **this** step — the same one that registers the subcommand — not a later docs step: `plan-tool validate`'s no-Claude honesty check (`plan_tool/capability_catalog.py`) flags any subcommand with no owning capability, and `tests/test_capability_catalog.py:test_check_real_repo_catalog_is_honest` asserts the check returns no findings. Registering the verb without the surface row would leave `plan-tool validate` reporting an `orphan-subcommand` and that regression test red. No principle edit — the capability already lists `converge-on-correct-plan`, the principle scope-out serves.

### `docs/cli/scope-out.md` (generated)

- Regenerate the whole `docs/cli/` set with `python -m plan_tool.cli_reference --write`; it emits `scope-out.md` from the argparse parser (usage, the `name` arg, and the `--step` / `--apply` / `-y` options). Do not hand-edit — `tests/cli/test_cli_reference.py` diffs the generated output against the parser and would flag any manual drift.

## Tests

Add to `tests/test_scope_out.py` (the unit file steps 1–3 created). Mark the new class `@pytest.mark.integration` per the repo rule (class-level integration marker) — it drives `main([...])` end-to-end across the CLI, parser, and orchestrator. The marker and the test-class shape come from the repo rule, **not** from the sibling test cited next: `tests/cli/test_convergence_cmd.py` is unmarked and uses module-level functions with a `registered_plan` fixture, so mirror only its `main(argv)`-against-a-temp-repo style, not its (absent) marker/class structure. **Do not reach for that test's `registered_plan` / `tmp_repo` (`CliRepo`) fixtures** — they are defined only in `tests/cli/conftest.py` and are out of pytest conftest scope in the top-level `tests/test_scope_out.py` (`tests/conftest.py` defines no such fixtures), so importing or requesting them there yields a fixture-not-found error. Instead build the repo + manifest manually as the top-level `main`-driving tests do (e.g. `tests/test_sweep.py` wires its temp repo with `json` / `Path` / `parse_plan`): reuse the unit file's existing plan-construction helpers (the ones steps 1–3 use to build a multi-step plan with detail files on disk) plus a manifest registration so `resolve_plan_for_context` finds the plan.

### Test-creation order (feature step)

This is a **feature** step — new CLI behavior. Add these tests **with** the wiring; every one must be green before the step is done:

- `test_scope_out_recommend_only_by_default` — `main(["scope-out", <plan>, "--step", N])` (no `--apply`) writes **no** seed and does **not** narrow the plan; prints the `--apply` opt-in line; rc is 0.
- `test_scope_out_apply_yes_carves` — `main(["scope-out", <plan>, "--step", N, "--apply", "-y"])` writes the forward-seed under `plan-seeds/` (assert the file exists) and narrows the plan without requiring a TTY (assert the carved step is gone, survivors renumbered `1..N-1`); then feed the emitted seed back through `create --from-existing` with `create`'s Claude invoker stubbed (no real decomposition, so the autouse no-Claude gate stays intact) and assert the seed parses/ingests cleanly through `create --from-existing`'s deterministic seed-ingestion/provenance path without error — never an end-to-end Claude decomposition; rc is 0.
- `test_scope_out_unsafe_step_refused` — carving a step with an inbound dependent (or a downstream non-PENDING step) under `--apply -y` writes nothing, prints the blocker(s), rc is 0 — proves the step-3 blocker gate is reached through the CLI and a refusal is not a non-zero exit.
- `test_scope_out_missing_step_refused` — `--step` for a non-existent id prints the `step-missing` refusal and writes nothing; rc is 0.
- `test_scope_out_in_help` — `build_parser()` lists `scope-out` among its subcommands. `build_parser()` returns only the parser (`app.py: return assemble(cli.__doc__, COMMAND_MODULES)[0]`), not the dispatch dict, so this test cannot assert the `scope-out` → `cmd_scope_out` handler mapping directly; that mapping is established through `assemble`'s dispatch dict and is covered by the existing parser↔dispatch correspondence check in `tests/cli/test_package_surface.py` (the golden snapshot guards the rendered help line).

The existing `tests/cli/test_package_surface.py` (golden help + every-subcommand-has-a-handler) and `tests/cli/test_cli_reference.py` (generated-docs drift) require no new test code — they pass once the golden and `docs/cli/scope-out.md` are re-baselined.

## Acceptance criteria

- `plan-tool scope-out <name> --step N` (no `--apply`) leaves the plan and `plan-seeds/` unchanged and exits 0.
- `plan-tool scope-out <name> --step N --apply -y` on a safe carve is the deliberate non-interactive apply path: it writes a `create --from-existing` seed under `plan-seeds/`, narrows the plan (carved step dropped, survivors contiguous `1..N-1`), feeds the emitted seed back through `create --from-existing` with `create`'s Claude invoker stubbed (no real decomposition) to assert it ingests cleanly through the deterministic seed-ingestion/provenance path without error, and exits 0.
- A blocked carve (inbound dependent, downstream non-PENDING, empty result, or missing step) writes nothing and exits 0 with the blocker reported. The `unsafe` and `empty-plan` branches additionally print the ready-to-run `plan-tool create --from-existing` re-seed line alongside the blockers, so the refused case lands on a next action rather than a bare blocker list (`step-missing`, a bad-id refusal, does not).
- `scope-out` appears in `plan-tool --help` in its `CANONICAL_COMMAND_ORDER` position and dispatches to `cmd_scope_out`.
- `from plan_tool.cli import cmd_scope_out` resolves (the `__all__` + app re-import).
- `CAPABILITIES.md`'s **Structural remedies** capability lists `scope-out` in its `surfaces:`, so `plan-tool validate` raises no `orphan-subcommand` finding for the new verb and `tests/test_capability_catalog.py` stays green from this step's completion onward.
- `docs/cli/scope-out.md` exists and matches `python -m plan_tool.cli_reference --write` output; `tests/cli/test_cli_reference.py` passes.
- `tests/cli/package_surface_help.golden.txt` is re-baselined; `tests/cli/test_package_surface.py` passes.
- All new `tests/test_scope_out.py` integration tests are green; full suite stays green.

## References

- [argparse — add_subparsers / add_parser](https://docs.python.org/3/library/argparse.html#sub-commands) — the `register(subparsers)` seam and the `--step` / `--apply` / `-y` flag wiring; `add_help=False` parents for the shared `-y/--yes`.
- [pytest — How to mark test functions](https://docs.pytest.org/en/stable/how-to/mark.html) — the `@pytest.mark.integration` marker the one end-to-end `main([...])` CLI test carries.

## Deferred

- **Convergence/reconcile flip of the empty `command`** — wiring `plan-tool convergence`'s scope-out fork-arm (and any reconcile re-ground finding) to render the now-runnable `plan-tool scope-out … --step N` line instead of `command=""`; the advisory plan carried `step_focus` for exactly this, but flipping it lives with the convergence/reconcile callers, not this CLI step. Track in the scope-out-executor follow-up routing.
- **Decision telemetry for scope-out** — `plan_tool/telemetry.py` Phase 1 records only `granularity` / `audit-coverage` / `convergence`; adding a scope-out decision event is a separate telemetry-schema change (`DATA_CONTRACT.md` drift-guarded), out of scope here.
- **Operator-doc surfaces beyond the generated CLI reference** — README / RUNBOOK / CLAUDE `## Architecture` / SKILL-pair router rows for the shipped `scope-out` verb are the six-file operator-command docs set owned by a later docs step (step 5 / the plan's docs step), not this wiring step. Only `docs/cli/scope-out.md` (generated) lands here.
- **Routing scope-out into the interactive review/reconcile apply walk** — the analog of `cli/review_actions.py:_dispatch_structural_escalation` for scope-out (apply a carve mid-walk) is a separate seam; this step ships the standalone command only.
