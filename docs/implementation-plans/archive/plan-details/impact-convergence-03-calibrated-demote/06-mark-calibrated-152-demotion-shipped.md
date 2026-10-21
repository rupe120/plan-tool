> **Auto-archived**: this plan was swept on 2026-08-03 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Mark the calibrated #152 demotion as shipped

## Summary

Update `BACKLOG.md`, `CLAUDE.md`, and `docs/AUDIT_FLOW.md` to record the calibrated low-impact demotion as shipped after steps 4 and 5 land. Verify the implemented shared predicate and its two adopted continuation paths before changing the documentation. Remove the completed #152 backlog entry and rewrite surviving references to describe the shipped policy by feature rather than a deleted issue number. On green, the project documentation accurately states both the demotion boundary and the work that remains outside it.

## Table of Contents

- [Summary](#summary) — The documentation outcome of this completion step.
- [Table of Contents](#table-of-contents) — Links to each section.
- [Why](#why) — Why the backlog and convergence guidance must match shipped behavior.
- [Input](#input) — The upstream implementation contracts this step verifies.
- [Files (creates vs edits)](#files-creates-vs-edits) — The three documentation files updated in place.
- [Implementation](#implementation) — The shipped-policy wording and backlog cleanup approach.
- [Tests](#tests) — Documentation verification for this non-code step.
- [Acceptance criteria](#acceptance-criteria) — Observable documentation and implementation alignment.
- [Deferred](#deferred) — Related convergence work that remains separate.

## Why

`BACKLOG.md`, `CLAUDE.md`, and `docs/AUDIT_FLOW.md` still describe calibrated demotion as pending even though steps 4 and 5 make it active in the two reachable continuation paths. Leaving that wording behind makes implementers treat shipped behavior as future work and obscures the deliberately narrow safety boundary.

## Input

- **Step 4 outcome:** Verify that `plan_tool/cli/reconcile.py:_iterate_reconcile_loop` builds one operation-scoped calibration lookup and supplies its rule at every blocking-findings refresh.
- **Step 5 outcome:** Verify that `plan_tool/review.py:audit_plan_until_stable` builds one lookup per audit invocation and applies its rule at `material_new`.
- **Shared policy contract:** Confirm `plan_tool/convergence.py:is_blocking_impact` still keeps high-impact recommendations and `high`/`critical` severities blocking while allowing only the supplied calibrated demotion decision to suppress an eligible baseline block.
- **Calibration contract:** Confirm the public lookup in `plan_tool/telemetry_analysis.py` limits demotion to the implemented low-impact, medium-severity evidence rule. Do not claim a broader impact-only policy.

## Files (creates vs edits)

- **New files:** None.

- **Existing files (edits only):**
  - `BACKLOG.md` — Remove the fully shipped #152 entry and update surviving impact-convergence references that treated it as pending.
  - `CLAUDE.md` — Update `# Convergence policy boundary` to describe the shipped calibrated demotion and its limits.
  - `docs/AUDIT_FLOW.md` — Update `Impact-aware convergence augment (BACKLOG #152)` and the `Impact-aware continuation` architecture-map row to describe the full shipped rule.

## Implementation

- **Foundational logic: calibrated low-impact demotion.** Treat this as a documentation-only completion step. Before editing prose, inspect the implementation delivered by steps 3 and 4 at `plan_tool/convergence.py:is_blocking_impact`, `plan_tool/cli/reconcile.py:_iterate_reconcile_loop`, and `plan_tool/review.py:audit_plan_until_stable`; documentation must follow the code that landed, not the earlier plan wording.

- **Describe the narrow rule accurately.** State that historical calibration can demote only the implemented low-impact, medium-severity recommendation classes with sufficient evidence. Keep the safety rule explicit: high-impact recommendations and `high`/`critical` severities remain blocking.

- **Keep the adoption boundary explicit.** Document that reconcile uses the rule for every open-blocking-findings refresh and audit uses it for `material_new`; completeness callers that invoke this audit loop therefore inherit that deliberately narrow materiality change. Keep deterministic and reporting gates, prompts, schemas, `Recommendation`, and `plan_tool/convergence_diagnosis.py` outside this policy.

- **Retire completed backlog tracking.** Remove #152 from `BACKLOG.md` once the implementation check confirms that both its augment and calibrated demotion are shipped. Update the `gate-signal` lens, the #125 follow-up reference, and #158’s `Arc` and dependency wording so open work names the shipped calibrated demotion by feature instead of treating #152 or #154 as pending prerequisites.

- **Keep triage separate from convergence.** Preserve the distinction already documented in `CLAUDE.md:# Convergence policy boundary` and `docs/AUDIT_FLOW.md:Impact-aware convergence augment (BACKLOG #152)`: `partition_findings_for_triage` controls apply or defer decisions, while calibrated materiality controls whether a continuation loop remains productive.

- **Do not broaden the policy in prose.** Do not describe all low-impact findings as advisory, imply that calibration changes recommendation parsing or persistence, or present the separate impact-recurrence work as part of this shipment.

## Tests

No automated test file changes are required for this non-code step.

### Verification (non-code step)

- `documentation_matches_shipped_calibrated_demotion` — Verify the implementation anchors in the Input section support every documented eligibility and safety claim.
- `no_pending_152_or_154_demotion_wording` — Search `BACKLOG.md`, `CLAUDE.md`, and `docs/AUDIT_FLOW.md` for stale wording that calls the calibrated demotion pending or deferred.
- `surviving_impact_convergence_references_are_valid` — Check that open #158 and #125 references describe the shipped feature without depending on a removed backlog number.
- `audit_flow_architecture_map_matches_policy` — Verify the `Impact-aware continuation` row names the shared predicate plus reconcile and audit consumers, including the inherited audit-loop behavior of completeness callers.

## Acceptance criteria

- `BACKLOG.md` contains no open #152 entry after the shipped implementation is verified.
- `BACKLOG.md` retains #158 as separate open work and describes its prerequisite in terms of the shipped calibrated demotion.
- `CLAUDE.md:# Convergence policy boundary` states the calibrated low-impact, medium-severity demotion boundary and preserves the high-impact and high-severity safety rules.
- `docs/AUDIT_FLOW.md:Impact-aware convergence augment (BACKLOG #152)` states that reconcile refreshes and audit materiality use the calibrated rule.
- The three edited documents do not describe impact-only demotion as pending, deferred, or blocked on #154.
- The documentation confines calibrated demotion to reconcile and audit materiality (including completeness callers that use that audit loop), and does not claim it affects deterministic/reporting gates, prompts, schemas, recommendation shape, or convergence diagnosis.

## Deferred

- Impact-recurrence structural stopping — #158 remains separate because it classifies repeated high-impact seams rather than deciding whether a single calibrated low-impact finding is material.
