> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Risk Profile 1
intent: Prevent low-risk mechanical work from accumulating load-bearing ceremony by
  preserving an operator-owned, reviewable risk signal from the moment a plan is created.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/risk-profile-1-detection.md
steps:
- id: 1
  title: Add an explicit risk-profile declaration and a legacy standard fallback
  intent: Give downstream passes a durable, reviewable work-risk declaration while
    preserving the distinction between a legacy omission and a newly recorded standard
    decision.
  files:
  - plan_tool/schema.py
  - plan_tool/parser.py
  - plan_tool/concept_sync.py
  - plan_tool/scope_out.py
  - plan_tool/__init__.py
  - PLAN_FORMAT.md
  - tests/test_parser.py
  - tests/test_concept_sync.py
  - tests/cli/test_inspect_cmds.py
  - tests/test_scope_out.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/risk-profile-1/01-explicit-risk-profile-declaration.md
  status: done
- id: 2
  title: Classify seed-fed single-plan paths and default no-source create to standard
  intent: 'Ensure every creation route starts with one conservative declaration policy:
    `low` only on affirmative seed evidence with no independently detected counter-signal,
    and `standard` without a seed.'
  files:
  - plan_tool/create.py
  - TESTING.md
  - tests/test_create.py
  creates:
  - plan_tool/prompts/classify-risk-profile.md
  - tests/fixtures/create/remove-vendor-scraper-poc-seed.md
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the RiskProfile vocabulary used by the shared classifier result.
  detail: docs/implementation-plans/plan-details/risk-profile-1/02-classify-seed-fed-single-plan-paths.md
  status: done
- id: 3
  title: Resolve a bounded operator declaration and safe create recovery boundary
  intent: Keep the final tier operator-owned, safe across the create failure boundary,
    visible in the run log, and present before detail authoring begins.
  files:
  - plan_tool/create.py
  - plan_tool/cli/authoring.py
  - docs/how-to/pipeline/create-from-existing.md
  - docs/how-to/recovery/create.md
  - tests/test_create.py
  - tests/cli/test_authoring_cmds.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Provides the frontmatter fields that receive the accepted tier and rationale.
    2: Provides the proposal and the minimum tier that bounds the final declaration.
  detail: docs/implementation-plans/plan-details/risk-profile-1/03-resolve-bounded-operator-declaration.md
  status: done
- id: 4
  title: Show the saved risk tier in create's completion summary
  intent: Let operators immediately confirm which risk declaration was recorded on
    the new plan.
  files:
  - plan_tool/cli/authoring.py
  - README.md
  - tests/cli/test_authoring_cmds.py
  complexity: low
  change_type: feature
  depends_on:
  - 3
  depends_on_notes:
    3: Provides the accepted and persisted declaration rendered by the CLI.
  detail: docs/implementation-plans/plan-details/risk-profile-1/04-show-saved-risk-tier-create-completion.md
  status: done
- id: 5
  title: Verify safe create boundaries and partial-publication recovery
  intent: Preserve the existing create safety guarantees while ensuring a failure
    once a plan artifact exists retains it for explicit operator recovery.
  files:
  - tests/test_create.py
  - tests/test_distill.py
  - tests/cli/test_authoring_cmds.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 2
  - 3
  - 4
  depends_on_notes:
    2: Provides the classification routes exercised by the safety regressions.
    3: Provides the reviewed declaration and recovery boundary exercised by those
      regressions.
    4: Provides the CLI completion path that continues into source and distilled-artifact
      archiving.
  detail: docs/implementation-plans/plan-details/risk-profile-1/05-verify-safe-create-boundaries-partial.md
  status: done
---
# Risk Profile 1

## Overview

Teach `create` to detect, at proposal time, what kind of work a seed is asking for —
a brute-force deletion of unconsumed code, a mechanical rename, a config flip, versus
a load-bearing feature on a live surface — propose the resulting **risk-profile tier**
to the operator (accept / override / decline), and persist the accepted tier in the
plan frontmatter as
the two scalar fields `risk_profile: low | standard | high` and
`risk_profile_rationale: <one line>`, so downstream passes can read it instead of
guessing.

The tier is a *declaration with an owner*, not an automation: the classifier only
proposes, the operator confirms or rejects that proposal, and the persisted rationale
is challengeable in review. A rejection continues creation with an explicit `standard`
declaration explaining that the proposal was declined. Ambiguity or classification
failure also yields `standard`, while newly created plans intentionally record the two
explicit declaration fields. This plan deliberately does **not** add a classifier
confidence field: #295 separately owns evidence-support signaling on `Recommendation`
findings, and neither a numeric model self-rating nor a new general confidence
contract belongs in this impact-tier stage.

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

### Classification boundary

`create` runs one small, dedicated risk-classification stage for every source-seed
route that can publish one plan. It remains independent of distillation so a canonical
small seed, a distilled or passthrough seed, and `--no-distill` receive the same policy
and fallback behavior. Distill `split` remains the existing no-write outcome and does
not invoke classification.

A create with no source seed has no work-shape evidence: it records an explicit
`standard` declaration with a no-source rationale and does not prompt for a tier. The
step detail owns the exact classifier input, cache/checkpoint representation, and path
fixtures; the plan's contract is one policy on every seed-fed single-plan route.

### Pre-publication declaration, not a `CreateResult` handoff

The tier is resolved inside the single-plan create flow before its first plan write;
the existing `CreateResult(split_proposal=...)` return remains a no-write exit and is
not used for a risk declaration.

`low` requires affirmative deletion, no-consumer, and no-new-surface evidence shown in
the selected seed. Named consumers, contracts, migrations, auth/authz concerns, or new
external, schema, API, or runtime surfaces set a minimum of
`standard`; ambiguity and parse failure also yield `standard`. `high` remains an
operator-decidable escalation. The final declaration cannot bypass those limits, and
its persisted rationale must explain the **final** tier—not an unaccepted proposal.

An interactive operator may accept, override with a reason, or decline the proposal.
Decline rejects the proposal but does not cancel creation: it writes an explicit
`standard` declaration with a decline rationale. Any silent route likewise records an
explicit standard declaration rather than accepting a model proposal. The run log
records the proposal, final declaration, and decision mode.

Compatible interactive pre-write retries may restore a saved proposal or decision;
`--no-resume` always starts fresh. Once a plan file exists, recovery is deliberately
manual: retain the artifact and report its path and recovery state. Before manifest
publication, only a parse-valid artifact may be explicitly registered/adopted; another
artifact must be repaired before adoption or removed before retrying. An unexpected
finalization error after manifest publication retains the already registered plan as an
incomplete tail handoff, not an adoption candidate. The existing reported
iteration-incomplete result remains a completed registered create. This plan never
auto-deletes, archives, or overwrites either recovery state; a general publication
transaction is deferred to BACKLOG #126. Step detail defines the checkpoint lifecycle
and failure fixtures.

A Ctrl-C follows the same boundary: interruption before the first target write retains
the existing branch rollback, while interruption after a target exists reports that
artifact's valid/invalid or registered state and preserves its branch binding for the
same explicit recovery path. It still exits as an interruption rather than a completed
create.

**Adoption boundary (user-confirmed 2026-08-24):** `register` is an explicit operator
takeover of a parse-valid retained artifact, including one whose later create-tail work
failed. It ends the original create retry and transfers any remaining repair or
finalization to the operator; it does not certify that the full create tail completed.
The registered output is then refused before a later create reads a prior proposal or
decision checkpoint.
Explicitly naming the retained artifact through `--from-existing` is instead a manual
conversion into a replacement plan and authorizes that command's existing source-archive
behavior; it is never an implicit retry.

This stage has no confidence-based auto-acceptance; #295 and later calibration work may
establish a separately evidenced policy before any such automation is proposed.

### Persistence

`risk_profile` and `risk_profile_rationale` are top-level plan-frontmatter fields.
The tier is the closed `low | standard | high` vocabulary and the rationale is a
non-empty one-line explanation. An omitted pair in an existing plan has effective
`standard` behavior; an explicit null in either stored field is invalid. Every new plan writes both fields,
including an explicit `standard` declaration; the rationale always explains the final
declaration.

### Classification signals

`low` requires a deletion-dominant scope, an explicit no-consumer claim, and no new
external, schema, API, or runtime surface. A policy-owned deterministic screen examines
the original selected seed for an affirmative named consumer, contract, migration,
auth/authz concern, or external, schema, API, or runtime surface before any proposal
can admit `low`; it
distinguishes an explicit negation used as affirmative low evidence from a positive
counter-signal. A detected counter-signal sets the `standard` minimum even when the
model response omits it. `high` remains an operator-decidable escalation. Step detail
owns the screen, response parsing, and fixtures.

### Scope contract

- **Outcome:** `create` proposes a risk-profile tier for the seed, the accepted tier
  is persisted in plan frontmatter with a one-line rationale, and a deletion-shaped
  seed like `remove-vendor-scraper-poc` gets `risk_profile: low` proposed without
  hand-authoring it.
- **In scope:** `plan_tool/create.py` (proposal, decision, and checkpoint plumbing),
  `plan_tool/cli/authoring.py` (completion summary), the sibling classifier prompt,
  the frontmatter schema/parser + `validate`,
  `docs/how-to/pipeline/create-from-existing.md`, `docs/how-to/recovery/create.md`, `PLAN_FORMAT.md`,
  `README.md`, and focused tests.
- **Allowed behavior changes:** the interactive proposal prompt, the create completion
  summary's saved declaration, the risk-decision run-log record, the two new
  frontmatter fields, and a failure report for a retained partial artifact; nothing
  else user-visible.
- **Allowed reorganization:** none.
- **Stop / defer:** downstream consumption is #182; the shared `Recommendation`
  confidence/evidence-support contract is #295; corpus calibration is
  `quality-bench-01` (#216). Do not grow any of those facilities here.

## References

- [Claude Code CLI referencehttps: — Documents non-interactive print mode and structured-output flags used when invoking the classifier.
- [Models | Pydantic Docshttps: — Covers typed models, defaults, validation errors, extra-field handling, and model serialization.
- [Fields | Pydantic Docshttps: — Explains field declarations and defaults needed for backward-compatible risk-profile fields.
- [Serialization | Pydantic Docshttps: — Documents model dumping and default exclusion behavior relevant to frontmatter round trips.
- [PyYAML Documentationhttps: — Covers safe YAML loading and dumping used to parse and publish plan frontmatter.
- [json — JSON encoder and decoderhttps: — Documents JSON decoding and parse failures for validating classifier responses and fallbacks.
- [io — Core tools for working with streamshttps: — Defines terminal detection used to separate interactive proposals from non-TTY create behavior.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Consuming the tier in detail authoring, completeness audit, or apply — that is
  the sibling seed (`risk-profile-2-honoring.md`, #182). Without it this field is
  still a paying declaration: the seed author no longer hand-writes a defensive
  preamble, and reviewers see a challengeable tier.
- A shared confidence/certainty field or any confidence-driven auto-acceptance; #295
  owns the former and evidence-based calibration must precede the latter.
- A non-TTY model-proposal acceptance. Non-TTY create records the explicit standard
  declaration defined above instead of pretending that a model has operator approval.
- Re-classifying or migrating existing plans in place; touching split-proposal behavior
  itself; `annotate` / `scope-out` seed flows. An operator-supplied
  `--from-existing` source remains the existing explicit conversion path, not an
  in-place migration or a retry.

## Risks

- **Misclassification in the dangerous direction** — calling load-bearing work
  `low` suppresses scrutiny exactly where it is needed. Mitigations: `low` requires
  parser-verified affirmative deletion/no-consumer/no-contract evidence from the
  selected seed, and a deterministic source screen independently detects positive
  counter-signals even when the model omits them; any counter-signal floors
  the final declaration at `standard`; ambiguity and parse failure select `standard`;
  and an interactive operator can choose only within that floor and low-admission
  rule. The persisted
  rationale makes the call visible and challengeable. #182 adds the downstream
  `tier-challenge`.
- **A path-specific seam drifts** — a seed-fed create route could evade the shared
  policy. Mitigation: one classification boundary for every single-plan seed route,
  explicit split/no-source behavior, and route-level tests. The implementation detail
  owns cache and model-call mechanics.
- **A failure loses or misapplies an operator decision** — retry behavior could hide or
  overwrite a decision or a partial plan. Mitigation: retries before a plan artifact
  exists, including interruption, remain safe to resume or restart. A pre-manifest
  artifact is retained and
  recovered only by explicit removal or, when parse-valid, registration/adoption; that
  adoption ends the create retry and transfers remaining work to the operator. A
  unexpected post-manifest finalization error instead retains the registered plan for
  manual completion. A reported iteration-incomplete result remains a completed create.
  An invalid pre-manifest artifact must be repaired before adoption. Explicitly naming
  the artifact via `--from-existing` is likewise a manual conversion, not a retry. A
  general publication transaction is deferred to #126.
- **Scope grows into confidence calibration** — an uncalibrated model self-rating
  would look authoritative without improving safety. Mitigation: use only the
  impact-tier policy here; #295 owns evidence support and #216 supplies later corpus
  evidence.

## Testing

- Frontmatter validation covers the closed tier/rationale pair, legacy omission,
  every explicit-null field shape, and the explicit declaration emitted for every new plan.
- Policy tests prove that `low` needs every affirmative condition, source-detected
  counter-signals floor the final declaration at `standard` even when omitted from a
  model response, and the persisted rationale describes
  that final declaration.
- Route coverage exercises every seed-fed single-plan create path, no-source creation,
  and the existing split no-write exit.
- Mode coverage proves that acceptance, override, and decline each produce their stated
  declaration; silent creation, resume and `--no-resume`, and the completion summary
  preserve the operator-ownership contract.
- Publication tests distinguish pre-write retry from recovery once a plan artifact
  exists, identify which pre-manifest artifacts can be adopted, distinguish registered
  tail failures, and prove that no automatic path destroys, archives, overwrites, or
  carries a risk decision into a distinct planned output target.
- The archived `remove-vendor-scraper-poc` lean seed remains the characterization case
  for a low-risk deletion proposal.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.
- step 5 (non-code) — verification appropriate to the artifacts rather than unit tests.

## Acceptance criteria

- A deletion-shaped seed can receive a low proposal only with parser-verified affirmative
  evidence from that seed and no independently detected positive counter-signal;
  acceptance persists a rationale that describes the final tier.
- Counter-signals, ambiguity, and classifier failure produce or retain `standard`;
  neither a proposal nor an override can create an inadmissible low declaration.
- Validation preserves legacy effective-standard behavior only for an omitted pair,
  rejects explicit null in either field or both, and ensures every new plan emits the
  two-field declaration.
- One policy covers every seed-fed single-plan route; no-source creation records
  standard and split remains the existing no-write exit.
- The run log records interactive acceptance, override, and decline, while the
  completion summary reports the saved tier or an unconfirmed-declaration warning.
  Decline creates an explicit standard declaration, and fresh creation never silently
  inherits a prior decision.
- A failure once a plan artifact exists retains it and reports its location and recovery
  state. Before manifest publication, only a parse-valid artifact may be
  registered/adopted; that explicit takeover ends the create retry without claiming
  full finalization. An unexpected finalization error after manifest publication reports
  the registered plan as incomplete and does not offer adoption; an iteration-incomplete
  result remains a completed create. Another pre-manifest artifact is repaired before
  adoption or removed before retry. No automatic deletion, archival, or overwrite occurs
  on a plain retry, and a risk checkpoint cannot cross to a distinct planned output
  target. A retained artifact stays on the branch that owns it when branch-aware create
  selected one. An interruption follows that same retained-artifact rule; only an
  interruption before a target exists restores the invoking branch.
  Explicit `--from-existing` is a separate manual conversion path that may archive its
  named source under the existing contract.

## Deferred

- Downstream consumption of the tier — sibling seed #182.
- Recommendation confidence/evidence-support — #295.
- Corpus-based calibration and benchmark corpus/noise floors — `quality-bench-01`
  (#216).
- Tier-aware behavior in `run --mode` review surfaces and `jira` sizing.
