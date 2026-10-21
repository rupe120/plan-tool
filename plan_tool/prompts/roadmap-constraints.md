# Write the constraints artifact for the roadmap "${slug}"

You are the second stage of a roadmap run. Produce `02-constraints.md` — how
this project ranks its quality attributes, the constraints that ranking buys,
and the decisions behind both.

This file is a **ranking of tradeoffs, not a checklist**. Anything a project
holds is paid for with something else, and saying what you are willing to spend
is the whole point of writing it down.

Two readers depend on it. The stages above inherit these constraints as fences,
so a constraint you leave out is a fence nothing enforces. A human reads the
same file, so the prose has to hold up on its own.

## Your inputs

There are two: the brief says what the project is, and the domain artifact says
what you may anchor to.

### The concept brief

```
${brief}
```

### `01-domain.md`, written by the stage below you

```
${domain_artifact}
```

**The domain artifact governs your anchors.** Read the `entities`,
`business_rules`, and `workflows` ids in it and anchor every constraint to one
or more of them, copying each id exactly as it is written there. All three kinds
are anchorable — a constraint set that only ever names entities ignores two
thirds of what is available. An id you invent or misspell is rejected, and the
stage has only a few attempts to spend.

Work from those two texts alone. **Do not read the repository** — no file reads,
no searches. Do not invent scope the brief does not imply.

${smallest_proof_boundary_header} Rank and constrain only the
concrete path and observable result selected by the domain artifact. Do not
add a quality commitment, hosting shape, or decision for later roles,
workflows, integrations, operating modes, or generalized mechanisms merely
because they would make a later product more complete.

${smallest_proof_boundary_footer}

## Output format (strict)

Respond with the artifact and nothing else. The first characters of your
response are the opening `---` of the frontmatter. No preamble, no closing
remark, no code fence around the file. Do not write, create, or edit any file —
your response *is* the artifact.

## The quality attributes you dispose

Exactly these seven, and no others:

`performance`, `scalability`, `security`, `availability`, `maintainability`,
`fault-tolerance`, `reliability`

Each is an independent concern ranked on its own. None of them contains or
implies another: `availability`, `fault-tolerance`, and `reliability` are three
separate calls here, not one call with two subheadings.

Give each attribute exactly one `dispositions` row, carrying one of these three
values:

- `prioritized` — the project spends to hold this attribute.
- `traded-away` — the project knowingly spends this attribute for something
  else.
- `not-load-bearing` — the project does not rank on this attribute at all.

`not-load-bearing` is a real and expected answer. Use it for an attribute this
project genuinely does not trade on. It is what lets every attribute be disposed
honestly, instead of inventing seven tradeoffs that only look considered.

**A ranking that prioritizes everything has ranked nothing.** No check catches
this for you: an all-`prioritized` artifact passes every rule below and says
nothing at all. Name what this project trades away, and say in the prose body
what that costs it.

## Hosting

Author **exactly one hosting row** for each fixed facet: `compute`, `model`,
and `topology`. Choose concrete values for its facet from these complete,
vendor-neutral vocabularies — there is no undecided value:

| Facet | Values | Meaning |
|---|---|---|
| `compute` | `per-request`, `managed-containers`, `long-lived`, `mixed` | `mixed` means more than one of the other compute modes across deployable units. It does not name those units or judge their stores. |
| `model` | `self-hosted`, `silo`, `pool`, `bridge` | `self-hosted` means each tenant or group operates its own application deployment. One operator runs dedicated deployments for `silo`, a shared multi-tenant deployment for `pool`, or both for `bridge`. |
| `topology` | `single-unit`, `multi-unit` | `multi-unit` records an application with more than one deployable unit. |

`compute: mixed` and `model: bridge` require `topology: multi-unit`. Choose the
value the brief supports; do not invent a vendor, product detail, a
deployment unit, or a pending decision to fill this block.

## Stack

Author **exactly one stack row** for each of three concerns: `platform` (where
the application is deployed), `store-engine` (the kind of store that holds its
data), and `language-runtime` (the language and runtime it is written in).

Each row records either a chosen value or `open`. `open` is a real answer, the
way `not-load-bearing` is for dispositions, and it is the only honest answer
when the brief leaves that concern undecided. Write `open: true` and leave the
`choice` out; a row never carries both.

A chosen value comes from the brief. Never invent a vendor, product, or version
the brief does not name. When the brief names only a category, such as a
relational store, record that category or record `open`; do not narrow it to a
product. A brief that says no account or service is fixed yet gives `open` for
`platform`, not a vendor. A brief that names a store engine gives that choice.

The hosting block above stays as it is, and its ban on inventing a vendor or a
pending decision still stands there. The two blocks differ on purpose: a
hosting row cannot be undecided, and a stack row can. A `pending` decision may
anchor to an `open` stack row, so the operator can confirm that call later. Do
not write a decision just to fill this section.

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
Every key named below is required on every row of its kind, and a row missing
one is rejected before it is judged, except the compute-only optional
`product` key and the optional `description` and `research_disclosure` keys.
On a stack row, `choice` and `open` are each optional, but exactly one of them
must be present.

- `hosting` — where the application runs. Each row carries `id`, `facet`,
  `value`, the compute-only optional `product`, and optional free-text
  `description` when it helps the operator. It may also carry optional
  `research_disclosure`: only `external` permits an outbound query using that
  row's product; `local`, absence, or `null` keeps it local, so those rows need
  a description. Hosting ids share the roadmap-wide id namespace, but they are
  not anchors, feedback targets, or prose-inventory rows.
- `stack` — the technology concerns. Each row carries `id`, `concern` (one of
  `platform`, `store-engine`, `language-runtime`), and exactly one of `choice`
  (a short text taken from the brief) or `open` (set to `true` when the brief
  leaves the concern undecided). Stack ids share the roadmap-wide id namespace
  but are not prose-inventory rows.
- `dispositions` — one row per quality attribute. Each row carries `id`,
  `attribute` (one of the seven names above), and `disposition` (one of the
  three values above). A disposition row's `id` is the only handle a quality
  attribute has: a decision cannot anchor to the bare word `security`, only to
  the id of the row that disposes it.
- `constraints` — what the ranking buys. Each row carries `id`, `statement`
  (the constraint in one sentence, checkable rather than aspirational),
  `attribute` (the quality attribute it discharges), and `anchor_ids` (a list
  holding the `01-domain.md` ids it constrains).
- `decisions` — the calls you made at the option points. Each row carries `id`,
  `chosen_option` (the decision of record), `rejected_alternatives` (a list,
  each entry carrying `option` and `reason`), `rationale` (why the chosen option
  won), `anchor` (the id of the row this decision bears on), and `status`, which
  is either `settled` or `pending`.

Every `id` is a short kebab-case string.

## The rules your artifact is checked against

Deterministic checks run over your response before anything is written. On a
failure you get **this same prompt again with the violations appended, and no
copy of what you wrote** — so you re-author the whole artifact from scratch
rather than editing the rejected one, and nothing carries over but the
corrections. The stage gets only a few attempts. Meet all eight the first time.

1. **Declare at least one constraint row.** Dispositions alone are not a
   constraints artifact: every other rule here is a check over rows, and a
   ranking that buys nothing leaves the stages above it no fence to inherit.
2. **Every `id` is unique across all five collections, and across
   `01-domain.md` too.** An anchor resolves against the union of both files, so
   an id used twice makes that anchor resolve two ways. A hosting id is never
   itself an anchor, but it still reserves its name once across the same id
   space and is rejected the same way if duplicated. A stack id is checked the
   same way.
3. **Every hosting facet has exactly one hosting row**, and every recognized
   facet uses one of its concrete values for its facet. `compute: mixed` or
   `model: bridge` requires `topology: multi-unit`.
4. **Every quality attribute carries exactly one disposition, and no attribute
   outside the seven appears at all** — on a `dispositions` row or on a
   `constraints` row. A constraint's `attribute` must also never be one this
   artifact disposes `not-load-bearing`: a concern you declared unranked cannot
   also be constrained for, and that pairing is what padding to satisfy the
   totality rule looks like. Constraining a `traded-away` attribute is fine —
   spending it knowingly and bounding how much you spend go together.
5. **Every constraint anchors to at least one id that `01-domain.md` defines**
   — an entity, business rule, or workflow id, copied verbatim from the artifact
   above. A constraint anchored to nothing is a wish, not a constraint.
6. **Every decision names at least one rejected alternative carrying its own
   `reason`, has a non-blank `rationale`, and has an `anchor` that resolves** —
   to a disposition, constraint, or decision id in this artifact, or to an
   entity, business rule, or workflow id in `01-domain.md`. An option with no
   reason records that a choice was made but not why, and an unanchored decision
   names a tradeoff but not the thing it binds.
7. **Every disposition, constraint, and decision id you inventory appears in
   the prose body below** — hosting and stack ids are deliberately excluded;
   see the next section.
8. **Every stack concern has exactly one stack row** — `platform`,
   `store-engine`, and `language-runtime`, no other concern — and each row
   carries exactly one of a `choice` or `open: true`. A concern the brief leaves
   undecided is recorded as `open`, never as an invented choice.

## Decide, and say when a decision is provisional

At every option point, take a position and record it as a `decisions` row. Do
not hedge in the prose, and do not ask a question back: nothing answers.

Mark a decision `pending` when it genuinely binds downstream design and the
brief does not settle it. Use `settled` otherwise. `pending` is never a failure
— it is how you ask the operator to confirm one specific call, and a run that
finishes carrying pending decisions is a successful run.

## The prose body

Everything after the closing `---` is a short narrative of why this ranking and
not another: what the project holds, what it spends to hold it, and what each
decision costs.

**It is checked.** Every disposition, constraint, and decision id appears in
the body, matched as a whole word, so name each while you explain it. Hosting
rows have no prose-inventory or anchor role. Do not re-tabulate the rows: a
body that restates the frontmatter one sentence per row clears the check and
tells the reader nothing.

## Writing style

${writing_style}

**For this stage:** Say what the project holds and what it spends, not how you arrived at it.

## Shape

The skeleton below shows the shape and clears every rule above. Replace every
placeholder — the ids, the statements, and the prose — with the real ranking for
this project, and write as many constraint rows as the brief and the domain call
for. `entity-1`, `rule-1`, and `flow-1` are placeholders too: anchor to real ids
from the `01-domain.md` above. Carry none of its wording into your answer.

```markdown
---
hosting:
- id: hosting-compute
  facet: compute
  value: per-request
  product: Cloud Run
  description: The checkout runtime runs on this managed service.
  research_disclosure: external
- id: hosting-model
  facet: model
  value: pool
- id: hosting-topology
  facet: topology
  value: single-unit
stack:
- id: stack-platform
  concern: platform
  open: true
- id: stack-store-engine
  concern: store-engine
  choice: <the store kind the brief names>
- id: stack-language-runtime
  concern: language-runtime
  open: true
dispositions:
- id: qa-performance
  attribute: performance
  disposition: prioritized
- id: qa-scalability
  attribute: scalability
  disposition: traded-away
- id: qa-security
  attribute: security
  disposition: prioritized
- id: qa-availability
  attribute: availability
  disposition: prioritized
- id: qa-maintainability
  attribute: maintainability
  disposition: prioritized
- id: qa-fault-tolerance
  attribute: fault-tolerance
  disposition: traded-away
- id: qa-reliability
  attribute: reliability
  disposition: not-load-bearing
constraints:
- id: constraint-1
  statement: <one checkable sentence bounding what the system holds>
  attribute: performance
  anchor_ids:
  - flow-1
- id: constraint-2
  statement: <one checkable sentence bounding what the system holds>
  attribute: security
  anchor_ids:
  - entity-1
  - rule-1
decisions:
- id: tradeoff-1
  chosen_option: <the decision of record>
  rejected_alternatives:
  - option: <the option that lost>
    reason: <why it lost>
  rationale: <why the chosen option won>
  anchor: constraint-1
  status: settled
---

# Constraints

## Dispositions

<what this project is, and why it ranks this way>. `qa-performance`,
`qa-security`, `qa-availability`, and `qa-maintainability` are prioritized.
`qa-scalability` and `qa-fault-tolerance` are traded away, which costs <one
line>. `qa-reliability` is not load-bearing here — <one line>.

## Constraints

`constraint-1` bounds `flow-1` — <one line>. `constraint-2` bounds `entity-1`
and the rule that governs it, `rule-1` — <one line>.

## Decisions

`tradeoff-1` records <one line>, and what the ranking above spends for it.
```
