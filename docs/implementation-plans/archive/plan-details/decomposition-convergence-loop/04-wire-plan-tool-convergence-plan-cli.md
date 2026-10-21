# Step 4 — Wire `plan-tool convergence <plan>` CLI seam (handler, registration, generated reference)

## Summary

- Adds the **read-only `plan-tool convergence <plan>` subcommand** — the operator-facing front door to the steps 1–3 diagnosis engine. A new thin handler module `plan_tool/cli/convergence_cmd.py` resolves the plan, calls `load_report_history → diagnose_convergence → render_diagnosis`, prints the rendered block, and exits 0 regardless of verdict.
- Wires the module into the CLI: registers it in `COMMAND_MODULES` and re-imports `cmd_convergence` in `plan_tool/cli/app.py`, appends `"convergence"` to `CANONICAL_COMMAND_ORDER` in `plan_tool/cli/parser.py`, and adds the catalog line in `plan_tool/cli/__init__.py`.
- **Most important design decision:** the handler spends **zero Claude and never mutates** — it is shaped exactly like `cmd_status`/`cmd_validate` in `plan_tool/cli/inspect.py` (no `invoker`, no `RunLogWriter`), and honors the project exit-code convention: a completed diagnosis exits 0 even on a `spinning` verdict; `--fail-on-findings` is the only lever that flips rc to 1 on `spinning`.
- The generated reference (`docs/cli/convergence.md` + the `docs/cli/README.md` row) is produced by `python -m plan_tool.cli_reference --write`, never hand-edited; the `tests/cli/package_surface_help.golden.txt` snapshot is re-baselined with `UPDATE_CLI_GOLDEN=1`.
- On green: `plan-tool convergence <plan>` prints the spinning/converging verdict plus the forked copy-paste command for a plan with saved report history, exits 0, and the new `tests/cli/test_convergence_cmd.py` passes.

## Table of Contents

- [Why](#why) — the engine exists but has no operator entry point
- [Files (creates vs edits)](#files-creates-vs-edits) — one new handler + one new test + generated docs, four edits
- [Implementation](#implementation) — the handler, the registration seam, the catalog, the generated reference
- [Tests](#tests) — parse-surface + handler-behavior cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors
- [References](#references) — argparse + the docs-generation surface
- [Deferred](#deferred) — `--json`, auto-execution, verdict-reading left out of v1

## Why

- **Steps 1–3 built the whole diagnosis engine but no way to run it.** `plan_tool/convergence_diagnosis.py` exposes `load_report_history` (reader), `diagnose_convergence` (verdict), `classify_fork`, and `render_diagnosis` (operator-facing text) — all pure, all read-only — yet no subcommand calls them. An operator who suspects a plan's audit/apply loop is spinning has no command to confirm it and get the forked repair recommendation.
- **This step is the last layer:** a thin CLI seam that turns the in-memory diagnosis into a printed report. It follows the established discovery/inspection posture (read plan state, never call Claude) so it inherits the repo's read-only safety guarantees and the exit-0-regardless-of-verdict convention with no new machinery.

## Files (creates vs edits)

**New files:**
- `plan_tool/cli/convergence_cmd.py` — the `cmd_convergence` handler + its `register(subparsers)`; the whole new code surface for this step.
- `tests/cli/test_convergence_cmd.py` — parse-surface tests (subparser registered, positional + flags parse) and handler-behavior tests (verdict printed, exit-code convention, `--fail-on-findings` flip), driving `cmd_convergence` directly with a `Namespace`.
- `docs/cli/convergence.md` — generated reference for the new subcommand (produced by `python -m plan_tool.cli_reference --write`, not hand-authored).

**Existing files (edits only):**
- `plan_tool/cli/app.py`:
  - add `from plan_tool.cli import convergence_cmd as _convergence_commands` beside the other per-intent module imports,
  - add `from plan_tool.cli.convergence_cmd import cmd_convergence` so the handler is a module-level name `app` re-exports,
  - append `_convergence_commands` to the `COMMAND_MODULES` tuple.
- `plan_tool/cli/parser.py` — append `"convergence"` to `CANONICAL_COMMAND_ORDER` (placed in the audit cluster, right after `"completeness-apply"`).
- `plan_tool/cli/__init__.py`:
  - add the `plan-tool convergence` line under the `Audit` section of the catalog docstring,
  - add `"cmd_convergence"` to the `__all__` dispatch-handlers list.
- `docs/cli/README.md` — the `convergence` index row (regenerated, not hand-edited).

## Implementation

### `plan_tool/cli/convergence_cmd.py` (new)

**Module posture.** Mirror the sibling read-only command modules (`plan_tool/cli/inspect.py`, `plan_tool/cli/gates_cmd.py`). Top-level imports only the cycle-free leaves and domain packages — never `plan_tool.cli.app`:
- `argparse`, `sys` (stdlib),
- `from plan_tool.cli.context import _load_context`,
- `from plan_tool.cli.parser import Handler`,
- `from plan_tool.locator import resolve_plan_for_context`,
- `from plan_tool.convergence_diagnosis import (load_report_history, diagnose_convergence, render_diagnosis)`.
- **`plan_tool/convergence_diagnosis.py` is a cycle-free leaf** (its only `plan_tool` imports are `review_persistence`, `locator`, `convergence`, `granularity` — none import `plan_tool.cli`; `review` is reached only transitively via `review_persistence`), so the import is safe at module top. Do **not** body-localize it.

**The handler — `cmd_convergence(args: argparse.Namespace) -> int`.**
- **No `invoker`, no `RunLogWriter`, no mutation** — shaped exactly like `plan_tool/cli/inspect.py: cmd_status` / `cmd_validate`. v1 spends zero Claude; the engine already did all disk work.
- Body, in order:
  1. `ctx = _load_context(args)`.
  2. `path = resolve_plan_for_context(ctx, args.name)` — resolves slug / filename stem / `*.md` to the plan path, raising the usual name-resolution error upstream when the plan can't be found.
  3. `history = load_report_history(path)` — the step-1 reader; returns an empty `ReportHistory` when the plan has no `reports/` dir (no error).
  4. `diagnosis = diagnose_convergence(history)` — the step-2 detector; a short/empty history yields `verdict == "converging"`.
  5. `print(render_diagnosis(diagnosis))` — the step-3 renderer returns the full operator-facing block (verdict line + forked command for `spinning`); the CLI prints it verbatim and re-derives nothing.
  6. Exit-code: return `1` only when `getattr(args, "fail_on_findings", False)` **and** `diagnosis.verdict == "spinning"`; otherwise `0`.
- **Plan slug is not computed here.** `render_diagnosis` reads `diagnosis.plan_slug` (carried from the step-1 reader's `slug_from_filename(path)`), so the handler stays thin and the printed slug can't drift from the diagnosis.

**The exit-code convention (most important).**
- A completed diagnosis **exits 0 even when the verdict is `spinning`** — same rule as every audit verb (`completeness-audit`, `verify-all`, `validate`). The verdict is in the printed text, not the exit code.
- `--fail-on-findings` is the single opt-in that flips rc to `1` on a `spinning` verdict, mirroring `cmd_validate`'s `INVALID`→rc-1 arm. It never affects a `converging` verdict.

**`register(subparsers) -> dict[str, Handler]`.**
- Build a local `-y/--yes` parent and a local `--fail-on-findings` parent (`dest="fail_on_findings"`), copying the pattern in `plan_tool/cli/inspect.py: register` and `plan_tool/cli/gates_cmd.py: register` (shared-flag consolidation into `parser.py` stays deferred).
- `p = subparsers.add_parser("convergence", help="diagnose whether a plan's audit/apply loop is converging or spinning, and recommend the repair", parents=[yes_parent, fail_on_findings_parent])`.
- `p.add_argument("name", help="plan name — slug, filename stem (e.g. 1-my-feature), or filename.md")` — reuse `cmd_status`'s exact help string.
- `return {"convergence": cmd_convergence}`.

### `plan_tool/cli/app.py` (edits)

- **Import the module for the registry and re-import the handler name.** Beside the existing per-intent imports (e.g. the `_gates_commands` / `_annotate_commands` block near the bottom of the import section), add:
  - `from plan_tool.cli import convergence_cmd as _convergence_commands`,
  - `from plan_tool.cli.convergence_cmd import cmd_convergence`.
- **Why the second import matters:** `plan_tool/cli/__init__.py` mirrors every module-level name of `app` into the package namespace (the `for _name in dir(app)` loop), and `tests/cli/test_package_surface.py` checks each registered subcommand has a `cmd_<name>` handler attribute on `plan_tool.cli`. Re-importing `cmd_convergence` into `app` makes `plan_tool.cli.cmd_convergence` resolve.
- **Append to `COMMAND_MODULES`.** Add `_convergence_commands` to the tuple. Order here is **not** help-order-bearing (help order is fixed by `CANONICAL_COMMAND_ORDER`), so append it after `_skill_commands` (or beside the other audit-adjacent modules) — `assemble` calls each module's `register` and merges the dispatch maps.

### `plan_tool/cli/parser.py` (edit)

- **Append `"convergence"` to `CANONICAL_COMMAND_ORDER`**, placed right after `"completeness-apply"` so `plan-tool --help` groups it with the audit verbs.
- A command absent from this tuple sorts after all canonical ones, so this is the documented way to give the new command a fixed help position (`_reorder_subcommands` reads the tuple). Without the entry, `convergence` would float to the end of the help list — functional but ungrouped.

### `plan_tool/cli/__init__.py` (edits)

- **Catalog docstring.** Add one line under the `Audit` section (it is a read-only diagnostic over saved report history, a sibling of the read-only verify verbs), e.g.:
  - `    plan-tool convergence <name>             Diagnose whether a plan's audit/apply loop is converging or spinning across its saved report history; on spinning, print the forked repair command (split vs. re-seed). Read-only, no claude.`
- **`__all__`.** Add `"cmd_convergence"` to the `# Dispatch handlers` block so the curated `import *` surface stays complete (the mirror loop already surfaces it for `hasattr` checks; this keeps the explicit list honest).

### `docs/cli/convergence.md` + `docs/cli/README.md` (generated)

- **Do not hand-write either file.** Run `python -m plan_tool.cli_reference --write` after the parser changes land. The generator (`plan_tool/cli_reference.py: render_reference`) walks the assembled parser and emits one `convergence.md` (usage + the `name` argument + the `--yes` / `--fail-on-findings` options, read straight from the live actions) plus the `convergence` row in `README.md` from the subparser's `help=`.
- `tests/cli/test_cli_reference.py` regenerates in memory and fails on any diff, so the committed files must match the generator output exactly.

### Foundational logic and where else it lives

- **This step's core behavior is "resolve a plan → run the read-only diagnosis → print it → exit 0 (unless `--fail-on-findings` on spinning)."** The diagnosis logic is entirely owned by `plan_tool/convergence_diagnosis.py` (steps 1–3); this handler only routes and prints — it re-derives no verdict, no fork, no slug.
- **The read-only-resolve-and-print shape is shared** with `plan_tool/cli/inspect.py: cmd_status` and `cmd_validate` (both `_load_context` → `resolve_plan_for_context` → render, no Claude, no log). This handler matches them deliberately; no consolidation is warranted — each owns a distinct render.
- **The exit-0-regardless-of-verdict + `--fail-on-findings` rule** is the same convention enforced in `cmd_validate` (the `INVALID`→rc arm) and the audit verbs. This handler reuses the convention via the local `fail_on_findings` parent; no shared helper exists to import, matching how `inspect.py` builds its own parent.

## Tests

Reference file: `tests/cli/test_convergence_cmd.py`. Follow the split-proof conventions in `tests/cli/` — drive `cmd_convergence` directly with a `Namespace` (no `plan_tool.cli` global patched), build the parse surface via `assemble("desc", (convergence_cmd,))[0]`, and seed report history on disk so the real `load_report_history` path runs.

**Parse-surface cases:**
- `test_convergence_subparser_registered` — `assemble("desc", (convergence_cmd,))[0]` registers a `convergence` subparser.
- `test_convergence_parses_name_positional` — `sub.parse_args(["1-my-plan"]).name == "1-my-plan"`.
- `test_fail_on_findings_defaults_off` — `sub.parse_args(["p"]).fail_on_findings is False`; `--fail-on-findings` sets it `True`.
- `test_yes_flag_parses` — `-y` / `--yes` parses (parent inherited).

**Handler-behavior cases** (seed a temp plan + `reports/*.json`; reuse the spinning series from `tests/fixtures/convergence/sample-report-history.json` written into the plan's reports dir, mutate inline for converging):
- `test_spinning_plan_prints_verdict_and_command` — a spinning report history → stdout contains `spinning`, `shape:`, and a `plan-tool split` / `plan-tool create --from-existing` command.
- `test_spinning_exits_zero_by_default` — spinning verdict, no `--fail-on-findings` → rc `0` (exit-code convention).
- `test_spinning_with_fail_on_findings_exits_one` — spinning verdict + `fail_on_findings=True` → rc `1`.
- `test_converging_prints_converging_and_exits_zero` — a converging/short history → stdout contains `converging`, no `→`/split line, rc `0`.
- `test_converging_with_fail_on_findings_still_zero` — converging + `fail_on_findings=True` → rc `0` (the flag never flips a converging verdict).
- `test_no_report_history_is_converging` — a plan with no `reports/` dir → empty history → converging line printed, rc `0` (no crash).
- `test_handler_spends_no_claude_no_mutation` — `cmd_convergence` takes no `invoker`, writes no files, and the plan/report files are unchanged after the call (guards the read-only invariant; the autouse backend gate in `tests/conftest.py` also ensures no `claude` binary is spawned).

**Cross-cutting (regenerated, asserted elsewhere):**
- After the parser edits, `tests/cli/test_cli_reference.py` and `tests/cli/test_package_surface.py` must pass — regenerate `docs/cli/` with `python -m plan_tool.cli_reference --write` and re-baseline the help golden with `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py`. `test_package_surface.py: test_help_lists_every_subcommand` and the registration-seam test confirm `convergence` has a reachable `cmd_convergence` handler.

### Test-creation order (feature step)

- This is a **feature** step — new behavior. Write the parse-surface tests first (they pass as soon as `register` exists), then the handler-behavior tests alongside `cmd_convergence`'s body (verdict print, then the exit-code/`--fail-on-findings` matrix, then the empty-history and no-mutation guards).
- **Green-before-done gate:** every new test in `tests/cli/test_convergence_cmd.py` must pass, and the regenerated `docs/cli/` + help-golden must leave `tests/cli/test_cli_reference.py` and `tests/cli/test_package_surface.py` green, before this step is finished. Run `uv run pytest tests/cli/test_convergence_cmd.py tests/cli/test_cli_reference.py tests/cli/test_package_surface.py -q`.

## Acceptance criteria

- `plan-tool convergence <plan>` resolves the plan, prints the `render_diagnosis` block, and exits `0` for both `spinning` and `converging` verdicts.
- With `--fail-on-findings`, the command exits `1` on a `spinning` verdict and `0` on a `converging` verdict.
- A plan with no saved report history prints the `converging` line and exits `0` (no crash).
- `cmd_convergence` takes no `invoker`, spends no Claude, and mutates no files (verified by the read-only test and the autouse backend gate).
- `convergence` appears in `plan-tool --help`, grouped with the audit verbs (positioned after `completeness-apply` via `CANONICAL_COMMAND_ORDER`).
- `plan_tool.cli.cmd_convergence` resolves as a package attribute (re-imported through `app`), and the parser↔handler correspondence test passes.
- `docs/cli/convergence.md` and the `convergence` row in `docs/cli/README.md` match `python -m plan_tool.cli_reference --write` output; `tests/cli/test_cli_reference.py` passes.
- `plan_tool/cli/convergence_cmd.py` imports cleanly with no import cycle (`python -c "import plan_tool.cli.convergence_cmd"` succeeds).

## References

- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — `add_parser` / parent parsers (`parents=`) / `parse_args` for the thin `register` seam and the `name` positional + `--fail-on-findings` flag.
- [pathlib — Object-oriented filesystem paths — Python documentation](https://docs.python.org/3/library/pathlib.html) — `Path` handling for the resolved plan path passed to `load_report_history`.

## Deferred

- **`--json` machine output** — v1 prints only the human-readable `render_diagnosis` block; a structured JSON form (verdict, regions, fork) mirroring `completeness-audit --json` is a later follow-up.
- **Auto-executing the recommended repair** — the command prints the `plan-tool split …` / `plan-tool create --from-existing …` command but never runs it; wiring an opt-in + TTY-gated executor is the plan's deferred item (owned by `plan_tool/create.py: _apply_step_split` for the localized split).
- **Reading apply verdicts from the report sidecar** — the diagnosis keys on recurrence + no-shrinkage + `report_bytes` growth because the saved report JSON does not persist per-finding verdicts (carried from step 1); surfacing a structured `BLOCKED`/`granularity-split` signal waits on upstream sidecar persistence (noted in step 3).
- **Run logging** — read-only inspection verbs (`status`, `validate`) write no `RunLogWriter` entry, and `convergence` follows them; logging a no-Claude diagnostic is out of scope.
