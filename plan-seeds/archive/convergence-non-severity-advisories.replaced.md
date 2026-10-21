> **Replaced**: this file has been superseded by `docs/implementation-plans/2-convergence-non-severity-advisories.md`.
> Preserved here for history; do not edit.

# Plan seed: convergence non-severity advisories (Stage 3)

```
plan-tool create convergence-non-severity-advisories \
  --from-existing plan-seeds/convergence-non-severity-advisories.md --iterate
```

Backlog sources: **#158** (impact-recurrence, rewritten post-**#251**),
**#248** edit-drift exit (thin advisory only), related **#231** (hard-exit
provenance — dependency named, not implemented here). When this ships, update
those backlog entries (remove shipped scope, mark plan-authored while pending,
or leave deferred follow-ups). Arc settlements:
`.tmp/convergence-arc.md` § Stage 3 (2026-08-10) — do not re-open.

Do **not** execute archived `#153` / first `#158` plans or the blocked seeds
`docs/implementation-plans/plan-seeds/impact-recurrence-01-classifier.md` /
`impact-recurrence-02-loop-stop.md` as-is — they still name retired
`FORK_*` / `RegionTrend` vocabulary.

---

## Outcome

`plan-tool convergence` (and a matching completeness iterate stderr note when
the same evidence is already in hand) prints **two recommend-only advisories**
that stop operators from treating severity-clean as the only exit signal:

1. **Impact-recurrence** — the same still-open, explicit-`impact=high` seam has
   recurred without shrinkage across three consecutive compatible completeness
   passes; name the seam and a conservative next action for discussion.
2. **Edit-drift / self-seeded rate** — across ≥3 compatible completeness
   reports, a strict majority of *new material* findings match the prior-apply
   set (binary observable below); name those findings and note that further
   hand-apply may not be addressing the conceptual problem.

Neither advisory flips iterate `stop_reason`, `--fail-on-findings`, or exit
code. Neither mutates plan structure. Neither revives `spinning` / `FORK_*` /
region-trending.

---

## Settled decisions (plan must not re-litigate)

1. **Post-#251 substrate:** new correlator over persisted report history +
   explicit impact + stable finding identity. Own frozen result type — do not
   consume, produce, or reshape retired `RegionTrend` / `recurring_regions` /
   `classify_fork` / `VERDICT_SPINNING`.
2. **Pass = one real audit.** Collapse each invocation's checkpoint/final
   sidecar pair; a reused-audit replay must not double-count (same invariant as
   the blocked `#158` part-1 seed — keep that counting rule, drop fork wiring).
3. **Impact eligibility:** three consecutive compatible passes; explicit
   `impact=high` every time; still open in newest; no shrinkage. Missing /
   legacy-unknown impact is insufficient, not a trigger. At most one named
   seam + optional step focus for the recommendation text.
4. **Impact delivery:** recommend-only feedback for discussion — **not** a
   loop-terminating `recurring_high_impact_seam` / structural stop in this plan.
5. **Edit-drift binary observable:** over ≥3 consecutive compatible
   completeness reports, a finding is *new* if its id is absent from the prior
   report. Prior-apply set = (a) ids marked applied in the prior report's
   disposition when present, else (b) ids present in pass *k−1* and absent in
   pass *k*. Match = same id, or the existing convergence report-history
   matcher, or ≥2 shared significant title tokens (deterministic). Fire when a
   strict majority of new *material* findings match. No Claude; never grade
   prose quality or "sounds like last edit."
6. **One plan, both advisories** — same altitude (print + discuss); do not
   split by code artifact the way the first `#158` attempt did.
7. **`self-seeded-finding` stays `judgment_only` in the audit-shapes registry**
   — this advisory raises the cost of a silent override; it is not a gate.

---

## Scope contract

### Outcome

See Outcome above.

### In scope

- Deterministic classifiers + result types for both advisories over saved
  completeness report history.
- Rendering on `plan-tool convergence`; optional completeness-iterate stderr
  when evidence is already loaded (no second Claude spend).
- Synthetic history fixtures proving fire / no-fire cases for both signals.
- Docs pointers (`docs/AUDIT_FLOW.md` / DIRECTIVES as needed) stating
  recommend-only + the binary observable.
- Final docs/status step updates BACKLOG **#158** / **#248** edit-drift note /
  names **#231** as the hard-exit follow-up.

### Out of scope / Non-goals

- Reviving `spinning`, `FORK_*`, `recurring_regions`, or widening structural
  recurrence to conceptual sources (`#172` / `#251` settled).
- Loop-terminating stop reasons, exit-code flips, `--fail-on-findings` changes.
- Automatic split / scope-out / re-seed (`#159` / `#160` / `#168` /
  `#116` — re-premise separately).
- Hard edit-drift exit or durable apply→finding provenance (**#231**).
- Changing stage bars (`#91` / `#248` core shipped); reporting polish **#260**;
  four-loop consistency **#261**.
- Arm-clustering changes; Stage 5 / `#255` chat surface.
- Re-weighting severity assignment; pass-count reduction.

### Allowed behavior changes

- New advisory lines on `convergence` (and optional completeness iterate
  stderr) when the settled predicates fire; otherwise silent.

### Allowed reorganization

- New leaf module for the impact correlator if that keeps
  `convergence_diagnosis` free of `#158` product logic; no drive-by folder
  moves.

### Verification

- Fixture histories: impact fire + each disqualifier (missing impact, shrink,
  resolved, &lt;3 passes, double-count collapse).
- Fixture histories: edit-drift fire on strict-majority match; no fire on
  minority, &lt;3 samples, or empty prior-apply set.
- Mutation: deleting the advisory render goes red; classifiers do not import
  retired fork/region APIs.

### Stop / defer

- Valid out-of-scope findings → `BACKLOG.md` / `BUG_BACKLOG.md`, never plan
  expansion.
- Hard exit / remedy-causation provenance → **#231**.
- Re-seed actuation after a named seam → **#159** / **#160** / **#168** after
  their own re-premise.
