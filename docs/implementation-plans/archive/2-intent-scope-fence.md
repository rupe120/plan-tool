> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Intent Scope Fence
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add optional intent fields to Plan and Step
  files:
  - plan_tool/schema.py
  - tests/test_parser.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/intent-scope-fence/01-optional-intent-fields-plan-step.md
  status: done
- id: 2
  title: Add an advisory check that flags a missing or placeholder intent
  files:
  - plan_tool/review.py
  - tests/test_review.py
  - tests/cli/test_completeness_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/intent-scope-fence/02-advisory-check-that-flags-missing.md
  status: done
- id: 3
  title: Move the plan scope-fence rendering into a shared leaf module
  files:
  - plan_tool/detail.py
  - plan_tool/create.py
  - tests/test_detail.py
  - tests/test_create.py
  creates:
  - plan_tool/scope_fence.py
  - tests/test_scope_fence.py
  complexity: medium
  change_type: refactor
  detail: docs/implementation-plans/plan-details/intent-scope-fence/03-move-plan-scope-fence-rendering-shared.md
  status: done
- id: 4
  title: Render the plan and step intent in the shared fence and pass it to the detail
    prompt
  files:
  - plan_tool/scope_fence.py
  - plan_tool/detail.py
  - plan_tool/prompts/detail.md
  - plan_tool/prompts/detail-jira.md
  - tests/test_scope_fence.py
  - tests/test_detail.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 3
  detail: docs/implementation-plans/plan-details/intent-scope-fence/04-render-plan-step-intent-shared-fence.md
  status: done
- id: 5
  title: Pass both fence halves into the run and run-jira prompts through renderer.py
  files:
  - plan_tool/renderer.py
  - plan_tool/prompts/run.md
  - plan_tool/prompts/run-jira.md
  - tests/test_renderer.py
  - tests/test_launcher.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  detail: docs/implementation-plans/plan-details/intent-scope-fence/05-pass-both-fence-halves-run-run-jira.md
  status: done
---

# Intent Scope Fence

## Overview

A plan's scope fence has two halves. The negative half — what not to build —
already travels: the plan body's `## Out of scope` reaches the `detail` prompt
as authoritative input. The positive half — what the work is *for* — is prose
that each stage re-infers, recorded in no machine-readable field.

This plan makes the positive half a field and gives it the same delivery
mechanism as the negative one, into the `detail` and `run` prompts. Presence is
advisory, so every plan already on disk keeps parsing and no migration ships.

**The point is that a stated why is in the conversation with the model doing
the work.** That is the whole value. The tool checks that an intent is there
and checks nothing else.

## Problem statement

**Intent is asserted at every altitude and persists at none that a machine
reads.**

The seed states it, the plan body states it, the detail file states it as a
*blocking* required section (`## Why` at run grade, `## Intent` at jira grade),
and the jira story states it. But neither `Plan` nor `Step` carries a rationale
field: the frontmatter this project calls its machine-readable source of truth
records *what* a step does and never *why*.

Two costs follow.

**The why is re-derived, not carried.** Each `detail` pass reconstructs a
step's motivation from plan prose and the step title. A why settled during
`create`'s change-type review, or argued through a completeness round, survives
only as long as the detail file it happened to land in.

**Only the negative half is data.** "What not to build" propagates to `detail`
as an authoritative block; "what this is for" propagates nowhere. And `run`
receives neither half — on the one surface that actually writes code.

## Architecture

**Fields, not sections.** Plan and step each carry an optional one-line
`intent`, so every plan on disk keeps parsing. The advisory finding, not the
schema, is what asks for one.

**Presence, and only presence.** The check asks whether an intent is there. It
does not judge whether the intent is good, and no length or content rule ships
beyond dropping an empty or placeholder value. It surfaces in the advisory
smell bucket and is deliberately **not apply-eligible** — it can never reach
`apply_finding` or flip an exit code.

**One whitespace rule, stated once.** Every producer collapses an intent to a
single line before rendering it. This is a correctness rule, not tidying: a
value containing a real newline could otherwise put `##` at line start and
forge a heading inside a markdown prompt.

**The guard is threading, not checking.** What discourages creep is the intent
reaching the model doing the work as authoritative input — the mechanism
`## Out of scope` already uses, with the sign reversed. Both detail grades and
both run grades receive it through one shared renderer. With no intent set,
every rendered prompt is byte-identical to today's.

## Scope guardrails

**This plan's intent — every step serves it or does not belong.** Put a stated
*why* in front of the model doing the work, and validate only that one is
present.

### Presence is the entire contract

The tool may check that an intent **exists**. It may not check anything else.
This is the plan's central rule, so it is written out rather than implied:

- **Allowed:** is the field there; is it non-empty after whitespace collapse;
  is it a bare placeholder (`TODO`).
- **Not allowed — no step may add any of these, now or later:**
  - judging whether an intent is *good*, specific, or well written;
  - comparing an intent against the step's `## Why`, the plan body, a detail
    file, an acceptance criterion, or any other prose;
  - comparing an intent against the diff a step produces;
  - a length cap, a truncation, a required shape, a grammar or phrasing rule;
  - any gate, exit-code flip, or refusal-to-advance keyed on an intent.

**Why the line is exactly here.** Anything past presence is unfalsifiable at
audit time and becomes prose-conformance checking — the failure recorded in
CLAUDE.md § "Withdrawn: the per-`change_type` test-ordering contract", where a
checker enforced that a document used the right *vocabulary* about a property
most steps could not have, ran at an ~85% false-positive rate, and taught
operators to ignore the finding channel. Presence is mechanically observable.
Quality is not. The tool asserts only what it can actually see.

### The other two fences

- Nothing becomes required at parse time, and no plan already on disk is
  migrated or rewritten.
- Delivery originally stopped at the `detail` and `run` prompts. Other
  consumers, and propagation through the structural verbs, were carved out
  2026-08-01; that residual is **discharged** by
  `docs/implementation-plans/2-intent-structural-propagation.md` (2026-08-03)
  — see `## Deferred`.

## References

_(carried from the pre-carve plan; the YAML and prompt-engineering sources
remain the ones steps 1–5 rely on)_

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — safe_load/safe_dump, scalar styles, and key ordering: the round-trip semantics that decide whether adding a frontmatter field rewrites existing plan files.
- [YAML Ain't Markup Language (YAML™) revision 1.2.2](https://yaml.org/spec/1.2.2/) — the normative spec on scalar styles, line folding, and quoting, which defines what "one line" means for the field and how a multi-line value is detected.
- [Use XML tags to structure your prompts — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/use-xml-tags) — delimiting authoritative prompt sections, the mechanism the shared renderer uses to carry both fence halves.
- [Long context prompting tips — Claude Docs](https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/long-context-tips) — where authoritative context should sit relative to instructions in the already-long detail and run prompts.
- [How to parametrize fixtures and test functions — pytest](https://docs.pytest.org/en/stable/how-to/parametrize.html) — table-driven cases, used to assert byte-identical prompts when no intent is set.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Any validation beyond presence.** Enumerated in `## Scope guardrails`
  above. Permanently refused — not deferred to a follow-up entry.
- Making intent required at parse time; any migration or backfill.
- Changing the required detail sections at either grade. `## Why` and
  `## Intent` stay exactly as they are.
- Delivery to any consumer past the `detail` and `run` prompts, and propagation
  through `split` / `merge` / `scope-out` / `reground` — carved out
  2026-08-01; **discharged** 2026-08-03 by
  `docs/implementation-plans/2-intent-structural-propagation.md` (see
  `## Deferred`).
- **Allowed behavior changes:** two optional frontmatter fields; one advisory
  finding class; rendered input reaching four templates — `detail.md`,
  `detail-jira.md`, `run.md`, `run-jira.md`. The run lane additionally gains the
  plan's existing guardrail and `## Out of scope` sections **whether or not an
  intent is set**, because it carries neither today. Nothing else.
- **Allowed reorganization:** one named move — extract the plan scope-fence
  renderer out of `plan_tool/detail.py` into a shared leaf
  (`plan_tool/scope_fence.py`, step 3). **Blocker:** `detail.py` already
  imports `plan_tool.launcher` (`detail.py:100`), so `launcher` / `renderer`
  cannot import the renderer back out of `detail` without a cycle, and the
  Outcome requires `detail` and `run` to render the same fence. Nothing else
  moves.

**Widened from BACKLOG #206 — recorded, not silent.** On an explicit user
decision (2026-07-31) this plan reverses two of #206's limits: it ships a
plan-altitude `Plan.intent` (#206 non-goals it), and an advisory presence check
(#206 scopes none). #206's *"making `intent` required on existing plans"*
non-goal is **not** widened, and its duplication call — intent is a one-line
seed the prompts consume, never re-checked against `## Why` — is kept verbatim
and reinforced by the presence-only rule above. Step 11 of the carved seed
carries the obligation to preserve this record when #206 is closed.

## Risks

- **A stale intent is worse than an absent one.** This plan deliberately did
  not touch the structural verbs, so an intent could outlive the step it
  described. That structural-verb / conceptual-audit residual is **discharged**
  by `docs/implementation-plans/2-intent-structural-propagation.md` (2026-08-03).
  The remaining residue is `BACKLOG.md` #212 (`apply_finding` can still leave
  a stale intent after a prose rewrite) — open, and out of that discharge.
- **Advisory volume on first run.** Every existing plan lacks both fields, so
  the check fires everywhere. Its severity must keep it out of the blocking
  path, or the channel gets ignored — the same failure the withdrawn contract
  documents.
- **The one-line rule ships in more than one module.** Each copy is pinned by a
  test to the single rule in `## Architecture`; consolidating them is a backlog
  item, not a later step here.

## Testing

- A plan with **neither an intent nor any fence section** parses, details, and
  runs exactly as today, with byte-identical prompts. The claim is scoped that
  narrowly on purpose: step 5 gives the run lane the plan's guardrail and
  `## Out of scope` sections regardless of intent, so a plan already carrying
  `## Out of scope` **does** gain that block — a deliberate delivery, not a
  regression.
- A plan carrying intent renders it into all four templates.
- Absence and placeholder each surface advisorily, and never refuse a run or
  flip an exit code on their own.
- A newline-bearing intent cannot forge a heading in any rendered block.
- **No test asserts anything about an intent's content or length** — the
  presence-only rule holds in the test suite too, not just in prose.
- The full suite passes with no edits to existing plan fixtures. That is the
  proof no migration is needed.

## Acceptance criteria

- Plans and steps can carry a one-line `intent`; absence is advisory only, and
  the advisory is not apply-eligible.
- **Nothing anywhere validates an intent beyond its presence** — no quality
  judgment, no agreement check, no length cap, no gate.
- Intent reaches both detail grades (`detail.md`, `detail-jira.md`) and both
  run grades (`run.md`, `run-jira.md`) through one shared renderer.
- Every producer collapses an intent to one line before rendering it, pinned by
  a test that a newline-bearing intent cannot forge a heading.
- Every existing plan parses, details, and runs unchanged — with the one stated
  exception that a plan already carrying `## Out of scope` gains that block in
  its run prompt.
- **This plan carries its own intent — adopted after the run, never inside
  it.** Once the plan's steps are green, this plan's frontmatter carries an
  `intent:` on the plan and on all five steps. Proof is a direct frontmatter
  check over all five steps; `plan-tool validate` is a supporting signal only,
  since it skips `done` steps.

  **Do not put the plan file in any step's footprint to do this.** A step that
  writes `intent:` into a plan file from inside the same `plan-tool run` that
  adds the field to `schema.py` silently loses it: the parent `run` process
  imported `plan_tool.schema` before the subprocess edited it, so its in-memory
  `Plan` / `Step` carry no `intent` for the life of the process, and
  `extra="forbid"` means the end-of-step plan rewrite strips the key that was
  just written. The adoption must happen in a **later invocation** — a separate
  `run`, or by hand — not in a later step of the same one.

## Deferred

- **Carve of 2026-08-01** (original dump:
  `plan-seeds/archive/intent-scope-fence-carved-fill-the-plan-s-intent-from-through-11.md`).
  **Partially discharged:** `create` authoring + reference-doc sweep shipped
  via `2-intent-required`. **Discharged** 2026-08-03: propagation across the
  four structural verbs and delivery to the conceptual-audit prompt shipped
  by `docs/implementation-plans/2-intent-structural-propagation.md` (seed
  `plan-seeds/intent-structural-propagation.md` is superseded). Carved
  because the plan had grown past its own Outcome — eleven steps for a
  two-field feature — not because that work is unwanted.
- **Any validation beyond presence.** Permanently refused, not deferred; see
  `## Scope guardrails`.
- The rest of BACKLOG #162 — the seed/backlog scope contract as an
  authoritative audit-prompt block.
