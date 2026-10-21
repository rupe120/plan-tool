> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 6 — Add `plan-tool quality-bench compare` — print each metric's delta against its recorded floor as inside noise, outside noise, or unfloored

## Summary

Extend `plan_tool/quality_bench.py` with a read-only comparison workflow and `plan_tool/cli/quality_bench_cmd.py` with `quality-bench compare`. The command recomputes one selected metric-registry version from stored baseline, candidate, and floor-sample evidence, then prints each registered distance beside its matching floor and classification. The key design decision is to classify only a coherent, identity-compatible optimistic read; missing or incompatible evidence stays explicit as `unfloored`. When green, a successful comparison exits zero and reports factual metric results without judging either label’s quality.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the comparison command and its result.
- [Table of Contents](#table-of-contents) — Links to every top-level section.
- [Why](#why) — Why stored metric distances need their measured rerun spread.
- [Input](#input) — Upstream label, floor, registry, and CLI contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New focused tests and the two edited modules.
- [Implementation](#implementation) — Comparison, identity, snapshot, and CLI requirements.
- [Tests](#tests) — Hermetic cases that pin compare behavior.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-step outcomes.
- [References](#references) — Standard-library references for records and command parsing.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that keep compare factual and read-only.
- [Deferred](#deferred) — Related work outside this comparison step.

## Why

`plan_tool/bench.py:build_quality_report` compares a separate backend matrix and has no label-owned corpus identity or rerun floor. Without this command, the stored metrics from steps 2, 3, and 5 remain bare distances that can make ordinary rerun variation look meaningful. Compare makes the existing evidence readable without reopening a corpus, running a backend, or turning a measurement into a quality decision.

## Input

- **Step 2 metric registry.** Use step 2’s completed version lookup, ordered declarations, value encoding, and per-metric distance functions. Its public names and signatures are authoritative; an unknown `--metric-version` must not fall back to another version.

- **Step 3 label evidence.** Read the immutable label generation selected by its logical-label marker. Recompute selected-version values only from its retained corpus snapshot, artifacts, run-log bytes, and serialized result facts.

- **Step 4 command and lock contract.** Extend `plan_tool/cli/quality_bench_cmd.py:register` and `cmd_quality_bench` under the dedicated `quality_bench_action` destination. Step 4’s `plan_tool/cli/app.py:_requires_repo_mutation_lock` policy keeps `compare` read-only.

- **Step 5 floor evidence.** Read the selected immutable `floor-record`, its retained raw samples, and the matching `current-floor-pointer` when `--floor-id` is absent. The floor record supplies the baseline identity and the evidence needed to rederive a later registry version.

- **Persisted-record boundary.** Accept only the landed version-1 label, full-corpus raw-sample, floor-record, current-floor-pointer, current-label-pointer, and replacement-journal forms. Verify each current-label pointer’s capture id and digest before loading a generation; a malformed, unsupported, or invalid-reference selected record is a command error before classification, while a valid but absent or incompatible record produces `unfloored` results. Compare never recovers or mutates a replacement journal.

## Files (creates vs edits)

- **New files:**
  - `tests/test_quality_bench_compare.py` — Hermetic engine and CLI tests for comparison, identity matching, floor selection, and optimistic reads.

- **Existing files (edits only):**
  - `plan_tool/quality_bench.py` — Add read-only label/floor selection, selected-version recomputation, marker-verified snapshot reads, metric classification, and comparison result rendering data.
  - `plan_tool/cli/quality_bench_cmd.py` — Register and dispatch `quality-bench compare`, validate its inputs, call the engine, and print factual results.

## Implementation

- **Foundational logic: identity-compatible distance classification.** Add one read-only engine entrypoint in `plan_tool/quality_bench.py` that compares a baseline label and candidate label through the selected registry declaration. For every metric, use that declaration’s distance function for both the reported delta and the comparison to its floor; do not derive a generic difference from serialized metric values.

- **Select one registry version.** Add `quality-bench compare <baseline-label> <candidate-label> [--metric-version <V>] [--floor-id <id>]` beneath `quality_bench_action` in `plan_tool/cli/quality_bench_cmd.py:register`. Use the current registry version when the flag is absent, and reject an unknown explicit version rather than reading cached values from another projection.

- **Validate keys before lookup.** Validate both labels and an explicit floor id with the safe-key rules that steps 3 and 5 land before forming a store path or loading evidence. The handler must resolve the repository through `plan_tool/cli/context.py:_resolve_cmd_repo_root` and leave label validation, store lookup, and record validation in the engine.

- **Recompute from retained evidence.** Recompute the selected version for both labels and every complete full-corpus floor raw sample. Read each sample’s manifest-id-keyed item map; do not trust a label’s stored projection as the comparison source, read a live corpus, reopen a scratch directory, or invoke a backend. This keeps an explicit later registry version meaningful for historical captures.

- **Match the required identities.** Classify only when baseline and candidate label evidence has the same frozen corpus-snapshot digest, replay identity, and canonical backend-profile digest. The selected floor must match those values and the baseline label’s full source execution identity. A candidate source revision may differ from the baseline; do not require candidate source identity equality.

- **Resolve the floor without fallback.** With no `--floor-id`, read the one current-floor pointer for the exact baseline identity and then its immutable floor record. With `--floor-id`, use only that immutable record. A missing pointer, absent explicit id, incompatible record, or a metric explicitly marked `unfloored` must remain `unfloored`; never search an older floor or metric projection.

- **Use the exact classification boundary.** Report `inside noise` when an available metric distance is less than or equal to its rederived floor. Report `outside noise` only when it is greater. Report `unfloored` when either label value, the selected-version floor value, or required compatible evidence is unavailable.

- **Take one coherent optimistic snapshot.** Read baseline and candidate current-label pointers, verify and resolve their immutable capture generations, then read the chosen floor marker. Load only that evidence and reread the identical pointers, generation markers, and floor marker before classifying. Retry a moved marker set at most three times and discard the whole attempt each time. If no attempt stabilizes, return one normal command error with no partial table or summary.

- **Keep comparison read-only.** Do not update a label marker, floor pointer, record, recovery journal, or directory. Do not take the repository mutation lock, and do not reuse `plan_tool/roadmap_revision_publish.py:roadmap_reader_guard`, whose writer-serialization contract does not match this bounded optimistic read.

- **Render measurement facts only.** Print the baseline label, candidate label, selected metric version, and resolved floor id, or explicitly state that no compatible floor was selected. Render every registry metric with its distance, floor when available, and one of the three required classifications. Exclude `unfloored` rows from any summary, and keep summaries limited to reported classifications rather than a score, winner, recommendation, or gate.

- **Keep the CLI handler thin.** Let `plan_tool/cli/quality_bench_cmd.py:cmd_quality_bench` parse and render only. It must not recreate record readers, identity checks, registry calculations, floor selection, or retry logic, and it must preserve ordinary command-error handling for malformed evidence or an unstable read.

## Tests

### Tests for this step

- `test_compare_registers_read_only_baseline_candidate_and_selection_arguments` — The parser accepts two labels plus optional `--metric-version` and `--floor-id` under `quality_bench_action`.

- `test_compare_validates_labels_and_explicit_floor_id_before_store_lookup` — Unsafe keys fail before any evidence path is read.

- `test_compare_uses_current_registry_version_when_metric_version_is_omitted` — The command selects the landed current version by default.

- `test_compare_rejects_unknown_metric_version_without_projection_fallback` — An unsupported version returns a command error and never uses cached or v1 metric values.

- `test_compare_recomputes_labels_and_floor_samples_from_retained_evidence` — Deleting or changing cached projections does not change a selected-version result derived from retained raw evidence.

- `test_compare_uses_each_registry_distance_for_delta_and_floor_classification` — Numeric, vector, set, boolean, and outcome metrics use their own declaration distance rather than one generic subtraction rule.

- `test_compare_distance_equal_to_floor_is_inside_noise` — A distance exactly equal to its available floor renders `inside noise`.

- `test_compare_distance_greater_than_floor_is_outside_noise` — A larger available distance renders `outside noise`.

- `test_compare_requires_matching_corpus_replay_and_backend_profile_identities` — Any valid label mismatch produces `unfloored` rows and no classified summary.

- `test_compare_requires_floor_to_match_baseline_source_identity_only` — A floor with a different baseline source identity is unfloored, while a different candidate source identity remains comparable.

- `test_compare_uses_only_the_matching_current_floor_or_explicit_floor_id` — Default selection follows the exact current pointer, and an explicit missing or incompatible id does not fall back to another floor.

- `test_compare_preserves_explicit_unfloored_and_selected_version_unavailable_metrics` — A floor’s explicit unavailable entry or an uncomputable selected-version value renders that metric `unfloored` without substituting a value.

- `test_compare_rejects_malformed_selected_evidence_before_classification` — Unsupported envelope versions or kinds return an error with no metric table or summary.

- `test_compare_rejects_invalid_current_label_pointer_before_loading_a_generation` — A missing, malformed, unsupported, or digest-mismatched current-label pointer returns a command error before it follows a capture id or emits a classification.

- `test_compare_retries_moved_markers_and_classifies_only_a_coherent_snapshot` — Interleaved label replacement or floor-pointer movement either stabilizes to one complete evidence set or retries without mixing generations.

- `test_compare_reports_concurrent_publication_after_three_unstable_reads` — Three unstable attempts return one command error and emit no partial classification or summary.

- `test_compare_prints_every_metric_version_floor_and_factual_summary_at_exit_zero` — A completed comparison prints each result, selected version, resolved floor id, and an unfloored-excluding summary while returning zero.

- `test_compare_does_not_take_the_repo_mutation_lock_or_invoke_a_backend` — The CLI comparison path remains read-only and uses stored evidence only.

Every test in `tests/test_quality_bench_compare.py` must be green before this step is complete.

## Acceptance criteria

- `plan-tool quality-bench compare <baseline-label> <candidate-label>` compares the current registry version from retained evidence without a backend call.

- `--metric-version` selects exactly one supported registry version, and an unknown version fails without a fallback.

- `--floor-id` selects only the named immutable floor record; default selection uses the matching baseline current-floor pointer.

- Available metric distances at or below their matching floor render `inside noise`, and larger distances render `outside noise`.

- A missing, incompatible, explicitly unavailable, or selected-version-uncomputable metric renders `unfloored` and is absent from the summary.

- Baseline and candidate labels must match corpus-snapshot digest, replay identity, and backend-profile digest; only the floor must also match the baseline full source execution identity.

- Compare takes at most three marker-verified optimistic reads and produces no partial result when concurrent publication prevents a stable snapshot.

- The command changes no store state, takes no repository mutation lock, returns zero for a completed measurement, and changes no existing gate or exit-code rule.

- `tests/test_quality_bench_compare.py` passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3/library/json.html) — Read for strict versioned evidence decoding.

- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — Read for immutable comparison rows and result records.

- [argparse — Parser for command-line options, arguments and sub-commands](https://docs.python.org/3/library/argparse.html) — Read for the nested compare parser and optional selectors.

## Applicable guardrails

- **The plan’s “## Step intent”, measured-floor classification.** `plan_tool/quality_bench.py` must use only the selected registry distance and matching floor for the three required result states.

- **The plan’s “## Architecture”, coherent evidence reads.** Compare must use the bounded marker-verified snapshot and return no mixed-generation result during concurrent publication.

- **The plan’s “## Out of scope”, deterministic measurement boundary.** These files may not add a model judge, rubric, control arm, tuning path, or expanded replay subject.

- **The plan’s “## Out of scope”, report-only behavior.** Comparison output must not rank labels, state a quality opinion, block work, alter a gate, or change successful exit behavior.

- **The plan’s “## Risks”, manual interpretation.** Render the evidence needed for human review without converting a wide floor or outside-noise result into an automatic warning or decision.

## Deferred

- Changes to `plan_tool/bench.py:build_quality_report` or the existing `bench` command module — The existing backend benchmark has a different corpus and storage contract; consolidation needs separate refactor planning.

- New metric definitions or registry versions — Step 2 owns metric semantics; this step selects and recomputes versions that have already landed.

- Long-form quality-bench storage and output documentation — Step 7 owns the documentation surface.
