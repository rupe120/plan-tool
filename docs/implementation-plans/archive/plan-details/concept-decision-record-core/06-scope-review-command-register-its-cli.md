> **Auto-archived**: this plan was swept on 2026-07-16 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add the scope-review command and register its CLI surface

## Summary

This step adds `plan-tool scope-review` as the CLI orchestration layer over the concept bootstrap, scoped review, and synchronization contracts delivered by steps 3–5. The new `plan_tool/cli/scope_review_cmd.py` resolves the plan, validates or bootstraps its concept record, applies review only to the requested scope, and delegates plan/record propagation to the canonical synchronizer. It also registers the command in `plan_tool/cli/app.py`, `plan_tool/cli/parser.py`, and `plan_tool/cli/__init__.py`, then updates the capability catalog, generated CLI reference, and help golden. On green, successful reviews persist matching concept and Markdown state, while conflicts and invalid records produce distinct, documented nonzero outcomes without overwriting either side.

## Table of Contents

- [Summary](#summary) — Overview of the command, registration work, and successful result.
- [Why](#why) — Why the domain contracts need one public orchestration surface.
- [Input](#input) — Contracts supplied by steps 3–5 and the limits on this step.
- [Files (creates vs edits)](#files-creates-vs-edits) — New and changed files in the CLI surface.
- [Implementation](#implementation) — Required command flow, registration points, and failure rules.
- [Tests](#tests) — Command, dispatch, locking, help, and documentation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable behavior required before completion.
- [References](#references) — Authoritative argparse documentation.
- [Deferred](#deferred) — Related work intentionally left outside this step.

## Why

Steps 3–5 provide reusable bootstrap, review, and synchronization behavior, but users and automation still need one command that applies those contracts in the right order. Without that layer, callers could select scope differently, bypass conflict checks, write only one artifact, or collapse invalid state and a merge conflict into the same failure. `scope-review` makes the safe path public: resolve one plan, validate or bootstrap its concept record, review an explicit scope, synchronize through one authority, and report an outcome that scripts can distinguish.

## Input

- **Step 3 bootstrap contract:** Consume the deterministic initial-derivation and conflict-aware re-derivation results from `plan_tool/concept_bootstrap.py`. Treat its conflict result as data to report, not permission to choose a winner or overwrite reviewed state.
- **Step 4 review contract:** Consume the public scoped-review operation and its three-state decision vocabulary from `plan_tool/concept_review.py`. Pass the operator’s requested scope unchanged and rely on that module to reject incomplete or stale sign-off.
- **Step 5 synchronization contract:** Route accepted changes through the canonical synchronization operation in `plan_tool/concept_sync.py`. Do not reproduce its Markdown parsing, unrelated-content preservation, or divergence checks in the CLI.
- **Step 1 persisted record contract:** Use the public load/save and integrity errors delivered in `plan_tool/concept_tree.py`. Absence may enter the step 3 bootstrap path; malformed, integrity-failing, or fingerprint-mismatched state must remain distinguishable from absence.
- **CLI context contract:** Follow `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` for `_load_context`, `resolve_plan_for_context`, and an `args`-only handler, while preserving the different semantics: `scope-review` reviews concepts and is mutating, whereas `scope-out` carves plan steps.
- **Verification limit:** Steps 3–5 are dependencies and may not exist when this detail is drafted. Use their landed public result types and exception names rather than introducing parallel CLI-only models or guessing around a changed upstream API.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/cli/scope_review_cmd.py` — define the command handler, outcome rendering, exit mapping, and `register(subparsers)` entry.
  - `tests/cli/test_scope_review_cmd.py` — cover orchestration, scoped mutation, persistence, and failure outcomes.
  - `docs/cli/scope-review.md` — generated per-command reference from the live argparse parser.

- **Existing files (edits only):**
  - `plan_tool/cli/app.py` — import the command module and handler, add the module to `COMMAND_MODULES`, and add `scope-review` to `_LOCKED_MUTATING_COMMANDS`.
  - `plan_tool/cli/parser.py` — add `scope-review` to `CANONICAL_COMMAND_ORDER` at the intended public help position.
  - `plan_tool/cli/__init__.py` — add the command to the intent-grouped package catalog and expose `cmd_scope_review` through `__all__`.
  - `CAPABILITIES.md` — assign `scope-review` to an owning capability with real command/module surfaces and valid `MISSION.md` principle identifiers.
  - `docs/cli/README.md` — regenerate the command index from the live parser.
  - `tests/cli/package_surface_help.golden.txt` — rebaseline top-level help after the intentional command addition.
  - `tests/cli/test_app_lock.py` — assert that `scope-review` always requires the repository mutation lock.
  - `tests/cli/test_package_surface.py` — include `cmd_scope_review` in the stable package surface and keep parser/dispatcher checks explicit where needed.
  - `tests/cli/test_cli_reference.py` — retain the generated-reference drift contract and add a command-specific assertion only if the existing generic checks cannot clearly diagnose a missing `scope-review` reference.

## Implementation

The foundational logic is **map one validated, scoped concept-review transaction to success, conflict, or invalid-state CLI outcomes without bypassing the canonical domain operations**.

- **Keep the command module thin.** Model `plan_tool/cli/scope_review_cmd.py` on the registration shape of `plan_tool/cli/scope_out_cmd.py:cmd_scope_out` and `register`, but import only `plan_tool/cli/context.py:_load_context`, `plan_tool/cli/parser.py:Handler`, locator helpers, style helpers, and the step 1/3/4/5 domain modules. Never import `plan_tool/cli/app.py` from the command module.

- **Expose an explicit scope.** The parser must accept a plan name plus the scope selector required by the landed `plan_tool/concept_review.py` public API. Use that module’s own identifier vocabulary and validation rather than translating scope into titles, list positions, or a second CLI-only representation. If the review API supports more than one concept in a scope, preserve that grouping in one review operation so sign-off cannot accidentally cover a broader set.

- **Resolve the plan through the shared context.** In `plan_tool/cli/scope_review_cmd.py:cmd_scope_review`, load context with `_load_context(args)` and resolve the plan through `plan_tool/locator.py:resolve_plan_for_context`. Do not accept a raw sidecar path as a substitute for the plan, because bootstrap, fingerprint checks, and synchronization are plan-relative.

- **Distinguish absence from invalid state.** A missing concept record should invoke the deterministic bootstrap supplied by step 3. A present record that fails the step 1 integrity or current-plan checks must stop before review or synchronization and return the invalid-state outcome. Do not catch every domain error and treat it as “no record.”

- **Run conflict checks before writes.** Feed existing state through step 3’s re-derivation contract when the source requires it, then through step 4’s scoped review contract and step 5’s synchronizer. A bootstrap, review, or synchronization conflict must leave the existing concept record and plan Markdown unchanged. The CLI may format the conflict, but it must not resolve it, retry with relaxed checks, or pick either side.

- **Use one synchronization authority.** After a valid scoped review, call the step 5 operation responsible for keeping the concept record and plan body consistent. Do not edit Markdown directly in `plan_tool/cli/scope_review_cmd.py`; direct CLI edits would create a second implementation of the same propagation rule and could drop unrelated Markdown.

- **Persist only a complete successful result.** Save the updated concept record using the step 1 writer and publish the synchronized plan result using the step 5 contract in the order required by those landed APIs. Perform all validation and conflict detection before the first write. This step does not promise a cross-file transaction, but a normal success must never intentionally leave the record and Markdown describing different accepted decisions.

- **Define stable exit meanings.** Return `0` only after a successful scoped review and consistent persistence. Assign separate named nonzero outcomes for domain conflict and invalid persisted/current state, document them in argparse help, and pin their numeric values in `tests/cli/test_scope_review_cmd.py`. Preserve argparse’s own usage-error behavior for missing or malformed arguments rather than mapping usage failures to a domain outcome.

- **Render actionable failures.** Conflict output should identify the affected concept or scope using the upstream result’s stable identifiers and say that no changes were written. Invalid-state output should identify the failed integrity or freshness condition and provide the supported recovery action. Do not print a success message before both artifacts have been published.

- **Register every enforced surface.** In `plan_tool/cli/app.py`, follow the existing two-part import pattern: import `plan_tool/cli/scope_review_cmd.py` as a command module, import `cmd_scope_review` for re-export, append the module to `COMMAND_MODULES`, and add the command literal to `_LOCKED_MUTATING_COMMANDS`. The lock is unconditional because every successful invocation may write the concept record and plan Markdown; unlike `scope-out`, there is no recommend-only carve path described by this plan.

- **Keep help order independent from registry order.** Add `scope-review` to `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`. Place it beside the related concept/structural authoring surfaces rather than relying on unknown-command sorting, then regenerate `tests/cli/package_surface_help.golden.txt`.

- **Preserve the package import contract.** Add `cmd_scope_review` to `plan_tool/cli/__init__.py:__all__` and describe `scope-review` in the package docstring’s intent-grouped command catalog. `tests/cli/test_package_surface.py:TestParserDispatcherCorrespondence` must see one registered parser command, one callable handler, and no orphan `cmd_*` symbol.

- **Give the command an owning capability.** Update `CAPABILITIES.md` so the capability honesty check finds `scope-review` in a `surfaces:` entry. Prefer a concept-decision capability that also names the real domain modules delivered by steps 1 and 3–5; use only principle IDs declared under `MISSION.md:Grounding principles`.

- **Generate, do not hand-author, the CLI reference.** After parser help is final, run `python -m plan_tool.cli_reference --write`. This creates `docs/cli/scope-review.md` and updates `docs/cli/README.md`; `plan_tool/cli_reference.py:render_reference` and `write_reference` remain the single source for both files.

- **Keep `scope-review` distinct from `scope-out`.** Parser summaries and generated docs must state that `scope-review` reviews and synchronizes concept decisions, while `scope-out` carves a step into a forward seed. Similar command names must not produce interchangeable help text.

## Tests

- `test_scope_review_is_registered` — `plan_tool/cli/__init__.py:build_parser` exposes `scope-review` and dispatches it to `cmd_scope_review`.
- `test_scope_review_bootstraps_missing_record` — an absent record uses step 3 bootstrap and reaches scoped review rather than being treated as invalid.
- `test_scope_review_limits_changes_to_requested_scope` — concepts outside the selected scope keep their decision and review state.
- `test_scope_review_persists_record_and_markdown_on_success` — a successful operation leaves the concept record and synchronized plan body describing the same accepted decisions.
- `test_scope_review_preserves_unrelated_markdown` — synchronization does not rewrite plan content outside the concept-backed sections.
- `test_scope_review_conflict_returns_distinct_exit_and_writes_nothing` — a re-derivation or synchronization conflict returns the pinned conflict code and preserves both files.
- `test_scope_review_invalid_record_returns_distinct_exit_and_writes_nothing` — malformed or integrity-failing persisted state returns the pinned invalid-state code without bootstrapping over it.
- `test_scope_review_stale_scope_cannot_sign_off` — a scope whose source state is no longer current fails through the step 4 contract and does not persist sign-off.
- `test_scope_review_reports_all_conflicts` — output retains every conflict supplied by the domain result rather than stopping at the first.
- `test_scope_review_success_message_follows_persistence` — a write failure cannot produce a success message or exit `0`.
- `test_scope_review_help_distinguishes_scope_out` — command summaries make review/sign-off and structural carve behavior visibly different.
- `test_scope_review_requires_repo_lock` — `tests/cli/test_app_lock.py` proves `_requires_repo_mutation_lock` is true without flag-dependent exceptions.
- `test_scope_review_handler_is_on_package_surface` — `tests/cli/test_package_surface.py` proves `cmd_scope_review` is importable from `plan_tool.cli`.
- `test_package_help_matches_scope_review_golden` — the top-level help snapshot contains the command in canonical order.
- `test_scope_review_reference_is_generated` — `tests/cli/test_cli_reference.py` confirms `docs/cli/scope-review.md` and `docs/cli/README.md` match the live parser.
- `test_scope_review_has_owning_capability` — the existing capability honesty suite reports no `orphan-subcommand` finding for `scope-review`.

### Test-creation order (feature step)

Add parser/dispatch and lock tests with the initial `register` implementation. Add missing-record, scoped-success, and synchronized-persistence tests with the handler’s successful path. Add conflict, invalid-state, stale-scope, write-failure, and no-mutation tests as each outcome branch is introduced. Finish by regenerating the help golden and CLI reference and running their drift tests. Every new test in `tests/cli/test_scope_review_cmd.py` and every affected package-surface, lock, capability, and CLI-reference test must be green before this step is considered finished.

## Acceptance criteria

- `plan-tool --help` lists `scope-review` in `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`, and `plan-tool scope-review --help` clearly describes concept review rather than step carving.
- `plan_tool/cli/app.py:COMMAND_MODULES` registers `plan_tool/cli/scope_review_cmd.py`, and the assembled dispatch maps `scope-review` to `cmd_scope_review`.
- `from plan_tool.cli import cmd_scope_review` succeeds, and `cmd_scope_review` appears in `plan_tool/cli/__init__.py:__all__`.
- `_requires_repo_mutation_lock` returns true for `Namespace(command="scope-review")` without requiring another flag.
- A missing concept record enters the step 3 bootstrap path; a malformed, stale, or integrity-failing record does not.
- A successful invocation changes only the requested concept scope and leaves the persisted concept record and synchronized Markdown consistent.
- A conflict returns its documented nonzero exit code and writes neither the proposed record nor the proposed Markdown.
- Invalid persisted or current state returns a different documented nonzero exit code and writes nothing.
- `CAPABILITIES.md` assigns `scope-review` to an owning capability using valid `MISSION.md` principle identifiers.
- `docs/cli/scope-review.md` and `docs/cli/README.md` match `plan_tool/cli_reference.py:render_reference`.
- `tests/cli/package_surface_help.golden.txt` matches the live top-level parser help.
- `tests/cli/test_scope_review_cmd.py`, `tests/cli/test_app_lock.py`, `tests/cli/test_package_surface.py`, and `tests/cli/test_cli_reference.py` pass.

## References

- [Python argparse — Parser for Command-Line Options](https://docs.python.org/3/library/argparse.html) — Use the subparser, argument validation, help, and usage-error conventions when defining `scope-review`.

## Deferred

- Automated conflict resolution — the command reports bootstrap and synchronization conflicts but does not choose a winning side.
- Cross-file transactional recovery — this step validates before writing and uses the existing atomic writers, but coordinated crash recovery across the concept record and Markdown remains a separate durability feature.
- General-purpose plan editing — synchronization remains limited to the concept-backed sections owned by step 5.
- Collaborative or remote review — this command operates on the local persisted plan and concept record only.
- Shared extraction of command registration boilerplate — `plan_tool/cli/app.py:COMMAND_MODULES`, `plan_tool/cli/parser.py:CANONICAL_COMMAND_ORDER`, and package re-exports remain separate framework contracts.
