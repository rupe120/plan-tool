> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 3 — Make retained guidance useful to maintainers

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Explain current decisions and procedures directly so a maintainer can continue
the project from the repository. Keep meaningful evidence and measurement limits;
remove session narration, redundant citations and availability commentary that
provides no next action. Preserve the governing judgment rules and content hashes.

## Table of Contents

- [Summary](#summary)
- [Why](#why)
- [Input](#input)
- [Files (creates vs edits)](#files-creates-vs-edits)
- [Implementation](#implementation)
- [Tests](#tests)
- [Acceptance criteria](#acceptance-criteria)
- [References](#references)
- [Applicable guardrails](#applicable-guardrails)
- [Deferred](#deferred)

## Why

Maintainers need the decision, its reason, the evidence limits and the next
procedure. A list of commits or session checkpoints does not supply those facts.
The withdrawal evidence and review-ledger rules must preserve enough explanation
to support their current decisions without asking a reader to reconstruct a session.

## Input

- Step 2's selected content and repaired references in the selection record.
- Current decisions and next actions in the release pickup.
- The measured-incidents evidence, current code and existing tests supporting
  settled rules. Treat sample numbers as dated measurements, not universal claims.
- The shared directives as the canonical owner of the provenance judgment.

## Files (creates vs edits)

**New files:**

- None. Step 1 owns creation of `docs/evidence/public-release-content-snapshot.md`.

**Existing files (edits only):**

- `CLAUDE.md` — Explain current decisions and procedures directly, preserving rule intent and architect-tier review.
- `integrations/shared/DIRECTIVES.md` — Apply the same bounded snapshot-compatible provenance route in the canonical driving authority; preserve its existing judgment rule and architect-tier review.
- `docs/evidence/claude-md-measured-incidents.md` — Keep the measurement, its limits and the decision it supports.
- `handoffs/README.md` — Clarify retention guidance and self-contained finding explanations and useful next actions.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — Update citation-treatment pickup and link to the durable disposition record.
- `docs/evidence/public-release-content-snapshot.md` — Record reviewed coverage, citation classifications, replacement instructions and unresolved dependencies.

## Implementation

- Enumerate relevant explanations, citations and procedures before editing. Search
  both identifiers and the words describing each concept; record the owner and
  purpose of each site.
- Lead with the current rule or next action. Keep dated evidence when it supports
  a settled decision, explains a failure to avoid or bounds a measurement. Remove
  commentary whose only purpose is describing former repository access.
- Preserve the test-ordering withdrawal's method, sample limits and conclusion.
  Link its maintained evidence from the governing rule rather than restating a
  sequence of commits.
- Use the same provenance judgment in both governing documents: compare reports
  or summaries, decisions, current code and tests; use relevant revisions when
  available. State uncertainty before proposing structural rework when causation
  is not established.
- Preserve review findings, evidence, dispositions and distinct closure labels.
  A compressed record must still explain each decision. Make the pickup state one
  current route and separate completed work from outstanding responsibilities.
- Keep content digests and artifact identifiers unchanged. Preserve working links
  and anchors; update every affected reference within the declared footprint.
  Record required repairs outside it rather than silently expanding scope.

## Tests

This is a non-code step; use document review and existing checks.

1. Read each changed explanation as a maintainer joining the project: identify the
   current rule, its reason, its limits and the next action.
2. Compare the withdrawal measurements and content identities with their owners;
   ensure prose edits do not change their meaning or values.
3. Walk both provenance procedures against current reports, code and tests;
   insufficient evidence must produce explicit uncertainty.
4. Verify finding dispositions and closure labels survive compression unchanged.
5. Resolve changed local links and anchors; repeat identifier and vocabulary
   searches for stale instructions and redundant availability commentary.
6. Run the existing data/response contract checks and complete regression suite;
   add no citation-validation runtime mechanism.

## Acceptance criteria

- Descriptions explain current behavior, settled decisions and useful next actions.
- Dated evidence keeps its method, limits and supported conclusion.
- Both governing documents preserve the same judgment and uncertainty rules.
- Review records retain findings, evidence, dispositions and closure labels.
- Content identities remain unchanged, and changed references resolve.
- Scope and required architect-tier review remain explicit.

## References

- [Plan](../../2-public-release-content-snapshot.md) — Scope and dependencies.
- [Selection record](../../../../evidence/public-release-content-snapshot.md) — Content decisions.
- [Pickup](../../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Current decisions and next actions.
- [Documentation style](../../../../reference/documentation-style.md) — Reader-first structure and fact preservation.

## Applicable guardrails

- Preserve the governing rules and architect-tier review requirement.
- Keep runtime contracts, report identities and qualification behavior unchanged.
- Limit edits to the declared files and report additional required work explicitly.
- Treat publication and remote changes as separate authorized actions.

## Deferred

- Step 5 owns independent candidate verification.
- Step 2 owns selection changes and dependent reference repairs.
- Repairs outside the declared files require a separate bounded disposition.
