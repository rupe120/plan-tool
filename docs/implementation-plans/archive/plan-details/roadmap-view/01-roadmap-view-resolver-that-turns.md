> **Auto-archived**: this plan was swept on 2026-08-10 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the roadmap_view resolver that turns a roadmap id into the row it names

## Summary

Add `plan_tool/roadmap_view.py`, a new read-only leaf that turns a bare roadmap
id into a human-readable label for the row it names, and reports the two ways
that can fail (the id names nothing, or it names more than one row) without
raising. It builds one roadmap-wide index of design-row ids — sourced from
`roadmap_gates.design_row_ids` per artifact, never re-derived — and a separate
index of `RemovalRecord`s, then exposes `resolve_id` for an ordinary
cross-reference and `resolve_feedback_target` for a `FeedbackTarget`, which
alone may resolve through a removal or bear on the whole artifact. The key
decision is putting exactly one display-label rule per row kind here, so the
three views steps 3–5 add later never invent their own. On green, every one of
the eleven row kinds a roadmap id can name has a resolver-owned label, and a
dangling or ambiguous id renders as a visible, structured outcome instead of a
crash, a silent drop, or a false positive on the review loop's own success
path.

## Table of Contents

- [Why](#why) — the gap this module closes and the two false positives it exists to prevent
- [Input](#input) — the two existing contracts this step reads and builds on
- [Files (creates vs edits)](#files-creates-vs-edits) — the two new files
- [Implementation](#implementation) — the index, the label rule, and the resolve functions
- [Tests](#tests) — what `tests/test_roadmap_view.py` covers
- [Acceptance criteria](#acceptance-criteria) — observable behavior on green
- [References](#references) — stdlib docs for the pieces this step uses
- [Applicable guardrails](#applicable-guardrails) — the plan-level fences this step's code must respect
- [Deferred](#deferred) — what later steps own instead

## Why

Every cross-row reference in a roadmap — the seventeen fields § Problem
statement of the plan enumerates, from `FieldRow.entity_id` to
`DraftSeedProvenance.roadmap_components` — is today a bare id in YAML. Nothing
in `plan_tool/roadmap_artifacts.py` or `plan_tool/roadmap_gates.py` turns one
into the row it names: the gates return `Violation` records that block a
stage, and the parser rejects nothing a resolver would need to walk around.
Three renderers are about to be built on top of this (steps 3–5); without one
shared place to turn an id into a label, each would invent its own rule for
the same eleven row kinds, and the two false positives named in the plan's
Risks — a resolver that ignores the `design rows ∪ removals` union on a
feedback target, or one that does not branch on `FeedbackTarget.kind` before
looking anything up — would each need catching three times instead of once.

The uniqueness contract this step must inherit already exists and has already
been gotten right once: `plan_tool.roadmap_gates.check_duplicate_row_ids`
scopes id uniqueness to the whole roadmap, not one artifact, and
`plan_tool/roadmap.py:_check_predecessor_review_rows` already resolves a
feedback target against exactly `design_row_ids(artifact) | {removed_id for
removal in artifact.removals}` — the orchestrator's own predecessor pre-flight,
run before this plan existed. This step gives that same formula a public,
read-only home so a hand-edited roadmap — the normal case these views exist to
read — resolves the same way whether the orchestrator or a view is asking.

## Input

This step is the first to touch the roadmap artifact contract from a new
consumer angle (a resolver, not a stage or a gate), so it reads two existing
surfaces whose shape drives correctness here:

- **The row dataclasses in `plan_tool/roadmap_artifacts.py`** — `EntityRow`,
  `BusinessRuleRow`, `WorkflowRow`, `DecisionRow`, `AttributeDispositionRow`,
  `ConstraintRow`, `PatternRow`, `ComponentRow`, `PlanRow`, `AssumptionRow`,
  `FeedbackRow`, `FeedbackTarget`, `RemovalRecord`, and the four artifact
  containers (`DomainArtifact`, `ConstraintsArtifact`, `ComponentsArtifact`,
  `PlansArtifact`). All are frozen dataclasses; every row collection is an
  **ordered tuple, not a dict keyed by id** (`ROADMAP_FORMAT.md`: "so a
  duplicate id survives parsing"), which is what makes a genuinely ambiguous
  id observable here instead of silently collapsed before this module ever
  sees it.
- **`roadmap_gates.design_row_ids(artifact) -> set[str]`** — the authoritative
  membership function for "which ids does this one artifact declare as a
  design row." It is deliberately public for this exact reuse (its own
  docstring: "two implementations would drift the first time either artifact
  gains a collection"). Its limit: it returns **ids only**, never the row
  object a label needs, and it takes one artifact at a time, never the whole
  roadmap — this step still has to walk each artifact's own row collections to
  get the objects, and the walk's resulting id set is what step-1's own tests
  hold to `design_row_ids(artifact)` rather than trusting by inspection.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/roadmap_view.py` — the resolver: the roadmap-wide design-row
    index, the removal index, the one-label-per-row-kind rule, and the two
    resolve functions.
  - `tests/test_roadmap_view.py` — mirrors the module; fixtures build the row
    dataclasses directly rather than parsing YAML text, matching
    `tests/test_roadmap_gates.py`'s stated fixture policy.
- **Existing files (edits only):** none. This step has no `depends_on` and
  nothing yet imports `plan_tool.roadmap_view` (that starts at step 6), so no
  other file changes.

## Implementation

**Shape the module as a leaf directly above the two it reads, mirroring
`plan_tool/roadmap_gates.py`'s own docstring convention** ("A stdlib-plus-one
leaf: the only first-party import is `plan_tool.roadmap_artifacts`"). This
step's module imports `plan_tool.roadmap_artifacts` **and**
`plan_tool.roadmap_gates` and nothing else first-party — see § Applicable
guardrails for why the gates import stays narrow.

**Build one roadmap-wide index of design rows, keyed for ambiguity, not
identity.** A reasonable shape:

- A small frozen dataclass — e.g. `DesignRowEntry(kind: str, id: str,
  artifact: str, row: object)` — pairing a row object with the kind label and
  the filename constant (`DOMAIN_FILENAME` / `CONSTRAINTS_FILENAME` /
  `COMPONENTS_FILENAME` / `PLANS_FILENAME`) it came from. `kind` carries the
  same label strings `roadmap_gates._domain_rows` / `_constraints_rows` /
  `roadmap_artifacts.components_design_rows` / `plans_design_rows` already use
  ("entity", "business rule", "workflow", "decision", "disposition",
  "constraint", "system pattern", "component pattern", "component", "plan",
  "assumption") — reusing that exact vocabulary is what lets `kind` double as
  the scope tag `PatternRow` needs (see the label rule below), and keeps this
  module's messages consistent with the gates' own.
- A builder — e.g. `build_design_row_index(*, domain=None, constraints=None,
  components=None, plans=None) -> Mapping[str, tuple[DesignRowEntry, ...]]` —
  that walks whichever of the four artifacts it is given (**every parameter
  optional, unlike `ArtifactEnvelope.domain`**; see § Applicable guardrails)
  in stage order (domain, constraints, components, plans), each artifact in
  its own declared row order (mirroring `roadmap_gates._domain_rows` /
  `_constraints_rows`'s field order, and `components_design_rows` /
  `plans_design_rows` directly), appending each row into a
  `collections.defaultdict(list)` keyed by id. One pass in stage order is what
  makes an ambiguous id's matches come out in the plan's stated render order
  for free, with no separate sort step.
- Because this walk enumerates the same collections `design_row_ids` does, its
  resulting id set for one artifact should equal `design_row_ids(artifact)` —
  that equality is what the tests in § Tests pin directly against the
  imported function, per the plan's own testing instruction, rather than
  trusted by construction alone.
- A **duplicate id one row declares twice does not create ambiguity by
  itself** — parsing already collapses within-row duplication elsewhere; what
  this index must catch is the cross-row and cross-artifact case
  `check_duplicate_row_ids` also catches: two distinct rows (in one artifact
  or across several) declaring the same id land as two entries under one key.

**A parallel, separate index for removals — never folded into the design-row
index.** `current` mode must resolve no removal at all (§ Architecture), so
mixing the two would make an ordinary `resolve_id` call quietter about
ambiguity than it should be and would leak removals into every caller instead
of the one that is allowed to see them. A matching builder — e.g.
`build_removal_index(*, domain=None, constraints=None, components=None,
plans=None) -> Mapping[str, tuple[RemovalRecord, ...]]` — flattens each
artifact's `.removals` tuple (a plain field, not `getattr`-guarded — all four
artifact types declare it) into a `collections.defaultdict(list)` keyed by
`removed_id`, in stage order, the same shape as `build_design_row_index`.
**A colliding `removed_id` is exactly as reachable as a colliding design-row
id, so it gets the same treatment.** Nothing in `roadmap_gates.py` enforces
`removed_id` uniqueness the way `check_duplicate_row_ids` enforces it for
live design rows, and `build_removal_index` walks the same kind of
undeduplicated, hand-editable collection `build_design_row_index` does — a
single-record-per-key mapping would silently let one `RemovalRecord`
overwrite another with no marker, which is precisely the silent-collapse this
plan's ambiguous-id rule exists to prevent for every other id space it
touches. Keying by a tuple carries the collision forward instead of hiding
it; the two functions that consume this index (below) decide what "more than
one match" means for their own caller.

**One display label per row kind, fixed here.** A dispatch function — e.g.
`display_label(row, *, kind: Optional[str] = None) -> str` — covering all
eleven row kinds per the plan's Architecture section, verbatim:

- `EntityRow` / `WorkflowRow` / `ComponentRow` → `.name`
- `BusinessRuleRow` / `ConstraintRow` / `AssumptionRow` → `.statement`
- `PlanRow` → `.title`
- `DecisionRow` → `.chosen_option`
- `FeedbackRow` → `.request`
- `AttributeDispositionRow` → `.attribute` and `.disposition` together (one
  way: `f"{row.attribute}: {row.disposition.value}"`) — use `.value` on the
  `ConstraintDisposition` member, not the member or an f-string of it
  directly, since a `str`-mixin `Enum`'s own `__str__`/`__format__` is not
  guaranteed to be its plain value (the same hazard `parser.py`'s
  `_coerce_enums` docstring already warns about for YAML dumping).
- `PatternRow` → **needs its scope, which the row itself does not carry** —
  the `kind` label passed in (`"system pattern"` or `"component pattern"`,
  exactly as `build_design_row_index` already tags it) is what disambiguates;
  calling `display_label` on a bare `PatternRow` with no `kind` is a caller
  bug and should raise rather than silently default to one scope, since a
  silent default would reproduce the exact ambiguity this step exists to
  remove.
- `RemovalRecord` → `.removed_id` and `.rationale` together, worded so it
  reads as a **tombstone, not a resolved row** (one way: `f"removed:
  {row.removed_id} — {row.rationale}"`) — it must never claim to be, or read
  like, a normal resolved label, since nothing recovers what the row said.

**Two resolve functions, not one, because only a feedback target may cross
into the removals index.**

- `resolve_id(id: str, index) -> Resolution` — looks `id` up in the
  design-row index only. Zero matches is `dangling`; exactly one is
  `resolved`, with the text set to that match's `display_label(...)`; more
  than one is `ambiguous`, carrying every match's label so the caller can
  name each one.
- `resolve_feedback_target(target: FeedbackTarget, index, removals) ->
  Resolution` — branches on `target.kind` **before** any lookup:
  `FeedbackTargetKind.ARTIFACT` returns `artifact-scope` outright (there is no
  `row_id` to resolve, by parse-time construction); `FeedbackTargetKind.ROW`
  tries `resolve_id(target.row_id, index)` first, and only on a `dangling`
  result falls back to `removals.get(target.row_id, ())`. Zero matches stays
  `dangling`; exactly one resolves (via `display_label` on the matched
  `RemovalRecord`, the tombstone label above); **more than one — a colliding
  `removed_id` — is `ambiguous`, carrying every match's tombstone label in
  `matches`**, the same three-way split `resolve_id` already applies to a
  colliding design-row id, reusing `RESOLUTION_AMBIGUOUS` rather than a
  removals-specific status. This is the one place this step reproduces
  `plan_tool/roadmap.py:_check_predecessor_review_rows`'s `design_row_ids(artifact)
  | {removed_id for removal in artifact.removals}` formula — mirrored, not
  imported (that function is private orchestrator code, and importing
  `plan_tool.roadmap` from this leaf would break the one-way chain); the
  formula itself only ever tests membership, so it is silent on what this
  step must decide for itself: what a duplicate `removed_id` renders as.

**One result type for every outcome**, in the style of `Violation` /
`JiraGradeFinding` (a frozen dataclass, plus module-level status constants
rather than a bare string literal at each call site) — one way: `Resolution(
status: str, text: str, matches: tuple[str, ...] = ())` with
`RESOLUTION_RESOLVED`, `RESOLUTION_DANGLING`, `RESOLUTION_AMBIGUOUS`,
`RESOLUTION_ARTIFACT_SCOPE` as the four values `status` takes. `text` is
**already the ready-to-print string** for every status — the resolved label,
or the literal marker text `"⚠ undefined: {id}"` / `"⚠ ambiguous: {id}"` —
so steps 3–5 interpolate `text` uniformly and never re-derive the marker
wording themselves (the plan's own words: "so no renderer invents its own
rule"). `matches` is populated only for `ambiguous`, one label per matched
row, in the index's stage-then-source order.

**What this step deliberately does not raise on.** Every path through
`resolve_id` and `resolve_feedback_target` returns a `Resolution` — a
dangling id, an ambiguous id, and an out-of-place `FeedbackTargetKind.ARTIFACT`
row are not exceptions here, matching the plan's "rendering annotation, not a
finding" framing. The only place this module should raise is the
`display_label` caller-bug case above (a `PatternRow` with no `kind`), which
is a programming error in a later step's code, not a property of the roadmap
on disk.

## Tests

`tests/test_roadmap_view.py`, built on row dataclasses constructed directly
(no YAML parsing), per the fixture policy `tests/test_roadmap_gates.py`
states for itself. Prefer one parametrized case per rule, per the plan's
Testing section, so a twelfth row kind or a new resolver outcome fails an
existing test instead of silently passing an under-specified one.

### Tests for this step

- `test_display_label_by_row_kind` (parametrized over all eleven kinds) —
  asserts each row kind's label reads from the field § Architecture names,
  covering `EntityRow`, `WorkflowRow`, `ComponentRow`, `BusinessRuleRow`,
  `ConstraintRow`, `AssumptionRow`, `PlanRow`, `DecisionRow`, `FeedbackRow`,
  `AttributeDispositionRow`, and both `PatternRow` scopes.
- `test_pattern_label_names_its_scope` — a system pattern and a component
  pattern sharing one `name` produce two distinguishable labels.
- `test_pattern_label_without_kind_raises` — `display_label` on a bare
  `PatternRow` with no `kind` argument raises rather than guessing a scope.
- `test_disposition_label_uses_the_plain_value` — asserts the
  `ConstraintDisposition` half of the label is the plain string (`"prioritized"`
  etc.), not an enum repr.
- `test_removal_label_reads_as_a_tombstone` — asserts the `RemovalRecord`
  label names the id and the rationale and is structurally distinct from a
  resolved row's label (so a later change that starts inventing a label from
  the id would fail this).
- `test_build_design_row_index_matches_design_row_ids` (parametrized over the
  four artifact types) — for a hand-built artifact of each type, the index's
  id set for that artifact equals `roadmap_gates.design_row_ids(artifact)`,
  imported and compared directly.
- `test_build_design_row_index_tolerates_no_artifacts` — calling the builder
  with every parameter left at its default returns an empty index without
  raising (unlike `ArtifactEnvelope`, which requires `domain`).
- `test_ambiguous_matches_render_in_stage_then_source_order` — an id declared
  by rows in two different artifacts resolves ambiguous with `matches` in
  domain-before-constraints-before-components-before-plans order, matching
  the source order within each artifact that declares it more than once.
- `test_resolve_id_returns_dangling_for_an_undeclared_id` — an id absent from
  every artifact resolves `dangling`, with `text` equal to `"⚠ undefined:
  {id}"`.
- `test_resolve_id_returns_resolved_with_the_display_label` — a declared id
  resolves `resolved`, with `text` equal to that row's `display_label`.
- `test_resolve_id_returns_ambiguous_naming_every_match` — a duplicated id
  resolves `ambiguous`, with `matches` naming every row it matched and `text`
  equal to `"⚠ ambiguous: {id}"`.
- `test_resolve_feedback_target_artifact_scope_is_not_dangling` — a
  `FeedbackTarget(kind=FeedbackTargetKind.ARTIFACT)` resolves `artifact-scope`
  without ever consulting either index.
- `test_resolve_feedback_target_row_kind_resolves_against_design_rows` — a
  `ROW`-kind target naming a live design row resolves `resolved` via the
  design-row index alone.
- `test_resolve_feedback_target_through_a_removal_is_resolved_not_dangling` —
  the false-positive case named in the plan's Risks: a `ROW`-kind target
  naming an id that is absent from the design-row index but present in the
  removal index resolves `resolved` with the removal's tombstone label, never
  `dangling`.
- `test_resolve_feedback_target_unresolvable_row_id_is_dangling` — a
  `ROW`-kind target naming an id in neither index still resolves `dangling` —
  the negative case that proves the removals fallback is not a blanket
  amnesty.
- `test_build_removal_index_collects_every_record_under_a_colliding_id` — two
  distinct `RemovalRecord`s sharing one `removed_id`, across two artifacts,
  both appear under that key rather than one overwriting the other.
- `test_resolve_feedback_target_removal_collision_is_ambiguous_naming_every_tombstone`
  — a `ROW`-kind target naming a `removed_id` two `RemovalRecord`s declare
  resolves `ambiguous`, with `matches` naming every one's tombstone label —
  the removal-index analog of `test_resolve_id_returns_ambiguous_naming_every_match`.
- `test_module_imports_only_the_artifact_and_gates_leaves` — mirrors
  `tests/test_roadmap_gates.py:test_module_imports_only_the_artifact_leaf`:
  a source grep asserts the module's only first-party imports are
  `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates`, and a
  subprocess run against a stubbed `plan_tool` package asserts nothing else
  first-party loads transitively.
- `test_module_touches_no_filesystem_and_no_subprocess` — mirrors
  `tests/test_roadmap_gates.py`'s sibling test: no `open(`, `read_text`,
  `subprocess`, or `invoker` token in the module's source (disk reads are
  step 2's job).

Every test above is green before this step is considered finished.

## Acceptance criteria

- All eleven row kinds an id can name (`EntityRow`, `BusinessRuleRow`,
  `WorkflowRow`, `DecisionRow`, `AttributeDispositionRow`, `ConstraintRow`,
  `PatternRow` in both scopes, `ComponentRow`, `PlanRow`, `AssumptionRow`,
  `FeedbackRow`, plus `RemovalRecord`'s tombstone) resolve to exactly one
  label each, defined once in this module.
- A `PatternRow` label names its scope (`system pattern:` vs. `component
  pattern:`); the same `name` under each scope renders two different labels.
- The design-row index for a given artifact has exactly the id set
  `roadmap_gates.design_row_ids(artifact)` returns for that artifact.
- `resolve_id` returns `dangling` for an id no supplied artifact declares,
  `ambiguous` (naming every match) for an id more than one row declares, and
  `resolved` (with that row's label) otherwise — never raises on any of the
  three.
- `resolve_feedback_target` returns `artifact-scope` for an `ARTIFACT`-kind
  target without consulting either index, `resolved` for a `ROW`-kind target
  whose id is either a live design row or exactly one recorded removal,
  `ambiguous` (naming every tombstone) for a target naming a `removed_id`
  more than one `RemovalRecord` declares, and `dangling` only when the id is
  in neither index.
- `build_removal_index` collects every `RemovalRecord` under a colliding
  `removed_id` rather than letting one overwrite another; its return shape is
  `Mapping[str, tuple[RemovalRecord, ...]]`.
- Building either index with no artifacts supplied returns an empty index and
  does not raise.
- The module's only first-party imports are `plan_tool.roadmap_artifacts` and
  `plan_tool.roadmap_gates`; it imports no `Violation`, no `check_*` gate, and
  no `run_*_gates` aggregate from `roadmap_gates`.
- The module touches no filesystem, spawns no subprocess, and calls no
  backend.
- `plan-tool validate` and the full existing roadmap suite
  (`tests/test_roadmap_artifacts.py`, `tests/test_roadmap_gates.py`,
  `tests/test_roadmap.py`, `tests/test_roadmap_format.py`) stay green —
  this step reads both modules and writes neither.

## References

- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — `@dataclass(frozen=True)` for `DesignRowEntry` and `Resolution`, matching the shape `Violation` and `JiraGradeFinding` already use in sibling modules.
- [collections — Container datatypes (Python 3 docs)](https://docs.python.org/3/library/collections.html) — `defaultdict(list)` for building the roadmap-wide id index in one pass, so an id declared by more than one row accumulates every match instead of overwriting it.

## Applicable guardrails

- **The one-way import chain (plan's Architecture, "Placement preserves the
  one-way chain").** This module's first-party imports are exactly
  `plan_tool.roadmap_artifacts` and `plan_tool.roadmap_gates` — never
  `plan_tool.roadmap` (the orchestrator sits beside this chain, not below it)
  and never anything under `plan_tool/cli/`. `_check_predecessor_review_rows`
  is mirrored above for exactly this reason rather than imported.
- **The gates import stays narrow (plan's Architecture, "Why the gates
  import").** Only `design_row_ids` may be imported from `roadmap_gates` —
  no `Violation`, no `check_*` function, no `run_*_gates` aggregate. This
  module judges nothing; it only resolves.
- **Not a second enforcement channel (plan's Out of scope).** `resolve_id`
  and `resolve_feedback_target` never raise on a dangling or ambiguous id and
  carry no severity/blocking field on `Resolution` — a dangling or ambiguous
  outcome is a rendering annotation, not a finding, and must stay that way
  even though this module is the first code to notice one.
- **Not called an envelope (plan's Architecture, "It is deliberately not
  called an envelope").** The multi-artifact parameters this step's index
  builders take are plain optional keyword arguments, not a new dataclass
  that could be confused with `roadmap_gates.ArtifactEnvelope` — whose
  `domain` is mandatory, unlike every parameter here.
- **The mode filter belongs to `LoadedRoadmap`, not to this step (plan's
  Architecture, "The mode is a property of `LoadedRoadmap`, not of each
  renderer").** Nothing in this module takes a mode argument or filters
  anything by lifecycle state; it resolves whatever ids and removals it is
  handed. Step 2 decides which artifacts and which populations ever reach it.

## Deferred

- **Reading artifacts off disk, the absent/unparseable notice, and the
  `current`/`review` mode filter** — `LoadedRoadmap` and its mode-aware
  population selection are step 2's deliverable; this step's builders take
  already-parsed artifacts only.
- **The reverse citation index ("if this row changes, what moves")** — step 3
  builds the id → citing-rows map on top of `resolve_id`; this step supplies
  the per-id resolution, not the reverse walk.
- **The traceability walk and the decision ledger's rendering rules** (which
  removal renders beside which feedback row, the `settled`/`pending`
  grouping, the `ordering`-sequence traversal) — steps 4 and 5.
- **A feedback-id namespace lookup usable by `--id` under `--mode review`** —
  this step guarantees `display_label` handles a bare `FeedbackRow` once one
  is in hand; building a searchable index over feedback ids (their own
  namespace, per `check_feedback_integrity`) is step 3's and step 2's to
  wire together with the mode filter.
- **`DraftSeedProvenance.roadmap_components`** — the plan's own Acceptance
  criteria route this to disposition (b), printed by the walk without being
  resolved through this module at all; out of this step's scope by the
  plan's own design, not an oversight.
- **CLI wiring (`--view`, `--mode`, `--id`) and the doc sweep** — steps 6 and
  7.
