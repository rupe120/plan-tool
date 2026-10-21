# Step 2 — Publish retirement records, classify one invalidation reason, and bind verified evidence bytes

## Summary

Add the filesystem-backed retirement-record producer and one closed invalidation classifier in `plan_tool/roadmap_evidence_retirement.py`. Update active-evidence readers in the escalation, impact-analysis, and structural-revision paths so a reissued receipt is current only for its matching active attempt. Keep retirement history separate from `plan_tool/roadmap_evidence_store.py`’s ordinary active namespaces: history reads must use the fixed no-follow root and verify raw bytes. On green, a valid retirement is inspectable and classifiable, while substituted, unreadable, invalid, or superseded evidence cannot regain active authority.

## Table of Contents

- [Summary](#summary) — The completed behavior and central design choice.
- [Table of Contents](#table-of-contents) — Links to the sections in this detail.
- [Why](#why) — The missing retirement and currentness boundary.
- [Input](#input) — The upstream history contract and existing evidence readers.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code, documentation, and tests.
- [Implementation](#implementation) — Retirement publication, classification, byte binding, and attempt checks.
- [Tests](#tests) — Focused behavior and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary contract and storage references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this step must preserve.
- [Deferred](#deferred) — Later reopen, recovery, and CLI work.

## Why

Active receipt storage can publish and read immutable finals, but it has no supported retirement record, no closed invalidation result, and no way to prove that retained bytes still match a verified response binding. The flagged `publish` helpers in `tests/test_roadmap_escalation_run.py` and `tests/test_roadmap_impact_run.py` cover the existing active-evidence publishers only; `plan_tool/roadmap_evidence_retirement.py` and its test module are absent at HEAD, so this step remains unimplemented. Without this boundary, a recovery path could mistake a missing, unreadable, malformed, or substituted final for the same condition.

## Input

- **Step 1 response history:** Step 1 provides the typed provenance and reissue-attempt identity that this step compares. Treat the landed contract as the source of truth for field names and validation.
- **Active evidence store:** `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `namespace_relative_components()`, `read_evidence_final()`, and `publish_evidence()` define the active immutable receipt namespace and exact-final behavior.
- **Receipt and analysis admission:** `plan_tool/roadmap_escalation_run.py:current_escalation_receipt()`, `plan_tool/roadmap_impact_run.py:_load_requested_receipt()`, and `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact()` already decide whether named receipt evidence can support current work.
- **Current artifact state:** `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` and `plan_tool/roadmap_source_identity.py:feedback_snapshot()` retain feedback-sensitive state without making it part of canonical source identity.

## Files (creates vs edits)

- **New files:**
  - None — Step 1 creates `plan_tool/roadmap_evidence_retirement.py` and `tests/test_roadmap_evidence_retirement.py`; this step extends them.

- **Existing files (edits only):**
  - `plan_tool/roadmap_evidence_retirement.py` — Add fixed-root no-follow history traversal, immutable retirement-record publication, raw-byte verification, and the closed invalidation classifier.
  - `plan_tool/roadmap_evidence_store.py` — Expose only the minimal active-namespace path or exact-name support the retirement service needs; keep history outside `EvidenceNamespace`, `publish_evidence()`, and `read_evidence_final()`.
  - `plan_tool/roadmap_escalation_run.py` — Bind a new receipt to the selected row’s active reissue attempt and make `current_escalation_receipt()` resolve a prior attempt.
  - `plan_tool/roadmap_impact_analysis.py` — Copy the receipt attempt into analysis evidence and reject a receipt that does not match the selected snapshot feedback.
  - `plan_tool/roadmap_impact_run.py` — Keep named-final, no-scan receipt loading and prevent a mismatched attempt from publishing or reusing analysis evidence.
  - `plan_tool/roadmap_impact_snapshot.py` — Preserve feedback-sensitive snapshot rechecks for attempt changes without changing canonical source identity rules.
  - `plan_tool/roadmap_source_identity.py` — Keep `canonical_projection()` feedback-free and ensure `feedback_snapshot()` retains the landed attempt and history fields.
  - `plan_tool/roadmap_structural_revision.py` — Require the receipt, analysis, and selected feedback row to bind the same active attempt.
  - `plan_tool/roadmap_structural_revision_proof.py` — Recheck the attempt identity as part of exact evidence proof, not only during preflight.
  - `ROADMAP_FORMAT.md` — Document retirement-record placement, byte checks, invalidation precedence, and reissued-evidence currentness.
  - `tests/test_roadmap_escalation_run.py` — Cover receipt publication and inspection across active attempts.
  - `tests/test_roadmap_evidence_retirement.py` — Cover retirement publication, traversal safety, classifier precedence, and byte binding.
  - `tests/test_roadmap_evidence_store.py` — Guard the active-store versus history-store boundary.
  - `tests/test_roadmap_impact_analysis.py` — Cover attempt copying and snapshot matching.
  - `tests/test_roadmap_impact_run.py` — Cover rejected named receipt admission without analysis publication.
  - `tests/test_roadmap_impact_snapshot.py` — Cover stale snapshot detection for attempt changes.
  - `tests/test_roadmap_source_identity.py` — Cover feedback-sensitive snapshots without baseline churn.
  - `tests/test_roadmap_structural_revision.py` — Cover exact-pair and selected-row attempt checks.
  - `tests/test_roadmap_structural_revision_proof.py` — Cover proof-time rejection of an attempt mismatch.

## Implementation

- **Keep one classifier owner.** Put retirement publication, no-follow reads, and invalidation classification in `plan_tool/roadmap_evidence_retirement.py`. The producer and later readers must call the same classifier or traversal helper so they cannot disagree about a retained final.

- **Use a fixed history root.** Accept retirement records and retained receipt bytes only below `<roadmap-root>/.plan-tool/evidence/history/retirements/`. Walk every component and both leaves without following links; require regular files, containment below the resolved root, and successful descriptor reads. Reject links, non-regular entries, containment failures, and read failures without trying another reason.

- **Keep active and historical storage separate.** `plan_tool/roadmap_evidence_store.py:publish_evidence()` and `read_evidence_final()` remain the active opaque-evidence API. Do not add the history directory as a normal `EvidenceNamespace` or use the generic publisher to claim no-follow safety.

- **Import only the documented archive.** Add one model-free importer for `<roadmap-root>/.plan-tool/evidence/history/2026-08-26-v1-retirement-archive/`. It must no-follow-read one contained regular source file, verify the requested receipt final and bytes, durably copy those bytes into the fixed retirement root, then publish the ordinary immutable record. It accepts no other history root, does not alter the source archive, and leaves an unrecorded copied file harmless if interruption occurs before record publication.

- **Publish one immutable retirement record.** The producer must accept one hash-named record only after validating its record identity, evidence kind, retained relative path, retained raw-byte digest, and absence of the named receipt from the active escalation namespace. Reusing an occupied record is valid only when its complete bytes match the candidate; never amend an existing record or mutate feedback, active evidence, or roadmap artifacts.

- **Make invalidation mutually exclusive.** Classify a valid retirement first. With no valid retirement record, classify an active final as `receipt-unreadable` only when a named regular final exists but reading raw bytes fails; classify `receipt-invalid` only after raw bytes were read and strict decoding or receipt validation fails. A missing final, a valid current receipt, a resolved receipt, or an unavailable source supplies no reopen reason. An invalid retirement record is a refusal, not a reason to fall back.

- **Bind verified routes to raw bytes.** Require retained or successfully read receipt bytes to SHA-256-match the verified response binding before treating the route as byte-verified. An unreadable final and any digest mismatch remain distinct from a verified route and must leave later attestation handling to Step 3.

- **Bind newly reissued receipts twice.** In `plan_tool/roadmap_escalation_run.py:_resolve_preflight()` and the publication path in `run_roadmap_escalation_receipt()`, carry the selected row’s active attempt into receipt construction and the final admission comparison. Preserve the absent-attempt path for ordinary rows so existing version-2 evidence remains readable and semantically stable.

- **Apply attempt matching at every currentness reader.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `_receipt_matches_captured_artifact()`, and the `build_impact_analysis()` payload; update `plan_tool/roadmap_impact_run.py:_load_requested_receipt()` callers without weakening their exact-final rule. In `plan_tool/roadmap_escalation_run.py:current_escalation_receipt()`, `plan_tool/roadmap_structural_revision.py:_require_pair_binding()` and `_current_selected_slice()`, and `plan_tool/roadmap_structural_revision_proof.py:_require_evidence_binding()`, treat a prior or missing attempt as inspectable but not current.

- **Preserve the existing source boundary.** `plan_tool/roadmap_source_identity.py:canonical_projection()` must still omit all feedback history. `feedback_snapshot()`, `RoadmapImpactSnapshot`, and `recheck_roadmap_impact_snapshot()` must still detect an attempt change through captured feedback-bearing artifact state.

- **Document the same precedence.** Update `ROADMAP_FORMAT.md`’s `## Structural escalation receipts` and `## Impact-routing analyses` sections with the history-record boundary, the closed invalidation order, and the rule that only the matching active attempt makes reissued evidence current.

## Tests

### Tests for this step

- `tests/test_roadmap_evidence_retirement.py::test_retirement_history_accepts_only_contained_regular_no_follow_files` — Links, non-regular leaves, traversal escapes, and descriptor-read failures refuse.
- `tests/test_roadmap_evidence_retirement.py::test_retirement_record_requires_active_receipt_absence_and_exact_immutable_reuse` — Publication preserves active evidence and accepts an occupied record only when its bytes match.
- `tests/test_roadmap_evidence_retirement.py::test_documented_v1_archive_import_copies_only_verified_contained_bytes` — The recorded version-1 archive can create one fixed-root retirement record without widening accepted history paths or mutating its source.
- `tests/test_roadmap_evidence_retirement.py::test_invalidation_classifier_uses_retired_unreadable_invalid_precedence` — A valid retirement wins; raw-read failure, post-read invalidity, and missing evidence remain distinct.
- `tests/test_roadmap_evidence_retirement.py::test_invalid_retirement_record_never_falls_back_to_another_reason` — A malformed or unsafe history record refuses rather than producing an alternate invalidation result.
- `tests/test_roadmap_evidence_retirement.py::test_verified_binding_requires_matching_retained_or_active_raw_bytes` — A digest mismatch cannot take the byte-verified route.
- `tests/test_roadmap_evidence_store.py::test_history_retirement_is_not_a_generic_evidence_namespace` — Active opaque-storage helpers do not become the history traversal API.
- `tests/test_roadmap_escalation_run.py::test_reissued_receipt_binds_the_same_active_attempt_at_both_preflights` — Publication refuses if the attempt changes before the final admission and preserves the ordinary absent-attempt path.
- `tests/test_roadmap_escalation_run.py::test_current_escalation_receipt_resolves_a_prior_reissue_attempt` — Earlier receipt finals remain readable but never return `fresh`.
- `tests/test_roadmap_impact_analysis.py::test_analysis_copies_and_hashes_the_receipt_reissue_attempt` — A new attempt changes analysis identity, while raw source digest remains outside presentation-tolerant currentness.
- `tests/test_roadmap_impact_run.py::test_attempt_mismatched_named_receipt_never_publishes_or_reuses_analysis` — Named receipt loading stays exact and produces no analysis final for an inactive attempt.
- `tests/test_roadmap_impact_snapshot.py::test_recheck_refuses_a_changed_active_reissue_attempt` — Snapshot recheck detects the feedback-state change.
- `tests/test_roadmap_source_identity.py::test_reissue_attempt_changes_feedback_snapshot_not_canonical_source_identity` — Baseline identity stays stable while feedback-sensitive publication checks change.
- `tests/test_roadmap_structural_revision.py::test_structural_preflight_requires_matching_receipt_analysis_and_active_attempt` — An exact pair with an earlier attempt is rejected.
- `tests/test_roadmap_structural_revision_proof.py::test_structural_proof_rechecks_the_selected_active_attempt` — Proof cannot rely on a preflight-only attempt check.
- `tests/test_roadmap_evidence_retirement.py::test_roadmap_format_retirement_rules_match_the_landed_contract` — The documented record fields and classifier outcomes match the code-owned contract.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A retirement record is accepted only from the fixed history root through a contained, regular, no-follow path, with matching retained bytes and no active receipt final.
- The exclusive documented-version-1 import accepts only one contained regular source from its named archive root, copies verified bytes into the fixed root, and creates the same retirement record without accepting another history location.
- An unsafe or invalid retirement record returns a refusal and never falls back to `receipt-unreadable` or `receipt-invalid`.
- The classifier returns `receipt-unreadable` only before raw bytes are available, `receipt-invalid` only after raw bytes are available, and no reopen reason for a missing or otherwise current final.
- A byte-verified route requires raw receipt bytes whose SHA-256 equals the stored verified binding.
- A receipt issued for an active reissue attempt includes that same attempt in its identity; ordinary version-2 evidence without an attempt remains valid.
- Receipt inspection, impact analysis, structural preflight, and structural proof reject an attempt that is no longer active while leaving its immutable final inspectable.
- Canonical source identity remains unchanged by response history, while feedback snapshots and impact snapshots detect an active-attempt change.
- `ROADMAP_FORMAT.md` states the fixed retirement boundary, invalidation precedence, and active-attempt currentness rule.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen, extra-forbidden models for immutable retirement data.
- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Define deterministic field and cross-record validation.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind exact evidence bytes and semantic identities with SHA-256.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Implement descriptor-based no-follow reads and durable immutable publication.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep retirement records strict and interoperable.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s “## Step intent” limits this work to supported retirement evidence and deterministic classification; do not add a general history browser or feedback editor.
- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps ordinary evidence issuance outside the retirement classifier and later reopen path.
- **Preserve ordinary protections** — The plan’s “## Plan intent” requires history-preserving recovery without weakening already-responded behavior for rows that do not meet this step’s evidence conditions.

## Deferred

- CLI flags, confirmation handling, and safe review rendering — Step 5 owns the operator-facing command surface.
- Reopen-candidate admission and operator-attestation persistence — Step 3 owns those state changes.
- Atomic reopen publication, run-log completion binding, and recovery — Step 4 owns the journaled write path.
- General roadmap revision retention — Keep the broader #242 redesign outside this bounded evidence path.
