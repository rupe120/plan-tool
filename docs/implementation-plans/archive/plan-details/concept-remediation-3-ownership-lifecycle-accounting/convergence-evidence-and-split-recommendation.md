---
kind: plan-convergence-evidence
version: 1
source_plan: concept-remediation-3-ownership-lifecycle-accounting
source_status: planning_reseeded
assessment: nonconverging_plan_boundary
recommended_action: split_into_dependency_ordered_plans
recommended_plan_count: 3
evidence_backend: codex
evidence_reports:
  - reports/20260713-130512-completeness.md
  - reports/20260713-161955-completeness.md
  - reports/20260713-170126-completeness.md
replacement_seeds:
  - plan-seeds/concept-remediation-3a-accounting-core.md
  - plan-seeds/concept-remediation-3b-lifecycle-publication.md
  - plan-seeds/concept-remediation-3c-seed-restoration.md
---

# Concept Remediation 3 — Convergence Evidence and Split Recommendation

## Decision

Stop auditing `concept-remediation-3-ownership-lifecycle-accounting` as one
plan. Preserve its plan, details, and reports as evidence, but replace its
implementation trajectory with three dependency-ordered plans:

1. `concept-remediation-3a-accounting-core` — durable non-delivery identity,
   validation, review transitions, resumable include regeneration, and
   completeness enforcement.
2. `concept-remediation-3b-lifecycle-publication` — split/merge routing,
   transactional scope-out/re-baseline publication, and reconstructable seed
   envelopes.
3. `concept-remediation-3c-seed-restoration` — create-time envelope parsing,
   explicit restoration review, lifecycle integration proof, and documentation.

This is a plan-boundary split, not another request to divide an individual
step. The final 14-step bundle had no remaining mixed-step or granularity smell,
yet conceptual findings continued to recur at the contracts between groups of
steps. The steps became locally reasonable while the enclosing plan remained a
shared convergence surface for three independently testable authorities.

## Execution history

All model-backed detail generation and completeness audits used the Codex
backend through `PLAN_TOOL_BACKEND=codex`.

The workflow deliberately generated every step detail without iteration before
auditing the complete bundle. Manual audit application then repaired concrete
gaps and split an overloaded transition step into:

- explicit non-delivery review and decision transitions; and
- persisted/resumable include-transition regeneration.

That changed the plan from 13 to 14 detailed steps. The plan, all detail
pointers, and the concept fingerprint validated after the split. A fresh
one-pass confirmation audit was then run against the complete 14-step bundle.

### Audit trajectory

| Report | Detail state | Correctness | Completeness | Coverage signal |
| --- | --- | ---: | ---: | --- |
| `reports/20260713-130512-completeness.md` | bare predecessor, 0/12 details | 2 | 1 | Early gaps already crossed review, enforcement, and scope-out. |
| `reports/20260713-161955-completeness.md` | complete detailed bundle | 7 | 1 | Three-pass discovery remained open at the cap: `3 -> 3 -> 2`; report called the plan likely under-decomposed. |
| `reports/20260713-170126-completeness.md` | complete 14-step post-split bundle | 5 | 1 | Convergence classified as `spinning`; recurring anchors remained after manual repair and a step split. |

The confirmation report's diagnosis is explicit:

```text
convergence: spinning — concept-remediation-3-ownership-lifecycle-accounting
  include-transition: recurs in 2 of 3 audits; severity high -> high
  scope-out-publication: recurs in 2 of 3 audits; severity high -> high
The decomposition itself is wrong across steps; re-seed and re-decompose.
```

Finding count alone understates the signal. Manual changes reduced some local
contradictions, but each repair exposed another missing contract at a downstream
boundary. The same concepts moved between producer, policy, publication, and
consumer steps instead of disappearing.

## Coverage evidence clusters

### Cluster A — accounting identity, transition state, and policy

Observed anchors and issues:

- `wont-do-operator-workflow` — enforcement existed before an operator could
  author and approve the record required to satisfy it.
- `non-delivery-decision-transitions` — the original design omitted transitions
  among `include`, `defer`, and `wont_do`.
- `include-transition` — first, no durable pending state connected review to
  regeneration; after adding one, completeness still interpreted the retained
  parked record as contradicting the reviewed include intent.
- `non-delivery-record-identity` — summary prose alternated between mutable
  `artifact_ref` and immutable `origin_ref` as an identity input.
- `dangling-non-delivery-concept` — strict load validation prevented the
  completeness diagnostic promised for structurally valid dangling records.

These findings share one authority: the persisted accounting model and the
policy that interprets its state. They require a bounded state machine and can
be validated independently of structural transforms and seed restoration.

Replacement owner: `concept-remediation-3a-accounting-core`.

### Cluster B — structural routing and publication generation

Observed anchors and issues:

- `artifact-reference` — split/merge renamed the detail path while preserving a
  supposedly stable current artifact reference.
- `split-link-fanout` — a single optional source step could not represent one
  reviewed record routed to multiple split children.
- `routing-approval` — structural remapping was simultaneously described as an
  approval-invalidating semantic change and an approval-preserving route edit.
- `scope-out-publication` — scope-out repeatedly oscillated between local
  seed-first mutation semantics and the prerequisite all-artifact transaction.
- `reground-publication` — re-baseline direct writes conflicted with the same
  publication authority and left fingerprint semantics ambiguous.

These findings share a different authority: preparation and atomic publication
of one lifecycle generation. They require failure matrices around split, merge,
scope-out, re-baseline, seed creation, plan replacement, detail migration, and
sidecar update. They should consume Cluster A's record contract rather than
co-design it inside the same audit surface.

Replacement owner: `concept-remediation-3b-lifecycle-publication`.

### Cluster C — producer/consumer restoration contract

Observed anchors and issues:

- `seed-concept-identity` — producers carried IDs and fingerprints but omitted
  required `ConceptNode` reconstruction inputs such as `title` and
  `parent_path`; create therefore could not restore exact signed nodes without
  prohibited inference.
- `seed-restoration-scope` — the consumer used “applicable source concepts”
  without a deterministic rule for contextual done concepts, re-planned
  concepts, parked concepts, or carved concepts transitioning from source
  deferral to destination delivery.
- `lifecycle-step-numbering` — stale producer/consumer step references routed
  contract failures to the wrong owner, a smaller symptom of the same broad
  cross-plan dependency surface.

These are consumer-boundary findings. The producer must emit a complete
reconstructable envelope and a closed restoration-action vocabulary; create
must validate and review that contract after destination steps settle. This can
be audited independently once Cluster B ships the envelope.

Replacement owner: `concept-remediation-3c-seed-restoration`.

## Why another in-place step split is not the remedy

The manual step split was useful: it separated decision approval from durable
regeneration and removed the local mixed responsibility. The confirmation audit
did not report another mixed-step or granularity smell. Nevertheless:

- `include-transition` still recurred across the review/regeneration/enforcement
  boundary;
- `scope-out-publication` still recurred across the scope-out/envelope boundary;
- a new high-severity identity gap appeared between envelope producers and the
  create consumer; and
- applicability remained a high-severity completeness gap owned by neither
  producer nor consumer precisely enough.

This pattern means the steps are not individually too large. The plan contains
too many coupled authorities. More step splitting would retain the same broad
prompt, concept graph, audit history, and cross-step correction loop.

## Frozen work and preserved decisions

The reseed must preserve the decisions already extracted by manual audit work:

- record identity uses `concept_id`, disposition, and immutable `origin_ref`;
  current `artifact_ref` and ordered `linked_step_ids` are relocatable routing;
- one record can route to multiple split children without duplicate identity;
- structural decoding permits diagnosable dangling references, while candidate
  publication rejects them;
- a reviewed pending include retains effective parked accounting plus an exact
  durable regeneration request until replacement delivery commits;
- scope-out and re-baseline publish seed, plan, details, and sidecar as one
  prerequisite transaction; a recoverable failure restores seed absence;
- seed envelopes carry canonical reconstructable concept-node projections, not
  opaque IDs alone; and
- restoration uses explicit actions: `context_only`, `require_delivery`, and
  `preserve_non_delivery`, with no local “applicable” inference.

The three new seeds contain these constraints. Future planning should consume
them as settled inputs unless code at HEAD invalidates a premise.

## Reusable coverage signals for split-suggestion logic

This case supplies a second concrete pattern, distinct from a single overloaded
step, that `plan-tool` can use when suggesting a plan split.

### Strong signals

1. **Discovery remains open at a multi-pass cap.** New findings per pass do not
   reach a confirming dry pass (`3 -> 3 -> 2` here).
2. **A fresh audit remains non-clean after manual application and an accepted
   step split.** Local decomposition improved, but plan-level findings persisted.
3. **Stable anchors recur at high severity.** `include-transition` and
   `scope-out-publication` each appeared in 2 of 3 audits at high severity.
4. **A repair moves the contradiction across a boundary.** Missing pending
   state became policy disagreement; seed-first mutation became a producer test
   that assumed an impossible orphan.
5. **Findings cluster by different authorities and failure matrices.** Persisted
   state/policy, lifecycle publication, and create restoration can each name a
   separate source of truth and independent exit condition.
6. **The plan is fully detailed and structurally valid.** Missing details or
   malformed dependency metadata cannot explain the conceptual churn.
7. **No individual-step smell explains the remaining gaps.** Absence of a
   mixed-step smell should not suppress a plan-level split recommendation when
   recurrence and authority clustering are strong.

### Suggested structured inputs

For each audit and finding, retain or derive:

- report path, audit index, pass index, backend, and whether a dry confirming
  pass occurred;
- stable anchor, severity trajectory, recurrence count, and whether the anchor
  survived manual application;
- owning step and upstream/downstream steps named by the finding;
- authority class: persisted schema/policy, mutation/publication, producer
  serialization, consumer restoration, CLI/documentation, or other;
- mutation generation and rollback boundary;
- finding relationship to the preceding repair: closed, unchanged, moved to a
  consumer, moved to a producer, or replaced by a stricter version;
- whether all steps have active details and the plan validates; and
- whether a step-level split/merge smell exists.

Cluster primarily by `(authority class, source of truth, mutation generation,
independent exit condition)`. File overlap is only a scheduling warning. In this
case `concept_tree.py`, `detail.py`, and `create.py` legitimately appear across
candidate plans, but each plan owns a distinct named contract.

### Candidate scoring rule

A plan-level reseed recommendation is justified when all of the following hold:

- the plan is fully detailed and validates;
- at least one high/critical anchor recurs after a manual application cycle, or
  a capped multi-pass audit remains open;
- findings form at least two authority clusters with different failure
  boundaries or independent exit tests; and
- an in-place step split has already failed to remove cross-cluster recurrence,
  or no single-step smell accounts for the findings.

Confidence should increase when three or more clusters can be arranged in a
directed dependency order without a cycle. The recommendation should be
`reseed`, not repeated `completeness-apply`, because the current plan's shared
audit surface is the defect.

### User-facing recommendation shape

Show:

1. the audit trajectory and whether coverage was confirmed;
2. recurring anchors with severity trajectories;
3. the prior manual remedies and how findings moved afterward;
4. proposed authority clusters and their dependency order;
5. frozen decisions that replacement seeds must preserve;
6. seed-ready names, owned scope, exclusions, and exit evidence; and
7. an explicit choice between creating seeds, continuing manual repair, or
   stopping.

Do not present an automatic plan split as a purely mechanical renumbering. Seed
creation changes plan boundaries, manifests, concept records, and audit history
and therefore remains an explicit operator action.

## Replacement boundaries and exit evidence

### Plan 3A — accounting core and enforcement

One authority: persisted non-delivery state and its policy interpretation.

Exit evidence: golden identity vector; strict decode versus publication
validation; explicit transition table; resumable pending include; completeness
accepts only exact ownership, approved non-delivery, or the precisely modeled
pending state; focused and full tests pass.

Seed: `plan-seeds/concept-remediation-3a-accounting-core.md`.

### Plan 3B — lifecycle transforms and seed publication

One authority: preparation and transaction of a complete lifecycle generation.

Exit evidence: split/merge routing conservation; scope-out and re-baseline
failure matrices; no normal seed orphan; deterministic reconstructable envelope
with explicit restoration actions; focused and full tests pass.

Seed: `plan-seeds/concept-remediation-3b-lifecycle-publication.md`.

### Plan 3C — seed restoration and lifecycle proof

One authority: validation and explicit destination restoration of producer
accounting.

Exit evidence: parse-before-model behavior; exact canonical node restoration;
closed applicability table; unattended no-write refusal; lifecycle conservation
matrix and documentation drift checks pass.

Seed: `plan-seeds/concept-remediation-3c-seed-restoration.md`.

## Readiness rule after reseeding

Generate all details for one replacement plan without iteration, then audit that
complete candidate independently. Do not place all three replacement plans back
into one convergence loop. A downstream plan may be authored early for review,
but it is not ready to execute until its prerequisite public contracts exist at
HEAD and its details reference those shipped contracts rather than inventing
local substitutes.

