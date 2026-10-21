# Withdrawn 2026-08-21: jira-grade 03 quality ledger

> **Historical record, not a `plan-tool create` input.** The probe,
> quality-ledger, materiality, and canonical-inversion route is cut. #293 now
> owns the selected implementation-grade bundle's terminal projection into
> concise Jira stories and a developer-handoff companion. The plan remains the
> authority for non-negotiable outcomes; the companion presents grounded
> implementation guidance as suggestions.

The former proposal is retained below only to document the cut route.

```
plan-tool create jira-grade-03-quality-ledger --from-existing plan-seeds/jira-grade-03-quality-ledger.md --iterate
```

> **Source and lifecycle.** Stage **03 of 05** in the ordered `jira-grade`
> group (arc: BACKLOG **#169**, the group anchor). **Re-scoped
> 2026-07-22** from the original paired decision experiment: once the
> communication-first direction was decided, a controlled A/B comparing
> run-grade against jira-grade lost its decision value — this stage now
> **instruments the chosen path** instead of comparing two futures. The
> paired-isolation machinery (clones, matched baselines, control arm, pilot
> pair) is dropped entirely; the one-off mechanism falsification check moved
> into stage 01. **Hard dependencies:** stages 01
> (`docs/implementation-plans/2-jira-grade-01-detail-instrument.md`, **shipped**) and 02
> (`plan-seeds/jira-grade-02-consumer-probe.md`) must ship first — the
> ledger aggregates the audit and probe evidence those stages produce. One
> stage-01 deferral is load-bearing here: jira-grade completeness audits
> ship audit-and-report-only and persist **no** findings sidecar (stage 01
> step 7's cross-grade safety rule), so this stage's first act is landing
> the **grade-marked jira-grade sidecar** — the persisted-schema decision
> stage 01 deferred (`DATA_CONTRACT.md` grade marker plus exclusion filters
> in the run-grade consumers) — without which the churn metric and
> `convergence` are blind to jira-grade audit history, and stage 05 would
> invert to a canonical bundle `convergence` cannot see. This
> seed inherits #164's scope contract (as amended by stage 01's grounding
> amendment). The final docs/status step must reconcile `BACKLOG.md` #164
> per its Stop/defer rules.

---

## Intent

Accumulate enough measured history across real plans that stage 05's
inversion gate reads evidence instead of impression. The priority is
**probe-actionability history** — one probe is an anecdote, and the gate
needs a corpus; churn instrumentation is retained but nothing downstream
waits on it. This stage also lands the grade-marked jira-grade sidecar, so
jira-grade audit history exists at all. Success is a read-only roll-up that
can honestly say *healthy*, *below-floor*, or *insufficient data* — and
recording that the noise floor swamps the churn effect is a legitimate
result, not a failure.

## Why a ledger, not a bake-off

The original stage 03 answered "which grade should win?" — a comparison
question demanding a control arm and matched baselines. That question is
settled by fiat: communication is the product. What remains is a
**monitoring question** — *is the jira-grade output good, and is it getting
better?* — and monitoring wants an absolute, longitudinal signal on the
canonical artifact against its consumer contract, not a synthetic pair:

- **Dissolved with the experiment:** `paired-run-isolation` (no paired runs
  exist, so there is no baseline to match) and the `metric-noise` single-pair
  gate (trends over a predeclared number of real plans replace a one-shot
  verdict).
- **Survives, repurposed:** the deterministic churn formula, the
  probe-actionability metric, provenance discipline, and the
  declare-before-reading posture — now collected from real usage as a
  quality ledger that both fine-tunes jira-grade output and feeds #171's
  inversion gate.

## Overview

Ship a read-only quality surface that aggregates **already-persisted
evidence** — stage-02 probe sidecars (actionability), run logs (consumer-mode
smoke checks), and completeness-report sidecars (churn) — into per-plan ledger
entries and a roll-up with predeclared floors and trend labels. The roll-up is
the evidence surface stage 05 (canonical inversion, #171) gates on.

**Read the ordering above as the stage's priority, not a list.** As of
2026-07-29 stage 05 is gated on **probe actionability**, so this stage's
first duty is to accumulate probe history across many plans — one probe run
is an anecdote, and the gate needs a corpus. Churn instrumentation is retained
and worth having, but **nothing downstream waits on it**; if the churn work
grows past what the ledger justifies on its own terms, cut it and say so
rather than rescuing the metric. (See "The mechanism question" below for why
churn was demoted, and the noise-floor pilot that demoted it.)

One behavior change, first and fenced: jira-grade completeness audits begin
persisting their grade-marked findings sidecar (the stage-01 deferral). Its
durable justification is **not** churn evidence — it is that inverting to a
canonical jira-grade bundle while jira-grade audits persist no history would
leave `convergence_diagnosis`, the tool's main structural-defect instrument,
blind on every plan's canonical bundle (#171's hard prerequisite). Everything
else is read-only; the roll-up spends no Claude and always exits 0.

## Design

### Derived, not duplicated

The ledger is a deterministic reader over sidecars the tool already writes;
it introduces minimal new state — a committed floors/protocol declaration
and the computed roll-up report. Entries carry provenance through the
fingerprints, grade selections, and backend settings already stamped on the
source sidecars; the ledger never re-derives or re-judges evidence, only
aggregates it.

### The metrics

- **Churn:** the deterministic formula — a single number computed from
  stable finding identities and material severities across completeness
  snapshots spanning scope changes. Two evaluators given the same reports
  must derive the same value; formula, inputs, and tie-breaks are declared,
  not judged per-run.
- **Actionability:** stage-02 probe blocker counts and severities per bundle
  over time. Plain-English drift is captured operationally here: prose a
  consumer cannot act on surfaces as anchored `unanswerable-decision` /
  `missing-constraint` blockers, so readability regressions move this
  metric rather than needing a separate style judge.
- **Smoke-check guardrail:** consumer-mode `run` outcomes on jira-grade
  bundles (first-pass result, verification outcome) recorded as ledger
  entries — a floor confirming `run` still works acceptably on the chosen
  path, not a comparison against run-grade.

### Floors and trends, predeclared

The protocol declaration fixes, before any roll-up is read: each metric's
floor, the number of distinct real plans and history depth required for a
trend to count, and the interpretation rules. The roll-up labels each metric
**healthy**, **below-floor**, or **insufficient-data** — insufficient data
is an explicit label, never coerced to healthy. Changing a formula or floor
is a new declaration, recorded, never a silent reinterpretation.

### The inversion gate feed

The roll-up explicitly states stage 05 eligibility: floors met across the
predeclared plan count → inversion eligible; anything else → #171 stays
blocked. This stage only reports — it never actuates inversion, changes a
default, or flips an exit code.

## Suggested decomposition

- **Grade-marked sidecar step (the stage-01 deferral, first):** land the
  persisted-schema decision stage 01 step 7 deferred — a grade marker in
  the saved-review sidecar schema (`DATA_CONTRACT.md`, drift-guarded),
  jira-grade audits writing their sidecar under it, and exclusion filters
  so the run-grade consumers (`resolve_reusable_audit`,
  `completeness-apply`, `convergence_diagnosis.load_report_history`) never
  read cross-grade — the producer this ledger's churn metric and stage
  05's convergence visibility require. Until the filters are tested,
  stage 01's no-sidecar rule stays the safety mechanism.
- **Protocol declaration step (non-code first):** the committed floors
  document — metric formulas, floors, required plan count/history depth,
  interpretation rules. Nothing downstream may reinterpret these.
- **Ledger reader step:** deterministic aggregation from the source sidecars
  into per-plan entries and the roll-up, with fixture coverage for metric
  math, provenance carry-through, and the insufficient-data label.
- **Surface step:** the read-only CLI surface (a roll-up command or an
  extension of an existing read-only surface such as `list --status`),
  `docs/cli/` regeneration, and the explicit #171-eligibility line in the
  roll-up output.
- **Docs/status step:** `RUNBOOK.md` / `CAPABILITIES.md` / `USE_CASES.md`
  coverage and `BACKLOG.md` #164 reconciliation.

## Stage and audit scope fence

**Tool state when this plan starts:** stages 01 and 02 have shipped — both
detail grades exist with grade-aware audit grounding and plain, concise
English jira-grade prose by contract; the consumer probe and its `probe`
verdict arm are live; run-grade is still the default and canonical grade. **Tool state
this plan leaves behind:** one read-only quality surface, plus jira-grade
audits persisting grade-marked sidecars the run-grade consumers provably
ignore; behavior otherwise unchanged.

Completeness audits of this plan must judge it against that stage's tool
state only. Route later-stage or sibling concerns as `[out-of-scope-deferred]`
to their owning stage instead of expanding this plan: probe internals or
blocker contracts (stage 02, #169 — fixed upstream), blocker-recurrence
materiality or any evidence-based demotion (stage 04, #170), inversion
actuation or any default change (stage 05, #171). Per the #125 convention,
deferred-tagged findings neither reset low-yield streaks nor justify raising
pass caps; prefer `--audit-passes 1` for audits of this plan.

## Out of scope

- Any paired or controlled experiment, clone isolation, matched baselines,
  or control arm — dropped with the decision-experiment framing. **The
  mechanism question itself now lives here**, not in stage 01: see "The
  mechanism question (moved from stage 01)" below.
- Actuating inversion or changing any default (stage 05, #171); the ledger
  only reports eligibility.
- Demoting or promoting audit findings on ledger or probe evidence (stage
  04, #170).
- Any new Claude-invoking surface — the ledger is deterministic end to end
  (the sidecar step changes persistence, not judgment, and invokes nothing
  new).
- Statistical machinery beyond floors and trend labels.
- Mutating, re-judging, or backfilling the source sidecars.

## Risks and mitigations

- **Goodhart / metric gaming:** floors and formulas are predeclared,
  deterministic, and evidence-cited; a formula change is a recorded
  re-declaration, and the actionability metric is grounded in anchored
  blockers rather than a tunable style score.
- **Sparse history:** insufficient-data is a first-class label; the roll-up
  cannot report healthy without the declared plan count and history depth.
- **Interpretation drift:** the roll-up cites the protocol declaration it
  was computed under; two declarations never silently mix.

## The mechanism question (moved from stage 01)

Stage 01 originally carried a one-off falsification check: author both grades
for one plan, apply one scoped change, audit each bundle, and compare the
finding-set deltas. **It was cut from stage 01 on 2026-07-29** and the question
belongs to this stage. Why it was cut, so this stage does not repeat the
mistake:

- **It could not produce a reading.** The comparison runs on the conceptual
  audit, which is a sampled Claude judgment, so a bundle's findings are not
  reproduced identically between its baseline and post-change audits. At n=1 —
  one plan, one change — an unknown share of each arm's delta is sampler
  variation rather than change-induced churn, and nothing in the design
  separated the two.
- **Every fix moved the bias instead of removing it.** Judging a compact bundle
  under run-grade prompt framing turns each shed implementation fact into an
  apparent gap and inflates the jira arm; telling the judge those absences are
  fine suppresses exactly the class the comparison counts and guarantees the
  expected answer. Stage 01 flipped between those two horns in consecutive
  audit rounds.
- **It cost more than it could return.** It gated nothing by its own statement,
  yet across ten audit rounds of stage 01 roughly 29% of all findings traced to
  it or to the `--bundle-framing` control it forced into the CLI.

What this stage needs in order to answer it properly, none of which stage 01
had:

- **A measured noise floor.** Before comparing arms, audit one unchanged bundle
  twice and record how much its finding set moves on its own. That number is
  the floor any claimed difference must clear. Without it there is no reading.
- **More than one plan and one change.** The ledger is longitudinal by design;
  use that rather than a single pair.
- **One fixed framing across arms, recorded in the artifact** — and the
  classification (absence vs contradiction) done in the analysis, not by
  instructing the judge, so the judgment is visible and reversible.
- **A stated direction for each outcome before the evidence exists**, including
  the case where the jira arm churns *more*, which must not be absorbed into
  "comparable" or reported as indeterminate.

If the noise floor turns out to swamp the effect at any feasible sample size,
that is a legitimate result: record it and drop the churn claim rather than
keeping the experiment alive. Stage 05's inversion must not be gated on a
measurement this stage cannot actually make.

**The successor gate is decided (user, 2026-07-29): probe actionability, not
churn.** If churn proves unmeasurable, stage 05's inversion is gated on stage
02's consumer probe instead — jira-grade bundles must produce **no worse**
anchored blocker findings than run-grade ones. The reasoning, recorded so this
is not re-litigated: probe blockers **anchor to code**, so they are far less
sampler-bound than a finding-set delta over sampled prose, and stage 02 is
building the probe regardless, so the successor gate costs no new instrument.
Two consequences for this stage:

- **Churn is no longer load-bearing for the arc.** It is worth measuring if the
  floor permits, but it is not the thing stage 05 waits on, so this stage must
  not grow its budget to rescue the churn number. If the floor work exceeds
  what the ledger justifies on its own terms, cut it and say so.
- **This stage still owns the floor question** — because probe actionability
  needs its own floor before it can gate anything. Measure repeat-run variance
  for the **probe's blocker set** on the same footing as the churn floor; a
  consumer-side metric is less sampler-bound, not un-sampled.

### What the free pilot already showed (2026-07-29)

Stage 01's committed report history was mined for a free floor estimate before
this stage spends anything on a clean measurement. Method: group the 26 saved
reports by identical `plan_fingerprint` **and** `detail_bundle_fingerprint` —
those pairs audited byte-identical input, so whatever differs between them is
the audit moving on its own. Eight such groups exist. Three results, and the
first two change this stage's design:

- **Seven of the eight groups are cache hits, not repeat measurements.** The
  conceptual audit is reused unless the saved one is stale, so a same-input
  re-run usually replays the previous findings verbatim — one pair emitted
  byte-identical multi-paragraph prose 34 minutes apart. **The saved report
  records no reuse flag**, so in the history a cache hit and perfect agreement
  are indistinguishable. Two consequences: the floor cannot be recovered from
  report history at all, only from purpose-built runs that *defeat* reuse; and
  this stage's ledger needs the report to record whether the conceptual pass
  was sampled or replayed, or every longitudinal number it computes silently
  mixes the two.
- **Finding-identity churn overstates real movement.** The one genuine repeat
  pair (`20260722-154518` → `20260722-161258`) returned 39 vs 37 findings with
  42% of finding identities disagreeing — but the disagreement is largely
  *renaming*: `[audit-grounding-fence]` and `[depth-aware-audit-grounding]` are
  the same issue about the same sentence under two different slugs. A churn
  metric keyed on finding id would score that pair as large movement on
  unchanged input. Match on substance, not identity, or the metric measures
  the sampler's naming habits.
- **n=1, so this bounds nothing.** One genuine repeat pair is a hypothesis
  generator, not a floor. It does tell this stage what to build: force at least
  five re-audits of one unchanged bundle with reuse defeated, and define churn
  over substance-matched findings before comparing any arms.

The pilot is deterministic and costs no Claude; re-run it against a larger
report corpus once this stage's ledger exists.

## Acceptance criteria

- The grade-marked jira-grade sidecar lands first: `DATA_CONTRACT.md`
  documents the grade marker, jira-grade audits persist under it, and
  tests prove the run-grade consumers (`resolve_reusable_audit`,
  `completeness-apply`, `convergence_diagnosis.load_report_history`) never
  read a cross-grade sidecar.
- A committed protocol declaration (formulas, floors, plan count, history
  depth, interpretation rules) exists before any roll-up is computed.
- The deterministic roll-up aggregates real sidecar evidence into per-plan
  ledger entries and per-metric labels (healthy / below-floor /
  insufficient-data); fixtures cover metric math, provenance carry-through,
  and edge cases.
- Consumer-mode `run` smoke-check outcomes are captured and aggregated as a
  guardrail metric.
- The surface is read-only: no Claude spend, no mutation, exit 0 always.
- The roll-up explicitly states stage 05 (#171) gate eligibility under the
  declared floors.
- Beyond the fenced sidecar persistence, no audit, `run`, or default
  behavior changed; tests pin this.
- `BACKLOG.md` #164 is reconciled by the final step.

## Deferred

- Blocker-recurrence materiality (stage 04, #170) — the ledger's probe
  history is its input, produced here as a side effect.
- Canonical inversion (stage 05, #171).
- Statistical confidence beyond floors/trends; auto-tuning floors; any
  alerting or scheduling around the roll-up.
