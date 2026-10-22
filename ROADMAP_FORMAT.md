# ROADMAP_FORMAT.md

> **Source of truth:** this doc is reference reading for humans and coding
> agents — the tool does **not** load it at runtime. The enforced contract
> lives in code, split by channel: **shape** (paths, frontmatter rows, closed
> vocabularies) in `plan_tool/roadmap_artifacts.py`, **relations** (the
> four stage-specific gate sets each artifact must clear — thirty `check_*`
> functions across four tuples in `plan_tool/roadmap_gates.py`) in
> `plan_tool/roadmap_gates.py`, **the version store and accepted head** in
> `plan_tool/roadmap_versions.py`, **local feedback revision** in
> `plan_tool/roadmap_revision.py`, and **candidate narrative review
> evidence** (the removed-id check `check_removed_ids_in_live_prose`, outside
> the stage tuples) in `plan_tool/roadmap_gates.py` with its evidence
> computation in `plan_tool/roadmap_candidate_narrative.py`. If this doc and the code disagree,
> the code wins — fix the doc.

The on-disk schema for a **roadmap's staged artifacts** — the four markdown
files `plan-tool roadmap` writes: `01-domain.md`, which says what the system is
about; `02-constraints.md`, which ranks the quality attributes it trades
on; `03-components.md`, which divides the domain into logical
components that own entity ids, cite patterns, discharge constraints, and name
their stores; and
`04-roadmap.md`, which maps those components to an ordered plan list with draft
seed destinations. Each has YAML frontmatter carrying a row inventory the gates
judge, and a prose body written for humans. Draft seeds materialize separately
from the stage-4 artifact.

## What a roadmap is, and what it is not

A roadmap sits one rung above a plan. It is **project-altitude** design output
— entities, business rules, workflows, quality-attribute dispositions,
constraints, and the decisions behind them — that later work cites, rather than
an ordered set of steps anyone executes.

**It is not a plan, and no plan-pipeline surface resolves one.** Roadmap
artifacts carry no steps, no `status`/`depends_on` machinery, and no manifest
entry. `plan_tool/locator.py:list_plans` globs `*.md` at the **top level** of
the plans directory only, so a file nested inside `roadmaps/<slug>/` is
invisible to it, and a roadmap run adds nothing to `.plan-tool/plans.json`.
The plan contract is a separate document — see `PLAN_FORMAT.md`.

The four artifacts are a **staged** sequence: each stage's gate-clean artifact
becomes upstream input to the next, and the four are published together as one
immutable version. A roadmap has exactly one stored copy of its content — the
immutable versions under the accepted head — and every command reads the
accepted version.

## What writes them

`plan-tool roadmap <slug> --from-existing BRIEF` — orchestrator `plan_tool/roadmap.py`, CLI handler
`plan_tool/cli/roadmap_cmd.py`, one prompt file per stage under
`plan_tool/prompts/` (`roadmap-domain.md`, `roadmap-constraints.md`,
`roadmap-components.md`, `roadmap-plans.md`). Claude runs only *inside* a
stage; the gates between stages are deterministic. A failing gate feeds its
violations back into a bounded retry of the same stage.

A stage run is the **first-run** route only: it holds each gate-clean stage in
memory and in a resume directory, then publishes the version, a ledger-native
feedback ledger, and the accepted head (written last). A roadmap that already
has an accepted head changes through the ledger feedback and candidate routes,
never through a stage run. The resume directory and its recovery are described in
[`docs/how-to/roadmap.md`](docs/how-to/roadmap.md).

The verb is **non-interactive by construction** — there is no interview to skip
or hang on. At an option point a stage guesses, records the guess as a decision
row naming what it rejected and why, and marks a genuinely load-bearing
tradeoff `pending` for an operator to confirm later.

**Versions are committed docs.** They live under the plans directory, beside
the plans and seeds that cite them, so they are reviewable and diffable. The
roadmap directory also keeps its feedback ledger, its tiny `seed-state.json`
lifecycle sidecar, the latest `seed-refresh-report.md`, and a generated
`INDEX.md`; the sidecar and report describe derived-seed freshness and its
comparison, not a fifth staged artifact. `INDEX.md` is a human-facing summary
rewritten after every version-store change; no command reads it. Run logs land
under `.plan-tool/runs/<slug>/` with every other verb's. No roadmap artifact
is written under the repo's `.plan-tool/`.

## Path convention

```
<plans_dir>/roadmaps/<slug>/.roadmap-versions/accepted-head.json # names the accepted version
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/version.json
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/brief.md
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/01-domain.md
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/02-constraints.md
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/03-components.md
<plans_dir>/roadmaps/<slug>/.roadmap-versions/<version-id>/04-roadmap.md
<plans_dir>/roadmaps/<slug>/feedback-ledger.yaml
<plans_dir>/roadmaps/<slug>/seed-state.json
<plans_dir>/roadmaps/<slug>/INDEX.md # generated; read by no command
<plans_dir>/roadmaps/<slug>/plan-seed-drafts/ # default draft-seed directory (side output)
<plans_dir>/roadmaps/<slug>/review.html # regenerated --view html output (side output)
```

The accepted-head and version-record paths come from
`plan_tool/roadmap_versions.py` (`ROADMAP_VERSION_NAMESPACE_DIRNAME`,
`ACCEPTED_HEAD_FILENAME`, `STORED_VERSION_RECORD_FILENAME`,
`STORED_BRIEF_FILENAME`). `roadmap_dir` and the constants `ROADMAP_DIRNAME`,
`DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`, and
`PLANS_FILENAME` live in `plan_tool/roadmap_artifacts.py`. Draft seeds default under
`draft_seeds_dir` using `DRAFT_SEEDS_DIRNAME` (`plan-seed-drafts`). Legacy
roadmaps may retain the accepted `seeds/` prefix. The helpers are pure — they
touch no filesystem. Besides the version store, the roadmap folder holds only
the files above and the `.plan-tool/evidence/` directory inside it.

`plans_dir` is **passed in, never hardcoded**: the caller resolves it, so
`--plans-dir` and `PLAN_TOOL_PLANS_DIR` (`plan_tool/locator.py:resolve_explicit_plans_dir`)
move the whole tree. With neither set, `cli/roadmap_cmd.py:cmd_roadmap` falls
back to `plan_tool/create.py:resolve_output_dir` (`DEFAULT_OUTPUT_DIR`), the
same default `create` writes plans under — not `locator.py:PLANS_SUBPATH`,
which holds the same value but is the discovery walk's constant and is never
consulted by this verb.

`<slug>` becomes a single path component, so `roadmap_dir` rejects one with a
`ValueError` when it is empty or whitespace-only, contains a path separator,
carries a `..` part, or is otherwise not a single component.

## Concept brief

A first stage run reads the brief named by `--from-existing`. The published
version stores its raw bytes as the member `brief.md` beside the four stage
artifacts, and the accepted version's stored brief is the only brief any later
command reads. A semantic change to the product definition goes through
reviewer feedback and candidate review, or a successor roadmap lineage; it never
re-grounds or regenerates an existing roadmap.

### Carried decisions in an admitted brief

An optional `## Carried decisions` section lets the producer preserve a closed
set of approved choices when it supplies the brief through `--from-existing`.
The section contains exactly one fenced `json` object and nothing else. Its
opening `json` fence and closing fence each use exactly three backticks at
column zero; tilde, indented, and longer fences are outside this closed input
syntax. The top-level object has exactly `confirmed_answers` and `decisions` arrays:

````markdown
## Carried decisions

```json
{
  "confirmed_answers": [
    {"id": "answer-hosting", "answer": "Use managed hosting.", "status": "confirmed"}
  ],
  "decisions": [
    {
      "id": "decision-hosting",
      "owner": "constraints",
      "anchor": "hosting-compute",
      "chosen_option": "Use managed hosting.",
      "source": "answer-hosting"
    }
  ]
}
```
````

Each confirmed answer has only `id`, `answer`, and `status: "confirmed"`.
Each decision has only `id`, `owner`, `anchor`, `chosen_option`, `source`, and
optional `rationale` and `rejected_alternatives`; each alternative has only
`option` and `reason`. `owner` is one of `domain`, `constraints`,
`components`, or `plans`; `source` names a confirmed answer, and
`chosen_option` exactly matches that answer. The block is source material, not
a general writer or lifecycle authority: only typed decisions selected for an
owner reach that stage. The raw JSON is excluded from shared stage context.

## `01-domain.md` — frontmatter schema

```yaml
---
entities: # list of rows. An absent or null collection parses as empty.
  - id: string   # required. Non-empty; unique across every row in the roadmap.
    name: string # required. Human-facing name of the thing.
    fields:      # required key. What the entity holds. Present-and-empty
                 # parses; the gate rejects an entity that holds nothing.
      - name: string # required. Unique within this entity (not across them).
        type: text | number | boolean | timestamp | enum | reference
                     # required. See Closed vocabularies.
        entity_id: string # required on a `reference` field, rejected on any
                          # other. The id of the entity pointed at.
business_rules:
  - id: string        # required.
    statement: string # required. The rule, in one sentence.
    entity_ids: [string, ...] # required key. Ids of the entities the rule
                              # governs. Present-and-empty parses; the gate
                              # rejects a rule that names none.
workflows:
  - id: string
    name: string # required. What the path through the domain does.
    entity_ids: [string, ...] # required key. Ids of the entities it touches.
decisions:
  - id: string
    chosen_option: string # required. The decision of record.
    rejected_alternatives: # required key. Present-and-empty parses; the gate
                           # rejects a decision that rejects nothing.
      - option: string # required. The option that lost.
        reason: string # required. Why it lost.
    rationale: string # required. Why the chosen option won.
    anchor: string    # required. The id of the row this decision bears on.
    status: settled | pending # required. See Closed vocabularies.
---
```

The schema above shows the Roadmap-derived form. The inherited form in any
artifact is instead:

```yaml
decisions:
  - id: string
    chosen_option: string
    source: string # required; a confirmed-answer id in the admitted brief.
    rationale: string # optional; omit when upstream supplied none.
    rejected_alternatives: # optional; omit when upstream supplied none.
      - option: string
        reason: string
    anchor: string
    status: settled # required for an inherited row.
```

`fields` is what stops every plan derived from the roadmap re-inventing an
entity's shape, and it is deliberately coarse. **What it records:** a field's
name, its *logical* type, and — for a reference — the entity it points at.
**What it does not, and what no gate checks:** whether the fields are the right
ones or a complete set; optionality or nullability; cardinality; validation
rules; physical or storage types (`varchar(255)` is a plan's decision, not a
roadmap's). The gate judges presence and shape only, because that is the part
that is observable before any code exists.

Parsed by `parse_domain_artifact` into a frozen `DomainArtifact` — the row
tuples `entities`, `business_rules`, `workflows`, `decisions` (types
`EntityRow`, `BusinessRuleRow`, `WorkflowRow`, `DecisionRow` /
`RejectedAlternative`, with `FieldRow` nested on `EntityRow.fields`) plus
`body`. Rows stay an **ordered tuple, not a dict
keyed by id**, so a duplicate id survives parsing and the duplicate-id gate has
something to report. `load_domain_artifact` is the read-then-parse form that
binds the file path to every failure.

`business_rules` carry entity ids for the same reason workflows do: a
constraint may anchor to a rule id, so a rule connected to no entity would be a
valid anchor target that breaks the entity→constraint traceability chain.

### Decision row forms

Every artifact's `decisions` collection uses `DecisionRow`, with two visibly
different forms. A Roadmap-derived row has no `source` and requires
`rejected_alternatives` and a non-blank `rationale`; its alternatives describe
the trade-offs the Roadmap stage made. An inherited row has a `source` citation
and is an approved upstream record: it remains `status: settled`, and it may
retain `rationale` or `rejected_alternatives` only when the admitted brief
supplies them. The renderer omits either optional inherited field when absent;
it never renders a null placeholder. Explicit `null` is not absence for these
decision text fields and fails parsing.

Both forms require `id`, `chosen_option`, `anchor`, and `status`. An inherited
row's citation names the matching confirmed answer in the current accepted
brief. It appears once, only in the artifact named by its source `owner`, and
its approved anchor names a live design row in that same artifact. The row
therefore records an inherited fence, not a Roadmap trade-off.

Material feedback and model revisions have no authority to add, edit, or
remove an inherited row. An unrelated revision carries it forward and the
inherited-decision gate validates it again against the current accepted brief
before publication.

## `02-constraints.md` — frontmatter schema

```yaml
---
hosting: # exactly one row per fixed facet — membership is a gate, not a parser rule.
  - id: string        # required. Unique across the roadmap, but not anchorable.
    facet: string     # required. One of compute, model, or topology.
    value: string     # required. See Hosting facets and values below.
    product: string   # optional on compute; an unknown facet remains parseable for its gate.
    description: string # optional operator text. No vocabulary or quality rule.
    research_disclosure: external | local # optional. Only external permits outbound product research.
stack: # optional key. Absent = stack not recorded; `stack: []` = recorded, and empty.
  - id: string        # required. Unique across the roadmap; anchorable by a decision.
    concern: string   # required. One of platform, store-engine, or language-runtime.
    choice: string    # exactly one of `choice` (non-blank) or `open: true` per row.
    open: true        # the concern is explicitly undecided; omit when `choice` is set.
dispositions: # exactly one row per quality attribute — see Closed vocabularies.
  - id: string        # required. The attribute's only handle in the anchor space.
    attribute: string # required. One of the shipped quality attributes.
    disposition: prioritized | traded-away | not-load-bearing # required.
constraints:
  - id: string
    statement: string # required. The constraint, in one sentence.
    attribute: string # required. The quality attribute it discharges.
    anchor_ids: [string, ...] # required key. Ids in 01-domain.md that it
                              # constrains. Present-and-empty parses; the gate
                              # rejects a constraint anchored to nothing.
decisions: # either DecisionRow form documented above.
  - id: string
    chosen_option: string
    rejected_alternatives:
      - option: string
        reason: string
    rationale: string
    anchor: string
    status: settled | pending
---
```

Parsed by `parse_constraints_artifact` into a frozen `ConstraintsArtifact` —
`hosting`, `stack`, `dispositions`, `constraints`, `decisions` (types
`HostingRow`, `StackRow`, `AttributeDispositionRow`, `ConstraintRow`,
`DecisionRow`) plus `body`;
`load_constraints_artifact` is the path-binding read-then-parse form.

A disposition row's `id` is **the only way a quality attribute reaches the
anchor space**. Attribute names are a constant, not rows, so a decision
anchored to the bare word `security` resolves nowhere; anchor it to the
disposition row's id instead.

Hosting rows are identity-only: their ids join the global duplicate-id check,
but they do not enter decision anchors, feedback targets, prose inventory, or
revision continuity. A hosting row's shape parses independently of its facet
and value, with one exception: `product` on a `model` or `topology` row is a
parse-time error, not a gate violation, because it is a malformed row rather
than an incomplete or unrecognized answer. Every other hosting defect —
missing, redundant, or unknown facet; unrecognized value; incoherent topology
— is a constraints gate, so a retried stage can correct it from an itemized
violation. `description` is optional operator text with no vocabulary or
quality rule; it is distinct from `product`, which names a product where that
field is permitted. Only `research_disclosure: external` explicitly permits
the row's trimmed product literal to leave the repository for external research;
`local`, absence, and `null` keep it local. A local row selected for research
requires a nonblank description instead of a generic query.

### Stack rows

The `stack` collection records the technology stack as a distinct concern layer
with one row per concern in `STACK_CONCERNS`: `platform` (the deployment
platform), `store-engine`, and `language-runtime`. It is display and constraint
text, not a judgment: no gate or callout evaluates whether a choice is good.

| Case | Meaning |
| --- | --- |
| `stack` key absent | Stack not recorded. Every version that predates the collection reads this way, and it re-renders with no `stack` key. |
| `stack: []` | Recorded, and empty. A recorded empty stack is not "not recorded"; the key survives a render. |
| Row with a non-blank `choice` | The concern is chosen. The tool does not interpret the text. |
| Row with `open: true` | The concern is explicitly undecided. A stage records `open` instead of inventing a choice. |

A row is exactly one of the last two. The parser checks types only; a row
carrying both or neither parses, and `check_stack_totality` refuses it as
`stack-row-state` on every route. Whether a concern is
*pending* is never stored on the row: it is derived from a `pending` decision
whose `anchor` is the row's id.

**Where the gate binds.** `check_stack_totality` runs in `CONSTRAINTS_GATES` on
every constraints artifact and binds only when the artifact carries the
collection. The constraints stage prompt (`roadmap-constraints.md`) is what asks
a first run to author it. The gate never binds on absence alone: an accepted
version without a `stack` key stays valid, and an unrelated candidate in that
lineage is not refused for lacking one. A candidate that introduces the
collection must carry every concern in that one candidate, because totality
binds the moment the collection is present.

| Rule | Enforcer | Violation `kind` |
| --- | --- | --- |
| Every concern in `STACK_CONCERNS` has a row | `check_stack_totality` | `missing-stack-concern` |
| A row names one of those concerns | `check_stack_totality` | `unknown-stack-concern` |
| A row id is declared once | `check_stack_totality` | `duplicate-stack-id` |
| A concern is carried by one row | `check_stack_totality` | `duplicate-stack-concern` |
| A row is exactly one of `choice` or `open: true` | `check_stack_totality` | `stack-row-state` |

**Ids, anchors, and feedback.** Stack ids join the global duplicate-id check
and the anchor union, so a decision can anchor to a stack row. Stack rows are
not ledger feedback targets (the ledger addresses design rows only), but a candidate can add, replace, and revise them, and a decision can anchor to one; the `concern`
field is fixed on edit and a row cannot be removed (`stage_row_operation_policy`
for `stack`: `allow_remove` false, `immutable_fields` of `concern`), so a
recorded stack never reverts to "not recorded" through a typed operation. (The embedded `removals` route stays open to a row the reviewer's own open feedback asked to drop, as for any design row.) A stack row has no row-owned
prose span.

**Authority.** Stack rows are authoritative over the `product` field of a
hosting row and of a store row. No gate compares them; candidate review prints
them side by side.

**Callouts.** The stack is shown, as display only, at three surfaces, all
produced by `plan_tool/roadmap_stack_summary.py`: the first-run completion
output (`_stack_summary_output_lines` in `plan_tool/cli/roadmap_cmd.py`), the
generated `INDEX.md` (`collect_index_stack_lines` in
`plan_tool/roadmap_index.py`), and candidate review
(`_print_candidate_stack_callout` in `plan_tool/cli/roadmap_cmd.py`), which adds
the stack rows a candidate added, changed, and opened beside the listed hosting
and store products. The first-run output and `INDEX.md` list open concerns and
pending concerns apart from the chosen ones; the candidate callout shows the
added, changed, and opened rows instead. The callout is not narrative evidence, adds no defect class, and
never blocks approval. The same rows render into the tool-owned `## Stack` seed
section; see [Stack section](#stack-section).

## `03-components.md` — frontmatter schema

```yaml
---
system_patterns: # list of rows. An absent or null collection parses as empty.
  - id: string        # required. Non-empty; unique across every row in the roadmap.
    name: string      # required. Human-facing name of the pattern.
    statement: string # required. The pattern, in one sentence.
component_patterns: # same row shape, different scope — reusable decomposition shapes.
  - id: string
    name: string
    statement: string
stores: # list of concrete persistence definitions. Absent or null parses empty.
  - id: string # unique across every row id in the roadmap, identity-only.
    category: in-process | relational | document | key-value | object
    sharing: silo | pool | bridge
    product: string # optional free-text product name; recorded but not gated.
    description: string # optional operator text. No vocabulary or quality rule.
    research_disclosure: external | local # optional. Only external permits outbound product research.
components:
  - id: string
    name: string # required. What the logical unit is called.
    entity_ids: [string, ...] # required key. Entity ids from 01-domain.md only.
                               # Present-and-empty parses; the gate rejects a
                               # component that owns none.
    pattern_ids: [string, ...] # required key. Pattern ids from system_patterns
                               # or component_patterns. Present-and-empty
                               # parses; the gate rejects a component citing none.
    constraint_ids: [string, ...] # optional key. Constraint ids from
                                   # 02-constraints.md this component discharges.
                                   # Absent or empty is not a discharge claim.
    store_ids: [string, ...] # optional at parse time. Every component must
                              # name at least one defined store through the
                              # components gates.
decisions: # either DecisionRow form documented above.
  - id: string
    chosen_option: string
    rejected_alternatives:
      - option: string
        reason: string
    rationale: string
    anchor: string
    status: settled | pending
---
```

**Purpose:** divide the domain into logical components. Each component owns
entity ids from `01-domain.md` (`entity_ids` cites **entity ids only** — not
workflow, rule, or field-name anchors), cites the patterns that shape it
(`pattern_ids` resolves across **both** `system_patterns` and
`component_patterns`), may claim constraint discharge (`constraint_ids`), and
names the store definitions it uses (`store_ids`).

Parsed by `parse_components_artifact` into a frozen `ComponentsArtifact` — the
row tuples `system_patterns`, `component_patterns`, `stores`, `components`,
`decisions` (types `PatternRow`, `StoreRow`, `ComponentRow`, `DecisionRow`)
plus `body`. Rows stay an
**ordered tuple, not a dict keyed by id**, so a duplicate id survives parsing
and the duplicate-id gate has something to report. `load_components_artifact`
is the read-then-parse form that binds the file path to every failure.

The design-row inventory for prose and continuity gates is
`components_design_rows` — system patterns, component patterns, components,
then decisions, in render order. Store rows are identity-only: their ids join
the global duplicate-id check, but they do not enter anchors, feedback targets,
prose inventory, or revision continuity. `description` is optional operator
text with no vocabulary or quality rule; it is distinct from `product`, which
names a known store product. Only `research_disclosure: external` explicitly
permits the row's trimmed product literal to leave the repository for external research;
`local`, absence, and `null` keep it local. A local row selected for research
requires a nonblank description instead of a generic query.

`feedback` / `removals` follow
[The review collections](#the-review-collections--feedback-and-removals) and
attach to `ComponentsArtifact` the same way they attach to the other artifacts.

**What parse time deliberately lets through** on a components artifact — each
owned by a gate in the table below, not by `parse_components_artifact`:

- dangling entity, pattern, constraint, or store ids;
- duplicate ids within or across artifacts;
- empty `entity_ids` or `pattern_ids` on a component row;
- absent or empty `store_ids` on a component row;
- empty `system_patterns` or `component_patterns` collections;
- a domain entity id owned by no component;
- a prioritized constraint cited by no component's `constraint_ids`.
- an unused store, repeated store reference, shared `in-process` store, or
  unknown store category or sharing value.

## `04-roadmap.md` — frontmatter schema

```yaml
---
plans: # list of rows. An absent or null collection parses as empty.
  - id: string   # required. Non-empty; unique across every design row in the
                 # roadmap. Also the create slug in printed next-steps.
    title: string # required. Human-facing plan name.
    intent: string # authored operational outcome. Optional only for a legacy
                 # row already on disk; new stage-4 output must be non-blank.
    non_goals: [string, ...] # explicit adjacent, prerequisite, or deferred
                 # work this plan does not deliver. Optional only for a legacy
                 # row; new stage-4 output must provide at least one.
    disposition: keep | merge | split | cross-cutting # required. See Closed
                 # vocabularies — not the same enum as constraint disposition.
                 # It is the delivery shape: cross-cutting means component
                 # ownership is not required; other values are component-owned.
    component_ids: [string, ...] # optional key. Component ids from
                 # 03-components.md. Present-and-empty parses; a non-cross-cutting
                 # plan that names none is a gate finding, not a parse error.
    draft_seed_path: string # required. Relative path from the roadmap slug root,
                 # e.g. plan-seed-drafts/checkout-core.md — uses the draft prefix.
    sizing_rationale: string # required key. Why this plan is sized this way.
                 # Blank parses.
ordering: # ordered sequence — mints no row ids.
  - plan_id: string # required. A plan row id from plans.
    depends_on: [string, ...] # optional key. Plan ids that must run first.
    assumption_targets: [string, ...] # optional key. Plan ids this entry's
                 # ordering-level assumptions bear on — not assumption inventory
                 # rows.
assumptions:
  - id: string
    statement: string # required. The inter-plan assumption, in one sentence.
    consuming_plan_ids: [string, ...] # required key. Plan ids that consume it.
                 # Present-and-empty parses; the gate rejects an assumption
                 # citing none.
decisions: # either DecisionRow form documented above.
  - id: string
    chosen_option: string
    rejected_alternatives:
      - option: string
        reason: string
    rationale: string
    anchor: string
    status: settled | pending
feedback: / removals: # same review contract; attach to PlansArtifact.
---
```

**Purpose:** map components to the smallest end-to-end proof of the brief's
central outcome — not the eventual product capability — as an ordered plan list
with closed dispositions. State each plan's intended operational outcome and
explicit boundaries; carry ordering, inter-plan assumptions, and review
collections; and advertise where each plan's draft seed will land. This is
roadmap altitude: outcome, tradeoffs, ownership, and ordering. The later
`create` and `detail` path grounds source files, APIs, storage schemas,
implementation mechanics, and tests. A plan row's `id` is also the `create`
slug in printed next-steps — it must satisfy `PLAN_ID_SLUG_RE`, which mirrors
`plan_tool/create.py`'s slug rule (lowercase letters, digits, and hyphens only,
starting and ending with a letter or digit).

Parsed by `parse_plans_artifact` into a frozen `PlansArtifact` — the row
tuples `plans`, `ordering`, `assumptions`, `decisions` (types `PlanRow`,
`OrderingEntry`, `AssumptionRow`, `DecisionRow`) plus `body`. Rows stay an
**ordered tuple, not a dict keyed by id**, so a duplicate id survives parsing
and the duplicate-id gate has something to report. `ordering` stays an ordered
sequence — not a dict keyed by plan id. `load_plans_artifact` is the
read-then-parse form that binds the file path to every failure.

The design-row inventory for prose and continuity gates is
`plans_design_rows` — plans, assumptions, and decisions, in that order.
**Ordering entries mint no row ids** and are excluded from the inventory.

`render_plans_artifact` emits only `PLANS_ROW_KEYS` plus non-empty review keys
(`plans`, `ordering`, `assumptions`, `decisions`, then `feedback` /
`removals` when present).

**What parse time deliberately lets through** on a plans artifact — each owned
by a gate in the table below, not by `parse_plans_artifact`:

- dangling component ids on plan rows;
- duplicate ids within or across artifacts;
- a domain component id covered by no plan row;
- ordering that lists a plan id more than once, omits one, or references an
  undefined plan id in `depends_on` / `assumption_targets`;
- plan ids that fail the create slug rule;
- duplicate `draft_seed_path` basenames across plan rows;
- unknown plan ids in `consuming_plan_ids`;
- assumption rows citing no consuming plans.
- a blank or absent legacy `intent`, or absent `non_goals`; stage 4
  rejects these missing review fields when it generates a plans artifact, while
  read-only views annotate them.

## Draft seeds under the roadmap slug

Draft seeds are **not** a fifth numbered roadmap artifact. A plan row declares
where its draft will materialize beside `04-roadmap.md`; the materialization
surface validates each draft on disk after generation.

**Default location** — `<plans_dir>/roadmaps/<slug>/plan-seed-drafts/` via
`DRAFT_SEEDS_DIRNAME`; `draft_seeds_dir(plans_dir, slug)` returns that path.
Each plan row's `draft_seed_path` is relative to the slug directory (for example
`plan-seed-drafts/checkout-core.md`). `resolve_draft_seed_path` validates segment
safety — no absolute paths, no `..`, and the path must begin with
`plan-seed-drafts/` or the legacy `seeds/` prefix.

**Validation** — `materialize_plan_seed` writes each draft through the shared
per-plan materializer. `classify_draft_seeds` checks its recorded identity and
`validate_draft_seed_content` checks provenance against the owning plan row.
`check_draft_seed_bundle_alignment` continues to reject plan rows whose draft
paths share a basename.

An unmatched opening code fence in a draft body is a materialization refusal
from `validate_draft_seed_content`; add its matching closing fence before the
draft can become a seed.

**Provenance frontmatter** — materialization and classification validate this
shape after a draft reaches disk:

```yaml
---
roadmap_components: [string, ...] # required. Component ids this seed cites.
cross_cutting: true               # optional boolean. When true on a
                                  # cross-cutting plan, provenance may list
                                  # component ids the plan row omits.
---
```

Parsed by `parse_draft_seed_provenance` into `DraftSeedProvenance`; rendered by
`render_draft_seed_provenance`. Wire keys are `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`
(`roadmap_components`) and optional `DRAFT_SEED_CROSS_CUTTING_KEY`
(`cross_cutting`).

**Seed body** — see `SEED_FORMAT.md` for the scope-contract fence and authoring
density. **No gate checks:** Outcome quality, agreement between seed body and
roadmap prose beyond inventory id presence, seed length, plan count, technology
names in `## Stack` compared against the plan's design, and any note or conflict
surfaced by `create` or `detail` (deliberately not built, decided 2026-10-08:
recognizing that a design contradicts a stack is a semantic judgment the tool
cannot observe; the plan audit is the contradiction check, and it is advisory).

**After `--apply`** — new promoted copies under `docs/implementation-plans/plan-seeds/` drop the provenance
block and carry a machine-readable HTML comment that links the copy (and any
later archive generation) to its roadmap lifecycle state; see
`plan_tool/cli/roadmap_cmd.py` for apply semantics. The promoted copy carries
the `## Stack` section, and a rematerialization rewrites it there too.
Refresh and `--accept-seed` rewrite a promoted copy only for a seed whose state
records `published: true`; an existing file at either publication destination alone is not
proof the tool wrote it, so an unpublished seed's file is left untouched and
`--apply` refuses it as a collision.

### Stack section

> **Enforced by:** `_render_stack_section` and `_replace_stack_section` in
> `plan_tool/roadmap.py`

Every draft carries a tool-written `## Stack` section so `create` and `detail`
take the accepted hosting and store choices as settled constraints instead of
choosing a technology of their own.

| Part | Content |
| --- | --- |
| Lead line | The accepted version id, with the instruction to treat the rows as constraints, not options |
| `### Hosting` | Every hosting row: `id`, `facet`, `value`, `product` |
| `### Stores` | Each store reached through the plan row's component ids, once: `id`, `category`, `sharing`, `product` |
| `### Technology stack` | Every `stack` row of the accepted version: `id`, `concern`, and either `choice: …` or `open — not decided by the accepted roadmap`; an unrecorded stack and a recorded empty stack each read as their own `(none)` line |

A row with no `product` renders as `product left open by the accepted roadmap`;
a missing product is never printed as `None` or left blank. The section is
always emitted: with no hosting rows it reads `(none) The accepted roadmap lists
no hosting rows.`, and with no store reached by the plan it reads `(none) This plan row's
components name no store, so none is listed here.`

**Ownership.** The tool writes the section from the accepted bytes and replaces
any model-authored `## Stack` in the generated draft. A hand edit to the section
is overwritten on the next `--materialize` or `--refresh-seeds`; `--accept-seed`
keeps a hand-edited draft only until that next rematerialization. To change a
stack choice, change the roadmap through feedback and rematerialize.

`create --from-existing` preserves the section in the plan body verbatim
(`GUARDRAIL_BODY_SECTIONS` in `plan_tool/scope_fence.py`), the `detail` scope
fence carries it, and the plan audit treats it as authoritative. A draft
materialized before the section existed lacks it until it is rematerialized
(`--materialize` or `--refresh-seeds`).

**Deliberately not built** (decided 2026-10-08): a hosting question or hosting
input requirement in the brief, owner-provenance on hosting rows, an
inapplicable-hosting answer (the hosting gates already guarantee a defined
stack; vendor or runtime clarification goes through the feedback lifecycle),
conflict surfacing or technology-name comparison in `create` and `detail`, and
carrying `## Stack` into the Jira handoff.

### Invalidation and explicit refresh

When a roadmap revision applies feedback, or a stage-4 write replaces
`04-roadmap.md`, every tracked derived seed is marked **invalidated**. A stage
never overwrites the draft files: a seed may be under review, promoted, or
already serving as a `create --from-existing` input. If an invalidated seed is
given to `create`, the operator must explicitly confirm continuing (or use
`-y` for an unattended explicit confirmation).

`plan-tool roadmap <slug> --materialize [PLAN_ID]` regenerates selected
recoverable drafts. `plan-tool roadmap <slug> --refresh-seeds` keeps `01`–`04`
unchanged, reprocesses each current plan row against the current codebase, and
writes `<roadmap>/seed-refresh-report.md` with a unified diff from the last
live or archived generation. A draft consumed by `create` or moved into its
`plan-seed-drafts/archive/` directory is recreated at its original live path;
a promoted copy at its recorded destination is refreshed or recreated too, but only for a seed
the state records as published. `plan-tool roadmap
<slug> --accept-seed PLAN_ID` records a reviewed `digest-mismatched` hand edit's
live digest as `current` without calling the backend or regenerating the draft.

### Draft-seed manifest states

> **Enforced by:** `plan_tool/roadmap_seed_manifest.py`

`classify_draft_seeds` recomputes each plan row's draft state from its live file,
the plan row, and `seed-state.json`; it never writes either source. Every row is
exactly one of `duplicate`, `path-escaping`, `missing`, `digest-mismatched`,
`stale`, `malformed`, or `current`, using that order as first-match-wins
precedence. A duplicate plan path wins before any file read; an unsafe sidecar
path wins before a missing file; and a known digest must match before an
invalidated or content-valid draft is trusted.

A draft whose body fails `validate_draft_seed_content` is `malformed`. Besides
the provenance, component, and fence checks, the body carries a `## References`
section citing the four accepted artifacts by filename and a non-empty
`## Risks` section (`missing-draft-seed-risks`). Presence is the only
observable: a fenced example or a `_(TODO)_`-style placeholder does not count,
and what a risk says is not judged (`create` refuses a risk with no source
text). A plan row whose artifacts state no risk says so in one line. A draft
written before the `Risks` requirement is `malformed` until `--refresh-seeds`
regenerates it, or a hand edit adds the section and `--accept-seed PLAN_ID`
records it (a hand edit first classifies `digest-mismatched`).

`Testing` and `Acceptance criteria` are evidence-only sections that a roadmap
seed does not carry. They are deliberately not gated here: `create` refuses a
seed that gives them no source text, and no refusal measured on a real run
justifies a presence rule for them yet.

`plan_tool/roadmap_seed_manifest.py` is a leaf below `roadmap.py` and
`roadmap_view.py`, like `roadmap_gates.py`. `cli/authoring.py` consumes it for
`create --from-existing`; roadmap execution and views are designed to call the
same classifier as their manifest features grow.

**Example draft seed** (provenance + stub body — tested separately from artifact
examples):

```markdown
---
roadmap_components:
  - component-checkout
---

# Checkout core

Outcome: _(stub — see SEED_FORMAT.md for the scope-contract fence.)_
```

The runnable `04-roadmap.md` example under [Examples](#examples) declares
draft destinations only.

## The schema is open, and rendering is closed

A frontmatter key the contract does not name is **ignored, not rejected** — a
harmless extra field would otherwise cost a stage retry. The optional nested
`feedback_reopen` mapping is the narrow exception: its shape is closed so it
cannot retain response or evidence metadata. The renderers
(`render_domain_artifact`, `render_constraints_artifact`,
`render_components_artifact`, `render_plans_artifact`) emit only the contract's
keys, in the order `DOMAIN_ROW_KEYS`, `CONSTRAINTS_ROW_KEYS`,
`COMPONENTS_ROW_KEYS`, and `PLANS_ROW_KEYS` declare, and reproduce the prose
body byte for byte. Those four constants are the canonical wire-key inventory;
they are deliberately free to differ from the dataclass field names.

## The review collections — `feedback` and `removals`

Every artifact may carry two further collections, documented once because all
four carry them under the same keys with the same shape. They are the **reviewer's**
channel: a `feedback` row is a redirect written in the reviewer's own words,
and a `removals` record accounts for a design row a revision dropped because
one of those rows asked for it.

Their wire keys are `REVIEW_ROW_KEYS`, deliberately a separate constant from
`DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS` / `COMPONENTS_ROW_KEYS` /
`PLANS_ROW_KEYS`. Those four name the rows a stage prompt asks the model to
*author*; these arrive from a reviewer's edit, so folding them in would put
feedback ids into the design-row inventory the gates walk. **Both are omitted
entirely when empty** (`_review_mappings`), which is why a first run's artifact
shows neither key — an unreviewed artifact renders exactly the design keys above.

```yaml
---
feedback: # list of rows. An absent or null collection parses as empty.
  - id: string   # required. Non-empty. Its own namespace — see below.
    target:      # required. What the request bears on — a tagged union.
      kind: artifact | row # required. See Closed vocabularies.
      row_id: string       # required on `kind: row`, rejected on
                           # `kind: artifact`. The design row id it bears on.
    request: string # required key. The reviewer's own words. Blank parses.
    state: open | awaiting-review | deferred # required. See Closed vocabularies.
    proposed_response: string # what the model offered back. Required and
                              # non-blank on an `awaiting-review` row, optional
                              # on the other two.
    feedback_reopen:          # optional closed, redacted reopen fact.
      selector:               # exactly this receipt-safe mapping.
        artifact_key: string
        feedback_id: string
      reason: operator-confirmed-evidence-unavailable
      nonce: string           # 43 URL-safe characters from token_urlsafe(32).
      recorded_at: timestamp  # UTC RFC 3339, six fractional-second digits, `Z`.
removals:
  - removed_id: string # required. The design row id that went. A removal mints
                       # no id of its own — nothing references one.
    rationale: string  # required key. Why the row went. Blank parses.
    feedback_ids: [string, ...] # required key. The feedback ids that asked for
                                # it. Present-and-empty parses; the continuity
                                # gate rejects a removal citing none.
---
```

Parsed into `FeedbackRow` (with `FeedbackTarget` nested under `target` and an
optional `FeedbackReopenRecord`) and `RemovalRecord`, carried on
`DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, and
`PlansArtifact` as the tuple fields `feedback` and `removals`. All default to
empty, so a parse of an artifact without them is the same value it always was.

`feedback_reopen` is a closed redacted record for the current open recovery,
not response history. A fresh normal stage response clears the record before it
returns the row to `awaiting-review`. Its `selector` carries exactly the
receipt-safe `artifact_key` and `feedback_id` strings, `reason` is exactly
`operator-confirmed-evidence-unavailable`, and `nonce` is exactly the
43-character URL-safe value shape `secrets.token_urlsafe(32)` produces.
`recorded_at` is a real UTC RFC 3339 timestamp with six fractional-second
digits and trailing `Z`. It rejects every other nested key: no
`proposed_response`, response text, evidence, digest, path, attestation, or
free-form operator statement belongs in the record.

**The target is a tagged union, and the tag travels with its payload.**
`kind: row` carries the `row_id` of the design row the request bears on;
`kind: artifact` carries none and must not. There is deliberately **no sentinel
id** for artifact-wide feedback: neither reading depends on a sibling key's
absence, so a mistyped `row_id` cannot quietly become "the whole artifact".

**Feedback ids are their own namespace.** `check_duplicate_row_ids` walks the
design rows only, so a feedback row may carry the same id as an entity without
colliding. A removal's `feedback_ids` resolve against feedback rows; a target's
`row_id` and a decision's `anchor` resolve against design rows. Nothing
resolves against the union of the two.

**A row is local to the artifact holding it.** It guides that artifact's stage
and reaches no other — a `row`-kind target names a row in the same file, and a
removal cites feedback in the same file. An instruction that should shape both
artifacts is written into both, once each. Nothing propagates.

### The feedback lifecycle

Five situations, one state vocabulary, and one rule about who may move a row:
**the model makes exactly one move — `open` → `awaiting-review`, adding a
`proposed_response`.** A fresh normal stage response clears the record from any
previous confirmed reopen. Ordinary close, defer, and reopen moves remain the
reviewer's edits in their editor before the next run. The gate that holds the
model transition is `check_feedback_integrity`; the end-to-end operator
walkthrough — where to write a request and how a proposal is reviewed — belongs to
[RUNBOOK → redirecting a proposal with feedback](RUNBOOK.md#redirecting-a-proposal-with-feedback).

**1. `open` — the reviewer writes the request.** This is the only state that
travels to the model as active guidance.

```yaml
feedback:
- id: fb-settlement-is-not-single
  target:
    kind: row
    row_id: decision-one-payment-per-order
  request: Refunds are in scope, so settlement is not one movement of money.
  state: open
```

**2. `awaiting-review` — the revision proposes a response.** The state says a
response is on offer, not that anyone accepted it; ordinary moves out of it
remain reviewer edits.

```yaml
feedback:
- id: fb-settlement-is-not-single
  target:
    kind: row
    row_id: decision-one-payment-per-order
  request: Refunds are in scope, so settlement is not one movement of money.
  state: awaiting-review
  proposed_response: Split the decision — settlement stays single, and a refund
    is a second payment row against the same order.
```

**3. `deferred` — the reviewer parks it.** Set by hand. A deferred row keeps
its text in the file and stops being sent as active guidance.

```yaml
feedback:
- id: fb-settlement-is-not-single
  target:
    kind: row
    row_id: decision-one-payment-per-order
  request: Refunds are in scope, so settlement is not one movement of money.
  state: deferred
  proposed_response: Split the decision — settlement stays single, and a refund
    is a second payment row against the same order.
```

**4. Reopened — the reviewer sets the state back to `open`.** The response may
be cleared or kept; keeping it leaves the prior response readable beside the
request. The next run of that artifact's own stage sends the row again.

```yaml
feedback:
- id: fb-settlement-is-not-single
  target:
    kind: row
    row_id: decision-one-payment-per-order
  request: Refunds are in scope, so settlement is not one movement of money. A
    refund and a payment are the same row kind, so say what distinguishes them.
  state: open
```

**Ledger reopen.** A retained reviewer ledger item reopens with
`plan-tool roadmap <slug> --reopen-ledger-feedback ITEM_ID`; the ledger owns
that state, see [Roadmap feedback ledger format](ROADMAP_FEEDBACK_FORMAT.md).
It does not edit an artifact's `feedback` rows.

**5. Closed — the reviewer deletes the row.** There is no `closed` member,
because a closed request is not state the artifact carries; git holds the
record. The whole move is a deletion, here of the row carrying a response
beside one the reviewer is still working:

```yaml
# before
feedback:
- id: fb-settlement-is-not-single
  target:
    kind: row
    row_id: decision-one-payment-per-order
  request: Refunds are in scope, so settlement is not one movement of money.
  state: awaiting-review
  proposed_response: Split the decision — settlement stays single, and a refund
    is a second payment row against the same order.
- id: fb-name-the-buyer
  target:
    kind: artifact
  request: Nothing here names the person placing the order.
  state: open
```

```yaml
# after
feedback:
- id: fb-name-the-buyer
  target:
    kind: artifact
  request: Nothing here names the person placing the order.
  state: open
```

Delete the last row and the `feedback` key goes with it: the artifact renders
exactly the design keys again, as it did before anyone reviewed it.

**What `deferred` actually buys, because the word oversells it.** A deferred
row is retained reviewer-owned input but is no longer active guidance. Only
`open` rows activate the bounded stage-feedback route; retained
`awaiting-review` and `deferred` rows do not cause a backend request.

**Answering a clarifying question.** A `proposed_response` may be a question
rather than a change. Immutability of `id`, `target`, and `request` binds the
**model**, not the reviewer: answer by amending that row's `request` in place
(or by adding a follow-up row) and setting the state back to `open`, as
situation 4 shows. The predecessor is snapshotted from disk *after* your edits,
so the amended request is what the gates compare the next revision against.
Reopening an **unchanged** request just re-asks the same ambiguous thing — the
one move that looks right and does nothing.

**Un-settling a decision makes a change *possible*; a `feedback` row is what
*requests* it.** These are two different acts and only the second moves the
artifact. A `settled` decision blocks a revision from changing what it pins, so
setting it to `pending` lifts the block — but lifting a block is not a request,
and a revision with an empty feedback channel is a no-op no matter what the
artifact contradicts. To change something a settled decision was blocking,
**do both**: set the decision `pending` *and* leave an `open` feedback row
saying what you want.

### The removal record

A design row disappears from a revision only when a `removals` record accounts
for it. The record names the dropped row (`removed_id`), says why
(`rationale`), and cites at least one feedback id from the artifact the
reviewer edited (`feedback_ids`) — which is what stops a model from dropping a
row on its own authority. It mints no id of its own, so nothing anchors to a
removal and `removed_id` is the only handle its violation messages name.

A record the predecessor already carried is history: it is carried forward
untouched and never re-judged against the predecessor, so a citation naming
feedback the reviewer has since closed does not become a violation nobody can
fix. Pruning a carried record is the reviewer's move, and it is how a removed
row is later allowed back.

Candidate review reads a carried record as the source of the removed ids that
live prose must not still name; see [Narrative review
evidence](#narrative-review-evidence).

## Reviewer feedback and candidate lifecycle

Mutable reviewer feedback lives outside immutable roadmap artifacts. [Roadmap feedback ledger format](ROADMAP_FEEDBACK_FORMAT.md) owns its schema, editing rules, and worked examples. Ordinary feedback has one selector-free intake: `--propose-candidate` validates typed operations and stores either a bounded or structural inert candidate from one exact ledger batch. A candidate stack is structural when any unpromoted candidate above the recorded accepted root stores a structural route, and its top candidate receives one exact approve/edit/reject decision that covers the whole stack; approval is two invocations, and only the invocation that carries the matching stack digest seals the top candidate's identity, edit stores a replacement for a fresh decision, and rejection releases only the active candidate and drops the unpromoted hops. Candidate creation, review, replacement, rejection, and staleness never overwrite a live artifact or advance the accepted head. Both approval paths, `plan_tool/roadmap_candidate_review.py:seal_review` and the approve branch of `plan_tool/roadmap_candidate_review.py:decide_structural_candidate`, recompute narrative evidence and refuse a blocking class; see [Narrative review evidence](#narrative-review-evidence).

A candidate carries prose authority through two operations. `plan_tool/roadmap_candidate.py:CandidateAddRow` carries a row-owned prose amendment for a row the same candidate adds. `plan_tool/roadmap_candidate.py:CandidateCorrectProse` (`op: correct-prose`) replaces exactly one issued shared span in an existing artifact body without any typed-row change, under the contract in [Shared-narrative correction](#shared-narrative-correction). An addition for a row type whose `plan_tool/roadmap_artifacts.py:stage_row_operation_policy` permits prose requires a `{ row_id, fragment }` amendment beside that added row. The amendment uses the added row's identity, has a nonblank fragment that names that identity as a whole token, and remains within `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES`. `plan_tool/roadmap_candidate.py:CandidateReplaceRow` and `plan_tool/roadmap_candidate.py:CandidateRemoveRow` carry no prose authority of their own.

One admitted feedback item may authorize multiple additions and their separate row-owned amendments; candidate batches do not adopt the stage-revision one-material-operation rule. `plan_tool/roadmap_candidate.py:parse_candidate_delta` admits this closed record, and `plan_tool/roadmap_candidate.py:materialize_candidate` applies corrections first and then its shared append behavior after authorized typed additions: each add-row fragment appends to the corrected predecessor narrative without replacing existing prose, creating body regions, or generating text, while a `correct-prose` operation replaces only its issued span via `plan_tool/roadmap_revision_patch.py:splice_exact_spans`. `check_inventory_has_prose` remains the gate that requires the added row to be named; the candidate path neither weakens nor bypasses it.

Structural disclosure reads row-linked amendment facts from stored normalized operations, including the artifact key, row id, and fragment. For each `correct-prose` operation it also shows the exact before text (the capsule's stored span text) and after text, projected by `plan_tool/roadmap_candidate.py:candidate_prose_correction_diffs` and printed by `plan_tool/cli/roadmap_cmd.py:_print_prose_correction_diffs`. The structural stack digest binds those stored facts with the other stack content, so approval covers the disclosed amendment or correction without changing approval, seal, promotion, or accepted-head rules. Replay of a stored batch re-derives the same operations through `plan_tool/roadmap_candidate_run.py:_require_reproducible_batch_operations`. Structured version comparison keeps showing the raw patch.

### Shared-narrative correction

Purpose: let admitted candidate feedback replace one stale narrative block that names several rows, without any typed-row change. Authority comes only from a span the tool issued for that feedback; a correction replaces one issued block's bytes and nothing outside it. The contract below is shared by issuance, application, and replay.

**Shared span and owning set**

| Term | Rule |
| --- | --- |
| Shared span | One non-blank, blank-line-delimited block of the predecessor body, using the same block definition as `plan_tool/roadmap_revision.py:_prose_blocks`. |
| Owning set | The full set of **live** rows whose ids appear in the block as whole tokens, using the `plan_tool/roadmap_artifacts.py:contains_whole_row_id` token rule. Live means present in the predecessor artifact's design rows. The owning set is defined here once; every rule below refers to it. |
| Single-row span | A span whose owning set has one row. It is the span `plan_tool/roadmap_revision.py:project_row_owned_prose_spans` issues today, loads and behaves unchanged, and is a valid correction target. A block naming one live row plus a removed-row reference is the common stale-paragraph case after a removal and is not excluded. |
| Removed-row reference | An id in the block that is not a live row. It does not join the owning set and is not required of it. |

- A span is issued only when **every live row in its owning set is visible in the candidate context**. Otherwise no span is issued for that block, because the interaction refusal below could not be checked; a partial span is never issued. A shared block larger than the replacement byte ceiling is not issued either, because a replacement could not re-express it; a selector context also repeats the span once per owner, and a batch context issues it once.
- The span id binds the whole owning set and the block text. The context representation is a code decision outside this contract; the binding must cover both.
- Spans carry one `row_id` today (`plan_tool/roadmap_revision.py:StageProseSpan`). The owning-set binding widens that; it never selects a block by marker or crosses block boundaries.

**Authority binding**

- A correction is authorized only by an issued span. A removed-row reference never grants authority, and an omitted correction is never read as a deletion.
- Each correction binds to the predecessor version, the artifact key, the span's exact source text and its digest, the admitted feedback, and the owning-set row ids. A removed-row reference is not part of the binding.

**Replacement and removal**

- A replacement is nonempty trimmed text, as in the stage revision path. Application gives it the span's own trailing newlines, so the blank line that separates the block from the next one is never consumed.
- Removal is never an empty replacement. The candidate correction offers no delete operation; the stage revision path's own delete amendment for a removed row is unchanged.
- Candidate batches keep their existing stance: one admitted feedback item may carry a correction beside its other operations.

**Refusals.** Any refusal publishes no candidate.

| Value | Meaning |
| --- | --- |
| `unknown` | The span id names no issued span. |
| `ambiguous` | The span id cannot select exactly one issued span. |
| `stale` | The span's bound predecessor version, text, or digest no longer matches the source. |
| `duplicate` | Two corrections target the same span. |
| `overlapping` | Two corrections cover intersecting byte ranges. |
| `oversized` | A replacement exceeds the byte ceiling below. |
| `unauthorized` | The span was not issued for the admitted feedback, or the correction relies on authority from a removed-row reference. |
| `owning-set-interaction` | The same candidate adds, edits, or removes a row in the span's owning set. Named separately from the values above so an operator can tell it apart. |
| `gate-failure` | The final candidate body fails an existing artifact gate. It surfaces through the existing gate-failed refusal, not as a separate reason. |

**Interaction with typed-row operations**

- A correction is refused (`owning-set-interaction`) when the same candidate adds, edits, or removes any row in its owning set.
- The owning set is computed from the predecessor's live rows only, and issuance, application, and replay all use that one computation. A row the same candidate adds is never in the owning set, so a correction may name it; an add of an id already in the owning set is refused.
- Operations on rows outside the owning set may share the candidate.

**Application order.** One order, at issuance, application, and replay:

1. Splice every correction into the predecessor body at its issued span.
2. Append add-row fragments after the corrected body.

Body text outside the issued spans, and the frontmatter delimiters, stay unchanged.

**The one body state the gates see.** The existing artifact gates, `check_inventory_has_prose` included, run against the **final candidate body**: corrections applied and the same candidate's add-row appends included. That one state is used at issuance, application, and replay, so a stored candidate replays to the accept or refuse result it had when published. A corrected body that fails the gates publishes no candidate; for example, a correction that drops a live row's only description. `check_inventory_has_prose` does not check that prose references resolve to known rows, and this contract adds no such check. A retained removed-row reference gets no special handling: the correction neither must remove it nor is exempt, and the existing gates decide. No gate is weakened and no candidate-only exception is added.

**Byte ceiling.** Each correction's replacement text is at most 4 KiB, measured in UTF-8 bytes, the same value as `plan_tool/project_config.py:HARD_MAX_PROSE_AMENDMENT_BYTES`. The ceiling is candidate-local, defined directly for candidates, and adds no project-config knob.

**Routes**

| Carries the correction | Does not carry it |
| --- | --- |
| The batch candidate route (`plan_tool/prompts/roadmap-candidate-delta.md`). | The selector-era candidate prompt. |
| The edit route, which stores a replacement candidate and requires a fresh approval. | The local stage-revision selector, which stays narrow. |

The selector-era prompt is the only fence on that route: materialization is shared and does not refuse a hand-built correction, whose authority stays the issued span and every existing gate.

**Delivery route.** Choose the route by why the correction is missing:

| The correction is missing because | Route |
| --- | --- |
| The candidate omitted or misstated it, and the same candidate could carry it | Edit: `plan_tool/roadmap_candidate_review.py:_edit_structural_candidate` stores a replacement that keeps the `correct-prose` operation, and the changed stack digest means approval of the old text cannot confirm the new text. |
| The same candidate adds, replaces, or removes a row in the span's owning set (`owning-set-interaction`) | Stack a follow-up: submit new feedback for the stale narrative and run `--propose-candidate` again. The new batch takes the active candidate as its source, so the changed rows are already in its predecessor, a row that candidate removed is a removed-row reference outside the owning set, and the follow-up carries only the correction. One stack decision covers both candidates. An edit or a re-run of the same batch cannot carry this correction, because each reproposes against the same source as the refused combination. |

**Deliberately not defined.** Arbitrary body replacement, marker-based editing, spans that cross blocks, automatic scope changes, and contradiction detection between narrative and rows are outside this contract. A definition that needs authority beyond the named block is a stop condition to raise, not a case to extend here.

<!-- immutable-candidate-version-authority:start -->
`plan_tool/roadmap_versions.py:AcceptedRoadmapHead` and `plan_tool/roadmap_versions.py:load_accepted_version` are the sole canonical-content selector. `plan_tool/roadmap_feedback_ledger.py` owns mutable reviewer input; `plan_tool/roadmap_candidate_context.py:build_candidate_context` constructs an exact root/source batch; `plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal` stores inert candidate evidence; `plan_tool/roadmap_candidate_review.py:seal_review` records ordinary review and `CandidateReviewSeal` records an exact review or `structural-approval` binding; and `plan_tool/roadmap_version_promotion.py:promote_review_seal` is the promotion boundary and accepted-head writer. Promotion rechecks the accepted root and active candidate freshness plus stored candidate, decision, and gate bindings before journaled publication. Candidate, review, and promotion records cannot substitute later ledger bytes, items, targets, responses, or context. Promotion re-derives the unpromoted stack from stored candidate records; when any hop above the recorded root stores a structural route, it requires the `structural-approval` seal and its enrolled publication applies the stored seed-state invalidation without rewriting seed bodies. Every later feedback proposal uses the promoted accepted version as its predecessor. `plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement` is the other accepted-head writer for its separate settlement route.
<!-- immutable-candidate-version-authority:end -->

Invalid output, failed gates, interruption, rejection, edit, and stale bindings preserve canonical artifacts, seeds, and `AcceptedRoadmapHead`; immutable history and selected-ledger lifecycle records remain only where their contracts provide them. Reopening and decision settlement keep their own selector-shaped inputs. They are separate operations, not alternatives for ordinary ledger feedback approval.

## Narrative review evidence

Purpose: show a candidate reviewer when live prose still names a design row the
candidate removed, computed from that candidate. This contract is evidence
only. The correction is the prose-correction operation of IPPT-18
([`docs/implementation-plans/2-candidate-prose-correction.md`](docs/implementation-plans/2-candidate-prose-correction.md));
the model-judged narrative review is BACKLOG #435; the response-basis check is
BACKLOG #437. The IPPT-18 correction operation ships as
`plan_tool/roadmap_candidate.py:CandidateCorrectProse`. The check is
`plan_tool/roadmap_gates.py:check_removed_ids_in_live_prose`, and the evidence
is computed by
`plan_tool/roadmap_candidate_narrative.py:compute_candidate_narrative_evidence`
and its stored-candidate adapter
`plan_tool/roadmap_candidate_narrative.py:candidate_narrative_evidence_from_bytes`.
The check is not a stage gate: it is absent from
`plan_tool/roadmap_gates.py:run_domain_gates` and its three sibling gate
tuples, and a stage run never evaluates it.

### Defect classes

The set is closed; a fourth class needs a change to this document.

| Class | Definition | Producer | Consumers | Blocks approval? | Exit |
| --- | --- | --- | --- | --- | --- |
| `removed-id-in-live-prose` | A removed id appears as a whole token in live prose. | The narrative check in `plan_tool/roadmap_gates.py`. | `plan_tool/roadmap_candidate_narrative.py`, `plan_tool/roadmap_candidate_review.py`, and the `roadmap` CLI display. | Yes. | The IPPT-18 correction operation, or the historical marker. |
| `removed-id-ambiguous-reference` | A removed id is also the id of a row present in the candidate, so the token may name the live row. | Same. | Same. | No. It is an evidence item shown to the reviewer, never a refusal. | None required; the reviewer reads it. |
| `unclosed-fence-unread` | A code fence opens and never closes, and the unread text after it names a removed id. The scanner runs an unclosed fence to end of text, so the check cannot read it. | Same. | Same. | No. It is an evidence item, so `none` is never printed for text the check did not read. | Close the fence. |

- **Whole token.** Ids match by the rule of
  [The prose body](#the-prose-body): bounded by anything outside `[0-9A-Za-z_-]`.
- **Live prose** is the artifact body only. Frontmatter rows, including
  decision `alternatives`, are not scanned.
- **A fenced code block is not live prose.** Fences follow the rules of
  `plan_tool/scope_fence.py:_fenced_code_spans`, the scanner the other
  `roadmap_gates.py` checks use (CommonMark: length-matching, tilde-aware,
  CRLF-safe; an opener indented four or more spaces is not a fence; a backtick
  line whose info string holds a backtick is an inline code span; an unclosed
  fence runs to end of text). This document defines no second fence rule.

### Historical marker

Prose that records history or a rejected alternative is set off structurally by
a pair of HTML-comment lines, each alone on its own line. The spelling is the
contract:

```text
<!-- roadmap:history:start -->
<!-- roadmap:history:end -->
```

- Prose from a start line to the next end line is historical context. A removed
  id there is not reported.
- A marker line inside a fenced span is quoted text, not a marker.
- An unclosed start excludes nothing: the check reports as if no marker were
  present. It fails safe, because the check blocks.
- A start inside an open region does not extend or reopen it.
- The marker is a line that must stand alone. Words such as "previously" or
  "rejected" in prose never set anything off.
- The marker is prose, so it reaches a candidate by the routes any prose change
  takes: the IPPT-18 replacement text, or the reviewer's edit decision.

### Source of the removed ids

1. The set is the `removed_id` of every record in the candidate artifact's own
   `removals`: the records carried from the predecessor plus any the candidate
   adds.
2. A carried record the reviewer pruned from the candidate is not in the set.
   Row ids come back into live use that way ([The removal record](#the-removal-record)).
3. A feedback-free candidate has no reviewer edit and no review rows:
   `plan_tool/roadmap_candidate.py:_assemble_candidate_artifacts` renders it
   with `removals` cleared, so its set is the predecessor's carried removals.
   The adapter reads the predecessor's records in that case.
4. **Known limits.** The set holds recorded removals only. A row the candidate
   itself drops with `remove-row` writes no record, so prose naming it is not
   checked. A feedback-free tip is checked against its immediate predecessor's
   records, so a removal recorded at an accepted root and cleared by an earlier
   feedback-free hop is not checked at the tip. BACKLOG #438 owns widening the
   source; until then the evidence covers removals carried by the feedback
   routes.

### What blocks, and the exit

`removed-id-in-live-prose` blocks approval. The refusal names the class, the
artifact, the id, and both exits:

- the IPPT-18 correction operation rewrites the span, when the block also names a live row (a block that names only removed rows is not issued as a span);
- the historical marker sets the span off.

Those are the only listed exits. Pruning a carried removal record also clears
the defect, but it is a deliberate reviewer bypass that lets the row back in: no
refusal text offers it as an exit. `removed-id-ambiguous-reference` never
blocks.

### Computed, never stored

1. Evidence is derived from the candidate's artifact text and its removals each
   time a surface needs it.
2. It is never stored, stamped with a digest or identity, cached in a sidecar,
   or regenerated by a model.
3. A candidate created before this contract is checked the same way, because
   nothing was ever stored for it.
4. Showing the evidence, sealing, and approving all re-derive it, so display and
   refusal use the same computation.

### Deliberately not defined

- **No judgment of pending versus settled, or current versus historical.** The
  property is unobservable and a keyword proxy measures vocabulary; BACKLOG #435
  owns it.
- **No keyword matching as the deciding rule.** The structural marker is the only
  historical signal.
- **No stored or stamped evidence record and no reviewer dispositions.** Both
  are BACKLOG #435.
- **No quality, length, or agreement check between prose artifacts.**
- **No change to the stage gate tuples, feedback eligibility, or authority
  limits.**

Alternatives rejected: a keyword list for historical prose (vocabulary, not
structure); storing evidence on the candidate (stale-evidence risk and a new
schema); blocking the ambiguous reference (it may name a live row, so blocking
would force a false correction).

## Read-only roadmap comparison

`plan-tool roadmap <slug> --compare` binds two complete roadmap snapshots for
review. Its base is the accepted immutable version by default and its target is
the active candidate by default; with no active candidate the route refuses and
asks for `--comparison-target`. Use `--comparison-base VERSION_ID`
and `--comparison-target VERSION_ID` to select stored immutable versions
explicitly. The route refuses when the default base has no accepted head, a
selected version is unavailable or invalid, or either resolved four-artifact
bundle cannot be read and parsed.

`--comparison-output cards` is the default terminal concept-card view;
`--comparison-output json` is deterministic machine-readable output; and
`--comparison-output patch` prints Git's complete unified patch. All forms
identify the bound snapshots and explain the same evidence. Git's complete
`--no-index` patch across exactly the four inventory artifact pairs remains the
source of record: cards and JSON never filter, rewrite, partition mixed bytes
by nearby concepts, or substitute for it. Bytes without a typed concept remain
identified as raw-only evidence.

When the target is a stored candidate whose direct predecessor is the selected
base, cards and JSON also report that candidate's ordered row-linked prose
amendments (`artifact_key`, `row_id`, `fragment`); cards quote each fragment as
a JSON string, JSON carries it exactly. Outcomes: `bound` (an empty collection
means the candidate's stored operations admitted none), `no-operation-evidence`
(a directly bound candidate stored no operation evidence, so its amendments are
unknown rather than empty), `not-applicable` (the target is not a stored
candidate or the base is not a stored version), and `not-directly-bound` (the
base is not the candidate's direct predecessor, so no binding is inferred from
changed bytes). Malformed or unbindable candidate evidence refuses the
comparison. Patch output remains the raw Git patch and carries no annotations.

Stable ids establish concept identity. A changed id is one removal and one
addition, never a label- or prose-based match. Comparing identical snapshots
and differing snapshots both succeeds; Git status `0` records identical
evidence and status `1` records differing evidence. Any other Git result, or a
launch or decoding failure, refuses rather than presenting partial evidence.

Comparison is exclusive and read-only: it accepts no companion roadmap option,
writes no roadmap artifact, metadata, lifecycle record, seed, receipt, run log,
or Git state, and does not accept, promote, settle, repair, or otherwise
change either snapshot. It is distinct from `--view`, which inspects one
snapshot, and from every separate lifecycle action an operator may choose after
reviewing the result.

## Immutable candidate-version authority

<!-- immutable-candidate-version-authority:start -->
`plan_tool/roadmap_versions.py:AcceptedRoadmapHead`
is the sole selector of canonical content. Its
`plan_tool/roadmap_versions.py:load_accepted_version()` result names one
complete immutable version: the stored brief and all four stored stage
artifacts. A stored candidate, review seal, model reply, and version-directory
order cannot select canonical content on their own. Two guarded writers change the accepted head, each only after its own
verification: `plan_tool/roadmap_version_promotion.py:promote_review_seal()`
changes it after verifying the exact sealed replacement and its current
accepted predecessor, and
`plan_tool/roadmap_decision_settlement_enrolled.py:run_enrolled_decision_settlement()`
changes it after rechecking the current accepted predecessor and storing its
one new immutable settled version. No other writer moves the selector.

A first stage run publishes one complete bundle as the immutable root version.
`plan_tool/roadmap_candidate_run.py:run_initial_candidate_proposal()`
then admits one fixed feedback selector against that root or its accepted
successor and stores an immutable inert candidate. The admission
persists the lineage's `plan_tool/roadmap_candidate_context.py:build_candidate_context()`
capsule, whose `CANDIDATE_CONTEXT_MAX_BYTES` ceiling is currently 384 KiB.
A capsule issued under an earlier ceiling (64 KiB or 192 KiB) keeps that
ceiling and stays readable: a stored selector capsule is also re-enterable,
because it is reproduced at its recorded ceiling, never the current one, and a
stored batch capsule is verified by its digest and receipts and never
re-rendered. Each new
context, including a new batch hop on a stored candidate, uses the current
ceiling. That module owns the
ceiling: callers cannot override it, silently truncate it, summarize it, or
widen the lineage beyond its one recorded
`plan_tool/roadmap_candidate_context.py:expand_candidate_context()` use. The one
caller-supplied ceiling is
`plan_tool/roadmap_candidate_context.py:rebuild_candidate_context_at_recorded_ceiling()`'s:
it accepts only a value the module has issued and exists to reproduce a stored
selector capsule at the ceiling that capsule recorded.
Replaying the same proposal re-enters the stored lineage; a different feedback
selector refuses before a model call, both before and after promotion.

`plan_tool/roadmap_candidate.py:materialize_candidate()` returns exactly one
`CandidateMaterializationResult` outcome in this order: a hard `refusal`, then
a `review_required` candidate, then a gate-clean `candidate`. A hard refusal
publishes no candidate. Review-required classification occurs only after
ordinary capsule authority, rendering, declared-relation, and complete-roadmap
checks pass; it records the deterministic `CandidateReviewRequirement` beside
an immutable inert candidate. The gate-clean candidate applies only when no
review requirement remains. Both valid candidate outcomes enter the established
candidate-review lifecycle, while a hard refusal cannot enter it.

`plan_tool/roadmap_candidate_review.py:generate_candidate_question()` binds a
question inventory to the admitted initial candidate. The review result renders
the stored deterministic review requirement beside its one opaque-question
response; the selected feedback remains the user request, and that opaque
answer is neither approval nor semantic validation. Its
`plan_tool/roadmap_candidate_review.py:answer_candidate_question()` path
records one exact stored answer and requests a replacement from the same
predecessor. The replacement prompt carries the stored question-and-answer
pair, not answer text alone. It stores a distinct immutable replacement
candidate, its binding, and an immutable review seal;
`plan_tool/roadmap_candidate_review.py:seal_review()` and
`plan_tool/roadmap_version_promotion.py:promote_review_seal()` require those
exact identities. Exact proposal and answer re-entry never creates a branch or
automatically retries a model-facing phase: exact command replay returns the
bound record or terminates with its recorded result. Model output remains inert
until exact review-seal promotion. Promotion is terminal consumption of the
exact review seal and changes only the accepted head.

For every review-required-lineage replacement, including a gate-clean result,
`plan_tool/roadmap_candidate_review.py:request_replacement()` recomputes
candidate-impact atoms and requires their multiplicity-preserving containment
by the initial disclosure. Repeated declared-relation occurrences remain
source-ordered occurrence facts: containment is not set membership,
impact-identity equality, or record-identity equality. A review-required
replacement reuses its initially admitted capsule and receipt; it cannot use
the gate-clean lineage's context-expansion route. When its predecessor is no
longer the accepted head, the review-required lineage refuses before it writes
a replacement or a seal.

`plan_tool/roadmap_view.py:load_roadmap()` is the completed downstream-reader
proof. It reads the accepted complete version, and a folder with no accepted
head refuses. A reader never repairs version state, and promotion never
rewrites a stored version. The remaining direct readers stay deferred in the
closed `BACKLOG.md` #328 record; they are not candidate-version writers.
<!-- immutable-candidate-version-authority:end -->

## Closed vocabularies

Ten closed vocabularies are restated here for readability. Artifact-shape
vocabularies are **owned as constants** in `plan_tool/roadmap_artifacts.py`;
the hosting value mapping and store category/sharing vocabularies are
gate-owned in `plan_tool/roadmap_gates.py`.

**Field type** — `FieldType`:

| Value | Holds |
|---|---|
| `text` | Free or bounded text. |
| `number` | A quantity, whole or fractional. |
| `boolean` | A yes/no. |
| `timestamp` | A point in time. |
| `enum` | One of a closed set — the members are a plan's decision. |
| `reference` | Another entity, named by the field's `entity_id`. |

**Logical, never physical**: a roadmap is written before a technology is
chosen, so `text` is the answer and `varchar(255)` is not. There is
deliberately no `collection` member — a to-many needs an element type to mean
anything, which would make `entity_id` optional on two members instead of
implied by exactly one, and cardinality is a plan's decision. Express a to-many
as a `reference` from the other side, or as a business rule.

**Decision status** — `DecisionStatus`:

| Value | Meaning |
|---|---|
| `settled` | This is the decision of record. A stage or an operator may set it. |
| `pending` | A load-bearing tradeoff a stage guessed at, awaiting an operator. |

Two members, deliberately. Status does not record authorship: a first run may
write a `settled` decision, and an operator settles a `pending` decision with
`plan-tool roadmap <slug> --settle-decision <artifact>:<decision-id>
--settlement-evidence <artifact>:<feedback-id> --confirm-decision-settlement`
(on a roadmap with a feedback ledger, `<feedback-id>` names an open ledger item
still eligible for the accepted version) — never by hand, since a stored
version is immutable. `check_settled_decisions` protects every predecessor
decision marked `settled` wherever a real predecessor is built; candidate
promotion's shared gate evaluator always builds `predecessor=None`, so the
check is a structural no-op there — see
`BUG_BACKLOG.md`, "An enrolled roadmap's candidate promotion never re-checks a
settled decision against its predecessor," a tracked, still-open gap this
capability documents rather than closes. The checker has no author signal to
distinguish authorship either way. That still makes accepting a `pending`
decision a queue an operator works down to zero rather than a tally that only
rises.

Un-settling a decision — setting it back to `pending` — has no confirmed
route yet, and a stored version is not hand-editable. Editing the status is
still the
*only* thing a working un-settle would need to do — lift the block the
decision placed on a revision without asking for anything else — once a
confirmed route exists. See [The feedback lifecycle](#the-feedback-lifecycle)
— "Un-settling a decision makes a change *possible*; a `feedback` row is
what *requests* it."

**Constraint disposition** — `ConstraintDisposition` (on `02-constraints.md`
disposition rows only — the YAML key `disposition` on a plan row uses a
different enum):

| Value | Meaning |
|---|---|
| `prioritized` | The roadmap spends to hold this attribute. |
| `traded-away` | The roadmap knowingly spends this attribute for something else. |
| `not-load-bearing` | The project does not rank on this attribute at all. |

`not-load-bearing` is the honest answer for an attribute a project does not
trade on, and it is what keeps a *total* disposition gate satisfiable without
filler.

**Plan disposition** — `PlanDisposition` (on `04-roadmap.md` plan rows only):

| Value | Meaning |
|---|---|
| `keep` | One component maps to this plan as-is. |
| `merge` | Several components share one plan. |
| `split` | One component spans several plans. |
| `cross-cutting` | Work not owned by a single component slice; may omit `component_ids`. The reviewer-facing delivery shape is cross-cutting. |

The YAML key `disposition` appears in both artifacts with **different closed
vocabularies** — constraint disposition ranks quality attributes; plan
disposition records how components map to plans.

**Quality attributes** — `QUALITY_ATTRIBUTES`, in display order:

`performance`, `scalability`, `security`, `availability`, `maintainability`,
`fault-tolerance`, `reliability`

A flat **operational** list, not a conformance taxonomy: each name is a concern
an operator ranks on its own, so `reliability: not-load-bearing` beside
`availability: prioritized` is coherent under this reading. The parser coerces
nothing against this tuple — membership belongs to `check_attribute_totality`,
which reports an unknown attribute as a violation naming the offending row
instead of dying at parse time.

**Hosting facets and values** — `HOSTING_FACETS` and
`HOSTING_FACET_VALUES`:

| Facet | Complete values | Meaning |
|---|---|---|
| `compute` | `per-request`, `managed-containers`, `long-lived`, `mixed` | `mixed` uses more than one of the other compute modes across deployable units. It names neither those units nor their stores. |
| `model` | `self-hosted`, `silo`, `pool`, `bridge` | `self-hosted` means each tenant or group operates its own application deployment. One operator runs dedicated deployments for `silo`, a shared multi-tenant deployment for `pool`, or both for `bridge`. |
| `topology` | `single-unit`, `multi-unit` | `multi-unit` means the application has more than one deployable unit. |

Every constraints artifact carries exactly one row for each facet. The parser
accepts an unknown facet or value so the gates can return a targeted violation;
an accepted artifact has no undecided member. `compute: mixed` and
`model: bridge` require `topology: multi-unit`. This application-level rule
does not identify individual units or judge runtime/store compatibility.

**Stack concerns** — `STACK_CONCERNS`:

| Value | Meaning |
|---|---|
| `platform` | The deployment platform the application runs on. |
| `store-engine` | The engine behind the durable stores. |
| `language-runtime` | The implementation language and its runtime. |

Three members, and every artifact that carries the `stack` collection names each
exactly once. The parser accepts an unknown concern so `check_stack_totality`
can report it. A concern not yet decided is recorded as `open: true`; there is
no undecided member to add. The vocabulary names concerns, not products: a
`choice` is free text and no vendor vocabulary exists.

**Store categories and sharing models** — `STORE_CATEGORIES` and
`STORE_SHARING_MODELS` on `03-components.md` store rows:

| Field | Complete values | Meaning |
|---|---|---|
| `category` | `in-process`, `relational`, `document`, `key-value`, `object` | `in-process` is volatile storage owned by one component for its process lifetime; the others are coarse durable-store categories. |
| `sharing` | `silo`, `pool`, `bridge` | `silo` dedicates a data resource per tenant; `pool` shares a resource while logically partitioning tenant data; `bridge` combines dedicated and pooled placement for one store role. |

Every component names at least one defined store, and every definition is used.
A component with no durable store names a distinct `in-process` definition;
only that category has one component owner. Durable stores may serve several
components. Store sharing describes data partitioning, not who operates the
application, so `self-hosted` is not a store-sharing value. The parser accepts
unknown values so the components gates can report them, and neither vocabulary
has an undecided member. Store gates never compare these values with hosting,
component behavior, cost, latency, or prose.

**Feedback state** — `FeedbackState`:

| Value | Meaning |
|---|---|
| `open` | The reviewer's request is active guidance, and the next revision of this artifact owes it an answer. |
| `awaiting-review` | A revision offered a `proposed_response`; the reviewer has not yet judged it. |
| `deferred` | The reviewer parked the request. It stays in the file and stops being sent as active guidance. |

Three members, and no `closed`: a closed request is a deleted row, not a state
the artifact carries. `awaiting-review` says a response is *on offer*, never
that anyone accepted it. Moves out of it stay with the reviewer.

**Feedback target kind** — `FeedbackTargetKind`:

| Value | What the request bears on |
|---|---|
| `artifact` | The artifact as a whole. Carries no `row_id`, and must not. |
| `row` | One design row, named by the target's `row_id`. |

Two members, and the tag travels with its payload rather than being inferred
from whether `row_id` is present — see
[The review collections](#the-review-collections--feedback-and-removals).

## The prose body

Everything after the closing `---` fence is the body. It is preserved **byte
for byte** through a load-and-render cycle and is written for humans: what the
domain is, why the ranking ranks the way it does, what each decision costs.

**One stage gate reads it.** (The candidate-review check in [Narrative review evidence](#narrative-review-evidence) also reads the body; it is not a stage gate.) `check_inventory_has_prose` requires every prose-
inventory row id to appear somewhere in the body, matched as a **whole token**
— bounded on both sides by something outside an id's alphabet `[0-9A-Za-z_-]`,
so a body mentioning `rule-payment-covers-order` does not satisfy the entity id
`order`. Hosting and store ids are identity-only and do not enter this
inventory. An inventoried row the narrative never describes reads as covered
and is not.

That is the whole of it. The gate **never judges whether the prose is good**,
only whether the row was named at all. It is decidable on ids, which is what
keeps it clear of the prose-quality gates this contract has none of.

Candidate additions preserve the same gate. An eligible candidate `add-row`
operation carries its required row-owned fragment and append-only
materialization places that fragment after predecessor narrative, so the added
id remains subject to `check_inventory_has_prose` rather than receiving a
candidate-only exception. A correction of an existing shared block follows
[Shared-narrative correction](#shared-narrative-correction).

### Candidate row anchors

An added row (`add-row`) must be grounded in a **reached** predecessor row, or
the batch is refused as `unauthorized-addition`. A predecessor row is reached
when the feedback closure or the inventory expansion included it; a row
included only because it is a settled decision is not reached. The reached set
grows to include added rows by these rules, and only these:

| An added row is reached when | Example |
| --- | --- |
| it cites a reached predecessor row (an outgoing relation) | a new entity with a reference field to a reached entity |
| it cites a reached added row | a new rule over the new entity above |
| a reached predecessor row cites it (an incoming relation) | a reached entity replaced to reference a new value-only entity |
| it is a `stack` row, which declares no relation; it grounds only a decision anchored to it, the one relation that can end at a stack row | a new `stack-platform` row |

Every relation an added row owns must also end at a reached row. A group of
added rows that only cite each other is not reached, in any artifact; one member
grounded by a rule above grounds the rest of the group. An incoming relation
from another *added* row never grounds a row by itself (the owner must be
reached first through a rule above). Single-feedback candidates cannot cite an
added row at all, so only the outgoing-to-predecessor rule applies to them.

Collections that can declare no relation to ground an addition (hosting,
dispositions, system and component patterns, stores) stay non-addable. A new
component that needs component-local storage can cite only an existing durable
store. The refusal names the artifact and row id of the first unreached addition
in operation order.

## Roadmap terminal-disposition matrix

This command contract defines the ordinary exception exits for the primary
`plan-tool roadmap <slug>` stage run and its named prompt-rendering routes. It
is separate from the artifact schema: it tells an operator how the command
ends, not what an artifact contains. `plan_tool/roadmap.py:run_roadmap` and
`plan_tool/cli/roadmap_cmd.py:cmd_roadmap` are the roadmap boundaries;
`plan_tool/cli/app.py:main` remains the application crash boundary. As with
every other reference in this document, code is authoritative if this matrix
and the implementation disagree.

The rows are chosen by **origin before exception type**. In particular, a
`RoadmapWriterGuardError` from `plan_tool/roadmap.py:run_roadmap`'s writer
preflight is a refusal, while the same type from stage publication is a failure
after work started. A common catch in `cmd_roadmap` must receive that preserved
origin rather than infer it from the exception text. The selected terminal
status is one best-effort roadmap-level emission attempt; a failed status sink
never replaces the original return or exception.

| Origin and precedence | Work may already have occurred? | Human error treatment | Roadmap terminal status fact | Run-log ending | CLI exit code | Crash-report behavior | Operator action |
|---|---|---|---|---|---|---|---|
| **Preflight refusal.** A known roadmap-domain refusal occurs before stage work: invalid invocation or source admission, an unavailable required input, or the writer guard rejected by `run_roadmap` before `_run_roadmap` begins. This row wins whenever no stage has started, including a prompt input failure reached during preflight. | No. Do not claim a started stage or published artifact. | Print one concise roadmap error naming the actionable input, guard, or template condition; retain useful path or decode context. | `preflight-refused` | `preflight-refused`, with `rc=2` and no stage phase. | `2` (invalid invocation or input-shaped refusal). | No crash report. This is a known, explainable roadmap condition. | Correct the invocation, source, guard state, or template input, then rerun. |
| **Expected failure after start.** A known roadmap-domain or environmental failure occurs after a stage has started, including a writer-guard failure during publication and an expected template missing/read/decode failure reached after work begins. This row wins over the exception's shared base type. | Yes. Earlier stages, phases, or side effects may exist; retain their facts. | Print the same concise roadmap error treatment as preflight for an equivalent template condition, while identifying that the run did not finish. | `error` | `error`, with `rc=1`, after any final stage fact. | `1` (the verb ran but did not finish). | No crash report. Known roadmap-domain and expected environmental failures stay out of the application crash path. | Inspect the retained stage and run-log facts, repair the named condition, then rerun. |
| **Unexpected exception.** A defect outside the documented roadmap-domain and expected environmental families escapes the roadmap command. This row applies only after the two known rows have been ruled out. | Possibly. Preserve any preceding stage facts; do not relabel the defect as a clean roadmap error. | Let `plan_tool/cli/app.py:main` print its unexpected-error diagnostic with the exception class and message. | `unexpected-error` | `error`, with `rc=1` when an owned roadmap lifecycle exists; otherwise no fabricated roadmap run record. | `1`. | Preserve `plan_tool/cli/app.py:main` crash persistence and traceback fallback. | Keep the crash report and preceding run facts, then report the defect; retry only after diagnosis. |

### Renderer routes and terminal ordering

The same template-input rule applies to
`plan_tool/roadmap.py:_render_stage_prompt`,
`plan_tool/roadmap.py:_render_stage_feedback_prompt`,
and `plan_tool/roadmap.py:_render_seed_materialize_prompt`: an equivalent
missing-template, unreadable-template, or decode failure receives the same
concise roadmap error treatment and known-error/no-crash classification. Its
origin still selects the row: a route reached before stage work uses
`preflight-refused`; one reached after stage work begins uses `error`. This
does not make raw filesystem failures, malformed placeholders, or programming
defects expected failures.

`plan_tool/roadmap.py:_stage_run_guard` owns the per-stage `stopped` fact when
an exception occurs inside a stage. `cmd_roadmap` owns exactly one final
roadmap-level terminal-status attempt for every matrix row. It emits that fact
after the last stage fact and does not replace the result, exception, retry,
publication or writer-lock path. Interrupts and process exits are
outside this matrix.

## The two enforcement channels

A broken artifact fails in one of two ways, and which one is a property of the
rule, not of how badly it is broken:

- **Shape** — the file is unreadable as an artifact at all. Parsing **raises**
  `RoadmapArtifactError`, which carries the offending `path` when the failure
  came through a `load_*` function.
- **Relations** — the file parses fine and says something incoherent. The gates
  **return** `Violation` records; nothing in `plan_tool/roadmap_gates.py`
  raises.

### Shape — raises at parse time

Enforced by `parse_domain_artifact`, `parse_constraints_artifact`,
`parse_components_artifact`, and `parse_plans_artifact` (and through them by
`load_domain_artifact` / `load_constraints_artifact` /
`load_components_artifact` / `load_plans_artifact`, which re-raise with the
path attached).

| Rule | What failing looks like |
|---|---|
| Line 1 is exactly `---`. | `RoadmapArtifactError`: must begin with a `---` frontmatter fence on line 1. |
| A later bare `---` closes the block. | `RoadmapArtifactError`: opens with `---` but has no closing fence. |
| The frontmatter is valid YAML. | `RoadmapArtifactError` naming the artifact and quoting the YAML error. |
| The frontmatter is a mapping (an empty block reads as `{}`). | `RoadmapArtifactError` naming the type it got instead. |
| A present row collection is a list, and each row in it is a mapping. | `RoadmapArtifactError` naming the collection key and the type it got — plus the row index when it is a row that is not a mapping. A collection that is not a list has no index to name. |
| Every row carries a non-empty string `id` — a `removals` record its `removed_id`, since it mints no id of its own. | `RoadmapArtifactError` naming the collection key, the row index, and the bad value. |
| Every required string field is present and a string (`name`, `statement`, `attribute`, `chosen_option`, `anchor`, a feedback row's `request`, a removal's `rationale`, and an alternative's `option` / `reason`). A Roadmap-derived decision also requires `rationale`; an inherited decision may omit it and carries optional string `source`. | `RoadmapArtifactError` naming the row id and the field. Blank is **not** a shape failure — emptiness of prose fields is a gate's judgment. The one exception is the row below: `proposed_response` on an `awaiting-review` row, whose state would otherwise claim a review that does not exist. |
| Every required id-list field is present and holds non-empty strings (`entity_ids`, `anchor_ids`, `pattern_ids`, a removal's `feedback_ids`). | `RoadmapArtifactError` naming the row id, the field, and the bad element. Present-and-empty parses. `constraint_ids` on a component row is optional and may be absent or empty. |
| A Roadmap-derived decision's `rejected_alternatives` is present and a list of mappings. An inherited decision may omit it; when present it has the same list shape. | `RoadmapArtifactError` naming the decision id and the alternative's index. Present-and-empty parses. |
| A decision's `status` is a `DecisionStatus` member. | `RoadmapArtifactError` naming the row id, the **offending value**, and the known members. |
| A disposition row's `disposition` is a `ConstraintDisposition` member. | `RoadmapArtifactError` naming the row id, the offending value, and the known members. |
| A plan row's `disposition` is a `PlanDisposition` member. | `RoadmapArtifactError` naming the row id, the offending value, and the known members. |
| Every plan row carries a non-empty `draft_seed_path` that passes `_validate_draft_seed_path` (relative, uses the draft prefix, no `..`). | `RoadmapArtifactError` naming the plan id and the bad path. |
| An ordering entry carries a non-empty string `plan_id`. | `RoadmapArtifactError` naming the ordering index and the bad value. |
| Draft-seed provenance carries required `roadmap_components` as a list of non-empty strings; optional `cross_cutting` is a boolean when present. | `RoadmapArtifactError` naming the missing key, bad type, or bad element — via `parse_draft_seed_provenance`. |
| A feedback row's `state` is a `FeedbackState` member. | `RoadmapArtifactError` naming the row id, the offending value, and the known members. |
| A feedback row's `target` is a mapping carrying a `kind` that is a `FeedbackTargetKind` member. | `RoadmapArtifactError` naming the row id, and the offending value plus the known members on an unknown `kind`. |
| A feedback target's tag agrees with its payload, both ways: `kind: row` carries a non-empty string `row_id`, and `kind: artifact` carries none. | `RoadmapArtifactError` naming the row id, the `kind`, and the bad `row_id`. A disagreeing tag has no defensible reading for a gate to report against; whether the id *resolves* is the gate's question. |
| A feedback row whose `state` is `awaiting-review` carries a non-blank `proposed_response`; any `proposed_response` present is a string. | `RoadmapArtifactError` naming the row id, the field, and the value. The deliberate exception to the blank-parses rule above — `awaiting-review` is *defined* by carrying a response. |
| A present feedback row `feedback_reopen` is exactly the closed redacted record: a receipt-safe two-string `selector`, fixed `reason`, 43-character URL-safe `nonce`, and real UTC RFC 3339 `recorded_at` with six fractional-second digits. | `RoadmapArtifactError` naming the feedback row and nested field. Missing, blank, wrong-typed, malformed, and extra keys fail; the record rejects response text, evidence, paths, digests, attestations, and any other free-form content. |
| The file is readable. | `RoadmapArtifactError` carrying the path and the OS error. |

### Relations — return violations

The removed-id check `check_removed_ids_in_live_prose` is not one of the
thirty below and runs in no stage tuple; see
[Narrative review evidence](#narrative-review-evidence).

Thirty relation gates across four stage-specific tuples. Each takes one
`ArtifactEnvelope` — the artifact under check, every upstream artifact already
parsed, optional lifted draft-seed text, and optionally the **predecessor**,
the prior version of the artifact under check as it sat on disk before this run
— and returns a list of `Violation(kind, artifact, row_id, message)`. `artifact` is a filename constant,
never a path; `row_id` is `None` only when the defect is an *absent* row, and
the message then names the identifier that should have been there. A row a
revision *dropped* and a removal's `removed_id` are real ids, so both populate
it. An `undefined-ordering-plan-reference` violation also carries
`referenced_id` (the cited plan id) and `reference_defect` — `absent` when no
plan row defines it, `cycle` when it is not earlier because it already reaches
the citing plan through `depends_on` / `assumption_targets`, and `not-earlier`
for any other defined reference that is not earlier in `ordering` — so a
candidate retry correction, which never echoes `message`, can name the real
defect (`plan_tool/roadmap_candidate.py:_gate_correction`).

Each gate judges **the artifact under check**, and reads the envelope's other
members only to *resolve* what it judges — never to widen it, because a
violation the retried stage cannot rewrite would spin the retry loop. There are
two exceptions, of different kinds:

- `check_duplicate_row_ids` judges **across** artifacts, because its rule is
  inherently cross-artifact: an id colliding between files is invisible from
  any one alone, and the retried stage can still rename its own side. When the
  envelope carries all four artifacts, plan, assumption, and decision rows on
  `04-roadmap.md` participate in the same uniqueness scope as domain,
  constraints, and components rows; constraints hosting ids and components
  store ids also participate as identity-only rows — **plan ids must not reuse
  component or other upstream design-row ids**.
- The three **revision** gates — `check_design_row_continuity`,
  `check_feedback_integrity`, and `check_settled_decisions` — judge the artifact
  under check **against its own prior version**, which upstream resolution has
  no analog for. The predecessor is never itself judged: it is the reviewer's
  document, and a rule finding fault with it would be a violation no revision
  could clear. Every rule derived from it is inert when the envelope carries no
  predecessor, so a first run and a below-stage re-gating pass behave exactly as
  they did without one.

`ArtifactEnvelope`'s fields are `domain` (always present), optional
`constraints`, optional `components`, optional `plans`, and optional
`predecessor`, plus optional admitted `carried_decisions`. The caller fills upstream
artifacts by stage; the last-filled slot among `plans` → `components` →
`constraints` → `domain` is the artifact under check (`artifact_under_check` /
`filename_under_check`). The predecessor's type matches the artifact under
check — a `DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`, or
`PlansArtifact` depending on which stage is running.

| Rule | Gate | Violation `kind` | The message names |
|---|---|---|---|
| The artifact declares the rows the other gates judge: a domain names at least one entity and at least one workflow; a constraints artifact names at least one constraint row — dispositions alone do not count; a components artifact names at least one component row; a plans artifact names at least one plan row. | `check_artifact_non_empty` | `empty-artifact` | The empty collection and the correction. No row id — there is no row. |
| Row ids are unique across every row kind in **every artifact the envelope carries**, not merely within one file. One violation per duplicated id, not per occurrence. Plan, assumption, and decision ids join the cross-artifact scope at stage 4; hosting and store ids reserve the namespace without becoming targetable rows, and stack ids join it as targetable rows. | `check_duplicate_row_ids` | `duplicate-row-id` | The id, how many rows declare it, and which file(s). A cross-file duplicate is reported against the artifact under check — the side the retried stage can rename. |
| Every constraints artifact holds exactly one row for each fixed hosting facet: `compute`, `model`, and `topology`. | `check_hosting_totality` | `missing-hosting-facet`, `redundant-hosting-facet`, `unknown-hosting-facet` | The missing facet, or the offending hosting row id and facet. |
| Each recognized hosting facet uses one of its own concrete values. Shape parses first, so an unknown value becomes retry text instead of a parser failure. | `check_hosting_value_membership` | `unknown-hosting-value` | The hosting row id, facet, invalid value, and allowed values. |
| `compute: mixed` and `model: bridge` require the recognized topology row to be `multi-unit`. An absent, duplicate, or unknown topology is left to the totality or membership gate. | `check_hosting_topology_coherence` | `hosting-topology-coherence` | The mixed or bridge hosting row id and the required topology. |
| A constraints artifact that carries the `stack` collection covers every stack concern (`platform`, `store-engine`, `language-runtime`) exactly once, names only those concerns, gives each row its own id, and gives each row exactly one of a `choice` or `open: true`. It binds on presence, never on absence: an artifact with no `stack` key is inert here. | `check_stack_totality` | `missing-stack-concern`, `unknown-stack-concern`, `duplicate-stack-id`, `duplicate-stack-concern`, `stack-row-state` | The missing concern (no row id), or the offending stack row id, its concern, and the correction. |
| Every entity holds at least one field; field names are unique **within** an entity (two entities may both hold an `id`); and `entity_id` is present on exactly the `reference` fields. Presence and shape only — whether the fields are the *right* ones is not checked. | `check_entity_fields` | `entity-without-fields`, `duplicate-field-name`, `field-reference-target` | The entity id, the offending field name, and the type vocabulary. |
| Every workflow **and every business rule** names entity ids the same artifact defines, and names at least one; every `reference` field's `entity_id` resolves too. Every bad reference is reported, not just a row's first. A reference field with *no* target is `check_entity_fields`' finding, not reported twice here. | `check_entity_references` | `no-entity-reference`, `undefined-entity-reference` | The row's kind and id, and the unresolved entity id. |
| Every quality attribute carries exactly one disposition; every `attribute` value — on a disposition row *or* a constraint row — is a known attribute; and no constraint serves an attribute the same artifact disposes `not-load-bearing`. | `check_attribute_totality` | `undisposed-attribute`, `redundant-disposition`, `unknown-disposed-attribute`, `unknown-constraint-attribute`, `constraint-on-not-load-bearing-attribute` | The **attribute name** when the row is missing (no row id to name); otherwise the offending row id, plus the full attribute list on an unknown value. |
| Every constraint anchors to at least one entity, business rule, or workflow id that `01-domain.md` defines. | `check_constraint_anchors` | `unanchored-constraint`, `unresolved-constraint-anchor` | The constraint id and the anchor id that did not resolve. |
| Every Roadmap-derived decision names at least one rejected alternative, each carrying a reason; carries a non-blank rationale; and anchors to an id that resolves — to a row in its own artifact, plus `01-domain.md`'s rows for a constraints decision. | `check_decision_records` | `no-rejected-alternative`, `unreasoned-alternative`, `blank-rationale`, `unresolved-decision-anchor` | The decision id, the rejected option that lacks a reason, and — on an unresolved anchor — which artifacts it was resolved against. |
| Every admitted inherited decision appears exactly once in its owner artifact and exactly matches its current source record: confirmed citation, chosen option, anchor, and any supplied rationale or rejected alternatives. Its status is `settled`, and its anchor is live and local to that owner artifact. | `check_inherited_decisions` | `missing-inherited-decision`, `duplicate-inherited-decision`, `altered-inherited-decision`, `inherited-decision-unconfirmed`, `inherited-decision-unknown-source`, `inherited-decision-ambiguous-source`, `inherited-decision-wrong-artifact`, `inherited-decision-nonlocal-anchor` | The inherited decision id, owner artifact, citation, and the field or placement to restore. |
| Every prose-inventory row id is named in the prose below the fence. Hosting and store rows are identity-only, and a reviewer's feedback is never asked for prose. | `check_inventory_has_prose` | `undescribed-row` | The row's kind and id. |
| Every removal record carries a non-blank rationale, cites at least one feedback id, and does not name a row the same artifact still declares. **With a predecessor:** every design row the predecessor declares is still here, or a removal record accounts for it and cites feedback that was `open` in the predecessor; a removal names a row the predecessor actually declared; and a row a `settled` decision anchors to may not go at all, with or without a record. | `check_design_row_continuity` | `blank-removal-rationale`, `uncited-removal`, `removal-names-a-present-row`, `dropped-design-row`, `removal-without-a-predecessor-row`, `unresolved-removal-citation` | The dropped row's kind and id, the removal's `removed_id`, the citation that did not resolve, and — on a pinned row — the settled decision to un-settle first. |
| A feedback id names one row within the artifact. **For a model revision with a predecessor:** every feedback row it carries is still here; a carried row's `target` and `request` are unchanged; the only state move is `open` → `awaiting-review`; a row carried in `awaiting-review` or `deferred` keeps its `proposed_response` verbatim; and a `row`-kind target the predecessor did not carry resolves against a row the predecessor declared or recorded the removal of. The dedicated confirmed reopen remains outside this model gate. | `check_feedback_integrity` | `duplicate-feedback-id`, `dropped-feedback`, `altered-feedback-source`, `disallowed-feedback-state`, `altered-carried-response`, `unresolved-feedback-target` | The feedback id and the field that changed — **never** the request or the response text, which stay the reviewer's and live only in the artifact. |
| **Predecessor only:** any decision the predecessor marks `settled` — whether a stage or an operator set it — keeps its id, `status`, `chosen_option`, and `anchor`. A cited removal does not excuse dropping it. **Candidate promotion never supplies a predecessor here, so this fence is a structural no-op there** — see `BUG_BACKLOG.md`, "An enrolled roadmap's candidate promotion never re-checks a settled decision against its predecessor." | `check_settled_decisions` | `dropped-settled-decision`, `altered-settled-decision` | The decision id, the fields that changed, and the un-settle the reviewer has to perform first. `rationale` and `rejected_alternatives` are deliberately not compared — the revision prompt asks for them, and equality on prose would fail on rewording alone. |
| Every component names at least one entity id `01-domain.md` defines. | `check_component_entity_references` | `no-entity-reference`, `undefined-entity-reference` | The component id and the unresolved entity id. |
| Every domain entity id appears on at least one component's `entity_ids`. | `check_entity_component_coverage` | `uncovered-entity` | The entity id that no component owns. No row id — the defect is an orphan entity. |
| Both pattern collections are non-empty, and every component cites at least one defined pattern id from their union. | `check_component_pattern_references` | `empty-pattern-collection`, `no-pattern-reference`, `undefined-pattern-reference` | The empty collection name, or the component id and the unresolved pattern id. `row_id=None` for an empty `system_patterns` or `component_patterns` collection. |
| Every non-empty `constraint_ids` entry names a constraint row `02-constraints.md` defines. An absent or empty list is not a discharge claim. | `check_component_constraint_references` | `undefined-constraint-reference` | The component id and the unresolved constraint id. |
| Every constraint on a `prioritized` attribute is cited by at least one component's `constraint_ids`. Constraints on `traded-away` attributes need no discharger. | `check_prioritized_constraint_discharge` | `undischarged-prioritized-constraint` | The constraint id that no component cites. |
| Every component names at least one defined store; it does not repeat a `store_ids` entry; and an `in-process` store has one component owner. | `check_store_definitions` | `no-store-reference`, `duplicate-store-reference`, `undefined-store-reference`, `shared-in-process-store` | The component id, unresolved or repeated store id, and the existing owner of an in-process store. |
| Every store definition appears in at least one component's `store_ids`. | `check_store_coverage` | `uncovered-store` | The unused store id. |
| Every store category and sharing value is a member of its closed vocabulary. Parsing remains permissive so an invalid value becomes retry text. | `check_store_value_membership` | `unknown-store-category`, `unknown-store-sharing` | The store id, invalid value, and allowed values. |
| Every plan states a non-blank operational `intent` and at least one explicit `non_goals` boundary. The intent says why the plan exists, and non-goals name adjacent, prerequisite, or deliberately deferred work; neither is a title or sizing-rationale restatement. Legacy rows remain readable by the parser but are flagged by the summary and fail when stage 4 generates a plans artifact. | `check_plan_review_context` | `blank-plan-intent`, `no-plan-non-goals` | The plan id and the missing review field. |
| Every non-`cross-cutting` plan names at least one component id from `03-components.md`; every listed id resolves there. | `check_plan_component_references` | `no-component-reference`, `undefined-component-reference` | The plan id and the unresolved component id. |
| Every component id in `03-components.md` appears on at least one plan row's `component_ids`. | `check_component_plan_coverage` | `uncovered-component` | The component id that no plan covers. `row_id=None` — the defect is an orphan component. |
| Plan-row `draft_seed_path` values resolve to distinct basenames. | `check_draft_seed_bundle_alignment` | `duplicate-draft-seed-basename` | The plan id, basename, and other plan rows that claim it. |
| Every plan id appears exactly once in `ordering`, matches the create slug rule, and every `depends_on` / `assumption_targets` entry names a plan id that appears earlier in the sequence. | `check_plan_ordering_totality` | `invalid-plan-id-slug`, `ordering-plan-id-duplicate`, `missing-ordering-plan-id`, `undefined-ordering-plan-reference` | The plan id, ordering entry, or slug defect. `row_id=None` for a missing ordering slot when the message names the plan id directly. |
| Every assumption cites at least one `consuming_plan_ids` entry, and every listed id names a plan row in the same artifact. | `check_assumption_plan_references` | `no-assumption-consumer`, `undefined-assumption-plan-reference` | The assumption id; for an unresolved consumer, that plan id too. |

**The table above lists all thirty relation gates; no stage runs all
thirty.**
`DOMAIN_GATES` holds ten — `check_artifact_non_empty`,
`check_duplicate_row_ids`, `check_entity_fields`, `check_entity_references`,
`check_decision_records`, `check_inherited_decisions`, `check_inventory_has_prose`,
`check_design_row_continuity`, `check_feedback_integrity`,
`check_settled_decisions` — and `CONSTRAINTS_GATES` holds fourteen, swapping
`check_entity_fields` and `check_entity_references` for the three hosting
gates, `check_stack_totality`, `check_attribute_totality`, and
`check_constraint_anchors`. `COMPONENTS_GATES`
holds sixteen — the shared gates minus the domain-only and constraints-only
checks, plus the eight components traceability gates above:
`check_component_entity_references`, `check_entity_component_coverage`,
`check_component_pattern_references`, `check_component_constraint_references`,
`check_prioritized_constraint_discharge`, `check_store_definitions`,
`check_store_coverage`, and `check_store_value_membership`. **`check_entity_fields`,
`check_entity_references`, `check_attribute_totality`, and
`check_constraint_anchors` are not in `COMPONENTS_GATES`** — upstream
artifacts were gated at their own stages. `PLANS_GATES` holds fourteen —
the shared gates minus the domain-only, constraints-only, and components-only
checks, plus the plan-review gate and five plan-relation gates above:
`check_plan_review_context`, `check_plan_component_references`,
`check_component_plan_coverage`, `check_draft_seed_bundle_alignment`,
`check_plan_ordering_totality`, and
`check_assumption_plan_references`.
**Domain-only, constraints-only, and components-only gates are not in
`PLANS_GATES`** — upstream artifacts were gated at their own stages. So a
domain artifact is judged by ten gates, not thirty, and a plans artifact
by fourteen.

What makes the four sets interchangeable is `ArtifactEnvelope`'s optional
upstream fields plus the uniform `Gate` signature — not the empty-list return
in artifact-specific gates when the artifact under check is the wrong type,
which is defensive only: each stage's tuple excludes gates that belong to other
stages, so nothing ever calls them against the wrong envelope in the shipped
table.

`check_component_constraint_references` and
`check_prioritized_constraint_discharge` have a second defensive return: when
`envelope.constraints` is absent, each returns no violations rather than
raising. The roadmap CLI re-gates stage 2 before it enters stage 3, so a normal
components stage always carries constraints; a direct caller may intentionally
use a partial envelope.

The four aggregates are `run_domain_gates`, `run_constraints_gates`,
`run_components_gates`, and `run_plans_gates`, over the tuples `DOMAIN_GATES`,
`CONSTRAINTS_GATES`, `COMPONENTS_GATES`, and `PLANS_GATES`. **Declared order
is the violation order** — gate by gate, then row order as parsed — so two runs
over one input produce the same list and a retried prompt is reproducible. All
four take the same `ArtifactEnvelope` and have the same signature on purpose: a
stage holds a gate set as data rather than branching on which artifact it
judges.

`ConstraintDisposition.TRADED_AWAY` is deliberately absent from the
`constraint-on-not-load-bearing-attribute` arm: spending an attribute knowingly
and bounding how much you spend are coherent together.

### What parse time deliberately lets through

Shape and relations are separate channels, so the parser accepts every one of
these without complaint. Do not go looking for them in
`plan_tool/roadmap_artifacts.py` — they are the gates':

- a workflow or business rule naming an entity id nothing defines, or naming none at all;
- two rows sharing an id, within a file or across the artifacts;
- a quality attribute with no disposition, or with two;
- an `attribute` value that is not one of the shipped quality attributes;
- a hosting block missing a fixed facet, repeating one, or carrying an unknown
  facet;
- a recognized hosting facet carrying a value outside its closed vocabulary;
- `compute: mixed` or `model: bridge` with a single-unit topology;
- a `stack` collection missing a concern, naming an unknown concern, repeating a
  concern or an id, or a row carrying both or neither of `choice` and `open`;
- a constraint anchored to nothing, or to an id `01-domain.md` never declares;
- a decision with no rejected alternatives, a blank rationale, or an anchor that resolves nowhere;
- an artifact with no rows at all;
- a row the prose below never mentions.

On a components artifact, shape and relations are likewise separate — the
parser accepts every one of these without complaint:

- a component naming an entity id nothing in `01-domain.md` defines, or naming none at all;
- a domain entity id appearing on no component's `entity_ids`;
- an empty `system_patterns` or `component_patterns` collection;
- a component citing no pattern ids, or citing pattern ids nothing defines;
- a component citing a constraint id nothing in `02-constraints.md` defines;
- a prioritized constraint cited by no component's `constraint_ids`;
- duplicate ids within or across the three artifacts.

On a plans artifact, shape and relations are likewise separate — the parser
accepts every one of these without complaint:

- a legacy row with no `intent` or `non_goals` (the stage-4 review-context gate
  rejects it when generated; read-only views call it out);
- a plan naming a component id nothing in `03-components.md` defines, or naming
  none when disposition is not `cross-cutting`;
- a component id appearing on no plan row's `component_ids`;
- an ordering sequence that duplicates, omits, or mis-orders plan ids;
- a plan id that fails the create slug rule;
- plan rows sharing a `draft_seed_path` basename;
- an assumption citing an undefined or absent consuming plan id;
- duplicate ids within or across the four artifacts.

Draft-seed provenance parse accepts without complaint:

- `roadmap_components` listing component ids the owning plan row does not
  carry — resolved by `validate_draft_seed_content` after materialization;
- a `cross_cutting` flag that disagrees with the plan row's disposition;
- seed body prose quality, length, or agreement with roadmap narrative.

The review collections add five more, and two of them are load-bearing rather
than merely tolerated:

- a feedback target naming a row id nothing declares;
- a removal citing a feedback id nothing declares, or citing none at all;
- two feedback rows sharing an id;
- a blank `request` or a blank removal `rationale`;
- an `open` or `deferred` row still carrying an old `proposed_response` — and
  **this is what makes the reopen path legal.** A reviewer reopening a row that
  carries a response keeps it readable beside their request while they decide,
  so a rule requiring the response to go with the state would turn the ordinary
  reopen into a shape error.

### What a violation is for

**Violations are retry text, not report lines.** Each message is written to be
quoted straight into the retried stage's prompt, so it names the offending
row's id, the file that row lives in, and the correction to make. Ids are the
only anchor: the artifact is rewritten on every retry, so a line number would
be stale before it was read.

Nothing carries a severity. Every violation blocks its stage, which is why
`Violation` has no advisory tier to sort by.

## What is deliberately not enforced

- **No gate judges whether live prose is current or historical.** Candidate
  review reports only a removed id found as a whole token outside the structural
  historical marker; the meaning-level question is listed under
  [Narrative review evidence](#narrative-review-evidence) as deliberately not
  defined.
- **No hosting gate judges a vendor, product, store, prose claim, deployment
  unit, or runtime/store compatibility.** Hosting records application-level
  categories only; `mixed` and `bridge` require `multi-unit` without modeling
  the units that make it so.
- **No gate or callout judges a stack choice.** Deliberately not defined: whether
  a `choice` is a good one; any comparison of a stack choice with a hosting or
  store `product`; a closed vendor or product vocabulary; stack concerns beyond
  the three in `STACK_CONCERNS`; a narrative-evidence defect class or an approval
  block on stack content; and a fifth roadmap artifact for the stack (decided
  2026-10-08: stack choices are constraints, and the four-member version layout
  runs through every roadmap surface).
- **No gate scores decomposition quality.** Components gates check id presence,
  entity coverage, pattern citation, and constraint discharge — not whether a
  decomposition is right-sized. Plans gates check component coverage, ordering
  totality, draft-seed alignment, and assumption references — not whether the
  disposition choice (`keep` / `merge` / `split` / `cross-cutting`) is the
  right one, whether plan count is sensible, or whether an authored plan
  `intent` / `non_goals` statement is substantively good. The review-context
  gate checks that those fields are present, not that the judgment is correct.
- **Discharge applies only to prioritized constraints.** A constraint on a
  `traded-away` attribute need not appear on any component's `constraint_ids`;
  only constraints whose disposition attribute is `prioritized` must be cited.
  `check_attribute_totality` rejects a `not-load-bearing` constraint before
  the components stage can evaluate discharge.
- **`cross-cutting` does not excuse uncovered components.** Gate
  `check_component_plan_coverage` still requires every component id from
  `03-components.md` to appear on at least one plan row — separate from gate
  `check_plan_component_references`, which allows a `cross-cutting` plan to
  omit `component_ids`.
- **No gate keyed on "this should have been one plan / two."** Disposition merit
  and plan-count caps are permanently out of scope.
- **A `pending` decision is never a violation.** `check_decision_records` reads
  a decision's `status` nowhere at all — that is how the rule is enforced
  rather than merely intended. `pending` is the review channel, and gating on
  it would fail the verb on exactly the artifacts it exists to produce.
- **Advisory residue never flips an exit code.** A completed run exits 0 with
  `pending` decisions, decisions the revision newly settled, feedback rows
  awaiting review, and any other residue on disk. The verb exits non-zero only
  when it fails to finish, in one of two ways: **1** when a stage spends its
  retry budget — on any of its four failure kinds: the backend failed, the
  reply was unparseable, the reply authored `feedback` or `removals` rows the
  reviewer never wrote, or the gates rejected it — and
  **2** for a pre-flight failure that stops the run before any stage is
  invoked — an unusable slug, an unreadable brief, a roadmap that
  already has an accepted head, or a folder holding pre-head state.
- **A revision settling a decision the predecessor had not is reported, never
  gated.** Two shapes count: a `decisions` row the predecessor never carried,
  and one it carried as `pending`. Both confer the fence that makes a decision
  revision-immutable, so the run summary names their ids and tells the operator
  to confirm each or set it to `pending`. Neither is a violation:
  `check_settled_decisions` examines only rows the predecessor *already* marks
  `settled`, and `check_decision_records` reads `status` nowhere at all.
  Status, not authorship, confers the fence: the first run can create it, and
  an operator can create it by settling a pending row. Whether a revision's
  own request decided the question is semantic — a gate would false-positive
  on exactly the case the revision prompt calls correct, and refusing inside
  the attempt loop spends one of a tight stage budget. The `pending` →
  `settled` shape is the quieter one: it also drops the row out of the
  pending-decision count, so the summary line is the only place it surfaces.
- **No gate enforces that a ranking ranks.** Disposing every quality attribute
  `prioritized` is gate-clean. The disposition vocabulary is the whole ranking
  mechanism and `check_attribute_totality` asks only for exactly one
  disposition each, so an all-prioritized artifact is operator-reviewable
  residue, visible in the committed diff like every other tradeoff.
- **No gate judges prose quality.** The only body check is whether a row id was
  named — see [The prose body](#the-prose-body).
- **A review row is never asked for prose.** `check_inventory_has_prose` and
  `check_duplicate_row_ids` walk the *design*-row inventory only, so a feedback
  row or a removal record needs no mention in the body below the fence. A
  reviewer's request is input, not narrative the artifact owes coverage of.
- **A feedback id may equal a design row id.** The two are separate namespaces,
  so `check_duplicate_row_ids` never sees a collision between them — and that
  separation is also why the review keys are their own constant and a first
  run's artifact is unchanged by any of this.
- **A `proposed_response` is stored and never judged.** No gate reads whether it
  answers the request, how long it is, or whether it repeats a prior one. The
  only comparison made on one is equality, and only on a carried
  `awaiting-review` or `deferred` row that must not change at all. Whether the
  response is any good is permanently the reviewer's call.
- **No count of rows awaiting review flips an exit code.** A completed run
  reports how many await the reviewer and still exits 0, exactly as it does for
  `pending` decisions. The count is a queue, not a verdict.
- **Nothing audits a written artifact after the run.** Correctness here is the
  in-run gates; a roadmap artifact is reviewed by reading the committed diff.
  When it is wrong, submit ledger feedback against the owning artifact and
  review the resulting candidate.

## Examples

Every example below parses, round-trips through render-and-re-parse unchanged,
and clears every gate in its stage's set — the last pair with the predecessor
that makes the three revision gates run. The constraints, components, and plans
examples run against the upstream examples above them in the same envelope.

### `01-domain.md`

```markdown
---
entities:
- id: order
  name: Order
  fields:
  - name: placed_at
    type: timestamp
  - name: total
    type: number
- id: payment
  name: Payment
  fields:
  - name: amount
    type: number
  - name: settles
    type: reference
    entity_id: order
business_rules:
- id: rule-payment-covers-order
  statement: A payment settles exactly one order and never exceeds its total.
  entity_ids:
  - order
  - payment
workflows:
- id: checkout
  name: Place an order and settle it
  entity_ids:
  - order
  - payment
decisions:
- id: decision-one-payment-per-order
  chosen_option: An order is settled by exactly one payment.
  rejected_alternatives:
  - option: Split settlement across several instruments.
    reason: No workflow in scope needs it, and it doubles the settlement states
      every downstream constraint has to reason about.
  rationale: Settlement stays a single transition, which is what lets a constraint
    anchor to the workflow rather than to a state machine.
  anchor: rule-payment-covers-order
  status: settled
---

# Domain

## Entities

An `order` is a customer's intent to buy, priced and frozen at the moment it is
placed. A `payment` is one movement of money against it.

## Business rules

`rule-payment-covers-order` binds the two: money moves once per order, and
never for more than the order is worth.

## Workflows

`checkout` is the one path through this domain — an order is placed, then
settled.

## Decisions

`decision-one-payment-per-order` records why settlement is single rather than
split.
```

### `02-constraints.md`

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
  choice: Google Cloud
- id: stack-store-engine
  concern: store-engine
  choice: PostgreSQL
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
- id: constraint-checkout-latency
  statement: Checkout settles within two seconds at the 95th percentile.
  attribute: performance
  anchor_ids:
  - checkout
- id: constraint-payment-audit-trail
  statement: Every payment state change is written to an append-only audit log
    before the response is returned.
  attribute: security
  anchor_ids:
  - payment
  - rule-payment-covers-order
decisions:
- id: decision-latency-over-headroom
  chosen_option: Hold the checkout latency budget and spend scale headroom for it.
  rejected_alternatives:
  - option: Queue settlement and confirm it asynchronously.
    reason: It holds throughput under load, but it moves settlement off the single
      transition the domain models, which every constraint here anchors to.
  rationale: The buyer waiting at checkout is the one who notices, and the traffic
    ceiling this trades away is far above what the workflow sees.
  anchor: constraint-checkout-latency
  status: pending
---

# Constraints

## Stack

`stack-platform` and `stack-store-engine` are chosen. `stack-language-runtime`
is `open`: the brief does not fix a language, so the roadmap records that rather
than inventing one.

## Dispositions

This is a small, latency-sensitive commerce path, so `qa-performance`,
`qa-security`, `qa-availability`, and `qa-maintainability` are prioritized.
`qa-scalability` and `qa-fault-tolerance` are traded away — the traffic ceiling
is low and a failed checkout is retried by the buyer. `qa-reliability` is not
load-bearing: nothing here runs unattended long enough for it to be ranked on
its own.

## Constraints

`constraint-checkout-latency` bounds the `checkout` workflow.
`constraint-payment-audit-trail` bounds `payment` and the rule that governs it.

## Decisions

`decision-latency-over-headroom` is the tradeoff behind the ranking above, and
it is `pending` — it is the one call here an operator should confirm.
```

### `03-components.md`

```markdown
---
system_patterns:
- id: pattern-audit-before-response
  name: Audit before response
  statement: Persist the state change before returning to the caller.
component_patterns:
- id: pattern-single-responsibility-unit
  name: Single-responsibility unit
  statement: One component owns one slice of the domain.
stores:
- id: store-checkout
  category: relational
  sharing: pool
  product: PostgreSQL
  description: The checkout team records orders in this managed database.
  research_disclosure: external
- id: store-payment
  category: document
  sharing: silo
components:
- id: component-checkout
  name: Checkout
  entity_ids:
  - order
  pattern_ids:
  - pattern-single-responsibility-unit
  - pattern-audit-before-response
  constraint_ids:
  - constraint-checkout-latency
  store_ids:
  - store-checkout
- id: component-payment
  name: Payment
  entity_ids:
  - payment
  pattern_ids:
  - pattern-single-responsibility-unit
  - pattern-audit-before-response
  constraint_ids:
  - constraint-payment-audit-trail
  store_ids:
  - store-payment
decisions:
- id: decision-checkout-payment-split
  chosen_option: Split checkout and payment into two components.
  rejected_alternatives:
  - option: One component owns the whole path.
    reason: The latency and audit constraints anchor to different entities.
  rationale: Each prioritized constraint discharges through the component that
    owns its anchored entity.
  anchor: component-checkout
  status: settled
---

# Components

## System patterns

`pattern-audit-before-response` is the cross-cutting rule behind the payment
audit constraint.

## Component patterns

`pattern-single-responsibility-unit` shapes every component row.

## Components

`component-checkout` owns `order`, uses `store-checkout`, and discharges
`constraint-checkout-latency`.
`component-payment` owns `payment`, uses `store-payment`, and discharges
`constraint-payment-audit-trail`.

## Decisions

`decision-checkout-payment-split` records why the path splits at checkout
versus payment.
```

### `04-roadmap.md`

```markdown
---
plans:
- id: checkout-core
  title: Checkout core
  intent: Let a shopper create a valid order before settlement begins.
  non_goals:
  - Payment authorization and settlement.
  disposition: keep
  component_ids:
  - component-checkout
  draft_seed_path: plan-seed-drafts/checkout-core.md
  sizing_rationale: One plan owns the checkout component slice.
- id: payment-core
  title: Payment core
  intent: Settle a previously created order with an auditable payment record.
  non_goals:
  - Creating or editing the checkout order.
  disposition: keep
  component_ids:
  - component-payment
  draft_seed_path: plan-seed-drafts/payment-core.md
  sizing_rationale: One plan owns the payment component slice.
ordering:
- plan_id: checkout-core
- plan_id: payment-core
  depends_on:
  - checkout-core
assumptions:
- id: assumption-checkout-before-payment
  statement: Payment settlement assumes checkout has created the order.
  consuming_plan_ids:
  - payment-core
decisions:
- id: decision-one-plan-per-component
  chosen_option: Map each component to its own plan with keep disposition.
  rejected_alternatives:
  - option: One plan owns checkout and payment together.
    reason: The components example already split them for constraint discharge.
  rationale: Each prioritized constraint discharges through the component that
    owns its anchored entity.
  anchor: component-checkout
  status: settled
---

# Plans

## Plans

`checkout-core` covers `component-checkout` to make a valid order; it leaves
payment settlement to `payment-core`. `payment-core` covers `component-payment`
to settle that order and deliberately does not redefine checkout creation.

## Ordering

`checkout-core` runs before `payment-core`, which depends on it.

## Assumptions

`assumption-checkout-before-payment` binds settlement to an existing order.

## Decisions

`decision-one-plan-per-component` records why the mapping is one plan per
component.
```

### A revision, with feedback

One pair of artifacts, one stage apart: what the reviewer handed the run, and
what the stage wrote back. The pair is the only way to show the review
collections doing anything — the three revision gates are inert without a
predecessor, so a feedback-bearing artifact judged alone proves nothing.

#### `01-domain.md`, before the run — the reviewer's edit

Two `open` rows the reviewer wrote by hand, one bearing on a single row and one
on the artifact as a whole.

```markdown
---
entities:
- id: order
  name: Order
  fields:
  - name: placed_at
    type: timestamp
  - name: total
    type: number
- id: payment
  name: Payment
  fields:
  - name: amount
    type: number
  - name: settles
    type: reference
    entity_id: order
- id: gift-card
  name: Gift card
  fields:
  - name: balance
    type: number
business_rules:
- id: rule-payment-covers-order
  statement: A payment settles exactly one order and never exceeds its total.
  entity_ids:
  - order
  - payment
workflows:
- id: checkout
  name: Place an order and settle it
  entity_ids:
  - order
  - payment
decisions:
- id: decision-one-payment-per-order
  chosen_option: An order is settled by exactly one payment.
  rejected_alternatives:
  - option: Split settlement across several instruments.
    reason: No workflow in scope needs it, and it doubles the settlement states
      every downstream constraint has to reason about.
  rationale: Settlement stays a single transition, which is what lets a constraint
    anchor to the workflow rather than to a state machine.
  anchor: rule-payment-covers-order
  status: settled
feedback:
- id: fb-gift-cards-are-out-of-scope
  target:
    kind: row
    row_id: gift-card
  request: Gift cards are a later product decision and nothing in scope touches
    them. Drop the entity.
  state: open
- id: fb-name-the-buyer
  target:
    kind: artifact
  request: Nothing here names the person placing the order, so every workflow
    reads as if orders appear on their own.
  state: open
---

# Domain

## Entities

An `order` is a customer's intent to buy, priced and frozen at the moment it is
placed. A `payment` is one movement of money against it. A `gift-card` holds a
balance a buyer can spend.

## Business rules

`rule-payment-covers-order` binds the two: money moves once per order, and
never for more than the order is worth.

## Workflows

`checkout` is the one path through this domain — an order is placed, then
settled.

## Decisions

`decision-one-payment-per-order` records why settlement is single rather than
split.
```

#### `01-domain.md`, the revision the stage wrote

Both requests carry a proposed response and neither is closed: the gates carry
every id, target, and request through untouched, and the state moves one step.
The dropped entity is accounted for by a `removals` record citing the row that
asked for it — a design row goes no other way.

```markdown
---
entities:
- id: order
  name: Order
  fields:
  - name: placed_at
    type: timestamp
  - name: total
    type: number
- id: payment
  name: Payment
  fields:
  - name: amount
    type: number
  - name: settles
    type: reference
    entity_id: order
- id: buyer
  name: Buyer
  fields:
  - name: email
    type: text
business_rules:
- id: rule-payment-covers-order
  statement: A payment settles exactly one order and never exceeds its total.
  entity_ids:
  - order
  - payment
workflows:
- id: checkout
  name: Place an order and settle it
  entity_ids:
  - buyer
  - order
  - payment
decisions:
- id: decision-one-payment-per-order
  chosen_option: An order is settled by exactly one payment.
  rejected_alternatives:
  - option: Split settlement across several instruments.
    reason: No workflow in scope needs it, and it doubles the settlement states
      every downstream constraint has to reason about.
  rationale: Settlement stays a single transition, which is what lets a constraint
    anchor to the workflow rather than to a state machine.
  anchor: rule-payment-covers-order
  status: settled
feedback:
- id: fb-gift-cards-are-out-of-scope
  target:
    kind: row
    row_id: gift-card
  request: Gift cards are a later product decision and nothing in scope touches
    them. Drop the entity.
  state: awaiting-review
  proposed_response: Dropped, and recorded in 'removals' citing this row. Nothing
    referenced it, so no rule or workflow changed.
- id: fb-name-the-buyer
  target:
    kind: artifact
  request: Nothing here names the person placing the order, so every workflow
    reads as if orders appear on their own.
  state: awaiting-review
  proposed_response: Added the 'buyer' entity and put it at the head of the
    'checkout' workflow. It holds an email only — what else identifies a buyer
    is a question I would rather you answered than guessed at.
removals:
- removed_id: gift-card
  rationale: Out of scope per the reviewer, and no rule, workflow, or field
    referenced it, so the drop reaches nothing else.
  feedback_ids:
  - fb-gift-cards-are-out-of-scope
---

# Domain

## Entities

A `buyer` is the person placing an order. An `order` is their intent to buy,
priced and frozen at the moment it is placed. A `payment` is one movement of
money against it. The `gift-card` entity is gone — see the removal record.

## Business rules

`rule-payment-covers-order` binds the two: money moves once per order, and
never for more than the order is worth.

## Workflows

`checkout` is the one path through this domain — a buyer places an order, then
settles it.

## Decisions

`decision-one-payment-per-order` records why settlement is single rather than
split. It is `settled`, so its status, chosen option, and anchor are pinned
until the reviewer sets it back to `pending`.
```

Both rows now read `awaiting-review`, which is where they stay until the
reviewer closes one by deleting it, reopens it by setting the state back to
`open`, or parks it at `deferred`. A normal stage response does not make those
ordinary lifecycle moves; it clears any prior current reopen record as it
writes the next `awaiting-review` response.

## See also

- `PLAN_FORMAT.md` — the plan file's frontmatter schema. A separate artifact
  type: nothing in plan discovery resolves a roadmap.
- `SEED_FORMAT.md` — authoring directives for the seeds that plans are created
  from.
- `DETAIL_FORMAT.md` — the per-step detail files under `plan-details/`.
- `docs/explanations/nondeterministic-plan-design.md` — the deterministic-core / judged-edge
  layering these gates are an instance of.
- `plan_tool/roadmap_view.py` — the read-only rendering half behind
  `roadmap <slug> --view {summary,walk,ledger,index,seeds}`; the compact `summary`
  view is the review starting point, while the other views provide full
  traceability drill-down. It introduces no schema or gate change of its own.
- `plan_tool/roadmap_html.py` — the sixth view, `--view html`: one
  self-contained, print-formatted page carrying every parsed row of all four
  artifacts, each resolvable forward reference linking to the row it names
  and each dangling or ambiguous one visibly marked, for reading a roadmap
  rather than auditing its state. Its domain section opens with an ER-style
  diagram of the `entities` rows and their `reference` fields, drawn by
  `plan_tool/roadmap_er.py`. The diagram states no cardinality and no
  optionality, because this schema records neither — a `reference` field is a
  target and nothing more, and where a to-many belongs is a plan's decision
  (see `FieldType`'s deliberate absence of a `collection` member). Business
  rules and workflows relate entities as well, but over any number of them at
  once, so they stay in the tables rather than becoming lines. A reference
  spanning multiple columns stays a single curve and can pass behind an
  intermediate box; the table remains the unoccluded record of every field.
  Written to
  `<roadmap-dir>/review.html` by default
  (`--output PATH` chooses the destination; `--output -` prints to stdout
  instead, the default every other view uses) — unlike every other view, it
  writes a file by default rather than printing, since the page is meant to
  be opened, and printed, in a browser. Like the views above it introduces
  no schema or gate change, and it reads the same parsed artifacts — a row
  this doc's schema admits renders, and one it does not never reaches the
  page.


### Published seed placement

New promotions use `docs/implementation-plans/plan-seeds/` and record
`publication_layout: nested` in their seed-state entry. The optional field
accepts `root` or `nested`; absence means the legacy root `plan-seeds/` path.
Acceptance, materialization and refresh preserve the recorded layout, including
when the promoted file is archived or temporarily absent. Existing seed files
are never moved, and unrelated files never establish publication ownership.
