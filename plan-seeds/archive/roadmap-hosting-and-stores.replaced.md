> **Replaced**: this file has been superseded by `docs/implementation-plans/archive/2-roadmap-hosting-and-stores.md`.
> Preserved here for history; do not edit.

# Hosting and per-component stores in the roadmap arc

Seed for BACKLOG **#243**. Extends the shipped roadmap stages 2 and 3; it is
**not** a new arc position and must not become one — see `## Architecture`.
The resulting plan updates `BACKLOG.md` (#243) in its final docs step.

## Outcome

`02-constraints.md` records how and where the application runs, and
`03-components.md` records which store each component persists to, so a plan
derived from the roadmap cites a store the roadmap defined instead of
inventing one.

## Overview

Two new frontmatter blocks and the gates that check them:

- `02-constraints.md` gains `hosting:` — the application-wide `compute` (what
  the code runs on), `model` (how tenants are separated), and `topology` (what
  deploys as one unit).
- `03-components.md` gains a top-level `stores:` block defining each store,
  and `store_ids` on every component row naming which it persists to.

Both are **required and concrete**: neither vocabulary carries an `undecided`
member. A stage that is inferring rather than reading the brief still commits
to a value and records a `pending` decision row against it, which is the
existing meaning of `pending` (`ROADMAP_FORMAT.md`: "a load-bearing tradeoff a
stage guessed at, awaiting an operator") and the existing queue an operator
works through the feedback channel.

## Problem statement

Nothing in the roadmap says what a component persists to or where the
application runs, so every derived plan re-invents both — inconsistently, and
sometimes wrongly. Three measurements from the TTRPG world-builder run
(`~/github/rupe120/ttrpg-demo`, 2026-08-07):

1. **An invented persistence claim, with nothing upstream to ground it.**
   `world-foundation`'s References cited `sqlite3` and PEP 249 as "useful when
   defining the single world-scoped repository/session boundary that mediates
   all reads and writes" — while all six of its code steps keep every store an
   in-process stand-in and none imports `sqlite3`. The detail-grounded
   completeness audit caught it as `persistence-references` (MEDIUM) and it
   was corrected by hand. The roadmap had no slot for the claim, so the plan
   asserted it in prose where no gate looks.
2. **A tenancy ambiguity that changes a function signature.**
   `constraint-a-world-fits-one-database` ("nothing is built to spread one
   world across more than one database") reads equally as *one physical
   database per world* (self-hosted per group) and *one shared database with
   `world_id` as the partition key* (multi-tenant service). The two produce
   materially different `world_session` implementations, and the constraint
   discharges into seven consuming plans. Nothing in the arc resolves it.
3. **A hosting assumption smuggled into a quality-attribute tradeoff.**
   `tradeoff-good-enough-uptime` accepts "an outage that could land on a game
   night" — phrasing that presumes a centrally-hosted service the product
   operates, rather than software each group runs. The hosting decision is
   already being made; it is being made in a field no gate reads.

4. **An in-process store that the compute model may forbid outright.** Every
   store in both TTRPG plans is an in-process stand-in, described throughout
   as a placeholder a later plan replaces. Whether that is a placeholder or an
   **impossibility** depends entirely on what the code runs on: on a
   long-lived server an in-process map is a working first cut, while on
   per-request serverless functions it is not a store at all — nothing
   survives the invocation, so a plan built on one produces software that
   cannot work. Seven plans are written against that assumption and the
   roadmap never states which world they are in.

The pattern is the one BACKLOG #222's kernel names for entities — "nothing
said what an entity *holds*, so every derived plan re-invented the shape" —
one altitude up. Measurement 4 is why `compute` is the load-bearing field of
the three: it decides whether in-process state is legal, whether a connection
pool is a resource or a leak, whether background work can exist in the same
process, and whether a request has a wall-clock ceiling. Those are not
deployment trivia a plan discovers at the end; they change what every step
builds.

## Architecture

**Shaped as fields on existing rows, not a fifth artifact.** #222's
near-identical kernel shipped as typed `fields` on `EntityRow` plus
`check_entity_fields`, deliberately not a new stage; this follows that
precedent. A dedicated stage was weighed and **rejected — do not re-open**,
for two reasons that are not about cost:

- **A store is a property of a component, not a peer of one.** `store_ids`
  sits beside `entity_ids`, `pattern_ids`, and `constraint_ids`, which are
  already per-component id lists on the same row. A separate artifact
  asserting "component X uses store Y" is a join table wearing an artifact's
  costume, and it puts the two halves one gate apart instead of one row.
- **Proportionality.** `hosting:` is two fields. A stage costs an artifact
  dataclass with parse/render, a path helper, an envelope slot, a gate set,
  and a ~250-line prompt — the `remedy-proportionality` shape CLAUDE.md names.

**State the cost accurately, because it cuts both ways.** *Inserting* a stage
mid-arc is genuinely expensive: it renames `03-components.md` and
`04-roadmap.md` on disk and rewrites roughly 150 doc lines, two golden files,
and ~20 prompt cross-references. *Appending* one as stage 5 is not — the table
in `roadmap.py` carries the comment "a further stage appends a row here — an
entry, never a branch", and the only hardcoded stage number in Python is
`cli/roadmap_cmd.py`'s `if 4 in stages`. So "a new stage is too expensive" is
true only of insertion and must not be cited as the reason here. The reason is
the two bullets above. Appending also fails on its own terms: it would place
hosting *after* components, so hosting could not inform whether components are
separable, which is one of the two questions it exists to answer.

**The gated vocabularies stay at category altitude.**
`ROADMAP_FORMAT.md`'s field-type rule — "a roadmap is written before a
technology is chosen, so `text` is the answer and `varchar(255)` is not" —
governs an entity field's *logical* type and is not weakened here. The line
this seed draws, and the plan must not move:

- **The roadmap's:** how tenants are separated, what deploys together, and
  which *category* of store a component persists to. Each changes what a plan
  builds — a graph store and a relational store yield different traversal
  work; a shared store forces a tenant key into every signature.
- **The plan's:** schema, physical and storage types, indexes, migrations,
  connection handling. Unchanged, and still out of the roadmap's reach.

A store row carries an optional free-text `product` (`Postgres 16`,
`DynamoDB`) for teams that have chosen one, and `hosting:` carries the same
slot for its own concretion (`AWS Lambda + API Gateway`, `ECS Fargate`, `EC2
behind an ALB`). Both are **recorded, never gated** — no gate reads either,
because a vendor name is not checkable before code and gating it would
manufacture exactly the ceremony below.

**AWS is the expected common case, and that is served by the free-text slot,
not by the vocabulary.** The gated members stay vendor-neutral and must fit a
traditional long-running server and a serverless deployment equally well —
that is the stated requirement, and it is also what keeps the vocabulary from
becoming an AWS service catalogue that rots on every re-brand. The
correspondence is intended to be obvious rather than encoded: a `compute`
member naming per-request functions is Lambda, one naming managed containers
is ECS/Fargate, one naming long-lived machines is EC2. **Do not add an
AWS-specific vocabulary, an AWS member, or an AWS branch to any gate.**
Framework- and vendor-specific vocabulary is what #208's unbuilt `--framework`
lens exists for (its named example is `aws-well-architected`); this effort
must not pre-empt it, depend on it, or grow a second one beside it.

**Why requiring a value does not repeat #222's ceremony failure.** #222
rejected requiring an ODCS data contract partly because "a gate over sections
most projects cannot fill honestly makes the model invent plausible SLAs to
clear it." Two things make this different rather than an exception. The
invention **already happens** — measurement 1 above is a model inventing a
persistence claim with no gate demanding one — so the choice is not between
invention and none, but between invention scattered across N plans' prose and
one reviewable row. And the `pending` status is the honest disposition the
ODCS proposal lacked: a guessed hosting model is committed *and* flagged, and
the reviewer's feedback channel is where it resolves. What is refused is a
value the reviewer can neither see nor answer.

**The vocabularies are closed and owned as constants** in
`plan_tool/roadmap_artifacts.py`, like the seven that ship. `hosting.compute`
names what the code runs on; `hosting.model` separates tenants;
`hosting.topology` names the deployable unit; a store's `sharing` says whether
tenants share it; a store's `kind` names the category. Members are the plan's
to finalize against the shipped constants' style, with two exceptions that are
decisions rather than derivations:

- **`sharing` must distinguish the two readings of measurement 2**, because
  collapsing them is the defect it exists to fix.
- **`compute` must separate per-request execution from long-lived execution**,
  because that is the line measurement 4 turns on — whether in-process state
  survives between requests. A vocabulary that lets serverless and a
  long-running server land on the same member has not done its one job.

## Scope of work

- The two frontmatter blocks, their row types, and their closed vocabularies
  in `plan_tool/roadmap_artifacts.py`; the parse paths for both artifacts.
- New gates in `plan_tool/roadmap_gates.py`, joining `CONSTRAINTS_GATES` and
  `COMPONENTS_GATES`.
- The stage-2 and stage-3 prompts, which must ask for the new blocks and say
  that an inferred value is committed with a `pending` decision row.
- `ROADMAP_FORMAT.md`: both schemas, the new vocabularies, the gate table, and
  the roadmap-versus-plan line from `## Architecture`.
- `tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`,
  `tests/test_roadmap_format.py`.

## The binary observable

Every component row names at least one `store_id` the same artifact defines;
every `hosting.compute`, `hosting.model`, `hosting.topology`, and store `kind`
/ `sharing` holds a member of its closed vocabulary; and any row whose paired
decision is `pending` has that decision present and anchored. Set membership,
set comparison, and presence — nothing else.

**Plus exactly one pair rule, and it is the only one.** A `compute` member
naming per-request execution and a store whose `kind` is in-process is a
contradiction, not a preference: nothing survives the invocation, so the store
does not exist. It is a lookup between two closed vocabularies with a fixed
answer, which is why it qualifies. **No second pair rule ships, and no
compatibility matrix ships** — the next such question ("is this store kind
sensible with that tenancy model?") is a judgment wearing a table's costume,
and it is refused below.

## Not allowed — enumerated, not implied

No gate, finding, or prompt directive in this effort may assert any of these.
A proposal for one is invalid, not deferrable:

- whether a store category **suits** a component's access patterns, data
  volume, or query shape;
- whether the hosting model, compute, or topology **can meet** any constraint,
  disposition, or latency or availability claim stated anywhere in the arc;
- **any compatibility rule beyond the single per-request/in-process pair named
  above.** No matrix, no second pair, no "these two are usually wrong
  together", and no severity or advisory tier for near-misses. If a second
  pair looks obligatory, that is the ceremony tell — stop and file it;
- **any AWS-specific or vendor-specific vocabulary member, gate, or branch.**
  Vendor concretion lives in the ungated free-text `product` slots, and
  framework vocabulary is #208's `--framework` lens, not this;
- **agreement between the new blocks and any prose** — the body, a
  constraint's `statement`, a decision's `rationale`, or a plan derived later.
  Prose-to-prose agreement is the banned shape (CLAUDE.md § "Validating a
  semantic property you cannot observe");
- cost, pricing, SLA, capacity, sizing, or scaling limits — #222's rejected
  ODCS territory, and none of it checkable before code;
- schema, physical or storage types, indexes, migrations, or connection
  handling — the plan's, per `## Architecture`;
- the optional `product` field, which is recorded and never read by a gate;
- any **quality judgment** on a `pending` value, including how long it has
  been pending or how many there are;
- any new exit-code flip. A stage that fails these gates retries with its
  violations quoted back, exactly as the shipped gates do; nothing else
  changes about the verb's exit status.

## Out of scope

- A new arc position or fifth artifact — rejected above, do not re-open.
- `01-domain.md` and `04-roadmap.md`, which gain no blocks and no gates.
- Threading either block into `create`, `detail`, `run`, or `jira` — a plan
  reading its roadmap's store rows is real and is the obvious follow-up, but
  it is a separate effort with its own fence. File it; do not absorb it.
- Reconciling the vocabularies against an existing on-disk roadmap, or
  migrating one. Artifacts predating this change fail the new gates on their
  next regeneration, which is the intended prompt to answer the questions.
- `--framework` lenses (#208 position 05) and the data-interface lens (#222).
  This effort must not become either, and must not depend on the unbuilt lens
  machinery.
- Infrastructure-as-code, environment counts, CI/CD, secrets, and regions.

## Allowed behavior changes

Stage 2 and stage 3 responses now carry two more blocks and fail their gates
without them. No change to stage ordering, filenames, numbering, the feedback
or removals channels, `--from-stage` re-entry, seed drafting, or `--apply`.

## Allowed reorganization

None.

## Risks

- **Ceremony on a brief that names no hosting.** The mitigation is the
  `pending` decision row and the reviewer queue, not a softer gate. Watch for
  the tell: if a real run produces a `pending` hosting decision the reviewer
  cannot answer from the brief either, the vocabulary is too fine-grained —
  narrow the members, do not add an `undecided` escape.
- **`sharing` and `hosting.model` restating each other.** They are related
  and must not be redundant; if the plan cannot state a case where they
  legitimately differ, they are one field, and it should say so rather than
  ship both.
- **Vocabulary churn.** Members are a closed constant, so a later addition is
  a breaking change for artifacts on disk. Prefer fewer, coarser members.

## Testing

Hermetic, fixture-driven, stubbed invokers — the arc's existing pattern.
What would prove the Outcome: a stage-3 response naming a store id no
`stores:` row defines is rejected and its violation quoted back; one naming a
defined store passes; a component with an empty `store_ids` is rejected; an
out-of-vocabulary `hosting.model` or store `kind` is rejected; a value with a
`pending` decision row passes while the same value with the decision absent is
rejected; the two readings of measurement 2 are expressible as different
`sharing` members; and the per-request/in-process pair is rejected while the
same store kind under long-lived compute passes. Assert by mutation, not by
reading (CLAUDE.md § Tests): break each new gate and watch its test go red.
Assert the deliberate carve-outs too — a `product` string a gate ignores,
prose contradicting a block without any finding, and a second
compute/store pair that is *not* rejected, which pins the single-pair fence
against a later matrix.

One worked fixture carries an AWS-shaped deployment and one a
traditional-server deployment, expressed only in the shared vocabulary plus
their own `product` strings, proving the neutral members cover both.

## Acceptance criteria

- A component row naming an undefined store id fails stage 3's gates, and the
  violation names the component and the unresolved id.
- A component row with a present-and-empty `store_ids` fails; the artifact
  parses first, so the gate reports it rather than the parser.
- `hosting.compute`, `hosting.model`, `hosting.topology`, store `kind`, and
  store `sharing` reject a value outside their constant, naming the offending
  value and its vocabulary.
- A per-request `compute` paired with an in-process store `kind` is rejected,
  naming both rows; the same store kind under a long-lived `compute` passes.
  This is the only pair rule, and a test asserts no other pair is rejected.
- A traditional long-running server deployment and a serverless deployment are
  both expressible without a vendor name, and land on **different** `compute`
  members — asserted directly, since a vocabulary that collapses them has
  failed its purpose.
- A committed-but-inferred value passes only with its `pending` decision row
  present and anchored to the row it bears on.
- Neither vocabulary has an `undecided`, `unknown`, `tbd`, or `n/a` member.
- `ROADMAP_FORMAT.md` documents both schemas, both vocabulary tables, and
  every new gate in the gate table, and `tests/test_roadmap_format.py` holds
  it to the shipped constants.
- The TTRPG run's tenancy ambiguity (measurement 2) is expressible: the two
  readings are different `sharing` members, demonstrated in a test.

## Deferred

- Plans consuming the store rows (`create`/`detail` grounding a persistence
  claim against them) — the obvious follow-up, deliberately not this effort.
- Migrating existing on-disk roadmaps to the new blocks.
- Any second store per component beyond what `store_ids` already expresses,
  such as a read replica or a cache tier, if a real run asks for one.
