> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-view.md`.
> Preserved here for history; do not edit.

# roadmap-view: resolve a roadmap's cross-row references into three deterministic views

Derived from **`BACKLOG.md` #240**, whose scope contract this seed inherits and
elaborates rather than replaces. The plan this seed produces **updates #240 in
`BACKLOG.md` when the work ships** — remove the entry only on full shipment,
mark it plan-authored while execution is still pending, and carry forward any
follow-up it deferred; that bookkeeping belongs in the plan's final docs/status
step and its acceptance criteria.

A standalone effort, **not** a position in the `roadmap-NN-*` (#208) arc.
Positions 01–04 of that arc have shipped, which is what makes a four-artifact
roadmap readable off disk at all; position 05 (framework lenses) stays
unauthored and this seed does not reach into it.

## Outcome

An operator reads an on-disk roadmap's cross-row structure — every id reference
resolved to the named row it points at — from one deterministic rendering,
without opening the four artifact files.

## Overview

`roadmap` authors, gates, and `--apply`s; nothing renders. This seed adds the
missing read half: a read-only leaf that joins rows the four loaders already
return, printing a **traceability walk**, a **decision ledger**, and a **reverse
index**. No Claude call, no mutation, no new gate, no new parsing.

The views are **joins, not copies**, and that is the load-bearing property. A
second prose artifact describing the frontmatter can drift from it and nothing
can check that it hasn't; a derived view has no drift failure mode because it is
not a copy — it *is* the frontmatter with ids resolved.

## Problem statement

**Nodes reach the prose; edges never do.** `check_inventory_has_prose` requires
every design-row id to be *named* in the body below the fence — decidable on
ids, and its docstring is explicit that it "never judges whether the prose is
*good*", so what it guarantees is **coverage, not quality**. **No gate asks for
a reference in prose at all.** Every cross-row reference therefore lives only as
a bare id in YAML — **seventeen fields** on the row dataclasses, spread across
four artifacts plus the draft seeds:

- domain — `FieldRow.entity_id` (a `reference` field's target: the
  entity→entity edge), `BusinessRuleRow.entity_ids`, `WorkflowRow.entity_ids`;
- constraints — `ConstraintRow.anchor_ids`;
- components — `ComponentRow.entity_ids` / `pattern_ids` / `constraint_ids`;
- plans — `PlanRow.component_ids`, `OrderingEntry.plan_id` / `depends_on` /
  `assumption_targets`, `AssumptionRow.consuming_plan_ids`;
- review and side output — `FeedbackTarget.row_id`, `RemovalRecord.removed_id` /
  `feedback_ids`, `DraftSeedProvenance.roadmap_components`;
- and `DecisionRow.anchor`, on all four artifacts.

A constraint row's `attribute` is deliberately **not** in that set: attribute
names are a closed constant, not rows, so an attribute reaches the anchor space
only through its disposition row's id. A reader gets well-covered nodes and
several hundred unreadable edges.

**Scale, measured on the demo roadmap 2026-08-06**
(`.tmp/roadmap-04-plan-derivation.plans/roadmaps/toollib/`): 1,964 lines across
four artifacts carrying **137 design rows** — 96 structural (11 entities, 13
business rules, 13 workflows, 7 dispositions, 17 constraints, 12 patterns, 9
components, 8 plans, 6 assumptions) and 41 decisions. The traceability chain the
format is built around — entity → constraint → component → plan — is the tool's
central claim at this altitude and is today readable only by hand-joining id
lists across four files. **The gap is in rendering, not authoring.**

## Architecture — settled decisions, do not re-open

**Three views, because there are at least four legitimate reading orders.**
*What is this* · *why does this plan exist* · *what breaks if I change this
entity* · *what is settled vs. still open*. Each view serves one; none tries to
serve all.

1. **Traceability walk** — per plan, in `ordering` sequence: the components it
   carries, the entities those own, the constraints they discharge, and the
   rules and workflows behind them, every id replaced by its `name` /
   `statement`. It prints each plan's `draft_seed_path` and that seed's
   `roadmap_components` provenance — the far end of the chain — and renders no
   seed *body*.
2. **Decision ledger** — every decision in one ordered list, grouped `settled` /
   `pending`, each with its anchor resolved to a named row plus its rejected
   alternatives and rationale. Highest value per line of code: 41 decisions
   scattered across four files with no rollup today.
3. **Reverse index** — for a given row id, every row that cites it. Answers "if
   this entity changes, what moves."

**Unclosed `feedback` rows join the ledger's pending section — all three of
`open` / `awaiting-review` / `deferred`, keyed on the lifecycle rather than on
the word *open*.** `FeedbackState`'s docstring is explicit that the reviewer and
never the tool moves a row out of `AWAITING_REVIEW` ("the state says a response
is on offer, not that anyone accepted it"), which makes it *more* pending on the
human than `open` is. The ledger's question is what is settled vs. still open,
and an unanswered reviewer request is exactly an open item. Feedback ids stay
outside the design-row namespace, exactly as `_rows_of` keeps them.

**A `removals` record renders inline beside the feedback that caused it**,
closing the loop, and nowhere else — never as its own section (§ Out of scope
carries the reason).

**A partial roadmap is the normal case, not the edge case.** `--from-stage`
re-entry, an interrupted run, and every mid-authoring moment leave only
`01-domain.md` (± `02-constraints.md`) on disk. Each view is a join across up to
four artifacts and **degrades to the stages that exist, naming the ones it did
not find** rather than reporting a truncated web as whole.

**A dangling id renders visibly (`⚠ undefined: …`), never crashes and never
silently drops the edge.** A hand-edited artifact read outside a stage run can
carry an id no gate ever saw; dropping it silently would hide exactly what the
gates exist to report. **The one id that is not dangling despite resolving to no
design row is a feedback `target` naming a removed row** — resolve feedback
targets against `design rows ∪ removals`, mirroring `check_feedback_integrity`'s
own set, whose comment names that union as "what lets feedback ask for the
removal of the row it names". A design-rows-only resolver prints `⚠ undefined:`
on a well-formed roadmap: a false positive in the review loop's *designed*
success path.

**Placement preserves the one-way chain.** A new read-only leaf
`plan_tool/roadmap_view.py` importing only `roadmap_artifacts` — a sibling of
`roadmap_gates.py`, keeping `roadmap_artifacts` → `roadmap_gates` → `roadmap` →
`cli/roadmap_cmd` strictly one-way, with the view hanging off the first link and
wired at the last.

**The one decision `create` must settle: the CLI shape — a flag on `roadmap` vs.
a sibling read verb. Exactly one lands, never both.** Two facts constrain it and
neither pre-decides it. A flag form joins `roadmap`'s existing mutually
exclusive mode group beside `--apply` and `--from-stage`, because it likewise
runs no stage and invokes no backend, and it must not require `--from-existing`.
A verb form obliges a `CAPABILITIES.md` row — `check_capabilities` raises
`orphan-subcommand` only for a *subcommand* with no owning capability, so a flag
does not; either way those findings are advisory and never gate an exit code.

**The arms differ only in the wiring site and one doc row.** The leaf, all three
renderers, the resolution rules, and the tests are identical under either shape,
so no step downstream of the wiring step is conditioned on the choice. This is
deliberately *not* the `premise-conditioned-design` shape (CLAUDE.md
§ "Audit the why, not the what"): the outcome changes where one call is made and
whether one catalog row is added, not what gets built.

## In scope

`plan_tool/roadmap_view.py` (new leaf), its wiring in
`plan_tool/cli/roadmap_cmd.py`, `tests/test_roadmap_view.py`, and the doc sweep
a fifth roadmap module obliges: the four-module chain line in CLAUDE.md
§ "Architecture", the matching text in `docs/ARCHITECTURE.md`,
`ROADMAP_FORMAT.md` § "See also", and a `docs/cli/` regeneration
(`python -m plan_tool.cli_reference --write`) — plus a `CAPABILITIES.md` row iff
the shape decision lands a verb.

No new parsing: `load_domain_artifact`, `load_constraints_artifact`,
`load_components_artifact`, and `load_plans_artifact` already return every row
the views need.

### Scope contract

- **Binary observable:** none required, and none is claimed. This proposes no
  check, gate, finding, or enforcement — it is a rendering, so SEED_FORMAT's
  observable rule does not bind. The `⚠ undefined:` marker is a **rendering
  annotation, not a finding**: it changes no exit code, enters no report, and
  reaches no convergence signal. That distinction is the line this work must not
  cross; the enumeration below is what holds it.
- **Allowed behavior changes:** exactly one new read-only surface — a flag on
  `roadmap` or a sibling read verb, whichever the shape decision settles; not
  both. No change to stage execution, `--apply`, `--from-stage`, the gates, or
  any artifact on disk.
- **Allowed reorganization:** none. `roadmap_view.py` is an addition, not a
  move; no existing roadmap code changes owners.
- **Verification:** §§ Testing and Acceptance criteria. Every assertion is over
  resolved ids and structural keys — none over rendered prose words.
- **Stop / defer:** § Deferred, and anything the iteration loop surfaces outside
  this fence goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan
  expansion. **A gate defect found while joining is a `BUG_BACKLOG.md` entry,
  not a fix inside this work** — the view reports what it finds and does not
  become a second enforcement channel.

### Not allowed — enumerated, because stating the principle does not hold it

Each is **invalid, not deferrable**:

- **any Claude call** anywhere in the read path — determinism is the whole
  point;
- **any narrative or story generation** (§ Out of scope carries the measured
  reason);
- any gate, finding, `Violation`, advisory, or exit-code flip: a completed
  render exits 0 whatever it found, per the exit-code convention;
- judging whether a body's prose describes its rows well, whether a decision's
  rationale is sound, or whether a plan's components suit it — every quality
  opinion about any artifact;
- any agreement check between two prose artifacts — body vs. frontmatter, seed
  vs. plan row, rationale vs. anchor;
- any shape, length, count, or ratio cap on any row, body, or rendered view;
- any frontmatter schema or `*_ROW_KEYS` change, and any mutation of any
  artifact, including reformatting or replacing the existing prose bodies.

## Out of scope

- **Mermaid or other graph output.** A separate entry: at 137 rows a
  whole-roadmap graph is a hairball, and per-plan subgraphs are a second design
  question.
- **A standalone removals or history section.** Records accumulate without bound
  across revisions, and a record preserves only `removed_id` plus a rationale,
  never the row's content — a dedicated section would be an ever-growing
  graveyard that cannot show what was lost. Removals are in scope *only* as the
  resolution half of the feedback lifecycle, inline beside the citing feedback
  row. **Excluding them outright was considered and rejected 2026-08-06 — do not
  re-cut it**, for the `check_feedback_integrity` false-positive reason in
  § Architecture.
- **Draft-seed bodies.** A seed is a `SEED_FORMAT.md` document with its own
  contract; the walk cites its path and provenance and stops.
- **Machine-readable output.** Text only, no `--json`, until a caller that needs
  it exists.
- **Reading plan files or the `.plan-tool` manifest.** Roadmap artifacts only.
- **Generating a narrative "story" of the roadmap. Do not re-open without new
  evidence.** It was the originating proposal (2026-08-06) and loses on two
  counts. (a) A story imposes one linear traversal on a graph with at least four
  legitimate reading orders, so it serves one reader and buries three. (b) It is
  a second prose copy of the frontmatter that nothing can check — precisely
  CLAUDE.md § "Validating a semantic property you cannot observe", whose named
  unobservable is "the doc is accurate". Roadmaps are **revisable** (feedback
  rows, removals, `--from-stage` re-entry), so a story goes stale on every
  revision, and a confident stale story about a twice-revised roadmap is worse
  than four dense files.

## Risks

Low overall: read-only and additive, no existing behavior moves. Two
correctness traps, both from reading artifacts no gate has just blessed, and one
process risk:

- **Reporting a partial roadmap as whole.** The mitigation is structural, not
  advisory: a view names the artifacts it did not find, so absence is stated
  rather than inferred from a short rendering.
- **The feedback-target false positive.** A naive design-rows-only resolver
  passes every other assertion in § Testing and fails only here, which is why it
  is pinned by its own test rather than left to review.
- **A missed doc-sweep site.** A fifth roadmap module invalidates a count and a
  chain that are restated in at least four places. Sweep by **vocabulary** ("four
  modules", "one-way", the chain arrow line) as well as by identifier, per
  CLAUDE.md § "Documentation is forward-looking"; the roadmap paragraph in
  CLAUDE.md has already carried stale counts once.

## Testing

`tests/test_roadmap_view.py` mirrors the module, built on parsed-artifact
fixtures. **Verify by mutation, never by reading** — break each join and watch it
go red — and **assert resolved ids and structural keys, not prose words**, since
a substring check breaks the next time a legitimate label uses the word.

**Assert the carve-outs, not only the rules.** Each is a deliberate exemption a
later widening would otherwise swallow while staying green:

- a dangling id renders visibly rather than crashing or dropping the edge;
- a feedback target resolvable **only** through a `removals` record renders as
  resolved, not dangling;
- a `cross-cutting` plan with no `component_ids` renders as such, not as a
  defect;
- a domain-only roadmap renders and names the three artifacts it did not find;
- no removal renders outside its citing feedback row;
- all three unclosed feedback states reach the pending section, and a closed one
  does not.

Manual check: run all three views against the toollib roadmap named in
§ Problem statement.

## Acceptance criteria

- Each of the seventeen reference fields in § Problem statement is resolved to
  its target row's `name` / `statement` in at least one view, or is stated in the
  module's own docs as deliberately unrendered with the reason.
- The traceability walk emits plans in `ordering` sequence and reaches
  `draft_seed_path` plus that seed's `roadmap_components` for every plan row.
- The decision ledger accounts for every `DecisionRow` on all four artifacts
  exactly once, grouped by `status`, with unclosed feedback rows in the pending
  group and each removal inline beside its citing feedback.
- The reverse index, given any design-row id, returns every citing row, and
  returns an empty result — stated as such — for an id nothing cites.
- A domain-only roadmap renders all three views and names the three artifacts it
  did not find.
- A well-formed roadmap whose feedback targets resolve only through removals
  renders with zero `⚠ undefined:` markers.
- No artifact on disk changes, no backend is invoked, and a completed render
  exits 0.
- The gates, stage table, `--apply`, and `--from-stage` behave identically
  before and after.
- The doc sweep lands at every site in § In scope, and `docs/cli/` regenerates
  clean.
- `BACKLOG.md` #240 is reconciled on shipment.

## Deferred

- **Mermaid / graph output** and per-plan subgraphs — their own entry and their
  own design question.
- **A decision-arc narrative on top of view 2.** The one place narrative
  genuinely beats a join: rejected alternatives and rationales are causal, and a
  table flattens what prose keeps as reasoning. If it is ever built it is
  regenerated disposably and never hand-edited. Out of scope here.
- **`--json` or any machine-readable form**, until a caller needs it.
- **The cheap cut, if this does not earn its slot:** the decision ledger alone is
  a single-view v1 and is `direct`-sized. Take it as a fallback, not as a first
  step that leaves the other two views half-specified.
