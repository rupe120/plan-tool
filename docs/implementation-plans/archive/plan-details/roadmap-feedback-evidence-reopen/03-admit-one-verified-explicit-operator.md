# Step 3 — Admit one verified or explicit operator-attested reopen

## Summary

Create `plan_tool/roadmap_feedback_reopen.py` as the pure admission boundary for one answered feedback row that needs the controlled recovery path. It consumes the response-history contract from step 1 and the evidence-classification result from step 2, then returns an in-memory `ReopenCandidate` only for a verified or explicitly attested association. Update `plan_tool/run_log.py` with a redacted admission event and keep the existing publication guard ready for step 4 without publishing anything in this step. On green, ordinary response-bearing rows stay blocked while one eligible `awaiting-review` response can be safely handed to guarded publication.

## Table of Contents

- [Summary](#summary) — The admission boundary and its finished result.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — The missing response-to-evidence decision.
- [Input](#input) — Contracts from steps 1 and 2 plus existing eligibility fences.
- [Files (creates vs edits)](#files-creates-vs-edits) — New admission code and scoped updates.
- [Implementation](#implementation) — Required eligibility, provenance, and redaction behavior.
- [Tests](#tests) — Focused regression coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Primary record and digest references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that constrain this step.
- [Deferred](#deferred) — Publication and operator work owned later.

## Why

`plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()` rejects an `open` row with `proposed_response` as already responded, and `plan_tool/roadmap_revision.py:preflight_feedback_revision()` and `plan_tool/roadmap_structural_revision.py:_current_selected_slice()` enforce the same unanswered-row boundary. After step 1 adds durable response history and step 2 can classify unusable evidence, the code still needs one fail-closed decision that determines whether a specific answered response may enter the guarded reopen path. Without it, callers could treat an evidence final, a matching selector, or a manual clear as an implicit already-responded bypass.

## Input

- **Step 1 response history:** Consume the landed `FeedbackRow` ledger, active response pointer, provenance, reopen-history, and attempt contract from `plan_tool/roadmap_artifacts.py`. The landed field names and validation rules override this detail.

- **Step 2 evidence admission:** Consume the closed invalidation classification, typed `EvidenceLocator`, and verified-byte result from `plan_tool/roadmap_evidence_retirement.py`. `retired` carries only a retirement-record final; unreadable or invalid evidence carries only an active receipt final. Do not reread evidence or recreate its precedence rules in this step.

- **Existing eligibility fences:** Preserve the ordinary behavior in `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, `plan_tool/roadmap_revision_patch.py:merge_feedback_revision()`, and `plan_tool/roadmap_structural_revision_patch.py:merge_structural_revision_patch()`.

- **Later publication seam:** Step 4 consumes the admitted `ReopenCandidate` through `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `recover_roadmap_publication()`, and `_publish_generation()`. This step does not cross that write boundary.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_reopen.py` — Add the pure reopen-admission contract, typed in-memory candidate, verified route, and operator-attested route.
  - `tests/test_roadmap_feedback_reopen.py` — Add focused admission, refusal, immutability, and redaction coverage.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Expose one narrow shared reader or validator for resolving a current response through its active ledger pointer when admission and later final rechecks would otherwise duplicate that rule.
  - `plan_tool/roadmap_revision_publish.py` — Keep the existing writer and recovery boundary as the only publication handoff; any candidate typing added here must remain non-publishing.
  - `plan_tool/run_log.py` — Add a closed, redacted reopen-admission event to `Event` and a matching `RunLogWriter` emitter.
  - `tests/test_roadmap_escalation_run.py` — Cover the unchanged receipt refusal for a response-bearing row before guarded reopen publication.
  - `tests/test_roadmap_revision_patch.py` — Update response-writer fixtures for the landed history shape and preserve append-only response behavior.
  - `tests/test_roadmap_structural_revision_patch.py` — Preserve refusal when the selected feedback already carries an active response.
  - `tests/test_roadmap_structural_revision_proof.py` — Preserve proof rejection when selected response or attempt facts no longer match.
  - `tests/test_roadmap.py` — Keep ordinary manual reopen delivery separate from evidence-reopen admission.

## Implementation

- **Put one admission rule in `plan_tool/roadmap_feedback_reopen.py`.** The foundational logic is: one current answered `awaiting-review` row may form one `ReopenCandidate` only through a verified route or an explicit operator-attested route. Return a typed accepted candidate or a closed refusal result; do not make callers infer permission from a boolean, missing exception, or evidence-file presence.

- **Require the exact current row state.** Accept one receipt-safe selector only when it identifies exactly one `FeedbackRow` in `awaiting-review` with a nonblank active response and no consumed or pending reopen for that response instance. Refuse missing, duplicate, `open`, `deferred`, blank, manually cleared, and already-consumed responses without changing artifact state.

- **Resolve active history once.** For a ledgered response, require its active pointer to identify exactly one history entry whose text and SHA-256 digest match `proposed_response`. Keep this matching logic beside `plan_tool/roadmap_artifacts.py:FeedbackRow`, `_parse_feedback_rows()`, and `_feedback_mapping()` if it must be shared; admission must not create a second, slightly different pointer check.

- **Handle genuine legacy rows deliberately.** For an eligible pre-ledger response, derive a candidate-only legacy response identity from the receipt-safe selector and the exact UTF-8 response digest. Treat it as unverified: do not add history, alter the artifact, or imply that derivation proves an evidence association.

- **Keep provenance routes separate.** Allow the verified route only when the selected response’s stored verified binding names the supplied typed locator and step 2 reports matching raw bytes. An unbound or legacy response, an unreadable final, or a byte mismatch requires the explicit operator-attested route. Reject a locator/reason mismatch and the tempting alternative of inferring a relationship from a shared selector, target, reason, response text, or arbitrary path.

- **Bind each attestation to one response instance.** An attested candidate must carry one immutable `OperatorAttestation` linked to the current response identity, current digest, locator kind and final, and the classifier-matching invalidation reason. Do not overwrite, relabel, or reuse an existing verified binding; a later generated response must receive a new identity and pass admission again.

- **Keep admission in memory.** Candidate creation must not clear `proposed_response`, move the row to `open`, assign a reissue attempt, write an attestation, publish evidence, create a journal, or acquire a writer lock. Step 4 owns journal recovery, final rereads, the guarded transition, and all durable writes.

- **Preserve ordinary eligibility fences.** Do not change `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback()`, `plan_tool/roadmap_revision.py:preflight_feedback_revision()`, or `plan_tool/roadmap_structural_revision.py:_current_selected_slice()` to admit this candidate directly. A ledgered manual clear remains distinct from the guarded reopen that step 4 later publishes.

- **Keep telemetry redacted and closed.** Extend `plan_tool/run_log.py:Event`, `RunLogWriter._emit()`, and the new emitter with safe selector values, response identity or digest, original provenance, admission route, invalidation reason, and verdict. Do not emit response text, reviewer request text, retained evidence bytes, or attestation prose. Preserve `plan_tool/run_log.py`’s leaf-import boundary by using primitive event facts rather than importing the new admission module.

- **Do not add a second writer path.** Keep `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `recover_roadmap_publication()`, and `_publish_generation()` as the only journaled publication path. Any handoff added for `ReopenCandidate` must not write artifacts or introduce another lock or journal format.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback_reopen.py::test_admission_accepts_one_awaiting_review_response_with_matching_active_ledger_entry` — A candidate is returned only when the active pointer, response text, and digest identify one current ledger entry.

- `tests/test_roadmap_feedback_reopen.py::test_admission_derives_legacy_identity_from_safe_selector_and_exact_response_digest` — A genuine legacy response receives a deterministic in-memory identity without creating history.

- `tests/test_roadmap_feedback_reopen.py::test_verified_route_requires_exact_binding_classifier_and_matching_bytes` — The no-attestation route accepts only an exact verified binding and the step 2 byte-verification result.

- `tests/test_roadmap_feedback_reopen.py::test_unbound_legacy_unreadable_and_mismatched_evidence_require_attestation` — Each non-provable route refuses without explicit attestation and accepts only a classifier-matching attestation.

- `tests/test_roadmap_feedback_reopen.py::test_admission_preserves_the_reason_specific_locator_in_candidate_and_attestation` — Candidates and attestations retain a retirement-record final only for `retired`, and an active receipt final only for unreadable or invalid evidence.

- `tests/test_roadmap_feedback_reopen.py::test_attestation_is_single_use_and_preserves_original_verified_provenance` — An attestation cannot replace, relabel, or be reused for the same response instance.

- `tests/test_roadmap_feedback_reopen.py::test_admission_refuses_open_deferred_blank_duplicate_and_consumed_responses` — Only the required predecessor state can enter controlled reopen.

- `tests/test_roadmap_feedback_reopen.py::test_candidate_creation_has_no_artifact_evidence_or_publication_side_effect` — Admission does not alter feedback, write an attestation, assign an attempt, publish evidence, or create a journal.

- `tests/test_roadmap_feedback_reopen.py::test_reopen_admission_event_excludes_response_request_and_attestation_text` — The structured event contains only redacted route facts.

- `tests/test_roadmap_escalation_run.py::test_current_escalation_receipt_keeps_response_bearing_feedback_ineligible_before_guarded_reopen` — A response-bearing row cannot regain ordinary receipt eligibility from candidate admission alone.

- `tests/test_roadmap_revision_patch.py::test_merge_replacement_and_response_updates_the_selected_pair` — Generic response writing retains the landed history contract and remains distinct from reopen admission.

- `tests/test_roadmap_structural_revision_patch.py::test_merge_rejects_selected_feedback_that_no_longer_matches_preflight` — An active response cannot be bypassed through structural patching.

- `tests/test_roadmap_structural_revision_proof.py::test_proof_requires_selected_feedback_to_only_advance_and_add_response` — Structural proof refuses a stale or changed selected response history.

- `tests/test_roadmap.py::test_a_reopened_row_is_delivered_again_and_gets_a_fresh_response` — The ordinary manual `open`-with-response workflow remains separate from controlled evidence reopen.

Every listed test and `uv run pytest tests/ -q -n auto` must be green before this step is complete.

## Acceptance criteria

- A pure admission call returns a typed candidate only for one answered `awaiting-review` row with one current response identity.

- A ledgered candidate retains the selected response text, identity, and digest in memory; a legacy candidate derives those facts without persisting them.

- A verified route requires exact binding and verified bytes; all other allowed recovery routes require one explicit operator attestation with the classifier’s reason.

- A candidate and attestation retain one reason-matching typed locator, never an arbitrary evidence path.

- Open and deferred response-bearing rows remain ineligible for controlled reopen, and ordinary receipt, revision, and structural selection stay unchanged.

- Candidate creation changes no artifact, ledger, active pointer, attempt identity, evidence store, publication journal, or run-log terminal state.

- The admission event contains only closed redacted facts and `plan_tool/run_log.py` retains no first-party runtime import.

- All focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Define strict, frozen candidate and attestation records.

- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Apply deterministic cross-field admission checks.

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Derive and compare response and evidence digests.

- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep redacted run-log records interoperable.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s `## Step intent` limits this module to one admitted association; do not turn it into a feedback editor or general eligibility API.

- **History-preserving recovery** — The plan’s `## Plan intent` requires the original response and provenance to remain available for step 4; this step must not clear, rewrite, or relabel either.

- **No ordinary re-escalation** — The plan’s `## Out of scope` keeps normal evidence issuance and broad already-responded bypasses outside this admission path.

## Deferred

- Atomic artifact publication, final-boundary rereads, journal recovery, and original terminal-event binding — Step 4 owns the durable guarded transition.

- CLI confirmation flags and review rendering — Step 5 owns the public operator workflow and safe presentation.

- General roadmap revision retention — Keep the separate #242 redesign outside this bounded recovery path.
