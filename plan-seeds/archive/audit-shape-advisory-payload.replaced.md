> **Replaced**: this file has been superseded by `docs/implementation-plans/2-audit-shape-registry.md`.
> Preserved here for history; do not edit.

# BACKLOG #224 — Dedicated arm-clustering feedback payload

## Outcome

Give users an interactive, evidence-bearing arm-clustering prompt before they
manually apply conceptual audit findings. The prompt must help a user decide
whether the concentrated arm belongs or should be carved, while never turning
that decision into a gate, an automatic apply, or a change to ordinary finding
dispatch.

The implementation must not reuse `Recommendation.step_id` for audit feedback.
That field is an existing execution target used by generic review walks and
cross-run tooling; using it as audit metadata made a small feedback feature
grow into stale-target and routing machinery. The feedback transport is instead
one small, dedicated `AuditShapeAdvisory` payload saved with a completeness
review.

## User-approved scope decision

On 2026-08-03, the user approved re-seeding the prior Step 2 rather than
continuing to harden `Recommendation.step_id` reuse. Preserve the registry,
the `check-saturation` and `self-seeded-finding` deferrals, and the
documentation-drift check. Replace only the overloaded feedback transport.

## In scope

### 1. Keep the five-shape registry narrow

- Create the stdlib-only `plan_tool/audit_shapes.py` registry with the five
  stable IDs, tells, and classifications from `CLAUDE.md`.
- Only `arm-clustering` is an advisory emitter. `check-saturation`,
  `measurement-instrument-adequacy`, `self-seeded-finding`, and
  `remedy-proportionality` remain `judgment_only` with no emitter path.
- Keep the pure arm evaluator independent of CLI, persistence, filesystem, and
  model invocation code.

### 2. Capture a dedicated advisory snapshot

- Extend the plan-audit prompt with one optional literal audit-reference tag:
  `[audit-step:N]` immediately after `[anchor-slug]`, where `N` is `0` or
  `-?[1-9][0-9]*` and names one current, non-`done` plan step whose planned
  work is at issue. It is not an apply target. Multi-step, plan-wide,
  uncertain, malformed, unknown, repeated, or prose-only references are
  unattributed.
- Keep parsed audit-step references outside `Recommendation`. Use a narrow
  ephemeral audit-result envelope or equivalent mapping keyed by stable finding
  ID while samples are unioned. The ordinary conceptual recommendations keep
  their existing `step_id=None` behavior.
- For a fresh audit, determine materiality once using the existing calibrated
  materiality rule. Require every material conceptual finding in the final
  normalized union to have the same valid audit-step reference in every sample
  where that stable finding appears. Any missing, malformed, conflicting, or
  ineligible reference suppresses the advisory.
- The pure evaluator emits at most one result when at least three material
  findings form a strict-majority, non-plan-wide, gap-free contiguous arm in
  declared plan order. A gap partitions maximal runs; a strict-majority run on
  one side remains eligible. Record the full material finding IDs, the arm
  finding IDs, ordered arm step IDs, and counts so a renderer can explain the
  evidence without reinterpreting findings later.
- Persist the result as an optional `audit_shape_advisory` field on a
  completeness `SavedReview`. Its self-contained contract includes the stable
  `shape_id`, the **source plan fingerprint** captured at audit time, ordered
  arm step IDs, full material and arm finding IDs/counts, and no mutable or
  executable target. It is an additive, explicitly documented saved-review
  schema field; legacy sidecars load with no advisory. It is not a
  `Recommendation`, annotation, apply directive, or cross-run input.
- A saved or reused audit never recomputes materiality from current report
  history. It either presents the stored advisory when its source fingerprint
  equals the current plan fingerprint, or presents no advisory. This freezes
  the evidence that was actually reviewed and avoids treating later calibration
  history as proof about an earlier report.

### 3. Render the advisory at the two user decision points

- For a fresh audit, pass the same dedicated advisory to audit-only Markdown,
  concise iterate output, pre-apply checkpoint, persisted report text, and the
  additive public JSON `audit_shape_advisory` object.
- For `completeness-apply`, read—not recompute—the saved advisory before any
  serial or parallel conceptual apply. Render it only when its source plan
  fingerprint still matches the plan on disk. A mismatch suppresses the
  advisory but preserves the existing saved-finding warning and human review
  flow.
- The message must name `arm-clustering`, the ordered arm, counts/evidence,
  and the explicit human rule: state why the arm belongs or propose a carve;
  continuing overrides the signal. It never prompts, blocks, changes exit
  status, changes an apply queue, or modifies any recommendation.
- Do not change `review-walk`, `review_actions`, `launcher.apply_finding`,
  `convergence_diagnosis`, generic saved-review dispatch, or their routing
  contracts. They see ordinary recommendations only.

### 4. Retire the weak count-only route, preserve compatibility

- Remove tapering, one-short, and non-converging recommendation behavior from
  the conceptual audit budget path. Keep budget-limited status, passes, caps,
  and confirmation facts.
- Keep the existing JSON coverage keys `recommendation_kind`,
  `recommended_passes`, and `recommendation_advice` present with `null` values
  for compatibility. Do not repurpose them for the advisory.
- Document the additive advisory field and retired fields in
  `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, CLI docs, active `CLAUDE.md` and
  BACKLOG #125 guidance, distinguishing active instructions from historical
  backlog evidence.

### 5. Pin the documented boundary

- Make `CLAUDE.md`'s authoritative five-shape list narrowly parseable, with
  stable ID, tell, classification, and user-owned override rule.
- Add a no-model `validate` advisory that compares complete ordered documented
  records against `AUDIT_SHAPES` without changing validation exit behavior.
- Update BACKLOG #224 with the bounded shipped design and point saturation and
  self-seeded future work at
  `plan-seeds/audit-shape-saturation-and-provenance.md`.

## Required implementation structure

Use four dependency-ordered steps:

1. Registry and pure classification helpers.
2. Audit-reference parsing, cross-sample consensus, pure arm evaluation, and
   optional `SavedReview.audit_shape_advisory` persistence.
3. Report/apply rendering, source-fingerprint freshness check, count-route
   retirement, and active documentation updates.
4. CLAUDE registry drift validation and BACKLOG #224 record.

Step 2 owns the new data contract and tests. Step 3 consumes it without
re-evaluating materiality or touching generic apply routing. Step 4 must depend
on the previous steps.

## Non-goals

- No use of `Recommendation.step_id` or raw finding prose as a feedback,
  attribution, or cross-run transport.
- No generic walk, action dispatcher, launcher, or convergence-diagnosis change.
- No feedback gate, refusal to advance, automatic carve, automatic apply,
  threshold tuning, exit-code change, or mandatory acknowledgement.
- No check-saturation or self-seeded emitter, historical causal attribution,
  Git-range analysis, citations, revisions, or checkpoints beyond the dedicated
  advisory's source plan fingerprint.
- No arbitrary new feedback detector for measurement-instrument adequacy or
  remedy proportionality.

## Risks and fail-closed rules

- LLM tag omissions and conflicting samples are expected; they suppress the
  advisory rather than allowing a tagged subset to look complete.
- A stale sidecar can still guide a human through its saved conceptual findings,
  but its dedicated advisory must be hidden when the source plan fingerprint is
  stale.
- The advisory's persisted evidence is intentionally small and frozen. It does
  not assert that an earlier audit caused an edit, prove historical causality,
  or supply executable routing data.
- If the renderer needs information absent from the dedicated payload, add the
  minimum typed evidence to that payload rather than reaching into
  `Recommendation`, report history, Git, or free-form text.

## Test requirements

- Pin all registry records and only-one-emitter eligibility.
- Exercise literal audit-reference parsing; invalid, prose-only, repeated,
  unknown, multi-step, done-step, conflicting, and missing references fail
  closed while ordinary recommendations retain `step_id=None`.
- Exercise full material denominator, sample consensus, strict-majority arm
  selection, ties, gaps, whole-plan arms, and insufficient support.
- Round-trip `audit_shape_advisory`; legacy review JSON loads without one;
  fresh/reused/saved-apply paths render only the stored, source-fingerprint
  fresh payload.
- Prove serial and parallel completeness apply show the payload before their
  normal work but never change a recommendation or generic apply target.
- Pin compatibility-null coverage fields, additive JSON output, no legacy
  count-route operator guidance, and unchanged block/exit behavior.
- Validate detects CLAUDE registry drift without a model call or changed exit.

## Acceptance criteria

- The user receives a clear, evidence-bearing keep-or-carve prompt before
  manual conceptual apply only when the fresh or source-fingerprint-matching
  dedicated advisory exists.
- No audit feedback mechanism can route, retarget, clear, or otherwise alter
  a `Recommendation` or generic saved-review walk.
- A reused audit presents exactly the material evidence captured at its source
  audit or no advisory; it never recalibrates from later history.
- Only arm clustering is checked; all other shapes remain judgment-only and
  non-emitting.
- Count-only taper/convergence advice is retired without breaking coverage JSON
  consumers, and the documented registry remains validator-checked.
