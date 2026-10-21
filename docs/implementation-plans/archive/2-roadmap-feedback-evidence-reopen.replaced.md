> **Replaced (2026-08-26):** this plan has been superseded by `docs/implementation-plans/2-roadmap-315-guarded-reopen-proof.md`.
> It describes an eventual response-history and evidence-recovery capability, not the selected #315 proof. Preserved for history; do not execute or extend it.

---
title: Roadmap Feedback Evidence Reopen
intent: Restore a supported recovery path for feedback blocked by unusable immutable
  escalation evidence while preserving history and ordinary already-responded protections.
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Define active response-ledger pointers, operator attestations, and per-attempt
    identities
  intent: Preserve every active response's exact ledger identity and provenance, and
    give every reopened attempt a distinct identity without letting a ledgered clear
    enter ordinary selection.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_gates.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_revision_patch.py
  - plan_tool/roadmap_revision.py
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_structural_revision_patch.py
  - plan_tool/roadmap_structural_revision.py
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_artifacts.py
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_format.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap_revision_patch.py
  - tests/test_roadmap_revision.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision.py
  creates:
  - plan_tool/roadmap_evidence_retirement.py
  - tests/test_roadmap_evidence_retirement.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/01-define-active-response-ledger-pointers.md
  status: current
- id: 2
  title: Publish retirement records, classify one invalidation reason, and bind verified
    evidence bytes
  intent: Keep archived evidence inspectable through a supported producer, including
    a bounded import for the recorded version-1 archive, while preventing ambiguous
    invalidation, byte substitution, untrusted history traversal, or old evidence
    from regaining active authority.
  files:
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_evidence_retirement.py
  - plan_tool/roadmap_evidence_store.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_run.py
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_structural_revision.py
  - plan_tool/roadmap_structural_revision_proof.py
  - ROADMAP_FORMAT.md
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_evidence_retirement.py
  - tests/test_roadmap_evidence_store.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_run.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision_proof.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: provides the response provenance and attempt identity that every reader compares
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/02-publish-retirement-records-classify-one.md
- id: 3
  title: Admit one verified or explicit operator-attested reopen, preserve the old
    response, and restore guarded eligibility
  intent: Let an operator establish a missing or no-longer-provable association without
    creating a general already-responded bypass or an invalid cleared awaiting-review
    row.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/run_log.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_revision_patch.py
  - tests/test_roadmap_structural_revision_patch.py
  - tests/test_roadmap_structural_revision_proof.py
  - tests/test_roadmap.py
  creates:
  - plan_tool/roadmap_feedback_reopen.py
  - tests/test_roadmap_feedback_reopen.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: provides the immutable record that receives the attested response and evidence
      identity
    2: provides the closed invalidation and active-attempt admission predicates
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/03-admit-one-verified-explicit-operator.md
- id: 4
  title: Atomically publish the guarded reopen, bind its complete original log event,
    and recover safely
  intent: Make reopening durable and recoverable without raw edits, immutable-evidence
    mutation, an ordinary eligibility bypass, or a duplicate terminal log event.
  files:
  - plan_tool/roadmap_artifacts.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/run_log.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_artifacts.py
  - tests/test_run_log.py
  - DATA_CONTRACT.md
  - tests/test_data_contract.py
  creates:
  - plan_tool/roadmap_feedback_reopen_run.py
  - tests/test_roadmap_feedback_reopen_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 3
  depends_on_notes:
    1: provides the canonical response history and reissue identity
    3: provides the admitted attestation; this runner performs the final-boundary
      recheck
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/04-atomically-publish-guarded-reopen-bind.md
- id: 5
  title: Add exclusive retirement import, reopen, and recovery CLI modes with a safe
    review view
  intent: Require an operator's explicit confirmation for each trust boundary and
    make the resulting record or attempt auditable without exposing prior response
    text.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - plan_tool/roadmap_view.py
  - CAPABILITIES.md
  - TESTING.md
  - docs/cli/roadmap.md
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  - tests/test_roadmap_view.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 4
  depends_on_notes:
    2: provides the closed reason and active-attempt result that the CLI must render
    4: provides the guarded backend-free runner and terminal outcomes
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/05-exclusive-retirement-import-reopen.md
- id: 6
  title: 'Record #315''s delivered outcome and document the recovery boundary for
    #242'
  intent: 'Keep the shipped operator and architecture contract aligned with the #315
    outcome and the future #242 redesign.'
  files:
  - RUNBOOK.md
  - docs/ROADMAP_WALKTHROUGH.md
  - docs/ARCHITECTURE.md
  - BACKLOG.md
  - BUG_BACKLOG.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md
  complexity: high
  change_type: non-code
  depends_on:
  - 5
  depends_on_notes:
    5: provides the final command syntax, outcomes, and tested operator sequence
  detail: docs/implementation-plans/plan-details/roadmap-feedback-evidence-reopen/06-record-315-delivered-outcome-document.md
---
# Roadmap Feedback Evidence Reopen

## Overview

This plan implements [BACKLOG #315](../../BACKLOG.md) with an explicit, auditable way to reopen or reissue a roadmap feedback row when its `proposed_response` is tied to unusable immutable escalation evidence. The operator explicitly confirms the otherwise-unprovable response-to-evidence association, and the tool records that confirmation as an attestation rather than presenting it as machine-verified fact. The mechanism preserves the original response, distinguishes the reopened attempt, and allows a newly eligible row to issue fresh versioned evidence without raw hand edits. It retains ordinary already-responded protection and remains separate from roadmap revision retention #242.

## Problem statement

A roadmap feedback row can become permanently ineligible when its `proposed_response` is tied to immutable escalation evidence that can no longer be admitted. The Integration preflight on 2026-08-26 shows the active shape: `domain:fb-plan-tool-lifecycle-responsibilities` is `awaiting-review` with a response, so an exact receipt preflight returns `not-open` and cannot produce a receipt-analysis pair for #242. Existing row data does not prove which old evidence, if any, produced a particular response. The recovery path therefore needs an explicit operator confirmation that preserves this distinction instead of inferring the link or requiring raw data edits.

## Architecture

Add a bounded reopen/reissue mechanism with two response-provenance classes. Future response writers append a new immutable response-ledger record containing its unique `response_instance_id`, exact response digest and text, and verified or unbound provenance before exposing `proposed_response`; the same atomic replacement sets the row's `active_response_instance_id` to that record. A structural writer records a **verified binding** when it has the exact receipt final, its immutable raw digest, and the receipt's reissue-attempt identity. Generic writers record the same response instance as unbound rather than inventing provenance. A ledgered row with a nonblank active `proposed_response` must carry exactly one `active_response_instance_id` that selects exactly one ledger record whose text and SHA-256 digest match the active text; duplicate, dangling, missing, or mismatched pointers fail parsing and every consumer. The reopen candidate captures that pointer, text, and digest, and its final recheck requires all three to remain equal. A nonblank manual replacement is an artifact-shape refusal, never a new legacy instance or a reuse of prior provenance. A manual clear remains legal only as the paired transition to `open` with no active response or pointer, but it retains its immutable ledger history and is not ordinary receipt or revision eligible. Only the guarded reopen can append a redacted `ReopenHistory` entry and assign a fresh `reissue_attempt_id`, the paired facts that let ordinary receipt and revision admission issue the next attempt. Existing pre-ledger rows have neither history collection nor active pointer and retain their current ordinary manual behavior; a predecessor-aware integrity gate rejects a generated artifact that removes ledger, reopen-history, pointer, or attempt facts to imitate that legacy shape.

A legacy `awaiting-review` response that has no ledger record remains unbound until an admitted reopen preflight derives a `legacy_response_instance_id` from the receipt-safe selector and the SHA-256 digest of its exact UTF-8 text. The runner rechecks that digest at the final boundary and persists that derived identity, text, and attestation only in the same atomic publication; derivation never claims verified provenance and a rejected or interrupted attempt writes nothing. An operator may create one **operator-attested recovery binding** for an unbound or legacy response, or for a verified response whose evidence bytes cannot prove its stored verified digest, by naming one typed `EvidenceLocator` and a closed invalidation reason, confirming the current response instance and digest, and passing a dedicated confirmation flag. `retired` accepts only `RetirementRecordLocator(record_final)` from `--retirement-record FINAL`; `receipt-unreadable` and `receipt-invalid` accept only `ActiveReceiptLocator(receipt_final)` from `--receipt-final FINAL`. Reopen accepts neither an arbitrary path nor a retained-evidence location. A verified response skips a new attestation only when the selected locator and its retained or readable raw bytes match the verified binding's final and raw digest exactly. An unreadable final supplies no comparable bytes, and a readable digest mismatch is not a verified route; each requires the explicit recovery attestation or refuses. That attestation retains the original verified binding as immutable history rather than relabeling it. Every admitted route appends one immutable, redacted `ReopenHistory` record with its original provenance class and its separate `admission_route`. An `operator-attested` route embeds its immutable `OperatorAttestation` record, linked to the same response instance and digest; a verified route has no attestation. Both records retain the classifier result, locator kind and final, and fresh attempt identity. The runner rechecks those linked facts at publication and emits their redacted route facts; the review view reads the persisted records and never needs raw evidence, response text, attestation prose, or a run log to explain a completed reopen.

Confirmation creates one in-memory `ReopenCandidate`; it is not a persisted pending attestation. Under the existing guarded publication lock, the runner recovers any prior publication journal, rereads the selected row, and reruns Step 2's single classifier and byte-binding check against the candidate's typed locator. It refuses if the row, active response-instance pointer, text, digest, response ledger, classifier result, locator, verified bytes, or required recovery attestation differs from the candidate. The runner starts its original run log before admission, derives one opaque completion-event ID, and canonically derives that log's contained relative path from its run ID. Immediately after this final admission and before rendering or journaling a candidate artifact, it freezes the one complete successful `run_end` payload: the original run ID, `reopened` outcome, zero exit code, elapsed duration measured at that final-admission boundary, and completion-event ID. It then constructs, renders, and parses the selected artifact containing the response history, redacted reopen record, selected provenance, fresh `reissue_attempt_id`, and immutable completion binding containing that frozen payload; it journals those exact candidate bytes and atomically replaces the artifact with no later re-admission callback. An interruption before the replacement accepts a retry with the same inputs. Recovery completes or rolls back the journal before another candidate is admitted. If artifact publication succeeds but the terminal run-log append fails, the command returns `committed-log-pending` with the selector and reissue-attempt ID. The exclusive `--recover-reopen ATTEMPT_ID` mode requires that selector, loads exactly its matching completion binding, validates the contained log path and original run ID, and reads the original log. With no matching terminal event it appends exactly the bound `run_end`; with exactly one event that matches every bound field it returns recovered without an append; a missing, malformed, path-mismatched, or conflicting log or event refuses. Recovery never republishes an artifact, creates a new attestation, or writes a second original completion event.

Only a row in `awaiting-review` with one nonblank active response, its matching active response-instance pointer or a derivable legacy identity, and no pending reopen is eligible. The existing `open`-with-response shape remains a legal ordinary manual-reopen state and this command leaves it unchanged; a `deferred` row with a response likewise remains deferred. Both are ineligible for the controlled evidence reopen and refuse without being reclassified as invalid. The admitted reopen moves the current response instance and its provenance record into immutable row history, atomically changes the selected row from `awaiting-review` to `open`, clears its active response slot and pointer, appends its redacted reopen record, and assigns a fresh opaque `reissue_attempt_id`. That action consumes the current response instance: it cannot add, replace, or reuse an attestation for that history entry. Ordinary receipt and revision admission accept an unanswered `open` row only when it is genuinely pre-ledger or carries this matching guarded-reopen record and attempt; a ledgered manual clear is a refusal. A later generated response receives a different response instance and may independently take the same bounded recovery path if it meets every gate; only a pending reopen or the consumed instance refuses.

The receipt and analysis schema version remains 2. Version-2 parsers accept an absent `reissue_attempt_id` for every existing final and calculate the unchanged legacy semantic preimage and final name by omitting that absent field. New reissued receipts require a nonempty attempt identity and include it in the receipt semantic preimage; the copied receipt identity, analysis semantic preimage, and analysis final therefore change together. Every currentness reader accepts an absent identity only for a row without an active reopen attempt, and requires the exact nonempty identity when the row is reopened. The publisher never rewrites an old final, and the later reader behavior preserves it as non-routable history rather than marking it malformed.

The feedback-independent canonical source projection remains unchanged, so the fresh attempt identity—not presentation drift—creates a new immutable receipt and analysis final.

The invalidation vocabulary is closed and mutually exclusive. A `retired` request names only a hash-named retirement-record final through `--retirement-record FINAL`; its `RetirementRecordLocator` resolves a valid `RetiredEvidenceRecord` at the fixed `<roadmap-root>/.plan-tool/evidence/history/retirements/` root. It yields `retired` only after its record final, evidence kind, retained relative path, and raw-byte digest validate, the retained bytes match, and the receipt final is absent from the active namespace. The producer and later classifier use the same descriptor-based no-follow traversal from that fixed resolved root: every traversed component, the record final, and the retained-evidence final must be non-symlink, the two leaf entries must be regular files, and the resolved descriptor targets must stay below the root. A symbolic link, non-regular entry, failed containment check, or descriptor-read failure makes the retirement record invalid and refuses rather than falling through to another reason. For a verified route, those retained bytes must also SHA-256-match the binding's raw digest; otherwise only an explicit recovery attestation can proceed. `plan-tool roadmap --record-retired-evidence FINAL --retained-evidence PATH --confirm-retirement` is the separate, model-free producer: it accepts only such a contained regular history file, verifies its bytes and active-namespace absence, and immutably publishes the record without touching a feedback row. One equally narrow import, `--import-retired-evidence FINAL --legacy-evidence PATH --confirm-retirement`, admits a regular non-symlink file only from the documented `<roadmap-root>/.plan-tool/evidence/history/2026-08-26-v1-retirement-archive/` root, copies its verified bytes into the fixed retirement root, and then publishes that same record. It neither broadens the reader root nor accepts arbitrary history paths. The reopen flow only reads the named record and its rooted retained file; it cannot create, amend, or select another history root.

An active-evidence request names only an active receipt final through `--receipt-final FINAL`; its `ActiveReceiptLocator` is the sole locator for `receipt-unreadable` and `receipt-invalid`. `receipt-unreadable` applies only when that named regular final exists in the active receipt namespace but an I/O read fails before it returns raw bytes; it cannot directly prove a verified binding and therefore requires an explicit recovery attestation. An absent final is an ineligible `not-found` refusal, not an unreadable reason. Once raw bytes are read, a strict UTF-8 decoding failure is `receipt-invalid`, alongside receipt parsing, schema, final-name, source-path, or semantic-identity validation failure; its raw bytes must SHA-256-match the verified binding before the no-attestation route proceeds, otherwise it also requires the explicit recovery attestation. The supplied CLI reason and locator kind must equal this classifier's one result; no result, a mismatch, or an invalid retirement record refuses. `fresh`, `resolved`, and `source-unavailable` are not reopen reasons. In particular, `resolved` can mean an ordinary response correctly consumed the receipt and never grants a reopen bypass.

Every receipt and analysis reader compares a selected row's active `reissue_attempt_id` with the candidate receipt before treating it as current. Ordinary receipt, local-revision, and structural-revision selection additionally reject a ledgered answered or cleared row unless its matching guarded-reopen record carries that active attempt; a genuine pre-ledger unanswered row remains eligible. This comparison applies in `current_escalation_receipt`, impact-analysis receipt admission, structural selected-slice loading, structural publication proof, `select_receipt_feedback()`, and revision preflight. Earlier attempts remain inspectable history, but cannot become current merely because the row returns to `open`.

Eligibility, the closed invalidation predicates, the explicit confirmation, and ordinary already-responded protection remain deterministic gates. The CLI and review view expose safe identifiers, original provenance class, separate admission route, invalidation reason, and attempt identity without echoing prior response text, so recovery never relies on raw hand edits.

The design must determine whether this bounded mechanism is safely independent of #242. It does not redesign or execute #242, which remains separate until it is re-grounded against the landed bounded stage-feedback route in [`backlog-arc-roadmap.md`](backlog-arcs/backlog-arc-roadmap.md)'s ordered route item 0.

## Input

The plan consumes roadmap feedback-row state, including `proposed_response`, `active_response_instance_id`, `awaiting-review`, response-ledger provenance, redacted reopen history, immutable escalation evidence, and the exact receipt preflight contract that can produce a receipt-analysis pair for #242. The active input shape is `domain:fb-plan-tool-lifecycle-responsibilities`, whose exact receipt preflight returns `not-open`. The reopen command accepts exactly one receipt-safe selector in `awaiting-review`, one existing nonblank response whose active pointer selects its matching ledger record or a legacy response whose exact text can derive an identity, and exactly one reason-matching locator: `--retirement-record RECORD_FINAL` for `retired`, or `--receipt-final RECEIPT_FINAL` for `receipt-unreadable` or `receipt-invalid`. It accepts neither an arbitrary path nor both locator forms. A raw-reader I/O failure is `receipt-unreadable`; after raw bytes are read, strict UTF-8 decoding and every receipt validation failure are `receipt-invalid`. A retirement locator is valid only through the fixed-root no-follow regular-file traversal; the one import mode may copy only the documented version-1 archive into that root after the same source checks. Every route requires `--confirm-response-evidence`: it is an operational acknowledgement for a byte-verified route and records the recovery association for an unbound, legacy, unreadable, or byte-mismatched route; `-y` never supplies it. The exclusive recovery mode accepts only the same receipt-safe selector and `--recover-reopen ATTEMPT_ID`; it accepts no evidence, reason, or confirmation inputs, and resolves only an immutable matching completion binding in that row's history. The normal command creates only an in-memory candidate after publication-journal recovery, then refuses missing or blank responses, a duplicate, dangling, or mismatched active pointer, a committed recovery attestation for the current response instance, a wrong locator kind, and, for a claimed `retired` reason, an absent, invalid, or record-attribute-mismatched retirement record. Recovery refuses a nonmatching attempt, noncontained path, wrong run ID, missing or malformed original log, or conflicting completion event. Both modes leave the legal ordinary `open`-with-response and every `deferred` row unchanged.

## References

- [Configuration | Pydantic Docs](https://docs.pydantic.dev/latest/api/config/) — Defines strict, frozen, and extra-forbidden models for closed immutable evidence and history records.
- [Validators | Pydantic Docs](https://docs.pydantic.dev/latest/concepts/validators/) — Explains field and model validators needed for deterministic reopen eligibility and evidence-admission gates.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Documents safe YAML loading, dumping, and node composition for preserving and updating feedback-row frontmatter.
- [argparse — Parser for command-line options, arguments and subcommands](https://docs.python.org/3.13/library/argparse.html) — Documents subcommands, argument groups, and mutual exclusion for the bounded reopen and reissue CLI workflow.
- [hashlib — Secure hashes and message digests](https://docs.python.org/3.13/library/hashlib.html) — Defines SHA-256 APIs used to bind versioned evidence, source digests, and fresh semantic identities.
- [os — Miscellaneous operating system interfaces](https://docs.python.org/3.13/library/os.html) — Documents exclusive file creation, hard linking, fsync, and replacement primitives for durable immutable evidence publication.
- [RFC 8259: The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259.html) — Defines interoperable JSON syntax, UTF-8 encoding, object-member rules, and numeric constraints for strict versioned evidence records.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A general feedback editor — this plan provides only the bounded reopen/reissue path.
- Ordinary re-escalation — this mechanism addresses permanently ineligible rows tied to `retired`, `receipt-unreadable`, or `receipt-invalid` immutable escalation evidence.

## Risks

- **An over-broad reopen gate could bypass ordinary already-responded protection (high).** Require only one `awaiting-review` row with one answered response instance, its exact active pointer or a derived legacy identity, one exact evidence locator, one closed invalidation reason, a matching current-response digest, any required dedicated operator confirmation, and a final-boundary eligibility recheck. An `open` or `deferred` row, a bare final name, `-y`, a normal `resolved` receipt, or an unbound inference is a refusal. A ledgered manual clear is also a refusal in ordinary selection; only its matching guarded-reopen record and fresh attempt restore eligibility. The predecessor-aware integrity gate rejects generated removal or alteration of any prior history field. Each future invalidation reason requires an explicit contract and test rather than a permissive fallback.
- **Operator attestation is a deliberate trust boundary (high).** The current model cannot verify every legacy response-to-evidence link or compare every formerly verified evidence byte stream. Keep an immutable `OperatorAttestation` record linked to its exact response instance and digest inside the reopen record, label its separate admission route `operator-attested`, and emit the same redacted route facts in the original run log. Never promote it to `verified` or relabel an existing verified binding. One recovery attestation applies only to one response instance and is consumed by its reopen; the command has no overwrite, edit, reuse, or batch form, so an attestation cannot silently change a prior record.
- **A manual nonblank replacement could inherit stale provenance (high).** For every ledgered row, require the active pointer to select one record whose text digest matches the active response at parse, selection, reopen preflight, and final publication. Preserve a clear-only manual exception that clears the pointer, but reject a replacement before it can bind an old response instance or receive a recovery attestation.
- **A changed final or completion payload could commit stale evidence (high).** Under the writer lock, rerun the single Step 2 classifier and byte-binding check before constructing the artifact candidate. Freeze the full terminal payload at that final-admission boundary, embed it in the rendered candidate, and journal those exact bytes with no later recheck callback. Any changed result refuses before a journal or replacement.
- **An interrupted confirmation or terminal log append could create a retry-blocking partial state (high).** Keep confirmation in an in-memory candidate, recover the existing publication journal before a final recheck, and persist the history, attestation when applicable, redacted reopen record, and complete immutable original-log terminal payload only in the same atomic replacement as the reopened row. A pre-publish interruption is retryable; after publication, the selector plus reissue-attempt ID recovers only the one bound original completion event and reports recovered instead of re-attesting or republishing.
- **A retirement record could reintroduce an untrusted history root or byte substitution (high).** The separate, explicit retirement-record command accepts and reads only a regular non-symlink file through descriptor-based no-follow traversal below the fixed resolved evidence-history root; its record final receives the same treatment. It verifies retained bytes and active-namespace absence, then immutably publishes a hash-named record. The equally bounded version-1 archive import reads only the documented archive root through the same checks, copies verified bytes into the fixed root, and then records them. Reopen only reads that record through the fixed-root traversal; a verified route also compares the retained bytes with its stored raw digest. A link, non-regular entry, containment failure, or invalid retirement record fails closed and never falls through. A valid retained record whose bytes do not match the stored verified digest cannot use the verified route and requires the separate recovery attestation.
- **Overlapping evidence failures could make the operator choose a bypass reason (high).** Classify `retired` first from a valid no-follow retirement record, `receipt-unreadable` only when I/O fails before raw receipt bytes are read, and `receipt-invalid` after a successful raw read whose strict UTF-8 decoding or validation fails. A verified route requires byte equality for `retired` and `receipt-invalid`; unreadable or mismatched bytes require a recovery attestation. A missing final has no reopen reason, and the supplied CLI reason must match the classifier.
- **A partial failure could leave response history, the selected artifact, the journal, or the run log inconsistent (high).** Publish through the guarded reopen runner, preserve the baseline and immutable evidence finals, and retain recovery metadata until cleanup completes. Filesystem, duplicate invocation, and interruption cases remain part of the required failure-path test matrix.
- **Fresh evidence could reuse or become detached from stale evidence identity (high).** Include the active `reissue_attempt_id` in each reissued receipt's semantic identity and require every receipt/analysis/structural reader to match it. The derived analysis final must change with its receipt. Earlier evidence remains visible as history and must never regain active authority.
- **Adding an attempt identity could invalidate retained version-2 evidence (high).** Keep schema version 2, parse the absent legacy field, omit it from legacy hash preimages, and require a nonempty field only for a new reissue. Test the retained final names and reader behavior for both layouts; never rewrite a published final.
- **Review output could expose the prior response while trying to explain a reopen (medium).** Render the redacted reopen record's attempt identity, original provenance class, separate admission route, invalidation reason, and safe evidence or retirement identity without echoing response text. Raw artifact access remains an intentional privileged inspection path outside the review view.
- **The bounded recovery could accidentally absorb or constrain the broader #242 retention redesign (medium).** Keep reopen-only history and the operator workflow independent, document the boundary, and defer general closed-row retention. #242 still requires redesign against the landed bounded stage-feedback route before implementation.

## Testing

Tests cover active response-instance pointers that select one unique matching ledger record at writing, parsing, every consumer, candidate capture, final recheck, and clear; verified and operator-attested response provenance; reason-specific typed locators (`--retirement-record` only for `retired`, `--receipt-final` only for active unreadable or invalid evidence) with no arbitrary reopen paths; a verified response reopening without a second attestation only when retained or readable bytes match its binding, plus recovery-attestation requirements for unreadable or mismatched bytes; append-only response-ledger and reopen-history behavior through guarded writer and reopen transitions, rejection of generated history stripping, and refusal of a ledgered manual clear by ordinary receipt, revision, and structural selection from Step 1 onward; legacy no-ledger behavior; legacy response-instance derivation and final-boundary digest recheck; final re-admission refusing a changed active final or retirement record before it writes a journal, freezing the entire terminal payload into the journaled artifact bytes after that admission, and recovery appending that exact payload; a redacted reopen record for every provenance route, including both original provenance and a persisted operator-attested route when used; in-memory candidates, journal recovery, committed-log-pending terminal results, an atomic attempt-to-original-log binding with every terminal field, idempotent recovery of exactly one equal `run_end`, and no second publication; a strict-UTF-8 fixture classified as `receipt-invalid`; and retirement producer, version-1 archive import, and reader fixtures rejecting linked, non-regular, resolved-outside-root, or replaced entries while admitting the documented archived evidence only through the fixed root; fresh future response-instance identities; mutually exclusive invalidation classification; ordinary already-responded protection; deterministic gates; atomic recovery; and the CLI, review view, and operator workflow.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Future writers append every response's unique identity, digest, text, and provenance to immutable response-ledger history before exposing it as `proposed_response`, and atomically set `active_response_instance_id` to that exact record. A ledgered row with a nonblank active response must have one pointer to one matching record at parsing and every consumer; a duplicate, dangling, missing, or digest-mismatched pointer fails closed, and a nonblank manual replacement fails closed. A manual clear must atomically move the row from `awaiting-review` to `open`, clear the active pointer, and leave its history intact but ordinary-ineligible. Only guarded reopen may append a redacted reopen record and fresh attempt that restore ordinary eligibility; the predecessor-aware gate rejects generated deletion or change of prior ledger, pointer, reopen-history, or attempt facts. Genuine pre-ledger rows with no history retain their current manual behavior and cannot recover a manually cleared response.
- Only an `awaiting-review` row with one nonblank active `proposed_response` can use this controlled reopen. The legal ordinary manual `open`-with-response state and a `deferred` row remain unchanged and ineligible; a pending reopen also refuses without changing state.
- A legacy eligible response with no instance derives its unverified `legacy_response_instance_id` from its selector and exact response digest, then persists it only atomically with the operator attestation after a final-boundary digest recheck. An unbound response can otherwise reopen only after an operator explicitly confirms the response-to-evidence association. A verified response reopens without a second attestation only when its exact final and retained or readable evidence bytes match the stored binding; an unreadable final or byte mismatch requires one explicit recovery attestation and leaves the original verified binding intact. Every admitted route preserves its original provenance and appends one immutable redacted reopen record with response identity and digest, original provenance class, classifier result, safe evidence or retirement identity, and fresh attempt identity. An operator-attested route additionally persists its linked immutable attestation and labels the separate admission route `operator-attested`; a verified route labels `verified` and has no attestation. All require the current response instance, pointer when ledgered, and digest to match the in-memory candidate and the named evidence to satisfy one classifier-matching invalidation predicate. A valid retirement record takes precedence and yields `retired` only through fixed-root no-follow regular-file traversal; the bounded documented-version-1 import copies verified source bytes into that root before creating such a record. Otherwise an existing final with an I/O failure before raw bytes are read yields `receipt-unreadable`, successfully read bytes that fail strict UTF-8 decoding or receipt validation yield `receipt-invalid`, and missing evidence has no reopen reason.
- Operator confirmation creates only an in-memory candidate, never a pending persisted attestation. After journal recovery, a final `awaiting-review` recheck of the active response, pointer, text, and digest reruns the step-2 classifier and verified-byte check through the candidate’s reason-matching typed locator. It refuses any changed or invalid result before rendering a candidate or journal. The runner freezes the terminal payload at that final-admission boundary, then journals and atomically replaces one artifact that records the response history, redacted reopen record, selected provenance, and `reissue_attempt_id` with its immutable selector-to-original-run-log binding and the whole frozen successful `run_end` payload. That payload has the original run ID, `reopened` outcome, zero exit code, duration measured at final admission, and completion-event ID. An interrupted pre-publish attempt is retryable. A terminal run-log failure after that publication returns `committed-log-pending` with the selector and attempt ID. The exclusive recovery mode validates that binding, appends exactly that one missing payload to the original log, and otherwise returns the existing matching completion as recovered, without a second publication or attestation.
- The recovery attestation remains a linked immutable `OperatorAttestation` inside its reopen record and keeps its separate admission route labeled `operator-attested`. It contains the selector, response instance and digest, exact evidence locator and final, invalidation reason, and confirmation, is rechecked and published atomically with the original provenance, and is single-use for that response instance. The original run log emits the same redacted route facts, and the review view renders both original provenance and admission route without exposing prior response text. It never rewrites a prior verified binding. A later response receives a new instance and may only use a new attestation.
- A structural response records a verified receipt binding with its exact raw digest and a new response instance; generic response writers retain an unbound response instance rather than inventing provenance. An unbound instance, or a verified instance whose evidence bytes cannot match its binding, can use only the explicit attestation path.
- Reopening preserves the original response instance and provenance in row history, atomically changes the selected row from `awaiting-review` to `open`, clears its active response and pointer, appends one redacted reopen record, and assigns one fresh `reissue_attempt_id`.
- Existing schema-version-2 receipt and analysis finals with no attempt identity remain parseable with their existing semantic hashes and stay eligible only for a row without an active reopen attempt. A newly eligible reissued row emits schema-version-2 receipt and analysis finals whose semantic identities include the nonempty active `reissue_attempt_id`; every receipt, impact-analysis, selected-slice, and structural-proof reader rejects an earlier or missing attempt identity after a reopen while retaining historical inspection.
- Ordinary already-responded protection remains in force outside the bounded reopen/reissue case: receipt and revision admission refuse a ledgered manual clear unless the row carries the matching guarded-reopen record and fresh attempt, while a genuine pre-ledger unanswered row retains its current ordinary eligibility.
- Eligibility, explicit confirmation, invalidation, evidence admission, and attempt matching are enforced by deterministic gates. `fresh`, `resolved`, and `source-unavailable` evidence never authorize a reopen.
- The CLI has separate exclusive `--record-retired-evidence`, documented-version-1 `--import-retired-evidence`, reopen, and `--recover-reopen ATTEMPT_ID` modes. The first two require `--confirm-retirement`; reopen requires `--confirm-response-evidence`; recovery requires only the matching selector and attempt ID. Its review view reads the redacted reopen history, and its documentation, tests, and run log cover all bounded workflows without raw response-text disclosure.
- The design records whether the mechanism is safely independent of #242 without redesigning or executing #242.
- Completion updates `BACKLOG.md` #315 with this plan's delivered outcome and verification, removes the then-stale no-reopen statement from the linked bug record, and identifies this separate #315 recovery contract as an input to #242's future redesign without an ambiguous step reference.

## Deferred

- Roadmap revision retention #242 — keep it separate until it is re-grounded against the landed bounded stage-feedback route in the roadmap arc's ordered route item 0.
