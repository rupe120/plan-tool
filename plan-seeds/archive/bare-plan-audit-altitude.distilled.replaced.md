> **Replaced**: this file has been superseded by `docs/implementation-plans/2-bare-plan-audit-altitude.md`.
> Preserved here for history; do not edit.

## Overview

This plan makes the bare-plan audit distinguish a selected design's required properties from implementation mechanisms that a later detail bundle must choose. The prompt preserves correctness findings for authority, scope, ordering, unsafe invariants, acceptance properties, contradictions, and uncovered grounded routes, while leaving mechanism choices to detail unless a settled property makes one indispensable. A deterministic, recommendation-text-only advisory composes with the existing `edit_drift` signal to help the operator reconsider property-level wording or defer a mechanism to detail; it remains advice and does not affect enforcement. No blocking predicate gains a new non-deterministic input.

## Problem statement

The bare-stage blocking policy already demotes plan completeness, but a mechanism preference emitted as plan correctness can still block convergence even when it belongs to a detail decision. Because the audit prompt lacks an explicit correctness-versus-completeness altitude rule, the current gate can amplify the last implementation-shaped plan edit instead of testing the plan's design. The existing blocking policy must remain the sole enforcement surface.

## Architecture

Prompt guidance owns what the auditor generates. It keeps authority, scope, ordering, unsafe invariants, acceptance properties, contradictions, and uncovered grounded routes at plan-correctness altitude, while leaving serializers, parser internals, fixture shape, telemetry values, typed carriers, and dependency-rewrite choices to detail unless a settled property makes one indispensable.

The existing stage-aware blocking policy evaluates findings unchanged. A pure classifier uses only persisted finding text to produce an operator-facing advisory, and its output never enters blocking, continuation, failure, or exit-code decisions.

When the classifier coincides with `edit_drift`'s prior-apply-set match, the operator receives one combined advisory to reconsider property-level wording or defer the mechanism to detail. `edit_drift` remains an apply-set comparison rather than durable causal provenance; #231 owns any future provenance engine.

## Out of scope

- A new gate, response field, model-assigned altitude label, automatic deferral, automatic apply, or exit-code change; the existing blocking policy remains the sole enforcement surface.
- Changes to existing blocking predicates, convergence continuation, failure behavior, audit-pass counts, arm clustering, or the detail-grounded bar; this work changes bare-altitude guidance and advisory rendering only.
- Widening the existing domain demotion or reviving an `unknown`-domain carve out; neither is part of this policy.
- A second provenance system or a causal claim from an apply-set match; `edit_drift` remains a comparison signal.
- Work owned by #91, #139, #231, #241, #248, or #262; those concerns remain separate.
- Create-path mechanics; the 2026-08-17 #291 replay supplies acceptance evidence without expanding this policy into that area.

## Risks

- Prompt guidance can still mislabel a mechanism preference as correctness. Preserve an operator advisory and record the measured miss rather than adding a gate-facing classifier.
- A classifier that is not stable for identical text is unsafe even as a signal. Keep the classifier pure, reproducible, and advisory-only.
- The policy can hide a real property gap if it confuses route coverage with route mechanics. Keep coverage of a declared outer-boundary, ownership, ordering, or acceptance property as a bare-plan correctness question.

## Testing

Prove that the prompt keeps genuine bare-plan contracts in correctness and leaves mechanics to detail. Prove that the deterministic classifier returns the same advisory label for identical persisted finding text across repeated calls, and that neither the classifier nor its composition with `edit_drift` changes any blocking, continuation, failure, or exit-code result.

Retain the #291 stage-separated replay as a canned fixture. Every combined and split proposal route must preserve a named outer-boundary contract. At bare stage, an uncovered route remains a correctness gap, while typed attachment, dependency ordering, or another delivery mechanism remains deferred to detail. Once detail exists, the detail-grounded audit may require the selected mechanism.

## Acceptance criteria

- The bare audit distinguishes plan-level properties from implementation mechanisms without creating a new gate or changing a blocking predicate.
- An uncovered grounded route for a named property remains a bare-plan correctness finding, while its unset delivery mechanics do not become a blocking bare-plan obligation.
- The deterministic advisory is stable for identical finding text and remains outside all blocking, continuation, failure, and exit-code decisions.
- The #291 replay retains its named outer-boundary property across every combined and split proposal route: an uncovered route remains a correctness gap at bare stage, typed attachment, dependency ordering, or another delivery mechanism remains deferred to detail, and the detail-grounded audit may require the selected mechanism once detail exists.
- The resulting plan retires or updates BACKLOG #290 when implementation ships without removing provenance that active follow-up work needs.

## Deferred

- #231 owns durable apply-to-finding provenance.
- #241 owns its separate bare-prompt completeness-generation policy.
- #262 owns a reactive post-churn advisory.
- Run-time attribution stays separate from this work and is already satisfied
  by the current phase distinction.

## Input

The prompt and classifier consume persisted conceptual-finding text produced by the existing bare-plan audit. Advisory composition also consumes the existing `edit_drift` prior-apply-set match, which remains an apply-set comparison and cannot establish causal provenance. The existing stage-aware blocking policy remains the authoritative enforcement contract and evaluates findings unchanged. The 2026-08-17 #291 replay supplies the stage-separated acceptance fixture.
