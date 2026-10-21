> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Extract recorded-brief readers and preserve source.json replacement

## Summary

Create `plan_tool/roadmap_source.py` as the shared recorded-brief read and text-digest boundary, with a separate raw source-record byte reader and digest for immutable impact evidence. Refactor `plan_tool/roadmap.py` to use the broad-compatible path/text operations while retaining the existing source-selection timing, error categories, run-log facts, and `source.json` write path. Keep `source.json` replacement in `plan_tool/roadmap.py:_write_brief_source` unchanged. Green means snapshot code can read the same resolved brief path and decoded-text digest as broad roadmap execution while binding exact raw source-record bytes without importing the orchestrator.

## Table of Contents

- [Summary](#summary) — The completed refactor and preserved behavior.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why recorded-brief reads need a shared boundary.
- [Input](#input) — Existing source-record and broad-run contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New shared reader and targeted orchestrator edit.
- [Implementation](#implementation) — Reader contract, compatibility rules, and import boundary.
- [Tests](#tests) — Focused reader and broad-compatibility coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — JSON and digest behavior references.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries for this refactor.
- [Deferred](#deferred) — Later snapshot and analysis work.

## Why

`plan_tool/roadmap.py` currently owns the recorded-source lookup, brief text read, and digest logic as private helpers. Step 4 needs those exact rules while holding a coherent snapshot, and copying them would risk different relative-path handling, text decoding, or digest values. A small shared reader keeps broad execution and later snapshot code grounded in the same source contract without widening roadmap behavior.

## Input

- **Recorded-source path:** Read `source.json` through `plan_tool/roadmap_artifacts.py:brief_source_path`. Its current payload contains one non-empty `brief_path` string.

- **Broad source flow:** Preserve `plan_tool/roadmap.py:_resolve_brief_path` as the owner of first-run versus recorded-source selection, including the `record_brief_source` result that controls when a record is written.

- **Broad text and digest contract:** Match `plan_tool/roadmap.py:_read_brief` and `_artifact_digest`: decode through `Path.read_text(encoding="utf-8")`, then calculate SHA-256 from the decoded text encoded as UTF-8. This remains the recorded brief digest; it is not the source-record digest.

- **Compatibility coverage:** Keep the source and re-entry behavior covered by `tests/test_roadmap.py:TestInputsAndSeams` while adding focused contract cases in `tests/test_roadmap_source.py`.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_source.py` — Provide the recorded-source byte/path reader, brief text reader, raw-byte source-record digest, and shared decoded-text brief digest without importing the roadmap orchestrator.
  - `tests/test_roadmap_source.py` — Cover source-record parsing and exact raw-byte binding, path resolution, decoded-text digest behavior, failure boundaries, and leaf imports.

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — Replace private recorded-brief read and digest implementations with the shared source contract. Keep `_resolve_brief_path`, `_write_brief_source`, and the first-successful-artifact write timing intact.

## Implementation

- **Extract the reader contract, not broad-run policy.** Add narrow read and digest entry points in `plan_tool/roadmap_source.py` for the existing behavior in `plan_tool/roadmap.py:_load_recorded_brief_path`, `_read_brief`, and `_artifact_digest`, plus an impact-only raw source-record byte reader. Keep source selection, CLI advice, stage execution, retries, and run-log sequencing in `plan_tool/roadmap.py`.

- **Keep lookup and content reads separate.** A missing or non-file `source.json` remains an explicit absence, while a malformed record remains an error. Do not combine source lookup with brief-content loading: `plan_tool/roadmap.py:_run_roadmap` must continue to distinguish `brief_source` preflight failure from `brief_read` preflight failure.

- **Preserve path interpretation.** Read `brief_path` from `source.json` exactly as today: resolve a relative reference against the supplied repository root and retain an absolute reference. Do not add new path normalization, containment checks, or source-record schema fields in this refactor.

- **Preserve decoded-text hashing.** Digest the UTF-8 decoded text with the same SHA-256 rule that `plan_tool/roadmap.py:_artifact_digest` uses. Do not switch to `read_bytes`, a raw-byte digest, or a renderer-normalized value; newline handling and invalid UTF-8 behavior must remain broad-equivalent.

- **Add a separate exact source-record binding.** For impact analysis only, read `source.json` once as raw bytes, parse those same bytes under the existing source-record schema, and compute `sha256(raw_bytes)`. Preserve this digest separately from the decoded-text brief digest: a whitespace-only or newline-only source-record change is a changed impact input even when it resolves to the same brief path. Do not change broad execution to use this digest or raw-byte behavior.

- **Retain broad errors at the orchestrator boundary.** Let `plan_tool/roadmap_source.py` stay independent of `plan_tool/roadmap.py:RoadmapError`. Adapt source-reader failures at the existing broad-run call sites so `plan_tool/roadmap.py:_resolve_brief_path` and `_run_roadmap` keep their current operator-facing failure behavior.

- **Preserve `source.json` replacement.** Leave `plan_tool/roadmap.py:_write_brief_source` as the writer. It must keep the one-key `brief_path` payload, portable reference rendering through `_brief_reference`, and `plan_tool/fileio.py:atomic_write_text` replacement behavior. `_run_roadmap` must still call it only after the first successful artifact write.

- **Keep the new module below orchestration.** Import only the source-record path contract from `plan_tool/roadmap_artifacts.py` plus standard-library dependencies. Do not import `plan_tool/roadmap.py`, gates, views, receipt code, snapshot code, or backend seams.

- **Keep existing JSON behavior.** Continue using the current `json.loads` record parsing rules. Strict duplicate-member checks or a new versioned source schema are separate contract changes, not part of this refactor.

## Tests

### Tests for this step

- `test_missing_source_record_is_reported_as_absent` — A missing or non-file `source.json` produces the existing no-record result without attempting to read a brief.

- `test_recorded_brief_path_resolves_relative_to_repo_root` — A relative `brief_path` resolves from the supplied repository root.

- `test_absolute_recorded_brief_path_is_preserved` — An absolute recorded path remains the brief path used for reading.

- `test_invalid_source_record_raises_naming_source_json` — Invalid JSON, a non-object payload, or a blank or missing `brief_path` fails with the source-record path identified.

- `test_recorded_brief_text_and_digest_match_broad_decoded_text_contract` — A brief with newline conversion proves the reader returns decoded text and the SHA-256 digest broad execution would calculate, rather than a raw-byte digest.

- `test_source_record_digest_binds_exact_raw_bytes_not_parsed_payload` — Source records with equivalent JSON payloads but different whitespace or newlines retain their own raw-byte SHA-256 values while resolving the same brief path.

- `test_non_utf8_recorded_brief_preserves_broad_read_failure` — Invalid UTF-8 follows the same failure boundary as the existing broad reader.

- `test_broad_run_keeps_source_lookup_and_brief_read_preflight_distinct` — A malformed source record and an unreadable resolved brief keep their separate broad-run preflight classifications.

- `test_first_successful_stage_write_still_records_source_json_atomically` — A failed first stage leaves no source record, while the first successful artifact writes the unchanged `brief_path` payload through the existing replacement path.

- `test_source_module_does_not_import_roadmap_or_orchestrator_modules` — Source inspection and isolated import confirm `plan_tool/roadmap_source.py` remains usable without the roadmap orchestrator.

- **Green-before-done gate:** `uv run pytest tests/test_roadmap_source.py tests/test_roadmap.py -q` passes.

## Acceptance criteria

- `plan_tool/roadmap_source.py` can read a recorded brief’s resolved path, decoded text, and broad-equivalent SHA-256 digest without importing `plan_tool/roadmap.py`; its impact-only source-record digest is SHA-256 of exact raw bytes, not parsed JSON or decoded brief text.

- Relative and absolute `brief_path` values behave exactly as they do through `plan_tool/roadmap.py:_load_recorded_brief_path`.

- Missing source metadata remains distinct from malformed source metadata and from an unreadable brief.

- Broad roadmap execution preserves its source-versus-brief preflight categories, prompt grounding, and source-related run-log facts.

- `plan_tool/roadmap.py:_write_brief_source` retains its existing one-key JSON payload, atomic replacement behavior, and first-successful-artifact timing.

- The focused source and roadmap test command passes.

## References

- [json — JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Read this for the existing source-record decoding and stable JSON rendering behavior.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Read this for the SHA-256 digest used to bind decoded brief text.

## Applicable guardrails

- **The plan’s “## Step intent,” shared recorded-brief contract:** Limit this step to extracting broad-equivalent source readers plus the impact-only raw source-record binding for later snapshot code.

- **The plan’s “## Architecture,” distinct source and brief digests:** Preserve the existing resolved-path, UTF-8 decoded-text brief-digest behavior; bind impact source metadata separately with exact raw bytes rather than claiming the two digest meanings are equivalent.

- **The plan’s “## Out of scope,” broad roadmap behavior:** Do not change generation, prompts, retries, timeouts, publication behavior, or CLI options.

- **The plan’s “## Out of scope,” writer boundary:** Preserve the existing `source.json` writer and do not add a new filesystem coordination or external-reader mechanism.

## Deferred

- Coherent source-record and artifact capture with before-publication rechecks — step 4 owns the guarded snapshot and current-state validation.

- Persisting only safe brief evidence into immutable impact analyses — steps 4 and 5 own snapshot evidence and analysis identity.

- Source-record schema changes or stricter JSON-member validation — require a separate plan-level contract decision.
