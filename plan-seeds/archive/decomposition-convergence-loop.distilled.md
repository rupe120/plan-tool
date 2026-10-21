## Overview

Add a read-only command — **`plan-tool convergence <plan>`** — that reads a plan's saved completeness/reconcile report history, detects when the audit/apply loop is **spinning instead of converging**, and prints a recommendation **forked by the failure's shape**: a *localized* over-pack (one step doing too much) recommends an in-place re-split; a *structural* / cross-step problem (the decomposition itself is wrong) recommends authoring a fresh `create` seed and re-decomposing. v1 is the lean form: a read-only diagnostic that mutates nothing, writes no files, and spends **zero Claude** (it analyzes report JSON already on disk). It prints a four-state verdict and a forked recommendation; completion exits 0 regardless of verdict (exit-code convention). The producer-side changes that would unlock stronger signals are parked in `## Deferred`. (BACKLOG #57.)

> **Why this re-seed exists.** The prior plan (`docs/implementation-plans/2-decomposition-convergence-loop.md`) was authored against an *imagined* report schema. A completeness audit surfaced 14 gaps that nearly all reduce to one root cause — the persisted `SavedReview` does **not** carry granularity findings, a BLOCKED flag, plan/detail body size, reliable step ids, or guaranteed-stable anchor slugs. This seed pins v1 to **what the present schema actually supports** and files the write-side changes the stronger signals need as named v2 prerequisites. The design analysis is in `docs/implementation-plans/plan-details/decomposition-convergence-loop/decomposition-convergence-loop.schema-contract.md`.

## Problem statement

**The pipeline converges on content, never on structure.** Every convergence loop the tool has — `create --iterate`, `detail --iterate`, `completeness --iterate` — closes over plan/detail **content**. **None closes over step boundaries.** Decomposition is decided once, by `create`, in a single round-trip, at the moment of *least* information in the pipeline (before any detail file exists, before the audit has read code at HEAD), and then frozen.

The audit later *acquires* that information and *detects* boundary problems — purity findings, size findings, a branch with no live scenario. But its only repair move is `apply_finding`, which edits **prose**: it cannot delete a concern, move it to another step, drop dead wiring, or re-split. So it patches *around* the mis-decomposition by adding prose, which grows the plan and feeds the next audit more surface — it re-finds the same problem under a new anchor every pass and never converges, all while reporting `no_blocking_findings`/converged and overstating soundness.

Today the only thing that closes this gap is a **human** noticing the non-convergence, diagnosing it, and re-running `create` with a hand-tuned seed (see the "When repeated audit/apply doesn't converge" workflow in `RUNBOOK.md`, and the worked re-seed at `plan-seeds/archive/escalate-structural-findings-to-split-redecomposed.replaced.md`). That human step is the missing pipeline edge: **audit-detects-bad-decomposition → re-decompose.** v1 automates the *detection and recommendation* half of it.

## Architecture

**One module + a thin CLI seam.**

- **`plan_tool/convergence_diagnosis.py`** (orchestrator leaf): read report history → detect signature → classify localized vs. structural → render the forked recommendation. Pure logic, no `invoker` (v1 spends no Claude). Keep it a leaf below the CLI; lazy-import report parsing if it would close a cycle.
- **`plan_tool/cli/convergence_cmd.py`** (thin handler, registered in `parser.py`).

**Input contract — what a saved report actually carries.** v1 is a reader designed against the real persisted schema, not an assumed one. A saved completeness/reconcile sidecar (`SavedReview`, `kind="completeness"` | `"detail-reconcile"` | `"run-reconcile"`) carries at top level: `plan_slug`, `plan_path`, `created_at` (ISO-8601 UTC), `kind`, `step_id` (None for completeness; set for reconcile kinds), `plan_fingerprint`, `code_fingerprint`, `code_fingerprint_present`, `report_md`, `recommendations[]`, and `annotations{}` (the operator's per-finding walk decisions). Per `Recommendation`: `id` (content-addressed, stable only for an *unchanged* finding), `source`, `severity`, `step_id` (**None** for `plan-completeness` / `plan-correctness`), `title`, `body`, `suggested_action`, `impact`, `complexity`, `redirect`, `file_path`, `anchor` (Claude-minted slug; may be None; only *encouraged* stable across re-audits, never guaranteed).

What is **not** present, and therefore cannot back a v1 signal: granularity / `smell_recs` findings, a per-finding BLOCKED marker, plan-body or detail-body byte size (the only size available is `len(report_md)`, which measures the *report*, not the plan), and a reliable per-finding step id for audit findings.

**The non-convergence signature — two deterministic signals.**

- **Region recurrence** (primary) — the same *region* re-flagged without being **closed** across an **M-of-N trailing window** (recurs in at least M of the last N runs, tolerating one missed sampled-audit run rather than requiring a strict consecutive streak).
- **No shrinkage** — open medium+ finding count fails to trend down across the window (endpoint rule: `counts[-1] >= counts[0]`; stated on its own terms, *not* claimed equivalent to `convergence.py`'s consecutive-stall semantics). Evaluate shrinkage on **the recurring region's own** open-count, not only the global count: a plan genuinely stuck on one over-packed step while resolving unrelated peripheral findings (global count trending down) must still read as `spinning` on that region.

**Canonical region key.** `region_key = (kind, normalized_focus)` where `normalized_focus` is, in priority order: the finding's `step_id` if present, else a `step<N>` token parsed from `anchor`, else a truncated slug of `title`. Recurrence matching is **tiered**: an exact `step_id` / `step<N>` match is authoritative; `anchor` equality is *corroborating* (anchors are encouraged-not-guaranteed stable, so a re-slugged gap must not silently break the streak); title-similarity is the last resort. **No cross-`kind` region match in v1** — completeness anchors and reconcile step ids draw from different spaces, so the series is partitioned by `kind`.

**Closed-state.** A finding is **closed** when `annotations[id].status` ∈ {`applied`, `skip`}. Only absent / `open` counts as unresolved. A region the operator deliberately **skipped** (WONTFIX / acknowledged-and-deferred) must not drive a `spinning` verdict.

**How history accrues.** `write_completeness_report` writes **one** sidecar per `completeness` invocation, after the `--iterate` loop converges; the intra-invocation re-audit rounds are **discarded**, and an unchanged-plan reuse skips the write entirely (`skip_sidecar_write`). So the N-run window counts **distinct `completeness`/reconcile invocations across which the plan changed** — not iterate rounds. A single `completeness --iterate` leaves history length 1, and the diagnostic only has signal after ≥N separate invocations.

**Verdict — four-state, not binary,** so "no data" is never mistaken for "healthy": `no-history` (reports dir missing/empty), `insufficient-history` (1…N-1 saved runs; below threshold, reads as "not enough data", *not* a reassuring `converging`), `converging` (≥N runs and the signature does not trip), `spinning` (≥N runs and recurrence + no-shrinkage both trip).

**The fork.** On `spinning`, classify the recurring region and recommend the matching repair: a **localized over-pack** (recurrence concentrates on a single step focus, the rest of the plan quiet) recommends an in-place re-split `plan-tool split <plan> --step N --into "<a>" --into "<b>"` (or interactive `detail --split`) — surgical, 1→2, preserves the other detail files and run state, the path the `escalate-structural-findings-to-split` bridge executes; a **structural / cross-step** problem (recurrence spans multiple step foci, or findings concern inter-step shape — dependencies, ordering, a dead/inert branch, two control-flow shapes merged) recommends authoring a fresh seed and re-decomposing `create --from-existing <seed> --iterate`. A 1→2 split can't fix the structural case; it's N-way.

> **v1 caveat — localization fires only on a `step<N>` anchor.** Because audit findings carry `step_id=None` and granularity (`step_id`-bearing) findings aren't persisted, the only reliable step focus in v1 comes from a Claude-minted `step<N>`-prefixed anchor. A genuine single-step over-pack slugged by concept (e.g. `over-packed-step`) yields no focus → ambiguous → cautious structural re-seed. v1 must **state this limitation honestly**. To reduce false-ambiguity, the localized branch fires when exactly one region is step-focused and any concept-only regions are in the minority. When genuinely ambiguous, v1 says so and recommends the more cautious re-seed (mirroring the `direct`-vs-`plan-tool` heuristic's "when unsure, author a plan").

**Read the report history.** Glob `docs/implementation-plans/plan-details/<slug>/reports/*-completeness.json` (and `*-reconcile.json` if present), ordered by timestamp. Partition per `kind`. For each run collect: open findings with their `anchor`, `step_id`, `severity`, the canonical region key, and the run's `annotations`. Build a per-region recurrence-and-severity trend across runs.

**Output.** Print to stdout: the four-state verdict, the recurring region(s) with their run-count **and severity trend** (`max_severity` / first→last seen — computable from per-run `severity` and **must be rendered**, not just computed), and the matched recommendation with the command pre-filled, e.g.:

```
spinning — step 5 re-flagged in 4 of the last 4 audits, no shrinkage (severity medium→high)
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

The localized `--into "<…>"` titles are **fill-in placeholders** (the diagnosis knows *which* step is over-packed, not the two concern titles to split into); the output must frame them as such, not as fully copy-paste-ready.

**Flags.** Preserve the exit-code convention: a completed diagnosis exits 0 regardless of verdict. **v1 ships no `--fail-on-findings` and no `--min-runs` flag** — the spin threshold N is a detector keyword (default 3) used for testing, not an operator-facing flag, and "tunable" is not advertised. Both flags are in `## Deferred`.

**Open question — standalone command vs. completeness-report section.** v1 assumes a standalone `plan-tool convergence <plan>`. The signature is most useful surfaced *exactly when it trips* — as a short "Convergence diagnosis" section the completeness report prints after K stalled runs. The report-JSON history reader and recurrence logic are the same either way. v1 leans standalone (smaller surface, no completeness coupling), with the report section as the first Deferred follow-up.

## Out of scope

- **Auto-executing any repair.** v1 diagnoses and recommends; it never splits a step, edits a plan, or authors a seed. (Auto-split behind an opt-in is Deferred and must obey the never-mutate-structure-unattended invariant the `escalate_to_split` bridge already uses.)
- **Re-running the audit.** v1 reads *saved* reports; it spends no Claude and triggers no new audit.
- **A new code checker or a new finding source.** This analyzes the *history of findings the audit already produced*; it adds no new audit of plan or code.
- **Any producer-side (write) change.** v1 is a pure reader of the schema as it exists today. Every change to *what gets persisted* is a v2 prerequisite (see `## Deferred`).

## Risks

- **False "spinning" on a plan that's legitimately mid-authoring.** Severity: UX. Mitigation: require N≥3 runs and an M-of-N-within-window recurrence rule that tolerates one missed sampled-audit run before declaring spinning, plus the `insufficient-history` verdict for sub-threshold histories.
- **Claude-authored anchor-slug instability.** Severity: medium. Anchors are only *encouraged* stable across re-audits, so a re-slugged gap could scatter recurrence across keys and suppress a true `spinning`. Mitigation: the tiered region key prefers `step_id` / `step<N>` and treats anchor equality as corroborating, with title-similarity as a fallback.
- **Skip-deferred regions read as spinning.** Severity: medium. Mitigation: the closed-state rule counts `skip` (alongside `applied`) as closed via each run's `annotations`.
- **Mis-forked recommendation.** Severity: wasted work. Mitigation: on an ambiguous classification, default to the cautious re-seed and *say it's ambiguous* — recommend-only keeps the operator in the loop.
- **Report-schema drift.** Severity: low. Mitigation: read defensively (tolerate missing fields) and pin the fields the detector depends on with a fixture test.
- **Import-cycle pressure.** Mitigation: keep `convergence_diagnosis.py` a leaf below the CLI; lazy-import report parsing if needed.

## Testing

Pin the detector against the **real persisted `SavedReview` schema** with fixture tests (not an assumed shape), so report-schema drift is caught — read defensively and assert on the specific fields the detector depends on (`recommendations[].anchor`/`step_id`/`severity`, `annotations[id].status`, `kind`, `created_at`). Default to unit tests on `convergence_diagnosis.py`: the four-state verdict logic, the M-of-N recurrence window (including the one-missed-run tolerance), the no-shrinkage endpoint rule evaluated on a recurring region's own open-count (a plan with global count trending down but one region stuck must still read `spinning`), the canonical `(kind, step_id || step<N> || title-slug)` region key with tiered matching and no cross-kind folding, the closed-state rule (`applied`/`skip` close a region; a skipped region does not drive `spinning`), and the localized-vs-structural fork including the ambiguous→cautious-re-seed default and the `step<N>`-anchor-only localization caveat. Cover the history-accrual boundary cases: `no-history` (empty/missing reports dir), `insufficient-history` (1…N-1 runs). Add an `@pytest.mark.integration` test only for the CLI wiring — driving `plan-tool convergence <plan>` through `main([...])` to assert it reads the globbed report history, prints the rendered verdict + severity trend + pre-filled recommendation, spends zero Claude, writes no files, and exits 0 regardless of verdict.

## Acceptance criteria

- `plan-tool convergence <plan>` reads the saved completeness report history and prints a **four-state** verdict (`no-history` / `insufficient-history` / `converging` / `spinning`) — never reporting a sub-threshold or never-audited plan as a positive `converging`.
- The signature is **recurrence + no-shrinkage** only; the output renders each recurring region's run-count **and** its cross-run severity trend.
- Recurrence keys on the canonical `(kind, step_id || step<N> || title-slug)` region key, treats anchor equality as corroborating not authoritative, and does not match across kinds.
- A region the operator **skipped** (`annotations[id].status == "skip"`) is treated as closed and does not drive `spinning`.
- On `spinning`, it classifies the shape (localized vs. structural) from the report data and prints the matched recommendation; the localized `split` command's `--into` concern titles are presented as fill-in placeholders, not as fully copy-pasteable.
- An ambiguous classification recommends the cautious re-seed and labels itself ambiguous (never a confident wrong split).
- The command spends **zero Claude calls** and writes no files (read-only).
- v1 ships **no** `--fail-on-findings` and **no** `--min-runs` flag; completion exits 0 regardless of verdict (exit-code convention).
- `convergence_diagnosis.py` adds no import cycle.

## Deferred

- **Persist `smell_recs` (granularity-split / -merge) into the completeness sidecar** (producer-change) — v2 prerequisite that unlocks a reliable per-step focus and the granularity-backed localized path, broadening the localized fork beyond `step<N>`-prefixed anchors.
- **Persist a per-finding BLOCKED marker** (producer-change) — v2 prerequisite that restores the structural-`[BLOCKED]` signature component (the strongest structural signal), cut from v1 because it isn't readable today.
- **Capture plan/detail body size at save time** (producer-change) — v2 prerequisite that restores the *intended* monotone-growth signal (plan grows run over run), which the current `report_md`-only size cannot honestly serve.
- **`--min-runs` flag** — expose the spin threshold N as an operator-tunable flag (the detector already takes it as a keyword); out of v1's minimal surface.
- **`--fail-on-findings`-style CI gate** — flip rc non-zero when a plan has been spinning for ≥N runs, so CI can block "this plan isn't converging." Out of v1 (exit-code convention; advisory only).
- **Per-iteration sidecar persistence** — optionally persist each iterate round's report so a single `completeness --iterate` run is diagnosable, rather than requiring ≥N separate invocations to accrue history.
- **Surface the diagnosis as a "Convergence diagnosis" section of the completeness report** after K stalled runs (the open-question follow-up).
- **Opt-in auto-execution of the *localized* split** — wire the recommendation into the `escalate_to_split` bridge behind an explicit flag + TTY gate. Never the structural/re-seed path, and never unattended.
- **Cross-plan sweep** — run the diagnosis over every registered plan (a backlog-health view).
- **Claude-assisted classification** for genuinely ambiguous localized-vs-structural cases — only if the deterministic classifier proves insufficient in practice.
