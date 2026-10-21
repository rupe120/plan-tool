> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 9 — Run stage 4 on an existing brief and record human-review outcomes

## Summary

Drive the shipped four-stage `roadmap` verb once against a real concept brief whose `01-domain.md`, `02-constraints.md`, and `03-components.md` already gate clean, using `--from-stage 4` when upstream artifacts are on disk, and have a human read the resulting `04-roadmap.md` and draft seeds for mapping and seed reviewability — not just gate conformance. Optionally promote **one** draft with `plan-tool roadmap <slug> --apply -y` to prove step 7's apply-only path. Write what happened into `BACKLOG.md` as a dated measurement block under **#208**, with a stage-4 retry sample beside the existing **#215** tables. The main design decision matches position 03's exercise step: **the durable record lives in `BACKLOG.md`, not a new `docs/` file** — briefs, artifacts, run logs, and scratch plans dirs stay gitignored, and #208 already carries real-run evidence this way. On green, a reader who never ran stage 4 can see the commands, gate-observable traceability facts, the reviewer's mapping and seed verdict, optional apply outcome, and operational numbers — and nothing in the record gates anything.

## Table of Contents

- [Summary](#summary) — the real run, the human read, optional apply, and where the record lands.
- [Why](#why) — gates prove structure; only a person can say the mapping and seeds are reviewable.
- [Input](#input) — what steps 6–7 hand this step, which briefs qualify, and what one reading cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — one edit; everything else stays scratch.
- [Implementation](#implementation) — the reading rule, upstream fixture, stage-4 run, machine checks, human review, optional apply, and backlog block.
- [Tests](#tests) — substitute verification for a non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — docs worth skimming for the run and record shape.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what step 10 owns and what is deliberately not measured.

## Why

Steps 1–7 make stage 4 runnable: the fourth `STAGES` row, six plan-relation gates in `run_plans_gates`, dual-output lift and write, draft-path create handoff, and opt-in `--apply` promotion. Every test in those steps is hermetic — canned multi-fence responses through the real parser and gates — which proves the contract is satisfiable and says nothing about whether a real model produces a component→plan mapping and draft seeds a human can actually review before `create`. That gap is the whole point of the plans artifact in #208's collaborative framing: a **review surface** where a bad merge/split or unreadable seed is caught before position 04 is declared shipped in operator docs. Without one recorded human read on a real gated `01/02/03` triple, position 04 would ship on stubbed evidence alone.

## Input

Land steps **6** and **7** before executing. Open the landed modules at execution time — **landed names win** over any name in earlier details or plan prose.

**From step 6 (`plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-plans.md`, `plan_tool/cli/roadmap_cmd.py`):**

- **`STAGES[3]`** (or the row with `number==4`) — the plans row: `artifact_key="plans"`, `plans_path`, `parse_plans_artifact`, `render_plans_artifact`, `run_plans_gates` held by identity; **`side_output_seed_paths`** (or landed name) not `None`.
- **`--from-stage 4`** — reads `01-domain.md`, `02-constraints.md`, and `03-components.md` off disk into the prompt and gate envelope; invokes only stage 4 when upstream pre-flight passes.
- **Completion output** — `RoadmapResult` plus `plan_tool/cli/roadmap_cmd.py:_print_completed`, `_feedback_summary_lines`, ordered `plan-tool create <plan-id> --from-existing <draft-path>` detail lines, and pending-decision copy. Read stdout and stderr together when capturing the operator view (the plan's Testing section names this explicitly).

**From step 7 (`plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`):**

- **`apply_roadmap_seeds`** (or landed name) — apply-only orchestrator; never calls `run_roadmap` or the invoker.
- **`plan-tool roadmap <slug> --apply`** — recommend-only preview; **`--apply -y`** copies one or more drafts to `plan-seeds/<plan-id>.md` with refuse-by-default collisions.
- **`--apply`** and **`--from-stage`** are mutually exclusive — the stage-4 measurement run uses `--from-stage 4` only; apply is a separate command afterward.

**From steps 1–3 (artifact and gate symbols this step verifies on the real output):**

- **`run_plans_gates`** over a four-slot `ArtifactEnvelope` with **`draft_seed_bundle`** populated — shared shape/revision tuple plus six plan-relation checks (confirm `check_*` names at HEAD in `plan_tool/roadmap_gates.py`).
- **`load_plans_artifact`**, **`load_components_artifact`**, and per-seed **`parse_draft_seed_provenance`** — re-parse written bytes after the run.
- **`PLAN_ID_SLUG_RE`** / `plan_tool/create.py:SLUG_RE` — plan row ids must satisfy create's slug shape (gate observable, not merit).
- **`resolve_draft_seed_path`**, **`DRAFT_SEED_ROADMAP_COMPONENTS_KEY`**, **`DRAFT_SEED_CROSS_CUTTING_KEY`** — draft provenance the human record quotes when judging traceability.

**Briefs the plan names (both are valid; pick one at execution time):**

- **`toollib`** — #208's second brief; the 2026-08-05 stage-3 block already recorded gate-clean `01/02/03` under `.tmp/roadmap-measure.plans/roadmaps/toollib/` (local). Strong choice when reusing that upstream triple.
- **`cfp-review`** — the walkthrough brief (`docs/ROADMAP_WALKTHROUGH.md` § 1); #208's first real run and feedback-loop exercise use it. Strong choice when local `01/02/03` artifacts exist from those runs.

Concept briefs, roadmap artifacts, and run logs under `.tmp/` or a scratch `--plans-dir` are gitignored. The backlog block must quote enough of the brief, the plans inventory, and at least one draft-seed excerpt that a reader without those files can still follow the reviewer's judgment.

**What one reading cannot prove.** This is n=1 — one brief, one reviewer, one first-pass mapping (plus at most one optional stage-4 revision or one optional `--apply`). It cannot establish hit rate, typical retry counts, whether dispositions are usually right-sized, or whether seeds converge under `create`. Say so in the record's reading rule.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — two additions, both dated:
    - a new bullet under **#208** for the first real stage-4 run: commands, brief choice, gate-observable traceability summary, the reviewer's mapping and seed verdict, optional feedback/revision and optional single-draft `--apply` outcomes, and operational numbers.
    - a **stage-4** sample appended near **#215**'s existing measurement tables (that entry is closed; the sample is historical evidence, not a reopening). Record attempts, `prompt_bytes`, advisory level, wall, and cost for stage 4 only.

Do **not** edit #208's `Status:` field, its arc-position table, or `docs/ROADMAP_WALKTHROUGH.md` § 7 — step 10 owns those reconciliations.

Everything besides the `BACKLOG.md` edit stays scratch and uncommitted: the plans directory, all four artifacts, draft seeds, run logs, and any helper script. Prefix scratch paths (`.tmp/roadmap-04-plan-derivation.*`) per the repo's `.tmp/` naming rule.

## Implementation

### 1. Write the reading rule before running anything

Put the outcome vocabulary and the "this gates nothing" sentence into the `BACKLOG.md` block **before** any evidence, and keep them above the results in document order.

**Mapping review (required)** — four values, fixed before opening `04-roadmap.md`:

- **reviewable** — dispositions and ordering are arguable, every component id has a plan home (or an explicit `cross-cutting` row), a reviewer can name what to push on without re-deriving the whole model.
- **reviewable with reservations** — gate-clean and readable, but at least one merge/split, assumption row, or ordering choice would get feedback before trusting the set for `create`.
- **not reviewable** — plans inventory, sizing rationale, or draft seeds too thin to judge (record why).
- **would redirect** — the reviewer would not accept the mapping without a `--from-stage 4` feedback pass (record the redirect topic even if you do not run it).

**Seed review (required, separate from mapping headline)** — one short verdict on the draft set as a whole:

- **seeds reviewable** — each draft's provenance block, scope-contract fence, and component citations are present enough to argue about; inter-plan assumptions appear only on consuming plans.
- **seeds not reviewable** — drafts missing load-bearing fences, inventing a second vocabulary, or copying frozen rejected-alternative rationale wholesale (walkthrough § 5 caveat).

Add one sentence: **this record gates nothing** — no score, threshold, or pass/fail on mapping merit, disposition sizing, or seed prose quality.

**Feedback responses (optional)** — if the exercise includes a stage-4 revision, reuse #208's four-value feedback vocabulary (**accepted**, **partially accepted**, **declined**, **required clarification**) and document actions per feedback id, same shape as the 2026-08-04 feedback-loop block.

**Apply exercise (optional)** — if run, state explicitly that **only one** plan row was promoted (not a batch apply of every seed). Record preview vs applied outcome and whether promoted bytes dropped the draft provenance YAML block.

### 2. Build upstream artifacts: gated `01/02/03` on disk

Two paths; either satisfies the plan's "existing gated 01/02/03" requirement:

- **Reuse local upstream.** If `01-domain.md`, `02-constraints.md`, and `03-components.md` for the chosen slug already parse and clear their stage gate sets at HEAD, point `--from-stage 4` at that directory. Name the path in the record; mark it gitignored/local if it is not committed. The toollib triple from the 2026-08-05 stage-3 block is the natural reuse candidate.
- **Fresh baseline in a scratch plans directory.** Isolate with the global flag before the subcommand: `plan-tool --plans-dir .tmp/roadmap-04-plan-derivation.plans roadmap <slug> --from-existing <brief>`. Run stages 1–3 once (a full three-stage run is simpler than stopping mid-arc). Confirm upstream gate-clean before stage 4.

Do not commit anything under `docs/implementation-plans/roadmaps/` from this step unless the repo already treats a specific slug as a committed fixture (today it does not).

### 3. Run stage 4 and capture the run

```bash
plan-tool --plans-dir <dir> roadmap <slug> --from-existing <brief> --from-stage 4
```

When upstream already exists, `--from-stage 4` is the cheap path — it spends tokens only on the plans stage and proves disk-as-interface for three upstream artifacts.

Capture per attempt from `.plan-tool/runs/<slug>/<run_id>.jsonl` (gitignored; `plan-tool runs list --slug <slug>` finds the id):

- **`prompt_bytes`** from each `claude_call_start` and **`cost_usd`** from each `claude_call_end` — stage 4 prompts are the largest yet (brief + three full upstream artifacts inline + multi-fence output contract).
- **`gate_violations` events** — which plan-relation rule consumed a retry, if any (`plan_tool/run_log.py:RunLogWriter.gate_violations`).
- **Prompt-budget advisory level** from the shell path (`plan_tool/shell.py:claude_invoke` → `plan_tool/prompt_budget.py` `LEVEL_OK` / `LEVEL_WARN` / `LEVEL_HIGH`). Record `ok` explicitly when nothing fired.
- **Exit outcome** — `completed` vs `stage-exhausted`; on exhaustion, the final violation list and `MAX_STAGE_ATTEMPTS` (`plan_tool/roadmap.py`, expected value `3`).

Also capture CLI stdout/stderr together: pending-decision count, feedback-awaiting count, ordered create handoff lines, overwrite pointer copy from `plan_tool/cli/roadmap_cmd.py`.

Confirm the default run did **not** write under repo-root `plan-seeds/` — drafts should live only under the slug directory until `--apply`.

### 4. Verify gate observables on the written outputs (machine checks for the record)

Before the human mapping read, confirm the binary facts the plan's Testing section names — these belong in the record as facts, not opinions:

- Re-parse `04-roadmap.md` through `load_plans_artifact`.
- Build a four-artifact `ArtifactEnvelope` with the in-memory **`draft_seed_bundle`** reconstructed from on-disk draft files (keyed by `Path(draft_seed_path).name`); run `run_plans_gates`; expect `[]` on success.
- **Component coverage** — every `ComponentRow.id` from `03-components.md` appears on ≥1 `PlanRow` (merge/split/`keep` all count); `cross-cutting` rows may omit component ids but do not excuse uncovered components.
- **Plan ↔ seed bijection** — every plan row's `draft_seed_path` basename matches a file under the slug tree; no orphan bundle entries.
- **Provenance** — each draft's frontmatter parses through `parse_draft_seed_provenance`; declared `roadmap_components` ids resolve to the components inventory.
- **Ordering** — `artifact.ordering` lists every plan id exactly once; dependency targets resolve.
- **Slug shape** — every plan id matches `create`'s slug rule (re-check via `plan_tool/create.py:SLUG_RE` or the landed mirror constant).
- **Assumption scoping** — for at least one draft inspected by hand, inter-plan assumptions copied into the seed fence match only rows whose consuming plan ids include that plan.

Name plan count, disposition mix (`keep` / `merge` / `split` / `cross-cutting`), assumption row count, and draft-seed file count. These numbers anchor the human read.

### 5. Review as a human — mapping and seeds, not gate conformance

Read `04-roadmap.md` and the draft directory the way `docs/ROADMAP_WALKTHROUGH.md` § 5 describes the manual hop — coherent behavior bundles sized into plans, component ids as provenance, inter-plan assumptions carried into seed fences — but judge whether **stage 4's automation** produced a reviewable set, not whether you would have sliced identically by hand.

Record at minimum:

- **One sentence per plan row** — what behavior bundle it claims, which component id(s) it owns, and its disposition in plain language.
- **Mapping judgment** — whether merge/split/`cross-cutting` choices match how a reviewer would size seeds from `03-components.md` (the plan's Out of scope refuses encoding this as a gate).
- **Ordering judgment** — whether the declared sequence and dependency targets look runnable as printed create lines.
- **Seed spot-check** — open at least two drafts (one `keep`, one non-`keep` if present): provenance block, scope-contract fence, settled-decision fences, and whether rejected-alternative *reasons* were over-copied vs left for `create` to re-ground (walkthrough § 5 caveat).
- **Pending decisions** — any `pending` decision rows the reviewer would settle before trusting the mapping.
- **One predeclared mapping outcome** from the four-value vocabulary in § 1, plus the seed verdict from § 1.

If the outcome is **would redirect** or **reviewable with reservations**, the strongest follow-up is one hand-written `feedback` row in `04-roadmap.md` and a second `--from-stage 4` run — same revision contract position 02 shipped (`plan_tool/prompts/roadmap-revision.md`, continuity and feedback gates on plan ids). Run it if budget allows; if not, say it was skipped and why.

### 6. Optional: exercise `--apply` on one draft only

After a green stage-4 run, optionally prove step 7's apply-only path on **a single** plan row whose `plan-seeds/<plan-id>.md` target does not exist yet:

```bash
plan-tool --plans-dir <dir> roadmap <slug> --apply        # recommend-only preview first
plan-tool --plans-dir <dir> roadmap <slug> --apply -y   # only if preview looks right AND only one destination will be written
```

**Do not batch-apply every seed** — the plan's Testing section treats one promotion as enough to prove the gate. If multiple destinations would be written, pick one plan id, temporarily note the others as skipped, or run preview-only and record that `-y` was not used. Record whether promoted bytes dropped the draft provenance YAML block and whether stdout printed `plan-tool create <plan-id> --from-existing plan-seeds/...` for the promoted path. Slug-directory drafts must remain on disk unchanged.

If `plan-seeds/<plan-id>.md` already exists, record a refused preview instead of forcing a collision — refuse-by-default is the expected policy.

### 7. Land the block in `BACKLOG.md`

Model on #208's existing real-run bullets (especially the 2026-08-05 stage-3 block):

- Lead with **How to read this block** — mapping vocabulary, seed verdict line, optional feedback vocabulary, optional apply note, and the no-gating sentence.
- Name the brief, slug, `--plans-dir`, and verbatim commands (including `--from-stage` value and any separate `--apply` invocations).
- Gate-observable summary table (components, plans, dispositions, drafts on disk, `run_plans_gates` clearing, bundle bijection, provenance parse).
- Human mapping outcome, seed verdict, and short prose rationale — not a score.
- Operational numbers for stage 4; append the **#215** stage-4 sample in the same table shape as prior rows, labelled **stage 4** / **plans** so it is not mistaken for a components sample.
- State plainly that `.tmp/` paths, draft seeds, and run logs are local/gitignored when used — **this bullet is the durable record**.

**The step completes whichever way the exercise goes.** A `stage-exhausted` outcome, a **not reviewable** verdict, a refused `--apply`, or a mapping the reviewer would redirect are all valid results to write down. The only failure mode is not recording what happened. Surprises that need code work go to `BACKLOG.md` or `BUG_BACKLOG.md` per that file's decision rule — never a loop change inside this step.

**Rejected alternative:** a committed `docs/` measurement file. It reads better standalone but is outside this step's declared `files:` list, and one reviewer's read fits a backlog bullet the way #208 already carries real-run evidence.

## Tests

This step is `change_type: non-code` and changes no production code. The plan's `enforce_step_tests: true` gate keys on `change_type` and fires only for `feature` / `refactor` steps, so it does not apply here.

### Verification (non-code step)

Roughly fifteen checks against the finished `BACKLOG.md` and working tree:

1. **reading-rule-precedes-evidence** — the four-value mapping vocabulary, seed verdict line, and the "this gates nothing" sentence appear above the first result in document order.
2. **commands-recorded-verbatim** — every invocation appears as a literal command line, including global `--plans-dir` placement, `--from-stage 4`, and any separate `--apply` lines.
3. **brief-and-slug-named** — the record states which of `cfp-review` / `toollib` ran and why that choice was available.
4. **upstream-triple-named** — the record states how gated `01/02/03` were obtained (reused path or fresh three-stage run).
5. **gate-observables-present** — component coverage, plan↔seed bijection, provenance parse, ordering totality, and `run_plans_gates` clearing are stated as checked facts with counts.
6. **mapping-outcome-present** — exactly one of the four predeclared mapping outcomes appears; no fifth label for the headline verdict.
7. **seed-verdict-present** — **seeds reviewable** or **seeds not reviewable** appears with at least one sentence of rationale.
8. **human-rationale-present** — at least one sentence per plan row (or explicit "N plans listed with one-line summaries") plus mapping and ordering judgment in plain language.
9. **numbers-present** — stage-4 attempts, `prompt_bytes` per attempt, advisory level (including `ok`), wall, and cost, each attributed to stage 4.
10. **215-sample-added-labelled** — #215 carries a new row or sub-table labelled **stage 4** / **plans**; `git diff plan_tool/` is empty.
11. **208-status-untouched** — this step's diff leaves #208's `Status:` field and arc-position prose unchanged; step 10 owns reconciliation.
12. **walkthrough-section-7-untouched** — `docs/ROADMAP_WALKTHROUGH.md` is absent from the diff.
13. **footprint-is-one-file** — the commit touches only `BACKLOG.md`.
14. **paths-resolve-or-marked-local** — every path named either exists at HEAD or is explicitly marked gitignored/local.
15. **apply-subblock-consistent** — if apply was run, the block states one plan id promoted (or preview-only / refused) and whether provenance was stripped; if apply was not run, the block says so explicitly.
16. **feedback-subblock-consistent** — if a stage-4 revision was run, every feedback id has one of the four feedback outcomes and a document action; if no revision was run, the block says so explicitly.
17. **plan-seeds-default-untouched** — the record states that the stage-4 run itself did not write repo-root `plan-seeds/` (unless optional single apply is documented separately).

## Acceptance criteria

- `BACKLOG.md` carries a dated **first real stage-4 run** bullet under **#208** containing: brief choice, verbatim commands, gate-observable traceability facts (component coverage, plan↔seed alignment, empty `run_plans_gates`), one predeclared mapping outcome, a seed verdict, and human prose on mapping, ordering, and at least two spot-checked drafts.
- The block's reading rule — mapping vocabulary, seed verdict, and "this gates nothing" — appears before any evidence in document order.
- The block reports stage-4 attempts, `prompt_bytes` per attempt, prompt-budget advisory level (including `ok`), wall, and cost; **#215** carries a matching sample labelled for stage 4/plans.
- If a stage-4 feedback revision was run, the block quotes each request, each `proposed_response`, per-id feedback outcome, and document action; if not run, the block states that explicitly.
- If optional `--apply` was run, the block documents preview and/or single-plan promotion, promoted create handoff line, and provenance stripping; if not run, the block states that explicitly. No batch apply of every seed is recorded as the measurement.
- `plan_tool/` is unchanged by this step's diff; `MAX_STAGE_ATTEMPTS` still reads `3`.
- #208's `Status:` field and `docs/ROADMAP_WALKTHROUGH.md` § 7 are unchanged by this step's diff.
- This step's commit touches only `BACKLOG.md`.
- Anything surprising that needs follow-up work exists as a `BACKLOG.md` or `BUG_BACKLOG.md` entry, not as a production change in this step.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — read when confirming written `04-roadmap.md` and draft-seed frontmatter parse through the landed loaders.
- [pathlib — Object-oriented filesystem paths (Python 3.13)](https://docs.python.org/3.13/library/pathlib.html) — resolving slug-relative `draft_seed_path` values and basename-keyed bundle alignment during manual verification.
- [shutil — High-level file operations (Python 3.13)](https://docs.python.org/3.13/library/shutil.html) — relevant when describing step 7's copy semantics in the optional apply sub-block.
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — invocation and exit-status contract when reading a non-zero or exhausted run correctly.

## Applicable guardrails

- **The plan's step intent** — prove reviewability on a real gated `01/02/03` triple; do not widen into operator doc sweeps, #208 status reconciliation, or lens work step 10 owns.
- **The plan's "## Out of scope", merit and quality gates** — record human mapping and seed judgment only; do not propose encoding right-sized dispositions, seed Outcome quality, or plan-count caps as gates.
- **The plan's "## Out of scope", auto-running create/detail/run** — hand-off stays printed lines and optional single-draft `--apply`; do not run `create` on emitted seeds as part of this measurement.
- **The plan's "## Out of scope", interactive review walks** — bounded gate retry plus optional human feedback re-entry only; no seed-content review walk.
- **The plan's "## Risks", `--apply` and dirty trees** — optional apply documents refuse-by-default collisions; do not force overwrites to complete the exercise.
- **The plan's "## Risks", prose-mention / retry budget** — measure stage-4 retry pressure and append the #215 sample; do not change `MAX_STAGE_ATTEMPTS` in this step.

## Deferred

- **Reconciling #208's arc-position status and sweeping operator docs** — step 10 (`CLAUDE.md`, `CAPABILITIES.md`, `RUNBOOK.md`, `USE_CASES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md` § 7, `integrations/claude/SKILL.md`).
- **Deciding whether `MAX_STAGE_ATTEMPTS` should rise for plans-sized prompts** — #215 is closed; this step only adds evidence.
- **A second brief, a second reviewer, or repeated sampling** — one reading by design; further samples are later backlog observations.
- **Running `create` on emitted seeds to measure convergence** — explicitly out of scope for this plan; file separately if warranted.
- **Automated mapping- or seed-quality scoring** — explicitly refused by the plan's Out of scope and verification limits.
- **Committing briefs, artifacts, draft seeds, or run logs** — gitignored by design; the backlog block is the durable carrier.
- **A committed `docs/` measurement file** — outside this step's `files:` list; see rejected alternative in Implementation.
- **Batch `--apply` of every draft** — the plan's Testing section caps the apply proof at one promotion; full promotion is an operator choice, not this step's measurement.
