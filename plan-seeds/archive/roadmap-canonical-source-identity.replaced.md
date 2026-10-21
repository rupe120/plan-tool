> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-canonical-source-identity.md`.
> Preserved here for history; do not edit.

# Roadmap canonical source identity

## Outcome

A roadmap consumer accepts source text that differs from its persisted
canonical baseline only in presentation, refuses semantic source drift, and
keeps the raw bytes named by an escalation receipt distinct from the canonical
identity that governs receipt freshness and structural-revision evidence.

This seed replaces BUG_BACKLOG's invalid parser-round-trip approach. An
artifact cannot prove that its own value is unchanged by comparing itself with
its own render.

## In scope

- A writer-owned, per-roadmap and per-stage canonical baseline that records the
  canonical artifact identity required to compare a later source with a known
  value. Existing exact-canonical artifacts can initialize that baseline; a
  noncanonical artifact never can.
- One source-classification contract for the impact snapshot, local revision,
  escalation receipt creation/currentness, and structural-revision preflight.
  Presentation-only source drift uses the baseline's canonical working text;
  a parsed difference from the baseline is a source-drift refusal.
- Receipt and impact evidence that retain the original raw-source digest for
  provenance while recording and checking the canonical-baseline identity for
  freshness. A cosmetic edit keeps eligible evidence current; a semantic edit
  does not.
- Atomic baseline publication with every roadmap writer-owned artifact
  publication, under the existing roadmap writer guard, and contract/test
  updates that make the two identities visible and unambiguous.

## Overview

The existing `render(parse(current_text)) == current_text` check establishes
only whether the current bytes are canonical. A comparison of `current_text`
with a render derived from `current_text` cannot detect that a value changed.
The replacement uses a previously persisted canonical baseline as the source
of truth: equal parsed values admit presentation-only drift and supply its
canonical working text; unequal values remain refused.

## Problem statement

`roadmap_impact_snapshot._capture_artifact`,
`roadmap_revision.preflight_feedback_revision`, and
`roadmap_escalation_selection.canonical_artifact_snapshot` each currently
derive their only comparison value from the input they read. The structural
route then binds `RoadmapImpactSnapshot.artifact_digests` into impact analysis
and revision publication, while `EscalationReceipt.source.sha256` and
`current_escalation_receipt` bind raw source bytes. These facts cannot safely
share one digest once presentation-only drift is accepted: the raw receipt
remains immutable evidence, but source freshness must compare a current value
with the canonical value selected at receipt creation.

The earlier parser-round-trip proposal is invalid. It would accept a valid
manual value edit without detecting it, while still rejecting a future
render-time feedback ordering change when the parser retains that order. It
also incorrectly treats patch/proof candidate checks as source readers.

## Architecture

The baseline is the only authority for presentation tolerance. It stores a
canonical stage value produced by the selected stage renderer and identifies
the stage and roadmap it belongs to. A source reader decodes and parses the
current text, compares that parsed value with the persisted baseline value,
and chooses exactly one result: canonical/equal source with baseline canonical
working text, semantic source drift refusal, missing baseline initialization
from already exact-canonical bytes only, or the existing unreadable/unparsable
refusal. It never repairs or blesses a noncanonical source while creating a
baseline.

Every writer that publishes a roadmap artifact updates its matching baseline
in the same guarded publication boundary. Receipt creation stores both the
raw-source digest and the baseline identity. Receipt currentness and impact/
structural snapshot binding use the baseline identity to survive
presentation-only drift; raw receipt bytes and their digest remain immutable
provenance. The route's result and format contract distinguish those two
identities rather than recasting raw evidence as canonical text.

`roadmap_structural_revision_patch._parse_canonical_candidate` and
`roadmap_structural_revision_proof._require_canonical_text` remain exact
renderer-byte checks on generated candidates. They do not load current source
text and must not use the tolerance contract. The malformed-scalar-span
protection therefore keeps its current inputs and behavior.

`roadmap-revision-retention` stays separate. Its direct reviewer change to
`state: closed` is semantic source drift until a writer-owned close workflow
publishes a new baseline; this effort does not design that workflow or make a
hand edit self-authorizing.

## Out of scope

- Accepting a current artifact simply because it parses or passes the ordinary
  roadmap gates; that would accept undetectable semantic edits.
- A generic repair, canonicalize, or accept-current command that lets an
  operator replace a baseline from noncanonical source text.
- Changing the raw bytes or digest preserved by any existing escalation
  receipt, weakening receipt validation, or broadening immutable evidence
  readers beyond their settled contract.
- Relaxing generated patch/proof candidate canonicality or the
  malformed-scalar-span protection.
- BACKLOG #242's feedback-close workflow, render sort, or any other retention
  feature. It must later consume this source-identity contract rather than
  make a direct hand edit authoritative.

## Risks

- A baseline that a reader can silently derive from noncanonical input only
  repackages the invalid parser-round-trip rule. Initialization and updates
  must remain writer-owned or exact-canonical-only.
- The raw receipt digest and canonical baseline identity protect different
  properties. Collapsing them would either invalidate harmless presentation
  drift or allow stale semantic evidence to look current.
- Existing roadmaps have no baseline. Their migration must fail closed on
  noncanonical text and must not alter artifact bytes merely to initialize
  metadata.

## Testing

Fixture-driven tests prove that each source family accepts a changed comment or
formatting only when its parsed artifact equals the stored baseline, then uses
canonical working text and preserves the original receipt raw digest. A changed
semantic value, missing baseline plus noncanonical text, or baseline from the
wrong stage remains refused at every source boundary. A current receipt and a
structural revision remain current after presentation-only drift but not after
semantic drift. Existing candidate-byte and malformed-scalar rejection tests
stay green unchanged. Mutation of the baseline comparison must make these
source-family tests fail.

## Acceptance criteria

- A persisted canonical baseline, not a render of the input under test,
  determines whether presentation-only source drift is acceptable.
- Every accepted presentation-only source produces canonical working text;
  every semantic difference from its baseline refuses.
- Raw receipt bytes remain immutable provenance, while receipt freshness and
  structural evidence use the recorded canonical identity.
- Generated structural patch/proof candidates remain byte-strict and retain
  malformed-scalar rejection.
- The format contract names the baseline, raw-evidence, initialization, and
  drift behavior precisely; the BUG_BACKLOG entry is removed only after that
  behavior ships.

## Deferred

- A writer-owned reviewer-close workflow for BACKLOG #242.
- Any operator command that intentionally authorizes a semantic hand edit.
- Broader canonical-baseline support for non-roadmap artifacts.
