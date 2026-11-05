> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Print the computed narrative evidence on the roadmap candidate CLI surfaces

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes `plan-tool roadmap` print each candidate's narrative evidence before the operator decides. Each finding shows its artifact, row or span, defect class, and correction path. The work is in `plan_tool/cli/roadmap_cmd.py`: one render helper, called from the candidate surfaces that already print a candidate. The helper calls step 3's pure function over the stored candidate, so the CLI and step 4's refusal read the same finding list. Output is display only, and exit codes keep their current meanings. `docs/cli/roadmap.md` is regenerated from the parser so any edited option help stays in sync. On green, a reviewer who runs the propose, review, answer, or decide surfaces sees a candidate's unresolved narrative defects, or an explicit "none", before any approval.

## Table of Contents

- [Why](#why) — what the reviewer cannot see today
- [Input](#input) — what steps 2 to 4 hand this step, and the limits on checking it
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files
- [Implementation](#implementation) — surfaces, placement, failure behavior, fixed constraints
- [Tests](#tests) — cases and the green gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what other steps and entries own

## Why

The candidate surfaces in `plan_tool/cli/roadmap_cmd.py` show the predecessor diff, stored route, typed operations, and (for structural candidates) the whole stack. None of them shows whether the candidate's live prose still names a row it removed. Step 4 refuses a blocking defect at approval, but a refusal alone gives the operator no list to act on. The plan's outcome is that the reviewer sees the defects before approving, so the CLI has to print them where the candidate is already being read.

## Input

- **Step 3** owns `plan_tool/roadmap_candidate_narrative.py`: the pure evidence function and the stored-candidate adapter. Each finding carries artifact, row or span, class, and correction path. Read the landed names off HEAD; they win over any name in this file. At the time this detail is written the module is not at HEAD.
- **Step 1** owns the wording in `ROADMAP_FORMAT.md` § "Narrative review evidence": which class blocks and the operator exit for each blocking class. The CLI prints the correction path that step 3 supplies and does not write its own wording.
- **Step 4** owns the refusal. Both approval paths already refuse a blocking defect, and the CLI does not duplicate that check.
- **Landed shapes the CLI already handles:** `roadmap_candidate_run.StoredCandidateProposal` (from `load_stored_candidate_proposal`), `CandidateStackView.hops` (each hop is a `StoredCandidateProposal`), and the replacement returned by the answer path (`CandidateReviewResult.replacement`).
- **Limits on checking:**
  - Whether the answer path's `replacement` object carries `.content` in the shape step 3's adapter takes is not confirmed here. Check at HEAD. `plan_tool/roadmap_candidate_review.py:load_stored_candidate_review_replacement` is the loader to use if it does not.
  - The IPPT-18 correction operation is not landed. Name it only as `docs/implementation-plans/2-candidate-prose-correction.md`.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/cli/roadmap_cmd.py`
    - Add one private render helper for narrative evidence.
    - Call it from the candidate surfaces listed under Implementation.
    - Add a short pointer to the evidence in the help text of the options whose output gains it.
  - `tests/cli/test_roadmap_cmd.py`
    - Add output cases for each surface, a "none found" case, a failure case, and a carve-out case.
  - `docs/cli/roadmap.md`
    - Regenerate. The edit is whatever the help-text change produces.

## Implementation

**What must hold**

- **One helper.** `_render_narrative_evidence` (name is a suggestion) takes the stored candidate and prints a block that starts with a fixed header line. For each finding it prints:
  - the artifact
  - the row or span
  - the defect class
  - the correction path
- **Same findings as step 4.** The helper must call step 3's function and adapter. It must not import `plan_tool/roadmap_gates.py` and must not re-check anything.
- **Explicit empty case.** When no finding exists, print the header with `none`. Absence of the block never means "no defects".
- **Both classes print.** The non-blocking ambiguous reference prints too, marked with whatever blocking marker step 3's result carries. Use that marker and do not recompute blocking in the CLI.
- **Recomputed each time.** Nothing is written, cached, or stored.
- **Own block.** The block has its own header, so a test can find it by key and not by matching words in other lines.

**Where it prints**

- **`--propose-candidate`:** after the stored candidate and its predecessor diff, in `_render_candidate_proposal_result`, or beside it in `_cmd_roadmap_propose_candidate`. The proposal is already stored when this runs.
- **`--review-candidate`:** after the candidate and predecessor lines, next to the question output.
- **`--answer-question`:** for the replacement, next to the replacement id and its predecessor diff.
- **`--decide-candidate`, all three decisions:**
  - Print it after `_render_structural_candidate_stack` and before the decision runs.
  - On approve, print it before `_render_unconfirmed_structural_approval` and before the stack digest line. An operator who only reads the first invocation still sees it.
  - For a stack, show evidence for the top candidate only. Narrative defects live in the candidate's own artifacts, and the top candidate holds the final text. If step 3's function takes the whole stack, use that and say so in a comment.
- **Not printed on:** `--reject-candidate`, `--discard-candidate`, `--promote-review-seal`. They show no candidate content today. Keep that.

**Failure behavior (recommended; the implementer owns the exact lines)**

- **Approve, first or confirmed invocation:** if the evidence cannot be computed, print the error and return `_RC_USAGE` before the digest line and before any write. Step 4's refusal needs the same computation, so approval could not proceed anyway.
- **Edit and reject:** if the evidence cannot be computed, print `narrative evidence: unavailable` plus the reason, then continue. These decisions must not be trapped by a display failure.
- **Propose, review, answer:** the record is already stored. Follow the existing `stack_error` pattern in `_cmd_roadmap_propose_candidate`: report the error and return `_RC_INCOMPLETE`.
- **Rejected alternative:** hiding the failure and printing nothing. Silence reads as "no defects".

**Fixed constraints**

- **No exit-code change from findings.** A candidate with findings exits as it does today. Only an evidence failure on the paths above changes a code, as listed. This follows the repo's rule that subcommands exit non-zero only on failure to complete.
- **Do not change `candidate_stack_route`, `build_candidate_stack_view`, or the stack digest.** Evidence is not part of the digest.
- **Keep existing lines.** Existing output lines stay as they are, including those pinned by `test_stack_printout_keeps_every_line_the_existing_disclosure_prints_for_the_top_candidate` and `test_proposal_output_keeps_todays_output_when_the_stack_has_no_structural_hop`. The new block is added, not folded into them.
- **Docs regeneration.** Run `python -m plan_tool.cli_reference --write` after any help-text edit. The file is generated, so do not hand-edit it. If no help string changes, the regenerated file is unchanged and the step records that. Do not invent a help edit just to move the file.

## Tests

All in `tests/cli/test_roadmap_cmd.py`. Most cases stub step 3's function, as the existing stack-printout cases stub the view builder.

- `test_propose_candidate_output_prints_narrative_evidence_with_artifact_span_class_and_correction_path` — each finding field appears in the block.
- `test_review_candidate_output_prints_narrative_evidence_block` — the review surface carries the block.
- `test_answer_output_prints_narrative_evidence_for_the_replacement_not_the_edited_candidate` — evidence is for the stored replacement, matching how the replacement's stack view is built.
- `test_decide_candidate_approve_prints_evidence_before_the_stack_digest_line` — first invocation shows the block ahead of the confirmation prompt.
- `test_decide_candidate_edit_and_reject_print_evidence_before_the_decision_runs` — ordering for the two non-approve choices, via call order.
- `test_no_findings_prints_the_block_header_with_none_and_not_silence` — the empty case is explicit, and a stubbed empty result differs from "block missing".
- `test_ambiguous_reference_prints_as_non_blocking_evidence_and_does_not_change_the_exit_code` — the non-blocking class shows, and the exit code matches the no-evidence run.
- `test_evidence_failure_on_approve_returns_usage_before_the_digest_line_and_writes_nothing` — the approve failure path.
- `test_evidence_failure_on_reject_prints_unavailable_and_still_releases_the_candidate` — the carve-out: a display failure does not trap reject. It pins that this is deliberate.
- `test_standalone_reject_discard_and_promote_print_no_narrative_evidence` — the carve-out for surfaces that print no candidate content.
- `test_evidence_is_not_part_of_the_stack_digest` — the same stack gives the same digest whether or not evidence has findings.
- `test_narrative_evidence_over_a_real_stored_candidate_matches_the_pure_function` — one seam case, only if the real-stack helpers used by `test_stack_printout_from_a_real_stack_prints_every_hop_and_never_prints_the_digest` can carry a removal record cheaply. It shows the CLI and the stored-candidate adapter agree. If building it is not cheap, record that in the handoff and keep the stubbed cases.

`tests/cli/test_cli_reference.py` already guards `docs/cli/roadmap.md` against the parser. It is not edited.

### Tests for this step

The cases above are the roster. Every one must be green before this step is finished, plus the existing `tests/cli/test_roadmap_cmd.py` and `tests/cli/test_cli_reference.py` suites. A rewritten existing test is expected only if an output line moved; none should.

## Acceptance criteria

- Each of the four surfaces (propose, review, answer, decide) prints the evidence block, before the decision for decide.
- A candidate with no findings prints the header with `none`.
- Each finding line names artifact, row or span, class, and correction path.
- The ambiguous reference prints and does not change any exit code.
- On approve, an evidence failure returns `_RC_USAGE` with no digest line and no write.
- On edit and reject, an evidence failure prints `unavailable` and the decision proceeds.
- `--reject-candidate`, `--discard-candidate`, and `--promote-review-seal` print no evidence.
- The stack digest is unchanged by evidence.
- `rg 'roadmap_gates' plan_tool/cli/roadmap_cmd.py` shows no new import for this step.
- `python -m plan_tool.cli_reference --write` leaves no further diff, and `tests/cli/test_cli_reference.py` passes.

## Applicable guardrails

- **The plan's "## Scope guardrails" (no semantic review, no stored evidence):** this step only prints evidence it recomputes. It writes no record and takes no reviewer disposition.
- **The plan's "## Scope guardrails" (no exit-code flip on a semantic finding):** the CLI adds no refusal and no exit-code change keyed on findings. Refusal belongs to step 4.
- **The plan's "## Out of scope" (the remedy):** the correction path shown is step 3's text. This step does not run or offer a correction, and the IPPT-18 operation is not called.
- **The plan's "## Out of scope" (response basis, #437):** no response-basis notes appear in this output.
- **The plan's "## Out of scope" (feedback eligibility and recovery behavior):** no change to existing refusal or recovery paths beyond the evidence-failure lines listed above.

## Deferred

- Reviewer dispositions, stored evidence, and model-judged narrative review — carved out to BACKLOG #435.
- Response-basis display — carved out to BACKLOG #437.
- Evidence in `--view` renderings and `roadmap_html.py` — not named by this step; add only by a separate decision.
- Showing evidence for each lower hop of a stack — the top candidate holds the final text; revisit only if a reviewer needs per-hop evidence.
