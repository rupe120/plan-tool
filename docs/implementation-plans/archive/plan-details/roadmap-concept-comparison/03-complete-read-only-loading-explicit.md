> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add complete read-only loading for an explicit stored roadmap version

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Extend `plan_tool/roadmap_versions.py` so a caller that supplies a stored version id receives the same complete, verified `ResolvedRoadmapVersion` bundle available through `load_accepted_version`. Keep `load_stored_version` as the record-only reader and add a public complete-loading path beside it. Ensure `load_accepted_version` uses that complete path after resolving the accepted-head selector, so accepted and explicit selection share one integrity check. Add focused coverage in `tests/test_roadmap_versions.py`; on green, an explicit root or candidate version yields its exact brief and fixed artifact inventory without changing storage.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the complete explicit-version reader.
- [Table of Contents](#table-of-contents) — Links to each detail section.
- [Why](#why) — Why explicit comparison selectors need the accepted reader’s integrity checks.
- [Input](#input) — Persisted record, member, and inventory contracts this reader consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — The version contract module and its focused tests.
- [Implementation](#implementation) — Required complete-loading behavior and shared validation path.
- [Tests](#tests) — Cases that prove exact, fail-closed, read-only loading.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Relevant roadmap format and feature-contract sources.
- [Applicable guardrails](#applicable-guardrails) — Read-only and fixed-inventory boundaries.
- [Deferred](#deferred) — Work left to later comparison steps.

## Why

`plan_tool/roadmap_versions.py:load_accepted_version` verifies the selected record, recorded brief, and each stored artifact, but `load_stored_version` returns only the record for an explicit id. The comparison flow needs an explicit base or target to be just as complete and trustworthy as an accepted-head selection; otherwise callers must duplicate digest and UTF-8 checks or risk comparing incomplete bytes.

## Input

- **Stored version records:** Read the canonical record through `plan_tool/roadmap_versions.py:load_stored_version`, including its requested-path identity binding.
- **Fixed content inventory:** Read `StoredRoadmapVersion.brief_digest`, `StoredRoadmapVersion.artifact_members`, and `VERSION_ARTIFACT_INVENTORY` in their established order.
- **Resolved bundle contract:** Return `plan_tool/roadmap_versions.py:ResolvedRoadmapVersion`, preserving its record, raw brief bytes, and stage-ordered artifact bytes.
- **Accepted selector:** Keep `plan_tool/roadmap_versions.py:load_accepted_head` responsible only for selector resolution; an absent selector remains distinct from an explicitly requested missing or invalid stored version.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_versions.py` — Add the public complete reader for an explicit version id and have `load_accepted_version` reuse it after selector resolution.
  - `tests/test_roadmap_versions.py` — Add direct coverage for complete explicit-version reads, refusal cases, and no-write behavior.

## Implementation

- **Foundational logic:** Load one explicit immutable version as a complete, digest-verified `ResolvedRoadmapVersion`.

- **Add one complete explicit-version read path.** Place it alongside `load_stored_version` and `load_accepted_version` in `plan_tool/roadmap_versions.py`. It must accept the already-resolved plans directory, roadmap slug, and explicit version id, then return the record with its exact brief and artifact bytes.

- **Keep record-only loading available.** `load_stored_version` remains the public reader for callers that need only a validated `StoredRoadmapVersion`. The new complete reader builds on that record contract rather than widening or changing its return type.

- **Share accepted and explicit integrity checks.** Make `load_accepted_version` resolve the selector through `load_accepted_head`, then use the complete explicit-version path for the selector’s id. This is the key design decision: selector choice and member verification stay separate, while both routes verify the same stored bytes.

- **Preserve the fixed member contract.** Read the recorded brief through `stored_brief_path` and every artifact through `stored_artifact_path`, using the record’s configured member digests and order. The resulting `artifact_bytes` must remain paired with `ResolvedRoadmapVersion.artifact_keys` in `VERSION_ARTIFACT_INVENTORY` order.

- **Fail closed for every requested explicit version.** Missing files, unreadable bytes, non-UTF-8 member content, digest mismatches, malformed records, and record/path identity mismatches must raise `RoadmapVersionError`. An explicit id must not fall back to the accepted head, live roadmap artifacts, or another stored version.

- **Keep the reader read-only.** Do not create directories, repair members, rewrite records, or update `accepted-head.json`. Reuse the existing `_read_member_bytes` and `_read_bytes` error behavior where it fits rather than adding a recovery path.

- **Leave candidate workflow ownership unchanged.** `plan_tool/roadmap_candidate_run.py:_load_resolved_version` has a similar private read shape, but this step’s declared files do not include that module. The new public version reader exists for later comparison work without changing candidate proposal behavior here.

## Tests

### Tests for this step

- `test_load_explicit_stored_version_returns_complete_root_bundle` — An explicitly selected stored root returns its record, exact brief bytes, and stage-ordered artifact bytes without an accepted-head selector.
- `test_load_explicit_stored_version_returns_complete_candidate_bundle` — An explicitly selected candidate returns the same complete bundle shape and does not require it to be accepted.
- `test_load_explicit_stored_version_ignores_unselected_malformed_sibling` — A malformed sibling version does not affect a valid explicitly named version.
- `test_load_explicit_stored_version_refuses_missing_or_corrupt_members` — Missing, digest-mismatched, and non-UTF-8 brief or artifact members raise `RoadmapVersionError`.
- `test_load_explicit_stored_version_refuses_unknown_or_path_mismatched_record` — An absent requested id or a record whose slug or version id does not match its requested path raises `RoadmapVersionError`.
- `test_load_accepted_version_uses_complete_explicit_version_contract` — The accepted-head route returns the same complete result and refusal behavior as the explicit route for its selected id.
- `test_complete_explicit_version_loading_does_not_write_or_repair_storage` — Snapshot storage before and after successful and refused reads is unchanged.

Every listed test in `tests/test_roadmap_versions.py` must be green before this step is complete.

## Acceptance criteria

- An explicit valid root or candidate version id returns a `ResolvedRoadmapVersion` containing the exact stored brief and all configured artifact members in `VERSION_ARTIFACT_INVENTORY` order.
- The accepted-head route delegates to the same complete member-validation path after resolving its selector.
- A missing, malformed, identity-mismatched, non-UTF-8, or digest-mismatched requested version raises `RoadmapVersionError` and does not select another source.
- Explicit loading does not require an accepted-head selector and never falls back to live artifacts.
- Successful and refused complete reads leave version records, members, and selector bytes unchanged.
- `tests/test_roadmap_versions.py` passes.

## References

- [ROADMAP_FORMAT.md — Read the immutable-version identity, fixed-member, and presentation contracts.](../../../../../ROADMAP_FORMAT.md)
- [BACKLOG.md #402 — Read the comparison feature’s explicit stored-version and read-only scope contract.](../../../../../BACKLOG.md)
- [Roadmap Concept Comparison plan — Read step 3’s intent and step 4’s consumer boundary.](../../2-roadmap-concept-comparison.md)

## Applicable guardrails

- **The plan’s “## Scope guardrails”, read-only command boundary:** This step may only read and validate immutable storage; it must not alter roadmap snapshots, selectors, or lifecycle state.
- **The plan’s “## Scope guardrails”, fixed evidence boundary:** This step must preserve the stored bytes and configured artifact ordering that later comparison evidence consumes.
- **The plan’s “## Scope guardrails”, compatibility boundary:** Existing accepted-version reads and lifecycle writers must keep their current behavior.
- **The plan’s “## Out of scope”, lifecycle and policy changes:** This step must not add acceptance, promotion, enrollment, repair, candidate-policy, or generalized comparison behavior.

## Deferred

- Candidate proposal reader consolidation — `plan_tool/roadmap_candidate_run.py:_load_resolved_version` remains unchanged because changing candidate workflow behavior is outside this step’s declared files and is not required for the comparison reader.
- Snapshot selection and Git patch collection — Step 4 owns comparison selector policy, working-artifact resolution, and controlled Git evidence.
