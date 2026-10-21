> **Replaced**: this file has been superseded by `docs/implementation-plans/2-mechanism-reach-01-authoring.md`.
> Preserved here for history; do not edit.

# Mechanism reach 01: authoring

## Outcome

`create` and `detail` will choose the smallest owner that makes a focused
property true: reuse a suitable existing common structure unchanged, use a
local adapter or bounded additive extension when it preserves existing
consumer behavior, or defer a required shared semantic change to a separately
intentional plan.

## In scope

- The proportionality and mechanism-axis guidance in
  `plan_tool/prompts/synthesize-body.md` and `plan_tool/prompts/detail.md`.
- Focused create/detail prompt-contract fixtures that pin the selected
  authoring decision.
- BACKLOG #334 and
  `docs/implementation-plans/backlog-arcs/backlog-arc-mechanism-reach.md` as
  the source contract and ordered-stage record.

## Scope guardrails

A shared file, helper, or owner is not cross-cutting merely because it is
shared. Reuse it unchanged when it already satisfies the focused property; do
not clone it merely to make a plan look local. A focused plan does not change
shared authority, lifecycle, identity, precedence, schema, or existing-consumer
behavior unless the named property cannot hold through an unchanged common
owner, a local adapter, or a bounded additive extension. That semantic change
is a separately intentional prerequisite or deferred plan, never a hidden arm
of the focused vertical plan.

## Overview

The existing synthesis and detail prompts already prefer a proportionate
mechanism over a speculative framework. This effort makes their decision
sequence explicit so a plan can use the common structure that already owns a
property without promoting ordinary reuse into a cross-cutting change. When
the property truly needs a changed shared contract, the prompts keep that work
visible as intentional later work instead of letting it expand a focused plan.

## Problem statement

Current proportionality guidance can reject an unnecessary rule engine or
adjacent capability but does not distinguish reuse of an established common
owner from a change to that owner's contract. An author can therefore either
clone a suitable common structure to appear local or enlarge a focused plan
with repository-wide identity, policy, or consumer work justified only by
future reuse. Neither result follows from the requested property.

## Architecture

The authoring prompts will require one private decision whenever a focused
property reaches a common structure:

1. Reuse the existing owner unchanged when its current contract satisfies the
   property.
2. Otherwise keep the focused plan at a local adapter or bounded additive
   extension when current consumers retain their behavior.
3. Otherwise state the shared semantic contract that must change and defer it
   to a separate prerequisite or backlog seed.

The plan body records only the resulting owner, boundary, and deferral when
they matter to the observable property. It adds no routine decision section,
new frontmatter field, or numeric consumer threshold. The author must compare
semantic reach with the property and its enforcement boundary, not with the
number of files or callers a proposed implementation touches.

## Out of scope

- A conceptual-audit or detail-quality mechanism-reach finding; stage 02 owns
  that lens.
- A new shared runtime mechanism, registry, policy, identity model, migration,
  or consumer update.
- A generic scope-control framework, automatic rewrite, or automatic plan
  split.
- A requirement to duplicate a suitable shared structure locally.

## Risks

- Treating shared file placement as shared semantic reach would reject useful
  reuse. The prompts classify the changed contract and affected behavior, not
  file count or consumer count.
- Treating any extension as cross-cutting would suppress a safe focused change.
  The bounded-extension route preserves current consumer behavior and remains
  available only when a local adapter cannot deliver the property.
- An ambiguous authoring rule would become generic proportionality prose. The
  tests pin the three routes and the explicit deferral boundary.

## Testing

Prompt-contract fixtures will prove that the synthesis and detail prompts state
all three routes. Each fixture fails when its route's rule is removed: existing
common reuse remains allowed, a local adapter remains allowed, and a changed
shared semantic contract is deferred. Existing prompt rendering and command
flow remain unchanged outside the added guidance.

## Acceptance criteria

- `create` and `detail` direct a focused property to reuse a suitable current
  common owner without requiring a duplicate local mechanism.
- Both prompts retain a local-adapter or bounded-extension route that preserves
  current consumer behavior.
- Both prompts direct a required change to shared semantics into a separately
  intentional prerequisite or deferred plan.
- Neither prompt uses file count or a numeric consumer threshold as the reach
  decision.
- No new plan schema, parser, audit finding, command flag, or automatic rewrite
  ships in this stage.

## Deferred

- BACKLOG #335 adds a high-precision, manual-only audit lens for explicit
  unjustified shared semantic commitments after this authoring vocabulary
  ships.
