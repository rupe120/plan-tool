> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Show the exact before/after correction in structural review and the stack digest, and prove the Integration Decisions correction end to end

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes step 4's `correct-prose` operation visible and confirmable at the structural approval gate. `plan_tool/roadmap_candidate.py:candidate_prose_amendment_diffs` gains a second projection that gives the full before text and after text for each correction. `plan_tool/cli/roadmap_cmd.py:_print_prose_amendment_diffs` prints those lines in the structural disclosure, in every stack hop and in the top-candidate disclosure. The stack digest in `plan_tool/roadmap_candidate_review.py:_stack_view_identity_input` must move when a correction's text moves. The step also pins that an edit decision keeps the correction operation and yields a new digest, so approval of the old text cannot confirm the new text. Last, one end-to-end test runs the real Integration Decisions paragraph (1,288 bytes, checked in as a fixture) through candidate, review, and approval with Group 4 untouched.

## Table of Contents

- [Why](#why) — the approver cannot see a correction today
- [Input](#input) — outputs of steps 4–6 and the review and digest code this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — touched files and the new fixture
- [Implementation](#implementation) — display, digest, edit route, and the end-to-end proof
- [Tests](#tests) — cases by file, with the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — diff, hash, and UTF-8 references
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work other steps or plans own

## Why

The plan intent is that an approver sees and confirms the exact before/after text before promotion. Steps 4–6 make a correction storable and replayable, but the structural review surface still prints only add-row fragments through `candidate_prose_amendment_diffs`. Without this step an approver would confirm a stack digest for a paragraph change they were never shown. This step also closes the plan's acceptance case on the real motivating paragraph, which no earlier step runs end to end.

## Input

- **Step 4 output:** `correct-prose` is a member of `CandidateDeltaOperation` in `plan_tool/roadmap_candidate.py`, bound to an issued span. Read the landed class name, field names, and the span-binding fields from that module. The landed names win over any name used here.
- **Step 3 output:** the capsule carries each issued shared span with its id, text, and owning set (`plan_tool/roadmap_candidate_context.py`). The "before" text is the stored span text. Read it from stored evidence, not from the live artifact.
- **Step 6 output:** `normalized_operations` carries corrections and replays them (`plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_operations`). Where this detail and step 6 disagree on replay behavior, step 6 wins.
- **Display today:** `candidate_prose_amendment_diffs` returns only `CandidateAddRow` fragments as `CandidateProseAmendmentDiff` records. `plan_tool/cli/roadmap_cmd.py:_print_prose_amendment_diffs` prints them as one `row-linked prose amendments:` line, always, with `[]` when empty. It is called from the stack hop loop in `_render_structural_candidate_stack` and from the proposal result render at `_render_candidate_proposal_result`.
- **Digest today:** `CandidateStackView.digest` hashes `_stack_view_identity_input`, which already includes each hop's `typed_operations` (`hop.evidence.normalized_operations`), `own_diff`, and the cumulative diff. A correction that is in `normalized_operations` is therefore covered by structure. The cumulative and own diffs are row diffs from `plan_tool/roadmap_diff.py` and may not show body-only changes. That is the gap to check.
- **Edit route today:** `_edit_structural_candidate` renders the batch prompt with the reviewer correction, parses the response through `parse_candidate_proposal_response`, and calls `roadmap_candidate.materialize_candidate`. It stores a new replacement candidate with its own stack. The CLI prints the replacement's stack and no confirm (`plan_tool/cli/roadmap_cmd.py`, the `edit` branch near `_render_structural_candidate_stack(replacement_view)`).
- **Sibling consumer:** `plan_tool/roadmap_compare_run.py` maps `candidate_prose_amendment_diffs` into `ComparisonProseAmendment`. It is not in this step's files.
- **Fixture source:** the Integration Decisions paragraph lives in integration-aidlc-mvp's `01-domain.md`. It is 1,288 UTF-8 bytes and names rows that Group 4 already settled. `tests/fixtures/roadmap/integration-scale-domain.md` is an existing Integration-derived fixture and shows where roadmap fixtures live.
- **Limit on verification:** the end-to-end test drives canned model responses. It proves the correction path works on the real paragraph, not that a model usually writes a good correction.

## Files (creates vs edits)

- **New files:**
  - `tests/fixtures/roadmap/integration-decisions-paragraph.md`: the 1,288-byte Decisions paragraph, copied unchanged from integration-aidlc-mvp's `01-domain.md`. This path is an addition to the declared files list. It is a fixture the step's own acceptance case needs.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate.py`: add a projection of corrections for display (before text, after text, owning row ids). Keep `candidate_prose_amendment_diffs` returning add-row fragments only.
  - `plan_tool/roadmap_candidate_review.py`: make sure the digest input covers each correction's stored before text and after text. Make the edit route's behavior explicit if it needs a change (see Implementation).
  - `plan_tool/cli/roadmap_cmd.py`: print the correction lines beside the row-linked amendments line in the hop render and the disclosure.
  - `tests/test_roadmap_candidate_review.py`: digest, edit-route, and end-to-end cases.
  - `tests/cli/test_roadmap_cmd.py`: render cases next to `test_structural_disclosure_prints_row_linked_prose_amendment_records`.

## Implementation

- **Show exact text, not a summary.** Print each correction as its own labeled lines: artifact key, owning row ids, the full before text, and the full after text. Use stored values from the operation and the capsule span, and never re-read the live artifact. A paragraph is at most a few KiB, so printing both sides in full is within bounds. Rejected alternative: a unified diff through `difflib`. It is optional later polish, and the approver needs both complete texts first.
- **Keep a separate projection.** Add a new record and a function beside `CandidateProseAmendmentDiff` and `candidate_prose_amendment_diffs`. Do not widen the existing record. `plan_tool/roadmap_compare_run.py` consumes it and builds `ComparisonProseAmendment` from add-row fragments only, so widening would change that consumer's output. Any comparison-side display of corrections is separate work (see Deferred).
- **Print unconditionally.** Follow the explicit-empty convention of `_print_prose_amendment_diffs`: print a corrections line with `[]` when there are none. Print it in both places that print amendments today, so a lower hop and the top candidate behave the same way.
- **The digest must move when the correction text moves.** Verify first, then fix only if needed. Because `typed_operations` is the stored `normalized_operations`, a changed correction should already change the digest. Do not assume this: an edit that changes only the after text of a correction changes no typed row, so only `typed_operations` can carry it. If the operation is serialized in a form that drops either text (for example, only a span id and a digest), add the before and after text, or their digests, to `_stack_view_identity_input` for each hop. State the covered facts in the docstring. The digest must stay a hash of structured facts and not of printed text, as its class docstring says.
- **An edit is a new candidate with a new digest.** Do not add confirm-reuse logic. The edit route stores a replacement candidate with its own version id, so its stack digest differs whenever the version id or operations differ. The approver must run approve without `--confirm-stack-digest`, read the new stack, and then confirm. Pin two facts. First, the replacement keeps the `correct-prose` operation when the reviewer correction does not remove it. This holds because the edit prompt carries the same capsule with its issued spans (step 3 and step 5), so check that `parse_candidate_proposal_response` accepts the operation on the `allow_expansion=False` path. Second, the old digest is refused for the replacement. Reuse the existing mismatch refusal and do not write a second one.
- **End-to-end proof.** Build the root artifact from the fixture paragraph placed in a domain artifact body, with Group 4's accepted feedback in the ledger. Run a batch candidate whose canned response is one `correct-prose` operation on the issued Decisions span. Check these facts:
  - the fixture's candidate context shows every live row the paragraph names (as a full member or an inventory entry), so the shared span is issued; a context missing one of them withholds the span, which is the not-issued case step 3 already tests;
  - the candidate artifact differs from the root only inside the issued span, and frontmatter bytes are unchanged;
  - the Group 4 ledger items and their snapshots are unchanged;
  - the structural stack output shows the exact before and after text;
  - approve without confirm seals nothing, and approve with the printed digest promotes;
  - the promoted artifact's body, outside the span, equals the root's byte for byte.
  Reuse the helpers imported from `tests/test_roadmap_candidate_run.py` (`_store_stack`, `_approve_structural_candidate`, `_run_batch`, `_seed_batch_ledger`, `_batch_item`, `_prompt_following_invoker`) before writing new ones.
- **Do not add a quality check.** `plan_tool/roadmap_gates.py:check_inventory_has_prose` stays as the only gate on the corrected body. This step shows the text and asks the approver to judge it.
- **Constraints that are not free to vary:**
  - the display reads only stored evidence;
  - the digest input stays structured facts;
  - no new CLI flag, no change to `--confirm-stack-digest` semantics, and no change to the `edit` decision's one-question contract.

## Tests

- `tests/test_roadmap_candidate_review.py`:
  - `test_stack_digest_moves_when_only_a_correction_after_text_moves` — two stacks equal in rows and before text, with different after text, give different digests; it must fail if the digest input drops the after text.
  - `test_stack_digest_moves_when_only_a_correction_before_text_moves` — the stored before text is covered by the digest.
  - `test_digest_is_unchanged_for_a_stack_with_no_corrections` — an add-row-only stack's digest equals the value computed from the unchanged input shape, so existing stored approvals stay valid.
  - `test_structural_edit_keeps_the_correction_operation_in_the_replacement` — an edit whose canned response again carries `correct-prose` stores a replacement with that operation in `normalized_operations`.
  - `test_edit_replacement_requires_a_fresh_approval_and_refuses_the_prior_digest` — confirming the replacement with the original candidate's digest is refused; the replacement's own digest is accepted.
  - `test_integration_decisions_paragraph_correction_end_to_end_leaves_group_four_untouched` — the full flow from Implementation, including byte equality outside the span and unchanged Group 4 ledger items.
  - `test_integration_decisions_fixture_is_the_recorded_size` — the fixture file is exactly 1,288 bytes, so a silent edit to the fixture fails loudly.
- `tests/cli/test_roadmap_cmd.py`:
  - `test_structural_disclosure_prints_exact_before_and_after_for_a_correction` — the render contains the complete before and after text and the owning row ids, asserted by labeled keys and not by loose words.
  - `test_structural_disclosure_prints_empty_corrections_line_when_none_present` — an explicit empty line, matching the sibling empty-amendments test.
  - `test_every_stack_hop_prints_its_own_corrections` — a lower hop's correction is printed under that hop, not only the top candidate's.
  - `test_correction_display_reads_stored_evidence_not_the_live_artifact` — editing the live artifact between store and render does not change the printed text.

### Tests for this step

Every case above must be green before this step is done. The two digest-movement cases and the stale-digest refusal are the ones that pin the approval guarantee, so verify them by mutation: remove the correction text from the digest input and confirm they go red. Existing add-row amendment tests in both files stay unedited and must stay green.

## Acceptance criteria

- A structural candidate with one correction prints a labeled artifact key, owning row ids, full before text, and full after text, in the hop render and in the top-candidate disclosure.
- A candidate with no correction prints an explicit empty corrections line.
- Changing only a correction's before text or after text changes the stack digest. A stack with no correction keeps its previous digest.
- A replacement produced by `edit` carries the correction when the reviewer correction keeps it, and approving it with the original candidate's digest is refused.
- The end-to-end test on the 1,288-byte Decisions fixture shows a promoted artifact that differs from the root only inside the issued span, with Group 4 ledger items unchanged.
- `candidate_prose_amendment_diffs` and its record are unchanged in output for add-row operations, and `plan_tool/roadmap_compare_run.py` needs no edit.
- `tests/fixtures/roadmap/integration-decisions-paragraph.md` exists and is exactly 1,288 bytes.

## References

- [difflib — Helpers for computing deltas (Python standard library)](https://docs.python.org/3/library/difflib.html) — Read for `unified_diff`, which is the option for a later compact before/after view.
- [hashlib — Secure hashes and message digests (Python standard library)](https://docs.python.org/3/library/hashlib.html) — Read for the SHA-256 API behind the stack digest and the span digests.
- [RFC 3629 — UTF-8, a transformation format of ISO 10646](https://www.rfc-editor.org/rfc/rfc3629) — Read for why the fixture size is counted in UTF-8 bytes and not characters.

## Applicable guardrails

- **The plan's "## Scope guardrails" and "## Out of scope", on arbitrary body replacement and generic document editing:** the display and the test only handle the issued span. Nothing here adds a way to edit any other part of the body.
- **The plan's "## Scope guardrails", on weaker described-row gates:** the end-to-end test runs the existing complete-roadmap gates unchanged. Do not relax a gate to make the fixture pass.
- **The plan's "## Scope guardrails" and "## Out of scope", on Group 4:** the test must not rewrite accepted Group 4 feedback or require a new feedback group. Assert that the ledger is unchanged.
- **The plan's "## Out of scope", on the review-evidence layer for narrative contradictions:** the approver sees the text and judges it. This step adds no check on whether the new text is right.
- **The plan's "## Scope guardrails", on stale-row references:** a removed row named in the fixture paragraph gives no authority over the body. The end-to-end test must not depend on one.

## Deferred

- Showing corrections in the `roadmap_compare_run.py` comparison output — a separate consumer outside this step's files, and widening it changes its evidence contract; carved to BACKLOG #436.
- A unified-diff rendering for long paragraphs — optional polish; the full before and after text satisfies the acceptance case.
- Syncing `ROADMAP_FORMAT.md` and `docs/ARCHITECTURE.md` to the landed display and digest facts — step 8 owns the doc sync.
- Any check that detects a correction that contradicts other prose — out of scope per the plan's review-evidence fence.
