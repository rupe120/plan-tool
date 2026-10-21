# Step 1 — Define active response-ledger pointers, operator attestations, and per-attempt identities

## Summary

Define the feedback-row history contract in `plan_tool/roadmap_artifacts.py`, including response-ledger entries, active-response pointers, redacted reopen history, operator attestations, and reissue-attempt identities. Update the existing receipt, analysis, selection, revision, structural-revision, gate, and snapshot contracts so they preserve and check those facts consistently. The key design decision is that ordinary eligibility remains based on an unanswered `open` row, while a ledgered clear becomes eligible only through its matching guarded reopen record and attempt. On green, every new generated response has distinct provenance, prior response history cannot be stripped or silently reused, and existing pre-ledger artifacts retain their current behavior.

## Table of Contents

- [Summary](#summary) — The completed behavior and primary design choice.
- [Table of Contents](#table-of-contents) — Links to each top-level section.
- [Why](#why) — The missing response-to-evidence identity boundary.
- [Input](#input) — Existing feedback, evidence, revision, and snapshot contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Scoped code, documentation, and tests.
- [Implementation](#implementation) — Ledger, provenance, eligibility, and attempt rules.
- [Tests](#tests) — Focused regression coverage for each new invariant.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Contract and serialization references.
- [Applicable guardrails](#applicable-guardrails) — Scope and safety boundaries for this step.
- [Deferred](#deferred) — Work owned by later recovery steps.

## Why

`plan_tool/roadmap_artifacts.py:FeedbackRow` currently retains only `proposed_response`, while `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, and `plan_tool/roadmap_structural_revision_patch.py:_selected_artifact_from_preflight()` can only see whether that text exists. That leaves no durable way to distinguish a response tied to immutable evidence from an unbound response, no proof that a response has not been manually replaced, and no identity that prevents a later reissue from making earlier immutable evidence current again.

## Input

- **Feedback-row wire contract:** `plan_tool/roadmap_artifacts.py:FeedbackRow`, `_parse_feedback_rows()`, `_parse_proposed_response()`, `_feedback_mapping()`, and `_review_mappings()` define the current parsed and rendered review state.

- **Ordinary eligibility:** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, and `plan_tool/roadmap_revision.py:build_stage_revision_context()` own the current unanswered-row checks.

- **Response writers:** `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `merge_stage_revision()` write ordinary responses. `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` writes the structural-response form.

- **Evidence identities:** `plan_tool/roadmap_escalation.py:EscalationReceipt`, `build_receipt()`, and `receipt_semantic_preimage()` define version-2 receipt identity. `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence` and `build_impact_analysis()` copy receipt facts into analysis identity.

- **Freshness boundaries:** `plan_tool/roadmap_source_identity.py:canonical_projection()` deliberately excludes feedback, while `feedback_snapshot()` and `plan_tool/roadmap_impact_snapshot.py:RoadmapImpactSnapshot` retain feedback-sensitive state for rechecks.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_evidence_retirement.py` — Create the narrow, no-I/O contract boundary for redacted evidence references and typed retirement-facing failures that later steps extend.
  - `tests/test_roadmap_evidence_retirement.py` — Cover the new pure contract without testing later filesystem publication or classification behavior.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Add parsed and rendered feedback-ledger, active-pointer, provenance, reopen-history, operator-attestation, and reissue-attempt fields with legacy-compatible absence rules.
  - `plan_tool/roadmap_escalation.py` — Allow an optional reissue attempt in version-2 receipt facts and semantic identity while preserving legacy version-2 final names when it is absent.
  - `plan_tool/roadmap_escalation_selection.py` — Keep ordinary response-bearing refusals and reject an unguarded ledgered clear from receipt selection.
  - `plan_tool/roadmap_gates.py` — Preserve predecessor response history and allow only the defined generated response append.
  - `plan_tool/roadmap_impact_analysis.py` — Carry the optional receipt attempt through typed analysis evidence and its semantic preimage.
  - `plan_tool/roadmap_impact_snapshot.py` — Keep captured artifact state and rechecks sensitive to ledger and attempt changes without adding a second source-identity system.
  - `plan_tool/roadmap_revision.py` — Apply the shared ordinary-eligibility rule to local and stage revision preflights.
  - `plan_tool/roadmap_revision_patch.py` — Make generic response writers append a fresh unbound response record and set its active pointer.
  - `plan_tool/roadmap_source_identity.py` — Preserve the feedback-free baseline projection while ensuring feedback snapshots include the new fields.
  - `plan_tool/roadmap_structural_revision.py` — Require the selected row, receipt, and analysis to agree on the active attempt when one exists.
  - `plan_tool/roadmap_structural_revision_patch.py` — Add a fresh verified response record and active pointer as part of the structural response patch.
  - `ROADMAP_FORMAT.md` — Document the response-ledger fields, legacy compatibility, guarded-clear rule, and optional version-2 attempt identity.
  - `tests/test_roadmap_artifacts.py` — Cover parsing, rendering, redaction, legacy artifacts, and pointer validation.
  - `tests/test_roadmap_escalation.py` — Cover receipt parsing and semantic identity with and without an attempt.
  - `tests/test_roadmap_escalation_selection.py` — Cover ordinary selection of legacy rows and refusal of unguarded ledgered clears.
  - `tests/test_roadmap_gates.py` — Cover append-only response history and predecessor integrity.
  - `tests/test_roadmap_impact_analysis.py` — Cover analysis identity propagation for the optional attempt.
  - `tests/test_roadmap_impact_snapshot.py` — Cover stale snapshots after feedback-ledger or attempt changes.
  - `tests/test_roadmap_format.py` — Keep the documented schema and receipt examples aligned with code.
  - `tests/test_roadmap_revision.py` — Cover local and stage eligibility under the new history state.
  - `tests/test_roadmap_revision_patch.py` — Cover generic unbound response creation.
  - `tests/test_roadmap_source_identity.py` — Cover feedback snapshots changing without baseline identity churn.
  - `tests/test_roadmap_structural_revision.py` — Cover selected-row and exact-pair attempt matching.
  - `tests/test_roadmap_structural_revision_patch.py` — Cover structural verified response creation and source-patch refusal paths.

## Implementation

- **Keep feedback history on the row.** Extend `plan_tool/roadmap_artifacts.py:FeedbackRow` with the response-ledger collection, `active_response_instance_id`, redacted reopen history, and optional `reissue_attempt_id`. Keep all new collections absent from legacy artifacts unless they contain data, matching `_review_mappings()`’s existing omission behavior.

- **Define one active-response invariant.** For a ledgered row with nonblank `proposed_response`, require exactly one nonempty active pointer that selects exactly one ledger entry. Require that entry’s retained response text and SHA-256 digest to match the active text exactly. Reject duplicate, missing, dangling, or mismatched entries during parsing rather than leaving each reader to make a different guess.

- **Preserve legacy rows.** A pre-ledger row has no response ledger, active pointer, reopen history, or attempt identity and continues to parse and follow its current lifecycle. Do not backfill a legacy response during ordinary parsing, selection, or a rejected attempt.

- **Make manual replacement fail closed.** A ledgered response cannot be changed in place while retaining its old pointer or provenance. Permit a clear only when the row is `open`, has no active response, and has no active pointer; retain its immutable ledger and reopen history.

- **Separate provenance from admission.** Give each ledger entry a fresh opaque response-instance identity, exact UTF-8 response digest, retained response text, and either unbound or verified provenance. A verified structural response must retain the exact receipt final, raw receipt digest, and receipt attempt identity when present. `OperatorAttestation` and `ReopenHistory` retain the later recovery facts separately; an operator attestation must never relabel or overwrite verified provenance.

- **Keep history redacted where required.** `ReopenHistory` and `OperatorAttestation` may retain safe selectors, response-instance identities, digests, evidence identifiers, invalidation facts, and attempt identities. Do not put the prior response text, reviewer request, raw evidence bytes, or free-form attestation prose in those records.

- **Keep `plan_tool/roadmap_artifacts.py` a leaf.** Do not add first-party imports to the artifact parser/renderer layer. Keep its shape validation local and let `plan_tool/roadmap_evidence_retirement.py` consume the persisted redacted facts in the later evidence workflow.

- **Create fresh response identities at writers.** Update `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `merge_stage_revision()` to append, never replace, a fresh unbound ledger entry before exposing a generated response. Use an identity-supply seam that tests can control; do not derive identity from response text alone.

- **Record structural provenance only where it is provable.** Update `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` to append the same response shape with verified receipt binding from `StructuralRevisionPreflight`. Do not let generic revision paths invent a receipt binding.

- **Protect history in the predecessor gate.** Extend `plan_tool/roadmap_gates.py:check_feedback_integrity()` so generated candidates cannot remove or alter existing ledger entries, reopen history, active pointers, or reissue attempts. Allow the selected `open` row to gain only the response, matching new ledger entry, and matching pointer required for that generated response.

- **Centralize ordinary eligibility.** Make `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, and `build_stage_revision_context()` use one artifact-owned eligibility rule. A legacy unanswered `open` row remains eligible. A ledgered clear is refused unless its matching guarded reopen history supplies the active reissue attempt.

- **Keep existing response-bearing refusals.** An `open` row that still carries `proposed_response` must remain `already-responded` for ordinary receipt selection and remain ineligible for local or structural revision. Do not add a general bypass for a known response.

- **Add optional attempt identity without a version bump.** Extend `plan_tool/roadmap_escalation.py:EscalationReceipt` and its semantic-hash helpers so an absent attempt retains the current version-2 preimage and final name. A present reissue attempt must be nonempty and must change the new receipt’s semantic identity.

- **Copy attempt identity into analyses.** Update `plan_tool/roadmap_impact_analysis.py:ImpactReceiptEvidence`, `_impact_receipt_evidence_fields()`, and analysis semantic hashing so a reissued receipt and its analysis bind the same attempt. Step 2 owns active-reader enforcement; this step establishes the typed fields and legacy-compatible identity behavior.

- **Keep freshness layers distinct.** `plan_tool/roadmap_source_identity.py:canonical_projection()` must continue to omit the whole feedback channel. `feedback_snapshot()`, `plan_tool/roadmap_impact_snapshot.py:capture_roadmap_impact_snapshot()`, and `recheck_roadmap_impact_snapshot()` must still detect ledger or attempt changes through the parsed artifact state.

- **Set up, but do not implement, retirement I/O.** Create `plan_tool/roadmap_evidence_retirement.py` as a pure contract module for redacted evidence-reference values used by verified provenance and later retirement work. Do not read files, publish records, classify invalidation, or add an operator command in this step.

- **Document the new state once.** Update `ROADMAP_FORMAT.md:## The review collections — \`feedback\` and \`removals\``, `### The feedback lifecycle`, `## Structural escalation receipts`, and `## Impact-routing analyses`. State that legacy version-2 evidence omits attempts, new reissued evidence binds one attempt, and only a guarded reopen makes a ledgered clear ordinarily eligible.

## Tests

### Tests for this step

- `tests/test_roadmap_artifacts.py::test_response_ledger_round_trips_with_active_pointer_and_redacted_history` — Parsed and rendered ledgered feedback retains the complete active identity and omits response text from reopen history.

- `tests/test_roadmap_artifacts.py::test_ledgered_nonblank_response_requires_one_matching_active_entry` — Missing, duplicate, dangling, text-mismatched, and digest-mismatched pointers fail parsing.

- `tests/test_roadmap_artifacts.py::test_preledger_feedback_rows_retain_existing_parse_and_render_behavior` — Existing feedback with no ledger fields remains valid.

- `tests/test_roadmap_artifacts.py::test_ledgered_clear_requires_open_state_and_no_active_pointer` — A retained history can be cleared only in the stated paired state.

- `tests/test_roadmap_revision_patch.py::test_generic_response_writers_append_unbound_instance_and_set_active_pointer` — Local and stage response merges append a distinct unbound entry instead of rewriting prior history.

- `tests/test_roadmap_structural_revision_patch.py::test_structural_response_writes_verified_receipt_binding_and_fresh_instance` — A structural patch records the receipt final, raw digest, attempt identity, and matching active pointer.

- `tests/test_roadmap_gates.py::test_feedback_integrity_preserves_ledger_history_and_allows_only_selected_response_append` — A generated candidate cannot strip or alter carried history.

- `tests/test_roadmap_escalation_selection.py::test_ledgered_manual_clear_is_not_ordinary_receipt_eligible` — An unanswered ledgered clear refuses without its matching guarded reopen record and attempt.

- `tests/test_roadmap_revision.py::test_local_and_stage_revision_refuse_unguarded_ledgered_clear` — Revision preflights use the same ordinary-eligibility boundary.

- `tests/test_roadmap_escalation.py::test_version2_receipt_attempt_is_optional_for_legacy_identity_and_hashed_when_present` — Existing version-2 finals stay stable while a reissued receipt changes identity.

- `tests/test_roadmap_impact_analysis.py::test_analysis_receipt_evidence_copies_optional_reissue_attempt` — Analysis identity changes with a present receipt attempt and accepts the absent legacy form.

- `tests/test_roadmap_source_identity.py::test_response_ledger_and_attempt_change_feedback_snapshot_not_canonical_source_identity` — Feedback-sensitive rechecks change while canonical source identity does not.

- `tests/test_roadmap_impact_snapshot.py::test_snapshot_recheck_refuses_response_ledger_or_attempt_change` — Snapshot freshness cannot mix preflight and changed feedback state.

- `tests/test_roadmap_structural_revision.py::test_structural_preflight_requires_selected_feedback_to_match_receipt_attempt` — Exact evidence cannot authorize a row with a different active attempt.

- `tests/test_roadmap_evidence_retirement.py::test_redacted_evidence_reference_contract_has_no_storage_side_effects` — The new module validates only its pure contract and does not start retirement publication work.

- `tests/test_roadmap_format.py::test_feedback_history_and_reissue_attempt_reference_matches_landed_contract` — The documented feedback and version-2 identity rules match the implemented schema.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A ledgered nonblank response has one active pointer to one matching ledger record with the same text and SHA-256 digest.

- Generic response writers append a fresh unbound response record; structural response writers append a fresh verified record with the exact receipt facts they can prove.

- Existing ledger entries, reopen history, pointers, and attempts cannot be deleted or changed by generated revision output.

- A pre-ledger feedback row remains valid and follows existing ordinary behavior.

- A ledgered clear is valid only in its paired cleared state, retains history, and cannot enter ordinary receipt or revision selection without its matching guarded reopen record and attempt.

- A version-2 receipt or analysis without an attempt retains its existing semantic identity. A nonempty attempt changes both new identities.

- Feedback-ledger and attempt changes invalidate feedback-sensitive snapshots without changing canonical source identity.

- `ROADMAP_FORMAT.md` documents the ledger, redaction, legacy compatibility, and guarded-clear rules.

- All listed focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Define closed immutable evidence values where Pydantic models fit the existing receipt and analysis contracts.

- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Implement deterministic cross-field checks for pointers, provenance, and attempts.

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Preserve the frontmatter parsing and rendering contract for feedback rows.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind active response text and immutable evidence with SHA-256.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Preserve strict, interoperable receipt and analysis records.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s “## Step intent” limits this step to response identity, provenance, and guarded future eligibility. Do not add a general editor or a recovery command.

- **Preserve ordinary protections** — The plan’s “## Plan intent” requires normal already-responded refusal to remain intact. Keep the exception tied to persisted guarded-reopen facts rather than response text alone.

- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps normal evidence reissue and general evidence repair outside this contract-definition step.

## Deferred

- Retirement-record publication, fixed-root reads, and invalidation classification — Step 2 owns the filesystem-backed evidence boundary.

- Reopen-candidate admission and explicit operator confirmation — Step 3 owns the in-memory decision path.

- Atomic reopen publication, completion-log binding, and recovery — Step 4 owns the guarded writer and journal behavior.

- CLI modes and safe review rendering — Step 5 owns operator-facing input and output.

- General roadmap revision retention — Keep the broader #242 redesign separate from this bounded recovery path.
