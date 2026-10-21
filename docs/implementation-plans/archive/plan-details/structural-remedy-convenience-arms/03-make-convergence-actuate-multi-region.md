> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make convergence actuate a multi-region FORK_SCOPE_OUT as a range carve

## Summary

Today `plan_tool/convergence_diagnosis.py:classify_fork` only recognizes a scope-out or localized fork when every recurring region resolves to **one and the same** step; several spinning regions on **distinct** steps always fall to the cautious `FORK_STRUCTURAL` re-seed. This step teaches `classify_fork` to recognize one more shape: recurring regions that resolve to a **contiguous ascending range of distinct steps, all still severe and not improving**, and emit a `FORK_SCOPE_OUT` whose remedy is the range carve `plan-tool scope-out <slug> --step N --through M` (the `--through` surface step 2 built). `plan_tool/cli/convergence_cmd.py:_actuate_scope_out` then actuates that range through step 2's set-aware `scope_out_step` (calling it with the full id set), so `convergence --apply-scope-out` carves the whole over-packed region in one atomic carve. The main design decision: keep the single-step scope-out and the structural fallback byte-for-byte the same — the range is a **new middle case** between them, gated on contiguity plus every step in the range having a severe region, so a gap or a mixed-severity range still falls structural. On green, a spinning plan whose steps 2–4 all stay high-and-flat prints and (under `--apply-scope-out`) actuates `--step 2 --through 4`.

## Table of Contents

- [Why](#why) — what a multi-region spin can't do today and why the range carve closes it
- [Input](#input) — the step-2 set-aware scope-out contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and two test files
- [Implementation](#implementation) — the new range branch in classify_fork, the range command, the render, and the actuator
- [Tests](#tests) — unit coverage for the classifier/command/render plus CLI-integration coverage for the carve
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the tests to add with the code and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — argparse and pytest docs for this step
- [Deferred](#deferred) — split-criteria display, disjoint carves, and other out-of-scope items

## Why

A plan can spin on a whole over-packed **region** — steps 2, 3, and 4 each re-surfacing high, not-improving findings audit after audit. `classify_fork` sees several distinct step foci, can't pick one `--step N`, and correctly falls to `FORK_STRUCTURAL` (re-seed the whole plan). But step 2 just shipped a cheaper remedy: `scope-out --step N --through M` carves a contiguous region into one forward-seed and narrows the plan atomically. When the spinning region is contiguous and uniformly severe, carving that band out and deferring it is a smaller, more surgical move than tearing the whole plan down to a re-seed. Right now nothing connects the diagnosis to that remedy — the range carve exists only as a hand-run CLI. This step makes the diagnostic recognize the range shape and makes `--apply-scope-out` actuate it, finishing the plan's Arm 1 acceptance criterion: `plan-tool convergence <name> --apply-scope-out` actuates a multi-region `FORK_SCOPE_OUT` focus via the range carve.

## Input

This step consumes what **step 2** produces in `plan_tool/scope_out.py` and `plan_tool/cli/scope_out_cmd.py`:

- **`scope_out_step` accepts an ordered id set.** Step 2 widens it to take `carved_ids=<sequence>` while keeping the scalar `carved_id=` keyword working. This step calls it with the full carved range. Do not restate step 2's seed/narrow mechanism — pass the id set and trust it.
- **`ScopeOutResult.carved_ids` holds the full region** and `ScopeOutResult.carved_id` holds the first id. `render_scope_out_result` (in `plan_tool/cli/scope_out_cmd.py`, imported by `convergence_cmd.py`) already renders a range label for a multi-id carve — this step passes the result through unchanged.
- **The `--through M` CLI surface exists.** `plan-tool scope-out <slug> --step N --through M` is the runnable range form this step's recommendation command renders and that `--apply-scope-out` mirrors internally.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/convergence_diagnosis.py` — add a `step_ids` field to `ForkRecommendation`; add a new contiguous-range branch to `classify_fork`; add a range-form command renderer (a sibling to `_scope_out_command`); extend the `FORK_SCOPE_OUT` prose in `_spinning_body` to describe a range.
  - `plan_tool/cli/convergence_cmd.py` — in `_actuate_scope_out`, read the carved range off the recommendation and call `scope_out_step` with the id set; make the stale-diagnosis and hint messages describe the range.
  - `tests/test_convergence_diagnosis.py` — unit tests for the range classifier, the range command, and the range render.
  - `tests/cli/test_convergence_cmd.py` — CLI-integration tests driving `main([...])` for the range carve and its recommend-only / stale / no-backend paths.

## Implementation

**Core behavior change: `classify_fork` gains a contiguous-range scope-out arm between the single-step scope-out and the structural fallback.** Everything else about the fork stays as-is. The single-step arm (`len(resolved) == 1`) now also sets `step_ids=(step,)` on the `FORK_SCOPE_OUT` it returns — behavior-preserving for the command string and `step_focus`, additive for `step_ids` (which the rewired actuator reads) — so its existing command/`step_focus` assertions pass unchanged while the new `step_ids == (N,)` assertion holds. The structural fallback is unchanged.

### Carry the carved range on the recommendation (`plan_tool/convergence_diagnosis.py`)

- **Add `step_ids: tuple[int, ...] = ()` to `ForkRecommendation`.** It holds every step the scope-out remedy carves: `(N,)` for a single-step scope-out, `(N, …, M)` for the range. Leave it `()` (the default) on `FORK_LOCALIZED`, `FORK_STRUCTURAL`, and `FORK_NONE`. Default it so no other construction site needs a change.
- **Keep `step_focus` meaningful.** For the range arm, set `step_focus` to the first id `N` (the start of the range) so the single-value readers of `step_focus` degrade to naming the region's start rather than `None`. `step_ids` is the authoritative set; `step_focus` stays "the primary over-packed step." Update the field's docstring to say `step_ids` carries the full carved set on `FORK_SCOPE_OUT`.

### The new range branch in `classify_fork`

- **Insert the range case after the existing `len(resolved) == 1` single-step arm and before the structural fallback.** The gathered spinning `regions`, `foci`, and `resolved` set are already computed at the top of `classify_fork`; reuse them.
- **Trigger the range arm only when all of these hold** (all read from data already on the regions — no new inputs):
  - `None not in foci` — every recurring region resolves to a concrete step (an anchor-only/unresolvable region still forces structural).
  - `len(resolved) >= 2` — genuinely multiple distinct steps (one step is the existing single-step arm).
  - **the distinct steps are contiguous** — `sorted(resolved) == list(range(min, max + 1))`; a gap (e.g. steps 2 and 4) falls structural. Contiguity is what makes `--step N --through M` name exactly this set.
  - **every step in the range has a severe, not-improving region** — the multi-step analog of the single-step arm's `any(_region_triggers_scope_out(r) for r in regions)`. One clean way: build the set of step foci whose region trips `_region_triggers_scope_out`, then require every id in `range(min, max+1)` to be in that set. A contiguous range where one step's regions are all medium/improving falls structural, because carving the whole band would carve a step that isn't over-packed.
- **On a trip, return `FORK_SCOPE_OUT`** with `step_focus=min(resolved)`, `step_ids=tuple(sorted(resolved))`, `command=` the range command (below), `regions=regions`, `ambiguous=False`.
- **Otherwise fall through to the existing structural return unchanged.** A fully-resolved but non-contiguous or mixed-severity set keeps `ambiguous=False` exactly as today (the `ambiguous = bool(resolved) and (None in foci)` line is untouched).

**Why not reuse the single-step arm's "any region trips" rule verbatim for the range?** Because a single over-packed step is one carve target; a *range* carves several steps at once, so the bar must be "every step in the band is severe," not "any region anywhere is severe." Requiring per-step severity keeps the range carve from removing a healthy step that merely sits between two sick ones.

### The range command renderer

- **Add a sibling to `_scope_out_command`** — e.g. `_scope_out_range_command(plan_slug, first, last)` returning `f"plan-tool scope-out {plan_slug} --step {first} --through {last}"`. Keep `_scope_out_command(plan_slug, step)` unchanged (its three existing tests stay green); `classify_fork` picks the range renderer when `len(sorted(resolved)) > 1`, the single renderer otherwise. This mirrors step 1/2's "add a sibling renderer, branch at the caller" shape rather than overloading one renderer.
- **The range command is fully runnable** — no `<...>` placeholder, same as `_scope_out_command`. It carries no `--apply`/`-y` (recommend-only preview), matching the single-step scope-out recommendation.

### Extend the spinning render (`_spinning_body`)

- **The `FORK_SCOPE_OUT` branch of `_spinning_body` reads `rec.step_focus` for its prose today.** Extend it to describe the range when `len(rec.step_ids) > 1`: say "Steps N..M stay severe … carve them out of the plan" and label it a range carve; keep the single-step wording (`Step N …`) when `len(rec.step_ids) <= 1`. The runnable-preview lines (`rec.command`) already work for both — no change there beyond the branch on region size.

### Actuate the range carve (`plan_tool/cli/convergence_cmd.py`)

- **`_actuate_scope_out` reads the carved set, not just the scalar.** Change the carve call from `scope_out_step(path, carved_id=rec.step_focus, ...)` to pass the full set: `scope_out_step(path, carved_ids=list(rec.step_ids), ...)`. Step 2 makes `carved_ids=[N]` identical to `carved_id=N`, so the single-step path is unaffected. Guard the arm on `rec.fork != FORK_SCOPE_OUT or not rec.step_ids` (empty set → nothing to actuate).
- **The stale-diagnosis guard is unchanged in logic.** `classify_report_staleness` compares the whole-plan fingerprint and is range-agnostic; keep the `STALENESS_MISMATCH` / `STALENESS_UNVERIFIABLE` gate exactly as it is. Only the **wording** in those messages (and the `-y` hint) should describe the range — e.g. "steps 2..4 may no longer be the over-packed region" — reading `rec.step_ids` for the range text. This is message text, not new gate logic.
- **The orphan-seed glob is unchanged.** `seed_glob = f"{diagnosis.plan_slug}-carved-*.md"` still matches step 2's region seed name (`<slug>-carved-<first-slug>-through-<M>.md`), so the `NarrowError` orphan-naming path needs no change.
- **`render_scope_out_result` is passed through unchanged.** Step 2 owns its range label; this step only supplies the result and the `recommend_hint`. Make the `recommend_hint`'s re-run line carry the range flags so an operator can re-run the exact carve.

### Constraints that are not free to vary

- **Single-step scope-out stays identical** — a spinning history resolving to one step still emits `--step N` (no `--through`), same command string, same `step_focus`, same actuation. The existing `classify_fork` scope-out and localized tests must pass unmodified.
- **Non-contiguous distinct steps still fall structural** — the existing `test_classify_scope_out_not_for_distinct_steps` (steps 3 and 5) and `test_classify_structural_distinct_steps` stay green because those sets are not contiguous.
- **The range arm never fires on an unresolvable region** — if any recurring region has no step focus (`None in foci`), the fork is structural, exactly as today.
- **`_actuate_scope_out` mutation/exit contract holds** — every completed `ScopeOutResult` outcome exits 0; only a post-seed `NarrowError` (orphan seed on disk) exits non-zero. The range carve inherits this from `scope_out_step` unchanged.

### Shared logic and where it lives

The foundational rule this step adds is **"a contiguous ascending range of distinct over-packed steps, all severe and not improving, is one range carve."** Grepping for readers of `ForkRecommendation.step_focus` turns up one other consumer outside this step's files: `plan_tool/split_criteria.py:_altitude3_result` builds its `step_ids` as `() if fork.step_focus is None else (fork.step_focus,)`. Because this step keeps `step_focus` populated (with `N`) on the range fork, that advisory `plan-tool split-criteria` surface will report just the first step of a range carve rather than the full band. Teaching it to prefer the new `fork.step_ids` is a one-line display fix in a file outside this step's declared `files:` — routed to [Deferred](#deferred), not folded in here.

## Tests

### Unit tests — `tests/test_convergence_diagnosis.py`

Reuse the module's `_fork_region`, `_series`, and `_diag` helpers. `_fork_region(step_id=N, first=, last=, peak=)` builds a region on step `N` at a chosen severity trend.

- `test_scope_out_range_command_renders_through` — the range renderer returns `plan-tool scope-out spinner --step 2 --through 4` with no placeholder.
- `test_classify_scope_out_range_contiguous_all_severe` — regions on steps 2, 3, 4 all high-and-flat → `FORK_SCOPE_OUT`, `step_ids == (2, 3, 4)`, `step_focus == 2`, command contains `--step 2 --through 4`, `ambiguous is False`.
- `test_classify_scope_out_range_two_steps` — high-flat regions on steps 2 and 3 → range carve `--step 2 --through 3`.
- `test_classify_scope_out_range_step_focus_is_first` — the range fork sets `step_focus` to the first id of the range.
- `test_classify_structural_range_has_gap` — high-flat regions on steps 2 and 4 (gap at 3) → `FORK_STRUCTURAL`, not scope-out.
- `test_classify_structural_range_mixed_severity` — step 2 high-flat but step 3 medium (contiguous) → `FORK_STRUCTURAL`, because not every step in the band is severe.
- `test_classify_structural_range_unresolvable_region` — two high-flat steps plus one anchor-only unresolvable region → structural (any `None` focus forces structural).
- `test_classify_scope_out_range_multiple_regions_per_step` — steps 2 and 3 each carry one severe region, step 2 also carries a medium one → still a range carve (every step has a severe region).
- `test_classify_single_step_scope_out_unchanged` — regression: one high-flat region on step 5 still emits `--step 5` with no `--through` and `step_ids == (5,)`.
- `test_render_spinning_range_scope_out_shows_range` — `render_diagnosis` on a range scope-out prints the range command and "steps 2..4"-style prose, with no `--into`/`<seed.md>` placeholder.

### CLI-integration tests — `tests/cli/test_convergence_cmd.py`

Drive `main([...])` through the real parse → dispatch → command path, seeding real sidecars with `save_review` and matching fingerprints with `compute_plan_fingerprint`. Mark the class `@pytest.mark.integration`. `_write_multistep_plan` writes a 2-step plan today; the range tests need a plan with a carvable contiguous band (e.g. steps 1–4 where carving 2–3 leaves committed survivor step 1) — add a small multi-step plan writer beside it, and seed a spinning history with one severe (`_severe_rec`) finding per carved step (anchors `step2-…`, `step3-…`) across three runs so the regions resolve to distinct contiguous steps.

- `test_apply_scope_out_carves_contiguous_range` — a spinning history on contiguous severe steps 2–3, `--apply-scope-out -y` writes exactly one region forward-seed and narrows the plan to the survivors; rc 0.
- `test_apply_scope_out_range_recommend_only_without_yes` — non-TTY without `-y` → recommends only, mutates nothing.
- `test_apply_scope_out_range_stale_fingerprint_recommends_only` — a fingerprint mismatch skips the carve, exits 0, and the message names the range.
- `test_apply_scope_out_range_prints_through_command` — the default (no-flag) diagnosis on the same history prints the runnable `--step N --through M` recommendation.
- `test_apply_scope_out_range_spends_no_backend` — no `@allow_real_claude` marker; a green run proves the range carve shells out to no backend (the conftest gate).

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the tests above **with** the implementation:

- Add `ForkRecommendation.step_ids` + the range command renderer, then the command and field unit tests.
- Add the `classify_fork` range branch, then the contiguous/gap/mixed-severity/unresolvable classifier tests.
- Extend `_spinning_body`, then the range render test.
- Wire `_actuate_scope_out` to the id set, then the CLI-integration carve/recommend/stale/no-backend tests.

**Green-before-done gate:** every new test above must be green, and the existing single-step and structural `classify_fork` tests plus the existing `--apply-scope-out` CLI tests must pass **unmodified**, before this step is finished. Run `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q`.

## Acceptance criteria

- `classify_fork` returns `FORK_SCOPE_OUT` with `step_ids == (2, 3, 4)` and a `--step 2 --through 4` command when three spinning regions resolve to contiguous steps 2, 3, 4 that are each severe and not improving.
- A contiguous range with a gap (steps 2 and 4) or a mixed-severity step returns `FORK_STRUCTURAL`, not scope-out.
- A single-step spinning history still returns the unchanged `--step N` scope-out command with `step_ids == (N,)`.
- `render_diagnosis` prints the runnable `--step N --through M` command and range prose for a multi-region scope-out.
- `plan-tool convergence <name> --apply-scope-out -y` on a contiguous severe range carves the whole region (one forward-seed, plan narrowed to survivors) and exits 0; without `-y` on a non-TTY it recommends only and mutates nothing.
- A stale fingerprint downgrades the range carve to recommend-only with a message naming the range, exiting 0.
- `uv run pytest tests/test_convergence_diagnosis.py tests/cli/test_convergence_cmd.py -q` passes; existing single-step and structural tests pass unmodified.

## References

- `plan_tool/scope_out.py` — step 2's set-aware `scope_out_step(carved_ids=…)` / `ScopeOutResult.carved_ids` contract this step calls with the full carved range; the seed/narrow/rollback mechanism is owned there, not restated here.
- `plan_tool/convergence_diagnosis.py:_scope_out_command` — the in-file single-step renderer the new `_scope_out_range_command` sibling mirrors, branching at the caller on region size rather than overloading one renderer.
- [How to mark test functions with attributes (pytest)](https://docs.pytest.org/en/stable/how-to/mark.html) — `@pytest.mark.integration` gates the new `main([...])` CLI tests apart from the unit-first suite.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path`/registered-plan fixtures keep the range-carve integration tests hermetic.

## Deferred

- **`plan_tool/split_criteria.py:_altitude3_result` full-range display** — it reads `fork.step_focus` only, so a range carve shows just the first step on the `plan-tool split-criteria` surface; teaching it to prefer `fork.step_ids` is a one-line display fix outside this step's declared files, left for reconcile.
- **Disjoint (non-contiguous) region carve** — `compute_narrow`/`scope_out_step` accept any id set (steps 1–2), but `convergence` actuates only the contiguous range; a disjoint auto-carve is deferred until a caller needs it (matches the plan's Deferred section).
- **Auto-filling the localized `--apply-split` `--into` titles** — the diagnosis still can't invent split titles, so `--apply-split` remains operator-titled; unchanged here.
- **Range detection tuning (per-step vs any-region severity)** — the "every step in the band is severe" bar is deliberately conservative; loosening it to "any severe step anchors the band" is a heuristic change deferred to telemetry-driven tuning (#57/#72).
