# Step 3 — Admit one verified or explicit operator-attested reopen, preserve the old response, and restore guarded eligibility

## Summary

Add `plan_tool/roadmap_feedback_reopen.py` as the fail-closed admission boundary for one feedback response that may be reopened. It consumes the response-ledger and invalidation contracts from steps 1 and 2, captures an in-memory candidate, and distinguishes byte-verified evidence from an explicit operator-attested association. Keep `plan_tool/roadmap_artifacts.py` as the source of feedback history, add a redacted reopen-admission run-log shape in `plan_tool/run_log.py`, and preserve the existing writer boundary for step 4. On green, only one eligible `awaiting-review` response can become a later reopen candidate; ordinary already-responded rows remain blocked.

## Table of Contents

- [Summary](#summary) — The completed admission boundary and its result.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The current gap between a response and unusable evidence.
- [Input](#input) — The step 1 and 2 contracts this admission reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — New admission code and focused regression coverage.
- [Implementation](#implementation) — Required eligibility, provenance, and redaction rules.
- [Tests](#tests) — Focused admission and unchanged-boundary coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable conditions for completion.
- [References](#references) — Primary contract references for identities and immutable records.
- [Applicable guardrails](#applicable-guardrails) — Scope limits on this recovery path.
- [Deferred](#deferred) — Publication and CLI work owned by later steps.

## Why

`plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()` rejects an `open` feedback row that retains `proposed_response` as `already-responded`, while `plan_tool/roadmap_revision.py:preflight_feedback_revision()` and `plan_tool/roadmap_structural_revision_patch.py:_selected_artifact_from_preflight()` also require an unanswered open row. The current `FeedbackRow` stores only the response text, so no bounded path can prove or explicitly record why an answered `awaiting-review` row may safely return to normal eligibility. This step supplies that missing admission decision without weakening the existing protections.

## Input

- **Step 1 response history:** Step 1 provides the landed `FeedbackRow` response ledger, active response-instance pointer, verified and unbound provenance, and reissue-attempt identity. Read the landed names and validation rules from `plan_tool/roadmap_artifacts.py`; they override names suggested by this plan or its earlier detail.

- **Step 2 evidence result:** Step 2 provides the landed closed invalidation classifier and byte-verification result in `plan_tool/roadmap_evidence_retirement.py`. Reopen admission must consume that one result instead of re-reading evidence or recreating its precedence rules.

- **Current eligibility boundaries:** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, and `plan_tool/roadmap_structural_revision_patch.py:_selected_artifact_from_preflight()` define the normal unanswered-row path. Keep their refusal of a response-bearing row intact.

- **Publication and telemetry seams:** `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `recover_roadmap_publication()`, and `_require_feedback_snapshot()` remain the later guarded-write boundary. `plan_tool/run_log.py:Event` and `RunLogWriter` define the redacted structured-event contract that step 4 will emit.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_reopen.py` — Define the pure reopen-admission predicate, immutable in-memory candidate, legacy identity derivation, verified-route check, and operator-attestation route.
  - `tests/test_roadmap_feedback_reopen.py` — Cover the candidate contract, route selection, refusals, and redaction.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Reuse `FeedbackRow`, `_parse_feedback_rows()`, and `_feedback_mapping()` as the history contract; add only a narrow shared accessor or validation hook if admission would otherwise duplicate active-pointer and ledger matching.
  - `plan_tool/roadmap_revision_publish.py` — Keep the guarded publication seam able to receive the later candidate recheck without publishing, journaling, or changing artifact state in this step.
  - `plan_tool/run_log.py` — Add a closed, redacted reopen-admission event and matching `RunLogWriter` emitter; include only safe identifiers, digests, route facts, and verdicts.
  - `tests/test_roadmap_escalation_run.py` — Keep receipt admission blocked for a response-bearing row until the later published reopen clears its active response.
  - `tests/test_roadmap_escalation_selection.py` — Retain `select_receipt_feedback()`’s `already-responded` result for an `open` row with `proposed_response`.
  - `tests/test_roadmap_revision.py` — Keep local revision preflight and stage-context behavior aligned with the landed feedback-history shape.
  - `tests/test_roadmap_revision_patch.py` — Keep response writers append-only and ensure reopen admission cannot be mistaken for a response-writing path.
  - `tests/test_roadmap_structural_revision.py` — Preserve the exact evidence and active-attempt checks while fixtures carry the landed response history.
  - `tests/test_roadmap_structural_revision_patch.py` — Preserve structural patch refusal for selected feedback that already has an active response.
  - `tests/test_roadmap_structural_revision_proof.py` — Preserve proof rejection when evidence or the selected response history is no longer current.
  - `tests/test_roadmap.py` — Keep ordinary manual `open`-with-response delivery behavior separate from the controlled evidence-reopen path.

## Implementation

- **Make one pure admission owner.** Put the foundational rule — “one current answered `awaiting-review` row may form one reopen candidate only through a verified or explicitly attested route” — in `plan_tool/roadmap_feedback_reopen.py`. Return a typed candidate or a closed refusal result; do not let callers infer eligibility from a boolean, missing exception, or the evidence final’s presence.

- **Require the exact predecessor state.** Admit only one receipt-safe selector that identifies exactly one `FeedbackRow` in `awaiting-review` with one nonblank active response. Refuse `open`, `deferred`, missing, duplicate, blank, manually cleared, or already-consumed responses without changing their state.

- **Bind the candidate to the active response.** Capture the selector, active response-instance identity, exact response text, and SHA-256 digest in the in-memory candidate. For a ledgered response, require the active pointer to select the one ledger entry whose text and digest match `proposed_response`; do not duplicate that matching rule outside the narrow helper in `plan_tool/roadmap_artifacts.py`.

- **Handle legacy responses explicitly.** For an eligible legacy row with no ledger entry, derive its identity from the receipt-safe selector and the SHA-256 digest of its exact UTF-8 response text. Treat that identity as unverified and candidate-only: do not fabricate ledger history, alter the artifact, or claim that the derived identity proves evidence provenance.

- **Keep the two provenance routes distinct.** A verified route may proceed without creating an attestation only when the selected response’s stored verified binding names the exact supplied evidence and step 2 confirms matching raw bytes. An unbound or legacy response, an unreadable final, or a readable byte mismatch requires the explicit operator-attested route. Do not relabel a verified binding as attested, overwrite it, or infer an association from a shared selector, target, reason, or response text.

- **Require one classifier-matching reason.** Accept only the closed invalidation result from the step 2 classifier. A missing result, invalid retirement record, mismatched operator-supplied reason, or any non-recovery currentness result refuses; do not introduce a permissive fallback or a second reason classifier.

- **Make attestation single-use per response instance.** An operator-attested candidate must carry one typed `OperatorAttestation` linked to one current response instance and digest, one exact evidence locator and final, and one closed invalidation reason. Refuse reuse or replacement of that record for the same response instance. A later generated response has a different response identity and must pass admission again on its own facts.

- **Keep admission in memory.** Candidate creation must not write a pending attestation, alter `FeedbackRow`, clear `proposed_response`, assign `reissue_attempt_id`, publish evidence, or start recovery. Step 4 owns journal recovery, the writer guard, final-boundary rereads, and the single atomic transition to `open`.

- **Use Step 1's ordinary fence.** Step 1 already makes receipt, local-revision, and structural selection refuse a ledgered clear unless the matching guarded-reopen record and active attempt exist. This step must not loosen that rule or create a parallel eligibility test. Keep response-bearing-row refusals in `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()` and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()` intact.

- **Keep telemetry redacted.** Extend `plan_tool/run_log.py:Event` and `RunLogWriter` with closed reopen-admission facts suitable for Step 4's runner to emit after its atomic publication. Record safe selector values, response-instance identity or digest, original provenance, separate admission route, invalidation reason, and verdict; never put `proposed_response`, reviewer request text, retained evidence bytes, or attestation prose in a run-log event.

- **Use the existing publication seam without widening it.** Preserve `plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()` and the feedback-snapshot recheck utilities as the later writer’s handoff. Do not add a second lock, a direct artifact writer, or a new journal format in this admission step.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback_reopen.py::test_reopen_admission_accepts_one_awaiting_review_response_with_matching_active_ledger_entry` — An answered `awaiting-review` row produces one candidate only when its pointer, text, and digest select the current ledger entry.

- `tests/test_roadmap_feedback_reopen.py::test_reopen_admission_derives_legacy_identity_from_safe_selector_and_exact_response_digest` — A legacy response receives a deterministic candidate-only identity without modifying artifact history.

- `tests/test_roadmap_feedback_reopen.py::test_verified_reopen_requires_exact_binding_and_step_two_byte_verification` — The no-attestation route requires the exact evidence final and matching raw-byte digest.

- `tests/test_roadmap_feedback_reopen.py::test_unbound_legacy_unreadable_and_mismatched_routes_require_explicit_attestation` — Each non-provable route refuses without the explicit confirmation and produces an attested candidate only with one classifier-matching reason.

- `tests/test_roadmap_feedback_reopen.py::test_attestation_is_single_use_and_preserves_existing_verified_provenance` — A candidate cannot replace or reuse an attestation for its response instance and never relabels a prior verified record.

- `tests/test_roadmap_feedback_reopen.py::test_reopen_admission_refuses_open_deferred_blank_duplicate_and_consumed_responses` — Only the stated predecessor state is eligible; ordinary manual states remain unchanged.

- `tests/test_roadmap_feedback_reopen.py::test_reopen_candidate_is_in_memory_and_does_not_clear_or_reissue_feedback` — Candidate creation writes no artifact state, pending attestation, reissue attempt, evidence final, or publication journal.

- `tests/test_roadmap_feedback_reopen.py::test_reopen_admission_log_projection_excludes_response_and_reviewer_text` — The new run-log event carries only the allowed redacted facts.

- `tests/test_roadmap_structural_revision_patch.py::test_merge_rejects_selected_feedback_with_existing_response` — Structural patching cannot bypass the active-response boundary.

- `tests/test_roadmap_revision_patch.py::test_generic_response_writers_append_unbound_instance_and_set_active_pointer` — Response writers remain the only path that creates a new generated response instance.

- `tests/test_roadmap_structural_revision.py::test_structural_preflight_requires_matching_receipt_analysis_and_active_attempt` — An earlier attempt remains ineligible after a reopen candidate is later published.

- `tests/test_roadmap_structural_revision_proof.py::test_structural_proof_rechecks_the_selected_active_attempt` — Proof retains its active-attempt recheck with the landed history fields.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A pure admission call returns one typed candidate only for one `awaiting-review` row with one nonblank, current active response and one valid response identity.

- A ledgered candidate preserves its selected response text, identity, and digest in memory; a legacy candidate derives the same identity inputs without persisting them.

- A verified route proceeds without a new attestation only when the selected binding, supplied final, and step 2 byte-verification result all agree.

- An unbound, legacy, unreadable, or byte-mismatched route requires one explicit operator-attested association with a classifier-matching reason.

- Open and deferred response-bearing rows remain ineligible for controlled reopen. Step 1's ordinary receipt, local-revision, and structural-revision fence remains unchanged.

- Candidate creation does not alter the artifact, response ledger, active pointer, active response, reissue attempt, evidence storage, or publication journal.

- The typed candidate carries a verified route or one linked immutable operator attestation, and Step 4 persists and emits its corresponding redacted admission facts without response text, reviewer request, or retained evidence bytes.

- All listed focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Use strict, frozen, extra-forbidden values for the candidate and attestation contracts.

- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Define deterministic field and cross-field admission checks.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Derive and compare response and evidence SHA-256 identities.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep structured run-log facts interoperable and safely bounded.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s “## Step intent” limits this step to one admitted recovery association. Keep the new module a narrow gate, not a general feedback editor.

- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps normal evidence issuance and already-responded bypasses outside this admission path.

- **Preserve response history** — The plan’s “## Plan intent” requires the old response and provenance to remain available to the later atomic publisher; do not clear, rewrite, or relabel them here.

## Deferred

- Atomic artifact publication, final-boundary rechecks, journal recovery, and original completion-event binding — Step 4 owns the guarded writer and durable recovery behavior.

- CLI confirmation flags and safe operator review output — Step 5 owns the public command surface and presentation rules.

- General roadmap revision retention — Keep the separate #242 redesign outside this bounded reopen path.
