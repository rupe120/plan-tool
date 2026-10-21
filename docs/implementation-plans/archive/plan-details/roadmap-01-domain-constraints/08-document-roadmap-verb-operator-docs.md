> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 8 — Document the roadmap verb in the operator docs and reconcile BACKLOG #208

## Summary

This step is pure documentation: it adds `plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]` to the four docs an operator or an agent actually reads to decide which verb to reach for — `USE_CASES.md`, `RUNBOOK.md`, `integrations/claude/SKILL.md`, `CLAUDE.md` — and reconciles BACKLOG #208's Status line to say **arc position 01** shipped. No code changes anywhere. The one design decision is scope: describe exactly what **artifact stages 1–2** ship (`01-domain.md` / `02-constraints.md`, gate-retried, non-interactive, `--from-stage` re-entry) and nothing BACKLOG #208's later arc positions add — no seed emission, no `--framework`, no sign-off walk. On green, the verb is discoverable from every doc surface this repo uses to route an operator or a driving Claude session to the right command, and BACKLOG #208 no longer describes execution as pending.

## Table of Contents

- [Summary](#summary) — what the step ships and the one design decision behind it.
- [Why](#why) — why steps 1–7 alone leave the verb undiscoverable.
- [Input](#input) — the landed CLI contract and BACKLOG entry this step describes and reconciles.
- [Files (creates vs edits)](#files-creates-vs-edits) — the five edited docs; no new files.
- [Implementation](#implementation) — what changes in each of the five files, and the rules that are not free to vary.
- [Tests](#tests) — non-code verification for this step.
- [Acceptance criteria](#acceptance-criteria) — checkable facts a reviewer can confirm.
- [Applicable guardrails](#applicable-guardrails) — the plan-level Out-of-scope fences that bound what this step's prose may claim.
- [Deferred](#deferred) — what other steps or follow-ups own, and why this step doesn't reach for them.

## Why

Steps 1–7 make `plan-tool roadmap` a real, gate-correct, discoverable-via-`--help` CLI verb, but "discoverable via `--help`" is not the same as "discoverable by an operator deciding what to run." `USE_CASES.md` answers *is this a good fit and which command do I reach for*; `RUNBOOK.md` answers *how do I actually run it*; `integrations/claude/SKILL.md` is the file the user's own global `CLAUDE.md` names as the canonical subcommand catalog a driving Claude session reads before invoking this tool. None of the three mentions `roadmap` until this step edits them, so an operator with a project-sized concept — the exact situation the verb exists for — has no route to it from any of the docs designed to route them. `CLAUDE.md`'s Architecture section documents every other verb group (worktrees, branch-awareness, concept sign-off, the granularity advisor) with its own paragraph; `roadmap` is the one shipped surface missing one.

BACKLOG #208's Status line also goes stale the moment steps 1–7 land: it currently reads "stage 01 **plan-authored** … Execution is pending, and 5 steps had suggested gates auto-dropped by `-y` — vet them with `plan-tool suggest-gates` before running." Once this plan's steps are `done`, that sentence is exactly the kind of present-tense claim `CLAUDE.md`'s "Documentation is forward-looking" rule calls a defect — it describes a state the repo no longer has.

## Input

This step consumes the landed CLI contract from steps 1, 2, 4, and 7, and the BACKLOG #208 anchor entry's existing prose. **The landed names and shipped `--help` output win over anything this file or the plan suggests** — re-read `plan_tool/cli/roadmap_cmd.py` and run `plan-tool roadmap --help` before writing, per the accumulated lesson that a documentation step must read identifiers off the landed modules, not transcribe an earlier detail file's proposal.

- **The CLI surface, per step 7's detail** — `plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]`: `slug` is a required positional, `--from-existing` is required (`type=Path`), `--from-stage` is optional (`type=int`, default `1`, deliberately no `choices=`). There is no `-y`/`--yes`, no `--iterate`, and no confirm flag — the orchestrator has no interactive surface to gate.
- **The outcome vocabulary, per steps 4 and 7** — a completed run exits `0` (even with `pending` decisions on the written artifacts); a stage that exhausts its retry budget halts the arc before the next stage and exits non-zero, naming the failed stage and its violations. This is the verb's only failure mode worth describing to an operator — it never fails on advisory content.
- **The artifact contract, per step 1** — two files per slug, `docs/implementation-plans/roadmaps/<slug>/01-domain.md` and `02-constraints.md`; `01-domain.md` holds entities, business rules, and workflows (workflow rows reference entity ids), `02-constraints.md` holds quality attributes each carrying exactly one disposition (including a *not load-bearing here* value — a valid answer, not an omission).
- **The gate behavior, per step 2** — a failing gate retries the same stage with the violations quoted back into the regenerated prompt; it never blocks on a `pending` decision, which is the review channel, not a defect.
- **`ROADMAP_FORMAT.md`, per step 3** — the schema reference this step's `CLAUDE.md` edit points at; confirm it exists on disk before citing it (it lands as part of this same plan, ahead of this step).
- **`docs/cli/roadmap.md`, per step 7** — the generated flag-level reference; this step's docs should point to it for the exhaustive flag list rather than restating one.
- **BACKLOG #208's anchor entry** (`BACKLOG.md`) — the Stage arc list (four ordered positions: `roadmap-01-domain-constraints` through `roadmap-04-framework-lenses`), the Scope contract's Out-of-scope / Non-goals bullets, and the current Status line naming this plan's file path and step count. This step edits only the Status line; the Stage arc list's own "Leaves: a repo can produce gated `01-domain.md` / `02-constraints.md`" line for arc position 01 is already accurate and forward-looking, so it needs no edit.
- **What this step cannot verify.** Nothing here re-runs the verb or its tests — steps 1–7's suites cover correctness. This step's own checks (below) are read-and-grep verification that the prose matches the shipped contract and that no new claim exceeds it.

## Files (creates vs edits)

No new files.

- **Existing files (edits only):**
  - `USE_CASES.md` — one new numbered use-case entry plus a new row in the "Pick your entry point" table.
  - `RUNBOOK.md` — one new Quick-reference block, one new sentence in "Command families and ordering", one new `## Workflow:` section (plus its Table of contents entry).
  - `integrations/claude/SKILL.md` — one new row in "Subcommands at a glance", one new row in "Decision tree for common user asks", one new bullet in "Going deeper".
  - `CLAUDE.md` — one new bullet in "Reference docs", one new paragraph in "Architecture".
  - `BACKLOG.md` — rewrite BACKLOG #208's Status line.

## Implementation

Cite the exact landed flag names and outcome vocabulary from [Input](#input) everywhere below; do not describe a `--framework` flag, seed emission, or a sign-off surface — see [Applicable guardrails](#applicable-guardrails).

### `USE_CASES.md`

- **Append a new numbered entry rather than inserting and renumbering.** `USE_CASES.md`'s existing ten entries are not in strict pipeline-altitude order (entry 8 is a telemetry-review aside, 9 and 10 were appended when `direct-*` and jira-grade shipped) — the doc's real precedent is additive growth, not reordering. Confirmed no inbound anchor links reference `USE_CASES.md#N-...` from elsewhere in the repo, so a renumber would be *safe* but isn't the established pattern; append entry 11 instead.
  - Cover: the situation (a project-sized concept, not a single feature), the command (`plan-tool roadmap <slug> --from-existing <concept.md>`), what it writes (the two gated artifacts and their directory), that it's non-interactive with `pending` decisions as the review channel, and the `--from-stage N` re-entry loop after a hand edit.
  - State plainly where the arc stops today: this stage produces the domain model and constraint set only — turning them into components and `create --from-existing` seeds is a later, unbuilt BACKLOG #208 position, so today's next step is hand-authoring a seed grounded in what `roadmap` wrote.
  - Point to `docs/cli/roadmap.md` for the full flag reference (step 7's generated page) and to `RUNBOOK.md`'s new workflow section for the walkthrough — **not** to `README.md`, which this step does not touch and does not describe `roadmap` in.
- **Add a row to "Pick your entry point"** (the table near the end): something like `A project-sized concept, before you have a seed | roadmap <slug> --from-existing <concept.md>`.
- Optionally cross-reference from entry 1 ("Turn a rough idea into a buildable plan") back to entry 11 for a reader whose idea turns out to be project-sized — a short forward pointer, not a restatement.

### `RUNBOOK.md`

- **Add a new `## Workflow: turn a concept brief into architecture artifacts (`roadmap`)` section**, positioned right before `## Workflow: start a new plan` — the plan's own Overview frames `roadmap` as "one rung above `create`," which is the same placement rationale step 7 used for `CANONICAL_COMMAND_ORDER`. Add its entry to the Table of contents list in the same relative position.
  - Cover, in the doc's existing walkthrough style (bash blocks + short prose, not a wall of text): the invocation, what each artifact holds, the deterministic-gate-then-retry behavior (one sentence — the mechanism is `roadmap_gates.py`'s job to enforce, not RUNBOOK's job to re-derive), the non-interactive `pending`-as-review-channel design, a worked `--from-stage 2` re-entry example after a hand edit, and the explicit "where the arc stops today" note from the USE_CASES entry above.
  - Close with a pointer to `docs/cli/roadmap.md` for the full flag reference.
- **Add a Quick-reference block.** A short new table — e.g. "**Roadmap (project-altitude, before `create`)**" — placed before "**Discovery & inspection**" (the verb runs before there's anything to discover), with rows for the base invocation and the `--from-stage` re-entry form.
- **Add one sentence to "Command families and ordering."** `roadmap` sits outside the seven numbered families the same way `annotate` does — the doc already carries a paragraph explaining that `annotate` bridges backward from an old plan into the next `create`; add a short parallel note that `roadmap` bridges forward from a project-sized concept into a `create` seed, one rung above the authoring family (2), and never touches an existing plan or the manifest. Place it near the existing `annotate` paragraph rather than inventing a new subsection.

### `integrations/claude/SKILL.md`

This is the file the user's global `CLAUDE.md` names as the authoritative subcommand catalog for a driving session — get the invocation shape exactly right here.

- **Add a row to "Subcommands at a glance"**, positioned first (before "Discovery") to match its project-altitude: subcommand `roadmap <slug> --from-existing <concept.md> [--from-stage N]`, one-line description naming the two artifacts and the non-interactive/gate-retry behavior, "Calls claude?" = Yes.
- **Add a row to "Decision tree for common user asks."** Something like: user says "I have a project-sized concept, not a single feature" → `plan-tool roadmap <slug> --from-existing <concept.md>` (produces `01-domain.md`/`02-constraints.md`; hand-author your `create` seed from those — the seed-emission stage is a later, unbuilt BACKLOG #208 position).
- **Add a bullet to "Going deeper"** pointing at `ROADMAP_FORMAT.md`, matching the existing `SEED_FORMAT.md` / `PLAN_FORMAT.md` bullets' one-line style.
- Leave the "Maintenance note" bullets under "Subcommands at a glance" and the `argument-hint:` frontmatter field alone — neither needs a `roadmap`-specific addition (the maintenance note is already generic instruction; `argument-hint` documents shared run-style flags `roadmap` doesn't take).

### `CLAUDE.md`

- **Add one bullet to "Reference docs"**, alongside the `PLAN_FORMAT.md` / `DETAIL_FORMAT.md` / `JIRA_FORMAT.md` bullets: `ROADMAP_FORMAT.md` — the frontmatter schema for the `roadmap` verb's two staged artifacts, naming the code that enforces each rule (`plan_tool/roadmap_artifacts.py` for shape, `plan_tool/roadmap_gates.py` for relations).
- **Add one paragraph to the Architecture section**, after the existing "Parallel plan worktrees" paragraph (the last one in that section), matching the density and citation style of its siblings (name the modules, the one structural bet, the invariants that don't vary). It should cover: the four modules (`plan_tool/roadmap.py`, `roadmap_artifacts.py`, `roadmap_gates.py`, `cli/roadmap_cmd.py`) and their strict one-way import line; a stage is `(prompt file, output path, gate set)` data, not a code branch; disk is the interface between stages, so `--from-stage` re-entry re-reads (and honors hand edits to) whatever an earlier stage wrote; a failing gate retries the same stage with violations quoted back, and an exhausted budget is the verb's only non-zero-exit path; non-interactive by construction, with `pending` decisions as the review channel instead of a TTY prompt; and that this stage (`roadmap-01-domain-constraints`, BACKLOG #208) ships `01-domain.md` / `02-constraints.md` only — the components and plan-derivation stages that turn these into `create` seeds are later, unauthored arc positions.

### `BACKLOG.md`

- **Rewrite BACKLOG #208's Status line.** Replace "stage 01 **plan-authored** … Execution is pending, and 5 steps had suggested gates auto-dropped by `-y` — vet them with `plan-tool suggest-gates` before running" with a shipped-state statement: **arc position 01** (`roadmap-01-domain-constraints`) **shipped** (still naming the plan file and its archived seed for provenance), that `plan-tool roadmap <slug> --from-existing <concept.md> [--from-stage N]` is live, and a pointer to `USE_CASES.md` / `RUNBOOK.md` / `integrations/claude/SKILL.md` for the operator workflow. Drop the "5 steps had suggested gates auto-dropped… before running" caveat entirely — it was operational guidance for running *this plan's own steps*, and once every step is `done` it no longer applies to anything; leaving it in reads as a live instruction for a run that already happened, which is exactly the stale-present-tense pattern `CLAUDE.md`'s forward-looking-docs rule flags.
- Keep the Stage arc list (the four ordered positions) and the Scope contract unedited — both already describe the arc in the accurate, forward-looking terms this step's own docs edits must match; re-read them as the source of truth for what arc position 01 does and does not cover, don't restate their mechanics elsewhere in `BACKLOG.md`.
- Leave every other `roadmap-01-domain-constraints` mention in `BACKLOG.md` (the grounding-quality-tag list entry, the unrelated `--commit` near-miss investigation entry) untouched — neither makes a stage-status claim this step's reconciliation affects.

### Constraints that are not free to vary

- **Describe only what artifact stages 1–2 ship, and keep the two numberings named.** The plan's Overview settles that an **arc position** is one plan of BACKLOG #208's four while an **artifact stage** is one numbered file the pipeline writes; they do not line up, so no sentence in these five files numbers a bare "stage". An operator reads this prose beside `--from-stage N`, which takes an artifact stage — a bare "stage 01" next to it invites exactly the wrong invocation. Every new sentence across all five files names `01-domain.md` and `02-constraints.md` specifically — never "the artifacts" vaguely in a way that could later be read as covering components or seeds too.
- **Never claim seed emission, `--framework`, or a sign-off/interactive surface.** See [Applicable guardrails](#applicable-guardrails) — these are the plan's own Out-of-scope bullets, not just a style preference.
- **Don't touch `README.md` or `CAPABILITIES.md`.** Neither is in this step's declared file list; `docs/cli/roadmap.md` (step 7) is the flag-level reference this step's docs point to instead of restating one, and `CAPABILITIES.md`'s entry already landed in step 7.

## Tests

### Verification (non-code step)

This is a `non-code` step in a plan with `enforce_step_tests: true`; the test-authoring gate keys on `change_type` and doesn't fire here. Verify instead:

1. Re-read `plan_tool/cli/roadmap_cmd.py` and run `plan-tool roadmap --help` (or read step 7's generated `docs/cli/roadmap.md`); confirm every flag and default named across the five edited files matches exactly — no more, no fewer.
2. Grep each edited file for the two artifact filenames (`01-domain.md`, `02-constraints.md`) and confirm every mention of "the artifacts" is scoped to those two, never phrased in a way that also reads as covering components or seeds.
3. Confirm `ROADMAP_FORMAT.md` and `docs/cli/roadmap.md` exist on disk at HEAD before `CLAUDE.md` / `USE_CASES.md` / `RUNBOOK.md` cite them.
3a. **Resolve `ROADMAP_FORMAT.md`'s forward references.** Step 3 wrote the doc before `plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`, and the two stage prompt files existed, and deliberately cited them as bare module paths its own verification could not check. Every one of them is on disk by now, so `rg` each path the doc cites against the tree and confirm zero misses — this is the step that closes step 3's deliberately open check, and it is the last point in the plan where a path that never landed would still be caught.
4. In `RUNBOOK.md`, confirm the new `## Workflow:` heading's GitHub-slug anchor matches its new Table-of-contents entry — the same anchor string must appear in both places.
5. In `BACKLOG.md`, confirm the #208 Status line no longer contains "Execution is pending" or the auto-dropped-gates caveat, and does contain a shipped-state statement naming the live invocation.
6. Re-read the plan's Out-of-scope bullets (below) and confirm none of the five files' new prose claims a `--framework` flag, seed/component output, or an interactive/TTY sign-off surface for `roadmap`.
7. `git status --porcelain` shows modifications (`M`) to exactly the five declared files and creates nothing new.

## Acceptance criteria

- `USE_CASES.md` contains a new numbered use-case entry documenting `plan-tool roadmap <slug> --from-existing <concept.md>` and its `--from-stage N` re-entry, and the "Pick your entry point" table has a row routing a project-sized concept to it.
- `RUNBOOK.md`'s Table of contents lists a new `roadmap` workflow section whose anchor resolves to a real `##` heading in the file; its Quick-reference section and "Command families and ordering" section both name `roadmap`.
- `integrations/claude/SKILL.md`'s "Subcommands at a glance" table and "Decision tree for common user asks" table each contain a row for `roadmap`, and "Going deeper" links `ROADMAP_FORMAT.md`.
- `CLAUDE.md`'s "Reference docs" list contains a `ROADMAP_FORMAT.md` bullet, and its Architecture section contains a paragraph naming `plan_tool/roadmap.py`, `roadmap_artifacts.py`, `roadmap_gates.py`, and `cli/roadmap_cmd.py`.
- `BACKLOG.md` #208's Status line states arc position 01 shipped and no longer contains "Execution is pending" or the auto-dropped-gates caveat.
- No sentence added by this step numbers a bare "stage": every occurrence is qualified as an **arc position** or an **artifact stage**, matching the plan's Overview.
- None of the five edited files claims `roadmap` supports a `--framework` flag, emits components or `create` seeds, or offers an interactive/TTY sign-off surface for `pending` decisions.
- Every module path `ROADMAP_FORMAT.md` forward-referenced at step 3 — `plan_tool/roadmap.py`, `plan_tool/cli/roadmap_cmd.py`, and the two stage prompt files — resolves to a file on disk.
- `README.md` and `CAPABILITIES.md` carry no diff from this step.
- `git status --porcelain` after this step shows modifications to exactly `USE_CASES.md`, `RUNBOOK.md`, `integrations/claude/SKILL.md`, `CLAUDE.md`, and `BACKLOG.md` — no other file touched, no new file created.

## Applicable guardrails

The plan's Out-of-scope / Non-goals bullets bound what this step's prose may claim, since documentation is the one place a scope violation can slip in without any gate catching it:

- **No components or plan-derivation stage.** BACKLOG #208's `roadmap-02-components` and `roadmap-03-plan-derivation` are unbuilt — nothing in these five docs may describe `roadmap` as producing components or `create` seeds today.
- **No sign-off command for `pending` decisions.** The review channel is a hand edit plus `--from-stage N` re-entry; don't describe or imply an interactive confirm/approval walk.
- **No interactive/TTY surface.** `roadmap` takes no `-y`/`--yes`/`--iterate`; don't describe a confirmation prompt anywhere.
- **No per-project quality-attribute configuration.** The constraints stage ships one generic list inline; don't describe a `--framework` flag or a config-file override.
- **The concept brief is the operator's input.** `--from-existing` reads a file the operator supplies; don't describe `roadmap` as authoring, distilling, or validating the brief itself.

## Deferred

- **`README.md`'s own subcommand reference** — not in this step's declared files or the plan's acceptance criteria; `docs/cli/roadmap.md` (step 7) plus the four docs this step edits are the documented surface for now. A follow-up if full `README.md` coverage (matching its `worktree` / `scope-out` sections) is wanted later.
- **A dedicated `docs/ROADMAP_FLOW.md` gate/sequence diagram** — the family `docs/RUN_FLOW.md` / `docs/AUDIT_FLOW.md` belong to; not named in this plan's files or acceptance criteria, and premature while only two of the arc's four stages exist.
- **Documentation for the components, plan-derivation, and framework-lens stages** — BACKLOG #208's `roadmap-02-components`, `roadmap-03-plan-derivation`, `roadmap-04-framework-lenses`; each documents itself once it ships, per this step's own scope fence.
- **`CAPABILITIES.md`'s `roadmap` entry** — step 7's deliverable, already landed by the time this step runs; this step doesn't touch the file.
- **A sign-off/interactive walk for `pending` decisions** — no such surface exists in the shipped verb (plan Out of scope); nothing to document beyond the hand-edit + `--from-stage` loop.
