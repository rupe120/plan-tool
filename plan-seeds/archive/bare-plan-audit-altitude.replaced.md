> **Replaced**: this file has been superseded by `docs/implementation-plans/2-bare-plan-audit-altitude.md`.
> Preserved here for history; do not edit.

# Bare-plan audit altitude policy

## Outcome

A bare-plan audit no longer blocks convergence on findings that describe
implementation mechanics a detail file should own, while genuine plan-level
defects — including an uncovered route for a named property — remain
correctness findings. No blocking predicate gains a new non-deterministic
input.

## In scope

- The bare-altitude instruction that determines whether the conceptual auditor
  emits a correctness or completeness finding.
- A pure classifier over a finding's persisted text and advisory rendering in
  convergence and completeness output.
- An advisory composition with the existing `edit_drift` signal.
- Prompt, classifier, advisory, and replay coverage for these boundaries.

## Overview

Make the bare-plan audit distinguish a selected design's properties from the
implementation mechanisms that a later detail bundle must choose. The prompt
does the primary work: it preserves correctness findings for authority, scope,
ordering, unsafe invariants, acceptance properties, contradictions, and
uncovered grounded routes, while leaving serializers, parser internals,
fixture shape, telemetry values, typed carriers, and dependency-rewrite
choices to detail unless a settled property makes one indispensable.

Add a deterministic, recommendation-text-only advisory for likely
mechanism-level correctness findings. When it coincides with `edit_drift`'s
prior-apply-set match, the operator receives one advisory to reconsider
property-level wording or defer the mechanism to detail. The combined signal
is advice, not causal proof or enforcement.

## Problem statement

The bare-stage blocking policy already demotes plan completeness, but a
mechanism preference emitted as plan correctness can still block despite
belonging to a detail decision. The audit prompt lacks an explicit
correctness-versus-completeness altitude rule, so the current gate can amplify
the last implementation-shaped plan edit instead of testing the plan's design.
The existing blocking policy must remain the sole enforcement surface.

## Architecture

Prompt guidance owns what the auditor generates; the existing stage-aware
blocking policy evaluates those findings unchanged. The deterministic advisory
classifies only persisted finding text and renders an operator-facing warning.
It neither supplies a model-authored finding field nor enters blocking,
continuation, failure, or exit-code decisions. Existing `edit_drift` remains
an apply-set comparison, not durable causal provenance; #231 owns any future
provenance engine.

## Out of scope / Non-goals

- A new gate, response field, model-assigned altitude label, automatic
  deferral, automatic apply, or exit-code change.
- Changes to existing blocking predicates, convergence continuation, failure
  behavior, audit-pass counts, arm clustering, or the detail-grounded bar.
- Widening the existing domain demotion or reviving an `unknown`-domain carve
  out.
- A second provenance system, a causal claim from an apply-set match, or work
  owned by #91, #139, #231, #241, #248, or #262.

## Risks

- Prompt guidance can still mislabel a mechanism preference as correctness.
  The response is to preserve an advisory for the operator and record the
  measured miss, not to add a gate-facing classifier.
- A classifier that is not stable for identical text is unsafe even as a
  signal. The classifier must be pure, reproducible, and advisory-only.
- The policy can hide a real property gap if it confuses route coverage with
  route mechanics. Coverage of a declared outer-boundary, ownership, ordering,
  or acceptance property remains a bare-plan correctness question.

## Testing

Prove the prompt keeps genuine bare-plan contracts in correctness and leaves
mechanics to detail. A deterministic classifier returns the same advisory
label for identical persisted finding text across repeated calls, and neither
the classifier nor its composition with `edit_drift` changes a blocking,
continuation, failure, or exit-code result.

Retain the #291 stage-separated replay as a canned fixture. Its property is
that every combined and split proposal route preserves a named outer-boundary
contract. At bare stage, an uncovered route remains a correctness gap; typed
attachment, dependency ordering, or another delivery mechanism remains
deferred to detail. Once detail exists, the detail-grounded audit may require
the selected mechanism. The replay must survive seed distillation in this
section and the matching acceptance criteria, rather than being compressed
into rationale.

## Acceptance criteria

- The bare audit distinguishes plan-level properties from implementation
  mechanisms without creating a new gate or changing a blocking predicate.
- An uncovered grounded route for a named property remains a bare-plan
  correctness finding, while its unset delivery mechanics do not become a
  blocking bare-plan obligation.
- The deterministic advisory is stable for identical finding text and remains
  outside all blocking, continuation, failure, and exit-code decisions.
- The #291 replay retains its property, routes, bare-stage disposition, and
  detail-stage disposition through seed distillation and into the resulting
  plan's testing and acceptance evidence.
- The resulting plan retires or updates BACKLOG #290 when implementation
  ships, without removing provenance that active follow-up work needs.

## Deferred

- #231 owns durable apply-to-finding provenance.
- #241 owns its separate bare-prompt completeness-generation policy.
- #262 owns a reactive post-churn advisory.
- Run-time attribution stays separate from this work and is already satisfied
  by the current phase distinction.

## Source

BACKLOG #290. The 2026-08-17 #291 replay supplies the acceptance fixture; it
does not expand this policy into create-path mechanics.
