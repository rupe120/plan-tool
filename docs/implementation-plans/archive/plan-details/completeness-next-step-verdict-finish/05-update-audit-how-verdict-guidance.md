> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Update the audit how-to's verdict guidance, replace the `_actionable_conceptual_gaps` citation, and remove BACKLOG #480 and every roll-up mention of it

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step brings `docs/how-to/pipeline/audit.md` in line with the verdict behavior that steps 1–4 ship, and removes the shipped work's backlog record from `BACKLOG.md`. In the how-to, the "One blocking set drives every next step" section gains the three untrusted causes (`transient`, `persistent`, `stale-revision`) and the action each prescribes. The stale `_actionable_conceptual_gaps` citations are replaced with the symbol that exists at HEAD. In `BACKLOG.md`, the #480 entry and its mention in the `gate-signal` roll-up bullet are deleted. The key decision is that the how-to describes the shipped contract and cites symbols read from the landed code, not from steps 1–4's detail files. On green, no live document names a deleted symbol or a shipped backlog item.

## Table of Contents

- [Why](#why) — what the how-to and backlog say today
- [Input](#input) — what steps 1–4 hand this step
- [Files (creates vs edits)](#files-creates-vs-edits) — footprint
- [Implementation](#implementation) — doc edits and backlog removal
- [Verification (non-code step)](#verification-non-code-step) — reviewer-runnable checks
- [Acceptance criteria](#acceptance-criteria) — observable results
- [Applicable guardrails](#applicable-guardrails) — fences that bind this step
- [Deferred](#deferred) — work left out

## Why

The how-to's bare-plan paragraph and its source-map table row for the "Bare-plan conceptual apply fence" both cite `_actionable_conceptual_gaps` in `plan_tool/completeness_report.py`. That helper no longer exists; the readers take their list from `next_step_gaps`. The verdict table's `incomplete` row speaks of "a persistent cause" but gives a reader no way to tell a cut-short stop (re-audit continues it) from an unqualified result (triage first) or a changed plan (run a fresh audit). BACKLOG #480 and its roll-up mention describe work that steps 1–4 ship, so once they land the entries read as pending work that is already done.

## Input

- **Steps 1–4** supply the behavior this step documents:
  - Step 1: the three-value `untrusted_cause` and the action each gets from `_reaudit_command`.
  - Step 2: an `incomplete` verdict keeps the stage-bar blocking ids.
  - Steps 3–4: every reader takes its list, count, and next command from the verdict.
- **Read the landed names off HEAD** (`plan_tool/completeness_report.py`, `plan_tool/cli/completeness_cmd.py`). Where they differ from steps 1–4's detail files, HEAD wins.
- **`docs/how-to/pipeline/audit.md` anchors:**
  - The bare-plan paragraph that ends "all read `_actionable_conceptual_gaps`".
  - The "One blocking set drives every next step" section and its verdict-state table.
  - The source-map row "Bare-plan conceptual apply fence".
- **`BACKLOG.md` anchors:**
  - The `**#480 — Finish the completeness next-step verdict…**` entry.
  - The `#480` mention in the arc/quality roll-up (the bullet ending "a reachable transient cause and ids for incomplete audits").
  - The `gate-signal` roll-up bullet. Re-check at HEAD whether it carries a #480 mention of its own; the grep found the only roll-up mention in the neighboring list.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/how-to/pipeline/audit.md`:
    - Replace each `_actionable_conceptual_gaps` citation with the current symbol.
    - Extend the verdict-state table or add a short cause table under it.
    - Make the `incomplete` row name the three causes.
  - `BACKLOG.md`:
    - Delete the #480 entry.
    - Delete the #480 clause from the roll-up bullet, fixing the bullet's list punctuation.

## Implementation

- **Replace the stale symbol first.**
  - Run `rg -n '_actionable_conceptual_gaps' docs/ plan_tool/ tests/ BACKLOG.md` before editing and write down every hit.
  - Edit the two how-to hits. Point both at `next_step_gaps` (plus `NextStepGaps` if the landed name is used in prose).
  - Keep the sentence's meaning: the three readers share one gap list.
  - If the search finds hits outside the declared files, report them; do not edit them in this step.
- **Document the causes in the "One blocking set" section.**
  - Add a compact table keyed by `untrusted_cause`, with columns for when it applies and what the next command says.
  - `transient`: the audit stopped on a cut-short stop (`max_iterations`, `deadline_exceeded`, `no_progress`). The command is the plain re-audit, which continues the run.
  - `persistent`: coverage is unqualified, or deferrals await a person. The text says to triage the saved report and commit before re-auditing.
  - `stale-revision`: the plan changed since the saved evidence, or legacy coverage is present. The text says to run a fresh audit, and the saved gaps are not offered as text to close.
  - Name the precedence when one result carries several causes, using the plan's `## Architecture` order. Cite it; do not re-decide it.
- **Fix the `incomplete` row.** It must say the verdict keeps the ids the stage bar computes, even for a budget-limited audit, while the finalize gate's `--json` fields, `--fail-on-findings`, and exit codes are unchanged. State that last point in the doc, since step 2 deliberately keeps two values.
- **Check the doc's own claims against the code.** Per the project's rule on false claims, confirm each sentence you write against the landed symbols. In particular, confirm which stop reasons map to `transient`.
- **Remove the backlog record.**
  - Delete the whole #480 entry, including its Origin and Arc assignment lines.
  - In the roll-up bullet, remove the `#480 (…)` clause and make the preceding item the last, with correct punctuation.
  - Sweep both identifier and vocabulary: `rg -n '#480|reachable transient|ids for incomplete'` over `BACKLOG.md`, `docs/`, and `plan-seeds/`. Leave a hit only if it is a dated, past-tense provenance note, and say so per site.
  - Do not renumber other entries; plan-tool entry ids are stable.
- **Write forward-looking prose.** Describe what the verdict does now; add no "previously" or "was" narration to the how-to.

## Verification (non-code step)

This step changes no production code, so the test-authoring gate does not apply (it keys on `change_type`). Check these by hand:

- **Symbol existence:** `rg -n 'def next_step_gaps|def _reaudit_command|def _verdict_untrusted_cause' plan_tool/` returns each cited symbol; every symbol the new doc text names appears there.
- **No stale citation:** `rg -n '_actionable_conceptual_gaps' docs/ BACKLOG.md` returns nothing.
- **Cause names match code:** the three cause strings in the doc equal the constants in `plan_tool/completeness_report.py`.
- **Backlog gone:** `rg -n '\*\*#480' BACKLOG.md` returns nothing, and `rg -n '#480' BACKLOG.md` returns no live reference.
- **Roll-up readable:** the edited bullet in `BACKLOG.md` still reads as a valid list (no dangling comma, `and`, or empty parenthesis).
- **Links:** the `[One blocking set drives every next step](#one-blocking-set-drives-every-next-step)` anchor still resolves; no heading was renamed.
- **Format guards:** run `uv run pytest tests/ -q -n auto -k "backlog or tracking or doc"` and then the full suite once, since doc and backlog format checks live in the test suite.
- **Clean tree:** `git status` shows only the two declared files changed.

## Acceptance criteria

- `docs/how-to/pipeline/audit.md` names no `_actionable_conceptual_gaps`.
- The how-to states all three untrusted causes and the action each prescribes, and each name matches the landed constant.
- The `incomplete` row states that retained ids are named as gaps to close and that `--json`, `--fail-on-findings`, and exit codes do not change.
- `BACKLOG.md` has no #480 entry and no roll-up mention of it.
- The roll-up bullet that carried #480 is still well-formed.
- No other backlog entry's id changed.
- The full pytest suite passes.

## Applicable guardrails

- **The plan's "## Out of scope"** bars this step from changing blocking predicates, gate fields, or exit codes. The how-to documents those as unchanged and must not describe any change to them.
- **The plan's "## Out of scope", settled states bullet** means the doc must not re-describe the `set` / `incomplete` / `absent` states as anything other than they are.
- **The step intent** limits this step to describing shipped causes and removing shipped work from the backlog. It adds no new advisories, no new gates, and no backlog entries.

## Deferred

- Code or test changes for the verdict readers — owned by steps 1–4; this step only documents them.
- Any `_actionable_conceptual_gaps` mention outside `docs/how-to/pipeline/audit.md` and `BACKLOG.md` — outside the declared files; report any hit rather than editing it here.
- A consolidated cause-to-action table in `docs/reference/` or `RUNBOOK.md` — not required for the outcome; the how-to is the operator contract.

## Tests

_(stub: model omitted this section — fill in manually)_

