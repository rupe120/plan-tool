> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Mechanism Reach 01 Authoring
intent: '`create` and `detail` will choose the smallest owner that makes a focused
  property true: reuse a suitable existing common structure unchanged, use a local
  adapter or bounded additive extension without changing existing consumer behavior
  or schema interpretation, or leave a required shared semantic change out of the
  focused plan for a separately intentional follow-up.'
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/mechanism-reach-01-authoring.md
steps:
- id: 1
  title: Extend combined and split create guidance to classify reach from the focused
    property and leave required shared work out, with focused prompt tests
  intent: Focused create runs choose owners by semantic reach at initial step selection,
    body synthesis, and foundational-logic sweep without duplicating suitable shared
    structures or widening contracts based on file or caller count.
  files:
  - plan_tool/create.py
  - plan_tool/prompts/synthesize-body.md
  - plan_tool/prompts/foundational-logic-sweep.md
  - tests/test_create.py
  - tests/test_foundational_logic.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/mechanism-reach-01-authoring/01-extend-combined-split-create-guidance.md
  status: done
- id: 2
  title: Extend combined and split detail guidance to apply unchanged reuse, bounded
    local changes, or separate shared work, with focused prompt tests
  intent: Detail drafts apply the owner rule to their existing plan, step, and scope-fence
    context, and split sweeps receive that context before they classify a find, so
    a shared-location find does not widen focused work without a semantic need.
  files:
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - tests/test_detail.py
  complexity: low
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Step 1 establishes the shared rule that combined and split detail paths apply
      to the plan, step, and any foundational-logic find.
  detail: docs/implementation-plans/plan-details/mechanism-reach-01-authoring/02-extend-combined-split-detail-guidance.md
  status: done
---
# Mechanism Reach 01 Authoring

## Overview

The existing create and detail prompts already prefer a proportionate mechanism
over a speculative framework. This effort makes their decision sequence
explicit in both combined and split modes: create's step proposal, body
synthesis, and foundational-logic sweep, plus detail's direct search or prior
sweep finding. A plan can therefore use the common structure that already owns
a property without promoting ordinary reuse into a cross-cutting change. When
the property truly needs a changed shared contract, the prompts keep that work
out of the focused plan. BACKLOG #336 later makes a split-create exclusion
visible as a manual follow-up handoff.

## Problem statement

Current proportionality guidance can reject an unnecessary rule engine or
adjacent capability but does not distinguish reuse of an established common
owner from a change to that owner's contract in both authoring modes. An author
can therefore select broad shared work in the initial step list, let a
foundational-logic sweep turn duplication alone into a consolidation step,
clone a suitable common structure to appear local, or enlarge a focused plan
with repository-wide identity, policy, or consumer work justified only by
future reuse. Neither result follows from the requested property.

## Architecture

The authoring prompts will require the same private decision whenever a focused
property reaches a common structure. `plan_tool/create.py:_render_from_prompt`,
`synthesize-body.md`, `foundational-logic-sweep.md`, `detail.py`'s combined and
split directives, and `detail.md` will each apply it from their existing
description, plan, step, scope-fence, or sweep-find context rather than
serialize a route choice between authoring phases:

1. Reuse the existing owner unchanged when its current contract satisfies the
   property.
2. Otherwise choose the smallest local adapter or bounded additive extension
   that introduces the focused capability while current consumers retain their
   behavior. A compatible bounded extension remains eligible even when an
   adapter is also possible; neither route exists merely to avoid appropriate
   reuse.
3. Otherwise identify the shared semantic contract as separate work and leave
   it out of the focused plan.

The combined inline foundational check and split foundational-logic sweep apply
the same routes. A duplicate, parallel caller, or shared file is evidence to
inspect an existing owner, not evidence that the focused plan must add an
update or consolidation step. A sweep may attach a bounded local change only
under route 2. `create.py:_render_sweep_context` will provide the original
focused description and the proposed steps, so the split sweep can compare a
location against the property and its enforcement boundary before returning a
recommendation. Route 3 returns `defer` and makes no focused-plan mutation.
Detail places a find only under the same rule and otherwise records its
deferral for reconcile.

`detail.py:_render_step_sweep_context` will likewise receive the rendered,
per-step scope fence before it invokes the split foundational-logic sweep. Both
serial and concurrent detail paths will render that existing fence before the
sweep, so it classifies a find against the focused property and enforcement
boundary rather than a title or file list alone. This only changes input to the
existing split sweep; it creates no route state or plan-wide handoff.

`defer` has mode-specific persistence. Split create returns it as a fail-closed
classification: it adds no step, file, plan-body entry, or durable record;
BACKLOG #336 owns the later manual handoff. Detail in either mode may put the
same finding in its step detail's `## Deferred` section for reconcile, with the
reason it remains out of the step. That note neither changes the focused plan
graph nor creates, orders, or approves a separate plan.

The plan body records a resulting owner or boundary only when it matters to the
observable property or existing scope fence. This plan adds no routine decision
section, new frontmatter field, route carrier, durable split-create deferral,
or numeric consumer threshold. BACKLOG #336 owns the later manual handoff from
a split-create `defer` result to a separately intentional plan. The author must
compare semantic reach with the property and its enforcement boundary, not with
the number of files or callers a proposed implementation touches.

## Scope guardrails

A shared file, helper, or owner is not cross-cutting merely because it is
shared. Reuse it unchanged when it already satisfies the focused property; do
not clone it merely to make a plan look local. A focused plan may use a local
adapter or bounded additive extension only when it keeps existing consumer
behavior and existing schema interpretation unchanged. A change to shared
authority, lifecycle, identity, precedence, schema interpretation, or
existing-consumer behavior is a separately intentional prerequisite or deferred
plan, never a hidden arm of the focused vertical plan.

This applies in both authoring modes. A foundational-logic sweep's relation or
file count never proves shared semantic reach. Do not change CLI mode selection,
the sweep result schema, or the merge mechanics merely to carry a route choice;
the affected prompts make the decision from their existing context. In this
stage, split-create `defer` is fail-closed: it prevents a focused-plan expansion
but creates no durable handoff. Detail may retain a reconcile-only `## Deferred`
note without changing the plan graph. BACKLOG #336 deliberately owns the
distinct split-create handoff capability.

## References

- [Prompt engineering overviewhttps: — Explains when prompt changes are appropriate and how success criteria and empirical tests guide prompt refinement.
- [Prompting best practiceshttps: — Covers clear instructions, contextual rationale, examples, scope control, and avoiding unnecessary abstractions in Claude prompts.
- [Define success criteria and build evaluationshttps: — Describes measurable success criteria and task-specific automated evaluations suitable for prompt-contract testing.
- [How to parametrize fixtures and test functionshttps: — Documents pytest parametrization for expressing the three authoring routes as focused independent test cases.
- [How to write and report assertions in testshttps: — Documents pytest assertions and failure introspection for precise prompt-contract fixture diagnostics.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A conceptual-audit or detail-quality mechanism-reach finding; stage 02 owns
  that lens.
- A new shared runtime mechanism, registry, policy, identity model, migration,
  or consumer update.
- A generic scope-control framework, automatic rewrite, or automatic plan
  split.
- A requirement to duplicate a suitable shared structure locally.
- A durable split-create deferral record, automatic follow-up seed, or separate
  plan creation; BACKLOG #336 owns the manual handoff.

## Risks

- Treating shared file placement as shared semantic reach would reject useful
  reuse. The prompts classify the changed contract and affected behavior, not
  file count or consumer count.
- Treating any extension as cross-cutting would suppress a safe focused change.
  The bounded-extension route remains available when it is compatible with
  current consumer behavior and schema interpretation; an available adapter
  does not by itself make that extension cross-cutting.
- Updating only the default prompt would leave split-mode sweeps as a widening
  path. The same contract applies before combined or split authoring adds,
  places, or defers a shared-location find.
- Giving a split sweep only titles and paths would make a semantic decision
  from file placement. Create receives the focused description and
  proposed-step boundary; detail receives the rendered per-step scope fence
  before it classifies. Neither context carries route state or a follow-up
  plan.
- An ambiguous authoring rule would become generic proportionality prose. The
  tests pin the three routes, their bounded-extension eligibility, and the
  fail-closed deferral boundary across both authoring modes.

## Testing

Prompt-contract fixtures will prove that create's initial-step, body, and
foundational-logic sweep surfaces, plus combined and split detail drafting,
independently state all three routes from their existing context. Each fixture
fails when its route's rule is removed: existing common reuse remains allowed,
a local adapter or compatible bounded extension remains allowed, and a changed
shared semantic contract is left out of the focused plan. Split-create fixtures
also prove that the sweep receives the focused description and proposed-step
boundary, and that `defer` adds neither a consolidation step nor a file.
Detail fixtures prove that a deferred find may appear only in its `## Deferred`
reconcile note and cannot change the plan graph; split-detail fixtures also
prove the sweep receives the rendered scope fence before it classifies. Existing
prompt rendering, CLI mode selection, and sweep merge mechanics remain
unchanged outside the added guidance.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Combined and split create paths, including the foundational-logic sweep, and
  combined and split detail paths independently apply the same reach rule from
  their existing scope context and direct a focused property to reuse a
  suitable current common owner without requiring a duplicate local mechanism.
- Every split sweep receives the focused property and enforcement boundary
  before it classifies a shared-location find: create receives the description
  and proposed-step boundary, and detail receives the rendered per-step scope
  fence.
- Every authoring surface retains a local-adapter or compatible bounded-
  extension route that preserves current consumer behavior and schema
  interpretation.
- Every authoring surface leaves a required change to shared semantics out of
  the focused plan; BACKLOG #336 owns a later durable manual handoff.
- A split-create `defer` adds no consolidation step, file, plan-body entry, or
  durable handoff. A detail `defer` may add only a reconcile-only `## Deferred`
  note and never expands the plan graph.
- No authoring surface uses file count or a numeric consumer threshold as the
  reach decision.
- No new plan schema, parser, route carrier, audit finding, command flag, or
  automatic rewrite ships in this stage.

## Deferred

- BACKLOG #336 adds the durable manual handoff from a split-create deferred
  shared semantic change to a separately intentional plan.
- BACKLOG #335 adds a high-precision, manual-only audit lens for explicit
  unjustified shared semantic commitments after this authoring vocabulary
  ships.
