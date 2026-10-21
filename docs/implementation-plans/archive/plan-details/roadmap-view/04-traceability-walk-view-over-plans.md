> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Add the traceability walk view over plans, components, entities, patterns, and constraints

## Summary

Adds `render_traceability_walk(loaded, plans_dir)` to `plan_tool/roadmap_view.py` — the view behind `--view walk`: for each plan, in `ordering` sequence, it prints the components the plan carries, the entities/patterns/constraints each component names, the business rules and workflows that govern each entity, and ends at that plan's draft seed and the `roadmap_components` provenance it carries. This is the one step of the three views that touches disk directly — the draft seed is a fifth kind of file `LoadedRoadmap` (step 2) does not load, so the walk takes `plans_dir` as a second argument and reads each plan's seed through the shipped `parse_draft_seed_provenance`, mirroring the read pattern `plan_tool/roadmap.py:apply_roadmap_seeds` already uses rather than importing it. The other real design decision here is reusing step 3's citation map for the one reverse hop the format has no forward field for — entity to the business rules and workflows that name it — which means adding a `kind` field to step 3's `Citation` record so the walk can pick out exactly those two row kinds without building a second traversal. On green, every plan renders in `ordering` sequence with its component/entity/pattern/constraint chain resolved, a plan row missing from `ordering` renders after the sequence marked as such, a dangling or ambiguous reference stops the walk at that point instead of guessing which row was meant, and a missing or broken draft seed renders named while the rest of that plan's walk keeps going.

## Table of Contents

- [Why](#why) — the gap this step closes and the two things it depends on step 3 for
- [Input](#input) — the step 1–3 contracts this step reads, and the two small extensions it makes to them
- [Files (creates vs edits)](#files-creates-vs-edits) — both edits, no new files
- [Implementation](#implementation) — field ownership, the leaf rule, and the per-plan render
- [Tests](#tests) — what `tests/test_roadmap_view.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — stdlib docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what later steps own instead

## Why

After step 3, every design row has one label (step 1), a roadmap loads off disk into one snapshot that degrades to whatever parsed (step 2), and any id resolves to the rows that cite it (step 3) — but nothing yet reads that snapshot in the one order the format is built around: entity to constraint to component to plan. The plan's Problem statement measures the gap directly: 137 design rows across four artifacts, and the chain the format's whole design rests on is today readable only by hand-joining id lists across those four files. This step is where that reading closes.

It also closes a gap step 3 leaves open by name. `BusinessRuleRow.entity_ids` and `WorkflowRow.entity_ids` point at entities, and `EntityRow` carries no field pointing back — step 3's citation map is exactly the reverse index this needs, and the plan makes this step depend on step 3 for that reason rather than have it build a second hand-rolled traversal to answer the same question.

And it is the one view that reads a file none of the first three steps touch. `LoadedRoadmap` loads the four staged artifacts and nothing else; a plan row's `draft_seed_path` points at a fifth kind of file, which the plan's Architecture names explicitly, and step 2's own Deferred section routes reading it here by step number rather than folding it into `load_roadmap`. `parse_draft_seed_provenance` already ships in `plan_tool/roadmap_artifacts.py` — this step calls it; it writes no new parser.

## Input

This step reads three prior contracts and extends two of them in small, additive ways.

- **Step 1** supplies `resolve_id(id, index) -> Resolution`, `display_label(row, *, kind=None) -> str`, and `design_row_index: Mapping[str, tuple[DesignRowEntry, ...]]`. `resolve_id` returns only marker text (`status`, `text`, `matches`) — never the underlying row — so this step reads `design_row_index` directly wherever it needs the actual `PlanRow` / `ComponentRow` / `EntityRow` object to keep descending, and calls `resolve_id` only for the dangling/ambiguous marker text.
- **Step 2** supplies `LoadedRoadmap`: `slug`, `mode`, `directory_exists`, the four optional parsed artifacts, `absent`, `unparseable`, `design_row_index`, `removal_index`, `feedback_index`. It does **not** carry `plans_dir` — `load_roadmap(plans_dir, slug, *, mode=...)` receives it but step 2's shape never stores it, since none of step 2's own fields need it. This step is the first and only one that does, so `render_traceability_walk` takes `plans_dir` as its own second parameter rather than this step reaching back into `LoadedRoadmap` to add a field only one of the three views reads. The rejected alternative — adding `plans_dir: Path` to `LoadedRoadmap` — was considered: it would work, but it would misrepresent `LoadedRoadmap` as a thing every view needs disk access through, which is exactly what step 2's Architecture states it is not.
- **Step 3** supplies `build_citation_map(loaded) -> Mapping[str, tuple[Citation, ...]]`, where `Citation` carries `label` and `field` — the field name that carried the edge (`"entity_ids"`, `"anchor"`, …). `field` alone cannot tell a `BusinessRuleRow` citer of an entity id apart from a `WorkflowRow` or a `ComponentRow` citer of the same id, because all three use the field name `entity_ids` — and the walk needs exactly the first two, not the third. This step adds a `kind: str` field to `Citation`, populated from the citer's own `DesignRowEntry.kind` at the same point in step 3's one-pass build where the citer is already in hand — this is not a second traversal, it is one more value carried out of a pass step 3 already makes, the same kind of additive extension step 3 itself made to step 1's `Resolution` (a fifth status beside the original four). Every existing consumer of `Citation.label` / `Citation.field` is unaffected.
- **`plan_tool/roadmap_artifacts.py`'s plan/ordering/component/entity shapes** — `PlanRow` (`id`, `title`, `disposition`, `component_ids`, `draft_seed_path`, `sizing_rationale`), `OrderingEntry` (`plan_id`, `depends_on`, `assumption_targets`), `AssumptionRow` (`id`, `statement`, `consuming_plan_ids`), `ComponentRow` (`id`, `name`, `entity_ids`, `pattern_ids`, `constraint_ids`), `EntityRow` (`id`, `name`, `fields`), `FieldRow` (`name`, `type`, `entity_id`), `PatternRow` (`id`, `name`, `statement` — no reference field of its own), `ConstraintRow` (`id`, `statement`, `attribute`, `anchor_ids`). All frozen, all already read by step 1's index builders; this step reads the same objects for their own field values rather than only their ids.
- **`resolve_draft_seed_path(plans_dir, slug, draft_seed_path) -> Path`** and **`parse_draft_seed_provenance(text) -> DraftSeedProvenance`**, both already shipped in `plan_tool/roadmap_artifacts.py`. `_parse_plan_rows` already runs `_validate_draft_seed_path` on every `PlanRow.draft_seed_path` at parse time, so `resolve_draft_seed_path` cannot raise `RoadmapArtifactError` for any `PlanRow` that came out of a successfully parsed `PlansArtifact` — the only two failure states left to handle are the file not existing and the file existing but failing `parse_draft_seed_provenance`.

## Files (creates vs edits)

- **New files:** none. Step 1 creates both files this step touches.
- **Existing files (edits only):**
  - `plan_tool/roadmap_view.py` — adds `render_traceability_walk`, its private per-plan/per-component/per-entity helpers, the draft-seed-reading helper, and the `kind` field on step 3's `Citation` record.
  - `tests/test_roadmap_view.py` — adds the test functions in § Tests, and edits one inherited test (named below) whose assertion this step's seed read genuinely changes.

## Implementation

**Field ownership: this step is responsible for 5 of the plan's seventeen reference fields, each with a stated disposition.** Step 3 owns eleven (the citation map, including `AssumptionRow.consuming_plan_ids` — see below); the reverse index (step 3's own render) owns `RemovalRecord.removed_id`'s appearance as a tombstone label. That leaves this step:

- `FieldRow.entity_id` — disposition (a): resolved to a label, printed beside the field that carries it, and not expanded further.
- `OrderingEntry.depends_on` — disposition (a): resolved to a label per id, in the order the field lists them.
- `OrderingEntry.assumption_targets` — disposition (a): resolved to a label per id, same order rule as `depends_on`. **It resolves to a `PlanRow`, never an `AssumptionRow`** — `ROADMAP_FORMAT.md`'s own comment on the field is "Plan ids this entry's ordering-level assumptions bear on," and `check_plan_ordering_totality` validates every entry against the roadmap's plan ids, exactly as it does for `depends_on`. There is no field on `OrderingEntry` that names an `AssumptionRow`.
- `OrderingEntry.plan_id` — disposition (a) when it names a real plan row (the join key that puts the entry in ordering-sequence position, not a separate `resolve_id` call) and disposition (b) when it does not: rendered with `resolve_id`'s own dangling text at that position in the sequence, per the plan's "marked like any other dangling id."
- `DraftSeedProvenance.roadmap_components` — disposition (b): printed as the literal ids the seed declares, never run through `resolve_id` / `display_label`. The plan's own words are "prints provenance without resolving it" — checking those ids against the plan row's own `component_ids` is `check_draft_seed_provenance`'s job as a build-time gate, and re-doing that check here would make this view a second enforcement channel, which § Out of scope refuses.

**`AssumptionRow.consuming_plan_ids` is step 3's field, not this step's** — the sixth field this step's own detail once (wrongly) claimed to own. The only field connecting an assumption to a plan is `consuming_plan_ids` itself, in the opposite direction from `assumption_targets`: an assumption names the plans it bears on, nothing on `OrderingEntry` names an assumption. Step 3's citation map computes the edge (an `AssumptionRow` is a citer of every plan id in its own `consuming_plan_ids`); this step reaches it the same way it already reaches an entity's governing business rules and workflows — a reverse query into the citation map, not a second lookup mechanism. See the per-plan render order below.

**Two small, additive extensions to shipped types, both explained above under Input — no other type changes.** `Citation` gains `kind`; the walk's entry point takes `plans_dir` as an explicit second parameter rather than widening `LoadedRoadmap`.

**The core traversal rule: a reference either continues the walk or is a leaf, and nothing in between.** For any reference field (a component id, an entity id, a pattern id, a constraint id), look it up in `loaded.design_row_index`:

```
entries = loaded.design_row_index.get(ref_id, ())
if len(entries) == 1:
    row, kind = entries[0].row, entries[0].kind
    # print display_label(row, kind=kind); continue the walk into row's own fields
else:
    # print resolve_id(ref_id, loaded.design_row_index).text  (dangling or ambiguous)
    # this reference is a leaf — do not guess which of an ambiguous match to follow
```

This is the one rule applied uniformly at every hop: `plan.component_ids` into components, `component.entity_ids` into entities, and the four walk-owned reference fields above (which resolve to a label and go no further, by design — they are named inline per the plan's Architecture, not new branches of the chain). It is also why an ambiguous entity id never reaches the business-rule/workflow lookup below: that lookup only runs for an entity that resolved to exactly one row, so the citation map is only ever queried with an unambiguous key.

**Plans render in `ordering` sequence; a plan row absent from `ordering` renders after it, a dangling `ordering` entry renders in place, and a `plan_id` repeated across two `ordering` entries renders in place only the first time.** Build `plan_by_id = {plan.id: plan for plan in loaded.plans.plans}` once (`loaded.plans` may be `None` — see the partial-load note below). Walk `loaded.plans.ordering` in order, tracking a `rendered: set[str]` of plan ids already rendered: for each entry, if `entry.plan_id` is in `rendered`, print a duplicate marker in place (one way: `f"⚠ duplicate ordering entry: {display_label(plan_by_id[entry.plan_id])}"`) and move on — this is `VIOLATION_ORDERING_PLAN_ID_DUPLICATE`'s own case, `check_plan_ordering_totality`'s third anomaly beside the other two this paragraph already names, and it needs the same visible treatment they get rather than a silent second render of the whole plan; if `entry.plan_id` is in `plan_by_id` and not yet in `rendered`, render that plan (see below) at this position and add its id to `rendered`; if it is in neither, print `resolve_id(entry.plan_id, loaded.design_row_index).text` in place and move on — reusing the existing dangling marker rather than inventing a second one, per the plan's own instruction. After the sequence, walk `loaded.plans.plans` in its own source order and render any plan whose id never entered `rendered`, each marked as not scheduled (one way: `f"⚠ not in ordering: {display_label(plan)}"` — the plan's Architecture fixes the wording for the seed markers below but leaves this one open; any clearly-marked, `⚠`-prefixed text that names the plan is fine).

**Per plan, in this order — depends_on and assumption_targets first, the assumptions that name this plan next, the component chain after that, the draft seed last:**

- `depends_on` and `assumption_targets` from the plan's `ordering` entry (empty for an unordered plan, since it has none), each id resolved per the leaf/continue rule above — both plan-id-valued, both leaves, identical treatment. Neither ever reaches an `AssumptionRow`: `assumption_targets` names a plan an ordering-level assumption bears on, not the assumption itself.
- The assumptions that name *this* plan, reached the same way the entity section below reaches an entity's governing business rules and workflows: `citation_map.get(plan.id, ())` filtered to `citer.kind == "assumption"`, in the citation map's own stage-then-source order, printing each citer's `label` (an `AssumptionRow`'s `.statement`, via step 1's `display_label`). This is what makes `AssumptionRow.consuming_plan_ids` visible "here rather than left to the reverse index" without this step needing to walk `loaded.plans.assumptions` itself or invent a second reverse-lookup mechanism beside the one step 3 already built for entities.
- `component_ids`, each resolved per the leaf/continue rule. A dangling or ambiguous component id is a leaf (its marker prints, nothing more). A uniquely-resolved `ComponentRow` opens three sub-lists, each in the row's own field order:
  - `entity_ids` — each resolved per the leaf/continue rule; a uniquely-resolved `EntityRow` prints:
    - the entity's own label;
    - the business rules and workflows that govern it — `citation_map.get(entity_id, ())` filtered to `citer.kind in ("business rule", "workflow")`, in the citation map's own stage-then-source order. Print each citer's `label` only; do not also resolve or print that business rule's or workflow's own `entity_ids` — doing so re-enters entities the current component does not own and has no place in the plan's stated chain.
    - each `FieldRow` in `entity.fields` whose `type` is a reference type: `field.name` plus `resolve_id(field.entity_id, ...)`'s result. Print the target's label only — never re-render the target entity's own governs-list or fields, which would let an entity-to-entity reference cycle turn one plan's walk into an unbounded one.
  - `pattern_ids` — each resolved per the leaf/continue rule; a pattern is always a leaf (`PatternRow` carries no reference field of its own), and its label already carries its scope (`system pattern:` / `component pattern:`) from step 1's `display_label`, using the `kind` the index entry already carries.
  - `constraint_ids` — each resolved per the leaf/continue rule; always a leaf here, per the plan's "constraints are a leaf" rule — the walk never continues from a constraint's own `anchor_ids`.
  - An empty `entity_ids` / `pattern_ids` / `constraint_ids` — including on a `PlanDisposition.CROSS_CUTTING` plan with no `component_ids` at all — prints an explicit "none" line rather than omitting the sub-list, mirroring step 3's reverse index, which states "nothing cites this" rather than dropping a zero-citer id silently. This is what keeps an empty list from reading as a defect.
- The draft seed, read directly off disk — the one place this module reads a file outside the four `load_*_artifact` functions:

```
source = resolve_draft_seed_path(plans_dir, loaded.slug, plan.draft_seed_path)
if not source.is_file():
    # print f"⚠ missing draft seed: {plan.draft_seed_path}"
else:
    try:
        provenance = parse_draft_seed_provenance(source.read_text(encoding="utf-8"))
    except RoadmapArtifactError:
        # print f"⚠ unparseable draft seed: {plan.draft_seed_path}"
    else:
        # print plan.draft_seed_path, then provenance.roadmap_components as literal ids
```

Both marker strings are fixed by the plan's Architecture verbatim; print `plan.draft_seed_path` (the relative string already on the row), never the resolved absolute `Path`, in either the success case or the two markers — the module has no `repo_root` to shorten an absolute path against, and the relative string is what the artifact itself declares.

**A partly-loaded roadmap degrades for free, with no per-artifact branch inside this step's own code.** If `loaded.plans` is `None`, the plan-by-plan section is simply empty — the header and absent/unparseable notice (below) already say why, so no extra marker belongs inside the body. If `loaded.domain` or `loaded.components` is `None`, every entity or component id any plan names resolves dangling through the same `design_row_index` lookup every other hop already uses, because `design_row_index` only ever contains ids from the artifacts that parsed (step 1's own guarantee). This step adds no absence handling of its own beyond what step 1 and step 2 already provide.

**The walk's content never depends on `mode`.** It reads `loaded.domain` / `loaded.constraints` / `loaded.components` / `loaded.plans` and `loaded.design_row_index` only — never `loaded.feedback_index`, `loaded.removal_index`, or `loaded.mode`, except to print the render's own header line. This is what makes the walk's body the same under both modes, per the plan's "deliberately mode-invariant" rule; the only difference between a `current`-mode and a `review`-mode render of the same roadmap is the header line naming the mode.

**Reuse step 3's header and absent/unparseable notice rather than re-deriving them.** Step 3's own Implementation names these as private helpers taking only `LoadedRoadmap`, explicitly recommended for reuse by later steps. Call them here; do not write a second version of either.

## Tests

`tests/test_roadmap_view.py`, extending steps 1–3's suite. Fixtures follow step 2's and step 3's pattern — real artifact dataclasses rendered through the shipped `render_*_artifact` functions and loaded via `load_roadmap`, plus, new to this step, real seed files written under `resolve_draft_seed_path(tmp_path, slug, plan.draft_seed_path)` using `render_draft_seed_provenance` for the parseable cases.

### Tests for this step

- `test_walk_orders_plans_by_ordering_sequence` — plans render in `ordering` order, not `plans` source order.
- `test_walk_appends_unordered_plan_row_after_the_sequence` — a plan row absent from `ordering` renders after the sequence, marked distinctly from an ordered plan.
- `test_walk_marks_ordering_entry_naming_no_plan_row_as_dangling` — an `ordering` entry with no matching plan row renders `resolve_id`'s own dangling text at its position.
- `test_walk_marks_repeated_ordering_entry_as_duplicate_not_a_second_render` — two `ordering` entries naming the same `plan_id` render that plan's full chain once, at the first position, and a duplicate marker (not a second full render) at the second — the third `check_plan_ordering_totality` anomaly, beside the unordered-row and dangling-entry cases above.
- `test_walk_resolves_component_ids_and_opens_their_entity_pattern_constraint_lists` — a uniquely-resolved component prints its label and all three sub-lists.
- `test_walk_finds_governing_business_rules_and_workflows_for_an_entity` — a `BusinessRuleRow` and a `WorkflowRow` both citing one entity id both appear under that entity, via the citation map's new `kind` field.
- `test_walk_excludes_non_governing_citers_from_the_entity_section` — a `ComponentRow`, a `ConstraintRow`, and a `DecisionRow` that also cite the same entity id do not appear in that entity's governs list.
- `test_walk_resolves_pattern_ids_naming_scope` — a system pattern and a component pattern sharing one `name`, cited by the same component, render distinguishably.
- `test_walk_resolves_constraint_ids_as_leaves` — a resolved constraint's own `anchor_ids` never appear anywhere in the walk's output.
- `test_walk_prints_field_row_entity_id_target_without_expanding_it` — an entity's `REFERENCE`-type field resolves to the target entity's label, and the target's own governs-list and fields are not re-rendered.
- `test_walk_prints_depends_on_and_assumption_targets_resolved` — an ordered plan's `depends_on` and `assumption_targets` render as resolved *plan* labels in field order — pinning that `assumption_targets` never resolves to an `AssumptionRow`.
- `test_walk_prints_assumptions_naming_this_plan_via_the_citation_map` — an `AssumptionRow` naming this plan in its own `consuming_plan_ids` appears in the plan's rendered section, reached through `citation_map.get(plan.id, ())` filtered to `kind == "assumption"` — the reverse-lookup replacement for the removed (and incorrect) `assumption_targets`-to-`AssumptionRow` chain.
- `test_walk_dangling_and_ambiguous_references_are_leaves` (parametrized over a component id, an entity id, and a pattern id) — each renders its marker and opens no sub-list.
- `test_walk_prints_seed_path_and_provenance_for_a_resolved_seed` — a plan whose seed file parses prints `draft_seed_path` plus its `roadmap_components` as literal, unresolved ids.
- `test_walk_names_a_missing_draft_seed` — a plan whose seed file does not exist renders `⚠ missing draft seed: {draft_seed_path}`, and every other plan's walk in the same render is unaffected.
- `test_walk_names_an_unparseable_draft_seed` — a plan whose seed file exists but fails `parse_draft_seed_provenance` renders `⚠ unparseable draft seed: {draft_seed_path}`, distinct from the missing case.
- `test_walk_cross_cutting_plan_with_no_components_renders_an_explicit_empty_list` — a `CROSS_CUTTING` plan with `component_ids == ()` renders a stated "none," not a dangling marker and not a crash.
- `test_walk_body_is_the_same_under_both_modes` — the identical fixture, carrying feedback and a removal, rendered under `mode="current"` and `mode="review"` produces the same body below the header line.
- `test_walk_render_is_the_same_on_repeat_calls` — rendering the same `LoadedRoadmap` twice produces the same text.
- `test_walk_render_names_its_mode_and_the_absent_unparseable_files` — the rendered text states its mode and, once before the walk's own output, the artifacts `loaded.absent` / `loaded.unparseable` name.
- `test_walk_on_a_partial_roadmap_resolves_every_reference_as_dangling` — a domain-only roadmap's walk (built from a `plans` fixture naming components and entities that were never loaded) renders every component/entity id dangling, with no exception.
- `test_citation_carries_the_citer_kind` — a `Citation` returned by `build_citation_map` exposes `kind` matching the citer's own `DesignRowEntry.kind`, the foundation the entity-governs filter depends on.
- `test_module_reads_disk_only_through_the_artifact_loaders_and_the_draft_seed_read` — replaces step 2/3's `test_module_reads_only_through_the_artifact_loaders`: the module's only direct `read_text` call outside the four `load_*_artifact` functions is the one in this step's draft-seed-reading helper, with a corrected docstring naming both.
- `test_module_imports_only_the_artifact_and_gates_leaves` — unchanged from step 1; stays green, since this step adds no new first-party import.

Every test above is green before this step is considered finished.

## Acceptance criteria

- Each of the five reference fields this step owns (`FieldRow.entity_id`, `OrderingEntry.depends_on`, `OrderingEntry.assumption_targets`, `OrderingEntry.plan_id`, `DraftSeedProvenance.roadmap_components`) renders with the disposition named in Implementation, and no other field's disposition changes. `AssumptionRow.consuming_plan_ids` is step 3's field; this step reaches it only through the citation map, never directly.
- `assumption_targets` resolves to a `PlanRow` label, exactly like `depends_on`, and never to an `AssumptionRow`; the assumptions naming a given plan render in that plan's own section, sourced from `citation_map.get(plan.id, ())` filtered to `kind == "assumption"`.
- The walk emits plans in `ordering` sequence; a plan row absent from `ordering` renders after that sequence, marked distinctly; an `ordering` entry naming no plan row renders `resolve_id`'s own dangling text at its position; an `ordering` entry repeating a `plan_id` already rendered renders a duplicate marker in place, not a second full render of that plan.
- Every component, entity, pattern, and constraint reference resolves through `loaded.design_row_index`: a unique match continues the walk into that row, and a dangling or ambiguous match is a leaf — its marker prints and nothing beneath it renders.
- An entity reached through a component's `entity_ids` shows exactly the business rules and workflows citing it, via the citation map's `kind` field — never a component, constraint, or decision that cites the same id.
- An entity's `REFERENCE`-type field resolves its target to a label and does not re-render that target's own governs-list or fields.
- A resolved seed prints `draft_seed_path` and its `roadmap_components` as literal ids, never run through `resolve_id`; a missing seed prints `⚠ missing draft seed: <path>`; an unparseable seed prints `⚠ unparseable draft seed: <path>`; either marker leaves the rest of that plan's walk, and every other plan's walk, unaffected.
- A `CROSS_CUTTING` plan with no `component_ids`, or any component with an empty `entity_ids` / `pattern_ids` / `constraint_ids`, renders an explicit empty statement rather than a marker or an omission.
- The walk's rendered body is the same, byte for byte, under `mode="current"` and `mode="review"` for the same artifacts, differing only in the header line naming the mode; the same `LoadedRoadmap` rendered twice produces the same text.
- A domain-only (or otherwise partial) roadmap's walk renders every reference an absent artifact would have defined as dangling, with no exception raised.
- The module's only first-party imports remain `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`; the only direct `read_text` call in the module outside the four `load_*_artifact` functions is this step's draft-seed read, scoped to a path built by `resolve_draft_seed_path`.
- `plan-tool validate` and the full existing roadmap suite (`tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`, `tests/test_roadmap.py`, `tests/test_roadmap_format.py`) stay green.

## References

- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for the `kind` field added to `Citation`, matching every other roadmap-view type's shape.
- [pathlib — Object-oriented filesystem paths (Python 3 docs)](https://docs.python.org/3/library/pathlib.html) — `Path.is_file()` ahead of the one direct `read_text()` call this step adds, mirroring `apply_roadmap_seeds`'s own existence check before reading a draft seed.
- [textwrap — Text wrapping and filling (Python 3 docs)](https://docs.python.org/3/library/textwrap.html) — `indent()` for nesting the component/entity/pattern/constraint levels under each plan as stable indented text, and for dedenting expected output in fixtures.
- [string — Format Specification Mini-Language (Python 3 docs)](https://docs.python.org/3/library/string.html#format-specification-mini-language) — alignment and width specifiers for keeping the walk's nested lines stable across runs.

## Applicable guardrails

- **The one-way import chain (plan's Architecture, "Placement preserves the one-way chain").** This step adds no new first-party import; `resolve_draft_seed_path` and `parse_draft_seed_provenance` both come from the already-imported `plan_tool.roadmap_artifacts`.
- **The gates import stays narrow (plan's Architecture, "Why the gates import").** This step adds no new `roadmap_gates` symbol; it reaches `design_row_ids` only indirectly, through the already-built `design_row_index`.
- **No new parser (plan's Architecture, closing paragraph).** This step calls `parse_draft_seed_provenance` as shipped; it adds no parsing logic of its own for the seed's frontmatter.
- **Constraints are a leaf (plan's Architecture, walk description).** A resolved `ConstraintRow`'s own `anchor_ids` never drive further traversal in this step's code.
- **`roadmap_components` is disposition (b), never re-validated (plan's Architecture and Out of scope, "second enforcement channel").** This step prints a seed's `roadmap_components` as literal ids; it never cross-checks them against the owning plan's `component_ids` — that stays `check_draft_seed_provenance`'s job.
- **The walk is mode-invariant in content (plan's Architecture, "The traceability walk's content is mode-invariant, deliberately").** This step's rendering code reads `loaded.domain` / `constraints` / `components` / `plans` / `design_row_index`, and the citation map built from them — never `loaded.feedback_index`, `loaded.removal_index`, or `loaded.mode`, except for the shared header line.
- **No standalone removals section, in any view (plan's Out of scope, and its 2026-08-07 narrowing).** The walk touches no removal or feedback content at all, by the mode-invariance rule above, which is the strongest form of that fence this step could apply.
- **Not a second enforcement channel (plan's Out of scope).** Every dangling, ambiguous, missing-seed, and unparseable-seed marker this step renders is a rendering annotation; none of them raises, and none carries a severity or blocking field.
- **Machine-readable output stays out of scope (plan's Out of scope).** `render_traceability_walk` returns plain text; this step adds no `--json` form.
- **Every list has a stated order (plan's Architecture).** Plans follow `ordering`, with the unordered group in `plans` source order; every reference field's own sub-list preserves that field's own tuple order, including a duplicated id, rather than sorting or deduplicating.

## Deferred

- **The reverse index and its own `--view index` rendering** — step 3's deliverable; this step only adds a `kind` field to `Citation` and calls `build_citation_map` for its one reverse hop.
- **The decision ledger, its settled/pending grouping, and rendering a removal beside a pending feedback row** — step 5; this step renders no `DecisionRow`, `FeedbackRow`, or `RemovalRecord` at all.
- **CLI wiring (`--view`, `--mode`, `--id`) and the exit-code mapping** — step 6; `render_traceability_walk` is not called from anywhere yet.
- **The doc sweep and `CAPABILITIES.md` update** — step 7.
- **Draft-seed body content** — the plan's Out of scope: this step's seed handling stops at the path and the provenance frontmatter; it never opens the seed's prose.
- **Mermaid or other graph output** — the plan's Out of scope; this step's walk stays plain text.
