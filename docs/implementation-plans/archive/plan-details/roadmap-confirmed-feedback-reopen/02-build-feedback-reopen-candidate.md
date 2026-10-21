> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Build feedback reopen safety checks and candidate construction

## Summary

Create `plan_tool/roadmap_feedback_reopen.py` as the pure contract for deciding whether a receipt-safe selected feedback row is safe to reopen. Add `tests/test_roadmap_feedback_reopen.py` for row safety, ordinary receipt-target viability, source admission, candidate binding, and stale-source checks. Keep the row checks separate from source reads and every write path; the candidate binds a safe row to the exact canonical artifact digest for step 4 to recheck. The checks do not identify unavailable evidence; step 4's explicit operator confirmation is the authority for that determination. On green, only one `awaiting-review` row with a nonblank response, a receipt-resolvable target, and no current record can produce a reusable reopen candidate.

## Table of Contents

- [Summary](#summary) — The completed behavior and its main boundary.
- [Table of Contents](#table-of-contents) — Links to each major section.
- [Why](#why) — The missing safe bridge between a selected row and the later writer.
- [Input](#input) — Upstream record, selection, and source-admission contracts.
- [Files (creates vs edits)](#files-creates-vs-edits) — Files created by this step.
- [Implementation](#implementation) — Safety checks, candidate binding, and final-recheck rules.
- [Tests](#tests) — Focused unit coverage for accepted and refused inputs.
- [Acceptance criteria](#acceptance-criteria) — Observable completion conditions.
- [References](#references) — Test-fixture guidance.
- [Applicable guardrails](#applicable-guardrails) — Scope boundaries that limit this module.
- [Deferred](#deferred) — Writer, receipt, and command work owned by later steps.

## Why

`plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` deliberately admits only an unanswered `open` row, while `plan_tool/roadmap_source_identity.py:canonical_projection` deliberately excludes all feedback from semantic baseline identity. The confirmed recovery needs separate, testable safety checks for the opposite state: one answered `awaiting-review` row that can be reopened only after the selected artifact is baseline-admitted and bound to the exact bytes later checked before publication. Those checks are not an evidence-unavailability category; confirmation is the authority for that judgment.

## Input

- **Step 1 record contract:** Step 1 supplies the landed `plan_tool/roadmap_artifacts.py:FeedbackRow` record shape and `FeedbackState` vocabulary. Read the landed names from that module; its code wins over this detail if they differ.

- **Receipt-safe selection:** `plan_tool/roadmap_escalation_selection.py:ReceiptSafeSelector` represents already-safe artifact and feedback identifiers. `plan_tool/roadmap_feedback.py:matching_feedback_rows` preserves duplicate matches for callers that must refuse ambiguity.

- **Ordinary receipt-target rule:** `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` already resolves an artifact target or exactly one live design-row target. Do not refactor that rule for this proof. Check viability by passing an in-memory copy of the selected artifact with only the selected row transformed to `open` and response-less to the existing function with its stable `"prose"` reason; retain only its accepted/refused result, not a second target policy.

- **Source admission:** `plan_tool/roadmap_escalation_selection.py:canonical_artifact_snapshot` binds parsed artifacts to source bytes, and `admit_versioned_artifact_source` applies the selected-stage baseline rule through `plan_tool/roadmap_source_identity.py:admit_baseline_backed_source`.

- **Baseline limit:** `plan_tool/roadmap_source_identity.py:canonical_projection` intentionally ignores feedback. The candidate therefore needs the full source digest as well as successful baseline admission; baseline identity alone cannot detect a changed selected or unselected feedback row.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_feedback_reopen.py` — Define the pure feedback-reopen safety, candidate, and candidate-currentness contract.
  - `tests/test_roadmap_feedback_reopen.py` — Cover the new contract with hand-built rows and admitted snapshots.

- **Existing files (edits only):** None.

## Implementation

- **Foundational logic: feedback reopen safety and source binding.** Create a focused module that turns an already receipt-safe selector and an already admitted artifact snapshot into either a bounded reopen candidate or a closed refusal result. The result says only that the tool may safely perform a confirmed reopen; it does not say why the operator confirmed it.

- **Keep row safety pure.** Give `plan_tool/roadmap_feedback_reopen.py` a public row-level predicate or verdict helper that accepts a hand-built `FeedbackRow` and performs no filesystem access. Accept only a row in `FeedbackState.AWAITING_REVIEW` with a nonblank response and no current step-1 feedback reopen record. This is a mutation safety condition, not a claim about unavailable evidence.

- **Treat blank as unsafe.** Check for both an absent response and whitespace-only response even if normal parsing rejects some of those shapes. The pure helper must be safe against manually constructed test inputs and later callers.

- **Require one selected row.** Build candidates only for a `ReceiptSafeSelector` whose artifact key matches the supplied stage context and whose feedback id finds exactly one row through `plan_tool/roadmap_feedback.py:matching_feedback_rows`. Refuse missing and duplicate matches rather than selecting the first.

- **Keep supplied stage context intact.** The confirmed operation passes its resolved stage into candidate construction and final currentness. Do not rediscover a global stage after accepting a caller-supplied stage table.

- **Require the ordinary receipt target now.** Before accepting a candidate, use `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback` unchanged against the one in-memory post-reopen copy described above. Accept only its `accepted` result. That preserves its artifact-target and live-design-row rules, including its missing, malformed, absent, and ambiguous-target refusals, without extracting or duplicating a target policy or storing the target as recovery history.

- **Keep ordinary receipt selection unchanged.** Do not widen or refactor `plan_tool/roadmap_escalation_selection.py:select_receipt_feedback`; its `open` and unanswered-row rule and existing target verdicts remain the ordinary receipt path. The new module consumes its outcome only to protect the confirmed recovery's fresh-receipt promise.

- **Bind candidates to canonical bytes.** Accept an admitted `CanonicalArtifactSnapshot` and retain its `source_digest` in a frozen candidate value, along with only the selected identifiers and the facts step 4 needs to recheck it. Refuse a baseline-equal `NoncanonicalArtifactSnapshot`: this writer must not normalize unrelated presentation while reopening feedback.

- **Reuse, do not copy, source admission.** Let step 4 call `canonical_artifact_snapshot` and `admit_versioned_artifact_source` at both capture and final recheck, then pass their admitted result to this module. Do not reproduce baseline parsing, journal handling, path resolution, or source-identity hashing in `plan_tool/roadmap_feedback_reopen.py`.

- **Make final currentness a conjunction.** Provide a pure candidate-currentness check that requires a fresh baseline-admitted canonical snapshot, the same exact `source_digest`, and the same still-safe selected row with a receipt-resolvable target. A changed selected row, target row, unselected feedback row, design row, prose body, or presentation byte must refuse; do not compare only baseline identity or a feedback-only snapshot.

- **Keep results redacted.** Candidate and refusal values may identify the selected artifact, feedback id, state, and source binding, but must not expose the response text, reviewer request, evidence bytes, evidence paths, or operator prose.

- **Do not create the transition in these APIs.** The pure safety and candidate APIs added in this step do not generate a nonce, clear a response, build the step-1 record, acquire a writer guard, write an artifact, or merge concurrent changes. Step 4 later extends the same module with the confirmed atomic transition and its final in-lock read.

- **Keep the one-use limit current-artifact-only.** An intact current step-1 record blocks this candidate. A later normal stage response clears the record as it creates a new response instance, so that new response can be evaluated independently. Do not add a history lookup, ledger, archive scan, or integrity store to detect a record that a raw editor removed or altered.

## Tests

### Tests for this step

- `tests/test_roadmap_feedback_reopen.py:test_safety_accepts_hand_built_awaiting_review_row_with_nonblank_response` — A safe row passes without filesystem setup; the test does not infer evidence availability.

- `tests/test_roadmap_feedback_reopen.py:test_safety_rejects_every_non_awaiting_review_state` — `open`, deferred, and closed lifecycle states cannot enter the recovery path.

- `tests/test_roadmap_feedback_reopen.py:test_safety_rejects_missing_blank_and_whitespace_only_response` — A response must contain non-whitespace text.

- `tests/test_roadmap_feedback_reopen.py:test_safety_rejects_row_with_current_reopen_record` — An intact step-1 record prevents reuse of this CLI recovery.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_requires_one_receipt_safe_selected_feedback_row` — Unsafe selectors, missing rows, and duplicate feedback ids refuse rather than selecting an arbitrary row.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_uses_ordinary_receipt_selection_for_target_viability` — Missing, malformed, absent, and ambiguous row targets refuse before candidate construction; an artifact target remains safe without a copied target resolver.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_builds_a_truthful_post_reopen_snapshot` — The in-memory post-reopen artifact carries the digest of its own canonical rendered bytes before the ordinary selector reads it.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_requires_canonical_baseline_admitted_snapshot` — Missing, invalid, pending, semantically changed, and presentation-only noncanonical sources cannot produce a writer candidate.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_allows_feedback_only_state_when_baseline_semantics_match` — The baseline rule still permits the intended feedback-only recovery shape.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_retains_exact_canonical_source_digest` — The candidate carries the SHA-256 digest of the exact source bytes supplied at capture.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_currentness_accepts_the_same_admitted_source` — A fresh canonical admission of unchanged bytes and the same safe row remains current.

- `tests/test_roadmap_feedback_reopen.py:test_candidate_currentness_refuses_every_visible_source_change` — Parameterized selected-feedback, target-row, unselected-feedback, design-row, prose, and presentation-byte changes all refuse before a write.

- `tests/test_roadmap_feedback_reopen.py:test_absent_current_record_does_not_trigger_history_lookup` — The bounded predicate judges only the current row and does not claim to detect a removed or altered record.

Green-before-done gate: every listed test and `uv run pytest tests/ -q -n auto` must pass.

## Acceptance criteria

- A hand-built row passes the pure row safety check only when it is `awaiting-review`, has a nonblank response, and has no current feedback reopen record; passing does not classify evidence availability.

- A candidate requires exactly one receipt-safe selected feedback row whose target can issue an ordinary receipt after the transition, and a canonical snapshot admitted against the selected-stage baseline.

- A candidate retains the exact source digest from its accepted canonical snapshot.

- A final recheck refuses any visible source-byte change, including a target-row, feedback-only, or presentation change that baseline identity intentionally ignores.

- The pure safety and candidate APIs perform no artifact write, lock acquisition, nonce generation, receipt work, or history lookup; step 4 owns the later operation in the same module.

- `tests/test_roadmap_feedback_reopen.py` and the full configured test command pass.

## References

- [pytest fixtures: explicit, modular, scalablehttps: — Structure isolated artifact, baseline, and stale-source fixtures without coupling this unit suite to the later CLI writer.

## Applicable guardrails

- **The plan’s “## Plan intent”, bounded recovery proof:** Limit the module to one current selected row and its source binding; do not create a general recovery, evidence-classification, or provenance abstraction.

- **The plan’s “## Step intent”, no-mutation safety checks:** Keep the row safety and candidate-currentness checks separate from all disk and publication behavior.

- **The plan’s “## Out of scope”, evidence and history limits:** Do not inspect legacy evidence, retain response provenance, or detect raw removal or alteration of the current record.

- **The plan’s “## Out of scope”, command and publication limits:** Do not add a CLI surface, atomic writer, journal, recovery flow, or external-writer coordination.

## Deferred

- Atomic mutation, final in-lock source read, nonce creation, and publication — Step 4 owns the confirmed transition and publication boundary.

- Receipt and impact currentness identity — Step 3 owns nonce-aware receipt construction and reader checks.

- CLI parsing, confirmation, help text, and end-to-end command coverage — Step 5 owns the exclusive operator surface.

- General evidence recovery, response provenance, and record-integrity history — Require a new seed under the plan’s scope fence.
