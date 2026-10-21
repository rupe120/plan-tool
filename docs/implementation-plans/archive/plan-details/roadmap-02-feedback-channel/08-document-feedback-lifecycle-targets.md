> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document the feedback lifecycle, its targets, and the roadmap review loop

## Summary

Update the four operator-facing docs so a reviewer can find and drive the feedback loop steps 1–7 ship: `ROADMAP_FORMAT.md` gains the `feedback` and `removals` frontmatter collections, the two new closed vocabularies, the new parse-time rules, and the corrected gate table; `RUNBOOK.md` gains the end-to-end walkthrough (write a request → re-enter at that artifact's stage → read the response → close, reopen, or defer); `USE_CASES.md` gains the situation and a compact example; `CAPABILITIES.md` records that the verb now revises against human feedback. The key design decision: **each fact class has exactly one home doc and the others cross-link to it** — the frontmatter keys and lifecycle values live only in `ROADMAP_FORMAT.md`, the operator loop only in `RUNBOOK.md` — because a lifecycle restated in four places drifts four ways. On green, no doc still claims eight gates or tells a reviewer not to re-run after editing an artifact, the feedback-bearing example in `ROADMAP_FORMAT.md` parses and clears its stage's gates against a predecessor, and `tests/test_capability_catalog.py` stays green.

## Table of Contents

- [Summary](#summary) — what changes across the four docs and what is checkable on green.
- [Why](#why) — the loop ships undocumented, and three current claims become wrong.
- [Input](#input) — the contracts this step describes, and the rule that the landed names win.
- [Files (creates vs edits)](#files-creates-vs-edits) — four edits, no new doc.
- [Implementation](#implementation) — the ownership map, the per-file edit shape, and the wording that is not free to vary.
- [Tests](#tests) — the substitute verification for a non-code step.
- [Acceptance criteria](#acceptance-criteria) — greppable facts a reviewer can run.
- [References](#references) — the YAML grammar and the anchor rules the edits depend on.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's prose.
- [Deferred](#deferred) — docs no step in this plan owns, and what is deliberately not written.

## Why

After step 7, the whole loop works and nothing tells anyone it exists. A reviewer reading today's docs learns the opposite of what now ships, in three specific places:

- **`ROADMAP_FORMAT.md` says "eight gates" in four spots** — the source-of-truth banner, the relations-table lead, the "no stage runs all eight" paragraph, and "judged by six gates, not eight". Step 2 lands three more. It also lists four closed vocabularies; step 1 lands two more.
- **`RUNBOOK.md` and `USE_CASES.md` both tell the reviewer not to re-run after editing `02-constraints.md`** — RUNBOOK's "needs **no re-run at all**, and you should not do one", USE_CASES entry 11's "wants no re-run at all". That was correct when a re-entry regenerated from the brief. Writing a feedback row into an artifact and re-entering at its own stage is now the supported loop, so the advice as written steers a reviewer away from the feature.
- **The summary's overwrite advice reads as a warning against the loop.** `plan_tool/cli/roadmap_cmd.py:_overwrite_summary_lines` says "copy it aside first if you edited it by hand", and RUNBOOK repeats it. It is still right about the prose body and about anything no gate pins — and now wrong as blanket advice, because a revision preserves ids, feedback rows, and settled decisions.

The plan's Risks section names the cost of leaving this: "a reviewer may accidentally resend a response or remove a request too early." Both mistakes are one edit away in YAML that nothing in the tool explains.

## Input

This step describes contracts that already landed. Read each name **off the module**, not out of this file or a sibling detail file — a name proposed while a step was being planned is a proposal, and **the landed name wins on any disagreement**, exactly as the doc's own source-of-truth banner says of the code.

- **Step 1 owns the schema names**: the feedback and removal row types, their fields, the two closed vocabularies (lifecycle state and target kind), the shared review-key constant, and the two collections defaulting to empty on both artifacts. Grep `plan_tool/roadmap_artifacts.py` for what actually shipped.
- **Step 2 owns the gates**: three new `check_*` functions, the envelope's predecessor field, and the entries appended to `DOMAIN_GATES` and `CONSTRAINTS_GATES`. Take the counts from the landed tuples, not from a sibling's prose.
- **Step 4 owns what a revision is asked for**: one shared template at `plan_tool/prompts/roadmap-revision.md`, wrapped around the stage's authoring prompt, carrying the prior artifact and only the `open` rows as active guidance.
- **Step 5 owns when a predecessor exists**: read pre-flight, for every stage at or above the re-entry point; an artifact that is present but unreadable stops the run; a predecessor is **never gated**.
- **Step 6 owns the write and the record**: the artifact lands as the gates accepted it, one `revision_feedback_delivered` run-log line per written revision carrying ids and counts but no text, and a count of rows awaiting review on the result. `DATA_CONTRACT.md` (step 3) is the event's home doc — cite it, do not restate its fields.
- **Step 7 owns the printed block**: the count and the three editor actions, printed for both outcomes, never touching the exit code.
- **The four docs' own conventions**, checked one at a time rather than assumed uniform:
  - `ROADMAP_FORMAT.md` carries the source-of-truth banner and a `## See also` tail; both stay.
  - `RUNBOOK.md`'s table of contents lists the roadmap workflow's H2 only — its two existing H3s (`### Reviewing what it guessed`, `### Where the arc stops today`) are not listed, so a new H3 there needs no ToC entry.
  - `USE_CASES.md` entry 11 is the roadmap situation, and it is linked from entry 1 by anchor.
  - `CAPABILITIES.md` entries parse into `id` / `surfaces` / `principles` plus free prose, and `tests/test_capability_catalog.py:test_check_real_repo_catalog_is_honest` asserts the real doc is clean.
- **What this step cannot verify.** Every check below judges whether the docs are accurate and internally consistent. Whether a reviewer actually finds the loop usable is step 9's real-run exercise.

## Files (creates vs edits)

**New files:** none. Resist giving the lifecycle its own document — a fifth roadmap doc splits the schema across two files and the honest homes already exist.

**Existing files (edits only):**

- `ROADMAP_FORMAT.md` — add the two review collections to the frontmatter schema, the two new closed vocabularies, the new parse-time rules, the predecessor field on the envelope, and the three gates in the relations table; sweep every gate-count and vocabulary-count claim; add the lifecycle walkthrough and a feedback-bearing example.
- `RUNBOOK.md` — add a quick-reference row, a new H3 under the roadmap workflow holding the end-to-end loop, and the preserved-versus-not table; correct the re-run advice and reconcile the copy-aside caution.
- `USE_CASES.md` — extend entry 11 with the feedback loop and a compact example; correct the same re-run sentence.
- `CAPABILITIES.md` — extend the `architecture-roadmap` entry.

## Implementation

### Do this first: read what landed

Before writing a line, grep the four modules for the names you are about to print. At minimum: the feedback and removal row types and their fields, both new vocabularies and every member, the review-key constant, the three `check_*` gate names, the envelope's predecessor field, `len(DOMAIN_GATES)` / `len(CONSTRAINTS_GATES)` and the total count of `def check_`, the revision template's filename, the result field the summary reads, and the run-log event kind. A name this plan proposed but the implementer changed is a name that must not appear in a schema reference.

### The ownership map — one home per fact class

State this to yourself before editing and hold it; it is what stops the same lifecycle drifting four ways.

- **`ROADMAP_FORMAT.md`** — the frontmatter keys, the row fields, both closed vocabularies and every member, what raises at parse time versus what a gate reports, the gate table, and the YAML-level lifecycle example. Sole home. No other doc lists the keys or the state values.
- **`RUNBOOK.md`** — the operator loop end to end: where to write a request, which stage to re-enter at, what the summary tells you, what a revision preserves and what it does not, and how to close, reopen, or defer.
- **`USE_CASES.md`** — the situation ("the proposal is wrong and I want to say so in my own words") plus one compact example, linking to the other two.
- **`CAPABILITIES.md`** — one or two sentences on the capability. No schema, no walkthrough.

Cross-link rather than restate. A second copy of the state list in `RUNBOOK.md` is the exact defect this map exists to prevent.

### `ROADMAP_FORMAT.md`

The biggest edit, and mostly additive. What must be true when it is done:

- **The review collections are documented once, for both artifacts.** Both `01-domain.md` and `02-constraints.md` carry them, so a shared section beats duplicating the block under each artifact's schema. Say that the collections are **omitted entirely when empty**, which is why a first run's artifact shows neither key.
- **The target is documented as a tagged union.** Name both kinds, say which one carries a row id and which must not, and say plainly that there is no sentinel id for artifact-wide feedback.
- **The two new vocabularies join the closed-vocabulary section**, in the same table shape the existing four use, each naming its owning constant. Fix the section's count claim; do not write a new number you have not counted off the module.
- **The shape table gains the new raises.** Step 1 put four rules in the parser rather than in a gate: an unknown state or target kind, a tag that disagrees with its payload either way, an `awaiting-review` row with no response, and the required keys on both row types. The last one is a deliberate exception to the doc's existing "blank is not a shape failure" line — say so where that line is, not in a footnote.
- **The "Nothing audits a written artifact after the run" bullet is an edit site too.** It still says a wrong artifact is fixed "by editing it and re-entering at `--from-stage N`", which after step 6 describes only half the review channel and reads as the edit-gets-overwritten warning this position removes. Name the feedback row beside the hand edit. The "no stale re-run advice" check must cover `ROADMAP_FORMAT.md` here, not only `RUNBOOK.md` and `USE_CASES.md`.
- **"What parse time deliberately lets through" gains the review-row non-checks** — a target naming an id nothing defines, a removal citing a feedback id nothing declares, two feedback rows sharing an id, a blank request or rationale, and an `open` or `deferred` row still carrying an old response. That last one is what makes the reopen path legal; call it out rather than listing it flatly.
- **The relations section gains the third gate class, and it is genuinely new.** The section today says each gate judges the artifact under check and reads upstream artifacts only to resolve ids, with the duplicate-id gate as the one exception. The predecessor gates are a second exception of a different kind: they judge the artifact under check **against its own prior version**. Rewrite that paragraph rather than appending to it, and document the envelope's third field beside the existing two.
- **Sweep every count.** The banner, the relations lead, the "no stage runs all eight" paragraph, and the per-stage "six gates, not eight" sentence. Grep the *words* as well as the numbers — "eight", "six", "four" — because the numerals sit inside prose that reads fine.
- **"What is deliberately not enforced" gains four entries**, each with its mechanism: feedback and removal rows are outside the prose-inventory and duplicate-id gates (the row inventory those gates walk names design rows only); feedback ids and design-row ids are separate namespaces, so a feedback id may equal an entity id; a proposed response is stored and never judged; and no count of rows awaiting review flips an exit code.
- **"What writes them" gains the shared revision template.** The section currently says "one prompt file per stage"; there is now also one wrapper shared by every stage, used when the stage's artifact is already on disk. Keep it to a sentence — the template's contents are the prompt's business.
- **The lifecycle walkthrough is the section the plan's Risks bullet demands**, and it must show all five states with real YAML: `open` as the reviewer writes it, `awaiting-review` as the model returns it, `deferred`, a reopened row (state back to `open`, response cleared or kept), and the human close — which has no row at all, so show it as a deletion, before and after. Say in one line who may make each move: the model makes exactly one (`open` → `awaiting-review`); every other move is the reviewer's, made in the editor.
- **Say what `deferred` actually buys, because the word oversells it.** A deferred row is no longer sent as *active guidance*, but its text still reaches the model inside the prior artifact, which a revision carries whole. Deferring parks a request; it does not hide it. A reviewer who defers to keep something out of the model's view needs to delete the row instead.
- **Show how the reviewer answers a clarifying question**, since the model's response may be a question rather than a change. Immutability of `id`, `target`, and `request` binds the *model*, not the reviewer: the reviewer answers by amending that row's `request` in place (or adding a follow-up row) and setting the state back to `open`. The predecessor is snapshotted after the reviewer's edits, so the amended request is what the gates compare against. Say plainly that reopening an *unchanged* request just re-asks the same ambiguous thing — that is the one move that looks right and does nothing.
- **The removal record gets its own short block**: it names the dropped row, carries a rationale, and cites at least one feedback id from the artifact the reviewer edited — which is what stops a model from dropping a row on its own authority. Note it mints no id of its own.
- **The examples are executable artifacts, not illustrations.** Add a feedback-bearing example (one answered row and one cited removal is enough) and put it through the same claim the existing two carry: it parses, round-trips through render-and-re-parse unchanged, and clears its stage's gate set. The new one needs one more thing the existing two do not — **a matching predecessor in the envelope** — because the three new gates are inert without one. An example that clears the gates only because nothing was checked is worse than no example.

### `RUNBOOK.md`

- **Quick reference** — add one row to the roadmap table: write feedback into an artifact, re-enter at that artifact's own stage, and the run revises it instead of regenerating it.
- **New H3 under `## Workflow: turn a concept brief into architecture artifacts (roadmap)`**, after `### Reviewing what it guessed`. It holds the loop: open the artifact, add a feedback row against a row id or against the artifact as a whole, re-enter at that artifact's stage, read the responses beside the requests, then close by deleting the row, reopen by setting the state back, or defer by setting it to deferred. Give it a runnable two-command example in the section's existing style. No ToC entry — this section's H3s are deliberately not listed.
- **Say that a settled decision's preserved anchor makes the anchored row unremovable.** The preserved-versus-not table already says a settled decision keeps its `anchor`; the consequence it does not draw is that the design row that anchor names cannot be removed *at all* until the reviewer sets that decision to `pending`. A reviewer writing "drop `entity-3`" otherwise learns this from a `proposed_response`, one paid attempt later. Put the un-settle-first move beside the anchor row.
- **Warn about the cascade before the reviewer pays for it.** A redirect that makes stage 1 drop a design row leaves stage 2 with no legal move: `02-constraints.md` must drop the constraint anchored to the removed entity, but a removal needs a cited feedback id *in that artifact* and keeping the row trips `check_constraint_anchors`. In practice stage 2 burns its whole budget and the run exits 1. Tell the reviewer, in the loop section, to place a matching request in `02-constraints.md` **before** re-entering low — a removal-bearing redirect is the one case where feedback in a single artifact is not enough.
- **Name the way back to a fresh authoring pass, because nothing else discovers it.** Revision mode is selected by predecessor presence, not feedback presence, so a re-entry over an existing artifact is a revision even when it carries no feedback: the model may add design rows but cannot drop one, since every removal must cite a feedback id and none exists. A reviewer who rewrote the brief and expected a clean re-author instead gets a locked revision. The escape is deleting the artifact file before re-entering; say so here, with the consequence (its feedback rows and settled decisions go with it).
- **Correct `### Reviewing what it guessed` rather than deleting it.** Pending decisions are still worked down by editing in place, and re-entering at that artifact's own stage still rewrites the decision row. What changes is that the section can no longer say "editing the top artifact wants no re-run at all" without scoping it: that is true for a pending decision, and false for a feedback row, which needs the re-entry to be answered. Keep the two channels distinct — a pending decision is the model's own unsettled guess; a feedback row is your instruction and its answer.
  - Renaming that heading is allowed but changes its anchor. Nothing links to it today (`rg -n 'reviewing-what-it-guessed' .`) and the ToC lists only the H2, so the rename is safe — run the grep anyway and record it.
- **Add the preserved-versus-not table.** This is the most useful thing the docs gain and it is what makes the copy-aside advice make sense again:
  - **Preserved on a revision** — every design row id (present, or dropped by a removal that carries a rationale and cites feedback); every feedback row's id, target, and request; a carried `awaiting-review` or `deferred` row's response; a `settled` decision's id, status, chosen option, and anchor.
  - **Not preserved** — the prose body; a `pending` decision; a settled decision's rationale and rejected alternatives (the prompt asks for them, no gate pins them); and the *contents* of a surviving design row, since continuity pins the id and not the value.
  - So the summary's "copy it aside first" advice now reads as: copy aside what is not in the left column.
- **Say that re-entering low sends every stage its own feedback.** A `--from-stage 1` re-run revises `02-constraints.md` too, and delivers whatever open rows it holds. A reviewer who meant to redirect only the domain should know that.
- **Carry the same scope caveat the pending-decision line already carries**: the count the summary prints covers the artifacts *that run wrote*, so a re-entry high says nothing about a lower artifact's rows. Grep the files for the full queue.
- **State the stronger fact the caveat implies, because it is the one that costs a reviewer a cycle**: open feedback in an artifact *below* the re-entry point is never delivered at all. On `--from-stage 2`, `01-domain.md` is loaded as upstream, gets no predecessor and no revision, and its `open` rows are neither sent nor answered — the reviewer finds no `proposed_response` and cannot tell "the model ignored me" from "I re-entered above it". Feedback is delivered only by re-entering at that artifact's own stage.
- **One line on the record**: the run log names which feedback ids went out, against which prior bytes, and with counts describing the artifact **as delivered** — so a row this run answered still counts `open` there, while the summary's awaiting-review count describes the artifact **as written**, and holds neither the request nor the response — pointing at `DATA_CONTRACT.md` for the schema rather than listing fields here.
- **Optional, and verify before writing it:** `## The prompt-budget advisory` lists which commands get a named-block breakdown and which get the total-bytes backstop, and `roadmap` appears in neither list today. A revision prompt carries the whole prior artifact, so this is the moment the advisory becomes relevant to this verb. Confirm at HEAD that the roadmap invoker in `plan_tool/roadmap.py` does not suppress the shell backstop, then add `roadmap` to the backstop list — and keep the advisory's own framing: it warns, it never fails a run.

### `USE_CASES.md`

- **Extend entry 11**, do not add a twelfth. The situation is the same one — a project-sized concept — and the feedback loop is what you do on the second pass.
- **Correct the "wants no re-run at all" sentence** the same way RUNBOOK's is corrected, and keep it short: the compact example plus the pointer to RUNBOOK's walkthrough is the whole job here.
- **Say the one-line version of the guarantee**: a re-entry now revises what is on disk instead of starting over, and the model may propose a response but may not close, defer, or delete your request.

### `CAPABILITIES.md`

- **Extend the `architecture-roadmap` entry's prose** with two sentences: a re-entry over an existing artifact revises it against the reviewer's feedback rows rather than regenerating it, and deterministic gates hold the reviewer's contribution — ids, request text, settled decisions — while the human alone closes a row.
- **Surfaces need no addition.** The four modules are already cited and no subcommand is added, so neither the absent-surface nor the orphan-subcommand check moves. Adding the revision template's path is allowed (a path-shaped surface is checked on disk) but buys nothing.
- **Principles are latitude.** `write-for-the-human` is a defensible third id here and is already served elsewhere, so adding or omitting it changes no finding either way. Add it only if the sentences you write actually make the human-review claim central.

### Wording that is not free to vary

- **Never write that the tool resolves, addresses, handles, closes, or completes feedback.** The model proposes a response; whether it answered the request is the reviewer's call, permanently. "Awaiting your review" is the whole claim.
- **Name no command for closing, reopening, or deferring.** All three are editor actions. A command in that sentence would be a command that does not exist.
- **Do not restate a fact class outside its home doc.** If you find yourself listing the lifecycle values in `RUNBOOK.md`, link instead.
- **Cite symbols, never line numbers.** Every anchor is a function, constant, filename, or heading.
- **Do not describe the review keys as part of the design-row key inventory.** They are a separate constant, and that separation is why a first run's artifact is unchanged.

## Tests

### Verification (non-code step)

This step is `change_type: non-code` and changes no production code. The plan's `enforce_step_tests: true` gate keys on `change_type` and fires only for `feature` and `refactor` steps, so it does not apply here; these checks are the substitute, and each is runnable by a reviewer.

Approx. 15 checks:

- **Examples parse.** Splice each YAML example in `ROADMAP_FORMAT.md` into a file and run it through the real parser for its artifact — no exception.
- **Examples round-trip.** Re-render each parsed example and re-parse it; the two parses are equal.
- **Examples clear their gates.** Run each example through its stage's gate aggregate and expect an empty list — and run the feedback-bearing example with a **matching predecessor** in the envelope, which is the only way the three new gates are exercised at all.
- **Every sentence in these docs that *enumerates* failure kinds or pre-flight causes is an edit site.** Step 6 adds a fourth exit-1 failure kind and step 5 adds three exit-2 pre-flight causes, so each such enumeration is now short. Known instances: `ROADMAP_FORMAT.md`'s "on any of its three failure kinds: the backend failed, the reply was unparseable, or the gates rejected it", `RUNBOOK.md`'s "whether the attempts went to a failing backend, an unparseable reply, or gate violations", and `USE_CASES.md`'s "(backend failure, unparseable reply, or gate violations alike)". Treat the list as the *class*, not the three: `rg -n 'three failure kinds|unparseable reply' ` across the four docs before calling it done, because this enumeration has already been missed twice — step 10 caught `CLAUDE.md` and `integrations/claude/SKILL.md`, and this step's own files were missed in the same pass. **The exit codes themselves do not change**, which is exactly why it keeps being overlooked.
- **Every gate the code ships appears in the doc.** Compare `rg -o 'def (check_\w+)' plan_tool/roadmap_gates.py` against the `check_*` names in `ROADMAP_FORMAT.md`, both directions.
- **Every violation token the code ships appears in the doc's `Violation kind` column**, both directions: compare `rg -o 'VIOLATION_\w+' plan_tool/roadmap_gates.py` against that column. Step 2 mints new tokens, and `roadmap_gates.py`'s own comment states the contract — "One token per defect, so a consumer can group violations without matching on prose. `ROADMAP_FORMAT.md` documents each beside the rule it enforces." Gate-*name* coverage alone lets a new row land with an empty or partial kind column and stay green.
- **Every vocabulary member appears.** Compare the landed feedback-state and target-kind members against the doc's tables.
- **Every cited symbol exists.** One grep per name printed in the four docs against `plan_tool/`.
- **No stale counts.** `rg -n 'eight gates|six gates' ROADMAP_FORMAT.md` returns nothing, and the vocabulary-count sentence matches the number of vocabularies the module declares.
- **No stale re-run advice.** No sentence in `RUNBOOK.md` or `USE_CASES.md` tells a reviewer not to re-run after editing an artifact without scoping that advice to an edit carrying no feedback.
- **No over-claiming.** `rg -in 'resolv|address|handle' ` over the four docs shows no sentence claiming the tool acts on feedback for the reviewer.
- **Anchors resolve.** Every intra-doc link added points at a real heading, and the RUNBOOK heading whose anchor changed (if any) has no inbound links.
- **ToC integrity.** Any new H2 has a ToC entry; new H3s under the roadmap workflow match that section's existing convention of not being listed.
- **No line numbers.** `rg -n '\.py:[0-9]+' ROADMAP_FORMAT.md RUNBOOK.md USE_CASES.md CAPABILITIES.md` returns nothing.
- **Capability catalog stays honest.** `uv run pytest tests/test_capability_catalog.py -q` is green, and `plan-tool validate <any plan>` reports no capability finding.
- **The generated flag reference is untouched.** `docs/cli/roadmap.md` is unchanged and `uv run pytest tests/cli/test_cli_reference.py -q` is green — this step adds no flag.
- **Footprint.** `git diff --name-only` lists exactly the four docs.

## Acceptance criteria

- `rg -n 'eight gates|six gates' ROADMAP_FORMAT.md` returns nothing.
- Every name in `rg -o 'def (check_\w+)' plan_tool/roadmap_gates.py` appears in `ROADMAP_FORMAT.md`, and every `check_*` the doc names exists in that module.
- Every token in `rg -o 'VIOLATION_\w+' plan_tool/roadmap_gates.py` appears in `ROADMAP_FORMAT.md`'s `Violation kind` column, and every token the doc names exists in that module.
- `ROADMAP_FORMAT.md` names both new frontmatter collections, every member of both new closed vocabularies, and the review-key constant, each with its owning constant in `plan_tool/roadmap_artifacts.py`.
- `ROADMAP_FORMAT.md` shows all five lifecycle situations — open, awaiting-review, deferred, reopened, and human-closed — with the close shown as a deleted row.
- The feedback-bearing example in `ROADMAP_FORMAT.md` parses through the real parser, re-parses equal after a render, and yields an empty violation list from its stage's gate aggregate with a matching predecessor in the envelope.
- `RUNBOOK.md` contains a runnable example that adds a feedback row and re-enters at that artifact's own stage, plus a list of what a revision preserves and what it does not.
- Neither `RUNBOOK.md` nor `USE_CASES.md` contains an unscoped instruction not to re-run after editing an artifact.
- No sentence in the four docs says the tool resolves, closes, defers, or reopens feedback, and none names a command for any of those three actions.
- `CAPABILITIES.md`'s `architecture-roadmap` entry describes the revision loop, and `uv run pytest tests/test_capability_catalog.py -q` is green.
- `rg -n '\.py:[0-9]+' ROADMAP_FORMAT.md RUNBOOK.md USE_CASES.md CAPABILITIES.md` returns nothing.
- `docs/cli/roadmap.md` is unchanged and `uv run pytest tests/cli/test_cli_reference.py -q` is green.
- `git diff --name-only` lists exactly `ROADMAP_FORMAT.md`, `RUNBOOK.md`, `USE_CASES.md`, and `CAPABILITIES.md`.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the frontmatter grammar every example in `ROADMAP_FORMAT.md` is written in and that a reviewer hand-edits when they add, reopen, or defer a row; read it for what a nested mapping and a multi-line scalar are allowed to look like.
- [Basic writing and formatting syntax — GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax) — read the section-links part before renaming any heading: the anchor is derived from the full heading text, so a one-word edit silently breaks every inbound link with no error anywhere.

## Applicable guardrails

- **The plan's "## Out of scope", no judging whether a revision honored feedback and no automatic transition out of awaiting-review.** This binds this step hardest, because documentation is where a convenient verb slips in. Describe what the tool does — deliver, preserve, propose, count — and never write that it resolved anything.
- **The plan's "## Out of scope", no TTY walk, confirm, or new feedback subcommand.** The docs must not describe a command for closing, deferring, or reopening a row, and must not imply one is coming.
- **The plan's "## Out of scope", cross-artifact feedback propagation.** Say plainly that feedback is local to the artifact holding it, and that a cross-artifact instruction is written into each artifact it should guide. Do not soften this into "may reach later stages".
- **The plan's "## Out of scope", no cap or rejection keyed on feedback length, shape, count, or semantics.** Where the docs mention prompt pressure, keep it as operational advice; no doc may present a size or count as a limit.
- **The plan's "## Out of scope", no second store, sidecar, or hidden feedback state.** The docs must locate the review state in the artifact and the historical record in git, and describe no other place it lives.
- **The plan's "## Architecture", the operator docs own the discoverable workflow.** That is this step's whole mandate, and it stops at description — no doc here specifies behavior a step did not build.
- **The plan's "## Acceptance criteria", the schema-doc obligations.** `ROADMAP_FORMAT.md` must cover the items that criterion enumerates; follow the plan's list rather than a summary of it.

## Deferred

- **`integrations/claude/SKILL.md`'s two roadmap rows** — the decision-tree row and the at-a-glance row both tell an agent to edit the top artifact in place and not re-run, which this position falsifies. Not deferred and not this step's: the scope decision was taken, and **step 10 owns and declares the file**. The codex and cursor SKILL files mention roadmap nowhere, so the sweep is one file.
- **`README.md`'s run-log event list** — not deferred and not this step's: step 3 owns the delivery event and declares `README.md` in its `files:` list, so the bullet naming the new kind lands there alongside the `DATA_CONTRACT.md` schema.
- **Reconciling `BACKLOG.md` #208 and `CLAUDE.md`'s roadmap paragraph** — step 10, including its "eight relation gates" and "four closed vocabularies" clauses and its "the feedback channel … are later, unauthored arc positions" sentence.
- **The real-run record of redirect and clarification feedback** — step 9. These docs describe the loop; they claim nothing about how well a model revises.
- **`docs/cli/roadmap.md`** — generated from the argparse parser and guarded by its drift test. This position adds no flag, so it is a verified non-edit, not an omission.
- **A separate feedback reference doc** — not taken. A fifth roadmap document would split the schema across two files and give the drift a place to hide.
- **A named-block prompt-budget breakdown for the roadmap verb** — code work, not documentation. If the revision prompt's size turns out to matter in step 9, file it in `BACKLOG.md`; this step documents the advisory as it behaves.
- **Documenting components, seed derivation, or framework lenses** — later, unbuilt arc positions. The "where the arc stops today" sections in `RUNBOOK.md` and `USE_CASES.md` stay accurate and stay put.
