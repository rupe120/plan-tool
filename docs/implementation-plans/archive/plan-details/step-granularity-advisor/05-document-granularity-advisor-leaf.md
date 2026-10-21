> **Auto-archived**: this plan was swept on 2026-06-20 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the granularity advisor leaf, its two sources, and the merge-is-advisory-only deferral

## Summary

Document the not-yet-shipped `plan_tool/granularity.py` advisor and its two finding sources across the two human-facing guides this step owns: `CLAUDE.md` (architecture map) and `RUNBOOK.md` (operator walkthroughs). Add one bolded Architecture paragraph to `CLAUDE.md` describing the cycle-free leaf, its `assess_granularity` contract, the `granularity-split` / `granularity-merge` sources, and its advisory/non-gating posture. In `RUNBOOK.md`, add the create-stage split hint to the change-type-review paragraph and a granularity note to the completeness `Smells (advisory)` flow, stating that `granularity-merge` is the only place merge advice surfaces and that it is **recommend-only** — the advisor never runs a merge; the operator hand-runs `plan-tool merge`. This is a non-code step: no production code, no unit tests, only doc accuracy/placement checks. On green, both guides describe the advisor, neither contradicts the landed code, and the merge deferral is recorded as a standing note rather than implied complete.

## Table of Contents

- [Summary](#summary) — what gets documented and where, and the result on green.
- [Table of Contents](#table-of-contents) — this list.
- [Why](#why) — the advisor ships across four code steps with zero docs.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two edited guides, edit-by-edit.
- [Implementation](#implementation) — the exact prose to add per surface and the placement decisions.
- [Confirm against landed code first](#confirm-against-landed-code-first) — symbols to grep at HEAD before writing, since steps 1–4 aren't landed yet.
- [Tests](#tests) — the verification checklist standing in for unit tests.
- [Verification (non-code step)](#verification-non-code-step) — doc-vs-code, completeness, anchor, placement, deferred-fidelity checks.
- [Acceptance criteria](#acceptance-criteria) — checkable conditions.
- [References](#references) — the markdown/docs sources for this step.
- [Deferred](#deferred) — what stays out (PLAN_FORMAT.md, TESTING.md, the split-escalation bridge).

## Why

The granularity advisor ships across steps 1–4 — a new cycle-free leaf (`plan_tool/granularity.py`), a folded `detail` purity kernel, a `create` change-type hint, and a `completeness` cross-step audit — with **zero documentation**. `CLAUDE.md`'s Architecture section already gives every cycle-free advisory leaf its own bolded paragraph (`backend.py`, the Correctness gates, the three branch-awareness leaves); the granularity leaf has none, so a future contributor reading the architecture map can't tell it exists or that it must stay below `create`/`detail`/`completeness`. `RUNBOOK.md` documents the `(s)plit` change-type action and the completeness workflow but mentions no granularity advice — and its completeness section (`RUNBOOK.md:1644-1647`) does not yet document the `Smells (advisory)` surface at all, so the note must introduce it. Most important: the plan's `granularity-merge` source is **recommend-only**, and an operator who sees a merge finding needs a doc that says the advisor won't act on it — they run `plan-tool merge` themselves. This step closes those gaps and records the merge deferral as a standing note so the partial state reads honestly.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `CLAUDE.md` — add one bolded Architecture paragraph for the granularity advisor leaf, placed in the `## Architecture` section after the **Correctness gates** paragraph (the advisory-validation sibling). No other section changes.
  - `RUNBOOK.md` — two small edits:
    - In the surface that documents the `--from` / `--from-existing` proposal change-type review loop (where `_review_step_change_types` / `_ask_change_type`→`_SPLIT` actually offer the invoker-gated `(s)plit` action), add one sentence: when an invoker is present, the `(s)plit` action now carries a deterministic "this step looks splittable" hint from the advisor. **Not** the from-scratch manual wizard paragraph, which states `(s)plit` is absent on that path; if no paragraph documents the proposal-review loop, add that surface.
    - In the `## Workflow: completeness checks` section, introduce the deterministic `Smells (advisory)` section (RUNBOOK does not document it yet — the report-grouping list at `RUNBOOK.md:1644-1647` names only Body sections / Detail coverage / Detail body completeness / Files coherence / Lessons coverage / Test-strategy) and state that it carries cross-step granularity advice (`granularity-split` + `granularity-merge`), that this is the only surface where merge advice appears, and that `granularity-merge` is recommend-only — surface it, then hand-run `plan-tool merge`.

## Implementation

### `CLAUDE.md` — new Architecture paragraph

- **Add one bolded paragraph** after the **Correctness gates (`review.py`, `gates.py`, `scope_guard.py`, `drift_detection.py`)** paragraph and before the **Exit-code convention** paragraph in `## Architecture`. Place it among the leaf/seam paragraphs, not in `## What this is` (which describes the pipeline, and the advisor is cross-cutting, not a pipeline stage).
- **Content to cover (mirror the terse, claim-dense style of the `backend.py` and branch-awareness paragraphs):**
  - **The leaf and its import discipline.** `plan_tool/granularity.py` is a cycle-free advisor leaf importing only `plan_tool/schema.py` (`Plan`, `Step`, `ChangeType`) and `plan_tool/review.py`'s finding primitives (`Recommendation`, `_make_rec_id`, `Invoker`) — no CLI, no orchestrator imports — so it sits below `create`/`detail`/`completeness`, which import *it*. `review` never imports `granularity` (one-way edge keeps it acyclic).
  - **The contract.** `assess_granularity(plan, *, stage, evidence, invoker=None) -> list[Recommendation]`, where `stage` is one of `create` / `detail` / `completeness` and `evidence` is a `GranularityEvidence` envelope. The deterministic split/merge detectors read only plan structure and never shell out; `invoker` is consumed only by `detail`'s relocated prose (MIXED-STEP) judgment.
  - **The two sources.** `source="granularity-split"` (a step too big / mixing concerns — generalizes the former `detail-purity` finding, folded in, not forked) and `source="granularity-merge"` (adjacent dependent steps fragmented). Both are advisory; both are kept **out** of `review.py`'s `APPLY_ELIGIBLE_SOURCES`, so they route through the generic `triage_reason` structural-diagnostic text and can never reach `apply_finding` or flip an exit code.
  - **The per-stage surfaces.** `create`'s change-type review loop shows `granularity-split` hints beside its `(s)plit` action (deterministic, no Claude); `detail`'s MIXED-STEP purity check emits through this source; `completeness-audit` folds both sources into its advisory `Smells (advisory)` bucket.
  - **The merge deferral, stated precisely.** The advisor only advises — it never mutates plan structure. `granularity-merge` is recommend-only: there is no automatic bridge from a merge finding to an actuating command. The operator resolves a flagged pair by hand-running `plan-tool merge` (the merge executor exists), or re-plans.

### `RUNBOOK.md` — change-type split hint

- **Edit the surface** that documents the `--from` / `--from-existing` proposal change-type review loop — the path where the invoker-gated `(s)plit` action is actually offered (`create.py:_review_step_change_types` / `_ask_change_type`→`_SPLIT`). Do **not** edit the from-scratch manual wizard paragraph (`(r)efactor / (f)eature / (n)on-code / Enter`): it explicitly states `(s)plit` is *absent* on the manual path because there is no claude proposal to decompose, so appending a split-hint sentence there contradicts the doc. If no RUNBOOK paragraph yet documents the proposal-review loop where the hint appears, add that surface.
- **Append one sentence** (on the proposal-review surface): when an invoker is present and a step looks splittable (a mixed refactor+feature title, a two-clause conjunction, or an unrelated file span), the prompt prints a deterministic split hint from the granularity advisor next to the proposal — the existing `(s)plit` choice, made informed, with no extra Claude spend. Keep the full `plan-tool` qualification out of this inline prose (it's about a key in the wizard, not a command).

### `RUNBOOK.md` — completeness Smells (advisory) granularity note

- **Edit the `## Workflow: completeness checks` section.** The report-grouping paragraph (`RUNBOOK.md:1644-1647`) lists the deterministic check kinds (Body sections / Detail coverage / Detail body completeness / Files coherence / Lessons coverage / Test-strategy) and the advisory severity bands, but does **not** mention the `Smells (advisory)` section at all — this note is RUNBOOK's *first* mention of that surface (the `Smells (advisory)` label is grep-confirmed in code, not RUNBOOK prose: `plan_tool/cli/completeness_phases.py` renders `### Smells (advisory)` and `plan_tool/completeness_report.py` renders `## Smells (advisory)`).
- **Introduce the `Smells (advisory)` surface** (one bullet or a two-sentence paragraph — written as a new mention, not appended to a nonexistent smell description) covering:
  - The deterministic report also emits a `Smells (advisory)` section, which carries **cross-step granularity advice** — `granularity-split` (a step that looks too big / mixes concerns) and `granularity-merge` (two adjacent dependent steps that look fragmented).
  - **Completeness is the only surface that shows merge advice.** `create`'s change-type loop surfaces only `granularity-split` (next to its `(s)plit` action) and drops merge recs, so the whole-plan audit is where a `granularity-merge` finding appears.
  - **`granularity-merge` is recommend-only.** Reading it does not act on it; the operator resolves a flagged pair by hand-running `plan-tool merge <name> --steps ID --steps ID` (already in the Quick reference Authoring table). rc stays 0 — granularity advice never gates (obeys the exit-code convention; `--fail-on-findings` is the only way to flip rc, same as every other advisory finding).

### Placement / scoping decisions

- **CLAUDE.md paragraph goes beside Correctness gates, not in the pipeline blurb.** The advisor is an advisory-validation leaf, a sibling of `review.py`/`gates.py`, not a pipeline stage; `## What this is` describes the `create → detail → audit → run/jira` pipeline and stays unchanged.
- **RUNBOOK split hint rides the proposal-review surface, not the manual wizard paragraph.** The `(s)plit` action exists only on the `--from` / `--from-existing` proposal-review loop; the from-scratch wizard paragraph documents `(s)plit` as *absent*. Annotate the surface that documents the proposal-review loop (adding it if none exists); avoid a new heading if an existing proposal-review paragraph can carry the sentence, so the hint stays attached to the action it annotates.
- **RUNBOOK merge note rides the completeness workflow; no new section, no new command tutorial.** `plan-tool merge` is documented as a command in exactly one place — the Quick reference Authoring table (per the merge-steps-executor docs). Reference that row; do not duplicate the command's usage here.
- **`plan-tool merge` is a common-English/different-domain collision.** Keep the full `plan-tool merge` form on every command line; leave any pre-existing git-sense "merge" lines in RUNBOOK (e.g. "before merge" in the verify/code-audit rows) as deliberate non-edits.

## Confirm against landed code first

- **depends_on: 2, 3, 4 — and none of steps 1–4 are landed at the time this detail is written** (`plan_tool/granularity.py` does not exist at HEAD; `grep -rn granularity plan_tool/` returns nothing). Treat every symbol below as a name to **re-confirm against the landed code at HEAD when this step is executed**, never copied from sibling detail files (which are pre-implementation guesses). The code wins on any conflict — fix the doc.
- **Grep-confirm before writing:**
  - the source string literals — `grep -rn "granularity-split\|granularity-merge" plan_tool/granularity.py plan_tool/review.py` — and the constant names (`GRANULARITY_SPLIT_SOURCE`, `GRANULARITY_MERGE_SOURCE`).
  - the contract signature — `grep -n "def assess_granularity" plan_tool/granularity.py` — confirm the keyword-only `stage` / `evidence` / `invoker=None` shape and the `GranularityEvidence` type name.
  - the apply-eligibility exclusion — `grep -n "APPLY_ELIGIBLE_SOURCES" plan_tool/review.py` and confirm neither granularity source is a member.
  - the render labels — `grep -rn "Smells (advisory)" plan_tool/` — confirm the exact `### Smells (advisory)` / `## Smells (advisory)` heading text the note refers to (these already exist at HEAD from the prior smell-checks work).
  - the merge command surface — `grep -n "plan-tool merge" RUNBOOK.md` — confirm the Quick reference Authoring-table row the note points at still exists.
  - the `(s)plit` action surface — `grep -n "(s)plit" RUNBOOK.md` — confirm where the action is documented before placing the hint. At HEAD the only `(s)plit` mention is **inside the from-scratch manual-wizard paragraph**, which documents availability as a **negative** ("the `(s)plit` key the `--from` / `--from-existing` wizard offers … is absent here"); no standalone proposal-review paragraph exists yet. So the split hint must ride a new/extended proposal-review surface — do not append it to the manual-wizard sentence, which says `(s)plit` is absent on its path.
- **Heads-up on a stale plan premise.** The plan body says `granularity-merge` "stays recommend-only because no merge executor exists yet" and its `## Deferred` blocks on `merge-steps-executor.md`. That executor **has landed** — `plan-tool merge` exists (`plan_tool/cli/authoring.py: cmd_merge`, `plan_tool/detail.py: merge_steps`, `docs/cli/merge.md`) and `merge-steps-executor` is archived. Document the **forward-true** state: merge advice is recommend-only not because the executor is missing, but because **no automatic bridge wires a `granularity-merge` finding to that command** — the operator runs `plan-tool merge` by hand. Do not write "no merge command exists."

## Tests

No unit tests — this step changes only `CLAUDE.md` and `RUNBOOK.md`. Verification is the checklist below.

## Verification (non-code step)

- **Doc-vs-code accuracy** — every symbol, source string, and render label written into either guide is grep-confirmed against the landed code at HEAD (see [Confirm against landed code first](#confirm-against-landed-code-first)); the code wins on conflict.
- **Surface completeness** — `CLAUDE.md` gained exactly one Architecture paragraph naming the leaf, the contract, both sources, and the merge deferral; `RUNBOOK.md` gained the split-hint sentence on the `--from` / `--from-existing` proposal-review surface (not the from-scratch wizard paragraph) and the granularity note in the completeness workflow.
- **Anchor / link validity** — the RUNBOOK note's reference to the Quick reference Authoring table (and any in-doc link added) resolves; no broken anchor introduced. Any `granularity-split` / `granularity-merge` / `plan-tool merge` strings render as inline code, not headings.
- **Placement assertions (mirror the key decisions)** — the CLAUDE.md paragraph sits in `## Architecture` after **Correctness gates**, not in `## What this is`; the RUNBOOK split hint is attached to the `--from` / `--from-existing` proposal-review surface (where `(s)plit` is actually offered), not the from-scratch wizard paragraph; the merge note is inside `## Workflow: completeness checks` with no new command-tutorial section.
- **Non-edit assertions** — pre-existing git-sense "merge" lines in RUNBOOK are unchanged; the command-families Authoring row (which omits `split`/`merge` by design, mirroring the cli docstring catalog) is unchanged.
- **Deferred fidelity** — the merge deferral is recorded in both guides as recommend-only with its real unblock condition (an auto-escalation bridge from a merge finding to `plan-tool merge`), not implied complete and not framed as "no merge executor."

## Acceptance criteria

- `grep -n "granularity" CLAUDE.md` returns the new Architecture paragraph, and it names `plan_tool/granularity.py`, `assess_granularity`, `granularity-split`, and `granularity-merge`.
- The CLAUDE.md paragraph states the leaf imports only `schema` + `review`'s finding primitives and sits below `create`/`detail`/`completeness`, and that both sources stay out of `APPLY_ELIGIBLE_SOURCES` (non-gating).
- `grep -n "granularity\|splittable" RUNBOOK.md` returns both the split-hint sentence and the completeness granularity note.
- The RUNBOOK completeness note states `granularity-merge` is recommend-only and points the operator to `plan-tool merge`, and states rc stays 0 (advisory, never gates).
- Neither guide claims "no merge executor exists"; the merge deferral is framed as the missing auto-escalation bridge.
- No git-sense "merge" line and no command-families catalog row in RUNBOOK was edited.
- The two source strings and every symbol named in either guide match `grep` output against the landed `plan_tool/` tree at HEAD.

## References

- [GitHub Flavored Markdown Spec](https://github.github.com/gfm/) — heading-slug/anchor rules used to verify the new RUNBOOK link and that inline code (source strings, command names) renders correctly.
- [Python Language Reference — The import system (Python 3.13)](https://docs.python.org/3.13/reference/import.html) — the acyclic-leaf import discipline the CLAUDE.md paragraph asserts (`granularity` imports `schema` + `review`, never the reverse).

## Deferred

- **PLAN_FORMAT.md / DETAIL_FORMAT.md edits** — out of this step's `files:`. The granularity sources are findings, not a frontmatter field or a detail-section contract, so the format specs need no change; if a future step wants the advisor in the `## Smell checks (advisory)` H2 of PLAN_FORMAT.md, that's a separate set of files.
- **TESTING.md neutralization row** — the granularity invoker seam's table entry lands with the step that first makes the seam reachable (step 2's `detail` fold), not in this docs step; it's outside these `files:`.
- **Documenting a split-escalation bridge** — the `escalate-structural-findings-to-split` plan is still `planning` (not landed), so the auto-bridge from a `granularity-split` finding to the split engine is not documented here beyond noting the advisor only advises. Revisit when that plan lands.
- **A `plan-tool merge` usage tutorial in RUNBOOK** — already covered by the Quick reference Authoring-table row and `docs/cli/merge.md`; this step only cross-references it from the merge deferral note.
