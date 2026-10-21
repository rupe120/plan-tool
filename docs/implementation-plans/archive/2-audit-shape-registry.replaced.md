> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

---
title: Audit Shape Registry
intent: The five audit traps in CLAUDE.md's "Audit the why, not the what" section
  have stable IDs and explicit checked-versus-judgment-only classifications. Arm clustering
  is the one presently checked, advisory signal because its inputs are explicitly
  attributable current audit facts. Check saturation and self-seeded provenance remain
  judgment-only until separate, observable producer contracts earn a reclassification.
  No shape gates, changes an exit code, or automatically applies a remedy.
status: planning
priority: medium
enforce_step_tests: true
steps:
- id: 1
  title: Add the audit-shape registry and pure classification helpers
  intent: It makes the five-shape boundary executable data and permits only arm clustering
    to have an advisory emitter.
  creates:
  - plan_tool/audit_shapes.py
  - tests/test_audit_shapes.py
  complexity: medium
  change_type: feature
  detail: docs/implementation-plans/plan-details/audit-shape-registry/01-audit-shape-registry-pure.md
  status: current
- id: 2
  title: Replace the taper route with arm-clustering scope advice
  intent: It identifies an explicitly attributed, concentrated plan arm before findings
    are manually applied, then states the user-owned keep-or-carve decision.
  files:
  - plan_tool/audit_shapes.py
  - plan_tool/prompts/plan-audit.md
  - plan_tool/review.py
  - plan_tool/cli/completeness_phases.py
  - plan_tool/cli/completeness_cmd.py
  - plan_tool/cli/completeness_apply_parallel.py
  - plan_tool/completeness_report.py
  - plan_tool/convergence_diagnosis.py
  - BACKLOG.md
  - CLAUDE.md
  - DATA_CONTRACT.md
  - docs/AUDIT_FLOW.md
  - docs/cli/completeness-audit.md
  - docs/cli/completeness-apply.md
  - tests/test_audit_shapes.py
  - tests/test_review.py
  - tests/test_completeness_report.py
  - tests/cli/test_completeness_cmd.py
  - tests/cli/test_completeness_apply_parallel.py
  - tests/cli/test_review_actions.py
  - tests/test_convergence_diagnosis.py
  - tests/test_cli.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  detail: docs/implementation-plans/plan-details/audit-shape-registry/02-replace-taper-route-arm-clustering.md
- id: 3
  title: 'Pin documented classifications and record the bounded #224 outcome'
  intent: It prevents the documented and executable boundary from drifting and makes
    the deferred saturation and provenance work explicit rather than implicit.
  files:
  - CLAUDE.md
  - BACKLOG.md
  - plan_tool/audit_shapes.py
  - plan_tool/cli/inspect.py
  - tests/test_audit_shapes.py
  - tests/cli/test_inspect_cmds.py
  complexity: medium
  change_type: feature
  depends_on:
  - 1
  - 2
  detail: docs/implementation-plans/plan-details/audit-shape-registry/03-pin-documented-classifications-record.md
---
# Audit Shape Registry

## Overview

This is BACKLOG #224's tool-side half of the standing rule that a fired audit
shape is a scope decision, not a nag. It gives each of the five shapes a stable
name, an explicit classification, and a documented override rule. The tool
surfaces evidence and leaves every scope decision to the user.

## Problem statement

CLAUDE.md currently describes five recurring audit traps only as prose. That
leaves the checked-versus-judgment-only boundary vulnerable to accidental
expansion: a later session can make an unavailable data source look measured,
or turn a human scope judgment into a detector.

The current taper warning also names only a count trajectory and routes a
round-two signal to cross-run convergence history. It does not identify the
concentrated arm that must be kept with a reason or carved before findings are
applied.

## Architecture

`plan_tool/audit_shapes.py` is a stdlib-only leaf with one immutable, ordered
entry per CLAUDE.md audit shape: stable ID, one-line tell, and classification.
The registry is the only code-side mapping. The current classifications are:

1. `arm-clustering` — `checked`.
2. `check-saturation` — `judgment_only`.
3. `measurement-instrument-adequacy` — `judgment_only`.
4. `self-seeded-finding` — `judgment_only`.
5. `remedy-proportionality` — `judgment_only`.

Arm clustering has an observable input: the final conceptual-audit result can
carry an explicit known `step_id` for a finding whose remedy targets exactly
one plan step. The audit prompt supplies the literal tag `[step-id:N]`, where
`N` is `0` or `-?[1-9][0-9]*` for any integer ID allowed by the plan schema,
immediately after the existing `[anchor-slug]`; parser
validation preserves it without inferring from title or body prose. That
meaning is shared with the existing apply dispatcher, so a plan-wide,
multi-step, uncertain, or cross-step-remedy finding stays unattributed rather
than redirecting an apply.

The material denominator is every material conceptual finding in the final
normalized union, not just the tagged subset. Every occurrence of a stable
finding ID across the sampled passes must carry the same valid target tag; an
absent, malformed, unknown, repeated, plan-wide, or conflicting target makes
that finding unattributed. Any unattributed material finding suppresses the
advisory. The pure evaluator therefore emits at most one result only when there
are at least three material findings and one non-plan-wide, maximal gap-free arm
in declared plan order holds a strict majority. A gap is any declared step
between represented endpoints with no attributed material finding; it partitions
the evidence into separate arms and disqualifies only a proposed arm that spans
it. A majority arm on one side still signals. The maximal represented runs are
disjoint, so strict majority makes the selected arm unique. Missing, invalid,
tied, or plan-wide evidence produces no signal.

The advice uses the current normalized audit result while its report is being
assembled. A staleness-approved `reused_audit_recs` payload is also an allowed
final normalized result: it supplies saved findings, not cross-run evidence or
decision history. Neither path compares prior sidecars, adds report revisions,
or persists reusable advisory state; normal report Markdown may record the
contemporaneous rendered text. Both audit-only and `--iterate` paths prepare
the same result before rendering. `completeness-apply` recomputes the same
advisory only when the saved review's `plan_fingerprint` equals the current
plan fingerprint; on mismatch it suppresses advice while preserving the
existing staleness warning and non-gating saved-finding walk. Before filtering
or dispatch on that same mismatch, it strips every saved walk recommendation's
`step_id` in memory, so neither serial nor `--jobs N` apply can reinterpret a
reused numeric target as a different current step. It never rewrites the saved
sidecar. The target is valid only while the audited plan fingerprint remains
unchanged: before final iterate persistence and before each serial, parallel,
or replayed dispatch, a mismatch clears the remaining in-memory target IDs.
This happens before any serial or parallel dispatch.

Coverage-budget facts remain available, but tapering/non-converging behavior
and the `plan-tool convergence` route are retired. To preserve the existing
JSON schema, `coverage.recommendation_kind`, `recommended_passes`, and
`recommendation_advice` remain present and are always `null`; they are
documented compatibility fields, not an advice channel. A populated arm result
appears only in a documented additive, output-only `audit_shape_advisory`
object. It is never written to the saved-review recommendation schema.

When arm clustering fires, every report surface states the stable ID, arm,
countable evidence, and override rule: name why the arm still belongs or
propose a carve; say plainly that continuing overrides the signal. The advice
is not a `Recommendation`, does not affect blocking state or exit codes, and
does not mutate a plan.

The explicit conceptual-audit target remains local to the audit/apply handoff.
`plan_tool/convergence_diagnosis.py` must ignore `step_id` for
`plan-correctness` and `plan-completeness` findings when it loads report
history, retaining its established anchor-based diagnosis. This prevents a
current-report remedy target from silently changing a separate cross-run fork
without a cross-run attribution and staleness contract.

Check saturation and self-seeded provenance are deliberately non-emitting in
this plan. The audit found no complete eligible-target inventory for saturation
and no causal observation that can distinguish a finding-driven edit from a
direct user edit. Treating either absence as a persistence problem would make
an unobservable semantic judgment look mechanical. Their future investigation
is preserved in `plan-seeds/audit-shape-saturation-and-provenance.md`.

The authoritative CLAUDE.md list carries both the stable ID and classification
in a narrowly parseable annotation. `validate` compares exact membership,
uniqueness, order, and classification with the registry, reporting drift on a
valid plan without invoking a model or changing the normal validation result.

**Scope decision, 2026-08-03:** BACKLOG #224's original three checked shapes
are narrowed to arm clustering only. Saturation and self-seeded are deferred,
not silently removed; their forward seed requires independent observable
contracts before either can be proposed for reclassification.

## References

- [Python dataclasses Documentation](https://docs.python.org/3/library/dataclasses.html) — Immutable registry and advisory records.
- [Python unittest Documentation](https://docs.python.org/3/library/unittest.html) — Focused tests for the classification boundary and report behavior.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- A checked emitter for check saturation or self-seeded provenance.
- New finding citations, report revisions, checkpoints, Git-range analysis,
  causal attribution records, or saved-review advisory fields.
- A detector for measurement-instrument adequacy or remedy proportionality.
- A gate, exit-code flip, refusal to advance, automatic carve, automatic apply,
  or automatic threshold tuning based on an audit shape.
- A generic semantic judgment about whether an arm belongs, a producer is
  missing, an instrument is adequate, or a remedy is proportional.

## Risks

An LLM can omit or mis-tag a step reference. The literal target tag is valid
only when every sampled occurrence of the stable finding agrees; invalid,
unknown, repeated, multi-step, conflicting, and plan-wide findings remain
unattributed. Any such material finding suppresses the arm signal rather than
letting a tagged subset look complete. A stale saved review suppresses its
recomputed pre-apply advisory and its stale target IDs, never the existing
human review of saved gaps. A concentrated arm is evidence for a conversation,
not evidence that the arm should be removed.

Plan edits can also happen after a fresh audit starts. Every remaining target
must be cleared before a later serial, parallel-replay, or final-persistence
stage observes a changed plan fingerprint; targetless saved findings remain
reviewable. Cross-run diagnosis must likewise remain insulated from this
current-report target field.

The two deferred shapes may look measurable because their reports contain
prose and Git history. Neither has the required producer or causal ground
truth. Re-promoting either based on a lower threshold or a new prose matcher
would recreate the high-false-positive trap this plan prevents.

## Testing

Registry tests pin all five IDs, order, tells, and classifications, and prove
that only arm clustering is emitter-eligible. Parser and evaluator tests cover
the literal target-tag grammar (including zero and negative schema-valid IDs),
apply-target semantics, cross-sample consensus,
the full material denominator, unique maximal gap-free arm selection, ties,
gap-separated majority arms, plan-wide targets, and insufficient support. Report
and CLI tests cover fresh and reused audit output plus fingerprint-fresh
pre-apply serial and parallel recomputation and stale target-ID stripping,
compatibility-null coverage fields, unchanged exit behavior, and removal of
taper routing. Tests also pin target lifetime across iterate and replay paths
and prove cross-run diagnosis ignores conceptual-audit targets. Validate tests
detect ID or classification drift.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests covering the behavior this step changes; green before completion.
- step 2 (feature) — tests covering the behavior this step changes; green before completion.
- step 3 (feature) — tests covering the behavior this step changes; green before completion.

## Acceptance criteria

- Exactly five registry entries match the CLAUDE.md list by stable ID, order,
  tell, and classification; only arm clustering is `checked`.
- An arm advisory is emitted only from the literal, validated remedy-target tag,
  cross-sample consensus, and the full material denominator; it includes the
  unique arm, countable evidence, and explicit override statement.
- Any material finding with absent, invalid, conflicting, multi-step, or
  plan-wide attribution, and every tie, whole-plan arm, or insufficient set,
  produces no arm advisory. A gap splits the candidate arms; a strict-majority
  maximal arm that does not span that gap remains eligible.
- A plan-fingerprint mismatch preserves the saved gap for human review but
  strips its in-memory target ID and suppresses the recomputed advisory before
  serial or parallel dispatch; no stale target can redirect an apply.
- A target stays usable only while the plan fingerprint still equals the audited
  fingerprint; final iterate persistence and every later dispatch clear it on
  drift. Cross-run diagnosis ignores conceptual-audit target IDs altogether.
- Saturation and self-seeded provenance have no emitter path, no new persistence
  contract, and a dated forward seed that names the missing observables.
- The taper/non-converging route and its stale operator documentation are removed
  while coverage-budget reporting remains intact with compatibility-null legacy
  keys and a documented output-only arm-advisory field.
- Validate exposes documentation/registry drift without a model call, file
  mutation, or changed exit-code convention.
- BACKLOG #224 records the bounded outcome and points to the deferred seed when
  the implementation ships.

## Deferred

- `plan-seeds/audit-shape-saturation-and-provenance.md` owns any future work on
  an eligible-target inventory, provenance candidates, causal observability, or
  reclassification of saturation and self-seeded. Cross-run convergence
  diagnosis remains separate from this within-report advisory.
