> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Show the current stack, and the stack rows a candidate adds, changes, or opens, at every candidate review print site next to the narrative evidence

<!-- plan-tool:detail-format-version: 1 -->

## Summary

- Every place that prints a candidate's narrative evidence also prints a stack callout beside it. The callout shows the candidate's stack, the stack rows it adds, changes, or opens, and each hosting and store `product` value the candidate carries.
- The callout comes from `plan_tool/roadmap_stack_summary.py`, which step 5 created for the first-run output and `INDEX.md`. This step adds a candidate-review function beside the step 5 producer, using the same row wording.
- Key decision: the callout is display only. It is a separate print call that never touches the narrative-evidence defect classes, `blocking_findings`, or the approval refusal. If it cannot be computed, it prints `stack: unavailable` with the reason and the command carries on.
- On green, `--propose-candidate`, `--review-candidate`, `--answer-question`, and `--decide-candidate` (approve, edit, reject) all print the callout next to the `narrative evidence:` block. Approval refuses and succeeds exactly as before.

## Table of Contents

- [Summary](#summary) — what the step does and the result on green
- [Why](#why) — the gap at the candidate review print sites
- [Input](#input) — what steps 3 and 5 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — the files touched
- [Implementation](#implementation) — producer function, print sites, and what must not vary
- [Tests](#tests) — the cases that pin the behavior
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — work that belongs elsewhere

## Why

- A candidate review is where a reviewer accepts or refuses a roadmap change. Step 3 lets a candidate add or replace stack rows, but the review output shows only the narrative evidence and the predecessor diff. A stack choice or an open stack question can pass review unseen.
- The `product` values on hosting and store rows sit beside the stack choice only for the reviewer to read; the callout never flags a difference and defines no comparison. Today the reviewer has to open the artifacts to see them.
- Narrative evidence is a defect report with blocking findings. Putting stack content in it would turn a display need into a defect class and a possible approval block, which the plan forbids.

## Input

- **Step 3 output.** `stack` rows are legal candidate delta targets (add, replace, open), so a candidate's `02-constraints.md` can differ from its predecessor's in the `stack` collection.
- **Step 5 output.** `plan_tool/roadmap_stack_summary.py` is the single producer of stack summary lines and returns plain text lines. It already distinguishes "stack not recorded" (`None`) from an empty or populated collection, and groups open and pending concerns.
- **Names come from the landed code.** `plan_tool/roadmap_stack_summary.py` is not on disk when this file is written. Read the landed function names, row field names, and the pending-decision source, and use them. Landed names win over every name used here.
- **Candidate content shape.** `plan_tool/cli/roadmap_cmd.py:_compute_narrative_evidence` shows how a candidate's four artifact bytes are paired with `VERSION_ARTIFACT_KEYS` and how the predecessor is loaded with `load_resolved_stored_version`. The callout needs the same two inputs: the candidate's content and the predecessor.

## Files (creates vs edits)

- **New files:** none. `plan_tool/roadmap_stack_summary.py` and `tests/test_roadmap_stack_summary.py` already exist from step 5.
- **Existing files (edits only):**
  - `plan_tool/roadmap_stack_summary.py`: add a candidate-review function that takes the candidate's parsed constraints, the predecessor's parsed constraints, and returns lines. Reuse the step 5 row-formatting code.
  - `plan_tool/cli/roadmap_cmd.py`: add one never-raising print helper beside `_print_narrative_evidence_or_unavailable`, and call it at each narrative-evidence print site.
  - `tests/test_roadmap_stack_summary.py`: cases for the new function.
  - `tests/cli/test_roadmap_cmd.py`: cases for every print site and for the approval-unchanged guarantee.
  - `tests/test_roadmap_candidate_review.py`: a case that the review library's approval refusal is unchanged by stack content.

## Implementation

**Producer function.** Add one function to `plan_tool/roadmap_stack_summary.py`, for example `candidate_stack_summary_lines`. Inputs are the candidate's `ConstraintsArtifact` and the predecessor's. Output is plain text lines.
- **Current stack.** List every stack row of the candidate, each beside the `product` values of the hosting and store rows it was reviewed with, using the step 5 row wording. A candidate with no `stack` collection prints the same "stack not recorded" line step 5 uses.
- **Delta.** List rows added, changed, and newly opened, compared by row id against the predecessor. A row that was open and is now chosen counts as changed. A predecessor with no collection makes every candidate row an add.
- **Products.** Print hosting and store `product` values verbatim, with an explicit "no product recorded" marker for `None`. The function lists them and does not compare a stack choice to a product, or judge either.
- Rejected alternative: a second formatting path for the candidate view. Two wordings for the same row would drift from the step 5 output.

**Print helper.** In `plan_tool/cli/roadmap_cmd.py`, add one helper in the style of `_print_narrative_evidence_or_unavailable`, for example `_print_candidate_stack_callout`.
- It takes the same `plans_dir`, `slug`, `initial`, and `content` arguments, loads the predecessor the way `_compute_narrative_evidence` does, parses both constraints artifacts, and prints the lines.
- It catches `ValueError`, `OSError`, and `RoadmapArtifactError`, prints `stack: unavailable` plus `reason: ...`, and returns. It must not return a failure for callers to turn into a return code.

**Print sites.** Call the helper next to each narrative-evidence print. The sites are:
- the proposal path (`--propose-candidate`), inside the `show_evidence` closure passed as `after_diff` to `_render_candidate_proposal_result`;
- the review path (`--review-candidate`), after the evidence print that follows `_render_candidate_review_result`;
- the answer path (`--answer-question`), inside its `show_evidence` closure, using `result.replacement.content` as the other answer-path call does;
- the structural decision path (`--decide-candidate`): the approve branch, which calls `_render_narrative_evidence` directly, and the edit and reject branch, which calls `_print_narrative_evidence_or_unavailable`.
- Rule: grep `_print_narrative_evidence_or_unavailable` and `_render_narrative_evidence` in `plan_tool/cli/roadmap_cmd.py` and give every call site a callout call, or state in the commit why a site stays without one. Do not leave a site by accident.
- Placement: print the callout directly after the narrative-evidence block, so the reviewer reads both together.

**Constraints that are not free to vary.**
- **No coupling to evidence.** The callout must not call into `plan_tool/roadmap_candidate_narrative.py`, add a field to `CandidateNarrativeEvidence`, or add a finding kind. Narrative evidence stays exactly as it is.
- **Approval untouched.** The approve branch must not read the callout result. A callout failure in that branch must not change the return code, the digest, or the refusal path. Print the callout outside the `try` that maps evidence failure to `_RC_USAGE`.
- **No stored output.** Nothing is written to disk; the callout is recomputed on each print.
- **No judging.** No wording such as "recommended", "mismatch", or "conflicts". The lines state what is there.

## Tests

Producer cases in `tests/test_roadmap_stack_summary.py`:
- `test_candidate_lines_list_added_changed_and_opened_stack_rows` — a candidate against a predecessor reports one add, one change, and one open-to-chosen change, each by row id.
- `test_candidate_without_stack_collection_prints_stack_not_recorded` — a `None` stack prints the step 5 wording, not an empty list.
- `test_predecessor_without_stack_makes_every_candidate_row_an_add` — the stack-less predecessor case.
- `test_hosting_and_store_products_are_listed_verbatim_with_explicit_none_marker` — a `None` product prints "no product recorded".
- `test_summary_displays_and_never_compares_a_choice_to_a_product` — a stack choice that differs from a store `product` yields identical lines to one that matches, apart from the values themselves.

CLI cases in `tests/cli/test_roadmap_cmd.py`:
- `test_every_narrative_evidence_print_site_also_prints_the_stack_callout` — parametrized over proposal, review, answer, structural approve, and edit/reject; each output contains the callout after the `narrative evidence:` line.
- `test_stack_callout_failure_prints_unavailable_and_does_not_change_the_return_code` — a corrupt stored constraints artifact makes the callout say `unavailable` while the command's code matches the no-callout baseline.
- `test_structural_approve_return_code_and_digest_are_unchanged_by_the_callout` — the unconfirmed and confirmed approve outputs keep their digest and codes with a stack-bearing candidate.
- `test_callout_never_appears_in_narrative_evidence_counts` — a candidate with stack changes still prints `narrative evidence: none`.

Library case in `tests/test_roadmap_candidate_review.py`:
- `test_stack_content_adds_no_approval_refusal_or_narrative_finding` — approval of a candidate that adds and opens stack rows is refused or allowed exactly as the same candidate without stack rows.

**Green-before-done gate.** Every test above must be green, and the existing narrative-evidence and structural-approval tests must stay green without edits to their assertions, before this step is finished.

## Acceptance criteria

- Each candidate review print site prints a stack callout after its `narrative evidence:` block, and a grep of the two evidence print functions shows no call site without one (or a stated reason).
- The callout lists the candidate's stack rows, the added, changed, and opened rows against the predecessor, and the hosting and store `product` values.
- A candidate with no `stack` collection prints "stack not recorded".
- A callout failure prints `stack: unavailable` with a reason and changes no return code.
- `rg 'roadmap_candidate_narrative' plan_tool/roadmap_stack_summary.py` returns nothing, and `plan_tool/roadmap_candidate_narrative.py` has no diff.
- The approve path's digest, refusal, and return codes are the same as before the step.

## Applicable guardrails

- The plan's "## Out of scope", the narrative-evidence and approval-block item: this step may not add a defect class, a finding kind, or any refusal keyed on stack content. The callout sits beside the evidence and is separate from it.
- The plan's "## Out of scope", the judging item: the summary lists values and does not decide whether a choice is good or matches a `product`.
- The plan's "## Out of scope", the item on rewriting existing accepted versions: the callout only reads stored versions.
- The plan's "## Out of scope", the item on stack concerns beyond the plan's named set: the callout shows whatever rows the artifact holds and does not add concern logic.

## Deferred

- Integration's HTML review aid — follows this work separately in Integration, per the plan's "## Out of scope".
- Any comparison or warning between a stack choice and a `product` value — the plan forbids judging; this step only lists both.
- Consolidating the several narrative-evidence print sites into one helper — a separate refactor with its own call-site sweep; this step adds a call at each site.
