> **Replaced**: this file has been superseded by `docs/implementation-plans/2-public-release-content-snapshot.md`.
> Archived brief. Use the implementation plan for execution scope and the release pickup for current next actions.

# Public-release content for a fresh sanitized snapshot

Source: BACKLOG #513, coordinated by
`docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md`.
The full source scope contract below remains authoritative. This effort finishes
current-content preparation; #514 owns distribution and history/sync procedure.

## Outcome

Publishable tracked content and filenames contain no private organization
or client material, while retained examples and tests remain coherent.

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

## In scope

Inventory prose, structured evidence, fixtures, demos, lessons, seeds,
plans, handoffs, local paths, tenant URLs and filenames; remove private material or
substitute neutral examples; identify client-derived content that cannot safely be
retained.

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

## Allowed behavior changes

Sanitize or remove content and repair affected
links/fixtures; preserve useful non-identifying evidence and test semantics. Classify
owner projects separately from client projects before treating their names as private.

## Allowed reorganization

only the smallest relocation needed for this outcome; no
unrelated restructuring.

## Out of scope

Git history rewriting, remote changes, blanket removal
of legitimate third-party product names, or changing tool contracts.

Additionally exclude publication, GitHub visibility changes or transfer, actual
remote snapshot installation, ongoing sync implementation, onboarding/provider/model
work in #508–#512/#377, and #515's full pipeline exercise. No generic sanitizer,
semantic privacy/rights validator, new runtime gate, hash mapping service, report
schema migration, concurrency, or unrelated documentation/policy redesign.

## Scope guardrails

This plan changes publishable repository content and bounded verification artifacts
only. It does not authorize push, PR publication, merge, public release, remote
changes, organization transfer, or rewriting existing Git history. Keep report and
artifact runtime contracts unchanged. Do not treat a scan match as a privacy verdict
or a missing match as a rights/secrets clearance. CLAUDE.md changes require
architect-tier review. Keep legitimate owner-approved technical references and
approved distribution identifiers. Do not reopen settled licensing/hosting choices.

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

## Stop / defer

file adjacent work separately; resolve missing owner decisions
before dependent implementation.

## Deferred

#514 owns the existing private GitHub repository/ref inspection, final release and
update guidance, and a later sync procedure that does not import internal ancestry.
Other onboarding work follows the public-release arc after this prerequisite.

## References

- `BACKLOG.md` — #513 scope contract and #514 selected boundary.
- `handoffs/2026-10-19-public-onboarding-and-release.md` — cleanup, inventory and decisions.
- `docs/implementation-plans/backlog-arcs/backlog-arc-public-release.md` — ordered scope.
- `docs/evidence/integration-context-budget-2026-10-09/provenance.json` and `sizing.md` — sanitized-example provenance.
- `plan_tool/fingerprint.py:audit_input_revision` and `plan_tool/review_persistence.py:normalize_audit_revision` — report identity contract.
- `docs/reference/ai-assisted-development-policy.md` — tracked PDF source.
- `docs/reference/documentation-style.md`, `SEED_FORMAT.md`, `integrations/shared/DIRECTIVES.md` — documentation and planning rules.
