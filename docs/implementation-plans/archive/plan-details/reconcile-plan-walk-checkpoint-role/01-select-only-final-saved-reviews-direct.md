> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Select only final saved reviews for direct walks

## Summary

Make `reconcile-plan-walk` select only a saved sidecar whose loaded checkpoint role is an ordinary final artifact. Update `plan_tool/cli/review_cmd.py` to scan default candidates newest-first, while treating `--id` as a contained exact request. Keep direct walks kind-agnostic: role decides eligibility, not the sidecar kind or filename. On green, a checkpoint, unknown role, or unreadable newer sidecar can never reach `walk_recommendations`.

## Table of Contents

- [Summary](#summary) — The completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current unsafe direct-walk path.
- [Input](#input) — The saved-review role and locator contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed and their purpose.
- [Implementation](#implementation) — Selection rules, boundaries, and command behavior.
- [Tests](#tests) — Focused unit and CLI coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary documentation for the touched surfaces.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that bind this step.
- [Deferred](#deferred) — Related work intentionally left out.

## Why

`plan_tool/cli/review_cmd.py:cmd_review_walk()` currently asks `plan_tool/review_persistence.py:resolve_saved_review()` for the newest path and walks its loaded findings without checking `SavedReview.is_pre_apply_checkpoint`. That permits a pre-apply checkpoint, or a sidecar with unknown role metadata, to enter the interactive apply loop. Direct walking must trust the persisted final-role contract before it offers any finding for application.

## Input

- **Saved role:** Read `plan_tool/review_persistence.py:SavedReview.is_pre_apply_checkpoint` after `load_review()`. Only `False` is an eligible final artifact; `True` and `None` are not eligible.
- **Candidate order and containment:** Use `plan_tool/review_persistence.py:list_saved_reviews()` for the default newest-first scan, but trust a candidate only after it both resolves under the resolved `plan_reports_dir(plan_path)` and loads successfully. A symlink in the listed directory cannot redirect a direct walk to another plan.
- **Exact lookup:** Direct walking must not pass `--id` to `plan_tool/review_persistence.py:resolve_saved_review()`. It first lists the resolved plan's candidates, rejects a path-bearing value, and matches only one literal `Path.name` or `Path.stem` candidate. No match and more than one match are different terminal refusals; a unique match must still meet the resolved-directory boundary. Keep the generic resolver unchanged for recovery readers, including ones that intentionally locate a pinned checkpoint.
- **Kind handling:** Preserve `cmd_review_walk()`’s kind-agnostic behavior. Do not reuse `plan_tool/cli/review_cmd.py:_review_reuse_ineligibility()` as-is, because that helper also limits reuse to `kind="review"`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py` — Gate default and exact direct-walk selection on the loaded final role; align `reconcile-plan-walk` help text with the eligible-save contract.
  - `tests/cli/test_review_cmds.py` — Add focused command-selection coverage for role-only eligibility without changing plan-wide review-reuse policy.
  - `tests/test_review_walk.py` — Extend `TestCliReviewWalkSubcommand` with end-to-end direct-walk selection and rejection cases.
  - `tests/test_review_persistence.py` — Keep the generic locator boundary explicit: persistence still resolves paths without applying direct-walk eligibility rules.

## Implementation

- **Own direct selection in the command layer.** In `plan_tool/cli/review_cmd.py:cmd_review_walk()` (or a small command-local helper), get candidates exclusively from `list_saved_reviews(args.name, ctx.repo_root, plan_path=plan_path)`. Resolve the selected plan's `plan_reports_dir(plan_path)` once and accept a candidate only when its resolved path stays beneath that resolved directory; safely treat a resolution failure or foreign-target symlink as ineligible. Apply this boundary to both default scans and exact pins. Do not call `resolve_saved_review()` for either direct-walk form; do not change that generic resolver or make recovery readers inherit this policy.

- **Contain and resolve an exact pin from the listing.** For `--id`, first reject an empty or path-bearing id (including `/`, `\\`, `.`/`..`, or any non-basename `Path` form) with exit `2`. Otherwise, collect every listed candidate whose literal `name` or `stem` matches; never construct a path from untrusted input. Zero matches reports a missing pin, while more than one reports an ambiguous pin—both are terminal exit-`2` refusals. Only a unique match can continue to the resolved-directory and payload checks. In every rejected-pin case, return before walk setup and never widen to the next candidate.

- **Select by loaded final role.** In the default path, inspect candidates in `list_saved_reviews()` newest-first order until one passes resolved-directory containment, loads, and has `is_pre_apply_checkpoint is False`. A saved-sidecar loading/parsing failure—including the content-shape exceptions currently able to escape `load_review()`—is treated as unreadable for direct selection and is skipped. A foreign-target symlink, confirmed-checkpoint, and unknown-role payload are likewise skipped. If every candidate is skipped, report that no eligible saved review is available and return `2` before `_build_review_action_fn()` or `walk_recommendations()` can run.

- **Make every exact-pin refusal terminal and specific.** Load only the uniquely matched, resolved-directory-contained listed candidate. A missing, ambiguous, foreign-target, load/parsing failure, checkpoint-role, or unknown-role pin has its own operator-facing refusal and returns `2`; an explicit final remains eligible. Do not preserve the current `ReviewLoadError` exit-`1` path for an operator-selected direct-walk sidecar: malformed pins belong to the same exit-`2` selection-refusal contract as missing and path-bearing pins.

- **Accept every final kind.** A final completeness, detail-reconcile, run-reconcile, or ordinary review sidecar remains walkable if its loaded role is `False`. Do not add a kind filter, filename convention, freshness check, or re-audit fallback.

- **Keep the persistence contract unchanged.** Do not alter `plan_tool/review_persistence.py:_normalize_checkpoint_role()`, `SavedReview`, `save_review()`, `load_review()`, or `resolve_saved_review()`. Legacy unmarked final sidecars and explicit version-3 `false` markers are already normalized to `False` and must remain accepted.

- **Keep related role checks separate.** `plan_tool/completeness_report.py:is_reusable_audit_sidecar()` and `plan_tool/convergence_diagnosis.py:_is_final_report_role()` use the same persisted role for different consumers. This step should not consolidate them with direct-walk selection.

## Tests

### Tests for this step

- `tests/cli/test_review_cmds.py::TestDirectWalkSavedReviewSelection::test_default_selection_skips_unreadable_and_nonfinal_candidates` — A newest-first scan skips malformed, checkpoint, and unknown-role sidecars before selecting the next final sidecar.
- `tests/cli/test_review_cmds.py::TestDirectWalkSavedReviewSelection::test_default_selection_reports_no_eligible_candidate_without_mutation` — An exhausted list of malformed, checkpoint, unknown-role, and foreign-target-symlink sidecars reports no eligible final, returns `2`, and neither starts a walk nor annotates any save.
- `tests/cli/test_review_cmds.py::TestDirectWalkSavedReviewSelection::test_explicit_id_rejects_each_ineligible_state_without_fallback` — Missing, ambiguous, malformed, checkpoint, unknown-role, foreign-target-symlink, and path-bearing pins each produce their own exit-`2` refusal and never choose an older final artifact. The path-bearing and symlink cases name a final report belonging to another plan to prove containment.
- `tests/cli/test_review_cmds.py::TestDirectWalkSavedReviewSelection::test_final_non_review_kind_is_eligible_for_direct_walk` — A final sidecar of a non-`review` kind remains eligible.
- `tests/test_review_walk.py::TestCliReviewWalkSubcommand::test_loads_newest_eligible_final_saved_review` — The command passes the selected final artifact, not a newer checkpoint or unknown-role artifact, to `walk_recommendations`.
- `tests/test_review_walk.py::TestCliReviewWalkSubcommand::test_rejected_direct_selection_returns_2_without_starting_walk` — Every exact refusal and an exhausted default scan leave the walk callback and saved annotations untouched.
- `tests/test_review_persistence.py::TestResolveSavedReview::test_picks_newest_by_default` — The generic persistence resolver remains role-agnostic, proving direct-walk filtering stays in the command layer.
- `tests/test_review_persistence.py::TestResolveSavedReview` existing exact-id coverage — The generic resolver may still locate a checkpoint for a recovery caller; direct containment is deliberately not imposed on this shared API in this step.
- `tests/test_review_persistence.py::TestCheckpointRole` role-matrix cases — Legacy finals and explicit `false` remain final; checkpoints and malformed role metadata remain distinct.

Every listed test must be green before this step is complete.

## Acceptance criteria

- Default `reconcile-plan-walk <name>` selects the newest loadable sidecar with `SavedReview.is_pre_apply_checkpoint is False`.
- Default selection skips unreadable files, `True` checkpoint roles, and `None` unknown roles without applying their findings.
- `reconcile-plan-walk <name> --id <stem-or-basename>` accepts only one uniquely matched listed final sidecar whose resolved path remains in the resolved plan's reports directory; an ineligible, missing, ambiguous, foreign-target, unreadable, or path-bearing id returns its own exit-`2` selection refusal and does not fall back.
- An unpinned scan that exhausts malformed, checkpoint, unknown-role, or foreign-target candidates reports no eligible saved review and returns `2` without annotation or plan mutation.
- A rejected sidecar never reaches `_build_review_action_fn()` or `walk_recommendations()`.
- Final sidecars remain eligible regardless of `SavedReview.kind`.
- `resolve_saved_review()` remains a generic path resolver and can still locate a pinned checkpoint for consumers that own checkpoint handling.
- The listed tests pass.

## References

- [argparse — Python Standard Library](https://docs.python.org/3/library/argparse.html) — Review command argument and exit behavior around the exact `--id` path.
- [pathlib — Python Standard Library](https://docs.python.org/3/library/pathlib.html) — Read saved sidecars and maintain newest-first path selection.
- [json — Python Standard Library](https://docs.python.org/3/library/json.html) — Handle malformed saved JSON through the existing load-error path.
- [pytest monkeypatch guide](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Isolate the walk callback and saved-review lookup in regression tests.
- [pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html) — Build isolated sidecar sets with `tmp_path`.

## Applicable guardrails

- **The plan’s “Plan intent” direct-walk safety rule:** Limit this step to selecting final artifacts before the direct walk begins.
- **The plan’s “Step intent” role boundary:** Treat checkpoint and unknown roles as ineligible without changing how they are written, normalized, or loaded.
- **The plan’s “Out of scope” selection limits:** Do not add freshness checks, new flags, fallback audits, kind restrictions, migrations, or changes to other checkpoint consumers.

## Deferred

- **Shared final-role predicate consolidation** — `plan_tool/completeness_report.py:is_reusable_audit_sidecar()` and `plan_tool/convergence_diagnosis.py:_is_final_report_role()` serve different consumer contracts; route any cross-module consolidation through reconcile work.
- **Checkpoint persistence and recovery behavior** — `plan_tool/review_persistence.py` remains unchanged so pinned checkpoint consumers keep their existing load behavior.
- **Freshness and replacement audits** — Direct walks continue to replay saved findings only; deciding whether they are current belongs outside this step.
