> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add per-remedy `--merge` and `--reground` opt-in flags to the reconcile walk

## Summary

Today the reconcile walk has one umbrella opt-in, `--apply-structural`, that enables **both** structural bridges at once — a pairwise `merge` fold and a re-ground mark-done. This step adds two granular flags, `--merge` and `--reground`, to `reconcile-plan` and `reconcile-plan-walk`, so an operator can turn on just one remedy. The change is confined to `plan_tool/cli/review_cmd.py` (parser flags + three builder call sites) and `plan_tool/cli/review_actions.py` (split the single `allow_structural_remedy` gate into two per-remedy opt-ins that each drive their own dispatcher). `--apply-structural` stays as the both-remedies umbrella so every existing caller — including the completeness-apply lane, which never passes the merge/reground opt-in anyway — is unchanged. On green, `reconcile-plan-walk <name> --merge` lets a merge directive fold on apply while a re-ground directive in the same walk stays recommend-only (and the reverse for `--reground`).

## Table of Contents

- [Why](#why) — what the single umbrella flag can't express and why the split matters
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files, the two generated docs, and the one test file
- [Implementation](#implementation) — the two per-remedy opt-ins, the gate split, and the invariants that must hold
- [Tests](#tests) — builder-seam unit coverage for each per-remedy flag
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the tests to add with the code and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — argparse and pytest docs for this step
- [Deferred](#deferred) — completeness-apply, the umbrella flag, and other out-of-scope items

## Why

The reconcile walk can actuate two structural bridges: a `merge` directive folds adjacent over-fragmented steps (`plan_tool/detail.py:merge_bridge`), and a `reground` directive marks already-built steps done (`plan_tool/reground.py:reground_bridge`). Both are gated behind one flag, `--apply-structural`, which flips **both** on together. An operator who trusts the tool to fold merges but wants to eyeball every re-ground (or the reverse) has no way to say so — it's all-or-nothing. This is the first of the three remaining "convenience arms" tracked in `BACKLOG.md` #70: give each remedy its own opt-in so the operator can enable exactly the one they want. The split is cheap because the two dispatchers (`_dispatch_merge_remedy` and `_dispatch_reground_remedy` in `plan_tool/cli/review_actions.py`) are already separate — only the shared `allow_structural_remedy` gate token binds them together.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — add two default-off kwargs to `_build_review_action_fn` (one per remedy), compute each dispatcher's effective opt-in as `umbrella OR its own flag`, and gate `_dispatch_merge_remedy` / `_dispatch_reground_remedy` on their own token. Update the `allow_structural_remedy` docstring paragraph and the two recommend-only messages that name `--apply-structural`.
  - `plan_tool/cli/review_cmd.py` — add `--merge` and `--reground` `store_true` flags to the `reconcile-plan` parser (`p_review`) and the `reconcile-plan-walk` parser (`p_review_walk`); thread them into the three `_build_review_action_fn` call sites (the reuse path and the fresh-walk path in `cmd_review`, and the walk in `cmd_review_walk`).
  - `docs/cli/reconcile-plan.md` — regenerated flag reference gaining the two new rows (this file is generated, not hand-edited — see Implementation).
  - `docs/cli/reconcile-plan-walk.md` — same, regenerated.
  - `tests/cli/test_review_actions.py` — add builder-seam tests pinning that each per-remedy flag enables only its own bridge.

## Implementation

**Foundational change: split the one `allow_structural_remedy` opt-in into two per-remedy opt-ins.** Today `_dispatch_merge_remedy` and `_dispatch_reground_remedy` each call `structural_apply_allowed(allow_structural_remedy, state)` — the same token. Give each dispatcher its own token so a flag can enable one without the other.

- **Add two default-off kwargs to `_build_review_action_fn`.** One gates merge, one gates re-ground. Name them for what they are — one way: `allow_merge_remedy: bool = False` and `allow_reground_remedy: bool = False`, matching the existing `allow_structural_remedy` naming. Both default False, so every call site that doesn't pass them behaves exactly as before.
- **Keep `allow_structural_remedy` as the both-remedies umbrella.** Compute each dispatcher's effective opt-in once near the top of the builder body, as `allow_structural_remedy or allow_<remedy>_remedy`. Then `_dispatch_merge_remedy` gates on `structural_apply_allowed(<effective merge opt-in>, state)` and `_dispatch_reground_remedy` on `structural_apply_allowed(<effective reground opt-in>, state)`. This keeps the umbrella meaning "both on" — the key back-compat rule, because `TestMergeRemedyDispatch` / `TestRegroundRemedyDispatch` and the three review_cmd call sites all still pass `allow_structural_remedy` and must keep folding/re-grounding.
- **Do not touch `structural_apply_allowed` itself.** Its `opt_in and not state.yes_to_all` rule is unchanged — the split happens at the *caller*, by passing a different `opt_in` per dispatcher. This preserves the shared invariant that a `-y` blanket fast-forward never auto-confirms an irreversible structure mutation, for the new flags too.
- **Leave the escalation dispatcher alone.** `_dispatch_structural_escalation` gates on `allow_split`, a different token for the inverse operation (split). It is out of this step — only merge and re-ground get per-remedy flags.

**Wire the two flags in `plan_tool/cli/review_cmd.py`.**

- **Add `--merge` and `--reground` `store_true` flags** to both `p_review` (the `reconcile-plan` parser) and `p_review_walk` (the `reconcile-plan-walk` parser), beside the existing `--apply-structural` argument in each. Pick a `dest` that won't shadow anything — one way: `dest="merge_remedy"` / `dest="reground_remedy"` (a bare `--merge` reading into `args.merge` also works; the flag name is what the operator types either way).
- **Thread them into the three builder calls.** `cmd_review` builds `_build_review_action_fn` twice (the reuse path and the fresh-walk path); `cmd_review_walk` builds it once. Each already reads `allow_structural_remedy=getattr(args, "apply_structural", False)`; add `allow_merge_remedy=getattr(args, "<merge dest>", False)` and `allow_reground_remedy=getattr(args, "<reground dest>", False)` alongside it. Use `getattr(..., False)` for the same reason the existing line does — the reuse/fresh-walk builders are reached from a namespace that may not carry the attr.
- **Match the umbrella's help-text convention.** The two new flags are the granular counterparts to `--apply-structural`; write one-line help that says each enables only its own bridge and points at `--apply-structural` for both. State the two gotchas that carry over: a `-y` fast-forward still forces recommend-only, and `--reground` still needs `--include-info` to surface the re-ground finding at all (a merge directive stays visible without it).

**Regenerate the two `docs/cli/` files — don't hand-edit them.** `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` are generated from the argparse parser and drift-guarded by `tests/cli/test_cli_reference.py`. After the flags land in `review_cmd.py`, regenerate with `python -m plan_tool.cli_reference --write`; the new rows appear from the flag help. The drift guard fails until the docs match, so this is a required part of the step, not optional polish.

**Update the recommend-only messages in the two dispatchers.** `_dispatch_reground_remedy`'s "recommended" branch tells the operator to `pass --apply-structural (with --include-info)`; `_dispatch_merge_remedy`'s "recommended" branch says `pass --apply-structural and confirm on a TTY to fold them`. Update both to name the granular flag too (e.g. "pass `--reground` or `--apply-structural`"), so an operator who reached recommend-only knows the narrow flag exists.

Constraints and gotchas that are **not** free to vary:

- **The umbrella must still enable both.** Any operator or test passing `allow_structural_remedy=True` (no granular flag) gets both bridges. The OR wiring guarantees this; don't replace the umbrella with the two granular kwargs.
- **The two new kwargs default False.** Adding them must not change any existing caller that omits them — the completeness-apply lane (`plan_tool/cli/completeness_cmd.py`) passes only `allow_split`, never the merge/reground opt-in, so it stays recommend-only for these bridges exactly as today.
- **`--reground` alone does not surface the finding.** The re-ground directive is info-level and hidden unless `--include-info` is passed; `--reground` only changes what happens on *apply*, not visibility. Say this in the help so the flag isn't mistaken for a visibility toggle.
- **No new gate rule.** All three dispatchers keep routing through `structural_apply_allowed`; the only change is which opt-in token each one receives.
- **Forward the two new kwargs through every internal sub-builder rebuild.** `_build_review_action_fn` calls itself to build a nested sub-walk in two places (the detail-reconcile sub-walk paths, `review_actions.py:233` and `:329`), each already forwarding `allow_structural_remedy=`. Add `allow_merge_remedy=` and `allow_reground_remedy=` to both recursive calls too, so a nested sub-walk inherits the granular opt-ins instead of dropping them while keeping the umbrella. Wire every reconstruction/forward site uniformly, even where the sub-walk can't currently surface a merge/reground directive — an un-threaded site is a latent parity break. This applies because these are **enable** opt-ins: like the umbrella `allow_structural_remedy` they gate *whether* a remedy actuates, so they follow the umbrella's own forwarding into the recursion for parity. Step 6's `reground_rebaseline` is a different kind of kwarg — a **disposition selector** that only chooses *how* an already-enabled re-ground actuates — and is deliberately **not** forwarded into these same recursive calls; the single propagation rule reconciling the two steps is stated in step 6's Implementation.

## Tests

All new tests go in `tests/cli/test_review_actions.py`, driving the public `_build_review_action_fn` seam (its `_build` helpers in `TestMergeRemedyDispatch` / `TestRegroundRemedyDispatch` already pass builder kwargs and stub the bridges).

- `test_merge_flag_alone_enables_merge_bridge` — `allow_merge_remedy=True` (no umbrella) makes a merge directive call `merge_bridge` with `allow_merge=True`.
- `test_merge_flag_alone_leaves_reground_recommend_only` — with only `allow_merge_remedy=True`, a re-ground directive calls `reground_bridge` with `allow_reground=False` (recommend-only).
- `test_reground_flag_alone_enables_reground_bridge` — `allow_reground_remedy=True` (no umbrella) makes a re-ground directive call `reground_bridge` with `allow_reground=True`.
- `test_reground_flag_alone_leaves_merge_recommend_only` — with only `allow_reground_remedy=True`, a merge directive calls `merge_bridge` with `allow_merge=False`.
- `test_umbrella_still_enables_both_bridges` — `allow_structural_remedy=True` (no granular flag) enables both merge and re-ground (the back-compat pin; complements the existing `test_merge_opt_in_passed_when_apply_structural_enabled` and the re-ground equivalent).
- `test_merge_flag_forced_off_under_yes_to_all` — `allow_merge_remedy=True` with `WalkState(yes_to_all=True)` passes `allow_merge=False` (fast-forward never auto-confirms), mirroring `test_merge_opt_in_forced_off_under_yes_to_all`.
- `test_per_remedy_flags_default_false` — a builder with neither umbrella nor granular flag leaves both bridges recommend-only (`allow_merge`/`allow_reground` both False).
- `test_narrow_flag_still_refuses_stale_saved_directive` — with only a per-remedy opt-in set (`allow_merge_remedy=True`, and the re-ground mirror), a directive whose saved directive is stale is refused by `_saved_directive_is_stale` before the opt-in gate, so the narrow flag never bypasses the stale-directive guard (closing the "widen the mutation surface" risk).

CLI-integration tests (one `main([...])`-driven assertion per new flag, closing the argparse-`dest` → `getattr(args, ...)` → builder-kwarg threading the builder-seam tests above can't reach). Extend the existing `--apply-structural` spy harness (the `TestRegroundApplyStructuralFlag` pattern that patches `_build_review_action_fn` to capture its kwargs) so the real CLI path is exercised across all three `cmd_review` / `cmd_review_walk` call sites:

- `test_merge_flag_reaches_builder_via_cli` — `main(["reconcile-plan-walk", <name>, "--merge"])` (with `_build_review_action_fn` spied) captures `allow_merge_remedy=True` and `allow_reground_remedy=False`, proving the flag's `dest` threads through the real argparse → builder path.
- `test_reground_flag_reaches_builder_via_cli` — the same via `main([..., "--reground"])` captures `allow_reground_remedy=True` and `allow_merge_remedy=False`.

These catch a wrong `dest` or a missed call site — the "un-threaded site is a latent parity break" hazard — that the builder-seam tests and `tests/cli/test_cli_reference.py` (which only proves the flag reached argparse) cannot.

### Test-creation order (feature step)

This is a **feature** step — new behavior (two per-remedy opt-ins). Add the tests above **with** the implementation:

1. Add the two kwargs and the gate split in `review_actions.py`, then write the four flag-alone tests and the default-false test — each asserts the bridge stub's `allow_merge`/`allow_reground` kwarg.
2. Add the umbrella-still-both pin and the yes-to-all pin.
3. Add the flags in `review_cmd.py`, regenerate the two `docs/cli/` files, and add the two `main([...])`-driven CLI-integration tests (extending the `TestRegroundApplyStructuralFlag` spy harness) so each flag's `dest`-to-builder-kwarg threading is exercised through the real CLI path; confirm `tests/cli/test_cli_reference.py` passes (the doc drift guard proves only that each flag reached argparse — the integration tests prove the threading).

Green-before-done gate: every new test in `tests/cli/test_review_actions.py` — including the two `main([...])`-driven CLI-integration tests — is green, the existing `TestMergeRemedyDispatch` / `TestRegroundRemedyDispatch` tests stay green unchanged, and `tests/cli/test_cli_reference.py` passes.

## Acceptance criteria

- `_build_review_action_fn` accepts two new default-off kwargs, one per remedy; omitting them reproduces current behavior unchanged.
- With only the merge opt-in set (no umbrella), `_dispatch_merge_remedy` calls `merge_bridge(..., allow_merge=True)` and `_dispatch_reground_remedy` calls `reground_bridge(..., allow_reground=False)` — and the reverse for the re-ground opt-in.
- `allow_structural_remedy=True` with neither granular flag still enables both bridges.
- Any per-remedy opt-in under `WalkState(yes_to_all=True)` passes `allow_...=False` to its bridge (fast-forward stays recommend-only).
- A narrow-flag-only walk still refuses a stale saved directive: with only a per-remedy opt-in set, `_saved_directive_is_stale` blocks before the opt-in gate, so the narrow flag never bypasses the stale-directive guard.
- `reconcile-plan --help` and `reconcile-plan-walk --help` list `--merge` and `--reground`; `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` each carry a row for both, and `tests/cli/test_cli_reference.py` passes.
- A `main([...])`-driven CLI-integration test per new flag (spying on `_build_review_action_fn`) proves each flag's argparse `dest` threads to its builder kwarg through the real CLI path across the `cmd_review` / `cmd_review_walk` call sites — catching a wrong `dest` or a missed site the doc-drift guard cannot.
- The `completeness-apply` lane is unaffected — it never passes the merge/reground opt-in, so it stays recommend-only for both bridges.
- The full new-test set in `tests/cli/test_review_actions.py` is green; existing merge/reground dispatch tests pass unmodified.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — reference for adding the two `store_true` flags and choosing `dest` on the `reconcile-plan` / `reconcile-plan-walk` subparsers.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — the `tmp_path` fixture the `TestMergeRemedyDispatch` / `TestRegroundRemedyDispatch` `_build` helpers use to construct a `PlanToolContext` and stub the bridges hermetically.

## Deferred

- **Per-remedy flags on `completeness-audit` / `completeness-apply`** — those verbs live in `plan_tool/cli/completeness_cmd.py` (out of this step's files) and their `--apply-structural` gates only `allow_split`, not the merge/reground umbrella, so there's no per-remedy split to make there. Follow-up if that lane ever wires the merge/reground bridges.
- **Retiring or renaming `--apply-structural`** — it stays as the both-remedies umbrella; collapsing the three flags into one shape is a separate #70 convenience arm (dispatcher consolidation), not this one.
- **`--merge` / `--reground` on the `convergence` command** — convergence actuates scope-out and split, not merge/re-ground, so it has no merge/reground opt-in to add.
- **Consolidating the three bridge dispatchers' apply-or-recommend gate into one shape** — a separate #70 arm; this step only splits the opt-in token, it does not merge the dispatchers.
