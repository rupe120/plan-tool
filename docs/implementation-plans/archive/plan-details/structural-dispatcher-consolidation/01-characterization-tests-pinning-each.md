> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Pin each structural dispatcher's WalkState and status output before the extraction

## Summary

Add characterization tests to `tests/cli/test_review_actions.py` that pin the *complete* post-call `WalkState` — not just the returned status string — for every outcome of all four structural dispatchers built by `plan_tool/cli/review_actions.py`'s `_build_review_action_fn` (`_dispatch_structural_escalation`, `_dispatch_reground_remedy`, `_dispatch_merge_remedy`, `_dispatch_file_check_create`). Today the tests pin the return strings and `apply_skip` for most rows, but leave gaps: the halt fields, `applied_structural_finding_ids`, `apply_failed`, and the drift `refresh_snapshot` call are only asserted on a few outcomes. This step is **test-only** (no production code changes): it locks the current behavior as a green baseline so step 2 can extract the shared outcome kernel under a green→refactor→green discipline. On green, the four dispatch classes assert the full five-field post-call `WalkState` (the four kernel fields + `apply_failed`) and the drift-refresh call/no-call for each of their outcomes.

## Table of Contents

- [Why](#why) — why the WalkState tail must be pinned before extraction
- [Input](#input) — the current outcome→WalkState behavior map this step records
- [Files (creates vs edits)](#files-creates-vs-edits) — the single test file this step edits
- [Implementation](#implementation) — which classes to extend, the field matrix, and seam discipline
- [Tests](#tests) — the characterization cases to add per dispatcher
- [Verification (non-code step)](#verification-non-code-step) — how to confirm the pins are a correct green baseline
- [Acceptance criteria](#acceptance-criteria) — observable checks a reviewer/CI can run
- [References](#references) — pytest/mock docs and the refactoring discipline
- [Deferred](#deferred) — the kernel extraction and file-check tests owned by other steps

## Why

Step 2 extracts the `apply_skip`/halt/`applied_structural_finding_ids`/drift-refresh side-effect tail into one shared kernel and routes all four dispatchers through it. "Behavior-preserving" there means the exact same `WalkState` after every outcome — but the current tests don't assert the full tuple everywhere, so an extraction bug could silently flip, say, `halt_apply_landed` on a merge-applied row or drop the `refresh_snapshot` call on an escalation-applied row and still pass. That is precisely the bug class shipped-fix `5d4fe1b` patched (a `granularity-split` branch that reached escalation without the `apply_skip` tail its siblings had, recording an un-split finding as `applied` and pre-skipping the required split forever). This step makes the whole tail observable per outcome so the extraction can't reintroduce that class undetected.

## Input

This step consumes the **current observable behavior** of the four dispatchers in `plan_tool/cli/review_actions.py` (built by `_build_review_action_fn`) and the `WalkState` dataclass in `plan_tool/review_walk.py`. The kernel-owned fields to pin, and their current per-outcome values:

- **`apply_skip`** — left `False` only on a terminal-applied outcome (walk records `applied`); set `True` on every other outcome (walk records `skip`). The genuine-resolved paths count as terminal-applied: reground `noop` (plan already fully done) and file-check create/"already declared".
- **`halt_requested` + `halt_apply_landed`** — set together to `True` only by: merge-applied (always) and escalation-applied under `halt_on_applied=True` (the `granularity-split` router branch via `action`). Escalation under the default `halt_on_applied=False` (the `BLOCKED-STRUCTURAL` reconcile caller), reground, and file-check never touch them.
- **`applied_structural_finding_ids`** — reground-applied and merge-applied add `rec.id`; escalation and file-check never add.
- **`apply_failed`** — never set by any of these four (it belongs to `_dispatch_apply_finding`'s error path). Stays `False` everywhere here.
- **drift `refresh_snapshot`** — called only by escalation-applied when `reconcile_scope_guard.iter_lock` is present (`from plan_tool.drift_detection import refresh_snapshot`). Reground and merge never refresh, even when applied.

This step pins all five fields plus the drift-refresh call from the code as-is, inventing no new behavior. Note the kernel step 2 extracts owns only **three** of them (`apply_skip`, halt pair, `applied_structural_finding_ids` — via its `resolved`/`record_finding_id`/`halt` descriptor); `apply_failed` is never touched here, and drift `refresh_snapshot` stays **inline in the escalation dispatcher** (not the kernel) to keep `review_walk` off `plan_tool.drift_detection`. The characterization still pins the `refresh_snapshot` call so step 2's inline preservation is verified.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `tests/cli/test_review_actions.py` — extend the existing dispatch classes `TestStructuralEscalation`, `TestSplitEscalationDispatch`, `TestRegroundRemedyDispatch`, and `TestMergeRemedyDispatch` to assert the complete post-call `WalkState` (all four kernel fields + `apply_failed`) and the drift-refresh call/no-call for every outcome. Add a small file-check characterization block pinning that create/fix outcomes leave the halt fields and `applied_structural_finding_ids` untouched. Reuse the existing stub/rec helpers (`_stub_escalate`, `_escalate_result`, `_stub_blocked_structural`, `_stub_reground_bridge`, `_reground_result`, `_reground_rec`, `_stub_merge_bridge`, `_merge_bridge_result`, `_merge_rec`).

## Implementation

**Foundational logic of this step:** pin the outcome→`WalkState` side-effect tail — the same tail step 2 consolidates. It's exercised in four places today (the four `_dispatch_*` closures inside `_build_review_action_fn`) plus the `BLOCKED-STRUCTURAL` arm of `_dispatch_apply_finding`, which delegates to `_dispatch_structural_escalation`. This step **does not** consolidate them — it only makes each place's field-by-field result observable so the consolidation is safe. Routing the duplication into one source is step 2/3's job (see Deferred).

**Drive everything through the public seam.** Build the action callable with `_build_review_action_fn(ctx=..., plan_path=..., plan_name=..., state=WalkState(...), **kwargs)` and call `action(rec)`, exactly as the existing classes do. Do not reach into the private `_dispatch_*` closures — they aren't importable, and testing through `action(rec)` also pins the router branch order in `action` (the `split_escalation_target` branch before `should_apply_as_finding`, and the merge/reground split by directive kind).

**What to add, per class.** The gap is the *completeness* of the `WalkState` assertion, not new outcomes. For each outcome already covered by a return-string test, also assert the fields that outcome leaves untouched:

- **`TestStructuralEscalation`** — a **direct** `_dispatch_structural_escalation(rec)` call with the default `halt_on_applied=False`, i.e. the dispatcher in isolation (**not** the full reconcile route — see the dedicated BLOCKED-STRUCTURAL bullet below):
  - Applied: `apply_skip is False` (the applied branch never touches `apply_skip`, and a fresh `WalkState` defaults it `False`), **and** `halt_requested is False` and `halt_apply_landed is False` (this lane does not halt), **and** `rec.id not in state.applied_structural_finding_ids` (escalation never records), plus the existing `refresh_snapshot` pin when a reconcile-lane guard is present.
  - Applied **without** a reconcile guard: `refresh_snapshot` is **not** called (patch it to a boom and assert it never fires).
  - recommended / unsafe / proposal-unusable / step-missing / plan-level-`step_id`-None: `apply_skip is True`, halt fields both `False`, `applied_structural_finding_ids` empty, `apply_failed is False`.
- **The BLOCKED-STRUCTURAL reconcile route (load-bearing — pin the FULL path, not the direct call).** The **only** production caller of escalation with `halt_on_applied=False` is the `BLOCKED-STRUCTURAL` arm of `_dispatch_apply_finding` (`review_actions.py:525`), which **pre-sets `state.apply_skip = True`** *before* delegating to `_dispatch_structural_escalation`. The applied branch never resets it, so an **applied** split reached via this route ends with `apply_skip=True` — the walk records **`skip`**, the *opposite* disposition from the direct-call and granularity-split-router applied cases (`apply_skip=False` → `applied`). Drive the full route (stub `apply_finding` to return a `BLOCKED-STRUCTURAL` verdict via `_stub_blocked_structural`, and `escalate_to_split` to return `applied`) and assert the final `state.apply_skip is True`. This is the invariant step 2's kernel must preserve by construction: the kernel may only ever **set `apply_skip=True`**, never **reset it to `False`** on a resolved/applied outcome — a kernel that reset `apply_skip=False` on `resolved=True` would silently flip this route `skip`→`applied`. The existing `test_blocked_structural_reconcile_path_unchanged` asserts only the halt fields; this pin closes the `apply_skip` gap at exactly the "byte-identical" seam acceptance criterion 5 names.
- **`TestSplitEscalationDispatch`** (`halt_on_applied=True`, the `granularity-split` caller): the applied-halts and recommended-does-not-halt cases already exist; add `rec.id not in state.applied_structural_finding_ids` on the applied case (split escalation, unlike merge/reground, does **not** record the id) and `apply_failed is False`.
- **`TestRegroundRemedyDispatch`**: applied → `apply_skip is False`, `rec.id in state.applied_structural_finding_ids`, halt fields both `False`; noop → `apply_skip is False`, `rec.id not in` the id set, halt both `False`; recommended / unsafe / step-missing / stale / manual-fallthrough → `apply_skip is True`, halt both `False`, id set empty. Assert `refresh_snapshot` is never called on the applied case (reground must not refresh drift). **Session short-circuit** (`review_actions.py:956` — `rec.id` already in `state.applied_structural_finding_ids`, returns "…already done" *without* touching the bridge): pre-seed `state.applied_structural_finding_ids = {rec.id}`, assert `apply_skip is False` (recorded `applied`, a resolved disposition), halt both `False`, and the bridge stub is **never called**. Unpinned today; the Architecture names it a must-preserve item, so the matrix must cover it.
- **`TestMergeRemedyDispatch`**: applied (and applied-with-`apply_error`) already pin `halt_requested`/`halt_apply_landed`/id membership; add `apply_failed is False` and assert `refresh_snapshot` is never called (merge must not refresh drift). recommended / unsafe / invalid / stale / manual-fallthrough → `apply_skip is True`, halt both `False`, id set empty. **Session short-circuit** (`review_actions.py:1084` — `rec.id` already applied, returns "…already folded" without the bridge): pre-seed `state.applied_structural_finding_ids = {rec.id}`, assert `apply_skip is False`, halt both `False`, and the bridge stub is **never called**.
- **File-check**: add a compact block that drives a MISSING_PARENT `file-check` rec through `action(rec)` with `builtins.input` stubbed, pinning the full `WalkState` for **all five** outcomes step 2 routes through the kernel — not just create/fix. `_dispatch_file_check_create` has three minority outcomes with distinct `apply_skip` dispositions that are unpinned today and would otherwise let the extraction mis-map them undetected (the `5d4fe1b` class, for file-check):
  - **create** (`review_actions.py:1219` moved, `:1226` already-declared) — the **resolved** paths: `apply_skip is False`, halt fields `False`, id set empty.
  - **fix** (`:1203`) — `apply_skip is True` (left unchanged), halt `False`, id set empty.
  - **"already declared"** (`:1226`, nothing to move — idempotent no-op treated as **resolved**): `apply_skip is False`. This is the load-bearing one: mis-mapping it to a skip outcome re-fires the finding forever.
  - **parse-error** (`:1213`) and **step-not-found** (`:1217`): `apply_skip is True`, halt `False`, id set empty.
  - **Location (resolve the step-1/step-2 inconsistency):** these file-check `WalkState`/`apply_skip` pins live in **`tests/cli/test_review_actions.py`** (step 1's declared file), as a compact block driving `action(rec)` — **not** in `tests/test_review_walk.py`. The existing `TestFileCheckCreateDispatch` in `test_review_walk.py` owns the orthogonal `files:`→`creates:` **plan-mutation** assertions; reference it, do not duplicate or move it. The two concerns split cleanly by file (dispatch/`WalkState` here; plan-mutation there), so coverage is complementary, not duplicated. **Step 2's Test-creation order must reference these pins at `test_review_actions.py`, not `test_review_walk.py`** — step 2's detail is corrected to match.

**Recommended, not required:** to keep the assertions uniform and cheap to read, one way is a small local helper like `_assert_walk(state, *, apply_skip, halt_requested=False, halt_apply_landed=False, applied_ids=frozenset(), apply_failed=False)` that checks all five at once with sensible "untouched" defaults. The implementer owns whether to add it or inline the asserts.

**Constraints that must hold:**
- **Stay in `tests/cli/test_review_actions.py`.** Do not edit production code, and do not edit `tests/test_review_walk.py` (step 2's file) — the file-check plan-mutation coverage stays there.
- **Assert the exact current behavior, not the desired end state.** If an existing return-string assertion uses a stable substring (e.g. `"re-grounded"`, `"already folded"`, `"walk halted"`), keep matching substrings, not full strings, so incidental wording doesn't make the pin brittle.
- **No real backend.** Stub `escalate_to_split`, `reground_bridge`, and `merge_bridge` (and `builtins.input` for file-check). `escalate_to_split` binds at build time (its `from plan_tool.launcher import …` runs when the action fn is built), so patch it before the build; `reground_bridge`/`merge_bridge` bind at call time via body-local imports, so patch either at any point before `action(rec)`. The conftest autouse gate must not see a backend spawn — no `@allow_real_claude` marker is needed.
- **Preserve the two distinct opt-in tokens.** Escalation gates on `allow_split`; reground/merge gate on `allow_structural_remedy`. Keep them separate in the new tests (don't collapse to one kwarg).

## Tests

All cases live in `tests/cli/test_review_actions.py`, extending the four existing dispatch classes.

**TestStructuralEscalation (halt_on_applied=False)**
- `test_escalation_applied_full_walk_state` — applied leaves `apply_skip=False`, halt fields False, id set empty.
- `test_escalation_applied_without_reconcile_guard_does_not_refresh` — no `iter_lock` guard → `refresh_snapshot` never called.
- `test_escalation_non_applied_outcomes_full_walk_state` — recommended/unsafe/proposal-unusable/step-missing each leave `apply_skip=True`, halt False, id set empty, `apply_failed=False`.
- `test_escalation_plan_level_none_leaves_no_halt_no_id` — `step_id=None` sets `apply_skip=True`, halt False, id set empty.

**TestSplitEscalationDispatch (halt_on_applied=True)**
- `test_granularity_split_applied_does_not_record_finding_id` — applied halts but leaves `rec.id` out of `applied_structural_finding_ids`, `apply_failed=False`.

**TestRegroundRemedyDispatch**
- `test_reground_applied_records_id_and_no_halt` — applied → `apply_skip=False`, `rec.id` recorded, halt fields False.
- `test_reground_applied_does_not_refresh_drift` — `refresh_snapshot` never called on applied reground.
- `test_reground_noop_leaves_id_set_empty_no_halt` — noop → `apply_skip=False`, id set empty, halt False.
- `test_reground_non_applied_outcomes_full_walk_state` — recommended/unsafe/step-missing/stale/manual → `apply_skip=True`, halt False, id set empty.

**TestMergeRemedyDispatch**
- `test_merge_applied_does_not_refresh_drift` — `refresh_snapshot` never called on applied merge.
- `test_merge_applied_apply_failed_stays_false` — applied (incl. `apply_error`) leaves `apply_failed=False`.
- `test_merge_non_applied_outcomes_full_walk_state` — recommended/unsafe/invalid/stale/manual → `apply_skip=True`, halt False, id set empty.

**File-check (new compact block in test_review_actions.py)**
- `test_file_check_create_leaves_halt_and_id_untouched` — create outcome leaves halt fields False and id set empty.
- `test_file_check_fix_leaves_halt_and_id_untouched` — fix outcome leaves halt fields False and id set empty.

### Verification (non-code step)

This step changes no production code — verification is that the new pins are a correct green baseline over current HEAD:

- Run `uv run pytest tests/cli/test_review_actions.py -q` and confirm all new cases pass against unmodified production code. They must be **green now** — a characterization test that fails at HEAD is mis-asserting current behavior, not pinning it.
- Run the full suite `uv run pytest tests/ -q` to confirm no collateral breakage and that the conftest autouse backend gate never trips (no real `claude`/`codex`/`agent` spawn from the stubbed bridges).
- Spot-check each new assertion against the source: the field values asserted must match the closures in `plan_tool/cli/review_actions.py` (`_dispatch_structural_escalation` applied/`halt_on_applied` branches, `_dispatch_reground_remedy` applied/noop branches, `_dispatch_merge_remedy` applied/halt branch, `_dispatch_file_check_create`) — no invented behavior.

## Acceptance criteria

- Every outcome of all four dispatchers has a test in `tests/cli/test_review_actions.py` asserting the full `WalkState` tuple: `apply_skip`, `halt_requested`, `halt_apply_landed`, `applied_structural_finding_ids`, and `apply_failed`.
- Escalation-applied is pinned both with a reconcile-lane guard (`refresh_snapshot` called) and without one (`refresh_snapshot` not called); reground-applied and merge-applied are each pinned to **not** call `refresh_snapshot`.
- Merge-applied and split-escalation-applied (`halt_on_applied=True`) assert `halt_requested is True` and `halt_apply_landed is True`; escalation under the default `halt_on_applied=False`, reground, and file-check assert both halt fields stay `False`.
- Reground-applied and merge-applied assert `rec.id in state.applied_structural_finding_ids`; escalation and file-check assert the id set stays empty.
- `uv run pytest tests/cli/test_review_actions.py -q` and `uv run pytest tests/ -q` both pass against unmodified production code, with no real backend spawn.

## References

- `plan_tool/cli/review_actions.py` — the four `_dispatch_*` closures built by `_build_review_action_fn` (`_dispatch_structural_escalation`, `_dispatch_reground_remedy`, `_dispatch_merge_remedy`, `_dispatch_file_check_create`) whose per-outcome `WalkState` tail is the contract this step pins.
- `plan_tool/review_walk.py` — the `WalkState` dataclass whose `apply_skip`, `halt_requested`, `halt_apply_landed`, `applied_structural_finding_ids`, and `apply_failed` fields the characterization matrix asserts.
- [How to monkeypatch/mock modules and environments (pytest)](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — for stubbing `escalate_to_split`, `reground_bridge`, `merge_bridge`, and `builtins.input` before building the action fn.
- [unittest.mock — mock object library (Python Standard Library)](https://docs.python.org/3/library/unittest.mock.html) — for spying on the `plan_tool.drift_detection.refresh_snapshot` seam to assert it is or isn't called per outcome.
- [Refactoring Catalog (Martin Fowler)](https://refactoring.com/catalog/) — the green→refactor→green (characterization-first) discipline this step's baseline enables for the step 2 Extract Function.

## Deferred

- Extracting the shared outcome-application kernel and routing the four dispatchers through it — step 2 owns it (`plan_tool/review_walk.py`, `plan_tool/cli/review_actions.py`); a direct unit test of that kernel is added there once it exists.
- The shared gate helper (`allow = <token> and not state.yes_to_all`) for the three bridge dispatchers — step 3.
- Extending `tests/test_review_walk.py:TestFileCheckCreateDispatch` — that file is out of this step's declared scope (step 2's file list); its existing create/fix `apply_skip` and plan-mutation pins are referenced, not duplicated here.
- Consolidating the duplicated outcome tail across the four `_dispatch_*` closures into one source — a refactor/consolidation this test-only step cannot make; it is the plan's own step 2/3 work.
