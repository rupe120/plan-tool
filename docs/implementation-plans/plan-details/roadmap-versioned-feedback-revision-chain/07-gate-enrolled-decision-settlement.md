# Step 7 — Gate enrolled decision settlement behind an atomic active-candidate confirmation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_decision_settlement_enrolled.py` so an enrolled decision settlement that would stale the current active candidate uses a non-interactive request/response confirmation handshake. Extend `tests/test_roadmap_decision_settlement_enrolled.py` to cover the request, decline, affirmation, and binding-drift paths. The key decision is that confirmation binds the exact accepted-root and active-candidate pair observed by the request, then the affirmed path rechecks and releases that pair in the same guarded publication as the settlement. On green, a frontend can present a durable confirmation result without terminal input, and no stale approval can settle a changed roadmap.

## Table of Contents

- [Summary](#summary) — Reviewer-level outcome of the confirmation gate.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why a boolean confirmation cannot safely stale an active candidate.
- [Input](#input) — Upstream root, active-candidate, ledger, and publication contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — The scoped production and test changes.
- [Implementation](#implementation) — Request/response binding, guarded recheck, and atomic settlement.
- [Tests](#tests) — Focused handshake and preservation coverage.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Durable publication and locking references.
- [Applicable guardrails](#applicable-guardrails) — Boundaries on artifact and candidate authority.
- [Deferred](#deferred) — Related lifecycle work outside this step.

## Why

`plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement` currently treats confirmation as a simple boolean and blocks an unpromoted candidate lineage outright. After step 5 introduces one root-and-active-candidate processing pair, settlement needs to let a caller explicitly choose whether that active candidate may become stale, without relying on a TTY, allowing a changed candidate to inherit an earlier approval, or leaving the pointer active after the accepted head moves.

## Input

- **Step 1 ledger evidence and readiness.** Consume the landed ledger item and target-provenance contract when validating settlement evidence for an *enrolled* roadmap, and consume `check_ledger_processing_ready` to reject a `migration-pending` roadmap. Settlement must not rewrite ledger bytes or re-evaluate later reviewer edits. At HEAD, `plan_tool/roadmap_decision_settlement.py:build_decision_settlement_candidate` sources its evidence from `matching_feedback_rows` against embedded artifact feedback — that path stays, unchanged, for an *unenrolled* roadmap and for an *enrolled roadmap with no ledger file* (enrolled before the reviewer ledger existed; the ledger file's existence is the same test that selects the batch route for proposals). A roadmap whose ledger file exists has no embedded feedback channel (Architecture, Acceptance criteria), so this step gives it a ledger-backed evidence path instead. Do not recreate migration checks in this runner.

- **Step 5 processing pair:** Consume the landed active-candidate pointer, candidate identity, and the shared `CandidateTerminalResolution` record from `plan_tool/roadmap_candidate_run.py`. Step 5 owns the record's shape and its guarded-publication helper; this step supplies only the release trigger and the `settled` reason. The landed names and record shapes win over this detail.

- **Accepted-head and publication boundary:** Continue to use `plan_tool/roadmap_versions.py:load_accepted_head`, `load_accepted_version`, and `accepted_head_path`, plus `plan_tool/roadmap_revision_publish.py:roadmap_writer_guard`, `recover_roadmap_publication`, and `publish_roadmap_generation`.

- **Evidence-store durability boundary:** Reuse `plan_tool/roadmap_evidence_store.py:publish_evidence` as the durable carrier for the confirmation-required request across two separate CLI invocations — the same content-addressed, read-back-by-exact-final-name convention `--escalate-feedback`/`--analyze-escalation` already use (`docs/ARCHITECTURE.md`, "Structural escalation receipts": never select a receipt from a scan). Call the published object a *confirmation-evidence receipt* everywhere in this step's own prose, tests, and code — never bare "receipt" or "settlement receipt" — because `plan_tool/roadmap_decision_settlement_receipt.py` already owns that name for the existing post-completion proof, and this step's own "confirmation-required... without a [settlement receipt or managed-state] write" language depends on the two staying distinguishable. `EvidenceNamespace.DECISION_SETTLEMENTS` already exists; use it if its existing record shape can hold a confirmation-evidence entry, or add a distinct evidence kind if it cannot — either way, do not invent a second pending-state file format outside `publish_evidence`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_decision_settlement_enrolled.py` — Replace the active-lineage block with the bound confirmation handshake and one guarded settlement-plus-stale-resolution publication.
  - `plan_tool/roadmap_decision_settlement.py` — Give `build_decision_settlement_candidate` an enrollment-aware evidence path: an unenrolled roadmap, and an enrolled roadmap with no ledger file, stay on `matching_feedback_rows` unchanged; a roadmap whose ledger file exists sources evidence from a ledger item instead, refusing `migration-required` first when that ledger is migration-pending.
  - `tests/test_roadmap_decision_settlement_enrolled.py` — Replace lineage-blocking expectations with request, response, binding, atomicity, and no-write coverage.
  - `tests/test_roadmap_decision_settlement.py` — Add enrolled ledger-evidence, migration-pending refusal, and unenrolled-unchanged coverage for `build_decision_settlement_candidate`.

## Implementation

- **Return a structured confirmation request for an active candidate, carried by an immutable confirmation-evidence receipt — not the settlement receipt.** In `plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement`, when a valid settlement would move the accepted root while step 5’s active pointer is present, return `confirmation-required` before publishing the *settlement* receipt or changing any managed state (ledger, candidate, accepted head). "Without a write" governs exactly that managed state and the settlement receipt — it never referred to, and does not forbid, publishing evidence. Include only the exact facts a caller needs to display and later bind: the accepted-root identity, active-candidate identity, and settlement identity evidence. Publish those exact facts as a distinct, immutable *confirmation-evidence receipt* via `publish_evidence` (never call this object "the settlement receipt" — that name stays reserved for the existing post-completion proof `plan_tool/roadmap_decision_settlement_receipt.py` already writes) and include the confirmation-evidence receipt's content-addressed final name in the result, so a caller across two separate process invocations — not just one in-memory call — can carry the binding forward. Keep the result safe for a CLI, web frontend, or container caller; it must not prompt or inspect terminal state.

- **Add a second entry point that reads the confirmation-evidence receipt back by its exact final name.** Provide a `respond_enrolled_decision_settlement`-style function taking the confirmation-evidence receipt's exact final name (never a scan or "the one pending record" lookup — the same explicit-naming convention `--analyze-escalation RECEIPT_FINAL` already uses) plus an affirmative or negative response. Load the confirmation-evidence receipt, treat a missing, malformed, or already-superseded one as a refusal, and only then proceed to the recheck-and-publish below (which is where the settlement receipt and managed state actually change). An affirmative response must name the exact confirmation-evidence receipt; a missing, malformed, negative, or mismatched response must leave every managed record — including the settlement receipt — unchanged. Do not treat `-y`, a truthy object, or an in-memory prompt as consent for an active-candidate settlement.

- **Retain the no-active-candidate path.** When no active candidate exists, preserve the enrolled settlement flow’s existing selector, currentness, receipt, gate, and accepted-head behavior. Do not require a new confirmation round for a settlement that cannot stale a candidate.

- **Recheck inside one writer lease.** Use the existing `roadmap_writer_guard` and recovery flow to re-read the accepted root and active pointer after an affirmative response. Refuse if either identity, the candidate’s terminal state, or the response binding no longer matches the confirmation request. A preflight match alone is not enough.

- **Publish the head advance and the candidate release together; the derived-context set needs no write.** Build one `PendingGeneration` through `plan_tool/roadmap_revision_publish.py:publish_roadmap_generation` that (1) advances the accepted head and (2) records step 5’s shared `CandidateTerminalResolution` with reason `settled` and releases the exact active candidate. The new accepted root owns an empty revision-bound derived-context set by construction: derived entries are keyed by `source_version_id`, so a root nothing has stored against selects none of the released candidate’s entries. Settlement therefore writes no ledger bytes, which this step’s Input forbids in any case. The publication must not leave a new accepted head with the former candidate still active, and it must preserve the candidate’s immutable history.

- **Keep current settlement proof checks, but give evidence resolution an enrollment-aware branch.** Retain `resolve_decision_settlement_selector`, `build_decision_settlement_candidate`, `decision_settlement_candidate_is_current`, `_settlement_gate_evidence`, and `_build_settlement_generation` as the settlement-content checks, adapting their ordering only where the active-pair confirmation requires it. Inside `build_decision_settlement_candidate`, for an unenrolled roadmap, and for an enrolled roadmap with no ledger file, keep the existing `matching_feedback_rows` embedded-artifact lookup exactly as it is today — reading directly from the current accepted artifact is what already makes a stale target impossible there. For a roadmap whose ledger file exists, first load the ledger (a corrupt ledger raises the source-corrupt error rather than a refusal), then call `check_ledger_processing_ready` and return `migration-required` if it refuses; otherwise resolve the evidence selector's id against a ledger item and require it to pass step 1's full eligibility predicate against the current accepted source being settled — `open`, submitted-against predecessor equal to that source, and current target fingerprint exactly matching the target in that source — in addition to the shape the embedded path already enforces: exactly one match, its target is `FeedbackTargetKind.ROW` naming the decision's id, and its request text is non-blank. An item that fails eligibility (stale target, wrong predecessor, or a retained non-`open` state) refuses with the `feedback-not-eligible` verdict, and a missing item keeps `missing-feedback`; do not accept an id match alone; a ledger item can outlive the accepted-source change that a live embedded row cannot, so this recheck is not optional. Continue publishing the receipt before canonical state changes, then recheck all mutable inputs that matter to the publication. That recheck, `decision_settlement_candidate_is_current`, compares the lineage, the exact source bytes, and the evidence digest, because ledger evidence lives outside the source bytes: a reviewer edit to the cited item while the receipt commits refuses as `source-changed`. An edit that lands after that recheck is deliberately not rechecked: the settlement generation writes no ledger member, so such an edit cannot be told apart from one made just after settlement.

- **Do not widen candidate ownership.** Reuse step 5’s pointer and terminal-resolution owner rather than adding a local candidate store, a second accepted-head writer, or a separate transaction format. The runner may coordinate the existing candidate state with settlement, but candidate review, rejection, discard, and promotion remain outside this step.

## Tests

### Tests for this step

- `test_active_candidate_returns_confirmation_required_without_a_settlement_write` — An eligible settlement with an active candidate returns the exact root, candidate, and settlement binding facts without publishing the settlement receipt, changing the accepted head, or changing the pointer. (Publishing the separate confirmation-evidence receipt is covered by the next test, not forbidden by this one.)

- `test_confirmation_required_publishes_a_durable_confirmation_evidence_receipt` — The confirmation-required result includes a confirmation-evidence receipt's exact final name, and a separate process reading that name back gets the same binding facts.

- `test_response_by_missing_or_malformed_confirmation_receipt_name_refuses_without_a_settlement_write` — A response naming a nonexistent or malformed confirmation-evidence receipt final name refuses and writes no settlement receipt or managed-state change.

- `test_declined_confirmation_evidence_preserves_all_managed_state` — A negative response leaves the accepted head, active pointer, candidate history, ledger, and settlement receipt unchanged; the confirmation-evidence receipt from the first call remains as immutable history either way.

- `test_affirmed_bound_confirmation_settles_and_stale_resolves_atomically` — A matching affirmative response advances the accepted head and releases the exact active candidate in one published generation while retaining terminal stale-resolved history.

- `test_affirmed_settlement_releases_the_active_candidate_and_records_it_as_settled_in_one_generation` — The released active candidate's terminal resolution uses step 5's shared `CandidateTerminalResolution` record with reason `settled`, the same shape rejection and discard use.

- `test_settled_root_owns_no_derived_context_from_the_released_candidate_and_the_ledger_is_untouched` — A successful affirmed settlement leaves the ledger bytes unchanged, and a batch built from the settled root carries no derived context from the released candidate, because derived entries are selected by `source_version_id`.

- `test_a_candidate_released_or_replaced_between_request_and_response_refuses_before_any_receipt` — Replacing, releasing, or otherwise changing the active candidate after the request refuses the old response and publishes no settlement.

- `test_affirmed_confirmation_refuses_when_accepted_root_changes` — Moving the accepted head after the request refuses the response and does not stale-resolve the candidate.

- `test_affirmed_confirmation_refuses_when_binding_does_not_match_request` — A response bound to different root, candidate, or settlement facts changes nothing.

- `test_settlement_without_an_active_candidate_keeps_existing_confirmation_path` — A current enrolled settlement with no active pointer completes through the normal receipt and selector-swap flow.

- `test_a_candidate_released_inside_the_publication_window_refuses_and_writes_no_terminal_record` — A release that lands inside the journal window, after the receipt is committed, is caught before canonical publication: nothing is swapped, no terminal record is written, and the receipt stays as evidence of the attempt.

- `test_a_request_edit_to_the_cited_ledger_item_during_the_receipt_commit_refuses_as_source_changed` — A request edit that keeps the cited item eligible, made while the receipt commits, refuses as `source-changed` with the receipt retained and the accepted head unchanged.

- `test_currency_refuses_a_ledger_evidence_edit_that_the_source_bytes_cannot_see` and `test_currency_accepts_a_ledger_edit_that_changes_only_a_model_proposal` — The currency check goes stale on an edited reviewer request and stays current on a proposal-only edit, because a live proposal is model output, never settlement evidence.

- `test_enrolled_settlement_evidence_resolves_from_a_ledger_item_not_embedded_feedback` — A ledger-ready roadmap whose ledger file exists takes its settlement evidence from a matching ledger item; `matching_feedback_rows` is never consulted for it.

- `test_enrolled_roadmap_without_a_ledger_keeps_embedded_feedback_evidence` and `test_both_lineages_build_the_same_settled_bytes_and_evidence_digest` — An enrolled roadmap with no ledger file resolves evidence from embedded feedback exactly as an unenrolled one does, and both build the same settled bytes and evidence digest.

- `test_enrolled_settlement_refuses_a_ledger_item_with_a_stale_target_fingerprint` — A ledger item that otherwise names the decision but whose target fingerprint no longer matches the current accepted source refuses settlement, proving id-and-shape matching alone is not accepted.

- `test_enrolled_settlement_refuses_a_ledger_item_not_submitted_against_the_current_source` — A ledger item whose submitted-against predecessor differs from the accepted source being settled refuses, even when its target fingerprint happens to still match.

- `test_enrolled_settlement_refuses_migration_required_before_evidence_lookup` — A migration-pending enrolled roadmap refuses with the deterministic `migration-required` result before any ledger-evidence lookup.

- `test_unenrolled_settlement_evidence_still_uses_matching_feedback_rows` — An unenrolled roadmap's settlement evidence resolution is byte-for-behavior unchanged from the existing embedded-feedback path.

Every listed test must be green before this step is complete.

## Acceptance criteria

- An enrolled settlement with an active candidate returns a structured `confirmation-required` result before any settlement-receipt or managed-state write — publishing the separate, immutable confirmation-evidence receipt is required, not forbidden, by this rule.

- The confirmation request identifies the exact accepted root, active candidate, and settlement facts needed to bind a later response.

- The confirmation request is durable across process invocations via a confirmation-evidence receipt (distinct from the settlement receipt) read back only by its exact final name; a missing or malformed name refuses without a settlement-receipt or managed-state write.

- A negative, missing, malformed, or mismatched response leaves the accepted head, active pointer, candidate history, ledger, and settlement receipt unchanged.

- An affirmative response succeeds only when the accepted root, active candidate, terminal state, and response binding still match under `roadmap_writer_guard`.

- A successful affirmed settlement advances the accepted head and releases the exact active pointer in one guarded publication.

- A successful affirmed settlement records the released candidate's terminal resolution using step 5's shared `CandidateTerminalResolution` record with reason `settled`.

- After a successful affirmed settlement the new accepted root owns an empty revision-bound derived-context set by construction, with no ledger write, so a later batch sources no context from the released candidate.

- The released candidate remains immutable stale-resolved history and is no longer a processing source.

- A settlement with no active candidate preserves the existing enrolled settlement behavior.

- Settlement evidence for a roadmap whose ledger file exists resolves from a ledger item, never from `matching_feedback_rows`; a `migration-pending` ledger refuses `migration-required` before evidence lookup; an unenrolled roadmap, and an enrolled roadmap with no ledger file, resolve evidence unchanged.

- An enrolled roadmap's ledger-item evidence must pass step 1's full eligibility predicate against the current accepted source (open, matching predecessor, matching target fingerprint), not merely an id-and-shape match; a stale or wrongly-sourced item refuses settlement.

- `tests/test_roadmap_decision_settlement_enrolled.py` and `tests/test_roadmap_decision_settlement.py` pass.

## References

- [os.replace — Read the atomic replacement and durability primitives used by publication.](https://docs.python.org/3.13/library/os.html#os.replace)

- [fcntl — Read the advisory locking behavior behind serialized writer operations.](https://docs.python.org/3.13/library/fcntl.html)

- [hashlib — Read the SHA-256 APIs used for immutable confirmation and receipt identities.](https://docs.python.org/3.13/library/hashlib.html)

## Applicable guardrails

- **The plan’s “Plan intent” — accepted-head writers:** This step may advance the accepted head only through enrolled decision settlement and must not rewrite reviewer feedback.

- **The plan’s “Scope guardrails” — canonical selector:** `AcceptedRoadmapHead` remains the only canonical artifact selector; the active pointer only controls processing and stale resolution.

- **The plan’s “Scope guardrails” — exact candidate binding:** The affirmation must bind the exact root, direct source, candidate, and immutable evidence already selected by the request, not later ledger state.

- **The plan’s “Scope guardrails” — existing publication boundary:** Use the existing guarded recovery and publication path rather than creating another transaction framework or accepted-head authority.

- **The plan’s “## Out of scope” — limited lifecycle work:** Do not add a general approval protocol, extra candidate branches, feedback retargeting, or changes to roadmap gates or stage operations.

## Deferred

- Candidate review, rejection, discard, and review replacement — Step 8 owns those active-candidate lifecycle actions.

- Exact active-candidate promotion — Step 9 owns promotion and its ledger-independent validation.
