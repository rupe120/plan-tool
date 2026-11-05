> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 6 — Reconcile BACKLOG #513 and publish the local verification pickup record

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Reconcile `BACKLOG.md` #513 with the preparation and verification evidence supplied by step 5. Update the existing pickup handoff and public-release coordination arc to identify completed work, remaining prerequisites and the next bounded action. Keep detailed evidence in `docs/evidence/public-release-content-snapshot.md`, with status and routing documents linking to it. Completion makes the local result clear without implying publication authorization or full release clearance.

## Table of Contents

- [Summary](#summary) — Deliverables and observable result.
- [Table of Contents](#table-of-contents) — Section navigation.
- [Why](#why) — Why preparation needs an accurate pickup record.
- [Input](#input) — Dependency evidence and closure rules.
- [Files (creates vs edits)](#files-creates-vs-edits) — Bounded documentation updates.
- [Implementation](#implementation) — Evidence ownership, status reconciliation and routing.
- [Tests](#tests) — Existing guards and document verification.
- [Acceptance criteria](#acceptance-criteria) — Checkable completion conditions.
- [References](#references) — Scope and tracking sources.
- [Applicable guardrails](#applicable-guardrails) — Authority and evidence boundaries.
- [Deferred](#deferred) — Remaining release and onboarding work.

## Why

The next maintainer needs one current route: what is complete, what still needs
a decision, and which owner takes the next action. Align backlog, pickup and
coordination records with measured results without treating local verification
as shipment or publication authority.

## Input

- **Step 5’s outcome:** Read the selected baseline, content identity, commands, results, exclusions and limitations in `docs/evidence/public-release-content-snapshot.md`. Its absence is an unmet dependency; do not reconstruct successful verification from the plan.
- **Closure contract:** Read `docs/implementation-plans/2-public-release-content-snapshot.md` § “Acceptance criteria” and step 6’s `depends_on_notes`. Unresolved rights or release prerequisites prevent a claim of full #513 shipment.
- **Tracking rules:** Reuse `docs/TRACKING.md` § “The life of an item” and § “Promotion stubs” unchanged. Determine whether #513 remains an unpromoted entry or becomes a promotion stub before editing it.
- **Existing routing:** Read `handoffs/2026-10-19-public-onboarding-and-release.md` § “Next actions” and `docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md` § “Ordered route.” Preserve their separation of content preparation, distribution decisions and consumer verification.

## Files (creates vs edits)

**New files:**

- None. Step 1 creates the durable evidence record.

**Existing files (edits only):**

- `BACKLOG.md` — Reconcile #513’s status and remaining work with evidence; remove its entry or promotion stub only when its closure conditions hold.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — Replace obsolete preparation instructions with the local verification result, remaining prerequisites and next bounded action.
- `docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md` — Update preparation status and pickup links while preserving separate work ownership.
- `docs/evidence/public-release-content-snapshot.md` — Add the final local pickup conclusion, outstanding prerequisites and the evidence supporting #513’s disposition.

## Implementation

- **Foundational logic: status follows recorded evidence.** Use `docs/evidence/public-release-content-snapshot.md` as the detailed evidence owner. Keep `BACKLOG.md` as the work-status owner, the existing handoff as the pickup route and the coordination arc as the ordering guide. Prefer links over copying inventories and command transcripts into every document.

- **Enumerate status claims before editing.** Search the four declared files by identifiers such as `#513`, `#514` and `#515`, then by vocabulary such as “bare,” “pending,” “remaining,” “snapshot,” “rights” and “publication.” Review the handoff’s opening direction, “Current decisions” and “Next actions” together with #513’s status and the arc’s “Ordered route” and “Exit and handoff.” Update each affected claim or retain it with a clear reason.

- **Record the result without upgrading its meaning.** Summarize step 5’s actual verification outcome and link to its evidence. Preserve failures, skips, exclusions, unresolved rights and credential-coverage limits. Distinguish successful technical checks from ownership decisions and release authorization; do not turn missing evidence into a passing result.

- **Reconcile #513 conditionally.** Keep its entry or promotion stub while execution, required review, rights decisions or applicable release prerequisites remain incomplete. Replace stale planning notes with the concrete remaining work and evidence link. Remove the entry or stub only after full shipment under the plan and `docs/TRACKING.md`; local snapshot tests alone must not trigger removal.

- **Make pickup actionable.** In `handoffs/2026-10-19-public-onboarding-and-release.md`, identify the verified selection, completed preparation, unresolved prerequisites, responsible work items and next bounded action. Remove superseded instructions rather than leaving competing routes. Keep decisions needed for correct pickup, and avoid depending on ignored scratch files.

- **Preserve the coordination boundary.** Update `docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md` to point to the actual preparation result. Keep #514’s distribution work and #515’s fresh-consumer evidence separate. Do not close sibling entries merely because this plan supplies one prerequisite.

- **Keep the tested selection identifiable.** These final documentation edits must not silently become part of the selection step 5 claims to verify. Record whether they lie outside that tested selection. If the intended candidate includes changed bytes, identify the verification gap and route them back through step 5 before claiming candidate-wide verification.

- **Reuse shared rules unchanged.** `docs/TRACKING.md` owns backlog closure, and the installed-skill and operator-workflow arcs own their respective lanes. This step updates pointers and status in its declared files; it does not revise those shared rules or expand their work.

## Tests

This step is `change_type: non-code`. The test-authoring gate does not apply because it fires only for `feature` and `refactor`; no new test file is required.

### Verification (non-code step)

1. `backlog_guards_remain_green` — Run `uv run pytest tests/test_backlog_ids.py tests/test_backlog_readability.py -q`; backlog edits preserve existing ID and entry-format checks.
2. `status_claims_match_recorded_evidence` — Trace every completion claim in the four edited documents to step 5’s results or an explicit owner decision.
3. `backlog_closure_requires_full_shipment` — Confirm #513 remains open whenever a required decision, review or prerequisite is unresolved; verify any removal against the plan’s closure conditions.
4. `pickup_has_one_current_next_action` — Repeat identifier and vocabulary searches across the declared files; no obsolete bare-plan or preparation instruction competes with the current route.
5. `verification_scope_does_not_expand_silently` — Compare the final edits with step 5’s selected-content identity; record exclusions or obtain renewed verification for changed selected bytes.
6. `links_and_routing_remain_usable` — Check changed relative links and heading anchors; #514 and #515 retain their separate responsibilities.
7. `local_result_does_not_claim_release_clearance` — Read the final pickup and evidence conclusions together; both preserve unresolved coverage and separate publication authority.

## Acceptance criteria

- The four declared files describe the same preparation outcome and point to `docs/evidence/public-release-content-snapshot.md` for detailed evidence.
- #513’s entry or promotion stub remains while its closure conditions are unmet; any removal has explicit supporting evidence.
- The pickup record names the verified selection, actual results, unresolved prerequisites and next bounded action without requiring ignored artifacts.
- The coordination arc preserves separate ownership of distribution decisions and fresh-consumer verification.
- Final documentation changes do not acquire an unsupported claim of inclusion in step 5’s verified selection.
- Existing backlog guards pass, and changed links and anchors point to available targets.
- No statement equates local verification with rights, secrets or publication clearance.

## References

- [Plan — closure and dependency contract](../../2-public-release-content-snapshot.md) — Read step 6’s dependency notes and acceptance criteria.
- [Backlog — #513 and neighboring release work](../../../../BACKLOG.md) — Read the content-preparation scope and separate prerequisites.
- [Pickup handoff](../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Read settled direction, remaining routing and current pickup instructions.
- [Public-release coordination arc](../../backlog-arcs/backlog-arc-public-release.md) — Preserve ordered responsibilities and exit boundaries.
- [Tracking rules](../../../TRACKING.md#promotion-stubs) — Apply the correct pending and shipped-entry treatment.
- [Documentation style](../../../reference/documentation-style.md) — Keep status, evidence and next actions easy to scan.

## Applicable guardrails

- **The plan’s “Scope guardrails,” publication authority:** Treat “publish” in this step’s title as updating the local pickup record. Documentation changes grant no external-action authority.
- **The plan’s “Scope guardrails,” evidence limits:** Keep conclusions bounded by the recorded checks and owner decisions; status wording must not imply broader clearance.
- **The plan’s “Scope guardrails,” settled choices:** Carry forward the selected distribution boundary without reopening it.
- **The plan’s “Out of scope,” runtime and adjacent work:** Limit changes to the declared documents. Record unmet prerequisites without implementing the excluded capabilities.
- **The plan’s “Scope guardrails,” required review:** Reflect any outstanding architect-tier review in the pickup record; do not substitute documentation completion for that review.

## Deferred

- #514’s remaining distribution and sync work — Its separate scope owns existing remote inspection and release/update guidance.
- Onboarding and fresh-consumer verification — The public-release arc routes these to their existing work items, including #515.
- Publication and remote installation — Require separate owner authorization beyond this local preparation record.
- Unresolved verification or rights work — Keep concrete gaps in the existing evidence and work records; this status step does not manufacture their resolution.
