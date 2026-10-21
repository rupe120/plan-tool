> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add the `--view` read mode to the `roadmap` command and regenerate the CLI reference

## Summary

Wires steps 3–5's three render functions into `plan_tool/cli/roadmap_cmd.py` as a third arm of `roadmap`'s existing mutually exclusive group (`--apply` / `--from-stage` / `--view {walk,ledger,index}`), adds the orthogonal `--mode {current,review}` and `--id ROW_ID` options, and maps the result to an exit code. `cmd_roadmap` gains a `_cmd_roadmap_view` branch that calls step 2's `load_roadmap`, maps `LoadedRoadmap.directory_exists` to rc 2 (missing roadmap) or rc 0 (any other state), dispatches on `args.view` to the matching render function, and prints the returned text. The key design decision is where the `--mode`/`--id` validation lives: argparse's mutually-exclusive-group machinery cannot express "meaningful only alongside `--view`", so this step adds an explicit pre-dispatch check in `cmd_roadmap` and rejects the combination before any path resolution or disk read. On green, `plan-tool roadmap <slug> --view {walk,ledger,index} [--mode {current,review}] [--id ROW_ID]` renders one of the three views to stdout with no backend call and no `--from-existing`, `docs/cli/roadmap.md` and `docs/cli/README.md` regenerate clean from the live parser, and `plan-tool` gains no new subcommand.

## Table of Contents

- [Why](#why) — the gap this step closes: three render functions with nothing calling them
- [Input](#input) — the step 2–5 contracts this step wires together, and the one name this step must confirm rather than assume
- [Files (creates vs edits)](#files-creates-vs-edits) — all edits, no new files
- [Implementation](#implementation) — the argparse shape, the validation, the dispatch, and the doc regeneration
- [Tests](#tests) — what `tests/cli/test_roadmap_cmd.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — argparse docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what step 7 and later work own instead

## Why

After steps 1–5, `plan_tool/roadmap_view.py` can load a roadmap off disk and render all three views, but nothing calls any of it — step 4's own Deferred section says so plainly: "CLI wiring (`--view`, `--mode`, `--id`) and the exit-code mapping — step 6; `render_traceability_walk` is not called from anywhere yet," and step 5 says the identical thing about `render_decision_ledger`. `plan_tool/cli/roadmap_cmd.py` today has exactly two modes — a stage run and `--apply` — and its own module docstring states the module's job as "path resolution, the exit-code mapping, and the operator summary — the three things `run_roadmap` deliberately does not do." A read mode is the same shape of thin wiring, just pointed at `plan_tool.roadmap_view` instead of `plan_tool.roadmap`.

The plan's Architecture settles the CLI shape already ("settled 2026-08-07, user-confirmed; do not re-open"): `--view` joins the existing mutually exclusive group rather than becoming a new subcommand, because a read mode "runs no stage and invokes no backend" — the same property that already justifies `--apply` sharing the group. The rejected sibling-verb alternative would have cost a `COMMAND_MODULES` entry and a `CAPABILITIES.md` capability row for a mode that has one natural home; this step's whole point is to avoid paying that cost.

## Input

This step is pure wiring over four upstream contracts. Three are pinned by name in their own detail files; one is not, and this step's implementer has to confirm it against the landed module before writing the import line.

- **Step 2** supplies `load_roadmap(plans_dir, slug, *, mode=...) -> LoadedRoadmap` and `LoadedRoadmap` itself, both in `plan_tool/roadmap_view.py`. Three facts drive this step's dispatch and exit-code logic:
  - `LoadedRoadmap.directory_exists: bool` is, per the plan's Architecture, "the field... step 2's to detect and step 6's to map to an exit code" — `False` is the sole rc-2 condition for `--view`; `True` (with any combination of absent/unparseable artifacts) renders at rc 0.
  - `load_roadmap` "never raises for any combination of absent, unparseable, or entirely-missing-directory input — only an invalid slug's `ValueError` passes through," propagated unchanged from `roadmap_dir`'s existing `_validate_slug` guard in `plan_tool/roadmap_artifacts.py`. This step must catch that `ValueError` itself: `plan_tool/roadmap.py:run_roadmap` performs the identical catch at its own call into `roadmap_dir` (`except ValueError as exc: raise RoadmapError(str(exc)) from exc`, immediately before its final `return`), but that translation lives inside `run_roadmap` and does not run for a direct `load_roadmap` call — `cmd_roadmap`'s existing `except (RoadmapError, RoadmapArtifactError)` clause around `run_roadmap` will not catch a bare `ValueError` raised by `load_roadmap`.
  - `load_roadmap` never picks an exit code or prints anything itself (step 2's Architecture: "not a second enforcement channel... that mapping belongs to a later step") — this step is that later step, and it is the only one.
- **Step 3** supplies the render function behind `--view index`. Its detail file describes it only by behavior — "given a `LoadedRoadmap` (step 2) and an optional row id, it prints either the full map or one id's citers as text" — and never pins a literal `def` name or parameter name the way steps 4 and 5 do for their own entry points. Grep the landed `plan_tool/roadmap_view.py` for the reverse-index render function before importing it; do not assume a name from this plan's prose.
- **Step 4** supplies `render_traceability_walk(loaded, plans_dir)` — the one view that takes a second argument, since the draft-seed read is disk access no other view needs.
- **Step 5** supplies `render_decision_ledger(loaded: LoadedRoadmap) -> str` — no `plans_dir`, like step 3's reverse-index render.
- **The mode constants.** Step 2's own Files section names them only as "the mode constants" without a literal spelling. Given this module's existing `RESOLUTION_*` (step 1) and, elsewhere in this codebase, `FAILURE_*` / `OUTCOME_*` (`plan_tool/roadmap.py`) naming convention, `MODE_CURRENT` / `MODE_REVIEW` string constants are a reasonable guess — confirm the landed names rather than importing on faith. Whatever they are called, `"current"` is the default when `--mode` is not supplied, per the plan's Architecture and Acceptance criteria.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — imports `load_roadmap`, `LoadedRoadmap`, `render_traceability_walk`, `render_decision_ledger`, the reverse-index render function, and the mode constants from `plan_tool.roadmap_view`; extends `register()`'s existing mutually exclusive group with `--view`; adds standalone `--mode` and `--id` options; adds the pre-dispatch validation and a `_cmd_roadmap_view` branch to `cmd_roadmap`; updates the module docstring and `cmd_roadmap`'s own docstring to describe the third mode and its exit codes.
  - `plan_tool/cli/__init__.py` — adds a third line under the existing "Roadmap" catalog section (module docstring) documenting the `--view` invocation form, alongside the two lines already there for the stage-run and `--apply` forms.
  - `docs/cli/roadmap.md`, `docs/cli/README.md` — regenerated, not hand-edited, via `python -m plan_tool.cli_reference --write` after the argparse changes land.
  - `tests/cli/test_roadmap_cmd.py` — adds the test classes/functions in [Tests](#tests); extends the `_ns()` namespace-builder helper with `view=None`, `mode=None`, `id=None` defaults.
  - `tests/cli/package_surface_help.golden.txt` — regenerated via `UPDATE_CLI_GOLDEN=1 uv run pytest tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden -q`, which snapshots `plan-tool --help` and therefore picks up both the `cli/__init__.py` catalog line and the new `roadmap` flags.

## Implementation

**`--view` joins the existing mutually exclusive group; `--mode` and `--id` do not.** `register()` currently builds `mode = p.add_mutually_exclusive_group()` and adds `--apply` and `--from-stage` to it. Add a third member, `--view`, with `choices=["walk", "ledger", "index"]` and `default=None` — argparse then rejects `--view` combined with `--apply` or `--from-stage` for free, matching the existing `test_parser_apply_and_from_stage_mutually_exclusive` precedent. Rename the local variable that holds the group (`mode`) before adding the new `--mode` flag to the parser — the two are unrelated (a local `argparse._MutuallyExclusiveGroup` versus the dest of a brand-new option), but sharing a name inside the same function body invites a misread. `--mode` (`choices=["current", "review"]`) and `--id` (a bare string, no `type=Path` — it is a row id, not a filesystem path) are ordinary standalone options outside the group, since the plan's Architecture treats `--mode` as valid alongside *any* `--view` value (it changes `--view walk`'s header even though the plan states the walk's body is byte-identical across modes) — it is not scoped to `--view index` the way `--id` is.

**Leave `--mode`'s argparse default at `None`, not `"current"`, and resolve `"current"` downstream.** The plan requires rejecting a bare `--mode` passed without `--view` — an error, not a silent no-op — which means the CLI layer must be able to tell "user typed `--mode current`" apart from "user typed nothing." A string default of `"current"` collapses that distinction; `None` preserves it. Compute the effective mode only after the validation below has already passed: `mode = args.mode or MODE_CURRENT` (or whatever the landed constant is named) right before calling `load_roadmap`. This does mean the generated `docs/cli/roadmap.md` Options table will show `--mode`'s Default column as `—` rather than `current` — `cli_reference.py:_format_default` renders an unset default as `—` and is out of this step's files, so the accurate place to say "defaults to `current`" for a reader is the option's own `help=` string, not the generated table's Default cell.

**The validation runs once, before either dispatch branch, and covers every combination — including `--apply --mode review` or `--from-stage 2 --id x`, not only bare invocations.** A reasonable shape, placed in `cmd_roadmap` right after `repo_root` / `plans_dir` resolution and before the existing `if args.apply:` check:

```
if args.view is None:
    if args.mode is not None:
        error("--mode requires --view")
        return _RC_USAGE
    if args.id is not None:
        error("--id requires --view index")
        return _RC_USAGE
elif args.view != "index" and args.id is not None:
    error("--id is only valid with --view index")
    return _RC_USAGE
```

The two error strings follow the established "`--flag` requires `--other-flag`" phrasing already used at this call site's neighbors (`"--from-existing PATH (the concept brief)"`,  `"--reconcile requires --step or --all"` in `plan_tool/cli/reconcile.py`, `"--commit requires --iterate"` in `plan_tool/cli/completeness_cmd.py`) — match that convention rather than inventing new wording. `--from-existing` is not rejected when supplied alongside `--view`; it is simply unused, mirroring `--apply`'s own existing precedent (`test_from_existing_not_required_with_apply` — "not required" is not "forbidden"). `-y`/`--yes` is likewise a benign no-op under `--view`, unchanged from how it already behaves during a stage run.

**Dispatch:** add `if args.view is not None: return _cmd_roadmap_view(args, plans_dir=plans_dir)` immediately after the existing `if args.apply: return _cmd_roadmap_apply(...)` check, before the `--from-existing` requirement (which stays scoped to the stage-run path only — a third `if`/`return` in the same shape `_cmd_roadmap_apply` already establishes). A new `_cmd_roadmap_view` function, module-private like `_cmd_roadmap_apply`, owns:

- resolving the effective mode (`args.mode or` the "current" constant);
- calling `load_roadmap(plans_dir, args.slug, mode=effective_mode)`, with the call wrapped in `try`/`except ValueError as exc: error(str(exc)); return _RC_USAGE` for the invalid-slug case named in [Input](#input);
- checking `loaded.directory_exists`; when `False`, an `error(...)` naming the slug (mirroring the existing `f"roadmap {slug}: ..."` message shape used throughout this module) and `return _RC_USAGE`;
- dispatching on `args.view` — `"walk"` to `render_traceability_walk(loaded, plans_dir)`, `"ledger"` to `render_decision_ledger(loaded)`, `"index"` to the reverse-index render function called with `loaded` and `args.id` (which is `None` for the full-map render, per the plan's "`--view index` with no `--id` renders the full citation map");
- printing the returned string with a plain `print(...)` — the render functions already bake their own mode header and absent/unparseable notice into the returned text (per step 3's Implementation, written to be reused by steps 4–6), so this function's job is to hand the text to stdout unmodified, not to add its own framing the way `_print_completed` / `_render_apply_result` do for the other two modes;
- returning `0`.

**Do not touch `plan_tool/cli_reference.py`.** It is not in this step's files. Its `_render_parser_body` has a hardcoded second usage block for `invocation == "roadmap"` (`"plan-tool roadmap [-h] [-y] --apply slug"`) documenting the apply-only shorthand specifically — that block is unrelated to `--view` and needs no third arm; the auto-generated primary usage line (from `parser.format_usage()`) already grows to include `--view {walk,ledger,index}` as a third arm of the group with no code change, since `_format_invocation` renders any `choices=` action generically.

**Update the two docstrings that describe this module's job**, since both currently describe only two modes. `plan_tool/cli/roadmap_cmd.py`'s module docstring lists what the module owns; add the read mode alongside the stage-run and apply-only descriptions it already gives. `cmd_roadmap`'s own docstring documents the exit-code mapping per pre-flight-failure category and per outcome kind — add the two new rc-2 categories this step introduces (bad slug under `--view`, missing roadmap directory) and state that a completed render is unconditionally rc 0. This is a documentation-accuracy edit inside a file already in scope, not new surface.

**Regenerate `docs/cli/roadmap.md` and `docs/cli/README.md`** with `python -m plan_tool.cli_reference --write` once the argparse changes above land, and commit the output verbatim — hand-editing either file is what `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` exists to catch (that test file is not in this step's own list, but it is the thing that validates this step's docs edits, and it is worth running before calling the step done).

**Add the third invocation-form line to `plan_tool/cli/__init__.py`.** The module's own docstring states its contract plainly: "keep this catalog and the SKILL.md 'Subcommands at a glance' section in sync." This step only owns the catalog side (the `SKILL.md` sweep is step 7's, per the plan's Risks "invocation-form class" split). Add one line under the existing "Roadmap" section, in the same style as the two lines already there (`plan-tool roadmap <slug> --from-existing ...` and `plan-tool roadmap <slug> --apply [-y]`), for `plan-tool roadmap <slug> --view {walk,ledger,index} [--mode ...] [--id ...]`.

## Tests

`tests/cli/test_roadmap_cmd.py`, following its own stated convention (the file's docstring: "the wiring, not the orchestrator") — stub `load_roadmap` and the three render functions as imported into `roadmap_cmd`'s namespace (`monkeypatch.setattr(f"{MODULE}.load_roadmap", ...)`, matching the existing `_stub_run` / `_stub_apply` pattern) for nearly every case, and reserve a real, unstubbed `load_roadmap` call for one integration-shaped case per the file's own "two deliberate exceptions" precedent (`TestOverwriteAdviceIsPrintedExactlyOnce`, `TestFeedbackSummaryOverTheRealOrchestrator`) — those two exist because layer-isolated tests on both sides passed while a real invocation printed something twice; the same risk applies here between `_cmd_roadmap_view`'s own printing and whatever header/notice text the render functions already embed.

### Tests for this step

- `test_view_choices_are_walk_ledger_index` — the parser accepts exactly the three literal values and rejects a fourth with `SystemExit`.
- `test_view_mutually_exclusive_with_apply` — `--view walk --apply` raises `SystemExit`.
- `test_view_mutually_exclusive_with_from_stage` — `--view walk --from-stage 2` raises `SystemExit`.
- `test_view_does_not_require_from_existing` — `roadmap <slug> --view ledger` parses with `from_existing` left `None`, mirroring `test_from_existing_not_required_with_apply`.
- `test_mode_choices_are_current_review` — a `--mode` value outside the two literals raises `SystemExit`.
- `test_mode_argparse_default_is_none` — parsing without `--mode` leaves `args.mode` as `None`, not `"current"` — pins the distinguishability decision in Implementation.
- `test_id_argparse_default_is_none`.
- `test_help_documents_view_mode_and_id` — `--view`, `--mode`, and `--id` all appear in `_roadmap_help()`, mirroring `test_help_documents_from_existing_and_from_stage`.
- `test_mode_without_view_is_rejected` — `roadmap <slug> --mode review` (no `--view`) returns rc 2 and the stderr message names `--mode` and `--view`.
- `test_id_without_view_is_rejected` — `roadmap <slug> --id entity-1` returns rc 2.
- `test_id_with_view_walk_is_rejected` — `--view walk --id entity-1` returns rc 2, distinct message from the without-view case.
- `test_id_with_view_ledger_is_rejected` — same, for `--view ledger`.
- `test_mode_rejected_even_when_apply_is_set` — `--apply --mode review` (no `--view`) returns rc 2, proving the validation runs ahead of the `--apply` branch, not only ahead of the stage-run branch.
- `test_view_walk_calls_render_traceability_walk_with_loaded_and_plans_dir` — stub asserts the exact `loaded` object `load_roadmap` returned is passed straight through, plus `plans_dir`.
- `test_view_ledger_calls_render_decision_ledger_with_loaded_only`.
- `test_view_index_calls_the_reverse_index_render_with_loaded_and_id`.
- `test_view_index_without_id_passes_none_for_the_full_map`.
- `test_view_mode_defaults_to_current_when_mode_flag_omitted` — `load_roadmap` is called with the "current" mode constant when `--mode` is not supplied.
- `test_view_mode_review_reaches_load_roadmap` — `--mode review` reaches `load_roadmap` unchanged.
- `test_view_prints_the_rendered_text_to_stdout` — the render stub's return value appears verbatim in `capsys`.
- `test_view_returns_zero_when_directory_exists` — stub `loaded.directory_exists = True`; rc is `0` regardless of `absent` / `unparseable` contents.
- `test_missing_roadmap_directory_returns_two` — stub `loaded.directory_exists = False`; rc is `2` and stderr names the slug.
- `test_bad_slug_under_view_mode_returns_two` — stub `load_roadmap` raising `ValueError("...")`; rc is `2` and the message reaches stderr, mirroring `test_roadmap_error_returns_a_usage_shaped_code_and_prints_the_message`'s existing pattern for the stage-run path.
- `test_view_mode_never_calls_run_roadmap_or_apply_roadmap_seeds` — both stubbed to raise `AssertionError` if called, matching `TestApplyMode`'s existing `boom` pattern; `--view` invocation must not reach either.
- `test_apply_and_from_stage_paths_are_unaffected_by_the_new_flags` — an ordinary `--apply` or stage-run invocation with `--view`/`--mode`/`--id` left at their defaults behaves exactly as before this step (regression guard for the shared `cmd_roadmap` entry point).
- `test_view_over_a_real_missing_roadmap_directory_returns_two_without_stubbing` — the one real-`load_roadmap` case per the file's own precedent: a `tmp_path` with no `roadmaps/<slug>/` directory at all, run through `cmd_roadmap` with no monkeypatching of `load_roadmap`, asserting rc 2 and that the real function's exact `directory_exists=False` path is what the CLI layer reacts to — not a stub standing in for it.

Every test above is green before this step is considered finished.

`tests/cli/package_surface_help.golden.txt` — regenerated (see [Files](#files-creates-vs-edits)); `tests/cli/test_package_surface.py::TestHelpGoldenSnapshot::test_help_matches_golden` and `test_help_lists_every_subcommand` both stay green against the regenerated file, the latter trivially since this step adds no subcommand.

## Acceptance criteria

- `--view` takes exactly one of `walk` / `ledger` / `index` and is mutually exclusive with `--apply` and `--from-stage`, enforced by argparse.
- `--view` does not require `--from-existing`.
- `--mode` defaults to `"current"` in the roadmap that is actually rendered, while its own argparse default stays distinguishable from an explicit `--mode current` for the purpose of the without-`--view` rejection below.
- Passing `--mode` or `--id` without `--view`, or `--id` with a `--view` other than `index`, returns rc 2 with a message naming which flag requires which.
- `--view index` with no `--id` renders the full citation map; `--view index --id <row-id>` renders that id's citers.
- `--view walk` calls `render_traceability_walk` with `plans_dir`; `--view ledger` and `--view index` do not take `plans_dir`.
- A `LoadedRoadmap` with `directory_exists=False` returns rc 2; any other `LoadedRoadmap` state (including all four artifacts absent) returns rc 0, matching the plan's stated pre-flight-vs-render line.
- An invalid slug under `--view` returns rc 2 with the underlying `ValueError` message surfaced, not an uncaught traceback.
- The rendered view text reaches stdout unmodified — no extra header, prefix, or summary line added by `cmd_roadmap` itself.
- `--apply` and stage-run (`--from-existing` / `--from-stage`) invocations behave identically to before this step.
- `plan-tool` registers no new subcommand and `CAPABILITIES.md` gains no new capability row (nothing in this step's files touches either).
- `docs/cli/roadmap.md` and `docs/cli/README.md` are byte-identical to `python -m plan_tool.cli_reference --write`'s current output.
- `tests/cli/package_surface_help.golden.txt` matches `plan-tool --help` rendered at 80 columns.
- `plan_tool/cli/__init__.py`'s "Roadmap" catalog section documents all three invocation forms.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — `add_mutually_exclusive_group()` for joining `--view` to the existing `--apply` / `--from-stage` group, and the `choices=` / `default=` semantics `--view`, `--mode`, and `--id` are declared with, including how an unset default interacts with `choices` validation.

## Applicable guardrails

- **The plan's Architecture, "The CLI shape — settled 2026-08-07, user-confirmed; do not re-open."** This step implements the shape as stated — `--view` in the existing mutually exclusive group, `--mode` and `--id` as separate options gated by validation rather than by argparse structure — and does not revisit the rejected sibling-subcommand alternative.
- **The plan's Out of scope, "Machine-readable output."** No `--json` flag or machine-readable form on `roadmap` for this mode; the render functions return plain text and this step's argparse surface adds nothing that would imply otherwise.
- **The plan's "In scope" / Risks split between the module-chain doc sweep and the invocation-form sweep.** This step owns only the invocation-form half for the code-side files (`plan_tool/cli/__init__.py`'s catalog, `tests/cli/package_surface_help.golden.txt`) and the mechanical `docs/cli/` regeneration; the module-chain sweep (`CLAUDE.md`, `docs/ARCHITECTURE.md`, `ROADMAP_FORMAT.md`, `CAPABILITIES.md`) and the doc-side invocation-form sweep (`integrations/claude/SKILL.md`, `README.md`, `USE_CASES.md`) are step 7's, per its own `files:` list — this step's edits stop at the boundary its own `files:` list draws.
- **The plan's "In scope," "No new `CAPABILITIES.md` capability row."** The settled flag shape adds no subcommand, so this step must not add one for convenience or discoverability — `check_capabilities` would then have an orphan-subcommand finding to raise with no plan-level cover for it.

## Deferred

- **`--json` / machine-readable output** — plan-level Out of scope; no caller needs it yet.
- **A standalone `roadmap-view` subcommand** — the plan's Architecture names and rejects this alternative explicitly; not reconsidered here.
- **The module-chain doc sweep** (`CLAUDE.md`, `docs/ARCHITECTURE.md`, `ROADMAP_FORMAT.md` § "See also", `CAPABILITIES.md`'s `architecture-roadmap` `surfaces:` line) and the doc-side invocation-form sweep (`integrations/claude/SKILL.md`, `README.md`, `USE_CASES.md`) — step 7, per its own `files:` list.
- **`BACKLOG.md` #240 reconciliation** — the plan's final docs/status step (step 7) closes it on full shipment.
- **`plan_tool/cli_reference.py`'s hardcoded apply-only usage block** — out of this step's `files:` list; the auto-generated primary usage line already grows to cover `--view` with no change to that module.
- **Widening `-y`/`--yes` into a hard-rejected combination under `--view`** — it stays a benign no-op, unchanged from its existing behavior during a stage run; the plan names no requirement to reject it.
