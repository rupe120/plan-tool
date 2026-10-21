> **Auto-archived**: this plan was swept on 2026-08-18 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 5 — Document the bare-plan policy and retire BACKLOG #290

## Summary

Document the shipped bare-plan property-versus-mechanism policy in `CLAUDE.md`, `integrations/shared/DIRECTIVES.md`, and `docs/AUDIT_FLOW.md`. Retire the completed `BACKLOG.md` #290 entry into `docs/HISTORICAL_BACKLOG_DECISIONS.md` while preserving the replay provenance and links to live follow-up work. Keep the policy concise: named properties and uncovered routes remain actionable, while unselected delivery mechanisms belong to detail unless the plan makes one an observable contract. On green, the operating docs agree with the landed behavior and #290 no longer appears in the forward-looking backlog.

## Table of Contents

- [Summary](#summary) — The documentation and backlog-retirement outcome.
- [Table of Contents](#table-of-contents) — Links to the detail sections.
- [Why](#why) — Why the shipped policy needs one clear operational record.
- [Input](#input) — The landed behavior and evidence this documentation reads.
- [Files (creates vs edits)](#files-creates-vs-edits) — The documentation and historical-record changes.
- [Implementation](#implementation) — The policy, ownership, and retirement approach.
- [Tests](#tests) — Non-code verification for policy consistency and retirement.
- [Acceptance criteria](#acceptance-criteria) — Observable completion checks.
- [Applicable guardrails](#applicable-guardrails) — Boundaries this documentation must preserve.
- [Deferred](#deferred) — Related work that remains separately owned.

## Why

The bare audit’s behavior changes across steps 1, 3, and 4, but the current guidance does not give operators one consistent explanation of what remains a plan-level defect, what moves to detail, or why the advisory does not affect enforcement. Leaving #290 in `BACKLOG.md` after delivery also keeps finished work in the active queue and risks preserving stale implementation notes as current policy.

## Input

- **Step 1 policy:** Read the landed bare-stage guidance in `plan_tool/prompts/plan-audit.md` and its rendering path in `plan_tool/review.py:render_plan_audit_prompt`. Record the shipped property-versus-mechanism boundary, including the exception for a mechanism the plan explicitly makes an observable contract.

- **Steps 3 and 4 presentation:** Read the landed convergence and stderr behavior through `plan_tool/convergence_diagnosis.py:render_diagnosis` and `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines`. Use the actual landed symbols in `docs/AUDIT_FLOW.md` rather than names proposed by an earlier detail.

- **Upstream evidence:** Use `tests/test_review.py`, `tests/test_convergence_diagnosis.py`, `tests/cli/test_convergence_cmd.py`, and `tests/cli/test_completeness_cmd.py` to confirm the documented stage, same-finding composition, and run-grade boundaries. These tests establish the behavior to describe; this step does not extend them.

- **Historical format:** Follow `docs/HISTORICAL_BACKLOG_DECISIONS.md:## Retired composite records` for the dated, short record that keeps a closed composite item citable.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `CLAUDE.md` — Update `## Plan audit gate` with a short developer-facing statement of the bare-stage property-versus-mechanism rule and the advisory-only boundary.
  - `integrations/shared/DIRECTIVES.md` — Update `## Gate 1 — the bare-plan audit (before \`detail\`)` with the operator-facing decision rule for route coverage, detail-owned mechanisms, and the selected-contract exception.
  - `docs/AUDIT_FLOW.md` — Update the bare-audit workflow sections and `## Source map` to explain the policy and point to the landed prompt, convergence, and completeness-stderr seams.
  - `BACKLOG.md` — Remove the completed #290 entry without replacing it with a closed-status backlog item.
  - `docs/HISTORICAL_BACKLOG_DECISIONS.md` — Add a dated #290 retired-composite record that states the shipped policy, preserves useful replay provenance, and links only to still-live follow-up entries.

## Implementation

- **Foundational rule: bare audits test named properties, not unselected implementation choices.** Document that a missing route for a named safety, ordering, ownership, compatibility, bypass, or acceptance property remains a plan-correctness issue. Document that an internal delivery choice remains detail work unless the plan explicitly makes that mechanism the observable contract required by a named property.

- **Keep the policy consistent across its three audiences.** Use `CLAUDE.md:## Plan audit gate` for concise development guidance, `integrations/shared/DIRECTIVES.md:## Gate 1 — the bare-plan audit (before \`detail\`)` for the operator’s next-action rule, and `docs/AUDIT_FLOW.md` for the lifecycle and source-of-truth map. Each location should link or point deeper where appropriate rather than copy a long list of mechanism examples.

- **Describe the advisory as observation, never enforcement.** State that the deterministic recommendation-text signal and its same-finding `edit_drift` composition help an operator reconsider a likely detail-owned request. Preserve that it appears through `plan_tool/convergence_diagnosis.py:render_diagnosis` and the run-grade stderr path rooted at `plan_tool/cli/completeness_cmd.py:_convergence_loop_advisory_lines`, without changing a finding’s gate, continuation, failure, or exit behavior.

- **Preserve stage and grade boundaries.** The documentation must distinguish the bare-plan policy from the detail-grounded audit and retain Jira-grade advisory suppression. Do not describe a mechanism advisory as an automatic deferral, a causal finding, or a replacement for operator judgment.

- **Make `docs/AUDIT_FLOW.md` source citations code-backed.** Update its `## Source map` only after reading the landed interfaces from steps 1, 3, and 4. Name the actual prompt, classifier, convergence-rendering, and completeness-stderr anchors; do not preserve a speculative helper name from this plan.

- **Retire #290 as a historical composite record.** Remove the full #290 block from `BACKLOG.md`. Add one concise, dated entry under `docs/HISTORICAL_BACKLOG_DECISIONS.md:## Retired composite records` that records the policy outcome, the advisory’s non-enforcing role, and the 2026-08-17 cross-route replay as provenance without relying on a non-live backlog identifier.

- **Keep active work discoverable without reviving #290.** Verify the current
  entries before linking #231, #241, and #262 from the historical record.
  Describe them as separate work; do not turn their open scope into remaining
  work for #290.

- **Sweep both the identifier and vocabulary.** Search `BACKLOG.md` for `#290`, and search the touched documents for stale language that frames the policy as planned, unshipped, gate-changing, or causal provenance. Historical prose belongs only in `docs/HISTORICAL_BACKLOG_DECISIONS.md` and must be dated.

## Tests

This step has `change_type: non-code`, so the plan’s test-authoring gate does not require a test file. Do not add or edit Python tests for this documentation-only change.

### Verification (non-code step)

1. **Policy alignment** — Compare `CLAUDE.md`, `integrations/shared/DIRECTIVES.md`, and `docs/AUDIT_FLOW.md`; all three state that named-property coverage stays actionable and an unselected mechanism belongs to detail.

2. **Selected-contract exception** — Confirm each applicable policy explanation preserves the narrow case where a mechanism remains actionable because the plan explicitly makes it the observable contract for a named property.

3. **Advisory-only boundary** — Confirm the docs describe the mechanism and same-finding `edit_drift` guidance as recommend-only, outside enforcement and outcome decisions.

4. **Source-map accuracy** — Confirm every `docs/AUDIT_FLOW.md:## Source map` citation added for this policy names a symbol that exists in the landed `plan_tool/` implementation.

5. **Backlog retirement** — Confirm `rg '#290' BACKLOG.md` returns no result and `docs/HISTORICAL_BACKLOG_DECISIONS.md` contains one dated #290 record.

6. **Live follow-up links** — Confirm every follow-up ID retained in the #290 historical record still identifies a current entry in `BACKLOG.md`.

## Acceptance criteria

- `CLAUDE.md:## Plan audit gate`, `integrations/shared/DIRECTIVES.md:## Gate 1 — the bare-plan audit (before \`detail\`)`, and `docs/AUDIT_FLOW.md` describe the same bare-stage policy without conflicting terms.

- The documentation states that uncovered named-property route coverage remains actionable and that pure unselected delivery mechanisms are detail-owned.

- The documentation preserves the explicit observable-contract exception and does not turn a mere implementation preference into a bare-stage obligation.

- `docs/AUDIT_FLOW.md:## Source map` points to the landed prompt, convergence, and completeness-stderr implementation seams using current symbolic anchors.

- The advisory is documented as run-grade guidance that does not change blocking, continuation, failure, or exit behavior, and Jira-grade suppression remains documented.

- `BACKLOG.md` has no #290 entry or stale #290 references.

- `docs/HISTORICAL_BACKLOG_DECISIONS.md` contains a dated #290 retired-composite record with the shipped decision, replay provenance, and verified live follow-up links.

## Applicable guardrails

- **The plan’s Plan intent, policy boundary** — Document the distinction between plan-level properties and detail-owned mechanisms without changing or broadening the enforcement contract.

- **The plan’s `## Out of scope`, enforcement and stage boundaries** — Keep this step to documentation of the landed behavior; do not describe a new gate, outcome change, or wider detail-grounded policy.

- **The plan’s `## Out of scope`, grade and provenance boundaries** — Preserve Jira-grade suppression and describe `edit_drift` as comparison evidence, not causal provenance.

- **The plan’s `## Out of scope`, separately owned work** — Retain only useful links to the plan’s listed follow-ups; do not absorb their work into #290’s historical record.

## Deferred

- **#231 durable apply-to-finding provenance** — Remains the owner of causal evidence beyond the advisory’s same-finding comparison.

- **#241 bare-prompt completeness-generation policy** — Remains a separate prompt-policy decision.

- **#262 post-churn detail-readiness guidance** — Remains a reactive operator advisory with a different trigger.

- **Run-time attribution** — Is separate from this audit-policy documentation
  step and already has the current phase distinction it needs.
