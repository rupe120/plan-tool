> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Refactor the stage write loop for optional side outputs

## Summary

Extend `plan_tool/roadmap.py` so a `RoadmapStage` row can declare optional draft-seed side outputs alongside its primary artifact. The attempt loop gains a multi-fence lift path that fills `ArtifactEnvelope.draft_seed_bundle` (from step 2) before gates run, and a green write path that persists the re-rendered primary artifact plus an atomic draft-seed directory rewrite keyed by each plan row's `draft_seed_path`. Stages without side-output configuration keep today's single-fence lift and single-file write with zero call-site changes. The shipped `STAGES` table stays at three rows — step 6 adds the plans stage entry and prompt. On green, existing `tests/test_roadmap.py` cases for stages 1–3 stay unchanged, and new injected-table cases prove lift → envelope → gate → atomic write without branching on stage number or name.

## Table of Contents

- [Summary](#summary) — loop refactor, side-output data on the row, and green state
- [Why](#why) — why dual output needs orchestrator work before stage 4 ships
- [Input](#input) — contracts from steps 1 and 2 this step consumes
- [Files (creates vs edits)](#files-creates-vs-edits) — the two paths this step touches
- [Implementation](#implementation) — stage-row fields, lift, envelope, write, and invariants
- [Tests](#tests) — new cases and the green-before-done gate
- [Acceptance criteria](#acceptance-criteria) — checkable outcomes
- [References](#references) — docs worth skimming while implementing
- [Applicable guardrails](#applicable-guardrails) — plan fences binding this step
- [Deferred](#deferred) — explicitly later steps

## Why

At HEAD, `_run_stage` lifts one artifact per reply via `_lift_artifact_text`, `_build_envelope` fills only artifact slots, and `_write_artifact` writes one re-rendered file. Stage 4 must emit `04-roadmap.md` **and** N draft seeds in one Claude call; step 3's plan-relation gates 3–4 judge an in-memory `draft_seed_bundle` before any seed bytes hit disk. Without generalizing the loop now, step 6 would fork `_run_stage` on stage identity — the exact failure mode the stage-as-data design rejects. This step closes the orchestrator gap: side outputs become optional fields on `RoadmapStage`, variation stays in data, and gates keep the single `ArtifactEnvelope` call shape.

## Input

Land steps **1** and **2** before implementing. Open the landed modules and record what shipped — code on disk wins over this detail or the plan.

**From step 1 (`plan_tool/roadmap_artifacts.py`):**

- **`PlansArtifact`**, **`PlanRow`**, **`PlanRow.draft_seed_path`** — relative path from the roadmap slug directory (e.g. `seeds/order-core.md`).
- **`parse_plans_artifact`**, **`render_plans_artifact`**, **`load_plans_artifact`**, **`plans_path`**, **`PLANS_FILENAME`** — primary artifact contract the injected test row uses.
- **`draft_seeds_dir`**, **`resolve_draft_seed_path`**, **`DRAFT_SEEDS_DIRNAME`** — slug-relative draft paths and directory helper for the atomic rewrite.
- **`parse_draft_seed_provenance`** — not called here; gates own provenance checks (step 3).

**From step 2 (`plan_tool/roadmap_gates.py`):**

- **`ArtifactEnvelope.draft_seed_bundle`** — optional `Mapping[str, str]` keyed by **`Path(draft_seed_path).name`**; `None` means no bundle attached.
- Widened **`ArtifactEnvelope`** with a `plans` slot — `_build_envelope` already fills slots by `artifact_key`; this step adds an explicit `draft_seed_bundle=` keyword at the gate call site in `_run_stage`, not inside `_build_envelope`'s comprehension (the bundle is not an artifact slot).

**Production order inside one attempt:** lift primary + bundle → parse primary → authored-review-rows check → build envelope **with** `draft_seed_bundle` → `stage.gates(envelope)` → on green, write primary + seeds. Step 3 gates read the bundle; this step fills it; neither step reads draft seeds from disk during the attempt loop.

## Files (creates vs edits)

- **New files:** none
- **Existing files (edits only):**
  - `plan_tool/roadmap.py` — optional side-output field(s) on `RoadmapStage`; multi-fence lift helper; `_run_stage` attaches `draft_seed_bundle` to the envelope; extend `_StageOutcome` and the `run_roadmap` write path for atomic draft-seed persistence; keep shipped `STAGES` at three rows
  - `tests/test_roadmap.py` — side-output lift, envelope, write, halting, and regression cases over an **injected** plans stage row (not `roadmap.STAGES`)

## Implementation

### Design decision: data on the row, not branches in the loop

**Chosen approach:** add one optional callable on `RoadmapStage` — e.g. **`side_output_seed_paths: Optional[Callable[[Any], tuple[str, ...]]] = None`** — that, when set, means "this stage's parsed artifact advertises draft-seed relative paths." The orchestrator derives bundle keys with **`Path(rel_path).name`**, lifts labeled fences from the reply, passes the mapping on **`ArtifactEnvelope.draft_seed_bundle`**, and runs an extended write after green gates. When the callable is **`None`** (default for shipped stages 1–3), the loop uses today's `_lift_artifact_text` → parse → envelope without bundle → `_write_artifact` only.

**Rejected alternative:** an `if stage.number == 4` (or `artifact_key == "plans"`) branch inside `_run_stage` / `run_roadmap`. That preserves today's code short-term but breaks the table-driven bet the moment a second side-output stage appears.

**Rejected alternative:** passing draft-seed text as extra positional arguments to each gate. That changes the `Gate` type and every gate set; step 2 placed the bundle on the envelope so `_run_stage` keeps one argument.

### `RoadmapStage` extension

- Add **`side_output_seed_paths`** (name may vary; keep it descriptive) — **`None`** by default; when present, returns every relative **`draft_seed_path`** string the parsed artifact carries (for plans: one entry per **`PlanRow`** in **`PlansArtifact.plans`** order is fine; gates judge set alignment, not order).
- Do **not** add stage-number, stage-name, or `artifact_key == "plans"` conditionals in the loop — the optional callable's presence selects behavior.
- Shipped **`STAGES`** tuple: **no edits** in this step. Step 6 appends the plans row with **`side_output_seed_paths`** wired to the landed plans artifact shape.

### Multi-fence lift (tolerance stops here)

Add a lift helper (e.g. **`_lift_stage_reply`**) that dispatches:

- **`side_output_seed_paths is None`** → delegate to existing **`_lift_artifact_text`** (stages 1–3 unchanged).
- **Callable set** → extract (1) primary artifact text and (2) a **`dict[str, str]`** bundle:

  - Apply the same preamble / outer-fence stripping **`_lift_artifact_text`** already uses (see module docstring: tolerance lives in the orchestrator, strict parse at the artifact leaf).
  - **Primary artifact** — text from the first **`---`** frontmatter fence through the end of the plans markdown body (same contract as today, extended to consume the full artifact before seed fences).
  - **Side-output fences** — one fenced block per seed; the fence label is the draft-seed **basename** (e.g. a line like **`` ```order-core.md ``**). Block contents are the full seed file text (provenance frontmatter + body). Strip the fence wrappers only; do not parse or rewrite seed bodies here.
  - Return **`None`** when the primary artifact cannot be lifted (same **`FAILURE_PARSE`** path and correction copy as today). Mis-labeled or missing seed fences are **not** lift failures — an empty or partial bundle flows to gates (step 3 gate 4 reports missing/extra keys).

Mirror precedents in spirit — **`detail.parse_detail_response`** for independent fence stripping; **`roadmap._lift_artifact_text`** for frontmatter-first primary extraction — but do **not** import **`detail.py`** (orchestrator import would drag the detail graph).

### Attempt loop changes (`_run_stage`)

After a successful invoke and before **`stage.parse`**:

1. Call the lift helper → **`(primary_text, bundle)`** or parse failure.
2. Parse **`primary_text`** through **`stage.parse`** (unchanged strict contract).
3. Run **`_authored_review_rows`** (unchanged).
4. Build envelope via **`_build_envelope(..., draft_seed_bundle=bundle)`** when the stage row carries **`side_output_seed_paths`**, else pass **`draft_seed_bundle=None`** (default). Extend **`_build_envelope`** with that optional kwarg; it attaches the field on the returned envelope and does **not** put the bundle in the artifact-slot dict.
5. On empty violations, return **`_StageOutcome(artifact=..., draft_seed_bundle=bundle)`** — extend **`_StageOutcome`** with an optional **`draft_seed_bundle`** field defaulting to **`None`**.

Gate call order stays **before** any write (matches plan architecture and existing stages 1–3).

### Write path (`run_roadmap` after green `_run_stage`)

Replace the direct **`_write_artifact`** call with a small coordinator (e.g. **`_write_stage_outputs`**) that:

- **When `outcome.draft_seed_bundle` is not `None`:**
  1. Resolve each target under **`draft_seeds_dir`** via **`resolve_draft_seed_path`** (step 1 already rejects paths outside `seeds/`).
  2. Stage every seed (and the rendered primary artifact) under a temp directory beside the slug, then **commit seeds first** (replace `seeds/` / write each target + delete stale files under `draft_seeds_dir` that are not in the new set), **then** write **`04-roadmap.md`** via **`atomic_write_text`**. Never leave a new primary artifact on disk advertising seeds that are not all present.
  3. On any failure before commit completes, leave the previous on-disk pair untouched (no half-updated `seeds/` with a new plans artifact).
- **When bundle is `None`:** single-file write only (zero diff for stages 1–3).

**Atomicity intent:** either the full advertised seed set and the primary artifact land together, or an exhausted/failed stage writes neither. Individual files use **`atomic_write_text`**; stale cleanup under **`draft_seeds_dir` only** runs as part of the seed commit **before** the primary artifact appears.

### Call sites and backward compatibility

- **`run_roadmap`** — call **`_write_stage_outputs`** instead of **`_write_artifact`** on the green path; pass through **`outcome.draft_seed_bundle`**.
- **`_build_envelope`** — extend with optional **`draft_seed_bundle: Mapping[str, str] | None = None`**; keep artifact-slot filling unchanged (do not store the bundle in the `{artifact_key: ...}` dict).
- **Stages 1–3** — **`side_output_seed_paths=None`** on shipped rows; no edits to **`run_domain_gates`**, prompts, or CLI.
- Enumerate zero-diff guarantee in acceptance: shipped **`STAGES`** and existing injected two-stage tables behave as today.

### Constraints (not free to vary)

- **`Gate = Callable[[ArtifactEnvelope], list[Violation]]`** — unchanged; no second envelope type.
- **Bundle keys** — basename of each plan row's **`draft_seed_path`**, matching step 2's field contract and step 3 gate 4.
- **No quality gates** — lift/write do not judge seed prose, disposition merit, or plan count.
- **No disk reads for gating** — gates during the loop read **`envelope.draft_seed_bundle`**, not files under **`seeds/`**.
- **Lift boundary** — after the primary plans artifact fence, seed fences are only blocks whose info-string / label equals `Path(draft_seed_path).name` for a plan row; stop attributing body text to the primary once the first such labeled seed fence begins (primary prose must not open a competing unlabeled ``` that would steal the remainder).
- **Non-interactive** — no prompts, confirms, or TTY branches in the write path (`rg 'input\(|isatty' plan_tool/roadmap.py` stays clean).
- **Halting** — exhausted side-output stage: no primary artifact write, no seed writes, no seed-dir creation; downstream stage invoker not called (extend existing halting tests).

### Shared locations (this step owns the orchestrator side only)

- **`plan_tool/roadmap_gates.py`** — **`draft_seed_bundle`** field and gates 3–4 (steps 2–3); this step fills the field before **`stage.gates`**.
- **`plan_tool/roadmap_artifacts.py`** — path helpers and plans parse/render (step 1); this step calls **`resolve_draft_seed_path`** and **`render_plans_artifact`**, does not edit the leaf.
- Consolidating multi-fence lift with **`detail.parse_detail_response`** or **`detail.py`'s** other lift helpers — cross-module refactor; route to Deferred, not this step.

## Tests

What this step adds or extends in **`tests/test_roadmap.py`**. Every listed test must be green before the step is done. Existing stage 1–3 cases stay green without edits unless a shared helper signature forces a mechanical update.

### Tests for this step

- `test_shipped_stages_have_no_side_output_seed_paths` — each row in `roadmap.STAGES` has `side_output_seed_paths is None` (guards accidental early stage-4 wiring).
- `test_side_output_lift_extracts_primary_and_basename_keyed_bundle` — unit-style call on a canned multi-fence reply; asserts primary text parses and bundle keys match fence labels.
- `test_side_output_lift_returns_none_when_primary_missing` — reply with seed fences but no `---` opening fails lift (parse failure kind).
- `test_stages_without_side_output_use_single_fence_lift` — injected two-stage table without side outputs; `_lift_stage_reply` path matches today's `_lift_artifact_text` behavior (regression guard while editing).
- `test_gate_envelope_carries_draft_seed_bundle_before_gates` — injected plans row + `_GateRecorder`; assert `envelope.draft_seed_bundle` equals the lifted mapping on the first gate call.
- `test_gate_envelope_draft_seed_bundle_none_for_single_output_stages` — existing-style domain stage; recorder sees `draft_seed_bundle is None`.
- `test_green_side_output_write_persists_plans_artifact_and_seed_files` — end-to-end injected plans stage with clean gates; files exist at `plans_path` and each `resolve_draft_seed_path` target; seed bytes match lifted content (not outer fence wrappers).
- `test_side_output_write_reparses_primary_through_loader` — written `04-roadmap.md` loads via `load_plans_artifact` equal to parsed artifact (renderer round-trip).
- `test_side_output_rewrite_deletes_stale_seed_files` — first green run writes two seeds; second run advertises one; orphan seed path under `draft_seeds_dir` is gone.
- `test_exhausted_side_output_stage_writes_no_artifact_and_no_seeds` — gate always fails; assert plans file absent, seed dir absent or unchanged, downstream invoker not called.
- `test_loop_never_branches_on_stage_identity` — `rg 'stage\.(number|name)\s*==' plan_tool/roadmap.py` returns nothing (table-driven guard).

**Green-before-done gate:** `uv run pytest tests/test_roadmap.py -q` passes; prefer parallel `-n auto` for the full file.

## Acceptance criteria

- `RoadmapStage` accepts optional `side_output_seed_paths`; shipped `STAGES` keeps three rows, each with `side_output_seed_paths is None`.
- Stages without side outputs: lift, envelope, write, and retry behavior unchanged (existing `TestStageTableAndDispatch` and `TestRetryLoop` cases green).
- Injected side-output stage: `_run_stage` sets `ArtifactEnvelope.draft_seed_bundle` before `stage.gates` runs.
- Green side-output run: seed set under `draft_seeds_dir` committed first (including stale cleanup), then primary artifact written via `stage.render`; each bundle entry written to `resolve_draft_seed_path(plans_dir, slug, rel_path)`; seed bytes match lifted content.
- Exhausted side-output stage: no new primary file, no new seed files, no seed directory created on first failure.
- `rg 'stage\.(number|name)\s*==' plan_tool/roadmap.py` returns nothing.
- `rg 'input\(|isatty' plan_tool/roadmap.py` returns nothing.
- All new tests listed above pass.

## References

- [dataclasses — Data Classes (Python 3.13)](https://docs.python.org/3.13/library/dataclasses.html) — frozen `RoadmapStage` row extensions and `_StageOutcome` fields.
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — basename keys, `resolve_draft_seed_path`, and stale-file deletion under the slug draft tree.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — background for plans artifact frontmatter the primary lift hands to `parse_plans_artifact` (shape only; seeds stay opaque text here).

## Applicable guardrails

- **Step intent (dual output as envelope data).** Side outputs are declared on the stage row and carried on `ArtifactEnvelope.draft_seed_bundle`; the loop does not special-case stage 4 by number or name.
- **Plan Architecture — gate-before-write order.** Bundle is attached before `stage.gates`; disk writes run only on a green `_StageOutcome`.
- **Plan Out of scope — quality / merit gates.** Lift and write paths do not score seed prose, dispositions, or plan counts; id alignment is gate work (step 3), not orchestrator judgment.
- **Plan Out of scope — auto-run create / `--apply`.** This step does not touch `plan-seeds/`, CLI flags, or printed next-steps (steps 6–7).
- **Plan Out of scope — stages 1–3 feedback lifecycle.** No changes to `_authored_review_rows`, revision prompts, or shipped stage rows beyond the additive optional field defaulting to off.

## Deferred

- **Stage-4 `STAGES` row, `roadmap-plans.md` prompt, and operator summary** — step 6; this step only proves the loop via injected tables.
- **`PLANS_GATES` / `run_plans_gates` and gate 3–4 violation messages** — step 3; side-output tests may use `_GateRecorder` or a one-line lambda gate until step 3 lands.
- **`ROADMAP_FORMAT.md` draft-seed fence examples** — step 4; lift contract here should stay consistent with whatever the step 6 prompt restates.
- **`--apply` / `-y` promotion into `plan-seeds/`** — step 7.
- **Consolidating multi-fence lift with `plan_tool/detail.py` lift helpers** — three generate-parse-retry loops; cross-module refactor belongs in reconcile or BACKLOG, not this step.
- **Reply-bytes sink half of #217** — plan Out of scope; do not add parse-failure persistence here.
