> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Define versioned evidence identities, issuance, and compatibility from the published baseline

## Summary

Add version-aware receipt and impact-analysis contracts in `plan_tool/roadmap_escalation.py` and `plan_tool/roadmap_impact_analysis.py`, then make structural preflight require an exact matching-version pair. Keep raw source digests as immutable provenance while version 2 carries a separate identity from the writer-published baseline. Preserve version-1 parsing, semantic IDs, final names, and exact-raw compatibility without inferring a new identity for legacy evidence. On green, versioned evidence can be created, parsed, hashed, reused, and paired without granting readers any baseline-writing authority.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and main design choice.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current ambiguity between raw provenance and canonical freshness.
- [Input](#input) — Existing baseline and evidence contracts this step must preserve.
- [Files (creates vs edits)](#files-creates-vs-edits) — The six scoped code and test files.
- [Implementation](#implementation) — Version rules, identity binding, reuse, and pair admission.
- [Tests](#tests) — Focused compatibility and fail-closed coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Canonical JSON and hashing references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits on reader-only work.
- [Deferred](#deferred) — Later reader wiring and documentation work.

## Why

`plan_tool/roadmap_escalation.py:ReceiptSource` and `plan_tool/roadmap_impact_analysis.py:ImpactSnapshotEvidence` currently retain raw digests as both provenance and freshness evidence. That makes a presentation-only source change indistinguishable from a semantic source change, even though `plan_tool/roadmap_source_identity.py:BaselineRecord` already records the writer-owned semantic baseline. Define a version boundary now so later readers can use canonical freshness without rewriting legacy evidence or treating a hand edit as accepted source.

## Input

- **Published baseline contract:** Read the semantic identity exposed by `plan_tool/roadmap_source_identity.py:BaselineRecord`, `load_baseline_record`, and `compare_baseline`. The baseline excludes feedback and remains writer-owned; this step only defines how evidence represents an already-admitted baseline identity.
- **Legacy receipt contract:** Preserve the version-1 value defined by `plan_tool/roadmap_escalation.py:EscalationReceipt`, `receipt_semantic_preimage`, `receipt_semantic_id`, `parse_receipt`, and `render_receipt`.
- **Legacy analysis contract:** Preserve the version-1 value defined by `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`, `impact_analysis_semantic_preimage`, `impact_analysis_semantic_id`, `parse_impact_analysis`, and `render_impact_analysis`.
- **Future canonical snapshot input:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` currently supplies raw artifact, source-record, and brief digests. Step 2 owns adding and capturing the baseline-backed facts that the version-2 analysis branch will consume.
- **Exact-pair reader:** `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight` already parses named finals and calls `_require_pair_binding` before returning structural context. Keep that ordering when adding version matching.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_source_identity.py` — Define the closed redacted identity value and convert only an already validated `BaselineRecord`; do not change baseline enrollment, publication, recovery, or comparison semantics.
  - `plan_tool/roadmap_escalation.py` — Add closed version-1 and version-2 receipt validation, version-aware semantic identity handling, and a version-2 canonical-freshness field that remains separate from `ReceiptSource.sha256`.
  - `plan_tool/roadmap_impact_analysis.py` — Add matching versioned analysis and nested receipt-evidence shapes, version-aware analysis construction, hashing, parsing, and exact-candidate reuse.
  - `plan_tool/roadmap_structural_revision.py` — Reject a receipt and analysis whose schema versions differ before structural context is loaded.
  - `tests/test_roadmap_source_identity.py` — Cover closed redacted identity construction and fieldwise equality without exposing a baseline projection or feedback.
  - `tests/test_roadmap_escalation.py` — Preserve fixed version-1 compatibility fixtures and add version-2 identity and issuance coverage.
  - `tests/test_roadmap_impact_analysis.py` — Cover version-matched analysis construction, legacy compatibility, and no inferred upgrade.
  - `tests/test_roadmap_structural_revision.py` — Cover matching-version pair admission and fail-closed mixed-version rejection.

## Implementation

- **Model each evidence version as a closed immutable shape.** Update `plan_tool/roadmap_escalation.py:parse_receipt` and `plan_tool/roadmap_impact_analysis.py:parse_impact_analysis` to select a supported schema version before validating that version’s fields. Do not use one schema with an optional canonical-freshness field: version 1 must not accept a missing or null version-2 field, and version 2 must not silently discard it.

- **Keep version 1 byte and hash compatible.** Preserve the version-1 semantic preimages used by `receipt_semantic_preimage`, `receipt_semantic_id`, `impact_analysis_semantic_preimage`, and `impact_analysis_semantic_id`. Existing version-1 finals must retain their current final names, and rendering a parsed legacy value must not add a baseline identity or otherwise rewrite it.

- **Make version 2 hold two different facts.** Retain `ReceiptSource.sha256` as the digest of the raw bytes observed by the reader. Add one closed, redacted `CanonicalBaselineIdentity` copied only from a fully validated writer-published `BaselineRecord`: `source_identity_version`, `roadmap_slug`, `stage_key`, `format_version`, and semantic `digest`. It must retain neither the baseline projection nor feedback content. Equality is fieldwise over exactly those five fields; no reader may compare a smaller subset or infer this identity from raw bytes.

- **Bind the canonical identity into every version-2 hash.** The version-2 receipt semantic preimage must include both issuance-time raw provenance and canonical freshness. The version-2 analysis must carry the matching receipt identity and its own baseline-backed snapshot evidence in its semantic preimage. Changing either identity at issuance produces a different final name. Later currentness must compare the stored closed canonical identity and live independent inputs directly; it must not rebuild a final and treat its different raw provenance as a stale semantic identity.

- **Do not infer version 2 from legacy facts.** Update `plan_tool/roadmap_escalation.py:receipt_semantic_id_from_facts` and `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence` so raw receipt facts can validate a version-1 receipt only. A version-2 receipt or analysis must receive its canonical identity explicitly; a missing, malformed, or mismatched value refuses construction rather than falling back to version 1.

- **Keep issuance version-aware and fail closed.** Adapt `plan_tool/roadmap_escalation.py:build_receipt` so new receipt issuance requires an already-admitted canonical identity and never lets a failed version-2 input downgrade to a new version-1 receipt. Adapt `plan_tool/roadmap_impact_analysis.py:build_impact_analysis` separately: a stored version-1 receipt that is exact-raw current may create or reuse only a version-1 analysis, while a version-2 receipt may create or reuse only version-2 analysis evidence. Neither path upgrades, rewrites, or infers a version from legacy facts. Step 2 and step 3 will supply the reader admission and live-source inputs.

- **Require analysis and receipt versions to match.** Make `build_impact_analysis` create or reuse a version-1 analysis only for a version-1 receipt and a version-2 analysis only for a version-2 receipt. Keep `classify_existing_impact_analysis` exact-byte based; it must not treat a semantically similar record from another version as reusable.

- **Reject mixed pairs before structural work begins.** In `plan_tool/roadmap_structural_revision.py:_require_pair_binding`, require the parsed receipt and analysis to have the same schema version in addition to the existing final-name, selector, target, reason, and raw-digest checks. `load_structural_revision_preflight` must reject the pair before capturing a snapshot, resolving a closure, or returning selected feedback.

- **Preserve existing structural authority.** Leave `plan_tool/roadmap_structural_revision.py:_current_selected_slice`, `_resolve_current_closure`, route handling, and generated-candidate checks responsible for their current selection, relation, and canonical-byte rules. This step adds identity compatibility only; it does not make structural preflight read, initialize, repair, or advance a baseline.

- **Keep strict decoding unchanged for both versions.** Continue rejecting duplicate JSON members, non-finite values, floats where forbidden, unknown fields, and malformed identifiers through the existing duplicate-key decoders and frozen Pydantic models.

## Tests

### Tests for this step

Every test below, plus the existing strict-scalar and canonical-rendering cases in these three files, must be green before this step is complete.

- `tests/test_roadmap_escalation.py:test_legacy_v1_receipt_round_trips_with_its_original_semantic_id` — A fixed version-1 receipt fixture parses and renders without gaining a canonical identity or changing its final name.
- `tests/test_roadmap_escalation.py:test_v2_receipt_keeps_raw_provenance_separate_from_canonical_freshness` — Version 2 retains the raw source digest and a distinct baseline-backed identity, with both affecting the receipt identity.
- `tests/test_roadmap_source_identity.py:test_canonical_baseline_identity_has_one_closed_fieldwise_equality_rule` — Missing, added, reordered, or differently bound identity facts reject before issuance; the valid five-field identity round-trips without projection or feedback.
- `tests/test_roadmap_escalation.py:test_v2_receipt_requires_an_explicit_valid_canonical_identity` — Missing, null, malformed, or wrongly bound canonical identity refuses rather than issuing version 1.
- `tests/test_roadmap_escalation.py:test_receipt_version_specific_closed_schemas_reject_cross_version_fields` — Each version rejects fields that belong only to the other version.
- `tests/test_roadmap_impact_analysis.py:test_legacy_v1_receipt_builds_only_a_v1_analysis` — A version-1 receipt produces an analysis with preserved legacy semantic and final-name rules.
- `tests/test_roadmap_impact_analysis.py:test_exact_raw_current_v1_receipt_may_publish_only_v1_analysis` — A retained exact-raw-current version-1 receipt may create or reuse a version-1 analysis, while a stale receipt refuses and no path emits version 2.
- `tests/test_roadmap_impact_analysis.py:test_v2_analysis_binds_matching_receipt_and_snapshot_canonical_identity` — Version 2 includes matching canonical freshness facts in its nested receipt and snapshot evidence.
- `tests/test_roadmap_impact_analysis.py:test_analysis_never_infers_a_v2_identity_from_a_v1_receipt` — A stale or legacy receipt cannot be upgraded from its raw digest alone.
- `tests/test_roadmap_impact_analysis.py:test_existing_analysis_reuse_requires_exact_bytes_and_matching_version` — Only the exact canonical candidate bytes for the same version are reusable; cross-version evidence collides.
- `tests/test_roadmap_structural_revision.py:test_preflight_accepts_matching_version_receipt_analysis_pairs` — Existing version-1 pairs remain admissible and a valid version-2 pair follows the same exact-pair boundary.
- `tests/test_roadmap_structural_revision.py:test_preflight_rejects_a_mixed_version_pair_before_snapshot_capture` — A mixed receipt-analysis pair raises `StructuralRevisionPreflightError` without loading current structural context.

## Acceptance criteria

- Version-1 receipt and impact-analysis fixtures remain parseable, retain their existing semantic IDs and final names, and render without a version-2 identity.
- Version-2 receipt and analysis values store raw provenance separately from a baseline-backed canonical-freshness identity.
- A version-2 identity is exactly `source_identity_version`, `roadmap_slug`, `stage_key`, `format_version`, and semantic `digest`; equality is fieldwise over that closed set, it is part of the relevant semantic hash, and raw source bytes cannot replace it.
- A missing or invalid version-2 canonical identity refuses construction; no failed version-2 path emits or rewrites version-1 evidence.
- New receipt issuance is version 2 only; an exact-raw-current stored version-1 receipt may create or reuse only version-1 analysis evidence.
- `build_impact_analysis` creates matching-version evidence only, and `classify_existing_impact_analysis` reuses only exact canonical bytes for that version.
- `load_structural_revision_preflight` rejects a mixed-version receipt-analysis pair before snapshot capture or selected-feedback return.
- `uv run pytest tests/test_roadmap_escalation.py tests/test_roadmap_impact_analysis.py tests/test_roadmap_structural_revision.py -q` passes.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use its representation-equality model when separating semantic baseline identity from source formatting.
- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use the SHA-256 contract for immutable raw provenance and versioned semantic identities.

## Applicable guardrails

- **The plan’s “## Plan intent”, writer-owned baseline authority** — Use `plan_tool/roadmap_source_identity.py` only as the existing canonical source; do not create another freshness authority in these contract modules.
- **The plan’s “## Step intent”, identity and compatibility boundary** — Limit this step to versioned evidence values, issuance rules, reuse, and structural pair compatibility.
- **The plan’s “## Out of scope”, baseline lifecycle boundary** — Do not edit baseline enrollment, publication, recovery, or ordinary and local revision admission.
- **The plan’s “## Out of scope”, reader mutation and provenance boundary** — Do not add a repair, migration, canonicalization, or accept-current path, and do not make raw provenance mutable.
- **The plan’s “## Out of scope”, generated-candidate boundary** — Preserve structural patch and proof canonicality checks without widening them into source-reader admission.
- **The plan’s “## Out of scope”, follow-up workflow boundary** — Do not add retention or hand-edit feedback workflows to these evidence contracts.

## Deferred

- `plan_tool/roadmap_impact_snapshot.py` and `plan_tool/roadmap_impact_run.py` baseline-backed impact capture — Step 2 owns collecting the canonical identity and retaining the independent source-record and brief checks.
- `plan_tool/roadmap_escalation_selection.py` and `plan_tool/roadmap_escalation_run.py` live baseline admission and version-2 receipt issuance — Step 3 owns reader-side admission and live feedback eligibility.
- `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md` — Step 4 owns published contract documentation after the reader behavior is complete.
- Baseline initialization, repair, and migration — These remain writer-owned lifecycle work outside this plan’s reader-only scope.
