> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Enroll an exact immutable root and atomically fence every legacy writer before accepted head becomes observable

## Summary

Add one guarded immutable-root enrollment path and make an accepted-head selector the point where legacy in-place mutation becomes unavailable. Update `plan_tool/roadmap.py`, `plan_tool/roadmap_versions.py`, and `plan_tool/roadmap_revision_publish.py` to capture one exact complete root and publish its stored members and selector through the shared journal boundary. Fence every legacy stage, baseline, seed, local-revision, structural-revision, and feedback-reopen writer while preserving unversioned behavior and immutable evidence publication. On green, an accepted head never points at incomplete root storage, and enrolled roadmaps cannot change legacy authoritative files.

## Table of Contents

- [Summary](#summary) — The enrollment and writer-fence outcome.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why root authority and legacy refusal must arrive together.
- [Input](#input) — The complete-bundle, version, and journal contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped implementation and test files.
- [Implementation](#implementation) — Root enrollment, recovery, and legacy-writer refusal rules.
- [Tests](#tests) — Focused coverage for publication ordering and refusal paths.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable replacement references for the publication boundary.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this proof narrow.
- [Deferred](#deferred) — Later lifecycle and reader work outside this step.

## Why

`plan_tool/roadmap.py:run_roadmap()` and the legacy publication helpers can still replace live artifacts, baselines, seed state, and seeds after a roadmap has immutable stored content. A selector that becomes visible before those routes refuse creates two canonical sources; a fence without an atomically published root creates no usable authority. This step makes the root and selector available only through one guarded generation, then uses that same accepted-head decision to stop every legacy mutation route.

## Input

- **Complete root evidence:** Step 1 preserves the existing complete snapshot gate behavior, and step 3 extends `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` with the exact recorded-brief byte binding needed for stored root content. Enrollment must require a complete stage-ordered bundle; it must not enroll a prefix or fill a member from a live path later.

- **Stored-version contract:** Step 3 supplies `plan_tool/roadmap_versions.py:load_accepted_version()` and `is_roadmap_enrolled()` as the only accepted-head and enrollment decisions. A missing selector is unversioned; a present but invalid selector must refuse mutation rather than act as an unversioned roadmap.

- **Publication boundary:** Step 2 exposes the guarded `plan_tool/roadmap_source_identity.py:PendingGeneration` publication path from `plan_tool/roadmap_revision_publish.py`. Enrollment must use its recorded old and replacement bytes rather than add another multi-file write protocol.

- **Legacy writer lease:** `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()` and `require_roadmap_writer_token()` serialize all participating roadmap writers. Enrollment checks and legacy refusal must run while the matching token remains active.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Add the domain-level immutable-root enrollment operation and stop stage, baseline, and seed entry points before legacy work begins.
  - `plan_tool/cli/roadmap_cmd.py` — Stop `--materialize` before its lifecycle, seed classification, backend call, or report write; keep command registration unchanged.
  - `plan_tool/roadmap_revision_publish.py` — Add the token-held legacy-writer fence and narrow enrolled-journal recovery rules while leaving the shared generation publisher available to version-owned writes.
  - `plan_tool/roadmap_revision_run.py` — Return the existing preflight-rejected result before a local-revision invoker runs on an enrolled roadmap.
  - `plan_tool/roadmap_structural_revision_run.py` — Check the fence before evaluator setup or structural-revision invocation.
  - `plan_tool/roadmap_feedback_reopen.py` — Refuse confirmed feedback reopen before source admission or publication when enrolled.
  - `plan_tool/roadmap_versions.py` — Build and validate the root enrollment generation from the step 3 storage contract.
  - `tests/test_roadmap.py` — Cover exact root capture plus stage, baseline, and seed refusal.
  - `tests/cli/test_roadmap_cmd.py` — Cover the materialize-only CLI bypass and retained HTML behavior.
  - `tests/test_roadmap_revision_publish.py` — Cover generation ordering, recovery, legacy wrappers, and unversioned compatibility.
  - `tests/test_roadmap_revision_run.py` — Cover local-revision preflight refusal.
  - `tests/test_roadmap_structural_revision_run.py` — Cover refusal before evaluator and invoker setup.
  - `tests/test_roadmap_feedback_reopen.py` — Cover confirmed-reopen refusal without artifact replacement.
  - `tests/test_roadmap_impact_run.py` — Characterize immutable impact-evidence publication for an enrolled roadmap with no legacy journal.
  - `tests/test_roadmap_versions.py` — Cover exact root records, raw-byte preservation, selector ordering, and already-enrolled refusal.

## Implementation

- **Foundational logic:** Treat a validated accepted-head selector as the atomic boundary between an unversioned roadmap and an enrolled roadmap whose legacy writers must refuse.

- **Capture one complete exact root under the writer lease.** Add a domain enrollment entry point in `plan_tool/roadmap.py` that holds `_roadmap_writer_owner()` from preflight through publication. Build its source only from the complete captured bundle and recorded-brief bytes supplied by steps 1 and 3. Require all `plan_tool/roadmap.py:STAGES` in their defined order, preserve stored artifact and raw brief bytes exactly, and refuse incomplete, noncanonical, gate-failing, or already-enrolled input without writing a root or selector.

- **Recheck freshness in the journaled final window.** Pass step 3's complete captured snapshot to step 2's final-recheck callback and call `recheck_roadmap_impact_snapshot()` while admitting the exact in-flight root generation. Revalidate every artifact and the raw recorded-brief binding after the journal is durable and before any generation member is replaced. A mismatch must remove the pre-write journal and leave root storage and the selector unchanged; the held writer token remains active through this check and publication.

- **Keep legacy baseline enrollment separate.** `plan_tool/roadmap.py:enroll_roadmap_baselines()` remains a legacy prefix-baseline route and must refuse after enrollment. Do not reinterpret its contiguous-prefix behavior as immutable-root enrollment.

- **Publish the root before the selector.** Have `plan_tool/roadmap_versions.py` build one fixed-storage root generation and send it through the step 2 journal boundary. The generation must contain the complete root record and its stored artifact and brief members before the accepted-head selector member. The selector must be the final replacement so readers cannot select missing or partial root content.

- **Do not move live authority during enrollment.** Root enrollment may store immutable copies and select that root, but it must not rewrite top-level roadmap artifacts, baseline records, seed state, draft seeds, promoted seeds, or prior stored versions. A repeat enrollment must not replace an existing accepted head.

- **Fence legacy wrappers, not the generic transaction.** Add one shared token-checked enrollment guard near `plan_tool/roadmap_revision_publish.py:require_roadmap_writer_token()`. Apply it before rendering, gate work, journal creation, replacement, deletion, or seed-state writes in `preinvalidate_roadmap_seeds()`, `enroll_stage_baselines()`, `publish_stage_artifact()`, `publish_revision_candidate()`, `publish_feedback_reopen_candidate()`, and `publish_structural_revision_proof()`. Do not put an unconditional enrolled check inside the shared generation publisher: immutable root enrollment and later selector-only promotion require that lower boundary.

- **Keep recovery within the writer-produced happy path.** Keep `recover_roadmap_publication()` unchanged for unversioned legacy routes. Before enrollment, a pending non-root generation refuses before capture; a pending `root-enrollment` generation may use the existing durable recovery boundary. Once an accepted head exists, recovery may clean up only a fully committed root-enrollment generation that exactly matches the selected root, or the future selector-only accepted-head generation whose old and replacement selector bytes both validate. [#329 owns exact member validation for a falsely labelled pre-enrollment root journal.

- **Stop direct legacy entry points before side effects.** In `plan_tool/roadmap.py`, make `run_roadmap()`, `accept_roadmap_seed()`, `apply_roadmap_seeds()`, `materialize_plan_seed()`, `materialize_and_diff_one_plan()`, and `refresh_roadmap_seeds()` check the shared fence while their writer token is held. Cover both owned-token and caller-supplied-token seed paths. Refusal must precede `_write_brief_source()`, `_write_roadmap_seed_state()`, `_materialize_seed_rows()`, `write_seed_refresh_report()`, prompt rendering, and any backend invoker.

- **Close only the materialize CLI bypass.** `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_materialize_owned()` must check the same fence before `_roadmap_command_lifecycle()` begins. Do not add a global `cmd_roadmap()` rejection: `--view html`, immutable evidence actions, and ordinary read-only views are not legacy artifact writers.

- **Use existing runner refusal paths.** `plan_tool/roadmap_revision_run.py:run_local_feedback_revision()` must return a preflight rejection before local source admission or invocation. In `plan_tool/roadmap_structural_revision_run.py:run_structural_revision()`, acquire the roadmap writer guard and check enrollment before `verified_structural_evaluator()` runs; unversioned recovery remains inside that protected path. `plan_tool/roadmap_feedback_reopen.py:run_confirmed_feedback_reopen()` must return its preflight refusal before it reads or publishes the selected artifact.

- **Preserve allowed non-legacy writes.** Do not edit `plan_tool/roadmap_impact_run.py:run_roadmap_impact_analysis()` for the no-journal case: it must continue to publish immutable impact evidence for an enrolled roadmap. Keep `plan_tool/cli/roadmap_cmd.py:_cmd_roadmap_view()` and its existing HTML derived-output overwrite behavior unchanged.

## Tests

### Tests for this step

- `tests/test_roadmap_versions.py:test_root_enrollment_stores_exact_complete_stage_and_raw_brief_bytes` — Enrollment preserves every stage member and recorded raw brief bytes in the immutable root.
- `tests/test_roadmap_versions.py:test_root_enrollment_refuses_existing_storage_or_selector_without_replacement` — Existing version storage or a selected head prevents root replacement.
- `tests/test_roadmap.py:test_immutable_root_enrollment_rechecks_before_storage_or_head_publication` — A changed captured artifact or raw brief prevents root publication.
- `tests/test_roadmap.py:test_immutable_root_enrollment_refuses_pending_legacy_publication_without_mutating_live_state` — A pending legacy journal leaves live artifact bytes and the journal unchanged; enrollment refuses before capture.

Every listed test must be green before this step is complete.

## Acceptance criteria

- A successful enrollment captures one complete exact root and atomically publishes its accepted-head selector only after every selected root member exists.
- Enrollment rechecks every captured artifact and the raw recorded brief in the journaled final pre-write window and writes no root member or selector when either changed after capture.
- Enrolling preserves top-level roadmap artifacts, baselines, seed state, draft seeds, promoted seeds, and prior stored-version bytes.
- An enrolled roadmap refuses every legacy artifact, baseline, seed, seed-state, and journal mutation before replacement or deletion.
- A completed root-enrollment journal can clean up after head selection, while enrolled legacy or mixed journals remain unchanged on refusal.
- Unversioned legacy routes retain their current behavior.
- Enrolled roadmaps retain immutable impact-evidence publication and HTML derived-output behavior.
- All tests named in `## Tests` pass.

## References

- [os — Miscellaneous operating system interfaceshttps: — Review atomic replacement expectations that the shared durable publication boundary preserves.
- [json — JSON encoder and decoderhttps: — Review strict, deterministic JSON handling for accepted-head and stored-root records.

## Applicable guardrails

- **The plan’s “## Scope guardrails”, allowed behavior changes** — Limit this step to root enrollment and refusal of legacy in-place writers while retaining unversioned behavior.

- **The plan’s “## Scope guardrails”, allowed reorganization** — Keep version-aware selection in the shared accepted-head boundary; do not reorganize unrelated roadmap pipeline or artifact-model code.

- **The plan’s “## Scope guardrails”, model-output boundary** — Do not add a model-assisted fallback, candidate proposal, or automatic authority move to a refused legacy route.

- **The plan’s “## Scope guardrails”, bounded feedback and structural rewrite** — Preserve both existing routes for unversioned roadmaps; enrolled routes refuse rather than gain cross-artifact write authority.

- **The plan’s “## Out of scope”, legacy-writer integration and recovery hardening** — Refuse legacy writers instead of migrating them to version production or adding a general journal-ownership system.

## Deferred

- CLI enrollment action — Step 11 exposes the completed domain enrollment operation without reusing `--enroll-baselines`.

- Accepted-head reader migration — Step 10 converts the selected downstream roadmap view; other readers remain outside this step.

- Candidate proposal, review, answer, and promotion lifecycle — Steps 5 through 9 own those version consumers and the later selector replacement.

- Broader recovery, history, retention, and legacy-writer migration — Record any need for wider storage work through the plan’s deferred process rather than expanding this fence.

- **Persistence-integrity hardening (2026-09-01, user-confirmed)** — A falsely labelled `root-enrollment` journal is outside this happy-path proof because normal lifecycle writers do not create it. [#329 owns exact member-set validation; do not expand this step for that state.
