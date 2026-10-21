> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 11 — Document both intent fields and the four propagation rules, give this plan its own intent, and close BACKLOG #206

## Summary

This step writes down what steps 1–10 built. It states both intent fields in `PLAN_FORMAT.md` (schema rows, semantics, the one-line rule and the cap, the advisory `intent-presence` check, and the four structural verbs' propagation rules), tells seed authors in `SEED_FORMAT.md` that `## Outcome` now becomes durable plan data, records one hop per flow doc (`docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md`), adds one terse paragraph plus two bullet updates to `CLAUDE.md`, and removes BACKLOG **#206** entirely. The main design decision is **one home per fact**: the field schema and the four rules live only in `PLAN_FORMAT.md`, every other doc cross-links to it, so the contract cannot drift six ways. It also gives this plan its own `intent` — plan-level and all eleven steps — which needs the plan file added to the declared list (noted below). On green, `plan-tool validate intent-scope-fence` reports no `intent-presence` smell, `rg '#206' BACKLOG.md` returns nothing, and every code symbol the seven docs cite resolves at HEAD.

## Table of Contents

- [Summary](#summary) — what ships, the one-home-per-fact decision, and the result on green.
- [Why](#why) — a feature nobody can find is a feature nobody uses, and a shipped backlog entry reads as unstarted work.
- [Input](#input) — the eight upstream outcomes this step describes, and the rule for reading their names.
- [Files (creates vs edits)](#files-creates-vs-edits) — seven declared files plus one added, with the per-file edit.
- [Implementation](#implementation) — the ownership map, the per-file edits, the backlog close, and eight gotchas.
- [Tests](#tests) — the test-authoring gate does not apply; the substitute is a numbered verification list.
- [Acceptance criteria](#acceptance-criteria) — greps and commands a reviewer can run.
- [References](#references) — the YAML, PyYAML, and markdown-anchor behavior this step leans on.
- [Applicable guardrails](#applicable-guardrails) — the fence entries that bind, and the two places breaking them is tempting.
- [Deferred](#deferred) — the sibling-detail sweep and the four things routed out.

## Why

Ten steps land two schema fields, an advisory check, a shared fence renderer, three prompt slots, two `create` producers, four propagation rules, and three seed renderers — and not one line anywhere tells an author the `intent:` key exists. `PLAN_FORMAT.md` is the doc a plan author actually opens, and today it lists eleven step fields and none of them is this one; a field absent from the schema doc reads as a typo, not a feature. The flow docs have the same gap in the other direction: `docs/DETAIL_FLOW.md`'s prompt-input list, `docs/RUN_FLOW.md`'s render step, and `docs/AUDIT_FLOW.md`'s "the plan body plus the per-step detail bundle" sentence each describe a prompt that now carries more than they say. And BACKLOG **#206** — the entry that asked for all of this — still sits in the backlog describing unstarted work, where `BACKLOG.md`'s own rule is "remove a feature's entry when it ships." This step also makes the plan the first user of its own feature: the plan's acceptance criteria require it, and a plan that adds `intent` while carrying none is the exact "documented but unadopted" shape the advisory check exists to flag.

## Input

Eight upstream outcomes this step describes. **Read every name off the landed module, not off this file or the sibling detail that proposed it — the landed name wins.** Each detail file was written before its code existed; where they disagree, correct this doc's citation rather than the code.

- **Step 1 — the two fields.** `plan_tool/schema.py` carries `Plan.intent` and `Step.intent`, both optional and left out of rewritten frontmatter when unset. That elision is the fact the `Defaults` table entry rests on.
- **Step 2 — the advisory check.** `plan_tool/review.py` ships `check_intent_presence` plus a `SMELL_DETECTORS` entry, a public source token (`intent-presence`) and a private character cap. Read both constants' landed values; the cap's number goes in `PLAN_FORMAT.md` and nowhere else.
- **Step 3 — the shared leaf.** `plan_tool/scope_fence.py` now owns the plan-body fence renderer that `PLAN_FORMAT.md` currently cites at its old home in `plan_tool/detail.py`. The re-export keeps the old import path working, so the stale citation will not fail anything — it just names the wrong module.
- **Step 4 — the detail prompt's fence.** The fence renders both halves through one function in `plan_tool/scope_fence.py`, and `plan_tool/prompts/detail.md`'s slot is renamed. `plan_tool/prompts/detail-quality.md` keeps the old slot and deliberately gets guardrails only.
- **Step 5 — the run lane's fence.** `plan_tool/renderer.py` builds the same block for `plan_tool/prompts/run.md` and `plan_tool/prompts/run-jira.md`, rendering nothing when there is no fence.
- **Steps 6 and 7 — the two `create` producers.** A seed's `## Outcome` fills the plan's intent; the step proposal supplies a one-line intent per step. Step 6 settles what "one line" means (a whitespace collapse, no truncation) — quote that rule, do not restate it in different words.
- **Step 8 — split and merge.** Two rules: a split half never inherits the target's intent; a merge survivor keeps one only when every folded member states the same one.
- **Step 9 — scope-out and reground.** Two more rules: survivors carry their intent unchanged, and a carved or re-baselined step's intent rides its own block or bullet in the forward seed, attached to its source step.
- **Step 10 — the audit prompt.** `plan_tool/review.py` formats an intent block into a new `plan-audit.md` slot, which makes the audit prompt's substituted-block count one higher than BACKLOG **#162** currently claims.

**What this step cannot verify.** Nothing here proves the documented behavior is the shipped behavior beyond symbol existence and grep. The checks below confirm every cited symbol resolves and every claim's home is unique; they cannot confirm a sentence describes the code correctly. Read the module when a claim feels uncertain rather than transcribing this file.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `PLAN_FORMAT.md` — five edits: the two `intent:` rows in the frontmatter schema block; two field-semantics entries (the step-level one carries the four propagation rules); the `Defaults` table row plus the optional-plan-level-fields sentence under it; a sentence in `### Validation rules` saying only the type is enforced; the `### Plan-level scope fence …` section rewritten for both halves and the moved renderer; and one new entry in `## Smell checks (advisory)`.
  - `SEED_FORMAT.md` — two bounded edits: the `**Outcome**` bullet gains what `create` now does with it, and the "Canonical H2s pay for themselves" convention's existing omitted-`Outcome` warning gains the new consequence.
  - `CLAUDE.md` — one new architecture paragraph for `plan_tool/scope_fence.py`; the `PLAN_FORMAT.md` and `SEED_FORMAT.md` reference-doc bullets updated; one cross-link clause in the **Structural remedy vocabulary** section; `docs/DETAIL_FLOW.md` added to the per-flow-docs bullet, which omits it today.
  - `docs/DETAIL_FLOW.md` — the `## The per-step author round-trip` prompt-input bullet gains the fence, and `## Source map` gains a row for the leaf.
  - `docs/RUN_FLOW.md` — the `run_step()` gauntlet's render-prompt step gains the fence, the jira-grade section notes both templates carry it, and `## Source map` gains a row.
  - `docs/AUDIT_FLOW.md` — the conceptual-layer paragraph's "plan body plus the per-step detail bundle" sentence gains the intent block, and `## Source map` gains a row.
  - `BACKLOG.md` — delete the whole **#206** entry; delete its clause from the grounding roll-up in the Quality/accuracy lens; correct **#162**'s four-block count; refresh the two entries citing the moved renderer and the renamed detail slot (the fold note inside **#161** and **#197**'s worked example).
  - `docs/implementation-plans/2-intent-scope-fence.md` — **an addition to the step's declared `files:` list.** The step title requires giving this plan its own intent, and a plan's intent lives in its own frontmatter, so the file has to be in the footprint; add the path to the step's `files:` when you start. Two bounded edits: the `intent:` values (plan-level plus all eleven steps), and the `## Testing` per-step test-strategy list, which labels step 10 `non-code` and has no step 11 line — stale after the renumber that inserted the audit step. Step 10's detail routed that correction to reconcile; it lands here instead, now that the file is in this step's footprint.

## Implementation

**What must be true on green.** An author who opens `PLAN_FORMAT.md` learns the field exists, what it holds, what happens to it under each of the four structural verbs, and that nothing enforces it. Each other doc states only its own share and links out for the rest. `BACKLOG.md` carries no trace of **#206**. This plan carries its own intent at both levels.

### The ownership map — one home per fact

Pick the home first, then write. Restating a fact class in a second doc is how six copies drift six ways.

- **`PLAN_FORMAT.md`** — the sole home of the field schema, the one-line rule and its numeric cap, the `intent-presence` source token, and the four propagation rules.
- **`SEED_FORMAT.md`** — the sole home of what a *seed author* must do differently: `## Outcome` becomes the plan's intent, so write it as one sentence.
- **Each flow doc** — its own command's hop, and nothing else. `docs/DETAIL_FLOW.md` owns the authoring prompt's fence input; `docs/RUN_FLOW.md` owns the run/run-jira slot; `docs/AUDIT_FLOW.md` owns the audit prompt's intent block.
- **`CLAUDE.md`** — the module map and the pointers. One paragraph naming the leaf, its two callers, and where the rules live.
- **`BACKLOG.md`** — no ownership at all here; it loses the entry.

### `PLAN_FORMAT.md` — the schema home

- **Frontmatter schema block.** Two rows, each with the same short comment shape the neighbours use: a plan-level `intent` near `title`, and a `steps[].intent` among the step fields. Say "optional" and "one line" in the comment.
- **Field semantics.** Two entries in the existing `**\`field\`** — prose` style. The plan-level one says what it holds and that `create` fills it from a seed's `## Outcome` (step 6). The step-level one is the longer of the two and carries the four propagation rules as a short list, one line each:
  - **split** — neither half inherits the target's intent; both start unset, because the target's line described work that turned out to be two things.
  - **merge** — the survivor keeps an intent only when every folded member states the same one; anything else clears it.
  - **scope-out** — every surviving step's intent carries unchanged and the narrowed plan's own `Plan.intent` is cleared; the carved step's intent travels into its block in the forward seed.
  - **reground** — marking a step `done` changes its lifecycle, not its purpose, so every intent survives unchanged; under the re-baseline disposition each step's intent rides its own bullet in the seed.

  Close the list with the rule the four share: **every rule can clear the field, and clearing beats carrying a value that is no longer true.** A stale intent reads as authoritative while being wrong, and after step 5 it reaches the `run` prompt as a boundary.
- **`Defaults` table + the sentence under it.** One `steps[].intent | null` row; add `intent` to the sentence listing the optional plan-level fields.
- **`### Validation rules`.** One short paragraph beside the existing feature-fields exception: the parser enforces the **type** only. One-line-ness, the cap, and placeholder detection are advisory and live in the smell layer — link to `## Smell checks (advisory)` the same way the feature paragraph does.
- **`### Plan-level scope fence …`.** The heading says "reaches the `detail` prompt" and that is now half the truth. Rename it to name both lanes; `rg` shows no inbound link to its current anchor, so the rename is safe (re-check before you edit). Inside:
  - The fence has **two halves** — the positive half is the plan's and the step's intent, the negative half is the four body sections already listed. Keep the existing four-section list exactly as it is; it is still correct.
  - Repoint the renderer citation from `plan_tool/detail.py:extract_plan_guardrails` to the landed function in `plan_tool/scope_fence.py`, naming both the whole-fence renderer and the guardrail extractor.
  - Name the slot: the implementation prompts (`plan_tool/prompts/detail.md`, `run.md`, `run-jira.md`) share one `${...}` name, while `plan_tool/prompts/detail-quality.md` keeps the older guardrails-only slot **on purpose** — handing a reviewer both the intent and the authored prose sets up the comparison this plan bans. Say that, in one sentence; it is the fact most likely to be "fixed" by a later editor.
  - Keep the existing paragraph about the channel carrying fence content only. It still holds for the negative half and now needs one clause saying the positive half is the author's stated purpose, not a claim about what the plan delivers.
- **`## Smell checks (advisory)`.** One entry in the existing style, naming the check function, the source token, the cap number, and the cardinality decision step 2 settled: absences roll up into one plan-wide finding naming every carrier; a placeholder or over-long value gets its own. Say it never flips an exit code — the section already says that of the whole layer, so one clause is enough.

### `SEED_FORMAT.md` — two sentences, not a section

The seed doc is short and dense; resist adding a heading. Both edits attach to text that already exists.

- The **`Outcome`** bullet gains what now happens to it: `create` lifts it into the new plan's `Plan.intent`, collapsed to one line, so it stops being prose the pipeline re-derives. The authoring consequence is the point — write Outcome as one sentence, because that sentence becomes the plan's durable statement of purpose.
- The **canonical-H2 convention** already warns that a seed shaped for the canonical body silently omits `Outcome` and `In scope`. Add the new cost: no `Outcome` means the plan ships with no `Plan.intent`, and the advisory check will say so.

### `CLAUDE.md` — one paragraph and three bullet fixes

Match the file's per-module paragraph shape (`**Rate-limit recovery loop (\`rate_limit_loop.py\`).**` is the closest model — a leaf, its callers, its one rule). Keep it to a paragraph; depth belongs in `PLAN_FORMAT.md`.

The paragraph should carry: the leaf's path and that it imports no first-party code; the whole-fence renderer and the guardrail extractor by name; the two callers (`plan_tool/detail.py` for authoring, `plan_tool/renderer.py` for `run`/`run-jira`) and the shared slot name; the deliberate exclusion of the review prompt; the audit's separate intent-only block via `plan_tool/review.py`; that presence is advisory and never blocking; and a pointer to `PLAN_FORMAT.md` for the field schema and the four rules.

Then three small fixes: the `PLAN_FORMAT.md` bullet gains "both intent fields"; the `SEED_FORMAT.md` bullet gains that Outcome becomes the plan's intent; the **Structural remedy vocabulary** section gets one cross-link clause saying each remedy carries an intent propagation rule, stated in `PLAN_FORMAT.md`. Do not restate the rules there. While in the reference-docs list, add `docs/DETAIL_FLOW.md` to the per-flow bullet — the new paragraph cites it and the list omits it.

### The three flow docs — each doc's own idiom

These are gate/sequence maps, not prose. Match what is already there.

- **`docs/DETAIL_FLOW.md`** — the `## The per-step author round-trip` **Prompt:** bullet enumerates every input `render_detail_prompt` fills in. Add the fence to that enumeration in the same clipped style, naming both halves. Add a `## Source map` row for `plan_tool/scope_fence.py`.
- **`docs/RUN_FLOW.md`** — the gauntlet's `[4] render prompt` line is where the fence appears. It is a fixed-width ASCII block: keep the alignment, add no `[BLOCK]`/`[WARN]` marker (nothing blocks here), and add no line number. Note in the jira-grade section that both templates carry the same slot. Add a `## Source map` row.
- **`docs/AUDIT_FLOW.md`** — the conceptual-layer paragraph's sentence about rendering the prompt "with the plan body **plus the per-step detail bundle**" gains the intent block as a third named input, framed as what makes the `Stay inside the declared scope contract` rule's Outcome item reachable. Add a `## Source map` row for the formatter.

### Closing BACKLOG #206

- **Delete the entry outright.** `BACKLOG.md`'s stated rule is removal on ship, not a status flip, and nothing of #206 remains open: its one deliberately-unshipped item — the intent-vs-`## Why` agreement check — is refused permanently by this plan's `## Out of scope`, whose durable record is `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract". **Do not leave a stub entry for that check.** A stub is exactly the "argues for the thing you removed" residue the delete-on-sight rule names.
- **Sweep the roll-up.** The Quality/accuracy lens' `grounding:` list names **#206** with a parenthetical description. Delete that clause and leave the surrounding list punctuation clean.
- **Correct #162's block count.** It states `render_plan_audit_prompt` "substitutes exactly four blocks" and names them. Step 10 makes it five. Update the count and the list, and add a short clause saying the intent fields already ride that prompt so #162's remaining scope is the seed/backlog contract — which keeps the sibling relationship the plan's `## Out of scope` declares.
- **Refresh the two stale renderer citations.** The fold note inside **#161** says `detail` "receives only the headings `extract_plan_guardrails` recognizes (`detail.py`)"; **#197**'s worked example cites `extract_plan_guardrails` → the old detail slot name. Repoint both at the leaf and, for #197, at the renamed slot. Both claims stay true otherwise — this is a name fix, not a rewrite.

### Giving this plan its own intent

- **Plan-level.** Write it by hand; step 6's lift is for plans `create` authors from a seed, and this plan predates the field. The plan's `## Scope guardrails` opens with the sentence that already says it ("make a plan's and a step's *why* durable data that reaches every model acting on it…"). Condense that to one line inside the cap; step 2's detail measured that sentence at roughly 135 characters, so it fits with room.
- **Per step.** One line each, for all eleven steps, saying why the step exists — not what it does, which the title already carries. The step's detail `## Why` is the natural source to condense from.
- **Then run the check.** `plan-tool validate intent-scope-fence` is the fastest confirmation that every carrier is covered and nothing is a placeholder or over-long.

### Gotchas — the parts not free to vary

- **Editing the plan file mid-run is safe, and the reason is specific.** `plan_tool/parser.py:write_plan` does a compare-and-swap and raises `ConcurrentModificationError` when the on-disk frontmatter moved since it was parsed. `plan_tool/launcher.py:_reread_plan_for_writeback` re-reads the plan before every status write-back precisely so an operator edit is not clobbered. Add `intent:` keys only — do not touch `status`, `steps` ordering, or ids while the step is running.
- **Adding intent moves the plan fingerprint.** `plan_tool/review_persistence.py:compute_plan_fingerprint` hashes the plan file's bytes, so this plan's saved completeness and reconcile sidecars go stale and a later reuse prompt reports drift. That is expected, not a defect — say nothing about it in the docs, just do not be surprised.
- **Cite symbols, never line numbers.** `docs/RUN_FLOW.md` carries a few pre-existing `file.py:NNNN` anchors; leave them alone and add none.
- **The renamed heading changes an anchor.** Grep for inbound links to the current `### Plan-level scope fence …` anchor before renaming (`rg 'plan-level-scope-fence'`); at the time of writing there are none, and `PLAN_FORMAT.md`'s own in-file links target `#body-sections-advisory-checked` and `#smell-checks-advisory`, neither of which this step touches.
- **`PLAN_FORMAT.md` has no `## See also` tail** — unlike `DETAIL_FORMAT.md` and `JIRA_FORMAT.md`. Do not add one; cross-link inline the way the file already does.
- **Do not restate the four propagation rules outside `PLAN_FORMAT.md`.** `CLAUDE.md` and the flow docs get a pointer. The moment a second copy exists, the next verb change updates one of them.
- **Do not document a check that does not exist.** Nothing compares an intent to prose, to a `## Why`, or to a diff, at any level. Write presence and shape as the only checked properties, and do not phrase the advisory finding as though it judged quality.
- **The seed doc is a directive doc, not a schema doc.** `SEED_FORMAT.md` tells an author what to write; it must not grow a field table. Two sentences attached to existing bullets is the whole edit.

## Tests

This is a `change_type: non-code` step. The plan sets `enforce_step_tests: true`, but the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps, so it does not apply here and no test file is owed. The substitute is the check list below.

### Verification (non-code step)

Run each from the repo root. Every one is mechanical.

1. **Every cited symbol resolves.** Extract each backticked `plan_tool/…:symbol` citation added by this step and confirm the symbol exists (`rg "def <symbol>" <path>`). Zero misses.
2. **Every cited path exists.** Same for the module and prompt paths added — `plan_tool/scope_fence.py`, `plan_tool/prompts/run-jira.md`, and the rest.
3. **No new line numbers.** `rg -n '\.(py|md):[0-9]+' PLAN_FORMAT.md SEED_FORMAT.md docs/DETAIL_FLOW.md docs/AUDIT_FLOW.md CLAUDE.md` shows nothing this step added; `docs/RUN_FLOW.md`'s pre-existing anchors are unchanged in `git diff`.
4. **The stale renderer citation is gone.** `rg -n 'detail\.py:extract_plan_guardrails' PLAN_FORMAT.md BACKLOG.md` returns nothing.
5. **The four rules have one home.** They appear in `PLAN_FORMAT.md` and are referenced — not restated — everywhere else. Read the `CLAUDE.md` and flow-doc additions and confirm each is a pointer.
6. **The cap number has one home.** No character cap for intent appears outside `PLAN_FORMAT.md`.
7. **#206 is gone, completely.** `rg -n '#206' BACKLOG.md BUG_BACKLOG.md CLAUDE.md README.md` returns nothing, and the grounding roll-up reads cleanly with the clause removed.
8. **#162 is accurate.** Its named block list matches what `render_plan_audit_prompt` substitutes at HEAD.
9. **The plan validates and carries its intent.** `plan-tool validate intent-scope-fence` exits 0 and prints no `intent-presence` line under `smells (advisory):`.
10. **The plan parses and round-trips.** `plan-tool status intent-scope-fence` succeeds after the frontmatter edit.
11. **Section links resolve.** Any new in-file `#anchor` link matches a real heading slug in its target file.
12. **The renamed anchor breaks nothing.** `rg` for the old anchor slug across the repo returns nothing.
13. **Tense check.** Every added sentence is present or future tense, and no removed concept is described in the present tense beside current design.
14. **Clean tree.** `git status` shows only the eight files this step declares (seven declared plus the plan file added above).

## Acceptance criteria

- `PLAN_FORMAT.md`'s frontmatter schema block contains a plan-level `intent:` row and a `steps[].intent:` row, each marked optional and one line.
- `PLAN_FORMAT.md` has a field-semantics entry for each field, and the step-level entry lists all four propagation rules (split, merge, scope-out, reground) plus the shared clearing rule.
- `PLAN_FORMAT.md`'s `Defaults` table has a `steps[].intent | null` row, and the sentence beneath it names `intent` among the optional plan-level fields.
- `PLAN_FORMAT.md`'s `## Smell checks (advisory)` names the check function, the `intent-presence` source, the cap's number, and the roll-up-vs-per-carrier cardinality.
- `rg -n 'detail\.py:extract_plan_guardrails' PLAN_FORMAT.md BACKLOG.md` returns nothing; the scope-fence section cites the function's landed home in `plan_tool/scope_fence.py`.
- `PLAN_FORMAT.md`'s scope-fence section states that `plan_tool/prompts/detail-quality.md` deliberately receives the guardrails half only.
- `SEED_FORMAT.md`'s `**Outcome**` bullet states that `create` lifts it into the new plan's `Plan.intent`, and the canonical-H2 convention names the missing-intent consequence.
- `CLAUDE.md` has one paragraph naming `plan_tool/scope_fence.py`, its two callers, and the pointer to `PLAN_FORMAT.md`; its `PLAN_FORMAT.md` and `SEED_FORMAT.md` reference bullets mention intent; its per-flow-docs bullet lists `docs/DETAIL_FLOW.md`.
- Each of `docs/DETAIL_FLOW.md`, `docs/RUN_FLOW.md`, `docs/AUDIT_FLOW.md` describes its own command's intent hop and has a `## Source map` row for every newly cited symbol.
- `rg -n '#206' BACKLOG.md` returns nothing, and no stub entry for an intent-vs-work agreement check exists anywhere in `BACKLOG.md`.
- BACKLOG **#162**'s substituted-block list matches `render_plan_audit_prompt` at HEAD and notes the intent fields already ride that prompt.
- `docs/implementation-plans/2-intent-scope-fence.md` carries a plan-level `intent:` and an `intent:` on each of its eleven steps, all within the cap and none a placeholder.
- The plan body's `## Testing` per-step list labels step 10 `feature` and carries a step 11 `non-code` line.
- `plan-tool validate intent-scope-fence` exits 0 with no `intent-presence` finding.
- `git status` shows changes to exactly the eight files named in [Files](#files-creates-vs-edits).

## References

- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — scalar styles and line folding, behind the "one line" wording in the schema rows and field semantics.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_dump` key ordering and scalar emission, behind the `Defaults` table's elision claim.
- [Basic writing and formatting syntax — GitHub Docs](https://docs.github.com/en/get-started/writing-on-github/getting-started-with-writing-and-formatting-on-github/basic-writing-and-formatting-syntax#section-links) — how a heading's anchor is derived, the reason the scope-fence heading rename needs an inbound-link grep first.

## Applicable guardrails

- **"No step ships a check comparing an intent against prose or against a diff."** This is the guardrail that binds this step hardest, because a docs step is where a checker gets *described* into existence. The tempting line is in `PLAN_FORMAT.md`'s scope-fence section: having explained that `detail-quality.md` gets guardrails only, it reads naturally to add "so a future check could compare the intent to the authored `## Why`." Do not write it. State the exclusion and its reason, and stop.
- **"Nothing becomes required at parse time, and no plan on disk is migrated."** Every sentence about the fields must say optional and advisory. Avoid "should always", "must declare", and any wording that reads as a requirement — an author reading a schema doc treats emphasis as enforcement.
- **"Allowed behavior changes: two optional frontmatter fields; one advisory finding class; and rendered input reaching three consumers across five templates — `detail.md` and `detail-jira.md`, `run.md` and `run-jira.md`, and `plan-audit.md`. The run lane additionally gains the plan's existing guardrail and `## Out of scope` sections whether or not an intent is set. Nothing else."** This step ships no behavior at all. If a doc edit seems to need a code change to be true, the doc claim is wrong — fix the claim.
- **"A finding that this plan's own artifacts fail to carry their intent **is** in scope."** This is what puts the plan file in the footprint and makes the eleven step intents a deliverable rather than a nicety.
- **"Findings proposing that intent be made required, that an agreement check be added, or that propagation widen past the four structural verbs are outside this fence — defer them to `BACKLOG.md`."** Applies directly to the backlog close: do not re-file the refused check as a fresh entry while removing #206.

## Deferred

- ~~The sibling detail files that said "step 10 owns the docs"~~ — **closed 2026-08-01 by a hand sweep** of all nine (details 01–09), which were stale after the renumber that made the audit step 10 and this step 11. Nothing remains for this step. Recorded because the original routing named `plan-tool reconcile-code`, which is the wrong verb for it: `reconcile-code` treats the plan as canonical and edits **code**, so it cannot rewrite detail prose. The only remedies for stale detail prose are a hand sweep or a follow-up `detail` re-author pass.
- **The rest of BACKLOG #162** — the seed/backlog scope contract as an authoritative audit-prompt block. This step only corrects #162's block count and notes that intent already rides that prompt; the entry stays open.
- **Any intent-vs-work agreement check** — refused permanently by the plan's `## Out of scope`, with `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract" as the durable record. Not deferred to a future entry; deliberately not filed.
- **A `CAPABILITIES.md` entry** — this plan registers no new subcommand, so `plan_tool/capability_catalog.py:check_capabilities` has nothing to flag in either direction. Checked, no edit owed.
- **Threading intent into the jira export and its docs (`JIRA_FORMAT.md`)** — out of the plan's scope; the story summary already carries the motivation.
- **A `DATA_CONTRACT.md` edit** — that doc covers persisted runtime schemas (sidecars, fingerprints, manifest) and enumerates no `Plan`/`Step` field, so the new fields add nothing there.
