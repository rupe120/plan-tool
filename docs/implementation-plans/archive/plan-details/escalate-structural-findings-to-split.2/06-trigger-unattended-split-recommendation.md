> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Surface a split recommendation on unattended `detail` runs (drop the Phase-B opt-in/TTY guard)

## Summary

- Replace Phase B's `if allow_split and mixed_steps and sys.stdin.isatty():` guard in `plan_tool/detail.py:generate_detail` with a plain `if mixed_steps:`, so every flagged mixed step now enters `plan_tool/launcher.py:escalate_to_split` — including the default (no `--split`) and non-TTY/CI runs that the old guard skipped entirely.
- The apply-vs-recommend decision moves fully into the bridge: `escalate_to_split` still mutates only on the safe + `allow_split` + interactive-confirm path, and recommends on every other path. The guard no longer enforces "never unattended" — the bridge does.
- Collect each `outcome == "recommended"` result's `recommendation` into a `structural_recs` list during the Phase-B loop, then emit them once **after** the loop (and after the half-reauthoring block) through a new private helper `_emit_split_recommendations`, because the per-step convergence loop's in-loop `emit_detail_findings_summary` calls already fired before Phase B and can't carry these.
- Scope is `plan_tool/detail.py` + `tests/test_detail.py` only. On green: a default `detail` run over a mixed step prints a `structural-split` recommendation pointing at `plan-tool split` (no plan mutation, no Claude spent), the nine existing `TestInteractiveSplit` tests (seven at HEAD plus the two step 5 added — `test_phase_b_delegates_to_escalate_to_split`, `test_phase_b_no_inline_engine_calls`) stay green, and the exit code stays 0.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the dead-ended unattended structural finding this surfaces
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the guard change, the recommendation collection, the post-loop emitter
- [Tests](#tests) — the new unattended cases plus the unchanged interactive set
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — what later steps own and the accepted double-surface

## Why

- The granularity MIXED-STEP purity check (`plan_tool/granularity.py:parse_mixed_step_findings`, surfaced through `detail`) is the producer of structural (`granularity-split`) findings, and an over-packed / mixed-concern step it flags can't be fixed by re-authoring — the remedy is a step split. Today Phase B's `if allow_split and mixed_steps and sys.stdin.isatty():` guard only ever runs that escalation on an interactive `detail --split` session. On the common path — a plain `detail` run, or any CI/non-TTY run — the operator gets only the one-line `mixed-step detected` warning (the `tool(...)` call beside `mixed_steps.append(...)`) and never sees the actionable "split this into two type-pure steps via `plan-tool split`" recommendation. The split is recognized and then dropped.
- This step delivers invariant 1 from the plan ("always validate the more-correct plan"): for a recognized structural finding with a concrete target, a split recommendation is surfaced on every run, while invariant 2 ("never mutate structure unattended") is preserved by `escalate_to_split` itself. Step 5 re-pointed Phase B at the bridge but deliberately kept the guard so it was behavior-preserving; this step is the feature that opens the unattended path.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — in `generate_detail`'s Phase B: change the guard to `if mixed_steps:`; rewrite the guard comment to state the bridge now owns the apply-vs-recommend / never-unattended decision; collect `result.recommendation` from `recommended` outcomes into a `structural_recs` list; after the loop, call the new `_emit_split_recommendations(structural_recs, ...)`. Add the module-level private helper `_emit_split_recommendations`.
  - `tests/test_detail.py` — add a new `TestUnattendedSplitRecommendation` class for the dropped-guard / collection / emission behavior; leave the nine `TestInteractiveSplit` tests unchanged (the seven at HEAD plus step 5's two).

## Implementation

### `plan_tool/detail.py`

**Drop the opt-in/TTY guard (the one behavior change at the entry).**
- Change the Phase-B opener from `if allow_split and mixed_steps and sys.stdin.isatty():` to `if mixed_steps:`. The bridge is now entered for every flagged mixed step regardless of `allow_split` or TTY.
- **Change the `escalate_to_split` call's `allow_split` argument from the literal `allow_split=True` (which step 5 passes — justified there because the dropped outer `allow_split and ... isatty()` guard had already proved opt-in) to the threaded `allow_split=allow_split`.** This is the essential edit of this step, not a no-op: once the guard is `if mixed_steps:`, the bridge is entered without the outer opt-in proof, so the operator's real flag must reach it. Resulting call: `escalate_to_split(plan_path, step_id=target_id, repo_root=repo_root, invoker=invoker, allow_split=allow_split, prompt_fn=prompt_fn)`. Do **not** leave a forced `allow_split=True`; on a plain TTY `detail` run (no `--split`, CLI `allow_split=False`) that would propose and apply after an interactive confirm — violating invariant 2 ("never mutate structure unattended / without opt-in"). The bridge's outcome ladder then decides the disposition from the real flag so a default run recommends and a `--split` run can apply.
- Rewrite the guard comment block (the "interactive refactor-then-feature split" comment above the old guard). State plainly: Phase B enters the bridge for every mixed step; `escalate_to_split` mutates only on the safe + `allow_split` + confirmed path and recommends on every unattended / non-opt-in path; the high→low `sorted(..., reverse=True)` order and the bridge's per-call re-parse are unchanged.

**Bridge cost on the default path (state, don't add code).**
- On a default `detail` run, `allow_split` is `False`, so `escalate_to_split`'s ladder hits its "recommend-only short-circuit (no Claude)" return **before** `_propose_step_split` — the unattended recommendation costs zero Claude per mixed step. The plan's Risks section anticipated "one `_propose_step_split` call per mixed step on the default path"; that does not happen with step 4's landed ladder, because the `allow_split=False` short-circuit precedes the proposal. The propose-then-auto-decline cost applies only to a `detail --split` run on a non-TTY (`allow_split=True`, no confirm).

**Collect recommendations in the outcome switch.**
- Initialize `structural_recs: list["Recommendation"] = []` beside `split_target_ids` at the top of the `if mixed_steps:` block.
- Extend the existing `EscalateResult.outcome` switch (the one step 5 wired):
  - `"unsafe"` → emit the blocking-ids warning built from `result.blocking`, but **rephrase step 5's copy** so it does not assume an opted-in `--split` session: now the guard is `if mixed_steps:` the warning also fires on plain (non-`--split`) and CI runs where the operator never requested an auto-split, so "skipping auto-split" reads as misleading there. Phrase it as a "cannot recommend split — downstream already started" message, e.g. `f"step {target_id}: cannot recommend split — downstream step(s) {result.blocking} have already run/started; restructure via re-plan if the split is still wanted"` (`level="warning"`). **Do not** add to `structural_recs` — an `unsafe` result carries `recommendation=None` (the recommended `plan-tool split` would itself be blocked by the same already-run downstream steps).
  - `"proposal-unusable"` → keep the existing unusable-proposal note. No rec.
  - `"applied"` → keep `split_target_ids.add(target_id)` + the re-author note. No rec (`applied` returns `recommendation=None`).
  - `"recommended"` → append `result.recommendation` to `structural_recs` (guard with `if result.recommendation is not None:` for safety, though the bridge always populates it on this outcome).
  - `"step-missing"` → silent no-op (matches the inline `except KeyError: continue` it replaced). No rec.

**Emit after the loop.**
- Leave the `if split_target_ids:` half-reauthoring/rebuild block unchanged — it still runs only when a real split applied.
- After that block, still inside `if mixed_steps:`, add:
  - `if structural_recs: _emit_split_recommendations(structural_recs, plan_slug=_plan_slug(plan_path))`
- Placement matters: Phase B runs **after** the `for step in target_steps` loop closes, so the in-loop `emit_detail_findings_summary` / `emit_triage_summary` calls have already printed. The post-loop emitter is the only surface that can carry a recommendation produced by the bridge.

**New helper — `_emit_split_recommendations`.**
- Add a module-level private helper near `emit_detail_findings_summary`:
  - Signature: `def _emit_split_recommendations(recs: "list[Recommendation]", *, plan_slug: str, stream=None) -> None:`
  - No-op on empty `recs` (mirror `emit_detail_findings_summary`'s `if not findings: return`).
  - Resolve `stream` at call time (`if stream is None: stream = sys.stderr`) — same reason as `emit_detail_findings_summary`: a `sys.stderr` default arg binds at definition and bypasses `capsys`.
  - Print a short header naming the plan slug and that these are split recommendations the operator must act on with `plan-tool split`, then one block per rec: the rec title, `review.triage_reason(rec)` (step 2's `structural-split` → `plan-tool split` message), and deeper-indented sub-lines for `rec.body` and `rec.suggested_action` (only when `suggested_action is not None`). Lazy-import `triage_reason` (`from plan_tool.review import triage_reason`) to keep load-time imports tree-shaped.
- **Why a dedicated emitter and not `review.emit_triage_summary`:** `emit_triage_summary`'s preamble ("…the iteration loop will short-circuit if these are the only findings remaining") describes the convergence loop and is wrong post-loop — a default non-`--iterate` run has no loop. The dedicated helper gives an honest header while keeping the message itself single-sourced through `review.triage_reason` (step 2). It reuses step 2's body/`suggested_action` sub-line shape as the format template; only the loop-specific preamble is left out.

## Tests

All in `tests/test_detail.py`, new class `TestUnattendedSplitRecommendation`. Stub `plan_tool.detail.escalate_to_split` (monkeypatch the module-level name) to return controlled `EscalateResult` values so the cases pin Phase B's guard / collection / emission logic without driving the real split engine or any Claude call. Capture stderr with `capsys`. The autouse `_stub_lessons_extraction` fixture and per-call `extract_lessons=False` keep lesson extraction off.

- `test_default_run_recommends_for_mixed_step` — a mixed step, `allow_split=False`, `sys.stdin.isatty()` → False; stub `escalate_to_split` to return `outcome="recommended"` with a `structural-split` rec → the rec's `plan-tool split` text appears on stderr; the plan file is unchanged (no split applied).
- `test_guard_enters_bridge_without_opt_in_or_tty` — spy on the stubbed `escalate_to_split`; with `allow_split=False` and non-TTY and a mixed step, assert the bridge **was** called once per mixed step (proves the guard no longer requires `allow_split`/`isatty`).
- `test_no_mixed_steps_skips_bridge_and_emission` — a run whose self-check flags no mixed step → `escalate_to_split` (spy) never called and no split-recommendation header on stderr (pins the `if mixed_steps:` guard).
- `test_split_flag_non_tty_recommends` — `allow_split=True`, non-TTY; stub returns `outcome="recommended"` → recommendation surfaced, plan file unchanged (the `--split` unattended path recommends, never mutates).
- `test_applied_outcome_emits_no_recommendation` — `allow_split=True`, TTY; stub returns `outcome="applied"` → `structural_recs` stays empty, no split-recommendation header printed (only the re-author path runs); pins applied ≠ recommended.
- `test_unsafe_outcome_warns_without_recommendation` — stub returns `outcome="unsafe"` with `blocking=[…]` → the `cannot recommend split — downstream already started` warning lists the blocking ids (and does **not** read as "skipping auto-split") and **no** split-recommendation block is emitted (unsafe carries no rec).
- `test_step_missing_outcome_is_silent` — stub returns `outcome="step-missing"` → no warning, no rec, no emission.
- `test_recommendation_keeps_rc_zero` — a recommend-only run returns from `generate_detail` with all `DetailResult`s successful/written (none carry a failure `skipped_reason`), so nothing flips the run's exit code; the recommendation is output only.
- `test_emit_split_recommendations_empty_is_noop` — `_emit_split_recommendations([], plan_slug="x")` prints nothing.
- `test_emit_split_recommendations_renders_action` — a single `structural-split` rec with a `suggested_action` → output contains the title, the `triage_reason` text, the body, and the `plan-tool split` action sub-line; a rec with `suggested_action is None` omits the action sub-line.

The nine existing `TestInteractiveSplit` tests — the seven at HEAD plus the two step 5 added (`test_phase_b_delegates_to_escalate_to_split`, `test_phase_b_no_inline_engine_calls`) — must stay **green unchanged**, and split into two behavior classes under the dropped guard:

- **Eight run on a TTY + `allow_split=True` + confirm `y` → real `escalate_to_split` applies.** The new `if mixed_steps:` guard still admits them, and on their TTY `--split` run (CLI `allow_split=True`) the `allow_split=True → allow_split` call change still threads `True`, so `test_phase_b_delegates_to_escalate_to_split`'s forwarded-`allow_split=True` assertion still holds and `test_phase_b_no_inline_engine_calls`'s no-inline-engine assertion is untouched; an all-applied run collects no recs so it emits no extra block.
- **`test_without_flag_only_warns` is the one test whose behavior changes** — it runs `allow_split=False`, so under the old guard it never entered the bridge. With the guard dropped to `if mixed_steps:` it now enters `escalate_to_split` and, on the `allow_split=False` short-circuit, recommends — emitting a `structural-split` recommendation via `_emit_split_recommendations`. It stays green only because it asserts on plan titles alone (the plan stays unchanged on a recommend-only run) and never asserts the absence of that new stderr block. Do **not** fold it into the all-apply claim; if it is later tightened to assert exact stderr, update it for the new recommendation surface.

### Test-creation order (feature step)

This is a **feature** step — new unattended-recommendation behavior. Add the tests **with** the implementation:

1. First `test_guard_enters_bridge_without_opt_in_or_tty` and `test_no_mixed_steps_skips_bridge_and_emission` — pin the guard change (enters without opt-in/TTY; still gated on `mixed_steps`).
2. Then `test_default_run_recommends_for_mixed_step`, `test_split_flag_non_tty_recommends`, `test_unsafe_outcome_warns_without_recommendation`, `test_step_missing_outcome_is_silent`, `test_applied_outcome_emits_no_recommendation` — pin the per-outcome collection and emission.
3. Then `test_recommendation_keeps_rc_zero`, `test_emit_split_recommendations_empty_is_noop`, `test_emit_split_recommendations_renders_action` — pin the no-rc-flip contract and the emitter formatting.
4. Re-run the full `TestInteractiveSplit` class to confirm all nine interactive tests still pass unmodified.

**Green-before-done gate:** every new test in `TestUnattendedSplitRecommendation` and all nine `TestInteractiveSplit` tests must be green before this step is finished.

## Acceptance criteria

- Phase B's guard in `plan_tool/detail.py:generate_detail` is `if mixed_steps:` — no `allow_split` or `sys.stdin.isatty()` term.
- A non-TTY, `allow_split=False` run over a mixed step calls `escalate_to_split` once per mixed step (proven by a spy) and the plan file is unchanged.
- A `recommended` outcome's `recommendation` is collected and printed by `_emit_split_recommendations`; the output contains the rec's `plan-tool split` action.
- `unsafe`, `proposal-unusable`, `applied`, and `step-missing` outcomes contribute nothing to `structural_recs`; only `applied` adds to `split_target_ids`.
- `_emit_split_recommendations([], …)` prints nothing; a non-empty call renders title + `review.triage_reason` text + body, and the `suggested_action` sub-line only when it is not `None`.
- A recommend-only run produces no failure `DetailResult` and does not flip the run's exit code.
- All nine `TestInteractiveSplit` tests (seven at HEAD plus step 5's `test_phase_b_delegates_to_escalate_to_split` and `test_phase_b_no_inline_engine_calls`) pass unmodified; `uv run pytest tests/test_detail.py -q` is green.

## References

- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — patch `plan_tool.detail.escalate_to_split` and `sys.stdin.isatty` so the new cases drive controlled outcomes with no real `claude` spawn.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — `capsys`, `tmp_path`, and the unit-test conventions the new class follows.
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the `EscalateResult` shape (`outcome`, `target_id`, `recommendation`, `blocking`) the switch reads.

## Deferred

- **The in-loop trigger-2 contract (`BLOCKED-STRUCTURAL` discovered mid-apply).** Owned by step 7 — break out of both loop levels, re-parse, re-collect `target_steps`, revert partial prose, and a per-run seen-set. This step only opens trigger 1 (the post-loop, pre-classified `granularity-split` path).
- **`cli/review_actions.py` apply-walk handling of `BLOCKED-STRUCTURAL`.** Owned by step 8.
- **Double-surface of the same mixed step.** Under `--iterate`, the convergence loop already shows the `granularity-split` diagnostic via `emit_triage_summary`, and Phase B now also shows the `structural-split` recommendation. This is intentional: the loop surface is the diagnostic, Phase B's surface is the actionable `plan-tool split` command. Collapsing the two into one line is a follow-up only if operators find it noisy.
- **A detection-only recommendation on the `unsafe` outcome.** The bridge returns `recommendation=None` for `unsafe`, so Phase B emits only the blocking-ids warning. Whether to also surface a non-actionable structural detection is tracked against the "always validate the most-correct plan" principle in step 4's Deferred — not reopened here.
