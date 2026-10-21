> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Handle `BLOCKED-STRUCTURAL` in `plan_tool/cli/review_actions.py` apply walk

## Summary

- Teach `plan_tool/cli/review_actions.py:_dispatch_apply_finding` to recognize the `BLOCKED-STRUCTURAL` apply verdict (added by step 3) and route it to `plan_tool/launcher.py:escalate_to_split` (added by step 4) instead of force-fitting it into the existing `BLOCKED`/`NOT-APPLICABLE` arm.
- The new verdict arm reverts any partial prose edit first (`apply_finding` reverts only on a non-zero exit, not on a non-`APPLIED` verdict), sets `phase_outcome = "reverted"` so the `finally` scope-guard/drift checks never fire against the bridge's out-of-scope plan/detail write, then delegates to a new `_dispatch_structural_escalation(rec)` closure that maps every `EscalateResult.outcome` back to a one-line walk status string.
- Thread a new `allow_split: bool = False` keyword through `_build_review_action_fn` (and both recursive sub-walk builds inside `_dispatch_detail_reconcile`) so the bridge's apply-vs-recommend choice is caller-controlled; every call site inherits the `False` default (no CLI flag sets it — deferred), so the walk recommends-only today.
- Thread a second `allow_structural_verdict: bool = False` keyword the same way, and **flip it ON at the `review`/reconcile `_build_review_action_fn(...)` call sites** — which live in `plan_tool/cli/review_cmd.py` (394/476/559) and `plan_tool/cli/reconcile.py` (564/673/1856), not in `review_actions.py` — so step 3's shared-prompt verdict is actually offered on the routed path. `cmd_completeness_apply`'s call site in `completeness_cmd.py` leaves it at the OFF default.
- Files touched: `plan_tool/cli/review_actions.py`, `plan_tool/cli/review_cmd.py`, `plan_tool/cli/reconcile.py`, and `tests/cli/test_review_actions.py`.
- On green: an apply finding that returns `BLOCKED-STRUCTURAL` reverts its partial edit, calls `escalate_to_split` once with the split-proposer seam, and reports a distinct status per outcome — without spuriously hitting the empty-diff no-op arm and without the scope guard reverting the bridge's split.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the silently-dropped structural verdict this resolves
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the verdict arm, the escalation closure, the `allow_split` thread
- [Tests](#tests) — the new verdict-routing cases plus the no-op guard
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — what later/other steps own

## Why

The interactive review/reconcile apply walk drives `apply_finding` on each recommendation, then branches on `result.verdict`. After step 3 widens the parser, a structural finding can come back as `BLOCKED-STRUCTURAL` — "the only correct fix is to split this step, which an apply edit can't do." Today `_dispatch_apply_finding` has no arm for that token: `BLOCKED-STRUCTURAL` is not in the `("BLOCKED", "NOT-APPLICABLE")` tuple, so it falls through to the `if not result.diff_text:` arm and reports the misleading "reported APPLIED but the plan file didn't change; nothing to keep" — the operator never sees that a split is the remedy, and any partial prose edit left on disk by `apply_finding` is silently kept. This step closes that gap by routing the verdict to the `escalate_to_split` bridge so the more-correct plan (a step split) is always surfaced from the walk, and applied when the caller opts in.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — add `escalate_to_split` to the builder's body-local `from plan_tool.launcher import (...)` block; add an `allow_split: bool = False` keyword to `_build_review_action_fn` and propagate it on both recursive `_build_review_action_fn` calls inside `_dispatch_detail_reconcile`; add an `allow_structural_verdict: bool = False` keyword to `_build_review_action_fn` (propagated on both recursive sub-walk builds) and pass it on `_dispatch_apply_finding`'s `apply_finding(...)` call; add a `BLOCKED-STRUCTURAL` arm in `_dispatch_apply_finding` (ordered before the `("BLOCKED", "NOT-APPLICABLE")` arm) that reverts + sets `phase_outcome = "reverted"` + delegates; add the `_dispatch_structural_escalation(rec)` closure.
  - `plan_tool/cli/review_cmd.py` — at the three `_build_review_action_fn(...)` call sites (lines 394/476/559) pass `allow_structural_verdict=True`, so the review walk's shared `apply-finding` prompt offers the verdict this step's arm routes. (Leave `allow_split` unset — that opt-in is deferred.)
  - `plan_tool/cli/reconcile.py` — at the three `_build_review_action_fn(...)` call sites (lines 564/673/1856) pass `allow_structural_verdict=True`, same rationale (the reconcile walk shares the dispatcher).
  - `tests/cli/test_review_actions.py` — add a `TestStructuralEscalation` class covering the verdict arm, each outcome, the proposer/`allow_split` wiring, the scope-guard/drift suppression, and the no-op guard.
  - **Untouched:** `plan_tool/cli/completeness_cmd.py` — its `_build_review_action_fn(...)` call (line 338) leaves `allow_structural_verdict` at the OFF default, keeping the completeness direct-apply loop off the verdict (per the plan).

## Implementation

### `plan_tool/cli/review_actions.py`

**Builder imports.** Extend the existing body-local `from plan_tool.launcher import (apply_finding, run_step as _run_step)` block (the one right after the docstring) to also import `escalate_to_split`. `_restore_text_files as _revert_snapshot` is already imported there — reuse it. Import the split-proposer seam body-local inside `_dispatch_structural_escalation` (see below) to keep this leaf import-light and avoid pulling `create` in at builder time.

**Add the `allow_split` keyword.** Give `_build_review_action_fn` a new keyword `allow_split: bool = False`, placed beside the existing `yes` keyword.
- **Default `False` keeps every caller unchanged for `allow_split`.** No call site passes `allow_split=True` — the operator opt-in CLI flag is deferred (see Deferred), so `review_cmd.py`, `reconcile.py`, and `completeness_cmd.py` all inherit `False` for *this* keyword. (They are still edited for the separate `allow_structural_verdict` keyword below — `review_cmd.py`/`reconcile.py` set it ON, `completeness_cmd.py` leaves it OFF.)
- **Thread it through both recursive sub-walk builds.** `_dispatch_detail_reconcile` self-recursively builds two sub-walk action fns (the saved-reuse `_build_review_action_fn(...)` call and the fresh-run one). Add `allow_split=allow_split` to **both** so a structural verdict surfacing inside a nested detail-reconcile walk inherits the parent's opt-in. A keyword added only to the signature would silently default nested walks back to `False`.

**Add the `allow_structural_verdict` keyword (guard (a)'s opt-in).** Give `_build_review_action_fn` a second new keyword `allow_structural_verdict: bool = False`, beside `allow_split`, and pass it on `_dispatch_apply_finding`'s `apply_finding(...)` call so the shared `apply-finding` prompt renders the `BLOCKED-STRUCTURAL` instruction (step 3's flag, default OFF). Thread it through both recursive sub-walk builds in `_dispatch_detail_reconcile`, exactly as `allow_split`.
- **Set it ON at the `review`/reconcile call sites.** Unlike the deferred `allow_split` CLI flag, this opt-in is **not** deferred: the `_build_review_action_fn(...)` call sites in `plan_tool/cli/review_cmd.py` (394/476/559) and `plan_tool/cli/reconcile.py` (564/673/1856) pass `allow_structural_verdict=True` so the verdict this step's arm routes is actually offered. These files are therefore in this step's `files:` scope (editing the call sites is required — they cannot be reached from `review_actions.py` alone). `cmd_completeness_apply`'s call site in `completeness_cmd.py` leaves the flag at the OFF default (the completeness direct-apply loop stays OFF, per the plan) and is **not** edited. Without this flip the prompt never offers `BLOCKED-STRUCTURAL`, real Claude never emits it, and `_dispatch_apply_finding`'s new arm is dead.

**Add the `BLOCKED-STRUCTURAL` verdict arm in `_dispatch_apply_finding`.** Place it **before** the `if result.verdict in ("BLOCKED", "NOT-APPLICABLE"):` arm (which is itself before `if not result.diff_text:`). Ordering is required: `BLOCKED-STRUCTURAL` is not in that tuple, so without a dedicated arm it would fall through to the empty-diff no-op (a structural verdict carries no diff) and report the wrong message. The arm:
- `_revert_snapshot(result.pre_snapshot)` **first**. `apply_finding` reverts the tree only on a non-zero subprocess exit, not on a non-`APPLIED` verdict, so a partial prose edit may sit on disk. `escalate_to_split` re-parses the plan from disk, so the revert must happen strictly before delegating or the half-applied edit leaks into the split's base.
- `phase_outcome = "reverted"`. This is the lever that suppresses the entire `finally` block: the per-finding scope-guard eval, the post-apply drift check, and the `state.work_landed_in_loop` flip are all gated on `phase_outcome == "success"`. The bridge writes `plan_path` and detail files outside the guard's `scope_dirs`/drift-watched set; a `"success"` disposition would make the `finally` evaluate those writes and revert the very split just applied.
- **`"reverted"` is correct only when nothing landed.** When the bridge actually applies a split (`result.outcome == "applied"`, reachable only in interactive + opt-in mode), the renumbered plan and new detail files genuinely persist, yet `"reverted"` leaves the reconcile drift baseline untouched. In reconcile-iteration mode that baseline is the only record of the working tree, so the *next* finding's pre-apply `check_drift` would see the split's files as uncommitted drift and halt the walk spuriously. An in-loop bridge-applied split must therefore **refresh the reconcile drift baseline** (the same `iter_lock` `refresh_snapshot` the collision-merge branch already calls) so the legitimate split is not re-detected as drift — do not reuse the unmodified-tree `"reverted"` disposition for a landed split. The remaining non-applying outcomes (`recommended` / `unsafe` / `proposal-unusable` / `step-missing`) mutate nothing and keep `"reverted"` as-is.
- `state.apply_skip = True`, mirroring the `BLOCKED`/`NOT-APPLICABLE` arm — no apply edit was kept on the original finding, so the walk records `skip`, not `applied`.
- `return _dispatch_structural_escalation(rec)` — the closure's status string becomes the arm's return value (the walk records/prints it).

**Add `_dispatch_structural_escalation(rec)` closure** (define it beside the other `_dispatch_*` closures, e.g. after `_dispatch_apply_finding`):
- Body-local `from plan_tool.create import shell_claude_invoker`. This is the split-**proposer** seam (`ClaudeInvoker = Callable[[str], str]`, returns raw Claude text) — the shape `escalate_to_split.invoker` expects. Do **not** reuse launcher's run-step `Invoker = Callable[[str], tuple[int, str]]`.
- **Treat `state.yes_to_all` as unattended — never auto-confirm a split.** Do **not** synthesize a `"y"` `prompt_fn` under `state.yes_to_all`; a blanket fast-forward must not substitute for a genuine per-split confirm (invariant 2: `--yes`/`yes_to_all` is an *unattended* path that must not satisfy the interactive-confirm gate). Force recommend-only when `state.yes_to_all` by passing `allow_split=False` to the bridge, so the escalation short-circuits to a recommendation before spending Claude on apply. Always pass `prompt_fn=None`, so the only apply path is a genuine interactive `builtins.input` confirm on a TTY; on a non-TTY that auto-declines (→ recommend). This deliberately differs from `_dispatch_apply_finding`/`_dispatch_file_check_create`, which *do* fast-forward under `state.yes_to_all` — a prose apply is reversible, an unattended structure mutation is not.
- **Guard plan-level findings (no target step) before escalating.** The builder-level `allow_structural_verdict` offers `BLOCKED-STRUCTURAL` to *every* apply-eligible finding, including plan-level ones (`rec.step_id is None` — e.g. `plan-correctness`/`plan-completeness`) that name no concrete step. `escalate_to_split` needs a step to split, and `step_by_id(None)` would `KeyError` → the confusing `step-missing` "step None not found." So if `rec.step_id is None`, do **not** call `escalate_to_split`: return a recommend-only status like `f"plan-level structural verdict on {rec.id}: no single target step to split — re-decompose by hand"`. The split engine is step-scoped; a plan-level structural verdict is an operator-level re-decompose signal, surfaced (not silently dropped, per invariant 1), not an `escalate_to_split` target.
- Otherwise (`rec.step_id is not None`) call `result = escalate_to_split(plan_path, step_id=rec.step_id, repo_root=ctx.repo_root, invoker=shell_claude_invoker, allow_split=(allow_split and not state.yes_to_all), prompt_fn=None)`.
- Map `result.outcome` (exactly one of `applied` / `recommended` / `unsafe` / `proposal-unusable` / `step-missing`) to a one-line status string. Read `result.recommendation` only under `recommended` and `result.blocking` only under `unsafe` (the bridge field-disciplines them):
  - `applied` → e.g. `f"escalated structural finding: applied a 2-step split at step {result.target_id}"`.
  - `recommended` → surface the more-correct plan, e.g. `f"escalated structural finding to a split recommendation: {result.recommendation.suggested_action}"` (points the operator at `plan-tool split`).
  - `unsafe` → name the blockers, e.g. `f"structural escalation unsafe — downstream steps {result.blocking} are not PENDING; resolve them, then run plan-tool split"`. `recommendation` is `None` on this outcome (the recommended `plan-tool split` would itself be blocked by the same steps), so do not dereference it.
  - `proposal-unusable` → `"structural escalation: split proposal unusable; left as-is"`.
  - `step-missing` → `f"structural escalation: step {rec.step_id} not found; nothing escalated"`.

**Foundational logic + shared locations.** This step's core rule is "a `BLOCKED-STRUCTURAL` apply verdict routes to `escalate_to_split`." The other consumer of that verdict is `plan_tool/detail.py:generate_detail`'s in-loop convergence path (step 7) — a parallel call site, not a duplicate to consolidate here; it owns the in-loop renumbering contract this walk deliberately does not (see Deferred). The completeness summary's blocked rollups in `plan_tool/completeness_report.py` (`a.verdict == "BLOCKED"` filters and `blocked_ct`) exclude `BLOCKED-STRUCTURAL`; widening those is out of scope for this step — left to reconcile (see Deferred).

## Tests

All in `tests/cli/test_review_actions.py`, in a new `TestStructuralEscalation` class. Follow the file's split-proof conventions: import `_build_review_action_fn` from `plan_tool.cli`, build with a directly-constructed `PlanToolContext`. The two seams bind at different times, so patch them differently: `escalate_to_split` is bound in the builder's build-time body-local `from plan_tool.launcher import (...)` block, so patch it **before** building; `plan_tool.create.shell_claude_invoker` is imported at dispatch time inside `_dispatch_structural_escalation` (binds later), so it usually needs no patch — stubbing `escalate_to_split` keeps the real invoker from ever being called. Stub `apply_finding` to return a `SimpleNamespace` with `verdict="BLOCKED-STRUCTURAL"`, and stub `escalate_to_split` to return a `SimpleNamespace`-style `EscalateResult` per case.

- `test_blocked_structural_reverts_before_escalating` — `apply_finding` returns `BLOCKED-STRUCTURAL` with a non-empty `pre_snapshot`; assert `_revert_snapshot` is called with that `pre_snapshot` **before** `escalate_to_split` (record call order), and `escalate_to_split` is called exactly once.
- `test_blocked_structural_routes_past_empty_diff_noop` — `verdict="BLOCKED-STRUCTURAL"` with `diff_text=""`; assert the result is the escalation status, **not** the "reported APPLIED but the plan file didn't change" no-op (ordering guard).
- `test_escalation_applied_outcome` — `escalate_to_split` returns `outcome="applied", target_id=4`; assert status names an applied split at step 4.
- `test_escalation_applied_refreshes_drift_baseline` — build with `allow_split=True`; `escalate_to_split` returns `outcome="applied"`; assert the arm refreshes the reconcile drift baseline (`iter_lock` `refresh_snapshot`) instead of leaving the `"reverted"` disposition, so the landed split is not re-detected as drift by the next finding's pre-apply `check_drift`. Pins the drift-refresh contract even while the production `allow_split=True` opt-in stays deferred.
- `test_escalation_recommended_outcome` — `outcome="recommended"` with a `structural-split` rec whose `suggested_action` names `plan-tool split`; assert status surfaces that action and nothing is mutated.
- `test_escalation_unsafe_outcome` — `outcome="unsafe", blocking=[5, 6], recommendation=None`; assert status names steps 5 and 6 and does not dereference `recommendation`.
- `test_escalation_proposal_unusable_and_step_missing` — the two terminal outcomes return their distinct fixed strings.
- `test_plan_level_verdict_not_escalated` — a `BLOCKED-STRUCTURAL` finding with `rec.step_id is None` (a plan-level source) is **not** passed to `escalate_to_split` at all (assert it is never called); the status names a plan-level re-decompose, so a plan-level verdict never reaches `step_by_id(None)`.
- `test_escalation_passes_proposer_and_allow_split` — build with `allow_split=True`; assert `escalate_to_split` is called with `invoker=create.shell_claude_invoker` and `allow_split=True`, `prompt_fn=None` (no `yes_to_all`).
- `test_escalation_yes_to_all_forces_recommend_only` — `state.yes_to_all=True` built with `allow_split=True`; assert `escalate_to_split` is called with `allow_split=False` and `prompt_fn=None` (a blanket yes-to-all never auto-confirms a split).
- `test_reverted_disposition_suppresses_scope_and_drift` — build with a `reconcile_scope_guard` whose scope-eval/drift helpers are rigged to raise (or spied for zero calls); a `BLOCKED-STRUCTURAL` apply must leave them un-called because `phase_outcome` is `"reverted"`.
- `test_allow_split_threads_into_detail_reconcile_subwalks` — spy on `_build_review_action_fn` (or assert via the recursive build) that both sub-walk builds inside `_dispatch_detail_reconcile` receive `allow_split` matching the parent.
- `test_non_structural_verdict_never_escalates` — an ordinary `APPLIED` finding with a real diff never calls `escalate_to_split` (no-op guard for the production path).
- `test_builder_allow_split_defaults_false` — building without the keyword leaves `allow_split` `False`, so a `BLOCKED-STRUCTURAL` apply calls `escalate_to_split(..., allow_split=False)` (recommend-only by default).

### Test-creation order (feature step)

This is a **feature** step. Add every test above **with** the implementation, not after. Green-before-done gate: all new `TestStructuralEscalation` cases pass, and the existing terminal-row tests in `TestActionMatrixTerminalRows` and `TestOperatorFeedbackSteersApply` stay green unchanged. Run `uv run pytest tests/cli/test_review_actions.py -q` before considering the step done.

## Acceptance criteria

- `_build_review_action_fn` accepts `allow_split: bool = False`; `_dispatch_detail_reconcile`'s two recursive builds pass `allow_split=allow_split`.
- `_build_review_action_fn` accepts `allow_structural_verdict: bool = False` and `_dispatch_apply_finding` passes it on its `apply_finding(...)` call; the `review`/reconcile call site sets it ON (`cmd_completeness_apply` leaves it OFF), so the rendered prompt offers `BLOCKED-STRUCTURAL` on the routed path — step 3's flag is flipped ON here, not left at the OFF default.
- `_dispatch_apply_finding`, given `result.verdict == "BLOCKED-STRUCTURAL"`, calls `_revert_snapshot(result.pre_snapshot)` then `escalate_to_split` exactly once, and the `BLOCKED-STRUCTURAL` arm is ordered before the `("BLOCKED", "NOT-APPLICABLE")` arm.
- A `BLOCKED-STRUCTURAL` apply with a non-applying outcome sets `phase_outcome = "reverted"`, so the `finally` scope-guard eval and post-apply drift check do not run; an `applied` outcome instead refreshes the reconcile drift baseline (`iter_lock` `refresh_snapshot`) so the landed split is not re-detected as drift by the next finding's pre-apply `check_drift`.
- `_dispatch_structural_escalation` always passes `invoker=create.shell_claude_invoker` and `prompt_fn=None`; under `state.yes_to_all` it forces `allow_split=False` (recommend-only — never auto-confirms a split), and returns a distinct status string for each of the five `EscalateResult.outcome` values.
- A `BLOCKED-STRUCTURAL` finding with `rec.step_id is None` (plan-level) is **not** passed to `escalate_to_split` (no `step_by_id(None)` KeyError); it returns a recommend-only "no single target step — re-decompose by hand" status, surfaced (not silently dropped).
- An ordinary `APPLIED` finding never calls `escalate_to_split`.
- The `_build_review_action_fn(...)` call sites in `review_cmd.py` (394/476/559) and `reconcile.py` (564/673/1856) pass `allow_structural_verdict=True`; `completeness_cmd.py`'s call site (338) is left at the OFF default and unedited.
- `tests/cli/test_review_actions.py` passes; the only modules edited are `review_actions.py`, `review_cmd.py`, and `reconcile.py`.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — the shape of `EscalateResult` (frozen dataclass, field-disciplined `recommendation`/`blocking`) this step consumes from step 4.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — patching `plan_tool.launcher.escalate_to_split` / `plan_tool.create.shell_claude_invoker` before building the action fn so no real `claude` binary spawns.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — fixtures/markers for the unit tests; these terminal/dispatch tests are unmarked (fast, isolated).

## Deferred

- **A CLI flag to set `allow_split=True` on the review/reconcile walk** — not wired here; all call sites inherit the `False` default, so the walk recommends-only today (the bridge short-circuits to recommend before spending Claude when `allow_split` is `False`). Left for a follow-up that adds the operator opt-in.
- **Re-collect-after-renumber in the interactive walk** — `escalate_to_split` renumbers step ids when it applies a split, but the review walk (unlike the `create`/`detail` convergence loops) does not re-collect findings mid-walk, so recs queued later in the same walk can point at shifted ids. Known gap, mirrors `_dispatch_file_check_create`'s existing mid-walk plan mutation; tracked for follow-up if it proves noisy.
- **Widening `plan_tool/completeness_report.py` blocked rollups** (`a.verdict == "BLOCKED"` filters, `blocked_ct`, the "split into sub-steps" headline) to include `BLOCKED-STRUCTURAL` — out of this step's two-file set; routed to reconcile.
- **Steps 3 and 4 are prerequisites** — this step consumes the `BLOCKED-STRUCTURAL` parser token (step 3) and the `escalate_to_split`/`EscalateResult` bridge (step 4). Confirm both are at HEAD before implementing; until then the verdict can't be produced and the import would fail.
