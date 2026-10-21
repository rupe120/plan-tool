> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 10 — Reconcile BACKLOG #208 and sweep roadmap operator docs for stage 4

## Summary

Close the documentation loop after stage 4 ships: reconcile `BACKLOG.md` **#208** so arc position **04** reads as shipped, and sweep the eight operator-facing docs that still describe a three-stage verb whose seed hop is manual-only. The main design choice matches position 03's reconciliation step: **correct claims in place, do not rewrite whole sections** — clause-level cardinality fixes in `docs/ARCHITECTURE.md` and terse bullet updates in `CLAUDE.md`, with workflow docs (`RUNBOOK.md`, `USE_CASES.md`, `docs/ROADMAP_WALKTHROUGH.md`) getting the automated hand-off, `--apply` carve-out, and downstream re-entry logic stage 4 changes (`04-roadmap.md` is the top artifact). On green, every file in the step's `files:` list describes four shipped stages, names the automated § 5 path with a short manual fallback, and #208 lists only position **05** as unauthored; gate counts match the landed modules; and step 9's measurement block is cited, not moved.

## Table of Contents

- [Summary](#summary) — backlog reconciliation plus an eight-file operator-doc sweep.
- [Why](#why) — three-stage / manual-hop prose is wrong once stage 4 lands.
- [Input](#input) — what steps 4–9 land, what to read off code, and what must stay untouched.
- [Files (creates vs edits)](#files-creates-vs-edits) — eight edits, no new files.
- [Implementation](#implementation) — per-file edit sites, count rules, and the `--apply` gotcha.
- [Tests](#tests) — non-code step; verification lives in the subsection below.
- [Verification (non-code step)](#verification-non-code-step) — greppable checks a reviewer runs instead of unit tests.
- [Acceptance criteria](#acceptance-criteria) — checkable facts on the finished tree.
- [References](#references) — docs worth skimming while editing prose.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step's edits.
- [Deferred](#deferred) — files and follow-ups this step deliberately does not touch.

## Why

Steps 1–7 make `plan-tool roadmap` a four-stage verb that writes gated `04-roadmap.md` and slug-relative draft seeds; steps 8–9 add the inverse `create` split pointer and one real human read recorded under **#208**. Until this step runs, eight documents still tell operators the verb stops at `03-components.md`, that turning artifacts into seeds is unbuilt position **04**, and that the only next move is to hand-author seeds from § 5 — including `RUNBOOK.md` and `USE_CASES.md` prose that says `03-components.md` is the top artifact with nothing downstream. That advice was true at three stages and becomes wrong at four. Stale cardinality in `CLAUDE.md`'s reference bullets also misleads every future session. This step is the plan's bookkeeping and operator-truth pass; it changes no code.

## Input

Land steps **4**, **6**, **7**, **8**, and **9** before implementing. Open the landed modules and sibling docs at execution time — **landed names and counts win** over anything in earlier details or plan prose.

**From step 4 (`ROADMAP_FORMAT.md`) — read only, do not edit:**

- Fourth-artifact schema, draft-seed conventions, and the six plan-relation gate rows for `04-roadmap.md`.
- Updated gate-inventory framing (four stage gate sets).
- Use this file as evidence that operator docs agree with the format reference; step 4 owns the schema doc itself.

**From step 6 (`plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-plans.md`, `plan_tool/cli/roadmap_cmd.py`) — symbols to cite, not re-specify:**

- **`STAGES[3]`** (or the row with `number==4`) — the plans row: `artifact_key="plans"`, `plans_path`, `parse_plans_artifact`, `render_plans_artifact`, `run_plans_gates` held by identity; **`side_output_seed_paths`** (or landed name) not `None`.
- **`len(plan_tool/roadmap.py:STAGES) == 4`** — full run writes four artifacts plus draft seeds under the slug directory; default completion does **not** write `plan-seeds/`.
- **`plan_tool/cli/roadmap_cmd.py`** — ordered `plan-tool create <plan-id> --from-existing <draft-path>` detail lines on stage-4 completion via **`_short_path`** (confirm landed helper name).

**From step 7 (`plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`) — apply-only path:**

- **`apply_roadmap_seeds`** (or landed name) — reads on-disk `04-roadmap.md`, refuse-by-default collisions, copies on `--apply` + confirm or `-y`.
- **`--apply`** mutually exclusive with **`--from-stage`**; stage runs stay non-interactive; **`-y` applies only under `--apply`**, not as a global roadmap yes flag (mirror **`scope-out`** wording).

**From step 8 (`plan_tool/cli/authoring.py`) — read only for cross-links:**

- **`_emit_split_proposal`** / **`_render_split_proposal_markdown`** — recommend-only generic pointer at the `roadmap` verb when `create` short-circuits on **`SplitProposal`**; no runnable slug/brief operands. Mention in operator docs where split guidance lives; do not edit this module in step 10.

**From step 9 (`BACKLOG.md`) — cite, do not restate or move:**

- The dated **first real stage-4 run** bullet step 9 appends under **#208** (plus any optional stage-4 retry / `--apply` sub-block).
- Step 9 explicitly reserves #208's `Status:` field, `docs/ROADMAP_WALKTHROUGH.md` § 7, and the other seven operator docs for this step.

**Counts to read off code when editing (do not transcribe from this detail):**

- **Relation gates** — `rg '^def check_' plan_tool/roadmap_gates.py` after step 3 (sixteen existing + six plan-relation = **twenty-two** at the plan's intended landing); stage sets are `DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, **`PLANS_GATES`** with `run_domain_gates`, `run_constraints_gates`, `run_components_gates`, **`run_plans_gates`**.
- **Stage numbering** — artifact stage `1` → `01-domain.md`, `2` → `02-constraints.md`, `3` → `03-components.md`, `4` → **`04-roadmap.md`** (`plan_tool/roadmap_artifacts.py:DOMAIN_FILENAME`, `CONSTRAINTS_FILENAME`, `COMPONENTS_FILENAME`, **`PLANS_FILENAME`**).

**What this step cannot check automatically.** Nothing diffs these prose files against code except `plan-tool validate`'s `plan_tool/capability_catalog.py:check_capabilities` sweep over `CAPABILITIES.md`. Every other claim stays correct by hand via the verification list below.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — **#208** only: `Status:` bullet (add position **04** shipped, narrow unauthored range to **05**); optional one-line touch to arc bullet 4 if the status narrative still reads as future work. Do **not** edit step 9's measurement block, the Framing bullet's settled decisions, or position 01–03 provenance paragraphs. Do **not** remove the **#208** entry when position 04 ships — the plan's acceptance criteria require reconciliation, not deletion.
  - `docs/ARCHITECTURE.md` — clause updates in the `**Roadmap (`plan_tool/roadmap.py`, …)**` paragraph under `## Roadmap`.
  - `CLAUDE.md` — terse updates to the `ROADMAP_FORMAT.md` and `docs/ROADMAP_WALKTHROUGH.md` bullets in `## Reference docs` (one or two clauses each; no new paragraph).
  - `CAPABILITIES.md` — the `architecture-roadmap` capability entry: four stages, fourth artifact, draft seeds, `--apply` promotion, create handoff.
  - `RUNBOOK.md` — quick-reference table, workflow opening, artifact table, stage-number mapping, downstream-artifact / pending-decision prose, **`### Where the arc stops today`**, and a short **`--apply`** subsection under the roadmap workflow.
  - `USE_CASES.md` — use case 11 body, `**Where the arc stops today.**` paragraph, entry-point table row for project-sized concepts; optional one line on **`SplitProposal`** → `roadmap` where create guidance lives.
  - `docs/ROADMAP_WALKTHROUGH.md` — intro, § 0 call-cost line, § 1 stage count, **§ 5** (automated path primary, manual fallback retained), § 7 arc table, closing paragraph.
  - `integrations/claude/SKILL.md` — situation table row, **Roadmap** subcommand blurb, and `ROADMAP_FORMAT.md` bullet (still says two artifacts at HEAD).

## Implementation

### Governing rule

Follow the repo's forward-looking documentation directive: describe what ships today; delete present-tense claims that stage 4 falsifies; keep dated measurements and settled don't-re-open decisions. One authority per fact — cite step 9's backlog bullet for the real stage-4 run, `ROADMAP_FORMAT.md` for schema, the modules for counts.

**Correct claims in place** — match position 03's reconciliation step. Do not paste implementation mechanics from steps 6–7 into operator docs; name outcomes (`04-roadmap.md`, draft seeds, printed create lines, optional `--apply`).

### `BACKLOG.md` #208

**`Status:` bullet — three edits:**

1. **Add a position-04 record** in the same shape as positions 01–03: what is live (four artifact stages; gated `04-roadmap.md` with component→plan mapping, ordering, assumptions; draft seeds under the slug directory; printed `create --from-existing` lines; opt-in `--apply` copies into `plan-seeds/` with refuse-by-default collisions), where the contract lives (`ROADMAP_FORMAT.md`, operator workflow in `RUNBOOK.md` / `USE_CASES.md` / `docs/ROADMAP_WALKTHROUGH.md`), and provenance — plan path `docs/implementation-plans/2-roadmap-04-plan-derivation.md`, step count, authoring date, seed archived under `plan-seeds/archive/` when present. Point at step 9's **first real stage-4 run** bullet for the human mapping/seed verdict; do not copy its numbers here.
2. **Narrow the unauthored range:** `Arc positions 04–05 stay unauthored` → **05 only** (plan derivation shipped; framework lenses remain).
3. **Drop discharged forward predictions** that position 04 was next to author — replace with shipped wording or delete. Update the note that **`integrations/claude/SKILL.md` still describes two stages — see #235** once this step sweeps that file (or narrow the #235 pointer if the skill is fixed here).

**Arc bullet 4** (`roadmap-04-plan-derivation`) already uses the correct "Leaves:" shape. Leave it unless the `Status:` narrative duplicates it awkwardly.

**Do not touch:** Framing bullet, position 01–03 status prose, step 9's appended measurement block, **#208**'s "shipped position-01 plan is deliberately left alone" fence, the **Deterministic gates** bullet's historical measurements unless a present-tense clause still promises position 04 as future work.

### `docs/ARCHITECTURE.md` — clause updates in the Roadmap paragraph

Edit in place; do not add a second roadmap section.

- **Output sentence** — the verb produces **`01-domain.md`**, **`02-constraints.md`**, **`03-components.md`**, and **`04-roadmap.md`** (plan list with dispositions, ordering, assumptions) plus **draft seeds** at each plan row's `draft_seed_path` under the slug directory.
- **Gate inventory** — replace "sixteen relation gates in three stage sets" with language naming **four stage gate sets** (`DOMAIN_GATES`, `CONSTRAINTS_GATES`, `COMPONENTS_GATES`, **`PLANS_GATES`**) and the total `check_*` count read off `plan_tool/roadmap_gates.py`.
- **Arc sentence** — record position **04** (`roadmap-04-plan-derivation`) as shipped beside 01–03; **framework lenses** (05) stay unauthored.
- **Top-artifact / re-entry clause** — **`04-roadmap.md`** is the top artifact: no `N` rewrites `03-components.md` without also rewriting plans and draft seeds. Pick `N` by the lowest artifact to regenerate (`--from-stage 4` when only the mapping and seeds need refresh; `--from-stage 3` when components change; earlier stages unchanged from position 03's table).
- **Hand-off clause** — default completion prints runnable **`create --from-existing`** lines against draft paths; **`plan-seeds/`** mutation only via **`--apply`** (+ confirm or `-y`), not on a normal stage run.
- **Non-interactive carve-out** — stage runs stay non-interactive; **`--apply`** is the scoped confirm-gated exception (same shape as **`scope-out`**), not a fifth stage.

**Verified non-edits:** four-module import line, disk-as-interface, revision-not-re-authoring, four failure kinds, exit codes 0/1/2, collaborates sentence, artifacts-not-plans — still true unless step 6–7 extended pre-flight lists and the paragraph enumerates them exhaustively.

### `CLAUDE.md` — two reference bullets only

Keep depth in the pointed-at docs; one or two clauses per bullet.

- **`ROADMAP_FORMAT.md` bullet** — **four** staged artifacts (`01-domain.md` through **`04-roadmap.md`**); relations in `plan_tool/roadmap_gates.py` as **four stage gate sets** with the landed total gate count.
- **`docs/ROADMAP_WALKTHROUGH.md` bullet** — end-to-end through **automated** plan derivation (stage 4) and printed create lines; § 5 keeps a **manual fallback** procedure; position **04** is shipped; position **05** (framework lenses) is not.

### `CAPABILITIES.md` — `architecture-roadmap` entry

Extend existing bullets; do not duplicate `ROADMAP_FORMAT.md`.

- Name **four stages** and the fourth artifact's role (component→plan mapping with closed dispositions, ordering, assumptions; draft seeds as side output).
- Mention **`--from-stage 4`**, printed **`create --from-existing`** handoff, and opt-in **`--apply`** promotion into `plan-seeds/`.
- Note plan ids participate in revision continuity and feedback targets like earlier design rows.
- Keep principles and surfaces unchanged unless a new module landed.

Run `plan-tool validate` — `check_capabilities` must stay green for cited surfaces and principle ids.

### `RUNBOOK.md` — sweep every stale three-artifact / manual-only site

Use `rg -n 'three files|three gated|03-components\.md.*top artifact|position 04|unbuilt|hand-author|manual hop|Arc positions 04' RUNBOOK.md` as the starting checklist.

- **Quick-reference table** — first row: four artifacts on a full run; add rows for `--from-stage 4` (re-enter at plans when `01`–`03` are gate-clean) and **`roadmap <slug> --apply`** / **`--apply -y`** (promote drafts to `plan-seeds/` without invoking stages).
- **Workflow opening** — replace "writes three files" with four artifacts plus draft seeds; extend the artifact table with **`04-roadmap.md`** (plans, ordering, assumptions; pointer to draft-seed paths and `ROADMAP_FORMAT.md`).
- **Stage number mapping** — `$N` list includes `4` → **`04-roadmap.md`**.
- **Downstream-artifact prose** — rewrite blocks that treat `03-components.md` as the permanent top artifact: with stage 4 shipped, **`04-roadmap.md`** and the draft set are downstream of components; domain/constraint/component edit rules from position 03 stay, extended with plans-stage re-entry.
- **`### Where the arc stops today`** — four artifacts plus draft seeds are the verb output; **`create --from-existing`** handoff is **automated** (printed lines; optional **`--apply`** for `plan-seeds/`). Point at `docs/ROADMAP_WALKTHROUGH.md` § 5 for the full operator narrative and manual fallback. Position **05** (framework lenses) remains unauthored.
- **`--apply` subsection (short)** — apply-only mode: no brief, no Claude, reads `04-roadmap.md`; preview by default; `-y` is second opt-in; refuse-by-default collisions; copies do not remove slug drafts.

Leave feedback/revision subsections structurally intact — add a stage-4 feedback example only where it clarifies (e.g. feedback targeting a plan row id).

### `USE_CASES.md` — use case 11 and entry table

Replace **`**Where the arc stops today.**`** and related prose:

- Four stages ship; stage 4 writes **`04-roadmap.md`**, draft seeds, and ordered create lines.
- **`--apply`** is optional promotion into `plan-seeds/`; it is not required to run `create` against slug-relative draft paths.
- Manual seed authoring is a **fallback**, not the only path — point at walkthrough § 5.

Update the entry-point table row: full run produces four artifacts and draft seeds; next step is review, then printed **`create --from-existing`** (and optionally **`roadmap --apply`**).

Add or extend one line where **`create`** split guidance lives: when distill returns **`SplitProposal`**, stdout names **`roadmap`** as the structured decomposition path (step 8); keep per-plan carve + **`create --from-existing`** advice unchanged.

Mirror **`RUNBOOK.md`** downstream-artifact fixes for `--from-stage` examples (include `--from-stage 4` where plans-only refresh applies).

### `docs/ROADMAP_WALKTHROUGH.md`

**§ 7 (required)** — position **04** → **shipped**; **05** stays unauthored. Closing paragraph: four artifacts, automated seed emission, collaborate framing unchanged.

**§ 5 (required restructure, not a delete)** — primary path is now **automated**:

- Open with what a full four-stage run produces: **`04-roadmap.md`**, draft seeds, CLI summary with create lines.
- Document the review loop on the mapping and seeds (feedback on plan rows, `--from-stage 4` revision) before optional **`--apply`**.
- Retain the measured **`cfp-review`** manual slice as **`### Manual fallback`** (or equivalent subheading) — the procedure step 9 used to judge reviewability stays available when stage 4 is skipped or rejected.
- Update provenance bullets in the fallback to name **four** artifacts where applicable; keep the frozen-rationale caveat.
- Drop opening claims that position **04** is not built or that § 5 is the **only** hand-off documentation.

**Intro** — replace "§ 5 — artifacts to seeds — is the only place the manual hand-off is written down" with language that § 5 covers **automated hand-off and manual fallback**.

**§ 0–§ 1** — "costs three Claude calls" → **four**; "All three stages run" → four stages; artifact count sentences → four artifacts plus draft seeds.

**Heading renames** — grep inbound `#` links (`rg -n 'ROADMAP_WALKTHROUGH|#5-|from-artifacts' BACKLOG.md CLAUDE.md RUNBOOK.md USE_CASES.md integrations/claude/SKILL.md`) before changing § 5's title or renumbering sections; prefer inserting subheadings over renumbering § 6–§ 7.

**Do not edit** step 9's evidence block in `BACKLOG.md`; **do not** retro-edit completed position-01/02/03 plan files.

### `integrations/claude/SKILL.md`

Sweep the three stale sites called out in #208's Status note and at HEAD:

- Situation table row for project-sized concepts — four artifacts, draft seeds, create lines; remove "hand-author the seed from two files" / "unbuilt position" wording.
- **Roadmap** subcommand group — four stages, **`04-roadmap.md`**, draft seeds, **`--apply`** exception to non-interactive (confirm / `-y` under apply only), **`--from-stage 4`**.
- **`ROADMAP_FORMAT.md` bullet** — four artifacts, not two.

Keep skill depth terse; point at `RUNBOOK.md` and `docs/ROADMAP_WALKTHROUGH.md` for workflows.

### Rejected alternative

A second committed measurement doc under `docs/`. Step 9 already placed the durable record in **#208**; this step reconciles status and operator docs only.

## Tests

This step is `change_type: non-code`. The plan sets `enforce_step_tests: true`, and the test-authoring gate keys on `change_type` and fires only for `feature` and `refactor` steps (`plan_tool/launcher.py:_step_requires_test_authoring`). Substitute verification is the numbered list below.

### Verification (non-code step)

Run after all edits:

1. **gate-count-match** — total `check_*` count and four-tuple framing in `docs/ARCHITECTURE.md` and `CLAUDE.md`'s `ROADMAP_FORMAT.md` bullet match `plan_tool/roadmap_gates.py` at HEAD (expect **twenty-two** after step 3 lands six plan-relation gates).
2. **four-artifacts-everywhere** — `rg -n 'three stages|three gated artifacts|writes three files|03-components\.md.*whole verb output|two gated artifacts under' BACKLOG.md CLAUDE.md CAPABILITIES.md RUNBOOK.md USE_CASES.md docs/ARCHITECTURE.md docs/ROADMAP_WALKTHROUGH.md integrations/claude/SKILL.md` returns nothing unless qualified as historical (rewrite to present tense instead).
3. **no-stale-arc-04-unauthored** — `rg -n 'position 04.*unauth|position 04.*unbuilt|arc positions 04–05.*unauth|04 \(plan derivation\).*unbuilt|still unbuilt \(BACKLOG #208\)' BACKLOG.md CLAUDE.md RUNBOOK.md USE_CASES.md docs/ROADMAP_WALKTHROUGH.md integrations/claude/SKILL.md` returns nothing in the eight declared files (historical bullets inside #208's Framing section that describe past state may stay if clearly dated — present-tense operator claims may not).
4. **automated-handoff-present** — `RUNBOOK.md`, `USE_CASES.md`, and `docs/ROADMAP_WALKTHROUGH.md` § 5 describe stage-4 output (`04-roadmap.md`, draft seeds, printed `create --from-existing` lines) as the default path; manual-only hop is labeled fallback, not primary.
5. **apply-carve-out** — `RUNBOOK.md` and `integrations/claude/SKILL.md` state that **`--apply`** / **`-y`** apply only to seed promotion, not to stage runs; stage runs remain non-interactive.
6. **downstream-artifact-fixed** — `RUNBOOK.md` and `USE_CASES.md` name **`04-roadmap.md`** as the top artifact (not `03-components.md` alone) and document `--from-stage 4` for plans-only refresh when upstream is gate-clean.
7. **walkthrough-section-7** — `docs/ROADMAP_WALKTHROUGH.md` § 7 table row for position **04** reads **shipped**; position **05** still unauthored.
8. **walkthrough-section-5-dual** — § 5 documents automated hand-off **and** retains manual fallback content (subheading or equivalent — not deleted wholesale).
9. **position-04-recorded** — #208 `Status:` bullet records position **04** shipped with plan path `docs/implementation-plans/2-roadmap-04-plan-derivation.md` and unauthored range starting at **05** only.
10. **step-9-block-untouched** — `git diff BACKLOG.md` does not change step 9's **first real stage-4 run** bullet (only `Status:` / reconciling prose elsewhere in #208).
11. **position-01-plan-untouched** — no diff under `docs/implementation-plans/2-roadmap-01-domain-constraints.md` or its detail bundle.
12. **footprint** — commit touches only the eight declared paths.
13. **validate-green** — `uv run pytest tests/test_capability_catalog.py -q` (or full `plan-tool validate` on a registered plan) passes.
14. **links-resolve** — every `#208` cite and plan path in edited prose exists; grep inbound `#`-anchors before any walkthrough heading rename.
15. **no-auto-create-claims** — none of the eight files imply `roadmap` auto-runs `create`, `detail`, or `run` on emitted seeds.
16. **split-pointer-present** — `USE_CASES.md` or `integrations/claude/SKILL.md` mentions the recommend-only `roadmap` pointer on `create`'s split short-circuit (step 8); no invented slug/brief operands in example text.

## Acceptance criteria

- `BACKLOG.md` #208 `Status:` records arc position **04** as shipped (same provenance shape as 01–03) and lists **05** as the only remaining unauthored position; the **#208** entry is **not** removed.
- #208 does not claim plan derivation or stage 4 are future work in the `Status:` narrative.
- `docs/ARCHITECTURE.md`'s Roadmap paragraph describes four output artifacts, four stage gate sets, draft seeds, printed create handoff, and a total gate count equal to `rg -c '^def check_' plan_tool/roadmap_gates.py`.
- `CLAUDE.md` reference bullets for `ROADMAP_FORMAT.md` and `docs/ROADMAP_WALKTHROUGH.md` agree with four stages, automated § 5 hand-off, and manual fallback.
- `CAPABILITIES.md` `architecture-roadmap` mentions stage 4, `04-roadmap.md`, draft seeds, and `--apply` without orphaning the `roadmap` subcommand surface.
- `RUNBOOK.md` quick reference, workflow, downstream re-entry table, and "Where the arc stops today" describe four artifacts, `--from-stage 4`, and `--apply` promotion.
- `USE_CASES.md` use case 11 and the entry table no longer promise a three-artifact-only verb or hand-author-seed as the only next step.
- `docs/ROADMAP_WALKTHROUGH.md` § 7 lists position **04** as **shipped**; § 5 describes the automated path and keeps manual fallback prose.
- `integrations/claude/SKILL.md` no longer describes a two-stage-only roadmap or unbuilt seed emission.
- Step 9's backlog measurement block is unchanged by this step's diff.
- Commit touches exactly the eight paths in the step's `files:` list; `plan-tool validate` capability check passes.

## References

- [YAML 1.2.2](https://yaml.org/spec/1.2.2/) — frontmatter grammar for any `04-roadmap.md` or draft-seed fragments quoted into swept prose.
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — path language for slug-relative draft seeds and `plan-seeds/` promotion when describing `--apply`.

## Applicable guardrails

- **The plan's step intent** — operator docs describe **four shipped stages**, automated § 5 hand-off with manual fallback, and #208 marks position **04** done; no code, prompts, or gates change here.
- **The plan's Out of scope, position 05** — no framework-lens or `--framework` prose beyond naming 05 as unauthored.
- **The plan's Out of scope, auto-running create/detail/run** — docs describe printed create lines and optional `--apply` only; never imply auto-chaining into the pipeline.
- **The plan's Out of scope, merit and quality gates** — docs may say a human judges mapping and seed quality; they must not claim the tool scores dispositions or seed Outcomes.
- **The plan's Out of scope, interactive review walks** — describe bounded gate retry and existing feedback re-entry; no seed-content review walk.
- **#208's "shipped position-01 plan is deliberately left alone"** — do not retro-edit `docs/implementation-plans/2-roadmap-01-domain-constraints.md` during this sweep.

## Deferred

- **`ROADMAP_FORMAT.md` and `tests/test_roadmap_format.py`** — step 4's deliverable; read as evidence only.
- **`docs/cli/roadmap.md`** — not in this step's `files:` list; step 7 may have regenerated it when `--apply` landed. If operator prose and the generated reference diverge, file a **`BACKLOG.md`** hygiene follow-up rather than expanding this step's footprint (or note in #208 Status that CLI reference was updated in step 7).
- **Step 9's measurement bullet under #208** — evidence source; cite, do not move or reword.
- **Arc position 05 (framework lenses)** — stays unauthored; this step records that fact, does not seed it.
- **`README.md` tree registration** — not the index for root FORMAT docs; `CLAUDE.md` reference list is.
- **Resolving `BACKLOG.md` #235** — if this step fully sweeps `integrations/claude/SKILL.md`, note discharge in #208 Status or narrow #235; do not re-litigate lens work.
- **Running `create` on emitted seeds to measure convergence** — explicitly out of scope for this plan.
- **Full narrative walkthrough of stage 4 on `cfp-review`** — optional; step 9's backlog record and schema docs are enough for completion.
