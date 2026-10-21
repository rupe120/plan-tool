> **Auto-archived**: this plan was swept on 2026-06-15 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Wire the `plan-tool annotate` CLI handler

## Summary

- **Create `plan_tool/cli/annotate_cmd.py`** — a thin per-intent command module exposing `cmd_annotate(args, *, invoker=None)` and `register(subparsers)`, mirroring `plan_tool/cli/gates_cmd.py`'s single-verb shape. The handler ingests a `<plan-file>` path, calls step 1's `classify_plan_implementation`, renders step 2's two artifacts, writes `<stem>.annotated.md` + `<stem>.seed.md`, and optionally archives the original via `plan_tool/create.py:archive_existing_source`.
- **Register + dispatch** wires through the established registry seam: `app.py` imports the module into `COMMAND_MODULES`, `parser.py` appends `"annotate"` to `CANONICAL_COMMAND_ORDER`, and the regenerated `tests/cli/package_surface_help.golden.txt` locks the new `--help`.
- **Load-bearing decision:** the Claude seam is wired through `cmd_annotate`'s `invoker=None → shell_annotate_invoker` default (the gates_cmd pattern), so production dispatch shells out for real while unit tests pass a stub `invoker=` with **no** cli-global monkeypatch.
- **Single-pass scoping:** steps 1–2 deliver a one-classification-then-render orchestrator with no convergence loop, so `--iterate`/`--no-iterate` is added (titled deliverable, family parity) but is **accepted-and-inert**; wiring it to a real re-classify loop is Deferred (it would need new orchestrator behavior, making step 3 a mixed step).
- On green: `plan-tool annotate <file>` writes both artifacts, `--archive` moves the original with a report-pointing notice, the `--help` gate exits 0, and no test spawns the real backend.

## Table of Contents

- [Why](#why) — the orchestrator has no CLI; this is the only entry point.
- [Files (creates vs edits)](#files-creates-vs-edits) — two new files, four edits, one justified addition.
- [Implementation](#implementation) — the handler, the subparser, the registry wiring, the golden regen.
- [Tests](#tests) — unit (helper) cases here, integration `main([...])` cases in `tests/test_cli.py`.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green.
- [References](#references) — the step-relevant subset of the plan's links.
- [Deferred](#deferred) — the `--iterate` convergence loop, compared-commit capture, parent-flag consolidation.

## Why

- **Steps 1–2 ship a `PlanAnnotation` core and two pure renderers but no way to invoke them.** `plan_tool/annotate.py:classify_plan_implementation` and `plan_tool/annotate_render.py:render_annotated_report` / `render_create_seed` are unreachable from the CLI — there is no `annotate` subparser, no dispatch entry, no path derivation, no disk write. This step is the sole consumer that turns the in-memory contract into the on-disk `<name>.annotated.md` + `<name>.seed.md` artifacts the plan's `## Acceptance criteria` require.
- **The invoker-seam rule (CLAUDE.md) demands a real-by-default, overridable Claude seam.** Production must shell out (`shell_annotate_invoker`), every test must override it, and the autouse gate in `tests/conftest.py` must never fire. The CLI layer is where that default is wired.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/annotate_cmd.py` — the command module: `cmd_annotate` handler, path derivation, the `--archive` mutation, and `register(subparsers)`. Mirrors `plan_tool/cli/gates_cmd.py` member-for-member (module docstring, leaf-only imports, `invoker=None` seam, `register` returning `{"annotate": cmd_annotate}`).
  - `tests/cli/test_annotate_cmd.py` — unit/helper tests: argparse-level parse checks plus `cmd_annotate(ns, invoker=stub)` driven directly over a `tmp_path` source (no `main()`).
- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — add `from plan_tool.cli import annotate_cmd as _annotate_commands` and `from plan_tool.cli.annotate_cmd import cmd_annotate`; add `_annotate_commands` to the `COMMAND_MODULES` tuple.
  - `plan_tool/cli/parser.py` — append `"annotate"` to `CANONICAL_COMMAND_ORDER`.
  - `tests/cli/package_surface_help.golden.txt` — regenerate (the brace metavar list and the per-command help line both change).
  - `tests/test_cli.py` — add the `main(["annotate", …])` end-to-end integration class.
- **Addition beyond the declared `files:` list (justified):**
  - `plan_tool/cli/__init__.py` — add an `annotate` line to the intent-grouped catalog in the package **module docstring** (and `"cmd_annotate"` to `__all__`). The docstring's own contract states *"New subcommands add a per-intent command module … keep this catalog and the SKILL.md 'Subcommands at a glance' section in sync"*, and that docstring **is** the `--help` description rendered in the golden. No later step covers it (step 4's `files:` are RUNBOOK/README/BACKLOG/CLAUDE.md), so omitting it leaves the new verb absent from the curated `--help` catalog — a UX regression the module forbids. This is the "genuinely required" exception to the files-list constraint.

## Implementation

### `plan_tool/cli/annotate_cmd.py` (new)

**Module shape — mirror `plan_tool/cli/gates_cmd.py`:**
- Module docstring explaining the verb and the leaf-import discipline (imports only the cycle-free leaves `plan_tool.cli.context` / `plan_tool.cli.parser` and domain packages — **never** `plan_tool.cli.app`).
- Top-level imports of the domain symbols as module globals:
  - `from plan_tool.annotate import AnnotateError, AnnotateInvoker, PlanAnnotation, classify_plan_implementation, shell_annotate_invoker` (step 1).
  - `from plan_tool.annotate_render import render_annotated_report, render_create_seed` (step 2).
  - `from plan_tool.create import CreateError, archive_existing_source` (ingestion error + the `--archive` mover).
  - `from plan_tool.locator import load_manifest_plan_paths` (the manifest read for the `--archive` manifest-registered warn).
  - `from plan_tool.cli.context import _load_context`; `from plan_tool.cli.parser import Handler`; `from plan_tool.cli.console import _short_path`; `from plan_tool.style import detail, error, success, warn`.

**Handler `def cmd_annotate(args: argparse.Namespace, *, invoker: Optional[AnnotateInvoker] = None) -> int:`** — the gates_cmd seam pattern:
- **Resolve the Claude seam first:** `inv = invoker if invoker is not None else shell_annotate_invoker`. Dispatch calls `cmd_annotate(args)` with no `invoker`, so production resolves to the real shell seam; unit tests pass `invoker=stub`. This is the "default the Claude seam to the real shell invoker" wiring named in the step title.
- **Context + source path:** `ctx = _load_context(args)`; `source_path = args.plan_file.resolve()`. `plan_file` is a **filesystem path**, not a registered plan name — do **not** route it through `resolve_plan_for_context`; `classify_plan_implementation` reuses `read_existing_description`, which raises `CreateError` on a non-file.
- **Derive output paths (the seed renderer needs `report_path`, so derive both paths here before either render call):**
  - `output_dir = args.output_dir if args.output_dir is not None else source_path.parent`.
  - `report_path = args.report.resolve() if args.report is not None else (output_dir / f"{source_path.stem}.annotated.md")`.
  - `seed_path = args.seed.resolve() if args.seed is not None else (output_dir / f"{source_path.stem}.seed.md")`.
  - **Precedence:** an explicit `--report` / `--seed` full path wins over `--output-dir` for that one artifact; `--output-dir` only redirects the *derived* names. `source_path.stem` strips the single trailing suffix (`2-old-plan.md → 2-old-plan`).
- **Classify (the one Claude call):** wrap in the typed-error guard —
  ```
  try:
      annotation = classify_plan_implementation(source_path, repo_root=ctx.repo_root, invoker=inv)
  except (CreateError, AnnotateError) as exc:
      error(str(exc)); return 1
  ```
  `CreateError` is the bad/missing source path; `AnnotateError` is an unparseable Claude response. Both are failure-to-complete → rc 1 (no artifact written), mirroring `cmd_create`'s `read_existing_description` → `return 1` posture. Do **not** swallow-and-write-empty.
- **Render + write** (renderers are pure; writes are the CLI's job):
  - `report_md = render_annotated_report(annotation)`.
  - `seed_md = render_create_seed(annotation, report_path=report_path)` — `report_path` injected as the required keyword (step 2 keeps the renderer filesystem-agnostic).
  - For each `(path, text)` in `[(report_path, report_md), (seed_path, seed_md)]`: `path.parent.mkdir(parents=True, exist_ok=True)` then `path.write_text(text, encoding="utf-8")`, wrapped in `try/except OSError as exc: error(...); return 1`. Re-running annotate overwrites both artifacts (idempotent refresh) — no overwrite prompt.
  - Report success: `success(f"annotated {_short_path(report_path, ctx.repo_root)}")` and `detail(f"seed {_short_path(seed_path, ctx.repo_root)}")`.
  - **Terminal (fully-implemented) case notice:** when carryover is empty — every `annotation.sections` entry is IMPLEMENTED, so neither a NOT-IMPLEMENTED section nor a PARTIAL remainder carries forward — emit an additional stdout notice naming the report and stating there is no forward work, e.g. `success(f"no remaining work — every section is implemented; see {_short_path(report_path, ctx.repo_root)}, no next plan needed")`, so the operator is not left to infer the no-op from an empty seed (the plan's fully-implemented-terminal-case criterion). Both artifacts are still written; only this extra line is conditional.
- **`--archive` (the only opt-in mutation):** when `args.archive`, call `archive_existing_source(source_path, report_path, repo_root=ctx.repo_root)` — `new_plan_path=report_path` so the prepended one-line notice points at the report (the plan's *"the archived original records the report's path"* lineage). When the source filename matches the `N-slug.md` convention (`_slug_from_filename`), `archive_existing_source` co-archives the sibling `plan-details/<slug>/` bundle too — so for annotate's intended input (a real plan file) `--archive` moves the plan's detail directory alongside the plan, not just the single file. Print results like `cmd_create` does: `detail(f"archived {orig} -> {tgt}")` for each `result.archived` pair (plan + detail bundle), `warn(reason)` for `result.skipped`. Without `--archive` the original is untouched.
  - **Manifest-registered source — warn, do not deregister (the plan's `--archive` orphan risk).** Before the move, check whether `source_path.resolve()` is in `load_manifest_plan_paths(ctx.repo_root)` (`plan_tool/locator.py`). When it is, emit a `warn(...)` naming the manifest (`<repo>/.plan-tool/plans.json`) and stating that archiving moves the plan but leaves its `plans.json` entry pointing at the old location, so `locator.py` resolution of that plan will fail until the operator updates or removes the entry by hand. Manifest mutation stays out of scope (`## Out of scope` excludes manifest registration), so this is document/warn only — the archive still proceeds; annotate's typical input is an unregistered old plan or rough-notes file, where the check is silent.
- **`--iterate` is parsed but not consumed** — see the scoping decision below. `cmd_annotate` runs exactly one classification pass regardless of `args.iterate`.
- Return `0`.

**`--iterate` scoping (load-bearing decision):**
- Steps 1–2 deliver a **single-pass** orchestrator: one `invoker(prompt)` classification → two deterministic pure renderers. There is no apply-findings loop, no sampling axis (`classify_plan_implementation` takes no `max_samples`), so a functional `--iterate` has nothing to converge.
- Add `--iterate`/`--no-iterate` to the subparser anyway (titled deliverable + authoring-family parity + the `annotate --help` gate), but `cmd_annotate` does **not** branch on it. Wiring `--iterate` to a real re-classify/refine loop would require the orchestrator to grow loop behavior — a separate step (it would make this a mixed CLI+behavior step) — so it is Deferred.
- **Do not** attach the 8-flag `iterate_parent` (`--max-iterations` / `--iteration-budget` / `--allow-drift` / …) that `authoring.py:register` and `completeness_cmd.py:register` build: with no loop those would be dead flags and would worsen the already-deferred parent-flag consolidation. Add only the literal `--iterate`/`--no-iterate` pair.

### `plan_tool/cli/annotate_cmd.py:register(subparsers) -> dict[str, Handler]`

- Mirror `gates_cmd.py:register`. No `yes_parent` (annotate has no Y/N prompt — `--archive` is its own explicit opt-in), no `iterate_parent`.
- ```
  p = subparsers.add_parser("annotate", help="<one-liner — see below>")
  p.add_argument("plan_file", type=Path, help="path to the existing plan/notes file to annotate against the current code")
  p.add_argument("--output-dir", type=Path, default=None, dest="output_dir", help="directory for the derived <name>.annotated.md / <name>.seed.md (default: beside the source file)")
  p.add_argument("--report", type=Path, default=None, help="explicit path for the annotated report (overrides the derived name + --output-dir)")
  p.add_argument("--seed", type=Path, default=None, help="explicit path for the create-seed (overrides the derived name + --output-dir)")
  p.add_argument("--archive", action="store_true", help="move the original (and, for an N-slug.md plan file, its sibling plan-details/<slug>/ bundle) into archive/ with a notice pointing at the report (the only mutation of the source; default: leave it in place)")
  p.add_argument("--iterate", action=argparse.BooleanOptionalAction, default=False, help="reserved: annotate is currently single-pass (one classification + two renderers). Deliberately defaults OFF — diverging from the authoring family's opt-out default=True (p_create/p_detail) — because the flag is inert; do NOT copy default=True, which would falsely advertise a convergence loop. No loop runs today.")
  return {"annotate": cmd_annotate}
  ```
- Subparser `help=` one-liner (feeds the per-command help block in the golden): *"judge an existing plan/notes file against the current code and emit two artifacts — an additive `<name>.annotated.md` (verbatim original + per-section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED status) and a carryover `<name>.seed.md` for `create --from-existing`; read-only except the opt-in `--archive`."*

### `plan_tool/cli/app.py` (edit)

- Add an import block beside the other per-intent module imports (e.g. after the `_gates_commands` / `_bench_commands` block):
  ```
  from plan_tool.cli import annotate_cmd as _annotate_commands
  from plan_tool.cli.annotate_cmd import cmd_annotate
  ```
  Use the `from plan_tool.cli import annotate_cmd as …` form (not dotted attribute access) — the docstring at the top of `app.py` explains this is load-bearing while `plan_tool.cli.__init__` is still initializing. Re-importing `cmd_annotate` into `app`'s namespace lets the `__init__.py` mirror loop surface it as `plan_tool.cli.cmd_annotate`.
- Append `_annotate_commands` to the `COMMAND_MODULES` tuple. Position in this tuple is **not** help-order-bearing (`CANONICAL_COMMAND_ORDER` fixes display order); append it after `_bench_commands`.

### `plan_tool/cli/parser.py` (edit)

- Append `"annotate"` to `CANONICAL_COMMAND_ORDER`, after `"bench"`. Per the tuple's own comment (*"new commands appended post-split extend the tuple instead"*), new verbs append rather than insert by intent — matching how `suggest-gates` / `bench` were added. This gives `annotate` a canonical index so `_reorder_subcommands` sorts it before the deprecated-alias cluster (`root`, `reconcile`, …) in both the brace metavar and the per-command help.

### `plan_tool/cli/__init__.py` (justified addition)

- Add a new intent group to the module docstring catalog (placed after the **Authoring** block, since annotate is authoring-adjacent and feeds `create`):
  ```
  Annotate — judge an existing plan against the code and emit a forward seed.
    plan-tool annotate <plan-file>           Classify each section IMPLEMENTED/PARTIAL/NOT-IMPLEMENTED against the repo; write <name>.annotated.md (verbatim + status blocks) and a carryover <name>.seed.md for `create --from-existing`. --archive moves the original.
  ```
- Add `"cmd_annotate"` to `__all__` (the dir(app) mirror loop already makes `from plan_tool.cli import cmd_annotate` resolve; this only lists it under `import *`, following the existing entries — note `__all__` is already not exhaustive of the mirrored handlers, omitting e.g. `cmd_suggest_gates`/`cmd_bench`).

### `tests/cli/package_surface_help.golden.txt` (regenerate)

- Regenerate after all wiring lands: `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py -q -k test_help_matches_golden` (the test rewrites the golden and skips when `UPDATE_CLI_GOLDEN` is set, per its `if not GOLDEN_HELP_PATH.exists() or os.environ.get("UPDATE_CLI_GOLDEN")` guard). Expected diff: `annotate` added to both brace metavar lists (usage + positional), a new `annotate  …` per-command help block at the canonical position, and the new `Annotate —` catalog group in the description. Re-run without the env var to confirm a clean byte-match.

## Tests

### `tests/cli/test_annotate_cmd.py` (new — unit/helper, no `main()`)

Follow the `tests/cli/` conventions: drive `cmd_annotate` **directly** with an `argparse.Namespace` and an explicit `invoker=` stub (recording closure returning canned JSON), so no `plan_tool.cli` module global is patched and the autouse backend gate never fires.

Parse-surface (via `build_parser()` + the `_find_subparser` helper):
- `test_annotate_subparser_registered` — `_find_subparser(build_parser(), "annotate")` is not `None`.
- `test_annotate_parses_paths_and_flags` — `parse_args([...,"--output-dir","o","--report","r.md","--seed","s.md","--archive","--iterate"])` populates `plan_file`, `output_dir`, `report`, `seed`, `archive is True`, `iterate is True`.
- `test_iterate_defaults_off` — bare `annotate plan.md` → `args.iterate is False`; `--no-iterate` → `False`.
- `test_archive_defaults_off` — bare invocation → `args.archive is False`.

Handler behavior (`cmd_annotate(ns, invoker=stub)` over a `tmp_path` source + canned-JSON stub — the **real** `classify_plan_implementation` + renderers run, only the Claude call is stubbed):
- `test_writes_report_and_seed` — returns 0; `<stem>.annotated.md` and `<stem>.seed.md` both exist beside the source.
- `test_report_is_additive` — every line of the source appears in the written report (light wiring check; the deep difflib invariant is step 2's).
- `test_seed_lists_carryover_headings` — the seed file lists the NOT-IMPLEMENTED headings and the PARTIAL headings under carryover scope; for a PARTIAL section it scopes the `remaining_work` text while its already-implemented `code_refs` appear only in the done-context block, not in carryover (the split contract step 2 locks — wiring-level smoke check; the deep assertions are step 2's).
- `test_output_dir_redirects_both_artifacts` — `output_dir=tmp/out` → both files land under `out/`.
- `test_report_and_seed_path_overrides_used_verbatim` — explicit `--report`/`--seed` paths are written exactly.
- `test_archive_moves_original_with_report_notice` — `archive=True` moves the source into `archive/` and the archived copy's prepended notice names the report path; the source no longer exists at its original location. Use an `N-slug.md` source with a sibling `plan-details/<slug>/` directory and assert that bundle is co-archived too (per `archive_existing_source`'s `_slug_from_filename` behavior), so the test isn't surprised by the extra move.
- `test_no_archive_leaves_original` — `archive=False` → source untouched.
- `test_archive_registered_source_warns` — `archive=True` on a source whose resolved path is listed in the repo's `.plan-tool/plans.json` → captured stderr/warn output names the manifest and the dangling-entry caveat; the archive still proceeds (source moved). An unregistered source archives with no such warning.
- `test_all_implemented_emits_no_forward_work_notice` — a canned-JSON stub classifying every section IMPLEMENTED → rc 0, both artifacts written, and captured stdout carries the terminal-case "no remaining work / no next plan needed" notice naming the report path (the fully-implemented-terminal-case criterion); a stub with at least one NOT-IMPLEMENTED/PARTIAL section omits that notice.
- `test_unparseable_response_returns_1` — stub returns `""` → `AnnotateError` → rc 1, report not written.
- `test_missing_source_returns_1` — `plan_file` pointing at a non-file → `CreateError` (from `read_existing_description`) → rc 1.
- `test_real_invoker_is_default_seam` — `annotate_cmd.shell_annotate_invoker is plan_tool.annotate.shell_annotate_invoker` (pins "default the Claude seam to the real shell invoker").

### `tests/test_cli.py` (edit — integration, `main(["annotate", …])`, patch the Claude seam)

Per the project convention, `main([...])`-level end-to-end coverage lives in `tests/test_cli.py`, not the helper file. Add `class TestAnnotateEndToEnd` (mark the heavy round-trip `@pytest.mark.integration`), patching `plan_tool.cli.annotate_cmd.shell_annotate_invoker` to a canned-JSON stub so the real classify→render→write chain runs with only the backend stubbed:
- `test_annotate_main_writes_report_and_seed` — temp plan file + a fixture code file under the repo; `main(["annotate", str(plan), "--repo-root", str(repo)])` returns 0; the report contains the verbatim original lines plus status blocks; the seed exists.
- `test_seed_feeds_create_from_existing` — feed the written `<stem>.seed.md` to `main(["create", slug, "--from-existing", seed, "--no-distill", "--no-iterate", "--repo-root", str(repo)])` with `create`'s invoker stubbed. Because the stub (not the seed) determines the resulting plan's content, assert the **stub-independent** surface instead: capture the recorded prompt/description the stub received and assert that the seed text fed into `create`'s invoker carries the carryover scoping (every NOT-IMPLEMENTED heading plus each PARTIAL's `remaining_work`) plus the done-context framing (IMPLEMENTED headings plus each PARTIAL's already-implemented half), and that `main([...])` returns 0 (`create` accepts the seed). Use a fixture PARTIAL section whose `remaining_work` and `code_refs` are distinct recognizable strings, and assert the discriminating split end-to-end: the seed text contains the PARTIAL's `remaining_work` under carryover scope, does **not** contain its `code_refs` under carryover scope, and does contain those `code_refs` in the done-context block — so this round-trip would fail against the old "PARTIAL carried whole" renderer (the regression Finding 1 flagged), not just pass trivially. Also assert the **distill no-op**: spy on `create.py:propose_distilled_seed_from_claude` and assert it is not invoked (call count 0), realizing the plan's "the seed passes through `create`'s distill gate as a no-op" criterion — the check step 2 deferred to this integration test. The call count is 0 because the invocation passes `--no-distill`, not because of size: the seed's non-canonical body (`Carryover scope`/`Already implemented`/`Provenance`) fails `create.py:_canonical_seed_covers_all`, so without the flag `create` would distill it regardless of size, the spy would observe a call, and the assertion would be wrong. Distill is bypassed by the flag, not by the seed falling under `create.py:_DISTILL_SKIP_BELOW_BYTES`.
- `test_annotate_help_exits_zero` — `main(["annotate", "--help"])` raises `SystemExit` with code `0` (validates the `uv run plan-tool annotate --help` gate).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Author every test above **with** the implementation:
1. `register` + parse tests (drive design of the subparser flags).
2. `cmd_annotate` handler unit tests (drive path derivation, archive, error rcs).
3. The `main([...])` integration class + the `create --from-existing` round-trip.
4. Regenerate the golden last (after wiring is stable).

**Green-before-done gate:** all new `tests/cli/test_annotate_cmd.py` cases and the new `tests/test_cli.py` class pass, the golden test byte-matches after regeneration, and the existing `tests/cli/test_package_surface.py` correspondence tests (`test_register_returns_dispatch_for_every_subcommand`, `test_every_subcommand_has_a_dispatch_handler`) stay green — before this step is finished.

## Acceptance criteria

- `plan-tool annotate <plan-file>` exits 0 and writes both `<stem>.annotated.md` and `<stem>.seed.md` (beside the source by default; under `--output-dir`, or at explicit `--report`/`--seed` paths).
- The report contains every original line verbatim with per-section status blocks; the seed scopes carryover to every NOT-IMPLEMENTED heading (whole) plus each PARTIAL's `remaining_work`, and routes the IMPLEMENTED headings plus each PARTIAL's already-implemented `code_refs`/`evidence` into done-context — a PARTIAL's done half never appears in carryover scope (consumes `SectionAnnotation.remaining_work`, not orphaned).
- When every section classifies IMPLEMENTED (empty carryover), both artifacts are still written and stdout carries a terminal-case notice naming the report and stating no forward work / no next plan is needed; a non-empty carryover omits that notice.
- `--archive` moves the original into `archive/` with a one-line notice pointing at the report; without it the original is untouched. When the source is registered in `.plan-tool/plans.json`, `--archive` emits a warning that the move orphans the manifest entry (document/warn only — annotate does not deregister); the archive still proceeds.
- An unparseable Claude response or a non-file `plan_file` exits non-zero (rc 1) with an error message and no partial report.
- `plan-tool annotate --help` exits 0 (the step's `gate:`).
- `annotate` appears in `build_parser()` with `cmd_annotate` as its dispatch handler; `tests/cli/test_package_surface.py` correspondence tests pass; the regenerated golden byte-matches.
- The default `invoker=` resolves to `shell_annotate_invoker`; every test overrides the seam and none spawns the real backend.

## References

- [argparse — Parser for command-line options, arguments and sub-commands — Python docs](https://docs.python.org/3/library/argparse.html) — `add_subparsers`/`add_parser`, `BooleanOptionalAction`, and `parents=` — the mechanics behind the `annotate` subparser and its flags.
- [pathlib — Object-oriented filesystem paths — Python docs](https://docs.python.org/3/library/pathlib.html) — `Path.stem`/`.parent`/`.resolve()`/`.write_text` for deriving the `<name>.annotated.md` / `<name>.seed.md` paths and writing them.
- [Claude Code — Headless / Run programmatically](https://code.claude.com/docs/en/headless) — the non-interactive `-p`/`--print` contract `shell_annotate_invoker` depends on when annotate shells out for the classification.

## Deferred

- **Wiring `--iterate` to a real convergence loop** — the flag is accepted-and-inert because steps 1–2 are single-pass; a functional loop needs new orchestrator behavior (re-classify / refine), which is a separate step, not a thin CLI carve. Tracked here so the flag isn't mistaken for a wired feature.
- **The 8-flag `iterate_parent` surface** (`--max-iterations` / `--iteration-budget` / `--allow-drift` / …) — deliberately not attached; they only mean something with a loop. Add alongside the deferred convergence loop above.
- **Compared commit/state in the report header** — step 2 records `repo_root` + grounded-file count as the available state proxy; the git `HEAD`/dirty-state read a pure renderer can't do is a CLI-or-follow-up concern, not wired here.
- **Consolidating the per-module `-y/--yes` / `iterate_parent` duplication into `plan_tool/cli/parser.py`** — a standing deferred refactor across `authoring.py` / `completeness_cmd.py` / `gates_cmd.py`; `annotate` adds neither parent, so it neither worsens nor resolves it.
- **The SKILL.md "Subcommands at a glance" sync** — the `__init__.py` docstring comment pairs the catalog with SKILL.md; the SKILL.md row belongs with step 4's documentation pass (its `files:` already covers the operator-facing docs), not this CLI step.
