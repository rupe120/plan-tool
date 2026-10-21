# Step 1 — Define active response-ledger pointers, operator attestations, and per-attempt identities

## Summary

Define the typed roadmap-feedback history that binds an active response to one immutable ledger entry and gives each guarded reopen a redacted history record plus its own attempt identity. Update `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_gates.py`, the receipt and impact-analysis contracts, both response writers, and `ROADMAP_FORMAT.md`; add a strict evidence-retirement contract leaf. Keep version-2 receipt and analysis finals readable when they lack an attempt identity, while making a new reissued final include its active identity in its semantic hash. On green, a response cannot inherit stale provenance, a cleared ledgered row cannot silently look new, and every generated response has explicit, testable history.

## Table of Contents

- [Summary](#summary) — The completed behavior and main contract changes.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current provenance gap this step closes.
- [Input](#input) — Existing artifact, evidence, and snapshot contracts this step extends.
- [Files (creates vs edits)](#files-creates-vs-edits) — New contract leaf and scoped edits.
- [Implementation](#implementation) — Required ledger, provenance, and attempt-identity rules.
- [Tests](#tests) — Focused contract and regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary references for strict persisted contracts.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that bind this work.
- [Deferred](#deferred) — Later workflow and publication work.

## Why

`FeedbackRow.proposed_response` currently carries only text, while `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` move selected feedback to `awaiting-review`. That leaves no durable way to tell which immutable evidence, if any, produced a response, and `plan_tool/roadmap_source_identity.py:feedback_snapshot()` can only detect that feedback changed. This step makes that association explicit before the later reopen flow needs to judge or preserve it.

## Input

- **Roadmap feedback rows:** `plan_tool/roadmap_artifacts.py:FeedbackRow`, `_parse_feedback_rows()`, and `_feedback_mapping()` currently define the persisted feedback shape and optional `proposed_response`.
- **Feedback freshness:** `plan_tool/roadmap_source_identity.py:canonical_projection()` deliberately excludes all feedback from baseline identity, while `feedback_snapshot()` retains the complete ordered feedback collection for publication rechecks.
- **Immutable evidence:** `plan_tool/roadmap_escalation.py:EscalationReceipt` and `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence` currently accept only schema version 2 and derive their final names from semantic fields.
- **Response writers:** `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `_apply_stage_responses()` write generic responses; `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` writes the structural-response path.
- **Snapshot boundary:** `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot()` and `recheck_roadmap_impact_snapshot()` must continue to reject a changed captured artifact without making feedback history part of the canonical source baseline.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_evidence_retirement.py` — Define strict, immutable retirement-record and operator-attestation contract values shared by later readers and publishers.
  - `tests/test_roadmap_evidence_retirement.py` — Cover closed schemas, semantic identities, and redaction rules for those values.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Extend `FeedbackRow`, feedback parsing, and rendering with response-ledger, active-pointer, and reissue-attempt rules.
  - `plan_tool/roadmap_gates.py` — Preserve predecessor response, pointer, reopen-history, and attempt facts except through the named writer and guarded-reopen transitions.
  - `plan_tool/roadmap_escalation.py` — Carry an optional active reissue identity through receipt construction, validation, and semantic hashing.
  - `plan_tool/roadmap_escalation_selection.py` — Refuse ledgered cleared history and admit only the matching guarded-reopen attempt from the first commit that permits a clear.
  - `plan_tool/roadmap_impact_analysis.py` — Copy and validate the receipt attempt identity in analysis evidence and currentness checks.
  - `plan_tool/roadmap_impact_snapshot.py` — Preserve the active-attempt facts needed to compare a receipt against its captured selected feedback row.
  - `plan_tool/roadmap_revision_patch.py` — Make generic response writers append an unbound ledger entry and set its active pointer with the response.
  - `plan_tool/roadmap_revision.py` — Apply the same cleared-history admission rule before local revision preflight.
  - `plan_tool/roadmap_source_identity.py` — Keep feedback history out of baseline identity while retaining it in feedback snapshots.
  - `plan_tool/roadmap_structural_revision_patch.py` — Make the exact source patch add a verified ledger entry and active pointer only for the selected response.
  - `plan_tool/roadmap_structural_revision.py` — Apply the same cleared-history admission rule in selected-slice loading.
  - `ROADMAP_FORMAT.md` — Document the feedback-history fields, legacy compatibility, and version-2 attempt-identity rules.
  - `tests/test_roadmap_artifacts.py` — Add parser, renderer, pointer, legacy, and manual-edit coverage.
  - `tests/test_roadmap_escalation.py` — Add legacy and reissued receipt semantic-identity coverage.
  - `tests/test_roadmap_escalation_selection.py` — Reject a ledgered manual clear while permitting only its matching guarded-reopen attempt.
  - `tests/test_roadmap_impact_analysis.py` — Add attempt propagation and selected-feedback matching coverage.
  - `tests/test_roadmap_impact_snapshot.py` — Add snapshot and recheck coverage for response-history changes.
  - `tests/test_roadmap_format.py` — Keep the format examples and field inventories bound to code.
  - `tests/test_roadmap_gates.py` — Prove generated artifacts cannot strip or alter established response-history facts.
  - `tests/test_roadmap_revision_patch.py` — Cover unbound ledger entries from generic response writers.
  - `tests/test_roadmap_revision.py` — Cover local-revision refusal of cleared history and admission of the matching guarded attempt.
  - `tests/test_roadmap_source_identity.py` — Prove baseline exclusion and feedback-snapshot inclusion.
  - `tests/test_roadmap_structural_revision_patch.py` — Cover verified structural provenance and selected-row-only source edits.
  - `tests/test_roadmap_structural_revision.py` — Cover the same selected-slice rule for structural revision.

## Implementation

- **Make the active response a checked pointer.** Extend `plan_tool/roadmap_artifacts.py:FeedbackRow` with an optional active response-instance pointer, an append-only response-ledger collection, an append-only redacted reopen-history collection, and an optional reissue-attempt identity. A ledger entry must retain its unique response-instance identity, exact response text, SHA-256 digest, and one provenance class. A reopen record must retain its response identity and digest, original provenance class, separate admission route, classifier result, safe evidence or retirement identity, and fresh attempt. An operator-attested route embeds its linked immutable attestation; a verified route has none. Neither record stores prior response text or attestation prose.

- **Validate the whole ledger at parse time.** In `_parse_feedback_rows()`, reject duplicate instance identities, dangling or ambiguous active pointers, missing pointers for a ledgered nonblank active response, and pointers whose selected entry’s text or digest does not match `proposed_response`. This is artifact shape validation, not a later gate finding.

- **Preserve the legacy boundary.** A pre-ledger row with no ledger, reopen-history, pointer, or attempt fields stays readable under its current manual behavior. Do not fabricate history for a legacy response during parsing, rendering, baseline comparison, or an ordinary manual edit.

- **Allow only the clear transition for ledgered manual edits.** A ledgered row may clear its active response only as the paired move to `open` with no active pointer; retain the ledger entry and any earlier reopen records unchanged. Reject a nonblank manual replacement that does not arrive through a response writer, since it could otherwise inherit an earlier instance’s provenance. This clear is not an ordinary receipt or revision admission path.

- **Ship the clear fence with the clear.** In the same step, update `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, and `plan_tool/roadmap_structural_revision.py:_current_selected_slice()`. A genuine pre-ledger unanswered row stays ordinary; a ledgered clear refuses until a guarded reopen record and its matching fresh attempt exist. Do not postpone this rule to the later admission step, because the clear becomes a valid artifact as soon as this step lands.

- **Keep ordinary retained states intact.** Continue to accept the established `open`-with-response and `deferred`-with-response shapes. A ledgered nonblank response still needs its matching pointer regardless of state; later reopen eligibility remains outside this step.

- **Protect history against generated stripping.** Extend `plan_tool/roadmap_gates.py:check_feedback_integrity()` to compare every predecessor ledger, pointer, reopen record, and attempt fact. Permit only an append from the named response writer and the guarded reopen’s paired preservation-and-attempt transition; reject removal, mutation, or a new legacy-shaped candidate. Direct pre-ledger rows remain outside this predecessor rule because they have no prior history to preserve.

- **Define provenance without pretending to verify it.** In new `plan_tool/roadmap_evidence_retirement.py`, define frozen, extra-forbidden values for verified receipt bindings, unbound generated responses, and operator-attested recovery bindings. An `OperatorAttestation` records receipt-safe selector and evidence facts, response-instance identity, response digest, and closed invalidation reason, but never stores or renders the old response text. A later guarded reopen persists it only as the linked operator-attested route, beside—not in place of—any original verified binding.

- **Keep retirement contracts separate from filesystem behavior.** Let `plan_tool/roadmap_evidence_retirement.py` own strict record validation, canonical rendering, and semantic identity for `RetiredEvidenceRecord`. Leave no-follow traversal, publication, and invalidation classification to step 2.

- **Mint one record before exposing each generated response.** Update `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `_apply_stage_responses()` so generic local and stage feedback responses receive a fresh response instance, an unbound provenance record, and an active pointer in the same candidate artifact. Preserve unselected feedback rows and their existing history exactly.

- **Bind structural responses to the evidence that produced them.** Update `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` to add a fresh selected-row entry with verified receipt final, raw receipt digest, and the receipt’s reissue-attempt identity. Retain its exact-source-patch rule: only the selected feedback row gains response-history fields, response text, and `awaiting-review` state.

- **Keep source identity feedback-independent.** `plan_tool/roadmap_source_identity.py:canonical_projection()` must continue to omit all feedback data, including ledger and attempt fields. `feedback_snapshot()` must include those fields so `plan_tool/roadmap.py:recheck_feedback_snapshot()` and `plan_tool/roadmap_revision_publish.py:_require_feedback_snapshot()` detect a concurrent history change without direct changes to those callers.

- **Make reissue identity part of new evidence identity only.** Extend `plan_tool/roadmap_escalation.py:_ReceiptSemanticFields`, `build_receipt()`, `_receipt_semantic_fields()`, and `receipt_semantic_id_from_facts()` with an optional `reissue_attempt_id`. An absent value must preserve the current version-2 preimage and final name; a new active attempt must be nonblank and included in the semantic preimage.

- **Carry the same identity into analysis.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `build_impact_analysis()`, and `_receipt_matches_captured_artifact()` so analysis records copy the receipt attempt identity and refuse a receipt whose identity does not match the captured selected feedback row. Update `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` support only as needed to expose this comparison from the already captured artifact.

- **Document code-owned fields and lifecycle rules.** Update `ROADMAP_FORMAT.md` sections covering feedback lifecycle, escalation receipts, and impact-routing analyses. State that legacy version-2 evidence omits an attempt identity, a new reissued final includes it, and history is preserved rather than rewritten. Keep copied examples executable through the real parser and renderer.

## Tests

### Tests for this step

- `tests/test_roadmap_artifacts.py::test_ledgered_active_response_requires_unique_matching_pointer` — A nonblank ledgered response selects exactly one entry with matching text and SHA-256 digest.
- `tests/test_roadmap_artifacts.py::test_ledgered_duplicate_dangling_missing_and_mismatched_pointers_raise` — Each invalid active-pointer shape fails parsing.
- `tests/test_roadmap_artifacts.py::test_legacy_feedback_without_ledger_preserves_current_manual_shape` — Existing unledgered feedback remains readable without fabricated provenance.
- `tests/test_roadmap_artifacts.py::test_ledgered_manual_clear_requires_open_and_removes_only_active_pointer` — A clear keeps immutable ledger history and cannot leave a cleared awaiting-review response.
- `tests/test_roadmap_artifacts.py::test_reopen_history_is_redacted_immutable_and_matches_attempt` — A persisted reopen record contains safe route facts, never old response text, and points to the row’s fresh attempt.
- `tests/test_roadmap_artifacts.py::test_operator_attested_reopen_history_keeps_original_provenance_and_linked_attestation` — An attested route keeps both provenance facts distinct and immutable.
- `tests/test_roadmap_artifacts.py::test_ledgered_manual_nonblank_replacement_raises` — Hand edits cannot reuse an old ledger entry for changed text.
- `tests/test_roadmap_artifacts.py::test_feedback_ledger_and_reissue_attempt_round_trip` — All roadmap artifact renderers preserve typed history and attempt fields.
- `tests/test_roadmap_escalation.py::test_legacy_v2_receipt_omits_absent_reissue_attempt_from_semantic_preimage` — Existing receipt bytes and final names remain valid.
- `tests/test_roadmap_escalation.py::test_reissued_v2_receipt_requires_attempt_and_changes_semantic_id` — A nonempty active attempt changes a new receipt’s semantic identity.
- `tests/test_roadmap_impact_analysis.py::test_analysis_copies_receipt_reissue_attempt_identity` — Analysis evidence retains the receipt’s attempt identity and changes its own final accordingly.
- `tests/test_roadmap_impact_analysis.py::test_analysis_rejects_receipt_attempt_not_matching_selected_feedback` — Earlier or missing receipt attempts cannot become current after a reopen.
- `tests/test_roadmap_impact_snapshot.py::test_recheck_refuses_changed_response_ledger_or_reissue_attempt` — Snapshot recheck catches history changes through captured artifact data.
- `tests/test_roadmap_source_identity.py::test_baseline_projection_excludes_response_history_but_feedback_snapshot_includes_it` — Feedback history does not change canonical source identity but does change the publication snapshot.
- `tests/test_roadmap_revision_patch.py::test_generic_response_writers_append_unbound_instance_and_set_active_pointer` — Local and stage response candidates add one fresh unbound entry before exposing text.
- `tests/test_roadmap_revision_patch.py::test_generic_response_writer_preserves_unselected_response_history` — Unselected rows keep their pointers, ledger entries, and prose unchanged.
- `tests/test_roadmap_structural_revision_patch.py::test_structural_patch_adds_verified_response_binding_only_to_selected_feedback` — The selected source row gains a verified binding with receipt facts while all other source spans stay unchanged.
- `tests/test_roadmap_evidence_retirement.py::test_retirement_record_and_operator_attestation_are_closed_immutable_values` — Unknown fields, invalid identifiers, invalid digests, and mutable models are rejected.
- `tests/test_roadmap_evidence_retirement.py::test_operator_attestation_excludes_prior_response_text` — Recovery evidence retains the response digest and identity without exposing its text.
- `tests/test_roadmap_format.py::test_feedback_history_and_reissue_reference_matches_landed_contract` — Documented field inventories and examples parse, render canonically, and agree with receipt and analysis models.
- `tests/test_roadmap_gates.py::test_feedback_integrity_rejects_generated_history_stripping_or_mutation` — A generated candidate cannot drop a ledger, pointer, reopen record, or attempt to imitate a legacy row.
- `tests/test_roadmap_escalation_selection.py::test_ledgered_clear_refuses_until_matching_guarded_attempt` — The first landed clear cannot issue ordinary evidence; only its recorded guarded attempt can.
- `tests/test_roadmap_revision.py::test_local_preflight_rejects_ledgered_clear_until_matching_guarded_attempt` — Local revision applies the same fence.
- `tests/test_roadmap_structural_revision.py::test_selected_slice_rejects_ledgered_clear_until_matching_guarded_attempt` — Structural revision applies the same fence.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A ledgered feedback row with a nonblank `proposed_response` parses only when one active pointer selects one matching immutable ledger entry.
- A redacted reopen record retains its route facts and fresh attempt for every admitted reopen without retaining response text or attestation prose.
- Generic response candidates create a fresh unbound instance and set its pointer in the same artifact candidate that exposes the response.
- Structural response candidates create a fresh verified instance bound to the exact receipt final, receipt-byte digest, and receipt attempt identity.
- A legacy row with no history fields remains readable, while a ledgered manual clear retains history and a ledgered nonblank manual replacement fails parsing.
- Receipt, local-revision, and structural-revision selection refuse a ledgered manual clear from this step onward, until one matching guarded-reopen record and fresh attempt exist.
- The predecessor integrity gate rejects generated removal or mutation of prior response, pointer, reopen-history, or attempt facts outside the named writer and guarded-reopen transitions.
- A legacy version-2 receipt or analysis final retains its current semantic identity when its attempt field is absent.
- A reissued version-2 receipt and its derived analysis include the nonempty active attempt identity in their semantic identities.
- A baseline identity ignores feedback history, but a feedback snapshot and roadmap-impact snapshot detect a changed ledger or attempt identity.
- `ROADMAP_FORMAT.md` examples for feedback history, receipts, and analyses pass the corresponding parser and renderer checks.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen, extra-forbidden configuration for immutable persisted evidence values.
- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Use field and model validators for pointer and semantic-identity invariants.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Use the existing safe YAML parse/render approach when extending feedback frontmatter.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Use SHA-256 to bind response text and immutable evidence facts.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep versioned evidence JSON closed, canonical, and interoperable.

## Applicable guardrails

- **Preserve active response provenance** — The plan’s “## Step intent” limits this step to preserving active-response identity and giving reopened attempts distinct identities; do not add a general feedback-editing surface.
- **Keep recovery bounded** — The plan’s “## Out of scope” keeps ordinary re-escalation and broad feedback editing outside these contracts; only define the data needed by the later guarded reopen path.
- **Retain ordinary protections** — The plan’s “## Plan intent” requires history-preserving recovery, so legacy compatibility and already-responded protections must remain intact while the new fields are introduced.

## Deferred

- Reopen candidate admission, invalidation classification, and retirement-record publication — Steps 2 and 3 own the filesystem, evidence-reader, and operator-confirmation behavior; this step supplies their typed contracts only.
- Atomic reopen publication, run-log completion binding, and recovery — Step 4 owns the journaled write and final-boundary recheck.
- CLI modes and safe ledger views — Step 5 owns command wiring and output that omits prior response text.
- General roadmap revision retention — Keep the broader retention redesign separate from this bounded recovery contract.
