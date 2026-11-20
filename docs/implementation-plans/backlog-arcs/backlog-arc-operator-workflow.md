# Operator workflow and surface-quality backlog arc

## File intent

This file is the execution guide for backlog work that helps an operator find,
select, and understand supported work without changing correctness or
ownership contracts.

## Details

It records the prerequisite chains for deferred-work selection, Jira sweep,
lessons reuse, and reader-facing surfaces; the required named reader and
action; and the limits that keep presentation work from becoming a new gate.
The chains do not rank their independent lanes against the current backlog
board.

## Choose this arc when

Choose this arc for an explicitly selected operator-visibility,
deferred-work-selection, or already-correct reader-surface problem. It does
not displace an active BUG or a `BACKLOG.md` Now/Next board pick; those remain
the global priority. Once this arc is the selected lane, use the route below
to choose the smallest chain that resolves the operator's stated constraint.

## Delivery cadence

Commit each resolved backlog item before starting the next one. Plan-tool work
uses committed green-step checkpoints; direct changes include their regression
coverage and backlog retirement in one bounded commit.
Do not push automatically; push only when the user explicitly requests it.

## Prioritized selection

1. Honor `BACKLOG.md`'s active BUG and Now/Next board choices before selecting
   any lane here. A completed prerequisite makes its dependent work eligible;
   it does not raise that work above a current board pick.
2. Pick the one lane that matches the operator's immediate decision:
   - **Export-state clarity:** `jira-sweep-deterministic` is parked under
     #142 until an active Jira export workflow needs its standalone status
     report. Evaluate `jira-sweep-verify-code-truth` once that report ships.
   - **Deferred-work triage:** reopen `deferred-scan-digest` when an actionable
     deferral is missed by the current filing workflow. Start with the
     read-only scan. Revisit `deferred-select-promote` when the scan shows a
     need for a separate promotion step. See the
     [backlog evidence](../../../BACKLOG.md#now--next--blocked--parked-working-set).
   - **Lesson-selection evidence:** if lesson selection is the question,
     compare matched tasks with and without injection before considering
     `lessons-store-restructure`. The
     [lesson influence decision](../../history/backlog-decisions.md#196--infer-lesson-influence-and-evict-inert-lessons)
     records why `lessons-reuse-instrumentation` is parked.
3. Treat reader-facing audit surfaces as later, decision-specific work. Choose
   only one of `completeness-output-quality` or
   `audit-finding-staleness-classification`, and only when it improves a named
   operator action rather than adding report text. Narrative review remains an
   optional human technique, not a product surface.
4. Keep T5 documentation, export, and cosmetic candidates behind a concrete
   user workflow. A surface is ready when it has a named reader, a named
   action, and a way to tell that the action improved.

## Decision gates

- Deferred work stays a record until a selector promotes it; a scan cannot
  mutate plans or reclassify backlog priority by itself.
- A report field must identify its consumer and next action. Avoid adding a
  second renderer for data that no command or human uses.
- Existing `jira --lint` and reconciliation behavior remain the baseline;
  workflow improvements do not weaken their error or ownership contracts.
- Do not promote an independent lane merely because another lane reached its
  prerequisite. Re-check the board, the named operator decision, and each
  dependent item's evidence gate before starting it.

## Exit and handoff

An individual pass ends when its selected lane leaves the operator able to
take the named action with grounded context and no hidden state. The complete
arc ends only when the deferred-work, export-state, lesson-evidence, and
selected reader-surface needs are each resolved or explicitly deferred.
Reassess T5 only with observed workflow demand.

## Out of scope

This arc does not repair bugs, add audit correctness gates, or redesign the
underlying plan/detail data model.

## Public onboarding lane

The skill-first README and first-task walkthrough (#510) reach detail review
in a consuming repository. #515 verifies that path with a fresh reader.
Keep clone plus editable `uv` installation as the supported method.
The installed-skill arc records the shipped onboarding guidance
(#508/#509/#511/#512). The installed skill supplies the seed-authoring
guidance shipped as #377. #513 (private-content sanitization) and #514 (license,
distribution and history boundary) are separate public-release prerequisites.
[Walkthrough evidence](../../demos/getting-started/RUNBOOK.md#live-first-plan-walkthrough)
