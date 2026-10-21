> **Auto-archived**: this plan was swept on 2026-07-09 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Wire the re-ground re-baseline disposition through the reconcile walk with an opt-in flag

## Summary

Expose step 5's re-baseline disposition on `reground_bridge` through the reconcile walk so an operator can, on apply, have a re-ground finding write a `create --from-existing` re-baseline seed for the flagged already-built steps in addition to marking them done. The change is confined to two source files: `plan_tool/cli/review_actions.py` (a new default-off builder kwarg that `_dispatch_reground_remedy` forwards as the disposition + `repo_root` to `reground_bridge`, plus the applied-branch message naming the written seed) and `plan_tool/cli/review_cmd.py` (a new `--reground-rebaseline` flag on both `reconcile-plan` and `reconcile-plan-walk`, threaded into the three builder call sites). The key design decision: model this as a **disposition selector**, not an enable toggle — it changes *how* a re-ground actuates, never *whether* it does, so it stays orthogonal to the existing `--apply-structural` enable opt-in (and, if step 4 has landed, its `--merge`/`--reground` opt-ins). On green, `reconcile-plan-walk <name> --apply-structural --include-info --reground-rebaseline` writes a re-baseline seed under `plan-seeds/` and marks the flagged steps done, while the same walk without the flag keeps today's mark-done-only behavior unchanged.

## Table of Contents

- [Why](#why) — what the re-baseline disposition can't reach today and why the walk flag closes it
- [Input](#input) — the step-5 disposition contract this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two source files, the two generated docs, and the one test file
- [Implementation](#implementation) — the disposition selector, the dispatcher wiring, and the invariants that must hold
- [Tests](#tests) — builder-seam unit coverage for the disposition flag
- [Test-creation order (feature step)](#test-creation-order-feature-step) — the tests to add with the code and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — argparse and pytest docs for this step
- [Deferred](#deferred) — completeness-apply, the reconcile lane, auto-selection, and other out-of-scope items

## Why

Step 5 gives `plan_tool/reground.py:reground_bridge` a second disposition — write a `create --from-existing` re-baseline seed for the flagged already-built steps, then mark them done — but nothing reaches it from the walk. The reconcile walk's `_dispatch_reground_remedy` in `plan_tool/cli/review_actions.py` always calls `reground_bridge` with its default `mark-done` disposition, so the re-baseline arm is callable only in a unit test, never from `reconcile-plan` / `reconcile-plan-walk`. An operator who wants the re-ground remedy to hand off a re-decompose seed (rather than only flip statuses to `done`) has no flag to ask for it. This step adds that flag and the one-line dispatcher wiring, finishing Arm 3 of BACKLOG #70: the re-ground actuator can, under an explicit opt-in, emit a re-baseline seed instead of only marking done, with mark-done staying the default.

## Input

This step consumes the disposition contract that **step 5** adds to `plan_tool/reground.py`:

- **`reground_bridge` accepts a disposition selector and a repo-root kwarg.** Step 5 adds a disposition kwarg (default `mark-done`) plus two module constants, and a repo-root kwarg (`Path | None = None`) used only by the re-baseline arm. Grep `plan_tool/reground.py` at HEAD for the actual symbol names — the constant names (likely `DISPOSITION_MARK_DONE` / `DISPOSITION_REBASELINE`), the disposition kwarg name (likely `disposition=`), and the repo-root kwarg name (likely `repo_root=`) — and use whatever step 5 shipped; these names are illustrative, not fixed, and step 5 is free to name them differently. The re-baseline arm writes the seed first, then still calls the shared mark-done, and keeps `outcome="applied"`.
- **`RegroundResult` carries a seed-path field.** Step 5 adds an optional seed-path field (likely `seed_path: Optional[Path] = None`), populated only on an applied re-baseline. Confirm the actual field name in `plan_tool/reground.py` at HEAD and use whatever step 5 shipped; this step reads it to name the written seed in the walk status line.
- **The five `RegroundResult` outcome strings are unchanged.** `applied` / `recommended` / `unsafe` / `step-missing` / `noop` all keep their meaning; only the applied re-baseline path additionally sets `seed_path`.

Do not restate step 5's seed renderer, collision-safe path helper, or gate order here — pass the confirmed disposition + repo-root kwargs and trust the bridge.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/review_actions.py` — add one default-off kwarg to `_build_review_action_fn` (recommend `reground_rebaseline: bool = False`); in `_dispatch_reground_remedy`, add step 5's disposition constants to the body-local `from plan_tool.reground import reground_bridge` line, forward `disposition=` (re-baseline when the flag is on, else mark-done) and `repo_root=ctx.repo_root` in the `reground_bridge(...)` call, and extend the applied-branch message to name `result.seed_path` when it is populated. Update the `_dispatch_reground_remedy` docstring to mention the disposition selector.
  - `plan_tool/cli/review_cmd.py` — add a `--reground-rebaseline` `store_true` flag to the `reconcile-plan` parser (`p_review`) and the `reconcile-plan-walk` parser (`p_review_walk`); thread it into the three `_build_review_action_fn` call sites (the reuse path and the fresh-walk path in `cmd_review`, and the walk in `cmd_review_walk`) using the same `getattr(args, "reground_rebaseline", False)` idiom the sibling opt-ins use.
  - `docs/cli/reconcile-plan.md` — regenerated flag reference gaining the new row (generated, not hand-edited — see Implementation).
  - `docs/cli/reconcile-plan-walk.md` — same, regenerated.
  - `tests/cli/test_review_actions.py` — add builder-seam tests pinning that the flag drives `reground_bridge`'s disposition/`repo_root` and that the default keeps mark-done.

## Implementation

**Foundational change: a disposition selector wired from the walk flag into the one `reground_bridge` call.** The core rule is that `_dispatch_reground_remedy` chooses which disposition to pass to `reground_bridge`, based on a new default-off builder kwarg, and the flag never changes whether the re-ground actuates.

- **Add a default-off builder kwarg, don't overload an existing one.** Add `reground_rebaseline: bool = False` (or a string disposition selector — see the alternative below) to `_build_review_action_fn`'s keyword-only signature in `plan_tool/cli/review_actions.py`. It must default off so every existing *external* caller — the reconcile-lane sites in `plan_tool/cli/reconcile.py` and the completeness-apply builder in `plan_tool/cli/completeness_cmd.py` — stays unchanged and keeps calling `reground_bridge` with the mark-done default. This mirrors how `allow_structural_remedy` (and, if step 4 has landed, its `allow_merge_remedy` / `allow_reground_remedy`) was added as a new default-off kwarg rather than folded into an existing flag.

- **Do not propagate `reground_rebaseline` into the sub-action recursion.** `_build_review_action_fn`'s two self-calls actively forward `allow_structural_remedy=allow_structural_remedy` into the sub-walk, so the enable opt-in *does* reach the recursion — but `reground_rebaseline` must **not**. Leave the two recursive calls unchanged so they invoke the sub-walk with the kwarg at its default (mark-done). The single propagation rule reconciling this step with step 4 is keyed to kwarg **kind**, not to whether the sub-walk can surface re-ground: an **enable** opt-in (`allow_structural_remedy`, and step 4's `allow_merge_remedy` / `allow_reground_remedy`) *is* forwarded into the recursion uniformly — following the umbrella's own forwarding for parity, so an un-threaded enable site can't become a latent parity break if the sub-walk ever gains that remedy — whereas a **disposition selector** like `reground_rebaseline` only chooses *how* an already-enabled remedy actuates and stays unforwarded. Non-propagation here is a deliberate application of that rule, not an oversight: the re-ground finding is emitted only by `cmd_review`'s own walk, never by the detail-reconcile sub-walk the recursion drives, so no re-ground bridge call is reachable through the recursion and forwarding the disposition there would select a disposition for a remedy that can never fire. Non-propagation is therefore harmless and keeps the disposition scoped to the top-level walk that actually surfaces re-ground findings. Step 4 threading `allow_reground_remedy` into the recursion while this step withholds `reground_rebaseline` is that one rule (enable threads, disposition does not), not a conflict.

- **Forward the disposition and `repo_root` in the single `reground_bridge(...)` call.** `_dispatch_reground_remedy` is the only caller of `reground_bridge` in the codebase. Extend its body-local `from plan_tool.reground import reground_bridge` line to also import step 5's disposition constants, then pass the disposition kwarg (re-baseline constant when `reground_rebaseline`, else mark-done constant) and the repo-root kwarg (`ctx.repo_root`) — using the actual kwarg/constant names step 5 shipped, per the confirm-at-HEAD note in [Input](#input). The dispatcher already closes over `ctx` (a `PlanToolContext` with `repo_root`) and `plan_path`, so no new plumbing is needed.
  - Pass `repo_root=ctx.repo_root` **unconditionally**. Step 5's bridge uses it only for the re-baseline arm, so it is harmless on the mark-done path and keeps the call site from silently breaking if a future default changes.

- **The flag is a disposition selector, not a visibility or enable toggle — keep every existing gate intact.** The re-ground still only actuates when its enable opt-in is on (`allow_structural_remedy`, or step 4's `allow_reground_remedy` if that step has landed) AND the finding is surfaced (`--include-info`, since the re-ground directive is info-level). `--reground-rebaseline` alone with neither the enable opt-in nor `--include-info` does nothing observable — the finding is hidden or the bridge returns `recommended`. Do not touch:
  - the pre-apply stale-directive guard (`_saved_directive_is_stale`) — it runs before the bridge regardless of disposition;
  - the `structural_apply_allowed(allow_structural_remedy, state)` / `yes_to_all` rule that forces `allow_reground=False` under a blanket apply;
  - the `yes=False` forwarding that keeps a genuine TTY confirm the only apply path;
  - the session stop-early check (`rec.id in state.applied_structural_finding_ids`) and the recommend-only default.

- **Name the seed in the applied message and direct the operator to retire the source plan.** In the `result.outcome == "applied"` branch, when the result's seed-path field (its confirmed name per [Input](#input)) is populated append a short clause naming it (e.g. `"; re-baseline seed written to <path>"`). Because step 5's seed is a *complete* `create --from-existing` input — the flagged steps as done-context **plus** every remaining committed step as scope-to-re-plan — running `create` on it produces a plan that supersedes the source plan's remaining scope; two live plans claiming the same unbuilt work is the failure mode. So the applied re-baseline status line must also tell the operator the seed **supersedes** the source plan's remaining scope and instruct them to re-create from it (`plan-tool create --from-existing <seed>`) and then **archive/retire the source plan** once the re-decompose lands. Leave the mark-done applied message unchanged when that field is `None`. The `noop` / `recommended` / `unsafe` / `step-missing` branches are unchanged.

- **Alternative rejected — a string disposition selector on the builder.** Passing `reground_disposition: str = <mark-done constant>` straight through would mirror step 5's named-selector shape more closely, but it forces `plan_tool/cli/review_cmd.py` to import step 5's constants to translate the `store_true` flag. A boolean kwarg keeps review_cmd free of the reground constants and does the boolean→constant translation inside the dispatcher, where the lazy reground import already lives. Recommend the boolean; the string form is acceptable if you prefer to single-source the constant names, but keep review_cmd from importing reground if you can.

- **Add the `--reground-rebaseline` flag to both parsers with the getattr-default idiom.** Add a `store_true` argument (dest `reground_rebaseline`) to `p_review` and `p_review_walk` in `plan_tool/cli/review_cmd.py`, next to the existing `--apply-structural` block in each. Thread it into all three `_build_review_action_fn` call sites (the reuse path and fresh-walk path in `cmd_review`, and the walk in `cmd_review_walk`) via `getattr(args, "reground_rebaseline", False)`. Missing one of the three silently disables the flag on that lane; reading the attr directly (not via `getattr`-default) can raise on the reuse/fresh-walk namespace that may omit it.
  - The help text must say it is a **disposition selector**: on apply it makes an actuated re-ground *also* write a `create --from-existing` re-baseline seed under `plan-seeds/` for the flagged already-built steps, in addition to marking them done. State plainly that it still needs the re-ground enabled (`--apply-structural`, or step 4's `--reground` if that step has landed) and surfaced (`--include-info`); it is not a visibility toggle. Model the wording on the existing `--apply-structural` help paragraph, which already spells out the `--include-info` dependency.

- **Regenerate the two CLI-reference docs — this is part of the step, not polish.** `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` are generated from the argparse parser by `python -m plan_tool.cli_reference --write` and drift-guarded by `tests/cli/test_cli_reference.py`. Never hand-edit them; run the regen after the flag lands. The drift test staying red until regenerated is the cheapest proof the flag actually reached argparse.

## Tests

New tests in `tests/cli/test_review_actions.py`, extending the existing `TestRegroundRemedyDispatch` class and its `_stub_reground_bridge` / `_reground_result` helpers (which record the kwargs passed to `reground_bridge`). The `_reground_result` stub gains a `seed_path` field so the applied-message test can assert the seed is named.

- `test_rebaseline_flag_forwards_rebaseline_disposition` — with `reground_rebaseline=True`, `_dispatch_reground_remedy` calls `reground_bridge` with the re-baseline disposition constant.
- `test_default_forwards_mark_done_disposition` — with the flag left at its default, the call passes the mark-done disposition (no behavior change for existing callers).
- `test_repo_root_forwarded_to_bridge` — the call passes `repo_root=ctx.repo_root` (so the re-baseline arm can place the seed).
- `test_applied_rebaseline_message_names_seed_path` — an applied outcome whose `seed_path` is set produces a walk status line naming the seed; an applied mark-done outcome (`seed_path=None`) keeps the unchanged message.
- `test_rebaseline_flag_does_not_enable_reground` — with `reground_rebaseline=True` but no enable opt-in, `allow_reground` stays `False` (the flag selects disposition only, never enables the remedy).

CLI-integration test (one `main([...])`-driven assertion for the new flag, closing the argparse-`dest` → `getattr(args, ...)` → builder-kwarg threading the builder-seam tests above can't reach). Extend the existing `--apply-structural` spy harness (the `TestRegroundApplyStructuralFlag` pattern that patches `_build_review_action_fn` to capture its kwargs) so the real CLI path is exercised across the three `cmd_review` / `cmd_review_walk` call sites:

- `test_rebaseline_flag_reaches_builder_via_cli` — `main(["reconcile-plan-walk", <name>, "--reground-rebaseline"])` (with `_build_review_action_fn` spied) captures `reground_rebaseline=True`, proving the flag's `dest` threads through the real argparse → builder path; the default run (no flag) captures `reground_rebaseline=False`. This catches a wrong `dest` or a missed call site — a silent parity break the doc-drift guard (which only proves the flag reached argparse) cannot.

## Test-creation order (feature step)

This is a **feature** step — new behavior. Add the five tests above **with** the implementation:

- Add `test_default_forwards_mark_done_disposition` and `test_rebaseline_flag_forwards_rebaseline_disposition` first — they pin the selector's two states directly against the recorded `reground_bridge` kwargs.
- Add `test_repo_root_forwarded_to_bridge` and `test_rebaseline_flag_does_not_enable_reground` to pin the two invariants (repo_root always forwarded; disposition never enables the remedy).
- Add `test_applied_rebaseline_message_names_seed_path` last, once the applied-branch message wiring is in place; extend the `_reground_result` stub with `seed_path`.
- Add the `main([...])`-driven `test_rebaseline_flag_reaches_builder_via_cli` once the flag is wired in `review_cmd.py`, extending the `TestRegroundApplyStructuralFlag` spy harness so the flag's `dest`-to-builder-kwarg threading is exercised through the real CLI path.

Green-before-done gate: every new test — including the `main([...])`-driven CLI-integration test — must pass, the existing `TestRegroundRemedyDispatch` tests must stay green unmodified (proving the mark-done default path is unchanged), and `tests/cli/test_cli_reference.py` must be green after regenerating the two docs.

## Acceptance criteria

- `_build_review_action_fn` accepts a default-off `reground_rebaseline` kwarg (or equivalent disposition selector); every existing caller that omits it keeps calling `reground_bridge` with the mark-done disposition.
- With the flag on, `_dispatch_reground_remedy` calls `reground_bridge` with step 5's re-baseline disposition and `repo_root=ctx.repo_root`; with it off, it passes the mark-done disposition.
- An applied re-baseline outcome names the written `seed_path` in the walk status line; an applied mark-done outcome does not.
- The applied re-baseline status line states the seed supersedes the source plan's remaining scope and directs the operator to re-create from it (`plan-tool create --from-existing <seed>`) and archive/retire the source plan, so two live plans never claim the same unbuilt work.
- `plan-tool reconcile-plan --help` and `plan-tool reconcile-plan-walk --help` both show a `--reground-rebaseline` flag whose help states it is a disposition selector and still needs the re-ground enabled and surfaced.
- `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` show the new row, and `tests/cli/test_cli_reference.py` passes.
- A `main([...])`-driven CLI-integration test (spying on `_build_review_action_fn`) proves `--reground-rebaseline`'s argparse `dest` threads to its builder kwarg through the real CLI path across the `cmd_review` / `cmd_review_walk` call sites — catching a wrong `dest` or a missed site the doc-drift guard cannot.
- The flag does not change whether a re-ground actuates: with `reground_rebaseline=True` and no enable opt-in, `allow_reground` passed to the bridge is `False`.
- The five new `tests/cli/test_review_actions.py` cases pass and the existing `TestRegroundRemedyDispatch` cases pass unchanged.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — reference for adding the `--reground-rebaseline` `store_true` flag to the two reconcile subparsers.
- [How to use temporary directories and files in tests (pytest)](https://docs.pytest.org/en/stable/how-to/tmp_path.html) — reference for the `tmp_path` fixture the builder-seam tests use to construct a `PlanToolContext` and stub `reground_bridge` hermetically.

## Deferred

- **Completeness-apply and reconcile lanes stay mark-done** — the completeness-apply builder in `plan_tool/cli/completeness_cmd.py` and the reconcile-lane / BLOCKED-STRUCTURAL builders in `plan_tool/cli/reconcile.py` never pass `reground_rebaseline`, so they keep the mark-done default; exposing the disposition there is out of scope for this walk-flag step.
- **Auto-selecting the re-baseline disposition** — this step keeps mark-done the default and makes re-baseline an explicit opt-in; letting convergence/reconcile signals choose re-baseline automatically is deferred (needs its own heuristic), per the plan's Deferred section.
- **A seed-only re-baseline (no mark-done)** — step 5's re-baseline arm writes the seed *and* marks done; a variant that only writes the seed without marking done is not built here.
- **Consolidating the three `create --from-existing` seed renderers** — `scope_out.render_carved_seed`, `annotate_render.render_create_seed`, and step 5's `render_rebaseline_seed` deliberately mirror rather than share; consolidation is a reconcile-owned refactor, not in scope for this step.
