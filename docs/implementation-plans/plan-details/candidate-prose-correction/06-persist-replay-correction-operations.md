# Step 6 — Persist and replay correction operations

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes a step-4 `correct-prose` operation survive storage and replay. The operation stays inside `normalized_operations`, and `plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_operations` replays it against the bound predecessor. The replay applies the operations in the contract's order: corrections first, then add-row appends. The main design decision is to reuse step 4's apply-side functions during replay instead of writing a second apply path. That way, storage and replay cannot disagree about what a correction does. Stored candidates with no corrections (legacy and selector-era) must load and replay exactly as they do now. On green, a stored correction candidate replays to its stored artifact bytes and route, a tampered correction is refused, and an interrupted publication leaves no partial candidate behind.

## Table of Contents

- [Why](#why) — what breaks if a correction is stored but not replayable
- [Input](#input) — step 1 and step 4 outputs and the current replay code
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files touched
- [Implementation](#implementation) — persistence, replay order, compatibility, recovery
- [Tests](#tests) — replay, tamper, compatibility, and interruption cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — digest and atomic-write references
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work other steps own

## Why

A candidate is immutable once stored, and promotion and review trust it only because `_require_reproducible_batch_operations` rebuilds its bytes from stored evidence. That function replays operations with `_apply_operation` and then `_append_added_row_prose`, and compares the result to `candidate.content.artifact_bytes`. A `correct-prose` operation that step 4 can apply but replay cannot reproduce would give a candidate that stores fine and then fails every later review or promotion, or worse, replays differently. This step closes that gap.

## Input

- **Step 1 contract:** `ROADMAP_FORMAT.md` § "Reviewer feedback and candidate lifecycle" fixes the application order (correction before add-row appends), the refusal values, and the removed-row rule. Where this detail and the doc disagree, the doc wins.
- **Owning set on replay:** recomputed from the bound predecessor's live rows only (step 1), so replay reaches the accept or refuse result the candidate had when published.
- **Step 4 output:** `plan_tool/roadmap_candidate.py` gains the correction operation as a member of `CandidateDeltaOperation`, with parsing, span binding, a candidate-local byte ceiling, and an apply function that uses step 2's splice helper. Read the landed names from that module. They do not exist at HEAD of this detail's writing, and the landed names win.
- **Storage today:** `normalized_operations` is carried on candidate evidence and on the review requirement (`plan_tool/roadmap_candidate_run.py` validator `_requires_normalized_operations`). It is serialized through `roadmap_candidate._wire_value` and re-parsed through `_operations_wire_for_reparse` plus `parse_candidate_delta`.
- **Replay today:** `_require_reproducible_batch_operations` runs `_prepare_operations`, compares the wire form to the stored form (the "not normalized" check), builds `authority` from `_full_member_authority(evidence.capsule)`, calls `_validate_operation_authority`, then applies each operation with `_apply_operation`, calls `_append_added_row_prose`, assembles with `_assemble_candidate_artifacts`, and compares bytes and `_classify_validated_operations` against the stored route.
- **Legacy skip:** when `normalized_operations` and `operation_classification` are both `None`, the function returns early. Selector-era candidates take the non-batch branch of the caller and never reach it.
- **Limit on verification:** the real model path is not exercised. These tests prove replay is deterministic over stored bytes, not that a model emits good corrections.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_run.py`: extend `_require_reproducible_batch_operations` so the authority loop and the apply loop handle the correction operation, in the contract's order.
  - `plan_tool/roadmap_candidate.py`: only the helpers replay needs and step 4 did not already expose. Likely a small shared "apply all operations in contract order" function so storage and replay call one body. Edit nothing step 4 already settled.
  - `tests/test_roadmap_candidate_run.py`: add the cases under Tests.

## Implementation

- **Persist by membership, not by new field.** The correction is already part of the `operations` union, so `normalized_operations` carries it with no new schema field. Confirm `_requires_normalized_operations` round-trips it through `_operations_wire_for_reparse` and `parse_candidate_delta` unchanged. Add a correction branch to `_operations_wire_for_reparse` only if the parser refuses the wire form (as it does for `DecisionRow.source`).
- **Recommended: one apply function for both paths.** The materialize path in `roadmap_candidate.py` and the replay loop in `_require_reproducible_batch_operations` each apply operations then append add-row fragments. Have both call one function that applies typed-row operations, then corrections, then add-row appends, in the order step 1 states. A second hand-written loop is the rejected alternative: it lets storage and replay drift, and `tests/test_duplication.py` would flag the copy.
- **Authority loop skips corrections.** The existing loop calls `_find_existing_row` for every non-add operation. A correction has no row target, so it must be skipped there, as add-row is. Its authority comes from the capsule-issued span, checked through step 4's `_validate_operation_authority` branch. Replay must check the span against the capsule stored in evidence, not against the live predecessor alone.
- **Bind to the predecessor bytes.** Replay uses `source` (the bound predecessor version) and the stored capsule. A correction whose span text or digest no longer matches the predecessor body must raise `CandidateProposalError` with the "cannot be reproduced" or "exceed stored reviewer authority" message the function already uses. Do not add new message families.
- **Order must hold.** Corrections apply to the predecessor body before add-row fragments are appended. Offsets in a correction are issued against the predecessor body, so appending first would shift them.
- **Route comparison.** `_classify_validated_operations` must classify a correction-bearing set the same way at store time and replay time. Compare against the stored `operation_classification` as today.
- **Legacy compatibility is the carve-out.** A stored candidate with no correction must replay byte-for-byte as before. The early return for `None` evidence stays. Selector-era candidates stay on the non-batch branch.
- **Interrupted publication.** `_store_batch_candidate` publishes through `publish_roadmap_generation` with a `PendingGeneration(kind="candidate-proposal", ...)`. A correction adds no new file or member, so the existing guarded recovery covers it. Verify that by test, not by reading. If an interrupted run could leave a candidate whose stored `normalized_operations` fail replay, the recovery path must refuse it, not promote it. Change recovery only if the test shows a gap.

## Tests

All in `tests/test_roadmap_candidate_run.py`, next to the existing batch replay cases.

- `test_stored_correction_candidate_replays_to_its_stored_artifact_bytes` — a stored correction-only candidate passes `_require_reproducible_batch_operations` and its route matches.
- `test_correction_replays_before_add_row_appends_in_the_contract_order` — a candidate with a correction and an add-row in one artifact replays to bytes where the correction landed in the predecessor body and the fragment is appended after it.
- `test_tampered_correction_text_is_refused_on_replay` — editing stored correction replacement text in `normalized_operations` raises `CandidateProposalError`.
- `test_correction_with_a_span_the_capsule_never_issued_is_refused_on_replay` — a span id or digest absent from the stored capsule exceeds stored authority.
- `test_correction_against_a_changed_predecessor_body_is_refused` — replay against a source whose body differs from the issued span is refused and writes nothing.
- `test_correction_operations_round_trip_through_the_reparse_wire_form` — `_operations_wire_for_reparse` then `parse_candidate_delta` returns an equal operation tuple.
- `test_legacy_candidate_without_route_evidence_still_loads_unchanged` — a candidate with both fields `None` returns early, with unchanged results (the carve-out, pinned by name).
- `test_selector_era_candidate_never_reaches_correction_replay` — a selector-era candidate stays on the non-batch branch.
- `test_interrupted_correction_publication_leaves_no_partial_candidate` — an interrupt during publication leaves no candidate directory that loads, and re-running recovers cleanly.

### Tests for this step

The nine cases above are the roster. Every one must be green before the step is finished. Run `uv run pytest tests/test_roadmap_candidate_run.py tests/test_duplication.py -q` and the existing batch-replay cases to prove nothing regressed. To check the tamper and order tests, break the apply order (append first) and the span check, and watch the matching case go red.

## Acceptance criteria

- A stored candidate with one correction passes replay, and its replayed bytes equal `candidate.content.artifact_bytes`.
- A candidate with a correction and an add-row replays with the correction applied before the append.
- Changing a stored correction's text, span id, or digest makes replay raise `CandidateProposalError`.
- A candidate with no correction replays with results unchanged, and the early return for missing route evidence still exists.
- The apply order exists in one function that both materialize and replay call, and `tests/test_duplication.py` stays green.
- An interrupted publication leaves no loadable partial candidate.
- Only `plan_tool/roadmap_candidate_run.py`, `plan_tool/roadmap_candidate.py`, and `tests/test_roadmap_candidate_run.py` change.

## References

- [hashlib — Python standard library — SHA-256 API behind span digests that replay re-checks.](https://docs.python.org/3/library/hashlib.html)
- [os.replace — Python standard library — atomic replacement behind the no-partial-candidate guarantee.](https://docs.python.org/3/library/os.html#os.replace)
- [RFC 3629 — UTF-8 — byte-exact offsets and the byte ceiling on non-ASCII text.](https://www.rfc-editor.org/rfc/rfc3629)

## Applicable guardrails

- **The plan's "## Scope guardrails", no arbitrary body replacement:** replay re-checks a correction against its capsule-issued span only. It must not accept any body edit outside an issued span.
- **The plan's "## Scope guardrails", stale-row reference grants no authority:** replay must not treat a removed-row reference in a span as authority over the body. Authority comes from the issued span.
- **The plan's "## Out of scope", review-evidence layer (IPPT-19):** replay checks reproducibility only. It must not judge whether a correction resolves a contradiction.
- **The plan's "## Out of scope", accepted Group 4 feedback:** replay must not rewrite stored feedback or require a new feedback group.

## Deferred

- Approver-facing before/after display of the correction — owned by the review-surface work elsewhere in this plan, not this step.
- Prompt text and the `ROADMAP_FORMAT.md` sync to landed symbols — step 5 and step 8.
- Reuse of the shared apply function by other callers — file in `BACKLOG.md` if found; not this step.
