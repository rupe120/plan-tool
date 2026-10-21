> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Resolve a bounded operator declaration and safe create recovery boundary

## Summary

Resolve step 2’s private risk proposal into a final, operator-owned declaration before the first plan write, then distinguish before-first-write failure, retained pre-manifest recovery, registered-finalization error, and the existing iteration-incomplete completion result. Update `docs/how-to/pipeline/create-from-existing.md` and `docs/how-to/recovery/create.md` to describe the decision modes, checkpoint lifecycle, and created-artifact recovery boundary, with focused coverage in `tests/test_create.py`. The final choice must stay within step 2’s risk floor, and every new plan must carry a tier and rationale that agree. On green, interactive choices, silent standard fallbacks, resume behavior, run-log records, and created-artifact failures all have one unambiguous outcome.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and key decision.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the proposal needs a bounded pre-write decision.
- [Input](#input) — Upstream declaration and proposal contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files this step changes.
- [Implementation](#implementation) — Required decision, persistence, checkpoint, and log behavior.
- [Tests](#tests) — Focused regression coverage and green gate.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for terminal and JSON behavior.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Work owned by later steps or follow-ups.

## Why

`plan_tool/create.py:_prepare_create_plan` builds an in-memory `Plan`, and `plan_tool/create.py:create_plan` passes it to `plan_tool/create.py:_publish_create_plan` for `plan_tool/create.py:write_new_plan`; without a final decision gate, step 2’s bounded proposal cannot become a reviewable frontmatter declaration before publication. The decision must be durable across safe pre-write retries but must never let a model or stale checkpoint choose a lower tier than the evidence permits.

## Input

- **Step 1 declaration contract:** Step 1 creates the closed risk-tier vocabulary and the paired frontmatter fields. New plans must set the pair together, and the rationale must describe the saved tier.
- **Step 2 proposal contract:** Step 2 supplies one private pre-publication proposal with a proposed tier, rationale, and minimum permitted tier. Use the landed shape rather than duplicating its classification policy.
- **Publication boundary:** `plan_tool/create.py:_prepare_create_plan`, `plan_tool/create.py:PreparedCreatePlan`, `plan_tool/create.py:create_plan`, and `plan_tool/create.py:_publish_create_plan` establish the in-memory-before-write ordering this step must preserve.
- **Existing decision patterns:** `plan_tool/create.py:_review_step_change_types` and `plan_tool/create.py:_offer_missing_intents` show the existing TTY, `--yes`, checkpoint, and `RunLoggerLike` seams. Keep `plan_tool/create.py:create_plan`’s public signature unchanged.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/create.py` — Resolve the bounded proposal before publication, attach the final declaration to the in-memory plan, persist and replay the operator decision safely, report retained post-write artifacts, and emit its run-log record.
  - `plan_tool/cli/authoring.py` — Preserve a branch-aware create binding when a reported error retains an artifact, and roll it back only when no artifact exists.
  - `docs/how-to/pipeline/create-from-existing.md` — Document the single-plan risk-declaration decision and retained-artifact recovery boundary, including interactive, silent, no-source, and split behavior.
  - `docs/how-to/recovery/create.md` — Document the risk-decision checkpoint’s matching, retention, successful-cleanup, and created-artifact handoff rules.
  - `tests/test_create.py` — Cover decision modes, policy bounds, checkpoint behavior, publication ordering, and run-log output.
  - `tests/cli/test_authoring_cmds.py` — Cover branch binding preservation for retained-artifact failures.

## Implementation

- **Foundational logic:** Resolve one bounded classifier proposal into one final declaration before publication, then preserve and classify any artifact a later failure leaves behind.

- **Keep resolution in the pre-write flow.** Run the resolver after step 2 has established a single-plan proposal and after the create flow has finalized its in-memory authoring state, but before `plan_tool/create.py:_prepare_create_plan` returns `PreparedCreatePlan` for `plan_tool/create.py:_publish_create_plan`. Set the declaration on the in-memory `Plan` so `plan_tool/create.py:write_new_plan` performs the only initial plan write.

- **Keep `CreateResult` unchanged.** Do not use `plan_tool/create.py:CreateResult` as a risk-declaration handoff. Preserve its existing split-proposal no-write exit, including the rule that a split never reaches risk resolution, plan writing, or manifest publication.

- **Bound every final choice.** Offer an ordinary interactive operator the proposal, its evidence-based rationale, and only final tiers permitted by step 2’s minimum. Acceptance may keep the proposed rationale only when it is non-empty, one line, and still explains the final tier. An override must include a non-empty one-line final rationale, and operator escalation to `high` remains allowed. Any malformed internal proposal rationale becomes step 2’s standard fallback before resolution rather than reaching plan validation.

- **Protect low-tier admission.** Never persist `low` unless step 2 admitted it from all required affirmative evidence and its independent source counter-signal screen. Never persist any final tier below the proposal floor. Preserve the admission state in the private proposal so the resolver rejects a low final tier when that screen found any named consumer, contract, migration, auth/authz, external, schema, API, or runtime-surface counter-signal, even if the model response omitted it. If an internal proposal falls outside step 2’s closed contract, fail before publication instead of inventing a weaker declaration.

- **Define decline as a declaration, not cancellation.** An interactive decline continues create with an explicit `standard` declaration and a rationale that says the proposal was declined. The saved pair must describe `standard`, not the rejected model proposal.

- **Treat every silent path as standard.** For no-source creates and any path without an interactive risk choice, including non-TTY stdin, EOF, and `--yes`, record an explicit `standard` declaration with a deterministic rationale. A silent resume must not restore an interactive decision checkpoint; it discards or bypasses that state and follows the same standard rule. Do not accept, preserve, or silently promote a model proposal in these modes.

- **Checkpoint the reviewed decision separately.** Add a dedicated operator-decision checkpoint beside `plan_tool/create.py:_STEP_REVIEW_CHECKPOINT_NAME` and `plan_tool/create.py:_INTENT_REVIEW_CHECKPOINT_NAME`; do not reuse step 2’s classifier checkpoint. Only a matching interactive non-replacement resume may restore the final tier, rationale, and decision mode, and only when the selected source, full predicted plan target, complete bounded proposal, and decision mode still match. `resume=False`, an explicit replacement, a mode mismatch, or a corrupt payload must resolve the declaration again.

- **Fail before publication if durability fails.** If saving an interactive decision checkpoint fails, raise a create error before `plan_tool/create.py:_publish_create_plan` starts. Do not write a plan, mutate the manifest, or leave a decision that cannot be safely resumed.

- **Make checkpoint use match the recovery lifecycle.** A normal completed create removes the risk checkpoints and records successful discard through `RunLoggerLike`. Retain them after interruptions or failures before manifest publication so an operator can explicitly recover that attempt. A registered collision at the same predicted target stops before classifier or decision checkpoint resume; an explicitly authorized replacement always resolves both risk stages fresh; a matching iteration-incomplete continuation retains its established resume behavior. Include the full predicted plan target in both risk checkpoint identities so a distinct create cannot consume an already completed attempt's risk state. This preserves the existing registration operation and avoids a second transaction.

- **Classify the created-artifact boundary in the publication owner.** The decision-checkpoint durability gate runs before any replacement archive or target write, so its failure leaves both collision and named-source files unchanged. The first on-disk target write begins retained-artifact recovery; an explicitly authorized replacement or `--from-existing` conversion keeps its existing source-archive contract rather than gaining a new rollback guarantee. Its temporary stub must deliberately fail structured-plan validation, so only completion of the final write and successful reparse makes an artifact parse-valid. A concept-synchronization failure before `append_to_manifest` retains the written artifact and reports the same parse-valid adoption or repair/removal guidance as every other pre-manifest artifact; it never deletes that artifact automatically. After `append_to_manifest`, an unexpected finalization error is a registered incomplete tail: retain and report the plan as already canonical, do not offer adoption, and leave success-only CLI summary and source/distilled-artifact archival unreachable. The existing `iteration_stage_failure` result is different: it remains a completed registered create, preserves its existing continuation checkpoints, and retains its current CLI summary and source/distilled-artifact archival behavior. A plain retry must preserve every retained artifact; an operator may instead name a pre-manifest artifact through `--from-existing`, which is the existing explicit conversion command and may archive its named source. Preserve the artifact unless one of those explicit recovery actions is chosen. The normal CLI error path displays a finalization `CreateError` and therefore must not run success-only source or distilled-artifact archival.

- **Carry interrupts through the same boundary.** In the publication owner, catch `KeyboardInterrupt` only after the first target write has begun, classify the on-disk target with the same valid/unregistered, invalid/unregistered, or registered state used for failure reporting, and surface that state to `cmd_create` before the interrupt exits 130. The CLI prints the same recovery guidance and preserves a branch-aware binding for that retained artifact; it does not turn the interruption into success or run success-only archival. An interrupt before a target exists retains the existing direct exit-130 and branch-rollback behavior.

- **Keep a retained artifact on its owning branch.** When branch-aware create selected and bound a disambiguated branch, an error or interruption that reports either a pre-manifest retained artifact or a registered finalization error keeps that binding and branch for the operator's recovery. Roll back the temporary binding only for failures or interruptions before a target artifact exists. The publication owner must make the artifact-state distinction available to this CLI boundary without changing branch behavior for ordinary success or no-artifact errors.

- **Make the decision visible in the run log.** Use the existing `RunLoggerLike.phase_start` and `RunLoggerLike.phase_end` pattern to record the proposal, final declaration, and decision mode. Keep the record useful for distinguishing interactive acceptance, override, decline, checkpoint replay, and silent standard fallback without changing step 4’s completion-summary surface.

- **Keep flow documents factual and aligned.** In `docs/how-to/pipeline/create-from-existing.md`, extend the high-level single-plan path and source map with the declaration and retained-artifact boundaries. In `docs/how-to/recovery/create.md`, add both classifier and operator-decision checkpoints to the resume table and explain which inputs—including the full predicted target—must match, when a checkpoint remains available, when normal finalization removes it, how same-target collision differs from an iteration continuation, and how pre-manifest and registered-tail failures differ.

## Tests

- `test_interactive_risk_declaration_accepts_admitted_proposal_before_initial_write` — Accepting an admitted proposal writes the final tier and rationale in the single initial plan write.
- `test_interactive_risk_declaration_override_requires_final_rationale_and_respects_floor` — An override records its own rationale and cannot choose a tier below the proposal minimum.
- `test_interactive_risk_declaration_decline_records_standard_final_rationale` — Declining continues create with an explicit standard pair that describes the decline.
- `test_malformed_classifier_rationale_falls_back_before_final_declaration` — Blank or multiline proposal rationale follows the step 2 standard fallback instead of reaching plan validation.
- `test_risk_declaration_never_persists_low_without_step_two_admission` — A malformed or inconsistent internal proposal, including one whose source screen found any named counter-signal omitted by the model response, cannot create a low declaration.
- `test_silent_risk_declaration_uses_standard_without_accepting_model_proposal` — Non-TTY stdin and EOF record standard without a risk-choice prompt, model-proposal acceptance, or interactive-checkpoint replay.
- `test_tty_yes_risk_declaration_uses_standard_without_accepting_model_proposal` — `--yes` on a TTY remains a silent standard path.
- `test_no_source_create_persists_standard_without_risk_prompt` — No-source creation receives the explicit standard declaration supplied by step 2 without a decision walk.
- `test_interactive_risk_declaration_checkpoint_replays_exact_matching_decision` — A matching interactive resume restores the tier, rationale, and mode without prompting again.
- `test_silent_resume_never_replays_interactive_risk_decision` — Non-TTY, EOF, and `--yes` resumes record standard rather than reusing an interactive decision.
- `test_changed_risk_proposal_source_target_or_mode_invalidates_risk_decision_checkpoint` — Changed classifier input, full predicted target, bounded proposal, or decision mode cannot replay a stale operator choice.
- `test_replacement_create_resolves_risk_decision_fresh` — An explicitly authorized replacement cannot restore a prior final declaration even when its other checkpoint inputs match.
- `test_no_resume_resolves_risk_declaration_fresh` — `resume=False` bypasses a matching decision checkpoint.
- `test_risk_decision_checkpoint_save_failure_blocks_publication` — A failed checkpoint save leaves `write_new_plan` and manifest publication unreachable.
- `test_pre_manifest_artifact_failure_reports_recovery_without_deletion` — A failure during final plan writing, reparse, or manifest publication retains the artifact and reports repair/removal, explicit adoption, or the separate explicit conversion path.
- `test_postwrite_interrupt_reports_recovery_and_preserves_branch_binding` — An interrupt after the target exists exits 130 with the matching recovery report and leaves a branch-aware artifact bound, while a pre-write interrupt keeps the existing rollback.
- `test_pre_manifest_concept_sync_failure_retains_artifact_for_recovery` — A concept-synchronization failure before manifest publication retains and classifies the written artifact rather than deleting it.
- `test_successful_create_discards_risk_decision_checkpoint` — Normal finalization removes the new checkpoint and emits its discard event.
- `test_same_target_collision_or_iteration_continuation_preserves_checkpoint_boundary` — A registered collision stops before risk checkpoint consumption, while the established iteration-incomplete continuation remains resumable.
- `test_registered_finalization_error_reports_incomplete_state` — An unexpected post-manifest finalization error retains the registered plan, reports its incomplete tail, and does not offer adoption or success-only CLI tail work.
- `test_retained_artifact_keeps_branch_aware_binding` — A branch-aware create error after target creation preserves the bound branch for adoption or manual completion, while a no-artifact error rolls it back.
- `test_risk_decision_run_log_records_proposal_final_declaration_and_mode` — The run log records the values and mode needed to audit the decision.
- `test_create_plan_signature_is_exact` — Remains green to prove this private behavior adds no public `create_plan` parameter.

### Tests for this step

Every listed test must be green before this step is complete. Run `uv run pytest tests/test_create.py -q` during implementation, then run the plan’s configured test command before handoff.

## Acceptance criteria

- A single-plan create resolves a final risk tier and one-line rationale before `plan_tool/create.py:write_new_plan` runs.
- Every new plan written by this flow contains both declaration fields, and the rationale explains the final tier.
- Interactive acceptance, override, and decline each produce a bounded declaration; decline produces explicit `standard`.
- No final declaration falls below step 2’s minimum, and `low` is impossible without step 2’s affirmative admission and clear source counter-signal screen.
- No-source, non-TTY, EOF, and `--yes` risk-decision paths record explicit `standard` without accepting a model proposal.
- Only a matching interactive non-replacement risk-decision checkpoint restores the exact final decision; silent mode, changed source, full predicted target, proposal state, `--no-resume`, and explicit replacement resolve it fresh.
- A risk-decision checkpoint write failure prevents any plan or manifest publication.
- Once a plan artifact exists, every failure or interruption reports its retained path and recovery state. Before manifest publication, parse-valid artifacts can be explicitly adopted and invalid ones need repair/removal; an unexpected finalization error after manifest publication reports the registered plan as incomplete and does not offer adoption. The existing iteration-incomplete result remains a completed registered create. A same-target collision stops before risk checkpoint reuse, while full-target identity prevents cross-target reuse and explicit `--from-existing` conversion remains a distinct create from a pre-manifest named source. A branch-aware retained artifact stays bound to its selected branch. Normal finalization removes the checkpoint, while failure paths do not add automatic partial-artifact cleanup.
- The create run log records the proposal, final declaration, and decision mode.
- `docs/how-to/pipeline/create-from-existing.md` and `docs/how-to/recovery/create.md` describe the same single-plan, resume, and created-artifact recovery rules implemented in `plan_tool/create.py`.

## References

- [io — Core tools for working with streamshttps: — Use for the TTY and non-interactive decision boundary.
- [json — JSON encoder and decoderhttps: — Use for checkpoint payload decoding and malformed-payload handling.
- [Models | Pydantic Docshttps: — Use for preserving a valid typed plan while setting the final frontmatter declaration.

## Applicable guardrails

- **The plan’s “## Plan intent”, operator-owned signal:** Keep the classifier advisory; only a permitted operator decision may choose a nonstandard final tier.
- **The plan’s “## Step intent”, retry and recovery boundary:** Make the decision resumable, visible in the run log, and safe across create failures.
- **The plan’s “## Out of scope”, non-TTY model acceptance:** Record standard on every silent decision path rather than treating model output as operator approval.
- **The plan’s “## Out of scope”, downstream consumers:** Do not change detail authoring, completeness audit, apply, run, or Jira behavior.
- **The plan’s “## Out of scope”, confidence and existing-plan behavior:** Do not add confidence automation, migrate existing plans, alter split handling, or extend annotate or scope-out flows.
- **The plan’s “## Scope contract”, allowed behavior changes:** Limit this step’s user-visible work to the risk-decision prompt, run-log record, and permitted retained-artifact failure report; leave completion output to step 4.

## Deferred

- Create completion-summary rendering — Step 4 owns `plan_tool/cli/authoring.py` and its CLI coverage.
- Retained-artifact recovery verification — Step 5 owns the cross-boundary test matrix for this step’s recovery behavior.
- Downstream tier consumption — The sibling risk-profile-2 work owns detail, audit, and apply behavior.
- Confidence or certainty policy — The plan’s #295 follow-up owns evidence-supported calibration.
- Existing-plan migration and split, annotate, or scope-out changes — The plan’s “## Out of scope” keeps these flows unchanged.
