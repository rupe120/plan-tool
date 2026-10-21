> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Keep unsafe sidecars out of reconcile-plan reuse

## Summary

Update `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` so `reconcile-plan` reuses only an ordinary-final `kind="review"` sidecar. The selector must load candidates before trusting them, skip unsafe candidates during an unpinned scan, and decline an unsafe exact pin without falling back. Add focused reuse-selection coverage in `tests/cli/test_review_cmds.py`, update the parser help, regenerate `docs/cli/reconcile-plan.md`, and record the prompt-only closure without closing the generic-walk RISK. On green, a checkpoint, unknown role, non-review sidecar, or unreadable file cannot be automatically walked by `reconcile-plan`; a safe selected report on non-TTY stdin also skips the per-finding walk rather than blocking on input.

## Table of Contents

- [Summary](#summary) — Scope and completed behavior.
- [Table of Contents](#table-of-contents) — Section guide.
- [Why](#why) — The unsafe reuse path this step closes.
- [Input](#input) — Saved-review and caller contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files changed and their purpose.
- [Implementation](#implementation) — Payload-validated selection and reuse boundaries.
- [Tests](#tests) — Focused regression coverage and green gate.
- [Acceptance criteria](#acceptance-criteria) — Observable reuse and documentation results.
- [References](#references) — Persistence and test-matrix references.
- [Applicable guardrails](#applicable-guardrails) — Compatibility and reader-scope limits.
- [Deferred](#deferred) — Related readers left outside this step.

## Why

`plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` currently picks the newest filename-filtered candidate before it loads the sidecar, so a fresh pre-apply completeness checkpoint or an unknown-role payload can reach `plan_tool/cli/review_cmd.py:_cmd_review_body` and be walked as a plan-wide review. Steps 1 and 6 establish that only a loaded ordinary-final role is trustworthy; this reader must apply that rule before its existing fingerprint gate so partial findings never replace a fresh reconcile-plan audit.

## Input

- **Checkpoint-role contract from step 1:** `plan_tool/review_persistence.py:SavedReview.is_pre_apply_checkpoint` is `False` only for an ordinary final artifact; `True` is a checkpoint and `None` is untrusted metadata. Consume the normalized loaded value rather than parsing sidecar JSON here.

- **Persistence seams:** `plan_tool/review_persistence.py:list_saved_reviews` provides newest-first paths and `plan_tool/review_persistence.py:load_review` provides the payload and raises `ReviewLoadError` for unreadable candidates.

- **Reuse handoff:** `plan_tool/cli/review_cmd.py:_cmd_review_body` expects `_prompt_reuse_saved_review` to return one safe path or `None`, then retains ownership of loading, walking, and fresh-audit fallback.

- **Parallel reader precedent:** `plan_tool/completeness_report.py:resolve_reusable_audit` already scans loaded candidates and rejects unsafe roles. Match its scan-versus-exact-pin behavior, but do not import its completeness-only predicate because this command accepts only `kind="review"`.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/cli/review_cmd.py` — make `_prompt_reuse_saved_review` select only loaded, eligible review sidecars and revise `register` help for `--reuse` and `--reuse-id`.
  - `tests/cli/test_review_cmds.py` — extend `TestPromptReuseSavedReviewFlags` with safe-selection, exact-pin, freshness-order, and dispatch-mode cases.
  - `docs/cli/reconcile-plan.md` — regenerate the command reference from the changed argparse help.
  - `tests/cli/test_cli_reference.py` — retain `TestCliReferenceDrift.test_every_generated_file_matches_disk` as the generated-reference gate; no dedicated assertion is needed if its generic drift check remains sufficient.
  - `BUG_BACKLOG.md` — mark the prompt-reuse portion complete while retaining the direct generic saved-walk RISK and its separate-contract boundary.
  - `handoffs/2026-08-05-checkpoint-identity-session.md` — record the implementation, test, audit, and tracker outcome without declaring the generic reader gap closed.

## Implementation

- **Foundational logic: payload-validated saved-review selection.** Select a candidate only after `plan_tool/review_persistence.py:load_review` confirms `SavedReview.kind == "review"` and `SavedReview.is_pre_apply_checkpoint is False`. A checkpoint, an unknown role, and every non-review kind are ineligible even if their filename and fingerprints look valid.

- **Scan unpinned candidates in saved order.** In `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review`, preserve `list_saved_reviews` newest-first order. Load candidates one at a time; skip `ReviewLoadError`, non-review payloads, checkpoints, and unknown roles until the newest eligible review is found. Do not use the `"-reconcile"` filename exclusion as the safety decision.

- **Keep the exact-pin boundary.** When `--reuse-id` is set, narrow to its exact filename stem before eligibility checks. If that path is unloadable or ineligible, return `None`, print a reason distinct from the existing unmatched-stem message, and let `plan_tool/cli/review_cmd.py:_cmd_review_body` run a fresh audit. Do not substitute an older candidate.

- **Run freshness after eligibility, once.** Keep the current plan and code fingerprint work after an eligible candidate is selected. A stale newest eligible review must start a fresh audit and must not trigger another scan for an older fresh review.

- **Preserve existing opt-outs and safe dispatch.** Keep the early returns for `--dry-run`, `--no-walk`, `--no-save`, `--step`, and `--no-reuse`. A selected path must continue through the existing `--reuse`, `--yes`, and interactive handling into the existing walk in `_cmd_review_body`. On non-TTY stdin it must instead report the selected saved review and return success without calling `walk_recommendations` or `input()`, matching the fresh-review non-TTY behavior.

- **Update generated help at the parser source.** Adjust the `--reuse` and `--reuse-id` help in `plan_tool/cli/review_cmd.py:register` to describe ordinary-final review-only eligibility, skipped unsafe candidates, and exact-pin decline. Regenerate `docs/cli/reconcile-plan.md` through `plan_tool/cli_reference.py:write_reference`; do not hand-maintain the generated text.

- **Record the bounded closure.** After the focused code and documentation gate is green, update `BUG_BACKLOG.md` and the active handoff to state that prompt reuse is protected, while retaining the direct `reconcile-plan-walk` kind-agnostic reader as an open, separately designed follow-up.

## Tests

### Tests for this step

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_unpinned_reuse_skips_unsafe_candidates` — a newest-first set containing unreadable, checkpoint, unknown-role, and non-review sidecars skips to the newest eligible ordinary-final review.

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_reuse_id_declines_unsafe_or_unreadable_candidate` — parametrized exact pins report a specific ineligibility reason and never fall back to an older review.

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_reuse_stops_at_newest_eligible_stale_candidate` — a stale eligible review returns the fresh-audit path instead of widening the scan to an older candidate.

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_reuse_true_accepts_eligible_final_without_prompt` — an ordinary-final `kind="review"` sidecar remains reusable without prompting.

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_safe_reuse_dispatch_modes` — interactive acceptance, `--reuse`, and `--yes` walk the eligible sidecar; non-TTY reuse applies the same eligibility rule but returns without walking or prompting.

- `tests/cli/test_review_cmds.py:TestPromptReuseSavedReviewFlags.test_review_no_reuse_skips_lookup` — preserve the hard `--no-reuse` lookup opt-out.

- `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk` — the regenerated `docs/cli/reconcile-plan.md` matches live argparse output.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan_tool/cli/review_cmd.py:_prompt_reuse_saved_review` returns an unpinned path only for the newest loaded sidecar with `kind="review"` and `is_pre_apply_checkpoint is False`.

- An unpinned lookup skips unreadable, checkpoint, unknown-role, and non-review candidates without walking them.

- `--reuse-id` never falls back when the exact candidate is unreadable or ineligible, and its message differs from an unmatched stem.

- A stale newest eligible review starts a fresh audit without trying older eligible reviews.

- `--no-reuse` still avoids all saved-review lookup.

- Interactive reuse, `--reuse`, `--yes`, and non-TTY reuse share the same eligibility rule.

- A non-TTY selected reuse exits without invoking the per-finding walk or `input()`.

- `docs/cli/reconcile-plan.md` describes the new safe-selection rule and passes `tests/cli/test_cli_reference.py:TestCliReferenceDrift.test_every_generated_file_matches_disk`.

- `BUG_BACKLOG.md` and the active handoff record the prompt-only closure and keep the generic saved-walk RISK open.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Background for treating decoded persisted sidecars as untrusted until the persistence loader validates them.

- [How to parametrize fixtures and test functions — pytest documentation](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Use a concise matrix for unsafe-role and unreadable exact-pin cases.

## Applicable guardrails

- **Compatibility:** The plan’s `## Out of scope`, report naming and historical-sidecar boundary limits this step to reader selection. Do not rename, migrate, rewrite, or delete sidecars.

- **Recovery evidence:** The plan’s `## Out of scope`, crash-recovery boundary requires checkpoints to remain readable and on disk; exclude them only from automatic reconcile-plan reuse.

- **Reader scope:** The plan’s `## Architecture`, direct saved-walk boundary keeps `plan_tool/cli/review_cmd.py:cmd_review_walk` out of this change.

- **Data-contract apply:** The plan’s `## Out of scope`, saved-artifact locator boundary leaves `plan_tool/cli/data_contract_cmd.py:_newest_saved_completeness_with_contract_payload` unchanged.

## Deferred

- `plan_tool/cli/review_cmd.py:cmd_review_walk` direct saved-artifact selection — needs its own contract because it is kind-agnostic and has no fresh-audit fallback.

- `plan_tool/cli/reconcile.py:resolve_reusable_reconcile` and `plan_tool/cli/reconcile.py:_find_saved_for_step` — reconcile-family reuse has separate kind and step rules; assess its role handling in a separate reconcile task.

- `plan_tool/cli/completeness_cmd.py:cmd_completeness_apply` and `plan_tool/cli/data_contract_cmd.py:_newest_saved_completeness_with_contract_payload` — retain their existing recovery and freshness boundaries outside this reconcile-plan reader change.
