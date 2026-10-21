> **Auto-archived**: this plan was swept on 2026-08-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Run stage 3 on an existing brief and record human-review outcomes

## Summary

Drive the shipped three-stage `roadmap` verb once against a real concept brief whose `01-domain.md` and `02-constraints.md` already gate clean, run only stage 3 when upstream artifacts are on disk (`--from-stage 3`), and have a human read the resulting `03-components.md` for partition quality — not just gate conformance. Write what happened into `BACKLOG.md` as a dated measurement block under **#208**, with a stage-3 retry sample beside the existing **#215** tables. The main design decision matches position 02's exercise step: **the durable record lives in `BACKLOG.md`, not a new `docs/` file** — briefs, artifacts, and run logs stay gitignored, and #208 already carries real-run evidence this way. On green, a reader who never ran stage 3 can see the commands, the gate-observable traceability facts, the reviewer's partition verdict, optional feedback outcomes, and the operational numbers — and nothing in the record gates anything.

## Table of Contents

- [Summary](#summary) — the real run, the human read, and where the record lands.
- [Why](#why) — gates prove structure; only a person can say the decomposition is reviewable.
- [Input](#input) — what step 5 hands this step, which briefs qualify, and what one reading cannot prove.
- [Files (creates vs edits)](#files-creates-vs-edits) — one edit; everything else stays scratch.
- [Implementation](#implementation) — the reading rule, the fixture, the run, the review, and the backlog block.
- [Tests](#tests) — substitute verification for a non-code step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can run.
- [References](#references) — docs worth skimming for the run and the record shape.
- [Applicable guardrails](#applicable-guardrails) — plan fences that bind this step.
- [Deferred](#deferred) — what step 7 owns and what is deliberately not measured.

## Why

Steps 1–5 make stage 3 runnable: a third `STAGES` row, five traceability gates in `run_components_gates`, and a components prompt that feeds both upstream artifacts. Every test in those steps is hermetic — canned responses through the real parser and gates — which proves the contract is satisfiable and says nothing about whether a real model produces a partition a human can actually review, or whether that partition is worth carrying into position 04's seed derivation. That gap is the whole point of the components artifact in #208's collaborative framing: a **review surface** where a bad decomposition is caught before seeds are emitted. Without one recorded human read on a real `01/02` pair, position 03 would ship on stubbed evidence alone.

## Input

This step consumes what step 5 lands, plus facts about briefs and prior runs already named in **#208**. Open the landed modules at execution time — **landed names win** over any name in earlier details or plan prose.

**From step 5 (`plan_tool/roadmap.py`, `plan_tool/prompts/roadmap-components.md`):**

- **`STAGES[2]`** — the components row: `artifact_key="components"`, `components_path`, `parse_components_artifact`, `render_components_artifact`, `run_components_gates` held by identity (no adapter).
- **`--from-stage 3`** — reads `01-domain.md` and `02-constraints.md` off disk into the prompt and gate envelope; invokes only stage 3 when upstream pre-flight passes (`plan_tool/roadmap.py` pre-flight and `plan_tool/cli/roadmap_cmd.py` pointer copy).
- **Completion output** — `RoadmapResult` plus `plan_tool/cli/roadmap_cmd.py:_print_completed`, `_feedback_summary_lines`, and pending-decision copy on stdout/stderr. Read both streams together when capturing the operator view (the plan's Testing section names this explicitly).

**From steps 1–3 (artifact and gate symbols this step verifies on the real output):**

- **`run_components_gates`** over a three-slot `ArtifactEnvelope` — the five traceability checks the human record must confirm on the written artifact: entity coverage, pattern presence, valid constraint citations, prioritized-constraint discharge only (not `traded-away` / `not-load-bearing`).
- **`load_components_artifact`** — re-parse the on-disk file after the run; gate violations are retry text, not a separate report.

**Briefs the plan names (both are valid; pick one at execution time):**

- **`cfp-review`** — the walkthrough brief (`docs/ROADMAP_WALKTHROUGH.md` § 1); #208's first real run and feedback-loop exercise already use it. Strong choice when local `01/02` artifacts exist from those runs.
- **`toollib`** — #208's second brief (2026-08-05): different domain shape, both stages 1–2 passed first try on both recorded runs. Strong choice when starting fresh and wanting a non-CFP partition read.

Concept briefs and roadmap artifacts under `.tmp/` or a scratch `--plans-dir` are gitignored. The backlog block must quote enough of the brief and the components inventory that a reader without those files can still follow the reviewer's judgment.

**What one reading cannot prove.** This is n=1 — one brief, one reviewer, one first-pass partition (plus at most one optional revision). It cannot establish hit rate, typical retry counts, or whether seams generalize. Say so in the record's reading rule.

## Files (creates vs edits)

- **New files:** none.
- **Existing files (edits only):**
  - `BACKLOG.md` — two additions, both dated:
    - a new bullet under **#208** for the first real stage-3 run: commands, brief choice, gate-observable traceability summary, the reviewer's partition verdict, optional feedback/revision outcomes, and operational numbers.
    - a **stage-3** sample appended near **#215**'s existing measurement tables (that entry is closed; the sample is historical evidence, not a reopening). Record attempts, `prompt_bytes`, advisory level, wall, and cost for stage 3 only.

Do **not** edit #208's `Status:` field, its arc-position table, or `docs/ROADMAP_WALKTHROUGH.md` § 7 — step 7 owns those reconciliations.

Everything besides the `BACKLOG.md` edit stays scratch and uncommitted: the plans directory, the three artifacts, run logs, and any helper script. Prefix scratch paths (`.tmp/roadmap-03-components.*`) per the repo's `.tmp/` naming rule.

## Implementation

### 1. Write the reading rule before running anything

Put the outcome vocabulary and the "this gates nothing" sentence into the `BACKLOG.md` block **before** any evidence, and keep them above the results in document order.

**Partition review (required)** — four values, fixed before opening `03-components.md`:

- **reviewable** — seams are arguable, ids trace to domain/constraints, a reviewer can name what to push on without re-deriving the whole model.
- **reviewable with reservations** — gate-clean and readable, but at least one seam or discharge claim would get feedback before seed derivation.
- **not reviewable** — prose, patterns, or component boundaries too thin to judge (record why).
- **would redirect** — the reviewer would not accept the partition without a `--from-stage 3` feedback pass (record the redirect topic even if you do not run it).

Add one sentence: **this record gates nothing** — no score, threshold, or pass/fail on partition quality.

**Feedback responses (optional)** — if the exercise includes a stage-3 revision, reuse #208's four-value feedback vocabulary (**accepted**, **partially accepted**, **declined**, **required clarification**) and document actions per feedback id, same shape as the 2026-08-04 feedback-loop block.

### 2. Build upstream artifacts: gated `01/02` on disk

Two paths; either satisfies the plan's "existing gated 01/02" requirement:

- **Reuse local upstream.** If `01-domain.md` and `02-constraints.md` for the chosen slug already parse and clear their stage gate sets at HEAD, point `--from-stage 3` at that directory. Name the path in the record; mark it gitignored/local if it is not committed.
- **Fresh baseline in a scratch plans directory.** Isolate with the global flag before the subcommand: `plan-tool --plans-dir .tmp/roadmap-03-components.plans roadmap <slug> --from-existing <brief>`. Run stages 1–2 once (or stop after stage 2 with `--from-stage 1` through 2 — a full two-stage run is simpler). Confirm upstream gate-clean before stage 3.

Do not commit anything under `docs/implementation-plans/roadmaps/` from this step unless the repo already treats a specific slug as committed fixture (today it does not).

### 3. Run stage 3 and capture the run

```bash
plan-tool --plans-dir <dir> roadmap <slug> --from-existing <brief> --from-stage 3
```

When upstream already exists, `--from-stage 3` is the cheap path — it spends tokens only on the components stage and proves disk-as-interface for two upstream artifacts.

Capture per attempt from `.plan-tool/runs/<slug>/<run_id>.jsonl` (gitignored; `plan-tool runs list --slug <slug>` finds the id):

- **`prompt_bytes`** from each `claude_call_start` and **`cost_usd`** from each `claude_call_end` — stage 3 prompts are the largest yet (brief + full domain + full constraints inline).
- **`gate_violations` events** — which traceability rule consumed a retry, if any (`plan_tool/run_log.py:gate_violations`).
- **Prompt-budget advisory level** from the shell path (`plan_tool/shell.py:claude_invoke` → `plan_tool/prompt_budget.py` `LEVEL_OK` / `LEVEL_WARN` / `LEVEL_HIGH`). Record `ok` explicitly when nothing fired.
- **Exit outcome** — `completed` vs `stage-exhausted`; on exhaustion, the final violation list and `MAX_STAGE_ATTEMPTS` (`plan_tool/roadmap.py`, expected value `3`).

Also capture CLI stdout/stderr together: pending-decision count, feedback-awaiting count, overwrite pointer lines from `plan_tool/cli/roadmap_cmd.py`.

### 4. Verify gate observables on the written artifact (machine checks for the record)

Before the human partition read, confirm the traceability facts the plan's Testing section names — these are binary and belong in the record as facts, not opinions:

- Re-parse `03-components.md` through `load_components_artifact`.
- Run `run_components_gates` with domain and constraints loaded from the same directory; expect `[]` on success.
- **Entity coverage** — every `EntityRow.id` from `01-domain.md` appears in at least one `ComponentRow.entity_ids`.
- **Prioritized discharge** — every constraint whose attribute disposition is `prioritized` appears in at least one component's `constraint_ids`; constraints under `traded-away` or `not-load-bearing` attributes need not appear.

Name component count, pattern-row counts (`system_patterns`, `component_patterns`), and how many `prioritized` constraints were discharged. These numbers anchor the human read.

### 5. Review as a human — partition, not gate conformance

Read `03-components.md` the way `docs/ROADMAP_WALKTHROUGH.md` § 5 describes seed slicing — coherent behavior bundles, arguable seams, constraints cited by id — but **stop before writing seeds** (position 04 is out of scope).

Record at minimum:

- **One sentence per component** — what behavior bundle it claims to own, in plain language.
- **Seam judgment** — whether those bundles match how a reviewer would slice the brief (the plan's Out of scope refuses encoding this as a gate).
- **Pattern usefulness** — whether pattern rows name something a reviewer could redirect, or read as gate-filler.
- **Pending decisions** — any `pending` decision rows the reviewer would settle before trusting the partition.
- **One predeclared partition outcome** from the four-value vocabulary in § 1.

If the outcome is **would redirect** or **reviewable with reservations**, the strongest follow-up is one hand-written `feedback` row in `03-components.md` and a second `--from-stage 3` run — same revision contract position 02 shipped (`plan_tool/prompts/roadmap-revision.md`, continuity and feedback gates on component ids). Run it if budget allows; if not, say it was skipped and why. This is optional for step completion but is the only way to exercise the components feedback target in the same record.

### 6. Land the block in `BACKLOG.md`

Model on #208's existing real-run bullets:

- Lead with **How to read this block** — the partition vocabulary, optional feedback vocabulary, and the no-gating sentence.
- Name the brief, slug, `--plans-dir`, and verbatim commands (including `--from-stage` value).
- Gate-observable summary table (entities, components, patterns, prioritized constraints discharged).
- Human partition verdict and short prose rationale — not a score.
- Operational numbers for stage 3; append the **#215** stage-3 sample in the same table shape as prior authoring/revision rows, labelled so it is not mistaken for a stages 1–2 sample.
- State plainly that `.tmp/` paths and run logs are local/gitignored when used — **this bullet is the durable record**, same move as the 2026-08-04 feedback exercise.

**The step completes whichever way the exercise goes.** A `stage-exhausted` outcome, a **not reviewable** verdict, or a partition the reviewer would redirect are all valid results to write down. The only failure mode is not recording what happened. Surprises that need code work go to `BACKLOG.md` or `BUG_BACKLOG.md` per that file's decision rule — never a loop change inside this step.

**Rejected alternative:** a committed `docs/` measurement file. It reads better standalone but is outside this step's declared `files:` list, and one reviewer's partition read fits a backlog bullet the way #208 already carries real-run evidence.

## Tests

This step is `change_type: non-code` and changes no production code. The plan's `enforce_step_tests: true` gate keys on `change_type` and fires only for `feature` / `refactor` steps, so it does not apply here.

### Verification (non-code step)

Roughly a dozen checks against the finished `BACKLOG.md` and working tree:

1. **reading-rule-precedes-evidence** — the four-value partition vocabulary and the "this gates nothing" sentence appear above the first result in document order.
2. **commands-recorded-verbatim** — every invocation appears as a literal command line, including global `--plans-dir` placement and the `--from-stage` value.
3. **brief-and-slug-named** — the record states which of `cfp-review` / `toollib` ran and why that choice was available.
4. **gate-observables-present** — entity coverage, prioritized-constraint discharge, and `run_components_gates` clearing are stated as checked facts with counts.
5. **partition-outcome-present** — exactly one of the four predeclared partition outcomes appears; no fifth label for the headline verdict.
6. **human-rationale-present** — at least one sentence per component (or an explicit "N components listed with one-line summaries") plus a seam judgment in plain language.
7. **numbers-present** — stage-3 attempts, `prompt_bytes` per attempt, advisory level (including `ok`), wall, and cost, each attributed to stage 3.
8. **215-sample-added-labelled** — #215 carries a new row or sub-table labelled **stage 3** / **components**; `git diff plan_tool/roadmap.py` is empty.
9. **208-status-untouched** — this step's diff leaves #208's `Status:` field and arc-position prose unchanged; step 7 owns reconciliation.
10. **walkthrough-section-7-untouched** — `docs/ROADMAP_WALKTHROUGH.md` is absent from the diff.
11. **footprint-is-one-file** — the commit touches only `BACKLOG.md`.
12. **paths-resolve-or-marked-local** — every path named either exists at HEAD or is explicitly marked gitignored/local.
13. **feedback-subblock-consistent** — if a revision was run, every feedback id has one of the four feedback outcomes and a document action; if no revision was run, the block says so explicitly.

## Acceptance criteria

- `BACKLOG.md` carries a dated **first real stage-3 run** bullet under **#208** containing: brief choice, verbatim commands, gate-observable traceability facts (total entity coverage, prioritized constraints discharged, empty `run_components_gates`), one predeclared partition outcome, and human prose on seams/patterns.
- The block's reading rule — partition vocabulary plus "this gates nothing" — appears before any evidence in document order.
- The block reports stage-3 attempts, `prompt_bytes` per attempt, prompt-budget advisory level (including `ok`), wall, and cost; **#215** carries a matching sample labelled for stage 3/components.
- If a stage-3 feedback revision was run, the block quotes each request, each `proposed_response`, per-id feedback outcome, and document action; if not run, the block states that explicitly.
- `plan_tool/roadmap.py` is unchanged; `MAX_STAGE_ATTEMPTS` still reads `3`.
- #208's `Status:` field and `docs/ROADMAP_WALKTHROUGH.md` § 7 are unchanged by this step's diff.
- This step's commit touches only `BACKLOG.md`.
- Anything surprising that needs follow-up work exists as a `BACKLOG.md` or `BUG_BACKLOG.md` entry, not as a production change in this step.

## References

- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — read when confirming the written `03-components.md` frontmatter parses through `load_components_artifact`.
- [string — Template strings](https://docs.python.org/3/library/string.html#template-strings) — relevant to understanding why stage-3 prompts are large (brief plus both upstream artifacts substituted inline).
- [Claude Code CLI reference](https://docs.claude.com/en/docs/claude-code/cli-reference) — invocation and exit-status contract when reading a non-zero or exhausted run correctly.

## Applicable guardrails

- **The plan's step intent** — prove reviewability on a real `01/02` pair; do not widen into seed emission, lens work, or doc sweeps step 7 owns.
- **The plan's "## Out of scope", partition quality gates** — record human seam judgment only; do not propose encoding "right-sized" components or pattern merit as a gate.
- **The plan's "## Out of scope", position 04** — stop at the gated components artifact; no `create` seeds, no component→plan mapping.
- **The plan's "## Out of scope", new convergence loop** — bounded gate retry plus optional human feedback re-entry only; no completeness-style loop inside `roadmap`.
- **The plan's "## Risks", retry-budget / #215** — measure stage-3 retry pressure and append the sample; do not change `MAX_STAGE_ATTEMPTS`.
- **The plan's deferred, stage-as-data widening** — if the real run exposes an orchestrator branch need, record it as a finding for step 7 or a backlog entry; do not patch `plan_tool/roadmap.py` in this step.

## Deferred

- **Reconciling #208's arc-position status and sweeping operator docs** — step 7 (`CLAUDE.md`, `CAPABILITIES.md`, `RUNBOOK.md`, `USE_CASES.md`, `docs/ARCHITECTURE.md`, `docs/ROADMAP_WALKTHROUGH.md` § 7).
- **Deciding whether `MAX_STAGE_ATTEMPTS` should rise for components-sized prompts** — #215 is closed; this step only adds evidence.
- **A second brief, a second reviewer, or repeated sampling** — one reading by design; further samples are later backlog observations.
- **Automated partition-quality scoring** — explicitly refused by the plan's Out of scope and verification limits.
- **Committing briefs, artifacts, or run logs** — gitignored by design; the backlog block is the durable carrier.
- **A committed `docs/` measurement file** — outside this step's `files:` list; see rejected alternative in Implementation.
