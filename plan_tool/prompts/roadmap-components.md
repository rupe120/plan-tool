# Write the components artifact for the roadmap "${slug}"

You are the third stage of a roadmap run. Produce `03-components.md` — how this
project divides its domain into logical components, the patterns each component
applies, and the decisions behind the decomposition.

This file is a **map of ownership, not a diagram**. Every entity from
`01-domain.md` belongs to at least one component, and every prioritized
constraint from `02-constraints.md` is discharged by at least one component
that cites it.

Two readers depend on it. The stages above inherit this decomposition as the
unit of work, so a component you leave out is an entity nothing owns. A human
reads the same file, so the prose has to hold up on its own.

## Your inputs

There are three: the brief says what the project is, the domain artifact says
what you may own, and the constraints artifact says what you must discharge.

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

**The domain artifact governs your entity ids.** `entity_ids` holds **entity ids
only** — never a business rule id, a workflow id, or a field name. Read the
`entities` rows in `01-domain.md`, list the ids of the entities each component
owns, and copy each one exactly as it is written there. An id you invent,
misspell, or take from another collection is rejected. Business rule and workflow
ids are still reachable, but only from a decision `anchor` — see rule 8.

**The constraints artifact governs your discharge claims.** Every
`constraint_ids` entry must name a constraint row from `02-constraints.md`.
Only constraints on attributes this project **prioritized** must appear on some
component's `constraint_ids` — constraints on `traded-away` attributes need no
discharger.

Work from those three texts alone. **Do not read the repository** — no file
reads, no searches. Do not invent scope the brief does not imply.

${smallest_proof_boundary_header} Name only the ownership,
patterns, and stores the selected concrete path and observable result need.
Do not add components for later roles, workflows, integrations, operating
modes, or generalized mechanisms merely because they would make a later
product more complete.

${smallest_proof_boundary_footer}

## Output format (strict)

Respond with the artifact and nothing else. The first characters of your
response are the opening `---` of the frontmatter. No preamble, no closing
remark, no code fence around the file. Do not write, create, or edit any file —
your response *is* the artifact.

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

Everything above the closing `---` is YAML: five collections, in this order.
Every required key named below is required on every row of its kind, and a row
missing one is rejected before it is judged. Define each store a component
names, and give every component at least one concrete store reference.

- `system_patterns` — cross-cutting patterns the components share. Each row
  carries `id`, `name` (the human-facing name of the pattern), and `statement`
  (what the pattern means in one sentence).
- `component_patterns` — reusable decomposition shapes. Each row carries `id`,
  `name`, and `statement` with the same meaning as `system_patterns`.
- `stores` — reviewed persistence definitions. Each row carries `id`,
  `category`, and `sharing`, and may carry free-text `product` or `description`
  when either helps the operator. It may also carry optional
  `research_disclosure`: only `external` permits an outbound query using that
  row's product; `local`, absence, or `null` keeps it local, so those rows need
  a description. `category` is one of `in-process`, `relational`, `document`,
  `key-value`, or `object`; `sharing` is one of `silo`, `pool`, or `bridge`.
- `components` — the logical units the domain divides into. Each row carries
  `id`, `name` (what this component is), `entity_ids` (a list holding the ids
  of the entities this component owns from `01-domain.md`), `pattern_ids` (a
  list holding ids from `system_patterns` or `component_patterns` that this
  component applies), and `constraint_ids` (a list holding ids from
  `02-constraints.md` that this component discharges — may be empty when the
  component makes no discharge claim), and `store_ids` (a non-empty list of
  store ids it uses).
- `decisions` — the calls you made at the option points. Each row carries
  `id`, `chosen_option` (the decision of record), `rejected_alternatives` (a
  list, each entry carrying `option` and `reason`), `rationale` (why the
  chosen option won), `anchor` (the id of the row this decision bears on), and
  `status`, which is either `settled` or `pending`.

Every `id` is a short kebab-case string.

## The rules your artifact is checked against

Deterministic checks run over your response before anything is written. On a
failure you get **this same prompt again with the violations appended, and no
copy of what you wrote** — so you re-author the whole artifact from scratch
rather than editing the rejected one, and nothing carries over but the
corrections. The stage gets only a few attempts. Meet all eleven the first time.

1. **Declare at least one component row**, listing the entity ids it owns and
   the pattern ids it applies. Every other rule here is a check over rows, so
   an artifact with none passes them all vacuously.
2. **Every `id` is unique across every artifact in the envelope** — `01-domain.md`,
   `02-constraints.md`, and this file. A decision `anchor` resolves against the
   union of all three, so an id used twice makes that anchor resolve two ways.
   A store id is never itself an anchor, but it still reserves its name once
   across the same id space and is rejected the same way if duplicated.
3. **Every component names at least one entity id** from `01-domain.md`. A
   component that owns nothing is not a component.
4. **Every domain entity is owned by at least one component.** An entity that
   appears on no component's `entity_ids` is an entity the decomposition
   abandoned.
5. **Both pattern collections are non-empty**, and **every component names at
   least one pattern id** from their union. `system_patterns` carries at least
   one cross-cutting pattern row; `component_patterns` carries at least one
   decomposition-shape row; each component lists the patterns it applies.
6. **Every `constraint_ids` entry names a constraint row** that
   `02-constraints.md` defines. An absent or empty list is not a discharge
   claim; a non-empty list must cite real constraint ids.
7. **Every constraint on a prioritized attribute is cited by at least one
   component's `constraint_ids`.** Constraints on `traded-away` attributes need
   no discharger — only `prioritized` constraints are in scope.
8. **Every component names at least one defined store in `store_ids`, and each
   store definition is used.** Name a distinct `in-process` store when a
   component has no durable store. `in-process` means volatile storage for one
   component during its process lifetime, so one such definition may appear on
   exactly one component. Durable store definitions may serve several
   components.
9. **Every store uses a concrete category and sharing model.** Categories are
   `in-process`, `relational`, `document`, `key-value`, and `object`.
   Sharing is `silo` for a dedicated data resource per tenant, `pool` for a
   shared resource with logically partitioned tenant data, or `bridge` for a
   store role that combines dedicated and pooled placement. These describe data
   partitioning, not application operation: `self-hosted` is not a sharing
   value, and there is no undecided value.
10. **Every decision names at least one rejected alternative carrying its own
   `reason`, has a non-blank `rationale`, and has an `anchor` that resolves** —
   to any row id in the three artifacts: a system pattern, component pattern,
   component, or decision id in this file; a disposition, constraint, or
   decision id in `02-constraints.md`; an entity, business rule, workflow, or
   decision id in `01-domain.md`. A quality attribute is reachable only through
   its disposition row's id, never by its bare name.
11. **Every system pattern, component pattern, component, and decision id
   appears in the prose body below.** Store ids are identity-only definitions,
   so they do not need prose coverage — see the next section.

## Decide, and say when a decision is provisional

At every option point, take a position and record it as a `decisions` row. Do
not hedge in the prose, and do not ask a question back: nothing answers.

Mark a decision `pending` when it genuinely binds downstream design and the
brief does not settle it. Use `settled` otherwise. `pending` is never a failure
— it is how you ask the operator to confirm one specific call, and a run that
finishes carrying pending decisions is a successful run.

## The prose body

Everything after the closing `---` is a short narrative of why this decomposition
and not another: what each component owns, which patterns apply, and how
constraints are discharged.

**It is checked.** Every system pattern, component pattern, component, and
decision id appears in the body, matched as a whole word, so name each one by
its id while you explain it. Store ids are identity-only and need no prose
coverage. Do not re-tabulate the rows: a body that restates the frontmatter one
sentence per row clears the check and tells the reader nothing.

## Writing style

${writing_style}

**For this stage:** Say what each component owns and which constraints it discharges, not how you
arrived at it.

## Shape

The skeleton below shows the shape and clears every rule above. Replace every
placeholder — the ids, the names, and the prose — with the real decomposition for
this project. `order` and `con-1` are placeholders too: copy real ids from the
artifacts above. Carry none of their wording into your answer.

```markdown
---
system_patterns:
- id: pattern-audit-before-response
  name: Audit before response
  statement: <one line>
component_patterns:
- id: pattern-checkout
  name: Checkout boundary
  statement: <one line>
stores:
- id: store-checkout
  category: relational
  sharing: pool
  product: PostgreSQL
  description: The checkout team records orders in this managed database.
  research_disclosure: external
components:
- id: component-checkout
  name: Checkout
  entity_ids:
  - order
  pattern_ids:
  - pattern-audit-before-response
  - pattern-checkout
  constraint_ids:
  - con-1
  store_ids:
  - store-checkout
decisions:
- id: dec-components-1
  chosen_option: <the decision of record>
  rejected_alternatives:
  - option: <the option that lost>
    reason: <why it lost>
  rationale: <why the chosen option won>
  anchor: con-1
  status: settled
---

# Components

## Patterns

`pattern-audit-before-response` is <one line>. `pattern-checkout` is <one line>.

## Components

`component-checkout` owns `order`, uses `store-checkout`, and discharges `con-1` — <one line>.

## Decisions

`dec-components-1` records <one line>.
```
