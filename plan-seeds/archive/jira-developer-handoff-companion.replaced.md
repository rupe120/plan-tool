> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-developer-handoff-companion.md`.
> Preserved here for history; do not edit.

# Jira developer-handoff companion

## Outcome

`jira` will optionally emit concise Jira stories and a provenance-stamped
developer-handoff companion from one captured input snapshot. The companion
will distinguish the plan's binding non-negotiables from an implementation-grade
suggested route, so a developer may choose a better mechanism without weakening
the required behavior, constraints, acceptance outcomes, or scope fence.

## In scope

The Jira export's selected detail bundle, terminal story output, a separate
generated companion path or mode, its provenance and staleness signal, and the
Jira format and CLI documentation are in scope. The resulting plan will update
BACKLOG.md #293 when the work ships.

## Allowed behavior changes

An explicit Jira companion mode will add a paired final handoff artifact. The
existing story-only export, detail-grade defaults, and independently authored
Jira-grade detail flow will remain unchanged when that mode is absent.

## Allowed reorganization

Only a small extraction around Jira export input capture or output rendering is
allowed when it gives the story set and companion one source snapshot and a
clear publication boundary. No broader detail-grade or pipeline reorganization
is allowed.

## Overview

The current export produces concise stories from the selected detail bundle;
`plan_tool.jira:export_jira` owns that read, prompt, and story write, while
`derive_jira_output_path` owns the conventional `jira-stories` destination. A
developer also needs a readable map that retains the why, guardrails, likely
route, and code anchors behind a ticket without treating its implementation
mechanics as the only permitted solution.

## Problem statement

Concise stories alone do not carry enough context for a developer to understand
why the work exists or which source constraints must survive an alternative
implementation. Copying or promoting the detail bundle would make an
implementation suggestion look authoritative and could collide with the
independent Jira-grade authoring artifacts under `plan-details/<slug>/jira/`.

## Architecture

The plan is the sole authority for intent, required behavior, constraints,
acceptance outcomes, and the scope fence. The explicitly selected detail bundle
supplies grounded guidance such as likely files, ordering, anchors, risks, and a
recommended route; the companion will label that material as a suggestion and
tell the reader that a different mechanism is valid when it preserves the
plan's non-negotiables.

The export will capture the plan and selected detail inputs once before it
renders either final artifact. Both the stories and companion will identify the
same selected source paths, input fingerprint, and generation mode. If an input
is absent or malformed, the export will fail before either final output is
written. An unresolved source conflict will be visible in the companion rather
than silently resolved; neither artifact will mix snapshots or invent a
resolution.

The companion is a terminal, generated-only view with a distinct destination
from independently authored Jira-grade detail. It is never an audit,
reconciliation, detail-authoring, or plan-mutation input. Its provenance will
make source changes visibly stale. Regeneration may replace only a prior
companion that identifies itself as generated for the same contract; a
human-authored target, including an independently authored Jira-grade artifact,
is preserved or explicitly refused.

## Out of scope

Changing the run/Jira detail-grade defaults or schemas; making Jira-grade detail
authoring derived rather than independently authored; external Jira posting or
sync; plan mutation; new audit, reconcile, or classification behavior; and the
withdrawn #169–#171 probe, ledger, materiality, or inversion route are out of
scope. The companion does not decide whether sources agree semantically beyond
making an unresolved conflict visible, and it does not prescribe a developer's
implementation mechanism.

## Risks

A companion that merely repeats stories adds noise, while one that presents
mechanics as requirements narrows legitimate engineering judgment. A second
output can also leave a stale or partial handoff if it reads inputs at different
times or overwrites a human artifact. The implementation must keep the existing
story export intact for callers that do not request the companion.

## Testing

Use stubbed export fixtures to prove that both terminal artifacts describe one
captured source snapshot and carry matching provenance; a source change leaves
the previous generated companion visibly stale. Missing or malformed selected
input fixtures fail before either output write, while an unresolved
source-conflict fixture remains visible without a fabricated resolution.
Replacement fixtures cover generated-companion regeneration and preservation or
explicit refusal of a human-authored target. A focused consumer fixture proves
that rendered output exposes non-negotiables and useful suggested guidance
without presenting the suggested mechanism as a requirement. Existing
story-only fixtures continue to prove unchanged behavior when the companion mode
is absent.

## Acceptance criteria

- An opt-in Jira export produces concise stories and a paired developer map
  grounded in one captured plan/detail snapshot, with readable provenance.
- Each map makes binding plan non-negotiables distinct from suggested
  implementation guidance and explicitly preserves developer choice of
  mechanism within those non-negotiables.
- Invalid selected input prevents both final output writes; unresolved source
  conflict remains visible rather than silently resolved; and a stale or
  human-authored companion is never silently represented as fresh generated
  guidance.
- The normal story-only export and the independent Jira-grade authoring lane
  retain their current behavior.

## Deferred

Feedback from actual developers on whether the companion's structure is useful,
and any later Jira-native attachment or synchronization workflow, remain
separate work. If this export uncovers broader disagreement about which detail
grade should be canonical, record that decision separately rather than widening
this terminal-handoff effort.

## Stop / defer

Defer any concern that needs a new detail grade, changes the plan's authority,
or turns the terminal companion into upstream workflow state to BACKLOG.md.
