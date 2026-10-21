> **Withdrawn 2026-09-22** — Superseded 2026-09-22: feedback moves to a roadmap-scoped mutable ledger; artifact versions retain no embedded mutable feedback.
> Preserved here for history; do not edit.

# Step 4 — Block enrolled decision settlement only on an unpromoted candidate for the current accepted-head generation

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Update `plan_tool/roadmap_decision_settlement_enrolled.py` so settlement blocks only when the current accepted head has a stored, unpromoted feedback candidate. Keep the existing accepted-head generation comparison, but distinguish an admission that has produced a candidate from one that has not. Update `tests/test_roadmap_decision_settlement_enrolled.py` to cover current-generation blocking, failed-proposal non-blocking, stale-generation non-blocking, and the existing post-receipt precedence rule. On green, a failed or incomplete candidate proposal cannot strand decision settlement, while a stored candidate for the current head still prevents competing publication.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the narrowed settlement block.
- [Table of Contents](#table-of-contents) — Links to this detail’s sections.
- [Why](#why) — Why admission existence is broader than a live candidate.
- [Input](#input) — Candidate-admission and accepted-head contracts this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The two scoped file edits.
- [Implementation](#implementation) — Required predicate, ordering, and unchanged authority boundaries.
- [Tests](#tests) — Focused coverage for settlement eligibility and rechecks.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Lifecycle and version contracts to consult.
- [Applicable guardrails](#applicable-guardrails) — Plan boundaries that constrain this change.
- [Deferred](#deferred) — Adjacent lifecycle work outside this step.

## Why

`plan_tool/roadmap_decision_settlement_enrolled.py:_admission_blocks_settlement()` currently treats any admission whose `predecessor_version_id` matches the accepted head as a competing lineage, including an admission left after a rejected model response with no stored candidate. That blocks a confirmed decision even though no candidate exists to promote. Step 3 makes admissions generation-scoped; this step narrows the settlement block to the actual competing publication case: a stored candidate rooted at the current accepted head.

## Input

- **Step 3 admission outcome:** Consume the generation-scoped `CandidateProposalAdmission` stored by `plan_tool/roadmap_candidate_run.py:load_candidate_admission()`. This step relies on its `predecessor_version_id` and optional `candidate_version_id`; it does not redefine admission persistence or candidate storage.

- **Accepted-head selector:** Continue to read `AcceptedRoadmapHead` through `plan_tool/roadmap_versions.py:load_accepted_head()`. The accepted head remains the sole source for determining whether an admitted candidate belongs to the current generation.

- **Settlement recheck:** Preserve the two calls to `_admission_blocks_settlement()` in `plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement()`: once before settlement construction and once after receipt publication, before `decision_settlement_candidate_is_current()`.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `plan_tool/roadmap_decision_settlement_enrolled.py` — Narrow `_admission_blocks_settlement()` and its contract text to identify only a stored candidate for the current accepted-head generation.
  - `tests/test_roadmap_decision_settlement_enrolled.py` — Replace admission-only blocking expectations with candidate-aware coverage and retain the post-receipt ordering check.

## Implementation

- **Block only a real competing candidate.** Update `plan_tool/roadmap_decision_settlement_enrolled.py:_admission_blocks_settlement()` so it returns true only when all of these facts hold:
  - `load_candidate_admission()` returns an admission.
  - The admission has a non-`None` `candidate_version_id`, meaning the candidate runner has stored a candidate.
  - `load_accepted_head()` returns a head whose `version_id` equals the admission’s `predecessor_version_id`.

- **Keep the accepted-head comparison.** Do not use admission age, response state, or file timestamps to decide settlement eligibility. A stored candidate from an older predecessor does not block the current accepted-head generation.

- **Treat an unmaterialized admission as non-blocking.** A rejected response or other proposal attempt that leaves `CandidateProposalAdmission.candidate_version_id` unset must allow the normal settlement path to continue. Do not add an abandonment flag, cleanup route, or new admission state.

- **Preserve settlement ordering.** Keep the preflight block before `build_decision_settlement_candidate()` and retain the post-receipt block before `decision_settlement_candidate_is_current()` in `run_enrolled_decision_settlement()`. This preserves the existing refusal precedence when both a candidate appears and the source changes during receipt publication.

- **Reuse existing owners.** Keep `plan_tool/roadmap_candidate_run.py:CandidateProposalAdmission` as the source of candidate presence and `plan_tool/roadmap_versions.py:load_accepted_head()` as the canonical selector. This step must not add a second candidate-status check, alter promotion, or write the accepted head directly.

## Tests

### Tests for this step

- `test_unmaterialized_admission_on_the_current_head_does_not_block_settlement` — A rejected proposal that leaves `candidate_version_id` unset allows settlement and produces the normal settlement result.

- `test_stored_candidate_on_the_current_head_refuses_before_any_receipt` — A stored candidate rooted at the current accepted head returns `unpromoted-candidate-lineage`, does not build settlement content, and creates no receipt.

- `test_stored_candidate_refusal_has_no_age_limit` — A current-generation stored candidate still blocks after its admission file timestamp is made old.

- `test_stored_candidate_from_an_old_generation_does_not_block_settlement` — Moving the accepted head past the admission predecessor permits settlement while leaving the stored admission unchanged.

- `test_runner_offers_no_way_to_abandon_or_override_a_stored_current_candidate` — The public `run_enrolled_decision_settlement()` signature adds no bypass, and a current stored candidate remains blocking.

- `test_post_receipt_recheck_reports_unpromoted_lineage_over_source_changed_when_both_trip` — The post-receipt candidate check still runs before the source-currency check and returns the established refusal.

Every listed test must be green before this step is complete.

## Acceptance criteria

- `_admission_blocks_settlement()` returns false when no admission exists.

- `_admission_blocks_settlement()` returns false when a current-generation admission has no `candidate_version_id`.

- `_admission_blocks_settlement()` returns true only when a stored candidate’s `predecessor_version_id` matches the current accepted head.

- A stored candidate from an older accepted-head generation does not block decision settlement.

- A current stored candidate returns `unpromoted-candidate-lineage` before receipt publication and before settlement construction.

- The post-receipt recheck preserves `unpromoted-candidate-lineage` precedence over `source-changed`.

- `tests/test_roadmap_decision_settlement_enrolled.py` passes.

## References

- [ROADMAP_FORMAT.md — Read the feedback lifecycle, immutable-version, candidate, and accepted-head contracts.](../../../../ROADMAP_FORMAT.md)

- [DATA_CONTRACT.md — Read the persisted candidate, review, version, and publication record contracts.](../../../../DATA_CONTRACT.md)

- [docs/how-to/roadmap.md — Read the operator-facing enrollment, candidate review, promotion, and settlement workflow.](../../../how-to/roadmap.md)

- [plan_tool/roadmap_candidate_run.py — Read CandidateProposalAdmission storage and candidate materialization ownership.](../../../../plan_tool/roadmap_candidate_run.py)

- [plan_tool/roadmap_version_promotion.py — Read exact-seal promotion and current-predecessor verification.](../../../../plan_tool/roadmap_version_promotion.py)

- [plan_tool/roadmap_revision_publish.py — Read the shared writer lease, publication journal, and recovery boundary.](../../../../plan_tool/roadmap_revision_publish.py)

## Applicable guardrails

- **The plan’s “Plan intent” — one accepted-head revision:** This step may block settlement only for a live competing candidate on the current canonical generation; it must not make admission creation or a failed proposal permanently consuming.

- **The plan’s “Scope guardrails” — accepted-head authority:** `plan_tool/roadmap_decision_settlement_enrolled.py` must continue to use the accepted head as the canonical selector and must not treat candidate storage as canonical content.

- **The plan’s “Scope guardrails” — exact predecessor binding:** The block must remain tied to the admission’s recorded predecessor and the current accepted-head identity; it must not infer eligibility from mutable top-level artifacts.

- **The plan’s “Out of scope” — no new review or lifecycle protocol:** Do not add candidate abandonment, new feedback states, approval rules, promotion routes, or a second writer authority.

## Deferred

- Candidate-admission replacement and batch construction — Step 3 owns the generation-scoped admission lifecycle; this step only consumes its resulting predecessor and candidate identity.

- Promotion and review-seal validation — `plan_tool/roadmap_version_promotion.py` remains the owner of making a candidate canonical and is outside this step’s declared files.
