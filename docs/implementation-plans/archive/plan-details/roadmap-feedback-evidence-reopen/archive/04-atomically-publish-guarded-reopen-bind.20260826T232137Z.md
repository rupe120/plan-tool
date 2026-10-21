# Step 4 — Atomically publish the guarded reopen, bind its complete original log event, and recover safely

## Summary

Create the backend-free reopen runner in `plan_tool/roadmap_feedback_reopen_run.py`, backed by one narrow guarded publisher in `plan_tool/roadmap_revision_publish.py`. Extend `plan_tool/roadmap_artifacts.py` to persist the guarded open transition and its redacted run binding, and extend `plan_tool/run_log.py` so a `RunEnd` can carry an optional opaque `completion_id`. Publish the artifact transition before appending its prepared terminal event, with the full original terminal payload recorded in that same artifact change. On green, a normal reopen produces one bound terminal event, while a failed terminal append returns a recoverable result that later adds at most that one exact event.

## Table of Contents

- [Summary](#summary) — The completed reopen publication and recovery behavior.
- [Table of Contents](#table-of-contents) — Links to each section in this detail.
- [Why](#why) — The missing durable link between a reopened row and its terminal log event.
- [Input](#input) — The upstream admission, artifact, publication, and log contracts this step consumes.
- [Files (creates vs edits)](#files-creates-vs-edits) — New runner files and scoped edits.
- [Implementation](#implementation) — Guarded publication, strict log binding, and recovery rules.
- [Tests](#tests) — Focused coverage for publication and terminal-event recovery.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Durable-write, YAML, and JSON references.
- [Applicable guardrails](#applicable-guardrails) — Scope limits that constrain the reopen path.
- [Deferred](#deferred) — CLI and broader lifecycle work outside this step.

## Why

`plan_tool/roadmap_revision_publish.py:recover_roadmap_publication()` can restore a recorded artifact generation, but it cannot prove that an answered feedback row’s reopen and the terminal event for its original run describe the same operation. `plan_tool/run_log.py:read_run_events()` intentionally skips damaged JSONL lines for reporting, so it cannot establish that a missing terminal event is safe to recreate. Step 3 can admit one bounded candidate, but this step must make that admission durable without allowing a raw edit, a second publication, or a duplicate terminal event.

## Input

- **Step 1 response history:** Use the landed feedback ledger, active-attempt pointer, and redacted reopen-history contract from `plan_tool/roadmap_artifacts.py`. Its field names and validation rules remain authoritative.

- **Step 2 evidence classification:** Treat Step 2 as the only classifier. Before publication this step reruns that same classifier and verified-byte binding through the candidate’s typed locator; it does not invent a second precedence rule, record replacement evidence, or accept an arbitrary path.

- **Step 3 admission:** Accept only Step 3’s `plan_tool/roadmap_feedback_reopen.py:ReopenCandidate` as an in-memory snapshot, not a general selection override. This runner owns the locked final admission: it rereads the candidate's row and reruns the Step 2 classifier, locator, verified-byte, and attestation checks before it builds publication bytes.

- **Publication journal:** Reuse `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard()`, `require_roadmap_writer_token()`, `recover_roadmap_publication()`, and `plan_tool/roadmap_source_identity.py:PendingGeneration`. The journal remains the only artifact-publication recovery record.

- **Run-log contract:** Build on `plan_tool/run_log.py:RunLogWriter.start()`, `RunLogWriter.run_end()`, `RunEnd`, `run_log_path()`, and `append_event()`. Do not use `read_run_events()` as recovery evidence because its tolerant reader deliberately accepts damaged logs.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_reopen_run.py` — Create the backend-free service that publishes one admitted reopen, appends its bound terminal event, and recovers that event when needed.
  - `tests/test_roadmap_feedback_reopen_run.py` — Add isolated lifecycle tests for normal completion, stale publication, terminal-append failure, and idempotent recovery.

- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — Extend the landed reopen-history representation, parser, renderer, and artifact update helper so one guarded transition records the redacted run binding and clears only the active response authority required for ordinary eligibility.
  - `plan_tool/roadmap_revision_publish.py` — Add an artifact-only guarded reopen publisher that requires an active writer token, performs final admission before candidate rendering, and journals only the selected artifact replacement.
  - `plan_tool/run_log.py` — Add optional `RunEnd.completion_id` support plus strict inspection and exact append support for a bound original completion event.
  - `tests/test_roadmap_revision_publish.py` — Cover the artifact-only generation, final recheck ordering, and journal recovery boundaries.
  - `tests/test_roadmap_artifacts.py` — Cover reopen-history render/parse behavior and preservation of prior response history without exposing it through the run binding.
  - `tests/test_run_log.py` — Cover optional completion identity, strict bound-event inspection, and at-most-once exact append behavior.
  - `DATA_CONTRACT.md` — Document the optional `run_end` completion identity, the exact-payload recovery rule, and the redaction boundary.
  - `tests/test_data_contract.py` — Extend the documentation drift checks for the new terminal-event contract.

## Implementation

### Guarded reopen publication

- **Make the foundational rule a transaction-bound reopen.** One admitted candidate may create one selected-artifact generation containing both the open-state transition and its redacted reopen-history record. That history binds the attempt’s `run_id`, canonical repository-relative log path, complete prepared `run_end` payload, and opaque `completion_id`.

- **Keep the publisher artifact-only.** Add a narrow path beside `plan_tool/roadmap_revision_publish.py:publish_revision_candidate()` rather than reusing that helper. `publish_revision_candidate()` updates a baseline and seed state; a reopen changes review state only, so it must not rewrite a baseline, invalidate seeds, modify immutable evidence, or touch another roadmap artifact.

- **Use the existing journal rather than a second recovery file.** Under `roadmap_writer_guard()`, recover any existing journal, complete final admission, freeze the payload, and build one rendered `PendingGeneration` member for the selected artifact before passing it through `plan_tool/roadmap_revision_publish.py:_publish_generation()`. Journal those exact bytes. The guarded reopen path has no `before_replace` admission callback because `_publish_generation()` journals before that callback.

- **Re-admit at the final publication boundary.** Require `roadmap_writer_guard()` ownership, reread the row, and rerun Step 2's single classifier, reason-specific locator, verified-byte binding, and required recovery-attestation checks before rendering a candidate. A moved row, active attempt, response pointer, history record, artifact snapshot, changed active receipt, changed retirement record, or changed classifier result must refuse before a journal or artifact replacement.

- **Preserve prior response history.** Update `plan_tool/roadmap_artifacts.py:FeedbackRow`, `_parse_feedback_rows()`, `_feedback_mapping()`, and `_review_mappings()` through the landed Step 1 contract. The reopened row becomes ordinarily eligible only through the exact guarded transition; its response provenance and prior history remain preserved, while the run binding contains no reviewer request, response prose, or immutable-evidence bytes.

### Bound terminal event

- **Freeze the terminal event at final admission.** The reopen runner must obtain its own run identity through `RunLogWriter.start()` and derive the canonical log path from that writer. Immediately after final admission and before it renders or journals the candidate artifact, freeze one complete `RunEnd` payload; its duration is measured at this final-admission boundary. Embed that exact payload in the candidate artifact, journal its bytes, and make normal completion and recovery append the same payload without recreating timestamps, durations, outcomes, or identifiers.

- **Add an optional opaque identity.** Extend `plan_tool/run_log.py:RunEnd` and `RunLogWriter.run_end()` with an optional `completion_id`. Omit the field entirely for existing unbound runs so current callers and their serialized log shape remain unchanged.

- **Keep the event inside the existing append contract.** The prepared payload must fit `plan_tool/run_log.py:_append_jsonl_line()` without truncating a field that the artifact later compares. Refuse before publication if the full bound event cannot be represented; do not store one payload and append an altered version.

- **Append only after successful artifact publication.** The runner may return a successful completion only after the artifact generation commits and the exact terminal event appends. If that append fails, return a distinct recoverable outcome that identifies the durable reopen without claiming terminal logging completed.

- **Do not call a backend.** `plan_tool/roadmap_feedback_reopen_run.py` only coordinates persisted contracts, the writer guard, and run-log I/O. It must not import or invoke Claude, shell transport, or an ordinary revision runner.

### Strict recovery

- **Recover the original event, not a new run.** Recovery opens the same roadmap writer guard, calls `recover_roadmap_publication()` first, reads the persisted reopen binding, and inspects only the bound original log path. It must not republish the artifact, re-run admission, create evidence, or create a replacement log.

- **Require a strict log read.** Add a separate strict reader in `plan_tool/run_log.py`; retain `read_run_events()` unchanged for tolerant reporting. The strict path rejects unreadable data, invalid UTF-8, malformed JSON, blank or damaged lines, duplicate object members, wrong schema shape, a noncanonical path, a missing or mismatched `run_start`, and any terminal event that does not match the bound run identity and complete payload.

- **Make recovery at most once.** A log with no terminal event may receive the exact bound `run_end` once. A log with exactly one equal bound event succeeds without another append. A duplicate, foreign, partial, or unequal terminal event is a refusal, not a reason to append another event.

- **Keep the recovery result redacted.** Return only stable outcome and identity facts needed by the later CLI. Do not expose the old response, reviewer request, evidence contents, or raw log body.

- **Document the special contract where readers look for log rules.** Update `DATA_CONTRACT.md:## Run log events` to distinguish ordinary tolerant reporting from this strict recovery path and to state that unbound `run_end` records retain their current form.

## Tests

### Tests for this step

- `tests/test_roadmap_artifacts.py::test_guarded_reopen_history_round_trips_without_response_text` — A reopened row preserves the landed response history and emits the redacted run binding without copying response prose.

- `tests/test_roadmap_artifacts.py::test_guarded_reopen_replaces_only_the_selected_active_response_authority` — The artifact helper changes only the admitted feedback row and refuses missing or ambiguous targets.

- `tests/test_roadmap_revision_publish.py::test_guarded_reopen_publication_journals_only_the_selected_artifact` — The reopen publisher replaces one artifact while leaving baseline, seed state, evidence, and sibling artifacts unchanged.

- `tests/test_roadmap_revision_publish.py::test_guarded_reopen_final_admission_refuses_changed_evidence_before_journal` — A changed active receipt or retirement record causes the Step 2 re-admission to refuse before candidate rendering, journaling, or replacement.

- `tests/test_roadmap_revision_publish.py::test_guarded_reopen_journal_contains_the_finally_admitted_frozen_payload` — The journaled artifact bytes contain the exact `run_end` payload frozen after final admission, with no later callback able to change it.

- `tests/test_roadmap_revision_publish.py::test_guarded_reopen_publication_recovery_never_repairs_unrecorded_bytes` — Existing journal recovery retains the refusal for bytes outside the recorded generation.

- `tests/test_run_log.py::test_unbound_run_end_omits_completion_id` — Existing `RunLogWriter.run_end()` callers write no new field unless they explicitly bind a completion.

- `tests/test_run_log.py::test_bound_completion_inspection_requires_the_complete_original_event` — Strict inspection accepts only the full prepared event associated with its original `run_start`.

- `tests/test_run_log.py::test_bound_completion_inspection_rejects_damaged_or_foreign_log_lines` — Tolerant reporting remains available, but recovery refuses damaged, duplicate-key, wrong-run, and noncanonical inputs.

- `tests/test_run_log.py::test_append_bound_completion_is_idempotent_for_one_equal_event` — Zero matching terminal events append once, one equal event appends nothing, and duplicate or unequal terminal events refuse.

- `tests/test_roadmap_feedback_reopen_run.py::test_admitted_reopen_publishes_bound_open_transition_then_one_terminal_event` — A current candidate produces the selected artifact transition, one bound `run_end`, and no backend call.

- `tests/test_roadmap_feedback_reopen_run.py::test_terminal_append_failure_returns_recoverable_without_republishing` — A post-publication terminal-write failure preserves the artifact binding and returns a recoverable result.

- `tests/test_roadmap_feedback_reopen_run.py::test_recovery_appends_only_the_original_bound_completion` — Recovery adds one exact original terminal event, leaves artifact and evidence bytes unchanged, and repeated recovery does not append again.

- `tests/test_roadmap_feedback_reopen_run.py::test_recovery_refuses_mismatched_bound_log_without_changing_artifact` — A malformed, foreign, duplicate, or unequal terminal event leaves the reopened artifact untouched.

- `tests/test_data_contract.py::test_run_end_completion_recovery_contract_is_documented` — `DATA_CONTRACT.md` documents the optional identity, strict comparison rule, and redaction boundary.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An admitted current candidate publishes exactly one selected roadmap artifact containing the open-state transition and its redacted original-run binding.

- The guarded reopen changes no baseline, seed state, immutable evidence file, or unselected artifact.

- The bound history records the original `run_id`, canonical repository-relative log path, full prepared terminal payload, and `completion_id`, without response prose or evidence contents.

- A changed row, locator, classifier result, or verified bytes refuses before candidate rendering or journaling, and leaves no pending publication journal.

- The journaled artifact contains the complete terminal payload frozen immediately after final admission; duration is measured at that boundary and no later re-admission callback changes it.

- A normal run writes exactly one `run_end` equal to the payload bound into the reopened artifact.

- A terminal-log append failure returns a recoverable result after publication without inventing a successful terminal record.

- Recovery reads the original log strictly, appends at most one equal bound terminal event, and never republishes the artifact or changes evidence.

- Existing unbound `RunEnd` records omit `completion_id`, and `read_run_events()` retains its tolerant reporting behavior.

- The focused suites in `tests/test_roadmap_feedback_reopen_run.py`, `tests/test_roadmap_revision_publish.py`, `tests/test_roadmap_artifacts.py`, `tests/test_run_log.py`, and `tests/test_data_contract.py` pass.

## References

- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Review file replacement and append error behavior used by the durable publisher and log writer.

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Review safe loading and dumping behavior for the extended feedback-row frontmatter.

- [RFC 8259: The JSON Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Use for the strict JSON object and complete-payload recovery rules.

## Applicable guardrails

- **The plan’s “## Plan intent”, supported recovery path** — Keep every change focused on restoring one evidence-blocked row through the admitted guarded path.

- **The plan’s “## Step intent”, durable and recoverable reopen** — Preserve the atomic publication and recovery boundary; do not add raw-edit, evidence-mutation, ordinary-eligibility, or duplicate-log behavior.

- **The plan’s “## Out of scope”, general feedback editing** — Do not turn the artifact helper or runner into a general lifecycle editor.

- **The plan’s “## Out of scope”, ordinary re-escalation** — Do not route ordinary feedback through this runner or change the existing selection behavior.

## Deferred

- CLI parsing, explicit operator confirmations, result rendering, and review-ledger display — Step 5 owns the public workflow.

- Generic terminal-publication infrastructure for `plan_tool/roadmap_escalation_run.py` and `plan_tool/roadmap_impact_run.py` — These runners have related lifecycle handling, but consolidating their different artifact and evidence contracts is a separate refactor.

- Broader retention and evidence-lifecycle redesign — This step records only the binding needed to recover one admitted reopen.
