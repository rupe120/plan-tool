> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Run the one-off mechanism falsification check and commit the recorded finding-set comparison

## Summary

Run one recorded observation comparing both depths' finding sets across one scoped change to a real plan, and commit it as `docs/jira-grade-falsification-check.md` plus an outcome-routing edit to `BACKLOG.md`. **This detail is deliberately authored at reduced grade.** The instruments this step drives are steps 7 and 4, which do not exist when this file is written; their flag spellings, battery selection, and report provenance are predictions until they land. The instrument-dependent *mechanics* of the reading are therefore authored **at execution time, against the merged code** — not predicted here (see [Deferred](#deferred)). What the three readings **are** is not deferred: the plan body's "Mechanism falsification check" declares all three in advance and forbids a fourth, and this step is bound by that — the executor applies those readings, it does not re-decide them. What must be true on green: a committed record exists, it applies the plan body's predeclared readings, its reading rule was written before its evidence, and the outcome gates nothing.

## Table of Contents

- [Summary](#summary) — what the check does, and why this file is short on purpose
- [Why](#why) — why the mechanism claim needs one recorded observation now
- [Input](#input) — the two unbuilt steps this drives, and the one durable constraint
- [Files (creates vs edits)](#files-creates-vs-edits) — the record doc and the one backlog edit
- [Implementation](#implementation) — the four commitments that survive not knowing the instruments
- [Tests](#tests) — referential checks for a non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes on green
- [References](#references) — the one plan-level reference relevant here
- [Deferred](#deferred) — what is deliberately not specified here, and why

## Why

The claim motivating the whole `jira-grade` group — jira-grade detail churns less than run-grade across a scope change because its contradiction surface is smaller — has only ever been inferred from post-mortems, never observed (plan Problem statement; BACKLOG #169's stage-01 bullet names this check). Steps 4 and 7 make both depths authorable and auditable for one plan, so this is the cheapest test of the mechanism before later stages invest in it: one plan, one change, four audits, one committed record. Whatever the result, it is recorded and routed, never gated on — a surprise becomes a `BACKLOG.md` direction question against stage 05 (#171), and this plan still closes.

## Input

- **Step 4's authoring mode** and **step 7's audit grade** — both unbuilt at authoring time. Their command lines, flag spellings, battery selection, and report-provenance shape are **deliberately not restated here**; read the merged detail files and `docs/cli/detail.md` / `docs/cli/completeness-audit.md` at execution time. Restating them in this file is what round 9's HIGH finding was about.
- **The one durable constraint, true at HEAD independent of those steps:** completeness reports persist to the target plan's **committed** `plan-details/<slug>/reports/` directory (`plan_tool/review_persistence.py:plan_reports_dir`), where `resolve_reusable_audit` and `convergence_diagnosis.load_report_history` later consume them. Experiment audits of a deliberately-broken plan state must not land there. This is why the isolation commitment below is not hygiene.

## Files (creates vs edits)

- **New files:**
  - `docs/jira-grade-falsification-check.md` — the committed record.
- **Existing files (edits only):**
  - `BACKLOG.md` — the outcome routing: a pointer to the record under the #169 stage-01 bullet, plus any direction question the selected reading calls for. Do **not** touch #164's Status line; step 11 owns that flip.

The experiment's own artifacts (jira-grade bundle, scoped plan edit, audit reports and sidecars) are **not** part of this step's committed footprint.

## Implementation

Four commitments survive not knowing the instruments. Everything else is authored at execution time.

1. **Predeclare before observing.** The record's reading rule and its routing are written into the doc *before* any audit runs. The readings themselves come from the plan body, which declares all three ahead of any evidence and forbids inventing a fourth — transcribe and apply them; do not re-derive or re-scope them. What is decided at execution time is only how each reading is *computed* against the merged instruments.
2. **Isolate.** Run the whole check on a scratch branch in its own worktree **sited outside the repo root** (a sibling, matching `plan_tool/worktree.py`'s default base). This is load-bearing: `plan-tool run --commit` stages a green step with `git add -A` (`plan_tool/cli/gitcommit.py:commit_all`), so a worktree under the repo would sweep the experiment into this step's own commit. Merge only the two declared files; delete the branch unmerged.
3. **Establish the shared surface before reading any delta — then choose an intervention that surface can see.** The two arms do not necessarily run the same instrument — step 7 selects a battery per grade. Before computing any delta, determine from the **merged code** which surface both arms genuinely share, read the mechanism claim only there, and record that determination with the citation it rests on. A finding absent from one arm by battery selection carries no information and must never enter a delta. **The scoped change must then be chosen so it moves that surface**: an intervention whose effects land only outside it produces a vacuous near-tie and the observation returns nothing. Pick the intervention after the surface is known, not before, and state in the record why it is visible there.

4. **Pin the prompt framing across both arms, and let the classification carry the asymmetry.** The plan body requires one framing for both arms, and step 7 exposes a control that pins it independently of the selected grade. Use **run-grade framing on both arms**; read step 7's merged flag spelling from `docs/cli/completeness-audit.md` at execution time rather than assuming one here, and record the exact invocations verbatim. Two consequences the record must state plainly so a reader does not mistake either for a result:
   - **The jira arm's raw finding count will be higher**, because the compact contract's shed facts surface as findings under run-grade framing instead of being excused in the prompt. That is the instrument working as designed, not evidence against the mechanism claim. Raw counts are not the reading.
   - **The reading is the contradiction class only.** Classify every delta finding in *both* arms as **absence** (the bundle never stated the fact), **contradiction** (the bundle stated something the change made wrong), or **structural** (a decomposition or dependency defect the plan carries), per the plan body's definitions. A bundle's standing absences are identical before and after the change and cancel in the baseline subtraction; new absences created when the change widens scope do not cancel, so count and report them separately and never read them as churn. The mechanism claim is about contradictions — a compact bundle states less, so less of it can become wrong — and that is where the arms are compared.

   Why this replaces letting the prompt do it: a grade-selected framing suppresses the jira arm's absence findings before they are ever counted, which also suppresses any contradiction findings entangled with them, and guarantees the *Expected* reading by construction. Moving the judgment from the prompt into this classification makes it visible, auditable, and reversible by a reader who disagrees with a label. If the classification cannot be applied to some finding, record it as unclassified and exclude it from the reading — never silently fold it into a class.

The rejected alternative: auditing once per depth (post-change only). Rejected because a single post-change audit cannot separate change-induced findings from pre-existing ones, and the claim is about churn *across* the change — so both arms need a baseline.

## Tests

### Verification (non-code step)

This step changes no production code; verification is referential and structural checks on the two committed files.

- predeclared-reading-precedes-evidence — the reading/routing section appears before any finding set in document order
- commands-recorded-verbatim — every invocation appears as a literal command line, the arms differing only by the grade flag, same explicit `--audit-passes` on both
- scoped-change-diff-present — the plan edit appears as a verbatim diff, touching only the target plan file
- shared-surface-determined — the doc names the surface both arms share, cites the merged code it read to determine it, and computes deltas only there
- four-finding-sets-present — baseline and post-change sets for both depths, each entry carrying stable id, severity, and step/region
- provenance-present — each finding set is bound to the bytes audited, by whatever provenance the shipped reports carry; backend/model recorded once
- framing-pinned-across-arms — both arms' recorded invocations carry the same prompt framing (run-grade), quoted verbatim from the shipped flag surface, and the doc says why it is pinned
- deltas-classified-three-ways — every delta finding in both arms is labelled absence / contradiction / structural (or explicitly unclassified and excluded); absence counts are reported separately and the doc states they are not churn
- reading-is-the-contradiction-class — the selected outcome is argued from the contradiction comparison, and the doc states in its own words that raw finding counts are not the reading
- readings-match-the-plan-body — the doc's three candidate readings are the plan body's three, in its terms; no fourth reading appears and none is re-scoped
- outcome-classified-and-routed — either exactly one of the plan body's three readings is selected and its routing performed, or the record is explicitly indeterminate because an arm could not be produced; the doc states the outcome gates nothing either way
- third-reading-named — the record names all three candidate readings including a materially larger jira-arm delta, and does not label that outcome "comparable" or "indeterminate" (the step's frontmatter gate greps for all three)
- backlog-pointer-links-doc — `BACKLOG.md` links the record under the #169 stage-01 bullet; #164's Status line is unchanged by this step's diff
- backticked-paths-exist — every repo path named in the doc exists at HEAD
- main-left-clean — the target plan is unchanged and its `plan-details/<slug>/reports/` directory contains no experiment reports or sidecars
- worktree-sited-outside-repo — the recorded `git worktree add` path resolves outside the repo root

## Acceptance criteria

- `docs/jira-grade-falsification-check.md` exists on main and contains: the claim under test, a reading rule with routing written before the evidence whose candidate readings are the plan body's three (none added, none re-scoped), the shared-surface determination with its code citation, the target-plan choice and why, verbatim commands, the scoped-change diff, both depths' baseline and post-change finding sets with stable ids and severities, provenance binding each set to the bytes audited, and one selected outcome with its routing performed.
- Both arms were audited under one pinned prompt framing, recorded verbatim in the invocations; every delta finding in both arms is classified absence / contradiction / structural; absence counts are reported and explicitly excluded from the reading; and the selected outcome is argued from the contradiction class, not from raw finding counts.
- The record carries the classification and routing the plan's **Mechanism falsification check** requires — cited by name from the plan body, not restated here. Whatever that section mandates about labelling one arm's delta findings and routing a material structural disappearance is a requirement of this step's record, and the deferral above does not exempt it. This is the acceptance hook for the deferred rule; it names no flag spelling, battery selection, or sibling-step prose.
- The doc states explicitly that the outcome is recorded and never gated on, and that an unavailable or failed arm reads as **indeterminate** — never as zero findings. Indeterminate is not a fourth reading: the plan body's three are the readings when the check *runs*, and indeterminate is what the record says when an arm could not be produced at all. A record that reaches a reading must select exactly one of the three; a record that cannot is indeterminate and selects none. State that distinction in the doc so a later reader cannot use "indeterminate" to sidestep the third reading, which the plan body forbids being absorbed that way.
- `BACKLOG.md` links the record; `#164`'s Status line is untouched by this step.
- This step's commit in the main tree touches exactly two files; the scratch worktree was sited outside the repo root and the branch was removed unmerged.
- The target plan and its reports directory on main are unchanged from before the check.
- All referential checks in the Verification section pass.

## References

- [Claude Code — Headless / programmatic mode](https://code.claude.com/docs/en/headless) — governs how this procedure's non-interactive invocations shell out; useful when recording backend/model provenance.

## Deferred

- **How the readings are computed — the delta classification rule (implementation-fact vs structural) and the battery-differential constraint naming step 7's dropped checks — deliberately authored at execution time, not here.** These describe behavior steps 7 and 4 have not built, so every version written now is a prediction about sibling detail prose. **This defers the mechanics, not the readings themselves:** the plan body predeclares all three outcomes and forbids a fourth, and that predeclaration is binding on this step (see Summary and commitment 1). Restating the three readings *here* is what stays out — the plan body is their single home, and duplicating them is how round 9's contradiction arose. Rounds 1, 2, 4, 7, and 9 of this plan's completeness audit each filed findings against these paragraphs; round 9's HIGH was this file's delta rule contradicting step 7's battery selection, and the fix for it bound the two files more tightly still. This is deliberate under-specification, not an authoring gap — **do not re-add these before the instruments exist.** Re-author this section at run grade once steps 7 and 4 are green.
- Longitudinal churn instrumentation, floors, and roll-up — stage 03's quality ledger; this step is one recorded observation, not a metric surface.
- Any verdict gate or adoption decision on the result — stage 05 (#171), and only after the ledger exists.
- Flipping BACKLOG #164 to instrument-shipped / evaluation-pending — step 11 owns the close-out.
- The consumer probe as an alternative evidence source — stage 02 (#169).
- Automating or re-running the check (scripts, clones, matched baselines) — the plan forbids the machinery; a repeatable version is the ledger's job.
- Migrating the scratch branch's jira-grade bundle into the target plan's durable state — that plan's operators' decision.
