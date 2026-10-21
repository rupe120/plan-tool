> **Replaced**: this file has been superseded by `docs/implementation-plans/2-roadmap-source-baseline-recovery.md`.
> Preserved here for history; do not edit.

# Roadmap source-baseline recovery

## Outcome

An explicitly confirmed operator can recover an intentional, exact-canonical
roadmap source change by atomically advancing only its selected canonical
baseline range, while ordinary readers and writers continue to reject every
semantic source drift without that authority.

## Overview

This recovery closes the fail-closed production state recorded in
`docs/implementation-plans/backlog-arcs/backlog-arc-roadmap.md` and
`handoffs/2026-08-27-integration-roadmap-evidence-preflight.md`. It is a source
identity recovery capability, not a retention workflow, feedback revision, or
structural-evidence retry.

## Problem statement

The writer-owned canonical baseline correctly refuses a semantic artifact
change made outside its publication boundary. Baseline enrollment only
bootstraps a wholly unenrolled prefix, and every existing stage, revision, and
evidence entry point admits the source before it can write or invoke a backend.
An intentional exact-canonical direct edit therefore has no safe route to
become the next trusted source identity.

## Architecture

Add one dedicated, confirm-gated roadmap recovery action for an existing
baseline. The command selects one explicit contiguous stage range and requires
a distinct confirmation at the same invocation; `-y`, ordinary stage re-entry,
feedback operations, evidence operations, and enrollment are not substitutes
for that confirmation. It performs no backend request and never rewrites the
selected artifact bytes.

The recovery route owns a narrow source-admission mode. It requires each
selected artifact to be readable, parseable, and exactly canonical; it rejects
an artifact already equal to its baseline, presentation-only drift that normal
admission already accepts, missing or malformed baseline/history state,
pending publication, a noncontiguous selection, and any gate failure. It
admits unselected source only through the existing baseline-backed rule and
re-gates the complete current roadmap with the selected current values before
it advances anything. This keeps an operator-approved semantic replacement
distinct from a raw edit that merely happens to parse.

Under the existing roadmap writer guard, one recoverable journaled generation
replaces only the selected active baseline records, appends immutable
predecessor/successor recovery history for every selected stage, and updates
derived-seed state when the selected range includes the plans stage. The
history binds the roadmap, stage, confirmation, and both canonical identities;
it preserves the displaced semantic baseline for audit without modifying a
receipt, analysis, or artifact. Interrupted recovery uses the existing
all-members-old-or-new recovery rule and refuses an unrecorded disk change.

Canonical identities remain the active baseline identities. A receipt or
analysis issued before recovery remains immutable historical provenance but is
not current after a selected baseline advances; no reader infers, rewrites, or
upgrades its identity from recovery history. New evidence may issue only after
the usual reader admission succeeds against the advanced baseline. Ordinary
baseline enrollment remains bootstrap-only and ordinary source admission
remains fail-closed.

## In scope

- The source-identity, publication, roadmap orchestration, and CLI surfaces
  that own an explicitly confirmed replacement of existing roadmap baselines.
- The recovery history format, currentness behavior, seed-state consequence,
  user-facing result, format contract, and regression coverage needed to make
  that authority auditable and recoverable.
- Updating the originating roadmap arc and Integration handoff when this capability
  ships, including the exact follow-up evidence command.

## Out of scope

- Automatic baseline refresh, a generic accept-current/canonicalize command,
  manual baseline JSON edits, or any recovery mode that treats ordinary source
  drift as trusted.
- Source-artifact mutation, feedback-state changes, seed materialization,
  receipt or analysis rewriting, historical-evidence promotion, or a backend
  call during recovery.
- #242 retention redesign, response history, feedback reopen, bounded local
  revision, structural-rewrite selection, cross-artifact transactions, and
  rerunning the paused Integration evidence workflow before recovery ships.
- Changing generated-candidate byte strictness, malformed-scalar protection,
  or the existing bootstrap enrollment contract.

## Risks

- Replacing a baseline without durable predecessor identity would let a prior
  final appear current or make an operator decision unauditable.
- A partial artifact/baseline/history/seed update could create a state that
  readers cannot classify safely; recovery must use the existing guarded
  generation journal and its exact interruption rules.
- Letting recovery select unchanged, noncanonical, or invalid artifacts would
  duplicate ordinary admission or turn a formatting or gate failure into
  operator authority.
- Scope that omits a changed dependent stage or accepts stale unselected input
  could bless a roadmap whose current gates do not hold.

## Testing

Prove at the bare-plan stage that the recovery authority is distinguishable
from ordinary admission and that old evidence becomes stale rather than
mutable. The detail-grounded bundle will cover successful multi-stage recovery,
all refusal boundaries, complete-roadmap gate validation, seed invalidation,
identity/history integrity, exact interruption recovery, and stale final
currentness across receipt, impact-analysis, escalation, and structural paths.
The Integration replay after implementation uses the exact blocked receipt with the
Codex backend only after the canonical-delivery gate is met; it records whether
the analysis yields a no-workflow `requires-scope-review` result or an admitted
same-artifact/cross-artifact route.

## Acceptance criteria

- Only the dedicated explicit-confirmation action can advance an existing
  baseline, and it makes no backend request or source-artifact edit.
- A successful selected-range recovery is atomically recoverable, retains
  immutable predecessor/successor history, and preserves ordinary source-drift
  refusal everywhere else.
- Recovery requires exact-canonical selected source and a complete
  gate-valid current roadmap; it refuses stale, malformed, incomplete, or
  ambiguous state without changing anything.
- Evidence issued before recovery remains immutable but cannot be current
  under the advanced baseline; fresh evidence follows ordinary admission.
- The completed work updates the roadmap arc and Integration handoff and gives the
  canonical checkout's next Codex-backed evidence command.

## Deferred

- A broader operator-attestation, authorization, or audit-log system beyond
  the explicit confirmation and immutable recovery record this capability
  requires.
- Recovery for non-roadmap canonical baselines.
