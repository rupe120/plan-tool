# Step 8 — Add the standalone `scope-review` command (create-if-missing, unconditionally mutating) and register it across every drift-guard surface

## Summary

Add `plan-tool scope-review <name> [-y] [--rederive]`: a standalone command that surfaces a plan's concept tree and walks the operator through sign-off, independent of `create` or `detail`. It creates a tree when missing, walks a current tree without an emit, and owns the explicit refresh path for a stale tree: without `--rederive` it reports the fingerprint mismatch and refuses to consume the stale decisions; with the flag it emits, appends new nodes, preserves existing decisions, flags conflicts, saves the current fingerprint, and then navigates. The command remains unconditionally mutating with no recommend-only `--apply` gate and is registered across every CLI drift-guard surface. On green, interactive confirmation signs off, `-y` / non-TTY leaves nodes unsigned, and stale decisions are never silently used.

## Table of Contents

- [Why](#why) — the missing standalone entry point for the concept gate
- [Input](#input) — the step 1/2/3 contracts this command drives
- [Files (creates vs edits)](#files-creates-vs-edits) — one new module, one new test, one generated doc, plus registration edits
- [Implementation](#implementation) — the command handler, the create-if-missing/mutating rule, and every registration surface
- [Tests](#tests) — cold-start, existing-tree, gating, and registration coverage
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — argparse, dataclasses, RFC 3339
- [Deferred](#deferred) — coverage stamping, SKILL.md sync, run-log entry

## Why

Steps 4 and 5 wired the concept sign-off gate into `create` and `detail`, but both are authoring runs. A plan can reach a state where its concepts were never signed off and neither of those commands is the right thing to re-run: a plan created under `--yes`, a plan created before this feature, or a plan whose deferrals an operator wants to revisit after the fact without re-authoring anything. There is no way today to say "just show me this plan's concept tree and let me sign off." This step adds that one command — the third and last of the three wiring surfaces (`create` in step 4, `detail` in step 5, `scope-review` here). It gives every plan a standalone, operator-invoked path to the same tree, emitting one on the spot if the plan has never had concepts proposed. Half the work is behavior (a small handler that reuses the step 1–3 leaf); the other half is registering the verb so the drift guards that keep the CLI honest — the help golden, the generated reference, the capability catalog — do not go red.

## Input

This command drives contracts owned by earlier steps — reference them, do not re-specify them.

- **Step 2 — the concept-emit producer (`depends_on: 2`).** The command calls step 2's producer (recommended name `emit_concept_tree`) with the plan's evidence and gets back an `Optional[ConceptTree]` (fail-soft: `None` on an unparseable round-trip, never raises). The default real-CLI invoker is step 2's `shell_concept_invoker`, which routes through `plan_tool/shell.py:claude_invoke`, so the conftest real-backend gate covers it for free. Follow step 2's shipped signature for the evidence envelope and the invoker kwarg name — step 2 owns it.
- **Step 3 — the navigator (`depends_on: 3`).** The command calls `navigate_concepts(tree, *, prompt_fn, yes, save_fn)` and reads its frozen `ConceptDecision`. Step 3 owns the `yes → non-TTY → interactive` gate, the per-selection persistence, and the terminal sign-off stamp — this step does not re-implement any of it; it injects `prompt_fn`, `yes`, and a `save_fn` closure.
- **Step 1 — the sidecar (transitive).** `read_concepts(plan_path)` loads the tree fail-soft (`None` on a missing or unreadable sidecar); `save_concepts(plan_path, …)` is the single writer. Step 1 pins both on the **plan path** (mirroring `plan_tool/grounding.py:read_grounding` / `write_grounding`, which resolve the sidecar path internally); pass the plan path, not a pre-resolved `concepts_path(plan_path)`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/scope_review_cmd.py` — the command module: `cmd_scope_review(args)` handler and `register(subparsers) -> dict[str, Handler]`. Imports only the cycle-free CLI leaves (`plan_tool.cli.context`, `plan_tool.cli.parser`) and domain modules (`plan_tool.concept_tree`, `plan_tool.locator`, `plan_tool.parser`, `plan_tool.style`) — never `plan_tool.cli.app`.
  - `tests/cli/test_scope_review_cmd.py` — unit/integration tests for the command (cold-start emit, existing-tree walk, gating, registration).
  - `docs/cli/scope-review.md` — the generated per-subcommand reference. **Not hand-written** — produced by `python -m plan_tool.cli_reference --write`; listed here because the generator creates it.
- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — add the two-line import block near the `scope_out_cmd` import (`from plan_tool.cli import scope_review_cmd as _scope_review_commands` + `from plan_tool.cli.scope_review_cmd import cmd_scope_review`); append `_scope_review_commands` to the `COMMAND_MODULES` tuple; add `"scope-review"` to the `_LOCKED_MUTATING_COMMANDS` frozenset.
  - `plan_tool/cli/__init__.py` — add a `plan-tool scope-review <name>` line to the intent-grouped catalog docstring; add `"cmd_scope_review"` to `__all__`.
  - `plan_tool/cli/parser.py` — append `"scope-review"` to `CANONICAL_COMMAND_ORDER` (place it right after `"scope-out"`).
  - `CAPABILITIES.md` — add `scope-review` to an owning capability's `surfaces:` list so the `plan-tool validate` honesty check (`plan_tool/capability_catalog.py:check_capabilities`) does not flag it as an `orphan-subcommand`.
  - `docs/cli/README.md` — the generated index; regenerated by the cli-reference generator to include the new `scope-review` row.
  - `tests/cli/package_surface_help.golden.txt` — the `--help` snapshot; regenerated (the catalog docstring line and the subcommand metavar list both change).

## Implementation

**The command handler is thin and reuses the step 1–3 leaf.** `cmd_scope_review(args)` in `plan_tool/cli/scope_review_cmd.py` does, in order:

- **Resolve the plan.** `ctx = _load_context(args)`, `path = resolve_plan_for_context(ctx, args.name)`, and the slug via `slug_from_filename(path)` — exactly as `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` opens.
- **Load, reject stale, or derive the tree.** Call step 1's `read_concepts`. If it returns a current tree and `--rederive` is absent, use it without an emit. If the tree is stale and `--rederive` is absent, report the fingerprint mismatch, write nothing, and exit non-zero with an instruction to rerun with the flag; never navigate stale decisions. On cold start, deterministically seed every existing `## Out of scope` bullet as `wont_do`, every `## Deferred` bullet as `defer`, and every committed step as `include`, all unsigned. Then build the evidence envelope step 2 defines and call `emit_concept_tree(evidence)` only to enrich that guaranteed seed with hierarchy or additional evidence-backed concepts; merging must retain every seeded node even when the emit omits it. Save the merged tree. Re-derivation appends new nodes, preserves existing decisions, flags conflicts for explicit operator review, saves the refreshed tree with the current fingerprint, and only then starts the walk.
- **Handle a fail-soft enrichment miss.** If the cold-start `emit_concept_tree` returns `None` (unparseable round-trip), warn through `plan_tool/style.py:warn`, save and navigate the deterministic seed, and return success after review; the optional enrichment cannot block or erase guaranteed scope nodes. A truly empty deterministic seed plus an empty or unparseable emit is intentionally empty and still counts as completed.
- **Walk and sign off.** Call `navigate_concepts(tree, prompt_fn=input, yes=args.yes, save_fn=<closure>)`, where the closure calls `save_concepts` for the resolved plan path. Do not re-implement the gate — step 3 owns `yes → non-TTY → interactive` and the per-selection save.
- **Preserve independent parent/child decisions.** The command delegates the plan §C rule unchanged: cycling or accepting a parent never propagates to descendants, mixed markers are display-only, and a mixed subtree may be signed after every descendant-bearing frame is reviewed or accepted. Re-derivation and deterministic seeding preserve each node's own state rather than normalizing a subtree to its parent.
- **Render the outcome.** Print one line per `ConceptDecision` outcome (signed-off / accepted-unsigned / empty) via `success` / `info` / `warn` from `plan_tool/style.py`, mirroring `render_scope_out_result`'s one-branch-per-outcome shape. Return 0.

**"Unconditionally mutating" is the key design decision, and it is what makes this command different from `scope-out`.** `scope-out` is recommend-only unless `--apply` plus a confirm; it defends against carving a plan without an explicit opt-in. `scope-review` has no such gate: reviewing concepts *is* the point, and the tree is written by cold-start/re-derivation or by the walk's per-selection saves. There is **no `--apply` flag**. The flags are `-y/--yes` and `--rederive`: `--yes` changes sign-off, while `--rederive` explicitly authorizes refreshing an existing tree. Because a completed run writes to disk, `scope-review` must go in `_LOCKED_MUTATING_COMMANDS`.

**The `emit_concept_tree` reference must be a module-level name in `scope_review_cmd.py` so tests can stub it.** Import it as `from plan_tool.concept_tree import emit_concept_tree` and call the bare name. A test then monkeypatches `plan_tool.cli.scope_review_cmd.emit_concept_tree` to hand back a canned tree with no Claude call — the standard stub-the-module-level-proposal-function pattern. A test that forgets to stub trips the conftest real-backend gate through the default `shell_concept_invoker`; no conftest edit is needed (inherited coverage).

**`register(subparsers)` mirrors `scope_out_cmd.py`'s `register` minus the carve flags.** Build a local `-y/--yes` parent parser (the same idiom the other command modules use until the shared flag is consolidated), add the `name` positional and a `--rederive` boolean flag, and return `{"scope-review": cmd_scope_review}`. No `--step`, `--through`, or `--apply`. Keep the `help=` text short and factual — it feeds the generated reference verbatim.

**Each registration edit guards a different check:**

- **`COMMAND_MODULES` (app.py).** Append `_scope_review_commands`. `assemble` calls its `register` and merges the dispatch map. Registration order does not set help order (that is `CANONICAL_COMMAND_ORDER`), so append is fine.
- **`__all__` + the auto-mirror (`__init__.py`).** The `_package_globals.setdefault` loop already mirrors every `app` module global — since `cmd_scope_review` is imported into `app`'s namespace, it is auto-exported as `plan_tool.cli.cmd_scope_review`. That satisfies `tests/cli/test_package_surface.py:test_every_subcommand_has_a_dispatch_handler`, whose `_handler_name_for` maps `scope-review → cmd_scope_review` mechanically. Adding it to `__all__` keeps `import *` complete.
- **`CANONICAL_COMMAND_ORDER` (parser.py).** Append `"scope-review"` after `"scope-out"`. Without it the command sorts after every canonical name (its `_canonical_index` returns the tuple length) and lands in the trailing group, which is churny; naming it fixes a clean, deterministic help position.
- **The intent catalog docstring (`__init__.py`).** Add a `plan-tool scope-review <name>` one-liner. This docstring is the base-parser `description`, so it is embedded in the help golden — the edit changes `tests/cli/package_surface_help.golden.txt`.
- **`_LOCKED_MUTATING_COMMANDS` (app.py).** Add `"scope-review"`; the command writes the sidecar, so `_requires_repo_mutation_lock` must return `True` for it.
- **`CAPABILITIES.md`.** Add `scope-review` to a capability's `surfaces:`. Recommended home: the `plan-authoring` capability (id `plan-authoring`, surfaces `create`, `detail`, …) — `scope-review` runs the same operator concept sign-off gate `create` and `detail` run, standalone. The `plan-completeness` capability (concepts, coverage) is a defensible alternative; the honesty check only needs one valid capability to own the primary name. Pick one and cite no invalid principle ids.

**Regenerate the two drift-guarded artifacts, do not hand-edit them.** After the parser edits land, run `python -m plan_tool.cli_reference --write` to produce `docs/cli/scope-review.md` and refresh `docs/cli/README.md` (guarded by `tests/cli/test_cli_reference.py`), and re-baseline the help golden with `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py::...::test_help_matches_golden` (guarded by `test_help_matches_golden`). Both are mechanical outputs; editing them by hand diverges from the generator and reds the guard.

## Tests

New tests in `tests/cli/test_scope_review_cmd.py` (drive `main(["scope-review", ...])` or `cmd_scope_review(args)` through the real parse → dispatch path; stub `emit_concept_tree` at the module level so no Claude is spawned):

- `test_cold_start_seeds_then_enriches_without_omission` — no `concepts.json`; seed a plan with scope bullets and committed steps, stub `emit_concept_tree` with output that omits some seed items and adds hierarchy or evidence-backed concepts, then assert the persisted tree retains every seed item and includes the enrichment.
- `test_stale_tree_requires_rederive` — a fingerprint mismatch without `--rederive` reports the stale tree, writes nothing, never calls the navigator, and exits non-zero with the recovery command.
- `test_rederive_refreshes_before_navigation` — with an existing tree and `--rederive`, the emit runs, new nodes append, existing decisions survive, conflicts are flagged for review, the saved fingerprint is current, and navigation begins only after that save.
- `test_current_tree_is_walked_not_re_emitted` — a fingerprint-current `concepts.json` is present; the `emit_concept_tree` stub asserts it is **not** called; the walk still runs and persists.
- `test_yes_leaves_nodes_unsigned` — a `-y` run persists the tree with every node `signed_off=False`.
- `test_non_tty_leaves_nodes_unsigned` — a non-TTY run (stdin not a tty) persists the tree unsigned.
- `test_interactive_signoff_sets_flag` — a fake `input` feeding the `c` keystroke returns a `ConceptDecision` with `signed_off=True` and a stamped `signed_off_at`.
- `test_parent_decision_does_not_normalize_subtree` — cycling or accepting a parent preserves independently stored descendant states through save and re-run, including a mixed subtree.
- `test_emit_none_preserves_seed_and_exits_zero` — cold start where `emit_concept_tree` returns `None`; the command warns, persists every deterministically seeded scope bullet and committed step, navigates that tree, and returns 0.
- `test_scope_review_takes_repo_mutation_lock` — `"scope-review"` is in `_LOCKED_MUTATING_COMMANDS` and `_requires_repo_mutation_lock` returns `True` for it.
- `test_registered_in_parser_and_dispatch` — `build_parser()` exposes `scope-review`; `register` returns `{"scope-review": cmd_scope_review}`; `plan_tool.cli.cmd_scope_review` is a callable attribute.

Existing drift-guard tests that must stay green after regeneration (no new tests needed, they cover the new command automatically): `tests/cli/test_package_surface.py:test_help_lists_every_subcommand` / `test_help_matches_golden` / `test_every_subcommand_has_a_dispatch_handler`, `tests/cli/test_cli_reference.py:test_every_generated_file_matches_disk` / `test_no_orphan_reference_files`, and the `CAPABILITIES.md` honesty check via `plan_tool/capability_catalog.py`.

### Test-creation order (feature step)

This is a **feature** step — new behavior (a new command) plus registration. Write the `test_scope_review_cmd.py` cases alongside `cmd_scope_review`/`register`; write the registration assertions alongside the app.py/parser.py/__init__.py edits. Regenerate the two drift-guarded artifacts last, once the parser surface is final. Every new test and every existing drift-guard test must be green before this step is done.

## Acceptance criteria

- `plan-tool scope-review <name>` on a plan with no `plan-details/<slug>/concepts.json` writes a tree containing every deterministically seeded scope bullet and committed step plus any producer enrichment, and reads it back equal via `read_concepts`.
- `plan-tool scope-review <name>` on a plan with a current `concepts.json` walks the existing tree without re-emitting; a stale tree is reported and refused unless `--rederive` is supplied.
- `plan-tool scope-review <name> --rederive` refreshes an existing tree with append-new, preserve-existing, flag-conflicts semantics, saves the current fingerprint, and then navigates it.
- A `-y` run and a non-TTY run both persist the tree with every node `signed_off=False`.
- An interactive `c` keystroke returns a `ConceptDecision` with `signed_off=True` and a non-empty `signed_off_at`.
- Parent decisions never propagate to descendants, mixed markers remain display-only, and re-running the command preserves every node's independent state.
- A cold-start run deterministically persists every existing scope bullet and committed step before review; producer output may enrich but never omit that seed, and a producer `None` warns while preserving and reviewing the seed with exit 0.
- `"scope-review"` is in `_LOCKED_MUTATING_COMMANDS`; the command takes the repo-mutation lock.
- `build_parser()` registers `scope-review`; `plan_tool.cli.cmd_scope_review` is callable; `register` returns `{"scope-review": cmd_scope_review}`.
- `tests/cli/test_package_surface.py`, `tests/cli/test_cli_reference.py`, and the `CAPABILITIES.md` honesty check all pass with `scope-review` present.
- `docs/cli/scope-review.md` exists and `docs/cli/README.md` lists it; `python -m plan_tool.cli_reference --write` produces no further diff.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python docs)](https://docs.python.org/3/library/argparse.html) — `add_subparsers`, parent parsers, and the `register(subparsers)` seam this command module wires.
- [dataclasses — Data Classes (Python 3.13 docs)](https://docs.python.org/3/library/dataclasses.html) — shape of the frozen `ConceptDecision` this command reads back from `navigate_concepts`.
- [RFC 3339 — Date and Time on the Internet: Timestamps](https://www.rfc-editor.org/rfc/rfc3339) — the UTC format of `signed_off_at`, stamped by step 3's walker on the interactive confirm.

## Deferred

- **`covered_by` coverage stamping / recompute** — owned by step 6 (`check_concept_coverage` recomputes coverage by slug); `scope-review` never touches coverage.
- **The scope-out concept flip** — carving a step's `include` concepts to `defer` is step 7's concern; `scope-review` only signs off, it never carves.
- **`SKILL.md` "Subcommands at a glance" sync** — the catalog docstring says to keep `SKILL.md` in sync, but `SKILL.md` is not in this step's declared files and no test guards it; route the sync to reconcile (or add it if a guard later requires it).
- **A run-log entry for the emit round-trip** — `scope-review` spends one Claude call on cold-start emit but, like `scope-out` and `convergence`, need not open a `RunLogWriter`; adding run-log coverage is a separate follow-up if telemetry wants it.
- **Consolidating the local `-y/--yes` parent parser** — each command module still builds its own; the shared-flag consolidation into `plan_tool/cli/parser.py` is reconcile-owned, not this step.
