> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Publish the reader-only evidence contract and retire superseded references

## Summary

Publish the version-aware, reader-only evidence contract in `ROADMAP_FORMAT.md`, `DATA_CONTRACT.md`, and `docs/ARCHITECTURE.md`. Update the two documentation drift guards so examples, version inventories, lifecycle records, and reader boundaries stay tied to the landed contracts from steps 1–3. The key decision is to describe canonical freshness separately from immutable raw provenance, without giving a reader any baseline-writing or repair authority. On green, the public docs explain what each evidence version proves, when readers refuse it, and which redacted facts remain durable.

## Table of Contents

- [Summary](#summary) — Reviewer-level result and primary boundary.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The stale raw-digest-only reading this step removes.
- [Input](#input) — Versioned evidence and reader contracts from steps 1–3.
- [Files (creates vs edits)](#files-creates-vs-edits) — The documentation and drift guards this step changes.
- [Implementation](#implementation) — Documentation ownership, version rules, and reference sweep.
- [Tests](#tests) — Drift-guard cases for the published contract.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and verification results.
- [References](#references) — Canonical-value and digest references.
- [Applicable guardrails](#applicable-guardrails) — Reader-only and writer-boundary limits.
- [Deferred](#deferred) — Work deliberately left outside this documentation step.

## Why

`ROADMAP_FORMAT.md` and `docs/ARCHITECTURE.md` currently describe receipts and analyses as version-1, raw-digest-only evidence. Steps 1–3 add a versioned canonical-freshness path, so leaving that wording in place would tell operators that a reader can trust or reject evidence for the wrong reason. The docs must make the version boundary clear while preserving raw source, source-record, and brief digests as immutable provenance and independent safety checks.

## Input

- **Versioned evidence:** Read the landed contracts from step 1 in `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `ImpactSnapshotEvidence`, and `ImpactAnalysis`. The landed field names and supported-version rules win over this plan and its earlier detail files.

- **Canonical source identity:** Read step 2’s baseline-backed capture contract through `plan_tool/roadmap_source_identity.py:BaselineRecord`, `load_baseline_record`, and `compare_baseline`, plus the snapshot type used by `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot`. This step documents reader behavior; it does not change source identity or publication behavior.

- **Reader admission:** Read step 3’s currentness paths in `plan_tool/roadmap_escalation_run.py:current_escalation_receipt`, `plan_tool/roadmap_impact_run.py:current_impact_analysis`, and `plan_tool/roadmap_structural_revision.py:load_structural_revision_preflight`. Document their shared refusal boundary without claiming that their separate readers have identical implementations.

- **Persisted lifecycle facts:** Use `plan_tool/data_contract.py:persisted_dataclass_contracts` and the registered `plan_tool/run_log.py:RoadmapStructuralRevisionPreflight`, `RoadmapStructuralRevisionAttempt`, `RoadmapEscalationPreflight`, `RoadmapEscalationResult`, `RoadmapImpactPreflight`, and `RoadmapImpactResult` records as the only source for `DATA_CONTRACT.md` field tables.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — Replace version-1-only receipt and analysis guidance with version-aware schema, provenance, currentness, and refusal guidance; keep the exact-pair writer boundary clear.
  - `DATA_CONTRACT.md` — Update the roadmap lifecycle-record descriptions to match the landed registered shapes and explain the redacted reader evidence they retain.
  - `docs/ARCHITECTURE.md` — Update the immutable-roadmap-evidence layer description to show the baseline reader/writer split and the version-aware reader paths.
  - `tests/test_data_contract.py` — Extend the data-contract drift checks for the published roadmap lifecycle and redaction boundary.
  - `tests/test_roadmap_format.py` — Extend the format-reference guards for all supported evidence versions, examples, and reader-only route guidance.

## Implementation

- **Publish one version-aware rule:** In `ROADMAP_FORMAT.md`’s `## Structural escalation receipts`, `## Impact-routing analyses`, and `## Exact-pair structural rewrite` sections, state which supported evidence versions use exact raw artifact identity and which use the writer-published canonical identity. Keep raw source digests, recorded-source digests, and decoded-brief digests as provenance or independent currentness checks; do not describe any of them as a substitute for the version-2 baseline check.

- **Keep legacy evidence readable:** Label version-1 receipt and analysis behavior as legacy-compatible rather than deleting it. Its parsing, semantic identity, immutable final name, and exact-raw currentness remain valid for that version. An exact-raw-current stored version-1 receipt may create or reuse only a version-1 analysis; new receipt issuance remains version 2 only. Do not write a global statement that makes a version-1 rule appear to govern version 2.

- **Make refusal behavior explicit:** Document that version-2 source readers refuse unavailable, malformed, wrongly bound, incomplete, or semantically different baseline state, and unreadable, non-UTF-8, or unparsable source. A parseable renderer-byte difference is admissible only when its full closed baseline identity matches; it is never normalized. Readers must also reject changes to live feedback, required source records, decoded briefs, exact evidence pairing, closure, or route requirements where their reader needs those facts. Generated patches, proofs, and immutable evidence finals remain renderer-byte strict. A refusal reports no new authority and never repairs, enrolls, migrates, canonicalizes, or accepts source state.

- **Preserve raw-provenance meaning:** Keep the distinction between immutable source provenance and reader freshness visible in both receipt and analysis references. A version-1 reader remains exact-raw; a version-2 reader may accept a strict-UTF-8, parseable presentation change only where its full baseline identity matches, while later currentness compares that identity and independent live inputs rather than rebuilding a different raw-evidence final. A semantic hand edit is not accepted merely because it resembles a canonical value.

- **Keep the writer boundary narrow:** Preserve `ROADMAP_FORMAT.md`’s `### Evidence, publication, and availability boundary`: version-aware evidence changes admission only. The exact-pair writer still publishes one proved selected artifact and selected feedback row, and cross-artifact evidence does not create transaction authority.

- **Publish stable-observation behavior:** State that version-2 receipt creation and escalation views hold the existing reader guard across their artifact/baseline observation, refuse a pending or changed publication pair, and expose no receipt or handoff from it. Explain that a mixed-version view evaluates each record by both stage and evidence version, independent of evidence listing order.

- **Document lifecycle records from code, not inference:** In `DATA_CONTRACT.md`, update the roadmap sections from the live registry and `plan_tool/run_log.py` classes after steps 1–3 land. Retain the existing redaction rule: durable records expose only registered safe identifiers, digests, counts, and closed outcomes, never source prose, reviewer requests, prompts, replies, or baseline contents. Do not add a telemetry field or change a persisted schema in this documentation step.

- **Clarify layer ownership:** In `docs/ARCHITECTURE.md`’s `### Immutable roadmap evidence` section, identify `plan_tool/roadmap_source_identity.py:BaselineRecord` as writer-owned state and the three step-3 reader entry points as read-only consumers. Keep `ROADMAP_FORMAT.md` as the operator-visible schema and route authority, while `DATA_CONTRACT.md` remains the persisted-lifecycle reference.

- **Sweep stale wording as a class:** Search the three scoped docs and both drift guards for `version-1`, `raw source digest`, `source digest`, `exact raw`, `canonical freshness`, `baseline`, and reader-currentness language. Replace only statements that incorrectly make raw bytes the sole freshness rule for every version; preserve explicit legacy and provenance references that still describe the landed contract.

- **Keep tests contract-driven:** In `tests/test_roadmap_format.py`, derive supported fields, versions, and canonical examples from the landed receipt and analysis contracts rather than repeating numeric version lists. Preserve the existing marker-block checks so operator-facing examples remain parsed, rendered, and identity-bound by the real contracts.

## Tests

- `tests/test_roadmap_format.py:test_escalation_receipt_reference_matches_landed_contract` — verifies the receipt inventory and closed values cover the landed supported-version contract without treating a legacy raw digest as universal freshness.

- `tests/test_roadmap_format.py:test_escalation_receipt_example_is_valid_and_identity_bound` — verifies each documented receipt example parses, renders canonically, and retains the identity rules for its version.

- `tests/test_roadmap_format.py:test_impact_analysis_reference_matches_landed_contract` — verifies the analysis inventory, route vocabulary, and version-specific snapshot facts match the live model.

- `tests/test_roadmap_format.py:test_impact_analysis_example_is_valid_canonical_and_identity_bound` — verifies documented analysis examples remain canonical, parseable immutable finals for their stated versions.

- `tests/test_roadmap_format.py:test_structural_rewrite_route_reference_separates_local_evidence_generic_transaction_and_stage_paths` — verifies version-aware evidence admission does not broaden the structural writer’s publication scope.

- `tests/test_roadmap_format.py:test_reader_only_evidence_reference_preserves_baseline_and_provenance_boundary` — verifies the format doc names baseline-backed freshness, independent raw provenance, refusal on unavailable state, and no reader-side repair.

- `tests/test_roadmap_format.py:test_reader_only_evidence_reference_separates_v2_presentation_admission_from_candidate_canonicality` — verifies the docs allow only a baseline-equal parseable version-2 source difference while retaining renderer-byte strict generated candidates and immutable finals.

- `tests/test_roadmap_format.py:test_reader_only_evidence_reference_describes_stable_receipt_observation_and_legacy_analysis_creation` — verifies documentation distinguishes version-2 receipt issuance from permitted exact-raw version-1 analysis creation and names guarded, order-independent receipt inspection.

- `tests/test_data_contract.py:test_structural_revision_event_contracts_are_registered_and_documented` — verifies every registered structural lifecycle field remains documented and the closed outcome vocabulary matches `plan_tool/run_log.py`.

- `tests/test_data_contract.py:test_roadmap_evidence_lifecycle_reference_remains_redacted` — verifies the data contract does not describe unregistered source, baseline, reviewer, prompt, or backend content as persisted lifecycle data.

### Verification (non-code step)

1. Run `uv run pytest tests/test_data_contract.py tests/test_roadmap_format.py -q`.
2. Review every supported receipt and analysis version against `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactAnalysis`; confirm the docs distinguish legacy exact-raw behavior from baseline-backed freshness.
3. Review the `ROADMAP_FORMAT.md` marker blocks and examples; confirm each remains valid input for its real parser and renderer.
4. Search the scoped docs and drift guards for raw-digest and version-1 wording; confirm every remaining match is either an explicit legacy rule or immutable provenance, never the only version-2 freshness test.
5. Review `docs/ARCHITECTURE.md` against the three reader entry points; confirm it assigns baseline publication to writers and admission only to readers.

## Acceptance criteria

- `ROADMAP_FORMAT.md` describes every landed receipt and analysis version without presenting a version-1 raw-digest rule as the sole currentness rule.

- `ROADMAP_FORMAT.md` states that canonical freshness, immutable raw provenance, live feedback, source-record facts, and brief facts have separate roles where the landed reader requires them.

- `ROADMAP_FORMAT.md` documents reader refusal for unsafe baseline or evidence state and gives readers no repair or publication authority.

- `ROADMAP_FORMAT.md` distinguishes version-1 exact-raw source readers from version-2 parseable baseline-equal presentation admission, without relaxing canonical rendering for generated patches, proofs, or evidence finals.

- `ROADMAP_FORMAT.md` documents that version-2 receipt issuance and escalation views use a stable reader observation, refuse a pending or changed source pair, and keep mixed-version view results independent of evidence order.

- `DATA_CONTRACT.md` documents every field registered for the six roadmap lifecycle records and retains their redacted-content boundary.

- `docs/ARCHITECTURE.md` identifies the writer-owned baseline contract and the reader-only receipt, analysis, and structural-preflight admission paths.

- All documented receipt and analysis examples parse, render canonically, and retain their expected semantic identities.

- `uv run pytest tests/test_data_contract.py tests/test_roadmap_format.py -q` passes.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2](https://yaml.org/spec/1.2.2/) — Use its representation-equality rules when explaining why formatting and comments do not define stage semantics.

- [hashlib — Secure Hashes and Message Digests](https://docs.python.org/3.13/library/hashlib.html) — Use the SHA-256 reference when documenting immutable provenance and canonical identities.

## Applicable guardrails

- **Reader-only documentation:** The plan’s `## Step intent` limits this step to making version boundaries, refusal rules, and raw-provenance requirements reviewable. Do not add behavior or change reader implementation.

- **Writer ownership:** The plan’s `## Out of scope`, writer-owned baseline behavior, keeps baseline initialization, publication, recovery, and ordinary revision admission outside these files.

- **No repair path:** The plan’s `## Out of scope`, reader-side mutation, requires the docs to describe refusal rather than introduce a reader repair, migration, or acceptance action.

- **Canonicality remains strict:** The plan’s `## Out of scope`, generated structural proof protection, requires documentation to preserve canonical-rendering and malformed-input refusal rather than implying that canonical freshness relaxes them.

## Deferred

- Reader-side repair or migration commands — require a separate design; this step documents refusal only.

- Baseline publication, enrollment, and recovery behavior — remain owned by the earlier implementation steps and the plan’s out-of-scope boundary.

- Retention and hand-edit follow-up workflows — remain with the plan’s named backlog work.
