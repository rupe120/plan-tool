> **Auto-archived**: this plan was swept on 2026-11-05 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

# Step 4 — Apply explicit policy rights decisions to the selected content

<!-- plan-tool:detail-format-version: 1 -->

## Summary

Record and apply the owner's redistribution decision for the policy Markdown and
PDF separately. Keep material with unresolved rights outside the publishable
selection, preserving an explicit unresolved prerequisite rather than inferring
approval from rebuilding or anonymization. Limit source edits to factual tool
references required by preparation and rebuild the PDF only when its retained
source changes. This step changes content and its disposition record, not policy
rules or runtime behavior.

## Table of Contents

- [Why](#why)
- [Files](#files-creates-vs-edits)
- [Implementation](#implementation)
- [Tests](#tests)
- [Acceptance criteria](#acceptance-criteria)

## Why

The policy and PDF must describe the same governance rules and current tool
references. Keep the owner-approved content intact while correcting demonstrated
factual errors. Rebuilding the derivative requires text, metadata and page checks
so readers receive a complete, usable policy.

## Input

- Step 1's selected paths, ownership evidence and pending decisions in
  `docs/evidence/public-release-content-snapshot.md`.
- The settled decisions and PDF rebuild record in the release handoff.
- The tracked policy Markdown as the editable source and the existing PDF as its
  rendered derivative. Do not embed PDF bytes in a backend argv prompt; inspect
  its extracted text and rendered pages with available local tools.
- Current command/parser guidance and `integrations/shared/DIRECTIVES.md` for
  factual references. Preserve the governance rules and review requirements.

## Files (creates vs edits)

**New files:** None.

**Existing files:**

- `AI_SDLC_POLICY.pdf` — Retain its existing rebuilt bytes unless an approved
  factual source correction requires regeneration; apply its recorded snapshot
  exclusion when rights remain unresolved.
- `docs/reference/ai-assisted-development-policy.md` — Apply only necessary factual
  tool-reference corrections, retaining its governance meaning and existing anchors.
- `docs/evidence/public-release-content-snapshot.md` — Record each artifact's
  ownership evidence, rights decision or unresolved state, selected treatment,
  factual corrections and any rebuild verification.

## Implementation

1. Read the existing selection record and identify the explicit owner decision
   covering each artifact. Distinguish permission to regenerate from permission to
   redistribute; do not manufacture either from a successful scan.
2. For rights-approved content, record the decision source and retention treatment.
   For explicitly refused content, record exclusion. For unresolved rights, record
   an exact exclusion and the outstanding decision; the step may record that
   disposition, but cannot certify rights or clear the full-shipment prerequisite.
   Apply this consistently to Markdown and PDF and check their selected references.
3. Review factual tool references against current local authorities. In particular,
   the policy's ongoing `convergence` reference must not misdescribe the advisory
   evaluator or the direction of reconciliation. Correct only demonstrated stale
   references; preserve who decides and approves. A correction that changes policy
   meaning returns to the owner rather than being bundled into preparation.
4. Keep `docs/reference/ai-assisted-development-policy.md` as the source. If retained
   source bytes change, regenerate the retained PDF with recorded external tools;
   do not add a package dependency or a new PDF-generation framework. If no source
   change is needed, preserve the completed rebuild and state that result.
5. For any rebuild, use a policy title in metadata and omit browser headers,
   checkout-local hyperlinks and source paths. Inspect extracted text and every
   rendered page for completeness, legibility and alignment with the source.
   Tool availability or a rendering failure is a recorded coverage gap, not an
   excuse to claim regeneration or to change the application.
6. Record results and unresolved rights in the evidence document before step 5
   assembles its selected snapshot. If a retained reference outside this step's
   files needs repair, return it to the owning preparation step and withhold the
   affected selection until repaired. Do not edit outside the declared footprint.

## Tests

This is a non-code step; no test-file authorship is required. Verify artifacts
rather than adding a runtime test or inferring legal rights from test results.

1. Compare the Markdown and PDF dispositions with explicit owner evidence. Confirm
   rebuilding alone does not appear as redistribution approval.
2. Check that pending/refused artifacts have exact snapshot exclusions and that
   retained references do not require excluded policy content.
3. Compare factual corrections with parser/help and canonical workflow guidance;
   review the diff for unchanged governance rules and approval boundaries.
4. If a rebuild occurs, compare extracted PDF content with the selected Markdown,
   inspect every rendered page, and check metadata and URL annotations for local
   paths. Record commands, tool versions and limitations in the evidence document.
5. Check links in changed Markdown and confirm no runtime source, dependencies,
   schemas, remotes or history change. Preserve unaffected PDF bytes when no
   source correction is required.

## Acceptance criteria

- Both artifacts have a separately recorded rights disposition with its evidence
  or an explicit unresolved decision; no regeneration or scan is called clearance.
- Only rights-approved content is marked publishable. Pending/refused artifacts
  are excluded, and pending rights prevent a full #513 shipment claim.
- Any tool-reference correction is factual and preserves policy meaning.
- A retained PDF reflects its retained Markdown; any regeneration has text,
  metadata/link and visual verification, or an explicit blocking coverage gap.
- The evidence record gives step 5 the exact approved/excluded selection and all
  remaining prerequisites without changing runtime contracts or publishing content.

## References

- [Plan](../../2-public-release-content-snapshot.md) — Scope and ordering.
- [Release handoff](../../../../handoffs/2026-10-19-public-onboarding-and-release.md) — Rebuild and ownership evidence limits.
- [Policy source](../../../reference/ai-assisted-development-policy.md) — Editable source.
- [Driving directives](../../../../integrations/shared/DIRECTIVES.md) — Current workflow authority.
- [Command reference](../../../reference/commands.md) — Current command meanings.

## Applicable guardrails

Use the plan's content-only scope, unchanged-runtime boundary and explicit owner
rights requirement. No publication, remote change, governance redesign or inferred
rights approval is authorized by this step. Keep adjacent distribution work with
#514 and final status reconciliation with step 6.

## Deferred

Owner rights decisions remain with the owner when unavailable. Tool runtime
handling of binary prompt input is a separately filed bug; this step uses the
tracked text source and artifact-appropriate local inspection. Publication,
remote installation, transfer and ongoing sync remain outside the plan.
