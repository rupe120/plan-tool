> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add a contiguous N..M range carve to scope-out with a `--through` flag

## Summary

Add a `--through M` flag to `plan-tool scope-out` so an operator can carve the inclusive `N..M` region (from `--step N`) out of a plan in one carve, instead of one step at a time. The work sits on top of step 1's set-based narrow: `plan_tool/scope_out.py:scope_out_step` widens from a single `carved_id` to an ordered set, renders **one** forward-seed covering the whole region (reusing the existing seed block helpers), and calls the already-generalized `compute_narrow`/`apply_narrow`. `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` expands `N..M` into the id set, rejects an out-of-order range with a clear error, and keeps `--step N` alone as the unchanged single-step path. On green, `plan-tool scope-out <name> --step 2 --through 4 --apply -y` writes one seed and atomically narrows the plan (rollback on any failure), while every existing single-step carve behaves exactly as before.

## Table of Contents

- [Why](#why) — what carving one step at a time costs and what the range form unblocks
- [Input](#input) — the step-1 narrow contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files, the doc, and the two test files
- [Implementation](#implementation) — the range flag, the region seed, and the invariants that must hold
- [Tests](#tests) — unit coverage for the region carve plus CLI-integration coverage for the flag
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the tests to add with the code and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — argparse and pytest docs for this step
- [Deferred](#deferred) — disjoint carves, convergence actuation, and other out-of-scope items

## Why

`plan-tool scope-out` carves exactly one `--step N` today, so carving a contiguous over-packed region means running the command once per step — each run writes its own seed and re-narrows the plan, fragmenting the region into several unrelated forward-seeds. Step 1 already generalized the narrow (`compute_narrow`/`apply_narrow`) to drop an ordered set of ids atomically, but nothing exposes that: `scope_out_step` and the CLI still pass a single `carved_id`. This step exposes the set through the CLI as a contiguous `N..M` range and produces one seed for the whole region, so an operator (and, later, step 3's `convergence --apply-scope-out`) can carve an over-packed region in a single atomic step. It also keeps the single-step path unchanged, so existing carves and the `convergence_cmd.py` caller that passes `carved_id=` see no behavior change.

## Input

This step consumes the set-based narrow contract that **step 1** produces in `plan_tool/scope_out.py`:

- **`compute_narrow` accepts `carved_ids: Sequence[int]`** (and still accepts the scalar `carved_id=` keyword). It normalizes to a sorted, de-duplicated list, builds the old→new shift map over the set, repairs `depends_on`, and returns a `NarrowPreview` with `blockers` empty when safe.
- **`NarrowPreview` / `NarrowResult` carry list fields** — `carved_ids: list[int]` and `archive_details` / `archived: list[Path]`. `NarrowResult.renumber` and `NarrowResult.new_current_id` keep their scalar/tuple shapes (read by `scope_out_cmd.py`).
- **Blocker semantics carry over per id in the set** — `inbound-dependent` fires when a *kept* survivor depends on any carved id; a carved-on-carved edge inside the region is not a blocker. `step-missing` lists any absent id. `downstream-orphan`, `empty-plan`, and `non-canonical-numbering` are unchanged.

Do not restate step 1's shift-map math or rollback mechanism here — call `compute_narrow(..., carved_ids=[...])` and trust it.

## Files (creates vs edits)

- **New files:**
  - `tests/cli/test_scope_out_cmd.py` — CLI-integration tests for the `--through` flag, driving `main([...])` through parse → dispatch → command.
- **Existing files (edits only):**
  - `plan_tool/scope_out.py` — widen `scope_out_step` to carve an ordered id set; render one region seed (reuse `_scope_block` / `_done_context_block` / `_upstream_block`); generalize `_resolve_upstream_context`, `_resolve_carved_detail_path`, and `_carved_seed_path` over the set; add `carved_ids` to `ScopeOutResult`.
  - `plan_tool/cli/scope_out_cmd.py` — add the `--through` argument in `register`; expand `N..M` to the id set and reject out-of-order ranges in `cmd_scope_out`; update `render_scope_out_result` to show a range label.
  - `docs/cli/scope-out.md` — regenerate with the new `--through` flag (`python -m plan_tool.cli_reference --write`).
  - `tests/test_scope_out.py` — add unit tests for the region carve at the `scope_out_step` / region-seed level.

## Implementation

**Core behavior change: `scope-out` carves a contiguous `N..M` region as one atomic carve, single-step as the special case.** The CLI owns the range→set expansion and the out-of-order rejection; `scope_out_step` owns the region seed and threading the set to the step-1 narrow; the narrow itself is unchanged.

### The CLI: parse the range, reject out-of-order (`plan_tool/cli/scope_out_cmd.py`)

- **Add `--through M` in `register`**, an optional `type=int` argument alongside the required `--step N`. Keep `--step` required. Update its help to say `--through M` carves the inclusive `N..M` region and defaults to a single-step carve when omitted.
- **Expand the range in `cmd_scope_out`** before calling `scope_out_step`:
  - `args.through is None` → carve `[args.step]` (single-step, the default).
  - `args.through < args.step` → out-of-order range: print a clear error to stderr and return a non-zero rc (a usage error, not a finding). One way: return `2`, matching argparse's usage-error convention. Do **not** route this through a `ScopeOutResult` outcome — it never reaches `scope_out_step`.
  - otherwise → carve `list(range(args.step, args.through + 1))`.
- **Contiguity is guaranteed by the range expansion** — `range(N, M+1)` is always contiguous, so there is no separate non-contiguous case to reject at the CLI. An id in `N..M` that runs past the plan's last step is handled downstream: `compute_narrow` returns a `step-missing` blocker → the existing `step-missing` outcome and rc 0. Do not duplicate a bounds check in the CLI.
- **`render_scope_out_result` shows a range label when the region has more than one id.** It is shared with `convergence --apply-scope-out` (which passes a single id), so single-id rendering must stay the same. One way: read the new `ScopeOutResult.carved_ids` and render `steps N..M` when `len > 1`, else the current `step N` message. The `recommend_hint` from `cmd_scope_out` should include `--through M` when the operator asked for a range.

### `scope_out_step`: carve the set, render one region seed (`plan_tool/scope_out.py`)

- **Widen the signature to accept the set while keeping `carved_id` working.** `plan_tool/cli/convergence_cmd.py:cmd_convergence` calls `scope_out_step(path, carved_id=rec.step_focus, ...)` and is **out of scope** for this step, so the scalar keyword must still work. Mirror step 1's back-compat shape: add `carved_ids: Sequence[int] | None = None`, keep `carved_id: int | None = None`, require exactly one, and normalize to a sorted, de-duplicated list (reuse or mirror step 1's normalize helper — do not re-derive the ordering differently, or the seed and the narrow could disagree on which ids are carved).
- **Thread the set to the step-1 narrow** — call `compute_narrow(plan, carved_ids=<set>, ...)` instead of `carved_id=`. The blocker gate, opt-in gate, and confirm gate around it are unchanged; the blocker→outcome mapping (`_outcome_for_blockers`) already covers the set because step 1 kept the `NarrowBlocker.kind` strings.
- **Render one forward-seed for the whole region.** The apply branch currently resolves one carved step's detail and calls `render_carved_seed(...)` once. Generalize it to loop the carved steps and produce a single seed covering all of them. The key design decision: **reuse the existing block helpers** (`_scope_block`, `_done_context_block`, `_upstream_block`) so the region seed's prose matches the single-step seed's prose — one source for the seed vocabulary. One clean approach:
  - Keep `render_carved_seed` unchanged for the single-step path (so all its existing block tests and the single-step round-trip stay green).
  - Add a region renderer (e.g. `render_carved_region_seed`) that emits one `## Scope to re-plan` + `## Done-context` pair per carved step (in ascending id order) and one merged upstream block, then have `scope_out_step` call `render_carved_seed` when the region is one id and the region renderer when it is more than one.
  - This keeps the single-step seed exactly as it is and localizes all new prose to the region path. The alternative — folding a sequence into `render_carved_seed` itself — risks changing the single-step output that `test_scope_out_apply_yes_carves`'s round-trip depends on; prefer the branch unless you can prove the single-id output is unchanged.
- **Upstream context spans the whole region and excludes in-region deps.** `_resolve_upstream_context` resolves one carved step's `depends_on` to post-narrow `(id, title, status)` triples. Generalize it to gather the deps of **all** carved steps, drop any dep that points at another carved id (that edge is internal to the region and re-planned together, not an external prerequisite), de-duplicate, and map surviving deps through `preview.renumber` exactly as today. A dep on a survivor is the only thing that becomes an upstream/external prerequisite.
- **Resolve every carved step's detail.** `_resolve_carved_detail_path` returns `(path, detail_missing)` for one step (pointer first, canonical fallback, missing flag). Call it per carved step so each region block carries its own body or its own never-detailed / missing-detail note. Keep the three-case contract per step unchanged.
- **Name the region seed after the range.** `_carved_seed_path` derives `plan-seeds/<plan-slug>-carved-<step-slug>.md` from the single carved title and never overwrites. For a region, include the range in the filename (e.g. `<plan-slug>-carved-<first-step-slug>-through-<M>.md`) so a region seed is distinguishable and still collision-safe (the `-2`, `-3`, … suffix loop carries over). Keep the single-step filename unchanged.
- **`ScopeOutResult` gains `carved_ids: list[int]`; keep `carved_id: int` scalar.** `plan_tool/cli/scope_out_cmd.py` reads `result.carved_id` in its `recommend_hint`, so keep the scalar populated as the first (N) id. Populate `carved_ids` with the full region for the range label. The five `outcome` strings and the seed-first / all-or-nothing contract are unchanged.

### Constraints that are not free to vary

- **Single-step behavior stays identical** — same seed bytes, same seed filename, same narrowed plan, same `ScopeOutResult` outcome. Existing `TestScopeOutCLI` tests and the `render_carved_seed` block tests must pass unmodified.
- **`carved_id=` must remain a valid keyword** on `scope_out_step` (the `convergence_cmd.py` caller) and on `compute_narrow` (step 1's contract).
- **Seed-first order holds for the region** — write the one region seed, then `apply_narrow`. A post-seed `apply_narrow` failure propagates as an exception (no `ScopeOutResult`), leaving the seed on disk as a durable orphan, exactly as the single-step path documents.
- **In-region deps are never upstream/external prerequisites** — a carved step depending on another carved step must not appear in the seed's prerequisite sections, or the re-plan reads a prerequisite that points at itself.
- **Contiguity comes only from the range expansion** — the narrow accepts any subset (step 1), so contiguity is a CLI concern; do not add a contiguity check inside `scope_out.py`.

### Shared logic and where it lives

The foundational logic here is **expand a contiguous `N..M` range into the carved id set and refuse an out-of-order one**. Grep confirms this is the only range-expansion site: `plan_tool/cli/convergence_cmd.py:cmd_convergence` still carves one `rec.step_focus`, and `plan_tool/split_criteria.py` calls `compute_narrow(carved_id=step.id, ...)` for a single step — both single-id, out of scope. `plan_tool/convergence_diagnosis.py:_scope_out_command` renders `plan-tool scope-out <slug> --step N` today; teaching it to render the `--through M` range form and having `convergence --apply-scope-out` actuate it is **step 3's job** (it `depends_on` this step), so leave those two symbols alone here — this step only makes the `--through` surface exist for step 3 to target.

## Tests

### Unit tests — `tests/test_scope_out.py`

Cover the region carve at the `scope_out_step` / region-seed level. Reuse the module's `_mk_plan` / `_mk_step` / `_render` / `_register_plan` / `_scope_out_argv` / `_seed_files` / `_safe_four_step_plan` helpers.

- `test_scope_out_step_carves_contiguous_region` — `scope_out_step(carved_ids=[2,3])` on a safe plan narrows the surviving ids and writes exactly one seed.
- `test_region_seed_covers_every_carved_step` — the region seed names each carved step's title and body under its own `## Scope to re-plan` block.
- `test_region_seed_excludes_in_region_deps_from_prerequisites` — a carved step depending on another carved step does not appear as an upstream/external prerequisite.
- `test_region_seed_reports_survivor_dep_as_prerequisite` — a carved step depending on a surviving step renders that survivor (by post-narrow id) as a prerequisite.
- `test_region_seed_path_encodes_range` — the region seed filename reflects the `N..M` range and never overwrites an existing seed.
- `test_scope_out_step_still_accepts_carved_id_keyword` — the scalar `carved_id=N` path is unchanged (single seed, same outcome), pinning the `convergence_cmd.py` caller's contract.
- `test_region_carve_inbound_dependent_survivor_is_unsafe` — carving `[2,3]` when a surviving step depends on `3` returns the `unsafe` outcome and writes nothing.
- `test_region_result_populates_carved_ids_and_scalar` — `ScopeOutResult.carved_ids` holds the region and `carved_id` holds the first id.

### CLI-integration tests — `tests/cli/test_scope_out_cmd.py` (new)

Drive `main([...])` through the real parse → dispatch → command path. These need a **multi-step** plan; `CliRepo.add_plan` writes a single-step plan, so either write a multi-step plan file into the repo directly (registering it in the manifest) or reuse the `_register_plan` / `_scope_out_argv` approach from `tests/test_scope_out.py`. Mark the class `@pytest.mark.integration` since it drives `main`.

- `test_through_carves_region_and_narrows_plan` — `--step 2 --through 4 --apply -y` writes one seed and leaves the expected renumbered plan on disk.
- `test_through_out_of_order_is_rejected` — `--step 4 --through 2` prints a clear error, returns non-zero, and writes nothing / leaves the plan untouched.
- `test_through_equal_to_step_is_single_step` — `--step 2 --through 2` behaves like `--step 2` (one seed, single-step narrow).
- `test_step_only_unchanged` — `--step 2 --apply -y` with no `--through` carves one step exactly as before.
- `test_through_recommend_only_by_default` — `--step 2 --through 3` without `--apply` writes nothing and shows the range in the recommend hint.
- `test_through_past_last_step_is_step_missing` — `--step 3 --through 9` surfaces the `step-missing` refusal with rc 0.
- `test_region_seed_round_trips_through_create_from_existing` — the emitted region seed ingests cleanly through `create --from-existing` with create's invoker stubbed (mirror `test_scope_out_apply_yes_carves`'s round-trip).
- `test_scope_out_help_lists_through` — `build_parser()` shows `--through` on the `scope-out` subparser.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the tests above **with** the implementation:

- Add the CLI arg + range expansion, then the out-of-order and single-step CLI tests.
- Add the region-seed rendering, then the region-seed unit tests.
- Add the `scope_out_step` set-widening + `ScopeOutResult.carved_ids`, then the carve/round-trip tests.

**Green-before-done gate:** every new test above must be green, and the existing single-step suite (`TestScopeOutCLI`, the `render_carved_seed` block tests, the `scope_out_step` orchestrator tests) must pass **unmodified**, before this step is finished. Run `uv run pytest tests/test_scope_out.py tests/cli/test_scope_out_cmd.py -q`.

## Acceptance criteria

- `plan-tool scope-out <name> --step 2 --through 4 --apply -y` writes exactly one forward-seed covering steps 2–4 and narrows the plan atomically; on any mid-carve failure the plan and detail files match their pre-carve state.
- `plan-tool scope-out <name> --step 4 --through 2` prints a clear out-of-order error, returns non-zero, and mutates nothing.
- `plan-tool scope-out <name> --step 2 --through 2` and `--step 2` (no `--through`) both carve a single step with identical output.
- `scope_out_step(path, carved_id=N, ...)` still works unchanged (the `convergence_cmd.py` caller compiles and behaves identically).
- The region seed renders one scope+done block per carved step, lists survivor deps as prerequisites, and never lists an in-region dep as a prerequisite; it ingests through `create --from-existing`.
- `ScopeOutResult.carved_ids` holds the full region; `ScopeOutResult.carved_id` holds the first id; `render_scope_out_result` shows a range label for a multi-id carve and the single-step message for one id.
- `docs/cli/scope-out.md` lists `--through` and `tests/cli/test_cli_reference.py` passes (no drift).
- `uv run pytest tests/test_scope_out.py tests/cli/test_scope_out_cmd.py -q` passes; existing single-step tests pass unmodified.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — for adding the `--through` option to the `scope-out` subparser and the usage-error return convention for an out-of-order range.
- [How to mark test functions with attributes (pytest)](https://docs.pytest.org/en/stable/how-to/mark.html) — `@pytest.mark.integration` gates the new CLI-entry-point tests apart from the unit-first suite.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture keeps the region-seed and narrow tests hermetic.

## Deferred

- **Disjoint (non-contiguous) region carve** — `compute_narrow`/`apply_narrow` accept any id set (step 1), but the CLI exposes only the contiguous `N..M` case; exposing a disjoint carve is deferred until a caller needs it.
- **`convergence` range rendering and actuation** — teaching `plan_tool/convergence_diagnosis.py:_scope_out_command` to print the `--through M` form and having `plan_tool/cli/convergence_cmd.py` actuate a multi-region `FORK_SCOPE_OUT` via the range carve is **step 3** (depends_on this step).
- **Consolidating drop-renumber with `detail.py`'s merge renumber** — the parallel renumber+`depends_on`-repair in `plan_tool/detail.py:merge_steps` / `plan_tool/create.py:_apply_step_merge` stays a separate reconcile-only refactor, unchanged here.
- **Moving existing `TestScopeOutCLI` into `tests/cli/`** — the single-step CLI tests stay in `tests/test_scope_out.py`; only the new `--through` CLI tests land in `tests/cli/test_scope_out_cmd.py`.
