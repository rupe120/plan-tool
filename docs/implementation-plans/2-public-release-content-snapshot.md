---
format_version: 1
title: Public Release Content Snapshot
intent: Publishable tracked content and filenames contain no private organization
  or client material, while retained examples and tests remain coherent.
status: completed
priority: medium
risk_profile: standard
risk_profile_rationale: Risk declaration uses standard because --yes does not accept
  model risk proposals.
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
source_seed: plan-seeds/public-release-content-snapshot.md
steps:
- id: 1
  title: Record the selected snapshot content, ownership decisions and report exclusions
  intent: Give every retained or excluded content class an explicit ownership and
    publication disposition.
  files:
  - BACKLOG.md
  - handoffs/2026-10-19-public-onboarding-and-release.md
  creates:
  - docs/evidence/public-release-content-snapshot.md
  complexity: high
  change_type: non-code
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/01-record-selected-snapshot-content.md
  status: done
- id: 2
  title: Prepare the selected content with report omissions, neutral replacements
    and repaired references
  intent: Produce coherent publishable content without exposing private material or
    presenting sanitized reports as qualified historical audits.
  files:
  - docs/evidence/public-release-content-snapshot.md
  - docs/evidence/integration-context-budget-2026-10-09/provenance.json
  - docs/evidence/integration-context-budget-2026-10-09/sizing.md
  - handoffs/README.md
  - .plan-tool/plans.json
  - docs/evidence/authored-artifact-structure-versioning.md
  - docs/explanations/audit-pass-persistence.md
  - docs/explanations/nondeterministic-plan-design.md
  - docs/history/backlog-decisions.md
  - docs/implementation-plans/archive/2-jira-grade-01-detail-instrument.md
  - handoffs/2026-09-14-developer-docs-and-tracking.md
  - handoffs/2026-09-14-roadmap-aidlc-integration-delivery.md
  - handoffs/2026-09-25-roadmap-candidate-vocabulary-retry.md
  - handoffs/2026-10-20-public-release-content-snapshot-plan-review.md
  - plan-seeds/archive/jira-grade-01-detail-instrument.distilled.replaced.md
  - plan-seeds/archive/jira-grade-01-detail-instrument.replaced.md
  - BACKLOG.md
  - handoffs/2026-10-19-public-onboarding-and-release.md
  complexity: high
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Provides the exact tracked-path selection and ownership decisions; omit captured
      reports from the snapshot by default, preserve needed conclusions in the evidence
      record, and resolve dependent references before excluding historical documents.
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/02-prepare-selected-content-report.md
  status: done
- id: 3
  title: Make retained guidance explain decisions and procedures directly
  intent: Let public readers understand retained decisions and follow instructions
    using only the fresh snapshot.
  files:
  - CLAUDE.md
  - integrations/shared/DIRECTIVES.md
  - docs/evidence/claude-md-measured-incidents.md
  - handoffs/README.md
  - handoffs/2026-10-19-public-onboarding-and-release.md
  - docs/evidence/public-release-content-snapshot.md
  complexity: high
  change_type: non-code
  depends_on:
  - 2
  depends_on_notes:
    2: Establishes which historical documents survive; review all retained citations,
      preserve useful explanations and content hashes, and require architect-tier
      review for CLAUDE.md edits.
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/03-make-retained-commit-citations-self.md
  status: done
- id: 4
  title: Apply owner rights decisions to policy retention, preserving governance and
    limiting PDF replacement
  intent: Keep client-derived material out of the publishable selection until its
    redistribution rights are established.
  files:
  - AI_SDLC_POLICY.pdf
  - docs/reference/ai-assisted-development-policy.md
  - docs/evidence/public-release-content-snapshot.md
  complexity: medium
  change_type: non-code
  depends_on:
  - 1
  depends_on_notes:
    1: Requires explicit owner rights decisions before dependent retention; preserve
      the completed rebuild unless factual tool-reference corrections require replacement,
      using explicitly recorded external PDF tools rather than new runtime dependencies.
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/04-apply-owner-rights-decisions-policy.md
  status: done
- id: 5
  title: Verify the selected content and existing tests in an independent single-commit
    snapshot
  intent: Prove that the selected content remains usable without internal ancestry
    or ignored local configuration.
  files:
  - docs/evidence/public-release-content-snapshot.md
  complexity: high
  change_type: non-code
  depends_on:
  - 3
  - 4
  depends_on_notes:
    3: Provides self-contained retained guidance and an explicit selection whose links,
      discovery, citations and digest claims can be checked.
    4: Provides the rights-approved selection or explicit exclusions; unresolved rights
      prevent full shipment.
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/05-verify-selected-content-existing-tests.md
  status: done
- id: 6
  title: 'Reconcile BACKLOG #513 and publish the local verification pickup record'
  intent: Make the completed preparation, remaining prerequisites and publication
    boundary clear to the next owner.
  files:
  - BACKLOG.md
  - handoffs/2026-10-19-public-onboarding-and-release.md
  - docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md
  - docs/evidence/public-release-content-snapshot.md
  complexity: low
  change_type: non-code
  depends_on:
  - 5
  depends_on_notes:
    5: 'Supplies identifier and filename scans, link and instruction checks, provenance
      verification, affected test results and snapshot test results; record history-dependent
      skips without weakening tests, and remove #513 only after full shipment and
      required rights decisions.'
  detail: docs/implementation-plans/plan-details/public-release-content-snapshot/06-reconcile-backlog-513-publish-local.md
  status: done
---
# Public Release Content Snapshot

## Overview

Prepare selected repository content for an independently verified release
candidate. Use `https://github.com/rupe120/plan-tool` as the selected destination;
confirm ownership and visibility before publication or an organization transfer.
Keep examples, fixtures and paths portable. Publication and transfer remain
separate from content preparation.

## Problem statement

Release content must give a maintainer useful examples, clear decisions and
working procedures. Keep private identifiers out while preserving technical
meaning, evidence identity and test behavior. Retain dated evidence only when it
supports a current decision or explains a failure to avoid. Keep policy source
and PDF aligned with the recorded ownership decision.

## Architecture

- Use `handoffs/2026-10-19-public-onboarding-and-release.md` for completed cleanup,
  owner-approved retained names and the current review evidence. Ignored scratch
  inventories are leads, not fresh-clone dependencies; regenerate scope evidence
  from tracked files when needed. Classify identifiers by ownership before editing.
- Explain current decisions, invariants and procedures directly. Keep a citation
  only when it supports a useful claim, and preserve the explanation beside it.
  Keep measurement and content identities tied to their actual inputs; remove
  session chronology and availability commentary that does not guide future work.
- Review historical plans, reports and handoffs for continuing value. Preserve live
  decisions in canonical owners before omitting superseded material; repair links,
  discovery and tests affected by any removal. Preserve unrelated untracked files.
- Retained sanitized reports are explicitly historical examples, not original-byte
  replay evidence or reusable qualified audits. Select a bounded treatment during
  plan authoring: preserve useful non-identifying evidence, omit reports when that
  is safer, and account for every changed path's digest/provenance implications.
  Use existing runtime contracts; do not change report readers or qualification
  rules to accommodate release preparation. `plan_tool/fingerprint.py:
  audit_input_revision` includes detail paths in the bundle digest, and
  `plan_tool/review_persistence.py:normalize_audit_revision` validates it.
- Step 2 owns the 13 retained document owners named in its footprint whose
  concrete report references or capture-opening instructions depend on omitted
  reports. Repair those dependencies before subsequent snapshot verification;
  preserve their useful conclusions and distinguish historical provenance from
  instructions that readers must still follow. Newly discovered dependencies
  outside the declared footprint remain explicit scope decisions, not extra edits.
- Content hashes, artifact IDs and report fingerprints keep their content-identity
  meaning. A sanitized example must distinguish its own bytes from any historical
  measurements or hashes of originals. Follow the existing distinction in the
  Integration context-budget evidence bundle rather than fabricating exact replay.
- The policy PDF is already rebuilt from its tracked Markdown source. Limit any
  policy-source correction to factual tool references required by this cleanup;
  do not change governance rules. Record redistribution ownership/rights decisions
  with unresolved items visible; obtain missing owner decisions before retaining
  dependent content as publishable. Do not infer rights from anonymization.
- Validate the selected content in a temporary independent local Git repository
  with a single snapshot commit and no internal objects, refs or ignored local
  configuration. This is a disposable verification artifact, not a rewrite of this
  checkout or of the existing GitHub repository. Check retained instructions and
  history-dependent checks there, reporting limitations rather than weakening
  application contracts. #515 retains the full fresh-consumer onboarding exercise.
- The final documentation/status step reconciles BACKLOG #513. Mark it plan-authored
  while pending; remove it only after full shipment and required rights decisions.
  Preserve any unresolved prerequisite or deferred follow-up in its proper backlog.

## Scope guardrails

This plan changes publishable repository content and bounded verification artifacts
only. It does not authorize push, PR publication, merge, public release, remote
changes, organization transfer, or rewriting existing Git history. Keep report and
artifact runtime contracts unchanged. Do not treat a scan match as a privacy verdict
or a missing match as a rights/secrets clearance. CLAUDE.md changes require
architect-tier review. Keep legitimate owner-approved technical references and
approved distribution identifiers. Do not reopen settled licensing/hosting choices.

## References

- `BACKLOG.md` — #513 scope contract and #514 selected boundary.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — cleanup, inventory and decisions.
- `docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md` — ordered scope.
- `docs/evidence/integration-context-budget-2026-10-09/provenance.json` and `sizing.md` — sanitized-example provenance.
- `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision` — report identity contract.
- `docs/reference/ai-assisted-development-policy.md` — tracked PDF source.
- `docs/reference/documentation-style.md`, `SEED_FORMAT.md`, `integrations/shared/DIRECTIVES.md` — documentation and planning rules.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

Git history rewriting, remote changes, blanket removal
of legitimate third-party product names, or changing tool contracts.

Additionally exclude publication, GitHub visibility changes or transfer, actual
remote snapshot installation, ongoing sync implementation, onboarding/provider/model
work in #508–#512/#377, and #515's full pipeline exercise. No generic sanitizer,
semantic privacy/rights validator, new runtime gate, hash mapping service, report
schema migration, concurrency, or unrelated documentation/policy redesign.

## Risks

Removing historical material can break evidence links and discovery. Rewriting a
path in a hashed report can invalidate its revision or misstate original provenance.
New plan/audit outputs can introduce local paths again, so final inventory must
cover generated artifacts too. A fresh root removes ancestry but does not sanitize
file content or establish redistribution rights.

## Testing

Repeat identifier and vocabulary scans, review structured files and
filenames, check links and run affected tests plus the full suite when fixtures/code
change. CLAUDE.md edits require architect-tier review.

Verify retained evidence's stated provenance and digest consistency, then repeat
content/link/instruction checks in the independent snapshot-only repository.
Record selected content, results, explicit exclusions and unresolved rights or
credentials coverage. Scans are bounded evidence, not certification of semantics.

## Acceptance criteria

- Publishable content has a reviewed ownership/disposition record; remaining private
  material is removed or replaced coherently without reopening completed sweeps.
- Retained explanations state the current decision, supporting evidence and usable
  procedure; content digests retain their stated meaning.
- Retained links, discovery and affected tests work with the selected content in a
  local snapshot-only repository. Any unresolved rights or release prerequisite
  remains explicit and prevents a claim of full #513 shipment.
- BACKLOG #513 and the pickup handoff reflect the actual result. No publication,
  remote change, internal-ancestry import or runtime-contract change occurs.

## Deferred

#514 owns the existing private GitHub repository/ref inspection, final release and
update guidance, and a later sync procedure that does not import internal ancestry.
Other onboarding work follows the public-release arc after this prerequisite.
