> **Auto-archived**: this plan was swept on 2026-09-17 after reaching `status: completed` with all steps marked `done`.
> Preserved here for history; do not edit.

---
title: Roadmap Canonical Source Identity
intent: Receipt, impact, escalation, and structural-evidence readers consume the writer-owned
  canonical baseline for freshness while preserving immutable raw provenance and refusing
  every source state they cannot safely admit.
status: completed
priority: medium
test_command: uv run pytest tests/ -q -n auto
enforce_step_tests: true
steps:
- id: 1
  title: Define versioned evidence identities, issuance, and compatibility from the
    published baseline
  intent: Separate immutable raw provenance from canonical freshness, define version-matched
    evidence creation and reuse, and preserve baseline ownership, writer publication,
    and ordinary/local revision admission.
  files:
  - plan_tool/roadmap_source_identity.py
  - plan_tool/roadmap_escalation.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_structural_revision.py
  - tests/test_roadmap_source_identity.py
  - tests/test_roadmap_escalation.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_structural_revision.py
  allowed_mentions:
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_impact_run.py
  complexity: high
  change_type: feature
  detail: docs/implementation-plans/plan-details/roadmap-canonical-source-identity/01-define-versioned-evidence-identities.md
  status: done
- id: 2
  title: Make impact capture and analysis consume canonical freshness without source
    mutation
  intent: Bind stage semantics in impact evidence to the existing baseline while retaining
    raw captured bytes plus direct source-record and brief currentness checks, and
    refuse missing, incomplete, or semantically drifted source state.
  files:
  - plan_tool/roadmap_impact_snapshot.py
  - plan_tool/roadmap_impact_analysis.py
  - plan_tool/roadmap_impact_run.py
  - tests/test_roadmap_impact_snapshot.py
  - tests/test_roadmap_impact_analysis.py
  - tests/test_roadmap_impact_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  depends_on_notes:
    1: Defines the versioned canonical freshness identity that impact evidence records.
  detail: docs/implementation-plans/plan-details/roadmap-canonical-source-identity/02-make-impact-capture-analysis-consume.md
  status: done
- id: 3
  title: Make escalation and structural-evidence readers admit only current versioned
    evidence
  intent: Use the published baseline only for stage semantics, recheck live feedback
    eligibility, and admit only matching-version receipt and analysis evidence without
    allowing a reader to initialize, repair, or advance the baseline.
  files:
  - plan_tool/cli/roadmap_cmd.py
  - plan_tool/roadmap_escalation_selection.py
  - plan_tool/roadmap_escalation_run.py
  - plan_tool/roadmap_revision_publish.py
  - plan_tool/roadmap_structural_revision.py
  - tests/cli/test_roadmap_cmd.py
  - tests/test_roadmap_escalation_selection.py
  - tests/test_roadmap_escalation_run.py
  - tests/test_roadmap_revision_publish.py
  - tests/test_roadmap_structural_revision.py
  - tests/test_roadmap_structural_revision_run.py
  complexity: high
  change_type: feature
  depends_on:
  - 1
  - 2
  depends_on_notes:
    1: Supplies the version boundary that keeps raw provenance distinct from freshness.
    2: Supplies the baseline-backed impact evidence that structural admission consumes.
  detail: docs/implementation-plans/plan-details/roadmap-canonical-source-identity/03-make-escalation-structural-evidence.md
  status: done
- id: 4
  title: Publish the reader-only evidence contract and retire superseded references
  intent: Make version boundaries, reader refusal, and raw-provenance requirements
    reviewable without reopening writer-owned baseline behavior.
  files:
  - ROADMAP_FORMAT.md
  - DATA_CONTRACT.md
  - docs/ARCHITECTURE.md
  - tests/test_data_contract.py
  - tests/test_roadmap_format.py
  complexity: medium
  change_type: non-code
  depends_on:
  - 3
  depends_on_notes:
    3: Completes the fields and refusal outcomes that the public evidence contract
      names.
  detail: docs/implementation-plans/plan-details/roadmap-canonical-source-identity/04-publish-reader-only-evidence-contract.md
  status: done
---
# Roadmap Canonical Source Identity

## Overview

The bounded stage-feedback route already publishes a writer-owned canonical
baseline and uses it for ordinary and local revision admission. This plan
extends that settled source identity only to readers that create or judge
evidence: receipts, impact snapshots and analyses, escalation freshness, and
structural evidence. It does not recreate baseline storage, enrollment,
publication, recovery, or revision admission.

## Problem statement

`roadmap_escalation_selection.canonical_artifact_snapshot`,
`roadmap_escalation_run.current_escalation_receipt`,
`roadmap_impact_snapshot._capture_artifact`, and
`roadmap_impact_analysis.build_impact_analysis` still need a common rule for
evidence freshness after a presentation-only source change. Their retained raw
bytes and digests provide immutable provenance, but raw identity alone cannot
also show that current parsed content equals the writer-published canonical
baseline. Structural evidence consumes those same inputs and needs the same
versioned boundary.

## Architecture

The existing writer-owned baseline remains the only source that decides
canonical freshness. An evidence reader reads it through the existing
side-effect-free admission boundary and chooses a closed result: current
canonical content, semantic source drift, missing baseline, incomplete
publication, or the existing unreadable and unparsable source refusal. It does
not initialize a baseline, repair source text, recover a publication, advance
a baseline, or turn a semantic hand edit into accepted input.

Freshness is source-scoped and conjunctive. The baseline identity covers only
the parsed semantics of each staged artifact; it excludes `feedback` and may
therefore admit a presentation-only stage change. Receipt creation and
currentness recheck the selected feedback row's live eligibility independently.
Impact capture and analysis retain direct currentness checks for the source
record and brief digests; neither receives a baseline identity. Any failed
baseline, feedback, source-record, or brief check refuses the evidence without
repairing the source.

Evidence carries two identities when the versioned contract needs both:

- Raw source bytes and their digest remain immutable provenance. They retain
  what the reader observed and are never canonicalized or rewritten.
- A canonical baseline identity records the freshness value selected from the
  writer-owned source state. Currentness compares this identity through the
  admitted reader path, not through a parser round trip of the input alone.

The version-2 canonical baseline identity is one closed, redacted value:
`source_identity_version`, `roadmap_slug`, `stage_key`, `format_version`, and
the baseline semantic `digest`. It is copied only from a fully validated
`BaselineRecord`, contains neither its projection nor feedback, and compares
equal only when all five fields match. A version-2 snapshot retains one such
identity per configured stage in stage order; receipts and analyses retain the
identity for their selected stage. No reader selects a smaller identity subset
or derives an identity from raw bytes.

Version-1 receipts, impact analyses, and structural evidence remain readable
and retain their exact-raw currentness behavior. They receive no inferred
canonical identity and no rewrite. Version-2 evidence records canonical
freshness separately from raw provenance; a mixed-version structural evidence
pair refuses rather than inventing a bridge.

New receipt issuance emits version 2 only through the version-2 admission
path; if that path cannot bind the current source to a published baseline,
creation refuses instead of falling back to version 1. A stored version-1 final
remains version 1 and is reusable only through its exact-raw-current path. An
exact-raw-current version-1 receipt may create or reuse only a version-1
analysis, and a version-2 receipt produces or reuses only a version-2 analysis.
A legacy receipt that is not exact-raw current refuses analysis rather than
receiving an inferred version-2 identity. Structural preflight accepts only one
matching-version exact pair.

Version-specific capture happens before currentness comparison. A stored
version-1 record uses the existing exact-raw capture and recheck path and does
not read a baseline. A new or stored version-2 record requires strict UTF-8
and a parsable source, then compares its parsed stage semantics to the
published baseline. A renderer-byte difference is admitted in this version-2
source-reader path only when that baseline comparison succeeds; its original
raw bytes and digest remain unchanged as provenance. It never normalizes or
rewrites the source. New evidence publication still rechecks the complete raw
snapshot inside its guarded window, whereas later version-2 receipt, analysis,
and structural currentness compares the stored closed canonical identities and
the independent live inputs rather than rebuilding an exact raw-evidence
final. Generated patches and proofs, and immutable receipt and analysis
finals, remain renderer-byte strict.

Version-2 receipt creation holds one reader guard across baseline/artifact
admission, the required pending-publication check, final raw-snapshot recheck,
and receipt evidence publication. Escalation views rescan and evaluate evidence
inside the same reader guard. A guard failure or a pending publication refuses
or reports no current receipt; it cannot expose a receipt or handoff formed
from a recoverable artifact/baseline pair. A mixed-version view evaluates each
record against a cache key that includes both the stage and evidence version,
so evidence scan order cannot apply version-1 raw currentness to a version-2
record or the reverse.

Ordinary structural preflight refuses every pending generation. The sole narrow
exception is the second preflight inside
`publish_structural_revision_proof`: its active writer token may present the
exact `structural-feedback-publication` generation that the publisher has just
journaled. The preflight validates the token’s roadmap binding and active state,
the generation kind, and every generation member before treating that one
pending state as the writer's own protected replacement boundary. A missing,
expired, wrongly bound, different-kind, or different-member allowance refuses;
the exception grants no general reader recovery, journal mutation, or broader
structural authority. Structural preflight passes that exact validated allowance
through version-2 impact snapshot capture and recheck; those shared functions
reject every pending generation by default and compare the loaded journal to
the allowance before admitting this one replacement-bound read.

Impact capture retains raw inspection data while recording the canonical
identity needed by `build_impact_analysis`. Escalation selection and
`current_escalation_receipt` use the same versioned distinction for receipt
creation and currentness. Structural evidence admits only the exact selected
versioned receipt and analysis pair and preserves the existing relation and
selection authority. Generated patch and proof candidates remain byte-strict
renderer checks: they are generated-candidate validation, not current-source
readers.

## References

- [YAML Ain’t Markup Language (YAML™) Revision 1.2.2https: — Defines representation equality while leaving comments and formatting outside parsed values.
- [hashlib — Secure Hashes and Message Digestshttps: — Defines the SHA-256 primitives used for immutable raw provenance and canonical freshness identities.

## Steps

See the `steps:` block in the frontmatter.

## Out of scope

- Baseline initialization, enrollment, writer publication, recovery, or any
  change to ordinary or local revision admission; the bounded-feedback route
  already owns those behaviors.
- A reader-side repair, canonicalize, accept-current, or migration action.
- Treating a semantic hand edit as accepted source or making raw provenance
  mutable to match canonical freshness.
- Relaxing generated structural patch/proof canonicality or malformed-scalar
  protection.
- BACKLOG #242's retention workflow, and a hand-edit-to-feedback review
  bridge (proposed as #298, retired 2026-08-27 for lack of real hand-edit
  evidence — see `docs/history/backlog-decisions.md`).

## Risks

- Conflating raw provenance with canonical freshness either rejects harmless
  presentation drift or lets stale semantic evidence look current.
- A reader that initializes or repairs source state turns evidence inspection
  into writer authority and can bless an unaudited hand edit.
- A version-1 final that acquires a new identity by inference ceases to be
  immutable evidence; a mixed-version pair must fail closed instead.
- Structural evidence can accidentally widen selection or relation authority
  if its freshness admission is not kept separate from its existing exact-pair
  validation.

## Testing

Fixture-driven tests prove that impact, escalation, receipt-currentness, and
structural-evidence readers preserve the raw bytes and digest they observed
while using the existing baseline for version-2 freshness. Presentation-only
drift admits a strict-UTF-8, parsable version-2 source only where its full
baseline identity matches; semantic drift, a missing or incomplete baseline,
unreadable or unparsable source, and mixed evidence versions refuse without
writing source or evidence. Version-1 finals remain parseable and
exact-byte-current without inferred identity or rewriting. Candidate-byte and
malformed-scalar rejection tests remain green unchanged.

The fixture matrix proves that a baseline-preserving stage change remains
current only while the selected feedback row stays eligible and the source
record and brief digests remain current; each independent change refuses. It
also proves version-1 exact-raw receipt-to-analysis reuse, version-2
receipt-to-analysis creation and reuse, refusal of a stale version-1 receipt,
mixed-version structural-pair rejection, reader-guard refusal during a pending
publication, the exact active-writer structural-publication exception, and
order-independent mixed version-1/version-2 receipt views.

**Per-step test strategy** (derived from each step's `change_type`):

- step 1 (feature) — tests cover versioned evidence identity and version-1 compatibility.
- step 2 (feature) — tests cover side-effect-free impact capture and analysis freshness.
- step 3 (feature) — tests cover escalation and structural reader admission at every refusal boundary.
- step 4 (non-code) — tests verify the published evidence fields and reader boundaries.

## Acceptance criteria

- The re-scoped plan contains no future baseline enrollment, writer
  publication, recovery, or ordinary/local revision-admission deliverable.
- Version-2 receipt, impact, escalation, and structural evidence distinguish
  immutable raw provenance from canonical freshness supplied by the existing
  writer-owned baseline. Their one closed baseline identity contains source
  identity version, roadmap slug, stage key, format version, and semantic
  digest; it applies only to stage semantics. Live feedback eligibility and
  source-record and brief currentness remain independent admission checks.
- Version-1 finals remain raw-evidence compatible, exact-byte-current, and
  unmodified. Version-1 receipts pair only with version-1 analyses, version-2
  receipts pair only with version-2 analyses, legacy evidence receives no
  inferred upgrade, and mixed-version structural evidence refuses.
- New receipt creation is version 2 only. A stored exact-raw-current version-1
  receipt may create or reuse version-1 analysis evidence, without upgrading
  or rewriting its receipt.
- Version-1 capture and recheck remain raw-only and need no baseline. Version-2
  source readers accept a strict-UTF-8, parsable presentation change only when
  the full closed baseline identity matches; their later currentness does not
  use a raw-stage mismatch as a freshness failure. New evidence publication
  remains protected by an exact raw snapshot recheck, and generated candidates
  remain renderer-byte strict.
- Version-2 receipt creation and escalation views hold a reader guard across
  their artifact/baseline observation and reject pending or changed publication
  state. A mixed-version view caches observation by stage and evidence version,
  so scan order cannot affect either record’s currentness.
- Structural preflight rejects pending generations except the publisher’s own
  exact structural-feedback generation at its second preflight, verified by an
  active matching writer token. That exception neither recovers nor changes a
  journal and rejects every other pending state.
- `canonical_artifact_snapshot`, `current_escalation_receipt`,
  `_capture_artifact`, and `build_impact_analysis` refuse source states they
  cannot admit without initializing, repairing, or advancing baseline state,
  including ineligible feedback and changed source-record or brief inputs.
- Structural evidence preserves existing exact-pair selection and relation
  authority while it adds no reader-side source mutation.
- Documentation and contract tests name only the reader-only freshness work
  that remains after the bounded stage-feedback route ships.

## Deferred

- BACKLOG #242 retention work remains paused until this reader-only plan is
  audited and its redesign can use the landed bounded merge layer.
- A hand-edit-to-feedback review bridge was considered (BACKLOG #298) but
  retired 2026-08-27 for lack of real hand-edit evidence; revisit only if a
  concrete case emerges.
- `ea6b41fe` supplies a safe block-scalar reviewer stub and malformed-feedback
  recovery guidance. The canonical renderer preserves supported scalar styles,
  so this is not a global hand-authored YAML-safety guarantee; reader freshness
  does not mediate a direct raw YAML edit.
- Broader baseline support for non-roadmap artifacts and any new roadmap stage
  remain separate work.
