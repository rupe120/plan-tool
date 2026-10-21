> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add merge_bridge around merge_steps

## Summary

This step adds a gated apply-or-recommend wrapper around `plan_tool/detail.py:merge_steps`. The primary code edit is `plan_tool/detail.py`, with focused coverage added to the merge cluster in `tests/test_detail.py`. The key design decision is to let `merge_steps` remain the structural executor and put confirmation, opt-in, and outcome mapping in a new `merge_bridge` layer. On green, callers can ask for a merge remedy and receive a structured result for applied, recommended, unsafe, or invalid inputs without duplicating merge validation or prompting inside `merge_steps`.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why the existing merge executor needs a bridge.
- [Files creates vs edits](#files-creates-vs-edits) — The exact file footprint for this step.
- [Implementation](#implementation) — The required bridge behavior and constraints.
- [Tests](#tests) — The focused unit coverage to add.
- [Acceptance criteria](#acceptance-criteria) — Observable checks for done.
- [References](#references) — Relevant Python and pytest docs.
- [Deferred](#deferred) — Related routing and documentation work left to later steps.

## Why

`plan_tool/detail.py:merge_steps` already performs the structural merge, detail migration, and merged-detail re-authoring, but it is an executor, not a reconcile-walk bridge. It raises `DetailError` on refused inputs and deliberately never prompts; that is correct for the direct merge command, but awkward for an automated walk that needs “recommend by default, apply only when explicitly allowed, and report why nothing changed.” This step adds the missing bridge layer beside the merge primitives so later routing can call one stable function and get a structured outcome without re-implementing merge validation, safety checks, or confirmation policy.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/detail.py` — Add a frozen merge bridge result type and a `merge_bridge` function near the existing merge cluster: `_merge_is_safe`, `_confirm_merge`, `MergeResult`, and `merge_steps`.
  - `tests/test_detail.py` — Extend the existing merge-cluster tests that already import `MergeResult`, `_confirm_merge`, `_merge_is_safe`, and `merge_steps`.

## Implementation

Foundational logic: **apply-or-recommend merge gate**.

- **Keep `merge_steps` as the only structural merge executor.** `plan_tool/detail.py:merge_bridge` should call `merge_steps` for safe preview and real application. Do not copy the merge assembly, `_apply_step_merge` call, downstream detail migration, folded-body authoring, or archive behavior into the bridge.

- **Add a frozen result type beside `MergeResult`.** A name like `MergeBridgeResult` fits the existing `plan_tool/launcher.py:EscalateResult`, `plan_tool/scope_out.py:ScopeOutResult`, and `plan_tool/reground.py:RegroundResult` pattern. It should carry an `outcome` string and enough structured data for a caller to render what happened: the requested ids, blocking ids for unsafe/refused paths, and the `MergeResult` when a preview or apply result exists.

- **Use four bridge outcomes.** The bridge needs these outcomes:
  - `applied` — the merge was confirmed and `merge_steps` mutated the plan.
  - `recommended` — the merge is valid and safe, but `allow_merge=False` or confirmation declined.
  - `unsafe` — the requested merge would renumber or fold a non-`PENDING` member/downstream step; report the blocking ids from `_merge_is_safe`.
  - `invalid` — malformed inputs that `merge_steps` refuses, such as fewer than two distinct ids, unknown ids, non-canonical numbering, mixed scope, or an invalid merge graph.

- **Let `merge_steps(..., dry_run=True, author_details=False)` be the validation and preview gate.** Do not duplicate its malformed-input guards in `merge_bridge`; call the dry-run path to validate the requested merge and produce the recommended-path `MergeResult` without spending Claude. A caught `DetailError` from that gate should become a structured refusal, not escape to a reconcile-walk caller.

- **Expose unsafe without re-listing merge validation.** `plan_tool/detail.py:_merge_is_safe` is the run-state classifier the bridge should surface as `unsafe`, but `merge_steps(..., dry_run=True, author_details=False)` remains authoritative for malformed inputs such as fewer than two distinct ids, unknown ids, non-canonical numbering, mixed scope, and invalid merge graphs. Use `_merge_is_safe` only to classify run-state blockers for a requested set that has passed the merge validation gate, or in the narrow refusal path where the bridge can attribute a dry-run refusal to those blockers; otherwise map dry-run `DetailError` to `invalid`.

- **Keep confirmation in the bridge.** `plan_tool/detail.py:_confirm_merge` already owns the interactive merge prompt and defaults to no for non-TTY callers. `merge_bridge` should forward `prompt_fn`/`yes` behavior consistently with the other bridges: no prompt when `allow_merge=False`, auto-apply only when an explicit `yes=True` is passed, and otherwise call `_confirm_merge` before the real `merge_steps` call. If `yes=True`, bypass the prompt but still run all validity and safety gates.

- **Forward the real merge seams.** The applied branch should call `merge_steps` with the caller’s `repo_root`, `invoker`, `reporter`, `run_logger`, `prompt_fn`, and `budget` so merged detail authoring keeps the same behavior as direct merge execution. The preview/recommended path should not spend Claude; use `author_details=False` on dry-run.

- **Do not mint a `Recommendation`.** Unlike `plan_tool/launcher.py:escalate_to_split`, the merge bridge will be called from an already-existing `granularity-merge` finding. Return only the bridge result and any preview/apply `MergeResult`.

- **Do not wire review dispatch here.** `plan_tool/review_walk.py:merge_remedy_target` and `plan_tool/cli/review_actions.py:_dispatch_reground_remedy` already show where later dispatch lives, but this step’s declared files are only `plan_tool/detail.py` and `tests/test_detail.py`.

## Tests

- `test_merge_bridge_recommends_without_opt_in` — valid safe ids return `recommended`, include a dry-run preview, do not mutate the plan, and do not call the detail invoker.
- `test_merge_bridge_applies_when_allowed_and_confirmed` — valid safe ids with `allow_merge=True` and `yes=True` call the real merge path and return `applied` with the underlying `MergeResult`.
- `test_merge_bridge_declined_confirm_recommends` — valid safe ids with `allow_merge=True` but a declined prompt return `recommended` and leave the plan unchanged.
- `test_merge_bridge_unsafe_reports_blocking_ids` — a non-`PENDING` member or downstream step returns `unsafe` with blocking ids and does not mutate.
- `test_merge_bridge_invalid_maps_detail_error` — malformed merge ids return `invalid` rather than raising `DetailError`.
- `test_merge_bridge_mints_no_recommendation` — the result type does not carry or create `plan_tool.review.Recommendation`.

### Test-creation order (feature step)

Add the `tests/test_detail.py` bridge tests with the implementation, using the existing `_build_merge_plan` helper and `_GOOD_BODY` fixture where authoring is needed. Every new merge-bridge test must be green before this step is finished, along with the existing `TestMergeIsSafe`, `TestConfirmMerge`, and `TestMergeSteps` coverage.

## Acceptance criteria

- `plan_tool/detail.py` exposes a `merge_bridge` function beside `merge_steps`.
- `merge_bridge` returns a frozen structured result for `applied`, `recommended`, `unsafe`, and `invalid` paths.
- `merge_bridge(..., allow_merge=False)` performs no disk mutation and spends no Claude.
- `merge_bridge(..., allow_merge=True, yes=True)` applies a safe merge through `merge_steps`.
- Unsafe run-state blockers are reported as `unsafe`, not as uncaught `DetailError`.
- Malformed merge requests are reported as `invalid`, not as uncaught `DetailError`.
- `tests/test_detail.py` covers the bridge outcome matrix and passes with the existing merge tests.

## References

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Use for the frozen bridge result type, matching the existing result objects.
- [typing — Support for Type Hints](https://docs.python.org/3/library/typing.html) — Use for optional fields and callable seams on the bridge signature.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Use for prompt, TTY, and invoker isolation in the bridge tests.
- [unittest.mock — Mock Object Library](https://docs.python.org/3/library/unittest.mock.html) — Useful if the tests patch merge or authoring seams instead of using simple stubs.

## Deferred

- `plan_tool/review_walk.py` dispatchability — Later routing should parse merge directives and decide when a finding is dispatchable.
- `plan_tool/cli/review_actions.py` merge dispatch — Later work should route `MERGE_ACTION_MERGE` to `merge_bridge` and keep `MERGE_ACTION_REGROUND` on `reground_bridge`.
- CLI/docs updates — This step adds the callable bridge only; user-facing reconcile-walk behavior and documentation belong to later steps.
