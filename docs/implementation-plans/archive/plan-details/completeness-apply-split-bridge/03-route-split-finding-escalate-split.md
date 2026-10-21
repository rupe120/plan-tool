> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Route the medium mixed-step split finding to the escalate-to-split bridge in the apply walk

## Summary

Wire the saved-review apply walk so a `medium` `granularity-split` MIXED-STEP finding (a step that fuses a refactor with new behavior) dispatches to the already-shipped `escalate_to_split` bridge instead of falling through to the "run it manually" no-op. Two files change: `plan_tool/review_walk.py` gains a dedicated dispatchability path for the finding, scoped to the caller opt-in (mirroring how `plan-correctness` is scoped), and `plan_tool/cli/review_actions.py`'s `action(rec)` router gains a branch that sends it through the existing `_dispatch_structural_escalation` helper — reusing the `escalate_to_split` call and its five-outcome status mapping, not forking a second escalation body. The key decision: the finding is a **structural dispatch, not an `apply_finding` edit**, so it must never reach the Claude apply path, and an `applied` split must **halt the walk** (later saved findings carry now-stale step ids). On green, a synthetic `medium` `granularity-split` rec walked with the opt-in dispatches to a stubbed `escalate_to_split`; without the opt-in it stays advisory.

## Table of Contents

- [Why](#why) — the routing gap this closes and what steps 1–2 already delivered
- [Input](#input) — the finding contract and the walk seams this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and their test files
- [Implementation](#implementation) — the dispatchable path, the router branch, and the halt-on-applied rule
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs worth reading for this step
- [Deferred](#deferred) — flag wiring and other work left to later steps

## Why

Steps 1–2 make the completeness audit produce and persist the `medium` `granularity-split` MIXED-STEP finding into the saved sidecar, so the `completeness-apply` walk can now replay it. But the walk has nowhere to send it. In `plan_tool/cli/review_actions.py`, the `action(rec)` router has branches for recognized commands, `apply_finding` sources, file-check path moves, and `granularity-merge` directives — none match `granularity-split`, so it lands on the terminal "suggested action isn't a recognized reconcile or detail invocation; run it manually" no-op. The correct fix for a mixed step is a 1→2 refactor-then-feature split, and `plan_tool/launcher.py:escalate_to_split` already owns that whole apply-or-recommend mechanism; the review/reconcile walk already reaches it through `_dispatch_structural_escalation` on a `BLOCKED-STRUCTURAL` apply verdict. This step gives the same bridge a second, direct entry point for the persisted `granularity-split` finding — without spending Claude on an `apply_finding` attempt first — so the operator gets an offered split instead of a hand-edit instruction.

## Input

- **Consumes step 2's persisted finding.** Step 2 writes the `medium` `granularity-split` rec into the saved completeness sidecar's `recommendations` list with `source="granularity-split"` (the `GRANULARITY_SPLIT_SOURCE` constant in `plan_tool/granularity.py`), `severity="medium"`, and `step_id` set to the mixed step. This step keys its dispatch on exactly those three fields. Do not re-mint them — `plan_tool/granularity.py:parse_mixed_step_findings` already drops non-code steps, so a `medium` `granularity-split` rec always names a real code step.
- **Reuses the `escalate_to_split` contract.** `plan_tool/launcher.py:escalate_to_split(plan_path, *, step_id, repo_root, invoker, allow_split, prompt_fn=None)` returns a frozen `EscalateResult` whose `outcome` is one of `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing` (only `applied` mutates). The recommend-only vs apply decision is gated by `allow_split` **and** an interactive TTY confirm inside `_confirm_split`; safety keys entirely on `plan_tool/split_safety.py:split_is_safe`. This step does not change the bridge — it only routes into it.
- **Reads the walk's opt-in and halt seams.** `plan_tool/review_walk.py:is_dispatchable(rec, *, extra_apply_sources)` decides whether apply auto-dispatches; `WalkState.halt_requested` / `halt_apply_landed` break the walk loop after the current rec's annotation persists (see `walk_recommendations`). This step widens dispatchability for the opted-in source and sets the halt fields on an applied split.
- **Verification limit.** All tests stub `escalate_to_split` (or the split proposer) so the conftest backend gate never sees a real Claude spawn; the actual 1→2 renumber + detail migration is exercised in `escalate_to_split`'s own tests, not re-proven here.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add a dedicated predicate that recognizes a dispatchable `medium` `granularity-split` finding gated on the caller opt-in; add it as a path in `is_dispatchable`; keep structural sources out of the `apply_finding` route so the finding can't reach `should_apply_as_finding`'s dispatcher.
  - `plan_tool/cli/review_actions.py` — add a branch in `action(rec)` that routes the `granularity-split` finding to `_dispatch_structural_escalation` before the `should_apply_as_finding` branch; give the escalation helper a halt-on-applied path so an applied split stops the completeness-apply walk.
  - `tests/test_review_walk.py` — dispatchability + routing scoping tests for the new source.
  - `tests/cli/test_review_actions.py` — outcome→status mapping and halt-on-applied tests for the new router branch.

## Implementation

### 1. Make the finding dispatchable, scoped to the opt-in (`plan_tool/review_walk.py`)

- **Add a dedicated recognizer**, modeled on `merge_remedy_target`. One shape: `split_escalation_target(rec, *, extra_apply_sources) -> bool` returning True when `rec.source == GRANULARITY_SPLIT_SOURCE` and `rec.severity == "medium"` and `GRANULARITY_SPLIT_SOURCE in extra_apply_sources`. Import `GRANULARITY_SPLIT_SOURCE` from `plan_tool/granularity.py` — `granularity` imports `review` (not `review_walk`), so `review_walk → granularity` is acyclic. Do **not** gate on `step_id` here; a `medium` rec always carries one, and the router surfaces the `step_id is None` case as a re-decompose message if it ever occurs.
- **Gate dispatchability on the caller opt-in**, exactly like `plan-correctness` (see `tests/test_review_walk.py:test_plan_correctness_dispatch_scoped_to_completeness_apply`). Dispatchable only when the caller passes `granularity-split` in `extra_apply_sources`; a generic reconcile/review walk that loads a completeness sidecar as its newest save must **not** auto-dispatch it. The mutation itself stays gated by `allow_split` at the bridge, but scoping dispatch to the opt-in matches the plan's decision to keep this in the completeness-apply lane only.
- **Add the path to `is_dispatchable`.** Thread `extra_apply_sources` into the new recognizer (the parameter is already on `is_dispatchable`). The four existing paths stay; this is a fifth.
- **Keep structural sources out of the `apply_finding` route.** `should_apply_as_finding(rec, extra_sources)` returns True for any `rec.source in extra_sources`. Once step 4 puts `granularity-split` in `extra_apply_sources`, that predicate would otherwise claim the finding for the Claude `apply_finding` dispatcher. Exclude structural sources so it can't — e.g. `should_apply_as_finding` returns True only when `rec.source` is apply-eligible **and not** a structural source (reuse `plan_tool/review.py:is_structural` / `STRUCTURAL_SOURCES`, which already covers `granularity-split`). This is defensive today (the source isn't in `extra_apply_sources` until step 4) but removes the ambiguity before the two routes can both claim the rec. It leaves `plan-correctness` dispatch unchanged (not a structural source), so `test_plan_correctness_dispatch_scoped_to_completeness_apply` stays green.

### 2. Route the finding to the split bridge (`plan_tool/cli/review_actions.py`)

- **Add a branch in `action(rec)`** that recognizes the `granularity-split` finding and routes it to the escalation helper. Place it **before** the `should_apply_as_finding(...)` → `_dispatch_apply_finding(rec)` branch so the finding never triggers a Claude `apply_finding` attempt. Key the branch on `rec.source == GRANULARITY_SPLIT_SOURCE` **and `rec.severity == "medium"`** (import the constant, or reuse `review.is_structural` — but match `granularity-split` specifically, not the recommend-only `structural-split` source). **The severity gate is load-bearing, not redundant with step 2's persistence filter:** the deterministic `info` detectors emit the same `source="granularity-split"` literal, so keying on `source` alone would dispatch a low-confidence `info` rec to `escalate_to_split` if one were ever persisted; the recognizer `split_escalation_target` (above) gates on `severity == "medium"` for the same reason, and both sites must agree.
- **Reuse `_dispatch_structural_escalation`, don't fork it.** It already: guards `rec.step_id is None` (→ "re-decompose by hand"), calls `escalate_to_split(plan_path, step_id=rec.step_id, repo_root=ctx.repo_root, invoker=shell_claude_invoker, allow_split=(allow_split and not state.yes_to_all), prompt_fn=None)`, and maps all five `EscalateResult.outcome` values to a one-line status. The default path (no `allow_split`) spends no Claude — `escalate_to_split` runs the safe-gate and `allow_split` check before any proposal. `allow_split` reaches the builder from step 4's `--apply-structural`; this step only needs the routing to honor it.
- **Do NOT add a whole-plan fingerprint staleness guard (it breaks the common path).** It is tempting to mirror `_dispatch_reground_remedy`'s `_saved_directive_is_stale()` (`saved_plan_fingerprint != compute_plan_fingerprint(plan_path)`) here, but that is wrong: the serial walk applies the rank-0/1/2 conceptual findings via `apply_finding` **before** the rank-last split, and those prose edits change plan/detail **bytes without renumbering steps** — so a whole-plan fingerprint guard would trip on every walk that applied any earlier finding and downgrade the split to recommend-only, making the headline applied-split path unreachable in the normal case. The real invariant is narrower: **no same-walk apply renumbers steps** (only the split does, and it is ranked last and halts), so `step_id` cannot go stale *within* a walk. Rely on `escalate_to_split` re-parsing the plan from disk (it returns `step-missing` if the id is gone) for the external-delete case. The rare "external edit renumbered to a *different valid* step" case is BACKLOG **#93** (precise per-step-id staleness) — **deferred**, not solved with a coarse guard. Do not thread a saved fingerprint into this branch.
- **Halt the walk on an `applied` split.** A 1→2 split renumbers every step from the target onward, so every other saved finding's `step_id`/anchor goes stale. Mirror `_dispatch_merge_remedy`'s applied branch: set `state.halt_requested = True` and `state.halt_apply_landed = True`, and return a status ending with a "walk halted — re-run the diagnosis / re-audit" note. `walk_recommendations` breaks after the annotation persists; `halt_apply_landed` keeps this rec's status `applied` past the break. `recommended` / `unsafe` / `proposal-unusable` / `step-missing` land no edit — record the existing one-line status and let the walk continue.
- **Do not change the reconcile lane's `BLOCKED-STRUCTURAL` behavior.** `_dispatch_structural_escalation` is also reached from `_dispatch_apply_finding` when an apply verdict is `BLOCKED-STRUCTURAL`. That caller must keep its current post-applied behavior. Recommended: give `_dispatch_structural_escalation` a `halt_on_applied: bool = False` keyword and pass `True` only from the new `granularity-split` branch — the existing `BLOCKED-STRUCTURAL` call keeps the default. One alternative — setting the halt unconditionally inside the shared helper — would also make the reconcile-iteration loop halt after a split; that touches `_iterate_reconcile_loop`'s `halt_merged` handling (in `plan_tool/cli/reconcile.py`, outside this step's files), so prefer the scoped keyword and leave the reconcile-lane halt question to Deferred.

### Constraints / gotchas

- **`granularity-split` stays out of `APPLY_ELIGIBLE_SOURCES`** and out of the `apply_finding` route — it is a structural dispatch. It must not flip an exit code.
- **Order matters in `action(rec)`.** The `granularity-split` branch must precede the `should_apply_as_finding` branch; otherwise the finding routes to `_dispatch_apply_finding` and burns a Claude apply attempt.
- **Recommend-only under `-y` / non-TTY.** `_dispatch_structural_escalation` already forces `allow_split=(allow_split and not state.yes_to_all)` and passes `prompt_fn=None`, so a blanket fast-forward or a non-TTY invoke recommends only. Preserve that — don't route the `granularity-split` branch around it.
- **Only `applied` mutates and only `applied` halts.** Any other outcome records a status and continues.

## Tests

### Test-creation order (feature step)

This is a feature step — new dispatch behavior. Add the unit tests below **with** the implementation; every new test must be green before the step is done. Stub `escalate_to_split` throughout so the conftest backend gate never sees a real spawn (no `@allow_real_claude` marker needed). Build the lowest-level dispatchability tests first, then the router/outcome tests.

`tests/test_review_walk.py` (dispatchability + scoping — model on `TestMergeDirectiveDispatch` and `test_plan_correctness_dispatch_scoped_to_completeness_apply`):

- `test_medium_granularity_split_dispatchable_only_with_opt_in` — a `medium` `granularity-split` rec is `is_dispatchable(rec)` False with no `extra_apply_sources`, and True with `extra_apply_sources=frozenset({"granularity-split"})`.
- `test_info_granularity_split_not_dispatchable` — an `info` `granularity-split` rec is not dispatchable even with the opt-in (only the `medium` mixed-step signal dispatches).
- `test_granularity_split_not_routed_as_apply_finding` — `should_apply_as_finding` returns False for a `granularity-split` rec even when `granularity-split` is in `extra_sources` (structural sources are excluded from the apply-finding route).

`tests/cli/test_review_actions.py` (routing + outcomes — model on `TestStructuralEscalation`, reuse its `_stub_escalate`/`_escalate_result` helpers):

- `test_granularity_split_routes_to_escalate_to_split` — walking a `medium` `granularity-split` rec (opted in) calls the stubbed `escalate_to_split` with `step_id` = the rec's step and `allow_split` threaded from the builder.
- `test_granularity_split_never_calls_apply_finding` — the branch dispatches to `escalate_to_split`, not `apply_finding` (patch both; assert `apply_finding` uncalled).
- `test_granularity_split_applied_halts_walk` — an `applied` outcome sets `state.halt_requested` / `state.halt_apply_landed` and returns a status naming the re-audit.
- `test_granularity_split_recommended_does_not_halt` — a `recommended` outcome leaves `halt_requested` False and returns the recommend-only status.
- `test_granularity_split_yes_to_all_forces_recommend_only` — with `state.yes_to_all=True`, `escalate_to_split` is called with `allow_split=False`.
- `test_granularity_split_step_id_none_reports_redecompose` — a `granularity-split` rec with `step_id=None` returns the re-decompose message and never calls `escalate_to_split`.
- `test_blocked_structural_reconcile_path_unchanged` — the existing `BLOCKED-STRUCTURAL` route (via `_dispatch_apply_finding`) still does not halt on `applied` (guards the scoped `halt_on_applied` default).

## Acceptance criteria

- `is_dispatchable(rec)` is False for a `medium` `granularity-split` rec with no `extra_apply_sources`, and True when `granularity-split` is passed in `extra_apply_sources`.
- Walking a `medium` `granularity-split` rec with the opt-in calls `escalate_to_split` (stubbed) with the rec's `step_id`; it never calls `apply_finding`.
- An `applied` escalate outcome sets `state.halt_requested` and `state.halt_apply_landed` and returns a status telling the operator to re-audit; `recommended` / `unsafe` / other outcomes do not halt.
- Under `state.yes_to_all`, `escalate_to_split` is called with `allow_split=False` (recommend-only).
- The existing `BLOCKED-STRUCTURAL` reconcile route is unchanged (no new halt on its applied split).
- `granularity-split` is not in `APPLY_ELIGIBLE_SOURCES` and the new path does not flip an exit code.
- All new tests in `tests/test_review_walk.py` and `tests/cli/test_review_actions.py` pass, and the existing `TestStructuralEscalation` and `test_plan_correctness_dispatch_scoped_to_completeness_apply` stay green.

## References

- `plan_tool/launcher.py:escalate_to_split` (its docstring + the frozen `EscalateResult` contract) — the bridge this step routes into: the `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing` outcomes, the `allow_split` + TTY-confirm gate, and the `split_safety.split_is_safe` choke point. The load-bearing reference for the dispatch this step wires.
- CLAUDE.md, "Escalate-to-split bridge" section — the bridge's callers, invariants (*always surface the more-correct plan* / *never mutate structure unattended*), and the two routing tokens (`structural-split` recommendation, `BLOCKED-STRUCTURAL` verdict); read it to see why `granularity-split` reuses `_dispatch_structural_escalation` rather than forking a second escalation body.
- `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` (and its `TestStructuralEscalation` tests) — the existing review/reconcile-lane entry point this step reuses, including the five-outcome→status mapping and the `rec.step_id is None` → re-decompose guard.
- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — Tangential to step 3; the `--apply-structural` → `allow_split` flag wiring lands in step 4 (`plan_tool/cli/completeness_cmd.py`). Read it there, not here.

## Deferred

- **`--apply-structural` flag + `allow_split` threading** — step 4 wires the opt-in in `plan_tool/cli/completeness_cmd.py` and adds `granularity-split` to `_SAVED_SERIAL_APPLY_SOURCE_RANK` and `_walk_apply_sources`; step 3 only makes the capability exist and testable via synthetic recs.
- **Persisting the finding to the sidecar** — done in step 2; step 3 assumes the `medium` `granularity-split` rec is already in `saved.recommendations`.
- **The reconcile lane's own halt-on-applied for `BLOCKED-STRUCTURAL`** — this step keeps that route's behavior unchanged via the scoped `halt_on_applied` default; whether the reconcile-iteration loop should also halt after a split is a separate `plan_tool/cli/reconcile.py` change, out of this step's files.
- **Run-evidence hardening of `split_is_safe`** — consulting run-log markers or `git status --porcelain` is a change to the single safe-gate choke point affecting every `escalate_to_split` caller; tracked in the plan's Deferred, not bundled here.
- **`create`-side structural dispatch** — the `create` convergence loop still does not route through `escalate_to_split`; deferred per CLAUDE.md.
