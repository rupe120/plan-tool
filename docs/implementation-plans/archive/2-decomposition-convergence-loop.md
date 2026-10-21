---
title: Decomposition Convergence Loop
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add convergence_diagnosis report-history reader and normalized per-run model
  creates:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  - tests/fixtures/convergence/sample-report-history.json
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/01-convergence-diagnosis-report-history.md
  status: current
- id: 2
  title: Add non-convergence signature detector (recurrence + no-shrinkage → converging/spinning)
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/02-non-convergence-signature-detector.md
- id: 3
  title: Add localized-vs-structural fork classifier and forked copy-paste recommendation
    renderer
  files:
  - plan_tool/convergence_diagnosis.py
  - tests/test_convergence_diagnosis.py
  complexity: medium
  change_type: feature
  depends_on:
  - 2
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/03-localized-vs-structural-fork-classifier.md
- id: 4
  title: Wire `plan-tool convergence <plan>` CLI seam (handler, registration, generated
    reference)
  files:
  - plan_tool/cli/app.py
  - plan_tool/cli/parser.py
  - plan_tool/cli/__init__.py
  - docs/cli/README.md
  creates:
  - plan_tool/cli/convergence_cmd.py
  - docs/cli/convergence.md
  - tests/cli/test_convergence_cmd.py
  complexity: medium
  change_type: feature
  depends_on:
  - 3
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/04-wire-plan-tool-convergence-plan-cli.md
- id: 5
  title: 'Document the convergence diagnostic (RUNBOOK workflow, CLAUDE architecture,
    BACKLOG #57)'
  files:
  - RUNBOOK.md
  - CLAUDE.md
  - BACKLOG.md
  complexity: low
  change_type: non-code
  depends_on:
  - 4
  detail: docs/implementation-plans/plan-details/decomposition-convergence-loop/05-document-convergence-diagnostic-runbook.md
---
# Decomposition Convergence Loop

## Overview

Add a read-only command — **`plan-tool convergence <plan>`** — that reads a plan's saved completeness/reconcile report history, detects when the audit/apply loop is **spinning instead of converging**, and prints a recommendation **forked by the failure's shape**: a *localized* over-pack (one step doing too much) → recommend an in-place re-split; a *structural* / cross-step problem (the decomposition itself is wrong) → recommend authoring a fresh `create` seed and re-decomposing. This is the lean v1 — read-only, advisory only: it mutates nothing, writes no files, and spends **zero Claude** (it analyzes report JSON already on disk). It builds on shipped dependencies — **#59 (exhaustion-aware audit sampling)** makes a single audit pass trustworthy so cross-run recurrence means mis-shape rather than undersampling, and the **granularity advisor** emits deterministic `granularity-split` / `granularity-merge` findings (though in v1 those findings never reach the saved report JSON this command reads — no step persists smell recs into the sidecar, so localized detection relies on step-id recurrence concentration, not on consuming `granularity-split`). #57's unique contribution is the **cross-run** read (recurrence + shrinkage trend across the report-history series, which no single audit sees) and the **re-split-vs-re-seed fork**. (BACKLOG #57.)

## Problem statement

The pipeline converges on content, never on structure. Every convergence loop the tool has — `create --iterate`, `detail --iterate`, `completeness --iterate` — closes over plan/detail **content**. **None closes over step boundaries.** Decomposition is decided once, by `create`, in a single round-trip, at the moment of *least* information in the pipeline (before any detail file exists, before the audit has read code at HEAD), and then frozen.

The audit later *acquires* that information and *detects* boundary problems — purity findings, size findings, a `[BLOCKED]` whose only fix is structural, a branch with no live scenario. But its only repair move is `apply_finding`, which edits **prose**: it cannot delete a concern, move it to another step, drop dead wiring, or re-split. So it patches *around* the mis-decomposition by adding prose, which grows the plan and feeds the next audit more surface — it re-finds the same problem under a new anchor every pass and never converges, all while reporting `no_blocking_findings`/converged and overstating soundness.

Today the only thing that closes this gap is a **human** noticing the non-convergence, diagnosing it, and re-running `create` with a hand-tuned seed (see the "When repeated audit/apply doesn't converge" workflow in `RUNBOOK.md`, and the worked re-seed at `plan-seeds/archive/escalate-structural-findings-to-split-redecomposed.replaced.md`). That human step is the missing pipeline edge: **audit-detects-bad-decomposition → re-decompose.** v1 automates the *detection and recommendation* half of it.

**The non-convergence signature (what the detector keys on)** — all deterministic, all readable from `docs/implementation-plans/plan-details/<slug>/reports/*.json` (anchor slugs are *encouraged* to be stable across re-audits, not guaranteed — the "re-use its exact anchor-slug" feedback at `review.py:~4036` is intra-invocation, across one audit's sampling rounds, with no cross-invocation mechanism feeding a prior report's slugs into the next run's prompt, so the same conceptual gap can be re-slugged run-over-run):

- **Region recurrence** — the same anchor slug (or, when the slug drifts run-over-run, the same step id, falling back to title-similarity) re-flagged across the trailing window without being resolved. Because slug stability across separate invocations is only encouraged, recurrence must not key on the anchor slug alone: match a recurring region by `(anchor || step_id || normalized-title-similarity)` so a re-slugged but identical gap still breaks no streak. Because the underlying completeness audit is a *sampled* Claude pass, one run that fails to re-surface a persistent boundary problem must not zero the streak: use an **M-of-N within the trailing window** rule (the region recurs in at least M of the last N runs) rather than strict-consecutive, so a single missed run is tolerated and the verdict doesn't flip to `converging` on exactly the spinning plan the command targets.
- **No shrinkage** — open medium+ finding count fails to trend down across those runs (mirrors the loop's own `--max-stall-rounds` idea, but *across* invocations rather than within one).
- **Monotone growth** — the saved report's markdown (`report_md`) grows in size run over run, a proxy for "patching, not resolving" (apply only adds prose, so each pass re-finds the same region under more surface). Plan/detail-body growth is *not* observable from saved reports — the completeness/reconcile JSON carries no plan or detail byte-size — so the detector measures the report-markdown length the reports actually persist, not the plan/detail bundle.
- **A structural `[BLOCKED]`** — any finding the iterate loop returned BLOCKED because the fix needs a new step / detail file.

**How the report history accrues (what the N-run window is counting).** The signature keys on a trailing window of N≥3 runs, so the threshold must be calibrated to how sidecars actually land on disk — and they land sparsely. `completeness_report.py: write_completeness_report` writes **one** sidecar per `completeness` *invocation* (after the mandated `--iterate` loop converges, not per iterate round), and `completeness_phases.py` **skips** the write (`skip_sidecar_write`) when an audit is reused against an unchanged plan. Two consequences: (1) a plan spinning *within* a single iterate invocation collapses to one report — intra-invocation rounds are invisible to this detector — and (2) re-running on an unchanged plan adds no new report. So the N-run window is **N distinct `completeness` invocations across which the plan changed**, not N iterate rounds and not N raw re-runs; it accrues over the operator's repeated author/audit cycles. The window is therefore deliberately small (N≥3) and the M-of-N rule above tolerates the gaps this cadence produces; a richer per-round-sidecar cadence that would densify the series is out of v1 scope (a follow-up, since it requires the upstream write path to persist per-round, not per-invocation).

**Excluded from the recurrence/no-shrinkage signal — deferred-by-design `plan-completeness` advisories.** The `plan-completeness` conceptual source is special-cased in `completeness_report.py:_deferred_kind` to `advisory-conceptual` ("reported, not auto-applied"), and the iterate loop still excludes it (`cli/completeness_cmd.py`). These advisories are persisted into every report's `recommendations` and re-emitted by every fresh audit by design, so a legitimately-converged plan that retains a stable conceptual advisory would otherwise recur across all N runs and read as `spinning`. The detector therefore filters the `plan-completeness` advisory-conceptual source out of the recurrence/no-shrinkage count (or buckets it separately as deferred-by-design), so a deferred-by-design advisory never drives the verdict.

**The fork (the heart of v1 — the wrong path wastes work)** — classify the recurring region, then recommend the matching repair:

- **Localized over-pack** — recurrence concentrates on a **single step id**, the rest of the plan is quiet → recommend an **in-place re-split**: `plan-tool split <plan> --step N --into "<a>" --into "<b>"` (or interactive `detail --split`). Surgical, 1→2, preserves the other detail files and run state. This is the path the `escalate-structural-findings-to-split` bridge executes.
- **Structural / cross-step** — recurrence **spans multiple steps**, or the findings concern inter-step shape (dependencies, ordering, a dead/inert branch, two control-flow shapes merged) → recommend **authoring a fresh seed and re-decomposing**: `create --from-existing <seed> --iterate`. A 1→2 split can't fix this; it's N-way.

The classifier is deterministic from the report data. When the signal is genuinely ambiguous, v1 **says so and recommends the more cautious re-seed** (mirroring the `direct`-vs-`plan-tool` heuristic's "when unsure, author a plan") rather than guessing a split. In v1 the granularity advisor's `granularity-split` consumption is **inert** — no step persists smell recs into the report sidecar, so those findings never reach the saved JSON this command reads — and localized detection relies on **step-id recurrence concentration** rather than the advisor's signal. (Consuming `granularity-split` directly becomes possible only once upstream completeness persistence carries smell recs into the sidecar; until then the detector owns the localized signal via recurrence.)

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

Preserve the **exit-code convention**: a completed diagnosis exits 0 regardless of verdict by default. v1 ships a per-invocation `--fail-on-findings` flag (default off) that flips rc to 1 on a `spinning` verdict, mirroring the convention's opt-in escape hatch; a richer ≥N-runs CI policy is Deferred.

**Open question — standalone command vs. completeness-report section.** v1 assumes a standalone `plan-tool convergence <plan>`. But the signature is most useful surfaced *exactly when it trips* — i.e. as a short "Convergence diagnosis" section the completeness report prints after K stalled runs. The report-JSON history reader and the recurrence logic are the same either way. Resolve during `create`/`detail`: standalone reads better as an on-demand inspector; a report section pushes the signal to the operator without their asking. Lean standalone for v1 (smaller surface, no completeness coupling), with the report section as the first Deferred follow-up.

## References

- [pathlib — Object-oriented filesystem paths — Python documentation](https://docs.python.org/3/library/pathlib.html) — Authoritative reference for Path.glob/rglob semantics (recursive patterns, unordered results, case sensitivity) needed to glob the per-slug reports/*.json history and sort it by timestamp.
- [glob — Unix style pathname pattern expansion — Python documentation](https://docs.python.org/3/library/glob.html) — Defines the wildcard pattern grammar (*, **, fnmatch rules) shared by pathlib, relevant when matching *-completeness.json / *-reconcile.json report files defensively.
- [json — JSON encoder and decoder — Python documentation](https://docs.python.org/3/library/json.html) — Primary reference for json.load/loads and decode-error handling, used to parse the saved completeness/reconcile report JSON while tolerating missing fields and schema drift.
- [argparse — Parser for command-line options, arguments and subcommands — Python documentation](https://docs.python.org/3/library/argparse.html) — Covers add_subparsers and set_defaults for wiring the new read-only `convergence` subcommand into parser.py as a thin CLI handler.
- [dataclasses — Data Classes — Python documentation](https://docs.python.org/3/library/dataclasses.html) — Reference for declaring the per-anchor/per-step recurrence-and-severity trend records the diagnosis module builds across report runs.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- **Auto-executing any repair.** v1 diagnoses and recommends; it never splits a step, edits a plan, or authors a seed. (Auto-split behind an opt-in is Deferred and must obey the never-mutate-structure-unattended invariant the `escalate_to_split` bridge already uses.)
- **Re-running the audit.** v1 reads *saved* reports; it spends no Claude and triggers no new audit.
- **A new code checker or a new finding source.** This analyzes the *history of findings the audit already produced*; it adds no new audit of plan or code.

## Risks

- **False "spinning" on a plan that's legitimately mid-authoring.** Severity: UX. A plan under active iteration naturally re-flags a region for a run or two. Mitigation: require N≥3 consecutive no-shrinkage runs before declaring spinning (tunable), matching the RUNBOOK rule of thumb.
- **Mis-forked recommendation** (recommend re-split for a spine problem, or re-seed for a one-step over-pack). Severity: wasted work. Mitigation: on an ambiguous classification, default to the cautious re-seed and *say it's ambiguous* — recommend-only keeps the operator in the loop.
- **Report-schema drift.** Severity: low. The detector reads completeness/reconcile JSON; a schema change breaks it. Mitigation: read defensively (tolerate missing fields), and pin the fields it depends on with a fixture test.
- **Import-cycle pressure.** Mitigation: keep `convergence_diagnosis.py` a leaf below the CLI; lazy-import report parsing if needed (codebase precedent).

## Testing

- Unit test `convergence_diagnosis.py` against captured completeness/reconcile report-history JSON fixtures: a spinning series (same anchor slug re-flagged across N≥3 consecutive runs with no shrinkage) yields a `spinning` verdict; a series whose open medium+ finding count trends down yields `converging`.
- Unit test the localized-vs-structural classifier: recurrence concentrated on a single step id → localized over-pack recommending the exact `plan-tool split …` command; recurrence spanning multiple steps (or inter-step shape findings) → structural recommending `create --from-existing … --iterate`; a genuinely ambiguous signal → cautious re-seed labeled ambiguous (never a confident wrong split).
- Fixture test pinning the completeness/reconcile JSON fields the detector depends on, so report-schema drift is caught (per the Risks mitigation); read defensively so missing fields don't crash.
- INTEGRATION test driving `plan-tool convergence <plan>` through the CLI entry point, asserting it exits 0 regardless of verdict and spends zero Claude invocations (assert no invoker is constructed/called).

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — unit tests added with the implementation; green before completion.
- step 2 (feature) — unit tests added with the implementation; green before completion.
- step 3 (feature) — unit tests added with the implementation; green before completion.
- step 4 (feature) — unit tests added with the implementation; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts; no test-ordering directive.

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
- **≥N-runs CI policy** — a persistent "spinning for ≥N runs" gate (beyond v1's per-invocation `--fail-on-findings`, which flips rc on a single `spinning` verdict), so CI can block "this plan isn't converging" before more effort is poured in.
- **Cross-plan sweep** — run the diagnosis over every registered plan and report which ones are spinning (a backlog-health view).
- **Claude-assisted classification** for genuinely ambiguous localized-vs-structural cases — only if the deterministic classifier proves insufficient in practice.
