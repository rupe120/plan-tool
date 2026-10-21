> **Auto-archived**: this plan was swept on 2026-07-07 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Update merge bridge docs and --apply-structural help

## Summary

This step updates the user-facing docs and generated CLI reference only after the merge bridge and merge directive dispatch actually exist in code. The primary edits are `plan_tool/cli/review_cmd.py`, `CLAUDE.md`, `RUNBOOK.md`, `BACKLOG.md`, `docs/cli/reconcile-plan.md`, and `docs/cli/reconcile-plan-walk.md`. The key design decision is to make `plan_tool/cli/review_cmd.py`'s `--apply-structural` `help=` text the source for the generated `docs/cli/*` files, while keeping `CLAUDE.md`, `RUNBOOK.md`, and `BACKLOG.md` as hand-maintained prose. On green, no checked-in doc claims pairwise `granularity-merge` advice can dispatch through a merge bridge unless `plan_tool/detail.py:merge_bridge` exists and the review action dispatcher routes `MERGE_ACTION_MERGE` to it.

## Table of Contents

- [Summary](#summary) — The step at a glance.
- [Why](#why) — Why the docs must change after the bridge lands.
- [Files (creates vs edits)](#files-creates-vs-edits) — The exact file footprint for this docs step.
- [Implementation](#implementation) — The behavior to document and the update approach.
- [Tests](#tests) — The existing verification that covers generated CLI docs.
- [Acceptance criteria](#acceptance-criteria) — Concrete checks for done.
- [References](#references) — The small external reference set for the CLI help surface.
- [Deferred](#deferred) — Related doc work that stays out of this step.

## Why

Steps 4 and 5 are expected to make `granularity-merge` directives dispatch through structural bridges in the review walk, with stale saved directives blocked before mutation. This docs step must first verify that expectation against HEAD. If `plan_tool/detail.py:merge_bridge` is absent or the review action dispatcher still routes only `MERGE_ACTION_REGROUND`, pairwise merge advice remains documented as manual/deferred and `--apply-structural` must not be expanded to promise merge dispatch.

## Files (creates vs edits)

- **New files:** none.

- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py` — Update the `--apply-structural` `help=` strings in `register` for both `reconcile-plan` and `reconcile-plan-walk` only when HEAD has a real merge bridge and merge directive dispatch; otherwise leave the help scoped to the shipped re-ground bridge.
  - `docs/cli/reconcile-plan.md` — Regenerate from `plan_tool.cli_reference` after any `reconcile-plan` help text change.
  - `docs/cli/reconcile-plan-walk.md` — Regenerate from `plan_tool.cli_reference` after any `reconcile-plan-walk` help text change.
  - `CLAUDE.md` — Update the Architecture paragraphs for `Granularity advisor` and `Structural remedy vocabulary` only when pairwise merge is no longer hand-run-only or deferred in code.
  - `RUNBOOK.md` — Update the reconcile walk, per-subcommand reconcile, completeness granularity, convergence remedy model, and structural-remedy walkthrough prose only to match shipped behavior.
  - `BACKLOG.md` — Retire or rewrite the backlog entries that describe the merge bridge as remaining work only after this plan's bridge, dispatch, and stale-directive gate have shipped.

## Implementation

Foundational logic: **document only shipped structural-directive gates**.

- **Preflight the shipped surfaces first.** Before editing docs, grep HEAD for `plan_tool/detail.py:merge_bridge`, `plan_tool/reground.py:reground_bridge`, `plan_tool/review.py:MERGE_ACTION_MERGE`, `plan_tool/review.py:MERGE_ACTION_REGROUND`, and the review action dispatcher branch that calls the merge bridge for `MERGE_ACTION_MERGE`. If the merge bridge or merge dispatch branch is missing, stop this step as blocked and do not change docs to describe pairwise merge as apply-capable.

- **Update the actual CLI help only after merge dispatch exists.** In `plan_tool/cli/review_cmd.py:register`, revise both `--apply-structural` `help=` strings: the `p_review.add_argument("--apply-structural", ...)` branch for `reconcile-plan`, and the matching `p_review_walk.add_argument("--apply-structural", ...)` branch for `reconcile-plan-walk`. The help should say the flag lets recognized structural directive findings call their bridge on apply, currently pairwise `merge` directives through `plan_tool/detail.py:merge_bridge` and re-ground `reground` directives through `plan_tool/reground.py:reground_bridge`. If HEAD still only routes `MERGE_ACTION_REGROUND`, keep the help scoped to re-ground.

- **Keep the gate language precise.** The flag is not an unconditional auto-merge. The docs must preserve these constraints from steps 4 and 5: without `--apply-structural`, the walk recommends only; with the flag, the bridge still owns its own safety checks and TTY confirmation behavior; stale saved review fingerprints are blocked before any bridge call; and only an actual bridge mutation records the finding as applied. Do not imply `-y` or apply-all silently performs structural mutations.

- **Regenerate generated CLI docs.** `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` are generated from the live parser by `plan_tool/cli_reference.py:render_reference`. After the help text changes, run `python -m plan_tool.cli_reference --write` and commit the generated changes for only those files if they are the only outputs that changed. Do not hand-edit these two Markdown files.

- **Replace stale manual prose only after merge dispatch exists.** In `CLAUDE.md:Granularity advisor`, remove the claim that pairwise `granularity-merge` has no automatic bridge and must be resolved by hand-running `plan-tool merge` only after the code has the bridge and dispatch path. In `CLAUDE.md:Structural remedy vocabulary`, describe merge and re-ground as distinct directive remedies that the review/reconcile walk can route through `merge_bridge` and `reground_bridge` behind `--apply-structural` only when both routes are real shipped surfaces.

- **Update the RUNBOOK parallel sections to match shipped behavior.** In `RUNBOOK.md`, sweep the sections that explain review walking and structural remedies: the review walk apply-path list, the `reconcile-plan` code-grounded re-ground callout, the completeness-audit `granularity-merge` paragraph, and the structural-remedy model under the convergence workflow. The final wording should make the split clear only if both routes exist: pairwise merge advice dispatches to `plan_tool/detail.py:merge_bridge` when it carries a `merge` directive, while the code-grounded already-built finding dispatches to `plan_tool/reground.py:reground_bridge` when it carries a `reground` directive. If HEAD still lacks merge dispatch, keep pairwise merge documented as manual/deferred and keep re-ground documented as the only apply-capable structural directive.

- **Clean up backlog state only after merge dispatch exists.** In `BACKLOG.md`, update the entries anchored at `#94 — Merge bridge: a walk-surfaced pairwise-merge producer + the deferred merge actuation` and `#70 — Structural-remedy vocabulary: remaining convenience arms`. If the full merge bridge is shipped by steps 1-5, remove `#94` as completed and change `#70` so auto-bridges no longer list merge as deferred. Keep any still-real follow-up items, such as per-remedy flags or dispatcher consolidation. If HEAD still lacks the merge producer, bridge, dispatch, or stale guard, keep those items listed as remaining work.

## Tests

- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — asserts `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` match the live argparse help after regeneration.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_no_orphan_reference_files` — asserts the generated CLI reference set has no stale command files after regeneration.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_subcommand_has_a_reference_file` — asserts the regenerated reference still covers every primary subcommand.
- `tests/cli/test_review_actions.py` existing re-ground structural dispatch tests — sanity-check the currently shipped re-ground bridge routing, skipped non-mutating outcomes, and stale-fingerprint blocking; merge bridge dispatch coverage must come from the earlier merge-dispatch implementation step before these docs describe merge as apply-capable.

### Test-creation order (feature step)

No new test files are in scope for this docs/help step. First verify that the bridge and dispatch surfaces exist. If they do, make the `plan_tool/cli/review_cmd.py` help change, regenerate `docs/cli/*`, then run the existing CLI reference drift tests before considering the step finished. The green-before-done gate is that every existing test named above passes, any merge dispatch tests introduced by the merge-dispatch implementation step pass, and the manual grep checks in Acceptance criteria return the expected results.

## Acceptance criteria

- If `plan_tool/detail.py:merge_bridge` and merge directive dispatch exist, `plan-tool reconcile-plan --help` describes `--apply-structural` as covering both merge and re-ground structural directives, not only re-ground.
- If `plan_tool/detail.py:merge_bridge` and merge directive dispatch exist, `plan-tool reconcile-plan-walk --help` describes `--apply-structural` the same way as `reconcile-plan`.
- If `plan_tool/detail.py:merge_bridge` or merge directive dispatch is absent, `plan-tool reconcile-plan --help` and `plan-tool reconcile-plan-walk --help` do not claim pairwise merge directives are apply-capable.
- `docs/cli/reconcile-plan.md` and `docs/cli/reconcile-plan-walk.md` match `python -m plan_tool.cli_reference --write` output.
- `rg "no automatic bridge|hand-running `plan-tool merge`|bridge is deferred|still-hand-run merge|still-manual" CLAUDE.md RUNBOOK.md BACKLOG.md` returns no stale claim about the merge bridge only after the merge bridge and merge dispatch have shipped.
- `rg "merge_bridge|reground_bridge|--apply-structural|MERGE_ACTION_MERGE|MERGE_ACTION_REGROUND" plan_tool/cli/review_cmd.py CLAUDE.md RUNBOOK.md docs/cli/reconcile-plan.md docs/cli/reconcile-plan-walk.md` shows the docs cite only real shipped surfaces.
- `BACKLOG.md` no longer lists the merge producer, `merge_bridge`, merge directive dispatch, or stale merge-directive guard as remaining work only after those items have shipped.
- `uv run pytest tests/cli/test_cli_reference.py -q` passes.

## References

- [argparse — Parser for Command-Line Options](https://docs.python.org/3/library/argparse.html) — Read for how `help=` text is attached to parser actions and surfaced in generated help.
- [pytest Monkeypatch Guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Useful background for the existing dispatch tests that patch bridge functions on their owning modules.

## Deferred

- Per-remedy walk flags such as separate `--apply-merge` and `--apply-reground` — this step documents the shared `--apply-structural` flag only for structural remedies that exist in HEAD.
- Dispatcher refactors in `plan_tool/cli/review_actions.py` — this step documents the shipped behavior and does not consolidate structural dispatch closures.
- New generated-reference infrastructure — `plan_tool/cli_reference.py` and `tests/cli/test_cli_reference.py` already own the `docs/cli/*` drift guard.
