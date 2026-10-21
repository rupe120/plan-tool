> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the citation map and the reverse index view

## Summary

Adds a roadmap-wide citation map to `plan_tool/roadmap_view.py` — a reverse
index from any id to the rows that name it — plus the render function behind
`--view index`: given a `LoadedRoadmap` (step 2) and an optional row id, it
prints either the full map or one id's citers as text. The map covers the
eleven reference fields that neither the walk nor a removal's own label
already claims, built once from `LoadedRoadmap` so that current-mode correctness for
feedback and removal citers falls out of `feedback_index` / `removal_index`
already being empty under that mode — no mode check needed at this step. The
one place mode still has to be checked directly is distinguishing an
undeclared id from a feedback id that current mode is hiding, because the
mode-filtered index alone cannot tell the two apart. On green, any id resolves
to its citers deterministically in either mode, an undeclared id, an
uncited-but-declared id, an ambiguous id, and a feedback id hidden by the
current mode each render as a different, stated outcome, and step 4's walk
gets its entity-to-business-rule/workflow reverse hop from this map instead of
building a second traversal.

## Table of Contents

- [Why](#why) — the gap this step closes and why the walk depends on it
- [Input](#input) — the step 1 and step 2 contracts this step builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — both edits, no new files
- [Implementation](#implementation) — field ownership, the map, and the view
- [Tests](#tests) — what `tests/test_roadmap_view.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — stdlib docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what later steps own instead

## Why

Every cross-row reference in a roadmap is still a bare id in YAML after steps
1 and 2: step 1 can turn one id into a label, and step 2 can load a roadmap
off disk, but nothing yet answers "if this row changes, what moves" — the
reverse question of which rows name a given id. The plan's Architecture states
this plainly for two fields in particular: `BusinessRuleRow.entity_ids` and
`WorkflowRow.entity_ids` point *at* entities, and there is no field on
`EntityRow` pointing back. Step 4's traceability walk needs that reverse hop
for every entity it renders, and the plan makes step 4 depend on step 3
instead of duplicating a traversal for exactly this reason.

This step is also the first to render anything from a `LoadedRoadmap` — steps
1 and 2 built the ingredients (the design-row index, the removal index, the
mode-filtered feedback and removal populations) without consuming them; step
2's own Deferred section names "the reverse index, the traceability walk, and
the decision ledger's own logic" as steps 3, 4, and 5's job, "all consuming
`LoadedRoadmap` without touching disk themselves." The reverse index is also
one of only two views the plan's `--mode` flag changes (the decision ledger,
step 5, is the other), so getting the mode boundary right here sets the
pattern step 5 follows.

## Input

This step builds on both prior steps and reads no new contract:

- **Step 1** supplies `resolve_id`, `Resolution` (with its `RESOLUTION_*`
  status constants), `display_label`, and `DesignRowEntry` (`kind`, `id`,
  `artifact`, `row`), all already living in `plan_tool/roadmap_view.py`. This
  step reuses `display_label` for every citer's printed text rather than
  writing a second label rule, and reuses `resolve_id` for the status of a
  queried id against the design-row population.
- **Step 2** supplies `LoadedRoadmap`, the sole input this step reads: its
  `domain` / `constraints` / `components` / `plans` (all `Optional`, present
  or absent per what parsed), `design_row_index`, `removal_index`,
  `feedback_index`, `absent`, `unparseable`, `mode`, and `slug`. Two shape
  facts about it drive correctness here:
  - `feedback_index` is keyed by **feedback id**, not by the id a feedback row
    targets — step 2 built it that way to keep a cross-artifact feedback-id
    collision from dropping a row, not to serve as a target-keyed lookup. This
    step must flatten `feedback_index.values()` and read each row's
    `.target.row_id` to get a target-keyed edge.
  - `removal_index` is keyed by **removed id**, not by the feedback ids a
    removal cites. This step must flatten `removal_index.values()` and read
    each record's `.feedback_ids` tuple to get a feedback-id-keyed edge.
  - `domain` / `constraints` / `components` / `plans` are **not** mode-gated —
    only the two indexes built from them are. Under `mode="current"` these
    four fields still carry their full `.feedback` tuples; only
    `feedback_index` is bound empty. This is the fact that makes the third
    resolution outcome below possible without reaching back into step 2.

## Files (creates vs edits)

- **New files:** none. Step 1 creates both files this step touches.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — adds the citation map builder, the
    id-resolution helper for a queried subject, and the reverse-index render
    function.
  - `tests/test_roadmap_view.py` — adds the test functions in § Tests.

## Implementation

**Which of the seventeen reference fields this step owns.** The plan's
Architecture assigns three of them to the walk to print directly as it
descends: `FieldRow.entity_id`, `OrderingEntry.depends_on`, and
`OrderingEntry.assumption_targets` — the last two both plan-id-valued and
both leaves, resolved identically; `assumption_targets` never names an
`AssumptionRow` (`ROADMAP_FORMAT.md`'s own comment: "Plan ids this entry's
ordering-level assumptions bear on," and `check_plan_ordering_totality`
validates it against the roadmap's plan ids, the same rule `depends_on`
gets). Three more sit elsewhere: `OrderingEntry.plan_id` is the walk's own
job to reconcile against `plans` (it names which plan an ordering entry is
*for*, not a citation of another row); `DraftSeedProvenance.roadmap_components`
is the walk's job to print without resolving; `RemovalRecord.removed_id`
never gets its own reverse-index entry because a removed id is not a
declared row — it is disposition (b) wherever the removal itself appears as
a citer, since `display_label` already bakes `removed_id` and the rationale
into that citer's own text.

**`AssumptionRow.consuming_plan_ids` is this step's field to compute, and
the walk's to print — the same split step 3 and step 4 already have for an
entity's governing business rules and workflows.** Nothing on `OrderingEntry`
links an `assumption_targets` entry back to any `AssumptionRow` — there is no
such link, per the field-boundary correction above — so the *only* field
connecting an assumption to a plan is `AssumptionRow.consuming_plan_ids`
itself, in the opposite direction: an assumption names the plans it bears
on, not a plan naming its assumptions. This step walks `loaded.plans.assumptions`
(when `loaded.plans` is not `None`) and, for each `AssumptionRow`, adds it as
a citer of every plan id in its own `consuming_plan_ids`, using
`display_label` (its `.statement`) as the citer text and
`"consuming_plan_ids"` as the field name — so a plan's citer list picks up
every assumption that names it, and step 4 reaches it exactly the way it
already reaches an entity's governing rules: a reverse query into this
step's map, not a second bespoke mechanism.

That leaves **eleven** fields for this step's citation map:
`BusinessRuleRow.entity_ids`, `WorkflowRow.entity_ids`,
`ConstraintRow.anchor_ids`, `ComponentRow.entity_ids`,
`ComponentRow.pattern_ids`, `ComponentRow.constraint_ids`,
`PlanRow.component_ids`, `DecisionRow.anchor` (on all four artifacts, walked
uniformly since the roadmap-wide id index makes per-artifact anchor scoping
unnecessary here), `AssumptionRow.consuming_plan_ids`, and, under
`mode="review"` only, `FeedbackTarget.row_id` and `RemovalRecord.feedback_ids`.
Get this boundary right and step 4 never has to guess whether a field is
already covered; get it wrong (by also indexing a walk-owned field, or
missing one of the eleven) and the two views either disagree or leave a
field with no view resolving it at all — the exact failure the plan's "one
place per rule" design exists to prevent.

**Build the map once from `LoadedRoadmap`, not from separate artifact
parameters.** Unlike step 1's builders (`build_design_row_index`,
`build_removal_index`), which take four optional artifact keywords because
nothing bundled them yet, this step is the first to take a whole
`LoadedRoadmap` as input — the shape steps 4 and 5 will also use. A
reasonable shape: `build_citation_map(loaded: LoadedRoadmap) ->
Mapping[str, tuple[Citation, ...]]`, with a small frozen record — e.g.
`Citation(label: str, field: str)` — pairing the citer's `display_label(...)`
text with the field name that carried the edge (`"entity_ids"`,
`"anchor_ids"`, `"anchor"`, `"pattern_ids"`, `"constraint_ids"`,
`"component_ids"`, `"consuming_plan_ids"`, `"row_id"`, `"feedback_ids"`),
so a caller can tell two
citers of the same id apart when they arrive by different fields. Walk in
`design_row_index`'s own stage-then-source order (domain, constraints,
components, plans) so the same query returns citers in the same order every
time, matching step 1's determinism guarantee rather than introducing a
second ordering rule. Reviewed once: `PatternRow` is only ever cited, never a
citer (it carries no reference field of its own), so it never appears as a
`Citation` entry — only as something other rows' `pattern_ids` name.

**Design-row edges are the same in both modes; feedback and removal edges
follow `LoadedRoadmap`'s own populations.** Walking `loaded.domain`,
`loaded.constraints`, `loaded.components`, `loaded.plans` for eight of the
nine design-row fields above needs no mode check — those four fields carry
the same rows regardless of `mode`. The ninth, `AssumptionRow.consuming_plan_ids`,
is walked separately over `loaded.plans.assumptions` (when `loaded.plans` is
not `None`) — also mode-independent, since assumptions are ordinary design
rows on `04-roadmap.md`, not a mode-gated population. For the two review-only
fields, iterate
`loaded.feedback_index.values()` (flattened) and keep only rows whose
`target.kind` is `FeedbackTargetKind.ROW`, adding each as a citer of
`target.row_id`; iterate `loaded.removal_index.values()` and add each record
as a citer of every id in its `feedback_ids`. Under `mode="current"` both of
those collections are empty by step 2's own contract, so this step adds no
`if loaded.mode == ...` branch anywhere — the same "mode is a property of
`LoadedRoadmap`" rule step 1 and step 2 already state, carried one step
further.

**Resolving what a queried id names needs a third outcome step 1 does not
have, and two fallbacks beyond `design_row_index` — removals and feedback —
each of which can itself be ambiguous.** `resolve_id` (against
`design_row_index`) returns resolved, dangling, or ambiguous; none of those
three distinguishes "genuinely no such id" from "this is a feedback id, but
`mode="current"` does not expose it." The plan's Testing section calls for
exactly three distinguishable outcomes for a feedback id under the two
modes, so this step needs one more status. Add it beside step 1's four
`RESOLUTION_*` constants — reusing the same `Resolution` shape (`status`,
`text`, `matches`) rather than a parallel result type, per the "one result
type for every outcome" precedent — and populate it by checking whether the
queried id appears in any of `loaded.domain.feedback`,
`loaded.constraints.feedback`, `loaded.components.feedback`,
`loaded.plans.feedback` (whichever artifacts parsed) directly, **not**
through `loaded.feedback_index`, since that index is exactly what is empty
under `mode="current"` and would make the new status unreachable. This is the
one place this step reads a `.feedback` tuple straight off an artifact
instead of through step 2's index — narrowly, and only to classify a query
subject, never to render feedback content current mode should hide.

A reasonable shape for the query itself: a function like
`resolve_citation_subject(row_id: str, loaded: LoadedRoadmap) -> Resolution`
that tries, in order, returning on the first non-dangling result:

1. `resolve_id(row_id, loaded.design_row_index)` — resolved or ambiguous
   returns immediately; `resolve_id` never itself needs to know about
   removals or feedback.
2. On `dangling`, `loaded.removal_index.get(row_id, ())` — **the fallback
   step 1's `resolve_feedback_target` already applies to a feedback target's
   own `row_id`, reused here so `--id <a-removed-id>` under `review` mode
   gets the same tombstone (or, on a collision, the same ambiguous naming
   every match) rather than falling through to a plain "no such row."**
   Zero matches continues to the next check; one resolves via that record's
   tombstone label; more than one is `ambiguous`, naming every tombstone —
   identical three-way handling to `resolve_feedback_target`'s own removals
   branch, because both are the same lookup on the same index. Under
   `mode="current"` this is a no-op, since `removal_index` is empty by step
   2's own contract — no `if loaded.mode == ...` branch needed here either.
3. On no removal match, `loaded.feedback_index.get(row_id, ())` — only
   non-empty under `mode="review"`. Zero matches continues to the next
   check; one resolves via that row's `display_label` (its `.request`);
   **more than one — the cross-artifact feedback-id collision step 2's own
   `feedback_index` deliberately preserves rather than drops — is
   `ambiguous`, naming every colliding row's `.request`**, the same
   three-way shape as steps 1 and 2 above rather than a silent pick of
   whichever row was flattened first.
4. On no feedback-index match, the raw `.feedback` tuples, for the
   out-of-scope-for-mode status described above.
5. Otherwise, `resolve_id`'s own `dangling` result.

**A design-row id and a same-string feedback id are different namespaces by
design — `check_feedback_integrity`'s own comment states feedback ids
"deliberately stay out of `check_duplicate_row_ids`" — and this order makes
the design-row result win when a hand edit makes the two strings collide.**
Step 1 is checked first (step 1 above), so a live design row's resolution is
returned before either fallback runs, and a same-id feedback row is never
reached for that query. This is a stated, deliberate precedence — the design
row currently has no way to announce that a same-named feedback row exists
underneath it — not an unspecified edge case; § Acceptance criteria pins the
concrete disposition, and it is a narrower, less surprising fix than adding a
second field to every `Resolution` just to carry a shadow notice for a rare
hand-edit collision.

**The full-map render iterates declared ids, not every id any field
happens to name.** Per the plan's Architecture, `--view index` with no id
"renders the full citation map — every declared id with the rows that cite
it, ids nothing cites included and marked as such." Declared here means
`design_row_index`'s keys always, plus `feedback_index`'s keys under
`mode="review"`. For each key, label the left side with `resolve_id`'s (or,
for a feedback id, `display_label`'s) result — an ambiguous id names every
match, exactly as step 1 already renders it — and look up its citers in the
citation map, printing an explicit "nothing cites this" line rather than
omitting the id when the citer tuple is empty. **Do not** additionally
iterate ids that only appear as a dangling reference inside some other row's
field; the full map is a map of what the roadmap declares, and a dangling
target already renders through the row that names it wherever that row's own
view resolves its fields.

**One `PatternRow` labeling trap to watch for.** Step 1's `display_label`
raises on a bare `PatternRow` passed with no `kind`, deliberately, so a
caller cannot silently guess a scope. When this step labels a
`DesignRowEntry` for the full map's left side, pass `entry.kind` (already
`"system pattern"` or `"component pattern"` from `build_design_row_index`) —
never call `display_label` on `entry.row` alone for a pattern entry, or the
render crashes on the first system/component pattern pair sharing a `name`,
which is exactly the case the plan's Testing section calls out by name for
this view.

**A render header and an absent/unparseable notice belong here first, and
should be written generic enough for steps 4 and 5 to reuse.** The plan
requires every render to name its mode and to state, once, before the view's
own output, which of the four artifacts it could not find or could not
parse — and step 2's own Deferred section leaves "how often it prints per
invocation" to steps 3 through 6. This is the first of those steps to write
it. One way: small private helpers taking only `LoadedRoadmap` (e.g. a
one-line mode/slug header, and a notice built from `loaded.absent` /
`loaded.unparseable`) that a later step can call rather than re-derive —
recommended, not required, since steps 4 and 5 are not yet written and this
step cannot bind their choices.

**Never give a removal its own section here.** The plan's Out of scope
refuses a standalone removals section in either mode, and the reverse index
is a place a reader "passes through," not one they "arrive at": a removal
surfaces only as a `Citation` entry under the feedback id its `feedback_ids`
names, using step 1's tombstone label as-is. No heading, no list, and no
grouping keyed on `RemovalRecord` anywhere in this view's output.

## Tests

`tests/test_roadmap_view.py`, extending steps 1 and 2's suite. Fixtures
follow step 2's pattern — real `DomainArtifact` / `ConstraintsArtifact` /
`ComponentsArtifact` / `PlansArtifact` values loaded into a `LoadedRoadmap`,
not hand-typed YAML — since this step's whole surface is a function of
`LoadedRoadmap`, not of parsing.

### Tests for this step

- `test_citation_map_finds_citers_for_each_design_row_field` (parametrized
  over eight of the nine design-row fields this step owns) — a row declaring
  a reference in that field appears as a citer of the id it names, labeled
  via `display_label`.
- `test_citation_map_walks_decisions_on_every_artifact` — a `DecisionRow` on
  each of the four artifacts appears as a citer of its own `.anchor`, with no
  per-artifact branching required to find it.
- `test_citation_map_finds_assumption_citers_of_consuming_plan_ids` — an
  `AssumptionRow` naming a plan id in its own `consuming_plan_ids` appears as
  a citer of that plan id, labeled via `display_label` (its `.statement`) —
  the ninth design-row field, kept separate from the parametrized eight above
  since it is the one field this step walks over `loaded.plans.assumptions`
  rather than over a row's own reference field.
- `test_citation_map_excludes_the_walk_owned_fields` — `FieldRow.entity_id`,
  `OrderingEntry.depends_on`, and `OrderingEntry.assumption_targets` produce
  no citation-map entry, pinning the step 3/step 4 boundary so a later change
  cannot blur it silently. `AssumptionRow.consuming_plan_ids` is deliberately
  **not** in this list — it is a citation-map field, per the correction
  above, not a walk-owned one.
- `test_review_mode_adds_feedback_target_citers` — a `ROW`-kind feedback
  target naming a live design row appears as a citer under `mode="review"`
  and does not appear under `mode="current"` for the identical fixture — the
  pair, not either mode alone.
- `test_review_mode_adds_removal_feedback_citers` — a `RemovalRecord` naming
  a feedback id in `feedback_ids` appears as that feedback id's citer under
  `mode="review"` and does not appear under `mode="current"` — the pair.
- `test_artifact_scope_feedback_produces_no_citation_edge` — a feedback row
  with `kind=FeedbackTargetKind.ARTIFACT` never appears in the citation map,
  under either mode, since it carries no `row_id` to key on.
- `test_resolve_citation_subject_undeclared_id_is_undeclared` — an id no
  artifact declares reports the undeclared outcome under both modes.
- `test_resolve_citation_subject_declared_id_with_no_citers_is_stated_empty`
  — a declared id with an empty citer tuple is distinguishable from an
  undeclared id — not the same outcome rendered two ways.
- `test_resolve_citation_subject_ambiguous_id_names_every_match` — an id
  declared by two rows reports ambiguous, naming both, reusing `resolve_id`'s
  own result rather than a second ambiguity check.
- `test_resolve_citation_subject_feedback_id_three_outcomes` — one feedback
  id resolves under `mode="review"`, reports the new out-of-scope-for-mode
  status under `mode="current"`, and a genuinely undeclared id reports plain
  undeclared under `mode="current"` too — three distinguishable outcomes from
  one fixture, not two collapsed into each other.
- `test_resolve_citation_subject_removed_id_resolves_through_the_removal_index`
  — querying a `removed_id` no live design row declares resolves via the
  removal's tombstone label, under `mode="review"` — the same false-positive
  case step 1 already pins for `resolve_feedback_target`, exercised here
  through `--id` directly.
- `test_resolve_citation_subject_removal_collision_is_ambiguous` — a
  `removed_id` two `RemovalRecord`s declare resolves `ambiguous`, naming
  every tombstone, reusing step 1's `build_removal_index` collision handling.
- `test_resolve_citation_subject_feedback_collision_is_ambiguous` — a
  feedback id declared by rows in two artifacts (the case
  `feedback_index` deliberately preserves both sides of) resolves
  `ambiguous` under `mode="review"`, naming both rows' `request` text,
  rather than resolving to whichever the flattening happened to see first.
- `test_resolve_citation_subject_design_row_wins_over_a_same_id_feedback_row`
  — a fixture where a live design row and a feedback row share one id
  string resolves to the design row's ordinary label under `mode="review"`;
  the same-id feedback row's own content is not surfaced by this query,
  pinning the stated design-row-wins precedence rather than leaving it
  undefined.
- `test_full_map_lists_every_declared_id_including_uncited_ones` — the whole
  map (no id supplied) contains every `design_row_index` key, plus every
  `feedback_index` key under `mode="review"`, with a stated empty result for
  any id nothing cites.
- `test_full_map_labels_same_named_patterns_by_scope` — a system pattern and
  a component pattern sharing one `name` render two distinct entries in the
  full map, each correctly scoped via `DesignRowEntry.kind`.
- `test_citer_labels_match_display_label_exactly` — a citer's printed text
  equals calling `display_label` on the same row directly, so this step never
  drifts from step 1's label rule.
- `test_citation_map_and_full_map_render_in_stage_then_source_order` —
  citers for one id, and the full map's own id ordering, both follow
  domain-before-constraints-before-components-before-plans, each artifact in
  its own row order.
- `test_reverse_index_render_names_its_mode_and_the_absent_unparseable_files`
  — the rendered text states the mode it was produced under and, once,
  before the view's own output, the artifacts `loaded.absent` and
  `loaded.unparseable` name.
- `test_reverse_index_render_is_the_same_on_repeat_calls` — rendering the
  same `LoadedRoadmap` twice produces the same text.
- `test_reverse_index_render_has_no_removals_heading_or_list` — a fixture
  carrying an unclosed feedback row and the removal it cites renders the
  removal only inside that feedback id's citer entry, never under a heading
  or list of its own.

Every test above is green before this step is considered finished.

## Acceptance criteria

- The citation map covers exactly the eleven fields listed in Implementation
  and no others; the three walk-owned fields, `OrderingEntry.plan_id`,
  `DraftSeedProvenance.roadmap_components`, and `RemovalRecord.removed_id`
  produce no citation-map entry of their own.
- `AssumptionRow.consuming_plan_ids` is one of the eleven: an assumption
  naming a plan id in that field appears as a citer of the plan, and
  `OrderingEntry.assumption_targets` never resolves to an `AssumptionRow` —
  it resolves to a `PlanRow`, the same as `depends_on`.
- `build_citation_map` takes a `LoadedRoadmap` and needs no `mode` branch to
  keep feedback and removal citers out of a `mode="current"` result — that
  falls out of `feedback_index` and `removal_index` already being empty.
- Given any declared design-row id, resolving it returns every citing row;
  given a declared id nothing cites, it returns an empty result stated as
  such rather than omitted; given an id no artifact declares, it returns
  undeclared, distinct from the empty-result case.
- Given a feedback id, resolving it under `mode="review"` returns its citers
  (or a stated empty result); under `mode="current"` it returns a status
  distinct from both "resolved" and "undeclared," derived from the raw
  `.feedback` tuples on `LoadedRoadmap`'s parsed artifacts, never from
  `feedback_index`.
- An id declared by two design rows resolves ambiguous, naming both, matching
  `resolve_id`'s own result. A `removed_id` two `RemovalRecord`s declare
  resolves ambiguous, naming every tombstone. A feedback id two rows declare
  across artifacts resolves ambiguous under `mode="review"`, naming both
  rows' `request` text — none of the three ambiguity cases silently picks
  the first match.
- Querying a `removed_id` no live design row declares resolves through the
  removal index under `mode="review"`, mirroring `resolve_feedback_target`'s
  own removals fallback rather than falling through to undeclared.
- A design row and a feedback row sharing one id string resolve to the
  design row's label; the design-row result is stated as taking precedence,
  not left undefined for that collision.
- The full map (no id supplied) lists every `design_row_index` key always,
  plus every `feedback_index` key under `mode="review"`, and marks a
  zero-citer id explicitly rather than dropping it from the listing.
- A system pattern and a component pattern sharing one `name` label
  distinctly in the full map, using `DesignRowEntry.kind`.
- Every citer's printed text is exactly what `display_label` returns for
  that row — no second label rule exists in this step's code.
- No removal ever renders under its own heading or in a list of its own; it
  appears only as a citer entry under the feedback id its `feedback_ids`
  names.
- The rendered view states the mode it was produced under and names the
  artifacts `loaded.absent` / `loaded.unparseable` list, once, before the
  view's own output.
- Citers and the full map's id ordering both follow stage-then-source order;
  the same `LoadedRoadmap` rendered twice produces the same text.
- The module's first-party imports stay exactly `plan_tool.roadmap_artifacts`
  and `plan_tool.roadmap_gates` — this step adds no new first-party import.
- The module still touches no filesystem, spawns no subprocess, and calls no
  backend.
- `plan-tool validate` and the full existing roadmap suite
  (`tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`,
  `tests/test_roadmap.py`, `tests/test_roadmap_format.py`) stay green.

## References

- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the `Citation` record and the new `Resolution` status, matching every other roadmap-view type's shape.
- [collections — Container datatypes (Python 3 docs)](https://docs.python.org/3/library/collections.html) — `defaultdict(list)` for the citation map, so an id cited by more than one row accumulates every citer instead of overwriting one.
- [textwrap — Text wrapping and filling (Python 3 docs)](https://docs.python.org/3/library/textwrap.html) — `indent()` for nesting a citer list under its id in the rendered text, and for dedenting expected output in fixtures.
- [string — Format Specification Mini-Language (Python 3 docs)](https://docs.python.org/3/library/string.html#format-specification-mini-language) — alignment and width specifiers for keeping the full map's id/label columns stable across runs.

## Applicable guardrails

- **The one-way import chain (plan's Architecture, "Placement preserves the
  one-way chain").** This step adds no new import; the module's first-party
  imports stay `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`,
  never `plan_tool.roadmap` or anything under `plan_tool/cli/`.
- **The gates import stays narrow (plan's Architecture, "Why the gates
  import").** This step reaches `design_row_ids` only indirectly, through
  step 1's already-built `design_row_index` — it adds no new
  `roadmap_gates` symbol.
- **Not a second enforcement channel (plan's Out of scope).** The citation
  map and the reverse-index render never raise on an undeclared, ambiguous,
  or out-of-scope-for-mode id, and carry no severity or blocking field —
  every outcome here is a rendering annotation, matching step 1's
  `Resolution` contract.
- **No standalone removals section, in either mode (plan's Out of scope, and
  its 2026-08-07 narrowing).** A removal appears only as a citer entry under
  the feedback id it names; this step must not give removals a heading, a
  list, or a place a reader arrives at directly.
- **The mode filter belongs to `LoadedRoadmap`, not to this step's own
  re-derivation (plan's Architecture, "The mode is a property of
  `LoadedRoadmap`").** Feedback and removal citer inclusion follows
  `feedback_index` / `removal_index` as-is, with no `if loaded.mode == ...`
  branch for that purpose. The one narrow exception — reading `.feedback`
  tuples directly to classify a queried subject as out-of-scope-for-mode — is
  a classification decision about the query, not a rendering-inclusion
  decision, and does not re-derive what the mode-filtered indexes already
  decide.
- **Machine-readable output stays out of scope (plan's Out of scope).** The
  reverse-index render returns plain text; this step adds no `--json` form.

## Deferred

- **CLI wiring (`--view`, `--mode`, `--id`) and the exit-code mapping** —
  step 6 calls this step's render function; it is not called from anywhere
  yet.
- **The three walk-owned fields (`FieldRow.entity_id`, `OrderingEntry.depends_on`,
  `OrderingEntry.assumption_targets`), `OrderingEntry.plan_id`'s
  reconciliation against `plans`, and `DraftSeedProvenance.roadmap_components`**
  — step 4's traceability walk resolves or prints each of these directly;
  this step's citation map deliberately does not duplicate them.
  `AssumptionRow.consuming_plan_ids` is **not** in this deferred list — it is
  this step's own field, reached by step 4 through the citation map rather
  than printed directly, the same split as an entity's governing rules.
- **The decision ledger's settled/pending grouping, and rendering a removal
  beside the pending feedback row that cited it in that ledger** — step 5;
  this step's own removal handling is limited to the reverse index's citer
  entries.
- **The doc sweep and `CAPABILITIES.md` update** — step 7.
