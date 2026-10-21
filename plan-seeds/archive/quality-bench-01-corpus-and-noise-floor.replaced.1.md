> **Replaced**: this file has been superseded by `docs/implementation-plans/2-quality-bench-01-corpus-and-noise-floor.md`.
> Preserved here for history; do not edit.

## Outcome

Prove whether one fixed two-item `roadmap` corpus can yield a reviewable deterministic noise-floor table: run the corpus serially at least twice from one pinned execution identity, retain the raw evidence, and publish one version-1 floor record with each metric's observed spread. This is the smallest proof of floor feasibility, not a reusable benchmark or an interpretation layer.

## In scope

- One fixed, versioned two-item corpus for the existing `roadmap` stage-2 route and exactly three deterministic integer metrics: final-artifact byte length, constraint-id count, and stage-2 gate-attempt count. Each metric's floor is its maximum pairwise absolute difference across the completed reruns.
- One serial `plan-tool quality-bench floor --corpus <dir> --reruns <R> --output <path>` surface, separate from the existing `bench` command. It freezes and records the corpus digest, source revision, and active backend descriptor before the first replay, and it rejects a changed identity rather than mixing samples.
- One self-contained `schema_version: 1` output record containing the frozen identity, the complete raw per-item artifacts and run-log facts for every rerun, and the derived three-metric table. The floor runner refuses an existing output path before replay, owns private staging, and atomically publishes that record only after all reruns validate; an interruption or refusal leaves no completed record at the selected output path.
- A bounded documentation and BACKLOG #216 reconciliation step when the resulting plan ships. It records that position 01 is this feasibility proof and keeps position 02 unauthored.

## Scope of work

1. Define the corpus snapshot and the fixed three-metric floor contract.
2. Build the serial replay-and-floor runner with one immutable output record and the existing roadmap `invoker=` seam.
3. Add the one floor command, focused documentation, and the #216 scope reconciliation.

The generated plan must remain at or below these three steps. A proposed component must name the proof property it enables; otherwise it belongs in Deferred.

## Overview

This is position 01 of BACKLOG #216's quality-bench arc. Its only question is whether repeated, unchanged `roadmap` inputs produce a small enough deterministic spread to justify later benchmark work. It measures bytes and recorded execution facts; it does not say whether an artifact is good or whether a later change helped.

## Problem statement

The current baseline lacks an observed floor for even a small representative set of deterministic roadmap measurements. Without that table, a later comparison, calibration, or judged metric would assign meaning to a delta without knowing whether unchanged inputs already produce it. A first proof needs evidence that a floor can be measured and inspected, not the product surfaces that might consume it later.

## Architecture

The corpus, execution identity, and metric vocabulary are fixed before replay. Reruns are serial and isolated through the existing `plan_tool/roadmap.py:run_roadmap` `invoker=` seam; its optional fake remains the only test route, and no test calls a live backend. The output record is the sole retained state for this position: it is written once to the caller-selected path, never selected by a label, replaced, recovered, compared, or read as a current generation.

The three measurements are deliberately a narrow proof set. They cover retained artifact bytes, a structured artifact fact, and a recorded execution fact without adding a rubric or an extensible metric-registry product. A later proposal may add a metric only after this record exists and is manually reviewed; it does not join this position by implication.

The source entry is BACKLOG #216. The resulting plan must update that entry on shipment so its position-01 description matches this proof boundary while preserving the arc anchor and the unauthored position-02 fence.

## Out of scope

- A separate `run` command, labelled captures, label replacement, archives, current pointers, recovery journals, or concurrent-reader protocol.
- A `compare` command, `inside noise` / `outside noise` classification, score, recommendation, winner, trend, or any automatic interpretation of the floor table.
- More than the fixed three metrics, a metric-registry evolution mechanism, or recomputation of historical records under later metric versions.
- A model judge, rubric, calibration, confidence behavior, quality opinion, prose-agreement check, gate, CI policy, exit-code change, control arm, auto-tuning, parallel fan-out, or any position-02 seed or plan.
- Changes to the existing `bench` command or to existing `create`, `detail`, `run`, and `roadmap` behavior outside the isolated replay invocation.

## Risks

- The table may show that the three measurements are too noisy, or that the corpus is too costly, to support a useful floor. That is a completed proof with a negative result: record the evidence and defer further benchmark work rather than widening the corpus or adding interpretation.
- A changed source or backend setting during a floor run would make its samples incomparable. The runner owns the pinned-identity check before each replay and before final publication; a mismatch discards private staging and reports the refusal.
- The raw record may be too large for the two-item, R-rerun proof to remain practical. The fixed corpus and explicit output path make that cost visible; compacting or generalizing storage is deferred rather than added here.

## Testing

The bare-plan stage retains the smallest-proof boundary: it covers one corpus, three measurements, one serial floor route, and one immutable output record; any product-shaped lifecycle or comparison request is deferred. Detail may require the exact replay and atomic-publication mechanism only when it demonstrates the pinned-identity and no-partial-record properties.

With a fake `invoker=`, two corpus items and R >= 2 reruns produce one output record with all raw evidence and all three floors. Constant fixture responses yield zero for every floor; a deliberately changed artifact, structured-id set, and gate-attempt fact widens only their respective floors. A source or backend-identity mismatch, failed replay, or interruption leaves no completed output record. No test spawns a live backend.

## Acceptance criteria

- The only shipped quality-bench operation is the serial floor proof, and it remains separate from the existing `bench` command.
- A complete floor run writes one version-1 self-contained record with the pinned identity, raw rerun evidence, and exactly the three predeclared deterministic floors.
- A source/backend identity mismatch or incomplete run produces no completed record; an unchanged constant fixture produces zero floors and a deliberately varied fixture widens only the relevant measurement.
- The command reports factual floor data only and changes no existing exit behavior, gate, confidence behavior, or decision path.
- BACKLOG #216 identifies position 01 as this smallest proof and leaves position 02 unauthored.

## Deferred

Comparison and any interpretation of a floor table, reusable label/store lifecycle, additional or versioned metrics, historical recomputation, corpus expansion, calibration, confidence work, and judged metrics are separate follow-up decisions. If this proof is not usable at an affordable R, record that result against BACKLOG #216; do not author a replacement position or broaden the experiment.
