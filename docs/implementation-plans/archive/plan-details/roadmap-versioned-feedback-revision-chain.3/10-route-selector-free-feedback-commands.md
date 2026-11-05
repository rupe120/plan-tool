> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Route selector-free feedback commands to the ledger lifecycle, retire the live-artifact overwrite, and preserve unenrolled legacy writers behind their existing fence

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/cli/roadmap_cmd.py` to expose the landed ledger, batch-candidate, review, discard, and promotion lifecycle without accepting an embedded-artifact feedback selector for ordinary feedback work. Replace the CLI route that calls the local live-artifact revision runner with selector-free candidate creation and preserve the existing candidate result and exit behavior. Keep unenrolled roadmap writers behind their existing ownership fence rather than adding a CLI-side compatibility path. On green, the CLI gives operators one ledger-based feedback workflow while no ordinary feedback command can overwrite a live roadmap artifact.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome of the command-surface change.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — Why selector-bound live-artifact feedback routing must end.
- [Input](#input) — Lifecycle contracts supplied by prerequisite steps.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped production and CLI-test changes.
- [Implementation](#implementation) — Selector-free dispatch, lifecycle ownership, and compatibility boundaries.
- [Tests](#tests) — Focused command parsing, dispatch, and no-write coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary durable-publication references.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope limits for this CLI step.
- [Deferred](#deferred) — Work outside the command-routing footprint.

## Why

`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` currently dispatches `--revise-feedback` to `_cmd_roadmap_revise_feedback`, which invokes `run_local_feedback_revision` against one `ARTIFACT:FEEDBACK_ID` and can publish a live-artifact replacement. That conflicts with the ledger and root/active-candidate contracts supplied by steps 2 through 9: ordinary reviewer work now starts from eligible ledger items and creates an inert candidate from one exact batch. The CLI must stop offering the old overwrite path while preserving the existing unenrolled writer fence as the compatibility boundary.

## Input

- **Step 2 enrollment boundary:** Treat `plan_tool/roadmap_revision_publish.py:require_unenrolled_roadmap_writer` and its callers as the existing authority for legacy artifact-writing compatibility. This CLI step must not duplicate, bypass, or loosen that decision.

- **Step 5 candidate creation:** Consume the landed selector-free `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` entry point and its closed proposal outcomes. The runner owns accepted-root lookup, direct-source selection, batch construction, storage, and no-work behavior.

- **Step 6 ledger lifecycle:** Register and dispatch the landed migration and focused reviewer-mutation operations from `plan_tool/roadmap_feedback_ledger_run.py`. Step 6 owns their persisted shapes, validation, and mutation results; its landed public names and arguments win over this detail.

- **Steps 7–9 lifecycle actions:** Preserve the enrolled settlement path, active-candidate review actions, discard and rejection actions, and `plan_tool/roadmap_version_promotion.py:promote_review_seal` as separate lifecycle operations. Their runners remain the authorities for state transitions and accepted-head publication.

- **Step 7 settlement confirmation, two calls.** Wire settlement's `confirmation-required` outcome to print its confirmation-evidence receipt's exact final name, and add the separate response command from step 7's `respond_enrolled_decision_settlement`-style entry point. The CLI passes the exact final name and response value through; it does not construct, scan for, or infer a pending confirmation-evidence receipt itself.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Replace selector-bound ordinary feedback dispatch with the ledger lifecycle, register the landed focused commands, update exclusivity checks and help text, and remove live-revision CLI routing and rendering.
  - `tests/cli/test_roadmap_cmd.py` — Replace selector-bound local-revision coverage with parser, dispatch, exit-status, conflict, and end-to-end lifecycle coverage.

## Implementation

- **Make ordinary feedback selector-free.** Change the parser registration in `plan_tool/cli/roadmap_cmd.py:register` so the ordinary feedback command starts candidate processing without an `ARTIFACT:FEEDBACK_ID` argument. A trailing legacy selector must fail as command usage before any path lookup, writer guard, or backend request.

- **Use one proposal route.** Route the selector-free ordinary-feedback spelling and `--propose-candidate` through `_has_candidate_lifecycle_action`, `_candidate_lifecycle_has_conflict`, and `_cmd_roadmap_candidate_lifecycle`. Adapt `_cmd_roadmap_propose_candidate` to call the landed step 5 runner without a selector and retain `_render_candidate_proposal_result` plus `_candidate_model_result_status` as the one proposal-output and exit-status mapping.

- **Expose the landed ledger lifecycle without reimplementing it.** Add focused command registration and thin handlers for the step 6 migration and reviewer-edit operations. Forward only parsed arguments, resolved paths, and any existing CLI seams to the ledger runtime owner; do not parse ledger bytes, infer target fingerprints, or construct mutable records in the CLI.

- **Keep lifecycle actions exclusive.** Update `_option_occurrences`, `_has_candidate_lifecycle_action`, `_candidate_lifecycle_has_conflict`, `_selects_non_stage_roadmap_route`, and related conflict predicates together. Exactly one lifecycle action must be selected, and any lifecycle action combined with stage, seed, view, confirmation, comparison, structural, settlement, or another lifecycle input must fail before side effects.

- **Add the settlement-response command as its own lifecycle action.** Register `--respond-decision-settlement RECEIPT_FINAL` paired with an exclusive `--decision-settlement-yes`/`--decision-settlement-no` response value, subject to the same one-lifecycle-action exclusivity as every other action above; combining it with `--settle-decision`, another lifecycle action, or any stage/seed/view/comparison/structural input must fail before path resolution or a runner call. Print the confirmation-required result's confirmation-evidence receipt final name plainly enough for an operator or frontend to copy into this command; do not print mutable settlement, ledger, or candidate content.

- **Keep review, resolution, and promotion separate.** Route the landed step 8 review, answer, rejection, and discard actions to their dedicated runner entry points. Keep the existing promotion wrapper around `roadmap_writer_guard` and `promote_review_seal`; neither proposal nor ledger mutation may advance `AcceptedRoadmapHead`.

- **Retire the CLI live-artifact overwrite.** Remove the `plan_tool/roadmap_revision_run.py` imports, `_cmd_roadmap_revise_feedback`, `_render_local_revision_result`, and any local-revision-only terminal output from `plan_tool/cli/roadmap_cmd.py`. Do not replace them with another artifact-writing fallback.

- **Preserve unenrolled legacy writers by leaving their owner unchanged.** Do not add CLI enrollment detection or a second legacy dispatch path. Existing stage and legacy routes retain their current `plan_tool/roadmap_revision_publish.py:require_unenrolled_roadmap_writer` protection; ledger lifecycle runners report their own migration or enrollment refusal outcomes.

- **Keep result rendering redacted and thin.** Follow the existing `_render_candidate_proposal_result`, `_render_candidate_review_result`, `_render_candidate_answer_result`, and promotion output style. The CLI may report stable identities and closed outcomes, but must not print mutable ledger contents, model prompts, or immutable candidate bodies.

## Tests

### Tests for this step

- `test_selector_free_revise_feedback_dispatches_to_batch_proposal` — The ordinary feedback command invokes the landed proposal runner without an artifact selector and forwards resolved paths and the optional invoker.

- `test_selector_free_propose_candidate_dispatches_to_same_batch_proposal` — `--propose-candidate` takes the same selector-free route and renders the same proposal result.

- `test_ordinary_feedback_commands_reject_legacy_selector_values` — A trailing `ARTIFACT:FEEDBACK_ID` after either ordinary-feedback spelling is a usage error before runner invocation.

- `test_ordinary_feedback_commands_share_candidate_outcome_mapping` — Both proposal spellings preserve the established statuses for stored, refused, failed, rejected-response, and interrupted results.

- `test_ledger_migration_command_forwards_only_cli_arguments` — The migration command calls the landed step 6 runtime owner without parsing or rewriting ledger data in the CLI.

- `test_ledger_mutation_command_preserves_runtime_owned_validation` — A focused reviewer action forwards its exact requested operation and returns the runtime owner’s refusal or success result without a CLI-side substitute rule.

- `test_lifecycle_commands_are_one_action_only` — Every ledger, proposal, review, resolution, and promotion action rejects another lifecycle action before path resolution, backend work, or publication.

- `test_lifecycle_commands_reject_broad_mode_companions_before_side_effects` — Lifecycle commands reject stage, seed, view, confirmation, comparison, structural, and settlement companions before their runner is called.

- `test_review_rejection_and_discard_dispatch_to_active_candidate_lifecycle` — The landed step 8 public actions reach their dedicated runners and cannot release a candidate through proposal or promotion dispatch.

- `test_promotion_remains_the_only_cli_route_to_accepted_head_writer` — Proposal, ledger, review, rejection, and discard handlers never call `promote_review_seal`; only the promotion action enters its writer guard.

- `test_ordinary_feedback_never_dispatches_to_local_revision_runner` — Neither selector-free ordinary-feedback spelling imports, calls, or renders the former local live-artifact revision route.

- `test_unenrolled_stage_writer_fence_remains_cli_reachable` — A legacy stage route retains its current dispatch behavior and relies on the existing runtime ownership fence rather than the new ledger lifecycle.

- `test_selector_free_feedback_workflow_over_real_orchestrators` — A real CLI sequence with stubbed model calls covers ledger migration or readiness, candidate storage, review activity, and exact promotion without a live-artifact overwrite.

- `test_settlement_confirmation_prints_receipt_final_name_for_later_response` — A settlement that returns `confirmation-required` prints the confirmation-evidence receipt's exact final name and no mutable settlement or candidate content.

- `test_respond_decision_settlement_dispatches_by_exact_receipt_name` — `--respond-decision-settlement RECEIPT_FINAL` forwards the exact name and response value to step 7's response entry point without scanning for or inferring a pending confirmation-evidence receipt.

- `test_respond_decision_settlement_rejects_other_lifecycle_or_broad_mode_companions` — Combining the response command with `--settle-decision`, another lifecycle action, or a stage/seed/view/comparison/structural input fails before path resolution or a runner call.

Every listed test in `tests/cli/test_roadmap_cmd.py` must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --revise-feedback` starts the landed selector-free batch proposal lifecycle.

- `plan-tool roadmap <slug> --propose-candidate` starts the same selector-free batch proposal lifecycle.

- Neither ordinary-feedback command accepts an embedded-artifact feedback selector.

- The CLI exposes the landed step 6 ledger migration and focused reviewer-edit operations without implementing ledger validation or persistence itself.

- Each candidate lifecycle command accepts exactly one action and refuses all conflicting lifecycle and broad-mode inputs before side effects.

- Proposal, ledger mutation, review, rejection, and discard commands do not advance `AcceptedRoadmapHead`.

- A settlement returning `confirmation-required` prints its confirmation-evidence receipt's exact final name; `--respond-decision-settlement RECEIPT_FINAL` forwards that exact name and a yes/no value to step 7's response entry point and is subject to the same one-lifecycle-action exclusivity as every other lifecycle command.

- `plan_tool/cli/roadmap_cmd.py` no longer imports, dispatches to, or renders results from `plan_tool/roadmap_revision_run.py`.

- Existing unenrolled legacy stage writers retain their current runtime fence.

- `tests/cli/test_roadmap_cmd.py` passes.

## References

- [os.replace — Read the atomic replacement behavior used by the lifecycle owners that CLI handlers call.](https://docs.python.org/3.13/library/os.html#os.replace)

- [fcntl — Read the advisory-lock behavior behind the existing roadmap writer guard used by exact promotion.](https://docs.python.org/3.13/library/fcntl.html)

## Applicable guardrails

- **The plan’s “## Plan intent”, immutable artifact authority** — Route ordinary feedback through the ledger and candidate lifecycle; this step must not restore an artifact-writing feedback command.

- **The plan’s “## Scope guardrails”, accepted-head authority** — Keep proposal and ledger actions non-canonical. Only the existing enrolled writers may move the accepted head.

- **The plan’s “## Scope guardrails”, immutable batch evidence** — The CLI must forward lifecycle requests to their owners and must not select, replace, or recompute reviewer items, responses, target facts, derived context, or ledger bytes.

- **The plan’s “## Scope guardrails”, existing writer ownership** — Reuse the existing writer guard and lifecycle runners. This step must not create another transaction, candidate store, review store, or compatibility writer.

- **The plan’s “## Out of scope”, interface limits** — Expose only the focused ledger-file and lifecycle operations supplied by prior steps; do not add a general editing interface or new review protocol.

## Deferred

- Removal or repurposing of `plan_tool/roadmap_revision_run.py` and its direct unit coverage — This step removes ordinary CLI access while preserving the existing unenrolled compatibility fence.

- Operator documentation and reference updates for the final command syntax — Step 11 owns the documentation sweep.
