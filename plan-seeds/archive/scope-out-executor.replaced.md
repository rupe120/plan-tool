> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-out-executor.md`.
> Preserved here for history; do not edit.

# Plan seed: the `plan-tool scope-out` executor (carve a region out of a plan into a forward-seed)

The actuating half of the structural-remedy work, carved out of
`structural-remedy-vocabulary` (which ships the *advisory* arms — the `scope-out`
source token + triage wiring, the convergence scope-out **recommendation**, the
reconcile code-grounded **finding**, and the docs). This plan builds the one piece
that genuinely needs **new code + a resolved design decision**: the gated
`plan-tool scope-out <plan>` executor that *acts on* that recommendation.

> **Why a separate plan.** A deep 5-pass audit of the combined plan (coverage
> confirmed) put 5 of 6 HIGH/structural findings on this executor: it is **not**
> compose-existing for its narrowing half, and it was gated on an unresolved
> run-state question (now decided — see below). The advisory arms are cheap,
> low-risk compose-work; this is high-complexity new-primitive work. Splitting
> keeps each plan bounded and lets the executor land grounded by the decisions
> below instead of re-packing them into the vocabulary plan.

## What scope-out is (the actuator)

Scope-out = **split at the plan-scope altitude with the carved side emitted as a
forward-seed**. When a region of a plan is spinning (recurs + no-shrinkage at
`max_severity ≥ high` with a non-decreasing first→last severity trend — the
"patches backfire" signature the `convergence` diagnostic detects), the right
remedy is to **carve that region out** so the rest of the plan can converge, and
land the carved work somewhere durable and resumable.

`plan-tool scope-out <plan> --step N` does two mutations, **seed-first**:

1. **Emit a `create --from-existing` forward-seed** for the carved step(s) under
   `plan-seeds/<plan>-carved-<slug>.md`, **carrying the carved step's run state**
   (status + progress) into the seed so the work is resumable in the next
   iteration (Resolved decision: run-state → carry into the seed, below).
2. **Narrow the plan**: drop the carved step(s) from `steps:`, renumber the
   survivors to contiguous `1..N`, and migrate the downstream detail files to their
   new ids.

**Seed-first ordering is the atomicity contract**: a crash after the seed write
leaves a harmless, re-runnable orphan seed (carved work captured); a crash before
it leaves the plan untouched. Never narrow before the carved region is durably
written.

## Resolved design decisions (ground the build on these — they fix the audit's HIGHs)

1. **Run-state of the carved step → carry into the seed.** Scope-out's whole
   purpose is to carve a step that *has* run state (the motivating PPW
   `prune`/clone-lifecycle region recurred + backfired *because* it was worked).
   So the executor must **not** reuse the PENDING-only safety gate verbatim
   (`merge_steps` / `split_step` / `escalate_to_split` all refuse a run-started
   *target*) — that would forbid the exact case scope-out exists for — and must
   **not** silently discard run state. Instead: **the emitted seed records the
   carved step's status + progress**, so the work travels intact and is resumable.
   The safety gate that *does* apply is the downstream-orphaning one (below), not a
   refuse-if-worked gate on the target. (fixes `scope-out-carved-step-runstate`)

2. **The narrow is a NEW primitive — not `merge` or `split`.** No existing executor
   *drops* a step: `split_step` is one→many, `merge_steps` folds many→**one
   survivor** at `min(merge_ids)` (it never removes a step's content). Scope-out
   drops the carved step(s) and discards nothing only because the content was
   already written to the seed in mutation 1. **Reuse** the renumber + detail-file
   migration machinery (`create._apply_step_merge`'s contiguous-renumber logic and
   `detail._migrate_downstream_details_after_merge`'s downstream-id rename), but
   the drop-and-renumber-around-the-hole narrowing is genuinely new code. Do not
   claim "compose-existing" for this half. (fixes `narrow-drop-primitive`)

3. **Intra-narrow atomicity.** The narrow itself is multi-step (rewrite frontmatter
   `steps:` + renumber + rename on-disk detail files); a crash *mid-narrow* can
   leave frontmatter and detail files inconsistent. Make the narrow all-or-nothing:
   compute the full new-plan + file-rename plan in memory (a dry-run preview, as
   `merge_steps(dry_run=True)` already does), validate, then apply with rollback on
   failure — never a partial on-disk state. (fixes `narrow-atomicity`)

4. **Empty-plan guard.** Carving the plan's *only* surviving step would produce a
   `steps: []` plan — the exact rot anti-pattern the forward-seed disposition was
   chosen to avoid. **Refuse** when the carve would empty the plan, with a message
   pointing the operator at a full re-seed (`create --from-existing`) instead — a
   plan with nothing left is a re-seed, not a scope-out. (fixes
   `scope-out-last-step-empty-plan`)

5. **Carved-region seed emitter — adapt, don't force-reuse.** `annotate`'s emitter
   `annotate_render.render_create_seed(annotation: PlanAnnotation, *, report_path)`
   consumes a **whole-plan** `PlanAnnotation` (from `annotate.classify_plan_implementation`,
   a Claude classification of every section) and writes **beside the source** — its
   input contract does not match a carved *step-subset* written under
   `plan-seeds/`. Build a **focused carved-region seed renderer** (or a thin adapter
   that synthesizes the minimal seed from the carved `Step`s + their detail bodies +
   run state), rather than manufacturing a `PlanAnnotation`. No Claude needed for
   the emit — it is a deterministic serialization of the carved steps. (fixes
   `scope-out-seed-emission-reuse`)

6. **Gating mirrors `escalate_to_split` (`launcher.py`).** The mutation applies only
   when **safe** (no downstream non-PENDING/run-started step would be orphaned by
   the renumber) **+ opt-in** flag **+ interactive confirm `yes`**. Every other path
   (unattended, unsafe, non-TTY, declined) **recommends only** and the default path
   spends **no Claude** and performs **no mutation** — the two invariants *always
   surface the more-correct plan* and *never mutate structure unattended*. Return a
   frozen result mirroring `EscalateResult` (an `outcome` like
   `applied` / `recommended` / `unsafe` / `step-missing`; only `applied` mutates),
   and re-parse the plan from disk on entry.

## Dependency on the advisory plan

This plan **depends on `structural-remedy-vocabulary`** (the advisory arms) landing
first:

- That plan introduces the `scope-out` source token (kept out of
  `APPLY_ELIGIBLE_SOURCES`) and the per-source triage message, and makes the
  `convergence` scope-out recommendation render **prose-only** (no runnable command
  yet — Resolved decision 7 of that plan).
- **This plan flips that**: once `plan-tool scope-out` exists, update
  `convergence_diagnosis.py:render_diagnosis` (alongside `_split_command` /
  `_reseed_command`) to render the **runnable** `plan-tool scope-out <plan> --step N`
  command for the scope-out sub-arm. No forward-ref: the command is rendered only
  after its executor ships.

## Seams to reuse / extend (verified at HEAD)

- `plan_tool/detail.py` — `merge_steps` / `split_step` (the step-altitude
  executors, the gating + dry-run + canonical-numbering model to mirror);
  `_migrate_downstream_details_after_merge` (reuse the downstream detail-file
  rename); `MergeResult`/dry-run preview shape.
- `plan_tool/create.py` — `_apply_step_merge` (the contiguous-renumber primitive to
  reuse for the survivors after the drop).
- `plan_tool/annotate_render.py:render_create_seed` + `plan_tool/annotate.py`
  (`PlanAnnotation`, `classify_plan_implementation`) — the existing seed emitter to
  adapt around, **not** drop-in reuse (Resolved decision 5).
- `plan_tool/launcher.py` — `escalate_to_split` + `EscalateResult` (the gating model
  + frozen-result contract to mirror).
- `plan_tool/convergence_diagnosis.py` — `render_diagnosis`, `_split_command`,
  `_reseed_command` (where this plan flips the scope-out recommendation from
  prose-only to a runnable command).
- `plan_tool/cli/` — `app.py` (dispatch) + `parser.py` (argparse) + a new thin
  `scope_out_cmd.py` wiring args to the orchestrator; the real work in a new
  `plan_tool/scope_out.py` leaf (mirrors the thin-handler / orchestrator layering).
- `plan_tool/schema.py` — `Plan` / `Step` / `StepStatus`; the run-state fields the
  seed must carry.

## Scope of work (indicative — let create decompose)

1. The new **narrow primitive** in `plan_tool/scope_out.py`: drop carved step(s),
   reuse `_apply_step_merge`'s renumber + `_migrate_downstream_details_after_merge`,
   all-or-nothing with a dry-run preview + rollback (Resolved decisions 2, 3).
2. The **carved-region seed emitter** carrying run state (Resolved decisions 1, 5).
3. The **executor orchestrator** sequencing seed-first → narrow, with the
   `escalate_to_split`-style gate (safe + opt-in + confirm) and frozen result
   (Resolved decision 6), plus the empty-plan refusal (Resolved decision 4).
4. The **CLI surface**: `plan-tool scope-out <plan> --step N [--yes]`, thin handler
   + parser wiring + generated `docs/cli/scope-out.md`.
5. **Flip the convergence recommendation** to render the runnable command
   (dependency section).
6. **Docs**: RUNBOOK recipe + the four-remedy altitude × disposition model note
   referencing the now-shipped actuator (coordinate with the vocabulary plan's docs
   step to avoid double-writing watched files).

## Non-goals / out of scope

- A new split/merge algorithm for the **step** altitude — reuse `split_step` /
  `merge_steps`.
- **Auto-mutating structure unattended** — every actuating path stays opt-in +
  interactive-confirm; default recommends only, spends no Claude.
- A **BACKLOG.md writer** or an **in-plan `DEFERRED`** disposition — the carved part
  is a forward-seed, full stop (settled in the vocabulary plan).
- The advisory arms themselves (token, triage, convergence *recommendation*,
  reconcile *finding*) — those ship in `structural-remedy-vocabulary`.

## Risks

- **Run-state fidelity in the seed** — the carried status/progress must round-trip
  so `create --from-existing` resumes correctly; test the carry explicitly.
- **Partial on-disk state** — mitigated by the dry-run-preview-then-apply +
  rollback narrow (Resolved decision 3) and the seed-first ordering.
- **Renumber orphaning** — the safety gate must catch a downstream non-PENDING step
  whose id would shift; mirror `merge_steps`'s unsafe-set refusal for *downstream*
  (not target) steps.
- **Doc double-write** — this plan and the vocabulary plan both touch RUNBOOK/CLAUDE
  docs; sequence them so a watched-file drift guard does not halt mid-run.

## Acceptance criteria (plan-level)

- `plan-tool scope-out <plan> --step N` (opt-in + interactive confirm, on a safe
  plan) **emits a `create --from-existing` forward-seed carrying the carved step's
  run state, then narrows the plan** (drop + renumber + migrate detail files) —
  seed-first, never dropping the carved work.
- A carved step with **live run state** is carried into the seed (status +
  progress preserved, resumable) — **not** refused, **not** silently discarded.
- The narrow is **atomic** (dry-run preview + apply-or-rollback); no partial
  frontmatter/detail-file state on crash.
- Carving the plan's **only** surviving step is **refused** with a re-seed hint
  (never a `steps: []` plan).
- The default / unattended / unsafe / non-TTY / declined paths **recommend only**,
  spend **no Claude**, and perform **no mutation**; the result is a frozen
  `EscalateResult`-style value where only `applied` mutated.
- `plan-tool convergence` renders the **runnable** `plan-tool scope-out … --step N`
  command for the scope-out sub-arm (flipped from the vocabulary plan's prose-only).
