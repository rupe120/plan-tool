> **Replaced**: this file has been superseded by `docs/implementation-plans/2-jira-grade-01-detail-instrument.md`.
> Preserved here for history; do not edit.

# Plan seed: jira-grade detail instrument — contract, consumers, and depth-aware audit grounding

This file is a `plan-tool create` input. Use it via:

```
plan-tool create jira-grade-01-detail-instrument --from-existing plan-seeds/jira-grade-01-detail-instrument.md --iterate
```

> **Source and lifecycle.** Stage **01 of 05** in the ordered `jira-grade`
> group (roadmap: BACKLOG **#169**, the group anchor; naming per the "Ordered
> efforts" directive in `BACKLOG.md`), re-decomposing BACKLOG **#164** after
> the predecessor plan `2-jira-grade-detail-side-by-side-evaluation` spun on
> its completeness convergence tail (verdict `FORK_STRUCTURAL`; latest report
> [retained historical summary](../../docs/evidence/public-release-content-snapshot.md#applied-dispositions-and-retained-conclusions)).
> This seed builds the **instrument only** — the jira-grade contract, its
> consumers, and the audit's ability to ground on it. The consumer probe is
> stage 02 (`plan-seeds/jira-grade-02-consumer-probe.md`) and the quality
> ledger is stage 03 (`plan-seeds/jira-grade-03-quality-ledger.md`);
> both depend on this plan shipping. This seed inherits #164's scope contract **with one
> explicit, narrow amendment** (depth-aware audit grounding — see "The fence
> amendment"). The final docs/status step must update `BACKLOG.md` #164's
> Status: mark the instrument half shipped and the evaluation still pending —
> never remove the entry from this plan.

---

## Why this is a re-seed, not an edit

The predecessor plan fused two concerns that converge under different audit
regimes: *building the instrument* (ordinary software — converges under tests
and completeness audit) and *running a defensible experiment* (epistemics —
isolation, metric definition, rubric, sample size). Three blockers recurred
across all three audit snapshots without shrinking; the seam between build and
measure is where each partition's findings become locally closable. This seed
takes the build side and directly resolves the blockers that live here:

- **`audit-churn` (CRITICAL, fence conflict):** the inherited fence forbade
  completeness-audit changes while the adoption gate required measuring churn
  on the jira-grade bundle — but the audit grounds on the run-grade
  `Step.detail` pointer, so both arms audited the control. Resolved by the
  narrow fence amendment below.
- **`step-1-type-purity` (MEDIUM, fused concerns):** the old step 1 mixed a
  behavior-preserving extraction with new audit-inclusion behavior. Resolved
  by splitting them into separate refactor and feature steps.
- **`artifact-ambiguity` (HIGH):** consumers validated only path existence, so
  a run-grade body at the jira-grade path would be read under the jira-grade
  prompt. Resolved by contract validation on read.

Of the measurement-side blockers, `paired-run-isolation` and `metric-noise`
**dissolved** when the paired decision experiment was dropped (stage 03 is
now a quality ledger — no paired runs, no single-pair gate); the surviving
instrumentation concerns (churn formula, actionability metric, provenance,
floors) belong to stage 03 and are **out of scope here**, apart from the
one-off mechanism falsification check below.

## The fence amendment (decision taken — carry it verbatim)

#164's contract excludes "altering the completeness audit's own logic." This
plan amends that fence **narrowly**: depth-aware audit **grounding** is in
scope — the completeness audit may learn which detail bundle to resolve and
which format contract to check it against for a selected depth. Audit
**judgment** stays untouchable: no changes to severities, finding sources,
sampling, convergence predicates, or check strength. The intent of the
original fence — reduce churn by shrinking the contradiction surface, never by
weakening the audit — is preserved; without this amendment the sibling seed's
churn comparison is unmeasurable and the critical blocker is unresolvable.
Completeness audits of this plan must treat audit-grounding work as in-scope
and must not re-raise the fence as a contradiction.

## Stage and audit scope fence

**Tool state when this plan starts:** today's tool — run-grade is the default
and the only conceptually-audited depth; no consumer probe, no probe-based
materiality, no inversion. **Tool state this plan leaves behind:** both
depths authorable, selectable, consumable, and independently auditable —
nothing more. Run-grade remains default and canonical throughout.

Completeness audits of this plan must judge it against that stage's tool
state only. Concerns owned by later stages are valid observations but
invalid findings here — route each as `[out-of-scope-deferred]` to its owning
stage instead of expanding this plan: the consumer probe and `probe` verdict
arm (stage 02, BACKLOG #169), the quality ledger's metrics, floors, and
roll-up (stage 03, `plan-seeds/jira-grade-03-quality-ledger.md`),
blocker-recurrence materiality (stage 04, #170), canonical inversion or any
default change (stage 05, #171). Per the #125 convention, deferred-tagged findings neither
reset low-yield streaks nor justify raising pass caps; prefer
`--audit-passes 1` for audits of this plan.

## Overview

Add an explicit jira-grade detail authoring altitude beside the existing
run-grade path so one plan can carry comparable bundles of both depths.
Run-grade remains the default everywhere; legacy bundles are always read as
run-grade and never rewritten or reinterpreted. `jira` consumes jira-grade
detail directly; an opt-in `run` path renders from it while the run-grade
renderer remains intact as the control. The completeness audit can ground on
whichever depth is selected, making both bundles independently auditable.

This plan ships **no evaluation and no default change** — it makes the
question measurable; the sibling seed measures it.

## Design

### Schema authority (one authority, never two)

The jira-grade contract is the smallest shared schema both consumers can use:
`Intent`/problem, `Change`, `Constraints`, `Done when`, `Out of scope` —
outcomes and boundaries, not pre-baked edits, test rosters, or mechanics
unless a declared constraint requires one.

**Authority decision (taken 2026-07-22, user-confirmed — carry it verbatim):
this plan's schema step is the single compact-schema authority.** BACKLOG
**#149**'s compact required-H2 schema (plan-authored:
`detail-verbosity-compact-summary`, unexecuted) is **not** the base:
#149's contract (`Intent`, `Footprint`, capped `Approach`, `Done when`) is a
compact *run-grade* schema — its `Footprint`/`Approach` sections retain the
implementation-fact carriers the jira-grade altitude sheds, it lacks
`Constraints` and `Out of scope`, and the surface it compacts is scheduled
to become derived at stage 05. The real overlap is `Intent` and `Done when`
only. Therefore: this plan defines the jira-grade tokens as the durable
authority, and the final docs/status step **re-scopes #149** so its
authoring-schema layer aliases the jira-grade tokens (its read-only
`--summary` review-card layer is unaffected and remains valuable). Audits
must not re-open the sequencing question; "aligned with or sequenced after"
hedging is not permitted to survive into the plan.

**Plain, concise English prose by contract.** Every prose surface this plan
ships is written in plain, to-the-point English from day one: the jira-grade
authoring prompt, the jira-grade bodies it produces, and the `jira` story
output built from them use short, direct sentences and familiar words, say
each thing once, and carry no filler — while keeping every technical fact
(paths, symbol anchors, examples, constraints, acceptance criteria) intact.
Both directives target the descriptive prose only: they never reduce code
anchors or examples. This applies BACKLOG **#167**'s rubric (including its
conciseness directive) to the new contract at birth rather than as a
retrofit — #167 remains the authority for the existing run-grade `detail`
output; this plan does not modify the run-grade prompts, it only refuses to
create a second dense-prose surface. The requirement is testable at the gate
level: the jira-grade response gates reject bodies that bury the required
outcome in stacked clauses, unexplained jargon, or padding, in the same pass
that validates the required H2s.

### Storage, selection, and read-time validation

Add explicit depth selection and collision-safe artifact routing so run-grade
and jira-grade bundles coexist for one plan (separate files under the plan's
detail directory; never overloading `Step.detail`'s meaning for legacy
bundles). Selection is explicit at every consumer; ambiguous or mislabeled
selection fails clearly. **Validation happens on read, not just on path
existence:** consuming a jira-grade artifact re-validates its required-H2
contract first, so a run-grade body at a jira-grade path is rejected loudly
rather than silently executed under the wrong prompt.

### Consumers

`jira` consumes the jira-grade schema directly (no down-conversion from
run-grade prose when a jira-grade bundle is selected). An opt-in jira-grade
`run` renderer receives the same schema plus normal plan/repository grounding
and asks the executor to derive the implementation; its output is separately
selectable from the unchanged run-grade renderer, and no hidden fallback may
mask which contract a run actually executed.

### Depth-aware audit grounding (the amended surface)

The completeness audit resolves the detail bundle for a requested depth and
applies that depth's format contract to it — run-grade bundles keep today's
behavior byte-for-byte when no depth is selected. This is resolution and
format-contract selection only; findings, severities, and convergence logic
are unchanged.

### Mechanism falsification check (one-off, recorded — not a gate)

The claim motivating this whole group — jira-grade detail churns less than
run-grade across a scope change because its contradiction surface is smaller
— has only ever been inferred from post-mortems, never observed. Before this
plan closes: author both depths' bundles for one representative real plan,
apply one deliberately scoped change, run the depth-aware completeness audit
against each bundle, and commit a short recorded observation comparing the
finding sets. No clones, no matched-baseline machinery, no verdict gate:
whatever the result, it is recorded and routed. A surprise — jira-grade
churning comparably, meaning churn is driven by plan-body facts rather than
detail facts — goes to `BACKLOG.md` as a direction question before stage 05
can be gated on churn floors; it does not block this plan.

## Suggested decomposition

Keep these as separate concerns:

- **Pure refactor step:** extract the shared detail artifact-path layer (e.g.
  `plan_tool/detail_artifacts.py`) with characterization tests pinned before
  the change and passing unchanged after. No behavior change of any kind.
- **Audit-inclusion feature step (small):** the piece the old step 1 fused in
  — an unset `Step.detail` pointer with an on-disk canonical detail file
  becomes visible to quality auditing. Its own tests establish the new
  behavior independently of the refactor's compatibility.
- **Schema/authoring step:** the jira-grade contract (resolving the #149
  authority branch above), authoring surface (an explicit depth flag on
  `detail`), and read-time validation, preserving all run-grade and legacy
  behavior.
- **Consumer step (jira):** `jira` reads jira-grade detail directly.
- **Consumer step (run):** the opt-in jira-grade `run` renderer beside the
  unchanged control.
- **Audit-grounding step:** depth-aware bundle resolution + format-contract
  selection in the completeness audit, within the amended fence.
- **Falsification-check step (non-code):** the one-off both-depths churn
  observation above, committed as a short record with its routing outcome.
- **Docs/status step:** formats/docs, `BACKLOG.md` #164 Status update (and
  #149 re-scope if that branch applied).

## Out of scope

- The quality ledger — longitudinal metrics, floors, smoke-check records,
  and roll-up — lives in `plan-seeds/jira-grade-03-quality-ledger.md`; this
  plan's one-off falsification check is a recorded observation, not
  instrumentation.
- Restyling existing run-grade prompts or bundles into plain English —
  that is BACKLOG #167's scope; this plan only guarantees the new jira-grade
  surfaces are plain-English from birth.
- The consumer probe and `probe` verdict arm (stage 02, #169),
  blocker-recurrence materiality (stage 04, #170), and canonical inversion
  (stage 05, #171).
- Making jira-grade the default for `detail`, `run`, or `jira`; default
  inversion requires a later evidence-backed plan.
- Re-authoring or bulk-rewriting existing run-grade bundles.
- Changing plan-body schema, step decomposition, `change_type`, or any audit
  **judgment** surface (severities, sources, sampling, convergence
  predicates) — only the grounding amendment above is open.
- Weakening audit checks in any form.

## Risks and mitigations

- **Run quality regression:** deferred entirely — no run behavior changes by
  default, and the experiment that measures the opt-in path is the sibling
  plan's concern.
- **Artifact ambiguity:** explicit depth selection + read-time contract
  validation + tests that reject ambiguous and mislabeled selection.
- **Schema duplication with #149:** the one-authority rule above; the plan
  must record which branch applied.
- **Fence creep:** the amendment is grounding-only; any proposed audit change
  beyond bundle resolution and format-contract selection is out of scope and
  routes to the backlog.

## Acceptance criteria

- Run-grade remains the default; legacy bundles read and execute unchanged,
  with byte-for-byte audit behavior when no depth is selected.
- An explicit jira-grade mode produces, stores, and selects artifacts
  independently from run-grade for the same plan; ambiguous or mislabeled
  selection fails clearly, and consuming an artifact re-validates its contract.
- Exactly one compact-schema authority exists, with the #149 branch recorded.
- `jira` consumes jira-grade detail directly; an opt-in `run` path renders
  from it; the run-grade renderer is intact as the control; no hidden fallback
  masks the executed contract.
- The completeness audit grounds on the selected depth's bundle with that
  depth's format contract; audit judgment surfaces are demonstrably unchanged.
- Jira-grade bodies and `jira` story output are plain, concise English by
  contract: short, direct, to-the-point sentences with all technical facts,
  code anchors, and examples intact, enforced by the same response gates
  that validate the required H2s (per #167's rubric, applied at birth;
  conciseness directed at descriptions only).
- A committed falsification-check record exists: both depths audited across
  one scoped change on a real plan, finding sets compared, outcome recorded
  and routed (never gated on).
- Tests cover both contracts, legacy compatibility, selection, read-time
  validation, prompt routing, depth-aware audit grounding, and that no
  default changed.
- `BACKLOG.md` #164 Status reflects instrument-shipped / evaluation-pending;
  out-of-scope findings route to `BACKLOG.md` / `BUG_BACKLOG.md`.

## Deferred

- The quality ledger (stage 03) and any default inversion (stage 05).
- A prescriptive-supplement escape hatch for individual jira-grade steps;
  derive from experiment failures, not preemptive schema growth.
- Corpus migration or re-authoring policy.
