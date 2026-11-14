---
format_version: 1
title: Required Guardrail Headings
intent: '`create --from-existing` refuses, before any model call, a seed missing any
  of the three guardrail headings or carrying one that is duplicated, empty or a placeholder,
  and accepts a heading whose body is an explicit `None`.'
status: planning
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: docs/implementation-plans/plan-seeds/required-guardrail-headings.md
steps:
- id: 1
  intent: One presence rule that both the create intake and the roadmap draft gate
    can call, so the two refusals cannot disagree about what a guardrail heading needs.
  files:
  - plan_tool/scope_fence.py
  - tests/test_scope_fence.py
  complexity: low
  change_type: feature
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/01-one-shared-check-three-guardrail.md
  status: current
  description: 'Add one shared check for the three guardrail headings to `plan_tool/scope_fence.py`.
    Add a constant naming exactly `## Scope guardrails`, `## Audit guardrails` and
    `## Expected placement`. `GUARDRAIL_BODY_SECTIONS` stays as it is, because it
    also carries `Stack`, which is not required. Add a pure function that takes a
    seed''s text and returns every one of the three headings that is missing, duplicated,
    empty or a placeholder. It uses the same rule `classify_file_backed_source` applies
    to `## References`: exactly one H2 occurrence outside fenced code, a non-empty
    body, and not `_is_placeholder_section`. Leave `_is_placeholder_section` and `_SECTION_PLACEHOLDER_RE`
    unchanged, so a body of `None` counts as content. In `tests/test_scope_fence.py`:
    test each kind of offending heading; test that a seed missing two headings reports
    both; test that `None` passes while `None`, `N/A` and `none` stay outside the
    placeholder pattern; and test that a `None` guardrail body is carried verbatim
    by `render_scope_fence`. The function writes nothing and deletes nothing.'
- id: 2
  intent: Seeds carved or rebaselined from a plan carry the parent's fence forward,
    or say plainly that it still has to be written, so they pass the new check without
    anyone inventing a fence.
  files:
  - plan_tool/scope_fence.py
  - plan_tool/scope_out.py
  - plan_tool/reground.py
  - plan_tool/cli/scope_out_cmd.py
  - tests/test_scope_out.py
  - tests/test_reground.py
  - tests/cli/test_scope_out_cmd.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/02-make-scope-out-reground-write-all-three.md
  description: 'Make `scope-out` and `reground` write all three guardrail headings
    into the seeds they render. `scope_out.render_carved_seed`, `scope_out.render_carved_region_seed`
    and `reground.render_rebaseline_seed` copy each heading''s body verbatim from
    the source plan only when the step 1 predicate accepts that heading in the source
    (exactly one, non-empty, not a placeholder, with `None` accepted). In every other
    source state (absent, empty, duplicated, or `_(TODO)_`) they write `_(TODO)_`
    under it, and the next step lists it as unfilled, never as inherited. Add a small
    block helper in `plan_tool/scope_fence.py`, next to `source_references_block`,
    so every seed writer (these three and step 3''s `annotate`) shares the one copy-or-`_(TODO)_`
    rule. The printed next steps change in two places: `plan_tool/cli/scope_out_cmd.py:render_scope_out_result`,
    and the re-baseline notice in `plan_tool/reground.py`. They name each inherited
    heading as one to review before `create`, because a parent''s fence can be wrong
    for the narrower plan. They name each `_(TODO)_` heading as one to fill in by
    hand. Neither renderer gains a model call. The destructive operations on this
    path stay exactly as they are: scope-out narrowing the source plan and archiving
    carved detail files, the seed-file writes, and reground''s mark-done. Only the
    text of the seed changes. Tests in `tests/test_scope_out.py`, `tests/test_reground.py`
    and `tests/cli/test_scope_out_cmd.py` cover three things: a source plan with guardrails
    is copied verbatim, a `None` body included; a source plan whose heading is absent,
    empty, duplicated or `_(TODO)_` gets `_(TODO)_`; and the next-step text names
    each heading as inherited or unfilled.'
- id: 3
  intent: Annotate's forward seeds pass the new check without a new model call, and
    the fence comes from the source rather than being made up.
  files:
  - plan_tool/annotate.py
  - plan_tool/annotate_render.py
  - plan_tool/prompts/annotate.md
  - plan_tool/cli/annotate_cmd.py
  - tests/test_annotate.py
  - tests/test_annotate_render.py
  - tests/cli/test_annotate_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  depends_on_notes:
    2: the shared copy-or-_(TODO)_ guardrail block helper in scope_fence.py
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/03-make-annotate-write-all-three-guardrail.md
  description: 'Make `annotate` write all three guardrail headings into its carryover
    seed. When the source plan or document has a guardrail heading the step 1 predicate
    accepts, `annotate_render.render_create_seed` copies it verbatim through the step
    2 block helper, under the same source-state rule. For each heading the source lacks an accepted body for, the existing single `annotate` call also returns that heading''s body (the decision is per heading, and a model body never replaces an inherited one),
    which takes an additive extension of `_ANNOTATE_RESPONSE_CONTRACT` and `PlanAnnotation`
    in `plan_tool/annotate.py`. Existing section-verdict parsing and the existing
    response stay valid unchanged. Each model-written body is used only when step 1''s single-body rule accepts it, through the step 2 helper; a missing or unusable body renders `_(TODO)_` rather than failing the annotation. Add one line to `plan_tool/prompts/annotate.md`:
    write only fences the source already implies, use `None` when it implies none,
    and add no scope, mechanism or requirement. That line carries the proportionality
    rule from `synthesize-body.md`. The printed result in `plan_tool/cli/annotate_cmd.py`
    names each model-written or inherited heading for review before `create`. The
    destructive operations stay as they are: the refusal to overwrite an existing
    default seed, replacement only through an explicit `--seed`, and the opt-in `--archive`
    move. Tests in `tests/test_annotate.py`, `tests/test_annotate_render.py` and `tests/cli/test_annotate_cmd.py`
    use canned responses and cover verbatim copy, a model-written guardrail, an older
    response shape with no guardrails, and that the prompt contains the instruction.'
- id: 4
  intent: Roadmap-derived seeds are checked against the same guardrail rule at materialization
    time, so a seed the roadmap accepts is never one `create` refuses.
  files:
  - plan_tool/prompts/roadmap-seed.md
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap_gates.py
  - tests/test_roadmap.py
  - tests/cli/test_roadmap_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: the shared guardrail-presence predicate
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/04-make-roadmap-materialize-refresh-seeds.md
  description: 'Make `roadmap --materialize` and `--refresh-seeds` produce draft seeds
    that carry all three guardrail headings. In `plan_tool/prompts/roadmap-seed.md`,
    add `Scope guardrails`, `Audit guardrails` and `Expected placement` to the required
    section list. The prompt says to write `Scope guardrails` from the plan row's `non_goals` and the settled decisions and constraints its components own, to write the other two only from accepted content that states them, to write only fences those sources imply and add no scope (the step 3 rule), and to put `None` where they set none. `roadmap_gates.validate_draft_seed_content`
    calls the step 1 predicate and returns one violation per offending heading. That
    makes a draft missing a heading consume an attempt in `materialize_plan_seed`''s
    existing retry loop, with the violation message as the correction. The operator
    still reviews the draft at `--accept-seed`. The same gate also runs on `--accept-seed`,
    on seed promotion and in `roadmap_seed_manifest` classification, so a draft materialized
    before this change and lacking the headings is reported malformed there; its one
    stated route is `--refresh-seeds`, which re-materializes it with the headings,
    and the refusal message names that route. The destructive operations stay as they
    are: the draft-seed write and the sidecar that commits last, so an interrupted
    write is still detectable. Tests: gate cases in `tests/test_roadmap_gates.py`
    for missing, duplicated, empty, `_(TODO)_` and `None` headings; in `tests/test_roadmap.py`,
    a retry on a missing heading, plus the existing canned seed replies updated to
    carry the headings; a prompt-containment test that the template names all three
    headings; and an existing-draft case in which a pre-change draft without the headings
    is classified malformed, its refusal names `--refresh-seeds`, and a refresh clears
    it.'
- id: 5
  intent: Live seeds still work after the refusal turns on, so the change breaks no
    current input.
  files:
  - docs/implementation-plans/plan-seeds
  - plan-seeds
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: the predicate used to confirm every swept seed passes
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/05-three-guardrail-headings-hand-every.md
  description: Add the three guardrail headings by hand to every live seed in `docs/implementation-plans/plan-seeds/`
    and `plan-seeds/` that lacks one; the step 1 predicate, run over both directories,
    defines which seeds lack a heading. Write each body from that seed's own content
    (its scope fence, Out of scope, Allowed reorganization), and write `None` where
    the seed states no such boundary. Do not add new scope, and leave every existing
    section's text unchanged. Archived seeds are not touched. Run the step 1 predicate
    over every file in both directories and confirm it reports nothing. This step
    deletes and overwrites nothing besides these additive heading insertions.
- id: 6
  intent: 'Delivers the outcome: a `--from-existing` seed must state each guardrail,
    with `None` as a valid answer, so a missing fence cannot pass as a deliberate
    one.'
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  - tests/test_cli.py
  - tests/test_distill.py
  - tests/test_review.py
  - tests/test_scope_fence.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  - 4
  - 5
  depends_on_notes:
    1: the guardrail-presence predicate
    2: scope-out and reground seeds already carry the headings
    3: annotate seeds already carry the headings
    4: roadmap draft seeds already carry the headings
    5: live seeds already pass, so turning the refusal on breaks no current input
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/06-turn-on-refusal-create-py-classify-file.md
  description: Turn on the refusal in `create.py:classify_file_backed_source`. `validate_from_existing_seed`
    and the CLI's pre-slug call in `plan_tool/cli/authoring.py` both reach it, and
    so does the `create_plan` intake. It calls the step 1 predicate and raises one
    `CreateError` before any model call. The error names every offending guardrail
    heading, alongside the `References` problem when there is one. Change the three
    guardrail entries in `OPTIONAL_PLAN_BODY_SECTION_SHAPES` from "Conditional" wording
    to required-and-verbatim wording, and keep `Stack` conditional. Update the test
    fixtures that feed `--from-existing` a seed so they carry the headings. They are
    in `tests/test_create.py`, `tests/cli/test_authoring_cmds.py`, `tests/test_cli.py`,
    `tests/test_distill.py` and `tests/test_review.py`, plus the others a grep for
    `from_existing` returns. Those red tests are the expected sweep, not a reason
    to narrow the rule. New tests cover the following. Each heading missing, duplicated,
    empty or `_(TODO)_` is refused, with a test invoker that asserts it was never
    called, at both the CLI and the `create_plan` seams. Two missing headings are
    both named. A `None` heading is accepted and appears verbatim in the written plan
    body and in `render_scope_fence`'s downstream fence. A seed produced by each of
    `scope-out`, `reground`, `annotate` and roadmap materialization passes when its
    source carries guardrails. The `_(TODO)_` that a deterministic renderer writes
    is refused. Break the check and confirm each refusal test goes red. This step
    adds a refusal only; no write path is touched.
- id: 7
  intent: The docs describe the contract that now ships, and the backlog no longer
    lists finished work.
  files:
  - SEED_FORMAT.md
  - PLAN_FORMAT.md
  - docs/how-to/pipeline/create-from-existing.md
  - ROADMAP_FORMAT.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  depends_on_notes:
    6: the shipped refusal and its message that the docs describe
  detail: docs/implementation-plans/plan-details/required-guardrail-headings/07-update-docs-say-three-guardrail.md
  description: 'Update the docs to say the three guardrail headings are required,
    that `None` is a valid body, and that `_(TODO)_` is refused. The pages are `SEED_FORMAT.md`,
    `PLAN_FORMAT.md` § "Scope fence", `docs/how-to/pipeline/create-from-existing.md`,
    and `ROADMAP_FORMAT.md`''s draft seed contract, which gains the new draft-gate
    rule. Each page also states which source each seed-writing tool fills the headings
    from. Then remove BACKLOG #532 from `BACKLOG.md`, because the work has shipped.'
---
# Required Guardrail Headings

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
  | `annotate` | The source plan or document's guardrail sections, copied verbatim per heading when the step 1 rule accepts it; for each heading the source lacks, the existing `annotate` call writes it, stating only fences the source supports (an exclusion or boundary it already implies) and adding no scope, mechanism or requirement. |
  | `scope-out`, `reground` | The source plan's guardrail sections, copied verbatim when the step 1 rule accepts them. |

  A seed writer whose source carries no guardrail heading the rule accepts
  (absent, empty, duplicated or `_(TODO)_`, as in a plan that predates this
  change) writes `_(TODO)_` under it, which `create`
  refuses, and its printed next step says to fill the heading in. An `annotate` response that returns no guardrail bodies is rendered the same
  way. These are the only cases left to a hand edit.
- **`annotate`'s guardrail instruction is prompt guidance only.** It carries
  the proportionality rule `synthesize-body.md` applies to plan bodies, in one
  line in `prompts/annotate.md`; whether a written fence is proportionate is not
  checked, since that is a judgment of content.
- **Inherited guardrails are reviewed, not trusted.** A carved or rebaselined
  seed's inherited fence can be wrong for the narrower plan (a parent's guardrail
  may exclude the very region carved out). The tool's printed next step names
  the inherited headings for review before `create`.
- **Order:** the four tools populate the headings, and the live seeds are swept,
  before the refusal turns on, so no shipped tool writes a seed the tool refuses.

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

## Steps

See the `steps:` block in the frontmatter.

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

## Risks

- **Breaking existing seeds:** every live seed and every on-disk tool-written
  seed without the headings stops working. The tool changes and the sweep land
  before the refusal. A roadmap draft materialized before the change is reported
  malformed at accept, promotion and classification; `--refresh-seeds` is its
  stated route, and the refusal names it.
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
  seed writer's source has no accepted heading or an `annotate` response returns
  no guardrail bodies; `create` refuses both until the operator fills them in.
- Every live seed in both seed directories passes the check.
- The docs describe the headings as required.
- BACKLOG #532 is removed in the final step.

## Deferred

Requiring `## Outcome` and `## In scope` waits for its own decision.

Stop / defer: any out-of-scope discovery is filed in BUG_BACKLOG.md (defect) or
BACKLOG.md (forward work), never applied as plan expansion.
