> **Withdrawn 2026-08-26** — Superseded by the user-directed smallest-proof seed after repeated granularity split signals were not acted on; its reusable benchmark scope exceeds position 01.
> Preserved here for history; do not edit.

# Step 1 — Parse and version the self-contained quality-bench corpus format, and add roadmap-stage-2 fixtures

## Summary

Create `plan_tool/quality_bench_corpus.py` as the v1 reader for a fixed, self-contained corpus and add two committed roadmap stage-2 inputs under `benchmarks/quality-bench/corpus/roadmap-constraints/`. The key design decision is that validation, byte capture, ordering, and digest generation share one canonical snapshot contract instead of letting later callers rediscover files or hash them differently. Each item declares its stage-2 replay context through a versioned manifest and contains a valid domain artifact with its matching trusted baseline. When green, a caller can load the corpus into an immutable, path-contained snapshot with a stable SHA-256 digest.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the corpus contract and fixtures.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why a dedicated corpus contract is needed now.
- [Input](#input) — Existing roadmap contracts the fixtures must satisfy.
- [Files (creates vs edits)](#files-creates-vs-edits) — New module, fixtures, and test file.
- [Implementation](#implementation) — Required v1 manifest, safety, ordering, and snapshot behavior.
- [Tests](#tests) — Unit and fixture checks that define completion.
- [Acceptance criteria](#acceptance-criteria) — Observable completed-step outcomes.
- [References](#references) — Standard-library format references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this step.
- [Deferred](#deferred) — Nearby code that remains outside this step.

## Why

No checked-in contract currently defines which files form one quality-bench replay input or gives those inputs a stable byte identity. `plan_tool/bench.py:corpus_hash` recursively hashes a different synthetic benchmark corpus with a different digest protocol, while `plan_tool/roadmap.py:run_roadmap` requires a readable brief and an admitted stage-1 source before it can select stage 2. This step makes those replay inputs explicit and committed so later replay and floor work cannot depend on ambient repository files or filesystem traversal order.

## Input

- **Roadmap stage selection.** `plan_tool/roadmap.py:STAGES` defines the stage-2 `RoadmapStage` entry, and `plan_tool/roadmap.py:run_roadmap` uses `from_stage` to re-admit stages below the selected stage before it runs the target.
- **Domain artifact contract.** `plan_tool/roadmap_artifacts.py:DOMAIN_FILENAME`, `plan_tool/roadmap_artifacts.py:load_domain_artifact`, and `plan_tool/roadmap_artifacts.py:render_domain_artifact` define the `01-domain.md` bytes the fixtures provide.
- **Trusted source contract.** `plan_tool/roadmap_source_identity.py:baseline_path`, `plan_tool/roadmap_source_identity.py:load_baseline_record`, and `plan_tool/roadmap_source_identity.py:compare_baseline` define the baseline sidecar that must bind the fixture’s slug and domain stage.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/quality_bench_corpus.py` — Versioned corpus loader, validation, canonical snapshot, and digest contract.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-1/brief.md` — First fixed concept brief.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-1/01-domain.md` — First admitted stage-1 domain artifact.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-1/.roadmap-baselines/domain.json` — Trusted baseline for the first domain artifact.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-1/manifest.json` — First v1 corpus-item declaration.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-2/brief.md` — Second fixed concept brief.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-2/01-domain.md` — Second admitted stage-1 domain artifact.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-2/.roadmap-baselines/domain.json` — Trusted baseline for the second domain artifact.
  - `benchmarks/quality-bench/corpus/roadmap-constraints/item-2/manifest.json` — Second v1 corpus-item declaration.
  - `tests/test_quality_bench_corpus.py` — Corpus-contract and committed-fixture tests.
- **Existing files (edits only):**
  - None.

## Implementation

- **Make `plan_tool/quality_bench_corpus.py` the single v1 corpus contract.** Expose one loader that validates the full corpus before returning item records and canonical snapshot bytes. Keep the item and snapshot values immutable so the step-3 replay engine can materialize from captured bytes rather than reread the source directory.

- **Settle the v1 manifest fields.** Use JSON fields named `format_version`, `id`, `roadmap_slug`, `target_stage`, `brief_path`, `domain_path`, and `domain_baseline_path`. Require `format_version` and `target_stage` to be JSON integers, rejecting booleans; v1 accepts only `format_version: 1` and `target_stage: 2`. Validate `roadmap_slug` before any scratch path is formed with the shared single-component contract: it is nonempty, contains neither `/` nor `\\`, has no `..` component, and `Path(slug).parts == (slug,)`; extract or expose the same validation `roadmap_artifacts.roadmap_dir` uses rather than waiting for `run_roadmap`.

- **Treat the item id as the durable corpus key.** Require a nonempty lower-case `id` matching `[a-z0-9][a-z0-9._-]{0,127}`, and reject duplicate ids across the complete corpus. Preserve the id on each loaded item for later evidence names and metric-vector ordering; do not derive that key from the directory name.

- **Discover only the v1 item set.** Strictly resolve the selected corpus directory, require a directory, select its non-hidden immediate child directories only, and sort them by UTF-8 name. Ignore nested directories as items, but reject a selected item directory or its `manifest.json` when its resolved target leaves the resolved corpus root.

- **Validate every declared input path before any snapshot is returned.** Each of the three path fields must be nonempty, relative, and free of a `..` component. Require each target to exist and strictly resolve beneath its resolved item directory, including after following symlinks; reject absolute, missing, traversal, and escaping references rather than skipping them.

- **Capture the corpus as bytes, not parsed prose.** The canonical snapshot must contain each enumerated manifest and its declared input files, keyed by their lexical POSIX-relative paths and sorted by that path. Preserve raw file bytes so later replay can copy exactly what passed preflight; this loader must not compare a brief to a domain artifact or make any quality judgment.

- **Use the fixed v1 digest encoding.** Hash the ASCII domain separator `quality-bench-corpus-v1\0`, then each snapshot path and byte value as length-prefixed records: unsigned 64-bit big-endian path-byte length, UTF-8 POSIX path bytes, unsigned 64-bit big-endian value length, and raw value bytes. Return the full SHA-256 hex digest and lock it with a golden vector; do not reuse `plan_tool/bench.py:corpus_hash`, whose recursive traversal and truncated null-delimited digest serve a different format.

- **Build committed replay-ready fixtures.** Give both manifests distinct valid ids and slugs, target stage 2, and item-relative declarations for their brief, domain artifact, and baseline. Make each `01-domain.md` parse through `plan_tool/roadmap_artifacts.py:load_domain_artifact`, and make each paired baseline load through `plan_tool/roadmap_source_identity.py:load_baseline_record` with no difference from the parsed domain artifact. Do not add generated stage-2 output files; step 3 owns replay output.

- **Keep scope at the corpus boundary.** This step must not call `plan_tool/roadmap.py:run_roadmap`, add a CLI command, calculate metrics, or create storage under `.plan-tool/`. `plan_tool/pathutil.py:is_within` is a suitable existing resolved-containment predicate if it fits the loader’s strict-existence checks.

## Tests

Add the following cases in `tests/test_quality_bench_corpus.py`.

### Tests for this step

- `test_loads_committed_roadmap_constraints_corpus` — Loads `benchmarks/quality-bench/corpus/roadmap-constraints/`, returns the two committed v1 items in UTF-8 directory order, and exposes their distinct valid ids.
- `test_committed_fixture_domain_and_baseline_are_admitted` — Parses each committed domain artifact, loads its baseline with the manifest slug and `domain` stage key, and finds no baseline difference.
- `test_discovers_only_nonhidden_immediate_item_directories_in_utf8_order` — Ignores hidden and nested directories while making enumeration independent of filesystem listing order.
- `test_rejects_non_directory_root_and_item_or_manifest_that_escapes_root` — Rejects an unusable corpus root plus item-directory and manifest symlinks that resolve outside the selected root.
- `test_rejects_missing_boolean_noninteger_and_unknown_format_versions` — Requires the exact JSON-integer v1 `format_version` before producing a corpus result.
- `test_rejects_manifest_without_v1_stage_two_replay_context` — Rejects missing or wrong `target_stage` and missing required replay-context declarations.
- `test_rejects_unsafe_roadmap_slug_before_snapshot_or_scratch_path` — Rejects an empty, separator-bearing, traversal-bearing, or multi-component `roadmap_slug` before the loader returns a snapshot or step 3 can form a scratch roadmap path.
- `test_rejects_invalid_and_duplicate_item_ids_before_snapshot` — Rejects empty, upper-case, path-like, overlong, and duplicate ids.
- `test_rejects_unsafe_or_unavailable_declared_input_paths` — Rejects empty, absolute, traversal, missing, and symlink-escaping input references.
- `test_snapshot_contains_only_declared_files_in_lexical_posix_order` — Captures manifests and declared inputs only, with their raw bytes ordered by POSIX-relative path.
- `test_snapshot_digest_uses_v1_separator_and_u64_length_framing` — Matches a fixed golden SHA-256 vector and distinguishes otherwise ambiguous concatenations.
- `test_loaded_snapshot_keeps_original_bytes_after_corpus_changes` — Proves the returned snapshot remains usable after the source files change.
- **Green-before-done gate** — Every test in `tests/test_quality_bench_corpus.py` must pass before this step is complete.

## Acceptance criteria

- Loading a valid corpus returns only its resolved root’s non-hidden immediate child directories, in UTF-8 name order, with unique valid item ids.
- A v1 manifest accepts only JSON-integer `format_version: 1` and `target_stage: 2`, a nonempty single-component roadmap slug, and all three required item-relative input paths.
- Any escaping item, manifest, or declared input path fails before the loader returns a snapshot.
- The snapshot contains exactly the validated manifests and declared input bytes in lexical POSIX-relative-path order, and its digest matches the specified length-framed SHA-256 encoding.
- Both committed fixture items provide a readable brief, a parsable domain artifact, and a matching trusted domain baseline.
- `tests/test_quality_bench_corpus.py` passes.

## References

- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Read for strict JSON manifest parsing and type handling.
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Read for immutable corpus-item and snapshot records.

## Applicable guardrails

- **Deterministic evidence only.** The plan’s `## Plan intent` limits this step to fixed replay inputs and their byte identity; it must not add a metric, verdict, or quality assessment.
- **V1 corpus boundary.** The plan’s `## Step intent` requires the version, containment, item-key, ordering, and snapshot rules to be enforced before a later replay can start.
- **No execution or evaluation surface.** The plan’s `## Out of scope` keeps backend calls, CLI behavior, gates, comparisons, and prompt-variant work outside this step.
- **Single-verb fixture scope.** The plan’s `## Out of scope` keeps the committed corpus focused on the roadmap stage-2 route rather than adding other verb families.

## Deferred

- Consolidating corpus containment or digest behavior with `plan_tool/roadmap_artifacts.py:resolve_draft_seed_path` or `plan_tool/bench.py:corpus_hash` — those helpers serve different contracts; changing them would widen this feature step.
