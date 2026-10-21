> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 4 — Wire `plan-tool quality-bench run` as an isolated CLI verb

## Summary

Add `plan-tool quality-bench run --corpus <dir> --label <name>` as a dedicated command group that forwards to the replay-and-store engine from step 3. Create `plan_tool/cli/quality_bench_cmd.py` for parsing, dispatch, exit handling, and operator output; register it through `plan_tool/cli/app.py` and document its generated CLI reference. Keep `quality-bench` distinct from `bench` in its command name, subaction destination, module, capability entry, and storage terminology. When green, a completed capture is available through the CLI under the repository mutation lock without changing the existing backend benchmark surface.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new command surface.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why the replay engine needs its own operator entry point.
- [Input](#input) — The step-3 engine contract and existing CLI seams this step uses.
- [Files (creates vs edits)](#files-creates-vs-edits) — New command files, registrations, and required generated artifacts.
- [Implementation](#implementation) — Command shape, dispatch, locking, capability registration, and generated reference rules.
- [Tests](#tests) — Parser, dispatch, lock, and generated-document coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completed command behavior.
- [References](#references) — Argument-parser reference for the nested command group.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this CLI work.
- [Deferred](#deferred) — Later subactions and unrelated benchmark work.

## Why

The existing `bench` command owns a separate backend-quality matrix with `bench run` and `bench report`; it is not an entry point for the fixed roadmap replay captured by step 3. The new engine needs an operator-facing command, but placing it under `bench` would mix two corpus formats, two storage roots, and two meanings of “run.” A separate top-level verb preserves both contracts. The quality-bench engine owns mutable capture locking so CLI dispatch must not take a competing outer lock, while later read-only comparison also stays unlocked.

## Input

- **Step 3 replay-and-store engine.** Step 3 creates the replay-and-store entrypoint, its capture result, error contract, label-replacement option, and optional invoker seam. Before wiring this handler, use the completed step’s public names and signature rather than an unimplemented symbol name from this detail.

- **CLI assembly.** `plan_tool/cli/parser.py:assemble` calls each command module’s `register(subparsers)` function and merges its returned command-to-handler map. `plan_tool/cli/app.py:COMMAND_MODULES` supplies that registry.

- **Existing benchmark boundary.** The existing `bench` command group defines separate `run` and `report` actions. Preserve them unchanged.

- **Mutation-lock policy.** `plan_tool/cli/app.py:_requires_repo_mutation_lock` controls the outer `repo_mutation_lock` call in `plan_tool/cli/app.py:main`. It must return false for every `quality-bench` subaction: mutable `run` and later `floor` acquire their one lock inside `quality_bench.py`, while `compare` is read-only. The CLI handler receives no lock token and never acquires a second lock.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/quality_bench_cmd.py` — Thin `quality-bench` parser registration, handler, engine forwarding, and operator-facing result rendering.
  - `tests/cli/test_quality_bench_cmd.py` — Integration-marked CLI dispatch and focused parser, lock, capability, and reference tests.
  - `docs/cli/quality-bench.md` — Generated reference for the new command group.

- **Existing files (edits only):**
  - `plan_tool/cli/parser.py` — Add `quality-bench` to `CANONICAL_COMMAND_ORDER` near `bench`.
  - `plan_tool/cli/app.py` — Import and register `quality_bench_cmd`; make `_requires_repo_mutation_lock` action-aware for `quality-bench`.
  - `CAPABILITIES.md` — Add one capability that owns the `quality-bench` command and its engine and command-module surfaces.
  - `docs/cli/README.md` — Required scope addition: regenerate the generated CLI index after the parser gains the new primary command.
  - `tests/cli/package_surface_help.golden.txt` — Required scope addition: refresh the checked-in top-level help snapshot after the primary command list changes.

## Implementation

- **Create one isolated command module.** Make `plan_tool/cli/quality_bench_cmd.py:register` add the top-level `quality-bench` parser and return only `{"quality-bench": cmd_quality_bench}`. Follow the leaf-import direction used by the existing `bench` and roadmap command modules: import CLI leaves and the domain engine, never `plan_tool/cli/app.py`.

- **Use a dedicated subaction destination.** Register `run` beneath `quality-bench` with a destination such as `quality_bench_action`, not the generic `action` used by the existing `bench` command. Keep the value and the command module named `quality_bench` so later `floor` and `compare` additions have one clear home.

- **Require explicit replay inputs.** `quality-bench run` must require `--corpus` and `--label`. Expose `--force` so the command can reach step 3’s existing collision-replacement behavior. Do not add a default corpus path, a backend matrix selector, or any `bench` option.

- **Keep the handler thin.** `plan_tool/cli/quality_bench_cmd.py:cmd_quality_bench` must resolve the requested repository through `plan_tool/cli/context.py:_resolve_cmd_repo_root`, then forward the parsed corpus path, label, force choice, repository root, and optional invoker seam to step 3’s engine. The handler must not repeat corpus validation, replay setup, label publication, recovery, metric calculation, or storage-path construction.

- **Preserve the test seam.** Give `cmd_quality_bench` an optional keyword-only invoker argument, following `plan_tool/cli/roadmap_cmd.py:cmd_roadmap`. Forward it only when supplied so ordinary `plan_tool/cli/app.py:main` dispatch retains the engine’s normal invoker behavior.

- **Report capture facts, not a quality verdict.** Render the completed label or stored-capture location and other result facts the step-3 result exposes. A completed capture must return zero regardless of its deterministic metric values; input refusal, failed capture, and interruption must retain the engine’s command-error behavior.

- **Register without changing `bench`.** Import the new module and `cmd_quality_bench` in `plan_tool/cli/app.py`, add the module to `COMMAND_MODULES`, and add `quality-bench` to `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`. Do not edit the existing `bench` command module, `plan_tool/bench.py`, or their parser shape.

- **Keep locking engine-owned.** Extend `plan_tool/cli/app.py:_requires_repo_mutation_lock` so every `quality-bench` subaction returns false. `quality-bench run` calls the step-3 engine, which acquires the one mutable-operation lock itself; reserve the same engine-owned behavior for the future `floor`, while `compare` remains read-only. This step does not register either future subaction.

- **Add the capability with the command.** Add one `CAPABILITIES.md` entry that names `quality-bench`, its step-3 engine module, and `plan_tool/cli/quality_bench_cmd.py` as surfaces, using the valid `deterministic-non-determinism` and `survive-interruption` principle ids. `plan_tool/capability_catalog.py:check_capabilities` must find neither an orphan command nor an absent cited surface.

- **Regenerate, do not hand-edit, CLI references.** Use `plan_tool/cli_reference.py:write_reference` after the parser is complete. Commit the generated `docs/cli/quality-bench.md`, updated `docs/cli/README.md`, and refreshed `tests/cli/package_surface_help.golden.txt`.

## Tests

Add the following cases in `tests/cli/test_quality_bench_cmd.py`.

### Tests for this step

- `test_quality_bench_run_requires_corpus_and_label` — The parser accepts `quality-bench run` only when both required options are present and records the dedicated `quality_bench_action` destination.

- `test_quality_bench_is_registered_separately_from_bench` — The assembled parser and dispatch map contain `quality-bench` and `cmd_quality_bench`, while `bench run` and `bench report` remain available.

- `test_quality_bench_run_forwards_capture_inputs_and_stubbed_invoker` — Mark as `integration`; parse the command through the CLI surface, invoke the command handler with a stubbed invoker, and assert the step-3 engine receives the resolved repository root, corpus path, label, force value, and the exact stub.

- `test_quality_bench_run_completed_capture_exits_zero_without_metric_gate` — A completed engine result containing deterministic measurements returns zero and prints capture facts without classifying the result as good or bad.

- `test_quality_bench_lock_policy_leaves_quality_bench_to_the_engine` — `_requires_repo_mutation_lock` returns false for `quality-bench run`, future `quality-bench floor`, and future `quality-bench compare`; the integration CLI route proves `run` reaches the engine’s one-lock capture entrypoint.

- `test_quality_bench_capability_entry_owns_registered_command` — The finished parser and `CAPABILITIES.md` pass `plan_tool/capability_catalog.py:check_capabilities` without a quality-bench ownership or surface finding.

- `test_quality_bench_reference_is_generated_from_parser` — `plan_tool/cli_reference.py:render_reference` produces `quality-bench.md` and links it from the generated CLI index.

- **Green-before-done gate** — Every test in `tests/cli/test_quality_bench_cmd.py` must pass, along with the generated-reference checks in `tests/cli/test_cli_reference.py` and help-surface checks in `tests/cli/test_package_surface.py`.

## Acceptance criteria

- `plan-tool quality-bench run --corpus <dir> --label <name>` parses, resolves the requested repository root, and forwards those values to the step-3 replay engine.

- Omitting either `--corpus` or `--label` is an argparse usage error before the engine runs.

- `--force` reaches the step-3 engine, while the handler does not recreate its validation, capture, or replacement logic.

- The new command registers as `quality-bench` with a `quality_bench_action` destination; `plan-tool bench run` and `plan-tool bench report` retain their current parser and dispatch behavior.

- `quality-bench run` reaches the engine-owned repository mutation lock exactly once; CLI lock policy leaves `run`, future `floor`, and read-only `compare` unlocked at dispatch.

- A completed capture returns exit code 0 without turning any deterministic metric into a gate or quality judgment.

- `CAPABILITIES.md` owns the new command and both quality-bench module surfaces, with no capability-catalog finding.

- Generated CLI references include `docs/cli/quality-bench.md`, the updated `docs/cli/README.md` index, and the refreshed top-level help golden file.

## References

- [argparse — Parser for command-line options, arguments and sub-commands](https://docs.python.org/3/library/argparse.html) — Use for the nested `quality-bench run` parser and required-option behavior.

## Applicable guardrails

- **The plan’s “## Step intent”, isolated command identity.** Keep this step as thin wiring to the step-3 engine and preserve the separate `quality-bench` namespace.

- **The plan’s “## Step intent”, mutation-lock split.** Make the lock decision depend on the subaction so capture work is protected and future read-only comparison remains unlocked.

- **The plan’s “## Out of scope”, report-only behavior.** Do not add a quality gate, a changed success code based on measurements, or an operator-facing quality decision.

- **The plan’s “## Out of scope”, bounded corpus route.** Do not extend this command into other verbs, corpus families, or concurrent replay work.

## Deferred

- `quality-bench floor` — Step 5 adds the mutating floor parser and its engine behavior.

- `quality-bench compare` — Step 6 adds the read-only comparison parser and its output.

- Changes to `plan_tool/bench.py` and the existing `bench` command module — The existing backend benchmark remains a separate command family.
