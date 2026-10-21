> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Close out BACKLOG #206 and update CLAUDE.md, keeping both reversal records

## Summary

Delete BACKLOG **#206** — the entry that asked for step-level intent — now that steps 1–7 have shipped it, and move the two recorded reversals into `CLAUDE.md` so they outlive the entry. Three files change: `BACKLOG.md` loses the whole #206 entry plus its clause in the Quality/accuracy lens roll-up, and gains a blocker-cleared note on **#212**; `BUG_BACKLOG.md` gains step 1's routed placeholder-vocabulary defect; `CLAUDE.md` gains a short dated record of both reversals inside `## Validating a semantic property you cannot observe`, plus a narrow carve on that section's rules so they stop arguing against what now ships. The key design decision is **short record, long citation** — `CLAUDE.md` carries only what stops a future audit from re-litigating (what was reversed, whose decision, when, what stayed refused) and cites the two plan files for the argument, because `CLAUDE.md` is injected into every session and both plan files stay on disk. On green, `rg -n '\b206\b' BACKLOG.md` returns nothing and a reader who never opens a plan file can still tell that gating intent *presence* was decided, not overlooked.

## Table of Contents

- [Summary](#summary) — what the step changes and what is true on green.
- [Why](#why) — why the entry must go and why deleting it alone loses something.
- [Input](#input) — the two reversal records, the lifted refusal, and the sibling outcomes this step reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched and the per-file edits.
- [Implementation](#implementation) — the deletions, the record's content and home, the constraints, and the alternatives rejected.
- [Tests](#tests) — why the test-authoring gate does not apply, and the checks that replace it.
- [Acceptance criteria](#acceptance-criteria) — greps and reads a reviewer or CI can run.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's prose.
- [Deferred](#deferred) — the files, sweeps, and follow-ups this step leaves alone.

## Why

`BACKLOG.md`'s own rule in `## Purpose` is "Remove a feature's entry when it ships", and #206 has shipped: the field and fence landed in `docs/implementation-plans/2-intent-scope-fence.md`, and steps 1–7 of this plan close the rest. Its `- **Status:** not started` line is false today and will read as a fresh proposal to the next person triaging the backlog. But a plain delete loses something real. Two decisions were recorded *inside* #206's orbit rather than in a durable doc: the shipped plan widened #206 on an explicit user decision, and this plan lifts one of the shipped plan's "permanently refused" bullets on another. Both are don't-reopen history — exactly the class `CLAUDE.md` § "Documentation is forward-looking" says a reader needs to act correctly — and both cite an id that is about to stop existing. Without the relocation, a later audit reading `2-intent-scope-fence.md`'s "Not allowed … any gate, exit-code flip, or refusal-to-advance keyed on an intent" would correctly flag step 6's promotion as a fence violation, and the argument that discharges it would be nowhere a session actually reads.

## Input

This step reads five things and changes none of their meaning.

- **Reversal record A** — the paragraph beginning "**Widened from BACKLOG #206 — recorded, not silent**" in `docs/implementation-plans/2-intent-scope-fence.md` `## Out of scope`. It carries four facts the relocated record must preserve: the 2026-07-31 explicit user decision; the two limits reversed (a plan-altitude `Plan.intent`, which #206 non-goaled, and an advisory presence check, which #206 did not scope); the one limit **not** widened (making intent required on existing plans); and #206's duplication call kept verbatim (intent is a one-line seed the prompts consume, never re-checked against `## Why`). That paragraph also says step 11 of the carved seed carries the obligation to preserve it — this step is that obligation under this plan's numbering.
- **Reversal record B** — the paragraph beginning "**Exactly one refusal is lifted, and it is recorded, not silent.**" in `docs/implementation-plans/2-intent-required.md` `## Architecture`. Its facts: the 2026-08-02 explicit user decision; that the lift covers presence only; and that the refusal's stated reason is *discharged*, not overruled.
- **The refusal being lifted** — the last bullet of the "Not allowed" list under `## Scope guardrails` → `### Presence is the entire contract` in `docs/implementation-plans/2-intent-scope-fence.md`. Only that one bullet moves; the four above it stay refused.
- **Step 8's outcome** — `check_intent_presence` is `medium` and sits on the blocking self-consistency bucket, so a missing intent blocks completeness convergence while the exit-code convention is untouched. Steps 2, 3, and 5 (authoring) and steps 4 and 7 (the proposer) are what discharge the refusal's reason; the record states that discharge without restating how any of them work.
- **Step 9's outcome** — `PLAN_FORMAT.md` and `SEED_FORMAT.md` now document both fields and the `## Outcome` mapping. `CLAUDE.md` therefore owes no schema restatement here; the record is about the decision, not the contract.

**Limits on verifying this.** Neither file is read at runtime and no test asserts on their contents, so nothing mechanical can confirm the record is *sufficient*. The only checks available are greps for the removed id and a read-through asking whether the record alone would stop a re-litigation. Say so rather than implying the suite covers it.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — delete the whole `**#206 — Step-level intent: the plan records what each step does, never why**` entry; delete the `**#206**` clause from the `grounding:` bullet in `### Quality/accuracy lens (cross-cutting)`; update `**#212 — apply_finding rewrites a step but never clears its intent, leaving an authoritative stale why**` so its dependency and status read as unblocked, and re-point its CLAUDE.md citation at the new record.
  - `BUG_BACKLOG.md` — file step 1's routed defect: `scope_fence._SECTION_PLACEHOLDER_RE` and `review._BODY_PLACEHOLDER_RE` have diverged, so a `TBD` intent is flagged missing by the finding yet still rendered into the fence.
  - `CLAUDE.md` — add the two dated reversal records plus the rule carve inside `## Validating a semantic property you cannot observe`.

## Implementation

### Remove #206, both halves

- **Delete the entry outright** — the bold `**#206 — …**` title line through its closing `- **Status:**` line. It sits in `### A. New capability, well-scoped`, between the `**#205 — Migrate jira-grade detail artifacts when a step renumber moves their ids**` entry and the `**#208 — plan-tool roadmap <slug> …**` anchor entry; leave those two neighbors and the blank-line spacing between entries untouched.
- **Delete its roll-up clause.** The `grounding:` bullet under "Current quality/accuracy-impacting items" in `### Quality/accuracy lens (cross-cutting)` names #206 with a parenthetical between the `#82` and `#208` clauses. Remove the clause and its parenthetical, and leave the remaining list reading as a clean sentence — no doubled comma, no stranded "and".
- **File no stub.** The one thing #206 asked for that is not shipping is the intent-vs-`## Why` agreement check, and that is permanently refused, not deferred. A stub entry for it is the "prose that still argues for the thing you removed" defect `CLAUDE.md` § "Documentation is forward-looking" names under delete-on-sight.
- **Sweep the vocabulary, not only the number.** After the two deletions, `\b206\b` has no hits left in `BACKLOG.md`; also read for any other entry still describing `Step` as carrying no why or step-level intent as unbuilt. None is known at HEAD, so the expected result is a no-op check, and recording that it was run is the point.

### File the entries the earlier steps routed out of scope

Six steps defer an item to a backlog file and none of them can write one — every such step's footprint is code. This step owns all of them, which is why it declares both backlog files. **A routed item that no step files is a deferral that silently evaporates**, and two of these are accuracy regressions this plan itself ships:

- **step 6** — `RUNBOOK.md`'s self-consistency walkthrough still names `concept-coverage` as the blocking example and should name the intent finding too. Goes to `BACKLOG.md`. (`_sc_manual_fix_note` needs no entry: an intent is fixed by a manual plan edit, so its wording stays true.)
- **step 1** — the placeholder-vocabulary divergence above, to `BUG_BACKLOG.md`.
- **steps 5 and 7** — file whatever each step's `## Deferred` routes at the time this step runs; read them rather than trusting this list, since a later audit round can add one.

Use `BACKLOG.md`'s decision rule to pick the file: what the code does *wrong* goes to `BUG_BACKLOG.md`, forward-looking work to `BACKLOG.md`. Each entry carries the scope contract that file requires. Do **not** file the permanently-refused agreement check — see below.

### Keep #212 open, with its blocker cleared

- Its `- **Dependencies:**` and `- **Status:**` lines both say it is blocked on `2-intent-scope-fence.md` step 1 shipping the field. That field shipped, so both are stale. Rewrite them to read as open and ready — the blocker is clear, the entry is not started.
- Its `Out of scope / Non-goals` cites `CLAUDE.md` § "Withdrawn: the per-`change_type` test-ordering contract" as the durable record of the refused agreement check. Once the new record exists, re-point that citation at it so the refusal and its record sit in one place. This is a citation fix inside an entry this step already edits, not a scope change.
- Do not discharge or absorb #212. This plan fills an **absent** intent; #212 clears a **stale** one on `apply_finding`'s rewrite path.

### Write the record in CLAUDE.md

What must be true: a reader with only `CLAUDE.md` open can tell **what was reversed, on whose authority, when, and what stayed refused** — enough to stop a re-litigation — and can follow a citation for the full argument.

- **Record A (2026-07-31, explicit user decision).** `2-intent-scope-fence.md` widened #206: it shipped a plan-altitude `Plan.intent` that #206 non-goaled, and an advisory presence check #206 did not scope. #206's "required on existing plans" non-goal was **not** widened, and its duplication call — intent is a one-line seed the prompts consume, never re-checked against `## Why` — is kept.
- **Record B (2026-08-02, explicit user decision).** Exactly one bullet of that plan's "Not allowed" list is lifted — a gate, exit-code flip, or refusal-to-advance keyed on an intent — and **only for presence**. A missing intent now blocks completeness convergence. The exit-code convention is unchanged: a completed audit still exits 0 unless `--fail-on-findings`. The refusal's reason — a check firing on the whole corpus with no remedy trains operators to skim the channel — is **discharged** by this plan's authoring and proposer work, not overruled. Everything past presence stays permanently refused; a finding proposing one is invalid, not deferrable.
- **Say the ids are gone.** Close the record the way `## Withdrawn: the per-`change_type` test-ordering contract` closes its **Provenance.** paragraph — note that #206 was closed and deleted once discharged, and that this record is now the durable one, so cite it rather than the id. Naming #206 once here is deliberate: someone searching the number should land on the record.
- **Cite, don't copy.** `docs/implementation-plans/2-intent-scope-fence.md` (`## Scope guardrails`, `## Out of scope`) and `docs/implementation-plans/2-intent-required.md` (`## Architecture`) both stay on disk and hold the long form.

### Carve the section's own rules so they stay honest

`## Validating a semantic property you cannot observe` currently states two things the tool has now partly crossed for one observable: rule 2 ("Deliver, don't verify … Threading is the guard; checking is not") and rule 3's enumerated not-allowed list, which names a gate or exit-code flip. Left alone, they read as current design and argue against shipped behavior.

- **One way, and the one I'd recommend:** put the carve in the same block as the two records — gating the **binary observable** is allowed once the finding carries a remedy an operator can run; gating the **semantic property** stays refused — and add a short pointer clause on rule 3 so a reader hitting the enumeration finds the carve. One home for the fact, one pointer to it.
- **Do not rewrite each rule to hedge.** The rules earn their force by being flat; a carve stated once beside them keeps that.
- The closing **Provenance.** paragraph of that section names the intent scope fence carve (2026-08-01, eleven steps to five). It is still true and needs no edit beyond sitting beside the new record.

### Placement, and what was rejected

- **Recommended home: inside `## Validating a semantic property you cannot observe`,** as a short dated block after the numbered rules. Both records are about that section's own fences, and the carve has to be readable next to the rules it narrows.
- **Rejected — a new top-level section.** `CLAUDE.md` is injected into every session; a third H2 for a settled two-paragraph history costs every future run tokens and buys no reader value the existing section can't give.
- **Rejected — copying both records verbatim.** The plan files are durable (`2-intent-scope-fence.md` is `status: completed`) and are the long-form home. Verbatim copies are a second source that drifts.
- **Rejected — `LESSONS_LEARNED.md`.** It is a scoped session history of the iteration feature, it is not injected into sessions, and it is not a declared file here.

### Constraints that are not free to vary

- **Terse.** Two short paragraphs plus a clause. `CLAUDE.md`'s own rule is depth-in-the-pointed-at-doc.
- **Dated and framed as past.** Per `## Documentation is forward-looking`, warranted history must be marked as history and never left in present tense beside current design.
- **Do not weaken the surviving refusal.** The four not-allowed bullets above the lifted one stay refused in the same words they carry today.
- **Nothing else from #206 relocates.** Its design-call prose, effort estimate, and scope contract go with the entry; only the two reversals move.
- **Order matters.** This step is `depends_on: 9` and runs last, so the entry is removed only after the work it describes has shipped.

## Tests

This is a **non-code** step: `change_type: non-code`, and the plan's `enforce_step_tests: true` does not reach it — the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps. No test file is authored and none is expected. The checks below replace it.

### Verification (non-code step)

1. **Suite unchanged** — `uv run pytest tests/ -q` is green. Neither file is read at runtime, and no test asserts on their contents (the `BACKLOG.md` strings in `tests/test_review.py` are fixture text, not this file).
2. **Diff shape** — `git status --porcelain` lists exactly `BACKLOG.md` and `CLAUDE.md`.
3. **The id is gone from the backlog** — `rg -n '\b206\b' BACKLOG.md BUG_BACKLOG.md` returns nothing.
4. **The record is findable by id** — `rg -n '#206' CLAUDE.md` returns exactly the record's mention.
5. **Both dates present** — `rg -n '2026-07-31|2026-08-02' CLAUDE.md` matches inside the new block.
6. **Roll-up reads clean** — read the `grounding:` bullet in `### Quality/accuracy lens (cross-cutting)` end to end; it lists the remaining ids as a well-formed sentence with no doubled punctuation.
7. **Neighbors intact** — the `**#205 …**` and `**#208 …**` entries and the blank line between entries are unchanged.
8. **No re-filed refusal** — `rg -n 'agreement check' BACKLOG.md` returns only #212's refusal citation and #213's existing lines; no new entry proposes an intent-vs-work check.
9. **#212 still open and no longer blocked** — its entry is present, and its `Dependencies` / `Status` lines no longer say it waits on `2-intent-scope-fence.md` step 1.
10. **Standalone read** — read the new `CLAUDE.md` block cold, without opening either plan file, and confirm it answers: what was reversed, by whose decision, on what date, and what remains refused.
11. **Links resolve** — every path the record cites exists on disk at the stated path.

## Acceptance criteria

- `rg -n '\b206\b' BACKLOG.md` returns nothing; the entry and the roll-up clause are both gone.
- `rg -n '#206' CLAUDE.md` returns the record's single mention, framed as closed.
- `CLAUDE.md` states both reversals with their dates (2026-07-31 and 2026-08-02), names each as an explicit user decision, and names what each did **not** widen.
- `CLAUDE.md` states that gating intent **presence** is allowed and that everything past presence stays permanently refused.
- `CLAUDE.md`'s rules 2 and 3 in `## Validating a semantic property you cannot observe` no longer read as forbidding the shipped presence gate.
- `BACKLOG.md` contains no stub entry for an intent-vs-`## Why` agreement check.
- `#212` is present, reads as open and unblocked, and cites the new record for the refused agreement check.
- **Every `## Deferred` bullet across steps 1–7 that *unconditionally* routes an item to a backlog file has a corresponding entry** in `BACKLOG.md` or `BUG_BACKLOG.md` — checked by re-reading those seven `## Deferred` sections, not from the list in this step's Implementation, which can go stale as audit rounds add routed items. A bullet that routes *conditionally* ("… or `BACKLOG.md`", "file it **if** …") is closed by recording the decision in this step's notes, not by filing an entry.
- `BUG_BACKLOG.md` carries the placeholder-vocabulary divergence entry, with a scope contract.
- `git status --porcelain` lists exactly the three declared files.
- `uv run pytest tests/ -q` is green.

## Applicable guardrails

- **The plan's `## Out of scope`, "any validation past presence" (permanently refused).** This step writes the record *of* that refusal and must not soften it: the relocated text keeps the refusal absolute and must not reframe it as deferred or revisitable.
- **The plan's `## Out of scope`, BACKLOG #212.** #212 stays open here. This step may record that its blocker cleared; it may not discharge, absorb, or close it.
- **The plan's `## Architecture`, "Backlog reconciliation".** It is the source of this step's obligation: remove #206 only after the work ships, and preserve both reversals when it goes.
- **The plan's `## Architecture`, "Allowed reorganization: none".** No section of `CLAUDE.md` moves; the record is added inside an existing section.
- **The plan's `## Risks`, "Deleting #206 at closeout could delete the two reversal records with it".** This step's whole verification exists to make that risk observable rather than assumed.

## Deferred

- **`docs/implementation-plans/2-intent-scope-fence.md`** — it still says "Step 11 of the carved seed carries the obligation to preserve this record", which is this plan's step 8. Outside this step's declared files, and the obligation is discharged regardless of the stale number. Fix it by hand or route it to reconcile.
- **`plan-seeds/intent-scope-fence-carved-fill-the-plan-s-intent-from-through-11.md`** — the spent carved seed keeps several `#206` citations and a step-11 draft describing the pre-carve eleven-step arc. It is a consumed input, not a live doc, and is outside this step's files; archiving or sweeping it is separate work.
- **`docs/implementation-plans/2-intent-required.md`'s own status and step states** — plan-file bookkeeping belongs to `run` and the manifest, not to this step, and the plan file is not declared here.
- **Documenting the scope fence in `docs/RUN_FLOW.md` / `docs/DETAIL_FLOW.md`** — step 7 routed this to `BACKLOG.md` *if* someone decides the reader-need is real. Nobody has, so this step files no entry for it; if it is decided later it is an ordinary new entry, not part of the closeout.
- **BACKLOG #213** (the conceptual-audit lens for named observables) — it cites this class and both known instances, all still accurate; nothing about it goes stale here.
- **Clearing a stale intent on `apply_finding`** — BACKLOG #212, kept open by design.
