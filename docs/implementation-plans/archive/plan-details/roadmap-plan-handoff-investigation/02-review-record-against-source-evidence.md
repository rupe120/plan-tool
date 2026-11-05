> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 2 — Review the record against source evidence and reconcile #492 while preserving its staged arc

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Review `docs/explanations/roadmap-plan-handoff.md` against the checked-in Integration evidence and the plan’s authority rules, then make its conclusions explicit enough to close the investigation. Update `BACKLOG.md` #492 only after the record demonstrates each required consumer and follow-on disposition. Keep #492’s staged arc as the routing authority, including the existing gates and ownership boundaries for #493, #462, and #494. On green, the record and backlog agree on what was decided, what remains gated, and what no tool behavior changes this investigation authorizes.

## Table of Contents

- [Summary](#summary) — States the review result and backlog reconciliation.
- [Table of Contents](#table-of-contents) — Routes readers through this detail.
- [Why](#why) — Explains why the design record needs an evidence review before closure.
- [Input](#input) — Names the step-1 record and authoritative evidence to compare.
- [Files (creates vs edits)](#files-creates-vs-edits) — Defines the documentation-only changes.
- [Implementation](#implementation) — Describes the evidence review and staged-arc-preserving reconciliation.
- [Tests](#tests) — Lists automated checks and non-code verification.
- [Acceptance criteria](#acceptance-criteria) — Gives observable completion conditions.
- [References](#references) — Links the authority and evidence sources.
- [Applicable guardrails](#applicable-guardrails) — Keeps the review inside the investigation boundary.
- [Deferred](#deferred) — Routes later feature work to its existing owners.

## Why

Step 1 creates the decision record, but #492 cannot close on a plausible narrative alone: its consumer decisions must match the bounded Integration evidence, accepted-roadmap authority rules, and the existing backlog ownership map. Without this review, the record could treat observed code or a proposal as approved intent, or make #493, #462, and #494 appear authorized before their separate evidence gates are met.

## Input

- **Step 1 record:** Treat `docs/explanations/roadmap-plan-handoff.md` as the artifact under review. Step 1 owns its journey trace, authority boundaries, consumer-input comparison, unresolved provider question, and initial follow-on dispositions.
- **Accepted-roadmap authority:** Confirm the record describes accepted roadmap content through `plan_tool/roadmap_versions.py:load_accepted_version` and the immutable accepted-head contract in `ROADMAP_FORMAT.md`. Candidate material, local source observations, and Integration proposals must remain distinct evidence classes.
- **Bounded Integration evidence:** Compare claims with `docs/evidence/integration-roadmap-to-plan-handoff.md`, especially its “Source identity” and “Proposed response and scope limits” sections. Preserve its stated limits: it supports investigation, not a claim that a tool change improves planning quality or execution readiness.
- **Backlog ownership:** Use `BACKLOG.md` #492’s “Stage arc (single authority for this group)” as the source for the #493, #462, and #494 sequence. Read #490, #485, #262, and #403 only to preserve their ownership boundaries.

## Files (creates vs edits)

- **New files:**
  - None.

- **Existing files (edits only):**
  - `docs/explanations/roadmap-plan-handoff.md` — revise the step-1 record where the evidence review finds an unsupported claim, missing authority boundary, unclear disposition, or unrecorded limitation.
  - `BACKLOG.md` — reconcile #492’s shipment state and record link only when the reviewed record meets its stated outcome; retain its staged arc and the current ownership and gate language for follow-on work.

## Implementation

- **Foundational logic:** Close #492 only through evidence-backed disposition review, not by treating the existence of a design record as proof that later features are ready.

- **Review each claim by evidence class.** Compare `docs/explanations/roadmap-plan-handoff.md` with `docs/evidence/integration-roadmap-to-plan-handoff.md: Source identity` and `Proposed response and scope limits`. Keep approved roadmap obligations, observed implementation, provider evidence, fixtures, proposals, and unresolved owner questions visibly separate.

- **Keep accepted-roadmap authority narrow.** Confirm the record names `ROADMAP_FORMAT.md` and `plan_tool/roadmap_versions.py:load_accepted_version` as the route for accepted content. Do not let a Integration proposal, a local checkout observation, or a source revision stand in for an accepted roadmap decision.

- **Recheck the three consumer decisions.** For `create`, `detail`, and `completeness-audit`, ensure the record states the needed information, the existing delivery route, demonstrated missing delivery if any, and one explicit `build`, `use-existing`, or `no-action` decision. Existing inputs named by step 1, including `plan_tool/create.py:_project_context_block`, `plan_tool/detail.py:render_detail_prompt`, and `plan_tool/review.py:render_plan_audit_prompt`, are evidence to inspect, not presumed gaps.

- **Keep follow-on decisions separate from consumer decisions.** The record must separately disposition #493, #462, and #494. Preserve #462’s independent evidence gate and advisory scope; an unmet gate can support a conditional recommendation but cannot be presented as closure, promotion, or a block on #492. Preserve #494’s requirement for a distinct status-information need.

- **Preserve ownership boundaries.** State that #490 remains the owner of finding dispositions, #485 remains the owner of deliberate-roadmap-departure authority, #262 remains a detail-readiness advisory, and #403 remains installation/readiness inspection. Do not recast any of them as shared-context work.

- **Record unresolved evidence honestly.** Verify the required unresolved provider capability or behavior question is present, remains unanswered at the inspected revision, and is distinct from owner product decisions. It may remain open only when it does not prevent the required consumer and follow-on decisions. If required evidence is unavailable or insufficient, revise the record to say which conclusion remains unresolved and leave #492 open rather than substituting a final disposition.

- **Reconcile #492 without collapsing the route.** Once the record meets #492’s outcome and acceptance conditions, update only #492’s status and shipment reference in `BACKLOG.md`. Retain its “Stage arc (single authority for this group)” and its gate language so #493 and #494 remain gated follow-ons and #462 remains independently evidence-gated. Do not remove, renumber, broaden, or implement neighboring entries.

## Tests

- `tests/test_backlog_ids.py:test_backlog_entry_ids_are_unique` — confirms the retained #492 entry does not create a duplicate backlog identifier.
- `tests/test_backlog_readability.py:test_backlog_is_fully_readable_by_the_id_guard` — confirms the edited #492 heading remains readable by the backlog-id guard.

### Verification (non-code step)

1. Read `docs/explanations/roadmap-plan-handoff.md` against every evidence category in `docs/evidence/integration-roadmap-to-plan-handoff.md`; each material claim identifies its authority or limitation.
2. Confirm the record has separate decisions for all three prompt consumers and all three follow-on backlog efforts.
3. Confirm every `build` decision names a demonstrated delivery gap, and every `use-existing` or `no-action` decision names the evidence that supports it.
4. Confirm accepted-roadmap claims cite the accepted-head route, not Integration proposals, source observations, or candidate content.
5. Confirm `BACKLOG.md` retains #492’s stage arc, leaves #493 and #494 gated, and leaves #462’s separate evidence gate intact.
6. Run `uv run pytest tests/test_backlog_ids.py tests/test_backlog_readability.py -q`.

## Acceptance criteria

- `docs/explanations/roadmap-plan-handoff.md` identifies the source revision and authority class for each material evidence claim it uses.
- The record includes an unresolved provider question, separately from any owner decisions; an owner question alone does not satisfy it.
- The record distinguishes accepted-roadmap authority from observed source behavior, proposals, fixtures, and unresolved owner questions.
- The record contains explicit `build`, `use-existing`, or `no-action` dispositions for `create`, `detail`, and `completeness-audit`.
- The record separately dispositions #493, #462, and #494, with #462’s gate status recorded without changing its eligibility.
- Any missing required evidence leaves the affected conclusion unresolved and leaves #492 open.
- After closure, `BACKLOG.md` #492 points to the reviewed record and retains its staged-arc text and follow-on ownership boundaries.
- `tests/test_backlog_ids.py:test_backlog_entry_ids_are_unique` and `tests/test_backlog_readability.py:test_backlog_is_fully_readable_by_the_id_guard` pass.

## References

- [BACKLOG.md #492](../../../../../BACKLOG.md) — Read the outcome, verification, and single staged arc that this step reconciles.
- [Integration evidence for the roadmap to plan handoff](../../../../evidence/integration-roadmap-to-plan-handoff.md) — Review the source identity, observations, and stated evidence limits.
- [Roadmap Plan Handoff Investigation](../../2-roadmap-plan-handoff-investigation.md) — Follow the plan’s decision targets, acceptance criteria, and scope boundary.
- [Roadmap format](../../../../../ROADMAP_FORMAT.md) — Use the accepted-head authority contract when reviewing roadmap claims.
- [Roadmap backlog arc](../../../backlog-arcs/backlog-arc-roadmap.md) — Preserve the router’s #492 anchor and follow-on ordering.
- [Documentation style](../../../../reference/documentation-style.md) — Keep the reviewed design record easy to scan and route by reader task.

## Applicable guardrails

- **The plan’s “## Scope guardrails”:** Limit this step to the design record and `BACKLOG.md`; do not add tool behavior, a new validation surface, or source-side activity.
- **The plan’s “## Out of scope”:** Do not implement #493, #462, #494, #490, #485, or #484 while reviewing their boundaries.
- **The plan’s “## Acceptance criteria”:** Keep #492 open when required evidence is missing; do not turn an unsupported conclusion into a no-action result.
- **The plan intent:** Preserve the record as the observable result. Do not claim it certifies decomposition quality, execution readiness, or plan quality.

## Deferred

- **#493 shared-context delivery** — Remains a later bounded feature only if the reviewed record demonstrates missing consumer delivery.
- **#462 cross-plan advisory report** — Retains its own evidence gate and advisory scope; this step records applicability without implementing or promoting it.
- **#494 prerequisite status view** — Remains conditional on a distinct operator need and approved input contract.
- **#490 finding dispositions and #485 deliberate departures** — Remain separate ownership decisions; the record may cite their boundaries but must not define their data or behavior.
- **#262 detail-readiness advisory and #403 doctor contract** — Remain unrelated operator-facing work and must not become shared-context scope.
