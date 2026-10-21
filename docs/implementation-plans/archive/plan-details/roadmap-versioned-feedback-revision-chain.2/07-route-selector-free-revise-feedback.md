> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 7 — Route selector-free feedback commands to the batch lifecycle

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/cli/roadmap_cmd.py` so selector-free `--revise-feedback` and `--propose-candidate` both start the accepted-head batch candidate lifecycle from step 3. Remove CLI routing, result rendering, and terminal-status handling that invoke the legacy live-artifact revision runner. Update `tests/cli/test_roadmap_cmd.py` to cover both command spellings, selector rejection, lifecycle exclusivity, and preservation of candidate lifecycle exit behavior. On green, ordinary feedback cannot reach a path that replaces live roadmap artifacts, baselines, or seed state.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the command-routing change.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why selector-based live-artifact routing no longer fits the lifecycle.
- [Input](#input) — Upstream batch, review, and promotion contracts the CLI consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped file edits.
- [Implementation](#implementation) — Selector-free parsing, lifecycle routing, and legacy-path retirement.
- [Tests](#tests) — Focused CLI coverage for the new command boundary.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Lifecycle contracts and command owners to consult.
- [Applicable guardrails](#applicable-guardrails) — Authority and scope limits for this routing step.
- [Deferred](#deferred) — Work outside the CLI routing footprint.

## Why

`plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_revise_feedback()` currently sends a selected row to `run_local_feedback_revision()`, whose result can report a published live-artifact replacement. `--propose-candidate` also requires a selector even though step 3 makes candidate admission derive one batch from the current accepted head. The CLI must expose the one immutable workflow consistently, so an operator cannot choose a live writer or narrow ordinary feedback to one row.

## Input

- **Step 3 batch proposal:** Use the selector-free `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()` entry point and its closed `CandidateProposalResult` outcomes. The accepted predecessor and batch membership remain runner-owned facts.

- **Step 5 review lifecycle:** Preserve `--review-candidate` and `--answer-question` as separate actions in `_cmd_roadmap_candidate_lifecycle()`. Candidate storage does not imply review or promotion.

- **Step 6 promotion boundary:** Keep `--promote-review-seal` as the only CLI action that reaches `plan_tool/roadmap_version_promotion.py:promote_review_seal()`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py` — Make both ordinary-feedback flags selector-free lifecycle actions, route them to the batch proposal handler, and remove local-revision CLI dependencies and output handling.
  - `tests/cli/test_roadmap_cmd.py` — Replace legacy local-revision routing assertions with selector-free batch-lifecycle, exclusivity, parsing, output, and exit-status coverage.

## Implementation

- **Use one batch-action route.** Treat `--revise-feedback` and `--propose-candidate` as two selector-free spellings for starting or re-entering the same batch proposal action. Route both through the candidate lifecycle path around `_has_candidate_lifecycle_action()`, `_candidate_lifecycle_has_conflict()`, and `_cmd_roadmap_candidate_lifecycle()`.

- **Reject row selectors at the parser boundary.** Update the command registration around `register()` so neither flag accepts an `ARTIFACT:FEEDBACK_ID` value. A trailing legacy selector must be a usage error rather than an ignored value or a request passed into the candidate runner.

- **Preserve one-action exclusivity.** Keep the occurrence tracking and conflict checks that require exactly one candidate lifecycle action. Supplying both ordinary-feedback spellings, or either spelling with review, answer, promotion, stage, seed, view, or confirmation inputs, must refuse before path resolution or backend work.

- **Call the runner without a selector.** Adapt `_cmd_roadmap_propose_candidate()` or a shared replacement so it calls the selector-free `run_initial_candidate_proposal()` with the slug, resolved repository paths, and optional invoker only. Reuse `_render_candidate_proposal_result()` and `_candidate_model_result_status()` so both spellings expose the same redacted candidate result and established exit mapping.

- **Retire the live-revision CLI path.** Remove imports and dispatch helpers tied only to `plan_tool/roadmap_revision_run.py`, including `LocalRevisionResult`, `run_local_feedback_revision()`, `_cmd_roadmap_revise_feedback()`, `_render_local_revision_result()`, and its separate terminal-disposition mapping. Do not replace them with another local artifact writer.

- **Keep the CLI thin.** Let step 3 own accepted-head lookup, batch derivation, admission reuse, storage, and model outcomes. The CLI must not rebuild feedback eligibility, inspect live roadmap artifacts, enroll a roadmap, advance `AcceptedRoadmapHead`, or add a second result mapping.

## Tests

### Tests for this step

- `test_revise_feedback_forwards_selector_free_batch_request` — `--revise-feedback` invokes `run_initial_candidate_proposal()` without a feedback selector and forwards the optional invoker and resolved paths.

- `test_propose_candidate_forwards_selector_free_batch_request` — `--propose-candidate` invokes the same batch proposal route with the same runner arguments and result rendering.

- `test_feedback_command_spellings_share_candidate_result_status` — Both spellings return the established statuses for `stored`, `response-rejected`, `failed`, `refused`, and `interrupted` outcomes.

- `test_selector_free_feedback_flags_reject_legacy_selector_values` — A trailing `ARTIFACT:FEEDBACK_ID` after either flag is rejected as command usage before runner invocation.

- `test_feedback_command_spellings_are_mutually_exclusive` — Supplying both spellings refuses before path resolution, backend invocation, or candidate storage.

- `test_feedback_command_spellings_reject_candidate_and_broad_companions` — Each spelling preserves the candidate lifecycle’s one-action rule for review, answer, promotion, and broad roadmap modes.

- `test_ordinary_feedback_never_dispatches_to_local_revision_runner` — Both selector-free commands leave `run_local_feedback_revision()` unreachable and render no legacy local-revision publication status.

Every listed test in `tests/cli/test_roadmap_cmd.py` must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --revise-feedback` starts the selector-free batch proposal lifecycle.

- `plan-tool roadmap <slug> --propose-candidate` starts the same selector-free batch proposal lifecycle.

- Neither ordinary-feedback flag accepts an `ARTIFACT:FEEDBACK_ID` argument.

- Both spellings use the same candidate result renderer and exit-status mapping.

- Both spellings refuse conflicting lifecycle and broad-mode inputs before side effects.

- `plan_tool/cli/roadmap_cmd.py` no longer routes ordinary feedback through `run_local_feedback_revision()` or renders `LocalRevisionResult`.

- `tests/cli/test_roadmap_cmd.py` passes with coverage for both spellings and the unreachable legacy route.

## References

- [ROADMAP_FORMAT.md — Read the accepted-head, feedback lifecycle, and candidate promotion contract.](../../../../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read the persisted candidate and legacy local-revision result contracts while removing the CLI dependency.](../../../../DATA_CONTRACT.md)

- [Roadmap candidate runner — Follow the batch proposal entry point and its closed outcomes.](../../../../plan_tool/roadmap_candidate_run.py)

- [Roadmap review module — Keep review and answer actions separate from candidate proposal.](../../../../plan_tool/roadmap_candidate_review.py)

- [Roadmap promotion module — Keep accepted-head movement limited to exact review-seal promotion.](../../../../plan_tool/roadmap_version_promotion.py)

## Applicable guardrails

- **Plan “## Plan intent”, ordinary feedback workflow:** Route both command spellings into the accepted-head batch lifecycle; this step must not create a second ordinary feedback path.

- **Plan “## Step intent”, live-artifact protection:** The CLI must leave no route from ordinary feedback to live roadmap, baseline, or seed replacement.

- **Plan “## Scope guardrails”, accepted-head authority:** Candidate proposal remains inert. This step must not enroll or promote a roadmap, or treat proposal output as canonical.

- **Plan “## Out of scope”, feedback lifecycle and review protocol:** Preserve existing reviewer actions and lifecycle meanings rather than adding a new feedback state, approval path, or selector-writing authority.

## Deferred

- Removal of `plan_tool/roadmap_revision_run.py` and its direct unit suite — This step retires ordinary CLI routing only; deleting or repurposing the legacy implementation is outside its declared files.

- Operator and reference-document updates for selector-free commands — Step 8 owns the documentation reconciliation.
