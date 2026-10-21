> **Withdrawn 2026-07-30 — the incumbent (model A) stands. Do not re-open
> without new evidence.** This seed proposed deciding the jira-grade authoring
> model (independent passes vs. jira-canonical intent-first) via a two-arm
> experiment. Its own **Probe 0** — "does `prompts/detail.md` receive any
> plan-body intent prose today?" — was answered against the premise before the
> experiment ran: it does. `## Scope guardrails` / `## Audit guardrails` /
> `## Expected placement` reach the detail prompt through
> `detail.py:extract_plan_guardrails` -> `${plan_guardrails_block}`, carrying
> fence content and no claim surface. That **is** the B-prime mechanism, already
> shipped; what was missing was a populated source. The #181/#182 ceremony
> evidence cited below as this seed's strongest support is explained by that
> channel being empty — the directive sat in `## Architecture`, which the audit
> reads and `detail` does not — so it argues for #161's preservation check, not
> for an authority inversion. Two further reasons not to run the experiment:
> its instrument (identity-keyed conceptual-audit comparison at n=2-3) is the
> shape the arc deliberately cut from stage 01 on 2026-07-29, and the authority
> question already has an owner in **#171**, gated on #169's code-anchored
> probe evidence.
>
> **Salvaged, so nothing here needs re-reading:** the summarization guard, the
> directional rule, the anchoring hazard, the detection-power gate, and the
> correction to #171's "run-grade *derived*" phrasing all moved into **#171**'s
> entry. The measured detail-side consequence of a folded fence moved into
> **#161**. The `## Out of scope` channel gap this surfaced was fixed directly
> (see `PLAN_FORMAT.md` s."Plan-level scope fence").
>
> Consequence for the plan: **step 4 of `2-jira-grade-01-detail-instrument` is
> not blocked** and executes as written — this seed's own B-prime analysis
> concluded step 4's from-scratch design survives the pivot intact.
>
> Preserved for history; do not edit.

# Seed: Decide the jira-grade authoring model — independent passes vs intent-first co-authoring

**Decision seed, drafted 2026-07-29.** Origin: user direction during stage-01
execution (8/10 steps green, step 4 — the authoring mode — next and unbuilt).
The user's own framing: *"the right answer for building reliably solid plans is
to do some degree of both jira and implementation planning at the same time"*,
and, explicitly, *"this pivot is more of a gut feeling than an objective
decision — I want to make sure we are making the correct call."*

That framing is this seed's contract: it exists to **make the call correct,
not to presume it**. It is a decision seed with falsifiers and a default, not a
build plan. The burden of proof sits on the pivot — the incumbent design
survived seventeen audit rounds; a gut feeling earns its restructure by
evidence, or it defers.

Backlog reconciliation: this seed bears on **#169** (arc roadmap authority),
**#171** (stage 05 inversion), and **#164** (arc history), and coordinates with
**#181/#182** (risk-profile signal threading). The resulting plan (or the
recorded decision, if no plan is authored) must update those entries; authoring
this seed alone updates nothing.

## Problem statement

Stage 01 as executed ships the jira-grade contract (`jira_grade.py`), the
collision-safe paths, and all three read-side consumers — `jira --grade jira`,
`run --detail-grade jira`, `completeness-audit --grade jira`. All of that is
**authoring-model-independent** and is not at stake here.

The one unbuilt authoring surface is step 4, and its current design commits to
a model: jira-grade is authored **from scratch, as a second independent pass**
— its own prompt, its own gate, bypassing the entire run-grade quality
machinery, never reading `Step.detail`. Two consequences follow:

1. **Two independent passes over one step can drift from birth.** Nothing ties
   what the intent artifact promises to what the implementation detail builds
   except a later audit catching it.
2. **The intent signal arrives last.** Step 4 runs after every consumer, and in
   any per-step workflow the run-grade detail (the thick, implementation
   artifact) exists before the compact intent contract does. Intent is
   summarized after the fact rather than stated first.

The hypothesis under decision, as the user sharpened it (2026-07-29): **the
jira-grade plan is the canonical definition of the plan's structure; the
run-grade (implementation) detail is the proof that each intent is buildable;
and proof failures feed back into deliberate amendments of the canonical
artifact — when needed, and only then.** Authority flows jira → run. Evidence
flows run → jira. Neither artifact is ever mechanically produced from the
other.

The theorem/proof framing is load-bearing, not decorative: a proof can fail in
a way that indicts the theorem — that is the feedback loop — but a theorem is
never *derived from* its proof. The moment the jira artifact is written by
looking at the implementation detail, it stops being a claim the proof can
falsify.

The hypothesis is tested in its **fence-coupled form, B′** (see the candidate
models): the coupling channel that delivers `detail` its intent signal is the
same channel that would let the two artifacts agree by construction, so the
tested arm threads only the fence sections and withholds the claim sections —
preserving the audit lever the incumbent's independence buys while capturing
the signal the #181/#182 evidence measured as missing.

## Evidence in hand (dated; judge it, don't inherit it)

- **For the hypothesis — the #181/#182 measurements (2026-07-29,
  `remove-vendor-scraper-poc` session).** Ceremony enters at
  detail-authoring time when no intent/proportionality signal is present:
  `detail`, running blind, wrote an out-of-band secret-export gate for a dead
  POC's placeholder secret. Retro-fitting the directive into the plan body
  afterward did **not** repair it — findings moved 18 → 17 and HIGH rose
  3 → 5, because the new findings were contradictions against ceremony already
  written. And a seed preamble does not survive `create`. Recorded conclusion:
  **the signal must be persisted and present before `detail` runs.** The
  jira-grade artifact's `Intent` / `Constraints` / `Out of scope` is exactly
  such a signal, generalized from a one-field risk tier to the whole intent
  contract. This is the strongest objective support the gut feeling has.
- **For the hypothesis — Decision 1 (communication-first, 2026-07-22).** The
  arc's settled value ordering says the communication artifact is the tool's
  primary value. Intent-first authoring produces it at the moment of maximal
  intent clarity; author-it-last produces a post-hoc summary of an
  implementation.
- **Against the hypothesis — the projection trap.** Step 4's from-scratch
  design is deliberate: an artifact *derived from* (or co-written with) the
  implementation detail tends to degrade into a compressed summary of that
  detail — inheriting its blind spots, failing the plain-English contract, and
  losing the independent-restatement property that makes contradictions
  between the two artifacts detectable at all. Round 17's value came from two
  artifacts that could disagree.
- **Caution for the evaluation, not the design — the reflexive hazard (round
  17).** A thinner artifact yields a quieter audit, and quiet reads as
  quality. Any evaluation of authoring models must therefore never score
  "fewer findings" without checking *which* findings and whether the artifact
  simply gave the audit less to judge.

## The candidate models

- **A — Independent passes** (step 4 as written). Two authoring events, no
  shared input beyond the plan itself. Drift is possible from birth; audits
  are the only coupling. Incumbent, audit-hardened.
- **B — Jira-canonical with proof feedback, full coupling** (the user's
  vision as first stated). The jira-grade artifact is authored first and is
  **canonical for the plan's structure**. The run-grade detail is authored
  *against* it — grounded on the whole artifact via #182's plan-directives
  channel (build the channel once; the risk tier and the intent contract both
  ride it) — and serves as the **proof of buildability**: implementation
  planning either witnesses the intent or fails in a way that indicts it. A
  proof failure surfaces as a **finding against the canonical artifact**,
  walked through a gated amendment channel; it never silently edits the jira
  artifact. Each artifact keeps its own contract and gates; run-grade remains
  the execution artifact. **Held in reserve, not the tested arm** — full
  coupling includes the claim sections, and the same pipe that delivers the
  signal lets the two artifacts agree by construction (see B′).
- **B′ — Jira-canonical, fence-coupled, claims-independent** (the tested
  pivot arm). B with a deliberately narrower grounding pipe, split on a
  **fence-vs-claims** line through the five-section schema
  (`jira_grade.py:JIRA_GRADE_REQUIRED_H2S`):
  - **Threaded to `detail`:** `Intent`, `Constraints`, `Out of scope` — the
    proportionality/boundary signal the #181/#182 evidence measured as
    missing. A fence tells detail what *not* to build; it carries no claim to
    agree with by construction. Threading `Intent` is safe *because of* a
    shipped guard: the plain-English gate forbids mechanism vocabulary in the
    jira artifact, so the pipe carries intent-level prose by contract.
  - **Withheld:** `Change`, `Done when` — the claim surface
    `detect_claim_vs_delivery` and `detect_orphaned_deliverable` compare
    against delivery. Withholding them forces the detail to *independently*
    restate what is built and what done means, so the audit keeps the lever
    round 17's best finding depended on.

  Authority is unchanged from B — jira-canonical, gated amendments with
  provenance — B′ is B with a narrower pipe, not a third authority model. It
  also mutates step 4 less than B: the jira pass keeps its from-scratch,
  never-reads-`Step.detail` design intact; the changes land on the run-grade
  side (a fence-section grounding input to `detail`) plus the jira-first
  ordering rule. The extraction is deterministic — `jira_grade.py`'s section
  parser already slices a body by token — so the pipe needs no new judgment
  surface.
- **C — Co-generation.** One authoring call emits both artifacts. Named to be
  rejected, with the reason recorded so it is not relitigated: a single call
  cannot serve two prose contracts, and the compact artifact collapses into a
  summary of the thick one — the summarization trap with no audit able to
  catch it, because the two artifacts are no longer independent restatements.

## The summarization guard (first-class requirement of models B/B′)

The failure mode that kills the vision is drift of the canonical artifact into
a **summary of the implementation** — through co-generation (model C), through
"sync" edits after detail authoring, or through amendment-by-accretion, where
each proof cycle deposits a little mechanism vocabulary into the intent until
the two artifacts agree by construction. Once that happens they stop being
independent restatements, contradictions become undetectable, and the audit
loses its lever — round 17's best finding existed *because* the artifacts
could disagree.

The trap is symmetric, and the guard must be too: **never summarize upward,
never project downward.** Run-grade detail mechanically projected from the
intent contract inherits the thin artifact's blind spots and calls the result
proof; a jira artifact summarized from the detail inherits the implementation's
framing and calls the result intent. Stage 05's own "run-grade *derived*"
phrasing (#171) errs on the second axis — under this vision both artifacts get
genuine authoring, and the relationship is theorem/proof, not
source/compilation. Carry that correction into #171 if B wins.

The coupling itself has a subtle form of the trap: **anchoring**. The pipe
that supplies `detail` its signal is the same channel that lets the detail
agree with the intent by construction — under which claim-vs-delivery-class
findings *fall*, and the drop is indistinguishable from a quality win unless
detection power is demonstrated rather than assumed. B′'s fence-vs-claims
split exists to close the mechanical half of that; the guards below close the
rest.

Guards, layered — the first two are shipped, the rest are design obligations
on any B/B′ implementation (and on the experiment's hand-run stand-ins):

1. **Structural (shipped):** the closed five-section schema has no section
   where implementation narrative belongs, and unknown H2s are blocking.
2. **Prose (shipped):** the plain-English gate.
3. **Directional (rule):** no run-grade surface ever writes a jira artifact.
   Amendment flows through one explicit channel — detection unconditional,
   mutation gated, the same shape as `escalate_to_split` and `scope-out` —
   and it is the artifact-pair analog of the standing reconcile direction
   rule: `reconcile-plan` must not rewrite intent from implementation, and
   neither may this loop.
4. **Provenance (rule):** every amendment cites the proof failure that forced
   it — **no silent sync**. An edit to the canonical artifact that cannot name
   its finding is summarization drift by definition.
5. **Pipe allowlist (rule, B′):** the grounding block is built from
   `jira_grade.py`'s section parser against an explicit allowlist of the
   three fence tokens (`intent`, `constraints`, `out`); `Change` and
   `Done when` never enter `detail`'s prompt. Deterministic and, when the
   pipe ships, tested — a test asserts the rendered grounding block contains
   no text from the two withheld sections. During the experiment the same
   rule is applied by hand: the injected block is the three sections
   verbatim, nothing more.
6. **Detection-power gate (rule):** any coupling design must prove the audit
   lever survived before it is trusted — plant one **seeded contradiction**
   (a `Done when` criterion the detail deliberately omits, or a `Change`
   claim delivered differently) and confirm `claim-vs-delivery` /
   `orphaned-deliverable` still fire against the coupled pair. A quieter
   audit is only evidence when detection power is demonstrated, not assumed.
7. **Anchoring read (rule, B′):** after each coupled detail authoring, read
   the generated detail for **parroted fence prose** — echoed sentences from
   the threaded sections are the small-scale form of anchoring and are
   recorded as a finding, not passed as color.
8. **Drift detection (candidate, design later, not a commitment):** re-run the
   contract + prose gates after every amendment, and consider a deterministic
   mechanism-vocabulary check on jira artifacts — prose narrating *how*
   (helper names, call-order narration) beyond the code anchors the gate
   already exempts.

## What would falsify the hypothesis (B′ over A)

1. Fence-grounded detail shows **no reduction in material finding classes**
   (ceremony/suppression-shape, files-coherence drift, claim-vs-delivery)
   versus independent-pass detail on the same steps. This falsifier is what
   promotes the reserve arm: if the fence-only signal is not enough, the
   remaining question is whether full-coupling B is — run it then, and only
   then.
2. The first-authored jira artifact **degrades**: it fails its own
   plain-English/compactness gates, or claim-vs-delivery findings *rise*
   because the intent contract drifts from what the detail actually builds.
3. The grounding thread **costs more than it pays**: threading the fence
   sections into `detail`'s prompt measurably degrades detail quality (budget
   pressure, anchoring the model on intent prose instead of code — the
   anchoring read, guard 7, is the instrument).
4. **Amendment churn.** If most proofs force an intent amendment — the
   canonical artifact cannot be stated stably before implementation planning —
   then jira-canonical is the wrong authority direction for this domain: the
   "proof" is actually *discovering* the plan, and the theorem is being
   written by the proof one amendment at a time (summarization by
   installments). "When needed" must stay exceptional; the experiment
   measures the rate — counting **both streams**: contradictions hit during
   detail authoring (fence sections) and contradictions the audit surfaces
   later (the withheld claim sections). Both are proof failures indicting the
   theorem.
5. **The seeded contradiction goes undetected** (guard 6). The withheld claim
   sections leaked — plan-body prose reaching the prompt (probe 0's
   question), or the injection carrying more than the fence — and the
   coupling has collapsed into co-agreement: artifacts that cannot disagree.
   This ends the variant outright; do not patch the pipe and retry inside the
   same decision window.

Any one of these, cleanly observed, ends the pivot; the seed archives with the
reason recorded.

## Decision experiment (cheap, anchored, no arc restructure)

- **Probe 0 — the channel.** Determine whether `prompts/detail.md` receives
  any plan-body intent prose today. #181's evidence says no frontmatter field
  reaches it; whether body prose does is unmeasured. If nothing reaches it,
  the experiment needs the minimal thread only — hand-injection or the #182
  context block — not a shipped feature. Probe 0 also baselines the **leak
  check**: if plan-body prose already reaches the prompt, the withheld claim
  sections may leak around the pipe, and falsifier 5 must be judged against
  that baseline.
- **Arms — A vs B′; full B held in reserve.** On 2–3 real steps of the next
  plan authored in this repo (stage 02's plan is the natural corpus — its
  seed is ready and its authoring is the next `create` regardless): **(A)**
  current order, detail authored blind; **(B′)** a jira-grade artifact
  authored first (hand-authored is fine — the contract validator already
  exists to gate it) with **only the three fence sections** (`Intent`,
  `Constraints`, `Out of scope`) supplied to `detail` as grounding, applied
  by hand per the pipe allowlist (guard 5). Full-coupling B is not a first-
  round arm — B′ dominates it analytically (the same measured benefit,
  strictly less anchoring risk) — and runs only if B′ fails falsifier 1.
  In arm B′, run the feedback loop by hand: every contradiction the detail
  pass hits is recorded as a finding against the jira artifact, and any
  amendment cites its finding (guard rule 4). Track the **amendment rate**
  (falsifier 4, both streams), and after each amendment re-run the contract +
  prose gates and read the diff for mechanism vocabulary (summarization
  drift). After each coupled authoring, run the anchoring read (guard 7).
- **The detection-power check — once per coupled arm, before its results
  count.** Plant one seeded contradiction (guard 6) in a B′ pair and confirm
  the audit fires. If it does not, falsifier 5 has triggered and the arm's
  finding-class comparison is void — a quieter coupled audit means nothing
  until the lever is proven alive.
- **Instruments — existing only, forced fresh.** The deterministic battery's
  finding classes, material conceptual findings against the detail, and the
  jira-grade contract + prose gates on the artifact itself. Force fresh audits
  every time — the conceptual audit **reuses cached results unless stale** and
  the saved report does not say so (this arc's own discovery; two identical
  reports prove nothing).
- **Compare finding classes and identities, never counts.** Decision 8's
  rationale carries: sampled prose deltas are noise; anchored classes are not.
  A quieter audit is only evidence when the *same* material classes shrink.
  The three-snapshot trajectory window applies if any arm is iterated.

## Consequences by outcome

- **B′ wins:** step 4 is re-scoped **before execution** — and the re-scope is
  smaller than full B's would have been: the jira pass keeps its from-scratch,
  never-reads-`Step.detail` design; what changes is the jira-first ordering
  rule, the fence-section grounding input to run-grade `detail` (pipe
  allowlist, guard 5, shipped with its no-leak test), and the gated amendment
  channel as the feedback surface. Stage 05's inversion stops being a terminal
  claim and becomes the starting posture — and #171's own "run-grade
  *derived*" phrasing is corrected to the theorem/proof relation (see the
  summarization guard: derivation downward is the mirror trap). Stage 02's
  gate question shifts from *"is the thin artifact good enough alone?"* (which
  its self-selected corpus may never answer cleanly — open question 6) to
  *"does intent-first authoring reduce implementation-detail defects, at an
  amendment rate that stays exceptional?"*. #164/#169/#171 are updated in the
  same change.
- **B wins (reachable only through the reserve arm):** same consequences as
  B′, with the pipe widened to the full artifact — and guard 6's detection-
  power proof becomes a standing obligation rather than a one-time check,
  because full coupling has no structural withholding to lean on.
- **A stands:** step 4 executes as written; this seed archives with the
  falsifier that ended it; stage 05 keeps its existing gate.
- **Inconclusive after the three-snapshot window: A stands.** The incumbent is
  the audited design; the pivot is the hypothesis. Record the open question
  against #171 rather than iterating indefinitely.

## Scope contract

- **Outcome:** one recorded A/B′/B/C decision with its evidence, plus only
  the step-4 detail re-scope and #164/#169/#171 updates that decision implies.
- **In scope:** probe 0, the two-arm experiment (A vs B′; the reserve B arm
  only if falsifier 1 promotes it), the seeded-contradiction detection-power
  check and the hand-applied pipe allowlist (guards 5–7, experiment-side),
  the decision record, step 4's detail file (unbuilt — re-scoping it mutates
  no shipped work), the named backlog entries.
- **Out of scope / Non-goals:** churn metrics, control arms, or any
  finding-count comparison (Decisions 4 and 8 stand); building stage 05;
  editing shipped steps 1–3 and 5–9 or their artifacts; new frontmatter
  fields (that is #181/#182's lane — coordinate, don't duplicate); model C
  beyond the recorded rejection.
- **Allowed behavior changes:** none shipped — the experiment's grounding
  thread stays hand-injected or flag-gated until the decision lands.
- **Verification:** the decision names which falsifiers were tested and what
  each showed; the detection-power check ran before any coupled arm's
  comparison was trusted, and its result is recorded; every audit consumed
  was forced-fresh; the backlog entries reflect the outcome.
- **Stop / defer:** anything the experiment surfaces about `detail` or the
  audit that is not the authoring-model question goes to `BACKLOG.md` /
  `BUG_BACKLOG.md`, not into this seed's scope.
