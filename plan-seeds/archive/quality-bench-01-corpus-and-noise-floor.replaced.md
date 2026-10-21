> **Replaced**: this file has been superseded by `docs/implementation-plans/2-quality-bench-01-corpus-and-noise-floor.md`.
> Preserved here for history; do not edit.

# quality-bench-01: a fixed corpus, a replay runner, and each metric's measured noise floor

**Arc position 01 of the `quality-bench-NN-*` group.** Later positions stay
unauthored until this one ships, per the ordered-efforts convention. This
position deliberately ships **no LLM judge at all** — see Architecture.

## Relationship to completed risk and confidence work

BACKLOG #216 owns this ordered arc. Completed #181/#182 supply a declared
work-shape and advisory authoring context; completed #295 supplies visible,
display-only evidence support for `Recommendation` findings. They remain
distinct inputs, not benchmark metrics or decision rules. This position
measures deterministic artifact behavior and rerun spread only. It cannot
calibrate confidence, score risk, admit a judge, or change a gate; a later
proposal needs the floor table this seed produces. Renderer consolidation
(BACKLOG #316) is independent display hygiene and is not a prerequisite.

## Outcome

`plan-tool bench run --corpus <dir> --label <name>` replays a fixed corpus of
seeds through one authoring stage, stores every artifact it produced, and
computes a predeclared set of **deterministic** metrics over them; `plan-tool
bench compare <label-a> <label-b>` prints each metric's delta **beside that
metric's own measured rerun spread**, so a difference is reported as inside or
outside the noise rather than as a bare number.

## Why this shape, and why no judge yet

The ask is "measure the impact of changes over time." The blocker is not
judging machinery — it is that **nobody knows what any of these metrics do when
nothing changes at all.**

Measured on `roadmap` stage 2, 2026-08-01, three runs on byte-identical input
(all three logged `prompt_bytes = 33942`):

| Dimension | Rerun behavior |
|---|---|
| quality-attribute dispositions | **7 of 7 identical**, all three runs |
| constraint row ids | **1 of 19 shared** between two runs |
| gate attempts consumed | 3, then 1, then 1 |

Same input, same commit, no change under test. A benchmark that had scored
"constraint set quality" across a code change would have reported a large
delta caused by nothing. One that scored "disposition ranking" would have been
reading real signal. **The dimension decides whether the metric is a metric**,
and the only way to know which is which is to run the corpus repeatedly against
an unchanged tree and measure.

This repo has already paid for skipping that step. BACKLOG #164's one-off
mechanism falsification check was **cut on 2026-07-29**: ~29% of findings
across ten audit rounds traced to it or its `--bundle-framing` control, it
gated nothing, and *at n=1 sampler variance swamped the signal*. That entry's
Out of scope now forbids re-introducing a comparison, control arm, or churn
claim into it. This seed is not that: it is the missing prerequisite that
would have told #164's evaluation it had no power, before it spent ten rounds.

`docs/NONDETERMINISM_PLAN_DESIGN.md` already governs this work and is not
restated here — Rule 3 (climb the determinism ladder before adding a judge),
Rule 6 (predeclare all interpretation; variance is signal; a metric two
evaluators compute differently from the same evidence is not a metric yet).
CLAUDE.md § "Validating a semantic property you cannot observe" applies with
full force, and its rule 1 is why this position's deliverable is a number
computed from stored bytes rather than an opinion about them.

## The question this asks, named

**Monitoring, not decision** (Rule 6's fork). It answers *is the chosen path
healthy, and did this commit move it* — floors and trends over the corpus. It
does **not** run controlled arms to choose between two futures; that is what
was cut, and re-proposing it needs its own justification, not this seed's.

## Architecture — settled decisions, do not re-open

**The determinism ladder is climbed in stage order, not all at once.** Position
01 computes only metrics decidable from stored artifacts by code: counts,
resolution of declared ids, presence of required sections and fence fields,
gate attempts consumed, exit outcome, wall time, cost, and **cross-rerun
stability** of each of those. No rubric, no scoring prose, no model in the
measurement path. Judged metrics are position 02's subject and are gated on
this position's output.

**Artifacts are the record; scores are recomputed.** A run stores the produced
files plus the run log, keyed by label. Metrics are computed *from* that store
and can be recomputed when a metric's definition changes, so a metric added in
six months can be applied retroactively to every label already captured.
Storing only scores would make the corpus un-reanalyzable, which is the failure
that makes a benchmark a dead end.

**Every metric ships with its noise floor or it does not ship.** A metric's
floor is the spread observed across R reruns of the corpus at one unchanged
commit. `bench compare` reports a delta as `inside noise` / `outside noise`
against that floor, and a metric with no floor recorded is reported as
`unfloored` and excluded from any summary verdict. **Insufficient-data is a
first-class label and is never coerced into a verdict** (Rule 6).

**The corpus is fixed, versioned, and small.** Seeds live in the corpus
directory and change only by an explicit, committed edit — a corpus that drifts
silently makes every historical label incomparable. Small because each item
costs a real Claude run: the roadmap smoke run was ~$2.50 and ~6 minutes for
two stages, so R reruns × N items is the whole budget conversation, and the
corpus is sized to the floor it can afford to measure rather than to coverage.

**Replay isolation.** Each corpus item runs against its own empty scratch
repo, so items cannot see each other's output and a metric never reflects the
order items ran in.

## In scope

A new `bench` verb group (`run`, `compare`, and a `floor` subaction that
executes the repeated-rerun measurement); the corpus directory format and its
versioning; the artifact store under `.plan-tool/bench/`; the deterministic
metric set and its registry; the noise-floor computation and its persistence;
`DATA_CONTRACT.md` rows for the stored label and floor records.

The first corpus targets the **`roadmap`** verb, because it is the newest
surface, its artifacts are small and fully structured, and this session already
has three same-input samples to check the harness's floor computation against.

## Out of scope / Non-goals — the enumerated not-allowed list

Stating "deliver numbers, don't judge quality" in prose does not hold the line.
These are the specific things this position may not grow, and a finding asking
for one of them is deferred, never applied:

- **No LLM judge, rubric, or model-scored metric of any kind.** Position 02's
  subject, gated on this position's floors.
- **No quality opinion.** No metric may assert that an artifact is good,
  better, well-grounded, or well-reasoned. Every metric is a count, a ratio, a
  resolution check, or a stability measure over bytes.
- **No agreement check between two prose artifacts** — not seed-vs-plan, not
  plan-vs-detail, not artifact-vs-brief. This is the specific shape CLAUDE.md's
  rule 5 says to kill rather than tune.
- **No gate, no exit-code flip, no CI blocking.** `bench` reports; a completed
  run exits 0 whatever the numbers say, per the exit-code convention.
- **No control arms, matched baselines, or A/B comparison of two prompt
  variants.** That is the cut #164 mechanism; re-proposing it is separate work
  that must first show it has the power this position's floors would reveal.
- **No auto-tuning.** Nothing reads a metric and adjusts a threshold, prompt,
  or default.
- **No expansion of the corpus to every verb.** One verb, one corpus, this
  position.
- **No shape or length caps** on any artifact, as a metric or otherwise.
- **No parallel fan-out** to make the corpus faster (CLAUDE.md's
  anti-parallelism directive); if a corpus is too slow, it is too big.

## Allowed behavior changes

The new `bench` verb group and its stored artifacts under `.plan-tool/bench/`.
Nothing about `create`, `detail`, `run`, `roadmap`, or any existing surface
changes — the harness observes them through their existing CLI.

## Allowed reorganization

None. The metric registry is new code, not an extraction from an existing
module.

## Verification

A corpus of two items, replayed R times at one commit with a stubbed invoker,
produces a floor per metric; a metric that is constant across reruns floors at
zero spread and a metric fed deliberately varying stub output floors wider.
`bench compare` on two labels captured from the same commit reports every
metric `inside noise`. A metric with no recorded floor is reported `unfloored`
and is absent from any summary. The stored artifacts round-trip: deleting the
computed metrics and recomputing from the store reproduces them exactly.

Hermetic per TESTING.md — the harness takes the same `invoker=` seam every
orchestrator does, and no test spawns a real backend.

## Stop / defer

If the floor measurement shows that **most** deterministic metrics are noisier
than any plausible change effect, stop and report that as the finding: it means
this corpus cannot support a benchmark at an affordable R, and the honest
answer is a smaller claim, not a bigger corpus. File it rather than widening.

Anything surfaced about a specific verb's own variance belongs to that verb's
own entry, not here. (The `roadmap` retry budget was one such question; it
closed 2026-08-05 with no action — `docs/HISTORICAL_BACKLOG_DECISIONS.md`.)

## Group bookkeeping

This group needs an anchor `BACKLOG.md` entry carrying the full arc — position
01 as scoped here, position 02 as the judged-metric layer gated on 01's floors
— per the ordered-efforts convention, and the plan this seed produces updates
that entry when it ships.
