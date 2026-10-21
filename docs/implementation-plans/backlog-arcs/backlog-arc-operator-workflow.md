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
   - **Export-state clarity:** execute `jira-sweep-deterministic`, then
     evaluate the blocked `jira-sweep-verify-code-truth` work against its
     actual exported artifact. The verifier is not ready before that sweep.
   - **Deferred-work triage:** execute `deferred-scan-digest`, then
     `deferred-select-promote`. The scan produces the normalized,
     deduplicated inventory that the selector consumes; do not author another
     selection surface first.
   - **Lesson-selection evidence:** execute `lessons-reuse-instrumentation`
     before considering `lessons-store-restructure`. Reuse evidence, rather
     than the current store's size alone, decides whether a restructure is
     useful.
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

#510 gives a new user a skill-first README and bounded first-task walkthrough;
#515 verifies that path in a fresh consuming repository. Keep clone plus editable
`uv` installation as the supported method. The installed-skill arc routes
#508/#509/#511/#512 and existing #377; consult those dependencies rather than
duplicating their scopes here. #513 (private-content sanitization) and #514
(license, distribution and history boundary) are separate public-release
prerequisites, not new reader-surface machinery.
