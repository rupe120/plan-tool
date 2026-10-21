# Step 6 — Route `BLOCKED-STRUCTURAL` apply verdicts to `escalate_to_split` in the review apply walk (escalate when interactive + opt-in, else recommend)

## Summary

- **Teaches `_dispatch_apply_finding` in `plan_tool/cli/review_actions.py` a new verdict branch** for the `BLOCKED-STRUCTURAL` token (minted in step 2): revert apply_finding's partial edit, then route the finding's target step to `launcher.escalate_to_split` (step 3) instead of falling through to the existing empty-diff no-op arm.
- **The bridge decides apply-vs-recommend; this branch only plumbs it.** Escalation applies an in-place split only when interactive (TTY, checked inside `escalate_to_split`) AND the walk was built with the new `allow_split=True` opt-in; every other path surfaces the bridge's `Recommendation` and changes nothing.
- **Primary files:** `plan_tool/cli/review_actions.py` (new `allow_split` param on `_build_review_action_fn` + a `_dispatch_structural_escalation` helper + the verdict branch) and `tests/cli/test_review_actions.py` (the new branch's cases).
- **Most important design decision:** the branch reverts apply_finding's snapshot and sets `phase_outcome = "reverted"` before escalating, so the per-finding scope-guard and drift post-checks in the `finally` block (gated on `phase_outcome == "success"`) never run against the bridge's structural write — which deliberately mutates `plan_path` + detail files, outside the `step.files` set those checks watch. Note the separate `record_apply(result.pre_snapshot)` call (not gated on `phase_outcome`) still records the pre-apply snapshot, which diverges from disk after the bridge writes a split; this is inert today (no call site pairs `reconcile_scope_guard` with `allow_split=True`) but must be revisited before `--split` is wired into the reconcile-iterate path (see Deferred).
- **On green:** a `BLOCKED-STRUCTURAL` verdict with `allow_split=True` + a stubbed `escalate_to_split` returning `outcome="applied"` reports the new step ids and records the rec applied; with `allow_split` off (the production default) it records `skip` and surfaces the split recommendation, leaving the plan unchanged.

## Table of Contents

- [Why](#why) — what dead-ends today and why this branch closes the loop
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — the `allow_split` param, the verdict branch, the escalation helper, the invoker seam
- [Tests](#tests) — branch cases added to `tests/cli/test_review_actions.py`
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors on green
- [References](#references) — Python `sys`/`io` TTY semantics and pytest fixtures
- [Deferred](#deferred) — CLI `--split` flag wiring, mid-walk stale-rec handling, the source rename

## Why

A `BLOCKED-STRUCTURAL` verdict tells the caller that Claude, mid-apply, judged the only correct fix to be splitting the step into a refactor + feature pair — something `apply_finding` (a prose editor) cannot do. Step 2 made that token parseable and emittable; step 3 built `launcher.escalate_to_split` to act on it. But the review apply walk in `plan_tool/cli/review_actions.py:_dispatch_apply_finding` still has no branch for it: a `BLOCKED-STRUCTURAL` result is not in the `("BLOCKED", "NOT-APPLICABLE")` tuple, so it falls through to the empty-diff arm and reports the misleading `"apply-finding reported APPLIED but the plan file didn't change; nothing to keep"` (the interim behavior step 2's Deferred section flagged). This step wires the verdict to the bridge so a structural finding surfaced during the walk finishes its life as a split (interactive + opt-in) or a recorded recommendation (everything else), instead of a confusing no-op.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — add `allow_split: bool = False` to `_build_review_action_fn`; add `escalate_to_split` to the builder-top body-local `from plan_tool.launcher import (...)` block; add a `_dispatch_structural_escalation(rec)` closure; add the `if result.verdict == "BLOCKED-STRUCTURAL":` branch inside `_dispatch_apply_finding`; propagate `allow_split=allow_split` on the two recursive `_build_review_action_fn` calls inside `_dispatch_detail_reconcile`.
  - `tests/cli/test_review_actions.py` — add a `TestBlockedStructuralEscalation` class.

## Implementation

### `plan_tool/cli/review_actions.py`

**Add the opt-in parameter.** Give `_build_review_action_fn` a new keyword `allow_split: bool = False`, placed beside the existing `yes: bool = False`. The default keeps every current call site unchanged (`review_cmd.py`, `reconcile.py`, `completeness_cmd.py`, and the two recursive sub-walk builds all omit it → `False`). It is the review-walk twin of `generate_detail`'s / `create_plan`'s `allow_split` from step 5 — the operator opt-in that gates in-place structural edits.

**Propagate it on the recursive builds.** The two `_build_review_action_fn(...)` calls inside `_dispatch_detail_reconcile` (the saved-reuse sub-walk and the fresh-run sub-walk) build the sub-action handler for a nested detail-reconcile walk. Pass `allow_split=allow_split` on both so a structural verdict surfaced inside a nested walk inherits the same opt-in as the parent.

**Extend the builder-top body-local launcher import.** The block already body-local-imports `apply_finding, run_step as _run_step`. Add `escalate_to_split`:

```
from plan_tool.launcher import (
    apply_finding,
    escalate_to_split,
    run_step as _run_step,
)
```

- **Body-local placement is required and patchable.** `escalate_to_split` resolves at build time from `plan_tool.launcher`, exactly like `apply_finding` — so a test patches `plan_tool.launcher.escalate_to_split` *before* building the action fn and the closure binds the stub. This matches the existing `test_apply_finding_consumes_and_clears_operator_feedback` pattern (patch `plan_tool.launcher.apply_finding`, then build).

**Add the `_dispatch_structural_escalation(rec)` closure**, defined beside `_dispatch_apply_finding` (it is the structural sibling of the prose-apply dispatcher). It reads the closure variables `state`, `allow_split`, `plan_path`, `ctx`, `plan_name`. Behavior:

- **Guard a missing step target.** `target_step_id = rec.step_id`; if `None`, set `state.apply_skip = True` and return a message that the structural finding names no step to split, leaving it for manual review. `escalate_to_split` needs a concrete `step_id`, and a plan-wide rec (`step_id is None`) has no single step to restructure.
- **Resolve the proposer seam.** Body-local `from plan_tool.create import shell_claude_invoker`. This is `create.ClaudeInvoker = Callable[[str], str]` — the split-**proposer** shape `escalate_to_split` expects, **not** launcher's run-step `Invoker = Callable[[str], tuple[int, str]]`. The import is body-local because it is only the value handed to the bridge; tests that stub `escalate_to_split` never call it, so the `tests/conftest.py` autouse real-binary gate never fires.
- **`yes_to_all` is unattended → recommend-only; never synthesize an auto-confirm.** A `yes_to_all` apply-all walk is an unattended path, so per plan invariant (2) "never mutate structure unattended" it must not drive `escalate_to_split` to mutate plan structure. Do **not** build an auto-confirm `prompt_fn`; leave `prompt_fn=None`. Instead, when `state.yes_to_all`, force the bridge's recommend-only branch by passing `allow_split=False` regardless of the builder opt-in. Only a genuine interactive walk (`not state.yes_to_all`) with `allow_split=True` reaches the bridge's apply gate, where `escalate_to_split` runs its own TTY + `_confirm_split` check for real operator assent. This diverges deliberately from `_dispatch_apply_finding`'s `state.yes_to_all → answer = "y"`: a prose edit is reversible and in-scope, but a structural split is neither, so apply-all recommends it rather than auto-confirming it.
- **Confirm the bridge contract against landed code first.** The `escalate_to_split` call signature, the `EscalateResult` field names (`new_ids`, `recommendation`), and the six outcome-label strings (`"applied"`, `"recommended"`, `"unsafe"`, `"split-failed"`, `"proposal-unusable"`, `"step-missing"`) below are transcribed from step 3's sibling detail (`03-launcher-escalate-split-bridge-safe.md`), a pre-implementation guess. Before wiring, read step 3's **landed** code in `plan_tool/launcher.py` at HEAD and confirm the exported signature (keyword-only params), the `EscalateResult` field names, and the exact outcome-label strings — match the implementation, not this detail file, where they disagree.
- **Call the bridge:**
  ```
  # yes_to_all is unattended: force recommend-only so an apply-all walk
  # never silently mutates plan structure, regardless of the opt-in.
  effective_allow_split = allow_split and not state.yes_to_all
  res = escalate_to_split(
      plan_path,
      step_id=target_step_id,
      repo_root=ctx.repo_root,
      invoker=shell_claude_invoker,
      allow_split=effective_allow_split,
      prompt_fn=None,
  )
  ```
- **Branch on `res.outcome`:**
  - `"applied"` — the split landed and the plan was renumbered. Return a message naming `res.new_ids` (e.g. `f"escalated BLOCKED-STRUCTURAL to a split on step {target_step_id}: new steps {res.new_ids}"`). **Do not** set `state.apply_skip` — the structural fix resolved the finding, so the walk records it applied.
  - everything else (`"recommended"`, `"unsafe"`, `"split-failed"`, `"proposal-unusable"`, `"step-missing"`) — nothing changed via this rec. Set `state.apply_skip = True` (walk records `skip`, leaving the rec for manual handling) and return a message surfacing `res.recommendation.suggested_action` (or `.title`) when `res.recommendation is not None`, else a generic "no split applied — run `plan-tool split`" note.

**Add the verdict branch inside `_dispatch_apply_finding`.** Place a dedicated `if result.verdict == "BLOCKED-STRUCTURAL":` branch immediately **before** the existing `if result.verdict in ("BLOCKED", "NOT-APPLICABLE"):` branch (and therefore before the `if not result.diff_text:` empty-diff arm it would otherwise fall through to). It sits after the scope-guard `record_apply(result.pre_snapshot)` call, at the same nesting level as the other verdict arms:

```
if result.verdict == "BLOCKED-STRUCTURAL":
    # Claude judged mid-apply that the only correct fix is a structural
    # split, not a prose edit. Revert any partial edit (apply_finding
    # can't restructure a plan), then route to the split bridge:
    # escalate when interactive + opt-in, else surface a recommendation.
    _revert_snapshot(result.pre_snapshot)
    phase_outcome = "reverted"
    return _dispatch_structural_escalation(rec)
```

- **Revert first, escalate second.** `_revert_snapshot` (the body-local `_restore_text_files as _revert_snapshot`) restores `plan_path` to its pre-apply state so the bridge re-parses clean state from disk. `escalate_to_split` re-parses the plan itself, so the order matters.
- **`phase_outcome = "reverted"` is the most important line in this branch.** It is the apply_finding-edit's disposition (its edit was reverted), and it keeps the `finally` block's per-finding scope-guard eval and post-apply drift check from running — both gate on `phase_outcome == "success"`. The bridge's own write (on `outcome="applied"`) mutates `plan_path` + detail files, which sit outside the `step.files` set those checks watch, so there is nothing for them to evaluate; skipping them avoids a spurious out-of-scope revert of the legitimate split. The `work_landed_in_loop` flag (also gated on `"success"`) likewise stays unset, correctly — the prose apply did not land.
- **No routing change in `action()`.** A finding that yields `BLOCKED-STRUCTURAL` is an ordinary apply-eligible rec (`should_apply_as_finding(rec)` is true) that Claude reclassifies *during* apply; it reaches `_dispatch_apply_finding` through the unchanged `action()` ladder. This branch lives entirely inside the verdict handling.

**Foundational logic + shared locations.** The core behavior added is "a `BLOCKED-STRUCTURAL` apply verdict routes to `escalate_to_split`." Grep confirms the only other consumers of `escalate_to_split` are step 5's convergence loops in `plan_tool/create.py:create_plan` and `plan_tool/detail.py:generate_detail` — both reached through their own loop bodies, not this walk. There is no duplicated routing block to consolidate; this step adds the third and final caller of the single bridge. The verdict-token parsing itself is single-sourced in `plan_tool/launcher.py:parse_apply_verdict` (step 2) and is not touched here.

## Tests

All cases live in a new `TestBlockedStructuralEscalation` class in `tests/cli/test_review_actions.py`. Follow the file's split-proof convention: build the action fn directly with a `PlanToolContext`, patch only domain-module attributes (`plan_tool.launcher.apply_finding`, `plan_tool.launcher.escalate_to_split`) **before** building, never a `plan_tool.cli` global. The shared `fake_apply_finding` returns a `SimpleNamespace(exit_code=0, verdict="BLOCKED-STRUCTURAL", diff_text="", summary="", pre_snapshot={}, introduced_findings=(), resolved_findings=())`; an empty `pre_snapshot` makes the real `_restore_text_files` a no-op. A `fake_escalate` captures its kwargs and returns a `SimpleNamespace` shaped like `EscalateResult` for the outcome under test.

### Test-creation order (feature step)

This is a **feature** step. Add each test with the implementation; every one must be green before the step is done (green-before-done gate):

- `test_blocked_structural_recommends_when_not_opt_in` — `allow_split` defaulted off; `fake_escalate` returns `outcome="recommended"` with a `Recommendation` carrying a `suggested_action`. Asserts `escalate_to_split` was called once with `allow_split=False`, `step_id=rec.step_id`, `repo_root=ctx.repo_root`; the returned message contains the recommendation's `suggested_action`; `state.apply_skip is True`.
- `test_blocked_structural_escalates_when_opt_in` — `allow_split=True`; `fake_escalate` returns `outcome="applied"` with `new_ids=[3, 4]`. Asserts `escalate_to_split` called with `allow_split=True`; the message names the new ids; `state.apply_skip` stays falsy (walk records applied).
- `test_blocked_structural_reverts_apply_edit` — spy on `plan_tool.launcher._restore_text_files`; assert it was called with the result's `pre_snapshot` before `escalate_to_split`, proving the prose edit is reverted prior to escalation.
- `test_blocked_structural_no_step_id_skips` — `rec.step_id = None`. Asserts `escalate_to_split` is **never** called, `state.apply_skip is True`, and the message says the finding names no step to split.
- `test_blocked_structural_passes_proposer_invoker` — assert the `invoker` kwarg captured by `fake_escalate` is `plan_tool.create.shell_claude_invoker` (identity), pinning the proposer seam wiring and that it is not launcher's run-step `Invoker`.
- `test_blocked_structural_yes_to_all_recommends_only` — `state.yes_to_all = True` **and** `allow_split=True`; assert `escalate_to_split` is called with `allow_split=False` (forced recommend-only) and `prompt_fn=None`, so an apply-all walk never auto-confirms a structural split and never mutates plan structure unattended.
- `test_blocked_structural_recommend_records_skip_no_mutation` — with a `tmp_path` plan file written to disk and `fake_escalate` returning `outcome="recommended"` (no real bridge), assert the plan file bytes are unchanged after the action and `state.apply_skip is True`.

Note: `escalate_to_split`'s own per-branch behavior (applied / recommended / unsafe / split-failed / proposal-unusable / step-missing) is pinned in `tests/test_launcher.py::TestEscalateToSplit` (step 3); `parse_apply_verdict` returning `BLOCKED-STRUCTURAL` is pinned in `tests/test_launcher.py::TestParseApplyVerdict` (step 2). These review-walk tests stub the bridge and cover only the dispatch wiring, not the split mechanics — no duplication.

## Acceptance criteria

- `_build_review_action_fn` accepts `allow_split: bool = False`; all existing call sites still build without passing it.
- A `BLOCKED-STRUCTURAL` apply verdict no longer falls through to the empty-diff `"...didn't change; nothing to keep"` message — it calls `escalate_to_split` with `allow_split` forwarded from the builder, `step_id=rec.step_id`, `repo_root=ctx.repo_root`, and `invoker=create.shell_claude_invoker`.
- A `yes_to_all` apply-all walk forces recommend-only: `escalate_to_split` is called with `allow_split=False` (regardless of the builder opt-in) and `prompt_fn=None`, so apply-all never mutates plan structure unattended.
- `escalate_to_split` returning `outcome="applied"` yields a message naming the new step ids and leaves `state.apply_skip` falsy (rec recorded applied); any other outcome sets `state.apply_skip = True` and surfaces the recommendation.
- The branch reverts apply_finding's `pre_snapshot` (via `_restore_text_files`) and sets `phase_outcome = "reverted"` before escalating, so the `finally` scope-guard and drift post-checks do not run for the structural path.
- A `BLOCKED-STRUCTURAL` rec with `step_id is None` skips escalation, records `skip`, and reports the missing step target.
- `uv run pytest tests/cli/test_review_actions.py -q` passes, and the existing review/reconcile suites stay green.

## References

- [sys — System-specific parameters and functions (Python 3 docs)](https://docs.python.org/3/library/sys.html) — `sys.stdin.isatty()` is the interactive gate the bridge checks; this gate lives inside `escalate_to_split` and is pinned by step 3's `TestEscalateToSplit`, not by this step's tests, which stub the bridge.
- [io — IOBase.isatty (Python 3 docs)](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — authoritative semantics of `isatty()` on stream objects, for reasoning about the TTY-vs-unattended branch the bridge owns.
- [How to use fixtures — pytest](https://docs.pytest.org/en/stable/how-to/fixtures.html) — `tmp_path` plan fixtures and `monkeypatch` overrides used to neutralize `apply_finding` / `escalate_to_split` so the dispatch tests never spawn the real `claude` binary.
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — `monkeypatch.setattr` against the launcher domain module, the mechanism the split-proof convention requires for stubbing body-local-imported symbols.

## Deferred

- **Exposing `--split` on `review` / `reconcile-plan-walk` at the CLI layer** (`plan_tool/cli/parser.py` + the handlers in `plan_tool/cli/review_cmd.py`, `reconcile.py`, `completeness_cmd.py`) — the opt-in defaults `False`, so production review walks recommend-only until a flag threads `allow_split` through, mirroring step 5's deferral of create's `--split`. Out of this step's scope.
- **Stale downstream recs after an in-walk applied split** — `escalate_to_split` renumbers step ids, so recs queued later in the same walk may point at shifted ids. This matches the existing mid-walk mutation in `_dispatch_file_check_create` (which also writes the plan); the convergence loops (step 5) re-collect after a split, but the interactive walk does not. Tracked for a follow-up if it proves noisy in practice.
- **Renaming the `detail-purity` source to `granularity-split`** across the classifier and call sites — postponed per the plan's Deferred section; this branch keys on the `BLOCKED-STRUCTURAL` *verdict* (step 2), independent of the finding's source token.
- **`record_apply` snapshot divergence after an in-walk applied split** — the unconditional `record_apply(result.pre_snapshot)` (not gated on `phase_outcome`) records the pre-apply snapshot, which diverges from disk once the bridge writes a split, so a reconcile-iteration collision sidecar would not skip the legitimate split. Inert today (no call site pairs `reconcile_scope_guard` with `allow_split=True`); must be addressed when `--split` is wired into the reconcile-iterate path, by gating or refreshing the recorded snapshot on the `outcome="applied"` structural write.
- **Detail-less halves after an in-walk applied split** — an `outcome="applied"` escalation writes two new `detail=None` step halves to the plan, but this review apply walk does not re-author them (unlike step 5's convergence loops, which keep the `half_ids`/`generate_detail(...)` re-authoring loop). The split halves are left detail-less until a later `plan-tool detail` pass. Inert today (the `--split` opt-in is unexposed at the CLI layer), but must be resolved when `--split` is exposed for `review` — by re-authoring the new halves after the applied split or directing the operator to run `plan-tool detail`.
