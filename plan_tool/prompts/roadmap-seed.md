# Materialize roadmap seed "${plan_id}" for "${slug}"

The roadmap artifacts below have already been accepted. Draft a seed for only
the `plans` row whose `id` is `${plan_id}`. Do not revise the roadmap rows,
plan mapping, or settled decisions, and do not write a seed for another plan.

Unlike normal roadmap stages, inspect the **current repository** before you
write. Make the implementation-facing language match the code that exists now,
without broadening the accepted plan because a neighboring repository change is
tempting.

## Accepted roadmap artifacts

### `01-domain.md`

```
${domain_artifact}
```

### `02-constraints.md`

```
${constraints_artifact}
```

### `03-components.md`

```
${components_artifact}
```

### `04-roadmap.md`

```
${plans_artifact}
```

## Seed requirements

Reply with the complete draft seed alone: required provenance frontmatter
opening with `---`, followed by its prose body. Do not use an outer code fence,
a preamble, or commentary.

The frontmatter must include `roadmap_components`. Every listed component id
must resolve against this plan row's `component_ids`. A `cross-cutting` plan
may list additional component ids only when its frontmatter also sets
`cross_cutting: true`.

Keep the accepted scope contract in the prose body. Include a body-level
`## References` section that cites `01-domain.md`, `02-constraints.md`,
`03-components.md`, and `04-roadmap.md` by their literal filenames; bind the
seed to its domain entities, rules, workflows, constraints,
and relevant inter-plan assumptions; carry chosen options from upstream
artifacts as settled fences, without pasting long rejected-alternative
rationale prose — `create` re-grounds reasons against live docs; and preserve
the owning plan row's `intent` in `Outcome`, making `Out of scope / Non-goals`
and `Stop / defer` consistent with its `non_goals`. The roadmap row remains the
authoritative review statement; do not make a reviewer infer it from this
derived seed. Use these sections exactly:

- `Outcome`
- `In scope`
- `Out of scope / Non-goals`
- `Allowed behavior changes`
- `Allowed reorganization`
- `Testing`
- `Acceptance criteria`
- `Stop / defer`
- `Risks`
- `References`

Preserve the selected row's complete accepted responsibility: shared production,
consumer integration, required handoffs, and contribution to eventual acceptance.
Keep relevant source ids and artifact references identifiable, reading the
accepted narrative alongside the structured rows. Preserve the accepted
implementation route in Outcome, scope, and Acceptance criteria rather than
collapsing distinct routes into a generic component brief. Do not invent missing
assignments; surface an overly broad mapping through existing roadmap review.

Carry `ordering.depends_on` and relevant inter-plan assumptions as inputs,
expected handoffs, or conditions. Distinguish what this row delivers from what
another row supplies. Preserve the named producer and consumer operations for
source-required business transitions, including any change to a shared contract
that the accepted mapping assigns. Do not turn a required production or update
operation into only a check of supplied data. If its owner or source support is
unresolved, carry that uncertainty explicitly without assigning new scope.
Do not repartition accepted rows or implement a sibling prerequisite merely
because this row consumes it. Missing prerequisite implementation blocks eventual
execution or acceptance; it does not replace this row's implementation outcome
with a prerequisite-verification-only outcome.

`Testing` states what proves the selected outcome; `Acceptance criteria` retains
its required results. When the accepted source requires observed end-to-end
behavior or an operational result, preserve that eventual proof requirement.
Do not execute application work or live provider calls while drafting this seed;
that drafting restriction must not weaken eventual proof into document inspection
or a simulated result. Keep proof at seed level, without fixture lists,
source-file inventories, or implementation mechanics.

`Risks` must be non-empty, and every risk in it needs source text, because
`create` refuses a seed whose risks cite none. Write only risks this plan row's
accepted artifacts already state: its `Stop / defer` conditions, provisional
decisions, open stack concerns, and inter-plan assumptions that could fail.
Restate each as a risk, and invent none to fill the section. When the
artifacts state no risk for this row, write the single line
`- The accepted artifacts state no risk for this plan row.`

The tool inserts the `## Stack` section (hosting rows, store rows, and the
technology stack concerns) from the accepted artifacts itself; do not write a
`## Stack` section and do not rewrite it. A stack concern marked open stays
open: do not choose a vendor, runtime, or engine for it in the seed.

Write the sections in plain words. A seed is dense, not cryptic: use whole
sentences, one idea per bullet, and say what a domain term means the first time
the seed names it. Keep every identifier, path, and boundary; swap only the
decorative wording.

Describe the requested plan row's scope only. Preserve discharged constraints,
the accepted plan ordering, and every non-goal even when repository inspection
offers a tempting adjacent change.

The roadmap row is one part of the roadmap's smallest end-to-end proof, not an
opening to build its eventual capability. Do not turn a nearby role, workflow,
integration, operating mode, or generalized mechanism into seed scope merely
because it would make a later product more complete. Stay at the roadmap
altitude: preserve the outcome, boundaries, and ordered handoff; leave source
files, APIs, storage schemas, class or method layout, algorithms, and test
mechanics for `create` and `detail` to ground later.
