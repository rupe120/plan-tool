---
title: Structural Remedy Vocabulary
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add `scope-out` source token and route `granularity-merge` through review.py
    structural triage (keep both out of APPLY_ELIGIBLE_SOURCES)
  files:
  - plan_tool/review.py
  - tests/test_review.py
  - tests/test_granularity.py
  complexity: medium
  change_type: feature
  status: current
- id: 2
  title: 'Add `plan-tool scope-out` executor: seed-first emit `create --from-existing`
    carved-region seed under plan-seeds/, then narrow the plan (drop carved steps
    + renumber + migrate detail files), gated safe + opt-in + interactive confirm'
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - docs/cli/README.md
  - tests/cli/package_surface_help.golden.txt
  creates:
  - plan_tool/scope_out.py
  - plan_tool/cli/scope_out_cmd.py
  - tests/test_scope_out.py
  - docs/cli/scope-out.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
- id: 3
  title: Fork convergence localized arm into re-split vs scope-out in `classify_fork`
    (max_severity ≥ high + non-decreasing first→last severity) and render the runnable
    `plan-tool scope-out` command in `render_diagnosis`
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
- id: 4
  title: Emit a code-grounded structural-merge/re-ground reconcile finding built on
    `heuristic_already_done`, tagged with the `granularity-merge` vocabulary and deduped
    against the existing `heuristic` hit (one finding per step set)
  files:
  - plan_tool/review.py
  - tests/test_review.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
- id: 5
  title: 'Document split / merge / scope-out / re-seed as one altitude × disposition
    model; document `plan-tool scope-out`; trim BACKLOG #70/#67 to their shipped state'
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
  - 2
  - 3
  - 4
---
# Structural Remedy Vocabulary

## Overview

Unifies BACKLOG #70 and #67 into one plan because they share a single structural-remedy vocabulary. It models the tool's three separate structural primitives — re-split a step (`granularity-split`), merge adjacent steps (`granularity-merge`), re-seed the whole plan (the `convergence` diagnostic's structural fork) — as **one split/merge axis** parameterized by altitude and disposition, and adds the one remedy the tool can detect the need for but cannot yet recommend: **scope-out** (reduce-scope). It also gives `reconcile` a **code-grounded** structural-decomposition check. This is a compose-existing plan, not a new split/merge algorithm: the executors already exist. Everything stays **advisory / recommend-only** — detection is unconditional; mutation stays gated + interactively confirmed (Principle 1, *converge; mutate only when allowed*).

## Problem statement

Today the tool's structural remedies are three separate primitives (`granularity-split`, `granularity-merge`, and the `convergence` structural re-seed fork), with no shared model — an operator sees four ad-hoc primitives, not one axis. Two concrete gaps follow: (1) The tool can *detect* a spinning region (`convergence_diagnosis.py` detects recurrence + no-shrinkage across saved reports) but has **no scope-out remedy in its vocabulary** — it only offers *rebuild* remedies (re-seed / re-split), never *reduce-scope*. This session, a spinning region (the PPW `prune`/clone-lifecycle work — recurred as HIGH across rounds, then backfired into data-loss HIGHs when patched) had exactly one right remedy — carve the work out of scope and defer it — and it had to be done by hand. (2) `reconcile` judges the plan code-centrically but lacks a structural-decomposition pass; its strongest unique signal — a collection of steps **already partially implemented in the code → merge / re-ground**, visible only via `review.py:heuristic_already_done` — is unused.

## Architecture

**Two-parameter model (#70).** A structural remedy is `split` or `merge`, parameterized by (1) **altitude** — a step (→ two sibling steps) vs the plan's scope (→ a narrowed plan + carved-out remainder) — and (2) **disposition of the carved-off side** — retained as a sibling step (ordinary split) vs carved out of the plan into a forward-seed (**scope-out**). The space collapses to one axis: scope-out = split at the plan-scope altitude with the carved side emitted as a forward-seed (not a 4th primitive); merge = the inverse of split; re-seed = the limit (split everything / restart).

**Scope-out destination = `annotate` forward-seed (Resolved decision 1).** When scope-out carves a spinning region off a plan, it (a) **narrows the plan** (removes the carved step(s) from `steps:`) and (b) **emits a `create --from-existing` seed file** under `plan-seeds/` for the carved region, reusing the `annotate` forward-seed bridge's seed-emission. The carved work leaves the plan entirely. It is **NOT** `StepScope.DEFERRED` (which parks the step in `steps:` — the opposite of carving out) and **NOT** a BACKLOG.md entry / `scope_guard.write_out_of_scope_plan` (which emits a `steps: []` stub — the rot anti-pattern CLAUDE.md forbids; no programmatic BACKLOG.md writer exists).

**Scope-out atomicity = seed-first, then narrow (Resolved decision 2).** Write the seed file first, then narrow the plan. A crash after the seed write leaves a harmless re-runnable orphan seed; a crash before it leaves the plan untouched. Never narrow before the carved region is durably written.

**Decidable scope-out trigger (Resolved decision 3).** `convergence_diagnosis.py` carries only `_SEVERITY_RANK = {medium, high, critical}` — there is no "data-loss" grade; none is invented. Scope-out is selected **inside the localized fork** (the single-step case `classify_fork` today always sends to re-split) by a falsifiable condition on data already on `RegionTrend`: the region spins (recurs ≥ `recurrence_min` + no-shrinkage), **and** `region.max_severity` is **≥ high**, **and** the per-run severity trend is **non-decreasing** across the window (the "patches backfire" signature). All three → recommend scope-out for that step; otherwise the localized case stays re-split (over-packed but shrinkable). Re-split and scope-out are the two sub-arms of the localized fork; structural re-seed is unchanged.

**Reconcile reuses vocabulary, not detectors (Resolved decision 4).** `granularity.py` imports `plan_tool.review`, so `review.py` cannot import `granularity` (the cycle CLAUDE.md guards), and the granularity detectors are deterministic plan-structure-only — they never read code. The reconcile arm reuses **only the source-token string literals** (`granularity-split` / `granularity-merge`) and the `Recommendation` shape (duplicating the literal as `STRUCTURAL_SOURCES` already does). The code signal comes from reconcile's own `review.py:heuristic_already_done` (source `"heuristic"`).

**Dedup the code-grounded merge finding (Resolved decision 5).** `reconcile` already surfaces "step already (partially) implemented" as a `source="heuristic"` `heuristic_already_done` hit. The new structural merge/re-ground finding keys on the same signal, so it must not double-report: for a given step set, emit one finding — either annotate the existing heuristic hit with the merge remedy, or suppress the structural finding when a heuristic hit already covers that step set.

**Scope-out source token + bucket (Resolved decision 6).** Introduce an explicit `scope-out` source token. Like every other structural-diagnostic source it stays **out of** `review.py:APPLY_ELIGIBLE_SOURCES` (recommend-only — never reaches `apply_finding` or flips an exit code) and routes through the generic structural `triage_reason`. The existing `granularity-split` / `granularity-merge` / `structural-split` tokens and their exclusion are unchanged.

**Step ordering / no forward-ref command (Resolved decision 7).** The convergence scope-out recommendation renders **prose-only** — it does not print a runnable `plan-tool scope-out …` line — until the executor step lands. Either (preferred) order the executor step before the recommendation renders the command, or have the recommendation gate the command line on the executor's existence.

**Seams reused (verify before extending):** `convergence_diagnosis.py` (`classify_fork`, `RegionTrend.max_severity` + per-run severity trend); `granularity.py` (source-token literals only); `review.py:heuristic_already_done`; `escalate_to_split` (`launcher.py`) as the model for scope-out's gating invariant (`applied` only when safe + `allow_split` + interactive confirm); `plan-tool split` / `plan-tool merge` executors; `annotate`'s seed-emission; `reconcile` (`review.py:review_plan_full`, `render_review_prompt`, `prompts/review.md`) with its recent `creates:` grounding fix (declared files = `files:` ∪ `creates:`).

## References

- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Official reference for frozen dataclasses, field(), and dataclasses.replace() — needed to extend the frozen EscalateResult contract and the Recommendation/RegionTrend shapes the new scope-out source token and remedy model attach to.
- [JSON Lines](https://jsonlines.org/) — The JSONL format spec (one JSON value per line, UTF-8, \n separated) governing the decision-telemetry .jsonl sidecar and the saved completeness/reconcile report history that convergence_diagnosis reads to detect spinning regions.
- [argparse — Parser for command-line options — Python documentation](https://docs.python.org/3/library/argparse.html) — Reference for subparsers and argument wiring, consulted when adding/adjusting the read-only convergence subcommand surface and any scope-out-related CLI prose that gates a runnable command line on the executor's existence.
- [RFC 8259 — The JavaScript Object Notation (JSON) Data Interchange Format](https://www.rfc-editor.org/rfc/rfc8259) — The primary JSON spec each JSONL record must conform to, relevant for safely reading/writing the persisted report subset (recommendations, walk annotations, fingerprints) the diagnostic consumes.
- [PyYAML Documentation](https://pyyaml.org/wiki/PyYAMLDocumentation) — Reference for safe loading/dumping of the YAML frontmatter that is the plan's machine-readable source of truth — touched when narrowing a plan's steps: during scope-out and emitting/parsing the create --from-existing seed.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A **new split/merge algorithm** — reuse `escalate_to_split`, `plan-tool split` / `merge`, `create --from-existing`, and `annotate`'s seed-emission.
- **Auto-mutating structure unattended** — every actuating path stays opt-in + interactive-confirm; the default path spends no Claude and only recommends. The structural re-seed stays human-authored.
- **A programmatic BACKLOG.md writer** — explicitly out (Resolved decision 1); the scope-out destination is a forward-seed, not BACKLOG.
- **In-plan `DEFERRED` disposition for scope-out** — explicitly out (Resolved decision 1); the carved step is removed, not parked.
- **Removing the BUG_BACKLOG reconcile-lane bookkeeping noise** — separate fix.
- **Clone-destruction / clone-lifecycle work itself** — that was the motivating scope-out, already handled by hand; this plan is the general capability.

## Risks

- **False "already implemented → merge" calls** on superficial symbol overlap — reuse `heuristic_already_done` carefully; keep it advisory so it never auto-mutates; dedup against the existing hit (Resolved decision 5).
- **Scope-out partial-failure data loss** — mitigated by seed-first ordering (Resolved decision 2): the carved region is durably written before the plan is narrowed, so a crash leaves a re-runnable orphan seed, never lost work.
- **Vocabulary churn** — the new `scope-out` token must not break the existing `granularity-split` / `granularity-merge` / `structural-split` routing tokens or their `APPLY_ELIGIBLE_SOURCES` exclusion (Resolved decision 6).

## Testing

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

## Acceptance criteria

- `plan-tool convergence` emits a **scope-out / defer** recommendation on a spinning single-step region whose `max_severity ≥ high` and whose severity trend is non-decreasing — as a sub-arm of the localized fork, distinct from re-split (over-packed/shrinkable) and from the structural re-seed. Read-only, advisory, exits 0. No invented "data-loss" severity grade.
- `reconcile` surfaces a **code-grounded** structural-decomposition finding when the current code implies a merge/re-ground (headline: steps already partially implemented), built on `heuristic_already_done`, emitted through the reused `granularity-*` source-token vocabulary, **deduped** against the existing heuristic hit (one finding per cause), advisory and never flipping the exit code.
- The four remedies (split / merge / scope-out / re-seed) read as **one altitude × disposition model** in the docs and recommendation prose; no new split/merge algorithm is introduced.
- A scope-out, when actuated (opt-in + confirm), **emits a `create --from-existing` forward-seed for the carved region and then narrows the plan** (seed-first) — never dropping the carved work, never marking it in-plan `DEFERRED`, never writing a BACKLOG stub. The default path only recommends (prose-only until the executor exists).
- The new `scope-out` source token stays **out of** `APPLY_ELIGIBLE_SOURCES`; existing structural routing tokens and their exclusion are unchanged; the granularity advisor and `escalate_to_split` behave as before.

## Deferred

- **Auto-actuation bridge for `granularity-merge` → `plan-tool merge`** — kept recommend-only; the operator hand-runs `plan-tool merge`. An automatic bridge (the merge analog of `escalate_to_split`) is postponed until the recommend-only signal proves reliable.
- **Auto-routing the convergence scope-out recommendation into the `plan-tool scope-out` executor** — `plan-tool convergence` stays read-only and only renders the runnable command; the operator runs it. Wiring convergence to invoke the executor directly is postponed (keeps the read-only/no-Claude contract intact for now).
- **`create`-side trigger for the scope-out remedy** — the convergence and reconcile arms land here; routing a scope-out recommendation through `create`'s convergence loop follows the deferred create-side `escalate_to_split` trigger.
