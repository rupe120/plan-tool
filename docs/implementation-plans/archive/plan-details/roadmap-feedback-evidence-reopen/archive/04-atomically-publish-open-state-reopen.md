# Step 4 — Atomically publish the open-state reopen, bind its original log, and recover safely

## Summary

Add the backend-free reopen runner in `plan_tool/roadmap_feedback_reopen_run.py` and use the existing roadmap writer journal to publish one revalidated reopen transition. Extend `plan_tool/roadmap_revision_publish.py` with a narrow artifact-only publication path, and extend `plan_tool/run_log.py` so the original terminal `run_end` can carry an opaque completion identity. Bind the reopened attempt to its original run ID, canonical relative log path, and complete terminal payload in the same artifact replacement. On green, a failed terminal log append returns a recoverable result, while recovery can add at most one equal original completion event without republishing the artifact or changing evidence.

## Table of Contents

- [Summary](#summary) — The completed behavior and primary files.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The durability gap between publication and terminal logging.
- [Input](#input) — The upstream candidate, publication, and log contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — New runner files and scoped changes.
- [Implementation](#implementation) — Atomic publication, strict log binding, and recovery rules.
- [Tests](#tests) — Focused publication, log, and contract coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Primary references for durable bytes and JSON records.
- [Applicable guardrails](#applicable-guardrails) — Boundaries that keep recovery narrow.
- [Deferred](#deferred) — Later CLI and broader retention work.

## Why

`plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()` can recover a recorded generation, but it has no atomic link between a reopen’s artifact transition and the terminal event in its original run log. `plan_tool/run_log.py:read_run_events()` intentionally tolerates damaged JSONL for ordinary reporting, so it cannot safely decide that a missing terminal event is recoverable. This step closes that gap without turning the reopen path into a general feedback editor or an immutable-evidence writer.

## Input

- **Step 1 response history:** Read the landed feedback-history and active-attempt contract from `plan_tool/roadmap_artifacts.py`. Its field names and validation rules win over this detail.

- **Step 3 admission:** Consume the landed `plan_tool/roadmap_feedback_reopen.py:ReopenCandidate` and its final recheck. The candidate remains in memory until this step’s atomic publication.

- **Publication journal:** Reuse `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `recover_roadmap_publication()`, `_publish_generation()`, and `PendingGeneration`. The existing journal remains the only interrupted-publication recovery record.

- **Run-log boundary:** Use `plan_tool/run_log.py:RunLogWriter.start()`, `run_log_path()`, `RunEnd`, `append_event()`, and `read_run_events()` as orientation. Do not use the tolerant `read_run_events()` result as proof that an original recovery log is clean.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_reopen_run.py` — Run one admitted reopen and recover one bound original terminal event without a backend call.
  - `tests/test_roadmap_feedback_reopen_run.py` — Cover normal publication, interrupted boundaries, terminal-log failure, and idempotent recovery.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Append the redacted reopen-history record with the guarded open transition and expose it to later selection and review readers.
  - `plan_tool/roadmap_revision_publish.py` — Add a narrow guarded reopen publisher that journals the selected artifact replacement and runs the final candidate recheck before replacement.
  - `plan_tool/run_log.py` — Support a bound `run_end` completion identity and strict inspection or append of a bound original completion event.
  - `tests/test_roadmap_revision_publish.py` — Cover the reopen generation’s atomicity, final recheck, and journal recovery.
  - `tests/test_roadmap_artifacts.py` — Cover atomic persistence and immutable retention of the redacted reopen-history record.
  - `tests/test_run_log.py` — Cover the optional completion identity and strict original-log recovery rules.
  - `DATA_CONTRACT.md` — Document the immutable attempt-to-original-log binding and the recovery event rules.
  - `tests/test_data_contract.py` — Keep the documented reopen completion contract tied to the run-log behavior.

## Implementation

- **Publish one revalidated candidate.** Make `plan_tool/roadmap_feedback_reopen_run.py` own the foundational rule: an admitted candidate becomes an `open` row only after the final guarded reread still matches its selector, state, active response identity, response text, digest, ledger history, provenance route, and attestation facts.

- **Start the original log before admission.** Open `RunLogWriter` before candidate admission, derive one opaque completion-event ID, and derive the stored relative log path from `plan_tool/run_log.py:run_log_path()` and that writer’s run ID. Never accept a log path from a caller or persist an absolute path.

- **Recover before every fresh admission.** Hold `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()` while calling `recover_roadmap_publication()` before reading a candidate. A remaining journal must complete or roll back before this runner can admit a new reopen.

- **Use an artifact-only journaled publication.** Add a focused reopen helper beside `publish_revision_candidate()` that renders and parses the candidate artifact, records its old and new bytes in one `PendingGeneration`, and invokes `_publish_generation()` with the final recheck at its replacement boundary. Do not use `publish_revision_candidate()` for this transition: its baseline and seed-state publication shape is broader than a feedback-only reopen.

- **Persist the whole reopen transition together.** The one artifact replacement must retain the original response instance and provenance in history, append one redacted reopen record, set the selected row to `open`, clear its active response and pointer, assign the fresh reissue attempt, and store the immutable completion binding. The reopen record carries its response identity and digest, original provenance class, separate admission route, classifier result, safe evidence or retirement identity, and attempt. An operator-attested route embeds the exact candidate `OperatorAttestation` beside the original provenance; a verified route embeds none. The completion binding carries the attempt identity, receipt-safe selector, original run ID, canonical relative log path, completion-event ID, `reopened` outcome, zero exit code, and duration measured at the final recheck.

- **Leave unrelated state untouched.** Preserve baseline records, unrelated artifact state, immutable evidence finals, and every unselected feedback row. The normal and recovery paths must never amend immutable evidence or write a second attestation.

- **Bind a complete normal completion before publication.** At the final recheck, form one successful `RunEnd` payload with original run ID, `reopened` outcome, zero exit code, elapsed duration at that boundary, and completion-event ID. Persist those facts in the binding, then after publication append that exact payload and the Step 3 redacted reopen-admission event through `RunLogWriter`. The event reports original provenance, admission route, and safe attestation identity or verified marker from the persisted reopen record. If terminal logging cannot complete, return `committed-log-pending` with the safe selector and reissue attempt; do not retry publication or run a second generic terminal append from cleanup.

- **Make completion identity additive.** Extend `plan_tool/run_log.py:RunEnd` and `RunLogWriter.run_end()` with an optional completion-event ID. Keep it absent from ordinary run logs, preserve the existing run-log schema version, and do not add a second terminal event discriminator.

- **Inspect recovery logs strictly.** Add a run-log helper for the recovery runner that reads the bound original log as strict UTF-8 JSONL and rejects malformed nonblank records, missing or mismatched `run_start` identity, a path outside the expected run-log location, or terminal events that conflict with the stored binding. Keep this helper free of first-party imports; artifact lookup stays in `plan_tool/roadmap_feedback_reopen_run.py`.

- **Recover exactly once.** Under the same roadmap writer guard, load the selected row’s matching completion binding. If the original log has no terminal event, append one `RunEnd` with every bound fact. If it has exactly one event matching all bound terminal fields, return `recovered` without an append. Refuse a duplicate matching event, a missing or different completion ID, or any different outcome, exit code, duration, or other conflicting terminal fact.

- **Keep recovery non-mutating for artifacts.** The recovery invocation may write its own separate run log, but it must not republish the roadmap artifact, create a new response-history entry, alter evidence, or recreate an attestation.

- **Document the durable protocol.** Update `DATA_CONTRACT.md` near the run-log contract to state the optional `RunEnd` completion field, the immutable attempt-to-log binding, the strict recovery read rules, and the absence of response or reviewer text. Keep `tests/test_data_contract.py` focused on those stated facts.

## Tests

### Tests for this step

- `tests/test_roadmap_revision_publish.py::test_reopen_publication_journals_only_the_revalidated_feedback_artifact` — The transition updates the selected artifact atomically while baseline, seed-state, and immutable evidence files remain unchanged.

- `tests/test_roadmap_revision_publish.py::test_reopen_publication_final_recheck_refuses_changed_response_identity_or_admission` — A changed response, pointer, digest, state, provenance, or attestation refuses before replacement and leaves no false recovery journal.

- `tests/test_roadmap_revision_publish.py::test_recover_roadmap_publication_restores_or_finishes_an_interrupted_reopen_generation` — The existing recovery routine handles the reopen generation without guessing about unrelated disk changes.

- `tests/test_roadmap_feedback_reopen_run.py::test_run_feedback_reopen_publishes_open_state_and_binds_original_completion` — A successful run records the response history, cleared active state, fresh attempt, original run ID, canonical relative path, and one completion ID together.

- `tests/test_roadmap_feedback_reopen_run.py::test_prepublication_interrupt_is_retryable_without_a_persisted_attestation` — An interruption before replacement leaves the candidate retryable and writes no partial reopen state.

- `tests/test_roadmap_feedback_reopen_run.py::test_terminal_log_failure_returns_committed_log_pending_without_republishing` — A post-publication terminal append failure returns the bound selector and attempt while retaining the published artifact exactly once.

- `tests/test_roadmap_feedback_reopen_run.py::test_atomic_reopen_persists_original_provenance_and_attested_route_then_emits_redacted_event` — An attested reopen keeps its original binding, persists the linked attestation and admission route, and emits only their safe facts.

- `tests/test_roadmap_feedback_reopen_run.py::test_recover_feedback_reopen_appends_one_bound_original_completion_then_is_idempotent` — Recovery appends the complete bound original `run_end` once, then reports recovery without a second append or artifact change.

- `tests/test_roadmap_feedback_reopen_run.py::test_recovery_refuses_missing_malformed_mismatched_or_conflicting_original_log` — Unsafe log states refuse and leave the artifact, attestation, and evidence unchanged.

- `tests/test_run_log.py::test_run_end_omits_completion_identity_unless_a_bound_completion_requires_it` — Existing callers retain their current payload while the reopen path persists its opaque identity.

- `tests/test_run_log.py::test_bound_original_completion_requires_one_complete_matching_terminal_event` — Strict recovery rejects damaged, duplicate, foreign, and terminal records with a mismatched outcome, exit code, duration, or completion identity.

- `tests/test_data_contract.py::test_reopen_completion_binding_contract_matches_run_log_behavior` — The documented binding fields, strict recovery rule, and redaction boundary match the landed code.

Every listed test, followed by `uv run pytest tests/ -q -n auto`, must be green before this step is complete.

## Acceptance criteria

- A successful reopen publishes one journaled artifact generation containing the guarded open-state transition, retained history, redacted reopen record with original provenance and admission route, fresh attempt, and original complete terminal binding.

- The final candidate recheck refuses any changed admission fact before artifact replacement.

- Reopen publication does not modify baseline records, unrelated artifact state, immutable evidence finals, or unselected feedback rows.

- A normal successful original log contains exactly one bound `run_end` with its original run ID, `reopened` outcome, zero exit code, final-recheck duration, and completion-event ID; ordinary `run_end` records omit that optional field.

- A failed original terminal append returns `committed-log-pending` and does not republish the artifact or create another attestation.

- An operator-attested reopen persists its linked immutable attestation beside its original provenance and emits the same redacted admission route in the original run log; a verified route emits `verified` without an attestation.

- Recovery accepts only a matching stored attempt and clean original log, appends one missing bound terminal event, and returns an existing exact event without appending again.

- Recovery refuses malformed, missing, path-mismatched, run-ID-mismatched, duplicate, or conflicting original-log records without changing artifact or evidence state.

- All listed focused tests and `uv run pytest tests/ -q -n auto` pass.

## References

- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Bind response and completion identities to exact SHA-256 inputs where the landed contracts require it.

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Review durable replacement and append primitives used by the journal and JSONL writer.

- [RFC 8259: The JSON Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Keep strict original-log recovery based on valid JSON objects.

## Applicable guardrails

- **Bounded recovery purpose** — The plan’s “## Step intent” limits this work to a durable reopen and its recovery path. Keep the runner backend-free and narrow.

- **No general editor** — The plan’s “## Out of scope” limits these files to the admitted reopen transition; do not add arbitrary feedback mutation.

- **No ordinary re-escalation** — The plan’s “## Out of scope” keeps normal evidence issuance outside the publisher and recovery runner.

- **Preserve history and evidence** — The plan’s “## Plan intent” requires this step to retain response history and avoid immutable-evidence mutation.

## Deferred

- CLI flags, confirmation parsing, and operator-facing recovery output — Step 5 owns the public command surface.

- General roadmap revision retention — Keep the separate #242 redesign outside this bounded recovery path.
