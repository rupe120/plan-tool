> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Audit Shape Registry
intent: Give users an interactive, evidence-bearing arm-clustering prompt before they
  manually apply conceptual audit findings. The prompt must help a user decide whether
  the concentrated arm belongs or should be carved, while never turning that decision
  into a gate, an automatic apply, or a change to ordinary finding dispatch. The implementation
  must not reuse `Recommendation.step_id` for audit feedback. That field is an existing
  execution target used by generic review walks and cross-run tooling; using it as
  audit metadata made a small feedback feature grow into stale-target and routing
  machinery. The feedback transport is instead one small, dedicated `AuditShapeAdvisory`
  payload saved with a completeness review.
status: completed
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add audit shape types and pure checks
  intent: It gives the audit flow one typed, non-executable registry for shape eligibility
    and documented classifications.
  creates:
  - plan_tool/audit_shapes.py
  - tests/test_audit_shapes.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/audit-shape-registry/01-audit-shape-types-pure-checks.md
  status: done
- id: 2
  title: Parse audit tags, evaluate arms, and persist the advisory
  intent: It captures reliable per-finding audit evidence, evaluates one fail-closed
    arm-clustering advisory, and persists that non-executable payload without turning
    feedback into an apply target.
  files:
  - plan_tool/audit_shapes.py
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - plan_tool/review_persistence.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/completeness_report.py
  - tests/test_audit_shapes.py
  - tests/test_review.py
  - tests/test_review_persistence.py
  - tests/cli/test_completeness_cmd.py
  allowed_mentions:
  - plan_tool/review_walk.py
  - plan_tool/schema.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/audit-shape-registry/02-parse-audit-tags-evaluate-arms-persist.md
  status: done
- id: 3
  title: Render fresh arm advice and retire count-only guidance
  intent: It presents the stored, source-fingerprint-fresh keep-or-carve advisory
    at audit and manual-apply decision points, while preserving blocking and apply
    behavior.
  files:
  - plan_tool/review.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/completeness_report.py
  - tests/test_completeness_report.py
  - tests/test_review.py
  - tests/test_cli.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  - DATA_CONTRACT.md
  - docs/AUDIT_FLOW.md
  - docs/cli/README.md
  - docs/cli/completeness-audit.md
  - docs/cli/completeness-apply.md
  complexity: medium
  change_type: feature
  gate:
  - '! rg -n ''recommend_audit_passes|one-short|tapering|non-converging'' plan_tool/review.py
    plan_tool/cli/completeness_phases.py plan_tool/completeness_report.py'
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/audit-shape-registry/03-render-fresh-arm-advice-retire-count.md
  status: done
- id: 4
  title: Validate the documented boundary and record Backlog
  intent: It keeps the ordered CLAUDE.md records aligned with the registry and records
    the bounded, shipped design and deferred future work.
  files:
  - CLAUDE.md
  - plan_tool/cli/inspect.py
  - tests/cli/test_inspect_cmds.py
  - BACKLOG.md
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  - 3
  detail: docs/implementation-plans/plan-details/audit-shape-registry/04-validate-documented-boundary-record.md
  status: done
---
# Audit Shape Registry

## Overview

Add a dedicated `AuditShapeAdvisory` that gives users an evidence-bearing `arm-clustering` keep-or-carve prompt before manual conceptual apply. The advisory is optional, saved with a completeness review, shown only when its source plan fingerprint matches the current plan, and never creates a software gate, apply action, or reroute. The existing agent-facing, user-visible override rule remains a separate operating policy for choosing to apply findings. `Recommendation.step_id` remains an execution target for ordinary recommendations and is not used for audit feedback.

## Problem statement

Conceptual audit findings can concentrate on a contiguous group of plan steps, but users currently receive no focused prompt to decide whether that arm belongs or should be carved. Reusing `Recommendation.step_id` for this feedback overloaded an existing generic review and cross-run execution target, creating stale-target and routing machinery for a small advisory feature.

## Architecture

Create a stdlib-only `plan_tool/audit_shapes.py` registry containing the five stable shape IDs, settled tells, and classifications. The final count-free `arm-clustering` tell is “Material conceptual findings form a strict-majority, contiguous proper arm of committed plan steps”; step 4 copies that registry record into `CLAUDE.md`. Only `arm-clustering` is an advisory emitter; `check-saturation`, `measurement-instrument-adequacy`, `self-seeded-finding`, and `remedy-proportionality` remain `judgment_only`. Keep the pure arm evaluator independent of CLI, persistence, filesystem, and model invocation code.

Parse an optional literal `[audit-step:N]` immediately after `[anchor-slug]` into a narrow ephemeral audit-result envelope or equivalent mapping keyed by stable finding ID, rather than storing it on `Recommendation`. For a fresh audit, use the existing calibrated materiality rule once, require cross-sample consensus on one valid current non-`done` step, and emit at most one advisory for a qualifying strict-majority, non-plan-wide, gap-free contiguous arm in declared plan order. The payload records `shape_id`, source plan fingerprint, ordered arm step IDs, material and arm finding IDs, and counts so renderers do not reinterpret findings.

Persist the optional additive `audit_shape_advisory` field on completeness `SavedReview`. Its source fingerprint covers the exact plan and resolved run-grade detail inputs that were sampled. The payload carries only typed, non-routing evidence (stable ID, anchor slug, audit axis, and counts), never finding prose or executable targets. A malformed optional payload is unavailable advisory data, not a reason to reject an otherwise valid saved review; malformed core data and unsupported versions still reject. Fresh audit output, concise iterate output, pre-apply checkpoint, persisted report text, and public JSON consume that same payload; `completeness-apply` reads it before serial or parallel conceptual apply and suppresses it when the source fingerprint is stale. Do not change `review-walk`, `review_actions`, `launcher.apply_finding`, `convergence_diagnosis`, generic saved-review dispatch, or their routing contracts. Retire count-only tapering, one-short, and non-converging recommendation behavior while retaining compatibility-null `recommendation_kind`, `recommended_passes`, and `recommendation_advice` coverage keys.

Document the additive field and retired fields in `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, CLI docs, active `CLAUDE.md`, and BACKLOG #125 guidance. Add a no-model `validate` advisory that compares complete ordered documented records with `AUDIT_SHAPES` without changing validation exit behavior, and update BACKLOG #224 with the bounded design.

## Input

This plan leaves existing recommendation routing untouched. It extends completeness `SavedReview` additively with optional `audit_shape_advisory`, preserves legacy review JSON loading, consumes the existing calibrated materiality rule for fresh audits only, and preserves the public JSON coverage keys `recommendation_kind`, `recommended_passes`, and `recommendation_advice` with `null` values.

## References

- [Python dataclasses](https://docs.python.org/3.13/library/dataclasses.html) — Covers frozen dataclasses, defaults, and serialization helpers for the immutable advisory and saved-review payloads.
- [Python regular-expression operations](https://docs.python.org/3.13/library/re.html) — Defines compiled-pattern matching needed to strictly parse the literal `[audit-step:N]` envelope.
- [Python JSON encoder and decoder](https://docs.python.org/3.13/library/json.html) — Documents JSON loading and serialization behavior for the additive, backward-compatible saved-review field.
- [Python hashlib](https://docs.python.org/3.13/library/hashlib.html) — Covers SHA-256 hashing used to compare the advisory source-plan fingerprint with current plan state.
- [Pydantic Models](https://pydantic.dev/docs/validation/latest/concepts/models/) — Explains typed model validation and serialization relevant to consuming the existing Plan and Step schema.
- [pytest parametrization](https://docs.pytest.org/en/stable/how-to/parametrize.html) — Shows how to express the plan’s large matrix of parser, consensus, contiguity, persistence, and stale-fingerprint cases.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- No use of `Recommendation.step_id` or raw finding prose as a feedback, attribution, or cross-run transport.
- No generic walk, action dispatcher, launcher, or convergence-diagnosis change.
- No product-level feedback gate, refusal to advance, automatic carve, automatic apply, threshold tuning, exit-code change, or mandatory acknowledgement. This does not remove the existing agent-facing, user-visible override policy for a human who elects to apply findings.
- No check-saturation or self-seeded emitter, historical causal attribution, Git-range analysis, citations, revisions, or checkpoints beyond the dedicated advisory's source plan fingerprint.
- No arbitrary new feedback detector for measurement-instrument adequacy or remedy proportionality.

## Risks

- LLM tag omissions, conflicting samples, a response still missing either required findings heading after its retry, or an absent/failed audit call can make attribution incomplete; suppress the advisory when any required reference or sample is malformed, missing, conflicting, ineligible, or failed while retaining ordinary review findings and their existing neutral error accounting.
- A stale sidecar can still guide review through saved conceptual findings; hide its dedicated advisory when the source plan fingerprint is stale.
- Persisted evidence could be mistaken for historical causality or executable routing data; keep it small, frozen, and non-executable.
- A renderer may need evidence not in the payload; add the minimum typed evidence to `AuditShapeAdvisory` rather than reading `Recommendation`, report history, Git, or free-form text.

## Testing

- Pin all `AUDIT_SHAPES` registry records and only-one-emitter eligibility.
- Exercise literal `[audit-step:N]` parsing; invalid, prose-only, repeated, unknown, multi-step, done-step, conflicting, and missing references fail closed while ordinary recommendations retain `step_id=None`.
- Exercise the full material denominator, cross-sample consensus, strict-majority arm selection, ties, gaps, whole-plan arms, and insufficient support.
- Round-trip `audit_shape_advisory`, including non-routing anchor/axis evidence; verify legacy review JSON loads without one, malformed optional advisory data leaves ordinary findings and annotations usable, malformed core data still rejects, and fresh, reused, and saved-apply paths render only a stored exact-input-fingerprint-fresh payload.
- Prove serial and parallel `completeness-apply` render the payload before normal work without changing a recommendation or generic apply target.
- Pin compatibility-null `recommendation_kind`, `recommended_passes`, and `recommendation_advice`, additive JSON output, absence of legacy count-route operator guidance, and unchanged block and exit behavior.
- Prove a budget-limited audit reports coverage facts without either a specific or fallback instruction to increase `--audit-passes`.
- Verify `validate` detects `CLAUDE.md` registry drift without a model call or changed exit behavior.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.
- step 4 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- A fresh audit shows an evidence-bearing `arm-clustering` keep-or-carve prompt before manual conceptual apply only when a valid dedicated advisory exists.
- A reused audit shows exactly the stored material evidence when its source plan fingerprint matches, and shows no advisory when it does not.
- An absent, failed, or malformed audit sample prevents advisory emission without changing ordinary finding handling; malformed optional persisted advice likewise cannot block the saved finding walk.
- No audit feedback mechanism routes, retargets, clears, or otherwise alters a `Recommendation` or generic saved-review walk.
- Only `arm-clustering` emits an advisory; the other four documented shapes remain `judgment_only` and non-emitting.
- `completeness-apply` renders a fresh saved advisory before normal serial or parallel conceptual apply without changing recommendations, apply queues, block behavior, or exit status.
- The old count-only taper/convergence advice is absent while `recommendation_kind`, `recommended_passes`, and `recommendation_advice` remain present with `null` values.
- `validate` reports `CLAUDE.md` registry drift without a model call or changed validation exit behavior.

## Deferred

- `check-saturation` and `self-seeded-finding` emitter work remains deferred in `plan-seeds/audit-shape-saturation-and-provenance.md`.
