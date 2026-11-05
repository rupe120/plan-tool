> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Settle the narrative review-evidence contract in ROADMAP_FORMAT.md

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step adds one new H2 section to `ROADMAP_FORMAT.md`, `## Narrative review evidence`, and makes one-line pointer edits at the sites that would otherwise contradict it. The section fixes five things:

- a closed set of two defect classes
- an HTML-comment marker that sets off historical and rejected-alternative prose
- where the removed ids come from
- which defect blocks approval, with an operator exit for each blocking class
- the rule that evidence is computed from the candidate every time and never stored

Steps 2 to 5 build the check, the pure function, the approval refusal, and the CLI display against this section. No code changes. On green, a developer can read one section and know what steps 2 to 5 must produce, without opening any of them.

## Table of Contents

- [Why](#why) — what is undecided today and why it must be fixed before code
- [Input](#input) — the landed contracts this section builds on and what they leave open
- [Files (creates vs edits)](#files-creates-vs-edits) — the one file and the sites inside it
- [Implementation](#implementation) — the decisions the new section records and the approach
- [Tests](#tests) — verification for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — spec and test-tool pointers
- [Applicable guardrails](#applicable-guardrails) — the plan fences that bind this step
- [Deferred](#deferred) — what this step leaves to other steps or backlog entries

## Why

`ROADMAP_FORMAT.md` § "The removal record" says a record is history and that pruning it lets a row back. § "The prose body" says one gate reads the body, and that it never judges the prose. Neither says what happens when live prose still names a row the revision removed. The plan's later steps need five undecided facts before they can start:

- what the defect is called
- what marks prose as history
- which removal records count
- which defects block approval
- how an operator clears a blocking one

If steps 2 to 5 pick these independently, the check, the refusal text, and the CLI display drift apart. This step fixes them once, in the format document that owns the contract.

## Input

The step reads these landed contracts. Read the names off HEAD; the landed names win over any name in this file.

- `plan_tool/roadmap_artifacts.py:RemovalRecord` carries `removed_id`, `rationale`, and `feedback_ids`. `removals` is a tuple on each of the four artifact types. § "The review collections — `feedback` and `removals`" and § "The removal record" document it.
- `plan_tool/roadmap_gates.py:check_inventory_has_prose` matches ids as whole tokens, bounded by anything outside `[0-9A-Za-z_-]`. The new check reuses that matching rule, so this file does not restate it.
- `plan_tool/roadmap_gates.py:check_design_row_continuity` already requires a removal record for a dropped row, and `plan_tool/roadmap_gates.py:run_domain_gates` and its three siblings are the stage gate tuples. The plan keeps the new check out of them (step 2).
- `plan_tool/scope_fence.py:_fenced_code_spans` is the fence scanner `roadmap_gates.py` already uses (CommonMark: length-matching, tilde-aware, CRLF-safe, indentation of four or more spaces is not a fence, unclosed fence runs to end of text). The format section refers to it and does not define a second set.
- `docs/reference/documentation-style.md` governs how a live developer document is structured.

Limits on what this step can verify:

- The IPPT-18 correction operation is not landed when this step is written. Name it by its ticket and plan (`docs/implementation-plans/2-candidate-prose-correction.md`) only. Cite no symbol of it.
- The modules steps 2 to 5 create or edit are cited by module path only.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md`
    - Add `## Narrative review evidence`. Place it after `## Reviewer feedback and candidate lifecycle` and before `## Structural escalation receipts`.
    - § "The removal record": add one sentence pointing to the new section for how a carried record is read by candidate review.
    - § "The prose body": the sentence "One gate reads it" is true for stage gating. Add one clause saying the candidate-review check in the new section also reads the body and is not a stage gate.
    - § "What is deliberately not enforced": add an entry for the meaning-level question, pointing to the new section's "deliberately not" list.

## Implementation

Write the new section in the document's existing idioms: purpose first, a table for the class map, an ordered flow for the compute rule, and the normal path separated from exceptions (`docs/reference/documentation-style.md`).

**Section purpose line.** One sentence: a candidate review shows live prose that names a design row the candidate removed, computed from that candidate. Evidence only. The correction is IPPT-18's, the model-judged review is BACKLOG #435, the response-basis check is BACKLOG #437.

**1. Closed defect classes.** Use a table. Rows are exhaustive; a third class needs a format change. Mint these kebab-case names, or better ones, and then use them identically everywhere:

| Class | Definition | Producer | Consumers | Blocks approval? | Exit |
| --- | --- | --- | --- | --- | --- |
| `removed-id-in-live-prose` | A removed id (see 3) appears as a whole token in live prose | the step 2 check in `plan_tool/roadmap_gates.py` | `plan_tool/roadmap_candidate_narrative.py` (step 3), `plan_tool/roadmap_candidate_review.py` (step 4), the CLI display (step 5) | yes | the IPPT-18 correction operation, or the historical marker |
| `removed-id-ambiguous-reference` | A removed id is also the id of a row present in the candidate, so the token may name the live row | same | same | no. It is an evidence item shown to the reviewer, never a refusal | none required; the reviewer reads it |

- State that "live prose" means the artifact body only. Frontmatter rows, including decision `alternatives`, are not scanned.
- State that a token inside a fenced code block is not live prose. Fenced spans follow the rules of `plan_tool/scope_fence.py:_fenced_code_spans`.

**2. The structural marker.** Use a pair of HTML-comment lines, each alone on its own line, with a fixed spelling. The spelling is the contract and this file owns it. One way: `<!-- roadmap:history:start -->` and `<!-- roadmap:history:end -->`, which follows the repo's existing `<!-- …:start -->` / `<!-- …:end -->` convention in this same file.

- Prose between a start line and the next end line is historical or rejected-alternative context. A removed id there is not reported.
- A marker line inside a fenced span is quoted text, not a marker.
- An unclosed start excludes nothing: the check then reports as if no marker were present. This fails safe, because the check blocks.
- A start nested inside an open start does not extend or reopen the region.
- The marker is structural (a line that must stand alone), not positional or keyword-based. Do not describe it by words like "previously" or "rejected" in prose.
- The marker is prose, so it reaches a candidate by the routes any prose change does: IPPT-18's replacement text, or the reviewer's edit decision.

**3. Source of the removed ids.** State it in one ordered rule:

- The set is the `removed_id` of every record in the candidate artifact's own `removals`: the records carried from the predecessor plus any the candidate adds.
- A carried record the reviewer pruned from the candidate is deliberately not in the set. Row ids come back into live use that way (§ "The removal record").
- A feedback-free candidate has no reviewer edit to its artifact, so its set is the predecessor's carried removals.
- The implementer confirms against `plan_tool/roadmap_candidate.py:materialize_candidate` how a feedback-free candidate's artifact carries `removals`. If it does not carry them, step 3's adapter reads the predecessor's; the format section states the outcome, not the mechanism.

**4. Blocking and exits.** Record the decision per class. `removed-id-in-live-prose` blocks approval, and the refusal names the class, the artifact, the id, and both exits. The two exits are the only listed ones:

- the IPPT-18 correction operation rewrites the span
- the historical marker sets the span off

State explicitly that pruning a carried removal record is a deliberate reviewer bypass, not a listed exit, and that no refusal text may offer it as one. `removed-id-ambiguous-reference` never blocks.

**5. Compute-from-the-candidate rule.** An ordered flow:

- Evidence is derived from the candidate's artifact text and its removals whenever a surface needs it.
- It is never stored, stamped with a digest or identity, cached in a sidecar, or regenerated by a model.
- A candidate created before this ships is checked the same way, because nothing was ever stored for it.
- Seal and approval re-derive it. Showing it and refusing on it use the same computation.

**6. Deliberately not (with reasons).** List these in the section: a semantic judgment of pending versus settled, or current versus historical (unobservable, and a keyword proxy measures vocabulary; carried to BACKLOG #435); keyword matching as the deciding rule; any stored or stamped record; reviewer dispositions; a quality, length, or agreement check between prose artifacts; any change to the stage gate tuples.

**Alternatives rejected** (state in one line each): a keyword list for "historical" prose (vocabulary, not structure); storing evidence on the candidate (stale-evidence risk and a new schema); blocking the ambiguous reference (it may name a live row, so blocking would force a false correction).

**Stop condition.** If blocking policy cannot be kept apart from a meaning-level judgment while writing this section, stop and go to the user. Do not widen the section to cover it.

## Tests

### Verification (non-code step)

This is a non-code step; the test-authoring gate does not apply to it. These checks stand in for unit tests:

- **Format tests stay green** — run `uv run pytest tests/test_roadmap_format.py -q`. Any example block added to the doc is machine-checked there, so a malformed YAML example fails it. Prefer prose and a table over a new YAML example.
- **Symbols exist** — `rg -n` each cited symbol (`RemovalRecord`, `check_inventory_has_prose`, `check_design_row_continuity`, `run_domain_gates`, `fenced_spans`, `materialize_candidate`) at its cited path.
- **Names are used identically** — `rg -n 'removed-id-in-live-prose|removed-id-ambiguous-reference' ROADMAP_FORMAT.md` shows the same two spellings everywhere, and no third class name appears.
- **Marker spelling is unique** — the marker lines are spelled once as the contract and any other mention matches that spelling exactly.
- **Doc sweep** — `rg -n 'One gate reads it|Pruning a carried record' ROADMAP_FORMAT.md` shows both sites edited consistently with the new section. Sweep vocabulary too: `rg -in 'narrative|historical|live prose' ROADMAP_FORMAT.md`.
- **No line numbers** — the added text cites symbols and headings only. A repo grep for the new heading's anchor (`#narrative-review-evidence`) finds only links that point to it.
- **Links resolve** — every relative link added in the section points to a real file or heading.
- **No stray edits** — `git status` shows only `ROADMAP_FORMAT.md` changed.

## Acceptance criteria

- `ROADMAP_FORMAT.md` has an H2 `## Narrative review evidence` placed as described in Files.
- The section lists exactly two defect classes, each with definition, producer, consumers, blocking status, and exit.
- The section gives the marker's exact spelling, the fence rule, the unclosed-start rule, and the statement that a marker inside a fence does not count.
- The section states the source rule for removed ids, including the pruned-record and feedback-free cases.
- The section states which class blocks, names the two exits for it, and says pruning a carried removal record is a bypass and not an exit.
- The section states the ambiguous reference is a non-blocking evidence item and never a refusal.
- The section states that evidence is computed from the candidate each time and is never stored, stamped, or regenerated, and lists the deliberately-not items with reasons.
- The three pointer edits (removal record, prose body, not-enforced) are present and agree with the section.
- `uv run pytest tests/test_roadmap_format.py -q` passes.
- No file other than `ROADMAP_FORMAT.md` is changed.

## References

- [CommonMark Spec 0.31.2: Fenced code blocks](https://spec.commonmark.org/0.31.2/#fenced-code-blocks) — read for the opening and closing fence rules the "not live prose" statement relies on.

## Applicable guardrails

- **The plan's "## Scope guardrails" — evidence only.** This step documents the check and its refusal. It adds no remedy, no model-judged review, no stored evidence, and no reviewer disposition.
- **The plan's "## Scope guardrails", "Not allowed" list.** The section must name the deliberately-not items with reasons. It must not describe a semantic gate or a keyword rule as the deciding test.
- **The plan's "## Out of scope", the response-basis and meaning-level carve-outs.** The section may point at the backlog entries that own them and must not specify them.
- **The plan's "## Scope guardrails", refusal behavior.** The only new refusal the section describes is for the blocking class chosen here. It states no change to feedback eligibility, authority limits, or recovery.

## Deferred

- The check function and its Integration fixture test — step 2.
- The pure evidence function and the adapter from stored candidate content — step 3.
- The approval refusals in `plan_tool/roadmap_candidate_review.py` — step 4.
- CLI display and `docs/cli/roadmap.md` regeneration — step 5.
- The IPPT-18 correction operation itself — its own plan, `docs/implementation-plans/2-candidate-prose-correction.md`.
- The meaning-level narrative review, stored evidence, and dispositions — BACKLOG #435.
- The reconciliation-response basis and its checks — BACKLOG #437.
- Consolidating the several frontmatter and fence scanners in the repo — a cross-module refactor for the backlog, not this step.
