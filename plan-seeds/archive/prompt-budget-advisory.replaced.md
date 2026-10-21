> **Replaced**: this file has been superseded by `docs/implementation-plans/2-prompt-budget-advisory.md`.
> Preserved here for history; do not edit.

# Plan seed: pre-send prompt budget advisory (bytes vs context window, structural remedies)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing plan-seeds/prompt-budget-advisory.md --iterate -y
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source: BACKLOG.md #95** ("Pre-send prompt budget advisory"), grounding
> facet of the Quality/accuracy lens. Sibling of #97 (symbol-aware excerpts,
> already authored as `2-symbol-aware-prompt-excerpts`). **This plan MUST update
> BACKLOG.md #95 when the work ships** — remove the entry, or mark it
> plan-authored with any deferred remainder split out (see the final step and
> acceptance criteria).

---

## Overview

Add a **pre-send, advisory-only** prompt-budget check. After each
`render_*_prompt` assembles a prompt and *before* the invoker fires, estimate the
total prompt size against a conservative model context-window budget and emit a
warning when headroom is tight — with a per-block breakdown (which sections
dominate) and runnable structural remedies (`--step`, distill/split, `scope-out`,
lower audit `--max-passes`, etc.). Never hard-block the invoke. Same discipline as
the `convergence` diagnostic and today's post-failure `CONTEXT_OVERFLOW` hints:
**surface unconditionally, mutate nothing.**

## Problem statement

The tool already classifies `CONTEXT_OVERFLOW` *after* a call fails
(`claude_errors.py`, propagated through `backend.py` / `shell.py` / `launcher.py`)
and caps individual chunks (4 KB/file embed, lessons-file cap, fetch caps), but
there is **no pre-send check that the *assembled* prompt fits**. Consequences:

- Operators discover overflow only **after burning a call** — the failure is
  reactive, at the point where a structural remedy is most expensive to reach.
- `prompt_bytes` is already computed and logged on many paths (`shell.py`,
  `run_log.py`, `backend.py:prompt_bytes`, `launcher._streaming_prompt_bytes`),
  but it is **accounting, not a safeguard** — nothing compares it to a budget.
- `model_specs.py` already carries `context_window` (from models.dev, line ~70 /
  ~151) for synthesized backends but **does not use it for budgeting**.

## Design

### New stdlib-only leaf `plan_tool/prompt_budget.py`

Cycle-free, first-party-import-free where possible (telemetry-style leaf posture
so any module can call it). Public surface:

- `estimate_prompt_budget(total_bytes, *, context_window=None, blocks=None) ->
  PromptBudget` — conservative token estimate (`ceil(bytes / 3.5)`), headroom
  ratio against `context_window` (default a ~200K-class window when unknown), an
  advisory level (`ok` / `warn` / `high`), and the optional per-block breakdown.
- `maybe_warn_prompt_budget(...)` — formats and emits the advisory (to stderr,
  `color_enabled`-gated) when level is `warn`/`high`; returns the `PromptBudget`
  so callers can also record telemetry. No-op / returns `ok` silently otherwise.

Advisory thresholds (start conservative to avoid fatigue): **`warn`** below ~40%
headroom, **`high`** below ~15%. The warning body lists the dominant blocks and
the runnable structural remedies relevant to the calling surface.

### Orchestrator hooks (named-block breakdown where available)

Wire the check at the assembly points, passing named blocks so the breakdown is
useful:

- `detail.py:generate_detail` (draft + `render_detail_prompt` /
  `render_detail_quality_prompt`).
- `create.py:create_plan` (distill / steps / synthesis phases).
- `review.py:audit_plan_until_stable` (+ `render_plan_audit_prompt`).
- `launcher.py:run_step` (the streaming `run` path; reuse
  `_streaming_prompt_bytes`).

**Generic backstop** in `shell.py:claude_invoke` (total bytes only) so a call
that doesn't pass named blocks still gets the overflow-headroom check. Do not
double-warn: if a caller already ran the named-block check, the backstop should
not re-emit for the same invoke.

### Dry-run visibility

`detail --dry-run` (and any sibling dry-run path that renders without invoking)
prints the budget breakdown so an operator can inspect headroom before spending a
call.

### #72 telemetry extension

Add a `record_prompt_budget` recorder to `telemetry.py` (mirroring the existing
`record_*` seams) capturing `phase`, `total_bytes`, `advisory`, and optional
`blocks`. Best-effort / swallow-all-errors like the rest of `telemetry.py`. This
lets a later analysis pass link the advisory to actual `CONTEXT_OVERFLOW`
outcomes ("warn at 85% → overflowed 12% of the time on detail") for threshold
tuning. Document the event shape in `DATA_CONTRACT.md` if it stabilizes (the
drift guard covers it).

## Step decomposition (single-concern steps — BACKLOG #58)

Propose **pure, single-concern steps**. Suggested shape:

- **Leaf step** — `plan_tool/prompt_budget.py`: `estimate_prompt_budget` +
  `maybe_warn_prompt_budget` + `PromptBudget` + advisory-level logic + the
  conservative token/headroom heuristic. Pure, fully unit-tested in isolation.
- **Telemetry step** — `record_prompt_budget` in `telemetry.py` + the schema
  note in `DATA_CONTRACT.md` if stable. Depends on the leaf's `PromptBudget`.
- **Wiring step(s)** — thread `maybe_warn_prompt_budget` into `generate_detail`,
  `create_plan`, `audit_plan_until_stable`, `run_step`, and the
  `shell.claude_invoke` backstop, passing named blocks where available. Keep the
  backstop non-duplicating.
- **Dry-run step** — surface the breakdown on `detail --dry-run`.
- **Docs/backlog step (final)** — document the advisory in `RUNBOOK.md`, and
  **reconcile BACKLOG.md #95** (remove or mark plan-authored with any deferred
  remainder). Update `docs/cli/` if a flag/surface changed.

## Out of scope

- **Tokenizer dependency** — the estimate stays a byte/char heuristic, no new
  dependency.
- **Hard pre-send refusal** — never block the invoke; advisory only.
- **New truncation caps / raising the 4 KB embed** — that is #97
  (symbol-aware excerpts); this plan only *measures and warns*, it does not
  change what gets embedded.
- **Capping `run`'s uncapped full-detail embed** — noted as a possible follow-up
  in #95; file it to `BACKLOG.md` if the advisory surfaces it often, do not fold
  it in here.

## Risks

- **False-positive warnings** if the byte/token heuristic is too aggressive.
  Severity: medium (advisory fatigue → operators ignore it). Mitigation: start
  conservative (`warn` below ~40% headroom, `high` below ~15%); make thresholds
  named constants so #72 telemetry can retune them later.
- **Advisory fatigue from an over-low `ok` threshold.** Severity: medium.
  Mitigation: only `warn`/`high` emit; `ok` is silent.
- **Breakdown only as good as the blocks passed.** Severity: low. Mitigation:
  the generic backstop still gives a total-bytes headroom check when named
  blocks are absent; wiring steps pass blocks where the assembly is structured.
- **Double-warning** (named-block hook + backstop for one invoke). Severity: low.
  Mitigation: the backstop suppresses when a named-block check already ran.

## Acceptance criteria

- A new `plan_tool/prompt_budget.py` leaf exposes `estimate_prompt_budget` and
  `maybe_warn_prompt_budget`, is import-cycle-free, and is unit-tested for the
  `ok` / `warn` / `high` boundaries and the token/headroom heuristic.
- `generate_detail`, `create_plan`, `audit_plan_until_stable`, and `run_step`
  emit the advisory (with a per-block breakdown) when headroom is tight; the
  `shell.claude_invoke` backstop covers callers that pass no blocks, without
  double-warning.
- The advisory **never changes rc** and **never blocks the invoke** (exit-code
  convention; surface-unconditionally-mutate-nothing discipline). Warnings are
  `color_enabled`-gated (plain on a pipe/non-TTY).
- `detail --dry-run` prints the budget breakdown without invoking.
- `telemetry.record_prompt_budget` records `phase` / `total_bytes` / `advisory`
  (+ optional `blocks`), swallows all errors, and — if the event shape is stable
  — is documented in `DATA_CONTRACT.md` and passes the drift guard.
- **BACKLOG.md #95 is reconciled** (removed, or marked plan-authored with any
  deferred remainder split out) as the plan's final step; `RUNBOOK.md` documents
  the advisory.

## Deferred

- Outcome-linkage of the advisory to actual `CONTEXT_OVERFLOW` failures and a
  recommend-tuning surface — belongs with #72 phases 2–3, not here.
- Per-model window resolution beyond `model_specs.context_window` (e.g. a
  richer per-`--backend` catalog lookup).
- Capping `run`'s full-detail embed (route to `BACKLOG.md` if it recurs).
- Symbol-aware / budget-bounded *excerpting* of embedded files — that is #97.

---

## Iterate recipe (default; substitute slug `prompt-budget-advisory`)

```bash
# Phase 1: author the plan (plan canonical).
.agents/plan-tool.sh create prompt-budget-advisory --iterate -y \
  --output-dir docs/implementation-plans \
  --from-existing plan-seeds/prompt-budget-advisory.md

# Phase 1.5: draft + converge per-step detail files (plan canonical).
.agents/plan-tool.sh detail prompt-budget-advisory --iterate -y

# Phase 2: plan/detail coherence (internal — body-fill + concept-completeness).
.agents/plan-tool.sh completeness prompt-budget-advisory --iterate -y

# Phase 2.5: code-vs-detail reconcile (code canonical). Per step; the leaf +
# telemetry recorder are net-new files (skippable there), but the wiring steps
# touch existing orchestrators — reconcile those.
.agents/plan-tool.sh detail prompt-budget-advisory --reconcile --step N -y

# Phase 3: execute the step (plan canonical). Per step. Pass --commit across a
# multi-step run.
.agents/plan-tool.sh run prompt-budget-advisory -y --step N --commit

# Phase 3b: optional post-execute reconcile loop (skip for mechanical steps).
.agents/plan-tool.sh run prompt-budget-advisory --mode reconcile --iterate -y --step N

# Phase 4: post-execution audit against implemented code (plan canonical).
.agents/plan-tool.sh completeness prompt-budget-advisory --iterate -y
```
