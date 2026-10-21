> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Publish the reader-only evidence contract and retire superseded references

## Summary

Publish the version-aware reader contract in `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`. Update `tests/test_roadmap_format.py` and `tests/test_data_contract.py` so documented evidence shapes, examples, lifecycle fields, and redaction rules stay tied to the landed contracts from steps 1–3. The key decision is to document canonical freshness separately from immutable raw provenance without granting readers baseline-writing or repair authority. On green, the public references explain supported evidence versions, refusal conditions, and durable redacted facts.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome and scope.
- [Table of Contents](#table-of-contents) — Links to every section.
- [Why](#why) — The stale raw-digest-only description this step replaces.
- [Input](#input) — Landed contracts that own the documented behavior.
- [Files (creates vs edits)](#files-creates-vs-edits) — Documentation and drift-guard changes.
- [Implementation](#implementation) — Ownership, version, refusal, and sweep rules.
- [Tests](#tests) — Contract-driven documentation checks.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Representation and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only scope limits.
- [Deferred](#deferred) — Work outside this documentation step.

## Why

`ROADMAP_FORMAT.md` and `docs/ARCHITECTURE.md` currently describe receipts and analyses as version-1 evidence whose raw digest decides currentness. Step 3 completes the versioned reader path, so leaving that description in place would tell operators the wrong reason an evidence record is current or rejected. The references must explain baseline-backed freshness while preserving raw source, source-record, and brief digests as immutable provenance and separate checks.

## Input

- **Versioned evidence:** Read the landed contracts from step 1 in `plan_tool/roadmap_escalation.py:EscalationReceipt`, `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, and `ImpactAnalysis`. Landed fields, validators, and supported-version rules win over this detail.

- **Canonical identity:** Read `plan_tool/roadmap_source_identity.py:BaselineRecord`, `load_baseline_record`, and `compare_baseline`, plus step 2’s `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`. This step documents reader behavior and does not alter baseline publication.

- **Reader admission:** Use the currentness paths completed by step 3: `plan_tool/roadmap_escalation_run.py:current_escalation_receipt`, `plan_tool/roadmap_impact_run.py:current_impact_analysis`, and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`. Describe their shared safety boundary without claiming their implementations are identical.

- **Persisted lifecycle facts:** Use `plan_tool/data_contract.py:persisted_dataclass_contracts` and the registered event types in `plan_tool/run_log.py` as the source for `DATA_CONTRACT.md` tables.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Replace version-1-only receipt and analysis guidance with version-aware schema, provenance, currentness, refusal, and exact-pair boundaries.
  - `DATA_CONTRACT.md` — Align roadmap lifecycle descriptions with registered event fields and their redacted-content boundary.
  - `docs/ARCHITECTURE.md` — Describe writer-owned baseline state and version-aware reader admission at the immutable-roadmap-evidence layer.
  - `tests/test_data_contract.py` — Extend documentation drift checks for all registered roadmap lifecycle records and redaction.
  - `tests/test_roadmap_format.py` — Extend format-reference checks for supported versions, examples, and reader-only route rules.

## Implementation

- **Keep documentation ownership clear:** Make `ROADMAP_FORMAT.md` the operator-facing source for evidence shape, freshness, refusal, and route authority. Keep `DATA_CONTRACT.md` limited to persisted lifecycle records. Keep `docs/ARCHITECTURE.md` at the layer-boundary level.

- **Publish version-specific freshness:** In `ROADMAP_FORMAT.md`’s receipt, analysis, and exact-pair rewrite sections, distinguish legacy exact-raw currentness from version-2 baseline-backed semantic freshness. State that raw source, source-record, and decoded-brief digests remain immutable provenance or independent currentness checks; none replaces the version-2 baseline comparison.

- **Preserve legacy readability:** Keep version-1 parsing, semantic identity, immutable final names, and exact-raw behavior documented. A current version-1 receipt may produce or reuse only version-1 analysis evidence; new receipt issuance follows the landed version-2 path.

- **Make refusal explicit:** Document refusal for unreadable, non-UTF-8, unparsable, unavailable, malformed, incomplete, wrongly bound, or semantically changed source and baseline state. A presentation-only source difference is admissible only for the landed version-2 rule and only when the complete baseline identity matches; readers never normalize or rewrite source text.

- **Keep checks separate:** State that live feedback eligibility, source-record and brief facts, exact receipt-analysis binding, closure, and route requirements remain independently required where their reader uses them. A baseline match does not make stale feedback or changed brief input current.

- **Keep generated candidates strict:** Preserve renderer-byte canonicality for immutable receipt and analysis finals, generated patches, and structural proofs. Canonical freshness applies to current source admission, not to generated-candidate validation.

- **Describe stable observation narrowly:** Document the landed reader guard around receipt creation and inspection, including refusal for an incomplete or changed publication state. Describe mixed-version inspection as version-aware so evidence order cannot apply the wrong rule.

- **Limit the pending-generation exception:** Document that ordinary structural preflight refuses pending state. Describe the publisher’s second preflight only as verification of its own active exact generation; it grants no recovery, mutation, wider selection, or additional write authority.

- **Document lifecycle records from the registry:** Update `DATA_CONTRACT.md` from the registered `plan_tool/run_log.py:RoadmapStructuralRevisionPreflight`, `RoadmapStructuralRevisionAttempt`, `RoadmapEscalationPreflight`, `RoadmapEscalationResult`, `RoadmapImpactPreflight`, and `RoadmapImpactResult` contracts. Do not add event fields or change a persisted schema.

- **Retire stale wording by meaning:** Sweep the scoped docs and tests for version-1, raw-digest, exact-raw, baseline, and reader-currentness claims. Replace only statements that make raw bytes the universal freshness rule; retain correct legacy and provenance references.

- **Keep tests code-owned:** Have `tests/test_roadmap_format.py` derive field inventories, supported versions, and canonical examples from the landed contracts rather than duplicating version lists by hand.

## Tests

- `tests/test_roadmap_format.py:test_escalation_receipt_reference_matches_landed_contract` — verifies documented receipt fields, closed values, and version rules match the landed contract.

- `tests/test_roadmap_format.py:test_escalation_receipt_example_is_valid_and_identity_bound` — verifies every documented receipt example parses, renders canonically, and retains its version-specific identity.

- `tests/test_roadmap_format.py:test_impact_analysis_reference_matches_landed_contract` — verifies documented analysis fields, snapshot facts, route values, and versions match the live model.

- `tests/test_roadmap_format.py:test_impact_analysis_example_is_valid_canonical_and_identity_bound` — verifies every documented analysis example is a parseable canonical immutable final.

- `tests/test_roadmap_format.py:test_reader_only_evidence_reference_preserves_baseline_and_provenance_boundary` — verifies the format doc distinguishes baseline-backed freshness, raw provenance, independent checks, refusal, and no reader repair.

- `tests/test_roadmap_format.py:test_reader_only_evidence_reference_separates_presentation_admission_from_candidate_canonicality` — verifies baseline-equal presentation admission does not relax canonical rendering for evidence finals, patches, or proofs.

- `tests/test_roadmap_format.py:test_structural_rewrite_route_reference_separates_local_evidence_generic_transaction_and_stage_paths` — verifies version-aware evidence does not broaden structural writer authority.

- `tests/test_data_contract.py:test_roadmap_evidence_lifecycle_contracts_are_registered_and_documented` — verifies every registered roadmap lifecycle field and closed outcome remains documented.

- `tests/test_data_contract.py:test_roadmap_evidence_lifecycle_reference_remains_redacted` — verifies lifecycle documentation excludes source prose, baseline contents, reviewer requests, prompts, replies, and backend text.

### Verification (non-code step)

1. Run `uv run pytest tests/test_data_contract.py tests/test_roadmap_format.py -q`.

2. Compare every documented receipt and analysis version with `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`.

3. Parse and render every `ROADMAP_FORMAT.md` evidence example through its real contract.

4. Search scoped documentation and tests for raw-digest and version-1 wording; confirm each surviving mention describes either legacy behavior or immutable provenance.

5. Review `docs/ARCHITECTURE.md` against the step-3 reader entry points; confirm it assigns publication to writers and admission to readers.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents every landed receipt and analysis version without presenting the version-1 raw-digest rule as universal currentness.

- `ROADMAP_FORMAT.md` gives canonical freshness, raw provenance, live feedback, source-record facts, and brief facts their separate roles.

- `ROADMAP_FORMAT.md` documents refusal for unsafe evidence state without introducing reader-side repair or baseline publication.

- `ROADMAP_FORMAT.md` keeps canonical rendering strict for immutable evidence finals and structural candidates.

- `DATA_CONTRACT.md` documents every field registered for the six roadmap lifecycle records and preserves their redaction boundary.

- `docs/ARCHITECTURE.md` identifies the writer-owned baseline and reader-only receipt, analysis, and structural-preflight paths.

- All documented receipt and analysis examples parse, render canonically, and retain their expected identities.

- `uv run pytest tests/test_data_contract.py tests/test_roadmap_format.py -q` passes.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2https: — Defines representation equality while leaving formatting and comments outside parsed values.

- [hashlib — Secure Hashes and Message Digestshttps: — Defines the SHA-256 primitives used for immutable provenance and canonical identities.

## Applicable guardrails

- **The plan’s `## Plan intent`, freshness and provenance boundary** — Document reader use of writer-owned baseline state without making provenance mutable or unsafe state current.

- **The plan’s `## Step intent`, documentation-only scope** — Limit this step to reviewing published version, refusal, and provenance contracts.

- **The plan’s `## Out of scope`, baseline lifecycle boundary** — Do not add enrollment, publication, recovery, or ordinary revision-admission behavior.

- **The plan’s `## Out of scope`, reader-side mutation boundary** — Document refusal rather than repair, migration, canonicalization, or acceptance actions.

- **The plan’s `## Out of scope`, generated-candidate boundary** — Preserve canonical-rendering and malformed-input protections.

- **The plan’s `## Out of scope`, deferred workflow boundary** — Keep retention and hand-edit follow-up work outside this step.

## Deferred

- Reader-side repair or migration commands — Require a separate design; this step documents refusal only.

- Baseline enrollment, publication, and recovery behavior — Remain outside this documentation step.

- Retention and hand-edit follow-up workflows — Remain with the plan’s named backlog work.
