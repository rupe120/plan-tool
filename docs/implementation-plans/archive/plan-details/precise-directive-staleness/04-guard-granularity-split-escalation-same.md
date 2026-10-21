> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Guard the granularity-split escalation with the same precise check

## Summary

Adds the per-directive stale check (from step 3) to the third structural bridge — the `granularity-split` MIXED-STEP escalation — so a saved split finding whose target step still holds its identity actuates under `--apply-structural` even after an earlier apply in the same walk rewrote the plan. The change lives in `plan_tool/cli/review_actions.py`: `_dispatch_structural_escalation` gains a default-off keyword (recommended name `guard_saved_directive`) that the `granularity-split` router branch in `action` passes on; when set and step 3's `_saved_directive_is_stale(rec)` reports stale, the dispatcher downgrades to recommend-only (records `resolved=False`, returns a re-run-the-diagnosis message) before ever calling `escalate_to_split`. The BLOCKED-STRUCTURAL reconcile caller keeps the default and is unchanged. On green, a fresh saved split escalates and a stale one is refused with no mutation, matching how re-ground and merge already behave.

## Table of Contents

- [Why](#why) — the split escalation has no staleness protection today
- [Input](#input) — step 1's field and step 3's rewritten guard this step reuses
- [Files (creates vs edits)](#files-creates-vs-edits) — the dispatcher guard, the router wiring, and tests
- [Implementation](#implementation) — where the guard goes, how it's scoped, and the constraints
- [Tests](#tests) — fresh/stale/legacy split cases and the unchanged reconcile path
- [Acceptance criteria](#acceptance-criteria) — observable results on green
- [References](#references) — stdlib docs for the field and the hash
- [Deferred](#deferred) — the other staleness surfaces and stamping

## Why

The `granularity-split` MIXED-STEP finding is the one structural bridge that today has **no staleness guard at all**. In `plan_tool/cli/review_actions.py`, `_dispatch_reground_remedy` and `_dispatch_merge_remedy` both gate on `_saved_directive_is_stale()` before their bridge call, but `_dispatch_structural_escalation` calls `escalate_to_split` with no such check. In the completeness-apply lane this gap is sharper than for the others: that lane builds the action fn with no `saved_plan_fingerprint` (see `plan_tool/cli/completeness_cmd.py`, the `_build_review_action_fn(...)` call that omits it), so even the old coarse whole-plan check is a no-op here — there is currently *nothing* that stops a stale saved split from escalating against a step id that a prior apply moved. Step 3 makes the guard precise by keying on each directive's own target signature (recovered from the finding, recomputed from disk). This step routes the split escalation through that same guard so a split finding whose target step still holds its `(id → title)` identity actuates even after an unrelated earlier apply, while a split whose target moved is downgraded to recommend-only.

## Input

- **Step 1 produces the field and the hasher.** `Recommendation.target_signature: Optional[str] = None` (`plan_tool/review.py`) and `compute_target_signature(plan, target_ids)` (`plan_tool/review_walk.py`). This step neither defines nor stamps them; it only benefits from step 3 reading them.
- **Step 2 stamps the split finding.** The `medium` `granularity-split` rec is stamped with its `target_signature` before it is saved (target set `(rec.step_id,)`), via `stamp_target_signatures` in the completeness write path. So a persisted split finding reaching this walk already carries a non-empty signature. This step does not stamp — it reads.
- **Step 3 produces the guard this step calls.** `_saved_directive_is_stale(rec)` in `plan_tool/cli/review_actions.py` — rewritten from a no-argument closure to take the `rec`, recover its target ids through `directive_target_ids(rec)`, recompute `compute_target_signature` from the plan on disk, and compare against `rec.target_signature`. `None` signature falls back to the coarse whole-plan check; a `granularity-split` rec has a non-None signature so it takes the precise path. **Reuse this closure exactly as re-ground and merge do — do not re-derive target ids or re-hash in the split path.** The whole point is that stamp-time and guard-time ids come from one shared function and can't diverge.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` —
    - Add a default-off keyword to `_dispatch_structural_escalation` (recommended `guard_saved_directive: bool = False`) that, when true, runs `_saved_directive_is_stale(rec)` before the `escalate_to_split` call and, on stale, records `apply_structural_outcome(state, rec, StructuralOutcomeEffects(resolved=False))` and returns a recommend-only message.
    - In `action`, pass the new keyword `True` where the `split_escalation_target(...)` branch calls `_dispatch_structural_escalation(rec, halt_on_applied=True)`.
  - `tests/cli/test_review_actions.py` — add the fresh / stale / legacy split cases plus the unchanged-reconcile assertion, in `TestSplitEscalationDispatch`. Extend the `_split_finding_rec` helper (or the tests) so a rec can carry a chosen `target_signature`.

## Implementation

**What changes:** the split-escalation path gets the same pre-apply staleness refusal the other two bridges have — scoped so only the completeness-apply split caller is affected, not the shared reconcile caller.

**Scope the guard with a dedicated default-off keyword, not by reusing `halt_on_applied`.**
- Add `guard_saved_directive: bool = False` (name is a suggestion — pick something self-descriptive) to `_dispatch_structural_escalation`. Only the `split_escalation_target(...)` branch in `action` passes it `True`; the BLOCKED-STRUCTURAL caller keeps the default, so the reconcile lane is unchanged.
- **Don't gate the guard on the existing `halt_on_applied` flag.** Both flags happen to be set by the same branch today, but they are different concerns — `halt_on_applied` is a *post-apply* walk halt, the new flag is a *pre-apply* staleness refusal. Folding them couples two unrelated behaviors and makes each impossible to test alone. A dedicated flag mirrors the precedent set when `halt_on_applied` itself was added as a default-off keyword rather than made unconditional.

**Put the guard right before the mutating bridge call.**
- Run the check after the existing `if rec.step_id is None:` plan-level branch and before the `result = escalate_to_split(...)` call. A `medium` `granularity-split` always carries a `step_id`, so the plan-level branch passes through and the guard sees a real target.
- On stale, mirror the re-ground/merge downgrade exactly: call `apply_structural_outcome(state, rec, StructuralOutcomeEffects(resolved=False))` (records skip → `apply_skip=True`) and return a one-line recommend-only message. Keep the wording close to `_dispatch_reground_remedy`'s ("the plan changed since this finding was computed … re-run the diagnosis (completeness-audit) … then re-walk") so a reader recognizes the shared behavior and tests can assert a stable substring like "changed since".
- Fire the guard **regardless of `allow_split`**. Re-ground and merge guard before their bridge unconditionally; a stale directive should be refused with the re-run message even in recommend-only mode, rather than recommending a split at a step that may have moved.

**No session short-circuit is needed here (unlike re-ground).**
- `_dispatch_reground_remedy` carries a `rec.id in state.applied_structural_finding_ids` pre-check because a re-ground can be re-dispatched (r-then-a) within one walk after it rewrote the plan. An **applied split halts the walk** (`halt_on_applied=True` → `halt_requested` / `halt_apply_landed`) and escalation never records the finding id, so there is no same-walk re-dispatch to protect against. Do not copy re-ground's session pre-check into the split path.

**Constraints that must hold:**
- The BLOCKED-STRUCTURAL apply-verdict path (default keyword off) must call `escalate_to_split` with no added guard — its existing test `test_blocked_structural_reconcile_path_unchanged` must stay green.
- The guard must be a no-op when the rec's `target_signature` is `None` and no `saved_plan_fingerprint` is set (the legacy shape today's `_split_finding_rec` builds), so existing `TestSplitEscalationDispatch` cases that expect the bridge to be reached don't regress. This falls out of step 3's guard: `None` signature + empty fingerprint → not stale.
- Order stays: `rec.step_id is None` check → **stale guard** → `escalate_to_split`. The stale downgrade must happen before any mutation and before `structural_apply_allowed(allow_split, state)` is consulted.

**Foundational logic and where else it lives.** The rule this step adds is "refuse to actuate a saved directive whose own targets moved." That rule already lives in `_dispatch_reground_remedy` and `_dispatch_merge_remedy` (same file) and, at a different altitude with different fingerprint axes, in `plan_tool/cli/convergence_cmd.py` (`_actuate_scope_out`) and the review/reconcile `plan_match` in `plan_tool/cli/review_cmd.py` / `plan_tool/cli/reconcile.py`. This step deliberately **reuses** the in-file `_saved_directive_is_stale(rec)` closure and touches none of the other surfaces — they classify freshness over different dataclasses and axes, and consolidating them is a cross-module refactor out of this step's footprint (leave to reconcile / a future step).

## Tests

All in `tests/cli/test_review_actions.py`, class `TestSplitEscalationDispatch`. Extend `_split_finding_rec` so a rec can carry a `target_signature` (or set it per-test), and write the plan file on disk in cases that exercise the guard (as the re-ground stale tests write `demo.md`).

- `test_split_fresh_signature_escalates` — a split rec whose `target_signature` matches the signature recomputed from the plan on disk reaches `escalate_to_split` (bridge called once), even with an unrelated plan edit present; produce the matching value by calling step 1's `compute_target_signature` for the on-disk plan and `(step_id,)`.
- `test_split_stale_signature_downgrades_to_recommend` — a split rec whose `target_signature` won't match the on-disk plan is refused: `escalate_to_split` is never called, `state.apply_skip is True`, and the result contains the re-run substring ("changed since").
- `test_split_legacy_none_signature_still_escalates` — a split rec with `target_signature=None` and no `saved_plan_fingerprint` reaches the bridge unchanged (guard is a no-op — proves existing behavior doesn't regress).
- `test_split_stale_downgrade_does_not_record_finding_id` — on a stale downgrade the rec id is not added to `state.applied_structural_finding_ids` and the walk is not halted (`halt_requested is False`).
- `test_blocked_structural_reconcile_path_unchanged` (existing) — still green: the BLOCKED-STRUCTURAL caller runs no stale guard and escalates on an `applied` result.

**Test-creation order (feature step).** This step adds new behavior. Add each unit test above alongside the guard code. Green-before-done gate: every new test — and the existing `TestSplitEscalationDispatch` / `TestStructuralEscalation` / reconcile-path tests — must pass before this step is finished.

## Acceptance criteria

- `_dispatch_structural_escalation` accepts a default-off keyword that, when true and `_saved_directive_is_stale(rec)` returns true, returns a recommend-only message and never calls `escalate_to_split`.
- The `granularity-split` router branch in `action` passes that keyword `True`; the BLOCKED-STRUCTURAL caller does not.
- A fresh (matching-signature) split escalates; a stale (non-matching-signature) split is downgraded with `apply_skip` set and no mutation.
- A `None`-signature split with no saved fingerprint still reaches the bridge (no regression).
- The stale-downgrade path leaves `halt_requested`, `halt_apply_landed`, and `applied_structural_finding_ids` untouched.
- All new tests and the existing `TestSplitEscalationDispatch` / reconcile-path tests pass (`uv run pytest tests/cli/test_review_actions.py -q`).

## References

- `_dispatch_reground_remedy` / `_dispatch_merge_remedy` in `plan_tool/cli/review_actions.py` — the two sibling structural dispatchers this step mirrors: each gates on `_saved_directive_is_stale(rec)` before its bridge call and downgrades to recommend-only on stale. Match their guard placement, downgrade recording (`apply_structural_outcome(state, rec, StructuralOutcomeEffects(resolved=False))`), and re-run message wording.
- `_saved_directive_is_stale(rec)` in `plan_tool/cli/review_actions.py` (rewritten by step 3) — the closure this step calls; reuse it exactly, do not re-derive target ids or re-hash in the split path.
- `compute_target_signature(plan, target_ids)` in `plan_tool/review_walk.py` (step 1) — the `(id → title)` hasher the guard recomputes from disk; tests recompute it to produce a matching signature for the fresh case.

## Deferred

- Stamping the `target_signature` — owned by step 2; this step only reads it.
- Rewriting `_saved_directive_is_stale` to the per-directive form — owned by step 3; this step reuses the rewritten closure.
- The re-ground and merge staleness callers — already carry the guard from step 3; unchanged here.
- The other staleness surfaces (`convergence_cmd.py:_actuate_scope_out`, review/reconcile `plan_match`) — different dataclasses and fingerprint axes; consolidating them is a cross-module refactor left for reconcile.
- Adding the guard to the BLOCKED-STRUCTURAL reconcile caller — that path handles a live apply verdict, not a persisted saved directive, and its post-split behavior is owned by the reconcile lane; intentionally left off.
