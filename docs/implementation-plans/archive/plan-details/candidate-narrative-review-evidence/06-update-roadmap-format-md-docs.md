> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Document the shipped narrative evidence and close the IPPT-19 backlog stub

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step brings the docs in line with what steps 1 to 5 shipped and closes the backlog record. `ROADMAP_FORMAT.md` is corrected where landed names differ from step 1's wording, and its source-of-truth banner and relations section name the new check and the new evidence module. `docs/ARCHITECTURE.md` gets the new module and its import edges in the Roadmap paragraphs. `BUG_BACKLOG.md` loses the IPPT-19 promotion stub, since the full effort has shipped. No code changes. On green, every symbol the docs name for this effort exists at HEAD, and the check's absence from the stage gate tuples is stated.

## Table of Contents

- [Why](#why) — what is stale or missing after steps 1 to 5
- [Input](#input) — landed names to read and limits on checking
- [Files (creates vs edits)](#files-creates-vs-edits) — the three files and their edits
- [Implementation](#implementation) — what each doc must say and the key constraints
- [Verification (non-code step)](#verification-non-code-step) — runnable checks in place of unit tests
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what other entries own

## Why

Step 1 wrote the contract in `ROADMAP_FORMAT.md` before any code existed, so some of its names are proposals. Steps 2 to 5 then minted the real symbols. Nothing yet says which of the doc's names landed, the source-of-truth banner and the "Relations" section do not mention a check that sits outside the stage tuples, and `docs/ARCHITECTURE.md` does not mention the new module. `BUG_BACKLOG.md` still carries the `### Candidate review can present prose reconciliation as handled while contradictions remain` stub (`- **Promoted:** IPPT-19 (2026-10-01)`). Per `docs/TRACKING.md` § "Promotion stubs" and the plan's backlog requirement, the stub is removed only after the full effort ships.

## Input

- **Steps 1 to 5** own the contract and the code. Read every name off HEAD. The landed name wins over any name in step 1's section or in the earlier detail files. Needed names:
  - the check in `plan_tool/roadmap_gates.py` and its two class-name constants
  - the finding record type
  - the pure evidence function and the stored-candidate adapter in `plan_tool/roadmap_candidate_narrative.py`
  - the private refusal helper in `plan_tool/roadmap_candidate_review.py` and its two callers (`seal_review`, the `approve` branch of `decide_structural_candidate`)
  - the render helper in `plan_tool/cli/roadmap_cmd.py`
- **Existing doc facts to keep true:** `ROADMAP_FORMAT.md` states "twenty-nine" relation gates in four tuples (banner, § "Relations — return violations", and the table below it). The new check is outside those tuples (step 2), so the count must not change.
- **Doc rules:** `docs/reference/documentation-style.md` governs structure. `ROADMAP_FORMAT.md` says the code wins when the two disagree.
- **Limits on checking:** IPPT-18's correction operation may not be landed. Cite it only as `docs/implementation-plans/2-candidate-prose-correction.md`, with no symbol.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md`
    - Reconcile `## Narrative review evidence` (step 1) against landed names. Fix only what disagrees with HEAD.
    - Banner: add the evidence module and the removed-id check to the code list, in the banner's existing style.
    - `### Relations — return violations`: add a short paragraph saying the removed-id check is not one of the twenty-nine and runs in no stage tuple, with a pointer to `## Narrative review evidence`.
    - `## Reviewer feedback and candidate lifecycle`: add one sentence that both approval paths recompute the evidence and refuse a blocking class, with a pointer to the same section.
  - `docs/ARCHITECTURE.md`
    - The Roadmap paragraph beginning "Roadmap (`plan_tool/roadmap.py`…": list `roadmap_candidate_narrative.py` in the module list.
    - The "shared leaves form a one-way import chain" paragraph: state the new module's first-party imports at HEAD (read them from the file) and that it is a pure function with no model call or filesystem write.
    - The candidate-lifecycle paragraph (starting "The reviewer ledger remains mutable input…"): add one or two sentences saying `seal_review` and the structural approve path recompute evidence from stored bytes, refuse only the blocking class, and store nothing. State that `plan_tool/cli/roadmap_cmd.py` displays the same finding list.
  - `BUG_BACKLOG.md`
    - Delete the whole entry: the `### Candidate review can present prose reconciliation as handled while contradictions remain` heading and its `- **Promoted:** IPPT-19 (2026-10-01)` line.

## Implementation

**What must hold**

- **Landed names win.** Open each module and copy names from it. Do not carry any name over from the plan or from step 1's prose. Change `ROADMAP_FORMAT.md` only where it disagrees with HEAD.
- **Count stays twenty-nine.** The check is not in `run_domain_gates` or its three siblings, so no count, table row, or "no stage runs all" sentence changes. State this in the new paragraph so the next reader does not "fix" the count.
- **Ownership: one home per fact.** The blocking classes, operator exits, marker rule, and "never stored" rule live only in `## Narrative review evidence`. The other sites carry a one-line pointer. Do not restate those facts in `docs/ARCHITECTURE.md` or the lifecycle section.
- **Forward-looking prose.** Write what the code does. Add no history lines about a former state.
- **Do not add a CLI doc edit.** `docs/cli/roadmap.md` was regenerated in step 5; this step does not touch it.
- **Backlog removal is a full delete.** Remove the stub because the effort has fully shipped. Leave `BACKLOG.md` entries #435 and #437 alone: they cite IPPT-19 as a dependency and stay valid.
- **Sweep both halves, by identifier and by vocabulary.** Before closing, grep the repo for:
  - `IPPT-19`, to confirm no remaining link depends on the deleted stub's heading anchor
  - the removed concept's words (`narrative`, `removed-id`, `live prose`) in `CLAUDE.md`, `CAPABILITIES.md`, and `docs/`, to catch a doc that still describes approval as not checking prose. Edit one only if it falls in a declared file. Otherwise record it in `## Deferred`.
- **Heading anchors.** Do not rename any existing heading in either doc. Adding sentences under existing headings changes no anchor.

## Verification (non-code step)

This is a **non-code** step. The plan's test-authoring gate does not apply (it keys on `change_type`). Run these checks instead:

1. **Symbols exist.** For each backtick symbol the new text names, run `rg -n "<symbol>" plan_tool/`. Each must return a definition.
2. **No line numbers.** The added text contains no `file:NN` form and no line ranges.
3. **Banner and gate count.** `rg -n "twenty-nine" ROADMAP_FORMAT.md` returns the same three sites as before. Compare the `check_*` list in `plan_tool/roadmap_gates.py` with the doc: the removed-id check is described as outside the tuples.
4. **Reverse direction.** Every public name that steps 2 to 5 added to `plan_tool/roadmap_gates.py` and `plan_tool/roadmap_candidate_narrative.py` appears in `ROADMAP_FORMAT.md` § "Narrative review evidence" or the lifecycle paragraph.
5. **One home per fact.** The blocking-class names and operator exits appear in full only under `## Narrative review evidence`.
6. **Links.** Every relative link and anchor added resolves. `rg -n "IPPT-19" BUG_BACKLOG.md` returns nothing.
7. **Backlog remainder.** `BUG_BACKLOG.md` still has the neighboring entries intact: `git diff BUG_BACKLOG.md` shows only the two-line stub removed (plus its blank line).
8. **Doc tests.** Run `uv run pytest tests/test_roadmap_format.py tests/test_capability_catalog.py -q`. `tests/test_roadmap_format.py` parses the examples in `ROADMAP_FORMAT.md`, so a broken example block shows up here. Run `uv run pytest tests/ -q -n auto` once at the end.
9. **Clean tree.** `git status` shows only the three declared files.

## Acceptance criteria

- `ROADMAP_FORMAT.md` § "Narrative review evidence" uses the names that exist at HEAD, with no leftover proposed name.
- The `ROADMAP_FORMAT.md` banner names the removed-id check and the evidence module.
- The relations section says the removed-id check is not one of the twenty-nine and is in no stage tuple; the number "twenty-nine" is unchanged at all three sites.
- `docs/ARCHITECTURE.md` lists `roadmap_candidate_narrative.py`, states its imports as read from HEAD, and says both approval paths and the CLI use it.
- `BUG_BACKLOG.md` no longer contains the IPPT-19 heading or its `Promoted` line; nothing else in that file changes.
- `rg -n "IPPT-19" BUG_BACKLOG.md` returns nothing; `BACKLOG.md` entries #435 and #437 are unedited.
- Every symbol named in the added prose is found by `rg` under `plan_tool/`.
- The full suite passes.

## Applicable guardrails

- **The plan's "## Scope guardrails" (supplies evidence only):** the docs describe evidence and the refusal. They do not describe model-judged review, stored evidence, or reviewer dispositions as shipped or planned here.
- **The plan's "## Out of scope" (carved items):** the pointers to the later review work stay in `BACKLOG.md`. This step does not add that work to the format doc.
- **The plan's "Not allowed" list:** the docs must not describe a semantic gate, a keyword-matching rule, or a semantic exit-code flip. The only refusal described is the deterministic one step 1 selected.
- **Plan's backlog requirement:** this step performs the backlog bookkeeping. The stub goes only because steps 1 to 5 are done.

## Deferred

- Updating `CLAUDE.md` or `CAPABILITIES.md` if the sweep finds stale prose about approval — outside this step's declared files; route to `BACKLOG.md` if found.
- Model-judged narrative review, stored evidence, and reviewer dispositions — carved out to BACKLOG #435.
- Reconciliation-response basis checking — carved out to BACKLOG #437.
- The prose-correction operation — IPPT-18 (`docs/implementation-plans/2-candidate-prose-correction.md`).

## Tests

_(stub: model omitted this section — fill in manually)_

