> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Handle in-loop `BLOCKED-STRUCTURAL` (trigger 2) in `detail`'s convergence apply loop

## Summary

- Teach `plan_tool/detail.py:generate_detail`'s per-step convergence loop to recognize the `BLOCKED-STRUCTURAL` apply verdict (added by step 3) and route it to `plan_tool/launcher.py:escalate_to_split` (added by step 4), inside the `for rec in open_apply` loop right after `apply_finding` returns.
- The key design decision is the **in-loop renumbering contract**: an applied split renumbers step ids out from under both loops, so this step reverts the finding's partial edit first, escalates, and on `outcome == "applied"` breaks the inner `for rec` loop, the `while True` convergence loop, and the outer `for step in target_steps` loop, then re-parses the renumbered plan and re-authors the detail-less halves.
- A **per-run seen-set** keyed on `rec.id` stops a recommend-only structural finding from being re-escalated (and re-proposed via `escalate_to_split`) on every later iteration; the dedup sits inside the post-`apply_finding` branch, so the underlying `apply_finding` prose attempt may still re-run on the same finding until stall detection terminates the loop — the guard bounds re-escalation/re-proposal, not re-invocation. Recommend-only escalations collect their `structural-split` recommendation for post-loop surfacing.
- All changes are additive new code (a new verdict branch, new run-scoped flags, a new post-loop re-author block) — no existing behavior changes when `BLOCKED-STRUCTURAL` never fires. Files touched: `plan_tool/detail.py`, `tests/test_detail.py`.
- On green: an interactive `--split --iterate` run whose mid-apply finding returns `BLOCKED-STRUCTURAL` applies the split once, re-authors both halves and drives each through its own convergence apply loop in the **same run** (the split re-enters convergence over the renumbered plan — it does not defer the new steps' validation to a later `--iterate` run), processes no stale pre-split `Step`, and exits 0; an unattended run recommends only, mutates nothing, and never re-proposes the same finding twice.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the dead-ended mid-apply structural verdict this resolves
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the verdict branch, the three-level break, the seen-set, the re-author block
- [Tests](#tests) — the trigger-2 cases plus the no-op guard
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — what later steps own and the rebuild-block consolidation

## Why

- The `detail` purity self-check (trigger 1) catches a mixed refactor+feature step **before** the apply loop and resolves it in Phase B. The second trigger fires **inside** the loop: when Claude, mid-apply on an ordinary prose finding, decides the only correct fix is to split the step, step 3 has it emit `## Verdict: BLOCKED-STRUCTURAL` instead of a bare `BLOCKED`. Today (after steps 3/4 land) `generate_detail`'s `for rec in open_apply` loop ignores `apply_result.verdict` entirely (it reads it only for the run log at the `apply_finding_dispatch` `phase_end`), so a `BLOCKED-STRUCTURAL` verdict is silently dropped, the structural finding stays unresolved, and the convergence loop re-collects and re-dispatches it every iteration until the budget runs out.
- This trigger is the hard one because applying a split renumbers step ids in the middle of a loop that iterates **by** step id (`for step in target_steps` over `plan.steps`, `apply_finding(..., step_id=step.id)`). A naive in-loop split leaves stale captured `Step` objects, makes the next `collect_detail_quality_findings` re-derive the same finding under a shifted id, and leaves a partial prose edit on disk that `escalate_to_split` would re-read. Isolating that whole contract — revert-first, escalate, break all three loop levels, re-parse, re-author, and remember recommend-only findings — into this one step is the core of the plan's re-decomposition (the predecessor scattered it across five plan-body sentences, which was the bug).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — in `generate_detail`:
    - extend the existing top-level `from plan_tool.launcher import apply_finding` to also import `escalate_to_split`;
    - pass `allow_structural_verdict=True` on the convergence-loop `apply_finding(...)` call inside `for rec in open_apply` (step 3's opt-in, default OFF), so the shared `apply-finding` prompt renders the `BLOCKED-STRUCTURAL` instruction and real Claude can emit the verdict this step routes;
    - add three run-scoped accumulators beside the existing `mixed_steps` list (before the `for step in target_steps` loop): `structural_seen`, `structural_split_ids`, `inloop_structural_recs` (named distinctly from step 6's Phase-B `structural_recs` — both live in the same `generate_detail` scope, so a shared name would let step 6's post-loop `structural_recs = []` re-init silently discard this step's collected trigger-2 recs);
    - add a step-level `did_structural_split = False` beside `phase_outcome = "success"`;
    - add `detail_structural_halted = False` beside the existing `detail_drift_halted` sentinel inside the `if budget.enabled:` block;
    - add the `BLOCKED-STRUCTURAL` branch inside `for rec in open_apply`, right after `apply_finding` returns and `touch(state)`, before the post-apply drift check;
    - add `if detail_structural_halted: break` after the `for rec` loop, beside the existing `if detail_drift_halted: break`;
    - guard the per-step lesson-capture and `results.append(... written=True)` on `not did_structural_split`, and set `phase_outcome`/`phase_reason` for the structural-halt case;
    - add `if did_structural_split: break` at `for step` level, after the per-step `try`/`finally`;
    - add a new post-loop re-author block keyed on `structural_split_ids`, after Phase B's `if mixed_steps:` block (step 6 replaces the prior `if allow_split and mixed_steps and sys.stdin.isatty():` guard with `if mixed_steps:`).
  - `tests/test_detail.py` — add a new `TestInLoopStructuralEscalation` class covering the trigger-2 cases plus the no-op guard.

## Implementation

### `plan_tool/detail.py` — imports

- **Add `escalate_to_split` to the existing top-level launcher import.** `detail.py` already imports `apply_finding` from `plan_tool.launcher` at module top (the load graph stays a tree because `review`→`detail` is lazy); `escalate_to_split` rides the same direction. Final line: `from plan_tool.launcher import apply_finding, escalate_to_split`.
- **Import the revert helper body-local in the new branch**, not at module top: `from plan_tool.launcher import _restore_text_files as _revert_snapshot`. Keep the private import next to its single use, matching the existing `_restore_text_files as _revert_snapshot` alias in `cli/review_actions.py` (review_actions.py:81).
- **Do not add a new proposer-invoker parameter.** `escalate_to_split`'s `invoker` is the split-PROPOSER seam (`Callable[[str], str]` returning raw Claude text). `generate_detail`'s own `invoker: DetailInvoker` is already exactly `Callable[[str], str]` (`DetailInvoker = Callable[[str], str]`) and is what Phase B hands to `_propose_step_split` today — pass that same `invoker` straight through. Do **not** reuse launcher's `Invoker = Callable[[str], tuple[int, str]]` run-step alias.

### `plan_tool/detail.py` — run-scoped accumulators

- **Declare beside `mixed_steps`** (just before `for step in target_steps:`), so they survive across steps and iterations within one `generate_detail` call:
  - `structural_seen: set[str] = set()` — `rec.id`s already escalated this run. A recommend-only escalation does **not** mutate the plan, so the finding's id is stable across re-collection (`_make_rec_id` hashes the finding content under a `step{N}` prefix; the prefix only shifts on a renumber, which only an *applied* split causes — and an applied split breaks the loop, so the seen-set is never consulted across a renumber).
  - `structural_split_ids: set[int] = set()` — original target ids whose in-loop split was applied; drives the post-loop re-author block.
  - `inloop_structural_recs: "list[Recommendation]" = []` — recommend-only `structural-split` recommendations to surface after the loop. Named distinctly from step 6's `structural_recs` to avoid the same-scope collision. (`Recommendation` is already a `TYPE_CHECKING` import in `detail.py`; use the string annotation, as `mixed_steps` does.)

### `plan_tool/detail.py` — the `BLOCKED-STRUCTURAL` branch

- **Opt into the verdict at this call site (guard (a)).** The convergence-loop `apply_finding(...)` call this branch reads must pass `allow_structural_verdict=True` (step 3's flag, default OFF). Without it the shared `apply-finding` prompt never renders the `BLOCKED-STRUCTURAL` instruction, real Claude never emits the verdict, and this entire branch is dead code — the detail convergence-loop call is exactly the opt-in caller guard (a) names.
- **Placement:** inside `for rec in open_apply`, immediately after the `apply_result = apply_finding(...)` call, its `run_logger.phase_end("apply_finding_dispatch", ...)`, and `touch(state)` — and **before** the post-apply drift check. The drift check is irrelevant on this path because the edit is reverted.
- **Branch body (in order — the ordering is the contract):**
  1. **Revert the partial edit first.** Call `_revert_snapshot(apply_result.pre_snapshot)`. `apply_finding` does **not** revert on a non-`APPLIED` verdict (it only reverts on a non-zero exit code), so a `BLOCKED-STRUCTURAL` run may leave a partial prose edit on disk. `escalate_to_split` re-reads the plan from disk, so the revert must land strictly before the escalate call or the half-applied edit leaks into the split's base.
  2. **Dedup against the seen-set.** If `rec.id in structural_seen`, `continue` — already escalated this run; do not re-propose (the seen-set is the cost/termination guard from invariant-2's "never re-propose" clause). Otherwise `structural_seen.add(rec.id)`.
  3. **Escalate once:** `esc = escalate_to_split(plan_path, step_id=step.id, repo_root=repo_root, invoker=invoker, allow_split=allow_split, prompt_fn=prompt_fn)`. The unattended-safety guarantee (invariant 2) does **not** rest on `prompt_fn` being `None` — `generate_detail` reassigns `prompt_fn = builtins.input` when it arrives `None` (`detail.py:1522-1524`), so it is non-`None` by the time this in-loop escalate runs. The real guard is `_confirm_split`'s own `sys.stdin.isatty()` short-circuit (`detail.py:2918`): on a non-TTY it auto-declines regardless of `prompt_fn`, so an unattended convergence loop never mutates structure. (Do not weaken that `isatty` check on the belief that a `None` `prompt_fn` enforces this — it doesn't.)
  4. **On `esc.outcome == "applied"`:** `structural_split_ids.add(esc.target_id or step.id)`, set `detail_structural_halted = True` and `did_structural_split = True`, then `break` the `for rec` loop. The remaining `open_apply` recs belong to a step id that no longer exists, so they must not be applied.
  5. **On every other outcome, surface something — never silently `continue`** (invariant 1: a recognized structural target is never silently skipped). Branch on `esc.outcome`, reading each `EscalateResult` field only where step 4 populates it:
     - `recommended` — append `esc.recommendation` (populated only here) to `inloop_structural_recs` for post-loop surfacing.
     - `unsafe` — `esc.recommendation` is `None` by design (the recommended `plan-tool split` would itself be blocked), but `esc.blocking` is populated; surface a transient blocking-ids warning naming it, e.g. via the reporter `f"structural escalation unsafe — downstream steps {esc.blocking} are not PENDING; resolve them, then run plan-tool split"` (mirrors step 8's `unsafe` status string). This satisfies the acceptance criterion that `unsafe` "surfaces a blocking-ids warning (steps 7/8)."
     - `proposal-unusable` / `step-missing` — both carry `recommendation=None`; surface a one-line note (e.g. `f"structural finding {rec.id} on step {step.id}: escalate_to_split returned {esc.outcome}; nothing surfaced to apply — re-run or re-plan"`) so a recognized target is not silently dropped.
     Then `continue`. The `structural_seen.add(rec.id)` in item 2 (before this branch) bounds each finding to **one** surfaced warning/note across the run's convergence iterations — it is emitted once, not re-emitted every iteration.
- **Do not add a new branch to `apply_finding`.** `BLOCKED-STRUCTURAL` already flows through `apply_finding` with empty `introduced_findings`/`resolved_findings` because that delta is gated on `verdict == "APPLIED"` — this step only reads the verdict in the caller.

### `plan_tool/detail.py` — propagating the break up three levels

- **`while True` (convergence) level:** beside the existing `if detail_drift_halted: break` (after the `for rec` loop), add `if detail_structural_halted: break`. Keep them separate — drift halt and structural halt have different post-loop handling.
- **`for step in target_steps` level:** the convergence loop sits inside the per-step `try:` (opened just after `phase_outcome = "success"`) … `finally:` (the `run_logger.phase_end(phase_name, ...)`). On a structural halt:
  - Set `phase_outcome = "structural-split"` and `phase_reason = f"step {step.id} split into refactor + feature; ids renumbered"` so the run log records why the phase ended without a written body.
  - Guard the per-step lesson-capture block (`if extract_lessons and body and not did_structural_split:`) and the success `results.append(DetailResult(... written=True))` on `not did_structural_split` — the original step's body was reverted and the step was split away, so neither a lesson nor a "written" result applies to it.
  - After the `try`/`finally` closes (at `for step` indentation), add `if did_structural_split: break`. The `finally` still fires first, emitting `phase_end` with the `structural-split` outcome. The remaining `target_steps` entries carry pre-split ids and must not be processed.

### `plan_tool/detail.py` — the post-loop re-author block

- **Placement:** after Phase B's `if mixed_steps:` block (step 6 replaces the prior `if allow_split and mixed_steps and sys.stdin.isatty():` guard with `if mixed_steps:`), before `return results`.
- **Invalidate stale `mixed_steps` entries before Phase B consumes them.** A trigger-2 applied split renumbers ids out from under `mixed_steps` exactly as it does `target_steps`: when the same step K is both flagged `granularity-split` (appended to `mixed_steps`) and yields `BLOCKED-STRUCTURAL` on a separate `detail-body` apply, the split leaves the `mixed_steps` entry for K (and any entry with id ≥ K) pointing at a freshly-created half. Phase B's `if mixed_steps:` block (step 6) runs **before** this step's `if structural_split_ids:` re-author, so unless `mixed_steps` is corrected first it runs `_split_is_safe`/`_propose_step_split` against a half it never flagged — a spurious propose (wasted Claude on `--split` non-TTY) or a wrong-step `structural-split` recommendation. When `structural_split_ids` is non-empty, either skip Phase-B `mixed_steps` processing entirely or re-derive `mixed_steps` from the renumbered plan, excluding `structural_split_ids`, so Phase B never proposes against a step the trigger-2 split created.
- **Body (mirror Phase B's `if split_target_ids:` block — same renumber-safe attribution):**
  - `if structural_split_ids:` — re-parse the renumbered plan and re-author every detail-less step. Mirror Phase B: `half_ids = [s.id for s in parse_plan(plan_path).steps if s.detail is None]`, then for each `hid` call `generate_detail(plan_path, ..., step_id=hid, force=False, allow_split=False, resume=False, ...)` (forwarding the same `invoker`/`reporter`/`budget`/`prompt_fn`/etc.). `allow_split=False` stops recursion; `resume=False` skips checkpoint probes for the new step shapes. This re-authors both new halves **and** any steps the broken `for step` loop never reached (all detail-less after the split). Forwarding `budget` (with `--iterate` on) means each recursive `generate_detail` runs its own per-step convergence apply loop over the renumbered plan, so the two new type-pure halves are driven to convergence **in this run** — the split **re-enters convergence** over the renumbered plan; it does not defer the new steps' validation to a later `--iterate` invocation.
  - **Rebuild `results` from the final on-disk state**, keyed on slug rather than id (renumber-stable). Reuse Phase B's exact mechanism: a `written_keys` set built from `_detail_slug_key(Path(r.output_path))` over this run's `results` plus the re-author results; `min_split = min(structural_split_ids)`; drop `results` entries with `step_id >= min_split`; re-add one `DetailResult` per final-plan step at/after `min_split` (written vs `"already exists (carried through split renumber)"`), and extend with any re-author halves that failed to write. This keeps the run summary truthful and the exit code honest after the renumber.
- **Surface the recommend-only recommendations.** After the re-author block, emit `inloop_structural_recs` once via step 6's `detail._emit_split_recommendations` helper — it writes a loop-free header and sidesteps `emit_triage_summary`'s loop-short-circuit preamble (`review.py:3424`), the exact reuse step 6's captured `[detail-authoring]` lesson exists to avoid. Step 6 lands before step 7, so `_emit_split_recommendations` is the **primary** path here. Only fall back to `review.emit_triage_summary(inloop_structural_recs, iteration_label=...)` if the helper has not landed (step 2 taught `emit_triage_summary` to render a structural rec's `body`/`suggested_action`). Both single-source the per-rec text through `review.triage_reason`, so the operator sees the `plan-tool split` remedy either way.

### Foundational logic — the verdict-dispatch rule

- This step's foundational logic is **"dispatch on `ApplyFindingResult.verdict` to route a structural finding to `escalate_to_split`."** The other site that consumes this exact verdict is `plan_tool/cli/review_actions.py:_dispatch_apply_finding` (step 8): it routes the same `BLOCKED-STRUCTURAL` verdict through `_dispatch_structural_escalation`, reverting via `_restore_text_files as _revert_snapshot` before delegating. The two share the revert-first-then-escalate shape but live on different control paths (in-loop convergence here, single apply-walk dispatch there) and are correctly kept separate — see Deferred for the consolidation note.

## Tests

All cases drive `generate_detail` with `budget=IterativeBudget(enabled=True, ...)` so the convergence loop runs, a fake `invoker`, a stubbed module-level `apply_finding` returning a chosen `verdict` (**except `test_real_apply_path_emits_blocked_structural`, which drives the real `apply_finding`** so the verdict is parsed from a genuine `## Verdict` block), and a monkeypatched module-level `escalate_to_split`. Add `@pytest.mark.integration` at the class level (these drive the orchestrator across modules). Tests live in `tests/test_detail.py` in a new `TestInLoopStructuralEscalation` class.

- `test_blocked_structural_escalates_once` — `apply_finding` returns `verdict="BLOCKED-STRUCTURAL"`; assert `escalate_to_split` is called exactly once with `step_id == step.id`, `allow_split` and `prompt_fn` forwarded.
- `test_reverts_before_escalate` — stub `apply_finding` to leave a sentinel partial edit on the plan file in `pre_snapshot`; rig the `escalate_to_split` stub to read the plan from disk and assert it sees the pre-edit (reverted) content — proves `_revert_snapshot` runs strictly before the escalate call.
- `test_applied_split_breaks_all_loops` — `escalate_to_split` returns `outcome="applied"`; assert no further `apply_finding` call fires for later `open_apply` recs or later `target_steps`, and the per-step phase ends with outcome `"structural-split"` (no `written=True` result for the original step).
- `test_applied_split_reauthors_detail_less_halves` — after an applied split that leaves two `detail is None` halves on disk, assert the returned `results` include a written entry per half (via the recursive `generate_detail` re-author) and the rebuilt region is slug-attributed.
- `test_seen_set_suppresses_reproposal` — `escalate_to_split` returns `outcome="recommended"`; run a loop where the same finding re-collects across two iterations; assert `escalate_to_split` is called once, not per iteration.
- `test_recommend_only_collects_and_surfaces_rec` — recommend-only outcome with a `structural-split` `Recommendation`; assert the plan bytes are unchanged, the rec is surfaced (its `suggested_action` naming `plan-tool split` appears on the captured stream), and rc stays 0.
- `test_unattended_recommends_no_mutation` — non-TTY (`sys.stdin.isatty` patched `False`), `prompt_fn=None`, `allow_split=True`; `escalate_to_split` returns `recommended`; assert plan unchanged and no `_apply_step_split` write.
- `test_normal_verdict_never_escalates` — `apply_finding` returns `verdict="APPLIED"` (and a second case `"BLOCKED"`); rig the `escalate_to_split` stub to raise; assert it is never called — proves the route is inert for every non-`BLOCKED-STRUCTURAL` verdict.
- `test_real_apply_path_emits_blocked_structural` — **the one case that does NOT stub `apply_finding`.** Drive the loop with the **real** `apply_finding` and a fake `invoker` that **captures the prompt string it receives** and, only when that prompt contains the `BLOCKED-STRUCTURAL` instruction bullet, returns a `## Verdict: BLOCKED-STRUCTURAL` block (with a `## Summary`). Assert the captured prompt the apply call rendered **contains the `BLOCKED-STRUCTURAL` bullet** (proving the detail call set `allow_structural_verdict=True`, so the verdict was actually offered — not an unconditional fake), then assert it flows through real `parse_apply_verdict` to `verdict="BLOCKED-STRUCTURAL"` and the loop routes it to the (still-stubbed) `escalate_to_split` with `step_id == step.id`. Because the verdict is gated on the rendered bullet, the test **fails if `allow_structural_verdict` is not set on the detail call** (no bullet → real `apply_finding` never emits the verdict → no escalation). Proves the detail-side trigger-2 path is live end-to-end (opt-in rendered into the prompt → real `apply_finding` → real `parse_apply_verdict` → escalate), not only asserted via a stubbed verdict return — closing the live-but-inert risk the plan-level criterion names.

### Test-creation order (feature step)

- This is a **feature** step — new in-loop behavior. Write each test above **with** the implementation it covers: the verdict branch and the three-level break (`test_blocked_structural_escalates_once`, `test_applied_split_breaks_all_loops`), the revert ordering (`test_reverts_before_escalate`), the seen-set (`test_seen_set_suppresses_reproposal`), the re-author block (`test_applied_split_reauthors_detail_less_halves`), the recommend-only surface (`test_recommend_only_collects_and_surfaces_rec`, `test_unattended_recommends_no_mutation`), and the inertness guard (`test_normal_verdict_never_escalates`).
- **Green-before-done gate:** every new test must pass, and the existing `TestInteractiveSplit` / detail-convergence tests must stay green unchanged, before this step is considered finished.

## Acceptance criteria

- The convergence-loop `apply_finding(...)` call passes `allow_structural_verdict=True`, so the rendered prompt offers the `BLOCKED-STRUCTURAL` instruction — step 3's flag is flipped ON on this path, not left at the OFF default.
- A `for rec in open_apply` iteration whose `apply_finding` returns `verdict="BLOCKED-STRUCTURAL"` reverts the finding's edit via `_restore_text_files`, then calls `escalate_to_split(step_id=step.id, allow_split=…, prompt_fn=…)`.
- On `outcome="applied"`: the `for rec`, `while True`, and `for step in target_steps` loops all break; the renumbered plan is re-parsed; its detail-less halves are re-authored; no stale pre-split `Step` is processed.
- The post-loop re-author forwards `budget` to each recursive `generate_detail`, so under `--iterate` the two new halves are driven through their own convergence apply loop in the **same run** — the split re-enters convergence over the renumbered plan and does not defer the new steps' validation to a later `--iterate` invocation.
- A recommend-only structural finding is recorded in `structural_seen` and `escalate_to_split` is invoked at most once for it across all convergence iterations of the run.
- A recommend-only escalation mutates no plan/detail files and surfaces a `structural-split` recommendation pointing at `plan-tool split`; rc stays 0 unless `--fail-on-findings`.
- An `unsafe` outcome surfaces a transient blocking-ids warning naming `esc.blocking` (not silently dropped); a `proposal-unusable` / `step-missing` outcome surfaces a one-line note. Every recognized structural target produces some operator-visible signal (invariant 1), emitted once per finding (bounded by `structural_seen`).
- `escalate_to_split` is never called when the apply verdict is `APPLIED` / `BLOCKED` / `NOT-APPLICABLE` / `UNKNOWN` (the raise-on-call stub is never reached).
- At least one test drives the **real** `apply_finding` (not a stubbed verdict return) with a fake invoker that captures the rendered prompt and emits `## Verdict: BLOCKED-STRUCTURAL` **only when that prompt contains the `BLOCKED-STRUCTURAL` bullet**; the test asserts the captured prompt contains that bullet, so it **fails if `allow_structural_verdict` is not set on the detail call**. This proves the trigger-2 route is exercised through opt-in-rendered prompt → real `apply_finding` → `parse_apply_verdict` — so step 7's machinery is proven live, not inert.
- All `TestInLoopStructuralEscalation` tests pass; pre-existing `detail` convergence and `TestInteractiveSplit` tests pass unchanged.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — Field defaults and `Optional` typing behind `EscalateResult` (`outcome`/`target_id`/`recommendation`/`blocking`) this step reads.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Patching the module-level `apply_finding` and `escalate_to_split` seams so the autouse gate never spawns a real `claude`.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — `@pytest.mark.integration` and `capsys` for the cross-module convergence-loop tests.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — The exit-code convention (rc 0 on a surfaced recommendation unless `--fail-on-findings`) the loop must preserve.

## Deferred

- **Consolidate the two post-split re-author blocks.** This step's `if structural_split_ids:` re-author/rebuild mirrors Phase B's `if split_target_ids:` block (`half_ids` recursion, `written_keys`/`min_split` slug-keyed rebuild). Extracting a shared `_reauthor_after_split(plan_path, split_ids, …)` helper used by both triggers is a behavior-preserving refactor `detail` cannot mint — route it to reconcile rather than expanding this step's footprint.
- **Create-side trigger 2.** Out of scope here (and Deferred at the plan level): `create` dispatches only prose-fill sources to `apply_finding` and names no concrete scenario where a fill-prose finding turns structural mid-apply. No in-loop split handling is added to `create_plan`.
- **The `cli/review_actions.py` apply-walk `BLOCKED-STRUCTURAL` branch** — step 8 owns the single-dispatch (non-convergence) path, including the known stale-rec gap where the interactive walk does not re-collect after a mid-walk renumber.
- **`completeness_report.py` blocked rollups.** Its `a.verdict == "BLOCKED"` equality filters (`_blocked_split_targets`, `blocked_ct`) still exclude `BLOCKED-STRUCTURAL`; widening them to a membership test is tracked separately (out of this step's files).
