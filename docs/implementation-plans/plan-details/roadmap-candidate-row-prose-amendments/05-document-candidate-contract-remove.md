# Step 5 — Document the candidate contract and remove the source bug after regressions pass

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Document the landed row-owned prose amendment contract in `ROADMAP_FEEDBACK_FORMAT.md` and `ROADMAP_FORMAT.md`, then remove the resolved candidate-prose bug from `BUG_BACKLOG.md`. Keep the ledger workflow focused on reviewer-facing lifecycle behavior and keep immutable candidate schema, gate, and structural-review facts in the roadmap format. Confirm the upstream candidate, run, review, and CLI regressions pass before treating the backlog symptom as resolved. On green, the reference documents describe the shipped contract without widening candidate authority, and the stale bug entry is gone.

## Table of Contents

- [Summary](#summary) — Reviewer overview of the documentation and backlog cleanup.
- [Table of Contents](#table-of-contents) — Quick links to each section.
- [Why](#why) — The candidate behavior that needs an accurate public contract.
- [Input](#input) — Landed upstream behavior and existing documentation ownership.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation edits.
- [Implementation](#implementation) — Documentation boundaries and the condition for retiring the bug.
- [Tests](#tests) — Non-code verification and required regression evidence.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [References](#references) — Existing contract and implementation anchors.
- [Applicable guardrails](#applicable-guardrails) — Scope limits for this documentation step.
- [Deferred](#deferred) — Related work that remains outside this step.

## Why

`plan_tool/roadmap_candidate.py:materialize_candidate()` currently has no candidate-owned prose path, so an added prose-inventory row can fail `plan_tool/roadmap_gates.py:check_inventory_has_prose()`. Steps 1 through 4 establish the append, admission, disclosure, and prompt behavior that resolves this gap; this step makes the reference contract match that landed behavior and removes the backlog entry only after its regression coverage proves the original failure is closed.

## Input

- **Steps 1–4 landed behavior:** Read the landed candidate operation shape and validation from `plan_tool/roadmap_candidate.py:CandidateAddRow`, `parse_candidate_delta()`, and `materialize_candidate()` rather than transcribing names or limits from this detail. The code wins if an upstream implementation differs from planned wording.

- **Existing document ownership:** `ROADMAP_FEEDBACK_FORMAT.md:## Ledger-to-candidate workflow` owns the reviewer-facing candidate lifecycle. `ROADMAP_FORMAT.md:## Reviewer feedback and candidate lifecycle`, `## The prose body`, and the immutable-candidate authority block own artifact, gate, review, and publication facts.

- **Regression evidence:** Use the focused suites in `tests/test_roadmap_candidate.py`, `tests/test_roadmap_candidate_run.py`, `tests/test_roadmap_candidate_review.py`, and `tests/cli/test_roadmap_cmd.py` as the evidence that the new contract works before deleting the matching `BUG_BACKLOG.md` entry.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `ROADMAP_FEEDBACK_FORMAT.md` — update `## Ledger-to-candidate workflow` with the reviewer-facing requirement for prose-bearing eligible additions and its inert-candidate lifecycle.
  - `ROADMAP_FORMAT.md` — document the immutable candidate operation and prose-gate contract, including the review-visible amendment facts and unchanged authority boundaries.
  - `BUG_BACKLOG.md` — remove the entry headed `### Structural candidates cannot satisfy described-row gates for newly added rows` after the required regressions pass.

## Implementation

- **Document the closed addition-only contract.** In `ROADMAP_FORMAT.md`, describe the landed `CandidateAddRow` contract as the sole candidate operation that can carry a row-owned prose amendment. The documentation must make clear that eligible additions require prose, while replacement and removal operations do not gain prose-edit authority.

- **Keep prose bounded and tied to its row.** Describe the facts enforced through `plan_tool/roadmap_candidate.py:parse_candidate_delta()` and `plan_tool/roadmap_artifacts.py:stage_row_operation_policy()`: the amendment belongs to the added row, uses the added row’s identity, is nonblank, names that row as a whole token, and stays within the project hard ceiling represented by `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES`.

- **Preserve batch semantics.** State that one admitted feedback item can still support multiple authorized additions and their separate amendments. Do not import the stage-revision one-material-operation rule into candidate documentation.

- **Describe append-only materialization.** Point readers to the candidate assembly boundary at `plan_tool/roadmap_candidate.py:materialize_candidate()` and the shared append behavior from step 1. The prose amendment must append to predecessor narrative without replacing existing prose, creating body regions, or generating text from the tool.

- **Make reviewability explicit.** In `ROADMAP_FORMAT.md`, explain that structural disclosure derives row-linked amendment facts from stored normalized operations and that the structural stack digest binds those facts. Keep `plan_tool/cli/roadmap_cmd.py:_render_structural_candidate_disclosure()` and `_render_structural_candidate_stack()` as orientation only; do not change approval, seal, promotion, or accepted-head rules while documenting the new data.

- **Keep the ledger guide procedural.** In `ROADMAP_FEEDBACK_FORMAT.md:## Ledger-to-candidate workflow`, explain what a reviewer can expect from a valid proposal and what remains inert until approval and promotion. Avoid duplicating the complete immutable operation schema there; `ROADMAP_FORMAT.md` remains the deeper contract reference.

- **Retire only the resolved bug.** Delete the named entry from `BUG_BACKLOG.md` only after the focused regressions cover successful prose-bearing additions, required refusals, structural disclosure, and no publication before approval. Preserve adjacent backlog items, including the candidate-diagnostics follow-up.

## Tests

This is a non-code step. The test-authoring gate does not apply because the step edits documentation and backlog tracking only.

### Verification (non-code step)

1. `tests/test_roadmap_candidate.py` — run the focused candidate regressions proving admitted eligible additions append row-linked prose, clear `undescribed-row`, and retain refusal behavior for invalid amendments.

2. `tests/test_roadmap_candidate_run.py` — run proposal and replay regressions proving prompts and stored normalized operations preserve the amendment contract.

3. `tests/test_roadmap_candidate_review.py` — run structural-review regressions proving amendment disclosure and stack-digest binding retain the existing approval lifecycle.

4. `tests/cli/test_roadmap_cmd.py` — run CLI rendering regressions proving structural output exposes the stored amendment facts without publishing a candidate.

5. `ROADMAP_FEEDBACK_FORMAT.md` and `ROADMAP_FORMAT.md` — verify every cited symbol and contract term exists in the landed implementation, and verify the two documents divide lifecycle guidance from immutable schema and authority facts without conflicting statements.

6. `BUG_BACKLOG.md` — verify the removed heading has no remaining match and that neighboring backlog entries remain unchanged.

## Acceptance criteria

- `ROADMAP_FORMAT.md` documents that only eligible candidate `add-row` operations carry the required row-owned prose amendment, including its identity, content, and hard-size boundaries.

- `ROADMAP_FORMAT.md` states that candidate prose appends to the predecessor body and that `check_inventory_has_prose()` remains the enforcement point rather than being weakened or bypassed.

- `ROADMAP_FORMAT.md` states that structural review exposes the row-linked amendment facts from stored operations and that stack identity includes them.

- `ROADMAP_FEEDBACK_FORMAT.md` describes the amendment requirement in the candidate workflow while retaining the existing inert-candidate, approval, and promotion boundaries.

- The focused regressions in `tests/test_roadmap_candidate.py`, `tests/test_roadmap_candidate_run.py`, `tests/test_roadmap_candidate_review.py`, and `tests/cli/test_roadmap_cmd.py` pass before the bug entry is removed.

- `rg -n "Structural candidates cannot satisfy described-row gates for newly added rows" BUG_BACKLOG.md` returns no matches.

## References

- [BUG_BACKLOG.md — Read the resolved candidate-prose symptom and its required regression evidence.](BUG_BACKLOG.md)

- [ROADMAP_FEEDBACK_FORMAT.md — Read the ledger workflow and reviewer-facing candidate lifecycle.](ROADMAP_FEEDBACK_FORMAT.md)

- [ROADMAP_FORMAT.md — Read the immutable candidate lifecycle, prose-body rule, and gate ownership.](ROADMAP_FORMAT.md)

- [plan_tool/roadmap_candidate.py — Read candidate operation admission and materialization behavior.](plan_tool/roadmap_candidate.py)

- [plan_tool/roadmap_gates.py — Read the unchanged `check_inventory_has_prose` enforcement rule.](plan_tool/roadmap_gates.py)

- [plan_tool/project_config.py — Read the project-wide prose amendment size ceiling.](plan_tool/project_config.py)

## Applicable guardrails

- **The plan’s “## Plan intent”, candidate prose behavior:** Document the shipped bounded addition path only; do not add a broader narrative-edit capability.

- **The plan’s “## Step intent”, documentation and backlog outcome:** Limit this step to accurate reference updates and bug retirement after regression evidence. Do not change production behavior.

- **The plan’s “## Out of scope”, candidate authority and prose editing:** Keep replacement, removal, and whole-body editing outside the documented candidate capability. Preserve the existing gate, lifecycle, accepted-head, seed, and correction-diagnostics boundaries.

## Deferred

- **Candidate correction diagnostics** — Leave the separate `BUG_BACKLOG.md` diagnostics entry unchanged because its closed-envelope error aggregation is unrelated to documenting the landed prose amendment contract.
