> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap View
intent: An operator reads an on-disk roadmap's cross-row structure — every id reference
  resolved to the named row it points at — from one deterministic rendering, without
  opening the four artifact files.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the roadmap_view resolver that turns a roadmap id into the row it names
  intent: Gives every later view one place that turns a bare cross-row id into the
    named row it points at — one display label per row kind, the feedback-target-through-removals
    union and the artifact-scope target that a design-rows-only resolver gets wrong,
    and the dangling and ambiguous ids that a hand edit produces — so no renderer
    invents its own rule, with membership taken from roadmap_gates.design_row_ids
    rather than re-derived.
  creates:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - plan_tool/roadmap_gates.py
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-view/01-roadmap-view-resolver-that-turns.md
  status: done
- id: 2
  title: Load a roadmap off disk into LoadedRoadmap, naming what it did not find
  intent: Gives the three views their only input — the artifacts that parsed, the
    absent and the unparseable named, whether the roadmap directory exists at all,
    the roadmap-wide id index, and the mode filter that decides whether the review
    channel is in scope — so an operator can render a partly-authored roadmap, the
    normal case after --from-stage re-entry or an interrupted run, and no renderer
    re-derives the mode or touches the disk.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/roadmap-view/02-load-roadmap-off-disk-loadedroadmap.md
  status: done
- id: 3
  title: Add the citation map and the reverse index view
  intent: Answers "if this row changes, what moves" for any design-row id — citers
    being design rows alone under current mode and additionally feedback targets and
    removal citations under review mode — and gives the traceability walk the entity-to-citing-rule
    lookups it needs instead of a second hand-rolled traversal.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-view/03-citation-map-reverse-index-view.md
  status: done
- id: 4
  title: Add the traceability walk view over plans, components, entities, patterns,
    and constraints
  intent: Lets a reader follow the entity to constraint to component to plan chain
    the roadmap format is built around, in ordering sequence and out to each plan's
    draft seed and its roadmap_components provenance — read through the existing parse_draft_seed_provenance,
    with the absent and unparseable seed named — and with plans and ordering reconciled
    visibly when a hand edit has left them disagreeing, without hand-joining id lists
    across four files.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  complexity: high
  change_type: feature
  depends_on:
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/roadmap-view/04-traceability-walk-view-over-plans.md
  status: done
- id: 5
  title: Add the decision ledger view in both modes
  intent: Rolls up every DecisionRow from all four artifacts into one settled-versus-pending
    list with anchors resolved — the view the mode changes most, adding unclosed feedback
    rows to the pending group under review mode, with any removal that feedback cited
    rendered beside it as a tombstone that names the id and the reason and cannot
    name the row's content — so what is still open is readable in one place and how
    it got there is one flag away.
  files:
  - plan_tool/roadmap_view.py
  - tests/test_roadmap_view.py
  allowed_mentions:
  - tests/test_roadmap.py
  - tests/test_roadmap_gates.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/roadmap-view/05-decision-ledger-view-both-modes.md
  status: done
- id: 6
  title: Add the --view read mode to the roadmap command and regenerate the CLI reference
  intent: Puts the three views in an operator's hands as a third read mode in roadmap's
    existing mutually exclusive group, with --mode selecting design state or the review
    channel, --id supplying the reverse index's row id, and its absence rendering
    the full citation map.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/cli/__init__.py
  - docs/cli/roadmap.md
  - docs/cli/README.md
  - tests/cli/test_roadmap_cmd.py
  - tests/cli/package_surface_help.golden.txt
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  - 4
  - 5
  detail: docs/implementation-plans/plan-details/roadmap-view/06-view-read-mode-roadmap-command.md
  status: done
- id: 7
  title: 'Update the roadmap module chain in the docs and reconcile BACKLOG #240'
  intent: Keeps the docs that a future session reads first honest about a fifth roadmap
    module — including CAPABILITIES.md's architecture-roadmap surfaces line, which
    enumerates the roadmap modules — and closes the backlog entry this work was derived
    from.
  files:
  - CLAUDE.md
  - docs/ARCHITECTURE.md
  - ROADMAP_FORMAT.md
  - CAPABILITIES.md
  - integrations/claude/SKILL.md
  - README.md
  - USE_CASES.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 6
  detail: docs/implementation-plans/plan-details/roadmap-view/07-update-roadmap-module-chain-docs.md
  status: done
---
# Roadmap View

## Overview

Add a read-only rendering half to the `roadmap` verb: a new read-only module `plan_tool/roadmap_view.py` that joins the rows the four existing artifact loaders already return and prints three deterministic views — a **traceability walk**, a **decision ledger**, and a **reverse index** — with every cross-row id reference resolved to the row it names, in either of two modes: **`current`** (the default — what the design *is*) or **`review`** (the review channel around it). No Claude call, no mutation, no new gate, and **no new parser** — every read goes through a parsing function that already ships. The views are **joins, not copies**: a derived view has no drift failure mode because it is not a copy — it *is* the frontmatter with ids resolved. A completed render exits 0 whatever it found, per the exit-code convention; the `⚠ undefined:` marker is a rendering annotation, not a finding.

Derived from **`BACKLOG.md` #240**, whose scope contract this work inherits and elaborates rather than replaces. The final docs/status step and the acceptance criteria update #240 when the work ships — remove the entry only on full shipment, mark it plan-authored while execution is still pending, and carry forward any follow-up it deferred. A standalone effort, **not** a position in the `roadmap-NN-*` (#208) arc; positions 01–04 of that arc have shipped, which is what makes a four-artifact roadmap readable off disk at all, and position 05 (framework lenses) stays unauthored and out of reach here.

Outcome: an operator reads an on-disk roadmap's cross-row structure — every id reference resolved to the named row it points at — from one deterministic rendering, without opening the four artifact files.

## Problem statement

**Nodes reach the prose; edges never do.** `check_inventory_has_prose` requires every design-row id to be *named* in the body below the fence — decidable on ids, and its docstring is explicit that it "never judges whether the prose is *good*", so what it guarantees is **coverage, not quality**. **No gate asks for a reference in prose at all.** Every cross-row reference therefore lives only as a bare id in YAML — **seventeen fields** on the row dataclasses, spread across four artifacts plus the draft seeds:

- domain — `FieldRow.entity_id` (a `reference` field's target: the entity→entity edge), `BusinessRuleRow.entity_ids`, `WorkflowRow.entity_ids`;
- constraints — `ConstraintRow.anchor_ids`;
- components — `ComponentRow.entity_ids` / `pattern_ids` / `constraint_ids`;
- plans — `PlanRow.component_ids`, `OrderingEntry.plan_id` / `depends_on` / `assumption_targets`, `AssumptionRow.consuming_plan_ids`;
- review and side output — `FeedbackTarget.row_id`, `RemovalRecord.removed_id` / `feedback_ids`, `DraftSeedProvenance.roadmap_components`;
- and `DecisionRow.anchor`, on all four artifacts.

A constraint row's `attribute` is deliberately **not** in that set: attribute names are a closed constant, not rows, so an attribute reaches the anchor space only through its disposition row's id. A reader gets well-covered nodes and several hundred unreadable edges.

**Scale, measured on the demo roadmap 2026-08-06** (`.tmp/roadmap-04-plan-derivation.plans/roadmaps/toollib/`): 1,964 lines across four artifacts carrying **137 design rows** — 96 structural (11 entities, 13 business rules, 13 workflows, 7 dispositions, 17 constraints, 12 patterns, 9 components, 8 plans, 6 assumptions) and 41 decisions. The traceability chain the format is built around — entity → constraint → component → plan — is the tool's central claim at this altitude and is today readable only by hand-joining id lists across four files. **The gap is in rendering, not authoring.**

## Architecture

Settled decisions — do not re-open.

**Two modes, and the line between them is the design record vs. the review channel around it — settled 2026-08-07, user-confirmed; do not re-open.** A roadmap file carries two different kinds of content and rendering them together is what makes a view hard to read. `--mode current` (the **default**) renders **what the design is**: every design row, and every decision — `settled` *and* `pending` — because a pending decision is a live open question *about the design*, not a record of an edit. `--mode review` adds the **review channel**: `feedback` rows in every lifecycle state — which is where the mode's substance lives, a feedback row carrying the reviewer's actual `request` and `proposed_response` — plus `removals` as tombstones beside the feedback that cited them.

This is CLAUDE.md § "Documentation is forward-looking" applied to a rendering rather than to prose: the present-tense record is the default, and the review scaffolding is one flag away rather than mixed into it. The mode's weight is deliberately on **feedback**, not on removals: a feedback row carries authored content and a target that usually resolves, while a removal carries only a tombstone (below).

**The mode is called `review`, not `history`, because the artifact holds no revision arc.** Every `feedback` row on disk is unresolved by construction — `FeedbackState` is `open` / `awaiting-review` / `deferred` with **no `closed` member**, and a reviewer closes a row by deleting it (`roadmap_cmd.py:_feedback_summary_lines`, "close one by deleting the row (git keeps the record)") — so the file carries a *live queue*, never a resolved conversation. Nothing in it records a diff, a timestamp, a revision count, or any prior value of an edited row; `--from-stage` re-entry rewrites in place, and git holds the actual history, which this work does not read. A mode named `history` would promise a reader an arc the format cannot supply. **BACKLOG #242 changes that** — retained `closed` feedback, a removal content snapshot, a removal→decision link — and **carries the rename to `--mode history`** as its own follow-up, at which point the name becomes true. Do not pre-adopt it here.

**The mode is a property of `LoadedRoadmap`, not of each renderer.** Step 2 builds it for a mode and exposes only the populations that mode permits; steps 3, 4, and 5 render whatever of their content the envelope carries. One place owns the filter — the same rule that puts the display label in the resolver rather than in three renderers. A renderer that re-derives the mode is the defect this prevents.

**Three views, because there are at least four legitimate reading orders.** *What is this* · *why does this plan exist* · *what breaks if I change this entity* · *what is settled vs. still open*. Each view serves one; none tries to serve all. The mode is orthogonal to the view: `--view` picks the reading order, `--mode` picks how much of the record is in scope.

1. **Traceability walk** — per plan, in `ordering` sequence, each level reached from the one above by a named edge: the **components** the plan carries (`PlanRow.component_ids`); for each component, the **entities** it owns (`ComponentRow.entity_ids`), the **patterns** it applies (`pattern_ids`), and the **constraints** it discharges (`constraint_ids`); and for each of *those entities*, the **business rules and workflows that govern it** — reached backwards through the citation map, since `BusinessRuleRow.entity_ids` and `WorkflowRow.entity_ids` point *at* entities and there is no forward edge. That reverse hop is why step 4 depends on step 3 rather than duplicating a traversal. Constraints are a leaf here: the walk does not continue from `ConstraintRow.anchor_ids`. That field resolves only against `01-domain.md`'s entities, business rules, and workflows — `check_constraint_anchors` builds its `anchorable` set from exactly those three, and `ROADMAP_FORMAT.md` states it as "Ids in `01-domain.md` that it constrains" — never against dispositions, which the ledger reaches separately through `DecisionRow.anchor`. Continuing from `anchor_ids` would therefore re-enter the same entities, business rules, and workflows the entity branch above already reaches, not a new part of the chain. Every id is replaced by its display label. All three of `ComponentRow`'s reference fields are carried, not two — dropping `pattern_ids` would leave 12 pattern rows of the demo roadmap unreachable from the chain while criterion 1 demands every reference field resolve somewhere. Each plan carries its `depends_on` and `assumption_targets` from its `ordering` entry — **both plan-id-valued and both leaves, resolved identically.** `assumption_targets` never names an `AssumptionRow`: `ROADMAP_FORMAT.md`'s own comment on the field is "Plan ids this entry's ordering-level assumptions bear on," and `check_plan_ordering_totality` validates every entry against the roadmap's plan ids, the same rule `depends_on` gets. Each plan also carries the assumptions that name it in *their own* `consuming_plan_ids` — reached through the citation map's reverse hop, the same pattern the walk already uses to find an entity's governing business rules and workflows, not a fourth bespoke mechanism. Each entity's `reference` fields carry their `FieldRow.entity_id` target. All four fields are named here rather than left to a reader who would otherwise need to already know an id to query them — which is what the Outcome's "without opening the four artifact files" requires. It prints each plan's `draft_seed_path` and that seed's `roadmap_components` provenance — the far end of the chain — and renders no seed *body*.
2. **Decision ledger** — every decision in one ordered list, grouped `settled` / `pending`, each with its anchor resolved to a named row plus its rejected alternatives and rationale. Highest value per line of code: 41 decisions scattered across four files with no rollup today. **This is the view the mode changes most:** in `review` mode it additionally carries unclosed `feedback` rows in the pending group — the reviewer's own `request` text, which is the substance — with any removal that feedback cited rendered beside it as a tombstone.
3. **Reverse index** — for a given row id, every row that cites it. Answers "if this entity changes, what moves." An id that no artifact declares is reported as undeclared rather than as an empty result: *nothing cites this* and *there is no such row* are different answers and must not render the same. In `review` mode the citers include feedback targets and removal citations; in `current` mode they are design rows only, so the same id can legitimately report different citers under the two modes — **each render names its mode** so the two are never mistaken for each other.

**Feedback ids are a subject only under `review` mode, and the index says which namespace it is answering in.** They are a separate namespace by design — `check_feedback_integrity`: "Feedback ids are their own namespace and deliberately stay out of `check_duplicate_row_ids`" — yet `RemovalRecord.feedback_ids` cites them, and that is one of the seventeen fields. So under `--mode review` the citation map's declared population is **design rows ∪ feedback rows**, and `--id` accepts either; under `--mode current` it is design rows alone and a feedback id is reported as *out of scope for this mode*, never as `⚠ undefined:` — the two answers are different and a reader must be able to tell "no such row" from "not in this mode".

**The traceability walk's *content* is mode-invariant, deliberately.** Its rows are design rows end to end — entity → constraint → component → plan — and none of that is review machinery, so `--view walk`'s body is byte-identical under both modes. **The mode header is not part of that claim**: every render names the mode it was produced under, so the two walk renders differ on the header line and nowhere below it. Stated rather than left to inference: a reader who passes `--mode review` and sees an unchanged body is looking at a deliberate property, not a bug, and a later change that makes the walk's rows mode-sensitive has to come here and say why. **The mode changes only the ledger and the reverse index.**

**One display label per row kind, fixed in the resolver rather than per renderer.** "Its `name` / `statement`" covers only some rows; five kinds carry neither field, so the resolver owns the whole mapping and no view invents its own: `EntityRow` / `WorkflowRow` / `ComponentRow` → `name`; `BusinessRuleRow` / `ConstraintRow` / `AssumptionRow` → `statement`; `PlanRow` → `title`; `AttributeDispositionRow` → `attribute` + `disposition`; `DecisionRow` → `chosen_option`; `FeedbackRow` → `request`; `RemovalRecord` → `removed_id` + `rationale`, which is a **tombstone label, not a resolved row** — it names the id that is gone and why, and cannot name what the row said.

**`PatternRow` names its scope, because `name` alone loses it.** `PatternRow`'s own docstring: "used for both system-level and component-level patterns; the collection key distinguishes scope" — the row carries no field saying which, only its home collection does. `ComponentRow.pattern_ids` resolves against the union of both (`check_*` builds `system_pattern_ids | component_pattern_ids`), so a bare `name` label loses exactly the distinction the reverse index's "if this entity changes, what moves" depends on: a **system** pattern is shared across every component that cites it — wide blast radius — while a **component** pattern is local to one. The resolver's label is therefore `system pattern: <name>` or `component pattern: <name>`, carrying the collection each `PatternRow` was read from rather than the row alone.

**The walk reconciles `ordering` against `plans` visibly, against all three anomalies `check_plan_ordering_totality` itself checks for — not just two of them.** That gate makes `ordering` and `plans` a bijection with no duplicate `plan_id`, but the premise of these views is reading an artifact no gate has just blessed. A plan row absent from `ordering` renders after the sequence, marked as un-ordered rather than dropped; an `ordering` entry naming no plan row is marked like any other dangling id; an `ordering` entry repeating a `plan_id` already rendered marks a duplicate rather than silently re-rendering the plan a second time. On a gate-clean artifact all three groups are empty and the walk is exactly the `ordering` sequence.

**`roadmap_components` comes from the draft seed, not from a loader.** It is read through the shipped `roadmap_artifacts.parse_draft_seed_provenance` against the file at each plan's `draft_seed_path` — a fifth kind of file. `apply_roadmap_seeds` (`roadmap.py:1633`) does not print either marker itself — it only collects `missing_drafts`/`unparseable_drafts` path tuples on a result object, and the text `cli/roadmap_cmd.py`'s apply branch prints from them (`missing draft source: <path>` / `draft provenance not parseable: <path>`, no `⚠` glyph) belongs to a different code path that refuses the whole apply rather than degrading per-plan. The two markers this walk prints are therefore a **genuinely new convention** — justified directly against this plan's own `⚠ undefined:` / `⚠ ambiguous:` wording (§ Architecture above), not a reuse of existing precedent: an absent seed renders as `⚠ missing draft seed: <path>` and an unparseable one as `⚠ unparseable draft seed: <path>`, each naming the path, with the rest of that plan's walk unaffected. **An absent seed is breakage, not a lifecycle state** — stage 4 writes the draft seeds together with `04-roadmap.md`, so any roadmap with plan rows to walk is one whose seeds were written; a walk reaching a plan row at all means the seed should be there. There is no "not seeded yet" state to distinguish, which is why the marker needs no lifecycle qualifier.

**Every list has a stated order, because "one deterministic rendering" is the Outcome's headline property.** Rows render in **source order within an artifact, artifacts in stage order** (`01-domain` → `04-roadmap`) — the order the file already has, so a reader can find a rendered row by scrolling the artifact. That fixes the ledger's decisions, the citation map's ids, the pending group, the un-ordered plan group, and the feedback rows in `review` mode. The walk's plans follow `ordering` instead, that being its whole point, with un-ordered rows appended in `plans` source order. Nothing sorts by label, count, or severity: the same artifacts must render byte-identical output on every run, and that is asserted rather than claimed.

**In `review` mode, unclosed `feedback` rows join the ledger's pending section — all three of `open` / `awaiting-review` / `deferred`, keyed on the lifecycle rather than on the word *open*.** `FeedbackState`'s docstring is explicit that the reviewer and never the tool moves a row out of `AWAITING_REVIEW` ("the state says a response is on offer, not that anyone accepted it"), which makes it *more* pending on the human than `open` is. An unanswered reviewer request is exactly an open item. Feedback ids stay outside the design-row namespace, exactly as `_rows_of` keeps them.

**A `removals` record renders beside the feedback that cited it**, closing the loop, and nowhere else — never as its own section (§ Out of scope carries the reason).

**A removal is a tombstone, and the view says so rather than implying otherwise.** A `RemovalRecord` carries exactly `removed_id`, `rationale`, and `feedback_ids` — **never the removed row's content**, which was deleted from the artifact and survives only in git. None of the three recovers it: the id is a slug that may or may not be self-describing (`entity-campaign` says something, `constraint-07` nothing); the `rationale` is gated non-blank but nothing requires it to *describe* the row, only to justify the drop; and the citing feedback is transient, since `check_design_row_continuity` states that "a citation that resolved last run may name a row nobody can restore". Nor do decisions fill the gap: `DecisionRow.rejected_alternatives` is where captured reasoning about roads not taken lives, but **no field links a removal to a decision**, so the join does not exist.

So a removal renders as what it is — the bare `removed_id`, its rationale, and its feedback linkage — with the rendering **stating that the row's content is not recoverable here and that git holds it**. It is never dressed as a resolved row, and `removed_id` is never marked `⚠ undefined:`, unresolvable being its correct state rather than a defect.

**A removal whose feedback is also gone leads nothing.** Such a record is a bare id and one sentence; giving it a section of its own is the ever-growing graveyard § Out of scope refuses, arrived at under another name. It renders only where it is still load-bearing — beside live feedback, and as the resolution target below. `current` mode resolves no removal at all, so the question does not arise there.

**The one real join, kept:** a **live** feedback target resolving *through* a removal, mirroring `check_feedback_integrity`'s `design rows ∪ removals` set. That is narrow, genuine, and the review loop's designed success path.

**A `settled` decision's anchor can never dangle through a removal.** `check_design_row_continuity` refuses the drop outright — "a row a **settled** decision anchors to may not go at all — not even with a cited removal" — rather than let `check_settled_decisions` and `check_decision_records` oscillate. So the ledger's anchor resolution is safe by construction for exactly the decisions most worth reading, and a dangling anchor there means a hand edit, not a review.

**`RemovalRecord.removed_id` is an expected-absent reference, carved out of the dangling rule by definition rather than by exception.** A removal *records that a row is gone*: `removed_id` naming no live design row is the record working, not breakage. Rendering `⚠ undefined:` for it would fire on every healthy revised roadmap — the false positive the dangling rule exists to avoid, arrived at from the opposite direction. It renders as a literal id annotated as expected-absent, at the tombstone, and never as dangling. This is the third carve-out on the review loop's success path, beside the removals union and the artifact-scope target.

**`feedback_ids` reaches a reader too, but through the reverse direction, not a forward print.** No view prints a removal's `feedback_ids` values literally at the removal's own site — they are never dressed up as "expected-absent" text the way `removed_id` is. Instead, each id it names is a key the reverse index already resolves: under `review` mode, querying one of those feedback ids surfaces the removal as one of its citers, using the same tombstone label. The field is covered by that reachability, not by a second literal print.

**`LoadedRoadmap` is step 2's deliverable and the other three views' only input.** It carries: the four artifacts that parsed, the ones absent, the ones present but unparseable, **whether the roadmap directory exists at all**, the mode it was built for, and the roadmap-wide id index the resolver reads. Steps 3, 4, and 5 render from it and never touch the disk themselves — which is what keeps the load rules, the mode filter, and the degradation notice in one place instead of three.

**It is deliberately *not* called an envelope**, because `roadmap_gates.ArtifactEnvelope` already owns that noun and means something else: the artifacts parsed so far with the one under check last, whose `domain` field is **always present** because a gate set always has a domain to resolve anchors against. `LoadedRoadmap` must tolerate an absent `01-domain.md` — a directory holding none of the four still renders — so reusing the name would invite a reader who knows the codebase to assume a compatibility that does not hold, and the two types are not interchangeable in either direction.

**The missing-directory signal lives in `LoadedRoadmap`, and the two sides of the rc split are named.** A missing roadmap directory and four absent artifacts are otherwise represented identically, which is how the rc 2 / rc 0 line quietly collapses to rc 0 for both. **Step 2 detects it** (it is the only step that touches disk) and records it as its own field; **step 6 maps it to rc 2** (it owns the exit-code mapping). Neither may assume the other did it.

**One invocation renders one view, in one mode.** `--view` takes exactly one of `walk` / `ledger` / `index`; there is no "render everything" form. The absent/unparseable notice is therefore emitted **once per render, before that view's output** — one render, one view, one statement of what it could not read. Where this plan says "all three views" it means each of the three invoked in turn, never one invocation producing three.

**A partial roadmap is the normal case, not the edge case.** `--from-stage` re-entry, an interrupted run, and every mid-authoring moment leave only `01-domain.md` (± `02-constraints.md`) on disk. Each view is a join across up to four artifacts and **degrades to the stages that exist** rather than reporting a truncated web as whole.

**The all-absent case is the line between a render and a failure, and it is drawn on the directory.** A roadmap directory that does not exist — a mistyped slug, a slug never run — is a **pre-flight failure at rc 2**, matching what `cmd_roadmap` already does with an unusable slug: there is nothing to render and an empty rendering would be a worse answer than an error. A directory that *exists* but holds none of the four artifacts **renders at rc 0** with a notice naming all four as absent: that is a real mid-authoring state, and reporting it is the view working. The distinction is *does the roadmap exist*, not *does it have content*.

**A present-but-malformed artifact is reported like an absent one; it does not abort the render.** `load_domain_artifact` and its three siblings raise `RoadmapArtifactError` on a file that exists and is malformed — the same hand-edited state these views exist to read — and `cmd_roadmap` maps that exception to rc 2 on the authoring path. A read-only render must not inherit that: it catches the error per artifact, names the file in the same notice that names the absent ones (distinguishing *unparseable* from *not found*, since they call for different fixes), renders every view from the artifacts that did parse, and **still exits 0**. A traceback from a read-only command is the failure mode being designed out.

**A dangling id renders visibly (`⚠ undefined: …`), never crashes and never silently drops the edge.** A hand-edited artifact read outside a stage run can carry an id no gate ever saw; dropping it silently would hide exactly what the gates exist to report. **The one id that is not dangling despite resolving to no design row is a feedback `target` naming a removed row** — resolve feedback targets against `design rows ∪ removals`, mirroring `check_feedback_integrity`'s own set, whose comment names that union as "what lets feedback ask for the removal of the row it names". A design-rows-only resolver prints `⚠ undefined:` on a well-formed roadmap: a false positive in the review loop's *designed* success path.

**The second target that is not dangling: an artifact-scope feedback row.** `FeedbackTarget.kind` may be `ARTIFACT`, carrying no `row_id` at all. The resolver branches on `kind` before it looks anything up, and renders such a row as bearing on the artifact as a whole. A resolver that skips that branch produces a second false positive on the same success path the removals union already protects.

**The id space is roadmap-wide, and an ambiguous id renders as visibly as a dangling one.** `check_duplicate_row_ids` exists because ids must be unique "across the roadmap's artifacts, not only within one file" — an anchor "would otherwise resolve two ways" — so the resolver builds one roadmap-wide index and inherits that gate's contract rather than a per-artifact one. The hand edit that produces a dangling id produces a duplicate just as easily, and a resolver that returns whichever row it saw first hides precisely what that gate exists to report. An id matching more than one row therefore renders as `⚠ ambiguous: <id>` naming every row it matched, rather than resolving to one of them.

**Placement preserves the one-way chain, with the view *below* the gates rather than beside them.** A new read-only module `plan_tool/roadmap_view.py` importing `roadmap_artifacts` **and `roadmap_gates`**, extending the chain to `roadmap_artifacts` → `roadmap_gates` → `roadmap_view` → `cli/roadmap_cmd`, still strictly one-way and acyclic; nothing imports `roadmap_view` but the CLI.

**Why the gates import, decided 2026-08-07 — it is the narrow fix, not a widening for convenience.** The view's id index must be the *same* design-row set the gates resolve against, and `roadmap_gates.design_row_ids` is public for exactly that reason, in its own words: "Public because the orchestrator's predecessor pre-flight resolves a feedback target against the *same* set this module's gates do. **Two implementations would drift the first time either artifact gains a collection.**" `roadmap_artifacts` exports `plans_design_rows` and `components_design_rows` but no domain or constraints equivalent — `_domain_rows` and `_constraints_rows` are private to `roadmap_gates` — so a view fenced to `roadmap_artifacts` alone must re-derive two of the four, which is the drift that docstring names. A collection added to `01-domain.md` later would reach the gates and not the view, live ids would render `⚠ undefined:` and vanish from the citation map, and the whole suite would stay green.

**What the import actually buys, precisely — a pinned equality, not a literal reuse.** `design_row_ids` returns a bare `set[str]`, never the row objects a display label needs, so the view's own index-building walk cannot be replaced by a call to it; the walk still has to enumerate each artifact's row collections itself to get the objects. What the import buys is a **membership check the walk's own tests assert against directly** — `roadmap_gates.design_row_ids(artifact)`, imported and compared, per artifact — so a collection either loader starts returning that the other one doesn't reach fails a test immediately instead of silently diverging. This two-implementation shape is unavoidable given `design_row_ids`'s signature: changing it to return row objects would be reorganization, which this plan fences at none (below, "Allowed reorganization: none"). The alternative — no gates import at all — is strictly worse: the same duplication would exist with no test pinning the two together, which is the exact drift the imported docstring warns against.

The import is **read-only and narrow**: `design_row_ids` for membership, and nothing that judges. The view imports no `Violation`, emits no finding, and runs no gate — § Out of scope's "second enforcement channel" bar is unchanged. Moving `_domain_rows` / `_constraints_rows` down into `roadmap_artifacts` so both could import them was considered and **not taken**: it is reorganization, which this plan fences at none (below, "Allowed reorganization: none"), and it would edit a module this work otherwise only reads.

**The CLI shape — settled 2026-08-07, user-confirmed; do not re-open.** The views ship as **`--view {walk,ledger,index}`, a third read mode in `roadmap`'s existing mutually exclusive group** beside `--apply` and `--from-stage`, with `--id <row-id>` supplying the reverse index's subject and **`--mode {current,review}` (default `current`)** selecting how much of the record is in scope. A read mode belongs in that group for the same reason `--apply` does: it runs no stage and invokes no backend. `--from-existing` is not required in this mode. `--mode` and `--id` are meaningful only with `--view`; passing either without it is an error, not a silent no-op.

The rejected alternative was a sibling read verb (`plan-tool roadmap-view <view> <slug> [id]`). It reads more cleanly for three views and takes a row id as a positional rather than a conditionally-meaningful flag, but it costs a `COMMAND_MODULES` entry in `plan_tool/cli/__init__.py` and a new `CAPABILITIES.md` **capability row** (`check_capabilities` raises `orphan-subcommand` only for a *subcommand* with no owning capability; its findings are advisory either way and never gate an exit code) — two surfaces for a read mode that has one natural home. Not taken.

`tests/cli/package_surface_help.golden.txt` is **not** one of those verb-only costs: it already carries a line per `roadmap` invocation form (`--from-existing`/`--from-stage`, and `--apply`), so the read mode adds a third line to it under the settled flag shape too. It is in scope for step 6 either way.

**`--view index` without `--id` renders the full citation map** — every declared id with the rows that cite it, ids nothing cites included and marked as such. That is the reverse index's whole-roadmap render, and it is why the four fields the walk carries (`depends_on`, `assumption_targets`, `consuming_plan_ids`, `FieldRow.entity_id`) are reachable even by a reader who knows no id to ask about. `--id` on any other view is an error, not a silent no-op.

**In scope.** `plan_tool/roadmap_view.py` (new module), its wiring in `plan_tool/cli/roadmap_cmd.py`, `tests/test_roadmap_view.py` and `tests/cli/test_roadmap_cmd.py` (the flag-parsing half: mutual exclusion, the `--mode` default, `--id` outside `--view index`), and the doc sweep a fifth roadmap module obliges — **all of it unconditional**: the four-module chain line in CLAUDE.md § "Architecture", the matching text in `docs/ARCHITECTURE.md`, a new `ROADMAP_FORMAT.md` § "See also" **entry pointing at `roadmap_view.py`** (that section states no module chain or count today — every "four" in the file is the four *artifacts* or the four *gate tuples* — so this is an addition, not a correction), `CAPABILITIES.md`'s `architecture-roadmap` **`surfaces:` line** (which enumerates the roadmap modules today and would otherwise keep naming four after a fifth ships), and a `docs/cli/` regeneration (`python -m plan_tool.cli_reference --write`). No new `CAPABILITIES.md` **capability row**: the settled flag shape adds no subcommand, so `check_capabilities` has nothing to orphan — the `surfaces:` line above is the only edit that file takes.

Plus the **invocation-form** sweep § Risks names, which is a distinct class from the module chain: `plan_tool/cli/__init__.py`'s roadmap catalog and `tests/cli/package_surface_help.golden.txt` (both code-side, step 6), and `integrations/claude/SKILL.md`, `README.md`, and `USE_CASES.md` (doc-side, step 7).

The one-way import chain becomes `roadmap_artifacts` → `roadmap_gates` → `roadmap_view` → `cli/roadmap_cmd`, so CLAUDE.md § "Architecture"'s cycle-free constraint list gains a line rather than only having its count corrected.

No new parser: `load_domain_artifact`, `load_constraints_artifact`, `load_components_artifact`, `load_plans_artifact`, and `parse_draft_seed_provenance` all ship today and between them read every row the views need. The claim is that this work writes no parsing code — not that it reads no file the four artifact loaders miss, which would be false for the draft seeds.

**Allowed reorganization: none.** Stated explicitly here rather than left to the seed's scope-contract field or to `BACKLOG.md` #240, both of which this plan outlives — the seed is archived and #240 is deleted on shipment (step 7), so a citation pointing at either goes stale. Every module this plan touches keeps its current owner and current file; no function moves, and no existing module's public surface changes shape to accommodate this work (the one exception, discussed above, is `roadmap_gates.design_row_ids`'s status as a read dependency of a new module — that module gains a caller, but its own signature and file are unchanged).

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — Official reference for add_mutually_exclusive_group(), which `roadmap` already uses for `--apply` / `--from-stage` and which the settled `--view` read mode joins, plus the choices/metavar semantics `--view` and `--id` are declared with.
- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — Documents fields() and asdict() for introspecting the roadmap row dataclasses, which is how the view enumerates the seventeen cross-row reference fields without re-parsing frontmatter.
- [collections — Container datatypes (Python 3 docs)](https://docs.python.org/3/library/collections.html) — defaultdict(list) and ordered-mapping semantics for building the reverse index (id → every citing row) deterministically in a single pass over the loaded artifacts.
- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — Path.exists()/read_text() semantics needed to detect which of the four staged artifacts are present so a partial roadmap degrades and names the files it did not find.
- [textwrap — Text wrapping and filling (Python 3 docs)](https://docs.python.org/3/library/textwrap.html) — indent(), dedent(), and fill() for rendering the nested traceability walk and decision ledger as stable indented text, and for dedenting expected output in fixtures.
- [string — Format Specification Mini-Language (Python 3 docs)](https://docs.python.org/3/library/string.html#format-specification-mini-language) — Fill, alignment, and width specifiers for the ledger and reverse-index columns, so rendered output is byte-stable across runs and safe to assert on structurally.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Mermaid or other graph output.** A separate entry: at 137 rows a whole-roadmap graph is a hairball, and per-plan subgraphs are a second design question.
- **A standalone removals or history section.** Records accumulate without bound across revisions, and a record preserves only `removed_id` plus a rationale, never the row's content — a dedicated section would be an ever-growing graveyard that cannot show what was lost. Removals are in scope *only* as the resolution half of the feedback lifecycle, as a tombstone beside the citing feedback row. **Excluding them outright was considered and rejected 2026-08-06 — do not re-cut it**, for the `check_feedback_integrity` false-positive reason in § Architecture. **The reverse also holds and is the narrowing of 2026-08-07:** `review` mode does not license a removals section by another name. A record that cannot show what was lost does not lead a rendering, whatever the mode — if a change would give removals their own heading, an ordered list of their own, or a place a reader arrives at rather than passes through, it has re-created this refused section and is out of scope.
- **Draft-seed bodies.** A seed is a `SEED_FORMAT.md` document with its own contract; the walk cites its path and provenance and stops.
- **Machine-readable output.** Text only, no `--json`, until a caller that needs it exists.
- **Reading plan files or the `.plan-tool` manifest.** Roadmap artifacts only.
- **Becoming a second enforcement channel.** These views are the first reader of artifacts no gate has just blessed, so a join that exposes a gate hole is the expected case, not a remote one. **A gate defect found while joining is a `BUG_BACKLOG.md` entry, not a fix inside this work** (#240's stop/defer rule). The view reports what it finds — `⚠ undefined:` / `⚠ ambiguous:` are rendering annotations, never findings: no exit code, no report, no convergence signal. Any other out-of-scope discovery goes to `BACKLOG.md` / `BUG_BACKLOG.md`, never applied as plan expansion.
- **Generating a narrative "story" of the roadmap. Do not re-open without new evidence.** It was the originating proposal (2026-08-06) and loses on two counts. (a) A story imposes one linear traversal on a graph with at least four legitimate reading orders, so it serves one reader and buries three. (b) It is a second prose copy of the frontmatter that nothing can check — precisely CLAUDE.md § "Validating a semantic property you cannot observe", whose named unobservable is "the doc is accurate". Roadmaps are **revisable** (feedback rows, removals, `--from-stage` re-entry), so a story goes stale on every revision, and a confident stale story about a twice-revised roadmap is worse than four dense files.

## Risks

Low overall: read-only and additive, no existing behavior moves. Four correctness traps, every one from reading artifacts no gate has just blessed, and one process risk:

- **Reporting a partial roadmap as whole.** The mitigation is structural, not advisory: a render names the artifacts it did not find and the ones it could not parse, so absence is stated rather than inferred from a short rendering.
- **The two false positives on the review loop's success path.** A resolver that ignores the removals union, or that does not branch on `FeedbackTarget.kind`, prints `⚠ undefined:` on a well-formed roadmap — in the one channel this work relies on being trusted. Both pass every other assertion in § Testing and fail only on their own case, which is why each is pinned by its own test rather than left to review.
- **The ambiguous id resolving silently.** A roadmap-wide index that keeps the first match hides exactly what `check_duplicate_row_ids` exists to report, and it fails no other test.
- **An unparseable artifact aborting a read-only render**, or worse, escaping as a traceback — the authoring path's rc-2 mapping is the wrong behavior to inherit here.
- **A missed doc-sweep site — and there are *two* classes here, not one.** Both are invisible to an identifier sweep for `roadmap_view`, because each site names only what exists today. Sweep by **vocabulary** per CLAUDE.md § "Documentation is forward-looking"; the roadmap paragraph in CLAUDE.md has already carried stale counts once.
  - **The module class** — a fifth roadmap module invalidates a count and a chain restated in at least five places, the fifth being `CAPABILITIES.md`'s `architecture-roadmap` `surfaces:` line. Vocabulary: "four modules", "one-way", the chain arrow line, the surfaces enumeration. Note the chain itself changes shape, not just length: the view sits *below* `roadmap_gates`, so the line is no longer a simple rename of a four-item list.
  - **The invocation-form class** — `--view` is a third way to invoke `roadmap`, and every place that enumerates the existing two goes stale. `plan_tool/cli/__init__.py`'s roadmap catalog (whose own docstring says "keep this catalog and the SKILL.md 'Subcommands at a glance' section in sync", and which is what `tests/cli/package_surface_help.golden.txt` snapshots — editing the golden alone reddens `test_package_surface.py`), `integrations/claude/SKILL.md`'s glance row, `README.md`'s cheatsheet, and `USE_CASES.md` § roadmap. Vocabulary: "invocation form", "mutually exclusive", "`--apply`", "two non-zero exits". **The sharpest instance:** SKILL.md states `--apply` is "mutually exclusive with `--from-stage`" — a sentence `--view` makes *incomplete rather than wrong*, which is the kind an identifier sweep never flags.

## Testing

`tests/test_roadmap_view.py` mirrors the module, built on parsed-artifact fixtures. **Verify by mutation, never by reading** — break each join and watch it go red — and **assert resolved ids and structural keys, not prose words**, since a substring check breaks the next time a legitimate label uses the word.

**Assert the carve-outs, not only the rules.** Each is a deliberate exemption a later widening would otherwise swallow while staying green:

- a dangling id renders visibly rather than crashing or dropping the edge;
- an **ambiguous** id renders visibly, naming every row it matched, rather than resolving to the first;
- a feedback target resolvable **only** through a `removals` record renders as resolved, not dangling;
- an **artifact-scope** feedback target (`kind: artifact`, no `row_id`) renders as artifact-scope, not dangling;
- `RemovalRecord.removed_id` renders as **expected-absent**, never as dangling, on a roadmap that has been through one review close — the case a uniform dangling rule gets wrong; querying one of its `feedback_ids` under `review` mode surfaces the removal as a citer, distinctly from the tombstone's own forward print;
- **`current` mode renders no `feedback` row and no `removal`**, and `review` mode renders both — the pair, since a mode that filters nothing passes every single-mode assertion;
- **`--view walk`'s body renders byte-identically under both modes** below its mode header, that invariance being deliberate — assert the body, not the whole output, or the header defeats it;
- the id index **equals `roadmap_gates.design_row_ids`** for each artifact, imported and compared directly rather than re-listed in the test — a re-listed expectation drifts with the view instead of catching it;
- a **feedback id** as `--id` resolves under `review` mode and reports out-of-scope-for-mode under `current`, distinctly from an undeclared id — three outcomes, not two;
- a **missing roadmap directory** is distinguishable in `LoadedRoadmap` from four absent artifacts, since the rc split depends on it and both otherwise look identical;
- a `pending` decision renders in **both** modes, being design state rather than review channel;
- a `cross-cutting` plan with no `component_ids` renders as such, not as a defect;
- a domain-only roadmap renders and names the three artifacts it did not find;
- a **present-but-unparseable** artifact is named as unparseable, distinctly from absent, and the render completes and exits 0;
- a roadmap directory holding **none** of the four artifacts renders at rc 0 naming all four, while a directory that **does not exist** is a pre-flight failure at rc 2 — the pair is the line, and either alone leaves it undrawn;
- a plan row absent from `ordering` renders marked as un-ordered, an `ordering` entry naming no plan row renders as dangling, and an `ordering` entry repeating a `plan_id` already rendered renders as a duplicate marker rather than a second full render;
- an **absent** and an **unparseable** draft seed each render named, with the rest of that plan's walk intact;
- in `review` mode, a removal whose citing feedback is **still live** renders beside it as a tombstone, and one whose feedback has been closed renders **nowhere** — the pair, not either alone, is what pins the rule, and the second half is what stops the refused removals section returning under this mode;
- a removal's rendering names the id and the rationale and makes **no claim about the removed row's content** — assert the absence, since a later change that starts guessing a label from the id would otherwise pass every other test here;
- a `settled` decision's anchor **never** dangles through a removal (`check_design_row_continuity` refuses the drop), so a dangling settled anchor in a fixture is a hand edit and renders as one;
- all three unclosed feedback states reach `review` mode's pending group, and a closed one does not;
- the same artifacts rendered twice produce **byte-identical** output, and every list follows the stated order rather than a sort;
- every row kind's display label resolves to the field the rule names — one case per kind, so a kind added later fails loudly instead of inheriting `name`;
- a **system** pattern and a **component** pattern of the same `name` render distinguishably by scope, in both the walk and the reverse index;
- a reverse-index query for an **undeclared** id reports it as undeclared, distinctly from a declared id that nothing cites.

Prefer one parametrized test per rule over the whole row-kind / failure-mode set — a new row kind or a new resolver failure mode should fail an existing test rather than silently pass an under-specified one.

**Manual smoke read, explicitly not a gate.** Run each view in each mode against a real multi-artifact roadmap and read the output. The toollib roadmap named in § Problem statement sits under `.tmp/`, which is gitignored and transient by definition — CLAUDE.md says so, and it went missing once during this plan's own authoring — so it is a convenience if present, never a dependency: regenerate it, point at any roadmap on disk, or skip the check. **Every property this plan asserts is pinned by a fixture test above**; the smoke read exists to catch what fixtures cannot — output that is correct and still unreadable at 137 rows. Nothing in the plan's verification depends on a scratch directory surviving.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (feature) — tests covering the behavior this step changes; green before completion.
- step 6 (feature) — tests covering the behavior this step changes; green before completion.
- step 7 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- Each of the seventeen reference fields in § Problem statement takes exactly one of **three** dispositions, and which one is stated: **(a)** resolved to its target row's display label in at least one view; **(b)** covered without a forward-printed resolved label — which is the disposition for `RemovalRecord.removed_id` (an annotated literal id at the tombstone, naming a row gone by design), for `RemovalRecord.feedback_ids` (covered in reverse: querying one of the named ids under `review` mode surfaces the removal as a citer — a reverse-lookup match satisfies this disposition with no forward print required), for an `ARTIFACT`-kind `FeedbackTarget` carrying no `row_id`, and for `DraftSeedProvenance.roadmap_components` where the walk prints provenance without resolving it; or **(c)** deliberately unrendered, stated in the module's own docs with the reason. Disposition (b) exists because (a) is unmeetable for an id whose referent no longer exists or is reachable only in reverse, and (c) would wrongly imply it is not shown.
- Every row kind an id can name has exactly one display label, fixed in the resolver; no renderer defines its own. A resolved `PatternRow` label names its scope (system vs. component), not `name` alone.
- The traceability walk emits plans in `ordering` sequence, renders any un-ordered plan row after that sequence, any ordering entry naming no plan row as dangling, and any ordering entry repeating a `plan_id` already rendered as a duplicate marker rather than a second full render — the three anomalies `check_plan_ordering_totality` itself checks for — and reaches `draft_seed_path` plus that seed's `roadmap_components` for every plan row — naming the seed when it is absent or unparseable instead.
- The decision ledger accounts for every `DecisionRow` on all four artifacts exactly once, grouped by `status`, in **both** modes; `review` mode additionally carries unclosed feedback rows in the pending group, each with any removal it cited rendered beside it as a tombstone; a removal whose feedback has since been closed renders in no view.
- `current` mode renders no `feedback` row and no `removal` in any view; `review` mode renders both **in the ledger and the reverse index**, those being the only views the mode changes; `--view walk`'s body is byte-identical under the two below its mode header; and every render names the mode it was produced under.
- The view's id index equals `roadmap_gates.design_row_ids` per artifact — asserted against that function directly, so a collection added to any artifact later fails this rather than silently vanishing from the citation map.
- Under `--mode review` the citation map's declared population is design rows ∪ feedback rows and `--id` accepts either; under `--mode current` a feedback id is reported as out of scope for the mode, distinctly from an undeclared id.
- No removal renders under its own heading, in a list of its own, or anywhere a reader arrives at rather than passes through — in either mode; and no rendering of a removal asserts anything about the removed row's content.
- The reverse index, given any declared design-row id, returns every citing row; returns an empty result — stated as such — for a declared id nothing cites; and reports an undeclared id as undeclared.
- Each of the three views, invoked in turn against a domain-only roadmap, renders and names the three artifacts it did not find, once before that view's output.
- A roadmap with one present-but-unparseable artifact renders each view from the remaining artifacts, names that file as unparseable distinctly from absent, and exits 0; a directory with none of the four renders at rc 0, and a directory that does not exist fails pre-flight at rc 2.
- The same artifacts render byte-identical output on repeat invocations, with every list in the order § Architecture states.
- A well-formed roadmap renders with zero `⚠ undefined:` markers in either mode — including one whose feedback targets resolve only through removals, one carrying an artifact-scope feedback row, and one revised through a review close whose `removed_id` and `feedback_ids` name rows that are gone.
- An id declared by two rows renders as ambiguous, naming both, in every view that resolves it.
- No artifact on disk changes, no backend is invoked, and a completed render exits 0 — whatever it found, and with no `⚠` marker reaching a report, finding, or convergence signal.
- The gates, stage table, `--apply`, and `--from-stage` behave identically before and after.
- The doc sweep lands at every site in § In scope — including `CAPABILITIES.md`'s `architecture-roadmap` `surfaces:` line — and `docs/cli/` regenerates clean.
- `--view` is mutually exclusive with `--apply` and `--from-stage`, does not require `--from-existing`; `--mode` defaults to `current`; and `--id` outside `--view index`, or `--mode`/`--id` without `--view`, is an error.
- `--view index` with no `--id` renders the full citation map; `plan-tool` gains no new subcommand and `CAPABILITIES.md` gains no new capability row.
- `BACKLOG.md` #240 is reconciled on shipment.

## Deferred

- **Mermaid / graph output** and per-plan subgraphs — their own entry and their own design question.
- **A decision-arc narrative on top of view 2.** The one place narrative genuinely beats a join: rejected alternatives and rationales are causal, and a table flattens what prose keeps as reasoning. If it is ever built it is regenerated disposably and never hand-edited. Out of scope here.
- **`--json` or any machine-readable form**, until a caller needs it.
- **The cheap cut, if this does not earn its slot:** the decision ledger alone is a single-view v1 and is `direct`-sized. Take it as a fallback, not as a first step that leaves the other two views half-specified.
