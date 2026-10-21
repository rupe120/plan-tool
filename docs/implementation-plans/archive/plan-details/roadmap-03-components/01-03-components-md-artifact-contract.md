> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 1 — Add the 03-components.md artifact contract with paths, rows, parse, and render

## Summary

This step extends `plan_tool/roadmap_artifacts.py` — the roadmap contract leaf positions 01–02 already ship — with a third artifact: `03-components.md`. It adds `components_path`, frozen row types for system patterns, component patterns, and components, a `COMPONENTS_ROW_KEYS` wire-name tuple, `parse_components_artifact` / `render_components_artifact` / `load_components_artifact`, and a public design-row inventory helper step 2 will wire into `plan_tool/roadmap_gates.py:design_row_ids` and the orchestrator's feedback-target pre-flight. The main design decision is unchanged from position 01: **shape here, relations in the gates** — parsing raises on a malformed frontmatter row but accepts dangling entity, pattern, and constraint ids, duplicate ids, and empty id lists so step 3's five traceability gates have malformed-looking input to judge. On green, a conforming components artifact round-trips through parse and render, lives at `<plans_dir>/roadmaps/<slug>/03-components.md`, and carries the same review collections (`feedback`, `removals`) domain and constraints already use.

## Table of Contents

- [Summary](#summary) — what lands in the contract leaf and the shape-vs-relations split.
- [Why](#why) — why stage 3 needs a typed artifact before gates or the orchestrator touch it.
- [Input](#input) — the upstream artifacts and row types this step reads or reuses.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — paths, row inventory, parse/render, design-row enumeration, and rules that are not free to vary.
- [Tests](#tests) — new cases plus the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — docs worth reading for YAML, dataclasses, and enums.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what later steps own.

## Why

Positions 01–02 define where `01-domain.md` and `02-constraints.md` live, how their rows parse, and how review feedback attaches. Nothing in the repo yet defines the third artifact the plan's architecture names — the partition of the domain into logical components, each owning entity ids, naming patterns, and claiming which constraints those patterns discharge. Steps 2–5 all need the same facts (path constant, row shapes, wire key names, parse/render pair), and `plan_tool/roadmap_gates.py` is allowed exactly one first-party import — this leaf — so the types must exist here first. Shipping parse and render together keeps `parse(render(x)) == x` testable now and means step 5's writer does no YAML shaping of its own. Position 02's revision machinery already resolves feedback targets against "design rows the artifact declares"; component ids cannot participate until this step mints the row kinds and an enumerator step 2 can import without re-listing collections.

## Input

This step builds on shipped position 01–02 contracts. It does not re-parse upstream files during normal operation; it defines the shape downstream gates and the orchestrator will consume.

- **`01-domain.md` row types** — `EntityRow.id` values are what `ComponentRow.entity_ids` will cite. Parsing does not resolve them; step 3's entity-coverage gates read a parsed `DomainArtifact` from the envelope.
- **`02-constraints.md` row types** — `ConstraintRow.id` values are what `ComponentRow.constraint_ids` will cite when a component claims discharge. Only `prioritized` constraints require a discharger (step 3); parse accepts any id string.
- **Shared decision and review rows** — reuse `DecisionRow`, `DecisionStatus`, `RejectedAlternative`, `FeedbackRow`, `FeedbackTarget`, `FeedbackTargetKind`, `FeedbackState`, `RemovalRecord`, and the existing `_parse_decision_rows`, `_parse_feedback_rows`, `_parse_removal_records`, `_decision_mapping`, and `_review_mappings` helpers. Components artifacts carry `decisions`, `feedback`, and `removals` with the same shape/relation split as the first two artifacts.
- **Position 02 feedback-target contract** — `plan_tool/roadmap.py:_check_predecessor_review_rows` resolves row targets against `plan_tool/roadmap_gates.py:design_row_ids(artifact)` plus removal `removed_id`s. Step 1 adds `components_design_rows` (name in [Implementation](#implementation)) so step 2 can extend that set for `ComponentsArtifact` without duplicating collection names.

Field and wire names minted here are authoritative; step 4's `ROADMAP_FORMAT.md` documents whatever ships in this module.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_artifacts.py` — add `COMPONENTS_FILENAME`, `components_path`, `COMPONENTS_ROW_KEYS`, pattern and component row dataclasses, `ComponentsArtifact`, parse/load/render for the third artifact, `components_design_rows`, and update the module docstring to name three artifacts instead of two.
  - `tests/test_roadmap_artifacts.py` — add a conforming `COMPONENTS_TEXT` fixture, cases for the third artifact's paths, parsing, non-relation acceptance, round-trip, design-row inventory, and review-collection behavior; extend imports for new public symbols. All 78 existing cases must stay green.

## Implementation

### Paths

- **Add `COMPONENTS_FILENAME = "03-components.md"`** beside `DOMAIN_FILENAME` and `CONSTRAINTS_FILENAME`, and **`components_path(plans_dir, slug) -> Path`** following `domain_path` / `constraints_path` — same `(plans_dir, slug)` signature, same `_validate_slug` guard, no filesystem access.
- **Do not hardcode `docs/implementation-plans`.** The plans directory is always caller-supplied, matching the existing path helpers.

### Row inventory — mint here, document in step 4

Settle wire names now; step 4 reads them off this module.

- **`COMPONENTS_ROW_KEYS`** — a tuple of the four **design** collection keys, in render order. Recommended members: `system_patterns`, `component_patterns`, `components`, `decisions`. These are the keys stage prompts and `ROADMAP_FORMAT.md` will pin; they deliberately exclude `feedback` and `removals` (see `REVIEW_ROW_KEYS` and `DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS` for the precedent).
- **`PatternRow`** — one named pattern (free text, no closed catalog per the plan's Deferred). Fields: `id`, `name`, `statement`. Used for both system-level and component-level patterns; the collection key distinguishes scope.
- **`ComponentRow`** — one logical unit. Fields:
  - **`id`** — non-empty string; joins the shared id namespace step 3's duplicate-id gate will judge across all design collections on this artifact.
  - **`name`** — non-empty string (prose label; emptiness of `statement`-like fields is a gate judgment elsewhere).
  - **`entity_ids`** — required key, typed as `tuple[str, ...]` via `_id_list`; **entity ids only** — do not add rule, workflow, decision, or field-name anchor fields (the plan's Out of scope fence).
  - **`pattern_ids`** — required key via `_id_list`; cites pattern row ids from either pattern collection.
  - **`constraint_ids`** — optional key defaulting to `()`; lists constraint ids the component claims its patterns discharge. Present-and-empty parses; step 3 decides whether a discharge claim is valid.
- **`ComponentsArtifact`** — frozen dataclass holding `system_patterns`, `component_patterns`, `components`, and `decisions` as **ordered tuples** (never dicts keyed by id), plus `body`, and default-empty `feedback` / `removals`. Same duplicate-survival rule as `DomainArtifact` and `ConstraintsArtifact`: two rows sharing an id both remain in the tuple.

### Design-row / feedback-target enumeration

- **Add `components_design_rows(artifact: ComponentsArtifact) -> tuple[tuple[str, str], ...]`** returning `(kind label, id)` for every design row: system pattern, component pattern, component, decision — in that order, matching render order. Kind labels are message-facing strings (e.g. `"system pattern"`, `"component pattern"`, `"component"`, `"decision"`); they need not match wire keys.
- **This function is public on purpose.** Step 2 extends `plan_tool/roadmap_gates.py:_rows_of` and `design_row_ids` to dispatch on `ComponentsArtifact` by importing this enumerator rather than re-declaring collections — the same anti-drift reason `design_row_ids` is public for `plan_tool/roadmap.py:_check_predecessor_review_rows`. Step 1 does **not** edit `roadmap_gates.py` or `roadmap.py`.
- **Rejected alternative:** leaving enumeration entirely in the gate module. That forces step 2 to know wire names and dataclass fields the contract leaf owns, and it is the first place the two modules drift when a collection is added.

### Parsing and rendering

- **Mirror the domain/constraints pair:** `parse_components_artifact(text)`, `render_components_artifact(artifact) -> str`, `load_components_artifact(path)` using `_load` and `RoadmapArtifactError` with `path=` set on failure.
- **Reuse the existing frontmatter pipeline:** `_split_frontmatter`, `_parse_frontmatter`, `_iter_rows`, `_row_id`, `_row_text`, `_id_list`, and the decision/feedback/removal parsers. Do not import `plan_tool/parser.py:_split_frontmatter` — leaf discipline stays intact.
- **Open frontmatter schema:** unknown top-level keys are ignored on parse (pin with a case like `test_unknown_frontmatter_keys_are_ignored_not_rejected` for the third artifact). The renderer emits only `COMPONENTS_ROW_KEYS` design keys plus non-empty review collections — same rule as the first two artifacts.
- **Always emit all four design keys on render**, even when a collection is empty, so neither pattern collection is "vacuously absent" from the wire format. Empty lists are fine; omitted keys are not.
- **Enum rendering:** convert `DecisionStatus` members to `.value` before `yaml.safe_dump` (same `RepresenterError` quirk documented on `_decision_mapping`).
- **Review collections:** reuse `_review_mappings`, `_FEEDBACK_KEY_COMMENT`, and `_NO_FEEDBACK_KEY_COMMENT` so an unreviewed components artifact renders the same reviewer key behavior domain and constraints already ship.

### Shape checked here; relations owned by step 3

List every relation this parser **deliberately does not** enforce, and cover each with a case asserting parse succeeds without raising:

- **`entity_ids` naming an entity `01-domain.md` does not define** — gate finding, not parse error.
- **`pattern_ids` naming a pattern row this artifact does not declare** — gate finding, not parse error.
- **`constraint_ids` naming a constraint `02-constraints.md` does not define** — gate finding, not parse error.
- **Duplicate row ids within or across the four design collections** — both rows survive parsing; step 3's duplicate-id gate reports them.
- **A component with empty `entity_ids` or empty `pattern_ids`** — parses; step 3's coverage gates report it.
- **A decision with no rejected alternatives, a blank rationale, or an anchor pointing nowhere** — parses; step 3 inherits the same decision gates constraints already use once the envelope carries domain and constraints.
- **Feedback targeting a component id the artifact does not declare** — parses; gate/pre-flight resolution is step 2–3.

Do not add uniqueness, referential, totality, or merit checks here — overlapping with step 3's gates wastes retry budget and breaks the ownership split position 01 established.

### Constraints that are not free to vary

- **No first-party import** — `yaml` only, plus stdlib. Keep both leaf-discipline tests green (`test_leaf_imports_no_first_party_module`, source grep paired with subprocess check).
- **No edits outside the two declared files** — no gate, orchestrator, prompt, or doc changes in this step.
- **No closed pattern vocabulary** — patterns are free-text rows; do not mint a `PatternKind` enum or catalog constant.
- **No entity-id-alternative anchor fields on `ComponentRow`** — the plan settled entity-id anchoring; field names, rules, workflows, and decisions are out of scope for component ownership lists.

## Tests

All cases live in `tests/test_roadmap_artifacts.py`. Plain unit tests (unmarked). The module has no backend seam.

### Tests for this step

Every new case below must be green before this step is finished, and **all 78 existing cases must still pass** — this step is additive on a live contract leaf.

**Paths**

- `test_components_path_sits_under_the_roadmap_dir` — `components_path` returns `<plans_dir>/roadmaps/<slug>/03-components.md`.
- `test_components_path_follows_an_arbitrary_plans_dir` — a non-default `plans_dir` moves the path; nothing hardcodes the default plans location.

**Row keys and design-row inventory**

- `test_components_row_key_constants_match_the_rendered_frontmatter` — `COMPONENTS_ROW_KEYS` matches the design keys `render_components_artifact` emits, in order, and excludes `REVIEW_ROW_KEYS`.
- `test_components_design_rows_lists_every_design_kind` — `components_design_rows` returns one entry per system pattern, component pattern, component, and decision row in the fixture.

**Components artifact parsing**

- `test_conforming_components_body_parses_every_row_kind` — system patterns, component patterns, components, and decisions land as typed rows.
- `test_missing_opening_fence_raises_on_components` — same fence contract as domain/constraints.
- `test_malformed_yaml_raises_and_names_the_path_for_components` — `load_components_artifact` attaches the path.
- `test_missing_required_component_row_key_raises_naming_the_row` — e.g. a component row with no `entity_ids` key names the row in the message.
- `test_wrong_type_for_a_components_row_collection_raises` — scalar where a list is required is rejected.
- `test_unknown_frontmatter_keys_are_ignored_on_components` — extra top-level keys do not fail parse.
- `test_duplicate_component_row_ids_survive_as_separate_rows` — two components sharing an id both appear in the tuple.

**Relations the parser deliberately does not check**

- `test_entity_id_not_in_domain_still_parses` — `entity_ids` cites `entity-missing`; no raise.
- `test_pattern_id_not_in_artifact_still_parses` — `pattern_ids` cites an undefined pattern id; no raise.
- `test_constraint_id_not_in_constraints_still_parses` — `constraint_ids` cites `constraint-missing`; no raise.
- `test_component_with_empty_entity_ids_still_parses` — present-but-empty list; gate finding, not parse error.
- `test_component_with_empty_pattern_ids_still_parses` — same.
- `test_feedback_targeting_an_undefined_component_id_parses` — row target names a missing component id; no raise.

**Round-trip and review collections**

- `test_components_artifact_round_trips_through_render_and_parse` — `parse(render(a)) == a` for a conforming artifact including both pattern collections.
- `test_components_feedback_and_removals_round_trip` — review rows parse and render like domain/constraints.
- `test_absent_review_collections_render_no_new_key_on_components` — no `feedback:` key when empty.
- `test_both_pattern_collections_render_even_when_empty` — rendered frontmatter includes `system_patterns:` and `component_patterns:` keys (empty lists acceptable).

**Layering (unchanged — must stay green)**

- `test_leaf_imports_no_first_party_module` — still passes after edits.
- `test_leaf_declares_no_invoker_seam` — still passes after edits.

## Acceptance criteria

- Only `plan_tool/roadmap_artifacts.py` and `tests/test_roadmap_artifacts.py` change; `plan_tool/roadmap_gates.py`, `plan_tool/roadmap.py`, and `ROADMAP_FORMAT.md` carry no diff.
- `rg '^(from|import) plan_tool' plan_tool/roadmap_artifacts.py` returns nothing; leaf-import tests still pass.
- `components_path(plans_dir, slug)` returns `<plans_dir>/roadmaps/<slug>/03-components.md`; slug traversal guards match `domain_path`.
- `COMPONENTS_ROW_KEYS`, `PatternRow`, `ComponentRow`, `ComponentsArtifact`, `parse_components_artifact`, `render_components_artifact`, `load_components_artifact`, and `components_design_rows` exist and are importable from `plan_tool/roadmap_artifacts`.
- Parsing a conforming components artifact yields typed system-pattern, component-pattern, component, and decision rows plus preserved prose `body`.
- Parsing raises `RoadmapArtifactError` (with path when loaded from disk) for: missing opening fence, unclosed fence, invalid YAML, missing required row key, wrong-typed collection, unknown `DecisionStatus`, and malformed feedback/removal shape — reusing the same rules as the first two artifacts.
- Parsing does **not** raise for: undefined entity/pattern/constraint ids, duplicate row ids, empty `entity_ids` or `pattern_ids` on a component, decisions with no rejected alternatives, or feedback targeting an undefined row id.
- `parse(render(artifact)) == artifact` for a conforming components artifact; rendered YAML carries enum values as plain strings.
- `render_components_artifact` emits all four `COMPONENTS_ROW_KEYS` design collections; neither pattern collection key is omitted when empty.
- `components_design_rows` returns every design-row `(kind label, id)` on the artifact — the set step 2 will fold into `design_row_ids`.
- All tests in `tests/test_roadmap_artifacts.py` pass under `uv run pytest tests/test_roadmap_artifacts.py -q`, and the full suite stays green.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load`, `YAMLError`, and `safe_dump` for frontmatter parse/render error handling.
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — type rules for id lists and nested pattern/component rows.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — frozen row types and equality used in round-trip tests.
- [enum — Support for enumerations](https://docs.python.org/3/library/enum.html) — `DecisionStatus` reuse and `.value` rendering before dump.

## Applicable guardrails

- **The plan's Out of scope — positions 04–05 and seed emission.** This step mints no seed helper, no plan-derivation rows, and no lens types.
- **The plan's Out of scope — partition quality and pattern merit.** No gate logic, no scoring, no closed pattern catalog — only row shapes and parse/render.
- **The plan's Out of scope — second feedback channel.** Reuse the existing review row types and render comments; do not invent parallel feedback fields.
- **The plan's Out of scope — orchestrator / stage-table widening.** No edits to `plan_tool/roadmap.py` or prompts; step 5 owns the `STAGES` row.
- **Entity-id anchoring only on components.** Do not add fields that cite business-rule, workflow, decision, or field-name ids on `ComponentRow`.
- **Plan discovery untouched.** Artifacts stay under `<plans_dir>/roadmaps/<slug>/`; no locator or manifest changes.

## Deferred

- **The five components traceability gates and `run_components_gates`** — step 3 in `plan_tool/roadmap_gates.py`.
- **Widening `ArtifactEnvelope`, `_rows_of`, and `design_row_ids` for a third artifact** — step 2; it imports `components_design_rows` from this step rather than re-listing collections.
- **`ROADMAP_FORMAT.md` documentation and executable examples** — step 4 reads wire names off the landed module.
- **Stage orchestration, `roadmap-components.md`, disk write, and `--from-stage 3`** — step 5 in `plan_tool/roadmap.py`.
- **Consolidating the three frontmatter fence scanners** — `plan_tool/parser.py:_split_frontmatter`, `plan_tool/reprocess.py:_split_frontmatter_for_rewrite`, and this leaf's `_split_frontmatter`; cross-module refactor, not this step.
- **A closed pattern vocabulary or pattern-catalog gate** — plan Deferred; patterns stay free text.
- **Judging decomposition quality, component count caps, or prose-inventory agreement beyond existing stage-1/2 gates** — reviewer judgment and later steps, not parse shape.
