> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Extract a shared `allow = <token> and not yes_to_all` gate helper for the three bridge dispatchers

## Summary

Pull the one-line apply-or-recommend gate the three bridge dispatchers in `plan_tool/cli/review_actions.py` each write by hand — `<opt-in token> and not state.yes_to_all` — into one small helper in `plan_tool/review_walk.py`, and route `_dispatch_structural_escalation`, `_dispatch_reground_remedy`, and `_dispatch_merge_remedy` through it. Each dispatcher keeps its own opt-in token (`allow_split` vs `allow_structural_remedy`) and its own confirm seam (`prompt_fn=None` / `yes=False`); the helper owns only the shared "a blanket fast-forward must never auto-confirm an irreversible structure mutation" rule. `_dispatch_file_check_create` is deliberately left out — it has no bridge and **inverts** the rule (it auto-applies `create` under `yes_to_all`). This is a behavior-preserving refactor: on green, every dispatcher passes the exact same gated bool to its bridge as it does today, and the existing gate characterization tests pass unchanged.

## Table of Contents

- [Why](#why) — why the gate expression is worth single-sourcing now
- [Input](#input) — the shared kernel and gate map this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and two test files
- [Implementation](#implementation) — the helper shape, the three call sites, and what stays per-dispatcher
- [Tests](#tests) — the characterization gate tests plus a direct helper unit test
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — pin the gate before extracting, keep it green after
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer/CI can run
- [References](#references) — the three dispatchers and `WalkState`/`apply_structural_outcome` this step reuses
- [Deferred](#deferred) — file-check, the kernel, and the confirm seam left out on purpose

## Why

The three bridge dispatchers each re-type the same gate: escalation passes `allow_split=(allow_split and not state.yes_to_all)`, reground passes `allow_reground=allow_structural_remedy and not state.yes_to_all`, and merge passes `allow_merge=allow_structural_remedy and not state.yes_to_all`. The rule — an opt-in flag AND no blanket `-y` fast-forward — is the same in all three, but it's copied three times, so a future edit to one can silently drop the `and not state.yes_to_all` half and let a fast-forward auto-confirm a split, fold, or re-ground with no interactive checkpoint. That is the same "one dispatcher drifts from its siblings" hazard step 2 removes for the `WalkState` side-effect tail; this step removes it for the gate. Writing the rule once makes the fast-forward safety a single reviewable place.

## Input

This step builds on **step 2's shared outcome kernel** (`apply_structural_outcome` + `StructuralOutcomeEffects` in `plan_tool/review_walk.py`), which the four dispatchers already route their `WalkState` tail through after step 2 lands. This step adds a **second** small shared piece beside it — the gate — and does not change the kernel.

The gate map it must preserve (verified against the current dispatchers, do not invent new behavior):

- **All three bridge dispatchers** gate on `<opt-in token> and not state.yes_to_all`, then forward the confirm seam (escalation: `prompt_fn=None`; reground/merge: `yes=False`) so the bridge owns the TTY confirm.
- **The opt-in token differs and must stay per-dispatcher.** Escalation uses `allow_split`; reground and merge use `allow_structural_remedy`. These two builder args are deliberately separate (see `_build_review_action_fn`'s signature and its `allow_structural_remedy` docstring). The helper must not collapse them.
- **`_dispatch_file_check_create` inverts the rule** — under `state.yes_to_all` it sets `choice = "c"` and auto-applies the `files:`→`creates:` move, the opposite of the three bridges. It has no bridge and no opt-in token, so it stays out of the helper.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add the gate helper beside `WalkState` and step 2's `apply_structural_outcome`.
  - `plan_tool/cli/review_actions.py` — replace the three hand-written gate expressions in `_dispatch_structural_escalation`, `_dispatch_reground_remedy`, and `_dispatch_merge_remedy` with calls to the helper; add a one-line note in `_dispatch_file_check_create` on why it is excluded.
  - `tests/test_review_walk.py` — add a direct unit test of the gate helper.
  - `tests/cli/test_review_actions.py` — the existing gate characterization tests are the pass-unchanged gate; extend only if a call site needs a new assertion.

## Implementation

**Add one tiny helper to `plan_tool/review_walk.py`.** It takes the dispatcher's already-chosen opt-in token and the `WalkState`, and returns the gated bool. One likely shape:

```python
def structural_apply_allowed(opt_in: bool, state: WalkState) -> bool:
    """True only when the caller opted in AND no blanket fast-forward is active.

    The three bridge dispatchers (escalate/reground/merge) share this: a
    ``-y`` fast-forward must never auto-confirm an irreversible structure
    mutation. See docs — the bridge still owns the TTY confirm.
    """
    return opt_in and not state.yes_to_all
```

- **Keep it a cycle-free leaf.** `review_walk.py` is imported **by** `review_actions.py`, never the reverse, and must stay free of `plan_tool.cli` and orchestrator imports. The helper only reads `WalkState.yes_to_all` and a plain bool, so it adds no import — place it next to `WalkState` / `apply_structural_outcome`, not in `review_actions.py`.
- **Return a plain `bool`, not the truthy operand.** `opt_in and not state.yes_to_all` already returns `bool` when `opt_in` is a bool; the bridges receive real bools today (`allow_split`, `allow_structural_remedy` are typed `bool`), so behavior is unchanged. Don't return the raw operand from a non-bool input.

**Route the three call sites through it, changing nothing else:**

- `_dispatch_structural_escalation` — replace `allow_split=(allow_split and not state.yes_to_all)` in the `escalate_to_split(...)` call with `allow_split=structural_apply_allowed(allow_split, state)`. Leave `prompt_fn=None` as-is.
- `_dispatch_reground_remedy` — replace `allow_reground=allow_structural_remedy and not state.yes_to_all` in the `reground_bridge(...)` call with `allow_reground=structural_apply_allowed(allow_structural_remedy, state)`. Leave `yes=False` as-is.
- `_dispatch_merge_remedy` — replace `allow_merge=allow_structural_remedy and not state.yes_to_all` in the `merge_bridge(...)` call with `allow_merge=structural_apply_allowed(allow_structural_remedy, state)`. Leave `yes=False` as-is.

**Leave `_dispatch_file_check_create` out, and say why in one line.** Its `if state.yes_to_all: choice = "c"` branch is the inverted rule — auto-apply under fast-forward, not force-recommend-only. Add a short comment there (e.g. `# Inverts the bridges' fast-forward gate: -y auto-applies create; see structural_apply_allowed's docstring`) so a future reader doesn't "consolidate" it into the helper and flip its behavior.

**Constraints and gotchas that are not free to vary:**

- **The two opt-in tokens stay distinct.** `allow_split` (escalation) and `allow_structural_remedy` (reground/merge) are passed to the helper as its argument — the helper never picks between them. Folding them into the helper would erase a real per-lane difference.
- **The confirm seam stays per-dispatcher.** `prompt_fn=None` (escalation) and `yes=False` (reground/merge) are the bridges' own confirm knobs and are **not** part of the gate — the plan's must-preserve list keeps them per-dispatcher. Don't push them into the helper.
- **No behavior, message, or exit-code change.** Every gated bool the bridges receive must be identical to today for all combinations of the opt-in token and `yes_to_all`. The existing gate tests are the proof.

## Tests

Reference existing tests as the characterization/pass-unchanged gate; add one direct helper test.

In `tests/cli/test_review_actions.py` (pass-unchanged — do not modify to make green):

- `test_escalation_yes_to_all_forces_recommend_only` — escalation passes `allow_split=False` to `escalate_to_split` when `yes_to_all=True`.
- `test_escalation_passes_proposer_and_allow_split` — escalation passes the real `allow_split=True` when not fast-forwarding.
- `test_granularity_split_yes_to_all_forces_recommend_only` — the `granularity-split` router branch also forces `allow_split=False` under `yes_to_all`.
- `test_opt_in_forced_off_under_yes_to_all` — reground passes `allow_reground=False` under `yes_to_all`.
- `test_opt_in_passed_through_when_allowed_and_not_fast_forward` — reground passes `allow_reground=True` when opted in and not fast-forwarding.
- `test_opt_in_defaults_off_and_ignores_allow_split` — reground stays `False` when only `allow_split` is on.
- `test_merge_opt_in_forced_off_under_yes_to_all` — merge passes `allow_merge=False` under `yes_to_all`.
- `test_merge_opt_in_passed_when_apply_structural_enabled` — merge passes `allow_merge=True` when opted in and not fast-forwarding.

In `tests/test_review_walk.py` (new):

- `test_structural_apply_allowed_true_when_opted_in_and_no_fast_forward` — returns `True` for `opt_in=True`, `WalkState(yes_to_all=False)`.
- `test_structural_apply_allowed_false_under_yes_to_all` — returns `False` for `opt_in=True`, `WalkState(yes_to_all=True)`.
- `test_structural_apply_allowed_false_when_not_opted_in` — returns `False` for `opt_in=False` regardless of `yes_to_all`.
- File-check exclusion stays pinned by `TestFileCheckCreateDispatch` in `tests/test_review_walk.py` — reference it, don't duplicate; its `yes_to_all` auto-create path must still assert `create` is picked (proving file-check was **not** routed through the force-recommend-only helper).

### Test-creation order (refactor step)

This is a **behavior-preserving refactor**. Order:

1. **First**, confirm the gate characterization tests above already pass on HEAD (they pin each dispatcher's gated-bool for both `yes_to_all` states). They are the safety net — if any is missing or thin for a call site you touch, add it **before** the extraction, asserting the exact gated bool passed to the bridge.
2. **Then** extract `structural_apply_allowed` and reroute the three dispatchers.
3. **Pass-unchanged gate:** the gate characterization tests in `tests/cli/test_review_actions.py` stay green **unmodified** after the extraction. The new `structural_apply_allowed` unit tests in `tests/test_review_walk.py` are the only additions.

## Acceptance criteria

- `plan_tool/review_walk.py` defines a shared gate helper (e.g. `structural_apply_allowed(opt_in, state)`) that returns `opt_in and not state.yes_to_all` as a `bool`, and imports nothing from `plan_tool.cli` or orchestrators.
- `_dispatch_structural_escalation`, `_dispatch_reground_remedy`, and `_dispatch_merge_remedy` each call that helper for their bridge's opt-in argument; none of the three still writes `... and not state.yes_to_all` inline.
- The two opt-in tokens stay distinct: escalation passes `allow_split` to the helper, reground and merge pass `allow_structural_remedy`.
- `_dispatch_file_check_create` still auto-applies `create` under `state.yes_to_all` and carries a one-line note that it is deliberately excluded from the gate helper.
- All gate characterization tests in `tests/cli/test_review_actions.py` listed above pass **unchanged**; the new `structural_apply_allowed` unit tests pass; the full suite stays green.
- No message text or exit-code change; the conftest autouse backend gate sees no real backend spawn.

## References

- `plan_tool/cli/review_actions.py` — the three bridge dispatchers whose duplicated `<token> and not state.yes_to_all` gate this step single-sources: `_dispatch_structural_escalation` (`allow_split`), `_dispatch_reground_remedy` and `_dispatch_merge_remedy` (`allow_structural_remedy`), plus `_dispatch_file_check_create`, the excluded inverted-rule case.
- `plan_tool/review_walk.py` — `WalkState` (the `yes_to_all` field the helper reads) and step 2's `apply_structural_outcome` kernel, beside which the new gate helper is placed.

## Deferred

- `_dispatch_file_check_create` routing through the gate helper — excluded on purpose; it has no bridge and inverts the `yes_to_all` rule.
- The shared `WalkState` outcome kernel (`apply_structural_outcome`) — owned by step 2; this step only adds the gate beside it and does not change it.
- The confirm seam (`prompt_fn=None` / `yes=False`) and the per-dispatcher glue (bridge call, target-id source, directive/kind guard, staleness guard, session short-circuit) — stay per-dispatcher per the plan's must-preserve list; not folded into the gate.
- Any behavior change tempted while refactoring (a dispatcher that "should" gate differently) — a BACKLOG #70 / #93 finding, not this consolidation.
