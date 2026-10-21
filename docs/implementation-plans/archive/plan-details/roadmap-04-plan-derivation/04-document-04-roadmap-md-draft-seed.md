> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Document 04-roadmap.md and draft-seed conventions in ROADMAP_FORMAT.md

## Summary

Extend `ROADMAP_FORMAT.md` so operators and agents can discover, hand-edit, and copy a conforming `04-roadmap.md` and its draft seeds without reading `plan_tool/roadmap_artifacts.py` or `plan_tool/roadmap_gates.py`. Add the fourth artifact's path convention, annotated frontmatter schema, plan-disposition vocabulary, shape-vs-relations rules, six traceability gate rows tied to the symbols step 3 lands, a dedicated draft-seed section (provenance frontmatter, slug-relative paths, bundle alignment), and one runnable ```markdown example that clears `run_plans_gates` against the doc's existing domain, constraints, and components examples plus an in-test `draft_seed_bundle`. Extend `tests/test_roadmap_format.py` so new examples parse, round-trip, run past the real gate aggregate, and cover draft-seed provenance parsing. The main design choice matches the FORMAT family: **the doc names the code that enforces each rule, and the code wins on disagreement** — wire names and kind constants are read off the landed modules at write time, not transcribed from plan prose. On green, an operator can paste the plans example verbatim, every new plan-relation gate function appears in the doc, and `uv run pytest tests/test_roadmap_format.py -q` passes with no production-code diff.

## Table of Contents

- [Summary](#summary) — what lands in the format doc and its drift guard
- [Why](#why) — why stage 4 needs a copy-safe schema reference before the orchestrator ships
- [Input](#input) — symbols and examples this step reads from steps 1–3
- [Files (creates vs edits)](#files-creates-vs-edits) — the two files this step touches
- [Implementation](#implementation) — doc sections, example design, test guard updates, and rules that are not free to vary
- [Tests](#tests) — verification checks for this non-code step
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run
- [References](#references) — docs worth skimming while authoring YAML examples
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step
- [Deferred](#deferred) — what later steps own

## Why

Steps 1–3 land the typed contract, widened envelope, and six plan-relation gates for `04-roadmap.md`, plus minimal draft-seed provenance parsing — but nothing in the repo yet tells an operator what to type. `ROADMAP_FORMAT.md` still describes three staged artifacts and sixteen relation gates; stage 4 adds a fourth artifact and a **side-output** draft-seed set that gates judge through `ArtifactEnvelope.draft_seed_bundle`, not through a fifth numbered markdown file. Without a gate-clean plans example and a draft-seed convention section wired through the same drift guard as stages 1–3, plan row keys, disposition vocabulary, ordering rules, and provenance frontmatter stay discoverable only from code. Step 6's prompt will restate the contract inline (prompts cannot cite repo-root FORMAT docs); this step makes the human-facing reference accurate before that restatement is authored.

## Input

Land steps **1**, **2**, and **3** before implementing. **Open `plan_tool/roadmap_artifacts.py` and `plan_tool/roadmap_gates.py` at HEAD and record what shipped — the landed names win over any name this plan or an earlier detail suggested.**

**From step 1 (`plan_tool/roadmap_artifacts.py`) — cite at symbol level:**

- Paths: `PLANS_FILENAME`, `DRAFT_SEEDS_DIRNAME`, `plans_path`, `draft_seeds_dir`, `resolve_draft_seed_path`
- Wire inventory: `PLANS_ROW_KEYS` (expected: `plans`, `ordering`, `assumptions`, `decisions`)
- Row types: `PlanRow`, `OrderingEntry`, `AssumptionRow`, `PlansArtifact`
- Closed vocabulary: `PlanDisposition` (`keep`, `merge`, `split`, `cross-cutting`)
- Slug mirror: `PLAN_ID_SLUG_RE` (must match `plan_tool/create.py:SLUG_RE` in tests — document the relationship, do not import `create` in the doc)
- Parse/render/load: `parse_plans_artifact`, `render_plans_artifact`, `load_plans_artifact`
- Design-row inventory: `plans_design_rows` — **plan, assumption, and decision rows only; ordering excluded**
- Draft-seed provenance: `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`, `DRAFT_SEED_CROSS_CUTTING_KEY`, `DraftSeedProvenance`, `parse_draft_seed_provenance` (and `render_draft_seed_provenance` if step 1 shipped it)
- Shared review rows: same `feedback` / `removals` / `decisions` shape as stages 1–3 (`REVIEW_ROW_KEYS`)

**From steps 2–3 (`plan_tool/roadmap_gates.py`) — cite at symbol level:**

- Envelope: `ArtifactEnvelope` with `domain`, `constraints`, `components`, `plans`, optional `draft_seed_bundle`, and `predecessor`; `artifact_under_check` / `filename_under_check` four-slot last-filled rule (`plans` → `components` → `constraints` → `domain`)
- Stage aggregate: `PLANS_GATES`, `run_plans_gates`
- Six plan-relation gates — **confirm function names and `VIOLATION_*` kind constants at HEAD** (step 3 detail proposes names like `check_plan_component_references`, `check_component_plan_coverage`, `check_draft_seed_provenance`, `check_draft_seed_bundle_alignment`, `check_plan_ordering_totality`, `check_assumption_plan_references`; the doc follows whatever landed)
- Shared gates reused in `PLANS_GATES`: `check_artifact_non_empty` (with `PlansArtifact` arm requiring non-empty `plans`), `check_duplicate_row_ids`, `check_decision_records`, `check_inventory_has_prose`, revision trio

**From the existing doc — keep and extend, do not rewrite from scratch:**

- Source-of-truth banner, `## See also` tail, annotated ```yaml schema blocks, ```markdown runnable examples under `## Examples`
- The order/payment/checkout fictional domain through **`03-components.md`** — the new plans example must cite **those** component ids (`component-checkout`, `component-payment`) so cross-artifact gates pass without inventing a second story

**Path-only references (steps 5–7 not landed — no function names):**

- `plan_tool/roadmap.py` — stage table, side-output lift, atomic draft-dir write
- `plan_tool/cli/roadmap_cmd.py` — `--apply` / `-y` apply-only mode
- `plan_tool/prompts/roadmap-plans.md` — stage-4 authoring prompt (step 6 creates this file)

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `ROADMAP_FORMAT.md` — widen the roadmap from three artifacts to four; add `04-roadmap.md` schema, draft-seed conventions, enforcement traceability for six new relation gates, and one gate-clean runnable plans example; update envelope, gate-set, path, and parse-time sections that still read as a three-stage trio
  - `tests/test_roadmap_format.py` — teach the drift guard to recognize, parse, round-trip, and gate-check a plans ```markdown example with a constructed `draft_seed_bundle`; add draft-seed provenance parsing coverage; fix the shared `disposition:` vocabulary check for two different enums; bump minimum example count

## Implementation

### Doc family checklist

Before editing, confirm each FORMAT-family element individually:

- **Source-of-truth banner** — keep; update the gate-count clause from "sixteen `check_*` functions across three tuples" to language naming **four stage gate sets** and the total relation-gate inventory step 3 adds (expect **twenty-two** `check_*` functions across four tuples — confirm with `rg '^def check_' plan_tool/roadmap_gates.py` at HEAD).
- **`## See also`** — keep the existing tail; add a cross-link to `SEED_FORMAT.md` in the new draft-seeds section if not already sufficient in See also.
- **Annotated ```yaml schema** — add one for `04-roadmap.md` frontmatter and one for draft-seed **provenance** frontmatter (not the full seed body).
- **Runnable ```markdown examples** — add one first-run `04-roadmap.md` block; retag only examples meant to round-trip (never annotated schema blocks).

### Global sweeps (do these before calling the step done)

- **Three → four artifacts** — opening paragraph ("three markdown files"), "staged" wording, path convention block, "What writes them" (name the fourth prompt file by **path only**), gate-count claims, and `ArtifactEnvelope` field list
- **No line numbers as anchors** — cite `parse_plans_artifact`, `check_component_plan_coverage`, etc.; never `plan_tool/roadmap_gates.py:1234`
- **Land-on-code for every wire name** — if step 1 renamed a field, the doc follows the module
- **Present tense, forward-looking** — describe what the contract **is**, not what "used to" ship

### New section: `## `04-roadmap.md` — frontmatter schema`

Add after the `03-components.md` schema section (before review collections if that preserves 01→02→03→04 ordering).

Document, grounded in step 1's landed types:

- **Purpose** — maps components to an ordered plan list with closed dispositions; carries ordering, inter-plan assumptions, and review collections; plan row `id` is also the `create` slug in printed next-steps
- **Annotated ```yaml block** — collections:
  - `plans` — `PlanRow`: `id`, `title`, `disposition`, `component_ids` (optional list; may be empty only when disposition is `cross-cutting`), `draft_seed_path` (required relative path from the **roadmap slug root**, e.g. `seeds/checkout-core.md`), `sizing_rationale`
  - `ordering` — `OrderingEntry`: `plan_id`, optional `depends_on`, optional `assumption_targets` (ordering-level plan-id references; **not** assumption inventory rows)
  - `assumptions` — `AssumptionRow`: `id`, `statement`, `consuming_plan_ids`
  - `decisions` — same row shape as stages 1–3
  - `feedback` / `removals` — same review contract; attach to `PlansArtifact`
- **Parsing** — `parse_plans_artifact` / `load_plans_artifact` into frozen `PlansArtifact`; ordered tuples, not dicts keyed by id; `ordering` stays an ordered sequence
- **Rendering** — `render_plans_artifact` emits only `PLANS_ROW_KEYS` plus non-empty review keys; open schema (unknown keys ignored on parse)
- **Design-row inventory** — `plans_design_rows` for prose and continuity gates: plans, assumptions, decisions — **ordering entries mint no row ids**
- **Shape vs relations split** — bullet list of what parse **deliberately does not** check (mirror step 1's non-enforcement cases): dangling component ids, duplicate ids, ordering totality, slug shape, draft-bundle alignment, provenance component ids not on the plan row, unknown plan ids in `depends_on` / `consuming_plan_ids` — each owned by a step 3 gate

### New section: `## Draft seeds — side output under the roadmap slug`

Draft seeds are **not** a fifth numbered roadmap artifact. They are markdown files the stage emits beside `04-roadmap.md`, judged in-memory via `ArtifactEnvelope.draft_seed_bundle` before disk write.

Document:

- **Default location** — `<plans_dir>/roadmaps/<slug>/seeds/` via `DRAFT_SEEDS_DIRNAME`; `draft_seeds_dir(plans_dir, slug)`; each plan row's `draft_seed_path` is relative to the slug directory (`resolve_draft_seed_path` validates segment safety — no absolute paths or `..`)
- **In-run bundle** — during stage 4, lifted seed text is keyed by **`Path(draft_seed_path).name`** (basename only); gates 3–4 read `draft_seed_bundle`, not disk
- **Provenance frontmatter (gates scan this)** — annotated ```yaml block naming `DRAFT_SEED_ROADMAP_COMPONENTS_KEY` (`roadmap_components`: required list of component ids) and optional `DRAFT_SEED_CROSS_CUTTING_KEY` (`cross_cutting: true`); parsed by `parse_draft_seed_provenance`; **shape only** — relation checks (declared ids resolve to the owning plan row's `component_ids`, cross-cutting flag matches disposition) are gates, not parse errors
- **Seed body** — pointer to `SEED_FORMAT.md` for the scope-contract fence and authoring density; state explicitly what **no gate checks**: Outcome quality, agreement between seed body and roadmap prose beyond inventory id presence, seed length, plan count
- **After `--apply`** — one sentence that promoted copies under `plan-seeds/` drop the provenance block (step 7 owns copy semantics); name `plan_tool/cli/roadmap_cmd.py` by path only
- **Rejected alternative:** documenting draft seeds only inside the `04-roadmap.md` example without a dedicated section — operators pasting provenance snippets would miss the basename-keyed bundle contract

### Update existing sections

- **`## Path convention`** — add `04-roadmap.md` and the default `seeds/` subtree; name `plans_path`, `PLANS_FILENAME`, `DRAFT_SEEDS_DIRNAME`
- **`### The schema is open, and rendering is closed`** — add `PLANS_ROW_KEYS` and `render_plans_artifact`
- **`## Closed vocabularies`** — add **Plan disposition** — `PlanDisposition` table (`keep`, `merge`, `split`, `cross-cutting`) with brief meanings; note **`disposition` on a plan row is not the same key as constraint disposition** on a `02-constraints.md` disposition row (same YAML key, different enums — the drift guard must disambiguate; see Tests)
- **`## The review collections`** — add `PlansArtifact` to carriers
- **`### Shape — raises at parse time`** — add `parse_plans_artifact` / `load_plans_artifact`; extend rules table for plan-specific shape rows (`PlanDisposition` coercion, required `draft_seed_path`, ordering entry shape)
- **`### Relations — return violations`** — largest edit:
  - **`ArtifactEnvelope`** — five data fields: `domain`, optional `constraints`, optional `components`, optional `plans`, optional `draft_seed_bundle`, optional `predecessor`; last-filled artifact slot is under check; predecessor type matches (`PlansArtifact` at stage 4)
  - **`check_duplicate_row_ids`** — plan, assumption, and decision ids join the cross-artifact uniqueness scope; **plan ids must not reuse component or other upstream design-row ids**
  - **Gate inventory framing** — document **four** stage gate sets; append **six rows** for plan-relation gates with `check_*`, violation `kind`, and message anchors (including `row_id=None` for uncovered-component and missing-ordering defects)
  - **`PLANS_GATES` / `run_plans_gates`** — document membership and order by reading the landed tuple (step 3 recommends: shared gates, then six plan-relation gates, then decision/prose/revision gates — confirm at HEAD). State that domain-only, constraints-only, and components-only gates are **not** in `PLANS_GATES` — upstream artifacts were gated at their own stages
- **`### What parse time deliberately lets through`** — add plans bullet list and draft-seed provenance bullet list mirroring step 1 non-checks
- **`## What is deliberately not enforced`** — add bullets aligned with the plan fence: no disposition-merit gate, no seed prose quality gate, no plan-count cap, `cross-cutting` does not excuse uncovered components (gate 2 vs gate 1 split), no gate keyed on "should have been one plan"

### Runnable example under `## Examples`

Add `### `04-roadmap.md`` **before** `### A revision, with feedback` so revision tests keep splitting at the same heading.

**Design constraints for the example (not optional):**

- **Same story as the shipped domain/constraints/components examples** — plan rows reference `component-checkout` and `component-payment`; every component id from the components example appears on at least one plan row
- **Plan ids** — satisfy `PLAN_ID_SLUG_RE` / create slug rules (e.g. `checkout-core`, `payment-core`); **do not reuse component ids as plan ids**
- **Gate 1** — each non-`cross-cutting` plan names ≥1 valid `component_id`; if the example includes a `cross-cutting` plan, it may omit `component_ids`
- **Gate 2** — both components covered
- **Gates 3–4** — every plan row has a `draft_seed_path`; the **test suite** builds `draft_seed_bundle` keyed by basename with provenance frontmatter listing that row's `component_ids` (the doc example alone cannot satisfy bundle gates without the test attaching the bundle — state this in Implementation comments for the implementer)
- **Gate 5** — `ordering` lists every plan id exactly once; `depends_on` / `assumption_targets` reference defined plan ids
- **Gate 6** — at least one assumption row whose `consuming_plan_ids` resolve
- **Shared gates** — non-empty `plans`; every `plans_design_rows` id appears as a whole token in prose; decision row follows rejected-alternative contract
- **Fence language** — ```markdown opening on `---`

**Rejected alternative:** a standalone plans example with its own component story — breaks composition with the doc's upstream examples and fails `run_plans_gates`.

**Draft-seed provenance example** — under the draft-seeds section, add one minimal ```markdown block (full seed file: provenance frontmatter + stub body) tested by a **heading-split helper**, not `_ARTIFACT_BLOCK` (draft seeds are not plans artifacts). Use placeholder ids aligned with the plans example.

### `tests/test_roadmap_format.py` updates

**Imports — add** from `plan_tool.roadmap_artifacts`: `PlanDisposition`, `parse_plans_artifact`, `render_plans_artifact`, `parse_draft_seed_provenance`, and provenance key constants if referenced in tests. From `plan_tool.roadmap_gates`: `run_plans_gates`.

**Parser dispatch — extend `_parse`:**

- After existing shape checks, if `\nplans:` in frontmatter → `(parse_plans_artifact(block), run_plans_gates)`

**Extend `_render`** with a `run_plans_gates` arm calling `render_plans_artifact`.

**Fix `disposition:` vocabulary check** — `_VOCAB_BY_KEY["disposition"]` cannot stay mapped only to `ConstraintDisposition`. For each fenced block, if the frontmatter contains `\nplans:`, validate `disposition:` lines against `PlanDisposition`; elif `\ndispositions:`, against `ConstraintDisposition`; else skip or use constraints default for orphan snippets. Pin with a case that would fail if `keep` were checked against `ConstraintDisposition`.

**Draft-seed test anchor** — add a constant like `_DRAFT_SEED_HEADING = "## Draft seeds"` (or the exact heading chosen) and `test_draft_seed_provenance_examples_parse` splitting there, parsing ```markdown bodies through `parse_draft_seed_provenance`.

**Bundle builder helper** — private function that, given a `PlansArtifact`, returns `dict[str, str]` mapping each plan row's basename to minimal seed text with valid provenance listing that row's `component_ids`.

**Cases to add or extend:**

- `test_the_doc_still_ships_artifact_examples` — raise minimum from `>= 5` to `>= 6`
- `test_standalone_examples_clear_their_own_gates` — when runner is `run_plans_gates`, build `ArtifactEnvelope(domain=…, constraints=…, components=…, plans=artifact, draft_seed_bundle=helper(artifact))` using first domain, constraints, and components examples from the pre-revision section
- `test_plans_example_clears_run_plans_gates_with_bundle` *(optional explicit case)* — same envelope assertion with helpful violation message list on failure
- `test_draft_seed_provenance_examples_parse` — provenance blocks under draft-seeds heading parse without error

**Do not break:**

- `_REVISION_HEADING = "### A revision, with feedback"` — insert the new first-run example **above** this heading
- Existing domain/constraints/components/revision cases stay green

### Symbol traceability (acceptance-critical)

- **Doc → code:** every new relation rule in prose names its enforcing `check_*` or `parse_*` symbol
- **Code → doc:** every **new** plan-relation `check_*` from step 3 appears in `ROADMAP_FORMAT.md` with its violation kind; reused shared gates stay documented once — no contradictory duplicate rows

Verify: compare `rg '^def check_' plan_tool/roadmap_gates.py` against `rg 'check_' ROADMAP_FORMAT.md` and reconcile — expect six new gate names documented; domain/constraints/components-only gates remain documented in the shared table without claiming they run on the plans stage.

### Constraints that are not free to vary

- **Non-code step** — zero diff in `plan_tool/`; if a symbol in the doc does not match HEAD, fix the doc (or stop and reconcile upstream steps first)
- **No orchestrator, prompt, or CLI authoring** — do not create `plan_tool/prompts/roadmap-plans.md` or edit `plan_tool/roadmap.py` / `roadmap_cmd.py`
- **No merit gates in prose** — document id-presence and alignment rules only; do not imply a gate scores decomposition or seed Outcomes
- **Citation depth** — symbol names for steps 1–3 modules; path-only for orchestrator, lift path, `--apply`, and prompt files steps 5–7 create
- **Draft bundle is test-constructed** — the doc's plans ```markdown example does not embed the in-memory bundle; tests attach it — document that split so implementers do not try to gate-check the example without the helper

## Tests

This step is **`change_type: non-code`** under a plan with `enforce_step_tests: true`. The test-authoring gate keys on `change_type` and does **not** apply here.

### Verification (non-code step)

1. `uv run pytest tests/test_roadmap_format.py -q` — all cases pass, including new or extended ones
2. `uv run pytest -m "not integration" tests/ -q` — fast suite stays green (doc-only diff)
3. **Example parse** — every ```markdown artifact block parses without `RoadmapArtifactError`
4. **Example round-trip** — all artifact blocks including the new plans example round-trip through the matching renderer
5. **Example gates** — standalone first-run examples clear their stage runners; plans clears `run_plans_gates` with domain, constraints, components examples and a conforming `draft_seed_bundle`
6. **Draft-seed provenance** — provenance example(s) parse through `parse_draft_seed_provenance`
7. **Revision pair unchanged** — revision tests pass without retargeting `_REVISION_HEADING`
8. **Symbol existence** — `rg 'parse_plans_artifact|run_plans_gates|PlanDisposition|parse_draft_seed_provenance' ROADMAP_FORMAT.md` returns hits (adjust to landed names)
9. **No stale three-artifact claims** — `rg 'three markdown files|sixteen .check_' ROADMAP_FORMAT.md` returns nothing unqualified
10. **No line-number anchors** — `rg 'plan_tool/roadmap_[a-z]+.py:[0-9]' ROADMAP_FORMAT.md` returns nothing
11. **Land-on-code** — field names in annotated schema match `PLANS_ROW_KEYS` and row dataclass fields at HEAD
12. **Bidirectional gate traceability** — each of the six new plan-relation `check_*` functions at HEAD appears in `ROADMAP_FORMAT.md`; `rg 'check_plan_component_references|check_component_plan_coverage|check_draft_seed_provenance|check_draft_seed_bundle_alignment|check_plan_ordering_totality|check_assumption_plan_references' ROADMAP_FORMAT.md` matches landed names (adjust if step 3 renamed them)
13. **Disposition vocab disambiguation** — `keep` / `merge` / `split` / `cross-cutting` in the plans example do not fail the closed-vocabulary test

## Acceptance criteria

- Only `ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py` change; `plan_tool/` carries **zero diff**
- `ROADMAP_FORMAT.md` documents `04-roadmap.md` paths (`plans_path`, `PLANS_FILENAME`), frontmatter schema (`PLANS_ROW_KEYS`, `PlanRow`, `OrderingEntry`, `AssumptionRow`), `PlanDisposition`, parse/render/load symbols, and the shape-vs-relations split for plans
- The doc documents draft-seed conventions: slug-relative paths, `DRAFT_SEEDS_DIRNAME`, provenance keys, `parse_draft_seed_provenance`, basename-keyed `draft_seed_bundle`, and pointer to `SEED_FORMAT.md` for seed body fences
- The runnable `04-roadmap.md` example parses, round-trips through `render_plans_artifact`, and yields `[]` from `run_plans_gates` when paired with the doc's domain, constraints, and components examples and a test-built conforming `draft_seed_bundle`
- The relations section documents four-slot `ArtifactEnvelope`, `PLANS_GATES`, `run_plans_gates`, and **all six** plan-relation `check_*` functions with violation kinds — read from HEAD
- Source-of-truth banner gate count matches `rg -c '^def check_' plan_tool/roadmap_gates.py` at HEAD
- `test_the_doc_still_ships_artifact_examples` requires at least **six** ```markdown artifact blocks
- `rg 'three markdown files' ROADMAP_FORMAT.md` returns nothing
- `uv run pytest tests/test_roadmap_format.py -q` passes

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — `safe_load` / `safe_dump` for annotated schema blocks and example frontmatter
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — list and mapping rules for plan, ordering, and assumption rows
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — field names on `PlanRow`, `OrderingEntry`, `AssumptionRow`, and `PlansArtifact`
- [enum — Support for enumerations (Python 3.13)](https://docs.python.org/3.13/library/enum.html) — `PlanDisposition` and reused decision/feedback enums
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — `Path(draft_seed_path).name` for bundle keys; slug-dir composition

## Applicable guardrails

- **The plan's step intent.** Make the fourth artifact and its draft-seed sidecar discoverable, copy-safe, and traceable to enforcing symbols — not runnable stage 4, not human proof on a real brief
- **The plan's Out of scope — merit and quality gates.** Document binary id and alignment checks only; never state or imply a gate judges disposition choice, seed Outcome quality, plan count, or seed length
- **The plan's Out of scope — auto-create and seed emission mechanics.** Document what draft seeds contain and where they live; do not document `--apply` copy behavior, collision policy, or printed `create` lines beyond one forward pointer (step 7 owns apply; step 6 owns next-steps printing)
- **The plan's Out of scope — orchestrator / lift / prompt wiring.** Name `plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-plans.md`, and lift mechanics by path only; do not document `STAGES` row fields or multi-fence reply shape (step 5–6)
- **The plan's Out of scope — rewriting stages 1–3.** Extend docs; do not change feedback lifecycle prose except adding `PlansArtifact` as a carrier

## Deferred

- **`plan_tool/prompts/roadmap-plans.md` authoring and containment tests** — step 6; prompt restates this schema inline
- **Side-output lift and atomic draft-dir rewrite** — step 5 (lift) and step 6 (write path)
- **`--apply`, `-y`, collision policy, and `docs/cli/roadmap.md`** — step 7
- **A plans revision before/after example pair** — optional; domain revision already demonstrates review collections
- **`CLAUDE.md`, `CAPABILITIES.md`, `RUNBOOK.md`, `docs/ROADMAP_WALKTHROUGH.md`, and walkthrough § 5 automation claims** — step 10 operator-doc sweep (banner still says three artifacts until then)
- **Human review run on real 01/02/03** — step 9
- **`create` SplitProposal roadmap pointer** — step 8
