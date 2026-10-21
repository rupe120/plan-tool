> **Auto-archived**: this plan was swept on 2026-07-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Register `direct-jira` and `direct-run` and regenerate the CLI reference

## Summary

This step makes the two chain verbs reachable from the command line. It adds a `register(subparsers)` function to `plan_tool/cli/direct_cmd.py` that builds the `direct-jira` and `direct-run` subparsers and returns their handler map, wires the module into `plan_tool/cli/app.py`'s `COMMAND_MODULES` registry (plus the mutation-lock set), and appends both command names to `CANONICAL_COMMAND_ORDER` in `plan_tool/cli/parser.py` so help order stays deterministic. The generated CLI reference is then re-baselined with `python -m plan_tool.cli_reference --write`, which creates `docs/cli/direct-jira.md` and `docs/cli/direct-run.md` and updates the `docs/cli/README.md` index. On green, `plan-tool direct-jira --help` and `plan-tool direct-run --help` exit 0, the parser feeds each verb a namespace complete against the fields its handler reads directly, and `tests/cli/test_cli_reference.py` passes against the regenerated docs.

## Table of Contents

- [Summary](#summary) — what the step ships and the result on green.
- [Why](#why) — why the verbs need registration and doc regeneration now.
- [Input](#input) — the two verb handlers and the registry/generator contracts this step wires.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two generated docs plus the wiring edits.
- [Implementation](#implementation) — the `register` seam, the app/parser wiring, the lock, and the doc regen.
- [Tests](#tests) — dispatch, field-completeness, and reference-generation cases.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — argparse and the CLI-reference generator.
- [Deferred](#deferred) — flag tuning and mid-chain resume left to other work.

## Why

Steps 4 and 5 landed `cmd_direct_jira` and `cmd_direct_run` in `plan_tool/cli/direct_cmd.py`, but no parser feeds them — they are reachable only in tests through a hand-built `argparse.Namespace`. Every other command in the tool is registered through the per-module `register(subparsers)` seam that `plan_tool/cli/parser.py:assemble` drives, so an operator can type it and `plan-tool --help` lists it. This step adds that registration for both verbs and regenerates the mechanical CLI reference under `docs/cli/`, which is drift-checked in CI (`tests/cli/test_cli_reference.py`) and would otherwise fail the moment a new subcommand exists without its reference file. It also closes the field-completeness gap the sibling steps deferred: because the verbs copy the parent namespace and override per stage, the real parser must supply every create-side field the verbs read directly, or a stage handler raises `AttributeError` at runtime.

## Input

This step reads three contracts it does not own:

- **The two verb handlers** — `cmd_direct_jira` (step 4) and `cmd_direct_run` (step 5) in `plan_tool/cli/direct_cmd.py`. This step registers them; it does not change their chain logic. It must know which create-side fields each reads off its own args namespace so the subparser supplies them.
- **The command-module registry contract** — `plan_tool/cli/parser.py:assemble` calls each module's `register(subparsers) -> dict[str, Handler]` and merges the returned maps, asserting no command key is registered twice. `Handler` is `Callable[[argparse.Namespace], int]`. The global flags (`--backend`, `--model`, `--on-rate-limit`, `--fallback-backend`, `--plans-dir`, verbosity) come from `make_base_parser` and are already present on every namespace, so the subparser only adds this verb's own flags.
- **The CLI-reference generator** — `plan_tool/cli_reference.py:render_reference` walks the live parser via `plan_tool.cli.build_parser()` and emits one `<command>.md` per subcommand plus `README.md`. New subcommands are picked up automatically; the step's job is to run `write_reference` (via `python -m plan_tool.cli_reference --write`) and commit the output.

## Files (creates vs edits)

- **New files:**
  - `docs/cli/direct-jira.md` — generated reference for the `direct-jira` subcommand (written by the generator, not hand-authored).
  - `docs/cli/direct-run.md` — generated reference for the `direct-run` subcommand (generated).
- **Existing files (edits only):**
  - `plan_tool/cli/direct_cmd.py` — add `register(subparsers) -> dict[str, Handler]` building both subparsers and returning `{"direct-jira": cmd_direct_jira, "direct-run": cmd_direct_run}`.
  - `plan_tool/cli/app.py` — import the module (`from plan_tool.cli import direct_cmd as _direct_commands`) and its handlers, add `_direct_commands` to `COMMAND_MODULES`, and add `"direct-jira"` / `"direct-run"` to `_LOCKED_MUTATING_COMMANDS`.
  - `plan_tool/cli/parser.py` — append `"direct-jira"` and `"direct-run"` to `CANONICAL_COMMAND_ORDER`.
  - `docs/cli/README.md` — regenerated index gains the two new rows/links (generator output).
  - `tests/cli/test_direct_cmd.py` — add parser-dispatch and namespace field-completeness tests driving the real parser.
  - `tests/cli/test_cli_reference.py` — add a targeted test that both reference files are generated and linked.

## Implementation

**What changes:** the two verbs become real subcommands. Follow the established per-module registration pattern — do not invent a new wiring shape.

- **Add `register(subparsers)` to `plan_tool/cli/direct_cmd.py`, modeled on `plan_tool/cli/scope_out_cmd.py:register`.** It calls `subparsers.add_parser("direct-jira", help=…)` and `subparsers.add_parser("direct-run", help=…)`, adds each verb's flags, and returns `{"direct-jira": cmd_direct_jira, "direct-run": cmd_direct_run}`. Keep the module a thin leaf: it imports only cycle-free leaves (`plan_tool.cli.parser` for `Handler`) and never `plan_tool.cli.app`.
- **Give each subparser the create-side inputs the verbs read.** Both verbs start by chaining `create`, so they mirror `create`'s seed-source shape. Look at `plan_tool/cli/authoring.py`'s `register` (`p_create` and its mutually-exclusive `--from` / `--from-existing` source group, the optional slug positional, and the `--iterate` / `--no-iterate` action) and reproduce the subset each verb reads off its own args. One way: a shared `add_help=False` parent parser for the flags both verbs take (seed source, slug, `--iterate`, `-y/--yes`), mirroring the `yes_parent` / `iterate_parent` parents in `authoring.py:register`. The exact final flag set is whatever steps 4–5's handlers read from their own namespace — the field-completeness test below is what pins it; add a flag when the test surfaces a missing one.
- **The downstream-only fields are set by the verbs, not the parser.** `cmd_direct_jira`/`cmd_direct_run` build each stage's namespace with `argparse.Namespace(**vars(args))` and override the stage-specific fields (detail's `force`/`dry_run`, jira's `lint`/`epic`/`max_hours`, run's `mode`/`all`/`commit`, etc.). Those overrides belong to steps 4–5. This step only ensures the *parent* namespace the parser produces carries the create-side fields the verbs copy from, plus the global flags already supplied by `make_base_parser`.
- **Wire the module into `plan_tool/cli/app.py`.** Add the two-line import pair next to the other command-module imports (`from plan_tool.cli import direct_cmd as _direct_commands` and `from plan_tool.cli.direct_cmd import cmd_direct_jira, cmd_direct_run`), then add `_direct_commands` to the `COMMAND_MODULES` tuple. A natural spot is beside the pipeline verbs (after `_run_commands` / near `_jira_commands`), but tuple order no longer drives help order, so anywhere in the tuple works.
- **Add both verbs to `_LOCKED_MUTATING_COMMANDS` in `plan_tool/cli/app.py`.** This is the key correctness gotcha. The repo mutation lock is acquired once at the `main()` dispatch seam from `args.command` (see the `repo_mutation_lock(... command=args.command, enabled=_requires_repo_mutation_lock(args))` call), *not* inside each handler. The composite verbs call `cmd_create`/`cmd_detail`/`cmd_run` directly, bypassing dispatch — so there is **no reentrancy deadlock**, but there is also no inner lock. If `direct-jira`/`direct-run` are absent from `_LOCKED_MUTATING_COMMANDS`, `_requires_repo_mutation_lock` returns `False` and the whole mutating chain runs unlocked, racing any concurrent plan-tool process on the manifest and plan files. Both verbs mutate (create/detail write, run commits), so both must be in the set.
- **Append to `CANONICAL_COMMAND_ORDER` in `plan_tool/cli/parser.py`.** `_reorder_subcommands` sorts registered subcommands by their index in this tuple; a command absent from it sorts after all canonical ones, so leaving them out is deterministic but ranks them last. Add `"direct-jira"` then `"direct-run"` so help order is intentional. Placing them next to `jira` / `run` reads best; the drift test only requires that the order you pick matches the docs you regenerate.
- **Regenerate the reference.** Run `python -m plan_tool.cli_reference --write` (`plan_tool/cli_reference.py:write_reference`). It reads the live parser, so once the verbs are registered it emits `docs/cli/direct-jira.md`, `docs/cli/direct-run.md`, and rewrites `docs/cli/README.md` with the two new rows. Commit the generated files exactly as emitted — hand-editing them re-introduces the drift the test catches.

Constraints and gotchas that are not free to vary:

- **`register` must return unique keys.** `assemble` asserts a command key is registered by only one module; `direct-jira`/`direct-run` are new, so no collision — but do not also register either name elsewhere.
- **The subparser `help=` string is the single source for three surfaces:** `plan-tool --help`, the README index row (`render_index`), and the reference file. Write one concise help line per verb.
- **Regenerate, don't hand-write, the three docs.** `docs/cli/direct-jira.md`, `docs/cli/direct-run.md`, and `docs/cli/README.md` are generator output. The step "creates" the two files only in the sense of running the generator.

## Tests

Add to `tests/cli/test_direct_cmd.py` (drive the **real** parser via `plan_tool.cli.build_parser()`; the `tests/cli/conftest.py` autouse gate fails the test if a backend spawns). Add one targeted test to `tests/cli/test_cli_reference.py`. Every new test must be green before the step is done.

- `test_direct_jira_registered_and_dispatches` — `build_parser().parse_args(["direct-jira", …])` resolves and the dispatch map routes `direct-jira` to `cmd_direct_jira`.
- `test_direct_run_registered_and_dispatches` — same for `direct-run` → `cmd_direct_run`.
- `test_direct_jira_namespace_is_field_complete` — parse a real `direct-jira` invocation and assert the namespace carries every create-side field the verb reads directly plus the global flags (`backend`, `model`, `on_rate_limit`, `fallback_backend`); stub the three stage handlers so no stage runs, and assert the verb completes without `AttributeError`.
- `test_direct_run_namespace_is_field_complete` — same for `direct-run`, including the run/reconcile-code direct-read fields the verb copies from the parent.
- `test_direct_verbs_in_locked_mutating_commands` — assert `"direct-jira"` and `"direct-run"` are in `plan_tool.cli.app._LOCKED_MUTATING_COMMANDS`, so `_requires_repo_mutation_lock` returns `True` for each.
- `test_direct_verbs_in_canonical_order` — assert both names appear in `plan_tool.cli.parser.CANONICAL_COMMAND_ORDER`.
- `test_direct_verbs_help_exits_zero` (integration) — `main(["direct-jira", "--help"])` and `main(["direct-run", "--help"])` exit 0.
- `tests/cli/test_cli_reference.py::test_direct_verbs_reference_is_generated` — mirror `test_scope_review_reference_is_generated`: `render_reference()` contains `direct-jira.md` and `direct-run.md`, and `README.md` links both. The existing `test_every_subcommand_has_a_reference_file`, `test_no_orphan_reference_files`, and `test_every_generated_file_matches_disk` already guard the committed set — regenerate the docs so they stay green.

## Acceptance criteria

- `plan_tool/cli/direct_cmd.py:register` returns `{"direct-jira": cmd_direct_jira, "direct-run": cmd_direct_run}` and both subparsers exist on the assembled parser.
- `plan_tool.cli.app.COMMAND_MODULES` includes the `direct_cmd` module, and `plan-tool direct-jira`/`plan-tool direct-run` dispatch to their handlers.
- `"direct-jira"` and `"direct-run"` are in `_LOCKED_MUTATING_COMMANDS`, so a mutating chain runs under the repo mutation lock.
- `"direct-jira"` and `"direct-run"` are in `CANONICAL_COMMAND_ORDER`.
- `docs/cli/direct-jira.md` and `docs/cli/direct-run.md` exist and match `render_reference()` output; `docs/cli/README.md` links both.
- `plan-tool direct-jira --help` and `plan-tool direct-run --help` exit 0.
- Parsing a real `direct-jira`/`direct-run` invocation yields a namespace complete against each downstream handler's direct-read fields — the chain runs (with stubbed stages) without `AttributeError`.
- All new tests in `tests/cli/test_direct_cmd.py` and `tests/cli/test_cli_reference.py` pass with no backend spawned.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — `add_subparsers`, `add_parser`, `add_help=False` parent parsers, and the `Namespace` shape the `register` seam builds on.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — stubbing the module-level stage handlers so the field-completeness tests never run a real stage or spawn a backend.

## Deferred

- **Flag-set tuning for the verbs** — which create-side flags each verb exposes is driven by what steps 4–5's handlers read; this step supplies exactly that set and does not add new operator knobs. Broadening the flag surface is out of scope.
- **Size-gate threshold configurability** — `MAX_CHAINABLE_STEPS` ships fixed; making it a flag/config value is deferred by the plan's `## Out of scope`.
- **Mid-chain resume/checkpoint** — a stage failure returns the standard non-zero exit with artifacts left on disk; chain-level rollback/resume is out of scope.
- **Shared `-y/--yes` consolidation** — the per-module `yes_parent` pattern stays duplicated until the shared flag is lifted into `plan_tool/cli/parser.py`; consolidating it is a separate refactor.
