> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Read saved brief digests and distinguish legacy absence from malformed metadata

## Summary

Extend the recorded-brief reader so `plan_tool/roadmap_source.py` exposes a validated saved decoded-text digest alongside the recorded brief path. Keep missing `source.json` distinct from a present legacy record that lacks the digest, and reject malformed digest metadata or an existing directory at the source-record target as source-record errors. Update `tests/test_roadmap_source.py` to lock down the new record states and preserve the existing path and raw-record-digest contracts. On green, later stage preflight can make one unambiguous admission decision without interpreting JSON itself or publishing before discovering a non-replaceable target.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the reader contract added here.
- [Table of Contents](#table-of-contents) — Section map for this detail.
- [Why](#why) — The current ambiguity this reader must remove.
- [Input](#input) — Persisted record and digest contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two in-scope file changes.
- [Implementation](#implementation) — Required source-reader behavior and boundaries.
- [Tests](#tests) — Focused regression coverage for the record states.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Source-persistence contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that limit this step.
- [Deferred](#deferred) — Follow-up ownership outside this reader change.

## Why

`source.json` currently binds a roadmap to a path but cannot say whether the current brief text matches the text accepted when that binding was written. Treating every absent digest alike would either silently preserve that uncertainty or reject valid older records without a migration path. Treating an existing directory at the source-record path as absent also lets artifact publication begin before the writer discovers that it cannot replace the target. The shared reader must instead provide the roadmap layer a trusted distinction between an eligible absent target, a valid legacy record with unknown content, a valid digest-bearing record, and a malformed or non-replaceable record target.

## Input

- **Recorded source record:** `plan_tool/roadmap_artifacts.py:brief_source_path` identifies `source.json`; `plan_tool/roadmap_source.py:read_recorded_brief_source` currently requires a non-empty `brief_path` and retains the raw record bytes.
- **Decoded-text digest:** `plan_tool/roadmap_source.py:digest_decoded_text` defines the SHA-256 value saved for the UTF-8 text contract returned by `read_brief_text`, including its newline normalization behavior.
- **Existing consumers:** `plan_tool/roadmap.py:_resolve_brief_path` currently consumes only the path, while `plan_tool/roadmap_impact_snapshot.py:_capture_recorded_brief_digests` consumes the shared record and its raw-record digest. Keep their current meanings intact; later steps own any stage admission behavior.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source.py` — extend `RecordedBriefSource` and `read_recorded_brief_source` with the saved brief-digest contract.
  - `tests/test_roadmap_source.py` — add focused record-state and malformed-digest coverage while retaining leaf-import coverage.

## Implementation

The foundational logic is: **parse a recorded brief reference with an optional valid decoded-text baseline digest.**

- **Expose one parsed record shape.** Extend `plan_tool/roadmap_source.py:RecordedBriefSource` so callers receive the resolved `brief_path`, existing raw source-record facts, and a saved brief digest whose absence explicitly means legacy/unknown. Do not make callers reopen or re-parse `source.json` to learn the digest state.

- **Keep absence categories separate.** `read_recorded_brief_source` returns `None` only when no readable record exists at an eligible target that the source writer can replace. A real directory at `brief_source_path` is not eligible absence: raise `RoadmapSourceError` before any stage work. Preserve existing replaceable-path behavior outside that concrete directory case. A readable record with a valid non-empty `brief_path` but no digest field returns a record with an explicit absent baseline, not `None` and not a match.

- **Validate a present digest strictly.** A present digest must be a canonical SHA-256 digest value for `digest_decoded_text`: a string with the required hexadecimal shape and length. Reject empty strings, non-strings, wrong lengths, and non-hex values through `RoadmapSourceError`, alongside the existing JSON and `brief_path` failures. Do not coerce, normalize, or silently drop malformed values, because later preflight must fail closed rather than mistake corruption for a legacy record.

- **Preserve the current path contract.** Keep relative `brief_path` values rooted at `repo_root`, preserve absolute paths, and retain `source_bytes` plus `source_digest` from `digest_source_record`. The new saved brief digest describes decoded brief content; it must not replace or reuse the raw `source.json` digest.

- **Keep the module a leaf.** Continue importing only `plan_tool.roadmap_artifacts:brief_source_path`. `plan_tool/roadmap.py:_resolve_brief_path` and `plan_tool/roadmap_impact_snapshot.py:_capture_recorded_brief_digests` reuse this reader unchanged in this step; changing their selection, snapshot, or lifecycle behavior belongs to later steps.

- **Leave comparison and persistence out of this step.** This reader validates and reports the saved baseline. `plan_tool/roadmap.py:_write_brief_source` owns writing it, and `plan_tool/roadmap.py:_run_roadmap` owns comparing current text before artifact admission.

## Tests

### Tests for this step

- `test_missing_source_record_is_reported_as_absent` — A genuinely missing `source.json` returns `None`, not a legacy record.
- `test_source_record_directory_is_rejected_as_non_replaceable` — An existing directory at `source.json` raises `RoadmapSourceError` instead of being treated as absence.
- `test_recorded_brief_source_exposes_saved_decoded_text_digest` — A valid record returns its resolved path and the exact valid saved digest.
- `test_recorded_brief_source_without_digest_is_legacy_unknown` — A valid path-only record remains readable and exposes an absent baseline explicitly.
- `test_invalid_recorded_brief_digest_raises_naming_source_json` — Empty, non-string, wrong-length, and non-hex digest values raise `RoadmapSourceError` rather than becoming legacy absence.
- `test_source_record_digest_binds_exact_raw_bytes_not_parsed_payload` — Whitespace-only changes to `source.json` still change `source_digest` independently of the saved brief digest.
- `test_recorded_brief_text_and_digest_match_broad_decoded_text_contract` — The saved-value contract remains aligned with `digest_decoded_text` and decoded UTF-8 text rather than raw brief bytes.
- `test_source_module_does_not_import_roadmap_or_orchestrator_modules` — The extended reader retains its leaf import boundary.

**Green-before-done gate:** `uv run pytest tests/test_roadmap_source.py -q` passes.

## Acceptance criteria

- `read_recorded_brief_source` returns `None` for an eligible absent source-record target and raises for an existing directory the atomic writer cannot replace.
- A valid record containing `brief_path` and a valid saved decoded-text digest returns both facts through `RecordedBriefSource`.
- A valid record without the digest remains readable and is visibly distinguishable from a matching digest-bearing record.
- A present digest with an invalid type or SHA-256 shape raises `RoadmapSourceError` that identifies the source record.
- Relative and absolute brief-path behavior, exact raw-record digest behavior, and the leaf-module import boundary remain covered by `tests/test_roadmap_source.py`.
- `uv run pytest tests/test_roadmap_source.py -q` is green.

## References

- [BUG_BACKLOG.md — Read the “A changed concept brief is silently ignored on every stage run after the first” risk contract for the legacy-versus-malformed distinction.
- [plan_tool/roadmap_source.py — Read `RecordedBriefSource`, `read_recorded_brief_source`, and `digest_decoded_text` as the shared source-reader contract.
- [plan_tool/roadmap.py — Read `_resolve_brief_path`, `_write_brief_source`, and `_run_roadmap` to preserve ownership boundaries.
- [ROADMAP_FORMAT.md — Read the source and re-entry rules that keep source binding separate from artifact regeneration.
- [docs/ARCHITECTURE.md — Read “Brief-source persistence” for the one-shot binding and legacy re-entry boundary.
- [tests/test_roadmap_source.py — Extend the existing source-reader contract tests beside their current path, digest, and leaf-import cases.

## Applicable guardrails

- **The plan’s “## Step intent”, trusted source-record representation:** Limit this step to parsing and classifying source-record metadata; do not compare current brief content or decide stage admission here.
- **The plan’s “## Out of scope”, artifact and workflow behavior:** Do not regenerate, reconcile, rewrite, or otherwise interpret roadmap artifacts from this reader.
- **The plan’s “## Out of scope”, source identity rules:** Preserve the existing `brief_path` identity and path-resolution behavior.
- **The plan’s “## Risks”, digest alignment:** Keep the saved value on `digest_decoded_text`’s decoded-text contract so later comparison cannot report drift for equivalent decoded text.

## Deferred

- Stage preflight comparison and refusal — step 2 consumes the parsed saved digest before artifact admission and backend contact.
- Initial digest persistence — step 2 extends `plan_tool/roadmap.py:_write_brief_source` while preserving its atomic write boundary.
- Explicit same-path baseline acceptance — step 3 owns the operator gesture, source-record replacement, and lifecycle reporting.
- Source-admission documentation and risk retirement — step 4 updates the authoritative documentation and backlog record.
