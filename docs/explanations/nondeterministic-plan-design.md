# Plan design for non-deterministic features

How to design a plan that adds Claude-judged (non-deterministic) behavior to
the tool so its completeness audit converges. Two plans spun before this was
written down — `impact-recurrence-structural-stop` (judged-impact
classifier; 10 correctness findings, 0 steps executed) and the jira-grade
side-by-side plan (re-seeded as the `jira-grade` group; spin verdict in
[retained historical summary](../evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)).
Both spun for design reasons, not prose reasons. This doc is the pattern
that shipped cleanly instead.

## Why these plans spin

The completeness audit judges plan prose against contracts and code. Judged
behavior cannot be pinned as fact — you cannot state today what a future
Claude call will decide — so a plan that *describes* judged outcomes in
factual prose hands the audit an inexhaustible supply of contradictions.
Editing the prose does not converge it; the contradiction is structural.

A finding that survives three audit/apply rounds is a property of the
decomposition. Classify its **fold** before editing anything:

| Fold | Meaning | Real example |
|------|---------|--------------|
| Fence conflict | The scope contract forbids machinery the acceptance criteria require | `audit-churn` (CRITICAL): the fence banned audit changes while the gate required measuring churn on a bundle the audit could not read |
| Missing substrate | The plan asserts a property no step purchases | `paired-run-isolation`: "matched baseline" with no isolation step |
| Self-inconsistent gate | Acceptance contradicts the plan's own risk mitigation | `metric-noise`: a one-pair trial could pass a gate the noise mitigation says must read indeterminate |
| Fused concerns | One step mixes work that audits under different regimes | `step-1-type-purity`: refactor + new behavior in one step, so characterization tests cannot isolate compatibility |

Fixing a fold means changing the decomposition or the fence — see the
reseed advisor (BACKLOG #168, `plan-seeds/reseed-advisor.md`) for the
directed version of this analysis.

## Rule 1: deterministic core, judged edge

Decompose every non-deterministic feature into four layers (the MISSION
principle *deterministically driven non-determinism*):

1. **Deterministic assembly** — gather inputs, evidence, and candidate
   structure with no Claude call.
2. **One directed judged call** — a forced output contract (closed
   vocabulary, required fields), not an open-ended ask.
3. **Deterministic response gates** — anchors resolve, vocabulary is legal,
   every element maps to a disposition; a failing reply re-prompts with the
   violation named (the `--iterate` pattern).
4. **Deterministic consumption** — persistence, counting, thresholds,
   rendering.

Only layer 2 is non-deterministic. Everything the audit reads — inputs,
schema, gates, dispositions — is deterministic, so the plan's claims are
checkable and stable. A shipped exemplar is
`launcher.py:escalate_to_split` (frozen `EscalateResult`, `outcome` enum, only
`applied` mutates).

## Rule 2: pin the shape, never the content

Plan and detail prose commit to: the input evidence, the output schema, the
gates, and a **total disposition map** (every possible response shape has
exactly one defined handling). They never commit to what the judge will
find — counts, specific classifications, or "the model will identify X."

- Bad criterion: "the audit identifies the three seeded contradictions."
- Good criterion: "a fixture with a seeded contradiction yields a finding
  that passes the anchor gate; an unanchored reply is re-prompted with the
  violation named."

A criterion about judgment *content* is a fact the next audit pass can
contradict; a criterion about *contract conformance* is not.

## Rule 3: climb the determinism ladder before adding a judge

When a design needs "the tool decides X" and X is a judgment, take the
highest rung that answers the question:

1. **Restructure so the question disappears** — shrink the fact surface
   instead of judging it. Keep the artifact sufficient to ground its consumers.
2. **Mechanical check** — extract the deterministically checkable subclass:
   path/symbol resolution, promised-vs-consumed contracts across steps,
   duplicate placements. Every class moved out of the sampled audit is
   variance permanently removed.
3. **Observation over prediction** — let a consumer or an execution answer
   it. Role asymmetry is the lever: an auditor is rewarded for producing
   findings and never returns empty; a consumer is rewarded for completing
   the task and reports only what stopped it (for example, a real `run`).
4. **Counting over classifying** — recurrence with stable identity across
   independent passes or sidecars. It is deterministic given the sidecars;
   pass-to-pass variance becomes the noise filter.
5. **A judged classifier — last resort** — only with a forced closed
   taxonomy, anchored outputs, deterministic gates, and a total disposition
   map (Rule 1). A judged classifier stacked on another judge to make it
   "smarter" regresses the problem; that is how the impact family spun.

## Rule 4: gates for judged output

- **Closed vocabulary.** Enums and forced taxonomies, never free-prose
  verdicts. An unknown token is a gate failure, not a new category.
- **Anchoring.** Every judged claim cites a point of use (file, step,
  section) that a gate can resolve. Unanchored critique is rejected.
- **Totality.** Every response element maps to exactly one disposition —
  apply / recommend / defer / error. No "other."
- **Recommend-only default.** Detection and recommendation are
  unconditional; mutation sits behind an apply gate (`--apply` + confirm,
  `-y` as the deliberate bypass). See the structural-remedy gates.

## Rule 5: fences that hold under audit

- **Fence-vs-acceptance coherence, checked at seed time.** For each
  acceptance criterion ask: *which step purchases the machinery this
  requires, and does the fence permit that step?* A criterion whose
  machinery the fence forbids is a fence conflict no prose edit can close.
  Either amend the fence narrowly and explicitly (the grade-aware
  audit-grounding amendment in `docs/implementation-plans/2-jira-grade-01-detail-instrument.md`
  is the template: name the amendment, its limit, and instruct audits not
  to re-raise it) or drop the criterion.
- **Pin the stage's tool state.** For ordered work, each seed declares what
  exists when its plan starts and names the later stages it must not reach
  into; audits judge against that state only, routing later-stage concerns
  as `[out-of-scope-deferred]` (see [`TRACKING.md`](../TRACKING.md)'s "Ordered efforts: seed groups
  and staged scope" directive; prefer `--audit-passes 1` for fenced plans).
- **Never gate a plan on measuring its own judged behavior with an
  instrument it doesn't build.** That was the `audit-churn` CRITICAL: the
  measurement the gate demanded was impossible inside the fence.

## Rule 6: measuring judged behavior

- Decide which question you are asking. A **decision** question (choosing
  between two futures) needs controls and matched baselines. A
  **monitoring** question (is the chosen path healthy?) needs floors and
  trends over real usage. Do not build a controlled experiment to validate
  a decision already made — reframe it as monitoring (the stage-03
  quality-ledger re-scope).
- **Predeclare all interpretation** — formulas, floors, tolerances, sample
  requirements — before evidence exists. A single observation caps at
  indeterminate; insufficient-data is a first-class label, never coerced.
- **Variance is signal.** Trust agreement across independent samples, not
  any one sample; a metric two evaluators can compute differently from the
  same evidence is not a metric yet.

## Rule 7: prose and the convergence tail

- Write judged-feature prose in plain, concise English (#167's rubric):
  describe the contract, say each thing once, keep every anchor and
  example.
- Record decisions **as taken**, with rationale, where audits will read
  them. A surviving hedge ("aligned with or sequenced after") is an
  audit-churn generator — resolve it or scope it out.
- Keep refactor and feature in separate steps (`change_type` purity).
- Drive the tail under the three-snapshot window (BACKLOG #125): converged
  or confirmed-low-yield finishes; a recurring finding means classify its
  fold (table above) and fix the structure — do not keep editing prose.

## Seed-time checklist

- [ ] Every judged behavior has the four layers of Rule 1, and the plan's
      steps map to them.
- [ ] No acceptance criterion states judgment content; all state contract
      conformance (Rule 2).
- [ ] Each judgment sits on the highest reachable ladder rung (Rule 3),
      with a sentence saying why the higher rungs don't answer it.
- [ ] Gates: closed vocabulary, anchoring, totality, recommend-only
      default (Rule 4).
- [ ] Every acceptance criterion's machinery is purchased by a named step
      the fence permits (Rule 5).
- [ ] Any measurement is typed decision-vs-monitoring with predeclared
      interpretation (Rule 6).
- [ ] No hedged decisions; refactor/feature steps separated; stage tool
      state pinned if the work is ordered (Rule 7 / Rule 5).
