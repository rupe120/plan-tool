# Seed: convergence policy-channel ownership

## Outcome

Establish an explicit, testable ownership boundary for convergence blocking:
each flow declares the finding channel that drives iteration, finalization, and
human escalation; the bare-plan bar remains conservative; and no caller gains
or loses blocking behavior by accidentally sharing a predicate meant for a
different channel.

## In scope

- Map `create`, `detail`, `completeness-audit`, and `reconcile` to the finding
  sets they actually place in convergence state, use at finalization, or hand
  to an operator.
- Preserve `bare` versus `detail` as an explicit stage selector for conceptual
  findings only. As of 2026-08-14, both stages invoke domain classification
  (docs-only demotion) for `plan-correctness`; `plan-completeness` medium
  keeps its unconditional bare non-block, independent of domain.
- Keep deterministic contract, self-consistency, and coverage failures on
  their existing severity-based path.
- Record the settled rule that reconcile's impact-calibration overlay is an
  intentionally independent review-risk policy, not an additional grounded
  conceptual safeguard.
- Document and test only a future caller that demonstrably consumes both
  channels in one decision.

## Overview

The shipped stage-differentiated policy correctly separates bare and
detail-grounded conceptual audits, but the follow-up described four commands
as though they all iterate the same findings. They do not. The replacement
effort is about policy ownership, not universal predicate reuse.

## Problem statement

Sharing a blocking helper is safe only when its callers answer the same
question. Here, automatic iteration, final clean/fail reporting, and
human-action escalation consume different evidence. Flattening them would
either classify bare prose with invented domains, make non-conceptual failures
advisory, or remove reconcile's deliberate impact safeguard.

## Architecture

Model blocking as three channels:

1. Conceptual audit findings use an explicit audit stage (2026-08-14: both
   stages now consult domain). At both `bare` and `detail`, medium demotes
   only when classified `docs` — `code-logic`, `unit-test`, and `unknown` all
   block. Bare-stage `plan-completeness` medium stays an unconditional
   non-block regardless of domain (`completeness-apply` is withheld until the
   detail bundle exists).
2. Deterministic checks use their own severity/coverage contract and are never
   domain-demoted by conceptual-audit policy.
3. Reconcile's impact calibration is a separate review-risk channel. It keeps
   high-impact advisory findings visible to its loop and may calibrate a
   low-impact medium; it does not use a conceptual finding's audit stage or
   domain classification.

Every caller must select its channel deliberately. No default stage or
implicit conversion of conceptual findings into apply-eligible loop state is
permitted.

## Out of scope

- Changing the settled bare-plan bar or requiring a multi-pass clean streak.
- Reviving retired #231 bad-fix provenance.
- Generic `detail --commit` readiness/exit policy (#262) or any new reporting
  work. #260 is parked pending a concrete misleading output fixture.
- Persisting a new `Recommendation.domain` field or redesigning source
  taxonomy.
- Treating agreement between plan prose and code as a new quality gate.

## Allowed behavior changes

- A confirmed caller may select the correct existing policy channel or render
  its resulting stop/handoff state more accurately.
- If the caller map proves no code change is needed, documentation and tests
  may become the sole delivery.

## Allowed reorganization

Only a small shared selector or caller-local adapter may be extracted if it
prevents a caller from defaulting to the wrong policy channel. Do not merge the
three channels into a universal predicate.

## Risks

- Calling a domain classifier on a bare finding risks false precision and
  hiding design defects. Addressed 2026-08-14 by keeping the rule narrow:
  bare-stage `plan-correctness` demotes only on an explicit `docs` match,
  never on `unknown` — bare-stage findings mostly lack path/phrase signal
  (they describe plan-body soundness, not files), and treating `unknown` as
  non-blocking there would have eroded `plan-correctness`'s
  always-actionable invariant for the common case rather than filtering
  noise.
- Feeding conceptual findings into an apply loop changes its action model and
  can cause unsupported automatic edits.
- Composing reconcile's impact policy with the conceptual bar can remove the
  safeguard that keeps a high-impact advisory visible to its loop.

## Testing

Use a caller/channel matrix rather than one predicate-only test. Prove that a
bare or detail medium correctness finding classified `docs` is advisory; a
medium finding classified `code-logic`, `unit-test`, or `unknown` blocks at
both stages; bare-stage `plan-completeness` medium never blocks regardless of
domain; and every deterministic coverage/contract failure keeps its stated
severity behavior.
Assert that create and detail do not silently begin consuming conceptual
findings. If a future caller combines these streams, pin reconcile's
independent impact-overlay behavior at that caller.

## Acceptance criteria

- Each of the four flows has a documented iteration, finalization, and
  escalation channel, with any intentional difference named.
- Bare-plan policy is not weakened by #261; its domain classification (added
  2026-08-14, docs-only, `plan-correctness` only) stays narrow enough that
  `plan-correctness`'s always-actionable-at-bare-stage invariant holds.
- Conceptual, deterministic, and reconcile-impact policies cannot be confused
  by a default argument or a shared catch-all predicate.
- The settled map documents that no policy propagation is justified; a future
  code change requires evidence of an actual combined-channel consumer.

## Deferred

Generic readiness messaging after audit churn remains #262. Causal bad-fix
provenance is retired (#231); this seed must not reactivate it. #260 is parked
until a concrete misleading output warrants a small direct defect. Any new
quality judgment or prose-agreement gate is out of scope and is filed separately
rather than added to this policy boundary.

## References

- `BACKLOG.md` #261 — bare-plan policy boundary whose domain classification
  this seed keeps narrow.
- `plan_tool/convergence.py` — conceptual finding policy consumer.
- `plan_tool/cli/completeness_phases.py` — completeness command channel that
  remains distinct from the convergence predicate.
