> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Add stage-4 relation gates and `run_plans_gates`

## Summary

Ship the fourth stage gate set in `plan_tool/roadmap_gates.py`: six new plan-relation checks over `PlansArtifact`, upstream `03-components.md`, and the envelope's `draft_seed_bundle`, plus `PLANS_GATES` and `run_plans_gates` wired like the three existing stage runners. Reuse the shared shape/revision tuple stages 1–3 already run (`check_artifact_non_empty` with its `PlansArtifact` arm from step 2, duplicate ids, decision records, inventory-has-prose, design-row continuity, feedback integrity, settled decisions) and append the plan-relation gates in the middle, after duplicate-id checking and before the decision-record gate. Every new check is plans-stage-only (returns `[]` when `artifact_under_check` is not a `PlansArtifact`), emits retry-ready `Violation` messages keyed by row id or expected id, and judges ids only — never disposition merit, seed prose quality, or plan count. On green, `run_plans_gates(plans_envelope())` is empty for a conforming hand-built envelope, all existing gate tests stay green, and the module remains a stdlib-plus-one leaf.

## Table of Contents

- [Summary](#summary) — what lands and the observable green state
- [Table of Contents](#table-of-contents) — section index
- [Why](#why) — gap this step closes
- [Input](#input) — contracts from steps 1, 2, and 5 this step reads
- [Files (creates vs edits)](#files-creates-vs-edits) — touched paths only
- [Implementation](#implementation) — gate design, tuple wiring, message rules
- [Tests](#tests) — new cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — external docs for enums, paths, YAML
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — explicitly later steps

## Why

Steps 1–2 give `04-roadmap.md` a typed shape and widen `ArtifactEnvelope` so plan, assumption, and decision ids join duplicate-id and revision gates; step 5 attaches lifted draft-seed text on `draft_seed_bundle`. Nothing at HEAD runs plan-relation checks: a stage-4 reply could omit component coverage, cite components nowhere in seeds, leave ordering incomplete, advertise draft paths with no bundle entry, or ship plan ids that fail `create`'s slug rule — and every shared gate would pass vacuously or never run. This step is the deterministic acceptance layer for those six observables from the plan architecture, exported as `PLANS_GATES` / `run_plans_gates` for step 6's stage table to hold by identity.

## Input

Land steps **1**, **2**, and **5** before implementing; this step reads their outputs but does not edit their files.

**From step 1 (`plan_tool/roadmap_artifacts.py`):**

- **`PlansArtifact`**, **`PlanRow`**, **`OrderingEntry`**, **`AssumptionRow`**, **`PlanDisposition`** — row shapes and closed disposition vocabulary (`keep`, `merge`, `split`, `cross-cutting`).
- **`PLANS_FILENAME`**, **`plans_design_rows`** — filename constant and design-row enumerator (plan + assumption + decision; ordering excluded).
- **`PLAN_ID_SLUG_RE`** — local mirror of `plan_tool/create.py:SLUG_RE`; gate 5 uses this, not an import from `create.py`.
- **`parse_draft_seed_provenance`**, **`DRAFT_SEED_ROADMAP_COMPONENTS_KEY`**, **`DRAFT_SEED_CROSS_CUTTING_KEY`** — minimal draft-seed frontmatter parser and wire-key names for gate 3.
- **`PlanRow.draft_seed_path`** — relative path from the roadmap slug root; gate 4 keys the bundle by **`Path(draft_seed_path).name`** (basename only).

**From step 2 (`plan_tool/roadmap_gates.py`):**

- **`ArtifactEnvelope.plans`**, **`ArtifactEnvelope.draft_seed_bundle`**, widened **`artifact_under_check`** / **`filename_under_check`**, **`_rows_of`** / **`_envelope_rows`** plans arms, and the **`PlansArtifact`** branch of **`check_artifact_non_empty`** (non-empty `plans` inventory).
- **`draft_seed_bundle`** contract: optional `Mapping[str, str]` keyed by basename; `None` means no bundle attached; `{}` is valid data gates 3–4 judge.

**From step 5 (`plan_tool/roadmap.py`):**

- Side-output lift fills **`draft_seed_bundle`** before gates run on stage 4. This step does not implement lift; tests hand-build the mapping. Production order is lift → gates → write.

**Landed names win** over any name this plan or an earlier detail proposed — read both modules at HEAD when implementing.

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `plan_tool/roadmap_gates.py` — mint plan-relation violation kind constants; add six `check_*` gate functions; declare `PLANS_GATES` and `run_plans_gates`; extend imports from `plan_tool.roadmap_artifacts`; update module docstring to name stage 4 and `run_plans_gates`
  - `tests/test_roadmap_gates.py` — extend imports; add `make_plans` / `plans_envelope` helpers if step 2 did not already land them; add plan-relation gate cases, tuple-order guard, inert-off-plans-stage guard, conforming `run_plans_gates` smoke test, and one parsed-text seam test for plans

## Implementation

### Design stance

- **Same call shape as stages 1–3.** `run_plans_gates(envelope)` delegates to `_run_gates(PLANS_GATES, envelope)`. Step 6's stage table holds the tuple by identity — no wrapper, no orchestrator branch (rejected alternative).
- **Plans-stage-only relation gates.** Each new `check_*` starts with `if not isinstance(envelope.artifact_under_check, PlansArtifact): return []`, matching components traceability gates. Upstream **`envelope.components`** is read to resolve component ids, never re-judged.
- **Bundle is judged, not read from disk.** Gates 3–4 read **`envelope.draft_seed_bundle`** only. Disk alignment after a green write is step 5/6's writer contract; gate 4 checks inventory pointers against the in-memory bundle the retry loop already holds.
- **Relations over ids, never merit.** No gate inspects sizing rationale text, disposition choice, seed body quality, plan count, or whether a merge should have been a split. Optional business-rule/workflow assignment inventory stays ungated unless the plan later adds a binary id-coverage rule (it does not in this position).
- **Plan-vs-component id disjointness is already enforced.** `check_duplicate_row_ids` unions ids across `_envelope_rows`; a plan id reusing a component id is a duplicate-id violation, not a separate gate. Retry messages should not suggest echoing component ids as plan slugs (plan architecture note).

### Violation kind constants

Mint one **`VIOLATION_*`** string token per new rule beside the existing constants block. Names should read clearly in retry bullets (e.g. kinds along the lines of `no-component-reference`, `undefined-component-reference`, `uncovered-component`, `draft-seed-provenance`, `undefined-seed-component-reference`, `missing-draft-seed-bundle-entry`, `dangling-draft-seed-bundle-entry`, `invalid-plan-id-slug`, `ordering-plan-id-duplicate`, `missing-ordering-plan-id`, `undefined-ordering-plan-reference`, `undefined-assumption-plan-reference`). Step 4 documents each token in `ROADMAP_FORMAT.md`; this step ships the constants and messages only.

### The six plan-relation gates (architecture observables 1–6)

Implement as separate functions (names are implementer's choice; one function per observable keeps tuple order obvious). All messages are **retry text**: self-contained, name every id involved, cite **`PLANS_FILENAME`** / **`COMPONENTS_FILENAME`** by filename constant, **no line numbers**.

**Gate 1 — plan row → component id (`check_plan_component_references` or similar)**

- For each **`PlanRow`** in the artifact under check:
  - If **`disposition`** is **`PlanDisposition.CROSS_CUTTING`** (`cross-cutting`): **`component_ids` may be empty**. When non-empty, every listed id must still resolve in the components inventory (same undefined-component check as non-cross-cutting rows).
  - Otherwise: require **at least one** **`component_id`**, and **every** listed id must exist on a row in **`envelope.components.components`**.
- **Cardinality:** report **every** bad or missing reference, not the first only.
- **`cross-cutting` is not a substitute for listing a component id** when disposition is not cross-cutting (architecture gate 1 vs gate 2 split).

**Gate 2 — component id → plan row (`check_component_plan_coverage` or similar)**

- Build the set of component ids claimed across all plan rows' **`component_ids`**.
- For **every** **`ComponentRow.id`** in **`envelope.components`**, require membership in that set.
- **`cross-cutting` plans do not excuse an unlisted component** — gate 2 is totality over `03-components.md`, independent of disposition.
- Absence violations use **`row_id=None`** and name the **expected component id** in the message (the missing-row fallback anchor rule).

**Gate 3 — draft-seed provenance (`check_draft_seed_provenance` or similar)**

- Requires **`draft_seed_bundle`** and plan rows; iterate each plan row, look up **`Path(plan_row.draft_seed_path).name`** in the bundle, parse value with **`parse_draft_seed_provenance`**.
- **Never raise from a gate function** — convert parser shape failures into **`Violation`** entries naming the plan row id and the basename.
- **Required:** provenance block with **`roadmap_components`** (step 1 parser enforces list shape).
- **Declared component ids must resolve:** each id in **`roadmap_components`** must appear on the **owning plan row's `component_ids`**, unless the seed declares **`cross_cutting: true`** via **`DRAFT_SEED_CROSS_CUTTING_KEY`** on a plan row whose disposition is **`cross-cutting`**. A seed listing a component id the plan row does not carry violates (step 1's "provenance listing component ids not on the plan row" non-check at parse time).
- Do **not** validate seed body prose, `SEED_FORMAT.md` fence completeness, or whether provenance lists *every* component on the plan row unless you add an explicit bidirectional rule — the plan's observable 3 is declaration + resolve, not prose quality.

**Gate 4 — plan row ↔ bundle bijection (`check_draft_seed_bundle_alignment` or similar)**

- **Every plan row:** basename of **`draft_seed_path`** must exist as a key in **`draft_seed_bundle`** (when bundle is **`None`**, treat as no keys — every plan row violates missing entry).
- **Every bundle key:** must match the basename of **exactly one** plan row's **`draft_seed_path`**; extra keys are dangling entries.
- One violation per offending plan row or dangling key; message names the plan row id and/or basename and the correction.

**Gate 5 — ordering inventory + slug shape (`check_plan_ordering_totality` or similar; may split slug check if clearer)**

Two sub-rules in one gate or two gates — either is fine if **`PLANS_GATES`** order stays stable and tests pin behavior.

- **Ordering totality / bijection:** collect plan ids from **`artifact.plans`**. Every id must appear **exactly once** as **`OrderingEntry.plan_id`** across **`artifact.ordering`**, and every **`OrderingEntry.plan_id`** must be a plans-inventory id (no phantom ordering rows). Keep the ordered tuple — detect duplicates and omissions from the raw sequence. **`depends_on`** and **`assumption_targets`** on each ordering entry must name plan ids present in the plans inventory **and appear earlier in `artifact.ordering` than that entry's `plan_id`**. (`assumption_targets` is reviewer metadata only for seeds/handoff — still gated for id presence and sequence.)
- **Slug shape:** every plan row **`id`** must satisfy **`PLAN_ID_SLUG_RE.fullmatch`**. Violation names the offending **`id`** string and points authors at create-compatible slug rules without importing **`create.py`**.

**Gate 6 — assumption consumers (`check_assumption_plan_references` or similar)**

- For each **`AssumptionRow`**, every id in **`consuming_plan_ids`** must exist in the plans inventory (`{row.id for row in artifact.plans}`).
- Report every undefined consumer id; message names assumption row id and missing plan id.

### `PLANS_GATES` tuple order

Mirror **`COMPONENTS_GATES`**: shared gates first, stage-specific relation gates in the middle, shared revision tail last. Recommended order:

1. `check_artifact_non_empty`
2. `check_duplicate_row_ids`
3. Gates 1–6 (component refs, component coverage, seed provenance, bundle alignment, ordering/slug, assumption refs — in that order)
4. `check_decision_records`
5. `check_inventory_has_prose`
6. `check_design_row_continuity`
7. `check_feedback_integrity`
8. `check_settled_decisions`

Add **`run_plans_gates`** with the same docstring pattern as **`run_components_gates`** (names `04-roadmap.md`, notes intentional call-shape parity for the stage table).

### Message and emission rules (not free to vary)

- **Retry-channel contract** — modelled on **`plan_tool/detail.py:_jira_retry_suffix`**: each message stands alone as a `- {message}` bullet; no report framing.
- **Reference gates:** emit **every** offender.
- **Duplicate ordering plan ids:** emit **once per duplicated id**, not once per occurrence (same cardinality as **`check_duplicate_row_ids`**).
- **Absence defects:** when no row exists to cite, anchor on the **expected id** (component id, plan id, basename).
- **Artifact field on `Violation`:** use **`PLANS_FILENAME`** for plan-row defects; use **`COMPONENTS_FILENAME`** for gate-2 uncovered-component messages (the retried stage rewrites plans, but the missing claim is about component coverage — follow **`check_entity_component_coverage`**, which cites **`COMPONENTS_FILENAME`** with **`row_id=None`**).

### Shared locations (this step does not edit)

- **`plan_tool/roadmap.py`** — step 6 adds the stage-4 `STAGES` row holding **`run_plans_gates`** by identity; step 5's lift fills **`draft_seed_bundle`** before the gate call.
- **`ROADMAP_FORMAT.md`** — step 4 documents each new kind token and rule; traceability criterion runs both directions there.
- **`plan_tool/create.py:SLUG_RE`** — authoritative slug definition; this module uses **`PLAN_ID_SLUG_RE`** from the artifact leaf only.
- **Components traceability gates** — unchanged; stay inert when plans is under check because they early-return on artifact type.

### Constraints that are not free to vary

- **Leaf discipline** — still exactly one first-party import (`plan_tool.roadmap_artifacts`). No import of **`plan_tool/roadmap.py`**, **`plan_tool/create.py`**, or **`plan_tool/gates.py`** (the shell-command suggester — unrelated module).
- **No orchestrator or CLI edits** in this step.
- **Gate functions never raise** — return **`list[Violation]`** only.
- **Do not re-open step 2 envelope work** — assume **`PlansArtifact`** non-empty arm and four-slot **`artifact_under_check`** already landed.

## Tests

All cases live in `tests/test_roadmap_artifacts.py`'s sibling **`tests/test_roadmap_gates.py`**. Build fixtures from dataclasses directly; do not route cases through text parsers except the one seam test below. Every new test and every existing test in the file must pass before this step is done.

### Tests for this step

**Fixtures (add or extend step 2 helpers)**

- `make_plans` — minimal conforming **`PlansArtifact`**: ≥1 plan row with valid **`draft_seed_path`**, **`component_ids`** matching upstream **`COMPONENT_ONE`**, ordering covering every plan id once, assumption row with valid **`consuming_plan_ids`**, decision row, prose naming every **`plans_design_rows`** id
- `plans_envelope` — full four-artifact envelope (domain, constraints, components, plans) plus **`draft_seed_bundle`** keyed by each plan row's basename with provenance frontmatter listing that row's component ids; defaults mirror **`components_envelope`**

**Aggregate smoke**

- `test_run_plans_gates_clears_a_conforming_envelope` — `run_plans_gates(plans_envelope()) == []`
- `test_plans_gates_tuple_includes_relation_gates_in_order` — slice of **`PLANS_GATES`** from first plan-relation gate through last matches declared order
- `test_plan_relation_gates_are_inert_off_plans_stage` — each new plan-relation gate returns `[]` on **`components_envelope()`** and **`constraints_envelope()`**

**Gate 1 — plan → component**

- `test_plan_with_defined_component_ids_passes` — non-cross-cutting plan listing valid component id passes gate 1
- `test_plan_with_empty_component_ids_violates` — non-cross-cutting plan with no component ids emits **`no-component-reference`** (or landed kind)
- `test_plan_referencing_undefined_component_violates` — bad component id on plan row
- `test_every_undefined_component_reference_on_plans_is_reported` — two bad ids → two violations
- `test_cross_cutting_plan_may_omit_component_ids` — **`PlanDisposition.CROSS_CUTTING`** with empty **`component_ids`** passes gate 1
- `test_cross_cutting_plan_with_undefined_component_violates` — cross-cutting row listing a bogus component id still fails

**Gate 2 — component → plan**

- `test_component_covered_by_plan_passes` — every component id listed on a plan passes gate 2
- `test_uncovered_component_violates` — component id absent from all plan rows; message names component id, **`row_id is None`**
- `test_cross_cutting_plan_does_not_cover_component` — cross-cutting plan alone does not satisfy coverage for a component still unlisted

**Gate 3 — seed provenance**

- `test_draft_seed_with_valid_provenance_passes` — bundle entry parses and lists plan row's component ids
- `test_draft_seed_missing_roadmap_components_violates` — bundle text without required key
- `test_draft_seed_lists_component_not_on_plan_row_violates` — provenance id absent from plan row **`component_ids`**
- `test_cross_cutting_seed_flag_matches_cross_cutting_plan` — **`cross_cutting: true`** allowed on cross-cutting disposition plan (pin allowed empty or minimal **`roadmap_components`** per implemented rule)

**Gate 4 — bundle alignment**

- `test_plan_row_and_bundle_basenames_match_passes` — bijection clean
- `test_missing_bundle_entry_for_plan_row_violates` — plan row basename absent from bundle
- `test_dangling_bundle_key_violates` — bundle key matches no plan row basename
- `test_duplicate_draft_seed_basename_across_plan_rows_violates` — two plan rows share `Path(draft_seed_path).name` → gate 4 violation
- `test_none_draft_seed_bundle_violates_for_every_plan_row` — **`draft_seed_bundle=None`** triggers missing-entry violations

**Gate 5 — ordering + slug**

- `test_ordering_lists_every_plan_id_once_passes` — conforming ordering
- `test_ordering_missing_plan_id_violates` — plan id absent from ordering sequence
- `test_ordering_unknown_plan_id_entry_violates` — ordering `plan_id` not in plans inventory
- `test_ordering_duplicate_plan_id_reported_once` — duplicate **`plan_id`** in ordering → one violation per duplicated id
- `test_ordering_depends_on_unknown_plan_violates` — bad **`depends_on`** entry
- `test_ordering_assumption_target_unknown_plan_violates` — bad **`assumption_targets`** entry
- `test_ordering_depends_on_must_appear_earlier_in_sequence` — dependency listed after the owning plan → violates
- `test_plan_id_must_match_slug_re` — id failing **`PLAN_ID_SLUG_RE`** violates
- `test_valid_slug_plan_id_passes_slug_check` — e.g. `order-core` passes

**Gate 6 — assumption consumers**

- `test_assumption_consuming_defined_plan_passes`
- `test_assumption_consuming_unknown_plan_violates` — message names assumption id and missing plan id

**Regression / shared gates on plans stage**

- `test_duplicate_plan_and_component_id_violates` — same id on plan row and component row → **`check_duplicate_row_ids`** fires (documents inherited rule; not gate 1/2)
- `test_inventory_has_prose_on_plans_artifact` — missing prose for a plan row id violates
- `test_design_row_continuity_on_plans_predecessor` — if not already green from step 2, pin dropping assumption row without removal

**Module boundary (one seam test)**

- `test_gates_accept_a_parsed_conforming_plans_artifact` — parse conforming plans text with step 1's **`parse_plans_artifact`**, attach upstream artifacts and a matching **`draft_seed_bundle`**, assert **`run_plans_gates`** returns `[]` (fourth seam test alongside domain/constraints/components)

(approx. 28–32 new cases, plus unchanged existing suite)

## Acceptance criteria

- **`PLANS_GATES`**, **`run_plans_gates`**, and all six plan-relation **`check_*`** functions are importable from **`plan_tool.roadmap_gates`**
- **`run_plans_gates(plans_envelope()) == []`** for the conforming fixture
- Each architecture observable 1–6 has at least one failing test and one passing test
- **`test_plan_relation_gates_are_inert_off_plans_stage`** passes
- **`test_plans_gates_tuple_includes_relation_gates_in_order`** passes
- **`test_gates_accept_a_parsed_conforming_plans_artifact`** passes
- **`uv run pytest tests/test_roadmap_gates.py -q`** exits 0
- **`rg 'from plan_tool' plan_tool/roadmap_gates.py`** matches only **`plan_tool.roadmap_artifacts`**
- No edits outside the two declared files
- **`rg 'run_plans_gates|PLANS_GATES' plan_tool/roadmap.py`** returns nothing (orchestrator wiring stays step 6)

## References

- [enum — Support for enumerations (Python 3.13)](https://docs.python.org/3.13/library/enum.html) — **`PlanDisposition`** membership checks in gate 1
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — **`Path(draft_seed_path).name`** for bundle keys
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — draft-seed provenance frontmatter **`parse_draft_seed_provenance`** consumes
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — gate fixtures built from frozen row types

## Applicable guardrails

- **Plan intent / no merit gates** — this step adds only id-relation observables. Do not add gates on disposition correctness, Outcome quality, seed length, plan count, or agreement between seed body and roadmap prose beyond what observables 3–4 require.
- **Plan Out of scope / no auto-create** — no code invokes **`create`**, writes **`plan-seeds/`**, or prints runnable CLI lines; bundle checks stay in-memory.
- **Plan Out of scope / framework lenses** — no **`--framework`** or lens-driven behavior.
- **Shape vs relation split** — do not move relation rules into **`parse_plans_artifact`** or **`parse_draft_seed_provenance`**; keep parse accepting dangling refs (step 1 negative tests must stay green).
- **Revision mode inherited** — no new revision gates; shared continuity/feedback/settled gates cover **`PlansArtifact`** via step 2 row helpers.

## Deferred

- **`ROADMAP_FORMAT.md` fourth-artifact rule documentation and kind-token traceability** — step 4 reads landed constants from this module
- **`plan_tool/roadmap.py` stage-4 `STAGES` row wiring `run_plans_gates` by identity** — step 6
- **Atomic draft-seed directory rewrite on disk and post-green disk/bundle parity** — steps 5–6 writer path; gate 4 judges the envelope field only
- **`--apply` / `-y` promotion into `plan-seeds/`** — step 7
- **Recommend-only `create` split-proposal pointer** — step 8
- **#235 / #236 / #237 gate cleanups from position 03 review** — sibling backlog; do not absorb here
- **Carve B decision-record mint-on-removal ruling** — settled 2026-08-05
  **narrow** (`BACKLOG.md` #208); out of this position's contract.
