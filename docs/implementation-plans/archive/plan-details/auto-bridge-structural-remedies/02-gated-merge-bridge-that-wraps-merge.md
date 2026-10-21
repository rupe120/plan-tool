> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Add a gated merge bridge that wraps `merge_steps` and returns an applied/recommended/unsafe result

## Summary

Adds one apply-or-recommend bridge in `plan_tool/detail.py` that wraps the existing `merge_steps` executor behind the tool's standard gate, plus its unit tests in `tests/test_detail.py`. The bridge takes a flagged contiguous merge set, runs the deterministic `_merge_is_safe` run-state gate, then either **recommends** (spends no Claude, mutates nothing) or **applies** the merge — only when an explicit opt-in plus a TTY confirm (or `-y` bypass) both hold. It returns a frozen result whose `outcome` lets the caller tell recommended from applied, mirroring `launcher.py:escalate_to_split`'s `EscalateResult` and `scope_out.py:scope_out_step`'s `ScopeOutResult`. The bridge adds no new merge logic and no new `review.Recommendation` source token; step 5 wires it into the walk, so step 2 ships only the primitive and its tests. On green, a merge set can be actuated straight from a `granularity-merge` finding, and every unattended / non-TTY / declined / unsafe / invalid path recommends only.

## Table of Contents

- [Summary](#summary) — what the bridge does and the result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the diagnosis-vs-actuation gap for merge.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two in-scope files and their edits.
- [Implementation](#implementation) — the gate order, the reused primitives, the outcome vocabulary, and the gotchas.
- [Tests](#tests) — the gate-matrix and apply-path cases to add.
- [Acceptance criteria](#acceptance-criteria) — checkable behaviors.
- [References](#references) — argparse, frozen dataclasses, TTY checks, monkeypatch.
- [Deferred](#deferred) — out-of-scope follow-ups.

## Why

`plan_tool/granularity.py` emits a `granularity-merge` finding (adjacent fragmented dependent steps) and `plan_tool/detail.py:merge_steps` already ships the executor that folds them — but the two are disconnected. The finding is recommend-only (kept out of `review.py`'s `APPLY_ELIGIBLE_SOURCES`), so re-combining always means the operator hand-runs `plan-tool merge --steps N --steps M` via `plan_tool/cli/authoring.py:cmd_merge`. That is a correct, already-computed remedy forcing a manual copy-and-retype. This step closes that gap with a programmatic apply-or-recommend bridge — the merge sibling of `launcher.py:escalate_to_split` and `scope_out.py:scope_out_step` — so step 5's walk can actuate the merge behind the standard gate. It adds only wiring between an existing producer and an existing executor: no new detection, no new merge/renumber logic.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/detail.py` — add a frozen result dataclass (e.g. `MergeBridgeResult`) and the bridge function (e.g. `merge_bridge`). Place both beside the existing merge primitives (`MergeResult`, `merge_steps`, `_merge_is_safe`, `_confirm_merge`), after `merge_steps` so it can call it.
  - `tests/test_detail.py` — add a `TestMergeBridge` class with the gate-matrix and apply-path cases below, reusing the existing `_build_merge_plan` helper and `_GOOD_BODY` constant.

## Implementation

- **What changes.** Add a bridge that turns the deterministic merge executor into a gated apply-or-recommend call. The bridge owns no merge algorithm — it routes through `merge_steps` for the mutation and `_merge_is_safe` for the run-state gate. This is the third instance of the apply-or-recommend gate shape; model it call-for-call on `plan_tool/launcher.py:escalate_to_split` and `plan_tool/scope_out.py:scope_out_step`.

- **Gate order — run the read-only checks first, before any Claude.** The default (recommend) and every refusal path must spend zero Claude and mutate nothing. One recommended order:
  1. Re-parse the plan from disk (`parse_plan(plan_path)`) — never trust an in-memory `Plan` the caller passed. Both siblings re-parse.
  2. **Existence pre-check** (deterministic refusal, in the bridge). Reject the two malformed conditions the safety gate cannot tolerate: fewer than two distinct ids, or an id absent from the plan → the `invalid` outcome. This runs first because the next gate (`_merge_is_safe`) calls `max(merge_ids)` without a membership check, so the ids must be proven to exist and the set non-empty before it runs.
  3. **Safety gate** (run-state). Call `_merge_is_safe(plan, merge_ids)` directly (as `escalate_to_split` calls `split_is_safe` directly) to get the `(safe, blocking_ids)` pair. If not safe → the `unsafe` outcome carrying `blocking`. This must run **before** the structural-validity gate below: `merge_steps` calls `_merge_is_safe` internally and raises `DetailError` on an unsafe set, so running the `dry_run=True` gate first would swallow the unsafe case and misclassify it as `invalid`, never producing the `unsafe` outcome. Consulting `_merge_is_safe` directly first — exactly as `escalate_to_split` consults `split_is_safe` first — resolves the safety condition cleanly. Reuse `_merge_is_safe` rather than re-deriving the predicate so the bridge refuses exactly what `merge_steps` refuses.
  4. **Structural-validity gate** (deterministic refusal). Catch the remaining malformed conditions the existence pre-check does not cover — non-canonical numbering or a mixed-`scope` member set — so no `DetailError` escapes into the walk. One clean way: call `merge_steps(plan_path, merge_ids=…, repo_root=…, dry_run=True, author_details=False)` inside a `try/except DetailError` — `dry_run=True` runs every guard and returns a preview `MergeResult` with no disk write and no Claude. Because the safety condition is already resolved above, any `DetailError` reaching here is a genuine structural-validity failure, not the safety case; map it to the `invalid` outcome (see the vocabulary below).
  5. **Opt-in gate.** Read the programmatic opt-in (name it to match the siblings, e.g. `allow_merge`). `False` → `recommended`, no prompt, no mutation.
  6. **Confirm gate.** Reuse `_confirm_merge(prompt_fn, steps_to_merge=…, merged_title=…)`, which auto-declines off a TTY. Support a `yes` bypass in the bridge (skip the `_confirm_merge` call when `yes=True`), mirroring how `scope_out_step` passes `yes` into `_confirm_scope_out`. A declined or non-TTY confirm → `recommended`.
  7. **Apply.** Call `merge_steps(plan_path, merge_ids=…, repo_root=…, invoker=…, …)` — this does the fold, renumber, downstream detail migration, and merged re-author. Wrap the returned `MergeResult` in the bridge result → `applied`.

- **Outcome vocabulary — only `applied` mutates.** Return a frozen dataclass (`@dataclass(frozen=True)`) whose `outcome` is one of a small closed set, mirroring `EscalateResult` / `ScopeOutResult`:
  - `applied` — the merge ran; carry the `MergeResult` (folded ids, merged id, re-author `detail_results`).
  - `recommended` — safe and valid but not actuated (opt-in off, declined/non-TTY confirm).
  - `unsafe` — the `_merge_is_safe` run-state gate refused; carry the `blocking` ids.
  - a fourth refusal outcome (recommend a name like `invalid`) for the deterministic validity failures — the existence pre-check and the structural-validity gate above — carrying the `DetailError` message (or an equivalent note) so the caller can explain. The plan's acceptance names the three headline outcomes (`applied`/`recommended`/`unsafe`); this fourth is the robustness case that keeps any `DetailError` from a malformed set from escaping the bridge. Keep the set closed and documented in the dataclass docstring, exactly as `EscalateResult`/`ScopeOutResult` document theirs.

- **Emit no `Recommendation`.** Unlike `escalate_to_split` (which builds `_structural_split_rec` because its create-loop caller needs a rec to surface), the merge bridge's caller — step 5's walk — already holds the `granularity-merge` finding that triggered it (`plan_tool/granularity.py:_merge_rec`, source `GRANULARITY_MERGE_SOURCE`). So the bridge mints nothing; it returns the outcome plus the merge set (and `blocking` on unsafe), like `scope_out_step` returning a `preview` rather than a rec. This is also how the step honors the plan's "no new `review.Recommendation` source token" constraint — cleanly, by adding no rec at all.

- **Forward the Claude seam.** The only Claude spend in a merge is the merged step's re-author, which lives inside `merge_steps` → `generate_detail`. Forward `invoker` (a `DetailInvoker`) into `merge_steps` so tests can neutralize it, and forward the other passthrough knobs `merge_steps` accepts — `title` (optional; default `None` lets `merge_steps` fall back to the first member's title), `author_details` (default `True`), `reporter`, `run_logger`, `budget` (`IterativeBudget`), and `prompt_fn` (used by the bridge's own `_confirm_merge` call). Do not re-implement the re-author.

- **Constraints that are not free to vary:**
  - The read-only gates (validity, safety) run before the opt-in and confirm gates and before any Claude — proven by tests asserting a sentinel invoker is never called on non-apply paths.
  - Only `applied` writes to disk. Every other outcome leaves the plan file bytes unchanged.
  - No `DetailError` from a malformed merge set escapes; it becomes a returned refusal result.
  - The bridge adds no gate logic of its own beyond wiring these existing primitives together — it reuses `_merge_is_safe` and `_confirm_merge` verbatim, matching the captured rule that a bridge supplies only the opt-in token plus a forwarded confirm.

## Tests

Add a `TestMergeBridge` class in `tests/test_detail.py`, reusing `_build_merge_plan` (canonical 4-step plan, accepts `statuses={id: StepStatus...}`) and the `_GOOD_BODY` valid seven-section constant. Model the matrix on `tests/test_launcher.py`'s `escalate_to_split` cases and `tests/test_scope_out.py`'s `scope_out_step` cases.

- `test_recommends_when_opt_in_off` — opt-in `False`, safe set → `recommended`; plan bytes unchanged; sentinel invoker never called.
- `test_recommends_on_declined_confirm` — opt-in `True`, `prompt_fn` returns `"n"` → `recommended`; no mutation.
- `test_recommends_on_non_tty` — opt-in `True`, non-TTY, no `yes` → `recommended` (auto-decline).
- `test_unsafe_when_member_non_pending` — a member already `DONE` (`statuses={2: StepStatus.DONE}`) → `unsafe`; `blocking` names it; no mutation; no Claude.
- `test_unsafe_when_downstream_non_pending` — a non-PENDING step after the region → `unsafe`; `blocking` names it.
- `test_invalid_on_fewer_than_two_ids` — one id → refusal (`invalid`); no raise; no mutation.
- `test_invalid_on_unknown_id` — an id not in the plan → refusal; no raise.
- `test_invalid_on_non_canonical_numbering` — a gapped plan → refusal; no raise.
- `test_invalid_on_mixed_scope` — members with mixed `scope` → refusal; no raise; no mutation.
- `test_applies_on_yes_bypass` — opt-in `True`, `yes=True`, `author_details=False`, sentinel invoker → `applied`; plan renumbered/folded; no Claude (proves the structural mutation alone).
- `test_applies_on_confirm_yes` — opt-in `True`, `prompt_fn` returns `"y"`, `author_details=False` → `applied`.
- `test_apply_forwards_invoker_to_re_author` — opt-in `True`, `yes=True`, `author_details=True`, `invoker=lambda _p: _GOOD_BODY` → `applied` with a non-empty `MergeResult.detail_results` (proves the re-author seam is forwarded, not bypassed).
- `test_only_applied_mutates` — capture plan bytes before each non-applied outcome and assert unchanged.
- `test_result_is_frozen` — setting an attribute on the result raises (frozen dataclass).
- `test_outcome_vocabulary_is_closed` — the outcome strings seen across the matrix are exactly the documented set.

### Test-creation order (feature step)

This is a **feature** step — new behavior. Write the tests above alongside the bridge. Green-before-done gate: every new `TestMergeBridge` test must pass, and the existing `TestMergeSteps` / `TestMergeIsSafe` suites must stay green, before this step is finished. Run the fast loop during dev: `uv run pytest tests/test_detail.py -q`.

## Acceptance criteria

- `merge_bridge` (or the chosen name) exists in `plan_tool/detail.py` and returns a frozen result whose `outcome` is one of the closed documented set; only `applied` writes to disk.
- With the opt-in off, a safe merge set returns `recommended`, leaves the plan file bytes unchanged, and never calls the invoker.
- A run-state-unsafe set (non-PENDING member or non-PENDING downstream step) returns `unsafe` with the blocking ids from `_merge_is_safe`, and spends no Claude.
- A malformed set (fewer than two ids, unknown id, non-canonical, or mixed-scope) returns a refusal outcome and never raises `DetailError` out of the bridge.
- With opt-in + confirm (or `-y`) + safety all holding, the bridge calls `merge_steps`, the plan is renumbered/folded, and the result is `applied` carrying the `MergeResult`.
- No new `review.Recommendation` source token and no new merge/renumber primitive are introduced; the bridge reuses `_merge_is_safe`, `_confirm_merge`, and `merge_steps`.
- All new `TestMergeBridge` tests pass and `TestMergeSteps` / `TestMergeIsSafe` remain green.

## References

- [dataclasses — Data Classes (frozen=True)](https://docs.python.org/3/library/dataclasses.html) — the frozen immutable result object the bridge returns, mirroring `EscalateResult` / `ScopeOutResult`.
- [io — isatty() on stream objects](https://docs.python.org/3/library/io.html#io.IOBase.isatty) — the TTY check behind `_confirm_merge`'s non-TTY auto-decline.
- [pytest: How to monkeypatch/mock modules and environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — overriding the `invoker` seam and `prompt_fn` so the bridge's gate tests stay deterministic and never spawn a real backend.

## Deferred

- **Wiring the bridge into the walk** — step 5 dispatches a surfaced `granularity-merge` finding to this bridge (`plan_tool/review_walk.py`, `plan_tool/cli/review_actions.py`); step 2 ships only the primitive and its unit tests.
- **Re-ground bridge** — the `≥2 already-built steps` re-ground / re-baseline remedy is a different bridge that must never route to `plan-tool merge`; step 3 owns it in `plan_tool/reground.py`.
- **Distinct suggested-action strings** — making `granularity-merge` vs re-ground findings emit distinct parseable actions is step 4 (`plan_tool/granularity.py`, `plan_tool/review.py`).
- **A `yes` param on `_confirm_merge`** — left unchanged; the bridge handles the `-y` bypass itself so the existing `cmd_merge` caller in `plan_tool/cli/authoring.py` is untouched.
