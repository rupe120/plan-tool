> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Resume the sampler at the next un-run pass

## Summary

Resume `plan_tool/review.py:audit_plan_until_stable` from a saved nonterminal sampler checkpoint when its complete identity matches the current audit. Keep all resume decisions in the sampler, expose the already-resolved model through `plan_tool/backend.py`, and leave the two `plan_tool/cli/completeness_phases.py` call paths as thin callers. A mismatch, unreadable checkpoint, or malformed payload starts a clean pass-1 sampler with no carried state. Green means an interrupted audit resumes at its next logical pass with the same outcome as an uninterrupted run.

## Table of Contents

- [Summary](#summary) — The completed behavior at a glance.
- [Table of Contents](#table-of-contents) — Links to this detail file’s sections.
- [Why](#why) — Why completed sampler work must survive interruption.
- [Input](#input) — The checkpoint and identity contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped source and test changes.
- [Implementation](#implementation) — The resume gate, restoration rules, and caller boundaries.
- [Tests](#tests) — Focused coverage for resume and decline behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for payload decoding and identity hashes.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this work.
- [Deferred](#deferred) — Related work owned by later steps.

## Why

`plan_tool/review.py:audit_plan_until_stable` currently rebuilds its finding union, counters, observations, and calibration for every invocation, even when step 2 has preserved a completed pass boundary. Resuming that state avoids repeating completed logical passes, but only if every input that defines the sampler remains the same; otherwise carrying findings forward would combine different audits and make the result untrustworthy.

## Input

- **Step 1 checkpoint contract** — Step 1 supplies the stable in-progress saved-review artifact, its fail-closed loader, and the conditionally persisted sampler payload. Treat any loader or payload-validation failure as no usable checkpoint.

- **Step 2 pass boundary** — Step 2 saves only fully processed continuing passes and invalidates terminal checkpoints. Restore only this published state; never infer progress from an interrupted invocation.

- **Exact audit inputs** — Use `plan_tool/review_persistence.py:_audit_input_fingerprint` through the captured `AuditInputSnapshot` for the plan, selected detail bundle, source seed, project context, and detail grade.

- **Declared code input** — Use `plan_tool/fingerprint.py:compute_code_fingerprint` unchanged. `plan_tool/prompts/plan-audit.md` remains in step 3’s declared code surface because its bytes directly affect the audit prompt.

- **Backend selection** — Use `plan_tool/backend.py:get_active_backend` for the active backend name and the resolved model that `plan_tool/backend.py:build_effective_backend` carries forward.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/review.py` — Restore a matching sampler checkpoint before the pass loop, preserve all loop state, and decline safely to a fresh sampler.
  - `plan_tool/backend.py` — Add one effective-backend field for the resolved model and populate it without changing model-selection precedence or argv behavior.
  - `plan_tool/cli/completeness_phases.py` — Keep both conceptual-audit entry points on the one sampler-owned resume path and pass through only the state needed for existing presentation and run-log behavior.
  - `plan_tool/prompts/plan-audit.md` — Keep this prompt as a declared identity input; no prompt-contract change is part of this step.
  - `tests/test_review.py` — Add resume, decline, equivalence, and updated same-fixture sampler coverage.
  - `tests/test_backend.py` — Cover the resolved-model field on effective backends.

## Implementation

- **Make one sampler-owned identity predicate.** In `plan_tool/review.py:audit_plan_until_stable`, capture the current audit inputs and compare the complete recorded identity before initializing fresh loop state. The predicate must require equal audit-input fingerprint, declared code fingerprint, `max_passes`, `dry_rounds`, `new_threshold`, active backend name, and resolved model.

- **Decline as one safe outcome.** A missing checkpoint, identity mismatch, unreadable artifact, unsupported payload shape, or failed `Recommendation` reconstruction must start a fresh pass-1 sampler. Do not restore a subset of fields, repair malformed data, or prompt the operator to choose.

- **Restore every result-bearing loop value.** On a match, restore `by_id` in first-occurrence order, materiality, observations, pass count, dry-streak state, conformance and failure counters, terminal state, and the frozen value from `build_low_impact_demotion_lookup`. Rebuilding only some of these values changes coverage or arm-clustering results after resume.

- **Resume at the next logical pass.** Continue the existing `while passes < cap` loop with the restored pass count, so reporting, run-log attempts, carried-finding prompt text, and the cap all begin at pass N+1. The `max_passes` cap remains a total logical-pass budget across the interrupted and resumed invocations.

- **Keep the pass boundary unchanged.** Step 2 owns the write after complete pass bookkeeping. This step must not checkpoint between `check_plan_audit` and unioning its result, so a `KeyboardInterrupt` during a pass retries that pass rather than treating it as complete.

- **Preserve the existing terminal and error rules.** An errored nonterminal pass remains a completed sampler slot when step 2 persisted it. A `terminal-residue` checkpoint never satisfies the resume predicate and the fresh sampler path continues to honor the current dry-stop, cap, and plan-quota behavior.

- **Expose the resolved model as data.** Add the field to `plan_tool/backend.py:CliBackend` and set it in `plan_tool/backend.py:build_effective_backend` from the already-resolved model passed by `_select_effective_backend`. `default_model` remains configuration input, not proof of the model selected for this invocation. Preserve the no-override fast path, registry seed immutability, transport behavior, and the existing value-equality contract for effective descriptors.

- **Do not duplicate the gate in callers.** `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` and the conceptual-audit call in `_run_iterate_convergence_loop` must both delegate to `audit_plan_until_stable`. Keep the existing module-local `plan_tool.review` imports so test monkeypatches still intercept them.

- **Keep presentation separate from evidence.** Have the sampler emit a concise resume message with the next pass and carried finding count, or a decline message distinguishing malformed data from identity mismatch. Surface the minimum internal outcome needed by later reporting work, but do not add a `completeness-audit --json` field or alter `qualified_result` or `audit_coverage`.

- **Record a successful resume when a logger exists.** When `run_logger` is supplied and the exact resume gate accepts the checkpoint, emit one existing `CheckpointHit` before sampling resumes. Declines emit no hit; step 2 remains responsible for save and discard events.

- **Do not alter prompt semantics for resume.** `plan_tool/prompts/plan-audit.md` is watched because it is fixed audit input. A content change to that file must decline an old checkpoint through the declared code fingerprint; this step does not add a resume instruction or placeholder to the template.

## Tests

### Tests for this step

- `test_resume_after_interruption_starts_at_next_unrun_pass` — Interrupt after two persisted continuing passes and assert the second invocation makes only the remaining logical pass, with both carried findings in that pass’s prompt.

- `test_interrupted_inflight_pass_is_retried_not_counted` — Raise `KeyboardInterrupt` during the next pass and assert no partial result enters the restored union or pass count.

- `test_resume_restores_union_counters_observations_and_calibration` — Compare an uninterrupted canned sequence with an interrupted-and-resumed sequence for finding order, materiality, observations, coverage fields, and arm-clustering advisory.

- `test_resume_restores_nonterminal_errored_pass_without_respends` — Persist a continuing errored pass, then assert a matching later invocation preserves its consumed slot and failure counter.

- `test_sampler_checkpoint_identity_mismatch_starts_fresh` — Parameterize independent mutations of plan content, detail content, source seed, project context, declared code including `plan_tool/prompts/plan-audit.md`, detail grade, sampler parameters, backend, and resolved model; each case must start at pass 1 with no carried findings.

- `test_malformed_sampler_checkpoint_starts_fresh_without_raising` — Cover truncated JSON, an invalid persisted recommendation, and an unsupported checkpoint schema or role.
- `test_matching_resume_emits_checkpoint_hit_when_run_logger_is_present` — Asserts one `CheckpointHit` for an accepted resume and none for identity or malformed declines.
- `test_resume_and_decline_messages_name_the_observable_outcome` — Asserts the sampler reports next pass plus carried findings on resume, and distinct malformed versus identity-mismatch decline messages without changing coverage or JSON.

- `test_terminal_sampler_checkpoint_never_resumes` — Extend `TestPlanQuotaConceptualAudit.test_plan_quota_state_does_not_cross_audit_invocations` so a terminal outcome still makes the later invocation start fresh.

- `test_same_identity_sampler_fixture_resumes_instead_of_replaying_prefix` — Update any `TestAuditPlanUntilStable` fixture that intentionally crosses an interrupted same-plan invocation so its expected call count and carried prompt assert resumption rather than a replay.

- `test_build_effective_backend_exposes_resolved_model` — Assert `plan_tool/backend.py:build_effective_backend` preserves the selected model as data for direct model input and project-override selection.

- `test_effective_backend_model_field_preserves_existing_descriptor_contracts` — Assert no-override selection returns the base descriptor and model exposure does not change existing argv, transport, registry, or equality expectations.

Every named test, plus `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A matching in-progress checkpoint resumes with its first backend call at pass N+1 and carries the first N passes’ findings into the prompt.

- An interrupted in-flight pass is retried exactly once on resume and does not appear in the restored union, counters, or observations.

- A resumed chain completes no more than `max_passes` logical sampler passes in total.

- A resumed audit produces the same finding order, materiality, coverage record, and arm-clustering advisory as an uninterrupted audit over the same replies.

- Any identity mismatch, unreadable checkpoint, malformed payload, or unsupported checkpoint version starts a fresh pass-1 sampler without raising or carrying partial state.

- The active effective backend exposes the resolved model selected for dispatch without changing existing selection precedence or generated argv.

- `plan_tool/cli/completeness_phases.py:_sample_conceptual_audit` and `_run_iterate_convergence_loop` continue to use `plan_tool/review.py:audit_plan_until_stable` as the sole resume decision point.

- `qualified_result`, `audit_coverage`, reusable-final behavior, and the `completeness-audit --json` payload remain unchanged.

## References

- [json — JSON encoder and decoderhttps: — Read the decoding and `JSONDecodeError` behavior for the fail-closed checkpoint loader.

- [dataclasses — Data Classeshttps: — Read the field and serialization rules used by the persisted recommendation and backend descriptors.

- [hashlib — Secure hashes and message digestshttps: — Read the digest contract behind exact checkpoint identity comparisons.

- [Built-in Exceptions — the exception hierarchyhttps: — Read why `KeyboardInterrupt` remains outside `Exception` handling and represents an interrupted pass.

## Applicable guardrails

- **Exact recovery boundary** — The plan’s `## Plan intent` and `## Architecture` resume-identity contract limit restoration to an exact identity match. This step must start fresh on every decline path.

- **Sampler-only ownership** — The plan’s `## Out of scope` non-conceptual-audit fence limits behavior changes to `plan_tool/review.py:audit_plan_until_stable` and its existing completeness callers. Do not extend the mechanism to other generation, run, purity, or reconcile paths.

- **No new operator control** — The plan’s `## Out of scope` CLI boundary prohibits new resume flags and interactive choices. Matching resume remains automatic.

- **No wider snapshot** — The plan’s `## Out of scope` repository-identity boundary permits only the existing declared code fingerprint. Do not add a repository-wide or execution-policy fingerprint.

- **Evidence remains separate** — The plan’s `## Out of scope` final-evidence and JSON boundaries prohibit changing final-audit selection, reader eligibility, `qualified_result`, `audit_coverage`, or the JSON payload.

- **Pass boundaries only** — The plan’s `## Out of scope` partial-call boundary prohibits saving model output or progress from inside `check_plan_audit`.

## Deferred

- Final-reader rejection and audit-evidence-ledger discovery — Step 4 owns the downstream reader and diagnostic-artifact changes.

- Final-report provenance and operator documentation — Steps 5 and 6 own report fields and user-facing flow documentation.

- Concurrent sampler coordination and global repository consistency — The plan’s `## Out of scope` fence keeps both outside this step.
