> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 11 — Update roadmap docs for per-seed draft materialization

## Summary

Sweeps four docs so none of them still describe stage 4 as the thing that writes draft seed bodies: `docs/ROADMAP_WALKTHROUGH.md` and `docs/ROADMAP_DEMO_ORCHESTRATION.md` narrate the operator-facing flow (call counts, the stage-4 artifact table, worked example paths, and the promote sequence), while `docs/ARCHITECTURE.md` and `CAPABILITIES.md` describe the module family and its behavior contract. By the time this step runs, steps 4/5/6/8/9/10 have already landed `--materialize`, `--refresh-seeds`' per-plan rewrite, `--accept-seed`, `--view seeds`, promotion's six-state refusal, and stage 4's own retirement from seed generation — this step's job is only to make the four declared docs agree with that shipped behavior, not to change any of it. One finding surfaced during grounding: step 9's own detail file already commits to rewriting the exact CAPABILITIES.md sentence this step's plan-level intent also names, so this step's real remaining CAPABILITIES.md work is narrower than the plan intent text suggests — see Input. On green, a reader following either narrative doc's commands gets a working sequence (materialize before promote), and both architecture docs name six roadmap modules with an accurate, non-stale description of what each command actually does.

## Table of Contents

- [Why](#why) — what four docs still assume about stage 4 that steps 4–10 already made false
- [Input](#input) — what steps 4/5/6/8/9/10 already shipped, and the one overlap this step must not duplicate
- [Files (creates vs edits)](#files-creates-vs-edits) — the four declared files, no additions
- [Implementation](#implementation) — the edits, file by file
- [Tests](#tests) — non-code verification
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

`docs/ROADMAP_WALKTHROUGH.md` and `docs/ROADMAP_DEMO_ORCHESTRATION.md` both narrate a world where one `plan-tool roadmap <slug> --from-existing <brief>` run leaves every plan's draft seed sitting on disk, ready to promote. Steps 1–10 make that false: stage 4's own call now only ever writes `04-roadmap.md` (step 9), a plan's draft materializes through its own independent call (step 2's `materialize_plan_seed`, driven by step 4's per-plan `--refresh-seeds` or step 5's targeted `--materialize`), and `--apply` now refuses to promote anything step 3's `classify_draft_seeds` doesn't call `current` (step 6). A reader who runs `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s Phase 3 exactly as written — `--apply` right after Phase 1's stage run — now hits a wall: nothing is `current` yet, because nothing has been materialized. That is not a wording problem alone; the runbook's command sequence stops working. Fixing only the three literal claims the plan's Step intent names (the call-count line, the `04-roadmap.md` + `seeds/` table row, the `seeds/<plan-id>.md` worked-example path) without also inserting the missing materialize call would leave the doc textually updated but still procedurally broken — see Implementation's Phase 3 treatment.

`docs/ARCHITECTURE.md`'s Roadmap paragraph and `CAPABILITIES.md`'s `architecture-roadmap` entry describe the same stale shape at the architecture level: both say stage 4 "emits" draft seeds, both count five roadmap modules (step 3 adds a sixth, `plan_tool/roadmap_seed_manifest.py`), and both describe the `create --from-existing` handoff lines as unconditional (step 9 makes them conditional on a plan's draft classifying `current`). `ARCHITECTURE.md` additionally claims `--from-stage 4` "refresh[es]" draft seeds — after step 9, a stage-4 re-entry only invalidates existing drafts; it never regenerates their content, because generation now lives exclusively in step 2's primitive.

## Input

This step is grounded entirely in what steps 4, 5, 6, 8, 9, and 10 already shipped by the time it runs — it invents no new behavior and adds no new command. Read each landed module/doc rather than trusting this file's paraphrase where the two disagree:

- **Step 5** ships `--materialize [PLAN_ID]` on `plan-tool roadmap`: with no id, it regenerates every plan step 3's classifier calls `missing`, `stale`, `malformed`, `path-escaping`, or `digest-mismatched`; with one, it targets that plan and refuses (naming the actual classification) an id that's unknown or already `current`/`duplicate`.
- **Step 4** rewrites `--refresh-seeds` to call `materialize_plan_seed` once per plan row instead of one bundled call, and both it and step 5 report one of three outcomes — applied / partial / exhausted — each with its own exit code.
- **Step 6** rewrites `--apply`'s preflight to refuse any draft step 3's `classify_draft_seeds` calls anything but `current` (six refusal states: `missing`, `stale`, `malformed`, `path-escaping`, `duplicate`, `digest-mismatched`), re-checked again immediately before the commit.
- **Step 8** ships `--view seeds`, printing every plan's classification plus an orphans report (a sidecar entry or on-disk file matching no current plan row).
- **Step 10** ships `--accept-seed PLAN_ID`: for a plan step 3 classifies `digest-mismatched`, it validates the live file's content and, if clean, records its digest as `current` without calling the backend — the one path that keeps a reviewed hand edit instead of overwriting it. It refuses every other classification.
- **Step 9** is this step's direct dependency and retires stage 4's inline seed generation entirely (`_lift_multi_fence_reply`, `ArtifactEnvelope.draft_seed_bundle`, and the rest of the bundle machinery are gone from `plan_tool/roadmap.py`/`roadmap_gates.py`). Two consequences for this step specifically:
  - `plan_tool/roadmap_gates.py`'s `PLANS_GATES` drops from 14 entries to 13 (it loses `check_draft_seed_provenance` outright); the repo-wide distinct-`check_*`-function count across `DOMAIN_GATES`/`CONSTRAINTS_GATES`/`COMPONENTS_GATES`/`PLANS_GATES` drops from 23 to 22 (verified at HEAD today: `check_artifact_non_empty`, `check_duplicate_row_ids`, `check_decision_records`, `check_inventory_has_prose`, `check_design_row_continuity`, `check_feedback_integrity`, `check_settled_decisions` are the 7 shared across all four sets, plus 2+2+5+7 = 16 not shared, for 23 total today; step 9 removes exactly one, `check_draft_seed_provenance`).
  - **Step 9's own detail file already commits to rewriting `CAPABILITIES.md`'s `architecture-roadmap` prose bullet** — the exact sentence ("Stage 4 maps components to an ordered plan list with closed dispositions, emits `SEED_FORMAT.md`-conformant draft seeds under the slug directory, and prints runnable `create --from-existing` handoff lines") that this plan's own Step intent also names as step 11's to fix. By the time this step runs, that sentence will already describe stage 4 as declaring a seed destination (not emitting a body), materialization as a separate step, and handoff lines as conditional on `current`. **Read the file as it stands before editing** — this step's real remaining CAPABILITIES.md work is the `surfaces:` list (the module-count analog of `ARCHITECTURE.md`'s "five becomes six"), not a second rewrite of a sentence step 9 already corrected. If step 9's landed wording still misses something (e.g. still says "five modules" implicitly by omission, or still leaves the sentence internally inconsistent), fix only that gap rather than rewriting the whole bullet a second time.
  - `docs/ARCHITECTURE.md` is **not** in step 9's file list — its Roadmap paragraph is untouched by step 9 and is entirely this step's to fix, including the "emits draft seeds", "five modules", and unconditional-handoff-lines claims all in one place.

## Files (creates vs edits)

**New files:** none.

**Existing files (edits only):**

- `docs/ROADMAP_WALKTHROUGH.md` — the stage table, the call-count sentence, the stage-4 read-for-seams paragraph, the promote section, and the two `seeds/`-prefixed example paths.
- `docs/ROADMAP_DEMO_ORCHESTRATION.md` — the Phase 1 call-count line and gate-count table row, the Phase 3 promote section (adds the missing materialize step), the worked-example path, and § 10's cost accounting.
- `docs/ARCHITECTURE.md` — the Roadmap paragraph: module count and import edges, the "emits draft seeds" clause, the unconditional handoff-lines claim, and the `--from-stage 4` "refresh" claim.
- `CAPABILITIES.md` — the `architecture-roadmap` entry's `surfaces:` list (add `plan_tool/roadmap_seed_manifest.py`); confirm rather than re-edit the prose bullet step 9 already rewrote.

## Implementation

### `docs/ROADMAP_WALKTHROUGH.md`

- **§ "Command sequence at a glance"** — the command block currently has no example of materializing, accepting, or viewing seed state. Add one line each for `--materialize` (no id, and with one), `--accept-seed <plan-id>`, and `--view seeds`, in the same style as the existing lines (placeholder `my-project`/`my-first-plan` slugs, no explanation inline — the explanation lives in the numbered sections below).
- **Line ~35, the "four backend calls" sentence** — still literally true for the four-stage pipeline itself (stage 4's own call count is unchanged by step 9), but it reads as though that run also produces usable seeds, which is no longer true. Add a clause noting that materializing a plan's draft seed is a separate, independent call per plan (step 2's `materialize_plan_seed`, driven by `--materialize` or `--refresh-seeds`), not part of the four.
- **The stage table's row 4** (`| 4 | \`04-roadmap.md\` and \`seeds/\` | Ordered plan rows with intent, delivery shape, and non-goals; cross-plan assumptions; and one draft seed per plan row. |`) — drop "and `seeds/`" from the artifact column and "and one draft seed per plan row" from the description; stage 4 now writes only `04-roadmap.md`. Consider adding a short note directly under the table (or as new prose) that each plan row names a `draft_seed_path` destination but nothing is written there yet — materializing it is the next step, covered in § 6.
- **"Stage 4 — read the plan mapping before creating plans"** — "Each row has a slug-relative `draft_seed_path`, and the command prints matching, runnable `create --from-existing` lines" is unconditional; after step 9 a handoff line prints only for a plan whose draft classifies `current` (`roadmap_seed_manifest.classify_draft_seeds`). Right after a first-time stage-4 run nothing is materialized yet, so this sentence's premise (lines print immediately) is usually false the first time through the walkthrough. Reword to say the command reports which plans are seed-ready and which need `--materialize` first, rather than implying every row gets a line immediately.
- **§ 6, "Promote accepted draft seeds, or create directly from them"** — this section currently jumps straight to `--apply` as though the drafts already exist. Add the missing step: materializing every plan step 3 classifies non-`current` (`--materialize`, or `--refresh-seeds` for a full regenerate), and note that `--apply`'s preflight now refuses any draft that isn't `current` (six refusal states, each named on refusal). Also cover `--accept-seed <plan-id>` as the path for keeping a reviewed hand edit to a draft instead of losing it to regeneration — it only accepts a draft classified `digest-mismatched`, and it never calls the backend. Point to `--view seeds` (step 8) as where an operator sees every plan's state and any orphaned sidecar entry or file before deciding which command to run. Whether this lands as new content prepended to § 6 or as a new numbered section inserted before it (renumbering §§ 6–7) is your call — either keeps the doc's existing structure intact for the surrounding sections.
- **Lines with `.../roadmaps/my-project/seeds/my-first-plan.md`** (the two `create --from-existing` example paths against the slug-relative draft, not the promoted `plan-seeds/` copy) — update to the `plan-seed-drafts/` prefix step 1 already renamed `DRAFT_SEEDS_DIRNAME` to, since this walkthrough is narrating a fresh roadmap. The legacy `seeds/` prefix stays valid read-only for a pre-existing roadmap (per step 1's Architecture), so a one-line note that an older roadmap may still show `seeds/`-prefixed paths is useful but not required.
- **§ 6's closing line, "This is a fallback; stage 4 is the normal way to derive the mapping and draft seeds."** — stage 4 no longer derives draft seeds, only the mapping. Reword to attribute draft-seed materialization to the separate per-plan step this section now describes.

### `docs/ROADMAP_DEMO_ORCHESTRATION.md`

Scope here is narrower than the walkthrough — this file is a dated runbook for one specific demo, not a general reference — but the same "docs must still work as a sequence of commands" concern applies to Phase 3.

- **§ 4 "Phase 1", the "Four Claude calls, one per stage, each gated before it writes" line** — same clarification as the walkthrough: still four calls for the stage run itself, but materializing seeds afterward is separate and not included in that count.
- **§ 4's artifact table, row 4** (`| \`04-roadmap.md\` + \`seeds/\` | ordered plan rows with intent, non-goals, dispositions, and draft seeds | 14 |`) — drop "+ `seeds/`" and "and draft seeds" (same reasoning as the walkthrough's table). Update the gate count from 14 to 13 (step 9 drops `check_draft_seed_provenance` from `PLANS_GATES`, per Input). The line immediately below the table, "Twenty-three distinct `check_*` functions across the four tuples; seven are shared by every stage," is the same underlying count and needs the matching correction, twenty-three to twenty-two — see Input for the arithmetic.
- **§ 6 "Phase 3 — promote the draft seeds"** — currently opens straight with `--apply`/`--apply -y`, and states "Draft seeds live under `<roadmap dir>/seeds/`" with `_validate_draft_seed_path` enforcing the `seeds/` prefix. After step 9, running `--apply` at this point in the runbook promotes nothing (every plan is still `missing`, since stage 4 never materialized anything). Add the missing step before the `--apply` commands: batch-materialize with `--materialize` (or target the visibility slice specifically, matching § 7's chosen plan). Update the directory-name paragraph to `plan-seed-drafts/` (step 1's rename), noting the enforced-path rule now accepts either prefix but new writes use the new name. Update the worked-example path (`docs/implementation-plans/roadmaps/ttrpg-world-builder/seeds/<plan-id>.md`) to the new prefix.
- **§ 10, "Claude calls: 4 for the stage run, plus 1 per revision re-entry ... plus `create`'s iterate loop, plus the two audits, plus `detail` (one call per step)"** — this cost accounting has no line for seed materialization at all, because previously it was bundled into the stage-4 call it's already counting. Add a line for the per-plan materialize cost (one call per plan row via `--materialize`/`--refresh-seeds`, run once as part of the new Phase 3 step above).
- Leave the dated "Measured 2026-08-06" results, the § 12 execution checklist, and any other content describing what a *specific past run* actually did untouched — those are historical record of an already-executed demo, not a claim about current behavior, and this step's job is forward-looking accuracy, not revising history.

### `docs/ARCHITECTURE.md`

All of the following sit inside the single "## Roadmap" paragraph (the paragraph opening "**Roadmap (`plan_tool/roadmap.py`, `roadmap_artifacts.py`, `roadmap_gates.py`, `roadmap_view.py`, `cli/roadmap_cmd.py`).**"). Edit it in place rather than restructuring the paragraph into multiple ones, matching this file's existing one-paragraph-per-subsystem convention elsewhere (see e.g. the Backend abstraction / Rate-limit recovery loop paragraphs above it).

- **The parenthetical module list** — add `roadmap_seed_manifest.py` alongside the existing five.
- **"...under `<plans_dir>/roadmaps/<slug>/`, plus draft seeds at each plan row's `draft_seed_path` under the slug directory."** — this describes stage 4 as producing the draft seed files themselves. Reword to say each plan row names a `draft_seed_path` destination, materialized independently of stage 4's own call (step 2's `materialize_plan_seed`, driven by `--materialize`/`--refresh-seeds`).
- **"Five modules on a **one-way import chain that forks below the gates**"** — becomes six. Per step 3's landed contract (see Input), `roadmap_seed_manifest.py` is a leaf importing only `roadmap_artifacts.py` and `roadmap_gates.py` (plus `roadmap_seed_state.py`, an existing module this paragraph does not currently name at all — see Deferred), sitting below `roadmap.py` and `roadmap_view.py` without either importing it back at first, though both are designed to call into it (steps 5/6/9/10 wire `roadmap.py`; steps 7/8 wire `roadmap_view.py`). Describe it as a third leaf alongside `roadmap_gates.py` in the fork — both `roadmap.py` and `roadmap_view.py` end up importing it, neither imports the other because of it. Verify the exact import edges against `plan_tool/roadmap_seed_manifest.py` as landed rather than trusting this paraphrase.
- **"twenty-two relation gates in four stage sets"** — leave this number alone. It reads as already-wrong today (today's true count is 23, per Input's arithmetic) but becomes correct once step 9 lands (22), and step 11 runs after step 9. Don't "fix" it to 23; verify it still reads 22 and move on.
- **"Default completion prints runnable `create --from-existing` lines against draft paths"** — make this conditional: a line prints only for a plan whose draft `roadmap_seed_manifest.classify_draft_seeds` calls `current`; a plan in any other state reports not-seed-ready and names `--materialize`/`--refresh-seeds` (step 9's `_create_handoff_lines` change).
- **"`04-roadmap.md` and its draft seeds are the top artifacts: no `N` rewrites `03-components.md` without also rewriting plans and draft seeds — pick `N` by the lowest artifact to regenerate (`--from-stage 4` when only the mapping and seeds need refresh; ...)"** — after step 9, `--from-stage 4` rewrites the mapping and *invalidates* existing drafts; it never regenerates their content. Reword to drop the claim that re-entering at stage 4 "refreshes" seeds — materializing invalidated drafts is a separate, explicit `--materialize`/`--refresh-seeds` call the operator makes afterward.

### `CAPABILITIES.md`

- **`architecture-roadmap`'s `surfaces:` list** — add `plan_tool/roadmap_seed_manifest.py`, matching `ARCHITECTURE.md`'s module-count edit above. This is required for `plan_tool/capability_catalog.py:check_capabilities`'s `absent-surface`/`orphan-subcommand` symmetry check (`plan-tool validate`) to keep passing once the module exists on disk — a path-shaped surface the catalog can check but that isn't listed is the kind of drift that check exists to catch, per the cross-step lesson on this exact file.
- **The prose bullet describing what stage 4 emits** — per Input, step 9's own detail file already commits to rewriting this sentence (dropping the "emits ... draft seeds" claim, making the handoff-lines clause conditional). Read the file as it stands. If it already says what this step needs it to say, leave it; if a gap remains (e.g., it doesn't yet reflect the module-count change, or some wording is still inconsistent with the now-landed behavior), fix only that gap. Do not rewrite the whole bullet again from scratch — that risks producing wording that disagrees with the corresponding claims in the now also-updated `ARCHITECTURE.md` paragraph.

## Tests

### Verification (non-code step)

This is a `non-code` step under a plan with `enforce_step_tests: true`; the test-authoring gate only fires for `feature`/`refactor` steps, so it does not apply here. Verify instead:

1. `rg -n "seeds/" docs/ROADMAP_WALKTHROUGH.md docs/ROADMAP_DEMO_ORCHESTRATION.md docs/ARCHITECTURE.md CAPABILITIES.md` — every remaining hit is either an explicit legacy-compatibility note (a pre-existing roadmap's paths stay `seeds/`-prefixed) or the unrelated top-level `plan-seeds/` promoted-copy directory, never a fresh-roadmap example presented as current convention.
2. `rg -n "four backend calls|Four Claude calls|and one draft seed per plan row|and draft seeds\b" docs/ROADMAP_WALKTHROUGH.md docs/ROADMAP_DEMO_ORCHESTRATION.md docs/ARCHITECTURE.md CAPABILITIES.md` — confirm no remaining hit implies stage 4 (or the initial roadmap run) produces seed content directly.
3. `rg -n "roadmap_seed_manifest" docs/ARCHITECTURE.md CAPABILITIES.md` — both files name the module (`ARCHITECTURE.md` in its Roadmap paragraph's module list and import-chain description; `CAPABILITIES.md` in the `architecture-roadmap` entry's `surfaces:` list).
4. `rg -n "Twenty-three|twenty-three|twenty-two" docs/ROADMAP_DEMO_ORCHESTRATION.md docs/ARCHITECTURE.md` — confirm both now read the same corrected count (22) and agree with each other and with `ROADMAP_FORMAT.md`'s own count (step 9's concern, already landed).
5. `python3 -c` (or equivalent) tally of `plan_tool/roadmap_gates.py`'s `DOMAIN_GATES`/`CONSTRAINTS_GATES`/`COMPONENTS_GATES`/`PLANS_GATES` entries confirms `PLANS_GATES` has 13 entries and the distinct-function total across all four is 22, matching what the docs now claim.
6. Every relative markdown link touched in these four files still resolves (`ROADMAP_FORMAT.md`, `SEED_FORMAT.md`, `RUNBOOK.md`, `docs/cli/roadmap.md`, cross-references between the four files themselves).
7. Manually walk `docs/ROADMAP_WALKTHROUGH.md`'s command sequence and `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s Phase 1 → Phase 3 sequence against `plan_tool/cli/roadmap_cmd.py`'s parser at HEAD: every flag named (`--materialize`, `--accept-seed`, `--view seeds`, `--refresh-seeds`, `--apply`) exists and takes the arguments the doc shows.
8. `plan-tool validate` passes (exercises `capability_catalog.check_capabilities`'s surface/subcommand symmetry over the updated `CAPABILITIES.md`).
9. `git status`/`git diff` shows changes only in the four declared files — no production code, prompt, or test file in this step's diff.

## Acceptance criteria

- `docs/ROADMAP_WALKTHROUGH.md`'s stage-4 table row and its "read the plan mapping" prose no longer claim the initial roadmap run leaves draft seeds on disk or unconditionally prints `create --from-existing` handoff lines.
- `docs/ROADMAP_WALKTHROUGH.md` documents `--materialize`, `--accept-seed`, and `--view seeds` as part of the seed lifecycle, and its two slug-relative draft-path examples use the `plan-seed-drafts/` prefix.
- `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s Phase 1 table row and adjacent gate-count sentence read 13 (`PLANS_GATES`) and 22 (total distinct gates), and no longer list `seeds/` or "draft seeds" as something stage 4's call writes.
- `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s Phase 3 section includes an explicit materialize step before `--apply`, and its worked-example path uses `plan-seed-drafts/`.
- `docs/ROADMAP_DEMO_ORCHESTRATION.md`'s § 10 cost accounting includes the per-plan seed materialization call(s).
- `docs/ARCHITECTURE.md`'s Roadmap paragraph names six roadmap modules (including `roadmap_seed_manifest.py`), states handoff lines print only for a `current` draft, and no longer claims `--from-stage 4` refreshes draft-seed content.
- `CAPABILITIES.md`'s `architecture-roadmap` entry's `surfaces:` list includes `plan_tool/roadmap_seed_manifest.py`.
- `CAPABILITIES.md`'s prose bullet about stage 4 is internally consistent with `ARCHITECTURE.md`'s corresponding claims (neither contradicts the other on what stage 4 emits or when handoff lines print).
- `plan-tool validate` passes.
- The diff for this step touches only `docs/ROADMAP_WALKTHROUGH.md`, `docs/ROADMAP_DEMO_ORCHESTRATION.md`, `docs/ARCHITECTURE.md`, and `CAPABILITIES.md`.

## References

- [ROADMAP_FORMAT.md](../../../ROADMAP_FORMAT.md) — the schema/gate contract step 9 already updates for the same behavior change; use its post-step-9 wording as the ground truth this step's docs must agree with, not re-derive independently.
- [docs/ROADMAP_WALKTHROUGH.md](../../../docs/ROADMAP_WALKTHROUGH.md) — the file this step edits; cited here as the plan's own reference for what step 11 corrects.

## Applicable guardrails

- **The plan's "Out of scope"** — "Changing how `create`, `detail`, Jira story generation, implementation, or plan/code reconciliation consume a promoted seed" binds this step to describing only the roadmap-side materialization/promotion mechanics; do not add or imply any change to how a promoted seed is consumed downstream.
- **The plan's "Out of scope"** — "Regenerating every seed on a roadmap revision ... or writing a replacement without the explicit materialization/refresh action" binds how this step must *describe* the lifecycle: every regeneration path named in these docs (`--materialize`, `--refresh-seeds`, `--accept-seed`) is operator-triggered, never automatic or implicit as a side effect of a stage run.
- **The plan's "Out of scope"** — "Reorganizing unrelated roadmap stages, `create`, or the generic plan-seed format" bounds the scope of the walkthrough/demo edits to the seed-materialization staleness this step exists to fix; do not restructure unrelated sections (stages 1–3's read-for-seams guidance, the feedback/decision-settling sections, `SEED_FORMAT.md` itself) while in these files.

## Deferred

- `roadmap_seed_state.py`'s absence from `ARCHITECTURE.md`'s Roadmap paragraph and its module-count language — this module already exists today and is not named in the "five modules" (soon "six modules") count even though `roadmap_seed_manifest.py` imports it. Pre-existing gap, not introduced by this plan; fixing it is a separate documentation cleanup, not part of this step's declared staleness.
- `docs/cli/roadmap.md`'s flag reference for `--materialize`/`--accept-seed`/`--view seeds` — regenerated by `python -m plan_tool.cli_reference --write` and drift-guarded by `tests/cli/test_cli_reference.py`; not hand-edited here.
- `ROADMAP_FORMAT.md` and `CLAUDE.md`'s own roadmap-module and gate-count corrections — already committed to steps 3 and 9 respectively (see Input); this step neither duplicates nor depends on redoing that work, only on it having landed.

<!-- plan-tool-detail-deferrals
{"deferrals":[]}
-->
