> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Add stage 4 writing 04-roadmap.md with roadmap-plans.md prompt and draft seeds

## Summary

Append the fourth shipped row to `plan_tool/roadmap.py:STAGES` so a full roadmap run writes gated `04-roadmap.md` and basename-keyed draft seeds under the slug directory, driven by a new `plan_tool/prompts/roadmap-plans.md` template. The row holds step 1–3 symbols by identity (`plans_path`, `parse_plans_artifact`, `render_plans_artifact`, `run_plans_gates`) and wires step 5's `side_output_seed_paths` callable so the generic lift/envelope/write path handles dual output without stage-number branches. Extend `plan_tool/cli/roadmap_cmd.py` to print ordered `plan-tool create <plan-id> --from-existing <draft-path>` lines when stage 4 lands, without writing `plan-seeds/`. On green, a four-stage stubbed run produces `04-roadmap.md`, seed files at each plan row's `draft_seed_path`, and create handoff lines in the CLI summary; stages 1–3 behavior stays unchanged.

## Table of Contents

- [Summary](#summary) — what lands, the main design choice, and green state
- [Why](#why) — the gap at HEAD and why now
- [Input](#input) — contracts from steps 1–5 this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — paths touched
- [Implementation](#implementation) — stage row, prompt, CLI handoff, test rewrites
- [Tests](#tests) — new and rewritten cases
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth skimming
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — explicitly later steps

## Why

At HEAD, `STAGES` ships three rows and `plan-tool roadmap` stops at `03-components.md`. Steps 1–3 land the typed `04-roadmap.md` contract and `run_plans_gates`; step 5 generalizes the orchestrator for optional draft-seed side outputs but deliberately leaves `STAGES` at three rows. Nothing runs the fourth stage: there is no `roadmap-plans.md`, no table entry, and no create handoff in the CLI summary — so #208's concept→seeds loop still ends with a manual walkthrough. This step closes that gap by appending one data row plus its prompt, reusing the side-output machinery step 5 built instead of forking `_run_stage` on stage identity.

## Input

Land steps **1**, **2**, **3**, **4**, and **5** before implementing. Open the landed modules and record what shipped — code on disk wins over this detail or the plan.

**From step 1 (`plan_tool/roadmap_artifacts.py`):**

- **Paths and filenames:** `PLANS_FILENAME`, `plans_path`, `draft_seeds_dir`, `resolve_draft_seed_path`, `DRAFT_SEEDS_DIRNAME`
- **Wire inventory:** `PLANS_ROW_KEYS` — expected `plans`, `ordering`, `assumptions`, `decisions`
- **Row types:** `PlansArtifact`, `PlanRow`, `OrderingEntry`, `AssumptionRow`, `PlanDisposition` (`keep`, `merge`, `split`, `cross-cutting`)
- **API:** `parse_plans_artifact`, `render_plans_artifact`, `load_plans_artifact`, `plans_design_rows`
- **Draft-seed provenance:** `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`, `DRAFT_SEED_CROSS_CUTTING_KEY`, `parse_draft_seed_provenance`
- **`PlanRow.draft_seed_path`** — slug-relative path (e.g. `seeds/plan-a.md`); bundle keys use `Path(draft_seed_path).name`

**From step 2 (`plan_tool/roadmap_gates.py`):**

- **`run_plans_gates`** and **`PLANS_GATES`** — hold by identity on the stage row; no wrapper
- **`ArtifactEnvelope.draft_seed_bundle`** — filled by step 5's lift before gates run

**From step 3 (`plan_tool/roadmap_gates.py`):**

- Six plan-relation **`check_*`** functions (confirm names at HEAD) — the prompt restates their observable rules; containment tests pin every gate the tuple runs

**From step 4 (`ROADMAP_FORMAT.md`):**

- Runnable plans example and draft-seed convention prose — use as a **fixture source** for `_plans_text()` and embedded prompt examples; do not cite `ROADMAP_FORMAT.md` from the prompt template

**From step 5 (`plan_tool/roadmap.py`):**

- **`RoadmapStage.side_output_seed_paths`** (or landed name) — optional callable; when set, `_lift_stage_reply` / `_write_stage_outputs` handle dual output
- **`_write_stage_outputs`** replaces direct `_write_artifact` on the green path

**What this step cannot verify:** canned-response tests prove the contract is satisfiable through real parsers and gates, not that a real model usually satisfies it on the first attempt. Hit-rate measurement needs real briefs and a recording surface — route to Deferred.

## Files (creates vs edits)

- **New files:**
  - `plan_tool/prompts/roadmap-plans.md` — fourth-stage authoring prompt: inline schema, multi-fence output contract, five seed Architecture additions, gate rules, placeholder skeleton

- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — import plans symbols; add `_plans_side_output_seed_paths` (or similar); append fourth `RoadmapStage` to `STAGES`; update module docstring to name four shipped stages
  - `plan_tool/cli/roadmap_cmd.py` — add create-handoff summary lines when `04-roadmap.md` was written; keep `--apply` out of this step
  - `tests/test_roadmap.py` — rewrite step-5 three-stage table tests to four; add `_plans_stage`, `_plans_text`, `_four_stage_invoker`, `plans_file` on `_Env`; add prompt containment and shipped stage-4 end-to-end classes; renumber synthetic-table injection to stage 5
  - `tests/cli/test_roadmap_cmd.py` — assert create handoff lines appear on completed four-stage runs and stay absent when stage 4 did not run

## Implementation

### Design stance

- **One table row, not a branch.** Append a `RoadmapStage` tuple entry; `rg 'stage\.(number|name)\s*==' plan_tool/roadmap.py` stays empty. Anything that feels stage-specific belongs on the row (`side_output_seed_paths`, `prompt_filename`, `gates=run_plans_gates`).
- **Hold symbols by identity.** The row's `artifact_path`, `parse`, `render`, and `gates` are the landed step 1–3 functions — no local adapter, lambda, or wrapper (rejected alternative: a thin wrapper "to normalize the signature").
- **Prompt restates the contract inline.** `plan_tool/prompts/` cannot cite repo-root `ROADMAP_FORMAT.md` or `SEED_FORMAT.md`; restate wire keys, disposition members, and seed fence requirements in the template text and pin them with containment tests against step 1 constants.
- **Dual output is prompt + row data, not orchestrator logic.** Step 5 owns lift, envelope attachment, and atomic seed-dir rewrite; this step owns the prompt's multi-fence reply shape and the `side_output_seed_paths` wiring that selects that path.

### `STAGES` fourth row (`plan_tool/roadmap.py`)

Append after the components row (confirm field names match step 5's landed `RoadmapStage`):

- **`number=4`**, **`name="plans"`** (or landed name), **`prompt_filename="roadmap-plans.md"`**
- **`artifact_key="plans"`** — feeds `${plans_artifact}` for any future stage above 4 and `_build_envelope`'s keyword slot
- **`artifact_path=plans_path`**, **`parse=parse_plans_artifact`**, **`render=render_plans_artifact`**, **`gates=run_plans_gates`**
- **`side_output_seed_paths=_plans_side_output_seed_paths`** — module-level helper returning `(row.draft_seed_path for row in artifact.plans)` (order fine; gates judge set alignment)

Update the module docstring opening paragraph: four shipped stages, fourth writes `04-roadmap.md` plus draft seeds.

**Rejected alternative:** special-casing stage 4 inside `_run_stage` or `_write_stage_outputs` instead of declaring side outputs on the row — that breaks the stage-as-data bet step 5 preserved.

### Prompt template (`plan_tool/prompts/roadmap-plans.md`)

Follow the repo's two prompt archetypes:

- **Closed output contract** from `plan_tool/prompts/detail-jira.md` — response is the deliverable; no preamble; first characters matter
- **Input-only stance** from `plan_tool/prompts/distill-seed.md` — work from supplied texts; do not read the repository

**Variable map** (must match `_render_stage_prompt`): `${slug}`, `${brief}`, `${domain_artifact}`, `${constraints_artifact}`, `${components_artifact}`. Stage 1–3 upstream rules already apply — this stage receives all three artifact texts off disk.

**Primary artifact section** — restate inline (pin in tests against step 1 constants):

- **`PLANS_ROW_KEYS`** collections and required fields per `PlanRow`, `OrderingEntry`, `AssumptionRow`
- **`PlanDisposition`** four members and when `component_ids` may be empty (`cross-cutting` only)
- **`draft_seed_path`** is relative to the roadmap slug root (e.g. `seeds/<slug-compatible-name>.md`)
- Review collections `feedback`, `removals`, `decisions` — same contract as stages 1–3
- **Plan ids are create slugs** — must satisfy create-compatible slug shape; **do not reuse component ids as plan ids** (duplicate-id gate unions envelope ids)
- Prose body: every inventoried design-row id appears as a whole word (same inventory-has-prose contract as earlier stages)
- Placeholder skeleton ids (`plan-1`, `assumption-1`, `<one line>`) — not a realistic project story

**Multi-fence output format (strict)** — this stage differs from stages 1–3:

1. **First:** the full `04-roadmap.md` text starting with `---` (no outer fence, no preamble)
2. **Then:** one fenced block per plan row, in **`plans` inventory order**, fence label = **`Path(draft_seed_path).name`** (e.g. a line like `` ```order-core.md ``), contents = full seed file text

Mis-labeled seed fences are gate failures, not lift failures — say so explicitly so the model does not treat missing fences as optional.

**Draft seed content (per fence)** — enumerate all five Architecture additions the plan names; the prompt is the only place operators/models see them before `--apply`:

1. **Four-artifact provenance** — seed prose names all four roadmap artifacts and forbids re-litigating **settled** upstream decisions
2. **Domain binding** — entity / rule / workflow ids this slice owns (from upstream artifacts)
3. **Settled decisions as fences** — carry chosen options; **do not** paste long rejected-alternative rationale prose (`create` re-grounds reasons against live docs)
4. **Discharged constraints** — constraint ids this slice discharges, with dispositions from `02-constraints.md`
5. **Inter-plan assumptions** — copy only `AssumptionRow` entries whose `consuming_plan_ids` includes **this seed's plan id**

Each seed also carries **YAML provenance frontmatter** gates scan:

- Required **`roadmap_components`** list (wire key from `DRAFT_SEED_ROADMAP_COMPONENTS_KEY`)
- Optional **`cross_cutting: true`** (wire key from `DRAFT_SEED_CROSS_CUTTING_KEY`) when disposition is `cross-cutting`

Seed **body** follows `SEED_FORMAT.md` scope-contract fence shape (Outcome, In scope, Out of scope / Non-goals, Allowed behavior changes, Allowed reorganization, Verification, Stop / defer) — restate the section names inline; do not link the file.

**Gate rules section** — restate every check in `PLANS_GATES` in plain language (shared tuple plus six plan-relation observables from step 3). Messages are retry bullets: name ids, cite filenames by constant string (`04-roadmap.md`, `03-components.md`), no line numbers. Include the correction-channel copy other roadmap prompts use (re-author whole response; violations appended; few attempts).

**Embedded example** — drive through `parse_plans_artifact` and `run_plans_gates` with a test-built `draft_seed_bundle` in the suite (same pattern as domain/components prompt examples). Use placeholder ids throughout.

**Template mechanics:** render through `string.Template.safe_substitute`; literal `$` → `$$`; every `${name}` must appear in the caller's variable map.

### CLI create handoff (`plan_tool/cli/roadmap_cmd.py`)

When a completed run wrote `04-roadmap.md` (detect via `PLANS_FILENAME` on a path in `result.artifacts`, or stage 4 ∈ `result.stages_run` with a matching artifact path):

- Load **`load_plans_artifact`** from the written path
- Re-check **ordering↔plans bijection** (same rule as gate 5 / apply preflight); if it fails, abort the summary with an explicit operator error — fail-closed, no partial handoff lines
- Walk **`artifact.ordering`** sequence (not raw `plans` row order) — each entry's **`plan_id`** drives handoff order
- For each ordering entry, resolve the matching **`PlanRow`**, then **`resolve_draft_seed_path(plans_dir, slug, row.draft_seed_path)`**
- Emit one detail line per plan, e.g. `plan-tool create <plan-id> --from-existing <short-path>` using **`_short_path`** against `repo_root` (match existing summary style)

Emit handoff for **`OUTCOME_COMPLETED`** and keep it absent when stage 4 did not run or exhausted before writing. Do **not** add `--apply`, `-y`, or any write under `plan-seeds/` — step 7 owns promotion.

**Rejected alternative:** extending `RoadmapResult` with handoff tuples — loading the written artifact in the CLI keeps the result type stable and matches how `_artifact_filenames` already reads paths off disk.

### Test fixture helpers (`tests/test_roadmap.py`)

Add alongside existing `_domain_text` / `_components_text`:

- **`_plans_stage()`** — returns `roadmap.STAGES[3]` (or index by `number==4`)
- **`_plans_text(**kwargs)`** — returns a **multi-fence** conforming reply: primary `04-roadmap.md` text plus one fence per plan row, keys = basenames, values = minimal seeds with valid provenance frontmatter aligned to the plans fixture
- **`_four_stage_invoker()`** — `_StubInvoker(_domain_text(), _constraints_text(), _components_text(), _plans_text())`
- **`_Env.plans_file`** / **`write_plans()`** — parallel to existing upstream helpers

Build `_plans_text` from the same component/domain fixture ids the three-stage helpers use so a four-stage run clears real `run_plans_gates` when upstream artifacts match.

### Rewrite step-5 "three stages only" tests (by name)

Step 5 shipped these as guards against early stage-4 wiring; step 6 **replaces** them:

- `test_stage_table_ships_three_stages` → **`test_stage_table_ships_four_stages`**
- `test_shipped_table_run_writes_all_three_artifacts` → **`test_shipped_table_run_writes_all_four_artifacts`** (includes seed files under slug)
- `test_shipped_stages_have_no_side_output_seed_paths` → **`test_stages_one_through_three_have_no_side_output`** plus **`test_plans_stage_declares_side_output_seed_paths`**

Also update:

- `test_both_stages_use_the_one_shared_revision_template` shipped prompt list — include `roadmap-plans.md`
- `TestSyntheticThirdStage._table` — synthetic injection becomes **stage 5** (real stage 4 now occupies `number=4`); adjust invoker reply count
- `test_the_shipped_table_is_unchanged_by_the_synthetic_stage_case` — expect four base stages

### Shared locations (read-only or step-7-owned)

- **`plan_tool/roadmap_artifacts.py`**, **`plan_tool/roadmap_gates.py`** — consumed, not edited
- **`plan_tool/cli/authoring.py`** create split-proposal pointer — step 8
- **`docs/cli/roadmap.md`**, **`--apply` flags** — step 7
- Consolidating multi-fence lift with `plan_tool/detail.py:parse_detail_response` — cross-module refactor; Deferred

### Constraints (not free to vary)

- **No merit gates in prompt or code** — restate id-presence and alignment rules only
- **Default run never writes `plan-seeds/`** — drafts stay under the slug directory
- **Non-interactive** — no confirm, TTY branch, or `-y` in this step
- **Halting** — exhausted stage 4 writes neither `04-roadmap.md` nor seeds (inherits step 5 tests; add shipped-table case if missing)
- **Disk is upstream** — stage 4 prompt reads 01/02/03 texts loaded off disk, same as stage 3
- **Identity assertions** on the stage row fields — `is` checks against landed symbols, not merely behavioral equality

## Tests

Every listed test must be green before this step is done. Prefer `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q -n auto`.

### Tests for this step

**Stage table and row wiring**

- `test_stage_table_ships_four_stages` — `len(STAGES)==4`, numbers `[1,2,3,4]`, names include `plans`, keys include `plans`
- `test_plans_stage_row_reuses_landed_path_parser_renderer_and_gates` — identity (`is`) on `plans_path`, `parse_plans_artifact`, `render_plans_artifact`, `run_plans_gates`
- `test_plans_stage_declares_side_output_seed_paths` — fourth row's side-output callable is not `None`; stages 1–3 remain `None`
- `test_loop_never_branches_on_stage_identity` — `rg 'stage\.(number|name)\s*==' plan_tool/roadmap.py` returns nothing

**Prompt containment (`roadmap-plans.md`)**

- `test_plans_prompt_template_ships_under_prompts_dir`
- `test_plans_prompt_placeholders_are_a_subset_of_the_variable_map`
- `test_plans_prompt_renders_with_no_unresolved_placeholder`
- `test_plans_prompt_names_every_plans_row_key` — parametrized over `PLANS_ROW_KEYS`
- `test_plans_prompt_names_every_plan_disposition_value`
- `test_plans_prompt_names_draft_seed_provenance_keys`
- `test_plans_prompt_states_every_plans_gate_rule` — one case per gate in `PLANS_GATES`
- `test_plans_prompt_cites_no_repo_document` — `rg`-style assertion: no `FORMAT.md`, no `SEED_FORMAT.md` path references
- `test_plans_prompt_forbids_component_ids_as_plan_slugs`
- `test_plans_prompt_describes_multi_fence_output_with_basename_labels`
- `test_plans_prompt_enumerates_five_seed_architecture_additions`
- `test_plans_prompt_warns_against_copying_rejected_alternative_rationale`
- `test_prompt_example_parses_through_the_plans_parser`
- `test_prompt_example_clears_run_plans_gates_with_bundle` — supplies conforming `draft_seed_bundle`

**Shipped four-stage end-to-end (real gates, stub invoker, `shipped_env`)**

- `test_shipped_table_run_writes_all_four_artifacts` — `04-roadmap.md` plus seed files at advertised paths
- `test_four_stage_run_does_not_write_plan_seeds_dir` — repo-root `plan-seeds/` untouched (path outside slug tree)
- `test_plans_artifact_reparses_from_disk_after_write`
- `test_seed_bytes_match_lifted_bundle_not_raw_fences`
- `test_from_stage_four_skips_stages_one_through_three` — upstream reread off disk; only stage 4 invoked
- `test_from_stage_four_revision_wraps_prompt_with_predecessor_and_feedback` — inherits shared revision template
- `test_exhausted_plans_stage_writes_no_plans_artifact_and_no_seeds` — real `run_plans_gates` with a broken fixture or `_GateRecorder` that always fails
- `test_gate_violation_on_plans_stage_is_retried_with_messages` — one seam case across lift → gates → retry prompt

**CLI (`tests/cli/test_roadmap_cmd.py`)**

- `test_completed_four_stage_run_prints_create_handoff_lines` — stub or real orchestrator; stdout/detail contains ordered `plan-tool create … --from-existing …` lines
- `test_three_stage_completed_run_prints_no_create_handoff` — no spurious create lines when stage 4 did not run
- `test_create_handoff_uses_ordering_sequence_not_plans_row_order` — ordering entries shuffled relative to `plans` list still print in ordering order

**Green-before-done gate:** `uv run pytest tests/test_roadmap.py tests/cli/test_roadmap_cmd.py -q` passes; full fast suite `-m "not integration"` stays green.

## Overwrite / re-entry guidance

When stage 4 is among `overwritten_stages`, the CLI overwrite / copy-aside summary must name both **`04-roadmap.md`** and the slug **`seeds/`** tree — `--from-stage 4` replaces draft seeds atomically, so hand-edited drafts need the same copy-aside warning as numbered artifact body prose.

## Acceptance criteria

- `len(plan_tool/roadmap.py:STAGES) == 4`; fourth row uses `prompt_filename="roadmap-plans.md"`, `artifact_key="plans"`, and `side_output_seed_paths` wired
- Stage row fields are landed step 1–3 symbols by identity (`is` assertions in tests)
- `plan_tool/prompts/roadmap-plans.md` exists; containment tests pass; `rg -l 'FORMAT\.md|SEED_FORMAT\.md' plan_tool/prompts/roadmap-plans.md` returns nothing
- Stubbed four-stage run writes `plans_path(…)/04-roadmap.md` and one seed file per plan row; `plan-seeds/` under repo root is not created or modified
- Written `04-roadmap.md` reloads through `load_plans_artifact`; seeds reparses through `parse_draft_seed_provenance` where applicable
- Completed run with stage 4 prints ordered `plan-tool create <plan-id> --from-existing <path>` lines; three-stage-only run prints none
- `--from-stage 4` revises with predecessor + feedback without rerunning stages 1–3
- Exhausted stage 4 leaves no new `04-roadmap.md` and no new seed files
- `rg 'stage\.(number|name)\s*==' plan_tool/roadmap.py` returns nothing
- All tests listed above pass

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — draft-seed provenance frontmatter and plans inventory YAML in prompt examples
- [YAML Ain't Markup Language (YAML) revision 1.2.2](https://yaml.org/spec/1.2.2/) — list/map syntax for plan, ordering, and assumption rows restated inline
- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — `RoadmapStage` row fields and test fixtures built from typed rows
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — `Path(draft_seed_path).name` bundle keys and `resolve_draft_seed_path` targets
- [enum — Support for enumerations (Python 3.13)](https://docs.python.org/3.13/library/enum.html) — `PlanDisposition` members the prompt must spell

## Applicable guardrails

- **The plan's step intent.** This step runs gated stage 4 and prints create lines; it never copies drafts into `plan-seeds/` and never auto-runs `create`.
- **The plan's Out of scope — merit and quality gates.** Prompt and tests restate binary id/alignment rules only; no prose scoring, plan-count caps, or disposition merit checks.
- **The plan's Out of scope — `--apply` and promotion.** No `--apply`, `-y`, collision policy, or `docs/cli/roadmap.md` flag docs — step 7.
- **The plan's Out of scope — framework lenses and stages 1–3 rewrite.** Append one row and one prompt; do not restructure upstream stages or add `--framework`.
- **The plan's Out of scope — create split-proposal wiring.** Generic roadmap-verb pointer in `create` next-steps is step 8.

## Deferred

- **`--apply`, `-y`, refuse-by-default collision policy, and `docs/cli/roadmap.md`** — step 7; CLI apply-only mode skips the stage table and never re-invokes stage 4
- **Recommend-only roadmap pointer on `create` SplitProposal next steps** — step 8 (`plan_tool/cli/authoring.py`)
- **Real brief run and human-review record** — step 9 (non-code)
- **Operator doc sweep, BACKLOG #208 closure, CAPABILITIES entry** — step 10
- **First-attempt prompt hit-rate measurement** — needs real briefs and a recording surface; canned tests cannot prove usual satisfaction
- **Consolidating multi-fence lift with `plan_tool/detail.py:parse_detail_response`** — cross-module refactor; route to reconcile or backlog, not this step
