> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 3 — Build the corpus replay engine and label-keyed artifact/run-log store

## Summary

Create `plan_tool/quality_bench.py` as the replay and durable-capture engine, plus `tests/test_quality_bench.py` for its focused contract tests. The engine takes the completed step-1 corpus snapshot, replays each item’s stage-2 route in an isolated scratch repository, and retains only label-owned evidence under `.plan-tool/quality-bench/`. Its key design decision is to pin all corpus, source, backend, and timeout inputs before replay, then publish a complete immutable generation through a recoverable label transition. When green, a label either names one complete, reproducible capture or remains unchanged after any refusal, mismatch, interruption, or failed replacement.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the replay engine and stored result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail file.
- [Why](#why) — Why replay needs a private snapshot and durable evidence store.
- [Input](#input) — Upstream corpus, metric, roadmap, backend, and logging contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New engine and tests plus the ignore rule.
- [Implementation](#implementation) — Replay, pinning, storage, replacement, and recovery requirements.
- [Tests](#tests) — Focused cases that define the replay and publication contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-step outcomes.
- [References](#references) — Standard-library references for the persisted formats and scratch workspaces.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this engine.
- [Deferred](#deferred) — Related work owned by later or separate steps.

## Why

`plan_tool/bench.py:run_bench_matrix` runs a different synthetic matrix and stores trial records, while `plan_tool/roadmap.py:run_roadmap` writes live roadmap artifacts rather than retaining a fixed corpus replay. The quality-bench lane needs one bounded, stage-2-only replay that cannot absorb an edited corpus, a changed source checkout, or an ambient backend setting during capture. It also needs evidence that steps 2, 5, and 6 can recompute without reopening a scratch directory or consulting the live repository.

## Input

- **Step 1 corpus snapshot.** Step 1 supplies the canonical ordered corpus snapshot, validated item ids, declared replay inputs, and corpus digest. Treat that snapshot as the only corpus source after preflight; do not reopen `--corpus` while processing items.

- **Step 2 stored-evidence contract.** Step 2 defines the metric registry’s durable evidence inputs. Persist the input snapshot, generated artifact bytes, run-log bytes, and serialized `RoadmapResult` facts in forms that step 2 can read without a live corpus path or scratch directory.

- **Roadmap stage route.** `plan_tool/roadmap.py:STAGES`, `RoadmapStage`, and `run_roadmap` define the stage table and replay entrypoint. `plan_tool/roadmap_artifacts.py:DOMAIN_FILENAME` and `CONSTRAINTS_FILENAME`, plus `plan_tool/roadmap_source_identity.py:baseline_path`, define the admitted stage-1 inputs a stage-2 replay needs.

- **Backend and timeout scopes.** `plan_tool/backend.py:get_active_backend` and `spawn_cwd`, `plan_tool/shell.py:scoped_claude_timeout`, and `plan_tool/backend_runner.py:scoped_silence_timeout` define the active execution settings that the replay must capture once and hold fixed.

- **Run-log contract.** `plan_tool/run_log.py:RunLogWriter`, `read_run_events`, and `run_log_path` define the JSONL evidence produced during a roadmap run. Retain completed log bytes rather than relying on the scratch path that produced them.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/quality_bench.py` — Corpus replay entrypoint, execution-input pinning, scratch materialization, label store readers and writers, and recoverable replacement handling.
  - `tests/test_quality_bench.py` — Unit and seam tests for snapshot-only replay, capture evidence, dirt checks, collisions, replacement, and recovery.

- **Existing files (edits only):**
  - `.gitignore` — Add the root-anchored `/.plan-tool/quality-bench/` runtime-store rule.

## Implementation

- **Keep the engine narrow.** Make `plan_tool/quality_bench.py` own one corpus-to-capture workflow. It must not compute a quality score, decide a floor, compare labels, add a CLI parser, or alter the existing synthetic benchmark in `plan_tool/bench.py`.

- **Freeze inputs before any scratch work.** Build one private preflight record from step 1’s complete corpus snapshot, including its exact input bytes and digest. Derive the label’s corpus digest from that same canonical encoding. A later corpus edit must not affect a running capture.

- **Pin a source execution identity.** Capture a complete identity for the resolved source root before replay, including the source revision and the root it applies to. Use `plan_tool/scenario_capture.py:repo_sha` as the repository-provenance precedent, but fail closed when the required identity cannot be established. Recheck the same identity immediately before and after every item and again before publication.

- **Pin the effective backend profile.** Capture the already-selected source-root backend from `plan_tool/backend.py:get_active_backend`, its effective configured profile, and the configured and silence timeout values that apply to a replay attempt. Serialize this profile canonically and retain its digest in the capture. Do not resolve project backend settings from the scratch repository.

- **Keep the pinned execution route fixed.** Run every item under the original effective backend and frozen timeout scopes. Add one capture-specific recovery-policy seam from the quality-bench roadmap invoker through `plan_tool/roadmap.py:shell_roadmap_invoker` into `plan_tool/shell.py:claude_invoke`, before `run_with_rate_limit_recovery` selects a backend or prompts. It permits a rate-limit wait only on the pinned profile; a configured fallback, interactive ask/switch, or profile change is converted to a capture refusal before `_select_rate_limit_backend`, the interactive menu, or a second backend invocation, even when the selected profile would compare equal. Record the actual profile digest on every allowed attempt.

- **Replay only the selected stage.** For each item, create an empty scratch repository using the isolation shape in `plan_tool/bench.py:_git_init_scratch` and `_git_commit_baseline`. Materialize the brief, admitted stage-1 artifact, and trusted baseline only from the private snapshot. Inside `plan_tool/backend.py:spawn_cwd`, call `plan_tool/roadmap.py:run_roadmap` with the stage table ending at the item target and `from_stage` set to that target. For this v1 corpus, that runs stage 2 once, re-admits stage 1, and never reaches a later stage.

- **Preserve roadmap retry and logging behavior.** Reuse `run_roadmap` rather than duplicating its stage parsing, gates, or attempt loop. Use its `run_logger` seam and retain the completed JSONL bytes. Store the emitted stage-2 artifact bytes separately from the result facts so consumers never need to reconstruct output from temporary paths.

- **Reject dirty source state at both boundaries.** Call `plan_tool/cli/gitcommit.py:working_tree_dirty` before scratch materialization and before publication. Treat a dirty or unreadable source tree as a refusal that removes private capture state and leaves an existing label generation untouched.

- **Validate label paths before joining.** Require the plan’s lower-case label shape and reject path separators, traversal, and malformed values before any store path is built. Follow the path-sink boundary in `plan_tool/roadmap_artifacts.py:_validate_slug`: format validation alone is not enough when a caller value becomes a directory name.

- **Persist self-contained version-1 evidence.** Write a versioned `label` envelope containing the corpus snapshot, capture identity, backend profile, every item’s stored inputs and outputs, run-log bytes, and serialized `RoadmapResult` facts. A `raw-sample` is not per-item attempt evidence: step 5 writes one complete-corpus envelope under `(floor_id, sample_ordinal)`, whose `items` map is keyed by validated manifest id and retains that rerun’s inputs, outputs, log bytes, and result facts. Store no required reference to a scratch path, live corpus path, or ambient configuration.

- **Make capture generations immutable.** Build and validate a new generation privately before a label points to it. An existing label must fail without `--force`; it must never be silently overwritten.

- **Publish forced replacements recoverably.** `plan_tool/quality_bench.py` owns exactly one `plan_tool/repo_lock.py:repo_mutation_lock` from label lookup through journal recovery and final pointer publication; its caller never nests that lock. Define a version-1 `current-label-pointer` envelope carrying its target `capture_id` and capture digest, and a version-1 `label-replacement-journal` carrying old/new capture ids and digests plus the reserved archive slot. Under `--force`, reserve that numbered archive slot, write and validate the journal, preserve the old generation at the reserved archive location, verify both generations, then atomically update the integrity-checked label pointer.

- **Recover without an absent label.** Model the transaction and recovery guarantees on `plan_tool/roadmap_revision_publish.py:_publish_generation` and `recover_roadmap_publication`, but keep the quality-bench store independent because its label/archive layout is distinct. Recovery under the mutation lock must either complete a valid recorded transition or retain the old complete generation; lookup must never return a missing or partial logical label.

- **Keep ignored runtime state precise.** Edit `.gitignore` to add only `/.plan-tool/quality-bench/`. Prove that the same dirt predicate accepts generated store files because Git ignores that exact root path, while a neighboring untracked path still makes the source tree dirty.

## Tests

### Tests for this step

- `test_replay_uses_the_preflight_snapshot_after_the_corpus_changes` — Mutates the corpus after preflight and proves the replayed item, stored inputs, and corpus digest still come only from the captured bytes.

- `test_replay_materializes_only_the_admitted_stage_one_inputs` — Proves the scratch repository receives the item brief, stage-1 artifact, and matching trusted baseline, with no ambient corpus files.

- `test_replay_runs_stage_two_once_and_never_runs_a_later_stage` — Records the `run_roadmap` arguments and proves the table ends at the target, `from_stage` selects it, and later stages are unreachable.

- `test_replay_scopes_backend_spawns_to_the_scratch_repository` — Proves the backend sees the item scratch directory through `plan_tool/backend.py:get_active_spawn_cwd` and that the scope resets afterward.

- `test_replay_pins_the_source_root_backend_profile_and_timeouts` — Changes ambient backend or timeout inputs during replay and proves every attempt uses the preflight profile and frozen timeout values.

- `test_capture_recovery_refuses_switch_before_another_backend_invocation` — Proves the capture-specific recovery seam refuses configured and interactive switch paths before backend selection or a second backend execution, including a switch that would otherwise resolve to the same profile; a pinned-profile wait/retry remains recorded and allowed.

- `test_source_identity_mismatch_before_or_after_an_item_preserves_existing_label` — Proves each required recheck rejects the capture and leaves the old label and archive generation unchanged.

- `test_dirty_source_before_materialization_refuses_capture` — Proves a tracked or unignored source change prevents scratch creation and label publication.

- `test_dirty_source_before_publication_discards_private_capture` — Proves dirt introduced during replay prevents publication and preserves any prior label.

- `test_label_envelope_retains_item_inputs_outputs_run_log_and_result_facts` — Proves each manifest item id maps to durable input bytes, output bytes, JSONL log bytes, and JSON-safe `RoadmapResult` facts.

- `test_raw_sample_envelope_is_versioned_full_corpus_evidence` — Proves a floor raw sample has the required envelope kind, `(floor_id, sample_ordinal)` identity, and one complete manifest-id-keyed item map; invalid item ids cannot enter that map.

- `test_invalid_label_is_rejected_before_store_paths_are_created` — Proves malformed, uppercase, and traversal-bearing labels create no store directory.

- `test_existing_label_refuses_without_force` — Proves a collision leaves the existing current generation and archive entries unchanged.

- `test_force_replacement_archives_old_generation_then_updates_current_pointer` — Proves a forced replacement reserves a numbered archive slot, retains the old complete generation there, and points the label only to the validated new generation.

- `test_recovery_completes_a_valid_journaled_transition` — Proves restart recovery recognizes a fully recorded completed replacement and clears only its journal state.

- `test_recovery_restores_old_generation_from_a_partial_transition` — Proves an interrupted replacement retains the old complete capture and never exposes a partial current generation.

- `test_engine_owns_one_mutation_lock_for_direct_capture` — Calls the direct mutable engine entrypoint and proves it takes one lock, never a nested acquisition; step 4 covers CLI dispatch.

- `test_quality_bench_store_is_ignored_but_neighboring_untracked_state_is_dirty` — Proves the `.gitignore` rule lets `working_tree_dirty` accept the exact quality-bench store while an adjacent untracked path still refuses capture.

Every test in `tests/test_quality_bench.py` must be green before this step is complete.

## Acceptance criteria

- A valid step-1 snapshot replays every item from private captured bytes and stores a stable corpus digest derived from those bytes.

- Each replay runs only its selected stage-2 route in an isolated scratch repository, with stage 1 re-admitted and no later roadmap stage invoked.

- Every stored label capture contains versioned input, output, run-log, result-fact, source-identity, backend-profile, and timeout evidence keyed by validated item id; every floor raw sample is one full-corpus `(floor_id, sample_ordinal)` envelope with that same manifest-id item mapping.

- A changed corpus, source identity, backend profile, timeout source, dirty source tree, or interactive/fallback backend selection rejects the capture before another backend reinvocation or publication and retains the prior label state.

- A label collision fails without `--force`.

- A forced replacement retains the old complete generation in its reserved numbered archive slot and changes a versioned, integrity-checked current-label pointer only after the new generation validates; its versioned journal is the only recoverable transition state.

- Restart recovery under the repository mutation lock yields either the old complete generation or the new complete generation, never an absent or partial label.

- `.gitignore` contains `/.plan-tool/quality-bench/`, and `tests/test_quality_bench.py` proves that exact ignored store does not count as source dirt while neighboring untracked state does.

## References

- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Read for strict versioned envelopes, canonical JSON encoding, and stored result facts.

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Read for converting frozen result records into durable JSON-safe evidence.

- [tempfile — Generate temporary files and directories — Python documentation](https://docs.python.org/3/library/tempfile.html) — Read for creating one isolated scratch workspace per corpus item.

## Applicable guardrails

- **The plan’s “## Step intent”, private snapshot and pinned execution inputs.** `plan_tool/quality_bench.py` must treat source, corpus, backend, and timeout drift as a capture refusal, not as a reason to continue with mixed evidence.

- **The plan’s “## Step intent”, bounded roadmap replay.** This engine may replay only the corpus’s declared single authoring stage and must not expand into later-stage or multi-verb execution.

- **The plan’s “## Step intent”, label publication and recovery.** Store mutation must remain lock-protected, recoverable, and pointer-safe for both first publication and replacement.

- **The plan’s “## Out of scope”, report-only measurement.** The engine may retain factual evidence but must not score quality, block a workflow, tune a backend, or make a quality decision.

- **The plan’s “## Out of scope”, no parallel fan-out.** Process corpus items serially; do not add concurrent replay workers.

## Deferred

- `quality-bench` CLI parsing and capability registration — Step 4 owns the namespaced command surface, so this step exposes engine-level behavior only.

- Metric calculation, noise-floor sampling, and label comparison — Steps 2, 5, and 6 own those consumers of the stored evidence.

- Corpus content and format changes — Step 1 owns the v1 snapshot contract and fixtures.

- A shared generic publication-journal utility — `plan_tool/roadmap_revision_publish.py` remains the roadmap-specific precedent; extracting a cross-store transaction layer is a separate refactor decision.

- Changes to `plan_tool/bench.py` — Its synthetic backend matrix remains independent from this fixed roadmap corpus replay.
