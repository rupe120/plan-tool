> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Delete `BACKLOG.md` #356, preserve the bounded authored-artifact follow-ups, restate #362 and the planning lanes, and update `CLAUDE.md`'s three format-doc bullets

## Summary

`BACKLOG.md` loses entry **#356** entirely, and every other line in that file that either points at it or advertises this plan as pending work is repaired in the same pass: **#362**'s thirteen `#356` citations, the `Next (idle plans)` lane cell, the `Authored plans` manifest row, and the Readiness lens's planning-plan count. The three bounded future records filed during this plan's restructuring — #363 for the first legacy-refusal operator route, #364 for version-contract drift coverage, and #365 for documentation and manifest discoverability — remain independent entries rather than disappearing with #356. The key decision is that **#362 is restated to stand on its own rather than re-pointed at a surviving stub** — its two verified code facts (the accepted-head digest binding and the `CanonicalSourceIdentity.format_version` name collision) are already written out in full in its own body, so removing the framing that treats it as #356's satellite costs no substance. `CLAUDE.md`'s three format-doc bullets — `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, `DATA_CONTRACT.md` — each gain a clause naming the version declaration that steps 2, 4, and 5 landed, staying at the one-or-two-line density that section uses. On green, `grep -n '#356' BACKLOG.md` returns nothing, no board or table lists this plan as next work, #362 reads as a self-contained deferred entry, the three bounded follow-ups remain available, and a future session reading `CLAUDE.md` learns that plans and run-grade detail files declare a format version.

## Table of Contents

- [Why](#why) — what goes stale the moment #356 is deleted, and why the sweep is the work
- [Input](#input) — what steps 2, 4, 5, and 6 landed that the `CLAUDE.md` clauses must describe
- [Files (creates vs edits)](#files-creates-vs-edits) — the two declared files and the edits in each
- [Implementation](#implementation) — the deletion, the three bounded records, the #362 restatement, the lane/table/count repairs, and the three bullet edits
- [Tests](#tests) — why the test-authoring gate does not fire, and the checks that replace it
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — the plan-level docs this step's edits rest on
- [Applicable guardrails](#applicable-guardrails) — which plan fences bind this step
- [Deferred](#deferred) — the `#356` mentions elsewhere in the repo that deliberately stay

## Why

`BACKLOG.md`'s own instructions say to remove a feature's entry when it ships, with history staying in git log and the plan file. Steps 1–6 discharge every line of #356's scope contract — both carriers, both readers, both writers, the `DATA_CONTRACT.md` registry, and the upgrade obligation — so the entry is now a document arguing for work that exists. Leaving it is the exact failure `CLAUDE.md` § "Documentation is forward-looking" describes: prose written in the present tense that a later reader, human or audit, acts on.

Deleting it alone is not enough, and that is the real content of this step. **#362 was written as #356's satellite**: it cites the id thirteen times, its heading says "carved from #356", one of its section headings is a contrast with #356's earlier draft, and its Dependencies, Out of scope, re-entry trigger, Origin, and Status all lean on the parent. A literal delete leaves the roadmap follow-up — the only tracked record of a real, verified hazard — pointing at nothing. Two more rows advertise this plan as pending: the `Next (idle plans)` lane and the `Authored plans` table, whose heading asserts every plan it lists is `status: planning`. That heading stops being true for this plan the moment `launcher.py:mark_done_and_advance` flips it to `PlanStatus.COMPLETED` on step 7's own green mark.

`CLAUDE.md` is injected into every session, so a stale contract claim there misleads future authoring runs even when the format docs themselves are right. Its `PLAN_FORMAT.md` bullet describes frontmatter and step conventions with no mention of a declared version; its `DETAIL_FORMAT.md` bullet describes the run-grade body with no mention of the marker; its `DATA_CONTRACT.md` bullet says "persisted/serialized runtime schemas", which is now an under-description of a doc that also holds the two authored-artifact version constants and their evolution rules.

## Input

This step describes what four sibling steps shipped. **Read the landed docs, not this file, for names and headings — where a name here disagrees with what is on disk, the landed name wins.**

- **Step 2** lands the plan class's declaration text in `PLAN_FORMAT.md`: the `format_version` entry in § "Frontmatter schema" / § "Field semantics", a new numbered rule under § "Validation rules", and the one-way bootstrap note.
- **Step 4** lands the run-grade detail marker's description in `DETAIL_FORMAT.md` — its fixed position as the first non-blank line after the H1, ahead of `Summary`, and the refusal an unsupported value gets. The marker belongs to the **run-grade** contract only; the jira-grade five-section contract is untouched.
- **Step 5** lands the authored-artifact version section in `DATA_CONTRACT.md` and widens that doc's § Scope paragraph, which today explicitly excludes the authored-artifact formats.
- **Step 6** lands the upgrade entry point per class and the coverage test holding the always-upgradable obligation — the last undischarged line of #356's scope contract, and the reason this step may delete the entry rather than trim it.

**What this step cannot verify:** nothing here is machine-checked. No test reads `CLAUDE.md` or `BACKLOG.md`, and `plan-tool validate` does not inspect either. The checks in [Tests](#tests) are reviewer-runnable greps and reads, and that is the whole verification surface.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `BACKLOG.md`
  - Delete entry **#356** in full, from its `**#356 — Authored plan and detail artifacts declare their format version**` heading through its `- **Status:**` bullet, including its `Iterate:` command block.
  - Restate **#362** so it carries no `#356` reference: its heading, **What**, the "Why this is not simply #356's roadmap steps, unmodified" heading and body, **Dependencies**, **Out of scope / Non-goals**, **Re-entry trigger**, **Origin**, and **Status**.
  - Retain the three bounded entries filed during this plan's restructuring: #363 (the first legacy-refusal operator route), #364 (completeness/registry drift coverage), and #365 (documentation and manifest discoverability). Their scope stays independent of #362 and of #356's shipped implementation.
  - Remove `authored-artifact-format-version` from the `Next (idle plans)` lane cell in § "Now / Next / Blocked / Parked (working set)".
  - Remove this plan's row from the `Authored plans` table under that same board.
  - Correct the planning-plan count in § "Readiness lens (concrete vs. theoretical)" under **Concrete (ready to implement)**.
- `CLAUDE.md` — three bullets in § "Reference docs": the `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `DATA_CONTRACT.md` lines.

## Implementation

### Enumerate before editing

Run both searches and keep the output beside you; the edits below are the answer to them, not a replacement for running them.

- **By identifier:** `grep -n '#356' BACKLOG.md` — 14 occurrences on 13 lines at HEAD: 1 is #356's own heading, 13 sit inside #362.
- **By vocabulary:** `grep -n 'authored-artifact-format-version\|authored-artifact\|Authored plan and detail artifacts' BACKLOG.md` — this is the pass that surfaces the lane cell and the manifest row, neither of which contains the id.

### Delete #356

Remove the entry whole. Do **not** leave a stub, a "shipped" marker, or a tombstone: the file's own § Purpose bullet routes shipped history to git log and the plan file, and `docs/HISTORICAL_BACKLOG_DECISIONS.md` is for closed *decisions* and retired composite records, not for delivered features — so this step deliberately writes nothing there.

### Preserve the three bounded follow-ups

Keep #363, #364, and #365 as independent records. They capture work this
version-1 plan deliberately does not pull forward: the first legacy-refusal
operator route, version-contract drift coverage in completeness and registry
metadata, and documentation/manifest discoverability. Do not merge any into
#362, reopen #362's design questions through them, or turn their future work
into a version-1 implementation requirement.

### Restate #362 so it stands alone

**The design decision: strip the framing, keep the substance, and add no new pointer that a later `sweep` can break.**

#362 already says of its two hazards that "Both are explained in full below so a session re-entering this later does not have to re-derive them" — and it delivers on that. The digest fact names `plan_tool/roadmap_versions.py` and `_require_content_matches_record` with its raised message; the collision fact names `plan_tool/roadmap_source_identity.py`, `BASELINE_FORMAT_VERSION`, and the `format_version` field on `BaselineRecord` and `CanonicalSourceIdentity`. Both are true at HEAD. So the restatement is subtraction, not research: remove the sentences whose only job was to position the entry against its parent, and leave every code fact and every design question untouched.

Site by site, with the shape each one needs:

- **Heading** — drop the `carved from #356` clause; keep `(deferred)`.
- **What** — the roadmap class is the third authored class with no in-band format version, beside the plan and run-grade detail classes that already have one. Name the shipped state, not the entry that requested it.
- **"Why this is not simply #356's roadmap steps, unmodified"** — this heading is the one that dies with its parent, because it contrasts against a draft that no longer exists anywhere. Retitle it to describe the hazard on its own terms (one way: "Why a declaration-only change is unsafe here"), and open the body with what a reader would otherwise try — a reader gate plus a matching writer stamp, structured like the plan and detail classes — rather than with whose plan once proposed it. **Both numbered facts stay verbatim in substance.**
- **Dependencies** — say the entry is independent of the shipped plan/detail format-version work. Drop "and already has".
- **Out of scope / Non-goals** — the clause reads "everything #356's Non-goals already exclude (…)" and the parenthetical already enumerates them, so deleting the citation and keeping the list loses nothing.
- **Re-entry trigger** — the trigger currently reads "not merely because #356 shipped", and instructs opening a fresh bare plan rather than resuming #356's. Reword to: the trigger is an actual breaking change to a staged roadmap artifact, and the entry gets a fresh bare plan of its own — never a resumed one. Keep all three design questions unchanged.
- **Origin** — keep the date and the user confirmation, drop the parent id. The handoff link already carried here is the right provenance anchor.
- **Status** — the "do not rerun or re-verify anything about #356's shipped plan/detail classes" sentence keeps its meaning once it names the shipped classes instead of the id.

**Do not anchor #362 on the live plan file path.** `plan_tool/sweep.py:archive_completed_plan` moves a completed plan into `docs/implementation-plans/archive/` (via `create.ARCHIVE_DIRNAME`), so `docs/implementation-plans/2-authored-artifact-format-version.md` is a path that moves out from under any link to it. The handoff citations #362 already carries are enough, and its self-contained body is what actually makes the entry survivable.

### Repair the lanes, the table, and the count

- **`Next (idle plans)` lane** — the cell lists several slugs joined by `·`. Remove this plan's `· authored-artifact-format-version (7)` segment and leave the rest of the cell alone. The row stays; other plans still occupy it.
- **`Authored plans` table** — delete this plan's row. That table's heading asserts every plan it lists is `status: planning`, which stops being true for this plan at the completion flip, so a row edited to say "shipped" would contradict the heading. Removal is the right shape.
- **Readiness lens count** — the **Concrete (ready to implement)** bullet ends "plus all eleven planning plans". **The number must be the count after this plan's completion flip, not the count visible while the step is running.** At HEAD, `grep -l '^status: planning' docs/implementation-plans/*.md` returns eleven files including this plan's; once `mark_done_and_advance` flips it, ten remain. Write **ten**. Re-derive it with that command rather than subtracting from memory.

### The three `CLAUDE.md` bullets

Keep each edit to a clause. That section is deliberately terse — depth lives in the pointed-at doc — so a migrated paragraph is the wrong answer even when it would be accurate.

- **`PLAN_FORMAT.md`** — add that the doc also owns the `format_version` declaration every plan carries and the refusal an unsupported value gets.
- **`DETAIL_FORMAT.md`** — attach the marker to the **run-grade half of the existing grade split**, not to the bullet as a whole; the jira-grade contract has no marker. **Leave both section counts at seven and five.** The marker is a comment line, not a section, so the run-grade seven-section contract and the jira-grade five-section contract are unchanged — this is the cardinality claim a reader would most plausibly assume moved, and it did not. The same holds for `docs/ARCHITECTURE.md`'s "run-grade seven-section `detail` response gate" phrase, which is correct as written and is not edited here.
- **`DATA_CONTRACT.md`** — the bullet's "persisted/serialized runtime schemas" description now under-describes the doc. Add that it also records the two authored-artifact format-version constants and their evolution rules, while `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` keep schema ownership — that boundary is the part a reader needs, because the obvious wrong reading is that `DATA_CONTRACT.md` took over the artifact formats.

Match each bullet's existing voice: a dash, then a fragment. Cite the enforcing symbol only where the sibling bullets already do (the `DATA_CONTRACT.md` bullet's `tests/test_data_contract.py` pointer stays; the two format bullets name docs, not code).

### Constraints that are not free to vary

- **Exactly three bounded backlog entries are retained, and no design work on #362 occurs.** #363, #364, and #365 carry the named future work this restructuring files; this step neither broadens their scope nor creates an unbounded fourth entry. The #362 restatement remains an edit to existing prose. Adding an effort estimate, answering one of its three design questions, or narrowing its re-entry trigger would reopen a deferred entry this plan carved out before it started.
- **#362's three design questions, its "Why deferring costs nothing right now" evidence, and both code facts keep their current meaning.** They are the entry's whole value.
- **Nothing in either file may claim that a reader checks an artifact's *content* against its declared version.** The shipped check reads the declared value and nothing else.
- **`BACKLOG.md` gains no version declaration of its own.** This step edits that file's content; the plan's fence puts versioning it out of scope.

## Tests

**The test-authoring gate does not apply to this step.** `plan_tool/launcher.py:_step_requires_test_authoring` fires only for `feature` and `refactor` steps; this step is `change_type: non-code`, so the gate never asks for a test file even though the plan sets `enforce_step_tests: true`. No test module in `tests/` reads `CLAUDE.md` or `BACKLOG.md` as a file, and `plan-tool validate` does not inspect either — so there is no drift guard to extend and none to break. The full suite is expected to stay green with zero test edits; a red test after this step means something outside the two declared files moved.

### Verification (non-code step)

1. **`grep -n '#356' BACKLOG.md` returns nothing.** The single mechanical check that the sweep is complete.
2. **`grep -n 'authored-artifact-format-version' BACKLOG.md`** returns no match inside § "Now / Next / Blocked / Parked (working set)" — neither in the `Next (idle plans)` lane cell nor in the `Authored plans` table.
3. **Read #363, #364, and #365.** Each must remain a bounded independent follow-up: none expands version 1, duplicates #362, or depends on #356 remaining present.
4. **Read #362 top to bottom as a stranger would.** It must be understandable with no knowledge that a parent entry ever existed: both code facts present, all three design questions present, the re-entry trigger stated without reference to another entry shipping.
5. **Verify #362's two code facts still hold at HEAD** — `grep -n '_require_content_matches_record' plan_tool/roadmap_versions.py` and `grep -n 'BASELINE_FORMAT_VERSION\|format_version' plan_tool/roadmap_source_identity.py`. The restatement carries these claims forward, so confirm rather than assume.
6. **Re-derive the planning-plan count** with `grep -l '^status: planning' docs/implementation-plans/*.md` and confirm the Readiness lens states the post-flip number, not the number visible mid-step.
7. **Confirm the `Next (idle plans)` cell still lists its other plans** and that no other lane row, tier list, or the Quality/accuracy lens rollup was touched.
8. **Diff `CLAUDE.md` and confirm exactly three bullets changed**, each still one or two lines, and that the run-grade seven-section and jira-grade five-section counts are unchanged in the `DETAIL_FORMAT.md` bullet.
9. **Confirm each `CLAUDE.md` clause matches what shipped** — open `PLAN_FORMAT.md`, `DETAIL_FORMAT.md`, and `DATA_CONTRACT.md` and check the clause against the landed text rather than against this file.
10. **Check no markdown link in either file points at a deleted anchor** — `grep -n '](#' BACKLOG.md` for in-file anchors, and confirm the deleted entry had no inbound link (it does not at HEAD).
11. **`git status` is clean apart from `BACKLOG.md` and `CLAUDE.md`.**

## Acceptance criteria

- `grep -n '#356' BACKLOG.md` returns no matches.
- `BACKLOG.md` contains no entry headed `**#356 — …**`, no stub in its place, and no new record in `docs/HISTORICAL_BACKLOG_DECISIONS.md`.
- `BACKLOG.md` #362 retains its heading, its two numbered code facts naming `plan_tool/roadmap_versions.py:_require_content_matches_record` and `plan_tool/roadmap_source_identity.py`'s `BASELINE_FORMAT_VERSION` / `CanonicalSourceIdentity.format_version`, its three re-entry design questions, its handoff citations, and its deferred status — with no reference to a deleted entry.
- `BACKLOG.md` retains #363, #364, and #365 as bounded independent records for the first legacy-refusal operator route, version-contract drift coverage, and documentation/manifest discoverability; none is represented as version-1 work or as a #362 design answer.
- The `Next (idle plans)` lane cell in § "Now / Next / Blocked / Parked (working set)" no longer names `authored-artifact-format-version`, and its other plans remain listed.
- The `Authored plans` table contains no row for `authored-artifact-format-version`.
- The § "Readiness lens" **Concrete** bullet states the number of `status: planning` plans that remain after this plan's completion flip, matching `grep -l '^status: planning' docs/implementation-plans/*.md` run after the flip.
- `CLAUDE.md`'s `PLAN_FORMAT.md` bullet names the plan `format_version` declaration and the unsupported-value refusal.
- `CLAUDE.md`'s `DETAIL_FORMAT.md` bullet names the run-grade format-version marker on the run-grade side of its existing grade split, and still states seven run-grade sections and five jira-grade sections.
- `CLAUDE.md`'s `DATA_CONTRACT.md` bullet names the two authored-artifact format-version constants and their evolution rules, and states that `PLAN_FORMAT.md` and `DETAIL_FORMAT.md` keep schema ownership.
- Exactly three `CLAUDE.md` bullets change; each stays within § "Reference docs" and within one or two lines.
- `uv run pytest tests/ -q -n auto` passes with no test file edited by this step.

## References

- `BACKLOG.md` #356 — the source entry this step deletes; its scope contract is the checklist steps 1–6 discharge, and its own § Purpose bullet ("Remove a feature's entry when it ships") is the rule this step follows.
- `BACKLOG.md` #362 — the deferred roadmap carve-out; read its two numbered code facts and three design questions before rewriting a word of it.
- `handoffs/2026-09-08-authored-artifact-structure-versioning.md` § "Roadmap staged artifacts — deferred" — the reasoning behind the carve-out, and the anchor #362 keeps citing.
- `PLAN_FORMAT.md` § "Frontmatter schema" / § "Validation rules" — what step 2 landed, and what the `CLAUDE.md` bullet must describe.
- `DETAIL_FORMAT.md` § Format and § "Section schema" — what step 4 landed, and the grade split the `CLAUDE.md` bullet already encodes.
- `DATA_CONTRACT.md` § Scope and its authored-artifact version section — what step 5 landed, and the ownership boundary the `CLAUDE.md` bullet must state.

## Applicable guardrails

- **The plan's "## Out of scope", roadmap staged artifacts.** This step may restate #362's prose so it stands alone; it must not answer any of #362's design questions, estimate its effort, change its re-entry trigger, or touch `plan_tool/roadmap_artifacts.py`, `plan_tool/roadmap_versions.py`, or `plan_tool/roadmap_source_identity.py`.
- **The plan's "## Out of scope", versioning `BACKLOG.md` / `plan-seeds/` / jira exports.** This step edits `BACKLOG.md`'s content only; it must not give that file a version declaration of its own.
- **The plan's "## Scope guardrails", the single binary observable and its not-allowed list.** Neither file may describe the shipped check as validating an artifact's content against its declared version, as upgrading on read, or as emitting an advisory about a supported version.
- **The plan's "## Deferred", named candidates.** The detail grade, seed and jira-export versioning, and the concrete v1-to-v2 conversion stay unmentioned in the `CLAUDE.md` bullets as shipped behavior.
- **The step's own intent — documentation only.** No production code or test; its only backlog work is retaining the three bounded future entries already filed during this plan's restructuring.

## Deferred

- **`#356` mentions in the plan and its detail files** (`docs/implementation-plans/2-authored-artifact-format-version.md` § References and § Deferred, and the References/Deferred sections of details 01, 03, 04, 05, 06) — these stay. They are dated provenance for the shipped work, they name the entry that authorized it, and neither the plan nor a sibling detail file is this step's to edit.
- **`#356` mentions in the saved audit reports** under `docs/implementation-plans/plan-details/authored-artifact-format-version/reports/` — immutable evidence of what each audit saw; never edited.
- **`plan-seeds/archive/authored-artifact-format-version.replaced.md`** — an archived seed generation, kept as-is for the same reason.
- **`handoffs/2026-09-08-authored-artifact-structure-versioning.md` and its entry in `handoffs/README.md`** — the handoff is a dated design-session record whose citation of the id is accurate as history. Retiring it from the README's current-pickup list once this plan ships is a handoff-lifecycle decision, made through that file's own § "consolidation record" convention, and both files sit outside this step's declared file list.
- **The `Authored plans` table's missing row for `roadmap-source-baseline-recovery`** — a pre-existing gap between that table and the eleven `status: planning` plans on disk. This step corrects the count claim it falsifies and adds no row; #365 owns the later manifest reconciliation.
- **`docs/ARCHITECTURE.md` has no entry for `plan_tool/detail_artifacts.py`** — a pre-existing description gap that steps 3 and 6 widen by giving that module the detail version contract and upgrader. The file is not in this step's declared list; #365 owns the later documentation reconciliation.
- **A drift guard over `CLAUDE.md`'s reference-docs bullets** — nothing machine-checks them today, and minting one is a new checking mechanism this plan's scope fence does not carry. #365 decides whether a bounded guard is worthwhile after its documentation sweep.
