# Roadmap Evidence Version-1 Retirement Record

## Release status

**Evidence inventory:** clear. **Retirement decision:** effective 2026-08-24.

The 2026-08-24 inventory finds no version-1 receipt or impact-analysis final
in the closed project/roadmap roster below. The one active final is a valid
version-2 receipt. No immutable final is reissued, archived, moved, replaced,
or modified by this record.

Retirement is approved — see [Approval](#approval) for the accountable
owner's dated confirmation, distinct from the zero-blocker inventory result.
Steps 2–5 may proceed.

## Scope and cutoff

- **Cutoff and scan date:** 2026-08-24.
- **Evidence in scope:** hash-named finals in the `escalations` and
  `impact-analyses` namespaces defined by `EvidenceNamespace`.
- **Excluded protocol:** the structural-revision operation envelope's
  independent `version: 1` protocol is not roadmap evidence and is not an
  inventory row.

### Project and roadmap roster

This is the closed roster of projects and roadmap slugs known to use this
package's roadmap evidence store at the cutoff. `roadmap_dir` and
`scan_evidence` do not discover this roster; this list is the inventory
universe.

| Project | Resolved plans directory | Roadmap slug | Resolved roadmap root | Roster basis |
| --- | --- | --- | --- | --- |
| Integration | `<integration-consumer-root>/docs/implementation-plans` | `integration` | `<integration-consumer-root>/docs/implementation-plans/roadmaps/integration` | The recorded Integration version-2 onboarding identifies it as the only known real roadmap-evidence user. |

The plan-tool source checkout has no `docs/implementation-plans/roadmaps/`
directory and no evidence-store root, so it is not a project/roadmap roster
entry. No other project or roadmap slug is known at the cutoff.

### Consumer roster

This is the closed roster of known systems or workflows that can name a receipt
or receipt-analysis final exactly at the cutoff. It is an operator attestation,
not a result that an evidence scan or exact-final loader can derive.

| Consumer | Exact-final route | Cutoff state | Version-1 final named |
| --- | --- | --- | --- |
| Integration roadmap-evidence workflow | May supply a receipt final to `_load_requested_receipt` and a receipt-analysis pair to `load_structural_revision_preflight`. | The inspected evidence root contains one version-2 receipt and no analysis final. | None. |

No other exact-final consumer is known at the cutoff. Because no version-1
final exists in the project roster, no consumer cutover is required for this
record. A newly disclosed consumer or a consumer that names a version-1 final
makes retirement blocking until the final is reissued or retained as
non-routable history under the rules below.

## Inventory and validation

The inventory resolves the roadmap root through `roadmap_dir`, scans each
namespace through `scan_evidence`, and treats a scan failure as unresolved
evidence rather than as an empty result. It validates receipts with
`parse_receipt` and `validate_receipt_final_name`, and analyses with
`parse_impact_analysis` and `validate_impact_analysis_final_name`.

### Integration / `integration`

| Namespace | Namespace components | Scan result | Hash-named finals | Version-1 finals | Malformed or unreadable finals | Storage failure |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `escalations` | `.plan-tool/evidence/escalations` | complete | 1 | 0 | 0 | none |
| `impact-analyses` | `.plan-tool/evidence/impact-analyses` | complete | 0 | 0 | 0 | none |

The complete receipt inventory contains this non-retirement record:

| Namespace | Final name | Raw-byte SHA-256 | Validation | Schema version | Selector | Reason | Source provenance | Current inspection route |
| --- | --- | --- | --- | ---: | --- | --- | --- | --- |
| `escalations` | `ce95b880271698ad9feabcb41a70d5f62dfcd6acd754b1770e2edb0837c47e11` | `dcede4cfad536a3c6692dab814a1a9b088101b625dd53f21c0447d43abbee6c7` | `parse_receipt` and final-name validation pass | 2 | `domain:fb-plan-tool-lifecycle-responsibilities` | `row-structure` | `01-domain.md`; raw digest `c8070362597aed8d7e91658d0979865c6be34da55bc156bf50aba455a271853e`; canonical source identity digest `630640eeab41291c57143a97c837ba4323e77c0fe64c4d728401b5725c84397d` | `current_escalation_receipt` returns `fresh` |

`impact-analyses` has no final to validate or inspect. Consequently,
`current_impact_analysis`, `_load_requested_receipt`, and
`load_structural_revision_preflight` have no version-1 record or
version-1 receipt-analysis pair to expose at this roster entry. The active
version-2 receipt remains outside the version-1 disposition set.

## Version-1 dispositions

Every discovered valid version-1 final receives exactly one disposition:
`reissue`, `archive-safe`, or `blocking`. A malformed, unreadable, missing
counterpart, unconfirmed, or still-routable final is `blocking` until resolved.

No version-1 receipt or analysis final is discovered in the closed roster, so
this table has no rows. The exclusivity, reissue-chain, archive-retention, and
archive-confirmation checks are therefore vacuously satisfied for this cutoff;
they must be rerun if the roster or a namespace changes.

| Original namespace | Original final | Raw-byte SHA-256 | Validation | Disposition | Replacement or history location | Route and owner verification | Final status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| _No version-1 final discovered._ | — | — | — | — | — | — | — |

### Required treatment if a version-1 final appears

1. Validate the original bytes and storage name before assigning a
   disposition. Treat a failed scan, malformed bytes, or a missing
   receipt-analysis counterpart as `blocking` and leave the original in its
   active namespace.
2. Reissue only through `run_roadmap_escalation_receipt` with currently
   eligible feedback, then derive the replacement through
   `run_roadmap_impact_analysis`. The replacement receipt must validate as
   version 2 and the replacement analysis must bind that replacement receipt.
   Never manufacture a version-2 payload from version-1 fields or infer a
   canonical source identity.
3. Before resolving a `reissue`, record a named confirmation from every
   applicable consumer-roster entry that it uses the replacement final name.
   Then retain the original bytes under a dated history path outside both
   active `EvidenceNamespace` paths, record matching pre-move and retained
   SHA-256 digests, and rescan the active namespace to prove the original is
   absent. Keep the disposition `reissue`.
4. Mark an original `archive-safe` only after its accountable owner confirms
   that no workflow needs it as an exact-name route. Retain its immutable
   bytes under the same kind of dated history path, record matching digests,
   and prove its absence from the active namespace with a fresh scan.
5. Never modify an original, publish replacement bytes under its name, or
   overwrite an occupied replacement final. `publish_evidence` preserves the
   existing exact final instead of overwriting it.

## Release gate

| Gate | Result | Evidence |
| --- | --- | --- |
| Explicit project/roadmap roster | pass | The one known Integration/`integration` entry is named with its plans directory and resolved roadmap root. |
| Explicit consumer roster | pass | Integration is named as the only known exact-final workflow; it names no version-1 final. |
| Both active namespaces scanned | pass | Both Integration namespaces complete without a storage failure; receipt count is 1 and analysis count is 0. |
| Version-1 disposition exclusivity | pass | No valid version-1 final is discovered. |
| Version-1 route preservation | pass | No version-1 route or exact-name pair is discovered, so no reissue, archive, or consumer cutover is required. |
| Blocking legacy rows | pass | None; no version-1 original remains active, malformed, unreadable, unresolved, or unconfirmed. |
| Named retirement approval | pass | The accountable owner recorded a dated approval below, reviewing the roster set, disposition table, and retirement decision. |

**Decision:** retire version-1 reader support. The evidence inventory has no
blocking legacy row, and the required named approval is recorded below. This
document itself does not change runtime behavior, archive evidence, or
touch code; it authorizes steps 2–5 to proceed.

## Approval

**Status: approved.** The accountable owner below reviewed and confirms the
final project/roadmap roster, consumer roster, disposition table, and
retirement decision recorded in this document as of the stated date.

| Approver | Date | Confirmation |
| --- | --- | --- |
| Josh Russo | 2026-08-24 | Reviewed the project/roadmap roster (Integration only), the consumer roster (Integration only, no version-1 final named), the disposition table (no version-1 final discovered), and the retirement decision above; approved. Retirement of version-1 reader support (steps 2–5) may proceed. |

## Verification record

- `scan_evidence` returns the namespace results recorded above in raw final-name
  order; no scan failure is treated as an empty namespace.
- The active receipt's parser and final-name validator pass, its raw-byte digest
  matches this record, and `current_escalation_receipt` reports `fresh`.
- The immutable-publication contract remains the one covered by
  `test_publish_reuses_exact_final_without_overwriting`; this non-code record
  performs no publication.
- A future release review must rerun the two namespace scans and all
  version-1 disposition checks immediately before recording approval.

## Boundaries

This record preserves the version-2 admission, baseline-identity, and
canonical-identity contracts. It does not add a converter, change reader or
CLI behavior, alter the active version-2 receipt, or classify the independent
structural-operation envelope as roadmap evidence.

## Addendum (2026-08-26)

Two schema-version-1 escalation receipts appeared in Integration's active
`escalations` namespace after this record's 2026-08-24 approval —
`62ee4558c87526f352e58d2c214eaa3d16d83206e60c3442a5b9ae12861b7f65` and
`6caf47fa9503b82fd9366c32185cca8960191cad39ae2f8863afd83df4ba20cf`, both
created 2026-08-24T21:23Z via a genuine `roadmap_escalation_preflight` CLI
event, roughly six hours after the write-side schema lock (commit
`1e44899c`, "Make version 2 the only legal roadmap evidence schema") landed.
This does not reopen the approval above: the disposition table was correct
against its stated 2026-08-24 cutoff scan, and no consumer named a
version-1 final at that scan. Both new finals were assigned `archive-safe`
and moved to a dated history path inside Integration's own evidence store,
following this record's own "Required treatment if a version-1 final
appears" procedure above — recorded in Integration's project tree, not this repo.
**Disposition 2026-08-28:** the repository-local BUG is closed as a won't-do.
Fresh current code cannot write or admit version-1 evidence, and the two
Integration-local finals have the required archive-safe disposition. The originating
session evidence is unavailable, so the stale-process explanation remains
unverified provenance rather than a current product defect. Start a new
`plan-tool` process after changing editable source. `BACKLOG.md` #313 remains
an unstarted, broader investigation only if a fresh current process writes
version-1 evidence, another project shows the failure, or provenance identifies
a supported fresh-process route.
