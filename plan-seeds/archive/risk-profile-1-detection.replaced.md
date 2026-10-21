> **Replaced**: this file has been superseded by `docs/implementation-plans/2-risk-profile-1.md`.
> Preserved here for history; do not edit.

# Risk-profile detection in `create`: classify the seed's work-shape and persist the tier

Seed for BACKLOG **#181**. Sibling: `risk-profile-2-honoring.md` (#182) consumes the
field this seed introduces — land this one first. The pair shares one worked example,
recorded fully here and referenced from the sibling.

## Overview

Teach `create` to detect, at proposal time, what kind of work a seed is asking for —
a brute-force deletion of unconsumed code, a mechanical rename, a config flip, versus
a load-bearing feature on a live surface — propose the resulting **risk-profile tier**
to the operator (accept / override / decline, the same contract as the existing
multi-plan split proposal), and persist the accepted tier in the plan frontmatter as
`risk_profile: low | standard | high` plus a one-line rationale, so downstream passes
can read it instead of guessing.

The tier is a *declaration with an owner*, not an automation: the classifier only
proposes, the operator confirms, and the persisted rationale is challengeable in
review. On ambiguity or classification failure the tier is `standard`, which is
byte-for-byte today's behavior.

## Problem statement

The authoring and audit pipeline calibrates ceremony for load-bearing work because it
has no signal saying otherwise. Worked example (example-app-amplify,
`remove-vendor-scraper-poc`, 2026-07-28/29):

- The change: delete a dead POC — **323 lines of unconsumed code** (a weekly
  headless-Chromium scraper Lambda nothing reads), one placeholder-adjacent secret,
  three orphaned dependencies, one runtime-created SSM parameter.
- What the pipeline produced: an 8-step plan with a **920 KB / 1,228-line detail
  bundle**; four completeness rounds trending **24 → 27 → 30 → 22** findings; and
  audit-invented ceremony proportionate to a live integration — credential-export
  custody rules, a team-confirmation gate, inter-deploy ordering rules, a
  baseline-capture synth-diff gate, cross-region IAM analysis for an instance where
  the resource never existed. All four HIGH findings surviving round 4 were
  proportionality errors, not defects.
- `convergence` twice diagnosed *spinning* and recommended a destructive re-seed.
- **The fix that worked was one hand-written seed paragraph** stating the risk
  profile: *"This is a brute-force deletion… no capability to preserve, no consumer.
  Do not add export gates, credential-custody procedures, confirmation checkpoints,
  or multi-deploy ordering rules."* With that sentence present, the same pipeline
  behaved.

That sentence is what this seed mechanizes — detected and proposed at create time
instead of hand-authored after five audit rounds. The archived heavyweight plan and
its detail bundle are preserved as the negative reference:
`example-app-amplify/docs/implementation-plans/archive/remove-vendor-scraper-poc.replaced.md`
and `…/archive/plan-details/remove-vendor-scraper-poc.replaced/`.

### Why a seed convention cannot substitute for a persisted field

Measured the same session, and this is the decisive argument for the frontmatter
field over "just tell authors to write a proportionality paragraph":

- The lean seed carried that paragraph explicitly. **`create` dropped it** —
  `grep -niE 'brute.force|proportionate|ceremony'` over the generated plan returns
  zero matches. The directive existed only in the seed, which `create` archives.
- Consequence: by the time `detail` authored the per-step bundle, no downstream
  pass could see the tier. `detail` then wrote ceremony into the step files —
  step 2's detail required "the live value is exported to the team's out-of-band
  secret store before that environment's deploy" for a placeholder secret on a
  dead POC.
- **Retro-fitting does not repair it.** Pasting the directive into the plan *body*
  afterwards — where a standalone audit does read it — moved the audit only
  18 → 17 findings and pushed HIGH **up** 3 → 5, because the new findings were
  contradictions against ceremony already written into the bundle, not gaps.

So the tier must be **persisted on the artifact and present before `detail` runs**,
not stated in an input that is consumed and archived, and not bolted on afterwards.
A frontmatter field is machine-readable, survives every pass, and reaches `detail`
at authoring time — which #182 shows is the load-bearing consumer.

**Ordering note for whoever implements this pair:** persistence (#181) is only
useful if it lands before a plan's `detail` bundle is authored. Re-tiering an
existing plan after the fact requires a `detail --reconcile --all` sweep to rewrite
the bundle; the field alone will not undo ceremony already written.

## Architecture

### Where the detection rides — and the seam that does NOT fit

The natural-looking home is the distill pass (`propose_distilled_seed_from_claude`,
`plan_tool/create.py` — returns a `DistillOutcome` of single / split / passthrough,
checkpoint-memoized as `create-distill-seed.json`, runs once per create and never
inside the convergence loop; prompt `plan_tool/prompts/distill-seed.md`, whose
`## Decide: one plan, or many?` section is the existing early-detection precedent).

**But the distill pass is size-gated and the classification must not be.** Seeds
below `_DISTILL_SKIP_BELOW_BYTES` (16 KB) skip distillation entirely (call-site
branch logs `propose_distilled_seed … skipped, already_canonical`) — and small seeds
are the *most* likely to be lean deletions. The worked example's lean seed was
10.4 KB; a distill-riding classifier would never have seen it. So the classifier is
its own step in the create flow that runs on **both** branches: ride the distill
call's response schema when distillation runs (no extra subprocess), and issue a
small standalone classification call on the skip path. Both paths land on one
code path that yields the proposal.

### Proposal plumbing precedent

The split proposal returns through `CreateResult(split_proposal=SplitProposal(…))`
and the caller walks the operator through accept/decline. The tier proposal follows
the same shape but does not abort plan creation — it is a field decision, not a
routing decision. Non-TTY `-y` behavior is a design decision to lock at plan time:
recommended default is *accept the proposed tier when the classifier is confident,
fall back to `standard` when it flags ambiguity* — never block a headless create on
a question, mirroring `DistillOutcome`'s passthrough-on-parse-failure semantics.

### Persistence

`risk_profile` becomes a top-level plan frontmatter field beside `enforce_step_tests`
(owners: `plan_tool/schema.py` + `plan_tool/parser.py` pydantic models, `validate`,
`PLAN_FORMAT.md`). Persist the tier **and** its one-line rationale (e.g.
`risk_profile_rationale:` or a structured sub-object — pick one at plan time); the
rationale is what makes the tier reviewable rather than oracular. Absent field ≡
`standard` everywhere, so no existing plan changes behavior.

### Classification signals (cheap, mostly deterministic; the prompt decides, these ground it)

- Deletion-dominant scope: imperative "delete/remove/retire" step verbs, zero
  `creates:` on production-code surfaces, net-negative footprint.
- An explicit no-consumer claim in the seed ("nothing reads it", "never wired to a
  product surface") — presence of the *claim* is the signal; verifying it stays the
  plan's job.
- No new external contract, no schema/API change, no new runtime surface.
- Counter-signals forcing `standard`/`high`: named consumers, data migration,
  auth/authz surface, anything the seed itself calls load-bearing.

### Scope contract (inherited verbatim from BACKLOG.md #181)

- **Outcome:** `create` proposes a risk-profile tier for the seed, the accepted tier
  is persisted in plan frontmatter with a one-line rationale, and a deletion-shaped
  seed like `remove-vendor-scraper-poc` gets `risk_profile: low` proposed without
  hand-authoring it.
- **In scope:** `plan_tool/create.py` (proposal plumbing beside `SplitProposal`),
  `plan_tool/prompts/distill-seed.md` (or one sibling prompt), the frontmatter
  schema + `validate`, `PLAN_FORMAT.md`, `tests/`.
- **Allowed behavior changes:** the new proposal prompt at create time and the new
  frontmatter field; nothing else user-visible.
- **Allowed reorganization:** none.
- **Stop / defer:** calibration of the classification prompt against a corpus is
  #182-adjacent follow-up; file separately rather than growing a corpus harness
  here.

## Scope of work

1. **Add the `risk_profile` frontmatter field** (`low|standard|high`, default
   `standard`, plus rationale) to the plan schema, parser, `validate`, and
   `PLAN_FORMAT.md`. Absent ≡ `standard`; round-trips through every existing
   read/write path untouched.
2. **Add the classification pass to `create`** on both branches of the distill size
   gate: extend the distill response schema when distillation runs; a small
   standalone call on the skip path. One shared code path produces the
   `(tier, rationale, confident)` result; parse failure ⇒ `standard` passthrough,
   mirroring `DistillOutcome`.
3. **Add the operator proposal step**: TTY — propose tier + rationale, operator
   accepts/overrides/declines (decline ⇒ `standard`); non-TTY `-y` — accept only a
   confident proposal, else `standard`; record the decision in the run log either
   way.
4. **Write the accepted tier into the generated plan's frontmatter** and surface it
   in `create`'s completion summary so the operator sees what was recorded.

## Out of scope

- Consuming the tier in detail authoring, completeness audit, or apply — that is
  the sibling seed (`risk-profile-2-honoring.md`, #182). Without it this field is
  still a paying declaration: the seed author no longer hand-writes a defensive
  preamble, and reviewers see a challengeable tier.
- Auto-accepting an unconfident classification, or any path with no operator
  override.
- Re-classifying or migrating existing plans; touching split-proposal behavior
  itself; `annotate` / `scope-out` seed flows.

## Risks

- **Misclassification in the dangerous direction** — calling load-bearing work
  `low` suppresses scrutiny exactly where it is needed. Mitigations: propose-only
  with operator confirmation; `standard` on ambiguity, failure, or decline;
  persisted rationale so the call is visible and challengeable; counter-signals
  (named consumer, migration, auth surface) hard-force at least `standard` in the
  prompt contract. #182 adds the audit-side backstop (`tier-challenge`).
- **The two-branch seam drifts** — classification behavior diverging between the
  distill path and the skip path. Mitigation: one shared result type and one shared
  proposal/persist code path; branch-parity tests.
- **Checkpoint interaction** — the distill checkpoint memoizes its response; the
  classification result must be part of the memoized payload (or its own
  checkpoint) so a resumed create does not silently re-classify.

## Testing

- Unit: deletion-shaped seed fixture → `low` proposed; feature-shaped → `standard`;
  ambiguous / parse-failure / declined → `standard`; counter-signal fixture (named
  consumer) → never `low`.
- Branch parity: the same seed classified identically above and below the distill
  size gate.
- Schema: `validate` accepts, rejects unknown tier values, round-trips; absent
  field reads as `standard`.
- Non-TTY: `-y < /dev/null` create records a tier without blocking; unconfident
  proposal lands `standard`.
- Characterization: the archived `remove-vendor-scraper-poc` lean seed (10.4 KB,
  skip-path) proposes `low` with a deletion rationale.

## Acceptance criteria

- A deletion-shaped seed run through `create` gets `risk_profile: low` proposed,
  and on acceptance the generated plan's frontmatter carries the tier and
  rationale.
- A seed with a named consumer or new contract is never proposed `low`.
- `validate` enforces the field; plans without it behave exactly as today.
- The proposal renders on both sides of the distill size gate.
- Run log records proposal, decision, and decision mode (TTY accept / override /
  non-TTY confident / fallback).

## Deferred

- Downstream consumption of the tier — sibling seed #182.
- Corpus-based calibration of the classifier prompt.
- Tier-aware behavior in `run --mode` review surfaces and `jira` sizing.
