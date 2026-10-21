# Step 4 — Refuse approval of a candidate whose live prose names a removed row

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes both approval paths, `seal_review` and the `approve` branch of `decide_structural_candidate`, recompute the candidate's narrative evidence from its stored bytes. Each path then refuses only the defect classes step 1 marked blocking. The work happens in `plan_tool/roadmap_candidate_review.py` through one private helper that both paths call. That helper turns step 3's evidence into one `CandidateReviewError`, which the existing `except` clauses already turn into a `refused` result with return code 0. The refusal names each defect and its operator exit. Non-blocking evidence never refuses. The answer path (`answer_candidate_question`) is untouched and inherits the check because it calls `seal_review`. On green, a candidate that still names a removed row cannot be sealed, whatever its age, and every other approval, replay, and refusal behavior is unchanged.

## Table of Contents

- [Why](#why) — what approval lets through today
- [Input](#input) — what steps 1 to 3 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files
- [Implementation](#implementation) — placement, helper shape, refusal text, fixed constraints
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what other steps and entries own

## Why

`seal_review` and `decide_structural_candidate` (approve) validate identity, lineage, digests, and ledger state. Neither looks at what the candidate's prose says. A reviewer can therefore approve a candidate whose body still refers to a design row the candidate removed, with no warning. Steps 2 and 3 make that defect computable from the candidate alone. This step is where it stops approval.

## Input

- **Step 1** owns the contract in `ROADMAP_FORMAT.md` § "Narrative review evidence". It fixes which class blocks, the operator exit for each blocking class, and the rule that evidence is recomputed and never stored. Take the exit wording from that section.
- **Step 3** owns `plan_tool/roadmap_candidate_narrative.py`. It supplies the pure evidence function and the stored-candidate adapter. Each finding names its artifact, row or span, class, and correction path.
- **Landed code, confirmed at HEAD:**
  - Both `roadmap_candidate_run.StoredCandidateProposal` and `StoredCandidateReviewReplacement` carry `.record` and `.content`. `.content` is a `RoadmapVersionContent` holding the artifact bytes. That is the shape the step 3 adapter takes.
  - `CandidateReviewError` is caught by both approval paths and becomes `_result("refused", str(exc), 0)`.
- **Limits on checking this step:**
  - Steps 1 to 3 have no code at HEAD when this detail is written. Read the landed names, the blocking classification, and the exit wording off HEAD. Those names win over any name in this file.
  - The IPPT-18 correction operation is not landed. Name it only by its ticket and plan (`docs/implementation-plans/2-candidate-prose-correction.md`). Do not cite a symbol of it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_candidate_review.py`
    - Add one private helper that computes the evidence and raises `CandidateReviewError` for blocking defects.
    - Call the helper from `seal_review` and from the `approve` branch of `decide_structural_candidate`.
    - Import the step 3 module. Do not import `plan_tool/roadmap_gates.py` directly for this.
  - `tests/test_roadmap_candidate_review.py`
    - Add cases for the two paths, the answer path, the batch seal, and the carve-outs below.

## Implementation

**What must hold**

- **One helper, two callers.** The helper takes the stored candidate (`.record` and `.content`) and `plans_dir`/`slug` if step 3's adapter needs them to load the predecessor. It returns normally when no blocking defect exists. Otherwise it raises one `CandidateReviewError` carrying the full refusal text.
- **Recompute every time.** Call step 3's function on the candidate being approved. Do not read or write any stored evidence, and do not add a field to `CandidateReviewSeal` or any stored record. Seal bytes and seal identity must not change for any candidate.
- **Blocking set comes from step 3's output.** Use step 3's own blocking marker or the class set step 1 named. Do not hardcode the class names here. A non-blocking item (the ambiguous reference) must produce no refusal and no extra output on the approval result.
- **Refusal text.** One message must:
  - name every blocking defect with its artifact, row id, and class
  - give the operator exit once per blocking class, in step 1's wording
  - read on its own, with no position or line number

  Report all blocking defects in one refusal, not the first only.
- **Placement in `seal_review`.** Call the helper after the replacement matches `replacement_candidate_version_id` and `_require_review_required_predecessor_is_current` has run. Place it before the existing-seal lookup (`review_seal_path(...).exists()`) or after it:
  - Recommended: **after** the existing-seal branch. A lineage already sealed returns its stored seal exactly as today, so the existing create-only behavior and idempotent replay stay unchanged. Pin that choice with a test.
  - Either way, the call sits before `_publish_batch_seal` and before `_publish_new_record`. One call therefore covers both the batch and non-batch seals.
- **Placement in `decide_structural_candidate`.** Call the helper inside the writer guard, after the digest comparison (`view.digest != confirm_digest`) and after the existing-seal branch. A wrong digest keeps reporting `_APPROVAL_DIGEST_MISMATCH` first. The missing-digest, edit, and reject routes stay untouched.
- **Which bytes.** Candidate versions are immutable, so the check needs no re-check inside the `before_replace` hook. Do not add a second call there.
- **Answer path.** `answer_candidate_question` calls `seal_review` and already returns any non-`stored` seal result as is. Leave it unchanged. A refused seal leaves the answer and replacement stored and unsealed, exactly as any other seal refusal does today.
- **Old candidates.** The check runs on whatever bytes are stored. No version or creation-time test is allowed. A candidate created before this ships is checked the same way as a new one.
- **Rejected alternative:** put the check in `_new_seal` or `_new_structural_approval_seal`. Both are pure identity builders, and the existing test `test_structural_approval_seal_has_one_construction_site` pins the second as a single construction site. A refusal there would also fire on stored-seal replay.

## Tests

All in `tests/test_roadmap_candidate_review.py`. Build the removed-id candidate from the same fixture helpers the neighboring seal tests use. Reuse the step 2 fixture only where a case needs the real Decisions paragraph.

- `test_seal_review_refuses_a_replacement_whose_live_prose_names_a_removed_row` — outcome `refused`, return code 0, no seal file written.
- `test_structural_approve_refuses_a_candidate_whose_live_prose_names_a_removed_row` — refused, no seal written, even with the matching digest.
- `test_refusal_names_each_blocking_defect_and_its_operator_exit` — two defects in two artifacts both appear, and each blocking class's exit appears once.
- `test_ambiguous_reference_is_never_a_refusal` — a candidate with only the non-blocking class seals normally on both paths, and the result carries no new fields.
- `test_approval_without_removed_ids_is_unchanged` — a clean candidate seals with the same seal identity as before (pin one known seal id).
- `test_a_candidate_stored_before_the_check_shipped_is_checked_the_same_way` — a stored candidate built with no evidence record is refused when defective and sealed when clean.
- `test_wrong_digest_still_reports_the_digest_mismatch_before_narrative_evidence` — ordering invariant: the digest refusal wins.
- `test_already_sealed_lineage_still_returns_the_stored_seal` — deliberate: the existing-seal replay is not re-checked, and it matches the sibling test that re-approval still needs the digest.
- `test_batch_seal_is_refused_through_the_same_check` — the `batch_receipt` path refuses and publishes nothing.
- `test_answer_path_returns_the_seal_refusal_and_leaves_replacement_stored` — `answer_candidate_question` returns `refused`, the replacement stays stored, and no seal exists.
- `test_narrative_evidence_is_not_stored_and_seal_bytes_gain_no_field` — the seal's rendered bytes contain no evidence, and no extra file appears under the review directories.
- `test_reject_and_edit_routes_do_not_run_the_narrative_check` — a defective candidate can still be rejected and edited.

### Tests for this step

Run the whole file, plus `tests/test_roadmap_candidate_narrative.py` and `tests/test_roadmap_gates.py`. Every case above must be green before the step is finished. Check each new refusal case by mutation: remove the helper call from one path and confirm that path's case goes red while the other stays green. The existing seal tests in the file are the guard that unchanged behavior stays unchanged. Do not rewrite them. If one goes red, the check is firing on a clean candidate.

## Acceptance criteria

- `seal_review` returns `refused` with return code 0 and writes no seal for a replacement whose live prose still names a removed row of a blocking class.
- `decide_structural_candidate(..., "approve", ...)` returns `refused` and writes no seal for the same kind of candidate, even with the correct `confirm_digest`.
- The refusal text names each blocking defect and each blocking class's operator exit.
- An approval with only non-blocking evidence succeeds and its seal identity is the same as before this step.
- `CandidateReviewSeal`, the seal render, and the stored review records gain no field and no new file.
- `rg 'roadmap_candidate_narrative' plan_tool/roadmap_candidate_review.py` shows the import and the helper's calls only, and the helper has exactly two call sites.
- `answer_candidate_question`, `reject_candidate_review`, `_edit_structural_candidate`, `_new_seal`, and `_new_structural_approval_seal` have no diff.

## Applicable guardrails

- The plan's "## Scope guardrails" bounds refusal to the defects step 1 selected as blocking. This step adds no other refusal, no stored evidence, no reviewer disposition, and no semantic judgment.
- The plan's "## Scope guardrails", "Not allowed" list bars keyword matching and any exit-code flip keyed on a semantic finding. The only gate here is the deterministic check, and `refused` keeps its return code 0.
- The plan's "## Out of scope" leaves the correction operation (IPPT-18) to its own plan. The refusal only names the exit.
- The plan's "## Out of scope", feedback eligibility and authority limits, binds the helper: it must not touch feedback state or the ledger.

## Deferred

- The correction operation that clears a blocking defect — IPPT-18, `docs/implementation-plans/2-candidate-prose-correction.md`.
- Showing evidence to the reviewer before approval in the candidate display — step 5.
- Model-judged narrative review, stored evidence, and reviewer dispositions — BACKLOG #435.
- Response-basis checking — BACKLOG #437.
- Re-checking an already-sealed lineage on replay — left out on purpose, because the plan keeps create-only seal publishing unchanged.
