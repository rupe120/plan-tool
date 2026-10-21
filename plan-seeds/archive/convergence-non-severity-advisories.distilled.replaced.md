> **Replaced**: this file has been superseded by `docs/implementation-plans/2-convergence-non-severity-advisories.md`.
> Preserved here for history; do not edit.

## Overview

This plan adds two recommend-only advisories to `plan-tool convergence` (and optional completeness-iterate stderr when evidence is already loaded) that alert operators when severity-clean convergence is not the only exit signal. The first, impact-recurrence, fires when the same still-open, explicit-`impact=high` seam has recurred without shrinkage across three consecutive compatible completeness passes. The second, edit-drift, fires when a strict majority of new material findings match the prior-apply set across ≥3 compatible reports. Neither advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit code, and neither mutates plan structure or revives retired `spinning` / `FORK_*` / region-trending vocabulary.

## Problem statement

Today `plan-tool convergence` diagnoses convergence state using severity and finding counts, but two important non-severity signals go unreported: a high-impact seam that persists across passes without shrinking, and an edit-drift pattern where new findings predominantly match prior-apply edits rather than the original artifact. Operators treating a severity-clean audit as the sole exit signal miss both patterns — continuing to hand-apply self-seeded findings or overlooking a recurring high-impact seam that warrants discussion. These are the non-severity signals the `#251` retirement of region-trending left unaddressed. Backlog sources: `#158` (impact-recurrence, rewritten post-`#251`), `#248` edit-drift exit (thin advisory only), related `#231` (hard-exit provenance — dependency named, not implemented here).

## Architecture

Both advisories are deterministic classifiers operating over persisted completeness report history — no Claude spend. They share a new correlator that collapses each invocation's checkpoint/final sidecar pair into one logical pass (preventing double-counting), then evaluates eligibility predicates over consecutive compatible passes.

**Impact-recurrence** tracks explicit-`impact=high` findings by stable identity across ≥3 consecutive compatible passes, firing when the same seam is still open in the newest pass with no shrinkage. Missing or legacy-unknown impact is insufficient — it is not a trigger. The advisory names at most one seam plus an optional step focus for the recommendation text.

**Edit-drift** uses a binary observable: a finding is *new* if its id is absent from the prior report. The prior-apply set is (a) ids marked applied in the prior report's disposition when present, else (b) ids present in pass *k−1* and absent in pass *k*. Match is same id, or the existing convergence report-history matcher, or ≥2 shared significant title tokens (deterministic). It fires when a strict majority of new material findings match. No Claude; never grade prose quality.

A new leaf module houses the impact correlator if that keeps `convergence_diagnosis.py` free of `#158` product logic; no drive-by folder moves. Both advisories produce their own frozen result type — they do not consume, produce, or reshape retired `RegionTrend` / `recurring_regions` / `classify_fork` / `VERDICT_SPINNING`.

The `self-seeded-finding` entry in the audit-shapes registry stays `judgment_only` — this advisory raises the cost of a silent override but is not a gate. Both advisories render on `plan-tool convergence`; completeness iterate surfaces them on stderr only when the evidence is already loaded (no second Claude spend).

## Out of scope

- Reviving `spinning`, `FORK_*`, `recurring_regions`, or widening structural recurrence to conceptual sources (`#172` / `#251` settled).
- Loop-terminating stop reasons, exit-code flips, `--fail-on-findings` changes.
- Automatic split / scope-out / re-seed (`#159` / `#160` / `#168` / `#116` — re-premise separately).
- Hard edit-drift exit or durable apply→finding provenance (`#231`).
- Changing stage bars (`#91` / `#248` core shipped); reporting polish `#260`; four-loop consistency `#261`.
- Arm-clustering changes; Stage 5 / `#255` chat surface.
- Re-weighting severity assignment; pass-count reduction.

## Testing

- Synthetic fixture histories for impact-recurrence: fire case, and each disqualifier (missing impact, shrinkage, resolved, <3 passes, double-count collapse from checkpoint/final sidecar pair).
- Synthetic fixture histories for edit-drift: fire on strict-majority match; no fire on minority match, <3 samples, or empty prior-apply set.
- Mutation: deleting the advisory render goes red; classifiers do not import retired fork/region APIs.
- Existing suites in `tests/` must remain green.

## Acceptance criteria

- `plan-tool convergence` prints an impact-recurrence advisory when the same still-open, explicit-`impact=high` seam recurs without shrinkage across ≥3 consecutive compatible completeness passes.
- `plan-tool convergence` prints an edit-drift advisory when a strict majority of new material findings match the prior-apply set across ≥3 compatible reports.
- Neither advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit code.
- Neither advisory mutates plan structure.
- Neither advisory consumes, produces, or reshapes retired `RegionTrend` / `recurring_regions` / `classify_fork` / `VERDICT_SPINNING`.
- Each invocation's checkpoint/final sidecar pair collapses to one logical pass; a reused-audit replay does not double-count.
- Missing or legacy-unknown impact does not trigger impact-recurrence.
- Edit-drift match is fully deterministic — no Claude, no prose-quality grading.
- Optional completeness-iterate stderr surfaces advisory when evidence is already loaded, without a second Claude spend.
- Final docs/status step updates BACKLOG `#158` / `#248` edit-drift note / names `#231` as the hard-exit follow-up.

## Deferred

- Hard edit-drift exit or remedy-causation provenance → `#231`.
- Re-seed actuation after a named seam → `#159` / `#160` / `#168` after their own re-premise.
- Valid out-of-scope findings surfaced during implementation → `BACKLOG.md` / `BUG_BACKLOG.md`, never plan expansion.

## Input

Consumes persisted completeness report history (saved sidecar files from `completeness-audit` invocations). Relies on: stable finding identity (ids) on `Recommendation` objects; the existing convergence report-history matcher in `convergence_diagnosis.py`; explicit `impact` field values; checkpoint/final sidecar pairs per invocation; and disposition/applied markers when present. `review_persistence` owns sidecar I/O; `DATA_CONTRACT.md` documents the persisted `Recommendation` schema including `impact` and finding identity fields.
