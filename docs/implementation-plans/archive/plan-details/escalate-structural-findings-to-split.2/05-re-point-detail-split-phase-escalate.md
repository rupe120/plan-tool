> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Re-point `detail --split` Phase B at `escalate_to_split` (behavior-preserving)

## Summary

- Replace the inline split sequence inside `plan_tool/detail.py:generate_detail`'s Phase B with a single call to `plan_tool/launcher.py:escalate_to_split` (added in step 4) per flagged mixed step. Same files only: `plan_tool/detail.py` and `tests/test_detail.py`.
- This is a **behavior-preserving refactor**. The seven existing `TestInteractiveSplit` integration tests must stay green unmodified — they now drive the bridge end-to-end instead of the inline block, and `escalate_to_split` mirrors that block exactly.
- Key boundary with step 6: **keep** the outer `if allow_split and mixed_steps and sys.stdin.isatty():` guard so the bridge is only ever entered on the interactive opt-in path. Dropping that guard (so the bridge decides apply-vs-recommend on unattended runs) is step 6's feature, not this step.
- Map each `EscalateResult.outcome` back to Phase B's existing observable: `"unsafe"` → the `skipping auto-split` warning (using `result.blocking`), `"proposal-unusable"` → the unusable-proposal note, `"applied"` → add to `split_target_ids` + the re-author note, `"recommended"`/`"step-missing"` → silent no-op (matching the inline `continue` paths).
- On green: a TTY `--split` run still splits a flagged mixed step into a refactor+feature pair and re-authors both halves; Phase B reaches the split engine only through `escalate_to_split`, never the inline `_apply_step_split`/`_propose_step_split` primitives.

## Table of Contents

- [Summary](#summary) — what this step does and the observable result
- [Why](#why) — the duplicated inline split flow this consolidates onto the bridge
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the import swap, the outcome→observable map, the guard kept
- [Tests](#tests) — characterization set plus the delegation/no-inline guards
- [Test-creation order (refactor step)](#test-creation-order-refactor-step) — pin behavior before touching code
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — what steps 6 and 7 own, plus the accepted rare-path divergence

## Why

- The gate→propose→confirm→apply→migrate→write split sequence lives today as an inline block inside `plan_tool/detail.py:generate_detail`'s Phase B and nowhere else. Step 4 lifted that exact sequence into one reusable seam, `plan_tool/launcher.py:escalate_to_split`. Leaving Phase B on its own copy means two implementations of the same ordering and safety invariants can drift the moment either changes.
- Re-pointing Phase B at the bridge makes `escalate_to_split` the single path to the split engine for `detail`, and is the prerequisite for step 6 (the unattended recommendation surface) and step 7 (the in-loop trigger-2 contract), which both build on a Phase B that already delegates. This step ships no new behavior — it consolidates onto the seam step 4 built.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — in `generate_detail`'s Phase B: add `escalate_to_split` to the existing top-level `from plan_tool.launcher import apply_finding`; delete the Phase-B body-local `from plan_tool.create import (CreateError, _apply_step_split, _propose_step_split)`; replace the per-iteration `parse_plan`/`step_by_id`/`_split_is_safe`/`_propose_step_split`/`_confirm_split`/`_apply_step_split`/`_migrate_downstream_details_after_split`/`write_plan` body with one `escalate_to_split(...)` call and an outcome→observable switch. Leave the `if split_target_ids:` half-reauthoring/rebuild block unchanged.
  - `tests/test_detail.py` — add a delegation test and a no-inline-engine guard to `TestInteractiveSplit`; the seven existing tests in that class stay unchanged.

## Implementation

**Preflight — confirm the step-4 export at HEAD before re-pointing.** This step consumes `escalate_to_split` and `EscalateResult` from step 4. Before editing Phase B, grep `plan_tool/launcher.py` to confirm the symbols exist and that the exported signature (`plan_path`, `step_id=`, `repo_root=`, `invoker=`, `allow_split=`, `prompt_fn=`) and the `EscalateResult.outcome` set (`"applied"`/`"recommended"`/`"unsafe"`/`"proposal-unusable"`/`"step-missing"` + the `blocking`/`recommendation`/`target_id` fields) match what the outcome→observable switch below reads. If they diverge from step 4's contract, reconcile against `04-escalate-split-bridge-seam-safe-gate.md` before proceeding rather than coding against the stale shape here.

### `plan_tool/detail.py`

**Imports.**

- **Add `escalate_to_split` to the existing top-level launcher import.** Change `from plan_tool.launcher import apply_finding` to also pull `escalate_to_split` (and `EscalateResult` if you annotate the returned value). `detail → launcher` at module top already exists and is safe (`launcher` imports `detail` only body-locally, inside `escalate_to_split`), so this stays a top-level import — do not body-localize it. A top-level import also keeps `plan_tool.detail.escalate_to_split` a monkeypatchable module attribute for the delegation test.
- **Delete the Phase-B body-local create import.** Remove `from plan_tool.create import (CreateError, _apply_step_split, _propose_step_split)` from inside the Phase-B guard. Those names are no longer referenced in Phase B — `escalate_to_split` owns them now.
  - **Do not touch `split_step`'s own body-local create import.** `plan_tool/detail.py:split_step` has its own independent `from plan_tool.create import (...)` and still calls `_split_is_safe`/`_apply_step_split`/`_migrate_downstream_details_after_split` directly. Those detail-module helpers stay defined and used; only Phase B stops calling them inline.

**Phase B body — the re-point.** Inside the unchanged `if allow_split and mixed_steps and sys.stdin.isatty():` guard, keep `split_target_ids: set[int] = set()` and the high→low loop header `for target_id, _finding in sorted(mixed_steps, key=lambda t: t[0], reverse=True):`. Replace the loop body with:

- **One bridge call per target:**
  ```python
  result = escalate_to_split(
      plan_path,
      step_id=target_id,
      repo_root=repo_root,
      invoker=invoker,
      allow_split=True,
      prompt_fn=prompt_fn,
  )
  ```
  - Pass `allow_split=True` literally — the outer guard already proved the operator opted in, so the bridge's recommend-only short-circuit (`if not allow_split`) is never hit on this path.
  - Pass `invoker` (the split-proposer seam, `Callable[[str], str]`) and `prompt_fn` (the interactive confirm) straight through — same arguments the inline `_propose_step_split`/`_confirm_split` received.
  - **Drop the per-iteration `parse_plan(plan_path)` + `step_by_id(target_id)` resolve.** The bridge re-parses from disk and resolves the target itself; a stale id returns `outcome="step-missing"`. Keeping a redundant in-loop re-parse here would duplicate the bridge's first two steps.

- **Switch on `result.outcome`, mapping each to the inline code's prior observable:**
  - `"unsafe"` → emit the existing warning naming the blocking ids, then `continue`:
    ```python
    tool(
        f"step {target_id}: skipping auto-split — downstream "
        f"step(s) {result.blocking} have already run/started; "
        "restructure via re-plan if the split is still wanted",
        level="warning",
    )
    ```
    Read the ids from `result.blocking` (populated only on `"unsafe"`), matching the inline `blocking` local.
  - `"proposal-unusable"` → emit the existing note, then `continue`:
    ```python
    tool(
        f"step {target_id}: split proposal was unusable; "
        "leaving the step as-is",
        level="note",
    )
    ```
  - `"applied"` → `split_target_ids.add(target_id)` and emit the existing re-author note:
    ```python
    tool(
        f"step {target_id}: split into refactor + feature; "
        "re-authoring both halves",
        level="note",
    )
    ```
  - `"recommended"` and `"step-missing"` → **silent no-op** (`continue`). These match the inline `continue` paths: a declined `_confirm_split` (`"recommended"`) and a `KeyError` on a renumbered-away id (`"step-missing"`) both produced no output before. The bridge's `result.recommendation` is **ignored here** — surfacing it on the unattended path is step 6's job, and on this interactive-only path the operator just declined.

  Order the branches so the two early `continue` arms (`"unsafe"`, `"proposal-unusable"`) precede the `"applied"` arm; let `"recommended"`/`"step-missing"` fall through to a trailing `continue`.

- **Leave the high→low sort in the caller.** Processing highest id first guarantees an earlier split never renumbers a not-yet-processed lower target, so the originally-captured `target_id` stays valid when handed to the bridge. Do not delete or reorder this — the bridge re-parses but trusts the id the caller passes.

- **Keep the entire `if split_target_ids:` block unchanged** — the `half_ids` discovery (`[s.id for s in parse_plan(plan_path).steps if s.detail is None]`), the recursive `generate_detail(..., allow_split=False, resume=False)` half-authoring, the slug-keyed `written_keys` attribution, and the `min_split` rebuild of `results`. `escalate_to_split` writes the split to disk and leaves both new halves with `detail is None`, exactly as the inline `write_plan` did, so this block consumes identical on-disk state.

**Accepted divergence (rare path).** The inline `except CreateError` arm emitted `step {target_id}: split failed ({exc}); leaving as-is` and continued. `escalate_to_split` degrades a mid-apply `CreateError` to `outcome="recommended"` instead, so that warning no longer fires — the target is silently skipped. This divergence is inherited from step 4's bridge design (its Deferred names it) and is acceptable: the safe-gate rules out the common unsafe cases first, the path is rare, and no existing `TestInteractiveSplit` test forces a mid-apply `CreateError`, so none regress.

## Tests

All in `tests/test_detail.py`, class `TestInteractiveSplit` (already `@pytest.mark.integration`). The seven existing tests are the characterization set and stay unchanged; add two new guards.

Existing characterization tests (must stay green, unmodified — they now exercise the bridge):
- `test_happy_path_splits_and_reauthors` — a TTY `--split` run splits step 1 into a refactor+feature pair, repoints downstream `depends_on`, and every step resolves to a detail file on disk.
- `test_split_does_not_prompt_to_replace_existing_files` — half re-authoring targets only the detail-less new steps; no "Replace" prompt fires.
- `test_declined_split_leaves_plan_unchanged` — `prompt_fn` returns `"n"`; plan titles unchanged (bridge returns `"recommended"`, no write).
- `test_without_flag_only_warns` — `allow_split=False`; the outer guard is not entered, plan unchanged.
- `test_multiple_splits_renumber_and_rewire` — two mixed steps split high→low; the bridge re-parses each call and sees the prior split's renumbering; downstream `depends_on` follows.
- `test_carried_downstream_reported_as_skip_not_write` — a `--step 1` split renumbers prior-run downstream; they report as carried-through skips, not fresh writes.
- `test_unsafe_downstream_blocks_split` — a `current` target makes `_split_is_safe` fail; the bridge returns `"unsafe"` before any propose, the caller prints `skipping auto-split`, and the proposer (rigged to raise) is never called.

New tests added with this refactor:
- `test_phase_b_delegates_to_escalate_to_split` — monkeypatch `plan_tool.detail.escalate_to_split` to a spy returning `EscalateResult(outcome="applied", target_id=...)`; assert it is called once per flagged mixed target with `step_id=target_id`, `allow_split=True`, and `prompt_fn`/`invoker` forwarded.
- `test_phase_b_no_inline_engine_calls` — with `escalate_to_split` stubbed, rig `plan_tool.create._apply_step_split` and `_propose_step_split` to raise (or spy for zero calls); drive a flagged-mixed-step run and assert the stub bridge is called while the inline primitives are never invoked — proving Phase B reaches the split engine only through the bridge.

### Test-creation order (refactor step)

This is a **refactor** step — behavior-preserving. Pin behavior before touching `generate_detail`:

1. **Confirm the seven `TestInteractiveSplit` tests are green against HEAD first.** They already characterize the inline Phase B (happy split, declined, no-flag, multi-split renumber, carried-downstream skip, unsafe-block). They are the safety net — do not modify them.
2. Re-point Phase B at `escalate_to_split` and delete the body-local create import.
3. **Pass-unchanged gate:** all seven characterization tests must stay green *unmodified* after the re-point. If any needs editing to pass, the re-point changed observable behavior and is wrong (except the documented rare-path `CreateError` warning, which no test exercises).
4. Add `test_phase_b_delegates_to_escalate_to_split` and `test_phase_b_no_inline_engine_calls` to lock the consolidation — a positive "bridge is called" test plus the negative "old inline primitives are not called directly" guard.

## Acceptance criteria

- `plan_tool/detail.py:generate_detail`'s Phase B calls `escalate_to_split(plan_path, step_id=target_id, repo_root=..., invoker=..., allow_split=True, prompt_fn=...)` once per flagged mixed step and no longer calls `_propose_step_split`/`_apply_step_split` inline.
- The Phase-B body-local `from plan_tool.create import (CreateError, _apply_step_split, _propose_step_split)` is removed; `split_step`'s own create import is untouched.
- The outer `if allow_split and mixed_steps and sys.stdin.isatty():` guard and the high→low `sorted(..., reverse=True)` loop order are unchanged.
- `escalate_to_split` is added to the top-level `from plan_tool.launcher import apply_finding`; `plan_tool.detail.escalate_to_split` is monkeypatchable.
- `result.outcome` maps to: `"unsafe"` → `skipping auto-split` warning with `result.blocking`; `"proposal-unusable"` → unusable-proposal note; `"applied"` → `split_target_ids.add` + re-author note; `"recommended"`/`"step-missing"` → silent continue.
- The seven existing `TestInteractiveSplit` tests pass unmodified; the two new delegation/no-inline tests pass.
- `uv run pytest -m integration tests/test_detail.py -q` is green.

## References

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — patching `plan_tool.detail.escalate_to_split` for the delegation test and rigging the inline create primitives to raise for the no-inline guard.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — `@pytest.mark.integration`, `tmp_path`, and the integration-tier conventions `TestInteractiveSplit` follows.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `EscalateResult`'s `outcome`/`blocking` fields the Phase-B switch reads.

## Deferred

- **Dropping the `allow_split and isatty()` warning-only guard + the post-Phase-B recommendation surface** — step 6. Once the guard is gone, Phase B passes `allow_split` through and the bridge decides apply-vs-recommend on unattended runs; surfacing `result.recommendation` is that step's work, not this one's.
- **The in-loop trigger-2 (`BLOCKED-STRUCTURAL`) renumbering contract** — step 7. This step touches only Phase B, which runs *after* the per-step convergence loop closes; the inside-the-loop split path is a separate, harder step.
- **The dropped `split failed (...)` rare-path warning** — `escalate_to_split` degrades a mid-apply `CreateError` to `"recommended"` (silent skip here) rather than re-raising with the inline warning. Accepted divergence on a rare path, inherited from step 4; no covering test in `TestInteractiveSplit`.
