> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add the five components traceability gates and run_components_gates

## Summary

This step adds five relation gates and a stage gate aggregate to `plan_tool/roadmap_gates.py` so a parsed `03-components.md` can be judged against `01-domain.md` and `02-constraints.md` already carried in `ArtifactEnvelope`. The gates enforce entity coverage, pattern presence, valid constraint citations, and prioritized-constraint discharge — binary id checks only, each violation written as retry text naming every identifier involved. The main design decision matches stages 1–2: **shape in the artifact leaf, relations here** — parsing already accepts dangling ids and empty lists; this step is where those relations become blocking violations. On green, `run_components_gates` over a hand-built three-artifact envelope returns an empty list for a conforming fixture and one self-contained message per defect for each of the five failure shapes; `plan_tool/roadmap.py` still has zero diff because the orchestrator wires the runner in step 5.

## Table of Contents

- [Summary](#summary) — five traceability gates, the stage runner, and what stays untouched.
- [Why](#why) — the relation checks step 1 deferred and step 2 left room for.
- [Input](#input) — envelope and row types this step reads from steps 1–2.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — gate rules, violation kinds, aggregate ordering, and constraints that are not free to vary.
- [Tests](#tests) — new cases plus the green-before-done gate.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — docs worth skimming for patterns and typing.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what later steps own.

## Why

Step 1 lands `ComponentRow` with `entity_ids`, `pattern_ids`, and optional `constraint_ids` but deliberately does not resolve or totality-check them — four parser cases exist purely to pin that non-enforcement. Step 2 widens `ArtifactEnvelope` so domain, constraints, and components travel together and fixes gates that mistook "constraints present" for "constraints stage," but it explicitly does **not** mint entity-coverage or discharge rules. Without this step, a components artifact can pass every existing gate while leaving orphan entities, citing undefined constraints, or skipping every `prioritized` constraint — exactly the review-surface gaps the plan's architecture names. The five gates are the deterministic half of stage 3; step 5 will hold `run_components_gates` as a table value the same way `run_domain_gates` and `run_constraints_gates` already do.

## Input

This step depends on steps 1–2 landing in `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py`. If this detail and the code disagree, the code wins.

- **Step 1 row types** — `PatternRow`, `ComponentRow` (`entity_ids`, `pattern_ids`, `constraint_ids`), and `ComponentsArtifact` with `system_patterns`, `component_patterns`, and `components` as ordered tuples. Pattern ids resolve against the union of both pattern collections on the same artifact.
- **Step 1 upstream types** — `EntityRow.id` from `DomainArtifact.entities`; `ConstraintRow.id` and `AttributeDispositionRow` from `ConstraintsArtifact`; `ConstraintDisposition.PRIORITIZED` marks attributes whose constraint rows require discharge.
- **Step 2 envelope** — `ArtifactEnvelope(domain=…, constraints=…, components=…)`; `artifact_under_check` / `filename_under_check` follow the last-filled-slot rule; `COMPONENTS_FILENAME` names the file in violation messages. The five new gates assume a components-stage envelope (all three slots filled); they early-return `[]` when `artifact_under_check` is not a `ComponentsArtifact`.
- **Step 2 fixtures** — `make_components` and `components_envelope` from step 2's test additions are the starting point for conforming and failing cases here.
- **Existing precedents in this module** — `check_entity_references` (undefined-id and empty-list messaging, report every bad reference), `check_attribute_totality` (build a disposition map from `dispositions` rows), and `Violation` (no `blocking` flag; `row_id=None` only for absence defects with the expected identifier named in `message`).

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — five `check_*` gate functions, new `VIOLATION_*` kind constants, `COMPONENTS_GATES` tuple, `run_components_gates`, and any small private helpers to build defined-id sets and disposition maps; extend imports from `plan_tool/roadmap_artifacts` for `COMPONENTS_FILENAME`, `ComponentsArtifact`, `ComponentRow`, `ConstraintDisposition`, and related symbols already used elsewhere in the module.
  - `tests/test_roadmap_gates.py` — extend `make_components` / `components_envelope` if needed, add traceability gate cases (pass, fail, message shape, cardinality), one module-boundary seam test driving `parse_components_artifact` → `run_components_gates`, and extend imports for new public symbols; all existing cases (including step 2 envelope cases once landed) must stay green.

## Implementation

### Governing rule

**Violations are retry text.** Each message must stand alone in a retried prompt: name the offending row id (or the expected id when the row is absent), every undefined id cited, and the filename constants (`DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`) — never a line number. Mirror the three-identifier shape `plan_tool/review.py:validate_feature_refs` uses and the wording habits of `check_entity_references`.

**Only run on the components stage.** Each new gate returns `[]` when `envelope.artifact_under_check` is not a `ComponentsArtifact`. Constraint- and domain-only gates (`check_attribute_totality`, `check_constraint_anchors`, `check_entity_fields`, `check_entity_references`) stay out of `COMPONENTS_GATES` — upstream artifacts are inputs for resolution, not re-judged on every components retry.

**Report every offender.** For reference walks (entity ids, pattern ids, constraint ids), emit one violation per bad id, not stop at the first. For uniqueness-style defects handled elsewhere, defer to `check_duplicate_row_ids`.

### The five gate functions (six Architecture rules)

Five `check_*` functions cover Architecture's six numbered traceability rules in `docs/implementation-plans/2-roadmap-03-components.md`. **Not one-to-one:** Architecture items 3 and 4 (artifact-level pattern collections non-empty; per-component ≥1 defined pattern id) both land in `check_component_pattern_references`. Items 1, 2, 5, and 6 each get their own function.

| # | Recommended function | Rule | Upstream read |
|---|----------------------|------|---------------|
| 1 | `check_component_entity_references` | Every component names ≥1 entity id that `01-domain.md` defines | `envelope.domain.entities` |
| 2 | `check_entity_component_coverage` | Every domain entity id appears in ≥1 component's `entity_ids` | domain entities ∪ all component `entity_ids` |
| 3 | `check_component_pattern_references` | Every component names ≥1 defined pattern id; both `system_patterns` and `component_patterns` are non-empty on the artifact | pattern rows on the components artifact |
| 4 | `check_component_constraint_references` | Every `constraint_ids` entry names a constraint row `02-constraints.md` defines | `envelope.constraints.constraints` |
| 5 | `check_prioritized_constraint_discharge` | Every constraint row whose attribute is `prioritized` appears in ≥1 component's `constraint_ids` | `dispositions` + `constraints` |

**Gate 1 — component entity references.** Walk `artifact_under_check.components`. Empty `entity_ids` → reuse `VIOLATION_NO_ENTITY_REFERENCE` with `artifact=COMPONENTS_FILENAME` and a message naming the component id (same defect shape as domain workflows/rules). Undefined entity id → reuse `VIOLATION_UNDEFINED_ENTITY_REFERENCE`, naming both the component id and the missing entity id plus `DOMAIN_FILENAME`.

**Gate 2 — entity component coverage.** Build the set of entity ids claimed across all components. For each `EntityRow` in `envelope.domain.entities` absent from that set, emit a new kind (recommended: `VIOLATION_UNCOVERED_ENTITY`) with `row_id=None` and a message naming the orphan entity id and `DOMAIN_FILENAME` — absence defects cannot populate `row_id` with a components-row id.

**Gate 3 — pattern references and collections.** Two checks in one function (still one gate):
- **Artifact level:** if `system_patterns` or `component_patterns` is empty, violate (recommended kind: `VIOLATION_EMPTY_PATTERN_COLLECTION`, `row_id=None`, message names which collection in `COMPONENTS_FILENAME` must carry at least one pattern row). Step 1's renderer always emits both keys; empty tuple is the failure mode.
- **Per component:** empty `pattern_ids` → new kind (recommended: `VIOLATION_NO_PATTERN_REFERENCE`). Undefined pattern id → new kind (recommended: `VIOLATION_UNDEFINED_PATTERN_REFERENCE`); defined set is `{row.id for row in system_patterns}` ∪ `{row.id for row in component_patterns}`.

**Gate 4 — constraint references.** Only inspect non-empty `constraint_ids` lists (present-but-empty is not a discharge claim). Undefined constraint id → new kind (recommended: `VIOLATION_UNDEFINED_CONSTRAINT_REFERENCE`), naming the component id, the bad constraint id, and `CONSTRAINTS_FILENAME`. Components with no `constraint_ids` entries pass this gate.

**Gate 5 — prioritized discharge.** Build `attribute → disposition` from `envelope.constraints.dispositions`. For each `ConstraintRow`, if disposition for `row.attribute` is not `ConstraintDisposition.PRIORITIZED`, skip. Otherwise require `row.id` to appear in at least one component's `constraint_ids`. If not, emit a new kind (recommended: `VIOLATION_UNDISCHARGED_PRIORITIZED_CONSTRAINT`) with `row_id=constraint_row.id`. Constraints on `traded-away` or `not-load-bearing` attributes pass without a discharger — the plan's Risks section calls this out explicitly; pin with tests.

**Rejected alternative:** one mega-gate that mixes all five rules. That hides which retry correction applies, breaks the one-token-per-defect convention, and makes step 4's doc-to-symbol traceability map unreadable.

### Stage aggregate

- **`COMPONENTS_GATES`** — tuple of gate functions in fixed order (declared order is violation order, same comment block as `DOMAIN_GATES` / `CONSTRAINTS_GATES`). Recommended ordering:
  1. `check_artifact_non_empty` (step 2 already dispatches on `ComponentsArtifact`)
  2. `check_duplicate_row_ids`
  3. the five traceability gates (entity refs → coverage → patterns → constraint refs → discharge)
  4. `check_decision_records`
  5. `check_inventory_has_prose`
  6. `check_design_row_continuity`
  7. `check_feedback_integrity`
  8. `check_settled_decisions`
- **`run_components_gates(envelope)`** — `return _run_gates(COMPONENTS_GATES, envelope)`; same signature as `run_domain_gates` / `run_constraints_gates` so step 5's stage table holds the symbol by identity with no wrapper.
- **Module docstring** — add a subsection naming the five components traceability gates and `run_components_gates`; update the opening count if it still says "eleven gates" without mentioning stage-specific sets.

### Violation kind constants

Mint new `VIOLATION_*` tokens for defects that have no domain/constraints analogue (`uncovered-entity`, `no-pattern-reference`, `undefined-pattern-reference`, `empty-pattern-collection`, `undefined-constraint-reference`, `undischarged-prioritized-constraint`). Reuse `VIOLATION_NO_ENTITY_REFERENCE` and `VIOLATION_UNDEFINED_ENTITY_REFERENCE` for gate 1 — the `artifact` field carries which file to fix.

### Constraints that are not free to vary

- **No orchestrator edits** — `plan_tool/roadmap.py`, prompts, and CLI stay untouched; zero callers for `run_components_gates` until step 5.
- **No doc edits** — `ROADMAP_FORMAT.md` is step 4; kind constants get documented there, not invented in prose here beyond recommendations.
- **Leaf import discipline** — still exactly one first-party import (`plan_tool.roadmap_artifacts`); keep `test_module_imports_only_the_artifact_leaf` green.
- **No merit gates** — do not judge partition quality, component count, pattern wording, or whether discharge claims are plausible — only id presence and resolution.
- **Do not import `plan_tool/gates.py` or `plan_tool/review.py`** — copy message shape, not code; either import ends leaf status.
- **No closed pattern catalog** — pattern ids are free text rows defined on the artifact; gate 3 checks existence, not vocabulary membership.

## Tests

All cases live in `tests/test_roadmap_gates.py`. Plain unit tests (unmarked). Build fixtures from step 1 row dataclasses directly; one deliberate seam test crosses into `parse_components_artifact`.

### Tests for this step

Every new case below must be green before this step is finished, and **all existing cases in `tests/test_roadmap_gates.py` must still pass** (approx. 121 at HEAD before steps 1–2 land; count grows with those steps).

**Fixtures (extend step 2)**

- Ensure `make_components` yields a conforming artifact: at least one system pattern, one component pattern, one component whose `entity_ids` and `pattern_ids` cite defined upstream ids, prose naming every design-row id, and `constraint_ids` listing a prioritized constraint when the default constraints fixture includes one.
- Ensure `components_envelope` fills `domain`, `constraints`, and `components`.

**Gate 1 — `check_component_entity_references`**

- `test_component_referencing_defined_entities_passes` — conforming fixture returns `[]`.
- `test_component_with_empty_entity_ids_violates` — empty `entity_ids` on a component row violates with `VIOLATION_NO_ENTITY_REFERENCE`.
- `test_component_referencing_undefined_entity_violates` — bad entity id violates with `VIOLATION_UNDEFINED_ENTITY_REFERENCE`.
- `test_every_undefined_entity_reference_on_components_is_reported` — two bad ids on one component yield two violations.

**Gate 2 — `check_entity_component_coverage`**

- `test_full_entity_coverage_passes` — every domain entity listed on some component returns `[]`.
- `test_orphan_entity_violates` — domain entity not on any component violates; message names the entity id and `DOMAIN_FILENAME`.
- `test_every_orphan_entity_is_reported` — two uncovered entities yield two violations.

**Gate 3 — `check_component_pattern_references`**

- `test_components_with_defined_patterns_passes` — conforming fixture returns `[]`.
- `test_empty_system_patterns_collection_violates` — zero system pattern rows violates at artifact level.
- `test_empty_component_patterns_collection_violates` — zero component pattern rows violates at artifact level.
- `test_component_with_empty_pattern_ids_violates` — component citing no patterns violates.
- `test_component_referencing_undefined_pattern_violates` — bad pattern id violates.
- `test_pattern_id_resolves_across_both_collections` — a component citing a system-pattern id passes when that id lives in `system_patterns`.

**Gate 4 — `check_component_constraint_references`**

- `test_component_citing_defined_constraints_passes` — valid `constraint_ids` return `[]`.
- `test_component_with_empty_constraint_ids_passes` — no discharge claim does not fail gate 4.
- `test_component_referencing_undefined_constraint_violates` — bad constraint id violates.
- `test_constraint_reference_violation_names_both_ids` — message names component id, constraint id, and `CONSTRAINTS_FILENAME`.

**Gate 5 — `check_prioritized_constraint_discharge`**

- `test_prioritized_constraint_discharged_by_a_component_passes` — `constraint_ids` listing the prioritized constraint returns `[]`.
- `test_prioritized_constraint_with_no_discharger_violates` — prioritized constraint omitted from every component violates.
- `test_traded_away_constraint_without_discharger_passes` — constraint on a `traded-away` attribute needs no component citation.
- `test_not_load_bearing_constraint_without_discharger_passes` — constraint on a `not-load-bearing` attribute needs no component citation.

**Aggregate and seam**

- `test_run_components_gates_clears_a_conforming_envelope` — `run_components_gates(components_envelope()) == []`.
- `test_components_gates_tuple_includes_traceability_gates_in_order` — `COMPONENTS_GATES` holds the five new functions (identity check, not wrappers) in the documented order among shared gates.
- `test_gates_accept_a_parsed_conforming_components_artifact` — conforming components text from step 1's parser, with parsed domain and constraints upstream, clears `run_components_gates` (third module-boundary case beside the two domain/constraints seam tests).

**Regression guards**

- `test_run_domain_gates_and_run_constraints_gates_unchanged` — existing conforming domain/constraints envelopes still clear their runners (no accidental edit to shared gates).
- `test_module_imports_only_the_artifact_leaf` — still passes.

## Acceptance criteria

- Only `plan_tool/roadmap_gates.py` and `tests/test_roadmap_gates.py` change among production and test code for this step's scope.
- `plan_tool/roadmap.py`, `tests/test_roadmap.py`, and `ROADMAP_FORMAT.md` carry **zero diff**.
- `check_component_entity_references`, `check_entity_component_coverage`, `check_component_pattern_references`, `check_component_constraint_references`, and `check_prioritized_constraint_discharge` exist and accept `ArtifactEnvelope`.
- `COMPONENTS_GATES` and `run_components_gates` exist; `run_components_gates` delegates to `_run_gates` with no local adapter wrapper.
- Each gate returns `[]` when `artifact_under_check` is not a `ComponentsArtifact`.
- Gate 1 reuses `VIOLATION_NO_ENTITY_REFERENCE` / `VIOLATION_UNDEFINED_ENTITY_REFERENCE` with `artifact=COMPONENTS_FILENAME`; gates 2–5 mint distinct new kind constants documented in code comments beside each constant.
- Orphan-entity and empty-pattern-collection violations use `row_id=None` with the expected identifier named in `message`.
- A `traded-away` or `not-load-bearing` constraint with no component citation produces no discharge violation; a `prioritized` constraint with none does.
- `rg 'run_components_gates' plan_tool/roadmap.py` returns nothing (runner not wired yet).
- `rg '^(from|import) plan_tool' plan_tool/roadmap_gates.py` matches only `plan_tool.roadmap_artifacts`.
- `uv run pytest tests/test_roadmap_gates.py -q` passes, and the full suite stays green.

## References

- [typing — Support for type hints](https://docs.python.org/3/library/typing.html) — `Callable` gate typing and optional envelope fields consumed from step 2.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — frozen row fixtures built with `replace` for failing cases.
- [enum — Support for enumerations](https://docs.python.org/3/library/enum.html) — `ConstraintDisposition.PRIORITIZED` / `TRADED_AWAY` / `NOT_LOAD_BEARING` lookup for gate 5.

## Applicable guardrails

- **The plan's step intent.** This step ships only deterministic id-relation checks whose output is retry text — not reviewer judgment, not partition scoring, not seed emission.
- **The plan's Out of scope — partition quality and pattern merit.** No gate counts components, compares pattern prose, or ranks decomposition choices; gate 3 checks that pattern rows exist and are cited, not that patterns are good.
- **The plan's Out of scope — constraint discharge breadth.** Gate 5 keys off `prioritized` dispositions only; demanding discharge for `traded-away` or `not-load-bearing` attributes is out of scope and must stay unimplemented.
- **The plan's Out of scope — orchestrator and stage table.** Do not edit `plan_tool/roadmap.py` or add prompts; wiring `run_components_gates` into `STAGES` is step 5.
- **The plan's Out of scope — closed pattern catalog.** Pattern rows stay free text; gate 3 resolves ids against rows on the artifact, not against an external vocabulary.
- **Entity-id anchoring on components.** Gates judge `ComponentRow.entity_ids` only — do not add parallel checks for rule, workflow, decision, or field-name ids on components.

## Deferred

- **`ROADMAP_FORMAT.md` rule documentation and executable examples** — step 4 reads kind constants and function names off the landed module.
- **`plan_tool/roadmap.py` `STAGES` row, prompt assembly, disk write, and `--from-stage 3`** — step 5 holds `run_components_gates` by identity in the stage table.
- **Updating `tests/test_roadmap.py:TestSyntheticThirdStage` to use `artifact_key="components"`** — step 5 when the real stage lands.
- **Re-running `check_attribute_totality` / `check_constraint_anchors` on components retry** — intentionally excluded from `COMPONENTS_GATES`; upstream constraints were gated at stage 2. Re-validating them on every components attempt is step 5/orchestrator policy, not this step.
- **Consolidating reference-check helpers with `check_entity_references` or `validate_feature_refs`** — three result types, three data shapes; consolidation routes to reconcile/BACKLOG, not this step.
