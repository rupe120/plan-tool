> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Extract a shared outcome-application kernel in review_walk.py and route the four structural dispatchers through it

## Summary

Pull the repeated `WalkState` side-effect tail — set `apply_skip`, set `halt_requested`+`halt_apply_landed`, add `rec.id` to `applied_structural_finding_ids` — out of the four structural dispatchers in `plan_tool/cli/review_actions.py` (`_dispatch_structural_escalation`, `_dispatch_reground_remedy`, `_dispatch_merge_remedy`, `_dispatch_file_check_create`) and into one small kernel in `plan_tool/review_walk.py`. Each dispatcher keeps its own outcome branching and message strings but, instead of hand-setting those fields per outcome, describes the outcome's disposition (resolved-vs-skip, record-id, halt) and calls the kernel to apply it. The key design decision: the kernel owns only the fields **all four dispatchers share**; the drift `refresh_snapshot` call (unique to escalation-applied), the `not state.yes_to_all` gates, and the `_saved_directive_is_stale` guards stay in the dispatchers. This is a behavior-preserving refactor — on green, every outcome leaves `WalkState` exactly as it does today, and Step 1's characterization tests pass unchanged.

## Table of Contents

- [Why](#why) — why the tail duplication is a bug hazard worth removing now
- [Input](#input) — the per-outcome `WalkState` map this step must preserve
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files and two test files
- [Implementation](#implementation) — the kernel shape, what it owns, and what stays in each caller
- [Tests](#tests) — kernel unit tests plus the Step 1 pins as the pass-unchanged gate
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer/CI can run
- [References](#references) — dataclasses, enum, and the refactoring discipline
- [Deferred](#deferred) — effects and callers left out of the kernel on purpose

## Why

The four structural dispatchers each re-implement the same `WalkState` tail by hand, one `state.apply_skip = True` / `state.halt_requested = True; state.halt_apply_landed = True` / `state.applied_structural_finding_ids.add(rec.id)` line at a time, spread across roughly a dozen outcome branches. The map is asymmetric — escalation-applied never records `rec.id` and halts only under `halt_on_applied`; reground-applied records the id but never halts; merge-applied records the id and always halts — so a copy-paste while editing one dispatcher can silently give it a sibling's tail. That is exactly the bug class fix `5d4fe1b` patched: a `granularity-split` branch that reached escalation without the `apply_skip` tail its siblings had, recording an un-split finding as `applied` and pre-skipping the required split forever. One kernel with an explicit per-outcome descriptor makes the tail a single reviewable place instead of a dozen, so the asymmetry is stated once and can't drift branch-by-branch.

## Input

This step consumes the **current observable behavior** the Step 1 characterization tests pin (step 1 produces the complete per-outcome `WalkState` pins in `tests/cli/test_review_actions.py`). The kernel must reproduce that map field-for-field. The kernel-owned fields and their current per-outcome values:

- **`apply_skip`** — set `True` on every non-resolved outcome (walk records `skip`); left at the walk's reset default `False` on a resolved/applied outcome (walk records `applied`). Genuine-resolved paths that leave it `False`: escalation-applied, reground-applied, reground `noop`, merge-applied, and file-check create / "already declared".
- **`halt_requested` + `halt_apply_landed`** — set together to `True` only by merge-applied (always) and escalation-applied under `halt_on_applied=True`. Reground, file-check, and escalation under the default `halt_on_applied=False` never touch them.
- **`applied_structural_finding_ids`** — reground-applied and merge-applied add `rec.id`; escalation and file-check never add.

Two effects sit **outside** the kernel and must not change:

- **drift `refresh_snapshot`** — called only by escalation-applied, only when `reconcile_scope_guard` and its `iter_lock` are both present.
- **`apply_failed`** — never set by any of the four (it belongs to `_dispatch_apply_finding`'s error path). Stays `False` throughout.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/review_walk.py` — add the kernel: a small frozen descriptor (recommended name `StructuralOutcomeEffects`) plus the applier function (recommended name `apply_structural_outcome`). No change to `WalkState`, the walk loop, or `_auto_apply`.
  - `plan_tool/cli/review_actions.py` — replace the hand-set tail lines in all four dispatchers with descriptor-building + one kernel call per outcome. Keep every message string, gate, guard, and branch order.
  - `tests/test_review_walk.py` — add direct unit tests for the kernel (see Tests).
  - `tests/cli/test_review_actions.py` — the pass-unchanged gate (Step 1's pins). Edit only if a new kernel-routing seam genuinely needs coverage Step 1 didn't add; prefer leaving it untouched.

## Implementation

**Foundational logic:** "apply the shared `WalkState` side-effect tail for one structural-dispatch outcome." Today that logic is duplicated across the four dispatchers built by `plan_tool/cli/review_actions.py`'s `_build_review_action_fn`. This step makes it one function.

**Add the kernel to `plan_tool/review_walk.py`.** Put it beside `WalkState` so both live in the module `review_actions` already imports from (`from plan_tool.review_walk import WalkState`). Recommended shape:

- A frozen descriptor — one way: `@dataclass(frozen=True)` with three fields — `resolved: bool`, `record_finding_id: bool = False`, `halt: bool = False`. **`resolved` is the plan Architecture's "terminal-applied?" dimension** (same concept, one name): `resolved=True` means the outcome mutated/settled the plan so the walk should record `applied` (leave `apply_skip=False`); `resolved=False` means set `apply_skip` (walk records `skip`). The genuine-noop "resolved" paths (reground `noop`, file-check "already declared") are `resolved=True` — they settled the finding even though nothing was written.
- An applier `apply_structural_outcome(state: WalkState, rec, effects) -> None` that:
  - sets `state.apply_skip = True` when `not effects.resolved` (and never sets it back to `False` — the walk resets it before each action call, so the kernel only sets `True`);
  - adds `rec.id` to `state.applied_structural_finding_ids` when `effects.record_finding_id`;
  - sets `state.halt_requested = True` and `state.halt_apply_landed = True` together when `effects.halt`.
- The applier touches **only** those three areas and never reads or writes `apply_failed`, `pending_feedback`, `yes_to_all`, or the other halt fields.

**Alternative rejected:** modeling outcomes as a single `enum`. The outcomes don't map one-to-one to a fixed enum because halt varies within escalation-applied (`halt_on_applied` decides it at the call site), so a boolean descriptor states each dimension honestly rather than minting near-duplicate enum members. The `enum` reference below is for background on the tradeoff, not a mandate to use one.

**Route the four dispatchers through it in `plan_tool/cli/review_actions.py`.** For each outcome branch, replace the inline field-setting with a descriptor + `apply_structural_outcome(state, rec, ...)` call, then return the existing message string unchanged. Call the kernel uniformly — including on plain resolved outcomes where the descriptor sets nothing — so every one of the four dispatchers visibly routes its tail through the one place.

- **`_dispatch_structural_escalation`** — applied → `resolved=True`, `halt=halt_on_applied`, `record_finding_id=False`; keep the drift `refresh_snapshot` block **inline in this dispatcher** (before or as part of the applied branch), guarded by `reconcile_scope_guard`/`iter_lock` as today. The plan-level-verdict (`rec.step_id is None`), recommended, unsafe, proposal-unusable, and step-missing branches → `resolved=False`.
- **`_dispatch_reground_remedy`** — applied → `resolved=True`, `record_finding_id=True`; `noop` → `resolved=True` (no record); recommended/unsafe/step-missing and the directive-none/stale guards → `resolved=False`. Keep the early `rec.id in state.applied_structural_finding_ids` session-signal return and the `_saved_directive_is_stale` guard in the dispatcher — they are policy, not tail.
- **`_dispatch_merge_remedy`** — applied → `resolved=True`, `record_finding_id=True`, `halt=True`; recommended/unsafe/invalid and the directive-none/stale guards → `resolved=False`. Keep the session-signal return and the `apply_error` message branch (still an applied outcome) in the dispatcher.
- **`_dispatch_file_check_create`** — create/move and "already declared" → `resolved=True`; fix/typo, parse error, and step-not-found → `resolved=False`. The defensive `path is None` early return keeps its current no-set behavior. Leave the `parse_plan`/`write_plan` plan mutation in the dispatcher — only the tail moves.

**Constraints that are not free to vary:**

- **Behavior-preserving.** Every outcome's post-call `WalkState` and returned string must match HEAD exactly. Step 1's pins are the contract.
- **Import direction stays acyclic.** `review_actions` imports from `review_walk`, never the reverse. Do **not** import `plan_tool.drift_detection` into `review_walk` — keeping `refresh_snapshot` inline in the escalation dispatcher preserves that. (If you instead thread drift refresh through the kernel, pass it as a caller-supplied callback so `review_walk` gains no new import; the recommended path avoids this entirely.)
- **Scope the kernel to the four structural dispatchers only.** Do not sweep in the other tail-mutating sites: `_dispatch_apply_finding`'s pre/post drift-halt path (which sets `halt_apply_landed=False` for a pre-apply skip and `apply_failed` on error) and the command-local callbacks in `plan_tool/cli/completeness_cmd.py` and `plan_tool/cli/data_contract_cmd.py` that set `apply_skip`. Their semantics differ; folding them in would change behavior.
- **Router branch order unchanged.** `action(rec)` keeps `split_escalation_target` before `should_apply_as_finding`, and the merge-vs-reground split by directive kind, exactly as today.

## Tests

### Test-creation order (refactor step)

This is a **behavior-preserving refactor**. The characterization tests that pin the four dispatchers' full per-outcome `WalkState` were written **first, in Step 1**, in `tests/cli/test_review_actions.py` (the classes `TestStructuralEscalation`, `TestSplitEscalationDispatch`, `TestRegroundRemedyDispatch`, `TestMergeRemedyDispatch`, plus a file-check `WalkState`/`apply_skip` block covering all five file-check outcomes). The file-check **plan-mutation** (`files:`→`creates:`) assertions remain in `tests/test_review_walk.py:TestFileCheckCreateDispatch` and are referenced, not moved — the file-check `WalkState` pins this refactor must preserve live in `test_review_actions.py` with the other three dispatchers. **Pass-unchanged gate:** those Step 1 tests must stay green, **unmodified**, after this extraction. If routing a dispatcher through the kernel forces an edit to a Step 1 assertion, the extraction changed behavior and is wrong.

New tests to add in `tests/test_review_walk.py` (direct kernel unit tests — the kernel is a public function on `review_walk`, so pin it directly for the boundaries the dispatcher-level tests exercise only indirectly):

- `test_kernel_skip_sets_apply_skip` — `resolved=False` sets `state.apply_skip=True`, leaves halt/record untouched.
- `test_kernel_resolved_sets_nothing` — `resolved=True` with no other flags leaves `apply_skip`, halt fields, and `applied_structural_finding_ids` at defaults.
- `test_kernel_record_finding_id_adds_rec_id` — `record_finding_id=True` adds `rec.id` to the set; a second call with the same rec is idempotent (set semantics).
- `test_kernel_halt_sets_both_halt_fields` — `halt=True` sets `halt_requested` and `halt_apply_landed` together.
- `test_kernel_never_touches_apply_failed` — no combination of flags sets `apply_failed`.
- `test_kernel_does_not_reset_apply_skip_to_false` — a `resolved=True` call after `apply_skip` was pre-set stays `True` (the kernel only sets `True`, the walk owns the reset).

## Acceptance criteria

- `plan_tool/review_walk.py` exposes the kernel function and descriptor; `plan_tool/cli/review_actions.py` imports and calls them from all four structural dispatchers.
- No `state.apply_skip = True`, `state.halt_requested = True`/`state.halt_apply_landed = True`, or `state.applied_structural_finding_ids.add(...)` line remains inline in the four structural dispatchers (each goes through `apply_structural_outcome`). The drift `refresh_snapshot` call still lives in `_dispatch_structural_escalation`.
- Every Step 1 characterization test in `tests/cli/test_review_actions.py` passes **without edits**.
- The new kernel unit tests in `tests/test_review_walk.py` pass.
- `uv run pytest tests/test_review_walk.py tests/cli/test_review_actions.py -q` is green.
- `apply_failed` is never set by the kernel or the four dispatchers (grep confirms no assignment in the routed branches).
- `plan_tool/review_walk.py` gains no import of `plan_tool.drift_detection` or `plan_tool.cli`.

## References

- [dataclasses — Data Classes (Python Standard Library)](https://docs.python.org/3/library/dataclasses.html) — For the small frozen `StructuralOutcomeEffects` descriptor (`frozen=True`, defaulted fields).
- [enum — Support for enumerations (Python Standard Library)](https://docs.python.org/3/library/enum.html) — Background for the rejected enum-per-outcome alternative; read to confirm why booleans model the varying-halt dimension better here.
- [Refactoring Catalog — Extract Function (Martin Fowler)](https://refactoring.com/catalog/extractFunction.html) — The behavior-preserving discipline this step follows: pin first (Step 1), extract, keep the pins green.

## Deferred

- **Drift `refresh_snapshot` in the kernel** — left inline in `_dispatch_structural_escalation`. It fires from one dispatcher, one outcome, and needs the reconcile guard plus a `drift_detection` import; folding it into `review_walk` would over-generalize and risk an import cycle. Step 1's pins still guard its call/no-call across outcomes.
- **`apply_failed`** — belongs to `_dispatch_apply_finding`'s error path, not the four structural dispatchers; out of the kernel's scope.
- **`_dispatch_apply_finding`'s drift-halt tail and the `completeness_cmd.py` / `data_contract_cmd.py` command-local `apply_skip` sites** — different semantics (pre-apply skip sets `halt_apply_landed=False`); not routed through this kernel.
- **The `not state.yes_to_all` gates, `_saved_directive_is_stale` guards, and session-signal (`rec.id in applied_structural_finding_ids`) early returns** — these stay per-dispatcher as policy; the kernel owns only the mechanical tail.
