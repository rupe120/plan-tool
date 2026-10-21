> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add `--apply-structural` to completeness-apply and gate the split dispatch

## Summary

Give `completeness-apply` a `--apply-structural` opt-in and wire the saved `medium` `granularity-split` MIXED-STEP finding into its interactive walk so it reaches step 3's dispatch. Two edits in `plan_tool/cli/completeness_cmd.py`: register the flag on the `completeness-apply` subparser, and thread the `granularity-split` source plus an `allow_split` value into the existing walk seams (`_SAVED_SERIAL_APPLY_SOURCE_RANK`, `_walk_apply_sources`, `_build_review_action_fn`, and `walk_recommendations`). The key decision: keep `allow_split` off unless `--apply-structural` is set *and* the run is not a blanket `-y` fast-forward, so a structural mutation only lands under a deliberate opt-in plus an interactive confirm; every other path recommends only. On green, a saved sidecar carrying a `medium` `granularity-split` finding, walked with `--apply-structural` on a safe plan with an interactive `yes`, dispatches through `escalate_to_split` and applies the 1→2 split; without the flag (or under `-y`, or in the `--jobs > 1` lane) the same finding is recommend-only.

## Table of Contents

- [Why](#why) — the CLI/opt-in gap this closes and what steps 2–3 already delivered
- [Input](#input) — the persisted finding and the walk seams this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — the one source file and its test file
- [Implementation](#implementation) — the flag, the source threading, and the `allow_split` gate
- [Tests](#tests) — unit cases added with the implementation
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — the docs worth reading for this step
- [Deferred](#deferred) — what this step deliberately leaves out

## Why

Steps 2 and 3 leave the wiring one hop short of usable. Step 2 persists the `medium` `granularity-split` MIXED-STEP rec into the saved completeness sidecar; step 3 gives the apply walk a dispatch path for it (a dedicated `is_dispatchable` branch in `plan_tool/review_walk.py` and a router branch in `plan_tool/cli/review_actions.py` that sends it through `_dispatch_structural_escalation` → `escalate_to_split`). But both of those seams only fire when the completeness-apply command **hands the `granularity-split` source and an `allow_split` value into the walk**. Today `cmd_completeness_apply` filters `saved.recommendations` down to `_SAVED_SERIAL_APPLY_SOURCE_RANK` (`plan-correctness`, `plan-completeness`, `data-contract`) — `granularity-split` is not a member, so the persisted finding is dropped before the walk ever sees it. And `_walk_apply_sources` (the frozenset passed to both `_build_review_action_fn` and `walk_recommendations`) is `{"plan-correctness", "data-contract"}`, so step 3's opt-in-scoped dispatch can never trigger. There is also no operator-facing switch to turn structural mutation on. This step adds that switch and closes the two threading gaps, entirely inside `plan_tool/cli/completeness_cmd.py`.

## Input

- **Consumes step 2's persisted finding.** Step 2 writes the `medium` `granularity-split` rec into the saved completeness sidecar's `recommendations` list with `source="granularity-split"` (the `GRANULARITY_SPLIT_SOURCE` constant in `plan_tool/granularity.py`), `severity="medium"`, and `step_id` set to the mixed step. This step keys the walk filter and the apply-source opt-in on that `source` value; it re-mints nothing.
- **Consumes step 3's dispatch contract.** Step 3 makes `plan_tool/review_walk.py:should_apply_as_finding` / `is_dispatchable` and the `action(rec)` router in `plan_tool/cli/review_actions.py` route a `granularity-split` rec to `_dispatch_structural_escalation` **only when `GRANULARITY_SPLIT_SOURCE` is in the caller's `extra_apply_sources`**. This step supplies that membership. Do not re-specify step 3's branch order or its `halt_on_applied` handling — this step only feeds the sources and `allow_split`.
- **Reuses the shared structural gate.** `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` already computes `allow_split=(allow_split and not state.yes_to_all)` and passes `prompt_fn=None` (a genuine TTY confirm, auto-declines on a non-TTY). This step supplies the `allow_split` value the helper ANDs against; it changes nothing inside the helper.
- **Limit on verification.** The end-to-end split is not exercised for real in tests — the conftest autouse gate raises if a backend binary spawns. Assert dispatch by stubbing `escalate_to_split` (and `shell_claude_invoker`), not by driving a live split.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/completeness_cmd.py`
    - Register `--apply-structural` (`action="store_true"`, `dest="apply_structural"`, default off) on the `p_completeness_apply` subparser in `register`.
    - Add `GRANULARITY_SPLIT_SOURCE` to the walk-filter source rank so the finding survives the `saved.recommendations` filter (extend `_SAVED_SERIAL_APPLY_SOURCE_RANK`, or a superset used only for that filter — see Implementation).
    - Add `GRANULARITY_SPLIT_SOURCE` to the `_walk_apply_sources` frozenset built in the serial walk, so step 3's dispatch fires. It flows to both `_build_review_action_fn(..., extra_apply_sources=...)` and `walk_recommendations(..., extra_apply_sources=...)` — both must agree.
    - Compute an `allow_split` value from the flag and pass it into `_build_review_action_fn(..., allow_split=...)`.
  - `tests/cli/test_completeness_cmd.py`
    - New cases for the flag-on dispatch, the recommend-only defaults, and the parallel-lane exclusion (see Tests).

## Implementation

**Add the `--apply-structural` flag.** Register it on `p_completeness_apply` in `register`, next to the existing `--include-info` / `--rewalk` flags. `action="store_true"`, `dest="apply_structural"`, default off. Help text: it opts the walk into *applying* a `medium` `granularity-split` step split (via `escalate_to_split`) on a safe plan with an interactive confirm; without it the finding is recommend-only. Keep it a separate flag from `--include-info` — `--include-info` controls info-severity gaps, and the `medium` split finding is walked regardless of it.

*In-file framing note.* Two maintainer-facing strings in this module still describe only the conceptual sources: the `p_completeness_apply` help ("Walks BOTH conceptual sources — plan-correctness first, then plan-completeness") and the `cmd_completeness_apply` module docstring ("replays the saved audit's `plan-correctness` and `plan-completeness` findings"). The new `--apply-structural` help surfaces the structural walk, so leave those conceptual-sources sentences as-is; refreshing that framing to also name the `granularity-split` structural walk is a deferred follow-up, not part of this step (see Deferred).

**Let the finding survive the walk filter.** The serial walk builds `walk_recs = [r for r in saved.recommendations if r.source in _SAVED_SERIAL_APPLY_SOURCE_RANK]` and sorts by that rank. `granularity-split` must be a member or it is dropped before the walk. Two constraints to respect:
- **Ranking / order.** Give it a rank value **after** the conceptual and data-contract sources (e.g. `3`). Reason: an applied split halts the walk and renumbers every later step's `step_id`, so let the reversible conceptual/prose and data-contract applies run first and put the irreversible, halting split last. One way: add `GRANULARITY_SPLIT_SOURCE: 3` to `_SAVED_SERIAL_APPLY_SOURCE_RANK`.
- **Keep it out of the conceptual/parallel path — but do not drop it silently.** `conceptual_walk_recs` filters on `_CONCEPTUAL_APPLY_SOURCE_RANK` (`plan-correctness`, `plan-completeness`) — do **not** add `granularity-split` there, so the `--jobs > 1` parallel lane never fans it out (a structural mutation must never run in a parallel worktree worker). Verify the two rank dicts stay distinct. **However**, `completeness-apply` degrades to serial only when `not conceptual_walk_recs and walk_recs`, so a **mixed** sidecar (conceptual gaps *plus* a `medium` `granularity-split`) still runs `_apply_walk_recs_parallel(conceptual_walk_recs, …)` and returns "done" while the split is never processed. That silently drops a discovered mixed-step split — a "no silent caps" violation. **Emit an operator-facing breadcrumb** whenever the parallel lane runs and one or more `medium` `granularity-split` findings are present in the sidecar: a one-line notice like `note: N mixed-step split(s) pending — re-run the serial walk (drop --jobs / --jobs 1) with --apply-structural to act on them`. The parallel lane is not "recommend-only" for the split (it prints nothing about the split otherwise); the breadcrumb is what makes the deferral visible. Add a test asserting the notice fires on a mixed sidecar under `--jobs > 1`.

**Thread the source into the walk's apply-source opt-in.** In the serial walk, `_walk_apply_sources` is currently `frozenset({"plan-correctness", _DATA_CONTRACT_SOURCE})`. Add `GRANULARITY_SPLIT_SOURCE` to it. It already flows to both `_build_review_action_fn(..., extra_apply_sources=_walk_apply_sources)` and `walk_recommendations(..., extra_apply_sources=_walk_apply_sources)`, so one edit reaches both seams — which step 3 requires (the walker's dispatchability predicate and the action router must see the same set, or the walk records an annotation without dispatching, or falls through to the manual-run no-op).

**Gate `allow_split` — the key decision.** `_build_review_action_fn` accepts `allow_split: bool = False`; the serial walk currently omits it (so it defaults off). Pass an explicit value:
- **Recommended:** `allow_split = bool(args.apply_structural) and not bool(getattr(args, "yes", False))`.
- **Why this shape.** `--apply-structural` is the deliberate opt-in. ANDing with `not args.yes` makes a blanket `-y` fast-forward recommend-only for the structural split — a structure mutation must never auto-confirm — while leaving the serial walk's existing per-gap interactive behavior for conceptual applies untouched. `_dispatch_structural_escalation` further ANDs with `not state.yes_to_all`, so this is double-guarded, not conflicting.
- **Alternative rejected:** seeding `state = WalkState(yes_to_all=bool(args.yes))`. That would also flip conceptual `apply_finding` calls into fast-forward under `-y`, a behavior change outside this step's scope. Computing `allow_split` locally keeps the change in-file and side-effect-free.

**Constraints that must hold:**
- `granularity-split` stays **out** of `_CONCEPTUAL_APPLY_SOURCE_RANK` (parallel exclusion) and out of any list that would route it to `apply_finding` as a prose edit — it is a structural dispatch. Step 3 owns the `is_structural` exclusion in `should_apply_as_finding`; this step must not add `granularity-split` anywhere that reads it as an apply-finding source.
- The two seams that read `_walk_apply_sources` must receive the same frozenset. Do not add the source to one and not the other.
- Do not change `_dispatch_structural_escalation`, `is_dispatchable`, or the halt-on-applied wiring — those are step 3's. This step only supplies inputs.

## Tests

Add these to `tests/cli/test_completeness_cmd.py` (mirror the existing `TestCompletenessApply*` classes; stub `escalate_to_split` and `shell_claude_invoker` so no backend spawns). Suggested new class: `TestCompletenessApplyStructuralSplit`.

- `test_apply_structural_dispatches_medium_split_to_escalate` — with `--apply-structural`, a TTY, and a safe plan, a saved `medium` `granularity-split` rec reaches a stubbed `escalate_to_split` (assert the stub was called with `step_id` = the finding's `step_id` and `allow_split=True`).
- `test_medium_split_recommend_only_without_flag` — without `--apply-structural`, the same saved rec walks but `escalate_to_split` is called with `allow_split=False` (recommend-only); plan + detail files unchanged.
- `test_medium_split_recommend_only_under_yes` — with `--apply-structural` **and** `-y`, the computed `allow_split` is `False` (blanket fast-forward never auto-applies a split).
- `test_medium_split_not_fanned_out_in_parallel` — with `--jobs 2 -y` on a clean tree, `granularity-split` is not in `conceptual_walk_recs`, so the parallel path never applies it (assert it is absent from the fanned-out set / degrades or is reported).
- `test_medium_split_survives_saved_walk_filter` — a saved sidecar carrying a `medium` `granularity-split` rec produces a `walk_recs` list that includes it (it is no longer dropped by the source-rank filter), and it sorts after the conceptual and data-contract sources.
- `test_walk_apply_sources_includes_granularity_split` — the frozenset passed to both `_build_review_action_fn` and `walk_recommendations` contains `GRANULARITY_SPLIT_SOURCE` (guard the two-seam-agreement invariant).
- `test_apply_structural_flag_registered` — parsing `completeness-apply <name> --apply-structural` sets `args.apply_structural is True`; default is `False`.

### Test-creation order (feature step)

This is a **feature** step. Author the tests above **with** the implementation, lowest-contract first: flag registration → walk-filter survival → source-set agreement → dispatch/allow_split gating → parallel exclusion. Every new test must be green before this step is considered finished, and the existing `TestCompletenessApply*`, `TestCompletenessApplyParallel`, and `TestGranularitySmellNeverGates` classes must stay green.

## Acceptance criteria

- `completeness-apply <name> --apply-structural` parses with `args.apply_structural is True`; default is `False`.
- A saved sidecar carrying a `medium` `granularity-split` rec (resolvable `step_id`) is included in `walk_recs` (not dropped by the source-rank filter) and sorts after `plan-correctness` / `plan-completeness` / `data-contract`.
- The frozenset handed to both `_build_review_action_fn(extra_apply_sources=...)` and `walk_recommendations(extra_apply_sources=...)` contains `GRANULARITY_SPLIT_SOURCE`.
- With `--apply-structural`, a TTY, and a safe plan, the walk calls `escalate_to_split` (stubbed) with `allow_split=True` and the finding's `step_id`.
- Without `--apply-structural`, or with `--apply-structural` **and** `-y`, `escalate_to_split` is reached with `allow_split=False` (recommend-only); plan and detail files are unchanged.
- Under `--jobs > 1`, the `granularity-split` finding is not in `conceptual_walk_recs` and is never applied by the parallel path.
- All new tests in `tests/cli/test_completeness_cmd.py` pass; no real backend is spawned (conftest gate holds).

## References

- `CLAUDE.md` — the **"Escalate-to-split bridge (`launcher.py:escalate_to_split`)"** section — the frozen `EscalateResult` contract, the safe + `allow_split` + interactive-confirm decision rule, and the `allow_split=(allow_split and not yes_to_all)` never-mutate-unattended invariant this step's `allow_split` gate must preserve.
- `plan_tool/cli/review_actions.py:_dispatch_structural_escalation` — the shared structural-dispatch helper this step feeds; it already computes `allow_split=(allow_split and not state.yes_to_all)` and passes `prompt_fn=None`, so read it to see exactly which value this step supplies and why the `-y` AND is belt-and-suspenders.
- `plan_tool/review_walk.py:should_apply_as_finding` / `is_dispatchable` — the `extra_apply_sources` semantics: a `granularity-split` rec only dispatches when `GRANULARITY_SPLIT_SOURCE` is in the caller's `extra_apply_sources` and stays out of the `apply_finding` prose path, which is the membership this step's `_walk_apply_sources` edit provides.
- [argparse — Parser for command-line options (Python docs)](https://docs.python.org/3/library/argparse.html) — `add_argument` / `store_true` reference for wiring `--apply-structural` and its default onto the `completeness-apply` subparser.

## Deferred

- **The `granularity-split` dispatch path, halt-on-applied, and `apply_finding` exclusion** — owned by step 3 in `plan_tool/review_walk.py` and `plan_tool/cli/review_actions.py`; this step only feeds the source set and `allow_split`.
- **Persisting the finding to the sidecar** — owned by step 2 (`plan_tool/cli/completeness_phases.py` + `DATA_CONTRACT.md`); this step consumes the persisted rec.
- **Docs and backlog updates** — `CLAUDE.md`, `RUNBOOK.md`, `docs/cli/completeness-apply.md`, and `BACKLOG.md` #70 are step 5.
- **Refreshing the in-file conceptual-sources framing** — the `p_completeness_apply` help and `cmd_completeness_apply` module docstring keep describing only `plan-correctness`/`plan-completeness`; broadening them to name the `granularity-split` structural walk is a deferred follow-up (the `--apply-structural` help already surfaces the structural walk).
- **Parallel-lane structural apply** — the `--jobs > 1` worktree lane stays recommend-only for structural findings; safe parallel structural apply is future design (plan Deferred).
- **`create`-side structural dispatch** — deferred per the plan; this arm is completeness-apply only.
