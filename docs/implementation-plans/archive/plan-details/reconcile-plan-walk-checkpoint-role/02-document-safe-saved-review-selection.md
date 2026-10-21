> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Document safe saved review selection and close the risk

## Summary

Document the role-gated and contained `reconcile-plan-walk` selection behavior delivered by step 1. Update `docs/AUDIT_FLOW.md`, regenerate the CLI reference files under `docs/cli/`, and remove the resolved risk from `BUG_BACKLOG.md`. Keep the command kind-agnostic while requiring an ordinary-final saved role. On green, operator docs, generated help, and the backlog all agree that a checkpoint or unknown-role sidecar is never walked.

## Table of Contents

- [Summary](#summary) — The completed documentation outcome.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The stale operator guidance and open risk this step closes.
- [Input](#input) — The saved-review and step-1 contracts this documentation reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation files changed and their purpose.
- [Implementation](#implementation) — The selection contract and generated-reference workflow.
- [Tests](#tests) — Runtime evidence and generated-document drift coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and tracking outcomes.
- [References](#references) — Primary references for generated CLI help and verification.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this documentation-only step.
- [Deferred](#deferred) — Related code and policy work left outside this step.

## Why

`docs/AUDIT_FLOW.md` currently says that `reconcile-plan-walk` needs its own saved-review contract, `docs/cli/README.md` says it loads the most recent save, and `BUG_BACKLOG.md` still lists the resulting checkpoint risk. Step 1 closes the runtime gap, so these operator-facing surfaces must now describe the delivered role-based rule and remove the stale risk record. Without this update, users can still infer that a newer checkpoint is safe to walk.

## Input

- **Step 1 outcome:** Treat step 1’s role-gated direct-walk selection as the source for this documentation. Do not restate its implementation mechanism.

- **Persisted role:** Use `plan_tool/review_persistence.py:SavedReview.is_pre_apply_checkpoint` as the operator-facing contract: `False` is final, while `True` and `None` are not direct-walk candidates.

- **Selection boundary:** Document `plan_tool/cli/review_cmd.py:cmd_review_walk()` as the direct-walk policy owner. It accepts only listed candidates that resolve within the selected reports directory and contains a pin to one unique listed basename/stem; `plan_tool/review_persistence.py:resolve_saved_review()` remains a generic locator for recovery readers, not a direct-walk or role-filtering API.

- **Generated CLI reference:** Read `plan_tool/cli/review_cmd.py:register()` for the public `reconcile-plan-walk` help text. `plan_tool/cli_reference.py:render_reference()` owns the rendered files under `docs/cli/`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `BUG_BACKLOG.md` — Remove the resolved `reconcile-plan-walk` partial-checkpoint risk card.
  - `docs/AUDIT_FLOW.md` — Add direct-walk role selection to the persisted-role reader boundary and keep its source map accurate.
  - `docs/cli/README.md` — Regenerate the command index so its summary says the default selects the newest eligible final save.
  - `docs/cli/reconcile-plan-walk.md` — Regenerate the `--id` help text with the final-role and exact-selection contract.

## Implementation

- **Document the step-1 selection rule.** In `docs/AUDIT_FLOW.md`’s “Pre-apply checkpoint vs. final report — the persisted role” section, add `plan_tool/cli/review_cmd.py:cmd_review_walk()` as a reader with its own direct-walk contract.

- **Keep role separate from kind.** State that default direct selection scans newest-first until it finds a loadable sidecar whose `SavedReview.is_pre_apply_checkpoint` is `False`. A final artifact remains eligible regardless of its saved kind.

- **Describe exact pins and containment.** State that `--id` may match only one basename or stem already listed under the resolved plan's reports directory and whose resolved path remains there; path-bearing input, an ambiguous match, and a foreign-target symlink are refused rather than joined or followed. A missing id, malformed file, checkpoint, or unknown role has a state-specific selection refusal, exits `2`, and never chooses an older artifact.

- **Describe exhausted defaults.** State that default selection skips malformed, checkpoint, unknown-role, and foreign-target candidates, but if it finds no final artifact it reports no eligible saved review and exits `2` without starting a walk or mutating annotations.

- **Do not add freshness language.** `reconcile-plan-walk` replays saved findings; it does not perform reuse freshness checks or start a replacement audit.

- **Preserve generic checkpoint access.** Make clear that the direct-walk rule does not change `plan_tool/review_persistence.py:resolve_saved_review()` or checkpoint-reading consumers such as `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply()` and `plan_tool/cli/data_contract_cmd.py:cmd_data_contract_apply()`.

- **Regenerate, do not hand-edit, the CLI reference.** After step 1 updates `plan_tool/cli/review_cmd.py:register()`, run `python -m plan_tool.cli_reference --write` so `docs/cli/README.md` and `docs/cli/reconcile-plan-walk.md` match argparse output.

- **Close the tracked risk.** Remove the whole resolved card from `BUG_BACKLOG.md` only after the runtime coverage from step 1 and the documentation checks below are green.

## Tests

Step 1 owns the runtime regression cases; this non-code step adds no test files.

- `tests/test_review_walk.py::TestCliReviewWalkSubcommand` — Direct-walk selection cases remain the runtime evidence for the documented default and exact-id behavior.
- `tests/test_review_persistence.py::TestCheckpointRole` — The persisted final, checkpoint, and unknown-role meanings match the documentation.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` — Regenerated `docs/cli/` files match the live argparse parser.

### Verification (non-code step)

1. Run `python -m plan_tool.cli_reference --write`, then confirm `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` passes.
2. Confirm `docs/cli/README.md` and `docs/cli/reconcile-plan-walk.md` describe the newest eligible final default and exact `--id` behavior.
3. Confirm `docs/AUDIT_FLOW.md` distinguishes direct-walk listed-candidate role and resolved-directory filtering from kind-restricted reuse and generic checkpoint recovery, including the no-fallback exit-`2` behavior for exact, ambiguous, and exhausted selections.
4. Confirm the removed `BUG_BACKLOG.md` title has no remaining match.

## Acceptance criteria

- `docs/AUDIT_FLOW.md` identifies `plan_tool/cli/review_cmd.py:cmd_review_walk()` as a role-aware direct-walk reader.
- `docs/AUDIT_FLOW.md` states that only a loaded `SavedReview.is_pre_apply_checkpoint is False` artifact can enter a direct walk.
- `docs/AUDIT_FLOW.md` preserves kind-agnostic direct walking and says an explicit `--id` is limited to one listed basename/stem whose resolved path stays in the selected reports directory, reports its own refusal, and never falls back to another save.
- `docs/cli/README.md` and `docs/cli/reconcile-plan-walk.md` are regenerated from the current argparse help and no longer describe the default as simply the newest save; their help explains newest eligible-final default and contained exact selection.
- `tests/cli/test_cli_reference.py::TestCliReferenceDrift::test_every_generated_file_matches_disk` passes.
- `BUG_BACKLOG.md` has no `reconcile-plan-walk can walk a partial checkpoint` entry.
- The documentation does not claim that `plan_tool/review_persistence.py:resolve_saved_review()` rejects checkpoints or that direct walks run freshness checks.

## References

- [argparse — Python Standard Library](https://docs.python.org/3/library/argparse.html) — Read the parser help and subcommand behavior that generate the CLI reference.
- [pytest API reference](https://docs.pytest.org/en/stable/reference/reference.html) — Run and target the generated-reference drift check.

## Applicable guardrails

- **The plan’s “Plan intent,” direct-walk safety rule:** Document the final-role boundary without describing any path that can apply checkpoint findings.

- **The plan’s “Step intent,” operator and recovery-reader boundary:** Explain eligible saved reviews to operators while preserving the documented distinction between direct walking and generic checkpoint recovery.

- **The plan’s “Out of scope,” selection and persistence limits:** Keep this step to documentation, generated CLI reference output, and risk closure; do not expand it into schema, recovery, or command behavior work.

## Deferred

- **Checkpoint-role implementation changes** — Step 1 owns `plan_tool/cli/review_cmd.py:cmd_review_walk()` behavior; this step only documents its delivered contract.

- **Shared final-role predicate consolidation** — `plan_tool/completeness_report.py:is_reusable_audit_sidecar()` and `plan_tool/convergence_diagnosis.py:_is_final_report_role()` serve different readers; route any consolidation through reconcile planning.

- **Freshness, artifact cleanup, and new selection flags** — These are separate product decisions outside the plan’s documented scope.
