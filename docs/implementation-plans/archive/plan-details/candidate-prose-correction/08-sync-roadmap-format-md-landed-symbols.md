> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Sync ROADMAP_FORMAT.md to the landed symbols, record the delivery route, and remove the IPPT-18 promotion stub

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This non-code step edits two docs. In `ROADMAP_FORMAT.md` § "Reviewer feedback and candidate lifecycle", it replaces the sentence that says `CandidateAddRow` is the only candidate operation with row-owned prose authority and that replacement and removal have no prose-edit authority. The new text names the `correct-prose` operation and the other symbols steps 2–7 landed, reading them off HEAD. It also records the delivery route for the Integration correction: use the edit route first, rerun the batch only as a fallback, and keep the Group 5 candidate as evidence until a replacement exists. In `BUG_BACKLOG.md`, it removes the IPPT-18 promotion stub. On green, the doc matches the code and no stale add-row-only claim remains. The backlog no longer carries the shipped entry.

## Table of Contents

- [Why](#why) — the doc claim that is now false and the stub that is now spent
- [Input](#input) — what the earlier steps produced and the current text being replaced
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — the doc edits, the delivery-route record, and the stub removal
- [Tests](#tests) — non-code verification
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step does not do

## Why

`ROADMAP_FORMAT.md` says `plan_tool/roadmap_candidate.py:CandidateAddRow` is the only candidate operation with row-owned prose authority. It also says replacement and removal carry no candidate prose-edit authority. Once steps 3–7 land, the first claim is false, because candidates can correct an issued shared span. The doc's banner says the code wins on any disagreement. A stale authority sentence misleads a reader about what a candidate may change in the body. Operators also need one stated path for delivering the Integration correction. The IPPT-18 entry in `BUG_BACKLOG.md` is a promotion stub that this plan's shipment obliges us to remove.

## Input

- **Step 1 contract:** step 1 already wrote the shared-narrative correction contract into this same section. That covers the owning set, authority binding, refusal values, combined-operation rule, application order, and byte ceiling. Read the landed text first and edit around it. This step reconciles that text with the add-row paragraph and does not restate the contract a second time.
- **Steps 2–7 output:** the landed symbols are the splice helper in `plan_tool/roadmap_revision_patch.py`, the `correct-prose` operation and its parse, bind, and apply functions in `plan_tool/roadmap_candidate.py`, the issued shared span in `plan_tool/roadmap_revision.py` and `plan_tool/roadmap_candidate_context.py`, replay in `plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_operations`, and the before/after projection in `plan_tool/roadmap_candidate.py:candidate_prose_amendment_diffs` with its printer in `plan_tool/cli/roadmap_cmd.py`. Read each name from HEAD. Landed names win over any name used in this plan or in the sibling detail files.
- **Text being replaced:** the paragraph starting "`plan_tool/roadmap_candidate.py:CandidateAddRow` is the only candidate operation that carries a row-owned prose amendment." Its last sentence is "Replacement and removal operations have no candidate prose-edit authority."
- **Neighbouring paragraphs to keep true:**
  - The "One admitted feedback item may authorize multiple additions…" paragraph says `materialize_candidate` applies "shared append behavior after authorized typed additions".
  - The "Structural disclosure reads row-linked amendment facts…" paragraph describes what the stack digest binds.
  - The § "The prose body" candidate-additions paragraph carries a pointer to step 1's contract.
  - The structured-comparison text (near the paragraph mentioning "row-linked prose amendments" in the comparison section) describes raw-patch comparison. It stays as is, because the labeled correction card is carved to BACKLOG #436.
- **Delivery-route facts:** the plan's "Delivery route" paragraph fixes the order: check the supported edit route first (`plan_tool/roadmap_candidate_review.py:_edit_structural_candidate`, step 7 pins that edit keeps the correction and moves the digest). Discard and rerun the same batch only if the edit route cannot carry the operation. The current Group 5 candidate stays as evidence until a corrected replacement exists.
- **Stub today:** under the heading "Candidate feedback cannot reconcile stale shared narrative without changing typed rows" in `BUG_BACKLOG.md`, the only content is `- **Promoted:** IPPT-18 (2026-10-01)`. `docs/TRACKING.md` § "Promotion stubs" says a promotion stub is removed after full shipment.
- **Open reference:** `BACKLOG.md` already names IPPT-18 in the #436 entry as a dependency. That entry is out of this step's file list and stays unchanged.
- **Limit on verification:** the doc cannot be checked against a real Integration run here. Symbol existence and the edit-route claim can be checked against HEAD and step 7's tests.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md`:
    - Replace the add-row-only prose-authority sentence and its "no candidate prose-edit authority" companion with text that matches the landed operations.
    - Cite the landed symbols that steps 1–7 created, by name from HEAD.
    - Add a short delivery-route paragraph.
    - Fix any sibling sentence made false by the change (see Implementation).
  - `BUG_BACKLOG.md`: remove the "Candidate feedback cannot reconcile stale shared narrative without changing typed rows" heading together with its `Promoted: IPPT-18` line.

## Implementation

- **Replace the authority sentence.**
  - State that candidates have two row-owned or span-owned prose authorities. One is `CandidateAddRow`'s `{row_id, fragment}` amendment for a row the same candidate adds. The other is the `correct-prose` operation, which replaces exactly one issued shared span in an existing artifact body.
  - State what stays true: `CandidateReplaceRow` and `CandidateRemoveRow` carry no prose authority of their own. Their prose-edit claim stays in the doc, narrowed to those two operations.
  - Keep the add-row rules (nonblank fragment, whole-token naming, `HARD_MAX_PROSE_AMENDMENT_BYTES`) as written.
  - Do not copy step 1's contract text. Point to its landed paragraph or subsection by heading.
- **Cite landed symbols, not planned ones.** Use `file:symbol` form for modules steps 2–7 landed: the splice helper, the operation class and its parser, the span issuance function, and the replay check. Do not cite line numbers. Check every cited name with `rg` before writing it.
- **Sweep the section for the claim's restatements.**
  - Class: any sentence in `ROADMAP_FORMAT.md` that says candidate prose authority is add-row-only, or that candidates can only append.
  - Search by identifier: `CandidateAddRow`, `row-owned prose`, `prose-edit authority`, `materialize_candidate`.
  - Search by vocabulary: "append", "only appends", "without replacing existing prose", "shared append behavior", "no candidate prose".
  - The "each fragment appends to the predecessor narrative without replacing existing prose" clause is about add-row fragments. Keep it true by scoping it to those fragments, and state that corrections replace an issued span.
  - Check the "Structural disclosure" paragraph. It should say disclosure also carries the correction's before and after text, and that the digest binds it, matching step 7. Remove or reword anything step 7 contradicts.
  - Check the § "The prose body" pointer and the ToC-like lead (the banner list of modules) for stale claims. The banner needs no new modules unless a new module landed.
  - Leave the structured-comparison text unchanged. State there that comparison shows the raw patch, as the plan's out-of-scope list requires.
- **Record the delivery route.** Add one short paragraph to the same section:
  - The edit route is tried first. The decision `edit` stores a replacement keeping the `correct-prose` operation, and the stack digest changes, so approval of the old text cannot confirm the new text.
  - Discard-and-rerun of the same batch is the fallback, used only if the edit route cannot carry the operation.
  - The existing Group 5 candidate stays as evidence until a corrected replacement exists.
  - Do not say the route has been run. Say what the documented order is. If step 7's tests show the edit route cannot carry the operation, write the fallback as the delivery path instead and say why.
- **Write forward-looking text.** Describe what the tool does now. Do not narrate the old add-row-only state. The plan's date-and-past-tense rule allows history only when it protects a reader, and none applies here.
- **Remove the stub.**
  - Delete the heading and its `Promoted: IPPT-18` line as one block. Keep the blank-line spacing between the neighbouring entries intact.
  - Do not touch the IPPT-19 stub below it. IPPT-19 is out of scope for this plan.
  - Search the repo for the entry's title and the key `IPPT-18`. `BACKLOG.md` mentions IPPT-18 in the #436 entry, which names it as a dependency and records the plan carve. Leave that entry as is, because it is outside this step's file list and records a still-valid dependency. Report any other inbound reference in the handoff instead of editing it here.
- **Check the anchor.** Removing a heading changes inbound anchors. Search the corpus for a link to the removed heading's slug before deleting. If none exists, the removal is safe.
- **Do not add a plan-completion marker.** The backlog bookkeeping this step does is exactly the stub removal. No other backlog file needs editing for this plan.

## Tests

### Verification (non-code step)

- `rg -n "only candidate operation|no candidate prose-edit authority" ROADMAP_FORMAT.md` — returns nothing, or only the narrowed replace/remove sentence
- `rg -n "correct-prose" ROADMAP_FORMAT.md` — shows the operation named in the authority paragraph and in the disclosure paragraph
- For each `plan_tool/…:symbol` cited by the edit, run `rg -n "<symbol>" plan_tool/<file>` — every cited symbol exists at HEAD
- `rg -n "append" ROADMAP_FORMAT.md` over the candidate section — every remaining "append" claim is scoped to add-row fragments
- `rg -n "Group 5|edit route|discard" ROADMAP_FORMAT.md` — the delivery-route paragraph states the edit-first order, the fallback, and the evidence rule
- `rg -n "IPPT-18" BUG_BACKLOG.md` — no match
- `rg -n "cannot reconcile stale shared narrative" BUG_BACKLOG.md ROADMAP_FORMAT.md` — no match
- `rg -n "IPPT-19" BUG_BACKLOG.md` — the neighbouring stub is still present
- `rg -n "cannot-reconcile-stale-shared-narrative" .` — no inbound anchor links to the removed heading
- `uv run pytest tests/test_roadmap_format.py -q` — passes. This test reads fenced blocks and marked regions, so confirm the edit did not break a marked region or fenced example.
- `uv run pytest tests/test_data_contract.py tests/test_duplication.py -q` — still passes (no code changed)
- `git diff --stat` — touches only `ROADMAP_FORMAT.md` and `BUG_BACKLOG.md`

## Acceptance criteria

- `ROADMAP_FORMAT.md` no longer says `CandidateAddRow` is the only candidate operation with prose authority.
- The doc names `correct-prose` and states that it replaces one issued shared span without any typed-row change.
- The doc states that replace-row and remove-row operations carry no prose authority of their own.
- Every `plan_tool/…:symbol` the edit cites exists at HEAD, and none is cited by line number.
- The doc states the delivery order: edit route first, discard-and-rerun only as fallback, and the Group 5 candidate kept as evidence until replaced.
- The structured-comparison text still describes raw-patch comparison, with the labeled correction card left to BACKLOG #436.
- `BUG_BACKLOG.md` has no IPPT-18 stub, and the IPPT-19 stub is untouched.
- `tests/test_roadmap_format.py` passes.
- The diff touches only the two declared files.

## Applicable guardrails

- **The plan's "## Out of scope", structured comparison:** this step must not edit the comparison text to add a correction card. It leaves comparison describing the raw patch and may only restate that fact.
- **The plan's "## Scope guardrails", no new authority:** the doc text must not describe arbitrary body replacement, marker-based editing, or any authority granted by a stale-row reference. The doc names only the bounded issued-span operation.
- **The plan's "## Scope guardrails", review-evidence layer (IPPT-19):** the doc must not claim contradiction detection. The IPPT-19 stub stays where it is.
- **The plan's "## Scope guardrails", Group 4 feedback:** the delivery-route paragraph must not describe rewriting accepted Group 4 feedback or requiring a new feedback group.
- **The plan's forward-looking documentation rule (project documentation rules):** write the new text in present tense. Add no past-tense narration of the add-row-only state.

## Deferred

- Labeled correction card in structured version comparison — carved to BACKLOG #436 and left unchanged by this step.
- Review-evidence layer for unresolved narrative contradictions (IPPT-19) — separate plan; its stub in `BUG_BACKLOG.md` stays.
- Running the Integration delivery route and replacing the Group 5 candidate — operator work after this plan ships. This step only documents the order.
- Edits to the `BACKLOG.md` #436 entry that mention IPPT-18 — outside this step's file list; the dependency it records remains valid.
