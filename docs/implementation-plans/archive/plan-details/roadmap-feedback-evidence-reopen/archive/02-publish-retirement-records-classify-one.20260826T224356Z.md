# Step 2 — Publish retirement records, classify one invalidation reason, and bind verified evidence bytes

## Summary

Add the filesystem-backed retirement-record producer and one closed invalidation classifier in `plan_tool/roadmap_evidence_retirement.py`. Update the receipt, impact-analysis, and structural-revision readers so reissued evidence is current only when it matches the selected row’s active attempt. Keep retirement history separate from `plan_tool/roadmap_evidence_store.py`’s active immutable namespaces, using fixed-root no-follow reads and SHA-256 checks for retained evidence bytes. On green, supported retirement evidence is inspectable and classifiable, while substituted, unreadable, invalid, or superseded evidence cannot regain active authority.

## Table of Contents

- [Summary](#summary) — The completed behavior and main design choice.
- [Table of Contents](#table-of-contents) — Links to every section in this detail.
- [Why](#why) — The missing retirement and currentness boundary.
- [Input](#input) — The upstream ledger contract and current evidence readers.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code, documentation, and tests.
- [Implementation](#implementation) — Retirement publication, classification, byte binding, and attempt checks.
- [Tests](#tests) — Focused regression coverage for the new rules.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary storage, hashing, and record-contract references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this step must preserve.
- [Deferred](#deferred) — Later reopen, recovery, and CLI work.

## Why

`plan_tool/roadmap_evidence_store.py:publish_evidence()` and `read_evidence_final()` protect active immutable finals, but they do not provide a supported retirement record, a single invalidation decision, or proof that retained bytes still match a verified response binding. The flagged `publish` helpers in `tests/test_roadmap_escalation_run.py` and `tests/test_roadmap_impact_run.py` cover only active-evidence publication; `plan_tool/roadmap_evidence_retirement.py` and `tests/test_roadmap_evidence_retirement.py` are absent at HEAD. Without this boundary, later recovery could confuse missing, unreadable, malformed, replaced, and retired evidence.

## Input

- **Step 1 response history:** Step 1 provides the landed response provenance and reissue-attempt contract. Read its persisted names and validation rules from `plan_tool/roadmap_artifacts.py`; they override names proposed here.

- **Active immutable evidence:** `plan_tool/roadmap_evidence_store.py:EvidenceNamespace`, `namespace_relative_components()`, `publish_evidence()`, and `read_evidence_final()` define the active receipt namespace and exact-final behavior.

- **Current receipt and analysis checks:** `plan_tool/roadmap_escalation_run.py:current_escalation_receipt()`, `plan_tool/roadmap_impact_run.py:_load_requested_receipt()`, `plan_tool/roadmap_impact_run.py:current_impact_analysis()`, and `plan_tool/roadmap_impact_analysis.py:_receipt_matches_captured_artifact()` are the existing readers that decide whether named evidence remains current.

- **Feedback-sensitive freshness:** `plan_tool/roadmap_source_identity.py:feedback_snapshot()` and `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` retain full feedback state for publication and snapshot rechecks. `plan_tool/roadmap_source_identity.py:canonical_projection()` deliberately excludes feedback.

## Files (creates vs edits)

- **New files:**
  - None. Step 1 creates `plan_tool/roadmap_evidence_retirement.py` and `tests/test_roadmap_evidence_retirement.py`; this step extends both.

- **Existing files (edits only):**
  - `plan_tool/roadmap_evidence_retirement.py` — Add fixed-root history reads, immutable retirement-record publication, the documented archive import, raw-byte verification, and the closed invalidation classifier.
  - `plan_tool/roadmap_evidence_store.py` — Expose only the narrow active-final inspection support needed to distinguish an absent final from a named unreadable one. Keep history out of `EvidenceNamespace`.
  - `plan_tool/roadmap_escalation_run.py` — Carry the selected active attempt through receipt construction, final admission, and currentness inspection.
  - `plan_tool/roadmap_impact_analysis.py` — Bind the receipt attempt into analysis evidence and require it to match the selected snapshot feedback.
  - `plan_tool/roadmap_impact_run.py` — Preserve exact named-final loading and reject an inactive-attempt receipt before analysis publication or reuse.
  - `plan_tool/roadmap_impact_snapshot.py` — Preserve attempt-sensitive snapshot rechecks without changing canonical source identity.
  - `plan_tool/roadmap_source_identity.py` — Keep canonical projections feedback-free while retaining the landed feedback and attempt fields in `feedback_snapshot()`.
  - `plan_tool/roadmap_structural_revision.py` — Require the receipt, analysis, and selected feedback row to bind one active attempt.
  - `plan_tool/roadmap_structural_revision_proof.py` — Check the attempt binding as part of the exact evidence proof.
  - `ROADMAP_FORMAT.md` — Document retirement placement, byte checks, invalidation precedence, and reissued-evidence currentness.
  - `tests/test_roadmap_escalation_run.py` — Cover receipt creation and inspection across active attempts.
  - `tests/test_roadmap_evidence_retirement.py` — Cover retirement publication, traversal safety, classifier precedence, and byte binding.
  - `tests/test_roadmap_evidence_store.py` — Guard the separation between active storage and history storage.
  - `tests/test_roadmap_impact_analysis.py` — Cover attempt copying, hashing, and snapshot matching.
  - `tests/test_roadmap_impact_run.py` — Cover named receipt rejection without analysis publication.
  - `tests/test_roadmap_impact_snapshot.py` — Cover snapshot staleness after an attempt change.
  - `tests/test_roadmap_source_identity.py` — Cover feedback-sensitive snapshots without baseline churn.
  - `tests/test_roadmap_structural_revision.py` — Cover exact-pair and selected-row attempt checks.
  - `tests/test_roadmap_structural_revision_proof.py` — Cover proof-time rejection of an attempt mismatch.

## Implementation

- **Foundational rule: one closed invalidation decision with one typed locator.** Keep retirement publication, fixed-root reads, raw-byte checks, `EvidenceLocator`, and invalidation classification in `plan_tool/roadmap_evidence_retirement.py`. `RetirementRecordLocator(record_final)` is the only locator for `retired`; `ActiveReceiptLocator(receipt_final)` is the only locator for `receipt-unreadable` and `receipt-invalid`. Every producer and later admission reader must use this boundary rather than recreating its precedence or accepting a path.

- **Keep history outside active evidence storage.** `plan_tool/roadmap_evidence_store.py:publish_evidence()` and `read_evidence_final()` remain the active opaque-evidence API. Do not add retirement history as an `EvidenceNamespace` or use the generic active publisher as evidence that a history path was traversed safely.

- **Accept evidence only below the fixed retirement root.** Read retirement records and retained receipt bytes only below `<roadmap-root>/.plan-tool/evidence/history/retirements/`. Require every traversed component and both leaves to be contained, non-symlink regular files, and reject descriptor-read, containment, and type failures without trying another path or reason.

- **Publish immutable retirement records.** Validate the Step 1 `RetiredEvidenceRecord` contract, receipt final, evidence kind, retained relative path, and retained raw-byte digest before publication. Require the named receipt to be absent from the active escalation namespace. An occupied record is reusable only when its complete bytes match the candidate; never amend an existing record or change feedback, active evidence, or roadmap artifacts.

- **Limit the archive import to its one documented source.** Admit a source only from `<roadmap-root>/.plan-tool/evidence/history/2026-08-26-v1-retirement-archive/`, using the same no-follow and containment rules. Copy verified source bytes into the fixed retirement root before publishing the ordinary immutable record. Do not alter the archive, accept another archive root, or treat a copied-but-unrecorded file after interruption as authority.

- **Make classifier outcomes mutually exclusive.** A `RetirementRecordLocator` may return `retired` only for a valid named retirement record. If that record is malformed, unsafe, unreadable, or its retained bytes do not match, return a refusal rather than falling back. An `ActiveReceiptLocator` may return `receipt-unreadable` only when its named active regular final exists but raw-byte reading fails; it may return `receipt-invalid` only after raw bytes were read and strict decoding, receipt parsing, final-name validation, source-path validation, or semantic validation fails. A missing final, a fresh or resolved receipt, an unavailable current source, or a locator/reason mismatch has no reopen admission.

- **Bind verified provenance to bytes, not names.** Require retained or successfully read receipt bytes to SHA-256-match Step 1’s verified response binding before reporting a byte-verified route. An unreadable final and a readable digest mismatch remain distinct from verified evidence and leave any explicit attestation decision to Step 3.

- **Bind reissued receipts at both admission points.** Update `plan_tool/roadmap_escalation_run.py:_resolve_preflight()`, `run_roadmap_escalation_receipt()`, and `_same_receipt_admission()` so the selected row’s active attempt participates in receipt construction and final equality. Preserve the absent-attempt behavior for ordinary pre-ledger rows and existing version-2 finals.

- **Carry attempt matching through every currentness reader.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `build_impact_analysis()`, `_receipt_matches_captured_artifact()`, and `version2_analysis_matches()` so the attempt changes copied analysis identity and currentness. Keep `plan_tool/roadmap_impact_run.py:_load_requested_receipt()` exact-final and no-scan; an inactive attempt must not publish or reuse analysis evidence.

- **Require one attempt across structural evidence.** Extend `plan_tool/roadmap_structural_revision.py:_require_pair_binding()` and `_current_selected_slice()` so the receipt, analysis, and selected feedback row agree on the active attempt. Extend `plan_tool/roadmap_structural_revision_proof.py:_require_evidence_binding()` so the proof cannot rely on a preflight-only attempt check.

- **Preserve the source-identity split.** Do not add response history or attempts to `plan_tool/roadmap_source_identity.py:canonical_projection()`. Keep `feedback_snapshot()`, `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot()`, and `recheck_roadmap_impact_snapshot()` sensitive to the parsed feedback change through their existing full-feedback and artifact-digest bindings.

- **Leave generic feedback-snapshot consumers unchanged.** `plan_tool/roadmap.py:recheck_feedback_snapshot()`, `plan_tool/roadmap_revision_publish.py:_require_feedback_snapshot()`, `plan_tool/roadmap_revision_run.py`, and `plan_tool/roadmap_structural_revision_run.py` already consume the full `feedback_snapshot()` result. Do not widen this step to refactor those callers.

- **Document the same rules the code enforces.** Update `ROADMAP_FORMAT.md:## Structural escalation receipts`, `### Versioned receipt reference`, `## Impact-routing analyses`, and `### Versioned analysis reference` with the fixed retirement boundary, classifier order, byte-verification rule, and matching-active-attempt rule.

## Tests

### Tests for this step

- `tests/test_roadmap_evidence_retirement.py::test_retirement_history_accepts_only_contained_regular_no_follow_files` — Links, non-regular leaves, traversal escapes, and read failures refuse.

- `tests/test_roadmap_evidence_retirement.py::test_retirement_record_requires_active_receipt_absence_and_exact_immutable_reuse` — Publication preserves active evidence and reuses an occupied record only for matching bytes.

- `tests/test_roadmap_evidence_retirement.py::test_documented_v1_archive_import_copies_only_verified_contained_bytes` — The documented archive creates one fixed-root retirement record without widening accepted source paths or changing the archive.

- `tests/test_roadmap_evidence_retirement.py::test_invalidation_classifier_uses_retired_unreadable_invalid_precedence` — Valid retirement wins, while unreadable, invalid, and missing evidence remain distinct.

- `tests/test_roadmap_evidence_retirement.py::test_invalidation_locator_is_reason_specific_and_never_a_path` — Only a retirement-record final can classify `retired`, only an active receipt final can classify unreadable or invalid evidence, and no reopen caller supplies a retained path.

- `tests/test_roadmap_evidence_retirement.py::test_invalid_retirement_record_never_falls_back_to_another_reason` — Unsafe or malformed retirement history refuses instead of producing an alternate reason.

- `tests/test_roadmap_evidence_retirement.py::test_verified_binding_requires_matching_retained_or_active_raw_bytes` — A final name alone or a digest mismatch cannot take the verified route.

- `tests/test_roadmap_evidence_store.py::test_retirement_history_is_not_an_active_evidence_namespace` — Active opaque-storage APIs do not become a history traversal API.

- `tests/test_roadmap_escalation_run.py::test_reissued_receipt_binds_the_same_active_attempt_at_both_preflights` — Receipt publication refuses if the attempt changes before final admission, while the ordinary absent-attempt path remains valid.

- `tests/test_roadmap_escalation_run.py::test_current_escalation_receipt_marks_a_prior_reissue_attempt_resolved` — Earlier receipt finals remain inspectable but are not fresh.

- `tests/test_roadmap_impact_analysis.py::test_analysis_copies_and_hashes_the_receipt_reissue_attempt` — A new attempt changes analysis identity and requires selected-feedback agreement.

- `tests/test_roadmap_impact_run.py::test_attempt_mismatched_named_receipt_never_publishes_or_reuses_analysis` — Named receipt loading stays exact and produces no analysis final for an inactive attempt.

- `tests/test_roadmap_impact_snapshot.py::test_recheck_refuses_a_changed_active_reissue_attempt` — Snapshot recheck detects the feedback change.

- `tests/test_roadmap_source_identity.py::test_reissue_attempt_changes_feedback_snapshot_not_canonical_source_identity` — Baseline identity stays stable while feedback-sensitive checks change.

- `tests/test_roadmap_structural_revision.py::test_structural_preflight_requires_matching_receipt_analysis_and_active_attempt` — An otherwise exact pair with an earlier attempt is rejected.

- `tests/test_roadmap_structural_revision_proof.py::test_structural_proof_rechecks_the_selected_active_attempt` — The proof cannot rely on a preflight-only attempt check.

- `tests/test_roadmap_evidence_retirement.py::test_roadmap_format_retirement_rules_match_the_landed_contract` — The documented record and classifier rules match the code-owned contract.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A retirement record is accepted only from the fixed history root through a contained, regular, no-follow path, with matching retained bytes and no active receipt final.

- The documented version-1 import accepts only its contained archive source, copies verified bytes into the fixed root, and creates the same retirement record without accepting another history location.

- An unsafe or invalid retirement record refuses and never falls back to `receipt-unreadable` or `receipt-invalid`.

- The classifier accepts `RetirementRecordLocator(record_final)` only for `retired` and `ActiveReceiptLocator(receipt_final)` only for active unreadable or invalid evidence; no reopen locator is a filesystem path.

- The classifier returns `receipt-unreadable` only before raw bytes are available, `receipt-invalid` only after raw bytes are available, and no reopen reason for missing, fresh, resolved, or source-unavailable evidence.

- A byte-verified route requires raw receipt bytes whose SHA-256 equals the stored verified binding.

- A receipt issued for an active reissue attempt includes that same attempt in its identity; ordinary version-2 evidence without an attempt remains valid.

- Receipt inspection, impact analysis, structural preflight, and structural proof reject an attempt that is no longer active while leaving its immutable final inspectable.

- Canonical source identity remains unchanged by response history, while feedback snapshots and impact snapshots detect an active-attempt change.

- `ROADMAP_FORMAT.md` states the fixed retirement boundary, invalidation precedence, byte-verification rule, and active-attempt currentness rule.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Define strict, frozen, extra-forbidden retirement-record values.

- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Implement deterministic field and cross-record validation.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind retained evidence and semantic identities with SHA-256.

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Implement no-follow reads and durable immutable publication.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep retirement records strict and interoperable.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s `## Step intent` limits this step to retirement evidence, byte checks, and deterministic classification. Do not add a general history browser or feedback editor.

- **No ordinary re-escalation** — The plan’s `## Out of scope` keeps normal receipt creation outside the retirement classifier and later recovery path.

- **Preserve ordinary protections** — The plan’s `## Plan intent` requires a history-preserving exception without weakening already-responded protection for rows outside this evidence-bound path.

## Deferred

- CLI flags, confirmation handling, and safe review rendering — Step 5 owns the operator-facing command surface.

- Reopen-candidate admission and operator-attestation persistence — Step 3 owns the in-memory decision path.

- Atomic reopen publication, terminal-log binding, and recovery — Step 4 owns the guarded write path.

- General roadmap revision retention — Keep the broader #242 redesign outside this bounded evidence path.
