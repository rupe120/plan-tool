> **Auto-archived**: this plan was swept on 2026-07-08 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Rewrite the stale-directive guard to check each directive's own targets

## Summary

Rewrites `_saved_directive_is_stale` in `plan_tool/cli/review_actions.py` so it compares each directive finding's **own target steps** against the plan on disk instead of the **whole-plan fingerprint**. The guard changes from a no-argument closure to one that takes the `rec`, recovers its target step ids through step 2's `directive_target_ids`, and recomputes step 1's `compute_target_signature` from the current plan to compare against the `target_signature` the finding was saved with. When the saved and recomputed signatures match, the directive's targets are unchanged, so the guard reports fresh — even if some other step was edited earlier in a mixed-finding walk. The two callers (`_dispatch_reground_remedy` and `_dispatch_merge_remedy`) pass `rec` through. On green, a re-ground or merge directive whose own target steps still hold their `(id → title)` identity actuates under `--apply-structural` even after an earlier apply rewrote the plan; a directive whose targets moved is still downgraded to recommend-only.

## Table of Contents

- [Why](#why) — what the coarse whole-plan guard gets wrong in a mixed walk
- [Input](#input) — the field, helper, and recovery function steps 1 and 2 produce
- [Files (creates vs edits)](#files-creates-vs-edits) — the guard rewrite and its two call sites, plus tests
- [Implementation](#implementation) — the new per-directive comparison, the legacy fallback, and the ordering that must hold
- [Tests](#tests) — precise-match, precise-mismatch, legacy fallback, and the preserved short-circuit
- [Acceptance criteria](#acceptance-criteria) — observable results on green
- [References](#references) — stdlib docs for the hash and dataclass field
- [Deferred](#deferred) — the split guard (step 4), the other two staleness surfaces, and stamping

## Why

The structural-remedy walk refuses to apply a **stale saved directive** — a re-ground or merge finding whose saved step ids may now name different steps after a plan edit. Today `_saved_directive_is_stale` (`plan_tool/cli/review_actions.py`) decides that by comparing a whole-plan fingerprint: `bool(saved_plan_fingerprint) and saved_plan_fingerprint != compute_plan_fingerprint(plan_path)`. That is too coarse. In a mixed-finding walk, applying **any** earlier finding rewrites the plan file, so the whole-plan fingerprint no longer matches and every later re-ground/merge directive is downgraded to recommend-only — **even when its own target steps are untouched**. That makes `--apply-structural` a no-op for those remedies in any walk that also applied something else first. Step 3 replaces the whole-plan comparison with a per-directive one keyed on the finding's actual targets, so an unrelated edit elsewhere no longer downgrades a still-valid directive, while a real change to the directive's targets still does.

## Input

- **Step 1 produces the field and the hash helper.** `Recommendation.target_signature: Optional[str] = None` (`plan_tool/review.py`) and `compute_target_signature(plan, target_ids) -> str` (`plan_tool/review_walk.py`). This step reads the field and calls the helper; it defines neither. `None` means the finding was never stamped (legacy sidecar, or a producer that carries no directive) — the guard treats `None` as "fall back to the old coarse check", so nothing regresses.
- **Step 2 produces the target-id recovery function.** `directive_target_ids(rec) -> Optional[tuple[int, ...]]` (`plan_tool/review_walk.py`), which returns the step ids a directive-carrying finding targets, or `None` for a non-directive rec. It recovers merge/re-ground ids through `merge_remedy_target` and returns `(rec.step_id,)` for a medium `granularity-split`. **Reuse it — do not re-derive the target ids in the guard.** The whole point of the shared function is that the ids hashed at stamp time (step 2) and the ids recomputed at guard time (this step) can never diverge; re-deriving them here would silently break the equality contract even with an identical hasher.
- **The callers already parse the directive.** Both `_dispatch_reground_remedy` and `_dispatch_merge_remedy` call `parse_merge_action(rec)` before reaching the guard, so a rec that reaches the guard is a real directive. The guard still handles a `None` recovery defensively (see Implementation).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — rewrite the `_saved_directive_is_stale` closure to take `rec` and compare the directive's own target signature; update its docstring (the current text advertises the coarse whole-plan behavior and names BACKLOG #93 as the fix — that framing is this step). Add `directive_target_ids` and `compute_target_signature` to the function-body `from plan_tool.review_walk import (...)` block (the one inside the builder, near `merge_remedy_target`). Update the two call sites — the guard call in `_dispatch_reground_remedy` and the one in `_dispatch_merge_remedy` — to pass `rec`.
  - `tests/cli/test_review_actions.py` — add cases under `TestRegroundRemedyDispatch` (and/or `TestMergeRemedyDispatch`) for the per-directive precise match, precise mismatch, and legacy fallback; confirm the existing coarse-fingerprint tests still pass because their recs carry no `target_signature`.

## Implementation

**Change the guard's shape from whole-plan to per-directive.** The core rule this step adds: a directive is stale only when **its own target steps** changed, not when the plan changed anywhere. Recommended flow for the rewritten `_saved_directive_is_stale(rec)`:

- **Recover the target ids first.** Call `directive_target_ids(rec)`. If it returns `None` (not a directive shape — shouldn't happen from these two callers, but stay defensive), fall back to the coarse whole-plan check so behavior is never more permissive than today.
- **Fall back to coarse when the finding was never stamped.** If `rec.target_signature is None`, the finding predates stamping (step 2) or came from a producer that doesn't stamp — there is no per-directive signal to compare, so use the old `bool(saved_plan_fingerprint) and saved_plan_fingerprint != compute_plan_fingerprint(plan_path)` result. This is what keeps every existing coarse-fingerprint test green and every legacy sidecar behaving exactly as before.
- **Otherwise compare the directive's own signature.** Parse the plan (`parse_plan(plan_path)`), recompute `compute_target_signature(plan, target_ids)`, and return `recomputed != rec.target_signature`. Equal → fresh (not stale) → let the bridge actuate. Different → the target ids now name different steps (a title changed, or a renumber shifted them) → stale → downgrade to recommend-only.
- **Handle a parse failure gracefully.** `parse_plan` can raise `ParseError` / `ValidationError` (both already imported in this module); `compute_plan_fingerprint` reads bytes and never raises. One safe option: on a parse error, fall back to the coarse whole-plan check rather than letting the exception escape the guard. Pick whichever keeps the guard total — it must always return a bool.

**The key design decision** is the fallback-to-coarse-on-`None` behavior. The alternative — treating an unstamped finding as always-fresh (never stale) — would let a genuinely stale legacy directive fold the wrong steps, which is worse than today. Falling back to the coarse check preserves the current safety floor for unstamped findings while giving stamped findings the precise check.

**Constraints and gotchas that must hold:**

- **Reuse `directive_target_ids` and `compute_target_signature` — never re-implement either.** The ids selected here must be the same ids step 2 hashed at save time, and the hash must be the same function. Divergence on either side silently breaks the match with no visible error.
- **Keep the guard's position in each dispatcher unchanged.** In `_dispatch_reground_remedy` it must still run **after** the `rec.id in state.applied_structural_finding_ids` session-signal short-circuit and **before** the `reground_bridge` call; in `_dispatch_merge_remedy` it must still run after the same session short-circuit and before `merge_bridge`. The session signal handles the "applied earlier this walk, then re-dispatched" case; moving the guard ahead of it would re-break that path. Both dispatchers already carry comments marking this ordering.
- **Update both call sites in the same edit.** The closure signature changes from `()` to `(rec)`; leaving either call site calling `_saved_directive_is_stale()` is a `TypeError` at walk time. Both callers have the `rec` in scope.
- **Don't touch `saved_plan_fingerprint` plumbing.** The kwarg on `_build_review_action_fn` stays; the coarse fallback still uses it. This step only adds the per-directive path in front of it.
- **`Plan.step_by_id` raises on a missing id — but that concern lives inside `compute_target_signature` (step 1), which already builds an `{id: title}` map with `.get()` so a renumbered-away target digests to a distinct sentinel instead of crashing.** The guard just passes the ids through; it does not look up steps itself.

The foundational logic here — "is this saved directive still valid against the plan on disk" — is one of three staleness surfaces in the tool. The other two (`convergence_cmd.py:classify_report_staleness` and the `plan_match` rule shared by `review_cmd.py`/`reconcile.py`) key on different fingerprint axes and their own dataclasses; they are intentionally **not** consolidated with this one (see Deferred).

## Tests

Add to `tests/cli/test_review_actions.py`, driving through `_build_review_action_fn(...)` + `action(rec)` (the public builder seam) exactly like the existing `TestRegroundRemedyDispatch` / `TestMergeRemedyDispatch` cases — reuse `_stub_reground_bridge` / `_stub_merge_bridge`, `_reground_rec`, and the merge equivalents. Enumerate:

- `test_matching_target_signature_actuates_despite_plan_edit` — a re-ground rec whose `target_signature` equals `compute_target_signature` for the on-disk plan actuates the bridge even when `saved_plan_fingerprint` differs from the plan's whole-plan fingerprint (the mixed-walk case the step fixes). Asserts the bridge is called once.
- `test_mismatched_target_signature_downgrades` — a re-ground rec whose stamped `target_signature` no longer matches the recomputed one (e.g. a target step's title changed on disk) is downgraded: bridge never called, `state.apply_skip is True`, message says the plan changed.
- `test_none_target_signature_falls_back_to_coarse_stale` — a rec with `target_signature=None` and a non-empty, non-matching `saved_plan_fingerprint` is downgraded via the coarse fallback (pins that legacy findings keep today's behavior). This is what the existing `test_stale_reground_downgrades` / `test_stale_reground_with_coincidental_done_ids_downgrades` already exercise since `_reground_rec()` sets no signature — confirm they still pass rather than duplicating them.
- `test_none_target_signature_empty_fingerprint_does_not_block` — the existing `test_empty_saved_fingerprint_does_not_block` still holds under the rewrite (empty fingerprint + `None` signature → coarse fallback → not stale).
- `test_matching_signature_merge_actuates_despite_plan_edit` — the merge-side mirror of the first case through `TestMergeRemedyDispatch`.
- `test_applied_reground_resolves_before_guard` — confirm the `applied_structural_finding_ids` session short-circuit still runs ahead of the (now per-directive) guard, so an r-then-a re-dispatch resolves rather than re-checking staleness. (Existing `test_applied_reground_resolves_on_redispatch` covers this; verify it stays green.)

### Test-creation order (feature step)

This is a **feature** step — it changes what the guard reports. Add the new unit tests **with** the implementation; each covers one branch of the rewritten guard (precise match, precise mismatch, legacy `None` fallback, preserved session short-circuit). Green-before-done gate: every new test plus the unchanged existing `TestRegroundRemedyDispatch` / `TestMergeRemedyDispatch` stale/empty-fingerprint tests must pass before this step is finished.

## Acceptance criteria

- `_saved_directive_is_stale(rec)` takes the `rec` and returns `False` when `rec.target_signature` is non-`None` and equals `compute_target_signature(parse_plan(plan_path), directive_target_ids(rec))`, **even when `saved_plan_fingerprint` differs from the plan's whole-plan fingerprint**.
- `_saved_directive_is_stale(rec)` returns `True` when a non-`None` `target_signature` no longer matches the recomputed signature.
- With `rec.target_signature is None`, the guard reproduces the old coarse result: stale iff `bool(saved_plan_fingerprint) and saved_plan_fingerprint != compute_plan_fingerprint(plan_path)`.
- Both `_dispatch_reground_remedy` and `_dispatch_merge_remedy` call the guard with `rec`, and the guard still runs after the `applied_structural_finding_ids` short-circuit and before the bridge call in each.
- The guard never raises: a `parse_plan` failure yields a bool (coarse fallback), not an exception.
- New and existing `TestRegroundRemedyDispatch` / `TestMergeRemedyDispatch` tests in `tests/cli/test_review_actions.py` pass; `uv run pytest tests/cli/test_review_actions.py -q` is green.

## References

- [dataclasses — Data Classes (Python Standard Library)](https://docs.python.org/3/library/dataclasses.html) — the `target_signature` field this guard reads is an optional dataclass field with a `None` default; useful for confirming `None` is the unstamped sentinel.
- [hashlib — Secure hashes and message digests (Python Standard Library)](https://docs.python.org/3/library/hashlib.html) — background on the SHA-256 digest `compute_target_signature` returns and this guard compares for equality.
- [typing — Optional](https://docs.python.org/3/library/typing.html#typing.Optional) — the `Optional[str]` / `Optional[tuple[int, ...]]` return shapes the guard branches on (`None` from `directive_target_ids` and from `target_signature`).

## Deferred

- **The `granularity-split` MIXED-STEP guard — step 4.** This step rewrites the guard for the two directive dispatchers that gate on it today (re-ground, merge). Extending precise per-directive staleness to the split path is step 4's work.
- **Consolidating the other two staleness surfaces** — `convergence_cmd.py:classify_report_staleness` and the `review_cmd.py`/`reconcile.py` `plan_match` rule — is out of scope. They key on different fingerprint axes and dataclasses; folding them into this guard is a cross-module refactor beyond this step. Route any such find to the backlog for reconcile.
- **Stamping the signature onto findings** — owned by step 2 (`stamp_target_signatures` before each `save_review`). This step only reads the stamped field.
- **Defining `target_signature`, `compute_target_signature`, and `directive_target_ids`** — owned by steps 1 and 2; this step imports and uses them unchanged.
