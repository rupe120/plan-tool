> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 2 — Build the deterministic quality-bench metric registry

## Summary

Create `plan_tool/quality_bench_metrics.py` and `tests/test_quality_bench_metrics.py` as the fixed v1 metric contract for captured roadmap stage-2 evidence. The registry owns the complete metric vocabulary, each metric’s encoded value, its unavailable state, and its distance function. It reads only stored artifact bytes, run-log events, and serialized `RoadmapResult` facts; it does not inspect a live checkout or invoke a model. When green, later replay, floor, and compare work can recompute the same ordered per-item and corpus values from retained evidence.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the new registry and its completed behavior.
- [Table of Contents](#table-of-contents) — Links to every top-level section.
- [Why](#why) — Why the metric definitions must become a separate deterministic contract.
- [Input](#input) — Existing artifact, result, and run-log contracts the registry reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two new registry and test files.
- [Implementation](#implementation) — V1 evidence rules, metric definitions, unavailable handling, and distances.
- [Tests](#tests) — Unit cases that pin the registry contract.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completing the step.
- [References](#references) — Standard-library and YAML parsing references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep this registry factual and report-only.
- [Deferred](#deferred) — Storage, replay, floor, compare, and unrelated telemetry work left to later steps.

## Why

The repository has roadmap artifacts, run-log event records, and `RoadmapResult` facts, but no single contract says which factual measurements may be derived from them or how two measurements differ. `plan_tool/bench.py:_read_log_stats` and `plan_tool/cli/runs.py:_iter_call_samples` aggregate telemetry for other reporting surfaces, while `plan_tool/roadmap.py:_run_stage` and `_run_roadmap` define the stage-2 evidence this benchmark needs. This step fixes the vocabulary before replay data exists, so later floor and compare work cannot silently choose different counts, missing-value behavior, or distance rules.

## Input

- **Artifact bytes.** `plan_tool/roadmap_artifacts.py:CONSTRAINTS_FILENAME`, `DOMAIN_FILENAME`, `parse_constraints_artifact`, and `parse_domain_artifact` define the stored roadmap artifacts the registry reads.
- **Artifact row shapes.** `plan_tool/roadmap_artifacts.py:ConstraintsArtifact`, `DomainArtifact`, `ConstraintRow`, and `DecisionRow` define the rows and anchor fields used by the count, id, and domain-reference metrics.
- **Run facts.** `plan_tool/roadmap.py:RoadmapResult` and `OUTCOME_COMPLETED`, `OUTCOME_COMPLETED_NO_CHANGE`, `OUTCOME_STAGE_EXHAUSTED`, and `OUTCOME_STAGE_INVALID` define the stored exit outcome.
- **Run-log events.** `plan_tool/run_log.py:ClaudeCallStart`, `ClaudeCallEnd`, `PhaseEnd`, and `read_run_events` define the event names and fields used for attempts, wall time, and cost.
- **Stored-evidence handoff.** Step 3 persists the label-owned evidence this module consumes. This step defines the registry input as one item id plus optional stored domain/output bytes, stored run-log bytes, and serialized result facts; it must not depend on the live corpus path or scratch directory.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/quality_bench_metrics.py` — Pure registry, stored-evidence input records, v1 metric computation, unavailable values, and distance functions.
  - `tests/test_quality_bench_metrics.py` — Focused unit tests for every v1 metric and corpus-distance rule.

- **Existing files (edits only):**
  - None.

## Implementation

- **Make `plan_tool/quality_bench_metrics.py` the sole v1 metric contract.** Expose immutable metric declarations and computed-value records, with a version lookup that selects registry v1 explicitly. A declaration must own one stable metric name, one evidence-to-value function, and one same-metric distance function. Reject an unknown registry version rather than falling back to a different projection.

- **Keep the v1 vocabulary finite and ordered.** Registry v1 must contain exactly `artifact_bytes`, `row_counts`, `constraint_ids`, `domain_reference_counts`, `required_section_presence`, `frontmatter_present`, `roadmap_gate_attempts`, `exit_outcome`, `wall_time_ms`, and `cost_usd`, in the Architecture-table order. Do not let callers append a metric ad hoc or infer a metric from stored fields.

- **Use stored evidence as the only input boundary.** One recommended shape is a frozen per-item evidence record carrying the manifest item id, stored `01-domain.md` bytes, optional stored `02-constraints.md` bytes, stored run-log bytes, and the serialized `RoadmapResult.outcome`. The registry must not open paths, read the current corpus, inspect an environment variable, or call an invoker. Step 3 owns turning its capture into this input shape and writing it durably.

- **Preserve the distinction between absent output and present malformed output.** When `02-constraints.md` is absent, every artifact-derived metric must be explicitly unavailable rather than becoming zero, an empty set, or `False`. When bytes are present, `artifact_bytes` remains computable from the raw byte length even if parser-based metrics cannot parse the artifact. Keep the unavailable state distinct from every encoded metric value so later floor and compare code can render it as `unfloored`.

- **Compute parsed artifact metrics from the existing artifact contract.** Use `plan_tool/roadmap_artifacts.py:parse_constraints_artifact` for `row_counts` and `constraint_ids`, and use `parse_domain_artifact` with it for `domain_reference_counts`. `row_counts` is the ordered `(dispositions, constraints, decisions)` count vector. `constraint_ids` is the sorted set of constraint-row ids, so duplicate source rows do not multiply the set value.

- **Count domain references by occurrence, not by distinct id.** For `domain_reference_counts`, count every `ConstraintRow.anchor_ids` entry and every `DecisionRow.anchor` as declared, including repeated ids. Count an occurrence as resolved only when it appears in the union of stored domain entity, business-rule, and workflow ids. Do not treat a repeated id as one occurrence or use decision ids, disposition ids, or prose text as domain anchors.

- **Read section and fence metrics from raw output text.** `required_section_presence` must report the three booleans for list-valued raw YAML frontmatter keys `dispositions`, `constraints`, and `decisions`; prose headings and parsed empty tuples do not prove presence. `plan_tool/roadmap_artifacts.py:_iter_rows` deliberately treats a missing collection as no rows, so this metric needs its own raw-frontmatter read. `frontmatter_present` is true only when the first line after an optional UTF-8 BOM is exactly `---`; whitespace or a preamble before that fence makes it false.

- **Use the stage-2 run-log evidence exactly.** Filter only events whose `phase` is `stage-2-constraints`, the phase built by `plan_tool/roadmap.py:_run_roadmap`. `roadmap_gate_attempts` counts every matching `claude_call_start`, including retry-spending attempts. A readable log with no matching starts measures zero; missing or unreadable run-log evidence is unavailable.

- **Keep wall time and cost separate.** `wall_time_ms` comes from the one matching `phase_end.duration_ms` and is unavailable when that event is missing, malformed, or ambiguous. `cost_usd` sums every matching `claude_call_end.cost_usd`, including internal backend retries that can produce multiple end records under one roadmap attempt; it is unavailable when no matching end exists or any matching end lacks a finite numeric cost. Do not reuse `plan_tool/bench.py:_read_log_stats`, which intentionally skips absent values and would change this metric’s unavailable rule.

- **Use stored result facts for the exit metric.** `exit_outcome` reads the stored `RoadmapResult.outcome` and accepts the current `plan_tool/roadmap.py:OUTCOME_*` vocabulary only. A missing or unknown outcome is unavailable; do not infer an outcome from artifact presence or run-log events.

- **Make distances part of each declaration.** Use absolute delta for scalar numeric values, maximum absolute component delta for numeric vectors, symmetric-difference size for `constraint_ids`, and zero-or-one equality distance for booleans and outcomes. A metric distance is unavailable when either side lacks that metric value.

- **Define corpus comparison independently of replay order.** Sort per-item projections by manifest item id before building the corpus vector, then take the maximum item distance for each metric. Require both corpus inputs to name the same item ids rather than zipping unequal vectors. This makes the value stable even when stored evidence arrives in a different capture order.

- **Keep the registry factual and local.** Do not add a quality score, a prose agreement check, a threshold, CLI behavior, persistence, or a backend call. `plan_tool/bench.py:aggregate_run` and `plan_tool/cli/runs.py:_summarize_group` remain separate reporting implementations.

## Tests

Add the following cases in `tests/test_quality_bench_metrics.py`.

### Tests for this step

- `test_registry_v1_has_the_exact_ordered_metric_vocabulary` — Asserts that v1 exposes only the ten planned metric names in Architecture-table order.
- `test_registry_v1_recomputes_the_same_projection_from_identical_stored_bytes` — Computes a projection twice from the same in-memory evidence and gets equal values without reading a path or invoking a backend.
- `test_artifact_bytes_row_counts_and_constraint_ids_use_the_stored_constraints_artifact` — Asserts raw byte length, ordered row counts, and sorted constraint-id set from one stored `02-constraints.md`.
- `test_constraint_ids_are_a_set_while_row_counts_preserve_duplicate_rows` — Pins the different duplicate-row behavior of the id and count metrics.
- `test_domain_reference_counts_include_every_constraint_anchor_and_decision_anchor` — Counts declared and resolved occurrences across entity, business-rule, and workflow ids, including repeats and unresolved ids.
- `test_required_section_presence_reads_raw_list_valued_frontmatter_not_prose_headings` — Rejects prose headings, missing keys, and non-list values as proof that a required collection exists.
- `test_frontmatter_present_allows_only_an_optional_bom_before_the_opening_fence` — Accepts a BOM plus immediate fence and rejects whitespace or a preamble before it.
- `test_missing_or_unparseable_output_is_unavailable_without_substitute_values` — Keeps artifact-derived values unavailable when output is absent or parser-dependent evidence cannot be read.
- `test_roadmap_gate_attempts_count_every_matching_stage_two_call_start` — Counts matching stage-2 starts while ignoring other phases and non-start records.
- `test_wall_time_requires_one_valid_stage_two_phase_end` — Reads the stage duration only from one valid matching phase-end event and marks missing, malformed, or duplicate evidence unavailable.
- `test_cost_sums_all_stage_two_call_ends_and_null_cost_makes_it_unavailable` — Includes internal retry end events in the sum and preserves unavailable cost when evidence is incomplete.
- `test_exit_outcome_uses_the_stored_roadmap_result_vocabulary` — Preserves a supported stored outcome and marks missing or unknown outcomes unavailable.
- `test_metric_distances_follow_the_v1_scalar_vector_set_and_enum_rules` — Pins absolute, maximum-component, symmetric-difference, and zero-or-one distance behavior.
- `test_corpus_distance_sorts_by_item_id_and_uses_the_maximum_item_distance` — Proves capture order does not affect a corpus result and rejects mismatched item-id sets.
- `test_unknown_metric_registry_version_is_rejected_without_fallback` — Prevents callers from silently measuring a different version.

- **Green-before-done gate** — Every test in `tests/test_quality_bench_metrics.py` must pass before this step is complete.

## Acceptance criteria

- Registry v1 exposes exactly the ten planned metrics, each with one deterministic value computation and one distance function.
- The registry computes every available value from stored evidence alone and does not read a live corpus or invoke a backend.
- Absent output or incomplete required evidence produces an explicit unavailable value, never a substitute numeric, collection, boolean, or outcome.
- Domain-reference counts include every declared anchor occurrence and resolve only against stored domain entity, business-rule, and workflow ids.
- Section and fence metrics inspect raw output text rather than prose headings or parser-defaulted empty collections.
- Stage-2 attempts, wall time, and cost use only `stage-2-constraints` run-log records with the stated missing-data behavior.
- Corpus values use manifest item-id order and corpus distance is the maximum matching item distance.
- `tests/test_quality_bench_metrics.py` passes.

## References

- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Read for deterministic decoding of stored JSONL events and serialized result facts.
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Read for the immutable registry, evidence, and computed-value records.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Read for safe parsing of the raw YAML frontmatter mapping used by the section-presence metric.

## Applicable guardrails

- **Deterministic evidence only.** The plan’s `## Plan intent` limits this module to values derived from retained evidence; it must not introduce a model, rubric, or subjective assessment.
- **Fixed registry boundary.** The plan’s `## Step intent` requires one finite v1 vocabulary, stable encodings, and explicit distances; this step must not add an open-ended metric plug-in surface.
- **Reporting-only behavior.** The plan’s `## Out of scope`, behavioral-gate boundary keeps this module from choosing a winner, blocking execution, changing an exit code, or tuning another subsystem.
- **Single replay subject.** The plan’s `## Out of scope`, corpus-scope boundary limits evidence interpretation to the roadmap stage-2 artifacts and events named by this registry.
- **No replay or storage work.** The plan’s `## Out of scope` leaves backend calls, parallelism, artifact persistence, and label replacement behavior outside these two files.

## Deferred

- Replay, scratch materialization, label-owned persistence, and the durable evidence envelope — step 3 owns capture and storage.
- `quality-bench floor` and `quality-bench compare` behavior — steps 5 and 6 consume this registry’s values and distances.
- CLI registration and operator output — step 4 owns the `quality-bench` command surface.
- Consolidating `plan_tool/bench.py:_read_log_stats` or `plan_tool/cli/runs.py:_iter_call_samples` with this registry — those functions serve different report contracts; any shared telemetry-reader refactor needs separate scope.
