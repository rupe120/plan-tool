# Step 4 — Re-point detail.py Phase B split sequence at `escalate_to_split` (behavior-preserving)

## Summary

- **Replaces the inline split engine sequence inside `generate_detail`'s Phase B block** (`plan_tool/detail.py`) with a single call to step 3's `launcher.escalate_to_split` bridge, once per flagged mixed step. The per-target sequence (`_split_is_safe` → `_propose_step_split` → `_confirm_split` → `_apply_step_split` → `_migrate_downstream_details_after_split` → `write_plan`) moves behind the bridge; the loop keeps only the outcome-to-message mapping and the `split_target_ids` bookkeeping the post-loop half re-authoring already depends on.
- **Behavior-preserving refactor.** Interactive `detail --split` (TTY + `allow_split=True` + operator confirm) still splits each mixed step in one pass, renumbers the plan on disk, and re-authors both detail-less halves — same observable result as today. The outer guard `if allow_split and mixed_steps and sys.stdin.isatty():` and the entire `if split_target_ids:` half re-authoring + summary-rebuild block are kept unchanged.
- **Key design decision:** keep the outer interactive+opt-in guard rather than dropping it and letting the bridge decide apply-vs-recommend. Dropping the guard would make unattended `detail` emit split *recommendations* — a behavior change, deliberately left to a later step. Here the bridge is only ever entered on the apply path, so the net effect is identical.
- **On green:** the seven existing `TestInteractiveSplit` characterization tests pass unchanged, `generate_detail` calls `escalate_to_split` (not the inline create primitives) once per mixed step, and the create-side split primitives are no longer imported or called directly inside Phase B.

## Table of Contents

- [Why](#why) — what the inline duplication costs and why it folds behind one seam now
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the import swap, the loop-body substitution, the outcome mapping, what stays untouched
- [Tests](#tests) — the characterization gate plus the two delegation-pinning tests
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — pytest fixtures/markers and `sys.isatty` semantics
- [Deferred](#deferred) — the unattended-recommend wiring and the CreateError-message divergence

## Why

The step-split sequence lives in exactly two places after step 3 lands: inside `generate_detail`'s Phase B block, and inside `launcher.escalate_to_split` (step 3 lifted the Phase B sequence out exactly so the create/detail convergence loops and the review apply walk can reach it). Until detail's inline copy is removed, the split engine has two callers re-implementing the same `propose → safe → confirm → apply → migrate` order by hand — any future change to that order has to be made in both, and the convergence loops (step 5) reach the engine through a *different* path than `detail --split` does. This step routes detail's inline copy through one bridge so there is one place the engine is driven from, without changing what an operator running `detail --split` sees.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — extend the existing top-level `from plan_tool.launcher import apply_finding` to also import `escalate_to_split`; delete the body-local `from plan_tool.create import (CreateError, _apply_step_split, _propose_step_split)` inside the Phase B block; replace the per-target inline split sequence in the `if allow_split and mixed_steps and sys.stdin.isatty():` loop with one `escalate_to_split(...)` call plus outcome-to-message mapping. Keep the `if split_target_ids:` half re-authoring + summary-rebuild block unchanged.
  - `tests/test_detail.py` — add two delegation-pinning tests to the existing `TestInteractiveSplit` class; leave its seven characterization tests untouched.

## Implementation

### `plan_tool/detail.py`

**Import swap (top of module).**

- **Extend the existing top-level launcher import** — change `from plan_tool.launcher import apply_finding` to `from plan_tool.launcher import apply_finding, escalate_to_split`. This import sits under the comment block explaining the module-level (non-lazy) placement (`# Module-level import (vs. lazy) so tests can monkeypatch plan_tool.detail.apply_finding`). The same rationale covers `escalate_to_split`: tests monkeypatch `plan_tool.detail.escalate_to_split` to spy on the seam.
- **No cycle, do not body-localize.** `plan_tool/detail.py` already imports `apply_finding` from `plan_tool/launcher.py` at module top; `escalate_to_split` is the same direction, so it adds no cycle. `launcher.escalate_to_split` reaches back into detail via its own *body-local* `from plan_tool.detail import (_confirm_split, _migrate_downstream_details_after_split, _split_is_safe)` — that call-time import is what keeps the load graph a tree. Do not cite cycle-breaking for detail's top-level launcher import.
- **Delete the body-local `from plan_tool.create import (...)`** inside the Phase B block (the `# lazy: avoid create↔detail import cycle` import bringing in `CreateError`, `_apply_step_split`, `_propose_step_split`). After this step the Phase B block calls none of them directly — `escalate_to_split` owns those calls. Leave the two *other* body-local `from plan_tool.create import (...)` statements (in `split_step` and `merge_steps`) untouched; they are separate call sites that still drive the create primitives directly.

**Loop-body substitution (the `if allow_split and mixed_steps and sys.stdin.isatty():` block).**

- **Confirm the bridge contract at HEAD first.** Before consuming it, verify `plan_tool.launcher.escalate_to_split`'s exported name, signature (`plan_path`, `step_id`, `repo_root`, `invoker`, `allow_split`, `prompt_fn`), and the six-value `outcome` enum (`applied`/`unsafe`/`split-failed`/`proposal-unusable`/`recommended`/`step-missing`) plus `blocking_ids`/`recommendation` against step 3's landed code (`depends_on: 3`) — this body consumes a symbol an earlier step produces, so the consumption must be falsifiable against what actually shipped.
- **Keep the outer guard and the high→low sort unchanged** — `for target_id, _finding in sorted(mixed_steps, key=lambda t: t[0], reverse=True):`. Processing highest id first means an earlier split's renumbering (which only shifts ids at/after its target) never invalidates a not-yet-processed lower-id target, so the original captured `target_id` is still valid when passed to the bridge. This is the same invariant the inline loop relied on.
- **Drop the per-iteration `plan_now = parse_plan(plan_path)` + `step_by_id` resolve.** `escalate_to_split` re-parses the plan from disk on every call (step 3 contract), so it already sees the prior split's renumbering and resolves the target itself; a stale-id target returns `outcome="step-missing"`. Re-parsing in the loop too would be redundant.
- **Replace the whole inline body with one bridge call:**
  ```
  result = escalate_to_split(
      plan_path,
      step_id=target_id,
      repo_root=repo_root,
      invoker=invoker,
      allow_split=allow_split,
      prompt_fn=prompt_fn,
  )
  ```
  Pass the same `invoker` the inline `_propose_step_split` used (the split-proposer seam, `Callable[[str], str]`) and the same `prompt_fn` the inline `_confirm_split` used. `allow_split` is always `True` on this branch (the outer guard requires it) — pass it through rather than hardcoding, so the bridge's own gate stays the single source of the apply decision.
- **Map the outcome to the existing operator messages and to `split_target_ids`** (preserve today's console output and the post-loop trigger):
  - `"applied"` → `split_target_ids.add(target_id)` and emit the existing note `tool(f"step {target_id}: split into refactor + feature; re-authoring both halves", level="note")`.
  - `"unsafe"` → emit the existing warning, rebuilt from `result.blocking_ids`: `tool(f"step {target_id}: skipping auto-split — downstream step(s) {result.blocking_ids} have already run/started; restructure via re-plan if the split is still wanted", level="warning")`. The substring `skipping auto-split` must stay in the message — `test_unsafe_downstream_blocks_split` asserts it on stderr.
  - `"proposal-unusable"` → emit the existing note `tool(f"step {target_id}: split proposal was unusable; leaving the step as-is", level="note")`.
  - `"split-failed"` → emit the existing warning the inline `except CreateError` produced: `tool(f"step {target_id}: split failed; leaving as-is", level="warning")`. This preserves today's console output on a mid-apply `CreateError` — step 3 now surfaces that case as a distinct `"split-failed"` outcome rather than collapsing it into `"recommended"`, so the warning fires here as before.
  - `"recommended"` → no-op (no message, no `split_target_ids` change). On this interactive+opt-in branch the bridge returns `"recommended"` only when the operator *declines* the confirm — which the inline code handled as a silent `continue`. Do **not** surface `result.recommendation` here; folding it into `emit_detail_findings_summary` is an unattended-path behavior change owned by a later step (see Deferred).
  - `"step-missing"` → no-op. Matches the inline `except KeyError: continue` (a target already restructured away by an earlier split in the same loop).
- **`split_target_ids` stays a plain `set[int]`** seeded empty before the loop, exactly as today; only the `"applied"` arm adds to it.

**What stays untouched (the pass-unchanged region).**

- **The entire `if split_target_ids:` block** — half-id discovery (`[s.id for s in parse_plan(plan_path).steps if s.detail is None]`), the recursive `generate_detail(step_id=hid, allow_split=False, resume=False, ...)` re-authoring of each detail-less half, and the slug-keyed attribution rebuild (`written_keys`, `min_split`, the `results` filter/rebuild, the failed-half surfacing). `escalate_to_split` deliberately does *not* re-author the new halves — it leaves both with `detail is None` exactly as the inline `write_plan` did, so detail's caller-side re-authoring is still required and still correct. Do not move it into the bridge.
- **`return results`** and everything outside Phase B.

## Tests

All cases live in the existing `TestInteractiveSplit` class in `tests/test_detail.py` (docstring `"Phase B: --split offers a refactor→feature split for flagged steps."`). It drives `generate_detail(..., allow_split=..., prompt_fn=..., invoker=...)` end-to-end with `sys.stdin.isatty` monkeypatched and the invoker seam neutralized by `self._invoker()`.

Two new delegation-pinning tests (added with the refactor):

- `test_phase_b_delegates_to_escalate_split` — monkeypatch `plan_tool.detail.escalate_to_split` with a spy returning `outcome="applied"`; run `generate_detail` on the single-mixed-step fixture with `allow_split=True` + TTY; assert the spy was called once with `step_id` = the mixed step's id and kwargs `repo_root`, `invoker`, `allow_split=True`, `prompt_fn` matching what `generate_detail` received. Pins that Phase B routes through the bridge.
- `test_phase_b_no_inline_split_engine_calls` — rig `plan_tool.create._propose_step_split` and `plan_tool.create._apply_step_split` to raise; stub `plan_tool.detail.escalate_to_split` to a no-op returning `outcome="recommended"` (so `split_target_ids` stays empty and the half-authoring block never runs); run `generate_detail` with a mixed step + `allow_split=True` + TTY; assert it returns without raising and the bridge stub was called. Proves the create-side primitives are reached *only* through the bridge, never inline.

### Test-creation order (refactor step)

This is a behavior-preserving refactor. The characterization tests already exist in `TestInteractiveSplit` — confirm them green at HEAD **before** editing `plan_tool/detail.py`, then keep them green and unmodified after the substitution. They pin the behavior that must not change:

- `test_happy_path_splits_and_reauthors` — interactive split renumbers the plan (refactor+feature pair, downstream pushed to id 3, `depends_on` rewired to the feature half), every step resolves to a detail file on disk, and the original mixed file is archived not left active.
- `test_split_does_not_prompt_to_replace_existing_files` — the half re-authoring fires no "Replace existing file?" prompt and returns coherent unique-id results.
- `test_declined_split_leaves_plan_unchanged` — declining the confirm leaves the plan titles `["Mixed step", "Downstream"]` (no mutation).
- `test_without_flag_only_warns` — `allow_split=False` performs no split even on a TTY (the outer guard short-circuits).
- `test_multiple_splits_renumber_and_rewire` — two mixed steps processed high→low both split, ids renumber contiguously, and the downstream dependency follows the lower split to its feature half.
- `test_carried_downstream_reported_as_skip_not_write` — a downstream step carried through a renumber is reported as an idempotent skip (`"carried through split"` in `skipped_reason`), not a fresh write.
- `test_unsafe_downstream_blocks_split` — an unsafe gate (downstream already run/started) skips the split, emits `"skipping auto-split"` on stderr, and the proposer (rigged to raise) is never called.

**Pass-unchanged gate:** all seven above stay green, unmodified, after the restructuring. The two new delegation tests are additive; they assert the *mechanism* (one bridge call, no inline engine calls) the characterization tests cannot see.

## Acceptance criteria

- `escalate_to_split` is imported into `plan_tool/detail.py` from `plan_tool.launcher` at module top (beside `apply_finding`), and the Phase B block no longer imports `_propose_step_split` / `_apply_step_split` / `CreateError` from `plan_tool.create`.
- `generate_detail` Phase B calls `escalate_to_split` exactly once per flagged mixed step, with `step_id`, `repo_root`, `invoker`, `allow_split`, and `prompt_fn` forwarded.
- The seven `TestInteractiveSplit` characterization tests pass unchanged.
- An interactive `detail --split` run on a mixed step still produces: the renumbered plan on disk, both halves re-authored to detail files, and the original mixed detail archived (`test_happy_path_splits_and_reauthors` green).
- An unsafe downstream still prints a message containing `skipping auto-split` and never calls the proposer (`test_unsafe_downstream_blocks_split` green).
- `grep -n "_apply_step_split\|_propose_step_split" plan_tool/detail.py` shows no occurrence inside the `if allow_split and mixed_steps and sys.stdin.isatty():` Phase B loop (only the unrelated `split_step` / `merge_steps` call sites remain).

## References

- [How to use fixtures — pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html) — `tmp_path` plan fixtures and `monkeypatch` overrides used to spy on `escalate_to_split` and neutralize the invoker seam so the new tests never spawn real `claude`.
- [sys — System-specific parameters and functions (Python 3 docs)](https://docs.python.org/3/library/sys.html) — `sys.stdin.isatty()` semantics behind the outer Phase B guard the tests monkeypatch to `True`.

## Deferred

- **Surfacing the bridge's `recommendation` from detail.** Folding `escalate_to_split`'s returned `structural-split` `Recommendation` into `emit_detail_findings_summary` (so an unattended `detail` run reports a split recommendation instead of doing nothing) is a behavior change, not preserved here. This step keeps the `"recommended"` outcome a silent no-op to match today's decline behavior; the unattended-recommend wiring is owned by the convergence-loop work (step 5 routes structural findings in `create`; the analogous detail-summary fold tracks alongside it).
- **The CreateError "split failed" warning is preserved.** Step 3's `escalate_to_split` surfaces a mid-apply `CreateError` (bad dependency graph) as a distinct `outcome="split-failed"` rather than re-raising, so this step maps it to the `"step {id}: split failed; leaving as-is"` warning (above), keeping today's console output on that path. The original inline message embedded the exception text (`({exc})`); the bridge returns only the outcome label, so the exception detail is dropped from the warning — an accepted, narrow divergence on an extremely rare path.
- **Dropping the outer interactive guard.** Letting unattended `detail` enter the bridge so `escalate_to_split` itself decides apply-vs-recommend is intentionally not done here — it would change unattended behavior. Kept for the step that wires the convergence-loop routing.
