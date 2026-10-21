> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document 03-components.md in ROADMAP_FORMAT.md with gate-clean examples

## Summary

This step extends `ROADMAP_FORMAT.md` — the fourth root-level FORMAT doc — so operators and agents can discover, hand-edit, and copy a conforming `03-components.md` without reading `plan_tool/roadmap_artifacts.py` or `plan_tool/roadmap_gates.py`. It adds the third artifact's path convention, annotated frontmatter schema, shape-vs-relations rules, five traceability gate rows tied to the symbols step 3 lands, and one runnable ```markdown example that clears `run_components_gates` against the doc's existing domain and constraints examples. It extends `tests/test_roadmap_format.py` so those examples parse, round-trip through the real renderer, and run past the real gate aggregates — the same drift guard positions 01–02 established. The main design decision is unchanged from the FORMAT family: **the doc names the code that enforces each rule, and the code wins on disagreement** — wire names and kind constants are read off the landed modules at write time, not transcribed from plan prose. On green, an operator can paste the components example verbatim, every documented gate function appears in `plan_tool/roadmap_gates.py`, and `uv run pytest tests/test_roadmap_format.py -q` passes with no production-code diff.

## Table of Contents

- [Summary](#summary) — what lands in the format doc and its drift guard.
- [Why](#why) — why stage 3 needs a copy-safe schema reference before the orchestrator ships.
- [Input](#input) — symbols and examples this step reads from steps 1–3.
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches.
- [Implementation](#implementation) — doc sections, example design, test guard updates, and rules that are not free to vary.
- [Tests](#tests) — verification checks for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — docs worth skimming while authoring YAML examples.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what later steps own.

## Why

Steps 1–3 land the typed contract, widened envelope, and five traceability gates for `03-components.md`, but nothing in the repo yet tells an operator what to type. `ROADMAP_FORMAT.md` is the hand-edit surface for roadmap artifacts — the part readers copy when adding feedback or fixing a gate failure — and it currently describes only two stages. Without a gate-clean example wired through the same drift guard as `01-domain.md` and `02-constraints.md`, the third artifact's row keys, id namespaces, and discharge rules stay discoverable only from code. Step 5's prompt will restate the contract inline (prompts cannot cite repo-root FORMAT docs); this step is what makes the human-facing reference accurate before that restatement is authored.

## Input

This step depends on steps 1–3 landing in `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py`. **Open both modules at HEAD and record what shipped — the landed names win over any name this plan or an earlier detail suggested.**

**From step 1 (`plan_tool/roadmap_artifacts.py`) — cite at symbol level:**

- Path: `COMPONENTS_FILENAME`, `components_path`
- Wire inventory: `COMPONENTS_ROW_KEYS` (expected: `system_patterns`, `component_patterns`, `components`, `decisions`)
- Row types: `PatternRow`, `ComponentRow`, `ComponentsArtifact`
- Parse/render/load: `parse_components_artifact`, `render_components_artifact`, `load_components_artifact`
- Design-row inventory: `components_design_rows`
- Shared review rows: same `feedback` / `removals` shape as domain and constraints (`REVIEW_ROW_KEYS`); `ComponentsArtifact` carries them too

**From steps 2–3 (`plan_tool/roadmap_gates.py`) — cite at symbol level:**

- Envelope: `ArtifactEnvelope` with `domain`, `constraints`, `components`, and `predecessor`; `artifact_under_check` / `filename_under_check` last-filled-slot rule
- Stage aggregate: `COMPONENTS_GATES`, `run_components_gates`
- Five traceability gates (names from step 3 detail — confirm at HEAD): `check_component_entity_references`, `check_entity_component_coverage`, `check_component_pattern_references`, `check_component_constraint_references`, `check_prioritized_constraint_discharge`
- Reused violation kinds on gate 1: `VIOLATION_NO_ENTITY_REFERENCE`, `VIOLATION_UNDEFINED_ENTITY_REFERENCE`
- New violation kinds minted in step 3 — document whatever `VIOLATION_*` constants actually ship beside gates 2–5

**From the existing doc — keep and extend, do not rewrite from scratch:**

- The source-of-truth banner, `## See also` tail, annotated ```yaml schema blocks, and ```markdown runnable examples under `## Examples`
- The order/payment/checkout fictional domain in the first-run `01-domain.md` and `02-constraints.md` examples — the new components example must cite **those** entity and constraint ids so cross-artifact gates pass without inventing a second story

**Path-only references (steps 5–7 not landed — no function names):**

- `plan_tool/roadmap.py` — stage table and disk write
- `plan_tool/cli/roadmap_cmd.py` — CLI entry
- `plan_tool/prompts/roadmap-components.md` — stage-3 authoring prompt (step 5 creates this file)

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — widen the roadmap from two artifacts to three; add `03-components.md` schema, enforcement traceability, and one gate-clean runnable example; update envelope, gate-set, and parse-time sections that still read as a two-stage pair.
  - `tests/test_roadmap_format.py` — teach the drift guard to recognize, parse, round-trip, and gate-check a components ```markdown example; bump minimum example count; extend standalone gate coverage for a three-artifact envelope.

## Implementation

### Doc family checklist

Before editing, confirm each FORMAT-family element individually (they are not all universal):

- **Source-of-truth banner** — keep; update the gate count clause from "eleven gates" to language that names **stage-specific gate sets** and the total relation-gate inventory step 3 adds (sixteen functions across three tuples at the plan's intended landing — confirm the exact count against `rg '^def check_' plan_tool/roadmap_gates.py` at HEAD).
- **`## See also`** — keep the existing tail; no new cross-links required unless a cited path changes.
- **Annotated ```yaml schema** — add one for `03-components.md` frontmatter (with `# required` / presence comments like the domain and constraints sections).
- **Runnable ```markdown examples** — add one first-run `03-components.md` block; retag only examples meant to round-trip (never the annotated schema blocks).

### Global sweeps (do these before calling the step done)

- **Two → three artifacts** — opening paragraph, "staged pair" wording, path convention block, "What writes them" (name the third prompt file by **path only**), and any count that still says two files or eleven gates without mentioning components.
- **No line numbers as anchors** — cite `check_component_entity_references`, `COMPONENTS_ROW_KEYS`, etc.; never "line 522".
- **Land-on-code for every wire name** — if step 1 renamed a field, the doc follows the module.

### New section: `## `03-components.md` — frontmatter schema`

Add after the `02-constraints.md` schema section (or immediately before review collections if that reads better — match the 01→02 ordering pattern).

Document, grounded in step 1's landed types:

- **Purpose** — partitions the domain into logical components: entities each component owns (`entity_ids` cites **entity ids only** from `01-domain.md`), patterns that shape the unit (system-level and component-level collections), and optional constraint discharge claims (`constraint_ids`).
- **Annotated ```yaml block** — collections:
  - `system_patterns` — list of `PatternRow` (`id`, `name`, `statement`); required key on render even when empty
  - `component_patterns` — same row shape, different scope
  - `components` — `ComponentRow`: `id`, `name`, `entity_ids`, `pattern_ids`, optional `constraint_ids`
  - `decisions` — same row shape as stages 1–2
  - Note that `feedback` / `removals` follow [The review collections](#the-review-collections--feedback-and-removals) and attach to `ComponentsArtifact` the same way
- **Parsing** — `parse_components_artifact` / `load_components_artifact` into frozen `ComponentsArtifact`; ordered tuples, not dicts keyed by id
- **Rendering** — `render_components_artifact` emits only `COMPONENTS_ROW_KEYS` plus non-empty review keys; open schema (unknown keys ignored on parse)
- **Shape vs relations split** — list what parse **deliberately does not** check (same pattern as the domain/constraints "What parse time deliberately lets through" bullets): dangling entity/pattern/constraint ids, duplicate ids, empty `entity_ids` or `pattern_ids`, empty pattern collections, orphan entities, undischarged prioritized constraints — each owned by a gate step 3 lands

### Update existing sections

- **`## Path convention`** — add `<plans_dir>/roadmaps/<slug>/03-components.md` and name `components_path`, `COMPONENTS_FILENAME`.
- **`### The schema is open, and rendering is closed`** — add `COMPONENTS_ROW_KEYS` beside `DOMAIN_ROW_KEYS` / `CONSTRAINTS_ROW_KEYS`; name `render_components_artifact`.
- **`## The review collections`** — add `ComponentsArtifact` to the list of carriers (`DomainArtifact`, `ConstraintsArtifact`, and now components).
- **`### Shape — raises at parse time`** — add `parse_components_artifact` / `load_components_artifact` to the enforcing-functions sentence; extend the rules table only where components introduce new shape rules (mostly the same row/collection rules as constraints).
- **`### Relations — return violations`** — this is the largest edit:
  - **`ArtifactEnvelope`** — four slots: `domain` (always), optional `constraints`, optional `components`, optional `predecessor`; last-filled slot is under check; predecessor type matches under-check artifact (domain, constraints, or components).
  - **Gate inventory framing** — replace "eleven gates" as the whole story with **three stage gate sets** sharing one `Gate` signature. Keep the existing eleven-row table for the gates domain and constraints run; **append five rows** for the components traceability gates, each naming its `check_*` function and violation `kind`, and stating what the message names (including `row_id=None` for orphan-entity and empty-collection defects).
  - **`COMPONENTS_GATES` / `run_components_gates`** — document membership and order by reading the landed tuple (step 3 recommends: shared gates, then the five traceability gates, then decision/prose/revision gates — confirm at HEAD). State that `check_entity_fields`, `check_entity_references`, `check_attribute_totality`, and `check_constraint_anchors` are **not** in `COMPONENTS_GATES` — upstream artifacts were gated at their own stages.
  - **`check_duplicate_row_ids`** — note cross-artifact scope now includes components rows when the envelope carries all three artifacts.
- **`### What parse time deliberately lets through`** — add a components bullet list mirroring step 1's non-enforcement cases.
- **`## What is deliberately not enforced`** — add bullets aligned with the plan fence: no partition-quality gate, no pattern-merit gate, discharge required only for `prioritized` attributes (not `traded-away` / `not-load-bearing`).

### Runnable example under `## Examples`

Add `### `03-components.md`` **before** `### A revision, with feedback` so existing revision tests keep splitting at the same heading.

**Design constraints for the example (not optional):**

- **Same story as the shipped domain/constraints examples** — entity ids `order`, `payment`; constraint ids `constraint-checkout-latency`, `constraint-payment-audit-trail`; workflow/rule ids only in prose if needed, not on `ComponentRow.entity_ids`.
- **Gate 1** — every component names ≥1 defined entity id from that domain story.
- **Gate 2** — every domain entity appears on at least one component.
- **Gate 3** — both `system_patterns` and `component_patterns` non-empty on the artifact; every component has non-empty `pattern_ids` citing defined pattern ids (pattern ids resolve across **both** collections).
- **Gate 4** — every cited `constraint_ids` entry names a constraint id that exists in the constraints example (no dangling constraint refs).
- **Gate 5** — every constraint whose disposition attribute is `prioritized` appears in some component's `constraint_ids`; constraints on `traded-away` or `not-load-bearing` attributes need not be cited.
- **Shared gates** — at least one component row; every design-row id appears as a whole token in the prose body; decisions follow the same rejected-alternative contract as stages 1–2.
- **Placeholders** — use obvious placeholder ids (`pattern-audit-before-response`, `<one line>` bodies) rather than inventing a second domain; the gates check structure, not product fit.
- **Fence language** — ```markdown opening on `---` (load-bearing for the drift guard).

**Rejected alternative:** a standalone components example with its own domain/constraints ids. That makes `test_standalone_examples_clear_their_own_gates` either fail or fork a second domain story, and it trains operators to paste an example that does not compose with the doc's other examples.

**Optional (not required for green):** a components before/after revision pair under a **new heading** (e.g. `### A components revision, with feedback`) with its own test anchor constant. The domain revision pair already demonstrates review collections; defer a components revision demo unless the implementer wants full parity — see [Deferred](#deferred).

### `tests/test_roadmap_format.py` updates

**Parser dispatch — extend `_parse`:**

- After checking `\nentities:` and `\ndispositions:`, treat `\nsystem_patterns:` (or `\ncomponents:` if that is the safer unique key at HEAD) as components and return `(parse_components_artifact(block), run_components_gates)`.

**Imports — add** `parse_components_artifact`, `render_components_artifact`, and `run_components_gates`.

**Cases to add or extend:**

- `test_the_doc_still_ships_artifact_examples` — raise minimum from `>= 4` to `>= 5` (domain, constraints, components, revision before, revision after).
- `test_standalone_examples_clear_their_own_gates` — when the runner is `run_components_gates`, build `ArtifactEnvelope(domain=domain_example, constraints=constraints_example, components=artifact)` using the first domain and constraints examples parsed from the pre-revision section (same pattern as constraints needing domain today).
- `test_every_artifact_example_round_trips` *(new)* — for each ```markdown block, `parse(render(parse(block))) == parse(block)` using the matching renderer (`render_domain_artifact`, `render_constraints_artifact`, `render_components_artifact`). The doc prose claims round-trip; this pins it.
- `test_components_example_clears_run_components_gates` *(new, optional split)* — explicit three-artifact envelope case if not folded into the standalone test; asserts `[]` violations with helpful message list on failure.

**Do not break:**

- `_REVISION_HEADING = "### A revision, with feedback"` — revision tests assume exactly one split; insert the new first-run example **above** this heading.
- `test_every_closed_vocabulary_literal_the_doc_prints_is_real` — components introduce no new closed vocabularies beyond reused `DecisionStatus` / feedback enums; no change expected unless new literals appear in snippets.

### Symbol traceability (acceptance-critical)

Apply the bidirectional rule from accumulated lessons:

- **Doc → code:** every relation rule added in prose names its enforcing `check_*` or `parse_*` symbol.
- **Code → doc:** every `check_*` gate function and each of the five new traceability gates appears in `ROADMAP_FORMAT.md` (the shared revision gates stay documented once — do not duplicate rows for components if the rule text is identical).

One way to verify: compare `rg '^def check_' plan_tool/roadmap_gates.py` against `rg 'check_' ROADMAP_FORMAT.md` and reconcile intentional omissions (none expected for the five new gates).

### Constraints that are not free to vary

- **Non-code step** — zero diff in `plan_tool/`; if a symbol name in the doc does not match HEAD, fix the doc, not the code (unless code is genuinely wrong — then stop and reconcile upstream steps first).
- **No orchestrator or prompt authoring** — do not create `plan_tool/prompts/roadmap-components.md` or edit `plan_tool/roadmap.py`; step 5 owns those.
- **No partition-quality rules in prose** — document what gates check (id presence, coverage, discharge), not whether a decomposition is "right-sized."
- **Entity-id anchoring only** — document `ComponentRow.entity_ids` as entity ids only; do not document rule/workflow/decision/field-name anchor fields the plan rejected.
- **No closed pattern vocabulary** — patterns are free-text rows; do not invent a pattern catalog table.
- **Citation depth** — symbol names for steps 1–3 modules; path-only for orchestrator, CLI, and prompt files step 5–7 create.

## Tests

This step is **`change_type: non-code`** under a plan with `enforce_step_tests: true`. The test-authoring gate keys on `change_type` and does **not** apply here — no requirement to touch unrelated test modules beyond `tests/test_roadmap_format.py`.

### Verification (non-code step)

1. `uv run pytest tests/test_roadmap_format.py -q` — all cases pass, including new or extended ones.
2. `uv run pytest -m "not integration" tests/ -q` — full fast suite stays green (doc-only diff should not redden anything; run to confirm).
3. **Example parse** — every ```markdown artifact block in `ROADMAP_FORMAT.md` parses without `RoadmapArtifactError`.
4. **Example round-trip** — `test_every_artifact_example_round_trips` (or equivalent) passes for all blocks including the new components example.
5. **Example gates** — standalone first-run examples clear their stage runners; components clears `run_components_gates` with domain and constraints examples in the envelope.
6. **Revision pair unchanged** — `test_the_revision_example_clears_its_gates_against_its_predecessor` and `test_the_revision_example_actually_exercises_the_review_collections` still pass without retargeting the revision heading.
7. **Symbol existence** — `rg 'components_path|parse_components_artifact|run_components_gates|check_entity_component_coverage' ROADMAP_FORMAT.md` returns hits (adjust names to whatever step 1–3 actually shipped).
8. **No stale two-artifact claims** — `rg 'two markdown files|staged pair|eleven gates a stage' ROADMAP_FORMAT.md` returns nothing unless qualified as historical (prefer rewrite to present tense).
9. **No line-number anchors** — `rg 'plan_tool/roadmap_gates.py:[0-9]' ROADMAP_FORMAT.md` returns nothing.
10. **Land-on-code** — field names in the annotated schema match `COMPONENTS_ROW_KEYS` and `ComponentRow` / `PatternRow` fields at HEAD (`rg 'entity_ids|pattern_ids|constraint_ids' ROADMAP_FORMAT.md` aligns with step 1).

## Acceptance criteria

- Only `ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py` change; `plan_tool/` carries **zero diff**.
- `ROADMAP_FORMAT.md` documents `03-components.md` path (`components_path`, `COMPONENTS_FILENAME`), frontmatter schema (`COMPONENTS_ROW_KEYS`, `PatternRow`, `ComponentRow`), parse/render/load symbols, and the shape-vs-relations split for components.
- The doc's runnable `03-components.md` example parses, round-trips through `render_components_artifact`, and yields `[]` from `run_components_gates` when paired with the doc's existing domain and constraints examples in an `ArtifactEnvelope`.
- The relations section documents `ArtifactEnvelope.components`, `COMPONENTS_GATES`, `run_components_gates`, and **all five** components traceability `check_*` functions with violation kinds — read from HEAD, not from this detail file.
- Every `check_*` function in the five traceability gates appears in `ROADMAP_FORMAT.md`; reused gates (`check_duplicate_row_ids`, revision gates, etc.) are not duplicated with contradictory text.
- `test_the_doc_still_ships_artifact_examples` requires at least **five** ```markdown artifact blocks.
- `rg 'two markdown files' ROADMAP_FORMAT.md` returns nothing.
- `rg 'roadmap-components.md' ROADMAP_FORMAT.md` may name the prompt **path** only — no claim that the file exists until step 5 lands.
- `uv run pytest tests/test_roadmap_format.py -q` passes.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load` / `safe_dump` behavior for the annotated schema blocks and example frontmatter.
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — list and mapping rules for pattern and component rows.
- [dataclasses — Data Classes](https://docs.python.org/3/library/dataclasses.html) — field names on `PatternRow`, `ComponentRow`, and `ComponentsArtifact` to mirror in the schema section.
- [enum — Support for enumerations](https://docs.python.org/3/library/enum.html) — reused `DecisionStatus`, `FeedbackState`, and `ConstraintDisposition` literals that appear in components examples.

## Applicable guardrails

- **The plan's step intent.** This step makes the third artifact discoverable and copy-safe with rules traced to enforcing symbols — not runnable stage 3, not human proof on a real brief.
- **The plan's Out of scope — positions 04–05 and seed emission.** Do not document seed derivation, plan sizing, or lens rows.
- **The plan's Out of scope — partition quality as a gate.** Document binary id checks only; prose may explain reviewer judgment lives elsewhere, but must not imply a gate scores decomposition quality.
- **The plan's Out of scope — orchestrator / prompt / CLI wiring.** Name `plan_tool/roadmap.py` and `plan_tool/prompts/roadmap-components.md` by path only; do not document `STAGES` row fields or prompt variables step 5 owns.
- **The plan's Out of scope — second feedback channel.** Document the existing `feedback` / `removals` contract once; components uses the same channel.
- **Entity-id anchoring on components.** Document `entity_ids` as entity ids from `01-domain.md` only — the plan's settled 2026-08-02 decision.

## Deferred

- **`plan_tool/prompts/roadmap-components.md` authoring and containment tests** — step 5; prompt restates this schema inline because installed prompts cannot cite repo-root FORMAT docs.
- **`plan_tool/roadmap.py` stage table row and `--from-stage 3` behavior** — step 5.
- **A components revision before/after example pair** — optional doc depth; domain revision already demonstrates review collections, and adding a second revision subsection requires a new heading constant and test split — route here if omitted.
- **`CLAUDE.md`, `CAPABILITIES.md`, `RUNBOOK.md`, and walkthrough doc sweeps for three stages** — step 7's operator-doc reconciliation.
- **Human review run on a real 01/02 pair** — step 6.
