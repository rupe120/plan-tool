# Plan seed: the `plan-tool scope-out` executor (carve a region out of a plan into a forward-seed)

The actuating half of the structural-remedy work, carved out of
`structural-remedy-vocabulary` (the *advisory* arms — the convergence scope-out
**recommendation**, the reconcile code-grounded **finding**, the docs). This plan
builds the one piece that needs **new code + resolved design**: the gated
`plan-tool scope-out <plan> --step N` executor that *acts on* that recommendation.

> **Why a separate plan.** A deep audit of the combined plan put almost every
> HIGH/structural finding on this executor: it is **not** compose-existing for its
> narrowing half (no existing executor *drops* a step), it touches hard plan-graph
> mechanics (dependency edges, run cursor, detail-file lifecycle), and the run-state
> "carry" has a real mechanism subtlety. Splitting keeps each plan bounded and lets
> this one land grounded by the decisions below.

## What scope-out is (the actuator)

Scope-out = **split at the plan-scope altitude with the carved side emitted as a
forward-seed**. When a region of a plan is spinning (recurs + no-shrinkage at
`max_severity ≥ high` with a non-decreasing first→last severity trend — the
"patches backfire" signature `convergence` detects), the remedy is to **carve that
region out** so the rest converges, and land the carved work somewhere durable and
re-plannable.

`plan-tool scope-out <plan> --step N` does two mutations, **seed-first**:

1. **Emit a `create --from-existing` forward-seed** for the carved step under
   `plan-seeds/<plan>-carved-<slug>.md`, carrying the carved work as **done-context
   prose** (see Resolved decision 1).
2. **Narrow the plan**: drop the carved step from `steps:`, renumber survivors to
   contiguous `1..N`, repoint/repair `depends_on` edges, archive the carved step's
   detail file, and re-establish a run cursor.

**Seed-first** is the atomicity contract: a crash after the seed write leaves a
harmless re-runnable orphan seed; a crash before it leaves the plan untouched.

## Resolved design decisions (ground the build on these — they fix the audits' findings)

1. **Run-state "carry" = done-context PROSE, not a live-status round-trip.** The
   carved step typically *has* run state (it is the spinning, worked region — often
   the CURRENT step). The user's intent — *nothing lost; resumable next iteration* —
   stands, but the **mechanism** must match reality: `create --from-existing`
   **re-decomposes into fresh PENDING steps** and cannot round-trip live `status`,
   and `schema.Step` has **no `progress` field** (only `status: StepStatus` and the
   ephemeral `status_note`). So the seed carries the carved work as **done-context
   prose** — what was implemented, what remains, and the carved step's
   `status`/`status_note` rendered as narrative — exactly as
   `annotate_render.render_create_seed`'s done-context block does for the whole-plan
   path. The re-plan *accounts for* that context; it does not resume an in-progress
   step verbatim. (fixes `progress-source-undefined`, `runstate-resume-overclaim`)
   - Do **not** reuse the PENDING-only safety gate verbatim
     (`merge_steps`/`split_step`/`escalate_to_split` refuse a run-started *target*)
     — that would forbid the exact case scope-out exists for. A worked carved step
     is allowed; its state is captured as done-context, not refused, not silently
     dropped.

2. **The narrow is a NEW primitive with its OWN drop-renumber — not a reuse of
   `merge`.** No existing executor *drops* a step: `split_step` is one→many,
   `merge_steps` folds many→**one survivor** and repoints dependents to it
   (`create._apply_step_merge`). `_apply_step_merge`'s renumber is **private inline
   fold-logic** (collapses members onto a survivor), not a callable unit and not
   shaped for a drop (which has no survivor) — so the narrow writes its **own**
   small drop-renumber: shift survivors after the hole down by one and rebuild the
   `depends_on` edges (decision 3). Reuse only the **detail-file migration** helper
   (`detail._migrate_downstream_details_after_merge` renames downstream files to
   their new ids); do **not** claim reuse of merge's renumber, and do **not** fold
   an extract-shared-helper refactor into this step (that would make it a
   refactor+feature mixed step). (fixes `narrow-drop-primitive`,
   `narrow-renumber-reuse-feasibility`)

3. **Dependency-graph integrity across the drop (the central correctness gap).**
   The carved step has edges in **both directions** and both must be handled
   explicitly — a silent id reuse corrupts the graph with no validation crash:
   - **Inbound** (a *surviving* step `depends_on` the carved step): after
     drop+renumber that id is reused by a *different* step, silently corrupting the
     edge. `_apply_step_merge` repoints dependents to the survivor; scope-out has
     **no survivor to repoint to**. So scope-out must **refuse** (recommend-only)
     when a surviving step depends on the carved step — carving a prerequisite out
     from under its dependents is not a localized scope-out — *unless* the whole
     dependent sub-tree is carved together (future multi-step carve, Deferred). The
     refusal is part of the safety gate (decision 6).
   - **Outbound** (the carved step `depends_on` surviving upstream steps): those
     prerequisites must be **captured in the seed as done-context** (the carved work
     assumed earlier steps' outputs), so `create --from-existing` re-establishes the
     assumption rather than re-deriving it. (fixes `carved-step-dependents`,
     `carved-step-upstream-deps`)

4. **Carved step's own detail file → archive.** The narrow migrates *downstream*
   detail files (`_migrate_downstream_details_after_merge` touches `id > survivor`),
   but the carved step's **own** detail file would be left orphaned, referencing a
   removed step. Archive it (mirror `merge_steps`, which archives folded-away
   files), since its body is already captured in the seed. (fixes
   `carved-detail-file-disposition`)

5. **Re-establish a run cursor in the narrowed plan.** Scope-out carves a
   run-started (typically CURRENT) step; after the drop, a plan left with a
   DONE+PENDING mix and **no CURRENT** has no cursor for `run` to resume from
   (`create._seed_initial_step_status` only promotes a CURRENT when all steps are
   PENDING). So the narrow must promote the appropriate survivor (the first PENDING
   after the last DONE) to CURRENT. (fixes `narrowed-plan-current-pointer`)

6. **Intra-narrow atomicity + the safety gate (mirror `escalate_to_split`).** The
   narrow is multi-step (drop + renumber + repoint depends_on + migrate/archive
   detail files + set cursor); compute the full new-plan + file-op plan in memory
   (a dry-run preview, as `merge_steps(dry_run=True)` does), validate, then apply
   **all-or-nothing with rollback** — never a partial on-disk state. The mutation
   applies only when **safe** (no inbound dependent on the carved step per decision
   3; no downstream non-PENDING step orphaned by renumber) **+ opt-in flag +
   interactive confirm `yes`**; every other path (unattended, unsafe, non-TTY,
   declined, or the empty-plan case below) **recommends only**, spends **no Claude**,
   performs **no mutation**. Return a frozen `EscalateResult`-style value (`outcome`
   ∈ `applied` / `recommended` / `unsafe` / `step-missing` / `empty-plan`; only
   `applied` mutates); re-parse the plan from disk on entry. (fixes
   `narrow-atomicity`)

7. **Empty-plan guard.** Carving the plan's only surviving step would produce a
   `steps: []` plan — the rot the forward-seed disposition exists to avoid.
   **Refuse** (outcome `empty-plan`) with a message pointing at a full re-seed
   (`create --from-existing`) instead — a plan with nothing left is a re-seed, not a
   scope-out. (fixes `scope-out-last-step-empty-plan`)

8. **Carved-region seed emitter — adapt, don't force-reuse.**
   `annotate_render.render_create_seed(annotation: PlanAnnotation, *, report_path)`
   consumes a **whole-plan** `PlanAnnotation` (from `annotate.classify_plan_implementation`,
   a Claude pass) and writes **beside the source** — wrong contract for a carved
   single-step subset under `plan-seeds/`. Build a **focused, deterministic**
   carved-region renderer (no Claude) that serializes the carved `Step` + its detail
   body + the done-context prose (decision 1) + the captured upstream-dep context
   (decision 3). (fixes `scope-out-seed-emission-reuse`)

## Dependency on the advisory plan (single-step only; multi-region stays prose)

This plan **depends on `structural-remedy-vocabulary`** (the advisory arms) landing
first, and **flips its scope-out recommendation from prose-only to a runnable
command** — but only for the single-step case:

- `plan-tool scope-out --step N` needs **one** resolved step id. The convergence
  scope-out arm fires inside the localized fork, which resolves a single step in the
  one-step case but can hold a multi-region focus; `classify_fork` sets
  `step=None` on `FORK_STRUCTURAL` / unresolvable foci. **Multi-step / multi-region
  carve is Deferred**, so `render_diagnosis` renders the **runnable `--step N`
  command only when a single step resolves, and falls back to prose-only** (the
  vocabulary plan's behavior) when it does not — never emitting a `--step` line with
  no id to fill. (fixes `scope-out-arm-step-focus`)

## Seams to reuse / extend (verified at HEAD)

- `plan_tool/detail.py` — `merge_steps` / `split_step` (the gating + dry-run +
  canonical-numbering model to mirror); `_migrate_downstream_details_after_merge`
  (reuse for downstream detail-file renames); `MergeResult` / dry-run preview shape;
  the folded-away-file **archive** behavior to mirror for the carved file.
- `plan_tool/create.py` — `_apply_step_merge` (study its dependent-repointing +
  renumber, but write a dedicated drop-renumber — decision 2);
  `_seed_initial_step_status` (the CURRENT-promotion rule the narrow must satisfy —
  decision 5).
- `plan_tool/annotate_render.py:render_create_seed` + `plan_tool/annotate.py`
  (`PlanAnnotation`, `classify_plan_implementation`, the done-context block) — the
  existing emitter to *adapt around*, not drop-in reuse (decisions 1, 8).
- `plan_tool/launcher.py` — `escalate_to_split` + `EscalateResult` (the gating model
  + frozen-result contract — decision 6).
- `plan_tool/convergence_diagnosis.py` — `render_diagnosis`, `classify_fork`,
  `_split_command`, `_reseed_command` (where this plan flips the scope-out arm to a
  runnable command for the single-step case — dependency section).
- `plan_tool/cli/` — `app.py` (dispatch) + `parser.py` (argparse) + a new thin
  `scope_out_cmd.py`; the orchestrator in a new `plan_tool/scope_out.py` leaf.
- `plan_tool/schema.py` — `Plan` / `Step` / `StepStatus` / `status_note`
  (the *actual* run-state fields — there is no `progress` field; decision 1).

## Scope of work (indicative — let create decompose)

1. The **carved-region seed emitter** (deterministic; done-context prose + upstream
   deps; decisions 1, 3, 8).
2. The **narrow primitive** in `plan_tool/scope_out.py`: own drop-renumber +
   depends_on repair + detail-file migrate/archive + cursor re-establishment,
   all-or-nothing with a dry-run preview + rollback (decisions 2–5, 6, 7).
3. The **executor orchestrator** sequencing seed-first → narrow, with the safety
   gate (inbound-dep refusal, downstream-orphan refusal, empty-plan, opt-in +
   confirm) and frozen result (decision 6).
4. The **CLI surface**: `plan-tool scope-out <plan> --step N [--yes]`, thin handler
   + parser wiring + generated `docs/cli/scope-out.md`.
5. **Flip the convergence recommendation** to a runnable command for the single-step
   case, prose-only fallback otherwise (dependency section).
6. **Docs**: RUNBOOK recipe + the four-remedy model referencing the shipped actuator
   (coordinate with the vocabulary plan's docs step to avoid double-writing watched
   files).

## Non-goals / out of scope

- A new split/merge algorithm for the **step** altitude — reuse `split_step` /
  `merge_steps`.
- **Multi-step / multi-region carve** — Deferred; this executor is single-step
  (`--step N`); the recommendation falls back to prose for the multi-region case.
- **Auto-mutating structure unattended** — every actuating path stays opt-in +
  interactive-confirm; default recommends only, spends no Claude.
- A **BACKLOG.md writer** or an **in-plan `DEFERRED`** disposition — the carved part
  is a forward-seed (settled in the vocabulary plan).
- The advisory arms themselves — those ship in `structural-remedy-vocabulary`.

## Risks

- **Silent graph corruption** — the inbound-dependent refusal + explicit depends_on
  repair (decision 3) is the mitigation; test a surviving step depending on the
  carved step.
- **Run-state overclaim** — carry as done-context prose, not a live-status
  round-trip (decision 1); the AC tests assert prose content + re-plan accounting,
  not a non-existent field.
- **Partial on-disk state** — dry-run-preview-then-apply + rollback (decision 6) +
  seed-first ordering.
- **Lost run cursor** — re-establish CURRENT in the narrowed plan (decision 5).
- **Doc double-write** — this plan and the vocabulary plan both touch RUNBOOK/CLAUDE
  docs; sequence so a watched-file drift guard does not halt mid-run.

## Detail-time wiring notes (from round-2 audit — resolve during `detail`/impl, not more seed surgery)

The round-2 audit eliminated both HIGHs (graph corruption, single-step focus); these
residual MEDIUM edge-cases ground against code at `detail` time:

- **The safety gate must precede the seed emit.** Run the full validate/refuse pass
  (step-missing, empty-plan, inbound-dependent, downstream-orphan) **before** any
  write — don't emit a forward-seed for a carve that will be refused. "Seed-first"
  orders the two *mutations* (seed before narrow) *within* the apply path, after the
  gate passes. (`safety-gate-precedes-seed`)
- **Make the seed path collision-safe.** `plan-seeds/<plan>-carved-<slug>.md` can
  collide with an existing seed; dedupe the path (suffix/abort-on-exists) rather than
  silently overwriting. (`seed-path-collision`)
- **Refusals name their specific reason.** Each `outcome` (unsafe / empty-plan /
  inbound-dependent / step-missing) surfaces *which* condition fired, so the operator
  knows why and what to do. (`refusal-diagnostics`)
- **Handle a carved step with no detail file (bare step).** The emitter + archive
  must tolerate a carved step that was never detailed — serialize from frontmatter
  only, skip the (absent) detail-file archival. (`carved-step-missing-detail`)
- **Sequence the docs step vs the vocabulary plan's docs step** to avoid a
  watched-file drift-guard halt when both touch RUNBOOK/CLAUDE. (`doc-double-write-risk`)
- **The convergence flip renders, it does not gate.** Step 5's `render_diagnosis`
  flip only *renders* the runnable command; the gate/confirm lives in the executor
  the operator then runs — keep render and apply separate. (`convergence-flip-applies-gate`)
- Already addressed in the decisions above (the audit re-flagged for emphasis):
  the narrow writes its **own** drop-renumber (decision 2), re-establishes the
  **CURRENT cursor** (decision 5), and captures the carved step's **upstream deps**
  as done-context (decision 3) — verify these land legibly in the detail bundle.

## Acceptance criteria (plan-level)

- `plan-tool scope-out <plan> --step N` (opt-in + interactive confirm, on a safe
  plan) **emits a `create --from-existing` forward-seed carrying the carved work as
  done-context prose (incl. its upstream-dep context), then narrows the plan** —
  seed-first, never dropping the carved work.
- The carved step's run state is captured as **done-context prose** (status +
  status_note rendered as narrative) — **not** a claimed live-status round-trip, and
  **not** refused or silently discarded; an AC test asserts the prose content, not a
  non-existent `progress` field.
- The narrow **repairs `depends_on`**: a surviving step that depends on the carved
  step causes a **refusal** (recommend-only), never a silent id-reuse; the carved
  step's own detail file is **archived**; a **CURRENT cursor** is re-established.
- The narrow is **atomic** (dry-run preview + apply-or-rollback); no partial
  frontmatter/detail-file state on crash.
- Carving the plan's **only** surviving step is **refused** (`empty-plan`) with a
  re-seed hint; the default / unattended / unsafe / non-TTY / declined paths
  **recommend only**, spend **no Claude**, and mutate nothing — a frozen
  `EscalateResult`-style value where only `applied` mutated.
- `plan-tool convergence` renders the **runnable** `plan-tool scope-out … --step N`
  only when the localized fork resolves a single step, and **prose-only** otherwise
  (multi-region) — never a `--step` line with no resolvable id.
