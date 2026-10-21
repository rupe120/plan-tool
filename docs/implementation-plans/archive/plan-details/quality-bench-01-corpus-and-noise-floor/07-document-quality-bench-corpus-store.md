> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 7 — Document the quality-bench corpus/store schema and correct BACKLOG

## Summary

Create `docs/QUALITY_BENCH_CORPUS_FORMAT.md` as the human reference for the v1 corpus and metric boundary. Update `DATA_CONTRACT.md` with the persisted quality-bench store records and reader outcomes, and add the landed `plan_tool/quality_bench.py` invoker seam to `TESTING.md`. Correct BACKLOG #216 to name the separate `quality-bench` command, its modules, and `/.plan-tool/quality-bench/` store. On green, the documented contract matches the completed steps 1–6 without changing runtime behavior.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog correction.
- [Table of Contents](#table-of-contents) — Links to each section in this file.
- [Why](#why) — Why the persisted evidence and command boundary need a durable reference.
- [Input](#input) — Upstream corpus, store, metric, CLI, and test-seam contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation created and updated by this step.
- [Implementation](#implementation) — Required ownership split, schema coverage, and correction rules.
- [Tests](#tests) — Existing upstream contract tests and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-document outcomes.
- [References](#references) — Standard-library references for the stored JSON forms.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain the documentation.

## Why

`DATA_CONTRACT.md` documents current runtime stores but has no quality-bench evidence section, `TESTING.md:Backend fallback seams` has no quality-bench replay seam, and BACKLOG #216 still describes this lane as the existing `bench` command family and its storage root. That leaves readers unable to distinguish the fixed roadmap corpus from the synthetic backend benchmark in `plan_tool/bench.py:BENCH_RUNS_REL` and `plan_tool/cli/bench_cmd.py:register`, or to determine which stored evidence is safe to compare.

## Input

- **Corpus contract.** Step 1 supplies the landed v1 manifest reader and committed fixtures under `benchmarks/quality-bench/corpus/`; use its implemented field names, containment rules, ordering, and snapshot digest as the corpus reference source.

- **Metric contract.** Step 2 supplies the landed registry-v1 declaration in `plan_tool/quality_bench_metrics.py`. Its ordered vocabulary and unavailable-value behavior are the source for the metric overview.

- **Persisted evidence.** Steps 3 and 5 supply the landed label, full-corpus raw-sample, floor-record, current-floor-pointer, current-label-pointer, and replacement-journal readers and writers in `plan_tool/quality_bench.py`. Document the fields and paths the code writes, not names proposed by this plan.

- **Command behavior.** Steps 4 and 6 supply the completed `quality-bench` command group and comparison outcomes. Keep the existing `plan_tool/cli/bench_cmd.py:register` contract separate.

- **Documentation conventions.** Follow `DATA_CONTRACT.md:Version-evolution policy`, `plan_tool/data_contract.py:json_object_contracts`, `tests/test_data_contract.py:test_data_contract_doc_exists`, and `TESTING.md:Backend fallback seams`.

## Files (creates vs edits)

- **New files:**
  - `docs/QUALITY_BENCH_CORPUS_FORMAT.md` — Source-of-truth reference for the v1 corpus input, deterministic metric boundary, and quality-bench command relationship.

- **Existing files (edits only):**
  - `DATA_CONTRACT.md` — Add the persisted quality-bench store location, version-1 record kinds, required record content, and fail-closed reader outcomes.
  - `TESTING.md` — Add the landed quality-bench replay/floor `invoker=` seam to the backend fallback table.
  - `BACKLOG.md` — Correct only #216’s command, module, and storage references to the shipped quality-bench lane.

## Implementation

- **Foundational logic: fail-closed versioned evidence documentation.** Document the boundary between usable v1 evidence, absent evidence, and malformed or unsupported evidence. The reference must make clear that readers accept only the landed schema version and expected record kind, never infer an upgrade or substitute another record.

- **Keep one owner per fact class.** Make `docs/QUALITY_BENCH_CORPUS_FORMAT.md` own the authored corpus format, corpus snapshot identity, registry-v1 overview, and operator-facing command relationship. Make `DATA_CONTRACT.md` own the durable store’s serialized record fields and reader outcomes. Link between the two instead of copying field tables into both documents.

- **Use the format-document source-of-truth pattern.** Start `docs/QUALITY_BENCH_CORPUS_FORMAT.md` with a short code-wins notice naming the landed `plan_tool/quality_bench_corpus.py`, `plan_tool/quality_bench_metrics.py`, and `plan_tool/quality_bench.py` anchors. Read their public names at implementation time; do not preserve names from an earlier detail if the landed code differs.

- **Describe the corpus as a self-contained v1 input.** Cover the selected corpus root, non-hidden immediate item-directory selection, manifest version and safe item identity, item-relative input files, containment validation, and canonical snapshot ordering. Record the v1 digest framing at the level needed to reproduce identity from stored bytes. Refer to the committed corpus fixtures rather than adding an unverified copy-paste manifest example.

- **List the fixed metric boundary.** In `docs/QUALITY_BENCH_CORPUS_FORMAT.md`, list the landed registry-v1 metrics in declaration order: `artifact_bytes`, `row_counts`, `constraint_ids`, `domain_reference_counts`, `required_section_presence`, `frontmatter_present`, `roadmap_gate_attempts`, `exit_outcome`, `wall_time_ms`, and `cost_usd`. State that values come from retained evidence, unavailable values remain explicit, and distances are measurements rather than quality judgments.

- **Document every v1 store record in `DATA_CONTRACT.md`.** Add a quality-bench evidence-store section for `/.plan-tool/quality-bench/` that covers `schema_version: 1` and the closed `record_kind` values `label`, `raw-sample`, `floor-record`, `current-floor-pointer`, `current-label-pointer`, and `label-replacement-journal`. Define a raw sample as one complete `(floor_id, sample_ordinal)` corpus capture with a manifest-id-keyed item map. For each landed envelope, provide its path role, identity fields, immutable evidence or pointer target, and integrity data needed by its reader; the label pointer must carry and verify its capture id/digest and the journal its old/new ids/digests and archive slot.

- **Preserve reader distinctions.** Document the landed result for a missing label or pointer, a missing or incompatible floor, an unavailable metric value, and malformed or unknown-version evidence. Missing compatible floor evidence and unavailable metric values must remain distinct from rejected evidence, and no outcome may silently select an older record or cached metric projection.

- **State the identity and publication invariants.** Describe that stored labels and floor samples bind corpus, replay, source, and backend-profile identities; logical labels and floor selection use immutable records plus pointers; and comparison reads retained evidence rather than a live corpus or scratch directory. Do not document raw sensitive backend arguments when the landed store records only safe display data and digests.

- **Add the test seam where contributors look for it.** Add one `TESTING.md:Backend fallback seams` row for the landed quality-bench capture and floor entry points. Name their default route through the roadmap invoker, require callers to pass the optional `invoker=` fake in tests, and direct read-only comparison tests to use stored evidence with a fail-on-call fake. Keep the row aligned with `plan_tool/roadmap.py:run_roadmap` instead of inventing a second backend-testing pattern.

- **Correct #216 as a bounded terminology sweep.** In `BACKLOG.md` under the `#216` heading’s What, stage arc, Scope contract, and allowed-behavior statements, name `quality-bench run`, `quality-bench floor`, and `quality-bench compare`; `plan_tool/quality_bench.py`; `plan_tool/cli/quality_bench_cmd.py`; and `/.plan-tool/quality-bench/`. Preserve references to the existing `bench` command only when they refer to its separate synthetic benchmark.

## Tests

- `tests/test_quality_bench_corpus.py:test_loads_committed_roadmap_constraints_corpus` — Confirms the documented corpus fixtures remain valid v1 inputs.

- `tests/test_quality_bench.py:test_label_envelope_retains_item_inputs_outputs_run_log_and_result_facts` — Confirms the label evidence the data-contract section describes remains retained.

- `tests/test_quality_bench_floor.py:test_floor_stages_one_versioned_full_corpus_raw_sample_per_completed_rerun` — Confirms raw-sample version, `(floor_id, sample_ordinal)`, and full-corpus identity behavior.

- `tests/test_quality_bench_floor.py:test_floor_record_and_current_pointer_use_version_one_envelopes` — Confirms the documented floor record and pointer kinds.

- `tests/test_quality_bench_compare.py:test_compare_rejects_malformed_selected_evidence_before_classification` — Confirms unsupported selected evidence stays fail-closed.

- `tests/test_quality_bench_compare.py:test_compare_rejects_invalid_current_label_pointer_before_loading_a_generation` — Confirms an invalid label pointer never selects a capture generation.

- `tests/test_quality_bench.py:test_recovery_completes_a_valid_journaled_transition` and `test_recovery_restores_old_generation_from_a_partial_transition` — Confirm the documented replacement journal preserves a complete readable generation through recovery.

- `tests/test_quality_bench_compare.py:test_compare_uses_only_the_matching_current_floor_or_explicit_floor_id` — Confirms missing or incompatible floor selection does not fall back.

### Verification (non-code step)

1. The plan marks this step `change_type: non-code`, so the test-authoring gate does not apply; add no production or test code.

2. Run `uv run pytest tests/test_data_contract.py -q` and the focused quality-bench suites created by steps 1–6.

3. Check every code symbol cited by `DATA_CONTRACT.md`, `TESTING.md`, and `docs/QUALITY_BENCH_CORPUS_FORMAT.md` against the landed modules with `rg`.

4. Compare each documented envelope table with the landed reader and writer shapes, including missing, malformed, unsupported, and incompatible evidence outcomes.

5. Search only BACKLOG #216 for quality-bench references and confirm the new lane no longer uses `bench` terminology or `/.plan-tool/bench/` as its own surface.

## Acceptance criteria

- `docs/QUALITY_BENCH_CORPUS_FORMAT.md` identifies its enforcing modules, documents the v1 corpus boundary, and links durable-store details to `DATA_CONTRACT.md`.

- `docs/QUALITY_BENCH_CORPUS_FORMAT.md` lists every landed registry-v1 metric in declaration order and describes explicit unavailable values without assigning a quality score or verdict.

- `DATA_CONTRACT.md` documents `/.plan-tool/quality-bench/`, schema version 1, and all six closed record kinds — `label`, `raw-sample`, `floor-record`, `current-floor-pointer`, `current-label-pointer`, and `label-replacement-journal` — with their landed identity, evidence, or pointer fields.

- `DATA_CONTRACT.md` distinguishes missing or incompatible usable evidence from malformed or unsupported evidence and states that readers do not upgrade or fall back.

- `TESTING.md:Backend fallback seams` tells a contributor how to inject the quality-bench `invoker=` seam without a live backend call.

- BACKLOG #216 names the separate `quality-bench` command family, `plan_tool/quality_bench.py`, `plan_tool/cli/quality_bench_cmd.py`, and `/.plan-tool/quality-bench/`, while preserving the existing synthetic `bench` family as separate.

- `uv run pytest tests/test_data_contract.py -q` and the focused quality-bench contract suites pass.

## References

- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Use for documenting strict JSON envelope and version parsing rules.

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Use for the immutable evidence and result-record terminology used by the landed modules.

## Applicable guardrails

- **The plan’s “## Step intent”, documentation ownership.** Record the completed v1 contract from steps 1–6 without introducing a new schema, reader rule, or command behavior.

- **The plan’s “## Out of scope”, reporting-only boundary.** Describe factual measurements and their stored evidence without adding a quality opinion, decision surface, or gate through documentation.

- **The plan’s “## Out of scope”, fixed replay scope.** Keep the reference limited to the quality-bench corpus and command family named by this plan; do not fold in the existing synthetic benchmark.

- **The plan’s “## Out of scope”, no automatic response to results.** Document the existing manual interpretation boundary without presenting metrics or floors as an automatic action.
