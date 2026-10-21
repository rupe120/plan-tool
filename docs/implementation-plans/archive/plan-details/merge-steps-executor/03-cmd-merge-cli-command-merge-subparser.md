> **Auto-archived**: this plan was swept on 2026-06-19 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `cmd_merge` CLI handler + `merge` subparser beside `split`, regenerate the `docs/cli` reference

## Summary

Add `cmd_merge` to `plan_tool/cli/authoring.py` as the operator-driven inverse of `cmd_split`, plus a `merge` subparser in the same module's `register(subparsers)` and a `"merge": cmd_merge` dispatch entry beside `"split"`. The handler reads repeatable `--steps ID` (≥2) + optional `--title`, confirms the merge at the TTY via `_confirm_merge` before any mutation, calls `merge_steps` (step 2's `plan_tool/detail.py` orchestrator) much as `cmd_split` calls `split_step`, prints the merge/dry-run summary, then — unless `--no-detail` / `--no-completeness` — runs the shared `_run_completeness_tail`. The load-bearing decisions: import only `merge_steps` (the handler never names `MergeResult`); mirror `cmd_split`'s parse-guard → orchestrator → DetailError→rc-2 → tail → next-steps control flow invariant-for-invariant; and treat `docs/cli/merge.md` + the `docs/cli/README.md` row as **generated artifacts** emitted by `python -m plan_tool.cli_reference --write`, never hand-edited. On green, `plan-tool merge demo --steps 3 --steps 4` routes to `merge_steps(merge_ids=[3,4], title=None, …)`, a `<2`-id invocation exits 2 before any orchestrator call, and the CLI-reference drift guard (`tests/cli/test_cli_reference.py`) plus the `--help` golden snapshot pass with `merge` present.

## Table of Contents

- [Why](#why) — the orchestrator has no operator entry point yet
- [Files (creates vs edits)](#files-creates-vs-edits) — the handler/subparser module, its tests, and the generated reference
- [Implementation](#implementation) — `cmd_merge`, the `merge` subparser, dispatch wiring, and regeneration
- [Tests](#tests) — parse-contract + routing cases in `tests/cli/test_authoring_cmds.py`, plus the regenerated goldens
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — argparse append/subparser docs for this step
- [Deferred](#deferred) — out-of-scope items left for later steps

## Why

Steps 1–2 build the merge engine bottom-up: `create._apply_step_merge` (the pure transform) and `detail.merge_steps` (the orchestrator with `_merge_is_safe`, `_migrate_downstream_details_after_merge`, `_confirm_merge`, `MergeResult`). Nothing drives them — there is no `plan-tool merge` verb, so an over-decomposed plan still cannot be folded back from the command line. `cmd_split` (`plan_tool/cli/authoring.py:cmd_split`) is the proven forward sibling: it owns the parse guard, the `split_step` call, the dry-run/success rendering, the DetailError→rc handling, the completeness tail, and the next-steps pointer. This step builds the symmetric `cmd_merge` so the executor is reachable end-to-end, mirroring how `cmd_split` exposes `split_step`. Keeping the verb in `authoring.py` (beside `cmd_split` and its `register`) and the orchestrator in `detail.py` preserves the existing CLI-thin / orchestrator-fat layering.

## Files (creates vs edits)

- **New files:**
  - `docs/cli/merge.md` — **generated** by `python -m plan_tool.cli_reference --write` (one file per subcommand). Do not hand-author; running the generator after the subparser lands emits it.
- **Existing files (edits only):**
  - `plan_tool/cli/authoring.py` —
    - Add `cmd_merge` immediately after `cmd_split` (before `register`).
    - Extend the existing `from plan_tool.detail import (...)` block (the one importing `DetailError, generate_detail, shell_detail_invoker, split_step`) to also import `merge_steps` and `_confirm_merge`. Do **not** import the `MergeResult` type — the handler binds `result = merge_steps(...)` and reads `result`'s fields but never names the type (mirrors `cmd_split` importing `split_step` but not `SplitResult`).
    - In `register`, add the `p_merge = sub.add_parser("merge", …)` block immediately after the `p_split` block, reusing the same `parents=[yes_parent, iterate_parent]`.
    - Add `"merge": cmd_merge` to `register`'s returned dispatch dict, beside `"split": cmd_split`.
  - `plan_tool/cli/app.py` — add `cmd_merge` to the `from plan_tool.cli.authoring import (…)` block (app.py:222-232, beside `cmd_split`) so `getattr(plan_tool.cli, "cmd_merge")` resolves; without it `tests/cli/test_package_surface.py::TestParserDispatcherCorrespondence::test_every_subcommand_has_a_dispatch_handler` fails.
  - `plan_tool/cli/__init__.py` — add a `merge` line to the "Subcommands at a glance" module docstring catalog, beside the existing `split` row, honoring the in-file "keep this catalog … in sync" mandate (the catalog is not test-gated, so the edit must land in this step or it ships silently inconsistent), and add `"cmd_merge"` to `__all__` (line 106) for the curated-surface convention.
  - `integrations/claude/SKILL.md` and `integrations/codex/SKILL.md` — add `merge`-style rows in lockstep mirroring the existing `split` rows (the "split step N" task line and the **Authoring** capability-table row), keeping both SKILL files byte-parallel.
  - `tests/cli/test_authoring_cmds.py` — add `TestMergeParseContract` and `TestMergeCmd` classes beside the existing `TestSplitParseContract` / `TestSplitCmd` classes. Import `MergeResult` from `plan_tool.detail` inside the test bodies (the test constructs it to feed the patched orchestrator; the production handler does not).
  - `docs/cli/README.md` — **regenerated** (the index table gains a `merge` row); same generator pass as `merge.md`, not a manual edit.

## Implementation

### `plan_tool/cli/authoring.py` — `cmd_merge`

Mirror `cmd_split`'s control-flow shape exactly; only the operand (a set of ids → one merged step, vs one step → many) and the orchestrator differ.

- **Signature:** `def cmd_merge(args: argparse.Namespace) -> int:` — identical shape to `cmd_split`.
- **Context + plan resolution:** `ctx = _load_context(args)`; `path = resolve_plan_for_context(ctx, args.name)` (same two lines as `cmd_split`).
- **Parse the ids + guard ≥2 (before any orchestrator call):**
  - `ids = list(getattr(args, "steps", None) or [])`.
  - Reject `<2` distinct ids with `error(...)` + `return 2`, mirroring `cmd_split`'s two-title guard message style: e.g. `merge needs at least two step ids — pass --steps 3 --steps 4 (repeat --steps for more).` Use `len(set(ids)) < 2` so a duplicated id (`--steps 3 --steps 3`) is also rejected.
  - `author_details = getattr(args, "author_details", True)`.
  - `title = getattr(args, "title", None)` — optional; passed straight through to `merge_steps` (the orchestrator derives a default when `None`).
- **Run log:** mirror `cmd_split` — body-local `from plan_tool.detail import _plan_slug as _detail_plan_slug`, then `RunLogWriter.start(repo_root=ctx.repo_root, slug=_detail_plan_slug(path), command="merge", argv=list(sys.argv[1:]), plan_path=path, step_filter=None, flags={"steps": ids, "title": title, "author_details": author_details})`. (`step_filter` is the single-step int on `cmd_split`; merge has a set, so pass `None` and carry the ids in `flags`.)
- **Budget:** `budget = _resolve_iterative_budget(args)` inside the same `try/except CreateError` → `error` + `run_logger.run_end(outcome="error", rc=2, …)` + `return 2` arm `cmd_split` uses.
- **Confirm at the TTY before merging (deliberate divergence from `cmd_split`).** `cmd_split` defers confirmation to `generate_detail`'s Phase-B; merge has no Phase-B and re-authors over the members' **existing** detail bodies, so `cmd_merge` owns the gate at the CLI. After the id guard and before `merge_steps`: parse the plan, collect the member `Step`s whose id is in `ids`, derive the preview merged title (`title` if given, else the lowest-id member's title — the same default `merge_steps` derives). **Honor `--yes` and a non-interactive default:** when `getattr(args, "yes", False) or not sys.stdin.isatty()` the gate is **bypassed** and the merge proceeds — an explicit, assented merge runs headlessly (reconciling with `cmd_split`'s no-gate posture) rather than auto-declining with rc 2 in CI/piped/agent contexts. Otherwise (interactive TTY without `--yes`) call `confirmed = _confirm_merge(input, steps_to_merge=<member Steps>, merged_title=<preview>)`, and on `not confirmed` (a TTY decline), `error("merge aborted — no steps were changed")` + `return 2` **before** any orchestrator call or disk mutation. Skip the prompt also on `--dry-run` (nothing is mutated to confirm). `merge_steps` itself no longer prompts (step 2), so the gate fires exactly once.
- **Call the orchestrator** (the step-2 seam — confirm its shape at HEAD first, see below):
  ```
  result = merge_steps(
      path,
      merge_ids=ids,
      title=title,
      repo_root=ctx.repo_root,
      author_details=author_details,
      dry_run=getattr(args, "dry_run", False),
      run_logger=run_logger,
      budget=budget,
  )
  ```
  Wrap in `try/except DetailError as exc:` → `error(str(exc))`, `rc = 2`, `return rc` (verbatim mirror of `cmd_split`'s `split_step` call site).
- **Dry-run arm** (`result.dry_run`): mirror `cmd_split`'s preview block, sourcing fields from `MergeResult` (no `original_title` — merge has `folded_ids` / `merged_id` / `merged_title` instead):
  - `info(f"[dry-run] would merge step(s) {result.folded_ids} into step {result.merged_id}; no changes written.")`
  - Print the renumber map from `result.renumber` (only the `old != new` rows), then `result.new_plan` rows `(sid, title, deps)` — identical loops to `cmd_split`'s dry-run block.
  - `rc = 0; return rc`.
- **Success arm:**
  - `success(f"merged step(s) {', '.join(str(i) for i in result.folded_ids)} into step {result.merged_id}")`.
  - `info(f"  now: {result.merged_title}")` (the merge analog of `cmd_split`'s `was: <original_title>`).
  - When `author_details and result.detail_results`: build `wrote`/`skipped` from `result.detail_results` and call `_print_detail_summary(slug=args.name, wrote=wrote, skipped=skipped, rc=rc, repo_root=ctx.repo_root)` — byte-for-byte the same summary loop as `cmd_split`, including the `if "already exists" not in reason: rc = 1` downgrade.
- **Completeness tail:** when `rc == 0 and author_details and getattr(args, "auto_completeness", True)`, call `_run_completeness_tail(args, what="merge")` (the shared helper at `plan_tool/cli/authoring.py:_run_completeness_tail`, already used with `what="detail"` and `what="split"`).
- **Next-steps pointer:** mirror `cmd_split`'s two arms via `_print_next_steps`:
  - `--no-detail` (`not author_details`) → point only at `plan-tool detail {args.name}` ("author the merged step's detail file").
  - else → `plan-tool reconcile-plan {args.name}` ("check the merged step against the codebase") + `plan-tool run {args.name}` ("execute the next runnable step"). The merged step may describe unbuilt work, so reconcile-plan (plan-vs-code) is offered as a follow-up, not run here — identical posture to `cmd_split`.
- **`finally` run-log tail:** mirror `cmd_split` — `run_logger.run_end(outcome=("success" if rc == 0 else "error"), rc=rc, error=err_msg)`, with the `KeyboardInterrupt → rc=130` re-raise arm.

#### Confirm the step-2 seam at HEAD before wiring

- **`merge_steps` and `MergeResult` are unimplemented at HEAD** (step 2, `depends_on: 2`). Pin the consumed shape to step 2's detail (`docs/implementation-plans/plan-details/merge-steps-executor/02-merge-steps-orchestrator-merge-safe.md`):
  - Signature: `merge_steps(plan_path, *, merge_ids: list[int], title: Optional[str] = None, repo_root, author_details=True, dry_run=False, invoker=shell_detail_invoker, reporter=None, run_logger=None, prompt_fn=None, budget=IterativeBudget(enabled=False)) -> MergeResult`.
  - `MergeResult` fields read here: `dry_run`, `folded_ids`, `merged_id`, `merged_title`, `detail_results` (list of `DetailResult`), and on dry-run `renumber` / `new_plan`.
- **Before writing the call site, grep `merge_steps` / `MergeResult` against HEAD.** If step 2 shipped a divergent kwarg name or field (e.g. `merged_id` vs a renamed survivor field), adapt the call/render to the **real** seam rather than this prose. Do not author against field names that exist only here.

### `plan_tool/cli/authoring.py` — `merge` subparser in `register`

- **Add `p_merge` immediately after the `p_split` block**, reusing `parents=[yes_parent, iterate_parent]` (the locally-built shared parents) so per-subcommand help stays byte-consistent with `split`/`detail`.
- **`help=`** : `"merge a contiguous set of steps into one on demand, combine + re-author their detail file, then loop on the completeness audit"`.
- **Positional `name`:** copy `p_split`'s `name` argument verbatim ("plan name — slug, filename stem …").
- **`--steps`** (the repeatable id flag — the merge analog of split's single `--step`):
  - `p_merge.add_argument("--steps", type=int, action="append", dest="steps", metavar="ID", required=True, help=…)`.
  - `action="append"` accumulates each `--steps N` into `args.steps`; `type=int` coerces each. Help: ids to fold together; pass `--steps` at least twice for a contiguous dependency chain; the set collapses to a single step at the lowest id and the plan renumbers to contiguous `1..N`.
  - Note the singular/plural inversion from `split` is deliberate: split targets **one** step (`--step`), merge targets a **set** (`--steps`).
- **`--title`** (optional, the merge-only field with no split analog):
  - `p_merge.add_argument("--title", dest="title", metavar="TITLE", default=None, help=…)`.
  - Help: optional title for the merged step; omit to let the orchestrator derive one from the folded members' titles.
- **`--iterate`** : `action=argparse.BooleanOptionalAction, default=True` — copy `p_split`'s `--iterate` (default ON, mirroring `detail`/`split`; `--no-iterate` downgrades the tail to an audit-only report). Add it on the subparser, not the shared `iterate_parent`, for the same default-divergence reason documented in `register` (argparse `parents=` copies actions by reference, so a single parent can't express per-subcommand defaults).
- **`--no-detail`** : `action="store_false", dest="author_details", default=True` — copy `p_split`'s, swapping prose to "merge only: renumber + combine-and-archive detail files, but don't re-author the merged step's body or run the completeness tail (author it later with `plan-tool detail <name>`)".
- **`--no-completeness`** : `action="store_false", dest="auto_completeness", default=True` — copy `p_split`'s verbatim.
- **`--dry-run`** : `action="store_true"` — copy `p_split`'s, swapping prose to "preview the merge — print the old→new step renumber map and the resulting plan — without writing the plan, renaming/archiving detail files, or authoring/auditing anything".
- **Dispatch:** extend `register`'s `return { "create": cmd_create, "detail": cmd_detail, "split": cmd_split }` to add `"merge": cmd_merge`.

### Command ordering (no `parser.py` edit)

- **`merge` is intentionally NOT added to `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`** — and neither is `split` today. Commands absent from that tuple sort to the end via `_canonical_index` returning `len(CANONICAL_COMMAND_ORDER)`, preserving registration order among the unknowns. `merge`, registered right after `split`, therefore lands directly after `split` in both `--help` and the generated `docs/cli/README.md` index. `parser.py` is outside this step's `files:` — adding `merge`/`split` to the canonical tuple is a separate ordering decision, not required here.

### Catalog + SKILL lockstep (hand-edited, not generated)

- **`plan_tool/cli/__init__.py` "Subcommands at a glance" docstring** — add a `merge` line beside the existing `split` row, matching its `plan-tool split <name> --step N --into "..."` formatting (verb + signature + one-line description). The in-file mandate keeps this catalog in sync with the registered subcommands, and it is **not** test-gated, so the edit must land here — `split` is already catalogued; omitting `merge` ships a silently inconsistent catalog.
- **`integrations/claude/SKILL.md` + `integrations/codex/SKILL.md`** — add `merge` rows in lockstep mirroring the `split` rows: the task-routing line (the analog of "split step N of plan X …") and the **Authoring** capability-table row (the analog of `split <name> --step N --into "..."`). Keep both SKILL files byte-parallel — the same rows in the same places — per the SKILL-lockstep convention.
- These three edits are hand-authored (not emitted by the generator) and carried in this step's `files:`; the captured "catalog edits land in the subcommand's own step" lesson means they belong here with `cmd_merge`, not deferred.

### Regenerate the generated reference

- **`docs/cli/merge.md` and the `docs/cli/README.md` row are produced by the generator**, not hand-written. After the subparser lands, run `python -m plan_tool.cli_reference --write`. `plan_tool/cli_reference.py` walks the live argparse parser, so the new `merge` subparser yields `merge.md` (usage line, arguments/options tables) and a `merge` index row automatically.
- **Do not hand-edit either file** — `tests/cli/test_cli_reference.py` regenerates in memory and fails on any drift from the committed bytes. The committed files must equal the generator's current output.

### Shared logic / parallel call sites

- **Foundational logic added:** a CLI verb that parses `--steps`/`--title`, guards a minimum-cardinality precondition, calls a `detail.py` structural orchestrator, and runs the shared completeness tail.
- **The one parallel site is `cmd_split`** (`plan_tool/cli/authoring.py`) — `cmd_merge` is its structural twin and must mirror it for shape (guard → orchestrator → DetailError→rc-2 → dry-run/success render → tail → next-steps → run-log `finally`). The split *body* is the layout template only; the merge operand (set→one), the `MergeResult` field set (`folded_ids`/`merged_id`/`merged_title`, no `original_title`), and the `--steps`/`--title` flags are re-derived, not copied. `_run_completeness_tail`, `_print_detail_summary`, `_print_next_steps`, and `_resolve_iterative_budget` are already shared leaves both verbs consume — reuse them, mint nothing.
- **No consolidation refactor is warranted** — two sibling verbs sharing a hand-mirrored shape is the established pattern here (`cmd_create`/`cmd_detail` likewise). Factoring a common split/merge CLI driver is not needed and not in scope.

## Tests

All in `tests/cli/test_authoring_cmds.py`, mirroring the existing `TestSplitParseContract`/`TestSplitCmd` classes (patch `plan_tool.cli.authoring.merge_steps` and `plan_tool.cli.app.cmd_completeness` — the documented interception seams — so **no claude is invoked**). The structural merge itself is covered in `tests/test_detail.py` by step 2; these pin the parse contract and routing branches. Real-run routing cases run under the suite's non-interactive stdin, so the `--yes`/non-TTY bypass lets the merge proceed without patching `_confirm_merge`; the decline case patches `sys.stdin.isatty` True (and omits `--yes`) so the TTY gate is actually reached.

### `TestMergeParseContract` (parse-only, via `build_parser().parse_args`)

- `test_steps_appends_and_defaults_on` — `merge demo --steps 3 --steps 4` → `args.steps == [3, 4]`, `args.iterate is True`, `args.author_details is True`, `args.auto_completeness is True`.
- `test_steps_is_required` — `merge demo` (no `--steps`) raises `SystemExit` (argparse `required=True`).
- `test_title_optional_defaults_none` — `merge demo --steps 1 --steps 2` → `args.title is None`; `--title "X"` → `args.title == "X"`.
- `test_no_detail_and_no_completeness_flags` — `--no-detail --no-completeness` → `args.author_details is False`, `args.auto_completeness is False`.

### `TestMergeCmd` (routing, via `main(argv)` on a registered temp plan)

- `test_fewer_than_two_ids_rejected` — `merge demo --steps 1` → rc 2, `"at least two"` on stderr, `merge_steps` never called (the guard fires first).
- `test_duplicate_ids_rejected` — `--steps 3 --steps 3` → rc 2 (the `len(set(...)) < 2` guard).
- `test_interactive_decline_aborts_before_merge_steps` — patch `sys.stdin.isatty` True and `_confirm_merge` to return `False` (no `--yes`) → rc 2, `"aborted"` on stderr, `merge_steps` never called.
- `test_yes_bypasses_gate_and_proceeds` — pass `--yes` (or leave stdin non-interactive) → `_confirm_merge` is **not** called and `merge_steps` runs, rc 0.
- `test_confirm_invoked_before_merge_steps` — patch `sys.stdin.isatty` True, `_confirm_merge` to return `True` (no `--yes`) and capture its args/call order → it receives the member steps + preview title and fires before `merge_steps`; on `--dry-run` it is **not** called.
- `test_clean_merge_authors_and_runs_completeness_tail` — patch `merge_steps` to return a `MergeResult(merged_id=1, merged_title="Merged", folded_ids=[1, 2], folded_titles=["A", "B"], detail_results=[DetailResult(step_id=1, output_path=…, written=True)])` and capture its kwargs; patch `app.cmd_completeness`. Assert rc 0, `merge_ids == [3, 4]`, `title` forwarded, `author_details is True`, and the completeness tail ran.
- `test_no_completeness_skips_tail` — `--no-completeness` → tail does not run, rc 0.
- `test_no_detail_points_at_detail_next` — `--no-detail` → fake `merge_steps` asserts it received `author_details=False`; stderr advertises `plan-tool detail demo`, not `reconcile-plan`; tail skipped.
- `test_dry_run_previews_without_writing` — patch `merge_steps` to return a `dry_run=True` `MergeResult` with populated `renumber` / `new_plan`; assert rc 0 and the renumber/`resulting plan` lines print. (Driving the **real** `merge_steps` dry-run requires steps 1–2 landed; until then this routing test patches the orchestrator. State that explicitly.)
- `test_detail_error_returns_2` — patch `merge_steps` to raise `DetailError("step 9 not found …")` → rc 2, message on stderr.
- `test_title_forwarded_to_orchestrator` — `--title "Combined"` → the patched `merge_steps` receives `title == "Combined"`.

### Generated-reference + surface guards (regenerate, don't author)

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift` — passes once `python -m plan_tool.cli_reference --write` has emitted `merge.md` and the `merge` README row; `test_no_orphan_reference_files` and `test_every_subcommand_has_a_reference_file` confirm `merge.md` exists and matches.
- `tests/cli/test_package_surface.py` — `test_register_returns_dispatch_for_every_subcommand` and `test_help_lists_every_subcommand` cover `merge` automatically once `cmd_merge` is dispatched. **Re-seed the `--help` golden** `tests/cli/package_surface_help.golden.txt` (it gains the `merge` line) — delete it and re-run so `test_help_matches_golden` re-seeds, or regenerate per that test's mechanism. This fixture is outside the declared `files:` but is a required-but-undeclared edit (the top-level `--help` text changes when a subcommand is added).

### Test-creation order (feature step)

- This is a **feature** step — a new CLI verb. Add the `TestMergeParseContract` + `TestMergeCmd` cases **with** the `cmd_merge`/subparser implementation; each case maps to a behavior above.
- **Green-before-done gate:** every new test in `tests/cli/test_authoring_cmds.py` is green, `python -m plan_tool.cli_reference --write` has been run, and `tests/cli/test_cli_reference.py` + `tests/cli/test_package_surface.py` pass (with the `--help` golden re-seeded) before this step is considered finished.

## Acceptance criteria

- `plan-tool merge demo --steps 3 --steps 4` routes to `merge_steps(merge_ids=[3, 4], title=None, …)` and exits 0 on a clean fold (orchestrator patched in tests).
- `merge demo --steps 1` (a single id) exits 2 with an "at least two" message **before** `merge_steps` is called.
- On a real (non-`--dry-run`) interactive merge without `--yes`, `cmd_merge` invokes `_confirm_merge` at the TTY **before** `merge_steps`; a declined confirmation returns rc 2 with the plan and detail files unchanged. With `--yes` or under a non-interactive stdin the gate is bypassed and the merge proceeds headlessly.
- `merge` with no `--steps` exits non-zero from argparse (`--steps` is `required=True`).
- `args.steps` is a `list[int]` accumulated by `action="append"`; `args.title` defaults to `None`; `args.iterate`/`args.author_details`/`args.auto_completeness` default `True`.
- A `DetailError` from `merge_steps` maps to rc 2 with the message on stderr; a clean run with `author_details` and findings runs `_run_completeness_tail(args, what="merge")`.
- `register`'s returned dispatch dict contains `"merge": cmd_merge`; `tests/cli/test_package_surface.py::TestRegistrationSeam::test_register_returns_dispatch_for_every_subcommand` passes.
- `docs/cli/merge.md` exists and equals `python -m plan_tool.cli_reference --write`'s output; `docs/cli/README.md` has a `merge` row; `tests/cli/test_cli_reference.py` passes with no drift or orphan.
- The `--help` golden `tests/cli/package_surface_help.golden.txt` includes `merge` and `test_help_matches_golden` passes.
- `plan_tool/cli/__init__.py`'s "Subcommands at a glance" catalog has a `merge` line beside `split`, and `integrations/claude/SKILL.md` + `integrations/codex/SKILL.md` carry byte-parallel `merge` rows mirroring their `split` rows.

## References

- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — The `action="append"` pattern for repeatable `--steps`, `BooleanOptionalAction` for `--iterate`/`--no-iterate`, `parents=` action-reference copying, and subparser (`add_parser`) wiring.

## Deferred

- **`granularity-merge` finding → auto-invoke `cmd_merge`** — the decision-to-execution wiring from the granularity advisor; this step ships the operator verb only (recommend-only loop closed later).
- **`merge` / `split` in `CANONICAL_COMMAND_ORDER`** (`plan_tool/cli/parser.py`) — neither verb is in the canonical tuple; both sort to the end. `parser.py` is outside this step's `files:`; an explicit ordering placement is a separate decision.
- **`PLAN_FORMAT.md` / `RUNBOOK.md` prose for `merge`** — step 4 covers `RUNBOOK.md`; the `PLAN_FORMAT.md` pass is a separate non-code edit once the command shape is final.
- **A `_merge_renumber_map` helper** mirroring `_split_renumber_map` — only minted if a non-dry-run caller needs the renumber rows; step 2 builds them inline in `merge_steps`'s dry-run arm, so the CLI consumes `MergeResult.renumber` rather than re-deriving.
