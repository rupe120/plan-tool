> **Replaced**: this file was superseded by `2-escalate-recurring-seams.md`, itself
> archived 2026-08-02 to `docs/implementation-plans/archive/`. The live successor is
> BACKLOG #158's re-seed pair (`plan-seeds/impact-recurrence-01-classifier.md`, `-02-loop-stop.md`).
> Preserved here for history; do not edit.

# Plan seed: route a recurring high-impact seam to a structural verdict in the live loop (reuse the existing history diagnostic)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing docs/implementation-plans/plan-seeds/impact-convergence-02a-recurring-seam-escalation.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source:** `BACKLOG.md` **#153** — "Route a recurring high-impact seam to a
> structural verdict instead of another audit pass (feed report history into the
> stop decision)." Step 2 of the impact-convergence arc **#152 → {#153, #154} →
> #152 demote**. **Depends on #152's augment slice landing first** (so
> "high-impact recurrence" is a defined concept). This seed's final docs/status
> step must update `BACKLOG.md` #153 (mark shipped/removed) once the work lands.

## Problem statement

Each completeness/iterate pass decides continuation from the **current** pass's
findings (`should_continue` + the `max_stall_rounds` count-shrink backstop). A
high-impact **seam** finding that recurs across many passes — the empirical
`security-check-command` pattern, where the same `--step`/`--reconcile` contract
seam surfaced on passes 2, 11, and 13 of 13 — is not a result to re-audit; it is
the signal that the **decomposition is seam-dense** and the remedy is
**re-split / scope-out**, not another audit round. The waste on that plan was an
**open audit→apply→audit loop re-discovering the same un-applied seam** (#85
persists conceptual findings unapplied) with no escalation to the structural
remedy the recurrence implies.

## Ground truth (confirmed at HEAD)

- `plan_tool/convergence_diagnosis.py` **already** reads cross-run report
  history and classifies the fork — reuse it, do not re-derive:
  - `load_report_history(plan_path)` (line ~174)
  - `diagnose_convergence(...)` (line ~769)
  - `classify_fork(diagnosis)` (line ~958) → `FORK_LOCALIZED` /
    `FORK_SCOPE_OUT` / `FORK_STRUCTURAL`
- Today this runs **only** as the after-the-fact `plan-tool convergence`
  command (`plan_tool/cli/convergence_cmd.py`) — the **live** iterate loop never
  consults it.
- The live loop's stop decision is `plan_tool/convergence.py:should_continue`
  (reason codes are stable strings the test suite asserts on) plus the
  `has_blocking_findings` construction in `cli/completeness_cmd.py` /
  `cli/reconcile.py`.
- The structural remedies keep their own `--apply`/TTY-confirm gates
  (`scope_out.py:scope_out_step`, `launcher.py:escalate_to_split`); the loop's
  job here is to **recommend** the carve, not actuate it.

## Resolved design decisions

1. **Reuse `convergence_diagnosis`'s history reader + classifier — do NOT fork a
   second recurrence heuristic.** The live loop calls the existing
   `load_report_history` / `diagnose_convergence` / `classify_fork` path; any
   tuning of *what counts as recurrence* happens in that one module.
2. **Add one new `should_continue` reason code** (e.g. `"structural"`) for the
   case: an `impact=high` finding recurring `≥N` passes with no count-shrink.
   When it fires, the loop **stops** and prints a **recommend-only**
   `plan-tool split …` / `plan-tool scope-out …` pointer (per the fork class),
   rather than continuing to the pass cap.
3. **Mutation stays gated.** The loop never auto-narrows; it surfaces the
   structural recommendation and the operator runs the gated actuator. No new
   auto-apply path.
4. **"High-impact recurrence" reuses #152's `is_blocking_impact` notion of
   high-impact** — this is why #152 augment is a prerequisite.

## Seams to reuse (verified at HEAD)

- `plan_tool/convergence_diagnosis.py` — the three reader/classifier functions
  above (the single source of recurrence logic).
- `plan_tool/convergence.py:should_continue` — add the reason code here; keep
  every existing reason string intact.
- `plan_tool/cli/completeness_cmd.py` / `plan_tool/cli/reconcile.py` — the live
  loop drivers where the new stop is consulted and the recommend-only pointer is
  printed.
- The existing `Next steps:` rendering convention — pointers must be
  `plan-tool …` commands only (never `/code-review`), per CLAUDE.md.

## Scope of work (indicative — let create decompose)

1. Wire the existing `convergence_diagnosis` read-only path into the live loop
   at the stop-decision point.
2. The new `should_continue` reason code + the recommend-only structural pointer
   rendering.
3. Tests: a synthetic multi-pass history with a recurring high-impact seam stops
   with the structural reason + prints the recommend-only pointer; a
   non-recurring high-impact finding still iterates normally; mutation is never
   auto-applied.
4. Docs/status: update `BACKLOG.md` #153; reconcile the recurrence-decay note
   with #116 (below).

## Non-goals / out of scope (guardrails — do not cross)

> Inherits BACKLOG **#153**'s **scope contract** (Outcome / In scope / Out of
> scope / Allowed behavior changes / Allowed reorganization / Verification /
> Stop-defer) — the section below elaborates that boundary and introduces no
> new scope.

- **A second recurrence/spin heuristic.** Do not compute recurrence anywhere
  but `convergence_diagnosis.py`. If its classifier needs tuning, that overlaps
  **#116** (spin-window decay + fork classifier) and **#129** — reconcile with
  those items rather than duplicating logic; do not silently re-implement.
- **Re-keying the stop gate on impact (#152).** That is the prerequisite, not
  this plan's work. Assume `is_blocking_impact` exists.
- **Impact calibration (#154).** Do not build drift correlation or auto-tuning.
- **Auto-narrowing / auto-splitting.** The loop recommends only; the
  `scope_out` / `escalate_to_split` confirm gates stay the sole mutation path.
- **Changing `convergence_diagnosis`'s classification semantics** beyond what a
  live caller strictly needs — its `plan-tool convergence` command behavior
  must not regress.

## Acceptance criteria (plan-level)

- The live iterate loop consults report history via the existing
  `convergence_diagnosis` functions (no new recurrence heuristic).
- On an `impact=high` finding recurring `≥N` passes without count-shrink, the
  loop stops with a **structural** reason code and prints a recommend-only
  `plan-tool split` / `plan-tool scope-out` pointer — it does not continue to
  the cap and does not mutate structure.
- A non-recurring high-impact finding still iterates normally; existing
  `should_continue` reason strings are unchanged.
- The `plan-tool convergence` command's own behavior does not regress.
- `BACKLOG.md` #153 is marked shipped/removed; overlap with #116/#129 is
  reconciled in one place.
