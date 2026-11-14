# Plan seed: A `--from-existing` seed must state its guardrails, even as `None`

## Outcome

`create --from-existing` refuses, before any model call, a seed missing any of
the three guardrail headings or carrying one that is duplicated, empty or a
placeholder, and accepts a heading whose body is an explicit `None`.

## Overview

A seed's three author-supplied guardrail headings (`## Scope guardrails`,
`## Audit guardrails`, `## Expected placement`) are copied verbatim into the
plan and threaded into the `detail` and `run` prompts as a hard fence that
overrides model output (`scope_fence.py:GUARDRAIL_BODY_SECTIONS`, rendered
through `renderer.py` into `prompts/detail.md` and `prompts/run.md`). They are
optional today, so a seed with no fence and a seed whose author forgot the
fence read the same. Requiring each heading, with `None` as a valid answer,
proves the question was asked. The tools that write seeds populate the headings
so their output passes the new check. Source entry: BACKLOG #532. No Jira key.
The plan's final step removes #532 when the work ships.

## Problem statement

`create.py:classify_file_backed_source` refuses only a missing, duplicate, empty
or placeholder `## References`. The guardrail headings are labelled
"conditional" in `create.py:OPTIONAL_PLAN_BODY_SECTION_SHAPES`, and an absent
one is not rendered. On 2026-11-14, before this seed, 2 of 28 live seeds carried
`## Scope guardrails` and none carried all three. Four tools write seeds into
the seed directory and none writes these headings:

- `roadmap.materialize_plan_seed` (`roadmap --materialize` / `--refresh-seeds`),
  whose seed body is model-written from `prompts/roadmap-seed.md`;
- `annotate_render.render_create_seed`, which renders a seed from the
  annotation that `annotate`'s one model call per file produces;
- `scope_out.render_carved_seed` and `render_carved_region_seed`, deterministic
  renderers over the source plan;
- `reground.render_rebaseline_seed`, a deterministic renderer over the source
  plan.

None of the four runs `create` itself; each prints the `create --from-existing`
command for the operator.

## Architecture

- **Presence is the whole check.** The refusal sits beside the `References`
  check in the file-backed intake (`validate_from_existing_seed`, called by the
  CLI before slug inference and any model call) and uses the same rule: exactly
  one heading, non-empty, not a placeholder. The message names every missing or
  malformed heading at once. Every caller of the shared intake inherits it.
- **`None` is an answer, not a placeholder.** `scope_fence._is_placeholder_section`
  matches only `TODO` forms, so a body of `None` already reads as content, and
  the fence renderer already carries it verbatim. Keep both, so a reader of the
  plan or a prompt sees that the author stated "no fence".
- **Each seed-writing tool populates all three headings, from the source it
  already has, with no new model call:**

  | Tool | Source of the guardrail content |
  | --- | --- |
  | `roadmap --materialize` / `--refresh-seeds` | `prompts/roadmap-seed.md` requires the three sections in the draft, written from the accepted roadmap's plan row, with `None` where the row sets no fence. A draft missing one fails the same check. The operator reviews it at `--accept-seed`. |
  | `annotate` | The source plan's guardrail sections, copied verbatim when it has them; otherwise the existing `annotate` call writes them from the source and its judgment. |
  | `scope-out`, `reground` | The source plan's guardrail sections, copied verbatim. |

  A deterministic renderer whose source plan carries no guardrail heading (a
  plan that predates this change) writes `_(TODO)_` under it, which `create`
  refuses, and its printed next step says to fill the heading in. This is the
  only case left to a hand edit, because filling it would need a model call the
  renderer does not make.
- **Inherited guardrails are reviewed, not trusted.** A carved or rebaselined
  seed's inherited fence can be wrong for the narrower plan (a parent's guardrail
  may exclude the very region carved out). The tool's printed next step names
  the inherited headings for review before `create`.
- **Order:** the four tools populate the headings, and the live seeds are swept,
  before the refusal turns on, so no shipped tool writes a seed the tool refuses.

## In scope

- The file-backed intake check and its refusal message.
- Tests that an explicit `None` guardrail survives into the plan body and the
  downstream fence.
- The four seed-writing tools above, their prompts where they have one
  (`roadmap-seed.md`, `annotate.md`), their printed next steps, and their tests.
- The live seeds in `docs/implementation-plans/plan-seeds/` and `plan-seeds/`,
  each populated by hand from its own content.
- Test fixtures that feed `--from-existing` a seed.
- `SEED_FORMAT.md`, `PLAN_FORMAT.md` § "Scope fence",
  `docs/how-to/pipeline/create-from-existing.md` and `ROADMAP_FORMAT.md`'s draft
  seed contract, which today describe the headings as optional or omit them.
- Removal of BACKLOG #532 in the final step.

## Out of scope

- The tool-written `## Stack` heading, which only `roadmap` writes.
- Requiring `## Outcome` or `## In scope`, which have no guardrail capture; that
  is a separate decision.
- Inline `--from` and `--from-plan`, which have no seed file to hold a heading.
- Archived seeds, which are not inputs to a future `create`.
- A new model call in any tool to compose guardrails.
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
- Seed-writing tools populate guardrails only from a source they already read
  or a model call they already make; none gains a new model call.

## Audit guardrails

None.

## Expected placement

None.

## Allowed behavior changes

The new refusal and its message; the four seed-writing tools write the three
headings, and their printed next steps name inherited or unfilled headings.

## Allowed reorganization

None.

## Risks

- **Breaking existing seeds:** every live seed and every on-disk tool-written
  seed without the headings stops working. The tool changes and the sweep land
  before the refusal.
- **A wrong inherited fence:** a carved seed can inherit a guardrail that
  contradicts its own scope. The printed next step asks for review; the tool
  does not try to judge it.
- **`None` read as empty downstream:** a consumer that treats a `None` body like
  an absent section loses the distinction the change exists for. Test that the
  fence carries it.
- **Fixture churn:** minimal seeds in tests go red. That is expected, not a
  reason to narrow the rule.

## Testing

A seed missing any one heading is refused with no model call, and the message
names it; duplicated, empty and `TODO` headings are refused; a seed missing two
headings names both. A `None` heading is accepted and appears verbatim in the
plan and the downstream fence. A seed from each of the four tools passes the
check when its source carries guardrails, and a deterministic renderer over a
source plan without them writes `_(TODO)_` that the check refuses. Every live
seed passes it. Break the check and confirm each refusal test goes red, and
assert that `None` stays outside the placeholder pattern.

## Acceptance criteria

- `create --from-existing` refuses a seed missing, duplicating, emptying or
  placeholding any of the three guardrail headings, before any model call, and
  names each offending heading.
- A heading whose body is `None` is accepted and appears verbatim in the plan
  and the downstream fence.
- `roadmap --materialize`, `annotate`, `scope-out` and `reground` write all
  three headings from their existing sources, with `_(TODO)_` only where a
  deterministic renderer's source plan has none.
- Every live seed in both seed directories passes the check.
- The docs describe the headings as required.
- BACKLOG #532 is removed in the final step.

## Deferred

Requiring `## Outcome` and `## In scope` waits for its own decision.

Stop / defer: any out-of-scope discovery is filed in BUG_BACKLOG.md (defect) or
BACKLOG.md (forward work), never applied as plan expansion.

## References

- BACKLOG #532
- `plan_tool/create.py` (`classify_file_backed_source`,
  `validate_from_existing_seed`, `OPTIONAL_PLAN_BODY_SECTION_SHAPES`)
- `plan_tool/scope_fence.py` (`GUARDRAIL_BODY_SECTIONS`, `_is_placeholder_section`,
  `render_scope_fence`)
- `plan_tool/roadmap.py` (`materialize_plan_seed`) and `prompts/roadmap-seed.md`
- `plan_tool/annotate_render.py` (`render_create_seed`) and `prompts/annotate.md`
- `plan_tool/scope_out.py` (`render_carved_seed`, `render_carved_region_seed`)
- `plan_tool/reground.py` (`render_rebaseline_seed`)
- `SEED_FORMAT.md`; `PLAN_FORMAT.md` § "Scope fence";
  `docs/how-to/pipeline/create-from-existing.md`; `ROADMAP_FORMAT.md`
