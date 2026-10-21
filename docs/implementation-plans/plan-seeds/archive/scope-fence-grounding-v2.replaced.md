> **Replaced**: this file has been superseded by `docs/implementation-plans/2-scope-fence-grounding-v2.md`.
> Preserved here for history; do not edit.

# Author-approved scope-fence grounding (BACKLOG #161 + #162)

This re-seeds `scope-fence-grounding` after its preservation-only contract
proved too restrictive. A seed is a starting point: plan-tool should help an
author develop a stronger plan, including a missing scope fence, but it must
never silently turn a model suggestion into an author constraint.

## Outcome

`create` preserves supplied `Scope guardrails`, `Audit guardrails`, and
`Expected placement` headings, may propose missing guardrail content, and
writes proposed content only after the author explicitly accepts it. The
conceptual audit receives the resulting originating scope contract whenever it
is resolvable, including author-approved guardrails.

## Decisions this seed settles

1. The three guardrail names remain optional canonical sections in
   `OPTIONAL_PLAN_BODY_SECTION_SHAPES`; do not open a general unknown-H2
   passthrough.
2. Supplied guardrails are preserved under their own headings. The
   deterministic exact-heading checks remain zero-model-call checks and cover
   both distill and synthesis boundaries.
3. When a seed lacks one or more guardrail sections, the model may propose
   content for those missing sections. Each proposed section must be shown to
   the author with an explicit accept/reject decision before it reaches the
   plan. Rejection omits it entirely. Non-interactive operation must use a
   safe default of omission unless an existing explicit approval input can be
   supplied; it must not silently accept.
4. Existing author-supplied guardrail text is not rewritten or weakened by the
   proposal path. A proposal may complement a missing heading only.
5. The three guardrail headings are excluded from defer-bucket derivation in
   both create and detail. A standing fence cannot be deferred.
6. `Plan.source_seed` records the durable, repo-relative originating seed
   actually used as body/guardrail input; follow only an existing explicit
   canonical provenance pointer, never slug inference. Archive failure keeps
   a verified readable original or omits the field.
7. `completeness-audit --seed <path>` is the explicit override for plans
   without provenance. It overrides stored provenance and forces a fresh
   audit rather than reusing findings from a different prompt.
8. The audit prompt receives the resolved source contract as originating
   intent. With no resolvable contract it emits no block and remains
   byte-identical. Oversized contracts have a visible marker while retaining
   bounded excerpts of every present scope/guardrail heading.
9. The audit must honor `Audit guardrails` as well as Outcome, In scope, Out
   of scope / Non-goals, Allowed behavior changes, and Allowed reorganization.
10. Spend no additional audit invocations. This changes plan authoring and
    grounding, not the number of audit calls.

## In scope

- `plan_tool/create.py`, `plan_tool/detail.py`, `plan_tool/schema.py`,
  `plan_tool/review.py`, `plan_tool/cli/authoring.py`, and
  `plan_tool/cli/completeness_cmd.py`.
- `plan_tool/prompts/synthesize-body.md`, `plan_tool/prompts/distill-seed.md`,
  and `plan_tool/prompts/plan-audit.md`.
- `PLAN_FORMAT.md`, `DATA_CONTRACT.md`, `docs/AUDIT_FLOW.md`, and generated
  `docs/cli/completeness-audit.md`.
- Relevant tests under `tests/`.

## Out of scope / non-goals

- General arbitrary-H2 acceptance or a new canonical section category.
- A model call in deterministic preservation checks, model-based fold
  detection (BACKLOG #163), or automatic acceptance of a guardrail proposal.
- Seed-vs-plan drift detection, mechanical enforcement of audit findings,
  convergence-predicate changes, and concept-record/schema changes.
- Changing the number of conceptual audit calls or expanding the audit into
  implementation readiness.

## Verification

- A seed with all three supplied guardrails preserves them exactly and offers
  no rewrite proposal for them.
- A seed with none can receive proposed guardrails, but accepted proposals are
  written only after explicit author approval and rejected proposals are
  omitted.
- Headings lost at distill or synthesis boundaries produce deterministic,
  bounded findings; ordinary seeds do not gain sections without approval.
- Neither bucket producer offers any guardrail section as deferrable.
- Durable provenance, `--seed` override/fresh-audit behavior, prompt fallback,
  safe truncation, and Audit-guardrail grounding are covered by tests.

## Stop / defer

- If an approval interaction cannot be added without a broader create UX
  redesign, preserve supplied guardrails and file author-approved proposals as
  a follow-up; do not silently accept them.
- Keep BACKLOG #163 deferred. If the new proposal path exposes a separate
  review/remove need, file it rather than extending concept storage.
- Update BACKLOG #161 and #162 only after full shipment; plan authoring alone
  must not remove them.
