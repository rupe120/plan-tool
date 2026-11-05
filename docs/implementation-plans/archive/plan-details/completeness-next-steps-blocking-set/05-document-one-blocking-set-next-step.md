> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the one-blocking-set next-step rule in the audit how-to and remove BACKLOG #479 and its gate-signal roll-up line

<!-- plan-tool:detail-format-version: 1 -->

## Summary

This step makes the operator docs match what steps 1–4 ship. It adds a short subsection to `docs/how-to/pipeline/audit.md` that states the rule: every next-step reader consumes the audit's one blocking set, a blocking gap ends the command list with the re-audit and offers no stage, and an advisory gap is listed but holds nothing back. It also removes the full #479 entry and its roll-up mention under the `gate-signal` facet in `BACKLOG.md`. The key decision is that the how-to names the verdict and the finalize gate's own symbols and does not restate the readers' wording. On green, `audit.md` has one place describing the rule, and `BACKLOG.md` has no #479 entry and no roll-up line for it.

## Table of Contents

- [Why](#why) — what the docs say today and what is stale
- [Input](#input) — what steps 1–4 land that this step must read off the code
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files touched
- [Implementation](#implementation) — where the doc text goes, what it states, and the backlog removal
- [Verification (non-code step)](#verification-non-code-step) — runnable doc and backlog checks
- [Acceptance criteria](#acceptance-criteria) — observable results
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — work this step leaves out

## Why

- `docs/how-to/pipeline/audit.md` says the report prose, the command list, and the `### Suggested next steps` block "all read `_actionable_conceptual_gaps`, so they cannot disagree" (under the bare-plan policy section). That claim is about the apply fence only. It says nothing about the blocking verdict, and it is the sentence a reader will trust.
- The doc has no statement that a stage transition is offered only when nothing blocks. After steps 1–4 that is the observable contract.
- BACKLOG #479 is the entry this plan closes. Left in place, it reads as open work, and its `gate-signal` roll-up line keeps pointing at it.
- The source map already lists the "Conceptual bar blocking set" row. It needs the verdict symbol added so the new subsection has a code anchor.

## Input

- **Steps 1–4 outcomes:** a blocking verdict with states `set`, `incomplete`, and `absent`, in `plan_tool/completeness_report.py`. Step 2 builds it from the finalize gate's own values in `plan_tool/cli/completeness_phases.py` and `plan_tool/cli/completeness_cmd.py`. Step 3 gates `run` in the `detail` / `split` / merge blocks in `plan_tool/cli/authoring.py`. Step 4 adds the table-driven agreement test.
- **Read the landed names off those modules.** The landed names win over any spelling in this file or in the plan. Cite a symbol in the doc only after confirming it exists at HEAD with `rg`.
- **Limit:** this step documents behavior; it does not verify it. The tests from steps 1–4 own that.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `docs/how-to/pipeline/audit.md` — add one subsection under `## completeness-audit` (beside "Bare-plan policy: properties before mechanisms" and "Stage bar and mid-run steering"); add the verdict symbol to the "Conceptual bar blocking set" source-map row; adjust the one "cannot disagree" sentence so it no longer implies the apply fence alone keeps the readers in agreement.
  - `BACKLOG.md` — delete the #479 entry (the section headed `**#479 — Derive every completeness "close these gaps" message …**`) and delete the `**#479**` item from the `gate-signal` facet roll-up bullet.

## Implementation

**Doc subsection (recommended shape)**
- Place it as a `###` heading after "Stage bar and mid-run steering". Heading suggestion: "One blocking set drives every next step".
- Open with its purpose in one sentence: after a `completeness-audit`, every message that says what to close and whether to move on agrees with the finalize gate's blocking verdict.
- Present the three verdict states as a small table, since this is a state-dependent mapping:
  - `set` and non-empty: blocking gaps are named, the command list ends with the re-audit to run after the session-directed edit, and no stage transition (`detail`, `run`, `jira`) is offered.
  - `set` and empty: the stage transition is offered, and advisory gaps stay listed.
  - `incomplete` or `absent`: no stage transition; the re-audit command is offered, because the audit did not finish or no verdict reached the reader.
- State separately that an advisory gap is listed but holds back no stage.
- Name the readers by symbol: `next_stage_command`, `suggested_next_steps`, `suggested_next_step_commands`, `console_summary` in `plan_tool/completeness_report.py`, and `_render_grouped_report` in `plan_tool/cli/completeness_phases.py`. Add the `detail` / `split` / merge parents (`plan_tool/cli/authoring.py`, `_CompletenessTailOutcome`) as the place `run` is dropped.
- State what did not change: the stage bar stays in `is_blocking_finding` and the stage stays `derive_audit_stage`'s; `--json`, `--fail-on-findings`, and exit codes are unchanged; the loop-stop `open_findings=` banner is not a next-step reader.
- Say the grade applies to both: at `--grade jira` the re-audit command is `completeness-audit <plan> --grade jira`, consistent with the existing "Next steps name no verb this grade cannot serve" paragraph. Link to that paragraph and do not restate it.

**Existing sentence**
- The "cannot disagree" sentence in the bare-plan policy section stays true for the apply fence. Narrow its wording to say the three readers share one actionable-gap list, and link forward to the new subsection for the blocking verdict. Do not rewrite the section around it.

**Source map**
- Extend the "Conceptual bar blocking set" row with the verdict type and its constructor, using the landed names. Do not add a second row.

**Backlog removal**
- Delete the whole #479 entry through its `Origin` bullet, up to the `## Adding a new entry` heading that follows. Keep one blank line before that heading.
- Delete only the `**#479** (…)` item from the `gate-signal` roll-up bullet. Fix the punctuation of the item before it (the `**#472**` item) so the sentence still ends cleanly with a period.
- Do not edit any other #-numbered entry. Grep first: `rg -n '#479|479' BACKLOG.md` also matches unrelated numbers (a line reference near `_SavedAuditResolution`); remove only the two #479 sites.
- Do not leave a tombstone line. The plan's history lives in git and the plan itself.

**Vocabulary sweep (class, not cited spot)**
- The class is "text that treats this next-step disagreement as open." Search by identifier (`#479`, `479`, `completeness-next-steps-blocking-set`) and by vocabulary ("no plan-level gaps remain", "no gaps left", "one blocking set", "next-step reader") across `BACKLOG.md`, `BUG_BACKLOG.md`, `docs/how-to/pipeline/audit.md`, `docs/TRACKING.md`, and `docs/history/backlog-decisions.md`.
- For each hit, either update it or say in the commit why it stays. Hits in `integrations/shared/DIRECTIVES.md` are outside this step's files; record them under Deferred rather than editing.

## Verification (non-code step)

This step changes no production code, so the test-authoring gate does not apply. Run these checks:

- **Symbols exist:** `rg` every function, class, and constant the new subsection names in `plan_tool/` and confirm each is present at HEAD.
- **No line numbers:** the new text cites no line numbers or ranges.
- **Links resolve:** the new subsection's relative links (to `DIRECTIVES.md`, the grade paragraph, `DATA_CONTRACT.md` if used) point to a real file and a real heading; confirm each anchor against the heading text.
- **Anchor safety:** `rg -n '#one-blocking-set' docs/ README.md` shows only the links this step adds, and no heading that existed before was renamed (so no inbound anchor breaks).
- **Source-map row:** the "Conceptual bar blocking set" row names the landed verdict symbol and no symbol absent from HEAD.
- **Backlog gone:** `rg -n '#479|\*\*#479' BACKLOG.md` returns nothing; `rg -n 'Derive every completeness' BACKLOG.md` returns nothing.
- **Readability guard:** run `uv run pytest tests/test_backlog_readability.py -q`; it is the repo's guard over `BACKLOG.md` structure.
- **Doc drift guards:** run `uv run pytest tests/ -q -n auto -k "doc or backlog or capability"` as a quick sweep for doc-drift tests; run the full suite if any fail.
- **Sweep record:** the vocabulary sweep's hit list is written in the commit message body, with each remaining hit marked updated or kept and why.

## Acceptance criteria

- `docs/how-to/pipeline/audit.md` has one subsection that states, for the three verdict states, what the command list and stage transition look like.
- That subsection says an advisory gap is listed but holds back no stage, and that a blocking gap ends the command list with the re-audit.
- That subsection states that the stage bar, `--json`, `--fail-on-findings`, and exit codes are unchanged.
- Every symbol the new text names resolves with `rg` in `plan_tool/` at HEAD.
- The "Conceptual bar blocking set" source-map row names the landed verdict symbol.
- `BACKLOG.md` has no #479 entry and no `**#479**` item in the `gate-signal` roll-up; the roll-up sentence is still well formed.
- `uv run pytest tests/test_backlog_readability.py -q` passes.
- The diff touches only `docs/how-to/pipeline/audit.md` and `BACKLOG.md`.

## Applicable guardrails

- **The plan's "## Out of scope":** the doc describes the verdict; it must not change what blocks or introduce a second blocking rule. Describe the stage as `derive_audit_stage`'s and the bar as `is_blocking_finding`'s, and nothing else.
- **The plan's "## Out of scope", apply command:** the new text must not suggest `completeness-apply` closes conceptual gaps; they close by a session-directed edit, as the existing text already says.
- **The plan's "## Out of scope", loop-stop banner:** the doc may say the banner is not a next-step reader; it must not relabel or redefine it.
- **Step intent:** this step makes the operator contract match what ships and closes the backlog entry. It must not add behavior notes for code that steps 1–4 did not land.

## Deferred

- Updating `integrations/shared/DIRECTIVES.md` or `docs/history/backlog-decisions.md` if the sweep finds text there that restates the old next-step behavior — outside this step's declared files; record any hit for a follow-up edit.
- Removing any BUG_BACKLOG entry for the same symptom — outside this step's declared files; the #479 `Origin` note says that entry was already replaced.
- Regenerating `docs/cli/` — no flag or default changes in this plan, so the generated reference is unaffected.

## Tests

_(stub: model omitted this section — fill in manually)_

