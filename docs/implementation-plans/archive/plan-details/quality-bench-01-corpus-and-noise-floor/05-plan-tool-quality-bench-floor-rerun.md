> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 5 — Add `plan-tool quality-bench floor` for identity-pinned rerun noise floors

## Summary

Extend `plan_tool/quality_bench.py` with the serial floor-capture workflow and extend `plan_tool/cli/quality_bench_cmd.py` with the `quality-bench floor` action. The command reruns one corpus three times by default, pins its complete execution identity, and stores immutable raw samples plus one registry-v1 floor record. The key design decision is all-or-nothing publication: any incomplete sample set, dirt, or identity mismatch leaves existing floor evidence and the current pointer unchanged. When green, an operator receives a factual per-metric floor table without a quality verdict or changed success condition.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the floor command and its publication rule.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why deterministic metrics need measured rerun spread.
- [Input](#input) — Upstream replay, identity, metric, and store contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The engine, CLI, and focused test footprint.
- [Implementation](#implementation) — Required sampling, identity, storage, and CLI behavior.
- [Tests](#tests) — Focused cases that define the floor contract.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-step outcomes.
- [References](#references) — Standard-library references for records and CLI parsing.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Related work left to later steps or reconciliation.

## Why

`plan_tool/bench.py:run_bench_matrix` repeats a separate backend matrix, but no current command measures how the fixed roadmap corpus varies when its source execution identity is unchanged. Without a measured floor, a later deterministic metric delta cannot distinguish ordinary rerun spread from a code-change effect. This step gives the stored-evidence lane from step 3 one complete, identity-bound baseline for each registry-v1 metric.

## Input

- **Step 3 replay and evidence contract.** Use step 3’s landed corpus replay entrypoint, stored-evidence readers, version-1 envelope rules, and source/backend identity capture. Its landed public signature is authoritative; floor must not duplicate its corpus validation, scratch materialization, roadmap-stage selection, or backend recovery logic.

- **Step 2 metric registry.** Use step 2’s landed registry-v1 declarations and each metric’s own distance function. The floor logic must not recreate metric definitions or calculate a generic distance from serialized values.

- **Step 4 command and lock contract.** Extend the `quality-bench` command group created by step 4. CLI dispatch deliberately leaves every quality-bench subaction unlocked; this mutable action calls the step-3 engine entrypoint, which acquires exactly one repository mutation lock for the full floor lifecycle.

- **Identity equality.** Use the source execution identity captured by step 3, including its code and prompt digests, rather than an absolute checkout path. The corpus digest, replay descriptor, source identity, and canonical backend-profile digest together define the one identity a floor record may represent.

## Files (creates vs edits)

- **New files:**
  - `tests/test_quality_bench_floor.py` — Hermetic engine and command tests for reruns, identity checks, floor calculation, and publication.

- **Existing files (edits only):**
  - `plan_tool/quality_bench.py` — Add floor capture, raw-sample and floor-record publication, current-pointer replacement, and a result record for CLI rendering.
  - `plan_tool/cli/quality_bench_cmd.py` — Register and dispatch `quality-bench floor`, validate its arguments, forward the invoker seam, and print the completed floor facts.

## Implementation

- **Foundational logic: serial identity-pinned floor capture.** Add one engine-level floor entrypoint in `plan_tool/quality_bench.py` that drives exactly `R` complete step-3 corpus replays. Run captures one after another; do not reuse `plan_tool/bench.py:run_bench_matrix` because its matrix, resume behavior, and record format do not preserve the all-or-nothing floor contract.

- **Require a usable rerun count.** Add `quality-bench floor --corpus <dir> [--reruns R]` beneath the dedicated `quality_bench_action` destination in `plan_tool/cli/quality_bench_cmd.py`. Default `--reruns` to 3 and reject values below 2 before a replay or store mutation starts.

- **Pin the complete identity once.** Before sample one, obtain a clean preflight from the step-3 engine that supplies the resolved corpus digest, replay descriptor, full source execution identity, and canonical backend-profile digest. Recompute and compare all four values immediately before and after every sample, and again before raw-sample, floor-record, or pointer publication.

- **Treat every mismatch as a failed capture.** Dirt, unreadable Git state, changed corpus/replay/source/profile identity, or a step-3 backend-switch refusal must discard all private samples for the attempted floor. The operation must leave every earlier immutable floor record and current-floor pointer unchanged.

- **Keep samples private until complete.** Retain exactly one complete version-1 `raw-sample` envelope for each successful rerun under `(generated_floor_id, sample_ordinal)`. Its `items` map carries every manifest-id-keyed item capture, including the retained inputs, outputs, run log bytes, and result facts needed for later registry recomputation; it is not one envelope per item. Do not publish a readable floor record or advance a pointer unless all `R` samples completed and passed their identity rechecks.

- **Calculate each floor through the registry.** For every registry-v1 metric, compute the maximum pairwise distance across all sample values using that metric declaration’s registered distance function. Equal values produce numeric zero. If any required sample value is unavailable, record an explicit `unfloored` result with its reason rather than using zero, omission, or a replacement value.

- **Retain evidence, not only numbers.** Bind the immutable floor record to its corpus/replay/source/profile identity, rerun count, raw samples, and per-metric coverage map. Preserve enough label-owned evidence for step 6 to recompute a later registry version from retained samples without a backend call.

- **Make immutable publication collision-safe.** Generate and validate a safe floor id in `plan_tool/quality_bench.py`; do not accept an operator-selected id in this action. Under the existing mutation lock, reserve an absent final record path before publishing. One approach is to use `plan_tool/fileio.py:durable_create_text` semantics for that reservation, then allocate another generated safe id on collision. Never overwrite an immutable record or retarget an existing pointer as part of collision handling.

- **Advance only the matching current pointer.** After the complete floor record validates, atomically replace the version-1 current-floor pointer for that exact corpus/replay/source/profile identity. The pointer must identify the chosen immutable floor record and its digest. An interruption before this point must leave the prior pointer selected.

- **Keep the CLI handler thin and factual.** Have `plan_tool/cli/quality_bench_cmd.py` resolve the repository through `plan_tool/cli/context.py:_resolve_cmd_repo_root`, forward the corpus path, rerun count, repository root, and optional invoker seam to the engine, and render the floor id, identity facts, sample count, and per-metric numeric or `unfloored` results. Follow `plan_tool/cli/roadmap_cmd.py:cmd_roadmap` by forwarding the invoker only when a test supplies one.

- **Return reporting success only.** A complete floor capture must return zero regardless of its numeric floors or `unfloored` entries. Do not add a quality classification, threshold warning, gate, automatic tuning action, or `bench` command change.

## Tests

### Tests for this step

- `test_floor_defaults_to_three_serial_reruns` — The command and engine use three captures when `--reruns` is omitted and never overlap sample execution.

- `test_floor_rejects_reruns_below_two_before_capture_or_store_access` — A value below two fails before an invoker call, raw sample, record, or pointer mutation.

- `test_floor_forwards_corpus_reruns_and_stubbed_invoker` — The CLI action resolves the repository and forwards its parsed inputs and exact optional invoker seam to the engine.

- `test_floor_pins_corpus_replay_source_and_profile_across_every_sample` — A change to any pinned identity component before or after a sample discards the private set and preserves earlier published evidence.

- `test_floor_refuses_source_dirt_during_sampling_and_before_publication` — Dirt or unreadable Git state at each required recheck prevents a new record and pointer update.

- `test_floor_source_identity_does_not_depend_on_checkout_path` — Equivalent clean source identities from different checkout paths compare equal for floor matching.

- `test_floor_stages_one_versioned_full_corpus_raw_sample_per_completed_rerun` — A complete run retains exactly `R` version-1 `(floor_id, sample_ordinal)` raw-sample envelopes, each holding its full manifest-id-keyed corpus capture.

- `test_interrupted_floor_publishes_no_record_and_preserves_current_pointer` — A capture interrupted before all reruns finish leaves no new readable record and keeps the old pointer target.

- `test_floor_uses_each_registry_metric_distance_and_maximum_pairwise_value` — Deliberately varied sample evidence produces the maximum distance across every pair for each registry-v1 metric.

- `test_identical_metric_values_have_zero_floor` — Equal available metric values produce a numeric floor of zero.

- `test_missing_metric_value_is_explicitly_unfloored` — Any unavailable required sample value creates an `unfloored` entry with a reason instead of a numeric substitute.

- `test_floor_record_and_current_pointer_use_version_one_envelopes` — The immutable record and exact-identity pointer have the required schema version and closed record kinds.

- `test_floor_id_collision_allocates_new_id_without_overwrite` — A reserved immutable record remains unchanged when a generated id collides, while the completed floor receives another safe id.

- `test_completed_floor_prints_table_and_exits_zero_without_quality_gate` — The CLI prints the floor id and every metric result, including `unfloored`, and returns zero for a completed measurement.

Every test in `tests/test_quality_bench_floor.py` must be green before this step is complete.

## Acceptance criteria

- `plan-tool quality-bench floor --corpus <dir>` runs three serial corpus captures by default, while `--reruns` accepts only values of at least two.

- Every floor capture uses one matching corpus digest, replay descriptor, source execution identity, and canonical backend-profile digest across all reruns.

- Any dirt, identity mismatch, backend-profile change, or incomplete sample set publishes no new floor record and leaves the prior current pointer unchanged.

- A complete floor retains one immutable full-corpus `(floor_id, sample_ordinal)` raw-sample envelope per rerun and one immutable version-1 floor record bound to those samples.

- The floor coverage map contains every registry-v1 metric as either its maximum pairwise registered distance or an explicit `unfloored` result.

- Identical available metric values produce a floor of zero.

- A generated floor-id collision leaves the existing record and pointer target unchanged and allocates a different safe id for the new record.

- The matching current-floor pointer advances only after the completed record validates.

- The completed CLI output identifies the floor and prints a factual per-metric table; it returns zero without a quality gate or changed exit behavior.

- `tests/test_quality_bench_floor.py` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Read for version-1 envelope encoding and strict evidence decoding.

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Read for immutable floor results and serialized evidence records.

- [argparse — Parser for command-line options, arguments and sub-commands](https://docs.python.org/3/library/argparse.html) — Read for the nested `floor` parser and `--reruns` validation.

## Applicable guardrails

- **The plan’s “## Step intent”, pinned execution identity.** `plan_tool/quality_bench.py` must refuse mixed corpus, replay, source, or backend evidence instead of measuring across it.

- **The plan’s “## Step intent”, complete publication.** Keep raw samples private until the complete set can become one immutable floor record and matching current pointer.

- **The plan’s “## Out of scope”, report-only behavior.** The command may report stored metric spread but must not judge quality, block work, tune configuration, or change success based on a result.

- **The plan’s “## Out of scope”, bounded replay.** Reuse only the fixed corpus and step-3 replay route; do not add another verb, corpus family, or control arm.

- **The plan’s “## Out of scope”, no parallel fan-out.** Run reruns serially even when the corpus is slow.

- **The plan’s “## Risks”, manual noise review.** Render the evidence an operator needs for the required review, but do not turn a wide floor into an automatic warning, decision, or `BACKLOG.md` mutation.

## Deferred

- `quality-bench compare` classification — Step 6 consumes floor records to classify candidate deltas without invoking a backend.

- Additional deterministic metric versions — This step retains raw evidence for future recomputation but adds only the registry-v1 floor projection.

- A shared repeat-run framework with `plan_tool/bench.py:run_bench_matrix` — The existing matrix has different corpus, storage, and resume contracts; any consolidation requires separate refactor planning.

- The operator’s dated BACKLOG #216 outcome — An operator records that manual review after examining a completed first floor table; this step only supplies the evidence.
