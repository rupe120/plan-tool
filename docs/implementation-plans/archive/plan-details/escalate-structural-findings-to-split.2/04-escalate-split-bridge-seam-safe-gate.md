> **Auto-archived**: this plan was swept on 2026-06-22 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the `escalate_to_split` bridge seam in `launcher.py`

## Summary

- Add one new function `escalate_to_split` to `plan_tool/launcher.py` plus a small `EscalateResult` dataclass and a `_structural_split_rec` helper. The function is the single reusable seam that takes one mixed step and either **applies** the refactor+feature split or **recommends** it — never half-doing it.
- It mirrors `plan_tool/detail.py:generate_detail`'s inline Phase-B sequence call-for-call: **re-parse plan from disk → safe-gate (`_split_is_safe`) → propose once (`_propose_step_split`) → confirm (`_confirm_split`) → `_apply_step_split` → `_migrate_downstream_details_after_split` → `write_plan`** — re-deriving no algorithm, only routing through the existing five split primitives.
- Key design decision: the cheap deterministic safe-gate and the `allow_split` recommend-only check both run **before** any Claude proposal, so no token is spent on a path that can never apply. Each terminal disposition returns a distinct `outcome` string.
- On green: `escalate_to_split` returns `EscalateResult(outcome="applied")` and writes a 2-step split for a safe TTY-confirmed call; returns `outcome="recommended"` with a `structural-split` `Recommendation` when it declines to mutate; returns `outcome` of `"unsafe"` / `"proposal-unusable"` / `"step-missing"` for the early-exit cases — all without a single real `claude` subprocess in the test suite.
- Scope is `plan_tool/launcher.py` + `tests/test_launcher.py` only. Wiring the bridge into the `create`/`detail` convergence loops and the `review_actions` apply dispatcher is later steps; this step ships the function and its unit tests, with the routes still unconnected.

## Table of Contents

- [Summary](#summary) — what this step adds and the observable result
- [Why](#why) — the duplicated inline split flow this seam consolidates
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the `EscalateResult` shape, the outcome ladder, the import placement
- [Tests](#tests) — outcome-by-outcome cases plus the negative cost-ordering guards
- [Test-creation order (feature step)](#test-creation-order-feature-step) — green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable conditions
- [References](#references) — relevant authoritative docs
- [Deferred](#deferred) — the callers and the unsafe-recommend gap left to later steps

## Why

The step-split flow exists today only as an inline block inside `plan_tool/detail.py:generate_detail`'s Phase B (the `if allow_split and mixed_steps and sys.stdin.isatty():` guard). It is reachable nowhere else, yet steps that come after this one need the same flow from two live call sites: the `detail` convergence loop and the `review_actions` `BLOCKED-STRUCTURAL` apply branch. (The `create` convergence loop is deferred — no named trigger-2 scenario; see the plan's Open question and Deferred.) Copying the six-call sequence into each would multiply the surface where the gate→propose→confirm→apply→migrate ordering (and its safety invariants) can drift. This step lifts that sequence into one named function so later callers route through a single path, and it adds the one piece the inline code lacks: an explicit **apply-vs-recommend** decision that emits a `structural-split` `Recommendation` (rendered by step 2's `triage_reason`/`emit_triage_summary`) when it chooses not to mutate — so the more-correct plan is always surfaced even on the paths that decline the auto-edit.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/launcher.py` — add the `EscalateResult` dataclass, the module-level `_structural_split_rec(step)` helper, and the public `escalate_to_split(...)` function. Extend the existing top-level `from plan_tool.review import (...)` block with `Recommendation` and `_make_rec_id`. Add `field` to the existing `from dataclasses import dataclass, replace` import.
  - `tests/test_launcher.py` — add a new `TestEscalateToSplit` class covering every outcome plus the negative cost-ordering guards. Import `escalate_to_split` (and `EscalateResult`) in the existing `from plan_tool.launcher import (...)` block.

## Implementation

### `plan_tool/launcher.py`

**Imports.**

- **Top-level (cycle-free):** add `Recommendation` and `_make_rec_id` to the existing `from plan_tool.review import (...)` block. `review` imports `launcher` only body-locally, so `launcher → review` at module top is acyclic — do not body-localize these.
- **Top-level stdlib:** add `field` to `from dataclasses import dataclass, replace` (the new dataclass needs `field(default_factory=list)` for the blocking-ids list).
- **Body-local (genuine cycles), inside `escalate_to_split`:** both `plan_tool/create.py` and `plan_tool/detail.py` import `apply_finding` from `launcher` at module top, so `launcher` importing back from them must be lazy:
  - `from plan_tool.create import CreateError, _apply_step_split, _propose_step_split`
  - `from plan_tool.detail import _split_is_safe, _confirm_split, _migrate_downstream_details_after_split`

**`EscalateResult` dataclass** (frozen, module level, beside the function):

- Fields:
  - `outcome: str` — exactly one of `"applied"`, `"recommended"`, `"unsafe"`, `"proposal-unusable"`, `"step-missing"`.
  - `target_id: int` — the step id the bridge was asked to act on.
  - `recommendation: Optional[Recommendation] = None` — populated **only** on `outcome == "recommended"`; the `structural-split` rec the caller surfaces. `None` for every other outcome.
  - `blocking: list[int] = field(default_factory=list)` — the downstream non-`PENDING` ids that made a split unsafe; populated only on `outcome == "unsafe"` so the caller can name them in a warning (mirroring Phase B's `skipping auto-split` message). Empty otherwise.

**`_structural_split_rec(step: Step) -> Recommendation`** (module-level helper):

- Build a `Recommendation` with:
  - `source="structural-split"` — the literal step 2 added to `review.STRUCTURAL_SOURCES` and gave a dedicated `triage_reason` arm pointing at `plan-tool split`. This is **not** `granularity-split` (a different, unrelated source).
  - `id=_make_rec_id(step.id, "structural-split", f"structural-split:{step.id}")` — content-addressed and stable across re-assessment.
  - `step_id=step.id`, `severity="medium"`, a `title` naming the structural finding, a `body` stating the step mixes refactor + feature and that its only correct fix is to split it into two type-pure steps (something `apply_finding` cannot do).
  - `suggested_action` pointing at the concrete command: `plan-tool split <plan> --step <id> --into "<refactor half>" --into "<feature half>"` (the real `cmd_split` surface in `plan_tool/cli/authoring.py:cmd_split`).
- Keep `source` out of `review.APPLY_ELIGIBLE_SOURCES` (it already is — step 2 owns that): the rec is advisory and non-apply-eligible, so it never re-enters `apply_finding`.

**`escalate_to_split(...)`** — the bridge. Signature:

```python
def escalate_to_split(
    plan_path: Path,
    *,
    step_id: int,
    repo_root: Path,
    invoker: Callable[[str], str],
    allow_split: bool,
    prompt_fn: Optional[Callable[[str], str]] = None,
) -> EscalateResult:
```

- **`invoker` is the split-PROPOSER seam — `Callable[[str], str]`** (returns raw Claude text that `_propose_step_split` parses). It is **not** launcher's `Invoker = Callable[[str], tuple[int, str]]` run-step alias; do not reuse that alias. Pass it as a required keyword (no shell default) so the conftest autouse real-claude gate never fires through an accidental default.
- **`prompt_fn` default `None`** → fall back to the interactive builtin: `confirm_fn = prompt_fn if prompt_fn is not None else input`. `_confirm_split` itself auto-declines on a non-TTY, so a non-TTY caller passing `None` still recommends rather than blocks.

Outcome ladder, in this exact order (each step is an early return):

1. **Re-parse from disk.** `plan = parse_plan(plan_path)`. The bridge re-parses on every call from `plan_path` (it takes no `Plan` parameter), so a prior split's renumbering in the same loop is visible. This re-parse is the bridge's job — callers that previously re-parsed per iteration drop that (a later step's concern).
2. **Resolve the target.** `try: step = plan.step_by_id(step_id) except KeyError: return EscalateResult(outcome="step-missing", target_id=step_id)`. A stale id (already restructured away by an earlier split) is a silent no-op, mirroring Phase B's `except KeyError: continue`.
3. **Safe-gate (deterministic, no Claude).** `safe, blocking = _split_is_safe(plan, step_id)`. If not safe: `return EscalateResult(outcome="unsafe", target_id=step_id, blocking=blocking)`. This runs **before** any proposal so no token is spent on a split that can't apply.
4. **Recommend-only short-circuit (no Claude).** `if not allow_split: return EscalateResult(outcome="recommended", target_id=step_id, recommendation=_structural_split_rec(step))`. When the caller hasn't opted into mutation, emit the rec without proposing — the second cheap gate before the expensive call.
5. **Propose once.** `replacements = _propose_step_split(step, invoker, repo_root=repo_root)`. If falsy (unparseable / wrong length): `return EscalateResult(outcome="proposal-unusable", target_id=step_id)`. Single proposal, no retry loop — recover by reporting, not re-asking.
6. **Confirm.** `if not _confirm_split(confirm_fn, step=step, replacements=replacements): return EscalateResult(outcome="recommended", target_id=step_id, recommendation=_structural_split_rec(step))`. A declined confirm (or non-TTY auto-decline) still surfaces the rec.
7. **Apply + migrate + write.** `shift = len(replacements) - 1`; `try: new_steps = _apply_step_split(plan.steps, step_id, replacements) except CreateError: return EscalateResult(outcome="recommended", target_id=step_id, recommendation=_structural_split_rec(step))`. On success: `_migrate_downstream_details_after_split(new_steps, repo_root=repo_root, target_id=step_id, shift=shift)`, then `write_plan(plan_path, plan.model_copy(update={"steps": new_steps}))` (here `plan` is the bridge's re-parsed local — the Phase-B template names the same plan `plan_now`), then `return EscalateResult(outcome="applied", target_id=step_id)`.

**Non-obvious decisions:**

- **`CreateError` degrades to `"recommended"`, not a re-raise.** The inline Phase-B code logged `step {id}: split failed (...)` and `continue`d; the bridge instead returns a recommend disposition (the safety gate already ruled out the common unsafe cases, so a mid-apply graph error is rare). Accepted divergence: the inline rare-path warning no longer fires here — the caller decides what to print from the outcome. State this in `Deferred`.
- **The bridge leaves both new halves with `detail is None`.** `_apply_step_split` + the migrate helper write the split to disk but do not author the new halves' detail bodies — that re-authoring is the caller's job (the `create`/`detail` loops discover `detail is None` steps and re-author them). The bridge does the structural edit only.
- **`"unsafe"` carries no recommendation.** The recommended action (`plan-tool split`) would itself be blocked by the same already-run downstream steps, so recommending it would mislead. The `blocking` ids let the caller warn precisely. Whether unsafe should still emit a detection-only rec is deferred.

## Tests

All in `tests/test_launcher.py`, new class `TestEscalateToSplit`. No real `claude` subprocess — `invoker` is always a fake `Callable[[str], str]`, and the destructive cases rig it to raise to prove it is never reached.

- `test_step_missing_returns_noop` — unknown `step_id` → `outcome == "step-missing"`, `recommendation is None`, plan file unchanged; `invoker` rigged to raise is never called.
- `test_unsafe_skips_proposal` — a downstream `DONE`/`CURRENT` step at/after the target → `outcome == "unsafe"`, `blocking` lists the offending ids, plan file unchanged; `invoker` rigged to raise is never called (pins safe-gate-before-Claude cost ordering).
- `test_recommend_only_no_claude` — `allow_split=False` on a safe step → `outcome == "recommended"`, `recommendation.source == "structural-split"`, `invoker` rigged to raise is never called.
- `test_proposal_unusable` — `invoker` returns junk so `_propose_step_split` yields `None` → `outcome == "proposal-unusable"`, `recommendation is None`, plan file unchanged.
- `test_declined_confirm_recommends` — good proposal, `prompt_fn` returns `"n"`, monkeypatch `sys.stdin.isatty` → `True` so `_confirm_split` reaches `prompt_fn` (the pytest runner is non-TTY; without this the auto-decline path passes the test for the wrong reason) → `outcome == "recommended"`, rec emitted, plan file unchanged (no write).
- `test_applied_writes_split` — good proposal, `prompt_fn` returns `"y"`, monkeypatch `sys.stdin.isatty` → `True` so `_confirm_split` reaches `prompt_fn` (the pytest runner is non-TTY; without this the call auto-declines and yields `outcome == "recommended"`, failing the assertion), safe step → `outcome == "applied"`; re-parsing the plan shows the target replaced by exactly two steps (refactor then feature), downstream ids renumbered, both new halves `detail is None`, `recommendation is None`.
- `test_apply_error_degrades_to_recommend` — force `_apply_step_split` to raise `CreateError` (monkeypatch or a graph it rejects) → `outcome == "recommended"`, rec emitted, plan file unchanged (no partial write).
- `test_reparses_plan_from_disk` — write a fresh plan to `plan_path`, call the bridge; assert it acts on the on-disk state, proving it re-parses from `plan_path` on every call.
- `test_non_tty_recommends` — `allow_split=True`, `prompt_fn=None`, monkeypatch `sys.stdin.isatty` to `False` so `_confirm_split` auto-declines → `outcome == "recommended"` (not blocked on input).
- `test_structural_rec_is_advisory` — the emitted `recommendation` has `source == "structural-split"`, `step_id == target`, `suggested_action` mentions `plan-tool split`; `review.is_apply_eligible(rec)` is `False` and `review.is_structural(rec)` is `True` (depends on steps 1–2 being landed).

### Test-creation order (feature step)

This is a **feature** step — `escalate_to_split` is new behavior, no pre-existing branch to characterize. Add each test in `TestEscalateToSplit` **with** the function:

1. First the two early-exit guards (`test_step_missing_returns_noop`, `test_unsafe_skips_proposal`) — they pin the no-Claude ordering and need only the safe-gate and resolve code.
2. Then `test_recommend_only_no_claude` and `test_proposal_unusable` — the next two early exits.
3. Then `test_declined_confirm_recommends`, `test_applied_writes_split`, `test_apply_error_degrades_to_recommend` — the full apply path and its error degrade.
4. Then `test_reparses_plan_from_disk`, `test_non_tty_recommends`, `test_structural_rec_is_advisory` — the contract/edge guards.

**Green-before-done gate:** every test in `TestEscalateToSplit` must pass (and the full `tests/test_launcher.py` stay green) before this step is finished. The destructive paths must use a raise-rigged `invoker`/proposer so a regression that leaks a Claude call onto a no-Claude path fails loudly.

## Acceptance criteria

- `escalate_to_split` exists in `plan_tool/launcher.py` with the signature above; `invoker` is typed `Callable[[str], str]` (a required keyword), not the `Invoker` tuple alias.
- `EscalateResult` carries `outcome`, `target_id`, `recommendation`, and `blocking`, and `outcome` only ever takes one of the five documented strings.
- A safe + TTY-confirmed call writes a 2-step split to `plan_path` (target replaced by refactor-then-feature, downstream renumbered, both halves `detail is None`) and returns `outcome == "applied"`.
- An unknown `step_id`, an unsafe target, or `allow_split=False` each returns its documented outcome **without** calling `invoker` (proven by a raise-rigged invoker in tests).
- A declined confirm, a `None` proposal, an `allow_split=False` call, and a mid-apply `CreateError` never write to `plan_path`.
- The `recommended` outcomes carry a `Recommendation` with `source == "structural-split"`; `review.is_apply_eligible` is `False` and `review.is_structural` is `True` for it.
- New imports are placed per direction: `Recommendation`/`_make_rec_id` top-level on the existing `review` import; the `create`/`detail` split primitives body-local inside `escalate_to_split`.
- `uv run pytest tests/test_launcher.py -q` is green.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3/library/dataclasses.html) — `field(default_factory=list)` and `Optional` defaults for the `EscalateResult` shape.
- [subprocess — Subprocess management (Python 3.13)](https://docs.python.org/3/library/subprocess.html) — return-code / streaming basis of the proposer seam; confirms the exit-code convention the bridge preserves (no rc flips on a recommend).
- [How to monkeypatch/mock modules and environments — pytest](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — patching `sys.stdin.isatty` and rigging the `invoker`/proposer to raise so the no-Claude paths are provable.
- [API Reference (markers, fixtures) — pytest](https://docs.pytest.org/en/stable/reference/reference.html) — `tmp_path`, `timeout`, and the unit-test conventions the new class follows.

## Deferred

- **Wiring `escalate_to_split` into callers** — the `create_plan` and `generate_detail` convergence loops (replacing Phase B's inline sequence) and the `review_actions.py` `BLOCKED-STRUCTURAL` apply branch are separate later steps. This step ships the function and tests with the routes unconnected.
- **The dropped rare-path warning on `CreateError`** — the inline Phase-B code emitted `step {id}: split failed (...)` and continued; the bridge degrades to `outcome="recommended"` and leaves the messaging to the caller. Accepted divergence on a rare path; no covering test beyond `test_apply_error_degrades_to_recommend`.
- **A detection-only recommendation on the `"unsafe"` outcome** — currently unsafe carries `blocking` ids but no `Recommendation` (the recommended `plan-tool split` would itself be blocked). Whether to surface a non-actionable structural detection here is left for a follow-up, tracked against the "always validate the most-correct plan" principle.
- **Re-collection of findings after an in-loop applied split** — keeping the convergence loop's finding ids aligned with post-split renumbering is the caller's contract, not the bridge's; owned by the later create/detail wiring steps.
