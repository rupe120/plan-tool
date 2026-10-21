> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Add a `create --from-existing` re-baseline disposition to `reground_bridge`

## Summary

Give `plan_tool/reground.py:reground_bridge` a second disposition: besides marking the flagged already-built steps `done`, it can emit a `create --from-existing` re-baseline seed for them so an operator re-decomposes the plan from current code. The change is additive — a new disposition selector (default `mark-done`) plus a small pure seed renderer and a `repo_root` param on the bridge, all inside `plan_tool/reground.py`. The key design decision: the seed renderer lives in `reground.py` and **mirrors** `plan_tool/scope_out.py:render_carved_seed`'s `create --from-existing` shape rather than importing it — because `reground.py` is a leaf that must not import `plan_tool.detail` (pinned by `test_imports_neither_launcher_nor_detail_at_module_level`), and `scope_out.py` pulls in `detail`. On green, `reground_bridge(..., disposition="re-baseline", repo_root=..., allow_reground=True, yes=True)` writes a re-baseline seed under `plan-seeds/` first, then marks the flagged steps done and returns `outcome="applied"` with `seed_path` populated; the default `mark-done` path is unchanged.

## Table of Contents

- [Why](#why) — what the re-ground actuator can't do today and why the seed disposition closes it
- [Files (creates vs edits)](#files-creates-vs-edits) — the one source file and its test file
- [Implementation](#implementation) — the disposition selector, the leaf seed renderer, and the invariants that must hold
- [Tests](#tests) — unit coverage for the seed disposition and the unchanged mark-done path
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the tests to add with the code and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — pytest docs for this step
- [Deferred](#deferred) — detail-body embedding, seed-only variant, walk wiring, and other out-of-scope items

## Why

`reground_bridge` today has exactly one disposition: mark a set of already-built steps `done` (re-baseline the current plan against HEAD). The human-authored `create --from-existing` re-baseline — hand off the already-built steps as done-context so a fresh `create` re-decomposes the plan from where the code actually is — is unbuilt. `scope_out.py` already has the seed-first analog on the carve side (`render_carved_seed` + `scope_out_step` write a forward-seed before narrowing), but the re-ground side has no seed at all. This step adds that missing disposition so the re-ground remedy can produce a re-decompose seed, not just flip statuses. It is Arm 3 of BACKLOG #70's remaining convenience arms.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/reground.py`
    - Add a disposition selector to `reground_bridge` (recommend a `disposition: str = "mark-done"` kwarg with two module constants) and a `repo_root: Path | None = None` kwarg used only by the re-baseline disposition.
    - Add a pure seed renderer (recommend `render_rebaseline_seed`) that builds a `create --from-existing` re-baseline seed for the flagged steps — no file IO, no `invoker=`, no `detail`/`launcher` import.
    - Add a collision-safe seed-path helper (recommend `_rebaseline_seed_path`) under `plan-seeds/`, mirroring `plan_tool/scope_out.py:_carved_seed_path`.
    - Add `seed_path: Optional[Path] = None` to `RegroundResult`; adapt `_confirm_reground` to mention the seed when the disposition is re-baseline.
  - `tests/test_reground.py` — add the re-baseline disposition tests; the existing mark-done tests stay green unchanged.

## Implementation

**Foundational change: a disposition selector on `reground_bridge` that keeps `mark-done` the default and adds a seed-first `re-baseline` arm.** The gate order (parse → normalize → existence → parked/unsafe → no-op → opt-in → confirm → apply) is unchanged; only the apply branch (gate 8) forks on disposition.

- **Model the disposition as an explicit selector, `mark-done` default.** Recommend a `disposition: str = "mark-done"` kwarg plus two module constants (e.g. `DISPOSITION_MARK_DONE = "mark-done"`, `DISPOSITION_REBASELINE = "re-baseline"`) so the value is self-describing and leaves room for a later seed-only variant. A bare boolean would also work today, but the plan calls for a disposition selector and the constant set reads clearer at the call site step 6 wires. Reject an unknown disposition value with a `ValueError` (a programming error, not a runtime outcome).
- **`re-baseline` is "in addition to" mark-done, not "instead of".** Under the re-baseline disposition the bridge writes the seed **first**, then marks the flagged steps done and writes the plan — so `RegroundResult` carries both `marked_ids` and `seed_path`, and `outcome` stays `"applied"`. This keeps the five existing outcome strings intact and the mark-done work single-sourced through `mark_steps_done`. (The seed-only variant — emit the seed but leave the steps untouched — is out of scope; see Deferred.)
- **Seed-first, mirroring `scope_out_step`.** Write the seed to disk before the `mark_steps_done` + `write_plan` mutation. The seed is the durable re-plannable artifact and must survive even if the plan write fails afterward. There is no multi-file transaction here (the plan write is a single `write_plan`), so no rollback journal is needed — the ordering alone gives "seed survives a failed plan write." Note the residual: a `write_plan` failure after the seed is written leaves the seed as a harmless orphan under `plan-seeds/` (the same durable-orphan property `scope_out_step` documents).
- **The seed renderer lives in `reground.py` and mirrors — does not import — `scope_out.py`.** `reground.py` must import only `locator` / `parser` / `schema` (leaf status, pinned by `test_imports_neither_launcher_nor_detail_at_module_level`, which greps the whole source for any `plan_tool.detail` / `plan_tool.launcher` import). `scope_out.py:render_carved_seed` imports `plan_tool.detail` transitively, so importing it — or reusing `detail`'s detail-file resolvers — would break the leaf boundary. Follow the codebase's established pattern instead: `scope_out.py` itself only **mirrors** `plan_tool/annotate_render.py:render_create_seed`'s design (it does not import it). Add `render_rebaseline_seed` as a pure deterministic string builder over `Plan` / `Step` that carries the same `create --from-existing` vocabulary a downstream `create` already consumes:
  - a provenance header comment (mirror `render_carved_seed`'s `<!-- plan-tool ... -->` block) naming the source plan and the flagged step ids,
  - a `# Plan seed: …` title and the "This is a `plan-tool create --from-existing` input" framing line,
  - a **done-context** section listing the flagged already-built steps (id, title, files) under the explicit "already implemented — do not re-plan" framing (these steps are built; the code is the ground truth for the re-baseline),
  - **required:** also render the plan's remaining non-flagged, not-done committed steps as the **scope to re-plan** so a subset re-baseline never loses unbuilt scope — a seed that omits them would produce a `create --from-existing` re-decompose that silently drops the work still to do. The exact section split is the implementer's call, but the seed must carry both the flagged done-context and every remaining non-flagged committed step as scope-to-re-plan, and be a valid `create --from-existing` file.
- **Render from frontmatter only — no per-step detail bodies.** `render_carved_seed` embeds a carved step's detail body, but resolving detail files needs `plan_tool.detail` helpers this leaf cannot import. Render the flagged steps from their `Step` frontmatter (title, `all_files`, change type, status, scope, features). This is enough for the "these are built, don't re-plan them" done-context, and a re-baseline re-decomposes from current **code**, not stale detail prose. Detail-body enrichment is deferred (see Deferred).
- **`repo_root` becomes required for the re-baseline disposition.** The mark-done path moves no files and needs no `repo_root`; the seed write needs a target directory. Add `repo_root: Path | None = None` and require it (raise `ValueError`) when the disposition is `re-baseline`. The walk (step 6) already holds `ctx.repo_root` and will pass it.
- **Seed path is collision-safe under `plan-seeds/`.** Add `_rebaseline_seed_path(plan_path, repo_root)` mirroring `plan_tool/scope_out.py:_carved_seed_path`: derive `<plan-slug>` from the filename via `plan_tool/locator.py:slug_from_filename`, write under `repo_root / "plan-seeds"`, and **never overwrite** an existing seed — a taken base path gets a `-2`, `-3`, … suffix. Encode the flagged step ids in the filename (e.g. a `-reground-<first>-<last>` stem) so a re-ground seed is distinguishable from a scope-out carved seed; the exact stem is the implementer's call.
- **Adapt the confirm prompt to the disposition.** `_confirm_reground` already surfaces the flagged ids/titles/files and the "confirm these steps really are built before re-baselining" caveat. Under the re-baseline disposition, add one line noting a `create --from-existing` seed will also be written. The non-TTY-without-`yes` decline and TTY `[y/N]` behavior stay as-is.

**Constraints that are not free to vary:**
- `reground.py` imports stay limited to `locator` / `parser` / `schema`, enforced as two distinct requirements: (a) no `detail` / `launcher` import — caught by `test_imports_neither_launcher_nor_detail_at_module_level`, a whole-file substring grep for `plan_tool.detail` / `plan_tool.launcher`; keep it green — and (b) no `scope_out` import, a separate rule the grep does **not** catch (a `from plan_tool.scope_out import …` line contains neither substring) that the implementer must uphold by hand, since `scope_out` transitively re-introduces the `detail` edge.
- No `invoker=` / `claude_invoker=` param on `reground_bridge` or the renderer — the bridge spends zero Claude (`test_default_path_spends_no_claude`).
- The default `mark-done` disposition must behave exactly as today: no seed written, `seed_path is None`, existing mark-done tests unmodified.
- The re-baseline seed write is gated behind the same opt-in + confirm as the mark-done mutation — recommend-only and refusal paths write no seed.
- Gates 3–7 (existence / parked / no-op / opt-in / confirm) return before the apply branch, so `step-missing` / `unsafe` / `noop` / `recommended` never write a seed regardless of disposition.

## Tests

Reference: `tests/test_reground.py`. Reuse the existing `_plan` / `_step` / `_write_plan_file` / `_built_plan_file` helpers.

- `test_default_disposition_is_mark_done` — no `disposition` arg → marks done, `seed_path is None`, no file under `plan-seeds/`.
- `test_rebaseline_writes_seed_first_then_marks_done` — `disposition="re-baseline"`, `allow_reground=True`, `yes=True` → `outcome="applied"`, `seed_path` exists on disk, and the flagged steps are `DONE` in the reparsed plan.
- `test_rebaseline_seed_is_create_from_existing_consumable` — the written seed contains the `create --from-existing` framing line and a provenance header naming the source plan.
- `test_rebaseline_seed_lists_flagged_steps_as_done_context` — the seed body names each flagged step id/title under the done-context framing.
- `test_rebaseline_subset_seed_carries_remaining_scope` — re-baselining a strict subset renders every remaining non-flagged, not-done committed step in the scope-to-re-plan section, so the seed retains the unbuilt scope.
- `test_rebaseline_recommended_when_not_allowed` — `allow_reground=False` → `outcome="recommended"`, no seed written, plan unchanged.
- `test_rebaseline_recommended_when_confirm_declined` — TTY, `prompt_fn` returns `n` → `recommended`, no seed.
- `test_rebaseline_recommended_when_non_tty_without_yes` — non-TTY, `yes=False` → `recommended`, no seed.
- `test_rebaseline_requires_repo_root` — `disposition="re-baseline"` with `repo_root=None` raises `ValueError`.
- `test_rebaseline_seed_never_overwrites` — a second re-baseline apply writes a `-2`-suffixed seed; the first seed is untouched.
- `test_rebaseline_step_missing_writes_no_seed` — an absent id returns `step-missing` before any seed write.
- `test_rebaseline_unsafe_writes_no_seed` — a parked flagged step returns `unsafe`, no seed.
- `test_rebaseline_noop_writes_no_seed` — all flagged ids already done → `noop`, no seed.
- `test_rebaseline_renderer_touches_no_disk` — calling `render_rebaseline_seed(...)` writes nothing (pure builder).
- `test_reground_still_imports_no_detail_or_launcher` — confirm `test_imports_neither_launcher_nor_detail_at_module_level` still holds after the renderer lands. That grep catches only `detail` / `launcher`; a `scope_out` import (which would transitively re-add the `detail` edge but not the literal substring) is a separate constraint, so also assert `plan_tool.scope_out` is not imported at module level.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Add the tests above **with** the implementation:

- Land the `disposition` selector + `RegroundResult.seed_path` + `repo_root` param first, covered by `test_default_disposition_is_mark_done` and `test_rebaseline_requires_repo_root`.
- Add `render_rebaseline_seed` + `_rebaseline_seed_path`, covered by the seed-content, seed-first, collision, and renderer-no-IO tests.
- Add the gate-interaction tests (`recommended` / `step-missing` / `unsafe` / `noop` write no seed).
- **Green-before-done gate:** every new test above is green, and the full existing `tests/test_reground.py` suite (the mark-done actuator and bridge gate-matrix tests) passes unchanged before the step is finished.

## Acceptance criteria

- `reground_bridge(plan_path, step_ids=[1,2], allow_reground=True, yes=True)` with no `disposition` marks steps 1 and 2 done and returns `seed_path is None` — the mark-done path is unchanged.
- `reground_bridge(plan_path, step_ids=[1,2], disposition="re-baseline", repo_root=<root>, allow_reground=True, yes=True)` returns `outcome="applied"` with `seed_path` pointing at an existing file under `plan-seeds/`, and marks steps 1 and 2 done on disk.
- The written seed contains the `create --from-existing` framing and names the flagged steps as done-context.
- When a strict subset of steps is re-baselined, the seed also carries every remaining non-flagged, not-done committed step as scope-to-re-plan, so no unbuilt scope is dropped from the re-decompose input.
- A re-baseline call with `allow_reground=False`, a declined confirm, or a non-TTY run without `yes` returns `recommended` and writes no seed.
- `disposition="re-baseline"` with `repo_root=None` raises `ValueError`.
- A second re-baseline apply never overwrites the first seed (`-2` suffix).
- `plan_tool/reground.py` still imports no `plan_tool.detail` / `plan_tool.launcher` (test stays green), and `reground_bridge` has no `invoker=` param.
- The full `tests/test_reground.py` suite passes.

## References

- `plan_tool/scope_out.py:render_carved_seed` / `_carved_seed_path` — the sibling seed-first renderer and collision-safe `plan-seeds/` path helper this step's `render_rebaseline_seed` / `_rebaseline_seed_path` mirror (not import).
- `plan_tool/annotate_render.py:render_create_seed` — the `create --from-existing` seed shape `scope_out.py` already mirrors and the new renderer follows so a downstream `create` can consume it.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the new seed-write and collision tests use to stay hermetic.

## Deferred

- **Embedding per-step detail bodies in the re-baseline seed** — `render_carved_seed` embeds a carved step's detail body, but resolving detail files needs `plan_tool.detail` helpers this leaf cannot import; enriching the seed with detail bodies would require the caller to inject them and is deferred until a caller needs it.
- **Consolidating the three seed renderers into one shared leaf** — `render_carved_seed` (scope_out), `render_create_seed` (annotate_render), and the new `render_rebaseline_seed` share a `create --from-existing` shape; the codebase currently mirrors rather than shares them (scope_out mirrors annotate_render without importing it). Extracting a common renderer is a reconcile-owned refactor, not this step.
- **The seed-only variant** — a re-baseline that emits the seed but does *not* mark the flagged steps done; this step ships the "in addition to mark-done" reading only.
- **Wiring the disposition through the walk with an opt-in flag** — step 6 (`plan_tool/cli/review_actions.py`, `plan_tool/cli/review_cmd.py`) owns exposing the disposition and passing `repo_root` from `ctx.repo_root`.
- **Auto-selecting the re-baseline disposition** — per the plan's Deferred, letting convergence/reconcile signals pick re-baseline automatically needs its own heuristic and is out of scope.
