# Forward seed — establish whether advisory risk context needs an authority or escalation guardrail

## Starting point

Run-grade detail authoring, quality review, and detail-loop rewrites receive
an explicitly declared risk profile and rationale as advisory context. The
context preserves ordinary grounding, test, and safety duties; completeness
audit remains independent of that authoring context.

The dated design reference
[`risk-profile-escalation-options.20260826.md`](archive/risk-profile-escalation-options.20260826.md)
records candidate properties from a separate unexecuted exploration. It is
input, not a predecessor plan or an implementation commitment.

## Decision needed

Determine whether the advisory boundary preserves proportional detail while
keeping a risk declaration under the right authority. The decision must answer
both questions separately:

1. Does advisory context leave a material proportionate-detail or safety
   failure in observed detail runs?
2. May an automated detail rewrite change `risk_profile` or its rationale, or
   must it leave an anchored explanation for a human decision?

## Required evidence

Before proposing enforcement, inspect a bounded set of explicit-declaration
detail runs and any accepted detail-loop declaration edits. For each relevant
case, record the declared tier and rationale, the concrete procedure or change
at issue, its grounding and test/safety obligations, the final review outcome,
and source locations. Classify the result as:

- advisory context preserved the required property;
- ordinary review corrected a mismatch; or
- a specific invariant remained unprotected.

The review must compare the normal authoring route, quality review, and
detail-loop rewrite where each has evidence. It must also verify that audit
output and purity-cache reuse remain uninfluenced by authoring-only context.
Absence of an observed failure is a valid result and closes the item without a
new policy.

## Constraints

- Keep named files, symbols, tests, compatibility work, and concrete safety
  requirements independent of the declared risk tier.
- Do not introduce a ceremony taxonomy, audit suppression, a custom finding
  grammar, or a cross-pipeline policy engine without evidence that a smaller
  boundary cannot preserve the identified invariant.
- Do not let a model silently change the declaration merely because it can
  explain a mismatch; authority and explanation are separate decisions.
- Keep authoring context isolated from completeness-audit behavior and cache
  reuse.
- Preserve byte-identical behavior for plans without an explicit declaration
  and for non-detail `apply_finding` callers.

## Possible outcomes

- Retain advisory context unchanged and close this seed with its evidence.
- Create one narrowly scoped plan for a human-confirmation boundary on
  declaration mutation.
- Create one narrowly scoped plan for an anchored escalation question backed
  by concrete contradictory evidence.

Any implementation plan must state the failed property, select one outcome,
and include a common-route test that proves the selected mechanic preserves
that property. It must not revive the reference document wholesale.

## Stop / defer

Do not author implementation details until the evidence identifies a concrete
failure and the user selects an outcome. Concerns outside declaration
authority, targeted escalation, or authoring/audit isolation go to their own
backlog item.

## References

- `BACKLOG.md` #314 — evidence-gathering scope and stop condition for this
  advisory-effectiveness decision.
- `plan-seeds/archive/risk-profile-escalation-options.20260826.md` — dated
  design reference that supplies candidate properties without committing one.
- `plan_tool/detail.py` — run-grade detail authoring surface that receives the
  advisory risk context under review.
