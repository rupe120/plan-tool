> **Replaced**: this file has been superseded by `docs/implementation-plans/2-calibrate-impact-drift.md`.
> Preserved here for history; do not edit.

# Plan seed: calibrate the `impact` axis against observed `reconcile-code` drift (read-only; unblocks #152's demote form)

This file is a `plan-tool create` input. Use it via:

```
plan-tool create --from-existing docs/implementation-plans/plan-seeds/impact-convergence-02b-drift-calibration.md --iterate
```

It is **not** itself a plan — `plan-tool create` consumes the prose below and
proposes a step decomposition; the author then runs `plan-tool detail` per step.

> **Source:** `BACKLOG.md` **#154** — "Calibrate the `impact` axis against
> observed `reconcile-code` drift (close the audit→outcome loop; unblocks #152's
> demote form)." The **keystone** of the impact-convergence arc **#152 → {#153,
> #154} → #152 demote** — not the start (#152 augment ships without it), but
> **#152's demote form is blocked on this**. This seed's final docs/status step
> must update `BACKLOG.md` #154 (mark shipped/removed) and note in #152 that the
> demote form is now unblocked.

## Problem statement

`impact` is today **self-graded** by the same Claude pass that raises the
finding — the audit grades its own downstream cost, introspectively, with no
ground truth. That is tolerable while impact only gates *applies* and #152's
*augment* (monotonic) blocking, but keying *stop* on it demote-style — the
actual cycle win that silences ~90 low-impact findings — requires impact to be
**grounded in outcomes**, or the loop can converge early by under-rating a real
seam. The tool already has the ground-truth signal: `reconcile-code` (and the
post-run reconciliation tail) empirically reports which plan predictions the
implementation diverged from. Feed those outcomes back to learn which finding
**classes** actually predicted real drift, and use that to calibrate impact
instead of trusting the per-finding self-report.

## Ground truth (confirmed at HEAD)

- Read-only outcome/telemetry readers already exist — reuse them:
  - `plan_tool/telemetry_analysis.py:analyze_decisions(repo_root)` (line ~465)
    — the read-only decision-outcome resolver (computes verdicts on read, never
    persists a second store; ownerless/legacy rows stay counted-but-unresolved).
  - `plan_tool/convergence_diagnosis.py:load_report_history(plan_path)` — the
    saved completeness/reconcile report history reader.
  - The reconcile report sidecars under `.plan-tool/runs/<slug>/` (the
    `*-reconcile.json` / `*-completeness.json` payloads).
- The finding classes to correlate: `Recommendation.source`, anchor category,
  and the seam-vs-detail shape — all already on saved findings.
- **Architectural constraints already codified** (CLAUDE.md): the
  telemetry/analysis leaves compute verdicts **on read**, must **not** auto-tune
  thresholds or mutate plans/config, and must not import `plan_tool.cli`.

## Resolved design decisions

1. **Read-only learning over already-persisted evidence.** Correlate historical
   audit findings (by class) with subsequent `reconcile-code` / post-run drift,
   computed **on read** — no new persisted store, no second telemetry sink.
   Reuse `telemetry_analysis` / report-history readers.
2. **Output is an advisory calibration signal**, per-finding-class, surfaced to
   the operator and **consumable by #152's `is_blocking_impact`** — not a silent
   live re-weighting and not an auto-tuner.
3. **No auto-tuning, no plan/config mutation.** The signal informs; a human (or
   #152's gate, when its demote slice is built) decides. Ownerless/legacy rows
   that can't correlate stay counted-but-unresolved.
4. **This plan does not itself re-key the convergence gate.** It produces the
   calibration; #152's demote slice (separate, out of scope here) consumes it.
5. **Preserve cache provenance as a calibration confounder.** For purity
   findings, retain whether the verdict was freshly generated, exact-cache
   reused, or below-floor reused; report and, where sample size permits,
   stratify those cohorts. Do not silently pool cached and fresh verdicts. Rows
   from legacy evidence that lacks this provenance remain counted with an
   explicit `unknown` cohort. This measures any cache-reuse bias and supplies
   evidence for BACKLOG #155; it does not harden the cache here.

## Seams to reuse (verified at HEAD)

- `plan_tool/telemetry_analysis.py:analyze_decisions` — the read-on-read
  resolver pattern to follow (and possibly extend for the finding-class join).
- `plan_tool/convergence_diagnosis.py:load_report_history` — saved report
  reader.
- The `.plan-tool/runs/<slug>/*-reconcile.json` / `*-completeness.json`
  sidecars — the audit-finding and drift-outcome evidence.
- `plan_tool/review.py` `Recommendation.source` / anchor — the class keys.
- The purity-cache audit path's result/provenance boundary — expose a stable
  read-side indication of `fresh`, `exact-cache`, or `below-floor-reuse` rather
  than inferring it later from verdict content.

## Scope of work (indicative — let create decompose)

1. A read-only correlation leaf that joins historical audit findings (by class)
   to subsequent reconcile/post-run drift and emits a per-class
   drift-prediction signal, computed on read. Preserve purity-verdict provenance
   (`fresh`, `exact-cache`, `below-floor-reuse`, or legacy `unknown`) and report
   it alongside the class-level result; stratify it when evidence is sufficient.
2. The advisory surface exposing that signal (operator-facing) and a clean
   consumption point #152's demote slice can read.
3. Tests: synthetic history where class A reliably preceded drift and class B
   never did → A calibrates up, B down; ownerless/uncorrelatable rows are
   counted-but-unresolved, not dropped; fresh and below-floor-reused purity
   cohorts remain distinguishable (legacy rows become `unknown`, not silently
   fresh); no persisted second store; no plan/config mutation.
4. Docs/status: `DATA_CONTRACT.md` only if a serialized *read* shape is exposed
   (not a new persisted store); update `BACKLOG.md` #154 and note #152 demote
   unblocked.

## Non-goals / out of scope (guardrails — do not cross)

> Inherits BACKLOG **#154**'s **scope contract** (Outcome / In scope / Out of
> scope / Allowed behavior changes / Allowed reorganization / Verification /
> Stop-defer) — the section below elaborates that boundary and introduces no
> new scope.

- **Re-keying the convergence gate (#152 demote).** This plan produces the
  calibration signal; it does **not** change `is_blocking_impact` or any stop
  gate. Building the demote wiring is a separate slice of #152.
- **The live-loop structural escalation (#153).** Not this plan.
- **A second persisted telemetry/verdict store.** Verdicts are computed on
  read, matching the `telemetry_analysis` no-second-store rule. Do not persist a
  calibration cache as durable state.
- **Any auto-tuner that mutates thresholds, plans, or config.** Advisory only.
- **Importing `plan_tool.cli` from the analysis leaf**, or otherwise breaking
  the leaf's below-CLI position / acyclic import order.
- **Dropping legacy/ownerless rows.** They stay counted-but-unresolved.
- **Hardening the purity cache or changing its reuse threshold (#155).** This
  plan records cache provenance so a real bias can be measured; it does not add
  TTLs, sampling, response-envelope changes, or cache-policy tuning.

## Acceptance criteria (plan-level)

- A read-only analysis correlates historical audit findings (by class) with
  subsequent `reconcile-code` / post-run drift and emits a per-class
  drift-prediction signal **computed on read** (no second persisted store).
- #152's demote slice can consume the signal; the entry point is documented.
- No auto-tuning of thresholds, no plan/config mutation; ownerless/legacy rows
  are counted-but-unresolved, not dropped.
- Purity findings expose `fresh`, `exact-cache`, `below-floor-reuse`, or legacy
  `unknown` provenance in the read-only result; the calibration does not pool
  cache-reused and fresh cohorts invisibly.
- The analysis leaf does not import `plan_tool.cli` and preserves the acyclic
  import order.
- `BACKLOG.md` #154 is marked shipped/removed and #152's demote form is noted as
  unblocked.
