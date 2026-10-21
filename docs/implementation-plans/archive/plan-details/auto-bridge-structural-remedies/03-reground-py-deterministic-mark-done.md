> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add `reground.py` with a deterministic mark-done actuator and a gated re-ground bridge

## Summary

Adds a new leaf module `plan_tool/reground.py` with two pieces: a deterministic **mark-done actuator** that flips a set of already-built steps to `status: done` (and re-establishes the run cursor), and a gated **re-ground bridge** that wraps that actuator behind the tool's standard apply-or-recommend gate. The bridge takes the step ids a `granularity-merge` re-ground finding named, re-parses the plan from disk, runs a deterministic safety check, then either **recommends** (mutates nothing, spends no Claude) or **applies** the mark-done — only when an explicit opt-in plus a TTY confirm (or `-y` bypass) both hold. It returns a frozen `RegroundResult` whose `outcome` lets the caller tell recommended from applied, mirroring `scope_out.py:ScopeOutResult` and `launcher.py:EscalateResult`. This bridge is deliberately **not** merge: it never routes to `plan-tool merge` (that would conflate re-ground with structural merge). It mints no `review.Recommendation` and adds no new source token. On green, the re-ground remedy can be actuated straight from the finding; step 5 wires it into the walk, so step 3 ships only the primitive and its tests.

## Table of Contents

- [Summary](#summary) — what the module adds and the result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the diagnosis-vs-actuation gap for re-ground.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files.
- [Implementation](#implementation) — the actuator, the gate order, the outcome vocabulary, and the gotchas.
- [Tests](#tests) — the actuator cases and the gate matrix.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — frozen dataclasses, TTY checks, monkeypatch.
- [Deferred](#deferred) — out-of-scope follow-ups.

## Why

`plan_tool/review.py:_reground_already_built_recommendation` fires a plan-wide `granularity-merge` finding when the code already implements **2 or more distinct plan steps** (per the `heuristic_already_done` scan). Its remedy is **re-ground / re-baseline** — mark the already-built steps `done`, or re-decompose — **not** a blind merge. But that finding is recommend-only, so re-grounding today forces the operator to hand-edit the plan's `status:` fields. The finding and the mutation are disconnected. This step closes that gap with a deterministic mark-done actuator plus an apply-or-recommend bridge — the re-ground sibling of `launcher.py:escalate_to_split`, `scope_out.py:scope_out_step`, and step 2's `detail.py:merge_bridge` — so step 5's walk can actuate the re-ground behind the standard gate. It adds only wiring between an existing finding producer and a new (deterministic, in-module) actuator: no new detection, no new source token.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/reground.py` — the mark-done actuator, the frozen `RegroundResult`, a `_confirm_reground` TTY helper, and the `reground_bridge` orchestrator.
  - `tests/test_reground.py` — the actuator cases and the gate-matrix cases below.
- **Existing files (edits only):** none.

## Implementation

- **What changes.** Add a small leaf module with the deterministic mark-done actuator and the gate that wraps it. The actuator owns no structural-remedy algorithm beyond "set status to `done` + re-establish the cursor"; the bridge owns the apply-or-recommend policy. This is the fourth instance of the apply-or-recommend gate shape — model it on `plan_tool/scope_out.py:scope_out_step` (the closest sibling: like re-ground, it spends **zero Claude** and takes no `invoker=` seam).

- **The mark-done actuator — deterministic, in-memory, no IO.** Add a function (one way: `mark_steps_done(plan, step_ids)`) that mutates a parsed `Plan` in place and returns a small summary (marked ids, the new current id if one was promoted, whether the plan completed). It has no filesystem, git, or Claude touch — the bridge does the parse and the write around it.
  - **Mark each named committed, not-yet-done step `done`.** Set `step.status = StepStatus.DONE` (`plan_tool/schema.py:StepStatus`). Skip ids already `DONE` (a no-op).
  - **Re-establish the run cursor once, after marking the whole set** — do not thread the cursor logic through a per-step loop. Mirror `plan_tool/launcher.py:mark_done_and_advance` and `plan_tool/scope_out.py:compute_narrow`'s "re-establish the run cursor" / "Top-level status" blocks: if `plan.current_step()` is now `None`, promote `plan.next_runnable_step()` to `CURRENT`; if none is promotable and `plan.all_steps_done` holds, flip `plan.status = PlanStatus.COMPLETED`. Reuse the `Plan` methods (`current_step`, `next_runnable_step`, `all_steps_done`) so the "next runnable" rule stays single-sourced on the model — do **not** re-type it.
  - **Key contrast with merge and scope-out: mark-done keeps every step id.** No renumber, so no `depends_on` repair, no detail-file migration, no downstream-orphan hazard. That is why the actuator is far simpler than `compute_narrow` / `merge_steps` and needs no `repo_root`.

- **The bridge (`reground_bridge`) — gate order, read-only checks first.** The default (recommend) and every refusal path must spend zero Claude and mutate nothing. One recommended signature: `reground_bridge(plan_path, *, step_ids, allow_reground, yes=False, prompt_fn=None) -> RegroundResult`. Note the deliberate absence of an `invoker=` seam (no Claude) and of `repo_root` (no detail files move). Recommended order:
  1. **Re-parse the plan from disk** (`parse_plan(plan_path)`) — never trust an in-memory `Plan` the caller passed. All three siblings re-parse.
  2. **Normalize** `step_ids` to a sorted, distinct set.
  3. **Existence gate** (deterministic refusal): any id not in the plan → `outcome="step-missing"`, no prompt, no mutation. Use `plan.step_by_id` / membership over `[s.id for s in plan.steps]`.
  4. **Safety gate** (deterministic refusal): any named id whose `scope` is not `StepScope.COMMITTED` (a parked `deferred`/`wont_do` step) → `outcome="unsafe"` carrying the blocking ids. This is required — `schema.py:Step._scope_status_coherent` **raises** if a parked step is set `current`/`done`, so marking one done would blow up `write_plan`'s re-validation. Refuse it up front instead.
  5. **No-op gate**: after dropping ids already `DONE`, if nothing is left to mark (empty input, or every named step already done) → `outcome="noop"`, no mutation. Re-ground is already satisfied.
  6. **Opt-in gate**: `if not allow_reground:` → `outcome="recommended"` with the would-be set, no prompt, no mutation. `allow_reground` is the `allow_split` / `allow_scope_out` analog.
  7. **Confirm gate** (`_confirm_reground`): a non-TTY caller without `yes` prints a `-y` hint and declines to `recommended`; on a TTY prompt `[y/N]` and return `recommended` unless the answer is `y`/`yes`; `yes` bypasses the prompt. Model it on `scope_out.py:_confirm_scope_out` and `detail.py:_confirm_merge` (default NO, non-TTY auto-declines). Use `locator.slug_from_filename(plan_path)` for the plan name in the message (`schema.Plan` has no `slug` field). **The prompt must surface what's being dropped, not just the plan name:** render the **flagged step ids and their titles/files** and the caveat *"confirm these steps really are built before re-baselining"* — because `mark_steps_done` flips them `PENDING → DONE`, removing them from `run`'s work queue, and it fires off `_reground_already_built_recommendation`'s own *low-confidence heuristic that can false-positive on superficial symbol overlap*. This confirm is the **one gate** guarding a false positive from silently skipping real implementation, so the operator must be able to verify builtness here; take the flagged step ids/titles as a `_confirm_reground` argument (don't reduce them to a count). `-y` bypass and non-TTY auto-decline are unchanged — the surfacing only affects the interactive prompt text.
  8. **Apply branch**: call the actuator, then `write_plan(plan_path, plan)` (its default `expect_unchanged=True` compare-and-swap is safe here — the same in-process parse recorded the provenance). Return `outcome="applied"` with the marked ids, the new current id, and whether the plan completed.

- **`RegroundResult` — frozen, five outcomes, no `Recommendation`.** Add a `@dataclass(frozen=True)` mirroring `ScopeOutResult`. `outcome` is exactly one of: `"applied"` (steps marked done, plan written), `"recommended"` (safe but not actuated), `"unsafe"` (a parked named step), `"step-missing"` (an id not in the plan), `"noop"` (nothing to mark). Carry the requested ids, the marked ids, the new current id, a `completed` flag, and the blocking ids (on `unsafe`/`step-missing`). Like `merge_bridge` and `scope_out_step`, mint **no** `review.Recommendation`: the caller (step 5's walk) already holds the re-ground finding that fired this. That honors "no new source token" cleanly by carrying none.

- **This bridge must never route to `plan-tool merge`.** Do not import or call `detail.py:merge_steps` / `merge_bridge`. The re-ground remedy is mark-done / re-baseline; routing to merge would defeat the neutral-`triage_reason` guard that keeps `_reground_already_built_recommendation` off the split path even though it reuses the `granularity-merge` literal (`review.py:_GRANULARITY_MERGE_SOURCE`). Re-decompose (the `create --from-existing` re-baseline arm of the finding's remedy) stays human-authored and is out of scope — this bridge actuates only the mark-done arm.

- **Leaf posture.** `reground.py` should import only light modules: `plan_tool.parser` (`parse_plan`, `write_plan`), `plan_tool.schema` (`Plan`, `StepStatus`, `StepScope`, `PlanStatus`), `plan_tool.locator` (`slug_from_filename`), and stdlib (`sys`, `dataclasses`, `pathlib`, `typing`). Do **not** import `plan_tool.launcher` for `mark_done_and_advance` — that would drag a heavy orchestrator into the leaf; re-derive the small cursor wrapper over the `Plan` methods instead.

- **Shared cursor logic — surface it, don't consolidate here.** The "mark step(s) done → promote next runnable → flip `COMPLETED`" rule now lives in three places: `launcher.py:mark_done_and_advance`, `scope_out.py:compute_narrow` (its cursor/status blocks), and this new actuator. All three already lean on `Plan.next_runnable_step` / `all_steps_done`, so the underlying rule is single-sourced; only the thin "set status + flip" wrapper repeats. Folding the wrapper into one shared helper is a refactor `detail` can't mint — see Deferred.

## Tests

All in `tests/test_reground.py`. Build small `Plan` objects in-memory (or via a tiny `tmp_path` plan file) the way `tests/test_scope_out.py` and `tests/test_detail.py:TestMergeBridge` build their fixtures. This is a **feature** step — add every test below **with** the implementation; each must be green before the step is done.

Actuator (`mark_steps_done`, deterministic, no IO):
- `test_marks_named_steps_done` — given ids, each named step's status becomes `DONE`.
- `test_skips_ids_already_done` — an id already `DONE` stays `DONE`; no error.
- `test_promotes_next_when_current_marked_done` — marking the current step done promotes the next runnable pending step to `CURRENT`.
- `test_no_promote_when_another_current_remains` — marking a non-current step done leaves an existing `CURRENT` untouched (never two currents).
- `test_flips_completed_when_all_committed_done` — marking the last committed step done sets `plan.status == COMPLETED` and promotes nothing.
- `test_actuator_touches_no_disk` — the actuator mutates only the in-memory `Plan` (no file written).

Bridge gate matrix (`reground_bridge`):
- `test_recommended_when_not_allowed` — `allow_reground=False` → `outcome=="recommended"`, plan bytes on disk unchanged.
- `test_recommended_when_non_tty_without_yes` — non-TTY, no `yes` → `recommended`, no mutation.
- `test_recommended_when_confirm_declined` — `prompt_fn` returns `"n"` → `recommended`, no mutation.
- `test_applies_on_yes_bypass` — `allow_reground=True`, `yes=True` → `outcome=="applied"`, named steps read `done` on disk.
- `test_applies_on_tty_confirm_yes` — `prompt_fn` returns `"y"` on a stubbed TTY → `applied`.
- `test_step_missing_when_id_absent` — an id not in the plan → `outcome=="step-missing"`, no prompt, no mutation.
- `test_unsafe_when_named_step_parked` — a `deferred`/`wont_do` named id → `outcome=="unsafe"` with the parked id in `blocking`, no mutation.
- `test_noop_when_all_already_done` — every named id already `DONE` → `outcome=="noop"`, no mutation.
- `test_noop_when_empty_ids` — empty `step_ids` → `outcome=="noop"`.
- `test_applied_flips_completed_on_disk` — an apply that finishes the plan writes `status: completed` to disk.
- `test_bridge_mints_no_recommendation` — `RegroundResult` exposes no `Recommendation` field / value.
- `test_bridge_never_routes_to_merge` — the apply path calls no merge primitive (e.g. patch `detail.merge_steps` to raise and assert it is never hit, or assert the module imports no merge symbol).
- `test_default_path_spends_no_claude` — no backend is spawned on any path (the autouse conftest gate already enforces this; assert the bridge takes no `invoker=` seam).

## Acceptance criteria

- `plan_tool/reground.py` and `tests/test_reground.py` exist; every test in `tests/test_reground.py` passes.
- `mark_steps_done` sets each named committed, not-yet-done step to `StepStatus.DONE`, promotes the next runnable step to `CURRENT` only when no `CURRENT` remains, and flips `plan.status` to `PlanStatus.COMPLETED` when every committed step is done — all in memory, no disk write.
- `reground_bridge` returns a frozen `RegroundResult` whose `outcome` is exactly one of `applied` / `recommended` / `unsafe` / `step-missing` / `noop`; only `applied` mutates the plan.
- Every unattended / non-TTY / declined-confirm / opt-in-off invocation returns `recommended` and writes nothing; a parked named step returns `unsafe`; a missing id returns `step-missing`.
- `_confirm_reground`'s interactive prompt surfaces the flagged step ids and their titles/files plus the "confirm these steps really are built before re-baselining" caveat (not just the plan name), so the operator can verify builtness at the one gate that guards the `PENDING → DONE` drop; a test asserts the flagged ids/titles appear in the rendered prompt text.
- The bridge takes no `invoker=` seam and spawns no backend on any path.
- `reground_bridge` mints no `review.Recommendation` and calls no merge primitive (`merge_steps` / `merge_bridge`).
- `reground.py` imports neither `plan_tool.launcher` nor `plan_tool.detail`.

## References

- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — the frozen immutable pattern for `RegroundResult`, matching `ScopeOutResult` / `EscalateResult`.
- [io — isatty() on stream objects](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — the TTY check behind `_confirm_reground`'s non-TTY-declines-vs-interactive-confirm decision.
- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for stubbing `sys.stdin.isatty` and injecting `prompt_fn` so gate-matrix tests stay deterministic.

## Deferred

- **Re-decompose (`create --from-existing`) arm of the re-ground remedy** — the finding's remedy also allows re-baselining by re-planning; that stays human-authored (the re-seed structural limit is out of scope per the plan's Out of scope).
- **CLI / walk wiring** — dispatching the re-ground finding to `reground_bridge` from the interactive walk (`review_walk.py`, `cli/review_actions.py`) is step 5. No subcommand, parser, `app.py`, or capability-catalog wiring is added here.
- **Making the finding's `suggested_action` parseable** — extracting the step ids the bridge consumes from the re-ground finding is step 4.
- **Consolidating the shared "mark done + re-establish cursor" wrapper** — `launcher.py:mark_done_and_advance`, `scope_out.py:compute_narrow`, and this actuator repeat the thin set-status-and-flip wrapper (the underlying rule already lives on the `Plan` model). A refactor step to fold it into one helper is a reconcile item, not this step's footprint.
