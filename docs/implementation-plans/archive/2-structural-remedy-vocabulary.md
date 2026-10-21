---
title: Structural Remedy Vocabulary
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add a scope-out/defer fork arm to the convergence diagnostic's localized-vs-structural
    classifier (#70)
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: Wire a code-grounded structural-decomposition pass into reconcile (review.py),
    emitting advisory granularity-merge/split findings from the symbol-token 'already
    implemented' signal (#67)
  files:
  - plan_tool/review.py
  - plan_tool/prompts/review.md
  - tests/test_review.py
  complexity: medium
  change_type: feature
- id: 3
  title: 'Add the gated scope-out executor + `plan-tool scope-out` command — narrow
    the plan (StepScope.DEFERRED) and route the carved part to ## Deferred / BACKLOG.md
    / an annotate forward seed, composing existing carve+route pieces (#70)'
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - plan_tool/scope_guard.py
  - CAPABILITIES.md
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/scope_out.py
  - plan_tool/cli/scope_out_cmd.py
  - tests/test_scope_out.py
  - tests/cli/test_scope_out_cmd.py
  - docs/cli/scope-out.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
- id: 4
  title: 'Document split / merge / scope-out / re-seed as one altitude × disposition
    model and trim BACKLOG #70/#67 to their shipped state'
  files:
  - README.md
  - RUNBOOK.md
  - CLAUDE.md
  - BACKLOG.md
  - integrations/claude/SKILL.md
  - integrations/codex/SKILL.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  - 2
  - 3
---
# Structural Remedy Vocabulary

## Overview

This plan unifies the tool's structural remedies into **one split/merge axis** and fills the gaps around it. Today the remedies are three separate primitives — re-split a step (`granularity-split`), merge adjacent steps (`granularity-merge`), and re-seed the whole plan (the `convergence` diagnostic's structural fork). This plan models them as one `split`/`merge` axis parameterized by **altitude** (a step vs the plan's scope) and **disposition of the carved-off side** (retained as a sibling vs deferred out of the plan), adds the missing **scope-out** (reduce-scope) remedy the tool can detect the need for but cannot yet recommend, and gives `reconcile` a **code-grounded** structural-decomposition check. It is a **compose-existing** plan — the executors already exist — and everything stays **advisory / recommend-only**: detection is unconditional; mutation stays gated + confirmed (Principle 1, *converge; mutate only when allowed*). Unifies BACKLOG **#70** and **#67**, which share one remedy vocabulary.

## Problem statement

The tool's structural remedies are three disconnected primitives (`granularity-split`, `granularity-merge`, and the `convergence` diagnostic's re-seed fork), so an operator can't see them as points on one model, and one needed remedy is missing entirely: **reduce-scope**. The tool has the *detection* signal — `convergence` detects recurrence + no-shrinkage across saved reports — but **no scope-out remedy in its vocabulary**; it only offers *rebuild* remedies (re-seed / re-split), never *reduce-scope*. Motivating evidence: this session a *spinning* region (the PPW `prune`/clone-lifecycle work — recurred as HIGH across rounds, then **backfired into data-loss HIGHs when patched**) had exactly one right remedy — carve clone-destruction out of scope and defer it — and the scope-out had to be done by hand. The tool *names* spinning but can't yet *recommend* the reduce-scope response.

Separately, the structural-decomposition assessment belongs in **both** `completeness` and `reconcile`, grounded differently: `completeness` already judges it plan-centrically (the granularity advisor folds split/merge into its `Smells` bucket; `convergence` does re-seed), but `granularity.py` is wired into `create` / `detail` / `completeness`, **not** `reconcile` (`review.py:review_plan_full` / `render_review_prompt`). So the code-grounded "these steps are already built / the code outgrew this boundary" structural feedback has **no home**. This is distinct from the bookkeeping-false-positive noise in BUG_BACKLOG ("reconcile review leaks into completeness's lane") — that's noise to remove; this is the *valuable* structural check to add, code-grounded.

## Architecture

**The two-parameter model (#70).** A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a **step** (→ two sibling steps) vs the **plan's scope** (→ a narrowed plan + a deferred remainder) — and (2) **disposition of the carved-off side** — **retained as a sibling step** (ordinary split) vs **deferred out of the plan** (**scope-out**). The whole space then collapses to one axis: **scope-out = split at the plan-scope altitude with the carved side deferred** (*not a 4th primitive*); **merge** = the inverse of split (fold a sibling back in / re-ground); **re-seed** = the limit (split everything / restart).

**Unified remedy vocabulary (emit through what already exists).** Each remedy maps to sources/executors already in the tree:

| Remedy | Sources / executors already in the tree |
|---|---|
| **split** (step altitude) | `granularity-split` (`granularity.py`) → `plan-tool split` → the `escalate_to_split` bridge (`launcher.py`) |
| **merge** | `granularity-merge` (`granularity.py`) → `plan-tool merge` |
| **re-seed** (plan limit) | the `convergence` diagnostic's structural fork → `create --from-existing` |
| **scope-out** (plan altitude + defer) | **NEW** — composes: narrow the plan + route the carved part to `## Deferred` / a `BACKLOG.md` entry (the out-of-scope→backlog routing rule already does the latter) or a forward-seed via `annotate` |

**Seams already in place (verify before extending).**
- **`convergence_diagnosis.py`** — spinning detection (recurrence + no-shrinkage across saved report history) and the localized-vs-structural fork (`classify_fork`): localized over-pack → `plan-tool split --step N`; structural → `create --from-existing`. Surfaced read-only by `plan-tool convergence` (always exits 0, no Claude, no mutation). **This is where the scope-out recommendation is added** as a third fork arm (localized reduce-scope), distinct from re-split.
- **`granularity.py`** — the advisory `granularity-split` / `granularity-merge` detectors (deterministic, plan-structure-only, no Claude); kept out of `APPLY_ELIGIBLE_SOURCES`. The detectors #67 reuses for the code-grounded arm.
- **`escalate_to_split` (`launcher.py`)** — the single seam from a recognized mixed/structural step to an *applied* refactor+feature 1→2 split or a `structural-split` *recommendation*; `applied` only when safe + `allow_split` + interactive confirm. The localized split executor.
- **`plan-tool split` / `plan-tool merge`** — the step-level executors (the merge executor exists; a flagged merge pair is resolved by hand-running it).
- **out-of-scope → backlog routing** (`scope_guard.write_out_of_scope_plan`, the BACKLOG.md decision rule) — the scope-out **destination** for the carved part.
- **`annotate`** — the forward-seed bridge (emits a `create --from-existing` seed for the *next* iteration without mutating its source); an alternative scope-out destination.
- **`reconcile` (`review.py:review_plan_full`, `render_review_prompt`, `prompts/review.md`)** — the code-centric audit #67 extends; note the recent `creates:` grounding fix (declared files = `files:` ∪ `creates:`).

**Scope of work (spike detection → recommendation first, cheap/no executor, before mutation paths).**
1. **Convergence scope-out recommendation (#70):** extend the localized-vs-structural fork to emit a **scope-out / defer** recommendation when a region spins at high (esp. **data-loss-grade**) severity that won't converge. Scope-out is *localized* (carve one region), surfaced alongside re-split, distinct from the structural re-seed. Read-only / advisory; the `convergence` command renders it.
2. **Unified-vocabulary surface:** make the three (now four) remedies legible as one model in the relevant render/help so an operator sees split / merge / scope-out / re-seed as points on one axis (doc + the recommendation prose).
3. **Code-grounded reconcile structural pass (#67):** a code-vs-plan structural-decomposition pass in `reconcile`, reusing the `granularity-split` / `granularity-merge` remedy vocabulary. The **novel detector** is "step(s) already (partially) implemented → merge / re-ground" from the code-vs-plan diff (reuse reconcile's existing symbol-token heuristic carefully). Advisory, recommend-only.
4. **Scope-out executor (#70):** narrow the plan + route the carved part to `## Deferred` / a `BACKLOG.md` entry (compose the out-of-scope routing) or a forward-seed via `annotate`. **No new split algorithm** — compose the existing carve + route pieces. Gate mutation behind explicit opt-in + confirm, mirroring `escalate_to_split`'s never-mutate-structure-unattended invariant.

## References

- [argparse — Parser for command-line options, arguments and subcommands (Python 3 docs)](https://docs.python.org/3/library/argparse.html) — Official stdlib reference for add_subparsers/add_parser an implementer opens when wiring the new convergence scope-out arm and reconcile structural pass into the existing subcommand parser without breaking flag/default conventions.
- [dataclasses — Data Classes (Python 3 docs)](https://docs.python.org/3/library/dataclasses.html) — Authoritative reference for frozen=True immutable dataclasses, needed to extend the frozen EscalateResult-style result contracts and any new recommendation/fork data structures.
- [JSON Lines (jsonlines.org)](https://jsonlines.org/) — The canonical JSONL convention reference for appending one DecisionEvent per line, relevant when recording the new scope-out/structural decisions into the decision-telemetry stream.
- [PyYAML Documentation (PyYAML.org)](https://pyyaml.org/wiki/PyYAMLDocumentation) — Reference for safe_load/dump of YAML, the machine-readable plan frontmatter source of truth that the scope-out executor must read and rewrite when it narrows a plan and routes the carved remainder.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **A new split/merge algorithm** — reuse `escalate_to_split`, `plan-tool split` / `merge`, `create --from-existing`.
- **Auto-mutating structure unattended** — every actuating path stays opt-in + interactive-confirm; the default path spends no Claude and only *recommends*. The structural re-seed stays human-authored (an auto-re-decompose that guesses wrong silently reshapes the plan's spine).
- **Removing the BUG_BACKLOG reconcile-lane bookkeeping noise** — that's a separate fix; this adds the *valuable* code-grounded structural check.
- **Clone-destruction / clone-lifecycle work itself** — that was the motivating scope-out, already handled by hand; this plan is the general capability.

## Risks

- **False "already implemented → merge" calls** on superficial symbol overlap — reuse reconcile's symbol-token heuristic carefully; keep it advisory so it never auto-mutates.
- **Scope-out routing correctness** — the carved part must land somewhere tracked (`## Deferred` / `BACKLOG.md` / a forward seed), never silently dropped.
- **Vocabulary churn** — renaming/unifying must not break the existing `granularity-split` / `granularity-merge` / `structural-split` routing tokens or their `APPLY_ELIGIBLE_SOURCES` exclusion.

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence` emits a **scope-out / defer** recommendation on a high-severity (data-loss-grade) spinning region that won't converge — alongside the existing re-split (localized) and re-seed (structural) forks, distinct from both. Read-only, advisory, exits 0.
- `reconcile` surfaces a **code-grounded** structural-decomposition finding when the current code implies a merge/split (the headline signal: steps already partially implemented → merge / re-ground), emitted through the existing `granularity-*` remedy vocabulary, advisory and never flipping the exit code.
- The four remedies (split / merge / scope-out / re-seed) read as **one altitude × disposition model** in the docs and the recommendation prose; no new split/merge algorithm is introduced.
- A scope-out, when actuated (opt-in + confirm), **narrows the plan and routes the carved part** to `## Deferred` / a `BACKLOG.md` entry / an `annotate` forward seed — never dropping it; the default path only recommends.
- Existing structural routing tokens and their `APPLY_ELIGIBLE_SOURCES` exclusion are unchanged; the granularity advisor and `escalate_to_split` behave as before.

## Deferred

- **Auto-actuation bridge for the new scope-out / reconcile-structural recommendations** — both stay recommend-only this iteration (mirroring `granularity-merge`, which the operator resolves by hand); wiring detection → executor (an `escalate_to_split`-style bridge) waits until the recommendations prove reliable. *(keep advisory first; separate, higher-risk concern.)*
- **`annotate` forward-seed as a scope-out destination** — the executor lands the `## Deferred` / `BACKLOG.md` routing first; the `annotate` forward-seed route can follow. *(smaller initial surface.)*
- **Create-side scope-out trigger** — the scope-out fork is surfaced through `convergence` / `reconcile`; routing it into the `create` convergence loop is deferred, tracking the existing create-side `escalate_to_split` deferral. *(out of this plan's altitude.)*
