> **Replaced**: this file has been superseded by `docs/implementation-plans/2-structural-remedy-vocabulary.md`.
> Preserved here for history; do not edit.

# Plan seed: unified structural-remedy vocabulary (split / merge-by-altitude + scope-out) and a code-grounded reconcile structural check

Unifies BACKLOG **#70** (model the structural remedies as one split/merge axis +
add **scope-out**) and **#67** (give `reconcile` a **code-grounded**
structural-decomposition check) — they share one remedy vocabulary, so plan them
together.

## Guiding principle

Today the tool's structural remedies are three separate primitives — **re-split**
a step (`granularity-split`), **merge** adjacent steps (`granularity-merge`),
**re-seed** the whole plan (the `convergence` diagnostic's structural fork). Model
them instead as **one split/merge axis parameterized by two things**, and add the
one remedy the tool can *detect the need for* but cannot yet *recommend*:
**reduce-scope**.

This is a **compose-existing** plan, not a new split/merge *algorithm*. The
executors already exist; the gaps are (a) the unified vocabulary + the scope-out
recommendation, and (b) a code-centric arm in `reconcile`. Keep everything
**advisory / recommend-only** (detection is unconditional; mutation stays gated +
confirmed — Principle 1 *converge; mutate only when allowed*).

## The two-parameter model (#70)

A structural remedy is `split` or `merge`, parameterized by:

1. **Altitude** — a **step** (→ two sibling steps) vs the **plan's scope** (→ a
   narrowed plan + a deferred remainder).
2. **Disposition of the carved-off side** — **retained as a sibling step**
   (ordinary split) vs **deferred out of the plan** (**scope-out**).

Then the whole space collapses to one axis:

- **scope-out = split at the plan-scope altitude with the carved side deferred**
  — *not a 4th primitive*.
- **merge** = the inverse of split (fold a sibling back in / re-ground).
- **re-seed** = the limit (split everything / restart).

### Why scope-out is the missing piece (motivating evidence)

This session a *spinning* region (the PPW `prune`/clone-lifecycle work — recurred
as HIGH across rounds, then **backfired into data-loss HIGHs when patched**) had
exactly one right remedy: **carve clone-destruction out of scope and defer it**.
The tool had the *detection* signal (`convergence` detects recurrence +
no-shrinkage across saved reports) but **no scope-out remedy in its vocabulary**
— it only offers *rebuild* remedies (re-seed / re-split), never *reduce-scope*. So
the scope-out was done by hand. The tool *names* spinning but can't yet
*recommend* the reduce-scope response.

## The code-grounded structural check in reconcile (#67)

The structural-decomposition assessment (re-seed / merge / split) belongs in
**both** `completeness` and `reconcile`, grounded differently:

- `completeness` already judges it **plan-centrically** (the granularity advisor
  folds split/merge into its `Smells` bucket; `convergence` does re-seed).
- `reconcile` should judge it **code-centrically** — does the *current code state*
  imply a decomposition change? Its **strongest unique signal**: a collection of
  steps **already partially implemented in the code → merge / re-ground** (only
  `reconcile`, reading the code, can see this); likewise code reality can reveal a
  step that must **split**.

Today `granularity.py` is wired into `create` / `detail` / `completeness`, **not**
`reconcile` (`review.py:review_plan_full` / `render_review_prompt`), so the
code-grounded "these steps are already built / the code outgrew this boundary"
structural feedback has **no home**. This is distinct from the
bookkeeping-false-positive noise in BUG_BACKLOG ("reconcile review leaks into
completeness's lane") — that's noise to remove; this is the *valuable* structural
check to add, code-grounded. Keep it **advisory** (recommend-only), like the
granularity advisor — never auto-mutate structure.

## The unified remedy vocabulary (emit through what already exists)

| Remedy | Sources / executors already in the tree |
|---|---|
| **split** (step altitude) | `granularity-split` (`granularity.py`) → `plan-tool split` → the `escalate_to_split` bridge (`launcher.py`) |
| **merge** | `granularity-merge` (`granularity.py`) → `plan-tool merge` |
| **re-seed** (plan limit) | the `convergence` diagnostic's structural fork → `create --from-existing` |
| **scope-out** (plan altitude + defer) | **NEW** — composes: narrow the plan + route the carved part to `## Deferred` / a `BACKLOG.md` entry (the out-of-scope→backlog routing rule already does the latter) or a forward-seed via `annotate` |

## Seams already in place (verify before extending)

- **`convergence_diagnosis.py`** — spinning detection (recurrence + no-shrinkage
  across saved report history) and the **localized-vs-structural fork**
  (`classify_fork`): localized over-pack → `plan-tool split --step N`; structural
  → `create --from-existing`. Surfaced read-only by `plan-tool convergence`
  (always exits 0, no Claude, no mutation). **This is where the scope-out
  recommendation is added** as a third fork arm (localized reduce-scope), distinct
  from re-split.
- **`granularity.py`** — the advisory `granularity-split` / `granularity-merge`
  detectors (deterministic, plan-structure-only, no Claude); kept out of
  `APPLY_ELIGIBLE_SOURCES`. The detectors `#67` reuses for the code-grounded arm.
- **`escalate_to_split` (`launcher.py`)** — the single seam from a recognized
  mixed/structural step to an *applied* refactor+feature 1→2 split or a
  `structural-split` *recommendation*; `applied` only when safe + `allow_split` +
  interactive confirm. The localized split executor.
- **`plan-tool split` / `plan-tool merge`** — the step-level executors (the merge
  executor exists; a flagged merge pair is resolved by hand-running it).
- **out-of-scope → backlog routing** (`scope_guard.write_out_of_scope_plan`, the
  BACKLOG.md decision rule) — the scope-out **destination** for the carved part.
- **`annotate`** — the forward-seed bridge (emits a `create --from-existing` seed
  for the *next* iteration without mutating its source); an alternative scope-out
  destination.
- **`reconcile` (`review.py:review_plan_full`, `render_review_prompt`,
  `prompts/review.md`)** — the code-centric audit `#67` extends; note the recent
  `creates:` grounding fix (declared files = `files:` ∪ `creates:`).

## Scope of work

**Spike the detection → recommendation first** (cheap, no executor) before the
mutation paths:

1. **Convergence scope-out recommendation (#70):** extend the
   localized-vs-structural fork to emit a **scope-out / defer** recommendation
   when a region spins at high (esp. **data-loss-grade**) severity that won't
   converge. Scope-out is *localized* (carve one region), surfaced alongside
   re-split, distinct from the structural re-seed. Read-only / advisory; the
   `convergence` command renders it.
2. **Unified-vocabulary surface:** make the three (now four) remedies legible as
   one model in the relevant render/help so an operator sees split / merge /
   scope-out / re-seed as points on one axis (doc + the recommendation prose).
3. **Code-grounded reconcile structural pass (#67):** a code-vs-plan
   structural-decomposition pass in `reconcile`, reusing the
   `granularity-split` / `granularity-merge` remedy vocabulary. The **novel
   detector** is "step(s) already (partially) implemented → merge / re-ground"
   from the code-vs-plan diff (reuse reconcile's existing symbol-token heuristic
   carefully). Advisory, recommend-only.
4. **Scope-out executor (#70):** narrow the plan + route the carved part to
   `## Deferred` / a `BACKLOG.md` entry (compose the out-of-scope routing) or a
   forward-seed via `annotate`. **No new split algorithm** — compose the existing
   carve + route pieces. Gate mutation behind explicit opt-in + confirm, mirroring
   `escalate_to_split`'s never-mutate-structure-unattended invariant.

## Non-goals / out of scope

- A **new split/merge algorithm** — reuse `escalate_to_split`, `plan-tool split` /
  `merge`, `create --from-existing`.
- **Auto-mutating structure unattended** — every actuating path stays opt-in +
  interactive-confirm; the default path spends no Claude and only *recommends*.
  The structural re-seed stays human-authored (an auto-re-decompose that guesses
  wrong silently reshapes the plan's spine).
- Removing the BUG_BACKLOG reconcile-lane bookkeeping noise — that's a separate
  fix; this adds the *valuable* code-grounded structural check.
- **Clone-destruction / clone-lifecycle work itself** — that was the motivating
  scope-out, already handled by hand; this plan is the general capability.

## Risks

- **False "already implemented → merge" calls** on superficial symbol overlap —
  reuse reconcile's symbol-token heuristic carefully; keep it advisory so it never
  auto-mutates.
- **Scope-out routing correctness** — the carved part must land somewhere tracked
  (Deferred / BACKLOG / a forward seed), never silently dropped.
- **Vocabulary churn** — renaming/unifying must not break the existing
  `granularity-split` / `granularity-merge` / `structural-split` routing tokens or
  their `APPLY_ELIGIBLE_SOURCES` exclusion.

## Acceptance criteria (plan-level)

- `plan-tool convergence` emits a **scope-out / defer** recommendation on a
  high-severity (data-loss-grade) spinning region that won't converge — alongside
  the existing re-split (localized) and re-seed (structural) forks, distinct from
  both. Read-only, advisory, exits 0.
- `reconcile` surfaces a **code-grounded** structural-decomposition finding when
  the current code implies a merge/split (the headline signal: steps already
  partially implemented → merge / re-ground), emitted through the existing
  `granularity-*` remedy vocabulary, advisory and never flipping the exit code.
- The four remedies (split / merge / scope-out / re-seed) read as **one
  altitude × disposition model** in the docs and the recommendation prose; no new
  split/merge algorithm is introduced.
- A scope-out, when actuated (opt-in + confirm), **narrows the plan and routes the
  carved part** to `## Deferred` / a `BACKLOG.md` entry / an `annotate` forward
  seed — never dropping it; the default path only recommends.
- Existing structural routing tokens and their `APPLY_ELIGIBLE_SOURCES` exclusion
  are unchanged; the granularity advisor and `escalate_to_split` behave as before.
