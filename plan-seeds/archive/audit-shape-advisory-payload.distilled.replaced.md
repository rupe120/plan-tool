> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

## Overview

Add a dedicated `AuditShapeAdvisory` that gives users an evidence-bearing `arm-clustering` keep-or-carve prompt before manual conceptual apply. The advisory is optional, saved with a completeness review, shown only when its source plan fingerprint matches the current plan, and never blocks, applies, or reroutes work. `Recommendation.step_id` remains an execution target for ordinary recommendations and is not used for audit feedback.

## Problem statement

Conceptual audit findings can concentrate on a contiguous group of plan steps, but users currently receive no focused prompt to decide whether that arm belongs or should be carved. Reusing `Recommendation.step_id` for this feedback overloaded an existing generic review and cross-run execution target, creating stale-target and routing machinery for a small advisory feature.

## Architecture

Create a stdlib-only `plan_tool/audit_shapes.py` registry containing the five stable shape IDs, tells, and classifications from `CLAUDE.md`. Only `arm-clustering` is an advisory emitter; `check-saturation`, `measurement-instrument-adequacy`, `self-seeded-finding`, and `remedy-proportionality` remain `judgment_only`. Keep the pure arm evaluator independent of CLI, persistence, filesystem, and model invocation code.

Parse an optional literal `[audit-step:N]` immediately after `[anchor-slug]` into a narrow ephemeral audit-result envelope or equivalent mapping keyed by stable finding ID, rather than storing it on `Recommendation`. For a fresh audit, use the existing calibrated materiality rule once, require cross-sample consensus on one valid current non-`done` step, and emit at most one advisory for a qualifying strict-majority, non-plan-wide, gap-free contiguous arm in declared plan order. The payload records `shape_id`, source plan fingerprint, ordered arm step IDs, material and arm finding IDs, and counts so renderers do not reinterpret findings.

Persist the optional additive `audit_shape_advisory` field on completeness `SavedReview`. Fresh audit output, concise iterate output, pre-apply checkpoint, persisted report text, and public JSON consume that same payload; `completeness-apply` reads it before serial or parallel conceptual apply and suppresses it when the source fingerprint is stale. Do not change `review-walk`, `review_actions`, `launcher.apply_finding`, `convergence_diagnosis`, generic saved-review dispatch, or their routing contracts. Retire count-only tapering, one-short, and non-converging recommendation behavior while retaining compatibility-null `recommendation_kind`, `recommended_passes`, and `recommendation_advice` coverage keys.

Document the additive field and retired fields in `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, CLI docs, active `CLAUDE.md`, and BACKLOG #125 guidance. Add a no-model `validate` advisory that compares complete ordered documented records with `AUDIT_SHAPES` without changing validation exit behavior, and update BACKLOG #224 with the bounded design.

## Out of scope

- No use of `Recommendation.step_id` or raw finding prose as a feedback, attribution, or cross-run transport.
- No generic walk, action dispatcher, launcher, or convergence-diagnosis change.
- No feedback gate, refusal to advance, automatic carve, automatic apply, threshold tuning, exit-code change, or mandatory acknowledgement.
- No check-saturation or self-seeded emitter, historical causal attribution, Git-range analysis, citations, revisions, or checkpoints beyond the dedicated advisory's source plan fingerprint.
- No arbitrary new feedback detector for measurement-instrument adequacy or remedy proportionality.

## Risks

- LLM tag omissions and conflicting samples can make attribution incomplete; suppress the advisory when any required reference is missing, malformed, conflicting, or ineligible.
- A stale sidecar can still guide review through saved conceptual findings; hide its dedicated advisory when the source plan fingerprint is stale.
- Persisted evidence could be mistaken for historical causality or executable routing data; keep it small, frozen, and non-executable.
- A renderer may need evidence not in the payload; add the minimum typed evidence to `AuditShapeAdvisory` rather than reading `Recommendation`, report history, Git, or free-form text.

## Testing

- Pin all `AUDIT_SHAPES` registry records and only-one-emitter eligibility.
- Exercise literal `[audit-step:N]` parsing; invalid, prose-only, repeated, unknown, multi-step, done-step, conflicting, and missing references fail closed while ordinary recommendations retain `step_id=None`.
- Exercise the full material denominator, cross-sample consensus, strict-majority arm selection, ties, gaps, whole-plan arms, and insufficient support.
- Round-trip `audit_shape_advisory`; verify legacy review JSON loads without one and fresh, reused, and saved-apply paths render only a stored source-fingerprint-fresh payload.
- Prove serial and parallel `completeness-apply` render the payload before normal work without changing a recommendation or generic apply target.
- Pin compatibility-null `recommendation_kind`, `recommended_passes`, and `recommendation_advice`, additive JSON output, absence of legacy count-route operator guidance, and unchanged block and exit behavior.
- Verify `validate` detects `CLAUDE.md` registry drift without a model call or changed exit behavior.

## Acceptance criteria

- A fresh audit shows an evidence-bearing `arm-clustering` keep-or-carve prompt before manual conceptual apply only when a valid dedicated advisory exists.
- A reused audit shows exactly the stored material evidence when its source plan fingerprint matches, and shows no advisory when it does not.
- No audit feedback mechanism routes, retargets, clears, or otherwise alters a `Recommendation` or generic saved-review walk.
- Only `arm-clustering` emits an advisory; the other four documented shapes remain `judgment_only` and non-emitting.
- `completeness-apply` renders a fresh saved advisory before normal serial or parallel conceptual apply without changing recommendations, apply queues, block behavior, or exit status.
- The old count-only taper/convergence advice is absent while `recommendation_kind`, `recommended_passes`, and `recommendation_advice` remain present with `null` values.
- `validate` reports `CLAUDE.md` registry drift without a model call or changed validation exit behavior.

## Deferred

- `check-saturation` and `self-seeded-finding` emitter work remains deferred in `plan-seeds/audit-shape-saturation-and-provenance.md`.

## Input

This plan consumes the existing `Recommendation.step_id` execution-target contract, which ordinary conceptual recommendations continue to expose as `step_id=None` for audit feedback. It extends completeness `SavedReview` additively with optional `audit_shape_advisory`, preserves legacy review JSON loading, consumes the existing calibrated materiality rule for fresh audits only, and preserves the public JSON coverage keys `recommendation_kind`, `recommended_passes`, and `recommendation_advice` with `null` values.
