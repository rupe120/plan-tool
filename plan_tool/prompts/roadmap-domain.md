# Write the domain artifact for the roadmap "${slug}"

You are the first stage of a roadmap run. Produce `01-domain.md` — the
entities, business rules, and workflows one project is about, plus the
decisions you made while modelling them.

Two readers depend on it. The next stage anchors the project's quality
constraints to the ids you declare here, so anything you leave undeclared is a
constraint that cannot be written. A human reads the same file, so the prose has to hold up on its own.

## Your input is the concept brief

```
${brief}
```

Build the domain model from that text alone. **Do not read the repository** —
no file reads, no searches. This is a concept with no code to inspect, and a
stage that goes looking is slower and less reproducible for nothing. Do not
invent scope the brief does not imply: model what it describes, at the altitude
it describes it.

${smallest_proof_boundary_header} Select one concrete path and an
observable result from the brief. Keep an entity, rule, workflow, or decision
only when that result cannot be true without it. Do not model later roles,
workflows, integrations, operating modes, or generalized mechanisms merely
because they would make a later product more complete.

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

Everything above the closing `---` is YAML: four collections, in this order.
Every key named below is required on every row of its kind, and a row missing
one is rejected before it is judged.

- `entities` — the things the domain is about. Each row carries `id`, `name`
  (the human-facing name of the thing), and `fields` (a list of what the entity
  holds). Each entry in `fields` carries `name` and `type`, where `type` is one
  of `text`, `number`, `boolean`, `timestamp`, `enum`, or `reference`. A
  `reference` entry also carries `entity_id`, the id of the entity it points
  at; no other type carries one. Types are **logical**: say `text`, never
  `varchar(255)` — the storage is a later decision, not yours.
- `business_rules` — the rules the domain enforces. Each row carries `id`,
  `statement` (the rule in one sentence), and `entity_ids` (a list holding the
  ids of the entities the rule governs).
- `workflows` — the paths through the domain. Each row carries `id`, `name`
  (what the path does), and `entity_ids` (a list holding the ids of the
  entities it touches).
- `decisions` — the calls you made at the option points. Each row carries
  `id`, `chosen_option` (the decision of record), `rejected_alternatives` (a
  list, each entry carrying `option` and `reason`), `rationale` (why the
  chosen option won), `anchor` (the id of the row this decision bears on), and
  `status`, which is either `settled` or `pending`.

Every `id` is a short kebab-case string, and every id is unique across all four
collections.

## The rules your artifact is checked against

Deterministic checks run over your response before anything is written. On a
failure you get **this same prompt again with the violations appended, and no
copy of what you wrote** — so you re-author the whole artifact from scratch
rather than editing the rejected one, and nothing carries over but the
corrections. The stage gets only a few attempts. Meet all six the first time.

1. **Declare at least one entity and at least one workflow.** Every other check
   here is a check over rows, so an artifact with none passes them all
   vacuously, and a domain with nothing in it gives the next stage nothing to
   anchor to.
2. **Every id is unique across all four collections**, not merely within one. A
   decision `anchor` resolves against the union of them, so a workflow and a
   rule sharing an id make that anchor resolve two ways.
3. **Every workflow and every business rule lists at least one `entity_ids`
   value, and every id it lists is an `entities` row in this same artifact.** A
   workflow that touches nothing is not a workflow, and a rule connected to no
   entity breaks the traceability chain the next stage's constraints anchor
   into.
4. **Every entity lists at least one field**, field names are unique within an
   entity, and `entity_id` is present on exactly the `reference` fields. An
   entity with no fields is a name with no shape, and every plan derived from
   it then invents what the thing holds. List the fields the entity is defined
   by — not every column it will ever grow.
5. **Every decision names at least one rejected alternative carrying its own
   `reason`, has a non-blank `rationale`, and has an `anchor` that resolves to
   an entity, business rule, workflow, or decision id in this artifact.** An
   option with no reason records that a choice was made but not why, and an
   unanchored decision names a tradeoff but not the thing it binds.
6. **Every id you inventory in the frontmatter appears in the prose body
   below** — see the next section.

## Decide, and say when a decision is provisional

At every option point, take a position and record it as a `decisions` row.
Do not hedge in the prose, and do not ask a question back: nothing answers.

Mark a decision `pending` when it genuinely binds downstream design and the
brief does not settle it. Use `settled` otherwise. `pending` is never a
failure — it is how you ask the operator to confirm one specific call, and a
run that finishes carrying pending decisions is a successful run.

## The prose body

Everything after the closing `---` is a short narrative of the domain, written
for a human: what the system is about, how the rules and workflows fit
together, and what each decision costs.

**It is checked.** Every id in the frontmatter must appear in the body, matched
as a whole word, so name each entity, rule, workflow, and decision by its id
while you describe it. Do not re-tabulate the rows: a body that restates the
frontmatter one sentence per row clears the check and tells the reader nothing.
Describe the domain, citing rows by id as you go.

## Writing style

${writing_style}

**For this stage:** Say what the domain is, not how you arrived at it. This
includes every rule statement and workflow name.

## Shape

The skeleton below shows the shape and clears every check above. Replace every
placeholder — the ids, the names, and the prose — with the real domain from the
brief, and use as many rows of each kind as the brief calls for. Carry none of
its wording into your answer.

```markdown
---
entities:
- id: entity-1
  name: <the thing this entity is>
  fields:
  - name: <what this entity is called>
    type: text
  - name: <when it was raised>
    type: timestamp
- id: entity-2
  name: <the thing this entity is>
  fields:
  - name: <which state it is in>
    type: enum
  - name: <the entity-1 this one belongs to>
    type: reference
    entity_id: entity-1
business_rules:
- id: rule-1
  statement: <one sentence stating the rule>
  entity_ids:
  - entity-1
  - entity-2
workflows:
- id: flow-1
  name: <what this path through the domain does>
  entity_ids:
  - entity-1
decisions:
- id: decision-1
  chosen_option: <the decision of record>
  rejected_alternatives:
  - option: <the option that lost>
    reason: <why it lost>
  rationale: <why the chosen option won>
  anchor: rule-1
  status: settled
---

# Domain

## Entities

`entity-1` is <one line>. `entity-2` is <one line>.

## Business rules

`rule-1` binds the two — <one line>.

## Workflows

`flow-1` is <one line>.

## Decisions

`decision-1` records <one line>.
```
