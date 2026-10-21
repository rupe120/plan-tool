# Risk-profile escalation options — dated design reference

**Status:** exploratory and noncanonical. This reference is cut 2026-08-26
from an unexecuted local enforcement design that diverged from the completed
advisory risk-context implementation. It records candidate properties, not
accepted behavior, and does not amend any completed plan.

## Use

`risk-profile-3-advisory-effectiveness.md` may use this document as input when
it evaluates whether advisory context is sufficient. A future plan may select
only the properties supported by observed evidence; it must not treat this
document's mechanisms as a commitment or as authority to expand the completed
advisory feature.

## Properties worth retaining

- **Grounded work remains mandatory.** A risk declaration must not license
  omissions of named files, symbols, tests, compatibility work, or a concrete
  safety obligation.
- **Declaration changes need a clear authority boundary.** If an automated
  detail rewrite can propose a different risk profile or rationale, the system
  must state whether it may apply that change or must leave an anchored
  explanation for a human decision.
- **A material contradiction needs one intelligible question.** Concrete,
  connected plan or code evidence may justify an explicit escalation asking
  whether the declaration remains appropriate. It must not disappear into a
  collection of unrelated procedural demands.
- **Authoring and auditing remain independent.** Advisory context used to
  author or review detail must not silently influence completeness-audit
  results, routing, or cache reuse.
- **A guardrail must preserve the common case.** A proposed enforcement
  mechanic must be traced against ordinary detail creation and rewrite flows,
  not only the exceptional example that motivated it.

## Candidate mechanisms that require evidence

- Require an explicit human confirmation before an automated flow changes a
  `risk_profile` declaration or its rationale.
- Emit one anchored, evidence-backed declaration-mismatch question when the
  actual changed surface contradicts a declaration.
- Refuse a narrowly named automatic mutation only when an identified safety
  invariant cannot otherwise be preserved.

Each candidate is conditional. The first two are not interchangeable: human
authority concerns mutation, while escalation concerns what a reviewer needs
to decide. A future proposal must identify which property has failed and prove
that its selected mechanic delivers that property.

## Deliberately not carried forward

The unexecuted design's closed ceremony taxonomy, risk-profile policy module,
audit suppression, custom finding grammar, and broad automatic-edit refusal
are not current contracts. No evidence yet establishes that they solve a real
failure more proportionately than advisory context and ordinary review.
