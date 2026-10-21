> **Replaced**: this file has been superseded by `docs/implementation-plans/2-risk-profile-2.md`.
> Preserved here for history; do not edit.

# Detail authoring and completeness audit honor the plan's declared risk profile

Seed for BACKLOG **#182**. Sibling and hard dependency:
`risk-profile-1-detection.md` (#181) introduces the `risk_profile` frontmatter field
this seed consumes — it must land first. The shared worked example
(example-app-amplify `remove-vendor-scraper-poc`, 2026-07-28/29) is recorded in
full in the sibling's Problem statement; this seed only restates the half that
motivates the audit-side change.

## Overview

Thread the persisted `risk_profile` tier into the two passes that generate and
police plan procedure, so declared-low-risk work stops accumulating load-bearing
ceremony:

- **Detail authoring** (`plan_tool/prompts/detail.md`): a `low`-tier plan still
  gets file lists, exact-symbol rules, and test gates — but not export gates,
  credential-custody procedures, confirmation checkpoints, or multi-deploy
  ordering rules, unprompted.
- **Completeness audit** (`plan_tool/prompts/plan-audit.md`): gaps are judged
  *against the declared tier*. On a `low`-tier plan, "no rollback procedure / no
  custody rule / no confirmation gate" is not a finding unless the auditor first
  argues the tier itself is wrong — and that argument becomes a first-class
  finding kind, **`tier-challenge`**, instead of leaking out as twenty ceremony
  findings.

The inversion is the point: today a mis-calibrated audit produces many
authoritative-looking findings and zero signal about the actual question. With the
tier as input, the audit either stays quiet or asks the one question worth asking —
*"is `low` right for this surface?"*

## Problem statement

**The measurement — including the one that falsified the first hypothesis.**

| Audit run | Directive location | Findings | HIGH |
| --- | --- | --- | --- |
| inside `detail` | working context | 6 | 0 |
| standalone `completeness-audit` | absent | 18 | 3 |
| standalone `completeness-audit` | **plan body (readable)** | **17** | **5** |

The third row is the important one. The initial hypothesis — *"the audit re-invents
ceremony because it cannot see the tier"* — predicted the count would drop once the
directive was written into the plan body where a standalone audit does read it. It
did not: 18 → 17, and HIGH rose. Reading the finding bodies rather than their labels
explains it. They were **not** invented gaps; they were contradictions between the
new body directive and ceremony that **`detail` had already written into the step
files** — step 2's detail carried "the live value is exported to the team's
out-of-band secret store before that environment's deploy", authored by a `detail`
run that had no risk signal. `secret-export-gate`,
`ssm-consumer-confirmation-gate`, `deploy-ordering-rule`, and
`secret-rollback-path` are all of that shape. The audit was policing consistency
correctly.

**Sequencing consequence, and it is the design point of this seed:** ceremony is
*written* at detail-authoring time and only *policed* at audit time. Threading the
tier into `plan-audit.md` alone would buy better-worded findings about ceremony that
already exists. `prompts/detail.md` must get the tier **before the bundle is
authored** — so of the two prompt surfaces in scope, the detail one is load-bearing
and the audit one is the backstop.

(The 6-vs-18 gap in the first two rows is most parsimoniously explained by the
in-`detail` audit being a lighter pass than a standalone `completeness-audit`, not
by directive reachability. Do not cite it as evidence of context sensitivity.)

In the earlier heavyweight run, all four HIGH findings surviving audit round 4 were
the same class of proportionality error, not defects: `credential-export-custody`,
`out-of-repo-consumer-gate`, `dr-cross-region-writer`, `step1-3-deploy-ordering` —
each demanding load-bearing-grade procedure for 323 lines of dead code with no
consumer. The operator's verdict on reading them: *"we really just need to remove
the functionality."* Each round of hand-closing ceremony findings opened
body↔detail divergence findings, driving the count 24 → 27 → 30 and two wrong
*spinning → re-seed* verdicts from `convergence`. An audit that had the tier as
input would have suppressed all four or produced a single `tier-challenge`
(the stored third-party credential is a legitimate one to raise).

## Architecture

### The threading is net-new, not an extension

Verified at HEAD: **no plan-level frontmatter field reaches either prompt today** —
`enforce_step_tests` (the closest analog) appears in neither `plan_tool/detail.py`'s
context assembly (template load at `prompts_dir() / "detail.md"`, rendered by the
function at `detail.py:648`) nor `plan_tool/review.py`'s (`plan-audit.md` render at
`review.py:5830`, template load `:5851`; carried-finding section `:5746`). So this
seed adds the first plan-level→prompt channel. Design it as a general one — a small
"plan directives" context block both templates render — rather than a
`risk_profile`-shaped special case, because `enforce_step_tests` and the
scope-guardrail work (#161/#162) want the same channel. Keep the *block* generic;
only the `risk_profile` clause ships here.

### Prompt-contract shape

- Tier present and `low` → the rendered context names the tier, its rationale, and
  the ceremony classes that are out of contract (export/custody, confirmation
  gates, deploy-ordering, rollback procedure beyond git) *unless* accompanied by a
  `tier-challenge`.
- Tier `standard` / `high` / absent → the block renders nothing tier-specific;
  rendered context stays **byte-identical to today** (this is the regression
  contract, and the test for it).
- The audit prompt is explicitly instructed, every round, to consider whether the
  declared tier fits the surfaces actually touched — the challenge is a standing
  question, not a one-time gate. Severity floors stay tier-independent for
  findings grounded in a named consumer or live surface: the tier suppresses
  *ceremony-class* findings only, never grounded correctness findings.

### `tier-challenge` finding kind

A new member of the finding-kind vocabulary (locate the enum/vocabulary and its
report rendering at plan time — `plan_tool/review.py` owns the audit report;
`DETAIL_FORMAT.md` gets a note). It carries: the tier declared, the evidence the
auditor believes contradicts it (named consumer, live surface, credential), and the
tier it proposes instead. It is a blocking-eligible finding — the one class that
must never be demoted by the tier, since it is the tier's own audit.

### Scope contract (inherited verbatim from BACKLOG.md #182)

- **Outcome:** on a `risk_profile: low` plan, the completeness audit reports zero
  ceremony-class findings (export/custody/confirmation/deploy-ordering) unless
  accompanied by a `tier-challenge` finding, and detail authoring emits no such
  procedure unprompted; `standard`-tier and field-absent plans behave
  byte-for-byte as today.
- **In scope:** `plan_tool/prompts/detail.md`, `plan_tool/prompts/plan-audit.md`,
  the context-assembly sites that render those prompts, the finding-kind
  vocabulary + its report rendering, `DETAIL_FORMAT.md` note, `tests/`.
- **Out of scope / Non-goals:** the classifier and field (that is #181); changing
  severity taxonomy for grounded correctness findings; touching `reconcile`,
  `run`, or `jira` surfaces; retroactive re-audits.
- **Allowed behavior changes:** tier-conditioned prompt context and the new
  finding kind; none for plans without the field.
- **Allowed reorganization:** none.
- **Stop / defer:** tier-aware behavior for `run --mode` review surfaces and
  `jira` sizing are follow-ups; file separately.

## Scope of work

1. **Add the shared plan-directives context block** — a helper that reads
   plan-level directive fields (here: `risk_profile` + rationale) and renders a
   context section; wire it into both templates' assembly sites. Empty when no
   directive applies, so existing rendered contexts are unchanged.
2. **Write the tier clause for `detail.md`** — what a `low` tier licenses omitting,
   with the explicit floor: file lists, exact-symbol rules, and test gates are
   never omitted at any tier.
3. **Write the tier clause for `plan-audit.md`** — ceremony-class gaps are not
   findings on a `low` plan absent a `tier-challenge`; the standing per-round
   challenge instruction; grounded-finding severity floors stay tier-independent.
4. **Add the `tier-challenge` finding kind** to the vocabulary and report
   rendering, blocking-eligible, never tier-demoted.
5. **Tests** — prompt-context tests both directions (tier present → clause
   rendered; absent → byte-identical), a characterization audit over a lean
   fixture plan showing ceremony findings replaced by at most one
   `tier-challenge`, and a fixture where a `low` tier plus a named consumer
   yields exactly that challenge.

## Out of scope

- The classifier, the proposal flow, and the frontmatter field itself — sibling
  seed #181.
- Any change to how grounded correctness findings are scored or blocked.
- `reconcile`, `run`, `jira`, and `annotate` surfaces; retroactive re-audits of
  existing plans.

## Risks

- **The suppression direction** — a wrongly-`low` plan now gets less scrutiny
  everywhere. Mitigations: the standing `tier-challenge` instruction every round
  (one prompt clause, cheap); tier-independent severity floors for grounded
  findings; `tier-challenge` itself blocking-eligible and never demoted; absent
  field ≡ today's behavior exactly, so nothing unmigrated is touched.
- **Prompt-contract drift between the two templates** — the same tier licensing
  different omissions in detail vs. audit produces the body↔detail divergence
  churn this pair exists to kill. Mitigation: both clauses render from the one
  shared directives block; a test asserts the ceremony-class list is defined
  once.
- **Finding-kind plumbing is wider than it looks** — kind vocabulary, report
  rendering, convergence trending, and telemetry may each enumerate kinds.
  Locate all consumers at plan time.

## Testing

Covered in Scope of work step 5; the two contracts that matter most:

- **Byte-identity regression**: rendered detail and audit contexts for a plan
  without the field are byte-identical before/after this change.
- **Both-directions characterization**: lean fixture → ceremony findings gone,
  ≤1 `tier-challenge`; lean-but-wrong fixture (named consumer) → exactly a
  `tier-challenge`.

## Acceptance criteria

- The Outcome clause of the inherited scope contract, verbatim, as the primary
  gate.
- `tier-challenge` appears in the audit report rendering with tier, evidence, and
  proposed tier; it is blocking-eligible and unaffected by tier demotion.
- The ceremony-class list exists in exactly one place consumed by both prompts.
- No test outside the new fixtures changes.

## Deferred

- Tier-aware `run --mode` review surfaces and `jira` story sizing.
- Corpus calibration of what each tier licenses (shared follow-up with #181).
- Migrating `enforce_step_tests` onto the shared directives block (natural
  follow-on once the channel exists; not this plan).
