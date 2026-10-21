> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Reconcile BACKLOG #208 and sweep every document that still describes re-entry as regeneration

## Summary

Close the loop on `BACKLOG.md` #208: mark arc position 02 shipped, delete the present-tense defect prose that this plan discharges, and repair the cross-references the arc's renumbering broke. Then sweep the two project documents that still describe a `--from-stage N` re-entry as regeneration — `CLAUDE.md`'s roadmap architecture paragraph (which also carries two counts steps 1 and 2 change) and `integrations/claude/SKILL.md`'s two roadmap rows, which tell an agent to edit the top artifact in place and never re-run. The key design decision: **`integrations/claude/SKILL.md` is added to this step's file list** — step 8's Deferred surfaced it as a scope decision because no step declares it, and the alternative (a backlog entry) leaves the repo's own agent-facing catalog telling agents to avoid the feature this plan just shipped. On green, no document in the tree describes the roadmap verb regenerating over a reviewer's artifact, no count in `CLAUDE.md` disagrees with `plan_tool/roadmap_gates.py`, and every follow-up this plan deferred exists as a backlog entry.

## Table of Contents

- [Summary](#summary) — what the sweep closes and where it reaches.
- [Why](#why) — the ship falsifies prose in three files, and one of them steers agents away from the feature.
- [Input](#input) — what steps 8 and 9 land, what this step reads off code, and what it must not touch.
- [Files (creates vs edits)](#files-creates-vs-edits) — three edits, one of them an addition to the declared list.
- [Implementation](#implementation) — the edit sites per file, the counts read off code, and the settled decisions that stay.
- [Verification (non-code step)](#verification-non-code-step) — the greppable checks that stand in for tests.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — the docs bearing on the swept claims.
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step's prose.
- [Deferred](#deferred) — what this step deliberately leaves alone.

## Why

Steps 1–9 change facts that four documents state in the present tense, and until this step runs they all read as current design.

- **`BACKLOG.md` #208 argues for building what now ships.** Its arc bullet for position 02 says `--from-stage N` "re-proposes from the original brief, discarding both the previous proposal and any comment on it," and its Framing bullet says "there is no feedback path" and the collaborative Outcome is "currently unimplementable." Its `Status:` bullet records only position 01 and predicts that "position 02 adds a stage with more gates" — position 02 added no stage.
- **The roadmap architecture paragraph moved to `docs/ARCHITECTURE.md` on 2026-08-04** (CLAUDE.md was split: normative rules stayed, the descriptive module inventory moved out). The paragraph is the same text at a new path — sweep it there. It names "the four closed vocabularies" and "the eight relation gates"; step 1 adds two vocabularies and step 2 adds three gates. It also lists "the feedback channel" among the "later, unauthored arc positions."
- **`CLAUDE.md` keeps one site and is injected into every session, so a stale count there misleads every future authoring run:** its `ROADMAP_FORMAT.md` bullet in `## Reference docs` repeats the gate count.
- **`integrations/claude/SKILL.md` tells an agent not to use the feature.** Its decision-tree row says to re-run `--from-stage N` "only to regenerate what is downstream of that edit," and its at-a-glance Roadmap row says to "edit `02-constraints.md` in place and don't re-run (any re-entry overwrites it)." That was correct advice; after step 6 it steers an agent away from the supported loop. Step 8's Deferred found this and routed the decision here.
- **Inserting position 02 into the arc renumbered the positions below it, and one inbound citation was never swept.** `BACKLOG.md` #222 cites the framework-lens machinery as "#208 arc position 04"; #208's own arc list names `roadmap-05-framework-lenses` at position 5. The same entry twice cites "#208's Phase B", a name #208 no longer defines.

## Input

This step reads what two sibling steps land and what the code says at the time of the edit. It writes no code and reads no new contract.

- **Step 8 lands the operator-facing docs.** `ROADMAP_FORMAT.md`, `RUNBOOK.md`, `USE_CASES.md`, and `CAPABILITIES.md` describe the lifecycle, the targets, and the review loop after step 8. Those four files are **step 8's**, not this step's — a corrected claim in one of them is evidence the sweep is done, never a site to re-edit.
- **Step 9 lands the real-run evidence in `BACKLOG.md`.** Step 9 adds a dated exercise bullet under #208 and a revision-mode sample under #215, and its detail explicitly reserves #208's `Status:` field and its Framing prose for this step. Cite step 9's bullet where the reconciliation needs evidence; do not restate its numbers, and do not move or reword its block.
- **The counts come off the modules, not out of this file.** The vocabulary count is the number of closed vocabularies `plan_tool/roadmap_artifacts.py` owns (today `DecisionStatus`, `FieldType`, `ConstraintDisposition`, and `QUALITY_ATTRIBUTES`); the gate count is the number of `check_*` functions in `plan_tool/roadmap_gates.py` reachable through `DOMAIN_GATES` / `CONSTRAINTS_GATES`. Count them at HEAD when making the edit. A number written into this detail while steps 1–2 were still being planned is a proposal; the landed code wins.
- **Position 01's records are the shape to copy.** #208's `Status:` bullet already records a shipped position as: what is live, where the contract and operator workflow live, and provenance (plan path, step count, authoring date, seed archive location). Position 02's entry takes the same shape.
- **What this step cannot check.** Nothing in the repo diffs `BACKLOG.md` or `CLAUDE.md` against code — `plan_tool/capability_catalog.py:check_capabilities` covers `CAPABILITIES.md` only, and `tests/cli/test_cli_reference.py` covers `docs/cli/`. Every claim this step corrects stays correct only by hand, so the verification below is greps a reviewer runs, not a suite.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — four edits inside **#208** (the arc bullet for position 02, the Framing bullet's discharged-defect paragraph, the id-stability paragraph's forward instruction, and the `Status:` bullet), one bullet in **#215**, and two citations in **#222**.
  - `docs/ARCHITECTURE.md` — the `**Roadmap (…)**` paragraph.
  - `CLAUDE.md` — one site: the `ROADMAP_FORMAT.md` bullet in `## Reference docs`.
  - `integrations/claude/SKILL.md` — **an addition to the step's declared `files:` list, noted here deliberately.** Two table rows: the project-sized-concept row under `## Decision tree for common user asks`, and the **Roadmap** row under `## Subcommands at a glance`.

**On the addition.** Step 8's Deferred raised this as a scope decision with two options — add the file to step 10, or file a `BACKLOG.md` entry. Add it. The step's own intent is that no project document describes re-entry regeneration, and `integrations/claude/SKILL.md` is the catalog an agent session reads before driving the verb, so leaving it is the one stale site guaranteed to be acted on. The edit is two table rows in a non-code file, which keeps the step's `low` complexity honest. The path is declared in the step's `files:` list in the plan frontmatter, which is what keeps it from reading downstream as an undeclared write (`plan_tool/detail.py:extract_path_mentions` matches it, since it carries a slash). No other integration needs the sweep — `integrations/codex/` and `integrations/cursor/` mention the roadmap verb nowhere.

## Implementation

### `BACKLOG.md` #208 — four edits

The governing rule is the repo's forward-looking documentation directive: a former state is **deleted**, not archived in place, unless a reader needs it to act correctly. Measurements and settled decisions stay and keep their dates; defect descriptions that this plan discharges go.

1. **The stage-arc bullet for position 02.** Today the whole bullet argues the defect — what `_render_stage_prompt` takes, what `_corrections_block` is wired to, and that hand-editing is the only correction. The arc list's contract is one line per position: the deliverable, and the tool state it leaves behind (position 01's bullet is the model — "Leaves: a repo can produce gated `01-domain.md` / `02-constraints.md`"). Rewrite position 02's bullet to that shape. Drop **"and the next position"** — position 03 is next now.
2. **The Framing bullet's discharged-defect paragraph.** The paragraph headed "The defect this framing exposes, which is now position 02" is entirely present-tense description of what step 5 and step 6 fixed: no feedback path, `_render_stage_prompt`'s inputs, `_corrections_block` wired only to gate violations, "currently unimplementable," hand-editing as the only correction. None of the four warranted-history cases applies — it is not a don't-reopen decision, a don't-repeat failure, a live legacy contract, or provenance for a claim. Delete it and replace it with one sentence naming what shipped, pointing at the `Status:` bullet for detail. **The rest of the Framing bullet does not move**: the collaborate-don't-replace decision, the 2026-08-01 measurement and its reversal, and the "do not re-cut on one-shot-quality grounds" fence are settled, user-confirmed, and dated.
3. **The id-stability paragraph's forward instruction.** The 85/60/30/25 measurement is provenance — keep it, dated 2026-08-02, framed as past. What goes is the tail that is now false or discharged: that feedback "does not survive the re-proposal it is feedback on," that "today feedback is durable only when edited in place and the stage is never re-run," and that "Position 02 has to solve this." Replace with what the shipped guarantee is — a predecessor feedback row's id, target, and request survive a revision — and cite step 9's exercise bullet for the re-measured continuity observation. Do not restate step 9's numbers here; one authority, no drift.
4. **The `Status:` bullet.** Three changes:
   - Add a position-02 record in position 01's shape. Name what is live (a stage re-run over its own artifact revises it against the predecessor and the reviewer's open feedback; feedback lifecycle is human-closed), where the contract lives (`ROADMAP_FORMAT.md`, per step 8), and provenance — plan path `docs/implementation-plans/2-roadmap-02-feedback-channel.md`, its step count, and its authoring date. **Check the seed before claiming one**: there is no `plan-seeds/roadmap-02-feedback-channel.md` and no archived copy at HEAD, so either archive the seed if one exists by then or say the position was authored without one. Do not copy position 01's "seed archived at …" clause blind.
   - Correct "Arc positions **02–04** stay unauthored" → 03–05, matching the arc list's five entries.
   - Retire the two discharged forward instructions: "Read **#215** before authoring arc position 02" (re-point at 03, which is where the extra gates actually arrive) and the prediction that "position 02 adds a stage with more gates" — it added three gates to the existing two stages and no new stage. State what it added, or drop the clause.

**One authority for the arc.** The ordered-efforts convention says the anchor entry carries the arc and every other entry cites it. Keep all five arc facts inside #208; do not seed a second copy in #215 or #222.

### `BACKLOG.md` #215 and #222 — bounded citation repairs

These are cross-reference repairs, not re-decisions. Neither entry's status, decision, or scope contract changes.

- **#215's "Why it gets sharper with a third stage" bullet** carries a gate condition on a shipped position: "so settling this is cheaper before arc position 02 than after." That is exactly the delete-on-sight case — a condition on something that no longer exists ahead of it. Re-point the timing at position 03, which is the next stage-adding position. The same bullet says "the constraints stage carries **six** rules"; on a revision it carries those six plus step 2's three predecessor gates, which is the pressure this plan's Risks section flags. Correct the count with the revision case named. **Do not resolve #215, do not change `MAX_STAGE_ATTEMPTS`, and do not restate step 9's appended sample** — step 9 owns that block and the entry stays open.
- **#222's two "#208's Phase B" citations** (its `Dependencies:` and `Status:` bullets) name something #208 does not define. The question Phase B stood for — does the arc continue, and under what Outcome — is settled in #208's Framing bullet, 2026-08-02. Re-point both citations there. Same bullet: "#208 specifies it as arc position 04" is off by one — #208's arc list names `roadmap-05-framework-lenses` at position 5, and the drift comes from #222 being written against the arc numbering before position 02 was inserted. Correct to 05.

### `docs/ARCHITECTURE.md` and `CLAUDE.md` — clause updates, not a rewritten paragraph

`docs/ARCHITECTURE.md` holds the roadmap paragraph; `CLAUDE.md` (injected into every session, deliberately terse) keeps only the reference bullet. Every edit below is a clause; none is a new paragraph, and neither file gains a roadmap section.

In the `**Roadmap (`plan_tool/roadmap.py`, …)**` paragraph under `## Architecture`:

- **The vocabulary count** — "the four closed vocabularies" → the number `plan_tool/roadmap_artifacts.py` owns after step 1. Count them in the module.
- **The gate count** — "the eight relation gates" → the number of `check_*` functions in `plan_tool/roadmap_gates.py` after step 2. Count them in the module. The rest of that clause ("which *return* `Violation`s and never raise") stays true.
- **The re-entry sentence** — "rewrites everything from `N` up" is still true of the file, and now incomplete about what happens to its content. Add the revision clause: a stage whose artifact already exists revises that artifact against it and the reviewer's `open` feedback instead of re-authoring from the brief. Keep the "**Disk is the interface between stages**" framing intact — step 5 loads the predecessor from disk, which strengthens rather than contradicts it.
- **The arc sentence** — drop "the feedback channel" from the list of "later, unauthored arc positions," and record position 02 as shipped beside position 01. The components, plan-derivation, and framework-lens positions stay in the unauthored list.
- **The review-channel clause** — "`pending` is the review channel (edit the artifact, re-enter at `--from-stage N`)" now describes one of two channels. Add `awaiting-review` feedback as the second, in one clause. **"Non-interactive by construction — no confirm, no `-y`, no TTY branch" stays exactly as written**: step 7 adds a printed advisory block and no branch.

In `## Reference docs`, the `ROADMAP_FORMAT.md` bullet repeats "**relations** (the eight gates)" — same count fix, same source.

**Verified non-edits in the same paragraph, worth confirming rather than assuming.** Each is a claim a reader would expect this plan to have broken, and none of them changed:

- **"A stage is a row of data, not a branch"** and the `RoadmapStage` tuple `(prompt file, artifact path, parser, renderer, gate set)` — steps 4, 5, and 6 each state they add no stage-table field, and the revision wrapper is shared rather than per-stage. Confirm with `rg 'stage\.(name|number) ==' plan_tool/roadmap.py` returning nothing before leaving the sentence alone.
- **The four-module one-way import line** — this plan adds no module and no import edge.
- **The exit-code sentences** (1 for an exhausted stage, 2 for a pre-flight failure, 0 for a completed run) — step 5 adds pre-flight failure cases but no new exit code, and step 7 states the count never touches the exit code. **The exit codes are the non-edit; the enumerations beside them are not** — neither the failure-kind count nor the exit-2 pre-flight cause list (`unusable slug, unreadable brief, out-of-range --from-stage, an upstream artifact malformed or failing its own gates`), which step 5 extends with an unreadable predecessor, duplicate predecessor feedback ids, and an unresolvable feedback target. See the edit site below.
- **"The verb collaborates … never justified or measured as a replacement for human authorship"** — this is the settled Framing decision that motivated the whole plan. It stays verbatim.
- **`docs/cli/roadmap.md`** — generated from argparse and drift-guarded by `tests/cli/test_cli_reference.py`. This plan adds no flag and changes no help string, so it needs no regeneration. Confirm by reading the file rather than regenerating.

**The failure-kind count is an edit site in both documents.** Step 6 adds a fourth rejection kind, which falsifies two enumerations a reader would otherwise trust:

- `docs/ARCHITECTURE.md`'s roadmap paragraph: "a stage that spends its `MAX_STAGE_ATTEMPTS` budget on any of its **three** failure kinds (invoke, parse, gates)". Widen to four and name the new kind. (`CLAUDE.md` carries the same three-kind list inside a *dated 2026-08-04 audit lesson* under check 4 — that is warranted history describing a past reasoning error, so leave it and do not widen it.)
- `integrations/claude/SKILL.md`'s Roadmap row enumerates the same three in prose — "**1** when a stage spends its retry budget (whether the backend failed, the reply was unparseable, or gates rejected it)". Add the fourth clause. The exit code itself is unchanged, which is why this is easy to miss.

### `integrations/claude/SKILL.md` — two rows

Both rows tell an agent the opposite of what now ships. Correct the advice; do not expand either row into a walkthrough — `RUNBOOK.md` owns the operator loop (step 8), and this file cross-links rather than restates.

- **The `## Decision tree for common user asks` row** ("I have a project-sized concept, not a single feature") ends with "re-run with `--from-stage N` only to regenerate what is downstream of that edit, since `N` and everything above it is rewritten." Replace the regeneration framing: writing feedback into an artifact and re-entering at that artifact's own stage is the supported loop. Everything else in the row — seed emission being a later unbuilt position, `pending` decisions being reviewed by editing in place — stays.
- **The `## Subcommands at a glance` **Roadmap** row** carries the sharpest version: "edit `02-constraints.md` in place and don't re-run (any re-entry overwrites it)." Replace it with the loop as shipped. Keep the row's other facts — the two artifacts, the gate-retry behavior, the two non-zero exits, non-interactive, writes no plan and no manifest entry — and update the two-artifact and non-interactive claims only if reading them against HEAD shows they moved (they should not have).

### Filing this plan's new deferrals

The plan's acceptance criteria require that "any newly created deferral is filed explicitly." Sweep the ten detail files' `## Deferred` sections plus the plan's own `## Deferred` for anything routed to `BACKLOG.md` or `BUG_BACKLOG.md`, and confirm each has an entry or write one. The plan-level list names five: a generic interactive feedback framework and review walk, cross-artifact propagation, optimistic conflict handling for in-flight edits, automatic semantic evaluation or a done-ness verdict, and #215's retry-budget calibration — the last already exists as an entry, so it needs a citation, not a new one. Anything the detail files routed out (a consolidation, a rework, a measurement) follows `BACKLOG.md`'s own decision rule for which file it lands in, and inherits the scope-contract shape that file requires. A follow-up recorded only in a `.tmp/` note is not filed.

## Verification (non-code step)

This step is `change_type: non-code`. The plan sets `enforce_step_tests: true`, and the test-authoring gate does not apply here — it keys on `change_type` and fires only for `feature` and `refactor` steps (`plan_tool/launcher.py`'s `_step_requires_test_authoring`). The substitute is a list of checks a reviewer runs against the finished tree:

1. **no-stale-counts** — the vocabulary and gate counts in `docs/ARCHITECTURE.md`'s roadmap paragraph and in `CLAUDE.md`'s `ROADMAP_FORMAT.md` reference bullet match what `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` actually ship. Count the modules; do not trust the prose.
2. **no-regeneration-advice** — `rg -in "don't re-run|no re-run at all|only to regenerate" integrations/claude/SKILL.md RUNBOOK.md USE_CASES.md CLAUDE.md` returns nothing about the roadmap verb.
3. **no-discharged-defect-prose** — `rg -nU "no\s+feedback path|is currently\s+unimplementable|Position 02 has to solve" BACKLOG.md` returns nothing. `rg` is line-oriented by default and #208's Framing bullet wraps two of these across lines ("There is no / feedback path", "is currently / unimplementable"), so the un-anchored single-line form matches only the third alternative and would pass at HEAD.
4. **arc-numbering** — `rg -n "arc position 0[0-9]" BACKLOG.md`; every hit agrees with #208's five-entry arc list.
5. **no-dangling-phase-b** — `rg -n "#208\*{0,2}'?s? Phase B" BACKLOG.md` returns nothing. **Derive every sweep pattern from the text as it actually sits in the file, and confirm each one *matches at HEAD* before you start** — a pattern that never matched returns nothing whether or not the edit landed, so it certifies the sweep it was meant to verify. The two citations here are written `**#208**'s Phase B` (#222's `Dependencies:`) and `#208 Phase B` (#222's `Status:`); the literal `#208's Phase B` matches neither.
6. **position-02-recorded** — #208's `Status:` bullet names position 02 as shipped with a provenance path that exists on disk.
7. **step-9-block-untouched** — `git diff` shows no change inside step 9's exercise bullet or its #215 sample.
8. **position-01-plan-untouched** — `git status` shows no change to `docs/implementation-plans/2-roadmap-01-domain-constraints.md` or its detail bundle.
9. **deferrals-filed** — every `BACKLOG.md`/`BUG_BACKLOG.md` routing in this plan's ten detail files and its own `## Deferred` resolves to a real entry.
10. **footprint** — the commit touches exactly `BACKLOG.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`, and `integrations/claude/SKILL.md`.
11. **no-code-regression** — `uv run pytest tests/ -q` is green (a no-code step should not move it) and `plan-tool validate` still passes.
12. **links resolve** — every path and entry id cited in the edited prose exists: the plan path, `ROADMAP_FORMAT.md`, and the `#215` / `#222` / `#208` anchors.

## Acceptance criteria

- `BACKLOG.md` #208's `Status:` bullet records arc position 02 as shipped, in the same shape as position 01, and its unauthored-positions range starts at 03.
- #208 contains no present-tense statement that the roadmap verb has no feedback path, re-proposes from the brief discarding the prior artifact, or leaves hand-editing as the only correction.
- #208's Framing bullet keeps its collaborate-don't-replace decision, its 2026-08-01 measurement and reversal, and its "do not re-cut" fence unchanged; only the discharged-defect paragraph and the id-stability paragraph's forward instruction change.
- #208 retires both discharged forward instructions in its `Status:` bullet — the read-#215-before-position-02 pointer and the "position 02 adds a stage" prediction.
- `rg -n "#208\*{0,2}'?s? Phase B" BACKLOG.md` returns nothing — a pattern verified to match both citations at HEAD before the edit — and #222 cites the framework-lens machinery at the position #208's arc list actually assigns it.
- #215's timing bullet no longer conditions on "before arc position 02", its rule count reflects the revision case, and its status, budget constant, and step 9 sample are unchanged.
- `docs/ARCHITECTURE.md`'s roadmap paragraph and `CLAUDE.md`'s `ROADMAP_FORMAT.md` reference bullet both state vocabulary and gate counts equal to what `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` ship.
- `docs/ARCHITECTURE.md` no longer lists the feedback channel among unauthored arc positions, and its re-entry sentence says a stage with an existing artifact revises rather than re-authors.
- `CLAUDE.md` still states "A stage is a row of data, not a branch" with the unchanged `RoadmapStage` tuple, "Non-interactive by construction", the four-module import line, and the collaborates sentence.
- Neither of `integrations/claude/SKILL.md`'s two roadmap rows tells the reader to edit an artifact in place and not re-run, or to re-run only to regenerate downstream artifacts.
- `integrations/claude/SKILL.md` appears in step 10's `files:` list in the plan frontmatter.
- Every follow-up this plan defers exists as a `BACKLOG.md` or `BUG_BACKLOG.md` entry, or cites an existing one.
- The commit touches exactly `BACKLOG.md`, `docs/ARCHITECTURE.md`, `CLAUDE.md`, and `integrations/claude/SKILL.md`; `uv run pytest tests/ -q -n auto` is green apart from the six pre-existing `test_cli.py` failures recorded in `BUG_BACKLOG.md`.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — the frontmatter grammar behind any lifecycle or removal example quoted into the swept prose; keep quoted snippets parseable.
- [Long context prompting tips — Claude Docs](https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — why the revision prompt delimits the prior artifact and the active feedback, which is the behavior `CLAUDE.md`'s corrected re-entry clause summarizes in one sentence.

## Applicable guardrails

- **The plan's "## Out of scope", no TTY walk / no new command** — the swept prose describes the loop as it ships: edit the artifact, re-enter at its stage. Do not let a corrected `integrations/claude/SKILL.md` row or `CLAUDE.md` clause imply a confirm, a review walk, or a feedback subcommand.
- **The plan's "## Out of scope", cross-artifact propagation** — where the sweep describes where feedback applies, keep it local to the artifact that carries it. Do not write prose suggesting an instruction in one artifact reaches another.
- **The plan's "## Out of scope", no judging whether feedback was honored** — the reconciliation records that the loop exists and what one exercise observed. It must not describe the tool as scoring, verifying, or closing feedback.
- **The plan's "## Out of scope", no caps on feedback** — do not introduce length, count, or shape guidance for a feedback request while rewriting a row that discusses prompt pressure.
- **The step's intent, no widening past the sweep** — this step corrects claims. It changes no behavior, no code, and no other step's declared files.
- **#208's "The shipped position-01 plan is deliberately left alone"** — a settled, dated, user-confirmed decision inside the entry being reconciled. `docs/implementation-plans/2-roadmap-01-domain-constraints.md` and its detail bundle name the later positions under their old numbering; that is an execution record, and retro-editing it is the code-canonical hazard the repo warns about. The arc-numbering repair stops at the backlog and does not reach into that plan.

## Deferred

- **`ROADMAP_FORMAT.md`, `RUNBOOK.md`, `USE_CASES.md`, and `CAPABILITIES.md`** — step 8's files. This step reads them as evidence and edits none.
- **`plan_tool/cli/roadmap_cmd.py`'s overwrite advice and its module docstring** — the printed "copy it aside first if you edited it by hand" line and the in-code comment warning never to re-enter at the edited stage are code, and step 7 owns them. A non-code step does not touch either.
- **Step 9's exercise bullet and its #215 sample** — step 9 writes the evidence; this step cites it.
- **Resolving `BACKLOG.md` #215** — the retry-budget decision stays open and needs a second brief per its own Risks bullet. This step corrects two stale claims in its prose and nothing else.
- **Resolving `BACKLOG.md` #222** — the data-interface-lens decision stays open. This step repairs its citations to #208 and does not touch its decision or its scope contract.
- **`docs/cli/roadmap.md`** — argparse-generated and drift-guarded; no flag or help string changes in this plan, so no regeneration.
- **`integrations/codex/` and `integrations/cursor/`** — neither mentions the roadmap verb, so the sweep is one integration file.
- **Arc positions 03–05 (`roadmap-03-components`, `roadmap-04-plan-derivation`, `roadmap-05-framework-lenses`)** — their seeds stay unauthored per the ordered-efforts convention. This step records them as unauthored; it does not author or re-scope them.
- **Any new claim about whether feedback improved a proposal** — the plan's Stop/defer rule makes that the arc's own test, on evidence larger than n=1. The reconciliation records the exercise happened; it draws no conclusion.

## Tests

This step is `change_type: non-code` and changes no production code. The plan's `enforce_step_tests: true` gate keys on `change_type` and fires only for `feature` / `refactor` steps, so it does not apply here. The substitute checks are the twelve greppable assertions in this file's [`## Verification (non-code step)`](#verification-non-code-step) section above, and they are what a reviewer runs.

