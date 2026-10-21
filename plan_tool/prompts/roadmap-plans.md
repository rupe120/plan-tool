# Write the plans artifact for the roadmap "${slug}"

You are the fourth stage of a roadmap run. Produce `04-roadmap.md` — an ordered
list of derived plans that map components to implementation slices.

Two readers depend on it. The materializer uses each row's destination to
create a draft seed later, so every plan id must be a valid create slug. A human
reads the same file, so the prose has to hold up on its own.

## Your inputs

There are four: the brief says what the project is, and the three upstream
artifacts say what you may map, what you must discharge, and how the domain
divides into components.

### The concept brief

```
${brief}
```

### `01-domain.md`, written by the stage below you

```
${domain_artifact}
```

### `02-constraints.md`, written by the stage below you

```
${constraints_artifact}
```

### `03-components.md`, written by the stage below you

```
${components_artifact}
```

Work from those four texts alone. **Do not read the repository** — no file
reads, no searches. Do not invent scope the brief does not imply.

${smallest_proof_boundary_header} The plan rows collectively
deliver one concrete path and observable result. Keep a plan only when that
result cannot be true without it. Each plan's `non_goals` must name the nearby
eventual capability it deliberately leaves for later. Do not add later roles,
workflows, integrations, operating modes, or generalized mechanisms merely
because they would make a later product more complete.

${smallest_proof_boundary_footer}

## Output format (strict)

Respond with the deliverable and nothing else — no preamble, no closing remark.

Return the full `04-roadmap.md` text starting with `---` (no outer code fence,
no preamble before the frontmatter). Do not write, create, or edit any file —
your response is the artifact.

## Map complete implementation responsibilities

Choose appropriately granular implementation plans. Give each plan a cohesive
implementation outcome, an explicit scope boundary, identifiable prerequisites,
and a verifiable completion result. Split overly broad scopes into bounded plan
rows; splitting steps inside one broad plan is insufficient. Component coverage
alone does not establish a complete implementation route.

- **Choose boundaries by responsibility.** Use `keep` for a component that fits
  one cohesive plan, `merge` when components share one cohesive outcome, `split`
  when a component needs several independently implementable plans, and
  `cross-cutting` for work without a single component owner. Several plans per
  component are expected where needed. Do not impose a target plan count or
  directory-based boundaries, or create a separate plan for every shared concern.
- **Assign shared production and integration.** Identify which plan produces
  each shared capability or contract, which plans consume it, and which plan
  connects each consumer to the producer. A producer's existence does not
  establish consumer integration. Record these responsibilities in existing row
  descriptions and narrative linked by plan id. Trace each source-required
  business transition of evidence, content, or an identity from where it
  originates to where it is consumed: the operation that produces or corrects it
  (not only the check that reads it), what makes the actual output available to
  its consumer, and the integration that receives it. Name a plan that owns each
  hop, even when the source leaves its support unresolved. An existing
  producer does not imply it already supports that operation. Keep distinct
  source identities distinct; do not substitute one revision or lifecycle for
  another. State unresolved source support as an assumption rather than
  inventing a capability or an internal mechanism.
- **Order required handoffs.** Use `ordering.depends_on` for prerequisite plans;
  describe what each consumer needs delivered by those plans. Keep
  `assumption_targets` as plan references for ordering-level assumptions, and
  record inter-plan unknowns in `assumptions` with their consuming plans. An
  unknown prerequisite remains explicit; do not invent a settled result.
- **Assign eventual acceptance.** In the plan-id-linked narrative, identify
  which plan proves each bounded route works, including consumer integration
  and observed runtime or deployment evidence when the source outcome requires
  it. A drafting-only or benchmark execution restriction does not replace
  eventual completion evidence with document review. Stay within the smallest
  proof boundary above; do not add proof for capabilities outside the requested
  outcome.

## The frontmatter inventory

### Supplied inherited decisions

The following rows are approved source facts for this artifact only:

```json
${inherited_decisions}
```

Reproduce every supplied row exactly in `decisions`: preserve its id, chosen
option, anchor, `settled` status, citation in `source`, and any supplied
rationale or rejected alternatives. Omit rationale or alternatives when the
row omits them. Do not invent deliberation for these rows. This does not limit
Roadmap-derived decisions: author those normally using the rules below.

Everything above the closing `---` of `04-roadmap.md` is YAML: four
collections, in this order. Every key named below belongs on every row you
author. `intent` and `non_goals` are enforced by the plans gate after parsing
so an older roadmap remains readable, but a newly authored row
without them still fails this stage.

- `plans` — the derived implementation plans. Each row carries `id`, `title`
  (what this plan delivers), `intent` (the short, operational outcome that
  makes the plan necessary — not a reworded title or sizing rationale), and
  `non_goals` (a non-empty list of adjacent, prerequisite, or deliberately
  deferred work this plan does not deliver). It also carries `disposition`
  (one of `keep`, `merge`, `split`, or `cross-cutting`): this is the plan's
  delivery shape. `cross-cutting` means component ownership is not required;
  every other disposition is component-owned. `component_ids` is the list of
  ids from `03-components.md` the plan covers — **empty only when disposition
  is `cross-cutting`**. Finally, provide `draft_seed_path` (relative to the
  roadmap slug root, must begin with `plan-seed-drafts/` — for example
  `plan-seed-drafts/order-core.md`) and `sizing_rationale` (why this plan is sized this
  way).
- `ordering` — the execution sequence. Each entry carries `plan_id` (a plan id
  from `plans`), optional `depends_on` (plan ids that must run before this one),
  and optional `assumption_targets` (plan ids this entry assumes are settled).
- `assumptions` — inter-plan assumptions. Each row carries `id`, `statement`,
  and `consuming_plan_ids` (plan ids that rely on this assumption).
- `decisions` — the calls you made at the option points. Each row carries
  `id`, `chosen_option`, `rejected_alternatives` (a list, each entry carrying
  `option` and `reason`), `rationale`, `anchor`, and `status` (`settled` or
  `pending`).

**Plan ids are create slugs.** Every `plans` row `id` must satisfy the same
shape `plan-tool create` accepts: lowercase letters, digits, and hyphens only,
starting and ending with a letter or digit. **Do not reuse component ids as plan ids** — duplicate-id checks union every design-row id across `01-domain.md`,
`02-constraints.md`, `03-components.md`, and this file, so a plan id that
matches a component id makes anchors and references resolve two ways.

A first run authors `decisions` only; do not author `feedback` or `removals` rows.

Every `id` is a short kebab-case string.

## The prose body

Everything after the closing `---` is a short narrative of why this plan list
and ordering, and not another.

**It is checked.** Every inventoried design-row id — every plan, ordering entry
(by its `plan_id`), assumption, and decision id — appears in the prose body as a
whole word. Do not re-tabulate the rows: a body that restates the frontmatter
one sentence per row clears the check and tells the reader nothing.

## Writing style

${writing_style}

**For this stage:** Say why this list of plans and this order, not how you arrived at it. The
reviewer approves each plan's `title`, `intent`, `non_goals`, `sizing_rationale`,
and every decision's `chosen_option` and `rationale`, so write those the same
way as the body.

## The rules your artifact is checked against

Deterministic checks run over your response before anything is written. On a
failure you get **this same prompt again with the violations appended, and no
copy of what you wrote** — so you re-author the whole response from scratch
rather than editing the rejected one, and nothing carries over but the
corrections. The stage gets only a few attempts. Meet all of them the first time.

1. **Declare at least one plan row** — name at least one plan, listing the
   component ids it covers and the draft seed path destination it declares. Every other
   rule here is a check over rows, so an artifact with none passes them all
   vacuously.
2. **Every `id` is unique across every artifact in the envelope** — `01-domain.md`,
   `02-constraints.md`, `03-components.md`, and `04-roadmap.md`. A decision
   `anchor` resolves against the union of all four, so an id used twice makes
   that anchor resolve two ways.
3. **Every plan has a non-blank `intent` and at least one `non_goals` entry.**
   State the intended operational outcome and the work deliberately outside
   the row; do not make either field a restatement of title or sizing.
4. **Every plan whose disposition is not `cross-cutting` names at least one
   component id** from `03-components.md`. Every listed `component_ids` entry
   must resolve to a component row in `03-components.md`. A `cross-cutting`
   plan may omit `component_ids` or list ids it spans.
5. **Every component id in `03-components.md` appears on at least one plan
   row's `component_ids`.** A component the decomposition named but no plan
   covers is an orphan slice.
6. **Every `draft_seed_path` has a unique basename** across plan rows, so
   independently materialized drafts never resolve to the same file.
7. **Every plan id appears exactly once in `ordering`**, every `ordering`
   `plan_id` names a plan row, every plan id is a valid create-compatible slug,
   every `depends_on` and `assumption_targets` entry names a plan id that
   appears earlier in the ordering sequence.
8. **Every assumption row's `consuming_plan_ids` names a plan id** declared in
   `plans`.
9. **Every decision names at least one rejected alternative carrying its own
   `reason`, has a non-blank `rationale`, and has an `anchor` that resolves** —
   to any row id across the four artifacts in the envelope.
10. **Every id you inventory in the frontmatter appears in the prose body
    below** — see the prose section above.

## Decide, and say when a decision is provisional

At every option point, take a position and record it as a `decisions` row. Mark
a decision `pending` when it genuinely binds downstream design and the brief
does not settle it. Use `settled` otherwise.

## Shape

The skeleton below shows the shape of `04-roadmap.md` and clears every rule
above. Replace every placeholder — the ids and the prose — with the real mapping
for this project. `component-checkout` and `plan-1` are placeholders: copy real
ids from the artifacts above. Carry none of their wording into your answer.

```markdown
---
plans:
- id: plan-1
  title: <one line>
  intent: <operational outcome, not a reworded title>
  non_goals:
  - <adjacent or prerequisite work this plan does not deliver>
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: plan-seed-drafts/plan-1.md
  sizing_rationale: <one line>
ordering:
- plan_id: plan-1
  depends_on: []
  assumption_targets: []
assumptions:
- id: assumption-1
  statement: <one line>
  consuming_plan_ids:
  - plan-1
decisions:
- id: decision-1
  chosen_option: <the decision of record>
  rejected_alternatives:
  - option: <the option that lost>
    reason: <why it lost>
  rationale: <why the chosen option won>
  anchor: plan-1
  status: pending
---

# Plans

`plan-1` is the only plan here, so it goes first and waits for nothing.
`assumption-1` is what `plan-1` relies on. `decision-1` records why the slice
stands alone.
```
