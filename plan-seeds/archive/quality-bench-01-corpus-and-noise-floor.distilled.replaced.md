> **Replaced**: this file has been superseded by `docs/implementation-plans/2-quality-bench-01-corpus-and-noise-floor.md`.
> Preserved here for history; do not edit.

## Overview

Adds a new `bench` verb group (`run`, `compare`, `floor`) that measures the deterministic behavior of plan-tool's existing verbs across code changes. `plan-tool bench run --corpus <dir> --label <name>` replays a fixed, versioned corpus of seeds through one authoring stage, stores every artifact it produces (plus the run log) under `.plan-tool/bench/` keyed by label, and computes a predeclared set of deterministic metrics from that stored evidence — counts, resolution of declared ids, presence of required sections/fence fields, gate attempts consumed, exit outcome, wall time, cost, and each metric's cross-rerun stability. `plan-tool bench floor` measures each metric's noise floor by repeating the corpus R times against one unchanged commit. `plan-tool bench compare <label-a> <label-b>` prints each metric's delta next to its recorded floor and labels it `inside noise` or `outside noise`, so a reported difference is judged against measured variance rather than treated as a bare number. This is position 01 of the `quality-bench-NN` arc (later positions stay unauthored until this one ships) and deliberately ships no LLM judge, rubric, or quality opinion — later positions build judged metrics on top of the floors this position produces.

## Problem statement

Nobody currently knows what any of plan-tool's candidate quality metrics do when nothing changes at all. A 2026-08-01 measurement on `roadmap` stage 2 — three runs on byte-identical input (`prompt_bytes = 33942` in every run) — found wildly different rerun behavior per dimension: quality-attribute dispositions were 7 of 7 identical across all three runs, constraint row ids shared only 1 of 19 between two runs, and gate attempts consumed went 3, then 1, then 1. A benchmark that scored 'constraint set quality' across a code change would report a large delta caused by nothing; one that scored disposition ranking would be reading real signal — and the only way to tell which metric is which is to rerun the corpus against an unchanged tree and measure. This repo already paid for skipping that step: BACKLOG #164's one-off mechanism falsification check was cut on 2026-07-29 after roughly 29% of findings across ten audit rounds traced back to it or its `--bundle-framing` control, because at n=1 sampler variance swamped the signal and the check gated nothing. This plan is the missing prerequisite #164 lacked — establishing each metric's noise floor before any comparison is trusted.

## Architecture

The determinism ladder is climbed in stage order, not all at once: position 01 computes only metrics decidable from stored artifacts by code — counts, resolution of declared ids, presence of required sections and fence fields, gate attempts consumed, exit outcome, wall time, cost, and each metric's cross-rerun stability. No rubric, scoring prose, or model sits in the measurement path; judged metrics are position 02's subject, gated on this position's output.

Artifacts are the record, scores are recomputed: a run stores the produced files plus the run log, keyed by label, under `.plan-tool/bench/`. Metrics are computed from that store and can be recomputed whenever a metric's definition changes, so a metric added months later can be applied retroactively to every already-captured label; storing only scores would make the corpus un-reanalyzable.

Every metric ships with its noise floor or it does not ship: a metric's floor is the spread observed across R reruns of the corpus at one unchanged commit, and `bench compare` reports each delta as `inside noise` / `outside noise` against that floor. A metric with no recorded floor is reported `unfloored` and excluded from any summary verdict — insufficient data is a first-class label, never coerced into a verdict.

The corpus is fixed, versioned, and small: seeds live in the corpus directory and change only by an explicit, committed edit, since a corpus that drifts silently makes every historical label incomparable. It stays small because each item costs a real Claude run (the roadmap smoke run was ~$2.50 and ~6 minutes for two stages), so the corpus is sized to the floor it can afford to measure (R reruns × N items) rather than to coverage.

Replay isolation: each corpus item runs against its own empty scratch repo, so items cannot see each other's output and no metric reflects the order items ran in.

This answers a monitoring question, not a decision question (`docs/NONDETERMINISM_PLAN_DESIGN.md` Rule 6's fork): is the chosen path healthy, and did this commit move it — floors and trends over the corpus — not a controlled-arm choice between two futures, which is the shape that was cut and would need its own separate justification.

## Out of scope

- No LLM judge, rubric, or model-scored metric of any kind — that is position 02's subject, gated on this position's floors.
- No quality opinion — no metric may assert that an artifact is good, better, well-grounded, or well-reasoned; every metric is a count, a ratio, a resolution check, or a stability measure over bytes.
- No agreement check between two prose artifacts — not seed-vs-plan, not plan-vs-detail, not artifact-vs-brief; this is the specific shape CLAUDE.md's rule 5 says to kill rather than tune.
- No gate, no exit-code flip, no CI blocking — `bench` reports; a completed run exits 0 whatever the numbers say, per the exit-code convention.
- No control arms, matched baselines, or A/B comparison of two prompt variants — that is the cut #164 mechanism; re-proposing it is separate work that must first show it has the power this position's floors would reveal.
- No auto-tuning — nothing reads a metric and adjusts a threshold, prompt, or default.
- No expansion of the corpus to every verb — one verb, one corpus, this position.
- No shape or length caps on any artifact, as a metric or otherwise.
- No parallel fan-out to make the corpus faster (CLAUDE.md's anti-parallelism directive) — if a corpus is too slow, it is too big.

## Risks

- Metrics may be dominated by noise rather than signal: if the floor measurement shows that most deterministic metrics are noisier than any plausible change effect, that is a real finding to surface, not a reason to widen the corpus. Mitigation: stop and report it — this corpus cannot support a benchmark at an affordable R, and the honest answer is a smaller claim, not a bigger corpus, filed rather than the scope being expanded.
- A specific verb's own rerun variance (e.g. the `roadmap` retry budget question, closed 2026-08-05 with no action per `docs/HISTORICAL_BACKLOG_DECISIONS.md`) is out of this plan's remit; surfacing such a gap here rather than routing it to that verb's own backlog entry risks misattributing a verb-specific issue to the benchmark itself.

## Testing

A corpus of two items, replayed R times at one commit with a stubbed invoker, produces a floor per metric: a metric that is constant across reruns floors at zero spread, and a metric fed deliberately varying stub output floors wider. `bench compare` run on two labels captured from the same commit reports every metric `inside noise`. A metric with no recorded floor is reported `unfloored` and is absent from any summary. The stored artifacts round-trip: deleting the computed metrics and recomputing from the store reproduces them exactly. Hermetic per TESTING.md — the harness takes the same `invoker=` seam every orchestrator does, and no test spawns a real backend.

## Acceptance criteria

- `plan-tool bench run --corpus <dir> --label <name>` replays every seed in the fixed corpus through one authoring stage, stores every produced artifact plus the run log keyed by label under `.plan-tool/bench/`, and computes the predeclared deterministic metric set from that store.
- `plan-tool bench floor` computes each metric's noise floor from R reruns of a corpus at one unchanged commit; a metric constant across reruns floors at zero spread, and a metric fed deliberately varying stub output floors wider.
- `plan-tool bench compare <label-a> <label-b>` prints each metric's delta alongside its recorded noise floor and labels the delta `inside noise` or `outside noise`; a metric with no recorded floor is reported `unfloored` and excluded from any summary verdict.
- Deleting a label's computed metrics and recomputing them from the stored artifacts reproduces the original values exactly.
- The harness is hermetic: it takes the same `invoker=` seam as every other orchestrator, and no test spawns a real backend (per TESTING.md).
- `BACKLOG.md` carries an anchor entry for the `quality-bench-NN` arc (this position plus the gated position-02 judged-metric layer), updated when this plan ships.
