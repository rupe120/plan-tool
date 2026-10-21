> **Replaced**: this file has been superseded by `docs/implementation-plans/2-intent-scope-fence.md`.
> Preserved here for history; do not edit.

# Plan seed: `intent` — the positive half of the scope fence

> Source: BACKLOG **#206** (2026-07-30), widened on an explicit user decision
> (2026-07-31) — see *Divergence from #206*. The resulting plan's **final step
> must close #206**; authoring the plan alone does not touch the entry.

## Divergence from #206

- *"a plan-altitude intent field"* — **lifted**. Plans carry intent too.
- *"making `intent` required on existing plans"* — **reaffirmed**. Presence is
  advisory; nothing becomes required and no migration ships.

Two surfaces #206 does not scope are added: the presence check, and carrying
the fence into `run`.

#206's duplication call is **kept verbatim**: intent is a one-line seed the
prompts consume, never re-checked against the detail's `## Why`.

## Overview

A plan's scope fence has two halves. The negative half — what not to
build — is already durable and already travels: the plan body's
`## Out of scope` reaches the detail prompt as authoritative input. The
positive half — what the work is *for* — exists only as prose that each stage
re-infers, and is recorded in no machine-readable field at any altitude.

This plan makes the positive half a first-class carrier and gives it the same
delivery mechanism as the negative one. Presence is advisory, so nothing on
disk changes and no migration ships.

## Outcome

A plan's and a step's *why* is stated once in the plan file and reaches every
model that acts on it — `detail` and `run` — as authoritative input, with
absence surfaced advisorily and no existing plan changed.

## Problem statement

**Intent is asserted at every altitude and persists at none of the ones a
machine reads.**

The seed states it, the plan body states it, the detail file states it as a
*blocking* required section (`## Why` at run grade, `## Intent` at jira
grade), and the jira story states it. But neither `Plan` nor `Step` carries a
rationale field: the frontmatter the project calls its machine-readable source
of truth records *what* a step does and never *why*.

Three costs follow.

**The why is re-derived, not carried.** Each `detail` pass reconstructs a
step's motivation from plan prose and the step title. Any structural edit —
split, merge, scope-out, reground — regenerates it rather than carrying the
decision that produced the step. A why settled during `create`'s change-type
review, or argued through a completeness round, survives only as long as the
detail file it happened to land in.

**Only the negative half is data.** "What not to build" propagates to `detail`
as an authoritative block. "What this is for" propagates nowhere.

**`run` receives neither half.** It gets a footprint and a detail file, and
nothing stating the boundary — on the one surface that writes code, where
creep is most expensive.

The same defect recurs one altitude up, and this plan closes that hop too: a
seed's `## Outcome` reaches `create`'s step proposal and nothing after it,
because it is neither a plan-body section nor a guardrail section. It is read
once and dropped.

## Architecture

**Fields, not sections.** Plan and step each carry a one-line intent. Optional,
so every plan on disk keeps parsing — the advisory finding, not the schema, is
what asks for it.

**Presence is advisory, and only presence.** The check asks whether an intent
is there and within its cap. Nothing anywhere judges whether it is *good*. It
joins the existing body-completeness advisory channel rather than becoming a
gate of its own.

**The guard is threading, not checking.** What prevents creep is the intent
reaching the model doing the work as authoritative input — the mechanism the
negative half already uses, with the sign reversed. Both halves travel
together, through one renderer, to both `detail` and `run`. With no intent
set, the rendered prompts are unchanged.

**Propagation is the work.** Each of the four structural verbs owes a stated
rule, written as contract rather than left to whatever the code happens to do.
Every rule must be able to *clear* the field: a carried intent that a split
made false reads as authoritative while being wrong, which is worse than none.

The negative half's continuity through `create` already shipped
(`docs/implementation-plans/2-scope-fence-continuity.md`, completed). This is
its sibling and must extend that machinery, never duplicate it.

## Scope guardrails

**This plan's intent — every step serves it or does not belong.** Make a
plan's and a step's *why* durable data that reaches every model acting on it,
without invalidating a single plan already on disk. The guard is that intent
**travels**, never that something checks it.

Two rules bind every step:

- Nothing becomes required at parse time, and no plan on disk is migrated.
- No step ships a check comparing an intent against prose or against a diff.

## Audit guardrails

Findings proposing that intent be made required, that an agreement check be
added, or that propagation widen past the four structural verbs are outside
this fence **by construction** — defer them to `BACKLOG.md` rather than
applying them as plan expansion.

A finding that this plan's own artifacts fail to carry their intent **is** in
scope: it is the plan's thesis applied to itself.

## In scope

Surfaces, not files — `detail` locates those.

- The two fields, and the one-line cap.
- The advisory presence check.
- One renderer carrying both fence halves to `detail` and to `run`.
- Authoring: `create` proposes a step intent, and fills a plan's from the
  seed's `## Outcome`.
- A propagation rule for each of the four structural verbs. Naming all four is
  the boundary — a plan covering three has missed one.

## Out of scope

- **An intent-vs-work agreement check, at any altitude** — not intent vs plan
  prose, not intent vs a detail's `## Why`, not intent vs the diff a step
  produces. Precedent: CLAUDE.md § "Withdrawn: the per-`change_type`
  test-ordering contract" — a checker validating *prose conformance* to a
  contract most steps could not satisfy read as rigor, delivered none, and at
  an ~85% false-positive rate trained operators to ignore the finding channel.
  #206 reaches this conclusion independently. Refuse it if audits surface it.
- Making intent required at parse time; any migration or backfill.
- Changing the required detail sections at either grade.
- Threading intent into the jira export — the story summary already covers it.
- Promoting the remaining scope-contract fields to schema-checked plan
  sections (deferred by BACKLOG § "Scope contract and anti-creep").
- **Allowed behavior changes:** two optional frontmatter fields; one advisory
  finding class; two prompts gain rendered input when the fields are set.
  Nothing else.
- **Allowed reorganization:** none.

## Risks

- **A prose field invites paragraphs.** The one-line cap is the answer, and
  over-length is advisory like absence — a mechanical property, unlike quality.
- **A stale intent is worse than an absent one.** Hence the clearing
  requirement on every propagation rule.
- **Two carriers can diverge.** One renderer, two callers.
- **Advisory volume on first run:** every existing plan lacks both fields, so
  the check fires everywhere. If its severity lands in the blocking path the
  channel gets ignored — the failure the withdrawn contract documents.

## Testing

- A plan with no intent parses, details, and runs exactly as today, with
  byte-identical prompts.
- A plan carrying intent renders it into both prompts.
- Absence, placeholder, and over-length each surface advisorily, and never
  refuse a run or flip an exit code on their own.
- Each structural verb leaves every surviving step with a defensible value —
  carried, composed, or cleared, never silently false.
- The full suite passes with no edits to existing plan fixtures. That is the
  proof no migration is needed.

## Acceptance criteria

- Plans and steps can carry a one-line intent; absence is advisory only.
- Intent reaches both the `detail` and `run` prompts through one renderer.
- `create` proposes step intents and fills a plan's from the seed's Outcome.
- The format doc states both fields and each structural verb's propagation
  rule.
- Every existing plan parses, details, and runs unchanged.
- No agreement check ships.
- **This plan carries its own intent.** Once the fields exist, this plan's
  frontmatter and every one of its steps declare one — the first consumer of
  the feature is the plan that adds it.
- BACKLOG #206 is closed or rewritten to what remains.

## Deferred

- Intent-vs-work agreement checking. If ever revisited it is its own entry,
  and must first answer what makes it different from the withdrawn contract.
- Promoting the remaining scope-contract fields to schema-checked sections.
- Jira export threading.

## Stop / defer

- If a verb's propagation rule cannot be settled without a consistency check,
  keep the field clearable there and file the check separately — #206's stop
  rule, kept.
- Out-of-scope findings route to `BACKLOG.md` / `BUG_BACKLOG.md`, never plan
  expansion.
