> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Wire the roadmap command into the CLI, the help catalog, and the generated docs/cli reference

## Summary

This step creates `plan_tool/cli/roadmap_cmd.py`, a thin per-intent command module exposing `register(subparsers)` and `cmd_roadmap`, and wires it into the rest of the CLI package: `plan_tool/cli/parser.py`'s `CANONICAL_COMMAND_ORDER`, `plan_tool/cli/app.py`'s import block, `COMMAND_MODULES` tuple, and `_LOCKED_MUTATING_COMMANDS` frozenset, and `plan_tool/cli/__init__.py`'s intent-organized docstring catalog and `__all__`. `cmd_roadmap` does nothing but resolve `repo_root`/`plans_dir`, call step 4's `run_roadmap`, and map its result onto an exit code and a short printed summary — no assembly, gate, or retry logic lives here. The step also regenerates the two derived artifacts that a new subcommand always invalidates (`tests/cli/package_surface_help.golden.txt` via the suite's self-seeding `UPDATE_CLI_GOLDEN=1` re-run, and `docs/cli/roadmap.md` plus `docs/cli/README.md`'s index row via `python -m plan_tool.cli_reference --write`), and adds one new entry to `CAPABILITIES.md` mapping the `roadmap` surface to the MISSION principles it serves. On green, `plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]` is a real, discoverable, exit-code-correct CLI verb with no test, doc, or catalog drift anywhere in the package.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why the orchestrator built in steps 1–6 is still unreachable from the command line.
- [Input](#input) — the landed symbols this step wires together and the CLI-package contracts it must follow.
- [Files (creates vs edits)](#files-creates-vs-edits) — one new command module, one new test file, and the generated/catalog edits.
- [Implementation](#implementation) — the handler, the parser/package wiring, the golden and docs regeneration, and the rules that are not free to vary.
- [Tests](#tests) — the 20 cases and the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs worth reading for the argparse wiring decisions.
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences that bind this step.
- [Deferred](#deferred) — what other steps own, and the flags this step deliberately does not add.

## Why

Steps 1–6 built a working two-stage arc — the artifact contract, the gates, the orchestrator, and both prompts — but nothing on the command line can reach it. `plan_tool/roadmap.py:run_roadmap` is only ever called from `tests/test_roadmap.py`, `plan-tool --help` says nothing about the verb, `docs/cli/` has no reference page for it, and `plan-tool validate`'s capability-catalog honesty check would flag `roadmap` as an orphan subcommand the moment it existed without a `CAPABILITIES.md` entry. This step is the last hop from "the orchestrator works" to "an operator can run it": it is pure wiring, deliberately free of any decision steps 1–6 already made — the stage table, the gate sets, the retry policy, and the artifact contract are all fixed inputs here, not things this step designs.

## Input

This step consumes the outcomes of steps 1, 2, 4, 5, and 6, plus the CLI package's own layering contracts. **The landed names win over any name this file suggests** — open each module and use what actually shipped.

- **Step 4 produces the orchestrator entry point** — `plan_tool/roadmap.py`: `run_roadmap`, taking (at minimum) a slug, the concept-brief path, `repo_root`, `plans_dir`, an `invoker=` seam defaulting to the module's own shell invoker, and a `from_stage` re-entry parameter; and a frozen `RoadmapResult` whose closed `outcome` vocabulary has exactly two members — the run completed, or a stage exhausted its retry budget. A `RoadmapError` covers every pre-flight failure: bad slug, missing brief, missing or malformed upstream artifact, `from_stage` out of range, missing prompt template. Step 4's Implementation notes one wrinkle worth reading before writing the `except` clause: "a malformed upstream artifact surfaces as step 1's parse error… let it propagate as a run failure rather than catching it into a violation" — so the CLI layer may need to catch **both** `RoadmapError` and step 1's own artifact-contract error type for that one case. Confirm which it actually is once step 4 has landed and catch accordingly.
- **Step 1 produces the artifact contract's error type** — `plan_tool/roadmap_artifacts.py`'s parse/load error, modeled on `plan_tool/jira_grade.py:JiraGradeContractError`, carrying the offending path. This is the type step 4's "surfaces as step 1's parse error" note refers to.
- **`RoadmapResult` carries what the handler prints** — per step 4: the artifacts written, the stages run, the count of `pending` decisions across those artifacts, and — on the stage-exhausted outcome — which stage failed and its final violation list. Step 4 explicitly leaves rendering this to step 7: "the rc mapping itself belongs to step 7. This module returns facts; it never calls `sys.exit` and never prints an operator-facing summary."
- **The CLI package's registration seam** — `plan_tool/cli/parser.py`: `Handler = Callable[[argparse.Namespace], int]`, `CANONICAL_COMMAND_ORDER` (the tuple that fixes `--help` display order independent of registration order), and `assemble`, which calls each command module's `register(subparsers) -> dict[str, Handler]` and asserts no two modules register the same command name.
- **The CLI package's per-intent module shape** — every existing sibling (`plan_tool/cli/scope_out_cmd.py`, `plan_tool/cli/annotate_cmd.py`, `plan_tool/cli/worktree_cmd.py`) imports only the cycle-free leaves (`plan_tool.cli.context`, `plan_tool.cli.parser`, `plan_tool.cli.console`) plus domain packages, and never `plan_tool.cli.app`. `plan_tool/cli/annotate_cmd.py:cmd_annotate` is the closest shape to copy: a Claude-invoking, non-interactive, single-pass verb exposing an `invoker=` keyword seam defaulting to `None` so `main()`'s bare `dispatch[args.command](args)` call still works, with the real default resolved inside the function.
- **`plan_tool/create.py`'s two resolution helpers** — `resolve_output_dir(repo_root, override=None)` (default `<repo_root>/docs/implementation-plans`, the same constant step 1's path helper composes `roadmaps/<slug>/` under) and the repo-root resolution `cmd_create` itself uses. `plan_tool/cli/authoring.py:cmd_create` calls `_resolve_cmd_repo_root(args)`, **not** `_load_context(args)`, for exactly the reason this step needs: `_load_context` → `build_plan_tool_context` can raise `ManifestError` in manifest mode when no candidate repo root resolves any registered plan — precisely the state of a brand-new project with nothing in `.plan-tool/plans.json` yet, which is `roadmap`'s primary target audience (it is the verb "one rung above `create`," per the plan Overview). `_resolve_cmd_repo_root` never raises; it falls back to `cwd` instead.
- **The capability-catalog honesty check** — `plan_tool/capability_catalog.py:check_capabilities`, run by `plan-tool validate`. `CAPABILITY_ALLOWLIST` is an empty frozenset (no grace period), and it fires `orphan-subcommand` for any registered subcommand with no owning `CAPABILITIES.md` entry and `absent-surface` for a capability citing a surface (subcommand name or `path/to/file.py`) that doesn't exist at HEAD — so the new `CAPABILITIES.md` entry must land in this same step, not step 8.
- **The generated docs/cli reference** — `plan_tool/cli_reference.py`: `render_reference()` walks `plan_tool.cli.build_parser()`'s live argparse actions, so `docs/cli/roadmap.md` and the `docs/cli/README.md` index row need no hand-authoring — running `python -m plan_tool.cli_reference --write` produces both from the registered subparser once step 7's other edits land. `tests/cli/test_cli_reference.py` is the drift guard; it fails (not skips) if the committed files don't match.
- **The self-seeding golden help snapshot** — `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` compares `cli.build_parser().format_help()` (rendered at a fixed `COLUMNS=80`) against `tests/cli/package_surface_help.golden.txt`. Setting `UPDATE_CLI_GOLDEN=1` before running that one test rewrites the golden file from the live parser — this is the mechanism to use; hand-editing the file to match argparse's exact wrapping is error-prone and unnecessary.
- **What this step cannot verify.** No amount of CLI-layer testing proves the orchestrator itself is correct — that is steps 1–6's suites. This step's tests stub `run_roadmap` and assert only that the handler resolves paths correctly, calls it with the right arguments, and maps its result onto the right exit code and printed summary.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/roadmap_cmd.py` — the command module: `register(subparsers)` and `cmd_roadmap`.
  - `tests/cli/test_roadmap_cmd.py` — the suite listed under [Tests](#tests).
  - `docs/cli/roadmap.md` — generated by `python -m plan_tool.cli_reference --write`, never hand-authored (see `plan_tool/cli_reference.py`'s own module docstring).
- **Existing files (edits only):**
  - `plan_tool/cli/parser.py` — add `"roadmap"` to `CANONICAL_COMMAND_ORDER`.
  - `plan_tool/cli/app.py` — import `roadmap_cmd` and `cmd_roadmap` alongside the other per-intent modules, add the module to `COMMAND_MODULES`, and add `"roadmap"` to `_LOCKED_MUTATING_COMMANDS`.
  - `plan_tool/cli/__init__.py` — add a new intent section to the module docstring (the catalog `plan-tool --help` renders) and add `"cmd_roadmap"` to `__all__`. No other edit is needed here: the package's existing `for _name in dir(app): … setdefault(...)` mirror loop already re-exports `cmd_roadmap` once `app.py` imports it.
  - `tests/cli/package_surface_help.golden.txt` — regenerated via `UPDATE_CLI_GOLDEN=1`, not hand-edited.
  - `docs/cli/README.md` — regenerated via `python -m plan_tool.cli_reference --write`, not hand-edited.
  - `CAPABILITIES.md` — add one new capability entry for the roadmap surface.

## Implementation

### `plan_tool/cli/roadmap_cmd.py`

- **`register(subparsers) -> dict[str, Handler]`** adds one subparser, `roadmap`, with:
  - `slug` — a required positional (`str`), matching `create`'s slug in shape but always required: `roadmap` has no interactive slug-confirmation prompt to fall back to (see [Applicable guardrails](#applicable-guardrails)).
  - `--from-existing` — required, `type=Path`, the concept-brief path. Named identically to `create`'s own `--from-existing` flag for the same purpose (a written file, not inline prose) — deliberately no `--from <description>` inline alternative; the plan's Overview and BACKLOG #208's Outcome line both spell the invocation as `--from-existing <concept.md>` only.
  - `--from-stage` — optional, `type=int`, `default=1`. **Do not add a `choices=` restriction.** The valid range depends on `len(STAGES)`, which `run_roadmap` already checks and raises `RoadmapError` for; hardcoding "1 or 2" into the argparse layer would bake this plan's two-stage table into the CLI and break the day BACKLOG #208's `roadmap-02-components` stage lands a third entry.
  - No `--iterate`, no `-y`/`--yes`, no confirm flag of any kind — the orchestrator has no interactive surface to gate (see [Applicable guardrails](#applicable-guardrails)).
- **`cmd_roadmap(args: argparse.Namespace, *, invoker=None) -> int`** mirrors `plan_tool/cli/annotate_cmd.py:cmd_annotate`'s keyword-seam shape so `main()`'s bare `dispatch[args.command](args)` call keeps working while tests can still inject a canned invoker:
  1. Resolve `repo_root` via `plan_tool/cli/context.py:_resolve_cmd_repo_root(args)` — not `_load_context(args)`, per the reasoning in [Input](#input).
  2. Resolve `plans_dir`: `plan_tool/locator.py:resolve_explicit_plans_dir(args.plans_dir)` (the same global `--plans-dir` / `PLAN_TOOL_PLANS_DIR` precedence every other command honors), falling back to `plan_tool/create.py:resolve_output_dir(repo_root)` when that returns `None` — the same default `<repo_root>/docs/implementation-plans` step 1's path helper composes `roadmaps/<slug>/` under.
  3. Call `run_roadmap` with the resolved slug, brief path, `repo_root`, `plans_dir`, and `from_stage`; pass `invoker=invoker` only when the caller supplied one, so `run_roadmap`'s own default shell seam is otherwise left untouched.
  4. Catch `RoadmapError` (and, per [Input](#input), whichever type actually carries the malformed-re-entry-artifact case) — print via `plan_tool/style.py:error` and return a usage-shaped code. `plan_tool/cli/scope_out_cmd.py:cmd_scope_out`'s out-of-order `--through` range and `plan_tool/cli/authoring.py:cmd_create`'s `resolve_create_slug` failure are the precedent for mapping an input-shaped pre-flight failure to `2`.
  5. On a `RoadmapResult`, branch on `outcome`:
     - **Completed** → print a short summary (`success`/`detail` from `plan_tool/style.py`, matching every sibling handler): each written artifact's short-relative path, and the `pending` decision count when it is non-zero. Return `0` — including when `pending` is non-zero, per the plan's explicit "a completed run exits 0 even when the written artifacts carry `pending` decisions" acceptance criterion.
     - **Stage exhausted** → print the failed stage and its final violation list, one `- {message}` bullet per violation (mirroring the retry-suffix rendering step 4 already uses internally), and suggest fixing the brief or an already-written upstream artifact and re-running with `--from-stage <N>`. Return a non-zero code — `1` is the precedent `plan_tool/cli/annotate_cmd.py:cmd_annotate` sets for "the verb ran but did not finish" (its `AnnotateError`/unparseable-response path), distinct from the usage-shaped `2` above.
- **No orchestration logic lives in this module.** No stage table, no gate call, no retry loop, no invoker default beyond the pass-through in step 3 above — this is the plan's own acceptance criterion for the file ("`plan_tool/cli/roadmap_cmd.py` contains no assembly, gate, or retry logic"), checkable with `rg 'STAGES|gate_set|MAX_STAGE_ATTEMPTS' plan_tool/cli/roadmap_cmd.py` returning nothing.

### Wiring into `parser.py` / `app.py` / `__init__.py`

- **`plan_tool/cli/parser.py`: `CANONICAL_COMMAND_ORDER`.** Insert `"roadmap"` immediately before `"create"`. The plan's own Overview frames the verb as "one rung above `create`," and the existing docstring catalog already groups commands by workflow position (Discovery → Authoring → …) — placing `roadmap` right before the authoring group matches that read. The rejected alternative — appending it at the tuple's end, as most net-new commands historically have been — would put it *after* `worktree`, misrepresenting a pre-authoring verb as an afterthought in the help text's reading order.
- **`plan_tool/cli/app.py`:**
  - Import block: add `from plan_tool.cli import roadmap_cmd as _roadmap_commands` and `from plan_tool.cli.roadmap_cmd import cmd_roadmap`, grouped beside the `_authoring_commands` / `cmd_create` / `cmd_detail` imports (same rationale as the `CANONICAL_COMMAND_ORDER` placement — it precedes authoring in the intended workflow).
  - `COMMAND_MODULES`: add `_roadmap_commands` to the tuple. Registration order here doesn't affect `--help` display order (`_reorder_subcommands` handles that from `CANONICAL_COMMAND_ORDER`), but placing it beside `_authoring_commands` keeps the tuple's grouping readable.
  - `_LOCKED_MUTATING_COMMANDS`: add `"roadmap"`. It writes files (the two artifacts, plus the run log) and must hold the repo mutation lock like every other file-writing verb; a run without the lock could interleave with a concurrent `create`/`detail`/`run` writing under `.plan-tool/`.
- **`plan_tool/cli/__init__.py`:**
  - Module docstring: add a new intent section, positioned between "Discovery & inspection" and "Authoring" (matching the `CANONICAL_COMMAND_ORDER` placement above). One way to word it, matching the existing sections' one-line-per-command style:
    ```
    Roadmap — turn a concept brief into staged architecture artifacts, one rung above `create`.
      plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]   Non-interactively stage a concept brief into gated 01-domain.md / 02-constraints.md architecture artifacts under docs/implementation-plans/roadmaps/<slug>/; deterministic gates retry each stage's Claude call before writing; exits non-zero only when a stage exhausts its retry budget. --from-stage N re-enters at a stage, re-reading upstream artifacts (including hand edits) from disk.
    ```
    Editing this docstring changes `plan-tool --help`'s literal output, so it must be followed by the golden-snapshot regeneration below — do not hand-patch the golden file to match instead.
  - `__all__`: add `"cmd_roadmap"`, positioned near `"cmd_create"` / `"cmd_detail"` alongside the other dispatch-handler entries, matching every other registered subcommand's handler being listed there.

### Regenerating the golden help snapshot and the docs/cli reference

- **Golden help snapshot.** After the docstring and parser edits land, run:
  ```
  UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden -q
  ```
  then re-run the same test without the env var to confirm it's green. This rewrites `tests/cli/package_surface_help.golden.txt` from the live parser (`tests/cli/test_package_surface.py`'s `_render_help`, fixed at `COLUMNS=80`) — the mechanism the suite's own docstring documents ("self-seeding… set `UPDATE_CLI_GOLDEN=1` to re-baseline after an intentional help change").
- **Generated CLI reference.** Run:
  ```
  python -m plan_tool.cli_reference --write
  ```
  This writes `docs/cli/roadmap.md` (new) and updates `docs/cli/README.md`'s index table (new row) from the same live parser. `tests/cli/test_cli_reference.py`'s drift-guard tests must be green afterward with no further edits.

### `CAPABILITIES.md`

Add one new entry, matching the existing entries' shape (`id`, `surfaces`, `principles`, optional prose). A workable shape:

- **id:** `architecture-roadmap` (or similar — a stable kebab-slug distinct from every existing id)
- **surfaces:** `roadmap`, `plan_tool/roadmap.py`, `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, `plan_tool/cli/roadmap_cmd.py`
- **principles:** `converge-on-correct-plan` (the gate-retry loop only admits a stage response that clears its gates), `deterministic-non-determinism` (Claude runs only inside a stage; deterministic gates decide whether its output counts — `MISSION.md`'s principle 2 stated almost verbatim)

Every cited surface must exist at HEAD by the time this step runs — all five do, since steps 1, 2, 4, and this step land them, and step 7 depends on step 6. Don't cite `plan_tool/prompts/roadmap-domain.md` / `roadmap-constraints.md`: `check_capabilities`'s `_surface_exists` treats any `surface` ending `.py` or containing `/` as a path check, and prompt templates aren't `.py` files, so they'd need the `/`-in-path branch — simpler to omit them, since the four Python modules plus the subcommand name already cover the capability.

### Constraints that are not free to vary

- **The handler is thin.** No stage table, no gate function, no retry constant, no prompt-template path — everything past "call `run_roadmap` and map the result" belongs to steps 1–6.
- **No new interactive surface.** No `input()`, no `isatty()`, no confirm gate, no `-y`/`--yes` flag — mirroring step 4's own "no interactive surface" constraint at the CLI layer.
- **`--from-stage` takes no `choices=`.** See the bullet above; a hardcoded range would silently break the next roadmap plan in the arc.
- **The new `CAPABILITIES.md` entry lands in this step, not step 8.** `check_capabilities`'s `CAPABILITY_ALLOWLIST` is empty — there is no grace period during which `roadmap` can be a registered-but-uncataloged subcommand without `plan-tool validate` flagging it.
- **Regenerate, never hand-edit, the golden help snapshot and the docs/cli reference.** Both are mechanically derived from the live parser; a hand-edit that doesn't byte-match what the generator would produce fails the respective drift-guard test.

## Tests

All cases live in `tests/cli/test_roadmap_cmd.py`, following the CLI-integration conventions `tests/cli/test_scope_out_cmd.py` and `tests/cli/test_package_surface.py` already use: build a parser via `plan_tool.cli.build_parser()` or drive `main([...])` against a `tmp_path` repo, and stub `run_roadmap` (imported into `plan_tool.cli.roadmap_cmd`'s own namespace) rather than spawning a backend. This is a `feature` step in a plan with `enforce_step_tests: true`, so the test-authoring gate applies and this file must land with the module.

### Tests for this step

20 cases. Every one must be green before this step is finished.

**Argparse wiring**

- `test_register_returns_the_roadmap_dispatch_entry` — `register(subparsers)` returns `{"roadmap": cmd_roadmap}` and adds exactly one subparser.
- `test_slug_positional_is_required` — omitting the slug positional exits via argparse usage error.
- `test_from_existing_is_required` — omitting `--from-existing` exits via argparse usage error.
- `test_from_stage_defaults_to_one` — parsing with no `--from-stage` yields `args.from_stage == 1`.
- `test_from_stage_parses_as_int` — `--from-stage 2` yields `args.from_stage == 2`, not the string `"2"`.
- `test_help_documents_from_existing_and_from_stage` — `plan-tool roadmap --help` output names both flags.
- `test_roadmap_help_has_no_interactive_flags` — `--iterate` / `-y` / `--yes` are absent from `plan-tool roadmap --help`.

**Repo-root / plans-dir resolution**

- `test_cmd_roadmap_resolves_repo_root_without_a_registered_manifest` — a `tmp_path` repo with no `.plan-tool/plans.json` does not raise `ManifestError` through `cmd_roadmap` (with a stub `run_roadmap`).
- `test_plans_dir_defaults_to_docs_implementation_plans` — no `--plans-dir` override → the `plans_dir` argument reaching `run_roadmap` is `<repo_root>/docs/implementation-plans`.
- `test_plans_dir_override_reaches_run_roadmap` — `--plans-dir <other>` changes the resolved `plans_dir` argument.

**Dispatch → orchestrator wiring**

- `test_cmd_roadmap_calls_run_roadmap_with_the_parsed_slug_and_paths` — a stubbed `run_roadmap` receives the parsed slug, `--from-existing` path, resolved `repo_root`/`plans_dir`, and `from_stage`.
- `test_cmd_roadmap_forwards_a_supplied_invoker` — `cmd_roadmap(args, invoker=fake)` reaches `run_roadmap`'s `invoker=` keyword.
- `test_cmd_roadmap_omits_invoker_kwarg_when_none_supplied` — the default dispatch path (`invoker=None`) does not override `run_roadmap`'s own default seam.

**Outcome → exit code and summary**

- `test_completed_outcome_returns_zero_and_prints_written_artifacts` — a stubbed completed `RoadmapResult` maps to rc 0 and each artifact path appears in the printed summary.
- `test_completed_outcome_with_pending_decisions_still_returns_zero` — a non-zero `pending` count on a completed result still returns 0.
- `test_stage_exhausted_outcome_returns_nonzero_and_names_the_failed_stage` — the printed summary names the failed stage and includes each violation message.
- `test_roadmap_error_returns_a_usage_shaped_code_and_prints_the_message` — a stubbed `RoadmapError` (e.g. an out-of-range `--from-stage`) is caught, its message printed, and a non-zero usage-shaped code returned — not left to `main()`'s generic exception handler.
- `test_malformed_upstream_artifact_error_is_caught_at_the_cli_layer` — whichever exception type step 4 actually lets propagate for a broken re-entry artifact (per [Input](#input)) is also caught here, not just `RoadmapError`.

**Repo-mutation lock and module registry**

- `test_roadmap_is_a_locked_mutating_command` — `plan_tool.cli.app._requires_repo_mutation_lock` returns `True` for a namespace with `command="roadmap"`.
- `test_build_parser_registers_roadmap_exactly_once` — `plan_tool.cli.build_parser()` does not raise (guards `assemble`'s duplicate-registration assert) and `"roadmap"` is among the parser's subcommand choices.

## Acceptance criteria

- `plan_tool/cli/roadmap_cmd.py` and `tests/cli/test_roadmap_cmd.py` exist; `plan_tool/roadmap.py`, `plan_tool/roadmap_artifacts.py`, and `plan_tool/roadmap_gates.py` carry no diff.
- `rg 'STAGES|gate_set|MAX_STAGE_ATTEMPTS' plan_tool/cli/roadmap_cmd.py` returns nothing — no orchestration logic in the handler.
- `plan-tool roadmap --help` documents `--from-existing` and `--from-stage`, and shows no `--iterate` / `-y` / `--yes` flag.
- `plan-tool --help` lists `roadmap` in the intent-organized catalog, and `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` passes against the regenerated `tests/cli/package_surface_help.golden.txt`.
- `docs/cli/roadmap.md` exists and `tests/cli/test_cli_reference.py` is green with no further edits after `python -m plan_tool.cli_reference --write`; `docs/cli/README.md` lists `roadmap` in its index.
- `plan-tool validate`'s capability-catalog check (`plan_tool/capability_catalog.py:check_capabilities`) reports no `orphan-subcommand` finding for `roadmap` and no `absent-surface` finding for the new `CAPABILITIES.md` entry; `tests/test_capability_catalog.py::test_repo_capabilities_doc_is_self_consistent` and `::test_check_real_repo_catalog_is_honest` pass unmodified.
- A completed `RoadmapResult` (with or without `pending` decisions) maps to rc 0; a stage-exhausted result maps to a non-zero rc naming the failed stage; a `RoadmapError` maps to a distinct non-zero usage-shaped rc — all three are asserted in `tests/cli/test_roadmap_cmd.py`.
- `plan_tool.cli.app._requires_repo_mutation_lock` returns `True` for `command="roadmap"`.
- A `cmd_roadmap` call against a `tmp_path` repo with no `.plan-tool/plans.json` does not raise `ManifestError`.
- The 20 cases in `tests/cli/test_roadmap_cmd.py` pass under `uv run pytest tests/cli/test_roadmap_cmd.py -q`, and the full suite (`uv run pytest tests/ -q`) stays green.
- `.plan-tool/plans.json` is unchanged by any test in this suite, and `plan_tool/schema.py` and `plan_tool/locator.py` carry no diff.

## References

- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3/library/argparse.html) — `add_subparsers`, positional vs optional argument required-ness, and `type=int` coercion — the mechanics behind `slug`, `--from-existing`, and `--from-stage`.

## Applicable guardrails

- **No interactive or TTY surface.** The plan fences this out at the orchestrator level (step 4); this step must not reopen it at the CLI layer with a confirm flag, a `-y`/`--yes` opt-out, or a prompt-the-operator fallback. `plan-tool roadmap`'s flag set is exactly `slug`, `--from-existing`, `--from-stage`.
- **No components or plan-derivation stage support.** `--from-stage` takes no `choices=` restriction to the current two-stage table (so it doesn't need editing when a later plan adds a third stage), but this step adds no flag, subcommand, or code path anticipating `03-components.md` or `04-roadmap.md`.
- **No sign-off command for `pending` decisions.** `cmd_roadmap` reports the `pending` count on a completed run; it adds no flag or subaction to confirm, resolve, or block on one.
- **No per-project configuration of the quality-attribute list.** No `--framework` flag and no config-file read in this module.
- **The concept brief is the operator's input.** `--from-existing` accepts a path and passes it straight to `run_roadmap`; this module never reads, rewrites, or distills the brief itself.
- **No change to plan discovery, the plan schema, or the manifest.** `cmd_roadmap` never calls into `plan_tool/locator.py`'s registration functions (`register`/`deregister`/`sweep`'s machinery) and never touches `.plan-tool/plans.json`; it only resolves `repo_root` and a plain filesystem `plans_dir` path.

## Deferred

- **Operator docs** (`USE_CASES.md`, `RUNBOOK.md`, `integrations/claude/SKILL.md`, `CLAUDE.md`) **and the BACKLOG #208 reconciliation** — step 8. This step makes the verb discoverable via `--help` and the generated reference; narrative walkthroughs and the backlog entry's status update are step 8's.
- **A `--framework` flag and the lens registry** — BACKLOG #208's `roadmap-04-framework-lenses`. Nothing in this step's flag set anticipates it.
- **CLI support for the components and plan-derivation stages** — BACKLOG #208's `roadmap-02-components` / `roadmap-03-plan-derivation`. `--from-stage`'s unrestricted `int` type is deliberately future-compatible, but no stage-3/4 concept exists in this step's code or tests.
- **A standalone audit/reconcile verb over roadmap artifacts** — out of scope per the plan; this step adds no `roadmap --check` or similar mode.
- **`create`'s distill-short-circuit next-steps hand-off line** — BACKLOG #208 names this as a follow-up in `create`'s own split-proposal path; it is not part of wiring the `roadmap` verb itself and touches `plan_tool/cli/authoring.py`, outside this step's declared files.
- **Customizing the top-level `FileNotFoundError` handler's next-steps hint for `roadmap`** — `plan_tool/cli/app.py:main`'s generic catch-all currently suggests `plan-tool list` / `plan-tool register <path>`, which doesn't quite fit a missing `--from-existing` brief; leaving it as inherited behavior is a minor imprecision, not a defect this step's scope requires fixing.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
