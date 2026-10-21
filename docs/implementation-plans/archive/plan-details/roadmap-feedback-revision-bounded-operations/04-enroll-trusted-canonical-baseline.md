# Step 4 — Enroll a trusted canonical baseline and publish every semantic roadmap change as one recoverable set

## Summary

Add `plan_tool/roadmap_source_identity.py` to own a stage-keyed, non-feedback canonical baseline and its identity checks. Wire `plan_tool/roadmap.py`, `plan_tool/roadmap_revision_publish.py`, `plan_tool/roadmap_revision_run.py`, and `plan_tool/roadmap_structural_revision_run.py` so accepted artifact changes publish their artifact, baseline, and required seed-state invalidation as one recoverable generation under the existing writer guard. Add the explicit `plan-tool roadmap <slug> --enroll-baselines` trust action in `plan_tool/cli/roadmap_cmd.py` for legacy canonical roadmaps. Green means no successful writer leaves changed roadmap semantics paired with seed state that still marks derived seeds current, and no failed writer silently adopts untrusted source as a baseline.

## Table of Contents

- [Summary](#summary) — The step’s publication and enrollment outcome.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — The current split writes and premature seed invalidation this step replaces.
- [Input](#input) — Existing stage, artifact, writer-guard, seed-state, and merge contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New baseline files and the writer and CLI updates.
- [Implementation](#implementation) — Baseline identity, enrollment, recoverable publication, and writer integration.
- [Tests](#tests) — Contract tests for trust, recovery, and writer ordering.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary references for digests, atomic replacement, JSON, and hermetic tests.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this a source and publication step.
- [Deferred](#deferred) — Source admission routing and evidence work owned elsewhere.

## Why

`plan_tool/roadmap.py:_write_artifact` currently publishes an artifact separately from `_invalidate_roadmap_seeds`, while `plan_tool/roadmap_revision_run.py:_run_accepted_revision` and `plan_tool/roadmap_structural_revision_run.py:_run_accepted_structural_revision` invalidate seeds before a candidate is known to publish. `plan_tool/roadmap_revision_publish.py:publish_revision_candidate` and `publish_structural_revision_proof` then replace only the artifact. That leaves no durable, trusted comparison value for later source admission and allows interruption or rejection to split artifact, baseline, and seed lifecycle state.

## Input

- **Step 3 merge result:** Consume step 3’s canonical typed artifact candidate. This step publishes that result and its non-feedback baseline; it does not redefine stage operations, row authority, or merge behavior.

- **Stage and artifact contract:** Use `plan_tool/roadmap.py:RoadmapStage` with its `artifact_key`, parser, renderer, and artifact path helper. Use the four artifact renderers in `plan_tool/roadmap_artifacts.py` as the canonical text boundary.

- **Writer ownership:** Preserve `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard` and `RoadmapWriterToken` as the sole cross-process writer lease. Every recovery and publication action in this step runs under that lease.

- **Seed lifecycle contract:** Preserve the validated `version`, `seeds`, `status`, `digest`, and `published` shape owned by `plan_tool/roadmap_seed_state.py:validate_seed_state`. A publication may snapshot and replace this state, but must not add a new seed lifecycle state.

- **Recorded brief source:** Keep `plan_tool/roadmap_source.py:read_recorded_brief_source` and `plan_tool/roadmap_artifacts.py:brief_source_path` limited to concept-brief grounding. A brief reference is not a canonical artifact baseline.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_source_identity.py` — Define validated baseline records, non-feedback projection and digest creation, baseline loading, comparison facts, and pending-generation metadata.
  - `tests/test_roadmap_source_identity.py` — Cover the baseline record, semantic projection, digest, malformed-state refusal, and module boundary.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Route ordinary stage publication and recovery through the shared guarded publisher instead of independently writing an artifact and then invalidating seeds.
  - `plan_tool/cli/roadmap_cmd.py` — Register and dispatch `--enroll-baselines`, reject incompatible companion modes, and render its bounded result without invoking a backend.
  - `docs/cli/roadmap.md` — Regenerate the roadmap command reference from the live parser so the public enrollment option and its boundary stay current.
  - `plan_tool/roadmap_revision_publish.py` — Replace pre-invalidation plus one-file publication with guarded recovery and recoverable artifact, baseline, and seed-state generation publication.
  - `plan_tool/roadmap_revision_run.py` — Stop invalidating seeds before the local backend request; pass the accepted candidate to the shared publication boundary.
  - `plan_tool/roadmap_seed_state.py` — Provide validated, independent seed-state snapshots suitable for a recoverable publication generation while preserving the current sidecar schema.
  - `plan_tool/roadmap_structural_revision_run.py` — Keep structural proof and exact-evidence checks intact while moving seed invalidation into its final shared publication action.
  - `tests/test_roadmap.py` — Cover ordinary writer publication, baseline enrollment service behavior, and recovery before a normal stage run.
  - `tests/cli/test_cli_reference.py` — Keep the generated roadmap command reference byte-identical to the parser output.
  - `tests/cli/test_roadmap_cmd.py` — Cover the enrollment flag, exclusivity, output, and no-backend dispatch.
  - `tests/test_roadmap_revision_publish.py` — Cover publication generations, recovery outcomes, writer-token enforcement, and seed-state inclusion.
  - `tests/test_roadmap_revision_run.py` — Cover local publication ordering and unchanged seed state on rejected or failed work.
  - `tests/test_roadmap_seed_state.py` — Cover isolated validated seed-state snapshots used by publication recovery.
  - `tests/test_roadmap_structural_revision_run.py` — Cover structural publication ordering without changing structural selection or proof authority.

## Implementation

- **Store a trusted semantic baseline.** Make `plan_tool/roadmap_source_identity.py` own a versioned record keyed to the roadmap slug and `RoadmapStage.artifact_key`. The record must retain the canonical parsed projection of all artifact semantics except `feedback`, plus its digest and enough stage identity to reject a record written for another roadmap or stage.

- **Treat feedback as normal input, not source drift.** Exclude all feedback rows from the baseline projection. Keep constructs, removal records, ordering entries, and body prose in the projection so an add, edit, delete, rename, or prose change remains detectable and explainable later.

- **Snapshot feedback only for one publication attempt.** In the source-identity leaf, add a short-lived ordered canonical feedback projection with a digest and enough value to name a changed row or order. A bounded route captures it after source admission and selected-row preflight, then rechecks it before any correction/retry prompt and before replacing that artifact. It is never enrolled or persisted as a trust baseline, and an observed mismatch is a fail-closed concurrent-reviewer change rather than semantic source drift.

- **Use the digest as an index, not the only evidence.** Compare the deterministic non-feedback projection first through its digest, then retain the canonical value needed to identify a changed row, field, or body span. Do not use `render(parse(current_text))` as proof that source semantics are trusted; it only proves the current text can be rendered canonically.

- **Keep the source-identity leaf independent of orchestrators.** `plan_tool/roadmap_source_identity.py` may use artifact-level types or serialized values it needs for the projection, but it must not import `plan_tool/roadmap.py`, revision runners, or CLI modules. Those modules consume its facts.

- **Add one explicit enrollment boundary.** Add `--enroll-baselines` to `plan_tool/cli/roadmap_cmd.py:register` and dispatch it from `cmd_roadmap` as an exclusive, no-backend action. It accepts only an exact-rendered contiguous stage prefix beginning with the first stage in `plan_tool/roadmap.py:STAGES`; after pending bootstrap recovery, reject a gap, a later-stage-only artifact, noncanonical text, or a fully enrolled prefix.

- **Do not rewrite artifacts during enrollment.** Enrollment records the operator-trusted current canonical projection and logs the action, but makes no model request and does not normalize or replace roadmap artifact text. If the enrolled prefix includes Plans, include invalidated seed state in the same bootstrap generation because existing seeds cannot be proven to derive from that newly trusted source.

- **Journal the complete enrollment prefix.** Record every new baseline in one pending bootstrap generation before replacing any member. Its old/new member sets cover the whole requested prefix and the Plans seed-state sidecar when applicable. Recover that set before testing enrollment state: a partial prefix restores its old set, a complete prefix clears its record, and a retry never has to decide whether a partly enrolled prefix is a direct edit or an incomplete earlier enrollment.

- **Publish a recoverable generation, not a sequence of unrelated writes.** In `plan_tool/roadmap_revision_publish.py`, record the full old and new state before replacing any member, then verify the committed set before clearing the pending record. The publication gate accepts caller-provided, already-admitted canonical upstream artifacts rather than rereading upstream paths; step 5 supplies and rechecks that source admission for the local route. Only a brand-new stage with no predecessor, baseline, or derived-seed state publishes an artifact and baseline pair. A missing artifact beside a baseline or seed-state sidecar is an invalid direct deletion, never fresh authoring. An accepted bounded feedback publication at any stage publishes the artifact, baseline, and invalidated seed state together.

- **Represent absence explicitly.** The pending generation must distinguish an absent old artifact or baseline from unknown bytes. This covers first publication and lets recovery remove a partially written first generation instead of treating it as a special unrepairable state.

- **Recover only known generations.** On entry to `run_roadmap`, `run_local_feedback_revision`, and `run_structural_revision`, recover any pending set while holding `roadmap_writer_guard`. Keep a fully recorded new set, clear a fully recorded old set, and restore a mixed recorded set to old. If any member matches neither recorded generation, refuse without replacing it.

- **Require source and feedback checks at publication.** Make the shared publisher accept source-admission bindings and an optional selected-feedback snapshot from its caller. It never rereads arbitrary raw upstream text; the normal and local routes recheck their admitted files and selected feedback before a correction/retry prompt and immediately before calling it. The publisher preserves that fail-closed boundary for observed mismatches, but does not claim a raw-editor compare-and-swap guarantee after the final check and during atomic replacement.

- **Move invalidation behind successful candidate proof.** Remove the early `preinvalidate_roadmap_seeds` calls from the accepted local and structural runner paths. A blank reply, rejected operation, merge rejection, failed gate, stale structural proof, or interrupted backend call leaves seed state unchanged. The shared publisher invalidates only when it is committing the accepted artifact generation.

- **Keep each route’s authority unchanged.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision` remains selector-bound, and `plan_tool/roadmap_structural_revision_run.py:run_structural_revision` retains its evidence selection, evaluator, merge, proof, and final guarded recheck. They share only recovery and final publication.

- **Prepare, but do not yet route by, source identity.** Expose the baseline and canonical working-value contract needed by step 5. Do not add feedback-free stage selection, no-op completion, new outcomes, or receipt and evidence source admission in this step.

## Tests

### Tests for this step

- `test_baseline_projection_excludes_feedback_and_retains_all_nonfeedback_semantics` — Verifies feedback-only changes do not alter baseline identity while rows, removals, ordering, and body prose do.

- `test_baseline_record_binds_slug_stage_format_and_projection_digest` — Verifies a baseline cannot be loaded for a different roadmap, stage, format, or digest.

- `test_baseline_comparison_identifies_row_field_and_body_semantic_drift` — Verifies retained canonical content supports an actionable difference rather than a digest-only refusal.

- `test_feedback_snapshot_is_ordered_ephemeral_input_not_baseline_identity` — Verifies added, changed, reopened, reordered, and removed feedback changes a short-lived publication snapshot without changing baseline identity or enrollment records.

- `test_source_identity_module_does_not_import_roadmap_or_runner_modules` — Verifies the new identity leaf cannot create an orchestrator import cycle.

- `test_enroll_baselines_accepts_only_exact_canonical_contiguous_prefix` — Verifies enrollment records each stage in a valid prefix without calling an invoker or rewriting artifacts.

- `test_enroll_baselines_rejects_gap_noncanonical_suffix_and_fully_enrolled_prefix` — Verifies enrollment cannot silently trust a partial, altered, or already trusted roadmap after pending bootstrap recovery.

- `test_enroll_baselines_recovers_interrupted_prefix_before_enrollment_state_checks` — Interrupts between baseline members of a requested prefix and verifies recovery restores or completes one whole prefix before a retry checks whether it is fully enrolled.

- `test_plans_enrollment_invalidates_seeds_in_the_same_recoverable_generation` — Verifies Plans enrollment never leaves a new baseline beside current seed state.

- `test_ordinary_stage_publication_commits_artifact_and_baseline_together` — Verifies `plan_tool/roadmap.py:run_roadmap` publishes a first or replacement artifact with its matching baseline.

- `test_missing_plans_artifact_with_current_seed_state_refuses_as_direct_deletion` — Verifies a residual current sidecar cannot be carried through a fresh-authoring path after a Plans artifact is deleted.

- `test_publication_recovery_keeps_recorded_new_generation` — Verifies recovery clears a pending record when every member already matches the recorded new generation.

- `test_publication_recovery_clears_recorded_old_generation_and_restores_mixed_generation` — Verifies old and mixed states return to one known generation, including removal of members recorded absent.

- `test_publication_recovery_refuses_unknown_member_without_overwrite` — Verifies an intervening unrecorded edit is never replaced during recovery.

- `test_feedback_publication_invalidates_seed_state_for_every_stage_key` — Verifies accepted Domain, Constraints, Components, and Plans feedback publications include invalidated seed state.

- `test_local_revision_failure_before_publication_keeps_seed_state_current` — Verifies local invoke, parse, merge, and gate failures do not pre-invalidate seeds.

- `test_local_revision_passes_accepted_candidate_to_shared_generation_publisher` — Verifies local invalidation occurs only at final publication, after its selected candidate clears validation.

- `test_publication_refuses_changed_feedback_snapshot_before_retry_or_replacement` — Verifies a bounded candidate cannot overwrite observed feedback added, changed, reopened, reordered, or removed after preflight, and cannot send a stale correction prompt between attempts.

- `test_publication_gate_accepts_caller_admitted_upstreams_without_rereading_paths` — Verifies the publisher gates the explicit canonical upstream map and leaves source-admission timing to the caller.

- `test_structural_revision_invalidates_seeds_only_with_proved_publication` — Verifies structural invocation and proof failures leave seed state unchanged while a proved publish commits the shared generation.

- `test_seed_state_generation_snapshot_is_validated_and_independent` — Verifies publication recovery cannot mutate the live seed-state object through a reused nested entry.

- `test_enroll_baselines_cli_is_exclusive_and_never_invokes_backend` — Verifies `cmd_roadmap` rejects companion modes and reports the explicit enrollment result without stage execution.

- `test_every_generated_file_matches_disk` — Requires the generated roadmap CLI reference to include the public enrollment option exactly as the live parser renders it.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `plan-tool roadmap <slug> --enroll-baselines` creates baselines only for an exact-canonical contiguous stage prefix, journals that whole prefix as one recoverable bootstrap set, does not rewrite an artifact or call a backend, and refuses gaps, suffixes, noncanonical artifacts, and fully enrolled prefixes after recovery.

- `docs/cli/roadmap.md` is regenerated from the live parser after the enrollment option changes.

- Every baseline binds its roadmap slug, stage key, format version, canonical non-feedback projection, and projection digest.

- Feedback-only changes do not change baseline identity; any non-feedback row, removal, ordering, or body-prose change does.

- A bounded publication captures the selected artifact's ordered feedback snapshot after preflight and refuses an observed changed snapshot before a retry/correction prompt or replacement without persisting that snapshot as baseline state.

- A brand-new stage with no predecessor, baseline, or derived-seed state recovers and commits its artifact and baseline as one recorded generation under `roadmap_writer_guard`. A missing artifact with residual baseline or seed-state data refuses as a direct deletion.

- Every accepted bounded feedback publication commits its artifact, baseline, and invalidated seed state as one recorded generation, regardless of the selected stage.

- Recovery accepts only recorded old or new member bytes, restores or completes one whole recorded generation, and refuses unknown bytes without replacement.

- Failed, rejected, stale, or interrupted local and structural revisions do not invalidate seed state before publication.

- The shared publisher gates the candidate against its caller-provided canonical upstream map and never treats a fresh upstream file read as admitted source.

- The shared publisher accepts the normal and local routes' final source-binding and feedback-snapshot checks, so an observed change refuses before any artifact, baseline, or seed-state replacement. It does not promise to preserve an uncoordinated raw write that races after those checks and during atomic replacement.

- `run_local_feedback_revision` remains selector-bound and `run_structural_revision` retains its existing evidence and proof checks.

- `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py tests/test_roadmap_revision_publish.py tests/test_roadmap_revision_run.py tests/test_roadmap_seed_state.py tests/test_roadmap_source_identity.py tests/test_roadmap_structural_revision_run.py -q` passes.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 for the stable canonical projection identity.

- [os.replace — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html#os.replace) — Review the replacement boundary used by the recoverable generation writer.

- [Python 3.13 json — JSON Encoder and Decoder](https://docs.python.org/3.13/library/json.html) — Use strict JSON parsing and serialization for baseline and pending-generation records.

- [pytest: How to Monkeypatch/Mock Modules and Environments](https://docs.pytest.org/en/stable/how-to/monkeypatch.html) — Simulate replacement boundaries, interrupted generations, and no-backend paths hermetically.

## Applicable guardrails

- **The plan’s “## Plan intent”, code-owned canonical changes:** Use the baseline only to support deterministic publication of typed merge results. Do not create a general artifact rewrite or patch surface.

- **The plan’s “## Out of scope”, gate and retry boundary:** Preserve current stage gates, retry behavior, and completed-result behavior. This step changes publication consistency, not candidate acceptance rules.

- **The plan’s “## Out of scope”, local and structural authority:** Keep local revision selector-bound and structural revision evidence-bound. Their shared publisher must not widen either route’s authority.

- **The plan’s “## Out of scope”, broad recovery boundary:** Recover only an interrupted recorded generation. Do not add a feedback-free rebuild or infer recovery work from `--from-stage`.

- **The plan’s “## Out of scope”, baseline-reader boundary:** Do not apply baseline admission to receipt, impact, escalation, or structural-evidence readers in this step.

- **The plan’s “## Out of scope”, retention and raw-YAML boundaries:** Do not add retention semantics or alter the reviewer-authored YAML feedback path while changing baseline and seed-state publication.

## Deferred

- **Baseline source admission and feedback-free stage routing** — Step 5 consumes the trusted baseline to select bounded feedback work, canonicalize harmless presentation drift in memory, and handle no-op stages.

- **Receipt, impact, escalation, and structural-evidence freshness** — The plan’s “## Out of scope” reserves those readers and their raw-evidence contracts for the re-scoped source-identity work.

- **A broad recovery command for direct semantic edits** — The plan’s “## Out of scope” requires an explicit future operator surface rather than extending interrupted-generation recovery.
