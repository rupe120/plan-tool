> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 7 — Reconcile BACKLOG #208 and sweep roadmap operator docs for stage 3

## Summary

Close the documentation loop after stage 3 ships: mark arc position 03 done in `BACKLOG.md` **#208**, and sweep the seven operator-facing docs that still describe a two-stage verb whose next hop is hand-authored seeds. The main design decision matches position 02's reconciliation step: **correct claims in place, do not rewrite whole sections** — clause-level edits in `docs/ARCHITECTURE.md` and terse bullet updates in `CLAUDE.md`, with the workflow docs (`RUNBOOK.md`, `USE_CASES.md`, `docs/ROADMAP_WALKTHROUGH.md`) getting the downstream-artifact logic that stage 3 changes (`02-constraints.md` is no longer the top artifact). On green, every file in the step's `files:` list describes three shipped stages and points seed emission at position 04; gate and vocabulary counts match the landed modules; and step 6's measurement block is cited, not moved.

## Table of Contents

- [Summary](#summary) — backlog reconciliation plus a seven-file operator-doc sweep.
- [Why](#why) — two-artifact prose is wrong the moment stage 3 lands, and it misleads the downstream re-entry advice.
- [Input](#input) — what steps 4–6 land, what to read off code, and what must stay untouched.
- [Files (creates vs edits)](#files-creates-vs-edits) — seven edits, no new files.
- [Implementation](#implementation) — per-file edit sites, count rules, and the downstream-artifact gotcha.
- [Tests](#tests) — non-code step; verification lives in the subsection below.
- [Verification (non-code step)](#verification-non-code-step) — greppable checks a reviewer runs instead of unit tests.
- [Acceptance criteria](#acceptance-criteria) — checkable facts on the finished tree.
- [References](#references) — docs worth skimming while editing prose.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step's edits.
- [Deferred](#deferred) — files and follow-ups this step deliberately does not touch.

## Why

Steps 1–5 make `plan-tool roadmap` a three-stage verb that writes gated `03-components.md`; step 6 records one real partition read under **#208**. Until this step runs, six documents still tell operators the verb stops at `01-domain.md` and `02-constraints.md`, that the next move is to hand-author a seed from those two files, and that arc position 03 is unauthored — including `RUNBOOK.md` and `USE_CASES.md` prose that says a hand edit to `02-constraints.md` needs no re-run because nothing downstream depends on it. That advice was true at two stages and becomes wrong at three. Stale cardinality in `CLAUDE.md`'s reference bullets also misleads every future session. This step is the plan's bookkeeping and operator-truth pass; it changes no code.

## Input

Open the landed modules and sibling docs at execution time — **landed names and counts win** over anything in earlier details or plan prose.

**From step 4 (`ROADMAP_FORMAT.md`) — read only, do not edit:**

- The third-artifact schema, path convention, and gate table rows for `03-components.md`.
- The updated gate-inventory framing (three stage gate sets, not "eleven gates, nine per stage" as the whole story).
- Use this file as evidence that operator docs agree with the format reference; step 4 owns the schema doc itself.

**From step 5 (`plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-components.md`) — symbols to cite, not re-specify:**

- **`STAGES[2]`** — the components row: `artifact_key="components"`, `components_path`, `parse_components_artifact`, `render_components_artifact`, `run_components_gates` held by identity.
- **`len(plan_tool/roadmap.py:STAGES) == 3`** — full run writes three artifacts; `--from-stage 3` re-enters at components only when upstream pre-flight passes.
- Prompt loads upstream text as `${domain_artifact}` and `${constraints_artifact}`; revision still uses `plan_tool/prompts/roadmap-revision.md`.

**From step 6 (`BACKLOG.md`) — cite, do not restate or move:**

- The dated **first real stage-3 run** bullet step 6 appends under **#208**.
- Step 6 explicitly reserves #208's `Status:` field, the arc-position table in `docs/ROADMAP_WALKTHROUGH.md` § 7, and the other six operator docs for this step.

**Counts to read off code when editing (do not transcribe from this detail):**

- **Closed vocabularies** — enumerate the closed enums/tuples `plan_tool/roadmap_artifacts.py` owns (at HEAD after step 1: `DecisionStatus`, `FeedbackState`, `FeedbackTargetKind`, `FieldType`, `ConstraintDisposition`, plus `QUALITY_ATTRIBUTES`; confirm nothing new landed).
- **Relation gates** — `rg '^def check_' plan_tool/roadmap_gates.py` after step 3 (eleven existing + five traceability = **sixteen** `check_*` functions at the plan's intended landing); stage sets are `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES` with `run_domain_gates`, `run_constraints_gates`, `run_components_gates`.
- **Stage numbering** — artifact stage `1` → `01-domain.md`, `2` → `02-constraints.md`, `3` → `03-components.md` (`plan_tool/roadmap_artifacts.py:DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`).

**What this step cannot check automatically.** Nothing diffs these prose files against code except `plan-tool validate`'s `plan_tool/capability_catalog.py:check_capabilities` sweep over `CAPABILITIES.md`. Every other claim stays correct by hand via the verification list below.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — **#208** only: `Status:` bullet (add position 03 shipped, narrow unauthored range to 04–05); narrow the **Deterministic gates** bullet so position-03 coverage is entity-id ownership/coverage (what stage 3 actually gates), and bridge or defer rule/workflow→component mapping to position 04; optional one-line touch to arc bullet 3 if it still reads as future work in the status narrative. Do **not** edit step 6's measurement block, the Framing bullet's settled decisions, or position 01/02 provenance paragraphs.
  - `docs/ARCHITECTURE.md` — clause updates in the `**Roadmap (`plan_tool/roadmap.py`, …)**` paragraph under `## Roadmap`.
  - `CLAUDE.md` — terse updates to the `ROADMAP_FORMAT.md` and `docs/ROADMAP_WALKTHROUGH.md` bullets in `## Reference docs` (one or two clauses each; no new paragraph).
  - `CAPABILITIES.md` — the `architecture-roadmap` capability entry: three stages, third artifact, partition/traceability in one bullet.
  - `RUNBOOK.md` — quick-reference table, workflow opening, artifact table, stage-number mapping, downstream-artifact / pending-decision prose, and `### Where the arc stops today`.
  - `USE_CASES.md` — use case 11 body, `**Where the arc stops today.**` paragraph, and the entry-point table row for project-sized concepts.
  - `docs/ROADMAP_WALKTHROUGH.md` — intro, § 0 call-cost line, § 1 stage count, § 5 opening framing (manual hop scope), § 7 arc table, closing paragraph; add a short stage-3 section only if step 6 left a citable `03-components.md` worth quoting — otherwise point at `ROADMAP_FORMAT.md` and step 6's record.

## Implementation

### Governing rule

Follow the repo's forward-looking documentation directive: describe what ships today; delete present-tense claims that stage 3 falsifies; keep dated measurements and settled don't-re-open decisions. One authority per fact — cite step 6's backlog bullet for the real run, `ROADMAP_FORMAT.md` for schema, the modules for counts.

### `BACKLOG.md` #208

**`Status:` bullet — three edits:**

1. **Add a position-03 record** in the same shape as positions 01 and 02 already use: what is live (three artifact stages; gated `03-components.md` with entity coverage and prioritized-constraint discharge; component ids in revision continuity and feedback targets), where the contract lives (`ROADMAP_FORMAT.md`, operator workflow in `RUNBOOK.md` / `USE_CASES.md`), and provenance — plan path `docs/implementation-plans/2-roadmap-03-components.md`, step count **7**, authoring date, seed archived at `plan-seeds/archive/roadmap-03-components.replaced.md`. Point at step 6's **first real stage-3 run** bullet for the human partition read; do not copy its numbers here.
2. **Narrow the unauthored range:** `Arc positions 03–05 stay unauthored` → **04–05** (components shipped; plan derivation and framework lenses remain).
3. **Drop discharged forward predictions** that position 03 was next to author — replace with shipped wording or delete.

**Deterministic gates bullet — align with what ships:** replace "every component maps to ≥1 domain concept" / "every domain concept lands in some component" with **entity-id** coverage (every component names ≥1 entity id; every entity lands in ≥1 component). State that business-rule and workflow assignment to components is **not** a stage-3 gate — defer that mapping to position 04 (or an explicit non-goal). Do not leave #208 promising rule/workflow→component traceability that `COMPONENTS_GATES` does not enforce.

**Arc bullet 3** (`roadmap-03-components`) already uses the correct "Leaves:" shape. Leave it unless the `Status:` narrative duplicates it awkwardly; do not re-argue the convergence loop (position 02's revision machinery is inherited — see plan Architecture).

**Do not touch:** Framing bullet (collaborate-don't-replace, 2026-08-01 measurement, do-not-re-cut fence), position 01/02 status prose, step 6's appended measurement block, **#208**'s "shipped position-01 plan is deliberately left alone" fence.

### `docs/ARCHITECTURE.md` — clause updates in the Roadmap paragraph

Edit in place; do not add a second roadmap section.

- **Output sentence** — the verb now produces **`01-domain.md`**, **`02-constraints.md`**, and **`03-components.md`** (logical components, system/component patterns, constraint discharge claims) under `<plans_dir>/roadmaps/<slug>/`.
- **Gate inventory** — replace "eleven relation gates — nine of them run per stage" with language that names **three stage gate sets** (`DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`) and the total `check_*` count read off `plan_tool/roadmap_gates.py`. Do not claim a uniform "nine per stage" — components carries five traceability gates plus the shared revision gates.
- **Arc sentence** — record position **03** (`roadmap-03-components`) as shipped beside 01 and 02; **plan derivation** (04) and **framework lenses** (05) stay unauthored.
- **Downstream-artifact implication (one clause)** — `run_roadmap` skips only stages *below* `from_stage`, so `--from-stage N` rewrites N and every stage above it. Until position 04 exists, `03-components.md` is the top artifact: no `N` rewrites constraints without also rewriting components. Pick `N` by the lowest artifact you want regenerated (`--from-stage 3` when only components needs a refresh).

**Verified non-edits** (confirm before leaving alone):

- "A stage is a row of data, not a branch" and the `RoadmapStage` tuple — step 5 adds a row, not a branch (`rg 'stage\.(name|number) ==' plan_tool/roadmap.py` should still return nothing).
- Four-module import line, disk-as-interface, revision-not-re-authoring, four failure kinds, exit codes 0/1/2, non-interactive, collaborates sentence, artifacts-not-plans — all still true; enumerate pre-flight causes only if step 5 extended them and the paragraph lists them exhaustively.

### `CLAUDE.md` — two reference bullets only

Keep depth in the pointed-at docs; one or two clauses per bullet.

- **`ROADMAP_FORMAT.md` bullet** — three staged artifacts (`01-domain.md`, `02-constraints.md`, `03-components.md`); relations in `plan_tool/roadmap_gates.py` as **three stage gate sets** with the landed total gate count, not "eleven gates, nine per stage."
- **`docs/ROADMAP_WALKTHROUGH.md` bullet** — manual hand-off to seeds is still written down for **position 04** (plan derivation); position **03** is shipped. Do not imply seeds are automated.

### `CAPABILITIES.md` — `architecture-roadmap` entry

Extend the existing bullets; do not duplicate `ROADMAP_FORMAT.md`.

- Name **three stages** and the third artifact's role (partition into logical components grounded in entity ids from domain and constraint discharge from constraints).
- Mention **`--from-stage 3`** and that component ids participate in the same feedback/revision contract as earlier design rows.
- Keep principles and surfaces unchanged unless a new module landed (it did not).

`plan-tool validate` runs `check_capabilities` — ensure cited surfaces still exist and the entry still maps to valid principle ids.

### `RUNBOOK.md` — sweep every stale two-artifact site

Use `rg -n 'two files|two gated|01-domain\.md.*02-constraints|whole output|top artifact|Arc positions 03|unbuilt position' RUNBOOK.md` as the starting checklist; confirm each hit against the edit rules below.

- **Quick-reference table** (Roadmap rows near the top) — first row: three artifacts on a full run; add a row for `--from-stage 3` (re-enter at components when `01-domain.md` and `02-constraints.md` are gate-clean).
- **`## Workflow: turn a concept brief into architecture artifacts`** — opening command still valid; replace "writes two files" with three; extend the artifact table with `03-components.md` (components, patterns, discharge claims; traceability gates named in `ROADMAP_FORMAT.md`).
- **Stage number mapping** — `$N` list includes `3` → `03-components.md`.
- **Downstream-artifact prose** — the block that says settling `pending` in `02-constraints.md` needs no re-run because it is the "top artifact today" must be rewritten: with stage 3 shipped, `03-components.md` is the top artifact until position 04, so pick `--from-stage N` by the lowest artifact to regenerate (`2` rewrites constraints *and* components; `3` refreshes components alone when upstream is gate-clean). Hand edits to **`03-components.md`** without feedback still need no re-run until position 04.
- **`### Where the arc stops today`** — three artifacts are the verb output; turning them into **`create --from-existing` seeds** remains position **04** (unauthored). Point at `docs/ROADMAP_WALKTHROUGH.md` § 5 for the manual seed procedure from the artifacts (including components), not from domain/constraints alone.

Leave the feedback/revision subsections structurally intact — add a stage-3 example only where it clarifies (e.g. feedback targeting a component id), not a second walkthrough.

### `USE_CASES.md` — use case 11 and entry table

Mirror the `RUNBOOK.md` downstream-artifact fix in the **`**Where the arc stops today.**`** paragraph: three artifacts ship; seed emission is position **04**; § 5 of the walkthrough still owns the manual hop.

- Update the prose that says the verb "writes two gated artifacts" and the entry-point table row that promises only `01-domain.md` + `02-constraints.md`.
- Add `--from-stage 3` to the command examples when showing components re-entry.

### `docs/ROADMAP_WALKTHROUGH.md`

**§ 7 (required)** — position **03** → **shipped**; 04 and 05 stay unauthored.

**§ 5 (required framing, not a rewrite)** — opening still owns the manual hop to seeds until position 04, but:

- Drop "arc positions 03 and 04 … neither is built" — **03 is built**, 04 is not.
- Replace "what the unbuilt components position would decide" with reading **`03-components.md`** as the partition surface (gate-clean structure; partition quality is reviewer judgment per step 6).
- **Required:** § 5's slice procedure reads `03-components.md` for component and pattern ids as provenance, and still pulls rule/workflow ids from `01-domain.md` until position 04 automates mapping — not optional "may cite."

**Intro and § 0–§ 1** — "costs two Claude calls" → **three**; "Both stages run" → three stages; closing "Two artifacts" sentence → three artifacts plus the same collaborate framing.

**Optional § for stage 3 narrative** — add `## 4. Stage 3 — 03-components.md` (renumbering later sections breaks inbound anchors — **grep `#` links before any heading renumber**; prefer inserting without renumbering § 4–§ 7 if possible) only when step 6 recorded a quotable partition on `cfp-review` or `toollib`. Otherwise one forward pointer to `ROADMAP_FORMAT.md` and the backlog measurement suffices.

**Do not edit** step 6's evidence block in `BACKLOG.md`; **do not** retro-edit `docs/implementation-plans/2-roadmap-01-domain-constraints.md`.

### Filing this plan's deferrals

Sweep this plan's seven detail files' `## Deferred` sections plus the plan body's `## Deferred` for routes to `BACKLOG.md` / `BUG_BACKLOG.md`. Confirm each target entry exists or write one using that file's scope-contract shape. The plan-level list names position 04, 05, #168, stage-as-data widening if observed, #215 evidence-only, and carve-B — most already have homes; cite existing entries rather than duplicating.

**Stage-as-data closure (required):** after step 5 has landed, record under **#208** Status (one clause) or by resolving the plan Deferred bullet whether stage 3 needed any `RoadmapStage` / orchestrator widening beyond the step-2 `components` envelope slot. A negative result is the expected and useful answer — write it down; do not leave the Deferred bullet open after evidence exists.

### Rejected alternative

A second committed measurement doc under `docs/`. Step 6 already placed the durable record in **#208**; this step reconciles status and operator docs only.

## Tests

This step is `change_type: non-code`. The plan sets `enforce_step_tests: true`, and the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps (`plan_tool/launcher.py:_step_requires_test_authoring`). Substitute verification is the numbered list below.

### Verification (non-code step)

Run after all edits:

1. **gate-count-match** — total `check_*` count and three-tuple framing in `docs/ARCHITECTURE.md` and `CLAUDE.md`'s `ROADMAP_FORMAT.md` bullet match `plan_tool/roadmap_gates.py` at HEAD.
2. **vocabulary-count-match** — closed-vocabulary count in `docs/ARCHITECTURE.md` matches `plan_tool/roadmap_artifacts.py` at HEAD.
3. **three-artifacts-everywhere** — `rg -n 'writes two (files|gated artifacts)|two artifacts under|01-domain\.md.*02-constraints\.md.*whole output' BACKLOG.md CLAUDE.md CAPABILITIES.md RUNBOOK.md USE_CASES.md docs/ARCHITECTURE.md docs/ROADMAP_WALKTHROUGH.md` returns nothing unless qualified as historical (rewrite to present tense instead).
4. **no-stale-arc-03-unauthored** — `rg -n 'position 03.*unauth|arc positions 03–(04|05).*unauth|03–04 are unbuilt' BACKLOG.md CLAUDE.md RUNBOOK.md USE_CASES.md docs/ROADMAP_WALKTHROUGH.md` returns nothing.
5. **downstream-artifact-fixed** — `RUNBOOK.md` and `USE_CASES.md` no longer say `02-constraints.md` is the top artifact with nothing downstream depending on it without naming stage 3; they state that domain entity-coverage edits and prioritized-constraint edits need `--from-stage 3` (or earlier), not `--from-stage 2` alone.
6. **walkthrough-section-7** — `docs/ROADMAP_WALKTHROUGH.md` § 7 table row for position 03 reads **shipped**.
7. **walkthrough-section-5-scope** — § 5 still documents manual seed hand-off and names position **04** as unbuilt (not 03); § 5 requires reading `03-components.md` for component/pattern provenance while still pulling rules/workflows from domain.
8. **position-03-recorded** — #208 `Status:` bullet records position 03 shipped with plan path `docs/implementation-plans/2-roadmap-03-components.md` and unauthored range starting at **04**.
9. **stage-as-data-closure** — #208 Status (or the resolved plan Deferred bullet) records whether stage 3 needed orchestrator/`RoadmapStage` widening beyond the step-2 `components` slot (negative result is valid and expected).
10. **step-6-block-untouched** — `git diff BACKLOG.md` does not change step 6's **first real stage-3 run** bullet (only `Status:` / reconciling prose elsewhere in #208).
11. **position-01-plan-untouched** — no diff under `docs/implementation-plans/2-roadmap-01-domain-constraints.md` or its detail bundle.
12. **footprint** — commit touches only the seven declared paths.
13. **validate-green** — `uv run pytest tests/test_capability_catalog.py tests/cli/test_inspect_cmds.py -q -k capability` (or full `plan-tool validate` on a registered plan) passes; `uv run pytest tests/ -q -n auto` stays green.
14. **links-resolve** — every `#208`, `#215` cite and plan path in edited prose exists; grep inbound `#`-anchors before any walkthrough heading rename.

## Acceptance criteria

- `BACKLOG.md` #208 `Status:` records arc position **03** as shipped (same provenance shape as 01/02) and lists **04–05** as the remaining unauthored positions.
- #208 does not claim components or stage 3 are future work in the `Status:` narrative.
- `docs/ARCHITECTURE.md`'s Roadmap paragraph describes three output artifacts, three stage gate sets, and a total gate count equal to `rg -c '^def check_' plan_tool/roadmap_gates.py`.
- `CLAUDE.md` reference bullets for `ROADMAP_FORMAT.md` and `docs/ROADMAP_WALKTHROUGH.md` agree with three stages and position-04-unbuilt seed hand-off.
- `CAPABILITIES.md` `architecture-roadmap` mentions stage 3 and `03-components.md` without orphaning the `roadmap` subcommand surface.
- `RUNBOOK.md` quick reference, workflow, and "Where the arc stops today" describe three artifacts and correct downstream re-entry for edits to `01-domain.md` and `02-constraints.md`.
- `USE_CASES.md` use case 11 and the entry table no longer promise a two-artifact-only verb or hand-author-seed-from-two-files as the only next step.
- `docs/ROADMAP_WALKTHROUGH.md` § 7 lists position 03 as **shipped**; § 5 still owns manual hop to seeds until position 04 and requires component/pattern ids from `03-components.md` in the slice procedure.
- #208's **Deterministic gates** prose matches entity-id coverage for position 03 (no over-promise of rule/workflow→component gates).
- Step 6's backlog measurement block is unchanged by this step's diff.
- A `BACKLOG.md` follow-up exists (or is confirmed already filed) for sweeping `integrations/claude/SKILL.md` to three stages.
- Commit touches exactly the seven paths in the step's `files:` list; `plan-tool validate` capability check passes.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — frontmatter grammar for any `03-components.md` fragment quoted into swept prose; keep snippets parseable.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — skimming only if validating quoted examples against `parse_components_artifact`.

## Applicable guardrails

- **The plan's step intent** — operator docs describe **three shipped stages** and #208 marks position 03 done; no code, prompts, or gates change here.
- **The plan's Out of scope, position 04** — do not write prose implying draft seeds or `04-roadmap.md` ship; seed emission stays manual via § 5 until position 04.
- **The plan's Out of scope, position 05** — no framework-lens or `--framework` prose.
- **The plan's Out of scope, partition quality gates** — docs may say a human judges partition quality; they must not claim the tool scores or gates merit.
- **The plan's Out of scope, new convergence loop** — describe bounded gate retry and existing feedback re-entry only.
- **#208's "shipped position-01 plan is deliberately left alone"** — do not retro-edit `docs/implementation-plans/2-roadmap-01-domain-constraints.md` during this sweep.

## Deferred

- **`ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py`** — step 4's deliverable; this step reads them as evidence only.
- **`plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-components.md`, CLI help, and `docs/cli/roadmap.md`** — step 5 wiring; argparse-generated reference needs no regeneration when flags unchanged.
- **Step 6's measurement bullet under #208** — evidence source; cite, do not move or reword.
- **`integrations/claude/SKILL.md`** — not in this step's declared `files:` list; it still carries two-artifact operator rows at HEAD. **File a `BACKLOG.md` follow-up** (scope: sweep that skill for three stages and `--from-stage 3`) when filing this plan's deferrals — do not expand this plan's footprint to absorb it.
- **Three-stage CLI overwrite-pointer tests** — owned by step 5 (`tests/cli/test_roadmap_cmd.py`); not deferred here.
- **Arc positions 04–05** — stay unauthored; this step records that fact, does not seed them.
- **Resolving `BACKLOG.md` #215 or changing `MAX_STAGE_ATTEMPTS`** — step 6 adds evidence only.
- **Full narrative walkthrough of stage 3 on `cfp-review`** — optional; depends on step 6 leaving a quotable artifact. Schema and backlog record are enough for completion.
- **README.md tree registration** — not the index for root FORMAT docs; `CLAUDE.md` reference list is.
