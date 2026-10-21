> **Replaced**: this file has been superseded by `docs/implementation-plans/2-decomposition-convergence-loop.md`.
> Preserved here for history; do not edit.

## Overview

Add a read-only command — **`plan-tool convergence <plan>`** — that reads a plan's saved completeness/reconcile report history, detects when the audit/apply loop is **spinning instead of converging**, and prints a recommendation **forked by the failure's shape**: a *localized* over-pack (one step doing too much) → recommend an in-place re-split; a *structural* / cross-step problem (the decomposition itself is wrong) → recommend authoring a fresh `create` seed and re-decomposing. This is the lean v1 — read-only, advisory only: it mutates nothing, writes no files, and spends **zero Claude** (it analyzes report JSON already on disk). It builds on shipped dependencies — **#59 (exhaustion-aware audit sampling)** makes a single audit pass trustworthy so cross-run recurrence means mis-shape rather than undersampling, and the **granularity advisor** emits deterministic `granularity-split` / `granularity-merge` findings into the completeness report history this command reads. #57's unique contribution is the **cross-run** read (recurrence + shrinkage trend across the report-history series, which no single audit sees) and the **re-split-vs-re-seed fork**. (BACKLOG #57.)

## Problem statement

The pipeline converges on content, never on structure. Every convergence loop the tool has — `create --iterate`, `detail --iterate`, `completeness --iterate` — closes over plan/detail **content**. **None closes over step boundaries.** Decomposition is decided once, by `create`, in a single round-trip, at the moment of *least* information in the pipeline (before any detail file exists, before the audit has read code at HEAD), and then frozen.

The audit later *acquires* that information and *detects* boundary problems — purity findings, size findings, a `[BLOCKED]` whose only fix is structural, a branch with no live scenario. But its only repair move is `apply_finding`, which edits **prose**: it cannot delete a concern, move it to another step, drop dead wiring, or re-split. So it patches *around* the mis-decomposition by adding prose, which grows the plan and feeds the next audit more surface — it re-finds the same problem under a new anchor every pass and never converges, all while reporting `no_blocking_findings`/converged and overstating soundness.

Today the only thing that closes this gap is a **human** noticing the non-convergence, diagnosing it, and re-running `create` with a hand-tuned seed (see the "When repeated audit/apply doesn't converge" workflow in `RUNBOOK.md`, and the worked re-seed at `plan-seeds/archive/escalate-structural-findings-to-split-redecomposed.replaced.md`). That human step is the missing pipeline edge: **audit-detects-bad-decomposition → re-decompose.** v1 automates the *detection and recommendation* half of it.

**The non-convergence signature (what the detector keys on)** — all deterministic, all readable from `docs/implementation-plans/plan-details/<slug>/reports/*.json` (anchor slugs are stable across re-audits, so a finding that returns is recognizable):

- **Region recurrence** — the same anchor slug (or the same step id) re-flagged across **N consecutive** report runs without being resolved.
- **No shrinkage** — open medium+ finding count fails to trend down across those runs (mirrors the loop's own `--max-stall-rounds` idea, but *across* invocations rather than within one).
- **Monotone growth** — the plan body / a step's detail grows in size run over run (apply only adds prose), a proxy for "patching, not resolving."
- **A structural `[BLOCKED]`** — any finding the iterate loop returned BLOCKED because the fix needs a new step / detail file.

**The fork (the heart of v1 — the wrong path wastes work)** — classify the recurring region, then recommend the matching repair:

- **Localized over-pack** — recurrence concentrates on a **single step id**, the rest of the plan is quiet → recommend an **in-place re-split**: `plan-tool split <plan> --step N --into "<a>" --into "<b>"` (or interactive `detail --split`). Surgical, 1→2, preserves the other detail files and run state. This is the path the `escalate-structural-findings-to-split` bridge executes.
- **Structural / cross-step** — recurrence **spans multiple steps**, or the findings concern inter-step shape (dependencies, ordering, a dead/inert branch, two control-flow shapes merged) → recommend **authoring a fresh seed and re-decomposing**: `create --from-existing <seed> --iterate`. A 1→2 split can't fix this; it's N-way.

The classifier is deterministic from the report data. When the signal is genuinely ambiguous, v1 **says so and recommends the more cautious re-seed** (mirroring the `direct`-vs-`plan-tool` heuristic's "when unsure, author a plan") rather than guessing a split. #57 should *consume* the granularity advisor's `granularity-split` findings as its strongest localized over-pack signal rather than re-deriving any static per-step check — that detector exists and is owned by the granularity advisor.

## Architecture

**One module + a thin CLI seam.**

- **`plan_tool/convergence_diagnosis.py`** (orchestrator leaf): read report history → detect signature → classify localized vs. structural → render the forked recommendation. Pure logic, no `invoker` (v1 spends no Claude). Keep it a leaf below the CLI; lazy-import report parsing if it would close a cycle.
- **`plan_tool/cli/convergence_cmd.py`** (thin handler, registered in `parser.py`).

**Read the report history.** Glob `docs/implementation-plans/plan-details/<slug>/reports/*-completeness.json` (and `*-reconcile.json` if present), ordered by timestamp. For each run collect: open findings with their anchor slug, associated step id, severity, and the artifact byte-size where the report carries it. Build a per-anchor / per-step recurrence-and-severity trend across runs.

**Output — the diagnosis.** Print to stdout: a one-line verdict (`converging` / `spinning`), the recurring region(s) with their run-count and severity trend, and the matched recommendation with the **exact command pre-filled** (copy-paste), e.g.:

```
spinning — step 5 re-flagged in 4 of the last 4 audits, no shrinkage
  shape: localized over-pack (recurrence on a single step)
  → plan-tool split escalate-structural-findings-to-split --step 5 \
        --into "<first concern>" --into "<second concern>"
```

or, for the cross-step shape:

```
spinning — findings span steps 4,5,7; 2 reference inter-step ordering
  shape: structural (the decomposition itself is wrong)
  → re-decompose: author a fresh seed and run
        create --from-existing <seed> --iterate
```

Preserve the **exit-code convention**: a completed diagnosis exits 0 regardless of verdict (no `--fail-on-findings` in v1 — see Deferred).

**Open question — standalone command vs. completeness-report section.** v1 assumes a standalone `plan-tool convergence <plan>`. But the signature is most useful surfaced *exactly when it trips* — i.e. as a short "Convergence diagnosis" section the completeness report prints after K stalled runs. The report-JSON history reader and the recurrence logic are the same either way. Resolve during `create`/`detail`: standalone reads better as an on-demand inspector; a report section pushes the signal to the operator without their asking. Lean standalone for v1 (smaller surface, no completeness coupling), with the report section as the first Deferred follow-up.

## Out of scope

- **Auto-executing any repair.** v1 diagnoses and recommends; it never splits a step, edits a plan, or authors a seed. (Auto-split behind an opt-in is Deferred and must obey the never-mutate-structure-unattended invariant the `escalate_to_split` bridge already uses.)
- **Re-running the audit.** v1 reads *saved* reports; it spends no Claude and triggers no new audit.
- **A new code checker or a new finding source.** This analyzes the *history of findings the audit already produced*; it adds no new audit of plan or code.

## Risks

- **False "spinning" on a plan that's legitimately mid-authoring.** Severity: UX. A plan under active iteration naturally re-flags a region for a run or two. Mitigation: require N≥3 consecutive no-shrinkage runs before declaring spinning (tunable), matching the RUNBOOK rule of thumb.
- **Mis-forked recommendation** (recommend re-split for a spine problem, or re-seed for a one-step over-pack). Severity: wasted work. Mitigation: on an ambiguous classification, default to the cautious re-seed and *say it's ambiguous* — recommend-only keeps the operator in the loop.
- **Report-schema drift.** Severity: low. The detector reads completeness/reconcile JSON; a schema change breaks it. Mitigation: read defensively (tolerate missing fields), and pin the fields it depends on with a fixture test.
- **Import-cycle pressure.** Mitigation: keep `convergence_diagnosis.py` a leaf below the CLI; lazy-import report parsing if needed (codebase precedent).

## Acceptance criteria

- `plan-tool convergence <plan>` reads the saved completeness report history and prints a `converging` / `spinning` verdict with the recurring region(s) and their cross-run severity trend.
- On `spinning`, it classifies the shape (localized vs. structural) from the report data and prints the matched recommendation with an exact, copy-pasteable command (`plan-tool split …` for localized, `create --from-existing …` for structural).
- An ambiguous classification recommends the cautious re-seed and labels itself ambiguous (never a confident wrong split).
- The command spends **zero Claude calls** and writes no files (read-only).
- Completion exits 0 regardless of verdict (exit-code convention).
- `convergence_diagnosis.py` adds no import cycle.

## Deferred

- **Surface the diagnosis as a "Convergence diagnosis" section of the completeness report** after K stalled runs (the open-question follow-up), so it pushes to the operator without a separate command.
- **Opt-in auto-execution of the *localized* split** — wire the recommendation into the `escalate_to_split` bridge (from `escalate-structural-findings-to-split`) behind an explicit flag + TTY gate, so an operator can accept the re-split in place. Never the structural/re-seed path (that stays human-authored), and never unattended.
- **`--fail-on-findings`-style CI gate** — flip rc non-zero when a plan has been spinning for ≥N runs, so CI can block "this plan isn't converging" before more effort is poured in.
- **Cross-plan sweep** — run the diagnosis over every registered plan and report which ones are spinning (a backlog-health view).
- **Claude-assisted classification** for genuinely ambiguous localized-vs-structural cases — only if the deterministic classifier proves insufficient in practice.
