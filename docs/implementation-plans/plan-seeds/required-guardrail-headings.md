# Plan seed: A `--from-existing` seed must state its guardrails, even as `None`

## Outcome

`create --from-existing` refuses, before any model call, a seed missing any of
the three guardrail headings or carrying one that is duplicated, empty or a
placeholder, and accepts a heading whose body is an explicit `None`.

## Overview

A seed's guardrail headings (`## Scope guardrails`, `## Audit guardrails`,
`## Expected placement`) are the only seed content `create` copies verbatim into
the plan and carries into `detail` and `run` prompts as a hard fence
(`scope_fence.py:GUARDRAIL_BODY_SECTIONS`). They are optional today, so a seed
with no fence and a seed whose author forgot the fence read the same. Requiring
each heading, with `None` as a valid answer, proves the question was asked.
Source entry: BACKLOG #532. No Jira key. The plan's final step removes #532 when
the work ships.

## Problem statement

`create.py:classify_file_backed_source` refuses only a missing, duplicate, empty
or placeholder `## References`. The guardrail headings are labelled
"conditional" in `create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES` and an absent
one is simply not rendered. At 2026-11-14, 2 of 28 live seeds carry `## Scope
guardrails`. Two tools also write seeds without them:
`annotate_render.render_create_seed` and `roadmap` stage 4's draft seeds.

## Architecture

- **Presence is the whole check.** The refusal sits beside the `References`
  check in the file-backed intake and uses the same rule: exactly one heading,
  non-empty, not a placeholder. It runs before slug inference and before any
  model call, and the message names every missing or malformed heading at once.
- **`None` is an answer, not a placeholder.** `scope_fence._is_placeholder_section`
  matches only `TODO` forms, so a body of `None` already reads as content, and
  `scope_fence`'s fence renderer already carries it verbatim
  (`## Scope guardrails` / `None`). Keep both: a reader of the plan or a prompt
  sees that the author stated "no fence", so the omission is not ambiguous.
- **Producers emit all three headings.** `annotate_render.render_create_seed`
  is deterministic and writes each heading as `None`. A `roadmap` stage 4 draft
  seed is model-authored; the tool adds any missing heading as `None` when it
  writes the draft, the way it already inserts `## Stack`, and keeps a heading
  the model wrote, which the operator reviews when accepting the draft. Neither
  producer gains a new model call to compose a fence.
- **Order:** the producers and the live seeds gain the headings before the
  refusal turns on, so no step leaves a shipped producer writing seeds the tool
  refuses.

## In scope

- The file-backed intake check and its refusal message.
- Tests that an explicit `None` guardrail survives into the plan body and the
  downstream fence.
- `annotate`'s and `roadmap` stage 4's seed writers, and their tests.
- The live seeds in `docs/implementation-plans/plan-seeds/` and `plan-seeds/`.
- Test fixtures that feed `--from-existing` a seed.
- `SEED_FORMAT.md`, `PLAN_FORMAT.md` § "Scope fence" and
  `docs/how-to/pipeline/create-from-existing.md`, which today describe the
  headings as optional.
- Removal of BACKLOG #532 in the final step.

## Out of scope

- The tool-written `## Stack` heading, which only `roadmap` writes.
- Requiring `## Outcome` or `## In scope`, which have no guardrail capture; that
  is a separate decision.
- Inline `--from` and `--from-plan`, which have no seed file to hold a heading.
- Archived seeds, which are not inputs to a future `create`.
- Any check of what a guardrail says beyond presence: deliberately no quality
  judgment, no agreement check against `Out of scope`, no length or shape cap,
  and no exit-code change other than the refusal.

## Scope guardrails

- The only new check is presence of each of the three headings, by the same
  rule as `## References`. Do not judge, compare or cap guardrail content.
- `None` must pass. Do not add `None`, `N/A` or similar to the placeholder
  pattern.
- Do not require `## Stack`, `## Outcome` or `## In scope`, and do not touch
  inline `--from`, `--from-plan` or archived seeds.
- A seed producer fills a missing heading with `None`; it adds no model call to
  compose guardrail prose.

## Audit guardrails

None.

## Expected placement

None.

## Allowed behavior changes

The new refusal and its message; `annotate` and `roadmap` seeds gain the three
headings.

## Allowed reorganization

None.

## Risks

- **Breaking existing seeds:** every live seed and every on-disk `annotate` or
  `roadmap` seed without the headings stops working. The sweep and the producer
  change land before the refusal.
- **`None` read as empty downstream:** a consumer that treats a `None` body like
  an absent section loses the distinction the change exists for. Test that the
  fence carries it.
- **Fixture churn:** minimal seeds in tests go red. That is expected, not a
  reason to narrow the rule.

## Testing

A seed missing any one heading is refused with no model call, and the message
names it; duplicated, empty and `TODO` headings are refused; a seed missing two
headings names both. A `None` heading is accepted and appears verbatim in the
plan and the downstream fence. A seed from `annotate` and one from
`roadmap` stage 4 pass the check. Every live seed passes it. Break the check and
confirm each refusal test goes red, and assert that `None` stays outside the
placeholder pattern.

## Acceptance criteria

- `create --from-existing` refuses a seed missing, duplicating, emptying or
  placeholding any of the three guardrail headings, before any model call, and
  names each offending heading.
- A heading whose body is `None` is accepted and appears verbatim in the plan
  and the downstream fence.
- `annotate` and `roadmap` stage 4 emit all three headings.
- Every live seed in both seed directories passes the check.
- The three docs describe the headings as required.
- BACKLOG #532 is removed in the final step.

## Deferred

Requiring `## Outcome` and `## In scope` waits for its own decision.

Stop / defer: any out-of-scope discovery is filed in BUG_BACKLOG.md (defect) or
BACKLOG.md (forward work), never applied as plan expansion.

## References

- BACKLOG #532
- `plan_tool/create.py` (`classify_file_backed_source`,
  `OPTIONAL_PLAN_BODY_SECTION_SHAPES`)
- `plan_tool/scope_fence.py` (`GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`)
- `plan_tool/annotate_render.py` (`render_create_seed`); `plan_tool/roadmap.py`
  (stage 4 draft seeds)
- `SEED_FORMAT.md`; `PLAN_FORMAT.md` § "Scope fence";
  `docs/how-to/pipeline/create-from-existing.md`
