# Audit-shape saturation and provenance observability

## Intent

Establish whether `check-saturation` and `self-seeded-finding` can ever earn
checked advisory emitters without turning missing ground truth into a proxy.
Either shape may remain judgment-only; successful investigation does not imply
that an emitter ships.

## Provenance

Deferred on 2026-08-03 while narrowing BACKLOG #224. The detailed plan audit
found that saturation has no persisted eligible-target denominator and that a
changed cited region cannot prove a later edit was caused by an earlier
finding. This seed preserves the questions without extending #224's registry
and arm-clustering core.

## Scope

- First identify an existing or independently deliverable source of truth for
  every eligible saturation target and its outcome. A count over fired findings
  alone is not a denominator.
- Treat changed cited regions as provenance candidates, never causal proof. A
  direct user edit must remain visible to the operator rather than being erased
  for lack of a tool-recorded apply event.
- If report checkpoints, revisions, or citation contracts are proposed, define
  one logical audit identity, unique ordered records, ancestry requirements,
  and hunk-level attribution before using them in an advisory.
- Measure false positives against a frozen, reviewed corpus. Insufficient
  history, noisy evidence, ambiguous line movement, rebases, dirty trees, or
  missing producer facts leave the candidate silent.
- Record a user-reviewed retain, reclassify, or kill decision for each shape.

## Non-goals

- No gate, exit-code change, automatic carve, automatic apply, or threshold
  tuning.
- No prose matcher that claims a producer is missing or an edit is causal.
- No implementation by extending BACKLOG #224 without a new scoped plan and
  explicit user review of the observable contract.

## Completion condition

The follow-up plan states a binary observable for each proposed emitter and a
testable fail-closed path. A result that keeps either or both shapes
`judgment_only` is a successful outcome.

## References

- `BACKLOG.md` #224 — narrowed audit-shape registry work that deferred these
  two observability questions.
- `plan_tool/review.py` — audit-shape classification surface where any future
  checked emitter remains fail-closed until its source facts exist.
